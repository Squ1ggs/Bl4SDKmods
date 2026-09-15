# Auto-synced from standalone mod — edit the sidecar and re-run _dev_sync_embedded_tuning.py.

"""
Vehicle Movement — vehicle / Chaos movement tuning for the Python SDK.

**Standalone:** copy only the ``bl4_vehicle_movement`` folder into your ``sdk_mods`` directory next to the SDK's
``mods_base`` and ``unrealsdk`` packages. Ultra Local Menu is **not** required; the optional "forward to ulm" hint
is ignored safely if ULM is absent.

Mods → Vehicle Movement: **Apply tuning to** (local / all / others), sliders, keybinds. Console: vehicle_move_* commands.
Enter a vehicle first. Session-only; may reset on travel.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Callable

import unrealsdk
from mods_base import CoopSupport, Game, BoolOption, ButtonOption, GroupedOption, SliderOption, build_mod, command, keybind
from mods_base.options import SpinnerOption
from unrealsdk import hooks, logging

EMBEDDED_IN_SQBT = True

__version__ = "1.0.0"
__author__ = "Squ1ggs"
MOD_NAME = "Vehicle Movement"
LOG_PREFIX = "[Vehicle Movement]"
from mods_base import SETTINGS_DIR as _SETTINGS_DIR

SETTINGS_PATH = Path(_SETTINGS_DIR) / "bl4_vehicle_movement.json"
from .sqbt_coop import skip_own_blimgui_tab
_BLIMGUI_TAB = "Vehicle Movement"
_suppress_option_apply: bool = False


def _set_option_value_silent(option: Any, value: Any) -> None:
    global _suppress_option_apply
    previous = _suppress_option_apply
    _suppress_option_apply = True
    try:
        option.value = value
    finally:
        _suppress_option_apply = previous


def _blimgui_defer(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Run UObject / hook work after the ImGui frame (avoids tab-switch crashes)."""
    try:
        import blimgui

        blimgui.defer_post_frame(lambda: fn(*args, **kwargs))
    except Exception:
        fn(*args, **kwargs)


def _collapsing_open(result: Any) -> bool:
    if isinstance(result, tuple):
        return bool(result[0]) if result else False
    return bool(result)


def _collapsing_header(imgui: Any, label: str, *, default_open: bool = True) -> bool:
    flags = 0
    if default_open:
        flags = getattr(getattr(imgui, "TreeNodeFlags_", None), "default_open", 0)
    return _collapsing_open(imgui.collapsing_header(label, flags))


def _draw_blimgui_tab() -> None:
    global BVM_APPLY_SCOPE, BVM_VEHICLE_DAMAGE_TAKEN, BVM_UNLIMITED_BOOST, _jump_repeat_latched
    try:
        from blimgui import imgui
    except Exception:
        return
    imgui.text_wrapped("Vehicle and Chaos movement tuning. Enter a vehicle first.")
    for key, label in (("local", "Local"), ("all", "All"), ("others", "Others")):
        if imgui.radio_button(f"{label}##bvm_f1_scope_{key}", BVM_APPLY_SCOPE == key):
            _set_option_value_silent(_target_scope, _SCOPE_LABELS[key])
            _blimgui_defer(_bvm_target_scope_apply, _SCOPE_LABELS[key])
        imgui.same_line()
    imgui.new_line()

    def _slider_rows(sliders: list[Any], specs: tuple[Any, ...]) -> None:
        for opt, spec in zip(sliders, specs, strict=True):
            attr, lo, hi, _step, default, label = spec[:6]
            imgui_id = str(attr).replace(".", "_")
            try:
                current = float(opt.value)
            except Exception:
                current = float(default)
            moved, value = imgui.slider_float(f"{label}##bvm_f1_{imgui_id}", current, float(lo), float(hi))
            if moved:
                current = float(value)
                _set_option_value_silent(opt, current)
                _blimgui_defer(_sync_vehicle_jump_hook)
            typed, exact = imgui.input_float(
                f"Exact value##bvm_f1_exact_{imgui_id}",
                current,
                float(_step),
                float(_step) * 10.0,
                "%.3f",
            )
            if typed:
                _set_option_value_silent(opt, max(float(lo), min(float(hi), float(exact))))

    def _sliders(title: str, sliders: list[Any], specs: tuple[Any, ...]) -> None:
        if _collapsing_header(imgui, title):
            _slider_rows(sliders, specs)

    _sliders("Core", _slider_core, _CORE_SPECS)
    changed, unlimited_boost = imgui.checkbox(
        "Unlimited boost##bvm_f1_unlimited_boost",
        bool(_unlimited_boost_opt.value),
    )
    if changed:
        _set_option_value_silent(_unlimited_boost_opt, bool(unlimited_boost))
        BVM_UNLIMITED_BOOST = bool(unlimited_boost)

        def _apply_boost_toggle() -> None:
            _sync_vehicle_jump_hook()
            if BVM_UNLIMITED_BOOST:
                _apply_unlimited_boost(log_result=True)
            else:
                target = float(_slider_core[4].value)
                for _path, pawn, comp in _iter_bvm_vehicle_hits():
                    _write_vehicle_field(pawn, comp, "BoostConsumptionRateScalar", target)

        _blimgui_defer(_apply_boost_toggle)
    if _collapsing_header(imgui, "Jump and gravity"):
        _slider_rows(_slider_jump, _JUMP_SPECS)
        for opt, label, lo, hi, step, suffix in (
            (_jump_repeat_interval_opt, "Repeat jump cooldown (sec)", 0.08, 1.0, 0.02, "repeat"),
        ):
            current = float(opt.value)
            moved, value = imgui.slider_float(f"{label}##bvm_f1_{suffix}", current, lo, hi)
            if moved:
                current = float(value)
                _set_option_value_silent(opt, current)
            typed, exact = imgui.input_float(
                f"Exact value##bvm_f1_exact_{suffix}",
                current,
                step,
                step * 10.0,
                "%.3f",
            )
            if typed:
                _set_option_value_silent(opt, max(lo, min(hi, float(exact))))
        changed, repeat_jump = imgui.checkbox(
            "Unlimited jumps (repeat on press)##bvm_f1_repeat_jump",
            bool(_repeat_jump_press_opt.value),
        )
        if changed:
            _set_option_value_silent(_repeat_jump_press_opt, bool(repeat_jump))
            BVM_REPEAT_JUMP_PRESS = bool(repeat_jump)
            _blimgui_defer(_sync_vehicle_jump_hook)
        if imgui.button("Test jump now##bvm_f1_jump_now"):
            _blimgui_defer(_apply_custom_vehicle_jump, log_result=True)
        imgui.text_wrapped(
            "Test jump / N key / mid-air repeats use HoverSetup jump height from the dump "
            "(VehicleMovementComp → PowerslideJumpHeight + gravity)."
        )
    _sliders("Handling", _slider_extra, _EXTRA_SPECS)
    if _collapsing_header(imgui, "Vehicle durability"):
        _slider_rows(_slider_durability, _DURABILITY_SPECS)
    if _collapsing_header(imgui, "Presets", default_open=False):
        for index, name in enumerate(("boost", "crawl", "floaty", "orbit", "heavy", "drift")):
            if imgui.button(f"{name.title()}##bvm_f1_preset_{name}"):
                _blimgui_defer(_apply_preset, name)
            if index % 3 != 2:
                imgui.same_line()
    if _collapsing_header(imgui, "Vehicle summon lock", default_open=True):
        imgui.text_wrapped(
            "PersonalVehicleState.VehicleActionsLock — force locked blocks summon/use until you turn it off."
        )
        changed_lock, force_locked = imgui.checkbox(
            "Force locked (blocks summon/use)##bvm_f1_force_locked",
            bool(_vehicle_force_locked_opt.value),
        )
        if changed_lock:
            _set_option_value_silent(_vehicle_force_locked_opt, bool(force_locked))
            _blimgui_defer(_vehicle_force_locked_apply, bool(force_locked))
        changed_sticky, sticky = imgui.checkbox(
            "Sticky re-apply##bvm_f1_lock_sticky",
            bool(_vehicle_lock_sticky_opt.value),
        )
        if changed_sticky:
            _set_option_value_silent(_vehicle_lock_sticky_opt, bool(sticky))
            _blimgui_defer(_vehicle_lock_sticky_apply, bool(sticky))
    if _collapsing_header(imgui, "Test vehicle", default_open=False):
        imgui.text_wrapped(
            "Summons a personal vehicle via OakPlayerController (dump: ServerSetPersonalVehicleDef + "
            "ServerRequestPersonalVehicle). Uses the same Apply tuning to scope as sliders and force lock. "
            "Console: vehicle_move_spawn <name> | vehicle_move_spawn_list"
        )
        imgui.text_wrapped(f"Apply scope: {_SCOPE_LABELS.get(BVM_APPLY_SCOPE, BVM_APPLY_SCOPE)}")
        labels = _vehicle_spawn_spinner_labels()
        global _spawn_ui_index
        idx = max(0, min(_spawn_ui_index, len(labels) - 1)) if labels else 0
        if labels:
            _changed, idx = imgui.combo("Vehicle##bvm_f1_spawn_combo", idx, labels)
            _spawn_ui_index = idx
            if imgui.button("Summon##bvm_f1_spawn_go"):
                entry = _vehicle_spawn_entry_by_label(labels[idx])
                if entry is not None:
                    _blimgui_defer(_spawn_vehicle_entry, entry)
            imgui.same_line()
        if imgui.button("List all##bvm_f1_spawn_list"):
            _blimgui_defer(_log_vehicle_spawn_list)
        imgui.same_line()
        if imgui.button("Scan all sources##bvm_f1_spawn_scan"):
            _blimgui_defer(_scan_runtime_vehicle_defs, log=True, deep_offline=True)
    if imgui.button("Apply all changes##bvm_f1_apply"):
        _blimgui_defer(_apply_saved_tuning)
    imgui.same_line()
    if imgui.button("Reset##bvm_f1_reset"):
        _blimgui_defer(_reset_all)
    imgui.same_line()
    if imgui.button("Log values##bvm_f1_show"):
        _blimgui_defer(_show_all)


def _register_blimgui() -> None:
    if skip_own_blimgui_tab(SETTINGS_PATH.name, embedded_copy=EMBEDDED_IN_SQBT):
        return
    try:
        import blimgui
        blimgui.register_tab(_BLIMGUI_TAB, _draw_blimgui_tab, author="Squ1ggs")
    except Exception as exc:
        _warn(f"BLImGui tab unavailable: {exc}")


def _unregister_blimgui() -> None:
    try:
        import blimgui
        blimgui.remove_tab(_BLIMGUI_TAB)
    except Exception:
        pass


def _on_enable() -> None:
    global BVM_APPLY_SCOPE, BVM_REPEAT_JUMP_PRESS, BVM_UNLIMITED_BOOST
    global BVM_VEHICLE_DAMAGE_DEALT, BVM_VEHICLE_DAMAGE_TAKEN, _BVM_MOD_ACTIVE
    _BVM_MOD_ACTIVE = True
    _clamp_saved_options()
    BVM_APPLY_SCOPE = _scope_from_spinner_label(str(_target_scope.value))
    BVM_REPEAT_JUMP_PRESS = bool(_repeat_jump_press_opt.value)
    BVM_UNLIMITED_BOOST = bool(_unlimited_boost_opt.value)
    BVM_VEHICLE_DAMAGE_DEALT = 1.0
    BVM_VEHICLE_DAMAGE_TAKEN = float(_vehicle_damage_taken_opt.value)
    if not EMBEDDED_IN_SQBT:
        _register_blimgui()
    _sync_vehicle_jump_hook()
    try:
        _reload_vehicle_spawn_catalog(deep_offline=False)
        _refresh_spawn_vehicle_spinner()
    except Exception as exc:
        _warn(f"Vehicle spawn catalog load failed (menu still works): {exc}")
    if BVM_UNLIMITED_BOOST:
        _apply_unlimited_boost(log_result=False)
    _apply_vehicle_incoming_damage_scale(BVM_VEHICLE_DAMAGE_TAKEN, log_result=False)


def _on_disable() -> None:
    global _BVM_MOD_ACTIVE, _last_auto_apply_vehicle_id
    _BVM_MOD_ACTIVE = False
    _last_auto_apply_vehicle_id = 0
    _unregister_blimgui()
    _remove_vehicle_jump_hook()
    _remove_vehicle_damage_hook()
SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

_DEFAULT_MAX_WALK_SPEED = 600.0
_DEFAULT_JUMP_Z = 620.0
_DEFAULT_GRAVITY_SCALE = 1.0
_DEFAULT_MASS = 100.0

_LEGACY_CORE_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    (
        "MinAnalogWalkSpeed",
        0.0,
        12000.0,
        5.0,
        _DEFAULT_MAX_WALK_SPEED,
        "Walk / analog speed (MinAnalogWalkSpeed — often what BL4 obeys)",
    ),
    (
        "MaxWalkSpeed",
        50.0,
        12000.0,
        5.0,
        _DEFAULT_MAX_WALK_SPEED,
        "Max speed (MaxWalkSpeed — may mirror MinAnalog on vehicle movement)",
    ),
    ("JumpZVelocity", 0.0, 12000.0, 10.0, _DEFAULT_JUMP_Z, "Jump Z velocity"),
    (
        "GravityScale",
        -80.0,
        80.0,
        0.05,
        _DEFAULT_GRAVITY_SCALE,
        "Gravity scale (negative = upward / anti-grav vs world down)",
    ),
    ("Mass", 1.0, 5000.0, 5.0, _DEFAULT_MASS, "Mass"),
)

_LEGACY_EXTRA_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("MaxWalkSpeedCrouched", 0.0, 6000.0, 5.0, 300.0, "Max walk speed (crouched / low)"),
    ("MaxAcceleration", 0.0, 32000.0, 50.0, 2048.0, "Max acceleration"),
    ("MaxBrakingDecelerationWalking", 0.0, 32000.0, 50.0, 2048.0, "Max braking decel (walking)"),
    ("MaxBrakingDecelerationFalling", 0.0, 32000.0, 50.0, 0.0, "Max braking decel (falling)"),
    ("MaxBrakingDecelerationFlying", 0.0, 32000.0, 50.0, 0.0, "Max braking decel (flying / glide-like modes)"),
    ("BrakingDecelerationWalking", 0.0, 32000.0, 50.0, 2048.0, "Braking deceleration (walking)"),
    ("BrakingDecelerationFalling", 0.0, 32000.0, 50.0, 0.0, "Braking deceleration (falling)"),
    ("BrakingDecelerationFlying", 0.0, 32000.0, 50.0, 0.0, "Braking deceleration (flying / glide-like modes)"),
    ("BrakingFrictionFactor", 0.0, 20.0, 0.05, 2.0, "Braking friction factor (air / slide feel)"),
    ("FallingLateralFriction", 0.0, 50.0, 0.05, 0.0, "Falling lateral friction (air strafe / glide drift)"),
    ("GroundFriction", 0.0, 100.0, 0.1, 8.0, "Ground friction"),
    ("MaxStepHeight", 0.0, 200.0, 1.0, 45.0, "Max step height"),
    ("WalkableFloorAngle", 0.0, 89.0, 0.5, 75.0, "Walkable floor angle (degrees)"),
    ("AirControl", 0.0, 20.0, 0.02, 0.05, "Air control"),
    ("AirControlBoostMultiplier", 0.0, 30.0, 0.1, 1.0, "Air control boost mult"),
    ("MaxFlySpeed", 0.0, 15000.0, 50.0, 600.0, "Max fly speed"),
    ("MaxSwimSpeed", 0.0, 5000.0, 50.0, 300.0, "Max swim speed"),
    ("MaxBrakingDecelerationSwimming", 0.0, 32000.0, 50.0, 0.0, "Max braking decel (swimming)"),
    ("BrakingDecelerationSwimming", 0.0, 32000.0, 50.0, 0.0, "Braking deceleration (swimming)"),
    ("MaxCustomMovementSpeed", 0.0, 20000.0, 50.0, 0.0, "Max custom movement speed (custom/glide modes if exposed)"),
    ("PerchRadiusThreshold", 0.0, 500.0, 1.0, 0.0, "Perch radius threshold"),
    ("Buoyancy", 0.0, 10.0, 0.05, 1.0, "Buoyancy"),
    ("JumpOffJumpZFactor", 0.0, 80.0, 0.01, 0.5, "Jump-off jump Z factor"),
    ("JumpMaxHoldTime", 0.0, 8.0, 0.01, 0.0, "Jump max hold time (variable-height jump)"),
    ("MaxJumpApexAttemptsPerSimulation", 1.0, 64.0, 1.0, 2.0, "Max jump apex attempts per simulation"),
)

_CORE_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("maxspeed", 0.0, 50_000.0, 50.0, 50.0, "Maximum driving speed (boost cap auto-syncs up)"),
    ("BoostMaxSpeed", 0.0, 50_000.0, 50.0, 65.0, "Maximum boost / overall speed cap"),
    ("MaxAccel", 0.0, 250_000.0, 100.0, 1000.0, "Driving acceleration"),
    ("BoostMaxAccel", 0.0, 250_000.0, 100.0, 1200.0, "Boost acceleration"),
    ("BoostConsumptionRateScalar", 0.0, 25.0, 0.05, 1.0, "Boost consumption (0 = unlimited)"),
)

_EXTRA_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("StrafeSpeed", 0.0, 50_000.0, 50.0, 35.0, "Strafe speed"),
    ("ReverseSpeed", 0.0, 50_000.0, 50.0, 25.0, "Reverse speed"),
    ("BrakingAccel", 0.0, 250_000.0, 100.0, 850.0, "Braking acceleration"),
    ("BoostingBrakingAccel", 0.0, 250_000.0, 100.0, 1250.0, "Boost braking acceleration"),
    ("AirControl", 0.0, 100.0, 0.05, 0.5, "Air control"),
    ("AirBraking", 0.0, 50_000.0, 10.0, 0.02, "Air braking"),
    ("PowerslideBoostSlideTime", 0.0, 30.0, 0.05, 1.0, "Powerslide boost slide time"),
    ("PowerslideBoostDuration", 0.0, 30.0, 0.05, 1.0, "Powerslide boost duration"),
    ("Mass", 0.01, 100_000.0, 25.0, 2500.0, "Chassis mass"),
    ("DragCoefficient", -25.0, 25.0, 0.01, 0.3, "Drag coefficient"),
    ("DownforceCoefficient", -100.0, 100.0, 0.05, 1.0, "Downforce (lower = more airborne)"),
)

_JUMP_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("PowerslideJumpHeight", 0.0, 25_000.0, 5.0, 165.0, "Native powerslide jump height"),
    ("PowerslideJumpGravityScalar", -100.0, 100.0, 0.05, 8.0, "Native jump gravity"),
    ("GravityScalar", -100.0, 100.0, 0.05, 2.0, "Vehicle gravity"),
    ("GravityScalar_AntiBounce", -100.0, 100.0, 0.05, 5.0, "Anti-bounce gravity"),
)

_DURABILITY_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("vehicle_damage_taken", 0.0, 1000.0, 0.1, 1.0, "Damage taken by vehicle"),
)

_FLOAT_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    _CORE_SPECS + _JUMP_SPECS + _EXTRA_SPECS
)

_VAULT_COST_VALUE_PATHS: tuple[str, ...] = (
    "OakCharacterMovement.VaultPowerCost_Dash.Value",
    "OakCharacterMovement.VaultPowerCost_DoubleJump.Value",
    "OakCharacterMovement.VaultPowerCost_Glide.Value",
    "OakCharacterMovement.VaultPowerCost_Grapple.Value",
    "OakCharacterMovement.VaultPowerCost_GroundSlam.Value",
    "OakCharacterMovement.VaultPower_Forgiveness.Value",
)

_PATH_SEG_BRACKET_RE = re.compile(r"^([^[\]]+)\[(\d+)\]$")


def _info(msg: str) -> None:
    logging.info(f"{LOG_PREFIX} {msg}")


def _warn(msg: str) -> None:
    logging.warning(f"{LOG_PREFIX} {msg}")


def _err(msg: str) -> None:
    logging.error(f"{LOG_PREFIX} {msg}")


def _is_cdo(obj: Any) -> bool:
    try:
        h = str(getattr(obj, "Name", "") or "")
    except Exception:
        h = ""
    return "Default__" in h


def _iter_pcs() -> list[Any]:
    out: list[Any] = []
    for cn in ("OakPlayerController", "Oak2PlayerController", "PlayerController"):
        try:
            out.extend(list(unrealsdk.find_all(cn, exact=False)))
        except Exception:
            continue
    seen: set[int] = set()
    uniq: list[Any] = []
    for p in out:
        try:
            a = int(getattr(p, "_get_address", lambda: 0)() or 0)
        except Exception:
            a = id(p)
        if a in seen:
            continue
        seen.add(a)
        uniq.append(p)
    return uniq


def _try_pawn(pc: Any) -> Any | None:
    for a in ("Pawn", "Character", "ControlledPawn"):
        try:
            v = getattr(pc, a, None)
            if v is not None:
                return v
        except Exception:
            continue
    return None


def _get_local_pc(candidates: list[Any] | None = None) -> Any | None:
    if candidates is None:
        candidates = [p for p in _iter_pcs() if not _is_cdo(p)]
    if not candidates:
        return None
    local = [p for p in candidates if _is_local_pc(p)]
    pool = local or candidates
    with_pawn = [p for p in pool if _try_pawn(p) is not None]
    pool = with_pawn or pool
    try:
        pool.sort(
            key=lambda p: (0 if "oak" in str(getattr(getattr(p, "Class", None), "Name", "")).lower() else 1, id(p)),
        )
    except Exception:
        pass
    return pool[0] if pool else None


def _is_local_pc(pc: Any) -> bool:
    if pc is None:
        return False
    for attr_name in ("IsLocalPlayerController", "IsPrimaryPlayer", "bIsLocalPlayerController"):
        try:
            attr = getattr(pc, attr_name, None)
            if callable(attr):
                if bool(attr()):
                    return True
            elif attr is not None:
                if bool(attr):
                    return True
        except Exception:
            continue
    try:
        if int(getattr(pc, "PlayerIndex", -1) or -1) == 0:
            return True
    except Exception:
        pass
    return False


