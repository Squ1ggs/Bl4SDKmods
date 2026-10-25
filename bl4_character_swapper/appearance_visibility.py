# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 RDPSqu1ggs
"""Reversible visibility/relevance setup for an actively worn cosmetic actor."""
from __future__ import annotations
from typing import Any
from unrealsdk.unreal import WeakPointer

def _call(obj: Any, method: str, *args: Any) -> bool:
    try:
        getattr(obj, method)(*args)
        return True
    except Exception:
        return False


def prepare_local_cosmetic_owner(state, pawn, source):
    """Establish the same owner contract for local and lobby animation drivers."""
    if source is pawn or str(source.GetAttachParentActor()) != str(pawn):
        raise RuntimeError('The cosmetic must be attached to its wearer before animation starts.')
    previous = getattr(source, 'Owner', None)
    if str(previous) == str(pawn):
        return
    state['local_cosmetic_owner'] = {
        'source': WeakPointer(source), 'pawn': WeakPointer(pawn),
        'previous': WeakPointer(previous) if previous is not None else None,
    }
    if not _call(source, 'SetOwner', pawn) or str(getattr(source, 'Owner', None)) != str(pawn):
        raise RuntimeError('The cosmetic could not establish its animation owner. Original appearance kept.')
    _match_wearer_side(source, pawn)


def restore_local_cosmetic_owner(state):
    saved = state.get('local_cosmetic_owner')
    if saved is None:
        return
    source, pawn = saved['source'](), saved['pawn']()
    if source is not None and pawn is not None and str(getattr(source, 'Owner', None)) == str(pawn):
        previous = saved['previous']() if saved['previous'] is not None else None
        if not _call(source, 'SetOwner', previous):
            raise RuntimeError('Could not restore the cosmetic animation owner.')
    state.pop('local_cosmetic_owner', None)


def _camera_anatomy(mesh):
    """Source-reviewed anatomy/accessories, keyed to the exact imported mesh."""
    try:
        asset=mesh.GetSkinnedAsset()
        getter=getattr(asset,'_path_name',None)
        if callable(getter):path=str(getter())
        else:
            text=str(asset);path=text.split("'",2)[1] if "'" in text else text
        from importlib.resources import files
        import json
        rows=json.loads(files(__package__).joinpath('data/camera_anatomy.json').read_text(encoding='utf-8'))['meshes']
        return rows.get(path,{})
    except Exception:return {}


def _mapped_camera_head(mesh):
    """Resolve explicit source anatomy, never infer a head from bone height."""
    head=_camera_anatomy(mesh).get('head')
    try:return head if head and int(mesh.GetBoneIndex(head))>=0 else None
    except Exception:return None


def _local_eye_delta(transform,offset):
    values=[float(value)*float(getattr(transform.Scale3D,axis)) for value,axis in zip(offset,'XYZ')]
    q=transform.Rotation;x,y,z,w=[float(getattr(q,axis)) for axis in 'XYZW']
    vx,vy,vz=values
    tx,ty,tz=2*(y*vz-z*vy),2*(z*vx-x*vz),2*(x*vy-y*vx)
    return [vx+w*tx+y*tz-z*ty,vy+w*ty+z*tx-x*tz,vz+w*tz+x*ty-y*tx]


def _hold_anatomical_eye(saved,camera,pawn,mesh):
    from . import native_eye_camera
    native_eye_camera.hold(saved,camera,pawn,mesh)
    diagnostics=saved.get('native_eye_camera',{})
    if diagnostics.get('error')=='No head anchor on this rig':
        head=_mapped_camera_head(mesh)
        if head is None:return
        service=native_eye_camera._service()
        if not service.installed:return
        diagnostics.update(head=head,error=None,eye_bones=False,anchor_source='explicit_source_anatomy')
        service.active={'owner':saved,'camera':WeakPointer(camera),'pawn':WeakPointer(pawn),
                        'mesh':WeakPointer(mesh),'head':head,'eye_offset':None,'diagnostics':diagnostics}
    service=native_eye_camera._service()
    active=service.active
    if active is None or active.get('owner') is not saved or diagnostics.get('mapped_eye_bones'):return
    anatomy=_camera_anatomy(mesh)
    names=anatomy.get('eye_bones',[])
    local_offset=anatomy.get('eye_local_offset')
    if not names and local_offset is None:return
    try:
        import math
        if local_offset is not None:
            delta=_local_eye_delta(mesh.GetSocketTransform(active['head'],0),local_offset)
        else:
            if any(int(mesh.GetBoneIndex(name))<0 for name in names):return
            center=mesh.GetSocketLocation(active['head'])
            eyes=[mesh.GetSocketLocation(name) for name in names]
            delta=[sum(float(getattr(eye,axis)) for eye in eyes)/len(eyes)-float(getattr(center,axis)) for axis in 'XYZ']
        if not 1<math.sqrt(sum(value*value for value in delta))<30:return
        yaw=math.radians(float(camera.GetCameraRotation().Yaw))
        active['eye_offset']=(delta[0]*math.cos(yaw)+delta[1]*math.sin(yaw),-delta[0]*math.sin(yaw)+delta[1]*math.cos(yaw),delta[2])
        diagnostics.update(eye_bones=True,mapped_eye_bones=names or ['source_eye_surface'],anchor_source='explicit_source_eyes')
    except Exception:pass


def _nonhuman_enemy_weapon_policy(state, mesh):
    """Reviewed swaps must not expose the player's unrelated weapon arms."""
    code=str(state.get('source_code',''))
    if code in ('pack:installed:cardboard_guardian','pack:installed:scrap_robot'):
        return True
    # Original imports do not populate native enemy animation-session metadata.
    # Match the actual asset exactly and use the same existing hide/restore path.
    try:
        asset=mesh.GetSkinnedAsset();getter=getattr(asset,'_path_name',None)
        if callable(getter):path=str(getter())
        else:
            text=str(asset);path=text.split("'",2)[1] if "'" in text else text
        if path in (
            '/Game/ImportedCharacters/CardboardGuardian/SK_CardboardGuardian.SK_CardboardGuardian',
            '/Game/ImportedCharacters/ScrapRobot/SK_ScrapRobot.SK_ScrapRobot',
        ):return True
    except Exception:pass
    if not code:return False
    from importlib.resources import files
    import json
    groups=globals().get('_enemy_weapon_groups')
    if groups is None:
        groups={row['code']:row['group'].upper() for row in json.loads(
            files(__package__).joinpath('data/bl4_characters.json').read_text(encoding='utf-8'))}
        globals()['_enemy_weapon_groups']=groups
    group=groups.get(code,'')
    return 'BOSS' in group or 'ENEM' in group


def suppress_cosmetic_presentation(actor, mesh=None):
    """Suppress AI gaze and non-body effects on an explicitly owned cosmetic."""
    try:
        owner=actor.GetOwner()
        if owner is None or str(owner)==str(actor) or not owner.IsPlayerControlled() or actor.IsPlayerControlled():return
        if mesh is None:
            from .native_helpers import _actor_mesh
            mesh=_actor_mesh(actor)
        instance=mesh.GetAnimInstance() if mesh is not None else None
        if instance is not None:
            for prop in instance.Class._properties():
                name=str(prop.Name)
                if not name.startswith('GbxAnimGraphNode_Rotation_AimOffset'):continue
                node=getattr(instance,name)
                channel=str(node.RotationChannelName.TagName)
                if channel not in ('RotationChannel.Head','RotationChannel.Eye'):continue
                node.ALPHA=0.
                node.AlphaScaleBias.scale=0.;node.AlphaScaleBias.Bias=0.
            if hasattr(instance,'HeadEnableAlpha'):instance.HeadEnableAlpha=0.
        import unrealsdk
        for component in actor.K2_GetComponentsByClass(unrealsdk.find_class('ActorComponent')):
            if str(component.GetOwner())!=str(actor):continue
            name=str(component.Name).lower();kind=str(component.Class.Name)
            asset=str(getattr(component,'StaticMesh',''))
            effect=kind in ('NiagaraComponent','ParticleSystemComponent','DecalComponent','WidgetComponent','PointLightComponent','SpotLightComponent')
            collision_proxy=('Collision_' in asset or name=='collisionbubble') and kind=='StaticMeshComponent'
            if not (effect or collision_proxy):continue
            _call(component,'Deactivate');_call(component,'SetComponentTickEnabled',False)
            _call(component,'SetVisibility',False,False);_call(component,'SetHiddenInGame',True,False)
            if collision_proxy:
                _call(component,'SetRenderInMainPass',False);_call(component,'SetRenderInDepthPass',False)
                _call(component,'SetCastShadow',False)
    except Exception:pass


def _restore_unsupported_weapon(saved):
    record=saved.pop('unsupported_fp_weapon',None) if saved else None
    if not record:return
    for part in record:
        component=part['component']()
        if component is None:continue
        _call(component,'SetVisibility',part['visible'],False)
        _call(component,'SetHiddenInGame',part['hidden'],False)
        if part.get('tick') is not None:component.VisibilityBasedAnimTickOption=part['tick']


def _hide_unsupported_weapon(saved,camera,pawn):
    native=camera.CameraModeState.Inputs.AttachComponent
    if native is None or str(native.GetOwner())!=str(pawn) or str(native.Name)!='FirstPersonArms':return
    record=saved.setdefault('unsupported_fp_weapon',[])
    known={str(part['component']()) for part in record}
    seen=set()
    def visit(component,depth=0):
        if component is None or depth>6 or str(component) in seen:return
        seen.add(str(component))
        if str(component) not in known:
            record.append({'component':WeakPointer(component),'visible':bool(component.bVisible),'hidden':bool(component.bHiddenInGame),'tick':getattr(component,'VisibilityBasedAnimTickOption',None)})
            known.add(str(component))
        if hasattr(component,'VisibilityBasedAnimTickOption'):component.VisibilityBasedAnimTickOption=0
        _call(component,'SetVisibility',False,False)
        _call(component,'SetHiddenInGame',True,False)
        for child in list(getattr(component,'AttachChildren',()) or ()):visit(child,depth+1)
    visit(native)


def _release_viewmodel_alignment(saved):
    record=saved.pop('viewmodel_alignment',None) if saved else None
    if not record:return
    try:
        from . import native_eye_camera
        active=native_eye_camera._service().active
        if active is not None and active.get('owner') is saved and record.get('source_provider'):
            active['mesh']=record['source_provider']
    except (ImportError,AttributeError):pass
    native=record['native']()
    if native is not None:
        import unrealsdk
        position=unrealsdk.make_struct('Vector',**dict(zip('XYZ',record['relative'])))
        native.K2_SetRelativeLocation(NewLocation=position,bSweep=False,SweepHitResult=unrealsdk.make_struct('HitResult'),bTeleport=False)


