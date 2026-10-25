"""Staged native-motion experiment. Disabled unless explicitly armed.

Native clip selection consumes the navigation simulation's frame, not reflected
animation speed caches. This driver permits complete native updates and restores
the cosmetic attachment at an owned PostPhysics boundary. Actual evaluated poses,
network ordering and guest behaviour must still be validated in game.
"""
from __future__ import annotations

import copy
import math
import time
import hashlib
import json
from pathlib import Path

CLASS_PATH = '/Game/SQBT/NativeFrameMotion/BP_NativeMotionFrameProxy.BP_NativeMotionFrameProxy_C'
KEY = 'native_frame_driver'
# The Blueprint override has its own UFunction; a base Engine.Actor hook does
# not prove interception of the generated event.
HOOK = CLASS_PATH + ':ReceiveTick'
HOOK_ID = 'SQBT.NativeFrameMotion.PostPhysics'
_states = {}
_hooked = False
# A component prerequisite does not establish completion of GbxNav's separate
# task manager. Keep this hard gate closed until its callback ordering is proven.
NATIVE_BOUNDARY_VERIFIED = False
LEGACY_FLAGS = ('network_follow_trial', 'passive_locomotion_trial',
    'player_stance_trial', 'active_native_motion_trial', 'gait_speed_scale_trial',
    'native_actor_cache_trial', 'native_nav_intent_trial', 'native_ground_contact_trial',
    'native_movement_input_trial', 'attached_native_motion_trial', 'native_motion_trial')


def _same(a, b):
    return a is not None and b is not None and str(a) == str(b)


def _point(value):
    return [float(getattr(value,n)) for n in 'XYZ'] if value is not None else None


def owns(state, pawn, actor):
    return (actor is not pawn and pawn.HasAuthority()
        and _same(actor.Owner, pawn) and _same(actor.GetAttachParentActor(), pawn)
        and actor.Controller is None and not state.get('native_seat_clip'))


def active(state):
    saved = state.get(KEY)
    return bool(saved and saved['phase'] == 'active' and not state.get('native_seat_clip'))


def _anchor(saved):
    import unrealsdk
    root = saved['root']()
    if root is not None:
        root.K2_SetRelativeTransform(NewTransform=saved['anchor'], bSweep=False,
            SweepHitResult=unrealsdk.make_struct('HitResult'), bTeleport=True)


def _quiesce(saved):
    actor, movement = saved['actor'](), saved['movement']()
    if actor is not None: actor.SetActorTickEnabled(False)
    if movement is not None:
        movement.SetComponentTickEnabled(False)
        movement.StopMovementImmediately()
        movement.ConsumeInputVector()


def restore(state):
    """Keep a retryable snapshot; seats may run only after this succeeds."""
    saved = state.get(KEY)
    if saved is None: return
    saved['phase'] = 'restoring'
    _quiesce(saved)
    actor, movement, helper = saved['actor'](), saved['movement'](), saved['helper']()
    if helper is not None: helper.SetActorTickEnabled(False)
    if actor is not None and movement is not None:
        import unrealsdk
        unrealsdk.find_class('GbxCharacterFunctionLibrary').ClassDefaultObject.ChangeNavType(actor, saved['nav'])
        # Native notifications can reactivate ticks. Stop them again first.
        _quiesce(saved)
        movement.MaxSimulationIterations = saved['iterations']
        movement.CachedAnimInstance = saved['cached']() if saved['cached'] else None
        movement.SetMovementMode(saved['mode'], saved['custom_mode'])
        movement.bEnablePhysicsInteraction = saved['physics_interaction']
        movement.Velocity = saved['velocity']
        for name,value in saved['input_vectors'].items():setattr(actor,name,copy.copy(value))
        for name, value in saved['speed_scale'].items():
            setattr(movement.MaxGroundSpeedScale, name, value)
        actor.SetActorEnableCollision(False)
        for reference, collision in saved['other_colliders']:
            component = reference()
            if component is not None and _same(component.GetOwner(),actor):
                component.SetCollisionEnabled(collision)
        root = saved['root']()
        if root is not None:
            root.SetGenerateOverlapEvents(False)
            for channel, response in enumerate(saved['responses']):
                root.SetCollisionResponseToChannel(channel, response)
            root.SetCollisionEnabled(saved['collision'])
            root.SetGenerateOverlapEvents(saved['overlaps'])
        actor.SetActorEnableCollision(saved['actor_collision'])
        actor.AnimRootMotionTranslationScale = saved['root_scale']
        if _same(actor.GetAttachParentActor(), saved['pawn']()): _anchor(saved)
        if saved['active']: movement.Activate(False)
        else: movement.Deactivate()
        movement.SetIsReplicated(saved['replicates'])
        movement.SetComponentTickEnabled(saved['tick'])
        actor.SetActorTickEnabled(saved['actor_tick'])
        actor.ForceNetUpdate()
    if helper is not None: helper.K2_DestroyActor()
    _states.pop(saved['helper_key'], None)
    state['native_frame_last_restore'] = {'at_monotonic':time.monotonic(),
        'frames':saved['frames'], 'succeeded':True}
    state.pop(KEY, None)


