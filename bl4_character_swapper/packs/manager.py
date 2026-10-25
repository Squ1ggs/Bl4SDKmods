"""One pack service for the standalone and EXE; all game work stays on ticks."""
from collections import deque
from threading import Lock
import math
import sys
from . import registry
from .catalog import menu_name

_controller = None
_requests = deque()
_lock = Lock()
_status = 'Install an Appearance pack, then restart BL4.'
_operation = {'id': 0, 'state': 'idle', 'message': _status}
_runtime_errors = []


def _vehicles_enabled():
    """Standalone entry opts out; embedded SQBT keeps its vehicle service."""
    package = sys.modules.get(__package__.rsplit('.', 1)[0])
    service=sys.modules.get('_squ1ggs_native_appearance_service_v1')
    return bool(getattr(package, 'VEHICLE_PACKS_ENABLED', True) or getattr(service,'vehicle_clients',set()))


def _shared():
    service = sys.modules.get('_squ1ggs_native_appearance_service_v1')
    manager = getattr(service, 'pack_manager', None)
    return manager if manager is not sys.modules[__name__] else None


def activate(controller):
    global _controller, _status
    from ..runtime import Model
    from .catalog import menu_name, game_family, source_name, character_role
    _controller = controller
    service = sys.modules.get('_squ1ggs_native_appearance_service_v1')
    if service is not None:
        service.pack_manager = sys.modules[__name__]
    installed = registry.discover()
    for key in list(controller.models):
        if key.startswith('pack:installed:'):
            controller.unregister_model(key)
    for row in installed:
        if (row['kind'] != 'character' or row['model'].get('effect_only')
                or row['id'] in ('custom_cortana_halo3','custom_spiderman_classic','custom_spiderman_2099','noble_six_haloreach')):
            continue
        model_id = row['id']
        def spawn(model_id=model_id):
            from . import imported_models
            return imported_models.spawn(model_id)
        controller.register_model(Model('pack:installed:' + model_id, menu_name(row['name']), ('Other characters' if game_family(row['source_game']) == 'Other games' else source_name(row['source_game'])),
                                        row['author'], spawn=spawn, apply_enabled=row['apply_enabled'],
                                        game=game_family(row['source_game']), role=row.get('character_role', character_role(row['model'].get('catalog_id', '')))))
    from . import imported_models
    imported_models._models = None
    _status = f"{len(registry.character_models())} character pack(s) installed."
    if _vehicles_enabled():
        _status += f" {len(registry.vehicle_models())} car pack(s) installed."
    rejected = len(registry.snapshot()['errors'])
    if rejected:
        _status += f' {rejected} pack error(s); see pack status.'
    _operation.update(id=_operation['id'] + 1, state='idle', message=_status)
    _runtime_errors.clear()


def vehicle_catalog(payload=None):
    if not _vehicles_enabled():
        return {'ok': True, 'rows': [], 'total': 0, 'message': 'Character-only standalone build.'}
    shared = _shared()
    if shared is not None:
        return shared.vehicle_catalog(payload)
    # Read cached metadata only; bridge catalogs may execute on an HTTP thread.
    search = str((payload or {}).get('search') or '').casefold().split()
    from . import imported_vehicles
    fit = imported_vehicles.choice()
    rows = [{'code': key, 'display_name': menu_name(row.get('display_name') or row['name']), 'scope': row.get('scope', ''),
             'preview_data': row.get('preview_data', ''), 'preview_kind': row.get('preview_kind', 'Generic placeholder'),
             'vehicle_height_cm': fit.get('vehicle_heights', {}).get(key, 0),
             'driver_height_cm': fit.get('driver_offsets', {}).get(key, row.get('driver_visual_offset_cm', [0, 0, 0]))[2],
             'notes': 'Visual car shell; retains native hover driving and static wheels.'}
            for key, row in registry.vehicle_models().items()
            if all(token in (key + ' ' + row['name']).casefold() for token in search)]
    return {'ok': True, 'rows': rows, 'total': len(rows), 'message': _status,
            'pack_errors': registry.snapshot()['errors']}


