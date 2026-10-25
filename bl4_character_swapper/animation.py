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
    movement = getattr(shell, "CharacterMovement", None)
    controlled_follow = (state.get('network_follow_trial') is True
                        and state.get('passive_locomotion_trial') is True
                        and shell is not pawn and shell.GetAttachParentActor() is None
                        and str(getattr(shell, 'Owner', None)) == str(pawn)
                        and getattr(shell, 'Controller', None) is None)
    cache_tick = (controlled_follow and state.get('native_actor_cache_trial') is True
                  and float(getattr(shell,'AnimRootMotionTranslationScale',1.0)) == 0.0)
    _call(shell, 'SetActorTickEnabled', cache_tick)
    if not controlled_follow:
        _call(movement, "StopMovementImmediately")
        _call(movement, "DisableMovement")
    _call(movement, "SetComponentTickEnabled", False)
    mesh = state.get('render_mesh') or getattr(shell, 'Mesh', None)
    leader = state.get('player_mesh') or getattr(pawn, 'Mesh', None)
    if mesh is None or leader is None:
        return False
    # An attached local body keeps its own graph. That graph reads movement
    # velocity, and DisableMovement above clears it, so a walk never starts.
    # Copy the player's velocity only. The movement component stays unticked
    # so the cosmetic actor cannot travel on its own.
    if state.get('scope') != 'lobby' and shell is not None and pawn is not None and shell is not pawn and movement is not None:
        try:
            parent = shell.GetAttachParentActor()
        except Exception:
            parent = None
        if parent is not None and str(parent) == str(pawn) and not _player_is_driving(pawn, leader):
            player_movement = getattr(pawn, 'CharacterMovement', None)
            if player_movement is not None:
                try:
                    velocity = pawn.GetVelocity()
                    _write(movement, 'Velocity', velocity)
                    for name in ('Acceleration', 'AnalogInputModifier'):
                        value = getattr(player_movement, name, None)
                        if value is not None:
                            _write(movement, name, value)
                except Exception:
                    pass
    if state.get('network_follow_trial') is True:
        unbind_animation_inputs(mesh)
        bound = True
    else:
        bound = bind_animation_inputs(state, pawn, shell, mesh, leader)
    if state.get('passive_locomotion_trial') is True:
        # Animation inputs only: never permit either movement simulation tick.
        allow_active = state.get('network_follow_trial') is True and state.get('active_native_motion_trial') is True
        if (movement is None or (movement.IsActive() and not allow_active) or movement.IsComponentTickEnabled()
                or (shell.IsActorTickEnabled() and not cache_tick) or (str(shell.GetAttachParentActor()) != str(pawn)
                    and not (state.get('network_follow_trial') is True and shell.GetAttachParentActor() is None and str(getattr(shell,'Owner',None)) == str(pawn)))):
            return False
        if not _player_is_driving(pawn,leader):
            velocity = pawn.GetVelocity()
            movement.Velocity = velocity
            if controlled_follow:
                # Grounded native graphs also inspect acceleration and analog
                # intent. Velocity alone left them easing through walk starts.
                player_movement = getattr(pawn, 'CharacterMovement', None)
                for name in ('Acceleration', 'AnalogInputModifier'):
                    value = getattr(player_movement, name, None)
                    if value is not None:
                        _write(movement, name, value)
    return bound


def _restore_attached_native_driver(state):
    # Keep the snapshot until every native notification and restore succeeds.
    # A failed ChangeNavType must not strand an active cosmetic driver with no
    # restore data, particularly while the wearer is entering a vehicle.
    saved = state.get('native_attached_driver')
    if saved is None:return
    import unrealsdk
    actor,movement=saved['actor'](),saved['movement']()
    if actor is None or movement is None:
        state.pop('native_attached_driver',None)
        return
    movement.SetComponentTickEnabled(False)
    movement.StopMovementImmediately()
    library=unrealsdk.find_class('GbxCharacterFunctionLibrary').ClassDefaultObject
    library.ChangeNavType(actor,saved['nav'])
    movement.MaxSimulationIterations=saved['iterations']
    previous=saved['cached']
    movement.CachedAnimInstance=previous() if previous else None
    movement.SetMovementMode(saved['mode'],0)
    if saved['active']:movement.Activate(False)
    else:movement.Deactivate()
    movement.SetIsReplicated(saved['replicates'])
    movement.SetComponentTickEnabled(saved['tick'])
    actor.AnimRootMotionTranslationScale=saved['root_scale']
    actor.SetActorTickEnabled(saved['actor_tick'])
    actor.ForceNetUpdate()
    state.pop('native_attached_driver',None)
    state.pop('attached_native_restore_error',None)


