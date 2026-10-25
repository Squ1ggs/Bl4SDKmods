"""Local, reversible imported vehicle visuals; native driving remains untouched."""
from __future__ import annotations
from .registry import state_path

import argparse
import json
import math
import re
import time
from collections import deque
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).parent
_state: dict[str, Any] | None = None
_retained: dict[str, Any] = {}
_surface_paths: dict[str, str] = {}
_last_tick = 0.0
_choice: dict | None = None
_requests: deque = deque(maxlen=8)
_ui_status = 'Choose a vehicle, then summon or use it.'
_auto_failure: dict = {}
_runtime_failure = ''
_driver_visual = None
_last_summon = 0.0
_drivable_state: dict[str, Any] | None = None
from .vehicle_catalog import HOST_VEHICLE_CHOICES as _HOST_VEHICLE_CHOICES
_HOST_VEHICLE_IDS = frozenset(row[0] for row in _HOST_VEHICLE_CHOICES)


def choice() -> dict:
    global _choice
    if _choice is None:
        path = state_path()
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            vehicle_id = saved.get('id', 'warthog_fh6')
            if not isinstance(vehicle_id, str) or not re.fullmatch(r'[a-z0-9_]{1,80}', vehicle_id):
                raise ValueError('Invalid saved vehicle ID')
            hosts = saved.get('host_vehicle_defs', {})
            if not isinstance(hosts, dict):
                hosts = {}
            hosts = {str(key): str(value) for key, value in hosts.items()
                     if key in vehicles()
                     and value in _HOST_VEHICLE_IDS}
            _choice = {'enabled': saved.get('enabled') is True, 'id': vehicle_id,
                       'host_vehicle_defs': hosts, 'driver_anchors': saved.get('driver_anchors', {}) if isinstance(saved.get('driver_anchors', {}), dict) else {},
                       'vehicle_heights': {key: float(value) for key, value in saved.get('vehicle_heights', {}).items()
                           if key in vehicles() and type(value) in (int, float) and math.isfinite(value) and abs(value) <= 200},
                       'driver_offsets': {key: _vector(value, 200) for key, value in saved.get('driver_offsets', {}).items()
                           if key in vehicles()}}
        except (OSError, ValueError, TypeError, AttributeError):
            _choice = {'enabled': False, 'id': 'warthog_fh6', 'host_vehicle_defs': {}}
    return dict(_choice)


def _save_choice(enabled: bool, vehicle_id: str = 'warthog_fh6', host_vehicle_def: str | None = None) -> None:
    global _choice, _auto_failure, _runtime_failure
    hosts = dict(choice().get('host_vehicle_defs', {}))
    if host_vehicle_def is not None:
        if host_vehicle_def not in _HOST_VEHICLE_IDS:
            raise ValueError('Choose a listed personal vehicle as the host.')
        hosts[vehicle_id] = host_vehicle_def
    saved = {'enabled': enabled, 'id': vehicle_id, 'host_vehicle_defs': hosts,
             'vehicle_heights': choice().get('vehicle_heights', {}),
             'driver_offsets': choice().get('driver_offsets', {}), 'driver_anchors': choice().get('driver_anchors', {})}
    path = state_path()
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(saved, indent=2), encoding='utf-8')
    temporary.replace(path)
    _choice, _auto_failure = saved, {}
    _runtime_failure = ''


def request_action(action: str, vehicle_id: str | None = None, host_vehicle_def: str | None = None) -> None:
    """UI schedules work for the existing game-thread bridge tick."""
    global _ui_status
    if action not in ('use', 'summon', 'preview', 'restore'):
        raise ValueError('Unknown vehicle appearance action')
    if vehicle_id is not None and vehicle_id not in vehicles():
        raise ValueError('Choose an installed vehicle from the list.')
    if host_vehicle_def is not None and host_vehicle_def not in _HOST_VEHICLE_IDS:
        raise ValueError('Choose a listed personal vehicle as the host.')
    request = (action, vehicle_id, host_vehicle_def)
    if request not in _requests:
        _requests.append(request)
    _ui_status = 'Vehicle action queued.'


def ui_status() -> str:
    selected = choice()
    if _ui_status == 'Choose a vehicle, then summon or use it.' and selected['enabled']:
        row = vehicles().get(selected['id'], {})
        name = row.get('name', 'vehicle')
        if row.get('scope') == 'chaos_wheeled_candidate':
            return f'Saved {name} candidate. Summon and enter the personal Borg as host; wheel conversion is unverified.'
        host = _effective_vehicle_def(row, selected['id'])
        return f'Saved {name} appearance. Enter {host or "a Grazer or Borg"} as host.'
    return _ui_status


def use(vehicle_id: str = 'warthog_fh6', host_vehicle_def: str | None = None) -> dict:
    global _ui_status
    row = _row(vehicle_id)
    if row.get('scope') == 'chaos_wheeled_candidate':
        _save_choice(True, vehicle_id, host_vehicle_def)
        vehicle = _driven()
        if vehicle is None or not vehicle.HasAuthority():
            _ui_status = row['name'] + ' selected. Summon the selected vehicle, then enter it as host to apply the car mesh and wheel setup.'
            return {'ok': True, 'message': _ui_status, 'saved_choice': choice()}
        return drive(vehicle_id)
    _save_choice(True, vehicle_id, host_vehicle_def)
    native_def = _effective_vehicle_def(row, vehicle_id)
    if native_def:
        _ui_status = f"{row['name']} selected. Summon and enter {native_def}; native movement stays active and imported wheels are static."
    else:
        _ui_status = row['name'] + ' selected. Enter a Grazer or Borg; it stays visible when parked.'
    _auto_apply_selected()
    return {'ok': True, 'message': _ui_status, 'saved_choice': choice(), 'host_vehicle_def': native_def}


def _effective_vehicle_def(row: dict, vehicle_id: str) -> str | None:
    return choice().get('host_vehicle_defs', {}).get(vehicle_id) or row.get('native_vehicle_def')


def _host_row(row: dict, vehicle_id: str) -> dict:
    effective = dict(row)
    selected = _effective_vehicle_def(row, vehicle_id)
    if selected:
        effective['native_vehicle_def'] = selected
        stem = selected[3:] if selected.startswith('PV_') else selected
        effective['native_vehicle_mesh_tokens'] = [f'SK_Vehicle_Personal_{stem}']
    return effective


def host_vehicle_choices() -> tuple[tuple[str, str, str], ...]:
    """Stable display choices for the shared host selector, grouped by category."""
    return _HOST_VEHICLE_CHOICES


def _wheel_profile(row: dict) -> dict:
    profile = row.get('vehicle_physics')
    if not isinstance(profile, dict):
        raise RuntimeError('This vehicle has no reviewed wheel setup profile.')
    bones = profile.get('wheel_bones')
    if not isinstance(bones, list) or len(bones) != 4 or len(set(bones)) != 4:
        raise RuntimeError('Vehicle must define exactly four unique Chaos wheel bones.')
    radius = profile.get('wheel_radius_cm')
    if not isinstance(radius, (int, float)) or not math.isfinite(float(radius)) or not 10 <= float(radius) <= 100:
        raise RuntimeError('Vehicle wheel radius must be reviewed and between 10 and 100 cm.')
    return {'wheel_bones': [str(name) for name in bones], 'wheel_radius_cm': float(radius)}


def _restore_drivable() -> dict:
    global _drivable_state
    saved, _drivable_state = _drivable_state, None
    if saved is None:
        return {'ok': True, 'message': 'No drivable conversion is active.'}
    errors: list[str] = []
    movement = saved['movement']()
    mesh_component = saved['component']()
    if movement is not None:
        try:
            movement.EnableMechanicalSim(bool(saved['mechanical']))
            movement.EnableSuspension(bool(saved['suspension']))
            movement.EnableWheelFriction(bool(saved['friction']))
            movement.bHoverSimEnabled = bool(saved['hover'])
            setups = []
            import unrealsdk
            for item in saved['wheel_setups']:
                offset = unrealsdk.make_struct('Vector', X=item['offset'][0], Y=item['offset'][1], Z=item['offset'][2])
                setups.append(unrealsdk.make_struct('ChaosWheelSetup', WheelClass=item['class'],
                    BoneName=item['bone'], AdditionalOffset=offset))
            movement.WheelSetups = setups
            for index, radius in enumerate(saved['radii']):
                movement.SetWheelRadius(index, radius)
        except Exception as exc:
            errors.append('movement restore: ' + str(exc))
    if mesh_component is not None:
        try:
            mesh_component.SetSkeletalMeshAsset(saved['mesh'])
            for index, material in saved.get('materials', []):
                mesh_component.SetMaterial(index, material)
            import unrealsdk
            rot = saved['rotation']
            mesh_component.K2_SetRelativeRotation(
                unrealsdk.make_struct('Rotator', Pitch=rot[0], Yaw=rot[1], Roll=rot[2]),
                False, unrealsdk.make_struct('HitResult'), True)
        except Exception as exc:
            errors.append('mesh restore: ' + str(exc))
    if not errors:
        vehicle = saved.get('vehicle')
        actor = vehicle() if vehicle is not None else None
        if actor is not None:
            _retained.pop(str(actor), None)
    if errors:
        _drivable_state = saved
        return {'ok': False, 'message': 'Drivable vehicle restore is pending.', 'errors': errors}
    return {'ok': True, 'message': 'Native vehicle mesh and hover settings restored.'}


