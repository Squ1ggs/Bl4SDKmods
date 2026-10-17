"""Native attached-loot prototype: replicate a holder, keep pickup with JunkSystem."""
from __future__ import annotations

import unrealsdk
from unrealsdk.unreal import FGameDataHandle, WeakPointer

_holders: dict[str, dict] = {}
_control_attempted = False


def inspect_container_templates() -> dict:
    """Read live container definitions and real mesh sockets, without changing them."""
    from .inventory_capacity import get_party_player_states
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1 or matches[0].Owner.Pawn is None:
        return {"available": False, "reason": "Xbox pawn is unavailable"}
    pawn = matches[0].Owner.Pawn
    loc = pawn.K2_GetActorLocation()
    rows = []
    for actor in unrealsdk.find_all("LootableObject", False):
        if "Default__" in str(actor) or actor.RootComponent is None:
            continue
        definition = actor.GbxActorData.GbxActorDef
        if definition is None or not int(definition._get_address()):
            continue
        mesh = actor.MeshComponent
        if mesh is None:
            continue
        pos = actor.K2_GetActorLocation()
        distance = sum((float(getattr(pos, axis)) - float(getattr(loc, axis))) ** 2
                       for axis in ("X", "Y", "Z")) ** .5
        sockets = [str(value) for value in mesh.GetAllSocketNames()]
        definition_fields = []
        for prop in definition._type._properties():
            name = str(prop.Name)
            if any(word in name.lower() for word in ("loot", "socket", "attach")):
                value = getattr(definition, name)
                definition_fields.append({"name": name, "type": type(prop).__name__, "value": str(value)[:300]})
        rows.append({"actor": str(actor), "definition": str(definition._name),
                     "distance_cm": round(distance), "sockets": sockets[:40],
                     "mesh": str(mesh.SkeletalMesh), "authority": bool(actor.HasAuthority()),
                     "definition_type": str(definition._type), "definition_fields": definition_fields,
                     "native_attached": len(unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject.GetJunkAttachedToActor(Actor=actor, OutJunkIds=[])[1])})
    rows.sort(key=lambda row: row["distance_cm"])
    return {"available": True, "containers": rows[:6],
            "white_chests": [row for row in rows if "whitechest" in row["definition"].lower()][:3],
            "holder_mesh_functions": [{"function": str(function),
                                        "params": [str(prop.Name) for prop in function._properties() if int(prop.PropertyFlags) & 0x80]}
                                       for cls in unrealsdk.find_class("GbxSkeletalMeshComponent")._superfields()
                                       for function in cls._fields()
                                       if isinstance(function, unrealsdk.unreal.UFunction)
                                       and str(function.Name) in ("SetSkeletalMesh", "SetSkeletalMeshAsset", "SetVisibility", "DoesSocketExist", "GetSocketLocation")],
            "lootable_functions": [{"function": str(function),
                                     "params": [str(prop.Name) for prop in function._properties() if int(prop.PropertyFlags) & 0x80]}
                                    for function in unrealsdk.find_class("LootableObject")._fields()
                                    if isinstance(function, unrealsdk.unreal.UFunction)
                                    and "/Script/OakGame.LootableObject:" in str(function)]}


