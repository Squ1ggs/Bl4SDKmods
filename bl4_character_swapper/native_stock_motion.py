"""Resolve per-rig locomotion from original game assets, without retarget guesses."""
from pathlib import Path
import json
import math
import re

from .native_seating import _path, support_config


def _animation_path(value):
    if not isinstance(value,str) or not re.match(r'^/Game/(?:AI/|DLC/[A-Za-z0-9_]+/AI/)',value):
        return False
    if any(part in value for part in ('..','\\','//')) or value.count('.') != 1:
        return False
    package,name=value.split('.')
    return package.rsplit('/',1)[-1]==name and all(char.isalnum() or char in '_/' for char in package)


def _graph_slot(mesh):
    instance=mesh.GetAnimInstance()
    cls=getattr(instance,'Class',None)
    if cls is None: return None
    found=set()
    for prop in cls._properties():
        name=str(prop.Name)
        if not name.startswith('AnimGraphNode_Slot'): continue
        node=getattr(instance,name,None)
        if node is not None: found.add(str(getattr(node,'SlotName','')))
    return next((name for name in ('FullBody','DefaultSlot') if name in found),None)


def definition(mesh,state):
    """Normalize an audited native run/walk into the existing owned-slot driver."""
    skeleton=_path(mesh.GetSkinnedAsset().Skeleton)
    instance=mesh.GetAnimInstance()
    cache=state.get('native_stock_motion_definition')
    if cache and cache['skeleton']==skeleton and cache['instance']==str(instance):
        return cache['row']
    _, rows = support_config(__file__, 'native_stock_motion_animations.json')
    slot=_graph_slot(mesh)
    if slot is None:
        state['native_stock_motion_unavailable']='native graph has no full-body montage slot'
        return None
    for row in rows.values():
        if (row.get('source')!='game_native' or row.get('enabled') is not True
                or row.get('local_slot_motion_enabled') is not True
                or row.get('mesh_skeleton')!=skeleton): continue
        clips={}
        for mode,clip in row.get('clips',{}).items():
            if mode not in ('walk','run','sprint'): continue
            if not isinstance(clip,dict): continue
            path=clip.get('animation')
            try: speed=float(clip.get('speed_cm_s',0))
            except (ValueError,TypeError): continue
            if not _animation_path(path) or not math.isfinite(speed) or speed<=0: continue
            # The playback driver verifies the loaded AnimSequence's exact
            # skeleton again before it can create any montage.
            clips[mode]={'animation':path,'speed_cm_s':speed}
        run=clips.get('run') or clips.get('walk') or clips.get('sprint')
        if run is None: continue
        result=dict(row,slot=slot,clips={'run':run,'sprint':clips.get('sprint') or run})
        if row.get('local_airborne_motion_enabled') is True:
            air={}
            for mode in ('airborne','air_hold'):
                clip=row.get('clips',{}).get(mode,{})
                try: duration=float(clip.get('duration_seconds',0))
                except (ValueError,TypeError): break
                if not _animation_path(clip.get('animation')) or not math.isfinite(duration) or duration<=0: break
                air[mode]={'animation':clip['animation'],'duration_seconds':duration}
            if len(air)==2: result['clips'].update(air)
            else: result['local_airborne_motion_enabled']=False
        state['native_stock_motion_definition']={'skeleton':skeleton,'instance':str(instance),'row':result}
        state.pop('native_stock_motion_unavailable',None)
        return result
    return None
