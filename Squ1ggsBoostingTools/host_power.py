"""Low power host mode — caps the local frame rate like the game's Frame Rate Limit option.

``GameUserSettings.FrameRateLimit`` is written so the cap survives a restart, and the engine
``t.MaxFPS`` cvar applies it live. The engine frame-rate smoothing cap (``bSmoothFrameRate``)
dragged a 30 cap down under 15 FPS in testing — do not use it.
On a host the whole lobby simulation runs at this rate, so the cap never goes below MIN_CAP.
Previous values are remembered and put back when the mode is turned off.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from unrealsdk import logging

from .fps_display import _settings

_PREFIX = "[Squ1ggs's Boosting Tools | LowPower]"
DEFAULT_CAP = 30
MIN_CAP = 20
MAX_CAP = 120
# The game saves FrameRateLimit to its own config, so the original must survive a restart too.
_RESTORE_FILE = Path(__file__).resolve().parent.parent / "settings" / "sqbt_host_power_restore.json"
_saved: dict[str, Any] | None = None
_cap = DEFAULT_CAP


def _load_restore() -> dict[str, Any] | None:
    try:
        data = json.loads(_RESTORE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or "limit" not in data:
        return None
    return {"limit": float(data.get("limit") or 0.0), "limit_on": data.get("limit_on")}


def _store_restore(saved: dict[str, Any] | None) -> None:
    try:
        if saved is None:
            _RESTORE_FILE.unlink(missing_ok=True)
            return
        _RESTORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _RESTORE_FILE.write_text(json.dumps(saved), encoding="utf-8")
    except Exception:
        pass


def _apply(gus: Any) -> None:
    fn = getattr(gus, "ApplyNonResolutionSettings", None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


def _read_limit(gus: Any) -> float:
    try:
        return float(gus.FrameRateLimit)
    except Exception:
        pass
    try:
        return float(gus.GetFrameRateLimit())
    except Exception:
        return 0.0


def _read_limit_on(gus: Any) -> bool | None:
    try:
        return bool(gus.LimitFrameRate)
    except Exception:
        return None


def _write(gus: Any, limit: float, limit_on: bool | None) -> None:
    if limit_on is not None:
        try:
            gus.LimitFrameRate = bool(limit_on)
        except Exception:
            pass
    setter = getattr(gus, "SetFrameRateLimit", None)
    if callable(setter):
        try:
            setter(float(limit))
        except Exception:
            pass
    if abs(_read_limit(gus) - float(limit)) > 0.01:
        try:
            gus.FrameRateLimit = float(limit)
        except Exception:
            pass
    _apply(gus)


def _set_engine_cap(limit: float) -> None:
    """The Options menu caps live without any settings UFunction — the engine cvar is what applies it."""
    try:
        from mods_base import get_pc

        from .travel import _try_kismet_execute

        _try_kismet_execute(f"t.MaxFPS {max(0, int(round(limit)))}", None, get_pc())
    except Exception:
        pass


def _clear_engine_smoothing() -> None:
    try:
        import unrealsdk

        eng = unrealsdk.get_engine()
        if bool(getattr(eng, "bSmoothFrameRate", False)):
            eng.bSmoothFrameRate = False
    except Exception:
        pass


def is_enabled() -> bool:
    global _saved
    if _saved is None:
        _saved = _load_restore()
    return _saved is not None


def status() -> dict[str, Any]:
    gus = _settings()
    out: dict[str, Any] = {"ready": gus is not None, "enabled": is_enabled(), "cap": _cap}
    if gus is not None:
        out["limit"] = _read_limit(gus)
        out["limit_on"] = _read_limit_on(gus)
    if _saved:
        out["saved"] = dict(_saved)
    return out


def set_enabled(enabled: bool, cap: int | None = None) -> tuple[bool, str]:
    global _saved, _cap
    gus = _settings()
    if gus is None:
        return False, "Game settings not ready yet — load into a map first."
    _clear_engine_smoothing()
    if cap is not None:
        _cap = max(MIN_CAP, min(MAX_CAP, int(cap)))
    if _saved is None:
        _saved = _load_restore()
    if enabled:
        if _saved is None:
            _saved = {"limit": _read_limit(gus), "limit_on": _read_limit_on(gus)}
            _store_restore(_saved)
        _write(gus, float(_cap), True)
        _set_engine_cap(float(_cap))
        msg = f"Low power host mode ON — frame limit set to {_cap} FPS."
    else:
        if _saved is None:
            return True, "Low power host mode already off."
        limit = float(_saved.get("limit") or 0.0)
        _write(gus, limit, _saved.get("limit_on"))
        _set_engine_cap(limit if _saved.get("limit_on") is not False else 0.0)
        _saved = None
        _store_restore(None)
        msg = "Low power host mode OFF — your frame rate limit is back."
    logging.info(f"{_PREFIX} {msg}")
    return True, msg
