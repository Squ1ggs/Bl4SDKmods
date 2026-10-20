# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 RDPSqu1ggs
"""Reversible visibility/relevance setup for an actively worn cosmetic actor."""
from __future__ import annotations
from typing import Any
from unrealsdk.unreal import WeakPointer

def _call(obj: Any, method: str, *args: Any) -> bool:
    try:
        getattr(obj, method)(*args)
        return True
    except Exception:
        return False

def prepare_lobby_visibility(state: dict[str, Any]) -> bool:
    source, mesh = state.get("shell"), state.get("render_mesh")
    if source is None or mesh is None:
        return False
    try:
        if not source.HasAuthority() or bool(source.bHidden) or bool(mesh.bHiddenInGame):
            return False
        saved = state.get("lobby_visibility")
        if saved is None:
            saved = {"actor": WeakPointer(source), "mesh": WeakPointer(mesh),
                     "actor_flags": {name: bool(getattr(source, name)) for name in
                                     ("bReplicates", "bReplicateMovement", "bAlwaysRelevant", "bOnlyRelevantToOwner")},
                     "mesh_flags": {name: bool(getattr(mesh, name)) for name in ("bOwnerNoSee", "bOnlyOwnerSee")}}
            pawn = state.get('pawn')
            if pawn is not None:
                owner = getattr(source, 'Owner', None)
                saved['owner'] = WeakPointer(owner) if owner is not None else None
                saved['owner_saved'] = True
            state["lobby_visibility"] = saved
        # These changes apply only to the currently worn source actor.
        if not source.bReplicates and not _call(source, "SetReplicates", True):
            return False
        # The replicated root carries attachment transforms. Separate actor
        # velocity replication would predict an independent walk on clients.
        if source.bReplicateMovement and not _call(source, "SetReplicateMovement", False):
            return False
        pawn = state.get('pawn')
        if pawn is not None:
            parent = getattr(source, 'GetAttachParentActor', None)
            if not callable(parent) or str(parent()) != str(pawn):
                return False
            if str(getattr(source, 'Owner', None)) != str(pawn) and not _call(source, 'SetOwner', pawn):
                return False
            if str(getattr(source, 'Owner', None)) != str(pawn):
                return False
        root = getattr(source, 'RootComponent', None)
        if root is not None:
            if 'root' not in saved:
                saved['root'] = WeakPointer(root)
                saved['root_flags'] = {name: bool(value) for name in
                    ('bReplicates', 'bAbsoluteLocation', 'bAbsoluteRotation', 'bAbsoluteScale')
                    if (value := getattr(root, name, None)) is not None}
            # This component belongs only to the cosmetic; never modify the
            # player's root or physics. Relative transforms follow attachment.
            _call(root, 'SetAbsolute', False, False, False)
            _call(root, 'SetIsReplicated', True)
        source.bAlwaysRelevant = True
        source.bOnlyRelevantToOwner = False
        if mesh.bOwnerNoSee and not _call(mesh, "SetOwnerNoSee", False):
            return False
        if mesh.bOnlyOwnerSee and not _call(mesh, "SetOnlyOwnerSee", False):
            return False
        if not saved.get("updated"):
            _call(source, "FlushNetDormancy")
            _call(source, "ForceNetUpdate")
            saved["updated"] = True
        return bool(source.bReplicates and not source.bReplicateMovement and source.bAlwaysRelevant and not source.bOnlyRelevantToOwner and not source.bHidden
                    and not mesh.bOwnerNoSee and not mesh.bOnlyOwnerSee and not mesh.bHiddenInGame)
    except Exception:
        return False

