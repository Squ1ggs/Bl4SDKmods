"""Scan boost-target backpack @U gear and bulk relevel in-place (on demand only).

Party Bay digs live InventoryIdentity the MSBT/LOV way:
  Identity +0xA0 -> @U pointer, +0xB0 length, +0xB8 capacity
  type via WrappedStruct._type.Name (not type().__name__)
  VirtualQuery-safe reads; dig from slot row then InventoryItem.

Stay shallow: deep dir() walks on fat packs AV the game.
"""
from __future__ import annotations

import ctypes
import re
from typing import Any

from .serial_converter import human_to_serial, rewrite_item_level, serial_to_human

_MAX_SLOT_WALK = 800
_INSTANCE_ID_RE = re.compile(r"InstanceId\s*[:=]\s*(\d+)", re.I)
_QUANTITY_RE = re.compile(r"Quantity\s*[:=]\s*(\d+)", re.I)

# MSBT / LOV InventoryIdentity layout.
_ITEM_SERIAL_POINTER_OFFSET = 0xA0
_ITEM_SERIAL_LENGTH_OFFSET = 0xB0
_ITEM_SERIAL_CAPACITY_OFFSET = 0xB8
_ITEM_SERIAL_MAX_CHARS = 131072

_LAST_SERIAL_DIG_HINT = ""


class _MemoryBasicInformation(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("PartitionId", ctypes.c_ushort),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]


