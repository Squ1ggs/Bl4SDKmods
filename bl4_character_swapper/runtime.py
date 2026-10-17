# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 RDPSqu1ggs
"""Appearance-only game-thread controller; no SQBT or boosting dependencies."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
from threading import Lock
from typing import Any, Callable
import time
import json
import hashlib
import sys
from types import ModuleType
from pathlib import Path
import unrealsdk
from unrealsdk.unreal import WeakPointer
from unrealsdk import logging
from mods_base import get_pc, open_in_mod_dir
from . import attachment as attach
from . import native_helpers as native
from .appearance_visibility import prepare_lobby_visibility, restore_lobby_visibility

@dataclass
class Model:
    key: str
    name: str
    group: str
    author: str
    spawn: Callable[[], Any] | None = None
    tick: Callable[[], None] | None = None

@dataclass
class Wear:
    owner: str
    pawn: Any
    source: Any
    model: str
    parts: list
    leader: Any
    pawn_hidden: bool
    hide_changed: bool
    visibility_state: dict
    options: dict = field(default_factory=dict)

class Controller:
    def __init__(self):
        self.models: dict[str, Model] = {}
        self.catalog = []
        self.templates = {}
        self.previews = {}
        self.worn: dict[str, Wear] = {}
        self.pending = None
        self.queue = deque()
        self.lock = Lock()
        self.players = []
        self.status = "Load a map, then choose a character."
        self.last_scan = self.last_tick = 0.0
        self.enabled = False
        self.world_key = ""
        self.world_ref = None
        self.world_index = None
        self.hook = None
        self.clients = set()
        self.spawn_job = None
        self.spawn_request = None
        self.owned_spawners = {}
        self.options = {}
        self.desired = {}
        self.invisible = False
        self.invisible_parts = []
        self.player_keys = {}
        self.player_refs = {}
        self.retries = {}
        self.operation = {"id": 0, "state": "idle", "code": "", "owner": "self", "message": self.status}

    def acquire(self, client):
        if client in self.clients:
            return
        if not self.clients:
            self.load_catalog()
            hooks = unrealsdk.hooks
            kind = getattr(hooks.Type, "POST_UNCONDITIONAL", hooks.Type.POST)
            path, key = "/Script/GbxUIUMG.GbxUIUMGTickWidget:BP_TickWidget", "squ1ggs.native_appearance.v1"
            callback = lambda *_: self.tick()
            if not hooks.add_hook(path, kind, key, callback):
                raise RuntimeError("BL4's appearance game-thread tick could not be registered.")
            self.hook = (path, kind, key, callback)
            self.enabled = True
        self.clients.add(client)

    def release(self, client):
        self.clients.discard(client)
        if self.clients:
            return
        try:
            self.shutdown()
        finally:
            self.enabled = False
            if self.hook:
                unrealsdk.hooks.remove_hook(*self.hook[:3])
                self.hook = None

    def shutdown(self):
        self._cancel_loading()
        with self.lock:
            self.queue.clear()
        self.set_invisible(False)
        for owner in list(self.worn):
            self.restore(owner)
        self.desired.clear()
        self._execute("clear", "", "self")
        for reference in self.owned_spawners.values():
            attach._call_quiet(reference(), "K2_DestroyActor")
        self.owned_spawners.clear()
        self.templates.clear()
        self.players = []
        self.player_keys.clear()
        self.player_refs.clear()
        self.retries.clear()
        self.last_scan = 0.0
        resolution = sys.modules.get(__package__ + ".native_resolution")
        if resolution is not None:
            resolution._LOADED_SPAWN_PACKAGES.clear()
            resolution._FAILED_SPAWN_PACKAGES.clear()

    def _cancel_loading(self):
        if self.spawn_job:
            self.spawn_job.cancel()
        self.spawn_job = self.spawn_request = None
        if self.pending:
            _, _, reference, *_ = self.pending
            actor = reference()
            if actor is not None and not any(str(state.source()) == str(actor) for state in self.worn.values()):
                self._destroy_source(actor)
        self.pending = None

    def _destroy_source(self, actor):
        if actor is None:
            return
        key = str(actor)
        attach._call_quiet(actor, "K2_DestroyActor")
        helper = self.owned_spawners.pop(key, None)
        attach._call_quiet(helper() if helper else None, "K2_DestroyActor")
        for model, reference in list(self.previews.items()):
            if reference() is None or str(reference()) == key:
                self.previews.pop(model, None)

    def load_catalog(self):
        path = Path(__file__).parent / "data/bl4_characters.json"
        with open_in_mod_dir(path, binary=True) as stream:
            self.catalog = json.load(stream)
        for row in self.catalog:
            self.models.setdefault(row["code"], Model(row["code"], row["name"], row["group"], "Gearbox / 2K"))

    def register_model(self, model: Model):
        if not model.author.strip() or not model.key.startswith("pack:") or model.spawn is None:
            raise ValueError("Character packs must provide an author, pack key and spawn callback")
        if model.key in self.models:
            raise ValueError(f"A character pack already registered {model.key}")
        self.models[model.key] = model

    def unregister_model(self, key: str):
        if not key.startswith("pack:"):
            raise ValueError("Only add-on pack models can be unregistered")
        if self.pending and self.pending[0] == key:
            self.pending = None
        for owner, state in list(self.worn.items()):
            if state.model == key:
                self.restore(owner)
        reference = self.previews.pop(key, None)
        actor = reference() if reference else None
        attach._call_quiet(actor, "K2_DestroyActor")
        self.models.pop(key, None)

    def request(self, action: str, *, model: str = "", owner: str = "self", options=None):
        if action not in ("preview", "apply", "restore", "restore_all", "clear"):
            raise ValueError("Unknown appearance action")
        with self.lock:
            if not self.enabled:
                self.status = "Enable BL4 Character Swapper before using its controls."
                return False
            if len(self.queue) >= 8 and action not in ("restore", "restore_all"):
                self.status = "Please wait for the current appearance action."
                return False
            if action in ("apply", "preview") and (self.pending or self.spawn_job or self.queue):
                self.status = "Wait for the current appearance action, or restore to cancel it."
                return False
            self.operation = {"id": self.operation["id"] + 1, "state": "queued", "code": model,
                              "owner": owner, "message": "Queued appearance action."}
            request = (action, model, owner, dict(options or {}),
                       self.player_refs.get(owner), self.world_key, self.operation["id"])
            if action in ("restore", "restore_all"):
                self.queue = deque(row for row in self.queue if action != "restore_all" and row[2] != owner)
                self.queue.appendleft(request)
            else:
                self.queue.append(request)
        self.status = "Queued appearance action."
        return True

    def _pc(self):
        pc = get_pc()
        for attr in ("OriginalControllerRef", "OriginalPlayerController", "OriginalController"):
            original = getattr(pc, attr, None)
            if getattr(original, "Pawn", None) is not None:
                return original
        return pc

    def _world(self):
        from .native_resolution import _world_from_pc
        return _world_from_pc(self._pc())

    def _targets(self):
        pc = self._pc()
        world = self._world()
        game_state = getattr(world, "GameState", None)
        local_ps = getattr(pc, "PlayerState", None)
        local_pawn = getattr(pc, "Pawn", None)
        rows, targets = [], {}
        if local_pawn is not None:
            targets["self"] = local_pawn
            rows.append({"key": "self", "name": "Me"})
        for ps in list(getattr(game_state, "PlayerArray", ()) or ()):
            if local_ps is not None and str(ps) == str(local_ps):
                continue
            pawn = getattr(ps, "PawnPrivate", None)
            if pawn is None:
                continue
            key = str(ps)
            targets[key] = pawn
            rows.append({"key": key, "name": str(getattr(ps, "PlayerNamePrivate", None) or getattr(ps, "PlayerName", None) or "Lobby player")})
        self.players = rows
        self.player_keys = {key: str(pawn) for key, pawn in targets.items()}
        self.player_refs = {key: WeakPointer(pawn) for key, pawn in targets.items()}
        return targets

    def _ready(self, actor):
        try:
            if actor is None or bool(getattr(actor, "bHidden", False)):
                return False
            mesh = native._actor_mesh(actor)
            if mesh is None or native._mesh_asset_for_kind(mesh) is None:
                return False
            visible, hidden = attach._component_visible(mesh)
            return visible and not hidden and int(mesh.GetNumBones()) > 0
        except Exception:
            return False

    def _scan(self, now):
        if now - self.last_scan < 3.0:
            return
        self.last_scan = now
        targets = self._targets()
        excluded = {str(pawn) for pawn in targets.values()}
        excluded.update(str(actor) for reference in self.previews.values() if (actor := reference()) is not None)
        excluded.update(str(actor) for state in self.worn.values() if (actor := state.source()) is not None)
        for key, reference in list(self.previews.items()):
            if reference() is None:
                self.previews.pop(key, None)
        names = {row["code"]: row["name"] for row in self.catalog}
        templates = {}
        for actor in unrealsdk.find_all("Character", False):
            try:
                if "Default__" in str(actor) or str(actor) in excluded or not self._ready(actor):
                    continue
                # Imported actors require their pack's material and animation callbacks.
                if "/Game/ImportedCharacters/" in str(actor.Class):
                    continue
                data = getattr(actor, "GbxActorData", None)
                definition = getattr(data, "GbxActorDef", None)
                code = str(getattr(definition, "_name", "")
                           or getattr(definition, "_experimental_name", "")
                           or getattr(actor.Class, "Name", ""))
                if code not in self.models or not code.startswith("Char_"):
                    continue
                templates.setdefault(code, WeakPointer(actor))
            except Exception:
                continue
        self.templates = templates

    def choices(self):
        return sorted([{"key": key, "name": row.name, "group": row.group, "author": row.author,
                        "availability": "loaded" if key in self.templates or key in self.previews else "load_on_demand"}
                       for key, row in list(self.models.items())],
                      key=lambda row: (row["group"], row["name"].casefold()))

    def _spawn(self, key):
        model = self.models.get(key)
        if model is None:
            raise RuntimeError("That character is not available in this map or an installed pack.")
        pawn = getattr(self._pc(), "Pawn", None)
        if pawn is None or not pawn.HasAuthority():
            raise RuntimeError("The host must create character previews. Load a map first.")
        if model.spawn is not None:
            actor = model.spawn()
        else:
            row = next((row for row in self.catalog if row["code"] == key), None)
            reference = self.templates.get(row.get("spawn_code", key) if row else key)
            template = reference() if reference else None
            if template is None:
                if row is None:
                    raise RuntimeError("The selected native character is not in this catalog.")
                from .native_spawn import NativeSpawn
                self.spawn_job = NativeSpawn(row, pawn, self._world())
                return None
            world = self._world()
            statics = unrealsdk.find_class("GameplayStatics")
            game_state = getattr(statics, "ClassDefaultObject", None)
            if game_state is None:
                raise RuntimeError("No live game state.")
            location, forward = pawn.K2_GetActorLocation(), pawn.GetActorForwardVector()
            transform = unrealsdk.make_struct("Transform")
            transform.Rotation.W = 1.0
            transform.Translation.X = float(location.X) + float(forward.X) * 350.0
            transform.Translation.Y = float(location.Y) + float(forward.Y) * 350.0
            transform.Translation.Z = float(location.Z)
            transform.Scale3D.X = transform.Scale3D.Y = transform.Scale3D.Z = 1.0
            actor = native._spawn_actor_deferred(game_state, world, template.Class, transform, source=template, class_name=key)
        if actor is None:
            raise RuntimeError("BL4 did not create the character preview.")
        attach._call_quiet(actor, "SetReplicates", False)
        attach._call_quiet(actor, "SetActorEnableCollision", False)
        self._make_passive(actor)
        self.previews[key] = WeakPointer(actor)
        return actor

    def _make_passive(self, actor):
        controller = getattr(actor, "Controller", None)
        if not attach._call_quiet(controller, "UnPossess"):
            attach._call_quiet(actor, "DetachFromControllerPendingDestroy")
        movement = getattr(actor, "CharacterMovement", None)
        attach._call_quiet(movement, "StopMovementImmediately")
        attach._call_quiet(movement, "DisableMovement")

    def _apply(self, key, owner, actor):
        targets = self._targets()
        pawn = targets.get(owner)
        if pawn is None:
            raise RuntimeError("The selected player is no longer in this lobby.")
        if str(pawn) == str(actor):
            raise RuntimeError("A player cannot be used as their own replacement character.")
        if owner != "self" and not pawn.HasAuthority():
            raise RuntimeError("Only the host can change a selected lobby player's appearance.")
        if not self._ready(actor):
            raise RuntimeError("The replacement character is not ready to render.")
        source_mesh, player_mesh = native._actor_mesh(actor), native._actor_mesh(pawn)
        source_asset, player_asset = native._mesh_asset_for_kind(source_mesh), native._mesh_asset_for_kind(player_mesh)
        if player_asset is None:
            raise RuntimeError("The original player mesh is not available for restoration.")
        # Restore an existing wearer after validating the replacement. Preserve
        # the same source actor when the user reapplies it.
        old = self.worn.get(owner)
        self.set_invisible(False)
        options = dict(self.options.get(owner, {}))
        self.restore(owner, destroy_source=old is None or str(old.source()) != str(actor), forget=False)
        try:
            message = attach._apply_worn_source_appearance_legacy(pawn, player_mesh, player_asset,
                                                                  actor, source_mesh, source_asset, key,
                                                                  follow_player_pose=bool(options.get("follow_player_pose")))
            state = attach._appearance_shell
            if not state.get("extras") or any(visible and not hidden for visible, hidden in
                    (attach._component_visible(row["comp"]) for row in state["extras"])):
                raise RuntimeError("The original body could not be hidden cleanly; its appearance was restored.")
            parts = [(WeakPointer(row["comp"]), row["visible"], row["hidden"], row.get("tick_option")) for row in state["extras"]]
            hidden = bool(getattr(pawn, "bHidden", False))
            authority = bool(options.get("hide_original_for_lobby")) and bool(pawn.HasAuthority()) and prepare_lobby_visibility(state)
            if authority:
                attach._call_quiet(pawn, "SetActorHiddenInGame", True)
                attach._call_quiet(pawn, "ForceNetUpdate")
            self.worn[owner] = Wear(owner, WeakPointer(pawn), WeakPointer(actor), key, parts,
                                    WeakPointer(source_mesh) if state.get("source_mesh") is not None else None,
                                    hidden, authority, {"lobby_visibility": state.get("lobby_visibility")} if state.get("lobby_visibility") else {}, options)
            self.desired[owner] = (key, options)
            self.status = message
            self.operation.update(state="applied", code=key, owner=owner, message=message)
        except Exception:
            state = attach._appearance_states.get(str(pawn), {})
            for row in state.get("extras", ()):
                attach._set_component_visible(row["comp"], row["visible"], row["hidden"])
                if row.get("tick_option") is not None:
                    row["comp"].VisibilityBasedAnimTickOption = row["tick_option"]
            restore_lobby_visibility(state)
            if 'hidden' in locals():
                attach._call_quiet(pawn, "SetActorHiddenInGame", hidden)
                attach._call_quiet(pawn, "ForceNetUpdate")
            attach._call_quiet(source_mesh, "SetLeaderPoseComponent", None, True)
            attach._call_quiet(actor, "K2_DetachFromActor", 1, 1, 1)
            raise
        finally:
            attach._appearance_states.clear()
            attach._appearance_shell = {}

    def restore(self, owner, *, destroy_source=True, forget=True):
        if forget:
            self.desired.pop(owner, None)
            self.options.pop(owner, None)
            self.retries.pop(owner, None)
        state = self.worn.pop(owner, None)
        if state is None:
            return
        pawn, source = state.pawn(), state.source()
        restore_lobby_visibility(state.visibility_state)
        if pawn is not None and state.hide_changed:
            attach._call_quiet(pawn, "SetActorHiddenInGame", state.pawn_hidden)
            attach._call_quiet(pawn, "ForceNetUpdate")
        for reference, visible, hidden, tick_option in state.parts:
            comp = reference()
            if comp is not None:
                attach._set_component_visible(comp, visible, hidden)
                if tick_option is not None:
                    try:
                        comp.VisibilityBasedAnimTickOption = tick_option
                    except Exception:
                        pass
        leader = state.leader() if state.leader else None
        attach._call_quiet(leader, "SetLeaderPoseComponent", None, True)
        if source is not None:
            attach._call_quiet(source, "K2_DetachFromActor", 1, 1, 1)
            if destroy_source:
                self._destroy_source(source)
        self.status = "Original appearance restored."

    def set_invisible(self, enabled):
        if not enabled:
            for reference, visible, hidden in self.invisible_parts:
                comp = reference()
                if comp is not None:
                    attach._set_component_visible(comp, visible, hidden)
            self.invisible_parts.clear()
            self.invisible = False
            return
        if self.invisible:
            return
        pawn = self._targets().get("self")
        if pawn is None:
            raise RuntimeError("Load your character before hiding its body.")
        actors = [pawn]
        state = self.worn.get("self")
        if state and state.source() is not None:
            actors.append(state.source())
        for actor in actors:
            for comp in attach._appearance_skeletal_components(actor):
                if str(getattr(comp, "Name", "")) == "FirstPersonArms":
                    continue
                visible, hidden = attach._component_visible(comp)
                self.invisible_parts.append((WeakPointer(comp), visible, hidden))
                attach._set_component_visible(comp, False, True)
                current_visible, current_hidden = attach._component_visible(comp)
                if current_visible and not current_hidden:
                    self.set_invisible(False)
                    raise RuntimeError("The body could not be hidden cleanly; its visibility was restored.")
        if not self.invisible_parts:
            raise RuntimeError("No body components are available to hide.")
        self.invisible = True

    def snapshot(self, owner=None):
        owner = owner or self.operation.get("owner", "self")
        state = self.worn.get(owner)
        source = state.source() if state else None
        return {"active": state is not None and source is not None,
                "source": state.model if state else "", "source_code": state.model if state else "",
                "pending": bool(self.pending or self.spawn_job or self.queue),
                "pending_code": self.operation.get("code", ""), "pending_state": self.operation["state"],
                "pending_error": self.operation.get("message", "") if self.operation["state"] == "failed" else "",
                "message": self.status, "operation_id": self.operation["id"],
                "scope": "local", "lobby_verified": False, "invisible": self.invisible,
                "targets": [{"owner": key, "source_code": wear.model} for key, wear in list(self.worn.items())]}

    def _execute(self, action, key, owner):
        if action == "restore_all":
            self._cancel_loading()
            with self.lock:
                self.queue.clear()
            self.set_invisible(False)
            self.desired.clear()
            for target in list(self.worn):
                self.restore(target)
            self.operation.update(state="restored", message=self.status)
        elif action == "restore":
            if (self.pending and self.pending[1] == owner) or (self.spawn_request and self.spawn_request[2] == owner):
                self._cancel_loading()
            if owner == "self":
                self.set_invisible(False)
            self.restore(owner)
            self.operation.update(state="restored", message=self.status)
        elif action == "clear":
            self._cancel_loading()
            worn = {str(actor) for state in self.worn.values() if (actor := state.source()) is not None}
            for code, reference in list(self.previews.items()):
                actor = reference()
                if actor is None or str(actor) not in worn:
                    self._destroy_source(actor)
                    self.previews.pop(code, None)
            self.status = "Unworn previews removed."
            self.operation.update(state="cleared", message=self.status)
        else:
            # Check identity/authority before allocating a source. Never create
            # an orphan preview for a stale selected player.
            target = self._targets().get(owner)
            if target is None:
                raise RuntimeError("The selected player is no longer in this lobby.")
            if owner != "self" and not target.HasAuthority():
                raise RuntimeError("Only the host can change a selected lobby player's appearance.")
            sqbt = sys.modules.get("Squ1ggsBoostingTools.dev_tools")
            if sqbt is not None and (getattr(sqbt, "_appearance_states", {}) or
                                    getattr(sqbt, "_appearance_pending", {}).get("code")):
                raise RuntimeError("Restore SQBT's current appearance before using the standalone swapper.")
            if self.pending or self.spawn_job:
                raise RuntimeError("Wait for the current model to finish loading.")
            reference = self.previews.get(key)
            actor = reference() if reference else None
            if actor is not None and any(str(state.source()) == str(actor) and (action == "preview" or target != owner)
                                         for target, state in self.worn.items()):
                actor = None
            if actor is None:
                worn = {str(state.source()) for state in self.worn.values()}
                unworn = {str(value) for ref in self.previews.values()
                          if (value := ref()) is not None and str(value) not in worn}
                if len(unworn) >= 8:
                    raise RuntimeError("Remove unworn previews before creating another character.")
            actor = actor or self._spawn(key)
            if actor is None and self.spawn_job is not None:
                self.spawn_request = (action, key, owner, WeakPointer(target))
                self.operation.update(state="loading", code=key, owner=owner)
                self.status = self.spawn_job.message
                return
            if action == "preview":
                self.status = "Character preview created beside you."
                self.operation.update(state="preview", message=self.status)
            elif self._ready(actor):
                self._apply(key, owner, actor)
            else:
                self.pending = (key, owner, WeakPointer(actor), time.monotonic() + 25.0, WeakPointer(target))
                self.status = "Waiting for the replacement character to load."
                self.operation.update(state="loading", code=key, owner=owner)

    def tick(self):
        if not self.enabled:
            return
        now = time.monotonic()
        if now - self.last_tick < .05:
            return
        self.last_tick = now
        try:
            world = self._world()
            world_key = str(world)
            world_index = getattr(world, "InternalIndex", None)
            if self.world_key and (world_key != self.world_key or world_index != self.world_index or
                                   (self.world_ref is not None and self.world_ref() is None)):
                self.shutdown()
                self.operation.update(state="cancelled", message="Map changed; original appearances restored.")
                self.status = "Map changed. Choose a character again after loading."
            self.world_key = world_key
            self.world_index = world_index
            self.world_ref = WeakPointer(world) if world is not None else None
            self._scan(now)
            worn_keys = {str(actor) for state in self.worn.values() if (actor := state.source()) is not None}
            for reference in self.previews.values():
                actor = reference()
                if actor is not None and str(actor) not in worn_keys and getattr(actor, "Controller", None) is not None:
                    self._make_passive(actor)
            targets = self._targets()
            # Cleanup requests preempt a loader even if its actor becomes
            # ready on this very tick. Never apply a just-cancelled source.
            with self.lock:
                cleanup = self.queue.popleft() if self.queue and self.queue[0][0] in ("restore", "restore_all", "clear") else None
            if cleanup:
                action, key, owner, _, _, _, operation_id = cleanup
                self.operation.update(id=operation_id, code=key, owner=owner)
                self._execute(action, key, owner)
            known_sources = {str(actor) for state in self.worn.values() if (actor := state.source()) is not None}
            known_sources.update(str(actor) for reference in self.previews.values() if (actor := reference()) is not None)
            for key, reference in list(self.owned_spawners.items()):
                if key not in known_sources:
                    attach._call_quiet(reference(), "K2_DestroyActor")
                    self.owned_spawners.pop(key, None)
            for owner, state in list(self.worn.items()):
                pawn, source = state.pawn(), state.source()
                current = targets.get(owner)
                if current is None or source is None:
                    self.restore(owner, forget=not state.options.get("keep_on_respawn", True))
                    continue
                if pawn is None or str(pawn) != str(current):
                    self.restore(owner, destroy_source=False, forget=False)
                    self.options[owner] = state.options
                    self._apply(state.model, owner, source)
                    continue
                if self.invisible and owner == "self":
                    continue
                # Restore a hidden shell on vehicle exit before deciding that
                # its body failed. Never hide a wearer behind an unusable model.
                mesh = native._actor_mesh(source)
                attach._call_quiet(source, "SetActorHiddenInGame", False)
                if mesh is not None:
                    attach._set_component_visible(mesh, True, False)
                if not self._ready(source):
                    self.restore(owner, forget=not state.options.get("keep_on_respawn", True))
                    self.status = "Replacement unavailable; original body restored."
                    continue
                existing = {str(comp) for ref, *_ in state.parts if (comp := ref()) is not None}
                for comp in attach._appearance_skeletal_components(pawn):
                    if str(getattr(comp, "Name", "")) == "FirstPersonArms":
                        continue
                    if str(comp) not in existing:
                        visible, hidden = attach._component_visible(comp)
                        state.parts.append((WeakPointer(comp), visible, hidden, getattr(comp, "VisibilityBasedAnimTickOption", None)))
                    attach._call_quiet(comp, "SetVisibility", False, False)
                    attach._call_quiet(comp, "SetHiddenInGame", True, False)
            if self.pending:
                key, owner, reference, deadline, target_key = self.pending
                actor = reference()
                current = targets.get(owner)
                expected = target_key() if callable(target_key) else target_key
                if actor is None or now > deadline or current is None or expected is None or str(current) != str(expected):
                    self.pending = None
                    self._destroy_source(actor)
                    self.status = "The replacement did not load. Your current appearance was kept."
                    self.operation.update(state="failed", message=self.status)
                elif self._ready(actor):
                    self.pending = None
                    self._apply(key, owner, actor)
            if self.spawn_job:
                action, key, owner, expected = self.spawn_request
                target = targets.get(owner)
                original = expected()
                if target is None or original is None or str(target) != str(original):
                    raise RuntimeError("Character loading cancelled because the selected player changed.")
                local_pawn = self.spawn_job.pawn()
                if local_pawn is None or str(local_pawn) != str(targets.get("self")):
                    raise RuntimeError("Character loading cancelled because the host respawned.")
                actor = self.spawn_job.step(world)
                self.status = self.spawn_job.message
                if actor is not None:
                    self._make_passive(actor)
                    attach._call_quiet(actor, "SetActorEnableCollision", False)
                    if self._ready(actor):
                        helper = self.spawn_job.detach()
                        if helper is not None:
                            self.owned_spawners[str(actor)] = helper
                        self.spawn_job = self.spawn_request = None
                        self.previews[key] = WeakPointer(actor)
                        attach._call_quiet(actor, "SetReplicates", False)
                        if action == "apply":
                            self._apply(key, owner, actor)
                        else:
                            self.status = "Character preview created beside you."
                            self.operation.update(state="preview", message=self.status)
            callbacks = {model.tick for model in self.models.values() if model.tick is not None}
            for callback in callbacks:
                callback()
            with self.lock:
                request = self.queue.popleft() if self.queue else None
            if request:
                action, key, owner, options, target_ref, requested_world, operation_id = request
                if action in ("preview", "apply"):
                    target = targets.get(owner)
                    expected = target_ref() if target_ref else None
                    if requested_world != self.world_key or expected is None or target is None or str(target) != str(expected):
                        raise RuntimeError("Appearance action cancelled because its player or map changed.")
                self.operation.update(id=operation_id, code=key, owner=owner)
                self.options[owner] = options
                self._execute(action, key, owner)
            # Respawn/source recovery is bounded, uses the original model ID,
            # and never follows a newly selected UI target.
            if not self.pending and not self.spawn_job and not self.queue:
                for owner, (key, options) in list(self.desired.items()):
                    if owner in self.worn or owner not in targets:
                        continue
                    attempt, last = self.retries.get(owner, (0, 0.0))
                    if attempt >= 3 or now - last < 10.0:
                        continue
                    self.retries[owner] = (attempt + 1, now)
                    self.options[owner] = options
                    self._execute("apply", key, owner)
                    break
        except Exception as exc:
            self._cancel_loading()
            self.status = str(exc)
            self.operation.update(state="failed", message=self.status)
            logging.error("[Squ1ggs Appearance] " + self.status)

REGISTRY_KEY = "_squ1ggs_native_appearance_service_v1"
_digest = hashlib.sha256()
for _relative in ("runtime.py", "native_spawn.py", "native_helpers.py", "native_resolution.py", "attachment.py",
                  "appearance_visibility.py", "animation.py", "data/bl4_characters.json"):
    with open_in_mod_dir(Path(__file__).parent / _relative, binary=True) as _stream:
        _digest.update(_relative.encode("utf-8") + b"\0" + _stream.read())
_fingerprint = _digest.hexdigest()
_service = sys.modules.get(REGISTRY_KEY)
if _service is None:
    _service = ModuleType(REGISTRY_KEY)
    _service.api = 1
    _service.fingerprint = _fingerprint
    _service.controller = Controller()
    sys.modules[REGISTRY_KEY] = _service
if getattr(_service, "api", None) != 1 or getattr(_service, "fingerprint", None) != _fingerprint:
    raise RuntimeError("A different native Appearance runtime is loaded. Restart BL4 after updating.")
CONTROLLER = _service.controller

def register_model(model: Model):
    CONTROLLER.register_model(model)

def unregister_model(key: str):
    CONTROLLER.unregister_model(key)
