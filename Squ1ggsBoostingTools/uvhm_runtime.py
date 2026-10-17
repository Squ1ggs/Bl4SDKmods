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
# Sticky terminal text for EXE after fail/complete so the bar does not vanish
# into a blank idle before the host reads the outcome.
_sticky_phase = ""
_sticky_until = 0.0
_hook_path = ""
_hook_error = ""
_tick_count = 0
_last_tick_seen_at = 0.0
_STICKY_SEC = 1.6
_STICKY_COMPLETE_SEC = 2.0
_STICKY_CANCEL_SEC = 1.2
# MAX ALL / Auto re-queue right after complete re-fires FinalChallenge natives
# on settling wrappers → AV 0xffffffffffffffff (UECC …0656275C).
_last_complete_at = 0.0
_POST_COMPLETE_COOLDOWN_SEC = 10.0
# Guests on weak links drop ("Connection lost") when rank-ups land right on top
# of a MAX ALL / cosmetics burst — hold the next queued start briefly.
_start_not_before = 0.0


def defer_start(seconds: float) -> None:
    global _start_not_before
    _start_not_before = max(_start_not_before, time.monotonic() + max(0.0, float(seconds)))


def _post_complete_cooldown_remaining() -> float:
    if _last_complete_at <= 0.0:
        return 0.0
    left = _POST_COMPLETE_COOLDOWN_SEC - (time.monotonic() - _last_complete_at)
    return max(0.0, float(left))


def _block_if_post_complete_cooldown(*, quiet: bool = False) -> bool:
    """True when a start was rejected because UVHM just finished."""
    global _runtime_message
    left = _post_complete_cooldown_remaining()
    if left <= 0.0:
        return False
    wait = int(left) + 1
    _runtime_message = (
        f"UVHM just finished — wait ~{wait}s before starting again "
        "(challenge state is still settling)."
    )
    if not quiet:
        _arm_sticky("error", _runtime_message)
    return True


def _log(message: str) -> None:
    try:
        logging.info(f"{_PREFIX} {message}")
    except Exception:
        pass
    try:
        from . import runtime_log

        runtime_log.note(f"uvhm: {message}")
    except Exception:
        pass


def _intra_rank_fraction(phase: str, poll_count: int, settle_grace: int) -> float:
    """How far through the current rank slot (0..~0.99). Uses real settle polls."""
    p = str(phase or "").strip().lower()
    poll = max(0, int(poll_count or 0))
    grace = max(1, int(settle_grace or 1))
    ratio = min(0.99, poll / grace)
    if p == "ready":
        return 0.02
    if p == "increment_objective":
        return 0.06
    if p == "wait_objective":
        return 0.08 + 0.30 * ratio
    if p == "increment_final":
        return 0.42
    if p == "wait_final":
        # Long Parent settle — this is what looked "stuck at the end".
        return 0.48 + 0.44 * ratio
    if p == "verify_rank":
        return 0.93 + 0.06 * ratio
    if p == "breathe":
        return 0.0
    if p in ("queued",):
        return 0.0
    return 0.10


def _clear_sticky() -> None:
    global _sticky_phase, _sticky_until
    _sticky_phase = ""
    _sticky_until = 0.0


def _arm_sticky(phase: str, message: str) -> None:
    global _sticky_phase, _sticky_until, _runtime_message
    _sticky_phase = str(phase or "error").strip().lower() or "error"
    if _sticky_phase == "complete":
        hold = float(_STICKY_COMPLETE_SEC)
    elif _sticky_phase == "cancelled":
        hold = float(_STICKY_CANCEL_SEC)
    else:
        hold = float(_STICKY_SEC)
    _sticky_until = time.monotonic() + hold
    if message:
        _runtime_message = str(message)