# Co-op: sliders / presets / reset / vault apply to one or many pawns (Mods spinner + `vehicle_move_target`).
BVM_APPLY_SCOPE: str = "local"
_SCOPE_LABELS: dict[str, str] = {
    "local": "Local (you only)",
    "all": "All players in session",
    "others": "Other players only (exclude you)",
}
_SCOPE_SPINNER_CHOICES: list[str] = list(_SCOPE_LABELS.values())
BVM_REPEAT_JUMP_PRESS: bool = False
BVM_UNLIMITED_BOOST: bool = False
BVM_VEHICLE_DAMAGE_DEALT: float = 1.0
BVM_VEHICLE_DAMAGE_TAKEN: float = 1.0
_VEHICLE_JUMP_HOOK_ID = "bl4_vehicle_movement.unlimited_jump"
_VEHICLE_POWERSLIDE_HOOK_ID = "bl4_vehicle_movement.powerslide_jump"
_VEHICLE_DAMAGE_HOOK_ID = "bl4_vehicle_movement.vehicle_damage"
_vehicle_jump_hook_path: str | None = None
_vehicle_jump_hook_type: Any | None = None
_vehicle_powerslide_hook_paths: list[tuple[str, str]] = []
_psi_active_was: bool = False
_mod_jump_pending: bool = False
_space_jump_pending: bool = False
_space_key_was_down: bool = False
_mod_key_was_down: bool = False
_jump_kb_handles: list[Any] = []
_last_native_jump_at: float = 0.0
_last_sampled_launch_vz: float | None = None
_jump_b_pressed_was: bool = False
_vehicle_damage_hook_paths: list[tuple[str, str]] = []
_vehicle_damage_trace_budget: int = 0
_last_custom_jump_at: float = 0.0
_last_jump_warn_at: float = 0.0
_last_repeat_jump_log_at: float = 0.0
_was_vehicle_on_ground: bool = True
_jump_air_session: bool = False
_jump_air_session_grace: int = 0
_jump_air_session_until: float = 0.0
_jump_repeat_armed: bool = False
_vehicle_jump_was_in_air: bool = False
_jump_chain_active: bool = False
_jump_chain_grace: int = 0
_last_jump_chain_log_at: float = 0.0
_postframe_jump_registered: bool = False
_jump_repeat_latched: bool = False
_jump_key_was_down: bool = False
_comp_jump_was_down: bool = False
_vehicle_jump_down_latched: bool = False
_vehicle_jump_pressed_pending: bool = False
_last_jump_maintain_at: float = 0.0
_cached_jump_mesh: Any | None = None
_cached_jump_mesh_id: int = 0
_cached_jump_pawn_id: int = 0
_BVM_MOD_ACTIVE: bool = False
_last_auto_apply_vehicle_id: int = 0
_auto_apply_pending_vehicle_id: int = 0
_auto_apply_pending_since: float = 0.0
_AUTO_APPLY_RETRY_SEC = 4.0
_cached_jump_comp: Any | None = None
_cached_jump_vehicle: Any | None = None
_cached_launch_vz: float | None = None
_cached_launch_vz_key: int = 0
_last_jump_cache_at: float = 0.0
_JUMP_CACHE_INTERVAL = 0.15
_JUMP_MAINTAIN_INTERVAL = 0.15
_TUNING_MAINTAIN_INTERVAL = 1.0
_JUMP_WARN_COOLDOWN = 8.0
_last_boost_maintenance_at: float = 0.0
_last_tuning_maintenance_at: float = 0.0
_last_damage_maintenance_at: float = 0.0
_last_damage_rescan_at: float = 0.0
_last_vehicle_lock_maintenance_at: float = 0.0
BVM_VEHICLE_LOCK_STICKY: bool = True
_vehicle_weapon_damage_baselines: dict[int, tuple[float, float]] = {}
_vehicle_driver_damage_baselines: dict[int, tuple[float, float]] = {}
_vehicle_weapon_damage_targets: dict[int, Any] = {}
_vehicle_driver_damage_targets: dict[int, Any] = {}
_vehicle_incoming_damage_targets: dict[int, Any] = {}
_vehicle_tuning_baselines: dict[tuple[int, str], float] = {}
# POST first — BL4 builds often reject POST_UNCONDITIONAL on PlayerTick (see reward_generator).
_POWERSLIDE_JUMP_HOOKS: tuple[str, ...] = (
    "/Script/OakGame.OakWheeledVehicleMovementComponent:PowerslideCooldownElapsed",
    "/Script/Oak2.OakWheeledVehicleMovementComponent:PowerslideCooldownElapsed",
    "/Script/ChaosVehicles.ChaosWheeledVehicleMovementComponent:PowerslideCooldownElapsed",
)
_VEHICLE_JUMP_TICK_SPECS: tuple[tuple[str, str], ...] = (
    ("/Script/Oak2.OakPlayerController:PlayerTick", "POST"),
    ("/Script/OakGame.OakPlayerController:PlayerTick", "POST"),
    ("/Script/GbxGame.GbxPlayerController:PlayerTick", "POST"),
    ("/Script/Engine.PlayerController:PlayerTick", "POST"),
    ("/Script/Oak2.OakPlayerController:ReceiveTick", "POST"),
    ("/Script/OakGame.OakPlayerController:ReceiveTick", "POST"),
    ("/Script/Engine.PlayerController:ReceiveTick", "POST"),
    ("/Script/Oak2.OakPlayerController:PlayerTick", "POST_UNCONDITIONAL"),
    ("/Script/OakGame.OakPlayerController:PlayerTick", "POST_UNCONDITIONAL"),
    ("/Script/Engine.PlayerController:PlayerTick", "POST_UNCONDITIONAL"),
    ("/Script/OakGame.OakVehicle:ReceiveTick", "POST"),
    ("/Script/Oak2.OakVehicle:ReceiveTick", "POST"),
    ("/Script/OakGame.OakWheeledVehicleMovementComponent:ReceiveTick", "POST"),
    ("/Script/Oak2.OakWheeledVehicleMovementComponent:ReceiveTick", "POST"),
)
_VEHICLE_DAMAGE_APPLY_HOOKS: tuple[str, ...] = (
    "/Script/Engine.GameplayStatics:ApplyDamage",
    "/Script/Engine.GameplayStatics:ApplyPointDamage",
    "/Script/Engine.GameplayStatics:ApplyRadialDamage",
)
_VEHICLE_DAMAGE_TAKE_FALLBACKS: tuple[str, ...] = (
    "/Script/Engine.Actor:TakeDamage",
    "/Script/OakGame.OakPawn:TakeDamage",
    "/Script/Oak2.OakPawn:TakeDamage",
    "/Script/OakGame.OakCharacter:TakeDamage",
    "/Script/Oak2.OakCharacter:TakeDamage",
)


def _scope_from_spinner_label(lab: str) -> str:
    for key, disp in _SCOPE_LABELS.items():
        if disp == lab:
            return key
    return "local"


def _iter_pawns_for_bvm_scope() -> list[tuple[Any, str]]:
    pcs = [p for p in _iter_pcs() if not _is_cdo(p)]
    if not pcs:
        return []
    local_pc = _get_local_pc(pcs)
    out: list[tuple[Any, str]] = []
    if BVM_APPLY_SCOPE == "local":
        pc = local_pc or pcs[0]
        pw = _try_pawn(pc)
        if pw is not None:
            out.append((pw, "local"))
        return out
    for pc in pcs:
        pw = _try_pawn(pc)
        if pw is None:
            continue
        is_loc = bool(local_pc is not None and (pc is local_pc or _is_local_pc(pc)))
        if BVM_APPLY_SCOPE == "others" and is_loc:
            continue
        label = "?"
        try:
            ps = getattr(pc, "PlayerState", None) or getattr(pc, "OakPlayerState", None)
            label = str(getattr(ps, "PlayerName", None) or getattr(pc, "Name", None) or "?")
        except Exception:
            label = str(getattr(pc, "Name", "?"))
        out.append((pw, label))
    return out


def _iter_pcs_for_bvm_scope() -> list[tuple[Any, str]]:
    pcs = [p for p in _iter_pcs() if not _is_cdo(p)]
    if not pcs:
        return []
    local_pc = _get_local_pc(pcs)
    out: list[tuple[Any, str]] = []
    if BVM_APPLY_SCOPE == "local":
        pc = local_pc or pcs[0]
        out.append((pc, "local"))
        return out
    for pc in pcs:
        is_loc = bool(local_pc is not None and (pc is local_pc or _is_local_pc(pc)))
        if BVM_APPLY_SCOPE == "others" and is_loc:
            continue
        label = "?"
        try:
            ps = getattr(pc, "PlayerState", None) or getattr(pc, "OakPlayerState", None)
            label = str(getattr(ps, "PlayerName", None) or getattr(pc, "Name", None) or "?")
        except Exception:
            label = str(getattr(pc, "Name", "?"))
        out.append((pc, label))
    return out


def _parse_attr_segment(seg: str) -> tuple[str, int | None]:
    s = seg.strip()
    m = _PATH_SEG_BRACKET_RE.match(s)
    if m:
        return m.group(1), int(m.group(2))
    return s, None


def _pawn_set_path(root: Any, path: str, value: Any) -> bool:
    parts = [p for p in path.split(".") if p]
    if not parts:
        return False
    obj: Any = root
    for part in parts[:-1]:
        name, idx = _parse_attr_segment(part)
        try:
            nxt = getattr(obj, name)
        except Exception:
            return False
        if nxt is None:
            return False
        if idx is not None:
            try:
                nxt = nxt[idx]
            except Exception:
                return False
        obj = nxt
    last = parts[-1]
    name, idx = _parse_attr_segment(last)
    if idx is not None:
        try:
            seq = getattr(obj, name)
            seq[idx] = value
            return True
        except Exception:
            return False
    try:
        setattr(obj, name, value)
        return True
    except Exception:
        return False


def _pawn_get_path(root: Any, path: str) -> Any | None:
    parts = [p for p in path.split(".") if p]
    if not parts:
        return None
    obj: Any = root
    for part in parts:
        name, idx = _parse_attr_segment(part)
        try:
            nxt = getattr(obj, name)
        except Exception:
            return None
        if nxt is None:
            return None
        if idx is not None:
            try:
                nxt = nxt[idx]
            except Exception:
                return None
        obj = nxt
    return obj


def _get_driven_vehicle_actor_from_pawn(pawn: Any) -> Any | None:
    if pawn is None:
        return None
    try:
        vdc = getattr(pawn, "VehicleDriverComponent", None)
        if vdc is None:
            for attr in ("VehicleDriver", "GbxVehicleDriverComponent", "OakVehicleDriverComponent"):
                vdc = getattr(pawn, attr, None)
                if vdc is not None:
                    break
        if vdc is None:
            if _looks_like_vehicle_actor(pawn):
                return pawn
            return None
        vds = getattr(vdc, "VehicleDriverState", None) or getattr(vdc, "DriverState", None)
        if vds is None:
            vds = vdc
        for attr in ("DrivenVehicle", "CurrentVehicle", "VehicleActor", "OccupiedVehicle", "MountedVehicle"):
            dv = getattr(vds, attr, None)
            if dv is not None:
                return dv
        for attr in ("DrivenVehicle", "CurrentVehicle", "VehicleActor", "OccupiedVehicle", "MountedVehicle"):
            dv = getattr(pawn, attr, None)
            if dv is not None:
                return dv
        if _looks_like_vehicle_actor(pawn):
            return pawn
        return None
    except Exception:
        if _looks_like_vehicle_actor(pawn):
            return pawn
        return None


def _resolve_oak_vehicle_movement_from_vehicle_actor(vehicle: Any) -> tuple[str, Any] | None:
    if vehicle is None:
        return None
    for attr in (
        "OakVehicleMovement",
        "VehicleMovement",
        "VehicleMovementComp",
        "ChaosVehicleMovement",
        "WheeledVehicleMovement",
    ):
        try:
            comp = getattr(vehicle, attr, None)
        except Exception:
            continue
        if comp is not None:
            return (f"DrivenVehicle.{attr}", comp)
    return None


def _resolve_vehicle_movement_from_pawn(pawn: Any) -> tuple[str, Any] | None:
    if pawn is None:
        return None
    dv = _get_driven_vehicle_actor_from_pawn(pawn)
    if dv is not None:
        hit = _resolve_oak_vehicle_movement_from_vehicle_actor(dv)
        if hit is not None:
            return hit
    try:
        cname = str(getattr(getattr(pawn, "Class", None), "Name", "") or "")
    except Exception:
        cname = ""
    low = cname.lower()
    looks_vehicle = any(
        x in low for x in ("vehicle", "chaos", "hover", "bike", "borg", "grazer", "drivable", "cyclone")
    )
    for attr in (
        "VehicleMovementComp",
        "VehicleMovement",
        "OakVehicleMovement",
        "GbxVehicleMovement",
        "ChaosVehicleMovement",
        "WheeledVehicleMovement",
    ):
        try:
            comp = getattr(pawn, attr, None)
        except Exception:
            continue
        if comp is not None:
            return (f"pawn.{attr}", comp)
    if looks_vehicle:
        for attr in (
            "CharacterMovement",
            "GbxCharacterMovement",
            "OakCharacterMovement",
        ):
            try:
                comp = getattr(pawn, attr, None)
            except Exception:
                continue
            if comp is not None:
                return (f"pawn.{attr}", comp)
    return None


def _iter_bvm_vehicle_hits() -> list[tuple[str, Any, Any]]:
    hits: list[tuple[str, Any, Any]] = []
    for pawn, who in _iter_pawns_for_bvm_scope():
        hit = _resolve_vehicle_movement_from_pawn(pawn)
        if hit is None:
            continue
        path, comp = hit
        hits.append((f"{path} [{who}]", pawn, comp))
    return hits


def _movement_roots_for_vehicle_jump(pawn: Any, comp: Any, vehicle: Any | None) -> list[Any]:
    roots: list[Any] = []
    seen: set[int] = set()

    def add(obj: Any) -> None:
        if obj is None:
            return
        oid = _object_identity(obj)
        if oid and oid not in seen:
            seen.add(oid)
            roots.append(obj)

    add(pawn)
    for attr in (
        "CharMoveComp",
        "CharacterMovement",
        "OakCharacterMovement",
        "GbxCharacterMovement",
        "MovementComponent",
    ):
        try:
            add(getattr(pawn, attr, None))
        except Exception:
            pass
    add(comp)
    add(vehicle)
    if vehicle is not None:
        hit = _resolve_oak_vehicle_movement_from_vehicle_actor(vehicle)
        if hit is not None:
            add(hit[1])
    return roots


def _set_nested_bcanjump(obj: Any) -> None:
    for field in ("MovementState", "NavAgentProps"):
        try:
            nested = getattr(obj, field, None)
        except Exception:
            nested = None
        if nested is None:
            continue
        try:
            if hasattr(nested, "bCanJump"):
                setattr(nested, "bCanJump", True)
        except Exception:
            continue


def _arm_vehicle_air_jump_state(pawn: Any, comp: Any, vehicle: Any | None = None) -> None:
    """BL4 vehicle jumps are ground-gated (bCanJump=false in air) — re-arm for repeat hops."""
    for obj in _movement_roots_for_vehicle_jump(pawn, comp, vehicle):
        for name, value in (
            ("JumpMaxCount", 99),
            ("JumpCurrentCount", 0),
            ("JumpCurrentCountPreJump", 0),
            ("JumpedCount", 0),
            ("bCanJump", True),
            ("bVehiclePowerslideJumping", False),
            ("bPendingSlideJump", False),
            ("bPressedJump", False),
            ("bWasJumping", False),
            ("JumpForceTimeRemaining", 0.0),
            ("ProxyJumpForceStartedTime", 0.0),
            ("bProxyIsJumpForceApplied", False),
        ):
            try:
                if hasattr(obj, name):
                    setattr(obj, name, value)
            except Exception:
                continue
        _set_nested_bcanjump(obj)
        for meth, arg in (("SetJumpMaxCount", 99), ("K2_SetJumpMaxCount", 99)):
            try:
                fn = getattr(obj, meth, None)
                if callable(fn):
                    fn(arg)
            except Exception:
                pass


def _reset_vehicle_first_jump_state(pawn: Any, comp: Any, vehicle: Any | None = None) -> None:
    _arm_vehicle_air_jump_state(pawn, comp, vehicle)


def _read_gbx_init_constant(obj: Any, attr: str) -> float | None:
    if obj is None:
        return None
    try:
        field = getattr(obj, attr, None)
    except Exception:
        return None
    if field is None:
        return None
    try:
        value = getattr(field, "constant", None)
    except Exception:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _read_hover_setup_scalar(comp: Any, attr: str) -> float | None:
    hover = getattr(comp, "HoverSetup", None)
    if hover is not None:
        value = _read_gbx_init_constant(hover, attr)
        if value is not None:
            return value
    return _read_gbx_init_constant(comp, attr)


def _read_hover_setup_plain(comp: Any, attr: str) -> float | None:
    for root in (getattr(comp, "HoverSetup", None), comp):
        if root is None:
            continue
        try:
            value = getattr(root, attr, None)
        except Exception:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _vehicle_jump_strength(pawn: Any, comp: Any) -> float:
    live = _read_vehicle_field(pawn, comp, "PowerslideJumpHeight")
    if live is not None and live > 0:
        return float(live)
    hover = _read_hover_setup_scalar(comp, "PowerslideJumpHeight")
    if hover is not None and hover > 0:
        return hover
    for option, spec in zip(_slider_jump, _JUMP_SPECS, strict=True):
        if spec[0] == "PowerslideJumpHeight":
            try:
                return float(option.value)
            except Exception:
                break
    return 165.0


def _arm_vehicle_jump_minimal(comp: Any) -> None:
    for name, value in (
        ("JumpMaxCount", 99),
        ("JumpCurrentCount", 0),
        ("bCanJump", True),
    ):
        try:
            if hasattr(comp, name):
                setattr(comp, name, value)
        except Exception:
            continue


def _slider_jump_height() -> float:
    for option, spec in zip(_slider_jump, _JUMP_SPECS, strict=True):
        if spec[0] == "PowerslideJumpHeight":
            try:
                return float(option.value)
            except Exception:
                break
    return 165.0


def _slider_jump_gravity() -> float:
    for option, spec in zip(_slider_jump, _JUMP_SPECS, strict=True):
        if spec[0] == "PowerslideJumpGravityScalar":
            try:
                return float(option.value)
            except Exception:
                break
    return 8.0


def _compute_dump_jump_launch_vz_fast(comp: Any) -> float:
    """HoverSetup only — avoids find_all / driver scans on every key press."""
    global _cached_launch_vz, _cached_launch_vz_key
    comp_id = _object_identity(comp)
    height = _read_hover_setup_scalar(comp, "PowerslideJumpHeight")
    if height is None or height <= 0:
        height = _slider_jump_height()
    grav = _read_hover_setup_scalar(comp, "PowerslideJumpGravityScalar")
    if grav is None or grav <= 0:
        grav = _slider_jump_gravity()
    cache_key = comp_id ^ (int(height * 4) << 16) ^ int(grav * 1000)
    if _cached_launch_vz is not None and _cached_launch_vz_key == cache_key:
        return _cached_launch_vz
    g = 980.0 * max(0.25, abs(float(grav)))
    launch = (2.0 * g * max(1.0, float(height))) ** 0.5
    hover = getattr(comp, "HoverSetup", None)
    if hover is not None:
        limits = getattr(hover, "VelocityLimitZUp", None)
        if limits is not None:
            soft = getattr(limits, "SoftLimit", None)
            if isinstance(soft, (int, float)) and float(soft) > 100.0:
                launch = min(launch, float(soft))
    if _last_sampled_launch_vz is not None and _last_sampled_launch_vz > launch * 0.75:
        launch = float(_last_sampled_launch_vz)
    launch = max(400.0, launch)
    _cached_launch_vz = launch
    _cached_launch_vz_key = cache_key
    return launch


def _resolve_jump_mesh(vehicle: Any | None, pawn: Any | None, comp: Any) -> Any | None:
    mesh = _cached_jump_mesh
    if mesh is not None and _ue_object_usable(mesh):
        return mesh
    mesh = _cached_vehicle_mesh(vehicle or pawn, comp)
    if mesh is not None:
        return mesh
    for root in (vehicle, pawn):
        if root is None:
            continue
        try:
            candidate = getattr(root, "VehicleMesh", None)
        except Exception:
            candidate = None
        if candidate is not None and _ue_object_usable(candidate):
            return candidate
    return None


def _vehicle_jump_in_air(comp: Any, vehicle: Any | None) -> bool:
    if _jump_air_session:
        return True
    return _vehicle_in_air_loose(comp, vehicle)


def _vehicle_jump_keybind_cooldown() -> float:
    return 0.08


def _vehicle_jump_tick_cooldown() -> float:
    try:
        return max(0.08, min(1.0, float(_jump_repeat_interval_opt.value)))
    except Exception:
        return 0.08


def _fast_mesh_launch(
    vehicle: Any | None, pawn: Any | None, comp: Any, target_vz: float
) -> bool:
    mesh = _resolve_jump_mesh(vehicle, pawn, comp)
    if mesh is None:
        return False
    try:
        get_velocity = getattr(mesh, "GetPhysicsLinearVelocity", None)
        set_velocity = getattr(mesh, "SetPhysicsLinearVelocity", None)
    except Exception:
        return False
    if not callable(get_velocity) or not callable(set_velocity):
        return False
    try:
        current = get_velocity("None")
    except Exception:
        try:
            current = get_velocity()
        except Exception:
            current = None
    if current is None:
        return False
    velocity = unrealsdk.make_struct(
        "Vector",
        X=float(getattr(current, "X", 0.0)),
        Y=float(getattr(current, "Y", 0.0)),
        Z=float(target_vz),
    )
    try:
        set_velocity(velocity, False, "None")
        return True
    except (TypeError, ValueError):
        pass
    except Exception:
        return False
    try:
        set_velocity(velocity, False)
        return True
    except Exception:
        return False


def _apply_vehicle_jump_fast(*, reset_first: bool = True) -> bool:
    if BVM_APPLY_SCOPE == "local" and not _local_player_is_driving():
        return False
    pc = _get_local_pc()
    pawn = _try_pawn(pc) if pc is not None else None
    hit = _resolve_vehicle_movement_from_pawn(pawn) if pawn is not None else None
    if hit is None:
        return False
    _path, comp = hit
    vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
    if vehicle is None and pawn is not None and _looks_like_vehicle_actor(pawn):
        vehicle = pawn
    if pawn is None:
        pawn = vehicle
    if comp is None or not _ue_object_usable(comp):
        return False
    global _cached_jump_comp, _cached_jump_vehicle, _cached_jump_pawn_id, _last_jump_cache_at
    _cached_jump_comp = comp
    _cached_jump_vehicle = vehicle
    _cached_jump_pawn_id = _object_identity(pawn)
    _last_jump_cache_at = time.monotonic()
    _cached_vehicle_mesh(vehicle, comp)
    return _execute_vehicle_jump(
        pawn, comp, vehicle, reset_first=reset_first, fast=True
    )


def _compute_dump_jump_launch_vz(pawn: Any, comp: Any) -> float:
    """Ballistic launch speed from HoverSetup jump height + gravity (OakVehicle dump)."""
    return _compute_dump_jump_launch_vz_fast(comp)


def _jump_lift_verified(before: float | None, after: float | None, target_vz: float) -> bool:
    if after is None:
        return False
    if before is not None and after > before + 70.0:
        return True
    return after >= target_vz * 0.55


def _prime_powerslide_jump_input(comp: Any) -> None:
    threshold = max(60.0, _read_powerslide_threshold(comp))
    try:
        setattr(comp, "PowerslideInput", threshold)
    except Exception:
        pass
    for attr, value in (("bPendingSlideJump", True), ("bVehiclePowerslideJumping", False)):
        try:
            if hasattr(comp, attr):
                setattr(comp, attr, value)
        except Exception:
            continue


def _clear_powerslide_jump_input(comp: Any) -> None:
    try:
        setattr(comp, "PowerslideInput", 0.0)
    except Exception:
        pass


def _wake_vehicle_physics(mesh: Any) -> None:
    for meth in ("WakeAllRigidBodies", "WakeRigidBody"):
        try:
            fn = getattr(mesh, meth, None)
        except Exception:
            fn = None
        if callable(fn):
            try:
                fn()
                return
            except Exception:
                continue


def _set_mesh_launch_vz(mesh: Any, target_vz: float) -> bool:
    if not _ue_object_usable(mesh):
        return False
    _wake_vehicle_physics(mesh)
    before = _read_physics_body_vz(mesh)
    try:
        get_velocity = getattr(mesh, "GetPhysicsLinearVelocity", None)
        set_velocity = getattr(mesh, "SetPhysicsLinearVelocity", None)
    except Exception:
        return False
    if not callable(get_velocity) or not callable(set_velocity):
        return False
    try:
        current = get_velocity("None")
    except Exception:
        try:
            current = get_velocity()
        except Exception:
            current = None
    if current is None:
        return False
    velocity = unrealsdk.make_struct(
        "Vector",
        X=float(getattr(current, "X", 0.0)),
        Y=float(getattr(current, "Y", 0.0)),
        Z=float(target_vz),
    )
    for call_args in ((velocity, False, "None"), (velocity, False), (velocity,)):
        try:
            set_velocity(*call_args)
        except (TypeError, ValueError):
            continue
        except Exception:
            break
        after = _read_physics_body_vz(mesh)
        if _jump_lift_verified(before, after, target_vz):
            return True
    impulse = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=float(target_vz))
    try:
        add_impulse = getattr(mesh, "AddImpulse", None)
    except Exception:
        add_impulse = None
    if callable(add_impulse):
        for args in ((impulse, "None", True), (impulse, True), (impulse,)):
            try:
                add_impulse(*args)
            except (TypeError, ValueError):
                continue
            except Exception:
                break
            after = _read_physics_body_vz(mesh)
            if _jump_lift_verified(before, after, target_vz):
                return True
    return False


def _apply_dump_physics_jump(
    pawn: Any, comp: Any, vehicle: Any | None, target_vz: float
) -> bool:
    for obj in _collect_vehicle_physics_bodies(pawn, comp, vehicle):
        if _set_mesh_launch_vz(obj, target_vz):
            return True
    mesh = _cached_vehicle_mesh(vehicle or pawn, comp)
    if mesh is not None and _set_mesh_launch_vz(mesh, target_vz):
        return True
    if vehicle is not None:
        try:
            launch = getattr(vehicle, "LaunchCharacter", None)
        except Exception:
            launch = None
        if callable(launch):
            impulse = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=float(target_vz))
            before = _vehicle_mesh_vz(comp, vehicle, refresh=True)
            try:
                launch(impulse, False, False)
            except Exception:
                pass
            after = _vehicle_mesh_vz(comp, vehicle, refresh=True)
            if _jump_lift_verified(before, after, target_vz):
                return True
    return False


