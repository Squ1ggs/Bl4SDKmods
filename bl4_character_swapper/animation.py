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
    # Bone-name-only humanoid follower trial was malformed live on Amara.
    # Extra native joints are not sufficient proof of compatible bind poses.
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
    return "source_locomotion"


def tick_driver(state: dict[str, Any]) -> bool:
    if state.get("animation_driver") != "source_locomotion":
        return True
    pawn, shell = state.get("pawn"), state.get("shell")
    # A worn actor has no independent travel. Restoring walking mode/velocity
    # here made both native movement and client prediction move the cosmetic.
    _call(shell, "SetActorTickEnabled", False)
    movement = getattr(shell, "CharacterMovement", None)
    _call(movement, "StopMovementImmediately")
    _call(movement, "DisableMovement")
    _call(movement, "SetComponentTickEnabled", False)
    mesh = state.get('render_mesh') or getattr(shell, 'Mesh', None)
    leader = state.get('player_mesh') or getattr(pawn, 'Mesh', None)
    if mesh is None or leader is None:
        return False
    return bind_animation_inputs(state, pawn, shell, mesh, leader)


def update_worn_animation(state, pawn, shell, mesh, leader, *, lobby=False):
    """Drive the native controller's worn actors, including after Gestalt rebuilds.

    Imported packs have a separate animation callback and must not use this.
    Never relax the bone-parent check to force a humanoid pose onto a creature.
    """
    if mesh is None:
        return "unavailable"
    if leader is None:
        saved = state.get('native_animation')
        leader = saved['leader']() if saved and saved.get('leader') else None
        if leader is None:
            restore_seated_pose(state)
            return 'unavailable'
    from . import native_seating
    seated = native_seating.update(state, mesh, _player_is_driving(pawn, leader))
    if seated:
        unbind_animation_inputs(mesh)
        return seated
    try:
        mesh_asset = mesh.GetSkinnedAsset()
        leader_asset = leader.GetSkinnedAsset()
    except Exception:
        mesh_asset = getattr(mesh, "SkeletalMesh", None)
        leader_asset = getattr(leader, "SkeletalMesh", None)
    signature = (str(mesh), str(mesh_asset), str(leader), str(leader_asset),
                 str(getattr(mesh, 'AnimClass', None)), bool(lobby))
    saved = state.get("native_animation")
    if saved is None or saved["signature"] != signature:
        # These references are used only while this Wear is alive. The controller
        # clears the state before destroying either actor or changing maps.
        restore_worn_animation(state)
        from unrealsdk.unreal import WeakPointer
        previous = getattr(mesh, 'LeaderPoseComponent', None)
        driver = start_driver(pawn, shell, mesh, leader, shared_skeleton=False, lobby=lobby)
        saved = {"signature": signature, "driver": driver, "mesh": WeakPointer(mesh),
                 "leader": WeakPointer(leader), "previous": WeakPointer(previous) if previous is not None else None}
        state["native_animation"] = saved
    driver = saved["driver"]
    if driver == "player_pose":
        # Camera/Gestalt changes may clear the pointer without replacing a mesh.
        current = getattr(mesh, "LeaderPoseComponent", None)
        if current is None or str(current) != str(leader):
            if not _call(mesh, "SetLeaderPoseComponent", leader, True, False):
                saved["driver"] = driver = "source_locomotion"
    if driver == "source_locomotion":
        updated = tick_driver({"pawn": pawn, "shell": shell, 'render_mesh': mesh, 'player_mesh': leader,
                               "animation_driver": driver, "scope": "lobby" if lobby else "local"})
        if not updated:
            return "unavailable"
    # Undo old mesh-tilt trials. A lowered crouch is not a vehicle animation.
    if state.get('seated_pose'):
        restore_seated_pose(state)
    return driver


def restore_worn_animation(state):
    from . import native_seating
    native_seating.restore(state)
    restore_seated_pose(state)
    saved = state.pop('native_animation', None)
    if saved is not None:
        unbind_animation_inputs(saved['mesh']())
    if saved is None or saved['driver'] != 'player_pose':
        return
    mesh, leader = saved['mesh'](), saved['leader']()
    if mesh is not None and leader is not None and str(getattr(mesh, 'LeaderPoseComponent', None)) == str(leader):
        previous = saved['previous']() if saved['previous'] else None
        _call(mesh, 'SetLeaderPoseComponent', previous, True, False)


def _animation_input_fields():
    # Scalar/vector animation caches observed on BL4's native instances. No
    # actor, controller, movement component, graph-node or proxy pointers.
    return ('speed', 'Speed2D', 'SpeedRaw', 'Speed2DRaw', 'bIsMoving2D',
            'bIsMovingOrRotating2D', 'bIsFiring', 'AimYaw', 'AimPitch',
            'bIsCrouched', 'bIsCrouching', 'bIsFalling', 'bIsInAir') + _driver_fields()


