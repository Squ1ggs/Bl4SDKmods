"""Optional delegate to the standalone BL4 Item Spawner mod (off by default when both load)."""

from __future__ import annotations

import os
from typing import Any

_DELEGATE_CHOICE: bool | None = None


def bl4_item_spawner_available() -> bool:
    try:
        import bl4_item_spawner as _bis  # noqa: F401

        return True
    except ImportError:
        return False


def bl4_delegate_enabled() -> bool:
    """
    When bl4_item_spawner is installed, SQBT still uses its bundled spawn path unless
    SQBT_USE_BL4_SPAWNER=1. Running both without this avoids double routers / false OKs.
    """
    global _DELEGATE_CHOICE
    if _DELEGATE_CHOICE is None:
        raw = os.environ.get("SQBT_USE_BL4_SPAWNER", "0").strip().lower()
        _DELEGATE_CHOICE = raw in ("1", "true", "yes", "on")
    return _DELEGATE_CHOICE and bl4_item_spawner_available()


def try_bl4_item_spawner_pool(
    pool_name: str,
    *,
    count: int = 1,
    level: int = 60,
    display_name: str = "",
    category: str = "Other",
    skip_raid_bridge: bool = False,
) -> int | None:
    """
    Run BL4 Item Spawner's spawn pipeline when SQBT_USE_BL4_SPAWNER=1.

    Returns spawn count when handled; None when delegate disabled or mod missing.
    """
    if not bl4_delegate_enabled():
        return None
    try:
        import bl4_item_spawner as bis
    except ImportError:
        return None

    pool = str(pool_name or "").strip()
    if not pool:
        raise RuntimeError("No loot pool name for the external pool backend.")

    label = str(display_name or pool).strip().lstrip(">").strip() or pool
    n = max(1, min(int(count), 100))
    lvl = max(1, int(level))

    outcome = bis.CONTROLLER._run_pool_spawn_tracked(
        pool_name=pool,
        display_name=label,
        category=str(category or "Other"),
        count=n,
        level=lvl,
        skip_raid_bridge=bool(skip_raid_bridge),
    )
    if outcome.ok:
        return n
    raise RuntimeError(f"{label}: {outcome.detail}")


def pool_name_for_entry(entry: dict[str, str], catalog: str = "") -> str:
    """Best pool id for BL4 / bundled spawn from a UI row."""
    pool = str(entry.get("itempool") or "").strip()
    if pool:
        return pool
    catalog = str(catalog or entry.get("catalog_key") or "").strip().lower()
    if catalog:
        try:
            from .raid2_content import primary_itempool_key_for_catalog

            primary = primary_itempool_key_for_catalog(catalog)
            if primary:
                return str(primary)
        except Exception:  # noqa: BLE001
            pass
        try:
            from .raid2_content import synthetic_itempool_key_for_catalog

            syn = synthetic_itempool_key_for_catalog(catalog)
            if syn:
                return str(syn)
        except Exception:  # noqa: BLE001
            pass
    return pool


def _is_pearl_spawn_entry(entry: dict[str, str], catalog: str = "") -> bool:
    catalog_l = str(catalog or entry.get("catalog_key") or "").strip().lower()
    if "_comp_06_pearl_" in catalog_l:
        return True
    pool_l = str(entry.get("itempool") or "").strip().lower()
    return "_06_pearl_" in pool_l and not pool_l.endswith("_pearl")


def try_bl4_item_spawner_entry(
    entry: dict[str, str],
    *,
    count: int = 1,
    level: int = 60,
    catalog: str = "",
) -> int | None:
    """Spawn one row through BL4 Item Spawner when delegate enabled."""
    pool = pool_name_for_entry(entry, catalog)
    if not pool:
        return None
    display = str(entry.get("display_name") or pool).strip()
    category = str(entry.get("category") or "Other")
    return try_bl4_item_spawner_pool(
        pool,
        count=count,
        level=level,
        display_name=display,
        category=category,
        skip_raid_bridge=False,
    )