def _hold_native_viewmodel(saved,camera,pawn,offset=(0.,0.,0.)):
    """Keep the native gun rig at the corrected eye; do not move the camera."""
    from . import native_eye_camera
    from types import SimpleNamespace
    import math
    import unrealsdk
    service=native_eye_camera._service();active=service.active
    if active is None or active.get('owner') is not saved:return False
    if saved.get('viewmodel_alignment'):
        saved['viewmodel_alignment']['offset']=offset
        active['mesh']=saved['viewmodel_alignment'].setdefault('provider',active['mesh'])
        return True
    native=camera.CameraModeState.Inputs.AttachComponent
    if native is None or str(native.GetOwner())!=str(pawn) or str(native.Name)!='FirstPersonArms':return False
    original=active['mesh'];native_ref=WeakPointer(native);camera_ref=WeakPointer(camera)
    record={'native':native_ref,'relative':tuple(float(getattr(native.RelativeLocation,axis)) for axis in 'XYZ'),'offset':offset,'source_provider':original}
    def socket_location(bone):
        source=original();rig=native_ref();manager=camera_ref()
        if source is None or rig is None or manager is None:raise RuntimeError('Viewmodel alignment target expired')
        point=source.GetSocketLocation(bone)
        yaw=float(manager.CameraCachePrivate.POV.Rotation.Yaw)
        desired=native_eye_camera.eye_position([float(getattr(point,axis)) for axis in 'XYZ'],yaw,active.get('eye_offset'))
        forward,side,height=record['offset']
        angle=math.radians(yaw)
        desired=(desired[0]+forward*math.cos(angle)-side*math.sin(angle),desired[1]+forward*math.sin(angle)+side*math.cos(angle),desired[2]+height)
        origin=rig.GetSocketLocation('Camera')
        delta=[value-float(getattr(origin,axis)) for value,axis in zip(desired,'XYZ')]
        if all(math.isfinite(value) for value in delta) and math.sqrt(sum(value*value for value in delta))<150:
            if max(abs(value) for value in delta)>.01:
                current=rig.K2_GetComponentLocation()
                position=unrealsdk.make_struct('Vector',**{axis:float(getattr(current,axis))+value for axis,value in zip('XYZ',delta)})
                rig.K2_SetWorldLocation(NewLocation=position,bSweep=False,SweepHitResult=unrealsdk.make_struct('HitResult'),bTeleport=False)
            record['last_delta_cm']=delta
            active['diagnostics']['viewmodel_alignment_delta_cm']=delta
        return point
    proxy=SimpleNamespace(GetSocketLocation=socket_location)
    record['provider']=lambda:proxy if original() is not None and native_ref() is not None else None
    active['mesh']=record['provider']
    saved['viewmodel_alignment']=record
    return True


def _reflected_properties(bound):
    func = getattr(bound, 'func', None)
    props = getattr(func, '_properties', None)
    if not callable(props):
        return []
    try:
        return list(props())
    except Exception:
        return []


def _property_name(prop):
    name = getattr(prop, 'Name', None)
    if name:
        return str(name)
    text = str(prop)
    return text.rsplit(':', 1)[-1].strip("'")


def _slot_weapons(actor):
    found = []
    active = getattr(actor, 'ActiveWeapons', None)
    for slot in list(getattr(active, 'Slots', None) or ()):
        weapon = getattr(slot, 'Weapon', None)
        if weapon is not None:
            found.append(weapon)
    equipped = getattr(actor, 'EquippedInventorySlots', None)
    for item in list(getattr(equipped, 'items', None) or ()):
        weapon = getattr(item, 'InstancedInventory', None)
        if weapon is not None:
            found.append(weapon)
    return found


def _same_actor(left, right):
    return left is not None and right is not None and str(left) == str(right)


def _weapon_owner(weapon):
    try:
        return weapon.GetOwner()
    except Exception:
        return getattr(weapon, 'Owner', None)


def player_gameplay_weapon_ids(player):
    """Identities of the wearer's own equipped guns. Never a destruction list."""
    if player is None:
        return set()
    return {str(weapon) for weapon in _slot_weapons(player)}


def player_has_gameplay_weapon(player):
    return bool(player_gameplay_weapon_ids(player))


def cosmetic_owned_gameplay_weapons(actor, player=None):
    """Guns on this cosmetic whose user, owner, or instigator is the cosmetic.

    A weapon object that belongs to the player is never returned, even when it
    also appears in a cosmetic slot.
    """
    if actor is None:
        return []
    player_ids = player_gameplay_weapon_ids(player)
    found = []
    seen = set()
    for weapon in _slot_weapons(actor):
        identity = str(weapon)
        if not identity or identity in seen or identity in player_ids:
            continue
        seen.add(identity)
        found.append(weapon)
    return found


def _empty_weapon_parameter(bound):
    """One reflected weapon object argument can be cleared with None."""
    if not callable(bound):
        return None
    props = _reflected_properties(bound)
    if len(props) != 1:
        return None
    text = str(props[0]).lower()
    name = _property_name(props[0])
    if any(token in text for token in ('intproperty', 'boolproperty', 'nameproperty', 'floatproperty', 'byteproperty', 'structproperty')):
        return None
    if 'weapon' not in name.lower() and 'weapon' not in text:
        return None
    return name


def _zero_arg_destroy(weapon):
    for name in ('GbxDestroyActor', 'K2_DestroyActor'):
        method = getattr(weapon, name, None)
        if not callable(method) or _reflected_properties(method):
            continue
        try:
            method()
            return name
        except Exception:
            continue
    return None


def release_cosmetic_gameplay_weapons(actor, player=None):
    """Drop gameplay guns owned by the cosmetic. The player's gun stays."""
    if actor is None:
        return {'removed': [], 'remaining': []}
    if player is None:
        try:
            player = actor.GetOwner()
        except Exception:
            player = getattr(actor, 'Owner', None)
        if player is None or _same_actor(player, actor):
            player = None
    owned = cosmetic_owned_gameplay_weapons(actor, player)
    if not owned:
        return {'removed': [], 'remaining': []}
    parameter = _empty_weapon_parameter(getattr(actor, 'ServerSetCurrentWeapon', None))
    if parameter is not None:
        try:
            actor.ServerSetCurrentWeapon(**{parameter: None})
        except Exception:
            pass
    removed = []
    for weapon in owned:
        identity = str(weapon)
        if identity in player_gameplay_weapon_ids(player):
            continue
        try:
            if bool(weapon.IsActorBeingDestroyed()):
                continue
        except Exception:
            pass
        still_cosmetic = identity in {str(item) for item in cosmetic_owned_gameplay_weapons(actor, player)}
        still_owned = any(_same_actor(ref, actor) for ref in (
            getattr(weapon, 'WeaponUser', None), _weapon_owner(weapon), getattr(weapon, 'Instigator', None)))
        if not still_cosmetic and not still_owned:
            continue
        if _zero_arg_destroy(weapon):
            removed.append(identity)
    remaining = [str(weapon) for weapon in cosmetic_owned_gameplay_weapons(actor, player)]
    return {'removed': removed, 'remaining': remaining}


def gun_hold_scalars_active(*, player_has_weapon, cosmetic_armed, hide_unsupported, weapon_preview_enabled):
    """Player-driven hold/aim only for rigs that already have gun poses."""
    return bool(weapon_preview_enabled and player_has_weapon and not cosmetic_armed and not hide_unsupported)


def _read_attr(obj, name):
    if obj is None:
        return None
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _side_sources(owner):
    """Read the wearer's side from the pawn, its player state, and team components."""
    sources = []
    if owner is None:
        return sources
    sources.append(owner)
    for name in ('Controller', 'PlayerState'):
        extra = _read_attr(owner, name)
        if extra is not None and extra not in sources:
            sources.append(extra)
    getter = _read_attr(owner, 'K2_GetComponentsByClass')
    if not callable(getter):
        return sources
    try:
        import unrealsdk
        cls = unrealsdk.find_class('ActorComponent')
        if cls is None:
            return sources
        parts = list(getter(cls) or ())[:48]
    except Exception:
        return sources
    for component in parts:
        kind = str(_read_attr(_read_attr(component, 'Class'), 'Name') or '').lower()
        if any(token in kind for token in ('team', 'faction', 'allegiance')):
            sources.append(component)
    return sources


def _is_player_controlled(actor):
    try:
        return actor is not None and bool(actor.IsPlayerControlled())
    except Exception:
        return False


_TEAM_SHAPE = {}
_TEAM_COPIED = set()
_ALLY_AIM_RELEASED = set()


def _gbx_team_library():
    """Gbx team calls live on the function library, not on OakCharacter."""
    try:
        import unrealsdk
    except Exception:
        return None
    for name in ('GbxTeamFunctionLibrary', 'GbxTeam'):
        try:
            cls = unrealsdk.find_class(name)
        except Exception:
            cls = None
        library = getattr(cls, 'ClassDefaultObject', None) if cls is not None else None
        if callable(_read_attr(library, 'SetTeam')) or callable(_read_attr(library, 'SetTeamID')):
            return library
    return None


def _call_shapes(library, name, shapes):
    fn = _read_attr(library, name)
    if not callable(fn) or not shapes:
        return None
    key = (name, tuple(len(shape) for shape in shapes))
    saved = _TEAM_SHAPE.get(key)
    order = list(range(len(shapes)))
    if isinstance(saved, int) and saved < len(shapes):
        order = [saved] + [index for index in order if index != saved]
    for index in order:
        try:
            value = fn(*shapes[index])
        except Exception:
            continue
        if name.startswith('Get') and value is None:
            continue
        _TEAM_SHAPE[key] = index
        return value if name.startswith('Get') else True
    return None


def _copy_gbx_team(actor, owner):
    """Put this shell on the wearer's Gbx team. Never write the wearer."""
    library = _gbx_team_library()
    if library is None:
        return []
    applied = []
    team = _call_shapes(library, 'GetTeam', [(owner,)])
    if team is None:
        team = _call_shapes(library, 'GetTeamFromActorDef', [(owner,)])
    shapes = [(actor, team)] if team is not None else []
    shapes.append((actor, owner))
    if _call_shapes(library, 'SetTeam', shapes):
        applied.append('SetTeam')
    team_id = _call_shapes(library, 'GetTeamID', [(owner,)])
    if team_id is not None and _call_shapes(library, 'SetTeamID', [(actor, team_id)]):
        applied.append('SetTeamID')
    if applied:
        _TEAM_COPIED.add(str(actor))
    return applied


def _release_friendly_aim(actor, wearer):
    """Friendlies that already aimed at the worn body drop that target once."""
    if wearer is None or str(actor) not in _TEAM_COPIED or str(actor) in _ALLY_AIM_RELEASED:
        return
    library = _gbx_team_library()
    if library is None:
        return
    wearer_team = _call_shapes(library, 'GetTeam', [(wearer,)])
    friendly = _call_shapes(library, 'GetAttitudeTowards', [(wearer, wearer), (wearer, wearer)])
    try:
        import unrealsdk
        pawns = list(unrealsdk.find_all('OakCharacter', False) or ())[:800]
    except Exception:
        return
    for pawn in pawns:
        if pawn is None or str(pawn) in (str(actor), str(wearer)) or _is_player_controlled(pawn):
            continue
        try:
            if float(pawn.GetDistanceTo(wearer)) > 8000:
                continue
        except Exception:
            continue
        same_team = False
        pawn_team = _call_shapes(library, 'GetTeam', [(pawn,)])
        if wearer_team is not None and pawn_team is not None and str(pawn_team) == str(wearer_team):
            same_team = True
        if not same_team and friendly is not None:
            attitude = _call_shapes(library, 'GetAttitudeTowards', [(wearer, pawn), (pawn, wearer)])
            same_team = attitude == friendly
        if not same_team:
            continue
        controller = _read_attr(pawn, 'Controller')
        _call(pawn, 'ForgetTarget', actor)
        _call(controller, 'ForgetTarget', actor)
        for obj in (pawn, controller):
            for field in ('TargetActor', 'CombatTarget', 'CurrentTarget', 'FocusActor'):
                current = _read_attr(obj, field)
                if current is not None and str(current) == str(actor):
                    _call(obj, 'ClearFocus', actor)
                    try:
                        setattr(obj, field, None)
                    except Exception:
                        pass
    _ALLY_AIM_RELEASED.add(str(actor))