def request_selected(player_index: int, *, max_rank: int = 7, quiet: bool = False) -> bool:
    global _pending_request, _runtime_message
    install()
    try:
        from . import challenge_bulk_runtime

        bulk = challenge_bulk_runtime.status()
        # running/queued only — sticky Complete keeps active=true for a flash and
        # used to block MAX ALL UVHM follow-up forever.
        if bool(bulk.get("running") or bulk.get("queued")):
            _runtime_message = (
                "UVHM cannot start while Complete ALL / bulk challenges are running. "
                "Wait for that job to finish or cancel it first."
            )
            if not quiet:
                _arm_sticky("error", _runtime_message)
            return False
    except Exception:
        pass
    if _block_if_post_complete_cooldown(quiet=quiet):
        return False
    # Challenges already prove BP_TickWidget/serial shared ticks work even when
    # unrealsdk PlayerTick add_hook returns false — never block UVHM on that.
    if _machine.running or _pending_request is not None:
        _runtime_message = "Another UVHM workflow or request is already active."
        return False
    world, _gs = _gbc_session_world_and_gamestate()
    if not _gbc_is_listen_host_world(world):
        _runtime_message = "UVHM needs the listen host (you must be hosting the lobby)."
        if not quiet:
            _arm_sticky("error", _runtime_message)
        return False
    try:
        identity = selected_lobby_identity(int(player_index))
    except Exception as exc:
        _runtime_message = (
            f"Could not target lobby index {player_index}: {exc}. "
            "Refresh party / pick the player again in Boost target."
        )
        if not quiet:
            _arm_sticky("error", _runtime_message)
        return False
    rank = max(1, min(7, int(max_rank)))
    _clear_sticky()
    _pending_request = ("selected", int(player_index), False, rank)
    who = getattr(identity, "display_name", None) or f"index {player_index}"
    _runtime_message = f"UVHM queued for {who} (up to rank {rank})."
    return True


def request_all(*, confirmed: bool, max_rank: int = 7, quiet: bool = False) -> bool:
    global _pending_request, _runtime_message
    install()
    if not confirmed:
        _runtime_message = "All-lobby confirmation was not completed."
        return False
    try:
        from . import challenge_bulk_runtime

        bulk = challenge_bulk_runtime.status()
        # running/queued only — ignore challenge Complete sticky (active flash).
        if bool(bulk.get("running") or bulk.get("queued")):
            _runtime_message = (
                "UVHM cannot start while Complete ALL / bulk challenges are running. "
                "Wait for that job to finish or cancel it first."
            )
            if not quiet:
                _arm_sticky("error", _runtime_message)
            return False
    except Exception:
        pass
    if _block_if_post_complete_cooldown(quiet=quiet):
        return False
    if _machine.running or _pending_request is not None:
        _runtime_message = "Another UVHM workflow or request is already active."
        return False
    world, _gs = _gbc_session_world_and_gamestate()
    if not _gbc_is_listen_host_world(world):
        _runtime_message = "UVHM needs the listen host (you must be hosting the lobby)."
        if not quiet:
            _arm_sticky("error", _runtime_message)
        return False
    rank = max(1, min(7, int(max_rank)))
    _clear_sticky()
    _pending_request = ("all", None, True, rank)
    _runtime_message = f"Confirmed all-lobby workflow queued (up to rank {rank})."
    return True


def cancel() -> bool:
    global _pending_request, _runtime_message
    if _pending_request is not None:
        _pending_request = None
        _runtime_message = "Queued request cancelled."
        _arm_sticky("cancelled", _runtime_message)
        try:
            from . import hold_session

            hold_session.release_job("uvhm")
        except Exception:
            pass
        return True
    if _machine.cancel():
        _runtime_message = _machine.status().message or "UVHM cancelled."
        _arm_sticky("cancelled", _runtime_message)
        try:
            from . import hold_session

            hold_session.release_job("uvhm")
        except Exception:
            pass
        return True
    return False


def resume() -> bool:
    if _machine.resume():
        _clear_sticky()
        return True
    return False


