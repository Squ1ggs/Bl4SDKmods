"""Desktop-bridge field helpers for embedded / standalone tuning modules."""
from __future__ import annotations

from typing import Any

from . import tuning_embed as _tuning

_MODULE_SHORT = frozenset({"bpm", "bvm", "bdam", "brc"})


def _option_key(opt: Any) -> str:
    for attr in ("path", "identifier", "name", "id"):
        val = getattr(opt, attr, None)
        if val:
            return str(val)
    return ""


def _option_is_bool(opt: Any) -> bool:
    if type(opt).__name__ == "BoolOption":
        return True
    return isinstance(getattr(opt, "value", None), bool)


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value) and float(value) != 0.0
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _slider_groups(short: str, eng: Any) -> list[list[Any]]:
    if short == "bpm":
        return [
            list(getattr(eng, "_slider_core", []) or []),
            list(getattr(eng, "_slider_glide", []) or []),
        ]
    if short == "bvm":
        jump_extra = [
            opt
            for opt in (
                getattr(eng, "_jump_repeat_interval_opt", None),
                getattr(eng, "_repeat_jump_press_opt", None),
            )
            if opt is not None
        ]
        boost = getattr(eng, "_unlimited_boost_opt", None)
        groups = [
            ([boost] if boost is not None else []) + list(getattr(eng, "_slider_core", []) or []),
            list(getattr(eng, "_slider_jump", []) or []) + jump_extra,
            list(getattr(eng, "_slider_extra", []) or []),
            list(getattr(eng, "_slider_durability", []) or []),
        ]
        vault = getattr(eng, "_vault_cost_slider", None)
        if vault is not None:
            groups.append([vault])
        return groups
    if short == "bdam":
        return [
            list(getattr(eng, "_slider_dcd", []) or []),
            list(getattr(eng, "_slider_ds", []) or [])[:4],
        ]
    if short == "brc":
        return [
            list(getattr(eng, "_slider_repair", []) or []),
            list(getattr(eng, "_slider_recovery", []) or []),
            list(getattr(eng, "_slider_adv", []) or []),
            list(getattr(eng, "_slider_ammo", []) or []),
        ]
    return []


def manifest_fields(short: str) -> list[dict[str, Any]]:
    short = str(short or "").strip().lower()
    if short not in _MODULE_SHORT:
        return []
    try:
        eng = _tuning.get_engine(short)
    except Exception:
        return []
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in _slider_groups(short, eng):
        for opt in group:
            key = _option_key(opt)
            if not key or key in seen:
                continue
            seen.add(key)
            label = str(getattr(opt, "display_name", None) or key)
            if _option_is_bool(opt):
                fields.append(
                    {
                        "key": key,
                        "label": label,
                        "type": "checkbox",
                        "default": bool(getattr(opt, "value", False)),
                    }
                )
                continue
            try:
                default = float(getattr(opt, "value", 0.0))
            except Exception:
                default = 0.0
            row: dict[str, Any] = {
                "key": key,
                "label": label,
                "type": "number",
                "default": default,
            }
            for attr in ("min", "max", "step"):
                val = getattr(opt, attr, None)
                if val is not None:
                    try:
                        row[attr] = float(val)
                    except Exception:
                        pass
            fields.append(row)
    return fields


def read_values(short: str) -> dict[str, Any]:
    short = str(short or "").strip().lower()
    out: dict[str, float] = {}
    if short not in _MODULE_SHORT:
        return out
    try:
        eng = _tuning.get_engine(short)
    except Exception:
        return out
    for group in _slider_groups(short, eng):
        for opt in group:
            key = _option_key(opt)
            if not key:
                continue
            try:
                if _option_is_bool(opt):
                    out[key] = bool(getattr(opt, "value", False))
                else:
                    out[key] = float(getattr(opt, "value", 0.0))
            except Exception:
                continue
    return out


def write_values(short: str, values: dict[str, Any]) -> int:
    short = str(short or "").strip().lower()
    if short not in _MODULE_SHORT or not values:
        return 0
    eng = _tuning.get_engine(short)
    updated = 0
    for group in _slider_groups(short, eng):
        for opt in group:
            key = _option_key(opt)
            if not key or key not in values:
                continue
            try:
                if _option_is_bool(opt):
                    opt.value = _as_bool(values[key])
                else:
                    opt.value = float(values[key])
                updated += 1
            except Exception:
                continue
    return updated
