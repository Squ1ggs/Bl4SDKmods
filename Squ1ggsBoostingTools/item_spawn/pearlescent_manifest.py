"""Authoritative pearlescent weapon list from game_data dump + raid catalog.

Comp tiers (dump — BOTH exist, different weapons):
- comp_06_pearl_*     → true pearlescent (7 guns) — itempool_*_06_pearl_<name>
- comp_05_legendary_* → ALL other player-facing pearlescents use this comp tier
  - with *_pearl pool suffix (Crow-Sourced Pearl, Handcannon Pearl, …)
  - OR dedicated legendary pool (Abyss, Gomie, Solar Temper, Raiden, …)

NOT pearlescent: Kaoson/KaoSon — comp_05 shiny legendary (itempool_*_KaoSon_shiny).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, TypedDict

CompClass = Literal["p6", "pearl_pool", "pearl_world"]


class PearlescentRow(TypedDict):
    catalog_key: str
    title: str
    itempool: str
    weapon_type: str  # ps | sm | sg | sr | ar
    comp_class: CompClass


# Dump-backed spawn pools — prefer live NCS itempool ids from game_data.json.
PEARLESCENT_ROWS: list[PearlescentRow] = [
    # --- comp_06_pearl (true pearlescent) ---
    {"catalog_key": "tor_ps_comp_06_pearl_herald", "title": "Herald", "itempool": "itempool_tor_ps_06_pearl_herald", "weapon_type": "ps", "comp_class": "p6"},
    {"catalog_key": "mal_sm_comp_06_pearl_juliet", "title": "Juliet's Sparkle", "itempool": "itempool_mal_sm_06_pearl_juliet", "weapon_type": "sm", "comp_class": "p6"},
    {"catalog_key": "jak_sg_comp_06_pearl_constable", "title": "Constable", "itempool": "itempool_jak_sg_06_pearl_constable", "weapon_type": "sg", "comp_class": "p6"},
    {"catalog_key": "dad_sm_comp_06_pearl_screwed", "title": "Screwstonian", "itempool": "itempool_dad_sm_06_pearl_screwed", "weapon_type": "sm", "comp_class": "p6"},
    {"catalog_key": "vla_sm_comp_06_pearl_locust", "title": "Parasite", "itempool": "itempool_vla_sm_06_pearl_Locust", "weapon_type": "sm", "comp_class": "p6"},
    {"catalog_key": "ted_sg_comp_06_pearl_sharkbait", "title": "Sharkbait", "itempool": "itempool_ted_sg_06_pearl_sharkbait", "weapon_type": "sg", "comp_class": "p6"},
    # --- comp_05 + *_pearl itempool ---
    {"catalog_key": "ord_ar_comp_05_legendary_crowsourced", "title": "Crow-Sourced Pearl", "itempool": "itempool_ord_ar_05_legendary_crowsourced_pearl", "weapon_type": "ar", "comp_class": "pearl_pool"},
    {"catalog_key": "bor_sg_comp_05_legendary_crazedearl", "title": "Crazed Earl Pearl", "itempool": "itempool_bor_sg_05_legendary_CrazedEarl_pearl", "weapon_type": "sg", "comp_class": "pearl_pool"},
    {"catalog_key": "ted_sg_comp_05_legendary_eigenburst", "title": "Eigenburst Pearl", "itempool": "itempool_ted_sg_05_legendary_eigenburst_pearl", "weapon_type": "sg", "comp_class": "pearl_pool"},
    {"catalog_key": "tor_ps_comp_05_legendary_handcannon", "title": "Handcannon Pearl", "itempool": "itempool_tor_ps_05_legendary_handcannon_pearl", "weapon_type": "ps", "comp_class": "pearl_pool"},
    {"catalog_key": "dad_ps_comp_05_legendary_soulsurvivor", "title": "Soul Survivor Pearl", "itempool": "itempool_dad_ps_05_legendary_soulsurvivor_pearl", "weapon_type": "ps", "comp_class": "pearl_pool"},
    {"catalog_key": "mal_sr_comp_05_legendary_conflux", "title": "Conflux", "itempool": "itempool_mal_sr_05_legendary_conflux_pearl", "weapon_type": "sr", "comp_class": "pearl_pool"},
    # --- comp_05 pearlescent world / event (dedicated legendary pool, no *_pearl suffix) ---
    {"catalog_key": "bor_sr_comp_05_legendary_abyss", "title": "Abyss Ripper", "itempool": "itempool_bor_sr_05_legendary_abyss", "weapon_type": "sr", "comp_class": "pearl_world"},
    {"catalog_key": "jak_ar_comp_05_legendary_gomie", "title": "Gomie", "itempool": "itempool_jak_ar_05_legendary_gomie", "weapon_type": "ar", "comp_class": "pearl_world"},
    {"catalog_key": "bor_sm_comp_05_legendary_jailbroken", "title": "Jail-Broken Gatling", "itempool": "itempool_bor_sm_05_legendary_jailbroken", "weapon_type": "sm", "comp_class": "pearl_world"},
    {"catalog_key": "dad_sm_comp_05_legendary_raiden", "title": "Raiden", "itempool": "itempool_dad_sm_05_legendary_raiden", "weapon_type": "sm", "comp_class": "pearl_world"},
    {"catalog_key": "ord_sr_comp_05_legendary_temper", "title": "Solar Temper", "itempool": "itempool_ord_sr_05_legendary_temper", "weapon_type": "sr", "comp_class": "pearl_world"},
    {"catalog_key": "jak_sr_comp_05_legendary_burrow", "title": "PRISM", "itempool": "itempool_jak_sr_05_legendary_burrow", "weapon_type": "sr", "comp_class": "pearl_world"},
    {"catalog_key": "ord_ar_comp_05_legendary_pchonk", "title": "Pachonk", "itempool": "itempool_ord_ar_05_legendary_Pchonk", "weapon_type": "ar", "comp_class": "pearl_world"},
]

_TYPE_TO_GENERIC_POOL: dict[str, str] = {
    "ps": "itempool_ps_06_pearl",
    "sm": "itempool_sm_06_pearl",
    "sg": "itempool_sg_06_pearl",
    "sr": "itempool_sr_06_pearl",
    "ar": "itempool_ar_06_pearl",
}


def generic_pool_for_weapon_type(weapon_type: str) -> str | None:
    return _TYPE_TO_GENERIC_POOL.get(str(weapon_type or "").strip().lower())


def generic_pool_for_catalog(catalog_key: str) -> str | None:
    row = pearlescent_row(catalog_key)
    if not row:
        return None
    return generic_pool_for_weapon_type(row["weapon_type"])


PEARLESCENT_CATALOG_KEYS: frozenset[str] = frozenset(r["catalog_key"] for r in PEARLESCENT_ROWS)

# Dump-proven *_shiny pools — Soul Survivor is the only known pearl with a shiny /
# Phosphene variant (Story Pack 1). Other rows keep base pearl pools only.
PEARL_SHINY_POOLS: dict[str, str] = {
    "dad_ps_comp_05_legendary_soulsurvivor": "itempool_dad_ps_05_legendary_soulsurvivor_shiny",
}

# itempool8 explicitly deletes Crow-Sourced's old base pool; pearl rows use
# their *_pearl pools or direct inv-comp fallback.
PEARL_BASE_LEGENDARY_POOLS: dict[str, str] = {}

# Nexus-Data-itempool dump: named pools that wrap dump inv' comps. game_data.json
# item_pools is older and omits Jail-Broken Gatling / Raiden.
_NCS_DUMP_INV_POOLS: dict[str, str] = {
    "bor_sm_comp_05_legendary_jailbroken": "itempool_bor_sm_05_legendary_jailbroken",
    "dad_sm_comp_05_legendary_raiden": "itempool_dad_sm_05_legendary_raiden",
}


@lru_cache(maxsize=1)
def _dump_pool_canonical_by_lower() -> dict[str, str]:
    return {p.lower(): p for p in dump_registered_itempools()}


def _registered_pool_siblings(pool_name: str) -> list[str]:
    """Dump-registered *_shiny / *_pearl alternates (comp_05 + Locust-style comp_06)."""
    low = str(pool_name or "").strip().lower()
    if not low.startswith("itempool_"):
        return []
    by_low = _dump_pool_canonical_by_lower()
    out: list[str] = []
    seen: set[str] = {low}

    def add(cand_low: str) -> None:
        if cand_low in seen or cand_low not in by_low:
            return
        seen.add(cand_low)
        out.append(by_low[cand_low])

    if low.endswith("_pearl"):
        stem = low[: -len("_pearl")]
        add(f"{stem}_shiny")
        add(f"{stem}_pearl")
    if "_06_pearl_" in low and not low.endswith("_shiny"):
        add(f"{low}_shiny")
    return out


@lru_cache(maxsize=1)
def dump_native_pool_aliases() -> dict[str, str]:
    """catalog_key -> live NCS pool from pearl_spawn_serials.json (dump)."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent / "data" / "reference" / "pearl_spawn_serials.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    aliases = doc.get("native_pool_aliases") if isinstance(doc, dict) else None
    if not isinstance(aliases, dict):
        return {}
    out: dict[str, str] = {}
    for cat, pool in aliases.items():
        key = str(cat or "").strip().lower()
        name = str(pool or "").strip()
        if key and name:
            out[key] = name
    return out


