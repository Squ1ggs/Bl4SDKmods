"""Raid 2 / pearlescent comp rows for UI lists, pool expansion, and reward grants."""

from __future__ import annotations

from typing import Any

from .pearl_serial_spawn import native_pool_for_catalog, serial_for_catalog
from .raid2_content import RAID2_CATALOG_KEYS, primary_itempool_key_for_catalog, synthetic_itempool_key_for_catalog
from .raid3_content import RAID3_CATALOG_KEYS, primary_itempool_key_for_catalog as raid3_primary_pool
from .squ1ggs_spawn_bridge import RAID2_SPAWN_HINTS, _load_serial_index

try:
    from .tools.build_merge_from_ncs_json import PREFERRED_PRIMARY_DISPLAY
except ImportError:
    PREFERRED_PRIMARY_DISPLAY: dict[str, str] = {}

# Generic weapon-type pearl pools — roll random pearlescents via live NCS criteria rolls.
GENERIC_PEARL_ITEMPOOLS: frozenset[str] = frozenset(
    {
        "itempool_ar_06_pearl",
        "itempool_ps_06_pearl",
        "itempool_sm_06_pearl",
        "itempool_sg_06_pearl",
        "itempool_sr_06_pearl",
    }
)

GENERIC_PEARL_SPAWNABLE: frozenset[str] = frozenset(GENERIC_PEARL_ITEMPOOLS)

_EXTRA_DISPLAY_TITLES: dict[str, str] = {
    "ord_ar_comp_05_legendary_crowsourced": "Crow-Sourced",
}


def is_generic_pearl_itempool(pool_name: str) -> bool:
    return pool_name.strip().lower() in GENERIC_PEARL_ITEMPOOLS


def generic_pearl_pool_spawnable(pool_name: str) -> bool:
    return pool_name.strip().lower() in GENERIC_PEARL_SPAWNABLE


def generic_pearl_spawn_targets(parent_pool: str, count: int) -> list[dict[str, str]]:
    """
    Targets for generic PS/SG/SM/SR/AR pearl pool expansion.

    count=1 → one random pearlescent for that weapon type.
    count>=N → one of each of the N pearls (shuffled), then random extras if count>N.
    """
    import random

    children = expanded_pearl_pool_children(parent_pool)
    if not children:
        return []
    total = max(1, min(int(count), 32))
    if total >= len(children):
        # Shuffle each complete cycle independently.  This guarantees every
        # named pearl before repeats and keeps repeated counts balanced (for
        # example x10 over two AR pearls becomes five of each).
        out: list[dict[str, str]] = []
        while len(out) < total:
            cycle = list(children)
            random.shuffle(cycle)
            out.extend(cycle)
        return out[:total]
    if total == 1:
        return [random.choice(children)]
    # A partial roster should also vary between clicks while remaining unique.
    return random.sample(children, total)


_PEARL_WEAPON_TYPE_POOLS: dict[str, str] = {
    "mal_sm": "itempool_sm_06_pearl",
    "dad_sm": "itempool_sm_06_pearl",
    "vla_sm": "itempool_sm_06_pearl",
    "tor_ps": "itempool_ps_06_pearl",
    "jak_sg": "itempool_sg_06_pearl",
    "ted_sg": "itempool_sg_06_pearl",
    "bor_sr": "itempool_sr_06_pearl",
}


def is_synthetic_named_pearl_pool(pool_name: str) -> bool:
    """Named pearl itempool ids that are merge-only — not live NexusConfigStore rows."""
    low = str(pool_name or "").strip().lower()
    if not low or is_generic_pearl_itempool(low):
        return False
    return "_06_pearl_" in low


def generic_pearl_pool_for_catalog(catalog_key: str) -> str | None:
    """Live generic pearl pool for a weapon type (part rolls within SM/PS/SG/etc.)."""
    catalog = str(catalog_key or "").strip().lower()
    if "_comp_06_pearl_" not in catalog:
        return None
    inv = catalog.split("_comp_06_pearl_", 1)[0]
    pool = _PEARL_WEAPON_TYPE_POOLS.get(inv)
    if pool and is_generic_pearl_itempool(pool):
        return pool
    return None


def display_title_for_catalog(catalog_key: str) -> str:
    key = catalog_key.strip().lower()
    return (
        _EXTRA_DISPLAY_TITLES.get(key)
        or PREFERRED_PRIMARY_DISPLAY.get(key)
        or key.replace("_", " ").title()
    )


