from __future__ import annotations

import ctypes as C

import struct

from typing import Any

_STAMP = 0x6AA81051

_RVA = 0x2840C80

_FINGERPRINT = bytes.fromhex("4157415641554154565755534881ec98010000488b05a6eceb094831e0488984249001000048833a000f84fd0100004d")

_BUILD_PROFILES = {
    _STAMP: (_RVA, _FINGERPRINT),
    0xF38DF04C: (0x283DC80, bytes.fromhex("4157415641554154565755534881ec98010000488b05a69cec094831e0488984249001000048833a000f84fd0100004d")),
}


def verified_loader_rva(stamp, read):
    profile = _BUILD_PROFILES.get(stamp)
    if profile is None:
        raise RuntimeError(f"Imported loader is unsupported on this BL4 build (stamp {stamp:#x})")
    rva, fingerprint = profile
    if read(rva, len(fingerprint)) != fingerprint:
        raise RuntimeError(f"Imported loader entry differs on supported BL4 build {stamp:#x}")
    return rva


_loader: Any = None

_IMPORTED_PREFIXES = ()  # Only verified installed manifests authorize namespaces.

_MATERIAL_PACKAGES = {
    "/Game/Common/Material/Character/M_Character_Skin",
    "/Game/Common/MaterialTemplateLibrary/Character/MI_Template_Char_Mouth",
    "/Game/World/Interactives/Lootables/AmmoChest/OrderAmmoChest/Model/MI_Order_AmmoChest_SkelMesh",
    "/Game/AI/_Shared/Materials/MI_Color_Invisible",
    "/Game/Common/Texture/Proxy/T_Proxy_N",
    "/Game/Common/Texture/Proxy/T_Proxy_Dielectric_C",
}

def is_imported_path(path: str) -> bool:
    if path.startswith('/Game/ImportedCharacters/FirstPersonArms/'):
        from importlib.resources import files
        import json
        rows=json.loads(files(__package__.rsplit('.',1)[0]).joinpath('data/native_first_person_arms.json').read_text(encoding='utf-8'))['definitions']
        return any(row.get('native_bind_verified') is True and (
                   path==row.get('mesh','').split('.',1)[0] or
                   any(path==slot.get('normal_texture','').split('.',1)[0] for slot in row.get('material_slots',[]))) for row in rows)
    if path.startswith(_IMPORTED_PREFIXES):
        return True
    if path.startswith('/Game/ImportedVehicles/'):
        from .imported_vehicles import allow_path
        return allow_path(path)
    from pathlib import Path
    import json
    from . import imported_models
    from .imported_namespaces import valid_record
    if path.startswith(('/Game/ImportedCharacters/DriverSeats/','/Game/ImportedCharacters/MissingImportMotion/')):
        for model_id,row in imported_models.models().items():
            roots=tuple('/Game/ImportedCharacters/'+family+'/'+model_id+'/' for family in ('DriverSeats','MissingImportMotion'))
            if not path.startswith(roots):continue
            for extension in row.get('animation_extensions',[]):
                if any(path==asset.split('.',1)[0] for asset in extension.get('animations',{}).values()) and imported_models.pack_ready(row):
                    return True
        return False
    try:
        from .registry import namespace_records
        records = namespace_records()
        for model_id, record in records.items():
            row = imported_models.models().get(model_id)
            if valid_record(record, row) and path.startswith(record['namespace']) and imported_models.pack_ready(row):
                return True
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return False

def package_path_buffer(name_bytes: bytes) -> Any:
    if len(name_bytes) != 8 or name_bytes == b"\0" * 8:
        raise ValueError("Expected a nonempty, eight-byte cooked package FName")
    # FName + EPackageExtension::Unspecified + zeroed alignment padding.
    return C.create_string_buffer(name_bytes + b"\0" * 24)

class _Loader:
    def __init__(self) -> None:
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.kernel.GetModuleHandleW.argtypes = [C.c_wchar_p]
        self.kernel.GetModuleHandleW.restype = C.c_void_p
        self.kernel.GetCurrentProcess.restype = C.c_void_p
        self.kernel.ReadProcessMemory.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
        self.kernel.ReadProcessMemory.restype = C.c_bool
        self.process = self.kernel.GetCurrentProcess()
        self.base = int(self.kernel.GetModuleHandleW(None) or 0)
        pe = struct.unpack("<I", self.read(self.base + 0x3C, 4))[0]
        stamp = struct.unpack("<I", self.read(self.base + pe + 8, 4))[0]
        try:
            rva = verified_loader_rva(stamp, lambda address, size: self.read(self.base + address, size))
        except RuntimeError:
            from .. import native_build
            profile = native_build.resolve(native_build.running_executable())
            entry = profile['functions']['loader']
            rva = entry['rva']
            expected = bytes.fromhex(entry['entry'])
            if self.read(self.base+rva,len(expected)) != expected:
                raise RuntimeError('Relocated BL4 loader entry is modified in memory; loading disabled')
        self.function = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint32,
                                   C.c_void_p, C.c_void_p, C.c_void_p)(self.base + rva)
        self.validate_loaded_map()

    def read(self, address: int, size: int) -> bytes:
        if not 0x10000 < address < 0x800000000000 or not 0 < size <= 4096:
            raise ValueError("Package-loader read out of range")
        buffer = C.create_string_buffer(size)
        count = C.c_size_t()
        if not self.kernel.ReadProcessMemory(self.process, address, buffer, size, C.byref(count)) or count.value != size:
            raise OSError("Package-loader memory is unreadable")
        return buffer.raw

    def name_bytes(self, package: str) -> bytes:
        import unrealsdk
        token = unrealsdk.make_struct("/Script/CoreUObject.SToken", Name=package)
        if str(token.Name) != package:
            raise RuntimeError("Package FName did not round-trip")
        return self.read(int(token._get_address()) + 4, 8)

    def call(self, package: str) -> int:
        buffer = package_path_buffer(self.name_bytes(package))
        return int(self.function(None, C.byref(buffer), 0, None, None, None) or 0)

    def validate_loaded_map(self) -> None:
        from .dev_tools import _gameplay_pc
        pc = _gameplay_pc()
        obj = getattr(pc, "Pawn", None)
        if obj is None:
            raise RuntimeError("Load an unpaused map before checking the package loader")
        for _ in range(12):
            outer = getattr(obj, "Outer", None)
            if outer is None:
                break
            obj = outer
        if str(obj.Class.Name) != "Package":
            raise RuntimeError("Current map package was not resolved")
        name = str(obj.Name)
        address = int(obj._get_address())
        if not name.startswith("/Game/") or self.name_bytes(name) != self.read(address + 0x18, 8):
            raise RuntimeError("Live map FName layout differs from the inspected build")
        if self.call(name) != address:
            raise RuntimeError("Corrected loader did not return the exact already-loaded map; imported assets were not attempted")

    def load(self, package: str) -> Any:
        if (not is_imported_path(package) and package not in _MATERIAL_PACKAGES) or "." in package or ".." in package:
            raise ValueError("This loader only loads the approved character namespaces and fixed BL4 material templates")
        pointer = self.call(package)
        if not pointer:
            raise RuntimeError(f"The corrected package loader returned no package for {package}")
        import unrealsdk
        obj = unrealsdk.find_object("Package", package)
        if obj is None or int(obj._get_address()) != pointer:
            raise RuntimeError("Loaded package pointer disagrees with the SDK lookup")
        return obj

def load_package(package: str) -> Any:
    global _loader
    if _loader is None:
        _loader = _Loader()
    return _loader.load(package)