def _try_native_powerslide_jump_verified(
    pawn: Any, comp: Any, vehicle: Any | None, target_vz: float
) -> bool:
    before = _vehicle_mesh_vz(comp, vehicle, refresh=True)
    _prime_powerslide_jump_input(comp)
    for obj in (comp, vehicle):
        if obj is None:
            continue
        try:
            fn = getattr(obj, "PowerslideCooldownElapsed", None)
        except Exception:
            fn = None
        if not callable(fn):
            continue
        try:
            fn()
        except Exception:
            continue
        break
    _clear_powerslide_jump_input(comp)
    after = _vehicle_mesh_vz(comp, vehicle, refresh=True)
    if _jump_lift_verified(before, after, target_vz):
        if after is not None and after > 60.0:
            global _last_sampled_launch_vz
            _last_sampled_launch_vz = after
        return True
    return False


def _execute_vehicle_jump(
    pawn: Any,
    comp: Any,
    vehicle: Any | None = None,
    *,
    reset_first: bool = True,
    fast: bool = False,
) -> bool:
    global _jump_air_session, _jump_air_session_grace, _last_sampled_launch_vz
    if vehicle is None:
        vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
        if vehicle is None and _looks_like_vehicle_actor(pawn):
            vehicle = pawn
    target_vz = _compute_dump_jump_launch_vz_fast(comp)
    in_air = _vehicle_jump_in_air(comp, vehicle)
    if fast:
        if reset_first:
            if in_air:
                _arm_vehicle_air_jump_state(pawn, comp, vehicle)
            else:
                _arm_vehicle_jump_minimal(comp)
        if in_air:
            mesh = _resolve_jump_mesh(vehicle, pawn, comp)
            if mesh is not None and _apply_verified_mesh_lift(mesh, target_vz, verify=True):
                _last_sampled_launch_vz = target_vz
                _jump_air_session = True
                _jump_air_session_grace = 18
                return True
            if _try_native_powerslide_jump_verified(pawn, comp, vehicle, target_vz):
                vz = _vehicle_mesh_vz(comp, vehicle, refresh=False)
                if vz is not None and vz > 60.0:
                    _last_sampled_launch_vz = vz
                _jump_air_session = True
                _jump_air_session_grace = 18
                return True
            return False
        if not _fast_mesh_launch(vehicle, pawn, comp, target_vz):
            return False
        _last_sampled_launch_vz = target_vz
        _jump_air_session = True
        _jump_air_session_grace = 18
        return True
    if reset_first:
        _arm_vehicle_air_jump_state(pawn, comp, vehicle)
    jumped = _try_native_powerslide_jump_verified(pawn, comp, vehicle, target_vz)
    if not jumped:
        mesh = _resolve_jump_mesh(vehicle, pawn, comp)
        if in_air and mesh is not None:
            jumped = _apply_verified_mesh_lift(mesh, target_vz, verify=True)
        if not jumped:
            jumped = _apply_dump_physics_jump(pawn, comp, vehicle, target_vz)
    if not jumped:
        return False
    vz = _vehicle_mesh_vz(comp, vehicle, refresh=False)
    if vz is not None and vz > 60.0:
        _last_sampled_launch_vz = vz
    _jump_air_session = True
    _jump_air_session_grace = 18
    for obj in (vehicle, pawn):
        if obj is None:
            continue
        try:
            setattr(obj, "bVehiclePowerslideJumping", True)
        except Exception:
            pass
    return True


def _trigger_native_powerslide_jump(
    pawn: Any,
    comp: Any,
    vehicle: Any | None = None,
    *,
    reset_first: bool = True,
) -> bool:
    return _execute_vehicle_jump(pawn, comp, vehicle, reset_first=reset_first)


def _trigger_vehicle_first_jump(
    pawn: Any,
    comp: Any,
    *,
    reset_first: bool = True,
    velocity_fallback: bool = True,
) -> bool:
    vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
    if vehicle is None and _looks_like_vehicle_actor(pawn):
        vehicle = pawn
    if reset_first:
        _reset_vehicle_first_jump_state(pawn, comp, vehicle)
    for obj in (comp, vehicle, pawn):
        if obj is None:
            continue
        for method in (
            "Jump",
            "DoJump",
            "StartJump",
            "PerformJump",
            "TryJump",
            "VehicleJump",
            "PowerslideJump",
            "TryPowerslideJump",
            "ExecuteJump",
        ):
            try:
                fn = getattr(obj, method, None)
            except Exception:
                fn = None
            if not callable(fn):
                continue
            for args in ((), (True,), (False,)):
                try:
                    fn(*args)
                    return True
                except (TypeError, ValueError):
                    continue
                except Exception:
                    break
    if not velocity_fallback:
        return False
    strength = _vehicle_jump_strength(pawn, comp)
    return _try_movement_component_jump(pawn, comp, strength)


def _read_physics_body_vz(obj: Any) -> float | None:
    if not _ue_object_usable(obj):
        return None
    try:
        get_velocity = getattr(obj, "GetPhysicsLinearVelocity", None)
    except Exception:
        return None
    if not callable(get_velocity):
        return None
    try:
        current = get_velocity("None")
    except Exception:
        try:
            current = get_velocity()
        except Exception:
            current = None
    if current is None:
        return None
    try:
        return float(getattr(current, "Z", 0.0))
    except Exception:
        return None


def _apply_verified_mesh_lift(obj: Any, strength: float, *, verify: bool = True) -> bool:
    if not _ue_object_usable(obj):
        return False
    before = _read_physics_body_vz(obj)
    try:
        get_velocity = getattr(obj, "GetPhysicsLinearVelocity", None)
        set_velocity = getattr(obj, "SetPhysicsLinearVelocity", None)
    except Exception:
        get_velocity = set_velocity = None
    if callable(get_velocity) and callable(set_velocity):
        try:
            current = get_velocity("None")
        except Exception:
            try:
                current = get_velocity()
            except Exception:
                current = None
        if current is not None:
            base_z = before if before is not None else float(getattr(current, "Z", 0.0))
            launch_z = max(base_z, 0.0) + float(strength)
            velocity = unrealsdk.make_struct(
                "Vector",
                X=float(getattr(current, "X", 0.0)),
                Y=float(getattr(current, "Y", 0.0)),
                Z=launch_z,
            )
            for call_args in ((velocity, False, "None"), (velocity, False), (velocity,)):
                try:
                    set_velocity(*call_args)
                    after = _read_physics_body_vz(obj)
                    if not verify:
                        return True
                    if after is not None and after >= launch_z - min(float(strength) * 0.05, 35.0):
                        return True
                except (TypeError, ValueError):
                    continue
                except Exception:
                    break
    impulse = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=float(strength))
    try:
        add_impulse = getattr(obj, "AddImpulse", None)
    except Exception:
        add_impulse = None
    if callable(add_impulse):
        for args in ((impulse, "None", True), (impulse, True), (impulse,)):
            try:
                add_impulse(*args)
                after = _read_physics_body_vz(obj)
                if not verify:
                    return True
                if after is not None and (before is None or after > before + 20.0):
                    return True
            except (TypeError, ValueError):
                continue
            except Exception:
                break
    return False


def _vehicle_comp_airborne(comp: Any, vehicle: Any | None) -> bool:
    for obj in (comp, vehicle):
        if obj is None:
            continue
        for meth in ("IsFalling",):
            try:
                fn = getattr(obj, meth, None)
            except Exception:
                fn = None
            if callable(fn):
                try:
                    if bool(fn()):
                        return True
                except Exception:
                    pass
        for meth in ("IsMovingOnGround",):
            try:
                fn = getattr(obj, meth, None)
            except Exception:
                fn = None
            if callable(fn):
                try:
                    if not bool(fn()):
                        return True
                except Exception:
                    pass
        for attr in ("bVehicleAirborne", "bVehiclePowerslideJumping"):
            try:
                if bool(getattr(obj, attr, False)):
                    return True
            except Exception:
                pass
    mesh = _cached_vehicle_mesh(vehicle, comp)
    if mesh is not None:
        vz = _read_physics_body_vz(mesh)
        if vz is not None and abs(vz) > 15.0:
            return True
    return False


def _vehicle_firmly_on_ground(comp: Any, vehicle: Any | None) -> bool:
    grounded = False
    for obj in (comp, vehicle):
        if obj is None:
            continue
        try:
            fn = getattr(obj, "IsMovingOnGround", None)
        except Exception:
            fn = None
        if callable(fn):
            try:
                grounded = bool(fn())
            except Exception:
                continue
            break
    if not grounded:
        return False
    mesh = _cached_vehicle_mesh(vehicle, comp)
    if mesh is not None:
        vz = _read_physics_body_vz(mesh)
        if vz is not None and abs(vz) > 120.0:
            return False
    return True

def _vehicle_mesh_vz(comp: Any, vehicle: Any | None, *, refresh: bool = False) -> float | None:
    _refresh_jump_runtime_cache(force=refresh)
    mesh = _cached_jump_mesh or _cached_vehicle_mesh(vehicle, comp)
    if mesh is None:
        return None
    return _read_physics_body_vz(mesh)


def _vehicle_in_air_loose(comp: Any, vehicle: Any | None, vz: float | None = None) -> bool:
    if vz is None:
        vz = _vehicle_mesh_vz(comp, vehicle)
    if vz is not None:
        return vz > 4.0 or vz < -6.0
    return _vehicle_comp_airborne(comp, vehicle)


def _vehicle_jump_vz_is_airborne(vz: float | None) -> bool:
    return vz is not None and (vz > 3.5 or vz < -5.0)


def _maintain_vehicle_jump_chain(
    comp: Any, vehicle: Any | None, now: float, vz: float | None = None
) -> bool:
    """Sticky air window on PlayerTick — never repeat-hop on the ground."""
    global _jump_chain_active, _jump_chain_grace, _jump_repeat_latched
    global _jump_air_session, _jump_air_session_until
    if vz is None:
        vz = _vehicle_mesh_vz(comp, vehicle)
    if _vehicle_jump_vz_is_airborne(vz):
        _jump_air_session = True
        _jump_air_session_until = max(_jump_air_session_until, now + 0.45)
    in_window = _jump_air_session and now < _jump_air_session_until
    if not in_window:
        settled = vz is not None and abs(vz) < 3.5
        if settled and not _jump_key_is_down():
            _jump_chain_active = False
            _jump_repeat_latched = False
            _jump_air_session = False
        return False
    _jump_chain_active = True
    _jump_chain_grace = 30
    return True


def _log_jump_chain_status(comp: Any, vehicle: Any | None, *, chain: bool, delay: float, now: float) -> None:
    global _last_jump_chain_log_at
    if now - _last_jump_chain_log_at < 2.0:
        return
    _last_jump_chain_log_at = now
    vz = _vehicle_mesh_vz(comp, vehicle)
    _info(
        f"Unlimited vehicle jump: chain={chain} in_air={_vehicle_in_air_loose(comp, vehicle)} "
        f"vz={vz} next_in={max(0.0, delay - (now - _last_custom_jump_at)):.2f}s"
    )




def _update_jump_air_session(comp: Any, vehicle: Any | None) -> bool:
    """Stay in-air for repeat hops through apex and brief wheel contacts."""
    global _jump_air_session, _jump_air_session_grace, _was_vehicle_on_ground
    if _vehicle_comp_airborne(comp, vehicle):
        if not _jump_air_session:
            _was_vehicle_on_ground = True
        _jump_air_session = True
        _jump_air_session_grace = 18
        return True
    if _jump_air_session:
        if _vehicle_firmly_on_ground(comp, vehicle):
            _jump_air_session_grace -= 1
            if _jump_air_session_grace <= 0:
                _jump_air_session = False
        else:
            _jump_air_session_grace = 18
        return _jump_air_session
    return False


def _collect_vehicle_physics_bodies(
    pawn: Any, comp: Any, vehicle: Any | None
) -> list[Any]:
    bodies: list[Any] = []
    seen: set[int] = set()

    def add(obj: Any) -> None:
        if obj is None or not _ue_object_usable(obj):
            return
        oid = _object_identity(obj)
        if oid and oid not in seen:
            seen.add(oid)
            bodies.append(obj)

    for root in (vehicle, comp, pawn):
        if root is None:
            continue
        for name in (
            "VehicleMesh",
            "Mesh",
            "UpdatedComponent",
            "RootPrimitiveComponent",
            "RootComponent",
        ):
            try:
                add(getattr(root, name, None))
            except Exception:
                continue
        try:
            get_updated = getattr(root, "GetUpdatedComponent", None)
            if callable(get_updated):
                add(get_updated())
        except Exception:
            pass
    return bodies


def _apply_vehicle_physics_jump(
    pawn: Any,
    comp: Any,
    vehicle: Any | None,
    strength: float,
    *,
    verify: bool = False,
) -> bool:
    for obj in _collect_vehicle_physics_bodies(pawn, comp, vehicle):
        if _apply_verified_mesh_lift(obj, strength, verify=verify):
            return True
    if vehicle is not None:
        try:
            launch = getattr(vehicle, "LaunchCharacter", None)
        except Exception:
            launch = None
        if callable(launch):
            impulse = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=float(strength))
            try:
                launch(impulse, False, False)
                mesh = _cached_vehicle_mesh(vehicle, comp)
                if mesh is not None and _read_physics_body_vz(mesh) is not None:
                    return True
            except Exception:
                pass
    return False


def _apply_vehicle_physics_lift(
    pawn: Any, comp: Any, vehicle: Any | None, lift: float
) -> bool:
    return _apply_vehicle_physics_jump(pawn, comp, vehicle, lift)


def _log_repeat_jump(message: str) -> None:
    global _last_repeat_jump_log_at
    now = time.monotonic()
    if now - _last_repeat_jump_log_at < 1.5:
        return
    _last_repeat_jump_log_at = now
    _info(message)


def _trigger_vehicle_repeat_jump(pawn: Any, comp: Any) -> bool:
    return _apply_custom_vehicle_jump(log_result=False) > 0


def _mod_jump_key_names() -> tuple[str, ...]:
    """Key names from the mod's Vehicle jump keybind setting."""
    try:
        raw = str(getattr(KEY_VEHICLE_JUMP, "key", "") or "").strip()
    except Exception:
        raw = ""
    if not raw or raw.lower() in {"none", "unbound", ""}:
        return ()
    names: list[str] = [raw, raw.replace(" ", "")]
    if len(raw) == 1 and raw.isalpha():
        names.append(raw.upper())
    low = raw.casefold()
    if low in {"space", "spacebar", "space bar"}:
        names.extend(("SpaceBar", "Space"))
    return tuple(dict.fromkeys(n for n in names if n))


def _vehicle_jump_key_candidates() -> tuple[str, ...]:
    """SpaceBar (game jump) plus optional vehicle jump keybind — both always checked."""
    names: list[str] = ["SpaceBar", "Space"]
    for name in _mod_jump_key_names():
        if name not in names:
            names.append(name)
    return tuple(names)


def _jump_key_name_candidates() -> tuple[str, ...]:
    return _vehicle_jump_key_candidates()


def _key_down_by_name(name: str) -> bool:
    pc = _get_local_pc()
    if pc is None:
        return False
    try:
        key = unrealsdk.make_struct("Key", KeyName=name)
        if bool(pc.IsInputKeyDown(key)):
            return True
    except Exception:
        pass
    pi = getattr(pc, "PlayerInput", None)
    if pi is not None:
        try:
            key = unrealsdk.make_struct("Key", KeyName=name)
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


def _space_bar_down() -> bool:
    for name in ("SpaceBar", "Space"):
        if _key_down_by_name(name):
            return True
    return False


def _mod_jump_key_down() -> bool:
    for name in _mod_jump_key_names():
        if _key_down_by_name(name):
            return True
    return False


def _vehicle_jump_down() -> bool:
    return _space_bar_down() or _mod_jump_key_down()


def _space_only_pressed_edge() -> bool:
    global _space_key_was_down
    down = _space_bar_down()
    pressed = down and not _space_key_was_down
    _space_key_was_down = down
    if pressed:
        return True
    pc = _get_local_pc()
    if pc is None:
        return False
    fn = getattr(pc, "WasInputKeyJustPressed", None)
    if not callable(fn):
        return False
    for name in ("SpaceBar", "Space"):
        try:
            key = unrealsdk.make_struct("Key", KeyName=name)
            if bool(fn(key)):
                _space_key_was_down = True
                return True
        except Exception:
            continue
    return False


def _mod_only_pressed_edge() -> bool:
    global _mod_key_was_down
    down = _mod_jump_key_down()
    pressed = down and not _mod_key_was_down
    _mod_key_was_down = down
    return pressed


def _vehicle_jump_pressed_edge() -> bool:
    global _jump_key_was_down
    down = _vehicle_jump_down()
    pressed = down and not _jump_key_was_down
    _jump_key_was_down = down
    if pressed:
        return True
    pc = _get_local_pc()
    if pc is None:
        return False
    fn = getattr(pc, "WasInputKeyJustPressed", None)
    if not callable(fn):
        return False
    for name in _vehicle_jump_key_candidates():
        try:
            key = unrealsdk.make_struct("Key", KeyName=name)
            if bool(fn(key)):
                _jump_key_was_down = True
                return True
        except Exception:
            continue
    return False


def _consume_mod_jump_pending() -> bool:
    global _mod_jump_pending
    if _mod_jump_pending:
        _mod_jump_pending = False
        return True
    return False


def _consume_space_jump_pending() -> bool:
    global _space_jump_pending
    if _space_jump_pending:
        _space_jump_pending = False
        return True
    return False


def _space_down() -> bool:
    return _vehicle_jump_down()


def _space_pressed_edge() -> bool:
    return _vehicle_jump_pressed_edge() or _consume_mod_jump_pending()


def _powerslide_input_edge(comp: Any) -> bool:
    global _psi_active_was
    active = _powerslide_input_active(comp)
    edge = active and not _psi_active_was
    _psi_active_was = active
    return edge


def _is_local_vehicle_movement_comp(comp: Any) -> bool:
    if comp is None or not _ue_object_usable(comp):
        return False
    pc = _get_local_pc()
    pawn = _try_pawn(pc) if pc is not None else None
    if pawn is None:
        return False
    owner = None
    try:
        get_owner = getattr(comp, "GetOwner", None)
        if callable(get_owner):
            owner = get_owner()
    except Exception:
        owner = None
    if owner is None:
        try:
            owner = getattr(comp, "Owner", None)
        except Exception:
            owner = None
    oid = _object_identity(owner)
    if oid and oid == _object_identity(pawn):
        return True
    vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
    if vehicle is not None and oid == _object_identity(vehicle):
        return True
    if _looks_like_vehicle_actor(pawn):
        hit = _resolve_oak_vehicle_movement_from_vehicle_actor(pawn)
        if hit is not None and _object_identity(hit[1]) == _object_identity(comp):
            return True
    return False


def _vehicle_owner_from_comp(comp: Any) -> Any | None:
    try:
        get_owner = getattr(comp, "GetOwner", None)
        if callable(get_owner):
            owner = get_owner()
            if owner is not None:
                return owner
    except Exception:
        pass
    try:
        return getattr(comp, "Owner", None)
    except Exception:
        return None


def _apply_custom_vehicle_jump_on_comp(comp: Any, *, log_result: bool = False) -> bool:
    if not _is_local_vehicle_movement_comp(comp):
        return False
    vehicle = _vehicle_owner_from_comp(comp)
    pawn = _try_pawn(_get_local_pc())
    if pawn is None:
        pawn = vehicle
    launch_vz = _compute_dump_jump_launch_vz_fast(comp)
    if _execute_vehicle_jump(pawn, comp, vehicle, fast=True):
        if log_result:
            _info(f"Vehicle jump ok (launch_vz≈{launch_vz:.0f}).")
        return True
    if log_result:
        _warn_jump_once(
            f"Vehicle jump failed — in vehicle? (target vz≈{launch_vz:.0f})"
        )
    return False


def _powerslide_jump_hook(caller: Any, *args: Any, **kwargs: Any) -> None:
    """Native jump just executed — sample launch speed and re-arm for mid-air repeats only."""
    global _last_custom_jump_at, _last_native_jump_at, _last_sampled_launch_vz
    global _jump_air_session, _jump_air_session_grace
    comp = caller
    if not _is_local_vehicle_movement_comp(comp):
        return
    now = time.monotonic()
    vehicle = _vehicle_owner_from_comp(comp)
    pawn = _try_pawn(_get_local_pc()) or vehicle
    _last_native_jump_at = now
    _last_custom_jump_at = now
    _jump_air_session = True
    _jump_air_session_grace = 18
    vz = _vehicle_mesh_vz(comp, vehicle, refresh=True)
    if vz is not None and vz > 60.0:
        _last_sampled_launch_vz = vz
    if BVM_REPEAT_JUMP_PRESS:
        _arm_vehicle_air_jump_state(pawn, comp, vehicle)


def _sync_vehicle_powerslide_hooks() -> None:
    global _vehicle_powerslide_hook_paths
    want = bool(_BVM_MOD_ACTIVE)
    if not want:
        for path, hook_id in list(_vehicle_powerslide_hook_paths):
            try:
                if hooks.has_hook(path, hooks.Type.POST, hook_id):
                    hooks.remove_hook(path, hooks.Type.POST, hook_id)
            except Exception:
                pass
        _vehicle_powerslide_hook_paths = []
        return
    if _vehicle_powerslide_hook_paths:
        return
    registered: list[tuple[str, str]] = []
    for candidate in _POWERSLIDE_JUMP_HOOKS:
        try:
            if hooks.add_hook(candidate, hooks.Type.POST, _VEHICLE_POWERSLIDE_HOOK_ID, _powerslide_jump_hook):
                registered.append((candidate, _VEHICLE_POWERSLIDE_HOOK_ID))
        except Exception:
            continue
    _vehicle_powerslide_hook_paths = registered


def _read_powerslide_input(obj: Any) -> float:
    if obj is None:
        return 0.0
    try:
        return float(getattr(obj, "PowerslideInput", 0) or 0)
    except Exception:
        return 0.0


def _read_powerslide_threshold(obj: Any) -> float:
    if obj is None:
        return 1.0
    try:
        return float(getattr(obj, "PowerslideInputThreshold", 1.0) or 1.0)
    except Exception:
        return 1.0


def _powerslide_input_active(obj: Any, *, threshold: float | None = None) -> bool:
    psi = _read_powerslide_input(obj)
    if threshold is None:
        threshold = _read_powerslide_threshold(obj)
    if threshold > 1.0:
        return psi >= threshold * 0.85
    return psi >= max(threshold, 0.5)


def _char_move_b_pressed(pawn: Any, comp: Any, vehicle: Any | None = None) -> bool:
    for root in _movement_roots_for_vehicle_jump(pawn, comp, vehicle):
        try:
            if bool(getattr(root, "bPressedJump", False)):
                return True
        except Exception:
            continue
    return False


def _reset_vehicle_jump_input_state() -> None:
    global _jump_b_pressed_was, _jump_key_was_down, _comp_jump_was_down
    global _vehicle_jump_down_latched, _vehicle_jump_pressed_pending
    global _psi_active_was, _mod_jump_pending, _space_jump_pending
    global _space_key_was_down, _mod_key_was_down
    _jump_b_pressed_was = False
    _jump_key_was_down = False
    _comp_jump_was_down = False
    _vehicle_jump_down_latched = False
    _vehicle_jump_pressed_pending = False
    _psi_active_was = False
    _mod_jump_pending = False
    _space_jump_pending = False
    _space_key_was_down = False
    _mod_key_was_down = False


def _movement_comp_jump_down(pawn: Any, comp: Any, vehicle: Any | None = None) -> bool:
    return _char_move_b_pressed(pawn, comp, vehicle) or _jump_key_is_down()


def _vehicle_jump_input_down(pawn: Any, comp: Any, vehicle: Any | None = None) -> bool:
    if _movement_comp_jump_down(pawn, comp, vehicle):
        return True
    return _jump_key_is_down()


