"""Spawn All pile / pearl ring offsets — bulk pile or random spit-from-player."""

from __future__ import annotations

import math
import random

_RING_INDEX = 0
_ACTIVE_SLOT = 0
_PILE_SLOT = 0
_BULK_PILE_MODE = False

# Straight in front of the pawn/camera — never left/right/behind.
# Close enough to read as "at my feet" for verify, far enough to avoid pawn clip.
_FRONT_FORWARD_UU = 180.0
_FRONT_UP_UU = 40.0


def bulk_pile_mode() -> bool:
    return bool(_BULK_PILE_MODE)


def set_bulk_pile_mode(enabled: bool) -> None:
    """Spawn All: drop everything in a tight pile at your feet (no ring spread)."""
    global _BULK_PILE_MODE, _RING_INDEX, _PILE_SLOT, _ACTIVE_SLOT
    _BULK_PILE_MODE = bool(enabled)
    _RING_INDEX = 0
    _PILE_SLOT = 0
    _ACTIVE_SLOT = 0


def reset_ring_index() -> None:
    global _RING_INDEX, _PILE_SLOT, _ACTIVE_SLOT
    _RING_INDEX = 0
    _PILE_SLOT = 0
    _ACTIVE_SLOT = 0


def reset_pile_slot() -> None:
    """New pile anchor after a breather pause (same spot, fresh stack offset)."""
    global _PILE_SLOT, _ACTIVE_SLOT
    _PILE_SLOT = 0
    _ACTIVE_SLOT = 0


def ring_index() -> int:
    if _BULK_PILE_MODE:
        return int(_ACTIVE_SLOT)
    return int(_RING_INDEX)


def bump_ring_index() -> int:
    global _RING_INDEX, _PILE_SLOT, _ACTIVE_SLOT
    if _BULK_PILE_MODE:
        _ACTIVE_SLOT = int(_PILE_SLOT)
        _PILE_SLOT = (int(_PILE_SLOT) + 1) % 8
        return int(_ACTIVE_SLOT)
    _RING_INDEX += 1
    _ACTIVE_SLOT = int(_RING_INDEX)
    return int(_RING_INDEX)


def pile_pose_offset(slot: int) -> tuple[float, float, float]:
    """Straight ahead only — side=0 so nothing lands left/behind from jitter."""
    s = max(0, int(slot)) % 12
    # Stack upward only so copies don't z-fight; never lateral.
    return _FRONT_FORWARD_UU, 0.0, _FRONT_UP_UU + (s * 14.0)


def front_only_pose_offset(slot: int = 0) -> tuple[float, float, float]:
    """Singular / Spawn selected: one point dead ahead of the player."""
    return pile_pose_offset(slot)


def ring_pose_offset(ring_slot: int) -> tuple[float, float, float]:
    """
    Forward / right / up offsets (uu) for one batch slot.
    Bulk pile mode: straight ahead stack. Otherwise items spit in a *narrow*
    front fan only — never behind (cos of 180° was negative), and side is
    capped so loot does not shoot over the left shoulder.
    """
    if _BULK_PILE_MODE:
        return pile_pose_offset(ring_slot)
    slot = max(0, int(ring_slot))
    # Keep spread mild and always forward (cos stays positive).
    angle_deg = ((slot * 17.0) % 40.0) - 20.0
    ring = slot % 12
    radius = 140.0 + (ring // 4) * 18.0
    rad = math.radians(angle_deg)
    forward = max(_FRONT_FORWARD_UU, math.cos(rad) * radius)
    side = math.sin(rad) * radius * 0.25
    up = _FRONT_UP_UU + (slot % 3) * 10.0
    return forward, side, up
