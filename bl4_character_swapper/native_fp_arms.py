"""Owner-only character arms authored for the native weapon animation rig.

Build hidden first. The original weapon arms are retained unless both hands,
forearms and index fingers follow their native anchors. Nonmodular characters
keep the working native arms until an authored arm-only asset is available.
"""
import math
import json
from pathlib import Path
from unrealsdk.unreal import WeakPointer

TAG='SQBT_LocalWeaponArms'
_ANCHORS=('L_Hand','R_Hand','L_Forearm','R_Forearm','L_Index_01','R_Index_01')
_DEFINITIONS=None
_QUEUED=set()


def _object_path(value):
    text=str(value)
    return text.split("'",2)[1] if "'" in text else text


def queue_source(source,mesh,parts,diagnostics):
    """Record each unseen selected mesh once for the local, resumable builder."""
    try:
        import hashlib
        asset=mesh.GetSkinnedAsset()
        row={'source_mesh':_object_path(asset),'skeleton':_object_path(asset.Skeleton),
             'source_parts':[_object_path(p) for p in parts],'model':str(source.Name)}
        key=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:16]
        if key in _QUEUED:return
        from .packs.registry import game_root
        root=game_root()
        if root is None:return
        folder=root/'sdk_mods/model_imports/first_person_arms/requests'
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/(key+'.json')
        if not path.exists():path.write_text(json.dumps(row,indent=2),encoding='utf-8')
        _QUEUED.add(key);diagnostics['authoring_request']=path.name
    except Exception as exc:
        diagnostics['authoring_request_error']=str(exc)


def definition(parts,mesh=None):
    global _DEFINITIONS
    if _DEFINITIONS is None:
        path=Path(__file__).parent/'data/native_first_person_arms.json'
        try:
            if path.is_file():text=path.read_text(encoding='utf-8')
            else:
                from importlib.resources import files
                text=files(__package__).joinpath('data/native_first_person_arms.json').read_text(encoding='utf-8')
            _DEFINITIONS=json.loads(text)['definitions']
        except (OSError,TypeError,KeyError):_DEFINITIONS=[]
    names=sorted(str(part.Name) for part in parts)
    if mesh is not None:
        asset=mesh.GetSkinnedAsset()
        path=_object_path(asset)
        exact=next((row for row in _DEFINITIONS if row.get('native_bind_verified') is True
                    and row.get('source_mesh')==path),None)
        if exact is not None:return exact
    if not parts:return None
    return next((row for row in _DEFINITIONS if row.get('native_bind_verified') is True
                 and 'source_parts' in row
                 and sorted(row.get('source_parts',()))==names),None)


def load_mesh(row):
    import unrealsdk
    path=row.get('mesh','')
    if not path.startswith('/Game/ImportedCharacters/FirstPersonArms/'):return None
    try:
        mesh=unrealsdk.find_object('SkeletalMesh',path)
        if mesh is not None:return mesh
    except Exception:pass
    try:
        # This build's SDK LoadPackage overload cannot load these cooked
        # packages. Use the existing build-gated FPackagePath loader.
        from .packs.imported_package_loader import load_package
        load_package(path.rsplit('.',1)[0])
        return unrealsdk.find_object('SkeletalMesh',path)
    except Exception as exc:
        raise RuntimeError('Authored arm package load failed: '+str(exc)) from exc


def arm_parts(mesh):
    parts=list(getattr(mesh,'GbxActorParts_Meshes',()) or ())
    if not parts:parts=list(getattr(mesh,'GestaltMeshParts',()) or ())
    selected=[];left=right=False
    for part in parts:
        name=str(getattr(part,'Name','')).lower()
        if not any(token in name for token in ('_arm_','_hand_','_glove','_mech_rightarm','_mech_leftarm','_mech_rightcap','_mech_leftcap')):
            continue
        selected.append(part)
        left=left or any(token in name for token in ('arm_l','l_arm','leftarm'))
        right=right or any(token in name for token in ('arm_r','r_arm','rightarm'))
    return selected if left and right else []