def status() -> dict[str, Any]:
    current = _machine.status()
    message = current.message
    phase = current.phase.value
    max_rank = max(1, int(getattr(_machine, "_max_rank", 7) or 7))
    sticky_live = bool(_sticky_phase) and time.monotonic() < _sticky_until
    if not sticky_live and _sticky_phase:
        # Expire terminal sticky copy so Complete/Cancel text cannot linger.
        expired = str(_sticky_phase)
        _clear_sticky()
        if expired in ("complete", "cancelled", "error") and not current.running:
            if current.phase == Phase.COMPLETE:
                try:
                    _machine.acknowledge_complete()
                    current = _machine.status()
                except Exception:
                    pass
            message = "Idle."
            phase = "idle"
    if _pending_request is not None:
        phase = "queued"
        message = _runtime_message or "Queued for the host game tick."
    elif current.running:
        pass
    elif current.phase == Phase.ERROR:
        phase = "error"
        message = current.message or _runtime_message or "UVHM failed."
    elif current.phase == Phase.COMPLETE:
        # Same as cancelled — do not leave phase=complete forever or the EXE bar sticks.
        if sticky_live:
            phase = "complete"
            message = current.message or _runtime_message or "UVHM complete."
        else:
            try:
                _machine.acknowledge_complete()
                current = _machine.status()
            except Exception:
                pass
            phase = "idle"
            message = "Idle."
    elif current.phase == Phase.CANCELLED:
        # Keep can_resume, but stop advertising "cancelled" forever after sticky —
        # leftover phase=cancelled made the EXE progress bar re-flash on every poll.
        if sticky_live:
            phase = "cancelled"
            message = current.message or _runtime_message or "UVHM cancelled."
        else:
            phase = "idle"
            message = "Idle."
    elif sticky_live:
        phase = _sticky_phase
        message = _runtime_message or message
    elif not current.running and _runtime_message and current.phase not in (
        Phase.CANCELLED,
        Phase.COMPLETE,
        Phase.IDLE,
    ):
        message = _runtime_message
    # EXE-only: stabilize settle text (does not slow the game tick).
    ui_message = message
    if "to settle (" in str(message or ""):
        token = str(current.token or "challenge").strip() or "challenge"
        ui_message = f"Waiting for {token} to settle..."
    target_count = max(1, int(current.target_count or 1))
    target_number = max(1, int(current.target_number or 1))
    rank = max(0, int(current.rank or 0))
    progress_total = float(target_count * max_rank)
    settle_grace = max(0, int(getattr(current, "settle_grace", 0) or 0))
    poll_count = max(0, int(current.poll_count or 0))
    if phase == "complete":
        progress_index = progress_total
        progress_percent = 100.0
    elif _pending_request is not None or phase == "queued":
        progress_index = 0.0
        progress_percent = 0.0
    elif phase == "breathe":
        # _advance_target already moved to the next seat; fill a tiny bridge into it.
        completed_seats = max(0, target_number - 1)
        bridge = min(0.99, poll_count / float(max(1, settle_grace)))
        progress_index = min(progress_total, float(completed_seats * max_rank) + bridge)
        progress_percent = (
            100.0
            if progress_total <= 0
            else min(99.5, max(0.0, (progress_index / progress_total) * 100.0))
        )
    else:
        # Prior players' full ranks + completed ranks for current player + settle fill.
        base = float((target_number - 1) * max_rank + max(0, rank - 1))
        frac = _intra_rank_fraction(phase, poll_count, settle_grace) if rank >= 1 else 0.0
        progress_index = min(progress_total, base + frac)
        progress_percent = (
            100.0
            if progress_total <= 0
            else min(99.5, max(0.0, (progress_index / progress_total) * 100.0))
        )
    live = bool(current.running or _pending_request is not None)
    # Keep EXE busy through sticky error/cancel/complete so "Starting…" does not
    # collapse to an empty idle panel before the outcome is readable.
    sticky_busy = sticky_live and phase in ("error", "cancelled", "complete")
    return {
        "phase": phase,
        "running": live,
        "active": bool(live or sticky_busy),
        "queued": _pending_request is not None,
        "target_mode": current.target_mode,
        "target_number": current.target_number,
        "target_count": current.target_count,
        "target_name": current.target_name,
        "rank": current.rank,
        "max_rank": max_rank,
        "progress_index": progress_index,
        "progress_total": progress_total,
        "progress_percent": progress_percent,
        "settle_grace": settle_grace,
        "token": current.token,
        "poll_count": poll_count,
        "message": ui_message,
        "detail_message": message,
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
        "post_complete_cooldown": _post_complete_cooldown_remaining(),
    }


