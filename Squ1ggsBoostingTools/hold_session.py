"""Sticky host hold: cancel leave-to-menu and block travel/menu pull.

Live-edit dump (2026-09-13 OakPlayerController while guest-initiated leave):
  TravelStatus.status=1
  Initiator=OakPlayerState (guest)
  CountdownTime=5.0   ← stays at idle 5.0 while active — do not require ct < 5
  bIsTravelingToMainMenu=true
  CancelledReason type = SName (NOT FText) — empty SummaryHash/TokenCount/"None"
  Cancel RPC: ServerInterruptTravelCountdown(CancelReason=SName)
  Also: ClientCancelPendingMapChange

Runtime proof (3.8.147): leave was detected but interrupt returned ok=False because we
passed FText/""/0 instead of SName. View-button cancel uses the same RPC with SName.

Host-local get_pc only. Turn OFF before you quit to the menu yourself.
"""

from __future__ import annotations

import time
from typing import Any

from unrealsdk import logging

_PREFIX = "[Squ1ggs Boosting Tools | HoldSession]"
_sticky = False
_user_sticky = False
_job_holds: set[str] = set()
_hooks_installed = False
_last_scrub = 0.0
_last_block_log = 0.0
_last_interrupt = 0.0
_last_pin_log = 0.0
_last_scrub_hit_at = 0.0
_last_fail_log = 0.0
_scrub_count = 0
_interrupt_ok_once = False
_hold_off_after = 0.0
# Companion to LocalTravel PRE-block: pin map FT flag while sticky; clear on OFF.
_hold_pinned_local_ft = False
_STEADY_GAP = 0.10
_ACTIVE_GAP = 0.05
_INTERRUPT_GAP = 0.08
_PIN_LOG_GAP = 2.0
_BLOCK_LOG_GAP = 3.0
_FAIL_LOG_GAP = 5.0
# Keep No main menu armed across challenge→UVHM handoffs (Auto Lobby step gap).
_RELEASE_GRACE_SEC = 3.0
_IDLE_COUNTDOWN = 5.0
_PIN_COUNTDOWN = 4.0
# Runtime-tracked jobs only — sticky keys like auto_lobby stay until release_job().
_RUNTIME_JOBS: frozenset[str] = frozenset({"uvhm", "challenges"})

# session_guards: skip teardown if these fire while we intentionally Block them.
# Do not include ClientEndOnlineSession / ClientWasKicked — guests must leave+save.
_HOLD_SUPPRESS_TEARDOWN_NAMES: frozenset[str] = frozenset(
    {
        "ClientTravel",
        "ServerTravel",
        "ClientTravelInternal",
        "ClientReturnToMainMenu",
        "ClientReturnToMainMenuWithTextReason",
        "ReturnToMainMenu",
        "ReturnToMainMenuHost",
        "ClientForceCharacterSelectionAfterCountdown",
        "LocalTravel",
        "OnRep_TravelStatus",
        "ClientSetTravelStatus",
        "ServerSetTravelStatus",
    }
)

# PRE-Block only — no world scans. Paths cover Engine / OakGame / Oak2 names.
# Never block ClientEndOnlineSession / ClientWasKicked: those run on guest leave
# and must finish or backpack loot never saves after they disconnect.
_MENU_BLOCK_PATHS: tuple[str, ...] = (
    "/Script/Engine.PlayerController:ClientReturnToMainMenuWithTextReason",
    "/Script/OakGame.OakPlayerController:ClientReturnToMainMenu",
    "/Script/Oak2.OakPlayerController:ClientReturnToMainMenu",
    "/Script/OakGame.OakPlayerController:ClientReturnToMainMenuWithTextReason",
    "/Script/Oak2.OakPlayerController:ClientReturnToMainMenuWithTextReason",
    "/Script/Engine.GameInstance:ReturnToMainMenu",
    "/Script/OakGame.OakGameMode:ReturnToMainMenuHost",
    "/Script/Oak2.OakGameMode:ReturnToMainMenuHost",
    "/Script/OakGame.OakPlayerController:ClientForceCharacterSelectionAfterCountdown",
    "/Script/Oak2.OakPlayerController:ClientForceCharacterSelectionAfterCountdown",
    "/Script/Engine.PlayerController:ClientTravel",
    "/Script/Engine.PlayerController:ClientTravelInternal",
    "/Script/Engine.PlayerController:ServerTravel",
    "/Script/OakGame.OakPlayerController:ClientTravel",
    "/Script/Oak2.OakPlayerController:ClientTravel",
    "/Script/OakGame.OakPlayerController:ClientTravelInternal",
    "/Script/Oak2.OakPlayerController:ClientTravelInternal",
    "/Script/OakGame.OakPlayerController:ServerTravel",
    "/Script/Oak2.OakPlayerController:ServerTravel",
    "/Script/OakGame.OakPlayerController:LocalTravel",
    "/Script/Oak2.OakPlayerController:LocalTravel",
)

