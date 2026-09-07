"""Standalone item-pool catalog and world-spawn bridge.

No ``bl4_item_spawner`` dependency — bundled ``item_spawn`` + raid catalog handle world drops;
serials go through explicit grant/mail actions.
"""
from __future__ import annotations

import json
import logging
import pkgutil
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent / "data"


def _read_data_json(relative_name: str) -> Any:
    """Read a bundled data JSON, working from both a folder and a .sdkmod zip."""
    try:
        blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], f"data/{relative_name}")
        if blob:
            return json.loads(blob.decode("utf-8"))
    except Exception:
        pass
    try:
        path = _DATA_DIR / relative_name
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    logging.warning(
        f"[Squ1ggs's Boosting Tools | Spawning] data/{relative_name} unavailable — "
        "catalog features limited for this session."
    )
    return {}

GENERIC_PEARL_ITEMPOOLS = frozenset(
    {
        "itempool_ar_06_pearl",
        "itempool_ps_06_pearl",
        "itempool_sm_06_pearl",
        "itempool_sg_06_pearl",
        "itempool_sr_06_pearl",
    }
)


@dataclass(slots=True)
class SpawnRow:
    catalog_key: str
    title: str
    native_pool: str | None
    serial: str | None
    serial_source: str


@dataclass(slots=True)
class SpawnResult:
    ok: bool
    method: str
    detail: str


_CATALOG: dict[str, dict[str, Any]] | None = None
_NATIVE_POOLS: dict[str, str] | None = None


def _load_catalog() -> dict[str, dict[str, Any]]:
    global _CATALOG
    if _CATALOG is None:
        doc = _read_data_json("raid_spawn_catalog.json")
        rows = doc.get("rows", []) if isinstance(doc, dict) else []
        _CATALOG = {
            str(row.get("catalog_key", "")).strip().lower(): dict(row)
            for row in rows
            if isinstance(row, dict) and str(row.get("catalog_key", "")).strip()
        }
    return _CATALOG


def _norm_pool_key(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(name or "").strip().lower()).strip("_")


def _load_native_pools() -> dict[str, str]:
    """Load the bundled live-Nexus pool names, preserving their exact casing."""
    global _NATIVE_POOLS
    if _NATIVE_POOLS is not None:
        return dict(_NATIVE_POOLS)
    doc = _read_data_json("game_data.json")
    names = doc.get("item_pools", []) if isinstance(doc, dict) else []
    index: dict[str, str] = {}
    for raw in names if isinstance(names, list) else []:
        name = str(raw or "").strip()
        if name:
            index.setdefault(_norm_pool_key(name), name)
    _NATIVE_POOLS = index
    return dict(index)


def _resolve_native_pool(hint: str | None, native_index: dict[str, str]) -> str | None:
    if not hint:
        return None
    raw = str(hint).strip()
    resolved = native_index.get(_norm_pool_key(raw))
    if resolved:
        return resolved
    low = raw.lower()
    if low.startswith("itempool") or low.startswith("itempool_") or low.startswith("oak_"):
        return raw
    if raw.startswith("ItemPool_") or raw.startswith("ItemPool"):
        return raw
    return None


def is_generic_pearl_itempool(pool_name: str) -> bool:
    return str(pool_name or "").strip().lower() in GENERIC_PEARL_ITEMPOOLS


def native_pool_for_catalog(catalog_key: str) -> str | None:
    row = _load_catalog().get(str(catalog_key or "").strip().lower(), {})
    value = str(row.get("native_pool", "") or "").strip()
    return value or None


def row_for_catalog(catalog_key: str) -> SpawnRow:
    key = str(catalog_key or "").strip().lower()
    row = _load_catalog().get(key, {})
    serial = str(row.get("serial", "") or "").strip()
    return SpawnRow(
        catalog_key=key,
        title=str(row.get("title", "") or key.replace("_", " ").title()),
        native_pool=native_pool_for_catalog(key),
        serial=serial if serial.startswith("@U") else None,
        serial_source="raid_spawn_catalog" if serial.startswith("@U") else "",
    )


def catalog_spawn_row(catalog_key: str) -> dict[str, Any]:
    key = str(catalog_key or "").strip().lower()
    row = dict(_load_catalog().get(key, {}))
    if not row:
        return {}
    row.setdefault("catalog_key", key)
    row.setdefault("itempool", row.get("native_pool", ""))
    return row


