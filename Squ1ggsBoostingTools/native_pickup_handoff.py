"""Exact native loot-ID handoff for the verified BL4 build; no serial injection."""
import ctypes as C
import struct

_STAMP = 0x6AA81051
_GETTER = bytes.fromhex("4889d08a917c02000088500480fa0175088b89780200008908c3")
_control = None
_shape_items = {}


def remember_shape_item(actor):
    """Keep pickup identity independently of animation pins and hold settings."""
    from unrealsdk.unreal import WeakPointer
    address = int(actor._get_address())
    reference = WeakPointer(actor)
    if address and reference() is not None:
        _shape_items[address] = {"addr": address, "reference": reference, "shape_managed": True}
        from .native_shape_visibility import remember
        remember(actor)


def tracked_shape_rows():
    rows = []
    for address, row in list(_shape_items.items()):
        actor = row["reference"]()
        if actor is None or int(actor._get_address()) != address:
            _shape_items.pop(address, None)
        else:
            rows.append(row)
    return rows


def clear_shape_tracking():
    _shape_items.clear()


def _module_base():
    kernel = C.WinDLL("kernel32", use_last_error=True)
    kernel.GetModuleHandleW.argtypes = [C.c_wchar_p]
    kernel.GetModuleHandleW.restype = C.c_void_p
    return kernel, int(kernel.GetModuleHandleW(None))


def _identity(actor, read, base):
    """Read the verified IJunkSystemObject getter's fields, never call a vtable."""
    address = int(actor._get_address())
    pe = base + struct.unpack_from("<I", read(base, 64), 60)[0]
    if struct.unpack_from("<I", read(pe, 12), 8)[0] != _STAMP:
        raise ValueError("Native pickup build is not verified")
    if str(actor.Class.Name) != "InventoryPickup" or int(actor.Class._get_struct_size()) != 2496:
        raise ValueError("Native pickup class/layout is not verified")
    if not any(str(cls.Name) == "JunkSystemObject" for cls in actor.Class.Interfaces):
        raise ValueError("Pickup does not implement native loot identity")
    table = struct.unpack("<Q", read(address + 0x520, 8))[0]
    if table != base + 0xB310620:
        raise ValueError("Native pickup interface table changed")
    getter = struct.unpack("<Q", read(table + 24, 8))[0]
    if getter != base + 0xEF8DE8 or read(getter, len(_GETTER)) != _GETTER:
        raise ValueError("Native pickup identity getter changed")
    identity = read(address + 0x798, 5)
    if identity[4] != 1:
        raise ValueError("Pickup no longer has a native loot identity")
    return identity[:4]


def _validate_function(func):
    if str(func.Name) != "ServerUseJunkObject" or int(func._get_struct_size()) != 8:
        raise ValueError("Native pickup RPC layout changed")
    actual = [(str(p.Name), type(p).__name__, int(p.Offset_Internal), int(p.ElementSize))
              for p in func._properties()]
    expected = [("JunkId", "ZStructProperty", 0, 4),
                ("bWasHeld", "ZBoolProperty", 4, 1),
                ("bAutoTrash", "ZBoolProperty", 5, 1)]
    if actual != expected:
        raise ValueError("Native pickup RPC fields changed")


def prepare(pc, actor, *, was_held=False, auto_trash=False):
    """Validate everything before the caller releases its shape pin."""
    from unrealsdk.unreal import WeakPointer
    from .loot_junk_diagnostics import _read
    pc_ref, actor_ref = WeakPointer(pc), WeakPointer(actor)
    if pc_ref() is None or actor_ref() is None or not pc.HasAuthority():
        raise ValueError("Native pickup requires live host authority")
    kernel, base = _module_base()
    identity = _identity(actor, _read, base)
    func = pc.ServerUseJunkObject.func
    _validate_function(func)
    sdk = kernel.GetModuleHandleW("unrealsdk.dll")
    kernel.GetProcAddress.argtypes = [C.c_void_p, C.c_char_p]
    kernel.GetProcAddress.restype = C.c_void_p
    export = kernel.GetProcAddress(sdk, b"_unrealsdk_export__process_event") if sdk else None
    if not export:
        raise ValueError("SDK native event dispatcher unavailable")
    # SDK C export: void process_event(UObject*, UFunction*, void*).
    # Own the 8-byte POD buffer; reflected struct assignment erases opaque JunkId.
    params = C.create_string_buffer(identity + bytes((bool(was_held), bool(auto_trash), 0, 0)), 8)
    dispatch = C.PYFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_void_p)(export)

    def send():
        current_pc, current_actor = pc_ref(), actor_ref()
        if current_pc is None or current_actor is None:
            return False
        if _identity(current_actor, _read, base) != identity:
            return False
        dispatch(int(current_pc._get_address()), int(func._get_address()), C.addressof(params))
        return True  # Request sent; not a claim that inventory delivery completed.

    return send


def handoff(pc, actor, row, *, was_held=False):
    """Stop shape movement, retaining exact identity for a declined-use retry."""
    from . import loot_shapes
    send = prepare(pc, actor, was_held=was_held)
    loot_shapes._pause_coop_force_net_for_grab(seconds=3.0, reason="native shape pickup")
    loot_shapes._release_pin_for_pickup(actor, row)
    # A full backpack can decline the request. Keep weak identity matching so
    # another press can retry, without publishing/moving the actor again.
    loot_shapes._released_held_pins.append(row)
    return send()


def control(mode="status"):
    """Explicit single-item check; never part of the regular status inspection."""
    global _control
    if mode == "status":
        if _control is None:
            return {"started": False}
        from .serial_rewards import _backpack_occupied_snapshot
        pc = _control["pc"]()
        after = _backpack_occupied_snapshot(pc) if pc is not None else {}
        actor = _control["actor"]()
        native_valid = None
        if actor is not None:
            from .loot_junk_diagnostics import _read
            native_valid = _read(int(actor._get_address()) + 0x79C, 1).hex()
        return {"started": True, "actor_alive": _control["actor"]() is not None,
                "native_valid_byte": native_valid,
                "actor_hidden": bool(actor.bHidden) if actor is not None else None,
                "before_count": len(_control["before"]), "after_count": len(after),
                "inventory_changed": after != _control["before"]}
    if mode != "start" or _control is not None:
        raise ValueError("Single-item native test already started or invalid mode")
    from . import loot_shapes
    from .shinies import _pc_for_party_index
    from .serial_rewards import _backpack_occupied_snapshot
    from unrealsdk.unreal import WeakPointer
    pc = _pc_for_party_index(1)
    if pc is None:
        raise ValueError("Guest is not connected")
    for row in list(loot_shapes._pinned_slots):
        reference = row.get("reference")
        actor = reference() if reference is not None else None
        if actor is None or not row.get("hold"):
            continue
        send = prepare(pc, actor)
        _control = {"pc": WeakPointer(pc), "actor": WeakPointer(actor),
                    "before": _backpack_occupied_snapshot(pc)}
        loot_shapes._release_pin_for_pickup(actor, row)
        sent = send()
        return {"started": True, "request_sent": sent}
    raise ValueError("No live held shape item available")
