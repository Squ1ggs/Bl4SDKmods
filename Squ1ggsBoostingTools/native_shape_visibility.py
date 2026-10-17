"""Guarded suppression of the native ground display for replicated shape actors.

Leaves the host JunkId and InventoryPickup intact. The separate native feed
would otherwise create a second ground display on guests. Restores only the
original feed bit when the mod stops.
"""
import ctypes as C
import hashlib
import math
import struct

_GUARDS = (
    (0x1695D04, 2261, 'ab2628cac28abc5a1b00aaa429014c5486b6882276603d88a7188101270fa7c5'),
    (0xC65E3C, 88, 'b493b22ca2d3b78f980816534c8639408a1ba30c14415e8996136ee196538f8a'),
    (0xC65E94, 57, 'c8d62553525b7ecfb321fba988bca3633f80a14b2d1a1701478e8a7af4c7b96f'),
    (0xDA2CD8, 131, '1ec90248ecde06bdbc1529616d96f720ad5e50266d9df1dbabf57c10a9b324a0'),
)
_FEED_WRITE = bytes.fromhex('8a8bb102000080e1fd08c1888bb1020000')
_CHANNEL_SLOTS = (0x3C7A220,0x1695D04,0x18848C4,0x1884920,0x3D28934,0xC65E3C,0x3D2893A,0x3D289A0)


def _validate(base, read):
    for rva, size, digest in _GUARDS:
        if hashlib.sha256(read(base+rva,size)).hexdigest()!=digest:
            raise ValueError('Native ground-display method changed')
    if read(base+0x14C9ADB,len(_FEED_WRITE))!=_FEED_WRITE:
        raise ValueError('Native ground-display feed layout changed')


def _channel_address(channel, base, read):
    if str(channel.Class.Name)!='JunkReplicationChannel' or int(channel.Class._get_struct_size())!=272:
        raise ValueError('Native loot channel layout changed')
    address=int(channel._get_address())
    table=struct.unpack('<Q',read(address+0x68,8))[0]
    if table!=base+0xB31ADD0 or struct.unpack('<8Q',read(table,64))!=tuple(base+x for x in _CHANNEL_SLOTS):
        raise ValueError('Native loot channel interface changed')
    return address+0x68


def _write_feed(row, expected_identity, flag, read):
    if read(row,4)!=expected_identity:
        raise ValueError('Loot identity changed before display update')
    current=read(row+0x2B1,1)[0]
    C.c_ubyte.from_address(row+0x2B1).value=(current & ~2)|(int(flag)&2)


def suppress(actor, channels):
    from unrealsdk.unreal import WeakPointer
    from .native_loot_sync import locate
    from .loot_junk_diagnostics import _read
    from .shinies import _get_world
    if not actor.HasAuthority() or not bool(actor.bReplicates):
        raise ValueError('Ground-display suppression requires a replicated host pickup')
    base,system,row,token=locate(actor)
    _validate(base,_read)
    interfaces=[_channel_address(channel,base,_read) for channel in channels]
    now=struct.unpack('<f',_read(system+0x30,4))[0]
    if not math.isfinite(now) or now<0:
        raise ValueError('Native loot world time invalid')
    identity=token.to_bytes(4,'little')
    original=_read(row+0x2B1,1)[0]&2
    world=_get_world()
    if world is None:raise ValueError('Native loot world unavailable')
    handle={'reference':WeakPointer(actor),'world':WeakPointer(world),'identity':identity,'feed':original,'base':base,'system':system}
    _write_feed(row,identity,0,_read)
    try:
        leave=C.PYFUNCTYPE(None,C.c_void_p,C.c_uint32,C.c_float)(base+0xC65E3C)
        for interface in interfaces:
            leave(interface,token,now)
    except Exception:
        _write_feed(row,identity,original,_read)
        raise
    return handle


def restore(handle):
    from .native_loot_sync import locate
    from .loot_junk_diagnostics import _read
    from .shinies import _get_world
    actor,world,current=handle['reference'](),handle['world'](),_get_world()
    if (actor is None or world is None or current is None or not actor.HasAuthority()
            or int(world._get_address())!=int(current._get_address())):
        return False
    base,system,row,token=locate(actor)
    if token.to_bytes(4,'little')!=handle['identity']:
        return False
    _validate(base,_read)
    _write_feed(row,handle['identity'],handle['feed'],_read)
    return True


# Work is queued once per item/channel, rather than scanning all pickups per item
# or sending repeated network messages for an already-clean shape.
from collections import deque
import time
_tracked = {}
_pending = deque()
_queued = set()
_world = None
_channels = []
_last_channels = -1.0
_last_tick = 0.0
_failures = 0
_last_error = ''


def _enqueue(address):
    if address not in _queued:
        _queued.add(address)
        _pending.append(address)


def remember(actor):
    global _world
    from unrealsdk.unreal import WeakPointer
    from .shinies import _get_world
    world = _get_world()
    if world is None:
        return
    previous = _world() if _world else None
    if previous is None or int(previous._get_address()) != int(world._get_address()):
        cancel()
        _world = WeakPointer(world)
    address = int(actor._get_address())
    existing = _tracked.get(address)
    if existing is not None and existing['reference']() is not None:
        return
    _tracked[address] = {'reference': WeakPointer(actor), 'handle': None,
                         'deadline': time.monotonic()+30.0, 'channels': set(), 'native_channels': set()}
    _enqueue(address)