def inspect_spawn_initialization() -> dict:
    """Read the native GBX actor initialization APIs and their parameter schemas."""
    from unrealsdk.unreal import UFunction
    functions = []
    for function in unrealsdk.find_all("Function", False):
        path = str(function)
        if not any(script in path for script in ("/Script/Gbx", "/Script/OakGame.")):
            continue
        name = str(function.Name).lower()
        if not ("actor" in name and any(term in name for term in ("spawn", "init", "definition", "apply"))):
            continue
        functions.append({"function": path, "params": [
            {"name": str(prop.Name), "type": type(prop).__name__,
             "struct": str(prop.Struct) if type(prop).__name__ in ("ZStructProperty", "ZGbxDefPtrProperty") else None,
             "type_handle": int(prop.TypeHandle) if type(prop).__name__ == "ZGameDataHandleProperty" else None}
            for prop in function._properties() if int(prop.PropertyFlags) & 0x80]})
        if len(functions) >= 64:
            break
    return {"functions": functions,
            "native_loot_apis": [
                {"function": str(function), "params": [
                    {"name": str(prop.Name), "type": type(prop).__name__,
                     "struct": str(prop.Struct) if type(prop).__name__ in ("ZStructProperty", "ZGbxDefPtrProperty") else None,
                     "members": [{"name": str(member.Name), "type": type(member).__name__,
                                  "struct": str(member.Struct) if type(member).__name__ in ("ZStructProperty", "ZGbxDefPtrProperty") else None}
                                 for member in prop.Struct._properties()]
                                 if type(prop).__name__ in ("ZStructProperty", "ZGbxDefPtrProperty") else None}
                    for prop in function._properties() if int(prop.PropertyFlags) & 0x80]}
                for cls in (unrealsdk.find_class("LootFunctionLibrary"), unrealsdk.find_class("InventoryItemBlueprintLibrary"))
                for function in cls._fields()
                if isinstance(function, UFunction) and any(word in str(function.Name).lower() for word in ("spawn", "serial", "loot", "drop"))],
            "loot_config_type": str(unrealsdk.find_class("LootableObject").ClassDefaultObject.SetLootConfigOverride.func._find_prop("ConfigOverride").Struct),
            "render_replication": [{"class": str(cls), "properties": [
                {"name": str(prop.Name), "type": type(prop).__name__, "net": bool(int(prop.PropertyFlags) & 0x20),
                 "struct": str(prop.Struct) if type(prop).__name__ in ("ZStructProperty", "ZGbxDefPtrProperty") else None}
                for prop in cls._properties() if any(term in str(prop.Name).lower() for term in ("visible", "visibility", "hidden", "material", "body", "skeletalmesh", "replicate"))]}
                for cls in (unrealsdk.find_class("LootableObject"), unrealsdk.find_class("GbxSkeletalMeshComponent"))],
            "invisible_mesh_candidates": [str(mesh) for mesh in unrealsdk.find_all("SkeletalMesh", False)
                                          if any(term in str(mesh).lower() for term in ("invisible", "dummy", "empty", "proxy", "null", "placeholder"))][:24],
            "skip_definition_default": bool(unrealsdk.find_class("LootableObject").ClassDefaultObject.GbxActorData.bSkipActorDefApplicationDuringCook)}


