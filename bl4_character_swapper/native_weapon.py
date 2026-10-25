"""Opt-in local equipped-gun display on an owned native cosmetic character.

The existing imported-weapon adapter owns renderer copying and weapon changes.
This adapter never equips a weapon or changes firing, ammunition or animation.
"""
from unrealsdk.unreal import WeakPointer
from mods_base import get_pc
import math

def _release_fp_arms(saved):
    if not saved:
        return
    for part in saved.pop('fp_arms', []) or []:
        arm = part['component']()
        if arm is None:
            continue
        try:
            arm.SetOwnerNoSee(part['owner_no_see'])
            if 'visible' in part:
                arm.SetVisibility(part['visible'], False)
            if 'hidden' in part:
                arm.SetHiddenInGame(part['hidden'], False)
            if part.get('tick') is not None:
                arm.VisibilityBasedAnimTickOption = part['tick']
        except Exception:
            try:
                arm.bOwnerNoSee = part['owner_no_see']
            except Exception:
                pass


def _hide_fp_arms(saved, pawn):
    """Hide the native gun arms only after her own hand is holding the gun."""
    if 'fp_arms' not in saved:
        found = []
        try:
            import unrealsdk
            for component in pawn.K2_GetComponentsByClass(unrealsdk.find_class('SkeletalMeshComponent')):
                if component is not None and str(getattr(component, 'Name', '')) == 'FirstPersonArms':
                    found.append(component)
        except Exception:
            found = []
        arm = getattr(pawn, 'FirstPersonArms', None)
        if arm is not None and all(str(arm) != str(item) for item in found):
            found.append(arm)
        saved['fp_arms'] = [{'component': WeakPointer(arm),
                             'owner_no_see': bool(getattr(arm, 'bOwnerNoSee', False)),
                             'visible': bool(getattr(arm, 'bVisible', True)),
                             'hidden': bool(getattr(arm, 'bHiddenInGame', False)),
                             'tick': getattr(arm, 'VisibilityBasedAnimTickOption', None)} for arm in found]
    for part in saved['fp_arms']:
        arm = part['component']()
        if arm is None:
            continue
        try:
            arm.SetOwnerNoSee(True)
            arm.SetVisibility(False, False)
            arm.SetHiddenInGame(True, False)
            # Hidden viewmodel arms must keep posing so a replacement can follow them.
            arm.VisibilityBasedAnimTickOption = 0
            arm.SetComponentTickEnabled(True)
        except Exception:
            try:
                arm.bOwnerNoSee = True
            except Exception:
                pass


def _restore_aim_target(saved):
    # Drop the player aim write. Restoring the default target hands the body
    # back to whatever enemy it was tracking.
    if saved:
        saved.pop('aim_target', None)


def _sync_aim_target(saved, source, player):
    """Point this cosmetic where the player looks. Never hand it back an enemy target."""
    pitch,yaw=getattr(player,'AimPitch',None),getattr(player,'AimYaw',None)
    if not all(isinstance(value,(int,float)) and math.isfinite(float(value)) for value in (pitch,yaw)):
        return
    import unrealsdk
    target=saved.get('aim_target')
    if target is None:
        library=unrealsdk.find_class('GbxRotationBlueprintLibrary').ClassDefaultObject
        channel=unrealsdk.make_struct('GameplayTag',TagName='RotationChannel.Aim')
        target={'source':WeakPointer(source),'library':WeakPointer(library),'channel':channel}
        saved['aim_target']=target
    rotation=unrealsdk.make_struct('Rotator',pitch=max(-89.,min(89.,float(pitch))),
        yaw=max(-180.,min(180.,float(yaw))),roll=0.)
    target['library']().SetRotationTargetRotationLocal(source,target['channel'],rotation)


def _restore_combat_inputs(saved):
    _restore_aim_target(saved)
    previous = saved.get('combat_inputs')
    if previous is None:
        return
    instance = previous['instance']()
    if instance is not None:
        # Remove snapshots only after each successful write, so a transition
        # failure preserves every value still requiring restoration.
        for name, value in list(previous['values'].items()):
            setattr(instance, name, value)
            previous['values'].pop(name)
    saved.pop('combat_inputs', None)