def drive(vehicle_id: str) -> dict:
    """Reconfigure the locally driven OakVehicle's existing Chaos wheel solver."""
    global _drivable_state, _ui_status
    import unrealsdk
    from unrealsdk.unreal import WeakPointer
    from . import engine as oak
    vehicle = _driven()
    if vehicle is None or not vehicle.HasAuthority():
        raise RuntimeError('Enter the supported personal vehicle as host before converting it to a car.')
    if _state is not None:
        visual = clear()
        if not visual['ok']:
            raise RuntimeError('Clear the previous vehicle visual before changing the driven mesh.')
    if _drivable_state:
        if str(_drivable_state['vehicle']()) == str(vehicle) and _drivable_state.get('id') == vehicle_id:
            return {'ok': True, 'message': _ui_status, 'active_vehicle': vehicle_id}
        restored = _restore_drivable()
        if not restored['ok']:
            raise RuntimeError(restored['message'])
    row = _row(vehicle_id)
    if row.get('scope') != 'chaos_wheeled_candidate':
        raise RuntimeError('This pack is a visual shell. It has no Chaos vehicle conversion.')
    profile = _wheel_profile(row)
    component = getattr(vehicle, 'VehicleMesh', None) or oak._actor_mesh(vehicle)
    movement = getattr(vehicle, 'VehicleMovementComp', None)
    if movement is None:
        try:
            from .vehicle_engine import _resolve_oak_vehicle_movement_from_vehicle_actor
            hit = _resolve_oak_vehicle_movement_from_vehicle_actor(vehicle)
            movement = hit[1] if hit is not None else None
        except Exception:
            movement = None
    if component is None:
        raise RuntimeError('Driven vehicle has no accessible vehicle mesh component.')
    if movement is None:
        raise RuntimeError('Could not resolve the driven vehicle movement component. Confirm you are seated in the summoned Grazer as host.')
    native_mesh = oak._mesh_asset_for_kind(component)
    if not _native_mesh_matches(native_mesh, row) or not _native_vehicle_def_matches(vehicle, row):
        raise RuntimeError('This conversion only supports the exact personal vehicle mesh listed for this car. Dev vehicle variants are not supported.')
    setups = list(movement.WheelSetups)
    if len(setups) != 4:
        raise RuntimeError('Native Chaos setup must contain exactly four wheel entries.')
    bones = [str(item.BoneName) for item in setups]
    if set(bones) != set(profile['wheel_bones']):
        raise RuntimeError('Imported wheel bones do not match the live Chaos WheelSetups.')
    original_setups = []
    for item in setups:
        off = item.AdditionalOffset
        original_setups.append({'class': item.WheelClass, 'bone': str(item.BoneName),
            'offset': [float(off.X), float(off.Y), float(off.Z)]})
    saved = {
        'id': vehicle_id, 'vehicle': WeakPointer(vehicle), 'component': WeakPointer(component),
        'movement': WeakPointer(movement), 'world': WeakPointer(oak._spawn_context()[2]), 'mesh': native_mesh,
        'rotation': [float(component.RelativeRotation.Pitch), float(component.RelativeRotation.Yaw), float(component.RelativeRotation.Roll)],
        'hover': bool(movement.bHoverSimEnabled), 'mechanical': bool(movement.bMechanicalSimEnabled),
        'suspension': bool(movement.bSuspensionEnabled), 'friction': bool(movement.bWheelFrictionEnabled),
        'wheel_setups': original_setups, 'radii': [80.0] * 4,
        'materials': [(index, component.GetMaterial(index)) for index in range(len(native_mesh.Materials))],
    }
    mesh = _load('SkeletalMesh', row['mesh'])
    if mesh is None:
        raise RuntimeError('Imported vehicle mesh could not be loaded. Restart BL4 after installing its pack.')
    _drivable_state = saved
    try:
        component.SetSkeletalMeshAsset(mesh)
        _prepare_materials(vehicle, row, component=component)
        component.K2_SetRelativeRotation(
            unrealsdk.make_struct('Rotator', Pitch=float(row.get('mesh_pitch_degrees', 0)),
                Yaw=float(row.get('mesh_yaw_degrees', 90)), Roll=float(row.get('mesh_roll_degrees', 0))),
            False, unrealsdk.make_struct('HitResult'), True)
        get_bone_index = getattr(component, 'GetBoneIndex', None)
        if not callable(get_bone_index):
            raise RuntimeError('BL4 does not expose a skeletal wheel-bone check; conversion stopped before enabling physics.')
        missing_bones = [name for name in profile['wheel_bones'] if int(get_bone_index(name)) < 0]
        if missing_bones:
            raise RuntimeError('Imported mesh is missing Chaos wheel bones: ' + ', '.join(missing_bones))
        zero = unrealsdk.make_struct('Vector', X=0.0, Y=0.0, Z=0.0)
        converted = [unrealsdk.make_struct('ChaosWheelSetup', WheelClass=item.WheelClass,
            BoneName=item.BoneName, AdditionalOffset=zero) for item in setups]
        movement.WheelSetups = converted
        for index in range(4):
            movement.SetWheelRadius(index, profile['wheel_radius_cm'])
        movement.bHoverSimEnabled = False
        movement.EnableSuspension(True)
        movement.EnableWheelFriction(True)
        movement.EnableMechanicalSim(True)
        if bool(movement.bHoverSimEnabled) or not bool(movement.bMechanicalSimEnabled):
            raise RuntimeError('BL4 did not accept the requested hover-to-wheel simulation switch.')
    except Exception:
        _restore_drivable()
        raise
    _ui_status = row['name'] + ' wheel conversion applied to the host vehicle. Driving and restore still need in-game confirmation.'
    return {'ok': True, 'message': _ui_status, 'wheel_radius_cm': profile['wheel_radius_cm'],
        'wheel_bones': bones, 'runtime_verified': False}


def restore() -> dict:
    global _ui_status
    _save_choice(False, choice()['id'])
    result = clear()
    converted = _restore_drivable()
    if not converted['ok']:
        return converted
    _ui_status = result['message']
    return result


def summon(vehicle_id: str = 'warthog_fh6', host_vehicle_def: str | None = None) -> dict:
    """Summon the selected native host; imported car shells apply when it is entered."""
    global _last_summon, _ui_status
    from .dev_tools import _gameplay_pc
    from . import vehicle_engine as engine
    pc = _gameplay_pc()
    if pc is None or getattr(pc, 'Pawn', None) is None or not pc.Pawn.HasAuthority():
        raise RuntimeError('Load a map as host before summoning your vehicle.')
    if time.monotonic() - _last_summon < 2:
        raise RuntimeError('Wait a moment before summoning again.')
    use(vehicle_id, host_vehicle_def)
    row = _row(vehicle_id)
    spawn_def = str(_effective_vehicle_def(row, vehicle_id) or 'PV_Grazer')
    entry = engine._resolve_vehicle_spawn_token(spawn_def)
    if entry is None:
        raise RuntimeError(spawn_def + ' is missing from the native vehicle catalog.')
    ok, detail = engine._spawn_personal_vehicle_for_pc(pc, entry['id'], entry=entry)
    if not ok:
        raise RuntimeError('Native vehicle summon failed: ' + detail)
    _last_summon = time.monotonic()
    host_label = str(entry.get('label') or spawn_def)
    if row.get('scope') == 'visual_hover_shell':
        _ui_status = f'{host_label} summon requested for {row["name"]}. Enter that vehicle to apply the car shell.'
    else:
        _ui_status = host_label + ' (' + spawn_def + ') summon requested. Enter it to use the selected vehicle appearance.'
    return {'ok': True, 'message': _ui_status, 'detail': detail, 'requested_vehicle_def': spawn_def,
            'vehicle_id': vehicle_id}


