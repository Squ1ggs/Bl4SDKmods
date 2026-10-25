"""Read-only, fail-closed relocation of previously audited native functions.

Only reference-address operands may differ. Function length, unwind boundary,
all other instruction bytes and the unique executable-section entry must match.
Runtime callers still check live entry bytes and their own ABI/readback gates.
"""
import hashlib
from importlib.resources import files
import json
import mmap
from pathlib import Path
import struct

_cache = {}


def normalized_body(body, reference):
    if len(body) != reference['size']:
        raise ValueError('Native function length changed')
    result = bytearray(body)
    for offset, size in reference['address_operands']:
        if not 0 <= offset < offset + size <= len(result):
            raise ValueError('Invalid native audit mask')
        result[offset:offset + size] = b'\0' * size
    return bytes(result)


def running_executable():
    import ctypes as c
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleFileNameW.argtypes = [c.c_void_p, c.c_wchar_p, c.c_uint32]
    kernel.GetModuleFileNameW.restype = c.c_uint32
    path = c.create_unicode_buffer(32768)
    length = kernel.GetModuleFileNameW(None, path, len(path))
    if not length or length >= len(path):
        raise RuntimeError('Cannot identify running BL4 executable')
    return Path(path.value)


def resolve(path):
    path = Path(path)
    stat = path.stat(); key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key in _cache:
        return _cache[key]
    references = json.loads(files(__package__).joinpath('data/native_build_reference.json')
                            .read_text(encoding='utf-8'))['functions']
    with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        pe = struct.unpack_from('<I', data, 0x3c)[0]
        if data[:2] != b'MZ' or data[pe:pe+4] != b'PE\0\0':
            raise RuntimeError('Not a Windows BL4 executable')
        machine, count, stamp = struct.unpack_from('<HHI', data, pe+4)
        optional = pe+24
        if machine != 0x8664 or struct.unpack_from('<H', data, optional)[0] != 0x20b:
            raise RuntimeError('Native compatibility requires Windows x64')
        table = optional + struct.unpack_from('<H', data, pe+20)[0]
        sections = []
        for i in range(count):
            row = table + i*40
            _, rva, size, raw = struct.unpack_from('<IIII', data, row+8)
            flags = struct.unpack_from('<I', data, row+36)[0]
            if raw+size > len(data): raise RuntimeError('Invalid PE section')
            sections.append((rva, raw, size, bool(flags & 0x20000000)))
        def offset(rva):
            for va, raw, size, _ in sections:
                if va <= rva < va+size: return raw+rva-va
            raise RuntimeError('Native function outside PE sections')
        pdata, size = struct.unpack_from('<II', data, optional+112+3*8)
        if size % 12: raise RuntimeError('Invalid native unwind directory')
        start = offset(pdata)
        bounds = {a:(b,u) for a,b,u in (struct.unpack_from('<III',data,start+i)
                                      for i in range(0,size,12))}
        found = {}
        for name, reference in references.items():
            entry = bytes.fromhex(reference['entry'])
            matches = []
            for va, raw, length, executable in sections:
                if not executable: continue
                pos = raw
                while True:
                    pos = data.find(entry, pos, raw+length)
                    if pos < 0: break
                    rva = va+pos-raw; end, unwind = bounds.get(rva,(0,0))
                    if end-rva == reference['size'] and unwind:
                        body = data[pos:pos+reference['size']]
                        if hashlib.sha256(normalized_body(body,reference)).hexdigest() == reference['normalized_sha256']:
                            matches.append(dict(rva=rva,entry=data[pos:pos+reference['live_entry_size']].hex()))
                    pos += 1
            if len(matches) != 1:
                raise RuntimeError(f'BL4 {name} layout changed or is ambiguous; native compatibility requires review')
            found[name] = matches[0]
        digest = hashlib.sha256(data).hexdigest()
    result = dict(sha256=digest,stamp=stamp,functions=found,validation='full_normalized_function_and_unwind')
    _cache[key] = result
    return result