def _match_wearer_side(actor, owner):
    """The cosmetic uses the wearer's side. The wearer is never rewritten."""
    if owner is None or actor is None or owner is actor or _is_player_controlled(actor):
        return
    sources = _side_sources(owner)
    targets = [actor]
    controller = _read_attr(actor, 'Controller')
    if controller is not None and not _is_player_controlled(controller):
        targets.append(controller)
    applied = []
    names = ('TeamId', 'TeamIndex', 'TeamHandle', 'GroupTeamHandle', 'Team', 'GenericTeamId', 'Allegiance', 'TeamDef', 'Faction')
    for target in targets:
        for name in names:
            value = next((found for source in sources if (found := _read_attr(source, name)) is not None), None)
            if value is None:
                continue
            setter = _read_attr(target, 'Set' + name)
            if callable(setter):
                try:
                    setter(value)
                    applied.append('Set' + name)
                except Exception:
                    pass
            if hasattr(target, name):
                try:
                    setattr(target, name, value)
                    applied.append(name)
                except Exception:
                    pass
        for source in sources:
            for getter_name, setter_name in (
                    ('GetTeam', 'SetTeam'),
                    ('GetGenericTeamId', 'SetGenericTeamId'),
                    ('GetCharacterArmy', 'SetCharacterArmy'),
                    ('GetCharacterClan', 'SetCharacterClan'),
                    ('GetCharacterEnemyType', 'SetCharacterEnemyType'),
                    ('GetTeamId', 'SetTeamId'),
                    ('GetTeamHandle', 'SetTeamHandle'),
                    ('GetGroupTeamHandle', 'SetGroupTeamHandle')):
                getter = _read_attr(source, getter_name)
                setter = _read_attr(target, setter_name)
                if not callable(getter) or not callable(setter):
                    continue
                try:
                    value = getter()
                except Exception:
                    continue
                if value is None:
                    continue
                try:
                    setter(value)
                    applied.append(setter_name)
                except Exception:
                    pass
            # These attitude calls are not on OakCharacter. The Gbx team
            # library below is what friendly AI actually checks.
            _call(target, 'SetTeamAttitudeTowards', source, 0)
            _call(target, 'SetAttitudeTowards', source, 0)
        applied.extend(_copy_gbx_team(target, owner))
    seen = globals().setdefault('_side_copy_logged', set())
    key = str(actor)
    if key not in seen:
        seen.add(key)
        try:
            import unrealsdk
            unrealsdk.logging.info('[Squ1ggs Appearance] cosmetic side ' + (', '.join(dict.fromkeys(applied)) or 'unchanged'))
        except Exception:
            pass
    for field, value in (
            ('bWantsCombat', False), ('bInCombat', False), ('bIsInCombat', False),
            ('bAlwaysAwareInThreatArea', False), ('bCanAttack', False),
            ('bAggressiveAI', False), ('bPassiveAI', True)):
        if hasattr(actor, field):
            try:
                setattr(actor, field, value)
            except Exception:
                pass
    instigator = _read_attr(actor, 'Instigator')
    if _is_player_controlled(instigator) or any(instigator is not None and str(instigator) == str(source) for source in sources):
        try:
            actor.Instigator = None
        except Exception:
            pass
        _call(actor, 'SetInstigator', None)


def _wearer_of(actor, wearer=None):
    if _is_player_controlled(wearer):
        return wearer
    owner = _read_attr(actor, 'GetOwner')
    owner = owner() if callable(owner) else owner
    if _is_player_controlled(owner):
        return owner
    try:
        parent = actor.GetAttachParentActor()
    except Exception:
        parent = None
    if _is_player_controlled(parent):
        return parent
    return wearer


def make_cosmetic_combat_passive(actor, *, trusted_cosmetic=False, wearer=None):
    """Disable combat only on a cosmetic owned by and distinct from its player."""
    if actor is None:return
    try:
        owner=actor.GetOwner()
        if str(owner)==str(actor):return
        if not trusted_cosmetic and not _is_player_controlled(owner) and not _is_player_controlled(wearer):return
        if _is_player_controlled(actor):return
    except Exception:return
    try:actor.bCanBeDamaged=False
    except Exception:pass

    # Share the wearer's Gbx team. Do not mark the body untargetable: allies
    # that cannot target the boss retarget the wearer and shoot them.
    side = _wearer_of(actor, wearer)
    _match_wearer_side(actor, side)
    getter = _read_attr(actor, 'GetAttachedActors')
    if callable(getter):
        try:
            children = list(getter() or ())
        except Exception:
            children = []
        for child in children[:16]:
            if child is None or child is actor or _is_player_controlled(child):
                continue
            _match_wearer_side(child, side)
    _release_friendly_aim(actor, side)

    suppress_cosmetic_presentation(actor)
    # Same per-actor attributes used by the existing damage adapter. Zero only
    # this cosmetic's output; the real player's native weapon damage is intact.
    causer=getattr(actor,'DamageCauserData',None)
    for field in ('DamageDealtMultiplier','RadiusDamage_DamageMultiplier','EnemyReflectionChance'):
        attribute=getattr(causer,field,None)
        for value in ('Value','BaseValue'):
            if hasattr(attribute,value):
                try:setattr(attribute,value,0.)
                except Exception:pass
    _call(actor,'SetActorEnableCollision',False)
    controller=getattr(actor,'Controller',None)
    _call(getattr(controller,'BrainComponent',None),'StopLogic','Cosmetic appearance')
    _call(controller,'StopMovement')
    _call(controller,'SetActorTickEnabled',False)
    _call(controller,'UnPossess')
    try:actor.AutoPossessAI=0
    except Exception:pass
    # Native signed override: -1 follows the NPC definition; 0 forces it off.
    # Notify the local UI as well as setting the replicated property.
    try:
        if int(actor.bUseOverheadNameplateOverride)!=0:
            actor.bUseOverheadNameplateOverride=0
            _call(actor,'OnRep_UseOverheadNameplateOverride')
    except Exception:pass
    import unrealsdk
    for kind in ('GbxAIHeldExplosiveComponent','GbxAIHeldMeleeComponent'):
        try:
            cls=unrealsdk.find_class(kind)
            if cls is None:continue
            for component in actor.K2_GetComponentsByClass(cls):
                if str(component.GetOwner())!=str(actor):continue
                _call(component,'Deactivate')
                _call(component,'SetComponentTickEnabled',False)
                _call(component,'SetCollisionEnabled',0)
                try:component.bAutoActivate=False
                except Exception:pass
        except Exception:continue
    # Boss abilities may live outside the two held-attack component classes.
    # Only inspect components owned by this explicit cosmetic, never the player.
    try:
        cls=unrealsdk.find_class('ActorComponent')
        for component in actor.K2_GetComponentsByClass(cls):
            if str(component.GetOwner())!=str(actor):continue
            name=str(getattr(getattr(component,'Class',None),'Name','')).lower()
            if any(token in name for token in ('skeletal', 'anim', 'mesh')):continue
            if not any(token in name for token in ('ability','combat','damage','gbxai','perception','target','threat','aggro','sense','stimulus','hate','script','brain','force','pull','attract','grapple','vacuum','hover')):continue
            _call(component,'UnregisterFromPerceptionSystem')
            _call(component,'Deactivate')
            _call(component,'SetComponentTickEnabled',False)
            _call(component,'SetCollisionEnabled',0)
            _call(component,'CancelAllAbilities')
            try:component.bAutoActivate=False
            except Exception:pass
    except Exception:pass
    # The passive flags above leave a real OakWeapon in this actor's slots.
    # Remove that gameplay object. The wearer's own gun is a different object.
    try:release_cosmetic_gameplay_weapons(actor)
    except Exception:pass
    _make_shell_intangible(actor)


def _make_shell_intangible(actor, *, depth=0):
    """The worn body clips through the wearer and the ground. It never moves them."""
    try:
        if actor is None or bool(actor.IsPlayerControlled()):
            return
    except Exception:
        if actor is None:
            return
    _call(actor, 'SetActorEnableCollision', False)
    movement = getattr(actor, 'CharacterMovement', None)
    _call(movement, 'StopMovementImmediately')
    _call(movement, 'DisableMovement')
    _call(movement, 'SetComponentTickEnabled', False)
    try:
        movement.bEnablePhysicsInteraction = False
    except Exception:
        pass
    parts = []
    capsule = getattr(actor, 'CapsuleComponent', None)
    if capsule is not None:
        parts.append(capsule)
    try:
        import unrealsdk
        parts.extend(list(actor.K2_GetComponentsByClass(unrealsdk.find_class('PrimitiveComponent')) or ()))
    except Exception:
        pass
    seen = set()
    for part in parts:
        if part is None:
            continue
        key = str(part)
        if key in seen:
            continue
        seen.add(key)
        try:
            owner = part.GetOwner()
            if owner is not None and str(owner) != str(actor):
                continue
        except Exception:
            continue
        _call(part, 'SetSimulatePhysics', False)
        _call(part, 'SetGenerateOverlapEvents', False)
        _call(part, 'SetCollisionResponseToAllChannels', 0)
        _call(part, 'SetCollisionEnabled', 0)
        try:
            part.CanCharacterStepUpOn = 0
        except Exception:
            pass
    if depth > 0:
        return
    getter = getattr(actor, 'GetAttachedActors', None)
    if not callable(getter):
        return
    try:
        children = list(getter() or ())
    except Exception:
        children = []
    for child in children[:16]:
        if child is None or child is actor:
            continue
        _make_shell_intangible(child, depth=1)


def _sync_native_nav_intent(state, movement, velocity):
    """Supply animation request caches without enabling movement simulation."""
    import unrealsdk
    enabled = velocity is not None and state.get('native_nav_intent_trial') is True
    saved = state.get('native_nav_intent')
    names = ('RequestedVelocity', 'LastUpdateRequestedVelocity', 'LastUpdateVelocity')
    if not enabled:
        saved = state.pop('native_nav_intent', None)
        if saved is None: return
        target = saved['movement']()
        if target is None: return
        for name, values in saved['vectors'].items():
            setattr(target,name,unrealsdk.make_struct('Vector',**dict(zip('XYZ',values))))
        target.bHasRequestedVelocity = saved['has_request']
        return
    if saved is None:
        saved = {'movement':WeakPointer(movement), 'vectors':{
            name:tuple(float(getattr(getattr(movement,name),axis)) for axis in 'XYZ')
            for name in names}, 'has_request':movement.bHasRequestedVelocity}
        state['native_nav_intent'] = saved
    if str(saved['movement']()) != str(movement): return
    for name in names:
        setattr(movement,name,velocity)
    movement.bHasRequestedVelocity = sum(float(getattr(velocity,axis))**2 for axis in 'XYZ') > 4.0


def _sync_native_ground_contact(state, movement, player_movement):
    """Mirror measured ground contact for a cosmetic with simulation disabled."""
    import copy
    enabled = player_movement is not None and state.get('native_ground_contact_trial') is True
    saved = state.get('native_ground_contact')
    if not enabled:
        saved = state.pop('native_ground_contact',None)
        if saved is not None:
            target = saved['movement']()
            if target is not None: target.CurrentFloor = saved['floor']
        return
    if saved is None:
        saved = {'movement':WeakPointer(movement),'floor':copy.copy(movement.CurrentFloor)}
        state['native_ground_contact'] = saved
    if str(saved['movement']()) == str(movement):
        movement.CurrentFloor = copy.copy(player_movement.CurrentFloor)


