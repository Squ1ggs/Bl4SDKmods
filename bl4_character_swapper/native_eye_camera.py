"""Local swapped-eye camera, applied after Oak's native camera update.

The detour is restricted to the exact executable audited in
.workspace-temp/camera-native-hook-audit-20261021.json. No game file is patched.
An unknown build, changed entry point, or another detour leaves it disabled.
"""
from __future__ import annotations

import ctypes
import hashlib
import math
from pathlib import Path
import struct
import sys

_BUILD = '9c3afb7dc6a550a6c2e817846cd2c40ff11e066dc6aefeb819f802e6a4c5c3e0'
_RVA = 63785010
_ENTRY = bytes.fromhex('41 57 41 56 41 54 56 57 53 48 81 ec 78 03 00 00 66 44 0f 29 bc 24 60 03 00 00')
# Explicit PE/unwind/entry audit: .workspace-temp/native-build-audit-20261022.json.
# Camera positioning/callback/trampoline behavior is unchanged.
_BUILD_PROFILES = {_BUILD: _RVA,
    "ba75f7c2874b16efb5536a5c0cc28918a03efd3e55d790d2e4db57de0c3a353a": 0x3CD7982}


def verified_camera_rva(digest, executable=None):
    if digest not in _BUILD_PROFILES:
        if executable is None:
            raise RuntimeError('Unverified BL4 executable; native eye correction disabled')
        from . import native_build
        profile=native_build.resolve(executable)
        if profile['sha256']!=digest:
            raise RuntimeError('BL4 executable changed during compatibility check')
        return profile['functions']['camera']['rva']
    return _BUILD_PROFILES[digest]


_SINGLETON = '_sqbt_swapped_eye_native_v1'


def _jump(address):
    # RIP-indirect jump preserves every register, including RAX.
    return b'\xff\x25\x00\x00\x00\x00' + struct.pack('<Q', address)


def _run_original_then_adjust(original, adjust, *args):
    result = original(*args)
    try:
        adjust(*args)
    except Exception:
        # Never call the original twice if the cosmetic correction fails.
        pass
    return result


def eye_position(head, yaw, eye_offset=None):
    """Anatomical eye midpoint when available, with a bounded head fallback."""
    forward, side, height = eye_offset or (8., 0., 12.)
    angle = math.radians(yaw)
    position = (head[0] + forward*math.cos(angle) - side*math.sin(angle),
                head[1] + forward*math.sin(angle) + side*math.cos(angle),
                head[2] + height)
    if not all(math.isfinite(value) for value in position):
        raise ValueError('Nonfinite swapped eye position')
    return position


