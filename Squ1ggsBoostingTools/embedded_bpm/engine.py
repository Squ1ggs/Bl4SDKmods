# Auto-synced from standalone mod — edit the sidecar and re-run _dev_sync_embedded_tuning.py.

"""
Player Movement — on-foot CharacterMovement tuning for the Python SDK.

**Standalone:** copy ``bl4_player_movement`` into ``sdk_mods`` next to ``mods_base`` and ``unrealsdk``.
Ultra Local Menu is optional. Mods menu sliders, BLImGui tab (bind Keybinds after enabling), and ``player_move_*`` console commands.
Session-only; values may reset on travel.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Any, Callable

import unrealsdk
from mods_base import BoolOption, ButtonOption, CoopSupport, Game, GroupedOption, SliderOption, build_mod, command, keybind
from mods_base import SETTINGS_DIR as _SETTINGS_DIR
from mods_base.options import SpinnerOption
from unrealsdk import logging

EMBEDDED_IN_SQBT = True

__version__ = "1.0.0"
__author__ = "Squ1ggs"
MOD_NAME = "Player Movement"
LOG_PREFIX = "[BPM]"
_BLIMGUI_TAB = "Player Movement"
_BLIMGUI_KEYBIND_LABEL = "Show/hide BLImGui menu — Player Movement"

SETTINGS_PATH = Path(_SETTINGS_DIR) / "bl4_player_movement.json"
SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

from .sqbt_coop import skip_own_blimgui_tab

_SCOPE_LABELS: dict[str, str] = {
    "local": "Local (you only)",
    "all": "All players",
    "others": "Others (not you)",
}
_SCOPE_SPINNER_CHOICES: tuple[str, ...] = tuple(_SCOPE_LABELS.values())
BPM_APPLY_SCOPE: str = "local"

_CORE_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("MinAnalogWalkSpeed", 0.0, 8000.0, 5.0, 600.0, "Walk / analog speed"),
    ("MaxWalkSpeed", 50.0, 8000.0, 5.0, 600.0, "Max walk speed"),
    ("JumpZVelocity", 0.0, 5000.0, 10.0, 620.0, "Jump Z velocity"),
    ("GravityScale", -25.0, 25.0, 0.05, 1.0, "Movement gravity (falling — not glide lift)"),
    ("Mass", 1.0, 5000.0, 5.0, 100.0, "Mass"),
)

_EXTRA_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("MaxWalkSpeedCrouched", 0.0, 2500.0, 5.0, 300.0, "Max walk speed (crouched)"),
    ("MaxAcceleration", 0.0, 16000.0, 50.0, 2048.0, "Max acceleration"),
    ("MaxBrakingDecelerationWalking", 0.0, 16000.0, 50.0, 2048.0, "Max braking decel (walking)"),
    ("MaxBrakingDecelerationFalling", 0.0, 16000.0, 50.0, 0.0, "Max braking decel (falling)"),
    ("MaxBrakingDecelerationFlying", 0.0, 16000.0, 50.0, 0.0, "Max braking decel (flying)"),
    ("BrakingDecelerationWalking", 0.0, 16000.0, 50.0, 2048.0, "Braking deceleration (walking)"),
    ("BrakingDecelerationFalling", 0.0, 16000.0, 50.0, 0.0, "Braking deceleration (falling)"),
    ("BrakingDecelerationFlying", 0.0, 16000.0, 50.0, 0.0, "Braking deceleration (flying)"),
    ("BrakingFrictionFactor", 0.0, 20.0, 0.05, 2.0, "Braking friction factor"),
    ("FallingLateralFriction", 0.0, 20.0, 0.05, 0.0, "Falling lateral friction"),
    ("GroundFriction", 0.0, 50.0, 0.1, 8.0, "Ground friction"),
    ("MaxStepHeight", 0.0, 1000.0, 1.0, 45.0, "Max step height"),
    ("WalkableFloorAngle", 0.0, 89.9, 0.5, 75.0, "Walkable floor angle"),
    ("AirControl", 0.0, 8.0, 0.02, 0.05, "Air control"),
    ("AirControlBoostMultiplier", 0.0, 8.0, 0.02, 1.0, "Air control boost mult"),
    ("MaxFlySpeed", 0.0, 8000.0, 50.0, 600.0, "Max fly speed"),
    ("MaxSwimSpeed", 0.0, 5000.0, 50.0, 300.0, "Max swim speed"),
    ("MaxBrakingDecelerationSwimming", 0.0, 16000.0, 50.0, 0.0, "Max braking decel (swim)"),
    ("BrakingDecelerationSwimming", 0.0, 16000.0, 50.0, 0.0, "Braking deceleration (swim)"),
    ("MaxCustomMovementSpeed", 0.0, 8000.0, 50.0, 0.0, "Max custom movement speed"),
    ("PerchRadiusThreshold", 0.0, 500.0, 1.0, 0.0, "Perch radius threshold"),
    ("Buoyancy", 0.0, 10.0, 0.05, 1.0, "Buoyancy"),
    ("JumpOffJumpZFactor", 0.0, 2.0, 0.02, 0.5, "Jump-off jump Z factor"),
    ("JumpMaxHoldTime", 0.0, 5.0, 0.02, 0.0, "Jump max hold time"),
    ("MaxJumpApexAttemptsPerSimulation", 0.0, 10.0, 1.0, 2.0, "Max jump apex attempts"),
)

# Dump: OakCharacterMovement.LiveGlideSettings.* (separate from GravityScale).
_GLIDE_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("LiveGlideSettings.GlidingGravityScale", -10.0, 10.0, 0.05, 0.0, "Glide gravity scale"),
    (
        "LiveGlideSettings.GlidingUpwardsGravityScale",
        -10.0,
        500.0,
        0.05,
        1.0,
        "Glide upward gravity (lift while gliding)",
    ),
    ("LiveGlideSettings.GlidingSpeed", 0.0, 30_000.0, 50.0, 0.0, "Glide speed"),
    ("LiveGlideSettings.GlidingTerminalVelocity", -5000.0, 5000.0, 10.0, 0.0, "Glide terminal velocity"),
    ("LiveGlideSettings.GlidingAcceleration", 0.0, 50_000.0, 50.0, 0.0, "Glide acceleration"),
    ("LiveGlideSettings.GlidingDeceleration", 0.0, 50_000.0, 50.0, 0.0, "Glide deceleration"),
    ("LiveGlideSettings.DefaultGlidingAirControl", 0.0, 8.0, 0.02, 0.6, "Glide air control"),
    ("LiveGlideSettings.BaseGlidingSpeedBoost", 0.0, 30_000.0, 50.0, 0.0, "Glide speed boost"),
)

_FLOAT_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = _CORE_SPECS + _EXTRA_SPECS

_VAULT_COST_VALUE_PATHS: tuple[str, ...] = (
    "OakCharacterMovement.VaultPowerCost_Dash.Value",
    "OakCharacterMovement.VaultPowerCost_DoubleJump.Value",
    "OakCharacterMovement.VaultPowerCost_Glide.Value",
    "OakCharacterMovement.VaultPowerCost_Grapple.Value",
    "OakCharacterMovement.VaultPowerCost_GroundSlam.Value",
    "OakCharacterMovement.VaultPower_Forgiveness.Value",
)

_PRESETS: dict[str, dict[str, float]] = {
    "fast": {"MinAnalogWalkSpeed": 3200.0, "MaxWalkSpeed": 3200.0, "JumpZVelocity": 560.0},
    "moon": {
        "JumpZVelocity": 2000.0,
        "GravityScale": 0.18,
        "Mass": 35.0,
        "AirControl": 0.4,
        "LiveGlideSettings.GlidingUpwardsGravityScale": 12.0,
        "LiveGlideSettings.GlidingGravityScale": -0.12,
        "LiveGlideSettings.GlidingSpeed": 2200.0,
        "LiveGlideSettings.DefaultGlidingAirControl": 1.2,
    },
    "glide_up": {
        "LiveGlideSettings.GlidingUpwardsGravityScale": 6.0,
        "LiveGlideSettings.GlidingGravityScale": -0.35,
        "LiveGlideSettings.GlidingSpeed": 2600.0,
    },
}

_PATH_SEG_BRACKET_RE = re.compile(r"^([^[\]]+)\[(\d+)\]$")
_suppress_option_apply = False


def _info(msg: str) -> None:
    logging.info(f"{LOG_PREFIX} {msg}")


def _warn(msg: str) -> None:
    logging.warning(f"{LOG_PREFIX} {msg}")


def _err(msg: str) -> None:
    logging.error(f"{LOG_PREFIX} {msg}")


def _collapsing_open(result: Any) -> bool:
    if isinstance(result, tuple):
        return bool(result[0]) if result else False
    return bool(result)


def _collapsing_header(imgui: Any, label: str, *, default_open: bool = True) -> bool:
    flags = 0
    if default_open:
        flags = getattr(getattr(imgui, "TreeNodeFlags_", None), "default_open", 0)
    return _collapsing_open(imgui.collapsing_header(label, flags))


def _set_option_value_silent(option: Any, value: Any) -> None:
    global _suppress_option_apply
    previous = _suppress_option_apply
    _suppress_option_apply = True
    try:
        option.value = value
    finally:
        _suppress_option_apply = previous


def _blimgui_defer(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Run UObject work after the ImGui frame (avoids tab-switch crashes)."""
    try:
        import blimgui

        blimgui.defer_post_frame(lambda: fn(*args, **kwargs))
    except Exception:
        fn(*args, **kwargs)


