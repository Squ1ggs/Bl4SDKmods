"""GameState.RarityState drop-weight controls for Squ1ggs Boosting Tools."""

from __future__ import annotations

import time
from typing import Callable

from mods_base import ENGINE

from .inventory_capacity import load_inventory_settings, save_extra_settings

RARITY_ROWS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("common", "Common", ("CommonModifier",)),
    ("uncommon", "Uncommon", ("UncommonModifier",)),
    ("rare", "Rare", ("RareModifier",)),
    ("epic", "Epic", ("VeryRareModifier", "EpicModifier")),
    ("legendary", "Legendary", ("LegendaryModifier",)),
    ("pearlescent", "Pearlescent", ("PearlModifier", "PearlescentModifier")),
)

_settings = load_inventory_settings()
_old_disabled = dict(_settings.get("rarity_disabled", {}) or {})
_saved = dict(_settings.get("rarity_weights", {}) or {})
_weights: dict[str, float] = {}
for _key, _label, _fields in RARITY_ROWS:
    if _key in _saved:
        try:
            _val = float(_saved.get(_key, 1.0))
        except Exception:
            _val = 1.0
    else:
        _val = 0.0 if bool(_old_disabled.get(_key, False)) else 1.0
    _weights[_key] = max(0.0, min(1.0, float(_val)))

auto_reapply: bool = bool(_settings.get("rarity_auto_reapply", True))
status_message: str = "Rarity drop weights idle. 100% is normal weight, 50% is half weight, 0% disables that rarity."
_cached_gamestate: object | None = None
_cached_state: object | None = None
_reapply_until: float = 0.0
_reapply_next_try: float = 0.0


def _save() -> None:
    try:
        save_extra_settings(
            rarity_weights={k: float(max(0.0, min(1.0, float(v)))) for k, v in dict(_weights).items()},
            rarity_auto_reapply=bool(auto_reapply),
        )
    except Exception:
        pass


def _any_custom() -> bool:
    try:
        return any(abs(float(v) - 1.0) > 0.0001 for v in dict(_weights).values())
    except Exception:
        return False


def _state_for_gamestate(gs: object | None) -> object | None:
    global _cached_gamestate, _cached_state
    if gs is None:
        _cached_gamestate = None
        _cached_state = None
        return None
    try:
        if _cached_gamestate is gs and _cached_state is not None:
            return _cached_state
    except Exception:
        pass
    state = None
    for attr in ("RarityState", "RarityModifier", "RarityModifiers", "GameRarityState"):
        try:
            candidate = getattr(gs, attr, None)
            if candidate is not None:
                state = candidate
                break
        except Exception:
            pass
    _cached_gamestate = gs
    _cached_state = state
    return state


def _current_world_gamestate() -> tuple[object | None, object | None]:
    try:
        viewport = getattr(ENGINE, "GameViewport", None)
        world = getattr(viewport, "World", None) if viewport is not None else None
        gs = getattr(world, "GameState", None) if world is not None else None
        if gs is not None and _state_for_gamestate(gs) is not None:
            return world, gs
    except Exception:
        pass
    return None, None


def _get_modifier(state: object | None, fields: tuple[str, ...]) -> object | None:
    if state is None:
        return None
    for field in fields:
        try:
            mod = getattr(state, field, None)
            if mod is not None:
                return mod
        except Exception:
            pass
    return None


def _set_float(mod: object | None, value: float) -> int:
    if mod is None:
        return 0
    writes = 0
    try:
        v = float(value)
    except Exception:
        v = 1.0
    for name in ("Value", "CurrentValue", "Current", "BaseValue", "InitialValue", "Base"):
        try:
            if hasattr(mod, name):
                setattr(mod, name, v)
                writes += 1
        except Exception:
            pass
    for name in ("SetValue", "SetBaseValue", "SetCurrentValue"):
        try:
            fn = getattr(mod, name, None)
            if callable(fn):
                fn(v)
                writes += 1
        except Exception:
            pass
    return writes


def apply_to_gamestate(gs: object | None, *, log_result: bool = False, log: Callable[[str], None] | None = None) -> str:
    global status_message
    state = _state_for_gamestate(gs)
    if state is None:
        status_message = "No GameState.RarityState found yet. Load into a world and try again."
        if log_result and log:
            log(status_message)
        return status_message
    writes = 0
    parts: list[str] = []
    for key, label, fields in RARITY_ROWS:
        try:
            target = max(0.0, min(1.0, float(_weights.get(key, 1.0))))
        except Exception:
            target = 1.0
        mod = _get_modifier(state, fields)
        w = _set_float(mod, target)
        writes += w
        if abs(target - 1.0) > 0.0001:
            parts.append(f"{label}={int(round(target * 100))}%")
    if writes:
        status_message = "Applied rarity weights: " + (", ".join(parts) if parts else "all 100%")
    else:
        status_message = "RarityState found but no modifier fields were writable."
    if log_result and log:
        log(status_message)
    return status_message


