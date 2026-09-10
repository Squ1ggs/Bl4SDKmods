"""Embedded hostile mob / IO spawning backend for Squ1ggs Boosting Tools."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .aggro import apply_aggro_mode
from .oak_spawn import oak_available, run_oak_line, spawn_actor_def
from .spawn_core import (
    MAX_DEPLOY_COUNT,
    MobTracker,
    abstract_actor_code_message,
    clamp_deploy_count,
    disable_world_spawn_budget,
    DLC_OAK_CACHE_ACTORS,
    effective_spawn_spacing,
    find_new_characters_near,
    is_abstract_actor_code,
    is_boss_actor_code,
    oak_cache_prerequisite_message,
    player_pawn_keys,
    prefer_combat_boss_code,
    resolve_aggro_target,
    resolve_concrete_actor_code,
    snapshot_character_keys,
    try_auto_cache_actor_def,
)

_blimgui: Any | None = None
_BLIMGUI_ERR: str | None = None


def _ensure_blimgui() -> Any | None:
    """Lazy import — bl4_mob_spawner_hookedwidget may load before the blimgui mod finishes booting."""
    global _blimgui, _BLIMGUI_ERR
    if _blimgui is not None:
        return _blimgui
    try:
        import blimgui as bg  # noqa: PLC0415

        _blimgui = bg
        _BLIMGUI_ERR = None
    except Exception as exc:  # noqa: BLE001
        _blimgui = None
        _BLIMGUI_ERR = str(exc)
    return _blimgui


MOD_DIR = Path(__file__).resolve().parent
# Short labels retained for the reusable embedded panel renderer.
WINDOW_TITLE = "BMS"
IO_TAB_TITLE = "BMS · IO"
COMMAND_PREFIX = "mob"  # legacy; preferred prefix is ``bms``
BMS_COMMAND_PREFIX = "bms"
_LOG = "[BMS]"
_log = logging.getLogger("bl4_mob_spawner_hookedwidget")


def _pawn_from_pc(pc: Any | None) -> Any | None:
    if pc is None:
        return None
    pawn = getattr(pc, "Pawn", None)
    if pawn is not None:
        return pawn
    get_pawn = getattr(pc, "GetPawn", None)
    try:
        return get_pawn() if callable(get_pawn) else None
    except Exception:
        return None


AGGRO_MODES: list[tuple[str, str]] = [
    ("attack_me", "Attack me (local pawn)"),
    ("attack_party", "Attack party member"),
    ("free_for_all", "Free-for-all (mobs vs mobs)"),
    ("nearest_other", "Nearest other mob"),
    ("passive", "Passive (spawn only)"),
]


def _collapsing_show(ret: Any) -> bool:
    try:
        if isinstance(ret, tuple):
            return bool(ret[0])
        return bool(ret)
    except Exception:
        return False


def _load_encounter_presets() -> list[tuple[str, str]]:
    path = MOD_DIR / "data" / "mob_encounter_presets.txt"
    if not path.is_file():
        return []
    out: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            label, cmd = [x.strip() for x in line.split("|", 1)]
        else:
            label, cmd = line, line
        if cmd:
            out.append((label, cmd))
    return out


@dataclass(slots=True)
class MobUi:
    status_text: str = "Ready."
    error_text: str = ""
    aggro_mode: str = "attack_me"
    party_index: int = 2
    # Where to place the spawn: local player, selected party row, or nearest NPC.
    spawn_anchor: str = "local"  # "local" | "party" | "npc_nearest"
    scan_radius: float = 6000.0
    spawn_distance: float = 350.0
    spawn_spacing: float = 125.0
    summon_fallback: bool = True
    damage_wake: bool = True
    spawn_pending: bool = False
    spawn_pending_since: float = 0.0
    squ1ggs_section_idx: int = 0
    squ1ggs_filter: str = ""
    squ1ggs_selected_code: str = ""
    squ1ggs_deploy_count: int = 1
    squ1ggs_multi_select: set[str] = field(default_factory=set)
    squ1ggs_multi_select_mode: bool = False
    squ1ggs_search_all: bool = False
    max_deploy_count: int = MAX_DEPLOY_COUNT
    unlimited_world_spawns: bool = True
    world_prop_filter: str = ""
    world_prop_selected: str = ""
    world_prop_idx: int = 0
    world_difficulty: int = 7
    game_stage: int = 30


_TRACKER_PRUNE_INTERVAL_SEC = 4.0


def _mob_ui_needs_reset(ui: MobUi) -> bool:
    """Hot-reload safety — slotted MobUi from an older build cannot gain new fields."""
    required = (
        "squ1ggs_multi_select",
        "squ1ggs_multi_select_mode",
        "squ1ggs_search_all",
        "spawn_pending",
        "spawn_pending_since",
        "max_deploy_count",
        "unlimited_world_spawns",
        "world_prop_filter",
        "spawn_anchor",
    )
    return any(not hasattr(ui, name) for name in required)


class MobSpawnerController:
    def __init__(self) -> None:
        self.ui = MobUi()
        self.io_ui = None
        self.tracker = MobTracker()
        self.window_owned = False
        self.encounter_presets = _load_encounter_presets()
        self._last_tracker_prune_at = 0.0
        self._drawing_ui = False
        self._drawing_io_ui = False
        self._async_spawn = None
        self._async_status_ui = None
        self._io_tab_registered = False
        self._draw_io_tab = None
        self._spawn_tick_hook_path: str | None = None
        self._spawn_tick_hook_id: str | None = None
        self._spawn_tick_hook_type: object | None = None
        self._last_lobby_observe_at = 0.0
        self._last_spawn_drain_frame_token: tuple[str, float] | None = None
        self._last_spawn_drain_wall_at = 0.0

    def on_enable(self) -> None:
        if _mob_ui_needs_reset(self.ui):
            self.ui = MobUi()
        self._io_tab_registered = False
        self._draw_io_tab = None
        try:
            from .io_spawner_tab import IoUi, draw_io_tab  # noqa: PLC0415

            if self.io_ui is None or not hasattr(self.io_ui, "io_category"):
                self.io_ui = IoUi()
            self._draw_io_tab = draw_io_tab
        except Exception as ex:  # noqa: BLE001
            _log.warning("%s IO tab unavailable: %s", _LOG, ex)
            self._draw_io_tab = None
        bg = _ensure_blimgui()
        if bg is not None and not getattr(
            __import__(f"{__package__}", fromlist=["EMBEDDED_IN_SQBT"]),
            "EMBEDDED_IN_SQBT",
            False,
        ):
            bg.register_tab(WINDOW_TITLE, self.draw_ui)
            self._try_register_io_tab()
            if hasattr(bg, "register_per_frame"):
                bg.register_per_frame(self._per_frame_tick)
        elif bg is not None and hasattr(bg, "register_per_frame"):
            bg.register_per_frame(self._per_frame_tick)
        else:
            _log.warning("%s blimgui unavailable on enable: %s", _LOG, _BLIMGUI_ERR)
        self._ensure_spawn_tick_hook()
        try:
            from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415
            from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

            deferred.claim_drain_owner("Squ1ggsBoostingTools")
            ssp.clear_spawn_player_controller_override()
        except Exception:
            pass
        # Host bots / Echo4 always expect local placement unless UI is set to party.
        if str(getattr(self.ui, "spawn_anchor", "local") or "local").lower() not in (
            "local",
            "party",
            "npc_nearest",
        ):
            self.ui.spawn_anchor = "local"
        _log.info(
            "%s enabled — Mob Spawner embedded in Squ1ggs Boosting Tools. "
            "Control it from the desktop Mob and IO Spawner tab.",
            _LOG,
        )

    def _try_register_io_tab(self) -> None:
        if getattr(self, "_io_tab_registered", False):
            return
        if self._draw_io_tab is None:
            return
        bg = _ensure_blimgui()
        if bg is None:
            return
        try:
            bg.register_tab(IO_TAB_TITLE, lambda: self._draw_io_tab(self))
            self._io_tab_registered = True
        except Exception as ex:  # noqa: BLE001
            _log.warning("%s IO tab register failed: %s", _LOG, ex)

    def on_disable(self) -> None:
        bg = _ensure_blimgui()
        if bg is not None:
            if hasattr(bg, "unregister_per_frame"):
                try:
                    bg.unregister_per_frame(self._per_frame_tick)
                except Exception:
                    pass
            try:
                bg.remove_tab(WINDOW_TITLE)
            except Exception:
                pass
            try:
                bg.remove_tab(IO_TAB_TITLE)
            except Exception:
                pass
        self._unregister_spawn_tick_hook()
        try:
            from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415

            deferred.release_drain_owner("Squ1ggsBoostingTools")
        except Exception:
            pass
        self.window_owned = False

    def _sync_window_owned(self) -> None:
        bg = _ensure_blimgui()
        if bg is None:
            self.window_owned = False
            return
        if self.window_owned and not bg.is_mod_menu_open():
            self.window_owned = False

    def _ensure_spawn_tick_hook(self) -> None:
        """Engine tick: detect spawned actors + prune — never from ImGui draw."""
        installed = list(getattr(self, "_spawn_tick_hooks", None) or [])
        # Upgrade older single-path ReceiveTick-only registration after reload.
        if installed:
            return
        old_path = str(getattr(self, "_spawn_tick_hook_path", "") or "")
        if old_path and "PlayerTick" in old_path:
            # Legacy single PlayerTick hook is fine until disable/reload.
            return
        if old_path:
            self._unregister_spawn_tick_hook()
        try:
            import unrealsdk.hooks as hooks  # pyright: ignore[reportMissingImports]
        except Exception:
            return
        # POST often fails to install; item_spawner succeeds with PlayerTick +
        # POST_UNCONDITIONAL — match that so deferred F6 spawns actually flush.
        post_u = getattr(hooks.Type, "POST_UNCONDITIONAL", hooks.Type.POST)
        specs: tuple[tuple[str, object], ...] = (
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
        )
        installed = []
        for path, hook_type in specs:
            hook_id = f"bl4_mob_spawner_hookedwidget.player_tick:{path.rsplit(':', 1)[-1]}"
            try:
                if hooks.add_hook(path, hook_type, hook_id, self._on_spawn_player_tick):
                    installed.append((path, hook_type, hook_id))
                    _log.info("%s tick hook: %s", _LOG, path)
                    break  # one live drain path is enough
            except Exception:
                continue
        self._spawn_tick_hooks = installed
        # Compat with older poll/UI checks that read a single path.
        if installed:
            self._spawn_tick_hook_path = installed[0][0]
            self._spawn_tick_hook_id = installed[0][2]
            self._spawn_tick_hook_type = installed[0][1]
        else:
            _log.warning("%s: no spawn tick hook — relying on blimgui post-frame drain", _LOG)

    def _unregister_spawn_tick_hook(self) -> None:
        installed = list(getattr(self, "_spawn_tick_hooks", None) or [])
        if not installed:
            path = getattr(self, "_spawn_tick_hook_path", None)
            hook_id = getattr(self, "_spawn_tick_hook_id", None)
            if path and hook_id:
                installed = [
                    (
                        path,
                        getattr(self, "_spawn_tick_hook_type", None),
                        hook_id,
                    )
                ]
        if not installed:
            return
        try:
            import unrealsdk.hooks as hooks  # pyright: ignore[reportMissingImports]
        except Exception:
            self._spawn_tick_hooks = []
            self._spawn_tick_hook_path = None
            self._spawn_tick_hook_id = None
            self._spawn_tick_hook_type = None
            return
        for path, hook_type, hook_id in installed:
            try:
                hooks.remove_hook(path, hook_type or hooks.Type.POST, hook_id)
            except Exception:
                pass
        self._spawn_tick_hooks = []
        self._spawn_tick_hook_path = None
        self._spawn_tick_hook_id = None
        self._spawn_tick_hook_type = None

    def _on_spawn_player_tick(self, *_args: object, **_kwargs: object) -> None:
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
            pass
        try:
            from mods_base import ENGINE  # noqa: PLC0415

            viewport = getattr(ENGINE, "GameViewport", None) if ENGINE is not None else None
            world = getattr(viewport, "World", None) if viewport is not None else None
            frame_token = (str(world), float(getattr(world, "TimeSeconds")))
            wall_now = time.monotonic()
            if frame_token == self._last_spawn_drain_frame_token and wall_now - self._last_spawn_drain_wall_at < 0.005:
                return
            self._last_spawn_drain_frame_token = frame_token
            self._last_spawn_drain_wall_at = wall_now
        except Exception:
            # Host-controller filtering above remains the fallback on SDK builds
            # that do not expose World.TimeSeconds.
            pass
        try:
            from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415
            from .lobby_stability import observe_generation  # noqa: PLC0415

            now = time.monotonic()
            if deferred.has_pending():
                observe_generation()
                self._last_lobby_observe_at = now
            if deferred.has_pending():
                deferred.flush_tick(max_items=1, owner="Squ1ggsBoostingTools")
        except Exception:
            pass
        try:
            from .spawn_async import has_async_spawn, poll_async_spawn  # noqa: PLC0415

            if has_async_spawn(self):
                poll_async_spawn(self)
        except Exception:
            pass
        if not self.tracker.mobs:
            return
        now = time.monotonic()
        if now - self._last_tracker_prune_at < _TRACKER_PRUNE_INTERVAL_SEC:
            return
        self._last_tracker_prune_at = now
        try:
            self.tracker.clear_dead()
        except Exception:
            pass

    def _per_frame_tick(self) -> None:
        """ImGui-adjacent: UI bookkeeping only — no spawn/aggro/UObject flush."""
        self._sync_window_owned()
        self._try_register_io_tab()
        try:
            self._ensure_spawn_tick_hook()
        except Exception:
            pass
        try:
            from bl4_world_tools import hooks  # noqa: PLC0415

            hooks.register()
        except Exception:
            pass

    def _open_mod_menu_tab(self) -> bool:
        bg = _ensure_blimgui()
        if bg is None:
            self.ui.error_text = (
                f"blimgui unavailable: {_BLIMGUI_ERR or 'enable BLImGui mod and run rlm blimgui bl4_mob_spawner_hookedwidget'}"
            )
            return False
        try:
            # No debounce here — toggle_tabbed_mod_menu / prepare_menu_toggle already gated.
            self.window_owned = True
            bg.open_mod_menu(WINDOW_TITLE)
            self.ui.error_text = ""
            self.ui.status_text = "BL4 Mod Menu — BMS tab (F1 → BMS, or Ctrl+F6)."
            return True
        except Exception as ex:  # noqa: BLE001
            self.window_owned = False
            self.ui.error_text = str(ex)
            return False

    def toggle_window(self) -> None:
        bg = _ensure_blimgui()
        if bg is None:
            self.ui.error_text = (
                f"blimgui unavailable: {_BLIMGUI_ERR or 'enable BLImGui mod and run rlm blimgui bl4_mob_spawner_hookedwidget'}"
            )
            return
        if hasattr(bg, "toggle_tabbed_mod_menu"):
            bg.toggle_tabbed_mod_menu(self, tab=WINDOW_TITLE, open_fn=None)
            return
        if bg.is_mod_menu_open():
            if self.window_owned:
                self.window_owned = False
                try:
                    from blimgui import draw_tabbed_menu  # noqa: PLC0415

                    if hasattr(bg, "close_window_if_draw_callback"):
                        bg.close_window_if_draw_callback(draw_tabbed_menu)
                    else:
                        bg.close_window()
                except Exception as ex:  # noqa: BLE001
                    self.ui.error_text = str(ex)
                return
            self._open_mod_menu_tab()
            return
        if hasattr(bg, "close_conflicting_menus"):
            bg.close_conflicting_menus(keep_callback=None)
        self._open_mod_menu_tab()

    def _resolve_spawn_anchor_pc(self) -> Any | None:
        """PC whose pawn is used for spawn placement (host local or party guest)."""
        anchor = str(getattr(self.ui, "spawn_anchor", "local") or "local").strip().lower()
        if anchor == "party":
            try:
                from Squ1ggsBoostingTools.dev_tools import _pc_for_party_index  # noqa: PLC0415

                # party_index is a live PlayerArray index (0-based) from EXE player_select.
                pc, _err = _pc_for_party_index(max(0, int(self.ui.party_index)))
                if pc is not None:
                    return pc
            except Exception:
                pass
        try:
            from ..item_spawn.spawn_pc import resolve_spawn_pc

            return resolve_spawn_pc()
        except Exception:
            return None

    def _spawn_reference_loc(self) -> Any | None:
        if str(getattr(self.ui, "spawn_anchor", "local") or "local").lower() == "npc_nearest":
            try:
                from .spawn_anchor import actor_location  # noqa: PLC0415

                return actor_location(self._resolve_spawn_anchor_actor())
            except Exception:
                return None
        try:
            pc = self._resolve_spawn_anchor_pc()
            pawn = _pawn_from_pc(pc)
            if pawn is None:
                return None
            for meth in ("K2_GetActorLocation", "GetActorLocation"):
                fn = getattr(pawn, meth, None)
                if callable(fn):
                    try:
                        return fn()
                    except Exception:
                        pass
        except Exception:
            pass
        return None

    def _resolve_spawn_anchor_actor(self) -> Any | None:
        """Resolve the current NPC anchor from the local player's position."""
        if str(getattr(self.ui, "spawn_anchor", "local") or "local").lower() != "npc_nearest":
            return None
        try:
            from .spawn_anchor import nearest_npc  # noqa: PLC0415

            pc = self._resolve_spawn_anchor_pc()
            pawn = _pawn_from_pc(pc)
            return nearest_npc(pawn, max_distance=float(self.ui.scan_radius))
        except Exception:
            return None

    def _with_spawn_anchor(self):
        """Context manager: place Oak Spawner spawn at the chosen player/NPC anchor."""
        from contextlib import nullcontext  # noqa: PLC0415

        anchor = str(getattr(self.ui, "spawn_anchor", "local") or "local").strip().lower()
        if anchor == "npc_nearest":
            actor = self._resolve_spawn_anchor_actor()
            if actor is None:
                return nullcontext()
            try:
                from Squ1ggsBoostingTools.embedded_oak.engine import spawn_at_actor  # noqa: PLC0415

                return spawn_at_actor(actor, clear_on_exit=True)
            except Exception:
                return nullcontext()
        if anchor != "party":
            return nullcontext()
        pc = self._resolve_spawn_anchor_pc()
        if pc is None:
            return nullcontext()
        try:
            from Squ1ggsBoostingTools.embedded_oak.engine import spawn_at_player_controller  # noqa: PLC0415

            return spawn_at_player_controller(pc, clear_on_exit=True)
        except Exception:
            return nullcontext()

    def _deploy_gbx(self, code: str, *, count: int | None = None) -> tuple[bool, str]:
        cap = int(getattr(self.ui, "max_deploy_count", MAX_DEPLOY_COUNT))
        n = clamp_deploy_count(
            count if count is not None else self.ui.squ1ggs_deploy_count,
            max_cap=cap,
        )
        spacing = effective_spawn_spacing(float(self.ui.spawn_spacing), n, actor_code=code)
        with self._with_spawn_anchor():
            return spawn_actor_def(
                code,
                count=n,
                distance=float(self.ui.spawn_distance),
                spacing=spacing,
                allow_summon_fallback=bool(self.ui.summon_fallback),
                max_count=cap,
            )

    def _fire_async_spawn(
        self,
        line_or_code: str,
        *,
        bossish: bool,
        label: str,
        count: int = 1,
        ui: Any | None = None,
    ) -> tuple[bool, str]:
        from .spawn_async import begin_async_detect, fire_console_spawn, _spawn_token_from_line  # noqa: PLC0415

        target_ui = ui if ui is not None else self.ui
        code = _spawn_token_from_line(line_or_code) or (line_or_code or "").strip()
        if not code:
            return False, "empty spawn token"

        if bool(getattr(target_ui, "unlimited_world_spawns", True)):
            disable_world_spawn_budget(True)
            try:
                import unrealsdk  # noqa: PLC0415
                from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

                world = None
                try:
                    world = unrealsdk.get_engine().GameViewport.World
                except Exception:
                    world = None
                if world is not None:
                    ssp._overdrive_spawn_manager_if_needed(world)
            except Exception:
                pass
        remapped = resolve_concrete_actor_code(code)
        if remapped.lower() != code.lower():
            code = remapped
            line_or_code = f"oak_spawnai {code}"
        exclude = player_pawn_keys()
        # Full world snapshot hitch hosts — async detect uses family scans + SSP _SPAWNED.
        skip_snapshot = bossish or code.lower().startswith("char_")
        before = set() if skip_snapshot else snapshot_character_keys(exclude_keys=exclude)
        near = self._spawn_reference_loc()
        radius = max(float(self.ui.scan_radius), 4500.0 if bossish else float(self.ui.scan_radius))
        dist = max(float(self.ui.spawn_distance), 900.0 if bossish else float(self.ui.spawn_distance))

        # Bosses / Char_* — never trust console-only forward; use Oak Spawner direct.
        # Fire on PlayerTick, then detect/aggro on later frames. Avoid a
        # synchronous OakSpawner poll on the game thread.
        if bossish or code.lower().startswith("char_"):
            spawn_count = 1 if bossish else max(1, int(count))
            with self._with_spawn_anchor():
                ok, msg = spawn_actor_def(
                    code,
                    count=spawn_count,
                    distance=dist,
                    spacing=effective_spawn_spacing(float(self.ui.spawn_spacing), count, actor_code=code),
                    allow_summon_fallback=bool(self.ui.summon_fallback) and not bossish,
                    fast_path=True,
                    async_fire=True,
                )
            # Detect + aggro on later frames. Do NOT hold the UI spawn timer —
            # that stuck forever when async detect could not clear while the menu
            # was open. Spawn already happened (or soft-fired); settle in background.
            fired = bool(ok) or "stream" in str(msg).lower()
            try:
                target_ui.spawn_pending = False  # type: ignore[attr-defined]
                target_ui.spawn_pending_since = 0.0  # type: ignore[attr-defined]
            except Exception:
                pass
            if not fired:
                target_ui.status_text = str(msg)
                target_ui.error_text = str(msg)
                return False, msg
            return begin_async_detect(
                self,
                code,
                near=near,
                before=before,
                radius=radius,
                bossish=bossish,
                label=label,
                ui=target_ui,
                fired_msg=msg if ok else f"Oak Spawner fired: {msg}",
                distance=dist,
                spacing=effective_spawn_spacing(float(self.ui.spawn_spacing), count, actor_code=code),
                count=count,
                oak_already_fired=bool(ok) or bossish,
                hold_ui_pending=False,
            )

        ok, msg = fire_console_spawn(line_or_code)
        if not ok:
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
            return ok, msg

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
        )

    def _queue_async_spawn_ui(
        self,
        line_or_code: str,
        *,
        bossish: bool,
        label: str,
        count: int = 1,
        ui: Any | None = None,
        cache_code: str = "",
    ) -> tuple[bool, str]:
        from .spawn_safe import queue_spawn_action  # noqa: PLC0415

        target_ui = ui if ui is not None else self.ui

        def _fire() -> tuple[bool, str]:
            if cache_code:
                cached, cache_msg = try_auto_cache_actor_def(cache_code)
                if cached:
                    target_ui.status_text = cache_msg
                elif cache_msg:
                    target_ui.error_text = cache_msg
            return self._fire_async_spawn(line_or_code, bossish=bossish, label=label, count=count, ui=target_ui)

        return queue_spawn_action(label, _fire, target_ui)

    def _queue_async_spawn_batch(
        self,
        line_or_code: str,
        *,
        bossish: bool,
        label: str,
        count: int = 1,
        ui: Any | None = None,
        cache_code: str = "",
    ) -> tuple[bool, str]:
        """Spread multi-spawns across PlayerTick frames (lobby-safe)."""
        from .spawn_safe import queue_spawn_actions  # noqa: PLC0415

        target_ui = ui if ui is not None else self.ui
        n = max(1, int(count))
        if n == 1:
            return self._queue_async_spawn_ui(
                line_or_code,
                bossish=bossish,
                label=label,
                count=1,
                ui=target_ui,
                cache_code=cache_code,
            )

        def _make_fire(index: int) -> Callable[[], tuple[bool, str]]:
            def _fire() -> tuple[bool, str]:
                if index == 0 and cache_code:
                    cached, cache_msg = try_auto_cache_actor_def(cache_code)
                    if cached:
                        target_ui.status_text = cache_msg
                    elif cache_msg:
                        target_ui.error_text = cache_msg
                item_label = f"{label} ({index + 1}/{n})"
                return self._fire_async_spawn(
                    line_or_code,
                    bossish=bossish,
                    label=item_label,
                    count=1,
                    ui=target_ui,
                )

            return _fire

        return queue_spawn_actions(label, [_make_fire(i) for i in range(n)], target_ui)

    def spawn_mob(
        self,
        code: str,
        *,
        count: int | None = None,
        defer: bool = True,
        lightweight: bool | None = None,
    ) -> tuple[bool, str]:
        code = (code or "").strip()
        if not code:
            return False, "empty actor code"
        remapped = resolve_concrete_actor_code(code)
        if remapped.lower() != code.lower():
            code = remapped
        if is_abstract_actor_code(code):
            msg = abstract_actor_code_message(code)
            self.ui.status_text = msg
            self.ui.error_text = msg
            return False, msg
        if bool(getattr(self.ui, "unlimited_world_spawns", True)):
            # OakWorldSettings is replaced on map travel; reapply immediately
            # before every request so valid mobs do not wait for an AI slot.
            disable_world_spawn_budget(True)
            try:
                import unrealsdk  # noqa: PLC0415
                from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

                world = None
                try:
                    world = unrealsdk.get_engine().GameViewport.World
                except Exception:
                    world = None
                if world is not None:
                    ssp._overdrive_spawn_manager_if_needed(world)
            except Exception:
                pass
        # Prefer combat-ready …_TRUE defs so intro-gated base bosses don't just stare.
        if is_boss_actor_code(code):
            code = prefer_combat_boss_code(code)
        bossish = is_boss_actor_code(code)
        cache_code = code if bossish and str(code or "").strip().lower() in DLC_OAK_CACHE_ACTORS else ""
        lite = bool(lightweight) if lightweight is not None else defer
        cap = int(getattr(self.ui, "max_deploy_count", MAX_DEPLOY_COUNT))
        n = clamp_deploy_count(count if count is not None else self.ui.squ1ggs_deploy_count, max_cap=cap)
        inline_n = n

        # Bosses: same deferred coop-safe path as trash (no world pause, short polls).
        # Old path used lightweight=False + hard pause → 7–10s hitch / lobby drops.
        if defer and bossish:
            label = f"Spawn boss {code}"
            return self._queue_async_spawn_batch(
                f"oak_spawnai {code}",
                bossish=True,
                label=label,
                count=n,
                cache_code=cache_code,
            )

        # Trash mobs: async console + detect (menu stays responsive).
        if defer and lite:
            label = f"Spawn boss {code}" if bossish else f"Spawn {code}"
            line = f"oak_spawnai {code}"
            if inline_n > 1:
                return self._queue_async_spawn_batch(line, bossish=bossish, label=label, count=inline_n)
            return self._queue_async_spawn_ui(line, bossish=bossish, label=label, count=1)

        def _do_spawn() -> tuple[bool, str]:
            return self._spawn_mob_sync(code, count=count, lightweight=lite)

        if defer:
            from .spawn_safe import queue_spawn_action  # noqa: PLC0415

            label = f"Spawn boss {code}" if bossish else f"Spawn {code}"
            return queue_spawn_action(label, _do_spawn, self.ui)
        return self._spawn_mob_sync(code, count=count, lightweight=lite)

    def _spawn_mob_sync(
        self,
        code: str,
        *,
        count: int | None = None,
        lightweight: bool = False,
    ) -> tuple[bool, str]:
        code = (code or "").strip()
        if not code:
            return False, "empty actor code"
        if is_boss_actor_code(code):
            code = prefer_combat_boss_code(code)
        bossish = is_boss_actor_code(code)
        cap = int(getattr(self.ui, "max_deploy_count", MAX_DEPLOY_COUNT))
        n = clamp_deploy_count(count if count is not None else 1, max_cap=cap)
        if lightweight:
            n = 1
        mode = str(self.ui.aggro_mode or "attack_me")
        party_idx = int(self.ui.party_index)
        radius = float(self.ui.scan_radius)

        exclude = player_pawn_keys()
        before = set() if lightweight else snapshot_character_keys(exclude_keys=exclude)
        near = self._spawn_reference_loc()
        spawned_keys: list[str] = []
        last_msg = ""

        dist = float(self.ui.spawn_distance)
        if bossish:
            dist = max(dist, 900.0)
        live_bosses: list[Any] = []
        ok = False
        with self._with_spawn_anchor():
            if bossish and str(code).strip().lower() == "char_tubaboss":
                try:
                    from .spawn_core import find_characters_matching_code_near  # noqa: PLC0415

                    live_bosses = find_characters_matching_code_near(
                        near,
                        code,
                        radius=max(dist, 8000.0),
                        exclude_keys=exclude,
                    )
                except Exception:
                    live_bosses = []
            if live_bosses:
                ok = True
                last_msg = (
                    f"Using live {code} already in arena ({len(live_bosses)} found) — "
                    "mission adds may need a takedown run before combat starts."
                )
            else:
                ok, msg = spawn_actor_def(
                    code,
                    count=n,
                    distance=dist,
                    spacing=effective_spawn_spacing(float(self.ui.spawn_spacing), n, actor_code=code),
                    allow_summon_fallback=bool(self.ui.summon_fallback) and not bossish,
                    max_count=cap,
                    fast_path=bool(lightweight),
                )
                last_msg = msg

        if not ok:
            detect_radius = max(radius, 4500.0 if bossish else radius)
            late = find_new_characters_near(
                before if before else snapshot_character_keys(exclude_keys=exclude),
                near,
                radius=detect_radius,
                exclude_keys=exclude,
                expected_code=code,
            )
            if late:
                ok = True
                last_msg = f"spawn OK: {code}"
                if not before:
                    before = snapshot_character_keys(exclude_keys=exclude)

        if lightweight or bossish:
            spawned_keys: list[str] = []
            if ok:
                scan_before = before if before else snapshot_character_keys(exclude_keys=exclude)
                new_actors = find_new_characters_near(
                    scan_before,
                    near,
                    radius=max(radius, 6000.0 if bossish else radius),
                    exclude_keys=exclude,
                    expected_code=code,
                )
                if live_bosses and not new_actors:
                    new_actors = live_bosses[:n]
                # Bosses sometimes miss the near-scan — fall back to Squ1ggs last spawn.
                if not new_actors and bossish:
                    try:
                        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

                        spawned = getattr(ssp, "_SPAWNED", None) or []
                        if spawned:
                            last = spawned[-1]
                            actor = getattr(last, "actor", None)
                            if actor is not None:
                                new_actors = [actor]
                    except Exception:
                        pass
                for actor in new_actors[:n]:
                    key = str(actor)
                    self.tracker.add_actor(actor, code=code)
                    spawned_keys.append(key)
            aggro_detail = ""
            if mode not in ("passive", "none", "off"):
                if spawned_keys:
                    aggro_detail = self._apply_aggro_to_tracked(spawned_keys, mode, party_idx)
                elif ok and bossish:
                    # Tracked later via pulses — still schedule wake attempts.
                    aggro_detail = "aggro deferred (actor not tracked yet)"
                if bossish or (spawned_keys and mode in ("free_for_all", "ffa", "each_other", "nearest_other", "nearest")):
                    self._schedule_aggro_pulses(pulses=6 if bossish else 2)
            if aggro_detail:
                last_msg = f"{last_msg}; {aggro_detail}"
            if bossish and not spawned_keys:
                prereq = oak_cache_prerequisite_message(code)
                if prereq:
                    last_msg = prereq
                    self.ui.status_text = last_msg
                    self.ui.error_text = prereq
                    return False, last_msg
            self.ui.status_text = last_msg
            self.ui.error_text = "" if ok else last_msg
            return ok or bool(spawned_keys), last_msg

        spawned_keys: list[str] = []
        if ok:
            new_actors = find_new_characters_near(
                before,
                near,
                radius=radius,
                exclude_keys=exclude,
                expected_code=code,
            )
            seen: set[str] = set()
            for actor in new_actors:
                key = str(actor)
                if key in seen:
                    continue
                seen.add(key)
                self.tracker.add_actor(actor, code=code)
                spawned_keys.append(key)
                before.add(key)
                if len(spawned_keys) >= n:
                    break

        live = self.tracker.live_mobs_with_codes()
        target, tlabel = resolve_aggro_target(mode, party_index=party_idx)
        actors, code_map = self._resolve_aggro_mob_set(spawned_keys, mode)
        if not actors and live:
            actors, code_map = [live[-1][0]], {live[-1][0]: live[-1][1]}
        ok_n, fail_n, aggro_msg = apply_aggro_mode(
            actors,
            mode=mode,
            primary_target=target,
            damage_wake=bool(self.ui.damage_wake),
            mob_codes=code_map or self.tracker.mob_code_map(),
        )
        dead_cleared = self.tracker.clear_dead()
        detail = (
            f"spawn: {last_msg}; tracked={len(spawned_keys)}/{n} "
            f"aggro {ok_n}/{ok_n + fail_n} ({tlabel}) — {aggro_msg}"
        )
        if dead_cleared:
            detail += f"; pruned {dead_cleared} dead"
        success = ok or bool(spawned_keys)
        if not success:
            late = find_new_characters_near(
                before,
                near,
                radius=max(radius, 4500.0 if bossish else radius),
                exclude_keys=exclude,
                expected_code=code,
            )
            if late:
                success = True
                last_msg = f"spawn detected: {code} (async settle)"
                self.tracker.add_actor(late[0], code=code)
                spawned_keys.append(str(late[0]))
        self.ui.status_text = detail
        self.ui.error_text = "" if success else last_msg
        return success, detail

    def _resolve_aggro_mob_set(
        self,
        spawned_keys: list[str],
        mode: str,
    ) -> tuple[list[Any], dict[Any, str]]:
        """FFA / nearest-other need the full tracked pool, not just the latest spawn."""
        mode = (mode or "attack_me").strip().lower()
        live = self.tracker.live_mobs_with_codes()
        if mode in ("free_for_all", "ffa", "each_other", "nearest_other", "nearest"):
            return [a for a, _c in live], {a: c for a, c in live}
        key_set = set(spawned_keys)
        subset = [(a, c) for a, c in live if str(a) in key_set]
        if not subset and live:
            subset = [live[-1]]
        return [a for a, _c in subset], {a: c for a, c in subset}

    def _apply_aggro_to_tracked(self, spawned_keys: list[str], mode: str, party_idx: int) -> str:
        """Apply aggro to freshly spawned tracked actors (with actor codes for boss profiles)."""
        mode = (mode or "attack_me").strip().lower()
        if mode in ("passive", "none", "off"):
            return "passive — no aggro"
        actors, code_map = self._resolve_aggro_mob_set(spawned_keys, mode)
        if not actors:
            return "no live spawned actors for aggro"
        target, tlabel = resolve_aggro_target(mode, party_index=party_idx)
        damage_wake = bool(self.ui.damage_wake) or any(
            is_boss_actor_code(c) or "boss" in str(c).lower() for c in code_map.values()
        )
        ok_n, fail_n, aggro_msg = apply_aggro_mode(
            actors,
            mode=mode,
            primary_target=target,
            damage_wake=damage_wake,
            mob_codes=code_map,
        )
        return f"aggro {ok_n}/{ok_n + fail_n} ({tlabel}) — {aggro_msg}"

    def _schedule_aggro_pulses(self, *, pulses: int = 3, gap_frames: int = 8) -> None:
        """Raid bosses often need combat wake on later frames — re-aggro without blocking UI."""
        try:
            from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415

            n = max(1, min(8, int(pulses)))
            gap = max(0, min(20, int(gap_frames)))
            for i in range(n):
                # Spacer frames so AI can leave intro/idle before the next wake ping.
                for g in range(gap if i > 0 else 0):

                    def _wait(_g: int = g, _i: int = i) -> tuple[bool, str]:
                        return True, f"aggro settle {_i + 1}.{_g + 1}"

                    deferred.queue_action(f"Aggro settle {i + 1}/{n}", _wait)

                def _pulse(_i: int = i) -> tuple[bool, str]:
                    ok, msg = self._reaggro_tracked_sync()
                    return ok, f"pulse {_i + 1}: {msg}"

                deferred.queue_action(f"Aggro pulse {i + 1}/{n}", _pulse)
        except Exception:
            pass

    def _apply_aggro_after_async_spawn(self, code: str) -> None:
        mode = str(self.ui.aggro_mode or "attack_me")
        if mode in ("passive", "none", "off"):
            self.ui.status_text = f"Spawn OK: {code} (passive)"
            return
        live = self.tracker.live_mobs_with_codes()
        if not live:
            self.ui.status_text = f"Spawn OK: {code}"
            return
        keys = [str(a) for a, c in live if (not code) or c == code or code in c]
        if not keys:
            keys = [str(live[-1][0])]
        detail = self._apply_aggro_to_tracked(keys, mode, int(self.ui.party_index))
        self.ui.status_text = f"Spawn OK: {code} — {detail}"
        boss = is_boss_actor_code(code) or "boss" in str(code).lower()
        if boss or mode in ("free_for_all", "ffa", "each_other", "nearest_other", "nearest"):
            # Bosses: more spaced pulses — look-at alone is not combat.
            self._schedule_aggro_pulses(pulses=6 if boss else 2, gap_frames=10 if boss else 3)

    def reaggro_tracked(self, *, defer: bool = True) -> tuple[bool, str]:
        def _do() -> tuple[bool, str]:
            return self._reaggro_tracked_sync()

        if defer:
            from .spawn_safe import queue_spawn_action

            return queue_spawn_action("Re-aggro tracked", _do, self.ui)
        return self._reaggro_tracked_sync()

    def _reaggro_tracked_sync(self) -> tuple[bool, str]:
        self.tracker.clear_dead()
        # Late-bind bosses that spawned but weren't tracked on the first frame.
        # Only accept Oak/Gbx characters — ssp._SPAWNED also holds barrel logos / props.
        try:
            from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
            from .spawn_core import is_aggroable_character  # noqa: PLC0415

            for item in list(getattr(ssp, "_SPAWNED", None) or [])[-6:]:
                actor = getattr(item, "actor", None)
                code = str(getattr(item, "label", "") or "")
                if actor is not None and is_aggroable_character(actor):
                    # Prefer Char_* labels; skip barrel_logo / generic props.
                    if code.lower() in ("barrel_logo",) or "barrel" in code.lower():
                        continue
                    self.tracker.add_actor(actor, code=code)
        except Exception:
            pass
        live = self.tracker.live_mobs_with_codes()
        live_actors = [a for a, _c in live]
        if not live_actors:
            return False, "no live tracked mobs"
        mode = str(self.ui.aggro_mode or "attack_me")
        target, tlabel = resolve_aggro_target(mode, party_index=int(self.ui.party_index))
        # Bosses always get damage wake — intro gates often ignore focus RPCs alone.
        damage_wake = bool(self.ui.damage_wake) or any(
            is_boss_actor_code(c) or "boss" in c.lower() for _a, c in live
        )
        ok_n, fail_n, msg = apply_aggro_mode(
            live_actors,
            mode=mode,
            primary_target=target,
            damage_wake=damage_wake,
            mob_codes=self.tracker.mob_code_map(),
        )
        detail = f"re-aggro {ok_n}/{ok_n + fail_n} on {tlabel}: {msg}"
        self.ui.status_text = detail
        return ok_n > 0, detail

    def clear_tracked(self) -> tuple[int, int]:
        destroyed, failed = self.tracker.destroy_all()
        self.ui.status_text = f"Cleared tracked mobs: destroyed={destroyed} failed={failed}"
        return destroyed, failed

    def run_encounter_line(
        self,
        line: str,
        *,
        defer: bool = True,
        ui: Any | None = None,
        activate: bool = True,
    ) -> tuple[bool, str]:
        line = (line or "").strip()
        if not line:
            return False, "empty encounter line"
        target_ui = ui if ui is not None else self.ui
        if bool(getattr(target_ui, "unlimited_world_spawns", True)):
            disable_world_spawn_budget(True)
            try:
                import unrealsdk  # noqa: PLC0415
                from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

                world = None
                try:
                    world = unrealsdk.get_engine().GameViewport.World
                except Exception:
                    world = None
                if world is not None:
                    ssp._overdrive_spawn_manager_if_needed(world)
            except Exception:
                pass

        # IO_* need real Oak Spawner + script activation (async Char_* detect misses most props).
        token = ""
        low = line.lower()
        for prefix in (
            "oak_dual ",
            "asd_dual ",  # legacy catalog cmd → same oak dual path
            "oak_spawnai ",
            "oak_spawnai ",
            "oak_spawn ",
            "oak_spawn ",
        ):
            if low.startswith(prefix):
                parts = line.split(None, 1)
                token = parts[1].strip() if len(parts) > 1 else ""
                break
        if not token and not low.startswith("oak_"):
            token = line

        from .io_activate import (  # noqa: PLC0415
            activate_spawned_io,
            canonical_io_token,
            is_io_code,
            is_oak_dual_vending,
            needs_dual_world_spawn,
            oak_spawn_vending_world,
            oak_prepare_vending_packages,
            oak_spawnai_vending,
            oak_wake_vending,
            safe_world_io_spawn,
            short_io_token,
        )

        # Black Market / Maurice: embedded oak_spawnai → settle → PersistentLevel oak_spawn.
        if is_oak_dual_vending(token) or low.startswith(("oak_dual ", "asd_dual ")):
            short = canonical_io_token(token) or short_io_token(token) or token

            def _do_oak_prepare() -> tuple[bool, str]:
                try:
                    return oak_prepare_vending_packages(short)
                except Exception as ex:  # noqa: BLE001
                    return False, f"package load failed safely: {type(ex).__name__}: {ex}"

            def _do_oak_ai() -> tuple[bool, str]:
                try:
                    return oak_spawnai_vending(
                        short,
                        distance=float(self.ui.spawn_distance),
                        spacing=float(self.ui.spawn_spacing),
                    )
                except Exception as ex:  # noqa: BLE001
                    return False, f"oak_spawnai failed safely: {type(ex).__name__}: {ex}"

            def _do_oak_world() -> tuple[bool, str]:
                try:
                    return oak_spawn_vending_world(
                        short,
                        distance=float(self.ui.spawn_distance),
                        spacing=float(self.ui.spawn_spacing),
                        activate=activate,
                    )
                except Exception as ex:  # noqa: BLE001
                    return False, f"oak_spawn failed safely: {type(ex).__name__}: {ex}"

            def _do_oak_wake() -> tuple[bool, str]:
                try:
                    return oak_wake_vending(short)
                except Exception as ex:  # noqa: BLE001
                    return False, f"wake failed safely: {type(ex).__name__}: {ex}"

            if defer:
                from .spawn_safe import queue_spawn_actions  # noqa: PLC0415

                def _wait() -> tuple[bool, str]:
                    return True, "Setting up machine…"

                # Dump path: load packages → oak_spawnai ×2 → world ×3 → wake ×3.
                label = f"Oak dual {short[:40]}"
                ok, msg = queue_spawn_actions(
                    label,
                    [
                        _do_oak_prepare,
                        _wait,
                        _wait,
                        _do_oak_ai,
                        _wait,
                        _wait,
                        _do_oak_ai,
                        _wait,
                        _wait,
                        _do_oak_world,
                        _wait,
                        _do_oak_world,
                        _wait,
                        _do_oak_world,
                        _wait,
                        _wait,
                        _do_oak_wake,
                        _wait,
                        _do_oak_wake,
                        _wait,
                        _do_oak_wake,
                    ],
                    target_ui,
                )
                if ok:
                    friendly = "Queued black market: load → spawnai → world → wake."
                    target_ui.status_text = friendly
                    target_ui.error_text = ""
                    return True, friendly
                return ok, msg
            ok1, msg1 = _do_oak_prepare()
            ok2, msg2 = _do_oak_ai()
            ok3, msg3 = _do_oak_world()
            ok4, msg4 = _do_oak_wake()
            msg = f"{msg1}; {msg2}; {msg3}; {msg4}"
            target_ui.status_text = msg
            target_ui.error_text = "" if (ok1 or ok2 or ok3 or ok4) else msg
            return bool(ok1 or ok2 or ok3 or ok4), msg

        if is_io_code(token):
            short = canonical_io_token(token) or short_io_token(token) or token
            dual = needs_dual_world_spawn(short)

            def _do_ai_only() -> tuple[bool, str]:
                try:
                    # Always async-fire like mob spawner. Dual world pass waits on
                    # later ticks via find_object — never block PlayerTick with polls.
                    ok, msg = spawn_actor_def(
                        short,
                        count=1,
                        distance=float(self.ui.spawn_distance),
                        spacing=float(self.ui.spawn_spacing),
                        allow_summon_fallback=False,
                        fast_path=True,
                        async_fire=True,
                    )
                    fired = bool(ok) or ("stream" in msg.lower()) or msg.lower().startswith("oak_")
                    return True if fired else bool(ok), f"oak_spawnai {short}: {msg}"
                except Exception as ex:  # noqa: BLE001
                    return False, f"oak_spawnai failed safely: {type(ex).__name__}: {ex}"

            def _do_world_followup() -> tuple[bool, str]:
                try:
                    ok, msg = safe_world_io_spawn(
                        short,
                        distance=float(self.ui.spawn_distance),
                        spacing=float(self.ui.spawn_spacing),
                    )
                    act_msg = ""
                    if activate:
                        try:
                            _a_ok, a_msg = activate_spawned_io(short)
                            act_msg = f"; {a_msg}"
                        except Exception as act_ex:  # noqa: BLE001
                            act_msg = f"; activate skipped (safe): {type(act_ex).__name__}: {act_ex}"
                    # Soft-success: first AI spawn may already be enough; never raise.
                    return True, f"world follow-up {short}: {msg}{act_msg}"
                except Exception as ex:  # noqa: BLE001
                    return False, f"world follow-up failed safely: {type(ex).__name__}: {ex}"

            def _do_io() -> tuple[bool, str]:
                # World PersistentLevel paths must go through oak_spawn (template duplicate),
                # not OakSpawner actor-def spawn — that's what unlocks PlayerBank etc.
                try:
                    use_world = (
                        "persistentlevel." in token.lower()
                        or token.lower().startswith("/game/")
                        or low.startswith("oak_spawn ")
                    )
                    if dual and not use_world:
                        # Dual sequence is queued separately below.
                        return _do_ai_only()
                    if use_world:
                        ok, msg = safe_world_io_spawn(
                            short,
                            distance=float(self.ui.spawn_distance),
                            spacing=float(self.ui.spawn_spacing),
                        )
                    else:
                        # One Oak Spawner fire only. spawn_actor_def often returns False when the prop
                        # has not appeared in the 0.05–0.28s poll yet; the old run_oak_line
                        # fallback ResetSpawner'd again and duplicated IO_AscensionBeam etc.
                        ok, msg = spawn_actor_def(
                            short,
                            count=1,
                            distance=float(self.ui.spawn_distance),
                            spacing=float(self.ui.spawn_spacing),
                            allow_summon_fallback=False,
                            fast_path=True,
                            async_fire=True,
                        )
                    fired = bool(ok) or ("stream" in str(msg).lower()) or str(msg).lower().startswith("oak_")
                    if fired and activate and not dual:
                        a_ok, a_msg = activate_spawned_io(short)
                        msg = f"{msg}; {a_msg}" if a_ok else f"{msg}; activate: {a_msg}"
                        return True, msg
                    if fired:
                        return True, msg
                    return ok, msg
                except Exception as ex:  # noqa: BLE001
                    return False, f"IO spawn failed safely: {type(ex).__name__}: {ex}"

            if defer and dual:
                from .spawn_safe import queue_spawn_actions  # noqa: PLC0415

                def _wait() -> tuple[bool, str]:
                    return True, "Setting up machine…"

                # One user click → async oak_spawnai, settle, then world pass (+ retry).
                label = f"Spawn {short[:48]}"
                ok, msg = queue_spawn_actions(
                    label,
                    [
                        _do_ai_only,
                        _wait,
                        _wait,
                        _wait,
                        _wait,
                        _do_world_followup,
                        _wait,
                        _do_world_followup,
                    ],
                    target_ui,
                )
                if ok:
                    friendly = (
                        f"Queued {short}: setup runs automatically "
                        "(place → settle → unlock). Stay in-world for a moment."
                    )
                    target_ui.status_text = friendly
                    target_ui.error_text = ""
                    return True, friendly
                return ok, msg

            if defer:
                from .spawn_safe import queue_spawn_action  # noqa: PLC0415

                return queue_spawn_action(f"IO spawn {short[:48]}", _do_io, target_ui)
            ok, msg = _do_io()
            target_ui.status_text = msg
            target_ui.error_text = "" if ok else msg
            return ok, msg

        try:
            from .spawn_async import is_async_spawn_line  # noqa: PLC0415
        except Exception:
            is_async_spawn_line = lambda _l: False  # type: ignore[assignment,misc]

        if defer and is_async_spawn_line(line):
            return self._queue_async_spawn_ui(line, bossish=False, label="IO spawn", ui=target_ui)

        def _do() -> tuple[bool, str]:
            try:
                return run_oak_line(line)
            except Exception as ex:  # noqa: BLE001
                return False, f"spawn failed safely: {type(ex).__name__}: {ex}"

        if defer:
            from .spawn_safe import queue_spawn_action  # noqa: PLC0415

            return queue_spawn_action("Mob IO spawn", _do, target_ui)
        ok, msg = _do()
        target_ui.status_text = msg
        target_ui.error_text = "" if ok else msg
        return ok, msg

    def activate_last_io(self, *, ui: Any | None = None) -> tuple[bool, str]:
        from .io_activate import activate_spawned_io  # noqa: PLC0415

        target_ui = ui if ui is not None else self.ui
        ok, msg = activate_spawned_io()
        target_ui.status_text = msg
        target_ui.error_text = "" if ok else msg
        return ok, msg

    def draw_ui(self) -> None:
        """Tab body for BL4 Mod Menu — do not nest ``imgui.begin()``."""
        if self._drawing_ui:
            return
        self._drawing_ui = True
        try:
            if _mob_ui_needs_reset(self.ui):
                self.ui = MobUi()
            try:
                from .spawn_safe import poll_spawn_status  # noqa: PLC0415

                poll_spawn_status(self.ui, controller=self)
            except Exception:
                pass
            bg = _ensure_blimgui()
            if bg is None:
                return
            imgui = bg.imgui
            try:
                self._draw_panel(imgui)
            except Exception as exc:  # noqa: BLE001
                _log.error("%s UI error: %s", _LOG, exc)
                try:
                    imgui.text_colored((1.0, 0.45, 0.45, 1.0), f"BMS tab error: {exc}")
                except Exception:
                    pass
        finally:
            self._drawing_ui = False

    def _draw_panel(self, imgui: Any) -> None:
        oak_ok, oak_detail = oak_available()
        if oak_ok:
            imgui.text_colored((0.45, 0.95, 0.55, 1.0), f"BMS backend (BL4 Oak Spawner): {oak_detail}")
        else:
            imgui.text_colored(
                (1.0, 0.45, 0.45, 1.0),
                f"BL4 Oak Spawner missing — enable it + rlm BL4 Oak Spawner. ({oak_detail})",
            )

        imgui.text_wrapped(
            "**Borderlands Mob Spawner (BMS)** — spawn **Char_*** via Squ1ggs ``oak_spawnai`` "
            "(OakSpawner). GBX Summon is optional fallback only. "
            "Use the desktop Mob and IO Spawner tab. "
            "Use **Re-aggro tracked** after spawn if needed.",
        )
        imgui.spacing()

        mode_labels = [label for _id, label in AGGRO_MODES]
        mode_ids = [mid for mid, _label in AGGRO_MODES]
        cur_idx = mode_ids.index(self.ui.aggro_mode) if self.ui.aggro_mode in mode_ids else 0
        if _collapsing_show(imgui.begin_combo("Aggro mode##mob_aggro", mode_labels[cur_idx])):
            for i, label in enumerate(mode_labels):
                clicked, _sel = imgui.selectable(label, i == cur_idx)
                if clicked:
                    self.ui.aggro_mode = mode_ids[i]
            imgui.end_combo()

        anchor_labels = ("From me", "From selected player", "Near nearest NPC")
        anchor_ids = ("local", "party", "npc_nearest")
        a_cur = anchor_ids.index(self.ui.spawn_anchor) if self.ui.spawn_anchor in anchor_ids else 0
        if _collapsing_show(imgui.begin_combo("Spawn location##mob_spawn_anchor", anchor_labels[a_cur])):
            for i, label in enumerate(anchor_labels):
                clicked, _sel = imgui.selectable(label, i == a_cur)
                if clicked:
                    self.ui.spawn_anchor = anchor_ids[i]
                    # Spawning on a guest usually means they should also get aggro focus.
                    if anchor_ids[i] == "party" and self.ui.aggro_mode == "attack_me":
                        self.ui.aggro_mode = "attack_party"
                    if anchor_ids[i] == "local":
                        try:
                            from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

                            ssp.clear_spawn_player_controller_override()
                        except Exception:
                            pass
            imgui.end_combo()

        if self.ui.spawn_anchor == "npc_nearest":
            npc = self._resolve_spawn_anchor_actor()
            if npc is None:
                imgui.text_colored(
                    (1.0, 0.70, 0.35, 1.0),
                    "No nearby NPC found; spawn will safely fall back to your position.",
                )
            else:
                try:
                    from .spawn_anchor import npc_label  # noqa: PLC0415

                    imgui.text_colored((0.55, 0.85, 1.0, 1.0), f"NPC anchor: {npc_label(npc)}")
                except Exception:
                    pass

        if self.ui.aggro_mode == "attack_party" or self.ui.spawn_anchor == "party":
            _cp, self.ui.party_index = imgui.input_int(
                "Party index (PlayerArray / Echo4 #)##mob_party",
                int(self.ui.party_index),
            )
            self.ui.party_index = max(0, min(31, int(self.ui.party_index)))
            if self.ui.spawn_anchor == "party":
                imgui.text_colored(
                    (0.55, 0.85, 1.0, 1.0),
                    "Spawns appear in front of that party member (host still runs the spawn).",
                )

        _cr, self.ui.scan_radius = imgui.input_float("Post-spawn scan radius##mob_rad", float(self.ui.scan_radius))
        self.ui.scan_radius = max(500.0, min(20000.0, float(self.ui.scan_radius)))

        _cd, self.ui.spawn_distance = imgui.input_float("BMS spawn distance##mob_dist", float(self.ui.spawn_distance))
        self.ui.spawn_distance = max(50.0, min(5000.0, float(self.ui.spawn_distance)))
        imgui.same_line()
        _cs, self.ui.spawn_spacing = imgui.input_float("BMS spacing##mob_space", float(self.ui.spawn_spacing))
        self.ui.spawn_spacing = max(25.0, min(2000.0, float(self.ui.spawn_spacing)))
        imgui.same_line()
        _cm, self.ui.max_deploy_count = imgui.input_int(
            f"Max spawn count##mob_maxcnt",
            int(getattr(self.ui, "max_deploy_count", MAX_DEPLOY_COUNT)),
        )
        self.ui.max_deploy_count = max(1, min(999, int(self.ui.max_deploy_count)))
        if self.ui.squ1ggs_deploy_count > self.ui.max_deploy_count:
            self.ui.squ1ggs_deploy_count = self.ui.max_deploy_count

        _ub, self.ui.unlimited_world_spawns = imgui.checkbox(
            "Disable world AI spawn budget##mob_unlimited_budget",
            bool(getattr(self.ui, "unlimited_world_spawns", True)),
        )
        if _ub:
            _changed, budget_msg = disable_world_spawn_budget(self.ui.unlimited_world_spawns)
            self.ui.status_text = budget_msg
            self.ui.error_text = ""
        imgui.same_line()
        imgui.text_disabled("Lets new mobs spawn without waiting for an existing mob to die.")

        _fb, self.ui.summon_fallback = imgui.checkbox(
            "Summon fallback if Oak Spawner fails##mob_summon_fb",
            bool(self.ui.summon_fallback),
        )
        _dw, self.ui.damage_wake = imgui.checkbox(
            "Damage wake (bosses + FFA)##mob_dmg_wake",
            bool(self.ui.damage_wake),
        )
        imgui.text_disabled(
            "FFA: distinct army/clan slots + cross-damage. Char_TubaBoss = Tuba DLC water boss — "
            "spawn near water if idle; try Attack me + damage wake, or shoot once. "
            "Live Editor dump on spawned TubaBoss helps tune script states.",
        )

        imgui.text_disabled(f"Tracked mobs: {len(self.tracker.mobs)}")

        if imgui.button("Re-aggro tracked##mob_reaggro"):
            self.reaggro_tracked(defer=True)
        imgui.same_line()
        if imgui.button("Clear tracked##mob_clear"):
            self.clear_tracked()

        err = str(self.ui.error_text or "").strip()
        st = str(self.ui.status_text or "").strip()
        if bool(getattr(self.ui, "spawn_pending", False)):
            since = float(getattr(self.ui, "spawn_pending_since", 0.0) or 0.0)
            elapsed = max(0.0, time.monotonic() - since) if since > 0.0 else 0.0
            imgui.text_colored(
                (1.0, 0.85, 0.25, 1.0),
                f"Spawn timer: {elapsed:.1f}s — detecting (world stays running)",
            )
        if err:
            imgui.text_colored((1.0, 0.35, 0.35, 1.0), err[:500])
        elif st:
            imgui.text_wrapped(st[:500])

        imgui.spacing()
        if _collapsing_show(imgui.collapsing_header("★ Favorites", 0)):
            try:
                from .mob_favorites import draw_favorites_section  # noqa: PLC0415

                draw_favorites_section(
                    imgui,
                    self.ui,
                    spawn_mob=self.spawn_mob,
                    run_encounter=self.run_encounter_line,
                    id_prefix="mob_fav",
                )
            except Exception as ex:  # noqa: BLE001
                imgui.text_disabled(f"Favorites unavailable: {ex}")

        if _collapsing_show(
            imgui.collapsing_header("Mixed Mob Spawner", 0),
        ):
            try:
                from Squ1ggsBoostingToolsHookedWidget import world_spawn as mix_spawn  # noqa: PLC0415

                rows = mix_spawn.load_catalog()
                if not rows:
                    imgui.text_disabled("No Mix_* definitions were found.")
                else:
                    labels = [f"{row['mix_id']} [{row['category']}]" for row in rows]
                    selected = max(0, min(int(getattr(self, "_mix_selected", 0)), len(rows) - 1))
                    if _collapsing_show(imgui.begin_combo("Spawn group##bms_mix", labels[selected])):
                        for index, label in enumerate(labels):
                            clicked, _chosen = imgui.selectable(label, index == selected)
                            if clicked:
                                selected = index
                        imgui.end_combo()
                    self._mix_selected = selected
                    imgui.text_disabled(
                        "Uses the BMS count, aggro mode, party target, distance and spawn-budget settings above.",
                    )
                    if imgui.button("Spawn selected mix##bms_mix_spawn"):
                        ok, msg = mix_spawn.spawn_mix_def(
                            rows[selected]["mix_id"],
                            count=int(self.ui.squ1ggs_deploy_count),
                            aggro_mode=str(self.ui.aggro_mode),
                            party_index=int(self.ui.party_index),
                        )
                        self.ui.status_text = msg
                        self.ui.error_text = "" if ok else msg
            except Exception as ex:  # noqa: BLE001
                imgui.text_disabled(f"Mixed mob spawner unavailable: {ex}")

        if _collapsing_show(
            imgui.collapsing_header("BMS catalog (Char_* spawn + aggro)", 0),
        ):
            imgui.text_disabled(
                "Rows ending in _SHARED auto-remap to a concrete army/creature "
                "member when known (e.g. Army Bandit → GunToter). Dev Testing Map "
                "re-applies spawn-budget disable + spawn-manager overdrive every click.",
            )
            try:
                from .mob_catalog import draw_squ1ggs_quick_pick  # noqa: PLC0415
                from .mob_favorites import (  # noqa: PLC0415
                    is_favorite_mob,
                    sort_mob_entries_first,
                    toggle_favorite_mob,
                )

                draw_squ1ggs_quick_pick(
                    imgui,
                    self.ui,
                    deploy_fn=self.spawn_mob,
                    sync_filter_fn=None,
                    id_prefix="mob_sq",
                    list_height=240.0,
                    is_favorite=is_favorite_mob,
                    toggle_favorite=toggle_favorite_mob,
                    sort_entries=sort_mob_entries_first,
                )
            except Exception as ex:  # noqa: BLE001
                imgui.text_disabled(f"Catalog picker unavailable: {ex}")

        if _collapsing_show(imgui.collapsing_header("Encounter IO (BMS / oak_spawnai)", 0)):
            imgui.text_wrapped(
                "Requires **BL4 Oak Spawner**. Spawns encounter managers / spawners — not individual Char rows.",
            )
            try:
                from .mob_favorites import (  # noqa: PLC0415
                    is_favorite_encounter,
                    toggle_favorite_encounter,
                )
            except Exception:
                is_favorite_encounter = None  # type: ignore[assignment,misc]
                toggle_favorite_encounter = None  # type: ignore[assignment,misc]

            for label, cmd in self.encounter_presets:
                fav = bool(is_favorite_encounter and is_favorite_encounter(cmd))
                row = f"{'★ ' if fav else ''}{label}"
                if imgui.button(f"{row}##mob_enc_{label[:24]}"):
                    self.run_encounter_line(cmd)
                imgui.same_line()
                if toggle_favorite_encounter is not None:
                    fav_label = "−" if fav else "+"
                    if imgui.small_button(f"{fav_label}##mob_enc_fav_{label[:16]}"):
                        toggle_favorite_encounter(cmd, label)
                    imgui.same_line()
                imgui.text_disabled(cmd[:80])

        if _collapsing_show(imgui.collapsing_header("World props (io_* placed objects)", 0)):
            try:
                from .world_props_ui import draw_world_props_section  # noqa: PLC0415

                draw_world_props_section(
                    imgui,
                    self.ui,
                    run_line=self.run_encounter_line,
                    id_prefix="mob_wp",
                )
            except Exception as ex:  # noqa: BLE001
                imgui.text_disabled(f"World props UI unavailable: {ex}")

        imgui.spacing()
        imgui.text_disabled(
            "Embedded BMS is controlled through the Squ1ggs Boosting Tools desktop app.",
        )

        if _collapsing_show(imgui.collapsing_header("World scale + AI tools", 0)):
            try:
                from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415
                from bl4_world_tools import ai_cloak, world_scale  # noqa: PLC0415

                if deferred.gameplay_ready():
                    wd, gs = world_scale.read_scale()
                    imgui.text_disabled(f"Live pawn: WorldDifficulty={wd} gamestage={gs}")
                else:
                    imgui.text_disabled("Load into a world before applying world scale / cloak.")
                _cwd, self.ui.world_difficulty = imgui.input_int(
                    "World difficulty##mob_wd",
                    int(self.ui.world_difficulty),
                )
                _cgs, self.ui.game_stage = imgui.input_int(
                    "Game stage##mob_gs",
                    int(self.ui.game_stage),
                )
                if imgui.button("Apply to pawn##mob_ws"):
                    wd_i = int(self.ui.world_difficulty)
                    gs_i = int(self.ui.game_stage)

                    def _ws() -> tuple[bool, str]:
                        return world_scale.apply_scale(world_difficulty=wd_i, game_stage=gs_i)

                    if not deferred.gameplay_ready():
                        self.ui.status_text = "Load into a world first."
                    else:
                        self.ui.status_text = deferred.queue_action("Apply world scale", _ws)
                imgui.separator()
                tracked = len(self.tracker.mobs)
                imgui.text_disabled(f"Tracked mobs: {tracked} (cloak buttons use last live spawn)")
                if imgui.button("Uncloak last tracked##mob_uncloak"):
                    if not deferred.gameplay_ready():
                        self.ui.status_text = "Load into a world first."
                    else:
                        def _uc() -> tuple[bool, str]:
                            live = self.tracker.live_mobs_with_codes()
                            if not live:
                                return False, "no tracked mobs"
                            mob, _code = live[-1]
                            return ai_cloak.interrupt_cloak(mob)

                        self.ui.status_text = deferred.queue_action("Uncloak mob", _uc)
                imgui.same_line()
                if imgui.button("Lock cloak (last)##mob_lockcloak"):
                    if not deferred.gameplay_ready():
                        self.ui.status_text = "Load into a world first."
                    else:
                        def _lc() -> tuple[bool, str]:
                            live = self.tracker.live_mobs_with_codes()
                            if not live:
                                return False, "no tracked mobs"
                            mob, _code = live[-1]
                            return ai_cloak.lock_cloak(mob)

                        self.ui.status_text = deferred.queue_action("Lock cloak", _lc)
            except Exception as ex:  # noqa: BLE001
                imgui.text_disabled(f"World/AI tools unavailable: {ex}")


CONTROLLER = MobSpawnerController()
