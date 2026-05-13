"""
BL4 Damage & More — **OakDamageState** / **OakDamageCauserData** tuning on your **local pawn**.

Data paths mirror Live Editor dumps (``OakCharacter`` → ``DamageState`` / ``DamageCauserData`` with
``GbxAttributeFloat`` **Value** + **BaseValue** pairs where applicable).

**Outgoing** knobs live under ``DamageCauserData`` (damage dealt, radius, crit, healing dealt, ignore resist).
**Incoming** knobs live under ``DamageState`` (damage taken, radius taken, healing received, status-effect scalars).

Session-only: values may reset on travel / reconnect. Use **Sticky re-apply** if the game overwrites structs.

**Standalone:** drop ``bl4_damage_and_more`` next to ``mods_base`` / ``unrealsdk``. No Ultra Local Menu required.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import unrealsdk
from mods_base import BoolOption, ButtonOption, Game, GroupedOption, SliderOption, build_mod, command, keybind
from mods_base import CoopSupport
from unrealsdk import hooks, logging

__version__ = "1.0.0"
__author__ = "sdk_mods"
MOD_NAME = "BL4 Damage & More"
LOG_PREFIX = "[BDAM]"
SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings" / "bl4_damage_and_more.json"
SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

# --- OakCharacter ReceiveTick (optional sticky re-apply) ---
_STICKY_HOOK_ID = "bl4_damage_and_more.sticky_tick"
_STICKY_CANDIDATES: tuple[str, ...] = (
    "/Script/Oak2.OakCharacter:ReceiveTick",
    "/Script/OakGame.OakCharacter:ReceiveTick",
    "/Script/Engine.Character:ReceiveTick",
)
_sticky_hook_path: str | None = None
_last_sticky_apply: float = 0.0


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


def _get_local_pawn() -> Any | None:
    pc = _get_local_pc()
    return _try_pawn(pc) if pc is not None else None


def _is_local_pawn(pawn: Any) -> bool:
    if pawn is None:
        return False
    pc = _get_local_pc()
    if pc is None:
        return False
    try:
        if _try_pawn(pc) is pawn:
            return True
    except Exception:
        pass
    return False


def _damage_state(pawn: Any) -> Any | None:
    if pawn is None:
        return None
    for attr in ("DamageState", "damageState"):
        try:
            ds = getattr(pawn, attr, None)
            if ds is not None:
                return ds
        except Exception:
            continue
    return None


def _damage_causer_data(pawn: Any) -> Any | None:
    if pawn is None:
        return None
    for attr in ("DamageCauserData", "damageCauserData"):
        try:
            d = getattr(pawn, attr, None)
            if d is not None:
                return d
        except Exception:
            continue
    return None


def _write_gbx_pair(container: Any, field: str, value: float) -> bool:
    """``GbxAttributeFloat`` / similar: set **Value** and **BaseValue** when present."""
    if container is None:
        return False
    try:
        st = getattr(container, field, None)
    except Exception:
        return False
    if st is None:
        return False
    ok = False
    for sub in ("Value", "BaseValue"):
        if hasattr(st, sub):
            try:
                setattr(st, sub, float(value))
                ok = True
            except Exception:
                continue
    return ok


def _write_raw_float(container: Any, field: str, value: float) -> bool:
    if container is None:
        return False
    try:
        setattr(container, field, float(value))
        return True
    except Exception:
        return False


# (attr, vmin, vmax, step, default, title)
_DS_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("DamageTakenMultiplier", 0.0, 3.0, 0.05, 1.0, "Damage taken mult (lower = tankier)"),
    ("RadiusDamageTakenMultiplier", 0.0, 3.0, 0.05, 1.0, "Radius damage taken mult"),
    ("HealingReceivedMultiplier", 0.0, 3.0, 0.05, 1.0, "Healing received mult"),
    ("StatusEffectChanceModifierScalar", 0.0, 3.0, 0.05, 1.0, "Status effect chance scalar"),
    ("StatusEffectDPSModifierScalar", 0.0, 3.0, 0.05, 1.0, "Status effect DPS scalar"),
    ("StatusEffectChargeModifierScalar", 0.0, 3.0, 0.05, 1.0, "Status effect charge scalar"),
    ("DisableElementalResistance", 0.0, 1.0, 1.0, 0.0, "Disable elemental resist (0=off 1=on)"),
)

_DCD_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("DamageDealtMultiplier", 0.1, 5.0, 0.05, 1.0, "Damage dealt mult"),
    ("RadiusDamage_DamageMultiplier", 0.1, 5.0, 0.05, 1.0, "Radius damage — damage mult"),
    ("RadiusDamage_RadiusMultiplier", 0.1, 5.0, 0.05, 1.0, "Radius damage — radius mult"),
    ("HealingDealtMultiplier", 0.1, 5.0, 0.05, 1.0, "Healing dealt mult"),
    ("ShouldIgnoreEnemyElementalResistance", 0.0, 1.0, 1.0, 0.0, "Ignore enemy elemental resist (0/1)"),
    ("DefaultCriticalHitMultiplier", 0.1, 8.0, 0.05, 1.0, "Default crit damage mult"),
    ("DefaultCriticalHitChance", 0.0, 1.0, 0.01, 0.0, "Default crit chance add (0–1)"),
    ("EnemyReflectionChance", 0.0, 1.0, 0.01, 0.0, "Enemy reflection chance"),
)

_ADV_DS_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("AvertDeathChance", 0.0, 1.0, 0.01, 0.0, "Avert death chance"),
    ("SelfReflectionChance", 0.0, 1.0, 0.01, 0.0, "Self-reflection chance"),
    ("SelfReflectionDamageScale", 0.0, 3.0, 0.05, 1.0, "Self-reflection damage scale"),
    ("SelfReflectionDamageTakenScale", 0.0, 3.0, 0.05, 1.0, "Self-reflection damage taken scale"),
    ("SelfReflectionTowardsAttacker", 0.0, 1.0, 0.05, 1.0, "Self-reflection toward attacker"),
    ("lifestealpercent", 0.0, 3.0, 0.05, 1.0, "Lifesteal percent scalar"),
    ("lifestealrate", 0.0, 3.0, 0.05, 1.0, "Lifesteal rate scalar"),
    ("lifestealratecap", 0.0, 3.0, 0.05, 1.0, "Lifesteal rate cap scalar"),
)

# Raw scalar on OakDamageState (not always a Gbx pair in dumps)
_INTRINSIC_ARMOR_SPEC = ("IntrinsicArmor", -500.0, 2000.0, 5.0, 0.0, "Intrinsic armor (raw float on DamageState)")

BDAM_MASTER_ENABLED: bool = True
BDAM_STICKY_ENABLED: bool = False


def _apply_damage_tuning(*, log_hits: bool = False) -> tuple[int, int]:
    """Returns (writes_ok, writes_fail)."""
    if not BDAM_MASTER_ENABLED:
        return 0, 0
    pawn = _get_local_pawn()
    if pawn is None:
        if log_hits:
            _warn("No local pawn — load in-world.")
        return 0, 0
    ds = _damage_state(pawn)
    dcd = _damage_causer_data(pawn)
    ok = 0
    fail = 0

    def bump(good: bool) -> None:
        nonlocal ok, fail
        if good:
            ok += 1
        else:
            fail += 1

    for opt in _slider_ds:
        field = opt._bdam_field  # type: ignore[attr-defined]
        val = float(opt.value)
        bump(_write_gbx_pair(ds, field, val) if ds is not None else False)

    for opt in _slider_dcd:
        field = opt._bdam_field  # type: ignore[attr-defined]
        val = float(opt.value)
        bump(_write_gbx_pair(dcd, field, val) if dcd is not None else False)

    for opt in _slider_adv:
        field = opt._bdam_field  # type: ignore[attr-defined]
        val = float(opt.value)
        bump(_write_gbx_pair(ds, field, val) if ds is not None else False)

    bump(_write_raw_float(ds, _INTRINSIC_ARMOR_SPEC[0], float(_slider_intrinsic.value)) if ds is not None else False)

    if log_hits and ok + fail > 0:
        _info(f"apply: ok={ok} miss={fail} pawn={getattr(pawn, 'Name', '?')}")
    return ok, fail


def _sticky_tick(caller: Any, *args: Any, **kwargs: Any) -> None:
    global _last_sticky_apply
    if not BDAM_STICKY_ENABLED or not BDAM_MASTER_ENABLED:
        return
    if caller is None or not _is_local_pawn(caller):
        return
    now = time.monotonic()
    if now - _last_sticky_apply < 0.35:
        return
    _last_sticky_apply = now
    _apply_damage_tuning(log_hits=False)


def _remove_sticky_hook() -> None:
    global _sticky_hook_path
    p = _sticky_hook_path
    if p:
        try:
            if hooks.has_hook(p, hooks.Type.POST_UNCONDITIONAL, _STICKY_HOOK_ID):
                hooks.remove_hook(p, hooks.Type.POST_UNCONDITIONAL, _STICKY_HOOK_ID)
        except Exception:
            pass
    _sticky_hook_path = None


def _sync_sticky_hook() -> None:
    global _sticky_hook_path
    if not BDAM_STICKY_ENABLED or not BDAM_MASTER_ENABLED:
        _remove_sticky_hook()
        return
    if _sticky_hook_path and hooks.has_hook(_sticky_hook_path, hooks.Type.POST_UNCONDITIONAL, _STICKY_HOOK_ID):
        return
    _remove_sticky_hook()
    for cand in _STICKY_CANDIDATES:
        try:
            if hooks.add_hook(cand, hooks.Type.POST_UNCONDITIONAL, _STICKY_HOOK_ID, _sticky_tick):
                _sticky_hook_path = cand
                _info(f"Sticky re-apply hook: {cand}")
                return
        except Exception:
            continue
    _warn("Could not register sticky ReceiveTick hook.")


def _build_slider_group(
    specs: tuple[tuple[str, float, float, float, float, str], ...],
    prefix: str,
) -> list[SliderOption]:
    out: list[SliderOption] = []
    for field, vmin, vmax, step, default, title in specs:
        opt = SliderOption(
            f"{prefix}_{field}",
            float(default),
            float(vmin),
            float(vmax),
            step=float(step),
            is_integer=False,
            display_name=title,
            description=f"Writes ``{field}`` on the local pawn's struct when exposed.",
        )
        opt._bdam_field = field  # type: ignore[attr-defined]

        @opt
        def _on(_: Any, value: float, _opt: SliderOption = opt) -> None:
            _apply_damage_tuning(log_hits=False)

        out.append(opt)
    return out


_slider_ds = _build_slider_group(_DS_SPECS, "bdam_ds")
_slider_dcd = _build_slider_group(_DCD_SPECS, "bdam_dcd")
_slider_adv = _build_slider_group(_ADV_DS_SPECS, "bdam_adv")

_slider_intrinsic = SliderOption(
    "bdam_intrinsic_armor",
    0.0,
    -500.0,
    2000.0,
    step=5.0,
    is_integer=False,
    display_name=_INTRINSIC_ARMOR_SPEC[5],
    description="Raw ``IntrinsicArmor`` on ``DamageState`` (dump-backed).",
)


@_slider_intrinsic
def _on_intrinsic(_: Any, _v: float) -> None:
    _apply_damage_tuning(log_hits=False)


_master_opt = BoolOption(
    "bdam_master_enable",
    True,
    display_name="Enable damage tuning",
    description="When off, sliders are ignored and sticky hook is removed.",
)


@_master_opt
def _on_master(_: Any, value: bool) -> None:
    global BDAM_MASTER_ENABLED
    BDAM_MASTER_ENABLED = bool(value)
    if not BDAM_MASTER_ENABLED:
        _remove_sticky_hook()
    else:
        _sync_sticky_hook()
        _apply_damage_tuning(log_hits=True)


_sticky_opt = BoolOption(
    "bdam_sticky_reapply",
    False,
    display_name="Sticky re-apply (~0.35s)",
    description="Re-writes structs on ReceiveTick — use if the game resets your values.",
)


@_sticky_opt
def _on_sticky(_: Any, value: bool) -> None:
    global BDAM_STICKY_ENABLED
    BDAM_STICKY_ENABLED = bool(value)
    _sync_sticky_hook()


_apply_btn = ButtonOption(
    "bdam_apply_btn",
    display_name="Apply now",
    description="Force one apply pass (same as bdam_apply).",
)


@_apply_btn
def _on_apply_btn(_: Any) -> None:
    ok, miss = _apply_damage_tuning(log_hits=True)
    _info(f"Manual apply: writes_ok={ok} writes_miss={miss}")


_reset_btn = ButtonOption(
    "bdam_reset_btn",
    display_name="Reset sliders to defaults",
    description="Restores slider defaults then applies once.",
)


@_reset_btn
def _on_reset_btn(_: Any) -> None:
    for opt, spec in zip(_slider_ds, _DS_SPECS, strict=True):
        opt.value = float(spec[4])
    for opt, spec in zip(_slider_dcd, _DCD_SPECS, strict=True):
        opt.value = float(spec[4])
    for opt, spec in zip(_slider_adv, _ADV_DS_SPECS, strict=True):
        opt.value = float(spec[4])
    _slider_intrinsic.value = float(_INTRINSIC_ARMOR_SPEC[4])
    _apply_damage_tuning(log_hits=True)


_probe_btn = ButtonOption(
    "bdam_probe_btn",
    display_name="Probe (log struct fields)",
    description="Logs whether DamageState / DamageCauserData resolve on the local pawn.",
)


@_probe_btn
def _on_probe_btn(_: Any) -> None:
    bdam_probe_impl()


def bdam_probe_impl() -> None:
    pawn = _get_local_pawn()
    if pawn is None:
        _warn("bdam_probe: no pawn.")
        return
    cls = getattr(getattr(pawn, "Class", None), "Name", type(pawn))
    _info(f"bdam_probe: pawn={cls} Name={getattr(pawn, 'Name', '?')}")
    ds = _damage_state(pawn)
    dcd = _damage_causer_data(pawn)
    _info(f"  DamageState={'ok' if ds is not None else 'MISS'}")
    if ds is not None:
        for name, *_ in _DS_SPECS:
            has = hasattr(ds, name)
            _info(f"    .{name}: {'yes' if has else 'no'}")
        for name, *_ in _ADV_DS_SPECS:
            has = hasattr(ds, name)
            _info(f"    .{name} (adv): {'yes' if has else 'no'}")
        has_i = hasattr(ds, "IntrinsicArmor")
        _info(f"    .IntrinsicArmor: {'yes' if has_i else 'no'}")
    _info(f"  DamageCauserData={'ok' if dcd is not None else 'MISS'}")
    if dcd is not None:
        for name, *_ in _DCD_SPECS:
            _info(f"    .{name}: {'yes' if hasattr(dcd, name) else 'no'}")


@command("bdam_help", description="List BL4 Damage & More console commands.")
def bdam_help(_args: argparse.Namespace) -> None:
    for ln in (
        "BL4 Damage & More — local pawn ``DamageState`` / ``DamageCauserData`` (see Mods UI).",
        "  bdam_apply        — force apply current sliders",
        "  bdam_reset        — reset sliders to defaults + apply",
        "  bdam_status       — master / sticky / pawn",
        "  bdam_probe        — log which struct fields exist",
        "  bdam_help",
    ):
        _info(ln)


@command("bdam_apply", description="Apply current damage sliders to the local pawn.")
def bdam_apply(_args: argparse.Namespace) -> None:
    ok, miss = _apply_damage_tuning(log_hits=True)
    _info(f"bdam_apply: writes_ok={ok} writes_miss={miss}")


@command("bdam_reset", description="Reset all sliders to defaults and apply.")
def bdam_reset(_args: argparse.Namespace) -> None:
    _on_reset_btn(None)


@command("bdam_status", description="Log master toggle, sticky hook, pawn resolution.")
def bdam_status(_args: argparse.Namespace) -> None:
    pw = _get_local_pawn()
    _info(
        f"master={BDAM_MASTER_ENABLED} sticky={BDAM_STICKY_ENABLED} hook={_sticky_hook_path or 'none'} "
        f"pawn={'set' if pw is not None else 'none'}",
    )


@command("bdam_probe", description="Log DamageState / DamageCauserData field presence on local pawn.")
def bdam_probe(_args: argparse.Namespace) -> None:
    bdam_probe_impl()


def _kb_bdam_apply() -> None:
    bdam_apply(argparse.Namespace())


KEY_APPLY = keybind(
    "bdam_apply_key",
    key="Ctrl+Shift+F10",
    callback=_kb_bdam_apply,
    display_name="Apply damage tuning",
    description="Runs bdam_apply.",
)


BDAM_OPTIONS: list[GroupedOption | BoolOption | ButtonOption | SliderOption] = [
    _master_opt,
    _sticky_opt,
    GroupedOption(
        "bdam_group_incoming",
        display_name="Incoming (DamageState)",
        description="Damage you **take**, healing you **receive**, DoT/status scalars, elemental resist bypass.",
        children=_slider_ds + [_slider_intrinsic],
    ),
    GroupedOption(
        "bdam_group_outgoing",
        display_name="Outgoing (DamageCauserData)",
        description="Damage you **deal**, radius hits, crit defaults, healing **to** others.",
        children=_slider_dcd,
    ),
    GroupedOption(
        "bdam_group_advanced",
        display_name="Advanced (DamageState extras)",
        description="Self-reflection, avert-death, lifesteal scalars — may be build-sensitive.",
        children=_slider_adv,
    ),
    GroupedOption(
        "bdam_group_actions",
        display_name="Actions",
        description="Manual apply / reset / probe.",
        children=[_apply_btn, _reset_btn, _probe_btn],
    ),
]


_bdam_mod = build_mod(
    name=MOD_NAME,
    author=__author__,
    description="DamageState / DamageCauserData sliders (incoming, outgoing, status, advanced) + sticky re-apply.",
    version=__version__,
    supported_games=Game.BL4,
    coop_support=CoopSupport.ClientSide,
    settings_file=SETTINGS_PATH,
    commands=[bdam_help, bdam_apply, bdam_reset, bdam_status, bdam_probe],
    keybinds=[KEY_APPLY],
    options=BDAM_OPTIONS,
)

# Keep runtime flags aligned with persisted option values (callbacks do not run on load).
try:
    BDAM_MASTER_ENABLED = bool(_master_opt.value)
    BDAM_STICKY_ENABLED = bool(_sticky_opt.value)
except Exception:
    pass
_sync_sticky_hook()

if not SETTINGS_PATH.exists():
    try:
        _bdam_mod.enable()
    except Exception:
        pass
