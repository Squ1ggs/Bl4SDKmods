"""Bounded, read-only native pickup interface evidence. Never calls native slots."""
import ctypes as C
import struct


def inspect(actor):
    import unrealsdk
    from .loot_junk_diagnostics import _read
    from unrealsdk.unreal import WeakPointer
    reference = WeakPointer(actor)
    kernel = C.WinDLL("kernel32", use_last_error=True)
    kernel.GetModuleHandleW.argtypes = [C.c_wchar_p]
    kernel.GetModuleHandleW.restype = C.c_void_p
    base = int(kernel.GetModuleHandleW(None))
    pe = base + struct.unpack_from("<I", _read(base, 64), 60)[0]
    header = _read(pe, 96)
    image_size = struct.unpack_from("<I", header, 80)[0]
    size = int(actor.Class._get_struct_size())
    if not 0 < size <= 4096 or reference() is None:
        raise ValueError("Unexpected pickup allocation")
    data = _read(int(actor._get_address()), size)
    from .shinies import _pc_for_party_index
    pc = _pc_for_party_index(1)
    func = pc.ServerUseJunkObject.func
    params = [{"name": str(prop.Name), "type": type(prop).__name__,
               "offset": int(prop.Offset_Internal), "size": int(prop.ElementSize)}
              for prop in func._properties()]
    world_system = {}
    try:
        from .shinies import _get_world
        world = _get_world()
        world_system["world"] = str(world)
        address = int(world._get_address())
        for label, offset in (("game_instance", 0x1f0), ("native_game", 0x1e0), ("interface", 0x38)):
            address = struct.unpack("<Q", _read(address + offset, 8))[0]
            world_system[label] = hex(address)
        table = struct.unpack("<Q", _read(address, 8))[0]
        getter = struct.unpack("<Q", _read(table + 0x308, 8))[0]
        world_system["getter"] = {"rva": getter-base, "code": _read(getter, 256).hex()}
        world_system["index"] = _read(address + 0x1f0, 1).hex()
        getter = struct.unpack("<Q", _read(table + 0x2b0, 8))[0]
        world_system["container_getter"] = {"rva": getter-base, "code": _read(getter, 128).hex()}
        getter = struct.unpack("<Q", _read(table + 0x3a0, 8))[0]
        world_system["container_impl"] = {"rva": getter-base, "code": _read(getter, 64).hex()}
        container = struct.unpack("<Q", _read(address + 0x178, 8))[0]
        world_system["container"] = hex(container)
        world_system["container_weak"] = _read(container + 0x60, 8).hex()
        system = struct.unpack("<Q", _read(container + 0x148, 8))[0]
        world_system["loot_system"] = hex(system)
        table = struct.unpack("<Q", _read(system, 8))[0]
        world_system["loot_table_rva"] = table-base
        world_system["loot_slots"] = [{"slot": slot, "rva": entry-base, "code": _read(entry, 128).hex()}
                                      for slot, entry in enumerate(struct.unpack("<96Q", _read(table, 768)))
                                      if base <= entry < base+image_size-128]
    except Exception as exc:
        world_system["error"] = repr(exc)
    actor_flags = []
    for parent in actor.Class._superfields():
        for prop in parent._properties():
            offset = int(prop.Offset_Internal)
            if offset <= 0x78:
                actor_flags.append({"name": str(prop.Name), "offset": offset,
                                    "value": str(getattr(actor, str(prop.Name), None))[:120]})
    native_functions = []
    for name in ("DestroyJunkItem", "MakeJunkWithinBoundsFall", "DetachJunkItem"):
        library = unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject
        function = getattr(library, name).func
        raw = _read(int(function._get_address()), 256)
        pointers = []
        for offset in range(40, 249, 8):
            pointer = struct.unpack_from("<Q", raw, offset)[0]
            if base <= pointer < base + image_size - 512:
                pointers.append({"offset": offset, "rva": pointer-base, "code": _read(pointer, 512).hex()})
        native_functions.append({"name": name, "pointers": pointers})
    tables = []
    for offset in range(0, len(data) - 7, 8):
        pointer = struct.unpack_from("<Q", data, offset)[0]
        if not base <= pointer < base + image_size - 128:
            continue
        slots = struct.unpack("<16Q", _read(pointer, 128))
        if not all(base <= entry < base + image_size - 96 for entry in slots[:2]):
            continue
        tables.append({"offset": offset, "rva": pointer-base,
                       "slots": [{"slot": i, "rva": entry-base, "code": _read(entry, 96).hex()}
                                 for i, entry in enumerate(slots)
                                 if base <= entry < base + image_size - 96]})
        if len(tables) >= 20:
            break
    return {"actor": str(actor), "size": size, "native_functions": native_functions, "actor_flags": actor_flags, "world_system": world_system,
            "native_use": {"function": str(func), "size": int(func._get_struct_size()), "params": params},
            "candidate_id": data[0x798:0x79d].hex(),
            "class_api": [name for name in dir(actor.Class) if "interface" in name.lower()],
            "interfaces": str(actor.Class.Interfaces),
            "sdk_calls": [name for name in dir(unrealsdk) if "call" in name.lower() or "event" in name.lower()],
            "actor_calls": [name for name in dir(type(actor)) if "call" in name.lower() or "event" in name.lower() or "interface" in name.lower()],
            "function_calls": [name for name in dir(type(actor.K2_GetActorLocation)) if not name.startswith("__")],
            "function_doc": str(type(actor.K2_GetActorLocation).__doc__),
            "timestamp": struct.unpack_from("<I", header, 8)[0],
            "tables": tables}
