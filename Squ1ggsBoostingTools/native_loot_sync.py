"""Build-guarded native loot transform notification; no raw memory writes."""
import ctypes as C
import struct

_TABLE = 0xB3F5F50
_NOTIFY = 0x3D2BA48
_MARK = 0x10BB8C2
_GUEST_MASK = 0x1B  # sender requires row+0x2f8 & 0x1b when 0x2b0 bit0 is set
_HEAD = bytes.fromhex("5657534881ec9000000089d74889ce488b05e23e9d084831e048898424880000")
_COPY = bytes.fromhex("488b01ff502884c0743bf683b002000001750e4889f14889da41b004e838fc38fd488b8b08010000488b01488d7424204889f2ff5030488dbb30010000b90c000000f348a5")
# Verified mark helper: or byte ptr [row+0x2f8], mask (requires row+0x2b1 bit1).
_MARK_BYTES = bytes.fromhex(
    "5657534883ec204489c34889d74889ce8b412085c074498b4e1c85c97842390df60e8a0b7e3a0fb7d14c8b05d60e8a0b"
    "c1e910488d1452c1e203490314c87420394210751b8b4208a90000201075114889f1e8d796a0ff83f8030f8487000000"
    "f687b102000002747e089ff80200008b86f00300003b861c040000746a8b07488d8e20040000488b96280400004885d2"
    "480f45ca8b9630040000ffca21c28b149183faff7441488b8ee80300004c63c249c1e0044a8d14014239040175214885"
    "d274244883c204741e4881c6500300004889f14883c4205b5f5ee9334cccff8b520883faff75c64883c4205b5f5ec3"
)
_control = None


def locate(actor):
    from .native_pickup_handoff import _identity, _module_base
    from .loot_junk_diagnostics import _read
    from .shinies import _get_world
    _, base = _module_base()
    identity = _identity(actor, _read, base)
    token = int.from_bytes(identity, "little")
    def q(address):
        return struct.unpack("<Q", _read(address, 8))[0]
    def i(address):
        return struct.unpack("<i", _read(address, 4))[0]
    world = _get_world()
    if world is None or not actor.HasAuthority():
        raise ValueError("Native loot sync requires current host world")
    address = int(world._get_address())
    for offset in (0x1f0, 0x1e0, 0x38):
        address = q(address + offset)
    table = q(address)
    if q(table + 0x308) != base + 0x8F98C or _read(address + 0x1f0, 1) != b"\0":
        raise ValueError("Native world accessor/index changed")
    if q(table + 0x3a0) != base + 0x40488 or _read(base + 0x40488, 8) != bytes.fromhex("488b8178010000c3"):
        raise ValueError("Native world container getter changed")
    container = q(address + 0x178)
    system = q(container + 0x148)
    table = q(system)
    if table != base + _TABLE or q(table + 24) != base + _NOTIFY:
        raise ValueError("Native loot interface changed")
    if _read(base + _NOTIFY, len(_HEAD)) != _HEAD or _read(base + 0x3D2BC69, len(_COPY)) != _COPY:
        raise ValueError("Native loot notification implementation changed")
    if _read(base + _MARK, len(_MARK_BYTES)) != _MARK_BYTES:
        raise ValueError("Native loot mark helper changed")
    # Reproduce the native ID map lookup with bounded reads, then require that
    # its registered interface is this exact pickup, never a nearby item.
    count, buckets = i(system + 0x3f0), i(system + 0x430)
    if not 0 < count <= 100000 or not 0 < buckets <= 262144 or buckets & (buckets-1):
        raise ValueError("Native loot map bounds invalid")
    heads = q(system + 0x428) or system + 0x420
    entries = q(system + 0x3e8)
    index = i(heads + (token & (buckets-1))*4)
    row = None
    for _ in range(min(count, 128)):
        if not 0 <= index < count:
            break
        entry = entries + index*16
        if struct.unpack("<I", _read(entry, 4))[0] == token:
            slot = i(entry+4)
            num_bits = i(system+0x60)
            if not 0 <= slot < min(num_bits, 100000):
                break
            bits = q(system+0x58) or system+0x48
            word = struct.unpack("<I", _read(bits + (slot>>5)*4, 4))[0]
            if not word & (1 << (slot & 31)):
                break
            row = q(system+0x38) + slot*0x300
            break
        index = i(entry+8)
    if row is None or _read(row, 4) != identity or q(row+0x108) != int(actor._get_address())+0x520:
        raise ValueError("Native loot identity does not belong to this actor")
    return base, system, row, token