def spawn_holder(context, location, rotation, pool_name: str, *, existing=None, template=None, socket_name="", loot_config_name=None, attach_now=True, hidden=False) -> dict:
    """Create one empty replicated actor and attach one native pool result to it."""
    if context is None or not context.HasAuthority():
        raise RuntimeError("Native loot holders require a live host context")
    statics = unrealsdk.find_class("GameplayStatics").ClassDefaultObject
    transform = context.GetTransform()
    transform.Translation = location
    transform.Scale3D = unrealsdk.make_struct("Vector", X=1.0, Y=1.0, Z=1.0)
    scale = unrealsdk.find_enum("ESpawnActorScaleMethod").OverrideRootScale
    collision = unrealsdk.find_enum("ESpawnActorCollisionHandlingMethod").AlwaysSpawn
    holder_class = unrealsdk.find_class("LootableObject")
    if not holder_class._implements(unrealsdk.find_class("JunkAttachParent")):
        raise RuntimeError("The holder class cannot own native attached loot")
    actor = existing
    if actor is None:
        raw = statics.BeginDeferredActorSpawnFromClass(
            WorldContextObject=context, ActorClass=holder_class,
            SpawnTransform=transform, CollisionHandlingOverride=collision,
            owner=None, TransformScaleMethod=scale)
        # Const-reference transforms are also SDK output parameters. The actor
        # is the first tuple element; the transform is an additional output.
        actor = raw[0] if isinstance(raw, tuple) else raw
    if actor is None:
        raise RuntimeError("Native loot holder did not spawn")
    reference = WeakPointer(actor)
    loot_created = False
    phase = "finish_spawn"
    try:
        if template is not None:
            phase = "copy_native_definition"
            # Copy only the typed actor definition; never share a live script
            # instance or a container's existing native junk IDs.
            actor.GbxActorData.GbxActorDef = template.GbxActorData.GbxActorDef
            actor.GameStage = 70
            if loot_config_name:
                from unrealsdk.unreal import FGbxDefPtr
                actor.MeshComponent.SetSkeletalMeshAsset(NewMesh=template.MeshComponent.SkeletalMesh)
                setter = actor.SetLootConfigOverride
                config_type = setter.func._find_prop("ConfigOverride").Struct
                setter(ConfigOverride=FGbxDefPtr(loot_config_name, config_type))
        phase = "finish_spawn"
        raw = statics.FinishSpawningActor(Actor=actor, SpawnTransform=transform,
                                        TransformScaleMethod=scale)
        actor = raw[0] if isinstance(raw, tuple) else raw
        if actor is None or reference() is None:
            raise RuntimeError("Native loot holder did not finish spawning")
        identity = unrealsdk.make_struct(
            "Transform", Translation=unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=0.0),
            Rotation=unrealsdk.make_struct("Quat", X=0.0, Y=0.0, Z=0.0, W=1.0),
            Scale3D=unrealsdk.make_struct("Vector", X=1.0, Y=1.0, Z=1.0))
        phase = "scene_root"
        component = actor.RootComponent
        if component is None:
            raw = actor.AddComponentByClass(
                Class=unrealsdk.find_class("SceneComponent"), bManualAttachment=False,
                RelativeTransform=identity, bDeferredFinish=False)
            component = raw[0] if isinstance(raw, tuple) else raw
        if component is None or actor.RootComponent is None:
            raise RuntimeError("Native loot holder has no scene root")
        if template is not None and socket_name and not actor.MeshComponent.DoesSocketExist(socket_name):
            phase = "configure_socket_mesh"
            # Cooked map containers have their body mesh baked into the actor.
            # The typed definition alone does not rebuild that mesh on a clone.
            actor.MeshComponent.SetSkeletalMeshAsset(NewMesh=template.MeshComponent.SkeletalMesh)
        if socket_name and not actor.MeshComponent.DoesSocketExist(socket_name):
            raise RuntimeError("The configured holder did not initialize its loot socket")
        component.SetIsReplicated(True)
        phase = "publish_holder"
        actor.SetActorEnableCollision(False)
        if not actor.K2_TeleportTo(location, rotation):
            raise RuntimeError("Native loot holder could not reach its slot")
        actor.bAlwaysRelevant = True
        actor.bOnlyRelevantToOwner = False
        actor.NetUpdateFrequency = 2.0
        actor.MinNetUpdateFrequency = 2.0
        actor.SetReplicateMovement(True)
        actor.SetReplicates(True)
        actor.SetNetDormancy(unrealsdk.find_enum("ENetDormancy").DORM_Awake)
        if hidden:
            actor.SetActorHiddenInGame(True)
        actor.ForceNetUpdate()
        phase = "attach_native_loot"
        # Native LootableObject starts at GameStage 1; use the same stage as the
        # established NCS controls so inventory part requirements can be met.
        actor.GameStage = 70
        library = unrealsdk.find_class("ItemPoolFunctionLibrary").ClassDefaultObject
        bound = library.SpawnItemsFromItemPool_Attach
        pool_type = int(bound.func._find_prop("itempool").TypeHandle)
        result = bound(SourceActor=actor, itempool=FGameDataHandle(pool_type, pool_name),
                       SocketName=socket_name, OutJunkIds=[]) if attach_now else None
        count = len(result[1]) if result is not None else 0
        if attach_now and count == 0:
            raise RuntimeError("The native pool returned no attached loot")
        loot_created = bool(count)
        key = str(actor)
        _holders[key] = {"reference": reference, "pool": pool_name, "initial_items": count,
                         "socket": socket_name, "pending_attachment": not attach_now,
                         "hidden": hidden}
        attached = unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject.GetJunkAttachedToActor(Actor=actor, OutJunkIds=[])
        return {"holder": key, "native_items": count, "pool": pool_name,
                "attached_now": len(attached[1]), "socket": socket_name,
                "definition": str(actor.GbxActorData.GbxActorDef._name),
                "position": {axis: float(getattr(actor.K2_GetActorLocation(), axis))
                             for axis in ("X", "Y", "Z")}}
    except Exception as exc:
        globals()["_last_spawn_holder_error"] = {"phase": phase, "error": repr(exc), "actor": str(actor)}
        # Do not remove a holder after native loot was successfully attached.
        if not loot_created:
            live = reference()
            if live is not None:
                live.K2_DestroyActor()
        raise


