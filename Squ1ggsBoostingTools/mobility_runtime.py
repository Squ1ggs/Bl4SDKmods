"""Host-only movement tuning and infinite jump runtime for Squ1ggs Boosting Tools."""

from __future__ import annotations

import math
import sys
import time
from typing import Any, Callable

from mods_base import get_pc, hook
import unrealsdk
from unrealsdk import logging

from .inventory_capacity import load_inventory_settings, save_extra_settings
from .movement_adjustments import (
    apply_movement_advanced_to_all_players,
    delete_ground_items,
    reset_movement_advanced_all_players,
    set_noclip,
    set_no_target,
    set_time_dilation,
    toggle_players_only as _toggle_players_only_impl,
    zero_vault_power_costs_all_players,
    _set_attr as _write_move_attr,
)
from .party_helpers import (
    _gbc_find_pc_for_player_state,
    _gbc_is_listen_host_world,
    _gbc_resolve_player_display_name,
    _gbc_session_world_and_gamestate,
)

_PREFIX = "[Squ1ggs Boosting Tools | Mobility]"

DEFAULT_PRESET: dict[str, float | bool] = {
    "speed_scale": 2.0,
    "walk_speed": 1500.0,
    "jump_goal": 420.0,
    "jump_velocity": 420.0,
    "sprint_jump_goal": 420.0,
    "jump_hold_time": 0.0,
    "gravity_scale": 1.0,
    "max_step_height": 45.0,
    "jump_count": 2,
    "jump_off_z_factor": 0.5,
    "walkable_floor_angle": 44.76508331298828,
    "walkable_floor_z": 0.7099999785423279,
    "time_dilation": 1.0,
    "glide_speed": 2600.0,
    "glide_boost": 4200.0,
    "glide_air_control": 6.0,
    "dash_speed": 3000.0,
    "zero_vault_costs": True,
}

_settings = load_inventory_settings()
_auto_apply_on_load: bool = bool(_settings.get("mobility_auto_apply_on_load", False))
_saved_preset: dict[str, object] = dict(_settings.get("mobility_saved_preset", {}) or {})
_noclip: bool = bool(_settings.get("mobility_noclip", False))
# FAAFO-only: collision off + gravity on + force fly off (fall through floors).
_fall_through_indices: set[int] = set()
_no_target: bool = False
_boot_preset: dict[str, object] = dict(DEFAULT_PRESET)
if _auto_apply_on_load and _saved_preset:
    _boot_preset.update(dict(_saved_preset))

speed_scale: float = float(_boot_preset.get("speed_scale", DEFAULT_PRESET["speed_scale"]) or DEFAULT_PRESET["speed_scale"])
walk_speed: float = float(_boot_preset.get("walk_speed", DEFAULT_PRESET["walk_speed"]) or DEFAULT_PRESET["walk_speed"])
jump_goal: float = float(_boot_preset.get("jump_goal", DEFAULT_PRESET["jump_goal"]) or DEFAULT_PRESET["jump_goal"])
gravity_scale: float = float(_boot_preset.get("gravity_scale", DEFAULT_PRESET["gravity_scale"]) or DEFAULT_PRESET["gravity_scale"])
max_step_height: float = float(_boot_preset.get("max_step_height", DEFAULT_PRESET["max_step_height"]) or DEFAULT_PRESET["max_step_height"])
walkable_floor_angle: float = float(_boot_preset.get("walkable_floor_angle", DEFAULT_PRESET["walkable_floor_angle"]) or DEFAULT_PRESET["walkable_floor_angle"])
walkable_floor_z: float = float(_boot_preset.get("walkable_floor_z", DEFAULT_PRESET["walkable_floor_z"]) or DEFAULT_PRESET["walkable_floor_z"])
glide_speed: float = float(_boot_preset.get("glide_speed", DEFAULT_PRESET["glide_speed"]) or DEFAULT_PRESET["glide_speed"])
glide_boost: float = float(_boot_preset.get("glide_boost", DEFAULT_PRESET["glide_boost"]) or DEFAULT_PRESET["glide_boost"])
glide_air_control: float = float(_boot_preset.get("glide_air_control", DEFAULT_PRESET["glide_air_control"]) or DEFAULT_PRESET["glide_air_control"])
dash_speed: float = float(_boot_preset.get("dash_speed", DEFAULT_PRESET["dash_speed"]) or DEFAULT_PRESET["dash_speed"])
zero_vault_costs: bool = bool(_boot_preset.get("zero_vault_costs", True))
time_dilation: float = float(DEFAULT_PRESET.get("time_dilation", 1.0) or 1.0)

status_message: str = "Host-only movement tools. Adjust sliders, then apply to all party pawns."
infinite_jump_indices: set[int] = {
    int(x) for x in (_settings.get("mobility_infinite_jump_indices", []) or []) if str(x).strip().isdigit()
}
# Gates jump hooks / HUD tick. Import installs hooks early; on_enable arms this.
# Default False so a disabled-at-boot mod cannot leave Infinite Jump live.
_runtime_enabled: bool = False
_DEFAULT_JUMP_MAX_COUNT: int = 2
_INFINITE_JUMP_HOOK_TARGETS: tuple[str, ...] = (
    "/Script/Engine.Character:CanJumpInternal",
    "/Script/Engine.Character:CanJump",
    "/Script/Engine.Character:Jump",
    "/Script/GbxGame.OakCharacter:CanJumpInternal",
    "/Script/GbxGame.OakCharacter:CanJump",
    "/Script/GbxGame.OakCharacter:Jump",
    "/Script/OakGame.OakCharacter:CanJumpInternal",
    "/Script/OakGame.OakCharacter:CanJump",
    "/Script/OakGame.OakCharacter:Jump",
)
force_fly_speed: float = 10000.0
force_fly_preset: str = "fast"
FLY_PRESETS: dict[str, float] = {
    # uu/s — Cruise ≈ walk/jog; Fast = travel.
    "cruise": 750.0,
    "fast": 5500.0,
}
force_fly_targets: dict[str, Any] = {}
_force_fly_restore: dict[str, dict[str, Any]] = {}
_force_fly_disabling: set[str] = set()
_force_fly_missing_since: dict[str, float] = {}
_last_force_fly_tick: float = 0.0
_last_orphan_fly_scrub_at: float = 0.0
_last_mobility_party_count: int = 0
_last_remote_walk_scrub_at: float = 0.0
_remote_join_scrub_until: float = 0.0
_force_fly_throttle_until: float = 0.0
_force_fly_altitude_until: float = 0.0
_force_fly_maintain_until: float = 0.0
_force_fly_maintain_until_by_key: dict[str, float] = {}
_force_fly_safe_anchor: dict[str, tuple[float, float, float]] = {}
_force_fly_last_wish: dict[str, tuple[tuple[float, float, float], float]] = {}
_force_fly_liftoff_at: dict[str, float] = {}
_FORCE_FLY_WISH_HOLD_SEC = 0.18
_FORCE_FLY_LIFTOFF_COOLDOWN_SEC = 0.55
_FORCE_FLY_LIFTOFF_Z = 40.0

_apply_on_load_done: bool = False
_last_auto_apply_try: float = 0.0
_debounce_apply_delay: float = 0.35
_pending_apply_due: float = 0.0
_pending_apply: bool = False
_pending_apply_reason: str = ""
_infinite_jump_context_cache: list[tuple[int, str, object, object | None, object | None]] = []
_infinite_jump_context_cache_time: float = 0.0
_infinite_jump_disabling: set[int] = set()
_infinite_jump_disable_until: dict[int, float] = {}
_infinite_jump_all_mode: bool = bool(_settings.get("mobility_infinite_jump_all_mode", False))
_force_fly_all_mode: bool = bool(_settings.get("mobility_force_fly_all_mode", False))
_remote_cheat_fly_latched: set[str] = set()

_log_fn: Callable[[str], None] | None = None
_status_pill_fn: Callable[[str, str], None] | None = None


def bind_ui_callbacks(log_fn: Callable[[str], None], status_pill_fn: Callable[[str, str], None]) -> None:
    global _log_fn, _status_pill_fn
    _log_fn = log_fn
    _status_pill_fn = status_pill_fn


def _log(msg: str) -> None:
    text = str(msg or "")
    try:
        logging.log(text, _PREFIX)
    except Exception:
        pass
    if _log_fn is not None:
        try:
            _log_fn(text)
        except Exception:
            pass


def _set_status_pill(msg: str, accent: str = "cyan") -> None:
    if _status_pill_fn is not None:
        try:
            _status_pill_fn(str(msg or ""), str(accent or "cyan"))
        except Exception:
            pass


def is_listen_host() -> bool:
    try:
        world, _gs = _gbc_session_world_and_gamestate()
    except Exception:
        world = None
    try:
        return bool(_gbc_is_listen_host_world(world))
    except Exception:
        pass
    try:
        pc = get_pc()
        return bool(pc is not None and pc.HasAuthority())
    except Exception:
        return False


def require_host(action: str = "mobility tools", *, quiet: bool = False) -> bool:
    global _apply_on_load_done, _pending_apply, _pending_apply_due, _pending_apply_reason, status_message
    if is_listen_host():
        return True
    _pending_apply = False
    _pending_apply_due = 0.0
    _pending_apply_reason = ""
    _apply_on_load_done = True
    status_message = f"Client mode — {action} paused until you are host."
    if not quiet:
        _log(status_message)
        _set_status_pill(status_message, "gold")
    return False


def _is_default_obj(obj: object) -> bool:
    try:
        return obj is None or "Default__" in str(obj)
    except Exception:
        return obj is None


def _uobject_live(obj: object) -> bool:
    """False for freed wrappers (0xffffffffffffffff AV)."""
    if obj is None or _is_default_obj(obj):
        return False
    try:
        addr = int(obj._get_address() or 0)
    except Exception:
        return False
    return addr > 0 and addr != 0xFFFFFFFFFFFFFFFF


def live_party_contexts() -> list[tuple[int, str, object, object | None, object | None]]:
    world, gs = _gbc_session_world_and_gamestate()
    out: list[tuple[int, str, object, object | None, object | None]] = []
    if gs is None:
        return out
    pa = getattr(gs, "PlayerArray", None)
    if pa is None:
        return out
    try:
        total = len(pa)
    except Exception:
        total = 0
    for i in range(total):
        try:
            ps = pa[i]
        except Exception:
            ps = None
        if ps is None:
            continue
        pc = _gbc_find_pc_for_player_state(ps, world)
        if pc is None:
            continue
        name = _gbc_resolve_player_display_name(ps)
        pawn = None
        for attr in ("Pawn", "AcknowledgedPawn", "Character"):
            try:
                pawn = getattr(pc, attr, None)
                if pawn is not None:
                    break
            except Exception:
                pass
        if pawn is None:
            gp = getattr(pc, "GetPawn", None)
            if callable(gp):
                try:
                    pawn = gp()
                except Exception:
                    pawn = None
        move = None
        if pawn is not None:
            for attr in ("CharacterMovement", "MovementComponent", "PawnMovement", "Movement", "OakCharacterMovement"):
                try:
                    move = getattr(pawn, attr, None)
                    if move is not None:
                        break
                except Exception:
                    pass
            if move is None:
                for meth in ("GetMovementComponent", "GetCharacterMovement"):
                    fn = getattr(pawn, meth, None)
                    if callable(fn):
                        try:
                            move = fn()
                            if move is not None:
                                break
                        except Exception:
                            pass
        out.append((i, name, pc, pawn, move))
    return out


def preset_dict() -> dict[str, object]:
    return {
        "speed_scale": float(speed_scale),
        "walk_speed": float(walk_speed),
        "jump_goal": float(jump_goal),
        "jump_velocity": float(jump_goal),
        "sprint_jump_goal": float(jump_goal),
        "jump_hold_time": 0.0,
        "gravity_scale": float(gravity_scale),
        "max_step_height": float(max_step_height),
        "jump_count": 2,
        "jump_off_z_factor": 0.5,
        "walkable_floor_angle": float(walkable_floor_angle),
        "walkable_floor_z": float(walkable_floor_z),
        "glide_speed": float(glide_speed),
        "glide_boost": float(glide_boost),
        "glide_air_control": float(glide_air_control),
        "dash_speed": float(dash_speed),
        "fly_speed": float(force_fly_speed),
        "fly_preset": str(force_fly_preset),
        "zero_vault_costs": bool(zero_vault_costs),
    }


def get_auto_apply_on_load() -> bool:
    return bool(_auto_apply_on_load)


def set_auto_apply_on_load(value: bool) -> None:
    global _auto_apply_on_load
    _auto_apply_on_load = bool(value)
    save_settings()


def get_noclip_enabled() -> bool:
    return bool(_noclip)


def set_noclip_enabled(value: bool) -> None:
    global _noclip, _fall_through_indices
    _noclip = bool(value)
    if _noclip:
        # Mutual exclusion: fly-noclip vs fall-through.
        _clear_fall_through_all()


def fall_through_enabled_for_index(idx: int) -> bool:
    try:
        return int(idx) in _fall_through_indices
    except Exception:
        return False


def get_fall_through_map_enabled() -> bool:
    """True when the local player is in fall-through mode (kinematic fly checks)."""
    local = local_party_index()
    if local is not None:
        return fall_through_enabled_for_index(int(local))
    return fall_through_enabled_for_index(0)


def set_fall_through_map_enabled(value: bool) -> None:
    """Legacy global toggle — applies to local/host party index only."""
    global _noclip
    local = local_party_index()
    idx = int(local) if local is not None else 0
    set_fall_through_for_index(idx, bool(value))
    if bool(value):
        _noclip = False


def _clear_fall_through_all() -> None:
    global _fall_through_indices
    if not _fall_through_indices:
        return
    for idx in sorted(_fall_through_indices):
        try:
            set_fall_through_for_index(int(idx), False)
        except Exception:
            pass
    _fall_through_indices.clear()


def set_fall_through_for_index(idx: int, enabled: bool) -> str:
    """FAAFO: collision off + gravity on for one boost target. Force fly must be off."""
    global status_message, _noclip
    from .movement_adjustments import apply_fall_through_pawn

    idx = normalize_mobility_target_index(int(idx), party_wide=False)
    if enabled:
        _noclip = False
        if force_fly_enabled_for_index(idx):
            set_force_fly_for_index(idx, False)
    contexts = live_party_contexts()
    target = next((row for row in contexts if int(row[0]) == idx), None)
    if target is None:
        msg = f"Fall through map failed: party index {idx} is unavailable."
        status_message = msg
        _log(msg)
        return msg
    _idx, name, _pc, pawn, move = target
    if pawn is None or move is None:
        msg = f"Fall through map failed: no pawn for {name}."
        status_message = msg
        _log(msg)
        return msg
    if enabled:
        _fall_through_indices.add(idx)
    else:
        _fall_through_indices.discard(idx)
    msg = apply_fall_through_pawn(pawn, move, enabled=bool(enabled))
    if enabled:
        msg = f"{msg} Force fly off for {name}."
    else:
        msg = f"{msg} ({name})"
    status_message = msg
    _log(msg)
    _set_status_pill(msg, "red" if enabled else "cyan")
    return msg


def save_settings() -> None:
    try:
        save_extra_settings(
            mobility_auto_apply_on_load=bool(_auto_apply_on_load),
            mobility_saved_preset=dict(_saved_preset),
            mobility_noclip=bool(_noclip),
            mobility_infinite_jump_indices=sorted(int(x) for x in infinite_jump_indices),
            mobility_infinite_jump_all_mode=bool(_infinite_jump_all_mode),
            mobility_force_fly_all_mode=bool(_force_fly_all_mode),
        )
    except Exception as exc:
        _log(f"Mobility settings save failed: {exc!r}")


def save_current_preset() -> None:
    global _saved_preset, status_message
    _saved_preset = preset_dict()
    save_settings()
    status_message = "Saved current mobility values as preset."
    _log(status_message)
    _set_status_pill(status_message, "green")


