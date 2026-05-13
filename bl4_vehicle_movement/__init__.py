"""
BL4 Vehicle Movement — vehicle / Chaos movement tuning for the Python SDK.

**Standalone:** copy only the ``bl4_vehicle_movement`` folder into your ``sdk_mods`` directory next to the SDK's
``mods_base`` and ``unrealsdk`` packages. Ultra Local Menu is **not** required; the optional "forward to ulm" hint
is ignored safely if ULM is absent.

Mods → BL4 Vehicle Movement: **Apply tuning to** (local / all / others), sliders, keybinds. Console: vehicle_move_* commands.
Enter a vehicle first. Session-only; may reset on travel.
"""

from __future__ import annotations

import argparse
import re
from typing import Any

import unrealsdk
from mods_base import CoopSupport, Game, BoolOption, ButtonOption, GroupedOption, SliderOption, build_mod, command, keybind
from mods_base.options import SpinnerOption
from unrealsdk import logging

__version__ = "1.0.5"
__author__ = "Squ1ggs"
MOD_NAME = "BL4 Vehicle Movement"
LOG_PREFIX = "[BVM]"
SETTINGS_PATH = __import__("pathlib").Path(__file__).resolve().parent.parent / "settings" / "bl4_vehicle_movement.json"
SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

_DEFAULT_MAX_WALK_SPEED = 600.0
_DEFAULT_JUMP_Z = 620.0
_DEFAULT_GRAVITY_SCALE = 1.0
_DEFAULT_MASS = 100.0

_CORE_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
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

_EXTRA_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
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

_FLOAT_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = _CORE_SPECS + _EXTRA_SPECS

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


def _get_local_pc() -> Any | None:
    candidates = [p for p in _iter_pcs() if not _is_cdo(p)]
    if not candidates:
        return None
    with_pawn = [p for p in candidates if _try_pawn(p) is not None]
    pool = with_pawn or candidates
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


def _scope_from_spinner_label(lab: str) -> str:
    for key, disp in _SCOPE_LABELS.items():
        if disp == lab:
            return key
    return "local"


def _iter_pawns_for_bvm_scope() -> list[tuple[Any, str]]:
    pcs = [p for p in _iter_pcs() if not _is_cdo(p)]
    if not pcs:
        return []
    local_pc = _get_local_pc()
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
            return None
        vds = getattr(vdc, "VehicleDriverState", None)
        if vds is None:
            return None
        dv = getattr(vds, "DrivenVehicle", None)
        return dv if dv is not None else None
    except Exception:
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


def _iter_bvm_vehicle_hits() -> list[tuple[str, Any]]:
    hits: list[tuple[str, Any]] = []
    for pawn, who in _iter_pawns_for_bvm_scope():
        hit = _resolve_vehicle_movement_from_pawn(pawn)
        if hit is None:
            continue
        path, comp = hit
        hits.append((f"{path} [{who}]", comp))
    return hits


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


def _movement_hits_or_warn() -> list[tuple[str, Any]]:
    hits = _iter_bvm_vehicle_hits()
    if not hits:
        _err(
            "No vehicle movement for current scope — each target must be **in a vehicle** (or expose vehicle movement). "
            "Try **Apply tuning to** = Local + enter a vehicle, or `vehicle_move_target local`.",
        )
    return hits


def _apply_field(attr: str, value: float) -> None:
    hits = _movement_hits_or_warn()
    if not hits:
        return
    wrote = 0
    for path, comp in hits:
        if _read_float(comp, attr) is None:
            continue
        if _write_float(comp, attr, float(value)):
            _info(f"Set {path}.{attr} = {value}")
            wrote += 1
    if wrote == 0:
        _warn(f"No targets wrote {attr!r} (missing float or blocked).")


def _reset_all() -> None:
    hits = _movement_hits_or_warn()
    if not hits:
        return
    defaults = {spec[0]: spec[4] for spec in _FLOAT_SPECS}
    total = 0
    for path, comp in hits:
        ok = 0
        for attr, val in defaults.items():
            if _read_float(comp, attr) is not None and _write_float(comp, attr, float(val)):
                ok += 1
        total += ok
        _info(f"Reset {ok} float fields on {path}")
    _info(f"Total float writes this reset: {total}")


def _show_all() -> None:
    hits = _movement_hits_or_warn()
    if not hits:
        return
    for path, comp in hits:
        _info(f"Vehicle movement: {path}")
        for attr, _vmin, _vmax, _step, _defv, title in _FLOAT_SPECS:
            v = _read_float(comp, attr)
            if v is not None:
                _info(f"  {title} ({attr}) = {v}")


