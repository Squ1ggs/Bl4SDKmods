"""Gather and vacuum ground loot around party pawns.

Gather: ammo/cash piles snap to feet; gear lands on an expanding Archimedean coil.
Vacuum / pull: fast snap of nearby ground loot to feet (Attract yourself) — not
backpack inventorize, not mail. Scope = you, Boost target, or every party member.
"""
from __future__ import annotations

import math
from typing import Any

import unrealsdk
from mods_base import get_pc
from unrealsdk import logging

_PREFIX = "[Squ1ggs Boosting Tools | LootGather]"
_START_R = 220.0
_ITEM_SPACING = 150.0
_TURN_GROWTH = 220.0
_PICKUP_TAGS = ("Ammo", "Cash", "Eridium", "Health", "Shield", "Grenade")
_MAX_MOVE = 400


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
    except Exception:
        pass


def _live(obj: Any) -> bool:
    if obj is None:
        return False
    try:
        _ = obj.Name
        return True
    except Exception:
        return False


def _coil_xy(index: int) -> tuple[float, float]:
    growth = _TURN_GROWTH / (2.0 * math.pi)
    arc = max(0, int(index)) * _ITEM_SPACING
    radius = math.sqrt(_START_R ** 2 + 2.0 * growth * arc)
    angle = (radius - _START_R) / growth
    return math.cos(angle) * radius, math.sin(angle) * radius


def _iter_pickups() -> list[Any]:
    out: list[Any] = []
    for cls in ("InventoryPickup", "OakInventoryPickup", "OakPickup"):
        try:
            found = unrealsdk.find_all(cls, False) or []
        except Exception:
            continue
        for inv in found:
            if not _live(inv):
                continue
            try:
                if inv == inv.Class.ClassDefaultObject:
                    continue
            except Exception:
                pass
            out.append(inv)
    return out


def _pickup_xyz(inv: Any) -> tuple[float, float, float] | None:
    try:
        loc = inv.K2_GetActorLocation()
        return float(loc.X), float(loc.Y), float(loc.Z)
    except Exception:
        pass
    root = getattr(inv, "RootComponent", None) or getattr(inv, "RootPrimitiveComponent", None)
    if root is not None:
        try:
            loc = root.RelativeLocation
            return float(loc.X), float(loc.Y), float(loc.Z)
        except Exception:
            pass
    return None


def _within_radius(
    inv: Any,
    anchors: list[tuple[float, float, float]],
    radius_m: float,
) -> bool:
    if radius_m <= 0 or not anchors:
        return True
    xyz = _pickup_xyz(inv)
    if xyz is None:
        return False
    limit = float(radius_m) * 100.0
    limit_sq = limit * limit
    x, y, z = xyz
    for ax, ay, az in anchors:
        dx, dy, dz = x - ax, y - ay, z - az
        if dx * dx + dy * dy + dz * dz <= limit_sq:
            return True
    return False


def _is_material_pile(inv: Any) -> bool:
    try:
        body = str(getattr(inv, "BodyData", "") or "")
        if "Pickups" in body:
            return True
    except Exception:
        pass
    root = getattr(inv, "RootPrimitiveComponent", None) or getattr(inv, "RootComponent", None)
    if root is None:
        return False
    try:
        count = int(root.GetNumMaterials())
    except Exception:
        return False
    for index in range(min(count, 8)):
        try:
            material = root.GetMaterial(index)
        except Exception:
            material = None
        if not material:
            continue
        name = str(getattr(material, "Name", "") or "")
        if any(tag in name for tag in _PICKUP_TAGS):
            return True
    return False


def _make_vector(x: float, y: float, z: float) -> Any:
    try:
        return unrealsdk.make_struct("Vector", X=float(x), Y=float(y), Z=float(z))
    except Exception:
        return None


def _make_rotator() -> Any:
    try:
        return unrealsdk.make_struct("Rotator", Pitch=0, Yaw=0, Roll=0)
    except Exception:
        return None