def dump_native_pool_for_catalog(catalog_key: str) -> str | None:
    return dump_native_pool_aliases().get(str(catalog_key or "").strip().lower())


def primary_named_pearl_ncs_pool(catalog_key: str, manifest_itempool: str = "") -> str | None:
    """First pool in the dump-backed try order."""
    order = named_pearl_ncs_pool_try_order(catalog_key, manifest_itempool)
    return order[0] if order else None


def _pool_tryable(name: str | None) -> str | None:
    """Pool id we should attempt — dump-registered, shiny index, manifest, or merge row."""
    raw = str(name or "").strip()
    if not raw.lower().startswith("itempool_"):
        return None
    if itempool_in_dump(raw) or ncs_dump_inv_pool(raw):
        return raw
    from .shiny_pool_lookup import lookup_shiny_pool

    if lookup_shiny_pool(raw):
        return raw
    if pearlescent_row_for_pool(raw):
        return raw
    from .pearl_comp_spawn import merge_payload_for_pearl_pool

    if merge_payload_for_pearl_pool(raw):
        return raw
    return None


def named_pearl_ncs_pool_try_order(catalog_key: str, manifest_itempool: str = "") -> list[str]:
    """Dump-native manifest pool first, then shiny/alias siblings."""

    out: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        hit = _pool_tryable(name)
        if not hit:
            return
        low = hit.lower()
        if low in seen:
            return
        seen.add(low)
        out.append(hit)

    catalog = str(catalog_key or "").strip().lower()
    manifest = str(manifest_itempool or "").strip()
    row = pearlescent_row(catalog) if catalog else None
    shiny_primary = PEARL_SHINY_POOLS.get(catalog)

    add(manifest)
    add(dump_native_pool_for_catalog(catalog))
    add(_NCS_DUMP_INV_POOLS.get(catalog))
    add(PEARL_BASE_LEGENDARY_POOLS.get(catalog))
    for sibling in _registered_pool_siblings(manifest):
        add(sibling)
    add(shiny_primary)
    if shiny_primary:
        for sibling in _registered_pool_siblings(shiny_primary):
            add(sibling)
    if row and row["comp_class"] == "pearl_pool":
        for sibling in _registered_pool_siblings(row["itempool"]):
            add(sibling)
    return out