def _feed(saved):
    import unrealsdk
    pawn, actor, movement = saved['pawn'](), saved['actor'](), saved['movement']()
    velocity = pawn.GetVelocity()
    x, y = float(velocity.X), float(velocity.Y)
    speed = math.hypot(x, y)
    maximum = max(speed, float(pawn.CharacterMovement.GetMaxSpeed()), 1.)
    stance_speed = float(actor.ReplicatedStance.stance.speed)
    if not all(math.isfinite(n) for n in (x, y, maximum, stance_speed)) or stance_speed <= 0:
        raise ValueError('Invalid native stance speed')
    for name in ('Value', 'BaseValue'):
        setattr(movement.MaxGroundSpeedScale, name, maximum / stance_speed)
    movement.Velocity = velocity
    mode = int(pawn.CharacterMovement.MovementMode)
    if mode not in (1, 2, 3): raise ValueError('Unsupported player movement mode')
    if int(movement.MovementMode) != mode: movement.SetMovementMode(mode, 0)
    movement.ConsumeInputVector()
    movement.AddInputVector(unrealsdk.make_struct('Vector', X=x/maximum, Y=y/maximum, Z=0.), True)


def _post_tick(helper, *_args):
    state = _states.get(str(helper))
    if state is None: return
    saved = state.get(KEY)
    if saved is None or not _same(saved['helper'](), helper): return
    try:
        pawn, actor = saved['pawn'](), saved['actor']()
        from .animation import _player_is_driving
        if (pawn is None or actor is None or not owns(state, pawn, actor)
                or _player_is_driving(pawn, getattr(pawn,'Mesh',None))
                or int(helper.PrimaryActorTick.TickGroup) != 4):
            restore(state)
            return
        before = _point(getattr(saved['root'](),'RelativeLocation',None))
        _anchor(saved)
        saved['heartbeat'] = time.monotonic()
        saved['frames'] += 1
        state['native_frame_boundary_observation'] = {'frames':saved['frames'],
            'tick_group':int(helper.PrimaryActorTick.TickGroup), 'at_monotonic':saved['heartbeat'],
            'relative_location_before':before,
            'relative_location_after':_point(getattr(saved['root'](),'RelativeLocation',None))}
        if saved['phase'] == 'pending':
            # No physics until the exact helper has demonstrably ticked.
            import unrealsdk
            movement = saved['movement']()
            unrealsdk.find_class('GbxCharacterFunctionLibrary').ClassDefaultObject.ChangeNavType(actor, 4)
            instance = saved['instance']()
            if instance is None or not _same(instance.GetOwningActor(),actor):
                raise ValueError('Owned native animation instance lost')
            movement.CachedAnimInstance = instance
            movement.MaxSimulationIterations = saved['iterations']
            movement.bEnablePhysicsInteraction = False
            actor.AnimRootMotionTranslationScale = 1.
            root = saved['root']()
            for reference, _ in saved['other_colliders']:
                component = reference()
                if component is not None and _same(component.GetOwner(),actor):
                    component.SetCollisionEnabled(0)
            root.SetGenerateOverlapEvents(False)
            root.SetCollisionResponseToAllChannels(0)
            root.SetCollisionResponseToChannel(0, 2)  # WorldStatic only; no pawn/dynamic pushes.
            root.SetCollisionEnabled(1)  # QueryOnly; grounded sweeps, no rigid-body simulation.
            actor.SetActorEnableCollision(True)
            movement.SetIsReplicated(True)
            movement.Activate(False)
            saved['phase'] = 'active'
        if saved['phase'] == 'active':
            _feed(saved)
            actor.SetActorTickEnabled(True)
            saved['movement']().SetComponentTickEnabled(True)
    except Exception as exc:
        state['native_frame_motion_error'] = type(exc).__name__ + ': ' + str(exc)
        try: restore(state)
        except Exception as failure:
            state['native_frame_restore_error'] = type(failure).__name__ + ': ' + str(failure)


