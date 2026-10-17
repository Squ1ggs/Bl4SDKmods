# -*- coding: utf-8 -*-
"""3.11.24: no sync-mail grab hitch; freecam spawn never sync-fires on bridge thread."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def patch_grab_no_sync_mail() -> None:
    path = ROOT / "loot_shapes.py"
    t = path.read_text(encoding="utf-8")
    old = '''def _give_shaped_serial_to_pc(pc: Any, serial: str) -> bool:
    """Put @U into that player's pack (guest PC from ServerUse, not host-only APIs)."""
    serial = str(serial or "").strip()
    if not serial.startswith("@U") or pc is None:
        return False
    idx = _party_index_for_pc(pc)
    local = _is_local_player_controller(pc)

    def _via_party_serial() -> bool:
        if idx is None:
            return False
        try:
            from .serial_rewards import _do_give_serial_to_player_indices_sync

            _do_give_serial_to_player_indices_sync(
                [serial],
                [int(idx)],
                scope_label="shaped grab",
                open_rewards=False,
            )
            return True
        except Exception:
            return False

    # Backpack first (sync mail freezes host ~1s per grab). Party serial fallback.
    if _add_serial_to_pc_backpack(pc, serial):
        return True
    if not local and _via_party_serial():
        return True
    return False'''
    new = '''def _give_shaped_serial_to_pc(pc: Any, serial: str) -> bool:
    """Put @U into that player's pack (guest PC from ServerUse, not host-only APIs).

    Never sync loyalty-mail here — each grant freezes the host ~1s (ULM/runtime:
    Sync delivery complete for shaped grab). Backpack inject only; if that fails
    ServerUse soft-unlocks and native Attract finishes without hitching the lobby.
    """
    serial = str(serial or "").strip()
    if not serial.startswith("@U") or pc is None:
        return False
    if _add_serial_to_pc_backpack(pc, serial):
        return True
    return False'''
    if old not in t:
        raise SystemExit("give_shaped missing")
    path.write_text(t.replace(old, new, 1), encoding="utf-8")
    print("ok grab no sync mail")


def patch_spawn_safe_no_sync() -> None:
    path = ROOT / "embedded_bms" / "spawn_safe.py"
    t = path.read_text(encoding="utf-8")
    # Replace freecam sync blocks with pose stamp + queue
    old = '''def queue_spawn_action(
    label: str,
    fn: SpawnFn,
    ui: Any,
    *,
    pause: bool = False,
) -> tuple[bool, str]:
    """
    Queue spawn on PlayerTick via bl4_world_tools deferred.

    Flushed only by BMS's listen-host ``PlayerTick`` owner.

    Freecam: fire immediately — get_pc() is DebugCameraController and the
    deferred drain used to stall forever (action ok, nothing at cam).

    ``pause=False`` (default): keep the world running so lobby clients do not
    time out during LoadPackage / boss settle. Hard-pause is optional for rare
    crash-prone IO paths that explicitly opt in.
    """
    try:
        from Squ1ggsBoostingTools.dev_tools import is_debug_cam_active

        if is_debug_cam_active():
            work = _wrap_paused(fn) if pause else fn
            ok, msg = work()
            if ok:
                _clear_pending(ui)
                ui.status_text = msg
                ui.error_text = ""
            else:
                ui.status_text = msg
                ui.error_text = msg
                _clear_pending(ui)
            return bool(ok), str(msg)
    except Exception:
        pass
    try:'''
    new = '''def _stamp_freecam_pose_for_queue() -> None:
    """Sticky look-at before deferred flush — never sync-fire from the bridge thread."""
    try:
        from Squ1ggsBoostingTools.dev_tools import freecam_spawn_pose, is_debug_cam_active
        from Squ1ggsBoostingTools.embedded_oak.engine import set_spawn_pose_override

        if not is_debug_cam_active():
            return
        pose = freecam_spawn_pose(distance=220.0)
        if pose is not None:
            set_spawn_pose_override(pose)
            try:
                from Squ1ggsBoostingTools import runtime_log

                runtime_log.note(
                    f"freecam: queued pose ({float(pose[0]):.0f}, "
                    f"{float(pose[1]):.0f}, {float(pose[2]):.0f})"
                )
            except Exception:
                pass
    except Exception:
        pass