def _hold_attached_native_driver(state,pawn,actor):
    if (actor is pawn or str(getattr(actor,'Owner',None))!=str(pawn)
            or str(actor.GetAttachParentActor())!=str(pawn)
            or getattr(actor,'Controller',None) is not None):return False
    import unrealsdk
    root=actor.RootComponent
    zero=unrealsdk.make_struct('Vector',X=0.,Y=0.,Z=0.)
    try:
        root.K2_SetRelativeLocation(NewLocation=zero,bSweep=False,
            SweepHitResult=unrealsdk.make_struct('HitResult'),bTeleport=True)
        root.K2_SetRelativeRotation(NewRotation=unrealsdk.make_struct('Rotator',Pitch=0.,Yaw=0.,Roll=0.),
            bSweep=False,SweepHitResult=unrealsdk.make_struct('HitResult'),bTeleport=True)
    except Exception as exc:
        state['attached_native_error']=str(exc)
        return False
    return True


def _update_attached_native_driver(state,pawn,actor,mesh):
    """Opt-in native updates on an attached cosmetic, with no server physics loop."""
    import unrealsdk
    from unrealsdk.unreal import WeakPointer
    if not pawn.HasAuthority() or not _hold_attached_native_driver(state,pawn,actor):
        _restore_attached_native_driver(state)
        return 'attached_native_unavailable'
    movement=actor.CharacterMovement
    saved=state.get('native_attached_driver')
    if saved is None:
        cached=movement.CachedAnimInstance
        saved={'actor':WeakPointer(actor),'movement':WeakPointer(movement),
            'iterations':movement.MaxSimulationIterations,'nav':movement.ReplicatedNavType,
            'mode':int(movement.MovementMode),'tick':movement.IsComponentTickEnabled(),
            'active':movement.IsActive(),'replicates':movement.bReplicates,
            'actor_tick':actor.IsActorTickEnabled(),'root_scale':float(actor.AnimRootMotionTranslationScale),
            'cached':WeakPointer(cached) if cached is not None else None}
        state['native_attached_driver']=saved
        unrealsdk.find_class('GbxCharacterFunctionLibrary').ClassDefaultObject.ChangeNavType(actor,4)
    movement.MaxSimulationIterations=0
    actor.AnimRootMotionTranslationScale=0.
    movement.SetIsReplicated(True)
    movement.Activate(False)
    instance=mesh.GetAnimInstance()
    if instance is not None and str(instance.GetOwningActor())==str(actor):
        movement.CachedAnimInstance=instance
    velocity=pawn.GetVelocity()
    movement.Velocity=velocity
    mode=int(pawn.CharacterMovement.MovementMode)
    if int(movement.MovementMode)!=mode:movement.SetMovementMode(mode,0)
    speed=(float(velocity.X)**2+float(velocity.Y)**2)**.5
    direction=unrealsdk.make_struct('Vector',X=float(velocity.X)/speed if speed>2 else 0.,
        Y=float(velocity.Y)/speed if speed>2 else 0.,Z=0.)
    movement.ConsumeInputVector()
    movement.AddInputVector(direction,True)
    actor.SetActorTickEnabled(True)
    movement.SetComponentTickEnabled(True)
    return 'attached_native_update'