def cancel():
    global _world, _channels, _last_channels
    _tracked.clear()
    _pending.clear()
    _queued.clear()
    _world = None
    _channels = []
    _last_channels = -1.0


def restore_all():
    for item in list(_tracked.values()):
        if item['handle'] is not None:
            try:
                restore(item['handle'])
            except Exception:
                pass
    cancel()


def _withdraw(actor, channels, identity):
    from .native_loot_sync import locate
    from .loot_junk_diagnostics import _read
    base, system, row, token = locate(actor)
    if token.to_bytes(4, "little") != identity:
        raise ValueError("Shape native identity changed")
    _validate(base, _read)
    interfaces = [_channel_address(channel, base, _read) for channel in channels]
    now = struct.unpack('<f', _read(system+0x30, 4))[0]
    if not math.isfinite(now) or now < 0:
        raise ValueError('Native loot world time invalid')
    leave = C.PYFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_float)(base+0xC65E3C)
    for interface in interfaces:
        leave(interface, token, now)


def _prime(actor, channels, identity):
    from .native_loot_sync import locate
    from .loot_junk_diagnostics import _read
    base, system, row, token = locate(actor)
    if token.to_bytes(4, "little") != identity:
        raise ValueError("Shape native identity changed")
    _validate(base, _read)
    from .native_loot_sync import notify
    notify(actor)
    interfaces = [_channel_address(channel, base, _read) for channel in channels]
    now = struct.unpack('<f', _read(system+0x30, 4))[0]
    if not math.isfinite(now) or now < 0:
        raise ValueError('Native loot world time invalid')
    leave = C.PYFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_float)(base+0x1695D04)
    for interface in interfaces:
        leave(interface, row, now)


def _retire(item):
    handle = item['handle']
    if handle is None or not item.get('native_channels'):
        return
    from .loot_junk_diagnostics import _read
    base, system = handle['base'], handle['system']
    _validate(base, _read)
    now = struct.unpack('<f', _read(system+0x30, 4))[0]
    if not math.isfinite(now) or now < 0:
        return
    leave = C.PYFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_float)(base+0xC65E3C)
    for reference in _channels:
        channel = reference()
        if channel is not None and int(channel._get_address()) in item['native_channels']:
            interface = _channel_address(channel, base, _read)
            leave(interface, int.from_bytes(handle['identity'], 'little'), now)


def runtime_tick():
    global _last_tick, _last_channels, _channels, _failures, _last_error
    if not _tracked:
        return
    now = time.monotonic()
    if now-_last_tick < 0.05:
        return
    _last_tick = now
    from .shinies import _get_world
    previous, current = _world() if _world else None, _get_world()
    if (previous is None or current is None
            or int(previous._get_address()) != int(current._get_address())):
        cancel()
        return
    if now-_last_channels >= 1.0:
        import unrealsdk
        from unrealsdk.unreal import WeakPointer
        _last_channels = now
        _channels = [WeakPointer(channel) for channel in unrealsdk.find_all('JunkReplicationChannel', False)
                     if 'Default__' not in str(channel)]
        # Late-join channels are handled once; expired shapes do not retain work.
        live_channel_keys = {int(channel._get_address()) for ref in _channels if (channel := ref()) is not None}
        for address, item in list(_tracked.items()):
            actor = item['reference']()
            if actor is None or not actor.HasAuthority():
                try:
                    _retire(item)
                except Exception:
                    pass
                _tracked.pop(address, None)
                continue
            item['channels'].intersection_update(live_channel_keys)
            item['native_channels'].intersection_update(live_channel_keys)
            if not item.get('blocked') and live_channel_keys-item['channels']:
                _enqueue(address)
    for _ in range(min(6, len(_pending))):
        address = _pending.popleft()
        _queued.discard(address)
        item = _tracked.get(address)
        actor = item['reference']() if item else None
        if actor is None:
            _tracked.pop(address, None)
            continue
        try:
            if not actor.HasAuthority():
                _tracked.pop(address, None)
                continue
            if not actor.bReplicates:
                if now < item['deadline']:
                    _enqueue(address)
                else:
                    _tracked.pop(address, None)
                continue
            channels = [channel for ref in _channels if (channel := ref()) is not None
                        and int(channel._get_address()) not in item['channels']]
            if item['handle'] is None:
                item['handle'] = suppress(actor, channels)
            elif channels:
                _prime(actor, channels, item['handle']['identity'])
                item['native_channels'].update(int(channel._get_address()) for channel in channels)
            item['channels'].update(int(channel._get_address()) for channel in channels)
        except Exception as exc:
            # Do not keep retrying an unsupported build/layout on every frame.
            _failures += 1
            if item['handle'] is None:
                _tracked.pop(address, None)
            else:
                item['blocked'] = True
            error = str(exc)
            if error != _last_error:
                _last_error = error
                from .loot_shapes import _log
                _log('Guest shape display update unavailable: '+error)


def status():
    return {'tracked': len(_tracked), 'pending': len(_pending), 'failures': _failures,
            'suppressed': sum(item['handle'] is not None for item in _tracked.values())}