def prepare_shape_control(*, bare=False, mesh_only=False) -> dict:
    """Prepare three hidden native parents; attach loot on a later game-thread call."""
    from .inventory_capacity import get_party_player_states
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1 or matches[0].Owner.Pawn is None:
        raise RuntimeError("Xbox pawn is unavailable")
    pawn = matches[0].Owner.Pawn
    guard = ("_bare_shape_control_prepared" if bare else
             "_mesh_shape_control_prepared" if mesh_only else "_shape_control_prepared")
    if globals().get(guard, False):
        return {"prepared": False, "reason": "small shape already prepared", "holders": inspect_holders()}
    templates = [actor for actor in unrealsdk.find_all("LootableObject", False)
                 if "Default__" not in str(actor) and actor.RootComponent is not None
                 and str(actor.GbxActorData.GbxActorDef._name) == "lootable_ammochest"
                 and actor.HasAuthority() and actor.MeshComponent.DoesSocketExist("Middle")]
    if not templates and not bare:
        raise RuntimeError("The native holder template is not loaded")
    template = templates[0] if not bare else None
    loc = pawn.K2_GetActorLocation()
    forward = pawn.GetActorForwardVector()
    right = pawn.GetActorRightVector()
    globals()[guard] = True
    rows = []
    for horizontal, height in ((-70.0, 0.0), (70.0, 0.0), (0.0, 120.0)):
        target = unrealsdk.make_struct("Vector",
            X=float(loc.X) + float(forward.X) * 220.0 + float(right.X) * horizontal,
            Y=float(loc.Y) + float(forward.Y) * 220.0 + float(right.Y) * horizontal,
            Z=float(loc.Z) + height)
        control = spawn_holder(pawn, target, pawn.K2_GetActorRotation(), "itempool_ar_01_common",
                               template=template, socket_name="" if bare else "Middle",
                               loot_config_name=None if bare else "none",
                               attach_now=False, hidden=not bare and not mesh_only)
        if mesh_only:
            actor = _holders[control["holder"]]["reference"]()
            # This build's SceneComponent.bVisible is replicated. Hiding the
            # mesh alone leaves the native parent actor visible to JunkSystem.
            actor.MeshComponent.SetIsReplicated(True)
            actor.MeshComponent.SetVisibility(bNewVisibility=False, bPropagateToChildren=False)
            actor.ForceNetUpdate()
        _holders[control["holder"]]["shape_control"] = True
        rows.append(control)
    return {"prepared": True, "points": rows}


def prepare_bare_shape_control() -> dict:
    return prepare_shape_control(bare=True)


def prepare_mesh_shape_control() -> dict:
    return prepare_shape_control(mesh_only=True)


def remove_shape_controls() -> dict:
    removed = []
    for key, saved in list(_holders.items()):
        if not saved.get("shape_control"):
            continue
        actor = saved["reference"]()
        if actor is not None:
            actor.K2_DestroyActor()
            removed.append(key)
        _holders.pop(key, None)
    return {"removed": removed}


def attach_shape_control() -> dict:
    """Attach one native rifle per initialized hidden triangle point, at most once."""
    rows = []
    bound = unrealsdk.find_class("ItemPoolFunctionLibrary").ClassDefaultObject.SpawnItemsFromItemPool_Attach
    pool_type = int(bound.func._find_prop("itempool").TypeHandle)
    library = unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject
    for key, saved in _holders.items():
        if not saved.get("shape_control") or not saved.get("pending_attachment"):
            continue
        actor = saved["reference"]()
        if actor is None:
            continue
        saved["pending_attachment"] = False
        response = bound(SourceActor=actor, itempool=FGameDataHandle(pool_type, saved["pool"]),
                         SocketName=saved["socket"], OutJunkIds=[])
        saved["native_outputs"] = response
        saved["initial_items"] = len(response[1])
        rows.append({"holder": key, "native_items": len(response[1]),
                     "native_attached": len(library.GetJunkAttachedToActor(Actor=actor, OutJunkIds=[])[1]),
                     "hidden": bool(actor.bHidden)})
    return {"attached_points": rows, "count": len(rows)}


