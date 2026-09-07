"""Pearlescent comp world spawn — bundled merge payloads from Item Spawner dump."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .mod_data import read_mod_json
from .raid2_content import synthetic_itempool_key_for_catalog

MOD_DIR = Path(__file__).resolve().parent
PEARL_MERGE_PATH = MOD_DIR / "data" / "reference" / "pearl_merge_pools.json"

_MERGE_BY_CATALOG: dict[str, dict[str, Any]] | None = None
_MERGE_BY_POOL: dict[str, dict[str, Any]] | None = None


@dataclass(slots=True)
class SpawnResult:
    ok: bool
    method: str
    detail: str


def _load_pearl_merge_index() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    global _MERGE_BY_CATALOG, _MERGE_BY_POOL
    if _MERGE_BY_CATALOG is not None and _MERGE_BY_POOL is not None:
        return _MERGE_BY_CATALOG, _MERGE_BY_POOL

    by_catalog: dict[str, dict[str, Any]] = {}
    by_pool: dict[str, dict[str, Any]] = {}
    doc = read_mod_json(PEARL_MERGE_PATH)
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if isinstance(entries, dict):
        for pool_key, row in entries.items():
            if not isinstance(row, dict):
                continue
            indexed_row = dict(row)
            indexed_row.setdefault("__itempool_name", str(pool_key).strip())
            by_pool[str(pool_key).strip().lower()] = indexed_row
            catalog = str(indexed_row.get("source_comp") or indexed_row.get("catalog_key") or "").strip().lower()
            if catalog:
                by_catalog[catalog] = indexed_row
            syn = synthetic_itempool_key_for_catalog(catalog) if catalog else ""
            if syn:
                by_pool[syn.strip().lower()] = indexed_row

    _MERGE_BY_CATALOG = by_catalog
    _MERGE_BY_POOL = by_pool
    return by_catalog, by_pool


def merge_payload_for_pearl_catalog(catalog_key: str) -> dict[str, Any] | None:
    catalog = str(catalog_key or "").strip().lower()
    by_catalog, by_pool = _load_pearl_merge_index()
    if catalog in by_catalog:
        return dict(by_catalog[catalog])
    pool = synthetic_itempool_key_for_catalog(catalog)
    if pool and pool.lower() in by_pool:
        return dict(by_pool[pool.lower()])
    return None


def merge_payload_for_pearl_pool(pool_name: str) -> dict[str, Any] | None:
    pool = str(pool_name or "").strip().lower()
    if not pool:
        return None
    _, by_pool = _load_pearl_merge_index()
    hit = by_pool.get(pool)
    return dict(hit) if hit is not None else None


def _try_bl4_item_spawner_inline(
    payload: dict[str, Any], count: int, level: int, *, drop_only: bool = True
) -> SpawnResult | None:
    try:
        import bl4_item_spawner as bis
    except ImportError:
        return None
    try:
        bis.CONTROLLER._spawn_from_inline_itempool(
            payload, count, level, drop_only=drop_only
        )
        return SpawnResult(True, "bl4_pearl_merge_inline", str(payload.get("spawn_serial", "")))
    except Exception as exc:  # noqa: BLE001
        return SpawnResult(False, "bl4_pearl_merge_inline", str(exc)[:240])


def try_spawn_pearl_comp_world(
    catalog_key: str,
    *,
    count: int = 1,
    level: int = 60,
    pool_name: str | None = None,
    drop_only: bool = True,
    skip_verify: bool = False,
) -> SpawnResult:
    """World-drop a named pearl via bundled merge __synthetic rows (dump-backed)."""
    catalog = str(catalog_key or "").strip().lower()
    payload = merge_payload_for_pearl_catalog(catalog) if catalog else None
    if payload is None and pool_name:
        payload = merge_payload_for_pearl_pool(pool_name)
    if payload is None:
        label = catalog or str(pool_name or "").strip() or "pearl"
        return SpawnResult(False, "pearl_comp", f"no merge payload for {label}")

    if not skip_verify:
        try:
            from .inventory_def_ptr import reset_inventory_def_scriptstruct_cache

            reset_inventory_def_scriptstruct_cache()
        except Exception:  # noqa: BLE001
            pass

    # Keep manifest/catalog lookup usable in release tooling without importing
    # UnrealSDK-only spawn code until a physical spawn is actually requested.
    from .comp_loot_drop import spawn_from_merge_payload

    spawned, err = spawn_from_merge_payload(
        payload,
        count=count,
        level=level,
        drop_only=drop_only,
        pool_name=str(pool_name or payload.get("__itempool_name") or ""),
        skip_verify=skip_verify,
    )
    if spawned > 0:
        label = str(payload.get("display_name") or payload.get("spawn_serial") or catalog)
        return SpawnResult(True, "pearl_merge_inline", f"{label} x{spawned}")

    # In ground-only mode the bundled path above performs actor verification.
    # The external compatibility path reports only that its Python call returned,
    # which previously hid silent-empty Pearl attempts as successful.
    bl4_hit = (
        None
        if drop_only
        else _try_bl4_item_spawner_inline(payload, count, level, drop_only=drop_only)
    )
    if bl4_hit is not None and bl4_hit.ok:
        return bl4_hit

    detail = err or (bl4_hit.detail if bl4_hit is not None else "merge inline spawn failed")
    return SpawnResult(False, "pearl_comp", detail)
