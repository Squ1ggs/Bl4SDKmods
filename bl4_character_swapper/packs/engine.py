"""Appearance-only spawn facade; shares the native controller's world and pawn."""
from ..native_helpers import _unwrap, _actor_mesh, _mesh_asset_for_kind, _spawn_actor_deferred

_SPAWNED = []


def _spawn_context():
    import unrealsdk
    from .dev_tools import _controller
    ctrl = _controller()
    pc = ctrl._pc()
    return pc, getattr(pc, 'Pawn', None), ctrl._world(), unrealsdk.find_class('GameplayStatics').ClassDefaultObject


def _spawn_transform(pawn, *, distance, z_offset, scale):
    import unrealsdk
    location, forward = pawn.K2_GetActorLocation(), pawn.GetActorForwardVector()
    transform = unrealsdk.make_struct('Transform')
    transform.Rotation.W = 1.0
    transform.Translation.X = float(location.X) + float(forward.X) * distance
    transform.Translation.Y = float(location.Y) + float(forward.Y) * distance
    transform.Translation.Z = float(location.Z) + z_offset
    transform.Scale3D.X = transform.Scale3D.Y = transform.Scale3D.Z = scale
    return transform


def _actor_key(actor):
    return str(actor)


def _class_name(actor):
    return str(actor.Class.Name)


def _object_path_name(obj):
    getter = getattr(obj, 'GetPathName', None)
    if callable(getter):
        return str(getter())
    for attr in ('PathName', 'ObjectPath'):
        value = getattr(obj, attr, None)
        if value:
            return str(value)
    text = str(obj or '')
    return text.split("'", 2)[1] if "'" in text else text