def remove_box_controls() -> dict:
    """Remove only this prototype's visible test parents, preserving shape controls."""
    removed = []
    for key, saved in list(_holders.items()):
        if saved.get("shape_control"):
            continue
        actor = saved["reference"]()
        if actor is not None:
            actor.K2_DestroyActor()
            removed.append(key)
        _holders.pop(key, None)
    return {"removed": removed}


def spawn_configured_control() -> dict:
    """One supported native body/socket control, with no default container loot."""
    from .inventory_capacity import get_party_player_states
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1 or matches[0].Owner.Pawn is None:
        raise RuntimeError("Xbox pawn is unavailable")
    pawn = matches[0].Owner.Pawn
    world_key = str(pawn.Outer)
    if globals().get("_configured_control_world") == world_key:
        failure = globals().get("_last_spawn_holder_error", {})
        if (globals().get("_configured_mesh_retry", False) or _holders
                or failure.get("phase") != "scene_root"
                or "did not initialize its loot socket" not in failure.get("error", "")):
            return {"spawned": False, "reason": "configured control already attempted", "holders": inspect_holders()}
        # The identified first attempt was destroyed before any loot call.
        globals()["_configured_mesh_retry"] = True
    templates = [actor for actor in unrealsdk.find_all("LootableObject", False)
                 if "Default__" not in str(actor) and actor.RootComponent is not None
                 and str(actor.GbxActorData.GbxActorDef._name) == "Lootable_Toolbox_NoLoot"
                 and actor.HasAuthority() and actor.MeshComponent.DoesSocketExist("Middle")]
    if not templates:
        raise RuntimeError("The verified no-loot toolbox template is not loaded")
    loc = pawn.K2_GetActorLocation()
    forward = pawn.GetActorForwardVector()
    target = unrealsdk.make_struct("Vector", X=float(loc.X) + float(forward.X) * 180.0,
                                  Y=float(loc.Y) + float(forward.Y) * 180.0, Z=float(loc.Z) + 30.0)
    globals()["_configured_control_world"] = world_key
    control = spawn_holder(pawn, target, pawn.K2_GetActorRotation(), "itempool_ar_01_common",
                           template=templates[0], socket_name="Middle")
    return {"spawned": True, **control}


def spawn_loot_config_control() -> dict:
    """One native attachment control with an explicit supported loot configuration."""
    from .inventory_capacity import get_party_player_states
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1 or matches[0].Owner.Pawn is None:
        raise RuntimeError("Xbox pawn is unavailable")
    pawn = matches[0].Owner.Pawn
    world_key = str(pawn.Outer)
    if globals().get("_loot_config_control_world") == world_key:
        return {"spawned": False, "reason": "loot config control already attempted", "holders": inspect_holders()}
    templates = [actor for actor in unrealsdk.find_all("LootableObject", False)
                 if "Default__" not in str(actor) and actor.RootComponent is not None
                 and str(actor.GbxActorData.GbxActorDef._name) == "lootable_ammochest"
                 and actor.HasAuthority() and actor.MeshComponent.DoesSocketExist("Middle")]
    if not templates:
        raise RuntimeError("The verified ammo chest template is not loaded")
    loc = pawn.K2_GetActorLocation()
    forward = pawn.GetActorForwardVector()
    target = unrealsdk.make_struct("Vector", X=float(loc.X) + float(forward.X) * 180.0,
                                  Y=float(loc.Y) + float(forward.Y) * 180.0, Z=float(loc.Z) + 30.0)
    globals()["_loot_config_control_world"] = world_key
    control = spawn_holder(pawn, target, pawn.K2_GetActorRotation(), "itempool_ar_01_common",
                           template=templates[0], socket_name="Middle", loot_config_name="Loot_OneSmallItem")
    return {"spawned": True, **control}


def inspect_holders(*, clean_collected: bool = False) -> list[dict]:
    library = unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject
    result = []
    for key, saved in list(_holders.items()):
        actor = saved["reference"]()
        if actor is None:
            _holders.pop(key, None)
            continue
        response = library.GetJunkAttachedToActor(Actor=actor, OutJunkIds=[])
        count = len(response[1])
        loc = actor.K2_GetActorLocation()
        row = {"holder": key, "pool": saved["pool"], "remaining_items": count,
               "bReplicates": bool(actor.bReplicates), "dormancy": int(actor.NetDormancy),
               "position": {axis: float(getattr(loc, axis)) for axis in ("X", "Y", "Z")}}
        if clean_collected and count == 0 and not saved.get("pending_attachment"):
            actor.K2_DestroyActor()
            _holders.pop(key, None)
            row["cleaned"] = True
        result.append(row)
    return result


