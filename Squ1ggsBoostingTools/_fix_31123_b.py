from pathlib import Path

p = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Borderlands 4"
    r"\sdk_mods\Squ1ggsBoostingTools\embedded_bms\spawn_safe.py"
)
t = p.read_text(encoding="utf-8")
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

    ``pause=False`` (default): keep the world running so lobby clients do not
    time out during LoadPackage / boss settle. Hard-pause is optional for rare
    crash-prone IO paths that explicitly opt in.
    """
    try:
        from Squ1ggsBoostingTools import spawn_deferred as deferred
        request = make_request(
            label,
            _wrap_paused(fn) if pause else fn,
            anchor=str(getattr(ui, "spawn_anchor", "local") or "local"),
            party_index=int(getattr(ui, "party_index", 2) or 2),
            status_ui=ui,
        )
        deferred.queue_action(label, request.execute)
        msg = f"Queued: {label} — waiting_for_stable_lobby"
        _mark_pending(ui, msg)
        return True, msg'''
new = '''def queue_spawn_action(
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
    try:
        from Squ1ggsBoostingTools import spawn_deferred as deferred
        request = make_request(
            label,
            _wrap_paused(fn) if pause else fn,
            anchor=str(getattr(ui, "spawn_anchor", "local") or "local"),
            party_index=int(getattr(ui, "party_index", 2) or 2),
            status_ui=ui,
        )
        deferred.queue_action(label, request.execute)
        msg = f"Queued: {label} — waiting_for_stable_lobby"
        _mark_pending(ui, msg)
        return True, msg'''
if old not in t:
    raise SystemExit("spawn_safe missing")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
print("ok spawn_safe")

# queue_spawn_actions: freecam fire all sync one by one
t = p.read_text(encoding="utf-8")
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
        from Squ1ggsBoostingTools import spawn_deferred as deferred
        n = len(fns)
        for i, fn in enumerate(fns):'''
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
    try:
        from Squ1ggsBoostingTools import spawn_deferred as deferred
        n = len(fns)
        for i, fn in enumerate(fns):'''
if old2 not in t:
    raise SystemExit("spawn_actions missing")
p.write_text(t.replace(old2, new2, 1), encoding="utf-8")
print("ok spawn_actions")
