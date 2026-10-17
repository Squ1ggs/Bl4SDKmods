"""Scoped native loot diagnostics and explicitly invoked single-item controls."""
from __future__ import annotations

import ctypes as C
from pathlib import Path
import json
import copy

import unrealsdk
from unrealsdk import hooks
from unrealsdk.unreal import WeakPointer

_PATH = "/Script/OakGame.OakPlayerController:ServerUseJunkObject"
_IDENT = "Squ1ggsBoostingTools.junk_id_probe"
_actors = []
_events = []
_seen = set()
_remaining = 0
_kernel = None
_spawn_remaining = 0
_spawn_results = []
_spawn_ids = []
_native_control = None
_control_before = set()


def _read(address, size):
    global _kernel
    if not 0x10000 < address < 0x800000000000 or not 0 < size <= 4096:
        raise ValueError("Native probe read outside bounds")
    if _kernel is None:
        _kernel = C.WinDLL("kernel32", use_last_error=True)
        _kernel.GetCurrentProcess.restype = C.c_void_p
        _kernel.ReadProcessMemory.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
        _kernel.ReadProcessMemory.restype = C.c_bool
    buffer = C.create_string_buffer(size)
    count = C.c_size_t()
    if not _kernel.ReadProcessMemory(_kernel.GetCurrentProcess(), address, buffer, size, C.byref(count)) or count.value != size:
        raise OSError("Native probe memory unreadable")
    return buffer.raw


def _observe(obj, args, _ret, _function):
    global _remaining
    if _remaining <= 0:
        return None
    if getattr(args, "JunkId", None) is None:
        return None
    try:
        junk = args.JunkId
        size = int(junk._type._get_struct_size())
        if not 1 <= size <= 32:
            raise ValueError("Unexpected native JunkId size")
        token = _read(int(junk._get_address()), size)
        if token in _seen:
            return None
        _seen.add(token)
        _remaining -= 1
        row = {"controller": str(obj), "junk_size": size, "junk_hex": token.hex(), "matches": [], "scanned": 0}
        _events.append(row)
        if not any(token):
            row["match_skipped"] = "A zero byte pattern cannot identify a pickup allocation"
            return None
        for reference in _actors:
            actor = reference()
            if actor is None:
                continue
            allocation_size = int(actor.Class._get_struct_size())
            if not 0 < allocation_size <= 4096:
                continue
            data = _read(int(actor._get_address()), allocation_size)
            row["scanned"] += 1
            offset = data.find(token)
            while offset >= 0 and len(row["matches"]) < 12:
                row["matches"].append({"actor": str(actor), "offset": offset, "allocation_size": allocation_size})
                offset = data.find(token, offset + 1)
    except Exception as exc:
        _events.append({"error": repr(exc)[:256]})
        _remaining = 0
    return None


def install():
    global _actors, _remaining
    remove()
    _events.clear()
    _seen.clear()
    _actors = [WeakPointer(actor) for actor in unrealsdk.find_all("InventoryPickup", False)
               if "Default__" not in str(actor)][:400]
    _remaining = 2
    hooks.add_hook(_PATH, hooks.Type.PRE, _IDENT, _observe)
    hooks.add_hook(_PATH, hooks.Type.POST_UNCONDITIONAL, _IDENT, _observe)
    return snapshot()