def attach_initialized_control() -> dict:
    """Attach one rifle to the existing, opened native chest after initialization."""
    if globals().get("_initialized_attach_attempted", False):
        return {"spawned": False, "reason": "initialized attachment already attempted", "holders": inspect_holders()}
    library = unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject
    for key, saved in _holders.items():
        actor = saved["reference"]()
        if actor is None or str(actor.GbxActorData.GbxActorDef._name) != "lootable_ammochest":
            continue
        before = len(library.GetJunkAttachedToActor(Actor=actor, OutJunkIds=[])[1])
        if before > 1:
            return {"spawned": False, "reason": "the control already contains multiple native entries", "attached_before": before}
        if not actor.MeshComponent.DoesSocketExist("Middle"):
            raise RuntimeError("The initialized chest no longer has its loot socket")
        bound = unrealsdk.find_class("ItemPoolFunctionLibrary").ClassDefaultObject.SpawnItemsFromItemPool_Attach
        pool_type = int(bound.func._find_prop("itempool").TypeHandle)
        globals()["_initialized_attach_attempted"] = True
        response = bound(SourceActor=actor, itempool=FGameDataHandle(pool_type, "itempool_ar_01_common"),
                         SocketName="Middle", OutJunkIds=[])
        # Keep native output storage, not reflected copies of opaque JunkIds.
        globals()["_initialized_attach_outputs"] = response
        return {"spawned": bool(len(response[1])), "holder": key,
                "native_items": len(response[1]), "attached_before": before,
                "attached_after": len(library.GetJunkAttachedToActor(Actor=actor, OutJunkIds=[])[1])}
    raise RuntimeError("The initialized control chest is no longer available")


def spawn_control() -> dict:
    global _control_attempted
    if _control_attempted:
        return {"spawned": False, "reason": "control already attempted", "holders": inspect_holders()}
    from .inventory_capacity import get_party_player_states
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1:
        raise RuntimeError("Xbox player is not uniquely present")
    pawn = matches[0].Owner.Pawn
    if pawn is None:
        raise RuntimeError("Xbox pawn is unavailable")
    loc = pawn.K2_GetActorLocation()
    forward = pawn.GetActorForwardVector()
    target = unrealsdk.make_struct("Vector", X=float(loc.X) + float(forward.X) * 150.0,
                                  Y=float(loc.Y) + float(forward.Y) * 150.0, Z=float(loc.Z))
    _control_attempted = True
    control = spawn_holder(pawn, target, pawn.K2_GetActorRotation(), "itempool_ar_05_legendary")
    return {"spawned": True, **control}


def recover_control(expected_name: str) -> dict:
    """Finish the identified deferred control instead of duplicating its spawn."""
    if globals().get("_recovery_attempted", False) or _holders:
        return {"recovered": False, "reason": "control already recovered or active"}
    from .inventory_capacity import get_party_player_states
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    candidates = [actor for actor in unrealsdk.find_all("Actor", True)
                  if str(actor.Name) == expected_name and "Default__" not in str(actor)]
    if len(matches) != 1 or len(candidates) != 1:
        return {"recovered": False, "reason": "control identity is unavailable"}
    pawn = matches[0].Owner.Pawn
    actor = candidates[0]
    if pawn is None or str(actor.Outer) != str(pawn.Outer) or actor.RootComponent is not None or bool(actor.bReplicates):
        return {"recovered": False, "reason": "control no longer matches its deferred state"}
    library = unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject
    if len(library.GetJunkAttachedToActor(Actor=actor, OutJunkIds=[])[1]):
        return {"recovered": False, "reason": "control already owns loot"}
    loc = pawn.K2_GetActorLocation()
    forward = pawn.GetActorForwardVector()
    target = unrealsdk.make_struct("Vector", X=float(loc.X) + float(forward.X) * 150.0,
                                  Y=float(loc.Y) + float(forward.Y) * 150.0, Z=float(loc.Z))
    globals()["_recovery_attempted"] = True
    control = spawn_holder(pawn, target, pawn.K2_GetActorRotation(), "itempool_ar_05_legendary", existing=actor)
    return {"recovered": True, **control}


