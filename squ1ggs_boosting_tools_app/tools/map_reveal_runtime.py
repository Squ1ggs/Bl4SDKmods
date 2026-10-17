"""Offline control-flow checks; all game objects and game calls are fake."""
import json
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1] / 'resources'
SOURCE = (ROOT/'Squ1ggsBoostingTools/map_reveal.py').read_text(encoding='utf-8')
EXPECTED_STOPS = len(json.loads((ROOT/'Squ1ggsBoostingTools/data/map_reveal_route.json').read_text())['stops'])



def scenario(kind):
    clock = NS(value=0.0)
    vector = lambda x=0, y=0, z=0: NS(X=x, Y=y, Z=z)
    movement = NS(MovementMode=1, CustomMovementMode=0)
    movement.StopMovementImmediately = lambda: None
    movement.DisableMovement = lambda: setattr(movement, 'MovementMode', 0)
    def set_mode(mode, custom):
        movement.MovementMode, movement.CustomMovementMode = mode, custom
    movement.SetMovementMode = set_mode
    host = NS(HasAuthority=lambda: True)
    identity = NS(display_name='SimulatedGuest')
    pc = NS()
    pawn = NS(Controller=pc, CharacterMovement=movement,
              CapsuleComponent=NS(GetScaledCapsuleHalfHeight=lambda: 105.0))
    pc.Pawn = pawn
    home = (-140915.56, 271748.68, 12217.38) if kind == 'already_nearby' else (-50000, -40000, 13000)
    position = vector(*home)
    pawn.K2_GetActorLocation = lambda: position
    pawn.K2_GetActorRotation = lambda: NS(Pitch=0., Yaw=10., Roll=0.)
    pawn.GetTransform = lambda: NS(Translation=vector(position.X, position.Y, position.Z))
    pawn.ForceNetUpdate = lambda: None
    calls = []
    def teleport(target, rotation):
        calls.append((target.X, target.Y, target.Z))
        if kind == 'blocked_center' and len(calls) == 1:
            return False
        if kind == 'all_stops_blocked' and (target.X, target.Y, target.Z) != home:
            return False
        position.X, position.Y, position.Z = target.X, target.Y, target.Z
        return True
    pawn.K2_TeleportTo = teleport
    control = NS(pc=pc, world='World_P')
    state = NS(__file__=str(ROOT/'Squ1ggsBoostingTools/map_discovery.py'))
    original_tick = lambda *a, **k: None
    serial = NS(_tick_cb=original_tick)
    other_identity = NS(display_name='SimulatedGuest' if kind == 'ambiguous_guest' else 'OtherGuest')
    other_pc = NS(Pawn=NS())
    lobby = [identity, other_identity] if kind in ('named_guest', 'ambiguous_guest') else [other_identity] if kind == 'missing_guest' else [identity, identity] if kind == 'duplicate_rows' else [identity]
    up = NS(snapshot_lobby_identities=lambda: lobby, resolve_lobby_pc=lambda i: control.pc if i is identity else other_pc,
            _pc_is_local_host=lambda p: False, _pc_matches_identity=lambda p, i: p is pc)
    volumes = []
    def begin(**kwargs):
        obj = NS(destroyed=False, bOnlyRelevantToOwner=False, bAlwaysRelevant=False)
        obj.SetReplicates = obj.SetReplicateMovement = obj.SetLifeSpan = lambda *a: None
        obj.ForceNetUpdate = lambda: None
        obj.K2_DestroyActor = lambda: setattr(obj, 'destroyed', True)
        volumes.append(obj)
        return obj
    statics = NS(GetCurrentLevelName=lambda *a: control.world, GetTimeSeconds=lambda *a: clock.value,
                 IsGamePaused=lambda *a: False, RebaseLocalOriginOntoZero=lambda h, v: v,
                 RebaseZeroOriginOntoLocal=lambda h, v: v, BeginDeferredActorSpawnFromClass=begin,
                 FinishSpawningActor=lambda **k: k['Actor'])
    box = NS(ClassDefaultObject=NS(RootComponent=NS(BoxExtent=vector(40, 40, 40))))
    sdk = types.ModuleType('unrealsdk')
    sdk.find_class = lambda name: NS(ClassDefaultObject=statics) if name == 'GameplayStatics' else box
    sdk.find_enum = lambda name: NS(AlwaysSpawn=1, OverrideRootScale=1)
    sdk.make_struct = lambda name, **kwargs: NS(**kwargs)
    sdk.logging = NS(info=lambda *a: None)
    unreal = types.ModuleType('unrealsdk.unreal')
    unreal.WeakPointer = lambda obj: lambda: None if getattr(obj, 'destroyed', False) else obj
    mods = types.ModuleType('mods_base'); mods.get_pc = lambda: host
    package = types.ModuleType('Squ1ggsBoostingTools'); package.__path__ = []
    package.map_discovery, package.serial_rewards, package.uvhm_progression = state, serial, up
    package.data_files = NS(read_data_json=lambda name: json.loads((ROOT/'Squ1ggsBoostingTools/data'/name).read_text()))
    package.runtime_log = NS(note=lambda message: None)
    package.map_party_escort = NS(status=lambda: {'active': False})
    replacements = {'unrealsdk': sdk, 'unrealsdk.unreal': unreal, 'mods_base': mods,
                    'Squ1ggsBoostingTools': package, 'Squ1ggsBoostingTools.data_files': package.data_files}
    old_modules = {k: sys.modules.get(k) for k in replacements}
    import pkgutil
    old_data = pkgutil.get_data
    pkgutil.get_data = lambda *args: (ROOT/'Squ1ggsBoostingTools/travelstations.json').read_bytes()
    old_clock = time.monotonic
    try:
        sys.modules.update(replacements)
        time.monotonic = lambda: clock.value
        namespace = {'__package__': 'Squ1ggsBoostingTools'}
        if kind in ('named_guest', 'missing_guest', 'ambiguous_guest'):
            namespace['FOG_TARGET_NAME'] = 'SimulatedGuest'
        try:
            exec(compile(SOURCE, 'production-map-reveal-under-simulation', 'exec'), namespace)
            namespace['start'](identity)
        except RuntimeError as exc:
            assert kind in ('missing_guest', 'ambiguous_guest'), (kind, str(exc))
            assert ('not available' if kind == 'missing_guest' else 'unambiguous') in str(exc)
            assert not calls and serial._tick_cb is original_tick and movement.MovementMode == 1
            return dict(scenario=kind, phase='refused_without_mutation')
        for step in range(300):
            clock.value += 1
            namespace['runtime_tick']()
            job = namespace['status']()
            if kind == 'cancel' and step == 1:
                namespace['cancel']()
            if kind == 'identity_change' and step == 1:
                control.pc = NS(Pawn=NS())
            if kind == 'world_change' and step == 1:
                control.world = 'Other_P'
            if kind == 'fall' and job['phase'] == 'dwell':
                position.Z -= 2000
            if not job['running']:
                break
        assert not job['running'], (kind, 'job did not finish')
        assert serial._tick_cb is original_tick, (kind, 'tick not restored')
        assert movement.MovementMode == 1, (kind, 'movement not restored')
        if kind in ('complete', 'cancel', 'blocked_center', 'already_nearby', 'all_stops_blocked', 'fall', 'boundary_patch', 'named_guest', 'duplicate_rows'):
            assert job['home_restored'] and (position.X, position.Y, position.Z) == home, (kind, 'home not restored')
        if kind in ('complete', 'blocked_center', 'already_nearby', 'named_guest', 'duplicate_rows'):
            assert len(job['passes']) == EXPECTED_STOPS and job['phase'] == 'complete'
            assert clock.value <= EXPECTED_STOPS*10+20, clock.value
            if kind == 'blocked_center':
                assert any(row['attempts'] == 2 for row in job['landings'])
            if kind == 'already_nearby':
                assert job['landings'][0]['method'] == 'already_nearby'
        elif kind == 'all_stops_blocked':
            assert len(job['skipped']) + len(job['passes']) == EXPECTED_STOPS and job['skipped'] and job['phase'] == 'partial'
        elif kind == 'boundary_patch':
            assert len(job['passes']) == 2 and job['scope'] == 'boundary_patch' and clock.value < 35
            assert job['passes'][0]['station'] == 'World_P.FT_SHA_ZanesBar'
        elif kind in ('identity_change', 'world_change'):
            assert len(calls) <= 1 and job['phase'] == 'restore_failed', (kind, 'retargeted unsafe return')
        else:
            assert job['phase'] == 'stopped', kind
        assert all(v.destroyed for v in volumes), (kind, 'test volume leaked')
        return dict(scenario=kind, passes=len(job['passes']), elapsed=clock.value, phase=job['phase'])
    finally:
        pkgutil.get_data = old_data
        time.monotonic = old_clock
        for key, value in old_modules.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


for case in ('complete', 'already_nearby', 'blocked_center', 'all_stops_blocked', 'cancel', 'identity_change', 'world_change', 'fall'):
    print(json.dumps(scenario(case)))