_TRAVEL_STATUS_HOOK_PATHS: tuple[str, ...] = (
    "/Script/OakGame.OakPlayerController:OnRep_TravelStatus",
    "/Script/Oak2.OakPlayerController:OnRep_TravelStatus",
    "/Script/OakGame.OakPlayerState:OnRep_TravelStatus",
    "/Script/Oak2.OakPlayerState:OnRep_TravelStatus",
)


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
    except Exception:
        pass
    try:
        from . import runtime_log

        runtime_log.note(f"hold: {msg}")
    except Exception:
        pass


def is_enabled() -> bool:
    return bool(_sticky)


def _is_host() -> bool:
    try:
        from . import world_spawn

        return bool(world_spawn.is_host())
    except Exception:
        return False


def _local_pc() -> Any | None:
    try:
        from mods_base import get_pc

        return get_pc()
    except Exception:
        return None


def _empty_sname() -> Any | None:
    """CancelledReason dump type is SName (SummaryHash/TokenCount/InlineTokens)."""
    try:
        import unrealsdk

        token = None
        for tname in ("SToken", "FSnameToken", "GbxSToken"):
            try:
                token = unrealsdk.make_struct(tname, Hash=0, Name="None")
                break
            except Exception:
                try:
                    token = unrealsdk.make_struct(tname)
                    try:
                        setattr(token, "Hash", 0)
                    except Exception:
                        pass
                    try:
                        setattr(token, "Name", "None")
                    except Exception:
                        pass
                    break
                except Exception:
                    continue

        for name in ("SName", "FSname", "GbxSName"):
            try:
                if token is not None:
                    try:
                        built = unrealsdk.make_struct(
                            name,
                            SummaryHash=0,
                            TokenCount=0,
                            InlineTokens=token,
                            ExternalTokens=[],
                        )
                    except Exception:
                        built = unrealsdk.make_struct(name)
                else:
                    built = unrealsdk.make_struct(name)
            except Exception:
                continue
            if built is None:
                continue
            try:
                setattr(built, "SummaryHash", 0)
            except Exception:
                pass
            try:
                setattr(built, "TokenCount", 0)
            except Exception:
                pass
            if token is not None:
                try:
                    setattr(built, "InlineTokens", token)
                except Exception:
                    pass
            return built
    except Exception:
        pass
    return None


def _cancel_reasons(pc: Any) -> list[Any]:
    """Candidate CancelReason args — live dump proved CancelledReason is SName."""
    out: list[Any] = []
    status = getattr(pc, "TravelStatus", None)
    if status is not None:
        for attr in ("CancelledReason", "CancelReason"):
            try:
                val = getattr(status, attr, None)
            except Exception:
                val = None
            if val is not None:
                out.append(val)
    sn = _empty_sname()
    if sn is not None:
        out.append(sn)
    try:
        import unrealsdk

        for name, kwargs in (
            ("Text", {}),
            ("FText", {}),
            ("Text", {"CultureInvariantString": ""}),
            ("Text", {"SourceString": ""}),
        ):
            try:
                out.append(unrealsdk.make_struct(name, **kwargs) if kwargs else unrealsdk.make_struct(name))
            except Exception:
                continue
    except Exception:
        pass
    out.extend(("", None))
    seen: set[int] = set()
    uniq: list[Any] = []
    for item in out:
        key = id(item)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq


def _interrupt_countdown(pc: Any) -> bool:
    """View-button cancel. CancelReason must be SName (dump), not plain FText/int."""
    global _interrupt_ok_once, _last_fail_log
    fn = getattr(pc, "ServerInterruptTravelCountdown", None)
    if not callable(fn):
        now = time.monotonic()
        if now - _last_fail_log >= _FAIL_LOG_GAP:
            _last_fail_log = now
            _log("ServerInterruptTravelCountdown missing on local PC.")
        return False

    errors: list[str] = []
    try:
        fn()
        _interrupt_ok_once = True
        return True
    except TypeError as exc:
        errors.append(f"():{type(exc).__name__}")
    except Exception as exc:
        errors.append(f"():{type(exc).__name__}:{exc}")

    for reason in _cancel_reasons(pc):
        for call in (
            lambda r=reason: fn(r),
            lambda r=reason: fn(CancelReason=r),
        ):
            try:
                call()
                _interrupt_ok_once = True
                return True
            except TypeError as exc:
                errors.append(f"{type(reason).__name__}:{type(exc).__name__}")
            except Exception as exc:
                errors.append(f"{type(reason).__name__}:{type(exc).__name__}:{exc}")

    now = time.monotonic()
    if now - _last_fail_log >= _FAIL_LOG_GAP:
        _last_fail_log = now
        sample = "; ".join(errors[:6]) or "no attempts"
        _log(f"InterruptTravel FAILED ({sample}).")
    return False


def _status_code(status: Any) -> int:
    try:
        raw = getattr(status, "status", 0)
        if hasattr(raw, "value"):
            return int(raw.value)
        return int(raw or 0)
    except Exception:
        return 0


def _countdown_time(status: Any) -> float:
    try:
        return float(getattr(status, "CountdownTime", _IDLE_COUNTDOWN) or 0.0)
    except Exception:
        return _IDLE_COUNTDOWN


def _countdown_active(status: Any) -> bool:
    """True for dump-proven leave-to-main-menu.

    Live dump kept CountdownTime at 5.0 while active — do not require ct < 5.
    status=1 + bIsTravelingToMainMenu were the leave markers.
    """
    if status is None:
        return False
    try:
        if bool(getattr(status, "bIsTravelingToMainMenu", False)):
            return True
    except Exception:
        pass
    try:
        if _status_code(status) == 1:
            return True
    except Exception:
        pass
    return False


