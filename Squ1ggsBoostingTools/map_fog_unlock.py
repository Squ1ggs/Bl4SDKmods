"""Unlock map locations / safehouses via dump-proven discovery bits + station handles.

Also widens live FoD walk-unfog radius (MSBT-style UnfogRadius setattr + FOD manager
floats) with MSBT's fixed widen — no user radius knob (MSBT does not expose one).

Fog raster (100% visited) is still ``gbx_discovery_pc.foddatas`` 128x128 0xFF in
the save — FOD manager has no reflected fields for that. Safehouses/FT are the
``OakGameState.DiscoveryReplicatedBitArray`` (same GbxFastReplicatedBitArray
challenge complete already writes) plus ``FGameDataHandle(24576, 'World_P.FT_…')``
on ``ServerReportDiscoveredPoAState`` / live ``FastTravelStationObject.NexusData``.
"""

from __future__ import annotations

import ctypes
import json
import struct
from pathlib import Path
from typing import Any

import unrealsdk
from mods_base import get_pc
from unrealsdk import logging

from .challenge_objective_state import COMPLETE_WORD, _append, _make_bit_item

_PREFIX = "[Squ1ggs's Boosting Tools | MapFogUnlock]"
_STATION_TYPE = 24576
_UNLOCK_STATE = 2
_STATIONS_JSON = Path(__file__).resolve().parent / "travelstations.json"
_logged_sigs: set[str] = set()

# MSBT fod_reveal uses a fixed widen (not a user radius knob) — match that.
_DEFAULT_UNFOG_RADIUS = 10000000.0
_UNFOG_RATE = 10.0
_FOD_MANAGER_CLS = "GbxDiscoveryFODManagerCPU"
# Walk radius lives at +0xC0 / +0xC8 (defaults ~30000). Widen via real unfog.
_FOD_UNFOG_OFFS = (0xC0, 0xC8)
_HOLDER_CLASSES = (
    "GbxDiscoveryUnfogData",
    "GbxDiscoveryPinConfig",
    "GbxDiscoveryGlobals",
    "GbxDiscoveryViewableMapDef",
    "GbxDiscoveryViewableMapBehaviorDef",
    "GbxDiscoveryDiscovererDef",
    "GbxDiscoveryFODManagerCPU",
    "GbxDiscoverySaveGameData",
)
_NEST_ATTRS = (
    "UnfogData",
    "OverrideUnfogData",
    "Discoverer",
    "DiscovererDef",
    "ViewableMapBehavior",
    "ViewableMapBehaviorDef",
    "PinConfig",
    "DiscoveryComponent",
    "GbxDiscoveryComponent",
    "OakDiscoveryComponent",
)
_BOOL_FIELDS = ("bUseOverrideUnfog",)

try:
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _PAGE_EXECUTE_READWRITE = 0x40
except Exception:  # pragma: no cover
    wintypes = None  # type: ignore[assignment]
    _kernel32 = None
    _PAGE_EXECUTE_READWRITE = 0x40


def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")


def _obj_name(obj: Any) -> str:
    try:
        return str(getattr(obj, "Name", "") or obj)
    except Exception:
        return str(obj)


def _is_default(obj: Any) -> bool:
    name = _obj_name(obj)
    return name.startswith("Default__") or name.startswith("default__")


def _find_all(class_name: str) -> list[Any]:
    try:
        return list(unrealsdk.find_all(class_name, False) or [])
    except TypeError:
        try:
            return list(unrealsdk.find_all(class_name) or [])
        except Exception:
            return []
    except Exception:
        return []


def _live(class_name: str) -> list[Any]:
    return [obj for obj in _find_all(class_name) if obj is not None and not _is_default(obj)]


