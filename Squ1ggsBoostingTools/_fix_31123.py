"""3.11.23: freecam spawn drain + faster grab-ready."""
from __future__ import annotations

from pathlib import Path

STEAM = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Borderlands 4"
    r"\sdk_mods\Squ1ggsBoostingTools"
)


def must(path: Path, old: str, new: str, name: str) -> None:
    t = path.read_text(encoding="utf-8")
    if old not in t:
        raise SystemExit(f"MISSING {name}")
    path.write_text(t.replace(old, new, 1), encoding="utf-8")
    print("ok", name)


ctrl = STEAM / "embedded_bms" / "controller.py"

# 1) Unwrap freecam get_pc so Oak PC ticks still drain the queue
must(
    ctrl,
    '''    def _on_spawn_player_tick(self, *_args: object, **_kwargs: object) -> None:
        """Safe context for deferred spawn flush + detect / tracker prune."""
        # PlayerTick may run for several controllers in a populated lobby. Only
        # the listen-host controller owns the queue.
        try:
            from mods_base import get_pc  # noqa: PLC0415

            host_pc = get_pc()
            host_ps = getattr(host_pc, "PlayerState", None) if host_pc is not None else None
            for candidate in _args[:2]:
                if candidate is None or isinstance(candidate, (bool, int, float, str, bytes)):
                    continue
                try:
                    cls_obj = getattr(candidate, "Class", None)
                    cls_text = str(getattr(cls_obj, "Name", "") or cls_obj or "").lower()
                except Exception:
                    cls_text = ""
                if "playercontroller" not in cls_text or host_pc is None:
                    # ViewportClient Tick etc.: no PC in args — still drain.
                    continue
                if candidate is host_pc:
                    break
                try:
                    candidate_ps = getattr(candidate, "PlayerState", None)
                except Exception:
                    candidate_ps = None
                if host_ps is None or candidate_ps is not host_ps:
                    return
        except Exception:
            pass''',
    '''    def _on_spawn_player_tick(self, *_args: object, **_kwargs: object) -> None:
        """Safe context for deferred spawn flush + detect / tracker prune."""
        # PlayerTick may run for several controllers in a populated lobby. Only
        # the listen-host controller owns the queue.
        # Freecam: get_pc() is DebugCameraController (often no PlayerState) — that
        # used to abort every Oak PC tick and leave the queue forever (action ok,
        # nothing at cam). Unwrap to gameplay PC before comparing.
        try:
            from mods_base import get_pc  # noqa: PLC0415

            host_pc = get_pc()
            try:
                from Squ1ggsBoostingTools.dev_tools import (  # noqa: PLC0415
                    _gameplay_pc,
                    is_debug_cam_active,
                )

                if is_debug_cam_active():
                    gp = _gameplay_pc()
                    if gp is not None:
                        host_pc = gp
            except Exception:
                pass
            host_ps = getattr(host_pc, "PlayerState", None) if host_pc is not None else None
            for candidate in _args[:2]:
                if candidate is None or isinstance(candidate, (bool, int, float, str, bytes)):
                    continue
                try:
                    cls_obj = getattr(candidate, "Class", None)
                    cls_text = str(getattr(cls_obj, "Name", "") or cls_obj or "").lower()
                except Exception:
                    cls_text = ""
                # DebugCameraController contains "playercontroller" substring — treat
                # as host when freecam shell is the tick owner.
                if "playercontroller" not in cls_text or host_pc is None:
                    continue
                if candidate is host_pc:
                    break
                try:
                    candidate_ps = getattr(candidate, "PlayerState", None)
                except Exception:
                    candidate_ps = None
                # Freecam DCC may have null PS — never abort the whole drain for that.
                if host_ps is not None and candidate_ps is not None and candidate_ps is not host_ps:
                    return
        except Exception:
            pass''',
    "tick_unwrap_freecam",
)

