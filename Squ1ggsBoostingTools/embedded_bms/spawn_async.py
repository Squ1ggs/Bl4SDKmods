"""Fire-and-forget spawns: console forward returns immediately; detect actors on later frames."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .spawn_core import find_new_characters_near, player_pawn_keys


@dataclass
class AsyncSpawnJob:
    code: str
    label: str
    started_at: float
    before: set[str]
    near: Any
    radius: float
    bossish: bool
    count: int = 1
    fired_msg: str = ""
    timeout: float = 18.0
    poll_every: float = 0.2
    last_poll_at: float = 0.0
    oak_fallback_done: bool = False
    distance: float = 350.0
    spacing: float = 125.0
    generation: int = 0
    state: str = "fired"
    breadcrumbs: list[str] = field(default_factory=list)


def _spawn_token_from_line(line_or_code: str) -> str:
    raw = (line_or_code or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    for prefix in ("oak_spawnai ", "oak_spawnai ", "oak_spawn ", "oak_spawn "):
        if low.startswith(prefix):
            parts = raw.split(None, 1)
            return parts[1].strip() if len(parts) > 1 else ""
    return raw


def fire_console_spawn(line_or_code: str) -> tuple[bool, str]:
    """Fire oak_spawnai without blocking the game thread.

    Prefer the bundled/embedded Oak Spawner module. Console ``oak_spawnai`` is
    handled by standalone ``bl4_oak_spawner`` when enabled and can hitch ~10s
    from repeated load_package probes.
    """
    token = _spawn_token_from_line(line_or_code)
    if not token:
        return False, "empty spawn token"
    try:
        from .oak_spawn import spawn_actor_def  # noqa: PLC0415

        ok, msg = spawn_actor_def(token, count=1, fast_path=True, async_fire=True)
        if ok:
            return True, msg
    except Exception:
        pass
    try:
        from gbx_actor_deploy import _pc_console_raw  # noqa: PLC0415
    except Exception as ex:  # noqa: BLE001
        return False, str(ex)
    last = "console forward failed"
    for cmd in (f"oak_spawnai {token}", f"oak_spawnai {token}"):
        ok, msg = _pc_console_raw(cmd)
        if ok:
            return True, f"Fired: {cmd} ({msg})"
        last = str(msg)
    return False, last


def is_async_spawn_line(line: str) -> bool:
    low = (line or "").strip().lower()
    return any(low.startswith(p) for p in ("oak_spawnai ", "oak_spawnai "))


def begin_async_detect(
    controller: Any,
    line_or_code: str,
    *,
    near: Any,
    before: set[str],
    radius: float,
    bossish: bool,
    label: str = "",
    ui: Any | None = None,
    fired_msg: str = "",
    distance: float = 350.0,
    spacing: float = 125.0,
    count: int = 1,
    oak_already_fired: bool = False,
    hold_ui_pending: bool = True,
) -> tuple[bool, str]:
    """Track spawn detection after console/Oak Spawner already fired.

    When ``oak_already_fired`` is True, never run Oak Spawner fallback — a second
    ResetSpawner is what caused duplicate bosses (first spawn streams in late).

    ``hold_ui_pending=False``: settle in background without the BMS spawn timer
    (menu-open detect used to never finish and left the timer running forever).
    """
    code = _spawn_token_from_line(line_or_code)
    if not code:
        return False, "empty spawn token"
    status_ui = ui if ui is not None else controller.ui
    from .lobby_stability import current_generation  # noqa: PLC0415

    generation = current_generation()
    controller._async_spawn = AsyncSpawnJob(  # noqa: SLF001
        code=code,
        label=label or code,
        started_at=time.monotonic(),
        before=set(before),
        near=near,
        radius=max(float(radius), 4500.0 if bossish else float(radius)),
        bossish=bool(bossish),
        count=max(1, int(count)),
        fired_msg=fired_msg or f"oak_spawnai {code}",
        distance=float(distance),
        spacing=float(spacing),
        # Already did thin-air Oak Spawner once — waiting only, no second spawn.
        oak_fallback_done=bool(oak_already_fired),
        generation=generation,
        state="detecting",
        breadcrumbs=[f"fired generation {generation}", "detecting"],
        timeout=6.0 if not hold_ui_pending else 18.0,
    )
    controller._async_status_ui = status_ui  # noqa: SLF001
    if hold_ui_pending:
        status_ui.spawn_pending = True  # type: ignore[attr-defined]
        try:
            status_ui.spawn_pending_since = time.monotonic()  # type: ignore[attr-defined]
        except Exception:
            pass
        status_ui.status_text = f"{fired_msg or 'Spawn fired'} — detecting spawn…"
    else:
        status_ui.spawn_pending = False  # type: ignore[attr-defined]
        try:
            status_ui.spawn_pending_since = 0.0  # type: ignore[attr-defined]
        except Exception:
            pass
        status_ui.status_text = f"{fired_msg or 'Spawn fired'} — settling (timer off)"
    status_ui.error_text = ""
    return True, status_ui.status_text


def start_async_spawn(
    controller: Any,
    line_or_code: str,
    *,
    near: Any,
    before: set[str],
    radius: float,
    bossish: bool,
    label: str = "",
    ui: Any | None = None,
) -> tuple[bool, str]:
    """Fire console spawn and track detection on ``_per_frame_tick``."""
    ok, msg = fire_console_spawn(line_or_code)
    if not ok:
        return ok, msg
    return begin_async_detect(
        controller,
        line_or_code,
        near=near,
        before=before,
        radius=radius,
        bossish=bossish,
        label=label,
        ui=ui,
        fired_msg=msg,
    )


def _try_oak_fallback(controller: Any, job: AsyncSpawnJob, ui: Any) -> bool:
    """Console forward often does nothing — run Oak Spawner once if detect stalls.

    Never use this after an Oak Spawner thin-air fire already ran (duplicates bosses).
    """
    if job.oak_fallback_done:
        return False
    job.oak_fallback_done = True
    try:
        from .oak_spawn import spawn_actor_def  # noqa: PLC0415

        ok, msg = spawn_actor_def(
            job.code,
            count=1,
            distance=job.distance,
            spacing=job.spacing,
            allow_summon_fallback=False,
            fast_path=True,
            async_fire=True,
        )
        ui.status_text = f"Oak Spawner retry: {msg}"
        return bool(ok)
    except Exception as ex:  # noqa: BLE001
        ui.status_text = f"Oak Spawner retry failed: {ex}"
        return False


def _is_non_combat_io(code: str) -> bool:
    low = (code or "").strip().lower()
    if not low:
        return False
    if low.startswith(("io_", "lootable_", "oakinteractive", "vending")):
        return True
    return any(s in low for s in ("goldenchest", "lostloot", "playerbank", "blackmarket", "firmware"))


def _finish_async_with_actor(controller: Any, job: AsyncSpawnJob, ui: Any, actor: Any) -> None:
    job.state = "fired"
    job.breadcrumbs.append(f"detected {actor}")
    try:
        controller.tracker.add_actor(actor, code=job.code)
    except Exception:
        pass
    code = job.code
    ui.error_text = ""
    # World IO / lootables are not combatants — skip aggro entirely.
    if _is_non_combat_io(code):
        try:
            low = f"{code} {actor}".lower()
            if "goldenchest" in low or "lootable_goldenchest" in low:
                from Squ1ggsBoostingTools.golden_chest_keybinds import remember_golden_chest  # noqa: PLC0415

                remember_golden_chest(actor)
        except Exception:
            pass
        ui.status_text = f"Spawn OK: {code}"
        controller._async_spawn = None  # noqa: SLF001
        controller._async_status_ui = None  # noqa: SLF001
        ui.spawn_pending = False  # type: ignore[attr-defined]
        try:
            ui.spawn_pending_since = 0.0  # type: ignore[attr-defined]
        except Exception:
            pass
        return
    # Aggro / ApplyDamage / SpawnDefaultController must NOT run on the ImGui draw
    # path (blimgui register_per_frame runs inside draw_tabbed_menu). Queue to
    # PlayerTick via bl4_world_tools.deferred instead.
    ui.status_text = f"Spawn OK: {code} — queuing aggro…"
    try:
        from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415

        def _aggro(_code: str = code) -> tuple[bool, str]:
            try:
                if hasattr(controller, "_apply_aggro_after_async_spawn"):
                    controller._apply_aggro_after_async_spawn(_code)
                return True, f"aggro {_code}"
            except Exception as ex:  # noqa: BLE001
                return False, f"aggro failed: {ex}"

        deferred.queue_action(f"Aggro after spawn {code}", _aggro)
    except Exception:
        try:
            if hasattr(controller, "_apply_aggro_after_async_spawn"):
                controller._apply_aggro_after_async_spawn(code)
            elif not str(getattr(ui, "status_text", "") or "").startswith("Spawn OK"):
                ui.status_text = f"Spawn OK: {code}"
        except Exception:
            ui.status_text = f"Spawn OK: {code}"
    controller._async_spawn = None  # noqa: SLF001
    controller._async_status_ui = None  # noqa: SLF001
    ui.spawn_pending = False  # type: ignore[attr-defined]
    try:
        ui.spawn_pending_since = 0.0  # type: ignore[attr-defined]
    except Exception:
        pass


def poll_async_spawn(controller: Any) -> None:
    """Advance in-flight spawn detection; clears ``spawn_pending`` when done.

    Prefer PlayerTick, but still allow completion while the BMS menu is open —
    skipping entirely during ImGui left jobs stuck and the spawn timer spinning.
    """
    job: AsyncSpawnJob | None = getattr(controller, "_async_spawn", None)
    if job is None:
        return
    in_imgui = False
    try:
        import blimgui as _blg  # noqa: PLC0415

        in_imgui = bool(getattr(_blg, "_IN_IMGUI_FRAME", False))
    except Exception:
        in_imgui = False
    # Heavy Oak Spawner fallback stays off the ImGui thread; finish/timeout/track is fine.
    ui = getattr(controller, "_async_status_ui", None) or controller.ui
    now = time.monotonic()
    from .lobby_stability import current_generation  # noqa: PLC0415

    generation = current_generation()
    if generation != job.generation:
        job.state = "failed"
        job.breadcrumbs.append(f"generation changed {job.generation}->{generation}")
        ui.status_text = f"failed: {job.code} [{'; '.join(job.breadcrumbs[-8:])}]"
        ui.error_text = ui.status_text
        controller._async_spawn = None  # noqa: SLF001
        controller._async_status_ui = None  # noqa: SLF001
        ui.spawn_pending = False  # type: ignore[attr-defined]
        return
    if now - job.started_at >= job.timeout:
        # Late bind: boss may be visible even when world-delta missed it.
        from .spawn_core import find_characters_matching_code_near  # noqa: PLC0415

        exclude = player_pawn_keys()
        late = find_characters_matching_code_near(
            job.near,
            job.code,
            radius=max(job.radius, 8000.0 if job.bossish else job.radius),
            exclude_keys=exclude,
        )
        if late:
            ui.status_text = f"Late-bound {job.code} — applying aggro…"
            _finish_async_with_actor(controller, job, ui, late[0])
            return
        job.state = "failed"
        job.breadcrumbs.append(f"detection timeout {job.timeout:.0f}s")
        from .spawn_core import oak_cache_prerequisite_message  # noqa: PLC0415

        prereq = oak_cache_prerequisite_message(job.code) if job.bossish else None
        if prereq:
            ui.status_text = prereq
            ui.error_text = prereq
        else:
            # Soft-fired spawns often already stand in the world — don't red-error the UI.
            ui.status_text = f"Spawn settled: {job.code} (detect timed out; check nearby)"
            ui.error_text = ""
        controller._async_spawn = None  # noqa: SLF001
        controller._async_status_ui = None  # noqa: SLF001
        ui.spawn_pending = False  # type: ignore[attr-defined]
        return
    if now - job.last_poll_at < job.poll_every:
        return
    job.last_poll_at = now
    # Prefer Squ1ggs last tracked actor when world-delta misses (common after soft success).
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

        spawned = getattr(ssp, "_SPAWNED", None) or []
        code_l = job.code.casefold()
        for entry in reversed(list(spawned)[-8:]):
            label = str(getattr(entry, "label", "") or "").casefold()
            actor = getattr(entry, "actor", None)
            if actor is None:
                continue
            if label == code_l or code_l in label or label in code_l:
                _finish_async_with_actor(controller, job, ui, actor)
                return
    except Exception:
        pass
    exclude = player_pawn_keys()
    new_actors = find_new_characters_near(
        job.before,
        job.near,
        radius=job.radius,
        exclude_keys=exclude,
        expected_code=job.code,
    )
    if not new_actors:
        elapsed = now - job.started_at
        # Mid-wait family scan for bosses (snapshot often empty at fire time).
        if job.bossish and elapsed >= 2.0:
            from .spawn_core import find_characters_matching_code_near  # noqa: PLC0415

            late = find_characters_matching_code_near(
                job.near,
                job.code,
                radius=max(job.radius, 8000.0),
                exclude_keys=exclude,
            )
            if late:
                _finish_async_with_actor(controller, job, ui, late[0])
                return
        # Bosses: retry Oak Spawner sooner if the first fire did not produce a trackable actor.
        # Skip heavy fallback during ImGui draw.
        fallback_at = 0.85 if job.bossish else 2.5
        if (not in_imgui) and elapsed >= fallback_at and not job.oak_fallback_done:
            _try_oak_fallback(controller, job, ui)
        if bool(getattr(ui, "spawn_pending", False)):
            ui.status_text = f"Waiting for {job.code}… ({elapsed:.1f}s)"
        return
    _finish_async_with_actor(controller, job, ui, new_actors[0])


def has_async_spawn(controller: Any) -> bool:
    return getattr(controller, "_async_spawn", None) is not None