def sync_combat_inputs(state, player, follower):
    """Post-update gun-hold scalars for rigs that already have weapon poses."""
    saved = state.get('native_weapon_preview')
    pose_only = saved is None
    if pose_only:
        saved = state.get('native_weapon_pose')
    if saved is None:
        return False
    try:
        from .packs import imported_models
        source = saved['source']()
        mesh = saved.get('mesh', lambda: None)()
        package = None if pose_only else imported_models._packages.get(saved['key'])
        clone = None if package is None else package['component']()
        native = None if package is None else package['native']()
        pc = get_pc()
        pawn = getattr(pc, 'Pawn', None) if pc is not None else None
        allowed = (state.get('native_weapon_trial') is True and source is not None
                   and mesh is not None and pawn is not None
                   and str(source) != str(pawn) and str(player) != str(follower)
                   and str(source.GetOwner()) == str(pawn)
                   and str(source.GetAttachParentActor()) == str(pawn)
                   and str(mesh.GetOwner()) == str(source)
                   and str(mesh.GetAnimInstance()) == str(follower)
                   and (pose_only or (clone is not None and native is not None
                                      and str(clone.GetOwner()) == str(source))))
        if not allowed:
            _restore_combat_inputs(saved)
            return False
        previous = saved.get('combat_inputs')
        if previous is not None and str(previous['instance']()) != str(follower):
            _restore_combat_inputs(saved)
        previous = saved.setdefault('combat_inputs', {'instance': WeakPointer(follower), 'values': {}})
        from .appearance_visibility import (
            _camera_anatomy, cosmetic_owned_gameplay_weapons, gun_hold_scalars_active,
            player_has_gameplay_weapon)
        row = state.get('native_motion_definition')
        if not row:
            from . import native_motion
            row = native_motion.definition(mesh, state) or {}
        hold = gun_hold_scalars_active(
            player_has_weapon=player_has_gameplay_weapon(pawn),
            cosmetic_armed=bool(cosmetic_owned_gameplay_weapons(source, pawn)),
            hide_unsupported=_camera_anatomy(mesh).get('first_person_weapon_policy') == 'hide_known_unsupported',
            weapon_preview_enabled=row.get('local_weapon_preview_enabled') is True or row.get('source') == 'game_native')
        if not hold:
            _restore_combat_inputs(saved)
            return False
        values = {'HasWeaponPoses': True, 'F_HasWeaponPoses': 1.0,
                  'NoWeaponActive': False, 'bWeaponIsHidden': False}
        for name in ('bWeaponLowered', 'AimEnableAlpha'):
            value = getattr(player, name, None)
            if isinstance(value, (bool, int, float)) and math.isfinite(float(value)):
                values[name] = value
        for name, value in values.items():
            current = getattr(follower, name, None)
            if not isinstance(current, (bool, int, float)):
                continue
            previous['values'].setdefault(name, current)
            setattr(follower, name, value)
        _sync_aim_target(saved,source,player)
        state.pop('native_weapon_combat_error', None)
        return True
    except Exception as exc:
        state['native_weapon_combat_error'] = str(exc)
        try:
            _restore_combat_inputs(saved)
        except Exception as cleanup_exc:
            state['native_weapon_combat_restore_error'] = str(cleanup_exc)
        return False


def _restore_native_tick(saved):
    previous = saved.get('native_tick')
    if previous is not None:
        native = previous['component']()
        if native is not None:
            native.VisibilityBasedAnimTickOption = previous['option']
            if ('only_owner_see' in previous and 'only_owner_applied' in previous
                    and bool(getattr(native,'bOnlyOwnerSee',False))==previous['only_owner_applied']):
                _set_flag(native,'SetOnlyOwnerSee','bOnlyOwnerSee',previous['only_owner_see'])
        saved.pop('native_tick', None)


def _validate_transform(transform):
    for field, axes in (('Translation', 'XYZ'), ('Rotation', 'XYZW'), ('Scale3D', 'XYZ')):
        values = [float(getattr(getattr(transform, field), axis)) for axis in axes]
        if not all(math.isfinite(value) for value in values):
            raise ValueError('Native weapon grip transform is not finite')
        if field == 'Scale3D' and any(abs(value) < .0001 for value in values):
            raise ValueError('Native weapon grip transform has zero scale')


def _set_flag(component, method, attr, value):
    try:
        getattr(component, method)(value)
        return
    except Exception:
        pass
    try:
        setattr(component, attr, value)
    except Exception:
        pass


def _grip_distance(weapon_world, hand_world):
    weapon, hand = weapon_world.Translation, hand_world.Translation
    return math.hypot(float(weapon.X) - float(hand.X), float(weapon.Y) - float(hand.Y), float(weapon.Z) - float(hand.Z))


