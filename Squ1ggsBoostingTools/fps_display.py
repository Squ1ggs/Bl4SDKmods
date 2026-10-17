"""Game FPS counter through the engine's user settings (``ShowFPSMode``)."""

from __future__ import annotations

import enum
from typing import Any

import unrealsdk
from unrealsdk import logging

_PREFIX = "[Squ1ggs's Boosting Tools | FPS]"
_last_on_mode = 1


def _settings() -> Any | None:
    try:
        gus = getattr(unrealsdk.get_engine(), "GameUserSettings", None)
    except Exception:
        gus = None
    if gus is not None:
        return gus
    try:
        cdo = unrealsdk.find_class("GameUserSettings").ClassDefaultObject
        return cdo.GetGameUserSettings()
    except Exception:
        return None


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return int(getattr(value, "value", 0) or 0)


def _read_mode(gus: Any) -> Any:
    try:
        return gus.ShowFPSMode
    except Exception:
        pass
    getter = getattr(gus, "GetShowFPSMode", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            pass
    return None


def _write_mode(gus: Any, mode: int) -> bool:
    cur = _read_mode(gus)
    value: Any = int(mode)
    if isinstance(cur, enum.Enum):
        try:
            value = type(cur)(int(mode))
        except Exception:
            value = int(mode)
    setter = getattr(gus, "SetShowFPSMode", None)
    if callable(setter):
        try:
            setter(value)
        except Exception:
            pass
    if _as_int(_read_mode(gus)) != int(mode):
        try:
            gus.ShowFPSMode = value
        except Exception:
            return False
    apply = getattr(gus, "ApplyNonResolutionSettings", None)
    if callable(apply):
        try:
            apply()
        except Exception:
            pass
    return _as_int(_read_mode(gus)) == int(mode)


def is_shown() -> bool:
    gus = _settings()
    if gus is None:
        return False
    try:
        return _as_int(_read_mode(gus)) != 0
    except Exception:
        return False


def set_shown(shown: bool) -> tuple[bool, str]:
    global _last_on_mode
    gus = _settings()
    if gus is None:
        return False, "Game settings not ready yet — load into a map first."
    cur = _as_int(_read_mode(gus))
    if bool(shown) == (cur != 0):
        return True, "FPS counter shown." if shown else "FPS counter hidden."
    if cur != 0:
        _last_on_mode = cur
    want = _last_on_mode if shown else 0
    if not _write_mode(gus, want):
        return False, "Could not change the FPS counter setting."
    logging.info(f"{_PREFIX} ShowFPSMode={want}")
    return True, "FPS counter shown." if shown else "FPS counter hidden."