def sync_surfaces(component,source,native,material_slots=None,surface_cache=None):
    """Map each separated part to its source material, not a full-body index."""
    if material_slots and all('source_index' in slot or slot.get('hidden') is True for slot in material_slots):
        if int(component.GetNumMaterials())!=len(material_slots):return False
        for index,slot in enumerate(material_slots):
            if slot.get('hidden') is True:
                from .packs.imported_models import _load
                material=_load('MaterialInterface','/Game/AI/_Shared/Materials/MI_Color_Invisible.MI_Color_Invisible')
                if material is None:return False
                component.SetMaterial(index,material)
                continue
            source_index=int(slot['source_index'])
            if not 0<=source_index<int(source.GetNumMaterials()):return False
            material=source.GetMaterial(source_index)
            if material is None:return False
            normal_path=slot.get('normal_texture')
            if normal_path:
                import unrealsdk
                if not normal_path.startswith('/Game/ImportedCharacters/FirstPersonArms/'):return False
                try:texture=unrealsdk.find_object('Texture2D',normal_path)
                except Exception:texture=None
                if texture is None:
                    from .packs.imported_package_loader import load_package
                    load_package(normal_path.split('.',1)[0])
                    texture=unrealsdk.find_object('Texture2D',normal_path)
                if texture is None:return False
                key=(index,str(material),normal_path)
                cached=(surface_cache or {}).get(key)
                dynamic=cached() if cached else None
                if dynamic is None:
                    dynamic=component.CreateDynamicMaterialInstance(index,material,'None')
                    if isinstance(dynamic,(list,tuple)):dynamic=dynamic[0]
                    if dynamic is None:return False
                    dynamic.SetTextureParameterValue('Normal',texture)
                    if surface_cache is not None:surface_cache[key]=WeakPointer(dynamic)
                material=dynamic
            component.SetMaterial(index,material)
        component.SetGbxForeground(bool(native.bGbxForeground))
        return True
    original=list(getattr(source,'GestaltMeshParts',()) or ())
    if not original:original=list(getattr(source,'GbxActorParts_Meshes',()) or ())
    selected=list(getattr(component,'GestaltMeshParts',()) or ())
    if not selected and not material_slots:return False
    ranges={};names={};offset=0
    for part in original:
        count=len(list(part.materials or ()))
        if not count:return False
        ranges[str(part)]=(offset,count)
        names[str(part.Name)]=(offset,count)
        offset+=count
    if int(source.GetNumMaterials())!=offset:return False
    materials=[]
    slots=material_slots or [dict(source_part=str(part.Name),source_slot=i)
                            for part in selected for i in range(ranges.get(str(part),(0,0))[1])]
    for slot in slots:
        span=names.get(slot['source_part'])
        if span is None or not 0<=int(slot['source_slot'])<span[1]:return False
        index=span[0]+int(slot['source_slot'])
        material=source.GetMaterial(index)
        if material is None:return False
        materials.append(material)
    if int(component.GetNumMaterials())!=len(materials):return False
    for index,material in enumerate(materials):
        if str(component.GetMaterial(index))!=str(material):component.SetMaterial(index,material)
    # BL4's foreground path is independent of UE's FirstPersonPrimitiveType.
    # World-pass arms clip against the body and use the wrong weapon projection.
    if bool(component.bGbxForeground)!=bool(native.bGbxForeground):
        component.SetGbxForeground(bool(native.bGbxForeground))
    return True


def _vector(value):return tuple(float(getattr(value,a)) for a in 'XYZ')


def _unrotate(vector,quaternion):
    """Inverse unit-quaternion rotation; pure arithmetic for per-frame updates."""
    x,y,z,w=(float(getattr(quaternion,a)) for a in 'XYZW')
    norm=x*x+y*y+z*z+w*w
    if not math.isfinite(norm) or abs(norm-1.)>.01:raise ValueError('Invalid shoulder rotation')
    x,y,z=-x,-y,-z
    a,b,c=vector
    tx,ty,tz=2*(y*c-z*b),2*(z*a-x*c),2*(x*b-y*a)
    return (a+w*tx+y*tz-z*ty,b+w*ty+z*tx-x*tz,c+w*tz+x*ty-y*tx)