def _sync_native_movement_input(state, movement, source, velocity):
    """Use the native nav input override, never offsets or simulation ticks."""
    import copy
    import math
    import unrealsdk
    saved = state.get('native_movement_input')
    if velocity is None or state.get('native_movement_input_trial') is not True:
        saved = state.pop('native_movement_input',None)
        if saved is not None:
            actor = saved['source']()
            if actor is not None:
                actor.ControlInputVector = saved['pending']
                actor.LastControlInputVector = saved['last']
        return
    if saved is None:
        saved = {'source':WeakPointer(source),'pending':copy.copy(source.ControlInputVector),
                 'last':copy.copy(source.LastControlInputVector)}
        state['native_movement_input'] = saved
    if str(saved['source']()) != str(source): return
    speed = math.hypot(float(velocity.X),float(velocity.Y))
    if not math.isfinite(speed): return
    direction = unrealsdk.make_struct('Vector',X=float(velocity.X)/speed if speed>2. else 0.,
        Y=float(velocity.Y)/speed if speed>2. else 0.,Z=0.)
    # Consume the previous Pawn input before forwarding. The Gbx override also
    # writes a separate native navigation buffer; direct field writes miss it.
    movement.ConsumeInputVector()
    movement.AddInputVector(direction,True)



def prepare_original_body_visibility(state, pawn, components):
    """Enable SceneComponent visibility replication, without changing its transform."""
    if pawn is None or not pawn.HasAuthority(): return False
    saved = state.setdefault('original_body_visibility',{})
    for component in components:
        if (component is None or str(getattr(component,'Name','')) == 'FirstPersonArms'
                or 'SQBT_LocalWeaponArms' in [str(tag) for tag in (getattr(component,'ComponentTags',()) or ())]): continue
        if str(component.GetOwner()) != str(pawn) or str(component) == str(getattr(pawn,'RootComponent',None)):
            return False
        key = str(component)
        if key not in saved:
            saved[key] = {'component':WeakPointer(component),'replicates':bool(component.bReplicates)}
        if not component.bReplicates:
            if not _call(component,'SetIsReplicated',True) or not component.bReplicates: return False
            _call(pawn,'ForceNetUpdate')
    return bool(saved)


def restore_native_animation_cache(state, source, movement):
    """Release native graph updates before another driver creates its instance."""
    saved = state.get('lobby_visibility', {})
    if 'root_motion_translation_scale' not in saved:
        return
    reference = saved.get('actor')
    if reference is not None and str(reference()) != str(source):
        raise ValueError('Native animation cache belongs to another cosmetic')
    source.SetActorTickEnabled(False)
    source.AnimRootMotionTranslationScale = saved['root_motion_translation_scale']
    previous = saved.get('cached_animation_instance')
    movement.CachedAnimInstance = previous() if previous is not None else None
    if 'cached_nav_route' in saved:
        movement.ReplicatedNavType = saved['cached_nav_route']
        movement.OnRep_NavType()
        movement.SetComponentTickEnabled(False)
        source.ForceNetUpdate()
    source.SetActorTickEnabled(saved['actor_tick_enabled'])
    for key in ('root_motion_translation_scale', 'actor_tick_enabled',
                'cached_animation_instance', 'cached_nav_route'):
        saved.pop(key, None)
    state.pop('native_cache_waiting_for_instance', None)


def prepare_lobby_visibility(state: dict[str, Any]) -> bool:
    state.pop('lobby_visibility_error',None)
    state['lobby_visibility_stage'] = 'source visibility'
    source, mesh = state.get("shell"), state.get("render_mesh")
    if source is None or mesh is None:
        return False

    try:
        if not source.HasAuthority() or bool(source.bHidden):
            return False
        motion_proxy_visible = False
        if bool(mesh.bHiddenInGame):
            motion = state.get('native_motion_clip', {})
            proxy = motion['proxy']() if motion.get('proxy') else None
            original = motion['mesh']() if motion.get('mesh') else None
            parent = mesh.GetAttachParent() if proxy is not None else None
            if (motion.get('proxy_visible') is not True or proxy is None or original is None or str(original) != str(mesh)
                    or str(proxy.GetOwner()) != str(source) or parent is None
                    or str(proxy.GetAttachParent()) != str(parent)
                    or str(proxy.GetSkinnedAsset()) != str(mesh.GetSkinnedAsset())
                    or not bool(proxy.bVisible) or bool(proxy.bHiddenInGame)
                    or int(proxy.GetNumBones()) <= 0):
                return False
            motion_proxy_visible = True
        saved = state.get("lobby_visibility")
        if saved is None:
            saved = {"actor": WeakPointer(source), "mesh": WeakPointer(mesh),
                     "actor_flags": {name: bool(getattr(source, name)) for name in
                                     ("bReplicates", "bReplicateMovement", "bAlwaysRelevant", "bOnlyRelevantToOwner")},
                     "mesh_flags": {name: bool(getattr(mesh, name)) for name in ("bOwnerNoSee", "bOnlyOwnerSee")}}
            pawn = state.get('pawn')
            if pawn is not None:
                owner = getattr(source, 'Owner', None)
                saved['owner'] = WeakPointer(owner) if owner is not None else None
                saved['owner_saved'] = True
            state["lobby_visibility"] = saved
        # These changes apply only to the currently worn source actor.
        if not source.bReplicates and not _call(source, "SetReplicates", True):
            return False
        # The replicated root carries attachment transforms. Separate actor
        # velocity replication would predict an independent walk on clients.
        replicate_velocity = state.get('network_follow_trial') is True
        if bool(source.bReplicateMovement) != replicate_velocity and not _call(source, "SetReplicateMovement", replicate_velocity):
            return False
        state['lobby_visibility_stage'] = 'cosmetic ownership'
        pawn = state.get('pawn')
        if pawn is not None:
            parent = getattr(source, 'GetAttachParentActor', None)
            follow = callable(parent) and parent() is None and state.get('network_follow_trial') is True and str(getattr(source,'Owner',None)) == str(pawn)
            if not callable(parent) or (str(parent()) != str(pawn) and not follow):
                return False
            if str(getattr(source, 'Owner', None)) != str(pawn) and not _call(source, 'SetOwner', pawn):
                return False
            if str(getattr(source, 'Owner', None)) != str(pawn):
                return False
        root = getattr(source, 'RootComponent', None)
        if root is not None:
            if 'root' not in saved:
                saved['root'] = WeakPointer(root)
                saved['root_flags'] = {name: bool(value) for name in
                    ('bReplicates', 'bAbsoluteLocation', 'bAbsoluteRotation', 'bAbsoluteScale')
                    if (value := getattr(root, name, None)) is not None}
            # This component belongs only to the cosmetic; never modify the
            # player's root or physics. Relative transforms follow attachment.
            _call(root, 'SetAbsolute', False, False, False)
            _call(root, 'SetIsReplicated', True)
        source.bAlwaysRelevant = True
        source.bOnlyRelevantToOwner = False
        if state.get('player_stance_trial') is True:
            pawn = state.get('pawn')
            if pawn is None: return False
            original = source.ReplicatedStance.stance
            if 'stance_name' not in saved:
                saved['stance_name'] = str(getattr(original,'_name','') or getattr(original,'_experimental_name',''))
                if not saved['stance_name']: return False
            desired = pawn.ReplicatedStance.stance
            if str(original) != str(desired):
                source.ReplicatedStance.stance = desired
                _call(source,'OnRep_Stance')
                _call(source,'ForceNetUpdate')
        elif saved.get('stance_name'):
            from unrealsdk.unreal import FGbxDefPtr
            source.ReplicatedStance.stance = FGbxDefPtr(saved.pop('stance_name'),type='GbxStanceDef')
            _call(source,'OnRep_Stance')
            _call(source,'ForceNetUpdate')
        movement = getattr(source,'CharacterMovement',None)
        state['lobby_visibility_stage'] = 'movement replication'
        if movement is not None:
            if 'movement' not in saved:
                saved['movement'] = WeakPointer(movement)
                saved['movement_active'] = bool(movement.IsActive())
                saved['movement_replicates'] = bool(movement.bReplicates)
            attached_motion = (bool(state.get('native_attached_driver'))
                or state.get('native_frame_driver',{}).get('phase') == 'active') and not state.get('native_seat_clip')
            active_motion = not state.get('native_motion_clip') and (attached_motion or (state.get('network_follow_trial') is True and state.get('active_native_motion_trial') is True))
            changed = not bool(movement.bReplicates) or bool(movement.IsActive()) != active_motion
            if not movement.bReplicates and not _call(movement,'SetIsReplicated',True): return False
            if active_motion:
                if not movement.IsActive() and not _call(movement,'Activate',False): return False
                if not _call(movement,'SetComponentTickEnabled',attached_motion): return False
                if bool(movement.IsComponentTickEnabled()) != attached_motion: return False
            elif movement.IsActive() and not _call(movement,'Deactivate'): return False
            if bool(movement.IsActive()) != active_motion or not movement.bReplicates: return False
            cache_tick = (state.get('network_follow_trial') is True
                          and state.get('native_actor_cache_trial') is True and active_motion
                          and not state.get('native_seat_clip') and not state.get('native_motion_clip'))
            if cache_tick:
                if 'root_motion_translation_scale' not in saved:
                    saved['root_motion_translation_scale'] = float(source.AnimRootMotionTranslationScale)
                    saved['actor_tick_enabled'] = bool(source.IsActorTickEnabled())
                source.AnimRootMotionTranslationScale = 0.0
                if float(source.GetAnimRootMotionTranslationScale()) != 0.0: return False
                if not _call(source,'SetActorTickEnabled',True): return False
                # EGbxNavCharacterType: None=0, AI_Walking=1, Player=4.
                # Oak player pawns report None because their player graph uses
                # a separate locomotion path. Copying that value disables the
                # NPC graph's navigation animation rather than driving it.
                route = 4
                if hasattr(movement,'ReplicatedNavType'):
                    saved.setdefault('cached_nav_route',movement.ReplicatedNavType)
                    if movement.ReplicatedNavType != route:
                        movement.ReplicatedNavType = route
                        _call(movement,'OnRep_NavType')
                        _call(movement,'SetComponentTickEnabled',False)
                        _call(source,'ForceNetUpdate')
                instance = mesh.GetAnimInstance()
                if instance is None:
                    # Seat/camera mode changes can temporarily clear the graph.
                    # This is not a loss of network ownership or visibility.
                    _call(source,'SetActorTickEnabled',False)
                    state['native_cache_waiting_for_instance'] = True
                else:
                    if str(instance.GetOwningActor()) != str(source):
                        state['lobby_visibility_error'] = 'Animation instance belongs to another actor'
                        return False
                    state.pop('native_cache_waiting_for_instance',None)
                    if 'cached_animation_instance' not in saved:
                        previous = movement.CachedAnimInstance
                        saved['cached_animation_instance'] = WeakPointer(previous) if previous is not None else None
                    if str(movement.CachedAnimInstance) != str(instance):
                        movement.CachedAnimInstance = instance
            elif 'root_motion_translation_scale' in saved:
                state['lobby_visibility_stage'] = 'restore native cache for seat'
                restore_native_animation_cache(state, source, movement)
            if replicate_velocity:
                state['lobby_visibility_stage'] = 'replicated velocity'
                pawn = state.get('pawn')
                if pawn is None: return False
                # A cosmetic cloned from an NPC can retain its slow network
                # cadence. Use player cadence and send gait transitions now.
                for name in ('NetUpdateFrequency', 'MinNetUpdateFrequency'):
                    current = getattr(source, name, None)
                    target = getattr(pawn, name, None)
                    if current is not None and target is not None:
                        saved.setdefault('network_rates', {}).setdefault(name, current)
                        setattr(source, name, max(float(current), float(target)))
                velocity = pawn.GetVelocity()
                player_movement = getattr(pawn, 'CharacterMovement', None)
                movement.Velocity = velocity
                _sync_native_nav_intent(state,movement,velocity if cache_tick else None)
                _sync_native_ground_contact(state,movement,player_movement if cache_tick else None)
                _sync_native_movement_input(state,movement,source,velocity if cache_tick else None)
                source.ReplicatedMovement.LinearVelocity = velocity
                replicated = source.ReplicatedMovement
                player_movement = getattr(pawn, 'CharacterMovement', None)
                if state.get('gait_speed_scale_trial') is True:
                    # This per-component attribute is CPF_Net in BL4. Keep the
                    # native stance/animation sets, but stop an NPC walk-speed
                    # ceiling from clamping player-speed cosmetic motion.
                    import math
                    scale = movement.MaxGroundSpeedScale
                    if 'ground_speed_scale' not in saved:
                        saved['ground_speed_scale'] = {name:float(getattr(scale,name)) for name in ('Value','BaseValue')}
                    base_speed = float(source.ReplicatedStance.stance.speed)
                    actual_speed = math.hypot(float(velocity.X),float(velocity.Y))
                    allowed_speed = max(float(player_movement.GetMaxSpeed()),actual_speed)
                    if not (math.isfinite(base_speed) and base_speed > 0 and math.isfinite(allowed_speed) and allowed_speed > 0):
                        return False
                    desired_scale = allowed_speed/base_speed
                    if abs(float(scale.Value)-desired_scale) > .001 or abs(float(scale.BaseValue)-desired_scale) > .001:
                        scale.Value = desired_scale
                        scale.BaseValue = desired_scale
                        _call(source,'ForceNetUpdate')
                elif 'ground_speed_scale' in saved:
                    for name,value in saved.pop('ground_speed_scale').items():
                        setattr(movement.MaxGroundSpeedScale,name,value)
                    _call(source,'ForceNetUpdate')
                # Retire the rejected player-nav-type trial. Native NPC
                # graphs went idle when forced onto the player's nav route.
                if 'nav_type' in saved:
                    movement.ReplicatedNavType = saved.pop('nav_type')
                    _call(movement, 'OnRep_NavType')
                    _call(source, 'ForceNetUpdate')
                acceleration = getattr(player_movement, 'Acceleration', None)
                if acceleration is not None and hasattr(replicated, 'bRepAcceleration'):
                    if 'rep_acceleration' not in saved:
                        saved['rep_acceleration'] = bool(replicated.bRepAcceleration)
                    replicated.Acceleration = acceleration
                    replicated.bRepAcceleration = True
                speed = sum(float(getattr(velocity, axis))**2 for axis in 'XYZ')**0.5
                previous = saved.get('sent_motion_speed')
                if (previous is None or (previous > 2.0) != (speed > 2.0)
                        or abs(speed - previous) >= 100.0):
                    saved['sent_motion_speed'] = speed
                    _call(source, 'ForceNetUpdate')
            if changed: _call(source,'ForceNetUpdate')
        if mesh.bOwnerNoSee and not _call(mesh, "SetOwnerNoSee", False):
            return False
        if mesh.bOnlyOwnerSee and not _call(mesh, "SetOnlyOwnerSee", False):
            return False
        if not saved.get("updated"):
            _call(source, "FlushNetDormancy")
            _call(source, "ForceNetUpdate")
            saved["updated"] = True
        state['lobby_visibility_stage'] = 'final visibility'
        return bool(source.bReplicates and bool(source.bReplicateMovement) == replicate_velocity and source.bAlwaysRelevant and not source.bOnlyRelevantToOwner and not source.bHidden
                    and not mesh.bOwnerNoSee and not mesh.bOnlyOwnerSee and (not mesh.bHiddenInGame or motion_proxy_visible))
    except Exception as exc:
        state['lobby_visibility_error'] = type(exc).__name__+': '+str(exc)
        return False

