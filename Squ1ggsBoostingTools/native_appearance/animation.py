"""Animation drivers for a character worn as a cosmetic actor.

Leader pose needs matching bone names and parents, not necessarily the same
Skeleton UObject. Other rigs keep their own AnimBlueprint and receive the
wearer's movement inputs without allowing their movement component to move them.
"""
from __future__ import annotations

from typing import Any


def _write(obj: Any, attr: str, value: Any) -> bool:
    try:
        setattr(obj, attr, value)
        return True
    except Exception:
        return False


def _call(obj: Any, method: str, *args: Any) -> bool:
    try:
        getattr(obj, method)(*args)
        return True
    except Exception:
        return False


def compatible_bones(follower: Any, leader: Any) -> bool:
    """Require every follower bone and parent to exist in the leader."""
    try:
        count = int(follower.GetNumBones())
        if not 0 < count <= 1024:
            return False
        for index in range(count):
            bone = follower.GetBoneName(index)
            if int(leader.GetBoneIndex(bone)) < 0:
                return False
            if str(follower.GetParentBone(bone)) != str(leader.GetParentBone(bone)):
                return False
        return True
    except Exception:
        return False


def start_driver(pawn: Any, shell: Any, mesh: Any, leader: Any, *, shared_skeleton: bool, lobby: bool) -> str:
    for component in (leader, mesh):
        _write(component, "VisibilityBasedAnimTickOption", 0)
        _write(component, "bPauseAnims", False)
        _write(component, "bNoSkeletonUpdate", False)
        _call(component, "SetComponentTickEnabled", True)
    # The pose-component pointer is local; lobby shells use their cooked
    # AnimBlueprint instead so a remote machine can run the same animation.
    if not lobby and (shared_skeleton or compatible_bones(mesh, leader)):
        if _call(mesh, "SetLeaderPoseComponent", leader, True, False) or _call(mesh, "SetLeaderPoseComponent", leader, True):
            return "player_pose"
    # Preserve a cooked NPC's existing pose links and animation instance. In
    # BL4 these can be part of its Gestalt setup; resetting the animation mode
    # or clearing its pose leader can invalidate an otherwise visible body.
    movement = getattr(shell, "CharacterMovement", None)
    if movement is None or getattr(mesh, "AnimClass", None) is None:
        return "unavailable"
    _call(movement, "SetComponentTickEnabled", False)
    state = {"pawn": pawn, "shell": shell, "animation_driver": "source_locomotion"}
    return "source_locomotion" if tick_driver(state) else "unavailable"


def tick_driver(state: dict[str, Any]) -> bool:
    if state.get("animation_driver") != "source_locomotion":
        return True
    pawn, shell = state.get("pawn"), state.get("shell")
    movement = getattr(shell, "CharacterMovement", None)
    original = getattr(pawn, "CharacterMovement", None)
    if movement is None or original is None:
        return False
    try:
        velocity = pawn.GetVelocity()
        mode = original.MovementMode
    except Exception:
        return False
    written = _write(movement, "Velocity", velocity)
    # DisableMovement sets MOVE_None, which makes the NPC graph stay idle.
    # Physics is disabled separately; its graph still sees walking/falling.
    _write(movement, "MovementMode", mode)
    _write(movement, "CustomMovementMode", getattr(original, "CustomMovementMode", 0))
    try:
        _write(movement, "Acceleration", original.GetCurrentAcceleration())
    except Exception:
        pass
    _write(shell, "bIsCrouched", getattr(pawn, "bIsCrouched", False))
    if state.get("scope") == "lobby":
        try:
            shell.ReplicatedMovement.LinearVelocity = velocity
            shell.ReplicatedMovement.bRepPhysics = False
        except Exception:
            pass
        _call(shell, "ForceNetUpdate")
    return written
