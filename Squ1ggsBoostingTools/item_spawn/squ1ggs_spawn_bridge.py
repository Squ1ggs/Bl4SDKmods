"""Spawn bridge for Raid 2/3 catalog rows — standalone (no bl4_item_spawner import)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .mod_data import read_mod_json
from .native_store_pools import load_native_pool_rows
from .pearl_comp_spawn import try_spawn_pearl_comp_world
from .classmod_comp_spawn import is_dedicated_classmod_inline_pool
from .pearl_serial_spawn import (
    native_pool_for_catalog,
    serial_for_catalog,
    serials_for_catalog,
    try_deliver_serial,
    try_spawn_catalog_via_serial,
)
from .raid2_content import (
    RAID2_CATALOG_KEYS,
    RAID2_SPAWN_HINTS,
    is_broad_classmod_legendary_pool,
    pool_matches_shiny_intent,
    primary_itempool_key_for_catalog,
    synthetic_itempool_key_for_catalog,
)
from .raid3_content import (
    RAID3_CATALOG_KEYS,
    RAID3_PRIMARY_POOL_OVERRIDES,
    primary_itempool_key_for_catalog as raid3_primary_pool,
)

MOD_DIR = Path(__file__).resolve().parent
REF_DIR = MOD_DIR / "data" / "reference"
PEARL_SERIALS = REF_DIR / "pearl_spawn_serials.json"
NCS_SERIALS = REF_DIR / "ncs_shiny_serials.json"
ECHO4 = MOD_DIR.parent.parent / "shiny_serials.json"

_GENERIC_PEARL_ITEMPOOLS = frozenset(
    {
        "itempool_ar_06_pearl",
        "itempool_ps_06_pearl",
        "itempool_sm_06_pearl",
        "itempool_sg_06_pearl",
        "itempool_sr_06_pearl",
    }
)

_NATIVE_POOLS: dict[str, str] | None = None
_SERIAL_INDEX: dict[str, tuple[str, str]] | None = None


@dataclass(slots=True)
class SpawnResult:
    ok: bool
    method: str
    detail: str


def _norm_pool_key(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(name or "").strip().lower()).strip("_")


def _is_generic_pearl_itempool(pool_name: str) -> bool:
    return str(pool_name or "").strip().lower() in _GENERIC_PEARL_ITEMPOOLS


def _load_native_pools() -> dict[str, str]:
    global _NATIVE_POOLS
    if _NATIVE_POOLS is not None:
        return dict(_NATIVE_POOLS)
    index: dict[str, str] = {}
    for row in load_native_pool_rows():
        pool = str(row.get("itempool", "")).strip()
        if pool:
            index.setdefault(_norm_pool_key(pool), pool)
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


def _build_pool_catalog_aliases() -> dict[str, str]:
    from .raid2_content import (
        RAID2_NATIVE_POOL_OVERRIDES,
        RAID2_PRIMARY_POOL_OVERRIDES,
        RAID2_SHINY_POOL_OVERRIDES,
    )

    out: dict[str, str] = {}
    for catalog, pool in {
        **RAID2_PRIMARY_POOL_OVERRIDES,
        **RAID2_SHINY_POOL_OVERRIDES,
        **RAID2_NATIVE_POOL_OVERRIDES,
        **RAID3_PRIMARY_POOL_OVERRIDES,
    }.items():
        norm = _norm_pool_key(pool)
        if norm:
            out[norm] = catalog
    out.setdefault("itempool_fishgrenade_slippy", "tor_grenade_gadget_comp_05_legendary_slippy")
    return out


_POOL_CATALOG_ALIASES: dict[str, str] = _build_pool_catalog_aliases()


def _load_serial_index() -> dict[str, tuple[str, str]]:
    global _SERIAL_INDEX
    if _SERIAL_INDEX is not None:
        return dict(_SERIAL_INDEX)

    out: dict[str, tuple[str, str]] = {}

    def ingest(path: Path, source: str) -> None:
        doc = read_mod_json(path)
        if isinstance(doc, dict) and isinstance(doc.get("by_catalog_key"), dict):
            for catalog_key, row in doc["by_catalog_key"].items():
                if not isinstance(row, dict):
                    continue
                serial = str(row.get("serial", "")).strip()
                if serial.startswith("@U"):
                    out[str(catalog_key).strip().lower()] = (serial, source)
                extras = row.get("serials")
                if isinstance(extras, list):
                    for item in extras:
                        s = item if isinstance(item, str) else str(item.get("serial", ""))
                        s = str(s).strip()
                        if s.startswith("@U"):
                            out.setdefault(str(catalog_key).strip().lower(), (s, source))
            return
        rows = doc if isinstance(doc, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("id", "")).strip().lower()
            serial = str(row.get("serial", "")).strip()
            if sid and serial.startswith("@U"):
                out[sid] = (serial, source)

    ingest(PEARL_SERIALS, "pearl_spawn")
    ingest(NCS_SERIALS, "ncs_shiny")
    ingest(ECHO4, "echo4_shiny")
    _SERIAL_INDEX = out
    return dict(out)


def catalog_key_from_pool(
    pool_name: str,
    pool_data: Mapping[str, Any] | None = None,
) -> str | None:
    data = pool_data or {}
    for key in ("catalog_key", "source_comp"):
        val = str(data.get(key, "")).strip().lower()
        if not val:
            continue
        if val in RAID2_CATALOG_KEYS or val in RAID3_CATALOG_KEYS or "_comp_" in val:
            return val

    norm = _norm_pool_key(pool_name)
    alias = _POOL_CATALOG_ALIASES.get(norm)
    if alias:
        return alias

    low = str(pool_name or "").strip().lower()
    if not low:
        return None

    for catalog in sorted(RAID2_CATALOG_KEYS | RAID3_CATALOG_KEYS):
        for candidate in (
            synthetic_itempool_key_for_catalog(catalog),
            primary_itempool_key_for_catalog(catalog),
            raid3_primary_pool(catalog),
        ):
            if candidate and candidate.lower() == low:
                return catalog
        hints = RAID2_SPAWN_HINTS.get(catalog, {})
        native = hints.get("native_pool")
        if native and str(native).lower() == low:
            return catalog

    return None


def _find_native_pool_for_catalog(catalog: str, native_index: dict[str, str]) -> str | None:
    catalog = catalog.strip().lower()
    for cand in (
        native_pool_for_catalog(catalog),
        (RAID2_SPAWN_HINTS.get(catalog) or {}).get("native_pool"),
        primary_itempool_key_for_catalog(catalog),
        synthetic_itempool_key_for_catalog(catalog),
    ):
        resolved = _resolve_native_pool(str(cand or ""), native_index)
        if resolved:
            return resolved
    return None


def spawn_native_pool(pool_name: str, count: int = 1, level: int = 60) -> SpawnResult:
    """World-spawn via NexusConfigStoreItemPool (legacy — no loot verify)."""
    try:
        from .ncs_pool_spawn import spawn_legacy_itempool

        resolved = _resolve_native_pool(pool_name, _load_native_pools()) or str(pool_name).strip()
        spawned, err = spawn_legacy_itempool([resolved], count=count, level=level)
        if spawned > 0:
            return SpawnResult(True, "ncs_pool", resolved)
        return SpawnResult(False, "ncs_pool", err or "spawn failed")
    except Exception as exc:  # noqa: BLE001
        return SpawnResult(False, "ncs_pool", str(exc)[:240])


def _native_pool_candidates(
    pool_name: str,
    pool_data: Mapping[str, Any] | None,
) -> list[str]:
    from .comp_spawn_catalog import is_synthetic_named_pearl_pool

    names: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        name = str(value or "").strip()
        low = name.lower()
        if not name or low in seen:
            return
        if is_synthetic_named_pearl_pool(name):
            if not (isinstance(pool_data, Mapping) and pool_data.get("__native_store")):
                return
        seen.add(low)
        names.append(name)

    catalog = catalog_key_from_pool(pool_name, pool_data)
    if catalog:
        hints = RAID2_SPAWN_HINTS.get(catalog, {})
        if hints.get("native_pool"):
            add(hints["native_pool"])
        add(native_pool_for_catalog(catalog))
        if catalog in RAID3_CATALOG_KEYS:
            add(raid3_primary_pool(catalog))
        else:
            add(primary_itempool_key_for_catalog(catalog))

    if isinstance(pool_data, Mapping):
        add(pool_data.get("itempool"))
        if pool_data.get("__native_store"):
            add(pool_data.get("itempool") or pool_name)

    add(pool_name)
    resolved = _resolve_native_pool(pool_name, _load_native_pools())
    if resolved:
        add(resolved)
    return names


def try_ncs_native_for_pool(
    pool_name: str,
    pool_data: Mapping[str, Any] | None,
    *,
    count: int = 1,
    level: int = 60,
) -> SpawnResult:
    """Try registered NexusConfigStoreItemPool names."""
    for cand in _native_pool_candidates(pool_name, pool_data):
        if is_broad_classmod_legendary_pool(cand):
            continue
        hit = spawn_native_pool(cand, count=count, level=level)
        if hit.ok:
            return hit
    return SpawnResult(False, "ncs_native_pool", "no registered native itempool")


try_squ1ggs_native_for_pool = try_ncs_native_for_pool


def _spawn_serials_ground(catalog: str, count: int = 1) -> SpawnResult:
    """Try every bundled @U for a catalog — ground drop only (never mail/backpack)."""
    serials = serials_for_catalog(catalog.strip().lower())
    last = "no @U serial path"
    for index, serial in enumerate(serials):
        hit = spawn_serial(serial, count=count, ground_only=True)
        if hit.ok:
            tag = "serial_ground" if index == 0 else f"serial_ground_alt{index + 1}"
            return SpawnResult(True, tag, hit.detail)
        last = hit.detail
    return SpawnResult(False, "serial_ground", last)


def try_serial_backup_for_pool(
    pool_name: str,
    pool_data: Mapping[str, Any] | None,
    *,
    count: int = 1,
    level: int = 60,
) -> SpawnResult:
    _ = level
    catalog = catalog_key_from_pool(pool_name, pool_data)
    if catalog and "_comp_06_pearl_" in catalog.strip().lower():
        ok, method = try_spawn_catalog_via_serial(catalog, count=count)
        if ok:
            return SpawnResult(True, method, catalog)
        hit = _spawn_serials_ground(catalog, count=count)
        if hit.ok:
            return hit
        return SpawnResult(False, "serial_backup", method or hit.detail or "pearl serial ground failed")
    if catalog:
        ok, method = try_spawn_catalog_via_serial(catalog, count=count)
        if ok:
            return SpawnResult(True, method, catalog)
        hit = _spawn_serials_ground(catalog, count=count)
        if hit.ok:
            return hit

        sid = str((RAID2_SPAWN_HINTS.get(catalog) or {}).get("serial_id", "")).strip().lower()
        if sid:
            idx = _load_serial_index()
            hit_row = idx.get(sid)
            if hit_row:
                hit = spawn_serial(hit_row[0], count=count, ground_only="_comp_06_pearl_" in catalog)
                if hit.ok:
                    return SpawnResult(True, f"serial_backup_{hit_row[1]}", hit_row[0][:48])

    return SpawnResult(False, "serial_backup", "no @U serial path")


def deliver_catalog_serial_ground_only(
    catalog_key: str,
    count: int = 1,
) -> tuple[bool, str]:
    """Ground loot only — Item Spawner never uses mail/backpack fallback."""
    catalog = str(catalog_key or "").strip().lower()
    if not catalog:
        return False, "no catalog"
    ok, method = try_spawn_catalog_via_serial(catalog, count=count)
    if ok:
        return True, method
    serials = serials_for_catalog(catalog)
    if not serials:
        return False, method or "no_pearl_serial"
    return False, method or "ground @U serial failed"


def deliver_pearl_serial_resilient(
    catalog_key: str,
    count: int = 1,
) -> tuple[bool, str]:
    """Ground @U only — never loyalty mail for pearls."""
    return deliver_catalog_serial_ground_only(catalog_key, count=count)


def deliver_catalog_serial_resilient(
    catalog_key: str,
    count: int = 1,
) -> tuple[bool, str]:
    """Mail/backpack only when explicitly enabled — otherwise ground-only."""
    import os

    allow_mail = os.environ.get("BL4_IS_ALLOW_SERIAL_BACKUP", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not allow_mail:
        return deliver_catalog_serial_ground_only(catalog_key, count=count)
    catalog = str(catalog_key or "").strip().lower()
    if not catalog:
        return False, "no catalog"
    ok, method = try_spawn_catalog_via_serial(catalog, count=count)
    if ok:
        return True, method
    serials = serials_for_catalog(catalog)
    if not serials:
        return False, method or "no_pearl_serial"
    try:
        from .pearl_serial_spawn import try_deliver_serial_comprehensive

        for serial in serials:
            ok2, via = try_deliver_serial_comprehensive(
                str(serial), count, prefer_ground=True, ground_only=True
            )
            if ok2:
                return True, via
            ok2, via = try_deliver_serial_comprehensive(str(serial), count, prefer_ground=False)
            if ok2:
                return True, via
    except Exception:
        pass
    for serial in serials:
        if try_deliver_serial(str(serial), count):
            return True, "serial_backpack"
    try:
        from ..serial_rewards import grant_serials_via_loyalty_rewards

        n = max(1, min(int(count), 32))
        for serial in serials[:1]:
            for _ in range(n):
                grant_serials_via_loyalty_rewards([str(serial)], all_players=False)
        return True, "loyalty_mail"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]


def spawn_serial(serial: str, count: int = 1, *, ground_only: bool = False) -> SpawnResult:
    serial = str(serial or "").strip()
    if not serial.startswith("@U"):
        return SpawnResult(False, "serial_drop", "Invalid serial")
    from .pearl_serial_spawn import try_deliver_serial_comprehensive

    ok, via = try_deliver_serial_comprehensive(
        serial, count, prefer_ground=True, ground_only=ground_only
    )
    if ok:
        method = "serial_ground" if ground_only or "spawn" in via.lower() else "serial_drop"
        return SpawnResult(True, method, serial[:48])
    detail = "ground FromSerial failed" if ground_only else "FromSerial RPC unavailable"
    return SpawnResult(False, "serial_drop", detail)


def _catalog_pool_candidates(
    catalog: str,
    *,
    wants_shiny: bool = False,
) -> list[str]:
    from .comp_spawn_catalog import catalog_spawn_row

    row = catalog_spawn_row(catalog)
    seen: set[str] = set()
    out: list[str] = []

    def add(value: Any) -> None:
        pool = str(value or "").strip()
        low = pool.lower()
        if not pool or low in seen:
            return
        if _is_generic_pearl_itempool(pool):
            return
        if not pool_matches_shiny_intent(pool, wants_shiny):
            return
        if is_broad_classmod_legendary_pool(pool):
            return
        seen.add(low)
        out.append(pool)

    for cand in (
        row.get("native_pool"),
        row.get("itempool"),
        (RAID2_SPAWN_HINTS.get(catalog) or {}).get("native_pool"),
        native_pool_for_catalog(catalog),
        primary_itempool_key_for_catalog(catalog, wants_shiny=wants_shiny),
        raid3_primary_pool(catalog) if catalog in RAID3_CATALOG_KEYS else None,
    ):
        add(cand)
    return out


def spawn_raid2_catalog(
    catalog_key: str,
    count: int = 1,
    level: int = 60,
    wants_shiny: bool = False,
) -> SpawnResult:
    """Raid 2: live NCS pool at feet → pearl inline → ground @U. No mail."""
    catalog = catalog_key.strip().lower()
    if catalog not in RAID2_CATALOG_KEYS:
        return SpawnResult(False, "raid2_spawn", f"not a Raid 2 catalog key: {catalog}")

    last = "no delivery path"
    is_pearl = "_comp_06_pearl_" in catalog and not wants_shiny

    for pool in _catalog_pool_candidates(catalog, wants_shiny=wants_shiny):
        pool_hit = spawn_native_pool(pool, count=count, level=level)
        if pool_hit.ok:
            return SpawnResult(True, pool_hit.method, pool_hit.detail)
        last = pool_hit.detail

    if is_pearl:
        comp_hit = try_spawn_pearl_comp_world(
            catalog,
            count=count,
            level=level,
            pool_name=primary_itempool_key_for_catalog(catalog, wants_shiny=wants_shiny),
            drop_only=False,
        )
        if comp_hit.ok:
            return SpawnResult(True, comp_hit.method, comp_hit.detail or catalog)
        last = str(comp_hit.detail or last)

    ok, method = try_spawn_catalog_via_serial(catalog, count=count)
    if ok:
        return SpawnResult(True, method, catalog)
    if method and method != "no_pearl_serial":
        last = method

    hit = _spawn_serials_ground(catalog, count=count)
    if hit.ok:
        return hit
    if hit.detail:
        last = hit.detail

    sid = str((RAID2_SPAWN_HINTS.get(catalog) or {}).get("serial_id", "")).strip().lower()
    if sid:
        idx = _load_serial_index()
        hit_row = idx.get(sid)
        if hit_row:
            hit = spawn_serial(hit_row[0], count=count, ground_only=is_pearl)
            if hit.ok:
                return SpawnResult(True, f"serial_backup_{hit_row[1]}", hit_row[0][:48])
            last = hit.detail

    return SpawnResult(False, "raid2_spawn", last)


def spawn_raid3_catalog(
    catalog_key: str,
    count: int = 1,
    level: int = 60,
) -> SpawnResult:
    """Raid 3: live native shiny pool via NCS."""
    catalog = catalog_key.strip().lower()
    if catalog not in RAID3_CATALOG_KEYS:
        return SpawnResult(False, "raid3_spawn", f"not a Raid 3 catalog key: {catalog}")

    last = "no delivery path"
    for pool in _catalog_pool_candidates(catalog, wants_shiny=True):
        hit = spawn_native_pool(pool, count=count, level=level)
        if hit.ok:
            return SpawnResult(True, hit.method, hit.detail)
        last = hit.detail

    return SpawnResult(False, "raid3_spawn", last)


def _try_inline_comp_spawn(
    catalog: str,
    primary_pool: str,
    count: int,
    level: int,
) -> SpawnResult | None:
    """Try inv-comp ground drop for pearlescent / classmod catalog rows."""
    catalog_l = str(catalog or "").strip().lower()
    if "_comp_06_pearl_" in catalog_l:
        hit = try_spawn_pearl_comp_world(
            catalog_l,
            count=count,
            level=level,
            pool_name=primary_pool or None,
        )
        return hit if hit.ok else hit

    if catalog_l.startswith("classmod_") and is_dedicated_classmod_inline_pool(
        str(primary_pool or "")
    ):
        from .classmod_comp_spawn import try_spawn_classmod_comp_world

        hit = try_spawn_classmod_comp_world(
            catalog_l,
            count=count,
            level=level,
            pool_name=primary_pool or None,
        )
        return hit if hit is not None else None

    try:
        import bl4_item_spawner as bis

        pool = str(primary_pool or "").strip()
        pool_data = bis.CONTROLLER._get_itempool_payload(pool) if pool else None
        if isinstance(pool_data, dict) and (
            pool_data.get("handle_variants")
            or pool_data.get("items")
            or pool_data.get("__synthetic")
        ):
            bis.CONTROLLER._spawn_from_inline_itempool(pool_data, count, level)
            return SpawnResult(True, "ncs_comp_handle", pool)
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        return SpawnResult(False, "inline_comp", str(exc)[:240])

    pool = str(primary_pool or "").strip()
    if not pool:
        return None
    hit = spawn_native_pool(pool, count=count, level=level)
    if hit.ok:
        return hit
    return SpawnResult(False, "inline_comp", hit.detail or "inline comp spawn failed")