def _vehicle_jump_input_pressed(pawn: Any, comp: Any, vehicle: Any | None = None) -> bool:
    global _comp_jump_was_down, _jump_key_was_down
    down = _vehicle_jump_input_down(pawn, comp, vehicle)
    pressed = down and not _comp_jump_was_down
    _comp_jump_was_down = down
    _jump_key_was_down = down
    if pressed:
        return True
    if _jump_key_just_pressed():
        _comp_jump_was_down = True
        _jump_key_was_down = True
        return True
    return False


def _jump_key_is_down() -> bool:
    return _space_down()


def _jump_key_just_pressed() -> bool:
    return _space_pressed_edge()


def _consume_vehicle_jump_press() -> bool:
    """SpaceBar press edge for repeat hops."""
    return _space_pressed_edge()


def _update_jump_repeat_latch(now: float) -> bool:
    global _jump_repeat_latched
    if _jump_key_is_down() or _jump_key_just_pressed():
        _jump_repeat_latched = True
        return True
    return _jump_repeat_latched


def _clear_jump_repeat_latch() -> None:
    global _jump_repeat_latched, _was_vehicle_on_ground
    global _jump_air_session, _jump_air_session_grace, _jump_repeat_armed
    global _jump_air_session_until
    _jump_repeat_latched = False
    _reset_vehicle_jump_input_state()
    _was_vehicle_on_ground = True
    _jump_air_session = False
    _jump_air_session_grace = 0
    _jump_air_session_until = 0.0
    _jump_repeat_armed = False
    _vehicle_jump_was_in_air = False
    _jump_chain_active = False
    _jump_chain_grace = 0
    _clear_jump_runtime_cache()


def _local_player_is_driving() -> bool:
    pc = _get_local_pc()
    if pc is None:
        return False
    pawn = _try_pawn(pc)
    if pawn is None:
        return False
    if _get_driven_vehicle_actor_from_pawn(pawn) is not None:
        return True
    return _resolve_vehicle_movement_from_pawn(pawn) is not None


def _warn_jump_once(message: str) -> None:
    global _last_jump_warn_at
    now = time.monotonic()
    if now - _last_jump_warn_at < _JUMP_WARN_COOLDOWN:
        return
    _last_jump_warn_at = now
    _warn(message)


def _try_movement_component_jump(pawn: Any, comp: Any, strength: float) -> bool:
    applied = False
    if _write_vehicle_field(pawn, comp, "JumpZVelocity", strength):
        applied = True
    for obj in (comp, pawn):
        if obj is None:
            continue
        for method in ("Jump", "DoJump", "StartJump", "PerformJump", "TryJump"):
            try:
                fn = getattr(obj, method, None)
            except Exception:
                fn = None
            if not callable(fn):
                continue
            for args in ((), (True,), (False,)):
                try:
                    fn(*args)
                    return True
                except (TypeError, ValueError):
                    continue
                except Exception:
                    break
    return applied


def _ue_object_usable(obj: Any) -> bool:
    if obj is None:
        return False
    try:
        addr = int(getattr(obj, "_get_address", lambda: 0)() or 0)
        if addr <= 0 or addr == 0xFFFFFFFFFFFFFFFF:
            return False
    except Exception:
        pass
    return True


def _clear_jump_runtime_cache() -> None:
    global _cached_jump_mesh_id, _cached_jump_mesh, _cached_jump_pawn_id
    global _cached_jump_comp, _cached_jump_vehicle, _last_jump_cache_at
    global _cached_launch_vz, _cached_launch_vz_key
    _cached_jump_mesh_id = 0
    _cached_jump_mesh = None
    _cached_jump_pawn_id = 0
    _cached_jump_comp = None
    _cached_jump_vehicle = None
    _cached_launch_vz = None
    _cached_launch_vz_key = 0
    _last_jump_cache_at = 0.0
    _reset_vehicle_jump_input_state()


def _refresh_jump_runtime_cache(*, force: bool = False) -> bool:
    global _cached_jump_pawn_id, _cached_jump_comp, _cached_jump_vehicle, _last_jump_cache_at
    now = time.monotonic()
    if not force and now - _last_jump_cache_at < _JUMP_CACHE_INTERVAL:
        return _cached_jump_comp is not None and _cached_jump_mesh is not None
    hits = _iter_bvm_vehicle_hits()
    if not hits:
        _clear_jump_runtime_cache()
        return False
    _path, pawn, comp = hits[0]
    if not _ue_object_usable(pawn) or not _ue_object_usable(comp):
        _clear_jump_runtime_cache()
        return False
    vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
    if vehicle is None and _looks_like_vehicle_actor(pawn):
        vehicle = pawn
    _cached_jump_pawn_id = _object_identity(pawn)
    _cached_jump_comp = comp
    _cached_jump_vehicle = vehicle
    _last_jump_cache_at = now
    _cached_vehicle_mesh(vehicle, comp)
    return _cached_jump_comp is not None


def _cached_vehicle_mesh(vehicle: Any, comp: Any) -> Any | None:
    global _cached_jump_mesh_id, _cached_jump_mesh
    ident = _object_identity(vehicle or comp)
    if ident and ident == _cached_jump_mesh_id and _ue_object_usable(_cached_jump_mesh):
        return _cached_jump_mesh
    mesh = None
    for root in (vehicle, comp):
        if root is None:
            continue
        for name in ("VehicleMesh", "Mesh", "RootPrimitiveComponent", "RootComponent"):
            try:
                obj = getattr(root, name, None)
            except Exception:
                obj = None
            if obj is not None:
                mesh = obj
                break
        if mesh is not None:
            break
    if mesh is not None and ident:
        _cached_jump_mesh_id = ident
        _cached_jump_mesh = mesh
    return mesh


def _apply_physics_jump_impulse(vehicle: Any, comp: Any, strength: float) -> bool:
    if not _refresh_jump_runtime_cache():
        return False
    obj = _cached_jump_mesh
    if not _ue_object_usable(obj):
        _clear_jump_runtime_cache()
        return False
    try:
        get_velocity = getattr(obj, "GetPhysicsLinearVelocity", None)
        set_velocity = getattr(obj, "SetPhysicsLinearVelocity", None)
    except Exception:
        return False
    if not callable(get_velocity) or not callable(set_velocity):
        return False
    try:
        current = get_velocity("None")
    except Exception:
        try:
            current = get_velocity()
        except Exception:
            current = None
    if current is None:
        return False
    velocity = unrealsdk.make_struct(
        "Vector",
        X=float(getattr(current, "X", 0.0)),
        Y=float(getattr(current, "Y", 0.0)),
        Z=max(float(getattr(current, "Z", 0.0)), 0.0) + strength,
    )
    for call_args in ((velocity, False, "None"), (velocity, False), (velocity,)):
        try:
            set_velocity(*call_args)
            return True
        except (TypeError, ValueError):
            continue
        except Exception:
            break
    return False


def _apply_custom_vehicle_jump(*, log_result: bool = False, physics_only: bool = False) -> int:
    if BVM_APPLY_SCOPE == "local" and not _local_player_is_driving():
        if log_result:
            _warn_jump_once("Vehicle jump: enter a vehicle first.")
        return 0
    if _apply_vehicle_jump_fast():
        if log_result:
            _info("Vehicle jump applied (fast path).")
        return 1
    wrote = 0
    for _path, pawn, comp in _iter_bvm_vehicle_hits():
        vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
        if vehicle is None:
            if _looks_like_vehicle_actor(pawn):
                vehicle = pawn
            elif BVM_APPLY_SCOPE == "local":
                continue
            else:
                vehicle = pawn
        if _execute_vehicle_jump(pawn, comp, vehicle, fast=True):
            wrote += 1
    if log_result:
        if wrote:
            _info(f"Vehicle jump applied to {wrote} vehicle(s).")
        else:
            _warn_jump_once(
                "Vehicle jump failed — enter a vehicle first, then try Test jump again."
            )
    return wrote


def _effective_tuning_target(attr: str, target: float) -> float:
    if attr == "BoostConsumptionRateScalar" and BVM_UNLIMITED_BOOST:
        return 0.0
    return target


def _build_vehicle_tuning_targets() -> dict[str, float]:
    targets: dict[str, float] = {}
    for option, spec in zip(
        (*_slider_core, *_slider_jump, *_slider_extra),
        _FLOAT_SPECS,
        strict=True,
    ):
        attr, _lo, _hi, _step, default, _title = spec
        try:
            target = float(getattr(option, "value", default))
        except Exception:
            target = float(default)
        targets[attr] = _effective_tuning_target(attr, target)
    maxspeed = targets.get("maxspeed")
    boost_max = targets.get("BoostMaxSpeed")
    if maxspeed is not None and boost_max is not None and maxspeed > boost_max:
        targets["BoostMaxSpeed"] = maxspeed
    return targets


def _apply_vehicle_tuning_targets(
    hits: list[tuple[str, Any, Any]], targets: dict[str, float]
) -> int:
    applied = 0
    for attr, target in targets.items():
        for _path, pawn, comp in hits:
            if _read_vehicle_field(pawn, comp, attr) is None:
                continue
            if _write_vehicle_field(pawn, comp, attr, target):
                applied += 1
    return applied


def _maintain_saved_vehicle_tuning(*, interval: float | None = None) -> None:
    """Re-apply slider targets — BL4 often resets VehicleAttributesState while driving."""
    global _last_tuning_maintenance_at
    now = time.monotonic()
    wait = _TUNING_MAINTAIN_INTERVAL if interval is None else interval
    if now - _last_tuning_maintenance_at < wait:
        return
    hits = _iter_bvm_vehicle_hits()
    if not hits:
        return
    _last_tuning_maintenance_at = now
    _apply_vehicle_tuning_targets(hits, _build_vehicle_tuning_targets())


def _vehicle_jump_tick(_caller: Any, *args: Any, **kwargs: Any) -> None:
    global _last_custom_jump_at, _last_boost_maintenance_at
    global _last_damage_maintenance_at, _last_damage_rescan_at
    global _last_vehicle_lock_maintenance_at
    global BVM_REPEAT_JUMP_PRESS
    BVM_REPEAT_JUMP_PRESS = bool(_repeat_jump_press_opt.value)
    now = time.monotonic()
    _maybe_auto_apply_on_vehicle_enter()
    is_driving = _local_player_is_driving()
    tuning_active = any(
        abs(float(getattr(opt, "value", spec[4])) - float(spec[4])) > 1e-6
        for opt, spec in zip(
            (*_slider_core, *_slider_jump, *_slider_extra),
            _FLOAT_SPECS,
            strict=True,
        )
    )
    if is_driving and (
        BVM_REPEAT_JUMP_PRESS
        or BVM_UNLIMITED_BOOST
        or tuning_active
        or BVM_VEHICLE_DAMAGE_TAKEN != 1.0
    ):
        _maintain_saved_vehicle_tuning()
    if is_driving and BVM_REPEAT_JUMP_PRESS:
        if now - _last_jump_cache_at >= _JUMP_CACHE_INTERVAL:
            _refresh_jump_runtime_cache()
    if BVM_UNLIMITED_BOOST:
        if now - _last_boost_maintenance_at >= 0.5:
            _apply_unlimited_boost(log_result=False)
            _last_boost_maintenance_at = now
    if BVM_VEHICLE_DAMAGE_TAKEN != 1.0:
        if now - _last_damage_maintenance_at >= 0.05:
            _maintain_cached_vehicle_damage()
            _last_damage_maintenance_at = now
        if now - _last_damage_rescan_at >= 1.0:
            _apply_vehicle_incoming_damage_scale(BVM_VEHICLE_DAMAGE_TAKEN, log_result=False)
            _last_damage_rescan_at = now
    if _vehicle_actions_lock_overridden() and BVM_VEHICLE_LOCK_STICKY and now - _last_vehicle_lock_maintenance_at >= 0.5:
        _maintain_vehicle_actions_lock()
        _last_vehicle_lock_maintenance_at = now
    if BVM_REPEAT_JUMP_PRESS:
        _run_vehicle_jump_modes(now, is_driving)


def _run_vehicle_jump_modes(now: float, is_driving: bool) -> None:
    global _last_custom_jump_at
    if not BVM_REPEAT_JUMP_PRESS:
        return
    if not is_driving:
        _reset_vehicle_jump_input_state()
        return
    hits = _iter_bvm_vehicle_hits()
    if not hits:
        return
    _path, hit_pawn, hit_comp = hits[0]
    vehicle = _get_driven_vehicle_actor_from_pawn(hit_pawn)
    if vehicle is None and _looks_like_vehicle_actor(hit_pawn):
        vehicle = hit_pawn
    in_air = _update_jump_air_session(hit_comp, vehicle) or _vehicle_in_air_loose(hit_comp, vehicle)
    mod_press = _consume_mod_jump_pending() or _mod_only_pressed_edge()
    space_press = in_air and (
        _consume_space_jump_pending() or _space_only_pressed_edge()
    )
    if not mod_press and not space_press:
        return
    if not mod_press and now - _last_native_jump_at < 0.08:
        return
    cooldown = _vehicle_jump_tick_cooldown()
    if now - _last_custom_jump_at < cooldown:
        return
    if _apply_custom_vehicle_jump_on_comp(hit_comp, log_result=False):
        _last_custom_jump_at = now


def _remove_vehicle_jump_keybinds() -> None:
    global _jump_kb_handles
    if not _jump_kb_handles:
        return
    try:
        from keybinds import deregister_keybind

        for handle in _jump_kb_handles:
            try:
                deregister_keybind(handle)
            except Exception:
                pass
    except Exception:
        pass
    _jump_kb_handles = []


def _sync_vehicle_jump_keybinds() -> None:
    """SDK keybind presses — works when OakVehicle blocks keyboard polling."""
    global _jump_kb_handles
    _remove_vehicle_jump_keybinds()
    if not _BVM_MOD_ACTIVE:
        return
    try:
        from keybinds import register_keybind
        from mods_base import EInputEvent
    except Exception:
        return
    registered: list[Any] = []
    mod_key = ""
    try:
        mod_key = str(getattr(KEY_VEHICLE_JUMP, "key", "") or "").strip()
    except Exception:
        mod_key = ""
    keys: list[str] = list(_mod_jump_key_names())
    if mod_key and mod_key not in keys:
        keys.insert(0, mod_key)
    if not keys and mod_key:
        keys = [mod_key]
    for key in keys:
        low = key.casefold()
        if low in {"none", "unbound", "spacebar", "space"}:
            continue
        try:
            registered.append(
                register_keybind(key, EInputEvent.IE_Pressed, _kb_vehicle_jump)
            )
            break
        except Exception:
            continue
    if BVM_REPEAT_JUMP_PRESS:
        for key in ("SpaceBar", "Space"):
            try:
                registered.append(
                    register_keybind(key, EInputEvent.IE_Pressed, _kb_space_jump)
                )
                break
            except Exception:
                continue
    _jump_kb_handles = registered


def _sync_mod_jump_keybind() -> None:
    _sync_vehicle_jump_keybinds()


def _remove_vehicle_jump_hook() -> None:
    global _vehicle_jump_hook_path, _vehicle_jump_hook_type
    _sync_vehicle_powerslide_hooks()
    _remove_vehicle_jump_keybinds()
    if _vehicle_jump_hook_path == "blimgui.post_frame":
        try:
            import blimgui as _bvm_blimgui

            _bvm_blimgui.unregister_post_frame(_vehicle_jump_tick)
        except Exception:
            pass
    elif _vehicle_jump_hook_path is not None:
        for hook_type in (_vehicle_jump_hook_type, hooks.Type.POST, hooks.Type.POST_UNCONDITIONAL):
            if hook_type is None:
                continue
            try:
                if hooks.has_hook(_vehicle_jump_hook_path, hook_type, _VEHICLE_JUMP_HOOK_ID):
                    hooks.remove_hook(_vehicle_jump_hook_path, hook_type, _VEHICLE_JUMP_HOOK_ID)
                    break
            except Exception:
                continue
    _vehicle_jump_hook_path = None
    _vehicle_jump_hook_type = None
    _reset_vehicle_jump_input_state()


def _sync_vehicle_jump_hook() -> None:
    global _vehicle_jump_hook_path, _vehicle_jump_hook_type
    if not _BVM_MOD_ACTIVE:
        _remove_vehicle_jump_hook()
        return
    _sync_vehicle_powerslide_hooks()
    _sync_mod_jump_keybind()
    type_map = {
        "POST": hooks.Type.POST,
        "POST_UNCONDITIONAL": hooks.Type.POST_UNCONDITIONAL,
        "PRE": hooks.Type.PRE,
    }
    if _vehicle_jump_hook_path is None:
        for candidate, type_name in _VEHICLE_JUMP_TICK_SPECS:
            hook_type = type_map.get(type_name, hooks.Type.POST)
            try:
                if hooks.add_hook(candidate, hook_type, _VEHICLE_JUMP_HOOK_ID, _vehicle_jump_tick):
                    _vehicle_jump_hook_path = candidate
                    _vehicle_jump_hook_type = hook_type
                    break
            except Exception:
                continue
        if _vehicle_jump_hook_path is None:
            _warn(
                "Vehicle jump tick hook unavailable — N and Space keybinds still work "
                "when Unlimited jumps is enabled."
            )
    if not BVM_REPEAT_JUMP_PRESS:
        _reset_vehicle_jump_input_state()


def _object_identity(obj: Any) -> int:
    if obj is None:
        return 0
    try:
        return int(getattr(obj, "_get_address", lambda: 0)() or 0)
    except Exception:
        return id(obj)


def _object_type_text(obj: Any) -> str:
    if obj is None:
        return ""
    bits: list[str] = []
    for value in (
        getattr(obj, "Name", ""),
        getattr(getattr(obj, "Class", None), "Name", ""),
    ):
        try:
            if value:
                bits.append(str(value))
        except Exception:
            pass
    try:
        bits.append(repr(obj)[:240])
    except Exception:
        pass
    return " ".join(bits).lower()


def _resolved_def_instance(value: Any) -> Any | None:
    if value is None:
        return None
    for name in ("instance", "_experimental_instance"):
        try:
            instance = getattr(value, name, None)
        except Exception:
            instance = None
        if instance is not None:
            return instance
    return value


def _vehicle_definition_instances(vehicle: Any, *extra_roots: Any) -> list[tuple[str, Any]]:
    """Resolve the live OakVehicleDef behind the vehicle's FGbxDefPtr."""
    candidates: list[tuple[str, Any]] = []
    roots = (vehicle, *extra_roots)
    for root_index, root in enumerate(roots):
        if root is None:
            continue
        for path in (
            "VehicleDef",
            "OakVehicleMovement.VehicleDef",
            "VehicleMovementComp.VehicleDef",
            "VehicleMovementComponent.VehicleDef",
            "GbxActorData.GbxActorDef",
            "ActorData.GbxActorDef",
            "GbxActorDef",
            "ActorDef",
        ):
            value = _resolve_relative(root, path)
            instance = _resolved_def_instance(value)
            if instance is not None:
                prefix = "vehicle" if root_index == 0 else f"root[{root_index}]"
                candidates.append((f"{prefix}.{path}", instance))
    unique: list[tuple[str, Any]] = []
    seen: set[int] = set()
    for path, instance in candidates:
        ident = _object_identity(instance)
        if ident in seen:
            continue
        seen.add(ident)
        unique.append((path, instance))
    return unique


def _set_attribute_init_post_scale(value: Any, scale: float) -> tuple[bool, str]:
    """Set the GbxAttributeInit post-scale used after its calculated value resolves."""
    if value is None:
        return False, ""
    for field in ("PostScale", "postscale"):
        try:
            current = getattr(value, field)
        except Exception:
            continue
        if not isinstance(current, (int, float)) or isinstance(current, bool):
            continue
        try:
            setattr(value, field, float(scale))
            return True, field
        except Exception:
            continue
    # Older SDK wrappers exposed the same GbxAttributeInit member under this
    # legacy name. Do not write both fields or the multiplier could be squared.
    for field in ("BaseValueScale", "basevaluescale"):
        try:
            current = getattr(value, field)
        except Exception:
            continue
        if not isinstance(current, (int, float)) or isinstance(current, bool):
            continue
        try:
            setattr(value, field, float(scale))
            return True, field
        except Exception:
            continue
    return False, ""


def _weapon_damage_inits(root: Any) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for path in (
        "WeaponDamage",
        "weaponDamage",
        "VehicleWeaponData.WeaponDamage",
        "WeaponData.WeaponDamage",
        "Damage",
    ):
        value = _resolve_relative(root, path)
        if value is not None:
            out.append((path, value))
    return out


def _set_live_damage_pair(
    pair: Any,
    multiplier: float,
    baseline_key: int,
) -> tuple[bool, tuple[float, float] | None]:
    """Scale a spawned weapon behavior's evaluated damage without compounding."""
    try:
        current_value = getattr(pair, "Value")
        current_base = getattr(pair, "BaseValue")
    except Exception:
        return False, None
    if (
        not isinstance(current_value, (int, float))
        or isinstance(current_value, bool)
        or not isinstance(current_base, (int, float))
        or isinstance(current_base, bool)
    ):
        return False, None
    baseline = _vehicle_weapon_damage_baselines.get(baseline_key)
    if baseline is None:
        baseline = (float(current_value), float(current_base))
        _vehicle_weapon_damage_baselines[baseline_key] = baseline
    _vehicle_weapon_damage_targets[baseline_key] = pair
    try:
        pair.Value = baseline[0] * multiplier
        pair.BaseValue = baseline[1] * multiplier
    except Exception:
        return False, baseline
    return True, baseline


def _patch_spawned_vehicle_weapon(weapon: Any, multiplier: float, label: str) -> tuple[int, list[str]]:
    writes = 0
    details: list[str] = []
    try:
        behaviors = list(getattr(weapon, "behaviors", ()) or ())
    except Exception:
        behaviors = []
    for index, behavior in enumerate(behaviors):
        try:
            pair = getattr(behavior, "damage", None)
        except Exception:
            pair = None
        if pair is None:
            continue
        ok, baseline = _set_live_damage_pair(pair, multiplier, _object_identity(behavior))
        if ok:
            writes += 1
            base_text = "?" if baseline is None else f"{baseline[1]:g}"
            details.append(f"{label}.behaviors[{index}].damage (base={base_text})")
    return writes, details


def _patch_vehicle_driver_damage(pawn: Any, vehicle: Any, multiplier: float) -> tuple[int, list[str]]:
    """Scale the damage context BL4's vehicle formula resolves as `Driver`."""
    roots: list[tuple[str, Any]] = [("pawn", pawn), ("vehicle", vehicle)]
    paths = (
        "DriverPawn",
        "Driver",
        "CurrentDriver",
        "RestrictedOwner",
        "RestrictedOwner.OakPlayerCharacter",
    )
    try:
        live_weapons = list(getattr(vehicle, "VehicleWeapons", ()) or ())
    except Exception:
        live_weapons = []
    for label, source in (("vehicle", vehicle), *(
        (f"VehicleWeapons[{index}]", weapon) for index, weapon in enumerate(live_weapons)
    )):
        for path in paths + (
            "WeaponUser",
            "instigator",
            "BodyOwner",
            "owner.RestrictedOwner",
            "owner.RestrictedOwner.OakPlayerCharacter",
        ):
            obj = _resolve_relative(source, path)
            if obj is not None and all(obj is not existing for _root_label, existing in roots):
                roots.append((f"{label}.{path}", obj))
    writes = 0
    details: list[str] = []
    for label, root in roots:
        if root is None:
            continue
        try:
            data = getattr(root, "DamageCauserData", None)
            pair = getattr(data, "DamageDealtMultiplier", None) if data is not None else None
            current_value = getattr(pair, "Value")
            current_base = getattr(pair, "BaseValue")
        except Exception:
            continue
        if not all(
            isinstance(number, (int, float)) and not isinstance(number, bool)
            for number in (current_value, current_base)
        ):
            continue
        key = _object_identity(root)
        baseline = _vehicle_driver_damage_baselines.get(key)
        if baseline is None:
            baseline = (float(current_value), float(current_base))
            _vehicle_driver_damage_baselines[key] = baseline
        _vehicle_driver_damage_targets[key] = pair
        try:
            pair.Value = baseline[0] * multiplier
            pair.BaseValue = baseline[1] * multiplier
        except Exception:
            continue
        writes += 1
        details.append(
            f"{label}.DamageCauserData.DamageDealtMultiplier "
            f"(base={baseline[1]:g})"
        )
    return writes, details