def restore_lobby_visibility(state: dict[str, Any], *, restore_shadows: bool = True) -> None:
    _sync_native_nav_intent(state,None,None)
    _sync_native_ground_contact(state,None,None)
    _sync_native_movement_input(state,None,None,None)
    restore_owner_camera_view(state)
    if restore_shadows:
        restore_shadow_visibility(state)
    saved = state.pop("lobby_visibility", None)
    if saved is None:
        return
    actor, mesh = saved["actor"](), saved["mesh"]()
    movement = saved['movement']() if saved.get('movement') else None
    if movement is not None:
        if 'cached_nav_route' in saved:
            movement.ReplicatedNavType = saved['cached_nav_route']
            _call(movement,'OnRep_NavType')
            _call(movement,'SetComponentTickEnabled',False)
        if 'cached_animation_instance' in saved:
            previous = saved['cached_animation_instance']
            movement.CachedAnimInstance = previous() if previous is not None else None
        if 'ground_speed_scale' in saved:
            for name,value in saved['ground_speed_scale'].items():
                setattr(movement.MaxGroundSpeedScale,name,value)
        if 'nav_type' in saved:
            movement.ReplicatedNavType = saved['nav_type']
            _call(movement, 'OnRep_NavType')
        if saved['movement_active']: _call(movement,'Activate',True)
        else: _call(movement,'Deactivate')
        _call(movement,'SetIsReplicated',saved['movement_replicates'])
    root = saved['root']() if saved.get('root') else None
    if root is not None:
        flags = saved['root_flags']
        if 'bReplicates' in flags:
            _call(root, 'SetIsReplicated', flags['bReplicates'])
        if all(name in flags for name in ('bAbsoluteLocation', 'bAbsoluteRotation', 'bAbsoluteScale')):
            _call(root, 'SetAbsolute', *(flags[name] for name in ('bAbsoluteLocation', 'bAbsoluteRotation', 'bAbsoluteScale')))
    if mesh is not None:
        _call(mesh, "SetOwnerNoSee", saved["mesh_flags"]["bOwnerNoSee"])
        _call(mesh, "SetOnlyOwnerSee", saved["mesh_flags"]["bOnlyOwnerSee"])
    if actor is not None:
        if 'root_motion_translation_scale' in saved:
            actor.AnimRootMotionTranslationScale = saved['root_motion_translation_scale']
            _call(actor,'SetActorTickEnabled',saved['actor_tick_enabled'])
        if 'rep_acceleration' in saved:
            actor.ReplicatedMovement.bRepAcceleration = saved['rep_acceleration']
        for name, value in saved.get('network_rates', {}).items():
            setattr(actor, name, value)
        if saved.get('stance_name'):
            from unrealsdk.unreal import FGbxDefPtr
            actor.ReplicatedStance.stance = FGbxDefPtr(saved['stance_name'],type='GbxStanceDef')
            _call(actor,'OnRep_Stance')
        if saved.get('owner_saved'):
            reference = saved.get('owner')
            _call(actor, 'SetOwner', reference() if reference is not None else None)
        for name in ("bAlwaysRelevant", "bOnlyRelevantToOwner"):
            try:
                setattr(actor, name, saved["actor_flags"][name])
            except Exception:
                pass
        _call(actor, "SetReplicateMovement", saved["actor_flags"]["bReplicateMovement"])
        _call(actor, "SetReplicates", saved["actor_flags"]["bReplicates"])
        _call(actor, "ForceNetUpdate")


def set_shadow_visibility(state, components, visible, *, group="original"):
    """Keep body shadow flags reversible, including newly rebuilt components."""
    saved = state.setdefault("shadow_visibility", {})
    for component in components:
        if component is None or str(getattr(component, "Name", "")) == "FirstPersonArms":
            continue
        key = group + ":" + str(component)
        if key not in saved:
            values = {attr: bool(value) for attr in ("CastShadow", "bCastHiddenShadow")
                      if (value := getattr(component, attr, None)) is not None}
            saved[key] = (WeakPointer(component), values)
        component_visible=visible and 'SQBT_FullShadowProxyActive' not in list(getattr(component,'ComponentTags',()) or ())
        for attr in saved[key][1]:
            if bool(getattr(component, attr)) != component_visible:
                method = "SetCastShadow" if attr == "CastShadow" else "SetCastHiddenShadow"
                if not _call(component, method, component_visible):
                    setattr(component, attr, component_visible)


def restore_shadow_visibility(state):
    for reference, values in state.pop("shadow_visibility", {}).values():
        component = reference()
        if component is None:
            continue
        for attr, value in values.items():
            method = "SetCastShadow" if attr == "CastShadow" else "SetCastHiddenShadow"
            if not _call(component, method, value):
                try:
                    setattr(component, attr, value)
                except Exception:
                    pass


def hold_local_visual(shell, wearer_parts):
    """Draw the swap for the wearer only. The world still sees the real character."""
    if shell is not None:
        _call(shell, 'SetReplicates', False)
        _call(shell, 'SetActorEnableCollision', False)
        _call(shell, 'SetActorHiddenInGame', False)
        try:
            shell.bOnlyRelevantToOwner = True
        except Exception:
            pass
        parts = []
        try:
            import unrealsdk
            parts = [part for part in list(shell.K2_GetComponentsByClass(
                unrealsdk.find_class('PrimitiveComponent')) or ()) if part is not None]
        except Exception:
            parts = []
        for part in parts:
            if str(getattr(part, 'Name', '')) == 'FirstPersonArms':
                continue
            _set_component_flag(part, 'SetOnlyOwnerSee', 'bOnlyOwnerSee', True)
            _set_component_flag(part, 'SetOwnerNoSee', 'bOwnerNoSee', False)
            _call(part, 'SetVisibility', True, False)
            _call(part, 'SetHiddenInGame', False, False)
            _call(part, 'SetCollisionEnabled', 0)
    for part in wearer_parts or ():
        if part is None or str(getattr(part, 'Name', '')) == 'FirstPersonArms':
            continue
        _set_component_flag(part, 'SetOwnerNoSee', 'bOwnerNoSee', True)
        _set_component_flag(part, 'SetOnlyOwnerSee', 'bOnlyOwnerSee', False)
        _call(part, 'SetVisibility', True, False)
        _call(part, 'SetHiddenInGame', False, False)


def _set_component_flag(component, method, attr, value):
    if component is None:
        return
    if not _call(component, method, value):
        try:
            setattr(component, attr, value)
        except Exception:
            pass


def _owner_body_parts(source, mesh):
    found = []
    try:
        import unrealsdk
        found = [part for part in list(source.K2_GetComponentsByClass(
            unrealsdk.find_class('PrimitiveComponent')) or []) if part is not None]
    except Exception:
        found = []
    if not found and mesh is not None:
        found = [mesh]
    return [part for part in found if str(getattr(part, 'Name', '')) != 'FirstPersonArms']


def _hide_owner_body_keep_shadow(saved, source, mesh):
    """Hide the swapped body from this player while its shadow still draws."""
    known = {}
    for part in saved.get('shadow_parts') or []:
        component = part['component']()
        if component is not None:
            known[str(component)] = part
    for part in _owner_body_parts(source, mesh):
        key = str(part)
        if key in known:
            continue
        known[key] = {'component': WeakPointer(part),
            'owner_no_see': bool(getattr(part, 'bOwnerNoSee', False)),
            'cast_shadow': bool(getattr(part, 'CastShadow', True)),
            'hidden_shadow': bool(getattr(part, 'bCastHiddenShadow', False))}
    saved['shadow_parts'] = list(known.values())
    for part in saved['shadow_parts']:
        component = part['component']()
        if component is None:
            continue
        _set_component_flag(component, 'SetOwnerNoSee', 'bOwnerNoSee', True)
        _set_component_flag(component, 'SetCastShadow', 'CastShadow', True)
        _set_component_flag(component, 'SetCastHiddenShadow', 'bCastHiddenShadow', True)


def _restore_owner_body_shadow(saved):
    if not saved:
        return
    for part in saved.get('shadow_parts') or []:
        component = part['component']()
        if component is None:
            continue
        _set_component_flag(component, 'SetOwnerNoSee', 'bOwnerNoSee', part['owner_no_see'])
        _set_component_flag(component, 'SetCastShadow', 'CastShadow', part['cast_shadow'])
        _set_component_flag(component, 'SetCastHiddenShadow', 'bCastHiddenShadow', part['hidden_shadow'])


