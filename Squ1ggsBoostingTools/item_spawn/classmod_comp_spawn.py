"""Class mod comp world spawn — bundled merge payloads extracted from merge.json."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .comp_loot_drop import spawn_from_merge_payload
from .mod_data import read_mod_json

MOD_DIR = Path(__file__).resolve().parent
CLASSMOD_MERGE_PATH = MOD_DIR / "data" / "reference" / "classmod_merge_pools.json"

_DEDICATED_INLINE_POOL_RE = re.compile(
    r"^itempool_classmod_[a-z0-9_]+_05_legendary_(?:0[1-6]|cowbell|raid1|raid2|tuba|dlc1)$",
    re.IGNORECASE,
)

_MERGE_BY_CATALOG: dict[str, dict[str, Any]] | None = None
_MERGE_BY_POOL: dict[str, dict[str, Any]] | None = None


@dataclass(slots=True)
class SpawnResult:
    ok: bool
    method: str
    detail: str


def pool_from_dedicated_classmod_catalog(catalog_key: str) -> str:
    """classmod_paladin_comp_05_legendary_06 -> itempool_classmod_paladin_05_legendary_06"""
    low = str(catalog_key or "").strip().lower()
    if not low.startswith("classmod_") or "_comp_05_legendary_" not in low:
        return ""
    return "itempool_" + low.replace("_comp_05_legendary_", "_05_legendary_", 1)


def is_dedicated_classmod_catalog(catalog_key: str) -> bool:
    pool = pool_from_dedicated_classmod_catalog(catalog_key)
    return bool(pool) and is_dedicated_classmod_inline_pool(pool)


def is_dedicated_classmod_inline_pool(pool_name: str) -> bool:
    """Single-comp synthetic pools (Artificer, Bombastic, …) — safe for inline merge.

    Requires a merge payload entry so empty/fake pool ids (e.g. Loveless before payload)
    do not force a flaky dedicated path with nothing to spawn.
    """
    low = str(pool_name or "").strip().lower()
    if low == "itempool_classmod_comp_05_legendary":
        return True
    if not bool(_DEDICATED_INLINE_POOL_RE.match(low)):
        return False
    _, by_pool = _load_classmod_merge_index()
    return low in by_pool


def is_native_roll_classmod_pool(pool_name: str) -> bool:
    """Mixed / criteria classmod pools — live NCS roll only, never inline merge."""
    low = str(pool_name or "").strip().lower()
    if not low or "classmod" not in low and "class_mod" not in low:
        return False
    return not is_dedicated_classmod_inline_pool(low)


def _catalog_from_pool_key(pool_key: str) -> str:
    """itempool_classmod_paladin_05_legendary_06 -> classmod_paladin_comp_05_legendary_06"""
    low = str(pool_key or "").strip().lower()
    if not low.startswith("itempool_"):
        return ""
    body = low[len("itempool_") :]
    if body.startswith("classmod_") and "_05_legendary_" in body:
        parts = body.split("_05_legendary_", 1)
        if len(parts) == 2:
            return f"{parts[0]}_comp_05_legendary_{parts[1]}"
    if body.startswith("class_mods_"):
        return ""
    return ""


def _load_classmod_merge_index() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    global _MERGE_BY_CATALOG, _MERGE_BY_POOL
    if _MERGE_BY_CATALOG is not None and _MERGE_BY_POOL is not None:
        return _MERGE_BY_CATALOG, _MERGE_BY_POOL

    by_catalog: dict[str, dict[str, Any]] = {}
    by_pool: dict[str, dict[str, Any]] = {}
    doc = read_mod_json(CLASSMOD_MERGE_PATH)
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if isinstance(entries, dict):
        for pool_key, row in entries.items():
            if not isinstance(row, dict):
                continue
            pool_l = str(pool_key).strip().lower()
            by_pool[pool_l] = dict(row)
            catalog = str(
                row.get("source_comp") or row.get("catalog_key") or _catalog_from_pool_key(pool_l)
            ).strip().lower()
            if catalog:
                by_catalog[catalog] = dict(row)

    _MERGE_BY_CATALOG = by_catalog
    _MERGE_BY_POOL = by_pool
    return by_catalog, by_pool


def merge_payload_for_classmod_catalog(catalog_key: str) -> dict[str, Any] | None:
    catalog = str(catalog_key or "").strip().lower()
    if not catalog or not is_dedicated_classmod_catalog(catalog):
        return None
    by_catalog, _ = _load_classmod_merge_index()
    hit = by_catalog.get(catalog)
    return dict(hit) if hit is not None else None


def merge_payload_for_classmod_pool(pool_name: str) -> dict[str, Any] | None:
    pool = str(pool_name or "").strip().lower()
    if not pool or not is_dedicated_classmod_inline_pool(pool):
        return None
    _, by_pool = _load_classmod_merge_index()
    hit = by_pool.get(pool)
    return dict(hit) if hit is not None else None


def _try_bl4_item_spawner_inline(
    payload: dict[str, Any], count: int, level: int, *, drop_only: bool = False
) -> SpawnResult | None:
    try:
        import bl4_item_spawner as bis
    except ImportError:
        return None
    try:
        bis.CONTROLLER._spawn_from_inline_itempool(
            payload, count, level, drop_only=drop_only
        )
        return SpawnResult(True, "bl4_classmod_merge_inline", str(payload.get("spawn_serial", "")))
    except Exception as exc:  # noqa: BLE001
        return SpawnResult(False, "bl4_classmod_merge_inline", str(exc)[:240])


def try_spawn_classmod_comp_world(
    catalog_key: str = "",
    *,
    count: int = 1,
    level: int = 60,
    pool_name: str | None = None,
    drop_only: bool = False,
) -> SpawnResult:
    """World-drop a dedicated single-comp class mod via bundled merge inline."""
    catalog = str(catalog_key or "").strip().lower()
    pool = str(pool_name or "").strip().lower()
    if pool and not is_dedicated_classmod_inline_pool(pool):
        return SpawnResult(False, "classmod_comp", f"pool '{pool}' is a roll pool — use native NCS")
    payload = merge_payload_for_classmod_catalog(catalog) if catalog else None
    if payload is None and pool:
        payload = merge_payload_for_classmod_pool(pool)
    if payload is None:
        label = catalog or pool or "classmod"
        return SpawnResult(False, "classmod_comp", f"no dedicated merge payload for {label}")

    bl4_hit = _try_bl4_item_spawner_inline(payload, count, level, drop_only=drop_only)
    if bl4_hit is not None and bl4_hit.ok:
        return bl4_hit

    spawned, err = spawn_from_merge_payload(
        payload, count=count, level=level, drop_only=drop_only
    )
    if spawned > 0:
        label = str(payload.get("display_name") or payload.get("spawn_serial") or catalog or pool_name)
        return SpawnResult(True, "classmod_merge_inline", f"{label} x{spawned}")

    detail = err or (bl4_hit.detail if bl4_hit is not None else "classmod merge inline failed")
    return SpawnResult(False, "classmod_comp", detail)