def _apply_vehicle_weapon_damage_scale(scale: float, *, log_result: bool) -> int:
    """Patch OakVehicleDef.VehicleWeapons[*].WeaponDamage at its real PostScale."""
    multiplier = max(0.0, float(scale))
    writes = 0
    details: list[str] = []
    scoped_vehicles: list[Any] = []
    scoped_pairs: list[tuple[Any, Any]] = []
    for pawn, _who in _iter_pawns_for_bvm_scope():
        vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
        if vehicle is None and _looks_like_vehicle_actor(pawn):
            vehicle = pawn
        if vehicle is not None and all(vehicle is not existing for existing in scoped_vehicles):
            scoped_vehicles.append(vehicle)
            scoped_pairs.append((pawn, vehicle))

    for pawn, vehicle in scoped_pairs:
        driver_writes, driver_details = _patch_vehicle_driver_damage(pawn, vehicle, multiplier)
        writes += driver_writes
        details.extend(driver_details)
        movement_hit = _resolve_oak_vehicle_movement_from_vehicle_actor(vehicle)
        movement = movement_hit[1] if movement_hit is not None else None
        # The authoritative source is the resolved OakVehicleDef. The extracted
        # definition proves each entry owns a GbxAttributeInit named WeaponDamage.
        for def_path, definition in _vehicle_definition_instances(vehicle, movement):
            try:
                entries = list(getattr(definition, "VehicleWeapons", ()) or ())
            except Exception:
                entries = []
            for index, entry in enumerate(entries):
                try:
                    damage_init = getattr(entry, "WeaponDamage", None)
                except Exception:
                    damage_init = None
                ok, field = _set_attribute_init_post_scale(damage_init, multiplier)
                if ok:
                    writes += 1
                    details.append(f"{def_path}.instance.VehicleWeapons[{index}].WeaponDamage.{field}")
            try:
                collision_ptr = getattr(definition, "CollisionDamageData", None)
            except Exception:
                collision_ptr = None
            collision_def = _resolved_def_instance(collision_ptr)
            try:
                collision_damage = getattr(collision_def, "Damage", None)
            except Exception:
                collision_damage = None
            ok, field = _set_attribute_init_post_scale(collision_damage, multiplier)
            if ok:
                writes += 1
                details.append(f"{def_path}.instance.CollisionDamageData.instance.Damage.{field}")

        # Also patch live OakVehicleWeapon objects/copies when the vehicle has
        # already spawned its weapons from the definition.
        try:
            live_weapons = list(getattr(vehicle, "VehicleWeapons", ()) or ())
        except Exception:
            live_weapons = []
        for index, weapon in enumerate(live_weapons):
            live_writes, live_details = _patch_spawned_vehicle_weapon(
                weapon,
                multiplier,
                f"VehicleWeapons[{index}]",
            )
            writes += live_writes
            details.extend(live_details)
            for rel_path, damage_init in _weapon_damage_inits(weapon):
                ok, field = _set_attribute_init_post_scale(damage_init, multiplier)
                if ok:
                    writes += 1
                    details.append(f"VehicleWeapons[{index}].{rel_path}.{field}")

    if log_result:
        if writes:
            _info(f"Vehicle damage scale {multiplier:g}: wrote {writes} live damage target(s).")
            for detail in details[:12]:
                _info(f"  weapon damage path: {detail}")
        elif not scoped_vehicles:
            _warn("Vehicle weapon damage: no selected player is currently driving a vehicle.")
        else:
            _warn(
                "Vehicle weapon damage: vehicle found, but no writable "
                "OakVehicleDef.VehicleWeapons[*].WeaponDamage.PostScale was exposed."
            )
            for vehicle in scoped_vehicles[:2]:
                movement_hit = _resolve_oak_vehicle_movement_from_vehicle_actor(vehicle)
                movement = movement_hit[1] if movement_hit is not None else None
                defs = _vehicle_definition_instances(vehicle, movement)
                try:
                    live_count = len(list(getattr(vehicle, "VehicleWeapons", ()) or ()))
                except Exception:
                    live_count = 0
                _info(
                    "  vehicle damage probe: "
                    f"vehicle={_object_type_text(vehicle)[:120]} resolved_defs={len(defs)} "
                    f"live_vehicle_weapons={live_count}"
                )
                for def_path, definition in defs[:4]:
                    try:
                        entries = list(getattr(definition, "VehicleWeapons", ()) or ())
                    except Exception:
                        entries = []
                    _info(
                        f"  vehicle damage probe: {def_path} -> "
                        f"{_object_type_text(definition)[:100]} entries={len(entries)}"
                    )
                    for index, entry in enumerate(entries[:4]):
                        try:
                            init = getattr(entry, "WeaponDamage", None)
                        except Exception:
                            init = None
                        _info(
                            f"  vehicle damage probe: entry[{index}]={_object_type_text(entry)[:80]} "
                            f"WeaponDamage={_object_type_text(init)[:120]}"
                        )
    return writes


def _apply_vehicle_incoming_damage_scale(scale: float, *, log_result: bool) -> int:
    """Write only the driven vehicle's own GbxDamageState multiplier."""
    multiplier = max(0.0, float(scale))
    writes = 0
    details: list[str] = []
    for pawn, _who in _iter_pawns_for_bvm_scope():
        vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
        if vehicle is None and _looks_like_vehicle_actor(pawn):
            vehicle = pawn
        if vehicle is None:
            continue
        for path in (
            "DamageState.DamageTakenMultiplier",
            "GbxDamageState.DamageTakenMultiplier",
            "DamageComponent.DamageState.DamageTakenMultiplier",
            "DamageReceiverComponent.DamageState.DamageTakenMultiplier",
        ):
            pair = _resolve_relative(vehicle, path)
            if pair is None:
                continue
            wrote_pair = False
            for field in ("Value", "BaseValue"):
                try:
                    current = getattr(pair, field)
                except Exception:
                    continue
                if not isinstance(current, (int, float)) or isinstance(current, bool):
                    continue
                try:
                    setattr(pair, field, float(multiplier))
                    wrote_pair = True
                except Exception:
                    continue
            if wrote_pair:
                _vehicle_incoming_damage_targets[_object_identity(pair)] = pair
                writes += 1
                details.append(path)
    if log_result:
        if writes:
            _info(f"Vehicle incoming damage scale {multiplier:g}: wrote {writes} vehicle damage state(s).")
            for detail in details[:8]:
                _info(f"  incoming damage path: {detail}")
        else:
            _warn("Vehicle incoming damage: no writable driven-vehicle GbxDamageState multiplier was exposed.")
    return writes


def _maintain_cached_vehicle_damage() -> None:
    """Keep evaluated live pairs scaled without performing expensive world scans every frame."""
    dealt = max(0.0, float(BVM_VEHICLE_DAMAGE_DEALT))
    taken = max(0.0, float(BVM_VEHICLE_DAMAGE_TAKEN))
    for key, pair in tuple(_vehicle_weapon_damage_targets.items()):
        baseline = _vehicle_weapon_damage_baselines.get(key)
        if baseline is None:
            continue
        try:
            pair.Value = baseline[0] * dealt
            pair.BaseValue = baseline[1] * dealt
        except Exception:
            _vehicle_weapon_damage_targets.pop(key, None)
    for key, pair in tuple(_vehicle_driver_damage_targets.items()):
        baseline = _vehicle_driver_damage_baselines.get(key)
        if baseline is None:
            continue
        try:
            pair.Value = baseline[0] * dealt
            pair.BaseValue = baseline[1] * dealt
        except Exception:
            _vehicle_driver_damage_targets.pop(key, None)
    for key, pair in tuple(_vehicle_incoming_damage_targets.items()):
        try:
            pair.Value = taken
            pair.BaseValue = taken
        except Exception:
            _vehicle_incoming_damage_targets.pop(key, None)


def _looks_like_vehicle_actor(obj: Any) -> bool:
    text = _object_type_text(obj)
    return (
        "oakvehicle" in text
        or "personalvehicle" in text
        or "bpvehicle" in text
        or "bp_vehicle" in text
    ) and "weapon" not in text and "projectile" not in text


def _scoped_vehicle_context() -> tuple[set[int], set[int]]:
    """Return controller and driven-vehicle identities allowed by the current scope."""
    controller_ids: set[int] = set()
    vehicle_ids: set[int] = set()
    for pawn, _who in _iter_pawns_for_bvm_scope():
        for pc in _iter_pcs():
            if _try_pawn(pc) is pawn:
                controller_ids.add(_object_identity(pc))
        vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
        if vehicle is None and _looks_like_vehicle_actor(pawn):
            vehicle = pawn
        if vehicle is not None:
            vehicle_ids.add(_object_identity(vehicle))
    return controller_ids, vehicle_ids


def _walk_damage_source_objects(params: Any) -> list[Any]:
    queue: list[tuple[Any, int]] = []
    for name in (
        "DamageCauser",
        "EventInstigator",
        "InstigatedBy",
        "DamageSource",
        "DamageEvent",
    ):
        try:
            obj = getattr(params, name, None)
        except Exception:
            obj = None
        if obj is not None:
            queue.append((obj, 0))
    out: list[Any] = []
    seen: set[int] = set()
    while queue and len(out) < 32:
        obj, depth = queue.pop(0)
        ident = _object_identity(obj)
        if ident in seen:
            continue
        seen.add(ident)
        out.append(obj)
        if depth >= 3:
            continue
        for name in (
            "Owner",
            "Instigator",
            "Controller",
            "Pawn",
            "Weapon",
            "SourceActor",
            "DamageCauser",
            "DamageSource",
        ):
            try:
                child = getattr(obj, name, None)
            except Exception:
                child = None
            if child is not None:
                queue.append((child, depth + 1))
    return out


def _damage_is_from_scoped_vehicle(params: Any) -> bool:
    controller_ids, vehicle_ids = _scoped_vehicle_context()
    if not controller_ids and not vehicle_ids:
        return False
    objects = _walk_damage_source_objects(params)
    identities = {_object_identity(obj) for obj in objects}
    if identities.intersection(controller_ids) or identities.intersection(vehicle_ids):
        return True
    # Vehicle projectiles retain recognizable source/weapon names even when the
    # reflected Owner link is unavailable on a client. Only accept that fallback
    # while a player in the selected scope is actively driving.
    markers = (
        "oakvehicleweapon",
        "weapon_vehicle",
        "vehicle_weapon",
        "lp_vehicle",
        "personalvehicleweapon",
        "dmgsrc_personalvehicle",
        "personalvehiclecollision",
    )
    return bool(vehicle_ids) and any(
        any(marker in _object_type_text(obj) for marker in markers)
        for obj in objects
    )


def _target_is_scoped_vehicle(target_obj: Any, params: Any | None = None) -> bool:
    _controller_ids, vehicle_ids = _scoped_vehicle_context()
    if not vehicle_ids:
        return False
    targets = [target_obj]
    if params is not None:
        for field in ("DamagedActor", "DamageTarget", "Target", "Victim"):
            try:
                candidate = getattr(params, field, None)
            except Exception:
                candidate = None
            if candidate is not None:
                targets.append(candidate)
    for target in targets:
        if _object_identity(target) in vehicle_ids:
            return True
        try:
            owner = getattr(target, "Owner", None)
        except Exception:
            owner = None
        if _object_identity(owner) in vehicle_ids:
            return True
    return False


def _damage_params_from_hook_args(hook_args: tuple[Any, ...]) -> Any | None:
    for candidate in hook_args:
        for field in ("Damage", "BaseDamage", "DamageAmount", "ActualDamage", "IncomingDamage", "Amount"):
            try:
                value = getattr(candidate, field)
            except Exception:
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return candidate
    return None


def _vehicle_damage_pre(target_obj: Any, *hook_args: Any, **_kwargs: Any) -> None:
    global _vehicle_damage_trace_budget
    params = _damage_params_from_hook_args(hook_args)
    if params is None:
        return
    scale = 1.0
    from_vehicle = _damage_is_from_scoped_vehicle(params)
    to_vehicle = _target_is_scoped_vehicle(target_obj, params)
    if BVM_VEHICLE_DAMAGE_DEALT != 1.0 and from_vehicle:
        scale *= max(0.0, float(BVM_VEHICLE_DAMAGE_DEALT))
    if BVM_VEHICLE_DAMAGE_TAKEN != 1.0 and to_vehicle:
        scale *= max(0.0, float(BVM_VEHICLE_DAMAGE_TAKEN))
    if _vehicle_damage_trace_budget > 0:
        source_names = ", ".join(
            _object_type_text(obj)[:80] for obj in _walk_damage_source_objects(params)[:4]
        )
        _info(
            "damage event "
            f"from_vehicle={from_vehicle} to_vehicle={to_vehicle} scale={scale:g} "
            f"target={_object_type_text(target_obj)[:80]} source={source_names}"
        )
        _vehicle_damage_trace_budget -= 1
    if scale == 1.0:
        return
    for field in ("Damage", "BaseDamage", "DamageAmount", "ActualDamage", "IncomingDamage", "Amount"):
        try:
            old = getattr(params, field)
        except Exception:
            continue
        if not isinstance(old, (int, float)) or isinstance(old, bool):
            continue
        try:
            setattr(params, field, float(old) * scale)
        except Exception:
            continue
        return


def _remove_vehicle_damage_hook() -> None:
    global _vehicle_damage_hook_paths
    for path, hook_id in tuple(_vehicle_damage_hook_paths):
        try:
            if hooks.has_hook(path, hooks.Type.PRE, hook_id):
                hooks.remove_hook(path, hooks.Type.PRE, hook_id)
        except Exception:
            pass
    _vehicle_damage_hook_paths = []


def _sync_vehicle_damage_hook() -> None:
    global _vehicle_damage_hook_paths, _vehicle_damage_trace_budget
    needed = BVM_VEHICLE_DAMAGE_DEALT != 1.0 or BVM_VEHICLE_DAMAGE_TAKEN != 1.0
    if not needed:
        _remove_vehicle_damage_hook()
        return
    if _vehicle_damage_hook_paths:
        try:
            if all(hooks.has_hook(path, hooks.Type.PRE, hook_id) for path, hook_id in _vehicle_damage_hook_paths):
                return
        except Exception:
            pass
    _remove_vehicle_damage_hook()
    # The three GameplayStatics functions are separate native entry points, so
    # hook all that exist. Do not also hook Actor.TakeDamage: doing so could
    # multiply the same hit twice when a stock Unreal path calls into it.
    registered: list[tuple[str, str]] = []
    for index, candidate in enumerate(_VEHICLE_DAMAGE_APPLY_HOOKS):
        hook_id = f"{_VEHICLE_DAMAGE_HOOK_ID}.apply{index}"
        try:
            if hooks.add_hook(candidate, hooks.Type.PRE, hook_id, _vehicle_damage_pre):
                registered.append((candidate, hook_id))
        except Exception:
            continue
    # Older SDK mappings may not expose GameplayStatics. In that case, take
    # the first reflected TakeDamage path as a compatibility fallback.
    if not registered:
        for index, candidate in enumerate(_VEHICLE_DAMAGE_TAKE_FALLBACKS):
            hook_id = f"{_VEHICLE_DAMAGE_HOOK_ID}.take{index}"
            try:
                if hooks.add_hook(candidate, hooks.Type.PRE, hook_id, _vehicle_damage_pre):
                    registered.append((candidate, hook_id))
                    break
            except Exception:
                continue
    if registered:
        _vehicle_damage_hook_paths = registered
        _vehicle_damage_trace_budget = 12
        _info("Vehicle damage multiplier active on: " + ", ".join(path for path, _hook_id in registered))
        return
    _warn("Vehicle damage multiplier could not register its damage hook on this build.")


_CHASSIS_FIELDS = {"Mass", "DragCoefficient", "DownforceCoefficient"}


def _vehicle_field_path(attr: str) -> str:
    return f"VehicleDriverComponent.VehicleAttributesState.{attr}.Value"


def _vehicle_driver_components(pawn: Any, comp: Any) -> list[Any]:
    """Find the live driver component whose BoostState points at this vehicle."""
    vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
    if vehicle is None and _looks_like_vehicle_actor(pawn):
        vehicle = pawn
    roots: list[Any] = [pawn, comp, vehicle]
    for root in tuple(roots):
        if root is None:
            continue
        for name in ("DriverPawn", "Driver", "CurrentDriver", "Owner"):
            try:
                obj = getattr(root, name, None)
            except Exception:
                obj = None
            if obj is not None and all(obj is not existing for existing in roots):
                roots.append(obj)

    candidates: list[Any] = []
    for root in roots:
        if root is None:
            continue
        try:
            if getattr(root, "VehicleAttributesState", None) is not None:
                candidates.append(root)
        except Exception:
            pass
        for name in (
            "VehicleDriverComponent",
            "VehicleDriver",
            "GbxVehicleDriverComponent",
            "OakVehicleDriverComponent",
        ):
            try:
                obj = getattr(root, name, None)
            except Exception:
                obj = None
            if obj is not None and all(obj is not existing for existing in candidates):
                candidates.append(obj)

    try:
        found = list(unrealsdk.find_all("VehicleDriverComponent", exact=False))
    except Exception:
        found = []
    target_id = _object_identity(vehicle)
    for candidate in found:
        if candidate is None or _is_cdo(candidate):
            continue
        try:
            state = getattr(candidate, "VehicleAttributesState", None)
            boost_state = getattr(state, "BoostState", None) if state is not None else None
            linked_vehicle = getattr(boost_state, "Vehicle", None) if boost_state is not None else None
        except Exception:
            continue
        if target_id and _object_identity(linked_vehicle) != target_id:
            continue
        if all(candidate is not existing for existing in candidates):
            candidates.append(candidate)

    unique: list[Any] = []
    seen: set[int] = set()
    for candidate in candidates:
        ident = _object_identity(candidate)
        if ident in seen:
            continue
        seen.add(ident)
        unique.append(candidate)
    return unique


def _vehicle_attr_pair(pawn: Any, comp: Any, attr: str) -> Any | None:
    """Resolve the dump-backed GbxAttribute pair from either driver or vehicle ownership."""
    for root in _vehicle_driver_components(pawn, comp):
        if root is None:
            continue
        try:
            state = getattr(root, "VehicleAttributesState", None)
            pair = getattr(state, attr, None) if state is not None else None
            if pair is not None:
                return pair
        except Exception:
            pass
    return None


def _apply_unlimited_boost(*, log_result: bool) -> int:
    writes = 0
    for path, pawn, comp in _iter_bvm_vehicle_hits():
        if _write_vehicle_field(pawn, comp, "BoostConsumptionRateScalar", 0.0):
            writes += 1
            if log_result:
                _info(
                    f"Unlimited boost: {path} -> "
                    "VehicleDriverComponent.VehicleAttributesState.BoostConsumptionRateScalar = 0"
                )
    if log_result and writes == 0:
        _warn("Unlimited boost: enter a vehicle first, then toggle again.")
    return writes


def _vehicle_roots(pawn: Any, comp: Any) -> list[Any]:
    roots: list[Any] = []
    vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
    try:
        owner = getattr(comp, "Owner", None)
    except Exception:
        owner = None
    for obj in (vehicle, comp, owner, pawn):
        if obj is not None and all(obj is not existing for existing in roots):
            roots.append(obj)
    # When possession moves to the vehicle, recover the hidden driver character
    # from the matching controller so combat attributes do not resolve only on
    # the vehicle pawn.
    for pc in _iter_pcs():
        candidates: list[Any] = []
        for name in ("Pawn", "AcknowledgedPawn", "Character", "ControlledPawn"):
            try:
                obj = getattr(pc, name, None)
            except Exception:
                obj = None
            if obj is not None and all(obj is not existing for existing in candidates):
                candidates.append(obj)
        if not any(obj is pawn or obj is vehicle for obj in candidates):
            continue
        for obj in candidates:
            if all(obj is not existing for existing in roots):
                roots.append(obj)
    for root in tuple(roots):
        for name in ("Driver", "CurrentDriver", "DriverPawn", "VehicleDriver", "Instigator"):
            try:
                obj = getattr(root, name, None)
            except Exception:
                obj = None
            if obj is not None and all(obj is not existing for existing in roots):
                roots.append(obj)
    return roots


def _resolve_relative(root: Any, path: str) -> Any | None:
    obj = root
    for part in path.split("."):
        try:
            obj = getattr(obj, part, None)
        except Exception:
            return None
        if obj is None:
            return None
    return obj


def _vehicle_config_values(pawn: Any, comp: Any, attr: str) -> list[tuple[str, Any, str]]:
    """Resolve dump-backed movement initializers and OakVehicleDef scalar fields."""
    out: list[tuple[str, Any, str]] = []
    vehicle = _get_driven_vehicle_actor_from_pawn(pawn)
    if vehicle is None and _looks_like_vehicle_actor(pawn):
        vehicle = pawn
    if attr in {"PowerslideJumpHeight", "PowerslideJumpGravityScalar"}:
        init = _resolve_relative(comp, f"HoverSetup.{attr}")
        if init is not None:
            out.append((f"HoverSetup.{attr}.constant", init, "constant"))
    if attr in {
        "PowerslideJumpHeight",
        "PowerslideJumpGravityScalar",
        "GravityScalar",
        "GravityScalar_AntiBounce",
    }:
        for def_path, definition in _vehicle_definition_instances(vehicle, comp):
            if attr in {"PowerslideJumpHeight", "PowerslideJumpGravityScalar"}:
                target = _resolve_relative(definition, f"HoverSetup.{attr}")
                field = "constant"
                path = f"{def_path}.HoverSetup.{attr}.constant"
            else:
                target = definition
                field = attr
                path = f"{def_path}.{attr}"
            if target is not None:
                out.append((path, target, field))
    unique: list[tuple[str, Any, str]] = []
    seen: set[tuple[int, str]] = set()
    for path, target, field in out:
        key = (_object_identity(target), field)
        if key in seen:
            continue
        seen.add(key)
        unique.append((path, target, field))
    return unique


def _read_vehicle_field(pawn: Any, comp: Any, attr: str) -> float | None:
    pair = None if "." in attr else _vehicle_attr_pair(pawn, comp, attr)
    value = getattr(pair, "Value", None) if pair is not None else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    for _path, target, field in _vehicle_config_values(pawn, comp, attr):
        try:
            value = getattr(target, field)
        except Exception:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    for root in _vehicle_roots(pawn, comp):
        value = _resolve_relative(root, attr)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        pair_value = getattr(value, "Value", None) if value is not None else None
        if isinstance(pair_value, (int, float)) and not isinstance(pair_value, bool):
            return float(pair_value)
    return None


def _write_vehicle_field(pawn: Any, comp: Any, attr: str, value: float) -> bool:
    pair = None if "." in attr else _vehicle_attr_pair(pawn, comp, attr)
    wrote = False
    if pair is not None:
        for name in ("Value", "BaseValue"):
            try:
                current = getattr(pair, name, None)
                if isinstance(current, (int, float)) and not isinstance(current, bool):
                    setattr(pair, name, int(value) if isinstance(current, int) else float(value))
                    wrote = True
            except Exception:
                continue
    for _path, target, field in _vehicle_config_values(pawn, comp, attr):
        try:
            current = getattr(target, field)
            if isinstance(current, (int, float)) and not isinstance(current, bool):
                setattr(target, field, int(value) if isinstance(current, int) else float(value))
                wrote = True
        except Exception:
            continue
    for root in _vehicle_roots(pawn, comp):
        parts = attr.split(".")
        parent = _resolve_relative(root, ".".join(parts[:-1])) if len(parts) > 1 else root
        if parent is None:
            continue
        name = parts[-1]
        try:
            current = getattr(parent, name, None)
        except Exception:
            continue
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            try:
                setattr(parent, name, int(value) if isinstance(current, int) else float(value))
                wrote = True
            except Exception:
                pass
            continue
        for subfield in ("Value", "BaseValue"):
            try:
                old = getattr(current, subfield, None)
                if isinstance(old, (int, float)) and not isinstance(old, bool):
                    setattr(current, subfield, int(value) if isinstance(old, int) else float(value))
                    wrote = True
            except Exception:
                continue
    return wrote


def _read_float(obj: Any, name: str) -> float | None:
    try:
        v = getattr(obj, name, None)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    except Exception:
        return None
    return None