def _scan_floats(max_lines: int) -> None:
    hits = _movement_hits_or_warn()
    if not hits:
        return
    per = max(5, max_lines // max(1, len(hits)))
    for path, comp in hits:
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
    "boost": {"MinAnalogWalkSpeed": 1800.0, "MaxWalkSpeed": 1800.0, "MaxAcceleration": 12000.0},
    "crawl": {"MinAnalogWalkSpeed": 220.0, "MaxWalkSpeed": 220.0, "MaxAcceleration": 600.0},
    "floaty": {"GravityScale": 0.45, "JumpZVelocity": 900.0},
    "orbit": {"GravityScale": -2.0, "MinAnalogWalkSpeed": 950.0, "MaxWalkSpeed": 950.0, "JumpZVelocity": 750.0},
    "heavy": {"Mass": 2500.0, "MinAnalogWalkSpeed": 420.0, "MaxWalkSpeed": 420.0, "GroundFriction": 14.0},
    "drift": {
        "GroundFriction": 0.12,
        "BrakingDecelerationWalking": 150.0,
        "MinAnalogWalkSpeed": 1100.0,
        "MaxWalkSpeed": 1100.0,
    },
}


def _apply_preset(name: str) -> None:
    key = name.strip().lower()
    if key not in _PRESETS:
        _err(f"Unknown preset {name!r}. Try: {', '.join(sorted(_PRESETS))}")
        return
    hits = _movement_hits_or_warn()
    if not hits:
        return
    for path, comp in hits:
        for attr, val in _PRESETS[key].items():
            if _read_float(comp, attr) is not None and _write_float(comp, attr, float(val)):
                _info(f"preset {key}: set {path}.{attr} = {val}")
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
    global BVM_APPLY_SCOPE
    key = _bvm_scope_from_cli_token(str(getattr(args, "scope", "")))
    if key is None:
        _err(f"Unknown scope {getattr(args, 'scope', '')!r}. Use: local, all, others (or copy the Mods menu labels).")
        return
    BVM_APPLY_SCOPE = key
    _info(f"apply scope → {BVM_APPLY_SCOPE} ({_SCOPE_LABELS[BVM_APPLY_SCOPE]})")
    _warn("Co-op: writes on remote pawns may not replicate; host / solo is the reliable case.")


vehicle_move_target.add_argument("scope", help="local | all | others")


@command("vehicle_move_help", description="List BL4 Vehicle Movement console commands.")
def vehicle_move_help(_args: argparse.Namespace) -> None:
    _info("BL4 Vehicle Movement:")
    _info("  vehicle_move_show              — log floats that exist on vehicle movement")
    _info("  vehicle_move_reset             — reset to mod defaults (fields that exist)")
    _info("  vehicle_move_preset <name>     — boost | crawl | floaty | orbit | heavy | drift")
    _info("  vehicle_move_set <Field> <n>   — one float, e.g. MaxWalkSpeed 1200")
    _info("  vehicle_move_scan_floats [N]   — discovery (default 80)")
    _info("  vehicle_move_vault_show / vehicle_move_vault_zero / vehicle_move_vault_set <n>")
    _info("  vehicle_move_preset …          — includes **orbit** (upward gravity on vehicle movement)")
    _info("  vehicle_move_target <local|all|others> — who receives slider / preset / vault writes (same as Mods spinner)")
    _info("Enter a vehicle first (per target). Mods → BL4 Vehicle Movement: **Apply tuning to** + sliders + keybinds.")


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


@command("vehicle_move_set", description="Set one float on vehicle movement (e.g. MaxWalkSpeed 1200).")
def vehicle_move_set(args: argparse.Namespace) -> None:
    _apply_field(args.field, float(args.value))


vehicle_move_set.add_argument("field", help="Property name")
vehicle_move_set.add_argument("value", type=float, help="Float value")


@command("vehicle_move_scan_floats", description="List float fields on the vehicle movement component.")
def vehicle_move_scan_floats(args: argparse.Namespace) -> None:
    _scan_floats(max(5, min(400, int(args.maxn))))


