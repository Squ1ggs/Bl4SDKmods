"""Canonical Raid 3 shiny-legendary filter for Item Spawner + Nexus Discovery.

Sourced from ``Nexus-Data-itempool6.json`` (FModel export) — new wave after Subjugator / Vault Card 3.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

# Spawnable ``inv_comp`` catalog keys (shiny itempool wave in itempool shard 6).
RAID3_CATALOG_KEYS: frozenset[str] = frozenset(
    {
        "mal_sg_comp_05_legendary_sweet_embrace",
        "ted_sg_comp_05_legendary_commbd",
        "tor_ar_comp_05_legendary_coldshoulder",
        "vla_sr_comp_05_legendary_crowdsourced",
        "bor_sr_comp_05_legendary_tankbuster",
        "dad_ar_comp_05_legendary_mercredi",
        "dad_sg_comp_05_legendary_misslaser",
        "bor_sg_comp_05_legendary_crazedearl",
        "bor_sr_comp_05_legendary_rainmaker",
        "bor_sm_comp_05_legendary_roil",
        "ord_sr_comp_05_legendary_seamstress",
        "tor_ps_comp_05_legendary_breadth",
        "tor_sg_comp_05_legendary_arctic",
        "tor_grenade_gadget_comp_05_legendary_slippy",
    }
)

RAID3_LEGENDARY_SUFFIXES: frozenset[str] = frozenset(
    {
        "sweet_embrace",
        "commbd",
        "coldshoulder",
        "crowdsourced",
        "tankbuster",
        "mercredi",
        "misslaser",
        "crazedearl",
        "rainmaker",
        "roil",
        "seamstress",
        "breadth",
        "arctic",
        "slippy",
    }
)

_COMP_SUFFIX_RE = re.compile(
    r"comp_05_legendary_([a-z0-9_]+)",
    re.IGNORECASE,
)

RAID3_PRIMARY_POOL_OVERRIDES: dict[str, str] = {
    "mal_sg_comp_05_legendary_sweet_embrace": "itempool_mal_sg_05_legendary_sweet_embrace_shiny",
    "ted_sg_comp_05_legendary_commbd": "itempool_ted_sg_05_legendary_commbd_shiny",
    "tor_ar_comp_05_legendary_coldshoulder": "itempool_tor_ar_05_legendary_coldshoulder_shiny",
    "vla_sr_comp_05_legendary_crowdsourced": "itempool_vla_sr_05_legendary_crowdsourced_shiny",
    "bor_sr_comp_05_legendary_tankbuster": "itempool_bor_sr_05_legendary_tankbuster_shiny",
    "dad_ar_comp_05_legendary_mercredi": "itempool_dad_ar_05_legendary_mercredi_shiny",
    "dad_sg_comp_05_legendary_misslaser": "itempool_dad_sg_05_legendary_misslaser_shiny",
    "bor_sg_comp_05_legendary_crazedearl": "itempool_mal_sg_05_legendary_crazedearl_shiny",
    "bor_sr_comp_05_legendary_rainmaker": "itempool_mal_sg_05_legendary_rainmaker_shiny",
    "bor_sm_comp_05_legendary_roil": "itempool_mal_sg_05_legendary_roil_shiny",
    "ord_sr_comp_05_legendary_seamstress": "itempool_ord_sr_05_legendary_seamstress_shiny",
    "tor_ps_comp_05_legendary_breadth": "itempool_tor_ps_05_legendary_breadth_shiny",
    "tor_sg_comp_05_legendary_arctic": "itempool_tor_sg_05_legendary_arctic_shiny",
    "tor_grenade_gadget_comp_05_legendary_slippy": "itempool_fishgrenade_slippy",
}


def synthetic_itempool_key_for_catalog(catalog_key: str) -> str:
    low = catalog_key.lower()
    return f"itempool_{low.replace('_comp_05_legendary_', '_05_legendary_')}"


def build_raid3_itempool_key_set() -> frozenset[str]:
    keys: set[str] = set()
    for catalog in RAID3_CATALOG_KEYS:
        keys.add(synthetic_itempool_key_for_catalog(catalog))
        keys.add(catalog.lower())
        override = RAID3_PRIMARY_POOL_OVERRIDES.get(catalog)
        if override:
            keys.add(override.lower())
    return frozenset(keys)


RAID3_ITEMPOOL_KEYS: frozenset[str] = build_raid3_itempool_key_set()


def primary_itempool_key_for_catalog(catalog_key: str) -> str:
    catalog = catalog_key.strip().lower()
    override = RAID3_PRIMARY_POOL_OVERRIDES.get(catalog)
    if override:
        return override
    return synthetic_itempool_key_for_catalog(catalog)


def build_canonical_raid3_itempool_key_set() -> frozenset[str]:
    return frozenset(primary_itempool_key_for_catalog(c) for c in RAID3_CATALOG_KEYS)


CANONICAL_RAID3_ITEMPOOL_KEYS: frozenset[str] = build_canonical_raid3_itempool_key_set()


def is_canonical_raid3_itempool_key(pool_key: str) -> bool:
    return pool_key.strip().lower() in CANONICAL_RAID3_ITEMPOOL_KEYS


def itempool_key_is_raid3(pool_key: str) -> bool:
    key = pool_key.strip().lower()
    if not key:
        return False
    if key in RAID3_ITEMPOOL_KEYS or is_canonical_raid3_itempool_key(key):
        return True
    if key.endswith("_shiny") or "_shiny_" in key:
        for suffix in RAID3_LEGENDARY_SUFFIXES:
            if suffix in key:
                return True
    for catalog in RAID3_CATALOG_KEYS:
        syn = synthetic_itempool_key_for_catalog(catalog)
        if key == syn or catalog in key:
            return True
    return False


def row_mapping_is_raid3(row: Mapping[str, Any]) -> bool:
    catalog = str(row.get("catalog_key", "")).strip().lower()
    if catalog in RAID3_CATALOG_KEYS:
        return True
    for pool in row.get("itempools") or []:
        if itempool_key_is_raid3(str(pool)):
            return True
    return False


def entry_is_raid3_content(
    *,
    source_key: str = "",
    data: Mapping[str, Any] | None = None,
) -> bool:
    data = data or {}
    key = source_key.strip().lower()
    if key.startswith("itempool"):
        return is_canonical_raid3_itempool_key(key)
    source_comp = str(data.get("source_comp", "")).strip().lower()
    if source_comp in RAID3_CATALOG_KEYS:
        return True
    if data.get("__raid3_content") and is_canonical_raid3_itempool_key(key):
        return True
    return False
