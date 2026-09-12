"""Sticky host hold: cancel travel-to-menu countdown and block return-to-main-menu.

When ON, the listen host keeps scrubbing TravelStatus (CountdownTime /
bIsTravelingToMainMenu) and PRE-blocks ClientReturnToMainMenu* / session-end
paths so co-op guests cannot pull the lobby apart. Auto-arms during UVHM /
challenge bulk. Turn OFF before you intentionally quit to the menu.
"""

from __future__ import annotations

import time
from typing import Any

from unrealsdk import logging

_PREFIX = "[Squ1ggs Boosting Tools | HoldSession]"
_sticky = False
_user_sticky = False  # True when host toggled ON manually — jobs must not auto-release.
_job_holds: set[str] = set()
_hooks_installed = False
_last_scrub = 0.0
_last_block_log = 0.0
_scrub_count = 0
_STEADY_GAP = 0.12
_BLOCK_LOG_GAP = 8.0

_MENU_BLOCK_PATHS: tuple[str, ...] = (
    "/Script/Engine.PlayerController:ClientReturnToMainMenuWithTextReason",
    "/Script/OakGame.OakPlayerController:ClientReturnToMainMenu",
    "/Script/Oak2.OakPlayerController:ClientReturnToMainMenu",
    "/Script/OakGame.OakPlayerController:ClientReturnToMainMenuWithTextReason",
    "/Script/Oak2.OakPlayerController:ClientReturnToMainMenuWithTextReason",
    "/Script/Engine.GameInstance:ReturnToMainMenu",
    "/Script/OakGame.OakPlayerController:ClientForceCharacterSelectionAfterCountdown",
    "/Script/Oak2.OakPlayerController:ClientForceCharacterSelectionAfterCountdown",
    # Lobby leave / session teardown (host-side) — guests pulling out mid UVHM/challenges.
    "/Script/Engine.PlayerController:ClientEndOnlineSession",
    "/Script/OakGame.OakPlayerController:ClientEndOnlineSession",
    "/Script/Oak2.OakPlayerController:ClientEndOnlineSession",
    "/Script/OakGame.OakPlayerController:ClientWasKicked",
    "/Script/Oak2.OakPlayerController:ClientWasKicked",
)


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
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


def _local_pcs() -> list[Any]:
    pcs: list[Any] = []
    try:
        from mods_base import get_pc

        pc = get_pc()
        if pc is not None:
            pcs.append(pc)
    except Exception:
        pass
    try:
        import unrealsdk

        for cls in ("OakPlayerController", "GbxPlayerController", "PlayerController"):
            try:
                found = list(unrealsdk.find_all(cls, False) or [])
            except Exception:
                found = []
            for obj in found:
                if obj is None:
                    continue
                try:
                    name = str(getattr(obj, "Name", "") or obj)
                except Exception:
                    name = ""
                if "Default__" in name or "default__" in name:
                    continue
                if all(obj is not existing for existing in pcs):
                    pcs.append(obj)
    except Exception:
        pass
    return pcs


def _interrupt_countdown(pc: Any) -> bool:
    fn = getattr(pc, "ServerInterruptTravelCountdown", None)
    if not callable(fn):
        return False
    try:
        fn()
        return True
    except TypeError:
        try:
            fn(0)
            return True
        except Exception:
            return False
    except Exception:
        return False


def _scrub_pc(pc: Any) -> bool:
    """Cancel an active travel/menu countdown on one controller. True if scrubbed."""
    if pc is None:
        return False
    status = getattr(pc, "TravelStatus", None)
    need = False
    if status is not None:
        try:
            ct = float(getattr(status, "CountdownTime", 0.0) or 0.0)
        except Exception:
            ct = 0.0
        try:
            to_menu = bool(getattr(status, "bIsTravelingToMainMenu", False))
        except Exception:
            to_menu = False
        if ct > 0.05 or to_menu:
            need = True
        if need:
            try:
                setattr(status, "CountdownTime", 0.0)
            except Exception:
                pass
            try:
                setattr(status, "bIsTravelingToMainMenu", False)
            except Exception:
                pass
    if need:
        _interrupt_countdown(pc)
        cancel = getattr(pc, "ClientCancelPendingMapChange", None)
        if callable(cancel):
            try:
                cancel()
            except Exception:
                pass
        return True
    return False


