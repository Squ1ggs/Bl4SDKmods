"""Session-only map fog overlay hide (visual). Does not unlock exploration or FT.

Dump: OakMapViewerFog has FogMesh (StaticMeshComponent) + FogRoot (SceneComponent),
bHidden on the actor, SetActorHiddenInGame, SetVisibility, SetHiddenInGame.
"""

from __future__ import annotations

import time
from typing import Any

import unrealsdk
from unrealsdk import logging

_PREFIX = "[Squ1ggs's Boosting Tools | MapFog]"
_sticky = False
_last_apply = 0.0
_last_count = 0
_burst_until = 0.0
_FOG_ATTRS = ("FogMesh", "FogRoot", "RootComponent")
_BURST_SEC = 4.0
_BURST_GAP = 0.04
_STEADY_GAP = 0.12


def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")


def is_hidden() -> bool:
    return bool(_sticky)


def _obj_name(obj: Any) -> str:
    for attr in ("Name", "name"):
        try:
            value = getattr(obj, attr, None)
        except Exception:
            value = None
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    try:
        return str(obj)
    except Exception:
        return ""


def _is_default(obj: Any) -> bool:
    name = _obj_name(obj)
    return name.startswith("Default__") or name.startswith("default__")


def _call_hide(obj: Any, hidden: bool) -> bool:
    if obj is None:
        return False
    ok = False
    vis = getattr(obj, "SetVisibility", None)
    if callable(vis):
        try:
            vis(not bool(hidden), True)
            ok = True
        except TypeError:
            try:
                vis(not bool(hidden))
                ok = True
            except Exception:
                pass
        except Exception:
            pass
    hide = getattr(obj, "SetHiddenInGame", None)
    if callable(hide):
        try:
            hide(bool(hidden), True)
            ok = True
        except TypeError:
            try:
                hide(bool(hidden))
                ok = True
            except Exception:
                pass
        except Exception:
            pass
    actor_hide = getattr(obj, "SetActorHiddenInGame", None)
    if callable(actor_hide):
        try:
            actor_hide(bool(hidden))
            ok = True
        except Exception:
            pass
    for name, value in (
        ("bHiddenInGame", bool(hidden)),
        ("bVisible", not bool(hidden)),
        ("bHidden", bool(hidden)),
    ):
        try:
            setattr(obj, name, value)
            ok = True
        except Exception:
            pass
    return ok


def _set_scale(comp: Any, scale: float) -> None:
    if comp is None:
        return
    fn = getattr(comp, "SetRelativeScale3D", None)
    if callable(fn):
        try:
            fn(unrealsdk.make_struct("Vector", X=float(scale), Y=float(scale), Z=float(scale)))
            return
        except Exception:
            pass
    try:
        vec = getattr(comp, "RelativeScale3D", None)
        if vec is None:
            return
        vec.X = float(scale)
        vec.Y = float(scale)
        vec.Z = float(scale)
        setattr(comp, "RelativeScale3D", vec)
    except Exception:
        pass


def _hide_tree(obj: Any, hidden: bool, seen: set[int], depth: int = 0) -> int:
    if obj is None or depth > 5:
        return 0
    key = id(obj)
    if key in seen:
        return 0
    seen.add(key)
    n = 1 if _call_hide(obj, hidden) else 0
    _set_scale(obj, 0.001 if hidden else 1.0)
    for attr in _FOG_ATTRS:
        try:
            child = getattr(obj, attr, None)
        except Exception:
            child = None
        n += _hide_tree(child, hidden, seen, depth + 1)
    try:
        children = getattr(obj, "AttachChildren", None)
    except Exception:
        children = None
    if children is not None:
        try:
            for child in list(children):
                n += _hide_tree(child, hidden, seen, depth + 1)
        except Exception:
            pass
    return n


def _apply(hidden: bool) -> int:
    n = 0
    seen: set[int] = set()
    try:
        objs = list(unrealsdk.find_all("OakMapViewerFog", False) or [])
    except Exception:
        objs = []
    for obj in objs:
        if obj is None or _is_default(obj):
            continue
        n += _hide_tree(obj, hidden, seen)
    return n


def start_hide() -> str:
    global _sticky, _last_apply, _last_count, _burst_until
    _sticky = True
    _last_apply = 0.0
    _burst_until = time.monotonic() + _BURST_SEC
    _last_count = _apply(True)
    _log(f"Map fog overlay hide ON (wrote={_last_count})")
    return (
        "Map fog overlay hidden this session. Open the map to see it. "
        "Fog comes back after reload. This does not unlock safehouses or mark the world visited."
    )


def stop_hide() -> str:
    global _sticky, _last_apply, _last_count, _burst_until
    _sticky = False
    _burst_until = 0.0
    _last_count = _apply(False)
    _last_apply = time.monotonic()
    _log(f"Map fog overlay hide OFF (wrote={_last_count})")
    return "Map fog overlay is back on."


def set_hidden(enabled: bool) -> str:
    return start_hide() if enabled else stop_hide()


def tick_fog_hide(now: float | None = None) -> None:
    """Re-hide while sticky — map UI recreates FogMesh when opened."""
    global _last_apply, _last_count
    if not _sticky:
        return
    now = time.monotonic() if now is None else float(now)
    gap = _BURST_GAP if now < _burst_until else _STEADY_GAP
    if now - _last_apply < gap:
        return
    _last_apply = now
    try:
        _last_count = _apply(True)
    except Exception:
        pass


def status() -> str:
    state = "ON" if _sticky else "OFF"
    return f"Map fog overlay hide {state}."
