"""F.A.A.F.O. — party-aware chaos / grief tools (StreamerChaos-style effects).

Effects target the boost-selected party index (host listen-server), not only the
local player. Do not install the standalone StreamerChaos NumPad mod beside SQBT.
"""

from __future__ import annotations

import threading
from typing import Any

import unrealsdk
from mods_base import get_pc
from unrealsdk import logging

from .dev_tools import _pc_for_party_index, _pawn_for_pc

_PREFIX = "[SQBT FAAFO]"
_DEFAULT_LAUNCH_Z = 5000.0
_DEFAULT_LOCK_SECS = 5.0
_DEFAULT_INVERT_SECS = 8.0
_SPAWN_PATTERN_TYPE = 49152
_SPAWN_PATTERN_NAMES: tuple[str, ...] = (
    "spawnpattern_lootable_upandforward",
    "spawnpattern_loot_at_location",
    "spawnpattern_default_loot",
)

_lock = threading.Lock()
_unlock_timers: dict[str, threading.Timer] = {}
_invert_timers: dict[str, threading.Timer] = {}
_invert_backups: dict[str, dict[str, tuple[Any, str, Any]]] = {}
_pending_launch: dict[str, float] = {}


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
    except Exception:
        print(f"{_PREFIX} {msg}")


def _pc_key(pc: Any, player_index: int | None = None) -> str:
    if player_index is not None:
        return f"idx:{int(player_index)}"
    try:
        name = getattr(pc, "Name", None)
        if name:
            return f"pc:{name}"
    except Exception:
        pass
    return f"pc:{id(pc)}"


def _try_call(obj: Any, name: str, *args: Any) -> bool:
    fn = getattr(obj, name, None) if obj is not None else None
    if not callable(fn):
        return False
    try:
        fn(*args)
        return True
    except TypeError:
        if args:
            try:
                fn()
                return True
            except Exception:
                return False
        return False
    except Exception:
        return False


def _movement(character: Any) -> Any:
    if character is None:
        return None
    for attr in ("OakCharacterMovement", "CharacterMovement", "MovementComponent"):
        try:
            move = getattr(character, attr, None)
        except Exception:
            move = None
        if move is not None:
            return move
    return None


def _inventory_statics() -> Any:
    for cls_name, path in (
        ("OakInventoryStatics", "Default__OakInventoryStatics"),
        ("GbxInventoryStatics", "Default__GbxInventoryStatics"),
        ("InventoryStatics", "Default__InventoryStatics"),
    ):
        try:
            obj = unrealsdk.find_object(cls_name, path)
        except Exception:
            obj = None
        if obj is not None:
            return obj
    return None


def resolve_pc(player_index: int | None = None) -> tuple[Any | None, str]:
    return _pc_for_party_index(player_index)


def do_unlock(pc: Any = None, player_index: int | None = None) -> str:
    if pc is None:
        pc, err = resolve_pc(player_index)
        if pc is None:
            return err or "no PC"
    ok = False
    for name in ("ResetIgnoreLookInput", "ResetIgnoreMoveInput", "ResetIgnoreInputFlags"):
        if _try_call(pc, name):
            ok = True
    return "unlock OK" if ok else "unlock failed"


def _schedule_unlock(seconds: float, pc: Any, player_index: int | None = None) -> None:
    key = _pc_key(pc, player_index)

    def _fire() -> None:
        try:
            msg = do_unlock(pc, player_index)
            _log(f"auto-unlock {key}: {msg}")
        except Exception as exc:
            _log(f"auto-unlock ERR {exc!r}")
        with _lock:
            _unlock_timers.pop(key, None)

    with _lock:
        old = _unlock_timers.pop(key, None)
        if old is not None:
            try:
                old.cancel()
            except Exception:
                pass
        timer = threading.Timer(max(0.5, float(seconds)), _fire)
        timer.daemon = True
        _unlock_timers[key] = timer
        timer.start()


def do_lock_look(pc: Any = None, player_index: int | None = None, seconds: float = _DEFAULT_LOCK_SECS) -> str:
    if pc is None:
        pc, err = resolve_pc(player_index)
        if pc is None:
            return err or "no PC"
    ok = _try_call(pc, "SetIgnoreLookInput", True) or _try_call(pc, "SetIgnoreLookInput")
    if ok:
        _schedule_unlock(float(seconds), pc, player_index)
    return f"lock look {'OK' if ok else 'FAILED'} ({seconds}s)"


def do_lock_move(pc: Any = None, player_index: int | None = None, seconds: float = _DEFAULT_LOCK_SECS) -> str:
    if pc is None:
        pc, err = resolve_pc(player_index)
        if pc is None:
            return err or "no PC"
    ok = _try_call(pc, "SetIgnoreMoveInput", True) or _try_call(pc, "SetIgnoreMoveInput")
    if ok:
        _schedule_unlock(float(seconds), pc, player_index)
    return f"lock move {'OK' if ok else 'FAILED'} ({seconds}s)"


