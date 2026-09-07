"""Inject native NexusConfigStoreItemPool names into merge + discovery."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

MOD_DIR = Path(__file__).resolve().parent

from .mod_data import read_mod_json
from .raid2_content import is_canonical_raid2_itempool_key, itempool_key_is_raid2

_GENERIC_PEARL_ITEMPOOLS = frozenset(
    {
        "itempool_ar_06_pearl",
        "itempool_ps_06_pearl",
        "itempool_sm_06_pearl",
        "itempool_sg_06_pearl",
        "itempool_sr_06_pearl",
    }
)


def _is_generic_pearl_itempool(pool_name: str) -> bool:
    return pool_name.strip().lower() in _GENERIC_PEARL_ITEMPOOLS

DEFAULT_NATIVE_POOLS = MOD_DIR / "data" / "reference" / "ncs_native_itempools.json"


def _native_row_is_raid2(pool: str, low: str) -> bool:
    return itempool_key_is_raid2(pool) or itempool_key_is_raid2(low)
FALLBACK_NATIVE_POOLS = MOD_DIR.parent / "item_pools.json"


def _normalize_entry_key(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")


def resolve_native_pools_path(explicit: Path | None = None) -> Path | None:
    if explicit is not None and read_mod_json(explicit) is not None:
        return explicit
    env = os.environ.get("BL4_NATIVE_ITEMPOOLS_JSON", "").strip()
    if env:
        candidate = Path(env)
        if read_mod_json(candidate) is not None:
            return candidate
    for candidate in (DEFAULT_NATIVE_POOLS, FALLBACK_NATIVE_POOLS):
        if read_mod_json(candidate) is not None:
            return candidate
    return None


def load_native_pool_rows(path: Path | None = None) -> list[dict[str, str]]:
    resolved = resolve_native_pools_path(path)
    if resolved is None:
        return []
    data = read_mod_json(resolved)
    if not isinstance(data, list):
        raise ValueError(f"{resolved} must contain a JSON list.")
    rows: list[dict[str, str]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        pool = str(entry.get("itempool", "")).strip()
        if not pool:
            continue
        low = pool.lower()
        cat = str(entry.get("category", "Other")).strip() or "Other"
        if (
            "turret" in low
            or "terminal" in low
            or cat.lower() == "cosmetic"
            or low.startswith("cosmetics")
            or low.startswith("cosmetic")
        ):
            continue
        rows.append(
            {
                "itempool": pool,
                "display_name": str(entry.get("display_name", pool)).strip() or pool,
                "category": cat,
            }
        )
    return rows


def inject_native_store_itempools(
    itempool_entries: dict[str, dict[str, Any]],
    *,
    path: Path | None = None,
) -> tuple[int, int]:
    """Add stub rows for live ``SpawnInventoryFromItemPool`` names. Returns (added, skipped)."""
    added = 0
    skipped = 0
    source = str(resolve_native_pools_path(path) or "ncs_native_itempools.json")
    for row in load_native_pool_rows(path):
        pool = row["itempool"]
        if _is_generic_pearl_itempool(pool):
            skipped += 1
            continue
        key = _normalize_entry_key(pool)
        existing = itempool_entries.get(key)
        if existing and not existing.get("__synthetic") and not existing.get("__native_store"):
            skipped += 1
            continue
        if key not in itempool_entries or existing.get("__synthetic"):
            added += 1
        payload: dict[str, Any] = {
            "__native_store": True,
            "display_name": row["display_name"],
            "category": row["category"],
            "itempool": pool,
            "source": source,
        }
        if is_canonical_raid2_itempool_key(pool):
            payload["__raid2_content"] = True
        itempool_entries[key] = payload
    return added, skipped


def native_pool_discovery_entries(rows: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    if rows is None:
        rows = load_native_pool_rows()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        pool = row["itempool"]
        key = _normalize_entry_key(pool)
        if key in seen:
            continue
        seen.add(key)
        low = pool.lower()
        title = row["display_name"]
        out.append(
            {
                "id": f"pool:{key}",
                "kind": "itempool",
                "title": title,
                "status": "spawnable",
                "spawn_serial": None,
                "catalog_key": key,
                "itempools": [pool],
                "marketing_aliases": [row["category"]],
                "raid2_watch": _native_row_is_raid2(pool, low),
                "native_store": True,
                "hint": (
                    "Native game loot pool — spawns via Loot Pool Spawner / Discovery. "
                    "No merge items row; game rolls loot from live config."
                ),
            }
        )
    return out