def _auto_apply_selected() -> None:
    global _auto_failure, _ui_status
    selected = choice()
    if not selected['enabled'] or (_state and _state.get('restoring')):
        return
    from . import engine as oak
    vehicle = _driven()
    if vehicle is None or not vehicle.HasAuthority():
        return
    if _state and _state.get('vehicle') is not None and _state['vehicle']() is not None:
        if str(_state['vehicle']()) == str(vehicle) and _state['id'] == selected['id']:
            return
    native = getattr(vehicle, 'VehicleMesh', None) or oak._actor_mesh(vehicle)
    asset = oak._mesh_asset_for_kind(native)
    row = vehicles().get(selected['id'], {})
    if row.get('scope') == 'chaos_wheeled_candidate' and _drivable_state:
        if str(_drivable_state['vehicle']()) == str(vehicle) and _drivable_state.get('id') == selected['id']:
            return
    effective_row = _host_row(row, selected['id'])
    mesh_matches = _native_mesh_matches(asset, effective_row)
    definition_matches = _native_vehicle_def_matches(vehicle, effective_row)
    if not mesh_matches or not definition_matches:
        if row.get('scope') == 'visual_hover_shell':
            found = str(asset).rsplit('.', 1)[-1] if asset is not None else 'unknown mesh'
            _ui_status = (f"Waiting for the exact {effective_row.get('native_vehicle_def', 'personal vehicle')} host "
                f"(current mesh: {found}). Enter the summoned personal vehicle to apply {row.get('name', 'the car')}; dev variants are skipped.")
        return
    key = (str(oak._spawn_context()[2]), str(vehicle), selected['id'])
    if _auto_failure.get('key') == key and (_auto_failure.get('count', 0) >= 3 or time.monotonic() < _auto_failure.get('retry_at', 0)):
        return
    try:
        apply(selected['id'])
        _auto_failure = {}
        if row.get('scope') == 'chaos_wheeled_candidate':
            _ui_status = row['name'] + ' wheel conversion applied. Driving remains unverified until tested in BL4.'
        else:
            _ui_status = row['name'] + ' applied. Native vehicle movement is retained; imported wheels are static.'
    except Exception as exc:
        count = _auto_failure.get('count', 0) + 1 if _auto_failure.get('key') == key else 1
        _auto_failure = {'key': key, 'count': count, 'retry_at': time.monotonic() + 10}
        _ui_status = 'Vehicle appearance could not apply: ' + str(exc)
        from .imported_materials import _save_report
        _save_report('imported_vehicles_last', {'action': 'auto_apply', 'ok': False, 'error': str(exc), 'attempt': count})


def vehicles() -> dict:
    from .registry import vehicle_models
    return vehicle_models()


def _archives(row: dict) -> dict:
    files = {row.get('pak', ''): row.get('sha256', ''), **row.get('containers', {})}
    if len(files) != 3 or {Path(name).suffix.lower() for name in files} != {'.pak', '.utoc', '.ucas'}:
        raise RuntimeError('Vehicle requires exactly three archive hashes.')
    stem = Path(row['pak']).stem
    if any(Path(name).name != name or Path(name).stem != stem or not re.fullmatch(r'[0-9a-f]{64}', digest)
           for name, digest in files.items()):
        raise RuntimeError('Invalid vehicle archive receipt.')
    return files


def _namespace(row: dict) -> str:
    namespace = row.get('namespace', '')
    if not re.fullmatch(r'/Game/ImportedVehicles/[A-Za-z][A-Za-z0-9_]{0,79}/', namespace):
        raise RuntimeError('Invalid vehicle namespace.')
    paths = [row.get('actor_class', ''), row.get('mesh', ''), *row.get('slot_textures', {}).values(),
             *row.get('slot_normals', {}).values(), *row.get('slot_packed', {}).values()]
    if any(not path.startswith(namespace) or '..' in path or '\\' in path for path in paths):
        raise RuntimeError('Vehicle assets must remain inside their recorded namespace.')
    return namespace


def _material_slot_key(value: Any) -> str:
    """Normalize Unreal's imported material suffix before matching recipe slots."""
    key = str(value).strip().casefold()
    return re.sub(r'(?:_?material)+$', '', key)


def _wheel_finish(name: str):
    """Separate wheel rubber from rims, including UE-sanitized material names."""
    key = re.sub(r'[^a-z0-9]+', '', name.casefold())
    if any(token in key for token in ('rubber', 'tire', 'tyre')):
        return (.018, .018, .018, 1), (.92, .92, 0, 1)
    if 'rim' in key or 'wheelneutralpreview' in key:
        return (.42, .43, .44, 1), (.3, .3, .8, 1)
    if 'geometryinspectionneutralgrey' in key:
        return (.22, .23, .24, 1), (.8, .8, 0, 1)
    return None


def pack_ready(row: dict) -> bool:
    from .companion_pak import _game_paks_dir
    from .imported_models import _file_hash_matches
    try:
        _namespace(row)
        files = _archives(row)
        game = _game_paks_dir()
        return game is not None and all(_file_hash_matches(game / name, digest) for name, digest in files.items())
    except (KeyError, TypeError, ValueError, OSError, RuntimeError):
        return False


def allow_path(path: str) -> bool:
    """Scoped loader gate; registry namespace and both archive copies must match."""
    try:
        if not isinstance(path, str) or '..' in path or '\\' in path or ':' in path:
            return False
        return any(path.startswith(_namespace(row)) and pack_ready(row) for row in vehicles().values())
    except (TypeError, ValueError, OSError, RuntimeError):
        return False


def _load(kind: str, path: str) -> Any:
    from .imported_models import _load as load
    return load(kind, path)


def _row(vehicle_id: str) -> dict:
    rows = vehicles()
    if vehicle_id not in rows:
        raise RuntimeError('No installed vehicle with that ID. Use sqbt_vehicle list.')
    row = rows[vehicle_id]
    if not pack_ready(row):
        raise RuntimeError('Vehicle archives are missing or changed. Install the matching pack and restart BL4.')
    return row


def check(vehicle_id: str = 'warthog_fh6') -> dict:
    row = _row(vehicle_id)
    from . import engine as oak
    cls, mesh = _load('Class', row['actor_class']), _load('SkeletalMesh', row['mesh'])
    if cls is None or mesh is None or oak._mesh_asset_for_kind(oak._actor_mesh(cls.ClassDefaultObject)) is None:
        raise RuntimeError('Vehicle actor/mesh is not ready. Restart BL4 after installing the pack.')
    drivable = row.get('scope') == 'chaos_wheeled_candidate'
    result = {'ok': True, 'name': row['name'], 'game_verified': row.get('game_verified', False),
            'saved_choice': choice(),
            'scope': ('Visual swap using native vehicle controls'
                      if drivable else 'Visual swap; native driving and handling stay the same'),
            'message': 'Vehicle appearance is ready.'}
    if _state and _state.get('id') == vehicle_id:
        actor = _state['actor']()
        if actor is not None:
            component = oak._actor_mesh(actor)
            result['live_preview'] = {'actor': str(actor), 'attached_parent': str(actor.GetAttachParentActor()),
                'mesh_rotation': str(component.RelativeRotation), 'mesh_offset': str(component.RelativeLocation),
                'actor_scale': str(actor.GetActorScale3D()), 'restoring': bool(_state.get('restoring')),
                'native_render_components_saved': len(_state.get('visibility', []))}
    return result


