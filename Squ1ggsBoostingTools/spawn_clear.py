"""Clear explicitly registered SQBT world actors across both spawn backends."""
from __future__ import annotations

import sys
from typing import Any


def clear_registered_spawns(controller: Any) -> dict[str, Any]:
    from . import spawn_deferred, spawn_registry
    from .embedded_oak import engine as oak
    from .world_spawn import is_host
    import unrealsdk

    if not is_host():
        raise RuntimeError("Host / in-world session required to clear tracked spawns")

    player_keys: set[str] = set()
    for pc in unrealsdk.find_all("OakPlayerController", False):
        try:
            pawn = getattr(pc, "Pawn", None)
            if pawn is not None:
                player_keys.add(str(pawn))
        except Exception:
            continue
    if not player_keys:
        raise RuntimeError("Could not safely identify player pawns; tracked-spawn clear was cancelled.")

    from .native_appearance.runtime import CONTROLLER as appearance_controller
    appearance_controller.shutdown()

    cancelled = spawn_deferred.clear_spawn_pending()
    controller._async_spawn = None
    for ui in (controller.ui, getattr(controller, "_async_status_ui", None), getattr(controller, "io_ui", None)):
        if ui is not None:
            ui.spawn_pending = False
            ui.spawn_pending_since = 0.0
    encounter = sys.modules.get(__package__ + ".encounter_builder")
    if encounter is not None:
        encounter.stop({"keep_plan": True})
    oak.cancel_logo_job()
    oak.clear_logo_pins()

    placements = list(oak._SPAWNED)
    mobs = list(controller.tracker.mobs)
    requested = {str(item.actor_key or item.actor) for item in placements}
    requested.update(item.key for item in mobs)
    requested.update(spawn_registry._spawns)
    actors: dict[str, Any] = spawn_registry.live()
    classes = set()
    for item in placements:
        reference = getattr(item, "reference", None)
        if callable(reference):
            actor = reference()
            if actor is not None:
                actors[str(actor)] = actor
        else:
            classes.add(str(item.class_name or "Actor"))
    if mobs:
        classes.update(("OakCharacter", "GbxAICharacter", "Pawn"))
    for name in classes:
        if unrealsdk.find_class(name) is None:
            continue
        for actor in unrealsdk.find_all(name, False):
            key = str(actor)
            if key in requested:
                actors[key] = actor

    protected = set(actors) & player_keys
    failed: set[str] = set()
    destroyed: list[str] = []
    for key, actor in actors.items():
        if key in protected:
            continue
        try:
            if not actor.HasAuthority():
                failed.add(key)
                continue
            if actor.K2_DestroyActor() is False:
                failed.add(key)
                continue
            destroyed.append(key)
        except Exception:
            failed.add(key)
    keep = failed | protected
    oak._SPAWNED[:] = [item for item in placements if str(item.actor_key or item.actor) in keep]
    controller.tracker.mobs[:] = [item for item in mobs if item.key in keep]
    for key in set(spawn_registry._spawns) - keep:
        spawn_registry._spawns.pop(key, None)
    result = {"destroyed": len(destroyed), "failed": len(failed),
              "already_gone": len(requested - set(actors)), "protected_players": len(protected),
              "cancelled": cancelled}
    controller.ui.status_text = (f"Cleared tracked spawns: {result['destroyed']} destroyed, "
                                 f"{result['failed']} failed.")
    return result