def all_raid_spawn_ui_rows() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for key, row in sorted(_load_catalog().items()):
        # Prefer dedicated non-shiny itempool; native_pool is often a live NCS shiny alias.
        pool = str(row.get("itempool") or row.get("native_pool") or "").strip()
        if not pool:
            continue
        out.append(
            {
                "display_name": str(row.get("title") or key.replace("_", " ").title()),
                "itempool": pool,
                "category": str(row.get("category") or "Shiny"),
                "catalog_key": key,
            }
        )
    return out


GENERIC_PEARL_SPAWNABLE = frozenset(GENERIC_PEARL_ITEMPOOLS)


def generic_pearl_spawn_targets(parent_pool: str, count: int) -> list[dict[str, str]]:
    from .item_spawn.comp_spawn_catalog import generic_pearl_spawn_targets as _manifest_targets

    return _manifest_targets(parent_pool, count)


def expanded_pearl_pool_children(parent_pool: str) -> list[dict[str, str]]:
    """Named pearlescents under generic type pools — manifest roster (all tiers)."""
    from .item_spawn.comp_spawn_catalog import expanded_pearl_pool_children as _manifest_children

    return _manifest_children(parent_pool)


RAID2_SPAWN_HINTS: dict[str, dict[str, str]] = {}
for _key, _row in _load_catalog().items():
    if str(_row.get("raid", "")) == "2":
        _hint: dict[str, str] = {}
        if _row.get("native_pool"):
            _hint["native_pool"] = str(_row["native_pool"])
        if _row.get("serial_id"):
            _hint["serial_id"] = str(_row["serial_id"])
        RAID2_SPAWN_HINTS[_key] = _hint

RAID3_CATALOG_KEYS = frozenset(
    key for key, row in _load_catalog().items() if str(row.get("raid", "")) == "3"
)


def spawn_native_pool(pool_name: str, count: int = 1, level: int = 60) -> SpawnResult:
    """World-spawn a native pool. Never attempts any serial delivery."""
    try:
        from .item_pool_spawning import spawn_item_pool

        resolved = _resolve_native_pool(pool_name, _load_native_pools()) or str(pool_name)
        spawned = spawn_item_pool(resolved, level=level, count=count)
        return SpawnResult(spawned > 0, "ncs_pool", resolved)
    except Exception as exc:  # noqa: BLE001
        return SpawnResult(False, "ncs_pool", str(exc)[:240])


def _spawn_catalog(
    catalog_key: str,
    count: int,
    level: int,
    raid: str,
    *,
    wants_shiny: bool = False,
) -> SpawnResult:
    key = str(catalog_key or "").strip().lower()
    row = _load_catalog().get(key)
    if not row or str(row.get("raid", "")) != raid:
        return SpawnResult(False, f"raid{raid}_spawn", f"not a Raid {raid} catalog key: {key}")
    try:
        if raid == "2":
            from .item_spawn.squ1ggs_spawn_bridge import spawn_raid2_catalog as _bridge

            return _bridge(key, count=count, level=level, wants_shiny=wants_shiny)
        if raid == "3":
            from .item_spawn.squ1ggs_spawn_bridge import spawn_raid3_catalog as _bridge

            return _bridge(key, count=count, level=level)
    except Exception as exc:  # noqa: BLE001
        pass
    candidates = [row.get("itempool"), row.get("native_pool")]
    seen: set[str] = set()
    last = "no native item pool"
    for candidate in candidates:
        pool = str(candidate or "").strip()
        low = pool.lower()
        if not pool or low in seen or is_generic_pearl_itempool(pool):
            continue
        if not _pool_matches_shiny_intent(pool, wants_shiny):
            continue
        seen.add(low)
        hit = spawn_native_pool(pool, count=count, level=level)
        if hit.ok:
            return hit
        last = hit.detail
    return SpawnResult(
        False,
        f"raid{raid}_spawn",
        f"{last} (no serial/mail fallback; use an explicit serial or mail action)",
    )


def _pool_matches_shiny_intent(pool_name: str, wants_shiny: bool) -> bool:
    low = str(pool_name or "").strip().lower()
    if not low:
        return False
    is_shiny = low.endswith("_shiny") or "_shiny_" in low
    return is_shiny if wants_shiny else not is_shiny


def spawn_raid2_catalog(
    catalog_key: str,
    count: int = 1,
    level: int = 60,
    wants_shiny: bool = False,
) -> SpawnResult:
    return _spawn_catalog(catalog_key, count, level, "2", wants_shiny=wants_shiny)


def spawn_raid3_catalog(catalog_key: str, count: int = 1, level: int = 60) -> SpawnResult:
    return _spawn_catalog(catalog_key, count, level, "3")
