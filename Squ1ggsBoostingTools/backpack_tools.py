"""Scan boost-target backpack @U gear and bulk relevel in-place (on demand only)."""
from __future__ import annotations

import re
from typing import Any

from .serial_converter import human_to_serial, serial_to_human


def _iter_backpack_slots(ps: Any) -> list[Any]:
    wrapper = getattr(ps, "BackpackItems", None)
    if wrapper is None:
        return []
    for attr in ("items", "Items"):
        entries = getattr(wrapper, attr, None)
        if entries is None:
            continue
        try:
            return list(entries)
        except Exception:
            continue
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


def _safe_str(value: Any, *, limit: int = 240) -> str:
    if value is None:
        return ""
    try:
        text = str(value).strip()
    except Exception:
        return ""
    if not text or text.lower() in ("none", "null"):
        return ""
    return text[:limit]


def _looks_like_struct_dump(text: str) -> bool:
    low = text.lower()
    if text.startswith("{") or text.startswith("<"):
        return True
    if "instanceid" in low or "identity:" in low or "quantity:" in low:
        return True
    if "flags:" in low and "state:" in low:
        return True
    return False


def _dig_serial(obj: Any, *, depth: int = 0) -> str:
    """Pull @U from inventory wrappers (attrs first — no world-pickup memory dig)."""
    if obj is None or depth > 4:
        return ""
    for attr in (
        "ItemSerialString",
        "ItemSerial",
        "SerialString",
        "Serial",
        "serial",
        "CachedSerial",
        "ItemSerialNumber",
    ):
        try:
            raw = getattr(obj, attr, None)
        except Exception:
            continue
        text = _safe_str(raw, limit=512)
        if text.startswith("@U") and len(text) >= 12:
            return text
    for path in (
        ("ItemData", "ItemSerial"),
        ("item", "ItemSerial"),
        ("SerializedItem", "ItemSerial"),
        ("InventoryData", "ItemSerial"),
        ("data", "ItemSerial"),
        ("Identity", "ItemSerial"),
        ("data", "Identity", "ItemSerial"),
    ):
        cur: Any = obj
        ok = True
        for part in path:
            try:
                cur = getattr(cur, part, None)
            except Exception:
                ok = False
                break
            if cur is None:
                ok = False
                break
        if not ok:
            continue
        text = _safe_str(cur, limit=512)
        if text.startswith("@U") and len(text) >= 12:
            return text
    if depth < 2:
        for attr in ("item", "ItemData", "InventoryData", "SerializedItem", "data", "Identity", "InventoryIdentity"):
            try:
                child = getattr(obj, attr, None)
            except Exception:
                continue
            hit = _dig_serial(child, depth=depth + 1)
            if hit:
                return hit
    return ""


def _inventory_label(inv: Any) -> str:
    for attr in ("ItemName", "DisplayName", "UIName", "LocalizedName", "Name"):
        try:
            raw = getattr(inv, attr, None)
        except Exception:
            continue
        text = _safe_str(raw, limit=96)
        if text and not _looks_like_struct_dump(text) and not text.startswith("Inventory"):
            return text
    return ""


def _slot_quantity(slot: Any, inv: Any) -> int | None:
    for obj in (inv, slot):
        if obj is None:
            continue
        for attr in ("Quantity", "ItemQuantity", "Count", "StackCount"):
            try:
                raw = getattr(obj, attr, None)
            except Exception:
                continue
            try:
                if raw is not None:
                    return int(raw)
            except Exception:
                continue
        for path in (("State", "Quantity"), ("item", "State", "Quantity"), ("data", "State", "Quantity")):
            cur: Any = obj
            ok = True
            for part in path:
                try:
                    cur = getattr(cur, part, None)
                except Exception:
                    ok = False
                    break
                if cur is None:
                    ok = False
                    break
            if not ok:
                continue
            try:
                return int(cur)
            except Exception:
                continue
    return None