def _teleport(inv: Any, x: float, y: float, z: float) -> bool:
    loc = _make_vector(x, y, z)
    rot = _make_rotator()
    if loc is None or rot is None:
        return False
    fn = getattr(inv, "K2_TeleportTo", None)
    if not callable(fn):
        return False
    try:
        result = fn(loc, rot)
        return True if result is None else bool(result)
    except Exception:
        return False


def _local_pawn() -> Any | None:
    try:
        pc = get_pc()
    except Exception:
        return None
    if pc is None:
        return None
    for attr in ("OakCharacter", "Pawn", "AcknowledgedPawn"):
        try:
            pawn = getattr(pc, attr, None)
        except Exception:
            pawn = None
        if _live(pawn):
            return pawn
    return None


def _anchor_from_pawn(pawn: Any) -> tuple[float, float, float, float] | None:
    if pawn is None:
        return None
    try:
        where = pawn.K2_GetActorLocation()
        yaw = math.radians(float(pawn.K2_GetActorRotation().Yaw))
        return float(where.X), float(where.Y), float(where.Z) - 36.0, yaw
    except Exception:
        return None


def _reel_at_anchor(
    anchor: tuple[float, float, float, float],
    pickups: list[Any],
    *,
    max_items: int,
) -> int:
    base_x, base_y, base_z, yaw = anchor
    forward_x, forward_y = math.cos(yaw), math.sin(yaw)
    right_x, right_y = -math.sin(yaw), math.cos(yaw)
    piles: list[Any] = []
    gear: list[Any] = []
    for inv in pickups:
        if _is_material_pile(inv):
            piles.append(inv)
        else:
            gear.append(inv)
    cap = max(1, min(int(max_items), _MAX_MOVE))
    moved = 0
    for inv in piles:
        if moved >= cap:
            break
        if _teleport(inv, base_x, base_y, base_z):
            moved += 1
    gear_i = 0
    for inv in gear:
        if moved >= cap:
            break
        ahead, side = _coil_xy(gear_i)
        x = base_x + forward_x * ahead + right_x * side
        y = base_y + forward_y * ahead + right_y * side
        if _teleport(inv, x, y, base_z):
            moved += 1
            gear_i += 1
    return moved


def _resolve_scope(scope: str, player_index: int | None) -> list[tuple[str, Any]]:
    """Return (label, pawn) anchors to reel toward."""
    key = str(scope or "me").strip().lower()
    if key in ("me", "local", "self", ""):
        pawn = _local_pawn()
        return [("you", pawn)] if pawn is not None else []
    if key in ("target", "selected", "boost"):
        from . import mobility_runtime

        idx = int(player_index) if player_index is not None else None
        if idx is None:
            try:
                from .backend_actions import get_target_player_index

                idx = int(get_target_player_index())
            except Exception:
                idx = 0
        if int(idx) < 0:
            return []
        for slot, name, _pc, pawn, _move in mobility_runtime.live_party_contexts():
            if int(slot) == int(idx) and pawn is not None:
                return [(str(name or f"P{int(slot) + 1}"), pawn)]
        return []
    if key in ("party", "all", "lobby"):
        from . import mobility_runtime

        out: list[tuple[str, Any]] = []
        for slot, name, _pc, pawn, _move in mobility_runtime.live_party_contexts():
            if pawn is None:
                continue
            out.append((str(name or f"P{int(slot) + 1}"), pawn))
        return out
    return _resolve_scope("me", player_index)


