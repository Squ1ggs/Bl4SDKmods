"""Console commands to manually test each pearl spawn path (no UI queue / verify batch)."""

from __future__ import annotations

import argparse

from mods_base import command
from unrealsdk import logging

from .item_pool_spawning import (
    DEFAULT_ITEM_LEVEL,
    _escalate_pearl_catalog_spawn,
    _spawn_generic_pearl_pool_entries,
    _try_direct_generic_pearl_ncs,
)

_WEAPON_TYPES = ("ps", "sm", "sg", "sr", "ar")
_GENERIC_BY_TYPE = {
    "ps": "itempool_ps_06_pearl",
    "sm": "itempool_sm_06_pearl",
    "sg": "itempool_sg_06_pearl",
    "sr": "itempool_sr_06_pearl",
    "ar": "itempool_ar_06_pearl",
}


def _info(msg: str) -> None:
    logging.info(f"[SQBT pearl probe] {msg}")


def _err(msg: str) -> None:
    logging.warning(f"[SQBT pearl probe] {msg}")


def _resolve_catalog(token: str) -> tuple[str, str, str]:
    from .item_spawn.pearlescent_manifest import PEARLESCENT_ROWS, pearlescent_row

    raw = str(token or "").strip()
    if not raw:
        raise ValueError("missing catalog / title token")
    low = raw.lower()
    for row in PEARLESCENT_ROWS:
        if low in (row["catalog_key"], row["title"].lower(), row["itempool"].lower()):
            return row["catalog_key"], row["itempool"], row["title"]
        if low in row["title"].lower().replace("'", ""):
            return row["catalog_key"], row["itempool"], row["title"]
    hit = pearlescent_row(low)
    if hit:
        return hit["catalog_key"], hit["itempool"], hit["title"]
    if "_comp_" in low:
        return low, "", raw
    raise ValueError(f"unknown pearl '{raw}' — run sqbt_pearl_list")


def _resolve_generic_pool(token: str) -> str:
    low = str(token or "").strip().lower()
    if low in _GENERIC_BY_TYPE:
        return _GENERIC_BY_TYPE[low]
    if low.startswith("itempool_") and "_06_pearl" in low:
        return low
    raise ValueError(f"expected ps|sm|sg|sr|ar or itempool_*_06_pearl, got {token!r}")


@command("sqbt_pearl_help", description="Pearl spawn manual test commands (one path at a time).")
def sqbt_pearl_help(_args: argparse.Namespace) -> None:
    _info("Manual pearl tests — stand on open ground, one command = one path:")
    _info("  sqbt_pearl_pool ps|sg|sm|sr|ar [level] [count]  — LIVE generic NCS only (Squ1ggs pool spawn)")
    _info("  sqbt_pearl_ncs <itempool_name> [level] [count]   — legacy SpawnInventoryFromItemPool")
    _info("  sqbt_pearl_merge <catalog|title> [level]         — dump merge inline only")
    _info("  sqbt_pearl_serial <catalog|title> [level]        — ground @U serial only")
    _info("  sqbt_pearl_shiny <catalog|title> [level]         — *_shiny pool only")
    _info("  sqbt_pearl_escalate <catalog|title> [level]      — full dump-first chain")
    _info("  sqbt_pearl_generic ps|sg|… [level] [count]       — same as UI Pearl Pool button")
    _info("  sqbt_pearl_list [ps|sm|sg|sr|ar]                 — catalog keys + pools to probe")
    _info("  sqbt_pearl_readiness                             — probe-only LIVE/DEAD (no drops)")
    _info("  sqbt_spawn_dump / sqbt_spawn_log_clear             — log results after tests")


@command("sqbt_pearl_list", description="List pearlescents for manual sqbt_pearl_* probes.")
def sqbt_pearl_list(args: argparse.Namespace) -> None:
    from .item_spawn.pearlescent_manifest import PEARLESCENT_ROWS, generic_pool_for_weapon_type

    filt = str(getattr(args, "type", "") or "").strip().lower()
    rows = PEARLESCENT_ROWS
    if filt:
        rows = [r for r in rows if r["weapon_type"] == filt]
    for row in rows:
        gp = generic_pool_for_weapon_type(row["weapon_type"]) or "?"
        _info(
            f"[{row['weapon_type'].upper()}|{row['comp_class']}] {row['title']} "
            f"catalog={row['catalog_key']} pool={row['itempool']} generic={gp}"
        )


sqbt_pearl_list.add_argument("type", nargs="?", default="", help="ps|sm|sg|sr|ar filter")


