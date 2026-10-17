from contextlib import nullcontext
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]/'resources/Squ1ggsBoostingTools'
def native(monkeypatch):
    pkg=ModuleType('vendor_test');pkg.__path__=[str(ROOT)]
    monkeypatch.setitem(sys.modules,pkg.__name__,pkg)
    def stub(name,**values):
        m=ModuleType(name);m.__dict__.update(values);monkeypatch.setitem(sys.modules,name,m);return m
    pc=NS(HasAuthority=lambda:True);pawn=NS();world=NS();gs=NS()
    control=NS(now=1.,actors=[],world=world,created=0,tracked=[],loaded=[],caps=[])
    component=NS(PushActorDef=lambda *args:None,ResetSpawner=lambda *args:None)
    spawner=NS(destroyed=False,GetSpawnerComponent=lambda:component)
    spawner.K2_DestroyActor=lambda:setattr(spawner,'destroyed',True)
    statics=NS(GetCurrentLevelName=lambda *args:'World_P')
    stub('unrealsdk',find_class=lambda name:NS(ClassDefaultObject=statics))
    stub('unrealsdk.unreal',WeakPointer=lambda obj:lambda:obj)
    stub('mods_base',get_pc=lambda:pc)
    stub('vendor_test.embedded_oak')
    def create(*args,**kwargs):control.created+=1;return spawner,False
    oak=stub('vendor_test.embedded_oak.engine',
        _load_one_spawn_package=control.loaded.append,_spawn_context=lambda:(pc,pawn,control.world,gs),
        _spawn_transform_for_index=lambda *args,**kwargs:NS(),_spawn_thin_air_spawner_for_fire=create,
        _overdrive_spawner_component_fast=lambda component:None,
        _safe_set_attr=lambda obj,k,v:control.caps.append((k,v)),
        _spawnai_resolve_from_loaded_packages_only=lambda *args:object(),_make_actor_def_shell=lambda *args:object(),
        _alive_actors_for_spawner_component=lambda component:control.actors)
    stub('vendor_test.embedded_bms',get_controller=lambda:NS(_with_spawn_anchor=nullcontext))
    io=stub('vendor_test.embedded_bms.io_activate',oak_spawn_vending_world=lambda *args,**kwargs:(False,'oak_spawn waiting for template'),
            activate_spawned_io=lambda *args,**kwargs:(True,'activated'))
    stub('vendor_test.bridge_actions_extended',_apply_bms_ui=lambda *args:None)
    stub('vendor_test.black_market',restore_black_market_visibility=lambda actor:None,
        remember_placed_black_market=control.tracked.append)
    stub('vendor_test.runtime_log',note=lambda message:None)
    spec=importlib.util.spec_from_file_location('vendor_test.black_market_spawn',ROOT/'black_market_spawn.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    monkeypatch.setattr(m.time,'monotonic',lambda:control.now)
    return m,control,spawner,io

def test_missing_world_machine_creates_one_native_machine_and_verifies_later(native):
    m,c,spawner,io=native
    assert m.start({})['ok'] and m.is_running()
    assert len(c.loaded)==1 and '/Bodies/' in c.loaded[0]
    assert ('MaxAliveActors',1) in c.caps and ('bInfinite',False) in c.caps
    assert not m.start({})['ok'] and c.created==1
    c.actors=[object()];c.now+=1;m.runtime_tick()
    assert m.status()['phase']=='complete' and len(c.tracked)==1
    assert not spawner.destroyed

def test_missing_native_actor_reports_failure_and_cleans_its_spawner(native):
    m,c,spawner,io=native
    m.start({});c.now+=9;m.runtime_tick()
    assert m.status()['phase']=='error' and spawner.destroyed and not c.tracked

def test_world_change_stops_without_tracking_another_machine(native):
    m,c,spawner,io=native
    m.start({});c.now+=1;c.world=object();c.actors=[object()];m.runtime_tick()
    assert m.status()['phase']=='error' and not c.tracked and spawner.destroyed

def test_cancel_cleans_only_the_owned_spawner(native):
    m,c,spawner,io=native
    m.start({});m.cancel()
    assert m.status()['phase']=='cancelled' and spawner.destroyed

def test_existing_machine_relocates_without_creating_another(native,monkeypatch):
    m,c,spawner,io=native
    monkeypatch.setattr(io,'oak_spawn_vending_world',lambda *args,**kw:(True,'relocated'))
    assert m.start({})['ok'] and m.status()['phase']=='complete'
    assert not c.created and not c.loaded

class Patcher:
    def __init__(self):self.undo=[]
    def setitem(self,mapping,key,value):
        old=mapping.get(key,self);self.undo.append(lambda: mapping.pop(key,None) if old is self else mapping.__setitem__(key,old));mapping[key]=value
    def setattr(self,obj,key,value):
        old=getattr(obj,key);self.undo.append(lambda:setattr(obj,key,old));setattr(obj,key,value)
    def close(self):
        for fn in reversed(self.undo):fn()

import inspect
for name,fn in list(globals().items()):
    if name.startswith('test_'):
        patch=Patcher()
        try:
            fixture=native(patch)
            fn(**{key:fixture if key=='native' else patch for key in inspect.signature(fn).parameters})
            print('PASS: '+name)
        finally:patch.close()
