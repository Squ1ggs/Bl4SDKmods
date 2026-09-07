"""Shared placement target for Boosting Tools spawning utilities."""

from __future__ import annotations

import time
from typing import Any

import unrealsdk

MODES: tuple[tuple[str, str], ...] = (
    ("local", "From me"),
    ("party", "From selected player"),
    ("npc_nearest", "Near nearest NPC"),
    ("freecam", "At debug cam"),
)

_mode = "local"
_party_index: int | None = None
_last_label = "me"

# find_all(OakCharacter) is expensive — cache nearest NPC across bulk spawn ticks.
_NPC_CACHE_TTL_SEC = 1.35
_npc_cache_at = 0.0
_npc_cache_origin_id = 0
_npc_cache_actor: Any | None = None
_npc_cache_max_d = 0.0


def set_target(mode: str, party_index: int | None = None) -> None:
    global _mode, _party_index
    requested = str(mode or "local").strip().lower()
    if requested in ("debug_cam", "debugcam", "debug"):
        requested = "freecam"
    _mode = requested if requested in {key for key, _label in MODES} else "local"
    _party_index = None if party_index is None else max(0, int(party_index))


def mode() -> str:
    return _mode


def label() -> str:
    return _last_label


def _actor_pose(actor: Any) -> tuple[Any, Any] | None:
    if actor is None:
        return None
    try:
        return actor.K2_GetActorLocation(), actor.K2_GetActorRotation()
    except Exception:
        return None


def _selected_pc() -> Any | None:
    if _party_index is None:
        return None
    try:
        from .dev_tools import _pc_for_party_index  # noqa: PLC0415

        pc, _err = _pc_for_party_index(_party_index)
        return pc
    except Exception:
        return None


def _npc_still_live(actor: Any) -> bool:
    if actor is None:
        return False
    try:
        name = str(getattr(actor, "Name", "") or "")
        return bool(name) and not name.startswith("Default__")
    except Exception:
        return False


def _nearest_npc(origin_actor: Any, max_distance: float = 14000.0) -> Any | None:
    global _npc_cache_at, _npc_cache_origin_id, _npc_cache_actor, _npc_cache_max_d

    origin_pose = _actor_pose(origin_actor)
    if origin_pose is None:
        return None
    now = time.monotonic()
    origin_id = id(origin_actor)
    max_d = float(max_distance)
    if (
        _npc_still_live(_npc_cache_actor)
        and now - _npc_cache_at < _NPC_CACHE_TTL_SEC
        and _npc_cache_origin_id == origin_id
        and abs(_npc_cache_max_d - max_d) < 1.0
    ):
        return _npc_cache_actor

    origin = origin_pose[0]
    player_ids: set[int] = set()
    for class_name in ("OakPlayerController", "PlayerController"):
        try:
            for pc in unrealsdk.find_all(class_name, False) or []:
                pawn = getattr(pc, "Pawn", None)
                if pawn is not None:
                    player_ids.add(id(pawn))
        except Exception:
            pass
    best: Any | None = None
    best_dist = max_d ** 2
    seen: set[int] = set()
    # Prefer enemy class first — much smaller than blanket OakCharacter.
    for class_name in ("Char_Enemy", "OakCharacter", "GbxCharacter", "Character"):
        try:
            actors = unrealsdk.find_all(class_name, False) or []
        except Exception:
            continue
        for actor in actors:
            key = id(actor)
            if key in seen or key in player_ids:
                continue
            seen.add(key)
            name = str(getattr(actor, "Name", "") or "")
            cls = str(getattr(getattr(actor, "Class", None), "Name", "") or "").lower()
            if not name or name.startswith("Default__") or "player" in cls:
                continue
            if not any(token in cls for token in ("character", "enemy", "npc", "boss", "badass")):
                continue
            pose = _actor_pose(actor)
            if pose is None:
                continue
            loc = pose[0]
            dist = (
                (float(loc.X) - float(origin.X)) ** 2
                + (float(loc.Y) - float(origin.Y)) ** 2
                + (float(loc.Z) - float(origin.Z)) ** 2
            )
            if dist < best_dist:
                best, best_dist = actor, dist
        # Early exit once Char_Enemy found someone nearby.
        if best is not None and class_name == "Char_Enemy":
            break

    _npc_cache_at = now
    _npc_cache_origin_id = origin_id
    _npc_cache_actor = best
    _npc_cache_max_d = max_d
    return best