def _prepare_materials(actor: Any, row: dict, *, component: Any = None):
    """Yield after each slot so vehicle texture binding can be spread across ticks."""
    appearance_colors = row.get('appearance_colors', {})
    if not row.get('slot_textures') and not appearance_colors and not row.get('slot_color_overrides'):
        # Preserve cooked source materials when neither imported maps nor tint
        # colors were explicitly supplied.
        return
    import unrealsdk
    from mods_base import ObjectFlags
    from . import imported_materials as materials
    from . import engine as oak
    checked = materials._checked_object
    source = checked(_load('MaterialInterface', '/Game/World/Interactives/Lootables/AmmoChest/OrderAmmoChest/Model/MI_Order_AmmoChest_SkelMesh.MI_Order_AmmoChest_SkelMesh'), 'MaterialInterface', 'Native vehicle preview shader')
    info = next((p.ParameterInfo for p in source.TextureParameterValues if str(p.ParameterInfo.Name) == 'BaseColor'), None)
    if info is None:
        raise RuntimeError('Native shader has no BaseColor parameter.')
    normal = checked(_load('Texture2D', '/Game/Common/Texture/Proxy/T_Proxy_N.T_Proxy_N'), 'Texture', 'Native normal proxy')
    packed = checked(_load('Texture2D', '/Game/Common/Texture/Proxy/T_Proxy_Dielectric_C.T_Proxy_Dielectric_C'), 'Texture', 'Native surface proxy')
    if row.get('surface_profile', 'matte') == 'matte':
        rgba = [float(v) for v in row.get('surface_comp_rg', [.95, .95])]
        if len(rgba) != 2 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in rgba):
            raise RuntimeError('Invalid matte surface channels.')
        colour = unrealsdk.make_struct('LinearColor', R=rgba[0], G=rgba[1], B=0, A=1)
        surface_key = _namespace(row) + repr(rgba)
        packed = None
        if surface_key in _surface_paths:
            try:
                packed = checked(unrealsdk.find_object('TextureRenderTarget2D', _surface_paths[surface_key]),
                                 'TextureRenderTarget2D', 'Retained vehicle surface')
            except ValueError:
                pass
        if packed is None:
            library = unrealsdk.find_class('KismetRenderingLibrary').ClassDefaultObject
            packed = checked(library.CreateRenderTarget2D(actor, 16, 16, 2, colour, False, False), 'TextureRenderTarget2D', 'Matte surface')
            library.ClearRenderTarget2D(actor, packed, colour)
            packed.ObjectFlags |= int(ObjectFlags.KEEP_ALIVE)
            _surface_paths[surface_key] = oak._object_path_name(packed)
    component = component or oak._actor_mesh(actor)
    mesh = oak._mesh_asset_for_kind(component)
    mapping = row.get('slot_textures', {})
    rendering_library = unrealsdk.find_class('KismetRenderingLibrary').ClassDefaultObject
    invisible_names = row.get('preview_invisible_slots', [])
    if not isinstance(invisible_names, list) or any(not isinstance(n, str) for n in invisible_names):
        raise RuntimeError('Invalid vehicle invisible material slots.')
    invisible_slots = tuple(str(slot.MaterialSlotName) for slot in mesh.Materials
        if any(_material_slot_key(slot.MaterialSlotName) == _material_slot_key(n) for n in invisible_names))
    invisible = checked(_load('MaterialInterface', '/Game/AI/_Shared/Materials/MI_Color_Invisible.MI_Color_Invisible'),
                        'MaterialInterface', 'Native gauge glass visibility') if invisible_slots else None
    retained, detail_maps, bound_names = [], [], set()
    diagnostics = {'slots': len(mesh.Materials), 'mapped': [], 'tinted': [], 'hidden': [], 'unbound': []}
    total = len(mesh.Materials)
    # Retain each completed batch immediately; Python wrappers alone do not
    # protect Unreal assets while this generator is suspended between ticks.
    _retained[str(actor)] = (retained, normal, packed, detail_maps, invisible)
    source_slots = [str(slot.MaterialSlotName) for slot in mesh.Materials
                    if _material_slot_key(slot.MaterialSlotName).startswith('src_')]
    if source_slots and not any(_material_slot_key(key) == _material_slot_key(name)
                                for key in mapping for name in source_slots):
        raise RuntimeError('No vehicle source slots match the colour mapping: ' + ', '.join(source_slots))
    finish_surfaces = {}
    for index, slot in enumerate(mesh.Materials):
        name = str(slot.MaterialSlotName)
        normalized_name = _material_slot_key(name)
        matches={path for key,path in mapping.items() if _material_slot_key(key)==normalized_name}
        if len(matches)>1:
            raise RuntimeError('Ambiguous vehicle colour maps for ' + name)
        if name in invisible_slots:
            component.SetMaterial(index, invisible)
            retained.append((index, invisible, None))
            diagnostics['hidden'].append(name)
            yield index + 1, total
            continue
        path = next(iter(matches),'')
        tint = next((value for key, value in appearance_colors.items()
                     if _material_slot_key(key) == normalized_name), None)
        override = [value for key,value in row.get('slot_color_overrides',{}).items()
                    if _material_slot_key(key)==normalized_name]
        if len(override)>1 and any(value!=override[0] for value in override[1:]):
            raise RuntimeError('Ambiguous vehicle lamp colours for '+name)
        if override:
            path=''
            tint=override[0]
        finish = _wheel_finish(name) if not path else None
        if finish is not None:
            # Placeholder wheel maps must not paint the rim as tire rubber.
            path = ''
            tint = finish[0]
        elif not path and tint is None:
            diagnostics['unbound'].append(name)
        if path:
            if not path.startswith(_namespace(row) + 'Textures/'):
                raise RuntimeError('Vehicle colour map outside texture namespace.')
            texture = checked(_load('Texture2D', path), 'Texture', 'Vehicle colour ' + name)
        elif tint is not None:
            rgba = [float(v) for v in tint]
            if len(rgba) == 3:
                rgba.append(1.0)
            if len(rgba) != 4 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in rgba):
                raise RuntimeError('Vehicle appearance colors must be linear RGBA values between 0 and 1.')
            colour = unrealsdk.make_struct('LinearColor', R=rgba[0], G=rgba[1], B=rgba[2], A=rgba[3])
            texture = checked(rendering_library.CreateRenderTarget2D(actor, 16, 16, 2, colour, False, False),
                              'TextureRenderTarget2D', 'Vehicle tint ' + name)
            rendering_library.ClearRenderTarget2D(actor, texture, colour)
            texture.ObjectFlags |= int(ObjectFlags.KEEP_ALIVE)
        else:
            yield index + 1, total
            continue
        if path and not path.startswith(_namespace(row) + 'Textures/'):
            raise RuntimeError('Missing vehicle colour map for ' + name)
        if bool(getattr(texture, 'VirtualTextureStreaming', False)):
            raise RuntimeError('Vehicle colour map must be an ordinary texture.')
        binding=(index, name, texture)
        bound_names.add(name.casefold())
        slot_normal, slot_packed = [], []
        for key, fallback in (('slot_normals', normal), ('slot_packed', packed)):
            matches = {path for slot_name, path in row.get(key, {}).items()
                       if _material_slot_key(slot_name) == normalized_name}
            if len(matches) > 1:
                raise RuntimeError('Ambiguous vehicle detail maps for ' + name)
            detail_path=next(iter(matches), '')
            if detail_path and not detail_path.startswith(_namespace(row) + 'Textures/'):
                raise RuntimeError('Vehicle detail map outside texture namespace.')
            detail=checked(_load('Texture2D', detail_path), 'Texture', 'Vehicle detail ' + name) if detail_path else fallback
            if bool(getattr(detail, 'VirtualTextureStreaming', False)):
                raise RuntimeError('Vehicle detail map must be an ordinary texture.')
            (slot_normal if key=='slot_normals' else slot_packed).append(detail)
        if finish is not None:
            surface_key = finish[1]
            if surface_key not in finish_surfaces:
                colour = unrealsdk.make_struct('LinearColor',
                    R=surface_key[0], G=surface_key[1], B=surface_key[2], A=surface_key[3])
                surface = checked(rendering_library.CreateRenderTarget2D(actor, 16, 16, 2, colour, False, False),
                                  'TextureRenderTarget2D', 'Vehicle wheel surface ' + name)
                rendering_library.ClearRenderTarget2D(actor, surface, colour)
                surface.ObjectFlags |= int(ObjectFlags.KEEP_ALIVE)
                finish_surfaces[surface_key] = surface
            slot_normal[0], slot_packed[0] = normal, finish_surfaces[surface_key]
        retained.extend(materials._bind_colour_maps(component, source, info, [binding], slot_normal[0], slot_packed[0],
            normal_name='Normal', packed_name='Comp', invisible=invisible, invisible_slots=invisible_slots))
        if path:
            diagnostics['mapped'].append(name)
        elif tint is not None:
            diagnostics['tinted'].append(name)
        detail_maps.extend((slot_normal[0], slot_packed[0]))
        yield index + 1, total
    missing_tints = [name for name in appearance_colors
                      if _material_slot_key(name) not in {_material_slot_key(bound) for bound in bound_names}]
    if missing_tints:
        raise RuntimeError('Imported mesh has no matching material slots for vehicle tints: ' + ', '.join(missing_tints))
    _retained[str(actor)] = (retained, normal, packed, detail_maps, invisible)
    return diagnostics


def _vector(values: Any, limit: float = 2000) -> list[float]:
    values = [float(v) for v in values]
    if len(values) != 3 or any(not math.isfinite(v) or abs(v) > limit for v in values):
        raise RuntimeError('Offsets require three finite centimetre values within +/-2000.')
    return values


