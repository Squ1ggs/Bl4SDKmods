"""Viewer-local cosmetic weapons for imported rigs; gameplay weapon stays intact."""
from typing import Any
from unrealsdk.unreal import WeakPointer


def diagnose() -> dict:
    """Read weapon renderer ownership and native pose-copy parameters."""
    import unrealsdk
    from unrealsdk.unreal import UFunction
    from .dev_tools import _gameplay_pc
    from . import engine as oak
    from . import imported_models
    pawn = getattr(_gameplay_pc(), "Pawn", None)
    functions = []
    for cls in unrealsdk.find_class("GbxSkeletalMeshComponent")._superfields():
        for function in cls._fields():
            if isinstance(function, UFunction) and str(function.Name) in ("SetLeaderPoseComponent", "K2_SetRelativeLocationAndRotation", "K2_SetRelativeTransform"):
                if any(row["function"] == str(function) for row in functions):
                    continue
                functions.append({"function": str(function), "params": [
                    {"name": str(prop.Name), "type": type(prop).__name__}
                    for prop in function._properties() if int(prop.PropertyFlags) & 0x80]})
    native = []
    if pawn is not None:
        for component in _native_weapon_meshes(pawn):
            native.append({"component": str(component), "owner": str(component.GetOwner()),
                           "mesh": str(oak._mesh_asset_for_kind(component)),
                           "scale": str(component.K2_GetComponentScale()),
                           "location": str(component.K2_GetComponentLocation()),
                           "visible": bool(component.bVisible), "hidden": bool(component.bHiddenInGame),
                           "only_owner_see": bool(component.bOnlyOwnerSee), "owner_no_see": bool(component.bOwnerNoSee)})
            native[-1]["actor_replicates"] = bool(component.GetOwner().bReplicates)
            native[-1]["component_replicates"] = bool(component.bReplicates)
            native[-1]["gestalt_parts"] = {}
            for name in ("GestaltPartList", "GestaltMeshParts", "ExternalGestaltMeshes", "GbxActorParts_Meshes"):
                value = getattr(component, name)
                if name == "GestaltPartList":
                    native[-1]["gestalt_parts"][name] = str(value)
                else:
                    native[-1]["gestalt_parts"][name] = [str(item)[:700] for item in list(value)[:24]]
            gestalt = component.GestaltData
            native[-1]["gestalt_data_schema"] = [
                {"name": str(prop.Name), "type": type(prop).__name__,
                 "struct": str(prop.Struct) if type(prop).__name__ == "ZStructProperty" else None}
                for prop in gestalt._type._properties()]
    return {"ok": True, "message": "Native weapon renderer and pose-copy schemas read.",
            "pose_functions": functions, "native_weapons": native,
            "gestalt_functions": [{"function": str(function), "params": [
                {"name": str(prop.Name), "type": type(prop).__name__,
                 "struct": str(prop.Struct) if type(prop).__name__ in ("ZStructProperty", "ZGbxDefPtrProperty") else None}
                for prop in function._properties() if int(prop.PropertyFlags) & 0x80]}
                for function in unrealsdk.find_class("GbxSkeletalMeshComponent")._fields()
                if isinstance(function, UFunction) and "gestalt" in str(function.Name).lower()],
            "gestalt_properties": [{"name": str(prop.Name), "type": type(prop).__name__,
                                    "struct": str(prop.Struct) if type(prop).__name__ == "ZStructProperty" else None}
                                   for prop in unrealsdk.find_class("GbxSkeletalMeshComponent")._properties()
                                   if "gestalt" in str(prop.Name).lower() or "actorparts" in str(prop.Name).lower()],
            "imported_actors": [{"actor": str(actor), "model_id": model_id,
                                 "bone": imported_models.models()[model_id].get("weapon_bone")}
                                for actor, model_id in imported_models.live_actors()]}


def _native_weapon_meshes(pawn: Any) -> list[Any]:
    import unrealsdk
    from .dev_tools import _appearance_skeletal_components
    mesh_class = unrealsdk.find_class("SkeletalMeshComponent")
    weapon_class = unrealsdk.find_class("OakWeapon")
    seen = set()
    found = []
    def visit(component,depth):
        if component is None or depth>4 or str(component) in seen:
            return
        seen.add(str(component))
        owner = component.GetOwner()
        if (owner is not None and owner.Class._inherits(weapon_class)
                and component.Class._inherits(mesh_class) and not component.bOnlyOwnerSee):
            found.append(component)
            return
        for child in list(getattr(component,"AttachChildren",()) or ()):
            visit(child,depth+1)
    for component in _appearance_skeletal_components(pawn):
        visit(component,0)
    return found


def clear(actor: Any, saved: dict) -> None:
    native = saved["native"]()
    if native is not None and saved.get("suppressed_native",False):
        native.SetVisibility(saved["visible"],False)
        native.SetHiddenInGame(saved["hidden"],False)
    cosmetic = saved["component"]()
    if cosmetic is not None:
        cosmetic.SetLeaderPoseComponent(None,True,False)
        cosmetic.K2_DestroyComponent(actor)


