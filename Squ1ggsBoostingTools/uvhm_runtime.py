"""Game-thread owner for the staged UVHM progression workflow."""
from __future__ import annotations

import time
from typing import Any

from mods_base import get_pc
from unrealsdk import logging

from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate
from .uvhm_progression import (
    Phase,
    UVHMProgression,
    UnrealChallengeBackend,
    POST_FINAL_GRACE_POLLS,
    PRE_FINAL_GRACE_POLLS,
    RANK_ACTIVATION_GRACE_POLLS,
    resolve_lobby_pc,
    selected_lobby_identity,
    snapshot_lobby_identities,
)

_PREFIX = "[Squ1ggs Boosting Tools | UVHM]"
_machine = UVHMProgression(resolve_lobby_pc, UnrealChallengeBackend(), max_polls=300)
_pending_request: tuple[str, int | None, bool, int] | None = None
_last_tick_at = 0.0
_last_status_line = ""
_runtime_message = ""
_hook_path = ""
_hook_error = ""
_tick_count = 0
_last_tick_seen_at = 0.0


def _log(message: str) -> None:
    try:
        logging.log(str(message), _PREFIX)
    except Exception:
        pass
    try:
        from . import runtime_log

        runtime_log.note(f"uvhm: {message}")
    except Exception:
        pass


def _wait_progress_fraction(current: Any) -> float:
    """Small bar creep during native settle polls so the UI does not look frozen."""
    phase = current.phase
    poll = max(0, int(current.poll_count or 0))
    if phase == Phase.WAIT_OBJECTIVE:
        grace = max(1, PRE_FINAL_GRACE_POLLS)
        return min(0.35, (poll / grace) * 0.35)
    if phase == Phase.WAIT_FINAL:
        grace = max(1, POST_FINAL_GRACE_POLLS)
        return 0.35 + min(0.35, (poll / grace) * 0.35)
    if phase == Phase.VERIFY_RANK:
        grace = max(1, RANK_ACTIVATION_GRACE_POLLS)
        return 0.72 + min(0.27, (poll / grace) * 0.27)
    if phase in (Phase.INCREMENT_OBJECTIVE, Phase.INCREMENT_FINAL):
        return 0.05
    if phase == Phase.READY:
        return 0.02
    return 0.0


def request_selected(player_index: int, *, max_rank: int = 7) -> bool:
    global _pending_request, _runtime_message
    install()
    # Challenges already prove BP_TickWidget/serial shared ticks work even when
    # unrealsdk PlayerTick add_hook returns false — never block UVHM on that.
    if _machine.running or _pending_request is not None:
        _runtime_message = "Another UVHM workflow or request is already active."
        return False
    rank = max(1, min(7, int(max_rank)))
    _pending_request = ("selected", int(player_index), False, rank)
    _runtime_message = f"Selected-player workflow queued (up to rank {rank})."
    return True


def request_all(*, confirmed: bool, max_rank: int = 7) -> bool:
    global _pending_request, _runtime_message
    install()
    if not confirmed:
        _runtime_message = "All-lobby confirmation was not completed."
        return False
    if _machine.running or _pending_request is not None:
        _runtime_message = "Another UVHM workflow or request is already active."
        return False
    rank = max(1, min(7, int(max_rank)))
    _pending_request = ("all", None, True, rank)
    _runtime_message = f"Confirmed all-lobby workflow queued (up to rank {rank})."
    return True


def cancel() -> bool:
    global _pending_request, _runtime_message
    if _pending_request is not None:
        _pending_request = None
        _runtime_message = "Queued request cancelled."
        return True
    return _machine.cancel()


def resume() -> bool:
    return _machine.resume()


