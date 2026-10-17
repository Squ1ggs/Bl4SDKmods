"""Create or relocate one native Black Market machine; verify on later ticks."""
from __future__ import annotations
import math
import time
from typing import Any
import unrealsdk
from unrealsdk.unreal import WeakPointer
from mods_base import get_pc

_job: dict[str, Any] | None = None
_refs = None
_last_tick = 0.0
_BODY = '/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Bodies/IO_VendingMachine_BlackMarket'
_TOKEN = 'IO_VendingMachine_BlackMarket'

def status():
    return dict(_job or {'running':False,'phase':'idle','message':'No machine spawn requested.'})

def is_running():
    return bool(_job and _job.get('running'))

def _finish(phase, message):
    if _job is not None:
        _job.update(running=False,phase=phase,message=message)
    try:
        from . import runtime_log
        runtime_log.note('Black market spawn: '+message)
    except Exception:
        pass

def cancel():
    if not is_running():return
    _finish('cancelled','Machine creation cancelled because the session ended.')
    _cleanup_spawner()

def _cleanup_spawner():
    if _refs:
        spawner=_refs['spawner']()
        if spawner is not None:
            try:spawner.K2_DestroyActor()
            except Exception:pass

def _number(payload,key,default,minimum,maximum):
    value=float(payload.get(key,default))
    if not math.isfinite(value) or not minimum<=value<=maximum:
        raise ValueError('Invalid machine placement '+key)
    return value

def start(payload=None):
    global _job,_refs,_last_tick
    if is_running():return dict(ok=False,message='Black market machine is already setting up; wait for its result.')
    payload=dict(payload or {})
    spawner=None
    try:
        from .embedded_oak import engine as oak
        from .embedded_bms.io_activate import oak_spawn_vending_world
        from .embedded_bms import get_controller
        from .bridge_actions_extended import _apply_bms_ui
        pc=get_pc()
        statics=unrealsdk.find_class('GameplayStatics').ClassDefaultObject
        if pc is None or not pc.HasAuthority() or str(statics.GetCurrentLevelName(pc,True))!='World_P':
            raise RuntimeError('Load into the host main Kairos world to place the Black Market machine.')
        distance=_number(payload,'spawn_distance',350,100,2000)
        z_offset=_number(payload,'spawn_z_offset',payload.get('z_offset',0),-200,500)
        scale=_number(payload,'spawn_scale',1,0.5,2)
        controller=get_controller()
        _apply_bms_ui(controller,{**payload,'spawn_anchor':payload.get('spawn_anchor','local')})
        with controller._with_spawn_anchor():
            ok,message=oak_spawn_vending_world(_TOKEN,distance=distance,z_offset=z_offset,scale=scale,activate=True)
            if ok:
                _job=dict(running=False,phase='complete',message=message)
                return dict(ok=True,message=message,spawn=status())
            if 'waiting for template' not in message:
                raise RuntimeError(message)
            # One exact body package, then one native spawner. No world scans,
            # deployment fallback, package fan-out or blocking polling.
            oak._load_one_spawn_package(_BODY)
            _pc,pawn,world,gs=oak._spawn_context()
            if _pc!=pc or pawn is None or world is None or gs is None:
                raise RuntimeError('Host spawn context changed.')
            transform=oak._spawn_transform_for_index(pawn,index=0,count=1,distance=distance,spacing=125,z_offset=z_offset,scale=scale)
            cls=unrealsdk.find_class('OakSpawner')
            spawner,_=oak._spawn_thin_air_spawner_for_fire(gs,world,cls,transform,async_mode=True)
            if spawner is None:raise RuntimeError('Could not create native machine spawner.')
            component=spawner.GetSpawnerComponent()
            oak._overdrive_spawner_component_fast(component)
            # This request owns one vending machine, never a respawning mob batch.
            for target in (component,spawner):
                for field in ('bInfinite','bUnlimitedSpawns','bAllowRespawn','bRespawnEnabled'):
                    oak._safe_set_attr(target,field,False)
                for field in ('MaxAliveActors','MaxActiveActors','MaxSpawnedActors','MaxSpawnCount','NumActorsToSpawn','SpawnCount'):
                    oak._safe_set_attr(target,field,1)
            definition=oak._spawnai_resolve_from_loaded_packages_only('io_VendingMachine_BlackMarket',(_BODY,)) or oak._make_actor_def_shell('io_VendingMachine_BlackMarket')
            if definition is None:raise RuntimeError('Native machine definition is unavailable.')
            _refs=dict(pc=WeakPointer(pc),pawn=WeakPointer(pawn),world=WeakPointer(world),spawner=WeakPointer(spawner),component=WeakPointer(component))
            _job=dict(running=True,phase='waiting',started=time.monotonic(),message='Creating Black Market machine; waiting for native activation (up to eight seconds).')
            _last_tick=0.0
            component.PushActorDef('SSP',definition,True)
            component.ResetSpawner(True)
        return dict(ok=True,message=_job['message'],spawn=status())
    except Exception as exc:
        _job=dict(running=False,phase='error',message='Black market placement failed: '+str(exc))
        if spawner is not None:
            try:spawner.K2_DestroyActor()
            except Exception:pass
        return dict(ok=False,message=_job['message'],spawn=status())

def runtime_tick():
    global _last_tick
    if not is_running():return
    now=time.monotonic()
    if now-_last_tick<0.1:return
    _last_tick=now
    try:
        from .embedded_oak import engine as oak
        from .embedded_bms.io_activate import activate_spawned_io
        from . import black_market as bm
        pc,pawn,world,_gs=oak._spawn_context()
        if pc is None or _refs['pc']() is None or pawn is None or world is None or get_pc()!=_refs['pc']() or pc!=_refs['pc']() or pawn!=_refs['pawn']() or world!=_refs['world']():
            raise RuntimeError('Host, pawn or world changed before machine placement; no replacement player was used.')
        component=_refs['component']()
        if component is None:raise RuntimeError('Machine spawner expired.')
        actors=oak._alive_actors_for_spawner_component(component)
        if actors:
            actor=actors[0]
            bm.restore_black_market_visibility(actor)
            bm.remember_placed_black_market(actor)
            ok,message=activate_spawned_io(_TOKEN,actor=actor)
            _job['machine_path']=str(actor)
            if not ok:raise RuntimeError('Machine created but activation failed: '+message)
            _finish('complete','Black Market machine placed and activated. '+message)
            return
        if now-_job['started']>8:
            raise RuntimeError('Native machine did not appear within eight seconds. No successful placement was reported.')
    except Exception as exc:
        _finish('error',str(exc))
        _cleanup_spawner()