vehicle_move_scan_floats.add_argument("maxn", nargs="?", default="80", help="Max lines (default 80).")


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
            f"bvm_slider_{attr}",
            float(default),
            float(vmin),
            float(vmax),
            step=float(step),
            is_integer=False,
            display_name=title,
            description=(
                f"Writes {attr} on each resolved vehicle movement component for the current **Apply tuning to** scope "
                "when the field exists (each target should be in a vehicle)."
            ),
        )

        @opt
        def _on_slider(_: Any, value: float, _attr: str = attr) -> None:
            _apply_field(_attr, float(value))

        opts.append(opt)
    return opts


_slider_core = _build_sliders_from(_CORE_SPECS)
_slider_extra = _build_sliders_from(_EXTRA_SPECS)

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
    display_name="Vault power costs (driver pawn, all same .Value)",
    description=(
        "Same vault paths as the player mod — writes **pawn.OakCharacterMovement** `.Value` fields for each pawn "
        "in the current **Apply tuning to** scope (0 = free)."
    ),
)


@_vault_cost_slider
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


@_ulm_hint
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


_target_scope = SpinnerOption(
    "bvm_target_scope",
    _SCOPE_LABELS["local"],
    _SCOPE_SPINNER_CHOICES,
    wrap_enabled=True,
    display_name="Apply tuning to",
    description=(
        "**Local** — only your pawn. **All** — every player pawn we can find. **Others** — everyone except you. "
        "Vehicle fields resolve per pawn (usually requires that player to be **in a vehicle**). "
        "Co-op: remote writes may not replicate."
    ),
)


@_target_scope
def _on_bvm_target_scope(_: Any, value: str) -> None:
    global BVM_APPLY_SCOPE
    BVM_APPLY_SCOPE = _scope_from_spinner_label(str(value))
    _info(f"apply scope → {BVM_APPLY_SCOPE}")


BVM_OPTIONS: list[Any] = [
    GroupedOption(
        "bvm_group_scope",
        display_name="Who receives tuning",
        description="Sliders, presets, reset/show, vault controls, keybinds, and vehicle_move_* all respect this.",
        children=[_target_scope],
    ),
    GroupedOption(
        "bvm_group_core",
        display_name="Core (speed / jump / gravity / mass)",
        description="Enter a vehicle first. vehicle_move_show reads live values.",
        children=list(_slider_core),
    ),
    GroupedOption(
        "bvm_group_extra",
        display_name="Advanced (accel, friction, air, swim, slope, …)",
        description="Extra floats when the Chaos / vehicle component exposes them.",
        children=list(_slider_extra),
    ),
    GroupedOption(
        "bvm_vault_group",
        display_name="Vault traversal (driver pawn costs)",
        description="Lowers dash / double-jump / glide / grapple / slam / forgiveness costs on **pawn.OakCharacterMovement** for each pawn in **Apply tuning to**.",
        children=[_vault_cost_slider, _vault_zero_button, _vault_show_button],
    ),
    GroupedOption(
        "bvm_presets",
        display_name="Presets",
        description="One-click bundles; missing fields are skipped.",
        children=[*_preset_buttons, _reset_button, _show_button, _ulm_hint],
    ),
]


def _kb_reset() -> None:
    _reset_all()


def _kb_show() -> None:
    _show_all()


KEY_RESET = keybind(
    "bvm_reset_defaults",
    key="Ctrl+Shift+F7",
    callback=_kb_reset,
    display_name="Reset vehicle movement to defaults",
    description="Same as vehicle_move_reset.",
)

KEY_SHOW = keybind(
    "bvm_log_values",
    key="Ctrl+Shift+F8",
    callback=_kb_show,
    display_name="Log vehicle movement values",
    description="Runs vehicle_move_show.",
)


_bvm_mod = build_mod(
    name=MOD_NAME,
    author=__author__,
    description="Vehicle / Chaos movement sliders, presets, and vehicle_move_* console commands.",
    version=__version__,
    supported_games=Game.BL4,
    coop_support=CoopSupport.ClientSide,
    settings_file=SETTINGS_PATH,
    commands=[
        vehicle_move_help,
        vehicle_move_target,
        vehicle_move_show,
        vehicle_move_reset,
        vehicle_move_preset,
        vehicle_move_set,
        vehicle_move_scan_floats,
        vehicle_move_vault_show,
        vehicle_move_vault_zero,
        vehicle_move_vault_set,
    ],
    keybinds=[KEY_RESET, KEY_SHOW],
    options=BVM_OPTIONS,
)

if not SETTINGS_PATH.exists():
    try:
        _bvm_mod.enable()
    except Exception:
        pass