def _cancel_pending_map(pc: Any) -> None:
    for name in (
        "ClientCancelPendingMapChange",
        "ServerCancelPendingMapChange",
        "CancelPendingMapChange",
        "ClearPendingMapChange",
    ):
        fn = getattr(pc, name, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass


def _pin_travel_status(pc: Any, status: Any) -> None:
    """Live-edit cancel path — pin at 4s and clear leave flags (no Initiator writes)."""
    if status is None:
        return
    for attr, val in (
        ("CountdownTime", _PIN_COUNTDOWN),
        ("bIsTravelingToMainMenu", False),
        ("status", 0),
    ):
        try:
            setattr(status, attr, val)
        except Exception:
            pass
    try:
        setattr(pc, "TravelStatus", status)
    except Exception:
        pass
    try:
        ps = getattr(pc, "PlayerState", None)
    except Exception:
        ps = None
    if ps is not None:
        try:
            ps_status = getattr(ps, "TravelStatus", None)
            if ps_status is not None:
                for attr, val in (
                    ("CountdownTime", _PIN_COUNTDOWN),
                    ("bIsTravelingToMainMenu", False),
                    ("status", 0),
                ):
                    try:
                        setattr(ps_status, attr, val)
                    except Exception:
                        pass
                try:
                    setattr(ps, "TravelStatus", ps_status)
                except Exception:
                    pass
            fn = getattr(ps, "ServerSetTravelStatus", None)
            if callable(fn):
                try:
                    fn(status)
                except TypeError:
                    try:
                        fn(0)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass


def suppress_teardown_for_hook(hook_name: str) -> bool:
    if not _sticky:
        return False
    name = str(hook_name or "").strip()
    if not name:
        return False
    short = name.rsplit(":", 1)[-1].strip()
    return short in _HOLD_SUPPRESS_TEARDOWN_NAMES or name in _HOLD_SUPPRESS_TEARDOWN_NAMES


def _initiator_is_local(pc: Any, status: Any) -> bool:
    """True when the leave countdown was started by the host (not a guest pull)."""
    if pc is None or status is None:
        return False
    try:
        init = getattr(status, "Initiator", None)
        local_ps = getattr(pc, "PlayerState", None)
        if init is None or local_ps is None:
            return False
        if init is local_ps:
            return True
        try:
            return bool(init == local_ps)
        except Exception:
            return False
    except Exception:
        return False


def _scrub_pc(pc: Any, *, force: bool = False) -> bool:
    """View-button equivalent: interrupt + cancel pending whenever sticky."""
    if pc is None:
        return False
    status = getattr(pc, "TravelStatus", None)
    active = _countdown_active(status) if status is not None else False
    # Host intentionally leaving — fighting Esc/menu while Auto Lobby holds caused crashes.
    if active and not force and _initiator_is_local(pc, status):
        _log("Host self-leave detected — releasing No main menu so you can quit.")
        try:
            stop_hold(force=True)
        except Exception:
            pass
        return False
    if not active and not force and not _sticky:
        return False

    ct_before = _countdown_time(status) if status is not None else 0.0
    global _last_interrupt, _last_pin_log
    now = time.monotonic()
    interrupted = False
    if now - _last_interrupt >= _INTERRUPT_GAP or force:
        _last_interrupt = now
        interrupted = _interrupt_countdown(pc)
        _cancel_pending_map(pc)
        if status is not None and (active or force):
            _pin_travel_status(pc, status)
            try:
                again = getattr(pc, "TravelStatus", None)
                if _countdown_active(again):
                    _pin_travel_status(pc, again)
                    interrupted = _interrupt_countdown(pc) or interrupted
            except Exception:
                pass
    if active and (now - _last_pin_log >= _PIN_LOG_GAP or force):
        _last_pin_log = now
        still = False
        try:
            still = _countdown_active(getattr(pc, "TravelStatus", None))
        except Exception:
            pass
        _log(
            f"Host leave interrupt ({ct_before:.2f}s, ok={interrupted}, "
            f"still_active={still}, sname_ok={_interrupt_ok_once})."
        )
    return bool(active or interrupted)


def _set_local_ft_disallowed(want: bool) -> bool:
    """Pin/clear bDisallowLocalTravel on the host PC (map fast travel)."""
    global _hold_pinned_local_ft
    pc = _local_pc()
    if pc is None:
        return False
    wrote = False
    status = getattr(pc, "TravelStatus", None)
    if status is not None:
        try:
            setattr(status, "bDisallowLocalTravel", bool(want))
            wrote = True
            try:
                setattr(pc, "TravelStatus", status)
            except Exception:
                pass
        except Exception:
            pass
    try:
        setattr(pc, "bDisallowLocalTravel", bool(want))
        wrote = True
    except Exception:
        pass
    if wrote:
        _hold_pinned_local_ft = bool(want)
    return wrote


def _clear_local_ft_pin_if_ours() -> None:
    """Release the map-FT pin when No main menu turns OFF (does not touch menu scrub)."""
    global _hold_pinned_local_ft
    if not _hold_pinned_local_ft:
        return
    try:
        _set_local_ft_disallowed(False)
    except Exception:
        _hold_pinned_local_ft = False


def scrub_now(*, force_scan: bool = False) -> int:
    del force_scan
    global _scrub_count, _last_scrub_hit_at
    if not _is_host():
        return 0
    if _sticky:
        try:
            _set_local_ft_disallowed(True)
        except Exception:
            pass
    n = 0
    try:
        if _scrub_pc(_local_pc(), force=bool(_sticky)):
            n = 1
    except Exception:
        n = 0
    if n:
        _scrub_count += n
        _last_scrub_hit_at = time.monotonic()
    return n


def _job_still_running(job: str) -> bool:
    key = str(job or "").strip().lower()
    if key == "uvhm":
        try:
            from . import uvhm_runtime

            st = uvhm_runtime.status()
            phase = str(st.get("phase") or "").lower()
            if phase in ("complete", "completed", "idle", "error", "cancelled"):
                return False
            return bool(st.get("running") or st.get("queued") or phase == "queued")
        except Exception:
            return False
    if key == "challenges":
        try:
            from . import challenge_bulk_runtime

            st = challenge_bulk_runtime.status()
            msg = str(st.get("message") or "").lower()
            if msg.startswith("complete:") or "complete:" in msg[:20]:
                return False
            if not bool(st.get("active") or st.get("queued")):
                return False
            try:
                total = int(st.get("total") or 0)
                index = int(st.get("index") or 0)
                if total > 0 and index >= total and not st.get("queued"):
                    return False
            except Exception:
                pass
            return bool(st.get("active") or st.get("queued"))
        except Exception:
            return False
    return False


def _refresh_job_holds_from_runtime() -> None:
    for job in list(_job_holds):
        if job not in _RUNTIME_JOBS:
            continue
        if not _job_still_running(job):
            _job_holds.discard(job)


def _sync_sticky_from_jobs(now: float | None = None) -> None:
    global _sticky, _hold_off_after
    want = bool(_user_sticky or _job_holds)
    clock = time.monotonic() if now is None else float(now)
    if want:
        _hold_off_after = 0.0
        if not _sticky:
            if not _is_host():
                return
            _sticky = True
            _install_hooks()
            scrub_now()
            _log(f"No main menu ON (jobs={sorted(_job_holds)} user={_user_sticky}).")
        return
    if not _sticky:
        _hold_off_after = 0.0
        return
    # Grace so challenge→UVHM (or Auto Lobby next step) can re-arm without an OFF gap.
    if _hold_off_after <= 0.0:
        _hold_off_after = clock + _RELEASE_GRACE_SEC
        return
    if clock < _hold_off_after:
        return
    _sticky = False
    _hold_off_after = 0.0
    _clear_local_ft_pin_if_ours()
    _log("No main menu OFF (no jobs / user toggle).")


def arm_for_job(job: str) -> None:
    key = str(job or "").strip().lower()
    if not key or not _is_host():
        return
    _job_holds.add(key)
    _sync_sticky_from_jobs()


def release_job(job: str) -> None:
    key = str(job or "").strip().lower()
    if key:
        _job_holds.discard(key)
    _sync_sticky_from_jobs()


def tick_hold_session(now: float | None = None) -> None:
    global _last_scrub
    now = time.monotonic() if now is None else float(now)
    _refresh_job_holds_from_runtime()
    _sync_sticky_from_jobs(now)
    if not _sticky:
        return
    pull_active = (now - _last_scrub_hit_at) < 2.5
    gap = _ACTIVE_GAP if pull_active else _STEADY_GAP
    if now - _last_scrub < gap:
        return
    _last_scrub = now
    try:
        scrub_now()
    except Exception:
        pass


def runtime_tick(*_args: Any, **_kwargs: Any) -> None:
    tick_hold_session()


def _block_menu_hook(_obj: Any, _args: Any, _ret: Any, _func: Any) -> Any:
    if not _sticky or not _is_host():
        return None
    # Only intercept the HOST local PC. Blocking guest PCs breaks leave/save so
    # dump loot they just picked vanishes after disconnect. If we can't resolve
    # the local PC (or the hook's object) we can't confirm that, so don't block.
    local = _local_pc()
    if local is None or _obj is None:
        return None
    try:
        if _obj is not local and _obj != local:
            return None
    except Exception:
        return None
    pc = local
    status = getattr(pc, "TravelStatus", None) if pc is not None else None
    if status is not None and _initiator_is_local(pc, status):
        _log("Host menu/travel — releasing No main menu (self leave).")
        try:
            stop_hold(force=True)
        except Exception:
            pass
        return None
    global _last_block_log
    now = time.monotonic()
    try:
        name = str(getattr(_func, "Name", "") or getattr(_func, "__name__", "") or "menu")
    except Exception:
        name = "menu"
    if now - _last_block_log >= _BLOCK_LOG_GAP:
        _last_block_log = now
        _log(f"Blocked {name}.")
    try:
        scrub_now()
    except Exception:
        pass
    try:
        from unrealsdk.hooks import Block

        return Block
    except Exception:
        return True


def _on_travel_status_hook(_obj: Any, _args: Any, _ret: Any, _func: Any) -> Any:
    """React the instant TravelStatus replicates — do not wait for the poll gap."""
    if not _sticky or not _is_host():
        return None
    try:
        scrub_now()
    except Exception:
        pass
    return None


def _install_hooks() -> None:
    global _hooks_installed
    if _hooks_installed:
        return
    try:
        from unrealsdk import hooks

        Type = hooks.Type
    except Exception as exc:
        _log(f"Could not import hooks: {exc!r}")
        return

    pre_types = [Type.PRE]
    pre_u = getattr(Type, "PRE_UNCONDITIONAL", None)
    if pre_u is not None:
        pre_types.append(pre_u)

    for i, path in enumerate(_MENU_BLOCK_PATHS):
        for ident in (
            f"Squ1ggsBoostingTools.hold_session.block.{i}",
            f"sqbt_hold_session_block_{i}",
        ):
            installed = False
            for typ in pre_types:
                try:
                    if hooks.add_hook(path, typ, ident, _block_menu_hook):
                        installed = True
                        break
                except Exception:
                    continue
            if installed:
                break

    for i, path in enumerate(_TRAVEL_STATUS_HOOK_PATHS):
        for ident in (
            f"Squ1ggsBoostingTools.hold_session.travel_status.{i}",
            f"sqbt_hold_travel_status_{i}",
        ):
            installed = False
            for typ in (Type.POST, Type.PRE, *([pre_u] if pre_u is not None else [])):
                if typ is None:
                    continue
                try:
                    if hooks.add_hook(path, typ, ident, _on_travel_status_hook):
                        installed = True
                        break
                except Exception:
                    continue
            if installed:
                break

    _hooks_installed = True
    _log("Menu/travel block hooks installed.")


def start_hold() -> str:
    global _sticky, _user_sticky, _last_scrub, _hold_off_after
    if not _is_host():
        return (
            "No main menu needs the listen-server host (you hosting with SQBT). "
            "Guests cannot arm this."
        )
    _user_sticky = True
    _sticky = True
    _hold_off_after = 0.0
    _last_scrub = 0.0
    _install_hooks()
    scrubbed = scrub_now()
    _log(f"No main menu ON (user toggle, scrubbed={scrubbed}).")
    return (
        "No main menu ON — guests can’t pull you to the title screen, "
        "and your map fast travel is blocked while this stays ON. "
        "Turn OFF before you quit to the menu yourself."
    )


def stop_hold(*, force: bool = True) -> str:
    global _sticky, _user_sticky, _hold_off_after
    _user_sticky = False
    _refresh_job_holds_from_runtime()
    leftover = sorted(_job_holds)
    if leftover and force:
        _log(f"No main menu force-OFF clearing stale jobs={leftover}.")
        _job_holds.clear()
    if force:
        # Desktop/user quit path — skip challenge→UVHM grace so leave works immediately.
        _hold_off_after = 0.0
        was_on = bool(_sticky)
        _sticky = False
        _clear_local_ft_pin_if_ours()
        if was_on or leftover:
            _log("No main menu OFF (force).")
        return "No main menu OFF — normal leave countdown behavior is back."
    _sync_sticky_from_jobs()
    if _sticky:
        _log(f"No main menu stays ON (jobs still live: {sorted(_job_holds)}).")
        return (
            "No main menu stays ON — UVHM / Complete ALL challenges / Auto Lobby still holding. "
            "Wait a moment and try OFF again, or cancel those jobs first."
        )
    _clear_local_ft_pin_if_ours()
    _log("No main menu OFF.")
    return "No main menu OFF — normal leave countdown behavior is back."


def set_enabled(enabled: bool) -> str:
    if enabled:
        return start_hold()
    return stop_hold(force=True)


def status() -> str:
    state = "ON" if _sticky else "OFF"
    extra = ""
    if _job_holds:
        extra = f" (jobs: {', '.join(sorted(_job_holds))})"
    elif _user_sticky:
        extra = " (user)"
    return f"No main menu {state}{extra}."