def resolve_pose(local_pc: Any) -> tuple[Any, Any] | None:
    """Resolve current spawn target, falling back safely to the local pawn."""
    global _last_label
    local_pawn = getattr(local_pc, "Pawn", None)
    if _mode in ("freecam", "debug_cam", "debugcam"):
        try:
            from .dev_tools import _cached_dcc, get_debug_cam_location, is_debug_cam_active

            if is_debug_cam_active():
                dcc = _cached_dcc()
                pose = _actor_pose(dcc)
                if pose is not None:
                    _last_label = "debug cam"
                    return pose
                loc = get_debug_cam_location().get("location")
                if isinstance(loc, dict) and loc.get("x") is not None:
                    try:
                        vector = unrealsdk.make_struct(
                            "Vector",
                            X=float(loc.get("x") or 0.0),
                            Y=float(loc.get("y") or 0.0),
                            Z=float(loc.get("z") or 0.0),
                        )
                        rot = unrealsdk.make_struct("Rotator", Pitch=0, Yaw=0, Roll=0)
                        _last_label = "debug cam"
                        return vector, rot
                    except Exception:
                        pass
            _last_label = "debug cam inactive; using me"
        except Exception:
            _last_label = "debug cam unavailable; using me"
    elif _mode == "party":
        pc = _selected_pc()
        pawn = getattr(pc, "Pawn", None) if pc is not None else None
        pose = _actor_pose(pawn)
        if pose is not None:
            _last_label = f"selected player: {getattr(pc, 'Name', 'player')}"
            return pose
        _last_label = "selected player unavailable; using me"
    elif _mode == "npc_nearest":
        npc = _nearest_npc(local_pawn)
        pose = _actor_pose(npc)
        if pose is not None:
            _last_label = f"nearest NPC: {getattr(npc, 'Name', 'NPC')}"
            return pose
        _last_label = "no nearby NPC; using me"
    else:
        _last_label = "me"
    return _actor_pose(local_pawn)


def party_index() -> int | None:
    return _party_index


def anchor_pawn(local_pc: Any) -> Any | None:
    """Pawn at the current spawn anchor (party target, NPC, or local)."""
    if _mode == "party":
        pc = _selected_pc()
        return getattr(pc, "Pawn", None) if pc is not None else None
    if _mode == "npc_nearest":
        local_pawn = getattr(local_pc, "Pawn", None) if local_pc is not None else None
        return _nearest_npc(local_pawn)
    if _mode in ("freecam", "debug_cam", "debugcam"):
        try:
            from .dev_tools import _cached_dcc, is_debug_cam_active

            if is_debug_cam_active():
                return _cached_dcc()
        except Exception:
            pass
    return getattr(local_pc, "Pawn", None) if local_pc is not None else None


def apply_from_payload(
    payload: dict[str, Any] | None = None,
    *,
    default_party_index: int | None = None,
) -> str:
    """Apply spawn placement from bridge / desktop action payloads."""
    payload = payload or {}
    anchor = str(payload.get("spawn_anchor") or mode() or "local").strip().lower()
    party_idx: int | None = None
    if anchor == "party":
        if payload.get("player_index") is not None and str(payload.get("player_index")).strip() != "":
            party_idx = int(payload["player_index"])
        elif payload.get("party_index") is not None and str(payload.get("party_index")).strip() != "":
            party_idx = int(payload["party_index"])
        elif default_party_index is not None:
            party_idx = int(default_party_index)
    elif default_party_index is not None and anchor in ("", "local"):
        # Boost target selected in EXE — shape/spawn at them, not host feet.
        try:
            from .mobility_runtime import local_party_index

            local = local_party_index()
            if local is not None and int(default_party_index) != int(local):
                anchor = "party"
                party_idx = int(default_party_index)
        except Exception:
            pass
    set_target(anchor, party_idx)
    return label()