def apply_modifiers(*, log_result: bool = False, log: Callable[[str], None] | None = None) -> str:
    _world, gs = _current_world_gamestate()
    return apply_to_gamestate(gs, log_result=log_result, log=log)


def mark_reapply(reason: str = "world change", seconds: float = 12.0) -> None:
    global _reapply_until, _reapply_next_try
    if not auto_reapply or not _any_custom():
        return
    try:
        now = time.monotonic()
    except Exception:
        now = 0.0
    _reapply_until = max(float(_reapply_until or 0.0), now + max(1.0, float(seconds)))
    _reapply_next_try = 0.0


def background_tick() -> None:
    global _reapply_until, _reapply_next_try
    if not auto_reapply or not _any_custom():
        return
    try:
        now = time.monotonic()
    except Exception:
        return
    if now > float(_reapply_until or 0.0):
        return
    if now < float(_reapply_next_try or 0.0):
        return
    _reapply_next_try = now + 0.75
    _world, gs = _current_world_gamestate()
    if _state_for_gamestate(gs) is None:
        return
    apply_to_gamestate(gs, log_result=False)
    _reapply_until = 0.0
    _reapply_next_try = 0.0


def set_only(allowed_key: str, *, log: Callable[[str], None] | None = None) -> None:
    allowed_key = str(allowed_key or "").strip().lower()
    allowed_key = {
        "pearl": "pearlescent",
        "pearlescent": "pearlescent",
        "pearlescent": "pearlescent",
    }.get(allowed_key, allowed_key)
    for key, _label, _fields in RARITY_ROWS:
        _weights[key] = 1.0 if key == allowed_key else 0.0
    _save()
    apply_modifiers(log_result=True, log=log)


def weights_snapshot() -> dict[str, float]:
    """Percent values (0-100) for EXE/UI field sync."""
    out: dict[str, float] = {}
    for key, _label, _fields in RARITY_ROWS:
        try:
            out[key] = round(float(_weights.get(key, 1.0)) * 100.0, 1)
        except Exception:
            out[key] = 100.0
    return out


def reset_all(*, log: Callable[[str], None] | None = None) -> None:
    for key, _label, _fields in RARITY_ROWS:
        _weights[key] = 1.0
    _save()
    apply_modifiers(log_result=True, log=log)


def set_from_payload(payload: dict[str, object] | None = None) -> str:
    payload = payload or {}
    global auto_reapply
    for key, _label, _fields in RARITY_ROWS:
        raw = payload.get(key)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            val = float(raw)
        except Exception:
            continue
        if val > 1.0:
            val = val / 100.0
        _weights[key] = max(0.0, min(1.0, val))
    if "auto_reapply" in payload and str(payload.get("auto_reapply") or "").strip() != "":
        text = str(payload.get("auto_reapply")).strip().lower()
        auto_reapply = text in ("1", "true", "yes", "on")
    _save()
    return apply_modifiers(log_result=True)


def draw_card(
    *,
    button: Callable[..., None],
    checkbox: Callable[[str, bool], bool],
    input_float_slider: Callable[..., float],
    muted_wrapped: Callable[[str], None],
    begin_card: Callable[..., bool],
    end_card: Callable[[], None],
    log: Callable[[str], None],
) -> None:
    global auto_reapply
    opened = begin_card("Rarity Drop Weights", "purple", 325.0)
    if opened:
        muted_wrapped(
            "Sliders control GameState.RarityState drop-weight multipliers. "
            "100% is vanilla weight, 0% effectively removes that rarity from drops."
        )
        button("Apply", lambda: (_save(), apply_modifiers(log_result=True, log=log)), "purple", 80, 0)
        import blimgui as _blimgui

        imgui = _blimgui.imgui
        imgui.same_line()
        button("Reset All", lambda: reset_all(log=log), "gold", 100, 0)
        imgui.same_line()
        button("Only Legendary", lambda: set_only("legendary", log=log), "gold", 140, 0)
        imgui.same_line()
        button("Only Pearlescent", lambda: set_only("pearlescent", log=log), "pink", 160, 0)
        old_auto = bool(auto_reapply)
        auto_reapply = checkbox("Auto reapply on world change###sqbt_rarity_auto", bool(auto_reapply))
        if old_auto != bool(auto_reapply):
            _save()
        changed = False
        for key, label, _fields in RARITY_ROWS:
            try:
                current_pct = float(_weights.get(key, 1.0)) * 100.0
            except Exception:
                current_pct = 100.0
            new_pct = input_float_slider(f"{label} Weight###sqbt_rarity_{key}", current_pct, 0.0, 100.0, "%.0f%%")
            new_pct = max(0.0, min(100.0, float(new_pct)))
            new_val = new_pct / 100.0
            if abs(new_val - float(_weights.get(key, 1.0))) > 0.0001:
                _weights[key] = new_val
                changed = True
        if changed:
            _save()
            apply_modifiers(log_result=True, log=log)
        muted_wrapped(status_message)
    end_card()