def _scale_grip(relative, mesh, bone):
    """A scale-100 imported hand would throw a centimetre grip metres away."""
    scale = mesh.GetSocketTransform(bone, 0).Scale3D
    axes = [float(getattr(scale, axis)) for axis in 'XYZ']
    if any(abs(value) < 0.0001 for value in axes):
        raise ValueError('Native weapon grip bone has zero scale')
    translation = relative.Translation
    translation.X = float(translation.X) / axes[0]
    translation.Y = float(translation.Y) / axes[1]
    translation.Z = float(translation.Z) / axes[2]
    return relative


def _identity_grip():
    import unrealsdk
    transform = unrealsdk.make_struct('Transform')
    transform.Translation.X = transform.Translation.Y = transform.Translation.Z = 0
    transform.Rotation.X = transform.Rotation.Y = transform.Rotation.Z = 0
    transform.Rotation.W = 1
    transform.Scale3D.X = transform.Scale3D.Y = transform.Scale3D.Z = 1
    return transform


def _apply_grip(component, relative):
    import unrealsdk
    component.K2_SetRelativeTransform(NewTransform=relative, bSweep=False,
        SweepHitResult=unrealsdk.make_struct('HitResult'), bTeleport=True)


def _follow_native_grip(saved, pawn, mesh, native, component):
    import unrealsdk
    from .native_helpers import _actor_mesh, _unwrap
    player_mesh = _actor_mesh(pawn)
    # Use the anatomical hand: the native weapon helper can be repositioned
    # downstream by arm IK and is not a reliable grip on the cosmetic graph.
    bone = 'R_Hand'
    if (player_mesh is None or str(player_mesh.GetOwner()) != str(pawn)
            or not mesh.DoesSocketExist(bone) or not player_mesh.DoesSocketExist(bone)):
        raise ValueError('Native weapon grip requires both owned hand sockets')
    previous = saved.get('native_tick')
    if previous is not None and str(previous['component']()) != str(native):
        _restore_native_tick(saved)
    if 'native_tick' not in saved:
        saved['native_tick'] = {'component': WeakPointer(native),
                                'option': native.VisibilityBasedAnimTickOption,
                                'only_owner_see':bool(getattr(native,'bOnlyOwnerSee',False))}
    # The hidden leader still needs evaluated firing/recoil bones for the copy.
    native.VisibilityBasedAnimTickOption = 0
    weapon_world = native.GetSocketTransform('', 0)
    hand_world = player_mesh.GetSocketTransform(bone, 0)
    _validate_transform(weapon_world)
    _validate_transform(hand_world)
    # First person parks the shared gun on the camera. That offset is not a
    # hold, so keep the last in-hand grip or sit the gun on the hand itself.
    distance = _grip_distance(weapon_world, hand_world)
    if distance <= 80.0:
        library = unrealsdk.find_object('KismetMathLibrary', '/Script/Engine.Default__KismetMathLibrary')
        if library is None:
            raise ValueError('Native grip transform library unavailable')
        relative = _scale_grip(_unwrap(library.MakeRelativeTransform(weapon_world, hand_world)), mesh, bone)
        _validate_transform(relative)
        saved['hand_grip'] = relative
    elif distance == distance:
        relative = saved.get('hand_grip') or _identity_grip()
        _validate_transform(relative)
    else:
        raise ValueError('Native weapon grip transform is not finite')
    _apply_grip(component, relative)


def _player_gun_renderers(pawn):
    """Every equipped-gun mesh, including the owner-only first-person one."""
    import unrealsdk
    mesh_class = unrealsdk.find_class('SkeletalMeshComponent')
    weapon_class = unrealsdk.find_class('OakWeapon')
    seen = set()
    found = []
    def visit(component, depth):
        if component is None or depth > 6 or str(component) in seen:
            return
        seen.add(str(component))
        try:
            owner = component.GetOwner()
            if (owner is not None and owner.Class._inherits(weapon_class)
                    and component.Class._inherits(mesh_class)):
                found.append(component)
                return
        except Exception:
            pass
        for child in list(getattr(component, 'AttachChildren', ()) or ()):
            visit(child, depth + 1)
    try:
        for component in pawn.K2_GetComponentsByClass(mesh_class):
            visit(component, 0)
    except Exception:
        pass
    arm = getattr(pawn, 'FirstPersonArms', None)
    if arm is not None:
        visit(arm, 0)
    return found