def _presentation(actor: Any, row: dict, *, attached: bool) -> None:
    import unrealsdk
    from . import engine as oak
    component = oak._actor_mesh(actor)
    rotation = unrealsdk.make_struct('Rotator', Pitch=float(row.get('mesh_pitch_degrees', 0)),
        Yaw=float(row.get('mesh_yaw_degrees', 90)), Roll=float(row.get('mesh_roll_degrees', 0)))
    component.K2_SetRelativeRotation(rotation, False, unrealsdk.make_struct('HitResult'), True)
    # A Character capsule origin is above its floor; native vehicle roots need their own offset.
    xyz = [0, 0, 0] if attached else [0, 0, float(row.get('preview_ground_z_cm', -88))]
    component.K2_SetRelativeLocation(unrealsdk.make_struct('Vector', X=xyz[0], Y=xyz[1], Z=xyz[2]),
                                    False, unrealsdk.make_struct('HitResult'), True)
    component.SetVisibility(True, False)
    component.SetHiddenInGame(False, False)
    component.SetCollisionEnabled(0)


def _vehicle_components(vehicle: Any, kind: str) -> list[Any]:
    """Use the reflected K2 API first; OakVehicle wrappers omit GetComponentsByClass."""
    import unrealsdk
    component_class = unrealsdk.find_class(kind)
    for method_name in ('K2_GetComponentsByClass', 'GetComponentsByClass'):
        method = getattr(vehicle, method_name, None)
        if not callable(method):
            continue
        try:
            return [component for component in list(method(component_class) or []) if component is not None]
        except Exception:
            continue
    raise RuntimeError(f'Cannot enumerate native {kind} components on this vehicle.')


def _spawn(vehicle_id: str, *, defer_materials: bool = False):
    from . import engine as oak
    from .dev_tools import _gameplay_pc, _appearance_mesh_ready
    row = _row(vehicle_id)
    check(vehicle_id)
    pc = _gameplay_pc()
    pawn = getattr(pc, 'Pawn', None) if pc is not None else None
    if pawn is None or not pawn.HasAuthority():
        raise RuntimeError('Load a map as host before spawning the vehicle preview.')
    _, _, world, gs = oak._spawn_context()
    if world is None or gs is None:
        raise RuntimeError('No live world.')
    cls = _load('Class', row['actor_class'])
    capsule = getattr(pawn, 'CapsuleComponent', None)
    # Source scene ground is Z=0. Place it at the player's floor, including custom mesh offsets.
    player_half_height = float(capsule.GetScaledCapsuleHalfHeight()) if capsule is not None else 0
    z_offset = -player_half_height - float(row.get('preview_ground_z_cm', -88))
    transform = oak._spawn_transform(pawn, distance=600, z_offset=z_offset, scale=1)
    actor = oak._spawn_actor_deferred(gs, world, cls, transform, class_name=row['actor_class'])
    if actor is None:
        raise RuntimeError('Vehicle shell did not spawn.')
    try:
        actor.SetReplicates(False)
        actor.SetReplicateMovement(False)
        actor.SetActorEnableCollision(False)
        movement = getattr(actor, 'CharacterMovement', None)
        if movement is not None:
            movement.StopMovementImmediately()
            movement.DisableMovement()
        _presentation(actor, row, attached=False)
        material_job = _prepare_materials(actor, row)
        if not defer_materials:
            for _ in material_job:
                pass
        if not _appearance_mesh_ready(actor, oak._actor_mesh(actor)):
            raise RuntimeError('Vehicle shell has no ready visible mesh.')
        _set_scale(actor, float(row.get('visual_scale', 1)))
    except Exception:
        key = str(actor)
        actor.K2_DestroyActor()
        _retained.pop(key, None)
        raise
    if defer_materials:
        return actor, row, world, material_job
    return actor, row, world


def _set_scale(actor: Any, value: float) -> None:
    import unrealsdk
    if not math.isfinite(value) or not .1 <= value <= 3:
        raise RuntimeError('Visual scale must be between 0.1 and 3.')
    actor.SetActorScale3D(unrealsdk.make_struct('Vector', X=value, Y=value, Z=value))


def _driven() -> Any:
    from .dev_tools import _gameplay_pc
    from .vehicle_engine import _get_driven_vehicle_actor_from_pawn
    pc = _gameplay_pc()
    return _get_driven_vehicle_actor_from_pawn(getattr(pc, 'Pawn', None)) if pc is not None else None


def _native_mesh_matches(asset: Any, row: dict) -> bool:
    if asset is None:
        return False
    value = str(asset).strip().strip("'").casefold()
    object_name = value.rsplit('.', 1)[-1].rsplit('/', 1)[-1].strip("'")
    allowed = {str(token).casefold() for token in row.get('native_vehicle_mesh_tokens', ())}
    return object_name in allowed


def _native_vehicle_def_matches(vehicle: Any, row: dict) -> bool:
    expected = str(row.get('native_vehicle_def') or '').casefold()
    if not expected:
        return True
    try:
        from .vehicle_engine import _vehicle_definition_instances
        definitions = _vehicle_definition_instances(vehicle)
    except Exception:
        return True
    for _, definition in definitions:
        for attribute in ('Name', 'ObjectName', 'DefName', '_experimental_name', 'name'):
            try:
                value = getattr(definition, attribute, None)
            except Exception:
                value = None
            if value:
                value = str(value).strip().strip("'").casefold()
                if value.startswith('pv_'):
                    return value == expected
        match = re.search(r"(?:fgbxdefptr\()?['\"]?(pv_[a-z0-9_]+)", str(definition).casefold())
        if match:
            return match.group(1) == expected
    return True


def clear() -> dict:
    global _state
    driver_restored = _restore_driver_visual()
    saved, _state = _state, None
    errors = [] if driver_restored else ['Driver visual restoration is pending.']
    if saved:
        # Restore render flags before destroying the shell, including partially failed applies.
        pending = []
        for reference, visible, hidden in saved.get('visibility', []):
            component = reference()
            if component is not None:
                try:
                    component.SetVisibility(visible, False)
                    component.SetHiddenInGame(hidden, False)
                except Exception as exc:
                    errors.append(str(exc))
                    pending.append((reference, visible, hidden))
        actor = saved['actor']()
        destroy_pending = False
        if actor is not None:
            try:
                actor.K2_DestroyActor()
            except Exception as exc:
                errors.append(str(exc))
                destroy_pending = True
        if not destroy_pending:
            _retained.pop(saved['actor_key'], None)
        if pending or destroy_pending:
            # Retry restoration from the existing tick; never forget a still-live native component.
            saved['visibility'] = pending
            saved['restoring'] = True
            _state = saved
    return {'ok': not errors, 'message': 'Vehicle visual cleared; native visibility restored.' if not errors else 'Vehicle restore pending.', 'errors': errors}


def preview(vehicle_id: str = 'warthog_fh6') -> dict:
    global _state, _runtime_failure
    _runtime_failure = ''
    from unrealsdk.unreal import WeakPointer
    _save_choice(False, choice()['id'])
    result = clear()
    if not result['ok']:
        raise RuntimeError('Restore the previous vehicle before starting another preview.')
    actor, row, world, material_job = _spawn(vehicle_id, defer_materials=True)
    _state = {'actor': WeakPointer(actor), 'actor_key': str(actor), 'world': WeakPointer(world),
              'vehicle': None, 'visibility': [], 'id': vehicle_id, 'name': row['name'],
              'material_job': material_job, 'materials_done': 0, 'materials_total': 0}
    return {'ok': True, 'message': row['name'] + ' parked preview spawned; materials are loading in short batches. Static wheels; rendering unverified.'}


