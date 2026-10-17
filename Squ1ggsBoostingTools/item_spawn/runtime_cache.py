"""Cached runtime UObject lookups for item spawn (avoid find_all on every pool call)."""

from __future__ import annotations

from typing import Any

import unrealsdk
from mods_base import ENGINE, get_pc
from unrealsdk.unreal import UObject

_pool_store: UObject | None = None
_cached_pc: UObject | None = None
_cached_world: UObject | None = None
_native_pools: dict[str, str] | None = None


def invalidate_spawn_runtime_cache() -> None:
    global _pool_store, _cached_pc, _cached_world, _native_pools
    _pool_store = None
    _cached_pc = None
    _cached_world = None
    _native_pools = None


def get_nexus_config_store_item_pool() -> UObject:
    global _pool_store
    if _pool_store is not None:
        return _pool_store
    configs = unrealsdk.find_all("NexusConfigStoreItemPool", False)
    if not configs:
        raise RuntimeError("NexusConfigStoreItemPool not found.")
    _pool_store = list(configs)[-1]
    return _pool_store


def iter_nexus_config_stores() -> list[UObject]:
    """CDO plus every live item-pool config layer, de-duplicated."""
    out: list[UObject] = []
    seen: set[int] = set()

    def add(obj: UObject | None) -> None:
        if obj is None:
            return
        key = id(obj)
        try:
            key = int(getattr(obj, "_get_address", lambda: 0)() or 0) or key
        except Exception:
            pass
        if key in seen:
            return
        seen.add(key)
        out.append(obj)

    try:
        add(unrealsdk.find_class("NexusConfigStoreItemPool").ClassDefaultObject)
    except Exception:
        pass
    try:
        for config in reversed(list(unrealsdk.find_all("NexusConfigStoreItemPool", False) or [])):
            add(config)
    except Exception:
        pass
    return out


def get_runtime_pc() -> UObject | None:
    global _cached_pc
    pc = get_pc()
    if pc is not None:
        _cached_pc = pc
        return pc
    if _cached_pc is not None:
        return _cached_pc
    for class_name in ("OakPlayerController", "PlayerController"):
        try:
            objects = unrealsdk.find_all(class_name, False) or []
        except Exception:  # noqa: BLE001
            continue
        for obj in objects:
            if obj is not None:
                _cached_pc = obj
                return obj
    return None


def get_world() -> UObject | None:
    global _cached_world
    viewport = getattr(ENGINE, "GameViewport", None)
    world = getattr(viewport, "World", None)
    if world is not None:
        _cached_world = world
        return world
    if _cached_world is not None:
        return _cached_world
    pc = get_runtime_pc()
    if pc is None:
        return None
    candidate = getattr(pc, "World", None)
    if candidate is not None:
        _cached_world = candidate
        return candidate
    pawn = getattr(pc, "Pawn", None)
    candidate = getattr(pawn, "World", None) if pawn is not None else None
    if candidate is not None:
        _cached_world = candidate
    return candidate


def load_native_pools_index(json_path: Any) -> dict[str, str]:
    """Load + cache ncs_native_itempools.json index (was re-read from disk every spawn)."""
    global _native_pools
    if _native_pools is not None:
        return _native_pools
    import json
    import re
    from pathlib import Path

    path = Path(json_path)
    if not path.is_file():
        _native_pools = {}
        return _native_pools
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        _native_pools = {}
        return _native_pools
    out: dict[str, str] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            pool = str(row.get("itempool", "")).strip()
            if pool:
                out[re.sub(r"[^a-z0-9_]+", "_", pool.lower()).strip("_")] = pool
    _native_pools = out
    return _native_pools
