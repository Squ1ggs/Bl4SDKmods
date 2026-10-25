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

def _set_component_visible(component: Any, visible: bool, hidden: bool = False, *, propagate: bool = True) -> None:
    try:
        component.SetVisibility(bool(visible), propagate)
    except Exception:
        pass
    try:
        component.SetHiddenInGame(bool(hidden), propagate)
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
            return [c for c in list(fn(cls) or []) if c is not None
                    and not {'SQBT_LocalWeaponArms','SQBT_HeadShadow'}.intersection(str(tag) for tag in (getattr(c,'ComponentTags',()) or ()))]
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

def _passivate_worn_shell(shell: Any, source_mesh: Any | None = None) -> None:
    """Stop AI / capsule movement / root-motion travel; leave mesh anim ticking for pose."""
    if shell is None:
        return
    from .appearance_visibility import make_cosmetic_combat_passive
    make_cosmetic_combat_passive(shell, trusted_cosmetic=True)
    # OakCharacter actor tick can integrate root motion even with movement off —
    # that is what made Apply look like "they walk off" then restore the hunter.
    _call_quiet(shell, "SetActorTickEnabled", False)
    _call_quiet(shell, "SetActorEnableCollision", False)
    controller = getattr(shell, "Controller", None)
    if controller is not None:
        _call_quiet(getattr(controller, "BrainComponent", None), "StopLogic", "Cosmetic appearance")
        _call_quiet(controller, "StopMovement")
        _call_quiet(controller, "SetActorTickEnabled", False)
        if not _call_quiet(controller, "UnPossess"):
            _call_quiet(shell, "DetachFromControllerPendingDestroy")
    try:
        if hasattr(shell, "AutoPossessAI"):
            shell.AutoPossessAI = 0
    except Exception:
        pass
    movement = getattr(shell, "CharacterMovement", None)
    _call_quiet(movement, "StopMovementImmediately")
    _call_quiet(movement, "DisableMovement")
    _call_quiet(movement, "SetComponentTickEnabled", False)
    mesh = source_mesh
    if mesh is None:
        try:
            from . import native_helpers as oak

            mesh = oak._actor_mesh(shell)
        except Exception:
            mesh = None
    if mesh is not None:
        try:
            mesh.VisibilityBasedAnimTickOption = 0
            mesh.bPauseAnims = False
            mesh.bNoSkeletonUpdate = False
        except Exception:
            pass
        _call_quiet(mesh, "SetComponentTickEnabled", True)
        try:
            instance = mesh.GetAnimInstance()
            # IgnoreRootMotion — pose keeps cooking; travel stays on the player capsule.
            _call_quiet(instance, "SetRootMotionMode", 1)
        except Exception:
            pass


def _pin_worn_shell_to_pawn(pawn: Any, shell: Any, source_mesh: Any | None = None) -> bool:
    """Attach shell to player root at 0,0,0 relative and keep it passive."""
    root = getattr(pawn, "RootComponent", None)
    if root is None or shell is None:
        return False
    _passivate_worn_shell(shell, source_mesh)
    if not _call_quiet(shell, "K2_AttachToComponent", root, "None", 2, 2, 1, False):
        return False
    zero = unrealsdk.make_struct("Vector", X=0.0, Y=0.0, Z=0.0)
    shell_root = getattr(shell, "RootComponent", None)
    if shell_root is not None:
        if not _call_quiet(shell_root, "K2_SetRelativeLocation", zero, False, False):
            try:
                shell_root.RelativeLocation = zero
            except Exception:
                pass
    here, there = _actor_location(pawn), _actor_location(shell)
    try:
        if here is None or there is None:
            return False
        if (float(here.X) - float(there.X)) ** 2 + (float(here.Y) - float(there.Y)) ** 2 > 100 ** 2:
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
    if not _pin_worn_shell_to_pawn(pawn, source, source_mesh):
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
    # Mesh anim stays on for pose; actor/AI/movement stay off (see _passivate_worn_shell).
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
        _call_quiet(comp, "SetVisibility", True, False)
        _call_quiet(comp, "SetHiddenInGame", False, False)
        _call_quiet(comp, "SetOwnerNoSee", True)
    from .appearance_visibility import hold_local_visual
    hold_local_visual(source, [row["comp"] for row in extras])
    _appearance_shell = {
        "mode": "worn_source_actor", "shell": source,
        "source_mesh": source_mesh if leader else None,
        "render_mesh": source_mesh,
        "pawn": pawn, "player_mesh": None,
        "source_label": _actor_label(source), "source_code": requested,
        "extras": extras, "scope": "local",
        "animation_driver": "legacy_local",
        "root_relative_xyz": [0.0, 0.0, 0.0],
    }
    _appearance_states[str(pawn)] = _appearance_shell
    _appearance_runtime_log(
        f"legacy local swap — {getattr(source_asset, 'Name', source_asset)}; "
        f"{len(extras)} player parts hidden; source passive (no root-motion travel)"
    )
    return f"Local appearance applied from {_actor_label(source)} using the original attachment method."