def _copy_animation_inputs(player, follower):
    copied = 0
    for name in _animation_input_fields():
        try:
            value = getattr(player, name)
            current = getattr(follower, name)
            if isinstance(value, (bool, int, float)) and isinstance(current, (bool, int, float)):
                copied += int(_write(follower, name, value))
            elif name in ('DriveDirection', 'VehicleWorldVelocity', 'VehicleLocalVelocity'):
                copied += int(_write(follower, name, _driver_value(value)))
        except Exception:
            continue
    return copied


def _animation_input_post_update(instance, *_):
    routes = globals().setdefault('_animation_routes', {})
    route = routes.get(str(instance))
    if route is None:
        return
    try:
        pawn, shell = route['pawn'](), route['shell']()
        mesh, leader = route['mesh'](), route['leader']()
        if (route['instance']() is None or pawn is None or shell is None or mesh is None or leader is None
                or str(shell.GetAttachParentActor()) != str(pawn)
                or str(mesh.GetAnimInstance()) != str(instance)):
            routes.pop(str(instance), None)
            return
        player = leader.GetAnimInstance()
        if player is not None and str(player) != str(instance):
            route['copies'] += _copy_animation_inputs(player, instance)
            route['updates'] += 1
    except Exception:
        routes.pop(str(instance), None)


def bind_animation_inputs(state, pawn, shell, mesh, leader):
    """Feed the graph AFTER native cache updates, without enabling travel.

    UAnimInstance::UpdateAnimation invokes BlueprintUpdateAnimation after
    NativeUpdateAnimation and before graph evaluation. The old 20Hz writes
    were overwritten by NativeUpdateAnimation on the next mesh tick.
    """
    from unrealsdk.unreal import WeakPointer
    import unrealsdk
    try:
        instance = mesh.GetAnimInstance()
        player = leader.GetAnimInstance()
        if instance is None or player is None or str(instance) == str(player):
            return False
        hooks = unrealsdk.hooks
        kind = getattr(hooks.Type, 'POST_UNCONDITIONAL', hooks.Type.POST)
        paths = ['/Script/Engine.AnimInstance:BlueprintUpdateAnimation']
        try:
            path = instance.Class._path_name() + ':BlueprintUpdateAnimation'
            if unrealsdk.find_object('Function', path) is not None:
                paths.append(path)
        except Exception:
            pass
        registered = globals().setdefault('_animation_input_hooks', {})
        active = False
        for path in paths:
            if path not in registered:
                key = 'sqbt.cosmetic.animation_inputs.' + __name__
                registered[path] = bool(hooks.add_hook(path, kind, key, _animation_input_post_update))
            active = active or registered[path]
        if not active:
            return False
        routes = globals().setdefault('_animation_routes', {})
        route = routes.get(str(instance))
        if route is None or str(route['leader']()) != str(leader):
            route = {'instance': WeakPointer(instance), 'pawn': WeakPointer(pawn), 'shell': WeakPointer(shell),
                     'mesh': WeakPointer(mesh), 'leader': WeakPointer(leader), 'updates': 0, 'copies': 0}
            routes[str(instance)] = route
        state['animation_input_route'] = str(instance)
        return True
    except Exception:
        return False


def unbind_animation_inputs(mesh):
    routes = globals().setdefault('_animation_routes', {})
    for key, route in list(routes.items()):
        if route['mesh']() is None or (mesh is not None and str(route['mesh']()) == str(mesh)):
            routes.pop(key, None)


def _driver_fields():
    return ('bIsDriving', 'DriveDirection', 'VehicleSpeed', 'VehicleWorldVelocity',
        'VehicleLocalVelocity', 'bVehicleAirborne', 'bVehiclePowerslideJumping',
        'bVehicleLanded', 'VehicleLandedAirTime', 'VehicleLandedVelZ')


def _driver_value(value):
    """Own a copy of a reflected vector instead of retaining borrowed fields."""
    if isinstance(value, (bool, int, float)):
        return value
    import unrealsdk
    axes = ('X', 'Y', 'Z') if hasattr(value, 'Z') else ('X', 'Y')
    return unrealsdk.make_struct('Vector' if len(axes) == 3 else 'Vector2D',
        **{axis: float(getattr(value, axis)) for axis in axes})


def restore_vehicle_inputs(state):
    saved = state.pop('vehicle_animation_inputs', None)
    if saved and saved.get('read_only'):
        return
    instance = saved['instance']() if saved else None
    if instance is not None:
        for name, value in saved['values'].items():
            _write(instance, name, value)


def _player_is_driving(pawn: Any, leader: Any) -> bool:
    """Require an occupied driving state; an owned parked vehicle is insufficient."""
    try:
        if leader is not None:
            player = leader.GetAnimInstance()
            if player is not None and bool(getattr(player, "bIsDriving", False)):
                return True
    except Exception:
        pass
    if bool(getattr(pawn, "bIsDriving", False)):
        return True
    return False


