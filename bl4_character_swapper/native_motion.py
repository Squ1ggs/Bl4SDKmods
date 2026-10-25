"""Rig-checked local playback for captured and stock character locomotion.

The character's own animation graph plays idle, walk, and gun holds. A
matching full-body montage is added only while moving fast enough for that
rig. Replacing the graph with one clip left passive bodies in the bind pose.
This does not replicate animation to unmodified clients.
"""
from pathlib import Path
import hashlib
import json
import math
import re
import time

from .native_seating import _path, load_clip, support_config


def _instance(mesh):
    if int(mesh.GetAnimationMode()) == 1:
        getter = getattr(mesh, 'GetSingleNodeInstance', None)
        if callable(getter):
            instance = getter()
            if instance is not None: return instance
    return mesh.GetAnimInstance()


def _animation_root(value, *, airborne=False):
    if not isinstance(value,str):return False
    legacy='/Game/ImportedCharacters/NativeAmaraAirborne/' if airborne else '/Game/ImportedCharacters/NativeAmaraMotion/'
    return value==legacy or bool(re.fullmatch(r'/Game/ImportedCharacters/NativeCharacterMotion/[A-Za-z0-9_-]{1,64}/',value))


def _archives_valid(root, archives):
    if not isinstance(archives,dict) or len(archives)!=3 or {Path(name).suffix for name in archives}!={'.pak','.utoc','.ucas'}:return False
    folder=root/'assets/native_character_animations'
    return all(Path(name).name==name and (folder/name).is_file()
        and hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest for name,digest in archives.items())


def _stock_definition(mesh,state):
    try:
        from . import native_stock_motion
    except ImportError:
        return None
    return native_stock_motion.definition(mesh,state)


def definition(mesh, state):
    if 'native_motion_definition' in state:
        return state['native_motion_definition'] or _stock_definition(mesh,state)
    state['native_motion_definition'] = None
    root, rows = support_config(__file__, 'native_motion_animations.json')
    skeleton = _path(mesh.GetSkinnedAsset().Skeleton)
    for row in rows.values():
        if row.get('enabled') is not True or row.get('mesh_skeleton') != skeleton: continue
        archives = row.get('archives', {})
        if not _archives_valid(root,archives):continue
        animation_root=row.get('animation_root','/Game/ImportedCharacters/NativeAmaraMotion/')
        if not _animation_root(animation_root):continue
        clips = row.get('clips', {})
        airborne=row.get('local_airborne_motion_enabled') is True
        if set(clips) != ({'run','sprint','airborne','air_hold'} if airborne else {'run','sprint'}): continue
        if any(not clips[mode].get('animation','').startswith(animation_root)
               or '..' in clips[mode]['animation'] or not math.isfinite(float(clips[mode].get('speed_cm_s',0)))
               or float(clips[mode]['speed_cm_s']) <= 0 for mode in ('run','sprint')): continue
        if airborne:
            air_root=row.get('airborne_animation_root',animation_root)
            if not _animation_root(air_root,airborne=True) or not _archives_valid(root,row.get('airborne_archives',{})):continue
            if any(not clips[mode].get('animation','').startswith(air_root)
               or '..' in clips[mode]['animation'] or not math.isfinite(float(clips[mode].get('duration_seconds',0)))
               or float(clips[mode]['duration_seconds']) <= 0 for mode in ('airborne','air_hold')):continue
        state['native_motion_definition'] = row
        return row
    return _stock_definition(mesh,state)


def _owned(component, actor):
    return component is not None and actor is not None and str(component.GetOwner()) == str(actor)


def _suspend_leg_ik(saved):
    """The native foot targets do not accompany our captured FK leg tracks."""
    instance=saved['instance']()
    if instance is None: raise ValueError('Owned native animation instance lost')
    values=saved.setdefault('leg_ik_alphas', {})
    for name in ('GbxAnimGraphNode_LegIK', 'AnimGraphNode_LegIK'):
        node=getattr(instance,name,None)
        if node is None:continue
        if name not in values:
            values[name]={'alpha':float(node.ALPHA),
                'scale':float(node.AlphaScaleBias.scale), 'bias':float(node.AlphaScaleBias.Bias)}
        elif not isinstance(values[name],dict):
            # An already active loop can carry the earlier alpha-only snapshot.
            values[name]={'alpha':values[name],
                'scale':float(node.AlphaScaleBias.scale), 'bias':float(node.AlphaScaleBias.Bias)}
        node.ALPHA=0.
        # Exposed graph pins overwrite ALPHA each evaluation. These constant
        # scale/bias fields gate the computed alpha after that pin assignment.
        node.AlphaScaleBias.scale=0.
        node.AlphaScaleBias.Bias=0.


def _restore_leg_ik(saved):
    instance=saved['instance']()
    if instance is not None:
        for name,value in saved.get('leg_ik_alphas', {}).items():
            node=getattr(instance,name)
            if isinstance(value,dict):
                node.ALPHA=value['alpha']
                node.AlphaScaleBias.scale=value['scale']
                node.AlphaScaleBias.Bias=value['bias']
            else: node.ALPHA=value


