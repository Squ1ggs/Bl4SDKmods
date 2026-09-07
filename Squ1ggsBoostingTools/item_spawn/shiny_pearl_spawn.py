"""Pearl shiny ground spawn — unlock phosphene cosmetics before NCS *_shiny pools."""

from __future__ import annotations

import re
from typing import Any

from .loot_verify import feet_loot_keys, unclaimed_loot_gain, verify_available
from .pearlescent_manifest import PEARL_SHINY_POOLS
from .shiny_pool_lookup import inline_payload_for_shiny, lookup_shiny_pool, serial_for_shiny_pool
from .spawn_pc import resolve_spawn_pc


def _feet_snapshot() -> tuple[Any | None, set[str]]:
    from .loot_verify import player_location_from_pc

    if not verify_available():
        return None, set()
    pc = resolve_spawn_pc()
    loc = player_location_from_pc(pc)
    if loc is None:
        return None, set()
    return loc, feet_loot_keys(loc)


def _feet_gained(before_loc: Any | None, before_keys: set[str]) -> bool:
    if before_loc is None or not verify_available():
        return False
    return bool(unclaimed_loot_gain(before_loc, before_keys))


def primary_shiny_pool_for_catalog(catalog_key: str, manifest_pool: str = "") -> str | None:
    """Dump-canonical *_shiny pool for one named pearl."""
    catalog = str(catalog_key or "").strip().lower()
    if catalog:
        hit = PEARL_SHINY_POOLS.get(catalog)
        if hit:
            return hit
    manifest = str(manifest_pool or "").strip()
    if manifest:
        low = manifest.lower()
        if low.endswith("_shiny"):
            return manifest
        return f"{manifest}_shiny"
    return None


def prepare_shiny_pool_context(pool_name: str, pc: Any | None = None) -> None:
    """Unlock shiny cosmetic profile entry — required for most pearl *_shiny pools."""
    pool = str(pool_name or "").strip()
    if not pc:
        pc = resolve_spawn_pc()
    if not pool or pc is None:
        return
    try:
        from bl4_item_spawner.shiny_pool_spawn import prepare_shiny_spawn_context

        prepare_shiny_spawn_context(pc, pool)
        return
    except Exception:
        pass
    try:
        from bl4_item_spawner.shiny_pool_spawn import unlock_shiny_for_pool

        unlock_shiny_for_pool(pc, pool)
        return
    except Exception:
        pass
    _bundled_unlock_shiny_for_pool(pc, pool)


def unlock_all_pearl_shinies(*, limit: int = 0) -> tuple[int, int]:
    """Unlock every pearl shiny cosmetic once (idempotent). Returns (attempted, ok)."""
    pc = resolve_spawn_pc()
    if pc is None:
        return 0, 0
    try:
        from bl4_item_spawner.shiny_pool_spawn import unlock_all_shiny_weapons

        return unlock_all_shiny_weapons(pc, limit=limit)
    except Exception:
        pass
    pools = list(dict.fromkeys(PEARL_SHINY_POOLS.values()))
    if limit > 0:
        pools = pools[: int(limit)]
    ok = 0
    for pool in pools:
        if _bundled_unlock_shiny_for_pool(pc, pool):
            ok += 1
    return len(pools), ok


def prepare_pearl_spawn_batch(catalog_keys: list[str] | None = None) -> None:
    """Pre-unlock shinies for a batch of named pearls (Spawn All / generic pools)."""
    pc = resolve_spawn_pc()
    if pc is None:
        return
    if catalog_keys:
        seen: set[str] = set()
        for catalog in catalog_keys:
            shiny = primary_shiny_pool_for_catalog(str(catalog or "").strip().lower(), "")
            if not shiny:
                continue
            low = shiny.lower()
            if low in seen:
                continue
            seen.add(low)
            prepare_shiny_pool_context(shiny, pc)
        return
    unlock_all_pearl_shinies()


def _bundled_unlock_shiny_for_pool(pc: Any, pool_name: str) -> bool:
    row = lookup_shiny_pool(pool_name)
    customization = str((row or {}).get("customization", "")).strip()
    if not customization:
        return False
    ps = getattr(pc, "PlayerState", None) or getattr(pc, "OakPlayerState", None)
    if ps is None:
        return False
    tokens = _unlock_tokens_for_customization(customization, pool_name=pool_name)
    for token in tokens:
        if _client_unlock(ps, token):
            return True
    return False