def apply(vehicle_id: str = 'warthog_fh6') -> dict:
    global _state
    import unrealsdk
    from unrealsdk.unreal import WeakPointer
    from . import engine as oak
    vehicle = _driven()
    if vehicle is None or not vehicle.HasAuthority():
        raise RuntimeError('Enter the supported personal vehicle as host first, then use sqbt_vehicle apply.')
    row = _row(vehicle_id)
    if row.get('scope') == 'chaos_wheeled_candidate':
        return drive(vehicle_id)
    if _drivable_state is not None:
        restored = _restore_drivable()
        if not restored['ok']:
            raise RuntimeError(restored['message'])
    native = getattr(vehicle, 'VehicleMesh', None) or oak._actor_mesh(vehicle)
    asset = oak._mesh_asset_for_kind(native)
    row = _host_row(row, vehicle_id)
    if not _native_mesh_matches(asset, row) or not _native_vehicle_def_matches(vehicle, row):
        expected=row.get('native_vehicle_mesh_tokens', ['the selected personal vehicle mesh'])
        found=str(asset).rsplit('.',1)[-1] if asset is not None else 'unknown mesh'
        raise RuntimeError(f"This car expects {', '.join(expected)}; current vehicle mesh is {found}. Dev variants are skipped.")
    if getattr(vehicle, 'RootComponent', None) is None:
        raise RuntimeError('Vehicle has no root for the visual shell.')
    result = clear()
    if not result['ok']:
        raise RuntimeError('Previous vehicle visibility restoration is pending.')
    actor, row, world, material_job = _spawn(vehicle_id, defer_materials=True)
    _state = {'actor': WeakPointer(actor), 'actor_key': str(actor), 'world': WeakPointer(world), 'name': row['name'],
              'vehicle': WeakPointer(vehicle), 'visibility': [], 'id': vehicle_id,
              'material_job': material_job, 'materials_done': 0, 'materials_total': 0}
    try:
        attached = actor.K2_AttachToComponent(vehicle.RootComponent, 'None', 2, 2, 1, False)
        if attached is False or str(actor.GetAttachParentActor()) != str(vehicle):
            raise RuntimeError('Visual shell attachment did not succeed.')
        _presentation(actor, row, attached=True)
        _state['base_attach_offset'] = _vector(row.get('attach_offset_cm', [0, 0, 0]))
        _state['driver_offset'] = _vector(row.get('driver_visual_offset_cm', [0, 0, 0]), 200)
        xyz = list(_state['base_attach_offset'])
        xyz[2] += choice().get('vehicle_heights', {}).get(vehicle_id, 0)
        offset(*xyz)
        components = [native]
        for kind in ('StaticMeshComponent', 'SkeletalMeshComponent'):
            found = _vehicle_components(vehicle, kind)
            if len(found) > 64:
                raise RuntimeError('Unexpected vehicle render component count.')
            for component in found:
                if str(component.GetOwner()) == str(vehicle) and all(str(component) != str(c) for c in components):
                    components.append(component)
        # Snapshot all native render flags before changing the first component.
        _state['visibility'] = [(WeakPointer(c), bool(c.bVisible), bool(c.bHiddenInGame)) for c in components]
        # Keep the native vehicle visible until every shell material has loaded.
        _state['pending_native_hide'] = True
    except Exception:
        clear()
        raise
    return {'ok': True, 'message': row['name'] + ' attached; materials are loading in short batches. Native hover physics/collision retained; wheels and turret are static.'}


def offset(x: float, y: float, z: float) -> dict:
    import unrealsdk
    xyz = _vector((x, y, z))
    actor = _state['actor']() if _state and not _state.get('restoring') else None
    if actor is None or _state.get('vehicle') is None:
        raise RuntimeError('Apply the vehicle shell before adjusting its attachment offset.')
    actor.RootComponent.K2_SetRelativeLocation(unrealsdk.make_struct('Vector', X=xyz[0], Y=xyz[1], Z=xyz[2]),
                                             False, unrealsdk.make_struct('HitResult'), True)
    return {'ok': True, 'offset_cm': xyz, 'message': 'Temporary visual offset changed; native vehicle untouched.'}


def _advance_material_job() -> None:
    global _ui_status
    if _state is None or _state.get('material_job') is None:
        return
    job=_state['material_job']
    started=time.monotonic()
    finished=False
    for _ in range(24):
        try:
            done,total=next(job)
            _state['materials_done'],_state['materials_total']=done,total
        except StopIteration as completed:
            _state['material_job']=None
            finished=True
            if isinstance(completed.value, dict):
                _state['material_diagnostics'] = completed.value
            break
        if time.monotonic()-started >= .035:
            break
    if finished:
        if _state.get('pending_native_hide'):
            for reference, _, _ in _state['visibility']:
                component = reference()
                if component is None:
                    raise RuntimeError('Native vehicle component disappeared during material loading.')
                component.SetVisibility(False, False)
                component.SetHiddenInGame(True, False)
            _state['pending_native_hide'] = False
        _ui_status=_state.get('name', _state['id']) + ' materials ready.'
        from .imported_materials import _save_report
        _save_report('imported_vehicles_last', {'action':'material_apply','ok':True,
            'vehicle_id':_state['id'],'slots':_state.get('materials_total',0),
            'diagnostics':_state.get('material_diagnostics',{})})
    else:
        _ui_status=(f"Applying {_state.get('name', _state['id'])} materials: "
                    f"{_state.get('materials_done',0)}/{_state.get('materials_total',0)} slots")


def scale(value: float) -> dict:
    actor = _state['actor']() if _state and not _state.get('restoring') else None
    if actor is None:
        raise RuntimeError('Spawn/apply a vehicle preview first.')
    _set_scale(actor, float(value))
    return {'ok': True, 'scale': float(value), 'message': 'Temporary visual scale changed.'}


def tick() -> None:
    global _last_tick, _ui_status, _runtime_failure
    if time.monotonic() - _last_tick < .2:
        return
    _last_tick = time.monotonic()
    if _driver_visual is not None and (_state is None or _state.get('restoring')):
        _restore_driver_visual()
    if _requests:
        action = _requests.popleft()
        try:
            if isinstance(action, tuple) and len(action) == 3:
                action, vehicle_id, host_vehicle_def = action
            elif isinstance(action, tuple) and len(action) == 2:
                action, vehicle_id = action
                host_vehicle_def = None
            else:
                action, vehicle_id, host_vehicle_def = action, None, None
            handler = {'use': use, 'summon': summon, 'preview': preview, 'restore': restore}[action]
            if action in ('use', 'summon') and vehicle_id:
                result = handler(vehicle_id, host_vehicle_def)
            else:
                result = handler(vehicle_id) if vehicle_id and action != 'restore' else handler()
            from .imported_materials import _save_report
            _save_report('imported_vehicles_last', {'action': action, 'result': result})
        except Exception as exc:
            _ui_status = str(exc)
            from .imported_materials import _save_report
            _save_report('imported_vehicles_last', {'action': action, 'ok': False, 'error': str(exc)})
    if _state is None:
        if not _runtime_failure:
            _auto_apply_selected()
    else:
        if _state.get('restoring'):
            clear()
            return
        from . import engine as oak
        from .dev_tools import _appearance_mesh_ready
        try:
            actor, world = _state['actor'](), _state['world']()
            if actor is None or world is None or str(oak._spawn_context()[2]) != str(world):
                clear()
                return
            _advance_material_job()
            if not _appearance_mesh_ready(actor, oak._actor_mesh(actor)) or bool(actor.bHidden):
                clear()
                return
            reference = _state.get('vehicle')
            if reference is not None:
                vehicle = reference()
                selected = choice()
                keep_parked = selected['enabled'] and selected['id'] == _state['id']
                if vehicle is None or (not keep_parked and str(_driven()) != str(vehicle)) or str(actor.GetAttachParentActor()) != str(vehicle):
                    clear()
            _auto_apply_selected()
            _sync_driver_visual()
        except Exception as exc:
            _runtime_failure = 'Vehicle visual failed: ' + str(exc)
            if _state is not None and _state.get('material_job') is not None:
                _runtime_failure = 'Vehicle material apply failed: ' + str(exc)
                from .imported_materials import _save_report
                _save_report('imported_vehicles_last', {'action':'material_apply','ok':False,
                    'vehicle_id':_state.get('id'),'error':str(exc)})
            _ui_status = _runtime_failure
            clear()
            raise RuntimeError(_runtime_failure) from exc
    if _drivable_state is not None:
        try:
            vehicle = _drivable_state['vehicle']()
            selected = choice()
            current_world = None
            from . import engine as oak
            current_world = oak._spawn_context()[2]
            original_world_ref = _drivable_state.get('world')
            original_world = original_world_ref() if original_world_ref is not None else None
            if (vehicle is None or not selected['enabled'] or selected['id'] != _drivable_state['id']
                    or (original_world is not None and str(current_world) != str(original_world))):
                _restore_drivable()
        except Exception:
            _restore_drivable()


def _command(args: argparse.Namespace) -> None:
    from unrealsdk import logging
    from .imported_materials import _save_report
    try:
        if args.action == 'list':
            result = {key: {'name': row['name'], 'game_verified': row.get('game_verified', False)} for key, row in vehicles().items()}
        elif args.action == 'offset':
            if len(args.values) != 3:
                raise RuntimeError('Use sqbt_vehicle offset X Y Z (centimetres).')
            result = offset(*map(float, args.values))
        elif args.action == 'scale':
            if len(args.values) != 1:
                raise RuntimeError('Use sqbt_vehicle scale VALUE.')
            result = scale(float(args.values[0]))
        elif args.action == 'clear':
            result = restore()
        else:
            if len(args.values) > 1:
                raise RuntimeError('Choose one installed vehicle ID.')
            result = {'check': check, 'preview': preview, 'apply': apply, 'use': use, 'summon': summon}[args.action](args.values[0] if args.values else 'warthog_fh6')
        _save_report('imported_vehicles_last', {'action': args.action, 'result': result})
        logging.info('[SQBT vehicles] ' + json.dumps(result, default=str))
    except Exception as exc:
        _save_report('imported_vehicles_last', {'action': args.action, 'ok': False, 'error': str(exc)})
        logging.error('[SQBT vehicles] ' + str(exc))