def _is_face_bone(name):
    """Head and neck only. Spine, chest, hips and legs stay visible."""
    folded = str(name).casefold()
    if any(word in folded for word in ('ik', 'weapon', 'gun', 'end')):
        return False
    return any(word in folded for word in ('head', 'neck', 'face', 'skull', 'jaw', 'hair', 'scarf', 'collar', 'frill', 'cowl', 'hood', 'shawl', 'veil'))


def _existing_face_bones(mesh):
    if mesh is None:
        return []
    found, seen = [], set()

    def add(bone):
        if not _is_face_bone(bone):
            return
        key = str(bone).casefold()
        if key in seen:
            return
        try:
            if int(mesh.GetBoneIndex(bone)) < 0:
                return
        except Exception:
            return
        seen.add(key)
        found.append(bone)

    try:
        count = min(1024, max(0, int(mesh.GetNumBones())))
    except Exception:
        count = 0
    for index in range(count):
        try:
            add(mesh.GetBoneName(index))
        except Exception:
            continue
    for bone in ('Head', 'head', 'Bip01_Head', 'Bip01 Head', 'mixamorig:Head', 'head_jnt',
                 'Neck', 'Neck1', 'neck', 'neck_01', 'Bip01_Neck', 'Bip01 Neck', 'mixamorig:Neck', 'neck_jnt',
                 'L_NeckFrills_MOX', 'R_NeckFrills_MOX', 'B_NeckFrills_MOX'):
        add(bone)
    return found


def _release_head_shadow(saved):
    record=saved.pop('head_shadow_proxy',None) if saved else None
    if not record:return
    component=record['component']();mesh=record['mesh']()
    if component is not None:_call(component,'K2_DestroyComponent',component.GetOwner())
    if mesh is not None:
        mesh.ComponentTags=[tag for tag in list(getattr(mesh,'ComponentTags',()) or ()) if str(tag)!='SQBT_FullShadowProxyActive']
        _set_component_flag(mesh,'SetCastShadow','CastShadow',record['cast_shadow'])


def _finish_head_shadow(saved, mesh, component, status):
    _call(component,'SetVisibility',True,False)
    _call(component,'SetHiddenInGame',True,False)
    component.SetCastShadow(True)
    # The hidden head copy adds the camera-hidden head to the shadow.
    # The visible body keeps its own shadow; turning that off removed the
    # player shadow whenever this proxy was created.
    saved['head_shadow_status']=status


def _sync_head_shadow(saved,source,mesh,animation_state=None):
    """Keep the hidden first-person head in the shadow.

    Evaluate independently: following the masked mesh also copied its missing
    head. Never leader-pose the shadow to the camera-masked body.
    """
    try:
        animation=getattr(getattr(mesh,'AnimationData',None),'AnimToPlay',None)
        position=rate=None
        if animation is None and animation_state and animation_state.get('native_motion_clip'):
            from . import native_motion
            from .native_seating import load_clip
            motion=animation_state['native_motion_clip']
            definition=native_motion.definition(mesh,animation_state)
            if definition and motion.get('clip') in definition.get('clips',{}):
                animation=load_clip(definition['clips'][motion['clip']]['animation'])
                montage=motion['montage']();instance=motion['instance']()
                position=float(instance.Montage_GetPosition(montage))
                rate=float(instance.Montage_GetPlayRate(montage))
        driver='clip' if animation is not None else 'graph'
        record=saved.get('head_shadow_proxy')
        if record is not None and record.get('driver') not in (None, driver):
            # Reuse the component across idle/run transitions. Repeatedly
            # destroying/recreating render components is unnecessary here.
            component=record['component']()
            if component is None:raise RuntimeError('Shadow component expired')
            if driver=='graph':component.SetAnimInstanceClass(mesh.AnimClass)
            record.update(driver=driver,animation=None)
        if record is None and driver=='graph':
            import unrealsdk
            transform=unrealsdk.make_struct('Transform')
            transform.Rotation.W=1.;transform.Scale3D.X=transform.Scale3D.Y=transform.Scale3D.Z=1.
            result=source.AddComponentByClass(unrealsdk.find_class('GbxSkeletalMeshComponent'),True,transform,False)
            component=result[0] if isinstance(result,(tuple,list)) else result
            if component is None:raise RuntimeError('Cannot create shadow component')
            record={'component':WeakPointer(component),'mesh':WeakPointer(mesh),'cast_shadow':bool(mesh.CastShadow),'driver':'graph'}
            saved['head_shadow_proxy']=record
            component.SetVisibility(False,False)
            component.SetCastShadow(False)
            component.SetSkeletalMeshAsset(mesh.GetSkinnedAsset())
            anim_class=getattr(mesh,'AnimClass',None)
            if anim_class is None:raise RuntimeError('Source shadow animation class unavailable')
            component.SetAnimInstanceClass(anim_class)
            if not component.K2_AttachToComponent(mesh,'',2,2,2,False):raise RuntimeError('Cannot attach shadow component')
            component.SetCollisionEnabled(0);component.SetIsReplicated(False)
            component.ComponentTags=list(getattr(component,'ComponentTags',()) or ())+['SQBT_HeadShadow']
            component.bRenderInMainPass=False;component.bRenderInDepthPass=False
            component.bCastHiddenShadow=True
            component.bUseAttachParentBound=False
            component.VisibilityBasedAnimTickOption=0
            component.bPauseAnims=False
            _call(component,'SetComponentTickEnabled',True)
            for index in range(mesh.GetNumMaterials()):component.SetMaterial(index,mesh.GetMaterial(index))
        if driver=='graph':
            component=record['component']() if record is not None else None
            if component is None:raise RuntimeError('Shadow component expired')
            instance=component.GetAnimInstance()
            if instance is None:
                saved['head_shadow_status']='waiting_for_independent_graph'
                return
            from .animation import _copy_animation_inputs
            _copy_animation_inputs(mesh.GetAnimInstance(),instance)
            _finish_head_shadow(saved,mesh,component,'independent_graph_shadow')
            return
        if record is None:
            import unrealsdk
            transform=unrealsdk.make_struct('Transform')
            transform.Rotation.W=1.;transform.Scale3D.X=transform.Scale3D.Y=transform.Scale3D.Z=1.
            result=source.AddComponentByClass(unrealsdk.find_class('GbxSkeletalMeshComponent'),True,transform,False)
            component=result[0] if isinstance(result,(tuple,list)) else result
            if component is None:raise RuntimeError('Cannot create shadow component')
            record={'component':WeakPointer(component),'mesh':WeakPointer(mesh),'cast_shadow':bool(mesh.CastShadow),'animation':None,'driver':'clip'}
            saved['head_shadow_proxy']=record
            component.SetVisibility(False,False)
            component.SetCastShadow(False)
            component.SetSkeletalMeshAsset(mesh.GetSkinnedAsset())
            if not component.K2_AttachToComponent(mesh,'',2,2,2,False):raise RuntimeError('Cannot attach shadow component')
            component.SetCollisionEnabled(0);component.SetIsReplicated(False)
            component.ComponentTags=list(component.ComponentTags)+['SQBT_HeadShadow']
            component.bRenderInMainPass=False;component.bRenderInDepthPass=False
            component.bCastHiddenShadow=True
            component.VisibilityBasedAnimTickOption=0
            for index in range(mesh.GetNumMaterials()):component.SetMaterial(index,mesh.GetMaterial(index))
        component=record['component']()
        if component is None:raise RuntimeError('Shadow component expired')
        if record.get('animation')!=str(animation):
            component.PlayAnimation(animation,True)
            record['animation']=str(animation)
        component.SetPosition(float(mesh.GetPosition()) if position is None else position,False)
        component.SetPlayRate(float(mesh.GetPlayRate()) if rate is None else rate)
        _finish_head_shadow(saved,mesh,component,'independent_clip_shadow_candidate')
    except Exception as exc:
        _release_head_shadow(saved)
        saved['head_shadow_status']='error: '+str(exc)


def _reveal_shadow_head(saved):
    """The camera hides the head on the visible mesh. The shadow copy keeps it."""
    record=saved.get('head_shadow_proxy') if saved else None
    if not record: return
    component=record['component']()
    if component is None: return
    for bone in list(saved.get('masked_bones') or {}):
        _call(component,'UnHideBoneByName',bone)


def _show_shadow_head(saved, mesh):
    """The head hide was also removing the head from the shadow."""
    if not saved or mesh is None:
        return
    _release_head_shadow(saved)
    bones = saved.get('masked_bones') or {}
    names = list(bones)
    names.extend(['Head', 'head', 'Bip01_Head', 'Bip01 Head', 'mixamorig:Head', 'head_jnt',
                  'Neck', 'Neck1', 'neck', 'neck_01', 'Bip01_Neck', 'Bip01 Neck', 'mixamorig:Neck', 'neck_jnt'])
    if saved.get('head_bone'):
        names.append(saved['head_bone'])
    for bone in names:
        was_hidden = bones.pop(bone, None)
        if was_hidden is False:
            _call(mesh, 'UnHideBoneByName', bone)


def run_body_correction_cm(ahead, target=16.0):
    """Keep the head just in front of the camera, standing or running."""
    if ahead is None:
        return 0.0
    extra = float(ahead) - float(target)
    if abs(extra) < 4.0:
        return 0.0
    return max(-120.0, min(extra, 180.0))


def fp_eye_height_cm(head_z, pawn_z):
    """Clear the scarf. The head joint sits at the neck, and the scarf fills the next 18cm."""
    return max(40.0, min(float(head_z) - float(pawn_z) + 42.0, 4096.0))


def _copy_location(loc):
    import unrealsdk
    return unrealsdk.make_struct('Vector', X=float(loc.X), Y=float(loc.Y), Z=float(loc.Z))


def _location_matches(mesh, loc):
    current = mesh.RelativeLocation
    return all(abs(float(getattr(current, axis)) - float(getattr(loc, axis))) <= 1.0 for axis in 'XYZ')


def release_fp_body_anchor(state, mesh=None):
    """Restore the cosmetic mesh only while this run correction still owns it."""
    anchor = state.pop('fp_body_anchor', None) if state else None
    if not anchor:
        return
    target = mesh if mesh is not None else (anchor['mesh']() if anchor.get('mesh') is not None else None)
    if target is None or anchor.get('origin') is None:
        return
    applied = anchor.get('applied')
    if applied is not None and not _location_matches(target, applied):
        return
    _call(target, 'K2_SetRelativeLocation', anchor['origin'], False, False)


def _body_ahead_cm(mesh, pawn):
    forward = pawn.GetActorForwardVector()
    origin = pawn.K2_GetActorLocation()
    fx, fy = float(forward.X), float(forward.Y)
    scale = (fx * fx + fy * fy) ** 0.5 or 1.0
    fx, fy = fx / scale, fy / scale
    best = None
    for bone in ('Head', 'head', 'Bip01_Head', 'Bip01 Head', 'mixamorig:Head', 'head_jnt',
                 'Hips', 'hips', 'Pelvis', 'pelvis', 'Bip01_Pelvis', 'mixamorig:Hips'):
        try:
            if int(mesh.GetBoneIndex(bone)) < 0:
                continue
            pos = mesh.GetSocketLocation(bone)
        except Exception:
            continue
        ahead = (float(pos.X) - float(origin.X)) * fx + (float(pos.Y) - float(origin.Y)) * fy
        if ahead == ahead:
            best = ahead
            if 'head' in str(bone).casefold():
                return best
    return best


