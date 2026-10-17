"""Validate the shipped panel structure without importing the game runtime."""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path


APP = Path(__file__).resolve().parents[1]
ROOT = APP / "resources" / "Squ1ggsBoostingTools"
PKG = "Squ1ggsBoostingTools"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(f"{PKG}.{name}", ROOT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pkg = types.ModuleType(PKG)
sys.modules["mods_base"] = types.SimpleNamespace(open_in_mod_dir=lambda path, binary=False: open(path, "rb" if binary else "r"))
pkg.__path__ = [str(ROOT)]
sys.modules[PKG] = pkg
sys.modules[f"{PKG}.world_spawn"] = types.SimpleNamespace(categories=lambda: [])
load_module("_mod_version", "_mod_version.py")
load_module("logo_actor_options", "logo_actor_options.py")
sys.modules[f"{PKG}.tuning_bridge_fields"] = types.SimpleNamespace(
    manifest_fields=lambda _module: []
)
sys.modules[f"{PKG}.loot_shapes"] = types.SimpleNamespace(
    land_layout_defaults=lambda _profile: {}
)
panel = load_module("panel_manifest", "panel_manifest.py")

manifest = panel.get_panel_manifest()
tabs = list(manifest.get("tabs") or [])
ids = [str(tab.get("id") or "") for tab in tabs]
assert len(ids) == len(set(ids)), f"duplicate tab ids: {ids}"
assert "missions" in ids

by_id = {str(tab.get("id") or ""): tab for tab in tabs}
build_sections = list(by_id["builds"].get("sections") or [])
assert any(section.get("serialStore") for section in build_sections)
assert not any(
    section.get("serialStore")
    for section in list(by_id["serials"].get("sections") or [])
)

freecam_titles = {
    str(section.get("title") or "")
    for section in list(by_id["freecam"].get("sections") or [])
}
assert "Third-person view" not in freecam_titles
assert "Third-person view" in {
    str(section.get("title") or "")
    for section in list(by_id["camera"].get("sections") or [])
}
offline = json.loads((APP / "renderer" / "offline_manifest.json").read_text(encoding="utf-8"))
assert offline.get("tabs")
assert [row.get("key") for row in panel._world_drop_location_fields()] == [
    "spawn_anchor"
]
assert "Max backpack 300 · bank 800" in str(by_id["home"])
home_text = str(by_id["home"])
assert "GIVE EVERYTHING" in home_text
assert "'shine': True" in home_text
home_builds = [
    section
    for section in list(by_id["home"].get("sections") or [])
    if section.get("catalog") == "curated_builds"
]
assert len(home_builds) == 1
assert "featured_only" not in str(home_builds[0].get("multiselect") or {})

curated = load_module("curated_builds", "curated_builds.py")
seed = json.loads((ROOT / "squ1ggs_lootlemon_codes.json").read_text(encoding="utf-8"))
seed_rows = [
    {
        "title": row.get("name"),
        "name": row.get("name"),
        "serial": row.get("serial"),
        "category": row.get("category"),
        "rarity": row.get("rarity"),
    }
    for row in seed.get("entries") or []
]
assert len(curated.BUILD_DEFINITIONS) >= 10
assert not curated.validate_definitions(seed_rows)
featured = curated.catalog(seed_rows, {"featured_only": True, "limit": 100})
assert len(featured.get("group_counts") or {}) == 2
assert featured.get("rows")

serial_converter = load_module("serial_converter", "serial_converter.py")
level_60_truck = "@Ugy3L+35E/MOymv9i7M2g8g&yj4^<C!5A~@ss5_`qs8gs~sBoy32m"
level_70_truck = serial_converter.rewrite_item_level(level_60_truck, 70)
assert serial_converter.serial_to_human(level_70_truck).startswith(
    "24, 0, 1, 70|"
)

# Give everything must serialize missions -> challenges -> UVHM.
states = {"mission": "idle", "challenge": "idle", "uvhm": "idle", "grassroots": "idle"}
max_payloads = []
sys.modules[f"{PKG}.backend_actions"] = types.SimpleNamespace(
    get_target_player_index=lambda: 0,
    max_all=lambda payload: (
        max_payloads.append(dict(payload))
        or {"ok": True, "message": "MAX ALL applied"}
    ),
)
sys.modules[f"{PKG}.mission_progress"] = types.SimpleNamespace(
    is_running=lambda: states["mission"] == "running",
    preview=lambda _scope: {"ok": True, "message": "preview"},
    start=lambda _scope, _index, redo_completed=False: (
        states.__setitem__("mission", "running")
        or {"ok": True, "message": "missions queued"}
    ),
    start_grassroots_turnin=lambda _index: (
        states.__setitem__("grassroots", "running")
        or {"ok": True, "message": "Grassroots mission queued"}
    ),
    status=lambda: {
        "running": states["mission"] == "running",
        "phase": states["mission"],
        "message": states["mission"],
    },
    cancel=lambda: True,
)
sys.modules[f"{PKG}.challenge_bulk_runtime"] = types.SimpleNamespace(
    request_selected=lambda *_args, **_kwargs: states.__setitem__("challenge", "queued") or True,
    status=lambda: {
        "running": states["challenge"] == "running",
        "queued": states["challenge"] == "queued",
        "phase": states["challenge"],
        "message": states["challenge"],
    },
    cancel=lambda: True,
)
sys.modules[f"{PKG}.uvhm_runtime"] = types.SimpleNamespace(
    request_selected=lambda *_args, **_kwargs: states.__setitem__("uvhm", "queued") or True,
    status=lambda: {
        "running": states["uvhm"] == "running",
        "queued": states["uvhm"] == "queued",
        "phase": states["uvhm"],
        "message": states["uvhm"],
    },
    cancel=lambda: True,
)
# The coordinator validates stable lobby identities before any economy writes.
identity = types.SimpleNamespace(key="test-host", display_name="Host")
sys.modules[f"{PKG}.uvhm_progression"] = types.SimpleNamespace(
    selected_lobby_identity=lambda _index: identity,
    snapshot_lobby_identities=lambda: (identity,),
)
sys.modules[f"{PKG}.map_discovery"] = types.SimpleNamespace(
    is_running=lambda: False,
    start=lambda _index: {"ok": True, "message": "Discovery queued"},
    status=lambda: {"running": False, "phase": "complete", "accepted": 1391, "message": "Discovery requests sent"},
    cancel=lambda: None,
)
workflow = load_module("give_everything", "give_everything.py")
started = workflow.start({})
assert started["ok"], started
assert max_payloads[-1]["max_mayhem"] is True
assert max_payloads[-1]["max_challenges"] is False
assert workflow.status()["phase"] == "missions"
states["mission"] = "complete"
workflow._last_tick_at = 0
workflow.runtime_tick()
assert workflow.status()["phase"] == "challenges"
states["challenge"] = "complete"
workflow._last_tick_at = 0
workflow.runtime_tick()
assert workflow.status()["phase"] == "uvhm"
states["uvhm"] = "complete"
workflow._last_tick_at = 0
workflow.runtime_tick()
assert workflow.status()["phase"] == "grassroots"
states["grassroots"] = "complete"
sys.modules[f"{PKG}.mission_progress"].status = lambda: {
    "running": False, "phase": "complete",
    "results": [{"name": "SideMission", "outcome": "completed"}],
}
workflow._last_tick_at = 0
workflow.runtime_tick()
assert workflow.status()["workflow_phase"] == "discovery"
workflow._last_tick_at = 0
workflow.runtime_tick()
assert workflow.status()["state"] == "complete"
assert workflow.status()["discovery_summary"]["accepted"] == 1391
print("ALL OK")
