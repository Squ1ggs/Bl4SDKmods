"""Paced, identity-scoped map discovery using the reflected discovery key RPCs.

Location markers and terrain fog are separate. Accepted RPCs do not prove a
remote character saved discovery; never report them as verified visited tiles.
"""
from __future__ import annotations

import time
from typing import Any

from .data_files import read_data_json
from .uvhm_progression import (
    _pc_is_local_host, _pc_matches_identity, resolve_lobby_pc,
    selected_lobby_identity, snapshot_lobby_identities,
)

_job: dict[str, Any] | None = None
_last_tick = 0.0


def _log(message: str) -> None:
    from . import runtime_log
    runtime_log.note("Map discovery: " + message)


def _hold(active: bool) -> None:
    try:
        from . import hold_session
        (hold_session.arm_for_job if active else hold_session.release_job)('map discovery')
    except Exception:
        pass


def is_running() -> bool:
    return bool(_job and _job['phase'] == 'running')


def status() -> dict[str, Any]:
    if not _job:
        return dict(running=False, phase='idle', message='No discovery job.')
    route = {}
    if _job.get('stage') == 'fog':
        from . import map_reveal
        route = map_reveal.status()
    route_done = _job.get('fog_target', 0) + (min(1.0, float(route.get('index', 0)) / max(1, int(route.get('total', 0)))) if route else 0)
    progress = (0.4 + 0.6 * route_done / len(_job['targets'])) if _job.get('stage') == 'fog' else 0.4 * _job['index'] / _job['total']
    return {key: _job[key] for key in ('phase', 'index', 'total', 'accepted', 'failed', 'message')} | {
        'running': is_running(), 'fog_revealed': False, 'persistence_verified': False,
        'progress_percent': 100.0 if _job['phase'] in ('complete', 'partial') else min(99.5, progress * 100),
        'fog_routes': list(_job.get('fog_routes', [])), 'route': route,
    }


def _catalog() -> tuple[str, ...]:
    rows = read_data_json('map_discovery_catalog.json', {}).get('locations', [])
    seen: set[str] = set()
    for row in rows:
        name, parent = str(row.get('name') or ''), str(row.get('parent') or '')
        if not name or name in seen or (parent and parent not in seen):
            raise ValueError('Discovery catalog has an invalid parent order or duplicate.')
        seen.add(name)
    if not seen:
        raise ValueError('Discovery catalog is unavailable.')
    return tuple(str(row['name']) for row in rows)


def start(player_index: int) -> dict[str, Any]:
    global _job
    if is_running():
        return dict(ok=False, message='Map discovery is already running.')
    try:
        from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate
        world, _gs = _gbc_session_world_and_gamestate()
        if not _gbc_is_listen_host_world(world):
            raise ValueError('Map discovery requires the lobby host.')
        targets = tuple(snapshot_lobby_identities()) if player_index == -1 else (selected_lobby_identity(player_index),)
        if not targets or player_index < -1:
            raise ValueError('No valid discovery targets.')
        tokens = _catalog()
        # Resolve every target before queuing any writes.
        for identity in targets:
            pc = resolve_lobby_pc(identity)
            if pc is None or not _pc_matches_identity(pc, identity):
                raise ValueError('A discovery target is unavailable.')
        _job = dict(phase='running', targets=targets, tokens=tokens, index=0,
                    total=len(tokens) * len(targets), accepted=0, failed=0,
                    stage='markers', fog_target=0, fog_routes=[],
                    message='Discovering map locations and safehouses; a main-map reveal route follows. Keep everyone connected; this takes several minutes.')
        _log(_job['message'])
        _hold(True)
        return dict(ok=True, message=_job['message'], discovery=status())
    except Exception as exc:
        return dict(ok=False, message=str(exc))


def cancel() -> None:
    if is_running():
        if _job.get('stage') == 'fog':
            from . import map_reveal
            map_reveal.cancel()
        _job.update(phase='cancelled', message='Map discovery cancelled; sent requests remain applied.')
        _hold(False)
        _log(_job['message'])


