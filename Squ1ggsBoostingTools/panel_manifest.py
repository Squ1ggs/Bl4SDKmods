"""Machine-readable UI layout for the Squ1ggs Boosting Tools desktop app."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import world_spawn
from ._mod_version import __version__
from .logo_actor_options import DEFAULT_LOGO_ACTOR, logo_actor_select_options
from .tuning_bridge_fields import manifest_fields as _tuning_manifest_fields

TAB_LABELS: tuple[str, ...] = (
    "Home",
    "Player",
    "Progress",
    "Loot",
    "Serials",
    "Backpack",
    "Mobility",
    "Vehicle",
    "Damage & More",
    "Kits & Shields",
    "World",
    "Mob and IO Spawner",
    "Loot Shapes",
    "F.A.A.F.O.",
    "Keybinds",
    "Toggles",
    "Support",
)

_OPEN_REWARDS_LARGE_WARNING = (
    "Open rewards runs one mail package at a time with a 3–5s wait between opens "
    "(never bulk-open — that can crash or blank backpacks in multiplayer). "
    "Large sends (250+) still take a while; prefer solo for big opens, then bank/mule before rejoining MP."
)

_BOOST_SAFETY_DANGER = (
    "Always check Boost target (player bar under the tabs) — you are editing that player's save, "
    "not necessarily your own. Use Squ1ggs tools in good humour with friends who opted in; "
    "do not grief strangers. F.A.A.F.O. pranks and mass-drop tools are for fun with your group — "
    "not for harassing randoms. Spread huge loot across bank and mule characters so saves stay healthy."
)

_REWARDS_AND_INVENTORY_WARNING = (
    "Mail / rewards: Open rewards on send defaults to Yes — each package opens one-by-one "
    "with a 3–5s gap (never open hundreds in one frame). Console / cross-play: avoid bulk Open pending in MP. "
    "If someone carries roughly 250–300+ items and joins online, backpack slots can look empty until "
    "they drop below that in solo — fix in solo, then split gear between bank and mule chars before going online again."
)

_SHAPE_2D_OPTIONS: list[str] = [
    "circle",
    "double_ring",
    "spiral",
    "star",
    "star_filled",
    "firehawk",
    "diamond",
    "square",
    "grid",
    "rows",
    "arc",
    "fan",
    "arrow",
    "cross",
    "x_mark",
    "infinity",
    "figure8",
    "wave",
    "letter_s",
    "lightning",
    "vault",
    "psycho",
    "pyramid",
    "hexagon",
    "honeycomb",
    "scatter",
    "poisson",
    "rarity_lanes",
    "type_piles",
    "unique_piles",
    "heart",
    "line",
    "rings",
    "smiley",
]
_SHAPE_3D_OPTIONS: list[str] = [
    "house",
    "boat",
    "car",
    "dome",
    "dna_helix",
    "claptrap",
    "pyramid_3d",
    "globe",
    "diamond_3d",
    "blocks",
    "cube",
    "torus",
    "crown",
    "ufo",
    "rocket",
    "gear",
]
_SHAPE_SELECT_OPTIONS: list[str] = [*_SHAPE_3D_OPTIONS, *_SHAPE_2D_OPTIONS]
_SHAPE_OPTION_LABELS: dict[str, str] = {
    "dna_helix": "DNA helix",
    "pyramid_3d": "pyramid",
    "psycho": "psycho",
    "claptrap": "Claptrap",
    "x_mark": "X mark",
    "globe": "globe",
    "letter_s": "letter S",
    "star_filled": "star filled",
    "double_ring": "double ring",
    "type_piles": "type piles",
    "unique_piles": "unique item piles",
    "rarity_lanes": "rarity lanes",
    "diamond_3d": "diamond (3D)",
    "blocks": "blocks",
    "cube": "cube",
    "torus": "torus",
    "crown": "crown",
    "ufo": "UFO",
    "rocket": "rocket",
    "gear": "gear",
    "forbidden_one": "the forbidden one",
    "forbidden_pair": "the forbidden pair",
}
_SETTLE_SELECT_OPTIONS: list[str] = [
    "none",
    "slow",
    "medium",
    "fast",
    "spiral",
    "rain",
    "fountain",
    "stagger",
    "snap",
    "drip",
]
_SETTLE_OPTION_LABELS: dict[str, str] = {
    "none": "None (ground)",
    "slow": "Slow drop",
    "medium": "Medium drop",
    "fast": "Fast drop",
    "spiral": "Spiral",
    "rain": "Rain",
    "fountain": "Fountain",
    "stagger": "Stagger",
    "snap": "Snap onto slots",
    "drip": "Drip peel to ground",
}


def _shape_select_field(*, include_none: bool, default: str, label: str, land_profile: str = "") -> dict[str, Any]:
    options = (["none"] if include_none else []) + list(_SHAPE_SELECT_OPTIONS)
    groups: list[dict[str, Any]] = []
    if include_none:
        groups.append({"label": "Off", "options": ["none"]})
    groups.append({"label": "3D shapes", "options": list(_SHAPE_3D_OPTIONS)})
    groups.append({"label": "2D", "options": list(_SHAPE_2D_OPTIONS)})
    out: dict[str, Any] = {
        "key": "shape",
        "label": label,
        "type": "select",
        "options": options,
        "option_groups": groups,
        "option_labels": dict(_SHAPE_OPTION_LABELS),
        "default": default,
    }
    if land_profile:
        out["land_profile"] = land_profile
    return out

TAB_SHORT_LABELS: tuple[str, ...] = (
    "Home",
    "Player",
    "Progress",
    "Loot",
    "Serials",
    "Backpack",
    "Mobility",
    "Vehicle",
    "Damage",
    "Kits",
    "World",
    "Mob / IO",
    "Shapes",
    "FAAFO",
    "Keybinds",
    "Toggles",
    "Support",
)

# Recent release highlights on Home (collapsible — not the dev changelog).
HOME_WHATS_NEW: tuple[str, ...] = (
    "Character cap 70 — MAX ALL / Player level / keybinds boost to 70 (gear defaults follow).",
    "Item-pool catalog refresh for the main page is coming soon — this drop is the level-70 pre-update.",
    "Send serials — Browse/YAML into paste box; Add to library…; open rewards one-at-a-time.",
    "Spawn shapes — UFO, rocket, gear, crown, torus, cube, blocks, diamond (3D).",
)

_AGGRO_MODES = ["attack_me", "attack_party", "free_for_all", "nearest_other", "passive"]
_SPAWN_ANCHORS = ["local", "party", "npc_nearest"]
_SHINY_DROP_TOOLTIP = (
    "Shiny cosmetics must be unlocked on this save. Finished the story? Start a new game in UVHM "
    "and Drop All Shinies should spawn them."
)
_SHINY_NOTE_BEFORE = (
    "If these spawn as normal Legendaries, the Shiny unlocks are not loaded for this character. "
    "Story finished: start a new game in UVHM, then Drop All Shinies. Or use a save editor such as "
)
_SHINY_NOTE_AFTER = (
    " to give all unlocks, load that save, then Drop All Shinies again."
)
_MAYHEM_NOTE = (
    "Bypasses the first normal clear. Sets Mayhem Rank: 1+ unlocks Mayhem mode, "
    "5+ unlocks Hardcore (default 10 does both). Reload save after — kiosk UI will not update until then."
)
_DEFAULT_ITEM_LEVEL = 70
_MOB_SECTIONS = [
    "All",
    "dedicated_drop_bosses_91",
    "true_boss_variants_no_dedicated_row_67",
    "boss_rank_enemies_74",
    "npcs_287",
    "enemies_combat_actors_857",
    "ncs_discovered_actors",
]


def _io_categories() -> list[str]:
    path = Path(__file__).resolve().parent / "embedded_bms" / "data" / "io_spawn_catalog.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cats = data.get("categories") if isinstance(data, dict) else None
        if isinstance(cats, list):
            return ["All", *[str(c) for c in cats if str(c).strip()]]
    except Exception:
        pass
    return ["All"]


def _delivery_recipient_fields() -> list[dict[str, Any]]:
    return [
        {
            "key": "player_index",
            "label": "Send to",
            "type": "player_select",
            "default": "",
            "includeAll": True,
        },
        {
            "key": "open_rewards",
            "label": "Open rewards on send",
            "type": "select",
            "options": ["yes", "no"],
            "default": "yes",
            "tooltip": _OPEN_REWARDS_LARGE_WARNING,
        },
    ]


def _progression_player_field() -> dict[str, Any]:
    return {
        "key": "player_index",
        "label": "Target player",
        "type": "player_select",
        "default": "",
        "includeAll": True,
    }


def _uvhm_max_rank_field() -> dict[str, Any]:
    return {
        "key": "max_rank",
        "label": "Up to UVHM rank",
        "type": "select",
        "options": ["1", "2", "3", "4", "5", "6", "7"],
        "default": "7",
    }


def _progression_target_fields(*, include_max_rank: bool = False) -> list[dict[str, Any]]:
    fields = [_progression_player_field()]
    if include_max_rank:
        fields.append(_uvhm_max_rank_field())
    return fields


def _item_pool_spawn_fields(*, land: bool = False) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = [
        {"key": "level", "label": "Item level", "type": "number", "default": _DEFAULT_ITEM_LEVEL},
        {"key": "count", "label": "Count per pool", "type": "number", "default": 1},
        *_world_drop_location_fields(),
    ]
    if land:
        fields.extend(_bulk_land_fields())
    return fields


def _item_pool_browser_section(pool_categories: list[str]) -> dict[str, Any]:
    return {
        "title": "Loot Pool Spawner",
        "hint": (
            "Legendaries under weapon tabs; shinies only under Shiny; pearls under Pearl. "
            "If a named row is missing or Spawn this one item fails, use Spawn all filtered "
            "on that tab, or spawn the type pool (AR / SG / SM / PS / SR 05 Legendary, "
            "or Pearl type pools). "
            "Use the coloured toggles to hide cash / oversized AI guns. "
            "Land / shape options sit with Spawn all filtered on this page."
        ),
        "poolBrowser": {
            "catalog": "item_pools",
            "categories": pool_categories,
            "defaultCategory": "All",
            "toggles": [
                {
                    "key": "exclude_currency",
                    "label": "No cash",
                    "default": True,
                    "color": "#3ddc97",
                    "tooltip": "Hide currency / cash / money pools from the list and Spawn all filtered.",
                },
                {
                    "key": "exclude_ai_guns",
                    "label": "No AI guns",
                    "default": True,
                    "color": "#5b8cff",
                    "tooltip": "Hide oversized NPC / mech / mounted guns (DahlMech, Brute, Meathead, …).",
                },
            ],
        },
        "actions": [
            _action(
                "Spawn this one item",
                "spawn_item_pool",
                fields=_item_pool_spawn_fields(land=False),
                full_width=True,
                tooltip="Same live world path as Spawn all filtered, but only the highlighted row.",
            ),
            _action(
                "Stop spawn list",
                "spawn_item_pool_cancel",
                tooltip="Cancel an in-progress Spawn All queue.",
                full_width=True,
            ),
            _action(
                "Spawn all filtered",
                "spawn_item_pool_all",
                fields=[
                    *_item_pool_spawn_fields(land=True),
                    {"key": "spawn_gap", "label": "Delay between items (sec)", "type": "number", "default": 0.1},
                    {"key": "spawn_per_tick", "label": "Items per tick", "type": "number", "default": 1},
                    {
                        "key": "random_spread",
                        "label": "Spit random directions",
                        "type": "select",
                        "options": ["yes", "no"],
                        "default": "no",
                    },
                ],
                confirm="Queue every loot pool matching the search/category filter? Narrow filters first to avoid freezes.",
                full_width=True,
            ),
        ],
    }


def _world_drop_location_fields() -> list[dict[str, Any]]:
    return [
        {
            "key": "spawn_anchor",
            "label": "Drop / spawn near",
            "type": "select",
            "options": _SPAWN_ANCHORS,
            "default": "local",
        },
        {
            "key": "player_index",
            "label": "Party player",
            "type": "player_select",
            "default": "",
            "includeAll": False,
        },
    ]


def _bms_group_option_fields() -> list[dict[str, Any]]:
    return [
        {
            "key": "advance",
            "label": "Next wave when",
            "type": "select",
            "options": ["on_clear", "timed", "manual"],
            "default": "on_clear",
        },
        {
            "key": "loop",
            "label": "Loop waves",
            "type": "select",
            "options": ["off", "last", "all"],
            "default": "off",
        },
        {"key": "timed_seconds", "label": "Timed delay (seconds)", "type": "number", "default": 25},
        {"key": "distance", "label": "Spawn distance", "type": "number", "default": 900},
        {
            "key": "aggro_mode",
            "label": "Aggro mode",
            "type": "select",
            "options": _AGGRO_MODES,
            "default": "attack_me",
        },
        *_world_drop_location_fields(),
    ]


def _bms_spawn_fields() -> list[dict[str, Any]]:
    return [
        {"key": "count", "label": "Count (1–999)", "type": "number", "default": 1},
        {
            "key": "aggro_mode",
            "label": "Aggro mode",
            "type": "select",
            "options": _AGGRO_MODES,
            "default": "attack_me",
        },
        *_world_drop_location_fields(),
    ]


def _io_spawn_fields() -> list[dict[str, Any]]:
    """World IO props are not combatants — no aggro mode."""
    return [
        {"key": "count", "label": "Count (1–999)", "type": "number", "default": 1},
        *_world_drop_location_fields(),
    ]


def _mobility_slider_fields() -> list[dict[str, Any]]:
    return [
        {"key": "speed_scale", "label": "Speed scale", "type": "number", "default": 2.0},
        {"key": "walk_speed", "label": "Walk speed", "type": "number", "default": 1500},
        {"key": "jump_goal", "label": "Jump height", "type": "number", "default": 420},
        {"key": "gravity_scale", "label": "Gravity scale", "type": "number", "default": 1.0},
        {"key": "max_step_height", "label": "Max step height", "type": "number", "default": 45},
        {"key": "walkable_floor_angle", "label": "Walkable floor angle", "type": "number", "default": 44.77},
        {"key": "walkable_floor_z", "label": "Walkable floor Z", "type": "number", "default": 0.71},
        {"key": "glide_speed", "label": "Glide speed", "type": "number", "default": 2600},
        {"key": "glide_boost", "label": "Glide boost", "type": "number", "default": 4200},
        {"key": "glide_air_control", "label": "Glide air control", "type": "number", "default": 6.0},
        {"key": "dash_speed", "label": "Dash speed", "type": "number", "default": 3000},
        {
            "key": "zero_vault_costs",
            "label": "Zero vault costs on apply",
            "type": "select",
            "options": ["yes", "no"],
            "default": "yes",
        },
    ]


def _party_slot_field() -> dict[str, Any]:
    return {"key": "slot", "label": "Party slot", "type": "select", "options": ["0", "1", "2", "3"], "default": "0"}


def _legit_item_types() -> list[str]:
    try:
        from . import legit_builder_core as core

        seen: set[str] = set()
        order = [
            "pistol",
            "smg",
            "shotgun",
            "assault_rifle",
            "sniper",
            "shield",
            "repair_kit",
            "enhancement",
            "gadget",
            "heavy",
            "class_mod",
        ]
        for row in core.roots():
            item_type = str(row.get("item_type") or "").strip()
            if item_type:
                seen.add(item_type)
        return [t for t in order if t in seen] + sorted(seen.difference(order))
    except Exception:
        return ["pistol", "smg", "shotgun", "assault_rifle", "sniper", "shield", "class_mod"]


def _legit_forge_fields(*, include_delivery: bool = False, include_part_picker: bool = False) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = [
        {
            "key": "item_type",
            "label": "Item type",
            "type": "select",
            "options": _legit_item_types(),
            "default": "pistol",
            "catalogParam": "item_type",
        },
        {
            "key": "manufacturer",
            "label": "Manufacturer",
            "type": "catalog_select",
            "catalog": "legit_manufacturers",
            "valueKey": "id",
            "labelKey": "label",
            "catalogParamsFrom": ["item_type"],
        },
        {
            "key": "root_key",
            "label": "Item root",
            "type": "catalog_select",
            "catalog": "legit_roots",
            "valueKey": "key",
            "labelKey": "build_label",
            "search": True,
            "catalogParamsFrom": ["item_type", "manufacturer"],
        },
        {
            "key": "parts",
            "label": "Part keys (one per line)",
            "type": "textarea",
            "default": "",
            "placeholder": "inv_comp:comp_05_legendary  (# comments allowed)",
        },
        {"key": "level", "label": "Level", "type": "number", "default": 70},
        {
            "key": "unlock_rules",
            "label": "Unlock rules (modded gear)",
            "type": "select",
            "options": ["no", "yes"],
            "default": "no",
        },
    ]
    if include_part_picker:
        fields.append(
            {
                "key": "pick",
                "label": "Part catalog",
                "type": "catalog_select",
                "catalog": "legit_parts",
                "valueKey": "part_line",
                "labelKey": "display",
                "search": True,
                "catalogParamsFrom": ["root_key"],
            }
        )
    if include_delivery:
        fields.append(
            {"key": "mode", "label": "Delivery mode", "type": "select", "options": ["selected", "nonhost"], "default": "selected"}
        )
    return fields


def _tuning_apply_action(label: str, module: str, *, extra_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"module": module}
    if extra_payload:
        payload.update(extra_payload)
    return _action(label, "tuning_apply", payload=payload, fields=_tuning_manifest_fields(module))


def _challenge_categories() -> list[str]:
    try:
        from .challenge_bulk_runtime import CATEGORY_LABELS

        return list(CATEGORY_LABELS)
    except Exception:
        return [
            "All non-UVHM",
            "Vault of the Damned",
            "Story challenge flags",
            "Activities",
            "Collectibles",
            "Loot",
            "Weapons",
            "Manufacturers",
            "Combat",
            "Enemies",
            "Elemental",
            "Economy",
            "Character",
            "Shinies",
            "Achievements / Misc",
            "Other",
        ]


_CONSOLE_REWARDS_WARNING = _REWARDS_AND_INVENTORY_WARNING


def _num_field(
    key: str,
    label: str,
    default: float | int,
    *,
    min_v: float | int,
    max_v: float | int,
    step: float | int = 1,
    tooltip: str = "",
    field_fold: str = "",
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "key": key,
        "label": label,
        "type": "number",
        "default": default,
        "min": min_v,
        "max": max_v,
        "step": step,
    }
    if tooltip:
        out["tooltip"] = tooltip
    if field_fold:
        out["field_fold"] = field_fold
    return out


def _settle_select_field(*, default: str = "none", field_fold: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {
        "key": "settle",
        "label": "Settle",
        "type": "select",
        "options": list(_SETTLE_SELECT_OPTIONS),
        "option_labels": dict(_SETTLE_OPTION_LABELS),
        "default": default,
        "tooltip": "Drop-from-above: none = ground spawn; snap = fall onto slots; drip = peel 3D down.",
    }
    if field_fold:
        out["field_fold"] = field_fold
    return out


def _air_hold_fields(*, field_fold: str = "") -> list[dict[str, Any]]:
    stay: dict[str, Any] = {
        "key": "stay_in_air",
        "label": "Stay in air",
        "type": "select",
        "options": ["yes", "no"],
        "default": "yes",
        "tooltip": "3D shapes stay up instead of falling to the ground.",
    }
    if field_fold:
        stay["field_fold"] = field_fold
    return [
        stay,
        _num_field(
            "peel_after",
            "Peel delay (sec)",
            0,
            min_v=0,
            max_v=70,
            step=1,
            field_fold=field_fold,
            tooltip="After this many seconds, peel 3D down. 0 = keep in air when Stay in air is yes.",
        ),
    ]


def _shiny_land_fields() -> list[dict[str, Any]]:
    return [
        _shape_select_field(include_none=True, default="house", label="Shape", land_profile="shiny"),
        _settle_select_field(),
        *_air_hold_fields(),
        {
            "key": "fill_until_complete",
            "label": "Continue until shape complete — pads drops until silhouette is full (house ≈ 420, smiley ≈ 140)",
            "type": "select",
            "options": ["no", "yes"],
            "default": "yes",
        },
        {
            "key": "spawn_then_shape",
            "label": "Spawn all, then shape",
            "type": "select",
            "options": ["no", "yes"],
            "default": "no",
        },
        _num_field("drop_height", "Drop height", 440, min_v=0, max_v=800, step=10),
        _num_field("z_bias", "Ground height", 18, min_v=0, max_v=250, step=5),
        _num_field("radius", "Shape radius", 200, min_v=80, max_v=800, step=10),
        _num_field("spacing", "Shape spacing", 72, min_v=50, max_v=400, step=5),
        _num_field(
            "line_length",
            "Line length",
            1100,
            min_v=200,
            max_v=2000,
            step=10,
        ),
    ]


def _bulk_land_fields() -> list[dict[str, Any]]:
    """Land arrangement for Spawn All Filtered / shaped world drops."""
    return [
        _shape_select_field(include_none=True, default="none", label="Shape", land_profile="bulk"),
        _settle_select_field(),
        *_air_hold_fields(),
        {
            "key": "fill_until_complete",
            "label": "Continue until shape complete — pads drops until silhouette is full (house ≈ 420, smiley ≈ 140)",
            "type": "select",
            "options": ["no", "yes"],
            "default": "yes",
        },
        {
            "key": "spawn_then_shape",
            "label": "Spawn all, then shape",
            "type": "select",
            "options": ["no", "yes"],
            "default": "no",
        },
        _num_field("drop_height", "Drop height", 440, min_v=0, max_v=800, step=10),
        _num_field("z_bias", "Ground height", 18, min_v=0, max_v=250, step=5),
        _num_field("radius", "Shape radius", 240, min_v=80, max_v=800, step=10),
        _num_field("spacing", "Shape spacing", 68, min_v=50, max_v=400, step=5),
        _num_field(
            "line_length",
            "Line length",
            1400,
            min_v=200,
            max_v=2000,
            step=10,
        ),
    ]


def _loot_layout_fields() -> list[dict[str, Any]]:
    layout_fold = "Layout tuning"
    advanced_fold = "More options"
    return [
        _shape_select_field(include_none=False, default="circle", label="Shape"),
        _settle_select_field(),
        *_air_hold_fields(),
        _num_field("radius", "Radius", 220, min_v=80, max_v=800, step=10, field_fold=layout_fold),
        _num_field("spacing", "Spacing", 140, min_v=50, max_v=400, step=5, field_fold=layout_fold),
        _num_field("per_ring", "Per ring", 28, min_v=6, max_v=64, step=1, field_fold=layout_fold),
        _num_field("z_bias", "Ground height", 18, min_v=0, max_v=250, step=5, field_fold=layout_fold),
        _num_field("stack_height", "Stack height", 0, min_v=0, max_v=200, step=5, field_fold=layout_fold),
        _num_field(
            "line_length",
            "Line length",
            900,
            min_v=200,
            max_v=2000,
            step=10,
            field_fold=layout_fold,
            tooltip="Line, S, lightning, and wave shapes.",
        ),
        _num_field(
            "drop_height",
            "Drop height",
            440,
            min_v=0,
            max_v=800,
            step=10,
            field_fold=advanced_fold,
            tooltip="How high items start when settle is not none.",
        ),
        {
            "key": "spawn_then_shape",
            "label": "Spawn then shape",
            "type": "select",
            "options": ["no", "yes"],
            "default": "no",
            "field_fold": advanced_fold,
            "tooltip": "Spawn the full pool first, then arrange (useful to compare hitch).",
        },
        {
            "key": "include_consumables",
            "label": "Include ammo/cash",
            "type": "select",
            "options": ["no", "yes"],
            "default": "no",
            "field_fold": advanced_fold,
        },
    ]


def _max_all_option_fields() -> list[dict[str, Any]]:
    """Toggle what MAX ALL applies — all on by default."""
    return [
        {"key": "max_cash", "label": "Cash", "type": "checkbox", "default": True, "compact": True},
        {"key": "max_eridium", "label": "Eridium", "type": "checkbox", "default": True, "compact": True},
        {"key": "max_sdu", "label": "SDU", "type": "checkbox", "default": True, "compact": True},
        {"key": "max_vault_cards", "label": "Vault 1–4", "type": "checkbox", "default": True, "compact": True},
        {"key": "max_player_level", "label": "Level 70", "type": "checkbox", "default": True, "compact": True},
        {"key": "max_spec_level", "label": "Spec 701", "type": "checkbox", "default": True, "compact": True},
    ]


def _action(
    label: str,
    action: str,
    *,
    payload: dict[str, Any] | None = None,
    fields: list[dict[str, Any]] | None = None,
    confirm: str = "",
    tooltip: str = "",
    note_before: str = "",
    note_link_label: str = "",
    note_link_url: str = "",
    note_after: str = "",
    deliver_multiselect: bool = False,
    deliver_from_paste: bool = False,
    deliver_store: bool = False,
    spawn_multiselect: bool = False,
    challenge_multiselect: bool = False,
    backpack_multiselect: bool = False,
    showResult: bool = False,
    fold: str = "",
    fold_hint: str = "",
    full_width: bool = False,
) -> dict[str, Any]:
    row: dict[str, Any] = {"label": label, "action": action}
    if payload:
        row["payload"] = payload
    if fields:
        row["fields"] = fields
    if confirm:
        row["confirm"] = confirm
    if tooltip:
        row["tooltip"] = tooltip
    if note_before or note_after or note_link_url:
        row["note"] = {
            "before": note_before,
            "linkLabel": note_link_label,
            "linkUrl": note_link_url,
            "after": note_after,
        }
    if deliver_multiselect:
        row["deliverMultiselect"] = True
    if deliver_from_paste:
        row["deliverFromPaste"] = True
    if deliver_store:
        row["deliverStore"] = True
    if spawn_multiselect:
        row["spawnMultiselect"] = True
    if challenge_multiselect:
        row["challengeMultiselect"] = True
    if backpack_multiselect:
        row["backpackMultiselect"] = True
    if showResult:
        row["showResult"] = True
    if fold:
        row["fold"] = fold
    if fold_hint:
        row["foldHint"] = fold_hint
    if full_width:
        row["fullWidth"] = True
    return row


def _fly_speed_mode_field() -> dict[str, Any]:
    return {
        "key": "fly_speed_mode",
        "label": "1) Speed source",
        "type": "select",
        "options": ["preset", "custom"],
        "option_labels": {
            "preset": "Pick a preset (recommended)",
            "custom": "Type my own number",
        },
        "default": "preset",
    }


def _fly_preset_field() -> dict[str, Any]:
    return {
        "key": "fly_preset",
        "label": "2a) Preset speed",
        "type": "select",
        "options": ["cruise", "fast"],
        "option_labels": {
            "cruise": "Cruise — walk/jog (750)",
            "fast": "Fast — travel (5,500)",
        },
        "default": "fast",
    }


def _fly_speed_field() -> dict[str, Any]:
    return {
        "key": "fly_speed",
        "label": "2b) Your speed number",
        "type": "number",
        "default": 10000,
        "min": 300,
        "max": 500000,
        "step": 500,
    }


def _fly_control_fields() -> list[dict[str, Any]]:
    return [_fly_speed_mode_field(), _fly_preset_field(), _fly_speed_field()]


def _toggle(
    label: str,
    action: str,
    *,
    payload_on: dict[str, Any],
    payload_off: dict[str, Any],
    fields: list[dict[str, Any]] | None = None,
    tooltip: str = "",
    default_on: bool = False,
    sticky: bool = False,
    sync_key: str = "",
) -> dict[str, Any]:
    """Single on/off control — EXE flips color/label instead of two buttons."""
    row: dict[str, Any] = {
        "label": label,
        "action": action,
        "type": "toggle",
        "payloadOn": dict(payload_on),
        "payloadOff": dict(payload_off),
        "defaultOn": bool(default_on),
    }
    if fields:
        row["fields"] = fields
    if tooltip:
        row["tooltip"] = tooltip
    if sticky:
        row["sticky"] = True
    if sync_key:
        row["syncKey"] = str(sync_key)
    return row


def _gzo_multiselect_section() -> dict[str, Any]:
    return {
        "title": "GZO catalog",
        "hint": (
            "GZO codes from save-editor.be. Thank you to Tobgun for feedback, ideas, testing, and bug reports. "
            "How to send: Select all filtered (or tick rows) → set Send to → Deliver selected. "
            "Open rewards on send opens only this delivery's mail automatically in the background (one package at a time). "
            f"{_OPEN_REWARDS_LARGE_WARNING} Every selected row is one mail item. "
            "Host must run the EXE while in-game. Empty list → Refresh GZO (needs network). "
            "Use Item category (Weapons / Shields / Class Mods / …) then Item type (Pistol, SMG, …). "
            "★ pins favourites to the top (shared with in-game)."
        ),
        "catalog": "gzo",
        "multiselect": {
            "catalog": "gzo",
            "kind": "serial",
            "valueKey": "serial",
            "labelKey": "title",
            # Serial is unique; title/id collisions were breaking checkbox selection.
            "idKey": "serial",
            "levelOverride": True,
            "refreshAction": "gzo_refresh_start",
            "refreshStatusAction": "gzo_refresh_status",
            "refreshLabel": "Refresh GZO",
            "filters": [
                {
                    "key": "listing",
                    "label": "Listing",
                    "type": "select",
                    "options": ["All", "Legit", "Modded"],
                    "default": "All",
                    "catalogParam": "listing",
                },
                {
                    "key": "category",
                    "label": "Item category",
                    "type": "select",
                    "options": [
                        "All",
                        "Weapons",
                        "Shields",
                        "Ordnance",
                        "Class Mods",
                        "Enhancements",
                        "Repkits",
                        "Other",
                    ],
                    "default": "All",
                    "catalogParam": "category",
                },
                {
                    "key": "type",
                    "label": "Item type",
                    "type": "select",
                    "options": [
                        "All",
                        "Pistol",
                        "SMG",
                        "Shotgun",
                        "Assault Rifle",
                        "Sniper",
                        "Heavy Weapon",
                        "Shield",
                        "Gadget",
                        "Grenade",
                        "Repkit",
                        "Enhancement",
                        "Classmod",
                    ],
                    "default": "All",
                    "catalogParam": "type",
                },
                {
                    "key": "manufacturer",
                    "label": "Manufacturer",
                    "type": "select",
                    "options": ["All"],
                    "default": "All",
                    "catalogParam": "manufacturer",
                },
            ],
        },
        "actions": [
            _action(
                "Deliver selected",
                "deliver_serials",
                payload={"mode": "player"},
                deliver_multiselect=True,
                tooltip="Tick rows above, pick Send to, then deliver. Uses the Send to dropdown (not only Boost target).",
            ),
        ],
    }


def _lootlemon_multiselect_section(lootlemon_categories: list[str]) -> dict[str, Any]:
    return {
        "title": "Lootlemon catalog",
        "hint": (
            "How to send: Select all filtered (or tick rows) → set Send to → Deliver selected. "
            "Open rewards opens only mail from this delivery (default No). "
            f"{_OPEN_REWARDS_LARGE_WARNING} "
            "Empty/stale list → Refresh Lootlemon (can take a few minutes). "
            "★ pins favourites to the top (shared with in-game)."
        ),
        "catalog": "lootlemon",
        "multiselect": {
            "catalog": "lootlemon",
            "kind": "serial",
            "valueKey": "serial",
            "labelKey": "title",
            "idKey": "serial",
            "levelOverride": True,
            "refreshAction": "lootlemon_refresh_start",
            "refreshStatusAction": "lootlemon_refresh_status",
            "refreshLabel": "Refresh Lootlemon",
            "filters": [
                {
                    "key": "category",
                    "label": "Category",
                    "type": "select",
                    "options": lootlemon_categories,
                    "default": "All",
                    "catalogParam": "category",
                }
            ],
        },
        "actions": [
            _action(
                "Deliver selected",
                "deliver_serials",
                payload={"mode": "player"},
                deliver_multiselect=True,
                tooltip="Tick rows above, pick Send to, then deliver.",
            ),
        ],
    }


def _serial_store_section() -> dict[str, Any]:
    return {
        "title": "My Library",
        "catalog": "serial_store",
        "serialStore": True,
        "actions": [
            _action(
                "Deliver selected",
                "deliver_serials",
                payload={"mode": "player"},
                deliver_store=True,
                tooltip="Tick saved rows, pick Send to, then deliver.",
            ),
            _action("Save entry", "serial_store_save", fold="Library tools"),
            _action("Duplicate entry", "serial_store_duplicate", fold="Library tools"),
            _action(
                "Delete selected",
                "serial_store_delete",
                fold="Library tools",
            ),
        ],
    }


def _loot_text_section() -> dict[str, Any]:
    """Spell words with shinies / pool loot — lives on Loot (and Loot Shapes)."""
    return {
        "title": "Loot text",
        "featured": True,
        "aura": "loot-text",
        "hint": (
            "Spell up to 3 lines with denser loot lettering (shinies or a pool). "
            "Settle = Slow rains each gun into place as it spawns. "
            "Stop drop (Loot Shapes tab) snaps mid-air guns onto slots. Host + in-world — not mail."
        ),
        "actions": [
            _action(
                "Spawn loot text",
                "spawn_text_shape",
                full_width=True,
                fields=[
                    {
                        "key": "row1",
                        "label": "Line 1",
                        "type": "text",
                        "default": "MODS",
                        "wide": True,
                    },
                    {
                        "key": "row2",
                        "label": "Line 2",
                        "type": "text",
                        "default": "ARE",
                        "wide": True,
                    },
                    {
                        "key": "row3",
                        "label": "Line 3",
                        "type": "text",
                        "default": "FREE",
                        "wide": True,
                    },
                    {
                        "key": "source",
                        "label": "Fill with",
                        "type": "select",
                        "options": ["shiny", "pool"],
                        "option_labels": {
                            "shiny": "Shinies",
                            "pool": "Loot pool",
                        },
                        "default": "shiny",
                    },
                    {
                        "key": "itempool",
                        "label": "Pool id (only if Fill with = Loot pool)",
                        "type": "text",
                        "default": "itempool_ar_05_legendary",
                        "wide": True,
                        "placeholder": "itempool_ar_05_legendary",
                    },
                    _num_field("distance", "Distance", 640, min_v=200, max_v=2000, step=20),
                    _num_field("height", "Height", 670, min_v=40, max_v=800, step=10),
                    _num_field("spacing", "Spacing", 56, min_v=28, max_v=120, step=2),
                    _num_field("scale", "Scale", 1.0, min_v=0.35, max_v=2.5, step=0.05),
                    _settle_select_field(default="slow"),
                    *_air_hold_fields(),
                    _num_field("level", "Item level", _DEFAULT_ITEM_LEVEL, min_v=1, max_v=70, step=1),
                ],
            ),
        ],
    }

def get_panel_manifest() -> dict[str, Any]:
    from .loot_shapes import land_layout_defaults

    currency_kinds = ["cash", "eridium", "vaultcard_1", "vaultcard_2", "vaultcard_3", "vaultcard_4"]
    exp_tracks = [
        "player",
        "specialization",
        "vaultcard_xp_1",
        "vaultcard_xp_2",
        "vaultcard_xp_3",
        "vaultcard_xp_4",
    ]
    pool_categories = [
        "All",
        "Assault Rifle",
        "Pistol",
        "SMG",
        "Sniper",
        "Shotgun",
        "Heavy",
        "Class Mod",
        "Enhancement",
        "Shield",
        "Ordnance",
        "Repkit",
        "Pearl",
        "Shiny",
        "Other",
    ]
    lootlemon_categories = [
        "All",
        "Weapons",
        "Shields",
        "Ordnance",
        "Repkits",
        "Class Mods",
        "Enhancements",
    ]
    spawn_mix_categories = ["All", *world_spawn.categories()]
    io_categories = _io_categories()
    return {
        "name": "Squ1ggs Boosting Tools",
        "author": "RDPSqu1ggs",
        "version": __version__,
        "safety_banner": _BOOST_SAFETY_DANGER,
        "land_layout_defaults": {
            "shiny": land_layout_defaults("shiny"),
            "bulk": land_layout_defaults("bulk"),
        },
        "tabs": [
            {
                "id": "home",
                "label": TAB_LABELS[0],
                "short": TAB_SHORT_LABELS[0],
                "sections": [
                    {
                        "title": "Before you boost",
                        "danger": _BOOST_SAFETY_DANGER,
                    },
                    {
                        "title": "What's new",
                        "whats_new": list(HOME_WHATS_NEW),
                        "whats_new_collapsible": True,
                    },
                    {
                        "title": "Start here",
                        "featured": True,
                        "warning": (
                            "First use: set your Borderlands 4 install folder in Setup if needed, install oak2 once, "
                            "fully restart the game, load a character, then wait for Online. "
                            "Later EXE launches auto-copy the Squ1ggs mod. "
                            "Other tools: github.com/Squ1ggs/Bl4SDKmods · save editor scooterstoolbox.com"
                        ),
                        "guide": [
                            "If the game is on another drive, Setup → Set install folder (folder with Borderlands4.exe / OakGame).",
                            "Install SDK + Squ1ggs mod once if oak2 is missing.",
                            "Fully restart Borderlands 4 — quit to desktop, then launch again.",
                            "Load a character, then wait for Online (this card hides once connected).",
                        ],
                    },
                    {
                        "title": "Most used",
                        "featured": True,
                        "hint": (
                            "Daily one-taps for the boost target. MAX ALL checkboxes pick "
                            "cash, eridium, SDU, vault cards, level 70, spec 701. "
                            "Vault cards / SDU alone are under Economy below."
                        ),
                        "actions": [
                            _action(
                                "Run MAX ALL",
                                "max_all",
                                fields=_max_all_option_fields(),
                                tooltip=(
                                    "Apply checked options for the boost target: cash, eridium, "
                                    "SDU, vault cards 1–4 (+ XP tracks), player 70, spec 701."
                                ),
                            ),
                            _action("Unlock all cosmetics", "devperk_activate", payload={"perk_index": 4}),
                            _action(
                                "Open pending rewards (everyone)",
                                "rewards_open_everyone",
                                confirm=(
                                    "Open every pending Reward Center package for all live party members? "
                                    "Packages open in the background — stay in-world until the progress line finishes."
                                ),
                                tooltip="Open every pending Reward Center package for all live party players using Squ1ggs Boosting Tools.",
                            ),
                            _action("God mode (toggle)", "devperk_activate", payload={"perk_index": 6}),
                            _action("Kill all enemies", "kill_all_enemies"),
                            _action("Spawn legendary/epic loot", "devperk_activate", payload={"perk_index": 7}),
                            _toggle(
                                "Infinite jump",
                                "mobility_infinite_jump",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                                sticky=True,
                                sync_key="infinite_jump",
                            ),
                            _toggle(
                                "Force fly",
                                "mobility_force_fly",
                                payload_on={"enabled": True, "scope": "target"},
                                payload_off={"enabled": False, "scope": "target"},
                                sticky=True,
                                sync_key="force_fly",
                                tooltip=(
                                    "Turn force fly ON for the boost target. "
                                    "Set Cruise/Fast under **Mobility → Movement toggles** "
                                    "(Apply fly speed) before or after."
                                ),
                            ),
                            _toggle(
                                "Shoot while sprinting",
                                "character_flag",
                                payload_on={"flag": "shoot_sprint", "enabled": True},
                                payload_off={"flag": "shoot_sprint", "enabled": False},
                                sticky=True,
                                sync_key="shoot_sprint",
                            ),
                            _toggle(
                                "Zoom while sprinting",
                                "character_flag",
                                payload_on={"flag": "zoom_sprint", "enabled": True},
                                payload_off={"flag": "zoom_sprint", "enabled": False},
                                sticky=True,
                                sync_key="zoom_sprint",
                            ),
                            _toggle(
                                "Zoom while downed",
                                "character_flag",
                                payload_on={"flag": "zoom_injured", "enabled": True},
                                payload_off={"flag": "zoom_injured", "enabled": False},
                                sticky=True,
                                sync_key="zoom_injured",
                            ),
                            _toggle(
                                "Hide map fog (this session)",
                                "map_fog_hide",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                                sticky=True,
                                sync_key="map_fog",
                            ),
                            _action("Toggle freecam", "freecam_toggle"),
                            _action("Freecam OFF if stuck", "freecam_disable"),
                            _action(
                                "Spawn golden chest",
                                "spawn_ios",
                                payload={
                                    "cmds": ["oak_spawnai Lootable_GoldenChest"],
                                    "count": 1,
                                    "activate": "yes",
                                },
                            ),
                            _action("Open golden chest", "golden_chest", payload={"action": "open"}),
                            _action("Close golden chest", "golden_chest", payload={"action": "close"}),
                            _action(
                                "Spawn black market machine",
                                "black_market",
                                payload={"action": "spawn"},
                            ),
                            _action("Reward all shinies — target player", "shiny_mail_all", payload={"mode": "selected"}),
                            _action("Reward all shinies — entire lobby", "shiny_mail_all", payload={"mode": "all"}),
                            _action(
                                "Drop backpack",
                                "faafo_drop_backpack",
                                confirm="Spill the target's whole backpack onto the ground?",
                                tooltip="Quick spill at feet. Pick a shape on Loot → Drop backpack → shape.",
                            ),
                            _action(
                                "Drop all shinies (world loot)",
                                "shiny_drop_all",
                                tooltip=_SHINY_DROP_TOOLTIP,
                                note_before=_SHINY_NOTE_BEFORE,
                                note_link_label="Scooter's Toolbox",
                                note_link_url="https://scooterstoolbox.com",
                                note_after=_SHINY_NOTE_AFTER,
                                fields=[
                                    {"key": "level", "label": "Item level", "type": "number", "default": _DEFAULT_ITEM_LEVEL},
                                    *_world_drop_location_fields(),
                                    *_shiny_land_fields(),
                                ],
                            ),
                        ],
                    },
                    {
                        "title": "Jump to",
                        "featured": True,
                        "hint": "Shortcuts into the tabs that hold the rest of the toolkit.",
                        "quickLinks": [
                            {"label": "Send serials (paste & deliver)", "tab": "serials"},
                            {"label": "Progress / UVHM / challenges", "tab": "progression"},
                            {"label": "Mobility / fly / sprint", "tab": "mobility"},
                            {"label": "Loot pools / drop backpack shape", "tab": "loot"},
                            {"label": "World / fog / golden chest", "tab": "world"},
                            {"label": "F.A.A.F.O. / drop backpack", "tab": "faafo"},
                            {"label": "Player / freecam / teleports", "tab": "player"},
                            {"label": "Mob & IO spawner", "tab": "mob_io"},
                        ],
                    },
                    {
                        "title": "Black market",
                        "featured": True,
                        "hint": "Spawn a shop, clear the buy timer, or reroll stock.",
                        "actions": [
                            _action(
                                "Spawn black market machine",
                                "black_market",
                                payload={"action": "spawn"},
                            ),
                            _action(
                                "Clear purchase cooldown",
                                "black_market",
                                payload={"action": "cooldown"},
                                tooltip="Clear the buy timer and refresh the nearby shop.",
                            ),
                            _action(
                                "Reroll BM stock",
                                "black_market",
                                payload={"action": "reroll"},
                                tooltip="Reroll stock and refresh the nearby shop.",
                            ),
                            _action("Black market status", "black_market", payload={"action": "status"}),
                        ],
                    },
                    {
                        "title": "Economy",
                        "featured": True,
                        "hint": "Use Boost target = All players to boost everyone. MAX ALL (Home) includes vault cards + SDU.",
                        "actions": [
                            _action("Max cash", "max_cash"),
                            _action("Max eridium", "max_eridium"),
                            _action("Player level 70", "give_experience", payload={"track": "player", "level": 70}),
                            _action("Spec level 701", "give_experience", payload={"track": "specialization", "level": 701}),
                            _action("Max SDU", "max_sdu"),
                            _action("Delivery status", "serial_delivery_status"),
                            _action(
                                "Give currency",
                                "give_currency",
                                fields=[
                                    {"key": "kind", "type": "select", "options": currency_kinds, "default": "cash"},
                                    {"key": "amount", "type": "number", "default": 100000},
                                    {"key": "mode", "type": "select", "options": ["delta", "absolute"], "default": "delta"},
                                ],
                            ),
                            _action(
                                "Set experience",
                                "give_experience",
                                fields=[
                                    {"key": "track", "type": "select", "options": exp_tracks, "default": "player"},
                                    {"key": "level", "type": "number", "default": 70},
                                ],
                            ),
                            _action(
                                "Backpack / bank sizes",
                                "inventory_set_sizes",
                                fields=[
                                    {"key": "backpack_size", "type": "number", "default": 500},
                                    {"key": "bank_size", "type": "number", "default": 500},
                                ],
                            ),
                        ],
                    },
                    {
                        "title": "Party host",
                        "featured": True,
                        "actions": [
                            _action("Refresh party roster", "party_refresh"),
                            _action(
                                "Kick player",
                                "party_kick",
                                fields=[
                                    {
                                        "key": "player_index",
                                        "label": "Player",
                                        "type": "player_select",
                                        "default": "",
                                        "includeAll": False,
                                    },
                                    {
                                        "key": "reason",
                                        "label": "Kick reason",
                                        "type": "text",
                                        "default": "Squ1ggs Boosting Tools",
                                    },
                                ],
                            ),
                        ],
                    },
                ],
            },
            {
                "id": "player",
                "label": TAB_LABELS[1],
                "short": TAB_SHORT_LABELS[1],
                "sections": [
                    {
                        "title": "Combat cheats",
                        "actions": [
                            _action("God mode (toggle)", "devperk_activate", payload={"perk_index": 6}),
                            _action("Kill all enemies", "kill_all_enemies"),
                            _action("Infinite ammo (toggle)", "devperk_activate", payload={"perk_index": 5}),
                            _action("Spawn legendary/epic loot", "devperk_activate", payload={"perk_index": 7}),
                            _action("Give 1M cash", "devperk_activate", payload={"perk_index": 1}),
                            _action("Give 100k eridium", "devperk_activate", payload={"perk_index": 2}),
                            _action("Give experience", "devperk_activate", payload={"perk_index": 0}),
                            _action("Unlock all cosmetics", "devperk_activate", payload={"perk_index": 4}),
                        ],
                    },
                    {
                        "title": "Local cheats",
                        "actions": [
                            _toggle(
                                "No target",
                                "pawn_no_target",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                            ),
                            _action("Low gravity", "pawn_gravity", payload={"scale": 0.35}),
                            _action("Normal gravity", "pawn_gravity", payload={"scale": 1.0}),
                            _toggle(
                                "Force fly",
                                "mobility_force_fly",
                                payload_on={"enabled": True, "scope": "target"},
                                payload_off={"enabled": False, "scope": "target"},
                                sticky=True,
                                sync_key="force_fly",
                                tooltip=(
                                    "Sticky on/off for the boost target. "
                                    "Cruise / Fast + Apply fly speed live under **Mobility**."
                                ),
                            ),
                            _toggle(
                                "Infinite jump",
                                "mobility_infinite_jump",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                                sticky=True,
                                sync_key="infinite_jump",
                                tooltip="Sticky: stays highlighted while it is on. Starts off on a new install.",
                            ),
                        ],
                    },
                    {
                        "title": "Weapon / vehicle locks",
                        "actions": [
                            _toggle(
                                "Weapons restricted",
                                "weapons_restricted",
                                payload_on={"restricted": True},
                                payload_off={"restricted": False},
                            ),
                            _toggle(
                                "Vehicle lock",
                                "vehicle_actions_locked",
                                payload_on={"locked": True},
                                payload_off={"locked": False},
                            ),
                            _toggle(
                                "Ammo regen x5",
                                "ammo_regen",
                                payload_on={"rate": 5.0},
                                payload_off={"rate": 0.0},
                            ),
                        ],
                    },
                    {
                        "title": "Freecam",
                        "actions": [
                            _action("Toggle freecam", "freecam_toggle"),
                            _action("Freecam OFF if stuck", "freecam_disable"),
                            _action("Pull target here", "freecam_pull_target"),
                            _action("Copy cam location", "freecam_copy_location"),
                            _action("Freecam speed 1x", "freecam_set_speed", payload={"speed": 1.0}),
                            _action("Freecam speed 5x", "freecam_set_speed", payload={"speed": 5.0}),
                            _action("Freecam speed 10x", "freecam_set_speed", payload={"speed": 10.0}),
                            _action(
                                "Set freecam speed",
                                "freecam_set_speed",
                                fields=[{"key": "speed", "type": "number", "default": 1.0}],
                            ),
                            _action(
                                "Set freecam distance",
                                "freecam_set_distance",
                                fields=[{"key": "distance", "type": "number", "default": 256.0}],
                            ),
                            _action("Inspect looked-at", "freecam_inspect_target"),
                            _action("Destroy looked-at", "freecam_destroy_target"),
                            _action(
                                "Damage looked-at",
                                "freecam_damage_target",
                                fields=[{"key": "amount", "type": "number", "default": 999999.0}],
                            ),
                        ],
                    },
                    {
                        "title": "Party teleport",
                        "actions": [
                            _action("Me → selected", "teleport_party", payload={"mode": "me_to_selected"}),
                            _action("Selected → me", "teleport_party", payload={"mode": "selected_to_me"}),
                        ],
                    },
                    {
                        "title": "Takedown mayhem",
                        "hint": (
                            "Sets Mayhem Rank on this character (skips first normal clear). "
                            "1+ unlocks Mayhem, 5+ unlocks Hardcore. Save + reload if the kiosk still says complete Normal first."
                        ),
                        "actions": [
                            _action(
                                "Unlock takedown mayhem",
                                "mayhem_level",
                                payload={"action": "unlock_cap"},
                                note_before=_MAYHEM_NOTE,
                                fields=[
                                    {
                                        "key": "level",
                                        "label": "Mayhem Rank (1+=Mayhem, 5+=Hardcore)",
                                        "type": "number",
                                        "default": 10,
                                    },
                                ],
                            ),
                        ],
                    },
                ],
            },
            {
                "id": "progression",
                "label": TAB_LABELS[2],
                "short": TAB_SHORT_LABELS[2],
                "sections": [
                    {
                        "title": "UVHM progression",
                        "hint": "Uses Boost target (player bar under the tabs). Start UVHM (target) needs one player — not All players.",
                        "fields": [_uvhm_max_rank_field()],
                        "actions": [
                            _action(
                                "Start UVHM (target)",
                                "uvhm_start",
                                confirm="Start UVHM for the Boost target player? This is not a loot spawn.",
                            ),
                            _action(
                                "Start UVHM (all lobby)",
                                "uvhm_start_all",
                                confirm="Run UVHM for entire lobby?",
                            ),
                            _action("Cancel UVHM", "uvhm_cancel"),
                            _action("Resume UVHM", "uvhm_resume"),
                            _action("UVHM status", "uvhm_status"),
                        ],
                    },
                    {
                        "title": "Challenge completion",
                        "hint": (
                            "Story challenge flags ticks Completemainstory / Completesidemissions achievement tokens. "
                            "That is not the same as finishing story in the mission log — dumps have no CompleteMission RPC. "
                            "Weapons = gun/grenade type challenges. Combat = shields/repairs/revive/cowbell combat. "
                            "Other catches leftovers. Use Boost target = All players to boost everyone."
                        ),
                        "warning": _CONSOLE_REWARDS_WARNING,
                        "actions": [
                            _action(
                                "Complete selected category",
                                "challenge_bulk_start",
                                fields=[
                                    {
                                        "key": "category",
                                        "label": "Challenge category",
                                        "type": "select",
                                        "options": _challenge_categories(),
                                        "default": "All non-UVHM",
                                    },
                                ],
                                confirm="Permanently complete selected challenges for the target player?",
                            ),
                            _action(
                                "Complete ALL non-UVHM",
                                "challenge_bulk_start",
                                payload={"category": "All non-UVHM"},
                                confirm="Complete every non-UVHM challenge (including Vault of the Damned) for the target player?",
                            ),
                            _action("Cancel challenge bulk", "challenge_bulk_cancel"),
                            _action("Refresh challenge progress", "challenge_bulk_status"),
                        ],
                    },
                    {
                        "title": "Complete one / selected challenges",
                        "hint": (
                            "Same singular picker as Challenge Ticker: filter by category, search, tick one or a few, "
                            "then complete only those."
                        ),
                        "warning": _CONSOLE_REWARDS_WARNING,
                        "catalog": "challenges",
                        "multiselect": {
                            "catalog": "challenges",
                            "kind": "challenge",
                            "valueKey": "token",
                            "labelKey": "title",
                            "idKey": "token",
                            "filters": [
                                {
                                    "key": "category",
                                    "label": "Category",
                                    "type": "select",
                                    "options": _challenge_categories(),
                                    "default": "All non-UVHM",
                                    "catalogParam": "category",
                                }
                            ],
                        },
                        "actions": [
                            _action(
                                "Complete selected challenge(s)",
                                "challenge_complete_selected",
                                challenge_multiselect=True,
                                confirm="Permanently complete only the ticked challenge(s) for the target player?",
                            ),
                        ],
                    },
                ],
            },
            {
                "id": "loot",
                "label": TAB_LABELS[3],
                "short": TAB_SHORT_LABELS[3],
                "sections": [
                    _item_pool_browser_section(pool_categories),
                    {
                        "title": "Shiny drops",
                        "hint": "World loot only — same Drop All Shinies as Home. Mail lives under Serials.",
                        "actions": [
                            _action(
                                "Drop all shinies (world loot)",
                                "shiny_drop_all",
                                tooltip=_SHINY_DROP_TOOLTIP,
                                note_before=_SHINY_NOTE_BEFORE,
                                note_link_label="Scooter's Toolbox",
                                note_link_url="https://scooterstoolbox.com",
                                note_after=_SHINY_NOTE_AFTER,
                                fields=[
                                    {"key": "level", "label": "Item level", "type": "number", "default": _DEFAULT_ITEM_LEVEL},
                                    *_world_drop_location_fields(),
                                    *_shiny_land_fields(),
                                ],
                            ),
                        ],
                    },
                    _loot_text_section(),
                    {
                        "title": "Drop backpack → shape",
                        "hint": (
                            "Spill the boost target's whole backpack as world loot, then catch into the "
                            "selected silhouette (same path as Drop All Shinies — never mail). Use type piles "
                            "or unique item piles when you want stacked piles instead of a wireframe."
                        ),
                        "actions": [
                            _action(
                                "Drop backpack → shape",
                                "faafo_drop_backpack",
                                confirm="Spill the target's whole backpack and arrange into the selected shape?",
                                fields=[*_shiny_land_fields()],
                                full_width=True,
                                tooltip=(
                                    "SpillOut dumps inventory to the ground; catch/settle pulls items onto "
                                    "shape slots. Works with car, house, type piles, unique piles, and co-op pins."
                                ),
                            ),
                        ],
                    },
                    {
                        "title": "Rarity drop weights",
                        "hint": (
                            "World drop weights. 100 is normal, 0 turns that rarity off. "
                            "Same sliders as the in-game rarity card."
                        ),
                        "layout": "fields_sidebar",
                        "actions": [
                            _action(
                                "Apply rarity weights",
                                "rarity_weights_set",
                                fields=[
                                    _num_field("common", "Common %", 100, min_v=0, max_v=100, step=5),
                                    _num_field("uncommon", "Uncommon %", 100, min_v=0, max_v=100, step=5),
                                    _num_field("rare", "Rare %", 100, min_v=0, max_v=100, step=5),
                                    _num_field("epic", "Epic %", 100, min_v=0, max_v=100, step=5),
                                    _num_field("legendary", "Legendary %", 100, min_v=0, max_v=100, step=5),
                                    _num_field("pearlescent", "Pearlescent %", 100, min_v=0, max_v=100, step=5),
                                ],
                            ),
                            _action("Legendary drops only", "rarity_weights_set", payload={"preset": "legendary"}),
                            _action("Pearlescent drops only", "rarity_weights_set", payload={"preset": "pearlescent"}),
                            _action("Reset rarity weights", "rarity_weights_set", payload={"preset": "reset"}),
                        ],
                    },
                ],
            },
            {
                "id": "serials",
                "label": TAB_LABELS[4],
                "short": TAB_SHORT_LABELS[4],
                "sections": [
                    {
                        "title": "Send serials",
                        "featured": True,
                        "hint": (
                            "Paste or Browse @Ug serials into the box (YAML/STBX ok), then Send items. "
                            "Browse fills the paste box — not the queue or My Library. "
                            "Add to library… saves the paste box under a name for later. "
                            "Optional queue is only for mixing sets. "
                            f"{_OPEN_REWARDS_LARGE_WARNING}"
                        ),
                        "warning": _REWARDS_AND_INVENTORY_WARNING,
                        "serialSendList": True,
                        "actions": [
                            _action(
                                "Send items",
                                "deliver_serials",
                                deliver_from_paste=True,
                                tooltip="Reads the paste box above — does not require Add to queue.",
                                fields=[
                                    {"key": "count", "label": "Amount per serial", "type": "number", "default": 1},
                                    {
                                        "key": "level_override",
                                        "label": "Rewrite item level",
                                        "type": "select",
                                        "options": ["no", "yes"],
                                        "default": "no",
                                    },
                                    {"key": "level", "label": "Item level", "type": "number", "default": _DEFAULT_ITEM_LEVEL},
                                    *_delivery_recipient_fields(),
                                ],
                            ),
                            _action(
                                "Deliver queued serials",
                                "deliver_serials",
                                deliver_multiselect=True,
                                fields=[
                                    {"key": "count", "label": "Amount per serial", "type": "number", "default": 1},
                                    {
                                        "key": "level_override",
                                        "label": "Rewrite item level",
                                        "type": "select",
                                        "options": ["no", "yes"],
                                        "default": "no",
                                    },
                                    {"key": "level", "label": "Item level", "type": "number", "default": _DEFAULT_ITEM_LEVEL},
                                    *_delivery_recipient_fields(),
                                ],
                            ),
                        ],
                    },
                    {
                        "title": "Serial tools",
                        "fold": "Expert: convert serials",
                        "hint": "Convert human ↔ @U. Optional rewrite changes the 4th header level (300, 0, 1, LEVEL| …).",
                        "actions": [
                            _action(
                                "Open pending rewards (everyone)",
                                "rewards_open_everyone",
                                confirm=(
                                    "Open every pending Reward Center package for all live party members? "
                                    "Packages open in the background — stay in-world until the progress line finishes."
                                ),
                                tooltip="Open every pending Reward Center package for all live party players using Squ1ggs Boosting Tools.",
                            ),
                            _action(
                                "Convert serial(s)",
                                "serial_convert",
                                fields=[
                                    {
                                        "key": "input",
                                        "type": "textarea",
                                        "default": "",
                                        "label": "Human or @U serial (one or more lines)",
                                        "placeholder": "300, 0, 1, 60| 2, 2002|| {9}",
                                    },
                                    {
                                        "key": "level_override",
                                        "label": "Rewrite item level",
                                        "type": "select",
                                        "options": ["no", "yes"],
                                        "default": "no",
                                    },
                                    {"key": "level", "label": "Item level", "type": "number", "default": _DEFAULT_ITEM_LEVEL},
                                ],
                                showResult=True,
                            ),
                        ],
                    },
                    _gzo_multiselect_section(),
                    _lootlemon_multiselect_section(lootlemon_categories),
                    _serial_store_section(),
                    {
                        "title": "Shiny mail",
                        "hint": "Mailbox only. World shiny drops live under Loot.",
                        "actions": [
                            _action("Reward all shinies — target player", "shiny_mail_all", payload={"mode": "selected"}),
                            _action("Reward all shinies — entire lobby", "shiny_mail_all", payload={"mode": "all"}),
                        ],
                    },
                ],
            },
            {
                "id": "backpack",
                "label": TAB_LABELS[5],
                "short": TAB_SHORT_LABELS[5],
                "sections": [
                    {
                        "title": "Backpack scan & relevel",
                        "featured": True,
                        "hint": (
                            "Reads the Boost target's backpack only when you open this tab or press Refresh. "
                            "Tick gear, pick a new level, then relevel — decodes @U, rewrites level, swaps in-place."
                        ),
                        "warning": _REWARDS_AND_INVENTORY_WARNING,
                        "multiselect": {
                            "catalog": "backpack",
                            "kind": "backpack",
                            "valueKey": "slot",
                            "labelKey": "title",
                            "idKey": "id",
                        },
                        "actions": [
                            _action(
                                "Refresh backpack list",
                                "backpack_scan_status",
                                tooltip="Rescan the Boost target's backpack for @U serials.",
                            ),
                            _action(
                                "Relevel selected",
                                "backpack_relevel_selected",
                                backpack_multiselect=True,
                                confirm=(
                                    "Rewrite level on every ticked backpack item for the Boost target? "
                                    "Works best in solo with room in the pack."
                                ),
                                fields=[
                                    {
                                        "key": "level",
                                        "label": "New item level",
                                        "type": "number",
                                        "default": _DEFAULT_ITEM_LEVEL,
                                        "min": 1,
                                        "max": 100,
                                    },
                                ],
                            ),
                        ],
                    },
                ],
            },
            {
                "id": "mobility",
                "label": TAB_LABELS[6],
                "short": TAB_SHORT_LABELS[6],
                "sections": [
                    {
                        "title": "Movement tuning",
                        "layout": "fields_sidebar",
                        "actions": [
                            _action(
                                "Apply mobility settings",
                                "mobility_apply",
                                fields=_mobility_slider_fields(),
                            ),
                            _action("Fast preset", "mobility_preset_apply", payload={"preset": "fast"}),
                            _action("Moon preset", "mobility_preset_apply", payload={"preset": "moon"}),
                            _action("Wall walk preset", "mobility_preset_apply", payload={"preset": "wall_walk"}),
                            _action("Reset mobility", "mobility_preset_apply", payload={"preset": "reset"}),
                            _action("Zero vault now", "mobility_zero_vault"),
                            _action("Save current preset", "mobility_save_preset"),
                            _action("Load saved preset", "mobility_load_preset", payload={"apply_now": True}),
                            _action("Refresh current values", "mobility_status"),
                        ],
                    },
                    {
                        "title": "Time and utility",
                        "actions": [
                            _action(
                                "Set time dilation",
                                "mobility_time",
                                fields=[{"key": "dilation", "label": "Time dilation", "type": "number", "default": 1.0}],
                            ),
                            _action("Reset time dilation", "mobility_time", payload={"reset": True}),
                            _toggle(
                                "Noclip",
                                "mobility_noclip",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                                sticky=True,
                                sync_key="noclip",
                                tooltip=(
                                    "Collision off for flying through walls. Auto-enables Force fly "
                                    "so you do not freefall. Use FAAFO → Fall through map to drop through floors."
                                ),
                            ),
                            _action("Toggle players-only", "mobility_players_only"),
                            _action("Toggle no-target", "mobility_toggle_no_target"),
                            _action("Delete ground loot", "mobility_delete_ground"),
                            _toggle(
                                "Auto-apply on load",
                                "mobility_auto_apply",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                                sticky=True,
                                sync_key="auto_apply",
                            ),
                        ],
                    },
                    {
                        "title": "Movement toggles",
                        "hint": (
                            "How to fly: 1) Pick Cruise / Fast (or Custom)  "
                            "2) Press Apply fly speed  3) Turn Force fly ON  4) Hold WASD. "
                            "Jump = up, Crouch = down (look pitch no longer steers vertical). "
                            "Cruise is walk/jog (~750); Fast for travel. "
                            "Custom numbers go up to 500,000. "
                            "Home → Most used has a quick Force fly toggle — speed stays here."
                        ),
                        "fields": _fly_control_fields(),
                        "actions": [
                            _action(
                                "Apply fly speed",
                                "mobility_force_fly",
                                payload={"apply_speed_only": True},
                                full_width=True,
                                tooltip="Sets the speed number first. Does not turn fly on/off.",
                            ),
                            _toggle(
                                "Infinite jump (target)",
                                "mobility_infinite_jump",
                                payload_on={"enabled": True, "scope": "target"},
                                payload_off={"enabled": False, "scope": "target"},
                                sticky=True,
                                sync_key="infinite_jump",
                            ),
                            _toggle(
                                "Infinite jump (all)",
                                "mobility_infinite_jump",
                                payload_on={"enabled": True, "scope": "all"},
                                payload_off={"enabled": False, "scope": "all"},
                                sticky=True,
                                sync_key="infinite_jump_all",
                            ),
                            _toggle(
                                "Force fly (target)",
                                "mobility_force_fly",
                                payload_on={"enabled": True, "scope": "target"},
                                payload_off={"enabled": False, "scope": "target"},
                                sticky=True,
                                sync_key="force_fly",
                                tooltip=(
                                    "Host-authoritative fly for the Boost target. "
                                    "Local: kinematic WASD fly. Party member: cheat fly on their pawn "
                                    "(they move with their own input)."
                                ),
                            ),
                            _toggle(
                                "Force fly (all)",
                                "mobility_force_fly",
                                payload_on={"enabled": True, "scope": "all"},
                                payload_off={"enabled": False, "scope": "all"},
                                sticky=True,
                                sync_key="force_fly_all",
                                tooltip=(
                                    "Force fly for every live party member from the host panel "
                                    "(remotes use CheatManager fly — not host kinematic drive)."
                                ),
                            ),
                            _toggle(
                                "Shoot while sprinting",
                                "character_flag",
                                payload_on={"flag": "shoot_sprint", "enabled": True},
                                payload_off={"flag": "shoot_sprint", "enabled": False},
                                sticky=True,
                                sync_key="shoot_sprint",
                                tooltip="Fire while sprinting. Stays on for this session until you turn it off.",
                            ),
                            _toggle(
                                "Zoom while sprinting",
                                "character_flag",
                                payload_on={"flag": "zoom_sprint", "enabled": True},
                                payload_off={"flag": "zoom_sprint", "enabled": False},
                                sticky=True,
                                sync_key="zoom_sprint",
                                tooltip="ADS / zoom while sprinting. Stays on for this session until you turn it off.",
                            ),
                            _toggle(
                                "Zoom while downed",
                                "character_flag",
                                payload_on={"flag": "zoom_injured", "enabled": True},
                                payload_off={"flag": "zoom_injured", "enabled": False},
                                sticky=True,
                                sync_key="zoom_injured",
                                tooltip="ADS while in Fight For Your Life.",
                            ),
                        ],
                    },
                    {
                        "title": "On-foot tuning (BPM)",
                        "actions": [
                            _tuning_apply_action("Apply on-foot tuning", "bpm"),
                            _action("Reset on-foot tuning", "tuning_reset", payload={"module": "bpm"}),
                            _action("Fast preset", "tuning_preset", payload={"module": "bpm", "preset": "fast"}),
                            _action("Moon preset", "tuning_preset", payload={"module": "bpm", "preset": "moon"}),
                            _action("Glide up preset", "tuning_preset", payload={"module": "bpm", "preset": "glide_up"}),
                            _action("Load on-foot values", "tuning_status", payload={"module": "bpm"}),
                        ],
                    },
                    {
                        "title": "Party slot teleports",
                        "actions": [
                            _action(
                                "Me → party slot",
                                "teleport_party_slot",
                                fields=[_party_slot_field()],
                                payload={"mode": "me_to_slot"},
                            ),
                            _action(
                                "Party slot → me",
                                "teleport_party_slot",
                                fields=[_party_slot_field()],
                                payload={"mode": "slot_to_me"},
                            ),
                            _action(
                                "Selected → party slot",
                                "teleport_party_slot",
                                fields=[_party_slot_field()],
                                payload={"mode": "selected_to_slot"},
                            ),
                        ],
                    },
                ],
            },
            {
                "id": "vehicle",
                "label": TAB_LABELS[7],
                "short": TAB_SHORT_LABELS[7],
                "sections": [
                    {
                        "title": "Vehicle tuning",
                        "actions": [
                            _tuning_apply_action("Apply vehicle tuning", "bvm"),
                            _action("Reset vehicle movement", "tuning_reset", payload={"module": "bvm"}),
                            _action("Boost preset", "tuning_preset", payload={"module": "bvm", "preset": "boost"}),
                            _action("Drift preset", "tuning_preset", payload={"module": "bvm", "preset": "drift"}),
                            _action("Vehicle movement status", "tuning_status", payload={"module": "bvm"}),
                        ],
                    },
                    {
                        "title": "Vehicle jump",
                        "hint": (
                            "Unlimited jumps repeats Space / your vehicle jump key mid-air. "
                            "Jump height and gravity are the powerslide jump sliders under Apply vehicle tuning."
                        ),
                        "actions": [
                            _toggle(
                                "Unlimited vehicle jumps",
                                "bvm_vehicle_jump",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                                sticky=True,
                                sync_key="vehicle_jump",
                                fields=[
                                    {
                                        "key": "interval",
                                        "label": "Repeat jump cooldown (sec)",
                                        "type": "number",
                                        "default": 0.15,
                                        "min": 0.08,
                                        "max": 1,
                                        "step": 0.02,
                                    }
                                ],
                                tooltip="Sticky: highlighted while unlimited jumps is on. Starts off on a new install. Sit in a vehicle first.",
                            ),
                            _action(
                                "Test jump now",
                                "bvm_vehicle_jump",
                                payload={"action": "test"},
                                tooltip="Fires one vehicle jump using the current jump height slider.",
                            ),
                        ],
                    },
                    {
                        "title": "Spawn vehicle",
                        "catalog": "vehicle_spawns",
                        "actions": [
                            _action(
                                "Reload vehicle catalog",
                                "vehicle_spawn_catalog_reload",
                                payload={"deep": True},
                            ),
                            _action(
                                "Summon selected vehicle",
                                "vehicle_spawn",
                                fields=[
                                    {
                                        "key": "search",
                                        "label": "Search filter",
                                        "type": "text",
                                        "default": "",
                                        "placeholder": "Optional name filter",
                                    },
                                    {
                                        "key": "vehicle",
                                        "label": "Vehicle",
                                        "type": "catalog_select",
                                        "catalog": "vehicle_spawns",
                                        "valueKey": "vehicle",
                                        "labelKey": "title",
                                        "catalogParamsFrom": ["search"],
                                    },
                                ],
                            ),
                        ],
                    },
                ],
            },
            {
                "id": "damage",
                "label": TAB_LABELS[8],
                "short": TAB_SHORT_LABELS[8],
                "sections": [
                    {
                        "title": "Combat sliders",
                        "layout": "fields_sidebar",
                        "actions": [
                            _tuning_apply_action("Apply damage tuning", "bdam"),
                            _action("Reset damage tuning", "tuning_reset", payload={"module": "bdam"}),
                            _action("Damage tuning status", "tuning_status", payload={"module": "bdam"}),
                        ],
                    },
                ],
            },
            {
                "id": "resources",
                "label": TAB_LABELS[9],
                "short": TAB_SHORT_LABELS[9],
                "sections": [
                    {
                        "title": "Shield / repkit / recovery",
                        "layout": "fields_sidebar",
                        "actions": [
                            _tuning_apply_action("Apply kits & shields tuning", "brc"),
                            _action("Reset kits & shields tuning", "tuning_reset", payload={"module": "brc"}),
                            _action("Kits & shields status", "tuning_status", payload={"module": "brc"}),
                        ],
                    },
                ],
            },
            {
                "id": "world",
                "label": TAB_LABELS[10],
                "short": TAB_SHORT_LABELS[10],
                "sections": [
                    {
                        "title": "Fast travel",
                        "catalog": "travel_maps",
                        "hint": (
                            "Pick a map, then a station. You can travel to a station even if it is still locked on the map. "
                            "That sends you there; it does not unlock the pin for later."
                        ),
                        "actions": [
                            _action(
                                "Travel to map",
                                "travel_map",
                                fields=[
                                    {
                                        "key": "map",
                                        "label": "Map",
                                        "type": "catalog_select",
                                        "catalog": "travel_maps",
                                        "valueKey": "map",
                                        "labelKey": "display_name",
                                        "search": True,
                                    }
                                ],
                            ),
                            _action(
                                "Travel to station",
                                "travel_station",
                                fields=[
                                    {
                                        "key": "map",
                                        "label": "Map",
                                        "type": "catalog_select",
                                        "catalog": "travel_maps",
                                        "valueKey": "map",
                                        "labelKey": "display_name",
                                        "search": True,
                                        "catalogParam": "map",
                                    },
                                    {
                                        "key": "station",
                                        "label": "Fast travel station",
                                        "type": "catalog_select",
                                        "catalog": "travel_stations",
                                        "valueKey": "station",
                                        "labelKey": "display_name",
                                        "search": True,
                                        "catalogParamsFrom": ["map"],
                                    },
                                ],
                            ),
                            _action(
                                "Tuba Boss Arena",
                                "travel_preset",
                                payload={"preset": "tuba_boss_arena"},
                            ),
                            _action(
                                "Dev Testing Map",
                                "travel_preset",
                                payload={"preset": "dev_testing_map"},
                                confirm="Travel to bespoke_visionquest (Dev Testing Map)?",
                            ),
                        ],
                    },
                    {
                        "title": "Map fog",
                        "hint": (
                            "Hide map fog (this session) is the working overlay hide. "
                            "Open the map after turning it on. Fog comes back after reload. "
                            "It does not unlock safehouses or mark the world visited."
                        ),
                        "actions": [
                            _toggle(
                                "Hide map fog (this session)",
                                "map_fog_hide",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                                sticky=True,
                                sync_key="map_fog",
                                tooltip=(
                                    "Hides the map fog overlay while you play. Open the map after turning it on. "
                                    "Fog comes back after you reload."
                                ),
                            ),
                        ],
                    },
                    {
                        "title": "Golden chest",
                        "hint": "Spawn a golden chest at your feet, then open or close nearby chests.",
                        "featured": True,
                        "actions": [
                            _action(
                                "Spawn golden chest",
                                "spawn_ios",
                                payload={
                                    "cmds": ["oak_spawnai Lootable_GoldenChest"],
                                    "count": 1,
                                    "activate": "yes",
                                },
                                tooltip="Spawn a golden chest near you. Host / in-world.",
                            ),
                            _action("Open golden chest", "golden_chest", payload={"action": "open"}),
                            _action("Close golden chest", "golden_chest", payload={"action": "close"}),
                        ],
                    },
                    {
                        "title": "Travel / vehicle",
                        "hint": (
                            "Block fast travel from this character, cancel a travel countdown, "
                            "or allow personal vehicles in this world."
                        ),
                        "actions": [
                            _toggle(
                                "Block local fast travel",
                                "oak_travel",
                                payload_on={"action": "disallow_local", "enabled": True},
                                payload_off={"action": "disallow_local", "enabled": False},
                            ),
                            _action(
                                "Cancel travel countdown",
                                "oak_travel",
                                payload={"action": "cancel_countdown"},
                            ),
                            _toggle(
                                "Allow personal vehicles here",
                                "world_personal_vehicle",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                            ),
                        ],
                    },
                    {
                        "title": "World text (prop logo)",
                        "hint": (
                            "Spells text with world props (not floating UI). Default text MODS / ARE / FREE; "
                            "default actor electisafe. Heavy actors (goldenchest/IO/NPC) auto-cap at 256 props "
                            "so default text stays readable. Open golden chest opens logo letter chests in range."
                        ),
                        "actions": [
                            _action(
                                "Spawn world text",
                                "barrel_logo",
                                fields=[
                                    {
                                        "key": "row1",
                                        "label": "Line 1",
                                        "type": "text",
                                        "default": "MODS",
                                    },
                                    {
                                        "key": "row2",
                                        "label": "Line 2",
                                        "type": "text",
                                        "default": "ARE",
                                    },
                                    {
                                        "key": "row3",
                                        "label": "Line 3",
                                        "type": "text",
                                        "default": "FREE",
                                    },
                                    {
                                        "key": "actor",
                                        "label": "Actor (props → IO → NPCs)",
                                        "type": "select",
                                        "options": logo_actor_select_options(),
                                        "default": DEFAULT_LOGO_ACTOR,
                                    },
                                    {
                                        "key": "custom_actor",
                                        "label": "Custom actor / IO / Char_ (overrides dropdown)",
                                        "type": "text",
                                        "default": "",
                                        "placeholder": "e.g. IO_VendingMachine_Munitions or Char_NPC_Claptrap",
                                    },
                                    {"key": "distance", "label": "Distance", "type": "number", "default": 1400},
                                    {"key": "height", "label": "Height", "type": "number", "default": 750},
                                    {"key": "spacing", "label": "Spacing", "type": "number", "default": 70},
                                    {"key": "scale", "label": "Scale", "type": "number", "default": 0.45},
                                    {
                                        "key": "max_props",
                                        "label": "Max props (0 = auto 256 for heavy actors)",
                                        "type": "number",
                                        "default": 0,
                                    },
                                ],
                            ),
                            _action("Clear world text props", "barrel_logo_clear"),
                        ],
                    },
                ],
            },
            {
                "id": "mob_io",
                "label": TAB_LABELS[11],
                "short": TAB_SHORT_LABELS[11],
                "sections": [
                    {
                        "title": "Mix spawn groups",
                        "catalog": "spawn_mixes",
                        "actions": [
                            _action(
                                "Spawn mix",
                                "spawn_mix",
                                fields=[
                                    {
                                        "key": "category",
                                        "label": "Category",
                                        "type": "select",
                                        "options": spawn_mix_categories,
                                        "default": "All",
                                        "catalogParam": "category",
                                    },
                                    {
                                        "key": "mix_id",
                                        "label": "Mix group",
                                        "type": "catalog_select",
                                        "catalog": "spawn_mixes",
                                        "valueKey": "mix_id",
                                        "labelKey": "mix_id",
                                        "search": True,
                                        "catalogParamsFrom": ["category"],
                                    },
                                    *_bms_spawn_fields(),
                                ],
                            ),
                        ],
                    },
                    {
                        "title": "Mob spawner (Char_*)",
                        "hint": (
                            "Tick mobs, set Count, pick Spawn at, then Spawn selected. "
                            "Optional: open Wave packs below to queue several packs and spawn them one after another. "
                            "Actor spawn caps are raised automatically. Disable standalone bl4_mob_spawner / "
                            "bl4_oak_spawner to avoid conflicting hooks."
                        ),
                        "catalog": "mob_actors",
                        "multiselect": {
                            "catalog": "mob_actors",
                            "kind": "spawn",
                            "valueKey": "code",
                            "labelKey": "display_name",
                            "idKey": "code",
                            "filters": [
                                {
                                    "key": "section",
                                    "label": "Catalog section",
                                    "type": "select",
                                    "options": _MOB_SECTIONS,
                                    "default": "All",
                                    "catalogParam": "section",
                                }
                            ],
                        },
                        "actions": [
                            _action(
                                "Spawn selected",
                                "spawn_mobs",
                                fields=_bms_spawn_fields(),
                                spawn_multiselect=True,
                            ),
                            _action("Re-aggro tracked mobs", "bms_reaggro"),
                            _action("Clear tracked mobs", "bms_clear", confirm="Destroy all BMS-tracked spawns?"),
                            _action(
                                "Save ticked mobs as next wave",
                                "bms_group_add",
                                fields=[
                                    {"key": "count", "label": "Count per ticked Char_*", "type": "number", "default": 4},
                                ],
                                spawn_multiselect=True,
                                fold="Wave packs (optional)",
                                fold_hint=(
                                    "1) Tick mobs above. 2) Save them as a wave. 3) Repeat for more waves. "
                                    "4) Set when the next wave starts. 5) Press Start wave packs."
                                ),
                            ),
                            _action(
                                "Wave settings",
                                "bms_group_set_options",
                                fields=_bms_group_option_fields(),
                                fold="Wave packs (optional)",
                            ),
                            _action("Start wave packs", "bms_group_start", fold="Wave packs (optional)"),
                            _action("Stop wave packs", "bms_group_stop", fold="Wave packs (optional)"),
                            _action("Next wave now", "bms_group_next", fold="Wave packs (optional)"),
                            _action(
                                "Remove a wave",
                                "bms_group_remove",
                                fields=[
                                    {
                                        "key": "wave_index",
                                        "label": "Wave",
                                        "type": "catalog_select",
                                        "catalog": "bms_groups",
                                        "valueKey": "wave_index",
                                        "labelKey": "title",
                                        "search": True,
                                    }
                                ],
                                fold="Wave packs (optional)",
                            ),
                            _action(
                                "Clear wave list",
                                "bms_group_clear_plan",
                                confirm="Drop every saved wave from the list?",
                                fold="Wave packs (optional)",
                            ),
                            _action(
                                "Clear live wave mobs",
                                "bms_group_clear_live",
                                confirm="Destroy BMS-tracked spawns?",
                                fold="Wave packs (optional)",
                            ),
                            _action(
                                "Save wave list",
                                "bms_group_save",
                                fields=[{"key": "name", "label": "Name", "type": "text", "default": "", "placeholder": "My pack"}],
                                fold="Wave packs (optional)",
                            ),
                            _action(
                                "Load wave list",
                                "bms_group_load",
                                fields=[{"key": "name", "label": "Name", "type": "text", "default": ""}],
                                fold="Wave packs (optional)",
                            ),
                        ],
                    },
                    {
                        "title": "World IO spawns",
                        "catalog": "io_spawns",
                        "hint": (
                            "Tick IO objects and spawn selected. Maurice's Black Market auto-finishes after a short settle — "
                            "stay in-world a couple seconds so the machine can unlock."
                        ),
                        "warning": (
                            "If Maurice's Black Market looks blank, wait 2–3 seconds, "
                            "or spawn any other IO nearby once — that finishes setup. "
                            "Then use Activate last IO spawn if it still looks dead."
                        ),
                        "multiselect": {
                            "catalog": "io_spawns",
                            "kind": "spawn",
                            "valueKey": "cmd",
                            "labelKey": "label",
                            "idKey": "cmd",
                            "filters": [
                                {
                                    "key": "category",
                                    "label": "Category",
                                    "type": "select",
                                    "options": io_categories,
                                    "default": "All",
                                    "catalogParam": "category",
                                }
                            ],
                        },
                        "actions": [
                            _action(
                                "Spawn selected",
                                "spawn_ios",
                                fields=[
                                    {
                                        "key": "activate",
                                        "label": "Activate after spawn",
                                        "type": "select",
                                        "options": ["yes", "no"],
                                        "default": "yes",
                                    },
                                    *_io_spawn_fields(),
                                ],
                                spawn_multiselect=True,
                            ),
                            _action("Activate last IO spawn", "bms_activate_io"),
                        ],
                    },
                    {
                        "title": "Encounter presets",
                        "catalog": "encounter_presets",
                        "actions": [
                            _action(
                                "Run encounter preset",
                                "spawn_encounter",
                                fields=[
                                    {
                                        "key": "line",
                                        "label": "Encounter",
                                        "type": "catalog_select",
                                        "catalog": "encounter_presets",
                                        "valueKey": "line",
                                        "labelKey": "label",
                                        "search": True,
                                    },
                                    *_bms_spawn_fields(),
                                ],
                            ),
                        ],
                    },
                ],
            },
            {
                "id": "loot_shapes",
                "label": TAB_LABELS[12],
                "short": TAB_SHORT_LABELS[12],
                "sections": [
                    _loot_text_section(),
                    {
                        "title": "Place shape",
                        "featured": True,
                        "hint": (
                            "Shape + settle, then Place Fully. New shapes keep prior house/globe frozen. "
                            "Expand Layout tuning / More options for every size knob."
                        ),
                        "actions": [
                            _action(
                                "Place Fully",
                                "loot_shape_place_fully",
                                fields=_loot_layout_fields(),
                                full_width=True,
                            ),
                        ],
                    },
                    {
                        "title": "Adjust & cleanup",
                        "hint": "Re-run the same layout, cancel a drop animation, or soft-hide ground loot.",
                        "actions": [
                            _action(
                                "Quick Arrange",
                                "loot_shape_arrange",
                                fields=_loot_layout_fields(),
                                full_width=True,
                            ),
                            _action("Re-apply last layout", "loot_shape_reapply"),
                            _action(
                                "Stop drop (snap to slots)",
                                "loot_shape_stop_drop",
                                tooltip="Cancel an in-progress drop-from-above animation and place remaining items on their shape slots.",
                            ),
                            _action(
                                "Soft clear (hide loot)",
                                "loot_shape_clear",
                                confirm="Hide all ground loot far away?",
                            ),
                        ],
                    },
                ],
            },
            {
                "id": "faafo",
                "label": TAB_LABELS[13],
                "short": TAB_SHORT_LABELS[13],
                "sections": [
                    {
                        "title": "F.A.A.F.O.",
                        "hint": (
                            "Party-aware chaos tools for the current boost target(s). "
                            "Weapon/vehicle locks and mobility shortcuts are below."
                        ),
                        "featured": True,
                        "actions": [
                            _action(
                                "Empty backpack (delete)",
                                "faafo_empty_backpack",
                                confirm="DELETE the target's backpack contents?",
                            ),
                            _action("Force FFYL", "faafo_ffyl", confirm="Put target into Fight For Your Life?"),
                            _action("Kill / down", "faafo_kill", confirm="Force StartDownState(True) on target?"),
                            _action("Unlock look/move", "faafo_unlock"),
                            _toggle(
                                "Fall through map",
                                "faafo_fall_through_map",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                                sticky=True,
                                sync_key="fall_through_map",
                                tooltip=(
                                    "Boost target only: collision off + gravity on + Force fly off — they fall "
                                    "through floors. Not Mobility Noclip (that auto-enables fly on you)."
                                ),
                            ),
                        ],
                    },
                    {
                        "title": "Launch & locks",
                        "hint": "Skyward launch and timed look/move locks for the boost target.",
                        "featured": True,
                        "actions": [
                            _action(
                                "Launch skyward",
                                "faafo_launch",
                                fields=[{"key": "z", "label": "Z boost", "type": "number", "default": 5000}],
                                tooltip="Launch the boost target upward.",
                            ),
                            _action(
                                "Invert look",
                                "faafo_invert_look",
                                fields=[{"key": "seconds", "label": "Seconds", "type": "number", "default": 8}],
                            ),
                            _action(
                                "Lock look",
                                "faafo_lock_look",
                                fields=[{"key": "seconds", "label": "Seconds", "type": "number", "default": 5}],
                            ),
                            _action(
                                "Lock move",
                                "faafo_lock_move",
                                fields=[{"key": "seconds", "label": "Seconds", "type": "number", "default": 5}],
                            ),
                            _action(
                                "Lock look + move",
                                "faafo_lock_both",
                                fields=[{"key": "seconds", "label": "Seconds", "type": "number", "default": 5}],
                            ),
                        ],
                    },
                    {
                        "title": "Drop backpack",
                        "hint": (
                            "Spill the whole backpack to the ground. Use type piles or unique piles "
                            "under Shape when you want stacked piles instead of a silhouette."
                        ),
                        "actions": [
                            _action(
                                "Drop backpack",
                                "faafo_drop_backpack",
                                confirm="Spill the target's whole backpack onto the ground?",
                                fields=[*_shiny_land_fields()],
                                tooltip=(
                                    "Spills the whole backpack to the ground. Pick type piles (weapon/shield/…) "
                                    "or unique item piles (one pile per exact item) under Shape."
                                ),
                            ),
                        ],
                    },
                    {
                        "title": "Weapon / vehicle locks",
                        "hint": "Same toggles as Player — restrict firing or vehicle summon/use on boost targets.",
                        "featured": True,
                        "actions": [
                            _toggle(
                                "Weapons restricted",
                                "weapons_restricted",
                                payload_on={"restricted": True},
                                payload_off={"restricted": False},
                            ),
                            _toggle(
                                "Vehicle lock",
                                "vehicle_actions_locked",
                                payload_on={"locked": True},
                                payload_off={"locked": False},
                            ),
                            _toggle(
                                "Ammo regen x5",
                                "ammo_regen",
                                payload_on={"rate": 5.0},
                                payload_off={"rate": 0.0},
                            ),
                        ],
                    },
                    {
                        "title": "Also useful",
                        "hint": "Same actions as Player / Mobility — handy here when you're already in FAAFO mode.",
                        "featured": True,
                        "actions": [
                            _toggle(
                                "No target",
                                "pawn_no_target",
                                payload_on={"enabled": True},
                                payload_off={"enabled": False},
                            ),
                            _action("Kill all enemies", "kill_all_enemies"),
                            _action("Low gravity", "pawn_gravity", payload={"scale": 0.35}),
                            _action("Normal gravity", "pawn_gravity", payload={"scale": 1.0}),
                        ],
                    },
                ],
            },
            {
                "id": "keybinds",
                "label": TAB_LABELS[14],
                "short": TAB_SHORT_LABELS[14],
                "sections": [
                    {
                        "title": "Custom keybinds",
                        "hint": (
                            "Pick an action and a key for each slot. Binds fire in-game for the current "
                            "boost target. Keys also appear under Mods → Keybinds as SQBT Custom 1–12."
                        ),
                        "keybindsEditor": True,
                    },
                ],
            },
            {
                "id": "toggles",
                "label": TAB_LABELS[15],
                "short": TAB_SHORT_LABELS[15],
                "sections": [
                    {
                        "title": "Sticky toggles",
                        "togglesBoard": True,
                        "hint": (
                            "Live on/off for sticky boosts (fly, jump, noclip, shoot/zoom flags). "
                            "Turn them on from Home or Mobility — this tab only shows current state."
                        ),
                    },
                ],
            },
            {
                "id": "activity",
                "label": TAB_LABELS[16],
                "short": TAB_SHORT_LABELS[16],
                "sections": [
                    {
                        "title": "Support",
                        "kofiLink": "https://ko-fi.com/rdpsqu1ggs",
                        "discordLink": "https://discord.gg/DqetrAK2sJ",
                        "discordName": "ScootersGarage",
                        "discordQr": "assets/discord-invite-qr.svg",
                        "hint": "Join the community for updates, help, testing and new releases.",
                    },
                ],
            }
        ],
    }