def queue_spawn_action(
    label: str,
    fn: SpawnFn,
    ui: Any,
    *,
    pause: bool = False,
) -> tuple[bool, str]:
    """
    Queue spawn on PlayerTick / viewport tick via deferred.

    Never sync-fire while freecam is on from the EXE bridge thread — that froze
    the game and dropped the bridge (action begin spawn_mobs, no ok).

    Stamp sticky look-at pose, then flush on the next viewport/PlayerTick.
    """
    _stamp_freecam_pose_for_queue()
    try:'''
    if old not in t:
        raise SystemExit("queue_spawn_action freecam block missing")
    t = t.replace(old, new, 1)

    old2 = '''def queue_spawn_actions(
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
        from Squ1ggsBoostingTools.dev_tools import is_debug_cam_active

        if is_debug_cam_active():
            n = len(fns)
            last = ""
            ok_n = 0
            for i, fn in enumerate(fns):
                work = _wrap_paused(fn) if pause else fn
                ok, msg = work()
                last = str(msg)
                if ok:
                    ok_n += 1
                else:
                    ui.status_text = msg
                    ui.error_text = msg
                    _clear_pending(ui)
                    return False, f"Stopped after {ok_n}/{n}: {msg}"
            _clear_pending(ui)
            ui.status_text = last or f"Spawned {ok_n}x {label}"
            ui.error_text = ""
            return True, ui.status_text
    except Exception:
        pass
    try:'''
    new2 = '''def queue_spawn_actions(
    label: str,
    fns: list[SpawnFn],
    ui: Any,
    *,
    pause: bool = False,
) -> tuple[bool, str]:
    """Queue several spawns — one deferred action per frame (smooth multi-spawn)."""
    if not fns:
        return False, "nothing to queue"
    _stamp_freecam_pose_for_queue()
    try:'''
    if old2 not in t:
        raise SystemExit("queue_spawn_actions freecam block missing")
    path.write_text(t.replace(old2, new2, 1), encoding="utf-8")
    print("ok spawn_safe deferred")


def patch_controller_freecam() -> None:
    path = ROOT / "embedded_bms" / "controller.py"
    t = path.read_text(encoding="utf-8")

    # ViewportClient first so freecam still drains when Oak PlayerTick is odd.
    old_specs = '''        specs: tuple[tuple[str, object], ...] = (
            ("/Script/Engine.PlayerController:PlayerTick", post_u),
            ("/Script/GbxGame.GbxPlayerController:PlayerTick", post_u),
            ("/Script/OakGame.OakGameViewportClient:Tick", post_u),
            ("/Script/GbxGame.GbxGameViewportClient:Tick", post_u),
            ("/Script/Engine.GameViewportClient:Tick", post_u),
            ("/Script/Oak2.OakPlayerController:PlayerTick", post_u),
            ("/Script/OakGame.OakPlayerController:PlayerTick", post_u),
            ("/Script/Oak2.OakPlayerController:ReceiveTick", post_u),
            ("/Script/OakGame.OakPlayerController:ReceiveTick", post_u),
            ("/Script/Engine.PlayerController:ReceiveTick", post_u),
            ("/Script/Engine.PlayerController:PlayerTick", hooks.Type.POST),
            ("/Script/OakGame.OakGameViewportClient:Tick", hooks.Type.POST),
        )'''
    new_specs = '''        specs: tuple[tuple[str, object], ...] = (
            # Viewport first — freecam/DebugCamera still ticks the viewport when
            # Oak PlayerTick filtering / DCC shell would stall the spawn queue.
            ("/Script/OakGame.OakGameViewportClient:Tick", post_u),
            ("/Script/GbxGame.GbxGameViewportClient:Tick", post_u),
            ("/Script/Engine.GameViewportClient:Tick", post_u),
            ("/Script/Engine.PlayerController:PlayerTick", post_u),
            ("/Script/GbxGame.GbxPlayerController:PlayerTick", post_u),
            ("/Script/Oak2.OakPlayerController:PlayerTick", post_u),
            ("/Script/OakGame.OakPlayerController:PlayerTick", post_u),
            ("/Script/Oak2.OakPlayerController:ReceiveTick", post_u),
            ("/Script/OakGame.OakPlayerController:ReceiveTick", post_u),
            ("/Script/Engine.PlayerController:ReceiveTick", post_u),
            ("/Script/OakGame.OakGameViewportClient:Tick", hooks.Type.POST),
            ("/Script/Engine.PlayerController:PlayerTick", hooks.Type.POST),
        )'''
    if old_specs not in t:
        raise SystemExit("tick specs missing")
    t = t.replace(old_specs, new_specs, 1)

    # Remove sync freecam fire in _queue_async_spawn_ui
    old_q = '''        def _fire() -> tuple[bool, str]:
            if cache_code:
                cached, cache_msg = try_auto_cache_actor_def(cache_code)
                if cached:
                    target_ui.status_text = cache_msg
                elif cache_msg:
                    target_ui.error_text = cache_msg
            return self._fire_async_spawn(line_or_code, bossish=bossish, label=label, count=count, ui=target_ui)

        # Freecam: deferred PlayerTick never drained (get_pc=DCC) — fire now at cam.
        try:
            from Squ1ggsBoostingTools.dev_tools import is_debug_cam_active  # noqa: PLC0415

            if is_debug_cam_active():
                ok, msg = _fire()
                target_ui.status_text = msg
                target_ui.error_text = "" if ok else msg
                target_ui.spawn_pending = False  # type: ignore[attr-defined]
                return ok, msg
        except Exception:
            pass
        return queue_spawn_action(label, _fire, target_ui)'''
    new_q = '''        def _fire() -> tuple[bool, str]:
            if cache_code:
                cached, cache_msg = try_auto_cache_actor_def(cache_code)
                if cached:
                    target_ui.status_text = cache_msg
                elif cache_msg:
                    target_ui.error_text = cache_msg
            return self._fire_async_spawn(line_or_code, bossish=bossish, label=label, count=count, ui=target_ui)

        # Always queue — freecam sync-fire from the bridge froze the game (1.4.23).
        return queue_spawn_action(label, _fire, target_ui)'''
    if old_q not in t:
        raise SystemExit("queue_async freecam sync missing")
    t = t.replace(old_q, new_q, 1)

    # Freecam branch in _fire_async_spawn: use async_fire=True (zero poll) + sticky pose
    old_fc = '''        # Freecam: sync Oak at look-at (console fire ignores pose override).
        if freecam_on:
            with self._with_spawn_anchor():
                ok, msg = spawn_actor_def(
                    code,
                    count=count,
                    distance=dist,
                    spacing=effective_spawn_spacing(float(self.ui.spawn_spacing), count, actor_code=code),
                    allow_summon_fallback=bool(self.ui.summon_fallback) and not bossish,
                    fast_path=True,
                    async_fire=False,
                )
            target_ui.status_text = msg
            target_ui.error_text = "" if ok else msg
            target_ui.spawn_pending = False  # type: ignore[attr-defined]
            if ok:
                return begin_async_detect(
                    self,
                    line_or_code,
                    near=near,
                    before=before,
                    radius=radius,
                    bossish=bossish,
                    label=label,
                    ui=target_ui,
                    fired_msg=msg,
                    distance=dist,
                    spacing=effective_spawn_spacing(float(self.ui.spawn_spacing), count, actor_code=code),
                    count=count,
                    oak_already_fired=True,
                    hold_ui_pending=False,
                )
            return ok, msg

        with self._with_spawn_anchor():'''
    new_fc = '''        # Freecam: sticky pose + zero-poll Oak fire (full init). Never poll_cap wait.
        if freecam_on:
            with self._with_spawn_anchor():
                ok, msg = spawn_actor_def(
                    code,
                    count=count,
                    distance=dist,
                    spacing=effective_spawn_spacing(float(self.ui.spawn_spacing), count, actor_code=code),
                    allow_summon_fallback=bool(self.ui.summon_fallback) and not bossish,
                    fast_path=True,
                    async_fire=True,
                )
            target_ui.status_text = msg
            target_ui.error_text = "" if ok else msg
            target_ui.spawn_pending = False  # type: ignore[attr-defined]
            if ok:
                return begin_async_detect(
                    self,
                    line_or_code,
                    near=near,
                    before=before,
                    radius=radius,
                    bossish=bossish,
                    label=label,
                    ui=target_ui,
                    fired_msg=msg,
                    distance=dist,
                    spacing=effective_spawn_spacing(float(self.ui.spawn_spacing), count, actor_code=code),
                    count=count,
                    oak_already_fired=True,
                    hold_ui_pending=False,
                )
            return ok, msg

        with self._with_spawn_anchor():'''
    if old_fc not in t:
        raise SystemExit("fire_async freecam block missing")
    path.write_text(t.replace(old_fc, new_fc, 1), encoding="utf-8")
    print("ok controller freecam")


def bump() -> None:
    (ROOT / "_mod_version.py").write_text(
        '"""Single source of truth for the Squ1ggsBoostingTools package version."""\n\n'
        '__version__: str = "3.11.24"\n'
        "__version_info__: tuple[int, int, int] = (3, 11, 24)\n",
        encoding="utf-8",
    )
    cl = ROOT / "CHANGELOG.md"
    text = cl.read_text(encoding="utf-8")
    entry = (
        "## 3.11.24 / EXE 1.4.24\n"
        "- **Host grab hitch:** shaped Use no longer sync loyalty-mails each collect "
        "(~1s host freeze per grab) — backpack inject only; else soft-unlock + native Attract.\n"
        "- **Freecam NPC freeze / EXE disconnect:** never sync-fire Oak spawn from the "
        "bridge thread; stamp look-at pose + deferred viewport tick flush (zero-poll).\n"
        "\n"
    )
    if "## 3.11.24" not in text:
        text = text.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        cl.write_text(text, encoding="utf-8")
    print("ok bump 3.11.24")


if __name__ == "__main__":
    patch_grab_no_sync_mail()
    patch_spawn_safe_no_sync()
    patch_controller_freecam()
    bump()
    print("done")
