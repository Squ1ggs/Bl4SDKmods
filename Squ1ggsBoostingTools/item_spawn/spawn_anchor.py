"""Spawn location anchor — local player, party member, or nearby / aimed NPC."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import unrealsdk
from mods_base import get_pc

SpawnAnchorMode = Literal["local", "party", "npc_nearest", "npc_aim"]

_PLAYER_CLASS_HINTS: tuple[str, ...] = (
    "oakplayer",
    "gbxplayer",
    "playable",
    "playercharacter",
)
_NPC_CLASS_HINTS: tuple[str, ...] = (
    "enemy",
    "char_enemy",
    "oakcharacter",
    "gbxcharacter",
    "ai_",
    "badass",
    "boss",
    "npc",
)


@dataclass(slots=True)
class SpawnAnchorConfig:
    mode: SpawnAnchorMode = "local"
    party_index: int = 0
    npc_max_distance: float = 14000.0
    npc_search_limit: int = 160
    last_label: str = "local player"


def _safe_name(obj: Any) -> str:
    if obj is None:
        return "<none>"
    for attr in ("PlayerName", "Name"):
        try:
            val = getattr(obj, attr, None)
            if val:
                return str(val)
        except Exception:  # noqa: BLE001
            continue
    return str(obj)


def _class_name(obj: Any) -> str:
    try:
        cls = getattr(obj, "Class", None)
        return str(getattr(cls, "Name", "") or "")
    except Exception:  # noqa: BLE001
        return ""


def _is_class_default(obj: Any) -> bool:
    try:
        nm = _safe_name(obj)
        return nm.startswith("Default__")
    except Exception:  # noqa: BLE001
        return False


def _is_local_pc(pc: Any) -> bool:
    local = get_pc()
    if local is not None and pc is local:
        return True
    for attr in ("IsLocalPlayerController", "bIsLocalPlayerController", "IsLocalController"):
        try:
            val = getattr(pc, attr, None)
            if isinstance(val, bool):
                return val
        except Exception:  # noqa: BLE001
            continue
    return False


def list_party_controllers() -> list[Any]:
    """Local/host PC first, then guests (stable for UI + spawn targeting)."""
    found: list[Any] = []
    seen: set[int] = set()
    for class_name in ("OakPlayerController", "PlayerController"):
        try:
            objects = unrealsdk.find_all(class_name, False) or []
        except Exception:  # noqa: BLE001
            continue
        for obj in objects:
            if obj is None or _is_class_default(obj):
                continue
            oid = id(obj)
            if oid in seen:
                continue
            seen.add(oid)
            found.append(obj)
    local: list[Any] = []
    other: list[Any] = []
    for pc in found:
        if _is_local_pc(pc):
            local.append(pc)
        else:
            other.append(pc)
    if not local and found:
        local = [found[0]]
        other = found[1:]
    return local + other


def _actor_location(actor: Any) -> Any | None:
    if actor is None:
        return None
    for meth in ("K2_GetActorLocation", "GetActorLocation"):
        fn = getattr(actor, meth, None)
        if callable(fn):
            try:
                return fn()
            except Exception:  # noqa: BLE001
                continue
    root = getattr(actor, "RootComponent", None)
    if root is not None:
        for meth in ("K2_GetComponentLocation", "GetComponentLocation"):
            fn = getattr(root, meth, None)
            if callable(fn):
                try:
                    return fn()
                except Exception:  # noqa: BLE001
                    continue
    return None


def _actor_rotation(actor: Any) -> Any | None:
    if actor is None:
        return None
    for meth in ("K2_GetActorRotation", "GetActorRotation"):
        fn = getattr(actor, meth, None)
        if callable(fn):
            try:
                return fn()
            except Exception:  # noqa: BLE001
                continue
    return None


def _dist_sq(a: Any, b: Any) -> float:
    dx = float(a.X) - float(b.X)
    dy = float(a.Y) - float(b.Y)
    dz = float(a.Z) - float(b.Z)
    return dx * dx + dy * dy + dz * dz


def _party_pawn_ids() -> set[int]:
    ids: set[int] = set()
    for pc in list_party_controllers():
        pawn = getattr(pc, "Pawn", None)
        if pawn is not None:
            ids.add(id(pawn))
    return ids


def _looks_like_player_actor(actor: Any, party_pawn_ids: set[int]) -> bool:
    if actor is None:
        return True
    if id(actor) in party_pawn_ids:
        return True
    cname = _class_name(actor).lower()
    if any(h in cname for h in _PLAYER_CLASS_HINTS):
        return True
    owner = getattr(actor, "Owner", None)
    if owner is not None and _class_name(owner).lower().find("playercontroller") >= 0:
        return True
    return False


def _looks_like_npc(actor: Any) -> bool:
    cname = _class_name(actor).lower()
    if not cname or "default__" in cname:
        return False
    if any(h in cname for h in _PLAYER_CLASS_HINTS):
        return False
    return any(h in cname for h in _NPC_CLASS_HINTS)


def find_nearest_npc(origin: Any, *, max_distance: float, search_limit: int) -> Any | None:
    if origin is None:
        return None
    max_dist_sq = max(100.0, float(max_distance)) ** 2
    party_ids = _party_pawn_ids()
    best: Any | None = None
    best_d = max_dist_sq + 1.0
    checked = 0
    for hint in ("Char_Enemy", "OakCharacter", "GbxCharacter", "Character"):
        try:
            objects = unrealsdk.find_all(hint, False) or []
        except Exception:  # noqa: BLE001
            continue
        for obj in objects:
            if checked >= search_limit:
                break
            if obj is None or _is_class_default(obj):
                continue
            if _looks_like_player_actor(obj, party_ids):
                continue
            if not _looks_like_npc(obj):
                continue
            loc = _actor_location(obj)
            if loc is None:
                continue
            d = _dist_sq(origin, loc)
            checked += 1
            if d <= max_dist_sq and d < best_d:
                best_d = d
                best = obj
    return best


def get_aimed_actor(pc: Any) -> Any | None:
    if pc is None:
        return None
    for fn_name in (
        "GetHitResultUnderCursor",
        "GetHitResultUnderCursorByChannel",
        "GetHitResultUnderFinger",
    ):
        fn = getattr(pc, fn_name, None)
        if not callable(fn):
            continue
        try:
            hit = fn()
        except Exception:  # noqa: BLE001
            continue
        if hit is None:
            continue
        for attr in ("Actor", "HitActor", "Component"):
            try:
                val = getattr(hit, attr, None)
            except Exception:  # noqa: BLE001
                val = None
            if val is None:
                continue
            actor = getattr(val, "Owner", None) if attr == "Component" else val
            if actor is not None:
                return actor
        try:
            loc = getattr(hit, "ImpactPoint", None) or getattr(hit, "Location", None)
            if loc is not None:
                return loc
        except Exception:  # noqa: BLE001
            pass
    return None


def resolve_spawn_controller(cfg: SpawnAnchorConfig) -> Any | None:
    local = get_pc()
    if cfg.mode == "party":
        pcs = list_party_controllers()
        if not pcs:
            return local
        idx = max(0, min(int(cfg.party_index), len(pcs) - 1))
        return pcs[idx]
    return local or (list_party_controllers()[0] if list_party_controllers() else None)


def resolve_anchor_pose(
    cfg: SpawnAnchorConfig,
    *,
    local_pc: Any | None = None,
) -> tuple[Any, Any, str] | None:
    """Return (location, rotation, label) for spawn offsets."""
    pc = local_pc or get_pc() or resolve_spawn_controller(cfg)
    if pc is None:
        cfg.last_label = "<no pc>"
        return None

    if cfg.mode == "party":
        target_pc = resolve_spawn_controller(cfg)
        pawn = getattr(target_pc, "Pawn", None) if target_pc is not None else None
        if pawn is None:
            cfg.last_label = f"party pc{cfg.party_index + 1} (no pawn)"
            return None
        loc = _actor_location(pawn)
        rot = _actor_rotation(pawn)
        if loc is None or rot is None:
            cfg.last_label = f"party pc{cfg.party_index + 1} (no pose)"
            return None
        cfg.last_label = f"party: {_safe_name(target_pc)}"
        return loc, rot, cfg.last_label

    if cfg.mode in ("npc_nearest", "npc_aim"):
        origin_pawn = getattr(pc, "Pawn", None)
        origin = _actor_location(origin_pawn) if origin_pawn is not None else None
        actor: Any | None = None
        if cfg.mode == "npc_aim":
            actor = get_aimed_actor(pc)
            if actor is not None and not _looks_like_npc(actor) and not hasattr(actor, "X"):
                # aimed at player prop — still use its location
                pass
        if actor is None and cfg.mode == "npc_nearest":
            actor = find_nearest_npc(
                origin,
                max_distance=cfg.npc_max_distance,
                search_limit=cfg.npc_search_limit,
            )
        if actor is None:
            cfg.last_label = "npc (none found — using local pawn)"
            pawn = getattr(pc, "Pawn", None)
            if pawn is None:
                return None
            loc = _actor_location(pawn)
            rot = _actor_rotation(pawn)
            if loc is None or rot is None:
                return None
            return loc, rot, cfg.last_label
        # ImpactPoint-style struct (no rotation)
        if hasattr(actor, "X") and hasattr(actor, "Y"):
            yaw = 0.0
            if origin is not None:
                dx = float(actor.X) - float(origin.X)
                dy = float(actor.Y) - float(origin.Y)
                if abs(dx) + abs(dy) > 1.0:
                    yaw = math.degrees(math.atan2(dy, dx))
            rot = unrealsdk.make_struct("Rotator", Pitch=0.0, Yaw=yaw, Roll=0.0)
            cfg.last_label = "npc: aim point"
            return actor, rot, cfg.last_label
        loc = _actor_location(actor)
        rot = _actor_rotation(actor)
        if loc is None:
            cfg.last_label = "npc (no location)"
            return None
        if rot is None:
            rot = unrealsdk.make_struct("Rotator", Pitch=0.0, Yaw=0.0, Roll=0.0)
        cfg.last_label = f"npc: {_safe_name(actor)} ({_class_name(actor)})"
        return loc, rot, cfg.last_label

    pawn = getattr(pc, "Pawn", None)
    if pawn is None:
        cfg.last_label = "local (no pawn)"
        return None
    loc = _actor_location(pawn)
    rot = _actor_rotation(pawn)
    if loc is None or rot is None:
        cfg.last_label = "local (no pose)"
        return None
    cfg.last_label = f"local: {_safe_name(pc)}"
    return loc, rot, cfg.last_label