def do_lock_both(pc: Any = None, player_index: int | None = None, seconds: float = _DEFAULT_LOCK_SECS) -> str:
    if pc is None:
        pc, err = resolve_pc(player_index)
        if pc is None:
            return err or "no PC"
    ok_l = _try_call(pc, "SetIgnoreLookInput", True) or _try_call(pc, "SetIgnoreLookInput")
    ok_m = _try_call(pc, "SetIgnoreMoveInput", True) or _try_call(pc, "SetIgnoreMoveInput")
    if ok_l or ok_m:
        _schedule_unlock(float(seconds), pc, player_index)
    return f"lock look={'OK' if ok_l else 'FAIL'} move={'OK' if ok_m else 'FAIL'} ({seconds}s)"


def do_invert_look(pc: Any = None, player_index: int | None = None, seconds: float = _DEFAULT_INVERT_SECS) -> str:
    if pc is None:
        pc, err = resolve_pc(player_index)
        if pc is None:
            return err or "no PC"

    key = _pc_key(pc, player_index)
    targets: list[tuple[str, Any]] = [("pc", pc)]
    for attr in ("PlayerInput", "GbxPlayerInput", "EnhancedPlayerInput"):
        try:
            obj = getattr(pc, attr, None)
        except Exception:
            obj = None
        if obj is not None:
            targets.append((attr, obj))

    flipped: list[str] = []
    backup: dict[str, tuple[Any, str, Any]] = {}
    scale_names = ("InputYawScale", "InputPitchScale", "LookRightScale", "LookUpScale")

    for label, obj in targets:
        for name in scale_names:
            if not hasattr(obj, name):
                continue
            try:
                cur = getattr(obj, name)
                if callable(cur):
                    continue
                field_key = f"{label}.{name}"
                backup[field_key] = (obj, name, cur)
                if isinstance(cur, (int, float)):
                    setattr(obj, name, float(cur) * -1.0)
                    flipped.append(field_key)
            except Exception:
                continue

    def _restore() -> None:
        stored = _invert_backups.pop(key, {})
        for _fk, triple in list(stored.items()):
            obj, name, cur = triple
            try:
                setattr(obj, name, cur)
            except Exception:
                pass
        with _lock:
            _invert_timers.pop(key, None)
        _log(f"invert restored {key}")

    with _lock:
        old = _invert_timers.pop(key, None)
        if old is not None:
            try:
                old.cancel()
            except Exception:
                pass
        prev = _invert_backups.get(key) or {}
        for fk, triple in prev.items():
            obj, name, cur = triple
            try:
                setattr(obj, name, cur)
            except Exception:
                pass
        _invert_backups[key] = backup
        timer = threading.Timer(max(0.5, float(seconds)), _restore)
        timer.daemon = True
        _invert_timers[key] = timer
        timer.start()

    if not flipped:
        return "invert: nothing flipped"
    return f"invert OK {flipped} ({seconds}s)"


def do_kill(pc: Any = None, player_index: int | None = None) -> str:
    if pc is None:
        pc, err = resolve_pc(player_index)
        if pc is None:
            return err or "no PC"
    pawn = _pawn_for_pc(pc)
    if pawn is None:
        return "kill: no pawn"
    _try_call(pawn, "SetCanBeDowned", True)
    start = getattr(pawn, "StartDownState", None)
    if not callable(start):
        return "kill: StartDownState missing"
    try:
        start(True)
        return "kill OK StartDownState(True)"
    except Exception as exc:
        return f"kill ERR {exc!r}"


def do_ffyl(pc: Any = None, player_index: int | None = None) -> str:
    if pc is None:
        pc, err = resolve_pc(player_index)
        if pc is None:
            return err or "no PC"
    pawn = _pawn_for_pc(pc)
    if pawn is None:
        return "ffyl: no pawn"
    statics = _inventory_statics()
    _try_call(pawn, "SetCanBeDowned", True)
    if statics is not None:
        unblock = getattr(statics, "UnblockCharacterHealth", None)
        if callable(unblock):
            try:
                unblock(pawn)
            except Exception:
                pass
        drain = getattr(statics, "DrainResourcePool", None)
        if callable(drain):
            for resource in (
                "HealthType_Player_Overshield",
                "HealthType_Player_Shield_Armor",
                "HealthType_Player_Health_Flesh",
            ):
                try:
                    drain(pawn, resource, 1.0, 0.0)
                except Exception:
                    pass
    start = getattr(pawn, "StartDownState", None)
    if not callable(start):
        return "ffyl: StartDownState missing"
    try:
        start(False)
        return "ffyl OK StartDownState(False)"
    except Exception as exc:
        return f"ffyl ERR {exc!r}"


