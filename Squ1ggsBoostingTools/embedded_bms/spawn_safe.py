"""Defer UObject spawn work off the ImGui draw thread."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from .lobby_stability import make_request
from .spawn_pause import spawn_paused

SpawnFn = Callable[[], tuple[bool, str]]


def _mark_pending(ui: Any, msg: str) -> None:
    if ui is None:
        return
    try:
        ui.status_text = msg
        ui.error_text = ""
        ui.spawn_pending = True  # type: ignore[attr-defined]
        try:
            ui.spawn_pending_since = time.monotonic()  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        pass


def _clear_pending(ui: Any) -> None:
    if ui is None:
        return
    try:
        ui.spawn_pending = False  # type: ignore[attr-defined]
        try:
            ui.spawn_pending_since = 0.0  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        pass


def _wrap_paused(fn: SpawnFn) -> SpawnFn:
    def _inner() -> tuple[bool, str]:
        with spawn_paused():
            return fn()

    return _inner


def _queue_anchor(ui: Any) -> str:
    anchor = "local"
    if ui is not None:
        anchor = str(getattr(ui, "spawn_anchor", "local") or "local")
    else:
        try:
            from Squ1ggsBoostingTools import spawn_targets  # noqa: PLC0415

            anchor = str(spawn_targets.mode() or "local")
        except Exception:
            pass
    try:
        from Squ1ggsBoostingTools.dev_tools import is_debug_cam_active  # noqa: PLC0415

        if is_debug_cam_active() and anchor in ("local", ""):
            anchor = "freecam"
    except Exception:
        pass
    return anchor


def queue_spawn_action(
    label: str,
    fn: SpawnFn,
    ui: Any,
    *,
    pause: bool = False,
) -> tuple[bool, str]:
    """
    Queue spawn on PlayerTick via bl4_world_tools deferred.

    Flushed only by BMS's listen-host ``PlayerTick`` owner.

    ``pause=False`` (default): keep the world running so lobby clients do not
    time out during LoadPackage / boss settle. Hard-pause is optional for rare
    crash-prone IO paths that explicitly opt in.
    """
    try:
        from Squ1ggsBoostingTools import spawn_deferred as deferred
        anchor = _queue_anchor(ui)
        request = make_request(
            label,
            _wrap_paused(fn) if pause else fn,
            anchor=anchor,
            party_index=int(getattr(ui, "party_index", 2) or 2) if ui is not None else 2,
            status_ui=ui,
        )
        deferred.queue_action(label, request.execute)
        msg = f"Queued: {label} — waiting for world to settle"
        _mark_pending(ui, msg)
        return True, msg
    except Exception as exc:  # noqa: BLE001
        msg = f"failed: could not queue {label}: {type(exc).__name__}: {exc}"
        ui.status_text = msg
        ui.error_text = msg
        _clear_pending(ui)
        return False, msg


def queue_spawn_actions(
    label: str,
    fns: list[SpawnFn],
    ui: Any,
    *,
    pause: bool = False,
) -> tuple[bool, str]:
    """Queue several spawns — one deferred action per frame (smooth multi-spawn)."""
    if not fns:
        return False, "nothing to queue"
    try:
        from Squ1ggsBoostingTools import spawn_deferred as deferred
        n = len(fns)
        for i, fn in enumerate(fns):
            item_label = f"{label} ({i + 1}/{n})"
            anchor = _queue_anchor(ui)
            request = make_request(
                item_label,
                _wrap_paused(fn) if pause else fn,
                anchor=anchor,
                party_index=int(getattr(ui, "party_index", 2) or 2) if ui is not None else 2,
                status_ui=ui,
            )
            deferred.queue_action(
                item_label,
                request.execute,
            )
        msg = f"Queued {n}x {label} — waiting for world to settle"
        _mark_pending(ui, msg)
        return True, msg
    except Exception as exc:  # noqa: BLE001
        last_msg = f"failed: could not queue {label}: {type(exc).__name__}: {exc}"
        if ui is not None:
            try:
                ui.status_text = last_msg
                ui.error_text = last_msg
            except Exception:
                pass
        _clear_pending(ui)
        return False, last_msg


# Hard fail if async detect never finishes (dead tick hook).
_SPAWN_PENDING_FAIL_SEC = 25.0


def poll_spawn_status(ui: Any, *, controller: Any | None = None) -> None:
    """Update spawn timer while pending; clear after BMS detect finishes.

    Important: do **not** keep the BMS timer alive just because the shared
    ``bl4_world_tools.deferred`` queue has unrelated work (aggro, item spawner,
    world tools). That made successful spawns show an endless timer.
    """
    # Advance background detect even while the BMS tab is open.
    if controller is not None:
        try:
            from .spawn_async import poll_async_spawn  # noqa: PLC0415

            poll_async_spawn(controller)
        except Exception:
            pass

    async_busy = False
    if controller is not None:
        from .spawn_async import has_async_spawn  # noqa: PLC0415

        async_busy = has_async_spawn(controller) and getattr(controller, "_async_status_ui", None) is ui
        # Background settle (hold_ui_pending=False) must never re-arm the timer.
        if async_busy and not bool(getattr(ui, "spawn_pending", False)):
            async_busy = False

    st = str(getattr(ui, "status_text", "") or "")
    st_low = st.lower()
    finished = (
        "spawn ok" in st_low
        or "spawn settled" in st_low
        or "timer off" in st_low
        or st_low.startswith("failed")
        or "timed out" in st_low
        or st_low.startswith("late-bound")
    )

    if finished and not async_busy:
        if bool(getattr(ui, "spawn_pending", False)):
            _clear_pending(ui)
        return

    if async_busy and bool(getattr(ui, "spawn_pending", False)):
        since = float(getattr(ui, "spawn_pending_since", 0.0) or 0.0)
        if since <= 0.0:
            since = time.monotonic()
            try:
                ui.spawn_pending_since = since  # type: ignore[attr-defined]
            except Exception:
                pass
        elapsed = max(0.0, time.monotonic() - since)
        if elapsed >= _SPAWN_PENDING_FAIL_SEC:
            if controller is not None:
                try:
                    controller._async_spawn = None  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    controller._async_status_ui = None  # type: ignore[attr-defined]
                except Exception:
                    pass
            ui.status_text = (
                f"Spawn timed out after {elapsed:.0f}s — detection never finished. "
                "Reload: rlm blimgui bl4_world_tools bl4_mob_spawner_hookedwidget"
            )
            ui.error_text = ui.status_text
            _clear_pending(ui)
            return
        if "Spawn OK" not in st and "failed" not in st_low and "timed out" not in st_low:
            if (
                st.startswith("Queued:")
                or st.startswith("Spawning")
                or "pausing" in st_low
                or "detecting" in st_low
                or "waiting" in st_low
            ):
                head = st.split("(")[0].rstrip()
                ui.status_text = f"{head} ({elapsed:.1f}s)"
            elif not st:
                ui.status_text = f"Spawning… ({elapsed:.1f}s)"
        return

    # No UI-held detect: clear leftover pending from a finished queue fire.
    if bool(getattr(ui, "spawn_pending", False)):
        waiting = (
            st.startswith("Queued:")
            or "waiting_for_stable" in st_low
            or st.startswith("Spawning")
        )
        if not waiting:
            _clear_pending(ui)
            return
        since = float(getattr(ui, "spawn_pending_since", 0.0) or 0.0)
        elapsed = max(0.0, time.monotonic() - since) if since > 0.0 else 0.0
        if elapsed >= _SPAWN_PENDING_FAIL_SEC:
            ui.status_text = (
                f"Spawn timed out after {elapsed:.0f}s — deferred queue never drained. "
                "Reload: rlm blimgui bl4_world_tools bl4_mob_spawner_hookedwidget"
            )
            ui.error_text = ui.status_text
            _clear_pending(ui)