def _local_first_person(pawn: Any) -> bool:
    from .dev_tools import _gameplay_pc, _player_camera_manager, _actor_camera_mode
    import math
    pc = _gameplay_pc()
    if pc is None or str(getattr(pc, "Pawn", None)) != str(pawn):
        return False
    manager = _player_camera_manager(pc)
    if (_actor_camera_mode(manager, pawn) or "Default") != "Default":
        return False
    camera, origin = manager.GetCameraLocation(), pawn.K2_GetActorLocation()
    return math.hypot(float(camera.X) - float(origin.X), float(camera.Y) - float(origin.Y)) < 90


def prepare(actor: Any, row: dict, *, preview: bool = False) -> None:
    import unrealsdk
    from . import imported_models
    from . import engine as oak
    key = "cosmetic_weapon:" + str(actor)
    saved = imported_models._packages.get(key)
    pawn = actor.GetAttachParentActor()
    # A preview becomes worn when attached to a player. Its old preview flag
    # must not bypass the worn-model feature gate or leave two gun renderers.
    preview = pawn is None and (preview or bool(saved and saved.get("preview")))
    if pawn is None and preview:
        from .dev_tools import _gameplay_pc
        pawn = _gameplay_pc().Pawn
    body = oak._actor_mesh(actor)
    bone = row.get("weapon_bone")
    if pawn is None or not bone or (not preview and not row.get("weapon_preview_enabled",True)) or not body.DoesSocketExist(bone):
        if saved is not None:
            clear(actor,saved)
            imported_models._packages.pop(key,None)
        return
    candidates = _native_weapon_meshes(pawn)
    native = next((component for component in candidates if oak._mesh_asset_for_kind(component) is not None),None)
    if saved is not None and (saved["native"]() is None or str(saved["native"]()) != str(native)):
        clear(actor,saved)
        imported_models._packages.pop(key,None)
        saved = None
    if native is None:
        return
    if saved is None:
        transform = unrealsdk.make_struct("Transform")
        transform.Rotation.W = 1
        transform.Scale3D.X = transform.Scale3D.Y = transform.Scale3D.Z = 1
        component = oak._unwrap(actor.AddComponentByClass(unrealsdk.find_class("GbxSkeletalMeshComponent"),True,transform,False))
        if component is None:
            raise RuntimeError("Could not create cosmetic weapon component")
        try:
            component.SetSkeletalMeshAsset(oak._mesh_asset_for_kind(native))
            component.SetCollisionEnabled(0)
            # Both meshes use the exact same native weapon skeleton.
            component.SetLeaderPoseComponent(native,True,False)
            for index in range(int(native.GetNumMaterials())):
                component.SetMaterial(index,native.GetMaterial(index))
            if not component.K2_AttachToComponent(body,bone,2,2,2,False):
                raise RuntimeError("Cosmetic weapon could not attach to its source weapon bone")
            # FBX imported bone scale is 100; native weapon world scale is 1.
            # Compensate via the actual native scale rather than a guessed factor.
            component.SetWorldScale3D(native.K2_GetComponentScale())
            component.SetOnlyOwnerSee(False)
            component.SetVisibility(True,False)
            component.SetHiddenInGame(False,False)
            saved = {"native":WeakPointer(native),"component":WeakPointer(component),
                     "visible":bool(native.bVisible),"hidden":bool(native.bHiddenInGame),"bone":bone,
                     "preview":preview,"suppressed_native":False}
            imported_models._packages[key] = saved
        except Exception:
            component.K2_DestroyComponent(actor)
            raise
    component = saved["component"]()
    if component is None:
        imported_models._packages.pop(key,None)
        return
    offset = row.get("weapon_socket_offset_cm", (0.0, 0.0, 0.0))
    rotation = row.get("weapon_socket_rotation_degrees", {})
    adjustment = (tuple(float(value) for value in offset),
                  float(rotation.get("pitch", 0)), float(rotation.get("yaw", 0)), float(rotation.get("roll", 0)))
    if saved.get("socket_adjustment") != adjustment:
        socket_scale = body.GetSocketTransform(bone, 0).Scale3D
        scales = [float(getattr(socket_scale, axis)) for axis in ("X", "Y", "Z")]
        if any(abs(value) < 0.0001 for value in scales):
            raise RuntimeError("Imported weapon bone has an invalid scale")
        # UE3 sockets store centimetres. The imported FBX bone carries scale100,
        # so divide translation by the measured parent scale, just like size.
        component.K2_SetRelativeLocationAndRotation(
            NewLocation=unrealsdk.make_struct("Vector", **dict(zip(("X", "Y", "Z"),
                (adjustment[0][index] / scales[index] for index in range(3))))),
            NewRotation=unrealsdk.make_struct("Rotator", Pitch=adjustment[1], Yaw=adjustment[2], Roll=adjustment[3]),
            bSweep=False, SweepHitResult=unrealsdk.make_struct("HitResult"), bTeleport=True)
        component.SetWorldScale3D(native.K2_GetComponentScale())
        saved["socket_adjustment"] = adjustment
    component.SetOwnerNoSee(bool(body.bOwnerNoSee))
    # BL4 can share a renderer between first and third person; OnlyOwnerSee
    # alone does not identify a dedicated world weapon. Restore that renderer
    # in the owner's first-person view, where HiddenActors masks the cosmetic.
    if not preview:
        suppress = not _local_first_person(pawn)
        if saved.get("suppressed_native", False) != suppress:
            native.SetVisibility(False if suppress else saved["visible"], False)
            native.SetHiddenInGame(True if suppress else saved["hidden"], False)
            saved["suppressed_native"] = suppress