def load_saved_preset(*, apply_now: bool = True) -> None:
    global speed_scale, walk_speed, jump_goal, gravity_scale, max_step_height
    global walkable_floor_angle, walkable_floor_z, glide_speed, glide_boost, glide_air_control, dash_speed, zero_vault_costs, status_message
    if not _saved_preset:
        status_message = "No mobility preset saved yet."
        _log(status_message)
        _set_status_pill(status_message, "gold")
        return
    p = dict(DEFAULT_PRESET)
    p.update(dict(_saved_preset))
    speed_scale = float(p.get("speed_scale", DEFAULT_PRESET["speed_scale"]) or DEFAULT_PRESET["speed_scale"])
    walk_speed = float(p.get("walk_speed", DEFAULT_PRESET["walk_speed"]) or DEFAULT_PRESET["walk_speed"])
    jump_goal = float(p.get("jump_goal", DEFAULT_PRESET["jump_goal"]) or DEFAULT_PRESET["jump_goal"])
    gravity_scale = float(p.get("gravity_scale", DEFAULT_PRESET["gravity_scale"]) or DEFAULT_PRESET["gravity_scale"])
    max_step_height = float(p.get("max_step_height", DEFAULT_PRESET["max_step_height"]) or DEFAULT_PRESET["max_step_height"])
    walkable_floor_angle = float(p.get("walkable_floor_angle", DEFAULT_PRESET["walkable_floor_angle"]) or DEFAULT_PRESET["walkable_floor_angle"])
    walkable_floor_z = float(p.get("walkable_floor_z", DEFAULT_PRESET["walkable_floor_z"]) or DEFAULT_PRESET["walkable_floor_z"])
    glide_speed = float(p.get("glide_speed", DEFAULT_PRESET["glide_speed"]) or DEFAULT_PRESET["glide_speed"])
    glide_boost = float(p.get("glide_boost", DEFAULT_PRESET["glide_boost"]) or DEFAULT_PRESET["glide_boost"])
    glide_air_control = float(p.get("glide_air_control", DEFAULT_PRESET["glide_air_control"]) or DEFAULT_PRESET["glide_air_control"])
    dash_speed = float(p.get("dash_speed", DEFAULT_PRESET["dash_speed"]) or DEFAULT_PRESET["dash_speed"])
    zero_vault_costs = bool(p.get("zero_vault_costs", True))
    if apply_now:
        apply_all()
    else:
        status_message = "Loaded saved mobility preset into UI."
        _log(status_message)


def schedule_debounced_apply(reason: str = "slider") -> None:
    global _pending_apply_due, _pending_apply, _pending_apply_reason, status_message
    try:
        _pending_apply_due = time.monotonic() + float(_debounce_apply_delay)
    except Exception:
        _pending_apply_due = 0.0
    _pending_apply = True
    _pending_apply_reason = str(reason or "slider")
    status_message = f"Mobility changes pending… applying after slider stops ({_debounce_apply_delay:.2f}s)."


def apply_pending_if_due(now: float | None = None) -> None:
    global _pending_apply_due, _pending_apply, _pending_apply_reason
    if not _pending_apply:
        return
    try:
        t = time.monotonic() if now is None else float(now)
    except Exception:
        t = time.monotonic()
    if t < float(_pending_apply_due or 0.0):
        return
    _pending_apply = False
    _pending_apply_due = 0.0
    reason = _pending_apply_reason or "slider"
    _pending_apply_reason = ""
    _log(f"Mobility debounced apply fired after {reason} changes.")
    apply_all()


def recalc_floor_z_from_angle() -> None:
    global walkable_floor_z
    try:
        import math
        walkable_floor_z = max(0.0, min(1.0, math.cos(math.radians(float(walkable_floor_angle)))))
    except Exception:
        pass


def apply_all() -> None:
    global _pending_apply, _pending_apply_due, _pending_apply_reason, status_message
    global speed_scale, walk_speed, jump_goal, gravity_scale, max_step_height
    global walkable_floor_angle, walkable_floor_z, glide_speed, glide_boost, glide_air_control, dash_speed, zero_vault_costs
    _pending_apply = False
    _pending_apply_due = 0.0
    _pending_apply_reason = ""
    if not require_host("mobility apply"):
        return
    speed_scale = max(0.05, min(25.0, float(speed_scale)))
    walk_speed = max(50.0, min(10000.0, float(walk_speed)))
    jump_goal = max(0.0, min(10000.0, float(jump_goal)))
    gravity_scale = max(0.0, min(10.0, float(gravity_scale)))
    max_step_height = max(0.0, min(1000.0, float(max_step_height)))
    walkable_floor_angle = max(0.0, min(89.9, float(walkable_floor_angle)))
    walkable_floor_z = max(0.0, min(1.0, float(walkable_floor_z)))
    glide_speed = max(0.0, min(30000.0, float(glide_speed)))
    glide_boost = max(0.0, min(30000.0, float(glide_boost)))
    glide_air_control = max(0.0, min(50.0, float(glide_air_control)))
    dash_speed = max(0.0, min(30000.0, float(dash_speed)))
    try:
        msg = apply_movement_advanced_to_all_players(
            speed_scale,
            walk_speed,
            jump_goal,
            jump_goal,
            gravity_scale,
            max_step_height,
            2,
            0.5,
            walkable_floor_angle,
            walkable_floor_z,
            jump_goal,
            0.0,
            glide_speed,
            glide_boost,
            glide_air_control,
            dash_speed,
            0.0 if zero_vault_costs else None,
            local_only=True,
        )
        status_message = msg
        _log(msg)
        _set_status_pill(msg, "green")
    except Exception as exc:
        status_message = f"Mobility apply failed: {exc!r}"
        _log(status_message)


def reset_all() -> None:
    global speed_scale, walk_speed, jump_goal, gravity_scale, max_step_height
    global walkable_floor_angle, walkable_floor_z, glide_speed, glide_boost, glide_air_control, dash_speed, zero_vault_costs, status_message
    if not require_host("mobility reset"):
        return
    speed_scale = float(DEFAULT_PRESET["speed_scale"])
    walk_speed = float(DEFAULT_PRESET["walk_speed"])
    jump_goal = float(DEFAULT_PRESET["jump_goal"])
    gravity_scale = float(DEFAULT_PRESET["gravity_scale"])
    max_step_height = float(DEFAULT_PRESET["max_step_height"])
    walkable_floor_angle = float(DEFAULT_PRESET["walkable_floor_angle"])
    walkable_floor_z = float(DEFAULT_PRESET["walkable_floor_z"])
    glide_speed = float(DEFAULT_PRESET["glide_speed"])
    glide_boost = float(DEFAULT_PRESET["glide_boost"])
    glide_air_control = float(DEFAULT_PRESET["glide_air_control"])
    dash_speed = float(DEFAULT_PRESET["dash_speed"])
    zero_vault_costs = False
    try:
        msg = reset_movement_advanced_all_players(local_only=True)
        status_message = f"{msg} Reset mobility sliders to defaults (host only)."
        _log(status_message)
        _set_status_pill("Mobility reset to defaults.", "gold")
    except Exception as exc:
        status_message = f"Mobility reset failed: {exc!r}"
        _log(status_message)


def apply_preset(
    *,
    speed: float,
    walk: float,
    jump: float,
    gravity: float | None = None,
    step: float | None = None,
    glide_s: float | None = None,
    glide_b: float | None = None,
    glide_air: float | None = None,
    dash: float | None = None,
    zero_vault: bool | None = None,
    floor_angle: float | None = None,
) -> None:
    global speed_scale, walk_speed, jump_goal, gravity_scale, max_step_height
    global glide_speed, glide_boost, glide_air_control, dash_speed, zero_vault_costs, walkable_floor_angle
    speed_scale = float(speed)
    walk_speed = float(walk)
    jump_goal = float(jump)
    if gravity is not None:
        gravity_scale = float(gravity)
    if step is not None:
        max_step_height = float(step)
    if glide_s is not None:
        glide_speed = float(glide_s)
    if glide_b is not None:
        glide_boost = float(glide_b)
    if glide_air is not None:
        glide_air_control = float(glide_air)
    if dash is not None:
        dash_speed = float(dash)
    if zero_vault is not None:
        zero_vault_costs = bool(zero_vault)
    if floor_angle is not None:
        walkable_floor_angle = float(floor_angle)
        recalc_floor_z_from_angle()
    apply_all()


def zero_vault_now() -> None:
    global status_message
    if not require_host("zero vault"):
        return
    try:
        msg = zero_vault_power_costs_all_players()
        status_message = msg
        _log(msg)
        _set_status_pill(msg, "green")
    except Exception as exc:
        status_message = f"Zero vault failed: {exc!r}"
        _log(status_message)


def set_time() -> None:
    global time_dilation, status_message
    time_dilation = max(0.0, min(64.0, float(time_dilation)))
    msg = set_time_dilation(time_dilation)
    save_settings()
    status_message = msg
    _log(msg)
    _set_status_pill(msg, "cyan")


def reset_time() -> None:
    global time_dilation
    time_dilation = 1.0
    set_time()


def apply_noclip() -> None:
    """Collision off for exploration. Auto-enables local force fly so you don't freefall."""
    global status_message
    if _noclip:
        _clear_fall_through_all()
    msg = set_noclip(_noclip)
    if _noclip:
        try:
            local = local_party_index()
            host_idx = int(local) if local is not None else 0
            set_force_fly_for_index(host_idx, True)
            msg = f"{msg} Force fly auto-ON."
        except Exception as exc:
            msg = f"{msg} (force fly auto-ON failed: {exc!r})"
    save_settings()
    status_message = msg
    _log(msg)
    _set_status_pill(msg, "purple")


def apply_fall_through_map() -> None:
    """Legacy host-only fall-through apply."""
    local = local_party_index()
    idx = int(local) if local is not None else 0
    set_fall_through_for_index(idx, idx in _fall_through_indices)


def no_target_enabled() -> bool:
    return bool(_no_target)


def toggle_no_target() -> None:
    global _no_target, status_message
    requested = not bool(_no_target)
    msg = set_no_target(requested)
    if "failed" not in str(msg).casefold() and "unavailable" not in str(msg).casefold():
        _no_target = requested
    status_message = msg
    _log(msg)
    _set_status_pill(msg, "purple")


def teleport_selected_to_party_slot(slot_idx: int, selected_idx: int | None) -> None:
    """Teleport selected party pawn to another party slot's pawn."""
    global status_message
    try:
        contexts = live_party_contexts()
        src = None
        dst = None
        src_name = None
        dst_name = None
        for ctx_idx, name, _pc, pawn, _move in contexts:
            if selected_idx is not None and int(ctx_idx) == int(selected_idx):
                src = pawn
                src_name = name
            if int(ctx_idx) == int(slot_idx):
                dst = pawn
                dst_name = name
        if src is None:
            status_message = "Teleport failed: no selected player pawn."
        elif dst is None:
            status_message = f"Teleport failed: P{int(slot_idx) + 1} pawn not found."
        else:
            from .movement_adjustments import teleport_pawn_to_pawn

            status_message = (
                teleport_pawn_to_pawn(src, dst)
                + f" {src_name or 'Selected'} -> P{int(slot_idx) + 1} {dst_name or ''}."
            )
        _log(status_message)
        _set_status_pill(status_message, "cyan")
    except Exception as exc:
        status_message = f"Teleport failed: {exc!r}"
        _log(status_message)
        _set_status_pill(status_message, "red")


def _local_party_context() -> tuple[int, str, object, object | None] | None:
    """Return (idx, name, pc, pawn) for the local/host pawn when possible."""
    contexts = live_party_contexts()
    if not contexts:
        return None
    try:
        from mods_base import get_pc

        local_pc = get_pc()
    except Exception:
        local_pc = None
    if local_pc is not None:
        for ctx_idx, name, pc, pawn, _move in contexts:
            if pc is local_pc:
                return int(ctx_idx), str(name), pc, pawn
    # Fallback: first live context (host is usually index 0 on listen server).
    ctx_idx, name, pc, pawn, _move = contexts[0]
    return int(ctx_idx), str(name), pc, pawn


def teleport_local_to_party_slot(slot_idx: int) -> None:
    """Teleport local/host pawn to another party slot."""
    global status_message
    try:
        local = _local_party_context()
        if local is None:
            status_message = "Teleport failed: local pawn not found."
            _log(status_message)
            _set_status_pill(status_message, "red")
            return
        _local_idx, local_name, _pc, src = local
        if src is None:
            status_message = "Teleport failed: local pawn missing."
            _log(status_message)
            _set_status_pill(status_message, "red")
            return
        contexts = live_party_contexts()
        dst = None
        dst_name = None
        for ctx_idx, name, _pc, pawn, _move in contexts:
            if int(ctx_idx) == int(slot_idx):
                dst = pawn
                dst_name = name
                break
        if dst is None:
            status_message = f"Teleport failed: P{int(slot_idx) + 1} pawn not found."
        else:
            from .movement_adjustments import teleport_pawn_to_pawn

            status_message = (
                teleport_pawn_to_pawn(src, dst)
                + f" {local_name or 'You'} -> P{int(slot_idx) + 1} {dst_name or ''}."
            )
        _log(status_message)
        _set_status_pill(status_message, "cyan")
    except Exception as exc:
        status_message = f"Teleport failed: {exc!r}"
        _log(status_message)
        _set_status_pill(status_message, "red")


def teleport_party_slot_to_local(slot_idx: int) -> None:
    """Teleport a party slot's pawn to the local/host pawn."""
    global status_message
    try:
        local = _local_party_context()
        if local is None:
            status_message = "Teleport failed: local pawn not found."
            _log(status_message)
            _set_status_pill(status_message, "red")
            return
        _local_idx, local_name, _pc, dst = local
        if dst is None:
            status_message = "Teleport failed: local pawn missing."
            _log(status_message)
            _set_status_pill(status_message, "red")
            return
        contexts = live_party_contexts()
        src = None
        src_name = None
        for ctx_idx, name, _pc, pawn, _move in contexts:
            if int(ctx_idx) == int(slot_idx):
                src = pawn
                src_name = name
                break
        if src is None:
            status_message = f"Teleport failed: P{int(slot_idx) + 1} pawn not found."
        else:
            from .movement_adjustments import teleport_pawn_to_pawn

            status_message = (
                teleport_pawn_to_pawn(src, dst)
                + f" P{int(slot_idx) + 1} {src_name or ''} -> {local_name or 'You'}."
            )
        _log(status_message)
        _set_status_pill(status_message, "cyan")
    except Exception as exc:
        status_message = f"Teleport failed: {exc!r}"
        _log(status_message)
        _set_status_pill(status_message, "red")


def teleport_selected_to_local(selected_idx: int | None) -> None:
    """Teleport Rewards Hub selected player to local/host."""
    global status_message
    if selected_idx is None:
        status_message = "Teleport failed: no selected player."
        _log(status_message)
        _set_status_pill(status_message, "red")
        return
    teleport_party_slot_to_local(int(selected_idx))


def teleport_local_to_selected(selected_idx: int | None) -> None:
    """Teleport local/host to Rewards Hub selected player."""
    global status_message
    if selected_idx is None:
        status_message = "Teleport failed: no selected player."
        _log(status_message)
        _set_status_pill(status_message, "red")
        return
    teleport_local_to_party_slot(int(selected_idx))


def delete_ground_loot() -> None:
    global status_message
    msg = delete_ground_items()
    status_message = msg
    _log(msg)
    _set_status_pill(msg, "red")


def toggle_players_only() -> None:
    global status_message
    msg = _toggle_players_only_impl()
    status_message = msg
    _log(msg)
    _set_status_pill(msg, "purple")


def enabled_infinite_names() -> str:
    try:
        contexts = live_party_contexts()
    except Exception:
        contexts = []
    names = [str(name) for idx, name, _pc, _pawn, _move in contexts if int(idx) in infinite_jump_indices]
    return ", ".join(names) if names else "none"


def _normal_jump_max_count() -> int:
    try:
        raw = _saved_preset.get("jump_count", _DEFAULT_JUMP_MAX_COUNT)
        return max(1, min(50, int(raw if raw is not None else _DEFAULT_JUMP_MAX_COUNT)))
    except Exception:
        return _DEFAULT_JUMP_MAX_COUNT


