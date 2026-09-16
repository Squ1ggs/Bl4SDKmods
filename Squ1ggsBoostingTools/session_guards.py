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
    "/Script/Engine.PlayerController:ClientTravelInternal",
    "/Script/Engine.PlayerController:ServerTravel",
    "/Script/Engine.PlayerController:ClientRestart",
    "/Script/Engine.PlayerController:ClientReturnToMainMenuWithTextReason",
    "/Script/OakGame.OakPlayerController:ClientReturnToMainMenu",
    "/Script/Oak2.OakPlayerController:ClientReturnToMainMenu",
    "/Script/OakGame.OakPlayerController:ClientTravelInternal",
    "/Script/Oak2.OakPlayerController:ClientTravelInternal",
    "/Script/Engine.GameInstance:ReturnToMainMenu",
    "/Script/OakGame.OakGameMode:ReturnToMainMenuHost",
    "/Script/Oak2.OakGameMode:ReturnToMainMenuHost",
    "/Script/OakGame.OakPlayerController:K2_ClientRestart",
    "/Script/Oak2.OakPlayerController:K2_ClientRestart",
    "/Script/Engine.PlayerController:ClientEndOnlineSession",
    "/Script/OakGame.OakPlayerController:ClientEndOnlineSession",
    "/Script/Oak2.OakPlayerController:ClientEndOnlineSession",
)

_listeners: list[Callable[[str], None]] = []
_hooks_installed = False
_mutations_armed = True
_was_playable = False


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
    global _was_playable, _mutations_armed
    playable = session_playable()
    if not playable:
        _was_playable = False
        return
    if not _mutations_armed and not _was_playable:
        _mutations_armed = True
        _log("Session re-armed after load.")
    _was_playable = True


def session_safe() -> bool:
    """True only when in-world with a live pawn and not in a teardown window."""
    tick_session_arm()
    if not session_playable():
        return False
    return bool(_mutations_armed)


def notify_session_teardown(reason: str = "session_teardown") -> None:
    global _mutations_armed, _was_playable
    if not _mutations_armed and not _listeners:
        return
    _mutations_armed = False
    _was_playable = session_playable()
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
    # Hold session PRE-blocks menu/travel; do not cancel UVHM/shapes as if we left.
    try:
        from . import hold_session

        if hold_session.suppress_teardown_for_hook(name):
            _log(f"Teardown skipped (hold session ON): {name}")
            return
    except Exception:
        pass
    notify_session_teardown(name)


def install_session_teardown_hooks() -> None:
    global _hooks_installed
    if _hooks_installed:
        return
    try:
        from unrealsdk import hooks

        Type = hooks.Type
    except Exception as exc:
        _log(f"Could not import hook API: {exc!r}")
        return

    for i, path in enumerate(_TEARDOWN_HOOK_PATHS):
        # One successful register per path — same pattern as hold_session.
        # Without this, both idents can stick and teardown listeners double-fire.
        for ident in (
            f"Squ1ggsBoostingTools.session.teardown.{i}",
            f"sqbt_session_teardown_{i}",
        ):
            installed = False
            for hook_type in (Type.PRE, Type.PRE_UNCONDITIONAL, Type.POST):
                try:
                    hooks.add_hook(path, hook_type, ident, _on_teardown_hook)
                    installed = True
                    break
                except Exception:
                    continue
            if installed:
                break
    _hooks_installed = True
    _log("Session teardown hooks installed.")


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

            loot_shapes.abandon_world_loot(schedule_orphan_absorb=False)
        except Exception:
            pass

    def _map_scout(reason: str) -> None:
        try:
            from . import map_scout

            if map_scout.status().get("active"):
                map_scout.cancel()
                _log(f"Host map sweep cancelled ({reason}).")
        except Exception:
            pass

    def _map_escort(reason: str) -> None:
        try:
            from . import map_party_escort

            if map_party_escort.status().get("active"):
                map_party_escort.cancel()
                _log(f"Guest map assist cancelled ({reason}).")
        except Exception:
            pass

    def _auto_lobby(reason: str) -> None:
        del reason
        try:
            from . import auto_lobby

            auto_lobby.abandon()
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
        _map_scout,
        _map_escort,
        _auto_lobby,
    ):
        register_teardown_listener(fn)


_register_builtin_listeners()
