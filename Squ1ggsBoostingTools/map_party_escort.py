"""Guest map assist — host guides guests through a short hop ring so their map fills in.

SQBT-native: Boost-target-first, one guest at a time, ring anchored on the host
at start, each guest returns to their saved pose when done. Not a fixed world hop
file — ring is computed live from where you stand.
"""
from __future__ import annotations

import math
import time
from typing import Any

import unrealsdk
from mods_base import get_pc
from unrealsdk import logging

_PREFIX = "[Squ1ggs Boosting Tools | GuestMapAssist]"
_HOP_COUNT = 6
_RADIUS = 12000.0
_DWELL_S = 0.65
_RETURN_DWELL = 0.35

_active = False
_message = "Idle."
_hops: list[tuple[float, float, float]] = []
_hop_index = 0
_next_at = 0.0
_guests: list[dict[str, Any]] = []
_guest_index = 0
_phase = "idle"


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
    except Exception:
        pass


def status() -> dict[str, Any]:
    guest = _guests[_guest_index] if _guest_index < len(_guests) else None
    name = str(guest.get("name") or "") if guest else ""
    return {
        "active": bool(_active),
        "phase": _phase,
        "guest_index": _guest_index + 1 if _guests else 0,
        "guest_total": len(_guests),
        "guest_name": name,
        "hop": _hop_index + 1 if _hops else 0,
        "hop_total": len(_hops),
        "message": _message,
    }


def _make_vector(x: float, y: float, z: float) -> Any:
    try:
        return unrealsdk.make_struct("Vector", X=float(x), Y=float(y), Z=float(z))
    except Exception:
        return None


def _make_rotator(yaw: float = 0.0) -> Any:
    try:
        return unrealsdk.make_struct("Rotator", Pitch=0, Yaw=float(yaw), Roll=0)
    except Exception:
        return None


def _teleport_pawn_xyz(pawn: Any, x: float, y: float, z: float, *, yaw: float | None = None) -> bool:
    if pawn is None:
        return False
    loc = _make_vector(x, y, z)
    rot = _make_rotator(yaw if yaw is not None else 0.0)
    if loc is None or rot is None:
        return False
    fn = getattr(pawn, "K2_TeleportTo", None)
    if callable(fn):
        try:
            result = fn(loc, rot)
            return True if result is None else bool(result)
        except Exception:
            pass
    fn = getattr(pawn, "K2_SetActorLocation", None)
    if callable(fn):
        try:
            fn(loc, False, None, True)
            return True
        except Exception:
            pass
    return False


def _pawn_pose(pawn: Any) -> tuple[float, float, float, float] | None:
    if pawn is None:
        return None
    try:
        loc = pawn.K2_GetActorLocation()
        yaw = float(pawn.K2_GetActorRotation().Yaw)
        return float(loc.X), float(loc.Y), float(loc.Z), yaw
    except Exception:
        return None


def _ring_points(cx: float, cy: float, cz: float, *, hops: int, radius: float) -> list[tuple[float, float, float]]:
    n = max(4, min(int(hops), 12))
    r = max(3000.0, min(float(radius), 35000.0))
    pts: list[tuple[float, float, float]] = []
    for i in range(n):
        ang = (2.0 * math.pi * i) / n
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r, cz))
    return pts


def _local_slot() -> int | None:
    try:
        from . import mobility_runtime

        return mobility_runtime.local_party_index()
    except Exception:
        return None


def _guest_targets(*, player_index: int | None, all_guests: bool) -> list[dict[str, Any]]:
    from . import mobility_runtime

    local = _local_slot()
    if local is None:
        local = 0
    out: list[dict[str, Any]] = []
    for slot, name, _pc, pawn, _move in mobility_runtime.live_party_contexts():
        if pawn is None:
            continue
        if int(slot) == int(local):
            continue
        if not all_guests and player_index is not None and int(slot) != int(player_index):
            continue
        home = _pawn_pose(pawn)
        if home is None:
            continue
        out.append(
            {
                "slot": int(slot),
                "name": str(name or f"P{int(slot) + 1}"),
                "pawn": pawn,
                "home": home,
            }
        )
    return out


