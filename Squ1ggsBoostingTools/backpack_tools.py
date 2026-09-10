"""Scan boost-target backpack @U gear and bulk relevel in-place (on demand only)."""
from __future__ import annotations

from typing import Any

from .serial_converter import human_to_serial, serial_to_human


def _iter_backpack_slots(ps: Any) -> list[Any]:
    wrapper = getattr(ps, "BackpackItems", None)
    entries = getattr(wrapper, "items", None) if wrapper is not None else None
    if entries is None:
        return []
    try:
        return list(entries)
    except Exception:
        return []


def _slot_inv_item(slot: Any) -> Any | None:
    if slot is None:
        return None
    for attr in ("InventoryItem", "inventoryItem"):
        try:
            inv = getattr(slot, attr, None)
        except Exception:
            continue
        if inv is not None:
            return inv
    return None


def _serial_from_inv_item(inv: Any) -> str:
    if inv is None:
        return ""
    try:
        from .loot_shapes import serial_from_pickup

        return str(serial_from_pickup(inv) or "").strip()
    except Exception:
        pass
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
        text = str(raw).strip()
        if text.startswith("@U") and len(text) >= 12:
            return text
    return ""


def _player_state_for_index(player_index: int) -> tuple[Any | None, str]:
    from .serial_rewards import _pc_for_player_index

    pc = _pc_for_player_index(int(player_index))
    if pc is None:
        return None, f"No live player at index {player_index}."
    ps = getattr(pc, "PlayerState", None)
    if ps is None:
        return None, "No PlayerState on target."
    return ps, ""


def scan_backpack_rows(player_index: int) -> tuple[list[dict[str, Any]], str]:
    ps, err = _player_state_for_index(player_index)
    if ps is None:
        return [], err
    rows: list[dict[str, Any]] = []
    for index, slot in enumerate(_iter_backpack_slots(ps)):
        inv = _slot_inv_item(slot)
        if inv is None:
            continue
        serial = _serial_from_inv_item(inv)
        if not serial.startswith("@U"):
            continue
        human = ""
        try:
            human = str(serial_to_human(serial) or "").strip()
        except Exception:
            human = ""
        label = human[:96] if human else serial[:56]
        rows.append(
            {
                "id": str(index),
                "slot": int(index),
                "serial": serial,
                "human": human,
                "title": f"#{index} — {label}",
            }
        )
    who = f"player index {int(player_index)}"
    return rows, f"{len(rows)} backpack item(s) with @U serials ({who})."


def _relevel_serial(serial: str, level: int) -> tuple[str | None, str | None]:
    import re

    raw = str(serial or "").strip()
    if not raw.startswith("@U"):
        return None, "not a Base85 @U serial"
    level_i = max(1, min(int(level or 60), 100))
    try:
        human = serial_to_human(raw)
        level_re = re.compile(r"^(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*)\d+")
        new_human, count = level_re.subn(rf"\g<1>{level_i}", human, count=1)
        if count <= 0:
            return None, "could not find item level in human decode"
        converted = human_to_serial(new_human)
        if not converted or not str(converted).startswith("@U"):
            return None, "re-encode failed after level rewrite"
        return str(converted).strip(), None
    except Exception as exc:
        return None, str(exc)


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
        inv = _slot_inv_item(slots[slot_index])
        if inv is None:
            failed += 1
            errors.append(f"slot #{slot_index}: empty")
            continue
        old_serial = _serial_from_inv_item(inv)
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
