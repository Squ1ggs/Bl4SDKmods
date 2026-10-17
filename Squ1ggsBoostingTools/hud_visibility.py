"""Local HUD show/hide (OakHUD.ShowHUD exec — same as typing ShowHUD in console).

Local view only: guests / the game state are untouched. A new map spawns a fresh HUD,
so the HUD comes back after travel.
"""

from __future__ import annotations

from typing import Any

from unrealsdk import logging

_PREFIX = "[Squ1ggs Boosting Tools | HUD]"


def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")


def _local_pc() -> Any | None:
    try:
        from mods_base import get_pc

        return get_pc()
    except Exception:
        return None


def _local_hud() -> Any | None:
    pc = _local_pc()
    if pc is None:
        return None
    hud = getattr(pc, "MyHUD", None)
    if hud is None:
        # Freecam: get_pc() can be the DebugCameraController — HUD lives on the gameplay PC.
        orig = getattr(pc, "OriginalControllerRef", None)
        if orig is not None:
            hud = getattr(orig, "MyHUD", None)
    return hud


def is_hidden() -> bool:
    hud = _local_hud()
    if hud is None:
        return False
    try:
        return not bool(getattr(hud, "bShowHUD", True))
    except Exception:
        return False


def set_hidden(hidden: bool) -> str:
    hud = _local_hud()
    if hud is None:
        return "No HUD yet — load into a map first."
    want_show = not bool(hidden)
    try:
        current = bool(getattr(hud, "bShowHUD", True))
    except Exception:
        current = True
    if current != want_show:
        try:
            hud.ShowHUD()
        except Exception as exc:
            _log(f"ShowHUD call failed ({exc}); writing bShowHUD directly")
        try:
            if bool(getattr(hud, "bShowHUD", True)) != want_show:
                hud.bShowHUD = want_show
        except Exception as exc:
            return f"HUD toggle failed: {exc}"
    msg = "HUD hidden (comes back on map change)." if hidden else "HUD shown."
    _log(msg)
    return msg
