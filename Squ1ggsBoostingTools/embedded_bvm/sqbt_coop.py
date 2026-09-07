"""Squ1ggs Boosting Tools coexistence — standalones stay primary, SQBT reuses them when both are on."""
from __future__ import annotations

import os

# Squ1ggs Boosting Tools sets this when it enables.
SQBT_HOST_FLAG = "SQBT_TUNING_HOST"


def skip_own_blimgui_tab(settings_filename: str, *, embedded_copy: bool = False) -> bool:
    """True = do not register this mod's BLImGui tab (SQBT panel covers it)."""
    if embedded_copy:
        return True
    if os.environ.get(SQBT_HOST_FLAG) != "1":
        return False
    return _mod_enabled(settings_filename)


def _mod_enabled(settings_filename: str) -> bool:
    try:
        from mods_base.mod_list import get_ordered_mod_list
    except Exception:
        return False

    want = settings_filename.replace("\\", "/")
    for mod in get_ordered_mod_list():
        if not getattr(mod, "is_enabled", False):
            continue
        path = str(getattr(mod, "settings_file", "") or "").replace("\\", "/")
        if path.endswith(want):
            return True
    return False
