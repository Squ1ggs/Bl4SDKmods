"""Standalone spawn-anchor discovery for BMS."""

from __future__ import annotations

import time
from typing import Any

import unrealsdk

_NPC_CACHE_TTL_SEC = 1.35
_npc_cache_at = 0.0
_npc_cache_origin_id = 0
_npc_cache_actor: Any | None = None
_npc_cache_max_d = 0.0


def actor_location(actor: Any) -> Any | None:
    if actor is None:
        return None
    for name in ("K2_GetActorLocation", "GetActorLocation"):
        fn = getattr(actor, name, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    return None


def _distance_sq(a: Any, b: Any) -> float:
    return (
        (float(a.X) - float(b.X)) ** 2
        + (float(a.Y) - float(b.Y)) ** 2
        + (float(a.Z) - float(b.Z)) ** 2
    )


def _party_pawn_ids() -> set[int]:
    out: set[int] = set()
    for class_name in ("OakPlayerController", "PlayerController"):
        try:
            controllers = unrealsdk.find_all(class_name, False) or []
        except Exception:
            continue
        for pc in controllers:
            pawn = getattr(pc, "Pawn", None)
            if pawn is not None:
                out.add(id(pawn))
    return out


def _looks_live_npc(actor: Any, player_ids: set[int]) -> bool:
    if actor is None or id(actor) in player_ids:
        return False
    name = str(getattr(actor, "Name", "") or "")
    if not name or name.startswith("Default__"):
        return False
    cls = str(getattr(getattr(actor, "Class", None), "Name", "") or "").lower()
    if "player" in cls:
        return False
    return any(token in cls for token in ("character", "enemy", "npc", "boss", "badass"))


def _npc_still_live(actor: Any) -> bool:
    if actor is None:
        return False
    try:
        name = str(getattr(actor, "Name", "") or "")
        return bool(name) and not name.startswith("Default__")
    except Exception:
        return False


def nearest_npc(origin_actor: Any, *, max_distance: float = 14000.0) -> Any | None:
    """Find the closest non-player character to ``origin_actor`` (cached ~1.3s)."""
    global _npc_cache_at, _npc_cache_origin_id, _npc_cache_actor, _npc_cache_max_d

    origin = actor_location(origin_actor)
    if origin is None:
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

    player_ids = _party_pawn_ids()
    best: Any | None = None
    best_dist = max(100.0, max_d) ** 2
    seen: set[int] = set()
    for class_name in ("Char_Enemy", "OakCharacter", "GbxCharacter", "Character"):
        try:
            actors = unrealsdk.find_all(class_name, False) or []
        except Exception:
            continue
        for actor in actors:
            key = id(actor)
            if key in seen:
                continue
            seen.add(key)
            if not _looks_live_npc(actor, player_ids):
                continue
            loc = actor_location(actor)
            if loc is None:
                continue
            dist = _distance_sq(origin, loc)
            if dist < best_dist:
                best = actor
                best_dist = dist
        if best is not None and class_name == "Char_Enemy":
            break

    _npc_cache_at = now
    _npc_cache_origin_id = origin_id
    _npc_cache_actor = best
    _npc_cache_max_d = max_d
    return best


def npc_label(actor: Any) -> str:
    name = str(getattr(actor, "Name", "") or "NPC")
    cls = str(getattr(getattr(actor, "Class", None), "Name", "") or "")
    return f"{name} ({cls})" if cls else name