def _show_player_guns(saved):
    if not saved:
        return
    for part in saved.pop('player_guns', []) or []:
        gun = part['component']()
        if gun is None:
            continue
        try:
            gun.SetOwnerNoSee(part['owner_no_see'])
            gun.SetVisibility(part['visible'], False)
            gun.SetHiddenInGame(part['hidden'], False)
        except Exception:
            pass


def _hide_player_guns(saved, pawn):
    """The swapped character's hand gun is the one on screen."""
    known = {str(part['component']()): part for part in saved.get('player_guns') or [] if part['component']() is not None}
    for gun in _player_gun_renderers(pawn):
        if str(gun) in known:
            continue
        known[str(gun)] = {'component': WeakPointer(gun),
                           'visible': bool(getattr(gun, 'bVisible', True)),
                           'hidden': bool(getattr(gun, 'bHiddenInGame', False)),
                           'owner_no_see': bool(getattr(gun, 'bOwnerNoSee', False))}
    saved['player_guns'] = list(known.values())
    for part in saved['player_guns']:
        gun = part['component']()
        if gun is None:
            continue
        try:
            gun.SetOwnerNoSee(True)
            gun.SetVisibility(False, False)
            gun.SetHiddenInGame(True, False)
        except Exception:
            pass


def restore(state):
    release_viewmodel_arms(state)
    saved = state.get('native_weapon_preview')
    if saved is None:
        return
    _release_fp_arms(saved)
    _show_player_guns(saved)
    _restore_combat_inputs(saved)
    _restore_native_tick(saved)
    from .packs import imported_models, imported_weapons
    package = imported_models._packages.get(saved['key'])
    if package is not None:
        imported_weapons.clear(saved['source'](), package)
        imported_models._packages.pop(saved['key'], None)
    state.pop('native_weapon_preview', None)


def body_holds_gun(mesh):
    """True when this rig already has a gun-hold graph. Gunless bosses do not."""
    if mesh is None:
        return False
    try:
        instance = mesh.GetAnimInstance()
    except Exception:
        return False
    if instance is None:
        return False
    try:
        kind = str(getattr(getattr(instance, 'Class', None), 'Name', ''))
    except Exception:
        kind = ''
    if 'GunUser' in kind:
        return True
    for name in ('HasWeaponPoses', 'F_HasWeaponPoses'):
        try:
            if getattr(instance, name) is not None:
                return True
        except Exception:
            continue
    return False


def _player_is_aiming(pawn):
    zoom = getattr(pawn, 'ZoomState', None)
    return bool(getattr(zoom, 'bWantsToZoom', False) or getattr(zoom, 'bPendingZoom', False)
                or int(getattr(zoom, 'State', 0) or 0) != 0)


def _set_hand_gun_visible(state, visible):
    from .packs import imported_models
    saved = state.get('native_weapon_preview') or {}
    package = imported_models._packages.get(saved.get('key'))
    component = package['component']() if package is not None else None
    native = package['native']() if package is not None else None
    if component is not None:
        component.SetVisibility(bool(visible), False)
        component.SetHiddenInGame(not visible, False)
    if native is not None and visible:
        native.SetOwnerNoSee(True)
        native.SetVisibility(False, False)
        native.SetHiddenInGame(True, False)


def show_swapped_arms(source, mesh):
    """Draw the swapped character's own arms. Never the wearer's viewmodel."""
    def reveal(component):
        if component is None:
            return
        try:
            component.SetOwnerNoSee(False)
            component.SetOnlyOwnerSee(True)
            component.SetVisibility(True, False)
            component.SetHiddenInGame(False, False)
        except Exception:
            pass
        try:
            count = int(component.GetNumBones())
        except Exception:
            return
        for index in range(min(count, 1024)):
            try:
                bone = str(component.GetBoneName(index))
            except Exception:
                continue
            folded = bone.casefold()
            if any(word in folded for word in ('ik', 'weapon', 'gun', 'camera')):
                continue
            if not any(word in folded for word in ('arm', 'hand', 'clav', 'shoulder', 'forearm', 'finger', 'wrist', 'elbow', 'palm', 'thumb')):
                continue
            try:
                component.UnHideBoneByName(bone)
            except Exception:
                continue
    reveal(mesh)
    if source is None:
        return
    try:
        import unrealsdk
        for component in source.K2_GetComponentsByClass(unrealsdk.find_class('SkeletalMeshComponent')):
            if component is None or str(getattr(component, 'Name', '')) == 'FirstPersonArms':
                continue
            tags = [str(tag) for tag in (getattr(component, 'ComponentTags', ()) or ())]
            if 'SQBT_HeadShadow' in tags or 'SQBT_LocalWeaponArms' in tags:
                continue
            reveal(component)
    except Exception:
        return


