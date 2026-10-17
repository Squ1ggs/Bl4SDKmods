# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 RDPSqu1ggs
# Extracted from SQBT by tools/sync_appearance_core.py; see provenance.json.
from __future__ import annotations
from typing import Any, Optional
import unrealsdk
from unrealsdk import logging
from unrealsdk import find_object

_appearance_shell = {}
_appearance_states = {}

def _appearance_runtime_log(message):
    logging.info("[Squ1ggs Appearance] " + message)

def _call_quiet(obj: Any, name: str, *args: Any) -> bool:
    fn = getattr(obj, name, None) if obj is not None else None
    if not callable(fn):
        return False
    try:
        fn(*args)
        return True
    except Exception:
        return False

def _component_visible(component: Any) -> tuple[bool, bool]:
    visible = True
    hidden = False
    try:
        visible = bool(component.IsVisible())
    except Exception:
        try:
            visible = bool(getattr(component, "bVisible", True))
        except Exception:
            pass
    try:
        hidden = bool(getattr(component, "bHiddenInGame", False))
    except Exception:
        pass
    return visible, hidden

def _set_component_visible(component: Any, visible: bool, hidden: bool = False) -> None:
    try:
        component.SetVisibility(bool(visible), True)
    except Exception:
        pass
    try:
        component.SetHiddenInGame(bool(hidden), True)
    except Exception:
        pass

def _actor_location(actor: Any | None) -> Any | None:
    if actor is None:
        return None
    for name in ("K2_GetActorLocation", "GetActorLocation"):
        try:
            fn = getattr(actor, name, None)
            if callable(fn):
                return fn()
        except Exception:
            pass
    try:
        root = getattr(actor, "RootComponent", None)
        if root is not None:
            return getattr(root, "RelativeLocation", None)
    except Exception:
        pass
    return None

def _actor_label(obj: Any | None) -> str:
    if obj is None:
        return "(none)"
    try:
        name = str(getattr(obj, "Name", "") or "")
    except Exception:
        name = ""
    try:
        cls = str(getattr(getattr(obj, "Class", None), "Name", "") or "")
    except Exception:
        cls = ""
    if name and cls:
        return f"{cls}:{name}"
    return name or cls or repr(obj)

def _appearance_skeletal_components(actor: Any) -> list[Any]:
    try:
        cls = unrealsdk.find_class("SkeletalMeshComponent")
    except Exception:
        return []
    for meth in ("K2_GetComponentsByClass", "GetComponentsByClass"):
        fn = getattr(actor, meth, None)
        if not callable(fn):
            continue
        try:
            return [c for c in list(fn(cls) or []) if c is not None]
        except Exception:
            continue
    return []

def _appearance_mesh_ready(actor: Any, mesh: Any) -> bool:
    """Check readable render prerequisites; this does not prove a rendered frame."""
    if actor is None or mesh is None or bool(getattr(actor, "bHidden", False)):
        return False
    visible, hidden = _component_visible(mesh)
    if not visible or hidden:
        return False
    from . import native_helpers as oak

    if oak._mesh_asset_for_kind(mesh) is None:
        return False
    count = getattr(mesh, "GetNumBones", None)
    if callable(count):
        try:
            if int(count()) <= 0:
                return False
        except Exception:
            return False
    return True

def _apply_worn_source_appearance_legacy(
    pawn: Any,
    player_mesh: Any,
    player_asset: Any,
    source: Any,
    source_mesh: Any,
    source_asset: Any,
    requested: str,
    *, follow_player_pose: bool = False,
) -> str:
    """Restore the local actor attachment used before the animation regression."""
    global _appearance_shell
    root = getattr(pawn, "RootComponent", None)
    if root is None:
        raise RuntimeError("The local player has no root component to carry the model.")
    controller = getattr(source, "Controller", None)
    if not _call_quiet(controller, "UnPossess"):
        _call_quiet(source, "DetachFromControllerPendingDestroy")
    _call_quiet(source, "SetActorEnableCollision", False)
    movement = getattr(source, "CharacterMovement", None)
    _call_quiet(movement, "StopMovementImmediately")
    _call_quiet(movement, "DisableMovement")
    if not _call_quiet(source, "K2_AttachToComponent", root, "None", 2, 2, 1, False):
        raise RuntimeError("The selected model could not be attached to the local player.")
    here, there = _actor_location(pawn), _actor_location(source)
    try:
        offset = abs(float(here.X) - float(there.X)) + abs(float(here.Y) - float(there.Y))
    except Exception:
        offset = 0.0
    if offset > 100.0:
        _call_quiet(source, "K2_DetachFromActor", 1, 1, 1)
        raise RuntimeError("The selected model did not stay on the local player.")
    source_skel = getattr(source_asset, "Skeleton", None)
    player_skel = getattr(player_asset, "Skeleton", None)
    shared_skeleton = source_skel is not None and str(source_skel) == str(player_skel)
    extras = []
    for comp in _appearance_skeletal_components(pawn):
        if str(getattr(comp,"Name","")) == "FirstPersonArms":
            continue
        visible, hidden = _component_visible(comp)
        extras.append({"comp": comp, "asset": None, "materials": [],
                       "visible": visible, "hidden": hidden,
                       "tick_option": getattr(comp, "VisibilityBasedAnimTickOption", None)})
    leader = False
    from .animation import compatible_bones
    if shared_skeleton or (follow_player_pose and compatible_bones(source_mesh, player_mesh)):
        leader = _call_quiet(source_mesh, "SetLeaderPoseComponent", player_mesh, True)
    _call_quiet(source, "SetActorHiddenInGame", False)
    _set_component_visible(source_mesh, True, False)
    if not _appearance_mesh_ready(source, source_mesh):
        _call_quiet(source_mesh, "SetLeaderPoseComponent", None, True)
        _call_quiet(source, "K2_DetachFromActor", 1, 1, 1)
        raise RuntimeError("The selected model has no renderable mesh; your original appearance was kept visible.")
    for row in extras:
        comp = row["comp"]
        try:
            comp.VisibilityBasedAnimTickOption = 0
        except Exception:
            pass
        _call_quiet(comp, "SetVisibility", False, False)
        _call_quiet(comp, "SetHiddenInGame", True, False)
    _appearance_shell = {
        "mode": "worn_source_actor", "shell": source,
        "source_mesh": source_mesh if leader else None,
        "render_mesh": source_mesh,
        "pawn": pawn, "player_mesh": None,
        "source_label": _actor_label(source), "source_code": requested,
        "extras": extras, "scope": "local",
        "animation_driver": "legacy_local",
    }
    _appearance_states[str(pawn)] = _appearance_shell
    _appearance_runtime_log(
        f"legacy local swap — {getattr(source_asset, 'Name', source_asset)}; "
        f"{len(extras)} player parts hidden; source animation left unchanged"
    )
    return f"Local appearance applied from {_actor_label(source)} using the original attachment method."