def _spawn_helper(pawn):
    import unrealsdk
    from .native_helpers import _spawn_actor_deferred
    # An installed receipt alone is insufficient: resolve the exact generated
    # class and inspect its CDO before creating anything.
    try: cls = unrealsdk.find_object('BlueprintGeneratedClass', CLASS_PATH)
    except ValueError: cls = None
    if cls is None:
        package, generated = CLASS_PATH.rsplit('.', 1)
        data = unrealsdk.make_struct('AssetData', PackageName=package,
            PackagePath=package.rsplit('/', 1)[0], AssetName=generated[:-2],
            AssetClassPath=unrealsdk.make_struct('TopLevelAssetPath',
                PackageName='/Script/Engine', AssetName='Blueprint'))
        unrealsdk.find_class('AssetRegistryHelpers').ClassDefaultObject.GetAsset(data)
        cls = unrealsdk.find_object('BlueprintGeneratedClass', CLASS_PATH)
    if cls is None or str(cls.SuperField.Name) != 'Actor':
        raise ValueError('Exact Engine.Actor frame helper unavailable')
    cdo = cls.ClassDefaultObject
    if (not cdo.PrimaryActorTick.bCanEverTick or cdo.PrimaryActorTick.bStartWithTickEnabled
            or int(cdo.PrimaryActorTick.TickGroup) != 4
            or int(cdo.PrimaryActorTick.EndTickGroup) != 4
            or cdo.bReplicates):
        raise ValueError('Frame helper tick contract failed')
    gs = unrealsdk.find_class('GameplayStatics').ClassDefaultObject
    helper = _spawn_actor_deferred(gs, pawn, cls, pawn.GetTransform(), class_name=CLASS_PATH)
    if helper is None: raise ValueError('Frame helper spawn failed')
    return helper


def _installed_assets():
    root = Path(__file__).parent.parent
    config = root / 'data/native_frame_motion.json'
    if not config.is_file():
        from mods_base import MODS_DIR
        root = Path(MODS_DIR) / 'Squ1ggsBoostingTools'
        config = root / 'data/native_frame_motion.json'
    if not config.is_file(): return False
    row = json.loads(config.read_text(encoding='utf-8'))
    archives = row.get('archives', {})
    if (row.get('class') != CLASS_PATH or row.get('enabled') is not True
            or len(archives) != 3 or {Path(n).suffix for n in archives} != {'.pak','.utoc','.ucas'}):
        return False
    folder = root / 'assets/native_character_animations'
    return all(Path(n).name == n and (folder/n).is_file()
        and hashlib.sha256((folder/n).read_bytes()).hexdigest() == digest
        for n, digest in archives.items())