def shoulder_weights(delta,rotation,scale):
    local=_unrotate(delta,rotation)
    if any(not math.isfinite(v) or abs(v)<.001 for v in scale):raise ValueError('Invalid shoulder scale')
    # Blender's authored coordinate basis mirrors Unreal's Y axis. Each morph
    # unit is 100cm, with zero displacement at the elbow and the entire hand.
    values=tuple(local[i]/scale[i]/100.*(1 if i!=1 else -1) for i in range(3))
    if any(not math.isfinite(v) or abs(v)>1. for v in values):raise ValueError('Shoulder join exceeds authored range')
    return values


def sync_shoulders(component,source,native,camera,morphs,diagnostics):
    if not morphs:return
    corrections={}
    for side in ('L','R'):
        bone=side+'_UpperArm'
        # BL1 bodies retain Bip01 names while the authored weapon rig uses
        # BL4 names. Resolve only the explicitly configured body arm anchor.
        source_bone=bone
        if int(source.GetBoneIndex(source_bone))<0:
            from .appearance_visibility import _camera_anatomy
            anchors=_camera_anatomy(source).get('body_arm_bones',[])
            index=0 if side=='L' else 1
            source_bone=anchors[index] if len(anchors)>index else bone
        if int(source.GetBoneIndex(source_bone))<0:raise ValueError('Missing body shoulder '+source_bone)
        target=_vector(source.GetSocketLocation(source_bone));current=native.GetSocketTransform(bone,0)
        position=_vector(current.Translation)
        delta=tuple(a-b for a,b in zip(target,position))
        values=shoulder_weights(delta,current.Rotation,_vector(current.Scale3D))
        for axis,value in zip('XYZ',values):component.SetMorphTarget('SQBT_Shoulder_'+side+'_'+axis,value,False)
        corrections[side]={'source_bone':source_bone,'delta_cm':delta,'weights':values}
    diagnostics['shoulder_join']={'status':'experimental_world_anchor','corrections':corrections,
                                 'projection_verified':False}


def release(saved):
    record=saved.pop('weapon_arm_overlay',None) if saved else None
    if not record:return
    native=record['native']()
    if native is not None:
        for index,reference in enumerate(record.get('trial_native_materials',[])):
            native.SetMaterial(index,reference() if reference is not None else None)
    if native is not None and record.get('suppressed'):
        # Restore only the values this overlay still owns.
        if not bool(native.bVisible):native.SetVisibility(record['visible'],False)
        if bool(native.bHiddenInGame):native.SetHiddenInGame(record['hidden'],False)
        if int(native.VisibilityBasedAnimTickOption)==0:
            native.VisibilityBasedAnimTickOption=record['tick']
    component=record['component']()
    if component is not None:
        component.SetLeaderPoseComponent(None,True,False)
        component.K2_DestroyComponent(component.GetOwner())


