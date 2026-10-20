"""Viewer-local animated attachments owned by their cosmetic body component."""
from unrealsdk.unreal import WeakPointer


def clear(actor_key):
    from . import imported_models
    saved = imported_models._packages.pop('cosmetic_effect:' + actor_key, None)
    component = saved['component']() if saved else None
    if component is not None:
        component.K2_DestroyComponent(None)


def prepare(actor, row):
    from . import imported_models, imported_materials
    from . import engine as oak
    import unrealsdk
    effect_id = row.get('cosmetic_effect')
    if not effect_id:
        return
    effect = imported_models.models().get(effect_id)
    if effect is None or not effect.get('effect_only') or not imported_models.pack_ready(effect):
        raise RuntimeError('Matching cosmetic effect pack is missing or changed')
    body = oak._actor_mesh(actor)
    bone = row.get('cosmetic_effect_bone')
    if body is None or not bone or int(body.GetBoneIndex(bone)) < 0:
        raise RuntimeError('Cosmetic effect attachment bone is unavailable')
    key = 'cosmetic_effect:' + str(actor)
    saved = imported_models._packages.get(key)
    component = saved['component']() if saved else None
    if component is None:
        cls = unrealsdk.find_class('SkeletalMeshComponent')
        transform = unrealsdk.make_struct('Transform')
        transform.Rotation.W = 1
        transform.Scale3D.X = transform.Scale3D.Y = transform.Scale3D.Z = 1
        component = oak._unwrap(actor.AddComponentByClass(cls, True, transform, False))
        if component is None:
            raise RuntimeError('Cosmetic effect mesh could not be created')
        try:
            mesh = imported_models._load('SkeletalMesh', effect['mesh'])
            animation = imported_models._load('AnimSequence', effect['animations']['idle'])
            if mesh is None or animation is None or str(mesh.Skeleton) != str(animation.Skeleton):
                raise RuntimeError('Cosmetic effect animation does not match its mesh')
            oak._set_skeletal_mesh_asset(component, mesh)
            component.SetCollisionEnabled(0)
            component.SetIsReplicated(False)
            if not component.K2_AttachToComponent(body, bone, 2, 2, 2, False):
                raise RuntimeError('Cosmetic effect could not attach to the head')
            imported_materials._prepare_recipe_actor(actor, effect_id, component=component)
            component.VisibilityBasedAnimTickOption = 0
            component.bPauseAnims = False
            component.bNoSkeletonUpdate = False
            component.SetComponentTickEnabled(True)
            component.SetCastShadow(False)
            component.SetCastHiddenShadow(False)
            component.SetVisibility(True, False)
            component.SetHiddenInGame(False, False)
            component.PlayAnimation(animation, True)
            saved = {'component': WeakPointer(component), 'body': WeakPointer(body), 'animation': animation, 'mesh': mesh}
            imported_models._packages[key] = saved
        except Exception:
            component.K2_DestroyComponent(actor)
            raise
    # Socket scales include the source FBX's centimetre conversion. Keep the
    # authored effect's world scale and body orientation instead of magnifying it.
    if saved['body']() is None or str(saved['body']()) != str(body):
        clear(str(actor))
        return
    component.SetWorldScale3D(unrealsdk.make_struct('Vector', X=1, Y=1, Z=1))
    component.K2_SetWorldRotation(body.K2_GetComponentRotation(), False, unrealsdk.make_struct('HitResult'), True)
    location = body.GetSocketLocation(bone)
    offset = row.get('cosmetic_effect_height_cm', 0)
    position = unrealsdk.make_struct('Vector', X=float(location.X), Y=float(location.Y), Z=float(location.Z) + float(offset))
    component.K2_SetWorldLocation(position, False, unrealsdk.make_struct('HitResult'), True)
    if not component.IsPlaying():
        component.PlayAnimation(saved['animation'], True)
