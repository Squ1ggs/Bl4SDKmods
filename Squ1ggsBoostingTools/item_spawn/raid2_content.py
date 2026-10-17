"""Canonical Raid 2 (Subjugator) filter for Item Spawner + Nexus Discovery."""

from __future__ import annotations

import re
from typing import Any, Mapping

# Spawnable inv_comp catalog keys — Mobalytics Subjugator / Vault Card 2 wave.
RAID2_SPAWN_HINTS: dict[str, dict[str, str]] = {
    "bor_sr_comp_05_legendary_abyss": {"serial_id": "pearl_abyss_element_override_jakobs_ripper"},
    "jak_ar_comp_05_legendary_gomie": {"serial_id": "pearl_gomie_elemental_override_jakobs_ripper"},
    "bor_sm_comp_05_legendary_jailbroken": {"serial_id": "jailbroken"},
    "tor_ar_comp_05_legendary_lockjaw": {"serial_id": "lockjaw"},
    "ord_sr_comp_05_legendary_temper": {"serial_id": "temper"},
    "vla_hw_comp_05_legendary_splatoon": {"serial_id": "flak"},
    "tor_ps_comp_06_pearl_herald": {"serial_id": "pearl_herald_ripper_torgue_pearl_override"},
    "mal_sm_comp_06_pearl_juliet": {
        "serial_id": "pearl_juliet_s_sparkle_element_elemental_override_jakobs_shotgun",
    },
    "jak_sg_comp_06_pearl_constable": {"serial_id": "pearl_looming_constable_element_override_jakobs"},
    "dad_sm_comp_06_pearl_screwed": {
        "serial_id": (
            "pearl_screwstonian_jakobs_shotgun_ammo_note_ammo_switch_not_visible_on_main_card_"
            "due_to_lack_of_space_see_detailed_view_for_full_specs"
        ),
    },
    "vla_sm_comp_06_pearl_locust": {
        "serial_id": "locust",
        "native_pool": "itempool_vla_sm_06_pearl_Locust",
    },
    "ted_sg_comp_06_pearl_sharkbait": {},
    "ord_shield_comp_05_legendary_collector": {"serial_id": "collector"},
    "classmod_dark_siren_comp_05_legendary_06": {"serial_id": "grim_sister"},
    "classmod_exo_soldier_comp_05_legendary_06": {"serial_id": "bombastic"},
    "classmod_gravitar_comp_05_legendary_06": {"serial_id": "plasmaphile"},
    "classmod_paladin_comp_05_legendary_06": {"serial_id": "artificer"},
    "classmod_robodealer_comp_05_legendary_06": {"serial_id": "prestidigitator"},
}

RAID2_CATALOG_KEYS: frozenset[str] = frozenset(RAID2_SPAWN_HINTS.keys())

RAID2_LEGENDARY_SUFFIXES: frozenset[str] = frozenset(
    {
        "abyss",
        "gomie",
        "jailbroken",
        "lockjaw",
        "temper",
        "splatoon",
        "herald",
        "juliet",
        "constable",
        "screwed",
        "locust",
        "collector",
        "grim_sister",
        "bombastic",
        "plasmaphile",
        "artificer",
        "prestidigitator",
    }
)

_COMP_SUFFIX_RE = re.compile(
    r"comp_0[56]_(?:legendary|pearl)_([a-z0-9_]+)",
    re.IGNORECASE,
)

# Live NCS shiny pools — only when the UI row explicitly targets shiny.
RAID2_SHINY_POOL_OVERRIDES: dict[str, str] = {
    "tor_ar_comp_05_legendary_lockjaw": "itempool_tor_ar_05_legendary_lockjaw_shiny",
    "bor_sm_comp_05_legendary_jailbroken": "itempool_mal_sg_05_legendary_jailbroken_shiny",
    "vla_sm_comp_06_pearl_locust": "itempool_vla_sm_06_pearl_Locust_shiny",
}

# Non-shiny NCS pools that exist outside merge synthetic rows.
RAID2_NATIVE_POOL_OVERRIDES: dict[str, str] = {
    "vla_hw_comp_05_legendary_splatoon": "itempool_vla_hw_05_legendary_splatoon",
    "vla_sm_comp_06_pearl_locust": "itempool_vla_sm_06_pearl_Locust",
}

# Discovery tooling only — do not use for default world spawn (shiny is opt-in).
RAID2_PRIMARY_POOL_OVERRIDES: dict[str, str] = {
    **RAID2_NATIVE_POOL_OVERRIDES,
}