@command("sqbt_pearl_pool", description="Direct generic NCS: itempool_ps_06_pearl etc. (Squ1ggs pool spawn).")
def sqbt_pearl_pool(args: argparse.Namespace) -> None:
    try:
        pool = _resolve_generic_pool(str(getattr(args, "target", "")))
    except ValueError as exc:
        _err(str(exc))
        return
    level = max(1, int(getattr(args, "level", DEFAULT_ITEM_LEVEL) or DEFAULT_ITEM_LEVEL))
    count = max(1, min(int(getattr(args, "count", 1) or 1), 32))
    hit = _try_direct_generic_pearl_ncs(pool, level=level, count=count)
    if hit:
        _info(f"OK direct NCS {pool} x{hit} @ {level}")
    else:
        _err(f"FAIL direct NCS {pool} — try sqbt_pearl_generic or sqbt_pearl_escalate on a named row")


sqbt_pearl_pool.add_argument("target", help="ps|sm|sg|sr|ar")
sqbt_pearl_pool.add_argument("level", nargs="?", type=int, default=DEFAULT_ITEM_LEVEL)
sqbt_pearl_pool.add_argument("count", nargs="?", type=int, default=1)


@command("sqbt_pearl_ncs", description="Named itempool via legacy NCS only.")
def sqbt_pearl_ncs(args: argparse.Namespace) -> None:
    pool = str(getattr(args, "pool", "") or "").strip()
    if not pool:
        _err("Usage: sqbt_pearl_ncs itempool_tor_ps_06_pearl_herald [level] [count]")
        return
    level = max(1, int(getattr(args, "level", DEFAULT_ITEM_LEVEL) or DEFAULT_ITEM_LEVEL))
    count = max(1, min(int(getattr(args, "count", 1) or 1), 32))
    from .item_spawn.ncs_pool_spawn import spawn_legacy_itempool

    spawned, err = spawn_legacy_itempool([pool], count=count, level=level)
    if spawned > 0:
        _info(f"OK legacy NCS {pool} x{spawned} @ {level}")
    else:
        _err(f"FAIL legacy NCS {pool}: {err or 'silent empty'}")


sqbt_pearl_ncs.add_argument("pool", help="exact itempool id")
sqbt_pearl_ncs.add_argument("level", nargs="?", type=int, default=DEFAULT_ITEM_LEVEL)
sqbt_pearl_ncs.add_argument("count", nargs="?", type=int, default=1)


@command("sqbt_pearl_merge", description="Pearl dump merge inline only.")
def sqbt_pearl_merge(args: argparse.Namespace) -> None:
    try:
        catalog, pool, title = _resolve_catalog(str(getattr(args, "target", "")))
    except ValueError as exc:
        _err(str(exc))
        return
    level = max(1, int(getattr(args, "level", DEFAULT_ITEM_LEVEL) or DEFAULT_ITEM_LEVEL))
    from .item_spawn.pearl_comp_spawn import try_spawn_pearl_comp_world

    hit = try_spawn_pearl_comp_world(catalog, count=1, level=level, pool_name=pool or None, drop_only=True)
    if hit.ok:
        _info(f"OK merge {title} ({catalog}) — {hit.method}: {hit.detail}")
    else:
        _err(f"FAIL merge {title}: {hit.detail}")


sqbt_pearl_merge.add_argument("target", help="catalog_key or display title")
sqbt_pearl_merge.add_argument("level", nargs="?", type=int, default=DEFAULT_ITEM_LEVEL)


@command("sqbt_pearl_serial", description="Pearl ground @U serial only.")
def sqbt_pearl_serial(args: argparse.Namespace) -> None:
    try:
        catalog, _pool, title = _resolve_catalog(str(getattr(args, "target", "")))
    except ValueError as exc:
        _err(str(exc))
        return
    level = max(1, int(getattr(args, "level", DEFAULT_ITEM_LEVEL) or DEFAULT_ITEM_LEVEL))
    from .item_spawn.pearl_serial_spawn import try_spawn_catalog_via_serial

    ok, method = try_spawn_catalog_via_serial(catalog, count=1)
    if ok:
        _info(f"OK serial {title} ({catalog}) via {method} @ {level}")
    else:
        _err(f"FAIL serial {title}: {method}")


sqbt_pearl_serial.add_argument("target", help="catalog_key or display title")
sqbt_pearl_serial.add_argument("level", nargs="?", type=int, default=DEFAULT_ITEM_LEVEL)