def _safe_str(value: Any, *, limit: int = 240) -> str:
    if value is None:
        return ""
    try:
        text = str(value).strip()
    except Exception:
        return ""
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _attr(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    try:
        return getattr(obj, name, None)
    except Exception:
        return None


def _serial_text(value: Any) -> str:
    text = _safe_str(value, limit=512)
    if text.startswith("@U") and len(text) >= 12 and "@U" not in text[2:]:
        return text
    return ""


def _parse_int_from_blob(blob: str, pattern: re.Pattern[str]) -> int:
    if not blob:
        return 0
    try:
        m = pattern.search(blob)
        if not m:
            return 0
        return int(m.group(1))
    except Exception:
        return 0


def _struct_type_name(value: Any) -> str:
    if value is None:
        return ""
    try:
        struct_type = getattr(value, "_type", None)
        if struct_type is not None:
            name = getattr(struct_type, "Name", None)
            if name:
                return str(name)
    except Exception:
        pass
    try:
        return type(value).__name__
    except Exception:
        return ""


def _is_uobject(value: Any) -> bool:
    if value is None:
        return False
    try:
        _ = value.Name
        _ = value.Class
        return True
    except Exception:
        return False


def _object_address(value: Any) -> int:
    if value is None:
        return 0
    try:
        addr = int(value._get_address())
    except Exception:
        return 0
    return addr if addr > 0 and addr != 0xFFFFFFFFFFFFFFFF else 0


def _canonical_ptr(address: int) -> bool:
    value = int(address or 0)
    return 0x10000 <= value <= 0x00007FFFFFFFFFFF and (value & 7) == 0


def _native_range_readable(address: int, size: int) -> bool:
    if address <= 0 or size < 0:
        return False
    try:
        kernel32 = ctypes.windll.kernel32
        info = _MemoryBasicInformation()
        result = kernel32.VirtualQuery(
            ctypes.c_void_p(address), ctypes.byref(info), ctypes.sizeof(info)
        )
        if not result or int(info.State) != 0x1000:
            return False
        if int(info.Protect) & (0x01 | 0x100):
            return False
        start = int(info.BaseAddress or 0)
        return address >= start and address + size <= start + int(info.RegionSize)
    except Exception:
        return False


def _read_native_memory(address: int, size: int) -> bytes | None:
    if not _native_range_readable(address, size):
        return None
    try:
        return ctypes.string_at(address, size)
    except Exception:
        return None


def _read_native_u64(address: int) -> int | None:
    raw = _read_native_memory(address, 8)
    return int.from_bytes(raw, "little") if raw is not None else None


def _read_native_u32(address: int) -> int | None:
    raw = _read_native_memory(address, 4)
    return int.from_bytes(raw, "little") if raw is not None else None


def _looks_like_inventory_identity(value: Any) -> bool:
    if value is None or _is_uobject(value):
        return False
    return _struct_type_name(value) == "InventoryIdentity" and _object_address(value) > 0


def _identity_from_value(value: Any) -> Any:
    if _looks_like_inventory_identity(value):
        return value
    paths = (
        ("Identity",),
        ("InventoryIdentity",),
        ("data", "Identity"),
        ("Data", "Identity"),
        ("item", "data", "Identity"),
        ("Item", "data", "Identity"),
        ("item", "Data", "Identity"),
        ("InventoryItem",),
        ("InventoryItem", "data", "Identity"),
        ("InventoryItem", "item", "data", "Identity"),
        ("InventoryItem", "Identity"),
    )
    for path in paths:
        node: Any = value
        try:
            for name in path:
                node = getattr(node, name)
        except Exception:
            continue
        if path == ("InventoryItem",):
            hit = _identity_from_value(node)
            if hit is not None:
                return hit
            continue
        if _looks_like_inventory_identity(node):
            return node
    return None


def _serial_info_from_identity(identity: Any) -> dict[str, Any]:
    global _LAST_SERIAL_DIG_HINT
    address = _object_address(identity)
    type_name = _struct_type_name(identity) or "?"
    if not address:
        _LAST_SERIAL_DIG_HINT = f"Identity type={type_name} addr=0"
        return {}
    data_address = _read_native_u64(address + _ITEM_SERIAL_POINTER_OFFSET)
    length = _read_native_u64(address + _ITEM_SERIAL_LENGTH_OFFSET)
    capacity = _read_native_u64(address + _ITEM_SERIAL_CAPACITY_OFFSET)
    if data_address is None or length is None:
        _LAST_SERIAL_DIG_HINT = f"Identity type={type_name} addr=0x{address:x} ptr/len unreadable"
        return {}
    if (
        int(length) < 2
        or int(length) > _ITEM_SERIAL_MAX_CHARS
        or (
            capacity is not None
            and (int(capacity) < int(length) or int(capacity) > _ITEM_SERIAL_MAX_CHARS * 2)
        )
        or not _canonical_ptr(int(data_address))
    ):
        _LAST_SERIAL_DIG_HINT = (
            f"Identity type={type_name} addr=0x{address:x} "
            f"ptr@A0=0x{int(data_address):x} len@B0={int(length)} "
            f"cap@B8={int(capacity) if capacity is not None else -1}"
        )
        return {}
    raw = _read_native_memory(int(data_address), int(length))
    if raw is None:
        _LAST_SERIAL_DIG_HINT = (
            f"Identity type={type_name} addr=0x{address:x} "
            f"ptr@A0=0x{int(data_address):x} len={int(length)} (page not readable)"
        )
        return {}
    try:
        serial = raw.split(b"\x00", 1)[0].decode("ascii", "ignore").strip()
    except Exception:
        serial = ""
    hit = _serial_text(serial)
    if not hit:
        _LAST_SERIAL_DIG_HINT = (
            f"Identity type={type_name} addr=0x{address:x} "
            f"ptr@A0=0x{int(data_address):x} len={int(length)} (no @U ascii)"
        )
        return {}
    level = _read_native_u32(address + 0xC4)
    return {"serial": hit, "level": int(level) if level is not None else -1}


def _serial_header_ok(serial: str) -> bool:
    """True when @U has a readable type/flags/level header (MSBT-style; no full parse)."""
    raw = str(serial or "").strip()
    if not raw.startswith("@U") or len(raw) < 12:
        return False
    try:
        from .serial_converter import _read_header_numbers

        numbers, _leftover = _read_header_numbers(raw)
        return len(numbers) == 4 and int(numbers[3]) >= 1
    except Exception:
        return False


def _serial_from_identity_source(source: Any) -> str:
    identity = _identity_from_value(source)
    if identity is None:
        return ""
    info = _serial_info_from_identity(identity)
    return str(info.get("serial") or "")


def _serial_from_source(source: Any) -> str:
    global _LAST_SERIAL_DIG_HINT
    _LAST_SERIAL_DIG_HINT = ""
    if source is None:
        return ""
    attr_serial = ""
    for attr in (
        "ItemSerialString",
        "ItemSerial",
        "SerialString",
        "Serial",
        "CachedSerial",
        "ItemSerialNumber",
        "SerializedData",
    ):
        hit = _serial_text(_attr(source, attr))
        if hit:
            attr_serial = hit
            break
    id_serial = _serial_from_identity_source(source)
    # Reflected strings are often truncated; Identity +0xA0 is the full @U (Party Bay path).
    # Prefer whichever has a valid level header — full human parse is not required.
    if id_serial and _serial_header_ok(id_serial):
        return id_serial
    if attr_serial and _serial_header_ok(attr_serial):
        return attr_serial
    if id_serial:
        return id_serial
    if attr_serial:
        return attr_serial
    if _identity_from_value(source) is None:
        _LAST_SERIAL_DIG_HINT = f"no InventoryIdentity (type={_struct_type_name(source) or '?'})"
    return ""


def _serial_for_relevel(slot: Any, inv: Any) -> str:
    """Best @U for relevel — InventoryItem first, then slot row; header-ok preferred."""
    for src in (inv, slot):
        if src is None:
            continue
        serial = _serial_from_source(src)
        if serial.startswith("@U") and _serial_header_ok(serial):
            return serial
    for src in (inv, slot):
        if src is None:
            continue
        serial = _serial_from_source(src)
        if serial.startswith("@U"):
            return serial
    return ""


def _iter_backpack_slots(ps: Any) -> list[Any]:
    wrapper = _attr(ps, "BackpackItems")
    if wrapper is None:
        for alt in ("InventoryItems", "PlayerInventoryItems"):
            wrapper = _attr(ps, alt)
            if wrapper is not None:
                break
    entries = _attr(wrapper, "items") if wrapper is not None else None
    if entries is None and wrapper is not None:
        entries = _attr(wrapper, "Items")
    if entries is None:
        return []
    try:
        count = len(entries)
    except Exception:
        count = -1
    if count >= 0:
        out: list[Any] = []
        for index in range(min(int(count), _MAX_SLOT_WALK)):
            try:
                out.append(entries[index])
            except Exception:
                continue
        return out
    try:
        slots = list(entries)
    except Exception:
        return []
    return slots[:_MAX_SLOT_WALK]


def _slot_inv_item(slot: Any) -> Any | None:
    if slot is None:
        return None
    for attr in ("InventoryItem", "inventoryItem"):
        inv = _attr(slot, attr)
        if inv is not None:
            return inv
    if _struct_type_name(slot) == "InventoryItem" or _attr(slot, "data") is not None:
        return slot
    return None


def _instance_id(inv: Any) -> int:
    data = _attr(inv, "data") or _attr(inv, "Data")
    if data is not None:
        for name in ("InstanceId", "InstanceID", "instanceId"):
            try:
                raw = getattr(data, name, None)
            except Exception:
                raw = None
            if raw is None:
                continue
            try:
                value = int(raw)
            except Exception:
                value = _parse_int_from_blob(_safe_str(raw, limit=64), _INSTANCE_ID_RE)
            if value > 0:
                return value
    for node in (inv, _attr(inv, "Handle"), _attr(inv, "SourceItemHandle"), _attr(inv, "ItemHandle")):
        value = _parse_int_from_blob(_safe_str(node, limit=220), _INSTANCE_ID_RE)
        if value > 0:
            return value
    return 0


def _quantity(inv: Any) -> int:
    state = _attr(inv, "State") or _attr(inv, "state")
    if state is not None:
        for name in ("Quantity", "quantity"):
            try:
                raw = getattr(state, name, None)
            except Exception:
                raw = None
            if raw is None:
                continue
            try:
                value = int(raw)
            except Exception:
                value = _parse_int_from_blob(_safe_str(raw, limit=64), _QUANTITY_RE)
            if value > 0:
                return value
    for node in (inv, _attr(inv, "Handle"), _attr(inv, "SourceItemHandle"), _attr(inv, "ItemHandle")):
        value = _parse_int_from_blob(_safe_str(node, limit=220), _QUANTITY_RE)
        if value > 0:
            return value
    return 0


def _slot_display_bits(inv: Any) -> tuple[str, str]:
    handle = ""
    for attr in ("Handle", "SourceItemHandle", "ItemHandle"):
        raw = _safe_str(_attr(inv, attr), limit=96)
        if not raw or raw.lower() in ("none", "null"):
            continue
        if raw.startswith("{") or "InstanceId" in raw or "Identity" in raw:
            continue
        handle = raw
        break
    item_name = ""
    item_ref = _attr(inv, "item") or _attr(inv, "Item")
    if item_ref is not None:
        for attr in ("DisplayName", "ItemName", "Name", "InternalName", "LocalizedName"):
            value = _attr(item_ref, attr)
            if value:
                candidate = _safe_str(value, limit=96)
                if candidate and not candidate.startswith("{") and "InstanceId" not in candidate:
                    item_name = candidate
                    break
        if not item_name:
            candidate = _safe_str(item_ref, limit=96)
            if (
                candidate
                and candidate.lower() not in ("none", "null")
                and not candidate.startswith("{")
                and "InstanceId" not in candidate
            ):
                item_name = candidate
    return handle, item_name


def _slot_occupied(inv: Any) -> bool:
    if inv is None:
        return False
    if _instance_id(inv) > 0:
        return True
    if _quantity(inv) > 0:
        return True
    handle, item_name = _slot_display_bits(inv)
    if handle or item_name:
        return True
    for attr in ("Handle", "SourceItemHandle", "ItemHandle", "ItemSerial", "Serial"):
        text = _safe_str(_attr(inv, attr), limit=120)
        if not text or text.lower() in ("none", "null"):
            continue
        if text.startswith("{"):
            if _parse_int_from_blob(text, _INSTANCE_ID_RE) > 0:
                return True
            if _parse_int_from_blob(text, _QUANTITY_RE) > 0:
                return True
            continue
        return True
    return False


def _player_state_for_index(player_index: int) -> tuple[Any | None, str]:
    from .serial_rewards import _pc_for_player_index

    pc = _pc_for_player_index(int(player_index))
    if pc is None:
        return None, f"No live player at index {player_index}."
    ps = getattr(pc, "PlayerState", None)
    if ps is None:
        return None, "No PlayerState on target."
    return ps, ""


def _equip_slot_of(source: Any) -> int | None:
    candidates = [source, _slot_inv_item(source) if source is not None else None]
    for candidate in candidates:
        if candidate is None:
            continue
        for attr in ("EquipSlot", "equipSlot", "EquipmentSlot", "Slot"):
            try:
                raw = getattr(candidate, attr, None)
            except Exception:
                raw = None
            if raw is None:
                continue
            try:
                return int(raw)
            except Exception:
                continue
    return None


_EQUIP_SLOT_NAMES: dict[int, str] = {
    0: "Weapon 1",
    1: "Weapon 2",
    2: "Weapon 3",
    3: "Weapon 4",
    4: "Shield",
    5: "Grenade",
    6: "Class mod",
    7: "Repkit",
    8: "Enhancement",
}


def _equip_label(slot: int | None) -> str:
    if slot is None:
        return ""
    if int(slot) in _EQUIP_SLOT_NAMES:
        return _EQUIP_SLOT_NAMES[int(slot)]
    if 0 <= int(slot) <= 64:
        return f"Worn {int(slot)}"
    return ""


def _is_equipped(slot: int | None) -> bool:
    return slot is not None and 0 <= int(slot) <= 64


def scan_backpack_rows(
    player_index: int,
    *,
    limit: int | None = None,
    include_equipped: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    ps, err = _player_state_for_index(player_index)
    if ps is None:
        return [], err
    cap = None
    if limit is not None:
        try:
            cap = max(1, int(limit))
        except Exception:
            cap = None
    rows: list[dict[str, Any]] = []
    truncated = False
    occupied = 0
    with_serial = 0
    equipped_n = 0
    skipped_errors = 0
    try:
        slots = _iter_backpack_slots(ps)
    except Exception as exc:
        return [], f"Backpack slot list failed ({exc})."
    for index, slot in enumerate(slots):
        try:
            inv = _slot_inv_item(slot)
            if inv is None or not _slot_occupied(inv):
                continue
            occupied += 1
            equip = _equip_slot_of(slot) or _equip_slot_of(inv)
            worn = _is_equipped(equip)
            if worn:
                equipped_n += 1
                if not include_equipped:
                    continue
            if cap is not None and len(rows) >= cap:
                truncated = True
                continue
            try:
                serial = _serial_from_source(slot) or _serial_from_source(inv)
            except Exception:
                serial = ""
            handle, item_name = _slot_display_bits(inv)
            human = ""
            level: int | None = None
            if serial.startswith("@U"):
                with_serial += 1
                try:
                    human = str(serial_to_human(serial) or "").strip()
                except Exception:
                    human = ""
                if human:
                    try:
                        m = re.match(r"\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*(\d+)", human)
                        if m:
                            level = int(m.group(1))
                    except Exception:
                        level = None
            iid = _instance_id(inv)
            qty = _quantity(inv)
            wear = _equip_label(equip) if worn else ""
            meta_name = ""
            rarity = ""
            manufacturer = ""
            item_type = ""
            live_name = ""
            live_handle = ""
            try:
                from . import item_labels

                live_name = item_labels.usable_display_name(item_name)
                live_handle = item_labels.usable_display_name(handle)
                if serial.startswith("@U"):
                    meta = item_labels.meta_from_serial(serial)
                    meta_name = item_labels.usable_display_name(
                        str(meta.get("display_name") or meta.get("unique_name") or "")
                    )
                    rarity = str(meta.get("rarity") or "").strip()
                    manufacturer = str(meta.get("manufacturer") or "").strip()
                    item_type = str(meta.get("item_type") or "").strip()
                    if level is None:
                        level = item_labels.level_from_serial(serial)
            except Exception:
                live_name = str(item_name or "").strip()
                live_handle = str(handle or "").strip()
                meta_name = ""
            # Prefer GZO lore when live DisplayName is a failed localize ("Cannot reveal").
            pretty = (
                live_name
                or meta_name
                or live_handle
                or (human.split(",")[0].strip()[:48] if human else "")
                or (serial[:56] if serial else "")
                or (f"item #{iid}" if iid > 0 else "")
                or (f"qty {qty}" if qty > 0 else "")
                or "occupied slot"
            )
            bits: list[str] = []
            if rarity:
                bits.append(rarity)
            if manufacturer and manufacturer.casefold() not in pretty.casefold():
                bits.append(manufacturer)
            if item_type and item_type.casefold() not in pretty.casefold():
                bits.append(item_type)
            suffix = f" · {' / '.join(bits)}" if bits else ""
            if worn and wear:
                label = f"{wear} — {pretty}{suffix}"
            else:
                label = f"{pretty}{suffix}"
            if level is not None:
                label = f"{label} L{level}"
            title = f"★ {label}" if worn else f"#{index} — {label}"
            row: dict[str, Any] = {
                "id": f"{'eq' if worn else 'bp'}-{index}",
                "slot": int(index),
                "equip_slot": int(equip) if equip is not None else -1,
                "origin": "equipped" if worn else "backpack",
                "serial": serial if serial.startswith("@U") else "",
                "human": human,
                "title": title,
            }
            if meta_name:
                row["display_name"] = meta_name
            if rarity:
                row["rarity"] = rarity
            if manufacturer:
                row["manufacturer"] = manufacturer
            if item_type:
                row["item_type"] = item_type
            if handle:
                row["handle"] = handle
            if live_name:
                row["name"] = live_name
            elif item_name and not meta_name:
                row["name"] = item_name
            if level is not None:
                row["level"] = level
            if iid > 0:
                row["instance_id"] = iid
            if not serial.startswith("@U"):
                row["note"] = "no @U — copy/mail unavailable"
            rows.append(row)
        except Exception:
            skipped_errors += 1
            continue
    rows.sort(
        key=lambda r: (
            0 if r.get("origin") == "equipped" else 1,
            int(r.get("equip_slot") if r.get("equip_slot") is not None else 99),
            int(r.get("slot") or 0),
        )
    )
    who = f"player index {int(player_index)}"
    if not occupied:
        message = (
            f"0 occupied backpack slots ({who}). "
            "Pick the Boost target that owns the gear, then Snap once."
        )
    else:
        message = (
            f"{len(rows)} item(s) ({equipped_n} worn, {with_serial} with @U) from {occupied} occupied "
            f"({who})."
        )
        if with_serial == 0 and occupied > 0:
            hint = str(_LAST_SERIAL_DIG_HINT or "").strip()
            message += " No @U in live Identity yet."
            if hint:
                message += f" Dig: {hint}"
                try:
                    from . import runtime_log

                    runtime_log.note(f"party_bay serial dig miss: {hint}")
                except Exception:
                    pass
            else:
                message += " Try Pack Bay (autosave) for host @U, or Snap again in-world."
    if truncated:
        message += f" Sheet capped at {cap}."
    if skipped_errors:
        message += f" Skipped {skipped_errors} slot(s) on read errors."
    return rows, message


def _relevel_serial(serial: str, level: int) -> tuple[str | None, str | None]:
    raw = str(serial or "").strip()
    if not raw.startswith("@U"):
        return None, "not a Base85 @U serial"
    level_i = max(1, min(int(level or 60), 100))
    # MSBT path: header-only rewrite (no full part parse). Truncated @U still EOF.
    try:
        converted = rewrite_item_level(raw, level_i)
        if converted and str(converted).startswith("@U"):
            return str(converted).strip(), None
    except Exception as header_exc:
        header_err = str(header_exc)
    else:
        header_err = "header rewrite returned empty"
    # Fallback: full human round-trip for odd alphabets that still decode offline.
    try:
        human = serial_to_human(raw)
        level_re = re.compile(r"^(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*)\d+")
        new_human, count = level_re.subn(rf"\g<1>{level_i}", human, count=1)
        if count <= 0:
            return None, f"could not find item level ({header_err})"
        converted = human_to_serial(new_human)
        if not converted or not str(converted).startswith("@U"):
            return None, f"re-encode failed after level rewrite ({header_err})"
        return str(converted).strip(), None
    except Exception as exc:
        return None, f"{exc} (header: {header_err})"


def _clear_backpack_slot(ps: Any, slot_index: int) -> bool:
    slots = _iter_backpack_slots(ps)
    if slot_index < 0 or slot_index >= len(slots):
        return False
    slot = slots[slot_index]
    for attr in ("InventoryItem", "inventoryItem"):
        try:
            setattr(slot, attr, None)
            if _slot_inv_item(slot) is None:
                return True
        except Exception:
            continue
    return _slot_inv_item(slot) is None


def relevel_backpack_slots(player_index: int, slot_indices: list[int], level: int) -> dict[str, Any]:
    from .item_spawn.pearl_serial_spawn import try_deliver_serial

    ps, err = _player_state_for_index(player_index)
    if ps is None:
        return {"ok": False, "message": err, "updated": 0, "failed": 0, "errors": [err]}
    slots = _iter_backpack_slots(ps)
    work = sorted({int(i) for i in slot_indices if str(i).strip() != ""})
    updated = 0
    failed = 0
    errors: list[str] = []
    for slot_index in work:
        if slot_index < 0 or slot_index >= len(slots):
            failed += 1
            errors.append(f"slot #{slot_index}: out of range")
            continue
        slot = slots[slot_index]
        inv = _slot_inv_item(slot)
        if inv is None:
            failed += 1
            errors.append(f"slot #{slot_index}: empty")
            continue
        old_serial = _serial_for_relevel(slot, inv)
        if not old_serial.startswith("@U"):
            failed += 1
            errors.append(f"slot #{slot_index}: no @U serial")
            continue
        new_serial, rewrite_err = _relevel_serial(old_serial, level)
        if not new_serial:
            failed += 1
            errors.append(f"slot #{slot_index}: level rewrite failed ({rewrite_err or 'unknown'})")
            continue
        if new_serial == old_serial:
            updated += 1
            continue
        if not try_deliver_serial(new_serial, 1):
            failed += 1
            errors.append(f"slot #{slot_index}: could not add releveled item to backpack")
            continue
        if not _clear_backpack_slot(ps, slot_index):
            errors.append(
                f"slot #{slot_index}: added releveled copy but old slot may still show — drop duplicate manually"
            )
        updated += 1
    ok = updated > 0 and failed == 0
    message = (
        f"Releveled {updated} backpack item(s) to level {int(level)} for player index {int(player_index)}."
        if ok
        else f"Releveled {updated} item(s); {failed} failed."
    )
    if errors and len(errors) <= 4:
        message += " " + "; ".join(errors[:4])
    elif errors:
        message += f" First issue: {errors[0]}"
    return {
        "ok": ok or updated > 0,
        "message": message,
        "updated": updated,
        "failed": failed,
        "errors": errors[:12],
        "level": int(level),
    }


def collect_releveled_serials(
    player_index: int,
    slot_indices: list[int],
    level: int,
) -> dict[str, Any]:
    """Dig ticked slots, rewrite @U level headers — no live inject / no destroy yet."""
    ps, err = _player_state_for_index(player_index)
    if ps is None:
        return {
            "ok": False,
            "message": err,
            "serials": [],
            "slot_indices": [],
            "failed": 0,
            "errors": [err],
        }
    slots = _iter_backpack_slots(ps)
    work = sorted({int(i) for i in slot_indices if str(i).strip() != ""})
    serials: list[str] = []
    ok_slots: list[int] = []
    failed = 0
    errors: list[str] = []
    for slot_index in work:
        if slot_index < 0 or slot_index >= len(slots):
            failed += 1
            errors.append(f"slot #{slot_index}: out of range")
            continue
        slot = slots[slot_index]
        inv = _slot_inv_item(slot)
        if inv is None:
            failed += 1
            errors.append(f"slot #{slot_index}: empty")
            continue
        old_serial = _serial_for_relevel(slot, inv)
        if not old_serial.startswith("@U"):
            failed += 1
            errors.append(f"slot #{slot_index}: no @U serial")
            continue
        new_serial, rewrite_err = _relevel_serial(old_serial, level)
        if not new_serial:
            failed += 1
            errors.append(f"slot #{slot_index}: level rewrite failed ({rewrite_err or 'unknown'})")
            continue
        serials.append(new_serial)
        ok_slots.append(slot_index)
    return {
        "ok": bool(serials),
        "message": (
            f"Prepared {len(serials)} releveled @U at level {int(level)}"
            + (f" ({failed} failed)." if failed else ".")
        ),
        "serials": serials,
        "slot_indices": ok_slots,
        "failed": failed,
        "errors": errors[:12],
        "level": int(level),
    }


def clear_backpack_slots(player_index: int, slot_indices: list[int]) -> dict[str, Any]:
    """Clear ticked backpack slots after mail relevel (optional)."""
    ps, err = _player_state_for_index(player_index)
    if ps is None:
        return {"ok": False, "message": err, "cleared": 0}
    cleared = 0
    for slot_index in sorted({int(i) for i in slot_indices if str(i).strip() != ""}):
        if _clear_backpack_slot(ps, int(slot_index)):
            cleared += 1
    return {
        "ok": cleared > 0,
        "message": f"Cleared {cleared} old backpack slot(s).",
        "cleared": cleared,
    }


def export_backpack_txt(
    player_index: int,
    *,
    slot_indices: list[int] | None = None,
    include_equipped: bool = True,
) -> dict[str, Any]:
    """Build a .txt dump of Party Bay @U codes (ticked rows, or full snap)."""
    rows, err = scan_backpack_rows(
        player_index,
        limit=None,
        include_equipped=include_equipped,
    )
    if err and not rows:
        return {"ok": False, "message": err, "text": "", "count": 0}
    want: set[int] | None = None
    if slot_indices:
        want = {int(i) for i in slot_indices if str(i).strip() != ""}
    lines: list[str] = []
    for row in rows:
        try:
            slot = int(row.get("slot"))
        except Exception:
            continue
        if want is not None and slot not in want:
            continue
        serial = str(row.get("serial") or "").strip()
        if not serial.startswith("@U"):
            continue
        title = str(row.get("title") or row.get("name") or f"slot {slot}").strip()
        lines.append(f"# {title}")
        lines.append(serial)
        lines.append("")
    if not lines:
        return {
            "ok": False,
            "message": "No @U serials to export (Snap once / tick rows with serials).",
            "text": "",
            "count": 0,
        }
    text = "\n".join(lines).rstrip() + "\n"
    count = sum(1 for line in lines if line.startswith("@U"))
    return {
        "ok": True,
        "message": f"Exported {count} @U serial(s).",
        "text": text,
        "count": count,
        "player_index": int(player_index),
    }
