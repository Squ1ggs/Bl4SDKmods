"""Photo presets — one click for HUD / FPS counter / freecam / FOV, one click back.

Everything is local view only. Whatever a preset changed is remembered and restored
by ``clear()`` (or by switching to another preset).
"""

from __future__ import annotations

from typing import Any

from unrealsdk import logging

from . import fps_display, hud_visibility

_PREFIX = "[Squ1ggs's Boosting Tools | Photo]"

PRESETS: dict[str, dict[str, Any]] = {
    "clean": {"label": "Clean screen", "freecam": False, "fov": None},
    "freecam": {"label": "Freecam photo", "freecam": True, "fov": None},
    "wide": {"label": "Wide photo", "freecam": False, "fov": 110.0},
}

_active: str | None = None
_restore: dict[str, Any] = {}


def _local_player() -> Any | None:
    try:
        from mods_base import get_pc

        pc = get_pc()
    except Exception:
        return None
    if pc is None:
        return None
    lp = getattr(pc, "Player", None)
    if lp is None:
        orig = getattr(pc, "OriginalControllerRef", None)
        lp = getattr(orig, "Player", None) if orig is not None else None
    return lp


def read_fov() -> float | None:
    lp = _local_player()
    for src in (lp, fps_display._settings()):
        if src is None:
            continue
        try:
            return float(src.BaseFOV)
        except Exception:
            continue
    return None


def _write_fov(value: float) -> bool:
    lp = _local_player()
    if lp is None:
        return False
    setter = getattr(lp, "SetBaseFOV", None)
    if callable(setter):
        try:
            setter(float(value))
        except Exception:
            pass
    try:
        if abs(float(lp.BaseFOV) - float(value)) > 0.01:
            lp.BaseFOV = float(value)
        return abs(float(lp.BaseFOV) - float(value)) <= 0.01
    except Exception:
        return False


def _freecam_api() -> tuple[Any, Any, Any] | None:
    try:
        from .dev_tools import enable_debug_cam, force_disable_debug_cam, is_debug_cam_active

        return enable_debug_cam, force_disable_debug_cam, is_debug_cam_active
    except Exception:
        return None


def active_preset() -> str | None:
    return _active


def clear() -> tuple[bool, str]:
    global _active
    if _active is None:
        return True, "No photo preset active."
    notes: list[str] = []
    if _restore.get("freecam_was_off"):
        api = _freecam_api()
        if api is not None:
            try:
                api[1]()
            except Exception as exc:
                notes.append(f"freecam off failed: {exc}")
    if _restore.get("fov") is not None:
        if not _write_fov(float(_restore["fov"])):
            notes.append("FOV not restored")
    if "fps_shown" in _restore:
        fps_display.set_shown(bool(_restore["fps_shown"]))
    if "hud_hidden" in _restore:
        hud_visibility.set_hidden(bool(_restore["hud_hidden"]))
    label = PRESETS.get(_active, {}).get("label", _active)
    _active = None
    _restore.clear()
    msg = f"{label} off — view restored." + (f" ({'; '.join(notes)})" if notes else "")
    logging.info(f"{_PREFIX} {msg}")
    return True, msg


def apply_preset(key: str, *, fov: float | None = None) -> tuple[bool, str]:
    global _active
    preset = PRESETS.get(str(key or "").strip().lower())
    if preset is None:
        return False, f"Unknown photo preset {key!r}."
    if _active is not None:
        clear()
    _restore.clear()
    _restore["hud_hidden"] = hud_visibility.is_hidden()
    _restore["fps_shown"] = fps_display.is_shown()
    hud_visibility.set_hidden(True)
    if _restore["fps_shown"]:
        fps_display.set_shown(False)
    notes: list[str] = []
    want_fov = fov if fov is not None else preset.get("fov")
    if want_fov:
        _restore["fov"] = read_fov()
        if not _write_fov(float(want_fov)):
            notes.append("FOV not applied")
    if preset.get("freecam"):
        api = _freecam_api()
        if api is None:
            notes.append("freecam unavailable")
        else:
            enable, _disable, is_active = api
            try:
                if not is_active():
                    _restore["freecam_was_off"] = True
                    enable()
            except Exception as exc:
                notes.append(f"freecam failed: {exc}")
    _active = str(key).strip().lower()
    msg = f"{preset['label']} on." + (f" ({'; '.join(notes)})" if notes else "")
    logging.info(f"{_PREFIX} {msg}")
    return True, msg