def update(state, pawn, actor, mesh, driving):
    """Arm once, fail closed, and never silently retry an unsuccessful trial."""
    if driving or state.get('native_frame_motion_trial') is not True:
        restore(state)
        return None
    if state.get('native_frame_motion_error'):
        restore(state)
        return 'native_frame_unavailable'
    if any(state.get(flag) is True for flag in LEGACY_FLAGS) or not owns(state, pawn, actor):
        restore(state)
        return 'native_frame_unavailable'
    if not NATIVE_BOUNDARY_VERIFIED:
        restore(state)
        return 'native_frame_boundary_unverified'
    saved = state.get(KEY)
    if saved is not None:
        if time.monotonic() - saved['heartbeat'] > .25:
            state['native_frame_motion_error'] = 'PostPhysics heartbeat lost'
            restore(state)
            return 'native_frame_unavailable'
        return 'native_frame_' + saved['phase']
    if not _installed_assets(): return 'native_frame_assets_unavailable'
    import unrealsdk
    from unrealsdk.unreal import WeakPointer
    movement, root = actor.CharacterMovement, actor.RootComponent
    instance = mesh.GetAnimInstance()
    if instance is None or not _same(instance.GetOwningActor(), actor):
        return 'native_frame_waiting_instance'
    if movement.MaxSimulationIterations <= 0:
        raise ValueError('Full native grounded iterations required')
    cached = movement.CachedAnimInstance
    components=list(actor.K2_GetComponentsByClass(unrealsdk.find_class('PrimitiveComponent')) or ())
    if len(components)>128:raise ValueError('Cosmetic collider count exceeds bounded snapshot')
    colliders=[(WeakPointer(part),int(part.GetCollisionEnabled())) for part in components
        if not _same(part,root) and _same(part.GetOwner(),actor)]
    saved = dict(pawn=WeakPointer(pawn), actor=WeakPointer(actor), movement=WeakPointer(movement),
        root=WeakPointer(root), instance=WeakPointer(instance),
        anchor=copy.copy(root.GetRelativeTransform()), phase='pending',
        heartbeat=time.monotonic(), frames=0, nav=movement.ReplicatedNavType,
        iterations=movement.MaxSimulationIterations, cached=WeakPointer(cached) if cached else None,
        mode=int(movement.MovementMode), custom_mode=int(movement.CustomMovementMode),
        active=movement.IsActive(), tick=movement.IsComponentTickEnabled(), replicates=movement.bReplicates,
        actor_tick=actor.IsActorTickEnabled(), root_scale=actor.AnimRootMotionTranslationScale,
        collision=int(root.GetCollisionEnabled()), actor_collision=actor.GetActorEnableCollision(),
        overlaps=root.GetGenerateOverlapEvents(),
        other_colliders=colliders,velocity=copy.copy(movement.Velocity),
        input_vectors={name:copy.copy(getattr(actor,name))
            for name in ('ControlInputVector','LastControlInputVector')},
        responses=[int(root.GetCollisionResponseToChannel(i)) for i in range(32)],
        physics_interaction=movement.bEnablePhysicsInteraction,
        speed_scale={n:float(getattr(movement.MaxGroundSpeedScale,n)) for n in ('Value','BaseValue')})
    helper = _spawn_helper(pawn)
    saved.update(helper=WeakPointer(helper), helper_key=str(helper))
    state[KEY] = saved
    _states[str(helper)] = state
    try:
        global _hooked
        if not _hooked:
            if not unrealsdk.hooks.add_hook(HOOK, unrealsdk.hooks.Type.POST_UNCONDITIONAL, HOOK_ID, _post_tick):
                raise ValueError('Frame hook registration failed')
            _hooked = True
        helper.SetReplicates(False)
        helper.SetActorEnableCollision(False)
        helper.SetActorHiddenInGame(True)
        helper.SetTickGroup(4)
        helper.SetActorTickInterval(0.)
        helper.AddTickPrerequisiteActor(pawn)
        helper.AddTickPrerequisiteActor(actor)
        helper.AddTickPrerequisiteComponent(movement)
        helper.SetActorTickEnabled(True)
    except Exception:
        restore(state)
        raise
    return 'native_frame_pending'