@command("sqbt_pearl_shiny", description="Pearl *_shiny NCS pool only.")
def sqbt_pearl_shiny(args: argparse.Namespace) -> None:
    try:
        catalog, pool, title = _resolve_catalog(str(getattr(args, "target", "")))
    except ValueError as exc:
        _err(str(exc))
        return
    level = max(1, int(getattr(args, "level", DEFAULT_ITEM_LEVEL) or DEFAULT_ITEM_LEVEL))
    from .item_spawn.shiny_pearl_spawn import spawn_named_pearl_shiny

    attempted, verified, method, shiny_pool = spawn_named_pearl_shiny(catalog, pool, count=1, level=level)
    if attempted and verified:
        _info(f"OK shiny {title} via {method} pool={shiny_pool}")
    elif attempted:
        _err(f"FAIL shiny {title} pool={shiny_pool} (API ok, no feet loot)")
    else:
        _err(f"FAIL shiny {title}: no shiny pool")


sqbt_pearl_shiny.add_argument("target", help="catalog_key or display title")
sqbt_pearl_shiny.add_argument("level", nargs="?", type=int, default=DEFAULT_ITEM_LEVEL)


@command("sqbt_pearl_escalate", description="Full dump-first pearl chain for one catalog row.")
def sqbt_pearl_escalate(args: argparse.Namespace) -> None:
    try:
        catalog, pool, title = _resolve_catalog(str(getattr(args, "target", "")))
    except ValueError as exc:
        _err(str(exc))
        return
    level = max(1, int(getattr(args, "level", DEFAULT_ITEM_LEVEL) or DEFAULT_ITEM_LEVEL))
    try:
        n = _escalate_pearl_catalog_spawn(catalog, pool, level=level, title=title)
        _info(f"OK escalate {title} x{n} @ {level}")
    except Exception as exc:  # noqa: BLE001
        _err(f"FAIL escalate {title}: {exc}")


sqbt_pearl_escalate.add_argument("target", help="catalog_key or display title")
sqbt_pearl_escalate.add_argument("level", nargs="?", type=int, default=DEFAULT_ITEM_LEVEL)


@command("sqbt_pearl_generic", description="Same paths as UI PS/SG/SM/SR/AR Pearl Pool button.")
def sqbt_pearl_generic(args: argparse.Namespace) -> None:
    try:
        pool = _resolve_generic_pool(str(getattr(args, "target", "")))
    except ValueError as exc:
        _err(str(exc))
        return
    level = max(1, int(getattr(args, "level", DEFAULT_ITEM_LEVEL) or DEFAULT_ITEM_LEVEL))
    count = max(1, min(int(getattr(args, "count", 1) or 1), 32))
    try:
        n = _spawn_generic_pearl_pool_entries(pool, level=level, count=count)
        _info(f"OK generic pool {pool} x{n} @ {level}")
    except Exception as exc:  # noqa: BLE001
        _err(f"FAIL generic pool {pool}: {exc}")


sqbt_pearl_generic.add_argument("target", help="ps|sm|sg|sr|ar")
sqbt_pearl_generic.add_argument("level", nargs="?", type=int, default=DEFAULT_ITEM_LEVEL)
sqbt_pearl_generic.add_argument("count", nargs="?", type=int, default=1)


@command("sqbt_pearl_readiness", description="Probe pearl paths LIVE/DEAD without spawning loot.")
def sqbt_pearl_readiness(_args: argparse.Namespace) -> None:
    from .item_spawn.pearlescent_manifest import PEARLESCENT_ROWS
    from .item_spawn.pearl_comp_spawn import merge_payload_for_pearl_catalog
    from .item_spawn.pearl_serial_spawn import serials_for_catalog
    from .item_spawn.squ1ggs_spawn_bridge import _load_native_pools, _resolve_native_pool

    native = _load_native_pools()
    live = dead = 0
    for row in PEARLESCENT_ROWS:
        catalog = row["catalog_key"]
        pool = row["itempool"]
        merge = bool(merge_payload_for_pearl_catalog(catalog))
        serial = bool(serials_for_catalog(catalog))
        ncs = bool(_resolve_native_pool(pool, native) or _resolve_native_pool(pool, native))
        flags = []
        if merge:
            flags.append("merge")
        if serial:
            flags.append("@U")
        if ncs:
            flags.append("ncs")
        status = "LIVE" if flags else "DEAD"
        if flags:
            live += 1
        else:
            dead += 1
        line = f"  {status}  {row['title']} ({row['comp_class']}) — {', '.join(flags) or 'no dump path'}"
        if status == "LIVE":
            _info(line)
        else:
            _err(line)
    _info(f"Readiness: {live}/{len(PEARLESCENT_ROWS)} have at least one bundled path.")
    _info("comp_class pearl_world (Abyss, Gomie, Raiden…) often need NCS or DLC — merge may be missing.")
