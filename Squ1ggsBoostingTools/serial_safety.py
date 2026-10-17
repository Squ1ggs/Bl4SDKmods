"""Per-code size / repeat profile and the opt-in Console mode send guard.

Tiers: clean (legit-shaped), modded, heavy (extreme length or one part repeated
hundreds of times), broken (does not decode). Console mode only holds back
heavy + broken codes; everything else still sends so long-used modded items keep working.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .serial_converter import is_readable_serial, serial_to_human

_SETTINGS_FILE = Path(__file__).resolve().parent.parent / "settings" / "sqbt_console_safety.json"

DEFAULT_MAX_LENGTH = 2500
DEFAULT_MAX_REPEAT = 300
DEFAULT_TOTAL_WARN = 60000

# Legit drops (GZO Legit set, 2195 codes): never repeat a part, <=20 parts, <=2 foreign families, <=104 chars.
_CLEAN_MAX_PARTS = 24
_CLEAN_MAX_FAMILIES = 2
_CLEAN_MAX_LENGTH = 120

_PART_RE = re.compile(r"\{(\d+)(?::(\d+|\[[^\]]*\]))?\}")
_profile_cache: dict[str, dict[str, Any]] = {}
_settings: dict[str, Any] | None = None


def _clamp(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except Exception:
        return default


def load_settings() -> dict[str, Any]:
    global _settings
    if _settings is not None:
        return dict(_settings)
    data: dict[str, Any] = {}
    try:
        raw = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data = raw
    except Exception:
        data = {}
    _settings = {
        "enabled": bool(data.get("enabled", False)),
        "max_length": _clamp(data.get("max_length"), 200, 20000, DEFAULT_MAX_LENGTH),
        "max_repeat": _clamp(data.get("max_repeat"), 2, 5000, DEFAULT_MAX_REPEAT),
        "total_warn": _clamp(data.get("total_warn"), 5000, 2_000_000, DEFAULT_TOTAL_WARN),
    }
    return dict(_settings)


def save_settings(**changes: Any) -> dict[str, Any]:
    global _settings
    cur = load_settings()
    if "enabled" in changes and changes["enabled"] is not None:
        cur["enabled"] = bool(changes["enabled"])
    for key, lo, hi, default in (
        ("max_length", 200, 20000, DEFAULT_MAX_LENGTH),
        ("max_repeat", 2, 5000, DEFAULT_MAX_REPEAT),
        ("total_warn", 5000, 2_000_000, DEFAULT_TOTAL_WARN),
    ):
        if changes.get(key) not in (None, ""):
            cur[key] = _clamp(changes[key], lo, hi, default)
    _settings = cur
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cur, indent=2), encoding="utf-8")
        tmp.replace(_SETTINGS_FILE)
    except Exception:
        pass
    return dict(cur)


def profile(serial: str) -> dict[str, Any]:
    """Length / part count / worst repeat / foreign families for one @U (cached)."""
    s = str(serial or "").strip()
    hit = _profile_cache.get(s)
    if hit is not None:
        return hit
    out: dict[str, Any] = {"length": len(s), "parts": 0, "max_repeat": 0, "families": 0, "broken": False}
    if not s.startswith("@U") or not is_readable_serial(s):
        out["broken"] = s.startswith("@U")
    else:
        try:
            human = str(serial_to_human(s) or "")
            m = re.match(r"\s*(\d+)\s*,", human)
            type_id = int(m.group(1)) if m else -1
            body = human.split("||", 1)[1] if "||" in human else human
            parts: list[tuple[int, int]] = []
            for pm in _PART_RE.finditer(body):
                a, b = pm.group(1), pm.group(2)
                if b is None:
                    parts.append((type_id, int(a)))
                elif b.startswith("["):
                    parts.extend((int(a), int(v)) for v in b[1:-1].split() if v.isdigit())
                else:
                    parts.append((int(a), int(b)))
            counts = Counter(parts)
            out["parts"] = len(parts)
            out["max_repeat"] = max(counts.values()) if counts else 0
            out["families"] = len({fam for fam, _v in parts if fam != type_id})
        except Exception:
            out["broken"] = True
    if len(_profile_cache) > 8192:
        _profile_cache.clear()
    _profile_cache[s] = out
    return out


def tier(serial: str, settings: dict[str, Any] | None = None) -> str:
    cfg = settings or load_settings()
    p = profile(serial)
    if p["broken"]:
        return "broken"
    if p["length"] > cfg["max_length"] or p["max_repeat"] > cfg["max_repeat"]:
        return "heavy"
    if (
        p["max_repeat"] <= 1
        and p["parts"] <= _CLEAN_MAX_PARTS
        and p["families"] <= _CLEAN_MAX_FAMILIES
        and p["length"] <= _CLEAN_MAX_LENGTH
    ):
        return "clean"
    return "modded"


def package_weight(serial: str, settings: dict[str, Any] | None = None) -> int:
    """Mail package slots one code takes: legit-length 1, modded 2, heavy 4.

    Length-only unless the repeat profile is already cached — never decodes on the send path.
    """
    cfg = settings or load_settings()
    s = str(serial or "").strip()
    n = len(s)
    cached = _profile_cache.get(s)
    if n > cfg["max_length"] or (cached is not None and cached["max_repeat"] > cfg["max_repeat"]):
        return 4
    if n > _CLEAN_MAX_LENGTH or (cached is not None and cached["max_repeat"] > 1):
        return 2
    return 1


def heavy_reason(serial: str, settings: dict[str, Any] | None = None) -> str:
    cfg = settings or load_settings()
    p = profile(serial)
    bits: list[str] = []
    if p["length"] > cfg["max_length"]:
        bits.append(f"{p['length']} chars > {cfg['max_length']}")
    if p["max_repeat"] > cfg["max_repeat"]:
        bits.append(f"one part ×{p['max_repeat']} > {cfg['max_repeat']}")
    return ", ".join(bits)


def console_filter(serials: list[str]) -> tuple[list[str], list[str]]:
    """Console mode on → (kept, held_back heavy). Off → everything kept."""
    cfg = load_settings()
    if not cfg["enabled"]:
        return list(serials), []
    kept: list[str] = []
    held: list[str] = []
    for s in serials:
        if str(s).startswith("@U") and tier(s, cfg) == "heavy":
            held.append(s)
        else:
            kept.append(s)
    return kept, held