def restore_lobby_visibility(state: dict[str, Any], *, restore_shadows: bool = True) -> None:
    restore_owner_camera_view(state)
    if restore_shadows:
        restore_shadow_visibility(state)
    saved = state.pop("lobby_visibility", None)
    if saved is None:
        return
    actor, mesh = saved["actor"](), saved["mesh"]()
    root = saved['root']() if saved.get('root') else None
    if root is not None:
        flags = saved['root_flags']
        if 'bReplicates' in flags:
            _call(root, 'SetIsReplicated', flags['bReplicates'])
        if all(name in flags for name in ('bAbsoluteLocation', 'bAbsoluteRotation', 'bAbsoluteScale')):
            _call(root, 'SetAbsolute', *(flags[name] for name in ('bAbsoluteLocation', 'bAbsoluteRotation', 'bAbsoluteScale')))
    if mesh is not None:
        _call(mesh, "SetOwnerNoSee", saved["mesh_flags"]["bOwnerNoSee"])
        _call(mesh, "SetOnlyOwnerSee", saved["mesh_flags"]["bOnlyOwnerSee"])
    if actor is not None:
        if saved.get('owner_saved'):
            reference = saved.get('owner')
            _call(actor, 'SetOwner', reference() if reference is not None else None)
        for name in ("bAlwaysRelevant", "bOnlyRelevantToOwner"):
            try:
                setattr(actor, name, saved["actor_flags"][name])
            except Exception:
                pass
        _call(actor, "SetReplicateMovement", saved["actor_flags"]["bReplicateMovement"])
        _call(actor, "SetReplicates", saved["actor_flags"]["bReplicates"])
        _call(actor, "ForceNetUpdate")


def set_shadow_visibility(state, components, visible, *, group="original"):
    """Keep body shadow flags reversible, including newly rebuilt components."""
    saved = state.setdefault("shadow_visibility", {})
    for component in components:
        if component is None or str(getattr(component, "Name", "")) == "FirstPersonArms":
            continue
        key = group + ":" + str(component)
        if key not in saved:
            values = {attr: bool(value) for attr in ("CastShadow", "bCastHiddenShadow")
                      if (value := getattr(component, attr, None)) is not None}
            saved[key] = (WeakPointer(component), values)
        for attr in saved[key][1]:
            if bool(getattr(component, attr)) != visible:
                method = "SetCastShadow" if attr == "CastShadow" else "SetCastHiddenShadow"
                if not _call(component, method, visible):
                    setattr(component, attr, visible)


def restore_shadow_visibility(state):
    for reference, values in state.pop("shadow_visibility", {}).values():
        component = reference()
        if component is None:
            continue
        for attr, value in values.items():
            method = "SetCastShadow" if attr == "CastShadow" else "SetCastHiddenShadow"
            if not _call(component, method, value):
                try:
                    setattr(component, attr, value)
                except Exception:
                    pass


def restore_owner_camera_view(state):
    saved = state.pop('owner_camera_view', None)
    pc = saved['controller']() if saved else None
    if pc is not None and saved['added']:
        pc.HiddenActors = [actor for actor in list(pc.HiddenActors)
            if actor is not None and str(actor) != saved['source_key']]


def prepare_owner_camera_view(state, pc, pawn, source):
    """Suppress only the local view of a worn head enclosing the camera."""
    import math
    if pc is None or pawn is None or source is None:
        restore_owner_camera_view(state)
        return
    saved = state.get('owner_camera_view')
    if saved is not None and (str(saved['controller']()) != str(pc) or saved['source_key'] != str(source)):
        restore_owner_camera_view(state)
        saved = None
    camera = getattr(pc, 'PlayerCameraManager', None) or getattr(pc, 'CameraManager', None)
    if camera is None:
        restore_owner_camera_view(state)
        return
    mode = str(camera.GetActorCameraMode(pawn) or 'Default')
    location, origin = camera.GetCameraLocation(), pawn.K2_GetActorLocation()
    first_person = mode == 'Default' and math.hypot(float(location.X-origin.X), float(location.Y-origin.Y)) < 90
    if saved is None:
        saved = {'controller': WeakPointer(pc), 'source_key': str(source), 'added': False}
        state['owner_camera_view'] = saved
    entries = [actor for actor in list(pc.HiddenActors) if actor is not None]
    if first_person:
        if not any(str(actor) == str(source) for actor in entries):
            pc.HiddenActors = [*entries, source]
            saved['added'] = True
    elif saved['added']:
        pc.HiddenActors = [actor for actor in entries if str(actor) != str(source)]
        saved['added'] = False