def _obj_addr(obj: Any) -> int:
    for attr in ("_address", "address", "_addr"):
        try:
            value = getattr(obj, attr, None)
        except Exception:
            value = None
        if isinstance(value, int) and value > 0x10000:
            return int(value)
    try:
        text = str(obj)
    except Exception:
        return 0
    if "0x" in text:
        try:
            return int(text[text.index("0x") :].split()[0], 16)
        except Exception:
            return 0
    return 0


def _read_f32(addr: int) -> float | None:
    if addr < 0x10000:
        return None
    try:
        return float(struct.unpack("<f", ctypes.string_at(addr, 4))[0])
    except Exception:
        return None


def _write_f32(addr: int, value: float) -> bool:
    if addr < 0x10000 or _kernel32 is None or wintypes is None:
        return False
    data = struct.pack("<f", float(value))
    old = wintypes.DWORD()
    if not _kernel32.VirtualProtect(
        ctypes.c_void_p(addr), len(data), _PAGE_EXECUTE_READWRITE, ctypes.byref(old)
    ):
        return False
    try:
        ctypes.memmove(addr, data, len(data))
    except Exception:
        return False
    restored = wintypes.DWORD()
    _kernel32.VirtualProtect(ctypes.c_void_p(addr), len(data), old.value, ctypes.byref(restored))
    return True


def _prop_offset(obj: Any, field_name: str) -> int:
    cls = getattr(obj, "Class", None) or getattr(obj, "Struct", None)
    hops = 0
    while cls is not None and hops < 16:
        hops += 1
        child = getattr(cls, "ChildProperties", None) or getattr(cls, "Children", None)
        current = child
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            try:
                name = str(getattr(current, "Name", "") or "")
            except Exception:
                name = ""
            if name == field_name:
                for attr in ("Offset_Internal", "offset_internal", "Offset", "PropertyOffset"):
                    try:
                        off = int(getattr(current, attr, -1) or -1)
                    except Exception:
                        off = -1
                    if off >= 0:
                        return off
            current = getattr(current, "Next", None)
        cls = getattr(cls, "SuperField", None) or getattr(cls, "SuperStruct", None)
    return -1


def _set_float_field(obj: Any, name: str, value: float) -> str:
    try:
        setattr(obj, name, float(value))
        after = getattr(obj, name)
        if after is not None and abs(float(after) - float(value)) < 0.01:
            return "setattr"
    except Exception:
        pass
    base = _obj_addr(obj)
    offset = _prop_offset(obj, name)
    if base and offset >= 0 and _write_f32(base + offset, float(value)):
        got = _read_f32(base + offset)
        if got is not None and abs(got - float(value)) < 0.01:
            return "memory"
    return ""


def _set_bool_field(obj: Any, name: str, value: bool) -> bool:
    try:
        setattr(obj, name, bool(value))
        return True
    except Exception:
        return False


def _apply_unfog_fields(obj: Any, radius: float) -> dict[str, int]:
    counts = {"setattr": 0, "memory": 0, "bools": 0}
    for flag in _BOOL_FIELDS:
        if _set_bool_field(obj, flag, True):
            counts["bools"] += 1
    values = {
        "UnfogRadius": radius,
        "UnfogRadiusVehicle": radius,
        "UnfogHeight": radius,
        "UnfogHeightVehicle": radius,
        "UnfogRate": _UNFOG_RATE,
        "UnfogSaveRate": _UNFOG_RATE,
        "PercentageOfUnfogRadiusThatIsFull": 1.0,
    }
    for name, value in values.items():
        method = _set_float_field(obj, name, value)
        if method:
            counts[method] += 1
    return counts


def _widen_fod_unfog_radius(radius: float) -> int:
    """Widen live walk-unfog floats on GbxDiscoveryFODManagerCPU +0xC0 / +0xC8."""
    try:
        target = max(10000.0, float(radius))
    except Exception:
        target = _DEFAULT_UNFOG_RADIUS
    wrote = 0
    for obj in _find_all(_FOD_MANAGER_CLS):
        if obj is None or _is_default(obj):
            continue
        base = _obj_addr(obj)
        if not base:
            continue
        for off in _FOD_UNFOG_OFFS:
            before = _read_f32(base + off)
            if before is None or before != before:
                continue
            if not (1.0 <= float(before) <= 1.0e8):
                continue
            if not _write_f32(base + off, target):
                continue
            after = _read_f32(base + off)
            wrote += 1
            _log(f"FOD-UNFOG {_obj_name(obj)}+{off:#x} {before} -> {after}")
    return wrote