def _head_height_cm(mesh, pawn):
    """Highest head or skull point. The first head bone is often the neck joint."""
    try:
        origin = float(pawn.K2_GetActorLocation().Z)
    except Exception:
        return None
    best = None

    def consider(bone):
        nonlocal best
        folded = str(bone).casefold()
        if 'head' not in folded and 'skull' not in folded:
            return
        if any(word in folded for word in ('ik', 'weapon', 'gun')):
            return
        try:
            if int(mesh.GetBoneIndex(bone)) < 0:
                return
            height = float(mesh.GetSocketLocation(bone).Z) - origin
        except Exception:
            return
        if height == height and (best is None or height > best):
            best = height

    try:
        count = min(1024, max(0, int(mesh.GetNumBones())))
    except Exception:
        count = 0
    for index in range(count):
        try:
            consider(mesh.GetBoneName(index))
        except Exception:
            continue
    for bone in ('Head', 'head', 'Bip01_Head', 'Bip01 Head', 'mixamorig:Head', 'head_jnt'):
        consider(bone)
    if best is not None:
        return best
    try:
        bounds = mesh.Bounds
        height = float(bounds.Origin.Z) + abs(float(bounds.BoxExtent.Z)) * 0.85 - origin
        if height == height:
            return max(-1024.0, min(4096.0, height))
    except Exception:
        return None
    return None


def _restore_fp_eye_height(state):
    saved = state.pop('fp_eye_height', None) if state else None
    pawn = saved['pawn']() if saved and saved.get('pawn') is not None else None
    if pawn is None:
        return
    if saved.get('base') is not None:
        try:
            pawn.BaseEyeHeight = saved['base']
        except Exception:
            pass
    if saved.get('crouch') is not None:
        try:
            pawn.CrouchedEyeHeight = saved['crouch']
        except Exception:
            pass


def _hold_fp_eye_height(state, mesh, pawn):
    offset = _head_height_cm(mesh, pawn)
    if offset is None:
        return
    height = fp_eye_height_cm(float(pawn.K2_GetActorLocation().Z) + offset, float(pawn.K2_GetActorLocation().Z))
    eye = state.get('fp_eye_height')
    if eye is None or eye.get('pawn') is None or str(eye['pawn']()) != str(pawn):
        eye = {'pawn': WeakPointer(pawn), 'base': getattr(pawn, 'BaseEyeHeight', None),
               'crouch': getattr(pawn, 'CrouchedEyeHeight', None)}
        state['fp_eye_height'] = eye
    try:
        pawn.BaseEyeHeight = height
        if eye.get('base') is not None and eye.get('crouch') is not None:
            pawn.CrouchedEyeHeight = height - (float(eye['base']) - float(eye['crouch']))
    except Exception:
        return


def _hold_fp_body_with_camera(state, mesh, pawn):
    """Put the view at her eyes immediately. A run must not leave it in her face or chest."""
    if state is None or mesh is None or pawn is None or state.get('native_seat_clip'):
        release_fp_body_anchor(state, mesh)
        _restore_fp_eye_height(state)
        return
    try:
        import unrealsdk
        _restore_fp_eye_height(state)
        ahead = _body_ahead_cm(mesh, pawn)
        if ahead is None:
            return
        anchor = state.get('fp_body_anchor')
        if anchor is None or anchor.get('mesh') is None or str(anchor['mesh']()) != str(mesh):
            anchor = {'mesh': WeakPointer(mesh), 'origin': _copy_location(mesh.RelativeLocation), 'applied': None}
            state['fp_body_anchor'] = anchor
        else:
            _call(mesh, 'K2_SetRelativeLocation', anchor['origin'], False, False)
            ahead = _body_ahead_cm(mesh, pawn)
        extra = run_body_correction_cm(ahead)
        if extra == 0:
            anchor['applied'] = None
            return
        forward = pawn.GetActorForwardVector()
        world = mesh.K2_GetComponentLocation()
        moved = unrealsdk.make_struct('Vector',
            X=float(world.X) - float(forward.X) * extra,
            Y=float(world.Y) - float(forward.Y) * extra,
            Z=float(world.Z))
        if not _call(mesh, 'K2_SetWorldLocation', moved, False, unrealsdk.make_struct('HitResult'), True):
            _call(mesh, 'K2_SetRelativeLocation', anchor['origin'], False, False)
            return
        anchor['applied'] = _copy_location(mesh.RelativeLocation)
    except Exception:
        return


def _restore_third_person_head(state):
    saved = state.pop('third_person_head', None) if state else None
    if not saved:
        return
    camera = saved['camera']() if saved.get('camera') is not None else None
    if camera is None:
        return
    offset = saved.get('offset')
    if offset is not None:
        try:
            import unrealsdk
            camera.FreeCamOffset = unrealsdk.make_struct('Vector', X=float(offset['x']), Y=float(offset['y']), Z=float(offset['z']))
        except Exception:
            pass
    if saved.get('distance') is not None:
        try:
            camera.FreeCamDistance = saved['distance']
        except Exception:
            pass


def _hold_third_person_head(state, camera, pawn, mesh):
    """Look at the swapped head. A boss-sized body steps the camera back outside it."""
    if camera is None or pawn is None or mesh is None:
        return
    try:
        height = _head_height_cm(mesh, pawn)
    except Exception:
        return
    if height is None:
        return
    try:
        current = camera.FreeCamOffset
        origin = {'x': float(current.X), 'y': float(current.Y), 'z': float(current.Z)}
        distance = float(getattr(camera, 'FreeCamDistance', 0.0) or 0.0)
    except Exception:
        return
    saved = state.get('third_person_head')
    if saved is None or saved.get('camera') is None or str(saved['camera']()) != str(camera):
        eye = getattr(pawn, 'BaseEyeHeight', None)
        saved = {'camera': WeakPointer(camera), 'offset': origin, 'distance': distance,
                 'eye': eye if isinstance(eye, (int, float)) else None}
        state['third_person_head'] = saved
    base = saved.get('eye')
    base = float(base) if isinstance(base, (int, float)) else 64.0
    lift = float(height) - base
    try:
        import unrealsdk
        start = saved['offset']
        camera.FreeCamOffset = unrealsdk.make_struct(
            'Vector', X=float(start['x']), Y=float(start['y']), Z=float(start['z']) + lift)
    except Exception:
        return
    try:
        extent = mesh.Bounds.BoxExtent
        size = max(abs(float(extent.X)), abs(float(extent.Y)), abs(float(extent.Z)))
    except Exception:
        size = 0.0
    if size >= 150.0:
        try:
            camera.FreeCamDistance = max(float(saved.get('distance') or 0.0), min(size * 2.2 + 80.0, 4000.0))
        except Exception:
            pass
    elif saved.get('distance') is not None:
        try:
            camera.FreeCamDistance = saved['distance']
        except Exception:
            pass


def _release_owner_camera_fit(saved):
    _restore_unsupported_weapon(saved)
    _release_viewmodel_alignment(saved)
    if saved:
        try:
            from . import native_fp_arms
            native_fp_arms.release(saved)
        except ImportError:
            pass
        try:
            from . import native_eye_camera
            native_eye_camera.release(saved)
        except ImportError:
            pass
    fit=saved.pop('camera_fit',None) if saved else None
    if fit is None:return
    try:
        from unrealsdk import hooks
        for event in ('BlueprintModifyCamera','BlueprintModifyPostProcess'):
            hooks.remove_hook('/Script/Engine.CameraModifier:'+event,hooks.Type.POST,fit['id'])
    except Exception: pass
    modifier=fit['modifier']();camera=fit['camera']()
    if modifier is not None:
        try:modifier.DisableModifier(True)
        except Exception: pass
        if camera is not None:
            try:camera.RemoveCameraModifier(modifier)
            except Exception: pass


def _ensure_owner_camera_fit(saved,camera,pawn,mesh):
    """Follow the visible head at the actual camera pass, without moving the body."""
    if mesh is None:return
    fit=saved.get('camera_fit')
    if fit is not None:return
    try:
        import unrealsdk,math
        from unrealsdk import hooks
        head=next((bone for bone in ('Head','head','Bip01_Head','Bip01 Head','mixamorig:Head','head_jnt')
                   if int(mesh.GetBoneIndex(bone))>=0),None)
        if head is None:return
        modifier=camera.AddNewCameraModifier(unrealsdk.find_class('CameraModifier'))
        if modifier is None:return
        modifier.Priority=255
        fit={'modifier':WeakPointer(modifier),'camera':WeakPointer(camera),'mesh':WeakPointer(mesh),
             'pawn':WeakPointer(pawn),'head':head,'id':'appearance_head_view_'+str(id(saved)),
             'seen':0,'applied':0}
        saved['camera_fit']=fit
        def observe(obj,args,_ret=None,_func=None):
            if str(obj)!=str(fit['modifier']()):return
            fit['input']=[float(getattr(args.NewViewLocation,a)) for a in 'XYZ']
        def apply(obj,_args,_ret=None,_func=None):
            if str(obj)!=str(fit['modifier']()):return
            try:
                fit['seen']+=1
                cam=fit['camera']();body=fit['mesh']();player=fit['pawn']()
                if cam is None or body is None or player is None:return
                if str(cam.GetActorCameraMode(player))!='Default' or bool(getattr(player,'bIsDriving',False)):return
                target=cam.ViewTarget
                if str(target.target)!=str(player):return
                position=target.POV.Location
                before=[float(getattr(position,a)) for a in 'XYZ']
                if 'input' not in fit or math.dist(before,fit['input'])>.5:
                    fit['native_input_match']=False;return
                fit['native_input_match']=True
                point=body.GetSocketLocation(fit['head'])
                yaw=math.radians(float(target.POV.Rotation.Yaw))
                desired=[float(point.X)+16*math.cos(yaw),float(point.Y)+16*math.sin(yaw),float(point.Z)+18]
                delta=[b-a for a,b in zip(before,desired)]
                if any(not math.isfinite(v) for v in delta) or math.dist(before,desired)>100:return
                # This event runs after ModifyCamera's output parameters have
                # copied back. Write the real native POV, never the hook args.
                target.POV.Location=unrealsdk.make_struct('Vector',**dict(zip('XYZ',desired)))
                cam.ViewTarget=target
                # Oak evaluates its own mode POV before filling the camera cache.
                # Updating only Engine's ViewTarget is overwritten by that POV.
                mode_state=getattr(cam,'CameraModeState',None)
                if mode_state is not None:
                    mode_pov=mode_state.POV
                    mode_pov.Location=unrealsdk.make_struct('Vector',**dict(zip('XYZ',desired)))
                    mode_state.POV=mode_pov
                fit.update(applied=fit['applied']+1,before=before,after=desired,head_position=[float(getattr(point,a)) for a in 'XYZ'])
            except Exception as exc:fit['error']=str(exc)
        for event,callback in (('BlueprintModifyCamera',observe),('BlueprintModifyPostProcess',apply)):
            hooks.add_hook('/Script/Engine.CameraModifier:'+event,hooks.Type.POST,fit['id'],callback)
        modifier.EnableModifier()
    except Exception as exc:
        _release_owner_camera_fit(saved);saved['camera_fit_error']=str(exc)


def restore_owner_camera_view(state):
    release_fp_body_anchor(state)
    _restore_fp_eye_height(state)
    _restore_third_person_head(state)
    saved = state.pop('owner_camera_view', None)
    _release_head_shadow(saved)
    _release_owner_camera_fit(saved)
    _restore_owner_body_shadow(saved)
    if saved and saved.get('mesh') is not None:
        mesh = saved['mesh']()
        bones=saved.get('masked_bones')
        if bones is None and saved.get('head_bone'):
            bones={saved['head_bone']:saved.get('head_was_hidden',False)}
        if mesh is not None:
            for bone,was_hidden in reversed(list((bones or {}).items())):
                if not was_hidden: _call(mesh,'UnHideBoneByName',bone)
    pc = saved['controller']() if saved else None
    if pc is not None and saved.get('added',False):
        pc.HiddenActors = [actor for actor in list(pc.HiddenActors)
            if actor is not None and str(actor) != saved['source_key']]


