"""Nearby loot fingerprint — catch SpawnInventoryFromItemPool silent empties."""

from __future__ import annotations

from typing import Any

_LOOT_VERIFY_RADIUS = 1800.0
_FEET_LOOT_RADIUS = 650.0
_FEET_WEAPON_RADIUS = 420.0
_FEET_WEAPON_RADIUS_OVERRIDE: float | None = None


def set_feet_verify_radius(radius: float | None) -> None:
    """Widen the post-spawn scanner (Spawn All random spit lands past 420uu)."""
    global _FEET_WEAPON_RADIUS_OVERRIDE
    if radius is None:
        _FEET_WEAPON_RADIUS_OVERRIDE = None
        return
    _FEET_WEAPON_RADIUS_OVERRIDE = max(420.0, min(2500.0, float(radius)))
# Narrow classes — broad Actor/Pickup scans during spawn can AV through pyunrealsdk.
_LOOT_VERIFY_CLASSES = (
    "OakPickup",
    "OakInventory",
    "OakWeapon",
    "OakActor",
)
_WEAPON_LOOT_CLASSES = (
    "InventoryPickup",
    "OakPickup",
)
_LOOT_VERIFY_SCAN_CAP = 400
_CLAIMED_LOOT_KEYS: set[str] = set()


def _stable_object_key(obj: Any, cls_name: str, name: str) -> str:
    """Fingerprint the Unreal object, not its short-lived Python wrapper."""
    try:
        get_address = getattr(obj, "_get_address", None)
        if callable(get_address):
            address = int(get_address() or 0)
            if address:
                return f"{cls_name}:{name}:0x{address:x}"
    except Exception:
        pass
    try:
        get_path = getattr(obj, "GetPathName", None)
        if callable(get_path):
            path = str(get_path() or "").strip()
            if path:
                return f"{cls_name}:{path}"
    except Exception:
        pass
    try:
        path = str(getattr(obj, "PathName", "") or "").strip()
        if path:
            return f"{cls_name}:{path}"
    except Exception:
        pass
    # Actor names are stable within a world; never use id(obj), because
    # find_all may return a fresh Python wrapper for the same Unreal object.
    return f"{cls_name}:{name}"


def reset_claimed_loot_keys() -> None:
    """Clear loot keys already credited to a spawn (start of pearl Spawn All)."""
    _CLAIMED_LOOT_KEYS.clear()


def claim_loot_keys(keys: set[str]) -> None:
    _CLAIMED_LOOT_KEYS.update(keys)


def unclaimed_loot_gain(near_loc: Any, before_keys: set[str]) -> set[str]:
    """New weapon/pickup keys near feet not already credited to a prior spawn."""
    if near_loc is None:
        return set()
    after = feet_weapon_loot_keys(near_loc)
    return after - before_keys - _CLAIMED_LOOT_KEYS


def _in_imgui_frame() -> bool:
    try:
        import blimgui  # noqa: PLC0415

        return bool(getattr(blimgui, "_IN_IMGUI_FRAME", False))
    except Exception:
        return False


def feet_loot_keys(near_loc: Any) -> set[str]:
    """Tight-radius fingerprint for post-spawn OK/FAIL (player feet only)."""
    return nearby_loot_keys(near_loc, radius=_FEET_LOOT_RADIUS)


def feet_weapon_loot_keys(near_loc: Any) -> set[str]:
    """Weapon/pickup only — avoids false OK from ambient OakActor noise during pearl batches."""
    radius = float(_FEET_WEAPON_RADIUS_OVERRIDE or _FEET_WEAPON_RADIUS)
    return _scan_loot_keys(near_loc, radius=radius, classes=_WEAPON_LOOT_CLASSES)


def _scan_loot_keys(near_loc: Any, *, radius: float, classes: tuple[str, ...]) -> set[str]:
    if near_loc is None or _in_imgui_frame():
        return set()
    import unrealsdk

    out: set[str] = set()
    try:
        ox = float(getattr(near_loc, "X"))
        oy = float(getattr(near_loc, "Y"))
        oz = float(getattr(near_loc, "Z"))
    except Exception:
        return out
    r2 = float(radius) * float(radius)
    scanned = 0
    for cls in classes:
        if scanned >= _LOOT_VERIFY_SCAN_CAP:
            break
        try:
            objs = list(unrealsdk.find_all(cls, False) or [])
        except Exception:
            continue
        # find_all is normally oldest-to-newest.  Ground drops just created by
        # a pool spawn are at the end; scan those first so a busy world cannot
        # exhaust the cap on old inventory objects and report a false empty.
        for obj in reversed(objs):
            if scanned >= _LOOT_VERIFY_SCAN_CAP:
                break
            scanned += 1
            try:
                name = str(getattr(obj, "Name", "") or "")
                if not name or "Default__" in name:
                    continue
                loc = None
                for attr in ("K2_GetActorLocation", "GetActorLocation"):
                    fn = getattr(obj, attr, None)
                    if callable(fn):
                        loc = fn()
                        break
                if loc is None:
                    loc = getattr(obj, "Location", None)
                if loc is None:
                    continue
                dx = float(loc.X) - ox
                dy = float(loc.Y) - oy
                dz = float(loc.Z) - oz
                if dx * dx + dy * dy + dz * dz > r2:
                    continue
                out.add(_stable_object_key(obj, cls, name))
            except Exception:
                continue
    return out


def nearby_loot_keys(near_loc: Any, *, radius: float = _LOOT_VERIFY_RADIUS) -> set[str]:
    """Lightweight nearby inventory fingerprint for silent-empty detection.

    Returns an empty set when called mid-ImGui draw — callers must treat that as
    \"verify skipped\" (not silent-empty), or they will false-FAIL successful spawns.
    """
    return _scan_loot_keys(near_loc, radius=radius, classes=_LOOT_VERIFY_CLASSES)


def verify_available() -> bool:
    """False mid-ImGui — nearby_loot_keys cannot be trusted then."""
    return not _in_imgui_frame()


def player_location_from_pc(pc: Any) -> Any | None:
    if pc is None:
        return None
    pawn = getattr(pc, "Pawn", None)
    if pawn is None:
        return None
    for attr in ("K2_GetActorLocation", "GetActorLocation"):
        fn = getattr(pawn, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                continue
    return getattr(pawn, "Location", None)