def _unlock_tokens_for_customization(customization: str, *, pool_name: str = "") -> list[str]:
    import re

    raw = str(customization or "").strip()
    if raw.lower().startswith("inv_custom'") and raw.endswith("'"):
        cosmetic = raw[len("inv_custom'") : -1]
    elif raw.lower().startswith("inv_custom'"):
        cosmetic = raw.replace("inv_custom'", "").rstrip("'")
    else:
        cosmetic = raw
    token = ""
    if "_Shiny_" in cosmetic:
        token = cosmetic.rsplit("_Shiny_", 1)[-1]
    elif cosmetic.lower().startswith("cosmetics_weapon_shiny_"):
        token = cosmetic[len("Cosmetics_Weapon_Shiny_") :]
    if not token and pool_name:
        low = str(pool_name).strip().lower()
        if low.endswith("_shiny"):
            low = low[: -len("_shiny")]
        match = re.search(r"_legendary_([^_]+)$", low) or re.search(r"_06_pearl_([^_]+)$", low)
        if match:
            token = match.group(1)
    if not token:
        return []
    out = [
        f"Unlockable_Weapons.Shiny_{token}",
        f"Unlockable_Weapons.shiny_{token.lower()}",
        f"Unlockable_Weapons.Shiny_{token.lower()}",
    ]
    if token[:1].isupper():
        out.append(f"Unlockable_Weapons.Shiny_{token[0].upper()}{token[1:]}")
    seen: set[str] = set()
    deduped: list[str] = []
    for item in out:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _client_unlock(ps: Any, unlock_token: str) -> bool:
    fn = getattr(ps, "ClientUnlockUnlockable", None)
    if not callable(fn):
        return False
    token = str(unlock_token or "").strip()
    if not token or "." not in token:
        return False
    ledger, entry = token.split(".", 1)
    attempts: list[tuple[tuple[Any, ...], dict[str, Any]]] = [
        ((ledger, entry), {}),
        ((entry, ledger), {}),
        ((), {"LedgerIdent": ledger, "EntryIdent": entry}),
    ]
    for args, kwargs in attempts:
        try:
            fn(*args, **kwargs)
            return True
        except Exception:
            continue
    return False


def catalog_key_from_shiny_pool(pool_name: str) -> str:
    """itempool_jak_ar_05_legendary_rowan_shiny → jak_ar_comp_05_legendary_rowan."""
    low = str(pool_name or "").strip().lower()
    if low.startswith("itempool'") and low.endswith("'"):
        low = low[len("itempool'") : -1]
    if low.endswith("_shiny"):
        low = low[: -len("_shiny")]
    match = re.match(r"^itempool_(.+)_05_legendary_(.+)$", low)
    if match:
        return f"{match.group(1)}_comp_05_legendary_{match.group(2)}"
    # Some rows omit _05_: itempool_jak_sr_legendary_Burrow_shiny
    match = re.match(r"^itempool_(.+)_legendary_(.+)$", low)
    if match:
        return f"{match.group(1)}_comp_05_legendary_{match.group(2)}"
    match = re.match(r"^itempool_(.+)_06_pearl_(.+)$", low)
    if match:
        return f"{match.group(1)}_comp_06_pearl_{match.group(2)}"
    return ""


def _apply_shiny_customization_for_pool(pool_name: str) -> None:
    """Apply phosphene / shiny skin to a nearby drop after merge or @U spawn."""
    row = lookup_shiny_pool(pool_name)
    if not row:
        return
    customization = str(row.get("customization") or "").strip()
    inv_handle = str(row.get("inv_handle") or "").strip()
    if not customization:
        return
    try:
        from bl4_item_spawner.shiny_pool_spawn import apply_phosphene_nearby

        pc = resolve_spawn_pc()
        if pc is not None:
            apply_phosphene_nearby(pc, customization, inv_handle)
            return
    except Exception:
        pass


def _dump_first_shiny_pool(pool_name: str) -> bool:
    """Bundled ncs_shiny_pools row — @U/merge only, never base inv or silent NCS pool."""
    return lookup_shiny_pool(pool_name) is not None