def _arm_player_gun_graph(state, mesh):
    """Keep gun-pose graphs eligible while idle. Hidden-gun imports stay hidden."""
    from .appearance_visibility import _camera_anatomy
    from .native_weapon import body_holds_gun
    if mesh is None or not body_holds_gun(mesh) or _camera_anatomy(mesh).get('first_person_weapon_policy') == 'hide_known_unsupported':
        return False
    row = state.get('native_motion_definition')
    if not row:
        from . import native_motion
        row = native_motion.definition(mesh, state)
    if not row:
        return False
    if row.get('local_weapon_preview_enabled') is not True and row.get('source') != 'game_native':
        return False
    state['native_weapon_trial'] = True
    return True


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
    from . import native_seating, native_motion
    driving = _player_is_driving(pawn, leader)
    motion_enabled=state.get('native_motion_trial') is True
    if 'native_motion_trial' not in state:
        lookup=getattr(native_motion,'definition',None)
        configured=lookup(mesh,state) if callable(lookup) else None
        motion_enabled=configured is not None and configured.get('local_slot_motion_enabled') is True
    if driving or motion_enabled:
        # Nav restoration may recreate the native graph. Complete it before
        # a seat or locomotion clip takes ownership of a single-node instance.
        if state.get('lobby_visibility', {}).get('root_motion_translation_scale') is not None:
            from .appearance_visibility import restore_native_animation_cache
            try:
                restore_native_animation_cache(state, shell, shell.CharacterMovement)
            except Exception as exc:
                state['native_cache_restore_error'] = type(exc).__name__ + ': ' + str(exc)
                return 'seat_handoff_waiting' if driving else 'native_motion_handoff_waiting'
    if state.get('native_frame_driver') or state.get('native_frame_motion_trial') is True:
        from . import native_frame_motion
        try:
            frame_status = native_frame_motion.update(state,pawn,shell,mesh,driving)
        except Exception as exc:
            state['native_frame_motion_error']=type(exc).__name__+': '+str(exc)
            try: native_frame_motion.restore(state)
            except Exception as failure:
                state['native_frame_restore_error']=type(failure).__name__+': '+str(failure)
                return 'seat_handoff_waiting' if driving else 'native_frame_restore_waiting'
            frame_status = 'native_frame_unavailable'
        if frame_status:
            unbind_animation_inputs(mesh)
            return frame_status
    if driving:
        native_motion.restore(state)
        try:
            _restore_attached_native_driver(state)
        except Exception as exc:
            state['attached_native_restore_error']=type(exc).__name__+': '+str(exc)
            return 'seat_handoff_waiting'
    seated = native_seating.update(state, mesh, driving)
    if seated:
        unbind_animation_inputs(mesh)
        return seated
    if state.get('attached_native_motion_trial') is True and not driving:
        unbind_animation_inputs(mesh)
        try:
            return _update_attached_native_driver(state,pawn,shell,mesh)
        except Exception as exc:
            state['attached_native_error']=type(exc).__name__+': '+str(exc)
            _restore_attached_native_driver(state)
            return 'attached_native_unavailable'
    _restore_attached_native_driver(state)
    motion = native_motion.update(state, pawn, shell, mesh, driving)
    if motion:
        # The full-body clip only runs above the slow-walk gate. The graph
        # keeps idle gun-hold, and these scalars follow the player.
        if _arm_player_gun_graph(state, mesh) or state.get('native_weapon_trial') is True:
            bind_animation_inputs(state, pawn, shell, mesh, leader)
        else:
            unbind_animation_inputs(mesh)
        return motion
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
        if _arm_player_gun_graph(state, mesh):
            bind_animation_inputs(state, pawn, shell, mesh, leader)
        updated = tick_driver({"pawn": pawn, "shell": shell, 'render_mesh': mesh, 'player_mesh': leader,
                               "animation_driver": driver, "scope": "lobby" if lobby else "local",
                               'passive_locomotion_trial':state.get('passive_locomotion_trial',False),
                               'network_follow_trial':state.get('network_follow_trial',False),
                               'active_native_motion_trial':state.get('active_native_motion_trial',False),
                               'native_actor_cache_trial':state.get('native_actor_cache_trial',False)})
        if not updated:
            return "unavailable"
    # Undo old mesh-tilt trials. A lowered crouch is not a vehicle animation.
    if state.get('seated_pose'):
        restore_seated_pose(state)
    return driver


def restore_worn_animation(state):
    if state.get('native_frame_driver'):
        from . import native_frame_motion
        native_frame_motion.restore(state)
    _restore_attached_native_driver(state)
    from . import native_seating, native_motion
    native_motion.restore(state)
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
                or (str(shell.GetAttachParentActor()) != str(pawn) and not
                    (route.get('network_follow_trial') is True and shell.GetAttachParentActor() is None and str(getattr(shell,'Owner',None)) == str(pawn)))
                or str(mesh.GetAnimInstance()) != str(instance)):
            routes.pop(str(instance), None)
            return
        player = leader.GetAnimInstance()
        state = route.get('state')
        if player is not None and str(player) != str(instance):
            route['copies'] += _copy_animation_inputs(player, instance)
            from . import native_weapon
            if state is not None and state.get('native_weapon_trial') is True:
                native_weapon.sync_combat_inputs(state, player, instance)
            from .packs.imported_weapons import _local_first_person
            if state is not None and state.get('hide_wearer_arms'):
                if _local_first_person(pawn):
                    native_weapon.hide_viewmodel_arms(state, pawn)
                    native_weapon._set_hand_gun_visible(state, False)
                    if native_weapon._player_is_aiming(pawn):
                        native_weapon._show_player_guns(state.get('native_weapon_preview'))
                else:
                    native_weapon.release_viewmodel_arms(state)
                    native_weapon._show_player_guns(state.get('native_weapon_preview'))
            elif state is not None and _local_first_person(pawn) and native_weapon._player_is_aiming(pawn):
                native_weapon.release_viewmodel_arms(state)
                native_weapon._show_player_guns(state.get('native_weapon_preview'))
                native_weapon._set_hand_gun_visible(state, False)
            elif state is not None and state.get('viewmodel_arms') is not None:
                native_weapon.hide_viewmodel_arms(state, pawn)
                native_weapon.show_swapped_arms(shell, mesh)
                preview = state.get('native_weapon_preview')
                if preview is not None:
                    native_weapon._hide_player_guns(preview, pawn)
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
        route['state'] = state
        route['network_follow_trial'] = state.get('network_follow_trial') is True
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
    # Cosmetics without a driving pin are incompatible â€” do not claim success.
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
