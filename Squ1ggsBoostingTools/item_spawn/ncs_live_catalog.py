"""Live NCS catalog: what actually exists in the shipped game data.

Generated from the converted Nexus config store (base + patch).  The mod's
older data files list pools and inv comps that were renamed or cut, which is
why rows could report a successful spawn and never drop anything.  This module
is the single source of truth for three questions:

  * does this itempool still exist?
  * what is the item's real in-game name?
  * if the row's own pool is gone, which live pool still drops the item?
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_CATALOG_PATH = Path(__file__).resolve().parent / "data" / "reference" / "ncs_live_catalog.json"
_HANDLE_RE = re.compile(r"^\s*inv(?:_custom)?'([^']+)'\s*$", re.I)


@lru_cache(maxsize=1)
def _catalog() -> dict[str, dict]:
    try:
        doc = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"pools": {}, "comps": {}, "handle_pools": {}}
    if not isinstance(doc, dict):
        return {"pools": {}, "comps": {}, "handle_pools": {}}
    return {
        "pools": doc.get("pools") if isinstance(doc.get("pools"), dict) else {},
        "comps": doc.get("comps") if isinstance(doc.get("comps"), dict) else {},
        "handle_pools": (
            doc.get("handle_pools") if isinstance(doc.get("handle_pools"), dict) else {}
        ),
    }


def catalog_available() -> bool:
    """False when the generated data file is missing — callers must not gate on it."""
    return bool(_catalog()["pools"])


def normalize_handle(handle: str) -> str:
    """inv'MAL_SR.comp_05_legendary_conflux' -> MAL_SR.comp_05_legendary_conflux"""
    raw = str(handle or "").strip()
    match = _HANDLE_RE.match(raw)
    return (match.group(1) if match else raw).strip()


def catalog_key_to_handle(catalog_key: str) -> str:
    """mal_sr_comp_05_legendary_conflux -> mal_sr.comp_05_legendary_conflux"""
    low = str(catalog_key or "").strip().lower()
    if not low or "_comp_" not in low:
        return ""
    return low.replace("_comp_", ".comp_", 1)


_POOL_TOKEN_RE = re.compile(r"_(?:\d\d_)?(?:legendary|pearl|pearlescent)_(.+)$", re.I)
_COMP_TOKEN_RE = re.compile(r"comp_\d\d_(?:legendary|pearl|pearlescent)_(.+)$", re.I)


def pool_item_token(pool: str) -> str:
    """itempool_mal_sg_05_legendary_reminisce_shiny -> reminisce"""
    low = str(pool or "").strip().lower()
    if low.startswith("itempool_"):
        low = low[len("itempool_") :]
    for suffix in ("_shiny", "_pearl"):
        if low.endswith(suffix):
            low = low[: -len(suffix)]
            break
    match = _POOL_TOKEN_RE.search(low)
    return match.group(1).strip("_") if match else ""


@lru_cache(maxsize=1)
def _comp_by_token() -> dict[str, str]:
    """Item name -> comp handle, for pool names whose prefix lies about the item.

    The shipped pool ids are not reliable (the Scoot'n'Shoot pool is named
    mal_sg while the comp is TOR_PS), so tokens claimed by more than one comp
    are dropped rather than guessed at.
    """
    found: dict[str, set[str]] = {}
    for low, row in _catalog()["comps"].items():
        match = _COMP_TOKEN_RE.search(low)
        if not match:
            continue
        token = match.group(1).strip("_")
        if token:
            found.setdefault(token, set()).add(str(row.get("handle") or low))
    return {token: next(iter(v)) for token, v in found.items() if len(v) == 1}


def comp_for_pool_token(pool: str) -> str:
    token = pool_item_token(pool)
    return _comp_by_token().get(token, "") if token else ""


def pool_row(pool: str) -> dict | None:
    return _catalog()["pools"].get(str(pool or "").strip().lower()) or None


def pool_is_live(pool: str) -> bool:
    return pool_row(pool) is not None


def exact_pool_name(pool: str) -> str:
    """Nexus lookups are case sensitive for some ids — return the shipped casing."""
    row = pool_row(pool)
    return str(row.get("exact") or "") if row else ""


def comp_row(handle_or_catalog: str) -> dict | None:
    raw = normalize_handle(handle_or_catalog).lower()
    comps = _catalog()["comps"]
    if raw in comps:
        return comps[raw]
    guess = catalog_key_to_handle(raw)
    return comps.get(guess) if guess else None


def pools_for_handle(handle_or_catalog: str) -> list[str]:
    """Live pools / ItemPoolLists that can drop this item."""
    raw = normalize_handle(handle_or_catalog).lower()
    table = _catalog()["handle_pools"]
    hit = table.get(raw)
    if not hit:
        guess = catalog_key_to_handle(raw)
        hit = table.get(guess) if guess else None
    return [str(x) for x in hit] if isinstance(hit, list) else []


def label_for_pool(pool: str) -> str:
    """Real in-game name, only for a pool that drops exactly one known item."""
    row = pool_row(pool)
    if row is not None:
        # A live pool speaks for itself; a shared drop list carries no label.
        return str(row.get("label") or "")
    handle = comp_for_pool_token(pool)
    return label_for_catalog(handle) if handle else ""


def label_for_catalog(catalog_key: str) -> str:
    row = comp_row(catalog_key)
    return str(row.get("label") or "") if row else ""


def is_pearlescent_handle(handle_or_catalog: str) -> bool:
    row = comp_row(handle_or_catalog)
    return "pearl" in str((row or {}).get("rarity") or "").lower()


def item_exists(*, pool: str = "", catalog_key: str = "", dump_inv: str = "") -> bool:
    """True when the game can still produce this row's item by some route."""
    if not catalog_available():
        return True
    if pool and pool_is_live(pool):
        return True
    for ref in (dump_inv, catalog_key, comp_for_pool_token(pool)):
        if not ref:
            continue
        if comp_row(ref) is not None or pools_for_handle(ref):
            return True
    return False


def live_source_pool(*, pool: str = "", catalog_key: str = "", dump_inv: str = "") -> str:
    """A live pool that drops this item, preferring the row's own pool."""
    if pool and pool_is_live(pool):
        return exact_pool_name(pool) or str(pool)
    for ref in (dump_inv, catalog_key, comp_for_pool_token(pool)):
        if not ref:
            continue
        hits = pools_for_handle(ref)
        if hits:
            # Prefer a dedicated single-item pool over a big shared drop list.
            hits.sort(key=lambda name: len((pool_row(name) or {}).get("handles") or []))
            return hits[0]
    return ""