def named_pearl_ncs_pool_candidates(catalog_key: str, manifest_itempool: str = "") -> list[str]:
    return named_pearl_ncs_pool_try_order(catalog_key, manifest_itempool)


def dump_registered_named_pearl_pools(catalog_key: str, manifest_itempool: str = "") -> list[str]:
    """Live dump itempool ids for this gun only — never a different manufacturer's shiny."""
    catalog = str(catalog_key or "").strip().lower()
    row = pearlescent_row(catalog)
    stem = ""
    if row:
        stem = str(row["itempool"]).strip().lower().removeprefix("itempool_")
        if stem.endswith("_pearl"):
            stem = stem[: -len("_pearl")]
    alias = dump_native_pool_for_catalog(catalog)
    out: list[str] = []
    own_pools = {
        str(row["itempool"]).strip().lower() if row else "",
        str(alias or "").strip().lower(),
        str(manifest_itempool or "").strip().lower(),
    }
    own_pools.discard("")
    for name in named_pearl_ncs_pool_try_order(catalog_key, manifest_itempool):
        low = name.lower()
        own = low in own_pools
        if not itempool_in_dump(name) and not ncs_dump_inv_pool(name) and not own:
            continue
        if alias and low == str(alias).strip().lower():
            if not stem or stem in low:
                out.append(name)
            continue
        if stem and stem not in low:
            continue
        out.append(name)
    non_shiny = [n for n in out if not n.lower().endswith("_shiny")]
    shiny = [n for n in out if n.lower().endswith("_shiny")]
    return non_shiny + shiny


def pearl_rows_by_comp_class(comp_class: CompClass) -> list[PearlescentRow]:
    return [r for r in PEARLESCENT_ROWS if r["comp_class"] == comp_class]


