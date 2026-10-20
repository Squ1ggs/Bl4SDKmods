"""Small compatibility facade for the existing imported-model implementation."""
from ..attachment import _call_quiet, _component_visible, _appearance_skeletal_components
from .. import native_helpers as native


def _controller():
    from ..runtime import CONTROLLER
    return CONTROLLER


def _gameplay_pc():
    return _controller()._pc()


class _WearStates:
    def values(self):
        return [{'shell': state.source(), 'pawn': state.pawn(), 'extras': []}
                for state in list(_controller().worn.values())]


_appearance_states = _WearStates()


def _appearance_mesh_ready(actor, mesh):
    if actor is None or mesh is None or bool(getattr(actor, 'bHidden', False)):
        return False
    visible, hidden = _component_visible(mesh)
    if not visible or hidden or native._mesh_asset_for_kind(mesh) is None:
        return False
    try:
        return int(mesh.GetNumBones()) > 0
    except Exception:
        return False


def _actor_still_alive(actor):
    if actor is None:
        return False
    if any(str(actor) == str(pawn) for pawn in _controller()._targets().values()):
        return False
    try:
        return actor.K2_GetActorLocation() is not None
    except Exception:
        return False


def _player_camera_manager(pc):
    return getattr(pc, 'PlayerCameraManager', None) or getattr(pc, 'CameraManager', None)


def _actor_camera_mode(pcm, pawn):
    return str(pcm.GetActorCameraMode(pawn) or '').strip()