def _restore_pawn_jump_limits(pawn: object, move: object | None = None) -> bool:
    """Undo Infinite Jump's JumpMaxCount=999 so OFF actually stops multi-hop."""
    if pawn is None or _is_default_obj(pawn):
        return False
    max_count = _normal_jump_max_count()
    touched = False
    try:
        move_obj = move or getattr(pawn, "OakCharacterMovement", None) or getattr(pawn, "CharacterMovement", None)
    except Exception:
        move_obj = move
    for obj in (pawn, move_obj):
        if obj is None:
            continue
        for attr, value in (
            ("JumpMaxCount", max_count),
            ("JumpCurrentCount", 0),
            ("JumpCurrentCountPreJump", 0),
            ("JumpedCount", 0),
        ):
            try:
                if hasattr(obj, attr):
                    setattr(obj, attr, value)
                    touched = True
            except Exception:
                pass
        try:
            setter = getattr(obj, "SetJumpMaxCount", None)
            if callable(setter):
                setter(max_count)
                touched = True
        except Exception:
            pass
    return touched


def _restore_jump_limits_for_indices(indices: set[int] | None = None) -> int:
    """Restore jump limits for specific party indices, or every live pawn if None."""
    try:
        contexts = live_party_contexts()
    except Exception:
        contexts = []
    restored = 0
    for idx, _name, _pc, pawn, move in contexts:
        try:
            if indices is not None and int(idx) not in indices:
                continue
        except Exception:
            continue
        if _restore_pawn_jump_limits(pawn, move):
            restored += 1
    return restored


def set_runtime_enabled(enabled: bool) -> None:
    """Called from mod on_enable / on_disable so menu toggle stops live effects."""
    global _runtime_enabled, status_message, _infinite_jump_context_cache, _infinite_jump_context_cache_time
    _runtime_enabled = bool(enabled)
    _infinite_jump_context_cache = []
    _infinite_jump_context_cache_time = 0.0
    if not _runtime_enabled:
        # Keep saved indices so re-enable can resume preference, but undo live 999 caps now.
        try:
            n = _restore_jump_limits_for_indices(None)
        except Exception:
            n = 0
        status_message = f"Mobility runtime disabled (restored jump limits on {n} pawn(s))."
        _log(status_message)
    else:
        status_message = "Mobility runtime enabled."
        _log(status_message)
        try:
            _prune_remote_mobility_toggles()
        except Exception:
            pass


def local_party_index() -> int | None:
    """Which PlayerArray slot is the local PC (listen host or client)."""
    try:
        from mods_base import get_pc

        local_pc = get_pc()
        local_ps = getattr(local_pc, "PlayerState", None) if local_pc is not None else None
    except Exception:
        return None
    if local_pc is None:
        return None
    try:
        contexts = live_party_contexts()
    except Exception:
        contexts = []
    for cidx, _name, pc, pawn, _move in contexts:
        if pc is local_pc:
            return int(cidx)
        if local_ps is not None and pc is not None:
            try:
                if getattr(pc, "PlayerState", None) is local_ps:
                    return int(cidx)
            except Exception:
                pass
        if pawn is not None:
            for attr in ("Pawn", "AcknowledgedPawn", "Character"):
                try:
                    if getattr(local_pc, attr, None) is pawn:
                        return int(cidx)
                except Exception:
                    pass
    return None


def normalize_mobility_target_index(idx: int, *, party_wide: bool = False) -> int:
    """Resolve boost-target party index (listen host applies to remote pawns)."""
    if party_wide:
        return int(idx)
    try:
        idx = int(idx)
    except Exception:
        idx = 0
    if idx < 0:
        local = local_party_index()
        return int(local) if local is not None else 0
    return idx


def _infinite_jump_party_wide() -> bool:
    """True when every live party member has infinite jump (explicit all-party mode)."""
    if _infinite_jump_all_mode:
        return True
    try:
        contexts = live_party_contexts()
        indices = [int(i) for i, _n, _pc, pawn, _m in contexts if pawn is not None and not _is_default_obj(pawn)]
    except Exception:
        return False
    if len(indices) <= 1:
        return True
    return bool(indices) and all(i in infinite_jump_indices for i in indices)


def _may_mutate_infinite_jump(idx: int | None) -> bool:
    if idx is None:
        return False
    return int(idx) in infinite_jump_indices


def _force_fly_party_wide() -> bool:
    """True when every live party member is in force_fly_targets."""
    if _force_fly_all_mode:
        return True
    try:
        from .uvhm_progression import selected_lobby_identity

        contexts = live_party_contexts()
        keys: list[str] = []
        for cidx, _n, _pc, pawn, _move in contexts:
            if pawn is None or _is_default_obj(pawn):
                continue
            try:
                keys.append(str(selected_lobby_identity(int(cidx)).key))
            except Exception:
                return False
    except Exception:
        return False
    if len(keys) <= 1:
        return True
    return bool(keys) and all(k in force_fly_targets for k in keys)


def pawn_party_index(pawn: object) -> int | None:
    if pawn is None:
        return None
    try:
        contexts = live_party_contexts()
    except Exception:
        contexts = []
    pawn_s = str(pawn)
    for idx, _name, _pc, ctx_pawn, _move in contexts:
        try:
            if ctx_pawn is pawn or str(ctx_pawn) == pawn_s:
                return int(idx)
        except Exception:
            pass
    return None


def set_infinite_jump_for_index(idx: int, enabled: bool) -> None:
    global status_message, _infinite_jump_context_cache, _infinite_jump_context_cache_time
    global _infinite_jump_disabling, _infinite_jump_disable_until, _infinite_jump_all_mode
    try:
        _infinite_jump_all_mode = False
        idx = normalize_mobility_target_index(int(idx), party_wide=False)
        if enabled:
            infinite_jump_indices.add(idx)
            _infinite_jump_disabling.discard(idx)
            _infinite_jump_disable_until.pop(idx, None)
        else:
            infinite_jump_indices.discard(idx)
            _infinite_jump_disabling.add(idx)
            _infinite_jump_disable_until[idx] = time.monotonic() + 4.0
            _restore_jump_limits_for_indices({idx})
        _infinite_jump_context_cache = []
        _infinite_jump_context_cache_time = 0.0
        save_settings()
        if enabled:
            status_message = "Infinite Jump ON (you)."
            pill = "green"
        else:
            status_message = "Infinite Jump OFF."
            pill = "cyan"
        _log(status_message)
        _set_status_pill(status_message, pill)
    except Exception as exc:
        status_message = f"Infinite Jump toggle failed: {exc!r}"
        _log(status_message)
        _set_status_pill(status_message, "red")


def set_infinite_jump_all(enabled: bool) -> None:
    global status_message, _infinite_jump_context_cache, _infinite_jump_context_cache_time
    global _infinite_jump_disabling, _infinite_jump_disable_until, _infinite_jump_all_mode
    try:
        _infinite_jump_all_mode = bool(enabled)
        contexts = live_party_contexts()
        if enabled:
            infinite_jump_indices.clear()
            _infinite_jump_disabling.clear()
            _infinite_jump_disable_until.clear()
            for idx, _name, _pc, pawn, _move in contexts:
                if pawn is not None and not _is_default_obj(pawn):
                    infinite_jump_indices.add(int(idx))
        else:
            infinite_jump_indices.clear()
            now = time.monotonic()
            for idx, _name, _pc, pawn, _move in contexts:
                if pawn is None or _is_default_obj(pawn):
                    continue
                i = int(idx)
                _infinite_jump_disabling.add(i)
                _infinite_jump_disable_until[i] = now + 4.0
            _restore_jump_limits_for_indices(None)
        _infinite_jump_context_cache = []
        _infinite_jump_context_cache_time = 0.0
        save_settings()
        status_message = f"Infinite Jump enabled for: {enabled_infinite_names()}."
        _log(status_message)
        _set_status_pill(status_message, "green" if enabled else "cyan")
    except Exception as exc:
        status_message = f"Infinite Jump all toggle failed: {exc!r}"
        _log(status_message)
        _set_status_pill(status_message, "red")


def _sanitize_force_fly_restore(restore: dict[str, Any] | None) -> dict[str, Any]:
    """Drop poisoned fly values so OFF always returns to walkable defaults."""
    out = dict(restore or {})
    out["pawn.bCheatFlying"] = False
    out["move.GravityScale"] = 1.0
    out["state.bCanFly"] = False
    for key, default, max_ok in (
        ("move.MaxWalkSpeed", 600.0, 2500.0),
        ("move.MinAnalogWalkSpeed", 20.0, 600.0),
        ("move.MaxFlySpeed", 600.0, 2500.0),
        ("move.MaxAcceleration", 2048.0, 12000.0),
        ("move.BrakingDecelerationWalking", 2048.0, 20000.0),
        ("move.BrakingDecelerationFlying", 0.0, 20000.0),
        ("move.AirControl", 0.35, 2.0),
        ("move.Friction", 8.0, 40.0),
    ):
        try:
            val = float(out.get(key, default))
        except Exception:
            out[key] = default
            continue
        if val <= 0.05 or val > max_ok:
            out[key] = default
        else:
            out[key] = val
    out.setdefault("move.DefaultLandMovementMode", 1)
    out.setdefault("move.GroundMovementMode", 1)
    out.setdefault("move.MovementMode", 1)
    out.setdefault("move.NetworkSmoothingMode", 2)
    out.setdefault("move.bAlwaysCheckFloor", True)
    return out


def _capture_force_fly_state(pawn: object, move: object) -> dict[str, Any]:
    out: dict[str, Any] = {"_pawn_id": id(pawn), "_move_id": id(move)}
    for prefix, obj, attrs in (
        ("pawn", pawn, ("bCheatFlying",)),
        (
            "move",
            move,
            (
                "GravityScale",
                "MaxFlySpeed",
                "MinAnalogWalkSpeed",
                "MaxWalkSpeed",
                "MaxAcceleration",
                "BrakingDecelerationFlying",
                "BrakingDecelerationWalking",
                "AirControl",
                "Friction",
                "DefaultLandMovementMode",
                "GroundMovementMode",
                "MovementMode",
                "NetworkSmoothingMode",
                "bAlwaysCheckFloor",
            ),
        ),
    ):
        for attr in attrs:
            try:
                out[f"{prefix}.{attr}"] = getattr(obj, attr)
            except Exception:
                pass
    try:
        state = getattr(move, "MovementState", None)
        if state is not None:
            out["state.bCanFly"] = getattr(state, "bCanFly")
    except Exception:
        pass
    return out


def _movement_components_for_pawn(pawn: object | None) -> list[object]:
    if pawn is None:
        return []
    seen: set[int] = set()
    out: list[object] = []
    for attr in (
        "OakCharacterMovement",
        "CharacterMovement",
        "GbxCharacterMovement",
        "MovementComponent",
        "PawnMovement",
        "Movement",
    ):
        try:
            comp = getattr(pawn, attr, None)
        except Exception:
            comp = None
        if comp is not None and id(comp) not in seen:
            seen.add(id(comp))
            out.append(comp)
    for meth in ("GetMovementComponent", "GetCharacterMovement"):
        fn = getattr(pawn, meth, None)
        if callable(fn):
            try:
                comp = fn()
            except Exception:
                comp = None
            if comp is not None and id(comp) not in seen:
                seen.add(id(comp))
                out.append(comp)
    return out


_FLY_SPEED_MIN = 300.0
_FLY_SPEED_MAX = 500000.0
# High-speed kinematic no-sweep threshold (only custom speeds above this use it now).
_FLY_KINEMATIC_NOSWEEP_SPEED = 12000.0


def clamp_force_fly_speed(value: Any, default: float = 25000.0) -> float:
    """Keep fly speed inside what Oak CharacterMovement can actually simulate."""
    try:
        speed = float(value)
    except Exception:
        speed = float(default)
    if speed != speed or speed <= 0.0:  # NaN / junk
        speed = float(default)
    return max(_FLY_SPEED_MIN, min(_FLY_SPEED_MAX, speed))


def normalize_fly_preset(value: Any, default: str = "fast") -> str:
    key = str(value or "").strip().lower()
    if key == "custom":
        return "custom"
    if key in FLY_PRESETS:
        return key
    return default if default in FLY_PRESETS else "fast"


def apply_fly_preset(preset: Any, *, custom_speed: Any = None, prefer_preset: bool = True) -> float:
    """Map Cruise/Fast onto force_fly_speed.

    The EXE always sends the number field with the preset. Prefer the preset so a
    stale custom value does not silently override the pick.
    """
    global force_fly_preset
    has_preset = str(preset or "").strip().lower() in FLY_PRESETS
    if has_preset:
        force_fly_preset = normalize_fly_preset(preset)
        base = float(FLY_PRESETS[force_fly_preset])
        if prefer_preset:
            return set_force_fly_speed_value(base, preset=force_fly_preset)
    else:
        force_fly_preset = normalize_fly_preset(force_fly_preset)
        base = float(FLY_PRESETS[force_fly_preset])
    if custom_speed is not None and str(custom_speed).strip() != "":
        try:
            custom = float(custom_speed)
        except Exception:
            custom = base
        return set_force_fly_speed_value(custom, preset="custom")
    return set_force_fly_speed_value(base, preset=force_fly_preset)


def set_force_fly_speed_value(speed: Any, *, preset: str | None = None, log: bool = True) -> float:
    """Commit fly speed and force movement stamps to pick it up immediately."""
    global force_fly_speed, force_fly_preset, _force_fly_maintain_until
    force_fly_speed = clamp_force_fly_speed(speed)
    if preset is not None:
        force_fly_preset = normalize_fly_preset(preset) if preset != "custom" else "custom"
    _force_fly_maintain_until = 0.0
    if log:
        try:
            from . import runtime_log
            from ._mod_version import __version__

            runtime_log.note(
                f"force fly speed {__version__}: {force_fly_speed:.0f} ({force_fly_preset})"
            )
            runtime_log.flush(force=True)
        except Exception:
            _log(f"Force fly speed -> {force_fly_speed:.0f} ({force_fly_preset})")
    return float(force_fly_speed)


def _fly_motion_params() -> tuple[float, float, float]:
    """speed, accel, fly-brake — accel unused by kinematic fly, kept for stamps."""
    speed = clamp_force_fly_speed(force_fly_speed)
    accel = max(48000.0, min(speed * 6.0, 900000.0))
    return speed, accel, 0.0


def _make_fly_vector(x: float, y: float, z: float) -> Any:
    try:
        return unrealsdk.make_struct("Vector", X=float(x), Y=float(y), Z=float(z))
    except Exception:
        return None


def _pawn_world_location(pawn: object) -> tuple[float, float, float] | None:
    if not _uobject_live(pawn):
        return None
    for meth in ("K2_GetActorLocation", "GetActorLocation"):
        try:
            fn = getattr(pawn, meth, None)
            if not callable(fn):
                continue
            loc = fn()
            if loc is None:
                continue
            return (
                float(getattr(loc, "X", 0.0) or 0.0),
                float(getattr(loc, "Y", 0.0) or 0.0),
                float(getattr(loc, "Z", 0.0) or 0.0),
            )
        except Exception:
            continue
    return None


def _set_pawn_world_location(
    pawn: object,
    x: float,
    y: float,
    z: float,
    *,
    sweep: bool = True,
) -> bool:
    """Move pawn. ``sweep=True`` stops on floors/walls (unless collision is disabled)."""
    vec = _make_fly_vector(x, y, z)
    if vec is None or not _uobject_live(pawn):
        return False
    # UE: K2_SetActorLocation(NewLocation, bSweep, SweepHitResult, bTeleport)
    for meth, args in (
        ("K2_SetActorLocation", (vec, bool(sweep), None, True)),
        ("K2_SetActorLocation", (vec, bool(sweep), None, False)),
        ("SetActorLocation", (vec, bool(sweep), None, True)),
    ):
        try:
            fn = getattr(pawn, meth, None)
            if not callable(fn):
                continue
            if bool(fn(*args)):
                return True
        except TypeError:
            try:
                fn = getattr(pawn, meth, None)
                if callable(fn) and bool(fn(vec, bool(sweep))):
                    return True
            except Exception:
                continue
        except Exception:
            continue
    if not sweep:
        try:
            fn = getattr(pawn, "K2_TeleportTo", None)
            if callable(fn):
                rot = None
                try:
                    getter = getattr(pawn, "K2_GetActorRotation", None)
                    rot = getter() if callable(getter) else None
                except Exception:
                    rot = None
                if rot is not None and bool(fn(vec, rot)):
                    return True
        except Exception:
            pass
    try:
        cur = _pawn_world_location(pawn)
        if cur is None:
            return False
        delta = _make_fly_vector(x - cur[0], y - cur[1], z - cur[2])
        if delta is None:
            return False
        for meth in ("K2_AddActorWorldOffset", "AddActorWorldOffset"):
            fn = getattr(pawn, meth, None)
            if not callable(fn):
                continue
            try:
                fn(delta, bool(sweep), None, True)
                return True
            except TypeError:
                try:
                    fn(delta, bool(sweep))
                    return True
                except Exception:
                    continue
            except Exception:
                continue
    except Exception:
        pass
    return False


