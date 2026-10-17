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
            state["lobby_visibility"] = saved
        # These changes apply only to the currently worn source actor.
        if not source.bReplicates and not _call(source, "SetReplicates", True):
            return False
        if not source.bReplicateMovement and not _call(source, "SetReplicateMovement", True):
            return False
        source.bAlwaysRelevant = True
        source.bOnlyRelevantToOwner = False
        if mesh.bOwnerNoSee and not _call(mesh, "SetOwnerNoSee", False):
            return False
        if mesh.bOnlyOwnerSee and not _call(mesh, "SetOnlyOwnerSee", False):
            return False
        if not saved.get("updated"):
            _call(source, "ForceNetUpdate")
            saved["updated"] = True
        return bool(source.bReplicates and not source.bOnlyRelevantToOwner and not source.bHidden
                    and not mesh.bOwnerNoSee and not mesh.bOnlyOwnerSee and not mesh.bHiddenInGame)
    except Exception:
        return False

def restore_lobby_visibility(state: dict[str, Any]) -> None:
    saved = state.pop("lobby_visibility", None)
    if saved is None:
        return
    actor, mesh = saved["actor"](), saved["mesh"]()
    if mesh is not None:
        _call(mesh, "SetOwnerNoSee", saved["mesh_flags"]["bOwnerNoSee"])
        _call(mesh, "SetOnlyOwnerSee", saved["mesh_flags"]["bOnlyOwnerSee"])
    if actor is not None:
        for name in ("bAlwaysRelevant", "bOnlyRelevantToOwner"):
            try:
                setattr(actor, name, saved["actor_flags"][name])
            except Exception:
                pass
        _call(actor, "SetReplicateMovement", saved["actor_flags"]["bReplicateMovement"])
        _call(actor, "SetReplicates", saved["actor_flags"]["bReplicates"])
        _call(actor, "ForceNetUpdate")
