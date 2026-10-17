"""Finish 3.10.5 Steam live mod patches (bridge/panel/version/changelog)."""
from __future__ import annotations

from pathlib import Path

STEAM = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Borderlands 4\sdk_mods\Squ1ggsBoostingTools"
)

# --- bridge_actions_extended soft_lobby_spread ---
bridge = STEAM / "bridge_actions_extended.py"
b = bridge.read_text(encoding="utf-8")
old = '''    # Never splat fill_until_complete into begin_spawn_landing (TypeError → fake "app out of date").
    before_keys: set[str] | None = None
    if land_wanted:
        begin_spawn_landing(
            est,
            shape=shape_l,
            settle=settle_l,
            drop_height=float(land.get("drop_height") or 440),
            line_length=float(land.get("line_length") or 520),
            radius=float(land.get("radius") or 200),
            spacing=float(land.get("spacing") or 72),
            z_bias=float(land.get("z_bias") or 18),
            spawn_then_shape=bool(land.get("spawn_then_shape")),
            stay_in_air=bool(land.get("stay_in_air", True)),
            float_on_grab=bool(land.get("float_on_grab", False)),
            peel_after=float(land.get("peel_after") or 0),
            land_profile=str(land.get("land_profile") or "shiny"),
        )
        arm_overhead_catch(max(24.0, est * 0.12))
    elif not soft_lobby:
        # Shape none (solo): SpillOut piles at feet — snapshot so we can fan like Drop All Shinies.
        try:
            before_keys = snapshot_pickup_ids()
        except Exception:
            before_keys = set()
        try:
            arm_backpack_fan_during_spill(before_keys, limit=max(32, min(400, int(est))))
        except Exception:
            pass
    try:
        if soft_lobby and not land_wanted:
            result = _faafo_apply(
                payload,
                _faafo.do_drop_backpack,
                max_passes=10,
                soft_lobby=True,
            )
        else:
            result = _faafo_apply(payload, _faafo.do_drop_backpack)
    finally:
        try:
            clear_backpack_fan_during_spill()
        except Exception:
            pass
    # SpillOut dumps at feet — same end sweep Drop All / Spawn All use so catch pulls into slots.
    if land_wanted:
        try:
            if landing_armed():
                from .loot_shapes import pull_new_pickups_into_shape

                settle_landing_loot(limit=max(32, min(200, int(est))))
                # Immediate extra sweeps: settle alone can't finish a 300+ pack in one pass.
                for _ in range(6):
                    if pull_new_pickups_into_shape(limit=12, fresh=True) <= 0:
                        break
                arm_deferred_catch(max(28.0, float(est) * 0.12))
        except Exception:
            pass
    elif soft_lobby:
        # Native feet pile — let ordinary replication carry items. No ForceNet ring storm.
        if isinstance(result, dict):
            msg = str(result.get("message") or "")
            if msg and "soft-lobby" not in msg.lower():
                result = dict(result)
                result["message"] = f"{msg} (lobby soft: feet pile, paced SpillOut)"
    elif before_keys is not None:'''

new = '''    # Never splat fill_until_complete into begin_spawn_landing (TypeError → fake "app out of date").
    before_keys: set[str] | None = None
    soft_spread = False
    raw_spread = payload.get("soft_lobby_spread")
    if raw_spread is not None:
        soft_spread = str(raw_spread).strip().lower() in ("1", "true", "yes", "on")
    if land_wanted:
        begin_spawn_landing(
            est,
            shape=shape_l,
            settle=settle_l,
            drop_height=float(land.get("drop_height") or 440),
            line_length=float(land.get("line_length") or 520),
            radius=float(land.get("radius") or 200),
            spacing=float(land.get("spacing") or 72),
            z_bias=float(land.get("z_bias") or 18),
            spawn_then_shape=bool(land.get("spawn_then_shape")),
            stay_in_air=bool(land.get("stay_in_air", True)),
            float_on_grab=bool(land.get("float_on_grab", False)),
            peel_after=float(land.get("peel_after") or 0),
            land_profile=str(land.get("land_profile") or "shiny"),
        )
        arm_overhead_catch(max(24.0, est * 0.12))
    elif not soft_lobby:
        # Shape none (solo): SpillOut piles at feet — snapshot so we can fan like Drop All Shinies.
        try:
            before_keys = snapshot_pickup_ids()
        except Exception:
            before_keys = set()
        try:
            arm_backpack_fan_during_spill(before_keys, limit=max(32, min(400, int(est))))
        except Exception:
            pass
    elif soft_lobby and soft_spread:
        try:
            before_keys = snapshot_pickup_ids()
        except Exception:
            before_keys = set()
    try:
        if soft_lobby and not land_wanted:
            result = _faafo_apply(
                payload,
                _faafo.do_drop_backpack,
                max_passes=10,
                soft_lobby=True,
            )
        else:
            result = _faafo_apply(payload, _faafo.do_drop_backpack)
    finally:
        try:
            clear_backpack_fan_during_spill()
        except Exception:
            pass
    # SpillOut dumps at feet — same end sweep Drop All / Spawn All use so catch pulls into slots.
    if land_wanted:
        try:
            if landing_armed():
                from .loot_shapes import pull_new_pickups_into_shape

                settle_landing_loot(limit=max(32, min(200, int(est))))
                # Immediate extra sweeps: settle alone can't finish a 300+ pack in one pass.
                for _ in range(6):
                    if pull_new_pickups_into_shape(limit=12, fresh=True) <= 0:
                        break
                arm_deferred_catch(max(28.0, float(est) * 0.12))
        except Exception:
            pass
    elif soft_lobby:
        if isinstance(result, dict):
            msg = str(result.get("message") or "")
            if msg and "soft-lobby" not in msg.lower():
                result = dict(result)
                note = "lobby soft: feet pile, paced SpillOut"
                if soft_spread:
                    note += ", wider spread"
                result["message"] = f"{msg} ({note})"
        if soft_spread and before_keys is not None:
            try:
                spread_limit = max(32, min(400, int(est)))
                for _ in range(4):
                    if (
                        spread_pickups_shiny_rings(
                            before_keys=before_keys,
                            limit=spread_limit,
                            radius=220.0,
                            forward=200.0,
                            force=True,
                        )
                        <= 0
                    ):
                        break
                arm_deferred_shiny_spread(
                    before_keys, seconds=8.0, limit=spread_limit, force=True
                )
            except Exception:
                pass
    elif before_keys is not None:'''