def _write_float(obj: Any, name: str, value: float) -> bool:
    try:
        cur = getattr(obj, name, None)
        if isinstance(cur, (int, float)) and not isinstance(cur, bool):
            setattr(obj, name, float(value))
            return True
    except Exception:
        return False
    return False


def _movement_hits_or_warn(*, quiet: bool = False) -> list[tuple[str, Any]]:
    hits = _iter_bvm_vehicle_hits()
    if not hits and not quiet:
        _err(
            "No vehicle movement for current scope — each target must be **in a vehicle** (or expose vehicle movement). "
            "Try **Apply tuning to** = Local + enter a vehicle, or `vehicle_move_target local`.",
        )
    return hits


def _apply_field(attr: str, value: float, hits: list[tuple[str, Any, Any]] | None = None) -> None:
    if hits is None:
        hits = _movement_hits_or_warn()
    if not hits:
        return
    wrote = 0
    for path, pawn, comp in hits:
        current = _read_vehicle_field(pawn, comp, attr)
        if current is None:
            continue
        baseline_key = (_object_identity(_get_driven_vehicle_actor_from_pawn(pawn) or comp), attr)
        _vehicle_tuning_baselines.setdefault(baseline_key, current)
        applied = _effective_tuning_target(attr, float(value))
        if _write_vehicle_field(pawn, comp, attr, applied):
            target = attr if attr in _CHASSIS_FIELDS else _vehicle_field_path(attr)
            _info(f"Set {path} -> {target} = {applied}")
            wrote += 1
            if attr == "maxspeed":
                boost_now = _read_vehicle_field(pawn, comp, "BoostMaxSpeed")
                if boost_now is not None and boost_now < applied:
                    if _write_vehicle_field(pawn, comp, "BoostMaxSpeed", applied):
                        _info(f"Set {path} -> BoostMaxSpeed = {applied} (synced to maxspeed)")
    if wrote == 0:
        _warn(f"No targets wrote {attr!r} (missing float or blocked).")


def _reset_all() -> None:
    global BVM_VEHICLE_DAMAGE_DEALT, BVM_VEHICLE_DAMAGE_TAKEN
    global BVM_UNLIMITED_BOOST, BVM_REPEAT_JUMP_PRESS
    hits = _movement_hits_or_warn()
    total = 0
    restored_options: dict[str, float] = {}
    for path, pawn, comp in hits:
        ok = 0
        identity = _object_identity(_get_driven_vehicle_actor_from_pawn(pawn) or comp)
        for attr, _low, _high, _step, _default, _title in _FLOAT_SPECS:
            val = _vehicle_tuning_baselines.get((identity, attr))
            if val is not None and _write_vehicle_field(pawn, comp, attr, float(val)):
                ok += 1
                restored_options.setdefault(attr, float(val))
        total += ok
        _info(f"Restored {ok} captured original vehicle fields on {path}")
    for option, spec in zip(
        (*_slider_core, *_slider_jump, *_slider_extra),
        _FLOAT_SPECS,
        strict=True,
    ):
        attr, _low, _high, _step, default, _title = spec
        _set_option_value_silent(option, restored_options.get(attr, float(default)))
    _set_option_value_silent(_vehicle_damage_taken_opt, 1.0)
    _set_option_value_silent(_unlimited_boost_opt, False)
    _set_option_value_silent(_repeat_jump_press_opt, False)
    _set_option_value_silent(_jump_repeat_interval_opt, 0.15)
    BVM_UNLIMITED_BOOST = False
    BVM_REPEAT_JUMP_PRESS = False
    BVM_VEHICLE_DAMAGE_DEALT = 1.0
    BVM_VEHICLE_DAMAGE_TAKEN = 1.0
    # Clean up any live outgoing scale left by pre-1.3.9 builds.
    _apply_vehicle_weapon_damage_scale(1.0, log_result=False)
    _apply_vehicle_incoming_damage_scale(1.0, log_result=True)
    _sync_vehicle_jump_hook()
    if hits and total == 0:
        _warn("No captured pre-tuning movement values existed; respawn the vehicle to restore its stock movement.")
    _info(f"Reset complete: {total} captured movement field(s), damage scales = 1.")


def _show_all() -> None:
    hits = _movement_hits_or_warn()
    if not hits:
        return
    for path, pawn, comp in hits:
        _info(f"Vehicle movement: {path}")
        for attr, _vmin, _vmax, _step, _defv, title in _FLOAT_SPECS:
            v = _read_vehicle_field(pawn, comp, attr)
            if v is not None:
                _info(f"  {title} ({attr}) = {v}")
    _info(f"Vehicle incoming damage multiplier = {BVM_VEHICLE_DAMAGE_TAKEN}")


def _scan_floats(max_lines: int) -> None:
    hits = _movement_hits_or_warn()
    if not hits:
        return
    per = max(5, max_lines // max(1, len(hits)))
    for path, _pawn, comp in hits:
        _info(f"--- scan: {path} (cap {per} lines) ---")
        try:
            from unrealsdk.unreal import UObject  # noqa: PLC0415

            names = (
                list(comp._get_fields())
                if isinstance(comp, UObject)
                else sorted(x for x in dir(comp) if not x.startswith("_"))
            )
        except Exception:
            names = sorted(x for x in dir(comp) if not x.startswith("_"))
        shown = 0
        for name in names:
            v = _read_float(comp, name)
            if v is None:
                continue
            _info(f"  float {name} = {v}")
            shown += 1
            if shown >= per:
                _warn(f"Capped this target at {per} lines.")
                break


def _safe_repr(v: Any) -> str:
    try:
        return repr(v)[:120]
    except Exception:
        return "?"


def _vault_show() -> None:
    pawns = _iter_pawns_for_bvm_scope()
    if not pawns:
        _err("No pawns for current scope.")
        return
    for pawn, who in pawns:
        _info(f"Vault power / traversal costs [{who}]:")
        for rel in _VAULT_COST_VALUE_PATHS:
            v = _pawn_get_path(pawn, rel)
            if v is None:
                _info(f"  {rel} = <missing>")
                continue
            try:
                _info(f"  {rel} = {float(v)}")
            except (TypeError, ValueError):
                _info(f"  {rel} = {_safe_repr(v)}")


def _vault_set_uniform(value: float, *, label: str = "set") -> None:
    pawns = _iter_pawns_for_bvm_scope()
    if not pawns:
        _err("No pawns for current scope.")
        return
    v = max(0.0, float(value))
    for pawn, who in pawns:
        ok = 0
        for rel in _VAULT_COST_VALUE_PATHS:
            if _pawn_set_path(pawn, rel, v):
                ok += 1
                _info(f"vault {label} [{who}]: {rel} = {v}")
        if ok == 0:
            _warn(f"[{who}] No vault cost paths wrote (OakCharacterMovement missing?).")
        else:
            _info(f"vault {label} [{who}]: updated {ok}/{len(_VAULT_COST_VALUE_PATHS)} paths.")


def _vault_zero() -> None:
    _vault_set_uniform(0.0, label="zero")


_PRESETS: dict[str, dict[str, float]] = {
    "boost": {"maxspeed": 12000.0, "BoostMaxSpeed": 20000.0, "MaxAccel": 40000.0, "BoostMaxAccel": 60000.0, "BoostConsumptionRateScalar": 0.0},
    "crawl": {"maxspeed": 500.0, "BoostMaxSpeed": 700.0, "MaxAccel": 1200.0},
    "floaty": {
        "AirControl": 25.0,
        "AirBraking": 100.0,
        "DownforceCoefficient": 0.0,
        "PowerslideJumpHeight": 800.0,
        "PowerslideJumpGravityScalar": 1.0,
        "GravityScalar": 0.35,
    },
    "orbit": {
        "maxspeed": 9000.0,
        "BoostMaxSpeed": 16000.0,
        "AirControl": 40.0,
        "DownforceCoefficient": 0.0,
        "PowerslideJumpHeight": 1200.0,
        "PowerslideJumpGravityScalar": -2.0,
        "GravityScalar": -1.0,
    },
    "heavy": {"Mass": 25000.0, "DownforceCoefficient": 20.0, "maxspeed": 2500.0},
    "drift": {
        "BrakingAccel": 500.0,
        "BoostingBrakingAccel": 500.0,
        "PowerslideBoostSlideTime": 8.0,
        "PowerslideBoostDuration": 5.0,
        "maxspeed": 9000.0,
    },
}


_VEHICLE_SPAWN_BUILTIN: list[dict[str, Any]] = [
    {"id": "PV_Grazer", "aliases": ["grazer"], "label": "Grazer", "category": "base", "unlock": "Unlockable_Vehicles.Grazer", "verified": True},
    {"id": "PV_Borg", "aliases": ["borg"], "label": "Borg", "category": "base", "unlock": "Unlockable_Vehicles.Borg", "verified": True},
    {"id": "PV_Base", "aliases": ["base"], "label": "Base", "category": "base", "unlock": "Unlockable_Vehicles.Base"},
    {"id": "PV_shatterlandV1", "aliases": ["shatterland", "shatterlandv1", "shatter"], "label": "Shatterland V1", "category": "promo", "unlock": "Unlockable_Vehicles.ShatterlandV1"},
    {"id": "PV_City", "aliases": ["city"], "label": "City", "category": "promo", "unlock": "Unlockable_Vehicles.City"},
    {"id": "PV_CityOrder", "aliases": ["cityorder", "city_order"], "label": "City Order", "category": "promo", "unlock": "Unlockable_Vehicles.CityOrder"},
    {"id": "PV_Mountain", "aliases": ["mountain", "cello"], "label": "Mountain (Vault Card)", "category": "dlc", "unlock": "Unlockable_Vehicles.Mountain"},
    {"id": "PV_DarkSiren", "aliases": ["darksiren", "siren"], "label": "Dark Siren", "category": "character", "unlock": "Unlockable_Vehicles.DarkSiren"},
    {"id": "PV_DarkSiren_Proto", "aliases": ["darksiren_proto", "siren_proto"], "label": "Dark Siren (Proto)", "category": "character", "unreleased": True},
    {"id": "PV_ExoSoldier", "aliases": ["exosoldier", "exo"], "label": "Exo Soldier", "category": "character", "unlock": "Unlockable_Vehicles.ExoSoldier"},
    {"id": "PV_ExoSoldier_Proto", "aliases": ["exosoldier_proto", "exo_proto"], "label": "Exo Soldier (Proto)", "category": "character", "unreleased": True},
    {"id": "PV_Gravitar", "aliases": ["gravitar"], "label": "Gravitar", "category": "character", "unlock": "Unlockable_Vehicles.Gravitar"},
    {"id": "PV_Gravitar_Proto", "aliases": ["gravitar_proto"], "label": "Gravitar (Proto)", "category": "character", "unreleased": True},
    {"id": "PV_Paladin", "aliases": ["paladin"], "label": "Paladin", "category": "character", "unlock": "Unlockable_Vehicles.Paladin"},
    {"id": "PV_Paladin_Proto", "aliases": ["paladin_proto"], "label": "Paladin (Proto)", "category": "character", "unreleased": True},
]
_vehicle_spawn_catalog: list[dict[str, Any]] = []
_vehicle_spawn_alias_map: dict[str, dict[str, Any]] = {}
_last_vehicle_spawn_at: float = 0.0
_spawn_ui_index: int = 0

_PV_DEF_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"FGbxDefPtr\('(PV_[A-Za-z0-9_]+)',\s*'OakVehicleDef'"),
    re.compile(r"'(PV_[A-Za-z0-9_]+)'\s*,\s*'OakVehicleDef'"),
    re.compile(r'"(PV_[A-Za-z0-9_]+)"'),
)
_UNLOCK_VEHICLE_RE = re.compile(r"Unlockable_Vehicles\.([A-Za-z0-9_]+)")
_PERSONAL_VEHICLE_FOLDER_RE = re.compile(r"/Game/Gear/Vehicles/Personal/([A-Za-z0-9_]+)/")
_UID_VEHICLE_LABEL_RE = re.compile(r"UIDisplayData_Vehicle_([A-Za-z0-9_]+)")


def _sdk_mods_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _is_vehicle_mesh_unlock_stem(stem: str) -> bool:
    return not str(stem or "").casefold().startswith("mat")


def _pv_id_from_unlock_stem(stem: str) -> str:
    clean = str(stem or "").strip()
    if clean.casefold() == "shatterlandv1":
        return "PV_shatterlandV1"
    if clean.startswith("PV_"):
        return clean if clean[3:] else "PV_"
    return f"PV_{clean}"


def _offline_vehicle_scan_roots() -> list[Path]:
    root = _sdk_mods_root()
    candidates = (
        root / "bl4_live_editor" / "dumps",
        root / "Squ1ggsBoostingTools" / "data",
        root / "ultra_local_menu",
        root / "hookedwidget mods for release" / "bl4_item_spawner_hookedwidget" / "data",
        root / "settings",
    )
    return [path for path in candidates if path.is_dir()]


def _extract_vehicle_ids_from_text(text: str) -> tuple[set[str], dict[str, str]]:
    found: set[str] = set()
    labels: dict[str, str] = {}
    for pattern in _PV_DEF_PATTERNS[:2]:
        found.update(pattern.findall(text))
    for match in _PERSONAL_VEHICLE_FOLDER_RE.finditer(text):
        folder = match.group(1)
        if folder not in {"_Shared", "Shared"}:
            found.add(_pv_id_from_unlock_stem(folder))
    for match in _UID_VEHICLE_LABEL_RE.finditer(text):
        labels[_pv_id_from_unlock_stem(match.group(1))] = match.group(1)
    unlocks: dict[str, str] = {}
    for stem in _UNLOCK_VEHICLE_RE.findall(text):
        if not _is_vehicle_mesh_unlock_stem(stem):
            continue
        def_id = _pv_id_from_unlock_stem(stem)
        unlocks[def_id] = f"Unlockable_Vehicles.{stem}"
        found.add(def_id)
    for def_id, label in labels.items():
        if def_id not in found:
            found.add(def_id)
    return found, unlocks


def _rows_from_vehicle_id_set(
    found: set[str],
    unlocks: dict[str, str] | None = None,
    *,
    source: str,
) -> list[dict[str, Any]]:
    unlocks = unlocks or {}
    rows: list[dict[str, Any]] = []
    for def_id in sorted(found):
        if not str(def_id).startswith("PV_"):
            continue
        stem = def_id[3:]
        row: dict[str, Any] = {
            "id": def_id,
            "aliases": [stem.casefold()],
            "label": stem,
            "category": "discovered",
            "discovered": True,
            "source": source,
        }
        unlock = unlocks.get(def_id) or _unlock_token_for_vehicle(def_id)
        if unlock:
            row["unlock"] = unlock
        rows.append(row)
    return rows


def _scan_text_sources_for_vehicles() -> tuple[set[str], dict[str, str]]:
    found: set[str] = set()
    unlocks: dict[str, str] = {}
    token_files = (
        _sdk_mods_root() / "ultra_local_menu" / "unlockable_try_tokens_candidates.json",
        _sdk_mods_root() / "ultra_local_menu" / "ALL_UNLOCKABLE_TOKENS_ONE_PER_LINE.txt",
    )
    for path in token_files:
        if not path.is_file():
            continue
        try:
            if path.suffix.lower() == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                tokens = [str(x) for x in data if isinstance(x, str)] if isinstance(data, list) else []
            else:
                tokens = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for token in tokens:
            token = str(token or "").strip()
            if not token.startswith("Unlockable_Vehicles."):
                continue
            stem = token.split(".", 1)[1]
            if not _is_vehicle_mesh_unlock_stem(stem):
                continue
            def_id = _pv_id_from_unlock_stem(stem)
            found.add(def_id)
            unlocks[def_id] = token
    for path in (
        _sdk_mods_root() / "Squ1ggsBoostingTools" / "data" / "game_data.json",
        _sdk_mods_root()
        / "hookedwidget mods for release"
        / "bl4_item_spawner_hookedwidget"
        / "data"
        / "reference"
        / "supplemental_inv_comp_hotfix_9.json",
    ):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        ids, file_unlocks = _extract_vehicle_ids_from_text(text)
        found.update(ids)
        unlocks.update(file_unlocks)
    return found, unlocks


def _scan_dump_files_for_vehicles(*, max_file_bytes: int = 80_000_000) -> tuple[set[str], dict[str, str], int]:
    found: set[str] = set()
    unlocks: dict[str, str] = {}
    scanned = 0
    for base in _offline_vehicle_scan_roots():
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".json", ".txt", ".log", ".md"}:
                continue
            try:
                if path.stat().st_size > max_file_bytes:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            scanned += 1
            ids, file_unlocks = _extract_vehicle_ids_from_text(text)
            found.update(ids)
            unlocks.update(file_unlocks)
    return found, unlocks, scanned


def _offline_vehicle_rows(*, deep: bool = False) -> list[dict[str, Any]]:
    found, unlocks = _scan_text_sources_for_vehicles()
    source = "ncs+ulm+game_data"
    files_scanned = 0
    if deep:
        dump_found, dump_unlocks, files_scanned = _scan_dump_files_for_vehicles()
        found.update(dump_found)
        unlocks.update(dump_unlocks)
        source = f"dumps({files_scanned})+ncs+ulm+game_data"
    return _rows_from_vehicle_id_set(found, unlocks, source=source)


def _write_user_vehicle_catalog(rows: list[dict[str, Any]]) -> None:
    out = SETTINGS_PATH.parent / "bvm_vehicle_spawn_catalog.user.json"
    payload = {
        "schema": "bvm.vehicle_spawn_catalog.v1",
        "note": "Auto-merged from live editor dumps, ULM/NCS unlock tokens, and game_data scans.",
        "vehicles": [
            {k: v for k, v in row.items() if k not in {"source"}}
            for row in rows
            if str(row.get("id", "")).startswith("PV_")
        ],
    }
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        _warn(f"Could not write {out.name}: {exc}")


def _vehicle_spawn_catalog_paths() -> list[Any]:
    paths: list[Any] = [
        SETTINGS_PATH.parent / "bvm_vehicle_spawn_catalog.json",
        SETTINGS_PATH.parent / "bvm_vehicle_spawn_catalog.user.json",
    ]
    try:
        paths.append(Path(__file__).resolve().parent / "bvm_vehicle_spawn_catalog.json")
    except Exception:
        pass
    return paths


def _normalize_spawn_entry(raw: dict[str, Any]) -> dict[str, Any] | None:
    def_id = str(raw.get("id") or raw.get("def") or "").strip()
    if not def_id:
        return None
    if def_id.lower().startswith("pv_"):
        def_id = "PV_" + def_id[3:]
    elif not def_id.startswith("PV_"):
        def_id = f"PV_{def_id}"
    aliases = [str(a).strip().casefold() for a in (raw.get("aliases") or []) if str(a).strip()]
    stem = def_id[3:]
    aliases.extend([stem.casefold(), stem.replace("_", "").casefold(), def_id.casefold()])
    label = str(raw.get("label") or stem).strip()
    unlock = str(raw.get("unlock") or "").strip() or None
    return {
        "id": def_id,
        "aliases": tuple(dict.fromkeys(a for a in aliases if a)),
        "label": label,
        "category": str(raw.get("category") or "unknown").strip().lower(),
        "unreleased": bool(raw.get("unreleased", False)),
        "verified": bool(raw.get("verified", False)),
        "unlock": unlock,
    }


def _merge_vehicle_spawn_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for raw in entries:
        entry = _normalize_spawn_entry(raw)
        if entry is None:
            continue
        existing = merged.get(entry["id"])
        if existing is None:
            merged[entry["id"]] = entry
            continue
        alias_set = dict.fromkeys([*existing["aliases"], *entry["aliases"]])
        existing["aliases"] = tuple(alias_set.keys())
        for key in ("label", "category"):
            if existing.get(key) in ("", "unknown") and entry.get(key):
                existing[key] = entry[key]
        existing["unreleased"] = bool(existing.get("unreleased")) or bool(entry.get("unreleased"))
        existing["verified"] = bool(existing.get("verified")) or bool(entry.get("verified"))
        if not existing.get("unlock") and entry.get("unlock"):
            existing["unlock"] = entry["unlock"]
    return sorted(merged.values(), key=lambda e: (e.get("category", ""), e.get("label", "")))


def _game_data_vehicle_rows() -> list[dict[str, Any]]:
    """Merge PV_* actor names from Squ1ggs game_data.json when present."""
    try:
        data_path = Path(__file__).resolve().parent.parent / "Squ1ggsBoostingTools" / "data" / "game_data.json"
        if not data_path.is_file():
            return []
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    names: list[str] = []
    if isinstance(data, dict):
        for key in ("actor_names", "actors", "spawn_names"):
            rows = data.get(key)
            if isinstance(rows, list):
                names.extend(str(row) for row in rows if isinstance(row, str))
        for value in data.values():
            if isinstance(value, list):
                names.extend(str(row) for row in value if isinstance(row, str) and row.startswith("PV_"))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in names:
        if not name.startswith("PV_"):
            continue
        if name in seen:
            continue
        seen.add(name)
        rows.append({"id": name, "aliases": [name[3:].casefold()], "label": name[3:], "discovered": True})
    return rows


def _reload_vehicle_spawn_catalog(*, log: bool = False, deep_offline: bool = False) -> int:
    global _vehicle_spawn_catalog, _vehicle_spawn_alias_map
    entries: list[dict[str, Any]] = list(_VEHICLE_SPAWN_BUILTIN)
    entries.extend(_game_data_vehicle_rows())
    entries.extend(_offline_vehicle_rows(deep=deep_offline))
    for path in _vehicle_spawn_catalog_paths():
        try:
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            rows = data.get("vehicles") or data.get("entries") or []
        elif isinstance(data, list):
            rows = data
        else:
            continue
        if isinstance(rows, list):
            entries.extend([row for row in rows if isinstance(row, dict)])
    _vehicle_spawn_catalog = _merge_vehicle_spawn_entries(entries)
    alias_map: dict[str, dict[str, Any]] = {}
    for entry in _vehicle_spawn_catalog:
        for alias in entry.get("aliases", ()):
            alias_map[str(alias).casefold()] = entry
        alias_map[str(entry["id"]).casefold()] = entry
        alias_map[str(entry["id"][3:]).casefold()] = entry
    _vehicle_spawn_alias_map = alias_map
    if log:
        _info(f"Vehicle spawn catalog: {len(_vehicle_spawn_catalog)} entries loaded.")
    return len(_vehicle_spawn_catalog)


def _vehicle_spawn_entries() -> list[dict[str, Any]]:
    if not _vehicle_spawn_catalog:
        _reload_vehicle_spawn_catalog()
    return list(_vehicle_spawn_catalog)


def _resolve_vehicle_spawn_token(token: str) -> dict[str, Any] | None:
    key = str(token or "").strip().casefold()
    if not key:
        return None
    if not _vehicle_spawn_alias_map:
        _reload_vehicle_spawn_catalog()
    hit = _vehicle_spawn_alias_map.get(key)
    if hit is not None:
        return hit
    if key.startswith("pv_"):
        return _vehicle_spawn_alias_map.get(key) or _vehicle_spawn_alias_map.get(f"pv_{key[3:]}")
    guess = _normalize_spawn_entry({"id": token.strip(), "aliases": [key]})
    return guess


def _vehicle_spawn_display_label(entry: dict[str, Any]) -> str:
    label = str(entry.get("label") or entry.get("id") or "?").strip()
    def_id = str(entry.get("id") or "")
    stem = def_id[3:] if def_id.startswith("PV_") else def_id
    if stem and label.casefold() != stem.casefold():
        return f"{label} [{stem}]"
    return label or def_id


def _vehicle_spawn_spinner_labels() -> list[str]:
    return [_vehicle_spawn_display_label(entry) for entry in _vehicle_spawn_entries()]


def _vehicle_spawn_entry_by_label(label: str) -> dict[str, Any] | None:
    want = str(label or "").strip()
    want_cf = want.casefold()
    if want.endswith("]") and "[" in want:
        stem = want.rsplit("[", 1)[1].rstrip("]").strip().casefold()
        for entry in _vehicle_spawn_entries():
            def_id = str(entry.get("id") or "")
            if def_id[3:].casefold() == stem or def_id.casefold() == f"pv_{stem}":
                return entry
    for entry in _vehicle_spawn_entries():
        if _vehicle_spawn_display_label(entry).casefold() == want_cf:
            return entry
        if str(entry.get("label") or "").casefold() == want_cf:
            return entry
        if str(entry.get("id") or "").casefold() == want_cf:
            return entry
    return None


