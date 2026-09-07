"""Live OakCharacter combat flags from player-controller dumps.

Shoot / zoom while sprinting are GbxAttributeInteger structs (Value + BaseValue).
Auto-revive restamps the misspelled ``bActorSucessfullyRevived`` bool plus
DownState.AutomaticSecondWindOnTimerExpired.
"""

from __future__ import annotations

import time
from typing import Any

from unrealsdk import logging

from .player_economy import _resolve_target_pc_for_index, _target_character_for_pc

_PREFIX = "[Squ1ggs's Boosting Tools | CharacterFlags]"
_INT_FLAGS: dict[str, str] = {
    "shoot_sprint": "bCanUseWeaponWhileSprinting",
    "zoom_sprint": "bCanZoomWhileSprinting",
    "zoom_injured": "bCanZoomWhileInjured",
}
_ALT_INT: dict[str, str] = {
    "bCanUseWeaponWhileSprinting": "ATTRIBUTE_can_use_weapon_while_sprinting",
    "bCanZoomWhileSprinting": "ATTRIBUTE_can_zoom_while_sprinting",
    "bCanZoomWhileInjured": "ATTRIBUTE_can_zoom_while_injured",
}
_REVIVE_BOOLS = ("bActorSucessfullyRevived", "bActorSuccessfullyRevived")
_sticky: dict[str, set[int]] = {key: set() for key in (*_INT_FLAGS, "auto_revive")}
_last_tick = 0.0
_TICK_GAP = 0.12


def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")


def is_on(flag: str, player_index: int) -> bool:
    bucket = _sticky.get(str(flag), set())
    idx = int(player_index)
    if idx < 0:
        return bool(bucket)
    return idx in bucket


def _write_int_attr(container: Any, name: str, value: int) -> bool:
    if container is None:
        return False
    attr = None
    try:
        attr = getattr(container, name, None)
    except Exception:
        attr = None
    wrote = False
    if attr is not None:
        for field in ("Value", "BaseValue", "CurrentValue"):
            try:
                setattr(attr, field, int(value))
                wrote = True
            except Exception:
                pass
        for method_name in ("SetValue", "SetBaseValue"):
            method = getattr(attr, method_name, None)
            if callable(method):
                try:
                    method(int(value))
                    wrote = True
                except Exception:
                    pass
        try:
            setattr(container, name, attr)
            wrote = True
        except Exception:
            pass
    if not wrote:
        try:
            setattr(container, name, int(value))
            wrote = True
        except Exception:
            pass
    alt = _ALT_INT.get(name)
    if alt:
        try:
            setattr(container, alt, int(value))
            wrote = True
        except Exception:
            pass
    return wrote


def _pawn_for_index(player_index: int) -> Any | None:
    pc, _err = _resolve_target_pc_for_index(int(player_index))
    if pc is None:
        return None
    return _target_character_for_pc(pc)


def _apply_int_flag(pawn: Any, flag: str, enabled: bool) -> bool:
    name = _INT_FLAGS.get(flag)
    if not name:
        return False
    return _write_int_attr(pawn, name, 1 if enabled else 0)


def _apply_auto_revive(pawn: Any, enabled: bool) -> bool:
    wrote = False
    want = bool(enabled)
    for name in _REVIVE_BOOLS:
        try:
            setattr(pawn, name, want)
            wrote = True
        except Exception:
            pass
    down = None
    try:
        down = getattr(pawn, "DownState", None)
    except Exception:
        down = None
    if _write_int_attr(down, "AutomaticSecondWindOnTimerExpired", 1 if want else 0):
        wrote = True
    return wrote


def set_flag(flag: str, indices: list[int], enabled: bool) -> str:
    key = str(flag or "").strip().lower()
    if key not in _sticky:
        return f"Unknown flag {flag!r}."
    want = bool(enabled)
    hits = 0
    for raw in indices:
        idx = int(raw)
        pawn = _pawn_for_index(idx)
        ok = False
        if pawn is not None:
            if key == "auto_revive":
                ok = _apply_auto_revive(pawn, want)
            else:
                ok = _apply_int_flag(pawn, key, want)
        if want and ok:
            _sticky[key].add(idx)
        else:
            _sticky[key].discard(idx)
        if ok:
            hits += 1
    label = {
        "shoot_sprint": "Shoot while sprinting",
        "zoom_sprint": "Zoom while sprinting",
        "zoom_injured": "Zoom while downed",
        "auto_revive": "Auto revive",
    }.get(key, key)
    state = "ON" if want else "OFF"
    msg = f"{label} {state} on {hits} player(s)."
    _log(msg)
    return msg


def set_intrinsic_element(
    indices: list[int],
    *,
    option: int,
    element: int,
    barrel_compat: bool | None = None,
) -> str:
    hits = 0
    for raw in indices:
        pawn = _pawn_for_index(int(raw))
        if pawn is None:
            continue
        state = None
        try:
            state = getattr(pawn, "IntrinsicElementState", None)
        except Exception:
            state = None
        if state is None:
            continue
        wrote = False
        try:
            setattr(state, "OverrideOption", int(option))
            wrote = True
        except Exception:
            pass
        try:
            setattr(state, "OverrideElement", int(element))
            wrote = True
        except Exception:
            pass
        if barrel_compat is not None:
            try:
                setattr(state, "bExplosiveBarrelBackwardsCompatibilitySet", bool(barrel_compat))
                wrote = True
            except Exception:
                pass
        try:
            setattr(pawn, "IntrinsicElementState", state)
            wrote = True
        except Exception:
            pass
        if wrote:
            hits += 1
    msg = (
        f"Intrinsic element option={int(option)} element={int(element)} "
        f"on {hits} player(s)."
    )
    _log(msg)
    return msg


def tick_character_flags(now: float | None = None) -> None:
    global _last_tick
    active = any(_sticky[key] for key in _sticky)
    if not active:
        return
    now = time.monotonic() if now is None else float(now)
    if now - _last_tick < _TICK_GAP:
        return
    _last_tick = now
    for key, indices in list(_sticky.items()):
        for idx in list(indices):
            pawn = _pawn_for_index(idx)
            if pawn is None:
                continue
            if key == "auto_revive":
                _apply_auto_revive(pawn, True)
            else:
                _apply_int_flag(pawn, key, True)
