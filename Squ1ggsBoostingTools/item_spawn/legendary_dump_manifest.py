"""Dump named legendaries that have a unique inv-comp but no dedicated NCS pool.

Commons / uncommons / epics stay as type-pool rolls. Named L5s that already have
a dump itempool (or shiny) stay on those rows. This only fills dump comps that
would otherwise never appear as a singular spawn button.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .pearlescent_manifest import is_pearlescent_catalog

_COMP_RE = re.compile(
    r"^(?P<root>[A-Za-z0-9_]+)\.(?P<comp>comp_05_legendary_.+)$",
    re.IGNORECASE,
)
_SKIP_ROOT = re.compile(
    r"classmod|enhancement|shield|repkit|repair|grenade|gadget|hover|turret|terminal|armor",
    re.IGNORECASE,
)
_ROOT_CAT = (
    ("_ar", "Assault Rifle"),
    ("_ps", "Pistol"),
    ("_sm", "SMG"),
    ("_sg", "Shotgun"),
    ("_sr", "Sniper"),
    ("_hw", "Heavy"),
)
_TITLE_ALIASES: dict[str, str] = {
    "roil": "Roil",
    "rainmaker": "Rainmaker",
    "draupner": "Draupner",
    "firstimpression": "First Impression",
    "harddark": "Hard Dark",
    "loarmaster": "Loarmaster",
    "screenwriter": "Screenwriter",
    "bottledlightning": "Bottled Lightning",
    "gammavoid": "Gamma Void",
    "ichor": "Ichor",
    "firework": "Firework",
    "dahlfather": "Dahl Father",
    "javelin": "Javelin",
    "ravenfire": "Ravenfire",
    "sidewinder": "Sidewinder",
    "unstable_kor": "Unstable Kor",
    "atlinggun": "Atling Gun",
    "flak": "Flak",
    "splatoon": "Flak Cannon",
    "bubbles": "Bubbles",
    "lucian": "Lucian's Flank",
    "discjockey": "Disc Jockey",
    "conflux": "Conflux",
    "temper": "Solar Temper",
    "burrow": "PRISM",
    "prism": "PRISM",
    "pchonk": "Pachonk",
    "pachonk": "Pachonk",
    "eigenburst": "Eigenburst",
    "earlyexcess": "Early Excess",
}
# FModel audit: no base itempool_* — only mal_sg *_shiny cross-family pools + @U.
_DUMP_NAMED_LEGENDARY_OVERRIDES: dict[str, dict[str, str]] = {
    "bor_sm_comp_05_legendary_roil": {
        "display_name": "Roil",
        "itempool": "itempool_mal_sg_05_legendary_roil_shiny",
        "category": "SMG",
        "dump_inv": "inv'BOR_SM.comp_05_legendary_Roil'",
    },
    "bor_sr_comp_05_legendary_rainmaker": {
        "display_name": "Rainmaker",
        "itempool": "itempool_mal_sg_05_legendary_rainmaker_shiny",
        "category": "Sniper",
        "dump_inv": "inv'bor_sr.comp_05_legendary_rainmaker'",
    },
}


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").strip().lower())


def _legendary_unique(comp: str) -> str:
    """Weapon token after legendary_ — case-insensitive (dump uses Legendary_*)."""
    low = str(comp or "").strip().lower()
    marker = "legendary_"
    idx = low.find(marker)
    if idx < 0:
        return low
    return low[idx + len(marker) :].strip()


def _game_data_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "game_data.json"


def _legit_rules_path() -> Path:
    return Path(__file__).resolve().parents[1] / "legit_rules_flat.json"


def _category_for_root(root: str) -> str | None:
    low = str(root or "").strip().lower()
    for suffix, cat in _ROOT_CAT:
        if low.endswith(suffix):
            return cat
    return None


@lru_cache(maxsize=1)
def _np_name_by_token() -> dict[str, str]:
    """comp_05_legendary_* → first np_names entry from legit_rules dump."""
    path = _legit_rules_path()
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict[str, str] = {}
    for match in re.finditer(r'"internal"\s*:\s*"([^"]+)"', text):
        internal = str(match.group(1) or "").strip()
        if "comp_05_legendary" not in internal.lower():
            continue
        window = text[match.end() : match.end() + 1200]
        names_blob = re.search(r'"np_names"\s*:\s*\[(.*?)\]', window, re.S)
        if not names_blob:
            continue
        names = re.findall(r'"([^"]+)"', names_blob.group(1))
        if not names:
            continue
        title = str(names[0]).strip()
        if not title:
            continue
        token = _alnum(_legendary_unique(internal))
        if token and token not in out:
            out[token] = title
        full = _alnum(internal)
        if full and full not in out:
            out[full] = title
    return out


def pretty_title_for_legendary_token(token: str) -> str:
    """Human gun name from dump np_names / aliases (e.g. lucian → Lucian's Flank)."""
    key = _alnum(token)
    if not key:
        return ""
    hit = _np_name_by_token().get(key)
    if hit:
        return hit
    for prefix in ("comp05legendary", "legendary", "shiny"):
        if key.startswith(prefix) and len(key) > len(prefix):
            hit = _np_name_by_token().get(key[len(prefix) :])
            if hit:
                return hit
    low = str(token or "").strip().lower().replace("-", "_")
    if low in _TITLE_ALIASES:
        return _TITLE_ALIASES[low]
    if key in _TITLE_ALIASES:
        return _TITLE_ALIASES[key]
    return ""


def pretty_title_for_catalog_or_pool(*, catalog: str = "", pool: str = "", fallback: str = "") -> str:
    """Best display title for a named L5 catalog / itempool row."""
    cat = str(catalog or "").strip().lower()
    pool_l = str(pool or "").strip().lower()
    token = ""
    if "legendary_" in cat:
        token = cat.rsplit("legendary_", 1)[-1]
    elif "legendary_" in pool_l:
        token = pool_l.rsplit("legendary_", 1)[-1]
        if token.endswith("_shiny"):
            token = token[: -len("_shiny")]
    title = pretty_title_for_legendary_token(token) if token else ""
    if title:
        if pool_l.endswith("_shiny") or "_shiny_" in pool_l:
            return f"{title} (Shiny)"
        return title
    return str(fallback or "").strip()


def _title_from_comp(comp: str) -> str:
    tail = _legendary_unique(comp)
    pretty = pretty_title_for_legendary_token(tail)
    if pretty:
        return pretty
    key = tail.strip().lower()
    if key in _TITLE_ALIASES:
        return _TITLE_ALIASES[key]
    return re.sub(r"[_\s]+", " ", tail).strip().title()


def _catalog_key(root: str, comp: str) -> str:
    return f"{root.strip().lower()}_{comp.strip().lower()}"


def _has_dedicated_named_pool(unique: str, pools_lower: list[str]) -> bool:
    """True when a non-shiny NCS / blackmarket pool exists for this gun.

    Shiny-only dump rows (itempool_*_shiny) do not count — base legendaries still
    need a comp/dump list entry (bl4_item_spawner uses inline inv comps for those).
    """
    token = _alnum(unique)
    if not token:
        return False
    for pool in pools_lower:
        compact = pool.replace("_", "")
        if f"legendary{token}" not in compact and f"pearl{token}" not in compact:
            continue
        if pool.endswith("_shiny") or "_shiny_" in pool:
            continue
        if "blackmarket" in compact and token in compact and len(token) >= 6:
            return True
        return True
    return False


@lru_cache(maxsize=1)
def _dump_doc() -> dict[str, Any]:
    try:
        doc = json.loads(_game_data_path().read_text(encoding="utf-8"))
    except OSError:
        return {}
    return doc if isinstance(doc, dict) else {}


@lru_cache(maxsize=256)
def dump_inv_handles_for_catalog(catalog_key: str) -> list[str]:
    """Exact dump item tokens as inv'ROOT.comp_*' for a catalog_key."""
    catalog = str(catalog_key or "").strip().lower()
    match = re.match(r"^(.+)_(comp_0[56]_.+)$", catalog)
    if not match:
        return []
    root, comp = match.group(1), match.group(2)
    want = f"{root}.{comp}".lower()
    out: list[str] = []
    seen: set[str] = set()

    def add(handle: str) -> None:
        raw = str(handle or "").strip()
        if not raw:
            return
        low = raw.lower()
        if low in seen:
            return
        seen.add(low)
        out.append(raw)

    for raw in _dump_doc().get("items") or []:
        item = str(raw or "").strip()
        if item.lower() != want:
            continue
        add(f"inv'{item}'")
        try:
            from .comp_loot_drop import _comp_inv_handle_variants

            for variant in _comp_inv_handle_variants(item):
                add(variant)
        except Exception:
            pass
    if not out:
        add(f"inv'{root}.{comp}'")
        try:
            from .comp_loot_drop import _comp_inv_handle_variants

            for variant in _comp_inv_handle_variants(f"{root}.{comp}"):
                add(variant)
        except Exception:
            pass
    return out


@lru_cache(maxsize=1)
def dump_named_legendary_ui_rows() -> tuple[dict[str, str], ...]:
    """Base (non-shiny) L5 dump comps for the spawn list.

    Includes guns whose only live NCS row is *_shiny — those still get a normal
    legendary list entry here (inline comp spawn), separate from the shiny pool row.
    """
    doc = _dump_doc()
    items = [str(x).strip() for x in (doc.get("items") or []) if str(x).strip()]
    pools_lower = [str(p).strip().lower() for p in (doc.get("item_pools") or []) if str(p).strip()]
    rows: list[dict[str, str]] = []
    seen_cat: set[str] = set()
    for catalog, override in sorted(_DUMP_NAMED_LEGENDARY_OVERRIDES.items()):
        row = dict(override)
        row["catalog_key"] = catalog
        row["dump_named_legendary"] = "1"
        rows.append(row)
        seen_cat.add(catalog)
    for item in items:
        hit = _COMP_RE.match(item)
        if not hit:
            continue
        root, comp = hit.group("root"), hit.group("comp")
        if _SKIP_ROOT.search(root) or _SKIP_ROOT.search(comp):
            continue
        category = _category_for_root(root)
        if not category:
            continue
        catalog = _catalog_key(root, comp)
        if catalog in seen_cat or is_pearlescent_catalog(catalog):
            continue
        unique = _legendary_unique(comp)
        if not unique:
            continue
        if _has_dedicated_named_pool(unique, pools_lower):
            continue
        seen_cat.add(catalog)
        rows.append(
            {
                "display_name": _title_from_comp(comp),
                "itempool": f"itempool_{root.lower()}_{comp.lower()}",
                "catalog_key": catalog,
                "category": category,
                "dump_inv": f"inv'{item}'",
                "dump_named_legendary": "1",
            }
        )
    rows.sort(key=lambda row: (row["category"], row["display_name"].lower()))
    return tuple(rows)
