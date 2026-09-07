"""Pick embedded vs standalone tuning code for Squ1ggs Boosting Tools."""
from __future__ import annotations

import os
from typing import Any

from unrealsdk import logging

SQBT_HOST_FLAG = "SQBT_TUNING_HOST"

_LOG = "[Squ1ggs Boosting Tools | Tuning]"

# short id -> standalone package folder name
_STANDALONE: dict[str, str] = {
    "bpm": "bl4_player_movement",
    "bvm": "bl4_vehicle_movement",
    "bdam": "bl4_damage_and_more",
    "brc": "bl4_resources_and_cooldowns",
}

_EMBEDDED_PKG: dict[str, str] = {
    "bpm": "embedded_bpm",
    "bvm": "embedded_bvm",
    "bdam": "embedded_bdam",
    "brc": "embedded_brc",
}

_pick: dict[str, tuple[str, Any]] = {}


def _log(msg: str) -> None:
    try:
        logging.info(f"{_LOG} {msg}")
    except Exception:
        pass


def _mod_enabled(stem: str) -> bool:
    try:
        from mods_base.mod_list import get_ordered_mod_list
    except Exception:
        return False

    for mod in get_ordered_mod_list():
        if not getattr(mod, "is_enabled", False):
            continue
        path = str(getattr(mod, "settings_file", "") or "").replace("\\", "/")
        if path.endswith(f"{stem}.json"):
            return True
    return False


def _load_standalone(stem: str) -> Any | None:
    try:
        mod = __import__(stem)
    except ImportError:
        return None
    if getattr(mod, "EMBEDDED_IN_SQBT", False):
        return None
    return mod


def _load_embedded(short: str) -> Any:
    from importlib import import_module

    return import_module(f".{_EMBEDDED_PKG[short]}", __package__).get_engine()


def _drop_blimgui_tab(mod: Any) -> None:
    tab = getattr(mod, "_BLIMGUI_TAB", None)
    if not tab:
        return
    try:
        import blimgui

        blimgui.remove_tab(str(tab))
    except Exception:
        pass


def resolve(short: str) -> tuple[str, Any]:
    """Always the bundled copy. Squ1ggs Boosting Tools is all-in-one."""
    if short in _pick:
        return _pick[short]
    _pick[short] = ("embedded", _load_embedded(short))
    return _pick[short]


def backend_kind(short: str) -> str:
    return resolve(short)[0]


def get_engine(short: str) -> Any:
    return resolve(short)[1]


def draw_tab(short: str) -> None:
    get_engine(short)._draw_blimgui_tab()


def active_standalone_backends() -> list[str]:
    return [stem for short, stem in _STANDALONE.items() if backend_kind(short) == "standalone"]


def enable_all() -> None:
    os.environ[SQBT_HOST_FLAG] = "1"
    _pick.clear()

    for short, stem in _STANDALONE.items():
        kind, backend = resolve(short)
        try:
            backend._on_enable()
        except Exception as exc:
            _log(f"embedded {short} on_enable failed: {exc!r}")
        if kind != "embedded":
            _log(f"{stem}: unexpected backend {kind!r}; Squ1ggs uses the bundled copy.")


def disable_all() -> None:
    for short in _STANDALONE:
        try:
            get_engine(short)._on_disable()
        except Exception:
            pass
    _pick.clear()
    os.environ.pop(SQBT_HOST_FLAG, None)


def standalone_conflicts() -> list[str]:
    return active_standalone_backends()


def apply_module(short: str) -> str:
    eng = get_engine(short)
    if short == "bpm":
        ok = bool(eng._apply_saved_tuning(log=True))
        return "Player movement applied." if ok else "Nothing to apply (check scope / pawn)."
    if short == "bvm":
        ok = bool(eng._apply_saved_tuning(log=True))
        return "Vehicle movement applied." if ok else "Nothing to apply — get in a vehicle first."
    if short == "bdam":
        ok, fail = eng._apply_damage_tuning(log_hits=True)
        return f"Damage tuning applied ({ok} ok, {fail} miss)."
    if short == "brc":
        ok, fail = eng._apply_damage_tuning(log_hits=True)
        return f"Kits & shields tuning applied ({ok} ok, {fail} miss)."
    raise ValueError(f"unknown tuning id: {short}")


def reset_module(short: str) -> str:
    eng = get_engine(short)
    if short in ("bpm", "bvm"):
        eng._reset_all()
    else:
        eng._on_reset_btn(None)
    return "Reset to defaults."


def preset_module(short: str, preset: str) -> str:
    eng = get_engine(short)
    if short not in ("bpm", "bvm"):
        raise ValueError(f"no presets for {short}")
    eng._apply_preset(preset)
    return f"Preset {preset!r} applied."


def status_module(short: str) -> dict[str, Any]:
    eng = get_engine(short)
    out: dict[str, Any] = {"module": short, "backend": backend_kind(short)}
    if short == "bpm":
        out["scope"] = getattr(eng, "BPM_APPLY_SCOPE", "")
    elif short == "bvm":
        out["scope"] = getattr(eng, "BVM_APPLY_SCOPE", "")
        try:
            out["vehicle_hits"] = len(list(eng._iter_bvm_vehicle_hits()))
        except Exception:
            out["vehicle_hits"] = 0
    elif short == "bdam":
        out["master"] = bool(getattr(eng, "BDAM_MASTER_ENABLED", False))
        out["sticky"] = bool(getattr(eng, "BDAM_STICKY_ENABLED", False))
    elif short == "brc":
        out["master"] = bool(getattr(eng, "BRC_MASTER_ENABLED", False))
        out["sticky"] = bool(getattr(eng, "BRC_STICKY_ENABLED", False))
    return out
