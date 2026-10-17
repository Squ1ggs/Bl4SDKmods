"""Paced main-Kairos terrain reveal using native player-owned discovery boxes.

Uses the tested station route; restores the original pose and movement.
"""
import json
import math
import time
import unrealsdk
from unrealsdk.unreal import WeakPointer
from mods_base import get_pc
from . import serial_rewards, uvhm_progression as up
from .data_files import read_data_json

_job = None
_advance = None
_cancel = None

def is_running():
    return bool(_job and _job.get("running"))

def status():
    return dict(_job or {"running": False, "phase": "idle"})

def runtime_tick():
    if is_running() and _advance is not None:
        _advance()

def cancel():
    if is_running() and _cancel is not None:
        _cancel()

def _log(message):
    try:
        from . import runtime_log
        runtime_log.note("Map reveal: " + message)
    except Exception:
        pass


def start(identity):
    global _job, _advance, _cancel
    if is_running():
        raise RuntimeError('Map reveal is already running.')
    from . import map_party_escort
    if map_party_escort.status().get('active'):
        raise RuntimeError('Stop Guest map assist before starting map reveal.')
    host = get_pc()
    if host is None or not host.HasAuthority():
        raise RuntimeError('A stable listen host is required.')
    statics = unrealsdk.find_class('GameplayStatics').ClassDefaultObject
    if str(statics.GetCurrentLevelName(host, True)) != 'World_P':
        raise RuntimeError('Terrain reveal requires the main Kairos map; return there and run map discovery again.')
    quiet = getattr(serial_rewards, '_serial_mail_join_quiet', None)
    if callable(quiet) and quiet():
        raise RuntimeError('Lobby is settling after a join/leave. Wait 12 seconds after the player joins, then retry.')
    pc = up.resolve_lobby_pc(identity)
    if pc is None:
        raise RuntimeError('Selected map-reveal player is unavailable.')
    if not up._pc_matches_identity(pc, identity):
        raise RuntimeError('Player identity changed.')
    pawn = getattr(pc, 'Pawn', None)
    if pawn is None:
        raise RuntimeError('Player pawn is unavailable.')
    if getattr(pawn, 'Controller', pc) != pc:
        raise RuntimeError('Player pawn/controller mismatch.')
    movement = getattr(pawn, 'CharacterMovement', None)
    if movement is None:
        raise RuntimeError('Player CharacterMovement is unavailable; no teleport attempted.')
    pc_ref, pawn_ref, movement_ref = WeakPointer(pc), WeakPointer(pawn), WeakPointer(movement)
    original_mode = movement.MovementMode
    original_custom_mode = int(movement.CustomMovementMode)
    original_rotation = pawn.K2_GetActorRotation()
    home_rotation = {k: float(getattr(original_rotation, k)) for k in ('Pitch', 'Yaw', 'Roll')}
    home_vector = statics.RebaseLocalOriginOntoZero(host, pawn.K2_GetActorLocation())
    home = tuple(float(getattr(home_vector, k)) for k in ('X', 'Y', 'Z'))
    capsule = getattr(pawn, 'CapsuleComponent', None)
    capsule_height = float(capsule.GetScaledCapsuleHalfHeight()) if capsule else 110.0
    if not (30 <= capsule_height <= 300):
        raise RuntimeError('Unexpected player capsule size; no teleport attempted.')
    plan = read_data_json('map_reveal_route.json')
    import pkgutil
    stations = json.loads(pkgutil.get_data(__package__, 'travelstations.json').decode('utf-8'))['stations']
    approved = {r['station']: r for r in stations if r.get('world') == 'World_P' and r.get('typedef') == 'fast_travel'}
    stops = []
    if plan.get('half_extent_xy_cm') != 160000 or not (1 <= len(plan.get('stops', [])) <= 20):
        raise RuntimeError('Invalid bounded route plan.')
    for row in plan['stops']:
        actual = approved.get(row['station'])
        if actual is None:
            raise RuntimeError('Route includes an unreviewed station.')
        values = {k: float(actual[k]) for k in ('x', 'y', 'z', 'yaw')}
        if not all(math.isfinite(v) for v in values.values()) or any(abs(values[k]) > 2000000 for k in ('x', 'y', 'z')):
            raise RuntimeError('Invalid station coordinates.')
        if any(abs(values[k] - float(row[k])) > 0.01 for k in values):
            raise RuntimeError('Route coordinates differ from the curated station data.')
        stops.append(dict(station=row['station'], **values))
    ordered = []
    current_xy = home[:2]
    while stops:
        row = min(stops, key=lambda r: (r['x']-current_xy[0])**2 + (r['y']-current_xy[1])**2)
        stops.remove(row)
        ordered.append(row)
        current_xy = row['x'], row['y']
    cls = unrealsdk.find_class('GbxDiscoveryFODBox')
    native_extent = cls.ClassDefaultObject.RootComponent.BoxExtent
    if any(abs(float(getattr(native_extent, k))-40) > 0.01 for k in ('X', 'Y', 'Z')):
        raise RuntimeError('Native fog-box extent changed; no teleport attempted.')
    collision = unrealsdk.find_enum('ESpawnActorCollisionHandlingMethod').AlwaysSpawn
    scale_method = unrealsdk.find_enum('ESpawnActorScaleMethod').OverrideRootScale
    job = dict(running=True, phase='teleport', target=identity.display_name, index=0,
               total=len(ordered), stops=ordered, passes=[], skipped=[], landings=[], half_extent_xy_cm=160000, seconds_per_stop=8,
               home=list(home), home_restored=False, movement_restored=True,
               persistence_verified=False, message='Starting map reveal route.')
    started = time.monotonic()
    last_poll = 0.0
    next_world = float(statics.GetTimeSeconds(host)) + 1.0
    volume_refs = []

    def selected_pawn():
        current_pc = up.resolve_lobby_pc(identity)
        if current_pc is None or pc_ref() is None or current_pc != pc_ref() or not up._pc_matches_identity(current_pc, identity):
            return None
        current_pawn = getattr(current_pc, 'Pawn', None)
        return current_pawn if current_pawn is not None and current_pawn == pawn_ref() else None

    def restore_movement():
        component = movement_ref()
        if component is not None:
            component.SetMovementMode(original_mode, original_custom_mode)
            job['movement_restored'] = True

    def teleport_absolute(actor, coordinates, rotation):
        vector = unrealsdk.make_struct('Vector', X=coordinates[0], Y=coordinates[1], Z=coordinates[2])
        local = statics.RebaseZeroOriginOntoLocal(host, vector)
        if not actor.K2_TeleportTo(local, rotation):
            return False
        actor.ForceNetUpdate()
        return True

    def return_home():
        if get_pc() != host or str(statics.GetCurrentLevelName(host, True)) != 'World_P':
            return False
        actor = selected_pawn()
        if actor is None:
            return False
        rotation = unrealsdk.make_struct('Rotator', **home_rotation)
        return teleport_absolute(actor, home, rotation)

    def land_near_station(actor, row, rotation):
        absolute = statics.RebaseLocalOriginOntoZero(host, actor.K2_GetActorLocation())
        # A player already standing beside this station is a better landing than
        # the station actor's occupied centre. Do not move them unnecessarily.
        if math.hypot(float(absolute.X)-row['x'], float(absolute.Y)-row['y']) <= 1500 and abs(float(absolute.Z)-row['z']) <= 1000:
            return dict(station=row['station'], method='already_nearby', attempts=0)
        candidates = [(row['x'], row['y'], row['z']+capsule_height+10.0)]
        # Fast-travel loc is the station actor, not necessarily a free capsule
        # location. Try its front and sides without bypassing native collision.
        for radius in (300.0, 600.0):
            for degrees in (0, 45, -45, 90, -90, 135, -135, 180):
                angle = math.radians(row['yaw']+degrees)
                candidates.append((row['x']+math.cos(angle)*radius,
                                   row['y']+math.sin(angle)*radius,
                                   row['z']+capsule_height+10.0))
        for extra_height in (150.0, 300.0):
            candidates.append((row['x'], row['y'], row['z']+capsule_height+extra_height))
        for attempt, destination in enumerate(candidates, 1):
            if teleport_absolute(actor, destination, rotation):
                return dict(station=row['station'], method='collision_checked', attempts=attempt, destination=list(destination))
        return None

    def finish(reason, failed=False):
        job.update(running=False, phase='stopped' if failed else ('partial' if job['skipped'] else 'complete'), message=reason)
        try:
            if not job['home_restored']:
                job['home_restored'] = bool(return_home())
        except Exception as exc:
            job['return_error'] = str(exc)
        try:
            restore_movement()
        except Exception as exc:
            job['movement_error'] = str(exc)
        for reference in volume_refs:
            volume = reference()
            if volume is not None:
                try:
                    volume.K2_DestroyActor()
                except Exception:
                    pass
        if not job['home_restored']:
            job['message'] += ' Original position could not be restored; check the player.'
            job['phase'] = 'restore_failed'
        if not job['movement_restored']:
            job['phase'] = 'restore_failed'
        _log('Fog teleport route stopped: ' + job['message'])

    def reveal(actor):
        transform = actor.GetTransform()
        transform.Rotation = unrealsdk.make_struct('Quat', X=0.0, Y=0.0, Z=0.0, W=1.0)
        transform.Scale3D = unrealsdk.make_struct('Vector', X=4000.0, Y=4000.0, Z=1250.0)
        volume = None
        try:
            raw = statics.BeginDeferredActorSpawnFromClass(WorldContextObject=host, ActorClass=cls,
                SpawnTransform=transform, CollisionHandlingOverride=collision, owner=pc_ref(), TransformScaleMethod=scale_method)
            volume = raw[0] if isinstance(raw, tuple) else raw
            if volume is None:
                raise RuntimeError('Could not create the native reveal volume.')
            reference = WeakPointer(volume)
            volume_refs.append(reference)
            volume.bOnlyRelevantToOwner = True
            volume.bAlwaysRelevant = False
            volume.SetReplicates(True)
            volume.SetReplicateMovement(True)
            volume.NetUpdateFrequency = 10.0
            volume.SetLifeSpan(15.0)
            raw = statics.FinishSpawningActor(Actor=volume, SpawnTransform=transform, TransformScaleMethod=scale_method)
            volume = raw[0] if isinstance(raw, tuple) else raw
            if volume is None or reference() is None:
                raise RuntimeError('Native reveal volume did not finish spawning.')
            volume.SetLifeSpan(15.0)
            volume.ForceNetUpdate()
            return str(transform.Translation)
        except Exception:
            if volume is not None:
                try:
                    volume.K2_DestroyActor()
                except Exception:
                    pass
            raise

    def advance():
        nonlocal last_poll, next_world
        now = time.monotonic()
        if now-last_poll < 0.2:
            return
        last_poll = now
        if now-started > len(ordered)*20+60:
            finish('Route timed out; returning the player.', True)
            return
        if get_pc() != host or str(statics.GetCurrentLevelName(host, True)) != 'World_P':
            finish('Host/world changed; route stopped.', True)
            return
        actor = selected_pawn()
        if actor is None:
            finish('Player left, changed controller or changed pawn; route stopped without retargeting.', True)
            return
        if statics.IsGamePaused(host):
            return
        world_now = float(statics.GetTimeSeconds(host))
        if job['phase'] in ('reveal', 'dwell') and float(actor.K2_GetActorLocation().Z) < job['landing_z']-1500:
            raise RuntimeError('Player fell below the reviewed landing; returning home.')
        if world_now < next_world:
            return
        phase = job['phase']
        if phase == 'teleport':
            row = ordered[job['index']]
            component = movement_ref()
            if component is None:
                raise RuntimeError('Selected movement component is unavailable.')
            component.StopMovementImmediately()
            component.DisableMovement()
            job['movement_restored'] = False
            rotation = unrealsdk.make_struct('Rotator', Pitch=0.0, Yaw=row['yaw'], Roll=0.0)
            job['message'] = 'Teleporting to ' + row['station']
            landing = land_near_station(actor, row, rotation)
            if landing is None:
                restore_movement()
                job['skipped'].append(dict(station=row['station'], reason='No clear collision-checked landing among 19 nearby candidates.'))
                _log('Fog teleport route: skipped blocked landing at ' + row['station'])
                job['index'] += 1
                if job['index'] < len(ordered):
                    next_world = world_now+0.5
                else:
                    job['home_restored'] = bool(return_home())
                    job.update(phase='home_save_wait', message='Landing checks finished; returning home.')
                    next_world = world_now+8.0
                return
            job['landings'].append(landing)
            job.update(phase='settle', landing_z=float(actor.K2_GetActorLocation().Z))
            next_world = world_now+2.0
        elif phase == 'settle':
            restore_movement()
            job['phase'] = 'reveal'
            next_world = world_now+1.0
        elif phase == 'reveal':
            if float(actor.K2_GetActorLocation().Z) < job['landing_z']-1500:
                raise RuntimeError('Player fell below the reviewed landing; returning home.')
            position = reveal(actor)
            row = ordered[job['index']]
            job['passes'].append(dict(station=row['station'], position=position, elapsed_seconds=round(now-started, 2)))
            job.update(phase='dwell', message='Reveal %d/%d sent; allowing five seconds after the reveal.' % (job['index']+1, job['total']))
            _log('Fog teleport route: ' + job['message'])
            next_world = world_now+5.0
        elif phase == 'dwell':
            job['index'] += 1
            if job['index'] < len(ordered):
                job['phase'] = 'teleport'
                next_world = world_now
            else:
                job['home_restored'] = bool(return_home())
                restore_movement()
                job.update(phase='home_save_wait', message='Player returned home; allowing a final eight seconds before completion.')
                _log('Fog teleport route: ' + job['message'])
                next_world = world_now+8.0
        elif phase == 'home_save_wait':
            finish(('%d blocked stop(s) skipped; route is partial.' % len(job['skipped']) if job['skipped'] else 'Route complete.') +
                   ' Player must verify the main map after their own save/reload.')

    def advance_safely():
        try:
            advance()
        except Exception as exc:
            finish('Route error: ' + str(exc), True)

    _job = job
    _advance = advance_safely
    _cancel = lambda: finish('Stopped by user; returning the player.', True)
    _log('Starting map reveal for %s: %d stops, about %d seconds; returns to the original position.' % (identity.display_name, len(ordered), len(ordered)*8+10))
    return status()