def _visible_driver_mesh(pawn):
    from . import engine as oak
    from .dev_tools import _controller
    for wear in _controller().worn.values():
        if wear.pawn() == pawn and wear.source() is not None:
            return oak._actor_mesh(wear.source())
    return oak._actor_mesh(pawn)


def fit(vehicle_id, *, vehicle_height=0, driver_height=0):
    global _choice
    if vehicle_id not in vehicles():
        raise ValueError('Choose one installed car.')
    vehicle_height, driver_height = float(vehicle_height), float(driver_height)
    if any(not math.isfinite(v) or abs(v) > 200 for v in (vehicle_height, driver_height)):
        raise ValueError('Car and driver heights require finite centimetres within +/-200.')
    saved = choice()
    saved['vehicle_heights'] = {**saved.get('vehicle_heights', {}), vehicle_id: vehicle_height}
    saved['driver_offsets'] = {**saved.get('driver_offsets', {}), vehicle_id: [0, 0, driver_height]}
    path = state_path()
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(saved, indent=2), encoding='utf-8')
    temporary.replace(path)
    _choice = saved
    if not _restore_driver_visual():
        raise RuntimeError('Fit saved, but previous driver offset could not be restored; retry Restore.')
    if _state and not _state.get('restoring') and _state.get('id') == vehicle_id and _state.get('vehicle'):
        xyz = list(_state.get('base_attach_offset', [0, 0, 0]))
        xyz[2] += vehicle_height
        offset(*xyz)
        _sync_driver_visual()
    return {'ok': True, 'message': 'Car and visible-driver heights saved for this car.',
            'vehicle_height_cm': vehicle_height, 'driver_height_cm': driver_height}


def _hip_height(mesh):
    try:
        bone=_driver_pelvis_bone(mesh)
        if bone is not None:
            height = float(mesh.GetSocketLocation(bone).Z)
            return height if math.isfinite(height) else None
    except Exception:
        pass
    return None


def _restore_driver_visual() -> bool:
    global _driver_visual
    if _driver_visual is None:
        return True
    saved = _driver_visual
    baseline=saved.get('native_baseline')
    if baseline:
        pawn=baseline['pawn']()
        if pawn is not None:
            try:
                current=[float(getattr(pawn.GetBaseTranslationOffset(),a)) for a in 'XYZ']
                if all(abs(a-b)<.01 for a,b in zip(current,baseline['applied'])):
                    import unrealsdk
                    pawn.CacheInitialMeshOffset(
                        unrealsdk.make_struct('Vector',**dict(zip('XYZ',baseline['original']))),
                        unrealsdk.make_struct('Rotator',**dict(zip(('Pitch','Yaw','Roll'),baseline['rotation']))))
            except Exception:return False
    component = saved['component']()
    if component is not None:
        try:
            current = component.RelativeLocation
            xyz = [float(getattr(current, axis)) for axis in 'XYZ']
            # Do not overwrite a newer visual adjustment owned by another feature.
            if all(abs(a-b) < .01 for a, b in zip(xyz, saved['applied'])):
                _set_driver_location(component, saved['original'])
        except Exception:
            return False
    _driver_visual = None
    return True


def _set_driver_location(component: Any, xyz: list) -> None:
    import unrealsdk
    component.K2_SetRelativeLocation(unrealsdk.make_struct('Vector', **dict(zip('XYZ', xyz))),
                                    False, unrealsdk.make_struct('HitResult'), True)


def _remember_standard_driver():
    """Retain only this controller's on-foot character before vehicle possession."""
    global _standard_driver_cache
    from .dev_tools import _gameplay_pc
    from unrealsdk.unreal import WeakPointer
    pc = _gameplay_pc()
    pawn = getattr(pc, 'Pawn', None)
    if pc is not None and pawn is not None and getattr(pawn, 'CharacterMovement', None) is not None and getattr(pawn, 'VehicleMesh', None) is None:
        _standard_driver_cache = (WeakPointer(pc), WeakPointer(pawn))


def _driver_character(pawn):
    """Possession switches to the vehicle; offsets belong to its retained driver."""
    if pawn is None:return None
    is_vehicle = getattr(pawn, 'VehicleMesh', None) is not None or 'vehicle' in str(getattr(getattr(pawn, 'Class', None), 'Name', '')).lower()
    if not is_vehicle:return pawn
    import sys
    service = sys.modules.get('_squ1ggs_native_appearance_service_v1')
    controller = getattr(service, 'controller', None)
    if controller is not None:
        candidate = controller._character_target('self', pawn)
        if candidate is not pawn and getattr(candidate, 'CharacterMovement', None) is not None:
            return candidate
    # Imported appearances use the legacy wearer registry. Match its stable
    # PlayerState owner; never select the first character in a co-op lobby.
    dev=sys.modules.get(globals().get('__package__','')+'.dev_tools')
    pc=dev._gameplay_pc() if dev is not None else None
    owner=getattr(pc,'PlayerState',None) if pc is not None else None
    owner_key=str(owner if owner is not None else pc)
    retained={}
    for state in getattr(dev,'_appearance_states',{}).values():
        candidate=state.get('pawn')
        if pc is not None and state.get('owner_key')==owner_key and candidate is not pawn and getattr(candidate,'CharacterMovement',None) is not None:
            retained[str(candidate)]=candidate
    if len(retained)==1:return next(iter(retained.values()))
    cached = globals().get('_standard_driver_cache')
    if cached and pc is not None and cached[0]() == pc:
        candidate = cached[1]()
        if candidate is not None and getattr(candidate, 'CharacterMovement', None) is not None:
            if str(candidate.GetAttachParentActor()) == str(pawn):
                return candidate
    return None


def _driver_anchor_location(anchor, shell, parent, current, hip_world):
    """Solve a shell-space hip target into the cosmetic mesh's parent space."""
    def rotate(rotation, vector, inverse=False):
        q=[float(getattr(rotation,axis)) for axis in 'XYZW']
        norm=math.sqrt(sum(a*a for a in q))
        if not math.isfinite(norm) or norm<.001:raise ValueError('Invalid fit rotation')
        x,y,z,w=[a/norm for a in q]
        if inverse:x,y,z=-x,-y,-z
        a,b,c=vector
        cross=(y*c-z*b,z*a-x*c,x*b-y*a)
        double=(y*cross[2]-z*cross[1],z*cross[0]-x*cross[2],x*cross[1]-y*cross[0])
        return [vector[i]+2*(w*cross[i]+double[i]) for i in range(3)]
    target=rotate(shell.Rotation,[a*float(getattr(shell.Scale3D,axis)) for a,axis in zip(anchor,'XYZ')])
    delta=[a+float(getattr(shell.Translation,axis))-float(getattr(hip_world,axis))
           for a,axis in zip(target,'XYZ')]
    local=rotate(parent.Rotation,delta,True)
    result=[]
    for i,axis in enumerate('XYZ'):
        scale=float(getattr(parent.Scale3D,axis))
        if not math.isfinite(scale) or abs(scale)<.001:raise ValueError('Invalid fit scale')
        result.append(float(getattr(current,axis))+local[i]/scale)
    if any(not math.isfinite(a) or abs(a)>300 for a in result):
        raise ValueError('Seat anchor exceeds bounded cosmetic adjustment')
    return result

def _native_driver_anchor(pawn, component):
    """Use an exact clip's private cabin anchor only after its pose evaluates."""
    import sys
    service=sys.modules.get('_squ1ggs_native_appearance_service_v1')
    controller=getattr(service,'controller',None)
    from . import engine as oak
    for worn in getattr(controller,'worn',{}).values():
        source=worn.source()
        if source is None or worn.pawn()!=pawn or oak._actor_mesh(source)!=component:continue
        state=worn.visibility_state
        definition=state.get('native_seat_definition') or {}
        anchor=definition.get('vehicle_seat_anchors',{}).get(_state['id'])
        if anchor is None and definition.get('clip_hip_component_cm') is not None:
            # A new exact-rig seat uses the car's measured cabin target, but
            # still waits for that clip's evaluated pelvis before fitting.
            target=choice().get('driver_anchors',{}).get(_state['id'])
            if target is None:target=vehicles().get(_state['id'],{}).get('driver_hip_anchor_cm')
            if target is not None:
                anchor={'hip_shell_cm':target,
                        'clip_hip_component_cm':definition['clip_hip_component_cm']}
        if anchor is None:return False,None
        try:
            saved=state.get('native_seat_clip')
            if not saved or str(component.GetAnimInstance())!=str(saved['instance']()):
                return True,None
            expected=anchor['clip_hip_component_cm']
            hip=component.GetSocketTransform('Hips',2).Translation
            if math.dist([float(getattr(hip,a)) for a in 'XYZ'],expected)>.1:
                return True,None  # Single-node instance exists but still has the old graph's bone cache.
            target=anchor['hip_shell_cm']
            if len(target)!=3 or any(type(a) not in (int,float) or not math.isfinite(a) or abs(a)>200 for a in target):
                raise ValueError('Invalid calibrated cabin anchor')
            shell=oak._actor_mesh(_state['actor']())
            result=_driver_anchor_location(target,shell.GetSocketTransform('',0),
                source.RootComponent.GetSocketTransform('',0),component.RelativeLocation,
                component.GetSocketLocation('Hips'))
            _state.pop('driver_fit_error',None)
            return True,result
        except Exception as exc:
            _state['driver_fit_error']=str(exc)
            return True,None
    return False,None

