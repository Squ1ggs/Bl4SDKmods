# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 RDPSqu1ggs
# Extracted from SQBT by tools/sync_appearance_core.py; see provenance.json.
from __future__ import annotations
from typing import Any, Optional
import unrealsdk
from unrealsdk import logging
from unrealsdk import find_object

def _log_info(message):
    logging.info("[Squ1ggs Appearance] " + message)

def _log_error(message):
    logging.error("[Squ1ggs Appearance] " + message)

def _log_warn(message):
    logging.warning("[Squ1ggs Appearance] " + message)

def _unwrap(value: Any) -> Any:
    return value[0] if isinstance(value, (list, tuple)) else value

def _actor_mesh(actor: Any) -> Any:
    """ADA-style mesh lookup for non-deployable actors such as OakWeapon."""
    for attr in ("Mesh", "CharacterMesh", "SkeletalMeshComponent", "GbxSkeletalMeshComponent", "MeshComponent"):
        try:
            mesh = getattr(actor, attr, None)
        except Exception:
            mesh = None
        if mesh is not None:
            return mesh
    for cls_path in ("/Script/OakGame.GbxSkeletalMeshComponent", "/Script/Engine.SkeletalMeshComponent"):
        try:
            cls = find_object("Class", cls_path)
            mesh = actor.GetComponentByClass(cls)
        except Exception:
            mesh = None
        if mesh is not None:
            return mesh
    return None

def _mesh_asset_for_kind(mesh: Any) -> Any:
    for attr in ("SkeletalMesh", "SkinnedAsset"):
        try:
            asset = getattr(mesh, attr, None)
        except Exception:
            asset = None
        if asset is not None:
            return asset
    return None

def _copy_actor_data(source: Any, actor: Any) -> None:
    try:
        src_data = getattr(source, "GbxActorData", None)
        dst_data = getattr(actor, "GbxActorData", None)
    except Exception:
        return
    if src_data is None or dst_data is None:
        return

    # This is the critical line from the console one-liner.  Keep it narrow first.
    for field_name in ("GbxActorDef", "ActorPartList", "ActorPartSelections", "SpawnDetails"):
        try:
            value = getattr(src_data, field_name)
        except Exception:
            continue
        try:
            setattr(dst_data, field_name, value)
            _log_info(f"Copied GbxActorData.{field_name}.")
        except Exception:
            pass

def _spawn_actor_deferred(
    gs: Any,
    world: Any,
    cls: Any,
    transform: Any,
    *,
    class_name: str = "Actor",
    source: Optional[Any] = None,
    collision_handling: int = 1,
) -> Optional[Any]:
    """Spawn an actor with the safer ADA deferred-spawn wrapper.

    If a source template is provided, copy its actor data before FinishSpawningActor so
    script/deployable actors initialize with the same data as their live template.
    """
    try:
        raw = gs.BeginDeferredActorSpawnFromClass(world, cls, transform, int(collision_handling), None, 1)
        actor = _unwrap(raw)
    except Exception as exc:
        _log_error(f"BeginDeferredActorSpawnFromClass failed for {class_name}: {exc}")
        return None
    if actor is None:
        _log_error("BeginDeferredActorSpawnFromClass returned None.")
        return None

    if source is not None:
        _copy_actor_data(source, actor)

    try:
        raw2 = gs.FinishSpawningActor(actor, transform, 0)
        return _unwrap(raw2)
    except Exception as exc:
        _log_error(f"FinishSpawningActor failed for {class_name}: {exc}")
        try:
            actor.K2_DestroyActor()
        except Exception:
            pass
        return None
