"""
NCS itempool world spawn — bundled for Squ1ggsBoostingTools.

Uses NexusConfigStoreItemPool.SpawnInventoryFromItemPool with forward/up offsets
so loot appears in front of the player (not inside the pawn).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import unrealsdk
from unrealsdk.unreal import UObject

from .loot_verify import feet_weapon_loot_keys, player_location_from_pc, verify_available
from .runtime_cache import get_nexus_config_store_item_pool, get_world, iter_nexus_config_stores
from .spawn_pc import resolve_spawn_pc

SPAWN_FORWARD_OFFSET = 50.0
SPAWN_HEIGHT_OFFSET = 50.0
SPAWN_SIDE_SPACING = 55.0
DEFAULT_ITEM_LEVEL = 70
MAX_ITEM_LEVEL = 999999


def _make_vector(x: float, y: float, z: float) -> Any:
    return unrealsdk.make_struct("Vector", X=x, Y=y, Z=z)


def _make_rotator(pitch: float, yaw: float, roll: float = 0.0) -> Any:
    return unrealsdk.make_struct("Rotator", Pitch=pitch, Yaw=yaw, Roll=roll)


def _quat_from_rotation(rotation: Any) -> Any:
    """Build the FQuat required by FTransform.Rotation.

    The original GitHub path used a Quat. Passing a Rotator can return from
    SpawnInventoryFromItemPool without an exception while producing no loot.
    """
    pitch = yaw = roll = 0.0
    try:
        pitch = math.radians(float(getattr(rotation, "Pitch", 0.0) or 0.0))
        yaw = math.radians(float(getattr(rotation, "Yaw", 0.0) or 0.0))
        roll = math.radians(float(getattr(rotation, "Roll", 0.0) or 0.0))
    except Exception:
        yaw = 0.0
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    return unrealsdk.make_struct(
        "Quat",
        X=sr * cp * cy - cr * sp * sy,
        Y=cr * sp * cy + sr * cp * sy,
        Z=cr * cp * sy - sr * sp * cy,
        W=cr * cp * cy + sr * sp * sy,
    )


def apply_world_spawn_transform(transform: Any, location: Any, rotation: Any) -> None:
    """Dump/inline FTransform: Translation + Rotator (original Item Spawner ABI).

    Named uniques spawn via SpawnLootFromData / ItemPoolFunctionLibrary, not NCS.
    Those APIs accept the pawn Rotator the hooked widget wrote. A constructed
    Quat here was rejecting dump drops while mixed NCS pools still worked.
    """
    if transform is None:
        return
    try:
        setattr(transform, "Translation", location)
    except Exception:
        pass
    try:
        setattr(transform, "Rotation", rotation)
    except Exception:
        try:
            setattr(transform, "Rotation", _quat_from_rotation(rotation))
        except Exception:
            pass


def _resolve_drop_pose(pc: UObject) -> tuple[Any, Any] | None:
    """Prefer EXE/bridge Drop-near target (party / NPC), else local pawn pose."""
    try:
        from ..spawn_targets import mode as spawn_mode  # noqa: PLC0415
        from ..spawn_targets import resolve_pose  # noqa: PLC0415

        pose = resolve_pose(pc)
        if pose is not None and str(spawn_mode() or "local").strip().lower() == "local":
            # Squ1ggs pool spawn: pawn body rotation drives natural forward spit.
            return _local_pawn_pose(pc) or pose
        if pose is not None:
            return pose
    except Exception:
        pass
    return _local_pawn_pose(pc)


def _yaw_degrees(raw: float) -> float:
    """Normalize Unreal yaw to degrees (handles rotator units where 65536=360°)."""
    y = float(raw or 0.0)
    if abs(y) > 720.0:
        y = y * (360.0 / 65536.0)
    return y


def _control_rotation(pc: UObject) -> Any | None:
    """Unused for pool spit — kept for dump exact-location callers."""
    rot = getattr(pc, "ControlRotation", None)
    if rot is None:
        fn = getattr(pc, "GetControlRotation", None)
        if callable(fn):
            try:
                rot = fn()
            except Exception:
                rot = None
    if rot is None:
        return None
    try:
        return _make_rotator(0.0, _yaw_degrees(float(getattr(rot, "Yaw", 0.0) or 0.0)), 0.0)
    except Exception:
        return rot


def _local_pawn_pose(pc: UObject) -> tuple[Any, Any] | None:
    pawn = getattr(pc, "Pawn", None)
    if pawn is None:
        return None
    loc = pawn.K2_GetActorLocation()
    try:
        body = pawn.K2_GetActorRotation()
        return loc, _make_rotator(0.0, _yaw_degrees(float(getattr(body, "Yaw", 0.0) or 0.0)), 0.0)
    except Exception:
        try:
            return loc, pawn.K2_GetActorRotation()
        except Exception:
            return None


def _facing_xy(pc: UObject | None, player_rotation: Any, pawn: Any = None) -> tuple[float, float]:
    """Unit XY facing — pawn forward vector first (matches engine loot spit)."""
    if pawn is not None:
        getter = getattr(pawn, "GetActorForwardVector", None)
        if callable(getter):
            try:
                vec = getter()
                fx = float(getattr(vec, "X", 0.0) or 0.0)
                fy = float(getattr(vec, "Y", 0.0) or 0.0)
                norm = math.hypot(fx, fy)
                if norm > 1e-3:
                    return fx / norm, fy / norm
            except Exception:
                pass
    yaw = math.radians(_yaw_degrees(float(getattr(player_rotation, "Yaw", 0.0) or 0.0)))
    return math.cos(yaw), math.sin(yaw)


def _get_spawn_transform(pc: UObject) -> Any | None:
    """Squ1ggs pool spawn: start from the pawn transform (keeps engine Rotation type)."""
    pawn = getattr(pc, "Pawn", None)
    if pawn is None:
        return None
    player_location = pawn.K2_GetActorLocation()
    for getter_name in ("K2_GetActorTransform", "GetActorTransform", "GetTransform"):
        getter = getattr(pawn, getter_name, None)
        if not callable(getter):
            continue
        try:
            transform = getter()
            setattr(
                transform,
                "Translation",
                _make_vector(player_location.X, player_location.Y, player_location.Z),
            )
            return transform
        except Exception:
            continue
    try:
        return unrealsdk.make_struct(
            "Transform",
            Translation=_make_vector(player_location.X, player_location.Y, player_location.Z),
        )
    except Exception:
        return None


def _get_player_pose(pc: UObject) -> tuple[Any, Any] | None:
    return _resolve_drop_pose(pc)


def _spawn_pose(player_location: Any, player_rotation: Any, index: int) -> tuple[Any, Any]:
    """Natural front drop — front offsets (50 forward / 50 up). No post-spawn yank."""
    try:
        from ..loot_shapes import next_spawn_land_world

        posed = next_spawn_land_world(player_location, player_rotation)
        if posed is not None:
            return posed
    except Exception:
        pass
    pc = resolve_spawn_pc()
    pawn = getattr(pc, "Pawn", None) if pc is not None else None
    forward_x, forward_y = _facing_xy(pc, player_rotation, pawn)
    right_x = -forward_y
    right_y = forward_x
    # Singular / pile: dead ahead. Multi without pile: mild left/right only.
    side = 0.0
    try:
        from .pearl_spawn_ring import bulk_pile_mode

        if not bulk_pile_mode():
            side = ((int(index) + 1) // 2) * SPAWN_SIDE_SPACING
            if int(index) % 2 == 1:
                side = -side
    except Exception:
        side = 0.0
    new_x = player_location.X + forward_x * SPAWN_FORWARD_OFFSET + right_x * side
    new_y = player_location.Y + forward_y * SPAWN_FORWARD_OFFSET + right_y * side
    new_z = player_location.Z + SPAWN_HEIGHT_OFFSET + (int(index) * 8.0)
    location = _make_vector(new_x, new_y, new_z)
    yaw = _yaw_degrees(float(getattr(player_rotation, "Yaw", 0.0) or 0.0))
    return location, _make_rotator(0.0, yaw, 0.0)


def _pool_name_variants(pool_name: str) -> list[str]:
    variants = [pool_name.strip()]
    low = pool_name.strip()
    if low.startswith("itempool'") and low.endswith("'"):
        variants.append(low.replace("itempool'", "").rstrip("'"))
    out: list[str] = []
    seen: set[str] = set()
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _spawn_pool_call(
    config: UObject,
    world: UObject,
    transform: Any,
    level: int,
    pool_name: str,
    location: Any,
    rotation: Any,
) -> None:
    """Issue the Nexus spawn with a valid FTransform (Rotation is FQuat)."""
    try:
        setattr(transform, "Translation", location)
    except Exception:
        pass
    try:
        setattr(transform, "Rotation", _quat_from_rotation(rotation))
    except Exception:
        pass
    config.SpawnInventoryFromItemPool(world, transform, level, pool_name)


def nexus_store_count() -> int:
    return len(iter_nexus_config_stores())


def default_nexus_store_index() -> int:
    """Return the index of the legacy/default store in the de-duplicated list."""
    target = get_nexus_config_store_item_pool()
    stores = iter_nexus_config_stores()
    for index, store in enumerate(stores):
        if store is target:
            return index
        try:
            target_address = int(getattr(target, "_get_address", lambda: 0)() or 0)
            store_address = int(getattr(store, "_get_address", lambda: 0)() or 0)
            if target_address and target_address == store_address:
                return index
        except Exception:
            continue
    # The runtime cache normally selects the newest live store, which is the
    # first live entry after the CDO in iter_nexus_config_stores().
    return 1 if len(stores) > 1 else 0


def spawn_itempool_on_store(
    pool_name: str,
    *,
    store_index: int,
    count: int = 1,
    level: int = DEFAULT_ITEM_LEVEL,
) -> tuple[int, str | None]:
    """Issue one pool request against one specific NCS config layer."""
    pool = str(pool_name or "").strip()
    stores = iter_nexus_config_stores()
    index = int(store_index)
    if not pool:
        return 0, "no pool name"
    if index < 0 or index >= len(stores):
        return 0, f"NCS store index {index} unavailable ({len(stores)} stores)"

    world = get_world()
    pc = resolve_spawn_pc()
    if world is None or pc is None:
        return 0, "Player or world is not available."
    transform = _get_spawn_transform(pc)
    player_pose = _get_player_pose(pc)
    if transform is None or player_pose is None:
        return 0, "Could not derive a spawn transform."

    want = max(1, min(int(count), 100))
    lvl = max(1, min(MAX_ITEM_LEVEL, int(level)))
    player_location, player_rotation = player_pose
    try:
        for item_index in range(want):
            location, rotation = _spawn_pose(player_location, player_rotation, item_index)
            _spawn_pool_call(stores[index], world, transform, lvl, pool, location, rotation)
    except Exception as exc:  # noqa: BLE001
        return 0, f"{pool} store {index}: {exc}"
    return want, None


def spawn_itempool_names(
    pool_names: Sequence[str],
    *,
    count: int = 1,
    level: int = DEFAULT_ITEM_LEVEL,
    require_loot_verify: bool = False,
    at_location: Any = None,
    at_rotation: Any = None,
) -> tuple[int, str | None]:
    """Try each pool name until one spawns successfully."""
    names = [
        str(n).strip()
        for n in pool_names
        if str(n).strip()
        and "_comp_05_" not in str(n).lower()
        and "_comp_06_" not in str(n).lower()
    ]
    if not names:
        return 0, "no live pool names (synthetic *_comp_* blocked)"

    count = max(1, min(int(count), 100))
    level = max(1, min(MAX_ITEM_LEVEL, int(level)))

    world = get_world()
    pc = resolve_spawn_pc()
    if world is None or pc is None:
        return 0, "Player or world is not available."

    transform = _get_spawn_transform(pc)
    player_pose = _get_player_pose(pc)
    if transform is None or player_pose is None:
        return 0, "Could not derive a spawn transform."

    config = get_nexus_config_store_item_pool()
    player_location, player_rotation = player_pose
    player_loc = player_location_from_pc(pc) or player_location
    last_err: str | None = None
    can_verify = verify_available() and player_loc is not None and at_location is None
    if require_loot_verify and not can_verify:
        require_loot_verify = False

    for pool_name in names:
        for variant in _pool_name_variants(pool_name):
            before = feet_weapon_loot_keys(player_loc) if can_verify else set()
            try:
                for index in range(count):
                    if at_location is not None:
                        location = at_location
                        rotation = (
                            at_rotation if at_rotation is not None else player_rotation
                        )
                    else:
                        location, rotation = _spawn_pose(
                            player_location, player_rotation, index
                        )
                    _spawn_pool_call(
                        config, world, transform, level, variant, location, rotation
                    )
            except Exception as exc:  # noqa: BLE001
                last_err = f"{variant}: {exc}"
                continue
            if require_loot_verify:
                after = feet_weapon_loot_keys(player_loc)
                if len(after - before) < 1:
                    last_err = f"FAILED — {variant}: OK but no weapon loot at feet (silent empty)"
                    continue
            return count, None

    return 0, last_err or "FAILED — SpawnInventoryFromItemPool failed for all candidates"


def spawn_legacy_itempool(
    pool_names: Sequence[str],
    *,
    count: int = 1,
    level: int = DEFAULT_ITEM_LEVEL,
    at_location: Any = None,
    at_rotation: Any = None,
) -> tuple[int, str | None]:
    """Squ1ggs pool spawn — direct SpawnInventoryFromItemPool, no loot verify."""
    names = [
        str(n).strip()
        for n in pool_names
        if str(n).strip()
        and "_comp_05_" not in str(n).lower()
        and "_comp_06_" not in str(n).lower()
    ]
    if not names:
        return 0, "no live pool names (synthetic *_comp_* blocked)"

    count = max(1, min(int(count), 100))
    level = max(1, min(MAX_ITEM_LEVEL, int(level)))

    world = get_world()
    pc = resolve_spawn_pc()
    if world is None or pc is None:
        return 0, "Player or world is not available."

    transform = _get_spawn_transform(pc)
    player_pose = _get_player_pose(pc)
    if transform is None or player_pose is None:
        return 0, "Could not derive a spawn transform."

    stores = iter_nexus_config_stores() or [get_nexus_config_store_item_pool()]
    player_location, player_rotation = player_pose
    last_err: str | None = None

    for pool_name in names:
        for variant in _pool_name_variants(pool_name):
            spawned_ok = False
            for store in stores:
                if store is None:
                    continue
                try:
                    for index in range(count):
                        if at_location is not None:
                            location = at_location
                            rotation = (
                                at_rotation if at_rotation is not None else player_rotation
                            )
                        else:
                            location, rotation = _spawn_pose(
                                player_location, player_rotation, index
                            )
                        _spawn_pool_call(
                            store, world, transform, level, variant, location, rotation
                        )
                    spawned_ok = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = f"{variant}: {exc}"
                    continue
            if spawned_ok:
                return count, None

    return 0, last_err or "SpawnInventoryFromItemPool failed for all candidates"