def reel_ground_loot(
    *,
    max_items: int = _MAX_MOVE,
    scope: str = "me",
    radius_m: float = 0.0,
    player_index: int | None = None,
) -> str:
    """Pull world loot into coil(s). Host / in-world."""
    try:
        from .session_guards import session_safe

        if not session_safe():
            return "Loot gather: wait until you are in-world (not menu / travel)."
    except Exception:
        pass
    anchors_pawns = _resolve_scope(scope, player_index)
    if not anchors_pawns:
        return "Loot gather: no live pawn for that scope (pick a Boost target?)."
    spatial_anchors: list[tuple[float, float, float]] = []
    reel_targets: list[tuple[str, tuple[float, float, float, float]]] = []
    for label, pawn in anchors_pawns:
        pose = _anchor_from_pawn(pawn)
        if pose is None:
            continue
        reel_targets.append((label, pose))
        spatial_anchors.append((pose[0], pose[1], pose[2]))
    if not reel_targets:
        return "Loot gather: could not read pawn position."
    all_pickups = _iter_pickups()
    if float(radius_m or 0) > 0:
        filtered = [inv for inv in all_pickups if _within_radius(inv, spatial_anchors, float(radius_m))]
    else:
        filtered = all_pickups
    if not filtered:
        rad_note = f" within {float(radius_m):g}m" if float(radius_m or 0) > 0 else ""
        return f"Loot gather: no ground loot{rad_note}."
    per_cap = max(1, min(int(max_items or _MAX_MOVE), _MAX_MOVE))
    if len(reel_targets) > 1:
        per_cap = max(1, min(per_cap // len(reel_targets), _MAX_MOVE))
    buckets: dict[str, list[Any]] = {label: [] for label, _ in reel_targets}
    limit_sq = (float(radius_m) * 100.0) ** 2 if float(radius_m or 0) > 0 else None
    for inv in filtered:
        xyz = _pickup_xyz(inv)
        if xyz is None:
            continue
        x, y, z = xyz
        best_label = ""
        best_d2 = None
        for label, pose in reel_targets:
            ax, ay, az = pose[0], pose[1], pose[2]
            dx, dy, dz = x - ax, y - ay, z - az
            d2 = dx * dx + dy * dy + dz * dz
            if limit_sq is not None and d2 > limit_sq:
                continue
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_label = label
        if best_label:
            buckets[best_label].append(inv)
    total = 0
    parts: list[str] = []
    for label, pose in reel_targets:
        moved = _reel_at_anchor(pose, buckets.get(label) or [], max_items=per_cap)
        total += moved
        if moved:
            parts.append(f"{label}={moved}")
    rad_bit = f", {float(radius_m):g}m bubble" if float(radius_m or 0) > 0 else ""
    scope_bit = str(scope or "me")
    msg = f"Loot gather ({scope_bit}): moved {total} pickup(s){rad_bit}"
    if parts:
        msg += f" ({', '.join(parts)})"
    msg += "."
    _log(msg)
    return msg


# --- Pull loot to feet (fast snap) ------------------------------------------

_VACUUM_MAX = 400
_vacuum_active = False
_vacuum_ok = 0
_vacuum_failed = 0
_vacuum_piled = 0
_vacuum_total = 0
_vacuum_message = "Idle."
# Kept for loot_shapes ServerUse PRE — vacuum no longer inventorizes via Use.
_vacuum_native_use = False


def vacuum_status() -> dict[str, Any]:
    return {
        "active": bool(_vacuum_active),
        "queued": 0,
        "index": int(_vacuum_ok + _vacuum_failed + _vacuum_piled),
        "progress_index": int(_vacuum_ok + _vacuum_failed + _vacuum_piled),
        "total": int(_vacuum_total),
        "progress_total": int(_vacuum_total),
        "ok": int(_vacuum_ok),
        "failed": int(_vacuum_failed),
        "piled": int(_vacuum_piled),
        "no_serial": 0,
        "give_fail": 0,
        "message": _vacuum_message,
    }


def cancel_vacuum() -> str:
    global _vacuum_active, _vacuum_message
    if not _vacuum_active:
        return "Loot pull was not running."
    _vacuum_active = False
    _vacuum_message = "Loot pull cancelled."
    _log(_vacuum_message)
    return _vacuum_message


def note_live_server_use(_args: Any, _func: Any) -> None:
    """No-op stub — vacuum no longer learns ServerUse (feet snap only)."""
    return None


def _snap_to_feet(
    anchor: tuple[float, float, float, float],
    pickups: list[Any],
    *,
    max_items: int,
) -> tuple[int, int]:
    """Teleport pickups to ground at feet (same Z as gather piles). Returns (ok, fail)."""
    base_x, base_y, base_z, _yaw = anchor
    cap = max(1, min(int(max_items), _VACUUM_MAX))
    ok = 0
    fail = 0
    for inv in pickups:
        if ok + fail >= cap:
            break
        if not _live(inv):
            fail += 1
            continue
        if _teleport(inv, base_x, base_y, base_z):
            ok += 1
        else:
            fail += 1
    return ok, fail


def start_vacuum(
    *,
    max_items: int = 200,
    scope: str = "me",
    radius_m: float = 40.0,
    player_index: int | None = None,
) -> str:
    """Fast snap nearby ground loot to feet. Host / in-world. Not backpack / not mail."""
    global _vacuum_active, _vacuum_ok, _vacuum_failed, _vacuum_piled
    global _vacuum_total, _vacuum_message
    try:
        from .session_guards import session_safe

        if not session_safe():
            return "Loot pull: wait until you are in-world (not menu / travel)."
    except Exception:
        pass
    try:
        from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate

        world, _ = _gbc_session_world_and_gamestate()
        if not _gbc_is_listen_host_world(world):
            return "Loot pull needs the listen host."
    except Exception:
        pass

    anchors_pawns = _resolve_scope(scope, player_index)
    if not anchors_pawns:
        return "Loot pull: no live pawn for that scope."
    spatial_anchors: list[tuple[float, float, float]] = []
    feet_targets: list[tuple[str, tuple[float, float, float, float]]] = []
    for label, pawn in anchors_pawns:
        pose = _anchor_from_pawn(pawn)
        if pose is None:
            continue
        feet_targets.append((label, pose))
        spatial_anchors.append((pose[0], pose[1], pose[2]))
    if not feet_targets:
        return "Loot pull: could not read pawn position."

    all_pickups = _iter_pickups()
    if float(radius_m or 0) > 0:
        filtered = [inv for inv in all_pickups if _within_radius(inv, spatial_anchors, float(radius_m))]
    else:
        filtered = all_pickups
    if not filtered:
        rad_note = f" within {float(radius_m):g}m" if float(radius_m or 0) > 0 else ""
        return f"Loot pull: no ground loot{rad_note}."

    per_cap = max(1, min(int(max_items or 200), _VACUUM_MAX))
    if len(feet_targets) > 1:
        per_cap = max(1, min(per_cap // len(feet_targets), _VACUUM_MAX))
    buckets: dict[str, list[Any]] = {label: [] for label, _ in feet_targets}
    limit_sq = (float(radius_m) * 100.0) ** 2 if float(radius_m or 0) > 0 else None
    for inv in filtered:
        xyz = _pickup_xyz(inv)
        if xyz is None:
            continue
        x, y, z = xyz
        best_label = ""
        best_d2 = None
        for label, pose in feet_targets:
            ax, ay, az = pose[0], pose[1], pose[2]
            dx, dy, dz = x - ax, y - ay, z - az
            d2 = dx * dx + dy * dy + dz * dz
            if limit_sq is not None and d2 > limit_sq:
                continue
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_label = label
        if best_label:
            buckets[best_label].append(inv)

    ok = 0
    fail = 0
    parts: list[str] = []
    for label, pose in feet_targets:
        chunk = buckets.get(label) or []
        moved, missed = _snap_to_feet(pose, chunk, max_items=per_cap)
        ok += moved
        fail += missed
        if moved:
            parts.append(f"{label}={moved}")

    _vacuum_active = False
    _vacuum_ok = 0
    _vacuum_failed = int(fail)
    _vacuum_piled = int(ok)
    _vacuum_total = int(ok + fail)
    rad_bit = f", {float(radius_m):g}m" if float(radius_m or 0) > 0 else ", whole map"
    scope_bit = str(scope or "me")
    _vacuum_message = (
        f"Loot pull ({scope_bit}): {ok} at feet{rad_bit}"
        + (f" ({', '.join(parts)})" if parts else "")
        + (f", {fail} failed" if fail else "")
        + "."
    )
    _log(_vacuum_message)
    return _vacuum_message


def runtime_tick(*_args: Any, **_kwargs: Any) -> None:
    """Vacuum is one-shot; nothing to pace."""
    return None