def request_vehicle(payload=None):
    global _status
    if not _vehicles_enabled():
        return {'ok': False, 'message': 'Vehicle swaps are excluded from BL4 Character Swapper.'}
    shared = _shared()
    if shared is not None:
        return shared.request_vehicle(payload)
    payload = payload or {}
    verb = payload.get('verb', 'preview')
    if verb == 'status':
        return {'ok': True, **status()}
    if verb not in ('preview', 'use', 'summon', 'restore', 'fit'):
        return {'ok': False, 'message': 'Unknown car action.'}
    codes = payload.get('codes', [])
    if verb != 'restore' and (not isinstance(codes, list) or len(codes) != 1 or codes[0] not in registry.vehicle_models()):
        return {'ok': False, 'message': 'Choose one installed car.'}
    if _controller is None or not _controller.enabled:
        return {'ok': False, 'message': 'Enable Appearance first.'}
    options = {}
    if verb == 'fit':
        try:
            options = {key: float(payload.get(field, 0)) for key, field in
                       (('vehicle_height', 'vehicle_height_cm'), ('driver_height', 'driver_height_cm'))}
            if any(not math.isfinite(value) or abs(value) > 200 for value in options.values()):
                raise ValueError()
        except (ValueError, TypeError, OverflowError):
            return {'ok': False, 'message': 'Car and driver heights require finite centimetres within +/-200.'}
    # ImGui can call this: capture cached weak identity without resolving any
    # UObject. Authority, pawn and world are validated on the game-thread tick.
    reference = _controller.player_refs.get('self')
    if verb != 'restore' and reference is None:
        return {'ok': False, 'message': 'Load your character into a map first.'}
    host = str(payload.get('host_vehicle_def') or '') or None
    if host is not None:
        from .vehicle_catalog import HOST_VEHICLE_CHOICES
        if host not in {row[0] for row in HOST_VEHICLE_CHOICES}:
            return {'ok': False, 'message': 'Choose a listed native host vehicle.'}
    with _lock:
        if verb == 'restore':
            _requests.clear()
        elif _requests or _operation['state'] in ('queued', 'running', 'loading'):
            return {'ok': False, 'message': 'Wait for the current car action.'}
        _requests.append((verb, codes[0] if codes else '', host, _controller.world_key, reference, options))
        _status = 'Car action queued.'
        _operation.update(id=_operation['id'] + 1, state='queued', message=_status)
    return {'ok': True, 'message': _status, 'vehicle_operation': dict(_operation)}


def tick():
    global _status
    if _controller is None:
        return
    if registry.character_models():
        from . import imported_models
        try:
            imported_models.tick()
        except Exception as exc:
            _runtime_errors[:] = [str(exc)]
    if not _vehicles_enabled() or not registry.vehicle_models():
        return
    from . import imported_vehicles
    with _lock:
        request = _requests.popleft() if _requests else None
    if request:
        verb, model_id, host, world, reference, options = request
        pawn = getattr(_controller._pc(), 'Pawn', None)
        if verb != 'restore' and (world != str(_controller._world()) or reference is None or reference() is None or str(reference()) != str(pawn)):
            _status = 'Car action cancelled because the player or map changed.'
            _operation.update(state='cancelled', message=_status)
        else:
            _operation.update(state='running')
            try:
                if verb != 'restore' and not pawn.HasAuthority():
                    raise RuntimeError('Only the host can create or apply imported car visuals.')
                if verb == 'restore':
                    result = imported_vehicles.restore()
                elif verb == 'fit':
                    result = imported_vehicles.fit(model_id, **options)
                elif verb in ('use', 'summon'):
                    result = getattr(imported_vehicles, verb)(model_id, host)
                else:
                    result = imported_vehicles.preview(model_id)
                _status = str(result.get('message', 'Car action finished.'))
                _operation.update(state='complete' if result.get('ok') else 'failed', message=_status)
            except Exception as exc:
                _status = str(exc)
                _operation.update(state='failed', message=_status)
    try:
        imported_vehicles.tick()
    except Exception as exc:
        _status = str(exc)
        _operation.update(state='failed', message=_status)
    if _operation['state'] not in ('failed', 'cancelled') and imported_vehicles._state and imported_vehicles._state.get('material_job') is not None:
        _status = imported_vehicles.ui_status()
        _operation.update(state='loading', message=_status)
    elif _operation['state'] == 'loading':
        if not imported_vehicles._state or imported_vehicles._state.get('restoring'):
            _status = 'Car loading cancelled because its visual was removed. Retry after checking the player and map.'
            _operation.update(state='cancelled', message=_status)
        else:
            _status = imported_vehicles.ui_status()
            _operation.update(state='complete', message=_status)


def cleanup():
    global _status
    with _lock:
        _requests.clear()
    _status = 'Map changed or Appearance disabled; car requests cancelled.'
    _operation.update(state='cancelled', message=_status)
    if registry.vehicle_models():
        from . import imported_vehicles
        imported_vehicles._requests.clear()
        try:
            imported_vehicles.restore()
        except Exception as exc:
            _runtime_errors[:] = [str(exc)]
    if registry.character_models():
        from . import imported_models
        imported_models.clear_previews()
        for key in list(imported_models._actors):
            imported_models._forget_actor(key)


def restore_vehicle():
    """Release only vehicle visuals when a vehicle frontend is disabled."""
    shared=_shared()
    if shared is not None:return shared.restore_vehicle()
    with _lock:_requests.clear()
    from . import imported_vehicles
    imported_vehicles._requests.clear()
    imported_vehicles.restore()


def status():
    shared = _shared()
    if shared is not None:
        return shared.status()
    return {**registry.snapshot(), 'message': _status, 'vehicle_operation': dict(_operation),
            'runtime_errors': list(_runtime_errors)}