def _identity_nonempty(inv: Any) -> bool:
    if inv is None:
        return False
    for path in (
        ("Identity",),
        ("InventoryIdentity",),
        ("data", "Identity"),
        ("item", "Identity"),
        ("item", "data", "Identity"),
    ):
        cur: Any = inv
        ok = True
        for part in path:
            try:
                cur = getattr(cur, part, None)
            except Exception:
                ok = False
                break
            if cur is None:
                ok = False
                break
        if not ok or cur is None:
            continue
        try:
            text = str(cur).strip()
        except Exception:
            text = ""
        if text and text not in ("{}", "None", "null") and "Identity: {}" not in text:
            # Empty struct dumps look like "{}" or "InventoryIdentity()"
            if text in ("InventoryIdentity()", "InventoryIdentity{}"):
                continue
            if "InstanceId" in text or "Serial" in text or "@U" in text:
                return True
            # Non-empty UObject / non-trivial identity
            if not _looks_like_struct_dump(text) or "InstanceId" in text:
                return True
        for attr in ("Serial", "ItemSerial", "ItemSerialString", "Handle", "Guid"):
            try:
                val = getattr(cur, attr, None)
            except Exception:
                continue
            if val is not None and _safe_str(val, limit=64):
                return True
    return False


def _instance_id(inv: Any) -> int | None:
    for path in (
        ("InstanceId",),
        ("data", "InstanceId"),
        ("item", "InstanceId"),
        ("item", "data", "InstanceId"),
    ):
        cur: Any = inv
        ok = True
        for part in path:
            try:
                cur = getattr(cur, part, None)
            except Exception:
                ok = False
                break
            if cur is None:
                ok = False
                break
        if not ok:
            continue
        try:
            return int(cur)
        except Exception:
            continue
    return None


def _slot_occupied(slot: Any, inv: Any) -> bool:
    if inv is None:
        return False
    if _dig_serial(inv) or _dig_serial(slot):
        return True
    if _inventory_label(inv):
        return True
    qty = _slot_quantity(slot, inv)
    if qty is not None and qty <= 0:
        return False
    if _identity_nonempty(inv):
        return True
    for attr in ("Handle", "SourceItemHandle", "ItemHandle"):
        try:
            raw = getattr(inv, attr, None)
        except Exception:
            continue
        text = _safe_str(raw, limit=64)
        if text and not _looks_like_struct_dump(text):
            return True
    # Quantity>0 with empty Identity still shows in-game as a slot — keep visible
    # but mark non-releveable. InstanceId alone is enough to list it.
    if qty is not None and qty > 0:
        return True
    if _instance_id(inv) is not None:
        return True
    return False


def _serial_from_slot(slot: Any, inv: Any) -> str:
    for obj in (inv, slot):
        hit = _dig_serial(obj)
        if hit:
            return hit
    # World-pickup dig can AV on inventory structs — only try as last resort.
    try:
        from .loot_shapes import serial_from_pickup

        hit = str(serial_from_pickup(inv) or "").strip()
        if hit.startswith("@U") and len(hit) >= 12:
            return hit
    except Exception:
        pass
    return ""