if "soft_lobby_spread" not in b:
    if old not in b:
        raise SystemExit("bridge block not found")
    bridge.write_text(b.replace(old, new, 1), encoding="utf-8")
    print("bridge patched")
else:
    print("bridge already has soft_lobby_spread")

# --- panel_manifest ---
panel = STEAM / "panel_manifest.py"
p = panel.read_text(encoding="utf-8")
p2 = p
p2 = p2.replace(
    '''            "tooltip": (
                "Works with Boost target All players (or anyone): codes go to the HOST only, open into "
                "their backpack, then drop onto the ground (or into a shape) so the whole lobby can grab. "
                "Default pile ~150 Modded codes. Refresh Codes once first. Not guest mail."
            ),''',
    '''            "tooltip": (
                "Works with Boost target All players (or anyone): codes go to the HOST only, open into "
                "their backpack, then drop onto the ground (or into a shape) so the whole lobby can grab. "
                "Loops every Drop-again interval while Auto Lobby is on. "
                "Optional: also mail a second Item list to guests. "
                "Default pile ~150 Modded codes. Refresh Codes once first."
            ),''',
    1,
)
p2 = p2.replace(
    '''            "tooltip": (
                "None = soft feet pile. A shape holds loot in a silhouette guests can Use/pick up "
                "(coop-safe; pin budget ~180). Auto-drop already pauses while someone joins."
            ),''',
    '''            "tooltip": (
                "None = wider soft feet pile (gentle spread, no ForceNet ring storm). "
                "A shape holds loot in a silhouette guests can Use/pick up "
                "(coop-safe; pin budget ~180). Auto-drop already pauses while someone joins."
            ),''',
    1,
)
old_pack = '''        {
            "key": "item_drip_pack",
            "label": "Item list name",
            "type": "text",
            "default": "",
            "field_group": drip,
            "visible_when": {"key": "item_drip_mode", "equals": "pack"},
            "tooltip": "Used when Where items come from = Item list. Leave blank for All.",
        },'''
new_pack = '''        {
            "key": "item_drip_pack",
            "label": "Item list to drop",
            "type": "text",
            "default": "",
            "field_group": drip,
            "visible_when": {"key": "item_drip_mode", "equals": "pack"},
            "tooltip": "Item list spilled on the ground for the lobby. Leave blank for All.",
        },
        {
            "key": "item_drip_mail_pack",
            "label": "Also mail Item list to guests (optional)",
            "type": "text",
            "default": "",
            "field_group": drip,
            "tooltip": (
                "Optional second Item list name. After the drop list is mailed to the host, "
                "these codes are mailed to guests (not spilled). Same name = mail + drop the same list. "
                "Blank = drop only."
            ),
        },'''
if "item_drip_mail_pack" not in p2:
    if old_pack not in p2:
        raise SystemExit("panel pack field not found")
    p2 = p2.replace(old_pack, new_pack, 1)
panel.write_text(p2, encoding="utf-8")
print("panel patched")

# --- version ---
ver = STEAM / "_mod_version.py"
ver.write_text(
    '''"""Single source of truth for the Squ1ggsBoostingTools package version."""

__version__: str = "3.10.5"
__version_info__: tuple[int, int, int] = (3, 10, 5)
''',
    encoding="utf-8",
)
print("version 3.10.5")

# --- changelog ---
cl = STEAM / "CHANGELOG.md"
c = cl.read_text(encoding="utf-8")
entry = '''## 3.10.5 / EXE 1.3.4
- **Editor pearlescent classmods:** pearl hook no longer uses TED_SG `{7:54}` — item cards stay Class Mod (not Shotgun); pearl still injects a non-gun foreign rarity when needed.
- **Editor classmod perk icons:** keep resolving after several skills are added (code-stem fallback + stronger card glyph backfill; passive↔perks alt both ways).
- **Auto Lobby auto-drop:** loops while Auto Lobby is on; optional **Also mail Item list to guests** (drop pack 1, mail pack 2); shape none uses a wider soft feet spread.
- **Most used:** shorter action buttons (same labels).

'''
if "## 3.10.5 / EXE 1.3.4" not in c:
    if c.startswith("# Changelog\n"):
        c = c.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
    else:
        c = entry + c
    cl.write_text(c, encoding="utf-8")
    print("changelog patched")
else:
    print("changelog already has 3.10.5/1.3.4")