def _collect_unfog_holders() -> list[tuple[str, Any]]:
    holders: list[tuple[str, Any]] = []
    seen: set[int] = set()

    def _add(label: str, obj: Any, depth: int = 0) -> None:
        if obj is None or depth > 2:
            return
        key = _obj_addr(obj) or id(obj)
        if key in seen:
            return
        seen.add(key)
        holders.append((label, obj))
        for name in _NEST_ATTRS:
            try:
                child = getattr(obj, name, None)
            except Exception:
                child = None
            if child is None or callable(child):
                continue
            _add(f"{label}.{name}", child, depth + 1)

    for cls_name in _HOLDER_CLASSES:
        for obj in _live(cls_name)[:24]:
            _add(cls_name, obj)
    pc = get_pc()
    if pc is not None:
        for attr in ("PlayerState", "Pawn", "AcknowledgedPawn"):
            try:
                child = getattr(pc, attr, None)
            except Exception:
                child = None
            if child is not None:
                _add(f"pc.{attr}", child)
    return holders


def _apply_live_unfog_radius(radius: float) -> str:
    radius_f = max(1000.0, float(radius))
    holders = _collect_unfog_holders()
    setattr_n = 0
    memory_n = 0
    bools_n = 0
    touched = 0
    for _label, obj in holders:
        counts = _apply_unfog_fields(obj, radius_f)
        wrote = int(counts["setattr"]) + int(counts["memory"])
        if wrote <= 0 and int(counts["bools"]) <= 0:
            continue
        touched += 1
        setattr_n += int(counts["setattr"])
        memory_n += int(counts["memory"])
        bools_n += int(counts["bools"])
    widen = _widen_fod_unfog_radius(radius_f)
    return (
        f"unfog radius={radius_f:.0f} fields setattr={setattr_n} memory={memory_n} "
        f"bools={bools_n} on {touched}/{len(holders)} holder(s); fod_widen={widen}"
    )


def _handle_name(value: Any) -> str:
    if value is None:
        return ""
    for attr in ("name", "Name", "_experimental_name"):
        try:
            text = str(getattr(value, attr, "") or "").strip()
        except Exception:
            text = ""
        if text and text.lower() not in ("none", "null"):
            return text.split("/")[-1]
    text = str(value).strip()
    if "FGameDataHandle(" in text:
        parts = text.split("'")
        if len(parts) >= 2:
            return parts[1].strip()
    return ""


def _station_handle(token: str) -> Any | None:
    label = (token or "").strip()
    if not label or label.lower() in ("none", "null"):
        return None
    try:
        from unrealsdk.unreal import FGameDataHandle

        return FGameDataHandle(_STATION_TYPE, label)
    except Exception:
        return None


def _field_chain(start: Any, *, limit: int = 512) -> list[Any]:
    out: list[Any] = []
    current = start
    seen: set[int] = set()
    while current is not None and len(out) < limit:
        key = id(current)
        if key in seen:
            break
        seen.add(key)
        out.append(current)
        nxt = getattr(current, "Next", None)
        if nxt is current:
            break
        current = nxt
    return out


def _ufunction_param_names(fn_obj: Any | None) -> list[str]:
    if fn_obj is None:
        return []
    names: list[str] = []
    props = getattr(fn_obj, "ChildProperties", None)
    for prop in _field_chain(props, limit=64):
        try:
            name = str(getattr(prop, "Name", "") or "").strip()
        except Exception:
            name = ""
        if not name or name in ("ReturnValue", "Return", "__Result"):
            continue
        try:
            if int(getattr(prop, "PropertyFlags", 0) or 0) & 0x400:
                continue
        except Exception:
            pass
        names.append(name)
    return names