def _refresh_spawn_vehicle_spinner() -> None:
    labels = _vehicle_spawn_spinner_labels()
    if not labels:
        return
    for attr in ("choices", "_choices", "options"):
        try:
            if hasattr(_spawn_vehicle_choice, attr):
                setattr(_spawn_vehicle_choice, attr, labels)
        except Exception:
            pass
    cur = str(getattr(_spawn_vehicle_choice, "value", "") or "")
    if cur not in labels:
        try:
            _spawn_vehicle_choice.value = labels[0]
        except Exception:
            pass


def _make_oak_vehicle_def_ptr(def_id: str) -> Any | None:
    name = str(def_id or "").strip()
    if not name:
        return None
    if name.lower().startswith("pv_"):
        name = "PV_" + name[3:]
    elif not name.startswith("PV_"):
        name = f"PV_{name}"
    try:
        from unrealsdk.unreal import FGbxDefPtr  # type: ignore[import-not-found]

        ptr = FGbxDefPtr(name, type="OakVehicleDef")
        inst = getattr(ptr, "_experimental_instance", None)
        if inst is not None:
            return inst
        return ptr
    except Exception:
        pass
    struct_names = (
        "FGbxDefPtr",
        "GbxDefPtr",
        "/Script/GbxGame.FGbxDefPtr",
        "/Script/OakGame.FGbxDefPtr",
    )
    kwarg_sets: tuple[dict[str, Any], ...] = (
        {"_experimental_name": name, "_experimental_ref": "OakVehicleDef"},
        {"name": name, "ref": "OakVehicleDef"},
        {"_experimental_name": name},
        {"name": name},
    )
    for struct_name in struct_names:
        for kwargs in kwarg_sets:
            try:
                return unrealsdk.make_struct(struct_name, **kwargs)
            except Exception:
                continue
        try:
            ws = unrealsdk.make_struct(struct_name)
            for na, ra in (("name", "ref"), ("_experimental_name", "_experimental_ref")):
                try:
                    setattr(ws, na, name)
                    setattr(ws, ra, "OakVehicleDef")
                    return ws
                except Exception:
                    continue
        except Exception:
            continue
    return None


def _try_call_ue_variants(
    obj: Any, method_names: tuple[str, ...], arg_sets: tuple[tuple[Any, ...], ...]
) -> tuple[bool, str]:
    last_err = ""
    for method_name in method_names:
        try:
            fn = getattr(obj, method_name, None)
        except Exception:
            fn = None
        if not callable(fn):
            continue
        for args in arg_sets:
            try:
                fn(*args)
                return True, f"{method_name}{args!r}"
            except TypeError:
                continue
            except Exception as exc:
                last_err = f"{method_name}{args!r}: {exc}"
    return False, last_err or "no callable method matched"


def _try_execute_console_line(pc: Any, line: str) -> tuple[bool, str]:
    payload = str(line or "").strip()
    if not payload:
        return False, "empty console line"
    for meth in ("ConsoleCommand", "ClientConsoleCommand"):
        try:
            fn = getattr(pc, meth, None)
        except Exception:
            fn = None
        if not callable(fn):
            continue
        for args in ((payload,), (payload, True)):
            try:
                fn(*args)
                return True, f"{meth}({payload!r})"
            except TypeError:
                continue
            except Exception as exc:
                return False, str(exc)
    return False, "ConsoleCommand unavailable"


def _personal_vehicle_state_roots(pc: Any) -> list[Any]:
    roots: list[Any] = []
    seen: set[int] = set()

    def add(obj: Any) -> None:
        if obj is None:
            return
        oid = _object_identity(obj)
        if oid and oid in seen:
            return
        if oid:
            seen.add(oid)
        roots.append(obj)

    add(pc)
    for attr in ("PlayerState", "OakPlayerState"):
        try:
            add(getattr(pc, attr, None))
        except Exception:
            continue
    for root in list(roots):
        try:
            add(getattr(root, "PersonalVehicleState", None))
        except Exception:
            pass
    return roots


def _write_gbx_lock_blocked(container: Any, field: str, locked: bool) -> bool:
    if container is None:
        return False
    try:
        lock = getattr(container, field, None)
    except Exception:
        return False
    if lock is None or not hasattr(lock, "bLocked"):
        return False
    try:
        setattr(lock, "bLocked", bool(locked))
        return True
    except Exception:
        return False


def _vehicle_actions_lock_mode() -> str:
    return "Force locked" if bool(_vehicle_force_locked_opt.value) else "Game default"


def _vehicle_actions_lock_overridden() -> bool:
    return bool(_vehicle_force_locked_opt.value)


def _apply_vehicle_actions_lock_on_pc(pc: Any, *, want_locked: bool = True) -> bool:
    ok = False
    for root in _personal_vehicle_state_roots(pc):
        pvs: Any = root
        try:
            if not hasattr(pvs, "VehicleActionsLock"):
                pvs = getattr(root, "PersonalVehicleState", None)
        except Exception:
            pvs = None
        if pvs is not None and _write_gbx_lock_blocked(pvs, "VehicleActionsLock", want_locked):
            ok = True
    return ok


def _apply_vehicle_actions_lock(*, log_result: bool = False) -> bool:
    if not _vehicle_actions_lock_overridden():
        return False
    want_locked = True
    targets = _iter_pcs_for_bvm_scope()
    if not targets:
        if log_result:
            _warn("Vehicle actions lock: no PlayerController in apply scope.")
        return False
    ok = False
    for pc, _label in targets:
        if _apply_vehicle_actions_lock_on_pc(pc, want_locked=want_locked):
            ok = True
    if log_result:
        state = "locked (no summon/use)" if want_locked else "unlocked"
        scope_note = f" ({len(targets)} player(s))" if len(targets) > 1 else ""
        _info(f"VehicleActionsLock → force {state}{scope_note} ({'ok' if ok else 'field miss'})")
    return ok


def _maintain_vehicle_actions_lock() -> None:
    if _vehicle_actions_lock_overridden() and BVM_VEHICLE_LOCK_STICKY:
        _apply_vehicle_actions_lock(log_result=False)


def _write_personal_vehicle_def(pc: Any, vehicle_def: Any, def_id: str) -> tuple[bool, str]:
    for root in _personal_vehicle_state_roots(pc):
        for attr in ("VehicleDef", "PersonalVehicleDef", "SelectedVehicleDef"):
            try:
                if hasattr(root, attr):
                    setattr(root, attr, vehicle_def)
                    return True, f"{attr} on {type(root).__name__}"
            except Exception as exc:
                return False, str(exc)
        for attr in ("PersonalVehicleState",):
            try:
                state = getattr(root, attr, None)
            except Exception:
                state = None
            if state is None:
                continue
            try:
                setattr(state, "VehicleDef", vehicle_def)
                return True, f"PersonalVehicleState.VehicleDef on {type(root).__name__}"
            except Exception:
                pass
    ptr = _make_oak_vehicle_def_ptr(def_id)
    arg_sets: tuple[tuple[Any, ...], ...] = ()
    if ptr is not None:
        arg_sets = ((ptr,), (def_id,), (ptr, True), (def_id, True))
    ok, how = _try_call_ue_variants(
        pc,
        ("ServerSetPersonalVehicleDef", "SetPersonalVehicleDef", "ClientSetPersonalVehicleDef"),
        arg_sets,
    )
    return ok, how


def _request_personal_vehicle(pc: Any) -> tuple[bool, str]:
    arg_sets: tuple[tuple[Any, ...], ...] = ((), (True,), (False,))
    return _try_call_ue_variants(
        pc,
        (
            "ServerRequestPersonalVehicle",
            "RequestPersonalVehicle",
            "ClientRequestPersonalVehicle",
            "SummonPersonalVehicle",
        ),
        arg_sets,
    )


def _unlock_token_for_vehicle(def_id: str, entry: dict[str, Any] | None = None) -> str | None:
    if entry is not None:
        token = str(entry.get("unlock") or "").strip()
        if token:
            return token
    stem = def_id[3:] if def_id.startswith("PV_") else def_id
    if stem.lower() == "shatterlandv1":
        return "Unlockable_Vehicles.ShatterlandV1"
    return f"Unlockable_Vehicles.{stem}"


def _try_unlock_vehicle_for_spawn(pc: Any, def_id: str, entry: dict[str, Any] | None = None) -> tuple[bool, str]:
    token = _unlock_token_for_vehicle(def_id, entry)
    if not token:
        return False, "no unlock token"
    return _try_unlock_unlockable(pc, token)


def _get_player_state(pc: Any) -> Any | None:
    for attr in ("PlayerState", "OakPlayerState"):
        try:
            ps = getattr(pc, attr, None)
            if ps is not None:
                return ps
        except Exception:
            continue
    return None


def _try_unlock_unlockable(pc: Any, token: str) -> tuple[bool, str]:
    ps = _get_player_state(pc)
    if ps is None:
        return False, "no PlayerState"
    try:
        import ultra_local_menu as ulm

        inv = getattr(ulm, "_invoke_client_unlock_unlockable", None)
        if callable(inv):
            ok, err, tag = inv(ps, token)
            if ok:
                return True, tag or token
            last = err or "ulm unlock failed"
        else:
            last = "ulm unlock helper missing"
    except Exception as exc:
        last = str(exc)
    fn = getattr(ps, "ClientUnlockUnlockable", None)
    if not callable(fn):
        return False, last
    candidates: list[Any] = []
    try:
        from unrealsdk.unreal import FGbxDefPtr  # type: ignore[import-not-found]

        ptr = FGbxDefPtr(token, type="UnlockableEntryDef")
        inst = getattr(ptr, "_experimental_instance", None)
        if inst is not None:
            candidates.extend([inst, ptr])
    except Exception:
        pass
    candidates.append(token)
    if "." in token:
        ledger, entry = token.split(".", 1)
        for lv, ev in ((ledger, entry), (f"/Script/OakGame.{ledger}", entry)):
            for args in ((lv, ev), (ev, lv)):
                try:
                    fn(*args)
                    return True, f"ClientUnlockUnlockable({lv},{ev})"
                except Exception as exc:
                    last = str(exc)
    for arg in candidates:
        try:
            fn(arg)
            return True, f"ClientUnlockUnlockable({token})"
        except TypeError:
            continue
        except Exception as exc:
            last = str(exc)
    return False, last


