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
_STEADY_GAP = 0.10
_ACTIVE_GAP = 0.05
_INTERRUPT_GAP = 0.08
_PIN_LOG_GAP = 2.0
_BLOCK_LOG_GAP = 3.0
_FAIL_LOG_GAP = 5.0
_IDLE_COUNTDOWN = 5.0
_PIN_COUNTDOWN = 4.0

# session_guards: skip teardown if these fire while we intentionally Block them.
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
        "ClientEndOnlineSession",
        "ClientWasKicked",
        "LocalTravel",
        "OnRep_TravelStatus",
        "ClientSetTravelStatus",
        "ServerSetTravelStatus",
    }
)

# PRE-Block only — no world scans. Paths cover Engine / OakGame / Oak2 names.
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
    "/Script/Engine.PlayerController:ClientEndOnlineSession",
    "/Script/OakGame.OakPlayerController:ClientEndOnlineSession",
    "/Script/Oak2.OakPlayerController:ClientEndOnlineSession",
    "/Script/OakGame.OakPlayerController:ClientWasKicked",
    "/Script/Oak2.OakPlayerController:ClientWasKicked",
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
    """True only for leave-to-main-menu — not ordinary online/map travel.

    Live dump markers were ``bIsTravelingToMainMenu`` (with status=1). Treating
    bare ``status==1`` as leave also matched going-online / map travel and
    No-main-menu scrub cancelled those joins while the EXE kept hold armed.
    """
    if status is None:
        return False
    try:
        if bool(getattr(status, "bIsTravelingToMainMenu", False)):
            return True
    except Exception:
        pass
    return False


def _hook_is_travel_path(name: str) -> bool:
    short = str(name or "").rsplit(":", 1)[-1].strip().lower()
    return short in {
        "clienttravel",
        "clienttravelinternal",
        "servertravel",
        "localtravel",
        "clientendonlinesession",
        "clientwaskicked",
    }


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


def _scrub_pc(pc: Any, *, force: bool = False) -> bool:
    """Interrupt leave-to-menu only — never cancel unrelated online/map travel."""
    if pc is None:
        return False
    status = getattr(pc, "TravelStatus", None)
    active = _countdown_active(status) if status is not None else False
    # Sticky alone must not force-cancel travel; that blocked getting online
    # whenever No main menu stayed armed after a disconnect.
    if not active and not force:
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


def scrub_now(*, force_scan: bool = False) -> int:
    del force_scan
    global _scrub_count, _last_scrub_hit_at
    if not _is_host():
        return 0
    n = 0
    try:
        # Never force=True here — sticky poll must not yank online joins.
        if _scrub_pc(_local_pc(), force=False):
            n = 1
    except Exception:
        n = 0
    if n:
        _scrub_count += n
        _last_scrub_hit_at = time.monotonic()
    return n


def _job_still_running(job: str) -> bool:
    key = str(job or "").strip().lower()
    if key == "auto_lobby":
        try:
            from . import auto_lobby

            return bool(auto_lobby.status().get("enabled"))
        except Exception:
            return False
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
            phase = str(st.get("phase") or "").lower()
            if phase in ("complete", "completed", "idle", "cancelled", "error"):
                return False
            msg = str(st.get("message") or "").lower()
            if msg.startswith("complete:") or "complete:" in msg[:20]:
                return False
            # Ignore EXE progress-bar sticky ``active`` — only real work holds the session.
            return bool(st.get("running") or st.get("queued"))
        except Exception:
            return False
    return False


def _refresh_job_holds_from_runtime() -> None:
    for job in list(_job_holds):
        if not _job_still_running(job):
            _job_holds.discard(job)


def _sync_sticky_from_jobs() -> None:
    global _sticky
    want = bool(_user_sticky or _job_holds)
    if want and not _sticky:
        if not _is_host():
            return
        _sticky = True
        _install_hooks()
        scrub_now()
        _log(f"No main menu ON (jobs={sorted(_job_holds)} user={_user_sticky}).")
    elif not want and _sticky:
        _sticky = False
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
    _refresh_job_holds_from_runtime()
    _sync_sticky_from_jobs()
    if not _sticky:
        return
    now = time.monotonic() if now is None else float(now)
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


def _obj_is_player_controller(obj: Any) -> bool:
    if obj is None:
        return False
    try:
        cls = getattr(obj, "Class", None)
        name = str(getattr(cls, "Name", "") or getattr(cls, "_name", "") or "")
        if "PlayerController" in name:
            return True
    except Exception:
        pass
    try:
        return getattr(obj, "PlayerState", None) is not None and hasattr(obj, "TravelStatus")
    except Exception:
        return False


def _block_menu_hook(_obj: Any, _args: Any, _ret: Any, _func: Any) -> Any:
    if not _sticky or not _is_host():
        return None
    # Only intercept the HOST local PC. Blocking guest PCs breaks leave/save so
    # dump loot they just picked vanishes after disconnect. If we cannot confirm
    # the local PC (travel/teardown flicker), do not Block — better a brief miss
    # than trapping a guest leave. GameInstance / GameMode hooks still Block.
    local = _local_pc()
    if local is None:
        return None
    if _obj_is_player_controller(_obj):
        try:
            if _obj is not local and _obj != local:
                return None
        except Exception:
            return None
    try:
        name = str(getattr(_func, "Name", "") or getattr(_func, "__name__", "") or "menu")
    except Exception:
        name = "menu"
    # Travel / end-session hooks fire for going online and map changes too.
    # Only Block those while leave-to-main-menu is actually active; always Block
    # ReturnToMainMenu* / ForceCharacterSelection pulls.
    if _hook_is_travel_path(name):
        try:
            status = getattr(local, "TravelStatus", None)
        except Exception:
            status = None
        if not _countdown_active(status):
            return None
    global _last_block_log
    now = time.monotonic()
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
    global _sticky, _user_sticky, _last_scrub
    if not _is_host():
        return (
            "No main menu needs the listen-server host (you hosting with SQBT). "
            "Guests cannot arm this."
        )
    _user_sticky = True
    _sticky = True
    _last_scrub = 0.0
    _install_hooks()
    scrubbed = scrub_now()
    _log(f"No main menu ON (user toggle, scrubbed={scrubbed}).")
    return (
        "No main menu ON — guests can’t pull you to the title screen. "
        "Turn OFF before you quit to the menu yourself."
    )


def stop_hold(*, force: bool = True) -> str:
    global _sticky, _user_sticky
    _user_sticky = False
    _refresh_job_holds_from_runtime()
    leftover = sorted(_job_holds)
    if leftover and force:
        _log(f"No main menu force-OFF clearing stale jobs={leftover}.")
        _job_holds.clear()
    _sync_sticky_from_jobs()
    if _sticky:
        _log(f"No main menu stays ON (jobs still live: {sorted(_job_holds)}).")
        return (
            "No main menu stays ON — UVHM / Complete ALL challenges still look active in-game. "
            "Wait a moment and try OFF again, or cancel those jobs first."
        )
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