def _find_ufunction(owner: Any, function_name: str, *paths: str) -> Any | None:
    for path in paths:
        try:
            hit = unrealsdk.find_object("Function", path)
        except Exception:
            hit = None
        if hit is not None:
            return hit
    cls = getattr(owner, "Class", None)
    hops = 0
    while cls is not None and hops < 12:
        hops += 1
        child = getattr(cls, "Children", None)
        for node in _field_chain(child, limit=2048):
            try:
                if str(getattr(node, "Name", "") or "") == function_name:
                    return node
            except Exception:
                continue
        cls = getattr(cls, "SuperField", None) or getattr(cls, "SuperStruct", None)
    return None


def _log_sig_once(tag: str, fn_obj: Any | None) -> None:
    if tag in _logged_sigs:
        return
    _logged_sigs.add(tag)
    names = _ufunction_param_names(fn_obj)
    _log(f"sig {tag}: {','.join(names) or '(none)'}")


def _call_bound(bound: Any, fn_obj: Any | None, values: dict[str, Any]) -> bool:
    if not callable(bound):
        return False
    names = _ufunction_param_names(fn_obj)
    kwargs: dict[str, Any] = {}
    for name in names:
        key = name.lower()
        if key in values and values[key] is not None:
            kwargs[name] = values[key]
    attempts: list[Any] = []
    if kwargs:
        attempts.append(kwargs)
    ident = values.get("locationmetadataident") or values.get("inlocation")
    if ident is not None:
        attempts.append((ident, values.get("discoverstate", _UNLOCK_STATE)))
        attempts.append((ident,))
    actor = values.get("inactor")
    if actor is not None:
        attempts.append((actor,))
        loc_type = values.get("inlocationtype")
        if loc_type is not None:
            attempts.append((actor, loc_type))
    for args in attempts:
        try:
            if isinstance(args, dict):
                bound(**args)
            else:
                bound(*args)
            return True
        except Exception:
            continue
    return False


def _fill_bit_array(bit_array: Any, *, ensure_slots: int = 32) -> int:
    if bit_array is None:
        return 0
    writes = 0
    for items_name in ("items", "Items"):
        try:
            sequence = getattr(bit_array, items_name, None)
        except Exception:
            sequence = None
        if sequence is None:
            continue
        try:
            count = len(list(sequence))
        except Exception:
            count = 0
        while count < max(1, int(ensure_slots)):
            item = _make_bit_item(count)
            if item is None or not _append(sequence, item):
                break
            count += 1
            writes += 1
        for index in range(count):
            try:
                item = sequence[index]
            except Exception:
                continue
            try:
                current = getattr(item, "BitField", None)
            except Exception:
                current = None
            if isinstance(current, int) and current == COMPLETE_WORD:
                continue
            try:
                setattr(item, "BitField", COMPLETE_WORD)
                try:
                    sequence[index] = item
                except Exception:
                    pass
                writes += 1
            except Exception:
                continue
        try:
            setattr(bit_array, items_name, sequence)
        except Exception:
            pass
        try:
            key = int(getattr(bit_array, "ArrayReplicationKey", 0) or 0)
            setattr(bit_array, "ArrayReplicationKey", key + 1)
        except Exception:
            pass
        return writes
    return 0


def _game_state(pc: Any) -> Any | None:
    for obj in _live("OakGameState"):
        return obj
    world = None
    fn = getattr(pc, "GetWorld", None)
    if callable(fn):
        try:
            world = fn()
        except Exception:
            world = None
    if world is None:
        try:
            from mods_base import ENGINE

            viewport = getattr(ENGINE, "GameViewport", None)
            world = getattr(viewport, "World", None) if viewport is not None else None
        except Exception:
            world = None
    if world is not None:
        try:
            gs = getattr(world, "GameState", None)
            if gs is not None:
                return gs
        except Exception:
            pass
    return None