def _read_relative_pose(mesh: Any) -> dict[str, Any] | None:
    try:
        loc = mesh.RelativeLocation
        rot = mesh.RelativeRotation
        return {
            "x": float(loc.X),
            "y": float(loc.Y),
            "z": float(loc.Z),
            "pitch": float(rot.Pitch),
            "yaw": float(rot.Yaw),
            "roll": float(rot.Roll),
        }
    except Exception:
        return None


def _write_relative_pose(mesh: Any, pose: dict[str, Any]) -> bool:
    import unrealsdk

    try:
        loc = unrealsdk.make_struct(
            "Vector",
            X=float(pose["x"]),
            Y=float(pose["y"]),
            Z=float(pose["z"]),
        )
        rot = unrealsdk.make_struct(
            "Rotator",
            Pitch=float(pose["pitch"]),
            Yaw=float(pose["yaw"]),
            Roll=float(pose["roll"]),
        )
    except Exception:
        return False
    if _call(mesh, "K2_SetRelativeLocationAndRotation", loc, rot, False, False):
        return True
    if _call(mesh, "K2_SetRelativeLocation", loc, False, False) and _call(
        mesh, "K2_SetRelativeRotation", rot, False, False
    ):
        return True
    written = _write(mesh, "RelativeLocation", loc)
    written = _write(mesh, "RelativeRotation", rot) or written
    return written


def restore_seated_pose(state: dict[str, Any], mesh: Any | None = None) -> None:
    """Undo seated crouch offset applied while driving."""
    saved = state.pop("seated_pose", None)
    if saved is None:
        return
    target = mesh
    if target is None:
        try:
            target = saved["mesh"]()
        except Exception:
            target = None
    pose = saved.get("original")
    if target is not None and pose is not None:
        _write_relative_pose(target, pose)
    if saved.get("forced_crouch") and saved.get("shell") is not None:
        try:
            shell = saved["shell"]()
        except Exception:
            shell = None
        if shell is not None and "crouch_was" in saved:
            _write(shell, "bIsCrouched", saved["crouch_was"])


def sync_seated_pose(state: dict[str, Any], pawn: Any, shell: Any, mesh: Any, leader: Any) -> bool:
    """Seat the worn shell while driving without writing anim-instance drive flags.

    Writing bIsDriving onto the cosmetic AnimInstance was rejected live (native
    graph resets it). Instead: snapshot RelativeLocation/Rotation, crouch the
    shell slightly into the seat, and mark bIsCrouched for locomotion graphs.
    Restores on exit / restore().
    """
    from unrealsdk.unreal import WeakPointer

    driving = _player_is_driving(pawn, leader)
    if not driving:
        if state.get("seated_pose") is not None:
            restore_seated_pose(state, mesh)
        return False
    if mesh is None:
        return False
    saved = state.get("seated_pose")
    if saved is None:
        original = _read_relative_pose(mesh)
        if original is None:
            return False
        seated = dict(original)
        # Lower and pitch forward into a driving crouch (cm / degrees).
        seated["z"] = float(original["z"]) - 42.0
        seated["pitch"] = float(original["pitch"]) - 28.0
        if not _write_relative_pose(mesh, seated):
            return False
        crouch_was = bool(getattr(shell, "bIsCrouched", False)) if shell is not None else False
        if shell is not None:
            _write(shell, "bIsCrouched", True)
        state["seated_pose"] = {
            "mesh": WeakPointer(mesh),
            "shell": WeakPointer(shell) if shell is not None else None,
            "original": original,
            "crouch_was": crouch_was,
            "forced_crouch": shell is not None,
        }
        return True
    # Keep crouch sticky while still driving (locomotion tick may clear it).
    if shell is not None:
        _write(shell, "bIsCrouched", True)
    return True


def sync_vehicle_inputs(state, pawn, source, actor_mesh):
    """Diagnostics-only: read driving inputs; do not fight the native anim graph.

    Live testing showed writes to cosmetic bIsDriving are reset every tick.
    Seated visuals use sync_seated_pose instead.
    """
    from unrealsdk.unreal import WeakPointer

    player_mesh, mesh = actor_mesh(pawn), actor_mesh(source)
    if player_mesh is None or mesh is None:
        restore_vehicle_inputs(state)
        return False
    try:
        player, instance = player_mesh.GetAnimInstance(), mesh.GetAnimInstance()
        driving = player is not None and bool(getattr(player, "bIsDriving", False))
    except Exception:
        restore_vehicle_inputs(state)
        return False
    # Cosmetics without a driving pin are incompatible — do not claim success.
    if not driving or instance is None or not hasattr(instance, "bIsDriving"):
        restore_vehicle_inputs(state)
        return False
    # Snapshot-only for diagnostics; never write back onto the cosmetic instance.
    saved = state.get("vehicle_animation_inputs")
    if saved is None:
        saved = {"instance": WeakPointer(player), "values": {}, "read_only": True}
        state["vehicle_animation_inputs"] = saved
    for name in _driver_fields():
        if hasattr(player, name):
            saved["values"][name] = _driver_value(getattr(player, name))
    return True
