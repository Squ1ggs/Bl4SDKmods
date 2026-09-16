"""Host map sweep — hop the local pawn through map POIs so FoD tiles paint.

Host-only. Does not teleport guests (co-op-safe). Default route uses packaged
fast-travel / level / zone coordinates on the current map (nearest-neighbor).
Legacy ``ring`` mode keeps the old circle around your feet.
"""
from __future__ import annotations

import math
import time
from typing import Any

from unrealsdk import logging

_PREFIX = "[Squ1ggs Boosting Tools | MapSweep]"
_HOP_COUNT = 0  # 0 = every scored FT/level/zone on the current map
_RADIUS = 18000.0
_DWELL_S = 0.55
_MAX_POI_HOPS = 250
_active = False
_hops: list[tuple[float, float, float]] = []
_hop_labels: list[str] = []
_index = 0
_home: tuple[float, float, float, float] | None = None
_next_at = 0.0
_message = "Idle."
_mode = "poi"

# Prefer real map landmarks over respawn spam / menu-only rows.
_POI_TYPEDEF_SCORE: dict[str, int] = {
    "fast_travel": 100,
    "level": 90,
    "zone": 80,
    "holding": 75,
    "leveltravel": 70,
    "stationtype_grapplerift": 60,
    "stationtype_bossreplayportal": 50,
}
_SKIP_TYPEDEF = frozenset(
    {
        "mainmenu",
        "destinationonly",
        "fast_travel_sendonly",
        "respawn",
        "mission_replay",
    }
)


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
    except Exception:
        pass


def _dist2(ax: float, ay: float, az: float, bx: float, by: float, bz: float) -> float:
    dx, dy, dz = ax - bx, ay - by, az - bz
    return dx * dx + dy * dy + dz * dz


def _typedef_score(typedef: str) -> int:
    key = str(typedef or "").strip().lower()
    if key in _SKIP_TYPEDEF:
        return -1
    if key in _POI_TYPEDEF_SCORE:
        return _POI_TYPEDEF_SCORE[key]
    if key.startswith("stationtype_"):
        return 40
    return 0


def _dedupe_stations(rows: list[dict[str, Any]], *, merge_cm: float = 2000.0) -> list[dict[str, Any]]:
    merge2 = merge_cm * merge_cm
    kept: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: -int(r.get("_score", 0))):
        x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
        dup = False
        for other in kept:
            if _dist2(x, y, z, other["x"], other["y"], other["z"]) <= merge2:
                dup = True
                break
        if not dup:
            kept.append(row)
    return kept


def _poi_candidates(*, map_name: str) -> list[dict[str, Any]]:
    from .travel import stations_on_current_map

    raw = stations_on_current_map(map_name=map_name)
    scored: list[dict[str, Any]] = []
    for row in raw:
        score = _typedef_score(str(row.get("typedef") or ""))
        if score < 1:
            continue
        scored.append({**row, "_score": score})
    return _dedupe_stations(scored)


def _greedy_poi_route(
    cx: float,
    cy: float,
    cz: float,
    candidates: list[dict[str, Any]],
    *,
    max_hops: int,
    max_range_cm: float,
) -> tuple[list[tuple[float, float, float]], list[str]]:
    remaining = list(candidates)
    pts: list[tuple[float, float, float]] = []
    labels: list[str] = []
    cur_x, cur_y, cur_z = cx, cy, cz
    range2 = (max_range_cm * max_range_cm) if max_range_cm > 0 else 0.0
    for _ in range(max(1, max_hops)):
        if not remaining:
            break
        best_i = -1
        best_d2 = float("inf")
        for i, row in enumerate(remaining):
            x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
            d2 = _dist2(cur_x, cur_y, cur_z, x, y, z)
            if range2 > 0 and _dist2(cx, cy, cz, x, y, z) > range2:
                continue
            if d2 < best_d2:
                best_d2 = d2
                best_i = i
        if best_i < 0:
            break
        row = remaining.pop(best_i)
        x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
        pts.append((x, y, z))
        label = str(row.get("display_name") or row.get("station") or "POI").strip()
        labels.append(label)
        cur_x, cur_y, cur_z = x, y, z
    return pts, labels


def _ring_points(cx: float, cy: float, cz: float, *, hops: int, radius: float) -> list[tuple[float, float, float]]:
    n = max(4, min(int(hops), 16))
    r = max(4000.0, min(float(radius), 40000.0))
    pts: list[tuple[float, float, float]] = []
    for i in range(n):
        ang = (2.0 * math.pi * i) / n
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r, cz))
    return pts


def status() -> dict[str, Any]:
    label = ""
    if _hop_labels and 0 <= _index < len(_hop_labels):
        label = _hop_labels[_index]
    elif _hop_labels and _index >= len(_hop_labels):
        label = _hop_labels[-1]
    return {
        "active": bool(_active),
        "index": int(_index),
        "total": len(_hops),
        "mode": _mode,
        "target": label,
        "message": _message,
    }


def cancel() -> str:
    global _active, _message, _hops, _hop_labels, _index, _home
    if not _active:
        return "Host map sweep was not running."
    _active = False
    _hops = []
    _hop_labels = []
    _index = 0
    home = _home
    _home = None
    _message = "Host map sweep cancelled."
    if home is not None:
        try:
            from .travel import teleport_local_pawn_to

            teleport_local_pawn_to(home[0], home[1], home[2], yaw=home[3])
        except Exception:
            pass
    return _message