def prepare_owner_camera_view(state, pc, pawn, source, mesh=None):
    """Mask local first-person head/neck/shoulders, preserving the lower body."""
    import math
    if pc is None or pawn is None or source is None:
        restore_owner_camera_view(state)
        return
    local=getattr(pawn,'IsLocallyControlled',None)
    if source is pawn or (callable(local) and not local()):
        restore_owner_camera_view(state)
        return
    driving=bool(getattr(pawn,'bIsDriving',False))
    try:
        player_instance=pawn.Mesh.GetAnimInstance()
        driving=driving or bool(getattr(player_instance,'bIsDriving',False))
    except Exception: pass
    if driving:
        restore_owner_camera_view(state)
        return
    saved = state.get('owner_camera_view')
    mesh = mesh or getattr(source,'Mesh',None)
    if saved is not None and (str(saved['controller']()) != str(pc) or saved['source_key'] != str(source)
            or (saved.get('mesh') is not None and str(saved['mesh']()) != str(mesh))):
        restore_owner_camera_view(state)
        saved = None
    camera = getattr(pc, 'PlayerCameraManager', None) or getattr(pc, 'CameraManager', None)
    if camera is None:
        restore_owner_camera_view(state)
        return
    try:
        downed=bool(pawn.IsInjured())
    except Exception:
        downed=False
    if downed:
        location,origin=camera.GetCameraLocation(),pawn.K2_GetActorLocation()
        if math.hypot(float(location.X-origin.X),float(location.Y-origin.Y)) < 90:
            if saved is None:
                saved={'controller':WeakPointer(pc),'source_key':str(source),'added':False}
                state['owner_camera_view']=saved
            _release_owner_camera_fit(saved)
            _show_shadow_head(saved,mesh)
            _hide_owner_body_keep_shadow(saved,source,mesh)
            if not any(actor is not None and str(actor)==str(source) for actor in list(pc.HiddenActors)):
                pc.HiddenActors=list(pc.HiddenActors)+[source]
                saved['added']=True
            saved['downed_hidden']=True
            release_fp_body_anchor(state,mesh)
            return
    if saved is not None:saved.pop('downed_hidden',None)
    mode = str(camera.GetActorCameraMode(pawn) or 'Default')
    location, origin = camera.GetCameraLocation(), pawn.K2_GetActorLocation()
    view_target=getattr(getattr(camera,'ViewTarget',None),'target',None)
    first_person = mode == 'Default' and (view_target is None or str(view_target)==str(pawn))
    if not first_person:
        restore_owner_camera_view(state)
        _hold_third_person_head(state, camera, pawn, mesh)
        return
    _restore_third_person_head(state)
    if saved is None:
        saved = {'controller': WeakPointer(pc), 'source_key': str(source), 'added': False}
        state['owner_camera_view'] = saved
    swapped_weapon_arms=False
    try:nonhuman_enemy=_nonhuman_enemy_weapon_policy(state,mesh)
    except Exception:nonhuman_enemy=False
    hide_unsupported=(nonhuman_enemy or
        _camera_anatomy(mesh).get('first_person_weapon_policy')=='hide_known_unsupported')
    try:
        from . import native_fp_arms
        # A subsequently authored matching arm definition supersedes the explicit
        # unsupported flag; unrelated/unreviewed characters keep their old behavior.
        from .native_weapon import body_holds_gun, hide_viewmodel_arms
        holds_gun=body_holds_gun(mesh)
        parts=native_fp_arms.arm_parts(mesh)
        authored=native_fp_arms.definition(parts) if parts else native_fp_arms.definition((),mesh)
        if hide_unsupported and authored is not None:hide_unsupported=False
        if hide_unsupported and holds_gun:
            # A gun-hold body owns its own arm visibility, including sights.
            _restore_unsupported_weapon(saved)
            saved['weapon_arm_status']={'status':'gun_user'}
        elif hide_unsupported:
            _release_viewmodel_alignment(saved)
            native_fp_arms.release(saved)
            hide_viewmodel_arms(state, pawn)
            saved['weapon_arm_status']={'status':'hidden_gunless_body'}
        else:
            _restore_unsupported_weapon(saved)
            swapped_weapon_arms=native_fp_arms.hold(saved,camera,pawn,source,mesh)
            if nonhuman_enemy and not swapped_weapon_arms and not holds_gun:
                # Keep a hidden overlay alive while its pose initializes, but
                # never reveal Vex's arms when an enemy's asset fails to load.
                hide_viewmodel_arms(state, pawn)
                hide_unsupported=True
    except Exception as exc:
        # An unavailable arm package/material must never prevent the accepted
        # anatomical camera from running later in this same update.
        saved['weapon_arm_status']={'status':'arm_error','error':str(exc)}
        try:native_fp_arms.release(saved)
        except Exception:pass
        if nonhuman_enemy:
            try:
                from .native_weapon import body_holds_gun, hide_viewmodel_arms
                if not body_holds_gun(mesh):
                    hide_viewmodel_arms(state, pawn)
                    hide_unsupported=True
            except Exception:
                pass
    try:
        from . import native_eye_camera
        zoom_state=getattr(pawn,'ZoomState',None)
        zooming=bool(getattr(zoom_state,'bWantsToZoom',False) or getattr(zoom_state,'bPendingZoom',False)
                     or int(getattr(zoom_state,'State',0) or 0)!=0)
        if zooming:
            # Aiming keeps the game's own camera and zoom. Do not pull the view
            # back to the swapped head while that zoom is active.
            native_eye_camera.release(saved)
            _release_viewmodel_alignment(saved)
        else:
            _hold_anatomical_eye(saved,camera,pawn,mesh)
            anatomy=_camera_anatomy(mesh)
            if not hide_unsupported and anatomy and anatomy.get('model')!='zane_bl3':_hold_native_viewmodel(saved,camera,pawn,anatomy.get('viewmodel_offset_cm',(0.,0.,0.)))
    except (ImportError,AttributeError) as exc:
        saved['native_eye_camera']={'error':str(exc)}
    # Keep the owner-view body visible during all movement at the accepted eye
    # camera height. Only oversized meshes retain the shadow-only guard.
    # Native gun arms stay on the player and are not part of this actor.
    try:
        extent = mesh.Bounds.BoxExtent
        oversized = max(abs(float(extent.X)), abs(float(extent.Y)), abs(float(extent.Z))) >= 150
    except Exception:
        oversized = False
    aiming=False
    try:
        velocity=pawn.GetVelocity()
        speed=math.hypot(float(velocity.X),float(velocity.Y))
        zoom=getattr(pawn,'ZoomState',None)
        aiming=bool(getattr(pawn,'bIsFiring',False) or getattr(zoom,'bWantsToZoom',False)
                    or getattr(zoom,'bPendingZoom',False) or int(getattr(zoom,'State',0) or 0)!=0)
        # Full run/sprint hides the leaning body; ordinary walking stays visible.
        # HiddenActors and hidden-shadow casting keep the running view clear.
        saved['movement_view']={'speed':speed,'mode':int(pawn.CharacterMovement.MovementMode),'aiming':aiming}
        sprinting=(int(pawn.CharacterMovement.MovementMode)==1
                   and speed>=(600 if saved.get('sprint_hidden') else 650))
    except Exception:
        sprinting=False
    saved['aiming']=aiming
    if oversized:
        _show_shadow_head(saved, mesh)
        _hide_owner_body_keep_shadow(saved, source, mesh)
        if not any(actor is not None and str(actor)==str(source) for actor in list(pc.HiddenActors)):
            pc.HiddenActors=list(pc.HiddenActors)+[source]
            saved['added']=True
        if sprinting:
            saved['sprint_hidden']=True
        else:
            saved.pop('sprint_hidden',None)
        saved['scale_hidden']=oversized
        # The sprint lean puts the camera in the face or on the back of the head.
        # Hide the body instead of sliding it. The shadow still draws, and the
        # view stays at this character's head, including a large boss.
        release_fp_body_anchor(state, mesh)
        _restore_fp_eye_height(state)
        return
    saved.pop('sprint_hidden',None)
    saved.pop('scale_hidden',None)
    _restore_owner_body_shadow(saved)
    saved.pop('shadow_parts', None)
    if saved.get('added',False):
        pc.HiddenActors = [actor for actor in list(pc.HiddenActors) if actor is not None and str(actor) != str(source)]
        saved['added'] = False
    if mesh is None: return
    face = _existing_face_bones(mesh)
    mapped_head=_mapped_camera_head(mesh)
    if mapped_head and mapped_head not in face:face.insert(0,mapped_head)
    # Original cosmetic accessories are distinct from the native gun. Save
    # their bone visibility with the face mask so camera/vehicle/clear restores it.
    for bone in _camera_anatomy(mesh).get('first_person_hide_bones',[]):
        if int(mesh.GetBoneIndex(bone))>=0 and bone not in face:face.append(bone)
    running=float(saved.get('movement_view',{}).get('speed',0))>=450
    for bone in _camera_anatomy(mesh).get('first_person_run_hide_bones',[]):
        if running:
            if int(mesh.GetBoneIndex(bone))>=0 and bone not in face:face.append(bone)
        else:
            was_hidden=saved.get('masked_bones',{}).pop(bone,None)
            if was_hidden is False:_call(mesh,'UnHideBoneByName',bone)
    if 'head_bone' not in saved:
        for bone in face:
            if bone==mapped_head or ('head' in str(bone).casefold() and 'neck' not in str(bone).casefold()):
                saved.update(mesh=WeakPointer(mesh),head_bone=bone,head_was_hidden=bool(mesh.IsBoneHiddenByName(bone)))
                break
    bones=saved.setdefault('masked_bones',{})
    if saved.get('head_bone'):
        # Preserve the pre-mask head state when upgrading a live head-only mask.
        bones.setdefault(saved['head_bone'],saved.get('head_was_hidden',False))
    arm_bones=('L_Clav','R_Clav','clavicle_l','clavicle_r','mixamorig:LeftShoulder','mixamorig:RightShoulder',
        'Bip01_L_Clavicle','Bip01_R_Clavicle','Bip01 L Clavicle','Bip01 R Clavicle',
        'L_B_Clav_AMA','R_B_Clav_AMA','L_T_Clav_AMA','R_T_Clav_AMA','L_M_Clav_AMA','R_M_Clav_AMA') + tuple(_camera_anatomy(mesh).get('body_arm_bones',[]))
    # Snapshot every face bone before hiding any ancestor; otherwise a
    # hidden parent would be mistaken for an originally hidden child.
    for bone in face:
        if bone in bones: continue
        try:
            bones[bone]=bool(mesh.IsBoneHiddenByName(bone))
        except Exception: continue
    if bones: saved['mesh']=WeakPointer(mesh)
    if face:_sync_head_shadow(saved,source,mesh,state)
    for bone,was_hidden in bones.items():
        if not was_hidden: _call(mesh,'HideBoneByName',bone,0)
    # Her arms stay out while she is holding the gun. While aiming, the native
    # first-person arms play the shot, so her clavicles go away for that moment.
    for bone in arm_bones:
        bones.pop(bone, None)
        _call(mesh, 'UnHideBoneByName', bone)
    _reveal_shadow_head(saved)
    # Do not slide her head in front of the camera. That is the view of her back.
    release_fp_body_anchor(state, mesh)
    _restore_fp_eye_height(state)