# 2) Drain pending from per_frame when freecam (ImGui path still blocked in flush)
must(
    ctrl,
    '''    def _per_frame_tick(self) -> None:
        """ImGui-adjacent: UI bookkeeping only — no spawn/aggro/UObject flush."""
        self._sync_window_owned()
        self._try_register_io_tab()
        try:
            self._ensure_spawn_tick_hook()
        except Exception:
            pass
        try:''',
    '''    def _per_frame_tick(self) -> None:
        """ImGui-adjacent: UI bookkeeping; freecam drain when PlayerTick stalls."""
        self._sync_window_owned()
        self._try_register_io_tab()
        try:
            self._ensure_spawn_tick_hook()
        except Exception:
            pass
        # While freecam owns get_pc(), Oak PlayerTick filtering used to skip flush.
        # Kick one deferred spawn from here when the menu is closed.
        try:
            from Squ1ggsBoostingTools.dev_tools import is_debug_cam_active  # noqa: PLC0415
            from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415
            import blimgui as _blg  # noqa: PLC0415

            if (
                is_debug_cam_active()
                and deferred.has_pending()
                and not bool(getattr(_blg, "_IN_IMGUI_FRAME", False))
            ):
                deferred.flush_tick(max_items=1, owner="Squ1ggsBoostingTools")
        except Exception:
            pass
        try:''',
    "per_frame_freecam_drain",
)

# 3) When freecam on, fire spawn immediately (no queue) in _queue_async_spawn_ui
must(
    ctrl,
    '''        def _fire() -> tuple[bool, str]:
            if cache_code:
                cached, cache_msg = try_auto_cache_actor_def(cache_code)
                if cached:
                    target_ui.status_text = cache_msg
                elif cache_msg:
                    target_ui.error_text = cache_msg
            return self._fire_async_spawn(line_or_code, bossish=bossish, label=label, count=count, ui=target_ui)

        return queue_spawn_action(label, _fire, target_ui)''',
    '''        def _fire() -> tuple[bool, str]:
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
        return queue_spawn_action(label, _fire, target_ui)''',
    "queue_ui_freecam_sync",
)

# loot_shapes: shorter join quiet + soft-unlock remaining on Use abort
ls = STEAM / "loot_shapes.py"
must(
    ls,
    '''            quiet = max(quiet, 32.0 if pin_n >= 80 else (26.0 if pin_n >= 30 else 22.0))''',
    '''            # Was 32/26/22 — lobby waited forever after join before Use worked.
            quiet = max(quiet, 12.0 if pin_n >= 80 else (10.0 if pin_n >= 30 else 8.0))''',
    "join_quiet_shorter",
)