def restore(state):
    saved = state.get('native_motion_clip')
    if saved is None: return
    if 'montage' in saved:
        instance, montage = saved['instance'](), saved['montage']()
        _restore_leg_ik(saved)
        if instance is not None and montage is not None:
            instance.Montage_Stop(.1, montage)
        state.pop('native_motion_clip', None)
        return
    mesh = saved['mesh']()
    if 'proxy' in saved:
        shell, proxy = saved['shell'](), saved['proxy']()
        if _owned(mesh, shell):
            mesh.SetVisibility(saved['visible'], False)
            mesh.SetHiddenInGame(saved['hidden'], False)
        if _owned(proxy, shell): proxy.K2_DestroyComponent(shell)
        state.pop('native_motion_clip', None)
        return
    # Cleanup remains compatible with an older direct-playback trial.
    state.pop('native_motion_clip', None)
    if mesh is None: return
    current = _instance(mesh)
    own = saved.get('instance')
    lost = current is None and int(mesh.GetAnimationMode()) == 1
    if own is not None and str(current) != str(own()) and not lost: return
    original = saved['class']() if saved['class'] else None
    if original is not None: mesh.SetAnimInstanceClass(original)
    mesh.SetAnimationMode(saved['mode'], True)


def update(state, pawn, shell, mesh, driving):
    try:
        enabled=state.get('native_motion_trial') is True
        if 'native_motion_trial' not in state:
            configured=definition(mesh,state)
            enabled=configured is not None and configured.get('local_slot_motion_enabled') is True
        if not enabled:
            restore(state); return None
        if (shell is pawn or not pawn.IsLocallyControlled() or str(getattr(shell,'Owner',None)) != str(pawn)
                or not _owned(mesh, shell)):
            restore(state); return None
        try:
            mesh.VisibilityBasedAnimTickOption = 0
            mesh.bPauseAnims = False
            mesh.SetComponentTickEnabled(True)
        except Exception:
            pass
        velocity = pawn.GetVelocity()
        speed = math.hypot(float(velocity.X), float(velocity.Y))
        state['native_motion_observation'] = {'speed_cm_s':speed,
            'mode':int(pawn.CharacterMovement.MovementMode), 'driving':bool(driving),
            'native_slot':'FullBody'}
        row = definition(mesh, state)
        if row is None or state.get('native_motion_error'):
            restore(state);return None
        state['native_motion_observation']['native_slot']=row.get('slot','FullBody')
        # Captured rigs lack grounded walking on the passive NPC graph.
        # Scale their validated run cycle at slow walking speeds too.
        minimum_speed=20.
        player_mode=int(pawn.CharacterMovement.MovementMode)
        if (driving or player_mode not in (1,3) or not math.isfinite(speed)
                or (player_mode==1 and speed < minimum_speed) or bool(getattr(pawn,'bIsCrouched',False))):
            restore(state); return None
        if player_mode==3 and row.get('local_airborne_motion_enabled') is not True:
            restore(state);return None
        saved = state.get('native_motion_clip')
        instance = mesh.GetAnimInstance()
        if saved is not None and ('montage' not in saved or str(saved['mesh']()) != str(mesh)
                or str(saved['instance']()) != str(instance)):
            restore(state)
            raise ValueError('Native render mesh or animation instance changed; trial suspended')
        if instance is None: return None
        current = instance.GetCurrentActiveMontage()
        own_montage = saved['montage']() if saved else None
        if current is not None and str(current) != str(own_montage):
            restore(state)
            state['native_motion_observation']['foreign_montage'] = str(current)
            return None
        air_started=None
        if player_mode==3:
            air_started=saved.get('air_started') if saved and saved['clip'] in ('airborne','air_hold') else None
            if air_started is None:air_started=time.monotonic()
            duration=float(row['clips']['airborne']['duration_seconds'])
            mode='air_hold' if time.monotonic()-air_started >= max(0.,duration-.15) else 'airborne'
        else:
            mode = 'sprint' if speed >= (600 if saved and saved['clip']=='sprint' else 650) else 'run'
        clip = row['clips'][mode]
        max_rate=1.5 if row.get('source')=='game_native' else 4.
        rate = 1. if player_mode==3 else max(.1,min(max_rate,speed/float(clip['speed_cm_s'])))
        if saved is None or saved['clip'] != mode or current is None:
            asset = load_clip(clip['animation'])
            if asset is None or _path(asset.Skeleton) != _path(mesh.GetSkinnedAsset().Skeleton):
                raise ValueError('Motion animation does not match the exact target skeleton')
            if saved is not None: restore(state)
            montage = instance.PlaySlotAnimationAsDynamicMontage(asset, row.get('slot','FullBody'), .1, .1, rate, 1 if mode=='airborne' else 1000000, -1., 0.)
            if isinstance(montage, tuple): montage=montage[0] if montage else None
            if montage is None: raise ValueError('Native FullBody slot did not create a motion montage')
            from unrealsdk.unreal import WeakPointer
            saved = {'mesh':WeakPointer(mesh), 'shell':WeakPointer(shell),
                'instance':WeakPointer(instance), 'montage':WeakPointer(montage), 'clip':mode}
            if air_started is not None:saved['air_started']=air_started
            state['native_motion_clip'] = saved
        _suspend_leg_ik(saved)
        instance.Montage_SetPlayRate(saved['montage'](), rate)
        state['native_motion_last_playing'] = mode
        return 'player_motion_'+mode
    except Exception as exc:
        restore(state)
        state['native_motion_error'] = str(exc)
        return None