def _is_cdo(obj: Any) -> bool:
    try:
        return "Default__" in str(getattr(obj, "Name", "") or "")
    except Exception:
        return False


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
        key = id(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _try_pawn(pc: Any) -> Any | None:
    for a in ("Pawn", "Character", "ControlledPawn", "MyPawn", "AcknowledgedPawn"):
        try:
            v = getattr(pc, a, None)
            if v is not None:
                return v
        except Exception:
            continue
    return None


def _is_local_pc(pc: Any) -> bool:
    if pc is None:
        return False
    for attr_name in ("IsLocalPlayerController", "IsPrimaryPlayer", "bIsLocalPlayerController"):
        try:
            attr = getattr(pc, attr_name, None)
            if callable(attr):
                if bool(attr()):
                    return True
            elif attr is not None and bool(attr):
                return True
        except Exception:
            continue
    try:
        return int(getattr(pc, "PlayerIndex", -1)) == 0
    except Exception:
        return False


def _get_local_pc(candidates: list[Any] | None = None) -> Any | None:
    if candidates is None:
        candidates = [p for p in _iter_pcs() if not _is_cdo(p)]
    if not candidates:
        return None
    local = [p for p in candidates if _is_local_pc(p)]
    pool = local or candidates
    with_pawn = [p for p in pool if _try_pawn(p) is not None]
    pool = with_pawn or pool
    return pool[0] if pool else None


def _scope_from_spinner_label(lab: str) -> str:
    for key, disp in _SCOPE_LABELS.items():
        if disp == lab:
            return key
    return "local"


def _iter_pawns_for_scope() -> list[tuple[Any, str]]:
    pcs = [p for p in _iter_pcs() if not _is_cdo(p)]
    if not pcs:
        return []
    local_pc = _get_local_pc(pcs)
    out: list[tuple[Any, str]] = []
    if BPM_APPLY_SCOPE == "local":
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
        if BPM_APPLY_SCOPE == "others" and is_loc:
            continue
        label = "?"
        try:
            ps = getattr(pc, "PlayerState", None) or getattr(pc, "OakPlayerState", None)
            label = str(getattr(ps, "PlayerName", None) or getattr(pc, "Name", None) or "?")
        except Exception:
            label = str(getattr(pc, "Name", "?"))
        out.append((pw, label))
    return out


def _resolve_character_movement(pawn: Any) -> tuple[str, Any] | None:
    if pawn is None:
        return None
    for attr in (
        "CharMoveComp",
        "CharacterMovement",
        "OakCharacterMovement",
        "GbxCharacterMovement",
        "MovementComponent",
    ):
        try:
            comp = getattr(pawn, attr, None)
        except Exception:
            comp = None
        if comp is not None and not _is_cdo(comp):
            return (f"pawn.{attr}", comp)
    for cls in ("OakCharacterMovementComponent", "GbxCharacterMovementComponent", "CharacterMovementComponent"):
        try:
            for comp in unrealsdk.find_all(cls, exact=False):
                if comp is None or _is_cdo(comp):
                    continue
                owner = (
                    getattr(comp, "OakCharacterOwner", None)
                    or getattr(comp, "CharacterOwner", None)
                    or getattr(comp, "PawnOwner", None)
                )
                if owner is pawn:
                    return (f"{cls}", comp)
        except Exception:
            continue
    return None


def _write_attr_struct(attr: Any, value: float) -> bool:
    if attr is None:
        return False
    wrote = False
    for field in ("Value", "BaseValue", "CurrentValue", "Base", "Current"):
        try:
            setattr(attr, field, float(value))
            wrote = True
        except Exception:
            pass
    return wrote


def _write_move_float(comp: Any, attr: str, value: float) -> bool:
    if comp is None:
        return False
    try:
        current = getattr(comp, attr, None)
    except Exception:
        current = None
    if _write_attr_struct(current, value):
        return True
    try:
        setattr(comp, attr, float(value))
        return True
    except Exception:
        return False


def _parse_attr_segment(seg: str) -> tuple[str, int | None]:
    m = _PATH_SEG_BRACKET_RE.match(seg.strip())
    if m:
        return m.group(1), int(m.group(2))
    return seg.strip(), None


def _pawn_get_path(root: Any, path: str) -> Any | None:
    obj: Any = root
    for part in [p for p in path.split(".") if p]:
        name, idx = _parse_attr_segment(part)
        try:
            obj = getattr(obj, name)
        except Exception:
            return None
        if obj is None:
            return None
        if idx is not None:
            try:
                obj = obj[idx]
            except Exception:
                return None
    return obj


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
        cur = getattr(obj, name, None)
        if _write_attr_struct(cur, float(value)):
            return True
        setattr(obj, name, value)
        return True
    except Exception:
        return False


def _write_comp_path(comp: Any, path: str, value: float) -> bool:
    return _pawn_set_path(comp, path, value)


def _write_glide_value(pawn: Any, comp: Any, rel_path: str, value: float) -> bool:
    wrote = False
    if _write_comp_path(comp, rel_path, value):
        wrote = True
    leaf = rel_path.rsplit(".", 1)[-1]
    if leaf != rel_path and _write_move_float(comp, leaf, value):
        wrote = True
    if _pawn_set_path(pawn, f"OakCharacterMovement.{rel_path}", value):
        wrote = True
    return wrote


def _movement_hits() -> list[tuple[str, Any, Any]]:
    hits: list[tuple[str, Any, Any]] = []
    for pawn, who in _iter_pawns_for_scope():
        hit = _resolve_character_movement(pawn)
        if hit is None:
            continue
        path, comp = hit
        hits.append((f"{path} [{who}]", pawn, comp))
    return hits


def _apply_saved_tuning(*, log: bool = True) -> bool:
    hits = _movement_hits()
    if not hits:
        if log:
            _warn("No character movement component for current scope — load in-world first.")
        return False
    writes = 0
    targets = {spec[0]: float(opt.value) for opt, spec in zip(_slider_all, _FLOAT_SPECS, strict=True)}
    glide_targets = {spec[0]: float(opt.value) for opt, spec in zip(_slider_glide, _GLIDE_SPECS, strict=True)}
    for path, pawn, comp in hits:
        for attr, value in targets.items():
            if _write_move_float(comp, attr, value):
                writes += 1
        for rel_path, value in glide_targets.items():
            if _write_glide_value(pawn, comp, rel_path, value):
                writes += 1
        v = max(0.0, float(_vault_cost_slider.value))
        for rel in _VAULT_COST_VALUE_PATHS:
            if _pawn_set_path(pawn, rel, v):
                writes += 1
    if log:
        _info(f"Applied player movement tuning ({writes} write(s) across {len(hits)} pawn(s)).")
    return writes > 0


def _show_all() -> None:
    hits = _movement_hits()
    if not hits:
        _warn("No movement component for current scope.")
        return
    for path, _pawn, comp in hits:
        _info(f"Movement values {path}:")
        for attr, *_rest in _FLOAT_SPECS:
            try:
                v = getattr(comp, attr, None)
                if hasattr(v, "Value"):
                    v = getattr(v, "Value")
                _info(f"  {attr} = {float(v)}")
            except Exception:
                _info(f"  {attr} = <missing>")
        for rel_path, *_rest in _GLIDE_SPECS:
            v = _pawn_get_path(comp, rel_path)
            if v is None:
                v = _pawn_get_path(pawn, f"OakCharacterMovement.{rel_path}")
            if v is None:
                _info(f"  {rel_path} = <missing>")
            else:
                try:
                    _info(f"  {rel_path} = {float(v)}")
                except Exception:
                    _info(f"  {rel_path} = {v!r}")


def _reset_all() -> None:
    for opt, spec in zip(_slider_all, _FLOAT_SPECS, strict=True):
        opt.value = float(spec[4])
    for opt, spec in zip(_slider_glide, _GLIDE_SPECS, strict=True):
        opt.value = float(spec[4])
    _vault_cost_slider.value = 12.0
    _apply_saved_tuning()


def _apply_preset(name: str) -> None:
    key = name.strip().lower()
    preset = _PRESETS.get(key)
    if preset is None:
        _err(f"Unknown preset {name!r}. Try: {', '.join(sorted(_PRESETS))}")
        return
    for opt, spec in zip(_slider_all, _FLOAT_SPECS, strict=True):
        if spec[0] in preset:
            opt.value = float(preset[spec[0]])
    for opt, spec in zip(_slider_glide, _GLIDE_SPECS, strict=True):
        if spec[0] in preset:
            opt.value = float(preset[spec[0]])
    _apply_saved_tuning()
    _info(f"Preset {key} applied.")


def _apply_field(field: str, value: float) -> None:
    key = field.strip()
    spec_map = {s[0].casefold(): s[0] for s in _FLOAT_SPECS}
    spec_map.update({s[0].casefold(): s[0] for s in _GLIDE_SPECS})
    spec_map.update({s[0].rsplit(".", 1)[-1].casefold(): s[0] for s in _GLIDE_SPECS})
    attr = spec_map.get(key.casefold(), key)
    matched = False
    for opt, spec in zip(_slider_all, _FLOAT_SPECS, strict=True):
        if spec[0] == attr:
            opt.value = float(value)
            matched = True
            break
    if not matched:
        for opt, spec in zip(_slider_glide, _GLIDE_SPECS, strict=True):
            if spec[0] == attr:
                opt.value = float(value)
                matched = True
                break
    if not matched:
        _warn(f"Unknown field {field!r}")
        return
    _apply_saved_tuning()


def _vault_set_uniform(value: float, *, label: str = "set") -> None:
    v = max(0.0, float(value))
    pawns = _iter_pawns_for_scope()
    if not pawns:
        _err("No pawns for current scope.")
        return
    for pawn, who in pawns:
        ok = sum(1 for rel in _VAULT_COST_VALUE_PATHS if _pawn_set_path(pawn, rel, v))
        _info(f"vault {label} [{who}]: {ok}/{len(_VAULT_COST_VALUE_PATHS)} paths = {v}")


def _draw_blimgui_tab() -> None:
    global BPM_APPLY_SCOPE
    try:
        from blimgui import imgui
    except Exception:
        return
    imgui.text_wrapped("On-foot CharacterMovement tuning. Load in-world, then apply.")
    imgui.text_disabled("Tip: Mods → Keybinds → Show/hide BLImGui menu — Player Movement toggles this panel.")
    imgui.spacing()
    for key, label in (("local", "Local"), ("all", "All"), ("others", "Others")):
        if imgui.radio_button(f"{label}##bpm_f1_scope_{key}", BPM_APPLY_SCOPE == key):
            BPM_APPLY_SCOPE = key
            _set_option_value_silent(_target_scope, _SCOPE_LABELS[key])
        imgui.same_line()
    imgui.new_line()

    def _slider_rows(sliders: list[Any], specs: tuple[Any, ...]) -> None:
        for opt, spec in zip(sliders, specs, strict=True):
            attr, lo, hi, step, default, title = spec[:6]
            imgui_id = str(attr).replace(".", "_")
            try:
                current = float(opt.value)
            except Exception:
                current = float(default)
            moved, value = imgui.slider_float(f"{title}##bpm_f1_{imgui_id}", current, float(lo), float(hi))
            if moved:
                _set_option_value_silent(opt, float(value))
            typed, exact = imgui.input_float(
                f"Exact##bpm_f1_exact_{imgui_id}", current, float(step), float(step) * 10.0, "%.3f",
            )
            if typed:
                _set_option_value_silent(opt, float(exact))

    def _sliders(title: str, sliders: list[Any], specs: tuple[Any, ...]) -> None:
        if _collapsing_header(imgui, title):
            _slider_rows(sliders, specs)

    _sliders("Core", _slider_core, _CORE_SPECS)
    _sliders("Extra", _slider_extra, _EXTRA_SPECS)
    _sliders("Glide (LiveGlideSettings)", _slider_glide, _GLIDE_SPECS)
    imgui.text_disabled("Glide upward gravity is separate from Movement gravity above.")
    if _collapsing_header(imgui, "Vault costs", default_open=False):
        v = float(_vault_cost_slider.value)
        moved, nv = imgui.slider_float("Vault traversal power costs##bpm_f1_vault", v, 0.0, 200.0)
        if moved:
            _set_option_value_silent(_vault_cost_slider, float(nv))
            _blimgui_defer(_vault_set_uniform, float(nv), label="slider")
    if _collapsing_header(imgui, "Presets", default_open=False):
        for index, name in enumerate(("fast", "moon", "glide_up")):
            if imgui.button(f"{name.title()}##bpm_f1_preset_{name}"):
                _blimgui_defer(_apply_preset, name)
            if index % 2 != 1:
                imgui.same_line()
    if imgui.button("Apply all##bpm_f1_apply"):
        _blimgui_defer(_apply_saved_tuning)
    imgui.same_line()
    if imgui.button("Reset##bpm_f1_reset"):
        _blimgui_defer(_reset_all)


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


def _log_blimgui_enable_hint() -> None:
    _info(
        f"Enabled. In the mods menu open Keybinds and assign «{_BLIMGUI_KEYBIND_LABEL}» "
        "to show or hide this mod's BLImGui panel."
    )


def _on_enable() -> None:
    global BPM_APPLY_SCOPE
    BPM_APPLY_SCOPE = _scope_from_spinner_label(str(_target_scope.value))
    if not EMBEDDED_IN_SQBT:
        _register_blimgui()
        _log_blimgui_enable_hint()


def _on_disable() -> None:
    _unregister_blimgui()


def _build_sliders_from(
    specs: tuple[tuple[str, float, float, float, float, str], ...],
) -> list[SliderOption]:
    out: list[SliderOption] = []
    for attr, lo, hi, step, default, title in specs:
        opt = SliderOption(
            f"bpm_slider_{attr}",
            float(default),
            float(lo),
            float(hi),
            step=float(step),
            is_integer=False,
            display_name=title,
            description=f"CharacterMovement.{attr}",
        )

        @opt.set_on_change()
        def _on_slider(_: Any, _value: float, *, _attr: str = attr) -> None:
            if _suppress_option_apply:
                return
            _apply_saved_tuning(log=False)

        out.append(opt)
    return out


def _build_path_sliders_from(
    specs: tuple[tuple[str, float, float, float, float, str], ...],
    *,
    prefix: str,
) -> list[SliderOption]:
    out: list[SliderOption] = []
    for path, lo, hi, step, default, title in specs:
        key = prefix + path.replace(".", "_")
        opt = SliderOption(
            key,
            float(default),
            float(lo),
            float(hi),
            step=float(step),
            is_integer=False,
            display_name=title,
            description=f"OakCharacterMovement.{path}",
        )

        @opt.set_on_change()
        def _on_path_slider(_: Any, _value: float, *, _path: str = path) -> None:
            if _suppress_option_apply:
                return
            _apply_saved_tuning(log=False)

        out.append(opt)
    return out


_slider_core = _build_sliders_from(_CORE_SPECS)
_slider_extra = _build_sliders_from(_EXTRA_SPECS)
_slider_glide = _build_path_sliders_from(_GLIDE_SPECS, prefix="bpm_glide_")
_slider_all = _slider_core + _slider_extra

_vault_cost_slider = SliderOption(
    "bpm_vault_cost_uniform",
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
    if _suppress_option_apply:
        return
    _vault_set_uniform(float(value), label="slider")


_target_scope = SpinnerOption(
    "bpm_target_scope",
    _SCOPE_LABELS["local"],
    _SCOPE_SPINNER_CHOICES,
    wrap_enabled=True,
    display_name="Apply tuning to",
    description="Local = you only. All / Others for co-op experiments.",
)


@_target_scope.set_on_change()
def _on_target_scope(_: Any, value: str) -> None:
    global BPM_APPLY_SCOPE
    BPM_APPLY_SCOPE = _scope_from_spinner_label(str(value))
    _info(f"apply scope → {BPM_APPLY_SCOPE}")


_apply_button = ButtonOption(
    "bpm_apply_btn",
    display_name="Apply all changes",
    description="Push every slider to the current scope.",
)


@_apply_button
def _on_apply_btn(_: Any) -> None:
    _apply_saved_tuning()


_reset_button = ButtonOption(
    "bpm_reset_btn",
    display_name="Reset all (defaults)",
    description="Same as player_move_reset.",
)


@_reset_button
def _on_reset_btn(_: Any) -> None:
    _reset_all()


_ulm_hint = BoolOption(
    "bpm_ulm_hint",
    False,
    display_name="Hint: forward to ulm tune show (optional)",
    description="If Ultra Local Menu is loaded, run ulm tune show once for cross-check.",
)


@_ulm_hint.set_on_change()
def _on_ulm_hint(_: Any, value: bool) -> None:
    if not value:
        return
    try:
        import ultra_local_menu as ulm

        fn = getattr(ulm, "_dispatch", None)
        if callable(fn):
            fn("ulm tune show", len("ulm"))
            _info("Forwarded: ulm tune show")
    except Exception as exc:
        _warn(f"ulm not available: {exc}")


_preset_buttons: list[ButtonOption] = []
for pname, pdesc in (
    ("fast", "High walk + moderate jump"),
    ("moon", "Low gravity, high jump, floaty glide"),
    ("glide_up", "Strong upward glide lift"),
):
    btn = ButtonOption(
        f"bpm_preset_btn_{pname}",
        display_name=f"Preset: {pname}",
        description=pdesc,
    )

    @btn
    def _on_preset(_: Any, _n: str = pname) -> None:
        _apply_preset(_n)

    _preset_buttons.append(btn)


@command("player_move_help", description="List Player Movement console commands.")
def player_move_help(_args: argparse.Namespace) -> None:
    for ln in (
        "Player Movement — on-foot CharacterMovement tuning.",
        "  BLImGui panel: Mods → Keybinds → Show/hide BLImGui menu — Player Movement",
        "  player_move_apply / player_move_reset / player_move_show",
        "  player_move_target <local|all|others>",
        "  player_move_set <Field> <n>",
        "  player_move_preset <fast|moon|glide_up>",
        "  player_move_vault_zero / player_move_vault_set <n>",
    ):
        _info(ln)


@command("player_move_apply", description="Apply every saved player movement slider.")
def player_move_apply(_args: argparse.Namespace) -> None:
    _apply_saved_tuning()


@command("player_move_reset", description="Reset sliders to defaults and apply.")
def player_move_reset(_args: argparse.Namespace) -> None:
    _reset_all()


@command("player_move_show", description="Log current movement floats.")
def player_move_show(_args: argparse.Namespace) -> None:
    _show_all()


@command("player_move_target", description="Set apply scope: local, all, or others.")
def player_move_target(args: argparse.Namespace) -> None:
    key = str(args.scope).strip().lower()
    if key not in _SCOPE_LABELS:
        _err(f"Unknown scope {args.scope!r}")
        return
    global BPM_APPLY_SCOPE
    BPM_APPLY_SCOPE = key
    _target_scope.value = _SCOPE_LABELS[key]
    _info(f"apply scope → {key}")


player_move_target.add_argument("scope", help="local | all | others")


@command("player_move_set", description="Set one movement field and apply.")
def player_move_set(args: argparse.Namespace) -> None:
    _apply_field(str(args.field), float(args.value))


player_move_set.add_argument("field", help="Property name, e.g. MaxWalkSpeed")
player_move_set.add_argument("value", type=float, help="Float value")


@command("player_move_preset", description="Apply a named preset (fast|moon|glide_up).")
def player_move_preset(args: argparse.Namespace) -> None:
    _apply_preset(str(args.name))


player_move_preset.add_argument("name", help="fast | moon | glide_up")


@command("player_move_vault_zero", description="Zero vault power costs on scoped pawn(s).")
def player_move_vault_zero(_args: argparse.Namespace) -> None:
    _vault_cost_slider.value = 0.0
    _vault_set_uniform(0.0, label="zero")


@command("player_move_vault_set", description="Set all vault power costs to one value (>= 0).")
def player_move_vault_set(args: argparse.Namespace) -> None:
    v = max(0.0, float(args.value))
    _vault_cost_slider.value = v
    _vault_set_uniform(v, label="set")


player_move_vault_set.add_argument("value", type=float, help="Uniform cost (0 = free).")


def _toggle_blimgui_tab() -> None:
    try:
        import blimgui

        blimgui.toggle_registered_tab(_BLIMGUI_TAB)
    except Exception as exc:
        _warn(str(exc))


KEY_OPEN_MENU = keybind(
    "bpm_open_menu",
    key="Ctrl+Shift+F9",
    callback=_toggle_blimgui_tab,
    display_name=_BLIMGUI_KEYBIND_LABEL,
    description="In the mods menu: Keybinds → assign this key to open or close the BLImGui panel.",
)

KEY_RESET = keybind(
    "bpm_reset_defaults",
    key="Ctrl+Shift+F5",
    callback=lambda: _reset_all(),
    display_name="Reset player movement to defaults",
    description="Same as player_move_reset.",
)

_blimgui_keybind_btn = ButtonOption(
    "bpm_blimgui_keybind_hint",
    display_name="FIRST: Keybinds opens the BLImGui panel",
    description=(
        "This mod registers a BLImGui panel that stays hidden until you bind a key. "
        f"In the mods menu go to Keybinds and assign «{_BLIMGUI_KEYBIND_LABEL}»."
    ),
)


@_blimgui_keybind_btn
def _on_blimgui_keybind_hint(_: Any) -> None:
    _info("Mods → Keybinds → Show/hide BLImGui menu — Player Movement (opens/closes the BLImGui panel)")

BPM_OPTIONS: list[GroupedOption | BoolOption | ButtonOption | SliderOption | SpinnerOption] = [
    _blimgui_keybind_btn,
    _target_scope,
    GroupedOption(
        "bpm_group_core",
        display_name="Core movement",
        description="Walk, jump, gravity, and mass.",
        children=_slider_core,
    ),
    GroupedOption(
        "bpm_group_extra",
        display_name="Extra movement",
        description="Accel, braking, friction, air/swim, step height, and related fields.",
        children=_slider_extra,
    ),
    GroupedOption(
        "bpm_group_glide",
        display_name="Glide / vault traversal",
        description="LiveGlideSettings from OakCharacterMovement dumps (upward glide lift is NOT GravityScale).",
        children=_slider_glide,
    ),
    GroupedOption(
        "bpm_vault_group",
        display_name="Vault costs",
        description="Uniform vault traversal power costs on OakCharacterMovement.",
        children=[_vault_cost_slider],
    ),
    GroupedOption(
        "bpm_presets",
        display_name="Presets and actions",
        description="Quick presets, apply, reset, and optional ULM cross-check.",
        children=[*_preset_buttons, _apply_button, _reset_button, _ulm_hint],
    ),
]

if not EMBEDDED_IN_SQBT:
    build_mod(
        name=MOD_NAME,
        author=__author__,
        description=(
            f"On-foot movement tuning. After enabling here, open Keybinds in the mods menu and assign "
            f"«{_BLIMGUI_KEYBIND_LABEL}» to open the BLImGui panel."
        ),
        version=__version__,
        supported_games=Game.BL4,
        coop_support=CoopSupport.ClientSide,
        settings_file=SETTINGS_PATH,
        commands=[
            player_move_help,
            player_move_apply,
            player_move_reset,
            player_move_show,
            player_move_target,
            player_move_set,
            player_move_preset,
            player_move_vault_zero,
            player_move_vault_set,
        ],
        keybinds=[KEY_OPEN_MENU, KEY_RESET],
        options=BPM_OPTIONS,
        on_enable=_on_enable,
        on_disable=_on_disable,
    )

try:
    BPM_APPLY_SCOPE = _scope_from_spinner_label(str(_target_scope.value))
except Exception:
    pass