def _dispatch(pc: Any, token: str) -> None:
    import unrealsdk
    from unrealsdk.unreal import FGbxDefPtr

    metadata = unrealsdk.find_object('ScriptStruct', '/Script/GbxGame.GbxDiscoveryLocationMetaData')
    if metadata is None:
        raise RuntimeError('Discovery metadata struct is unavailable.')
    proximity = unrealsdk.find_enum('EGbxDiscoveryProximity').Discovered
    if int(proximity) != 2:
        raise RuntimeError('Unexpected discovery enum; refusing the write.')
    key = unrealsdk.make_struct('/Script/GbxGame.GbxDiscoveryDiscoveredKey',
                               AsMetaLocation=FGbxDefPtr(token, metadata))
    # The server method alone executes on the host; guests must receive the
    # typed Client RPC on their own controller. Never use get_pc() as fallback.
    if _pc_is_local_host(pc):
        pc.ServerDiscoveryMakeNonAuthoritativeDiscovery(InLocation=key, InProximity=proximity)
    pc.ClientDiscoveryNotifyLocationDiscoveredStateChanged(
        InLocation=key, InProximity=proximity, InDiscoveringPlayer=pc.PlayerState)


def runtime_tick(*_args: Any, **_kwargs: Any) -> None:
    global _last_tick
    if not is_running() or time.monotonic() - _last_tick < 0.10:
        return
    # Keep restoration and world/identity checks ticking even during a join or
    # travel. Session quiet pauses marker writes, never an owned reveal cleanup.
    if _job.get('stage') == 'fog':
        _last_tick = time.monotonic()
        _tick_fog()
        return
    from .session_guards import session_safe
    from .serial_rewards import _serial_mail_join_quiet
    if not session_safe() or _serial_mail_join_quiet():
        return
    from . import mission_progress, challenge_bulk_runtime, uvhm_runtime
    if mission_progress.is_running() or any(
        st.get('running') or st.get('queued')
        for st in (challenge_bulk_runtime.status(), uvhm_runtime.status())
    ):
        _job['message'] = 'Map discovery paused until other progression jobs finish.'
        return
    _last_tick = time.monotonic()
    try:
        for _ in range(2):
            index = _job['index']
            identity = _job['targets'][index // len(_job['tokens'])]
            pc = resolve_lobby_pc(identity)
            if pc is None or not _pc_matches_identity(pc, identity):
                raise RuntimeError('Discovery target left or changed; no replacement player was boosted.')
            token = _job['tokens'][index % len(_job['tokens'])]
            _dispatch(pc, token)
            _job['accepted'] += 1
            _job['index'] += 1
            if _job['index'] >= _job['total']:
                _job.update(stage='fog', message='Location requests sent; starting the main-map reveal route. Each player returns to their original position.')
                _log(_job['message'])
                return
        _job['message'] = f"Discovering map locations {_job['index']}/{_job['total']} · {identity.display_name}"
        if _job['index'] % 100 == 0:
            _log(_job['message'])
    except Exception as exc:
        _job['failed'] += 1
        _job.update(phase='error', message=f'Discovery stopped at {_job["index"]}/{_job["total"]}: {exc}')
        _hold(False)
        _log(_job['message'])


def _tick_fog() -> None:
    from . import map_reveal
    try:
        if not _job.get('fog_started'):
            identity = _job['targets'][_job['fog_target']]
            map_reveal.start(identity)
            _job['fog_started'] = True
        map_reveal.runtime_tick()
        route = map_reveal.status()
        _job['message'] = f"Map reveal {_job['fog_target']+1}/{len(_job['targets'])} · {route.get('target', '')} · {route.get('message', '')}"
        if route.get('running'):
            return
        _job['fog_routes'].append({key: route.get(key) for key in ('target', 'phase', 'total', 'passes', 'skipped', 'home_restored', 'movement_restored', 'message')})
        if route.get('phase') not in ('complete', 'partial'):
            raise RuntimeError(str(route.get('message') or 'Map reveal stopped.'))
        _job['fog_target'] += 1
        _job['fog_started'] = False
        if _job['fog_target'] < len(_job['targets']):
            return
        partial = any(row.get('phase') != 'complete' for row in _job['fog_routes'])
        _job.update(phase='partial' if partial else 'complete', message=f"Discovery requests sent: {_job['accepted']} locations; main-map reveal route {'partial (blocked stops)' if partial else 'finished'}. Save and reload to confirm the map. Safehouse claims can still require a visit.")
        _hold(False)
        _log(_job['message'])
    except Exception as exc:
        map_reveal.cancel()
        _job['failed'] += 1
        _job.update(phase='partial', message=f"Location discovery sent, but main-map reveal did not finish: {exc}")
        _hold(False)
        _log(_job['message'])