def _backpack_occupied_count(pc: Any) -> int:
    ps = getattr(pc, "PlayerState", None) if pc is not None else None
    wrapper = getattr(ps, "BackpackItems", None) if ps is not None else None
    entries = getattr(wrapper, "items", None) if wrapper is not None else None
    try:
        slots = list(entries) if entries is not None else []
    except Exception:
        return -1
    n = 0
    for slot in slots:
        try:
            inv_item = getattr(slot, "InventoryItem", None)
        except Exception:
            inv_item = None
        if inv_item is None:
            continue
        for attr in ("Handle", "SourceItemHandle", "ItemHandle", "ItemSerial", "Serial"):
            try:
                value = getattr(inv_item, attr, None)
            except Exception:
                value = None
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() not in ("none", "null"):
                n += 1
                break
    return n


def _make_spill_pattern(name: str) -> Any | None:
    try:
        from unrealsdk.unreal import FGameDataHandle  # type: ignore[import-not-found]

        return FGameDataHandle(_SPAWN_PATTERN_TYPE, name)
    except Exception:
        pass
    try:
        from unrealsdk.unreal import FGbxDefPtr  # type: ignore[import-not-found]

        return FGbxDefPtr(name, type="SpawnPatternDef")
    except Exception:
        return None


def _try_drop_one_backpack_item(pc: Any, pawn: Any, slot: Any, inv_item: Any) -> bool:
    targets: list[Any] = [pc, pawn]
    statics = _inventory_statics()
    if statics is not None:
        targets.append(statics)
    names = (
        "ServerDropItem",
        "Server_DropItem",
        "DropItem",
        "ServerDropBackpackItem",
        "Server_DropBackpackItem",
        "ThrowItem",
    )
    args_list: list[tuple[Any, ...]] = []
    for obj in (inv_item, slot):
        if obj is not None:
            args_list.append((obj,))
            args_list.append((pc, obj))
            args_list.append((obj, pawn))
    for obj in targets:
        if obj is None:
            continue
        for name in names:
            fn = getattr(obj, name, None)
            if not callable(fn):
                continue
            for args in args_list:
                try:
                    fn(*args)
                    return True
                except TypeError:
                    continue
                except Exception:
                    continue
    return False


def do_empty_backpack(pc: Any = None, player_index: int | None = None) -> str:
    if pc is None:
        pc, err = resolve_pc(player_index)
        if pc is None:
            return err or "no PC"
    statics = _inventory_statics()
    if statics is None:
        return "empty: missing statics"
    empty_fn = getattr(statics, "EmptyContainer", None)
    if not callable(empty_fn):
        return "empty: EmptyContainer missing"
    try:
        from unrealsdk.unreal import FGbxDefPtr  # type: ignore[import-not-found]

        ptr = FGbxDefPtr("Backpack", type="InventoryContainerDef")
        empty_fn(pc, ptr)
        return "empty backpack OK (deleted)"
    except Exception as exc:
        return f"empty ERR {exc!r}"


def _backpack_occupied_entries(pc: Any) -> list[tuple[Any, Any]]:
    ps = getattr(pc, "PlayerState", None) if pc is not None else None
    wrapper = getattr(ps, "BackpackItems", None) if ps is not None else None
    entries = getattr(wrapper, "items", None) if wrapper is not None else None
    try:
        slots = list(entries) if entries is not None else []
    except Exception:
        return []
    occupied: list[tuple[Any, Any]] = []
    for slot in slots:
        try:
            inv_item = getattr(slot, "InventoryItem", None)
        except Exception:
            inv_item = None
        if inv_item is None:
            continue
        for attr in ("Handle", "SourceItemHandle", "ItemHandle", "ItemSerial", "Serial"):
            try:
                value = getattr(inv_item, attr, None)
            except Exception:
                value = None
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() not in ("none", "null"):
                occupied.append((slot, inv_item))
                break
    return occupied