def _spawn_personal_vehicle_for_pc(
    pc: Any,
    def_id: str,
    *,
    probe: bool = False,
    entry: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    notes: list[str] = []
    if not probe:
        unlock_ok, unlock_detail = _try_unlock_vehicle_for_spawn(pc, def_id, entry)
        if unlock_ok:
            notes.append(f"unlock:{unlock_detail}")
    ptr = _make_oak_vehicle_def_ptr(def_id)
    if ptr is None:
        return False, f"could not build OakVehicleDef ptr for {def_id}"
    wrote, write_how = _write_personal_vehicle_def(pc, ptr, def_id)
    if wrote:
        notes.append(write_how)
    requested, req_how = _request_personal_vehicle(pc)
    if requested:
        notes.append(req_how)
    if probe:
        return wrote or requested, " | ".join(notes) if notes else "no native summon methods accepted args"
    if wrote and requested:
        return True, " | ".join(notes)
    for line in (
        f"oak_spawn {def_id}",
        f"oak_spawn {def_id[3:]}",
        f"spawnvehicle {def_id}",
        f"summonvehicle {def_id}",
    ):
        ok, how = _try_execute_console_line(pc, line)
        if ok:
            return True, how
    if notes:
        return wrote or requested, "partial: " + " | ".join(notes)
    return False, "summon failed — try vehicle_move_spawn_probe " + def_id[3:]


def _spawn_personal_vehicle(
    def_id: str,
    *,
    probe: bool = False,
    entry: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    targets = _iter_pcs_for_bvm_scope()
    if not targets:
        return False, "no PlayerController in apply scope (load a save in-world first)"
    if len(targets) == 1:
        return _spawn_personal_vehicle_for_pc(
            targets[0][0],
            def_id,
            probe=probe,
            entry=entry,
        )
    parts: list[str] = []
    any_ok = False
    for pc, label in targets:
        ok, detail = _spawn_personal_vehicle_for_pc(pc, def_id, probe=probe, entry=entry)
        any_ok = any_ok or ok
        parts.append(f"{label}:{'ok' if ok else 'fail'} ({detail})")
    return any_ok, " | ".join(parts)


def _bvm_scope_log_suffix() -> str:
    if BVM_APPLY_SCOPE == "local":
        return ""
    label = _SCOPE_LABELS.get(BVM_APPLY_SCOPE, BVM_APPLY_SCOPE)
    count = len(_iter_pcs_for_bvm_scope())
    return f" [scope: {label}, {count} player(s)]"


def _spawn_vehicle_entry(entry: dict[str, Any], *, probe: bool = False) -> bool:
    global _last_vehicle_spawn_at
    now = time.monotonic()
    if not probe and now - _last_vehicle_spawn_at < 0.75:
        _warn("Spawn cooldown — wait a moment between vehicle spawns.")
        return False
    def_id = str(entry.get("id") or "")
    ok, detail = _spawn_personal_vehicle(def_id, probe=probe, entry=entry)
    if ok:
        _last_vehicle_spawn_at = now
        _clear_jump_runtime_cache()
        tag = " [unreleased]" if entry.get("unreleased") else ""
        _info(
            f"Spawn requested: {entry.get('label', def_id)} ({def_id}){tag}{_bvm_scope_log_suffix()} — {detail}"
        )
        if not probe:
            _info("Hop in when it appears; saved tuning auto-applies on enter.")
        return True
    _warn(f"Spawn failed for {def_id}: {detail}")
    return False


def _log_vehicle_spawn_list(*, category: str | None = None) -> None:
    entries = _vehicle_spawn_entries()
    if category:
        cat = category.strip().lower()
        entries = [e for e in entries if str(e.get("category") or "") == cat]
    _info(f"Vehicle spawn catalog ({len(entries)} entries):")
    for entry in entries:
        flags: list[str] = []
        if entry.get("unreleased"):
            flags.append("unreleased")
        if entry.get("verified"):
            flags.append("verified")
        elif not entry.get("discovered"):
            flags.append("unverified")
        if entry.get("discovered"):
            flags.append("runtime")
        flag_txt = f" [{', '.join(flags)}]" if flags else ""
        aliases = ", ".join(entry.get("aliases", ())[:4])
        _info(
            f"  {entry.get('label')} -> {entry.get('id')} ({entry.get('category')}) "
            f"aliases: {aliases}{flag_txt}"
        )
    _info("Spawn: vehicle_move_spawn <alias|PV_Name>  |  vehicle_move_spawn_probe <name>")


def _scan_runtime_vehicle_defs(*, log: bool = True, deep_offline: bool = True) -> list[str]:
    global _vehicle_spawn_catalog, _vehicle_spawn_alias_map
    found: set[str] = set()
    unlocks: dict[str, str] = {}
    try:
        offline_rows = _offline_vehicle_rows(deep=deep_offline)
        for row in offline_rows:
            def_id = str(row.get("id") or "")
            if def_id.startswith("PV_"):
                found.add(def_id)
                unlock = row.get("unlock")
                if unlock:
                    unlocks[def_id] = str(unlock)
        if deep_offline and offline_rows:
            _write_user_vehicle_catalog(offline_rows)
    except Exception as exc:
        if log:
            _warn(f"Offline vehicle scan failed: {exc}")
    patterns = _PV_DEF_PATTERNS[:2]
    for cls_name in ("OakVehicleDef", "OakVehicle", "GbxActorDef"):
        try:
            for obj in unrealsdk.find_all(cls_name, exact=False):
                if _is_cdo(obj):
                    continue
                for attr in ("Name", "ObjectName", "DefName", "_experimental_name", "name"):
                    try:
                        value = getattr(obj, attr, None)
                    except Exception:
                        value = None
                    if isinstance(value, str) and value.upper().startswith("PV_"):
                        found.add(value if value.startswith("PV_") else f"PV_{value}")
                try:
                    text = str(obj)
                except Exception:
                    text = ""
                if text:
                    for pattern in patterns:
                        found.update(pattern.findall(text))
        except Exception:
            continue
    if not found:
        for path in _vehicle_spawn_catalog_paths():
            try:
                if not path.exists():
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pattern in patterns:
                found.update(pattern.findall(text))
    discovered_rows = _rows_from_vehicle_id_set(found, unlocks, source="runtime+offline")
    if discovered_rows:
        _vehicle_spawn_catalog = _merge_vehicle_spawn_entries([*_VEHICLE_SPAWN_BUILTIN, *discovered_rows, *_vehicle_spawn_catalog])
        alias_map: dict[str, dict[str, Any]] = {}
        for entry in _vehicle_spawn_catalog:
            for alias in entry.get("aliases", ()):
                alias_map[str(alias).casefold()] = entry
            alias_map[str(entry["id"]).casefold()] = entry
            alias_map[str(entry["id"][3:]).casefold()] = entry
        _vehicle_spawn_alias_map = alias_map
        _refresh_spawn_vehicle_spinner()
    if log:
        if found:
            _info(
                f"Vehicle catalog scan: {len(found)} PV_* mesh(es) — "
                f"{', '.join(sorted(found))}"
            )
            _info("Saved merge → settings/bvm_vehicle_spawn_catalog.user.json")
        else:
            _warn(
                "No PV_* OakVehicleDef names discovered. "
                "Dump PersonalVehicleState with live editor, then Scan all sources again."
            )
    return sorted(found)


def _apply_preset(name: str) -> None:
    key = name.strip().lower()
    if key not in _PRESETS:
        _err(f"Unknown preset {name!r}. Try: {', '.join(sorted(_PRESETS))}")
        return
    hits = _movement_hits_or_warn()
    if not hits:
        return
    for path, pawn, comp in hits:
        for attr, val in _PRESETS[key].items():
            if _read_vehicle_field(pawn, comp, attr) is not None and _write_vehicle_field(pawn, comp, attr, float(val)):
                _info(f"preset {key}: set {path} -> {attr} = {val}")
            else:
                _warn(f"preset {key}: skip {attr} on {path} (missing or not float)")


def _bvm_scope_from_cli_token(raw: str) -> str | None:
    s = raw.strip().lower()
    if s in _SCOPE_LABELS:
        return s
    t = raw.strip()
    for key, lab in _SCOPE_LABELS.items():
        if lab == t or lab.lower() == t.lower():
            return key
    return None


@command("vehicle_move_target", description="Set who receives BVM tuning: local | all | others (same as Mods spinner).")
def vehicle_move_target(args: argparse.Namespace) -> None:
    key = _bvm_scope_from_cli_token(str(getattr(args, "scope", "")))
    if key is None:
        _err(f"Unknown scope {getattr(args, 'scope', '')!r}. Use: local, all, others (or copy the Mods menu labels).")
        return
    _set_option_value_silent(_target_scope, _SCOPE_LABELS[key])
    _bvm_target_scope_apply(_SCOPE_LABELS[key])
    _warn("Co-op: writes on remote pawns may not replicate; host / solo is the reliable case.")


vehicle_move_target.add_argument("scope", help="local | all | others")


@command("vehicle_move_help", description="List Vehicle Movement console commands.")
def vehicle_move_help(_args: argparse.Namespace) -> None:
    _info("Vehicle Movement:")
    _info("  vehicle_move_show              — log floats that exist on vehicle movement")
    _info("  vehicle_move_apply             — reapply every saved slider after entering/travel")
    _info("  vehicle_move_reset             — reset to mod defaults (fields that exist)")
    _info("  vehicle_move_preset <name>     — boost | crawl | floaty | orbit | heavy | drift")
    _info("  vehicle_move_set <Field> <n>   — one field, e.g. maxspeed 12000")
    _info("  vehicle_move_scan_floats [N]   — discovery (default 80)")
    _info("  vehicle_move_vault_show / vehicle_move_vault_zero / vehicle_move_vault_set <n>")
    _info("  vehicle_move_preset …          — includes **orbit** (upward gravity on vehicle movement)")
    _info("  vehicle_move_target <local|all|others> — who receives slider / preset / vault writes (same as Mods spinner)")
    _info("  vehicle_move_spawn <name>           — summon personal vehicle (alias or PV_* id)")
    _info("  vehicle_move_spawn_list [category]  — list spawn aliases (base|character|dlc|promo|…)")
    _info("  vehicle_move_spawn_probe <name>     — try summon paths and log which API accepted")
    _info("  vehicle_move_spawn_scan             — runtime + live editor dumps + ULM/NCS/game_data")
    _info("  vehicle_move_spawn_scan_offline     — dumps/tokens only, writes user catalog JSON")
    _info("  vehicle_move_spawn_reload           — reload settings/bvm_vehicle_spawn_catalog*.json")
    _info("Enter a vehicle first (per target). Mods → Vehicle Movement: **Apply tuning to** + sliders + keybinds.")


@command("vehicle_move_show", description="Log current vehicle movement floats.")
def vehicle_move_show(_args: argparse.Namespace) -> None:
    _show_all()


@command("vehicle_move_reset", description="Reset vehicle movement floats to bundled defaults.")
def vehicle_move_reset(_args: argparse.Namespace) -> None:
    _reset_all()


@command("vehicle_move_preset", description="Apply a named vehicle preset (boost|crawl|floaty|orbit|heavy|drift).")
def vehicle_move_preset(args: argparse.Namespace) -> None:
    _apply_preset(args.name)


vehicle_move_preset.add_argument("name", help="boost | crawl | floaty | orbit | heavy | drift")


@command("vehicle_move_set", description="Set one live vehicle field (e.g. maxspeed 12000).")
def vehicle_move_set(args: argparse.Namespace) -> None:
    _apply_field(args.field, float(args.value))


vehicle_move_set.add_argument("field", help="Property name")
vehicle_move_set.add_argument("value", type=float, help="Float value")


@command("vehicle_move_scan_floats", description="List float fields on the vehicle movement component.")
def vehicle_move_scan_floats(args: argparse.Namespace) -> None:
    _scan_floats(max(5, min(400, int(args.maxn))))


vehicle_move_scan_floats.add_argument("maxn", nargs="?", default="80", help="Max lines (default 80).")


@command("vehicle_move_spawn", description="Summon a personal vehicle by alias or PV_* OakVehicleDef id.")
def vehicle_move_spawn(args: argparse.Namespace) -> None:
    entry = _resolve_vehicle_spawn_token(str(getattr(args, "name", "")))
    if entry is None:
        _err(f"Unknown vehicle {getattr(args, 'name', '')!r}. Try: vehicle_move_spawn_list")
        return
    _spawn_vehicle_entry(entry)


vehicle_move_spawn.add_argument("name", help="Alias or PV_* id (e.g. grazer, PV_Grazer, paladin_proto)")


@command("vehicle_move_spawn_list", description="List personal vehicle spawn aliases from the BVM catalog.")
def vehicle_move_spawn_list(args: argparse.Namespace) -> None:
    category = getattr(args, "category", None)
    _log_vehicle_spawn_list(category=str(category) if category else None)


vehicle_move_spawn_list.add_argument(
    "category",
    nargs="?",
    help="Optional filter: base | character | dlc | promo | unknown",
)


@command("vehicle_move_spawn_probe", description="Try vehicle summon APIs and log which path accepts arguments.")
def vehicle_move_spawn_probe(args: argparse.Namespace) -> None:
    entry = _resolve_vehicle_spawn_token(str(getattr(args, "name", "")))
    if entry is None:
        _err(f"Unknown vehicle {getattr(args, 'name', '')!r}. Try: vehicle_move_spawn_list")
        return
    _spawn_vehicle_entry(entry, probe=True)


vehicle_move_spawn_probe.add_argument("name", help="Alias or PV_* id")


@command("vehicle_move_spawn_scan", description="Scan runtime + live editor dumps + ULM/NCS/game_data for PV_* vehicles.")
def vehicle_move_spawn_scan(_args: argparse.Namespace) -> None:
    _scan_runtime_vehicle_defs(log=True, deep_offline=True)


@command(
    "vehicle_move_spawn_scan_offline",
    description="Scan live editor dumps + ULM/NCS tokens only (no UObject walk). Writes user catalog JSON.",
)
def vehicle_move_spawn_scan_offline(_args: argparse.Namespace) -> None:
    rows = _offline_vehicle_rows(deep=True)
    if not rows:
        _warn("Offline scan found no PV_* personal vehicle defs.")
        return
    _write_user_vehicle_catalog(rows)
    count = _reload_vehicle_spawn_catalog(log=True, deep_offline=True)
    _refresh_spawn_vehicle_spinner()
    ids = sorted({str(r.get("id")) for r in rows if str(r.get("id", "")).startswith("PV_")})
    _info(f"Offline scan merged {len(ids)} vehicles into catalog ({count} total entries).")


@command("vehicle_move_spawn_reload", description="Reload vehicle spawn catalog JSON from settings/.")
def vehicle_move_spawn_reload(_args: argparse.Namespace) -> None:
    count = _reload_vehicle_spawn_catalog(log=True, deep_offline=False)
    _refresh_spawn_vehicle_spinner()
    _info(f"Reloaded {count} spawn entries.")


@command("vehicle_move_jump_diag", description="Log vehicle jump input state (drive + press Space first).")
def vehicle_move_jump_diag(_args: argparse.Namespace) -> None:
    hits = _iter_bvm_vehicle_hits()
    _info(
        f"jump diag: driving={_local_player_is_driving()} "
        f"repeat={BVM_REPEAT_JUMP_PRESS} hits={len(hits)}"
    )
    if not hits:
        return
    _path, hit_pawn, hit_comp = hits[0]
    vehicle = _get_driven_vehicle_actor_from_pawn(hit_pawn)
    if vehicle is None and _looks_like_vehicle_actor(hit_pawn):
        vehicle = hit_pawn
    psi = _read_powerslide_input(hit_comp)
    b_pressed = _char_move_b_pressed(hit_pawn, hit_comp, vehicle)
    now = time.monotonic()
    in_air = _update_jump_air_session(hit_comp, vehicle) or _vehicle_in_air_loose(hit_comp, vehicle)
    _info(
        f"  path={_path} in_air={in_air} jump_down={_vehicle_jump_down()} "
        f"sample_vz={_last_sampled_launch_vz} native_at={now - _last_native_jump_at:.2f}s "
        f"bPressedJump={b_pressed} PowerslideInput={psi} "
        f"psi_active={_powerslide_input_active(hit_comp)} "
        f"ps_hooks={len(_vehicle_powerslide_hook_paths)} "
        f"hook={_vehicle_jump_hook_path}"
    )



@command("vehicle_move_vault_show", description="Log vault power cost fields on scoped driver pawn(s).")
def vehicle_move_vault_show(_args: argparse.Namespace) -> None:
    _vault_show()


@command("vehicle_move_vault_zero", description="Zero vault power costs on scoped pawn(s).")
def vehicle_move_vault_zero(_args: argparse.Namespace) -> None:
    _vault_zero()


@command("vehicle_move_vault_set", description="Set all vault power .Value fields to the same number (>= 0).")
def vehicle_move_vault_set(args: argparse.Namespace) -> None:
    _vault_set_uniform(float(args.value))


vehicle_move_vault_set.add_argument("value", type=float, help="Uniform cost value (0 = free).")


def _build_sliders_from(
    specs: tuple[tuple[str, float, float, float, float, str], ...],
) -> list[SliderOption]:
    opts: list[SliderOption] = []
    for attr, vmin, vmax, step, default, title in specs:
        opt = SliderOption(
            f"bvm_slider_{attr.replace('.', '_')}",
            float(default),
            float(vmin),
            float(vmax),
            step=float(step),
            is_integer=False,
            display_name=title,
            description="Applies this value to each selected player currently driving a compatible vehicle.",
        )

        @opt.set_on_change()
        def _on_slider(_: Any, value: float, _attr: str = attr) -> None:
            if _suppress_option_apply:
                return
            hits = _movement_hits_or_warn(quiet=True)
            if not hits:
                return
            if _attr in {spec[0] for spec in _JUMP_SPECS}:
                global _cached_launch_vz, _cached_launch_vz_key
                _cached_launch_vz = None
                _cached_launch_vz_key = 0
            _apply_field(_attr, float(value), hits)

        opts.append(opt)
    return opts


_slider_core = _build_sliders_from(_CORE_SPECS)
_slider_jump = _build_sliders_from(_JUMP_SPECS)
_slider_extra = _build_sliders_from(_EXTRA_SPECS)


def _clamp_saved_options() -> None:
    """Keep older wide-range settings usable after the practical range pass."""
    for option, spec in zip(
        (*_slider_core, *_slider_jump, *_slider_extra),
        _FLOAT_SPECS,
        strict=True,
    ):
        _attr, low, high, _step, default, _title = spec
        try:
            current = float(option.value)
        except Exception:
            current = float(default)
        clamped = max(float(low), min(float(high), current))
        if clamped != current:
            option.value = clamped
    for option, low, high, default in (
        (_vehicle_damage_taken_opt, 0.0, 1000.0, 1.0),
        (_jump_repeat_interval_opt, 0.08, 1.0, 0.15),
    ):
        try:
            current = float(option.value)
        except Exception:
            current = default
        clamped = max(low, min(high, current))
        if clamped != current:
            option.value = clamped

_unlimited_boost_opt = BoolOption(
    "bvm_unlimited_boost",
    False,
    display_name="Unlimited boost",
    description=(
        "Keeps the live vehicle boost consumption scalar at zero. It is reapplied while enabled so the "
        "vehicle cannot restore its normal drain rate."
    ),
)


@_unlimited_boost_opt.set_on_change()
def _on_unlimited_boost(_: Any, value: bool) -> None:
    _unlimited_boost_apply(value)


def _unlimited_boost_apply(value: bool) -> None:
    global BVM_UNLIMITED_BOOST
    if _suppress_option_apply:
        return
    BVM_UNLIMITED_BOOST = bool(value)
    _sync_vehicle_jump_hook()
    if BVM_UNLIMITED_BOOST:
        _apply_unlimited_boost(log_result=True)
    else:
        target = float(_slider_core[4].value)
        for _path, pawn, comp in _iter_bvm_vehicle_hits():
            _write_vehicle_field(pawn, comp, "BoostConsumptionRateScalar", target)


_vehicle_damage_taken_opt = SliderOption(
    "bvm_vehicle_damage_taken",
    1.0,
    0.0,
    1000.0,
    step=0.1,
    is_integer=False,
    display_name="Damage taken by vehicle",
    description="Scales final incoming damage when the selected player's driven vehicle is the target.",
)

_slider_durability = [_vehicle_damage_taken_opt]


@_vehicle_damage_taken_opt.set_on_change()
def _on_vehicle_damage_taken(_: Any, value: float) -> None:
    global BVM_VEHICLE_DAMAGE_TAKEN
    if _suppress_option_apply:
        return
    BVM_VEHICLE_DAMAGE_TAKEN = max(0.0, float(value))
    _apply_vehicle_incoming_damage_scale(BVM_VEHICLE_DAMAGE_TAKEN, log_result=True)
    _sync_vehicle_jump_hook()

_jump_repeat_interval_opt = SliderOption(
    "bvm_jump_repeat_interval",
    0.15,
    0.08,
    1.0,
    step=0.02,
    is_integer=False,
    display_name="Repeat jump cooldown (sec)",
    description="Minimum seconds between mid-air jumps. Higher values feel smoother (try 0.25–0.5).",
)

_repeat_jump_press_opt = BoolOption(
    "bvm_vehicle_repeat_jump",
    False,
    display_name="Unlimited jumps (repeat on press)",
    description=(
        "Press SpaceBar or your vehicle jump keybind again mid-air for another jump. "
        "Jump height and gravity come from the sliders above."
    ),
)


@_repeat_jump_press_opt.set_on_change()
def _on_repeat_jump_press(_: Any, value: bool) -> None:
    _repeat_jump_press_apply(value)


def _repeat_jump_press_apply(value: bool) -> None:
    global BVM_REPEAT_JUMP_PRESS
    if _suppress_option_apply:
        return
    BVM_REPEAT_JUMP_PRESS = bool(value)
    if BVM_REPEAT_JUMP_PRESS:
        _info("Unlimited jumps enabled.")
    else:
        _reset_vehicle_jump_input_state()
    _sync_vehicle_jump_hook()


_jump_now_button = ButtonOption(
    "bvm_vehicle_jump_now",
    display_name="Test jump now",
    description="Immediately applies a vehicle jump using Powerslide jump height.",
)


@_jump_now_button
def _on_jump_now(_: Any) -> None:
    _apply_custom_vehicle_jump(log_result=True)


def _apply_saved_tuning(*, log: bool = True) -> bool:
    hits = _movement_hits_or_warn(quiet=not log)
    if not hits:
        return False
    applied = _apply_vehicle_tuning_targets(hits, _build_vehicle_tuning_targets())
    global BVM_VEHICLE_DAMAGE_TAKEN
    BVM_VEHICLE_DAMAGE_TAKEN = max(0.0, float(_vehicle_damage_taken_opt.value))
    _apply_vehicle_incoming_damage_scale(BVM_VEHICLE_DAMAGE_TAKEN, log_result=log)
    _sync_vehicle_jump_hook()
    if BVM_UNLIMITED_BOOST:
        _apply_unlimited_boost(log_result=False)
    if log:
        _info(f"Applied saved tuning: {applied} live vehicle field target(s) accepted values.")
    else:
        _info(f"Auto-applied saved vehicle tuning on enter ({applied} field target(s)).")
    return True


def _maybe_auto_apply_on_vehicle_enter() -> None:
    global _last_auto_apply_vehicle_id, _auto_apply_pending_vehicle_id, _auto_apply_pending_since
    now = time.monotonic()
    if not _local_player_is_driving():
        _last_auto_apply_vehicle_id = 0
        _auto_apply_pending_vehicle_id = 0
        return
    pc = _get_local_pc()
    pawn = _try_pawn(pc) if pc is not None else None
    vehicle = _get_driven_vehicle_actor_from_pawn(pawn) if pawn is not None else None
    vid = _object_identity(vehicle or pawn)
    if not vid:
        return
    if vid == _last_auto_apply_vehicle_id:
        return
    if vid != _auto_apply_pending_vehicle_id:
        _auto_apply_pending_vehicle_id = vid
        _auto_apply_pending_since = now
    elif now - _auto_apply_pending_since > _AUTO_APPLY_RETRY_SEC:
        return
    if not _iter_bvm_vehicle_hits():
        return
    _clear_jump_runtime_cache()
    if _apply_saved_tuning(log=False):
        _last_auto_apply_vehicle_id = vid
        _auto_apply_pending_vehicle_id = 0


@command("vehicle_move_apply", description="Apply every saved vehicle slider to the current target scope.")
def vehicle_move_apply(_args: argparse.Namespace) -> None:
    _apply_saved_tuning()


_apply_saved_button = ButtonOption(
    "bvm_apply_saved_btn",
    display_name="Apply all changes",
    description="Apply every displayed movement and damage value after entering a vehicle, travelling, or reconnecting.",
)


@_apply_saved_button
def _on_apply_saved_btn(_: Any) -> None:
    _apply_saved_tuning()

_preset_buttons: list[ButtonOption] = []
for pname, pdesc in (
    ("boost", "High speed + accel"),
    ("crawl", "Slow crawl"),
    ("floaty", "Low gravity + jump"),
    ("orbit", "Upward gravity + speed (vehicle component)"),
    ("heavy", "Heavy chassis"),
    ("drift", "Low friction / long slide"),
):
    btn = ButtonOption(
        f"bvm_preset_btn_{pname}",
        display_name=f"Preset: {pname}",
        description=pdesc,
    )

    @btn
    def _on_preset(_: Any, _n: str = pname) -> None:
        _apply_preset(_n)

    _preset_buttons.append(btn)


_reset_button = ButtonOption(
    "bvm_reset_btn",
    display_name="Reset all (defaults)",
    description="Same as vehicle_move_reset / keybind.",
)


@_reset_button
def _on_reset_btn(_: Any) -> None:
    _reset_all()


_show_button = ButtonOption(
    "bvm_show_btn",
    display_name="Log current values",
    description="Same as vehicle_move_show.",
)


@_show_button
def _on_show_btn(_: Any) -> None:
    _show_all()


_vault_cost_slider = SliderOption(
    "bvm_vault_cost_uniform",
    12.0,
    0.0,
    200.0,
    step=0.25,
    is_integer=False,
    display_name="Vault traversal power costs",
    description="Sets dash, double-jump, glide, grapple, slam, and forgiveness costs together (0 = free).",
)


@_vault_cost_slider.set_on_change()
def _on_vault_cost_slider(_: Any, value: float) -> None:
    _vault_set_uniform(float(value), label="slider")


_vault_zero_button = ButtonOption(
    "bvm_vault_zero_btn",
    display_name="Vault: zero all costs (free)",
    description="Same as vehicle_move_vault_zero.",
)


@_vault_zero_button
def _on_vault_zero_btn(_: Any) -> None:
    _vault_zero()


_vault_show_button = ButtonOption(
    "bvm_vault_show_btn",
    display_name="Vault: log costs",
    description="Same as vehicle_move_vault_show.",
)


@_vault_show_button
def _on_vault_show_btn(_: Any) -> None:
    _vault_show()


_ulm_hint = BoolOption(
    "bvm_ulm_hint",
    False,
    display_name="Hint: forward to ulm vehicle show (optional)",
    description="If Ultra Local Menu is loaded, run `ulm vehicle show` once for cross-check.",
)


@_ulm_hint.set_on_change()
def _on_ulm_hint(_: Any, value: bool) -> None:
    if not value:
        return
    try:
        import ultra_local_menu as ulm  # type: ignore[import-not-found]

        fn = getattr(ulm, "_dispatch", None)
        if callable(fn):
            fn("ulm vehicle show", len("ulm"))
            _info("Forwarded: ulm vehicle show")
        else:
            _warn("ultra_local_menu has no _dispatch")
    except Exception as ex:
        _warn(f"ulm not available: {ex}")


_spawn_vehicle_list_button = ButtonOption(
    "bvm_spawn_vehicle_list",
    display_name="List spawn vehicles (console)",
    description="Same as vehicle_move_spawn_list.",
)


@_spawn_vehicle_list_button
def _on_spawn_vehicle_list(_: Any) -> None:
    _log_vehicle_spawn_list()


_spawn_vehicle_scan_button = ButtonOption(
    "bvm_spawn_vehicle_scan",
    display_name="Scan runtime vehicle defs",
    description="Same as vehicle_move_spawn_scan.",
)


@_spawn_vehicle_scan_button
def _on_spawn_vehicle_scan(_: Any) -> None:
    _scan_runtime_vehicle_defs(log=True)


def _spawn_selected_catalog_vehicle() -> None:
    labels = _vehicle_spawn_spinner_labels()
    if not labels:
        _warn("Vehicle spawn catalog is empty — run vehicle_move_spawn_reload.")
        return
    global _spawn_ui_index
    idx = max(0, min(_spawn_ui_index, len(labels) - 1))
    entry = _vehicle_spawn_entry_by_label(labels[idx])
    if entry is None:
        _warn(f"Could not resolve spawn entry for {labels[idx]!r}.")
        return
    _spawn_vehicle_entry(entry)


def _vehicle_lock_sticky_apply(value: bool) -> None:
    global BVM_VEHICLE_LOCK_STICKY
    BVM_VEHICLE_LOCK_STICKY = bool(value)
    if _vehicle_actions_lock_overridden():
        _apply_vehicle_actions_lock(log_result=True)


_vehicle_lock_sticky_opt = BoolOption(
    "bvm_vehicle_lock_sticky",
    True,
    display_name="Sticky re-apply",
    description="When force locked is enabled, keep writing VehicleActionsLock while enabled.",
)


@_vehicle_lock_sticky_opt.set_on_change()
def _on_vehicle_lock_sticky(_: Any, value: bool) -> None:
    _vehicle_lock_sticky_apply(value)


def _vehicle_force_locked_apply(value: bool) -> None:
    if value:
        _apply_vehicle_actions_lock(log_result=True)
    else:
        _info("Vehicle summon lock → game default (no override).")


_vehicle_force_locked_opt = BoolOption(
    "bvm_vehicle_force_locked",
    False,
    display_name="Force locked (blocks summon/use)",
    description=(
        "When enabled, sets ``PersonalVehicleState.VehicleActionsLock.bLocked`` so you cannot summon or use vehicles. "
        "When disabled, the game controls the lock normally."
    ),
)


@_vehicle_force_locked_opt.set_on_change()
def _on_vehicle_force_locked(_: Any, value: bool) -> None:
    _vehicle_force_locked_apply(value)


_spawn_vehicle_button = ButtonOption(
    "bvm_spawn_vehicle_now",
    display_name="Summon selected",
    description=(
        "Summons the vehicle chosen below for each player in Apply tuning to scope "
        "(ServerSetPersonalVehicleDef + RequestPersonalVehicle)."
    ),
)


@_spawn_vehicle_button
def _on_spawn_vehicle_button(_: Any) -> None:
    _spawn_selected_catalog_vehicle()


_spawn_vehicle_choice = SpinnerOption(
    "bvm_spawn_vehicle_choice",
    "Grazer",
    _vehicle_spawn_spinner_labels() or ["Grazer"],
    wrap_enabled=True,
    display_name="Vehicle",
    description="Personal vehicle mesh to summon for movement/jump testing.",
)


@_spawn_vehicle_choice.set_on_change()
def _on_spawn_vehicle_choice(_: Any, value: str) -> None:
    global _spawn_ui_index
    labels = _vehicle_spawn_spinner_labels()
    try:
        _spawn_ui_index = labels.index(str(value))
    except ValueError:
        _spawn_ui_index = 0


_target_scope = SpinnerOption(
    "bvm_target_scope",
    _SCOPE_LABELS["local"],
    _SCOPE_SPINNER_CHOICES,
    wrap_enabled=True,
    display_name="Apply tuning to",
    description=(
        "**Local** — only your pawn. **All** — every player pawn we can find. **Others** — everyone except you. "
        "Vehicle fields resolve per pawn (usually requires that player to be **in a vehicle**). "
        "Vehicle summon and force lock also respect this scope. Co-op: remote writes may not replicate."
    ),
)


@_target_scope.set_on_change()
def _on_bvm_target_scope(_: Any, value: str) -> None:
    _bvm_target_scope_apply(str(value))


def _bvm_target_scope_apply(value: str) -> None:
    global BVM_APPLY_SCOPE
    BVM_APPLY_SCOPE = _scope_from_spinner_label(value)
    _info(f"apply scope → {BVM_APPLY_SCOPE} ({_SCOPE_LABELS[BVM_APPLY_SCOPE]})")


BVM_OPTIONS: list[Any] = [
    GroupedOption(
        "bvm_group_scope",
        display_name="Who receives tuning",
        description=(
            "Sliders, presets, reset/show, vault controls, vehicle summon, force lock, keybinds, "
            "and vehicle_move_* all respect this."
        ),
        children=[_target_scope],
    ),
    GroupedOption(
        "bvm_group_core",
        display_name="Core vehicle attributes",
        description="Speed, boost, acceleration, and boost consumption. Enter a vehicle first.",
        children=[_unlimited_boost_opt, *_slider_core],
    ),
    GroupedOption(
        "bvm_group_jump",
        display_name="Jump and gravity",
        description="Native powerslide jump tuning and unlimited mid-air jumps.",
        children=[
            *_slider_jump,
            _jump_repeat_interval_opt,
            _repeat_jump_press_opt,
            _jump_now_button,
        ],
    ),
    GroupedOption(
        "bvm_group_extra",
        display_name="Handling and chassis",
        description="Braking, air control, powersliding, mass, drag, and downforce.",
        children=list(_slider_extra),
    ),
    GroupedOption(
        "bvm_group_damage",
        display_name="Vehicle durability",
        description="Incoming damage taken by the current vehicle. Outgoing vehicle weapon scaling is not exposed.",
        children=list(_slider_durability),
    ),
    GroupedOption(
        "bvm_vault_group",
        display_name="Vault traversal",
        description="Adjusts dash, double-jump, glide, grapple, slam, and forgiveness costs for selected players.",
        children=[_vault_cost_slider, _vault_zero_button, _vault_show_button],
    ),
    GroupedOption(
        "bvm_presets",
        display_name="Presets",
        description="One-click bundles; missing fields are skipped.",
        children=[_apply_saved_button, *_preset_buttons, _reset_button, _show_button, _ulm_hint],
    ),
    GroupedOption(
        "bvm_group_spawn",
        display_name="Test vehicle",
        description=(
            "Summon personal OakVehicle meshes for movement/jump testing. "
            "Uses dump-backed ServerSetPersonalVehicleDef + ServerRequestPersonalVehicle. "
            "Honors Apply tuning to scope."
        ),
        children=[
            _vehicle_force_locked_opt,
            _vehicle_lock_sticky_opt,
            _spawn_vehicle_choice,
            _spawn_vehicle_button,
            _spawn_vehicle_list_button,
            _spawn_vehicle_scan_button,
        ],
    ),
]


def _kb_reset() -> None:
    _reset_all()


def _kb_show() -> None:
    _show_all()


def _on_registered_vehicle_jump_key(*, from_space: bool) -> None:
    global _last_custom_jump_at, _mod_key_was_down, _space_key_was_down, _space_jump_pending
    if from_space and not BVM_REPEAT_JUMP_PRESS:
        return
    now = time.monotonic()
    if now - _last_custom_jump_at < _vehicle_jump_keybind_cooldown():
        return
    if from_space:
        _space_key_was_down = True
        _space_jump_pending = True
    else:
        _mod_key_was_down = True
    if _apply_vehicle_jump_fast():
        _last_custom_jump_at = now
        if from_space:
            _space_jump_pending = False


def _kb_vehicle_jump(*_args: Any) -> None:
    _on_registered_vehicle_jump_key(from_space=False)


def _kb_space_jump(*_args: Any) -> None:
    _on_registered_vehicle_jump_key(from_space=True)


def _toggle_blimgui_tab() -> None:
    try:
        import blimgui
        blimgui.toggle_registered_tab(_BLIMGUI_TAB)
    except Exception as exc:
        _warn(str(exc))


KEY_OPEN_MENU = keybind(
    "bvm_open_menu",
    key="Ctrl+Alt+F8",
    callback=_toggle_blimgui_tab,
    display_name="Open Vehicle Movement tab",
    description="Toggles BL4 Mod Menu on Vehicle Movement.",
)


KEY_VEHICLE_JUMP = keybind(
    "bvm_vehicle_jump",
    key="N",
    callback=_kb_vehicle_jump,
    display_name="Vehicle jump",
    description=(
        "Extra jump key (default N). Works alongside SpaceBar for unlimited mid-air jumps. "
        "Jump height comes from the Powerslide jump height slider."
    ),
)

KEY_RESET = keybind(
    "bvm_reset_defaults",
    key="Ctrl+Shift+F7",
    callback=_kb_reset,
    display_name="Reset vehicle movement to defaults",
    description="Same as vehicle_move_reset.",
)

KEY_SHOW = keybind(
    "bvm_log_values",
    key="Ctrl+Shift+F4",
    callback=_kb_show,
    display_name="Log vehicle movement values",
    description="Runs vehicle_move_show.",
)


_bvm_mod = None

if not EMBEDDED_IN_SQBT:
    _bvm_mod = build_mod(
        name=MOD_NAME,
        author=__author__,
        description="Vehicle speed, handling, jump/gravity tuning, unlimited mid-air jumps, spawn test vehicles, durability, presets, and console controls.",
        version=__version__,
        supported_games=Game.BL4,
        coop_support=CoopSupport.ClientSide,
        settings_file=SETTINGS_PATH,
        commands=[
            vehicle_move_help,
            vehicle_move_target,
            vehicle_move_show,
            vehicle_move_apply,
            vehicle_move_reset,
            vehicle_move_preset,
            vehicle_move_set,
            vehicle_move_scan_floats,
            vehicle_move_jump_diag,
            vehicle_move_vault_show,
            vehicle_move_vault_zero,
            vehicle_move_vault_set,
            vehicle_move_spawn,
            vehicle_move_spawn_list,
            vehicle_move_spawn_probe,
            vehicle_move_spawn_scan,
            vehicle_move_spawn_scan_offline,
            vehicle_move_spawn_reload,
        ],
        keybinds=[KEY_OPEN_MENU, KEY_VEHICLE_JUMP, KEY_RESET, KEY_SHOW],
        options=BVM_OPTIONS,
        on_enable=_on_enable,
        on_disable=_on_disable,
    )

    if not SETTINGS_PATH.exists():
        try:
            _bvm_mod.enable()
        except Exception:
            pass