def spawn_lootable_control() -> dict:
    """One separate control with the required native parent interface."""
    if globals().get("_lootable_control_attempted", False) or _holders:
        return {"spawned": False, "reason": "native lootable control already attempted", "holders": inspect_holders()}
    from .inventory_capacity import get_party_player_states
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1:
        raise RuntimeError("Xbox player is not uniquely present")
    pawn = matches[0].Owner.Pawn
    loc = pawn.K2_GetActorLocation()
    forward = pawn.GetActorForwardVector()
    target = unrealsdk.make_struct("Vector", X=float(loc.X) + float(forward.X) * 150.0,
                                  Y=float(loc.Y) + float(forward.Y) * 150.0, Z=float(loc.Z))
    globals()["_lootable_control_attempted"] = True
    control = spawn_holder(pawn, target, pawn.K2_GetActorRotation(), "itempool_ar_05_legendary")
    return {"spawned": True, **control}


def spawn_staged_control() -> dict:
    if globals().get("_staged_control_attempted", False) or _holders:
        return {"spawned": False, "reason": "staged control already attempted", "holders": inspect_holders()}
    from .inventory_capacity import get_party_player_states
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1:
        raise RuntimeError("Xbox player is not uniquely present")
    pawn = matches[0].Owner.Pawn
    loc = pawn.K2_GetActorLocation()
    forward = pawn.GetActorForwardVector()
    target = unrealsdk.make_struct("Vector", X=float(loc.X) + float(forward.X) * 150.0,
                                  Y=float(loc.Y) + float(forward.Y) * 150.0, Z=float(loc.Z))
    globals()["_staged_control_attempted"] = True
    control = spawn_holder(pawn, target, pawn.K2_GetActorRotation(), "itempool_ar_01_common")
    return {"spawned": True, **control}


def place_control_again() -> dict:
    """Explicitly requested replacement at Xbox's current position, reuse empty holder."""
    from .inventory_capacity import get_party_player_states
    matches = [ps for _index, name, ps in get_party_player_states() if name == "Squ1ggs94"]
    if len(matches) != 1:
        raise RuntimeError("Xbox player is not uniquely present")
    pawn = matches[0].Owner.Pawn
    loc = pawn.K2_GetActorLocation()
    forward = pawn.GetActorForwardVector()
    target = unrealsdk.make_struct("Vector", X=float(loc.X) + float(forward.X) * 150.0,
                                  Y=float(loc.Y) + float(forward.Y) * 150.0, Z=float(loc.Z))
    library = unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject
    for saved in _holders.values():
        actor = saved["reference"]()
        if actor is None:
            continue
        if len(library.GetJunkAttachedToActor(Actor=actor, OutJunkIds=[])[1]):
            return {"spawned": False, "reason": "control holder still contains loot"}
        if not actor.K2_TeleportTo(target, pawn.K2_GetActorRotation()):
            raise RuntimeError("Control holder could not reach Xbox")
        actor.ForceNetUpdate()
        bound = unrealsdk.find_class("ItemPoolFunctionLibrary").ClassDefaultObject.SpawnItemsFromItemPool_Attach
        pool_type = int(bound.func._find_prop("itempool").TypeHandle)
        result = bound(SourceActor=actor, itempool=FGameDataHandle(pool_type, saved["pool"]),
                       SocketName="", OutJunkIds=[])
        return {"spawned": bool(len(result[1])), "native_items": len(result[1]),
                "attached_now": len(library.GetJunkAttachedToActor(Actor=actor, OutJunkIds=[])[1]),
                "holder": str(actor), "game_stage": int(actor.GameStage),
                "position": {axis: float(getattr(target, axis)) for axis in ("X", "Y", "Z")}}
    # A map transition expires old actors. This branch is invoked only for the
    # explicitly requested replacement and creates at most one per new level.
    world_key = str(pawn.Outer)
    if globals().get("_replacement_world") == world_key:
        return {"spawned": False, "reason": "replacement already placed in this level"}
    globals()["_replacement_world"] = world_key
    control = spawn_holder(pawn, target, pawn.K2_GetActorRotation(), "itempool_ar_01_common")
    return {"spawned": True, **control}