def _fill_discovery_bits(pc: Any) -> str:
    gs = _game_state(pc)
    writes = 0
    live_actors = 0
    gs_name = "none"
    if gs is not None:
        gs_name = _obj_name(gs)
        try:
            bits = getattr(gs, "DiscoveryReplicatedBitArray", None)
        except Exception:
            bits = None
        writes = _fill_bit_array(bits, ensure_slots=32)
        try:
            setattr(gs, "DiscoveryReplicatedBitArray", bits)
        except Exception:
            pass
        onrep = getattr(gs, "OnRep_DiscoveryReplicationData", None)
        if callable(onrep):
            try:
                onrep()
            except Exception:
                pass
        try:
            container = getattr(gs, "DiscoveryReplicatedLiveActors", None)
            array = getattr(container, "Array", None) if container is not None else None
        except Exception:
            array = None
        if array is not None:
            for actor in _live("FastTravelStationObject") + _live("PoAActor"):
                if _append(array, actor):
                    live_actors += 1
    return f"bits writes={writes} live_actors={live_actors} gs={gs_name}"


def _catalog_station_ids() -> list[str]:
    try:
        data = json.loads(_STATIONS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("stations") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        station = str(row.get("station") or "").strip()
        if not station.lower().startswith("world_p."):
            continue
        typedef = str(row.get("typedef") or "").lower()
        low = station.lower()
        if not (
            "safehouse" in low
            or "silo" in low
            or "fast_travel" in typedef
            or ".ft_" in low
            or ".fts_" in low
        ):
            continue
        if station in seen:
            continue
        seen.add(station)
        out.append(station)
    return out


def _unlock_handles(pc: Any, tokens: list[str]) -> tuple[int, int]:
    poa = getattr(pc, "ServerReportDiscoveredPoAState", None)
    disc = getattr(pc, "ServerDiscoveryMakeNonAuthoritativeDiscovery", None)
    notify = getattr(pc, "ClientDiscoveryNotifyLocationDiscoveredStateChanged", None)
    poa_fn = _find_ufunction(
        pc,
        "ServerReportDiscoveredPoAState",
        "/Script/OakGame.OakPlayerController:ServerReportDiscoveredPoAState",
    )
    disc_fn = _find_ufunction(
        pc,
        "ServerDiscoveryMakeNonAuthoritativeDiscovery",
        "/Script/OakGame.OakPlayerController:ServerDiscoveryMakeNonAuthoritativeDiscovery",
    )
    notify_fn = _find_ufunction(
        pc,
        "ClientDiscoveryNotifyLocationDiscoveredStateChanged",
        "/Script/OakGame.OakPlayerController:ClientDiscoveryNotifyLocationDiscoveredStateChanged",
    )
    _log_sig_once("ServerReportDiscoveredPoAState", poa_fn)
    _log_sig_once("ServerDiscoveryMakeNonAuthoritativeDiscovery", disc_fn)
    _log_sig_once("ClientDiscoveryNotifyLocationDiscoveredStateChanged", notify_fn)
    player_state = getattr(pc, "PlayerState", None)
    region = getattr(player_state, "ServerSetDiscoveryRegion", None) if player_state is not None else None
    ok = 0
    fail = 0
    for token in tokens:
        handle = _station_handle(token)
        if handle is None:
            fail += 1
            continue
        values = {
            "locationmetadataident": handle,
            "inlocation": handle,
            "discoverstate": _UNLOCK_STATE,
            "inproximity": True,
            "indiscoveringplayer": player_state,
        }
        hit = False
        if _call_bound(poa, poa_fn, values):
            hit = True
        if _call_bound(disc, disc_fn, values):
            hit = True
        if _call_bound(notify, notify_fn, values):
            hit = True
        if callable(region):
            try:
                region(handle)
                hit = True
            except Exception:
                pass
        if hit:
            ok += 1
        else:
            fail += 1
    return ok, fail


def _unlock_live_stations(pc: Any) -> tuple[int, int, list[str]]:
    lib = None
    try:
        lib = unrealsdk.find_class("GbxDiscoveryFunctionLibrary").ClassDefaultObject
    except Exception:
        lib = None
    make_live = getattr(lib, "MakeLiveLocationDiscoverable", None) if lib is not None else None
    make_actor = getattr(lib, "MakeActorDiscoverable", None) if lib is not None else None
    make_live_fn = (
        _find_ufunction(
            lib,
            "MakeLiveLocationDiscoverable",
            "/Script/GbxGame.GbxDiscoveryFunctionLibrary:MakeLiveLocationDiscoverable",
        )
        if lib is not None
        else None
    )
    make_actor_fn = (
        _find_ufunction(
            lib,
            "MakeActorDiscoverable",
            "/Script/GbxGame.GbxDiscoveryFunctionLibrary:MakeActorDiscoverable",
        )
        if lib is not None
        else None
    )
    _log_sig_once("MakeLiveLocationDiscoverable", make_live_fn)
    _log_sig_once("MakeActorDiscoverable", make_actor_fn)
    tokens: list[str] = []
    ok = 0
    fail = 0
    for actor in _live("FastTravelStationObject") + _live("PoAActor"):
        token = ""
        for attr in ("NexusData", "DynamicNexusData"):
            try:
                token = _handle_name(getattr(actor, attr, None))
            except Exception:
                token = ""
            if token:
                break
        if not token:
            getter = getattr(actor, "GetTravelStationNexusName", None)
            if callable(getter):
                try:
                    token = str(getter() or "").strip()
                except Exception:
                    token = ""
        if token:
            tokens.append(token)
        values = {
            "inactor": actor,
            "inlocationtype": getattr(actor, "NexusData", None),
            "incomponenttype": None,
        }
        hit = False
        if _call_bound(make_live, make_live_fn, values):
            hit = True
        if _call_bound(make_actor, make_actor_fn, values):
            hit = True
        if hit:
            ok += 1
        else:
            fail += 1
    return ok, fail, tokens


def expand_unfog_radius(radius: float | None = None) -> str:
    """Unlock safehouses/FT + widen live FoD walk-unfog radius (MSBT-style).

    ``radius`` is ignored — MSBT Host Clear Fog uses a fixed widen, not a UI field.
    Kept as a kwarg so older bridge payloads do not break.
    """
    pc = get_pc()
    if pc is None:
        msg = "No player controller. Load a character first."
        _log(msg)
        return msg

    radius_f = _DEFAULT_UNFOG_RADIUS
    if radius is not None:
        # Older UIs may still send a value; never go below MSBT's fixed widen.
        try:
            radius_f = max(_DEFAULT_UNFOG_RADIUS, float(radius))
        except Exception:
            radius_f = _DEFAULT_UNFOG_RADIUS

    bits = _fill_discovery_bits(pc)
    live_ok, live_fail, live_tokens = _unlock_live_stations(pc)
    catalog = _catalog_station_ids()
    merged: list[str] = []
    seen: set[str] = set()
    for token in live_tokens + catalog:
        if token in seen:
            continue
        seen.add(token)
        merged.append(token)
    handle_ok, handle_fail = _unlock_handles(pc, merged)
    unfog = _apply_live_unfog_radius(radius_f)
    msg = (
        f"{bits}. live stations ok={live_ok} fail={live_fail}. "
        f"handles {handle_ok}/{len(merged)} fail={handle_fail} "
        f"(safehouse/silo/FT World_P). {unfog}. Reopen the map. "
        "Not the same as Hide map fog (overlay)."
    )
    _log(msg)
    return msg