def try_bl4_pearl_catalog_row(
    catalog_key: str,
    *,
    count: int = 1,
    level: int = 60,
) -> tuple[int, str] | None:
    """Named pearl via BL4 router — only when SQBT_USE_BL4_SPAWNER=1."""
    if not bl4_delegate_enabled():
        return None
    try:
        import bl4_item_spawner as bis
    except ImportError:
        return None

    catalog = str(catalog_key or "").strip().lower()
    if not catalog:
        raise RuntimeError("missing pearl catalog_key")
    n = max(1, min(int(count), 100))
    lvl = max(1, int(level))
    prepare_bl4_pearl_spawn_ui(level=lvl)
    bump_bl4_pearl_bulk_ring()
    from bl4_item_spawner.pearl_spawn_manifest import pearl_row_by_catalog

    row = pearl_row_by_catalog(catalog)
    pool = str((row or {}).get("itempool") or "").strip()
    if not pool:
        raise RuntimeError(f"no BL4 manifest pool for {catalog}")
    bis.CONTROLLER._spawn_named_pearl_pool(pool, n, lvl, catalog)
    method = str(getattr(bis.CONTROLLER, "_last_spawn_method", "bl4_pearl_router"))
    return n, method


def bl4_pearl_sync_available() -> bool:
    return bl4_delegate_enabled()


def try_bl4_generic_pearl_pool(
    pool_name: str,
    *,
    count: int = 1,
    level: int = 60,
) -> int | None:
    """Generic PS/SG/SM/SR/AR 06 Pearl — only when SQBT_USE_BL4_SPAWNER=1."""
    if not bl4_delegate_enabled():
        return None
    try:
        import bl4_item_spawner as bis
    except ImportError:
        return None

    pool = str(pool_name or "").strip()
    if not pool:
        raise RuntimeError("No generic pearl pool name")
    n = max(1, min(int(count), 100))
    lvl = max(1, int(level))
    prepare_bl4_pearl_spawn_ui(level=lvl)
    bis.CONTROLLER._spawn_generic_pearl_pool(pool, n, lvl)
    return n


def reset_bl4_pearl_bulk_ring() -> None:
    if not bl4_delegate_enabled():
        return
    try:
        import bl4_item_spawner as bis

        bis.CONTROLLER._pearl_bulk_ring_index = 0
    except Exception:  # noqa: BLE001
        pass


def bump_bl4_pearl_bulk_ring() -> None:
    if not bl4_item_spawner_available():
        return
    try:
        import bl4_item_spawner as bis

        bis.CONTROLLER._pearl_bulk_ring_index = (
            int(getattr(bis.CONTROLLER, "_pearl_bulk_ring_index", 0) or 0) + 1
        )
    except Exception:  # noqa: BLE001
        pass


def prepare_bl4_pearl_spawn_ui(*, level: int = 60) -> None:
    if not bl4_item_spawner_available():
        return
    try:
        import bl4_item_spawner as bis
    except ImportError:
        return
    ctrl = bis.CONTROLLER
    ctrl.ui.spawn_level = max(1, min(int(level), 999999))
    if str(getattr(ctrl.ui, "pattern_mode", "")).lower() != "custom":
        ctrl.ui.pattern_mode = "custom"


def try_bl4_pearl_catalog_escalate(
    catalog_key: str,
    *,
    count: int = 1,
    level: int = 60,
) -> tuple[int, str] | None:
    """
    BL4 dump-first pearl router when bl4_item_spawner is loaded.

    Does not require SQBT_USE_BL4_SPAWNER — uses the same merge → serial → NCS path
    that worked before SQBT routing changes.
    """
    if not bl4_item_spawner_available():
        return None
    catalog = str(catalog_key or "").strip().lower()
    if not catalog:
        return None
    try:
        import bl4_item_spawner as bis
    except ImportError:
        return None

    n = max(1, min(int(count), 100))
    lvl = max(1, int(level))
    prepare_bl4_pearl_spawn_ui(level=lvl)
    bump_bl4_pearl_bulk_ring()
    method = bis.CONTROLLER._spawn_pearl_catalog_row(
        catalog,
        count=n,
        level=lvl,
        skip_raid_bridge=True,
    )
    return n, str(method or "bl4_pearl_router")


def try_bl4_generic_pearl_pool_when_loaded(
    pool_name: str,
    *,
    count: int = 1,
    level: int = 60,
) -> int | None:
    """Generic type pool via BL4 inline merge expansion when the mod is loaded."""
    if not bl4_item_spawner_available():
        return None
    pool = str(pool_name or "").strip()
    if not pool:
        return None
    try:
        import bl4_item_spawner as bis
    except ImportError:
        return None

    n = max(1, min(int(count), 100))
    lvl = max(1, int(level))
    prepare_bl4_pearl_spawn_ui(level=lvl)
    bis.CONTROLLER._spawn_generic_pearl_pool(pool, n, lvl)
    return n
