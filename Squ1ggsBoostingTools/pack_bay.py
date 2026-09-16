"""Save Pack / Live Pack — backpack @U sheets for all users.

- Save Pack: EXE decrypts newest character .sav → YAML @U list (no game-thread walk).
- Live Pack: one-shot live scan of Boost target only (hard-capped).
- Shipped on by default. Opt-out: SQBT_PACK_BAY=0. Ghost opacity is EXE chrome.
"""

from __future__ import annotations

import os
from pathlib import Path

# Soft cap for the bay sheet. Full packs stay usable without a full dump.
DEFAULT_ROW_CAP = 160


def _marker_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "Squ1ggsBoostingTools" / "pack_bay.enable"


def is_enabled() -> bool:
    """True for all users unless explicitly opted out."""
    flag = str(os.environ.get("SQBT_PACK_BAY") or os.environ.get("SQBT_ENABLE_PACK_BAY") or "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    # Legacy marker was opt-in; shipping default is on.
    return True


def enable_for_local_test() -> str:
    """No-op for shipping builds — packs are on by default."""
    path = _marker_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Save Pack / Live Pack enabled (default on)\n", encoding="utf-8")
    except Exception:
        pass
    return "Save Pack + Live Pack are on for everyone. Reload the EXE panel if tabs are missing."


def disable_for_local_test() -> str:
    """Opt out via env is preferred; marker alone no longer hides tabs."""
    path = _marker_path()
    try:
        if path.is_file():
            path.unlink()
    except Exception as exc:
        return f"Could not remove marker: {exc}"
    return (
        "Marker removed. Tabs stay visible unless you set SQBT_PACK_BAY=0 "
        "and reload the EXE."
    )


def row_cap() -> int:
    raw = str(os.environ.get("SQBT_PACK_BAY_CAP") or "").strip()
    if raw.isdigit():
        return max(24, min(int(raw), 400))
    return DEFAULT_ROW_CAP


def party_row_cap() -> int:
    """Harder cap for live Live Pack snaps (game-thread)."""
    raw = str(os.environ.get("SQBT_PARTY_BAY_CAP") or "").strip()
    if raw.isdigit():
        return max(24, min(int(raw), 160))
    return min(DEFAULT_ROW_CAP, 160)


TOOLBOX_URL = "https://scooterstoolbox.com"