def catalog_spawn_row(catalog_key: str) -> dict[str, Any]:
    """One spawnable comp row (for discovery UI, pool expansion, rewards)."""
    catalog = catalog_key.strip().lower()
    serial_index = _load_serial_index()
    serial, serial_src = None, ""
    hints = RAID2_SPAWN_HINTS.get(catalog, {})
    sid = hints.get("serial_id", "").strip().lower()
    for candidate in (sid, sid.replace("pearl_", "") if sid else ""):
        if candidate and candidate in serial_index:
            serial, serial_src = serial_index[candidate]
            break
    if not serial:
        serial = serial_for_catalog(catalog)
        serial_src = "pearl_spawn" if serial else ""
    native = (
        native_pool_for_catalog(catalog)
        or hints.get("native_pool")
        or primary_itempool_key_for_catalog(catalog)
    )
    if native and is_generic_pearl_itempool(native):
        native = native_pool_for_catalog(catalog) or hints.get("native_pool")
    if native and is_generic_pearl_itempool(str(native)):
        native = None
    return {
        "catalog_key": catalog,
        "title": display_title_for_catalog(catalog),
        "itempool": primary_itempool_key_for_catalog(catalog),
        "synthetic_pool": synthetic_itempool_key_for_catalog(catalog),
        "native_pool": native,
        "serial": serial,
        "serial_source": serial_src,
        "category": _category_for_catalog(catalog),
    }


def _category_for_catalog(catalog: str) -> str:
    if catalog.startswith("classmod_"):
        return "Class Mod"
    if "_comp_06_pearl_" in catalog:
        return "Pearl"
    if "shield" in catalog:
        return "Shield"
    if "_hw_" in catalog:
        return "Heavy"
    if "_sg_" in catalog:
        return "Shotgun"
    if "_sm_" in catalog:
        return "SMG"
    if "_sr_" in catalog:
        return "Sniper"
    if "_ps_" in catalog:
        return "Pistol"
    if "_ar_" in catalog:
        return "Assault Rifle"
    return "Raid 2"


def all_raid2_spawn_rows() -> list[dict[str, Any]]:
    return [catalog_spawn_row(c) for c in sorted(RAID2_CATALOG_KEYS)]


def expanded_pearl_pool_children(parent_pool: str) -> list[dict[str, str]]:
    """Named pearlescents under generic type pools (P6 + [Pearl] tiers from dump manifest)."""
    from .pearlescent_manifest import pearlescents_for_generic_pool

    parent = parent_pool.strip().lower()
    rows = pearlescents_for_generic_pool(parent)
    if not rows:
        return []
    out: list[dict[str, str]] = []
    for row in rows:
        out.append(
            {
                "display_name": row["title"],
                "itempool": row["itempool"],
                "category": "Pearl",
                "catalog_key": row["catalog_key"],
                "parent_pool": parent,
            }
        )
    return out


def raid2_serials_for_rewards() -> list[tuple[str, str]]:
    """(title, @U serial) for Grant-all-rewards."""
    rows: list[tuple[str, str]] = []
    for row in all_raid2_spawn_rows():
        serial = row.get("serial")
        if isinstance(serial, str) and serial.startswith("@U"):
            rows.append((str(row["title"]), serial))
    return rows


def _category_for_raid3_catalog(catalog: str) -> str:
    if "_sg_" in catalog:
        return "Shotgun"
    if "_sm_" in catalog:
        return "SMG"
    if "_sr_" in catalog:
        return "Sniper"
    if "_ps_" in catalog:
        return "Pistol"
    if "_ar_" in catalog:
        return "Assault Rifle"
    if "grenade" in catalog:
        return "Grenade"
    return "Raid 3"


def catalog_spawn_row_raid3(catalog_key: str) -> dict[str, Any]:
    catalog = catalog_key.strip().lower()
    native = raid3_primary_pool(catalog)
    return {
        "catalog_key": catalog,
        "title": display_title_for_catalog(catalog),
        "itempool": native,
        "synthetic_pool": synthetic_itempool_key_for_catalog(catalog),
        "native_pool": native,
        "serial": None,
        "serial_source": "",
        "category": _category_for_raid3_catalog(catalog),
    }


def all_raid3_spawn_rows() -> list[dict[str, Any]]:
    return [catalog_spawn_row_raid3(c) for c in sorted(RAID3_CATALOG_KEYS)]


def all_raid_spawn_ui_rows() -> list[dict[str, str]]:
    """Raid 2/3 catalog rows for Squ1ggs item pool UI (catalog_key enables comp/serial spawn)."""
    out: list[dict[str, str]] = []
    for row in (*all_raid2_spawn_rows(), *all_raid3_spawn_rows()):
        pool = str(row.get("native_pool") or row.get("itempool") or "").strip()
        if not pool:
            continue
        out.append(
            {
                "display_name": str(row.get("title", row.get("catalog_key", pool))),
                "itempool": pool,
                "category": str(row.get("category", "Shiny")),
                "catalog_key": str(row.get("catalog_key", "")),
            }
        )
    return out