class NativeEyeCamera:
    def __init__(self):
        self.active = None
        self.installed = False
        self.error = None
        self.checked = False
        self.busy = False
        self.calls = 0
        self.applied = 0

    def install(self):
        if self.checked:
            return self.installed
        self.checked = True
        allocation = None
        patched = False
        try:
            if sys.platform != 'win32' or ctypes.sizeof(ctypes.c_void_p) != 8:
                raise RuntimeError('Native eye camera requires Windows x64')
            from ctypes import wintypes as w
            api = ctypes.WinDLL('kernel32', use_last_error=True)
            signatures = {
                'GetModuleHandleW': ([w.LPCWSTR], ctypes.c_void_p),
                'GetModuleFileNameW': ([ctypes.c_void_p,w.LPWSTR,w.DWORD],w.DWORD),
                'VirtualAlloc': ([ctypes.c_void_p,ctypes.c_size_t,w.DWORD,w.DWORD],ctypes.c_void_p),
                'VirtualProtect': ([ctypes.c_void_p,ctypes.c_size_t,w.DWORD,ctypes.POINTER(w.DWORD)],w.BOOL),
                'VirtualFree': ([ctypes.c_void_p,ctypes.c_size_t,w.DWORD],w.BOOL),
                'GetCurrentProcess': ([],ctypes.c_void_p),
                'FlushInstructionCache': ([ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t],w.BOOL),
            }
            for name,(arguments,result) in signatures.items():
                function=getattr(api,name);function.argtypes=arguments;function.restype=result
            base=api.GetModuleHandleW(None)
            filename=ctypes.create_unicode_buffer(32768)
            length=api.GetModuleFileNameW(base,filename,len(filename))
            if not length or length>=len(filename):
                raise RuntimeError('Cannot identify running executable')
            with Path(filename.value).open('rb') as executable:
                digest=hashlib.file_digest(executable,'sha256').hexdigest()
            target=int(base)+verified_camera_rva(digest,Path(filename.value))
            if ctypes.string_at(target,len(_ENTRY)) != _ENTRY:
                raise RuntimeError('Camera entry differs or is already hooked')
            callback_type=ctypes.WINFUNCTYPE(ctypes.c_int64,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_float)
            code=_ENTRY+_jump(target+len(_ENTRY))
            allocation=api.VirtualAlloc(None,len(code),0x3000,0x04)
            if not allocation:
                raise ctypes.WinError(ctypes.get_last_error())
            ctypes.memmove(allocation,code,len(code))
            prior=w.DWORD()
            if not api.VirtualProtect(allocation,len(code),0x20,ctypes.byref(prior)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.original=callback_type(allocation)
            self.callback=callback_type(lambda *args:_run_original_then_adjust(self.original,self._after,*args))
            replacement=_jump(ctypes.cast(self.callback,ctypes.c_void_p).value).ljust(len(_ENTRY),b'\x90')
            if not api.VirtualProtect(target,len(_ENTRY),0x40,ctypes.byref(prior)):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                ctypes.memmove(target,replacement,len(replacement))
                patched=True
            finally:
                restored=w.DWORD()
                api.VirtualProtect(target,len(_ENTRY),prior.value,ctypes.byref(restored))
            api.FlushInstructionCache(api.GetCurrentProcess(),target,len(_ENTRY))
            self.api=api;self.allocation=allocation;self.target=target
            self.installed=True
        except Exception as exc:
            self.error=str(exc)
            if allocation and not patched:
                api.VirtualFree(allocation,0,0x8000)
        return self.installed

    def _after(self, context, _unused, _delta):
        active=self.active
        if active is None or self.busy:
            return
        self.busy=True
        try:
            self.calls+=1
            camera,pawn,mesh=(active[key]() for key in ('camera','pawn','mesh'))
            if camera is None or pawn is None or mesh is None:
                self.active=None;return
            if int(camera._get_address()) != int(context or 0):
                return
            if (str(camera.ViewTarget.target)!=str(pawn)
                    or str(camera.GetActorCameraMode(pawn))!='Default'
                    or bool(getattr(pawn,'bIsDriving',False))):
                return
            zoom=getattr(pawn,'ZoomState',None)
            if bool(getattr(zoom,'bWantsToZoom',False) or getattr(zoom,'bPendingZoom',False)
                    or int(getattr(zoom,'State',0) or 0)!=0):
                return
            cache=camera.CameraCachePrivate
            old=cache.POV.Location
            before=[float(getattr(old,axis)) for axis in 'XYZ']
            point=mesh.GetSocketLocation(active['head'])
            head=[float(getattr(point,axis)) for axis in 'XYZ']
            yaw=float(cache.POV.Rotation.Yaw)
            desired=eye_position(head,yaw,active.get('eye_offset'))
            if not all(math.isfinite(value) for value in before) or math.dist(before,desired)>150:
                return
            import unrealsdk
            cache.POV.Location=unrealsdk.make_struct('Vector',**dict(zip('XYZ',desired)))
            camera.CameraCachePrivate=cache
            target=camera.ViewTarget
            target.POV.Location=unrealsdk.make_struct('Vector',**dict(zip('XYZ',desired)))
            camera.ViewTarget=target
            actual=camera.GetCameraLocation()
            readback=[float(getattr(actual,axis)) for axis in 'XYZ']
            self.applied+=1
            active['diagnostics'].update(applied=self.applied,before=before,desired=list(desired),
                rendered=readback,readback_error_cm=math.dist(desired,readback),error=None)
        except Exception as exc:
            active['diagnostics']['error']=str(exc)
        finally:
            self.busy=False


def _service():
    service=sys.modules.get(_SINGLETON)
    if service is None:
        service=NativeEyeCamera()
        sys.modules[_SINGLETON]=service
    return service


def hold(saved,camera,pawn,mesh):
    from unrealsdk.unreal import WeakPointer
    service=_service()
    diagnostics=saved.setdefault('native_eye_camera',{})
    if not service.install():
        diagnostics['error']=service.error
        return
    active=service.active
    if active is not None and active['owner'] is saved:
        return
    head=next((name for name in ('Head','head','Bip01_Head','Bip01 Head','mixamorig:Head','head_jnt')
               if int(mesh.GetBoneIndex(name))>=0),None)
    if head is None:
        diagnostics['error']='No head anchor on this rig';return
    offset=None
    for left,right in (('L_Eye','R_Eye'),('Eye_L','Eye_R'),('eye_l','eye_r')):
        try:
            if any(int(mesh.GetBoneIndex(name))<0 for name in (left,right)):
                continue
            center=mesh.GetSocketLocation(head)
            eyes=[mesh.GetSocketLocation(name) for name in (left,right)]
            delta=[sum(float(getattr(eye,axis)) for eye in eyes)/2-float(getattr(center,axis)) for axis in 'XYZ']
            if not 2<math.sqrt(sum(v*v for v in delta))<30:
                continue
            yaw=math.radians(float(camera.GetCameraRotation().Yaw))
            offset=(delta[0]*math.cos(yaw)+delta[1]*math.sin(yaw),
                    -delta[0]*math.sin(yaw)+delta[1]*math.cos(yaw),delta[2])
            break
        except Exception:
            continue
    diagnostics.update(installed=True,eye_bones=offset is not None,head=head,error=None)
    service.active={'owner':saved,'camera':WeakPointer(camera),'pawn':WeakPointer(pawn),
                    'mesh':WeakPointer(mesh),'head':head,'eye_offset':offset,'diagnostics':diagnostics}


def release(saved):
    service=sys.modules.get(_SINGLETON)
    if service is not None and service.active is not None and service.active['owner'] is saved:
        service.active=None
    # Retain executable trampoline/callback for the process lifetime. A disabled
    # correction is pass-through; freeing an in-flight native trampoline is unsafe.
