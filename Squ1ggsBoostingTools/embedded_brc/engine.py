# Auto-synced from standalone mod — edit the sidecar and re-run _dev_sync_embedded_tuning.py.

"""
Resources & Cooldowns â€” **OakDamageState** / **OakDamageCauserData** tuning on your **local pawn**.

Data paths mirror Live Editor dumps (``OakCharacter`` â†’ ``DamageState`` / ``DamageCauserData`` with
``GbxAttributeFloat`` **Value** + **BaseValue** pairs where applicable).

**Outgoing** knobs live under ``DamageCauserData`` (damage dealt, radius, crit, healing dealt, ignore resist).
**Incoming** knobs live under ``DamageState`` (damage taken, radius taken, healing received, status-effect scalars).

Session-only: values may reset on travel / reconnect. Use **Sticky re-apply** if the game overwrites structs.

**Standalone:** drop ``bl4_resources_and_cooldowns`` next to ``mods_base`` / ``unrealsdk``. No Ultra Local Menu required.
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

EMBEDDED_IN_SQBT = True

__version__ = "1.0.0"
__author__ = "Squ1ggs"
MOD_NAME = "Resources & Cooldowns"
LOG_PREFIX = "[BRC]"
from mods_base import SETTINGS_DIR as _SETTINGS_DIR

SETTINGS_PATH = Path(_SETTINGS_DIR) / "bl4_resources_and_cooldowns.json"
SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

from .sqbt_coop import skip_own_blimgui_tab

# --- OakCharacter ReceiveTick (optional sticky re-apply) ---
_STICKY_HOOK_ID = "bl4_resources_and_cooldowns.sticky_tick"
_STICKY_CANDIDATES: tuple[str, ...] = (
    "/Script/Oak2.OakPlayerController:PlayerTick",
    "/Script/OakGame.OakPlayerController:PlayerTick",
    "/Script/Engine.PlayerController:PlayerTick",
    "/Script/Oak2.OakCharacter:ReceiveTick",
    "/Script/OakGame.OakCharacter:ReceiveTick",
    "/Script/Engine.Character:ReceiveTick",
)
_sticky_hook_path: str | None = None
_last_sticky_apply: float = 0.0
_last_applied_pawn_key: int = 0
_BLIMGUI_TAB = "Resources & Cooldowns"


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
    try:
        from blimgui import imgui
    except Exception:
        return
    imgui.text_wrapped("Repair-kit, recovery, Second Wind, overshield, and lifesteal tuning.")
    changed, enabled = imgui.checkbox("Enable resource tuning##brc_f1_master", bool(_master_opt.value))
    if changed:
        _master_opt.value = bool(enabled)
    changed, sticky = imgui.checkbox("Sticky re-apply##brc_f1_sticky", bool(_sticky_opt.value))
    if changed:
        _sticky_opt.value = bool(sticky)

    def _sliders(title: str, sliders: list[Any], specs: tuple[Any, ...]) -> None:
        if not _collapsing_header(imgui, title):
            return
        for opt, spec in zip(sliders, specs, strict=True):
            attr, lo, hi, _step, default, label = spec[:6]
            try:
                current = float(opt.value)
            except Exception:
                current = float(default)
            moved, value = imgui.slider_float(f"{label}##brc_f1_{attr}", current, float(lo), float(hi))
            if moved:
                current = float(value)
                opt.value = current
            typed, exact = imgui.input_float(
                f"Exact value##brc_f1_exact_{attr}",
                current,
                float(_step),
                float(_step) * 10.0,
                "%.3f",
            )
            if typed:
                opt.value = max(float(lo), min(float(hi), float(exact)))

    _sliders("Repair kits", _slider_repair, _REPAIR_KIT_SPECS)
    _sliders("Shields and second wind", _slider_recovery, _RECOVERY_SPECS)
    _sliders("Lifesteal recovery", _slider_adv, _ADV_DS_SPECS)
    _sliders("Ammo regen", _slider_ammo, _AMMO_REGEN_SPECS)
    if imgui.button("Apply now##brc_f1_apply"):
        _apply_damage_tuning(log_hits=True)
    imgui.same_line()
    if imgui.button("Reset##brc_f1_reset"):
        _on_reset_btn(None)


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
    global BRC_MASTER_ENABLED, BRC_STICKY_ENABLED, BRC_AMMO_STICKY_ENABLED
    BRC_MASTER_ENABLED = bool(_master_opt.value)
    BRC_STICKY_ENABLED = bool(_sticky_opt.value)
    BRC_AMMO_STICKY_ENABLED = bool(_ammo_sticky_opt.value)
    _sync_sticky_hook()
    if not EMBEDDED_IN_SQBT:
        _register_blimgui()


def _on_disable() -> None:
    _remove_sticky_hook()
    _unregister_blimgui()


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
    for a in ("Pawn", "Character", "ControlledPawn", "MyPawn"):
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


def _get_local_pc() -> Any | None:
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
                current = getattr(st, sub)
                new_value = int(round(value)) if isinstance(current, int) else float(value)
                setattr(st, sub, new_value)
                ok = True
            except Exception:
                continue
    return ok


def _resolve_path(root: Any, path: str) -> Any | None:
    obj = root
    for part in str(path).split("."):
        if obj is None:
            return None
        try:
            obj = getattr(obj, part)
        except Exception:
            return None
    return obj


def _write_pawn_pair(pawn: Any, path: str, value: float) -> bool:
    parts = str(path).rsplit(".", 1)
    if len(parts) != 2:
        return False
    return _write_gbx_pair(_resolve_path(pawn, parts[0]), parts[1], value)


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
    ("DamageTakenMultiplier", 0.0, 1_000_000.0, 0.05, 1.0, "Damage taken mult (lower = tankier)"),
    ("RadiusDamageTakenMultiplier", 0.0, 1_000_000.0, 0.05, 1.0, "Radius damage taken mult"),
    ("HealingReceivedMultiplier", 0.0, 1_000_000.0, 0.05, 1.0, "Healing received mult"),
    ("StatusEffectChanceModifierScalar", 0.0, 10_000.0, 0.05, 1.0, "Status effect chance scalar"),
    ("StatusEffectDPSModifierScalar", 0.0, 1_000_000.0, 0.05, 1.0, "Status effect DPS scalar"),
    ("StatusEffectChargeModifierScalar", 0.0, 10_000.0, 0.05, 1.0, "Status effect charge scalar"),
    ("DisableElementalResistance", 0.0, 1.0, 1.0, 0.0, "Disable elemental resist (0=off 1=on)"),
)

_DCD_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("DamageDealtMultiplier", 0.1, 1_000_000.0, 0.05, 1.0, "Damage dealt mult"),
    ("RadiusDamage_DamageMultiplier", 0.1, 1_000_000.0, 0.05, 1.0, "Radius damage â€” damage mult"),
    ("RadiusDamage_RadiusMultiplier", 0.1, 1_000.0, 0.05, 1.0, "Radius damage â€” radius mult"),
    ("HealingDealtMultiplier", 0.1, 1_000_000.0, 0.05, 1.0, "Healing dealt mult"),
    ("ShouldIgnoreEnemyElementalResistance", 0.0, 1.0, 1.0, 0.0, "Ignore enemy elemental resist (0/1)"),
    ("DefaultCriticalHitMultiplier", 0.1, 1_000_000.0, 0.05, 1.0, "Default crit damage mult"),
    ("DefaultCriticalHitChance", 0.0, 1.0, 0.01, 0.0, "Default crit chance add (0â€“1)"),
    ("EnemyReflectionChance", 0.0, 1.0, 0.01, 0.0, "Enemy reflection chance"),
)

_ADV_DS_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("lifestealpercent", 0.0, 10_000.0, 0.05, 1.0, "Lifesteal percent scalar"),
    ("lifestealrate", 0.0, 10_000.0, 0.05, 1.0, "Lifesteal rate scalar"),
    ("lifestealratecap", 0.0, 10_000.0, 0.05, 1.0, "Lifesteal rate cap scalar"),
)

_ELEMENTAL_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("ElementalDamageModifiers.FireModifier", 0.0, 1_000_000.0, 0.05, 1.0, "Fire damage multiplier"),
    ("ElementalDamageModifiers.ShockModifier", 0.0, 1_000_000.0, 0.05, 1.0, "Shock damage multiplier"),
    ("ElementalDamageModifiers.CorrosiveModifier", 0.0, 1_000_000.0, 0.05, 1.0, "Corrosive damage multiplier"),
    ("ElementalDamageModifiers.CryoModifier", 0.0, 1_000_000.0, 0.05, 1.0, "Cryo damage multiplier"),
    ("ElementalDamageModifiers.RadiationModifier", 0.0, 1_000_000.0, 0.05, 1.0, "Radiation damage multiplier"),
)

_REPAIR_KIT_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("HealthState.RepairKitMaxCharges", 0.0, 99.0, 1.0, 3.0, "Maximum repair kit charges"),
    ("HealthState.RepairKitCooldown", 0.0, 600.0, 0.1, 20.0, "Repair kit cooldown (seconds)"),
    ("HealthState.RepairKitDuration", 0.0, 120.0, 0.1, 8.0, "Repair kit healing duration"),
    (
        "HealthState.minhealthpercentmissingtoheal",
        0.0,
        1.0,
        0.01,
        0.0,
        "Minimum missing health required",
    ),
)

_RECOVERY_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("OvershieldManager.OvershieldDuration", 0.0, 600.0, 0.1, 8.0, "Overshield duration"),
    ("OvershieldManager.OvershieldBaseValue", 0.0, 1_000_000_000.0, 1.0, 0.0, "Bonus overshield amount"),
    ("DownState.SecondWindShield", 0.0, 10.0, 0.01, 1.0, "Shield restored after Second Wind"),
    ("DownState.SecondWindHealth", 0.0, 10.0, 0.01, 1.0, "Health restored after Second Wind"),
    ("DownState.RepeatDeathPenalty", 0.0, 10.0, 0.01, 1.0, "Repeated down penalty"),
    (
        "DownState.AutomaticSecondWindOnTimerExpired",
        0.0,
        1.0,
        1.0,
        0.0,
        "Automatic Second Wind when timer expires (0/1)",
    ),
    ("IntrinsicArmor", -500.0, 2000.0, 5.0, 0.0, "Intrinsic armor amount"),
)

# ``OakCharacter.ammoregenrate`` (GbxAttributeFloat) from OakPlayerController dumps
_AMMO_REGEN_SPECS: tuple[tuple[str, float, float, float, float, str], ...] = (
    ("ammoregenrate", 0.0, 1000.0, 0.5, 0.0, "Ammo regen rate (0 = off)"),
)

# Legacy intrinsic armor slider (not exposed in BRC_OPTIONS; kept for shared blimgui helpers)
_INTRINSIC_ARMOR_SPEC = ("IntrinsicArmor", -500.0, 2000.0, 5.0, 0.0, "Intrinsic armor")

BRC_MASTER_ENABLED: bool = True
BRC_STICKY_ENABLED: bool = False
BRC_AMMO_STICKY_ENABLED: bool = False


def _apply_damage_tuning(*, log_hits: bool = False) -> tuple[int, int]:
    """Returns (writes_ok, writes_fail)."""
    if not BRC_MASTER_ENABLED:
        return 0, 0
    pawn = _get_local_pawn()
    if pawn is None:
        if log_hits:
            _warn("No local pawn â€” load in-world.")
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

    for opt in _slider_adv:
        field = opt._brc_field  # type: ignore[attr-defined]
        val = float(opt.value)
        bump(_write_gbx_pair(ds, field, val) if ds is not None else False)

    for opt in (*_slider_repair, *_slider_recovery):
        field = opt._brc_field  # type: ignore[attr-defined]
        if "." in str(field):
            bump(_write_pawn_pair(pawn, field, float(opt.value)))
        else:
            # Flat DamageState fields (e.g. IntrinsicArmor).
            bump(_write_gbx_pair(ds, str(field), float(opt.value)) if ds is not None else False)

    for opt in _slider_ammo:
        field = opt._brc_field  # type: ignore[attr-defined]
        bump(_write_gbx_pair(pawn, field, float(opt.value)))

    if log_hits and ok + fail > 0:
        _info(f"apply: ok={ok} miss={fail} pawn={getattr(pawn, 'Name', '?')}")
    return ok, fail


def _apply_ammo_only(*, log_hits: bool = False) -> tuple[int, int]:
    if not BRC_MASTER_ENABLED:
        return 0, 0
    pawn = _get_local_pawn()
    if pawn is None:
        return 0, 0
    ok = 0
    fail = 0
    for opt in _slider_ammo:
        field = opt._brc_field  # type: ignore[attr-defined]
        if _write_gbx_pair(pawn, field, float(opt.value)):
            ok += 1
        else:
            fail += 1
    if log_hits and ok + fail > 0:
        _info(f"ammo apply: ok={ok} miss={fail}")
    return ok, fail


def _sticky_tick(caller: Any, *args: Any, **kwargs: Any) -> None:
    global _last_sticky_apply, _last_applied_pawn_key
    if not BRC_MASTER_ENABLED:
        return
    if caller is None:
        return
    pawn = None
    if "playercontroller" in str(getattr(getattr(caller, "Class", None), "Name", "") or "").lower():
        if not _is_local_pc(caller):
            return
        pawn = _try_pawn(caller)
    elif _is_local_pawn(caller):
        pawn = caller
    if pawn is None:
        return
    try:
        pawn_key = int(getattr(pawn, "_get_address", lambda: 0)() or 0)
    except Exception:
        pawn_key = id(pawn)
    now = time.monotonic()
    new_pawn = pawn_key != _last_applied_pawn_key
    sticky_all = BRC_STICKY_ENABLED
    sticky_ammo = BRC_AMMO_STICKY_ENABLED and not sticky_all
    if not new_pawn and not sticky_all and not sticky_ammo:
        return
    if not new_pawn and sticky_all and now - _last_sticky_apply < 0.35:
        return
    if not new_pawn and sticky_ammo and now - _last_sticky_apply < 0.35:
        return
    _last_applied_pawn_key = pawn_key
    _last_sticky_apply = now
    if sticky_all or new_pawn:
        ok, miss = _apply_damage_tuning(log_hits=False)
        if new_pawn:
            _info(f"Applied saved tuning to new local pawn: writes_ok={ok} writes_miss={miss}")
    elif sticky_ammo:
        _apply_ammo_only(log_hits=False)


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
    if not BRC_MASTER_ENABLED:
        _remove_sticky_hook()
        return
    if not BRC_STICKY_ENABLED and not BRC_AMMO_STICKY_ENABLED:
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
    _warn("Could not register the local-pawn lifecycle hook.")


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
            description="Applies this value to your current character. Reapply after travelling if the game resets it.",
        )
        opt._brc_field = field  # type: ignore[attr-defined]

        @opt.set_on_change()
        def _on(_: Any, value: float, _opt: SliderOption = opt) -> None:
            _apply_damage_tuning(log_hits=False)

        out.append(opt)
    return out


_slider_ds = _build_slider_group(_DS_SPECS, "brc_ds")
_slider_dcd = _build_slider_group(_DCD_SPECS, "brc_dcd")
_slider_adv = _build_slider_group(_ADV_DS_SPECS, "brc_adv")
_slider_elemental = _build_slider_group(_ELEMENTAL_SPECS, "brc_elemental")
_slider_repair = _build_slider_group(_REPAIR_KIT_SPECS, "brc_repair")
_slider_recovery = _build_slider_group(_RECOVERY_SPECS, "brc_recovery")
_slider_ammo = _build_slider_group(_AMMO_REGEN_SPECS, "brc_ammo")

_slider_intrinsic = SliderOption(
    "brc_intrinsic_armor",
    0.0,
    -500.0,
    2000.0,
    step=5.0,
    is_integer=False,
    display_name=_INTRINSIC_ARMOR_SPEC[5],
    description="Adds or removes intrinsic armor from your current character.",
)


@_slider_intrinsic.set_on_change()
def _on_intrinsic(_: Any, _v: float) -> None:
    _apply_damage_tuning(log_hits=False)


_master_opt = BoolOption(
    "brc_master_enable",
    True,
    display_name="Enable damage tuning",
    description="When off, sliders are ignored and sticky hook is removed.",
)


@_master_opt.set_on_change()
def _on_master(_: Any, value: bool) -> None:
    global BRC_MASTER_ENABLED
    BRC_MASTER_ENABLED = bool(value)
    if not BRC_MASTER_ENABLED:
        _remove_sticky_hook()
    else:
        _sync_sticky_hook()
        _apply_damage_tuning(log_hits=True)


_sticky_opt = BoolOption(
    "brc_sticky_reapply",
    False,
    display_name="Sticky re-apply (~0.35s)",
    description="Regularly reapplies your chosen values if the game resets them.",
)


@_sticky_opt.set_on_change()
def _on_sticky(_: Any, value: bool) -> None:
    global BRC_STICKY_ENABLED
    BRC_STICKY_ENABLED = bool(value)
    _sync_sticky_hook()


_ammo_sticky_opt = BoolOption(
    "brc_ammo_sticky_reapply",
    False,
    display_name="Sticky re-apply ammo regen only (~0.35s)",
    description="Keeps ammoregenrate applied even when full sticky is off.",
)


@_ammo_sticky_opt.set_on_change()
def _on_ammo_sticky(_: Any, value: bool) -> None:
    global BRC_AMMO_STICKY_ENABLED
    BRC_AMMO_STICKY_ENABLED = bool(value)
    _sync_sticky_hook()


_apply_btn = ButtonOption(
    "brc_apply_btn",
    display_name="Apply now",
    description="Force one apply pass (same as brc_apply).",
)


@_apply_btn
def _on_apply_btn(_: Any) -> None:
    ok, miss = _apply_damage_tuning(log_hits=True)
    _info(f"Manual apply: writes_ok={ok} writes_miss={miss}")


_reset_btn = ButtonOption(
    "brc_reset_btn",
    display_name="Reset sliders to defaults",
    description="Restores slider defaults then applies once.",
)


@_reset_btn
def _on_reset_btn(_: Any) -> None:
    for opt, spec in zip(_slider_adv, _ADV_DS_SPECS, strict=True):
        opt.value = float(spec[4])
    for opt, spec in zip(_slider_repair, _REPAIR_KIT_SPECS, strict=True):
        opt.value = float(spec[4])
    for opt, spec in zip(_slider_recovery, _RECOVERY_SPECS, strict=True):
        opt.value = float(spec[4])
    for opt, spec in zip(_slider_ammo, _AMMO_REGEN_SPECS, strict=True):
        opt.value = float(spec[4])
    _apply_damage_tuning(log_hits=True)


def brc_probe_impl() -> None:
    pawn = _get_local_pawn()
    if pawn is None:
        _warn("brc_probe: no pawn.")
        return
    cls = getattr(getattr(pawn, "Class", None), "Name", type(pawn))
    _info(f"brc_probe: pawn={cls} Name={getattr(pawn, 'Name', '?')}")
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
    _info(f"  ammoregenrate={'yes' if hasattr(pawn, 'ammoregenrate') else 'no'}")


@command("brc_help", description="List Resources & Cooldowns console commands.")
def brc_help(_args: argparse.Namespace) -> None:
    for ln in (
        "Resources & Cooldowns â€” local pawn ``DamageState`` / ``DamageCauserData`` (see Mods UI).",
        "  brc_apply        â€” force apply current sliders",
        "  brc_reset        â€” reset sliders to defaults + apply",
        "  brc_status       â€” master / sticky / pawn",
        "  brc_probe        â€” log which struct fields exist",
        "  brc_help",
    ):
        _info(ln)


@command("brc_apply", description="Apply current resource and recovery sliders to the local pawn.")
def brc_apply(_args: argparse.Namespace) -> None:
    ok, miss = _apply_damage_tuning(log_hits=True)
    _info(f"brc_apply: writes_ok={ok} writes_miss={miss}")


@command("brc_reset", description="Reset all sliders to defaults and apply.")
def brc_reset(_args: argparse.Namespace) -> None:
    _on_reset_btn(None)


@command("brc_status", description="Log master toggle, sticky hook, pawn resolution.")
def brc_status(_args: argparse.Namespace) -> None:
    pw = _get_local_pawn()
    _info(
        f"master={BRC_MASTER_ENABLED} sticky={BRC_STICKY_ENABLED} hook={_sticky_hook_path or 'none'} "
        f"pawn={'set' if pw is not None else 'none'}",
    )


@command("brc_probe", description="Log repair, recovery, and DamageState field presence on the local pawn.")
def brc_probe(_args: argparse.Namespace) -> None:
    brc_probe_impl()


def _kb_brc_apply() -> None:
    brc_apply(argparse.Namespace())


KEY_APPLY = keybind(
    "brc_apply_key",
    key="Ctrl+Shift+F10",
    callback=_kb_brc_apply,
    display_name="Apply resource tuning",
    description="Apply resource and recovery tuning (runs brc_apply).",
)


def _toggle_blimgui_tab() -> None:
    try:
        import blimgui
        blimgui.toggle_registered_tab(_BLIMGUI_TAB)
    except Exception as exc:
        _info(str(exc))


KEY_OPEN_MENU = keybind(
    "brc_open_menu",
    key="Ctrl+Shift+F12",
    callback=_toggle_blimgui_tab,
    display_name="Open Resources & Cooldowns tab",
    description="Toggles BL4 Mod Menu on Resources & Cooldowns.",
)


BRC_OPTIONS: list[GroupedOption | BoolOption | ButtonOption | SliderOption] = [
    _master_opt,
    _sticky_opt,
    _ammo_sticky_opt,
    GroupedOption(
        "brc_group_repair",
        display_name="Repair kits",
        description="Repair-kit charges, cooldown, duration, and minimum missing health.",
        children=_slider_repair,
    ),
    GroupedOption(
        "brc_group_recovery",
        display_name="Shields and Second Wind",
        description="Overshields, Second Wind recovery, repeated downs, and automatic recovery.",
        children=_slider_recovery,
    ),
    GroupedOption(
        "brc_group_advanced",
        display_name="Lifesteal recovery",
        description="Lifesteal percent, rate, and rate cap.",
        children=_slider_adv,
    ),
    GroupedOption(
        "brc_group_ammo",
        display_name="Ammo regen",
        description="``OakCharacter.ammoregenrate`` (GbxAttributeFloat) from OakPlayerController dumps.",
        children=_slider_ammo,
    ),
    GroupedOption(
        "brc_group_actions",
        display_name="Actions",
        description="Apply or reset slider values.",
        children=[_apply_btn, _reset_btn],
    ),
]


_brc_mod = None

if not EMBEDDED_IN_SQBT:
    _brc_mod = build_mod(
        name=MOD_NAME,
        author=__author__,
        description="Standalone repair-kit, overshield, Second Wind, recovery, lifesteal, and ammo regen tuning.",
        version=__version__,
        supported_games=Game.BL4,
        coop_support=CoopSupport.ClientSide,
        settings_file=SETTINGS_PATH,
        commands=[brc_help, brc_apply, brc_reset, brc_status, brc_probe],
        keybinds=[KEY_APPLY, KEY_OPEN_MENU],
        options=BRC_OPTIONS,
        on_enable=_on_enable,
        on_disable=_on_disable,
    )

# Keep runtime flags aligned with persisted option values (callbacks do not run on load).
try:
    BRC_MASTER_ENABLED = bool(_master_opt.value)
    BRC_STICKY_ENABLED = bool(_sticky_opt.value)
    BRC_AMMO_STICKY_ENABLED = bool(_ammo_sticky_opt.value)
except Exception:
    pass
if not EMBEDDED_IN_SQBT:
    _sync_sticky_hook()

    if not SETTINGS_PATH.exists():
        try:
            _brc_mod.enable()
        except Exception:
            pass