def synthetic_itempool_key_for_catalog(catalog_key: str) -> str:
    low = catalog_key.strip().lower()
    if "_comp_06_pearl_" in low:
        return f"itempool_{low.replace('_comp_06_pearl_', '_06_pearl_')}"
    return f"itempool_{low.replace('_comp_05_legendary_', '_05_legendary_')}"


def pool_matches_shiny_intent(pool_name: str, wants_shiny: bool) -> bool:
    low = str(pool_name or "").strip().lower()
    if not low:
        return False
    is_shiny = low.endswith("_shiny") or "_shiny_" in low
    return is_shiny if wants_shiny else not is_shiny


def primary_itempool_key_for_catalog(catalog_key: str, *, wants_shiny: bool = False) -> str:
    """Best single itempool id to spawn one Raid 2 catalog entry."""
    catalog = catalog_key.strip().lower()
    if catalog.startswith("classmod_") and "_comp_05_legendary_06" in catalog:
        return synthetic_itempool_key_for_catalog(catalog)
    if wants_shiny:
        shiny = RAID2_SHINY_POOL_OVERRIDES.get(catalog)
        if shiny:
            return shiny
    native = RAID2_NATIVE_POOL_OVERRIDES.get(catalog)
    if native:
        return native
    return synthetic_itempool_key_for_catalog(catalog)


def build_raid2_itempool_key_set() -> frozenset[str]:
    keys: set[str] = set()
    for catalog in RAID2_CATALOG_KEYS:
        keys.add(synthetic_itempool_key_for_catalog(catalog))
        keys.add(catalog.lower())
        for override in (
            RAID2_PRIMARY_POOL_OVERRIDES.get(catalog),
            (RAID2_SPAWN_HINTS.get(catalog) or {}).get("native_pool"),
        ):
            if override:
                keys.add(str(override).lower())
    return frozenset(keys)


RAID2_ITEMPOOL_KEYS: frozenset[str] = build_raid2_itempool_key_set()


def build_canonical_raid2_itempool_key_set() -> frozenset[str]:
    return frozenset(primary_itempool_key_for_catalog(c) for c in RAID2_CATALOG_KEYS)


CANONICAL_RAID2_ITEMPOOL_KEYS: frozenset[str] = build_canonical_raid2_itempool_key_set()


def is_canonical_raid2_itempool_key(pool_key: str) -> bool:
    return pool_key.strip().lower() in CANONICAL_RAID2_ITEMPOOL_KEYS


def itempool_key_is_raid2(pool_key: str) -> bool:
    key = pool_key.strip().lower()
    if not key:
        return False
    if key in RAID2_ITEMPOOL_KEYS or is_canonical_raid2_itempool_key(key):
        return True
    if key.endswith("_shiny") or "_shiny_" in key:
        for suffix in RAID2_LEGENDARY_SUFFIXES:
            if suffix in key:
                return True
    for catalog in RAID2_CATALOG_KEYS:
        syn = synthetic_itempool_key_for_catalog(catalog)
        if key == syn or catalog in key:
            return True
    return False


def is_broad_classmod_legendary_pool(pool_name: str) -> bool:
    """True for character-wide class mod pools that roll random older legendaries."""
    low = str(pool_name or "").strip().lower()
    if not low:
        return False
    if low.startswith("itempool_class_mods_05_legendary"):
        return True
    if "_05_legendary_06" in low or low.endswith("_legendary_06"):
        return False
    return bool(re.match(r"^itempool_classmod_[a-z0-9_]+_05_legendary(?:_|$)", low))


def row_mapping_is_raid2(row: Mapping[str, Any]) -> bool:
    catalog = str(row.get("catalog_key", "")).strip().lower()
    if catalog in RAID2_CATALOG_KEYS:
        return True
    for pool in row.get("itempools") or []:
        if itempool_key_is_raid2(str(pool)):
            return True
    return False


def entry_is_raid2_content(
    *,
    source_key: str = "",
    data: Mapping[str, Any] | None = None,
) -> bool:
    data = data or {}
    key = source_key.strip().lower()
    if key in RAID2_CATALOG_KEYS:
        return True
    if key.startswith("raid2_comp_") and key[len("raid2_comp_") :] in RAID2_CATALOG_KEYS:
        return True
    if key.startswith("itempool"):
        return is_canonical_raid2_itempool_key(key) or itempool_key_is_raid2(key)
    source_comp = str(data.get("source_comp", "")).strip().lower()
    if source_comp in RAID2_CATALOG_KEYS:
        return True
    if data.get("__raid2_content") and (
        is_canonical_raid2_itempool_key(key) or itempool_key_is_raid2(key)
    ):
        return True
    catalog = str(data.get("catalog_key", "")).strip().lower()
    if catalog in RAID2_CATALOG_KEYS:
        return True
    return False