def spawn_shiny_from_dump(
    pool_name: str,
    *,
    count: int = 1,
    level: int = 60,
    location: Any = None,
    rotation: Any = None,
    catalog: str = "",
) -> tuple[int, str | None, str]:
    """World-drop a *_shiny pool: native *_shiny pool, inline dump + phosphene, @U last.

    Never falls back to base catalog inv — that drops non-shiny legendaries.
    Returns (spawned_count, error, method_tag).
    """
    pool = str(pool_name or "").strip()
    want = max(1, int(count))
    lvl = max(1, int(level))
    prepare_shiny_pool_context(pool)
    err: str | None = None
    catalog_l = str(catalog or "").strip().lower() or catalog_key_from_shiny_pool(pool)
    dump_first = _dump_first_shiny_pool(pool)

    def _accept(spawned: int) -> bool:
        if spawned <= 0:
            return False
        if before_loc is None:
            return True
        return _feet_gained(before_loc, before_keys)

    before_loc, before_keys = _feet_snapshot()
    pool_l = pool.lower()
    wrong_family = pool_l in {
        "itempool_jak_sr_legendary_burrow_shiny",
    }
    shaped = location is not None
    payload = inline_payload_for_shiny(pool)

    def _catalog_handles() -> list[str]:
        handles: list[str] = []
        if not (catalog_l or wrong_family):
            return handles
        try:
            from .legendary_dump_manifest import dump_inv_handles_for_catalog

            handles.extend(dump_inv_handles_for_catalog(catalog_l) or [])
        except Exception:  # noqa: BLE001
            pass
        if not handles:
            try:
                from ..item_pool_spawning import (
                    _PATCH_INLINE_INVENTORY_DEFS,
                    _inv_handle_casing_variants,
                )

                patch = str(_PATCH_INLINE_INVENTORY_DEFS.get(catalog_l) or "").strip()
                if patch:
                    handles = _inv_handle_casing_variants(patch)
            except Exception:  # noqa: BLE001
                pass
        return handles

    def _try_inline_at_slot() -> tuple[int, str]:
        nonlocal err
        if payload is None:
            return 0, ""
        from .comp_loot_drop import spawn_from_merge_payload

        row = dict(payload)
        handles = list(row.get("handle_variants") or [])
        if handles and "handle_variants" not in row:
            row["handle_variants"] = handles
        spawned, merge_err = spawn_from_merge_payload(
            row,
            count=want,
            level=lvl,
            drop_only=True,
            pool_name=pool,
            skip_verify=True,
            at_location=location,
            at_rotation=rotation,
        )
        if spawned > 0:
            _apply_shiny_customization_for_pool(pool)
            return int(spawned), "shiny_merge_inline"
        err = merge_err or err
        return 0, ""

    def _try_catalog_at_slot() -> tuple[int, str]:
        nonlocal err
        handles = _catalog_handles()
        if not handles:
            return 0, ""
        from .comp_loot_drop import spawn_inv_handles_at_feet

        spawned, dump_err = spawn_inv_handles_at_feet(
            handles[:6],
            count=want,
            level=lvl,
            skip_verify=True,
            at_location=location,
            at_rotation=rotation,
        )
        if spawned > 0:
            _apply_shiny_customization_for_pool(pool)
            return int(spawned), "shiny_catalog_dump"
        err = dump_err or err
        return 0, ""

    def _try_ncs_at_slot() -> tuple[int, str]:
        nonlocal err
        if wrong_family or not dump_first or not pool:
            return 0, ""
        try:
            from .ncs_pool_spawn import spawn_legacy_itempool, spawn_itempool_names

            spawned, pool_err = spawn_itempool_names(
                [pool],
                count=want,
                level=lvl,
                require_loot_verify=False,
                at_location=location,
                at_rotation=rotation,
            )
            if spawned <= 0:
                spawned, pool_err = spawn_legacy_itempool(
                    [pool],
                    count=want,
                    level=lvl,
                    at_location=location,
                    at_rotation=rotation,
                )
            if spawned > 0:
                _apply_shiny_customization_for_pool(pool)
                return int(spawned), "ncs_shiny_pool"
            err = pool_err or err
        except Exception as pool_exc:
            err = str(pool_exc) or err
        return 0, ""

    if shaped:
        for try_fn in (_try_inline_at_slot, _try_catalog_at_slot, _try_ncs_at_slot):
            spawned, method = try_fn()
            if spawned > 0:
                return spawned, None, method

    # Feet-first paths (pile / no silhouette slot).
    if catalog_l or wrong_family:
        from .comp_loot_drop import spawn_inv_handles_at_feet

        handles = _catalog_handles()
        if handles:
            spawned, dump_err = spawn_inv_handles_at_feet(
                handles[:6],
                count=want,
                level=lvl,
                skip_verify=False,
            )
            if spawned > 0:
                _apply_shiny_customization_for_pool(pool)
                return int(spawned), None, "shiny_catalog_dump"
            err = dump_err or err

    if wrong_family:
        return 0, err or "wrong-family shiny pool blocked (would spawn Fearstalker)", ""

    if dump_first and pool:
        try:
            from .ncs_pool_spawn import spawn_legacy_itempool, spawn_itempool_names

            spawned, pool_err = spawn_itempool_names(
                [pool], count=want, level=lvl, require_loot_verify=False
            )
            if spawned <= 0:
                spawned, pool_err = spawn_legacy_itempool([pool], count=want, level=lvl)
            if spawned > 0:
                _apply_shiny_customization_for_pool(pool)
                return int(spawned), None, "ncs_shiny_pool"
            err = pool_err or err
        except Exception as pool_exc:
            err = str(pool_exc) or err

    if payload is not None:
        from .comp_loot_drop import spawn_from_merge_payload

        handles = list(payload.get("handle_variants") or [])
        if handles and "handle_variants" not in payload:
            payload = dict(payload)
            payload["handle_variants"] = handles
        spawned, merge_err = spawn_from_merge_payload(
            payload,
            count=want,
            level=lvl,
            drop_only=True,
            pool_name=pool,
            skip_verify=bool(dump_first),
            at_location=location,
            at_rotation=rotation,
        )
        if spawned > 0:
            _apply_shiny_customization_for_pool(pool)
            if _accept(spawned) or dump_first:
                return spawned, None, "shiny_merge_inline"
        err = merge_err or err or "shiny inline merge missed ground loot"
        before_loc, before_keys = _feet_snapshot()

    serial = serial_for_shiny_pool(pool)
    if not serial:
        try:
            from ..shinies import serial_for_shiny_pool as _alias_serial

            serial = _alias_serial(pool)
        except Exception:
            serial = None
    if serial:
        from .pearl_serial_spawn import try_deliver_serial_comprehensive

        ok, via = try_deliver_serial_comprehensive(
            serial, want, prefer_ground=True, ground_only=True
        )
        if ok:
            if _accept(want) or dump_first:
                _apply_shiny_customization_for_pool(pool)
                return want, None, "dump_serial_ground"
            err = f"shiny @U via {via} but no ground loot"
            before_loc, before_keys = _feet_snapshot()
        else:
            err = via or err

    if not dump_first and pool and not catalog_l:
        try:
            from .ncs_pool_spawn import spawn_legacy_itempool, spawn_itempool_names

            spawned, pool_err = spawn_itempool_names(
                [pool], count=want, level=lvl, require_loot_verify=False
            )
            if spawned <= 0:
                spawned, pool_err = spawn_legacy_itempool([pool], count=want, level=lvl)
            if spawned > 0:
                _apply_shiny_customization_for_pool(pool)
                if _accept(int(spawned)):
                    return int(spawned), None, "ncs_shiny_pool"
            err = pool_err or err
        except Exception as pool_exc:
            err = str(pool_exc) or err

    if payload is None and not catalog_l and not serial:
        return 0, "not in ncs_shiny_pools dump", ""
    return 0, err or "shiny dump missed", ""