def _consume_request() -> None:
    global _pending_request, _runtime_message
    request = _pending_request
    if request is None:
        return
    # Keep the queue until start succeeds so brief host/menu flicker cannot
    # drop the job into idle and erase EXE "Starting…" status.
    world, _gs = _gbc_session_world_and_gamestate()
    if not _gbc_is_listen_host_world(world):
        _runtime_message = (
            "UVHM waiting for listen-host world (stay in the lobby / unpause)."
        )
        return
    mode, player_index, confirmed, max_rank = request
    try:
        if mode == "selected":
            if player_index is None:
                raise ValueError("No selected player index.")
            identity = selected_lobby_identity(player_index)
            _machine.start_selected(identity, max_rank=max_rank)
            who = getattr(identity, "display_name", None) or f"index {player_index}"
            _runtime_message = f"Running UVHM for {who} (up to rank {max_rank})."
        else:
            roster = snapshot_lobby_identities()
            if not roster:
                raise ValueError("No lobby players found to apply UVHM.")
            _machine.start_all(roster, confirmed=confirmed, max_rank=max_rank)
            _runtime_message = f"Running UVHM for {len(roster)} lobby player(s) (up to rank {max_rank})."
        _pending_request = None
        _clear_sticky()
        if max_rank >= 7:
            _log(f"Started {mode} UVHM ranks 1-7 workflow.")
        else:
            _log(f"Started {mode} UVHM workflow up to rank {max_rank}.")
    except Exception as exc:
        _pending_request = None
        _runtime_message = f"Could not start UVHM: {exc}"
        _arm_sticky("error", _runtime_message)
        _log(f"UVHM {_runtime_message}")
        try:
            from . import hold_session

            hold_session.release_job("uvhm")
        except Exception:
            pass


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
    global _last_tick_at, _last_status_line, _tick_count, _last_tick_seen_at, _runtime_message
    if not _is_host_tick_context(args):
        return
    now = time.monotonic()
    # Guest join/leave churn + challenge RPCs is a common AV (null+0x70).
    # Pause UVHM natives until the lobby settle window ends — do not cancel.
    try:
        from .serial_rewards import _serial_mail_join_quiet

        if _serial_mail_join_quiet():
            return
    except Exception:
        pass
    # Slightly slower during settle / between-player breathe — FinalChallenge
    # native rank-ups need wall-clock time or the game AVs (0xc0000005).
    min_gap = 0.12
    try:
        st = _machine.status()
        phase = str(getattr(st.phase, "value", st.phase) or "")
    except Exception:
        phase = ""
    if phase in ("wait_final", "verify_rank", "breathe"):
        min_gap = 0.22
    elif phase == "wait_objective":
        min_gap = 0.16
    if now - _last_tick_at < min_gap:
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
        if now < _start_not_before:
            _runtime_message = (
                f"UVHM starts in ~{int(_start_not_before - now) + 1}s "
                "(letting the lobby catch up after boosts)."
            )
            return
        _consume_request()
        return
    if not _machine.running:
        return
    current = _machine.tick()
    if current.phase == Phase.COMPLETE:
        global _last_complete_at
        _last_complete_at = time.monotonic()
        _arm_sticky("complete", current.message or "UVHM complete.")
        try:
            from . import hold_session

            hold_session.release_job("uvhm")
        except Exception:
            pass
    elif current.phase == Phase.ERROR:
        _arm_sticky("error", current.message or "UVHM failed.")
        try:
            from . import hold_session

            hold_session.release_job("uvhm")
        except Exception:
            pass
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