def status() -> dict[str, Any]:
    current = _machine.status()
    message = current.message
    phase = current.phase.value
    max_rank = max(1, int(getattr(_machine, "_max_rank", 7) or 7))
    if _pending_request is not None:
        phase = "queued"
        message = "Queued for the host game tick."
    elif not current.running and _runtime_message:
        message = _runtime_message
    target_count = max(1, int(current.target_count or 1))
    target_number = max(1, int(current.target_number or 1))
    rank = max(0, int(current.rank or 0))
    progress_total = target_count * max_rank
    if phase == Phase.COMPLETE.value:
        progress_index = progress_total
    elif _pending_request is not None:
        progress_index = 0
    else:
        progress_index = min(
            progress_total,
            ((target_number - 1) * max_rank) + max(0, rank - 1) + _wait_progress_fraction(current),
        )
    return {
        "phase": phase,
        "running": bool(current.running or _pending_request is not None),
        "active": bool(current.running or _pending_request is not None),
        "queued": _pending_request is not None,
        "target_mode": current.target_mode,
        "target_number": current.target_number,
        "target_count": current.target_count,
        "target_name": current.target_name,
        "rank": current.rank,
        "max_rank": max_rank,
        "progress_index": progress_index,
        "progress_total": progress_total,
        "token": current.token,
        "poll_count": current.poll_count,
        "message": message,
        "can_resume": current.phase == Phase.CANCELLED,
        "results": current.results,
        "hook_ready": bool(_hook_path),
        "hook_path": _hook_path,
        "hook_error": _hook_error,
        "tick_count": _tick_count,
        "tick_age": (
            max(0.0, time.monotonic() - _last_tick_seen_at)
            if _last_tick_seen_at > 0.0
            else None
        ),
    }


def _consume_request() -> None:
    global _pending_request, _runtime_message
    request = _pending_request
    if request is None:
        return
    _pending_request = None
    world, _gs = _gbc_session_world_and_gamestate()
    if not _gbc_is_listen_host_world(world):
        _runtime_message = "Request refused: this tool must run on the listen host."
        _log(f"UVHM {_runtime_message}")
        return
    mode, player_index, confirmed, max_rank = request
    try:
        if mode == "selected":
            if player_index is None:
                raise ValueError("No selected player index.")
            _machine.start_selected(selected_lobby_identity(player_index), max_rank=max_rank)
        else:
            _machine.start_all(snapshot_lobby_identities(), confirmed=confirmed, max_rank=max_rank)
        _runtime_message = ""
        if max_rank >= 7:
            _log(f"Started {mode} UVHM ranks 1-7 workflow.")
        else:
            _log(f"Started {mode} UVHM workflow up to rank {max_rank}.")
    except Exception as exc:
        _runtime_message = f"Could not start workflow: {exc}"
        _log(f"UVHM {_runtime_message}")


def _is_host_tick_context(args: tuple[Any, ...]) -> bool:
    """Reject remote PlayerController ticks on a listen host."""
    try:
        host_pc = get_pc()
    except Exception:
        host_pc = None
    if host_pc is None:
        return True
    try:
        host_ps = getattr(host_pc, "PlayerState", None)
    except Exception:
        host_ps = None
    for candidate in args[:2]:
        try:
            cls = str(getattr(getattr(candidate, "Class", None), "Name", "")).casefold()
        except Exception:
            cls = ""
        if "playercontroller" not in cls:
            continue
        if candidate is host_pc:
            return True
        try:
            return host_ps is not None and getattr(candidate, "PlayerState", None) is host_ps
        except Exception:
            return False
    return True


def _tick(*args: Any, **_kwargs: Any) -> None:
    global _last_tick_at, _last_status_line, _tick_count, _last_tick_seen_at
    if not _is_host_tick_context(args):
        return
    now = time.monotonic()
    if now - _last_tick_at < 0.12:
        return
    _last_tick_at = now
    _last_tick_seen_at = now
    _tick_count += 1
    try:
        from .session_guards import session_safe

        if not session_safe():
            # Do not cancel queued/running UVHM on brief menu/inventory flicker.
            return
    except Exception:
        pass
    if _pending_request is not None:
        _consume_request()
        return
    if not _machine.running:
        return
    current = _machine.tick()
    line = (
        f"{current.phase.value}|{current.target_name}|{current.rank}|"
        f"{current.token}|{current.message}"
    )
    if line != _last_status_line:
        _last_status_line = line
        _log(
            f"{current.target_name or 'target'} rank={current.rank} "
            f"phase={current.phase.value}: {current.message}"
        )


def runtime_tick(*args: Any, **kwargs: Any) -> None:
    """Public game-thread pump shared by proven Boosting Tools tick owners."""
    _tick(*args, **kwargs)


def install() -> None:
    global _hook_path, _hook_error
    if _hook_path:
        return
    # serial_rewards owns the package's proven BP_TickWidget dispatcher and
    # always pumps runtime_tick. Registering another hook here doubles Python
    # entry overhead every HUD frame.
    _hook_path = "shared:serial_rewards:BP_TickWidget"
    _hook_error = ""
    _log(
        "UVHM using shared serial-delivery UMG tick."
    )


install()