def hide_viewmodel_arms(state, pawn):
    """Keep the wearer's original arms out of view, including while firing."""
    if pawn is None:
        return
    _hide_fp_arms(state.setdefault('viewmodel_arms', {}), pawn)


def release_viewmodel_arms(state):
    _release_fp_arms(state.pop('viewmodel_arms', None))


def _hold_gun(state, pawn, source, mesh):
    """One copy of the equipped gun, parented to her hand."""
    from .packs import imported_models, imported_weapons
    key = 'cosmetic_weapon:' + str(source)
    saved = state.setdefault('native_weapon_preview', {'source': WeakPointer(source), 'key': key})
    saved['mesh'] = WeakPointer(mesh)
    existing = imported_models._packages.get(key)
    if existing is not None and existing.get('bone') != 'R_Hand':
        _restore_native_tick(saved)
        imported_weapons.clear(source, existing)
        imported_models._packages.pop(key, None)
    imported_weapons.prepare(source, {'weapon_bone': 'R_Hand', 'weapon_preview_enabled': True})
    package = imported_models._packages.get(key)
    component = package['component']() if package is not None else None
    native = package['native']() if package is not None else None
    if component is None or native is None:
        return False
    _follow_native_grip(saved, pawn, mesh, native, component)
    component.SetVisibility(True, False)
    component.SetHiddenInGame(False, False)
    component.SetOwnerNoSee(False)
    return True


def update(state, pawn, source, mesh, driving):
    """Her arms stay visible and the equipped gun stays in her hand."""
    try:
        pc = get_pc()
        allowed = (not driving and pawn is not None and source is not None and mesh is not None
                   and str(source) != str(pawn)
                   and pc is not None and str(getattr(pc, 'Pawn', None)) == str(pawn)
                   and str(source.GetAttachParentActor()) == str(pawn)
                   and str(source.GetOwner()) == str(pawn)
                   and str(mesh.GetOwner()) == str(source))
        if not allowed:
            restore(state)
            saved = state.pop('native_weapon_pose', None)
            if saved is not None:
                _restore_combat_inputs(saved)
            release_viewmodel_arms(state)
            return 'player_gun'
        from .packs.imported_weapons import _local_first_person
        first_person = _local_first_person(pawn)
        aiming = first_person and _player_is_aiming(pawn)
        if not body_holds_gun(mesh):
            state['hide_wearer_arms'] = True
            state['native_weapon_trial'] = False
            _set_hand_gun_visible(state, False)
            if first_person:
                hide_viewmodel_arms(state, pawn)
                if aiming:
                    _show_player_guns(state.get('native_weapon_preview'))
                    return 'aiming'
                return 'body'
            release_viewmodel_arms(state)
            _show_player_guns(state.get('native_weapon_preview'))
            return 'body'
        state['hide_wearer_arms'] = False
        held = _hold_gun(state, pawn, source, mesh)
        if aiming:
            # Aim uses the game's own gun, arms and zoom. Her hand copy waits.
            release_viewmodel_arms(state)
            _show_player_guns(state.get('native_weapon_preview'))
            _set_hand_gun_visible(state, False)
            return 'aiming'
        if not held:
            release_viewmodel_arms(state)
            _show_player_guns(state.get('native_weapon_preview'))
            state['native_weapon_trial'] = False
            return 'player_gun'
        if first_person:
            hide_viewmodel_arms(state, pawn)
            show_swapped_arms(source, mesh)
        else:
            release_viewmodel_arms(state)
        _set_hand_gun_visible(state, True)
        preview = state.get('native_weapon_preview')
        if preview is not None:
            _hide_player_guns(preview, pawn)
        pose = state.setdefault('native_weapon_pose', {})
        pose['source'] = WeakPointer(source)
        pose['mesh'] = WeakPointer(mesh)
        state['native_weapon_trial'] = True
        return 'holding_gun'
    except Exception as exc:
        state['native_weapon_error'] = str(exc)
        try:
            restore(state)
        except Exception:
            pass
        return 'player_gun'