def _arm_route(
    pts: list[tuple[float, float, float]],
    labels: list[str],
    *,
    home: tuple[float, float, float, float],
    mode: str,
    summary: str,
) -> str:
    global _active, _hops, _hop_labels, _index, _home, _next_at, _message, _mode
    if not pts:
        return "Host map sweep: no hop points."
    _home = home
    _hops = pts
    _hop_labels = labels if len(labels) == len(pts) else [f"Hop {i + 1}" for i in range(len(pts))]
    _index = 0
    _active = True
    _mode = mode
    _next_at = time.monotonic()
    _message = summary
    _log(_message)
    return _message


def start_ring(*, hops: int = _HOP_COUNT, radius: float = _RADIUS) -> str:
    """Arm a host-only circle around the current pawn (legacy)."""
    gate = _host_gate()
    if gate:
        return gate
    home, err = _pawn_home()
    if home is None:
        return err or "Host map sweep failed."
    cx, cy, cz, yaw = home
    pts = _ring_points(cx, cy, cz, hops=hops, radius=radius)
    labels = [f"Ring {i + 1}/{len(pts)}" for i in range(len(pts))]
    return _arm_route(
        pts,
        labels,
        home=home,
        mode="ring",
        summary=f"Host map sweep (ring): {len(pts)} hops @ {max(4000.0, min(float(radius), 40000.0)):.0f}cm.",
    )


def start(
    *,
    hops: int = _HOP_COUNT,
    radius: float = 0.0,
    mode: str = "poi",
) -> str:
    """Arm host map sweep — POI route by default."""
    gate = _host_gate()
    if gate:
        return gate
    home, err = _pawn_home()
    if home is None:
        return err or "Host map sweep failed."
    cx, cy, cz, yaw = home
    sweep_mode = str(mode or "poi").strip().lower()
    if sweep_mode in ("ring", "circle", "local"):
        use_radius = float(radius or _RADIUS)
        return start_ring(hops=hops, radius=use_radius)

    from .travel import current_world_map_name

    world = current_world_map_name()
    # hops<=0 → visit every scored POI on this map (capped for safety).
    want = int(hops) if hops is not None else int(_HOP_COUNT)
    if want <= 0:
        max_hops = int(_MAX_POI_HOPS)
    else:
        max_hops = max(4, min(want, int(_MAX_POI_HOPS)))
    max_range = max(0.0, float(radius or 0.0))
    candidates = _poi_candidates(map_name=world)
    pts, labels = _greedy_poi_route(cx, cy, cz, candidates, max_hops=max_hops, max_range_cm=max_range)
    if len(pts) >= 2:
        range_note = f", within {max_range:.0f}cm" if max_range > 0 else ", whole map"
        all_bit = " (all main stops)" if want <= 0 else ""
        return _arm_route(
            pts,
            labels,
            home=home,
            mode="poi",
            summary=(
                f"Host map sweep (POI): {len(pts)} stops on {world or 'this map'}{range_note}{all_bit} — "
                f"fast travel / zones, then home."
            ),
        )
    _log(f"POI route thin on {world!r} ({len(candidates)} candidates) — falling back to ring.")
    use_radius = float(radius or _RADIUS)
    if use_radius <= 0:
        use_radius = _RADIUS
    return start_ring(hops=hops, radius=use_radius)


def _host_gate() -> str | None:
    try:
        from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate

        world, _gs = _gbc_session_world_and_gamestate()
        if not _gbc_is_listen_host_world(world):
            return "Host map sweep needs the listen host."
    except Exception:
        pass
    try:
        from .session_guards import session_safe

        if not session_safe():
            return "Host map sweep: wait until you are in-world."
    except Exception:
        pass
    return None


def _pawn_home() -> tuple[tuple[float, float, float, float] | None, str | None]:
    from mods_base import get_pc

    pc = get_pc()
    pawn = None
    if pc is not None:
        for attr in ("OakCharacter", "Pawn", "AcknowledgedPawn"):
            try:
                pawn = getattr(pc, attr, None)
            except Exception:
                pawn = None
            if pawn is not None:
                break
    if pawn is None:
        return None, "Host map sweep: load into a character first."
    try:
        loc = pawn.K2_GetActorLocation()
        yaw = float(pawn.K2_GetActorRotation().Yaw)
        cx, cy, cz = float(loc.X), float(loc.Y), float(loc.Z)
        return (cx, cy, cz, yaw), None
    except Exception as exc:
        return None, f"Host map sweep failed: {exc!r}"


def runtime_tick(*_args: Any, **_kwargs: Any) -> None:
    global _index, _active, _message, _next_at, _home, _hops, _hop_labels
    if not _active or not _hops:
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
    from .travel import teleport_local_pawn_to

    if _index >= len(_hops):
        home = _home
        _active = False
        _hops = []
        _hop_labels = []
        _home = None
        if home is not None:
            try:
                teleport_local_pawn_to(home[0], home[1], home[2], yaw=home[3])
            except Exception:
                pass
        _message = "Host map sweep complete - returned home."
        _log(_message)
        return
    x, y, z = _hops[_index]
    label = _hop_labels[_index] if _index < len(_hop_labels) else ""
    try:
        teleport_local_pawn_to(x, y, z)
        where = f" ({label})" if label else ""
        _message = f"Host map sweep hop {_index + 1}/{len(_hops)}{where}."
    except Exception as exc:
        _message = f"Host map sweep hop failed: {exc}"
        _log(_message)
    _index += 1
    _next_at = now + float(_DWELL_S)
