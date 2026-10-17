"""Comp tier from dump — pearlescents may use comp_05_legendary or comp_06_pearl inv comps.

In-game pearl card colour comes from rarity id, not comp tier name alone:
- comp_06_pearl_*  → Herald, Screwstonian, … (true P6 inv comp)
- comp_05_legendary_* + *_pearl pool → Handcannon Pearl, Soul Survivor Pearl, …
- comp_05_legendary_* dedicated pool → Abyss, Gomie, Raiden, … (pearl rarity, L5 comp)
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal

CompTier = Literal[
    "comp_06_pearl",
    "comp_05_legendary_pearl",
    "comp_05_legendary",
    "unknown",
]

_COMP06_PEARL_RE = re.compile(r"_comp_06_pearl_", re.I)
_COMP05_LEG_RE = re.compile(r"_comp_05_legendary_", re.I)

# Authoritative comp_06_pearl weapon roots from hotfix game_data dump.
_COMP06_WEAPON_ROOTS: frozenset[str] = frozenset(
    {
        "dad_sm",
        "jak_sg",
        "mal_sm",
        "ted_sg",
        "tor_ps",
        "vla_sm",
    }
)

_TIER_UI_TAG: dict[CompTier, str] = {
    "comp_06_pearl": "[P6]",
    "comp_05_legendary_pearl": "[Pearl]",
    "comp_05_legendary": "[L5]",
    "unknown": "",
}

# comp_05_legendary + *_pearl pool — in-game pearls that use legendary comp parts (dump/game_data).
# Conflux is rarity 06_pearlescent in live NCS (itempool_*_conflux_pearl) — treat as Pearl.
_COMP05_PEARL_CATALOG_KEYS: frozenset[str] = frozenset(
    {
        "ord_ar_comp_05_legendary_crowsourced",
        "bor_sg_comp_05_legendary_crazedearl",
        "dad_ps_comp_05_legendary_soulsurvivor",
        "ted_sg_comp_05_legendary_eigenburst",
        "tor_ps_comp_05_legendary_handcannon",
        "mal_sr_comp_05_legendary_conflux",
        "jak_sr_comp_05_legendary_burrow",
        "ord_ar_comp_05_legendary_pchonk",
    }
)

# Named L5s whose itempool id ends in *_pearl but dump tier is still [L5] (not Pearl UI).
# Empty: Conflux was wrongly forced to L5 here and skipped the live pearl-pool path.
_COMP05_LEGENDARY_ONLY_CATALOG_KEYS: frozenset[str] = frozenset()


def tier_ui_tag(tier: CompTier, *, catalog_key: str = "") -> str:
    from .pearlescent_manifest import is_pearlescent_catalog, pearlescent_row

    cat = str(catalog_key or "").strip().lower()
    if cat and is_pearlescent_catalog(cat):
        row = pearlescent_row(cat)
        if row and row.get("comp_class") == "p6":
            return "[P6]"
        return "[Pearl]"
    if cat and tier == "comp_05_legendary":
        return "[L5]"
    return _TIER_UI_TAG.get(tier, "")


def comp_tier_for_catalog(catalog_key: str, *, pool_name: str = "") -> CompTier:
    key = str(catalog_key or "").strip().lower()
    pool = str(pool_name or "").strip().lower()
    if key and key in _COMP05_LEGENDARY_ONLY_CATALOG_KEYS:
        return "comp_05_legendary"
    if key and _COMP06_PEARL_RE.search(key):
        return "comp_06_pearl"
    if key and _COMP05_LEG_RE.search(key):
        if pool.endswith("_pearl") or "_05_legendary_" in pool and pool.endswith("_pearl"):
            return "comp_05_legendary_pearl"
        return "comp_05_legendary"
    if pool:
        return comp_tier_for_pool(pool)
    return "unknown"


def comp_tier_for_pool(pool_name: str) -> CompTier:
    low = str(pool_name or "").strip().lower()
    if not low:
        return "unknown"
    if low == "itempool_ar_06_pearl":
        return "unknown"  # invalid — no AR comp_06 pearls in dump
    if "_06_pearl" in low and "_05_legendary_" not in low:
        return "comp_06_pearl"
    if "_05_legendary_" in low and low.endswith("_pearl"):
        return "comp_05_legendary_pearl"
    if any(low == f"itempool_{root}_06_pearl" for root in ("ps", "sm", "sg", "sr")):
        return "comp_06_pearl"
    if "_05_legendary_" in low:
        return "comp_05_legendary"
    return "unknown"


def is_comp06_pearl_catalog(catalog_key: str) -> bool:
    return comp_tier_for_catalog(catalog_key) == "comp_06_pearl"


def is_comp05_legendary_catalog(catalog_key: str) -> bool:
    return comp_tier_for_catalog(catalog_key) == "comp_05_legendary"


def is_comp05_legendary_pearl_pool(pool_name: str) -> bool:
    return comp_tier_for_pool(pool_name) == "comp_05_legendary_pearl"


def is_comp06_pearl_pool(pool_name: str) -> bool:
    return comp_tier_for_pool(pool_name) == "comp_06_pearl"


def is_invalid_ar_pearl_pool(pool_name: str) -> bool:
    """AR has no comp_06 pearls but itempool_ar_06_pearl rolls AR pearlescents from manifest."""
    return False


def is_pearl_tier(tier: CompTier) -> bool:
    return tier in ("comp_06_pearl", "comp_05_legendary_pearl")


def is_pearl_tier_pool(pool_name: str) -> bool:
    return is_pearl_tier(comp_tier_for_pool(pool_name))


def is_pearl_tier_catalog(catalog_key: str, *, pool_name: str = "") -> bool:
    return is_pearl_tier(comp_tier_for_catalog(catalog_key, pool_name=pool_name))


@lru_cache(maxsize=1)
def _pearl_friendly_titles() -> dict[str, str]:
    """Friendly weapon names from pearl_spawn_serials dump (not item pool boilerplate)."""
    titles: dict[str, str] = {
        "tor_ps_comp_06_pearl_herald": "Herald",
        "mal_sm_comp_06_pearl_juliet": "Juliet's Sparkle",
        "jak_sg_comp_06_pearl_constable": "Constable",
        "dad_sm_comp_06_pearl_screwed": "Screwstonian",
        "vla_sm_comp_06_pearl_locust": "Parasite",
        "ted_sg_comp_06_pearl_sharkbait": "Sharkbait",
        "ord_ar_comp_05_legendary_crowsourced": "Crow-Sourced Pearl",
        "bor_sg_comp_05_legendary_crazedearl": "Crazed Earl Pearl",
        "dad_ps_comp_05_legendary_soulsurvivor": "Soul Survivor Pearl",
        "ted_sg_comp_05_legendary_eigenburst": "Eigenburst Pearl",
        "tor_ps_comp_05_legendary_handcannon": "Handcannon Pearl",
        "mal_sr_comp_05_legendary_conflux": "Conflux",
        "jak_sr_comp_05_legendary_burrow": "PRISM",
        "ord_ar_comp_05_legendary_pchonk": "Pachonk",
    }
    try:
        from pathlib import Path

        from .mod_data import read_mod_json

        doc = read_mod_json(
            Path(__file__).resolve().parent / "data" / "reference" / "pearl_spawn_serials.json"
        )
        by_cat = doc.get("by_catalog_key") if isinstance(doc, dict) else {}
        if isinstance(by_cat, dict):
            for cat, row in by_cat.items():
                if cat in _COMP05_PEARL_CATALOG_KEYS or "_comp_06_pearl_" in str(cat):
                    title = str((row or {}).get("title") or "").strip()
                    if title:
                        titles[str(cat).lower()] = title
    except Exception:  # noqa: BLE001
        pass
    return titles


def friendly_weapon_title(catalog_key: str, *, pool_name: str = "", fallback: str = "") -> str:
    cat = str(catalog_key or "").strip().lower()
    if cat:
        hit = _pearl_friendly_titles().get(cat)
        if hit:
            return hit
    name = str(fallback or "").strip()
    if name.startswith(">"):
        name = name[1:].strip()
    for tag in ("[P6]", "[Pearl]", "[L5]", "[L+P]"):
        if name.startswith(tag):
            name = name[len(tag) :].strip()
    # Strip Squ1ggs "Ord AR 05 Legendary …" boilerplate for pearl-tier pools.
    low_pool = str(pool_name or "").lower()
    if low_pool.endswith("_pearl") or "_comp_06_pearl_" in cat:
        import re

        name = re.sub(r"\b05\s+Legendary\b", "", name, flags=re.I)
        name = re.sub(
            r"^(Ord|Tor|Mal|Dad|Vla|Jak|Ted|Bor|Ord)\s+(AR|PS|SM|SG|SR|Hw|HW)\s+",
            "",
            name,
            flags=re.I,
        )
        name = re.sub(r"\b06\s+Pearl\b", "", name, flags=re.I)
        name = re.sub(r"\s+", " ", name).strip()
    return name or fallback or cat


def tier_display_name(
    display: str,
    tier: CompTier,
    *,
    catalog_key: str = "",
    pool_name: str = "",
) -> str:
    """Prefix UI rows — pearl-tier legendaries show [Pearl] + short name, not 05 Legendary."""
    name = str(display or "").strip()
    tag = tier_ui_tag(tier, catalog_key=catalog_key)
    from .pearlescent_manifest import is_pearlescent_catalog, pearlescent_row

    if is_pearlescent_catalog(catalog_key):
        manifest = pearlescent_row(catalog_key)
        if manifest:
            name = manifest["title"]
    elif tier in ("comp_06_pearl", "comp_05_legendary_pearl"):
        short = friendly_weapon_title(catalog_key, pool_name=pool_name, fallback=name)
        name = short or name
    if not tag:
        return name
    if name.startswith("[") or name.startswith(tag):
        return name
    if name.startswith(">"):
        return f"> {tag} {name[1:].strip()}"
    return f"{tag} {name}"


@lru_cache(maxsize=1)
def dump_comp05_legendary_pearl_catalog_keys() -> frozenset[str]:
    return _COMP05_PEARL_CATALOG_KEYS


@lru_cache(maxsize=1)
def dump_comp06_catalog_keys() -> frozenset[str]:
    """Authoritative comp_06_pearl catalog keys from game_data dump (6 weapons)."""
    return frozenset(
        {
            "tor_ps_comp_06_pearl_herald",
            "mal_sm_comp_06_pearl_juliet",
            "jak_sg_comp_06_pearl_constable",
            "dad_sm_comp_06_pearl_screwed",
            "vla_sm_comp_06_pearl_locust",
            "ted_sg_comp_06_pearl_sharkbait",
        }
    )
