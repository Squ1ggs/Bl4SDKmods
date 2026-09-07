"""Named pearlescent spawn — delegates to the same NCS path as legendaries."""

from __future__ import annotations


def delivery_skips_verify(method: str, *, loot_verified: bool = False) -> bool:
    """Only skip deferred verify when feet loot was confirmed in-frame."""
    return bool(loot_verified)


def try_pearl_loyalty_mail(catalog_key: str) -> tuple[bool, str]:
    catalog = str(catalog_key or "").strip().lower()
    from .pearl_serial_spawn import serials_for_catalog

    serials = serials_for_catalog(catalog)
    if not serials:
        return False, "no_serial"
    try:
        from ..serial_rewards import grant_serials_via_loyalty_rewards

        n = grant_serials_via_loyalty_rewards([serials[0]], all_players=False)
        if n > 0:
            return True, serials[0][:48]
    except Exception as exc:
        return False, str(exc)[:120]
    return False, "grant_failed"


def ncs_pool_try_order(catalog: str, manifest_pool: str = "") -> list[str]:
    """Pool order for diagnostics — live dump pool first."""
    from .pearlescent_manifest import (
        PEARL_BASE_LEGENDARY_POOLS,
        PEARL_SHINY_POOLS,
        dump_native_pool_for_catalog,
        named_pearl_ncs_pool_try_order,
    )

    out: list[str] = []
    seen: set[str] = set()
    cat = str(catalog or "").strip().lower()
    manifest = str(manifest_pool or "").strip()

    def add(name: str | None) -> None:
        pool = str(name or "").strip()
        if not pool.lower().startswith("itempool_"):
            return
        low = pool.lower()
        if low in seen:
            return
        seen.add(low)
        out.append(pool)

    if manifest:
        add(manifest)
    if cat:
        add(dump_native_pool_for_catalog(cat))
        add(PEARL_BASE_LEGENDARY_POOLS.get(cat))
        add(PEARL_SHINY_POOLS.get(cat))
    for pool in named_pearl_ncs_pool_try_order(cat, manifest):
        add(pool)
    return out


def spawn_named_pearl(
    catalog_key: str,
    *,
    level: int = 60,
    count: int = 1,
    display: str = "",
) -> tuple[int, str, str, bool]:
    """
    Spawn one named pearl using the legendary NCS / BL4 / @U escalation chain.
    """
    from ..item_pool_spawning import (
        _ensure_entry_catalog,
        _pearl_spawn_delivery_info,
        _spawn_pearl_child_entry,
    )
    from .pearlescent_manifest import pearlescent_row

    catalog = str(catalog_key or "").strip().lower()
    if not catalog:
        raise RuntimeError("missing pearl catalog_key")

    row = pearlescent_row(catalog)
    label = str(display or (row["title"] if row else catalog)).strip()
    entry = _ensure_entry_catalog(
        {
            "catalog_key": catalog,
            "itempool": str(row["itempool"] if row else "").strip(),
            "display_name": label,
            "category": "Pearl",
        }
    )
    want = max(1, int(count))
    spawned = _spawn_pearl_child_entry(entry, level=level, count=want)
    delivery = _pearl_spawn_delivery_info()
    method = str(delivery.get("method") or "ncs_pool").strip()
    detail = str(delivery.get("detail") or entry.get("itempool") or catalog).strip()
    verified = str(delivery.get("loot_verified") or "") == "1"
    return spawned, method, detail, verified