def _row_state(row, token, actor, read):
    flags = read(row + 0x2b0, 2)
    return {
        "id": token,
        "position": list(struct.unpack("<3d", read(row + 0x150, 24))),
        "flags": flags[:1].hex(),
        "flags2": flags[1:].hex(),
        "guest_mask": read(row + 0x2f8, 1).hex(),
        "state298": read(row + 0x298, 1).hex(),
        "mark_eligible": bool(flags[1] & 0x02),
        "actor": str(actor),
        "actor_position": str(actor.K2_GetActorLocation()),
    }


def notify(actor):
    base, system, row, token = locate(actor)
    # Verified complete method: void NotifyTransform(system, uint32 loot_id).
    # Copies the live actor transform; may mark bit 4 only when 0x2b0 bit0 is clear.
    call = C.PYFUNCTYPE(None, C.c_void_p, C.c_uint32)(base + _NOTIFY)
    call(system, token)
    return True


def mark_guest_bits(actor, mask: int = _GUEST_MASK):
    """OR replication bits into row+0x2f8 via the verified mark helper (no raw writes)."""
    mask = int(mask) & 0xFF
    if not mask:
        raise ValueError("Guest mark mask must be non-zero")
    base, system, row, token = locate(actor)
    from .loot_junk_diagnostics import _read
    before = _row_state(row, token, actor, _read)
    if not before["mark_eligible"]:
        raise ValueError("Native mark helper requires row+0x2b1 bit1; item is not mark-eligible")
    # void MarkDirty(system, row*, uint8 mask) — same helper NotifyTransform uses with mask 4.
    call = C.PYFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint8)(base + _MARK)
    call(system, row, mask)
    after = _row_state(row, token, actor, _read)
    return {"before": before, "after": after, "mask": mask}


def notify_for_guests(actor, mask: int = _GUEST_MASK):
    """Mark guest-visible dirty bits, then copy the live actor transform into the row."""
    marked = mark_guest_bits(actor, mask=mask)
    notify(actor)
    from .loot_junk_diagnostics import _read
    base, system, row, token = locate(actor)
    return {"marked": marked, "after_notify": _row_state(row, token, actor, _read)}


def control(mode):
    global _control
    from . import loot_shapes
    from .loot_junk_diagnostics import _read
    from unrealsdk.unreal import WeakPointer

    def state(actor):
        _, _, row, token = locate(actor)
        return _row_state(row, token, actor, _read)

    if mode == "status":
        actor = _control["actor"]() if _control else None
        return {"started": bool(_control), "before": _control["before"] if _control else None,
                "after": state(actor) if actor else None,
                "mode": _control.get("mode") if _control else None}
    if mode not in ("inspect", "start", "guest_start") or _control is not None:
        raise ValueError("Native movement control already started or invalid mode")
    for row in loot_shapes._pinned_slots:
        reference = row.get("reference")
        actor = reference() if reference else None
        if actor is None or not row.get("hold"):
            continue
        before = state(actor)
        if mode == "inspect":
            return before
        _control = {"actor": WeakPointer(actor), "before": before, "mode": mode}
        if mode == "guest_start":
            result = notify_for_guests(actor)
            return {"before": before, "after": state(actor), "guest": result}
        notify(actor)
        return {"before": before, "after": state(actor)}
    raise ValueError("No held item available for single-item movement check")