def _control_yaw_forward_right(
    pc: object | None,
    pawn: object | None,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Horizontal forward/right from control yaw only — pitch must not steer fly."""
    import math

    rot = None
    try:
        if pc is not None:
            getter = getattr(pc, "GetControlRotation", None)
            if callable(getter):
                rot = getter()
            if rot is None:
                cam = getattr(pc, "PlayerCameraManager", None)
                if cam is not None:
                    getter = getattr(cam, "GetCameraRotation", None)
                    rot = getter() if callable(getter) else getattr(cam, "CameraRotation", None)
        if rot is None and pawn is not None:
            getter = getattr(pawn, "K2_GetActorRotation", None)
            rot = getter() if callable(getter) else None
    except Exception:
        rot = None
    if rot is None:
        return (1.0, 0.0), (0.0, 1.0)
    try:
        yaw = float(getattr(rot, "Yaw", 0.0) or 0.0)
        if abs(yaw) > 360.0:
            yaw = yaw * 360.0 / 65536.0
        yaw_r = yaw * math.pi / 180.0
        fwd = (math.cos(yaw_r), math.sin(yaw_r))
        right = (-math.sin(yaw_r), math.cos(yaw_r))
        return fwd, right
    except Exception:
        return (1.0, 0.0), (0.0, 1.0)


def _control_look_unit(pc: object | None, pawn: object | None) -> tuple[float, float, float]:
    import math

    rot = None
    try:
        if pc is not None:
            getter = getattr(pc, "GetControlRotation", None)
            if callable(getter):
                rot = getter()
            if rot is None:
                cam = getattr(pc, "PlayerCameraManager", None)
                if cam is not None:
                    getter = getattr(cam, "GetCameraRotation", None)
                    rot = getter() if callable(getter) else getattr(cam, "CameraRotation", None)
        if rot is None and pawn is not None:
            getter = getattr(pawn, "K2_GetActorRotation", None)
            rot = getter() if callable(getter) else None
    except Exception:
        rot = None
    if rot is None:
        return (1.0, 0.0, 0.0)
    try:
        # Unreal pitch/yaw are often in degrees; some builds use 360/65536 units.
        pitch = float(getattr(rot, "Pitch", 0.0) or 0.0)
        yaw = float(getattr(rot, "Yaw", 0.0) or 0.0)
        if abs(pitch) > 360.0 or abs(yaw) > 360.0:
            pitch = pitch * 360.0 / 65536.0
            yaw = yaw * 360.0 / 65536.0
        pitch_r = pitch * math.pi / 180.0
        yaw_r = yaw * math.pi / 180.0
        fx = math.cos(pitch_r) * math.cos(yaw_r)
        fy = math.cos(pitch_r) * math.sin(yaw_r)
        fz = math.sin(pitch_r)
        length = (fx * fx + fy * fy + fz * fz) ** 0.5
        if length < 1e-6:
            return (1.0, 0.0, 0.0)
        return (fx / length, fy / length, fz / length)
    except Exception:
        return (1.0, 0.0, 0.0)


def _zero_move_velocity(move: object | None) -> None:
    if move is None:
        return
    try:
        vel = getattr(move, "Velocity", None)
        if vel is not None:
            setattr(vel, "X", 0.0)
            setattr(vel, "Y", 0.0)
            setattr(vel, "Z", 0.0)
            setattr(move, "Velocity", vel)
            return
    except Exception:
        pass
    try:
        zero = _make_fly_vector(0.0, 0.0, 0.0)
        if zero is not None:
            setattr(move, "Velocity", zero)
    except Exception:
        pass


def _set_move_velocity(move: object | None, x: float, y: float, z: float) -> bool:
    if move is None:
        return False
    try:
        vel = getattr(move, "Velocity", None)
        if vel is not None:
            setattr(vel, "X", float(x))
            setattr(vel, "Y", float(y))
            setattr(vel, "Z", float(z))
            setattr(move, "Velocity", vel)
            return True
    except Exception:
        pass
    try:
        vec = _make_fly_vector(x, y, z)
        if vec is not None:
            setattr(move, "Velocity", vec)
            return True
    except Exception:
        pass
    return False


def _vec3_xyz(obj: object | None) -> tuple[float, float, float]:
    if obj is None:
        return (0.0, 0.0, 0.0)
    try:
        return (
            float(getattr(obj, "X", 0.0) or 0.0),
            float(getattr(obj, "Y", 0.0) or 0.0),
            float(getattr(obj, "Z", 0.0) or 0.0),
        )
    except Exception:
        return (0.0, 0.0, 0.0)


def _vec3_mag(v: tuple[float, float, float]) -> float:
    return (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5


def _vec3_horiz_mag(v: tuple[float, float, float]) -> float:
    return (v[0] * v[0] + v[1] * v[1]) ** 0.5


def _set_move_acceleration(move: object | None, x: float, y: float, z: float) -> None:
    if move is None:
        return
    try:
        accel = getattr(move, "Acceleration", None)
        if accel is not None:
            setattr(accel, "X", float(x))
            setattr(accel, "Y", float(y))
            setattr(accel, "Z", float(z))
            setattr(move, "Acceleration", accel)
            return
    except Exception:
        pass
    try:
        vec = _make_fly_vector(x, y, z)
        if vec is not None:
            setattr(move, "Acceleration", vec)
    except Exception:
        pass


def _force_fly_suppress_engine_fly(pawn: object | None, move: object | None) -> None:
    """Kinematic fly only — bCheatFlying steers on camera pitch and rockets you upward."""
    for obj in (pawn, move):
        if obj is None:
            continue
        try:
            setattr(obj, "bCheatFlying", False)
        except Exception:
            pass
    if move is not None:
        for attr in ("MovementState", "NavAgentProps"):
            try:
                state = getattr(move, attr, None)
                if state is None:
                    continue
                setattr(state, "bCanFly", True)
                setattr(move, attr, state)
            except Exception:
                pass


def _force_fly_enable_can_fly(move: object | None) -> None:
    """Dump: MovementState/NavAgentProps.bCanFly default False."""
    if move is None:
        return
    _force_fly_suppress_engine_fly(None, move)


def _call_vec3(obj: object | None, *names: str) -> tuple[float, float, float]:
    """Pick the strongest dump input vector. Do not return the first zero GetPending()."""
    if obj is None:
        return (0.0, 0.0, 0.0)
    best = (0.0, 0.0, 0.0)
    best_m = 0.0
    for name in names:
        xyz = (0.0, 0.0, 0.0)
        fn = getattr(obj, name, None)
        if callable(fn):
            try:
                xyz = _vec3_xyz(fn())
            except Exception:
                continue
        else:
            try:
                xyz = _vec3_xyz(getattr(obj, name, None))
            except Exception:
                continue
        mag = _vec3_mag(xyz)
        if mag > best_m:
            best = xyz
            best_m = mag
    return best


_FORCE_FLY_JUMP_KEYS: tuple[str, ...] = (
    "SpaceBar",
    "Space",
    "Gamepad_FaceButton_Bottom",
)
_FORCE_FLY_CROUCH_KEYS: tuple[str, ...] = (
    "LeftControl",
    "RightControl",
    "C",
    "Gamepad_FaceButton_Right",
    "Gamepad_LeftThumbstick",
)
_FORCE_FLY_JUMP_AXIS: tuple[str, ...] = (
    "Jump",
    "IA_Jump",
    "GbxJump",
    "Action_Jump",
    "MoveUp",
)
_FORCE_FLY_CROUCH_AXIS: tuple[str, ...] = (
    "Crouch",
    "IA_Crouch",
    "GbxCrouch",
    "Action_Crouch",
    "MoveDown",
    "Slide",
)
_FORCE_FLY_JUMP_ACTIONS: tuple[str, ...] = (
    "Jump",
    "IA_Jump",
    "Action_Jump",
    "GbxJump",
)
_FORCE_FLY_CROUCH_ACTIONS: tuple[str, ...] = (
    "Crouch",
    "IA_Crouch",
    "Action_Crouch",
    "GbxCrouch",
    "Slide",
)


def _input_key_down(pc: object | None, key_name: str) -> bool:
    if pc is None:
        return False
    try:
        key = unrealsdk.make_struct("Key", KeyName=str(key_name))
        fn = getattr(pc, "IsInputKeyDown", None)
        if callable(fn) and bool(fn(key)):
            return True
    except Exception:
        pass
    pi = getattr(pc, "PlayerInput", None)
    if pi is not None:
        try:
            key = unrealsdk.make_struct("Key", KeyName=str(key_name))
            for meth in ("IsPressed", "GetKeyValue"):
                fn = getattr(pi, meth, None)
                if not callable(fn):
                    continue
                result = fn(key)
                if isinstance(result, (int, float)) and float(result) > 0.01:
                    return True
                if bool(result):
                    return True
        except Exception:
            pass
    return False


def _force_fly_axis_value(obj: object | None, names: tuple[str, ...]) -> float:
    if obj is None:
        return 0.0
    fn = getattr(obj, "GetInputAxisValue", None)
    if not callable(fn):
        return 0.0
    best = 0.0
    for name in names:
        try:
            val = float(fn(name) or 0.0)
            if abs(val) > abs(best):
                best = val
        except Exception:
            continue
    return best


def _force_fly_action_value(obj: object | None, names: tuple[str, ...]) -> float:
    if obj is None:
        return 0.0
    best = 0.0
    fn_vec = getattr(obj, "GetInputVectorAxisValue", None)
    if callable(fn_vec):
        for name in names:
            try:
                vec = _vec3_xyz(fn_vec(name))
                pick = vec[2] if abs(vec[2]) >= max(abs(vec[0]), abs(vec[1])) else vec[1]
                if abs(pick) > abs(best):
                    best = pick
            except Exception:
                continue
    for attr in ("InputComponent", "PawnInputComponent"):
        try:
            comp = getattr(obj, attr, None)
        except Exception:
            comp = None
        if comp is None:
            continue
        bound = getattr(comp, "GetBoundActionValue", None)
        if not callable(bound):
            continue
        for name in names:
            try:
                raw = bound(name)
                if isinstance(raw, (int, float)):
                    val = float(raw)
                else:
                    vec = _vec3_xyz(raw)
                    val = vec[2] if abs(vec[2]) >= max(abs(vec[0]), abs(vec[1])) else vec[1]
                if abs(val) > abs(best):
                    best = val
            except Exception:
                continue
    return best


def _force_fly_control_z(pawn: object | None, move: object | None) -> float:
    best = 0.0
    for obj, names in (
        (
            pawn,
            (
                "GetPendingMovementInputVector",
                "GetLastMovementInputVector",
                "ControlInputVector",
                "LastControlInputVector",
            ),
        ),
        (
            move,
            (
                "GetPendingInputVector",
                "GetLastInputVector",
                "ControlInputVector",
                "LastControlInputVector",
            ),
        ),
    ):
        vec = _call_vec3(obj, *names)
        z = float(vec[2])
        if abs(z) > abs(best):
            best = z
    return best


def _force_fly_vertical_input(pc: object | None, pawn: object | None, move: object | None) -> float:
    """World up/down from jump/crouch keys and axes — not camera pitch."""
    up = 0.0
    for key in _FORCE_FLY_JUMP_KEYS:
        if _input_key_down(pc, key):
            up += 1.0
            break
    for key in _FORCE_FLY_CROUCH_KEYS:
        if _input_key_down(pc, key):
            up -= 1.0
            break
    for obj in (pc, pawn):
        jump_axis = _force_fly_axis_value(obj, _FORCE_FLY_JUMP_AXIS)
        if jump_axis > 0.05:
            up += min(1.0, jump_axis)
        crouch_axis = _force_fly_axis_value(obj, _FORCE_FLY_CROUCH_AXIS)
        if crouch_axis > 0.05:
            up -= min(1.0, crouch_axis)
        jump_act = _force_fly_action_value(obj, _FORCE_FLY_JUMP_ACTIONS)
        if jump_act > 0.05:
            up += min(1.0, jump_act)
        crouch_act = _force_fly_action_value(obj, _FORCE_FLY_CROUCH_ACTIONS)
        if crouch_act > 0.05:
            up -= min(1.0, crouch_act)
    control_z = _force_fly_control_z(pawn, move)
    if abs(control_z) >= 0.2:
        up += max(-1.0, min(1.0, control_z))
    for obj in (pawn, move):
        if obj is None:
            continue
        for flag in ("bPressedJump", "bWasJumping"):
            try:
                if bool(getattr(obj, flag, False)):
                    up += 1.0
                    break
            except Exception:
                pass
        for flag in ("bWantsToCrouch", "bIsCrouched"):
            try:
                if bool(getattr(obj, flag, False)):
                    up -= 1.0
                    break
            except Exception:
                pass
    if up > 1.0:
        return 1.0
    if up < -1.0:
        return -1.0
    if abs(up) < 0.05:
        return 0.0
    return up


def _force_fly_consume_walk_input(pawn: object | None, move: object | None) -> None:
    """Stop CMC PhysWalking from also applying the same WASD (dump GetPendingInputVector)."""
    for obj, meth in (
        (move, "ConsumeInputVector"),
        (pawn, "ConsumeMovementInputVector"),
    ):
        if obj is None:
            continue
        fn = getattr(obj, meth, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass


def _force_fly_input_xy(
    pawn: object | None,
    move: object | None,
    pc: object | None = None,
) -> tuple[str, float, float] | None:
    """Return ('planar', right, forward) or ('world', hx, hy). Never Acceleration."""
    planar = (0.0, 0.0)
    planar_m = 0.0
    space = (0.0, 0.0)
    space_m = 0.0

    def _consider_planar(x: float, y: float) -> None:
        nonlocal planar, planar_m
        mag = (x * x + y * y) ** 0.5
        if mag > planar_m:
            planar = (float(x), float(y))
            planar_m = mag

    def _consider_space(xyz: tuple[float, float, float]) -> None:
        nonlocal space, space_m
        mag = _vec3_horiz_mag(xyz)
        if mag > space_m:
            space = (float(xyz[0]), float(xyz[1]))
            space_m = mag

    for obj, names in (
        (
            pawn,
            (
                "GetPendingMovementInputVector",
                "GetLastMovementInputVector",
                "ControlInputVector",
                "LastControlInputVector",
            ),
        ),
        (
            move,
            (
                "GetPendingInputVector",
                "GetLastInputVector",
                "ControlInputVector",
                "LastControlInputVector",
            ),
        ),
    ):
        _consider_space(_call_vec3(obj, *names))

    for obj in (pc, pawn):
        if obj is None:
            continue
        fn = getattr(obj, "GetInputVectorAxisValue", None)
        if callable(fn):
            for name in ("Move", "Action_Move", "IA_Move", "Move2D", "GbxMove"):
                try:
                    vec = _vec3_xyz(fn(name))
                    _consider_planar(vec[0], vec[1])
                except Exception:
                    continue
        fn_a = getattr(obj, "GetInputAxisValue", None)
        if callable(fn_a):
            fwd = 0.0
            right = 0.0
            for name in ("MoveForward", "GbxMoveForward", "IA_MoveForward"):
                try:
                    fwd = float(fn_a(name) or 0.0)
                    if abs(fwd) >= 0.02:
                        break
                except Exception:
                    continue
            for name in ("MoveRight", "GbxMoveRight", "IA_MoveRight"):
                try:
                    right = float(fn_a(name) or 0.0)
                    if abs(right) >= 0.02:
                        break
                except Exception:
                    continue
            if abs(fwd) >= 0.02 or abs(right) >= 0.02:
                _consider_planar(right, fwd)
        for attr in ("InputComponent", "PawnInputComponent"):
            try:
                comp = getattr(obj, attr, None)
            except Exception:
                comp = None
            if comp is None:
                continue
            bound = getattr(comp, "GetBoundActionValue", None)
            if not callable(bound):
                continue
            for name in ("Action_Move", "Move"):
                try:
                    vec = _vec3_xyz(bound(name))
                    _consider_planar(vec[0], vec[1])
                except Exception:
                    continue
    if planar_m >= 0.05:
        return ("planar", planar[0], planar[1])
    if space_m >= 0.05:
        return ("world", space[0], space[1])
    return None


def _force_fly_raw_input_vector(
    pawn: object | None,
    move: object | None,
    pc: object | None = None,
) -> tuple[float, float, float]:
    """Legacy tuple for callers that only need a direction hint."""
    inp = _force_fly_input_xy(pawn, move, pc)
    if inp is None:
        return (0.0, 0.0, 0.0)
    mode, x, y = inp
    if mode == "planar":
        return (x, y, 0.0)
    mag = (x * x + y * y) ** 0.5
    if mag < 1e-6:
        return (0.0, 0.0, 0.0)
    return (x / mag, y / mag, 0.0)


def _force_fly_wish_dir(
    pc: object | None,
    pawn: object | None,
    move: object | None,
) -> tuple[float, float, float] | None:
    """WASD = yaw-relative horizontal. Space/jump up, Ctrl/crouch down (not look pitch)."""
    inp = _force_fly_input_xy(pawn, move, pc)
    up = _force_fly_vertical_input(pc, pawn, move)
    if inp is None:
        if abs(up) < 0.02:
            return None
        dz = 1.0 if up > 0.0 else -1.0
        return (0.0, 0.0, dz)
    mode, ix, iy = inp
    if mode == "planar":
        fwd_h, right_h = _control_yaw_forward_right(pc, pawn)
        strf = float(ix)
        fwd = float(iy)
        dx = fwd_h[0] * fwd + right_h[0] * strf
        dy = fwd_h[1] * fwd + right_h[1] * strf
    else:
        horiz = (ix * ix + iy * iy) ** 0.5
        if horiz < 1e-6:
            dx = dy = 0.0
        else:
            dx = float(ix) / horiz
            dy = float(iy) / horiz
    dz = up
    if abs(dx) < 0.02 and abs(dy) < 0.02 and abs(dz) < 0.02:
        return None
    mag = (dx * dx + dy * dy + dz * dz) ** 0.5
    if mag < 1e-6:
        return None
    return (dx / mag, dy / mag, dz / mag)


def _force_fly_input_throttle(pawn: object, move: object | None, pc: object | None = None) -> bool:
    if _force_fly_wish_dir(pc, pawn, move) is not None:
        return True
    if abs(_force_fly_vertical_input(pc, pawn, move)) >= 0.05:
        return True
    return False


def _force_fly_pawn_key(pawn: object) -> str:
    try:
        return str(int(pawn._get_address()))
    except Exception:
        return str(id(pawn))


def _remember_force_fly_safe(pawn: object, x: float, y: float, z: float) -> None:
    key = _force_fly_pawn_key(pawn)
    prev = _force_fly_safe_anchor.get(key)
    if prev is None or float(z) >= float(prev[2]) - 40.0:
        _force_fly_safe_anchor[key] = (float(x), float(y), float(z))


def _recover_force_fly_safe(pawn: object, *, lift: float = 72.0) -> bool:
    key = _force_fly_pawn_key(pawn)
    safe = _force_fly_safe_anchor.get(key)
    if safe is None:
        return False
    cur = _pawn_world_location(pawn)
    if cur is None:
        return False
    if float(cur[2]) >= float(safe[2]) - 90.0:
        return False
    return bool(
        _set_pawn_world_location(
            pawn,
            float(safe[0]),
            float(safe[1]),
            max(float(safe[2]), float(cur[2])) + float(lift),
            sweep=True,
        )
    )


def _force_fly_use_sweep() -> bool:
    """Stop on floors/walls unless the user explicitly disabled collision."""
    return not get_noclip_enabled() and not get_fall_through_map_enabled()


def _force_fly_kinematic_sweep(speed: float) -> bool:
    """Sweep for Cruise/Fast; custom speeds above threshold skip sweep."""
    if not _force_fly_use_sweep():
        return False
    return float(speed) < _FLY_KINEMATIC_NOSWEEP_SPEED


def _force_fly_is_grounded(move: object | None) -> bool:
    """Dump: IsMovingOnGround / IsWalking / CurrentFloor — landing snaps to walk and glues you."""
    if move is None:
        return False
    for meth in ("IsMovingOnGround", "IsWalking"):
        fn = getattr(move, meth, None)
        if callable(fn):
            try:
                if bool(fn()):
                    return True
            except Exception:
                pass
    try:
        mode = getattr(move, "MovementMode", None)
        try:
            mode_i = int(mode) if mode is not None else -1
        except Exception:
            mode_i = int(getattr(mode, "value", -1) or -1)
        if mode_i in (1, 2):  # Walking / NavWalking
            return True
    except Exception:
        pass
    try:
        floor = getattr(move, "CurrentFloor", None)
        if floor is not None and bool(getattr(floor, "bBlockingHit", False)):
            dist = float(getattr(floor, "FloorDist", 999.0) or 999.0)
            if dist < 60.0:
                return True
    except Exception:
        pass
    return False


def _force_fly_movement_mode_i(move: object | None) -> int:
    if move is None:
        return -1
    try:
        mode = getattr(move, "MovementMode", None)
        try:
            return int(mode) if mode is not None else -1
        except Exception:
            return int(getattr(mode, "value", -1) or -1)
    except Exception:
        return -1


def _force_fly_set_mode_flying(move: object | None) -> None:
    if move is None:
        return
    try:
        # Dump DefaultLandMovementMode=1 is why landing sticks you in walk under force-fly.
        setattr(move, "DefaultLandMovementMode", 5)
        setattr(move, "GroundMovementMode", 5)
    except Exception:
        pass
    if _force_fly_movement_mode_i(move) in (3, 5, 6):
        return
    setter = getattr(move, "SetMovementMode", None)
    if callable(setter):
        try:
            setter(5, 0)
        except TypeError:
            try:
                setter(5)
            except Exception:
                pass
        except Exception:
            pass


def _pawn_add_world_offset(
    pawn: object,
    ox: float,
    oy: float,
    oz: float,
    *,
    sweep: bool = True,
) -> bool:
    delta = _make_fly_vector(ox, oy, oz)
    if delta is None or pawn is None:
        return False
    for meth in ("K2_AddActorWorldOffset", "AddActorWorldOffset"):
        fn = getattr(pawn, meth, None)
        if not callable(fn):
            continue
        try:
            if bool(fn(delta, bool(sweep), None, True)):
                return True
        except TypeError:
            try:
                if bool(fn(delta, bool(sweep))):
                    return True
            except Exception:
                continue
        except Exception:
            continue
    cur = _pawn_world_location(pawn)
    if cur is None:
        return False
    return _set_pawn_world_location(
        pawn,
        cur[0] + ox,
        cur[1] + oy,
        cur[2] + oz,
        sweep=sweep,
    )


def _force_fly_move_budget(speed: float, dt: float, *, use_sweep: bool) -> tuple[float, float, int]:
    """Distance, sub-step size, and max sub-steps for one fly tick (scales with speed)."""
    speed = max(300.0, float(speed or 0.0))
    # Use real frame dt (capped). Do NOT floor to 1/45 — that inflated Cruise/Fast when the
    # HUD tick ran faster than 45 Hz and made "cruise" feel like sprint-zoom.
    dt = min(max(float(dt or 0.016), 1.0 / 120.0), 0.1)
    max_dist = speed * dt
    if not use_sweep:
        boost = 1.0 + min(0.85, speed / 120000.0)
        max_dist *= boost
        step = max(500.0, min(96000.0, max_dist))
        return max_dist, step, 1
    # Safe fly: small sweep steps so floor hits do not zero out the whole tick.
    step_cap = 220.0 if speed >= 8000.0 else 420.0
    step = max(80.0, min(step_cap, max(max_dist * 0.35, speed * 0.012)))
    max_steps = max(1, min(64, int(math.ceil(max_dist / max(step, 1.0)) + 2)))
    return max_dist, step, max_steps


def _drive_force_fly(
    pc: object | None,
    pawn: object,
    move: object | None,
    *,
    speed: float | None = None,
    dt: float = 0.016,
    remote: bool = False,
) -> bool:
    """Look-relative kinematic fly. Always uses the committed force_fly_speed global."""
    if not _uobject_live(pawn):
        return False
    if move is not None and not _uobject_live(move):
        move = None
    tick_speed = clamp_force_fly_speed(force_fly_speed if speed is None else speed)
    use_sweep = False if remote else _force_fly_kinematic_sweep(tick_speed)
    try:
        if move is not None:
            setattr(move, "GravityScale", 0.0)
            setattr(move, "MaxFlySpeed", tick_speed)
            setattr(move, "MaxCustomMovementSpeed", tick_speed)
    except Exception:
        pass
    eff_dt = min(max(float(dt or 0.016), 1.0 / 120.0), 0.1)
    wish = _force_fly_wish_dir(pc, pawn, move)
    key = _force_fly_pawn_key(pawn)
    now = time.monotonic()
    # Oak sometimes blanks ControlInput for a frame while keys are held — keep coasting briefly.
    if wish is not None:
        _force_fly_last_wish[key] = (wish, now)
    else:
        held = _force_fly_last_wish.get(key)
        if held is not None and (now - float(held[1])) <= _FORCE_FLY_WISH_HOLD_SEC:
            wish = held[0]
        else:
            _force_fly_last_wish.pop(key, None)
    if remote:
        # Party remotes: read replicated PC input — never ConsumeInputVector (freezes them).
        try:
            setattr(pawn, "bCheatFlying", False)
            if move is not None:
                setattr(move, "bCheatFlying", False)
        except Exception:
            pass
    else:
        _force_fly_consume_walk_input(pawn, move)
        _force_fly_suppress_engine_fly(pawn, move)
    if wish is None:
        _zero_move_velocity(move)
        return False
    dx, dy, dz = wish
    horiz_steer = (dx * dx + dy * dy) ** 0.5
    if use_sweep and move is not None and _force_fly_is_grounded(move):
        _force_fly_set_mode_flying(move)
        # Liftoff only when idle on the floor — not while steering forward/strafe.
        last_lift = float(_force_fly_liftoff_at.get(key, 0.0) or 0.0)
        if horiz_steer < 0.2 and (now - last_lift) >= _FORCE_FLY_LIFTOFF_COOLDOWN_SEC:
            cur0 = _pawn_world_location(pawn)
            if cur0 is not None:
                lifted = _set_pawn_world_location(
                    pawn,
                    cur0[0],
                    cur0[1],
                    float(cur0[2]) + _FORCE_FLY_LIFTOFF_Z,
                    sweep=False,
                )
                if not lifted:
                    _pawn_add_world_offset(pawn, 0.0, 0.0, _FORCE_FLY_LIFTOFF_Z, sweep=False)
                _force_fly_liftoff_at[key] = now
    mag = (dx * dx + dy * dy + dz * dz) ** 0.5
    if mag < 1e-6:
        return False
    dx, dy, dz = dx / mag, dy / mag, dz / mag
    max_dist, step_size, max_steps = _force_fly_move_budget(tick_speed, eff_dt, use_sweep=use_sweep)
    cur = _pawn_world_location(pawn)
    if cur is None:
        return False
    start_x, start_y, start_z = float(cur[0]), float(cur[1]), float(cur[2])
    _remember_force_fly_safe(pawn, start_x, start_y, start_z)
    moved = False
    if not use_sweep:
        moved = _pawn_add_world_offset(
            pawn,
            dx * max_dist,
            dy * max_dist,
            dz * max_dist,
            sweep=False,
        )
    else:
        remaining = max_dist
        steps = 0
        while remaining > 0.5 and steps < max_steps:
            seg = min(remaining, step_size)
            remaining -= seg
            steps += 1
            cur = _pawn_world_location(pawn)
            if cur is None:
                break
            ok = _pawn_add_world_offset(
                pawn,
                dx * seg,
                dy * seg,
                dz * seg,
                sweep=True,
            )
            if ok:
                moved = True
                after = _pawn_world_location(pawn)
                if after is not None:
                    _remember_force_fly_safe(pawn, after[0], after[1], after[2])
            else:
                # Big sweep steps often fail on floors — try kinematic segment before stopping.
                ok2 = _pawn_add_world_offset(
                    pawn,
                    dx * seg,
                    dy * seg,
                    dz * seg,
                    sweep=False,
                )
                if ok2:
                    moved = True
                    after = _pawn_world_location(pawn)
                    if after is not None:
                        _remember_force_fly_safe(pawn, after[0], after[1], after[2])
                    continue
                # Floor/wall clip — tiny vertical nudge only when not steering horizontally.
                bumped = False
                if horiz_steer < 0.15:
                    bumped = _pawn_add_world_offset(pawn, 0.0, 0.0, 18.0, sweep=False)
                if bumped:
                    ok2 = _pawn_add_world_offset(
                        pawn,
                        dx * seg,
                        dy * seg,
                        max(dz, 0.0) * seg,
                        sweep=False,
                    )
                    if ok2:
                        moved = True
                        after = _pawn_world_location(pawn)
                        if after is not None:
                            _remember_force_fly_safe(pawn, after[0], after[1], after[2])
                        continue
                break
    _zero_move_velocity(move)
    if use_sweep and moved:
        after = _pawn_world_location(pawn)
        # Only unstick if we barely moved horizontally (scraping the floor), not every land.
        if (
            horiz_steer < 0.2
            and after is not None
            and move is not None
            and _force_fly_is_grounded(move)
        ):
            hx = float(after[0]) - start_x
            hy = float(after[1]) - start_y
            if (hx * hx + hy * hy) < 100.0 and float(after[2]) < start_z + 16.0:
                last_lift = float(_force_fly_liftoff_at.get(key, 0.0) or 0.0)
                if (now - last_lift) >= _FORCE_FLY_LIFTOFF_COOLDOWN_SEC:
                    lifted = _set_pawn_world_location(
                        pawn,
                        after[0],
                        after[1],
                        max(float(after[2]), start_z) + _FORCE_FLY_LIFTOFF_Z,
                        sweep=False,
                    )
                    if lifted:
                        _force_fly_liftoff_at[key] = now
                        after2 = _pawn_world_location(pawn)
                        if after2 is not None:
                            _remember_force_fly_safe(pawn, after2[0], after2[1], after2[2])
        after = _pawn_world_location(pawn)
        if after is not None and float(after[2]) < start_z - 120.0:
            _recover_force_fly_safe(pawn)
    return moved


def _raise_world_fly_altitude(*, force: bool = False) -> None:
    """Dump MaxFlyAltitude=5000 caps midair. Cache — never find_all every tick (that lagged the game)."""
    global _force_fly_altitude_until
    now = time.monotonic()
    if not force and now < _force_fly_altitude_until:
        return
    _force_fly_altitude_until = now + 8.0
    try:
        worlds = list(unrealsdk.find_all("OakWorldSettings", False) or [])
    except Exception:
        worlds = []
    for ws in worlds:
        try:
            setattr(ws, "MaxFlyAltitude", 5000000.0)
        except Exception:
            continue


def _cheat_manager_set_fly(pc: object | None, enabled: bool) -> None:
    """Prefer CheatManager.Fly/Walk — ClientCheatFly alone often snaps back to walk."""
    if pc is None:
        return
    try:
        from .movement_adjustments import _ensure_cheat_manager

        cm = _ensure_cheat_manager(pc)
    except Exception:
        cm = getattr(pc, "CheatManager", None)
    if cm is None:
        return
    fn = getattr(cm, "Fly" if enabled else "Walk", None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


def _stamp_force_fly_speed(
    pawn: object,
    move: object | None,
    *,
    local_target: bool = True,
    pc: object | None = None,
    dt: float = 0.016,
) -> int:
    """Stamp MaxFlySpeed every tick + kinematic WASD steps on the local pawn."""
    global _force_fly_maintain_until
    if not _uobject_live(pawn):
        return 0
    if move is not None and not _uobject_live(move):
        move = None
    moves = [m for m in _movement_components_for_pawn(pawn) if _uobject_live(m)]
    if move is not None and id(move) not in {id(m) for m in moves}:
        moves.insert(0, move)
    if not moves:
        return 0
    fly_speed, fly_accel, fly_brake = _fly_motion_params()
    writes = 0
    primary = moves[0]
    now = time.monotonic()
    if not local_target:
        maintain_key = _force_fly_pawn_key(pawn)
        if now >= float(_force_fly_maintain_until_by_key.get(maintain_key, 0.0) or 0.0):
            _force_fly_maintain_until_by_key[maintain_key] = now + 0.4
            _raise_world_fly_altitude(force=False)
            for comp in moves:
                for attr, value in (
                    ("GravityScale", 0.0),
                    ("MaxFlySpeed", fly_speed),
                    ("MaxCustomMovementSpeed", fly_speed),
                    ("MaxAcceleration", fly_accel),
                    ("BrakingDecelerationFlying", fly_brake),
                    ("bCheatFlying", False),
                    ("BrakingDecelerationFalling", 0.0),
                    ("GroundFriction", 0.0),
                    ("AirControl", 1.0),
                    ("FallingLateralFriction", 0.0),
                    ("Friction", 0.0),
                    ("DefaultLandMovementMode", 5),
                    ("GroundMovementMode", 5),
                    ("NetworkSmoothingMode", 2),
                    ("bAlwaysCheckFloor", False),
                    ("bForceNextFloorCheck", False),
                    ("bEnablePhysicsInteraction", False),
                ):
                    try:
                        setattr(comp, attr, value)
                        writes += 1
                    except Exception:
                        pass
                _force_fly_enable_can_fly(comp)
                _force_fly_set_mode_flying(comp)
            try:
                setattr(pawn, "GravityScale", 0.0)
                setattr(pawn, "bCheatFlying", False)
                writes += 2
            except Exception:
                pass
        else:
            try:
                setattr(primary, "GravityScale", 0.0)
                setattr(primary, "MaxFlySpeed", fly_speed)
                setattr(primary, "MaxCustomMovementSpeed", fly_speed)
                writes += 3
            except Exception:
                pass
        return writes
    for comp in moves:
        try:
            setattr(comp, "MaxFlySpeed", fly_speed)
            setattr(comp, "MaxCustomMovementSpeed", fly_speed)
            writes += 2
        except Exception:
            pass
    if now >= _force_fly_maintain_until:
        _force_fly_maintain_until = now + 0.4
        for comp in moves:
            for attr, value in (
                ("GravityScale", 0.0),
                ("MaxFlySpeed", fly_speed),
                ("MaxCustomMovementSpeed", fly_speed),
                ("MaxAcceleration", fly_accel),
                ("BrakingDecelerationFlying", fly_brake),
                ("bCheatFlying", False),
                ("BrakingDecelerationFalling", 0.0),
                ("GroundFriction", 0.0),
                ("AirControl", 1.0),
                ("DefaultLandMovementMode", 5),
                ("GroundMovementMode", 5),
                ("NetworkSmoothingMode", 0),
                ("bAlwaysCheckFloor", False),
                ("bForceNextFloorCheck", False),
                ("bEnablePhysicsInteraction", False),
            ):
                try:
                    setattr(comp, attr, value)
                    writes += 1
                except Exception:
                    pass
            if local_target:
                for attr, value in (
                    ("FlyingSpeed", fly_speed),
                    ("FlySpeed", fly_speed),
                    ("MaxWalkSpeed", fly_speed),
                    ("Friction", 0.0),
                    ("FallingLateralFriction", 0.0),
                ):
                    try:
                        setattr(comp, attr, value)
                        writes += 1
                    except Exception:
                        pass
            _force_fly_enable_can_fly(comp)
            _force_fly_set_mode_flying(comp)
        try:
            setattr(pawn, "GravityScale", 0.0)
            setattr(pawn, "bCheatFlying", False)
            writes += 2
        except Exception:
            pass
        _raise_world_fly_altitude(force=False)
    else:
        try:
            setattr(primary, "GravityScale", 0.0)
            setattr(primary, "MaxFlySpeed", fly_speed)
        except Exception:
            pass
    if local_target:
        if pc is None:
            try:
                pc = getattr(pawn, "Controller", None)
            except Exception:
                pc = None
        if _drive_force_fly(pc, pawn, primary, speed=fly_speed, dt=dt):
            writes += 1
    return writes


def _force_fly_still_active(pawn: object, move: object | None) -> bool:
    """True when gravity is already off for force-fly."""
    del pawn
    try:
        gravity = float(getattr(move, "GravityScale", 1.0) or 1.0)
        return abs(gravity) <= 0.08
    except Exception:
        return False


def _pawn_has_mobility_poison(pawn: object, move: object | None) -> bool:
    """Stale fly / low-gravity / fly-mode fields on a pawn that should be walking."""
    if _force_fly_still_active(pawn, move):
        return True
    try:
        grav = float(getattr(pawn, "GravityScale", 1.0) or 1.0)
        if grav < 0.92:
            return True
    except Exception:
        pass
    try:
        jmc = int(getattr(pawn, "JumpMaxCount", 2) or 2)
        if jmc > 10:
            return True
    except Exception:
        pass
    if move is not None:
        try:
            mode = getattr(move, "MovementMode", None)
            if mode is not None and int(mode) == 5:
                return True
        except Exception:
            pass
        try:
            bdf = float(getattr(move, "BrakingDecelerationFalling", 2000.0) or 2000.0)
            ac = float(getattr(move, "AirControl", 0.35) or 0.35)
            if bdf < 150.0 and ac > 0.85:
                return True
        except Exception:
            pass
        try:
            mfs = float(getattr(move, "MaxFlySpeed", 600.0) or 600.0)
            grav = float(getattr(move, "GravityScale", 1.0) or 1.0)
            if mfs > 5000.0 and grav < 0.5:
                return True
        except Exception:
            pass
    try:
        if bool(getattr(pawn, "bCheatFlying", False)):
            return True
        if move is not None and bool(getattr(move, "bCheatFlying", False)):
            return True
    except Exception:
        pass
    return False


def _ensure_remote_cheat_fly(pc: object | None, pawn: object, *, enabled: bool) -> None:
    """Latch CheatManager fly once on party remotes — never toggle every tick (freezes)."""
    if not _uobject_live(pawn):
        return
    key = _force_fly_pawn_key(pawn)
    if enabled:
        if key in _remote_cheat_fly_latched:
            return
        _cheat_manager_set_fly(pc, True)
        _remote_cheat_fly_latched.add(key)
        return
    if key not in _remote_cheat_fly_latched:
        return
    _cheat_manager_set_fly(pc, False)
    _remote_cheat_fly_latched.discard(key)


def _apply_remote_force_fly_on(pc: object, pawn: object, move: object | None) -> int:
    """Party remotes: CheatManager fly + speed stamp (host kinematic drive freezes them)."""
    if not _uobject_live(pawn):
        return 0
    global _force_fly_maintain_until_by_key
    _force_fly_maintain_until_by_key.pop(_force_fly_pawn_key(pawn), None)
    _ensure_remote_cheat_fly(pc, pawn, enabled=True)
    _raise_world_fly_altitude(force=True)
    writes = _stamp_force_fly_speed(pawn, move, local_target=False, pc=pc, dt=0.016)
    try:
        cur = _pawn_world_location(pawn)
        if cur is not None and move is not None and _force_fly_is_grounded(move):
            if _set_pawn_world_location(
                pawn,
                cur[0],
                cur[1],
                float(cur[2]) + 36.0,
                sweep=False,
            ):
                writes += 1
    except Exception:
        pass
    return max(writes, 1)


def _apply_force_fly(
    pc: object,
    pawn: object,
    move: object | None,
    enabled: bool,
    restore: dict[str, Any] | None = None,
    *,
    local_target: bool = True,
) -> int:
    global _force_fly_maintain_until
    if not _uobject_live(pawn):
        return 0
    moves = [m for m in _movement_components_for_pawn(pawn) if _uobject_live(m)]
    if move is not None and id(move) not in {id(m) for m in moves}:
        moves.insert(0, move)
    if not moves:
        return 0
    writes = 0
    failures = 0
    if enabled:
        if not local_target:
            return _apply_remote_force_fly_on(pc, pawn, move)
        # Dump MaxFlySpeed=600 — Oak clamps CMC fly. Kinematic steps, no ClientCheatFly.
        _force_fly_maintain_until = 0.0
        _raise_world_fly_altitude(force=True)
        for obj in (pawn, *moves):
            try:
                setattr(obj, "GravityScale", 0.0)
                writes += 1
            except Exception:
                failures += 1
        for comp in moves:
            _force_fly_enable_can_fly(comp)
            for attr, value in (
                ("GravityScale", 0.0),
                ("bCheatFlying", False),
                ("BrakingDecelerationFlying", 0.0),
                ("BrakingDecelerationFalling", 0.0),
                ("GroundFriction", 0.0),
                ("AirControl", 1.0),
                ("FallingLateralFriction", 0.0),
                ("Friction", 0.0),
                ("DefaultLandMovementMode", 5),
                ("GroundMovementMode", 5),
                ("NetworkSmoothingMode", 0),
                ("bAlwaysCheckFloor", False),
                ("bEnablePhysicsInteraction", False),
            ):
                try:
                    setattr(comp, attr, value)
                    writes += 1
                except Exception:
                    failures += 1
            _force_fly_set_mode_flying(comp)
            writes += 1
        try:
            cur = _pawn_world_location(pawn)
            if cur is not None and _force_fly_is_grounded(move):
                _set_pawn_world_location(
                    pawn,
                    cur[0],
                    cur[1],
                    cur[2] + 36.0,
                    sweep=_force_fly_use_sweep(),
                )
                writes += 1
        except Exception:
            pass
        writes += _stamp_force_fly_speed(pawn, move, local_target=local_target, pc=pc, dt=0.016)
        return writes
    saved = _sanitize_force_fly_restore(restore)
    if not local_target:
        _ensure_remote_cheat_fly(pc, pawn, enabled=False)
        client_fn = getattr(pawn, "ClientCheatWalk", None)
        if callable(client_fn):
            try:
                client_fn()
                writes += 1
            except Exception:
                pass
    elif local_target:
        _cheat_manager_set_fly(pc, False)
        _cheat_manager_set_fly(pc, False)
        client_fn = getattr(pawn, "ClientCheatWalk", None)
        if callable(client_fn):
            try:
                client_fn()
                writes += 1
            except Exception:
                pass
            try:
                client_fn()
                writes += 1
            except Exception:
                pass
        # Force-fly OFF must not leave host noclip / fall-through active.
        try:
            if get_noclip_enabled():
                set_noclip_enabled(False)
                apply_noclip()
        except Exception:
            pass
    # Mirror every field Force Fly ON writes so walk restores cleanly.
    for obj in (pawn, *moves):
        for attr, default in (
            ("bCheatFlying", False),
            ("GravityScale", 1.0),
            ("BrakingDecelerationFlying", 0.0),
            ("BrakingDecelerationFalling", 2000.0),
            ("GroundFriction", 8.0),
            ("AirControl", 0.35),
            ("FallingLateralFriction", 0.0),
            ("Friction", 8.0),
            ("DefaultLandMovementMode", 1),
            ("GroundMovementMode", 1),
            ("NetworkSmoothingMode", 2),
            ("bAlwaysCheckFloor", True),
            ("bEnablePhysicsInteraction", True),
        ):
            try:
                setattr(obj, attr, default)
                writes += 1
            except Exception:
                failures += 1
    # Always hard-reset walk speeds even when no snapshot exists (fixes stuck guests/host).
    default_restore = {
        "move.MaxWalkSpeed": 600.0,
        "move.MinAnalogWalkSpeed": 20.0,
        "move.MaxAcceleration": 2048.0,
        "move.BrakingDecelerationWalking": 2048.0,
        "move.BrakingDecelerationFlying": 0.0,
        "move.AirControl": 0.35,
        "move.Friction": 8.0,
        "move.GroundFriction": 8.0,
        "move.DefaultLandMovementMode": 1,
        "move.GroundMovementMode": 1,
        "move.MovementMode": 1,
        "move.NetworkSmoothingMode": 2,
        "move.bAlwaysCheckFloor": True,
        "move.bEnablePhysicsInteraction": True,
        "pawn.bCheatFlying": False,
        "move.GravityScale": 1.0,
    }
    merged = dict(default_restore)
    # Prefer sane walk defaults over any fly-poisoned snapshot values.
    for key, value in saved.items():
        if key in ("_pawn_id", "_move_id"):
            continue
        if key in ("move.GravityScale", "pawn.bCheatFlying", "state.bCanFly"):
            continue
        merged[key] = value
    merged["move.GravityScale"] = 1.0
    merged["pawn.bCheatFlying"] = False
    merged["state.bCanFly"] = False
    values = tuple(
        (pawn if prefix == "pawn" else move, attr, value)
        for key, value in merged.items()
        if "." in key and (prefix := key.split(".", 1)[0]) in {"pawn", "move"}
        and (attr := key.split(".", 1)[1]) != "MovementMode"
    )
    for obj, attr, value in values:
        if obj is None:
            continue
        try:
            setattr(obj, attr, value)
            writes += 1
        except Exception:
            failures += 1
    for comp in moves:
        try:
            state = getattr(comp, "MovementState", None)
            if state is not None:
                state_value = merged.get("state.bCanFly", False)
                setattr(state, "bCanFly", state_value)
                writes += 1
        except Exception:
            failures += 1
        setter = getattr(comp, "SetMovementMode", None)
        if callable(setter):
            mode = merged.get("move.MovementMode", 1)
            try:
                setter(mode, 0)
                writes += 1
            except TypeError:
                try:
                    setter(mode)
                    writes += 1
                except Exception:
                    failures += 1
            except Exception:
                failures += 1
        # Apply walk defaults onto every movement component, not only primary `move`.
        for attr, value in (
            ("MaxWalkSpeed", merged.get("move.MaxWalkSpeed", 600.0)),
            ("MinAnalogWalkSpeed", merged.get("move.MinAnalogWalkSpeed", 20.0)),
            ("MaxFlySpeed", 600.0),
            ("GroundFriction", 8.0),
            ("GravityScale", 1.0),
            ("bCheatFlying", False),
            ("NetworkSmoothingMode", merged.get("move.NetworkSmoothingMode", 2)),
            ("bAlwaysCheckFloor", True),
            ("bEnablePhysicsInteraction", True),
            ("DefaultLandMovementMode", 1),
            ("GroundMovementMode", 1),
        ):
            try:
                setattr(comp, attr, value)
                writes += 1
            except Exception:
                failures += 1
    if not enabled and pawn is not None:
        try:
            from .movement_adjustments import apply_fall_through_pawn

            contexts = live_party_contexts()
            for cidx, _name, _pc, ctx_pawn, ctx_move in contexts:
                if ctx_pawn is not pawn:
                    continue
                if fall_through_enabled_for_index(int(cidx)):
                    apply_fall_through_pawn(pawn, move or ctx_move, enabled=True)
                    break
        except Exception:
            pass
    return 0 if failures and not writes else writes


def _is_local_party_index(idx: int) -> bool:
    local = local_party_index()
    if local is not None:
        return int(idx) == int(local)
    try:
        from mods_base import get_pc

        local_pc = get_pc()
        local_ps = getattr(local_pc, "PlayerState", None) if local_pc is not None else None
    except Exception:
        return int(idx) == 0
    try:
        contexts = live_party_contexts()
    except Exception:
        contexts = []
    for cidx, _name, pc, _pawn, _move in contexts:
        if int(cidx) != int(idx):
            continue
        if local_ps is not None and pc is not None:
            try:
                return getattr(pc, "PlayerState", None) is local_ps
            except Exception:
                pass
        return int(idx) == 0
    return int(idx) == 0


def force_fly_enabled_for_index(idx: int) -> bool:
    try:
        idx = int(idx)
        if idx < 0:
            contexts = live_party_contexts()
            if not contexts:
                return bool(force_fly_targets)
            from .uvhm_progression import selected_lobby_identity

            for cidx, _name, _pc, pawn, _move in contexts:
                if pawn is None or _is_default_obj(pawn):
                    continue
                try:
                    key = str(selected_lobby_identity(int(cidx)).key)
                except Exception:
                    continue
                if key not in force_fly_targets:
                    return False
            return True
        from .uvhm_progression import selected_lobby_identity

        identity = selected_lobby_identity(idx)
        return str(identity.key) in force_fly_targets
    except Exception:
        return False


def set_force_fly_all(enabled: bool) -> None:
    """Enable/disable force fly for every live party member (host panel applies remotes too)."""
    global status_message, _force_fly_all_mode
    _force_fly_all_mode = bool(enabled)
    try:
        contexts = live_party_contexts()
        applied = 0
        for idx, _name, _pc, pawn, _move in contexts:
            if pawn is None or _is_default_obj(pawn):
                continue
            set_force_fly_for_index(int(idx), bool(enabled), party_wide=True)
            applied += 1
        save_settings()
        status_message = (
            f"Force Fly {'ON' if enabled else 'OFF'} for {applied} party member(s)."
        )
        _log(status_message)
        _set_status_pill(status_message, "green" if enabled else "cyan")
    except Exception as exc:
        status_message = f"Force Fly all toggle failed: {exc!r}"
        _log(status_message)
        _set_status_pill(status_message, "red")


def set_force_fly_for_index(idx: int, enabled: bool, *, party_wide: bool = False) -> None:
    global status_message, _force_fly_all_mode
    from .uvhm_progression import selected_lobby_identity

    idx = int(idx)
    if idx < 0:
        set_force_fly_all(enabled)
        return
    if not party_wide:
        _force_fly_all_mode = False
    if enabled and fall_through_enabled_for_index(idx):
        set_fall_through_for_index(idx, False)
    if not party_wide:
        idx = normalize_mobility_target_index(idx, party_wide=False)
    local_target = _is_local_party_index(idx)
    try:
        identity = selected_lobby_identity(idx)
    except Exception as exc:
        status_message = f"Force Fly failed: could not snapshot target identity ({exc})."
        _log(status_message)
        return
    key = str(identity.key)
    if not enabled and key not in force_fly_targets:
        # Still force-disable cheat fly on the live pawn (may have been toggled elsewhere).
        contexts = live_party_contexts()
        target = next((row for row in contexts if int(row[0]) == idx), None)
        if target is not None:
            _idx, name, pc, pawn, move = target
            writes = _apply_force_fly(pc, pawn, move, False, {}, local_target=local_target)
            if writes > 0:
                status_message = f"Force Fly disabled for {name}."
                _log(status_message)
                _set_status_pill(status_message, "cyan")
                return
        status_message = f"Force Fly is already disabled for {identity.display_name}."
        _log(status_message)
        return
    if not enabled:
        _force_fly_disabling.add(key)
        restore = _force_fly_restore.get(key, {})
        global _force_fly_throttle_until
        _force_fly_throttle_until = 0.0
    else:
        _force_fly_disabling.discard(key)
        restore = {}
    contexts = live_party_contexts()
    target = next((row for row in contexts if int(row[0]) == idx), None)
    if target is None:
        status_message = (
            f"Force Fly disable pending for {identity.display_name}; target is temporarily unavailable."
            if not enabled
            else f"Force Fly failed: party index {idx} is unavailable."
        )
        _log(status_message)
        return
    _idx, name, pc, pawn, move = target
    # Capture walk state BEFORE zeroing gravity / enabling fly (poisoned restores
    # were the main reason Force Fly OFF needed multiple clicks).
    if enabled and key not in _force_fly_restore and pawn is not None and move is not None:
        _force_fly_restore[key] = _capture_force_fly_state(pawn, move)
    if enabled and pawn is not None and local_target:
        for obj in (pawn, *_movement_components_for_pawn(pawn)):
            try:
                setattr(obj, "GravityScale", 0.0)
            except Exception:
                pass
    if not enabled and pawn is not None and move is not None and (
        restore.get("_pawn_id") != id(pawn) or restore.get("_move_id") != id(move)
    ):
        # Replacement pawn — do not capture live fly fields as "restore".
        restore = _sanitize_force_fly_restore({})
        _force_fly_restore[key] = restore
    else:
        restore = _sanitize_force_fly_restore(restore)
    writes = _apply_force_fly(pc, pawn, move, bool(enabled), restore, local_target=local_target)
    if enabled and writes > 0:
        writes += _stamp_force_fly_speed(pawn, move, local_target=local_target, pc=pc, dt=0.016)
    if writes <= 0:
        status_message = (
            f"Force Fly restore pending for {name}; not every saved field was writable."
            if not enabled
            else f"Force Fly failed for {name}: no movement fields were writable."
        )
        _log(status_message)
        return
    if enabled:
        force_fly_targets[key] = identity
        _force_fly_missing_since.pop(key, None)
    else:
        force_fly_targets.pop(key, None)
        _force_fly_restore.pop(key, None)
        _force_fly_disabling.discard(key)
        _force_fly_missing_since.pop(key, None)
        _force_fly_last_wish.pop(key, None)
        _force_fly_liftoff_at.pop(key, None)
        if pawn is not None:
            _force_fly_maintain_until_by_key.pop(_force_fly_pawn_key(pawn), None)
        # Second hard pass — tick re-apply can race the first OFF write.
        _apply_force_fly(pc, pawn, move, False, {}, local_target=local_target)
        try:
            _scrub_remote_force_fly_latch()
        except Exception:
            pass
    status_message = f"Force Fly {'enabled' if enabled else 'disabled'} for {name}."
    _log(status_message)
    _set_status_pill(status_message, "green" if enabled else "cyan")


def _release_force_fly_target(
    key: str,
    *,
    pc: object | None = None,
    pawn: object | None = None,
    move: object | None = None,
    is_local: bool = False,
) -> None:
    """Drop dict entry and restore walk/gravity on the live pawn."""
    restore = _sanitize_force_fly_restore(_force_fly_restore.get(key, {}))
    if _uobject_live(pawn) and move is not None and _uobject_live(move):
        try:
            _apply_force_fly(pc, pawn, move, False, restore, local_target=is_local)
        except Exception:
            pass
    force_fly_targets.pop(key, None)
    _force_fly_restore.pop(key, None)
    _force_fly_disabling.discard(key)
    _force_fly_missing_since.pop(key, None)
    _force_fly_last_wish.pop(key, None)
    _force_fly_liftoff_at.pop(key, None)
    if _uobject_live(pawn):
        _force_fly_maintain_until_by_key.pop(_force_fly_pawn_key(pawn), None)
        if not is_local:
            _ensure_remote_cheat_fly(pc, pawn, enabled=False)


def _mobility_feature_active_for_index(idx: int) -> bool:
    if int(idx) in infinite_jump_indices:
        return True
    if int(idx) in _fall_through_indices:
        return True
    try:
        from .uvhm_progression import selected_lobby_identity

        key = str(selected_lobby_identity(int(idx)).key)
        if key in force_fly_targets:
            return True
    except Exception:
        pass
    return False


def _sync_party_wide_mobility_targets() -> None:
    """All-party modes: add new joiners instead of scrubbing them back to vanilla."""
    global infinite_jump_indices
    if not (_infinite_jump_all_mode or _force_fly_all_mode):
        return
    try:
        contexts = live_party_contexts()
    except Exception:
        return
    if _infinite_jump_all_mode:
        changed = False
        for idx, _name, _pc, pawn, _move in contexts:
            if pawn is None or _is_default_obj(pawn):
                continue
            i = int(idx)
            if i not in infinite_jump_indices:
                infinite_jump_indices.add(i)
                changed = True
        if changed:
            try:
                save_settings()
            except Exception:
                pass
    if _force_fly_all_mode:
        from .uvhm_progression import selected_lobby_identity

        for idx, _name, _pc, pawn, _move in contexts:
            if pawn is None or _is_default_obj(pawn):
                continue
            try:
                key = str(selected_lobby_identity(int(idx)).key)
            except Exception:
                continue
            if key not in force_fly_targets:
                set_force_fly_for_index(int(idx), True, party_wide=True)


def _prune_remote_mobility_toggles() -> None:
    """Do not wipe intentional remote infinite-jump targets.

    Older builds cleared every non-local index whenever all-party mode was off,
    so \"Infinite jump (target)\" for a friend died after one join blip / jump.
    Remotes that are *not* in infinite_jump_indices are still scrubbed via
    scrub_remote_party_mobility / _restore_remote_walk_pawn.
    """
    if _infinite_jump_party_wide() or _infinite_jump_all_mode:
        return
    # Keep explicit per-player targets (including remotes). Nothing to prune.


def _restore_remote_walk_pawn(pc: object, pawn: object, move: object | None, idx: int) -> int:
    """Remote party pawns: undo SQBT fly/gravity/jump-cap poison only — never rewrite JumpGoal presets."""
    if _is_local_party_index(int(idx)) or _mobility_feature_active_for_index(int(idx)):
        return 0
    if not _uobject_live(pawn):
        return 0
    moves = [m for m in _movement_components_for_pawn(pawn) if _uobject_live(m)]
    if move is not None and _uobject_live(move) and id(move) not in {id(m) for m in moves}:
        moves.insert(0, move)
    if not moves:
        return 0
    primary = moves[0]
    writes = 0
    need_scrub = _pawn_has_mobility_poison(pawn, primary)
    if not need_scrub:
        try:
            jmc = int(getattr(pawn, "JumpMaxCount", 2) or 2)
            if jmc > 10:
                need_scrub = True
        except Exception:
            pass
    if not need_scrub:
        try:
            from .movement_adjustments import jump_goal_flags_poisoned

            if any(jump_goal_flags_poisoned(o) for o in (pawn, primary) if o is not None and _uobject_live(o)):
                need_scrub = True
        except Exception:
            pass
    if not need_scrub:
        return 0
    if _pawn_has_mobility_poison(pawn, primary):
        writes += _apply_force_fly(pc, pawn, primary, False, {}, local_target=False)
    _restore_pawn_jump_limits(pawn, primary)
    try:
        from .movement_adjustments import jump_goal_flags_poisoned, restore_vanilla_jump_goal_flags_on_obj
    except Exception:
        jump_goal_flags_poisoned = None  # type: ignore[assignment,misc]
        restore_vanilla_jump_goal_flags_on_obj = None  # type: ignore[assignment,misc]
    for obj in (pawn, primary):
        if obj is None or not _uobject_live(obj):
            continue
        if restore_vanilla_jump_goal_flags_on_obj is not None and jump_goal_flags_poisoned is not None:
            if jump_goal_flags_poisoned(obj):
                try:
                    writes += int(restore_vanilla_jump_goal_flags_on_obj(obj) or 0)
                except Exception:
                    pass
        try:
            grav = float(getattr(obj, "GravityScale", 1.0) or 1.0)
            if grav < 0.92 or grav > 1.12:
                setattr(obj, "GravityScale", 1.0)
                writes += 1
        except Exception:
            pass
        try:
            if bool(getattr(obj, "bCheatFlying", False)):
                setattr(obj, "bCheatFlying", False)
                writes += 1
        except Exception:
            pass
    for comp in moves:
        if not _uobject_live(comp):
            continue
        try:
            mode = int(getattr(comp, "MovementMode", 1) or 1)
            if mode == 5:
                setattr(comp, "MovementMode", 1)
                writes += 1
        except Exception:
            pass
        try:
            ac = float(getattr(comp, "AirControl", 0.35) or 0.35)
            if ac > 0.9:
                setattr(comp, "AirControl", 0.35)
                writes += 1
            bdf = float(getattr(comp, "BrakingDecelerationFalling", 2000.0) or 2000.0)
            if bdf < 400.0:
                setattr(comp, "BrakingDecelerationFalling", 2000.0)
                writes += 1
            mfs = float(getattr(comp, "MaxFlySpeed", 600.0) or 600.0)
            if mfs > 8000.0:
                setattr(comp, "MaxFlySpeed", 600.0)
                writes += 1
        except Exception:
            pass
    return writes


def scrub_remote_party_mobility(*, reason: str = "") -> int:
    """Force vanilla movement on every remote party pawn (late join / stale host writes)."""
    try:
        contexts = live_party_contexts()
    except Exception:
        return 0
    if len(contexts) < 2:
        return 0
    restored = 0
    for idx, _name, pc, pawn, move in contexts:
        if _is_local_party_index(int(idx)):
            continue
        restored += _restore_remote_walk_pawn(pc, pawn, move, int(idx))
    try:
        restored += _scrub_orphan_force_fly_latches(include_local=False)
    except Exception:
        pass
    if restored:
        tag = f" ({reason})" if reason else ""
        _log(f"Remote mobility scrub{tag}: reset {restored} remote field(s).")
    return restored


def _maintain_remote_party_walk() -> None:
    """Disabled — periodic remote writes were re-poisoning joiners (moon-jump). Join scrub only."""
    return


def _tick_remote_join_scrub(now: float) -> None:
    """For ~18s after someone joins, clear SQBT fly/grav/jump-cap poison on remotes."""
    global _last_remote_walk_scrub_at
    if now >= float(_remote_join_scrub_until or 0.0):
        return
    if _infinite_jump_party_wide() or _force_fly_party_wide():
        try:
            _sync_party_wide_mobility_targets()
        except Exception:
            pass
        return
    if now - _last_remote_walk_scrub_at < 0.45:
        return
    _last_remote_walk_scrub_at = now
    try:
        scrub_remote_party_mobility(reason="join-maintain")
    except Exception:
        pass


def _scrub_orphan_force_fly_latches(*, include_local: bool = True) -> int:
    """Undo gravity-off fly latch on pawns not listed in force_fly_targets."""
    from .uvhm_progression import selected_lobby_identity

    restored = 0
    try:
        contexts = live_party_contexts()
    except Exception:
        return 0
    for idx, _name, pc, pawn, move in contexts:
        if not _uobject_live(pawn) or move is None or not _uobject_live(move):
            continue
        if not include_local and _is_local_party_index(int(idx)):
            continue
        if int(idx) in _fall_through_indices:
            continue
        if int(idx) in infinite_jump_indices:
            continue
        try:
            key = str(selected_lobby_identity(int(idx)).key)
        except Exception:
            continue
        if key in force_fly_targets:
            continue
        if not _pawn_has_mobility_poison(pawn, move):
            continue
        if _apply_force_fly(
            pc,
            pawn,
            move,
            False,
            {},
            local_target=_is_local_party_index(int(idx)),
        ) > 0:
            restored += 1
    return restored


def _mobility_party_join_scrub() -> None:
    """Someone joined — undo stale SQBT writes on remote pawns (not full mobility presets)."""
    global _last_mobility_party_count, _remote_join_scrub_until
    try:
        contexts = live_party_contexts()
        count = len(contexts)
    except Exception:
        return
    prev = int(_last_mobility_party_count or 0)
    _last_mobility_party_count = count
    if count <= prev or count < 2:
        return
    _remote_join_scrub_until = time.monotonic() + 18.0
    if _infinite_jump_party_wide() or _force_fly_party_wide():
        try:
            _sync_party_wide_mobility_targets()
        except Exception:
            pass
        return
    try:
        _prune_remote_mobility_toggles()
    except Exception:
        pass
    scrub_remote_party_mobility(reason=f"party {prev}->{count}")


def _scrub_remote_force_fly_latch() -> int:
    """Undo gravity-off / fly mode on remote pawns if a prior host tick latched them."""
    return _scrub_orphan_force_fly_latches(include_local=False)


def reapply_all_force_fly() -> int:
    """Re-push the current force-fly speed to every active target (kinematic stamp)."""
    from .uvhm_progression import selected_lobby_identity

    if not force_fly_targets:
        return 0
    applied = 0
    for idx, _name, pc, pawn, move in live_party_contexts():
        try:
            identity = selected_lobby_identity(int(idx))
        except Exception:
            continue
        if identity.key not in force_fly_targets:
            continue
        if pawn is None:
            continue
        if not _uobject_live(pawn):
            continue
        if _stamp_force_fly_speed(
            pawn,
            move,
            local_target=_is_local_party_index(int(idx)),
            pc=pc,
            dt=0.016,
        ) > 0:
            applied += 1
    if applied:
        status_message = f"Updated force-fly speed to {float(force_fly_speed):.0f} for {applied} target(s)."
        _log(status_message)
    return applied


def _force_fly_hud_tick() -> None:
    global _last_force_fly_tick, _last_orphan_fly_scrub_at
    now = time.monotonic()
    try:
        _sync_party_wide_mobility_targets()
    except Exception:
        pass
    try:
        _tick_remote_join_scrub(now)
    except Exception:
        pass
    try:
        _mobility_party_join_scrub()
    except Exception:
        pass
    if now - _last_orphan_fly_scrub_at >= 2.0:
        _last_orphan_fly_scrub_at = now
        try:
            _scrub_orphan_force_fly_latches()
        except Exception:
            pass
    if not force_fly_targets:
        return
    dt = now - _last_force_fly_tick if _last_force_fly_tick else 0.016
    if dt < 0.008:
        return
    _last_force_fly_tick = now
    from .uvhm_progression import resolve_lobby_pc

    contexts = live_party_contexts()
    for key, identity in list(force_fly_targets.items()):
        pc = resolve_lobby_pc(identity)
        if pc is None:
            missing_since = _force_fly_missing_since.setdefault(key, now)
            if now - missing_since >= 10.0:
                _release_force_fly_target(key)
            continue
        ps = getattr(pc, "PlayerState", None)
        target = next(
            (
                row
                for row in contexts
                if row[2] is pc or (ps is not None and getattr(row[2], "PlayerState", None) is ps)
            ),
            None,
        )
        if target is None:
            missing_since = _force_fly_missing_since.setdefault(key, now)
            if now - missing_since >= 10.0:
                _release_force_fly_target(key)
            continue
        _idx, _name, live_pc, pawn, move = target
        if int(_idx) in _fall_through_indices:
            _release_force_fly_target(
                key,
                pc=live_pc,
                pawn=pawn,
                move=move,
                is_local=_is_local_party_index(int(_idx)),
            )
            continue
        if not _uobject_live(pawn) or move is None or not _uobject_live(move):
            missing_since = _force_fly_missing_since.setdefault(key, now)
            if now - missing_since >= 10.0:
                _release_force_fly_target(key, pc=live_pc, pawn=pawn, move=move, is_local=_is_local_party_index(int(_idx)))
            continue
        _force_fly_missing_since.pop(key, None)
        restore = _sanitize_force_fly_restore(_force_fly_restore.get(key, {}))
        is_local = _is_local_party_index(int(_idx))
        if key in _force_fly_disabling:
            if _apply_force_fly(
                live_pc,
                pawn,
                move,
                False,
                restore,
                local_target=is_local,
            ) > 0:
                _release_force_fly_target(key, pc=live_pc, pawn=pawn, move=move, is_local=is_local)
            continue
        _stamp_force_fly_speed(
            pawn,
            move,
            local_target=is_local,
            pc=live_pc,
            dt=min(dt, 0.1),
        )


def _fall_through_hud_tick() -> None:
    if not _fall_through_indices:
        return
    from .movement_adjustments import apply_fall_through_pawn

    contexts = live_party_contexts()
    for idx in sorted(_fall_through_indices):
        target = next((row for row in contexts if int(row[0]) == int(idx)), None)
        if target is None:
            continue
        _i, _name, _pc, pawn, move = target
        if pawn is None or move is None:
            continue
        if force_fly_enabled_for_index(int(idx)):
            set_force_fly_for_index(int(idx), False)
        apply_fall_through_pawn(pawn, move, enabled=True)


def _force_default_jump_type(pawn: object, move: object | None = None) -> None:
    try:
        if move is None:
            move = getattr(pawn, "OakCharacterMovement", None) or getattr(pawn, "CharacterMovement", None)
    except Exception:
        move = None
    if move is None or _is_default_obj(move):
        return
    try:
        cj = getattr(move, "CurrentJump", None)
        jt = getattr(cj, "JumpType", None) if cj is not None else None
        if jt is None:
            return
        try:
            setattr(jt, "TagName", "Movement.JumpType.DefaultJump")
        except Exception:
            try:
                jt._set_field("TagName", "Movement.JumpType.DefaultJump")
            except Exception:
                pass
        set_type = getattr(move, "SetCurrentJumpType", None)
        if callable(set_type):
            try:
                set_type(jt)
            except Exception:
                pass
        rep = getattr(move, "OnRep_CurrentJump", None)
        if callable(rep):
            try:
                rep()
            except Exception:
                pass
    except Exception:
        pass


def _infinite_jump_cached_contexts(now: float) -> list[tuple[int, str, object, object | None, object | None]]:
    global _infinite_jump_context_cache, _infinite_jump_context_cache_time
    try:
        if _infinite_jump_context_cache and now - float(_infinite_jump_context_cache_time) < 1.0:
            return list(_infinite_jump_context_cache)
    except Exception:
        pass
    try:
        contexts = live_party_contexts()
    except Exception:
        contexts = []
    _infinite_jump_context_cache = list(contexts)
    _infinite_jump_context_cache_time = now
    return contexts


def _reset_pawn_jump_counter_if_spent(pawn: object, move: object | None = None) -> bool:
    if pawn is None or _is_default_obj(pawn):
        return False
    idx = pawn_party_index(pawn)
    if not _may_mutate_infinite_jump(idx):
        return False
    try:
        cur = int(getattr(pawn, "JumpCurrentCount", 0) or 0)
    except Exception:
        return False
    if cur < 1:
        return False
    try:
        try:
            move_obj = move or getattr(pawn, "OakCharacterMovement", None) or getattr(pawn, "CharacterMovement", None)
            is_falling = bool(getattr(move_obj, "IsFalling", lambda: False)()) if move_obj is not None else False
        except Exception:
            move_obj = move
            is_falling = True
        if not is_falling and cur <= 1:
            return False
        if cur >= 2:
            is_falling = True
        stop = getattr(pawn, "StopJumping", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass
        setattr(pawn, "JumpCurrentCount", 0)
        setattr(pawn, "JumpCurrentCountPreJump", 0)
        setattr(pawn, "JumpMaxCount", 999)
        _force_default_jump_type(pawn, move_obj)
        return True
    except Exception:
        return False


def _prepare_infinite_jump_pawn(pawn: object) -> bool:
    if not _runtime_enabled:
        return False
    if pawn is None or _is_default_obj(pawn):
        return False
    idx = pawn_party_index(pawn)
    if not _may_mutate_infinite_jump(idx):
        return False
    try:
        try:
            cur = int(getattr(pawn, "JumpCurrentCount", 0) or 0)
        except Exception:
            cur = 0
        try:
            if hasattr(pawn, "JumpMaxCount"):
                jmc = int(getattr(pawn, "JumpMaxCount", 0) or 0)
                if jmc < 900:
                    setattr(pawn, "JumpMaxCount", 999)
        except Exception:
            pass
        move = getattr(pawn, "OakCharacterMovement", None) or getattr(pawn, "CharacterMovement", None) or getattr(pawn, "GbxCharacterMovement", None)
        if move is not None:
            try:
                if hasattr(move, "JumpMaxCount"):
                    mjc = int(getattr(move, "JumpMaxCount", 0) or 0)
                    if mjc < 900:
                        setattr(move, "JumpMaxCount", 999)
            except Exception:
                pass
        if cur < 1:
            return True
        stop = getattr(pawn, "StopJumping", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass
        for attr, value in (
            ("JumpCurrentCount", 0),
            ("JumpCurrentCountPreJump", 0),
            ("JumpMaxCount", 999),
            ("bProxyIsJumpForceApplied", False),
            ("JumpKeyHoldTime", 0.0),
            ("JumpForceTimeRemaining", 0.0),
        ):
            try:
                if hasattr(pawn, attr):
                    setattr(pawn, attr, value)
            except Exception:
                pass
        if move is not None:
            for attr, value in (("JumpedCount", 0), ("JumpMaxCount", 999)):
                try:
                    if hasattr(move, attr):
                        setattr(move, attr, value)
                except Exception:
                    pass
        return True
    except Exception:
        return False


def _hook_arg_to_pawn(obj: object) -> object | None:
    if obj is None or _is_default_obj(obj):
        return None
    try:
        if hasattr(obj, "JumpCurrentCount") and hasattr(obj, "JumpMaxCount"):
            return obj
    except Exception:
        pass
    for attr in ("Object", "object", "obj", "self", "This", "this", "Caller", "caller", "Context", "context"):
        try:
            inner = getattr(obj, attr, None)
        except Exception:
            inner = None
        if inner is not None and inner is not obj:
            pawn = _hook_arg_to_pawn(inner)
            if pawn is not None:
                return pawn
    for attr in ("OakCharacter", "Pawn", "AcknowledgedPawn", "Character", "ControlledPawn"):
        try:
            pawn = getattr(obj, attr, None)
        except Exception:
            pawn = None
        if pawn is not None and not _is_default_obj(pawn):
            try:
                if hasattr(pawn, "JumpCurrentCount") and hasattr(pawn, "JumpMaxCount"):
                    return pawn
            except Exception:
                return pawn
    return None


def _jump_pre_hook(*args: Any, **kwargs: Any) -> None:
    if not _runtime_enabled or not infinite_jump_indices:
        return None
    try:
        for obj in list(args) + list(kwargs.values()):
            pawn = _hook_arg_to_pawn(obj)
            if pawn is None:
                continue
            idx = pawn_party_index(pawn)
            if not _may_mutate_infinite_jump(idx):
                continue
            _prepare_infinite_jump_pawn(pawn)
            break
    except Exception:
        pass
    return None


def _infinite_jump_hud_tick(now: float) -> None:
    if not _runtime_enabled or not is_listen_host():
        return
    try:
        _sync_party_wide_mobility_targets()
    except Exception:
        pass
    if _infinite_jump_disabling:
        done: list[int] = []
        for idx in list(_infinite_jump_disabling):
            until = float(_infinite_jump_disable_until.get(idx) or 0.0)
            if idx in infinite_jump_indices:
                infinite_jump_indices.discard(idx)
            _restore_jump_limits_for_indices({idx})
            if now >= until:
                done.append(idx)
        for idx in done:
            _infinite_jump_disabling.discard(idx)
            _infinite_jump_disable_until.pop(idx, None)
    if not infinite_jump_indices:
        return
    for idx, _name, _pc, pawn, move in _infinite_jump_cached_contexts(now):
        try:
            if int(idx) not in infinite_jump_indices:
                continue
        except Exception:
            continue
        try:
            if pawn is not None and hasattr(pawn, "JumpMaxCount"):
                setattr(pawn, "JumpMaxCount", 999)
        except Exception:
            pass
        if move is not None:
            try:
                if hasattr(move, "JumpMaxCount"):
                    setattr(move, "JumpMaxCount", 999)
            except Exception:
                pass
        _prepare_infinite_jump_pawn(pawn)
        _reset_pawn_jump_counter_if_spent(pawn, move)


def background_tick() -> None:
    global _apply_on_load_done, _last_auto_apply_try
    if not _runtime_enabled:
        return
    now = time.monotonic()
    # Never touch UObjects before a live world exists (early-boot AV).
    try:
        from .session_guards import session_safe

        if not session_safe():
            return
        world, _gs = _gbc_session_world_and_gamestate()
        if world is None:
            return
    except Exception:
        return
    if not is_listen_host():
        if _auto_apply_on_load or _pending_apply or infinite_jump_indices:
            require_host("mobility tools", quiet=True)
        return
    try:
        from . import encounter_builder as _encounter_builder

        _encounter_builder.tick()
    except Exception as exc:
        _log(f"Encounter tick failed: {exc!r}")
    try:
        from .inventory_capacity import game_thread_inventory_tick  # noqa: PLC0415

        game_thread_inventory_tick()
    except Exception:
        pass
    try:
        from .golden_chest_keybinds import golden_chest_tick

        golden_chest_tick()
    except Exception:
        pass
    try:
        from .embedded_oak.engine import logo_tick

        logo_tick()
    except Exception:
        pass
    try:
        apply_pending_if_due(now)
    except Exception:
        pass
    try:
        _infinite_jump_hud_tick(now)
    except Exception:
        pass
    try:
        _force_fly_hud_tick()
    except Exception:
        pass
    try:
        _fall_through_hud_tick()
    except Exception:
        pass
    try:
        from . import rarity_weights as _rarity_weights

        _rarity_weights.background_tick()
    except Exception:
        pass
    try:
        from .dev_tools import sticky_combat_tick  # noqa: PLC0415

        sticky_combat_tick()
    except Exception:
        pass
    if _auto_apply_on_load and not _apply_on_load_done and now - float(_last_auto_apply_try) >= 2.0:
        _last_auto_apply_try = now
        try:
            apply_all()
            if "0 player pawn(s)" not in str(status_message):
                _apply_on_load_done = True
        except Exception:
            pass


def _tick_cb(*_args: Any, **_kwargs: Any) -> None:
    # Reuse this already-installed, dump-proven live tick for the desktop
    # bridge and SQBT's deferred game-thread work. Look modules up without
    # importing them to avoid package-startup cycles.
    try:
        rewards = sys.modules.get(f"{__package__}.serial_rewards")
        rewards_tick = getattr(rewards, "_tick_cb", None)
        if callable(rewards_tick):
            rewards_tick(*_args, **_kwargs)
    except Exception as exc:
        _log(f"Reward/progression tick failed: {exc!r}")
    try:
        travel = sys.modules.get(f"{__package__}.travel")
        travel_tick = getattr(travel, "_travel_queue_tick", None)
        if callable(travel_tick):
            travel_tick(*_args, **_kwargs)
    except Exception as exc:
        _log(f"Travel tick failed: {exc!r}")
    try:
        bridge = sys.modules.get(f"{__package__}.external_bridge")
        bridge_tick = getattr(bridge, "_process_queue", None)
        if callable(bridge_tick):
            bridge_tick()
    except Exception as exc:
        _log(f"Bridge tick failed: {exc!r}")
    try:
        deferred = sys.modules.get(f"{__package__}.spawn_deferred")
        flush_tick = getattr(deferred, "flush_tick", None)
        if callable(flush_tick):
            flush_tick(max_items=1, owner="Squ1ggsBoostingTools")
    except Exception as exc:
        _log(f"Deferred tick failed: {exc!r}")
    try:
        background_tick()
    except Exception as exc:
        _log(f"Mobility tick failed: {exc!r}")


def _register_infinite_jump_hooks() -> None:
    for i, target in enumerate(_INFINITE_JUMP_HOOK_TARGETS):
        try:
            hook(
                target,
                immediately_enable=True,
                hook_identifier=f"squ1ggs_boost_infinite_jump_gate_hook_v1_{i}",
            )(_jump_pre_hook)
            _log(f"Infinite Jump hook installed: {target}")
        except Exception as exc:
            _log(f"Infinite Jump hook skipped {target}: {exc!r}")


def install_mobility_runtime() -> None:
    _register_infinite_jump_hooks()
    try:
        hook(
            "/Script/GbxUIUMG.GbxUIUMGTickWidget:BP_TickWidget",
            immediately_enable=True,
            hook_identifier="squ1ggs_boost_mobility_tick_v1",
        )(_tick_cb)
    except Exception as exc:
        _log(f"Could not install mobility HUD tick hook: {exc!r}")


def disable_mobility_runtime() -> None:
    """Mods-menu disable: stop Infinite Jump effects without tearing down the bridge tick."""
    set_runtime_enabled(False)


def enable_mobility_runtime() -> None:
    set_runtime_enabled(True)


try:
    install_mobility_runtime()
except Exception as exc:
    _log(f"Mobility runtime install failed: {exc!r}")