def snapshot():
    result = {"installed": any(hooks.has_hook(_PATH, kind, _IDENT)
                               for kind in (hooks.Type.PRE, hooks.Type.POST_UNCONDITIONAL)),
              "remaining": _remaining, "actor_limit": len(_actors), "events": list(_events),
              "spawn_results": list(_spawn_results)}
    actor = _native_control() if _native_control is not None else None
    if actor is not None:
        result["native_control"] = {"actor": str(actor), "bReplicates": bool(actor.bReplicates)}
        location = actor.K2_GetActorLocation()
        result["native_control"]["position"] = {axis: float(getattr(location, axis)) for axis in ("X", "Y", "Z")}
        from .loot_shapes import _physics_components
        for comp in _physics_components(actor):
            try:
                result["native_control"].update(simulating=bool(comp.IsSimulatingPhysics("")),
                                               gravity=bool(comp.IsGravityEnabled()),
                                               awake=bool(comp.IsAnyRigidBodyAwake()))
            except Exception as exc:
                result["native_control"]["state_error"] = repr(exc)[:256]
    else:
        result["native_control"] = {"live": False, "tracked": _native_control is not None}
    (Path(__file__).parent / "logs" / "loot_junk_probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def inspect_native_handles():
    """Resolve the proven control pool and existing pattern labels; never spawn."""
    from unrealsdk.unreal import FGameDataHandle
    from . import shinies
    library = unrealsdk.find_class("ItemPoolFunctionLibrary").ClassDefaultObject
    bound = library.SpawnItemsFromItemPoolUsingTransform_Drop
    pool_type = int(bound.func._find_prop("itempool").TypeHandle)
    pattern_type = int(bound.func._find_prop("SpawnPattern").TypeHandle)
    pool_name = shinies._resolve_native_pool_name("itempool_bor_sg_05_legendary_convergence_shiny")
    result = {"pool_type": pool_type, "pattern_type": pattern_type, "handles": []}
    junk_struct = unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject.RemoveOnlyPickupableByOwnerRestriction.func._find_prop("JunkId").Struct
    result["junk_id_size"] = int(junk_struct._get_struct_size())
    for type_handle, name in ((pool_type, pool_name),
                              (pattern_type, "spawnpattern_loot_at_location"),
                              (pattern_type, "spawnpattern_default_loot"),
                              (pattern_type, "spawnpattern_lootable_upandforward")):
        try:
            handle = FGameDataHandle(type_handle, name)
            result["handles"].append({"name": name, "type": type_handle,
                                      "resolved": bool(handle._get_address())})
        except Exception as exc:
            result["handles"].append({"name": name, "error": repr(exc)[:256]})
    result["functions"] = []
    from unrealsdk.unreal import UFunction
    for function in library.Class._fields():
        if isinstance(function, UFunction) and "SpawnItemsFromItemPool" in str(function.Name):
            result["functions"].append({"name": str(function.Name), "parameters": [
                {"name": str(prop.Name), "type": type(prop).__name__,
                 "struct": str(prop.Struct) if type(prop).__name__ == "ZStructProperty" else None}
                for prop in function._properties() if int(prop.PropertyFlags) & 0x80]})
    return result


def remove():
    global _remaining, _actors
    hooks.remove_hook(_PATH, hooks.Type.PRE, _IDENT)
    hooks.remove_hook(_PATH, hooks.Type.POST_UNCONDITIONAL, _IDENT)
    _remaining = 0
    _actors = []


def inspect_attached_control():
    """Read native IDs attached to the control's Xbox parent without changing them."""
    from .inventory_capacity import get_party_player_states
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1:
        return {"available": False}
    pawn = matches[0].Owner.Pawn
    library = unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject
    result = library.GetJunkAttachedToActor(Actor=pawn, OutJunkIds=[])
    ids = result[1]
    _spawn_ids.clear()
    rows = []
    for token in list(ids)[:8]:
        size = int(token._type._get_struct_size())
        if size != 4 or list(token._type._properties()):
            raise RuntimeError("Native JunkId layout changed")
        original = _read(int(token._get_address()), size)
        copied = copy.copy(token)
        copied_bytes = _read(int(copied._get_address()), size)
        # Native output views retain their SDK-owned parent call storage. Keeping
        # this view avoids the SDK's reflected-field copy losing opaque bytes.
        _spawn_ids.append(token)
        rows.append({"size": size, "original_hex": original.hex(),
                     "copied_hex": copied_bytes.hex()})
    return {"available": True, "parent": str(pawn), "count": len(ids), "ids": rows}


def inspect_anchor_api():
    from unrealsdk.unreal import UFunction
    result = []
    for class_name, names in (("GameplayStatics", {"BeginDeferredActorSpawnFromClass", "FinishSpawningActor"}),
                               ("Actor", {"HasActorBegunPlay", "GetActorTransform", "GetTransform", "K2_GetActorTransform", "AddComponentByClass", "FinishAddComponent", "AddComponent", "K2_TeleportTo", "SetReplicates", "SetReplicateMovement"}),
                               ("SceneComponent", {"SetIsReplicated"})):
        cls = unrealsdk.find_class(class_name)
        seen = set()
        for parent in cls._superfields():
            for function in parent._fields():
                if not isinstance(function, UFunction) or str(function.Name) not in names or str(function) in seen:
                    continue
                seen.add(str(function))
                result.append({"function": str(function), "fields": [
                    {"name": str(prop.Name), "type": type(prop).__name__, "flags": int(prop.PropertyFlags),
                     "struct": str(prop.Struct) if type(prop).__name__ == "ZStructProperty" else None}
                    for prop in function._properties() if int(prop.PropertyFlags) & 0x80]})
    for name in ("ENetDormancy", "ESpawnActorCollisionHandlingMethod", "ESpawnActorScaleMethod"):
        enum = unrealsdk.find_enum(name)
        result.append({"enum": name, "values": {key: int(value) for key, value in enum.__members__.items()}})
    prop = unrealsdk.find_class("GameplayStatics").ClassDefaultObject.BeginDeferredActorSpawnFromClass.func._find_prop("SpawnTransform")
    result.append({"transform_fields": [{"name": str(field.Name), "type": type(field).__name__,
                                         "struct": str(field.Struct) if type(field).__name__ == "ZStructProperty" else None}
                                        for field in prop.Struct._properties()]})
    deferred = []
    for actor in unrealsdk.find_all("Actor", True):
        if "Default__" not in str(actor) and getattr(actor, "RootComponent", None) is None:
            deferred.append({"actor": str(actor), "replicates": bool(actor.bReplicates),
                             "authority": bool(actor.HasAuthority())})
    result.append({"rootless_actors": deferred[:8], "rootless_count": len(deferred)})
    for name in ("JunkAttachParent", "GbxActor", "JunkSystemObject"):
        cls = unrealsdk.find_class(name)
        result.append({"class": name, "parents": [str(parent.Name) for parent in cls._superfields()],
                       "functions": [str(field.Name) for field in cls._fields() if isinstance(field, UFunction)],
                       "properties": [{"name": str(field.Name), "type": type(field).__name__}
                                      for field in cls._properties()]})
    interface = unrealsdk.find_class("JunkAttachParent")
    implementations = []
    checked = 0
    for cls in unrealsdk.find_all("Class", False):
        path = str(cls)
        if not ("/Script/GbxGame." in path or "/Script/OakGame." in path) or not cls._inherits(unrealsdk.find_class("Actor")):
            continue
        checked += 1
        if cls._implements(interface):
            implementations.append({"class": str(cls), "name": str(cls.Name),
                                    "parents": [str(parent.Name) for parent in cls._superfields()]})
        if checked >= 1024:
            break
    result.append({"native_attach_implementations": implementations, "checked_classes": checked})
    result.append({"all_junk_functions": [str(function) for function in unrealsdk.find_all("Function", False)
                                         if "junk" in str(function).lower()][:96]})
    cls = unrealsdk.find_class("LootableObject")
    cdo = cls.ClassDefaultObject
    fields = []
    seen = set()
    for parent in cls._superfields():
        for prop in parent._properties():
            name = str(prop.Name)
            if name in seen or not any(term in name.lower() for term in ("mesh", "loot", "root", "body", "stage", "level", "socket", "junk", "actorData".lower(), "attribute")):
                continue
            seen.add(name)
            entry = {"name": name, "type": type(prop).__name__}
            if type(prop).__name__ in ("ZObjectProperty", "ZWeakObjectProperty", "ZNameProperty", "ZIntProperty", "ZBoolProperty"):
                entry["default"] = str(getattr(cdo, name, None))
            if type(prop).__name__ == "ZStructProperty":
                entry["struct"] = str(prop.Struct)
                entry["members"] = [str(member.Name) for member in prop.Struct._properties()]
            fields.append(entry)
    result.append({"lootable_defaults": fields, "interfaces": [str(value.Name) for value in cls.Interfaces]})
    from .inventory_capacity import get_party_player_states
    guests = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(guests) == 1:
        loc = guests[0].Owner.Pawn.K2_GetActorLocation()
        templates = []
        for actor in unrealsdk.find_all("LootableObject", False):
            if "Default__" in str(actor) or actor.RootComponent is None:
                continue
            actor_def = getattr(actor.GbxActorData, "GbxActorDef", None)
            if actor_def is None or not int(actor_def._get_address()):
                continue
            pos = actor.K2_GetActorLocation()
            distance = sum((float(getattr(pos, axis)) - float(getattr(loc, axis))) ** 2 for axis in ("X", "Y", "Z")) ** .5
            templates.append({"actor": str(actor), "class": str(actor.Class),
                              "definition": str(actor_def._name), "distance_cm": round(distance),
                              "game_stage": int(actor.GameStage)})
        result.append({"live_container_templates": sorted(templates, key=lambda row: row["distance_cm"])[:4]})
    return result


def spawn_attached_control():
    """One native attached item, using typed name handles rather than Actor flags."""
    if globals().get("_attached_control_attempted", False):
        return {"spawn_call": False, "reason": "control already attempted", "spawn_results": list(_spawn_results)}
    from .inventory_capacity import get_party_player_states
    from unrealsdk.unreal import FGameDataHandle
    from . import shinies
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1:
        return {"spawn_call": False, "reason": "Xbox player is not uniquely present"}
    pc = matches[0].Owner
    pawn = getattr(pc, "Pawn", None)
    if pawn is None:
        return {"spawn_call": False, "reason": "Xbox pawn is unavailable"}
    bound = unrealsdk.find_class("ItemPoolFunctionLibrary").ClassDefaultObject.SpawnItemsFromItemPool_Attach
    pool_type = int(bound.func._find_prop("itempool").TypeHandle)
    pool_name = shinies._resolve_native_pool_name("itempool_bor_sg_05_legendary_convergence_shiny")
    pool = FGameDataHandle(pool_type, pool_name)
    # The SDK constructor sets name/type only. The engine resolves this handle;
    # _get_address()==0 before that call is not evidence that the name is invalid.
    globals()["_attached_control_attempted"] = True
    globals()["_spawn_remaining"] = 1
    result = bound(SourceActor=pawn, itempool=pool, SocketName="", OutJunkIds=[])
    capture_spawn_result(result)
    globals()["_spawn_remaining"] = 0
    return {"spawn_call": True, "parent": str(pawn), "pool": pool_name,
            "spawn_results": list(_spawn_results), "native_ids": len(_spawn_ids)}


def capture_spawn_result(result):
    global _spawn_remaining
    if _spawn_remaining <= 0:
        return
    _spawn_remaining -= 1
    row = {"return_type": type(result).__name__, "ids": []}
    _spawn_results.append(row)
    values = result[1:] if isinstance(result, tuple) else (result,)
    row["output_types"] = [type(value).__name__ for value in values]
    row["array_lengths"] = []
    row["token_types"] = []
    for value in values:
        try:
            tokens = list(value)[:4]
            row["array_lengths"].append(len(value))
        except TypeError:
            continue
        for token in tokens:
            row["token_types"].append(str(getattr(getattr(token, "_type", None), "Name", "")))
            if str(getattr(getattr(token, "_type", None), "Name", "")) != "JunkId":
                continue
            size = int(token._type._get_struct_size())
            row.setdefault("token_sizes", []).append(size)
            if not 1 <= size <= 32:
                continue
            data = _read(int(token._get_address()), size)
            # Keep the output view and its owning SDK call storage. copy.copy
            # copies reflected fields only and erases this opaque native value.
            _spawn_ids.append(token)
            row["ids"].append({"hex": data.hex(), "size": size})


def spawn_controls():
    """One native drop using names verified in exported game NCS tables."""
    global _spawn_remaining
    if globals().get("_drop_control_attempted", False):
        return {"calls": 0, "reason": "control already attempted", "spawn_results": list(_spawn_results)}
    from unrealsdk.unreal import FGameDataHandle
    from .inventory_capacity import get_party_player_states
    from .item_spawn import comp_loot_drop
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1:
        raise RuntimeError("Xbox player is not uniquely present")
    pc = matches[0].Owner
    pawn = getattr(pc, "Pawn", None)
    if pawn is None:
        raise RuntimeError("Load into a map before native control drops")
    library = unrealsdk.find_class("ItemPoolFunctionLibrary").ClassDefaultObject
    bound = library.SpawnItemsFromItemPoolUsingTransform_Drop
    pool_prop = bound.func._find_prop("itempool")
    pattern_prop = bound.func._find_prop("SpawnPattern")
    pool = FGameDataHandle(int(pool_prop.TypeHandle), "itempool_ar_05_legendary")
    pattern = FGameDataHandle(int(pattern_prop.TypeHandle), "spawnpattern_default_loot")
    transform = comp_loot_drop._get_spawn_transform(pc)
    if transform is None:
        raise RuntimeError("Xbox spawn transform is unavailable")
    globals()["_drop_control_attempted"] = True
    _spawn_remaining = 1
    try:
        result = bound(ContextActor=pawn, SourceTransform=transform, itempool=pool,
                       SpawnPattern=pattern, SocketName="", OutJunkIds=[])
        capture_spawn_result(result)
    finally:
        _spawn_remaining = 0
    return {"calls": 1, "pattern": pattern._name, "spawn_results": list(_spawn_results), "native_ids": len(_spawn_ids)}


def match_spawn_ids():
    actors = [WeakPointer(actor) for actor in unrealsdk.find_all("InventoryPickup", False)
              if "Default__" not in str(actor)][:400]
    matches = []
    for token in _spawn_ids[:4]:
        size = int(token._type._get_struct_size())
        data = _read(int(token._get_address()), size)
        row = {"hex": data.hex(), "matches": []}
        matches.append(row)
        for reference in actors:
            actor = reference()
            if actor is None:
                continue
            allocation = int(actor.Class._get_struct_size())
            if not 0 < allocation <= 4096:
                continue
            memory = _read(int(actor._get_address()), allocation)
            offset = memory.find(data)
            if offset >= 0:
                row["matches"].append({"actor": str(actor), "offset": offset, "allocation": allocation})
    result = {"ids": matches, "actors_scanned": len(actors)}
    (Path(__file__).parent / "logs" / "loot_junk_spawn_matches.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def spawn_native_control():
    global _control_before
    from . import shinies
    from .dev_tools import _gameplay_pc
    pc = shinies._pc_for_party_index(1) or _gameplay_pc()
    world = shinies._get_world()
    store = shinies._get_pool_store()
    pose = shinies._get_player_pose(pc)
    transform = shinies._get_spawn_transform(pc)
    if world is None or store is None or pose is None or transform is None:
        raise RuntimeError("The normal native loot spawner is not ready")
    _control_before = {str(actor) for actor in unrealsdk.find_all("InventoryPickup", False)}
    location, rotation = shinies._spawn_pose(pose[0], pose[1], 0)
    shinies._spawn_pool(store, world, transform, 70,
                        "itempool_bor_sg_05_legendary_convergence_shiny", location, rotation)
    return {"spawn_call": True, "before_count": len(_control_before), "target": str(pc)}


def stage_native_control():
    global _native_control
    from . import loot_shapes
    candidates = [actor for actor in unrealsdk.find_all("InventoryPickup", False)
                  if str(actor) not in _control_before and "Default__" not in str(actor)]
    if len(candidates) != 1:
        return {"staged": False, "new_pickups": len(candidates)}
    actor = candidates[0]
    reference = WeakPointer(actor)
    if reference() is None or bool(actor.bReplicates):
        return {"staged": False, "reason": "control is expired or already actor-replicated"}
    from . import shinies
    from .inventory_capacity import get_party_player_states
    from .dev_tools import _gameplay_pc
    pc = _gameplay_pc()
    for _index, name, ps in get_party_player_states():
        if name == "Squ1ggs94":
            pc = ps.Owner
            break
    pose = shinies._get_player_pose(pc)
    if pose is None:
        return {"staged": False, "reason": "control viewer is not ready"}
    location, _ = shinies._spawn_pose(pose[0], pose[1], 0)
    rotation = actor.K2_GetActorRotation()
    target = unrealsdk.make_struct("Vector", X=float(location.X), Y=float(location.Y), Z=float(location.Z) + 60.0)
    zero = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=0.0)
    components = list(loot_shapes._physics_components(actor))
    _native_control = reference
    for comp in components:
        comp.SetSimulatePhysics(True)
        comp.SetEnableGravity(False)
    actor.K2_TeleportTo(target, rotation)
    for comp in components:
        comp.SetPhysicsLinearVelocity(zero, False, "")
        sleep = getattr(comp, "PutRigidBodyToSleep", None)
        if callable(sleep):
            sleep("")
    return {"staged": True, "actor": str(actor), "bReplicates": bool(actor.bReplicates), "height_above_spawn_pose_cm": 60}
