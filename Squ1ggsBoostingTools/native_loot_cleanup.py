"""Paced world-loot removal through the game's exact native loot IDs."""
from __future__ import annotations

from collections import deque
import ctypes as C
import time

_pending = deque()
_queued = set()
_pc = None
_world = None
_last_tick = 0.0
_counts = {"sent": 0, "failed": 0, "gone": 0, "cancelled": 0}


def _validate_function(func):
    expected = [("WorldContextObject", "ZObjectProperty", 0, 8),
                ("JunkId", "ZStructProperty", 8, 4)]
    fields = [(str(p.Name), type(p).__name__, int(p.Offset_Internal), int(p.ElementSize))
              for p in func._properties()]
    if (str(func) != "Function'/Script/GbxGame.JunkSystemFunctionLibrary:DestroyJunkItem'"
            or int(func._get_struct_size()) != 16 or fields != expected):
        raise ValueError("Native loot cleanup API layout changed")


def _identity(actor):
    from .native_pickup_handoff import _identity as read_identity, _module_base
    from .loot_junk_diagnostics import _read
    _, base = _module_base()
    return read_identity(actor, _read, base)


def _dispatch(pc, actor, identity):
    import unrealsdk
    from .native_pickup_handoff import _module_base
    if not pc.HasAuthority() or not actor.HasAuthority() or _identity(actor) != identity:
        raise ValueError("Loot identity or host authority changed before cleanup")
    library = unrealsdk.find_class("/Script/GbxGame.JunkSystemFunctionLibrary").ClassDefaultObject
    func = library.DestroyJunkItem.func
    _validate_function(func)
    kernel, _ = _module_base()
    sdk = kernel.GetModuleHandleW("unrealsdk.dll")
    kernel.GetProcAddress.argtypes = [C.c_void_p, C.c_char_p]
    kernel.GetProcAddress.restype = C.c_void_p
    export = kernel.GetProcAddress(sdk, b"_unrealsdk_export__process_event") if sdk else None
    if not export:
        raise ValueError("SDK native event dispatcher unavailable")
    # Preserve the opaque ID bytes. Reflected assignment/copying zeros JunkId.
    params = C.create_string_buffer(int(pc._get_address()).to_bytes(8, "little") + identity + bytes(4), 16)
    dispatch = C.PYFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_void_p)(export)
    dispatch(int(library._get_address()), int(func._get_address()), C.addressof(params))


def status():
    return {**_counts, "pending": len(_pending)}


def message():
    state = status()
    if state["pending"]:
        text = f"Clearing world loot: {state['pending']} remaining."
    else:
        text = f"World loot cleanup: {state['sent']} removal request(s) sent."
    if state["failed"]:
        text += f" {state['failed']} item(s) could not be cleared."
    if state["cancelled"]:
        text += f" {state['cancelled']} cancelled after the session changed."
    return text


def cancel():
    global _pc, _world
    _counts["cancelled"] += len(_pending)
    _pending.clear()
    _queued.clear()
    _pc = _world = None


def queue_clear(pc, actors):
    global _pc, _world, _last_tick
    from unrealsdk.unreal import WeakPointer
    from .shinies import _get_world
    world = _get_world()
    if pc is None or world is None or not pc.HasAuthority():
        raise ValueError("Load into a host session before clearing world loot")
    if _world is not None:
        previous = _world()
        if previous is None or int(previous._get_address()) != int(world._get_address()):
            cancel()
    if not _pending:
        _counts.update(sent=0, failed=0, gone=0, cancelled=0)
        _queued.clear()
    _pc, _world = WeakPointer(pc), WeakPointer(world)
    for actor in actors:
        try:
            reference = WeakPointer(actor)
            if reference() is None:
                _counts["gone"] += 1
                continue
            if not actor.HasAuthority():
                _counts["gone"] += 1
                continue
            identity = _identity(actor)
            key = (int(actor._get_address()), identity)
            if key in _queued:
                continue
            _pending.append((reference, identity, key))
            _queued.add(key)
        except Exception:
            _counts["failed"] += 1
    _last_tick = 0.0
    return message()


def runtime_tick():
    global _last_tick
    if not _pending:
        return
    now = time.monotonic()
    if now - _last_tick < 0.05:
        return
    _last_tick = now
    from .shinies import _get_world
    pc, world, current = _pc(), _world(), _get_world()
    if (pc is None or world is None or current is None or not pc.HasAuthority()
            or int(world._get_address()) != int(current._get_address())):
        cancel()
    else:
        for _ in range(min(6, len(_pending))):
            reference, identity, key = _pending.popleft()
            _queued.discard(key)
            actor = reference()
            if actor is None:
                _counts["gone"] += 1
                continue
            try:
                if _identity(actor) != identity:
                    raise ValueError("Loot identity changed while cleanup was queued")
                _dispatch(pc, actor, identity)
                _counts["sent"] += 1
            except Exception:
                _counts["failed"] += 1
    from . import loot_shapes
    loot_shapes._status = message()
    if not _pending:
        loot_shapes._log(loot_shapes._status)
