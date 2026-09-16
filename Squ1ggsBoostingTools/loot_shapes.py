"""Ground-loot shape layouts for Squ1ggs Boosting Tools.

Drop All / Spawn All with a shape and/or drop-from-above: dump inv still
creates the shiny, then items are pinned onto the silhouette (no random spit).
Rain/fountain/etc start above and land in the same shape. Quick Arrange /
Place Fully after the fact is teleport + net-update.
"""

from __future__ import annotations

import ctypes
import json
import math
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Callable

import unrealsdk
from mods_base import get_pc
from unrealsdk import logging
from unrealsdk.hooks import Type

_PREFIX = "[Squ1ggsBoostingTools | LootShapes]"

SHAPE_3D_NAMES: tuple[str, ...] = (
    "house",
    "boat",
    "car",
    "dome",
    "dna_helix",
    "claptrap",
    "pyramid_3d",
    "globe",
    "diamond_3d",
    "blocks",
    "cube",
    "torus",
    "crown",
    "ufo",
    "rocket",
    "gear",
    "nova",
    "forbidden_one",
    "forbidden_pair",
)
SHAPE_2D_NAMES: tuple[str, ...] = (
    "circle",
    "double_ring",
    "spiral",
    "star",
    "star_filled",
    "firehawk",
    "diamond",
    "square",
    "grid",
    "rows",
    "arc",
    "fan",
    "arrow",
    "cross",
    "x_mark",
    "infinity",
    "figure8",
    "wave",
    "letter_s",
    "text",
    "lightning",
    "vault",
    "psycho",
    "pyramid",
    "hexagon",
    "honeycomb",
    "scatter",
    "poisson",
    "rarity_lanes",
    "type_piles",
    "unique_piles",
    "heart",
    "line",
    "rings",
    "smiley",
)
SHAPE_NAMES: tuple[str, ...] = (*SHAPE_3D_NAMES, *SHAPE_2D_NAMES)
SHAPE_LABELS: dict[str, str] = {
    "dna_helix": "DNA helix",
    "pyramid_3d": "pyramid",
    "psycho": "psycho",
    "claptrap": "Claptrap",
    "x_mark": "X mark",
    "globe": "globe",
    "nova": "nova (3D ball -> pulse)",
    "letter_s": "letter S",
    "text": "text",
    "star_filled": "star filled",
    "double_ring": "double ring",
    "type_piles": "type piles",
    "unique_piles": "unique item piles",
    "rarity_lanes": "rarity lanes",
    "diamond_3d": "diamond (3D)",
    "blocks": "blocks",
    "cube": "cube",
    "torus": "torus",
    "crown": "crown",
    "ufo": "UFO",
    "rocket": "rocket",
    "gear": "gear",
    "forbidden_one": "the forbidden one",
    "forbidden_pair": "the forbidden pair",
}
SHAPE_HIDDEN_3D_NAMES: frozenset[str] = frozenset({"forbidden_one", "forbidden_pair"})
PILE_GROUP_SHAPES: frozenset[str] = frozenset({"type_piles", "unique_piles", "rarity_lanes"})
SHAPE_PEEL_TO_GROUND: frozenset[str] = frozenset({"dome"})

_DEFAULT_RADIUS = 220.0
_DEFAULT_SPACING = 140.0
_DEFAULT_PER_RING = 28
_DEFAULT_Z_BIAS = 8.0
_DEFAULT_LINE_LENGTH = 520.0
_DEFAULT_DROP_HEIGHT = 440.0
_SHAPE_LIFT_PAD = 22.0
_MIN_RADIUS = 80.0
_MAX_RADIUS = 800.0
_MIN_SPACING = 50.0
_MAX_SPACING = 400.0
_MIN_PER_RING = 6
_MAX_PER_RING = 64
_MIN_Z_BIAS = 0.0
_MAX_Z_BIAS = 250.0
_MIN_STACK = 0.0
_MAX_STACK = 200.0
_MIN_LINE_LENGTH = 200.0
# Hard cap — never grow past this (old path expanded with item count → map-long lines).
_MAX_LINE_LENGTH = 720.0
# Car silhouette sits around the player — allow near-ground drop height.
_MIN_DROP_HEIGHT = 0.0
_MAX_DROP_HEIGHT = 800.0
_CAR_DEFAULT_DROP_HEIGHT = 8.0
_CAR_GROUND_LIFT = 6.0
_CAR_WORLD_Z_BIAS = -10.0
_MIN_ITEM_GAP = 48.0
# 3D globe/pyramid grew past this and froze the session (physics + pin restamps).
_MAX_SHAPE_SPAN = 560.0
# Line / wave / S / lightning / rows — keep strokes near the player.
_MAX_LINE_SPAN = 720.0
_MAX_GLOBE_RADIUS = 280.0
_MAX_PYRAMID_SPAN = 480.0
_PICKUP_MATERIALS = (
    "Health",
    "ArmorShard",
    "Ammo",
    "ammo",
    "Money",
    "Eridium",
    "ShieldBooster",
    "Cash",
    "Shield",
    "Grenade",
)

# LOV / inventory identity serial layout
_ITEM_SERIAL_POINTER_OFFSET = 0xA0
_ITEM_SERIAL_LENGTH_OFFSET = 0xB0
_ITEM_SERIAL_MAX_CHARS = 4096

_last_layout: dict[str, Any] = {
    "shape": "rings",
    "radius": _DEFAULT_RADIUS,
    "spacing": _DEFAULT_SPACING,
    "per_ring": _DEFAULT_PER_RING,
    "z_bias": _DEFAULT_Z_BIAS,
    "include_consumables": False,
    "mode": "place_fully",
    "entries": [],  # [{serial, x, y, z}] for re-spawn on join
    "party_count": 0,
    "applied_at": 0.0,
}
_status = "Idle."
_hooks_installed = False
_join_reapply_pending = False
_join_reapply_at = 0.0
_coop_followup_sync_at: float = 0.0
_coop_followup_waves: int = 0
# After clients receive the settled pose: keep held/3D/Stay pins frozen.
# Mass gravity wake collapses silhouettes and hitchs the lobby.
_coop_pickup_safe_active: bool = False
_coop_pickup_unlock_at: float = 0.0
_coop_pickup_unlock_cursor: int = 0
# Snapshot at arm time — do not re-evaluate Stay mid-publish (shape/stay can flicker).
_coop_keep_freeze: bool = False
# Visibility-only ForceNet after GLH-style pickable place (no pin / no freeze).
_coop_vis_addrs: list[int] = []
_coop_vis_cursor: int = 0
_coop_vis_until: float = 0.0
_coop_vis_ok: set[int] = set()
_float_jobs: list[dict[str, Any]] = []
_pinned_slots: list[dict[str, Any]] = []
_pin_tick: int = 0
# Shiny/bulk land: slot index → itempool name (for @U serial when pickup has no LOV serial).
_land_slot_pools: dict[int, str] = {}
_guest_sync_complete_announced: bool = False
_abandon_epoch: int = 0
_absorb_orphans_after_abandon: bool = False
_absorb_orphans_at: float = 0.0
_repin_log_at: float = 0.0


def _log_dev(msg: str) -> None:
    """Co-op sync detail — runtime log only, not unrealsdk.log."""
    try:
        from .runtime_log import note

        note(f"LootShapes {msg}")
    except Exception:
        pass


def _log(msg: str) -> None:
    """Short user-facing line in unrealsdk.log only."""
    text = str(msg or "").strip()
    if not text:
        return
    logging.info(f"{_PREFIX} {text}")


def _clamp_f(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        number = float(value)
    except Exception:
        return float(default)
    if number != number:  # NaN
        return float(default)
    return max(float(lo), min(float(hi), number))


def _clamp_i(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        number = int(round(float(value)))
    except Exception:
        return int(default)
    return max(int(lo), min(int(hi), number))


def clamp_layout_params(
    *,
    radius: Any = _DEFAULT_RADIUS,
    spacing: Any = _DEFAULT_SPACING,
    per_ring: Any = _DEFAULT_PER_RING,
    line_length: Any = _DEFAULT_LINE_LENGTH,
    drop_height: Any = _DEFAULT_DROP_HEIGHT,
    z_bias: Any = _DEFAULT_Z_BIAS,
    stack_height: Any = 0.0,
) -> dict[str, float | int]:
    """Hard limits for shape sliders. 0 line length stacked every gun and froze physics."""
    return {
        "radius": _clamp_f(radius, _MIN_RADIUS, _MAX_RADIUS, _DEFAULT_RADIUS),
        "spacing": _clamp_f(spacing, _MIN_SPACING, _MAX_SPACING, _DEFAULT_SPACING),
        "per_ring": _clamp_i(per_ring, _MIN_PER_RING, _MAX_PER_RING, _DEFAULT_PER_RING),
        "line_length": _clamp_f(line_length, _MIN_LINE_LENGTH, _MAX_LINE_LENGTH, _DEFAULT_LINE_LENGTH),
        "drop_height": _clamp_f(drop_height, _MIN_DROP_HEIGHT, _MAX_DROP_HEIGHT, _DEFAULT_DROP_HEIGHT),
        "z_bias": _clamp_f(z_bias, _MIN_Z_BIAS, _MAX_Z_BIAS, _DEFAULT_Z_BIAS),
        "stack_height": _clamp_f(stack_height, _MIN_STACK, _MAX_STACK, 0.0),
    }


def _uobject_addr(obj: Any) -> int:
    """0 if the wrapper is gone. Never TeleportTo 0xffffffffffffffff."""
    if obj is None:
        return 0
    try:
        addr = int(obj._get_address() or 0)
    except Exception:
        return 0
    if addr <= 0 or addr == 0xFFFFFFFFFFFFFFFF:
        return 0
    return addr


def _live(obj: Any) -> bool:
    """Address only — Name/Class probes hitch and false-kill dump pickups mid-flight."""
    return bool(_uobject_addr(obj))


def _make_vector(x: float, y: float, z: float) -> Any:
    return unrealsdk.make_struct("Vector", X=float(x), Y=float(y), Z=float(z))


def _make_rotator(pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0) -> Any:
    try:
        return unrealsdk.make_struct("Rotator", Pitch=float(pitch), Yaw=float(yaw), Roll=float(roll))
    except Exception:
        return unrealsdk.make_struct("Rotator")


def _player_anchor() -> tuple[Any, float, float, float, float] | None:
    """Return (pawn, x, y, z, yaw_rad) at Drop-near target — look yaw when local."""
    pc = get_pc()
    if pc is None:
        return None
    pawn = getattr(pc, "Pawn", None) or getattr(pc, "OakCharacter", None)
    try:
        from .spawn_targets import mode as spawn_mode
        from .spawn_targets import resolve_pose

        pose = resolve_pose(pc)
        if pose is not None:
            loc, rot = pose
            if str(spawn_mode() or "local").strip().lower() == "local":
                fn = getattr(pc, "GetControlRotation", None)
                look = None
                if callable(fn):
                    try:
                        look = fn()
                    except Exception:
                        look = None
                if look is None:
                    look = getattr(pc, "ControlRotation", None)
                if look is not None:
                    rot = look
            yaw_raw = float(getattr(rot, "Yaw", 0.0) or 0.0)
            if abs(yaw_raw) > 720.0:
                yaw_raw = yaw_raw * (360.0 / 65536.0)
            yaw = math.radians(yaw_raw)
            # Prefer pawn forward so yank/shape slots match engine facing.
            try:
                if _live(pawn):
                    fwd = pawn.GetActorForwardVector()
                    fx = float(getattr(fwd, "X", 0.0) or 0.0)
                    fy = float(getattr(fwd, "Y", 0.0) or 0.0)
                    if math.hypot(fx, fy) > 1e-3:
                        yaw = math.atan2(fy, fx)
            except Exception:
                pass
            if not _live(pawn):
                pawn = loc
            return pawn, float(loc.X), float(loc.Y), float(loc.Z), yaw
    except Exception:
        pass
    if not _live(pawn):
        return None
    try:
        loc = pawn.K2_GetActorLocation()
        try:
            fwd = pawn.GetActorForwardVector()
            fx = float(getattr(fwd, "X", 0.0) or 0.0)
            fy = float(getattr(fwd, "Y", 0.0) or 0.0)
            if math.hypot(fx, fy) > 1e-3:
                return pawn, float(loc.X), float(loc.Y), float(loc.Z), math.atan2(fy, fx)
        except Exception:
            pass
        rot = None
        fn = getattr(pc, "GetControlRotation", None)
        if callable(fn):
            try:
                rot = fn()
            except Exception:
                rot = None
        if rot is None:
            rot = getattr(pc, "ControlRotation", None)
        if rot is None:
            rot = pawn.K2_GetActorRotation()
        yaw_raw = float(getattr(rot, "Yaw", 0.0) or 0.0)
        if abs(yaw_raw) > 720.0:
            yaw_raw = yaw_raw * (360.0 / 65536.0)
        yaw = math.radians(yaw_raw)
        return pawn, float(loc.X), float(loc.Y), float(loc.Z), yaw
    except Exception:
        return None


def _iotd_pickups() -> list[Any]:
    out: list[Any] = []
    pc = get_pc()
    if pc is None:
        return out
    try:
        machines = unrealsdk.find_all("OakVendingMachine", False) or []
    except Exception:
        return out
    for machine in machines:
        try:
            if not machine or machine == machine.Class.ClassDefaultObject:
                continue
            featured = machine.GetIOTDForPlayer(pc)
            if featured:
                out.append(featured)
        except Exception:
            continue
    return out


_SLOT_CODE = {
    "ar": "assault_rifle",
    "ps": "pistol",
    "sg": "shotgun",
    "sm": "smg",
    "sr": "sniper",
    "hw": "heavy",
    "sh": "shield",
    "gd": "grenade",
    "gr": "grenade",
    "cm": "classmod",
    "rk": "repkit",
}
_SLOT_RE = re.compile(
    r"(?:^|[^a-z0-9])(?:jak|ted|vla|mal|tor|dad|rip|ord|bor|coa|hyp|atl|odr)?"
    r"[_/]?(ar|ps|sg|sm|sr|hw)(?:[^a-z0-9]|$)"
)
_RARITY_COMP_RE = re.compile(r"comp[_-]?0([1-6])")
_RARITY_FROM_COMP = {
    "1": "common",
    "2": "uncommon",
    "3": "rare",
    "4": "epic",
    "5": "legendary",
    "6": "pearl",
}


def _mid_shape_dump() -> bool:
    """Spawn All / shaped dump still filling slots — guest net + stale reads AV here."""
    return bool(_land_active and not _landing_settle_done)


def _append_obj_names(parts: list[str], obj: Any, *, depth: int = 0, seen: set[int] | None = None) -> None:
    if obj is None or depth > 3 or not _live(obj):
        return
    seen = seen if seen is not None else set()
    try:
        key = id(obj)
    except Exception:
        key = 0
    if key and key in seen:
        return
    if key:
        seen.add(key)
    for attr in ("Name", "PathName", "ObjectPath", "ItemName", "DisplayName", "UIName"):
        try:
            text = str(getattr(obj, attr, "") or "").strip()
        except Exception:
            text = ""
        if text and text not in ("None", "NoneType"):
            parts.append(text)
    if depth >= 3:
        return
    for attr in (
        "Inventory",
        "AssociatedInventory",
        "PickupInventory",
        "Item",
        "Weapon",
        "InventoryBalanceData",
        "BalanceData",
        "ItemData",
        "InventoryData",
        "WeaponData",
        "ShieldData",
        "GrenadeData",
        "ClassModData",
        "RepKitData",
        "ManufacturerData",
        "Identity",
        "ItemType",
        "WeaponType",
        "GearType",
        "RarityData",
        "Rarity",
    ):
        try:
            child = getattr(obj, attr, None)
        except Exception:
            child = None
        if child is None or child is obj:
            continue
        _append_obj_names(parts, child, depth=depth + 1, seen=seen)


def _pickup_type_blob(inv: Any) -> str:
    """Gather name / path / material / serial signals for gear-type sorting."""
    parts: list[str] = []
    _append_obj_names(parts, inv, depth=0)
    for attr in (
        "BodyData",
        "Name",
        "ItemName",
        "DisplayName",
        "UIName",
        "InventoryName",
    ):
        try:
            val = getattr(inv, attr, None)
        except Exception:
            val = None
        if val is None:
            continue
        if isinstance(val, (str, bytes, int, float)):
            text = str(val).strip()
            if text:
                parts.append(text)
            continue
        _append_obj_names(parts, val, depth=0)
    try:
        parts.append(str(getattr(getattr(inv, "Class", None), "Name", "") or ""))
    except Exception:
        pass
    for attr in (
        "InventoryBalanceData",
        "BalanceData",
        "ItemData",
        "InventoryData",
        "WeaponData",
        "ShieldData",
        "GrenadeData",
        "ClassModData",
        "RepKitData",
        "ManufacturerData",
    ):
        try:
            node = getattr(inv, attr, None)
        except Exception:
            node = None
        if node is None:
            continue
        try:
            parts.append(str(getattr(node, "Name", "") or ""))
        except Exception:
            pass
        try:
            parts.append(str(getattr(node, "PathName", "") or getattr(node, "ObjectPath", "") or ""))
        except Exception:
            pass
    try:
        root = getattr(inv, "RootPrimitiveComponent", None)
        if root is not None and _live(root):
            parts.append(str(getattr(root, "Name", "") or ""))
        count = int(root.GetNumMaterials()) if root and _live(root) else 0
        for index in range(min(count, 8)):
            material = root.GetMaterial(index)
            if material:
                parts.append(str(getattr(material, "Name", "") or ""))
    except Exception:
        pass
    return " ".join(parts).lower()


_SHAPE_GEAR_TYPES: frozenset[str] = frozenset(
    {
        "pistol",
        "smg",
        "shotgun",
        "sniper",
        "assault_rifle",
        "weapon",
        "shield",
        "grenade",
        "classmod",
        "heavy",
        "repkit",
    }
)
_SHAPE_REJECT_BLOB = (
    "stringlight",
    "string_light",
    "stringlights",
    "pile_string",
    "sm_pile",
    "pile_stringlights",
    "sm_pile_stringlights",
    "io_placeable",
    "placeable",
    "mercenary day",
    "cosmetic",
    "echo_attachment",
    "trinket",
    "ornament",
    "decoration",
    "hotdog",
    "hot_dog",
    "fairylight",
    "fairy_light",
)
# Hard pin ceiling — 500+ Place Fully + ForceNet guest sync AVs (0xffffffffffffffff).
_MAX_SHAPE_PINS_SOLO = 360
_MAX_SHAPE_PINS_COOP = 180


def _classify_gear_type(inv: Any) -> str:
    text = _pickup_type_blob(inv)
    slot_hit = _SLOT_RE.search(text)
    if slot_hit:
        return _SLOT_CODE.get(slot_hit.group(1), "weapon")
    # More specific tokens first so AR/SMG/etc. do not all collapse to "weapon".
    if any(
        k in text
        for k in (
            "classmod",
            "class_mod",
            "class-mod",
            "enhancement",
            "com_",
            "/com/",
            "classmoddata",
        )
    ):
        return "classmod"
    if any(k in text for k in ("repkit", "repairkit", "repair_kit", "kit_rep")):
        return "repkit"
    if any(
        k in text
        for k in (
            "oakshield",
            "shielddata",
            "/shield/",
            "energy_shield",
            "energyshield",
        )
    ) or re.search(r"(?:^|[^a-z])shield(?:[^a-z]|$)", text):
        return "shield"
    if any(
        k in text
        for k in (
            "grenade",
            "ordnance",
            "throwable",
            "grenadedata",
            "/grenade/",
        )
    ):
        return "grenade"
    if any(k in text for k in ("heavyweapon", "heavy_weapon", "_hw_", "/hw/", "rocketlauncher", "launcher")):
        return "heavy"
    if any(k in text for k in ("_sr_", "/sr/", "sniper", "sniperrifle")):
        return "sniper"
    if any(k in text for k in ("_sg_", "/sg/", "shotgun")):
        return "shotgun"
    if any(k in text for k in ("_sm_", "/sm/", "smg", "submachine")):
        return "smg"
    if any(k in text for k in ("_ps_", "/ps/", "pistol", "handgun", "handcannon")):
        return "pistol"
    if any(k in text for k in ("_ar_", "/ar/", "assaultrifle", "assault_rifle")):
        return "assault_rifle"
    if re.search(r"(?:^|[^a-z])rifle(?:[^a-z]|$)", text) and "sniper" not in text:
        return "assault_rifle"
    if any(k in text for k in ("oakweapon", "inventoryweapon", "weap_", "/weap", "firearm")):
        return "weapon"
    try:
        name = str(getattr(inv, "Name", "") or "").lower()
    except Exception:
        name = ""
    token = "".join(ch if ch.isalnum() else " " for ch in name).split()
    if token:
        stem = token[0][:18]
        if stem and stem not in ("inventorypickup", "default", "pickup", "oakinventory"):
            return stem
    return "other"


def _pickup_skip_shape(inv: Any, *, pool_name: str = "") -> bool:
    """Gifts/currency/mission/placeable junk — never silhouette guns."""
    blob = _pickup_type_blob(inv).lower()
    pool_l = str(pool_name or "").strip().lower()
    if any(k in blob or k in pool_l for k in _SHAPE_REJECT_BLOB):
        return True
    if any(
        k in blob or k in pool_l
        for k in (
            "gift",
            "guntoter",
            "present",
            "currency",
            "cash",
            "eridium",
            "lootbat",
            "mission",
            "mainmission",
            "sidemission",
            "quest",
            "objective",
        )
    ):
        return True
    try:
        name = str(getattr(inv, "Name", "") or "").lower()
    except Exception:
        name = ""
    return any(k in name for k in ("hotdog", "hot_dog", "mission", "quest", "objective", "stringlight", "pile_"))


def _is_shape_gear_pickup(inv: Any, *, pool_name: str = "") -> bool:
    """Only weapons/shields/grenades/classmods/heavy/repkits may pin into 3D shapes."""
    if _pickup_skip_shape(inv, pool_name=pool_name):
        return False
    gtype = _classify_gear_type(inv)
    if gtype in _SHAPE_GEAR_TYPES:
        return True
    blob = _pickup_type_blob(inv)
    if any(k in blob for k in ("oakweapon", "inventoryweapon", "weap_", "shielddata", "grenadedata", "classmod")):
        return True
    return False


def _shape_gear_list(candidates: list[Any]) -> list[Any]:
    """Filter + cap ground loot for Place Fully / arrange (stringlight piles AV)."""
    gear: list[Any] = []
    skipped = 0
    for inv in candidates:
        if not _live(inv):
            continue
        try:
            if not _is_shape_gear_pickup(inv):
                skipped += 1
                continue
        except Exception:
            skipped += 1
            continue
        gear.append(inv)
    cap = _MAX_SHAPE_PINS_COOP if _want_coop_replicate() else _MAX_SHAPE_PINS_SOLO
    if len(gear) > cap:
        _log_dev(f"Shape pin cap: using {cap}/{len(gear)} gear (skipped decor={skipped}).")
        gear = gear[:cap]
    elif skipped:
        _log_dev(f"Shape gear filter skipped {skipped} placeable/light/non-gun pickup(s).")
    return gear


def _purge_decor_pins() -> int:
    """Drop placeable/pile pins (e.g. SM_Pile_StringLights) that poison physics on join."""
    if not _pinned_slots:
        return 0
    removed = 0
    kept: list[dict[str, Any]] = []
    for row in _pinned_slots:
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr) if addr else None
        if inv is None or not _live(inv):
            kept.append(row)
            continue
        pool = str(row.get("pool_name") or "").lower()
        if pool and any(k in pool for k in _SHAPE_REJECT_BLOB):
            try:
                _hide_pickup(inv)
            except Exception:
                pass
            removed += 1
            continue
        try:
            root = getattr(inv, "RootPrimitiveComponent", None)
            rname = str(getattr(root, "Name", "") or "").lower() if root is not None and _live(root) else ""
        except Exception:
            rname = ""
        if any(k in rname for k in ("stringlight", "pile_string", "sm_pile")):
            try:
                _hide_pickup(inv)
            except Exception:
                pass
            removed += 1
            continue
        if not _is_shape_gear_pickup(inv, pool_name=pool):
            try:
                _hide_pickup(inv)
            except Exception:
                pass
            removed += 1
            continue
        kept.append(row)
    if removed:
        _pinned_slots[:] = kept
        _log_dev(f"Purged {removed} non-gear pin(s) from held shape (placeables/piles).")
    return removed


def register_land_slot_pool(index: int, pool_name: str) -> None:
    """Record which itempool filled a land slot (shiny dump has no readable LOV serial)."""
    global _land_slot_pools
    try:
        idx = int(index)
    except Exception:
        return
    name = str(pool_name or "").strip()
    if not name:
        return
    _land_slot_pools[idx] = name


def _planned_serial_for_slot(index: int) -> str:
    pool = str(_land_slot_pools.get(int(index)) or "")
    if not pool:
        return ""
    try:
        from .shinies import serial_for_shiny_pool

        serial = serial_for_shiny_pool(pool) or ""
    except Exception:
        serial = ""
    return serial if serial.startswith("@U") else ""


def _serial_for_pin_row(row: dict[str, Any], *, resolve_inv: bool = True) -> str:
    serial = str(row.get("serial") or "")
    if serial.startswith("@U"):
        return serial
    inv = None
    if resolve_inv:
        try:
            inv = _resolve_pin_inv(row, fresh=False)
        except Exception:
            inv = None
        if inv is not None:
            try:
                serial = serial_from_pickup(inv)
            except Exception:
                serial = ""
            if serial.startswith("@U"):
                row["serial"] = serial
                return serial
    pool = str(row.get("pool_name") or "")
    if not pool:
        try:
            idx = row.get("slot_index")
            if idx is not None:
                pool = str(_land_slot_pools.get(int(idx)) or "")
                if pool:
                    row["pool_name"] = pool
        except Exception:
            pool = ""
    if pool:
        try:
            from .shinies import serial_for_shiny_pool

            serial = serial_for_shiny_pool(pool) or ""
        except Exception:
            serial = ""
        if serial.startswith("@U"):
            row["serial"] = serial
            return serial
    try:
        idx = row.get("slot_index")
        if idx is not None:
            serial = _planned_serial_for_slot(int(idx))
            if serial:
                row["serial"] = serial
                return serial
    except Exception:
        pass
    return ""


def _track_layout_entry(inv: Any, x: float, y: float, z: float) -> None:
    serial = serial_from_pickup(inv)
    if not serial:
        return
    entries: list[dict[str, Any]] = list(_last_layout.get("entries") or [])
    for row in entries:
        if str(row.get("serial") or "") == serial:
            row["x"], row["y"], row["z"] = float(x), float(y), float(z)
            _last_layout["entries"] = entries
            return
    entries.append({"serial": serial, "x": float(x), "y": float(y), "z": float(z)})
    _last_layout["entries"] = entries


def _build_layout_entries_from_pins() -> int:
    """One layout row per held pin (never dedupe by serial — shapes reuse the same shiny)."""
    entries: list[dict[str, Any]] = []
    for i, row in enumerate(_pinned_slots):
        if not row.get("hold"):
            continue
        if row.get("slot_index") is None:
            row["slot_index"] = i
        try:
            slot_i = int(row.get("slot_index") or i)
        except Exception:
            slot_i = i
        pool = str(row.get("pool_name") or _land_slot_pools.get(slot_i, "") or "")
        if pool:
            row["pool_name"] = pool
        serial = _serial_for_pin_row(row, resolve_inv=True)
        entries.append(
            {
                "serial": serial if serial.startswith("@U") else "",
                "x": float(row["x"]),
                "y": float(row["y"]),
                "z": float(row["z"]),
                "yaw": float(row.get("yaw") or 0.0),
                "pitch": float(row.get("pitch") or 0.0),
                "roll": float(row.get("roll") or 0.0),
                "pin_addr": int(row.get("addr") or 0),
                "slot_index": slot_i,
                "pool_name": pool,
            }
        )
    _last_layout["entries"] = entries
    return len(entries)


def _progression_network_busy() -> bool:
    """Pause shape net pushes while challenge RPC workflows own the co-op lane."""
    try:
        from . import uvhm_runtime

        status = uvhm_runtime.status()
        if bool(status.get("running") or status.get("queued")):
            return True
    except Exception:
        pass
    try:
        from . import challenge_bulk_runtime

        status = challenge_bulk_runtime.status()
        if bool(status.get("active") or status.get("queued")):
            return True
    except Exception:
        pass
    return False


def _arm_coop_pickup_safe(*, delay: float = 2.5) -> None:
    """Queue one bounded slot publish, then keep freeze (or rare ground unlock)."""
    global _coop_pickup_safe_active, _coop_pickup_unlock_at, _coop_pickup_unlock_cursor
    global _guest_sync_active, _guest_sync_cursor, _guest_sync_last
    global _coop_followup_sync_at, _coop_followup_waves, _coop_pins_synced
    global _coop_keep_freeze
    if not _want_coop_replicate() or not _pinned_slots:
        return
    _coop_pickup_safe_active = True
    _coop_keep_freeze = bool(_coop_should_keep_freeze())
    _coop_pickup_unlock_at = time.monotonic() + max(0.0, float(delay))
    _coop_pickup_unlock_cursor = 0
    # Dedicated pickup-safe tick owns the one-time publish. Never start the old
    # guest retry/follow-up machinery.
    _guest_sync_active = False
    _guest_sync_cursor = 0
    _guest_sync_last = 0.0
    _coop_followup_sync_at = 0.0
    _coop_followup_waves = 0
    _coop_pins_synced = 0
    _last_layout["pickup_safe_ready"] = False
    _last_layout["pickup_safe_armed_at"] = time.monotonic()
    _last_layout["pickup_safe_progress_at"] = 0.0
    for row in _pinned_slots:
        row.pop("guest_ok", None)
        row.pop("guest_fail", None)
        row.pop("guest_skip", None)
        row.pop("guest_synced_at", None)
        row.pop("client_motion_unlocked", None)
        row["guest_publish_attempts"] = 0
        # Display silhouette — collect is Use → backpack, not Attract.
        row["hold"] = True
        # Keep pin rows alive for the whole publish — 6s TTL was killing them.
        try:
            row["expires"] = time.monotonic() + 600.0
        except Exception:
            pass
    _log(
        f"Co-op pickup-safe publish queued ({len(_pinned_slots)} pin(s)); "
        "shape held — Use an item to collect into backpack."
    )


def _tick_coop_pickup_safe(now: float) -> None:
    """Publish each slot once. Held/Stay/3D pins stay frozen — never mass-drop."""
    global _coop_pickup_unlock_at, _coop_pickup_unlock_cursor
    global _coop_pins_synced, _coop_pickup_safe_active
    global _pinned_slots, _pickup_by_addr
    global _guest_sync_active, _coop_followup_waves, _coop_followup_sync_at
    global _coop_keep_freeze
    if not _coop_pickup_safe_active or _coop_pickup_unlock_at <= 0.0:
        return
    if not _pinned_slots:
        # Pins evaporated mid-publish (old 6s TTL) — stop hanging forever.
        _coop_pickup_safe_active = False
        _coop_keep_freeze = False
        _coop_pickup_unlock_at = 0.0
        _log("Co-op shape publish aborted: pins cleared before guest sync finished.")
        return
    if now < _coop_pickup_unlock_at:
        return
    if _progression_network_busy() or _in_join_quiet(now):
        _coop_pickup_unlock_at = now + 0.5
        return
    rows = _pinned_slots
    n = len(rows)
    keep_freeze = bool(_coop_keep_freeze)
    armed_at = float(_last_layout.get("pickup_safe_armed_at") or now)
    # Force finish so we never leave a partial frozen house for guests.
    force_done = (now - armed_at) >= 40.0
    # Stay/held: stay conservative. Ground: still avoid ForceNet storms (lag).
    if keep_freeze:
        publish_budget = 3 if n > 100 else 4
        unlock_budget = 8
        retry_gap = 0.14 if n > 100 else 0.10
    else:
        publish_budget = 4 if n > 80 else 5
        unlock_budget = 10
        retry_gap = 0.10
    attempted = 0
    walked = 0
    while walked < n and attempted < publish_budget:
        idx = _coop_pickup_unlock_cursor % max(1, n)
        _coop_pickup_unlock_cursor = (idx + 1) % max(1, n)
        walked += 1
        row = rows[idx]
        if row.get("guest_ok") or row.get("guest_skip"):
            continue
        attempted += 1
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr) if addr else None
        if inv is None:
            inv = _resolve_pin_inv(row, fresh=False)
        if inv is None or not _live(inv):
            misses = int(row.get("guest_publish_attempts") or 0) + 1
            row["guest_publish_attempts"] = misses
            if misses >= 8 or force_done:
                row["guest_skip"] = True
                row["guest_synced_at"] = now
            continue
        try:
            ok = _push_pin_to_guests(row, inv)
        except Exception:
            ok = False
        if ok or row.get("guest_ok") or row.get("guest_skip"):
            row["guest_ok"] = True
            row["guest_synced_at"] = now
            row.pop("guest_fail", None)
            continue
        # Net budget / quiet miss — retry until force_done (do not guest_skip early).
        if force_done:
            row["guest_skip"] = True
            row["guest_ok"] = True
            row["guest_synced_at"] = now

    unlocked = 0
    for row in rows:
        if unlocked >= unlock_budget and not force_done:
            break
        if row.get("client_motion_unlocked"):
            continue
        if row.get("guest_skip") and not row.get("guest_ok"):
            row["client_motion_unlocked"] = True
            continue
        synced_at = float(row.get("guest_synced_at") or 0.0)
        if not force_done:
            if not (row.get("guest_ok") or row.get("guest_skip")):
                continue
            if synced_at <= 0.0 or now - synced_at < 0.35:
                continue
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr) if addr else None
        if inv is None or not _live(inv):
            row["client_motion_unlocked"] = True
            continue
        try:
            # Soft stamp only — never mass SetSimulatePhysics (lag + floor drop,
            # and 3.8.172 still left guests unable to pick). Keep pose frozen;
            # per-item Use/proximity restores dump physics.
            _stamp_guest_grab_ready(inv)
            row["client_motion_unlocked"] = True
            unlocked += 1
        except Exception:
            if force_done:
                row["client_motion_unlocked"] = True
            continue

    _coop_pins_synced = sum(1 for row in rows if row.get("guest_ok"))
    pending = sum(
        1
        for row in rows
        if not ((row.get("guest_ok") or row.get("guest_skip")) and row.get("client_motion_unlocked"))
    )
    ready = pending <= 0 or force_done
    if force_done and pending:
        # Last-chance unlock whatever is still tracked.
        for row in rows:
            if row.get("client_motion_unlocked"):
                continue
            addr = int(row.get("addr") or 0)
            inv = _live_pickup(addr) if addr else None
            if inv is not None and _live(inv):
                try:
                    _stamp_guest_grab_ready(inv)
                except Exception:
                    pass
            row["client_motion_unlocked"] = True
            if not (row.get("guest_ok") or row.get("guest_skip")):
                row["guest_skip"] = True
                row["guest_ok"] = True
        pending = 0
        ready = True

    prog_at = float(_last_layout.get("pickup_safe_progress_at") or 0.0)
    if now - prog_at >= 2.5 and not ready:
        _last_layout["pickup_safe_progress_at"] = now
        _log(
            f"Co-op shape publish… {_coop_pins_synced}/{n} netted, "
            f"{n - pending}/{n} grab-ready ({pending} left)."
        )

    _coop_pickup_unlock_at = now + (0.8 if ready else retry_gap)
    if ready and not bool(_last_layout.get("pickup_safe_ready")):
        _last_layout["pickup_safe_ready"] = True
        skipped = sum(1 for row in rows if row.get("guest_skip"))
        # Always keep pins for ServerUse / proximity hand-off. Clearing them
        # after world unlock left guests with floor guns that still would not Use.
        kept = [row for row in rows if not row.get("guest_skip")]
        _pinned_slots = kept
        addr_map: dict[int, Any] = {}
        for row in kept:
            addr = int(row.get("addr") or 0)
            if not addr:
                continue
            inv = _live_pickup(addr)
            if inv is not None:
                addr_map[addr] = inv
        _pickup_by_addr = addr_map
        _log(
            f"Co-op shape ready: {_coop_pins_synced}/{n} visible — Use to collect"
            + (f" ({skipped} skipped)" if skipped else "")
            + (" (forced)" if force_done else "")
            + "."
        )
        _coop_pickup_safe_active = False
        _coop_keep_freeze = False
        _coop_pickup_unlock_at = 0.0
        _coop_pickup_unlock_cursor = 0
        _guest_sync_active = False
        _coop_followup_waves = 0
        _coop_followup_sync_at = 0.0


def _schedule_coop_followup_sync(*, waves: int = 3, gap: float = 3.0) -> None:
    """Late join / streaming clients often miss the first net burst."""
    global _coop_followup_sync_at, _coop_followup_waves
    if _coop_pickup_safe_active:
        return
    if not _want_coop_replicate() or not _pinned_slots:
        return
    _coop_followup_waves = max(0, int(waves))
    _coop_followup_sync_at = time.monotonic() + max(1.5, float(gap))


def _tick_coop_followup_sync(now: float) -> None:
    global _coop_followup_sync_at, _coop_followup_waves, _coop_pins_synced, _guest_sync_cursor
    if _coop_followup_waves <= 0 or now < _coop_followup_sync_at:
        return
    if _progression_network_busy():
        _coop_followup_sync_at = now + 2.0
        return
    if _in_join_quiet(now):
        return
    if _land_active and not _landing_settle_done:
        return
    if not _want_coop_replicate() or not _pinned_slots:
        _coop_followup_waves = 0
        return
    pending = sum(1 for row in _pinned_slots if not row.get("guest_ok"))
    if pending <= 0:
        _coop_followup_waves = 0
        return
    _coop_followup_waves -= 1
    _coop_followup_sync_at = now + 4.0
    try:
        _guest_sync_cursor = 0
        _coop_pins_synced = 0
        _begin_guest_sync(force=True, clear_ok=False)
        _log_dev(
            f"Co-op follow-up guest sync ({_coop_followup_waves} wave(s) remain, "
            f"{pending} pin(s) pending)."
        )
    except Exception as exc:
        _log(f"co-op follow-up sync failed: {exc!r}")


def _stamp_coop_spawn(
    inv: Any,
    x: float,
    y: float,
    z: float,
    yaw: float,
    *,
    pitch: float = 0.0,
    roll: float = 0.0,
) -> None:
    """Movement stamp only — no ForceNetUpdate during dump (that was the hitch)."""
    if not _want_coop_replicate():
        return
    try:
        inv.bReplicates = True
        inv.bReplicateMovement = True
    except Exception:
        pass
    loc = _make_vector(x, y, z)
    rot = _make_rotator(float(pitch), math.degrees(yaw), float(roll))
    _stamp_replicated_movement(inv, loc, rot)


def _pickup_is_floor_decor(inv: Any, *, pool_name: str = "") -> bool:
    """Currency / gift boxes / small pickups belong on the floor ring, not walls/roof."""
    blob = _pickup_type_blob(inv).lower()
    pool_l = str(pool_name or "").strip().lower()
    if any(
        k in blob or k in pool_l
        for k in (
            "gift",
            "guntoter",
            "present",
            "currency",
            "cash",
            "eridium",
            "repair_kit",
            "repkit",
            "health_vial",
            "ammo",
        )
    ):
        return True
    try:
        name = str(getattr(inv, "Name", "") or "").lower()
    except Exception:
        name = ""
    return any(k in name for k in ("gift", "present", "currency", "guntoter"))


def _floor_slots_for_shape() -> list[tuple[float, float, float]]:
    """Lowest slots in the active silhouette — floor ring for presents/currency."""
    if not _drop_plan:
        return []
    oz = float(_drop_origin[2])
    floor_z = oz + 28.0
    low = sorted(_drop_plan, key=lambda p: (float(p[2]), float(p[0]), float(p[1])))
    out: list[tuple[float, float, float]] = []
    for x, y, z in low:
        if float(z) <= floor_z + 48.0:
            out.append((float(x), float(y), float(z)))
    return out or low[: max(1, min(12, len(low)))]


def _classify_exact_item(inv: Any, *, pool_name: str = "") -> str:
    """Stable key for one pile per exact item (serial, balance path, or pool name)."""
    serial = serial_from_pickup(inv)
    if serial:
        return serial
    pool_key = str(pool_name or "").strip().lower()
    if pool_key:
        return f"pool:{pool_key}"
    text = _pickup_type_blob(inv)
    for pattern in (
        r"(/game/[^\s\"']+balance[^\s\"']*)",
        r"(balance_[a-z0-9_]+)",
        r"(inv_[a-z0-9_]+)",
        r"(itempool_[a-z0-9_]+)",
        r"(datatable_[a-z0-9_]+)",
    ):
        hit = re.search(pattern, text, re.I)
        if hit:
            return hit.group(1).lower()
    gtype = _classify_gear_type(inv)
    tokens = re.findall(r"[a-z][a-z0-9_]{4,}", text)
    stem = ""
    for token in tokens:
        low = token.lower()
        if low in ("inventorypickup", "oakinventory", "default", "pickup", "none"):
            continue
        stem = low[:48]
        break
    if not stem:
        try:
            stem = str(getattr(inv, "Name", "") or "").lower()[:32]
        except Exception:
            stem = ""
    return f"{gtype}:{stem}" if stem else gtype


_CAR_WHEEL_TYPES = frozenset({"pistol", "smg"})


def _pool_is_car_wheel(pool_name: str) -> bool:
    low = str(pool_name or "").lower()
    return "_ps_" in low or "_sm_" in low or "pistol" in low or "_smg" in low


def _inv_is_car_wheel(inv: Any = None, pool_name: str = "") -> bool:
    if pool_name and _pool_is_car_wheel(pool_name):
        return True
    if inv is not None:
        return _classify_gear_type(inv) in _CAR_WHEEL_TYPES
    return False


def _car_take_part_slot(*, inv: Any = None, pool_name: str = "") -> tuple[float, float, float] | None:
    """Pistols/SMGs fill tires first; everything else stays on the chassis."""
    wheels = _drop_part_plans.get("car_wheel") or []
    body = _drop_part_plans.get("car_body") or []
    if not wheels and not body:
        return None
    if _inv_is_car_wheel(inv, pool_name):
        n = int(_drop_type_counts.get("car_wheel", 0))
        if n < len(wheels):
            _drop_type_counts["car_wheel"] = n + 1
            return wheels[n]
    n = int(_drop_type_counts.get("car_body", 0))
    if n < len(body):
        _drop_type_counts["car_body"] = n + 1
        return body[n]
    n = int(_drop_type_counts.get("car_wheel", 0))
    if n < len(wheels):
        _drop_type_counts["car_wheel"] = n + 1
        return wheels[n]
    return None


def _classify_rarity(inv: Any) -> str:
    text = _pickup_type_blob(inv)
    comp = _RARITY_COMP_RE.search(text)
    if comp:
        mapped = _RARITY_FROM_COMP.get(comp.group(1))
        if mapped:
            return mapped
    if any(k in text for k in ("pearlescent", "pearl", "shiny", "_06_pearl")):
        return "pearl"
    if any(k in text for k in ("legendary", "_05_legendary")):
        return "legendary"
    if "epic" in text or re.search(r"\bpurple\b", text):
        return "epic"
    if re.search(r"\brare\b", text) or re.search(r"\bblue\b", text):
        return "rare"
    if "uncommon" in text or re.search(r"\bgreen\b", text):
        return "uncommon"
    if "common" in text or re.search(r"\bwhite\b", text):
        return "common"
    return "other"


def sorted_ground_loot(*, include_consumables: bool = False) -> dict[str, list[Any]]:
    loot: dict[str, list[Any]] = {"Pickups": [], "Gear": []}
    skip = _iotd_pickups()
    skip_addrs = {_uobject_addr(inv) for inv in skip}
    skip_addrs.discard(0)
    pickups: list[Any] = []
    seen_loot: set[int] = set()
    for cls in ("InventoryPickup", "OakInventoryPickup", "OakPickup"):
        try:
            found = list(unrealsdk.find_all(cls, False) or [])
        except Exception:
            continue
        for inv in found:
            addr = _uobject_addr(inv)
            if not addr or addr in seen_loot or addr in skip_addrs:
                continue
            seen_loot.add(addr)
            pickups.append(inv)
    if not pickups:
        return loot
    for inv in pickups:
        try:
            if not _live(inv):
                continue
            cls = getattr(inv, "Class", None)
            cdo = getattr(cls, "ClassDefaultObject", None) if cls is not None else None
            if cdo is not None and inv == cdo:
                continue
            root = getattr(inv, "RootPrimitiveComponent", None)
            if not root:
                continue
            body_obj = getattr(inv, "BodyData", None)
            if isinstance(body_obj, str):
                body = body_obj
            elif body_obj is None:
                body = ""
            else:
                body = " ".join(
                    str(getattr(body_obj, attr, "") or "")
                    for attr in ("Name", "PathName", "ObjectPath")
                )
            if "Pickups" in body:
                if include_consumables:
                    loot["Pickups"].append(inv)
                continue
            if not getattr(inv, "BodyData", None):
                usable = False
                try:
                    count = int(root.GetNumMaterials())
                except Exception:
                    count = 0
                for index in range(count):
                    try:
                        material = root.GetMaterial(index)
                    except Exception:
                        material = None
                    if not material:
                        continue
                    name = str(getattr(material, "Name", "") or "")
                    if any(tag in name for tag in _PICKUP_MATERIALS):
                        usable = True
                        break
                if usable:
                    if include_consumables:
                        loot["Pickups"].append(inv)
                    continue
            loot["Gear"].append(inv)
        except Exception:
            continue
    return loot


# --- shape math ---------------------------------------------------------------

def _yaw_basis(yaw: float) -> tuple[float, float, float, float]:
    fx, fy = math.cos(yaw), math.sin(yaw)
    rx, ry = -math.sin(yaw), math.cos(yaw)
    return fx, fy, rx, ry


def _world_from_local(
    ox: float,
    oy: float,
    oz: float,
    yaw: float,
    lx: float,
    ly: float,
    lz: float = 0.0,
) -> tuple[float, float, float]:
    fx, fy, rx, ry = _yaw_basis(yaw)
    return (
        ox + fx * lx + rx * ly,
        oy + fy * lx + ry * ly,
        oz + lz,
    )


def _world_to_local(
    ox: float,
    oy: float,
    oz: float,
    yaw: float,
    x: float,
    y: float,
    z: float,
) -> tuple[float, float, float]:
    fx, fy, rx, ry = _yaw_basis(yaw)
    dx, dy, dz = x - ox, y - oy, z - oz
    return (dx * fx + dy * fy, dx * rx + dy * ry, dz)


def shape_pretty_name(name: str) -> str:
    raw = str(name or "").strip()
    return SHAPE_LABELS.get(raw, raw.replace("_", " "))


def _normalize_shape_name(shape: str) -> str:
    raw = str(shape or "circle").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "ring": "circle",
        "s": "letter_s",
        "double": "double_ring",
        "double_rings": "double_ring",
        "star_fill": "star_filled",
        "filled_star": "star_filled",
        "rectangle": "square",
        "inventory_wall": "rows",
        "wall": "rows",
        "semicircle": "arc",
        "semi_circle": "arc",
        "x": "x_mark",
        "xmark": "x_mark",
        "infinity_symbol": "infinity",
        "figure_8": "figure8",
        "sine": "wave",
        "sine_wave": "wave",
        "bolt": "lightning",
        "vault_symbol": "vault",
        "vault_logo": "vault",
        "bandit_mask": "psycho",
        "bl": "circle",
        "bl_logo": "circle",
        "initials": "circle",
        "gearbox": "house",
        "gbx": "house",
        "gearbox_logo": "house",
        "world_globe": "globe",
        "earth": "globe",
        "triangle": "pyramid",
        "hex": "hexagon",
        "random": "scatter",
        "random_scatter": "scatter",
        "poisson_scatter": "poisson",
        "rarity": "rarity_lanes",
        "unique": "unique_piles",
        "item_piles": "unique_piles",
        "exact_piles": "unique_piles",
        "firehawk_symbol": "firehawk",
        "cottage": "house",
        "home": "house",
        "ship": "boat",
        "vehicle": "car",
        "hemisphere": "dome",
        "igloo": "dome",
        "dna": "dna_helix",
        "helix": "dna_helix",
        "double_helix": "dna_helix",
        "clap_trap": "claptrap",
        "cl4p_tp": "claptrap",
        "3d_pyramid": "pyramid_3d",
        "tetrahedron": "pyramid_3d",
        "square_pyramid": "pyramid_3d",
        "psycho_face": "psycho",
        "psycho_mask": "psycho",
        "mask_3d": "psycho",
        "3d_psycho": "psycho",
        "3d_diamond": "diamond_3d",
        "octahedron": "diamond_3d",
        "gem": "diamond_3d",
        "diamond_gem": "diamond_3d",
        "minecraft": "blocks",
        "minecraft_blocks": "blocks",
        "voxel_blocks": "blocks",
        "dirt_blocks": "blocks",
        "block_stack": "blocks",
        "box": "cube",
        "donut": "torus",
        "doughnut": "torus",
        "ring_torus": "torus",
        "tiara": "crown",
        "flying_saucer": "ufo",
        "text_shape": "text",
        "words": "text",
        "word": "text",
        "write": "text",
        "loot_text": "text",
        "saucer": "ufo",
        "missile": "rocket",
        "cog": "gear",
        "cogwheel": "gear",
        "the_forbidden_one": "forbidden_one",
        "the_forbidden_pair": "forbidden_pair",
        "boom": "nova",
        "lootbomb": "nova",
        "loot_bomb": "nova",
        "bigbang": "nova",
        "big_bang": "nova",
        "singularity": "nova",
        "explosion": "nova",
        "explode": "nova",
        "pulse": "nova",
        "loot_pulse": "nova",
    }
    return aliases.get(raw, raw)


def hidden_shapes_unlocked() -> bool:
    """True after the EXE easter-egg combo writes LOCALAPPDATA/Squ1ggsBoostingTools/watcha.json."""
    try:
        raw = os.environ.get("LOCALAPPDATA") or ""
        if not raw:
            return False
        path = Path(raw) / "Squ1ggsBoostingTools" / "watcha.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return bool(data.get("unlocked"))
    except Exception:
        return False


def visible_shape_names() -> list[str]:
    unlock = hidden_shapes_unlocked()
    # "text" is its own Shapes section (Spell a word), not the normal Shape dropdown.
    return [
        name
        for name in SHAPE_NAMES
        if name != "text" and (unlock or name not in SHAPE_HIDDEN_3D_NAMES)
    ]


# ---------------------------------------------------------------------------
# Loot text silhouette (EXE Shapes → Loot text — same idea as World text props)
# ---------------------------------------------------------------------------
_SHAPE_TEXT_MAX = 12  # per line
_SHAPE_TEXT_MAX_ROWS = 3
_shape_text: str = ""
_text_distance: float = 640.0
_text_height: float = 670.0
# Spacing ≈ cell gap — guns + nameplates need room or "360" becomes an orange wall.
_text_spacing: float = 56.0
_text_scale: float = 1.0
_text_rows: tuple[str, str, str] = ("", "", "")
# X half-step only (Y densify made strokes too thick / unreadable).
_TEXT_CELL_DENSIFY: float = 0.5

# 5x7 bitmap glyphs (rows top→bottom). 1 = filled cell.
_FONT_5X7: dict[str, tuple[str, ...]] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10001", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10001", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
}


def sanitize_shape_text(raw: Any) -> str:
    """Uppercase A-Z / 0-9 / space / .!?- only, max chars for one line or joined rows."""
    text = str(raw or "").upper()
    out: list[str] = []
    for ch in text:
        if ch in _FONT_5X7 or ch == " ":
            out.append(ch)
        if len(out) >= max(_SHAPE_TEXT_MAX * _SHAPE_TEXT_MAX_ROWS + 2, 24):
            break
    cleaned = " ".join("".join(out).split())
    return cleaned[: max(_SHAPE_TEXT_MAX * _SHAPE_TEXT_MAX_ROWS + 2, 24)]


def sanitize_shape_text_line(raw: Any) -> str:
    """One world-text style line (max 12 glyphs)."""
    text = sanitize_shape_text(raw)
    # Prefer first token/line only for per-row fields.
    if " " in text and len(text) > _SHAPE_TEXT_MAX:
        text = text.split(" ", 1)[0]
    return text[:_SHAPE_TEXT_MAX]


def set_text_layout(
    *,
    row1: Any = None,
    row2: Any = None,
    row3: Any = None,
    text: Any = None,
    distance: Any = None,
    height: Any = None,
    spacing: Any = None,
    scale: Any = None,
) -> str:
    """Apply world-text style layout knobs. Returns joined display text."""
    global _shape_text, _text_distance, _text_height, _text_spacing, _text_scale, _text_rows
    r1 = sanitize_shape_text_line(row1) if row1 is not None else _text_rows[0]
    r2 = sanitize_shape_text_line(row2) if row2 is not None else _text_rows[1]
    r3 = sanitize_shape_text_line(row3) if row3 is not None else _text_rows[2]
    if text is not None and not (r1 or r2 or r3):
        # Legacy single field: spaces → up to 3 rows.
        joined = sanitize_shape_text(text)
        parts = [p for p in joined.split(" ") if p][:_SHAPE_TEXT_MAX_ROWS]
        while len(parts) < 3:
            parts.append("")
        r1, r2, r3 = parts[0][:_SHAPE_TEXT_MAX], parts[1][:_SHAPE_TEXT_MAX], parts[2][:_SHAPE_TEXT_MAX]
    _text_rows = (r1, r2, r3)
    _shape_text = " ".join(p for p in _text_rows if p)
    if distance is not None:
        try:
            _text_distance = max(200.0, min(2000.0, float(distance)))
        except Exception:
            pass
    if height is not None:
        try:
            _text_height = max(40.0, min(800.0, float(height)))
        except Exception:
            pass
    if spacing is not None:
        try:
            _text_spacing = max(28.0, min(120.0, float(spacing)))
        except Exception:
            pass
    if scale is not None:
        try:
            _text_scale = max(0.35, min(2.5, float(scale)))
        except Exception:
            pass
    return _shape_text


def set_shape_text(raw: Any) -> str:
    """Legacy single-string entry → up to 3 spaced rows.

    If Line 1–3 are already set and `raw` is only their joined form, keep the
    rows (do not re-split multi-word lines like "HELLO WORLD" on one line).
    """
    joined = sanitize_shape_text(raw)
    current = sanitize_shape_text(get_shape_text())
    if joined and joined == current and any(_text_rows):
        return _shape_text
    parts = [p for p in joined.split(" ") if p][:_SHAPE_TEXT_MAX_ROWS]
    while len(parts) < 3:
        parts.append("")
    return set_text_layout(row1=parts[0], row2=parts[1], row3=parts[2])


def get_shape_text() -> str:
    return str(_shape_text or "")


def get_text_layout() -> dict[str, Any]:
    return {
        "row1": _text_rows[0],
        "row2": _text_rows[1],
        "row3": _text_rows[2],
        "text": _shape_text,
        "distance": float(_text_distance),
        "height": float(_text_height),
        "spacing": float(_text_spacing),
        "scale": float(_text_scale),
    }


def clear_shape_text() -> None:
    global _shape_text, _text_rows
    _shape_text = ""
    _text_rows = ("", "", "")


def text_shape_pixel_count(text: str | None = None) -> int:
    if text is not None:
        rows = [p for p in sanitize_shape_text(text).split(" ") if p][:_SHAPE_TEXT_MAX_ROWS]
    else:
        rows = [p for p in _text_rows if p]
    total = 0
    densify = float(_TEXT_CELL_DENSIFY) > 0.05
    for word in rows:
        for ch in word:
            if ch == " ":
                continue
            glyph = _FONT_5X7.get(ch) or _FONT_5X7["?"]
            cells = sum(row.count("1") for row in glyph)
            # Primary + optional X half-step densify.
            total += cells * (2 if densify else 1)
    return int(total)


def text_shape_slot_count(text: str | None = None, *, profile: str = "shiny") -> int:
    """Guns needed for readable lettering (includes densify extras)."""
    pixels = text_shape_pixel_count(text)
    if pixels <= 0:
        return 0
    _ = profile
    return max(24, min(400, int(pixels)))


def _glyph_cells(ch: str) -> list[tuple[int, int]]:
    """(col, row) filled cells for one character. Row 0 = top."""
    if ch == " ":
        return []
    glyph = _FONT_5X7.get(ch) or _FONT_5X7["?"]
    cells: list[tuple[int, int]] = []
    for row_i, row in enumerate(glyph):
        for col_i, bit in enumerate(row):
            if bit == "1":
                cells.append((col_i, row_i))
    return cells


def _glyph_plot_cells(ch: str) -> list[tuple[float, float]]:
    """Filled glyph samples; X densify thickens strokes without vertical mush."""
    out: list[tuple[float, float]] = []
    step = float(_TEXT_CELL_DENSIFY)
    for col, row in _glyph_cells(ch):
        out.append((float(col), float(row)))
        if step > 0.05:
            out.append((float(col) + step, float(row)))
    return out


_land_layout_profile: str = "shiny"


def _offsets_text(
    n: int,
    radius: float,
    spacing: float = _DEFAULT_SPACING,
    text: str | None = None,
    *,
    profile: str | None = None,
) -> list[tuple[float, float, float]]:
    """Standing world-style loot text: up to 3 centered rows in front of the player."""
    _ = profile
    _ = radius
    if text is not None:
        words = [p for p in sanitize_shape_text(text).split(" ") if p][:_SHAPE_TEXT_MAX_ROWS]
    else:
        words = [p for p in _text_rows if p]
    if not words:
        return _offsets_circle(n, max(120.0, float(radius)))
    # Extra gap between letters so 3 / 6 / 0 read as separate glyphs.
    letter_advance = 10.0
    row_pitch = 9.5
    units: list[tuple[float, float, float]] = []
    for word_i, word in enumerate(words):
        cursor = 0.0
        # Top row highest (world text stacks downward).
        base_u = float((len(words) - 1 - word_i) * row_pitch)
        for ch in word:
            for col, row in _glyph_plot_cells(ch):
                units.append((0.0, cursor + float(col), base_u + float(6.0 - row)))
            cursor += letter_advance
    if not units:
        return _offsets_circle(n, max(120.0, float(radius)))
    # Center each row horizontally.
    by_row: dict[int, list[tuple[float, float, float]]] = {}
    for f, r, u in units:
        key = int(round(u / row_pitch))
        by_row.setdefault(key, []).append((f, r, u))
    units = []
    for pts in by_row.values():
        mid = (min(p[1] for p in pts) + max(p[1] for p in pts)) * 0.5
        units.extend((f, r - mid, u) for f, r, u in pts)
    min_r = min(u[1] for u in units)
    max_r = max(u[1] for u in units)
    min_u = min(u[2] for u in units)
    max_u = max(u[2] for u in units)
    mid_r = (min_r + max_r) * 0.5
    mid_u = (min_u + max_u) * 0.5
    ui_space = float(_text_spacing if _text_spacing > 1.0 else spacing)
    pitch = max(40.0, min(78.0, ui_space * float(_text_scale)))
    units_w = max(1.0, max_r - min_r)
    max_w = max(1400.0, min(2800.0, float(_text_distance) * 3.2))
    if units_w * pitch > max_w:
        pitch = max(40.0, max_w / units_w)
    # Slightly taller row spacing so horizontal strokes don't smear into a wall.
    v_pitch = pitch * 1.12
    air_center = float(_text_height)
    base = [
        (
            0.0,
            (r - mid_r) * pitch,
            (u - mid_u) * v_pitch + air_center,
        )
        for _f, r, u in units
    ]
    if n <= 0:
        return []
    if n >= len(base):
        return base
    step = len(base) / float(n)
    return [base[min(len(base) - 1, int(i * step))] for i in range(n)]

_pending_local_dirs: list[tuple[float, float, float]] = []


def shape_offsets(
    shape: str,
    count: int,
    *,
    radius: float = _DEFAULT_RADIUS,
    spacing: float = _DEFAULT_SPACING,
    per_ring: int = _DEFAULT_PER_RING,
    line_length: float = _DEFAULT_LINE_LENGTH,
    land_profile: str = "shiny",
) -> list[tuple[float, float, float]]:
    """Local (forward, right, up) offsets for `count` items."""
    global _pending_local_dirs, _forbidden_pair_globes
    _pending_local_dirs = []
    n = max(0, int(count))
    if n <= 0:
        return []
    shape = _normalize_shape_name(shape)
    clamped = clamp_layout_params(radius=radius, spacing=spacing, per_ring=per_ring, line_length=line_length)
    radius = float(clamped["radius"])
    spacing = float(clamped["spacing"])
    per_ring = int(clamped["per_ring"])
    line_length = float(clamped["line_length"])
    length = line_length
    text_profile = str(land_profile or _land_layout_profile or "shiny").strip().lower()

    dispatch = {
        "star": lambda: _offsets_star(n, radius, spacing),
        "star_filled": lambda: _offsets_star_filled(n, radius),
        "letter_s": lambda: _offsets_letter_s(n, radius, spacing, length),
        "text": lambda: _offsets_text(n, radius, spacing, profile=text_profile),
        "heart": lambda: _offsets_heart(n, radius),
        "line": lambda: _offsets_line(n, spacing, length),
        "grid": lambda: _offsets_grid(n, spacing),
        "spiral": lambda: _offsets_spiral(n, radius, spacing),
        "cross": lambda: _offsets_cross(n, radius, spacing),
        "x_mark": lambda: _offsets_x_mark(n, radius),
        "diamond": lambda: _offsets_diamond(n, radius),
        "circle": lambda: _offsets_circle(n, radius),
        "double_ring": lambda: _offsets_double_ring(n, radius, spacing),
        "arrow": lambda: _offsets_arrow(n, radius, spacing),
        "smiley": lambda: _offsets_smiley(n, radius),
        "square": lambda: _offsets_square(n, radius),
        "rows": lambda: _offsets_rows(n, spacing, per_ring),
        "arc": lambda: _offsets_arc(n, radius),
        "fan": lambda: _offsets_fan(n, radius, spacing),
        "infinity": lambda: _offsets_infinity(n, radius),
        "figure8": lambda: _offsets_figure8(n, radius),
        "wave": lambda: _offsets_wave(n, radius, spacing, length),
        "lightning": lambda: _offsets_lightning(n, radius, spacing, length),
        "vault": lambda: _offsets_vault(n, radius),
        "firehawk": lambda: _offsets_firehawk(n, radius),
        "psycho": lambda: _offsets_psycho(n, radius),
        "pyramid": lambda: _offsets_pyramid(n, spacing),
        "hexagon": lambda: _offsets_hexagon(n, radius),
        "honeycomb": lambda: _offsets_honeycomb(n, spacing),
        "scatter": lambda: _offsets_scatter(n, radius),
        "poisson": lambda: _offsets_poisson(n, radius, spacing),
        "nova": lambda: _offsets_nova(n, radius),
        "type_piles": lambda: _offsets_rings(n, radius, spacing, max(6, per_ring // 2)),
        "unique_piles": lambda: _offsets_rings(n, radius, spacing, max(6, per_ring // 2)),
        "rarity_lanes": lambda: _offsets_rows(n, spacing, max(6, per_ring)),
        "rings": lambda: _offsets_rings(n, radius, spacing, per_ring),
        "house": lambda: _offsets_house(n, radius),
        "boat": lambda: _offsets_boat(n, radius),
        "car": lambda: _offsets_car(n, radius),
        "dome": lambda: _offsets_dome(n, radius),
        "dna_helix": lambda: _offsets_dna_helix(n, radius),
        "claptrap": lambda: _offsets_claptrap(n, radius),
        "pyramid_3d": lambda: _offsets_pyramid_3d(n, radius),
        "globe": lambda: _offsets_globe(n, radius, spacing),
        "diamond_3d": lambda: _offsets_diamond_3d(n, radius),
        "blocks": lambda: _offsets_blocks(n, radius),
        "cube": lambda: _offsets_cube(n, radius),
        "torus": lambda: _offsets_torus(n, radius),
        "crown": lambda: _offsets_crown(n, radius),
        "ufo": lambda: _offsets_ufo(n, radius),
        "rocket": lambda: _offsets_rocket(n, radius),
        "gear": lambda: _offsets_gear(n, radius),
        "forbidden_one": lambda: _offsets_forbidden_one(n, radius),
        "forbidden_pair": lambda: _offsets_forbidden_pair(n, radius),
    }
    maker = dispatch.get(shape)
    if maker is None:
        raw = _offsets_rings(n, radius, spacing, per_ring)
    else:
        raw = maker()
    if shape in (
        "globe",
        "nova",
        "pyramid",
        "pyramid_3d",
        "dome",
        "diamond_3d",
        "blocks",
        "cube",
        "torus",
        "ufo",
        "rocket",
    ):
        raw = _limit_shape_extent(raw)
    elif shape in (
        "line",
        "wave",
        "lightning",
        "letter_s",
        "rows",
        "rarity_lanes",
        "arc",
        "spiral",
    ):
        raw = _limit_shape_extent(raw, max_span=_MAX_LINE_SPAN)
    clearance = 180.0
    if shape in ("firehawk", "psycho", "vault"):
        # Sit further forward than leftover 3D dumps so a new logo is not
        # drawn on top of the previous silhouette.
        clearance = 340.0
    elif shape == "text":
        clearance = max(220.0, float(_text_distance))
    raw = _push_shape_in_front(raw, clearance=clearance)
    if shape == "forbidden_pair" and raw:
        lefts = [p for p in raw if p[1] < 0.0]
        rights = [p for p in raw if p[1] >= 0.0]
        if lefts and rights:

            def _avg(pts: list[tuple[float, float, float]]) -> tuple[float, float, float]:
                k = float(len(pts))
                return (
                    sum(p[0] for p in pts) / k,
                    sum(p[1] for p in pts) / k,
                    sum(p[2] for p in pts) / k,
                )

            _forbidden_pair_globes = (_avg(lefts), _avg(rights))
    if shape in SHAPE_2D_NAMES and shape not in (
        "scatter",
        "poisson",
        "rows",
        "grid",
        "rarity_lanes",
        "type_piles",
        "unique_piles",
        "honeycomb",
    ):
        if len(_pending_local_dirs) != len(raw):
            _pending_local_dirs = _xy_tangents(raw)
    elif _pending_local_dirs and len(_pending_local_dirs) != len(raw):
        _pending_local_dirs = []
    return raw


def _limit_shape_extent(
    offsets: list[tuple[float, float, float]], *, max_span: float = _MAX_SHAPE_SPAN
) -> list[tuple[float, float, float]]:
    """Keep silhouettes in front of the player. Huge globe/pyramid spans froze physics."""
    if not offsets:
        return offsets
    xs = [float(p[0]) for p in offsets]
    ys = [float(p[1]) for p in offsets]
    zs = [float(p[2]) for p in offsets]
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0)
    cap = max(220.0, float(max_span))
    if span <= cap:
        return offsets
    scale = cap / span
    cx = (max(xs) + min(xs)) * 0.5
    cy = (max(ys) + min(ys)) * 0.5
    cz = (max(zs) + min(zs)) * 0.5
    return [
        ((x - cx) * scale + cx, (y - cy) * scale + cy, (z - cz) * scale + cz)
        for x, y, z in offsets
    ]


def _push_shape_in_front(
    offsets: list[tuple[float, float, float]], *, clearance: float = 180.0
) -> list[tuple[float, float, float]]:
    """Keep the whole silhouette in front of the player (star/∞/8 were half behind)."""
    if not offsets:
        return offsets
    min_fwd = min(float(fwd) for fwd, _right, _up in offsets)
    shift = float(clearance) - min_fwd
    if shift <= 1.0:
        return offsets
    return [(float(fwd) + shift, float(right), float(up)) for fwd, right, up in offsets]


def _sample_polyline(
    verts: list[tuple[float, float]],
    n: int,
    *,
    closed: bool = False,
) -> list[tuple[float, float, float]]:
    global _pending_local_dirs
    if n <= 0 or not verts:
        return []
    pts = list(verts)
    if closed and (len(pts) < 2 or pts[0] != pts[-1]):
        pts.append(pts[0])
    if len(pts) == 1:
        x, y = pts[0]
        _pending_local_dirs.extend([(1.0, 0.0, 0.0)] * n)
        return [(x, y, 0.0)] * n
    edge_lens = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
    total = sum(edge_lens) or 1.0
    out: list[tuple[float, float, float]] = []
    for index in range(n):
        t = (index + 0.5) / n * total if closed else (index / max(1, n - 1)) * total
        acc = 0.0
        placed = False
        for i, elen in enumerate(edge_lens):
            if acc + elen >= t or i == len(edge_lens) - 1:
                u = 0.0 if elen <= 1e-6 else min(1.0, max(0.0, (t - acc) / elen))
                x0, y0 = pts[i]
                x1, y1 = pts[i + 1]
                out.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, 0.0))
                _pending_local_dirs.append(_norm3(x1 - x0, y1 - y0, 0.0))
                placed = True
                break
            acc += elen
        if not placed:
            out.append((pts[-1][0], pts[-1][1], 0.0))
            _pending_local_dirs.append((1.0, 0.0, 0.0))
    return out


def _point_in_poly(x: float, y: float, verts: list[tuple[float, float]]) -> bool:
    inside = False
    count = len(verts)
    if count < 3:
        return False
    j = count - 1
    for i in range(count):
        xi, yi = verts[i]
        xj, yj = verts[j]
        if (yi > y) != (yj > y):
            denom = (yj - yi) or 1e-9
            at_x = (xj - xi) * (y - yi) / denom + xi
            if x < at_x:
                inside = not inside
        j = i
    return inside


def _fill_closed_polygon(
    verts: list[tuple[float, float]],
    n: int,
    *,
    outline_frac: float = 0.40,
) -> list[tuple[float, float, float]]:
    """Outline + interior grid so a silhouette reads as a filled shape, not a scribble."""
    if n <= 0 or not verts:
        return []
    n_out = max(6, min(n, int(round(n * max(0.2, min(0.7, outline_frac))))))
    n_fill = max(0, n - n_out)
    out = _sample_polyline(verts, n_out, closed=True)
    if n_fill <= 0:
        return out[:n]
    xs = [float(v[0]) for v in verts]
    ys = [float(v[1]) for v in verts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    span_x = max(1.0, maxx - minx)
    span_y = max(1.0, maxy - miny)
    cells = max(5, int(math.ceil(math.sqrt(n_fill * 2.4))))
    candidates: list[tuple[float, float, float]] = []
    for iy in range(cells):
        for ix in range(cells):
            x = minx + (ix + 0.5) / cells * span_x
            y = miny + (iy + 0.5) / cells * span_y
            if _point_in_poly(x, y, verts):
                candidates.append((x, y, 0.0))
    if len(candidates) < n_fill:
        rng = random.Random(11)
        attempts = 0
        want = n_fill * 2
        while len(candidates) < want and attempts < n_fill * 50:
            attempts += 1
            x = rng.uniform(minx, maxx)
            y = rng.uniform(miny, maxy)
            if _point_in_poly(x, y, verts):
                candidates.append((x, y, 0.0))
    if not candidates:
        return out[:n]
    if len(candidates) > n_fill:
        step = len(candidates) / float(n_fill)
        picked = [candidates[min(len(candidates) - 1, int(i * step))] for i in range(n_fill)]
    else:
        picked = candidates
    return (out + picked)[:n]


def _fill_xz_poly(
    verts_xz: list[tuple[float, float]],
    y: float,
    n: int,
) -> list[tuple[float, float, float]]:
    """Fill a closed (x, z) side-profile at a fixed Y."""
    return [(p[0], float(y), p[1]) for p in _fill_closed_polygon(verts_xz, n)]


def _sample_polylines(paths: list[list[tuple[float, float]]], n: int, *, closed: bool = False) -> list[tuple[float, float, float]]:
    if n <= 0:
        return []
    lengths = []
    for path in paths:
        pts = list(path)
        if closed and pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        length = 0.0
        for i in range(max(0, len(pts) - 1)):
            length += math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        lengths.append(max(length, 1.0))
    total = sum(lengths) or 1.0
    counts = [max(1, int(round(n * (ln / total)))) for ln in lengths]
    while sum(counts) > n and max(counts) > 1:
        counts[counts.index(max(counts))] -= 1
    while sum(counts) < n:
        counts[counts.index(max(lengths))] += 1
    out: list[tuple[float, float, float]] = []
    for path, count in zip(paths, counts):
        out.extend(_sample_polyline(path, count, closed=closed))
    return out[:n]


def _offsets_rings(n: int, radius: float, spacing: float, per_ring: int) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    for index in range(n):
        ring = index // per_ring
        slot = index % per_ring
        angle = (2.0 * math.pi / per_ring) * slot if slot else 0.0
        r = radius + ring * spacing
        out.append((r * math.cos(angle), r * math.sin(angle), 0.0))
    return out


def _offsets_star(n: int, radius: float, spacing: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    points = 5
    # Outer/inner star vertices, then fill remaining along edges.
    verts: list[tuple[float, float]] = []
    for i in range(points * 2):
        ang = -math.pi / 2 + i * math.pi / points
        r = radius if i % 2 == 0 else radius * 0.42
        verts.append((r * math.cos(ang), r * math.sin(ang)))
    # Sample along perimeter
    edge_lens = []
    for i in range(len(verts)):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % len(verts)]
        edge_lens.append(math.hypot(x1 - x0, y1 - y0))
    total = sum(edge_lens) or 1.0
    for index in range(n):
        t = (index + 0.5) / n * total
        acc = 0.0
        for i, elen in enumerate(edge_lens):
            if acc + elen >= t or i == len(edge_lens) - 1:
                u = 0.0 if elen <= 1e-6 else (t - acc) / elen
                x0, y0 = verts[i]
                x1, y1 = verts[(i + 1) % len(verts)]
                # slight radial layers for overflow density
                layer = 1.0 + 0.08 * (index // max(1, points * 4))
                out.append(((x0 + (x1 - x0) * u) * layer, (y0 + (y1 - y0) * u) * layer, 0.0))
                break
            acc += elen
    return out


def _offsets_letter_s(
    n: int, radius: float, spacing: float, line_length: float = _DEFAULT_LINE_LENGTH
) -> list[tuple[float, float, float]]:
    """Continuous letter-S stroke (single sine path) — not two disconnected C halves."""
    h = min(
        max(radius * 1.15, spacing * 2.8),
        max(160.0, float(line_length)),
        float(_MAX_LINE_SPAN),
    )
    w = max(radius * 0.55, spacing * 1.35)
    w = min(w, float(_MAX_LINE_SPAN) * 0.45)
    out: list[tuple[float, float, float]] = []
    for index in range(n):
        t = index / max(1, n - 1) if n > 1 else 0.0
        # Top→bottom with one full sine period: continuous S silhouette.
        # Forward = vertical stem; right = side bulge (top right → mid left → bottom right).
        forward = h * (0.5 - t)
        right = w * math.sin(2.0 * math.pi * t)
        out.append((forward, right, 0.0))
    return out


def _offsets_spiral(n: int, radius: float, spacing: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    turns = max(2.0, n / 18.0)
    for index in range(n):
        t = (index + 0.5) / max(1, n)
        ang = t * turns * 2.0 * math.pi
        r = radius * 0.35 + t * (radius + spacing * 0.8)
        out.append((r * math.cos(ang), r * math.sin(ang), 0.0))
    return out


def _offsets_cross(n: int, radius: float, spacing: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    arm = max(radius, spacing * 2.0)
    # Alternate arms: +F, -F, +R, -R
    for index in range(n):
        arm_i = index % 4
        slot = index // 4
        dist = spacing * 0.55 + slot * spacing * 0.85
        dist = min(dist, arm)
        if arm_i == 0:
            out.append((dist, 0.0, 0.0))
        elif arm_i == 1:
            out.append((-dist, 0.0, 0.0))
        elif arm_i == 2:
            out.append((0.0, dist, 0.0))
        else:
            out.append((0.0, -dist, 0.0))
    return out


def _offsets_diamond(n: int, radius: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    # Diamond perimeter (rhombus) sampled evenly.
    verts = (
        (radius, 0.0),
        (0.0, radius * 0.75),
        (-radius, 0.0),
        (0.0, -radius * 0.75),
    )
    edge_lens = []
    for i in range(4):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % 4]
        edge_lens.append(math.hypot(x1 - x0, y1 - y0))
    total = sum(edge_lens) or 1.0
    for index in range(n):
        t = (index + 0.5) / n * total
        acc = 0.0
        for i, elen in enumerate(edge_lens):
            if acc + elen >= t or i == 3:
                u = 0.0 if elen <= 1e-6 else (t - acc) / elen
                x0, y0 = verts[i]
                x1, y1 = verts[(i + 1) % 4]
                out.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, 0.0))
                break
            acc += elen
    return out


def _offsets_circle(n: int, radius: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    for index in range(n):
        ang = (2.0 * math.pi * index) / max(1, n) - math.pi / 2
        out.append((radius * math.cos(ang), radius * math.sin(ang), 0.0))
    return out


def _offsets_arrow(n: int, radius: float, spacing: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    shaft = max(3, int(n * 0.55))
    head = max(1, n - shaft)
    length = max(radius, spacing * 2.5)
    for index in range(shaft):
        t = index / max(1, shaft - 1) if shaft > 1 else 0.0
        out.append((length * (t - 0.15), 0.0, 0.0))
    tip_f = length * 0.85
    for index in range(head):
        t = index / max(1, head - 1) if head > 1 else 0.5
        # Left and right wings of the arrowhead
        side = -1.0 if index % 2 == 0 else 1.0
        depth = (index // 2) / max(1, (head - 1) // 2 + 1)
        out.append((tip_f - depth * spacing * 1.2, side * (radius * 0.55 - depth * spacing * 0.35), 0.0))
    return out[:n]


def _offsets_smiley(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Face ring + eyes + nose + smile. Mouth/nose are reserved first so `[:n]` cannot drop them."""
    if n <= 0:
        return []
    n_mouth = max(5, min(n, int(round(n * 0.24)) or 5)) if n >= 8 else max(3, min(n, n // 2 or 3))
    n_nose = 1 if n >= 10 else 0
    n_eyes = max(2, int(round(n * 0.18)))
    if n_eyes % 2:
        n_eyes -= 1
    n_eyes = max(2, n_eyes)
    if n_mouth + n_nose + n_eyes > n:
        n_eyes = max(0, n - n_mouth - n_nose)
        if n_eyes % 2:
            n_eyes -= 1
        n_eyes = max(0, n_eyes)
        if n_mouth + n_nose + n_eyes > n:
            n_mouth = max(0, n - n_nose - n_eyes)
    n_face = max(0, n - n_mouth - n_nose - n_eyes)
    out: list[tuple[float, float, float]] = []
    # Mouth / nose / eyes first so a short dump cannot slice them off.
    mouth_r = radius * 0.52
    for index in range(n_mouth):
        t = index / max(1, n_mouth - 1)
        theta = math.pi - 0.72 + t * 1.44
        out.append((mouth_r * math.cos(theta), mouth_r * math.sin(theta), 0.0))
    if n_nose:
        out.append((radius * 0.06, 0.0, 0.0))
    if n_eyes:
        per_eye = max(1, n_eyes // 2)
        eye_r = radius * 0.11
        placed_eyes = 0
        for eye_x, eye_y in ((radius * 0.32, -radius * 0.28), (radius * 0.32, radius * 0.28)):
            for index in range(per_eye):
                if placed_eyes >= n_eyes:
                    break
                ang = (2.0 * math.pi * index) / max(1, per_eye)
                out.append((eye_x + eye_r * math.cos(ang), eye_y + eye_r * math.sin(ang), 0.0))
                placed_eyes += 1
    for index in range(n_face):
        ang = (2.0 * math.pi * index) / max(1, n_face) - math.pi / 2
        out.append((radius * math.cos(ang), radius * math.sin(ang), 0.0))
    out = out[:n]
    global _pending_local_dirs
    _pending_local_dirs = _xy_tangents(out)
    return out


def _xy_tangents(points: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """Barrel along the ground stroke so long guns cover the line instead of punching holes."""
    if not points:
        return []
    n = len(points)
    if n == 1:
        return [(1.0, 0.0, 0.0)]
    dirs: list[tuple[float, float, float]] = []
    for i, (x, y, _z) in enumerate(points):
        if i + 1 < n:
            nx, ny, _nz = points[i + 1]
        else:
            nx, ny, _nz = points[i - 1]
            x, y, nx, ny = nx, ny, x, y
        dirs.append(_norm3(nx - x, ny - y, 0.0))
    return dirs


def _sample_polyline_3d(
    verts: list[tuple[float, float, float]],
    n: int,
) -> list[tuple[float, float, float]]:
    if n <= 0 or not verts:
        return []
    if len(verts) == 1:
        return [verts[0]] * n
    edge_lens = [
        math.sqrt(
            (verts[i + 1][0] - verts[i][0]) ** 2
            + (verts[i + 1][1] - verts[i][1]) ** 2
            + (verts[i + 1][2] - verts[i][2]) ** 2
        )
        for i in range(len(verts) - 1)
    ]
    total = sum(edge_lens) or 1.0
    out: list[tuple[float, float, float]] = []
    for index in range(n):
        t = (index / max(1, n - 1)) * total
        acc = 0.0
        placed = False
        for i, elen in enumerate(edge_lens):
            if acc + elen >= t or i == len(edge_lens) - 1:
                u = 0.0 if elen <= 1e-6 else min(1.0, max(0.0, (t - acc) / elen))
                a, b = verts[i], verts[i + 1]
                out.append(
                    (
                        a[0] + (b[0] - a[0]) * u,
                        a[1] + (b[1] - a[1]) * u,
                        a[2] + (b[2] - a[2]) * u,
                    )
                )
                placed = True
                break
            acc += elen
        if not placed:
            out.append(verts[-1])
    return out


def _norm3(dx: float, dy: float, dz: float) -> tuple[float, float, float]:
    length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    return (dx / length, dy / length, dz / length)


def _oriented_polyline(
    verts: list[tuple[float, float, float]],
    n: int,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Sample a 3D polyline and keep the stroke direction so guns can lie along it."""
    if n <= 0 or not verts:
        return []
    if len(verts) == 1:
        return [(verts[0], (1.0, 0.0, 0.0))] * n
    edge_lens = [
        math.sqrt(
            (verts[i + 1][0] - verts[i][0]) ** 2
            + (verts[i + 1][1] - verts[i][1]) ** 2
            + (verts[i + 1][2] - verts[i][2]) ** 2
        )
        for i in range(len(verts) - 1)
    ]
    edge_dirs = [
        _norm3(
            verts[i + 1][0] - verts[i][0],
            verts[i + 1][1] - verts[i][1],
            verts[i + 1][2] - verts[i][2],
        )
        for i in range(len(verts) - 1)
    ]
    total = sum(edge_lens) or 1.0
    out: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for index in range(n):
        t = (index / max(1, n - 1)) * total
        acc = 0.0
        placed = False
        for i, elen in enumerate(edge_lens):
            if acc + elen >= t or i == len(edge_lens) - 1:
                u = 0.0 if elen <= 1e-6 else min(1.0, max(0.0, (t - acc) / elen))
                a, b = verts[i], verts[i + 1]
                pt = (
                    a[0] + (b[0] - a[0]) * u,
                    a[1] + (b[1] - a[1]) * u,
                    a[2] + (b[2] - a[2]) * u,
                )
                out.append((pt, edge_dirs[i]))
                placed = True
                break
            acc += elen
        if not placed:
            out.append((verts[-1], edge_dirs[-1] if edge_dirs else (1.0, 0.0, 0.0)))
    return out


def _lift_oriented(
    rows: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    *,
    pad: float = _SHAPE_LIFT_PAD,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    if not rows:
        return []
    pts = _lift_above_ground([p for p, _d in rows], pad=pad)
    return [(pts[i], rows[i][1]) for i in range(len(rows))]


def _commit_oriented(
    rows: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    n: int,
) -> list[tuple[float, float, float]]:
    """Store stroke dirs for this silhouette, then return the points."""
    global _pending_local_dirs
    rows = rows[: max(0, int(n))]
    _pending_local_dirs = [d for _p, d in rows]
    return [p for p, _d in rows]


def _yaw_pitch_along(dx: float, dy: float, dz: float) -> tuple[float, float, float]:
    """Point the barrel along a local stroke. Horizontals stay flat; up-edges pitch, they do not all stand."""
    yaw0 = float(_drop_yaw)
    horiz = math.hypot(dx, dy)
    if horiz < 1e-5:
        return yaw0, 90.0 if dz >= 0.0 else -90.0, 0.0
    return yaw0 + math.atan2(dy, dx), math.degrees(math.atan2(dz, horiz)), 0.0


def _take_n_points(
    points: list[tuple[float, float, float]],
    n: int,
) -> list[tuple[float, float, float]]:
    if n <= 0:
        return []
    if not points:
        return [(0.0, 0.0, 0.0)] * n
    if len(points) == n:
        return list(points)
    if len(points) < n:
        extra = _sample_polyline_3d(points, n - len(points)) if len(points) > 1 else [points[0]] * (n - len(points))
        return (points + extra)[:n]
    out: list[tuple[float, float, float]] = []
    last = max(1, len(points) - 1)
    for i in range(n):
        out.append(points[int(round(i * last / max(1, n - 1)))])
    return out


def _lerp3(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    u: float,
) -> tuple[float, float, float]:
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u)


def _interleave_lists(
    groups: list[list[tuple[float, float, float]]],
    n: int,
) -> list[tuple[float, float, float]]:
    """Round-robin points from several strokes so a logo fills as a whole, not one side first."""
    out: list[tuple[float, float, float]] = []
    if n <= 0 or not groups:
        return out
    live = [list(g) for g in groups if g]
    i = 0
    while len(out) < n:
        progressed = False
        for g in live:
            if i < len(g):
                out.append(g[i])
                progressed = True
                if len(out) >= n:
                    break
        if not progressed:
            break
        i += 1
    return out[:n]


def _fill_tri_3d(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
    n: int,
) -> list[tuple[float, float, float]]:
    if n <= 0:
        return []
    out: list[tuple[float, float, float]] = []
    cols = max(2, int(math.ceil(math.sqrt(n * 2))))
    for i in range(n):
        row, col = divmod(i, cols)
        u = col / max(1, cols - 1)
        v = row / max(1, cols - 1)
        if u + v > 1.0:
            u, v = 1.0 - u, 1.0 - v
        w = max(0.0, 1.0 - u - v)
        out.append(
            (
                a[0] * w + b[0] * u + c[0] * v,
                a[1] * w + b[1] * u + c[1] * v,
                a[2] * w + b[2] * u + c[2] * v,
            )
        )
    return out


def _box_wire_3d(
    x0: float,
    y0: float,
    z0: float,
    x1: float,
    y1: float,
    z1: float,
    n: int,
) -> list[tuple[float, float, float]]:
    corners = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    edges = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]
    if n <= 0:
        return []
    per = max(2, n // len(edges))
    extra = n - per * len(edges)
    out: list[tuple[float, float, float]] = []
    for i, (a, b) in enumerate(edges):
        count = per + (1 if i < extra else 0)
        out.extend(_sample_polyline_3d([corners[a], corners[b]], count))
    return out[:n]


def _fill_quad_3d(
    corners: list[tuple[float, float, float]],
    n: int,
) -> list[tuple[float, float, float]]:
    """Bilinear fill of a quad so roofs/panels are a surface, not just an outline."""
    if n <= 0 or len(corners) < 4:
        return []
    a, b, c, d = corners[0], corners[1], corners[2], corners[3]
    cols = max(2, int(math.ceil(math.sqrt(n))))
    rows = max(2, int(math.ceil(n / cols)))
    out: list[tuple[float, float, float]] = []
    for i in range(n):
        row, col = divmod(i, cols)
        u = col / max(1, cols - 1)
        v = row / max(1, rows - 1)
        ab = _lerp3(a, b, u)
        dc = _lerp3(d, c, u)
        out.append(_lerp3(ab, dc, v))
    return out


def _ring_3d(
    cx: float,
    cy: float,
    cz: float,
    ax: float,
    ay: float,
    az: float,
    bx: float,
    by: float,
    bz: float,
    n: int,
) -> list[tuple[float, float, float]]:
    """Circle at c spanning radius vectors a and b."""
    if n <= 0:
        return []
    out: list[tuple[float, float, float]] = []
    for i in range(n):
        ang = (2.0 * math.pi * i) / n
        ca, sa = math.cos(ang), math.sin(ang)
        out.append((cx + ax * ca + bx * sa, cy + ay * ca + by * sa, cz + az * ca + bz * sa))
    return out


def _split_counts(total: int, buckets: int) -> list[int]:
    """Exact non-negative split so the last bucket is never dropped."""
    k = max(1, int(buckets))
    n = max(0, int(total))
    base = n // k
    extra = n - base * k
    return [base + (1 if i < extra else 0) for i in range(k)]


def _teardrop_shell(
    cx: float,
    cy: float,
    cz: float,
    rx: float,
    ry: float,
    rz: float,
    n: int,
    *,
    front_bias: float = 0.55,
) -> list[tuple[float, float, float]]:
    """Pear / breast: wider at the bottom, more projection toward the player."""
    if n <= 0:
        return []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    out: list[tuple[float, float, float]] = []
    for i in range(n):
        t = (i + 0.5) / n
        z = 1.0 - 2.0 * t
        rxy = math.sqrt(max(0.0, 1.0 - z * z))
        ang = i * golden
        # Bottom (z < 0) is fuller; top tapers.
        taper = 0.58 + 0.42 * (0.5 - 0.5 * z)
        fwd = rx * rxy * math.cos(ang) * taper
        right = ry * rxy * math.sin(ang) * taper
        up = rz * z
        if front_bias > 0.0:
            # Pull the facing hemisphere toward the player (negative forward).
            facing = max(0.0, -math.cos(ang))
            fwd = fwd - rx * front_bias * facing * (0.35 + 0.25 * taper)
        out.append((cx + fwd, cy + right, cz + up))
    return out


def _oriented_from_pts(
    pts: list[tuple[float, float, float]],
    direction: tuple[float, float, float],
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    return [(p, direction) for p in pts]


def _offsets_house(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Cottage: short dumps stay a wireframe; Spawn All fills floor, walls, and both roof slopes."""
    n = max(0, int(n))
    if n <= 0:
        return []
    r = min(max(110.0, float(radius)), 280.0)
    d = max(95.0, r * 0.98)
    w = max(72.0, r * 0.80)
    shiny = n <= 180
    wall_h = max(80.0, r * 0.58)
    roof_h = max(48.0, r * 0.38)
    peak_z = wall_h + roof_h
    ridge_back = (-d, 0.0, peak_z)
    ridge_front = (d, 0.0, peak_z)
    eave_bl = (-d, -w, wall_h)
    eave_fl = (d, -w, wall_h)
    eave_fr = (d, w, wall_h)
    eave_br = (-d, w, wall_h)
    near = -d
    door_w = w * 0.32
    door_h = wall_h * 0.78
    door = _oriented_polyline(
        [
            (near, -door_w, 0.0),
            (near, -door_w, door_h),
            (near, door_w, door_h),
            (near, door_w, 0.0),
            (near, -door_w, 0.0),
        ],
        max(10, int(round(n * (0.16 if shiny else 0.08)))),
    )
    corners = [(-d, -w), (d, -w), (d, w), (-d, w)]
    if shiny:
        # Outline first (door/posts/eaves/ridge), then roof, then walls, then floor —
        # so a short shiny dump still reads as a house with a roof.
        n_posts = max(8, int(round(n * 0.10)))
        n_roof = max(14, int(round(n * 0.30)))
        n_walls = max(12, int(round(n * 0.20)))
        n_floor = max(10, int(round(n * 0.16)))
        used = len(door) + n_floor + n_walls + n_roof + n_posts
        if used > n:
            cut = used - n
            n_floor = max(6, n_floor - cut)
            used = len(door) + n_floor + n_walls + n_roof + n_posts
            if used > n:
                n_walls = max(8, n_walls - (used - n))
        post_counts = _split_counts(n_posts, 4)
        posts: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
        for count, (px, py) in zip(post_counts, corners):
            if count:
                posts.extend(_oriented_polyline([(px, py, 0.0), (px, py, wall_h)], count))
        eaves = _oriented_polyline([eave_bl, eave_fl, eave_fr, eave_br, eave_bl], max(8, n_walls // 3))
        n_ridge = max(4, n_roof // 5)
        n_gables = max(6, n_roof // 4)
        n_slopes = max(0, n_roof - n_ridge - n_gables)
        n_left = n_slopes // 2
        n_right = n_slopes - n_left
        n_gf = n_gables // 2
        n_gb = n_gables - n_gf
        roof = (
            _oriented_polyline([ridge_back, ridge_front], n_ridge)
            + _oriented_polyline([eave_bl, ridge_back], max(2, n_left // 2) if n_left else 0)
            + _oriented_polyline([eave_fl, ridge_front], max(2, n_left - n_left // 2) if n_left else 0)
            + _oriented_polyline([eave_br, ridge_back], max(2, n_right // 2) if n_right else 0)
            + _oriented_polyline([eave_fr, ridge_front], max(2, n_right - n_right // 2) if n_right else 0)
            + _oriented_polyline([eave_fl, ridge_front, eave_fr], n_gf)
            + _oriented_polyline([eave_bl, ridge_back, eave_br], n_gb)
        )
        wall_budget = max(0, n_walls - len(eaves))
        wall_loops = [
            [(-d, -w, 0.0), (d, -w, 0.0), (d, -w, wall_h), (-d, -w, wall_h), (-d, -w, 0.0)],
            [(-d, w, 0.0), (d, w, 0.0), (d, w, wall_h), (-d, w, wall_h), (-d, w, 0.0)],
            [(d, -w, 0.0), (d, -w, wall_h), (d, w, wall_h), (d, w, 0.0)],
        ]
        wall_counts = _split_counts(wall_budget, len(wall_loops))
        walls: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
        for count, loop in zip(wall_counts, wall_loops):
            if count:
                walls.extend(_oriented_polyline(loop, count))
        floor = _oriented_polyline(
            [(-d, -w, 0.0), (d, -w, 0.0), (d, w, 0.0), (-d, w, 0.0), (-d, -w, 0.0)],
            n_floor,
        )
        rows = _lift_oriented(door + posts + eaves + roof + walls + floor, pad=36.0)
        return _commit_oriented(rows, n)

    # Spawn All: build the complete readable wireframe first. Only later drops
    # fill floor/wall/roof panels, so a short or partially failed batch still
    # looks like a house rather than disconnected filled patches.
    door_frame = _oriented_polyline(
        [
            (near, -door_w, 0.0),
            (near, -door_w, door_h),
            (near, door_w, door_h),
            (near, door_w, 0.0),
        ],
        14,
    )
    foundation = _oriented_polyline(
        [(-d, -w, 0.0), (d, -w, 0.0), (d, w, 0.0), (-d, w, 0.0), (-d, -w, 0.0)],
        20,
    )
    eaves = _oriented_polyline(
        [eave_bl, eave_fl, eave_fr, eave_br, eave_bl],
        18,
    )
    posts = []
    for px, py in corners:
        posts.extend(_oriented_polyline([(px, py, 0.0), (px, py, wall_h)], 5))
    roof_edges = (
        _oriented_polyline([ridge_back, ridge_front], 10)
        + _oriented_polyline([eave_bl, ridge_back], 6)
        + _oriented_polyline([eave_fl, ridge_front], 6)
        + _oriented_polyline([eave_br, ridge_back], 6)
        + _oriented_polyline([eave_fr, ridge_front], 6)
        + _oriented_polyline([eave_fl, ridge_front, eave_fr], 10)
        + _oriented_polyline([eave_bl, ridge_back, eave_br], 10)
    )
    frame = door_frame + foundation + posts + eaves + roof_edges
    if n <= len(frame):
        return _commit_oriented(_lift_oriented(frame, pad=36.0), n)

    remaining = n - len(frame)
    # Roof panels BEFORE walls/floor — incomplete batches keep a roof, not bare walls.
    n_roof = max(24, int(round(remaining * 0.42)))
    n_walls = max(16, int(round(remaining * 0.30)))
    n_floor = max(12, remaining - n_roof - n_walls)
    n_ridge = max(6, n_roof // 8)
    n_gables = max(8, n_roof // 8)
    n_slopes = max(0, n_roof - n_ridge - n_gables)
    n_left = n_slopes // 2
    n_right = n_slopes - n_left
    n_gf = n_gables // 2
    n_gb = n_gables - n_gf
    roof = (
        _oriented_polyline([ridge_back, ridge_front], n_ridge)
        + _oriented_from_pts(
            _fill_quad_3d([eave_bl, eave_fl, ridge_front, ridge_back], n_left),
            (1.0, 0.35, 0.55),
        )
        + _oriented_from_pts(
            _fill_quad_3d([eave_br, eave_fr, ridge_front, ridge_back], n_right),
            (1.0, -0.35, 0.55),
        )
        + _oriented_polyline([eave_fl, ridge_front, eave_fr], n_gf)
        + _oriented_polyline([eave_bl, ridge_back, eave_br], n_gb)
    )
    wall_panels = [
        ([(-d, -w, 0.0), (d, -w, 0.0), (d, -w, wall_h), (-d, -w, wall_h)], (1.0, 0.0, 0.0)),
        ([(-d, w, 0.0), (d, w, 0.0), (d, w, wall_h), (-d, w, wall_h)], (1.0, 0.0, 0.0)),
        ([(d, -w, 0.0), (d, w, 0.0), (d, w, wall_h), (d, -w, wall_h)], (0.0, 1.0, 0.0)),
    ]
    wall_counts = _split_counts(n_walls, len(wall_panels))
    walls = []
    for count, (quad, direction) in zip(wall_counts, wall_panels):
        if count:
            walls.extend(_oriented_from_pts(_fill_quad_3d(quad, count), direction))
    floor = _oriented_from_pts(
        _fill_quad_3d([(-d, -w, 0.0), (d, -w, 0.0), (d, w, 0.0), (-d, w, 0.0)], n_floor),
        (1.0, 0.0, 0.0),
    )
    rows = _lift_oriented(frame + roof + walls + floor, pad=36.0)
    if len(rows) < n:
        extra = _oriented_from_pts(
            _fill_quad_3d([eave_bl, eave_fr, ridge_front, ridge_back], n - len(rows)),
            (1.0, 0.0, 0.55),
        )
        rows = _lift_oriented(frame + roof + walls + floor + extra, pad=36.0)
    return _commit_oriented(rows, n)


def _offsets_boat(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Small motorboat from the side: pointed bow, hull, cabin, mast. Not a blob."""
    n = max(0, int(n))
    if n <= 0:
        return []
    r = min(max(120.0, float(radius)), 240.0)
    length = max(220.0, min(320.0, r * 1.55))
    beam = max(48.0, r * 0.32)
    hull_h = max(36.0, r * 0.22)
    cabin_h = hull_h * 1.15
    n_hull = max(16, int(round(n * 0.58)))
    n_cabin = max(8, int(round(n * 0.32)))
    n_mast = max(3, n - n_hull - n_cabin)
    # Bow toward the player (-X), same XZ side-profile trick as the car.
    x_bow = -length * 0.50
    x_stern = length * 0.48
    x_cabin_f = -length * 0.06
    x_cabin_r = length * 0.16
    hull_xz = [
        (x_stern, hull_h * 0.35),
        (x_stern, hull_h),
        (x_cabin_r, hull_h),
        (x_cabin_f, hull_h),
        (-length * 0.28, hull_h * 0.85),
        (x_bow, hull_h * 0.22),
        (-length * 0.42, 0.0),
        (0.0, 0.0),
        (x_stern - length * 0.08, 0.0),
        (x_stern, hull_h * 0.35),
    ]
    n_mid = max(10, int(round(n_hull * 0.70)))
    n_side = max(0, n_hull - n_mid)
    hull = _fill_xz_poly(hull_xz, 0.0, n_mid) + _fill_xz_poly(hull_xz, beam * 0.35, n_side // 2)
    if n_side - n_side // 2:
        hull.extend(_fill_xz_poly(hull_xz, -beam * 0.35, n_side - n_side // 2))
    cabin_box = _box_wire_3d(
        x_cabin_f, -beam * 0.28, hull_h, x_cabin_r, beam * 0.28, hull_h + cabin_h, n_cabin
    )
    mast = _sample_polyline_3d(
        [
            (-length * 0.02, 0.0, hull_h + cabin_h),
            (-length * 0.02, 0.0, hull_h + cabin_h + r * 0.55),
            (-length * 0.16, 0.0, hull_h + cabin_h + r * 0.32),
        ],
        n_mast,
    )
    return _lift_above_ground((hull[:n_hull] + cabin_box[:n_cabin] + mast)[:n], pad=28.0)


def _car_part_offsets(
    n: int, radius: float
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """Human-scale side-profile sedan; player stands in the driver seat (cabin)."""
    n = max(0, int(n))
    if n <= 0:
        return [], []
    # Sedan scales with item count — partial shiny drop stays narrower with full wheels.
    fill = min(1.0, max(0.58, math.sqrt(n / 130.0)))
    r = min(max(195.0, float(radius) * 1.06 * fill), 400.0)
    length = max(280.0, min(500.0, r * 1.55 * fill))
    width = max(128.0, min(length * 0.54, r * 0.74 * fill))
    wheel_r = max(24.0, min(38.0, length * 0.095 * max(0.75, fill)))
    z_rocker = wheel_r * 0.58
    z_arch = wheel_r * 2.0
    z_hood = wheel_r + 28.0
    z_roof = z_hood + 26.0
    # Shift so driver seat (mid cabin, left-ish) sits near world origin / player.
    seat_x = length * 0.06
    seat_y = -width * 0.18
    x_nose = length * 0.50 - seat_x
    x_hood = length * 0.16 - seat_x
    x_roof_f = length * 0.02 - seat_x
    x_roof_r = -length * 0.28 - seat_x
    x_trunk = -length * 0.40 - seat_x
    x_tail = -length * 0.50 - seat_x
    x_front = length * 0.28 - seat_x
    x_rear = -length * 0.26 - seat_x
    well = wheel_r * 1.05
    profile = [
        (x_nose, z_rocker),
        (x_nose, z_hood * 0.70),
        (x_hood, z_hood),
        (x_roof_f, z_roof),
        (x_roof_r, z_roof),
        (x_trunk, z_hood * 0.90),
        (x_tail, z_hood * 0.68),
        (x_tail, z_rocker),
        (x_rear + well, z_rocker),
        (x_rear + well * 0.72, z_arch),
        (x_rear, z_arch + 4.0),
        (x_rear - well * 0.72, z_arch),
        (x_rear - well, z_rocker),
        (x_front + well, z_rocker),
        (x_front + well * 0.72, z_arch),
        (x_front, z_arch + 4.0),
        (x_front - well * 0.72, z_arch),
        (x_front - well, z_rocker),
    ]
    y_near, y_far = -width * 0.56 - seat_y, width * 0.56 - seat_y
    hubs = [
        (x_front, y_near, wheel_r * 0.92),
        (x_front, y_far, wheel_r * 0.92),
        (x_rear, y_near, wheel_r * 0.92),
        (x_rear, y_far, wheel_r * 0.92),
    ]
    n_wheel_budget = min(max(12, n // 5), max(4, n - 4))
    n_per_hub = max(3, n_wheel_budget // 4)
    wheels: list[tuple[float, float, float]] = []
    for hx, hy, hz in hubs:
        wheels.extend(
            _ring_3d(hx, hy, hz, 0.0, wheel_r, 0.0, 0.0, 0.0, wheel_r * 0.40, n_per_hub)
        )
    wheels = wheels[:n_wheel_budget]
    n_body = max(0, n - len(wheels))
    if n_body > 0:
        bands = (-0.42, -0.21, 0.0, 0.21, 0.42)
        shares = _split_counts(n_body, len(bands))
        body: list[tuple[float, float, float]] = []
        for share, y_mul in zip(shares, bands):
            if share <= 0:
                continue
            body.extend(_fill_xz_poly(profile, width * float(y_mul) - seat_y, share))
        body = body[:n_body]
    else:
        body = []
    lifted = _lift_above_ground(body + wheels, pad=float(_CAR_GROUND_LIFT))
    nb = len(body)
    return lifted[:nb], lifted[nb:]

def _offsets_car(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Parked 3D car: side-profile cabin, then tires. Guns lie flat."""
    body, wheels = _car_part_offsets(n, radius)
    return (wheels + body)[:n]


def _offsets_dome(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Closed hemisphere: full equator ring, latitude bands, meridians, cap. No door hole."""
    r = min(max(110.0, float(radius)), _MAX_GLOBE_RADIUS)
    if n <= 0:
        return []
    if n == 1:
        return [(0.0, 0.0, r)]
    golden = math.pi * (3.0 - math.sqrt(5.0))
    n_cap = 1
    remain = max(0, n - n_cap)
    # Equator ring first — the old fibonacci bias left a bite in the rim.
    n_eq = max(8 if remain >= 8 else remain, min(remain, int(round(remain * 0.24))))
    remain2 = max(0, remain - n_eq)
    n_ribs = 8
    n_mer = max(0, min(remain2, n_ribs * max(2, remain2 // 28)))
    n_fill = max(0, remain2 - n_mer)
    rim_z = r * 0.04
    equator = _ring_3d(0.0, 0.0, rim_z, r, 0.0, 0.0, 0.0, r, 0.0, n_eq)
    meridians: list[tuple[float, float, float]] = []
    rib_counts = _split_counts(n_mer, n_ribs) if n_mer else []
    for i, count in enumerate(rib_counts):
        if not count:
            continue
        ang = (2.0 * math.pi * i) / n_ribs
        ca, sa = math.cos(ang), math.sin(ang)
        for k in range(count):
            t = (k + 1) / (count + 1)
            elev = t * (math.pi / 2.0)
            rr = r * math.cos(elev)
            z = r * math.sin(elev)
            meridians.append((rr * ca, rr * sa, z))
    fill: list[tuple[float, float, float]] = []
    for i in range(n_fill):
        # Even hemisphere, equator→pole. Do not bias the pole (that opened the rim).
        zn = 0.08 + 0.90 * ((i + 0.5) / n_fill)
        rxy = math.sqrt(max(0.0, 1.0 - zn * zn))
        ang = i * golden
        fill.append((r * rxy * math.cos(ang), r * rxy * math.sin(ang), r * zn))
    return (equator + meridians + fill + [(0.0, 0.0, r)])[:n]


def _offsets_dna_helix(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Double helix with rungs. Skip rungs at the cap so the top does not sprout a flat hat."""
    turns = 2.75
    height = max(220.0, radius * 1.85)
    rad = max(70.0, radius * 0.32)
    n_strand = max(10, int(n * 0.42))
    n_rungs = max(4, n - 2 * n_strand)
    helix_a: list[tuple[float, float, float]] = []
    helix_b: list[tuple[float, float, float]] = []
    rungs: list[tuple[float, float, float]] = []
    samples = max(n_strand, 24)
    rung_every = max(1, samples // max(4, n_rungs))
    for i in range(samples):
        t = i / max(1, samples - 1)
        ang = t * turns * 2.0 * math.pi
        z = t * height
        a = (rad * math.cos(ang), rad * math.sin(ang), z)
        b = (rad * math.cos(ang + math.pi), rad * math.sin(ang + math.pi), z)
        helix_a.append(a)
        helix_b.append(b)
        if i % rung_every == 0 and 0.06 < t < 0.86:
            steps = 3
            for s in range(steps):
                u = s / max(1, steps - 1)
                rungs.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, z))
    return _take_n_points(
        _sample_polyline_3d(helix_a, n_strand)
        + _sample_polyline_3d(helix_b, n_strand)
        + _take_n_points(rungs, n_rungs),
        n,
    )


def _offsets_claptrap(n: int, radius: float) -> list[tuple[float, float, float]]:
    """CL4P-TP facing the player: box head, one eye, antenna, trapezoid body, unicycle."""
    n = max(1, int(n))
    r = max(140.0, float(radius))
    wheel_r = r * 0.17
    body_h = r * 0.58
    head_h = r * 0.40
    head_w = r * 0.44
    head_d = r * 0.38
    body_top_w = r * 0.34
    body_bot_w = r * 0.22
    body_d = r * 0.30
    near_h, far_h = -head_d * 0.98, head_d * 0.28
    near_b, far_b = -body_d * 0.95, body_d * 0.30
    z_w = wheel_r
    z_b0 = wheel_r * 2.05
    z_b1 = z_b0 + body_h
    z_h1 = z_b1 + head_h
    eye_c = (near_h - r * 0.02, 0.0, z_b1 + head_h * 0.52)
    eye_rad = r * 0.16

    n_eye = max(16, int(round(n * 0.16)))
    n_ant = max(6, int(round(n * 0.08)))
    n_wheel = max(12, int(round(n * 0.12)))
    n_head = max(16, int(round(n * 0.18)))
    n_body = max(16, int(round(n * 0.18)))
    n_arms = max(10, int(round(n * 0.12)))
    n_head_fill = max(12, int(round(n * 0.10)))
    n_body_fill = max(12, n - n_eye - n_ant - n_wheel - n_head - n_body - n_arms - n_head_fill)

    eye = _ring_3d(eye_c[0], eye_c[1], eye_c[2], 0.0, eye_rad, 0.0, 0.0, 0.0, eye_rad, max(n_eye, 16))
    eye.append(eye_c)
    antenna = _sample_polyline_3d(
        [
            (0.0, 0.0, z_h1),
            (0.0, 0.0, z_h1 + r * 0.22),
            (0.0, 0.0, z_h1 + r * 0.34),
            (r * 0.04, 0.0, z_h1 + r * 0.40),
        ],
        n_ant,
    )
    n_tire = max(8, n_wheel // 2)
    n_hub = max(4, n_wheel - n_tire)
    wheel = _ring_3d(0.0, 0.0, z_w, wheel_r, 0.0, 0.0, 0.0, 0.0, wheel_r, n_tire)
    wheel.extend(_ring_3d(0.0, 0.0, z_w, 0.0, wheel_r * 0.55, 0.0, wheel_r * 0.35, 0.0, 0.0, n_hub))
    head_corners = [
        (near_h, -head_w, z_b1),
        (near_h, head_w, z_b1),
        (near_h, head_w, z_h1),
        (near_h, -head_w, z_h1),
        (far_h, -head_w * 0.92, z_b1),
        (far_h, head_w * 0.92, z_b1),
        (far_h, head_w * 0.92, z_h1),
        (far_h, -head_w * 0.92, z_h1),
    ]
    body_corners = [
        (near_b, -body_bot_w, z_b0),
        (near_b, body_bot_w, z_b0),
        (near_b, body_top_w, z_b1),
        (near_b, -body_top_w, z_b1),
        (far_b, -body_bot_w * 0.88, z_b0),
        (far_b, body_bot_w * 0.88, z_b0),
        (far_b, body_top_w * 0.88, z_b1),
        (far_b, -body_top_w * 0.88, z_b1),
    ]
    box_edges = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]

    def _box_edges(corners: list[tuple[float, float, float]], count: int) -> list[tuple[float, float, float]]:
        pts: list[tuple[float, float, float]] = []
        for edge_n, (a, b) in zip(_split_counts(count, len(box_edges)), box_edges):
            if edge_n:
                pts.extend(_sample_polyline_3d([corners[a], corners[b]], edge_n))
        return pts

    head = _box_edges(head_corners, n_head)
    body = _box_edges(body_corners, n_body)
    head_fill = _fill_quad_3d(
        [head_corners[0], head_corners[1], head_corners[2], head_corners[3]],
        n_head_fill,
    )
    body_fill = _fill_quad_3d(
        [body_corners[0], body_corners[1], body_corners[2], body_corners[3]],
        max(0, n_body_fill),
    )
    n_arm_each = max(5, n_arms // 2)
    arms: list[tuple[float, float, float]] = []
    for sign in (-1.0, 1.0):
        shoulder = (near_b * 0.20, sign * body_top_w, z_b1 - body_h * 0.08)
        elbow = (near_b * 0.05, sign * (body_top_w + r * 0.20), z_b0 + body_h * 0.42)
        hand = (near_b * 0.18, sign * (body_top_w + r * 0.22), z_b0 + body_h * 0.12)
        arms.extend(_sample_polyline_3d([shoulder, elbow, hand], n_arm_each))
    return _lift_above_ground(
        _interleave_lists(
            [eye, antenna, wheel, head, body, arms, head_fill, body_fill],
            n,
        ),
        pad=32.0,
    )


def _offsets_pyramid_3d(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Square pyramid: base outline, sloped edges, then all four faces filled together."""
    n = max(0, int(n))
    if n <= 0:
        return []
    s = min(max(80.0, float(radius) * 0.78), 210.0)
    h = min(max(110.0, float(radius) * 1.05), 320.0)
    apex = (0.0, 0.0, h)
    base = [(-s, -s, 0.0), (s, -s, 0.0), (s, s, 0.0), (-s, s, 0.0)]
    if n == 1:
        return _commit_oriented(_lift_oriented([(apex, (0.0, 0.0, 1.0))]), 1)
    n_base = max(16, int(round(n * 0.42)))
    n_rise = max(12, int(round(n * 0.34)))
    n_fill = max(0, n - n_base - n_rise)
    rows = _oriented_polyline(base + [base[0]], n_base)
    rise_counts = _split_counts(n_rise, 4)
    for count, corner in zip(rise_counts, base):
        if count:
            rows.extend(_oriented_polyline([corner, apex], count))
    if n_fill:
        # Horizontal stripes on all four faces, interleaved so the dump does not
        # finish the outer wire then pack only the player-facing side.
        faces = (
            ((-s, -s, 0.0), (-s, s, 0.0)),
            ((s, -s, 0.0), (s, s, 0.0)),
            ((-s, -s, 0.0), (s, -s, 0.0)),
            ((-s, s, 0.0), (s, s, 0.0)),
        )
        n_stripes = min(6, max(2, n_fill // 16))
        per = max(1, n_fill // (n_stripes * 4))
        face_rows: list[list[tuple[tuple[float, float, float], tuple[float, float, float]]]] = [
            [] for _ in faces
        ]
        for i in range(n_stripes):
            t = (i + 1) / (n_stripes + 1)
            for fi, (left_b, right_b) in enumerate(faces):
                a = _lerp3(left_b, apex, t)
                b = _lerp3(right_b, apex, t)
                face_rows[fi].extend(_oriented_polyline([a, b], per))
        fill_pts: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
        i = 0
        while len(fill_pts) < n_fill:
            progressed = False
            for fr in face_rows:
                if i < len(fr):
                    fill_pts.append(fr[i])
                    progressed = True
                    if len(fill_pts) >= n_fill:
                        break
            if not progressed:
                break
            i += 1
        rows.extend(fill_pts[:n_fill])
    return _commit_oriented(_lift_oriented(rows, pad=36.0), n)


def _lift_above_ground(
    points: list[tuple[float, float, float]],
    *,
    pad: float = 28.0,
) -> list[tuple[float, float, float]]:
    """Keep a standing silhouette's chin / lowest point above the player's feet."""
    if not points:
        return points
    min_z = min(p[2] for p in points)
    if min_z >= pad:
        return points
    dz = pad - min_z
    return [(x, y, z + dz) for x, y, z in points]


def _sphere_shell(
    cx: float,
    cy: float,
    cz: float,
    rad: float,
    n: int,
    *,
    front_bias: float = 0.0,
) -> list[tuple[float, float, float]]:
    """Fibonacci sphere. front_bias > 0 pulls points toward +forward (player-facing)."""
    if n <= 0:
        return []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    out: list[tuple[float, float, float]] = []
    for i in range(n):
        t = (i + 0.5) / n
        z = 1.0 - 2.0 * t
        rxy = math.sqrt(max(0.0, 1.0 - z * z))
        ang = i * golden
        fwd = rad * rxy * math.cos(ang)
        right = rad * rxy * math.sin(ang)
        up = rad * z
        if front_bias > 0.0:
            fwd = abs(fwd) * (0.35 + 0.65 * front_bias) + fwd * (1.0 - front_bias) * 0.25
        out.append((cx + fwd, cy + right, cz + up))
    return out


def _box_wire_oriented(
    cx: float,
    cy: float,
    cz: float,
    hx: float,
    hy: float,
    hz: float,
    n: int,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Axis-aligned box: 12 edges first, then face stripes if budget remains."""
    n = max(0, int(n))
    if n <= 0:
        return []
    corners = [
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    ]
    edges = (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    )
    n_edge = min(n, max(12, int(round(n * 0.62))))
    edge_counts = _split_counts(n_edge, len(edges))
    rows: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for count, (a, b) in zip(edge_counts, edges):
        if count:
            rows.extend(_oriented_polyline([corners[a], corners[b]], count))
    remain = max(0, n - len(rows))
    if remain <= 0:
        return rows[:n]
    # Light face fill so short dumps still read as solid cubes.
    faces = (
        (corners[0], corners[1], corners[2], corners[3]),  # bottom
        (corners[4], corners[5], corners[6], corners[7]),  # top
        (corners[0], corners[1], corners[5], corners[4]),
        (corners[1], corners[2], corners[6], corners[5]),
        (corners[2], corners[3], corners[7], corners[6]),
        (corners[3], corners[0], corners[4], corners[7]),
    )
    face_counts = _split_counts(remain, len(faces))
    for count, face in zip(face_counts, faces):
        if count <= 0:
            continue
        loop = list(face) + [face[0]]
        rows.extend(_oriented_polyline(loop, count))
    return rows[:n]

def _offsets_diamond_3d(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Standing octahedron / gem: apex, nadir, equatorial ring, then face stripes."""
    n = max(0, int(n))
    if n <= 0:
        return []
    s = min(max(70.0, float(radius) * 0.55), 160.0)
    h = min(max(120.0, float(radius) * 1.05), 280.0)
    mid = h * 0.48
    apex = (0.0, 0.0, h)
    nadir = (0.0, 0.0, 0.0)
    eq = [(s, 0.0, mid), (0.0, s, mid), (-s, 0.0, mid), (0.0, -s, mid)]
    if n == 1:
        return _commit_oriented(_lift_oriented([(apex, (0.0, 0.0, 1.0))]), 1)
    n_eq = max(12, int(round(n * 0.28)))
    n_rise = max(12, int(round(n * 0.36)))
    n_fill = max(0, n - n_eq - n_rise)
    rows = _oriented_polyline(eq + [eq[0]], n_eq)
    rise_budget = _split_counts(n_rise, 8)
    for i, corner in enumerate(eq):
        up_n = rise_budget[i] if i < len(rise_budget) else 0
        dn_n = rise_budget[i + 4] if i + 4 < len(rise_budget) else 0
        if up_n:
            rows.extend(_oriented_polyline([corner, apex], up_n))
        if dn_n:
            rows.extend(_oriented_polyline([corner, nadir], dn_n))
    if n_fill:
        n_stripes = min(5, max(2, n_fill // 16))
        per = max(1, n_fill // (n_stripes * 8))
        face_rows: list[list[tuple[tuple[float, float, float], tuple[float, float, float]]]] = [
            [] for _ in range(8)
        ]
        for i in range(n_stripes):
            t = (i + 1) / (n_stripes + 1)
            for fi, corner in enumerate(eq):
                nxt = eq[(fi + 1) % 4]
                a = _lerp3(corner, apex, t)
                b = _lerp3(nxt, apex, t)
                face_rows[fi].extend(_oriented_polyline([a, b], per))
                c = _lerp3(corner, nadir, t)
                d = _lerp3(nxt, nadir, t)
                face_rows[fi + 4].extend(_oriented_polyline([c, d], per))
        fill_pts: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
        i = 0
        while len(fill_pts) < n_fill:
            progressed = False
            for fr in face_rows:
                if i < len(fr):
                    fill_pts.append(fr[i])
                    progressed = True
                    if len(fill_pts) >= n_fill:
                        break
            if not progressed:
                break
            i += 1
        rows.extend(fill_pts[:n_fill])
    return _commit_oriented(_lift_oriented(rows, pad=28.0), n)

def _offsets_blocks(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Minecraft-ish: three cubes on the bottom row, one cube centered on top."""
    n = max(0, int(n))
    if n <= 0:
        return []
    s = min(max(42.0, float(radius) * 0.28), 78.0)
    gap = s * 2.12
    centers = (
        (0.0, -gap, s),
        (0.0, 0.0, s),
        (0.0, gap, s),
        (0.0, 0.0, s * 3.0),
    )
    # Bottom three get a bit more budget so short dumps still read as the row.
    weights = (0.26, 0.26, 0.26, 0.22)
    counts = [max(4, int(round(n * w))) for w in weights]
    while sum(counts) > n:
        for i in range(4):
            if sum(counts) <= n:
                break
            if counts[i] > 4:
                counts[i] -= 1
    while sum(counts) < n:
        counts[sum(counts) % 4] += 1
    rows: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for (cx, cy, cz), count in zip(centers, counts):
        rows.extend(_box_wire_oriented(cx, cy, cz, s, s, s, count))
    return _commit_oriented(_lift_oriented(rows[:n], pad=18.0), n)

def _offsets_cube(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Single standing cube silhouette."""
    n = max(0, int(n))
    if n <= 0:
        return []
    s = min(max(70.0, float(radius) * 0.52), 150.0)
    rows = _box_wire_oriented(0.0, 0.0, s, s, s, s, n)
    return _commit_oriented(_lift_oriented(rows, pad=20.0), n)

def _offsets_torus(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Donut / torus lying flat: major ring + tube rings."""
    n = max(0, int(n))
    if n <= 0:
        return []
    R = min(max(90.0, float(radius) * 0.72), 200.0)
    r = min(max(28.0, R * 0.32), 70.0)
    if n == 1:
        return _commit_oriented(_lift_oriented([((R, 0.0, r), (0.0, 1.0, 0.0))]), 1)
    n_major = max(16, int(round(n * 0.40)))
    n_tubes = max(0, n - n_major)
    major = _ring_3d(0.0, 0.0, r, R, 0.0, 0.0, 0.0, R, 0.0, n_major)
    rows = _oriented_from_pts(major, (0.0, 1.0, 0.0))
    if n_tubes:
        n_sections = min(12, max(4, n_tubes // 8))
        per = max(1, n_tubes // n_sections)
        tube_rows: list[list[tuple[tuple[float, float, float], tuple[float, float, float]]]] = [
            [] for _ in range(n_sections)
        ]
        for si in range(n_sections):
            ang = (2.0 * math.pi * si) / n_sections
            ca, sa = math.cos(ang), math.sin(ang)
            cx, cy = R * ca, R * sa
            # Tube circle in the plane spanned by radial + up.
            tube = _ring_3d(cx, cy, r, r * ca, r * sa, 0.0, 0.0, 0.0, r, per)
            tube_rows[si] = _oriented_from_pts(tube, (-sa, ca, 0.0))
        fill: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
        i = 0
        while len(fill) < n_tubes:
            progressed = False
            for tr in tube_rows:
                if i < len(tr):
                    fill.append(tr[i])
                    progressed = True
                    if len(fill) >= n_tubes:
                        break
            if not progressed:
                break
            i += 1
        rows.extend(fill[:n_tubes])
    return _commit_oriented(_lift_oriented(rows, pad=22.0), n)

def _offsets_crown(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Band + pointed spikes — reads as a crown even on short shiny dumps."""
    n = max(0, int(n))
    if n <= 0:
        return []
    R = min(max(80.0, float(radius) * 0.62), 170.0)
    band_h = max(28.0, R * 0.28)
    spike_h = max(55.0, R * 0.70)
    n_spikes = 5
    n_band = max(16, int(round(n * 0.45)))
    n_rise = max(0, n - n_band)
    band_lo = _ring_3d(0.0, 0.0, 0.0, R, 0.0, 0.0, 0.0, R, 0.0, max(8, n_band // 2))
    band_hi = _ring_3d(0.0, 0.0, band_h, R, 0.0, 0.0, 0.0, R, 0.0, n_band - len(band_lo))
    rows = _oriented_from_pts(band_lo + band_hi, (0.0, 1.0, 0.0))
    if n_rise:
        spike_counts = _split_counts(n_rise, n_spikes)
        for i, count in enumerate(spike_counts):
            if not count:
                continue
            ang = (2.0 * math.pi * i) / n_spikes - math.pi / 2.0
            ca, sa = math.cos(ang), math.sin(ang)
            base_l = (R * math.cos(ang - 0.22), R * math.sin(ang - 0.22), band_h)
            base_r = (R * math.cos(ang + 0.22), R * math.sin(ang + 0.22), band_h)
            tip = (R * 0.92 * ca, R * 0.92 * sa, band_h + spike_h)
            left_n = max(1, count // 2)
            right_n = max(0, count - left_n)
            rows.extend(_oriented_polyline([base_l, tip], left_n))
            if right_n:
                rows.extend(_oriented_polyline([base_r, tip], right_n))
    return _commit_oriented(_lift_oriented(rows, pad=24.0), n)

def _offsets_ufo(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Flying saucer: disc rim + cabin dome."""
    n = max(0, int(n))
    if n <= 0:
        return []
    R = min(max(100.0, float(radius) * 0.78), 210.0)
    disc_z = max(36.0, R * 0.22)
    dome_r = max(36.0, R * 0.34)
    n_rim = max(16, int(round(n * 0.38)))
    n_inner = max(8, int(round(n * 0.18)))
    n_dome = max(0, n - n_rim - n_inner)
    rim = _ring_3d(0.0, 0.0, disc_z, R, 0.0, 0.0, 0.0, R, 0.0, n_rim)
    inner = _ring_3d(0.0, 0.0, disc_z + 8.0, R * 0.55, 0.0, 0.0, 0.0, R * 0.55, 0.0, n_inner)
    rows = _oriented_from_pts(rim + inner, (0.0, 1.0, 0.0))
    if n_dome:
        dome = _sphere_shell(0.0, 0.0, disc_z + dome_r * 0.15, dome_r, n_dome, front_bias=0.15)
        # Keep only the upper cabin (z above disc).
        dome = [p for p in dome if p[2] >= disc_z - 4.0]
        if len(dome) < n_dome:
            dome = _take_n_points(dome or [(0.0, 0.0, disc_z + dome_r)], n_dome)
        rows.extend(_oriented_from_pts(dome[:n_dome], (1.0, 0.0, 0.0)))
    return _commit_oriented(_lift_oriented(rows, pad=26.0), n)

def _offsets_rocket(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Standing rocket: body rings, nose cone, base fins."""
    n = max(0, int(n))
    if n <= 0:
        return []
    h = min(max(160.0, float(radius) * 1.15), 320.0)
    body_r = min(max(34.0, float(radius) * 0.22), 70.0)
    nose_h = h * 0.28
    body_h = h * 0.62
    n_body = max(16, int(round(n * 0.42)))
    n_nose = max(8, int(round(n * 0.22)))
    n_fins = max(0, n - n_body - n_nose)
    # Horizontal body rings stacked up the fuselage.
    n_rings = min(8, max(3, n_body // 10))
    ring_counts = _split_counts(n_body, n_rings)
    rows: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for i, count in enumerate(ring_counts):
        if not count:
            continue
        z = (i + 0.5) / n_rings * body_h
        ring = _ring_3d(0.0, 0.0, z, body_r, 0.0, 0.0, 0.0, body_r, 0.0, count)
        rows.extend(_oriented_from_pts(ring, (0.0, 1.0, 0.0)))
    # Nose cone ribs to tip.
    tip = (0.0, 0.0, body_h + nose_h)
    nose_ribs = 6
    nose_counts = _split_counts(n_nose, nose_ribs)
    for i, count in enumerate(nose_counts):
        if not count:
            continue
        ang = (2.0 * math.pi * i) / nose_ribs
        base = (body_r * math.cos(ang), body_r * math.sin(ang), body_h)
        rows.extend(_oriented_polyline([base, tip], count))
    # Three fins at the base.
    if n_fins:
        fin_counts = _split_counts(n_fins, 3)
        for i, count in enumerate(fin_counts):
            if not count:
                continue
            ang = (2.0 * math.pi * i) / 3.0 + math.pi / 6.0
            ca, sa = math.cos(ang), math.sin(ang)
            root_lo = (body_r * ca, body_r * sa, 0.0)
            root_hi = (body_r * ca, body_r * sa, body_h * 0.28)
            tip_fin = (body_r * 2.2 * ca, body_r * 2.2 * sa, 0.0)
            a_n = max(1, count // 2)
            b_n = max(0, count - a_n)
            rows.extend(_oriented_polyline([root_lo, tip_fin], a_n))
            if b_n:
                rows.extend(_oriented_polyline([root_hi, tip_fin], b_n))
    return _commit_oriented(_lift_oriented(rows, pad=20.0), n)

def _offsets_gear(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Standing cog: outer toothed ring, hub, and spokes."""
    n = max(0, int(n))
    if n <= 0:
        return []
    R = min(max(90.0, float(radius) * 0.70), 190.0)
    r_hub = max(28.0, R * 0.28)
    teeth = 10
    tooth_out = R * 1.18
    n_rim = max(20, int(round(n * 0.48)))
    n_hub = max(8, int(round(n * 0.18)))
    n_spokes = max(0, n - n_rim - n_hub)
    # Build toothed outline in XY, lift to standing plane (forward/up).
    tooth_pts: list[tuple[float, float, float]] = []
    for i in range(teeth):
        a0 = (2.0 * math.pi * i) / teeth
        a1 = (2.0 * math.pi * (i + 0.35)) / teeth
        a2 = (2.0 * math.pi * (i + 0.65)) / teeth
        a3 = (2.0 * math.pi * (i + 1.0)) / teeth
        tooth_pts.extend(
            [
                (0.0, R * math.cos(a0), R * math.sin(a0)),
                (0.0, tooth_out * math.cos(a1), tooth_out * math.sin(a1)),
                (0.0, tooth_out * math.cos(a2), tooth_out * math.sin(a2)),
                (0.0, R * math.cos(a3), R * math.sin(a3)),
            ]
        )
    rows = _oriented_polyline(tooth_pts + [tooth_pts[0]], n_rim)
    hub = [
        (0.0, r_hub * math.cos((2.0 * math.pi * i) / max(1, n_hub)), r_hub * math.sin((2.0 * math.pi * i) / max(1, n_hub)))
        for i in range(max(1, n_hub))
    ]
    rows.extend(_oriented_from_pts(hub, (0.0, 0.0, 1.0)))
    if n_spokes:
        spoke_n = 6
        spoke_counts = _split_counts(n_spokes, spoke_n)
        for i, count in enumerate(spoke_counts):
            if not count:
                continue
            ang = (2.0 * math.pi * i) / spoke_n
            ca, sa = math.cos(ang), math.sin(ang)
            inner = (0.0, r_hub * ca, r_hub * sa)
            outer = (0.0, R * 0.92 * ca, R * 0.92 * sa)
            rows.extend(_oriented_polyline([inner, outer], count))
    return _commit_oriented(_lift_oriented(rows, pad=30.0), n)

def _offsets_forbidden_one(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Hidden 3D silhouette: glans first, then pair at the base, then shaft (full XYZ)."""
    r = max(120.0, radius)
    shaft_h = r * 1.65
    shaft_rad = r * 0.22
    ball_r = r * 0.28
    glans_r = r * 0.32
    n_glans = max(6, min(n, int(round(n * 0.12))))
    n_balls = max(8, min(n - n_glans, int(round(n * 0.16))))
    n_shaft = max(0, n - n_glans - n_balls)
    n_shaft = min(n_shaft, max(24, int(round(n * 0.32))))
    leftover = max(0, n - n_glans - n_balls - n_shaft)
    n_glans += leftover // 2
    n_balls += leftover - leftover // 2
    glans = _sphere_shell(shaft_rad * 0.35, 0.0, shaft_h + glans_r * 0.35, glans_r, n_glans, front_bias=0.55)
    n_each = max(2, n_balls // 2)
    left_ball = _sphere_shell(0.0, -ball_r * 0.82, ball_r, ball_r, n_each, front_bias=0.25)
    right_ball = _sphere_shell(0.0, ball_r * 0.82, ball_r, ball_r, n_balls - n_each, front_bias=0.25)
    # Interleave left/right so both fill together (same fix as forbidden_pair).
    balls: list[tuple[float, float, float]] = []
    for i in range(max(len(left_ball), len(right_ball))):
        if i < len(left_ball):
            balls.append(left_ball[i])
        if i < len(right_ball):
            balls.append(right_ball[i])
    shaft: list[tuple[float, float, float]] = []
    rings = max(4, min(12, n_shaft // 6))
    per = max(4, n_shaft // max(1, rings))
    z0 = ball_r * 1.35
    z1 = shaft_h
    for ri in range(rings):
        t = ri / max(1, rings - 1)
        z = z0 + (z1 - z0) * t
        rad = shaft_rad * (1.08 - 0.14 * t)
        for i in range(per):
            ang = (2.0 * math.pi * i) / per
            shaft.append((math.cos(ang) * rad * 0.35, math.sin(ang) * rad, z))
    out = (_take_n_points(glans, n_glans) + _take_n_points(balls, n_balls) + _take_n_points(shaft, n_shaft))[:n]
    # Lift so lowest item is at least 56 units above origin (floor items get
    # swept by the engine before catch can pin them, causing spray).
    if out:
        min_z = min(p[2] for p in out)
        if min_z < 56.0:
            lift = 56.0 - min_z
            out = [(x, y, z + lift) for x, y, z in out]
    return out


_forbidden_pair_globes: tuple[tuple[float, float, float], tuple[float, float, float]] = (
    (0.0, -80.0, 80.0),
    (0.0, 80.0, 80.0),
)


def _offsets_forbidden_pair(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Hidden 3D silhouette: two mirrored teardrops + partial torso.

    Fill left/right together (not left-then-right). The old order completed one
    globe first; later dump items missed slots and physics-yeeted the second side.
    """
    global _forbidden_pair_globes
    r = max(140.0, float(radius))
    br = r * 0.78
    sep = br * 0.78
    zc = br * 0.90
    rx, ry, rz = br * 1.02, br * 0.68, br * 1.00
    cx = -br * 0.16
    left_c = (cx, -sep * 0.5, zc)
    right_c = (cx, sep * 0.5, zc)
    _forbidden_pair_globes = (left_c, right_c)

    n = max(0, int(n))
    if n <= 0:
        return []
    n_torso = 0 if n < 36 else min(int(round(n * 0.12)), n // 6)
    n_pair = max(2, n - n_torso)
    n_left = (n_pair + 1) // 2
    n_right = n_pair - n_left
    left = _teardrop_shell(left_c[0], left_c[1], left_c[2], rx, ry, rz, n_left, front_bias=0.58)
    if n_right == n_left:
        right = [(p[0], -p[1], p[2]) for p in left]
    else:
        src = _teardrop_shell(left_c[0], left_c[1], left_c[2], rx, ry, rz, n_right, front_bias=0.58)
        right = [(p[0], -p[1], p[2]) for p in src]

    out: list[tuple[float, float, float]] = []
    for i in range(max(n_left, n_right)):
        if i < n_left:
            out.append(left[i])
        if i < n_right:
            out.append(right[i])

    remaining = max(0, n - len(out))
    if remaining > 0:
        rows = max(2, min(6, remaining // 3))
        per = max(1, int(math.ceil(remaining / rows)))
        for ri in range(rows):
            t = ri / max(1, rows - 1)
            z = zc - rz * (0.42 + 0.22 * t)
            fwd = cx - br * (0.22 + 0.28 * t)
            width = sep * (0.42 - 0.10 * t)
            for i in range(per):
                if len(out) >= n:
                    break
                u = (i + 0.5) / per - 0.5
                out.append((fwd, u * width, z))
    out = out[:n]
    if out:
        min_z = min(p[2] for p in out)
        if min_z < 56.0:
            lift = 56.0 - min_z
            out = [(x, y, z + lift) for x, y, z in out]
    return out


def _offsets_double_ring(n: int, radius: float, spacing: float) -> list[tuple[float, float, float]]:
    if n <= 1:
        return _offsets_circle(n, radius)
    inner_n = max(1, n // 2)
    outer_n = n - inner_n
    return _offsets_circle(inner_n, radius) + _offsets_circle(outer_n, radius + spacing)


def _offsets_square(n: int, radius: float) -> list[tuple[float, float, float]]:
    s = radius * 0.85
    verts = [(s, -s), (s, s), (-s, s), (-s, -s)]
    return _sample_polyline(verts, n, closed=True)


def _offsets_rows(n: int, spacing: float, per_row: int) -> list[tuple[float, float, float]]:
    cols = max(4, int(per_row))
    out: list[tuple[float, float, float]] = []
    for index in range(n):
        row = index // cols
        col = index % cols
        width = min(cols, n - row * cols)
        fx = spacing * 1.4 + row * spacing
        ry = (col - 0.5 * (width - 1)) * spacing
        out.append((fx, ry, 0.0))
    return out


def _offsets_arc(n: int, radius: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    span = math.pi * 0.95
    for index in range(n):
        t = index / max(1, n - 1) if n > 1 else 0.5
        ang = -span * 0.5 + t * span
        out.append((radius * math.cos(ang), radius * math.sin(ang), 0.0))
    return out


def _offsets_fan(n: int, radius: float, spacing: float) -> list[tuple[float, float, float]]:
    rows = max(2, int(math.ceil(math.sqrt(n * 0.7))))
    out: list[tuple[float, float, float]] = []
    remaining = n
    for row in range(rows):
        if remaining <= 0:
            break
        count = min(remaining, 4 + row * 3)
        r = radius * 0.45 + row * spacing * 0.85
        span = math.pi * (0.45 + 0.12 * row)
        for i in range(count):
            t = i / max(1, count - 1) if count > 1 else 0.5
            ang = -span * 0.5 + t * span
            out.append((r * math.cos(ang), r * math.sin(ang), 0.0))
        remaining -= count
    return out[:n]


def _offsets_x_mark(n: int, radius: float) -> list[tuple[float, float, float]]:
    a = radius * 0.85
    return _sample_polylines(
        [[(-a, -a), (a, a)], [(-a, a), (a, -a)]],
        n,
        closed=False,
    )


def _offsets_infinity(n: int, radius: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    a = radius * 0.95
    for index in range(n):
        t = (index / max(1, n)) * 2.0 * math.pi
        den = 1.0 + math.sin(t) ** 2
        # Lemniscate of Bernoulli, laid on the ground in front of the player.
        right = a * math.sqrt(2.0) * math.cos(t) / den
        forward = a * math.sqrt(2.0) * math.sin(t) * math.cos(t) / den + a * 0.15
        out.append((forward, right, 0.0))
    return out


def _offsets_figure8(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Upright 8 (two loops along forward). Infinity stays the sideways ∞."""
    out: list[tuple[float, float, float]] = []
    for index in range(n):
        t = (index / max(1, n)) * 2.0 * math.pi
        forward = radius * math.sin(2.0 * t)
        right = radius * 0.58 * math.sin(t)
        out.append((forward, right, 0.0))
    return out


def _offsets_wave(
    n: int, radius: float, spacing: float, line_length: float = _DEFAULT_LINE_LENGTH
) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    width = max(radius * 2.6, min(float(line_length), max(spacing * 5.0, 280.0)))
    width = min(width, float(_MAX_LINE_SPAN))
    amp = min(max(radius * 0.95, spacing * 0.9), float(_MAX_LINE_SPAN) * 0.35)
    cycles = 2.0 if n < 36 else 2.5
    for index in range(n):
        t = index / max(1, n - 1) if n > 1 else 0.5
        right = (t - 0.5) * width
        forward = spacing * 1.15 + amp * math.sin(t * 2.0 * math.pi * cycles)
        out.append((forward, right, 0.0))
    return out


def _offsets_lightning(
    n: int, radius: float, spacing: float, line_length: float = _DEFAULT_LINE_LENGTH
) -> list[tuple[float, float, float]]:
    h = min(
        max(radius * 1.4, spacing * 3.0),
        max(160.0, float(line_length)),
        float(_MAX_LINE_SPAN),
    )
    w = min(max(radius * 0.55, spacing * 1.2), float(_MAX_LINE_SPAN) * 0.4)
    verts = [
        (h * 0.55, -w * 0.15),
        (h * 0.12, w * 0.55),
        (h * 0.05, w * 0.08),
        (-h * 0.18, w * 0.62),
        (-h * 0.10, 0.0),
        (-h * 0.55, w * 0.22),
    ]
    return _sample_polyline(verts, n, closed=False)


def _offsets_vault(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Vault Hunter logo: circle + inverted V whose peak nearly touches 12 o'clock."""
    r = max(40.0, float(radius))
    circle: list[tuple[float, float]] = []
    steps = 48
    for i in range(steps):
        ang = (2.0 * math.pi * i) / steps
        circle.append((r * math.cos(ang), r * math.sin(ang)))
    # 12 o'clock = +X (player-forward). Λ peak sits just inside the ring.
    peak = (r * 0.96, 0.0)
    foot_l = (r * 0.90 * math.cos(4.0 * math.pi / 3.0), r * 0.90 * math.sin(4.0 * math.pi / 3.0))
    foot_r = (r * 0.90 * math.cos(2.0 * math.pi / 3.0), r * 0.90 * math.sin(2.0 * math.pi / 3.0))
    n_ring = max(10, int(round(n * 0.58)))
    n_v = max(8, n - n_ring)
    return _sample_polyline(circle, n_ring, closed=True) + _sample_polyline(
        [foot_l, peak, foot_r], n_v, closed=False
    )


def _offsets_firehawk(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Lilith Firehawk: hooked beak, eye, jagged wing feathers, three-flame tail.

    Logo space is (x right, y up). Local layout is (forward=y, right=x) so the bird
    sits on the ground in front of you, head to your left, wings away from you.
    Strokes fill together so a bulk dump reads as a bird, not one outline scribble.
    """
    if n <= 0:
        return []
    r = max(40.0, float(radius))

    def _xy(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [(y * r, x * r) for x, y in pts]

    head = _xy(
        [
            (-0.70, 0.06),
            (-0.88, 0.16),
            (-1.00, 0.10),
            (-1.14, 0.02),
            (-1.02, -0.08),
            (-0.86, -0.02),
            (-0.70, 0.04),
        ]
    )
    eye = _xy(
        [
            (-0.84, 0.10),
            (-0.78, 0.18),
            (-0.70, 0.12),
            (-0.76, 0.04),
            (-0.84, 0.10),
        ]
    )
    body = _xy(
        [
            (-0.68, 0.04),
            (-0.42, 0.08),
            (-0.12, 0.06),
            (0.16, 0.00),
            (0.40, -0.08),
            (0.58, -0.16),
        ]
    )
    belly = _xy(
        [
            (-0.66, -0.02),
            (-0.38, -0.18),
            (-0.08, -0.24),
            (0.22, -0.20),
            (0.48, -0.14),
        ]
    )
    # Five separate wing feathers (classic jagged tattoo), not one dense outline.
    feathers = [
        _xy([(-0.52, 0.12), (-0.40, 0.42), (-0.30, 0.74), (-0.20, 1.06)]),
        _xy([(-0.28, 0.36), (-0.10, 0.70), (0.04, 1.00), (0.12, 1.10)]),
        _xy([(-0.10, 0.22), (0.14, 0.56), (0.30, 0.86), (0.40, 0.98)]),
        _xy([(0.08, 0.10), (0.32, 0.40), (0.50, 0.68), (0.58, 0.80)]),
        _xy([(0.22, 0.00), (0.46, 0.24), (0.64, 0.44), (0.72, 0.54)]),
    ]
    wing_low = _xy(
        [
            (0.10, -0.02),
            (0.38, 0.14),
            (0.62, 0.28),
            (0.48, 0.04),
            (0.26, -0.08),
        ]
    )
    flames = [
        _xy([(0.52, -0.12), (0.78, -0.02), (1.04, 0.08), (0.74, -0.14), (0.54, -0.18)]),
        _xy([(0.48, -0.20), (0.76, -0.34), (0.98, -0.46), (0.64, -0.36), (0.46, -0.24)]),
        _xy([(0.40, -0.28), (0.58, -0.54), (0.72, -0.86), (0.44, -0.60), (0.34, -0.36)]),
    ]
    n_head = max(8, int(round(n * 0.12)))
    n_eye = max(6, int(round(n * 0.06)))
    n_body = max(8, int(round(n * 0.12)))
    n_belly = max(8, int(round(n * 0.10)))
    n_feather = max(10, int(round(n * 0.36)))
    n_low = max(6, int(round(n * 0.08)))
    n_tail = max(10, n - (n_head + n_eye + n_body + n_belly + n_feather + n_low))
    if n_tail < 0:
        n_feather = max(8, n_feather + n_tail)
        n_tail = max(8, int(round(n * 0.16)))
    groups = [
        _sample_polyline(head, n_head, closed=True),
        _sample_polyline(eye, n_eye, closed=True),
        _sample_polyline(body, n_body, closed=False),
        _sample_polyline(belly, n_belly, closed=False),
        _sample_polylines(feathers, n_feather, closed=False),
        _sample_polyline(wing_low, n_low, closed=False),
        _sample_polylines(flames, n_tail, closed=False),
    ]
    return _interleave_lists(groups, n)


def _offsets_psycho(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Ground psycho mask: pointed chin toward you, eye holes, mouth grill, vault V above the eyes."""
    if n <= 0:
        return []
    r = max(40.0, float(radius))
    # Eyes / mouth / V first so a short dump is still a face, not an empty oval.
    n_eyes = max(8, int(round(n * 0.24)))
    if n_eyes % 2:
        n_eyes += 1
    n_mouth = max(10, int(round(n * 0.24)))
    n_vault = max(8, int(round(n * 0.18)))
    used = n_eyes + n_mouth + n_vault
    if used >= n:
        n_outline = 0
        while n_eyes + n_mouth + n_vault > n:
            if n_vault > 0:
                n_vault -= 1
            elif n_mouth > 0:
                n_mouth -= 1
            elif n_eyes > 0:
                n_eyes -= 1
                if n_eyes % 2 and n_eyes > 0:
                    n_eyes -= 1
            else:
                break
    else:
        n_outline = n - used

    def _xy(fwd: float, right: float) -> tuple[float, float]:
        return (fwd * r, right * r)

    # Chin toward the player (-fwd). No mohawk — those guns read as eyebrows.
    skull = [
        _xy(-1.02, 0.00),
        _xy(-0.86, -0.34),
        _xy(-0.58, -0.70),
        _xy(-0.18, -0.94),
        _xy(0.22, -0.90),
        _xy(0.58, -0.72),
        _xy(0.82, -0.40),
        _xy(0.94, -0.14),
        _xy(0.94, 0.14),
        _xy(0.82, 0.40),
        _xy(0.58, 0.72),
        _xy(0.22, 0.90),
        _xy(-0.18, 0.94),
        _xy(-0.58, 0.70),
        _xy(-0.86, 0.34),
        _xy(-1.02, 0.00),
    ]
    eye_l = [
        _xy(0.10, -0.20),
        _xy(0.38, -0.24),
        _xy(0.44, -0.42),
        _xy(0.14, -0.52),
        _xy(0.10, -0.20),
    ]
    eye_r = [
        _xy(0.10, 0.20),
        _xy(0.38, 0.24),
        _xy(0.44, 0.42),
        _xy(0.14, 0.52),
        _xy(0.10, 0.20),
    ]
    # Forehead only — not a giant V from the mouth to the crown.
    vault = [_xy(0.50, -0.36), _xy(0.88, 0.00), _xy(0.50, 0.36)]
    n_teeth_bar = max(4, int(round(n_mouth * 0.40)))
    n_slats = max(0, n_mouth - n_teeth_bar)
    mouth_bar = [_xy(-0.38, -0.58), _xy(-0.42, 0.00), _xy(-0.38, 0.58)]
    slat_paths: list[list[tuple[float, float]]] = []
    slat_n = max(5, min(9, n_slats if n_slats else 5))
    for i in range(slat_n):
        t = i / max(1, slat_n - 1)
        y = (t - 0.5) * 1.10
        slat_paths.append([_xy(-0.40, y), _xy(-0.72, y * 0.92)])

    face: list[tuple[float, float, float]] = []
    if n_eyes:
        per = max(1, n_eyes // 2)
        face.extend(_sample_polyline(eye_l, per, closed=True))
        face.extend(_sample_polyline(eye_r, n_eyes - per, closed=True))
    face.extend(_sample_polyline(mouth_bar, n_teeth_bar, closed=False))
    if n_slats:
        face.extend(_sample_polylines(slat_paths, n_slats, closed=False))
    if n_vault:
        face.extend(_sample_polyline(vault, n_vault, closed=False))
    outline = _sample_polyline(skull, n_outline, closed=True) if n_outline else []
    return _interleave_lists([face, outline], n)


def _gearbox_block_letter(fwd: float, right: float, w: float, h: float, kind: str) -> list[tuple[float, float]]:
    """One chunky letter stroke for the Gearbox wordmark."""
    x0, x1 = fwd, fwd + h
    y0, y1 = right, right + w
    ym = right + w * 0.5
    if kind == "g":
        return [
            (x0, y0),
            (x1, y0),
            (x1, ym),
            (x0 + h * 0.42, ym),
            (x0 + h * 0.42, y1),
            (x1, y1),
            (x1, y0),
            (x0, y0),
            (x0, y1),
        ]
    if kind == "e":
        return [
            (x1, y0),
            (x0, y0),
            (x0, y1),
            (x1, y1),
            (x1, ym),
            (x0 + h * 0.22, ym),
            (x0 + h * 0.22, y0 + w * 0.18),
            (x1, y0 + w * 0.18),
        ]
    if kind == "a":
        return [(x0 + h * 0.55, y0), (x1, y0), (x1, y1), (x0, y1), (x0, ym), (x1, ym), (x0 + h * 0.18, y0)]
    if kind == "r":
        return [(x0, y0), (x0, y1), (x0 + h * 0.22, y1), (x1, ym), (x1, y0), (x0 + h * 0.55, y0), (x0 + h * 0.55, ym)]
    if kind == "b":
        return [
            (x0, y0),
            (x0, y1),
            (x0 + h * 0.52, y1),
            (x1, ym),
            (x0 + h * 0.52, y0),
            (x0, y0),
            (x0 + h * 0.52, y0),
            (x1, ym),
            (x0 + h * 0.52, y1),
        ]
    if kind == "o":
        return [(x0 + h * 0.18, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0), (x0 + h * 0.18, y0)]
    if kind == "x":
        return [(x0, y0), (x1, y1), (x0, y1), (x1, y0)]
    # software caps — short vertical bar
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def _offsets_gearbox_logo(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Gearbox Software logo facing the player: wide square gear icon + wordmark."""
    r = max(100.0, radius)
    face_x = -r * 0.14
    pad = 54.0
    hy = r * 0.62
    hz = r * 0.48
    icon_z = r * 1.72 + pad
    frame = [
        (face_x, -hy, icon_z - hz),
        (face_x, hy, icon_z - hz),
        (face_x, hy, icon_z + hz),
        (face_x, hy * 0.12, icon_z + hz),
        (face_x, hy * 0.12, icon_z + hz * 0.12),
        (face_x, -hy, icon_z + hz * 0.12),
        (face_x, -hy, icon_z - hz),
    ]
    gear: list[tuple[float, float, float]] = []
    gr_y, gr_z = hy * 0.78, hz * 0.78
    for i in range(20):
        ang = (2.0 * math.pi * i) / 20.0 - math.pi / 2.0
        scale = 1.16 if i % 2 == 0 else 0.90
        gear.append((face_x - r * 0.02, gr_y * scale * math.cos(ang), icon_z + gr_z * scale * math.sin(ang)))
    gear.append(gear[0])
    hole = _ring_3d(face_x - r * 0.02, 0.0, icon_z, 0.0, gr_y * 0.34, 0.0, 0.0, 0.0, gr_z * 0.34, max(8, n // 12))
    word_z = icon_z - hz - r * 0.22
    ww = r * 1.38
    lh = r * 0.19
    lw = ww / 7.2
    letters: list[list[tuple[float, float, float]]] = []
    cy = -ww * 0.50
    for ch in "gearbox":
        flat = _gearbox_block_letter(0.0, 0.0, lw * 0.94, lh, ch)
        letters.append([(face_x, cy + y, word_z + x) for x, y in flat])
        cy += lw
    sw_z = word_z - r * 0.34
    sw_w = ww * 0.96
    sw_h = r * 0.075
    sw_gap = sw_w / 8.4
    software: list[list[tuple[float, float, float]]] = []
    cy = -sw_w * 0.48
    for _ in range(8):
        flat = _gearbox_block_letter(0.0, 0.0, sw_gap * 0.58, sw_h, "s")
        software.append([(face_x, cy + y, sw_z + x) for x, y in flat])
        cy += sw_gap
    n_icon = max(10, min(n, int(round(n * 0.40))))
    n_word = max(8, min(n - n_icon, int(round(n * 0.42))))
    n_sw = max(0, n - n_icon - n_word)
    n_frame = max(4, n_icon // 3)
    n_gear = max(4, n_icon // 3)
    n_hole = max(0, n_icon - n_frame - n_gear)
    icon_pts = _sample_polyline_3d(frame, n_frame)
    icon_pts.extend(_sample_polyline_3d(gear, n_gear))
    if n_hole:
        icon_pts.extend(hole[:n_hole])
    word_pts: list[tuple[float, float, float]] = []
    if n_word and letters:
        for letter, count in zip(letters, _split_counts(n_word, len(letters))):
            if count:
                word_pts.extend(_sample_polyline_3d(letter, count))
    sw_pts: list[tuple[float, float, float]] = []
    if n_sw and software:
        for bar, count in zip(software, _split_counts(n_sw, len(software))):
            if count:
                sw_pts.extend(_sample_polyline_3d(bar, count))
    return _lift_above_ground(_take_n_points(icon_pts, n_icon) + word_pts + sw_pts)[:n]


def _offsets_globe(
    n: int, radius: float, spacing: float = _DEFAULT_SPACING
) -> list[tuple[float, float, float]]:
    """House-sized lat/lon wireframe. Do not grow with count — huge globes froze the session."""
    del spacing
    n = max(0, int(n))
    if n <= 0:
        return []
    r = min(max(150.0, float(radius) * 0.78), _MAX_GLOBE_RADIUS)
    cx, cy = 0.0, 0.0
    cz = r + 52.0
    if n == 1:
        return _lift_above_ground([(cx, cy, cz + r)])
    meridians = 8 if n >= 40 else (6 if n >= 16 else 4)
    lat_rings = 5 if n >= 40 else (3 if n >= 16 else 2)
    pts: list[tuple[float, float, float]] = [(cx, cy, cz + r)]
    if n > 1:
        pts.append((cx, cy, cz - r))
    n_left = max(0, n - len(pts))
    n_lat = int(round(n_left * 0.38))
    n_mer = n_left - n_lat
    per_m = max(1, (n_mer + meridians - 1) // meridians)
    for mi in range(meridians):
        ang = (2.0 * math.pi * mi) / meridians
        ca, sa = math.cos(ang), math.sin(ang)
        for k in range(per_m):
            if len(pts) >= n:
                break
            t = (k + 1) / (per_m + 1)
            elev = -math.pi / 2.0 + t * math.pi
            rr = r * math.cos(elev)
            z = cz + r * math.sin(elev)
            pts.append((cx + rr * ca, cy + rr * sa, z))
        if len(pts) >= n:
            break
    remain = n - len(pts)
    if remain > 0:
        ring_counts = _split_counts(remain, lat_rings)
        for ring_i, count in enumerate(ring_counts):
            if count <= 0:
                continue
            u = (ring_i + 1) / (lat_rings + 1)
            elev = -math.pi / 2.0 + u * math.pi
            rr = r * math.cos(elev)
            z = cz + r * math.sin(elev)
            cap = max(3, int((2.0 * math.pi * max(28.0, abs(rr))) / 26.0))
            count = min(count, cap)
            for k in range(count):
                ang = (2.0 * math.pi * (k + 0.5)) / count
                pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang), z))
                if len(pts) >= n:
                    break
            if len(pts) >= n:
                break
    i = 0
    while len(pts) < n:
        i += 1
        t = (i + 0.5) / max(1, n)
        z = 1.0 - 2.0 * t
        rxy = math.sqrt(max(0.0, 1.0 - z * z))
        ang = i * math.pi * (3.0 - math.sqrt(5.0))
        pts.append((cx + r * rxy * math.cos(ang), cy + r * rxy * math.sin(ang), cz + r * z))
        if i > n * 2:
            break
    return _lift_above_ground(pts[:n])


def _offsets_pyramid(n: int, spacing: float) -> list[tuple[float, float, float]]:
    gap = max(52.0, float(spacing) * 0.50)
    n = max(0, int(n))
    rows = max(1, int(math.ceil((math.sqrt(1.0 + 8.0 * max(1, n)) - 1.0) / 2.0)))
    span = gap * 0.90 * max(0, rows - 1) + gap * 0.35
    if span > _MAX_PYRAMID_SPAN:
        gap *= _MAX_PYRAMID_SPAN / span
    out: list[tuple[float, float, float]] = []
    row = 1
    placed = 0
    while placed < n:
        count = min(row, n - placed)
        fx = gap * 0.35 + (row - 1) * gap * 0.90
        for col in range(count):
            ry = (col - 0.5 * (count - 1)) * gap
            out.append((fx, ry, 0.0))
        placed += count
        row += 1
    return out


def _offsets_hexagon(n: int, radius: float) -> list[tuple[float, float, float]]:
    verts: list[tuple[float, float]] = []
    for i in range(6):
        ang = math.pi / 6 + i * math.pi / 3
        verts.append((radius * math.cos(ang), radius * math.sin(ang)))
    return _sample_polyline(verts, n, closed=True)


def _offsets_honeycomb(n: int, spacing: float) -> list[tuple[float, float, float]]:
    directions = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))
    seen: set[tuple[int, int]] = {(0, 0)}
    coords: list[tuple[int, int]] = [(0, 0)]
    frontier = [(0, 0)]
    while len(coords) < n and frontier:
        nxt: list[tuple[int, int]] = []
        for q, r in frontier:
            for dq, dr in directions:
                cell = (q + dq, r + dr)
                if cell in seen:
                    continue
                seen.add(cell)
                nxt.append(cell)
                coords.append(cell)
                if len(coords) >= n:
                    break
            if len(coords) >= n:
                break
        frontier = nxt
    size = max(40.0, spacing)
    out: list[tuple[float, float, float]] = []
    for q, r in coords[:n]:
        right = size * (math.sqrt(3.0) * q + math.sqrt(3.0) * 0.5 * r)
        forward = size * 1.6 + size * 1.5 * r
        out.append((forward, right, 0.0))
    return out


def _offsets_scatter(n: int, radius: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    rng = random.Random(n * 7919 + int(radius))
    for _ in range(n):
        ang = rng.random() * 2.0 * math.pi
        rad = radius * math.sqrt(rng.random())
        out.append((rad * math.cos(ang) + radius * 0.15, rad * math.sin(ang), 0.0))
    return out


def _offsets_nova(n: int, radius: float) -> list[tuple[float, float, float]]:
    """Final pulse resting spots: Fibonacci sphere in front. Dump packs to a small ball first."""
    n = max(0, int(n))
    if n <= 0:
        return []
    r = max(180.0, min(520.0, float(radius) * 1.45))
    if n == 1:
        return [(r * 0.15, 0.0, r * 0.35)]
    golden = math.pi * (3.0 - math.sqrt(5.0))
    out: list[tuple[float, float, float]] = []
    for index in range(n):
        # Even area on the sphere, then lift so the bottom sits above ground.
        y = 1.0 - (2.0 * index) / max(1, n - 1)
        rr = math.sqrt(max(0.0, 1.0 - y * y))
        theta = golden * index
        lx = r * rr * math.cos(theta)
        ly = r * rr * math.sin(theta)
        lz = r * y + r + 48.0
        out.append((lx, ly, lz))
    return out


def _offsets_poisson(n: int, radius: float, spacing: float) -> list[tuple[float, float, float]]:
    """Filled scatter patch (min distance) in front of the player — not random dump spit."""
    min_d = max(48.0, spacing * 0.55)
    min_d2 = min_d * min_d
    rad = max(radius * 1.05, min_d * math.sqrt(max(1.0, n)) * 0.62)
    rng = random.Random(n * 104729 + int(radius * 10))
    out: list[tuple[float, float, float]] = []
    attempts = 0
    limit = max(1200, n * 60)
    while len(out) < n and attempts < limit:
        attempts += 1
        ang = rng.random() * 2.0 * math.pi
        dist = rad * math.sqrt(rng.random())
        x = dist * math.cos(ang)
        y = dist * math.sin(ang)
        if any((x - px) ** 2 + (y - py) ** 2 < min_d2 for px, py, _pz in out):
            continue
        out.append((x, y, 0.0))
    while len(out) < n:
        t = len(out) / max(1, n)
        ang = t * 2.0 * math.pi * 3.0
        r = min_d * (1.15 + len(out) * 0.07)
        out.append((r * math.cos(ang), r * math.sin(ang), 0.0))
    return out[:n]


def _offsets_star_filled(n: int, radius: float) -> list[tuple[float, float, float]]:
    layers = max(1, int(math.ceil(math.sqrt(n / 5.0))))
    out: list[tuple[float, float, float]] = []
    remaining = n
    for layer in range(layers):
        if remaining <= 0:
            break
        count = min(remaining, max(5, n // layers + (1 if layer == 0 else 0)))
        scale = 1.0 - 0.18 * layer
        out.extend(_offsets_star(count, radius * scale, radius * 0.3 * scale))
        remaining -= count
    return out[:n]


def _offsets_heart(n: int, radius: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    for index in range(n):
        t = (index / max(1, n)) * 2.0 * math.pi
        # Classic heart parametric, scaled
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        scale = radius / 18.0
        out.append((y * scale, x * scale, 0.0))  # forward=y, right=x so heart faces player-forward
    return out


def _offsets_line(
    n: int, spacing: float, line_length: float = _DEFAULT_LINE_LENGTH
) -> list[tuple[float, float, float]]:
    """Left-to-right in front of the player. Pack denser when N is large — never grow past max."""
    out: list[tuple[float, float, float]] = []
    n = max(1, int(n))
    spacing = _clamp_f(spacing, _MIN_SPACING, _MAX_SPACING, _DEFAULT_SPACING)
    length = _clamp_f(line_length, _MIN_LINE_LENGTH, _MAX_LINE_LENGTH, _DEFAULT_LINE_LENGTH)
    length = min(float(length), float(_MAX_LINE_SPAN))
    fwd = max(80.0, min(200.0, spacing * 0.55))
    if n <= 1:
        return [(fwd, 0.0, 0.0)]
    gap = length / float(n - 1)
    start = -0.5 * length
    for index in range(n):
        out.append((fwd, start + index * gap, 0.0))
    return out


def _offsets_grid(n: int, spacing: float) -> list[tuple[float, float, float]]:
    cols = max(2, int(round(math.sqrt(max(1, n)))))
    gap = max(52.0, float(spacing) * 0.70)
    out: list[tuple[float, float, float]] = []
    for index in range(n):
        row = index // cols
        col = index % cols
        width = min(cols, n - row * cols)
        fx = gap * 0.35 + row * gap
        ry = (col - 0.5 * (width - 1)) * gap
        out.append((fx, ry, 0.0))
    return out


def _unique_pile_centers(keys: list[str], radius: float, spacing: float) -> dict[str, tuple[float, float]]:
    unique = list(dict.fromkeys(keys))
    k = max(1, len(unique))
    cols = max(3, int(math.ceil(math.sqrt(k))))
    rows = int(math.ceil(k / cols))
    gap_x = max(spacing * 2.2, radius * 0.95)
    gap_y = max(spacing * 2.0, radius * 0.85)
    fwd_base = max(radius * 1.35, spacing * 2.2)
    centers: dict[str, tuple[float, float]] = {}
    for i, name in enumerate(unique):
        row, col = divmod(i, cols)
        cx = fwd_base + row * gap_x * 0.35
        cy = (col - 0.5 * (cols - 1)) * gap_y + (row - 0.5 * max(0, rows - 1)) * gap_y * 0.12
        centers[name] = (cx, cy)
    return centers


def _pile_grid_local(
    cx: float,
    cy: float,
    index_in_pile: int,
    *,
    gap: float,
    stack: float,
    cols: int = 4,
) -> tuple[float, float, float]:
    row, col = divmod(int(index_in_pile), max(1, int(cols)))
    layer = 0 if stack <= 0.0 else (int(index_in_pile) // (max(1, int(cols)) * 16))
    lx = cx + (col - 1.5) * gap
    ly = cy + row * gap
    return lx, ly, layer * stack


def _type_pile_centers(types: list[str], radius: float, spacing: float) -> dict[str, tuple[float, float]]:
    preferred = (
        "assault_rifle",
        "smg",
        "shotgun",
        "sniper",
        "pistol",
        "heavy",
        "weapon",
        "shield",
        "grenade",
        "classmod",
        "repkit",
        "other",
    )
    rank = {name: i for i, name in enumerate(preferred)}
    unique = list(dict.fromkeys(types))
    unique.sort(key=lambda name: (rank.get(name, 100), name))
    centers: dict[str, tuple[float, float]] = {}
    k = max(1, len(unique))
    lane = max(spacing * 2.6, radius * 1.15)
    start = -0.5 * (k - 1) * lane
    fwd = max(radius * 1.35, spacing * 2.2)
    for i, name in enumerate(unique):
        centers[name] = (fwd, start + i * lane)
    return centers


# --- teleport / physics -------------------------------------------------------

def _physics_components(inv: Any) -> list[Any]:
    """Pickup primitive only. Live dumps: RootPrimitiveComponent is GbxSkeletalMeshComponent."""
    if not _live(inv):
        return []
    out: list[Any] = []
    for name in ("RootPrimitiveComponent", "RootComponent", "CapsuleComponent"):
        try:
            comp = getattr(inv, name, None)
        except Exception:
            comp = None
        if comp is None:
            continue
        out.append(comp)
        break
    return out


def _zero_velocity(inv: Any) -> None:
    zero = _make_vector(0.0, 0.0, 0.0)
    for target in _physics_components(inv):
        fn = getattr(target, "SetPhysicsLinearVelocity", None)
        if callable(fn):
            try:
                fn(zero)
            except Exception:
                pass
        ang = getattr(target, "SetPhysicsAngularVelocityInRadians", None) or getattr(
            target, "SetPhysicsAngularVelocity", None
        )
        if callable(ang):
            try:
                ang(zero)
            except Exception:
                pass
        sleep = getattr(target, "PutRigidBodyToSleep", None) or getattr(target, "PutAllRigidBodiesToSleep", None)
        if callable(sleep):
            try:
                sleep()
            except Exception:
                pass
    # Live dump: keep RepMovement sleep so guests don't get a physics launch.
    try:
        movement = getattr(inv, "ReplicatedMovement", None)
        if movement is not None:
            try:
                setattr(movement, "LinearVelocity", zero)
            except Exception:
                pass
            try:
                setattr(movement, "AngularVelocity", zero)
            except Exception:
                pass
            try:
                setattr(movement, "bSimulatedPhysicSleep", True)
            except Exception:
                pass
            try:
                setattr(movement, "bRepPhysics", False)
            except Exception:
                pass
            # Never reassign the RepMovement struct in shipping BL4; native
            # pickup destruction can race this copy and AV pyunrealsdk.
    except Exception:
        pass


def _set_pickup_collision(inv: Any, *, block: bool) -> None:
    """Query-only while shaping so one tipped gun cannot knock the rest across the floor.

    Overlap queries stay on so the player can still pick the item up.
    """
    # ECollisionEnabled: NoCollision=0, QueryOnly=1, PhysicsOnly=2, QueryAndPhysics=3
    mode = 3 if block else 1
    for comp in _physics_components(inv):
        fn = getattr(comp, "SetCollisionEnabled", None)
        if callable(fn):
            try:
                fn(mode)
            except Exception:
                try:
                    fn("QueryAndPhysics" if block else "QueryOnly")
                except Exception:
                    pass
        notify = getattr(comp, "SetNotifyRigidBodyCollision", None)
        if callable(notify):
            try:
                notify(bool(block))
            except Exception:
                pass


def _set_physics(inv: Any, enabled: bool, *, keep_grab_collision: bool = False) -> None:
    """enabled=False pins the pickup so gravity cannot yank it out of a shape slot.

    keep_grab_collision=True leaves QueryAndPhysics on while frozen so lobby guests
    can still interact with silhouette items (QueryOnly was leaving only the floor pile grabable).

    Never call ForceDisableSimulatePhysics — it sticks and leaves lobby mates unable
    to Use even after a later SetSimulatePhysics(True) / world unlock (3.8.172).
    """
    if not _uobject_addr(inv):
        return
    on = bool(enabled)
    for comp in _physics_components(inv):
        fn = getattr(comp, "SetSimulatePhysics", None)
        if callable(fn):
            try:
                fn(on)
            except Exception:
                pass
        grav = getattr(comp, "SetEnableGravity", None)
        if callable(grav):
            try:
                grav(on)
            except Exception:
                pass
    if on:
        _set_pickup_collision(inv, block=True)
    else:
        _set_pickup_collision(inv, block=bool(keep_grab_collision))
        _zero_velocity(inv)


def _flatten_rotation(inv: Any, yaw: float, pitch: float = 0.0, roll: float = 0.0) -> None:
    """Pin a pickup's rotator. Pitch 90 stands a gun up so silhouettes can use height."""
    rot = _make_rotator(float(pitch), math.degrees(yaw), float(roll))
    for name in ("K2_SetActorRotation", "SetActorRotation"):
        fn = getattr(inv, name, None)
        if not callable(fn):
            continue
        try:
            fn(rot, False)
            return
        except Exception:
            try:
                fn(rot)
                return
            except Exception:
                pass


def current_drop_mode() -> str:
    return str(_drop_mode or "none")


_net_push_window_at: float = 0.0
_net_push_window_n: int = 0
# Hard cap — Place Fully house (~250+) ForceNetUpdates in one frame AVs the host.
_NET_PUSH_WINDOW_SEC = 0.05
_NET_PUSH_PER_WINDOW = 6


def _force_net_update(inv: Any, *, coop_pin: bool = False, guest_push: bool = False) -> bool:
    """One net flush. Returns False if skipped (budget / quiet / dead) so callers can retry."""
    global _net_push_window_at, _net_push_window_n
    if (guest_push or coop_pin) and _progression_network_busy():
        return False
    # Join stream/GC turns wrappers into 0xffffffffffffffff mid-call — bail first.
    if not _live(inv):
        return False
    if _in_join_quiet() and guest_push:
        # Guest ForceNetUpdate during join quiet is the place_fully + joiner AV.
        return False
    addr0 = _uobject_addr(inv)
    if not addr0:
        return False
    try:
        if _pickup_skip_shape(inv):
            return False
    except Exception:
        return False
    if guest_push or coop_pin:
        now = time.monotonic()
        if now - _net_push_window_at >= _NET_PUSH_WINDOW_SEC:
            _net_push_window_at = now
            _net_push_window_n = 0
        # Pickup-safe publish: slightly higher cap, still bounded (no 14/window lag).
        push_cap = _NET_PUSH_PER_WINDOW
        try:
            if guest_push and _coop_pickup_safe_active:
                push_cap = 8
        except Exception:
            push_cap = _NET_PUSH_PER_WINDOW
        if _net_push_window_n >= push_cap:
            return False
    try:
        for name in ("SetReplicates", "SetReplicateMovement"):
            if _uobject_addr(inv) != addr0:
                return False
            fn = getattr(inv, name, None)
            if callable(fn):
                try:
                    fn(True)
                except Exception:
                    pass
        if guest_push:
            if _uobject_addr(inv) != addr0:
                return False
            dorm = getattr(inv, "SetNetDormancy", None)
            if callable(dorm):
                try:
                    dorm(3)  # DORM_Never
                except Exception:
                    pass
        try:
            if _uobject_addr(inv) != addr0:
                return False
            inv.bReplicates = True
            inv.bReplicateMovement = True
            inv.bAlwaysRelevant = bool(guest_push or coop_pin)
            inv.NetUpdateFrequency = 40.0 if guest_push else (24.0 if coop_pin else 100.0)
        except Exception:
            pass
        flushed = False
        for name in ("ForceNetUpdate", "FlushNetDormancy"):
            if _uobject_addr(inv) != addr0:
                return False
            fn = getattr(inv, name, None)
            if callable(fn):
                try:
                    fn()
                    flushed = True
                except Exception:
                    return False
                break
        # Wrapper can die mid-ForceNet — never touch it again.
        if _uobject_addr(inv) != addr0:
            return False
        if flushed and (guest_push or coop_pin):
            _net_push_window_n += 1
        return bool(flushed)
    except Exception:
        return False


def _relax_pinned_net_load() -> None:
    """After shaping, drop net priority so other world loot renders again."""
    global _coop_relax_at
    if _want_coop_replicate() and _pinned_slots and any(row.get("hold") for row in _pinned_slots):
        _coop_relax_at = time.monotonic() + 45.0
        return
    _coop_relax_at = 0.0
    for row in list(_pinned_slots):
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr)
        if inv is None:
            continue
        try:
            inv.bAlwaysRelevant = False
            inv.NetUpdateFrequency = 12.0
        except Exception:
            pass


def _want_coop_replicate() -> bool:
    """Guests already in lobby need a net push; joiners get serial re-apply instead."""
    try:
        return int(_party_count()) >= 2
    except Exception:
        return False


def _should_replicate_pin_now() -> bool:
    """Co-op net push only when shaping is idle — never mid-dump (AV + guest feet-spit)."""
    if not _want_coop_replicate():
        return False
    if _land_active and not _landing_settle_done:
        return False
    if _float_jobs:
        return False
    return True


_burst_replicate_at: float = 0.0
_coop_pins_synced: int = 0
_guest_sync_cursor: int = 0
_guest_sync_active: bool = False
_guest_sync_last: float = 0.0
_coop_tail_throttle_at: float = 0.0
_guest_sync_refresh_at: float = 0.0
_coop_tail_pin_count: int = 0
_coop_hold_sync_at: float = 0.0
_coop_hold_sync_cursor: int = 0
_coop_relax_at: float = 0.0
_join_quiet_until: float = 0.0
_join_refresh_needed: bool = False
_join_guest_boost_until: float = 0.0
_join_hold_freeze_at: float = 0.0
_join_hold_repin_last: float = 0.0
_join_hold_rebind_at: float = 0.0
_join_quiet_started_at: float = 0.0
_hold_repin_cursor: int = 0
_join_serial_reapply_active: bool = False
_join_serial_reapply_at: float = 0.0
_join_serial_reapply_cursor: int = 0
_guest_maint_cursor: int = 0
_guest_maint_last: float = 0.0


def _cancel_join_reapply_work() -> None:
    """Drop late-join mirror / serial respawn state (menu/travel must not respawn 1000+ stale entries)."""
    global _join_reapply_pending, _join_reapply_at, _join_serial_reapply_active
    global _join_serial_reapply_at, _join_serial_reapply_cursor, _join_quiet_until
    global _join_refresh_needed, _join_quiet_started_at, _join_guest_boost_until
    _join_reapply_pending = False
    _join_reapply_at = 0.0
    _join_serial_reapply_active = False
    _join_serial_reapply_at = 0.0
    _join_serial_reapply_cursor = 0
    _join_quiet_until = 0.0
    _join_quiet_started_at = 0.0
    _join_refresh_needed = False
    _join_guest_boost_until = 0.0


def _clear_stale_layout_entries() -> None:
    """Layout mirror list without live pins is unsafe after menu/travel (duplicate spawns / AV)."""
    global _last_layout
    _last_layout["entries"] = []
    _last_layout["applied_at"] = 0.0


def _schedule_orphan_pickup_absorb() -> None:
    """After abandon, mark world pickups untouchable on next in-world tick (items may still render)."""
    global _absorb_orphans_after_abandon, _absorb_orphans_at
    _absorb_orphans_after_abandon = True
    _absorb_orphans_at = time.monotonic() + 0.35


def _absorb_orphan_pickups_if_due(now: float | None = None) -> None:
    """One-shot: frozen shape loot left in the level after menu — never re-catch or re-pin."""
    global _absorb_orphans_after_abandon, _drop_preexisting, _drop_seen
    if not _absorb_orphans_after_abandon:
        return
    t = time.monotonic() if now is None else float(now)
    if t < float(_absorb_orphans_at or 0.0):
        return
    _absorb_orphans_after_abandon = False
    try:
        from .session_guards import session_safe

        if not session_safe():
            _schedule_orphan_pickup_absorb()
            return
    except Exception:
        pass
    added = 0
    try:
        for addr, inv in _raw_pickup_scan(fresh=True):
            if not addr or inv is None:
                continue
            key = _key_for_addr(int(addr))
            if key not in _drop_preexisting:
                _drop_preexisting.add(key)
                added += 1
            try:
                ser = serial_from_pickup(inv)
                if ser:
                    _drop_preexisting.add(str(ser))
            except Exception:
                pass
        _drop_seen |= set(_drop_preexisting)
    except Exception:
        pass
    if added:
        _log_dev(f"Marked {added} orphan pickup(s) unmanaged after travel (left in world, not re-pinned).")


def held_pin_count() -> int:
    """Held silhouette pins currently frozen in-world (for other modules to throttle scans)."""
    return sum(1 for row in _pinned_slots if row.get("hold"))


def _held_coop_shape_active() -> bool:
    """Held 3D silhouette in a 2+ player lobby — guests need ongoing net freeze."""
    try:
        if not _want_coop_replicate() or not _pinned_slots:
            return False
        return any(row.get("hold") for row in _pinned_slots)
    except Exception:
        return False


def _join_hold_repin_cap(*, base: int = 32) -> int:
    """Scale host repin batches down for large held shapes — avoids join AV storms."""
    n = held_pin_count()
    if n <= 80:
        return int(base)
    if n <= 140:
        return max(12, min(int(base), 28))
    if n <= 220:
        return max(8, min(int(base), 20))
    return max(6, min(int(base), 14))


def _join_hold_rebind_recent(now: float | None = None, *, within: float = 2.5) -> bool:
    t = time.monotonic() if now is None else float(now)
    return t - float(_join_hold_rebind_at or 0.0) < float(within)


def _in_join_quiet(now: float | None = None) -> bool:
    t = time.monotonic() if now is None else float(now)
    return t < float(_join_quiet_until or 0.0)


def _rebind_hold_pins_after_join() -> int:
    """Remap held silhouette rows to live pickup wrappers after party grow (addrs change on stream/GC)."""
    hold_rows = [row for row in _pinned_slots if row.get("hold")]
    if not hold_rows:
        return 0
    global _pickup_by_addr
    # One find_all pass — never fresh=True per pin (400+ shapes × find_all AVs / hitches).
    try:
        invalidate_pickup_cache()
        scanned = _raw_pickup_scan(fresh=True)
    except Exception:
        scanned = []
    by_serial: dict[str, tuple[int, Any]] = {}
    by_addr: dict[int, Any] = {}
    for addr, inv in scanned:
        if not addr or inv is None or not _live(inv):
            continue
        addr_i = int(addr)
        by_addr[addr_i] = inv
        try:
            ser = serial_from_pickup(inv)
            if ser:
                by_serial[str(ser)] = (addr_i, inv)
        except Exception:
            pass
    if by_addr:
        _pickup_by_addr.update(by_addr)
    rebound = 0
    for row in hold_rows:
        row.pop("inv", None)
        row["misses"] = 0
        serial = str(row.get("serial") or "")
        addr = int(row.get("addr") or 0)
        inv = by_addr.get(addr)
        if (inv is None or not _live(inv)) and serial:
            hit = by_serial.get(serial)
            if hit is not None:
                row["addr"] = int(hit[0])
                inv = hit[1]
                _pickup_by_addr[int(hit[0])] = inv
        if inv is None or not _live(inv):
            try:
                inv = _resolve_pin_inv(row, fresh=False)
            except Exception:
                inv = None
        if inv is not None and _live(inv):
            rebound += 1
    global _join_hold_rebind_at
    if rebound:
        _join_hold_rebind_at = time.monotonic()
    return rebound


def _begin_join_quiet(*, seconds: float = 8.0, reason: str = "") -> None:
    """A joiner (especially console) streams/GCs pickups. Touching old wrappers AVs."""
    global _join_quiet_until, _guest_sync_active, _pickup_by_addr, _guest_sync_cursor
    global _join_refresh_needed, _guest_sync_last, _guest_maint_last, _join_quiet_started_at
    hold_shape = _held_coop_shape_active()
    hold_n = sum(1 for row in _pinned_slots if row.get("hold"))
    if hold_shape and hold_n > 120:
        seconds = max(float(seconds), min(20.0, 8.0 + hold_n * 0.015))
    until = time.monotonic() + max(3.0, float(seconds))
    if until <= float(_join_quiet_until or 0.0):
        return
    _join_quiet_until = until
    _join_quiet_started_at = time.monotonic()
    _join_refresh_needed = True
    hold_addrs = {
        int(row.get("addr") or 0)
        for row in _pinned_slots
        if row.get("hold") and int(row.get("addr") or 0)
    }
    if hold_shape:
        # Do not invalidate/wipe the addr map at join start — half the house lost wrappers
        # and fell before rebind could catch up.
        try:
            rebound = _rebind_hold_pins_after_join()
            repinned = _repin_host_hold_pins(
                limit=_join_hold_repin_cap(base=64), refresh_cache=False
            )
            if rebound or repinned:
                _log_dev(
                    f"Join hold prep: {rebound} pin(s) remapped, {repinned} re-frozen before quiet."
                )
        except Exception:
            pass
    else:
        preserved = {a: _pickup_by_addr[a] for a in hold_addrs if a in _pickup_by_addr}
        invalidate_pickup_cache()
        _pickup_by_addr = preserved
    for row in _pinned_slots:
        row.pop("inv", None)
        row["misses"] = 0
        if row.get("hold"):
            # Keep guest_ok — mass re-net during join quiet was waking physics and
            # half the house fell before heartbeat caught up.
            row.pop("guest_fail", None)
        else:
            row.pop("guest_ok", None)
            row.pop("guest_fail", None)
    if hold_shape:
        # Never go fully dark on net during join quiet — guests simulate physics and the house falls.
        global _join_guest_boost_until, _join_hold_freeze_at
        _join_guest_boost_until = time.monotonic() + 90.0
        _join_hold_freeze_at = 0.0
        _guest_sync_active = True
        _guest_sync_cursor = 0
        _guest_sync_last = 0.0
        _guest_maint_last = 0.0
        try:
            _purge_decor_pins()
        except Exception:
            pass
    else:
        _guest_sync_active = False
        _guest_sync_cursor = 0
    _log_dev(
        f"Join wrapper drop {seconds:.0f}s"
        + (f" ({reason})" if reason else "")
        + (
            " — held shape guest heartbeat stays on."
            if hold_shape
            else " — host pins stay frozen; no stale teleports."
        )
    )


def _poll_party_join(now: float) -> None:
    """Detect lobby joins before pin/guest ticks. Must run first on the shape poll."""
    global _party_poll_at, _join_reapply_pending, _join_reapply_at, _coop_pins_synced
    gap = 0.45 if _pinned_slots else 1.5
    if now - _party_poll_at < gap:
        return
    _party_poll_at = now
    try:
        count = _party_count()
    except Exception:
        return
    prev = int(_last_layout.get("party_count") or 0)
    if count <= 0:
        return
    if count > prev:
        pass  # mobility_runtime party-join scrub handles remote jump/gravity (not loot_shapes)
    if count > prev and _pinned_slots and _coop_pickup_safe_active:
        # Publish one bounded pass for the new actor channels, then unlock again.
        _last_layout["party_count"] = count
        _join_reapply_pending = False
        _arm_coop_pickup_safe(delay=0.15)
        _log_dev(f"Party grew {prev}->{count}; pickup-safe republish queued.")
        return
    if count > prev and _pinned_slots:
        _last_layout["party_count"] = count
        _begin_join_quiet(seconds=8.0, reason=f"party {prev}->{count}")
        _coop_pins_synced = 0
        if not _held_coop_shape_active():
            try:
                tracked = _build_layout_entries_from_pins()
                if tracked:
                    _log_dev(f"Join layout refresh: {tracked} mirror slot(s) for re-apply.")
            except Exception:
                pass
        _join_reapply_pending = True
        _join_reapply_at = float(_join_quiet_until) + 0.12
        _log_dev(f"Party grew {prev}->{count}; guest shape push after join quiet.")
    elif count > prev and not _pinned_slots:
        stale = len(_last_layout.get("entries") or [])
        if stale:
            _clear_stale_layout_entries()
            _cancel_join_reapply_work()
            _log_dev(f"Party grew {prev}->{count}; cleared {stale} stale layout entries (no live pins).")
        _last_layout["party_count"] = count
    elif count != prev:
        _last_layout["party_count"] = count


def _schedule_coop_pin_tail(*, limit: int = 2) -> None:
    """Drip a few slot poses to lobby while host builds — never every spawn."""
    global _coop_tail_throttle_at
    if _coop_pickup_safe_active:
        return
    if not _want_coop_replicate():
        return
    if _progression_network_busy():
        return
    now = time.monotonic()
    mid = bool(_land_active and not _landing_settle_done)
    # ULM / Spawn All mid-dump: host hitch was from ForceNet every catch.
    if mid and _bulk_healthcheck_mode:
        min_gap = 1.35
        push_n = 1
    elif mid:
        min_gap = 0.85
        push_n = 1
    else:
        min_gap = 0.14
        push_n = max(1, min(4, int(limit)))
    if now - _coop_tail_throttle_at < min_gap:
        return
    _coop_tail_throttle_at = now
    try:
        _coop_sync_pins_tail(
            limit=push_n,
            allow_mid_dump=True,
        )
    except Exception:
        pass


def _begin_guest_sync(*, force: bool = False, clear_ok: bool = True) -> None:
    """Spread co-op pin pushes over many ticks — never blast 200+ ForceNetUpdates at once."""
    global _guest_sync_cursor, _guest_sync_active, _guest_sync_last, _coop_pins_synced
    global _guest_sync_complete_announced
    if _coop_pickup_safe_active:
        _guest_sync_active = False
        return
    if _in_join_quiet():
        return
    if not _want_coop_replicate() or not _pinned_slots:
        return
    pending = sum(1 for row in _pinned_slots if not row.get("guest_ok"))
    if not force and _guest_sync_active and pending:
        return
    if not clear_ok and pending <= 0:
        return
    _guest_sync_cursor = 0
    _guest_sync_active = True
    _guest_sync_last = 0.0
    _coop_pins_synced = 0
    if clear_ok:
        _guest_sync_complete_announced = False
        for row in _pinned_slots:
            row.pop("guest_ok", None)
            row.pop("guest_fail", None)
        _log_dev(f"Co-op guest sync queued ({len(_pinned_slots)} held pin(s)).")
    else:
        _log_dev(f"Co-op guest sync retry ({pending}/{len(_pinned_slots)} pin(s) still pending).")


def _tick_coop_hold_guest_heartbeat(now: float, *, join_quiet: bool = False) -> int:
    """Re-net held silhouette pins so guests do not drop the house during join quiet or dormancy."""
    global _guest_maint_cursor, _guest_maint_last, _guest_sync_active
    if not _held_coop_shape_active():
        return 0
    # Mid Spawn All: skip guest net unless we are already in join quiet (house must stay up).
    if _mid_shape_dump() and not join_quiet:
        return 0
    if join_quiet:
        # Join quiet = stream/GC. Host-local freeze only — never ForceNetUpdate / guest push.
        elapsed = max(0.0, now - float(_join_quiet_started_at or 0.0))
        gap = 0.28 if elapsed < 2.0 else 0.45
        if now - _guest_maint_last < gap:
            return 0
        _guest_maint_last = now
        try:
            return _repin_host_hold_pins(
                limit=_join_hold_repin_cap(base=18), refresh_cache=False
            )
        except Exception:
            return 0
    # After settle: NEVER restamp guest_ok pins — that ForceNet freeze is why guests
    # float mid-air when they grab (host pin never drifts, heartbeat yanks).
    if bool(_landing_settle_done) and not _mid_shape_dump():
        pending = [row for row in _pinned_slots if not row.get("guest_ok") and not row.get("guest_skip")]
        if not pending:
            return 0
        hold_rows = pending
    else:
        hold_rows = [row for row in _pinned_slots if row.get("hold") or not row.get("guest_ok")]
    gap = 1.8
    hold_n = held_pin_count()
    if hold_n > 160:
        gap = 3.2
    elif hold_n > 80:
        gap = 2.4
    if now - _guest_maint_last < gap:
        return 0
    _guest_maint_last = now
    if not hold_rows:
        return 0
    budget = 3 if hold_n > 160 else (4 if hold_n > 80 else 8)
    synced = 0
    n = len(hold_rows)
    for _ in range(min(budget, n)):
        row = hold_rows[_guest_maint_cursor % n]
        _guest_maint_cursor += 1
        if row.get("guest_skip"):
            continue
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr) if addr else None
        if inv is None:
            inv = _resolve_pin_inv(row, fresh=False)
        if inv is None or not _live(inv):
            continue
        try:
            if _push_pin_to_guests(row, inv):
                row["guest_ok"] = True
                row.pop("guest_fail", None)
                synced += 1
        except Exception:
            continue
    if synced:
        _guest_sync_active = True
    return synced


def _abandon_unsyncable_guest_pins(*, max_fail: int = 12) -> int:
    """Drop ghost / non-gear pins that block co-op sync forever (AV spam)."""
    if not _pinned_slots:
        return 0
    dropped = 0
    kept: list[dict[str, Any]] = []
    for row in _pinned_slots:
        if row.get("guest_ok"):
            kept.append(row)
            continue
        fails = int(row.get("guest_fail") or 0)
        if fails < int(max_fail):
            kept.append(row)
            continue
        pool = str(row.get("pool_name") or "")
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr) if addr else None
        if inv is not None and not _is_shape_gear_pickup(inv, pool_name=pool):
            try:
                _hide_pickup(inv)
            except Exception:
                pass
            dropped += 1
            continue
        row["guest_ok"] = True
        row["guest_skip"] = True
        kept.append(row)
        dropped += 1
    if dropped:
        _pinned_slots[:] = kept
        _log_dev(f"Abandoned {dropped} guest-sync pin(s) (unresolvable / non-gear).")
    return dropped


def _tick_guest_sync(now: float) -> None:
    global _guest_sync_active, _guest_sync_last, _guest_sync_refresh_at, _guest_sync_complete_announced
    if _coop_pickup_safe_active:
        _guest_sync_active = False
        return
    # Local pins keep the shape stable; guest net pushes resume once the
    # progression RPC lane is idle.
    if _progression_network_busy():
        return
    join_quiet = _in_join_quiet(now)
    if join_quiet:
        if _held_coop_shape_active():
            _tick_coop_hold_guest_heartbeat(now, join_quiet=True)
        return
    join_boost = now < float(_join_guest_boost_until or 0.0)
    if _land_active and not _landing_settle_done and not join_boost:
        return
    if not _guest_sync_active or not _want_coop_replicate() or not _pinned_slots:
        _guest_sync_active = False
        return
    try:
        _purge_decor_pins()
    except Exception:
        pass
    gap = 0.18 if _landing_settle_done else 0.28
    hold_n = held_pin_count()
    if hold_n > 200:
        gap = max(gap, 0.75)
    elif hold_n > 120:
        gap = max(gap, 0.50)
    elif hold_n > 80:
        gap = max(gap, 0.35)
    if now - _guest_sync_last < gap:
        return
    _guest_sync_last = now
    if now - _guest_sync_refresh_at >= 3.5:
        _guest_sync_refresh_at = now
        if not (_bulk_healthcheck_mode and _land_active and not _landing_settle_done):
            try:
                # Large held shapes: skip fresh find_all during sync (AV / hitch).
                if not (_held_coop_shape_active() and hold_n > 60):
                    _refresh_live_pickups()
            except Exception:
                pass
    pending = [row for row in _pinned_slots if not row.get("guest_ok")]
    if not pending:
        if _held_coop_shape_active():
            if _tick_coop_hold_guest_heartbeat(now, join_quiet=False) > 0:
                return
        _guest_sync_active = False
        if not _guest_sync_complete_announced:
            _guest_sync_complete_announced = True
            _log_dev(f"Co-op guest sync complete ({len(_pinned_slots)} pin(s)).")
        try:
            if not (_want_coop_replicate() and _pinned_slots and any(row.get("hold") for row in _pinned_slots)):
                _relax_pinned_net_load()
        except Exception:
            pass
        return
    synced = 0
    held_shape = any(row.get("hold") for row in _pinned_slots)
    budget = 24 if join_boost else (12 if held_shape else 10)
    if join_boost and hold_n > 120:
        budget = min(budget, 4)
    elif join_boost and hold_n > 80:
        budget = min(budget, 6)
    elif held_shape and hold_n > 200:
        budget = min(budget, 2)
    elif held_shape and hold_n > 140:
        budget = min(budget, 3)
    elif held_shape and hold_n > 80:
        budget = min(budget, 5)
    if join_boost:
        max_fail = 128
    elif held_shape:
        max_fail = 96
    else:
        max_fail = 24
    fresh_resolve = True
    for row in pending:
        if synced >= budget:
            break
        inv = _resolve_pin_inv(row, fresh=fresh_resolve)
        fresh_resolve = False
        if inv is None or not _live(inv):
            row["guest_fail"] = int(row.get("guest_fail") or 0) + 1
            continue
        try:
            ok = _push_pin_to_guests(row, inv)
            if ok:
                row["guest_ok"] = True
                row.pop("guest_fail", None)
                synced += 1
            else:
                row["guest_fail"] = int(row.get("guest_fail") or 0) + 1
        except Exception:
            row["guest_fail"] = int(row.get("guest_fail") or 0) + 1
            continue
    still = [row for row in _pinned_slots if not row.get("guest_ok")]
    if not still:
        if _held_coop_shape_active():
            _tick_coop_hold_guest_heartbeat(now, join_quiet=False)
            return
        _guest_sync_active = False
        _log("Co-op shape synced for party.")
        _log_dev(f"Co-op guest sync complete ({len(_pinned_slots)} pin(s), {synced} pushed this tick).")
        try:
            if not (_want_coop_replicate() and _pinned_slots and any(row.get("hold") for row in _pinned_slots)):
                _relax_pinned_net_load()
        except Exception:
            pass
        return
    if all(int(row.get("guest_fail") or 0) >= max_fail for row in still):
        if held_shape:
            if _abandon_unsyncable_guest_pins(max_fail=max_fail):
                return
            for row in still:
                row["guest_ok"] = True
                row["guest_skip"] = True
            _coop_followup_waves = 0
            _guest_sync_active = bool(_held_coop_shape_active())
            _log_dev(
                f"Co-op guest sync gave up on {len(still)} stubborn pin(s) — heartbeat only."
            )
            return
        _guest_sync_active = False
        _log_dev(
            f"Co-op guest sync stopped ({len(still)}/{len(_pinned_slots)} unresolved, "
            f"{synced} pushed this tick)."
        )


def _tick_coop_hold_sync(now: float) -> None:
    """Disabled — GitHub 3.8.133 did not restamp with physics on (that flattened houses)."""
    del now
    return


def _coop_sync_pins_tail(*, limit: int = 4, allow_mid_dump: bool = False) -> int:
    """Push frozen silhouette slots to lobby guests (first guest-visible pose = slot XYZ)."""
    global _coop_pins_synced
    if _mid_shape_dump() and not allow_mid_dump:
        return 0
    if not _want_coop_replicate() or not _pinned_slots:
        return 0
    synced = 0
    budget = max(1, min(2 if (_mid_shape_dump() and allow_mid_dump) else 8, int(limit)))
    # Prefer newest pending pins so the live build keeps up with the host.
    pending = [row for row in _pinned_slots if not row.get("guest_ok")]
    if not pending:
        _coop_pins_synced = len(_pinned_slots)
        return 0
    # Walk newest-first during mid-dump so guests see the house grow where host just pinned.
    walk = list(reversed(pending)) if _mid_shape_dump() else pending
    for row in walk:
        if synced >= budget:
            break
        inv = _resolve_pin_inv(row, fresh=False)
        if inv is None:
            continue
        try:
            ok = _push_pin_to_guests(row, inv)
            if ok:
                _set_physics(inv, False, keep_grab_collision=True)
                _zero_velocity(inv)
                row["guest_ok"] = True
                synced += 1
        except Exception:
            continue
    done = sum(1 for row in _pinned_slots if row.get("guest_ok"))
    _coop_pins_synced = done
    if synced:
        _log_dev(f"Co-op pin tail: synced {synced} held slot(s) for lobby guests.")
    return synced


def _stamp_replicated_movement(inv: Any, loc: Any, rot: Any) -> None:
    """Write the server FRepMovement snapshot before ForceNetUpdate."""
    try:
        movement = getattr(inv, "ReplicatedMovement", None)
        if movement is None:
            return
        try:
            setattr(movement, "Location", loc)
        except Exception:
            pass
        try:
            setattr(movement, "Rotation", rot)
        except Exception:
            pass
        try:
            setattr(movement, "LinearVelocity", _make_vector(0.0, 0.0, 0.0))
        except Exception:
            pass
        # K2_TeleportTo + ForceNetUpdate publish the native transform. Do not
        # reassign this struct: it raced actor destruction and AV'd.
    except Exception:
        pass


def _teleport_pickup(
    inv: Any,
    x: float,
    y: float,
    z: float,
    yaw: float = 0.0,
    *,
    pitch: float = 0.0,
    roll: float = 0.0,
    freeze: bool | None = None,
    replicate: bool = True,
    guest_push: bool = False,
    keep_grab_collision: bool = True,
    require_net: bool = False,
) -> bool:
    """Freeze first, then K2_TeleportTo. Never physics-on (that flattened houses).

    keep_grab_collision defaults True so lobby guests can grab frozen shape slots
    (QueryOnly on 2D grids left interact-looking items that floated instead of picking up).
    """
    addr0 = _uobject_addr(inv)
    if not addr0:
        return False
    # Join stream: never net-push; host-local freeze only.
    if _in_join_quiet():
        replicate = False
        guest_push = False
    try:
        loc = _make_vector(x, y, z)
        rot = _make_rotator(float(pitch), math.degrees(yaw), float(roll))
        if _uobject_addr(inv) != addr0:
            return False
        if replicate:
            try:
                inv.bReplicateMovement = True
                inv.bAlwaysRelevant = True
            except Exception:
                pass
        if freeze is True:
            try:
                _set_physics(inv, False, keep_grab_collision=bool(keep_grab_collision))
            except Exception:
                pass
        if _uobject_addr(inv) != addr0:
            return False
        ok = False
        fn = getattr(inv, "K2_TeleportTo", None)
        if callable(fn):
            try:
                result = fn(loc, rot)
                ok = True if result is None else bool(result)
            except Exception:
                ok = False
        if ok and replicate:
            if _uobject_addr(inv) != addr0:
                return False
            _stamp_replicated_movement(inv, loc, rot)
            net_ok = _force_net_update(inv, coop_pin=True, guest_push=bool(guest_push))
            if require_net and not net_ok:
                # Budget skipped the flush — caller must retry (do not mark guest_ok).
                if freeze is True:
                    try:
                        _set_physics(inv, False, keep_grab_collision=bool(keep_grab_collision))
                        _zero_velocity(inv)
                    except Exception:
                        pass
                return False
        if ok and freeze is True:
            _set_physics(inv, False, keep_grab_collision=bool(keep_grab_collision))
            _zero_velocity(inv)
        return ok
    except Exception:
        addr = _uobject_addr(inv)
        if addr:
            _pickup_by_addr.pop(int(addr), None)
        return False


def _pin_pickup_to_slot(
    inv: Any,
    slot: tuple[float, float, float],
    *,
    index: int = 0,
    hold: bool | None = None,
) -> bool:
    """Freeze on the slot. Lobby: net the pose — dump XYZ never reaches guests."""
    if _shape_grab_excluded_inv(inv):
        return False
    pool_name = str(_land_slot_pools.get(int(index)) or "")
    if not _is_shape_gear_pickup(inv, pool_name=pool_name):
        try:
            _hide_pickup(inv)
        except Exception:
            pass
        return False
    x1, y1, z1 = slot
    yaw_r, pitch, roll = _rot_for_xyz(index, x1, y1, z1)
    if not _remember_inv(inv):
        return False
    pin_hold = _shape_hold_active() if hold is None else bool(hold)
    try:
        _set_physics(inv, False, keep_grab_collision=True)
    except Exception:
        pass
    coop = False
    try:
        coop = bool(_want_coop_replicate())
    except Exception:
        coop = False
    # Host freezes locally mid-dump; throttled guest push (~2/s) stamps slot XYZ for lobby.
    mid_dump = bool(_land_active and not _landing_settle_done)
    net_push = bool(coop and not mid_dump)
    ok = _teleport_pickup(
        inv,
        x1,
        y1,
        z1,
        yaw_r,
        pitch=pitch,
        roll=roll,
        freeze=True,
        replicate=net_push,
        guest_push=net_push,
        keep_grab_collision=True,
    )
    if ok:
        _set_physics(inv, False, keep_grab_collision=True)
        _zero_velocity(inv)
        _remember_pin(
            inv, x1, y1, z1, yaw_r, pitch=pitch, roll=roll, hold=pin_hold, slot_index=index
        )
        try:
            _track_layout_entry(inv, x1, y1, z1)
        except Exception:
            pass
        if coop and mid_dump:
            try:
                _schedule_coop_pin_tail(limit=2)
            except Exception:
                pass
        if net_push:
            try:
                _stamp_coop_spawn(inv, x1, y1, z1, yaw_r, pitch=pitch, roll=roll)
            except Exception:
                pass
    return ok


def _burst_replicate_pins(*, limit: int = 64) -> None:
    """Disabled — GitHub 3.8.133: restamping every dump/tick flattened shapes and froze the host."""
    del limit
    return


def _repin_all_for_guests(*, limit: int = 0, only_pending: bool = True) -> int:
    """Push pinned slots to lobby guests. Hard-capped — unlimited settle blasts AVd the host."""
    global _coop_pins_synced
    if not _want_coop_replicate() or not _pinned_slots:
        return 0
    # Large silhouettes: skip find_all here (AV / hitch); resolve from pin addrs.
    if held_pin_count() <= 80:
        try:
            _refresh_live_pickups()
        except Exception:
            pass
    rows = [
        row
        for row in list(_pinned_slots)
        if (not only_pending or not row.get("guest_ok"))
    ]
    total = len(rows)
    if total <= 0:
        _coop_pins_synced = len(_pinned_slots)
        return 0
    # Never ForceNetUpdate hundreds in one call (shiny house settle AV).
    hard_cap = 6 if held_pin_count() > 120 else (8 if held_pin_count() > 60 else 12)
    if int(limit or 0) <= 0:
        cap = hard_cap
    else:
        cap = max(1, min(total, int(limit), hard_cap))
    stamped = 0
    for row in rows[:cap]:
        inv = _resolve_pin_inv(row, fresh=False)
        if inv is None:
            continue
        try:
            ok = _push_pin_to_guests(row, inv)
            if ok:
                row["guest_ok"] = True
                stamped += 1
        except Exception:
            continue
    _coop_pins_synced = sum(1 for row in _pinned_slots if row.get("guest_ok"))
    if stamped:
        _log_dev(f"Co-op guest repin: {stamped}/{cap} held pin(s).")
    return stamped


def soft_clear_ground_loot() -> str:
    loot = sorted_ground_loot(include_consumables=True)
    away = _make_vector(100000.0, 100000.0, -1000000000.0)
    rot = _make_rotator()
    moved = 0
    for inv in loot["Pickups"] + loot["Gear"]:
        try:
            _set_physics(inv, True)
            inv.K2_TeleportTo(away, rot)
            moved += 1
        except Exception:
            continue
    global _status
    _status = f"Soft clear: moved {moved} item(s) out of play." if moved else "Soft clear: no ground loot found."
    _log(_status)
    return _status


def cleanup_world_loot() -> str:
    """Stronger tidy for Most used: stop floats/nova, clear pins, then soft-clear ground loot."""
    global _float_jobs, _pinned_slots, _status
    try:
        finish_drop_jobs()
    except Exception:
        _float_jobs = []
    try:
        _reset_nova_explode()
    except Exception:
        pass
    try:
        _pinned_slots = []
    except Exception:
        pass
    try:
        from . import shinies

        shinies.cancel_pending_shiny_drops("loot_cleanup")
    except Exception:
        pass
    soft = soft_clear_ground_loot()
    _status = f"Cleanup loot: stopped motion/pins, then {soft}"
    _log(_status)
    return _status


# --- serial extract (minimal LOV-style) ---------------------------------------

def _read_u64(address: int) -> int:
    addr = int(address or 0)
    if addr < 0x10000:
        return 0
    try:
        return int(ctypes.c_uint64.from_address(addr).value)
    except Exception:
        return 0


def _read_bytes(address: int, length: int) -> bytes:
    addr = int(address or 0)
    if addr < 0x10000 or length <= 0:
        return b""
    length = min(int(length), _ITEM_SERIAL_MAX_CHARS)
    try:
        buf = (ctypes.c_ubyte * length).from_address(addr)
        return bytes(buf)
    except Exception:
        return b""


def _identity_address(identity: Any) -> int:
    try:
        return int(identity._get_address())
    except Exception:
        return 0


def _looks_like_identity(value: Any) -> bool:
    """True for InventoryIdentity structs with a readable memory address.

    MSBT/LOV: InventoryIdentity is a WrappedStruct — ``type(value).__name__`` is
    often ``WrappedStruct``, so resolve via ``value._type.Name``. Do **not** gate
    on address-only ``_live()`` (that rejected every Identity).
    """
    if value is None:
        return False
    # Reject real UObjects (have Class + Name) mistaken for identity.
    try:
        _ = value.Name
        _ = value.Class
        return False
    except Exception:
        pass
    type_name = ""
    try:
        struct_type = getattr(value, "_type", None)
        if struct_type is not None:
            type_name = str(getattr(struct_type, "Name", "") or "")
    except Exception:
        type_name = ""
    if not type_name:
        try:
            type_name = type(value).__name__
        except Exception:
            return False
    if type_name != "InventoryIdentity":
        return False
    try:
        addr = _identity_address(value)
        return bool(addr and addr != 0xFFFFFFFFFFFFFFFF)
    except Exception:
        return False


def _identity_from_pickup(inv: Any) -> Any:
    paths = (
        ("Identity",),
        ("InventoryIdentity",),
        ("data", "Identity"),
        ("Data", "Identity"),
        ("item", "data", "Identity"),
        ("Item", "data", "Identity"),
        ("item", "Data", "Identity"),
        ("Item", "Identity"),
        ("InventoryItem", "Identity"),
        ("InventoryItem", "data", "Identity"),
        ("InventoryItem", "item", "data", "Identity"),
        ("AssociatedItem", "Identity"),
        ("PickupData", "Identity"),
    )
    for path in paths:
        node = inv
        try:
            for name in path:
                node = getattr(node, name)
        except Exception:
            continue
        if _looks_like_identity(node):
            return node
    for meth in ("GetIdentity", "GetInventoryIdentity"):
        fn = getattr(inv, meth, None)
        if callable(fn):
            try:
                node = fn()
                if _looks_like_identity(node):
                    return node
            except Exception:
                pass
    return None


def serial_from_pickup(inv: Any) -> str:
    if not _live(inv):
        return ""
    for attr in (
        "ItemSerialString",
        "ItemSerial",
        "SerialString",
        "Serial",
        "CachedSerial",
        "ItemSerialNumber",
    ):
        try:
            raw = getattr(inv, attr, None)
        except Exception:
            continue
        if raw is None:
            continue
        try:
            serial = str(raw).strip()
        except Exception:
            continue
        if serial.startswith("@U") and len(serial) >= 12 and "@U" not in serial[2:]:
            return serial
    identity = _identity_from_pickup(inv)
    if identity is not None:
        addr = _identity_address(identity)
        if addr and addr != 0xFFFFFFFFFFFFFFFF:
            try:
                data_addr = _read_u64(addr + _ITEM_SERIAL_POINTER_OFFSET)
                length = _read_u64(addr + _ITEM_SERIAL_LENGTH_OFFSET)
            except Exception:
                data_addr, length = 0, 0
            if (
                data_addr
                and data_addr != 0xFFFFFFFFFFFFFFFF
                and 8 <= int(length) <= _ITEM_SERIAL_MAX_CHARS
            ):
                try:
                    raw = _read_bytes(data_addr, int(length))
                    serial = raw.split(b"\x00", 1)[0].decode("ascii", "ignore").strip()
                except Exception:
                    serial = ""
                if serial.startswith("@U") and len(serial) >= 12 and "@U" not in serial[2:]:
                    return serial
    # Party Bay dig (VirtualQuery-safe) — same InventoryIdentity +0xA0 layout.
    try:
        from . import backpack_tools as _bp

        for src in (inv, getattr(inv, "Item", None), getattr(inv, "InventoryItem", None)):
            if src is None:
                continue
            hit = str(_bp._serial_from_source(src) or "").strip()
            if hit.startswith("@U") and len(hit) >= 12:
                return hit
    except Exception:
        pass
    return ""


def _spawn_serial_at(serial: str, x: float, y: float, z: float) -> bool:
    """Spawn @U near the player, then move the newest nearby pickup to (x,y,z)."""
    try:
        from .item_spawn.pearl_serial_spawn import try_deliver_serial_ground
    except Exception:
        try:
            from Squ1ggsBoostingTools.item_spawn.pearl_serial_spawn import try_deliver_serial_ground  # type: ignore
        except Exception as exc:
            _log(f"serial spawn import failed: {exc!r}")
            return False

    before = set()
    try:
        for inv in unrealsdk.find_all("InventoryPickup", False) or []:
            if _live(inv):
                before.add(id(inv))
    except Exception:
        pass

    try:
        ok = bool(try_deliver_serial_ground(serial, 1))
    except Exception as exc:
        _log(f"try_deliver_serial_ground failed: {exc!r}")
        return False
    if not ok:
        return False

    # Find a new pickup and teleport it to the shaped spot.
    newest = None
    try:
        for inv in unrealsdk.find_all("InventoryPickup", False) or []:
            if not _live(inv) or id(inv) in before:
                continue
            newest = inv
            break
    except Exception:
        newest = None
    if newest is None:
        # Fallback: move any gear closest to the player toward the target.
        return False
    return _teleport_pickup(newest, x, y, z)


def _hide_pickup(inv: Any) -> None:
    if not _live(inv):
        return
    try:
        away = _make_vector(100000.0, 100000.0, -1000000000.0)
        _set_physics(inv, True)
        inv.K2_TeleportTo(away, _make_rotator())
    except Exception:
        pass


# --- public arrange API -------------------------------------------------------

def _group_summary(shape: str, items: list[Any]) -> str:
    if shape == "type_piles":
        counts: dict[str, int] = {}
        for inv in items:
            key = _classify_gear_type(inv)
            counts[key] = counts.get(key, 0) + 1
    elif shape == "unique_piles":
        counts = {}
        for inv in items:
            key = _classify_exact_item(inv)
            counts[key] = counts.get(key, 0) + 1
    elif shape == "rarity_lanes":
        counts = {}
        for inv in items:
            key = _classify_rarity(inv)
            counts[key] = counts.get(key, 0) + 1
    else:
        return ""
    if not counts:
        return " (no groups)"
    parts = [f"{name} {n}" for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return " [" + ", ".join(parts) + "]"


def _assign_positions(
    items: list[Any],
    shape: str,
    *,
    ox: float,
    oy: float,
    oz: float,
    yaw: float,
    radius: float,
    spacing: float,
    per_ring: int,
    stack_height: float = 0.0,
    line_length: float = _DEFAULT_LINE_LENGTH,
) -> list[tuple[Any, float, float, float]]:
    if shape == "car":
        body, wheels = _car_part_offsets(len(items), radius)
        wheel_items: list[Any] = []
        body_items: list[Any] = []
        for inv in items:
            if _inv_is_car_wheel(inv):
                wheel_items.append(inv)
            else:
                body_items.append(inv)
        if len(wheel_items) > len(wheels):
            body_items = wheel_items[len(wheels) :] + body_items
            wheel_items = wheel_items[: len(wheels)]
        elif len(wheel_items) < len(wheels):
            need = len(wheels) - len(wheel_items)
            wheel_items.extend(body_items[:need])
            body_items = body_items[need:]
        placed: list[tuple[Any, float, float, float]] = []
        for inv, (lx, ly, lz) in zip(wheel_items, wheels):
            wx, wy, wz = _world_from_local(ox, oy, oz, yaw, lx, ly, lz)
            placed.append((inv, wx, wy, wz))
        for inv, (lx, ly, lz) in zip(body_items, body):
            wx, wy, wz = _world_from_local(ox, oy, oz, yaw, lx, ly, lz)
            placed.append((inv, wx, wy, wz))
        return placed

    if shape == "type_piles":
        groups: dict[str, list[Any]] = {}
        for inv in items:
            groups.setdefault(_classify_gear_type(inv), []).append(inv)
        centers = _type_pile_centers(list(groups.keys()), radius, spacing)
        placed: list[tuple[Any, float, float, float]] = []
        gap = max(55.0, float(spacing) * 0.42)
        step = max(0.0, float(stack_height))
        for gtype, bucket in groups.items():
            cx, cy = centers.get(gtype, (radius, 0.0))
            n = max(1, len(bucket))
            cols = max(3, int(math.ceil(math.sqrt(n))))
            rows = max(1, int(math.ceil(n / cols)))
            for i, inv in enumerate(bucket):
                row, col = divmod(i, cols)
                layer = 0 if step <= 0.0 else (i // (cols * rows))
                lx = cx + (col - 0.5 * (cols - 1)) * gap
                ly = cy + (row - 0.5 * (rows - 1)) * gap
                wx, wy, wz = _world_from_local(ox, oy, oz, yaw, lx, ly, layer * step)
                placed.append((inv, wx, wy, wz))
        return placed

    if shape == "unique_piles":
        groups: dict[str, list[Any]] = {}
        for inv in items:
            groups.setdefault(_classify_exact_item(inv), []).append(inv)
        centers = _unique_pile_centers(list(groups.keys()), radius, spacing)
        placed: list[tuple[Any, float, float, float]] = []
        gap = max(55.0, float(spacing) * 0.42)
        step = max(0.0, float(stack_height))
        for item_key, bucket in groups.items():
            cx, cy = centers.get(item_key, (radius, 0.0))
            n = max(1, len(bucket))
            cols = max(3, int(math.ceil(math.sqrt(n))))
            rows = max(1, int(math.ceil(n / cols)))
            for i, inv in enumerate(bucket):
                row, col = divmod(i, cols)
                layer = 0 if step <= 0.0 else (i // (cols * rows))
                lx = cx + (col - 0.5 * (cols - 1)) * gap
                ly = cy + (row - 0.5 * (rows - 1)) * gap
                wx, wy, wz = _world_from_local(ox, oy, oz, yaw, lx, ly, layer * step)
                placed.append((inv, wx, wy, wz))
        return placed

    if shape == "rarity_lanes":
        order = ("pearl", "legendary", "epic", "rare", "uncommon", "common", "other")
        groups: dict[str, list[Any]] = {name: [] for name in order}
        for inv in items:
            groups.setdefault(_classify_rarity(inv), []).append(inv)
        lanes = [name for name in order if groups.get(name)]
        placed: list[tuple[Any, float, float, float]] = []
        for lane_i, name in enumerate(lanes):
            bucket = groups[name]
            fx = spacing * 1.8 + lane_i * spacing * 1.85
            start = -0.5 * (len(bucket) - 1) * spacing
            for col, inv in enumerate(bucket):
                wx, wy, wz = _world_from_local(ox, oy, oz, yaw, fx, start + col * spacing, 0.0)
                placed.append((inv, wx, wy, wz))
        return placed

    offsets = shape_offsets(
        shape, len(items), radius=radius, spacing=spacing, per_ring=per_ring, line_length=line_length
    )
    placed = []
    for inv, (lx, ly, lz) in zip(items, offsets):
        wx, wy, wz = _world_from_local(ox, oy, oz, yaw, lx, ly, lz)
        placed.append((inv, wx, wy, wz))
    return placed


def quick_arrange(
    shape: str = "rings",
    *,
    radius: float = _DEFAULT_RADIUS,
    spacing: float = _DEFAULT_SPACING,
    per_ring: int = _DEFAULT_PER_RING,
    z_bias: float = _DEFAULT_Z_BIAS,
    stack_height: float = 0.0,
    include_consumables: bool = False,
    settle: str = "none",
    drop_height: float = _DEFAULT_DROP_HEIGHT,
    line_length: float = _DEFAULT_LINE_LENGTH,
) -> str:
    global _status, _last_layout, _float_jobs, _land_active, _drop_until
    global _deferred_catch_at, _deferred_catch_until, _drop_shape, _drop_origin, _drop_yaw
    global _landing_settle_done
    anchor = _player_anchor()
    if anchor is None:
        _status = "Quick Arrange: load into a character first."
        return _status
    # A previous dump may still own stale pin/flight wrappers. Stop tracking
    # without touching those actors before gathering a fresh list.
    _land_active = False
    _drop_until = 0.0
    _float_jobs = []
    _deferred_catch_at = 0.0
    _deferred_catch_until = 0.0
    _clear_pins()
    _drop_shape = _normalize_shape_name(shape)
    _pawn, ox, oy, oz, yaw = anchor
    oz = oz + float(z_bias)
    _drop_origin = (ox, oy, oz)
    _drop_yaw = yaw
    loot = sorted_ground_loot(include_consumables=include_consumables)
    gear = _shape_gear_list([inv for inv in loot["Gear"] if _live(inv)])
    consumables = [inv for inv in loot["Pickups"] if _live(inv)] if include_consumables else []

    # Consumables pile at feet; gear gets the shape.
    moved = 0
    for inv in consumables:
        if _teleport_pickup(inv, ox, oy, oz, yaw, freeze=False):
            moved += 1

    placed = _assign_positions(
        gear,
        shape,
        ox=ox,
        oy=oy,
        oz=oz,
        yaw=yaw,
        radius=radius,
        spacing=spacing,
        per_ring=per_ring,
        stack_height=stack_height,
        line_length=line_length,
    )
    entries: list[dict[str, Any]] = []
    moved += apply_settle(placed, mode=settle, drop_height=drop_height, yaw=yaw)
    try:
        _purge_decor_pins()
    except Exception:
        pass
    _arm_peel_clock()
    # Arrange is already settled — guest grab hand-off / Use hooks need this True.
    _landing_settle_done = True

    _last_layout.update(
        {
            "shape": shape,
            "radius": radius,
            "spacing": spacing,
            "per_ring": per_ring,
            "z_bias": z_bias,
            "stack_height": stack_height,
            "line_length": line_length,
            "settle": settle,
            "drop_height": drop_height,
            "include_consumables": include_consumables,
            "mode": "quick",
            "entries": entries,
            "party_count": _party_count(),
            "applied_at": time.time(),
        }
    )
    _status = f"Quick Arrange ({shape}): moved {moved} item(s).{_group_summary(shape, gear)}"
    _log(_status)
    return _status


def place_fully(
    shape: str = "rings",
    *,
    radius: float = _DEFAULT_RADIUS,
    spacing: float = _DEFAULT_SPACING,
    per_ring: int = _DEFAULT_PER_RING,
    z_bias: float = _DEFAULT_Z_BIAS,
    stack_height: float = 0.0,
    include_consumables: bool = False,
    settle: str = "none",
    drop_height: float = _DEFAULT_DROP_HEIGHT,
    line_length: float = _DEFAULT_LINE_LENGTH,
) -> str:
    """Hardened teleport using a fresh pickup gather; no raw serial memory reads."""
    global _status, _last_layout, _float_jobs, _land_active, _drop_until
    global _deferred_catch_at, _deferred_catch_until, _drop_shape, _drop_origin, _drop_yaw
    global _landing_settle_done
    anchor = _player_anchor()
    if anchor is None:
        _status = "Place Fully: load into a character first."
        return _status
    # Do not let old dump pins/flight jobs keep stale wrappers alive while this
    # action moves the same actors. That native overlap caused pyunrealsdk AVs.
    _land_active = False
    _drop_until = 0.0
    _float_jobs = []
    _deferred_catch_at = 0.0
    _deferred_catch_until = 0.0
    _clear_pins()
    _drop_shape = _normalize_shape_name(shape)
    _pawn, ox, oy, oz, yaw = anchor
    oz = oz + float(z_bias)
    _drop_origin = (ox, oy, oz)
    _drop_yaw = yaw
    loot = sorted_ground_loot(include_consumables=include_consumables)
    gear = _shape_gear_list([inv for inv in loot["Gear"] if _live(inv)])
    consumables = [inv for inv in loot["Pickups"] if _live(inv)] if include_consumables else []

    for inv in consumables:
        _teleport_pickup(inv, ox, oy, oz, yaw)

    placed = _assign_positions(
        gear,
        shape,
        ox=ox,
        oy=oy,
        oz=oz,
        yaw=yaw,
        radius=radius,
        spacing=spacing,
        per_ring=per_ring,
        stack_height=stack_height,
        line_length=line_length,
    )

    teleported = 0
    settle_l = normalize_drop_mode(settle)
    teleported = apply_settle(placed, mode=settle_l, drop_height=drop_height, yaw=yaw)
    try:
        purged = _purge_decor_pins()
        if purged:
            _log_dev(f"Place Fully purged {purged} stringlight/placeable pin(s).")
    except Exception:
        pass
    _arm_peel_clock()
    _landing_settle_done = True
    tracked = _build_layout_entries_from_pins()

    _last_layout.update(
        {
            "shape": shape,
            "radius": radius,
            "spacing": spacing,
            "per_ring": per_ring,
            "z_bias": z_bias,
            "stack_height": stack_height,
            "line_length": line_length,
            "settle": settle_l,
            "drop_height": drop_height,
            "include_consumables": include_consumables,
            "mode": "place_fully",
            "entries": list(_last_layout.get("entries") or []),
            "party_count": _party_count(),
            "applied_at": time.time(),
        }
    )
    _status = (
        f"Place Fully ({shape}/{settle_l}): {teleported} placed, "
        f"tracked {tracked} serial(s) for co-op."
        f"{_group_summary(shape, gear)}"
    )
    _log(_status)
    return _status


def reapply_last_layout() -> str:
    """Re-spawn recorded serials at stored world coords (late-joiner recovery)."""
    global _status
    if _land_active and not _landing_settle_done:
        return "reapply skipped: dump in progress."
    entries = list(_last_layout.get("entries") or [])
    if not entries:
        # No serials captured — re-run last mode on current ground loot.
        mode = str(_last_layout.get("mode") or "place_fully")
        kwargs = {
            "radius": float(_last_layout.get("radius") or _DEFAULT_RADIUS),
            "spacing": float(_last_layout.get("spacing") or _DEFAULT_SPACING),
            "per_ring": int(_last_layout.get("per_ring") or _DEFAULT_PER_RING),
            "z_bias": float(_last_layout.get("z_bias") or _DEFAULT_Z_BIAS),
            "stack_height": float(_last_layout.get("stack_height") or 0.0),
            "line_length": float(_last_layout.get("line_length") or _DEFAULT_LINE_LENGTH),
            "settle": str(_last_layout.get("settle") or "none"),
            "drop_height": float(_last_layout.get("drop_height") or _DEFAULT_DROP_HEIGHT),
            "include_consumables": bool(_last_layout.get("include_consumables")),
        }
        shape = str(_last_layout.get("shape") or "rings")
        if mode == "quick":
            return quick_arrange(shape, **kwargs)
        return place_fully(shape, **kwargs)

    ok_n = 0
    for row in entries:
        serial = str(row.get("serial") or "")
        if not serial.startswith("@U"):
            continue
        try:
            x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
        except Exception:
            continue
        if _spawn_serial_at(serial, x, y, z):
            ok_n += 1
    _last_layout["party_count"] = _party_count()
    _last_layout["applied_at"] = time.time()
    _status = f"Re-applied last layout: {ok_n}/{len(entries)} serial spawn(s)."
    _log(_status)
    return _status


def get_status() -> str:
    return _status


def last_shape_name() -> str:
    name = _normalize_shape_name(_last_layout.get("shape") or "spiral")
    return name if name in SHAPE_NAMES else "spiral"


_DROP_HEIGHT = _DEFAULT_DROP_HEIGHT
DROP_MODES: dict[str, dict[str, float | str]] = {
    "none": {"dur": 0.0, "style": "none", "height_mul": 0.0, "stagger": 0.0},
    "slow": {"dur": 2.6, "style": "straight", "height_mul": 1.15, "stagger": 0.0},
    "medium": {"dur": 1.7, "style": "straight", "height_mul": 1.05, "stagger": 0.0},
    "fast": {"dur": 0.95, "style": "straight", "height_mul": 0.9, "stagger": 0.0},
    "spiral": {"dur": 2.2, "style": "spiral", "height_mul": 1.2, "stagger": 0.0},
    "rain": {"dur": 2.0, "style": "rain", "height_mul": 2.2, "stagger": 0.08},
    "fountain": {"dur": 2.1, "style": "fountain", "height_mul": 1.55, "stagger": 0.06},
    # Pack at center (nova) / fly from center outward to the 3D sphere.
    "explode": {"dur": 1.35, "style": "explode", "height_mul": 0.55, "stagger": 0.028},
    "stagger": {"dur": 1.15, "style": "straight", "height_mul": 1.22, "stagger": 0.12},
    # Fall from Drop height onto each slot (heart/circle XY). none = ground instant.
    "snap": {"dur": 0.0, "style": "straight", "height_mul": 1.0, "stagger": 0.0},
    # Appear on the 3D silhouette (or overhead for 2D), then peel down to the ground.
    "drip": {"dur": 2.4, "style": "drip", "height_mul": 1.0, "stagger": 0.08},
}
DROP_MODE_NAMES: tuple[str, ...] = tuple(DROP_MODES.keys())
_TYPE_ORDER = (
    "assault_rifle",
    "smg",
    "shotgun",
    "sniper",
    "pistol",
    "heavy",
    "weapon",
    "shield",
    "grenade",
    "classmod",
    "repkit",
    "other",
)
_RARITY_ORDER = ("pearl", "legendary", "epic", "rare", "uncommon", "common", "other")


def normalize_drop_mode(mode: str | None) -> str:
    raw = str(mode or "none").strip().lower()
    if raw in ("", "none", "normal", "off", "vanilla", "game"):
        return "none"
    if raw in ("instant", "float"):
        return "fast" if raw == "instant" else "slow"
    if raw in ("peel", "drip_peel"):
        return "drip"
    if raw in ("boom", "blast", "burst", "nova_explode", "pulse"):
        return "explode"
    return raw if raw in DROP_MODES else "none"


def _instant_land_mode() -> bool:
    """True when items should appear on the slot with no drop animation."""
    return normalize_drop_mode(_drop_mode) == "none"


def _is_peel_drop() -> bool:
    """Peel only when the user picked drip — never auto-collapse dome/house on slow/fast."""
    if _should_hold_in_air():
        return False
    return _drop_mode == "drip"


_stay_in_air: bool = False
_peel_after_sec: float = 0.0
_float_on_grab: bool = False
_float_on_grab_prev_addrs: set[int] = set()
_grab_float_jobs: list[dict[str, Any]] = []
_peel_armed_at: float = 0.0
_peel_started: bool = False
_peel_queue: list[dict[str, Any]] = []
_nova_explode_armed_at: float = 0.0
_nova_explode_started: bool = False
_nova_explode_queue: list[dict[str, Any]] = []


def _is_nova_shape(shape: str | None = None) -> bool:
    name = _normalize_shape_name(shape or _drop_shape or _land_user_shape or "")
    return name == "nova"


def _nova_ball_center() -> tuple[float, float, float]:
    """Condensed ball sits in front of the player (plan centroid), not on their feet."""
    ox, oy, oz = _drop_origin
    if _drop_plan:
        cx = sum(float(p[0]) for p in _drop_plan) / float(len(_drop_plan))
        cy = sum(float(p[1]) for p in _drop_plan) / float(len(_drop_plan))
        return cx, cy, oz + 110.0
    fx, fy, _rx, _ry = _yaw_basis(float(_drop_yaw))
    return ox + fx * 220.0, oy + fy * 220.0, oz + 110.0


def _nova_condensed_world(index: int) -> tuple[float, float, float]:
    """Tight ball in front of the player while the dump is still packing."""
    cx, cy, cz = _nova_ball_center()
    golden = math.pi * (3.0 - math.sqrt(5.0))
    y = 1.0 - (2.0 * ((int(index) % 89) + 0.5) / 89.0)
    rr = math.sqrt(max(0.0, 1.0 - y * y))
    theta = golden * int(index)
    rad = 28.0
    return (
        cx + rad * rr * math.cos(theta),
        cy + rad * rr * math.sin(theta),
        cz + rad * y,
    )


def _nova_catch_slot(
    slot: tuple[float, float, float], index: int
) -> tuple[float, float, float]:
    """Mid-dump nova packs into the ball; after settle, use final pulse slots."""
    if _is_nova_shape() and _land_active and not _landing_settle_done:
        return _nova_condensed_world(index)
    return slot


def _reset_nova_explode() -> None:
    global _nova_explode_armed_at, _nova_explode_started, _nova_explode_queue
    _nova_explode_armed_at = 0.0
    _nova_explode_started = False
    _nova_explode_queue = []


def _arm_nova_explode(*, delay: float = 0.35) -> None:
    """After dump settle: brief hold on the ball, then pulse outward."""
    global _nova_explode_armed_at, _nova_explode_started
    if not _is_nova_shape():
        return
    if _nova_explode_started or _nova_explode_queue:
        return
    _nova_explode_started = False
    _nova_explode_armed_at = time.monotonic() + max(0.12, float(delay))


def parse_stay_in_air(value: Any, default: bool = False) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return _truthy(value)


def parse_peel_after(value: Any) -> float:
    try:
        return max(0.0, min(60.0, float(value)))
    except Exception:
        return 0.0


def parse_float_on_grab(value: Any, default: bool = False) -> bool:
    if value is None or str(value).strip() == "":
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def set_float_on_grab(value: Any = False) -> None:
    """Gag: when someone grabs shaped loot, nearby silhouette guns briefly float up."""
    global _float_on_grab, _float_on_grab_prev_addrs, _grab_float_jobs
    _float_on_grab = parse_float_on_grab(value, False)
    if not _float_on_grab:
        _float_on_grab_prev_addrs = set()
        _grab_float_jobs = []


def float_on_grab_enabled() -> bool:
    return bool(_float_on_grab)


def _tick_float_on_grab(now: float) -> None:
    """Detect pin removals (pickups) and bob nearby held guns upward."""
    global _float_on_grab_prev_addrs, _grab_float_jobs, _pinned_slots
    if not _float_on_grab:
        _float_on_grab_prev_addrs = {
            int(r.get("addr") or 0) for r in _pinned_slots if int(r.get("addr") or 0)
        }
        return
    current = {int(r.get("addr") or 0) for r in _pinned_slots if int(r.get("addr") or 0)}
    gone = _float_on_grab_prev_addrs - current
    _float_on_grab_prev_addrs = set(current)
    if gone and _pinned_slots:
        # Lift nearby held pins — funny float when friends yank guns from the shape.
        origins: list[tuple[float, float, float]] = []
        for row in list(_pinned_slots):
            if not row.get("hold"):
                continue
            try:
                origins.append((float(row["x"]), float(row["y"]), float(row["z"])))
            except Exception:
                continue
        if origins:
            ox = sum(p[0] for p in origins) / len(origins)
            oy = sum(p[1] for p in origins) / len(origins)
            oz = sum(p[2] for p in origins) / len(origins)
            armed = 0
            for row in list(_pinned_slots):
                if armed >= 28:
                    break
                if not row.get("hold"):
                    continue
                addr = int(row.get("addr") or 0)
                if not addr or addr in gone:
                    continue
                try:
                    x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
                except Exception:
                    continue
                dx, dy, dz = x - ox, y - oy, z - oz
                if (dx * dx + dy * dy + dz * dz) > (720.0 * 720.0):
                    continue
                if any(int(j.get("addr") or 0) == addr for j in _grab_float_jobs):
                    continue
                lift = 110.0 + (armed % 5) * 12.0
                _grab_float_jobs.append(
                    {
                        "addr": addr,
                        "x": x,
                        "y": y,
                        "z": z,
                        "z_peak": z + lift,
                        "yaw": float(row.get("yaw") or 0.0),
                        "pitch": float(row.get("pitch") or 0.0),
                        "roll": float(row.get("roll") or 0.0),
                        "t0": now,
                        "up_dur": 0.38,
                        "down_dur": 0.55,
                        "phase": "up",
                    }
                )
                armed += 1

    if not _grab_float_jobs:
        return
    remaining: list[dict[str, Any]] = []
    # Host-local gag only — ForceNet during float-on-grab hitching lobbies.
    guest_budget = [0]
    for job in _grab_float_jobs:
        addr = int(job.get("addr") or 0)
        inv = _live_pickup(addr) if addr else None
        if inv is None:
            continue
        t0 = float(job.get("t0") or now)
        phase = str(job.get("phase") or "up")
        x = float(job["x"])
        y = float(job["y"])
        z0 = float(job["z"])
        z_peak = float(job["z_peak"])
        yaw = float(job.get("yaw") or 0.0)
        pitch = float(job.get("pitch") or 0.0)
        roll = float(job.get("roll") or 0.0)
        if phase == "up":
            dur = max(0.2, float(job.get("up_dur") or 0.38))
            u = min(1.0, (now - t0) / dur)
            ease = u * u * (3.0 - 2.0 * u)
            z = z0 + (z_peak - z0) * ease
            _teleport_pickup(
                inv,
                x,
                y,
                z,
                yaw,
                pitch=pitch,
                roll=roll,
                freeze=True,
                replicate=False,
                keep_grab_collision=True,
            )
            if guest_budget[0] > 0 and (u < 0.08 or u > 0.55 or (now - float(job.get("guest_net") or 0)) > 0.2):
                fly_row = {
                    "x": x,
                    "y": y,
                    "z": z,
                    "yaw": yaw,
                    "pitch": pitch,
                    "roll": roll,
                    "hold": True,
                    "addr": addr,
                }
                try:
                    if _push_pin_to_guests(fly_row, inv, allow_during_dump=True):
                        guest_budget[0] -= 1
                        job["guest_net"] = now
                except Exception:
                    pass
            if u >= 1.0:
                job["phase"] = "down"
                job["t0"] = now
            remaining.append(job)
            continue
        # down → slot
        dur = max(0.25, float(job.get("down_dur") or 0.55))
        u = min(1.0, (now - t0) / dur)
        ease = u * u * (3.0 - 2.0 * u)
        z = z_peak + (z0 - z_peak) * ease
        _teleport_pickup(
            inv,
            x,
            y,
            z,
            yaw,
            pitch=pitch,
            roll=roll,
            freeze=True,
            replicate=bool(u >= 1.0),
            guest_push=bool(u >= 1.0),
            keep_grab_collision=True,
        )
        if u < 1.0:
            remaining.append(job)
            continue
        # Restamp pin slot for guests after bob.
        for row in _pinned_slots:
            if int(row.get("addr") or 0) == addr:
                try:
                    _push_pin_to_guests(row, inv, allow_during_dump=True)
                except Exception:
                    pass
                break
    _grab_float_jobs = remaining


def _set_air_hold(stay_in_air: Any = False, peel_after: Any = 0.0, *, shape: str | None = None) -> None:
    """yes + 0 sec = keep the 3D silhouette. Any Drop-after seconds = hold, then peel.

    Nova defaults to ground shoot-out when Stay is unset; other shapes default to hold
    when unset. The EXE Stay field default is \"no\" (opt-in silhouette).
    """
    global _stay_in_air, _peel_after_sec, _peel_armed_at, _peel_started, _peel_queue
    shape_n = _normalize_shape_name(shape or _drop_shape or _land_user_shape or "")
    default = False if shape_n == "nova" else True
    stay = parse_stay_in_air(stay_in_air, default)
    sec = parse_peel_after(peel_after)
    _peel_started = False
    _peel_queue = []
    if sec > 0.0:
        # A set timer always peels — dump was ignoring this when Stay in air was still yes.
        _stay_in_air = False
        _peel_after_sec = sec
        _peel_armed_at = 0.0
        return
    if stay:
        _stay_in_air = True
        _peel_after_sec = 0.0
        _peel_armed_at = 0.0
        return
    _stay_in_air = False
    _peel_after_sec = 0.0
    _peel_armed_at = 0.0


def _arm_peel_clock() -> None:
    global _peel_armed_at
    if _peel_started or _peel_after_sec <= 0.0:
        return
    if _peel_armed_at <= 0.0:
        _peel_armed_at = time.monotonic() + _peel_after_sec


def _should_hold_in_air() -> bool:
    if _peel_started:
        return False
    shape = _normalize_shape_name(_drop_shape or _land_user_shape or "")
    if shape not in SHAPE_3D_NAMES:
        return False
    if _stay_in_air:
        return True
    # Timed peel: hold as soon as items land. Dump catch runs before
    # settle_landing_loot arms the clock — do not wait for _peel_armed_at.
    return _peel_after_sec > 0.0


def _coop_should_keep_freeze() -> bool:
    """Co-op shapes stay frozen for display; guests collect via ServerUse backpack.

    Native Attract on pinned freeze never worked for lobby guests. Soft
    physics unlock dropped the silhouette. Keep the shape posed; Use gives
    the item into that player's backpack and removes that world slot.
    """
    return True


def _apply_dump_usable_state(inv: Any, *, gravity: bool) -> None:
    """Per-item hand-off to natural InventoryPickup state (never mass-call this).

    Dump LIVE_OK: bReplicates=True, RemoteRole=1, AlwaysRelevant, NetDormancy=3,
    NetFreq=40, bRepPhysics=True, sleep=True. Host-only restore left guests on the
    non-replicating row — ForceNet after this so they can Use the dropped gun.
    """
    if inv is None or not _live(inv):
        return
    try:
        if not _live(inv):
            return
        set_rep = getattr(inv, "SetReplicates", None)
        if callable(set_rep):
            set_rep(True)
        set_rm = getattr(inv, "SetReplicateMovement", None)
        if callable(set_rm):
            set_rm(True)
        inv.bOnlyRelevantToOwner = False
        inv.bNetUseOwnerRelevancy = False
        inv.bReplicates = True
        inv.bReplicateMovement = True
        inv.bAlwaysRelevant = True
        inv.NetUpdateFrequency = 40.0
        inv.MinNetUpdateFrequency = 2.0
        # Dump LIVE_OK RemoteRole=1 (ROLE_SimulatedProxy).
        try:
            inv.RemoteRole = 1
        except Exception:
            pass
    except Exception:
        pass
    try:
        dorm = getattr(inv, "SetNetDormancy", None)
        if callable(dorm):
            dorm(3)  # DORM_Never — dump NetDormancy=3
    except Exception:
        pass
    try:
        if _live(inv):
            state = getattr(inv, "UsableActorState", None)
            if state is not None:
                setattr(state, "bInteractabilityLockedReplicated", False)
    except Exception:
        pass
    try:
        if _live(inv):
            inv.SetActorEnableCollision(True)
    except Exception:
        pass
    zero = _make_vector(0.0, 0.0, 0.0)
    for comp in _physics_components(inv):
        if not _live(inv):
            return
        for name, args in (
            ("SetPhysicsLinearVelocity", (zero,)),
            ("SetPhysicsAngularVelocityInRadians", (zero,)),
            ("SetPhysicsAngularVelocity", (zero,)),
        ):
            fn = getattr(comp, name, None)
            if callable(fn):
                try:
                    fn(*args)
                except Exception:
                    pass
        if not _live(inv):
            return
        # Undo sticky disable from older freeze paths.
        reset = getattr(comp, "ResetAllBodiesSimulatePhysics", None)
        if callable(reset):
            try:
                reset()
            except Exception:
                pass
        if not _live(inv):
            return
        sim = getattr(comp, "SetSimulatePhysics", None)
        if callable(sim):
            try:
                sim(True)
            except Exception:
                pass
        if not _live(inv):
            return
        grav = getattr(comp, "SetEnableGravity", None)
        if callable(grav):
            try:
                grav(bool(gravity))
            except Exception:
                pass
        sleep = getattr(comp, "PutRigidBodyToSleep", None) or getattr(
            comp, "PutAllRigidBodiesToSleep", None
        )
        if callable(sleep):
            try:
                sleep()
            except Exception:
                pass
        col = getattr(comp, "SetCollisionEnabled", None)
        if callable(col):
            try:
                col(3)
            except Exception:
                try:
                    col("QueryAndPhysics")
                except Exception:
                    pass
    try:
        if _live(inv):
            _set_pickup_collision(inv, block=True)
    except Exception:
        pass
    try:
        if not _live(inv):
            return
        movement = getattr(inv, "ReplicatedMovement", None)
        if movement is not None:
            try:
                setattr(movement, "LinearVelocity", zero)
            except Exception:
                pass
            try:
                setattr(movement, "AngularVelocity", zero)
            except Exception:
                pass
            try:
                setattr(movement, "bSimulatedPhysicSleep", True)
            except Exception:
                pass
            try:
                setattr(movement, "bRepPhysics", True)
            except Exception:
                pass
    except Exception:
        pass


def _force_net_guest_handoff(inv: Any) -> None:
    """One unbudgeted ForceNet after hand-off — guests must see LIVE_OK dump state.

    Mass ForceNet is banned; this is only for a single Use/proximity release.
    """
    if inv is None or not _live(inv):
        return
    try:
        set_rep = getattr(inv, "SetReplicates", None)
        if callable(set_rep):
            set_rep(True)
        set_rm = getattr(inv, "SetReplicateMovement", None)
        if callable(set_rm):
            set_rm(True)
    except Exception:
        pass
    try:
        inv.bAlwaysRelevant = True
        inv.bOnlyRelevantToOwner = False
        inv.bNetUseOwnerRelevancy = False
        inv.NetUpdateFrequency = 40.0
        try:
            inv.RemoteRole = 1
        except Exception:
            pass
    except Exception:
        pass
    try:
        dorm = getattr(inv, "SetNetDormancy", None)
        if callable(dorm):
            dorm(3)
    except Exception:
        pass
    if not _live(inv):
        return
    for name in ("FlushNetDormancy", "ForceNetUpdate"):
        try:
            if not _live(inv):
                return
            fn = getattr(inv, name, None)
            if callable(fn):
                fn()
        except Exception:
            continue


def _stamp_guest_grab_ready(inv: Any) -> None:
    """After publish: dump net/usable flags only — keep pose frozen (no physics wake).

    Mass SetSimulatePhysics on 120 slots lagged the lobby and dropped the shape
    while still leaving picks dead for guests (pins were cleared). Hand-off is
    per-item via ServerUse / proximity / drift → _release_pin_for_pickup.
    """
    if inv is None or not _live(inv):
        return
    try:
        inv.bOnlyRelevantToOwner = False
        inv.bNetUseOwnerRelevancy = False
        inv.bReplicates = True
        inv.bReplicateMovement = True
        inv.bAlwaysRelevant = True
        inv.NetUpdateFrequency = 40.0
        inv.MinNetUpdateFrequency = 2.0
    except Exception:
        pass
    try:
        dorm = getattr(inv, "SetNetDormancy", None)
        if callable(dorm):
            dorm(3)
    except Exception:
        pass
    try:
        state = getattr(inv, "UsableActorState", None)
        if state is not None:
            setattr(state, "bInteractabilityLockedReplicated", False)
    except Exception:
        pass
    try:
        inv.SetActorEnableCollision(True)
    except Exception:
        pass
    try:
        _set_physics(inv, False, keep_grab_collision=True)
        _zero_velocity(inv)
    except Exception:
        pass
    try:
        _set_pickup_collision(inv, block=True)
    except Exception:
        pass


def _stamp_pickup_net_for_guests(inv: Any, *, held: bool) -> None:
    """Net relevancy stamp without waking physics."""
    _ = held
    _stamp_guest_grab_ready(inv)


def _party_pawn_xy() -> list[tuple[float, float, float]]:
    """Live party pawn positions for guest-grab hand-off (no ForceNet)."""
    out: list[tuple[float, float, float]] = []
    try:
        from .party_helpers import _gbc_session_world_and_gamestate

        _world, gs = _gbc_session_world_and_gamestate()
        pa = getattr(gs, "PlayerArray", None) if gs is not None else None
        if pa is None:
            return out
        for i in range(len(pa)):
            try:
                ps = pa[i]
            except Exception:
                continue
            if ps is None:
                continue
            pawn = getattr(ps, "PawnPrivate", None) or getattr(ps, "Pawn", None)
            if pawn is None:
                continue
            try:
                loc = pawn.K2_GetActorLocation()
                out.append((float(loc.X), float(loc.Y), float(loc.Z)))
            except Exception:
                continue
    except Exception:
        pass
    if not out:
        try:
            anchor = _player_anchor()
            if anchor is not None:
                out.append((float(anchor[1]), float(anchor[2]), float(anchor[3])))
        except Exception:
            pass
    return out


def _drop_dead_pin(row: dict[str, Any]) -> None:
    """Remove a pin whose actor is gone — never call restore/ForceNet on it."""
    global _pinned_slots, _pickup_by_addr, _shape_grab_exclude
    addr = int(row.get("addr") or 0)
    if not addr:
        return
    _pickup_by_addr.pop(addr, None)
    try:
        _pinned_slots = [
            r for r in _pinned_slots if int(r.get("addr") or 0) != int(addr)
        ]
    except Exception:
        pass
    try:
        _shape_grab_exclude[_key_for_addr(addr)] = time.monotonic() + 120.0
    except Exception:
        pass


def _party_near_pin(row: dict[str, Any], party_xyz: list[tuple[float, float, float]]) -> bool:
    """True when any party pawn is close enough that Attract/grab needs a hand-off."""
    if not party_xyz:
        return False
    try:
        px = float(row.get("x") or 0.0)
        py = float(row.get("y") or 0.0)
        pz = float(row.get("z") or 0.0)
    except Exception:
        return False
    # lim2 ~150uu — guests must stand in the shape to hand off.
    lim2 = 22500.0
    for ax, ay, az in party_xyz:
        dx = ax - px
        dy = ay - py
        dz = az - pz
        if (dx * dx + dy * dy + dz * dz) <= lim2:
            return True
    return False


def _shape_hold_active() -> bool:
    """3D silhouettes stay pinned for the whole dump, not only when Stay in air is on."""
    if _should_hold_in_air():
        return True
    if not _land_active:
        return False
    shape = _normalize_shape_name(_drop_shape or _land_user_shape or "")
    if shape == "nova":
        # Condensed ball until the pulse starts. Once bursting, Stay in air alone
        # decides whether the final sphere stays pinned (do not force-hold mid-pulse).
        if not _landing_settle_done:
            return True
        if _nova_explode_armed_at > 0.0 and not _nova_explode_started:
            return True
        return False
    return shape in SHAPE_3D_NAMES


def _reset_air_hold() -> None:
    global _stay_in_air, _peel_after_sec, _peel_armed_at, _peel_started, _peel_queue
    global _float_on_grab, _float_on_grab_prev_addrs, _grab_float_jobs
    _stay_in_air = False
    _peel_after_sec = 0.0
    # Keep float_on_grab preference across soft clears of air-hold; only drop active bobs.
    _grab_float_jobs = []
    _float_on_grab_prev_addrs = set()
    _peel_armed_at = 0.0
    _peel_started = False
    _peel_queue = []
    _reset_nova_explode()

_drop_plan: list[tuple[float, float, float]] = []
_drop_plan_target: int = 0
_drop_plan_pending: bool = False
_drop_plan_build: dict[str, Any] = {}
_after_dump_calls: int = 0
_drop_local_dirs: list[tuple[float, float, float]] = []
_drop_next: int = 0
_spawn_cursor: int = 0
_drop_mode: str = "slow"
_drop_yaw: float = 0.0
_drop_seen: set[str] = set()
_drop_preexisting: set[str] = set()
# Released for player grab — never re-pin / overhead-catch (that was the fly-up loop).
_shape_grab_exclude: dict[str, float] = {}
_frozen_dump: set[str] = set()
_CATCH_CLASSES: tuple[str, ...] = ("OakInventoryPickup", "InventoryPickup", "OakPickup")
_CATCH_CLASSES_DUMP: tuple[str, ...] = ("InventoryPickup", "OakInventoryPickup")
_catch_last_at: float = 0.0
_drop_origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
_drop_shape: str = "spiral"
_drop_radius: float = _DEFAULT_RADIUS
_drop_spacing: float = _DEFAULT_SPACING
_drop_per_ring: int = _DEFAULT_PER_RING
_drop_stack: float = 0.0
_drop_line_length: float = _DEFAULT_LINE_LENGTH
_drop_type_counts: dict[str, int] = {}
_drop_unique_order: list[str] = []
_drop_part_plans: dict[str, list[tuple[float, float, float]]] = {}
_pickup_cache: list[tuple[int, Any]] = []
_pickup_cache_at: float = 0.0
_pickup_by_addr: dict[int, Any] = {}
_CATCH_RADIUS_LAND = 6000.0
_CATCH_RADIUS_IDLE = 1600.0
_tick_last: float = 0.0
_tick_busy: bool = False
_party_poll_at: float = 0.0
_drop_until: float = 0.0
_float_tick_at: float = 0.0
_deferred_catch_at: float = 0.0
_deferred_catch_until: float = 0.0
_deferred_catch_empty: int = 0


def _key_for_addr(addr: int) -> str:
    return f"a:{addr:x}"


def _pickup_key(inv: Any) -> str:
    """Unreal actor identity. Dump guns often share Name; id(wrapper) changes every find_all."""
    addr = _uobject_addr(inv)
    if addr:
        return _key_for_addr(addr)
    return f"id:{id(inv)}"


def _prune_shape_grab_exclude(now: float | None = None) -> None:
    global _shape_grab_exclude
    t = time.monotonic() if now is None else float(now)
    if not _shape_grab_exclude:
        return
    if len(_shape_grab_exclude) > 400 or any(True for _ in _shape_grab_exclude):
        _shape_grab_exclude = {k: exp for k, exp in _shape_grab_exclude.items() if exp > t}


def _mark_shape_grab_exclude(inv: Any, *, seconds: float = 120.0) -> None:
    """Block reshape/catch by actor address while a player takes it.

    Do not read the item serial during pickup hand-off: touching GbxItem while
    native pickup code owns it can race destruction and AV pyunrealsdk.
    """
    global _shape_grab_exclude, _drop_seen, _drop_preexisting
    until = time.monotonic() + max(5.0, float(seconds))
    keys: list[str] = []
    try:
        keys.append(_pickup_key(inv))
    except Exception:
        pass
    addr = _uobject_addr(inv)
    if addr:
        keys.append(_key_for_addr(int(addr)))
    for key in keys:
        if not key:
            continue
        _shape_grab_exclude[key] = until
        _drop_seen.add(key)
        _drop_preexisting.add(key)


def _shape_grab_excluded_inv(inv: Any) -> bool:
    if inv is None:
        return False
    _prune_shape_grab_exclude()
    now = time.monotonic()
    try:
        key = _pickup_key(inv)
        if key and float(_shape_grab_exclude.get(key) or 0.0) > now:
            return True
    except Exception:
        pass
    addr = _uobject_addr(inv)
    if addr and float(_shape_grab_exclude.get(_key_for_addr(int(addr))) or 0.0) > now:
        return True
    return False


def _shape_grab_excluded_addr(addr: int) -> bool:
    if not addr:
        return False
    _prune_shape_grab_exclude()
    return float(_shape_grab_exclude.get(_key_for_addr(int(addr))) or 0.0) > time.monotonic()


def _restore_world_pickup_for_grab(inv: Any, *, gravity: bool = False) -> None:
    """Per-item hand-off. Default no gravity — gravity drop left unusable floor loot for guests."""
    if not _live(inv):
        return
    _apply_dump_usable_state(inv, gravity=bool(gravity))
    _force_net_guest_handoff(inv)


def _is_local_player_controller(pc: Any) -> bool:
    if pc is None:
        return True
    local = None
    try:
        from unrealsdk import get_pc

        local = get_pc()
    except Exception:
        local = None
    if local is None:
        try:
            from .item_spawn.pearl_serial_spawn import _get_pc

            local = _get_pc()
        except Exception:
            local = None
    if local is None:
        return True
    try:
        return int(_uobject_addr(pc) or 0) == int(_uobject_addr(local) or 0)
    except Exception:
        return pc is local


def _add_serial_to_pc_backpack(pc: Any, serial: str) -> bool:
    """Put @U straight into that PC's backpack (not mailbox / loyalty mail)."""
    serial = str(serial or "").strip()
    if not serial.startswith("@U") or pc is None:
        return False
    try:
        from .item_spawn.pearl_serial_spawn import (
            _BACKPACK_SERIAL_METHODS,
            _SERIAL_INVENTORY_ATTRS,
            _invoke_serial_method,
            _safe_getattr,
        )
    except Exception:
        return False
    targets: list[Any] = [pc]
    pawn = _safe_getattr(pc, "Pawn")
    if pawn is not None:
        targets.append(pawn)
    ps = _safe_getattr(pc, "PlayerState")
    if ps is not None:
        targets.append(ps)
        for bag in ("BackpackContainer", "BankContainer"):
            bag_obj = _safe_getattr(ps, bag)
            if bag_obj is not None:
                targets.append(bag_obj)
    for attr in _SERIAL_INVENTORY_ATTRS:
        for root in (pc, pawn, ps):
            if root is None:
                continue
            obj = _safe_getattr(root, attr)
            if obj is not None:
                targets.append(obj)
    seen: set[int] = set()
    for target in targets:
        if target is None:
            continue
        try:
            key = int(_uobject_addr(target) or 0) or id(target)
        except Exception:
            key = id(target)
        if key in seen:
            continue
        seen.add(key)
        for method in _BACKPACK_SERIAL_METHODS:
            try:
                if _invoke_serial_method(target, method, serial, 1):
                    return True
            except Exception:
                continue
    return False


def _destroy_world_pickup(inv: Any) -> None:
    if inv is None or not _live(inv):
        return
    for name in ("GbxDestroyActor", "K2_DestroyActor", "DestroyActor", "Destroy"):
        try:
            if not _live(inv):
                return
            fn = getattr(inv, name, None)
            if callable(fn):
                fn()
                return
        except Exception:
            continue


def _collect_shaped_pickup_for_pc(pc: Any, inv: Any, row: dict[str, Any] | None) -> bool:
    """ServerUse on a shaped pin: backpack the serial and remove that world slot."""
    global _float_jobs, _grab_float_jobs, _pickup_by_addr, _pinned_slots
    if pc is None or inv is None or not _live(inv):
        return False
    serial = ""
    try:
        serial = serial_from_pickup(inv)
    except Exception:
        serial = ""
    if not serial.startswith("@U") and row is not None:
        try:
            serial = _serial_for_pin_row(row, resolve_inv=False)
        except Exception:
            serial = str(row.get("serial") or "").strip()
    if not serial.startswith("@U"):
        return False
    if not _add_serial_to_pc_backpack(pc, serial):
        return False
    _mark_shape_grab_exclude(inv)
    addr = _uobject_addr(inv) or int((row or {}).get("addr") or 0)
    try:
        _destroy_world_pickup(inv)
    except Exception:
        pass
    if addr:
        _float_jobs = [j for j in _float_jobs if int(j.get("addr") or 0) != int(addr)]
        _grab_float_jobs = [j for j in _grab_float_jobs if int(j.get("addr") or 0) != int(addr)]
        _pickup_by_addr.pop(int(addr), None)
        try:
            _pinned_slots = [
                r for r in _pinned_slots if int(r.get("addr") or 0) != int(addr)
            ]
        except Exception:
            pass
    who = "host" if _is_local_player_controller(pc) else "guest"
    _log(f"Co-op {who} collected shaped loot ({serial[:18]}…).")
    return True


def _release_pin_for_pickup(inv: Any, row: dict[str, Any] | None = None) -> None:
    """Stop managing a pin so Usable grab / Attract can finish into inventory."""
    global _float_jobs, _grab_float_jobs, _pickup_by_addr, _pinned_slots
    if inv is None and row is not None:
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr) if addr else None
    if inv is None:
        if row is not None:
            _drop_dead_pin(row)
        return
    if not _live(inv):
        # Never touch dead wrappers (AV). Drop tracking by addr only.
        if row is not None:
            _drop_dead_pin(row)
        else:
            addr = _uobject_addr(inv) or 0
            if addr:
                _drop_dead_pin({"addr": int(addr)})
        return
    _mark_shape_grab_exclude(inv)
    addr = _uobject_addr(inv) or int((row or {}).get("addr") or 0)
    try:
        # No gravity — gravity wake was the click→floor→still-unusable guest path.
        _restore_world_pickup_for_grab(inv, gravity=False)
    except Exception:
        pass
    try:
        if inv is not None and _live(inv):
            _force_net_guest_handoff(inv)
    except Exception:
        pass
    if addr:
        _float_jobs = [j for j in _float_jobs if int(j.get("addr") or 0) != int(addr)]
        _grab_float_jobs = [j for j in _grab_float_jobs if int(j.get("addr") or 0) != int(addr)]
        _pickup_by_addr.pop(int(addr), None)
        # Drop from pin list so guest heartbeat cannot yank mid-grab.
        try:
            _pinned_slots = [
                r for r in _pinned_slots if int(r.get("addr") or 0) != int(addr)
            ]
        except Exception:
            pass


def _catch_radius() -> float:
    return _CATCH_RADIUS_LAND if _land_active else _CATCH_RADIUS_IDLE


def _near_drop_origin(inv: Any, radius: float | None = None) -> bool:
    ox, oy, oz = _drop_origin
    if ox == 0.0 and oy == 0.0 and oz == 0.0:
        return True
    try:
        loc = inv.K2_GetActorLocation()
        x, y, z = float(loc.X), float(loc.Y), float(loc.Z)
    except Exception:
        return False
    if abs(x) < 1.0 and abs(y) < 1.0 and abs(z) < 1.0:
        # Brand-new dump actors often report 0,0,0 for one tick. Skip them
        # after landing is done; during dump they must still be catchable.
        return bool(_land_active)
    rad = float(_catch_radius() if radius is None else radius)
    dx = x - ox
    dy = y - oy
    dz = z - oz
    return (dx * dx + dy * dy + dz * dz) <= rad * rad


def _remember_inv(inv: Any) -> int:
    addr = _uobject_addr(inv)
    if addr:
        _pickup_by_addr[addr] = inv
    return addr


def _live_pickup(addr: int) -> Any | None:
    """Fresh wrapper from the address map only. Stale job/pin wrappers AV on peel/join."""
    want = int(addr or 0)
    if not want:
        return None
    inv = _pickup_by_addr.get(want)
    if inv is None:
        return None
    if _uobject_addr(inv) != want:
        _pickup_by_addr.pop(want, None)
        return None
    return inv


def _resolve_pin_inv(row: dict[str, Any], *, fresh: bool = False) -> Any | None:
    """Map a held pin row to a live pickup — addr, serial, then slot proximity."""
    addr = int(row.get("addr") or 0)
    if addr:
        inv = _live_pickup(addr)
        if inv is not None and _live(inv):
            return inv
    if _mid_shape_dump():
        return None
    serial = str(row.get("serial") or "")
    if serial:
        for cand_addr, candidate in _raw_pickup_scan(fresh=fresh):
            if not cand_addr or candidate is None or not _live(candidate):
                continue
            try:
                if serial_from_pickup(candidate) == serial:
                    row["addr"] = int(cand_addr)
                    _pickup_by_addr[int(cand_addr)] = candidate
                    return candidate
            except Exception:
                continue
    sx = float(row.get("x") or 0.0)
    sy = float(row.get("y") or 0.0)
    sz = float(row.get("z") or 0.0)
    slot_r2 = (520.0 * 520.0) if time.monotonic() < float(_join_guest_boost_until or 0.0) else (360.0 * 360.0)
    best: Any | None = None
    best_d2 = slot_r2 + 1.0
    for cand_addr, candidate in _raw_pickup_scan(fresh=fresh):
        if not cand_addr or candidate is None or not _live(candidate):
            continue
        xyz = _pickup_world_xyz(candidate)
        if xyz is None:
            continue
        cx, cy, cz = xyz
        dx = cx - sx
        dy = cy - sy
        dz = cz - sz
        d2 = dx * dx + dy * dy + dz * dz
        if d2 < best_d2:
            best = candidate
            best_d2 = d2
    if best is not None and best_d2 <= slot_r2:
        new_addr = _uobject_addr(best)
        if new_addr:
            row["addr"] = int(new_addr)
            _pickup_by_addr[int(new_addr)] = best
            try:
                got_serial = serial_from_pickup(best)
                if got_serial:
                    row["serial"] = got_serial
            except Exception:
                pass
        return best
    return None


def _refresh_live_pickups() -> None:
    """Replace the address map with this tick's find_all. Stale dump wrappers AV."""
    global _pickup_by_addr
    hold_addrs = {
        int(row.get("addr") or 0)
        for row in _pinned_slots
        if row.get("hold") and int(row.get("addr") or 0)
    }
    preserved = {a: _pickup_by_addr[a] for a in hold_addrs if a in _pickup_by_addr}
    fresh: dict[int, Any] = dict(preserved)
    try:
        for addr, inv in _raw_pickup_scan(fresh=True):
            if addr and inv is not None:
                fresh[int(addr)] = inv
    except Exception:
        _pickup_by_addr = preserved
        return
    _pickup_by_addr = fresh


def _tick_join_hold_freeze(now: float) -> None:
    """Join quiet: do not hammer teleports — that AVs when guests stream/GC pickups."""
    del now
    return


def pickup_address_set(*, fresh: bool = False) -> set[int]:
    """Addresses of dump/NCS pickups currently in the world (no actor property reads)."""
    return {addr for addr, _inv in _raw_pickup_scan(fresh=fresh) if addr}


def _raw_pickup_scan(*, fresh: bool = False) -> list[tuple[int, Any]]:
    """(address, pickup) for dump/NCS pickups, newest first. Address only."""
    global _pickup_cache, _pickup_cache_at
    now = time.monotonic()
    if _bulk_healthcheck_mode and _land_active and _shape_hold_active():
        ttl = 0.32
    elif _land_active:
        ttl = 1.15
    else:
        ttl = 0.25
    hold_n = held_pin_count()
    if hold_n > 400:
        ttl = max(ttl, 0.65 if _bulk_healthcheck_mode else 0.95)
    if hold_n > 900:
        ttl = max(ttl, 1.35)
    if not fresh and _pickup_cache and now - _pickup_cache_at < ttl:
        return _pickup_cache
    out: list[tuple[int, Any]] = []
    seen: set[int] = set()
    classes = _CATCH_CLASSES_DUMP if _land_active else _CATCH_CLASSES
    for cls in classes:
        try:
            found = list(unrealsdk.find_all(cls, False) or [])
        except Exception:
            continue
        for inv in reversed(found):
            addr = _uobject_addr(inv)
            if not addr or addr in seen:
                continue
            seen.add(addr)
            out.append((addr, inv))
    _pickup_cache = out
    _pickup_cache_at = now
    return out


def _iter_unseen_pickups(*, limit: int = 12, ignore_frozen: bool = False, fresh: bool = False) -> list[Any]:
    """Actors that appeared since the shape was armed.

    Known pickups are rejected by address before any actor property is read, so
    a batch that already placed hundreds of items costs no more than the first.
    """
    out: list[Any] = []
    budget = max(1, min(48, int(limit)))
    for addr, inv in _raw_pickup_scan(fresh=fresh):
        if not _live(inv):
            continue
        key = _key_for_addr(addr)
        if key in _drop_seen:
            continue
        if ignore_frozen and key in _frozen_dump:
            continue
        if not _near_drop_origin(inv):
            continue
        _pickup_by_addr[addr] = inv
        out.append(inv)
        if len(out) >= budget:
            break
    return out


def planned_world_slot(index: int) -> tuple[float, float, float] | None:
    """Spawn inside the silhouette even when a pool emits more actors than estimated."""
    _ensure_drop_plan_built()
    idx = int(index)
    if idx < 0 or not _drop_plan:
        return None
    if idx < len(_drop_plan):
        return _drop_plan[idx]
    # Some pool calls emit multiple actors. Keep overflow in the shape instead
    # of falling back to the normal facing-direction launch.
    lap, slot_i = divmod(idx, len(_drop_plan))
    x, y, z = _drop_plan[slot_i]
    return x, y, z + min(36.0, float(lap) * 8.0)


def _ensure_drop_plan_built() -> None:
    """Build silhouette slots lazily — doing it on the button click froze the host."""
    global _drop_plan, _drop_plan_pending, _drop_local_dirs, _drop_part_plans
    if not _drop_plan_pending:
        return
    _drop_plan_pending = False
    cfg = dict(_drop_plan_build or {})
    shape = str(cfg.get("shape") or _drop_shape or "spiral")
    n = max(1, int(cfg.get("n") or _drop_plan_target or 1))
    radius = float(cfg.get("radius") or _drop_radius)
    spacing = float(cfg.get("spacing") or _drop_spacing)
    per_ring = int(cfg.get("per_ring") or _drop_per_ring)
    line_length = float(cfg.get("line_length") or _drop_line_length)
    ox = float(cfg.get("ox") or _drop_origin[0])
    oy = float(cfg.get("oy") or _drop_origin[1])
    oz = float(cfg.get("oz") or _drop_origin[2])
    yaw = float(cfg.get("yaw") or _drop_yaw)
    _drop_part_plans = {}
    _drop_local_dirs = []
    if shape in PILE_GROUP_SHAPES:
        _drop_plan = []
        return
    if shape == "car":
        body, wheels = _car_part_offsets(n, radius)
        wheel_world = [_world_from_local(ox, oy, oz, yaw, lx, ly, lz) for lx, ly, lz in wheels]
        body_world = [_world_from_local(ox, oy, oz, yaw, lx, ly, lz) for lx, ly, lz in body]
        bias = float(_CAR_WORLD_Z_BIAS)
        if bias:
            wheel_world = [(x, y, z + bias) for x, y, z in wheel_world]
            body_world = [(x, y, z + bias) for x, y, z in body_world]
        _drop_part_plans = {"car_wheel": wheel_world, "car_body": body_world}
        _drop_plan = body_world + wheel_world
        return
    if shape == "text":
        if not any(_text_rows):
            set_shape_text(cfg.get("shape_text") or get_shape_text())
        elif cfg.get("shape_text"):
            set_shape_text(cfg.get("shape_text"))
    offsets = shape_offsets(
        shape,
        n,
        radius=radius,
        spacing=spacing,
        per_ring=per_ring,
        line_length=line_length,
        land_profile=str(cfg.get("land_profile") or _land_layout_profile or "shiny"),
    )
    _drop_plan = [_world_from_local(ox, oy, oz, yaw, lx, ly, lz) for lx, ly, lz in offsets]
    _drop_local_dirs = list(_pending_local_dirs)
    label = shape
    if shape == "text" and get_shape_text():
        label = f"text:{get_shape_text()}"
    _log_dev(f"Land plan ready: {label} × {len(_drop_plan)} slot(s).")


def _repin_host_hold_pins(*, limit: int = 0, refresh_cache: bool = True) -> int:
    """Re-freeze held silhouette slots on the host after join quiet (items must not fall)."""
    global _hold_repin_cursor, _join_hold_repin_last
    if not _pinned_slots:
        return 0
    hold_rows = [row for row in _pinned_slots if row.get("hold")]
    if not hold_rows:
        return 0
    if refresh_cache:
        try:
            invalidate_pickup_cache()
            _refresh_live_pickups()
        except Exception:
            pass
    total = len(hold_rows)
    cap = total if int(limit or 0) <= 0 else max(1, min(total, int(limit)))
    pinned = 0
    for i in range(cap):
        row = hold_rows[(_hold_repin_cursor + i) % total]
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr) if addr else None
        if inv is None or not _live(inv):
            inv = _resolve_pin_inv(row, fresh=False)
        if inv is None or not _live(inv):
            continue
        try:
            ok = _teleport_pickup(
                inv,
                float(row["x"]),
                float(row["y"]),
                float(row["z"]),
                float(row.get("yaw") or 0.0),
                pitch=float(row.get("pitch") or 0.0),
                roll=float(row.get("roll") or 0.0),
                freeze=True,
                replicate=False,
                guest_push=False,
                keep_grab_collision=True,
            )
            if ok:
                _set_physics(inv, False, keep_grab_collision=True)
                _zero_velocity(inv)
                pinned += 1
        except Exception:
            continue
    _hold_repin_cursor = (_hold_repin_cursor + cap) % max(1, total)
    if pinned:
        _join_hold_repin_last = time.monotonic()
        global _repin_log_at
        now = time.monotonic()
        if now - float(_repin_log_at or 0.0) >= 2.5:
            _repin_log_at = now
            _log_dev(f"Host hold repin: {pinned} silhouette slot(s) re-frozen after join.")
    return pinned


_JOIN_SERIAL_BATCH = 6
_JOIN_SERIAL_GAP = 0.28


def _spawn_pool_pickup_at_pin(row: dict[str, Any]) -> Any | None:
    """Respawn one itempool pickup at a shaped slot (late-join mirror for guests)."""
    pool = str(row.get("pool_name") or "")
    if not pool:
        try:
            idx = int(row.get("slot_index") or 0)
            pool = str(_land_slot_pools.get(idx, "") or "")
        except Exception:
            pool = ""
    if not pool:
        return None
    try:
        from .shinies import (
            _get_pool_store,
            _get_runtime_pc,
            _get_world,
            _resolve_native_pool_name,
            _spawn_pool,
        )
    except Exception:
        return None
    try:
        x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
    except Exception:
        return None
    slot_i = int(row.get("slot_index") or 0)
    yaw = float(row.get("yaw") or 0.0)
    pitch = float(row.get("pitch") or 0.0)
    roll = float(row.get("roll") or 0.0)
    world = _get_world()
    pc = _get_runtime_pc()
    if world is None or pc is None:
        return None
    before: set[int] = set()
    try:
        for inv in unrealsdk.find_all("InventoryPickup", False) or []:
            if _live(inv):
                before.add(id(inv))
    except Exception:
        pass
    try:
        transform = pc.GetTransform()
    except Exception:
        return None
    spawn_name = _resolve_native_pool_name(pool)
    location = _make_vector(x, y, z)
    rotation = _make_rotator(pitch, math.degrees(yaw), roll)
    try:
        level = int(getattr(pc, "GetPlayerLevel", lambda: 50)() or 50)
    except Exception:
        level = 50
    try:
        _spawn_pool(_get_pool_store(), world, transform, level, spawn_name, location, rotation)
    except Exception:
        return None
    newest = None
    try:
        for inv in unrealsdk.find_all("InventoryPickup", False) or []:
            if not _live(inv) or id(inv) in before:
                continue
            newest = inv
    except Exception:
        newest = None
    if newest is None:
        return None
    _teleport_pickup(
        newest,
        x,
        y,
        z,
        yaw,
        pitch=pitch,
        roll=roll,
        freeze=True,
        replicate=True,
        guest_push=True,
    )
    return newest


def _pin_row_for_addr(addr: int) -> dict[str, Any] | None:
    if not addr:
        return None
    for row in _pinned_slots:
        if int(row.get("addr") or 0) == int(addr):
            return row
    return None


def _join_mirror_pin_row(row: dict[str, Any]) -> bool:
    """Late joiner: spawn a guest-visible replica at the slot — never retire host pins."""
    try:
        x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
    except Exception:
        return False
    new_inv = _spawn_pool_pickup_at_pin(row)
    if new_inv is None:
        serial = str(row.get("serial") or "")
        if serial.startswith("@U"):
            try:
                if _spawn_serial_at(serial, x, y, z):
                    new_inv = _resolve_pin_inv(
                        {"serial": serial, "x": x, "y": y, "z": z, "slot_index": row.get("slot_index")},
                        fresh=True,
                    )
            except Exception:
                new_inv = None
    if new_inv is None or not _live(new_inv):
        return False
    mirror_row = {
        "x": x,
        "y": y,
        "z": z,
        "yaw": float(row.get("yaw") or 0.0),
        "pitch": float(row.get("pitch") or 0.0),
        "roll": float(row.get("roll") or 0.0),
        "hold": True,
    }
    try:
        _set_physics(new_inv, False, keep_grab_collision=True)
        _zero_velocity(new_inv)
        return bool(_push_pin_to_guests(mirror_row, new_inv))
    except Exception:
        return False


def _join_respawn_serial_row(row: dict[str, Any]) -> bool:
    """Legacy alias — join mirror handles pool + serial."""
    return _join_mirror_pin_row(row)


def _begin_join_serial_reapply() -> int:
    """Spread late-join serial respawn across HUD ticks (never one-tick blast)."""
    global _join_serial_reapply_active, _join_serial_reapply_at, _join_serial_reapply_cursor
    if not _pinned_slots:
        _join_serial_reapply_active = False
        _clear_stale_layout_entries()
        return 0
    entries = list(_last_layout.get("entries") or [])
    if not entries:
        _join_serial_reapply_active = False
        return 0
    if len(entries) > 96 and not any(row.get("hold") for row in _pinned_slots):
        _clear_stale_layout_entries()
        _join_serial_reapply_active = False
        _log_dev(f"Join serial mirror skipped ({len(entries)} stale entries, no held pins).")
        return 0
    _join_serial_reapply_active = True
    _join_serial_reapply_at = 0.0
    _join_serial_reapply_cursor = 0
    return len(entries)


def _tick_join_serial_reapply(now: float) -> None:
    global _join_serial_reapply_active, _join_serial_reapply_at, _join_serial_reapply_cursor
    if not _join_serial_reapply_active:
        return
    if _progression_network_busy():
        return
    if _held_coop_shape_active():
        _join_serial_reapply_active = False
        _log_dev("Join mirror skipped — held shape uses net push only (duplicate spawns knock pins down).")
        return
    if now > float(_join_guest_boost_until or 0.0):
        _join_serial_reapply_active = False
        return
    if _land_active and not _landing_settle_done:
        return
    if now < float(_join_serial_reapply_at or 0.0):
        return
    entries = list(_last_layout.get("entries") or [])
    if _join_serial_reapply_cursor >= len(entries):
        _join_serial_reapply_active = False
        _log("Guest joined — co-op layout respawn complete.")
        return
    batch = entries[_join_serial_reapply_cursor : _join_serial_reapply_cursor + _JOIN_SERIAL_BATCH]
    ok_n = 0
    for row in batch:
        try:
            if _join_mirror_pin_row(row):
                ok_n += 1
        except Exception as exc:
            _log_dev(f"join serial spawn failed: {exc!r}")
    _join_serial_reapply_cursor += len(batch)
    _join_serial_reapply_at = now + _JOIN_SERIAL_GAP
    if ok_n:
        _log_dev(
            f"Join serial batch {_join_serial_reapply_cursor}/{len(entries)} "
            f"({ok_n} spawned this tick)."
        )


def _run_join_guest_shape_push() -> None:
    """Late joiner: held shapes — host freeze during quiet, then guest heartbeat."""
    global _join_guest_boost_until, _guest_sync_active, _guest_sync_cursor, _guest_sync_last
    if _coop_pickup_safe_active:
        _guest_sync_active = False
        return
    if not _want_coop_replicate() or not _pinned_slots:
        return
    _join_guest_boost_until = time.monotonic() + 120.0
    hold_shape = any(row.get("hold") for row in _pinned_slots)
    try:
        _purge_decor_pins()
    except Exception:
        pass
    if hold_shape:
        _guest_sync_active = True
        _guest_sync_cursor = 0
        _guest_sync_last = 0.0
        try:
            now = time.monotonic()
            if not _join_hold_rebind_recent(now, within=3.0):
                _rebind_hold_pins_after_join()
            repin_gap = 0.45 if held_pin_count() > 120 else 0.28
            if now - float(_join_hold_repin_last or 0.0) >= repin_gap:
                _repin_host_hold_pins(
                    limit=_join_hold_repin_cap(base=24), refresh_cache=False
                )
            # Heartbeat already running from join quiet — do not reset guest_ok / cursor.
        except Exception:
            pass
        _log(f"Guest joined — held shape heartbeat ({len(_pinned_slots)} pin(s)).")
        _log_dev(
            "Join guest push: held shape — throttled repin; guest heartbeat continues."
        )
        return
    global _coop_pins_synced, _peel_armed_at, _peel_started
    _coop_pins_synced = 0
    _peel_armed_at = 0.0
    _peel_started = False
    try:
        tracked = _build_layout_entries_from_pins()
        invalidate_pickup_cache()
        _refresh_live_pickups()
        for row in _pinned_slots:
            row.pop("guest_ok", None)
            row.pop("guest_fail", None)
            row.pop("inv", None)
            row["misses"] = 0
        try:
            stamped = _repin_all_for_guests(limit=0)
        except Exception:
            stamped = 0
        _begin_guest_sync(force=True, clear_ok=True)
        _schedule_coop_followup_sync(waves=4, gap=4.0)
        n_serial = _begin_join_serial_reapply()
        _log(f"Guest joined — syncing layout ({len(_pinned_slots)} pin(s)).")
        _log_dev(
            f"Join guest push: {len(_pinned_slots)} pin(s), {tracked} layout slot(s), "
            f"{stamped} immediate net push(es)"
            + (f", {n_serial} join mirror(s) queued." if n_serial else ".")
        )
    except Exception as exc:
        _log_dev(f"join guest sync failed: {exc!r}")


def _tick_join_refresh(now: float) -> None:
    """After join quiet, rebuild pickup addr map so guest sync resolves live pins."""
    global _join_refresh_needed
    if not _join_refresh_needed or _in_join_quiet(now):
        return
    _join_refresh_needed = False
    hold_rows = [row for row in _pinned_slots if row.get("hold")]
    try:
        invalidate_pickup_cache()
        _refresh_live_pickups()
        for row in _pinned_slots:
            row.pop("inv", None)
            row["misses"] = 0
        if hold_rows:
            _log_dev(
                "Join quiet ended — pickup map refreshed; held shape repin deferred to guest push."
            )
            return
        _log_dev("Join quiet ended — pickup map refreshed for guest shape sync.")
    except Exception:
        pass


def _join_reapply_can_run(now: float) -> bool:
    """True when join quiet ended and we can push air-held pins to the new guest."""
    if not _join_reapply_pending or now < float(_join_reapply_at or 0.0):
        return False
    if _in_join_quiet(now):
        return False
    hold_ready = bool(
        _pinned_slots
        and _landing_settle_done
        and any(row.get("hold") for row in _pinned_slots)
    )
    if hold_ready:
        return True
    if _float_jobs or (_land_active and not _landing_settle_done):
        return False
    return True


def _tick_join_reapply(now: float) -> None:
    """Late joiner push — runs from motion tick (not throttled loot poll)."""
    global _join_reapply_pending
    if _progression_network_busy():
        return
    if not _join_reapply_can_run(now):
        return
    _join_reapply_pending = False
    if _pinned_slots:
        _run_join_guest_shape_push()
    return


def _push_pin_to_guests(
    row: dict[str, Any],
    inv: Any,
    *,
    allow_during_dump: bool = False,
) -> bool:
    """Freeze on slot XYZ and net to lobby guests (never wake physics — that drops the house)."""
    if _progression_network_busy():
        return False
    if not _live(inv):
        return False
    if _shape_grab_excluded_inv(inv):
        return False
    addr = _uobject_addr(inv) or int(row.get("addr") or 0)
    if addr and _shape_grab_excluded_addr(int(addr)):
        return False
    # Mid-grab Attract already moved this gun — hand off instead of yanking to slot.
    try:
        loc = inv.K2_GetActorLocation()
        dx = float(loc.X) - float(row["x"])
        dy = float(loc.Y) - float(row["y"])
        dz = float(loc.Z) - float(row["z"])
        if (dx * dx + dy * dy + dz * dz) > 1600.0 or dz > 28.0:
            _release_pin_for_pickup(inv, row)
            return False
    except Exception:
        pass
    try:
        pool = str(row.get("pool_name") or "")
        if _pickup_skip_shape(inv, pool_name=pool) or not _is_shape_gear_pickup(inv, pool_name=pool):
            row["guest_skip"] = True
            row["guest_ok"] = True
            # Treat as done so pickup-safe can unlock / finish (False used to stall ready).
            return True
    except Exception:
        return False
    # Mid-dump mass push AVs — allow_during_dump is sparse flight/land samples only.
    if _mid_shape_dump() and not allow_during_dump:
        return False
    try:
        ok = _teleport_pickup(
            inv,
            float(row["x"]),
            float(row["y"]),
            float(row["z"]),
            float(row.get("yaw") or 0.0),
            pitch=float(row.get("pitch") or 0.0),
            roll=float(row.get("roll") or 0.0),
            freeze=True,
            replicate=True,
            guest_push=True,
            keep_grab_collision=True,
            require_net=True,
        )
        if not _live(inv):
            return False
        if ok:
            _set_physics(inv, False, keep_grab_collision=True)
            _zero_velocity(inv)
            try:
                inv.SetSimulatePhysics(False)
            except Exception:
                pass
            try:
                _set_pickup_collision(inv, block=True)
            except Exception:
                pass
            try:
                if _live(inv):
                    inv.bOnlyRelevantToOwner = False
                    inv.bAlwaysRelevant = True
                    inv.bReplicateMovement = True
            except Exception:
                pass
        return ok
    except Exception:
        return False


_land_active: bool = False
_land_pose_index: int = 0
_land_settle: str = "none"
_land_drop_height: float = _DEFAULT_DROP_HEIGHT
_land_user_shape: str = "none"
_catch_paused: bool = False
_bulk_healthcheck_mode: bool = False
_bulk_after_dump_scan_at: float = 0.0
_landing_settle_done: bool = False
_loot_world_id: int = 0
_pin_refresh_at: float = 0.0
_pin_cursor: int = 0
_defer_shape: bool = False
_defer_dump_index: int = 0
_DEFER_FORWARD = 260.0
_DEFER_UP = 60.0


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value) and float(value) != 0.0
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def defer_shape_active() -> bool:
    return bool(_defer_shape and _land_active)


def pause_landing_catch(paused: bool) -> None:
    """True while Drop All / Spawn All is draining — skip PlayerTick find_all, not motion."""
    global _catch_paused
    was = bool(_catch_paused)
    _catch_paused = bool(paused)
    if was and not _catch_paused:
        _refresh_float_job_clocks()


def set_bulk_healthcheck_mode(active: bool) -> None:
    """Spawn All catalog pass: throttle after_dump_spawn find_all and skip deferred catch."""
    global _bulk_healthcheck_mode, _bulk_after_dump_scan_at
    _bulk_healthcheck_mode = bool(active)
    if not active:
        _bulk_after_dump_scan_at = 0.0


def pause_catch_for_shape(shape: str) -> None:
    """3D stay-in-air dumps need pin restamps; only pause catch for 2D / no-shape."""
    name = _normalize_shape_name(shape)
    pause_landing_catch(name not in SHAPE_3D_NAMES and name != "text")


def _refresh_float_job_clocks() -> None:
    """Dump drain can outlast rain/fountain dur — restart clocks when catch resumes."""
    if not _float_jobs:
        return
    now = time.monotonic()
    for job in _float_jobs:
        mode_n = str(job.get("mode") or "")
        stagger = float((DROP_MODES.get(mode_n) or {}).get("stagger") or 0.0)
        slot = max(0, int(job.get("index") or 0)) % 10
        job["t0"] = now + stagger * slot


def _is_none_shape(value: str) -> bool:
    return str(value or "none").strip().lower() in ("", "none", "off", "no", "vanilla")


def begin_spawn_landing(
    count: int,
    *,
    shape: str = "none",
    settle: str = "none",
    drop_height: float = _DEFAULT_DROP_HEIGHT,
    line_length: float = _DEFAULT_LINE_LENGTH,
    radius: float = _DEFAULT_RADIUS,
    spacing: float = _DEFAULT_SPACING,
    per_ring: int = _DEFAULT_PER_RING,
    z_bias: float = _DEFAULT_Z_BIAS,
    spawn_then_shape: bool | str = False,
    stay_in_air: Any = None,
    float_on_grab: Any = False,
    peel_after: Any = 0.0,
    land_profile: str = "shiny",
    shape_text: str = "",
) -> str:
    """Arm slots for loot-pool / spawn-all. Shape, drop, or both."""
    global _land_active, _land_pose_index, _land_settle, _land_drop_height, _land_user_shape
    global _defer_shape, _defer_dump_index, _land_layout_profile
    _land_pose_index = 0
    _defer_dump_index = 0
    _defer_shape = _truthy(spawn_then_shape)
    raw = str(shape or "none").strip().lower()
    if shape_text or raw in ("text", "text_shape", "words", "word", "write"):
        set_shape_text(shape_text or get_shape_text())
        if sanitize_shape_text(get_shape_text()):
            raw = "text"
    _land_settle = normalize_drop_mode(settle)
    shape_for_air = _normalize_shape_name(raw) if not _is_none_shape(raw) else "none"
    if shape_for_air == "nova" and (stay_in_air is None or str(stay_in_air).strip() == ""):
        stay_in_air = False
    _set_air_hold(stay_in_air, peel_after, shape=shape_for_air)
    set_float_on_grab(float_on_grab)
    try:
        _land_drop_height = float(
            clamp_layout_params(drop_height=drop_height)["drop_height"]
        )
    except Exception:
        _land_drop_height = _DEFAULT_DROP_HEIGHT
    if _is_none_shape(raw) and _land_settle == "none":
        _land_active = False
        _land_user_shape = "none"
        _defer_shape = False
        _defer_dump_index = 0
        return "none"
    # Drop-only still needs unique XY so items hang in a silhouette then fall.
    plan_shape = raw if not _is_none_shape(raw) else "circle"
    _land_user_shape = raw if not _is_none_shape(raw) else "none"
    _land_active = True
    _land_layout_profile = str(land_profile or "shiny").strip().lower()
    if _land_layout_profile not in ("shiny", "bulk"):
        _land_layout_profile = "shiny"
    fit_r, fit_s = land_layout_for(
        plan_shape,
        max(1, int(count)),
        _land_layout_profile,
        radius=radius,
        spacing=spacing,
    )
    return begin_overhead_drop(
        plan_shape,
        max(1, int(count)),
        mode=_land_settle,
        radius=fit_r,
        spacing=fit_s,
        per_ring=per_ring,
        drop_height=_land_drop_height,
        line_length=line_length,
        z_bias=z_bias,
        user_shape=_land_user_shape,
        stay_in_air=stay_in_air,
        peel_after=peel_after,
        shape_text=get_shape_text() if plan_shape == "text" else "",
        land_profile=_land_layout_profile,
    )


def clear_spawn_landing() -> None:
    abandon_world_loot()


def _current_world_id() -> int:
    """Python id of the live World wrapper. 0 if the viewport is already gone."""
    try:
        from mods_base import ENGINE

        viewport = getattr(ENGINE, "GameViewport", None)
        world = getattr(viewport, "World", None) if viewport is not None else None
        if world is None:
            return 0
        return id(world)
    except Exception:
        return 0


def _world_alive() -> bool:
    """False on main menu / travel. Do not compare Python id(World) — wrappers change every fetch."""
    try:
        pc = get_pc()
        if pc is None:
            return False
        pawn = getattr(pc, "Pawn", None) or getattr(pc, "AcknowledgedPawn", None)
        if pawn is None:
            return False
        return True
    except Exception:
        return False


def _player_left_drop_site() -> bool:
    """True after travel / lobby when the pawn is far from the dump silhouette."""
    if _join_reapply_pending:
        return False
    if not (_land_active or _float_jobs or _pinned_slots or _peel_queue):
        return False
    if _pinned_slots and any(row.get("hold") for row in _pinned_slots):
        try:
            if _want_coop_replicate():
                return False
        except Exception:
            pass
    # Dump drain can briefly fail pawn lookups. Treating that as "left"
    # used to wipe the armed silhouette so the first batch fell at your feet.
    if _catch_paused:
        return False
    ox, oy, _oz = _drop_origin
    if ox == 0.0 and oy == 0.0:
        return False
    try:
        pc = get_pc()
        pawn = getattr(pc, "Pawn", None) or getattr(pc, "AcknowledgedPawn", None) if pc is not None else None
        if pawn is None:
            return False
        loc = pawn.K2_GetActorLocation()
        dx = float(loc.X) - ox
        dy = float(loc.Y) - oy
        return (dx * dx + dy * dy) > (18000.0 * 18000.0)
    except Exception:
        return False


def abandon_world_loot(*, schedule_orphan_absorb: bool = True) -> None:
    """Drop every pickup wrapper without calling into Unreal. Safe on teardown."""
    global _land_active, _land_pose_index, _drop_plan, _drop_until, _float_jobs
    global _deferred_catch_at, _deferred_catch_until, _spawn_cursor
    global _pickup_cache, _pickup_cache_at, _pickup_by_addr, _drop_seen, _frozen_dump
    global _drop_preexisting, _shape_grab_exclude
    global _join_reapply_pending, _landing_settle_done, _defer_shape, _defer_dump_index
    global _coop_pins_synced, _guest_sync_cursor, _guest_sync_active, _guest_sync_last
    global _peel_queue, _loot_world_id, _drop_local_dirs, _land_slot_pools
    global _coop_followup_sync_at, _coop_followup_waves, _abandon_epoch
    global _last_layout
    global _absorb_orphans_after_abandon, _absorb_orphans_at
    had_pins = bool(_pinned_slots)
    _abandon_epoch = int(_abandon_epoch or 0) + 1
    _last_layout["abandon_epoch"] = _abandon_epoch
    _clear_stale_layout_entries()
    _cancel_join_reapply_work()
    _land_active = False
    _land_pose_index = 0
    _spawn_cursor = 0
    _drop_plan = []
    _drop_local_dirs = []
    _drop_until = 0.0
    _float_jobs = []
    _deferred_catch_at = 0.0
    _deferred_catch_until = 0.0
    _landing_settle_done = False
    _shape_grab_exclude = {}
    _loot_world_id = 0
    _join_reapply_pending = False
    _coop_pins_synced = 0
    _guest_sync_cursor = 0
    _guest_sync_active = False
    _guest_sync_last = 0.0
    _coop_followup_sync_at = 0.0
    _coop_followup_waves = 0
    _pickup_cache = []
    _pickup_cache_at = 0.0
    _pickup_by_addr = {}
    _drop_seen = set()
    _drop_preexisting = set()
    _frozen_dump = set()
    _defer_shape = False
    _defer_dump_index = 0
    _peel_queue = []
    _clear_pins()
    _land_slot_pools = {}
    _reset_air_hold()
    # Teardown must not schedule a later find_all absorb — that AVs on a dying world.
    if schedule_orphan_absorb and had_pins:
        try:
            from .session_guards import session_safe

            if session_safe():
                _schedule_orphan_pickup_absorb()
            else:
                _absorb_orphans_after_abandon = False
                _absorb_orphans_at = 0.0
        except Exception:
            _absorb_orphans_after_abandon = False
            _absorb_orphans_at = 0.0
    else:
        _absorb_orphans_after_abandon = False
        _absorb_orphans_at = 0.0


def spawn_landing_active() -> bool:
    return bool(_land_active and _drop_plan)


def landing_armed() -> bool:
    return bool(_land_active)


def consume_land_slot(count: int = 1) -> None:
    """Dump landed (or we trust the transform). Advance so the next dump uses the next slot."""
    global _drop_next, _land_pose_index, _spawn_cursor
    if not _land_active:
        return
    _drop_next += max(1, int(count))
    _land_pose_index = _drop_next
    _spawn_cursor = max(_spawn_cursor, _drop_next)


def pin_newest_dump(*, limit: int = 1) -> int:
    """Dump just spawned — catch new pickups onto the next shape slots. Spit is not left on the ground."""
    return pull_new_pickups_into_shape(limit=max(1, min(12, int(limit))))


def _horiz_dist2(inv: Any, ox: float, oy: float) -> float | None:
    try:
        loc = inv.K2_GetActorLocation()
        dx = float(loc.X) - ox
        dy = float(loc.Y) - oy
        return dx * dx + dy * dy
    except Exception:
        return None


def _pickup_world_xyz(inv: Any) -> tuple[float, float, float] | None:
    try:
        loc = inv.K2_GetActorLocation()
        return float(loc.X), float(loc.Y), float(loc.Z)
    except Exception:
        return None


def _near_any_planned_slot(inv: Any, *, slack: float = 90.0) -> bool:
    try:
        loc = inv.K2_GetActorLocation()
        x, y = float(loc.X), float(loc.Y)
    except Exception:
        return False
    slack2 = float(slack) * float(slack)
    for sx, sy, _sz in _drop_plan:
        dx = x - float(sx)
        dy = y - float(sy)
        if dx * dx + dy * dy <= slack2:
            return True
    return False


def _slot_for_caught_pickup(inv: Any, index: int, *, pool_name: str = "") -> tuple[float, float, float]:
    """Keep dump items on the silhouette they already spawned into.

    Freeze only if this pickup is already on ITS assigned slot. Freezing because
    it is near *any* slot adopted leftover guns from a previous dump that still
    sat in the same front volume (psycho / firehawk "coming out of" the last shape).
    """
    if not pool_name:
        pool_name = str(_land_slot_pools.get(int(index)) or "")
    planned = _slot_for_new_pickup(inv, index, pool_name=pool_name)
    if _drop_shape == "car":
        return planned
    if not _drop_plan or _shape_hold_active():
        return planned
    xyz = _pickup_world_xyz(inv)
    if xyz is None:
        return planned
    x, y, z = xyz
    if abs(x) < 1.0 and abs(y) < 1.0 and abs(z) < 1.0:
        return planned
    dx = x - float(planned[0])
    dy = y - float(planned[1])
    dz = z - float(planned[2])
    # Never adopt ground Z — that froze feet-spit under roof slots and looked random on guests.
    if dx * dx + dy * dy <= 110.0 * 110.0:
        return (x, y, float(planned[2]))
    return planned


def _iter_newest_dump_pickups(*, newest: int = 16, fresh: bool = False) -> list[Any]:
    """Last few dump actors only — reuse the capped scan, not another world sweep."""
    out: list[Any] = []
    take = max(4, min(32, int(newest)))
    for addr, inv in _raw_pickup_scan(fresh=fresh):
        _pickup_by_addr[addr] = inv
        out.append(inv)
        if len(out) >= take:
            break
    return out


def _float_or_pin_addrs() -> set[int]:
    addrs = {int(job.get("addr") or 0) for job in _float_jobs}
    addrs |= {int(row.get("addr") or 0) for row in _pinned_slots}
    return {a for a in addrs if a}


def _nearest_planned_slot(inv: Any) -> tuple[float, float, float] | None:
    if not _drop_plan:
        return None
    try:
        loc = inv.K2_GetActorLocation()
        x, y = float(loc.X), float(loc.Y)
    except Exception:
        return None
    best: tuple[float, float, float] | None = None
    best_d: float | None = None
    for slot in _drop_plan:
        dx = x - float(slot[0])
        dy = y - float(slot[1])
        d2 = dx * dx + dy * dy
        if best_d is None or d2 < best_d:
            best_d = d2
            best = (float(slot[0]), float(slot[1]), float(slot[2]))
    return best


def _straggler_radius2() -> float:
    """Squared pickup radius for the final sweep.

    A fixed 560 was smaller than the silhouette itself on wide shapes, so items
    that drifted off — the ones this sweep exists to recover — were out of range.
    """
    ox, oy = _drop_origin[0], _drop_origin[1]
    bounds = _shape_xy_bounds()
    reach = 560.0
    if bounds is not None:
        x0, x1, y0, y1 = bounds
        for cx, cy in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
            dx = float(cx) - ox
            dy = float(cy) - oy
            reach = max(reach, math.sqrt(dx * dx + dy * dy))
    reach += 700.0
    return reach * reach


def pin_stragglers(*, limit: int = 8, fresh: bool = True) -> int:
    """Dump spit at the player / behind the silhouette → remaining shape slots."""
    global _drop_next, _drop_seen, _pin_tick
    if not _land_active or not _world_alive():
        return 0
    _ensure_drop_plan_built()
    if not _drop_plan and _drop_shape not in PILE_GROUP_SHAPES:
        return 0
    ox, oy = _drop_origin[0], _drop_origin[1]
    near_player2 = _straggler_radius2()
    busy = _float_or_pin_addrs()
    caught = 0
    budget = max(1, min(32, int(limit)))
    for addr, inv in _raw_pickup_scan(fresh=bool(fresh)):
        if caught >= budget:
            break
        if not addr:
            continue
        if addr in busy:
            continue
        key = _pickup_key(inv)
        if key in _drop_preexisting or key in _drop_seen:
            continue
        if _shape_grab_excluded_inv(inv) or _shape_grab_excluded_addr(addr):
            continue
        hd2 = _horiz_dist2(inv, ox, oy)
        if hd2 is None or hd2 > near_player2:
            continue
        idx = _drop_next
        slot = _slot_for_new_pickup(inv, idx)
        if _shape_hold_active():
            if not _pin_pickup_to_slot(inv, slot, index=idx, hold=True):
                if not _queue_drop_job(inv, slot, index=idx):
                    continue
        elif not _queue_drop_job(inv, slot, index=idx):
            continue
        _drop_next += 1
        _drop_seen.add(key)
        caught += 1
    if caught:
        arm_overhead_catch(12.0)
        # Mid-dump catch: no per-batch net burst (lag). settle_landing_loot syncs guests.
    return caught


def pin_feet_spit(*, limit: int = 8) -> int:
    return pin_stragglers(limit=limit)


def _defer_front_xyz(
    index: int,
    ox: float,
    oy: float,
    oz: float,
    yaw_rad: float,
) -> tuple[float, float, float]:
    """Visible pile a few feet in front — not inside the pawn."""
    idx = max(0, int(index))
    col = idx % 6
    row = (idx // 6) % 5
    stack = idx // 30
    fwd = _DEFER_FORWARD + row * 28.0
    side = (col - 2.5) * 36.0
    up = _DEFER_UP + stack * 18.0 + (idx % 3) * 8.0
    return (
        ox + math.cos(yaw_rad) * fwd + (-math.sin(yaw_rad)) * side,
        oy + math.sin(yaw_rad) * fwd + math.cos(yaw_rad) * side,
        oz + up,
    )


def spawn_drop_pose(index: int, *, pool_name: str = "", inv: Any = None) -> tuple[float, float, float] | None:
    """World XYZ to spawn at so catch can animate into the matching slot."""
    _ensure_drop_plan_built()
    if _defer_shape:
        anchor = _player_anchor()
        if anchor is None:
            return None
        _pawn, ox, oy, oz, yaw = anchor
        return _defer_front_xyz(index, ox, oy, oz, yaw)
    if _drop_shape == "car" and _drop_part_plans.get("car_wheel"):
        part = _car_take_part_slot(inv=inv, pool_name=pool_name)
        if part is not None:
            return part
    slot = planned_world_slot(index)
    if slot is None:
        return None
    if _instant_land_mode():
        return slot
    x0, y0, z0 = _start_xyz_for_slot(slot, index)
    return x0, y0, z0


def peek_spawn_land_index() -> int | None:
    """Slot index for the next shaped world spawn (does not advance cursor)."""
    if not _land_active:
        return None
    _ensure_drop_plan_built()
    if _defer_shape:
        return int(_defer_dump_index)
    return max(int(_spawn_cursor), int(_drop_next))


def next_spawn_land_world(player_location: Any, player_rotation: Any) -> tuple[Any, Any] | None:
    """Pose for the next silhouette slot.

    This advances on its own rather than waiting for the catcher. While it was
    driven by _drop_next, a single missed catch aimed every later spawn at that
    same slot, where they stacked and shoved each other out across the floor.
    """
    global _spawn_cursor, _defer_dump_index
    if not _land_active:
        return None
    _ensure_drop_plan_built()
    if _defer_shape:
        idx = int(_defer_dump_index)
        _defer_dump_index = idx + 1
        yaw_deg = float(getattr(player_rotation, "Yaw", 0.0) or 0.0)
        x, y, z = _defer_front_xyz(
            idx,
            float(getattr(player_location, "X", 0.0) or 0.0),
            float(getattr(player_location, "Y", 0.0) or 0.0),
            float(getattr(player_location, "Z", 0.0) or 0.0),
            math.radians(yaw_deg),
        )
        return _make_vector(x, y, z), _make_rotator(0.0, yaw_deg, 0.0)
    index = max(int(_spawn_cursor), int(_drop_next))
    posed = spawn_drop_pose(index)
    if posed is None:
        return None
    _spawn_cursor = index + 1
    x, y, z = posed
    loc = _make_vector(x, y, z)
    yaw_r, pitch, roll = _rot_for_xyz(index, x, y, z)
    rot = _make_rotator(pitch, math.degrees(yaw_r), roll)
    return loc, rot


def rotator_for_world_slot(index: int, x: float, y: float, z: float) -> Any:
    """Public spawn rotator for a planned world slot (mixed standing / lying guns)."""
    yaw_r, pitch, roll = _rot_for_xyz(index, x, y, z)
    return _make_rotator(pitch, math.degrees(yaw_r), roll)


def invalidate_pickup_cache() -> None:
    global _pickup_cache, _pickup_cache_at
    _pickup_cache = []
    _pickup_cache_at = 0.0


def landing_label() -> str:
    if not _land_active:
        return ""
    shape = _land_user_shape if _land_user_shape != "none" else _drop_shape
    return f"{shape}/{_drop_mode}"


def yank_new_loot_in_front(*, before_keys: set[str] | None = None, limit: int = 6) -> int:
    """Move freshly spawned pickups to a pile in front of the player.

    Used after singular Spawn selected when FromSerial / engine spit lands
    over the shoulder. Shape landings handle their own placement.
    Requires before_keys — without it this teleports the whole nearby pile
    and guns flash then vanish (under world / out of verify radius).
    """
    if _land_active or not _world_alive():
        return 0
    if before_keys is None:
        return 0
    try:
        anchor = _player_anchor()
    except Exception:
        return 0
    if anchor is None:
        return 0
    _pawn, ox, oy, oz, yaw = anchor
    seen = before_keys if isinstance(before_keys, set) else set()
    moved = 0
    budget = max(1, min(16, int(limit)))
    for idx, (_addr, inv) in enumerate(_raw_pickup_scan(fresh=True)):
        if moved >= budget:
            break
        key = _pickup_key(inv)
        if not key or key in seen:
            continue
        fx, fy, fz = _defer_front_xyz(moved, ox, oy, oz, yaw)
        if _teleport_pickup(inv, fx, fy, fz, yaw, freeze=False):
            moved += 1
    return moved


def pull_new_pickups_into_shape(*, limit: int = 12, fresh: bool = False) -> int:
    """Catch dump spit onto the next shape slots. Motion ticks separately."""
    global _catch_last_at
    if not _land_active or not _world_alive():
        return 0
    _ensure_drop_plan_built()
    if not _drop_plan and _drop_shape not in PILE_GROUP_SHAPES:
        return 0
    try:
        caught = catch_overhead_drops(fresh=bool(fresh), limit=max(1, int(limit)))
    except Exception:
        caught = 0
    _catch_last_at = time.monotonic()
    if caught:
        arm_overhead_catch(12.0)
    return caught


def place_new_drops_now() -> int:
    return pull_new_pickups_into_shape(limit=8)


def after_spawn_landing_tick() -> None:
    """Do not find_all here — pump/shiny ticks call pull_new_pickups_into_shape once."""
    if _land_active:
        arm_overhead_catch(12.0)


def snapshot_pickup_ids() -> set[str]:
    """Every pickup that already exists, uncapped.

    A row missed here later reads as a fresh dump actor and gets pulled out of
    an existing layout into a new slot.
    """
    invalidate_pickup_cache()
    return {_key_for_addr(addr) for addr, _inv in _raw_pickup_scan(fresh=True)}


def _lock_unseen_dump(*, limit: int = 8, fresh: bool = False) -> int:
    """Hard-pin dump actors onto the next shape slot. Never freeze at the player's feet."""
    locked = 0
    _ensure_drop_plan_built()
    if not _drop_plan:
        return 0
    for inv in _iter_unseen_pickups(limit=max(1, int(limit)), ignore_frozen=True, fresh=fresh):
        key = _pickup_key(inv)
        if key in _drop_seen:
            continue
        if _shape_grab_excluded_inv(inv):
            _drop_seen.add(key)
            continue
        idx = _drop_next
        slot = _slot_for_caught_pickup(inv, idx)
        pinned = _pin_pickup_to_slot(inv, slot, index=idx, hold=True)
        if not pinned:
            pinned = _queue_drop_job(inv, slot, index=idx)
        if not pinned:
            continue
        _drop_next += 1
        _drop_seen.add(key)
        _frozen_dump.add(key)
        locked += 1
    return locked


def after_dump_spawn(count: int = 1) -> None:
    """Pin each new spawn onto the silhouette. Cache-first during bulk — no find_all every item."""
    global _bulk_after_dump_scan_at
    if not _land_active:
        return
    arm_overhead_catch(12.0)
    if _defer_shape:
        return
    if not (_bulk_healthcheck_mode and not _landing_settle_done) and not _shape_hold_active():
        arm_deferred_catch(12.0)
    n = max(1, min(6, int(count)))
    now = time.monotonic()
    is_2d = str(_drop_shape or "") in SHAPE_2D_NAMES
    is_hold = _shape_hold_active()
    if is_hold:
        # Spawn All + dump was find_all'ing ~every 0.22s → multi-minute car builds.
        fresh_gap = 1.15 if _bulk_healthcheck_mode else 0.70
        if _want_coop_replicate():
            fresh_gap = max(fresh_gap, 2.10 if _bulk_healthcheck_mode else 1.35)
        allow_fresh = (now - _bulk_after_dump_scan_at) >= fresh_gap
        caught = catch_overhead_drops(fresh=False, limit=n)
        if caught <= 0:
            caught = pull_new_pickups_into_shape(limit=n, fresh=False)
        if caught <= 0 and allow_fresh:
            invalidate_pickup_cache()
            caught = catch_overhead_drops(fresh=True, limit=n)
            if caught <= 0:
                caught = _lock_unseen_dump(limit=n, fresh=True)
        if caught or allow_fresh:
            _bulk_after_dump_scan_at = now
        # Live lobby build: rare drip only — mid-dump ForceNet was host lag on ULM grids.
        if caught > 0 and _want_coop_replicate() and is_hold:
            try:
                _schedule_coop_pin_tail(limit=1)
            except Exception:
                pass
        return
    if is_2d:
        fresh = (now - _bulk_after_dump_scan_at) >= (1.05 if _want_coop_replicate() else 0.70)
        if fresh:
            invalidate_pickup_cache()
    else:
        fresh = (now - _catch_last_at) >= 0.40
    caught = pull_new_pickups_into_shape(limit=n, fresh=fresh)
    if caught <= 0 and is_hold and fresh:
        caught = _lock_unseen_dump(limit=n, fresh=True)
    if is_hold and caught <= 0 and fresh:
        caught += pull_new_pickups_into_shape(limit=n, fresh=True)
        if caught <= 0:
            caught += _lock_unseen_dump(limit=n, fresh=True)
    if fresh or caught:
        _bulk_after_dump_scan_at = now


def arm_deferred_catch(seconds: float = 1.0) -> None:
    global _deferred_catch_at, _deferred_catch_until, _deferred_catch_empty
    now = time.monotonic()
    _deferred_catch_at = now
    _deferred_catch_until = max(_deferred_catch_until, now + max(0.2, float(seconds)))
    _deferred_catch_empty = 0


def settle_landing_loot(*, limit: int = 16) -> int:
    """End of Drop All / Spawn All: pull leftover feet-spit onto remaining slots."""
    global _landing_settle_done, _burst_replicate_at, _deferred_catch_until, _deferred_catch_at
    if not _land_active or not _world_alive():
        return 0
    if _landing_settle_done:
        return 0
    _landing_settle_done = True
    n = pull_new_pickups_into_shape(limit=max(4, min(160, int(limit))), fresh=True)
    try:
        # Fold dump spit into silhouette slots — never hide/teleport-away (that looked like dupes).
        n += int(pin_stragglers(limit=max(16, min(96, int(limit) * 2))))
        n += int(pin_stragglers(limit=max(8, min(48, int(limit))), fresh=True))
    except Exception:
        pass
    hold_n_early = held_pin_count()
    coop = False
    try:
        coop = bool(_want_coop_replicate())
    except Exception:
        coop = False
    # Large co-op houses: skip deferred catch — it grew pins during ForceNetUpdate and AVd.
    if not (coop and hold_n_early > 80):
        arm_deferred_catch(10.0)
    else:
        _deferred_catch_until = 0.0
        _deferred_catch_at = 0.0
    _arm_peel_clock()
    if _is_nova_shape():
        # Pulse must run even if a prior dump left catch/bulk paused.
        try:
            pause_landing_catch(False)
            set_bulk_healthcheck_mode(False)
        except Exception:
            pass
        # Stay in air only keeps the final 3D sphere after the pulse finishes.
        _arm_nova_explode(delay=0.35)
        _log("Nova ball packed — pulse armed.")
    if coop and _pinned_slots:
        try:
            tracked = _build_layout_entries_from_pins()
            if _is_nova_shape():
                _log("Co-op nova finishing locally; final pickup-safe publish follows.")
            else:
                _arm_coop_pickup_safe(delay=0.15)
                _log("Co-op shape publishing (held silhouette — Use to collect).")
            _log_dev(f"Co-op settle: tracked={tracked}.")
        except Exception as exc:
            _log_dev(f"guest sync at settle failed: {exc!r}")
    return n


_SHINY_LAYOUT_BASES: dict[str, tuple[float, float]] = {
    "house": (200.0, 72.0),
    "globe": (175.0, 68.0),
    "dome": (175.0, 68.0),
    "pyramid": (190.0, 70.0),
    "pyramid_3d": (190.0, 70.0),
    "boat": (180.0, 70.0),
    "car": (340.0, 88.0),
    "psycho": (210.0, 74.0),
    "claptrap": (230.0, 64.0),
    "dna_helix": (185.0, 70.0),
    "circle": (185.0, 78.0),
    "star": (200.0, 76.0),
    "heart": (190.0, 74.0),
    "diamond_3d": (195.0, 70.0),
    "blocks": (200.0, 68.0),
    "cube": (180.0, 70.0),
    "torus": (190.0, 68.0),
    "crown": (185.0, 70.0),
    "ufo": (200.0, 68.0),
    "rocket": (175.0, 66.0),
    "gear": (185.0, 70.0),
    "nova": (210.0, 72.0),
    "forbidden_one": (210.0, 70.0),
    "forbidden_pair": (200.0, 72.0),
    "type_piles": (220.0, 76.0),
    "unique_piles": (240.0, 74.0),
}
_BULK_LAYOUT_BASES: dict[str, tuple[float, float]] = {
    "house": (240.0, 68.0),
    "globe": (220.0, 62.0),
    "dome": (220.0, 62.0),
    "pyramid": (240.0, 66.0),
    "pyramid_3d": (230.0, 64.0),
    "boat": (240.0, 68.0),
    "car": (360.0, 92.0),
    "psycho": (230.0, 70.0),
    "firehawk": (260.0, 70.0),
    "claptrap": (310.0, 68.0),
    "dna_helix": (220.0, 66.0),
    "circle": (240.0, 70.0),
    "star": (250.0, 70.0),
    "heart": (240.0, 70.0),
    "diamond_3d": (230.0, 64.0),
    "blocks": (240.0, 64.0),
    "cube": (220.0, 66.0),
    "torus": (230.0, 64.0),
    "crown": (220.0, 66.0),
    "ufo": (240.0, 64.0),
    "rocket": (210.0, 64.0),
    "gear": (220.0, 66.0),
    "nova": (280.0, 68.0),
    "forbidden_one": (280.0, 68.0),
    "forbidden_pair": (250.0, 70.0),
    "type_piles": (280.0, 72.0),
    "unique_piles": (300.0, 70.0),
}


def land_layout_for(
    shape: str,
    count: int,
    profile: str = "shiny",
    *,
    radius: float | None = None,
    spacing: float | None = None,
) -> tuple[float, float]:
    """Per-shape + item-count layout. Shiny dumps stay compact; bulk densifies, it does not balloon 3D."""
    name = _normalize_shape_name(shape)
    if name in ("", "none", "off", "no", "vanilla"):
        name = "circle"
    prof = str(profile or "shiny").strip().lower()
    bases = _BULK_LAYOUT_BASES if prof == "bulk" else _SHINY_LAYOUT_BASES
    base_r, base_s = bases.get(name, (200.0, 72.0) if prof != "bulk" else (240.0, 68.0))
    if radius is not None:
        try:
            base_r = float(radius)
        except Exception:
            pass
    if spacing is not None:
        try:
            base_s = float(spacing)
        except Exception:
            pass
    n = max(1, int(count))
    if prof == "bulk":
        # Hundreds of filtered items should pack the same silhouette, not grow a mansion.
        s = base_s
        if name in SHAPE_3D_NAMES:
            if name in ("forbidden_one", "forbidden_pair"):
                scale = min(1.12, max(1.0, math.sqrt(n / 350.0)))
                r = min(320.0, base_r * scale)
            else:
                scale = min(1.08, max(1.0, math.sqrt(n / 500.0)))
                cap = 340.0 if name == "claptrap" else (240.0 if name == "house" else 260.0)
                if name in ("globe", "dome"):
                    cap = 240.0
                r = min(cap, base_r * scale)
        elif name in ("type_piles", "unique_piles"):
            scale = min(1.35, max(1.0, math.sqrt(n / 120.0)))
            r = min(420.0, base_r * scale)
            s = max(base_s, 62.0)
        else:
            scale = min(1.18, max(1.0, math.sqrt(n / 280.0)))
            r = min(320.0, base_r * scale)
    else:
        # ~80–130 shinies: keep the wireframe tight so items fill the silhouette.
        scale = min(1.0, max(0.58, math.sqrt(n / 88.0)))
        r = max(140.0, base_r * scale)
        s = max(52.0, base_s * min(1.0, max(0.72, scale)))
    clamped = clamp_layout_params(radius=r, spacing=s)
    return float(clamped["radius"]), float(clamped["spacing"])


def shape_complete_slot_count(shape: str, *, profile: str = "shiny") -> int:
    """How many guns a silhouette needs to read as that logo (fill-until-complete)."""
    name = _normalize_shape_name(shape)
    if name in ("", "none", "off", "no", "vanilla"):
        return 0
    complete = {
        "claptrap": 240,
        "psycho": 220,
        "firehawk": 240,
        "house": 420,
        "car": 200,
        "boat": 180,
        "vault": 200,
        "forbidden_one": 260,
        "forbidden_pair": 280,
        "globe": 200,
        "nova": 140,
        "dome": 180,
        "pyramid_3d": 200,
        "pyramid": 160,
        "dna_helix": 180,
        "smiley": 140,
        "heart": 140,
        "star": 140,
        "type_piles": 180,
        "unique_piles": 180,
    }
    if name in complete:
        return int(complete[name])
    if name in SHAPE_3D_NAMES:
        return 180
    return 120


def is_shape_fill_pool_name(pool_name: str) -> bool:
    """SMG / shotgun / rifle pools silhouette well. Skip shields, ammo, class mods."""
    low = str(pool_name or "").strip().lower()
    if not low:
        return False
    if any(tok in low for tok in ("classmod", "shield", "ammo", "currency", "enhancement", "grenade", "gadget", "repkit", "repair", "gift", "guntoter", "present", "cash", "lootbat")):
        return False
    if any(tok in low for tok in ("_sm_", "smg", "_sg_", "shotgun", "_ar_", "assaultrifle", "assault_rifle")):
        return True
    if low.endswith("_sm_05_legendary") or "itempool_sm_05" in low:
        return True
    return False


def land_layout_defaults(profile: str = "shiny") -> dict[str, dict[str, float]]:
    """Base radius/spacing/drop_height per shape for the EXE (before count scaling)."""
    prof = str(profile or "shiny").strip().lower()
    table = _BULK_LAYOUT_BASES if prof == "bulk" else _SHINY_LAYOUT_BASES
    out: dict[str, dict[str, float]] = {}
    for shape, (r, s) in table.items():
        row: dict[str, float] = {"radius": r, "spacing": s}
        if shape == "car":
            row["drop_height"] = float(_CAR_DEFAULT_DROP_HEIGHT)
        out[shape] = row
    return out


def _auto_fit_layout(
    shape: str,
    count: int,
    radius: float,
    spacing: float,
    line_length: float,
) -> tuple[float, float, float]:
    """Grow default radius so hundreds of items still fill the silhouette."""
    n = max(1, int(count))
    r = float(radius)
    s = float(spacing)
    ln = float(line_length)
    is_3d = str(shape or "") in SHAPE_3D_NAMES
    name = str(shape or "")
    if n >= 220:
        if name not in ("globe", "pyramid_3d", "pyramid", "dome"):
            r = max(r, 560.0 if is_3d else 480.0)
        # Keep strokes compact — never stretch line/wave/S across the map.
        ln = min(max(ln, float(_DEFAULT_LINE_LENGTH)), float(_MAX_LINE_LENGTH))
        if s >= 130.0:
            s = 72.0
    elif n >= 80:
        if name not in ("globe", "pyramid_3d", "pyramid", "dome"):
            r = max(r, 320.0 if is_3d else 280.0)
        ln = min(max(ln, float(_DEFAULT_LINE_LENGTH)), float(_MAX_LINE_LENGTH))
    else:
        r = max(r, 240.0)
    if name in ("globe", "pyramid_3d", "dome"):
        r = min(r, 360.0)
    elif name == "pyramid":
        r = min(r, 400.0)
    ln = min(float(ln), float(_MAX_LINE_LENGTH), float(_MAX_LINE_SPAN))
    return r, s, ln


def begin_overhead_drop(
    shape: str = "spiral",
    count: int = 1,
    *,
    mode: str = "slow",
    radius: float = _DEFAULT_RADIUS,
    spacing: float = _DEFAULT_SPACING,
    per_ring: int = _DEFAULT_PER_RING,
    z_bias: float = _DEFAULT_Z_BIAS,
    drop_height: float = _DEFAULT_DROP_HEIGHT,
    stack_height: float = 0.0,
    line_length: float = _DEFAULT_LINE_LENGTH,
    user_shape: str | None = None,
    stay_in_air: Any = None,
    float_on_grab: Any = False,
    peel_after: Any = 0.0,
    shape_text: str = "",
    land_profile: str = "shiny",
) -> str:
    """Shape = land slots. Mode = motion into those slots. Combinations share this path."""
    global _drop_plan, _drop_next, _spawn_cursor, _drop_mode, _drop_yaw, _drop_seen, _frozen_dump, _float_jobs
    global _drop_preexisting, _shape_grab_exclude
    global _pickup_by_addr, _defer_dump_index
    global _status, _DROP_HEIGHT, _drop_origin, _drop_shape, _drop_radius, _drop_spacing
    global _drop_per_ring, _drop_stack, _drop_line_length, _drop_type_counts, _drop_until
    global _land_active, _land_pose_index, _land_user_shape, _loot_world_id
    global _deferred_catch_at, _deferred_catch_until, _landing_settle_done, _drop_part_plans
    global _drop_local_dirs, _drop_unique_order, _last_layout
    global _drop_plan_pending, _drop_plan_target, _drop_plan_build, _after_dump_calls
    global _coop_pins_synced
    global _join_serial_reapply_active, _join_serial_reapply_at, _join_serial_reapply_cursor
    global _land_slot_pools, _land_layout_profile
    shape = _normalize_shape_name(shape)
    if shape_text:
        set_shape_text(shape_text)
    if shape not in SHAPE_NAMES:
        shape = "spiral"
    prof = str(land_profile or _land_layout_profile or "shiny").strip().lower()
    if prof not in ("shiny", "bulk"):
        prof = "shiny"
    _land_layout_profile = prof
    mode_l = normalize_drop_mode(mode)
    if shape == "nova":
        # Always pack -> pulse into the 3D sphere; Stay in air (opt-in) keeps the final ball.
        if mode_l in ("none", "snap", "drip"):
            mode_l = "explode"
        if stay_in_air is None or str(stay_in_air).strip() == "":
            stay_in_air = False
    _set_air_hold(stay_in_air, peel_after, shape=shape)
    set_float_on_grab(float_on_grab)
    n = max(1, int(count))
    anchor = _player_anchor()
    if anchor is None:
        _status = "Overhead drop: load into a character first."
        return _status
    layout = clamp_layout_params(
        radius=radius,
        spacing=spacing,
        per_ring=per_ring,
        line_length=line_length,
        drop_height=drop_height,
        z_bias=z_bias,
        stack_height=stack_height,
    )
    _DROP_HEIGHT = float(layout["drop_height"])
    radius, spacing, per_ring = _tuned_layout(
        shape, float(layout["radius"]), float(layout["spacing"]), int(layout["per_ring"])
    )
    _pawn, ox, oy, oz, yaw = anchor
    oz = oz + float(layout["z_bias"])
    _drop_shape = shape
    _drop_radius = radius
    _drop_spacing = spacing
    _drop_per_ring = per_ring
    _drop_stack = float(layout["stack_height"])
    _drop_line_length = float(layout["line_length"])
    _drop_type_counts = {}
    _drop_unique_order = []
    _drop_part_plans = {}
    _drop_local_dirs = []
    # Defer silhouette math + world find_all — those froze the host on arm.
    _drop_plan = []
    _drop_plan_target = n
    _drop_plan_pending = True
    _drop_plan_build = {
        "shape": shape,
        "n": n,
        "radius": radius,
        "spacing": spacing,
        "per_ring": per_ring,
        "line_length": float(layout["line_length"]),
        "ox": ox,
        "oy": oy,
        "oz": oz,
        "yaw": yaw,
        "shape_text": get_shape_text() if shape == "text" else "",
        "land_profile": prof,
    }
    _drop_next = 0
    _spawn_cursor = 0
    _land_pose_index = 0
    _landing_settle_done = False
    _land_active = True
    _shape_grab_exclude = {}
    _loot_world_id = _current_world_id()
    if user_shape is not None:
        _land_user_shape = "none" if _is_none_shape(user_shape) else str(user_shape)
    else:
        _land_user_shape = shape
    _drop_mode = mode_l
    _drop_yaw = yaw
    _drop_origin = (ox, oy, oz)
    _float_jobs = []
    _preserve_prior_held_shapes()
    _deferred_catch_at = 0.0
    _deferred_catch_until = 0.0
    _after_dump_calls = 0
    _coop_pins_synced = 0
    _join_serial_reapply_active = False
    _join_serial_reapply_at = 0.0
    _join_serial_reapply_cursor = 0
    try:
        from .item_spawn.comp_loot_drop import clear_item_pool_winner_cache

        clear_item_pool_winner_cache()
    except Exception:
        pass
    # Skip snapshot_pickup_ids find_all here — it doubled the start hitch with the
    # first after_dump scan. _preserve_prior_held_shapes seeds seen from prior silhouettes.
    _frozen_dump = set()
    _defer_dump_index = 0
    invalidate_pickup_cache()
    arm_overhead_catch(16.0)
    _last_layout.update(
        {
            "shape": _land_user_shape if _land_user_shape != "none" else shape,
            "radius": radius,
            "spacing": spacing,
            "per_ring": per_ring,
            "z_bias": float(layout["z_bias"]),
            "stack_height": float(layout["stack_height"]),
            "line_length": float(layout["line_length"]),
            "settle": mode_l,
            "drop_height": float(layout["drop_height"]),
            "mode": "land",
            "party_count": _party_count(),
            "applied_at": time.time(),
            "entries": [],
        }
    )
    _status = f"Land in {shape} via {mode_l} ({n} item(s) queued)."
    _log(_status)
    return _status


def _slot_for_new_pickup(inv: Any, index: int, *, pool_name: str = "") -> tuple[float, float, float]:
    ox, oy, oz = _drop_origin
    yaw = _drop_yaw
    if _drop_shape == "car" and _drop_part_plans.get("car_wheel"):
        part = _car_take_part_slot(inv=inv, pool_name=pool_name)
        if part is not None:
            return part
        body = _drop_part_plans.get("car_body") or []
        if body:
            bx, by, bz = body[len(body) // 2]
            return (float(bx), float(by), float(bz) - 10.0)
    if _drop_shape == "type_piles":
        gtype = _classify_gear_type(inv)
        n = int(_drop_type_counts.get(gtype, 0))
        _drop_type_counts[gtype] = n + 1
        centers = _type_pile_centers(list(_TYPE_ORDER), _drop_radius, _drop_spacing)
        cx, cy = centers.get(gtype, centers.get("other", (_drop_radius, 0.0)))
        gap = max(55.0, _drop_spacing * 0.42)
        lx, ly, lz = _pile_grid_local(cx, cy, n, gap=gap, stack=_drop_stack)
        return _world_from_local(ox, oy, oz, yaw, lx, ly, lz)
    if _drop_shape == "unique_piles":
        global _drop_unique_order
        item_key = _classify_exact_item(inv, pool_name=pool_name)
        if item_key not in _drop_unique_order:
            _drop_unique_order.append(item_key)
        n = int(_drop_type_counts.get(item_key, 0))
        _drop_type_counts[item_key] = n + 1
        centers = _unique_pile_centers(_drop_unique_order, _drop_radius, _drop_spacing)
        cx, cy = centers.get(item_key, (_drop_radius, 0.0))
        gap = max(55.0, _drop_spacing * 0.42)
        lx, ly, lz = _pile_grid_local(cx, cy, n, gap=gap, stack=_drop_stack)
        return _world_from_local(ox, oy, oz, yaw, lx, ly, lz)
    if _drop_shape == "rarity_lanes":
        rare = _classify_rarity(inv)
        n = int(_drop_type_counts.get(rare, 0))
        _drop_type_counts[rare] = n + 1
        lane = _RARITY_ORDER.index(rare) if rare in _RARITY_ORDER else len(_RARITY_ORDER) - 1
        fx = _drop_spacing * 1.8 + lane * _drop_spacing * 1.85
        return _world_from_local(ox, oy, oz, yaw, fx, n * _drop_spacing, 0.0)
    if 0 <= index < len(_drop_plan):
        return _drop_plan[index]
    if _drop_plan:
        # Overflow used to stack on the same XY and despawn. Scatter leftover guns
        # across the upper third of the silhouette (house roof / top of other 3D).
        lap = index - len(_drop_plan)
        top = _drop_plan[len(_drop_plan) // 2 :]
        base = top[lap % len(top)]
        spread = 18.0 + (lap % 7) * 4.0
        ang = lap * 2.399963
        return (
            float(base[0]) + math.cos(ang) * spread,
            float(base[1]) + math.sin(ang) * spread,
            float(base[2]) + 6.0 + (lap % 5) * 3.0,
        )
    return _world_from_local(ox, oy, oz, yaw, 220.0, 0.0, 80.0)


def arm_overhead_catch(seconds: float = 8.0) -> None:
    global _drop_until
    _drop_until = max(_drop_until, time.monotonic() + max(1.0, float(seconds)))


def catch_overhead_drops(
    before_ids: set[int] | None = None,
    *,
    fresh: bool = True,
    limit: int = 8,
) -> int:
    """Assign new pickups to the active shape, then fly them into the slot."""
    global _drop_next, _drop_seen
    if not _land_active and time.monotonic() > _drop_until and not _float_jobs:
        return 0
    _ensure_drop_plan_built()
    if not _drop_plan and _drop_shape not in PILE_GROUP_SHAPES:
        return 0
    known = set(_drop_seen)
    if before_ids:
        known |= {str(item) for item in before_ids}
    caught = 0
    budget = max(1, min(12, int(limit)))
    # Pause skips PlayerTick find_all. Dump catch still needs a real scan.
    fresh_scan = bool(fresh)
    for inv in _iter_unseen_pickups(limit=max(budget, 12), fresh=fresh_scan):
        if not _live(inv):
            continue
        key = _pickup_key(inv)
        if key in known:
            continue
        if _shape_grab_excluded_inv(inv):
            known.add(key)
            _drop_seen.add(key)
            continue
        if not _is_shape_gear_pickup(inv, pool_name=str(_land_slot_pools.get(int(_drop_next)) or "")):
            try:
                _hide_pickup(inv)
            except Exception:
                pass
            known.add(key)
            _drop_seen.add(key)
            continue
        idx = _drop_next
        if _shape_hold_active() and _drop_plan and idx >= len(_drop_plan):
            # Overflow: wrap onto existing slots (stacked) instead of dropping.
            pass
        pool_name = str(_land_slot_pools.get(int(idx)) or "")
        # Spawn already placed the gun on a silhouette slot. Freeze there.
        # Nearest-slot snap at 72u yanked later items onto occupied neighbors.
        slot = _slot_for_caught_pickup(inv, idx, pool_name=pool_name)
        slot = _nova_catch_slot(slot, idx)
        if _instant_land_mode() or (
            _is_nova_shape() and _land_active and not _landing_settle_done
        ):
            if not _pin_pickup_to_slot(
                inv, slot, index=idx, hold=_shape_hold_active() or _is_nova_shape()
            ):
                if not _queue_drop_job(inv, slot, index=idx):
                    continue
        elif not _queue_drop_job(inv, slot, index=idx):
            continue
        _drop_next += 1
        _drop_seen.add(key)
        known.add(key)
        caught += 1
        if caught >= budget:
            break
    if caught:
        arm_overhead_catch(12.0)
    return caught


def _start_xyz_for_slot(slot: tuple[float, float, float], index: int = 0) -> tuple[float, float, float]:
    cfg = DROP_MODES.get(_drop_mode) or DROP_MODES["slow"]
    x1, y1, z1 = slot
    style = str(cfg.get("style") or "straight")
    height = _DROP_HEIGHT * float(cfg.get("height_mul") or 1.0)
    ox, oy, oz = _drop_origin
    if _drop_mode == "none" or height <= 1.0:
        return x1, y1, z1
    if _is_peel_drop():
        # Peel drip only — animate silhouette down to ground.
        if z1 > oz + 40.0:
            return x1, y1, z1
        return x1, y1, z1 + max(320.0, height)
    if style == "drip":
        return x1, y1, z1
    # Scripted flight always ends on the slot. Stay over the silhouette —
    # do not start behind the shape at the player's feet.
    if style == "fountain":
        sx, sy = _clamp_xy_to_shape(ox, oy, pad=40.0)
        return sx, sy, oz + 64.0
    if style == "explode":
        # Condensed start in front — pulse out to the final slot.
        return _nova_condensed_world(index)
    if style == "rain":
        rng = random.Random(int(index) * 7919 + 104729)
        jitter = 90.0
        rx = x1 + (rng.random() - 0.5) * jitter
        ry = y1 + (rng.random() - 0.5) * jitter
        rx, ry = _clamp_xy_to_shape(rx, ry, pad=30.0)
        return rx, ry, z1 + max(_DEFAULT_DROP_HEIGHT, height)
    if style == "spiral":
        spin0 = math.pi * 6.0 + (int(index) * 0.47)
        rx = x1 + math.cos(spin0) * 90.0
        ry = y1 + math.sin(spin0) * 90.0
        rx, ry = _clamp_xy_to_shape(rx, ry, pad=30.0)
        return rx, ry, z1 + max(360.0, height)
    return x1, y1, z1 + max(320.0, height)


def _shape_xy_bounds() -> tuple[float, float, float, float] | None:
    if not _drop_plan:
        return None
    xs = [float(p[0]) for p in _drop_plan]
    ys = [float(p[1]) for p in _drop_plan]
    return min(xs), max(xs), min(ys), max(ys)


def _clamp_xy_to_shape(x: float, y: float, *, pad: float = 40.0) -> tuple[float, float]:
    bounds = _shape_xy_bounds()
    if bounds is None:
        return x, y
    x0, x1, y0, y1 = bounds
    p = max(0.0, float(pad))
    return (
        max(x0 - p, min(x1 + p, float(x))),
        max(y0 - p, min(y1 + p, float(y))),
    )


def _rot_for_xyz(index: int, x: float, y: float, z: float) -> tuple[float, float, float]:
    """Yaw rad + pitch/roll deg. Mix standing guns so shapes can use height, not only a flat pancake."""
    yaw0 = float(_drop_yaw)
    ox, oy, oz = _drop_origin
    k = int(index) % 3
    shape = str(_drop_shape or _land_user_shape or "")

    def _mix() -> tuple[float, float, float]:
        if k == 1:
            return yaw0, 90.0, 0.0
        if k == 2:
            return yaw0 + math.pi / 2.0, 0.0, 0.0
        return yaw0, 0.0, 0.0

    def _flat() -> tuple[float, float, float]:
        if k == 2:
            return yaw0 + math.pi / 2.0, 0.0, 0.0
        return yaw0, 0.0, 0.0

    # Car: every gun along the chassis. Yaw 90 sticks rifles out the doors.
    if shape == "car":
        return yaw0, 0.0, 0.0
    if _drop_local_dirs:
        dx, dy, dz = _drop_local_dirs[int(index) % len(_drop_local_dirs)]
        if shape == "house":
            horiz = math.hypot(dx, dy)
            # Vertical corner posts only; walls/floor/roof lie flat like shingles.
            if horiz < 1e-4 and abs(dz) > 1e-4:
                return yaw0, 90.0, 0.0
            if horiz > 1e-4:
                return yaw0 + math.atan2(dy, dx), 0.0, 0.0
            return yaw0, 0.0, 0.0
        yaw, pitch, roll = _yaw_pitch_along(dx, dy, dz)
        if shape in SHAPE_2D_NAMES:
            return yaw, 0.0, 0.0
        return yaw, pitch, roll
    if shape in SHAPE_2D_NAMES:
        return _flat()

    if ox == 0.0 and oy == 0.0 and oz == 0.0:
        return _mix()
    lx, ly, lz = _world_to_local(ox, oy, oz, yaw0, x, y, z)
    ax, ay, az = abs(lx), abs(ly), abs(lz)

    if shape == "house":
        # Flat cottage: guns lie on wall/floor/roof runs; only corner posts stand.
        hr = float(_drop_radius or 200.0)
        hd = max(95.0, hr * 0.98)
        hw = max(72.0, hr * 0.80)
        if az < 42.0:
            if ax >= ay:
                return yaw0, 0.0, 0.0
            return yaw0 + math.pi / 2.0, 0.0, 0.0
        # Corner posts (near both outer edges and tall)
        if ax > hd * 0.82 and ay > hw * 0.82:
            return yaw0, 90.0, 0.0
        # All other wall/roof strokes — horizontal barrel, no slope-pitch porcupine
        if ax >= ay:
            return yaw0, 0.0, 0.0
        return yaw0 + math.pi / 2.0, 0.0, 0.0

    if shape == "boat":
        # Mast stands. Hull and cabin lie along the boat like the car.
        if az > 95.0 and ay < 36.0:
            return yaw0, 90.0, 0.0
        return yaw0, 0.0, 0.0

    if shape == "dna_helix":
        # Do not treat the cap as a roof — that laid random strand guns flat.
        if math.hypot(lx, ly) < 42.0:
            return yaw0, 0.0, 0.0
        return yaw0, 90.0, 0.0

    if shape == "pyramid_3d":
        # Base square lies. Rising edges follow the slope — they are not pitch-90 pillars.
        if az < 48.0:
            if ax >= ay:
                return yaw0, 0.0, 0.0
            return yaw0 + math.pi / 2.0, 0.0, 0.0
        yaw = yaw0 + math.atan2(ly, lx) if (ax > 1.0 or ay > 1.0) else yaw0
        pitch = math.degrees(math.atan2(az, max(math.hypot(lx, ly), 1.0)))
        return yaw, min(62.0, max(16.0, pitch)), 0.0

    if shape == "claptrap":
        # Antenna stands. Head/body front panels face the player. Arms along +Y.
        if az > 150.0 and ax < 52.0 and ay < 40.0:
            return yaw0, 90.0, 0.0
        if lx < -4.0 and az > 40.0:
            if ay > 38.0 and az < 110.0:
                return yaw0 + math.pi / 2.0, 0.0, 0.0
            return yaw0, 90.0, 0.0
        if az > 28.0 and max(ax, ay) > 22.0:
            return yaw0, 90.0, 0.0
        return yaw0, 0.0, 0.0

    if shape == "forbidden_one":
        horiz = max(math.hypot(lx, ly), 1.0)
        yaw = yaw0 + math.atan2(ly, lx) if horiz > 1.0 else yaw0
        pitch = min(78.0, max(12.0, math.degrees(math.atan2(lz, horiz))))
        return yaw, pitch, 0.0

    if shape == "forbidden_pair":
        # Orient from each globe's center. Radial-from-player speared the cleavage
        # and physics-yeeted the second side after the first globe filled.
        best = _forbidden_pair_globes[0]
        best_d = 1e18
        for gcx, gcy, gcz in _forbidden_pair_globes:
            d = (lx - gcx) * (lx - gcx) + (ly - gcy) * (ly - gcy)
            if d < best_d:
                best_d = d
                best = (gcx, gcy, gcz)
        dx, dy, dz = lx - best[0], ly - best[1], lz - best[2]
        horiz = max(math.hypot(dx, dy), 1.0)
        yaw = yaw0 + math.atan2(dy, dx)
        pitch = min(36.0, max(8.0, abs(math.degrees(math.atan2(dz, horiz)))))
        return yaw, pitch, 0.0

    is_3d = shape in SHAPE_3D_NAMES or az > 28.0
    # Roof / cap (high and centered): lie flat. Standing those turns a house into pillars.
    if is_3d and az > 28.0 and az >= max(ax, ay) * 0.85:
        return _flat()
    # Walls / meridians (high and outward): stand so ~133 shinies still draw height.
    if is_3d and az > 28.0 and max(ax, ay) > 28.0:
        return yaw0, 90.0, 0.0
    if is_3d and ay > ax * 1.08 and ay > 22.0:
        return yaw0 + math.pi / 2.0, 0.0, 0.0
    return _mix()


def _remember_pin(
    inv: Any,
    x: float,
    y: float,
    z: float,
    yaw: float,
    *,
    pitch: float = 0.0,
    roll: float = 0.0,
    hold: bool | None = None,
    slot_index: int | None = None,
) -> None:
    """Two delayed settle passes, then release — or keep restamping while Stay in air is on."""
    holding = _should_hold_in_air() if hold is None else bool(hold)
    if hold is None and _land_active:
        shape = _normalize_shape_name(_drop_shape or _land_user_shape or "")
        if shape in SHAPE_3D_NAMES:
            holding = True
    # Catch-pause skips PlayerTick find_all, not pins on active shape slots.
    # Without a pin during dump drain the first teleport does not stick and
    # the item falls before deferred catch can run.
    if _catch_paused and not holding and not (_land_active and _drop_plan):
        return
    addr = _uobject_addr(inv)
    if not addr:
        return
    try:
        if _pickup_skip_shape(inv):
            return
    except Exception:
        return
    # Cap held silhouette size — 500+ + ForceNet is the stringlight/house AV.
    cap = _MAX_SHAPE_PINS_COOP if _want_coop_replicate() else _MAX_SHAPE_PINS_SOLO
    if len(_pinned_slots) >= cap and not any(int(row.get("addr") or 0) == addr for row in _pinned_slots):
        return
    _pickup_by_addr[addr] = inv
    now = time.monotonic()
    # Co-op publish needs pins alive past the old 6s non-hold TTL — otherwise
    # _tick_pins drops the house mid ForceNet and guests only see a partial shape.
    coop = False
    try:
        coop = bool(_want_coop_replicate())
    except Exception:
        coop = False
    expires = now + (600.0 if (holding or coop) else 6.0)
    retries = 2
    restamp_at = now + 0.9
    payload = {
        "x": x,
        "y": y,
        "z": z,
        "yaw": yaw,
        "pitch": pitch,
        "roll": roll,
        "next": restamp_at,
        "expires": expires,
        "retries": retries,
        "hold": holding,
    }
    if slot_index is not None:
        try:
            payload["slot_index"] = int(slot_index)
            pool = str(_land_slot_pools.get(int(slot_index)) or "")
            if pool:
                payload["pool_name"] = pool
        except Exception:
            pass
    try:
        pin_serial = ""
        if not _mid_shape_dump():
            pin_serial = serial_from_pickup(inv)
        if not pin_serial and slot_index is not None:
            pin_serial = _planned_serial_for_slot(int(slot_index))
        if pin_serial:
            payload["serial"] = pin_serial
    except Exception:
        pass
    for row in _pinned_slots:
        if int(row.get("addr") or 0) == addr:
            row.update(payload)
            row.pop("guest_ok", None)
            row.pop("guest_fail", None)
            return
    payload["addr"] = addr
    _pinned_slots.append(payload)


def _clear_pins() -> None:
    global _pinned_slots
    global _coop_pickup_safe_active, _coop_pickup_unlock_at, _coop_pickup_unlock_cursor
    global _coop_keep_freeze
    _pinned_slots = []
    _coop_pickup_safe_active = False
    _coop_pickup_unlock_at = 0.0
    _coop_pickup_unlock_cursor = 0
    _coop_keep_freeze = False


def _preserve_prior_held_shapes() -> None:
    """Keep frozen silhouettes when arming a new shape — do not wipe prior world loot."""
    global _pinned_slots, _pickup_by_addr, _drop_seen, _drop_preexisting, _float_jobs, _land_slot_pools
    kept: list[dict[str, Any]] = []
    preserved: dict[int, Any] = {}
    frozen: set[str] = set(_drop_preexisting)
    kept_addrs: set[int] = set()
    kept_pools = dict(_land_slot_pools)
    for row in _pinned_slots:
        if not row.get("hold"):
            continue
        kept.append(dict(row))
        addr = int(row.get("addr") or 0)
        if addr:
            kept_addrs.add(addr)
            if addr in _pickup_by_addr:
                preserved[addr] = _pickup_by_addr[addr]
            frozen.add(_key_for_addr(addr))
        serial = str(row.get("serial") or "")
        if serial:
            frozen.add(serial)
    _pinned_slots = kept
    _pickup_by_addr = preserved
    _drop_preexisting = frozen
    _drop_seen = set(frozen)
    _float_jobs = [j for j in _float_jobs if int(j.get("addr") or 0) in kept_addrs]
    _land_slot_pools = kept_pools


def _tick_pins() -> None:
    global _pinned_slots, _pin_tick, _join_refresh_needed
    now = time.monotonic()
    if not _pinned_slots or _peel_started:
        return
    # Pickup-safe publish owns net + unlock — pin heartbeat would expire/yank slots.
    if _coop_pickup_safe_active:
        return
    hold_rows = any(row.get("hold") for row in _pinned_slots)
    if _in_join_quiet() and not hold_rows:
        return
    if _join_refresh_needed:
        _join_refresh_needed = False
        try:
            _refresh_live_pickups()
        except Exception:
            pass
    # Mid-dump: pins happen in after_dump_spawn. Restamping hundreds of slots AVs.
    if _land_active and not _landing_settle_done:
        return
    holding = _shape_hold_active()
    join_quiet = _in_join_quiet(now)
    if join_quiet and hold_rows:
        return
    # 2D / non-hold drains: skip pin maintenance while slots are still filling.
    if _land_active and not holding:
        return
    tick_mod = 1 if (join_quiet and hold_rows) else (2 if (_float_jobs and holding) else (4 if (_land_active and holding) else 10))
    if (
        _landing_settle_done
        and not _float_jobs
        and _want_coop_replicate()
        and _pinned_slots
        and not join_quiet
    ):
        # Settled lobby: check often enough to hand off grabs before heartbeat yanks.
        tick_mod = min(tick_mod, 2)
    _pin_tick += 1
    if _pin_tick % tick_mod:
        return
    flying = {int(job.get("addr") or 0) for job in _float_jobs}
    # Also skip pins currently in the float-on-grab gag.
    flying |= {int(job.get("addr") or 0) for job in _grab_float_jobs}
    live: list[dict[str, Any]] = []
    checked = 0
    pin_check_budget = 28 if (join_quiet and hold_rows) else (12 if (_land_active and holding) else 8)
    if _landing_settle_done and hold_rows:
        # Scan more slots so Attract/grab drift is caught before ForceNet restamp.
        pin_check_budget = max(pin_check_budget, 18 if _want_coop_replicate() else 12)
    coop_pins = bool(
        _want_coop_replicate()
        and _pinned_slots
        and not join_quiet
        and not _progression_network_busy()
        and _landing_settle_done
        and not _mid_shape_dump()
    )
    # Do NOT proximity-release with gravity — that dropped guns on guest click
    # without ever completing collect. Guest collect is ServerUse → backpack.
    party_xyz: list[tuple[float, float, float]] = []
    near_budget = 0
    _ = coop_pins
    # Snapshot — release/drop mutate _pinned_slots mid-pass.
    for row in list(_pinned_slots):
        expires = float(row.get("expires") or 0.0)
        if expires and now > expires and not row.get("hold"):
            # Never drop mid guest-publish (partial shape + frozen unusable loot).
            if _coop_pickup_safe_active:
                try:
                    row["expires"] = now + 600.0
                except Exception:
                    pass
                live.append(row)
                continue
            # Solo/expired flat pin: restore world pickup before forgetting.
            addr_e = int(row.get("addr") or 0)
            inv_e = _live_pickup(addr_e) if addr_e else None
            if inv_e is not None and _live(inv_e):
                try:
                    _restore_world_pickup_for_grab(inv_e)
                except Exception:
                    pass
            continue
        if checked >= pin_check_budget:
            live.append(row)
            continue
        if _in_join_quiet() and not row.get("hold"):
            live.append(row)
            continue
        addr = int(row.get("addr") or 0)
        if addr in flying:
            live.append(row)
            continue
        # Never use row["inv"] — that wrapper is what crashed the dump.
        inv = _resolve_pin_inv(row, fresh=bool(_in_join_quiet() and row.get("hold")))
        if inv is None and addr:
            inv = _live_pickup(addr)
        if inv is None:
            # Addr map can lag one tick behind find_all. Held silhouettes must
            # not be dropped after a join (empty map used to flatten the house).
            misses = int(row.get("misses") or 0) + 1
            keep = 80 if row.get("hold") else 4
            if misses < keep:
                row["misses"] = misses
                live.append(row)
            continue
        if not _live(inv):
            _drop_dead_pin(row)
            continue
        row["misses"] = 0
        checked += 1
        if addr and _shape_grab_excluded_addr(addr):
            # Already handed to a player — drop pin tracking.
            continue
        if _shape_grab_excluded_inv(inv):
            continue
        if party_xyz and near_budget > 0 and _party_near_pin(row, party_xyz):
            near_budget -= 1
            try:
                _release_pin_for_pickup(inv, row)
            except Exception:
                _drop_dead_pin(row)
            continue
        drifted = False
        dist2 = 0.0
        loc = None
        try:
            if not _live(inv):
                _drop_dead_pin(row)
                continue
            loc = inv.K2_GetActorLocation()
            dx = float(loc.X) - float(row["x"])
            dy = float(loc.Y) - float(row["y"])
            dz = float(loc.Z) - float(row["z"])
            dist2 = dx * dx + dy * dy + dz * dz
            drifted = dist2 > 3025.0  # ~55uu
        except Exception:
            # Location read failed — usually destroyed mid-grab. Do not restore.
            _drop_dead_pin(row)
            continue
        settled = bool(_landing_settle_done) and not _mid_shape_dump()
        # Settled: drift / upward Attract = player grab. Hand off as world loot.
        # (Leaving pins frozen forever made guns float mid-air instead of picking up.
        # Float-on-grab gag is unrelated — that option lifts OTHER nearby guns.)
        if settled:
            dz_up = 0.0
            if loc is not None:
                try:
                    dz_up = float(loc.Z) - float(row["z"])
                except Exception:
                    dz_up = 0.0
            grabbing = bool(drifted) or dist2 > 1600.0 or dz_up > 28.0
            if grabbing:
                # Co-op held silhouette: never drift-unlock (drops shape / floor orphans).
                # Collect is ServerUse → backpack. Solo / host soft-unlock still OK.
                if _want_coop_replicate() and row.get("hold"):
                    live.append(row)
                    continue
                try:
                    if _live(inv):
                        _release_pin_for_pickup(inv, row)
                    else:
                        _drop_dead_pin(row)
                except Exception:
                    _drop_dead_pin(row)
                continue
            live.append(row)
            continue
        if not drifted:
            live.append(row)
            continue
        try:
            # Keep QueryAndPhysics so lobby guests can actually grab shaped guns.
            if not _live(inv):
                _drop_dead_pin(row)
                continue
            _set_physics(inv, False, keep_grab_collision=True)
        except Exception:
            pass
        try:
            if not _live(inv):
                _drop_dead_pin(row)
                continue
            _teleport_pickup(
                inv,
                float(row["x"]),
                float(row["y"]),
                float(row["z"]),
                float(row.get("yaw") or 0.0),
                pitch=float(row.get("pitch") or 0.0),
                roll=float(row.get("roll") or 0.0),
                freeze=True,
                replicate=False,
                guest_push=False,
                keep_grab_collision=True,
            )
            _set_physics(inv, False, keep_grab_collision=True)
            _zero_velocity(inv)
        except Exception:
            live.append(row)
            continue
        live.append(row)
    _pinned_slots = live


def _sample_flight_xyz(job: dict[str, Any], t: float) -> tuple[float, float, float]:
    """t is 0..1 already eased. Each mode must read as a different path."""
    x0, y0, z0 = float(job["x0"]), float(job["y0"]), float(job["z0"])
    x1, y1, z1 = float(job["x1"]), float(job["y1"]), float(job["z1"])
    mode_n = str(job.get("mode") or "")
    if mode_n == "rain":
        fall = t * t
        wobble = (1.0 - t) * 18.0
        x = x0 + (x1 - x0) * t + math.sin(t * 11.0 + x0) * wobble
        y = y0 + (y1 - y0) * t + math.cos(t * 8.0 + y0) * wobble
        z = z0 + (z1 - z0) * fall
        x, y = _clamp_xy_to_shape(x, y, pad=20.0)
        return x, y, z
    if mode_n == "fountain":
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        z = z0 + (z1 - z0) * t + math.sin(t * math.pi) * 340.0
        x, y = _clamp_xy_to_shape(x, y, pad=20.0)
        return x, y, z
    if mode_n == "explode":
        # Bigger ease-out pulse from the condensed ball onto the 3D sphere.
        u = 1.0 - (1.0 - t) ** 3
        x = x0 + (x1 - x0) * u
        y = y0 + (y1 - y0) * u
        z = z0 + (z1 - z0) * u + math.sin(t * math.pi) * 220.0
        return x, y, z
    if mode_n == "spiral":
        idx = int(job.get("index") or 0)
        spin = (1.0 - t) * math.pi * 6.0 + idx * 0.47
        rad = (1.0 - t) * 70.0
        x = x1 + math.cos(spin) * rad
        y = y1 + math.sin(spin) * rad
        z = z0 + (z1 - z0) * t
        x, y = _clamp_xy_to_shape(x, y, pad=20.0)
        return x, y, z
    x = x0 + (x1 - x0) * t
    y = y0 + (y1 - y0) * t
    z = z0 + (z1 - z0) * t
    x, y = _clamp_xy_to_shape(x, y, pad=20.0)
    return x, y, z


def _queue_drop_job(
    inv: Any,
    slot: tuple[float, float, float],
    *,
    index: int = 0,
) -> bool:
    cfg = DROP_MODES.get(_drop_mode) or DROP_MODES["slow"]
    # Nova dump phase: pack into the condensed ball; pulse fires after settle.
    if _is_nova_shape() and _land_active and not _landing_settle_done:
        condensed = _nova_condensed_world(index)
        ok = _pin_pickup_to_slot(inv, condensed, index=index, hold=True)
        if ok and not _catch_paused:
            _arm_peel_clock()
        return ok
    x1, y1, z1 = slot
    x0, y0, z0 = _start_xyz_for_slot(slot, index)
    dur = float(cfg.get("dur") or 0.0)
    stagger = float(cfg.get("stagger") or 0.0)
    # GitHub 3.8.133: never ForceNetUpdate on the dump pin (lobby restamp spat at host).
    replicate = False
    yaw_r, pitch, roll = _rot_for_xyz(index, x1, y1, z1)
    hold_shape = _shape_hold_active()
    if hold_shape and _instant_land_mode():
        ok = _pin_pickup_to_slot(inv, slot, index=index, hold=True)
        if ok and not _catch_paused:
            _arm_peel_clock()
        return ok
    if str(_drop_shape) in SHAPE_2D_NAMES and _instant_land_mode() and not _is_nova_shape():
        ok = _teleport_pickup(
            inv,
            x1,
            y1,
            z1,
            yaw_r,
            pitch=pitch,
            roll=roll,
            freeze=True,
            replicate=replicate,
            keep_grab_collision=True,
        )
        if ok:
            _remember_pin(
                inv, x1, y1, z1, yaw_r, pitch=pitch, roll=roll, hold=bool(_land_active), slot_index=index
            )
        return ok
    style = str(cfg.get("style") or "straight")
    if style == "drip" and not _is_peel_drop():
        # Stay in air + drip = freeze on silhouette (no peel-to-ground animation).
        return _pin_pickup_to_slot(inv, slot, index=index, hold=True)
    if _is_peel_drop():
        ox, oy, oz = _drop_origin
        if z1 > oz + 40.0:
            x0, y0, z0 = x1, y1, z1
            z1 = oz
        stagger = max(stagger, 0.12)
    if _drop_mode == "none" or (
        float(cfg.get("height_mul") or 0.0) <= 0.0 and style not in ("drip",)
    ):
        ok = _teleport_pickup(
            inv,
            x1,
            y1,
            z1,
            yaw_r,
            pitch=pitch,
            roll=roll,
            freeze=True,
            replicate=replicate,
            keep_grab_collision=True,
        )
        if ok:
            _remember_pin(inv, x1, y1, z1, yaw_r, pitch=pitch, roll=roll, slot_index=index)
        return ok
    # snap dur is 0 in the table (fall from height) — still script onto the slot
    # so gravity cannot bounce them out of the heart / square.
    if dur <= 0.0:
        dur = 0.55
    addr = _remember_inv(inv)
    if not addr:
        return False
    ok = _teleport_pickup(
        inv,
        x0,
        y0,
        z0,
        yaw_r,
        pitch=pitch,
        roll=roll,
        freeze=True,
        replicate=replicate,
        keep_grab_collision=True,
    )
    if not ok:
        return False
    try:
        _set_physics(inv, False, keep_grab_collision=True)
        _zero_velocity(inv)
    except Exception:
        pass
    now = time.monotonic()
    # Global item index made rain/fountain/stagger wait tens of seconds in a
    # large Spawn All. Keep the visible cascade, bounded to one short wave.
    wave = 24 if (_drop_mode == "drip" or _is_peel_drop()) else (6 if _drop_mode == "stagger" else 10)
    stagger_slot = max(0, int(index)) % wave
    pin_hold = hold_shape
    if not pin_hold and _should_hold_in_air():
        shape_n = _normalize_shape_name(_drop_shape or _land_user_shape or "")
        if shape_n in SHAPE_3D_NAMES:
            pin_hold = True
    _float_jobs.append(
        {
            "addr": addr,
            "x0": x0,
            "y0": y0,
            "z0": z0,
            "x1": x1,
            "y1": y1,
            "z1": z1,
            "t0": now + stagger * stagger_slot,
            "dur": max(0.35, dur),
            "yaw": yaw_r,
            "pitch": pitch,
            "roll": roll,
            "mode": _drop_mode,
            "index": int(index),
            "hold": pin_hold,
        }
    )
    arm_overhead_catch(max(8.0, dur + stagger * stagger_slot + 2.0))
    return True


def _tick_delayed_peel(now: float) -> None:
    """After Drop after (sec), peel the held 3D silhouette down to the ground."""
    global _peel_started, _stay_in_air, _float_jobs, _pinned_slots, _peel_queue
    if _peel_after_sec <= 0.0:
        return
    if not _peel_started:
        # Stay in air until Spawn All finishes. Peel-after used to fire a few
        # seconds in, drop the silhouette, and despawn stacked guns.
        if _bulk_healthcheck_mode:
            return
        if _catch_paused:
            return
        if _peel_armed_at <= 0.0:
            if _pinned_slots:
                _arm_peel_clock()
            return
        if now < _peel_armed_at:
            return
        if not _pinned_slots:
            return
        _peel_started = True
        _stay_in_air = False
        ox, oy, oz = _drop_origin
        pending: list[dict[str, Any]] = []
        for row in _pinned_slots:
            addr = int(row.get("addr") or 0)
            if not addr:
                continue
            z = float(row.get("z") or 0.0)
            if z <= oz + 8.0:
                continue
            pending.append(
                {
                    "addr": addr,
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "z": z,
                    "yaw": float(row.get("yaw") or _drop_yaw),
                    "pitch": float(row.get("pitch") or 0.0),
                    "roll": float(row.get("roll") or 0.0),
                }
            )
        _pinned_slots = []
        _peel_queue = pending
        _log(f"Peel start: {len(pending)} item(s) after {_peel_after_sec:.0f}s.")
    if not _peel_queue:
        return
    ox, oy, oz = _drop_origin
    # Spawn All can pin hundreds of items. Starting every drip in one tick AVs.
    room = max(0, 24 - len(_float_jobs))
    take = min(6, room, len(_peel_queue))
    if take <= 0:
        return
    _refresh_live_pickups()
    batch = _peel_queue[:take]
    _peel_queue = _peel_queue[take:]
    started = 0
    retry: list[dict[str, Any]] = []
    for row in batch:
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr)
        if not addr or inv is None:
            misses = int(row.get("misses") or 0) + 1
            if misses < 10:
                row["misses"] = misses
                retry.append(row)
            continue
        x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
        _float_jobs.append(
            {
                "addr": addr,
                "x0": x,
                "y0": y,
                "z0": z,
                "x1": x,
                "y1": y,
                "z1": oz,
                "t0": now + 0.10 * started,
                "dur": 2.8,
                "yaw": float(row.get("yaw") or _drop_yaw),
                "pitch": float(row.get("pitch") or 0.0),
                "roll": float(row.get("roll") or 0.0),
                "mode": "drip",
                "index": started,
            }
        )
        started += 1
    if retry:
        _peel_queue.extend(retry)
    if started:
        arm_overhead_catch(8.0)


def _tick_nova_explode(now: float) -> None:
    """After dump settle: pulse condensed-ball pins out to the 3D sphere slots."""
    global _nova_explode_started, _nova_explode_queue, _pinned_slots, _stay_in_air, _float_jobs
    global _nova_explode_armed_at
    if not _is_nova_shape():
        return
    if _nova_explode_armed_at <= 0.0 and not _nova_explode_started and not _nova_explode_queue:
        return
    if not _nova_explode_started:
        # Once armed, never wait on bulk/catch pause — that left the ball hanging forever.
        if _nova_explode_armed_at > 0.0 and now < _nova_explode_armed_at:
            return
        if not _pinned_slots:
            # Settle armed with no pins yet (late catch). Keep waiting briefly, then give up.
            if _nova_explode_armed_at > 0.0 and now < _nova_explode_armed_at + 4.0:
                return
            _reset_nova_explode()
            _log("Nova pulse cancelled — no pinned ball items.")
            return
        _nova_explode_started = True
        _nova_explode_armed_at = 0.0
        final_hold = bool(_should_hold_in_air())
        ox, oy, oz = _drop_origin
        pending: list[dict[str, Any]] = []
        for row in _pinned_slots:
            addr = int(row.get("addr") or 0)
            if not addr:
                continue
            idx = int(row.get("slot_index") if row.get("slot_index") is not None else row.get("index") or 0)
            if _drop_plan and 0 <= idx < len(_drop_plan):
                x1, y1, z1 = _drop_plan[idx]
            else:
                cx, cy, cz = _nova_ball_center()
                ang = (2.0 * math.pi * idx) / max(1, len(_pinned_slots))
                rad = 280.0
                x1 = cx + math.cos(ang) * rad
                y1 = cy + math.sin(ang) * rad
                z1 = cz + 40.0 + (idx % 7) * 22.0
            # Stay in air off → pulse ends on the ground under the sphere slot.
            if not final_hold:
                z1 = float(oz)
            pending.append(
                {
                    "addr": addr,
                    "x0": float(row["x"]),
                    "y0": float(row["y"]),
                    "z0": float(row["z"]),
                    "x1": float(x1),
                    "y1": float(y1),
                    "z1": float(z1),
                    "yaw": float(row.get("yaw") or _drop_yaw),
                    "pitch": float(row.get("pitch") or 0.0),
                    "roll": float(row.get("roll") or 0.0),
                    "index": idx,
                    "hold": final_hold,
                }
            )
        _pinned_slots = []
        _nova_explode_queue = pending
        _log(
            f"Nova pulse: {len(pending)} item(s) bursting from the ball"
            f"{' (stay in air)' if final_hold else ' → ground'}."
        )
    if not _nova_explode_queue:
        return
    coop = False
    try:
        coop = bool(_want_coop_replicate())
    except Exception:
        coop = False
    # Co-op: tiny batches — 10 teleports + find_all per tick lagged guests out of the lobby.
    room = max(0, (12 if coop else 28) - len(_float_jobs))
    take = min(3 if coop else 8, room, len(_nova_explode_queue))
    if take <= 0:
        return
    # Only refresh when the addr map looks empty — never every pulse tick.
    if not _pickup_by_addr or len(_pickup_by_addr) < max(8, take):
        try:
            _refresh_live_pickups()
        except Exception:
            pass
    batch = _nova_explode_queue[:take]
    _nova_explode_queue = _nova_explode_queue[take:]
    started = 0
    retry: list[dict[str, Any]] = []
    final_hold = _should_hold_in_air()
    for row in batch:
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr)
        if not addr or inv is None:
            misses = int(row.get("misses") or 0) + 1
            if misses < 10:
                row["misses"] = misses
                retry.append(row)
            continue
        hold = bool(row.get("hold")) if "hold" in row else final_hold
        _float_jobs.append(
            {
                "addr": addr,
                "x0": float(row["x0"]),
                "y0": float(row["y0"]),
                "z0": float(row["z0"]),
                "x1": float(row["x1"]),
                "y1": float(row["y1"]),
                "z1": float(row["z1"]),
                "t0": now + 0.04 * started,
                "dur": 1.35 if coop else 1.25,
                "yaw": float(row.get("yaw") or _drop_yaw),
                "pitch": float(row.get("pitch") or 0.0),
                "roll": float(row.get("roll") or 0.0),
                "mode": "explode",
                "index": int(row.get("index") or started),
                "hold": hold,
            }
        )
        started += 1
    if retry:
        _nova_explode_queue.extend(retry)
    if started:
        arm_overhead_catch(8.0)


def enqueue_placed_drops(
    placed: list[tuple[Any, float, float, float]],
    *,
    mode: str = "slow",
    drop_height: float = _DEFAULT_DROP_HEIGHT,
    yaw: float | None = None,
) -> int:
    """Animate existing pickups from overhead into already-computed world slots."""
    global _drop_mode, _DROP_HEIGHT, _drop_yaw, _drop_origin, _float_jobs, _drop_until, _land_slot_pools
    mode_l = normalize_drop_mode(mode)
    _drop_mode = mode_l
    _drop_until = 0.0
    _DROP_HEIGHT = float(clamp_layout_params(drop_height=drop_height)["drop_height"])
    anchor = _player_anchor()
    if yaw is None and anchor is not None:
        _drop_yaw = float(anchor[4])
        _drop_origin = (anchor[1], anchor[2], anchor[3])
    elif yaw is not None:
        _drop_yaw = float(yaw)
        if anchor is not None:
            _drop_origin = (anchor[1], anchor[2], anchor[3])
    _float_jobs = []
    _clear_pins()
    _land_slot_pools = {}
    n = 0
    for i, (inv, x, y, z) in enumerate(placed):
        _queue_drop_job(inv, (x, y, z), index=i)
        n += 1
    return n


def _arm_coop_vis_burst(addrs: list[int]) -> None:
    """Sparse ForceNet so guests see the arranged pose — never re-freeze / pin."""
    global _coop_vis_addrs, _coop_vis_cursor, _coop_vis_until, _coop_vis_ok
    _coop_vis_addrs = [int(a) for a in addrs if int(a or 0)]
    _coop_vis_cursor = 0
    _coop_vis_ok = set()
    # 120 slots @ ~4 ForceNet/tick needs headroom past the old 6s cut-off.
    _coop_vis_until = time.monotonic() + 25.0
    _log(f"Co-op shape visibility publish queued ({len(_coop_vis_addrs)} pickable slot(s)).")


def _tick_coop_vis_burst(now: float) -> None:
    global _coop_vis_addrs, _coop_vis_cursor, _coop_vis_until, _coop_vis_ok
    if not _coop_vis_addrs:
        return
    if _progression_network_busy() or _in_join_quiet(now):
        return
    n = len(_coop_vis_addrs)
    budget = 6
    walked = 0
    while walked < n and budget > 0:
        idx = _coop_vis_cursor % n
        _coop_vis_cursor = idx + 1
        walked += 1
        addr = int(_coop_vis_addrs[idx] or 0)
        if not addr or addr in _coop_vis_ok:
            continue
        inv = _live_pickup(addr)
        if inv is None or not _live(inv):
            _coop_vis_ok.add(addr)
            continue
        try:
            inv.bOnlyRelevantToOwner = False
            inv.bNetUseOwnerRelevancy = False
            inv.bAlwaysRelevant = True
            inv.bReplicates = True
            inv.bReplicateMovement = True
            inv.NetUpdateFrequency = 40.0
            try:
                inv.RemoteRole = 1
            except Exception:
                pass
            dorm = getattr(inv, "SetNetDormancy", None)
            if callable(dorm):
                dorm(3)
        except Exception:
            pass
        # Re-stamp dump usable each publish so guests get pickable + posed actors.
        try:
            _apply_dump_usable_state(inv, gravity=False)
        except Exception:
            pass
        if _force_net_update(inv, coop_pin=True, guest_push=True):
            _coop_vis_ok.add(addr)
            budget -= 1
    done = len(_coop_vis_ok)
    if done >= n or now > _coop_vis_until:
        _log(
            f"Co-op shape ready: {done}/{n} visible + pickable"
            + (" (timeout)" if done < n else "")
            + "."
        )
        _coop_vis_addrs = []
        _coop_vis_ok = set()
        _coop_vis_cursor = 0
        _coop_vis_until = 0.0


def _arm_coop_guest_sync_after_place(*, pin_count: int = 0) -> None:
    """Publish through normal replication, then permit client-local pickup Attract."""
    if not _want_coop_replicate() or not _pinned_slots:
        return
    try:
        _build_layout_entries_from_pins()
    except Exception:
        pass
    _arm_coop_pickup_safe(delay=0.15)
    _log(f"Co-op shape ready ({int(pin_count or len(_pinned_slots))} pickup-safe slots).")


def apply_settle(
    placed: list[tuple[Any, float, float, float]],
    *,
    mode: str = "none",
    drop_height: float = _DEFAULT_DROP_HEIGHT,
    yaw: float | None = None,
) -> int:
    """none = instant on slots. snap = fall from drop height onto slots. others = group drop."""
    global _landing_settle_done, _pinned_slots, _pickup_by_addr
    mode_l = normalize_drop_mode(mode)
    if mode_l == "none":
        coop = False
        try:
            coop = bool(_want_coop_replicate())
        except Exception:
            coop = False
        # Mass ForceNetUpdate on Place Fully house (~250+) is the co-op AV in CrashContext.
        mass = len(placed) > 40
        # Co-op: always freeze+pin so guests see the silhouette. Collect is
        # ServerUse → backpack (native Attract on freeze never worked for lobby).
        replicate_now = not (coop or mass)
        n = 0
        for i, (inv, x, y, z) in enumerate(placed):
            yaw_r, pitch, roll = _rot_for_xyz(i, x, y, z)
            if _teleport_pickup(
                inv,
                x,
                y,
                z,
                yaw_r,
                pitch=pitch,
                roll=roll,
                freeze=True,
                replicate=replicate_now,
                guest_push=False,
                keep_grab_collision=True,
            ):
                _set_physics(inv, False, keep_grab_collision=True)
                _zero_velocity(inv)
                _remember_pin(
                    inv,
                    x,
                    y,
                    z,
                    yaw_r,
                    pitch=pitch,
                    roll=roll,
                    hold=True,
                    slot_index=i,
                )
                n += 1
        if coop and n:
            _arm_coop_guest_sync_after_place(pin_count=n)
        return n
    return enqueue_placed_drops(placed, mode=mode_l, drop_height=drop_height, yaw=yaw)


def _job_inv_live(job: dict[str, Any]) -> Any | None:
    """Never reuse a stored wrapper — stale dump actors AV after peel/travel."""
    return _live_pickup(int(job.get("addr") or 0))


def _push_coop_flight_guest(
    job: dict[str, Any],
    inv: Any,
    x: float,
    y: float,
    z: float,
    *,
    yaw: float,
    pitch: float,
    roll: float,
    budget: list[int],
) -> bool:
    """Net one in-flight settle pose to lobby guests (does not mark guest_ok — slot pin does)."""
    if budget[0] <= 0:
        return False
    if not (_want_coop_replicate() and _shape_hold_active()):
        return False
    addr = int(job.get("addr") or 0)
    if not addr:
        return False
    fly_row = {
        "x": x,
        "y": y,
        "z": z,
        "yaw": yaw,
        "pitch": pitch,
        "roll": roll,
        "hold": True,
        "addr": addr,
    }
    try:
        if _push_pin_to_guests(fly_row, inv, allow_during_dump=True):
            budget[0] -= 1
            return True
    except Exception:
        pass
    return False


def _tick_float_jobs(now: float) -> None:
    global _float_jobs
    if not _float_jobs:
        return
    remaining: list[dict[str, Any]] = []
    moved = 0
    n_jobs = len(_float_jobs)
    # Large dumps need a fat budget or flights stall mid-air at dump height.
    budget = min(n_jobs, 64 if n_jobs > 80 else (40 if n_jobs > 24 else (20 if n_jobs > 10 else 10)))
    # Sparse mid-air guest samples so lobby sees rain/slow/medium — not shoot-high-then-snap.
    # Mid-dump ForceNet samples hitch the host on large ULM grids — wait until settle.
    # Nova explode ForceNet was lagging guests out of the lobby — host-local only during pulse.
    # Natural actor replication is enough for co-op animation. Explicit
    # ForceNet samples were the host hitch / lobby disconnect path.
    coop_fly_shape = False
    if coop_fly_shape:
        # Lobby needs denser rain/slow samples or guests only see high spawn → snap.
        if n_jobs > 180:
            guest_fly_budget = [2]
        elif n_jobs > 80:
            guest_fly_budget = [3]
        else:
            guest_fly_budget = [5]
    else:
        guest_fly_budget = [0]
    # Host hitch: smaller teleport budget while pulsing / large co-op shapes.
    if _nova_explode_started or _nova_explode_queue:
        budget = min(budget, 8 if _want_coop_replicate() else 16)
    elif _want_coop_replicate() and n_jobs > 80:
        budget = min(budget, 20)
    for job in _float_jobs:
        inv = _job_inv_live(job)
        dur = max(0.35, float(job.get("dur") or 1.0))
        t0 = float(job.get("t0") or now)
        yaw = float(job.get("yaw") or 0.0)
        pitch = float(job.get("pitch") or 0.0)
        roll = float(job.get("roll") or 0.0)
        x1, y1, z1 = float(job["x1"]), float(job["y1"]), float(job["z1"])
        addr = int(job.get("addr") or 0)
        if inv is None:
            # Give a transient wrapper one short recovery window, then discard
            # it instead of retaining a stale UObject indefinitely.
            if now <= t0 + dur + 2.0:
                remaining.append(job)
            continue
        if now < t0:
            remaining.append(job)
            continue
        u = min(1.0, (now - t0) / dur)
        t = u * u * (3.0 - 2.0 * u)
        if u < 1.0:
            x, y, z = _sample_flight_xyz(job, t)
            # Always snap to the scripted path — skipping frames caused visible judder.
            if moved < budget:
                if _teleport_pickup(inv, x, y, z, yaw, pitch=pitch, roll=roll, replicate=False):
                    try:
                        _set_physics(inv, False, keep_grab_collision=True)
                        _zero_velocity(inv)
                    except Exception:
                        pass
                    moved += 1
            elif (now - float(job.get("last_move") or 0.0)) >= 0.08:
                if _teleport_pickup(inv, x, y, z, yaw, pitch=pitch, roll=roll, replicate=False):
                    job["last_move"] = now
            if coop_fly_shape and guest_fly_budget[0] > 0:
                mode_n = str(job.get("mode") or "")
                if mode_n in ("rain", "fountain", "spiral", "stagger", "slow", "medium", "fast"):
                    mid_gap = 0.22 if n_jobs > 120 else 0.14
                else:
                    mid_gap = 0.40 if n_jobs > 120 else 0.22
                if not job.get("guest_start") and u > 0.02:
                    x0 = float(job.get("x0") or x)
                    y0 = float(job.get("y0") or y)
                    z0 = float(job.get("z0") or z)
                    if _push_coop_flight_guest(
                        job, inv, x0, y0, z0, yaw=yaw, pitch=pitch, roll=roll, budget=guest_fly_budget
                    ):
                        job["guest_start"] = True
                if u >= 0.48 and not job.get("guest_mid"):
                    if _push_coop_flight_guest(
                        job, inv, x, y, z, yaw=yaw, pitch=pitch, roll=roll, budget=guest_fly_budget
                    ):
                        job["guest_mid"] = True
                elif (now - float(job.get("guest_net") or 0.0)) >= mid_gap:
                    if _push_coop_flight_guest(
                        job, inv, x, y, z, yaw=yaw, pitch=pitch, roll=roll, budget=guest_fly_budget
                    ):
                        job["guest_net"] = now
            remaining.append(job)
            continue
        if moved < budget:
            if _teleport_pickup(inv, x1, y1, z1, yaw, pitch=pitch, roll=roll, freeze=True, replicate=False):
                mode_n = str(job.get("mode") or "")
                peel_land = mode_n == "drip" and _is_peel_drop()
                if not peel_land:
                    if mode_n == "explode":
                        # Nova pulse: honor the job's stay-in-air flag only (no mid-flight flip).
                        hold = bool(job.get("hold"))
                    else:
                        hold = bool(job.get("hold")) or _shape_hold_active()
                        if _should_hold_in_air():
                            shape_n = _normalize_shape_name(_drop_shape or _land_user_shape or "")
                            if shape_n in SHAPE_3D_NAMES:
                                hold = True
                    slot_idx = job.get("index")
                    slot_i = int(slot_idx) if slot_idx is not None else None
                    if hold:
                        _pin_pickup_to_slot(inv, (x1, y1, z1), index=slot_i or 0, hold=True)
                        if coop_fly_shape and addr and guest_fly_budget[0] > 0:
                            for row in _pinned_slots:
                                if int(row.get("addr") or 0) == addr:
                                    try:
                                        if _push_pin_to_guests(
                                            row, inv, allow_during_dump=True
                                        ):
                                            row["guest_ok"] = True
                                            row.pop("guest_fail", None)
                                            guest_fly_budget[0] -= 1
                                    except Exception:
                                        pass
                                    break
                    elif mode_n == "explode":
                        # Ground pulse end — freeze with grab, never SimulatePhysics
                        # (live dump: bRepPhysics + simulate launches guns upward).
                        try:
                            _set_physics(inv, False, keep_grab_collision=True)
                            _zero_velocity(inv)
                        except Exception:
                            pass
                        _remember_pin(
                            inv,
                            x1,
                            y1,
                            z1,
                            yaw,
                            pitch=pitch,
                            roll=roll,
                            hold=False,
                            slot_index=slot_i,
                        )
                    else:
                        _remember_pin(
                            inv,
                            x1,
                            y1,
                            z1,
                            yaw,
                            pitch=pitch,
                            roll=roll,
                            hold=False,
                            slot_index=slot_i,
                        )
                moved += 1
                continue
        remaining.append(job)
    _float_jobs = remaining
    if not remaining and _want_coop_replicate() and _pinned_slots:
        _arm_coop_pickup_safe(delay=0.15)


def finish_drop_jobs() -> str:
    """Cancel remaining animation without touching potentially stale wrappers."""
    global _float_jobs, _drop_until, _status
    n = len(_float_jobs)
    _float_jobs = []
    _drop_until = 0.0
    _status = f"Stopped drop motion for {n} item(s)."
    _log(_status)
    return _status


def get_last_layout_summary() -> str:
    entries = _last_layout.get("entries") or []
    jobs = len(_float_jobs)
    return (
        f"shape={_last_layout.get('shape')} mode={_last_layout.get('mode')} "
        f"settle={_last_layout.get('settle') or 'none'} tracked={len(entries)} "
        f"party={_last_layout.get('party_count')} dropping={jobs}"
    )


# --- party join polling -------------------------------------------------------

def _party_count() -> int:
    try:
        from .inventory_capacity import get_party_player_states

        return len(get_party_player_states())
    except Exception:
        try:
            from Squ1ggsBoostingTools.inventory_capacity import get_party_player_states  # type: ignore

            return len(get_party_player_states())
        except Exception:
            return 0


def _tick_deferred_dump_catch(now: float) -> None:
    """Occasional leftover catch only. The per-dump/tick restamp path froze the game."""
    global _deferred_catch_at, _deferred_catch_until, _deferred_catch_empty
    # Mid Spawn-All / shaped dump: after_dump_spawn already catches. A second
    # find_all every ~0.35s is what lagged hard after ~10 world pickups.
    if _bulk_healthcheck_mode and not _landing_settle_done:
        return
    # Hold silhouettes: after_dump_spawn pins each spawn — deferred find_all doubles hitch.
    if _land_active and not _landing_settle_done and _shape_hold_active():
        return
    bulk_shaped = bool(_bulk_healthcheck_mode and _land_active and _shape_hold_active())
    if _bulk_healthcheck_mode and not bulk_shaped:
        return
    if not (
        _land_active
        and not _defer_shape
        and _deferred_catch_until > 0.0
        and now >= _deferred_catch_at
        and now <= _deferred_catch_until
    ):
        return
    # While drip-syncing a big co-op silhouette, do not keep find_all-catching
    # more pins onto it (grew house 294→407 and AVd during ForceNetUpdate).
    if _guest_sync_active and held_pin_count() > 80:
        _deferred_catch_at = now + 1.2
        return
    if not _landing_settle_done and not (_land_active and _shape_hold_active()):
        return
    slots_left = max(0, len(_drop_plan) - int(_drop_next)) if _drop_plan else 0
    try:
        if bulk_shaped:
            batch = 2
        elif _guest_sync_active:
            batch = 1
        elif slots_left > 40:
            batch = 10
        elif slots_left > 12:
            batch = 8
        elif _land_active and not _landing_settle_done:
            batch = 4
        elif _shape_hold_active():
            batch = 6
        else:
            batch = 2
        # Cache-first — forced fresh here stacked with after_dump find_all.
        caught = pull_new_pickups_into_shape(limit=batch, fresh=False)
    except Exception:
        caught = 0
    if caught:
        _deferred_catch_empty = 0
        if slots_left > 0:
            _deferred_catch_until = max(_deferred_catch_until, now + 12.0)
    else:
        _deferred_catch_empty += 1
    if bulk_shaped:
        _deferred_catch_at = now + 0.9
        empty_limit = 24
    else:
        _deferred_catch_at = now + (0.12 if slots_left > 20 else (0.15 if _shape_hold_active() else 0.25))
        empty_limit = 48 if (_land_active and slots_left > 0) else 8
    if _deferred_catch_empty >= empty_limit:
        _deferred_catch_until = 0.0


def tick_drop_motion(now: float | None = None) -> None:
    """Fly rain/fountain/spiral/etc into shape slots. No find_all — HUD-tick safe."""
    global _float_tick_at, _pickup_by_addr
    try:
        from .session_guards import session_safe

        if not session_safe():
            abandon_world_loot(schedule_orphan_absorb=False)
            return
    except Exception:
        pass
    if not _world_alive():
        abandon_world_loot(schedule_orphan_absorb=False)
        return
    if _player_left_drop_site():
        abandon_world_loot()
        return
    now = time.monotonic() if now is None else float(now)
    try:
        _absorb_orphan_pickups_if_due(now)
    except Exception:
        pass
    try:
        _poll_party_join(now)
    except Exception:
        pass
    try:
        _tick_join_hold_freeze(now)
    except Exception:
        pass
    try:
        _tick_join_refresh(now)
    except Exception:
        pass
    try:
        _tick_join_reapply(now)
    except Exception:
        pass
    try:
        _tick_join_serial_reapply(now)
    except Exception:
        pass
    try:
        _tick_deferred_dump_catch(now)
    except Exception:
        pass
    min_gap = 0.10 if _float_jobs else (0.22 if _land_active else 0.16)
    if now - _float_tick_at < min_gap:
        return
    _float_tick_at = now
    waiting_peel = _peel_after_sec > 0.0 and not _peel_started and _land_active
    waiting_nova = (
        _is_nova_shape()
        and (
            (_nova_explode_armed_at > 0.0 and not _nova_explode_started)
            or bool(_nova_explode_queue)
        )
    )
    if not (
        _float_jobs
        or _pinned_slots
        or _peel_queue
        or waiting_peel
        or waiting_nova
        or (_land_active and _deferred_catch_until > 0.0)
        or _coop_vis_addrs
    ):
        return
    try:
        _tick_delayed_peel(now)
    except Exception:
        pass
    try:
        _tick_nova_explode(now)
    except Exception:
        pass
    try:
        _tick_float_jobs(now)
    except Exception:
        pass
    try:
        _tick_float_on_grab(now)
    except Exception:
        pass
    try:
        _tick_coop_pickup_safe(now)
    except Exception:
        pass
    try:
        _tick_coop_vis_burst(now)
    except Exception:
        pass
    try:
        _tick_guest_sync(now)
    except Exception:
        pass
    try:
        _tick_coop_followup_sync(now)
    except Exception:
        pass
    try:
        _tick_pins()
    except Exception:
        pass
    if _peel_started and not _peel_queue and not _float_jobs:
        abandon_world_loot()
        return
    if (
        _landing_settle_done
        and not _float_jobs
        and not _pinned_slots
        and not _peel_queue
        and not (_peel_after_sec > 0.0 and not _peel_started)
        and _pickup_by_addr
    ):
        _pickup_by_addr = {}


def tick_loot_shapes(now: float | None = None) -> None:
    """Call from a game tick. Re-applies layout shortly after party size grows."""
    global _join_reapply_pending, _join_reapply_at, _tick_last, _tick_busy, _party_poll_at
    global _deferred_catch_at, _deferred_catch_until, _deferred_catch_empty
    global _burst_replicate_at, _guest_sync_cursor, _guest_sync_active, _guest_sync_last
    global _coop_followup_sync_at, _coop_followup_waves
    if not _world_alive():
        if _land_active or _pinned_slots or _float_jobs:
            try:
                abandon_world_loot(schedule_orphan_absorb=False)
            except Exception:
                pass
        return
    now = time.monotonic() if now is None else float(now)
    try:
        _poll_party_join(now)
    except Exception:
        pass
    tick_drop_motion(now)
    try:
        # Vis burst must run even when pins are empty (GLH-style place).
        _tick_coop_vis_burst(now)
    except Exception:
        pass
    try:
        _tick_coop_hold_sync(now)
    except Exception:
        pass
    try:
        _tick_coop_followup_sync(now)
    except Exception:
        pass
    try:
        from .embedded_oak.engine import logo_tick

        logo_tick()
    except Exception:
        pass
    if _tick_busy:
        return
    if now - _tick_last < 0.2:
        return
    _tick_last = now
    _tick_busy = True
    try:
        try:
            if not (_land_active and not _landing_settle_done):
                from . import map_fog_hide

                map_fog_hide.tick_fog_hide(now)
        except Exception:
            pass
        # Deferred dump catch runs from tick_drop_motion (HUD tick, even while
        # catch is paused). Nothing to do here unless motion is idle.
        if _deferred_catch_until > 0.0 and not (_float_jobs or _pinned_slots):
            _tick_deferred_dump_catch(now)
        if not _progression_network_busy() and _join_reapply_can_run(now):
            _join_reapply_pending = False
            if _pinned_slots:
                _run_join_guest_shape_push()
    finally:
        _tick_busy = False


def _pinned_row_for_hook_value(value: Any) -> tuple[dict[str, Any], Any] | None:
    """Resolve a ServerUseObject parameter (actor/component/struct) to one pin."""
    if value is None or not _pinned_slots:
        return None
    by_addr = {
        int(row.get("addr") or 0): row
        for row in _pinned_slots
        if int(row.get("addr") or 0)
    }
    seen: set[int] = set()
    queue: list[Any] = [value]
    while queue and len(seen) < 24:
        candidate = queue.pop(0)
        if candidate is None:
            continue
        marker = id(candidate)
        if marker in seen:
            continue
        seen.add(marker)
        try:
            addr = int(_uobject_addr(candidate) or 0)
        except Exception:
            addr = 0
        row = by_addr.get(addr)
        if row is not None:
            inv = _live_pickup(addr)
            if inv is None:
                inv = candidate
            return row, inv
        # The RPC may pass a primitive/use component. Walk outward to its actor.
        outer = candidate
        for _ in range(4):
            try:
                outer = getattr(outer, "Outer", None)
            except Exception:
                outer = None
            if outer is None:
                break
            try:
                outer_addr = int(_uobject_addr(outer) or 0)
            except Exception:
                outer_addr = 0
            row = by_addr.get(outer_addr)
            if row is not None:
                inv = _live_pickup(outer_addr)
                if inv is None:
                    inv = outer
                return row, inv
        # Native use RPCs sometimes wrap the target in a small interaction struct.
        for attr in (
            "Object",
            "UseObject",
            "UsableObject",
            "TargetObject",
            "Target",
            "Actor",
            "Interactable",
            "Usable",
            "Component",
        ):
            try:
                inner = getattr(candidate, attr, None)
            except Exception:
                inner = None
            if inner is not None and inner is not candidate:
                queue.append(inner)
        if isinstance(candidate, (tuple, list)):
            queue.extend(list(candidate)[:8])
    return None


def _looks_like_inventory_pickup_actor(value: Any) -> bool:
    if value is None:
        return False
    try:
        cls_name = str(getattr(getattr(value, "Class", None), "Name", "") or "")
    except Exception:
        return False
    return "InventoryPickup" in cls_name or cls_name.endswith("Pickup")


def _server_use_pin_target(
    controller: Any,
    args: Any,
    func: Any,
) -> tuple[dict[str, Any], Any] | None:
    """Resolve exact RPC target; nearest pin is fallback only for opaque Use targets.

    If Usable is a concrete world InventoryPickup that is **not** a shape pin, return
    None so native ServerUse can collect it (vacuum / ground loot). Never hijack those
    onto the nearest pin within 320cm.
    """
    if not _pinned_slots or not _landing_settle_done or _mid_shape_dump():
        return None
    # Vacuum native collect — never redirect.
    try:
        from . import loot_coil as _coil

        if bool(getattr(_coil, "_vacuum_native_use", False)):
            return None
    except Exception:
        pass
    param_names: list[str] = []
    try:
        prop = getattr(func, "ChildProperties", None)
        for _ in range(32):
            if prop is None:
                break
            name = str(getattr(prop, "Name", "") or "").strip()
            flags = int(getattr(prop, "PropertyFlags", 0) or 0)
            if name and name not in ("ReturnValue", "Return", "__Result") and not (flags & 0x400):
                param_names.append(name)
            nxt = getattr(prop, "Next", None)
            if nxt is prop:
                break
            prop = nxt
    except Exception:
        param_names = []
    # Known spellings first, then every reflected non-return parameter.
    names = [
        "Object",
        "UseObject",
        "UsableObject",
        "TargetObject",
        "Target",
        "Actor",
        "Interactable",
        "Usable",
        "Component",
        *param_names,
    ]
    checked_names: set[str] = set()
    saw_unpinned_pickup = False
    for name in names:
        if not name or name in checked_names:
            continue
        checked_names.add(name)
        try:
            value = getattr(args, name, None)
        except Exception:
            value = None
        hit = _pinned_row_for_hook_value(value)
        if hit is not None:
            return hit
        if _looks_like_inventory_pickup_actor(value):
            saw_unpinned_pickup = True
            try:
                outer = getattr(value, "Outer", None)
            except Exception:
                outer = None
            if _looks_like_inventory_pickup_actor(outer):
                saw_unpinned_pickup = True
    # Concrete world pickup that isn't a pin — let native Use finish.
    if saw_unpinned_pickup:
        return None
    # Opaque Use target: release only the closest pin within interaction range.
    pawn = None
    for attr in ("Pawn", "OakCharacter", "AcknowledgedPawn"):
        try:
            candidate = getattr(controller, attr, None)
        except Exception:
            candidate = None
        if candidate is not None and _live(candidate):
            pawn = candidate
            break
    if pawn is None:
        return None
    try:
        pos = pawn.K2_GetActorLocation()
        px, py, pz = float(pos.X), float(pos.Y), float(pos.Z)
    except Exception:
        return None
    best: tuple[float, dict[str, Any], Any] | None = None
    for row in list(_pinned_slots):
        try:
            dx = float(row["x"]) - px
            dy = float(row["y"]) - py
            dz = float(row["z"]) - pz
            dist2 = dx * dx + dy * dy + dz * dz
        except Exception:
            continue
        if dist2 > (320.0 * 320.0):
            continue
        addr = int(row.get("addr") or 0)
        inv = _live_pickup(addr) if addr else None
        if inv is None or not _live(inv):
            continue
        if best is None or dist2 < best[0]:
            best = (dist2, row, inv)
    return (best[1], best[2]) if best is not None else None


def _on_server_use_release_pin(
    obj: Any,
    args: Any,
    _ret: Any,
    func: Any,
) -> Any:
    """PRE ServerUse*: collect shaped loot into the using player's backpack.

    Co-op shapes stay frozen for lobby visibility. Native Attract never finishes
    for guests on pinned freeze, and physics unlock drops the silhouette. So:
    give @U into that PC's backpack, destroy the world slot, Block native Use.
    Host uses the same path so grab works without collapsing the shape.
    """
    try:
        # Teach vacuum the live Use param layout (once) from a real player Use.
        try:
            from . import loot_coil as _coil

            _coil.note_live_server_use(args, func)
        except Exception:
            pass
        if not _pinned_slots or not _landing_settle_done or _mid_shape_dump():
            return None
        if _progression_network_busy() or _in_join_quiet():
            return None
        hit = _server_use_pin_target(obj, args, func)
        if hit is None:
            return None
        row, inv = hit
        if _collect_shaped_pickup_for_pc(obj, inv, row):
            try:
                from unrealsdk.hooks import Block

                return Block
            except Exception:
                return None
        # No serial / backpack miss — soft unlock (no gravity) so host can still try.
        if _is_local_player_controller(obj):
            _release_pin_for_pickup(inv, row)
    except Exception:
        return None
    return None


def install_loot_shapes_hooks(*, force: bool = False) -> None:
    """Install a light PlayerTick poll for late-joiner re-apply."""
    global _hooks_installed
    if _hooks_installed and not force:
        return
    try:
        from unrealsdk import hooks
        from unrealsdk.hooks import Type
    except Exception as exc:
        _log(f"Could not import hooks for loot shapes: {exc!r}")
        return

    # BL4 unrealsdk has POST / PRE / POST_UNCONDITIONAL — not PRE_UNCONDITIONAL.
    post_types = [Type.POST]
    post_u = getattr(Type, "POST_UNCONDITIONAL", None)
    if post_u is not None:
        post_types.append(post_u)
    pre_types = [Type.PRE]
    pre_u = getattr(Type, "PRE_UNCONDITIONAL", None)
    if pre_u is not None:
        pre_types.append(pre_u)

    def _on_tick(
        _obj: Any,
        _args: Any,
        _ret: Any,
        _func: Any,
    ) -> None:
        try:
            # World/session first — never touch pawn locations during teardown.
            if not _world_alive():
                try:
                    abandon_world_loot(schedule_orphan_absorb=False)
                except Exception:
                    pass
                return
            try:
                from .session_guards import session_safe

                if not session_safe():
                    abandon_world_loot(schedule_orphan_absorb=False)
                    return
            except Exception:
                pass
            if _player_left_drop_site():
                abandon_world_loot()
                return
        except Exception:
            return
        try:
            from . import map_fog_hide

            map_fog_hide.tick_fog_hide()
        except Exception:
            pass
        try:
            from . import character_flags

            character_flags.tick_character_flags()
        except Exception:
            pass
        try:
            from . import black_market as _bm

            _bm.tick_black_market()
        except Exception:
            pass
        try:
            tick_loot_shapes()
        except Exception:
            pass

    def _on_world_teardown(
        _obj: Any,
        _args: Any,
        _ret: Any,
        _func: Any,
    ) -> None:
        try:
            abandon_world_loot(schedule_orphan_absorb=False)
        except Exception:
            pass
        try:
            from .session_guards import notify_session_teardown

            notify_session_teardown("loot_shapes_hook")
        except Exception:
            pass

    tick_ok = False
    try:
        for i, path in enumerate(
            (
                "/Script/Oak2.OakPlayerController:PlayerTick",
                "/Script/OakGame.OakPlayerController:PlayerTick",
                "/Script/Engine.PlayerController:PlayerTick",
            )
        ):
            ident_list = (
                f"Squ1ggsBoostingTools.loot_shapes.tick.{i}",
                f"sqbt_loot_shapes_tick_{i}",
            )
            for ident in ident_list:
                for typ in post_types:
                    try:
                        hooks.remove_hook(path, typ, ident)
                    except Exception:
                        pass
                added = False
                for typ in post_types:
                    try:
                        if hooks.add_hook(path, typ, ident, _on_tick):
                            added = True
                            tick_ok = True
                            break
                    except Exception:
                        continue
                if not added:
                    try:
                        hooks.add_hook(path, Type.POST, ident, _on_tick)
                        tick_ok = True
                    except Exception:
                        pass
    except Exception as exc:
        _log(f"Loot shape tick hooks failed: {exc!r}")

    # Co-op Use on held pins: backpack collect + Block native Attract.
    try:
        for i, path in enumerate(
            (
                "/Script/Oak2.OakPlayerController:ServerUseObject",
                "/Script/OakGame.OakPlayerController:ServerUseObject",
                "/Script/Oak2.OakPlayerController:ServerUseJunkObject",
                "/Script/OakGame.OakPlayerController:ServerUseJunkObject",
            )
        ):
            ident = f"Squ1ggsBoostingTools.loot_shapes.server_use.{i}"
            for typ in (*pre_types, *post_types):
                try:
                    hooks.remove_hook(path, typ, ident)
                except Exception:
                    pass
            for typ in pre_types:
                try:
                    if hooks.add_hook(path, typ, ident, _on_server_use_release_pin):
                        break
                except Exception:
                    continue
    except Exception as exc:
        _log(f"Loot shape ServerUse hooks failed: {exc!r}")

    try:
        for i, path in enumerate(
            (
                "/Script/Engine.Engine:PreLoadMap",
                "/Script/Engine.World:BeginTearingDown",
                "/Script/Engine.PlayerController:ClientTravel",
                "/Script/Engine.PlayerController:ServerTravel",
                "/Script/Engine.PlayerController:ClientReturnToMainMenuWithTextReason",
                "/Script/OakGame.OakPlayerController:ClientReturnToMainMenu",
                "/Script/Oak2.OakPlayerController:ClientReturnToMainMenu",
                "/Script/Engine.GameInstance:ReturnToMainMenu",
            )
        ):
            ident_list = (
                f"Squ1ggsBoostingTools.loot_shapes.teardown.{i}",
                f"sqbt_loot_shapes_teardown_{i}",
            )
            for ident in ident_list:
                for typ in (*pre_types, *post_types):
                    try:
                        hooks.remove_hook(path, typ, ident)
                    except Exception:
                        pass
                added = False
                for typ in pre_types:
                    try:
                        if hooks.add_hook(path, typ, ident, _on_world_teardown):
                            added = True
                            break
                    except Exception:
                        continue
                if not added:
                    try:
                        hooks.add_hook(path, Type.POST, ident, _on_world_teardown)
                    except Exception:
                        pass
    except Exception as exc:
        _log(f"Loot shape teardown hooks failed: {exc!r}")

    # Mark installed once tick hooks landed — never leave False or reclaim stacks them.
    if tick_ok:
        _hooks_installed = True
        try:
            _last_layout["party_count"] = _party_count()
        except Exception:
            pass
    else:
        _log("Could not install loot shape PlayerTick hooks.")


def _tuned_layout(shape: str, radius: float, spacing: float, per_ring: int) -> tuple[float, float, int]:
    """Per-shape scale so the same Radius/Spacing sliders keep each silhouette readable."""
    scales = {
        "circle": (1.15, 1.0, 1.0),
        "double_ring": (1.05, 1.15, 1.0),
        "spiral": (1.1, 1.1, 1.0),
        "star": (1.25, 1.0, 1.0),
        "star_filled": (1.2, 1.0, 1.0),
        "firehawk": (1.65, 1.0, 1.0),
        "diamond": (1.2, 1.0, 1.0),
        "square": (1.15, 1.0, 1.0),
        "grid": (1.0, 1.2, 1.0),
        "rows": (1.0, 1.15, 0.85),
        "arc": (1.35, 1.0, 1.0),
        "fan": (1.25, 1.1, 1.0),
        "arrow": (1.35, 1.1, 1.0),
        "cross": (1.2, 1.05, 1.0),
        "x_mark": (1.25, 1.0, 1.0),
        "infinity": (1.4, 1.0, 1.0),
        "figure8": (1.3, 1.0, 1.0),
        "wave": (1.2, 1.15, 1.0),
        "letter_s": (1.15, 1.0, 1.0),
        "lightning": (1.4, 1.15, 1.0),
        "vault": (1.12, 1.0, 1.0),
        "psycho": (1.45, 1.05, 1.0),
        "pyramid": (1.0, 1.0, 1.0),
        "hexagon": (1.2, 1.0, 1.0),
        "honeycomb": (1.0, 1.2, 1.0),
        "scatter": (1.35, 1.0, 1.0),
        "poisson": (1.3, 1.15, 1.0),
        "type_piles": (1.7, 1.35, 0.8),
        "unique_piles": (1.85, 1.4, 0.75),
        "rarity_lanes": (1.2, 1.4, 1.0),
        "heart": (1.25, 1.0, 1.0),
        "line": (1.0, 1.0, 1.0),
        "rings": (1.1, 1.1, 1.0),
        "smiley": (1.3, 1.0, 1.0),
        "house": (1.0, 1.0, 1.0),
        "boat": (1.05, 1.0, 1.0),
        "car": (1.05, 1.0, 1.0),
        "dome": (1.05, 1.0, 1.0),
        "dna_helix": (1.05, 1.0, 1.0),
        "claptrap": (1.18, 1.0, 1.0),
        "pyramid_3d": (1.0, 1.0, 1.0),
        "globe": (1.0, 1.0, 1.0),
        "diamond_3d": (1.05, 1.0, 1.0),
        "blocks": (1.08, 1.0, 1.0),
        "cube": (1.05, 1.0, 1.0),
        "torus": (1.05, 1.0, 1.0),
        "crown": (1.05, 1.0, 1.0),
        "ufo": (1.1, 1.0, 1.0),
        "rocket": (1.05, 1.0, 1.0),
        "gear": (1.08, 1.0, 1.0),
        "nova": (1.25, 1.0, 1.0),
        "forbidden_one": (1.35, 1.0, 1.0),
        "forbidden_pair": (1.28, 1.0, 1.0),
    }
    sr, ss, sp = scales.get(shape, (1.15, 1.1, 1.0))
    return (
        max(_MIN_RADIUS, min(_MAX_RADIUS * 1.6, float(radius) * sr)),
        max(_MIN_SPACING, min(_MAX_SPACING * 1.4, float(spacing) * ss)),
        max(_MIN_PER_RING, min(_MAX_PER_RING, int(round(int(per_ring) * sp)))),
    )


def arrange_from_payload(payload: dict[str, Any] | None, *, mode: str = "place_fully") -> str:
    payload = payload or {}
    shape = _normalize_shape_name(payload.get("shape") or "circle")
    if shape not in SHAPE_NAMES:
        shape = "circle"
    layout = clamp_layout_params(
        radius=payload.get("radius", _DEFAULT_RADIUS),
        spacing=payload.get("spacing", _DEFAULT_SPACING),
        per_ring=payload.get("per_ring", _DEFAULT_PER_RING),
        line_length=payload.get("line_length", _DEFAULT_LINE_LENGTH),
        drop_height=payload.get("drop_height", _DEFAULT_DROP_HEIGHT),
        z_bias=payload.get("z_bias", _DEFAULT_Z_BIAS),
        stack_height=payload.get("stack_height", 0.0),
    )
    radius = float(layout["radius"])
    spacing = float(layout["spacing"])
    per_ring = int(layout["per_ring"])
    z_bias = float(layout["z_bias"])
    stack_height = float(layout["stack_height"])
    drop_height = float(layout["drop_height"])
    line_length = float(layout["line_length"])
    settle = normalize_drop_mode(payload.get("settle") if payload.get("settle") is not None else "none")
    # Nova Place Fully: pulse out of the center unless the user picked another motion.
    if shape == "nova" and settle in ("none", "snap", "drip"):
        settle = "explode"
    stay_raw = payload.get("stay_in_air", "no" if shape == "nova" else "yes")
    _set_air_hold(stay_raw, payload.get("peel_after", 0), shape=shape)
    set_float_on_grab(payload.get("float_on_grab", "no"))
    radius, spacing, per_ring = _tuned_layout(shape, radius, spacing, per_ring)
    raw_include = payload.get("include_consumables")
    if isinstance(raw_include, str):
        include = raw_include.strip().lower() in ("1", "true", "yes", "on")
    else:
        include = bool(raw_include)
    if mode == "quick":
        return quick_arrange(
            shape,
            radius=radius,
            spacing=spacing,
            per_ring=per_ring,
            z_bias=z_bias,
            stack_height=stack_height,
            include_consumables=include,
            settle=settle,
            drop_height=drop_height,
            line_length=line_length,
        )
    if mode == "reapply":
        return reapply_last_layout()
    if mode == "clear":
        return soft_clear_ground_loot()
    return place_fully(
        shape,
        radius=radius,
        spacing=spacing,
        per_ring=per_ring,
        z_bias=z_bias,
        stack_height=stack_height,
        include_consumables=include,
        settle=settle,
        drop_height=drop_height,
        line_length=line_length,
    )
