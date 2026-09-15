"""Keep Squ1ggs Boosting Tools as the all-in-one session.

While this mod is enabled, extra copies of the same tools (standalone movement /
kits / spawners, or other live desktop/loot clones) are paused. Squ1ggs runs its
own bundled copies. Those extras come back if you disable Squ1ggs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from unrealsdk import logging

_PREFIX = "[Squ1ggs Boosting Tools | Session]"
PRODUCT_ID = "squ1ggs-boosting-tools"
PRODUCT_AUTHOR = "Squ1ggs"
CLIENT_HEADER = "X-Sqbt-Client"
PRODUCT_HEADER = "X-Sqbt-Product"
CLIENT_VALUE = "squ1ggs-boosting-tools-exe"

_KEEP_FOLDERS = {
    "squ1ggsboostingtools",
    "ultra_local_menu",
    "mods_base",
    "unrealsdk",
    "keybinds",
    "blimgui",
    "pyunrealsdk",
    "oak2",
}

# Pause while Squ1ggs is enabled — they fight spawn, bridge, shapes, or hooks.
# ULM (ultra_local_menu) is intentionally NOT listed here.
_PAUSE_INTERFERING_MODS = frozenset({
    "bl4_live_editor",
    "bl4_loot_presentation",
    "bl4_reward_generator",
    "bl4_world_tools",
    "bl4_world_travel",
    "bl4_coop_session_tools",
    "bl4_challenge_ticker",
    "bl4_inventory_capacity_tools",
    "bl4_teleport_tools",
    "whatamilookingat",
    "azzyuvhbooster",
    "bot_suite",
    "actorscriptdeployer",
    "bvm_vehicle_spawn_catalog",
    "echo4bot",
    "echo4bot_vps",
    "echo4bot_windows",
    "echobot",
    "mattssdkboostingtools",
    "matts_sdk_boosting_tools",
    "mattboostingtools",
})

# Already inside Squ1ggs — extra copies of these fight the all-in-one session.
_BUNDLED_STANDALONES = {
    "bl4_player_movement",
    "bl4_vehicle_movement",
    "bl4_damage_and_more",
    "bl4_resources_and_cooldowns",
    "bl4_mob_spawner",
    "bl4_oak_spawner",
    "bl4_item_spawner",
}

_paused: list[dict[str, str]] = []
_overlap_names: list[str] = []


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
    except Exception:
        print(f"{_PREFIX} {msg}")


def _sdk_mods_root() -> Path | None:
    here = Path(__file__).resolve().parent
    if here.name.lower() == "squ1ggsboostingtools":
        return here.parent
    env = os.environ.get("OAK2_SDK_MODS") or os.environ.get("SDK_MODS")
    if env:
        path = Path(env)
        if path.is_dir():
            return path
    return here.parent if here.parent.is_dir() else None


def _folder_looks_like_live_clone(folder: Path) -> bool:
    """True when another sdk_mods folder copied the desktop bridge / loot catcher."""
    if not folder.is_dir():
        return False
    name = folder.name.lower()
    if name in _KEEP_FOLDERS or name.startswith("."):
        return False
    bridge = folder / "external_bridge.py"
    backend = folder / "backend_actions.py"
    if bridge.is_file() and backend.is_file():
        return True
    markers = 0
    scanned = 0
    try:
        py_files = list(folder.glob("*.py"))[:24]
        py_files.extend(list(folder.glob("*/*.py"))[:16])
    except Exception:
        py_files = []
    for path in py_files:
        if scanned >= 32:
            break
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:120_000]
        except Exception:
            continue
        low = text.lower()
        if ("threadinghamttpserver" in low or "httpserver" in low) and (
            "49775" in text or "50675" in text or "55175" in text
        ):
            return True
        if "sqbt_loot_shapes_tick" in low or "squ1ggsboostingtools.loot_shapes" in low:
            markers += 1
        if "sqbtbridge" in low or "sqbt_bridge" in low:
            markers += 1
        if markers >= 2:
            return True
    return False


def overlapping_peer_folders() -> list[str]:
    root = _sdk_mods_root()
    names: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        raw = str(name or "").strip()
        if not raw:
            return
        key = raw.lower()
        if key in _KEEP_FOLDERS or key in seen:
            return
        seen.add(key)
        names.append(raw)

    for stem in _PAUSE_INTERFERING_MODS:
        add(stem)
    if root is not None:
        try:
            children = list(root.iterdir())
        except Exception:
            children = []
        for child in children:
            try:
                stem = child.name
                if stem.lower().endswith(".sdkmod"):
                    stem = stem[: -len(".sdkmod")]
                key = stem.lower()
                if key in _BUNDLED_STANDALONES and (child.is_dir() or child.is_file()):
                    add(stem)
                elif child.is_dir() and _folder_looks_like_live_clone(child):
                    add(child.name)
            except Exception:
                continue
    return names


def _mod_folder_name(mod: Any) -> str:
    for attr in ("settings_file", "file", "__file__"):
        try:
            raw = getattr(mod, attr, None)
        except Exception:
            raw = None
        if not raw:
            continue
        try:
            path = Path(str(raw))
        except Exception:
            continue
        parts = [p.lower() for p in path.parts]
        for i, part in enumerate(parts):
            if part == "sdk_mods" and i + 1 < len(parts):
                return str(path.parts[i + 1])
        if path.parent.name:
            return path.parent.name
    try:
        name = str(getattr(mod, "name", "") or "")
    except Exception:
        name = ""
    return name


def _should_pause_mod(mod: Any, want: set[str]) -> bool:
    folder = _mod_folder_name(mod)
    key = folder.lower()
    if key in _KEEP_FOLDERS:
        return False
    if key in _PAUSE_INTERFERING_MODS or key in _BUNDLED_STANDALONES or key in want:
        return True
    try:
        path = str(getattr(mod, "settings_file", "") or "").replace("\\", "/").lower()
    except Exception:
        path = ""
    for stem in _BUNDLED_STANDALONES:
        if path.endswith(f"{stem}.json"):
            return True
    return False


def pause_overlapping_peers() -> list[str]:
    """Disable extra copies of tools Squ1ggs already bundles, plus live-tool clones."""
    global _paused, _overlap_names
    _overlap_names = overlapping_peer_folders()
    want = {name.lower() for name in _overlap_names}
    try:
        from mods_base.mod_list import get_ordered_mod_list
    except Exception:
        return []
    paused_now: list[str] = []
    try:
        mods = list(get_ordered_mod_list())
    except Exception:
        return []
    for mod in mods:
        try:
            if not getattr(mod, "is_enabled", False):
                continue
        except Exception:
            continue
        if not _should_pause_mod(mod, want):
            continue
        folder = _mod_folder_name(mod)
        key = folder.lower()
        if any(str(row.get("folder") or "").lower() == key for row in _paused):
            continue
        label = str(getattr(mod, "name", None) or folder)
        disable = getattr(mod, "disable", None)
        if not callable(disable):
            continue
        try:
            disable()
        except Exception as exc:
            _log(f"Could not pause extra mod {label!r}: {exc!r}")
            continue
        _paused.append({"folder": folder, "name": label})
        paused_now.append(label)
        _log(f"Paused extra mod {label!r} — Squ1ggs Boosting Tools already includes this.")
    return paused_now


def still_enabled_bundled_standalones() -> list[str]:
    """Names of bundled-overlap mods that are still enabled after a pause attempt."""
    try:
        from mods_base.mod_list import get_ordered_mod_list
    except Exception:
        return []
    want = {name.lower() for name in overlapping_peer_folders()} | set(_BUNDLED_STANDALONES)
    leftover: list[str] = []
    try:
        mods = list(get_ordered_mod_list())
    except Exception:
        return []
    for mod in mods:
        try:
            if not getattr(mod, "is_enabled", False):
                continue
        except Exception:
            continue
        if not _should_pause_mod(mod, want):
            continue
        leftover.append(str(getattr(mod, "name", None) or _mod_folder_name(mod)))
    return leftover


def restore_overlapping_peers() -> None:
    """Re-enable mods we paused (SQBT disable)."""
    global _paused
    if not _paused:
        return
    try:
        from mods_base.mod_list import get_ordered_mod_list
    except Exception:
        _paused = []
        return
    try:
        mods = list(get_ordered_mod_list())
    except Exception:
        _paused = []
        return
    by_folder = {str(row.get("folder") or "").lower(): row for row in _paused}
    restored: set[str] = set()
    for mod in mods:
        folder = _mod_folder_name(mod).lower()
        if folder not in by_folder:
            continue
        enable = getattr(mod, "enable", None)
        if not callable(enable):
            continue
        try:
            enable()
        except Exception as exc:
            _log(f"Could not restore {by_folder[folder].get('name')!r}: {exc!r}")
        else:
            restored.add(folder)
    # Keep anything that failed to re-enable so the next restore attempt retries it,
    # instead of silently forgetting we still owe it a re-enable.
    _paused = [row for row in _paused if str(row.get("folder") or "").lower() not in restored]


def status_fields() -> dict[str, Any]:
    names = list(_overlap_names) or overlapping_peer_folders()
    paused = [str(row.get("name") or row.get("folder") or "") for row in _paused]
    return {
        "product_id": PRODUCT_ID,
        "product_author": PRODUCT_AUTHOR,
        "peer_overlap": names,
        "peer_paused": paused,
    }


def reclaim_runtime_hooks() -> None:
    """Re-stamp our PlayerTick hooks after other mods may have overwritten them.

    Never force-reinstall when already present — EXE bridge reclaim ran every ~8s
    and stacked/churned hooks (same pyunrealsdk AV hash across dumps).
    """
    try:
        from .loot_shapes import install_loot_shapes_hooks

        install_loot_shapes_hooks(force=False)
    except Exception:
        pass
    try:
        from . import mobility_runtime

        # No-op if already on (avoids log spam + prune every poll).
        mobility_runtime.enable_mobility_runtime()
    except Exception:
        pass
    try:
        from .faafo import ensure_launch_hook

        ensure_launch_hook()
    except Exception:
        pass