must(
    ls,
    '''def _pause_coop_force_net_for_grab(*, seconds: float = 2.0, reason: str = "") -> bool:
    """Stop ForceNet while guests Use — soft late ForceNet + Use = 0xffffffffffffffff.

    ULM dump / unrealsdk showed force_done "3/139 visible (139 skipped)" then grabs
    AV'd the host. Abort soft-late + pause full publish; do not ForceNet dying actors.
    """
    global _coop_pickup_unlock_at, _coop_force_net_pause_log_at, _late_join_soft_republish
    if not _coop_pickup_safe_active and not _late_join_soft_republish:
        return False
    # Soft late ForceNet during Use is the poison-wrapper crash path (…2C7D3DED family).
    if _late_join_soft_republish or bool(_last_layout.get("pickup_safe_soft_late")):
        try:
            _abort_coop_force_net_publish(
                reason=str(reason or "shaped Use — soft late ForceNet aborted"),
                soft_only=True,
            )
        except Exception:
            _late_join_soft_republish = False
            _last_layout.pop("pickup_safe_soft_late", None)
    if not _coop_pickup_safe_active:
        return True
    now = time.monotonic()
    wait = max(2.5, float(seconds))
    already = float(_coop_pickup_unlock_at or 0.0) > now + 0.35
    _extend_coop_publish_pause(now, seconds=wait)
    note = str(reason or "co-op ForceNet paused for grab").strip()
    if note and (not already) and (now - float(_coop_force_net_pause_log_at or 0.0)) >= 2.5:
        _coop_force_net_pause_log_at = now
        _log_dev(note)
    return True''',
    '''def _pause_coop_force_net_for_grab(*, seconds: float = 2.0, reason: str = "") -> bool:
    """Stop ForceNet while guests Use — soft late ForceNet + Use = 0xffffffffffffffff.

    Abort soft-late + pause full publish; soft-unlock leftovers so Use still works
    without waiting for ForceNet (re-grab after first Use was stuck).
    """
    global _coop_pickup_unlock_at, _coop_force_net_pause_log_at, _late_join_soft_republish
    if not _coop_pickup_safe_active and not _late_join_soft_republish:
        return False
    if _late_join_soft_republish or bool(_last_layout.get("pickup_safe_soft_late")):
        try:
            _abort_coop_force_net_publish(
                reason=str(reason or "shaped Use — soft late ForceNet aborted"),
                soft_only=True,
            )
        except Exception:
            _late_join_soft_republish = False
            _last_layout.pop("pickup_safe_soft_late", None)
    # Soft-unlock remaining held pins so siblings stay Useable without ForceNet.
    try:
        stamped = 0
        for row in list(_pinned_slots):
            if not row.get("hold") or row.get("guest_skip"):
                continue
            inv = _resolve_pin_inv(row, fresh=False)
            if inv is None or not _live(inv):
                continue
            try:
                _stamp_guest_grab_ready(inv)
                row["client_motion_unlocked"] = True
                stamped += 1
            except Exception:
                continue
            if stamped >= 24:
                break
    except Exception:
        pass
    if not _coop_pickup_safe_active:
        return True
    now = time.monotonic()
    wait = max(1.2, float(seconds))
    already = float(_coop_pickup_unlock_at or 0.0) > now + 0.35
    _extend_coop_publish_pause(now, seconds=wait)
    note = str(reason or "co-op ForceNet paused for grab").strip()
    if note and (not already) and (now - float(_coop_force_net_pause_log_at or 0.0)) >= 2.5:
        _coop_force_net_pause_log_at = now
        _log_dev(note)
    return True''',
    "pause_soft_unlock_siblings",
)

# Soft settle: stamp unlock all held pins immediately (don't wait for ForceNet drip)
must(
    ls,
    '''    # Late-join soft: stamp Useable only — ForceNet here raced guest Use (UECC …ffffffff).
    if soft_late:
        publish_budget = 4 if n > 60 else 3
        unlock_budget = 0
        retry_gap = 0.20 if n > 80 else 0.14''',
    '''    # Late-join soft: stamp Useable only — ForceNet here raced guest Use (UECC …ffffffff).
    if soft_late:
        publish_budget = 8 if n > 60 else 6
        unlock_budget = 0
        retry_gap = 0.08 if n > 80 else 0.06''',
    "soft_late_faster_stamp",
)

# Guest blank @U: soft unlock + native Attract instead of forever Block defer spam
must(
    ls,
            '''            try:
                _stamp_guest_grab_ready(inv)
            except Exception:
                pass
            try:
                _queue_deferred_shaped_collect(obj, inv, row)
                _log_dev(
                    f"Shape Use (guest): no cached @U — deferred backpack resolve."
                )
                try:
                    from unrealsdk.hooks import Block

                    return Block
                except Exception:
                    return None
            except Exception:
                pass
            try:
                _soft_unlock_shaped_pickup(inv, wake_physics=True)
            except Exception:
                pass
            _release_pin_for_pickup(inv, row)
            _log_dev(
                f"Shape Use (guest): no cached @U — native Attract after soft unlock."
            )
            return None''',
    '''            # Prefer native Attract over forever Block+defer (lobby "can't grab again").
            try:
                _soft_unlock_shaped_pickup(inv, wake_physics=True)
            except Exception:
                pass
            _release_pin_for_pickup(inv, row)
            _log_dev(
                f"Shape Use (guest): no cached @U — native Attract after soft unlock."
            )
            return None''',
    "guest_blank_native",
)

print("all patches applied")