def _level_from_human(human: str) -> int | None:
    text = str(human or "").strip()
    if not text:
        return None
    # Human form usually starts: seed, manufacturer, type, level, ...
    m = re.match(r"^\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*(\d+)", text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _row_title(*, index: int, label: str, serial: str, human: str, level: int | None) -> str:
    parts: list[str] = [f"#{index}"]
    if level is not None:
        parts.append(f"L{level}")
    if label:
        parts.append(label[:72])
    elif human:
        parts.append(human[:64])
    elif serial.startswith("@U"):
        parts.append(f"{serial[:28]}…")
    else:
        parts.append("no @U serial")
    return " — ".join((parts[0], " · ".join(parts[1:]))) if len(parts) > 1 else parts[0]


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
    occupied = 0
    scanned = 0
    # Cap reflection cost on modded 1k+ backpacks.
    for index, slot in enumerate(_iter_backpack_slots(ps)):
        if scanned >= 800:
            break
        scanned += 1
        inv = _slot_inv_item(slot)
        if not _slot_occupied(slot, inv):
            continue
        occupied += 1
        serial = _serial_from_slot(slot, inv)
        human = ""
        level: int | None = None
        if serial.startswith("@U"):
            try:
                human = str(serial_to_human(serial) or "").strip()
            except Exception:
                human = ""
            level = _level_from_human(human)
        label = _inventory_label(inv)
        if not label and human:
            # Prefer a short human head over raw serial when name attrs are missing.
            label = human.split(",")[0].strip()[:48] if "," in human else human[:48]
        title = _row_title(index=index, label=label, serial=serial, human=human, level=level)
        rows.append(
            {
                "id": str(index),
                "slot": int(index),
                "serial": serial,
                "human": human,
                "level": level,
                "title": title,
                "releveable": bool(serial.startswith("@U")),
                "quantity": _slot_quantity(slot, inv),
            }
        )
    who = f"player index {int(player_index)}"
    if not rows and occupied <= 0:
        return [], f"No occupied backpack slots found ({who}). Check Boost target."
    releveable = sum(1 for r in rows if r.get("releveable"))
    return (
        rows,
        f"{len(rows)} backpack item(s) ({releveable} with @U serials) for {who}.",
    )


def _relevel_serial(serial: str, level: int) -> tuple[str | None, str | None]:
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


def _backpack_has_serial(ps: Any, serial: str) -> bool:
    needle = str(serial or "").strip()
    if not needle.startswith("@U"):
        return False
    for slot in _iter_backpack_slots(ps):
        inv = _slot_inv_item(slot)
        if not inv:
            continue
        hit = _serial_from_slot(slot, inv)
        if hit == needle:
            return True
    return False


def _deliver_serial_to_player(player_index: int, serial: str) -> tuple[bool, str]:
    """Deliver @U into the boost-target backpack; never clear until caller verifies."""
    from .serial_rewards import _pc_for_player_index

    pc = _pc_for_player_index(int(player_index))
    if pc is None:
        return False, "no live player for delivery"
    # Prefer bound *FromSerial methods on the target PC / inventory first.
    try:
        from .item_spawn import pearl_serial_spawn as pearl

        methods = getattr(pearl, "_BACKPACK_SERIAL_METHODS", ()) or ()
        targets: list[tuple[str, Any]] = [("pc", pc)]
        pawn = getattr(pc, "Pawn", None)
        if pawn is not None:
            targets.append(("pawn", pawn))
        ps = getattr(pc, "PlayerState", None)
        if ps is not None:
            targets.append(("playerstate", ps))
        for label, obj in targets:
            for method in methods:
                try:
                    if pearl._invoke_serial_method(obj, method, serial, 1):
                        return True, f"{label}.{method}"
                except Exception:
                    continue
            for method in pearl._discover_serial_methods(obj):
                if method in methods:
                    continue
                low = str(method).lower()
                if "fromserial" not in low or "spawn" in low:
                    continue
                try:
                    if pearl._invoke_serial_method(obj, method, serial, 1):
                        return True, f"{label}.{method}"
                except Exception:
                    continue
    except Exception as exc:
        return False, f"target deliver failed: {exc}"
    # Last resort: local host methods (may land on wrong player — caller must verify).
    try:
        from .item_spawn.pearl_serial_spawn import try_deliver_serial

        if try_deliver_serial(serial, 1):
            return True, "local try_deliver_serial"
    except Exception as exc:
        return False, str(exc)
    return False, "no FromSerial RPC matched for target"


def relevel_backpack_slots(player_index: int, slot_indices: list[int], level: int) -> dict[str, Any]:
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
        old_serial = _serial_from_slot(slots[slot_index], inv)
        if not old_serial.startswith("@U"):
            failed += 1
            errors.append(f"slot #{slot_index}: no @U serial (cannot relevel — left untouched)")
            continue
        new_serial, rewrite_err = _relevel_serial(old_serial, level)
        if not new_serial:
            failed += 1
            errors.append(f"slot #{slot_index}: level rewrite failed ({rewrite_err or 'unknown'})")
            continue
        if new_serial == old_serial:
            updated += 1
            continue
        delivered, via = _deliver_serial_to_player(int(player_index), new_serial)
        if not delivered:
            failed += 1
            errors.append(f"slot #{slot_index}: deliver failed ({via}) — original kept")
            continue
        # Never wipe the original unless the releveled copy is actually present.
        if not _backpack_has_serial(ps, new_serial):
            failed += 1
            errors.append(
                f"slot #{slot_index}: deliver reported {via} but new @U not found — original kept"
            )
            continue
        if not _clear_backpack_slot(ps, slot_index):
            errors.append(
                f"slot #{slot_index}: releveled copy added ({via}) but old slot may still show — drop duplicate manually"
            )
        updated += 1
    ok = updated > 0 and failed == 0
    message = (
        f"Releveled {updated} backpack item(s) to level {int(level)} for player index {int(player_index)}."
        if ok
        else f"Releveled {updated} item(s); {failed} failed (nothing deleted without a verified replacement)."
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