def cancel() -> str:
    global _active, _message, _hops, _hop_index, _guests, _guest_index, _phase
    if not _active and not _guests:
        return "Guest map assist was not running."
    restored = 0
    for row in _guests:
        pawn = row.get("pawn")
        home = row.get("home")
        if pawn is None or not home:
            continue
        hx, hy, hz, hyaw = home
        if _teleport_pawn_xyz(pawn, hx, hy, hz, yaw=hyaw):
            restored += 1
    _active = False
    _hops = []
    _hop_index = 0
    _guests = []
    _guest_index = 0
    _phase = "idle"
    _message = f"Guest map assist stopped — sent {restored} guest(s) home."
    _log(_message)
    return _message


def start(
    *,
    player_index: int | None = None,
    all_guests: bool = False,
    hops: int = _HOP_COUNT,
    radius: float = _RADIUS,
) -> str:
    """Arm escort. Default = Boost target only (one remote guest)."""
    global _active, _message, _hops, _hop_index, _next_at, _guests, _guest_index, _phase
    if _active:
        return "Guest map assist already running — stop it first."
    try:
        from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate

        world, _gs = _gbc_session_world_and_gamestate()
        if not _gbc_is_listen_host_world(world):
            return "Guest map assist needs the listen host."
    except Exception:
        pass
    try:
        from .session_guards import session_safe

        if not session_safe():
            return "Guest map assist: wait until you are in-world."
    except Exception:
        pass
    pc = get_pc()
    host_pawn = None
    if pc is not None:
        for attr in ("OakCharacter", "Pawn", "AcknowledgedPawn"):
            try:
                host_pawn = getattr(pc, attr, None)
            except Exception:
                host_pawn = None
            if host_pawn is not None:
                break
    host_pose = _pawn_pose(host_pawn)
    if host_pose is None:
        return "Guest map assist: host pawn not ready."
    cx, cy, cz, _ = host_pose
    idx = int(player_index) if player_index is not None else None
    if all_guests:
        guests = _guest_targets(player_index=None, all_guests=True)
    else:
        if idx is None:
            try:
                from .backend_actions import get_target_player_index

                idx = int(get_target_player_index())
            except Exception:
                idx = 0
        if int(idx) < 0:
            return "Pick one Boost target (not All players) for assist - or use All guests."
        guests = _guest_targets(player_index=int(idx), all_guests=False)
    if not guests:
        return "No remote guest with a live pawn to escort."
    _hops = _ring_points(cx, cy, cz, hops=hops, radius=radius)
    _guests = guests
    _guest_index = 0
    _hop_index = 0
    _phase = "hopping"
    _active = True
    _next_at = time.monotonic()
    who = guests[0]["name"] if len(guests) == 1 else f"{len(guests)} guests"
    _message = (
        f"Guest map assist: {who} · {len(_hops)} hops @ {float(radius):.0f}cm "
        f"(ring on host)."
    )
    _log(_message)
    return _message


def _advance_guest() -> None:
    global _guest_index, _hop_index, _phase, _active, _message, _next_at, _guests
    _guest_index += 1
    _hop_index = 0
    if _guest_index >= len(_guests):
        _active = False
        _phase = "idle"
        _guests = []
        _message = "Guest map assist complete — all guests returned home."
        _log(_message)
        return
    _phase = "hopping"
    _next_at = time.monotonic() + _RETURN_DWELL
    name = str(_guests[_guest_index].get("name") or "")
    _message = f"Guest map assist: next guest {name} ({_guest_index + 1}/{len(_guests)})."


def runtime_tick(*_args: Any, **_kwargs: Any) -> None:
    global _hop_index, _phase, _message, _next_at, _active
    if not _active or not _hops or not _guests:
        return
    try:
        from .session_guards import session_safe

        if not session_safe():
            return
    except Exception:
        pass
    now = time.monotonic()
    if now < float(_next_at):
        return
    guest = _guests[_guest_index]
    pawn = guest.get("pawn")
    home = guest.get("home")
    name = str(guest.get("name") or "guest")
    if pawn is None or home is None:
        _advance_guest()
        return
    if _phase == "return_home":
        hx, hy, hz, hyaw = home
        _teleport_pawn_xyz(pawn, hx, hy, hz, yaw=hyaw)
        _message = f"Guest map assist: returned {name} home."
        _advance_guest()
        return
    if _hop_index >= len(_hops):
        _phase = "return_home"
        _next_at = now + _RETURN_DWELL
        return
    x, y, z = _hops[_hop_index]
    _teleport_pawn_xyz(pawn, x, y, z)
    _message = f"Guest map assist: {name} hop {_hop_index + 1}/{len(_hops)}."
    _hop_index += 1
    _next_at = now + float(_DWELL_S)