def do_drop_backpack(pc: Any = None, player_index: int | None = None) -> str:
    if pc is None:
        pc, err = resolve_pc(player_index)
        if pc is None:
            return err or "no PC"
    pawn = _pawn_for_pc(pc)
    statics = _inventory_statics()
    if pawn is None or statics is None:
        return "drop: missing pawn/statics"
    fn = getattr(statics, "SpillOutItemsInContainer", None)
    if not callable(fn):
        return "drop: SpillOutItemsInContainer missing"
    patterns: list[tuple[str, Any]] = []
    for name in _SPAWN_PATTERN_NAMES:
        handle = _make_spill_pattern(name)
        if handle is not None:
            patterns.append((name, handle))
    if not patterns:
        return "drop: could not build spawn pattern"
    before = _backpack_occupied_count(pc)
    spilled = 0
    last: Exception | None = None
    stagnant = 0
    prev = before
    # Cap passes hard — long SpillOut + shape pulls was a pyunrealsdk AV magnet.
    max_passes = 40 if before < 0 else min(120, max(int(before) + 6, 6))
    # spawnpattern_default_loot is a one-item chest spit. Keep calling until
    # the backpack is empty instead of returning after the first success.
    for _pass in range(max_passes):
        occupied = _backpack_occupied_count(pc)
        if occupied == 0:
            break
        progressed = False
        for _pname, handle in patterns:
            for socket in ("None", "", "ROOT"):
                try:
                    fn(pc, "Backpack", pawn, handle, socket)
                    spilled += 1
                    progressed = True
                    break
                except Exception as exc:
                    last = exc
                    continue
            if progressed:
                break
        if not progressed:
            break
        try:
            from .loot_shapes import (
                arm_deferred_catch,
                arm_overhead_catch,
                landing_armed,
                pull_new_pickups_into_shape,
            )

            # Rare, light pulls only — fresh find_all every SpillOut pass AVs mid-drop.
            if landing_armed() and (_pass % 5 == 0):
                arm_overhead_catch(6.0)
                arm_deferred_catch(6.0)
                pull_new_pickups_into_shape(limit=2, fresh=False)
        except Exception:
            pass
        now = _backpack_occupied_count(pc)
        if now >= 0 and prev >= 0 and now >= prev:
            stagnant += 1
            if stagnant >= 3:
                break
        else:
            stagnant = 0
        if now >= 0:
            prev = now
    remaining = _backpack_occupied_count(pc)
    dropped_one = 0
    if remaining > 0:
        for slot, inv_item in list(_backpack_occupied_entries(pc)):
            if _try_drop_one_backpack_item(pc, pawn, slot, inv_item):
                dropped_one += 1
    remaining = _backpack_occupied_count(pc)
    if remaining == 0:
        extra = f" +{dropped_one} item RPC" if dropped_one else ""
        return f"drop backpack OK spilled={spilled}{extra} (was {max(0, before)})"
    return (
        f"drop backpack partial spilled={spilled} one-by-one={dropped_one} "
        f"remaining={remaining} last={last!r}"
    )


def _fire_launch_impulse(z_boost: float, pc: Any) -> str:
    character = _pawn_for_pc(pc)
    if character is None:
        return "launch: no character"
    move = _movement(character)
    if move is None:
        return "launch: no movement"
    vx = vy = vz = 0.0
    try:
        vel = getattr(move, "Velocity", None)
        if vel is not None:
            vx = float(getattr(vel, "X", 0.0) or 0.0)
            vy = float(getattr(vel, "Y", 0.0) or 0.0)
            vz = float(getattr(vel, "Z", 0.0) or 0.0)
    except Exception:
        pass
    impulse_z = vz + float(z_boost)
    try:
        impulse = unrealsdk.make_struct(
            "Vector",
            X=float(vx),
            Y=float(vy),
            Z=float(impulse_z),
        )
        move.AddImpulse(impulse, True)
        return f"launch OK Z={impulse_z:.1f} (boost={z_boost})"
    except Exception as exc:
        return f"launch ERR {exc!r}"


def do_launch(
    pc: Any = None,
    player_index: int | None = None,
    z_boost: float = _DEFAULT_LAUNCH_Z,
) -> str:
    if pc is None:
        pc, err = resolve_pc(player_index)
        if pc is None:
            return err or "no PC"
    msg = _fire_launch_impulse(float(z_boost), pc)
    if msg.startswith("launch OK"):
        return msg
    key = _pc_key(pc, player_index)
    _pending_launch[key] = float(z_boost)
    return f"{msg}; queued camera-tick retry"


def _tick_pending_launch(*_args: Any, **_kwargs: Any) -> None:
    if not _pending_launch:
        return
    pending = dict(_pending_launch)
    _pending_launch.clear()
    for key, z in pending.items():
        pc = None
        if key.startswith("idx:"):
            try:
                pc, _ = resolve_pc(int(key.split(":", 1)[1]))
            except Exception:
                pc = None
        if pc is None:
            try:
                pc = get_pc()
            except Exception:
                pc = None
        if pc is None:
            continue
        _log(_fire_launch_impulse(float(z), pc))


def ensure_launch_hook() -> None:
    from unrealsdk import hooks
    from unrealsdk.hooks import Type

    path = "/Script/Engine.CameraModifier:BlueprintModifyCamera"
    ident = "sqbt_faafo_launch_v1"
    try:
        hooks.remove_hook(path, Type.POST, ident)
    except Exception:
        pass
    try:
        hooks.add_hook(path, Type.POST, ident, _tick_pending_launch)
    except Exception as exc:
        _log(f"launch camera hook skipped: {exc!r}")
