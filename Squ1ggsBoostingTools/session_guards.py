"""Session safety for menu / travel / character change.

Prevents deferred SQBT work (serial mail, shapes, challenges, spawns) from touching
UObjects while the game tears down or swaps characters — a common AV source.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from unrealsdk import logging

_PREFIX = "[Squ1ggs Boosting Tools | Session]"
_TEARDOWN_HOOK_PATHS: tuple[str, ...] = (
    "/Script/Engine.Engine:PreLoadMap",
    "/Script/Engine.World:BeginTearingDown",
    "/Script/Engine.PlayerController:ClientTravel",
    "/Script/Engine.PlayerController:ServerTravel",
    "/Script/Engine.PlayerController:ClientRestart",
    "/Script/Engine.PlayerController:ClientReturnToMainMenuWithTextReason",
    "/Script/OakGame.OakPlayerController:ClientReturnToMainMenu",
    "/Script/Oak2.OakPlayerController:ClientReturnToMainMenu",
    "/Script/Engine.GameInstance:ReturnToMainMenu",
    "/Script/OakGame.OakPlayerController:K2_ClientRestart",
    "/Script/Oak2.OakPlayerController:K2_ClientRestart",
)

_listeners: list[Callable[[str], None]] = []
_hooks_installed = False
_mutations_armed = True
_was_playable = False
_playable_since: float = 0.0
_LOAD_WARM_SEC = 4.0


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
    except Exception:
        pass


def register_teardown_listener(fn: Callable[[str], None]) -> None:
    if fn not in _listeners:
        _listeners.append(fn)


def session_playable() -> bool:
    try:
        from .spawn_deferred import gameplay_ready

        return bool(gameplay_ready())
    except Exception:
        return False


def tick_session_arm() -> None:
    """Call once per HUD tick before deciding whether game mutations are safe."""
    global _was_playable, _mutations_armed, _playable_since
    playable = session_playable()
    if not playable:
        _was_playable = False
        return
    if not _was_playable:
        _playable_since = time.monotonic()
    if not _mutations_armed and not _was_playable:
        _mutations_armed = True
        _log("Session re-armed after load.")
    _was_playable = True


def session_warm() -> bool:
    """True after character load / travel settle — blocks heavy find_all shape work."""
    tick_session_arm()
    if not session_playable() or not _mutations_armed:
        return False
    since = float(_playable_since or 0.0)
    if since <= 0.0:
        return False
    return (time.monotonic() - since) >= _LOAD_WARM_SEC


def session_safe() -> bool:
    """True only when in-world with a live pawn and not in a teardown window."""
    tick_session_arm()
    if not session_playable():
        return False
    return bool(_mutations_armed)


def notify_session_teardown(reason: str = "session_teardown") -> None:
    global _mutations_armed, _was_playable, _playable_since
    if not _mutations_armed and not _listeners and not _playable_since:
        return
    _mutations_armed = False
    _was_playable = session_playable()
    _playable_since = 0.0
    label = str(reason or "session_teardown").strip() or "session_teardown"
    _log(f"Teardown: {label}")
    try:
        from . import runtime_log

        runtime_log.note(f"session teardown: {label}")
        runtime_log.flush(force=True)
    except Exception:
        pass
    for fn in list(_listeners):
        try:
            fn(label)
        except Exception as exc:
            _log(f"Teardown listener failed: {exc!r}")


def _on_teardown_hook(_obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    try:
        name = str(getattr(_func, "Name", "") or getattr(_func, "__name__", "") or "hook")
    except Exception:
        name = "hook"
    notify_session_teardown(name)


def install_session_teardown_hooks() -> None:
    global _hooks_installed
    if _hooks_installed:
        return
    try:
        from unrealsdk import hooks
        from unrealsdk.hooks import Type
    except Exception as exc:
        _log(f"Could not import hook API: {exc!r}")
        return

    installed = 0
    for i, path in enumerate(_TEARDOWN_HOOK_PATHS):
        ident = f"Squ1ggsBoostingTools.session.teardown.{i}"
        for hook_type in (Type.PRE, Type.PRE_UNCONDITIONAL):
            try:
                hooks.remove_hook(path, hook_type, ident)
            except Exception:
                pass
        ok = False
        for hook_type in (Type.PRE, Type.PRE_UNCONDITIONAL):
            try:
                hooks.add_hook(path, hook_type, ident, _on_teardown_hook)
                installed += 1
                ok = True
                break
            except Exception:
                continue
        if not ok:
            _log(f"Teardown hook skipped (path missing): {path}")
    _hooks_installed = True
    _log(f"Session teardown hooks installed ({installed}/{len(_TEARDOWN_HOOK_PATHS)}).")


def _register_builtin_listeners() -> None:
    def _serial_rewards(reason: str) -> None:
        try:
            from . import serial_rewards

            serial_rewards.cancel_deferred_reward_work(reason)
        except Exception:
            pass

    def _challenge_bulk(reason: str) -> None:
        try:
            from . import challenge_bulk_runtime

            if challenge_bulk_runtime.cancel():
                _log(f"Challenge bulk cancelled ({reason}).")
        except Exception:
            pass

    def _uvhm(reason: str) -> None:
        try:
            from . import uvhm_runtime

            if uvhm_runtime.cancel():
                _log(f"UVHM workflow cancelled ({reason}).")
        except Exception:
            pass

    def _shinies(reason: str) -> None:
        try:
            from . import shinies

            shinies.cancel_pending_shiny_drops(reason)
        except Exception:
            pass

    def _spawn_deferred(reason: str) -> None:
        try:
            from . import spawn_deferred

            n = spawn_deferred.clear_pending(reason=reason)
            if n:
                _log(f"Cleared {n} deferred spawn action(s) ({reason}).")
        except Exception:
            pass

    def _travel(reason: str) -> None:
        try:
            from . import travel

            travel.abort_pending_travel(reason)
        except Exception:
            pass

    def _loot_shapes(reason: str) -> None:
        try:
            from . import loot_shapes

            loot_shapes.abandon_world_loot()
        except Exception:
            pass

    for fn in (
        _serial_rewards,
        _challenge_bulk,
        _uvhm,
        _shinies,
        _spawn_deferred,
        _travel,
        _loot_shapes,
    ):
        register_teardown_listener(fn)


_register_builtin_listeners()