def spawn_pearl_shiny_at_feet(
    shiny_pool: str,
    *,
    count: int = 1,
    level: int = 60,
) -> tuple[bool, bool, str, str]:
    """
    Spawn via dump *_shiny pool.

    Returns (attempted, loot_verified, method, pool).
    Legacy NCS / BL4 shiny APIs never count as verified without feet loot.
    """
    pool = str(shiny_pool or "").strip()
    if not pool:
        return False, False, "", ""
    want = max(1, min(int(count), 32))
    lvl = max(1, int(level))

    prepare_shiny_pool_context(pool)

    dumped, _dump_err, dump_method = spawn_shiny_from_dump(pool, count=want, level=lvl)
    if dumped > 0:
        return True, True, dump_method or "pearl_shiny_inline", pool

    before_loc, before_keys = _feet_snapshot()

    try:
        import bl4_item_spawner as bis

        bis.CONTROLLER._spawn_shiny_pool_world(pool, want, lvl)
        method = str(getattr(bis.CONTROLLER, "_last_shiny_spawn_method", "bl4_shiny_world"))
        if _feet_gained(before_loc, before_keys):
            return True, True, method, pool
    except ImportError:
        pass
    except Exception:
        pass

    from .ncs_pool_spawn import spawn_legacy_itempool

    before_loc, before_keys = _feet_snapshot()
    spawned, _err = spawn_legacy_itempool([pool], count=want, level=lvl)
    if spawned > 0 and _feet_gained(before_loc, before_keys):
        return True, True, "pearl_shiny_legacy", pool

    from .ncs_pool_spawn import spawn_itempool_names

    before_loc, before_keys = _feet_snapshot()
    spawned, _err = spawn_itempool_names([pool], count=want, level=lvl, require_loot_verify=True)
    if spawned > 0 and _feet_gained(before_loc, before_keys):
        return True, True, "ncs_verified_pool", pool

    if spawned > 0 or (payload is not None):
        return True, False, "pearl_shiny_attempt", pool
    return False, False, "", pool


def spawn_named_pearl_shiny(
    catalog_key: str,
    manifest_pool: str = "",
    *,
    count: int = 1,
    level: int = 60,
) -> tuple[bool, bool, str, str]:
    """Spawn named pearl using dump-canonical shiny pool."""
    shiny = primary_shiny_pool_for_catalog(catalog_key, manifest_pool)
    if not shiny:
        return False, False, "", ""
    return spawn_pearl_shiny_at_feet(shiny, count=count, level=level)