def dump_ncs_pool_for_catalog(catalog_key: str) -> str | None:
    """Registered NCS itempool for ground drop, if any."""
    row = pearlescent_row(catalog_key)
    if not row:
        return None
    return primary_named_pearl_ncs_pool(row["catalog_key"], row["itempool"])


def pearlescent_row(catalog_key: str) -> PearlescentRow | None:
    key = str(catalog_key or "").strip().lower()
    for row in PEARLESCENT_ROWS:
        if row["catalog_key"] == key:
            return row
    return None


def pearlescent_row_for_pool(pool_name: str) -> PearlescentRow | None:
    low = str(pool_name or "").strip().lower()
    if not low:
        return None
    for row in PEARLESCENT_ROWS:
        if str(row["itempool"]).strip().lower() == low:
            return row
    return None


def is_pearlescent_catalog(catalog_key: str) -> bool:
    return str(catalog_key or "").strip().lower() in PEARLESCENT_CATALOG_KEYS


def pearlescents_for_weapon_type(weapon_type: str) -> list[PearlescentRow]:
    wt = str(weapon_type or "").strip().lower()
    return [r for r in PEARLESCENT_ROWS if r["weapon_type"] == wt]


def pearlescents_for_generic_pool(parent_pool: str) -> list[PearlescentRow]:
    parent = str(parent_pool or "").strip().lower()
    for wt, generic in _TYPE_TO_GENERIC_POOL.items():
        if generic == parent:
            return [
                r
                for r in pearlescents_for_weapon_type(wt)
                if dump_lists_named_pearl(r["catalog_key"], r["itempool"])
            ]
    return []


def ui_rows_for_pearlescents() -> list[dict[str, str]]:
    """Singular named pearlescents for the pool spawner (dump NCS)."""
    from .legendary_dump_manifest import dump_inv_handles_for_catalog

    out: list[dict[str, str]] = []
    for row in PEARLESCENT_ROWS:
        if not dump_lists_named_pearl(row["catalog_key"], row["itempool"]):
            continue
        handles = dump_inv_handles_for_catalog(row["catalog_key"])
        entry = {
            "display_name": row["title"],
            "itempool": row["itempool"],
            "catalog_key": row["catalog_key"],
            "category": "Pearl",
            "weapon_type": row["weapon_type"],
            "comp_class": row["comp_class"],
        }
        if handles:
            entry["dump_inv"] = handles[0]
        out.append(entry)
    return out


def generic_pool_ui_rows() -> list[dict[str, str]]:
    """Type-roll pools — one per weapon class that has pearlescents."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    labels = {
        "ps": "PS Pearl Pool",
        "sm": "SM Pearl Pool",
        "sg": "SG Pearl Pool",
        "sr": "SR Pearl Pool",
        "ar": "AR Pearl Pool",
    }
    for wt in ("ps", "sm", "sg", "sr", "ar"):
        children = pearlescents_for_weapon_type(wt)
        if not children:
            continue
        pool = _TYPE_TO_GENERIC_POOL[wt]
        if pool in seen:
            continue
        seen.add(pool)
        out.append(
            {
                "display_name": labels[wt],
                "itempool": pool,
                "category": "Pearl",
                "weapon_type": wt,
            }
        )
    return out


@lru_cache(maxsize=1)
def dump_registered_itempools() -> frozenset[str]:
    """Live NCS itempool ids from game_data.json dump."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "data" / "game_data.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return frozenset()
    pools = doc.get("item_pools") if isinstance(doc, dict) else None
    if not isinstance(pools, list):
        return frozenset()
    out: set[str] = set()
    for name in pools:
        low = str(name or "").strip().lower()
        if low.startswith("itempool_"):
            out.add(low)
    return frozenset(out)


def itempool_in_dump(pool_name: str) -> bool:
    return str(pool_name or "").strip().lower() in dump_registered_itempools()


def ncs_dump_inv_pool(pool_name: str) -> bool:
    """True for Nexus-Data-itempool names that wrap a dump inv' comp."""
    low = str(pool_name or "").strip().lower()
    return any(p.lower() == low for p in _NCS_DUMP_INV_POOLS.values())


def dump_lists_named_pearl(catalog_key: str = "", itempool: str = "") -> bool:
    """Named pearl row is listed only when the dump has a live itempool id."""
    pool = str(itempool or "").strip()
    catalog = str(catalog_key or "").strip().lower()
    if not pool and catalog:
        row = pearlescent_row(catalog)
        pool = str(row["itempool"] if row else "")
    if not pool:
        return False
    return itempool_in_dump(pool) or ncs_dump_inv_pool(pool)
