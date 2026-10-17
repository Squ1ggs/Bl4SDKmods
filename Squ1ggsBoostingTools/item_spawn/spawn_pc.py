"""Resolve a PlayerController that has a pawn for world loot spawns."""

from __future__ import annotations

from typing import Any

import unrealsdk
from mods_base import get_pc


def _is_debug_cam_pc(pc: Any | None) -> bool:
    if pc is None:
        return False
    cls = str(getattr(getattr(pc, "Class", None), "Name", "") or "")
    if "DebugCamera" in cls:
        return True
    name = str(getattr(pc, "Name", "") or "")
    return "DebugCameraController" in name


def resolve_spawn_pc() -> Any | None:
    """Gameplay Oak PC with pawn — not the freecam shell (DCC has no pawn)."""
    pc = get_pc()
    if pc is not None and not _is_debug_cam_pc(pc) and getattr(pc, "Pawn", None) is not None:
        return pc
    try:
        from ..dev_tools import _original_player_controller_for_debugcam

        gp = _original_player_controller_for_debugcam()
        if gp is not None and getattr(gp, "Pawn", None) is not None:
            return gp
    except Exception:
        pass
    if pc is not None and getattr(pc, "Pawn", None) is not None:
        return pc
    for class_name in ("OakPlayerController", "PlayerController"):
        try:
            objects = unrealsdk.find_all(class_name, False) or []
        except Exception:
            continue
        for obj in objects:
            if obj is None or _is_debug_cam_pc(obj):
                continue
            if "Default__" in str(getattr(obj, "Name", "")):
                continue
            if getattr(obj, "Pawn", None) is not None:
                return obj
    return pc