def _cabin_driver_anchor(pawn, component):
    """Anchor the evaluated visible pelvis to this car, independent of body size."""
    anchor = choice().get('driver_anchors', {}).get(_state['id'])
    if anchor is None:
        anchor = vehicles().get(_state['id'], {}).get('driver_hip_anchor_cm')
    if anchor is None:return False,None
    try:
        target = _vector(anchor, 200)
        bone = _driver_pelvis_bone(component)
        if bone is None:raise ValueError('Driver has no measured pelvis bone; cabin fit skipped')
        from . import engine as oak
        shell = oak._actor_mesh(_state['actor']())
        owner = component.GetOwner()
        location = _driver_anchor_location(target, shell.GetSocketTransform('', 0),
            owner.RootComponent.GetSocketTransform('', 0), component.RelativeLocation,
            component.GetSocketLocation(bone))
        _state.pop('driver_fit_error', None)
        return True,location
    except Exception as exc:
        _state['driver_fit_error'] = str(exc)
        return True,None


def _fit_native_driver(pawn, component, location=None):
    """Fit the cosmetic car to the stock rider; never relocate native hand IK."""
    global _driver_visual
    if _driver_visual is not None:
        # Undo the earlier body-offset approach once, then wait for its bone
        # cache to evaluate at the restored native movement baseline.
        _restore_driver_visual()
        return
    from . import engine as oak
    from unrealsdk.unreal import WeakPointer
    anchor=choice().get('driver_anchors',{}).get(_state['id'])
    if anchor is None:anchor=vehicles().get(_state['id'],{}).get('driver_hip_anchor_cm')
    if anchor is None:return
    shell=oak._actor_mesh(_state['actor']())
    parent=shell.GetAttachParent()
    if parent is None:raise ValueError('Vehicle shell has no attachment parent for native seat fitting')
    bone=_driver_pelvis_bone(component)
    if bone is None:raise ValueError('Stock driver pelvis is unavailable')
    current=[float(getattr(shell.RelativeLocation,a)) for a in 'XYZ']
    saved=_state.get('native_shell_fit')
    if saved and saved['component']()==shell:
        if any(abs(a-b)>.01 for a,b in zip(current,saved['applied'])):return
    else:
        saved={'component':WeakPointer(shell),'original':list(current),'applied':list(current)}
        _state['native_shell_fit']=saved
    # The body-fit solver returns the correction towards the shell. Apply its
    # opposite to the shell so the stock body, steering IK and camera stay put.
    towards=_driver_anchor_location(_vector(anchor,200),shell.GetSocketTransform('',0),
        parent.GetSocketTransform('',0),shell.RelativeLocation,component.GetSocketLocation(bone))
    fitted=[2*a-b for a,b in zip(current,towards)]
    if any(not math.isfinite(a) or abs(a)>300 for a in fitted):raise ValueError('Native shell seat correction is outside bounds')
    _set_driver_location(shell,fitted)
    saved['applied']=fitted
    observations=globals().setdefault('_native_fit_observations',{})
    error=math.dist(current,fitted);previous=observations.get(_state['id'],{})
    observations[_state['id']]={'strategy':'move_shell_keep_native_body_and_IK',
        'last_error_before_cm':error,'smallest_error_cm':min(error,previous.get('smallest_error_cm',error)),
        'samples':previous.get('samples',0)+1,'shell_original':saved['original'],'shell_applied':list(fitted)}


def _sync_driver_visual() -> None:
    global _driver_visual
    vehicle_ref = _state.get('vehicle') if _state and not _state.get('restoring') else None
    vehicle = vehicle_ref() if vehicle_ref is not None else None
    if vehicle is None or str(_driven()) != str(vehicle):
        _restore_driver_visual()
        return
    from .dev_tools import _gameplay_pc
    from . import engine as oak
    from unrealsdk.unreal import WeakPointer
    pc = _gameplay_pc()
    pawn = _driver_character(getattr(pc, 'Pawn', None))
    if pawn is None or not pawn.HasAuthority():
        _restore_driver_visual()
        return
    component = _visible_driver_mesh(pawn)
    if component is None:
        _restore_driver_visual()
        return
    # Drop the on-foot run correction before this fit snapshots the mesh.
    try:
        from ..appearance_visibility import release_fp_body_anchor
        import sys
        service = sys.modules.get('_squ1ggs_native_appearance_service_v1')
        controller = getattr(service, 'controller', None)
        for worn in getattr(controller, 'worn', {}).values():
            if worn.source() is not None and worn.visibility_state is not None:
                release_fp_body_anchor(worn.visibility_state, component)
    except Exception:
        pass
    if (callable(getattr(pawn,'GetBaseTranslationOffset',None)) and component==oak._actor_mesh(pawn)
            and (choice().get('driver_anchors',{}).get(_state['id']) is not None
                 or vehicles().get(_state['id'],{}).get('driver_hip_anchor_cm') is not None)):
        _fit_native_driver(pawn,component)
        return
    saved_shell=_state.pop('native_shell_fit',None)
    if saved_shell:
        shell=saved_shell['component']()
        if shell is not None:
            xyz=[float(getattr(shell.RelativeLocation,a)) for a in 'XYZ']
            if all(abs(a-b)<.01 for a,b in zip(xyz,saved_shell['applied'])):
                _set_driver_location(shell,saved_shell['original'])
    anchored, location = _native_driver_anchor(pawn, component)
    if not anchored:
        anchored, location = _cabin_driver_anchor(pawn, component)
    if anchored:
        if location is None:
            _restore_driver_visual()
            return
        current=[float(getattr(component.RelativeLocation,axis)) for axis in 'XYZ']
        if _driver_visual is not None:
            if _driver_visual['component']() == component:
                # Respect foreign visual changes; retain the true pre-fit pose.
                if any(abs(a-b)>.01 for a,b in zip(current,_driver_visual['applied'])):return
                if any(abs(a-b)>.01 for a,b in zip(current,location)):
                    _set_driver_location(component,location)
                    _driver_visual['applied']=location
                return
            if not _restore_driver_visual():return
        _driver_visual={'component':WeakPointer(component),'original':current,'applied':location}
        _set_driver_location(component,location)
        return
    if _driver_visual is not None:
        if _driver_visual['component']() == component:
            return
        if not _restore_driver_visual():
            return
    delta = _vector(choice().get('driver_offsets', {}).get(_state['id'], _state.get('driver_offset', [0, 0, 0])), 200)
    native_mesh = oak._actor_mesh(pawn)
    if component != native_mesh:
        native_hip, source_hip = _hip_height(native_mesh), _hip_height(component)
        if native_hip is not None and source_hip is not None and abs(native_hip - source_hip) <= 300:
            delta[2] += native_hip - source_hip
    if not any(delta):
        return
    location = component.RelativeLocation
    original = [float(getattr(location, axis)) for axis in 'XYZ']
    applied = [a+b for a, b in zip(original, delta)]
    _driver_visual = {'component': WeakPointer(component), 'original': original, 'applied': applied}
    _set_driver_location(component, applied)

def _driver_pelvis_bone(mesh):
    """Use reviewed imported anatomy, including rigs with numbered bone names."""
    from . import imported_models
    from . import engine as oak
    asset=oak._mesh_asset_for_kind(mesh)
    path=str(asset).split("'")[1] if "'" in str(asset) else str(asset)
    row=next((r for r in imported_models.models().values() if r.get('mesh')==path),{})
    mapped=row.get('driver_pelvis_bone')
    if not mapped:
        try:
            from .. import appearance_visibility
            mapped=appearance_visibility._camera_anatomy(mesh).get('pelvis')
        except (ImportError,AttributeError):pass
    if mapped and int(mesh.GetBoneIndex(mapped))>=0:return mapped
    return next((mesh.GetBoneName(i) for i in range(min(1024,int(mesh.GetNumBones())))
                 if str(mesh.GetBoneName(i)).casefold() in ('hips','hip','pelvis','koshi','b_pelvis')),None)