def scrub_now() -> int:
    """One-shot scrub of all known PCs. Returns how many were actively cleared."""
    global _scrub_count
    n = 0
    for pc in _local_pcs():
        try:
            if _scrub_pc(pc):
                n += 1
        except Exception:
            continue
    if n:
        _scrub_count += n
    return n


def _sync_sticky_from_jobs() -> None:
    global _sticky
    want = bool(_user_sticky or _job_holds)
    if want and not _sticky:
        if _is_host():
            _sticky = True
            _install_hooks()
            scrub_now()
            _log(f"Hold session ON (jobs={sorted(_job_holds)} user={_user_sticky}).")
    elif not want and _sticky:
        _sticky = False
        _log("Hold session OFF (no jobs / user toggle).")


def arm_for_job(job: str) -> None:
    """Auto-hold while UVHM / challenges run (does not mark user sticky)."""
    key = str(job or "").strip().lower()
    if not key:
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
    # Drop finished auto-jobs so hold releases when UVHM/challenges finish.
    try:
        from . import uvhm_runtime

        st = uvhm_runtime.status()
        if not bool(st.get("running") or st.get("active") or st.get("queued")):
            _job_holds.discard("uvhm")
    except Exception:
        pass
    try:
        from . import challenge_bulk_runtime

        st = challenge_bulk_runtime.status()
        if not bool(st.get("active") or st.get("queued")):
            _job_holds.discard("challenges")
    except Exception:
        pass
    _sync_sticky_from_jobs()
    if not _sticky:
        return
    if not _is_host():
        return
    now = time.monotonic() if now is None else float(now)
    if now - _last_scrub < _STEADY_GAP:
        return
    _last_scrub = now
    try:
        scrub_now()
    except Exception:
        pass


def _block_menu_hook(_obj: Any, _args: Any, _ret: Any, _func: Any) -> Any:
    if not _sticky:
        return None
    if not _is_host():
        return None
    global _last_block_log
    now = time.monotonic()
    if now - _last_block_log >= _BLOCK_LOG_GAP:
        _last_block_log = now
        try:
            name = str(getattr(_func, "Name", "") or getattr(_func, "__name__", "") or "menu")
        except Exception:
            name = "menu"
        _log(f"Blocked {name} (hold session ON).")
    try:
        scrub_now()
    except Exception:
        pass
    try:
        from unrealsdk.hooks import Block

        return Block
    except Exception:
        return True


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

    for i, path in enumerate(_MENU_BLOCK_PATHS):
        for ident in (
            f"Squ1ggsBoostingTools.hold_session.block.{i}",
            f"sqbt_hold_session_block_{i}",
        ):
            try:
                if hooks.add_hook(path, Type.PRE, ident, _block_menu_hook):
                    break
            except Exception:
                try:
                    if hooks.add_hook(path, Type.PRE_UNCONDITIONAL, ident, _block_menu_hook):
                        break
                except Exception:
                    continue
    _hooks_installed = True
    _log("Menu/leave block hooks installed.")


def start_hold() -> str:
    global _sticky, _user_sticky, _last_scrub
    if not _is_host():
        return (
            "Hold session needs the listen-server host (you hosting with SQBT). "
            "Guests cannot arm this."
        )
    _user_sticky = True
    _sticky = True
    _last_scrub = 0.0
    _install_hooks()
    scrubbed = scrub_now()
    _log(f"Hold session ON (user toggle, scrubbed={scrubbed}).")
    return (
        "Hold session ON — travel-to-menu countdown cancelled; main-menu / session-end return blocked. "
        "Turn this OFF when you want to quit to the menu yourself."
    )


def stop_hold() -> str:
    global _sticky, _user_sticky
    _user_sticky = False
    # Keep armed if UVHM/challenges still running.
    _sync_sticky_from_jobs()
    if _sticky:
        _log("Hold session stays ON (UVHM/challenges still running).")
        return (
            "Hold session stays ON while UVHM / Complete ALL challenges finish. "
            "It will release when those jobs end."
        )
    _log("Hold session OFF.")
    return "Hold session OFF — normal menu / travel countdown behavior is back."


def set_enabled(enabled: bool) -> str:
    if enabled:
        return start_hold()
    return stop_hold()


def status() -> str:
    state = "ON" if _sticky else "OFF"
    extra = ""
    if _job_holds:
        extra = f" (jobs: {', '.join(sorted(_job_holds))})"
    elif _user_sticky:
        extra = " (user)"
    return f"Hold session {state}{extra}."