def hold(saved,camera,pawn,source,mesh):
    import unrealsdk
    diagnostics=saved.setdefault('weapon_arm_status',{})
    try:
        native=camera.CameraModeState.Inputs.AttachComponent
        if (native is None or str(native.GetOwner())!=str(pawn)
                or str(getattr(native,'Name',''))!='FirstPersonArms'):
            release(saved);diagnostics['status']='native_arms_unavailable';return False
        parts=arm_parts(mesh)
        # A mesh-specific accepted rig takes precedence even when the body
        # exposes modular parts. Part-only lookup previously skipped it.
        authored=definition(parts,mesh)
        if authored is None:
            queue_source(source,mesh,parts,diagnostics)
            release(saved);diagnostics['status']='requires_native_bind_mesh' if parts else 'requires_authored_arm_mesh';return False
        signature=(str(source),str(native),tuple(str(part) for part in parts),authored['mesh'])
        if saved.get('weapon_arm_failed_signature')==signature:return False
        if saved.get('weapon_arm_missing_asset')==authored['mesh']:return False
        record=saved.get('weapon_arm_overlay')
        if record is not None and record['signature']!=signature:
            release(saved);record=None
        if record is None:
            asset=load_mesh(authored)
            if asset is None:
                saved['weapon_arm_missing_asset']=authored['mesh']
                diagnostics.update(status='authored_pack_not_loaded',mesh=authored['mesh'])
                return False
            transform=unrealsdk.make_struct('Transform')
            transform.Rotation.W=1.;transform.Scale3D.X=transform.Scale3D.Y=transform.Scale3D.Z=1.
            result=pawn.AddComponentByClass(unrealsdk.find_class('GbxSkeletalMeshComponent'),True,transform,False)
            component=result[0] if isinstance(result,(tuple,list)) else result
            if component is None:raise ValueError('Could not create local arm component')
            record={'signature':signature,'component':WeakPointer(component),'native':WeakPointer(native),
                    'visible':bool(native.bVisible),'hidden':bool(native.bHiddenInGame),
                    'tick':int(native.VisibilityBasedAnimTickOption),'suppressed':False,'checks':0,
                    'material_slots':authored['material_slots'],'bone_count':authored['bone_count'],
                    'surface_cache':{},
                    'shoulder_morphs':authored.get('shoulder_morphs')}
            saved['weapon_arm_overlay']=record
            component.SetVisibility(False,False);component.SetHiddenInGame(True,False)
            component.ComponentTags=list(component.ComponentTags)+[TAG]
            component.SetCollisionEnabled(0);component.SetOnlyOwnerSee(True)
            component.SetOwnerNoSee(False);component.SetCastShadow(False)
            component.SetIsReplicated(False)
            # Direct leader posing an NPC-bind mesh collapses its skin even
            # when its sockets match. Only use a verified native-bind mesh.
            component.SetSkeletalMeshAsset(asset)
            if not component.K2_AttachToComponent(native,'',2,2,2,False):
                raise ValueError('Cannot attach swapped weapon arms')
            component.SetLeaderPoseComponent(native,True,False)
            component.VisibilityBasedAnimTickOption=0
            component.SetComponentTickEnabled(True)
            for field in ('FirstPersonPrimitiveType','bIsViewModel','bUseViewModelDepth'):
                if hasattr(native,field) and hasattr(component,field):
                    setattr(component,field,getattr(native,field))
            diagnostics.update(status='waiting_for_pose',parts=len(parts))
            return False
        component=record['component']()
        if component is None:raise ValueError('Local arm component expired')
        record['checks']+=1
        if component.GetSkinnedAsset() is None:
            if record['checks']>60:raise ValueError('Arm mesh did not finish building')
            return False
        if int(component.GetNumBones())!=record['bone_count']:
            raise ValueError('Authored arm skeleton differs from validated bone count')
        if not sync_surfaces(component,mesh,native,record['material_slots'],record.setdefault('surface_cache',{})):
            diagnostics['status']='waiting_for_surfaces'
            if record['checks']>60:raise ValueError('Arm part/material mapping not ready')
            return False
        errors={}
        for bone in _ANCHORS:
            if int(component.GetBoneIndex(bone))<0 or int(native.GetBoneIndex(bone))<0:
                raise ValueError('Missing weapon-arm anchor '+bone)
            a,b=component.GetSocketLocation(bone),native.GetSocketLocation(bone)
            errors[bone]=math.dist([float(getattr(a,v)) for v in 'XYZ'],[float(getattr(b,v)) for v in 'XYZ'])
        if any(not math.isfinite(error) or error>1. for error in errors.values()):
            if record['checks']>15:raise ValueError('Swapped weapon arms do not follow native hand pose')
            diagnostics.update(status='waiting_for_pose',errors_cm=errors)
            return False
        sync_shoulders(component,mesh,native,camera,record.get('shoulder_morphs'),diagnostics)
        component.SetVisibility(True,False);component.SetHiddenInGame(False,False)
        native.VisibilityBasedAnimTickOption=0
        if record.get('trial_keep_native_parent_visible'):
            native.SetVisibility(True,False);native.SetHiddenInGame(False,False)
        else:
            native.SetVisibility(False,False);native.SetHiddenInGame(True,False)
        record['suppressed']=True
        diagnostics.update(status='ready',errors_cm=errors,materials_copied=int(component.GetNumMaterials()),
                           foreground=bool(component.bGbxForeground),error=None)
        return True
    except Exception as exc:
        failed=locals().get('signature')
        release(saved)
        if failed is not None:saved['weapon_arm_failed_signature']=failed
        diagnostics.update(status='native_fallback',error=str(exc))
        return False
