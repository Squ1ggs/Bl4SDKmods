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
from .appearance_visibility import prepare_lobby_visibility, restore_lobby_visibility, set_shadow_visibility

@dataclass
class Model:
    key: str
    name: str
    group: str
    author: str
    spawn: Callable[[], Any] | None = None
    tick: Callable[[], None] | None = None
    apply_enabled: bool = True
    game: str = 'Borderlands 4'
    role: str = ''

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
            from .packs import manager
            manager.activate(self)
            hooks = unrealsdk.hooks
            kind = getattr(hooks.Type, "POST_UNCONDITIONAL", hooks.Type.POST)
            key = "squ1ggs.native_appearance.v1"
            path = "/Script/GbxUIUMG.GbxUIUMGTickWidget:BP_TickWidget"
            callback = lambda *_: self._tick_unpaused()
            if not hooks.add_hook(path, kind, key, callback):
                raise RuntimeError(
                    "BL4's appearance game-thread tick could not be registered "
                    "(" + path + "). Restart BL4 after updating the game, PythonSDK, "
                    "and both Character/Vehicle Swapper mods. If it persists, share "
                    "the SDK log and installed versions; a conflicting hook or "
                    "incompatible game/SDK version may be responsible."
                )
            self.hook = (path, kind, key, callback)
            self.enabled = True
        self.clients.add(client)

    def _tick_unpaused(self):
        pc = self._pc()
        if pc is not None:
            library = unrealsdk.find_class('GameplayStatics')
            if library is not None and library.ClassDefaultObject.IsGamePaused(pc):
                return
        self.tick()

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
        from .packs import manager
        try:
            manager.cleanup()
        except Exception as exc:
            logging.error('[Squ1ggs Appearance packs] Cleanup: ' + str(exc))
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
        getattr(self, '_visual_scan_after', {}).pop(key, None)
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
            self.models.setdefault(row["code"], Model(row["code"], row["name"], row["group"], "Gearbox / 2K",
                                                     role='Vault Hunter' if row['group'] == 'Vault Hunters' else 'Character'))

    def register_model(self, model: Model):
        if not model.author.strip() or not model.key.startswith("pack:") or model.spawn is None:
            raise ValueError("Character packs must provide an author, pack key and spawn callback")
        if model.key in self.models:
            raise ValueError(f"A character pack already registered {model.key}")
        if model.game == 'Borderlands 4':
            from .packs.catalog import game_family
            model.game = game_family(model.group)
        self.models[model.key] = model

    def unregister_model(self, key: str):
        if not key.startswith("pack:"):
            raise ValueError("Only add-on pack models can be unregistered")
        if self.pending and self.pending[0] == key:
            self._cancel_loading()
        with self.lock:
            self.queue = deque(row for row in self.queue if row[1] != key)
        for owner, (model, _) in list(self.desired.items()):
            if model == key:
                self.desired.pop(owner, None)
        for owner, state in list(self.worn.items()):
            if state.model == key:
                self.restore(owner)
        reference = self.previews.pop(key, None)
        actor = reference() if reference else None
        attach._call_quiet(actor, "K2_DestroyActor")
        self.models.pop(key, None)

    def request(self, action: str, *, model: str = "", owner: str = "self", options=None):
        if action not in ("preview", "apply", "restore", "restore_all", "clear", "toggle_camera"):
            raise ValueError("Unknown appearance action")
        if action == 'apply' and model in self.models and not self.models[model].apply_enabled:
            self.status = 'This pack is preview-only; applying it has not been validated.'
            return False
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
                       self.player_refs.get(owner), self.world_key or str(self._world()), self.operation["id"])
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

    def _character_target(self, owner, candidate):
        # Vehicle possession changes Controller.Pawn. Keep the still-live
        # character that owns this swap instead of wearing the car or dropping
        # the cosmetic during the mount transition.
        if candidate is not None and (getattr(candidate, "VehicleMesh", None) is not None
                or "vehicle" in str(getattr(getattr(candidate, "Class", None), "Name", "")).lower()):
            state = self.worn.get(owner)
            retained = state.pawn() if state else None
            if retained is not None and getattr(retained, "CharacterMovement", None) is not None:
                return retained
        return candidate

    def _targets(self):
        pc = self._pc()
        world = self._world()
        game_state = getattr(world, "GameState", None)
        local_ps = getattr(pc, "PlayerState", None)
        local_pawn = self._character_target("self", getattr(pc, "Pawn", None))
        rows, targets = [], {}
        if local_pawn is not None:
            targets["self"] = local_pawn
            rows.append({"key": "self", "name": "Me"})
        for ps in list(getattr(game_state, "PlayerArray", ()) or ()):
            if local_ps is not None and str(ps) == str(local_ps):
                continue
            key = str(ps)
            pawn = self._character_target(key, getattr(ps, "PawnPrivate", None))
            if pawn is None:
                continue
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
            for state in self.worn.values():
                if state.source() is None or str(state.source()) != str(actor):
                    continue
                saved = state.visibility_state.get('native_motion_clip', {})
                if 'proxy' not in saved or saved.get('proxy_visible') is not True:
                    continue
                proxy = saved['proxy']()
                if (proxy is None or saved['mesh']() is None
                        or str(saved['mesh']()) != str(mesh)
                        or str(proxy.GetOwner()) != str(actor)
                        or str(proxy.GetAttachParent()) != str(mesh.GetAttachParent())
                        or str(native._mesh_asset_for_kind(proxy)) != str(native._mesh_asset_for_kind(mesh))):
                    return False
                visible, hidden = attach._component_visible(proxy)
                return visible and not hidden and int(proxy.GetNumBones()) > 0
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
                        "apply_enabled": row.apply_enabled,
                        "game": row.game, "role": row.role,
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
            transform = native._preview_spawn_transform(pawn)
            actor = native._spawn_actor_deferred(game_state, world, template.Class, transform, source=template, class_name=key)
        if actor is None:
            raise RuntimeError("BL4 did not create the character preview.")
        attach._call_quiet(actor, "SetReplicates", False)
        attach._call_quiet(actor, "SetActorEnableCollision", False)
        self._make_passive(actor)
        self.previews[key] = WeakPointer(actor)
        return actor

    def _make_passive(self, actor):
        from .appearance_visibility import make_cosmetic_combat_passive
        make_cosmetic_combat_passive(actor, trusted_cosmetic=True)
        # OakCharacter's actor tick can integrate animation/root movement even
        # with its CharacterMovement component disabled. Mesh ticks remain on.
        controller = getattr(actor, "Controller", None)
        if controller is not None:
            attach._call_quiet(getattr(controller, "BrainComponent", None), "StopLogic", "Cosmetic appearance")
            attach._call_quiet(controller, "StopMovement")
            attach._call_quiet(controller, "SetActorTickEnabled", False)
        try:
            if hasattr(actor, "AutoPossessAI"):
                actor.AutoPossessAI = 0
        except Exception:
            pass
        if not attach._call_quiet(controller, "UnPossess"):
            attach._call_quiet(actor, "DetachFromControllerPendingDestroy")
        movement = getattr(actor, "CharacterMovement", None)
        attached_motion = any((state.visibility_state.get('native_attached_driver')
            or state.visibility_state.get('native_frame_driver',{}).get('phase') == 'active')
            and state.source() is not None and str(state.source())==str(actor)
            and state.pawn() is not None and str(actor.GetAttachParentActor())==str(state.pawn())
            and not state.visibility_state.get('native_seat_clip')
            for state in self.worn.values())
        controlled_follow = any(
            state.visibility_state.get('network_follow_trial') is True
            and state.visibility_state.get('passive_locomotion_trial') is True
            and state.source() is not None and str(state.source()) == str(actor)
            and state.pawn() is not None and str(state.pawn()) != str(actor)
            and str(getattr(actor, 'Owner', None)) == str(state.pawn())
            and actor.GetAttachParentActor() is None
            for state in self.worn.values())
        cache_tick = (controlled_follow and float(getattr(actor,'AnimRootMotionTranslationScale',1.0)) == 0.0
            and any(state.visibility_state.get('native_actor_cache_trial') is True
                    and not state.visibility_state.get('native_seat_clip')
                    and not state.visibility_state.get('native_motion_clip')
                    and state.source() is not None and str(state.source()) == str(actor)
                    for state in self.worn.values()))
        worn_on_player = False
        try:
            parent = actor.GetAttachParentActor()
            worn_on_player = parent is not None and str(parent) != str(actor) and bool(parent.IsPlayerControlled())
        except Exception:
            worn_on_player = False
        # A worn body can still walk and aim while its actor tick is on.
        # The mesh keeps animating. The player attachment owns travel.
        if worn_on_player:
            attach._call_quiet(actor, 'SetActorTickEnabled', False)
            attach._call_quiet(movement, "StopMovementImmediately")
            attach._call_quiet(movement, "DisableMovement")
            attach._call_quiet(movement, "SetComponentTickEnabled", False)
        else:
            attach._call_quiet(actor,'SetActorTickEnabled',cache_tick or attached_motion)
            if not controlled_follow and not attached_motion:
                attach._call_quiet(movement, "StopMovementImmediately")
                attach._call_quiet(movement, "DisableMovement")
            attach._call_quiet(movement, "SetComponentTickEnabled", attached_motion)

        mesh = native._actor_mesh(actor)
        if mesh is not None:
            for name, value in (('VisibilityBasedAnimTickOption', 0), ('bPauseAnims', False), ('bNoSkeletonUpdate', False)):
                try:
                    setattr(mesh, name, value)
                except Exception:
                    pass
            attach._call_quiet(mesh, 'SetComponentTickEnabled', True)
            try:
                instance = mesh.GetAnimInstance()
                # IgnoreRootMotion extracts source motion from the pose but
                # discards its movement. The player's attachment owns travel.
                attach._call_quiet(instance, 'SetRootMotionMode', 1)
            except Exception:
                pass
        # A cloned NPC can carry arena/ability VFX and lights. They do not
        # belong to its cosmetic body and can obscure the entire camera.
        cache = getattr(self, '_visual_scan_after', {})
        now = time.monotonic()
        if now >= cache.get(str(actor), 0):
            for kind in ('NiagaraComponent', 'ParticleSystemComponent', 'DecalComponent', 'WidgetComponent', 'PointLightComponent', 'SpotLightComponent'):
                try:
                    cls = unrealsdk.find_class(kind)
                    if cls is None:
                        continue
                    parts = actor.K2_GetComponentsByClass(cls)
                    for component in list(parts or ())[:128]:
                        if str(component.GetOwner()) == str(actor):
                            attach._call_quiet(component, 'Deactivate')
                            attach._call_quiet(component, 'SetVisibility', False, False)
                            attach._call_quiet(component, 'SetHiddenInGame', True, False)
                except Exception:
                    continue
            cache[str(actor)] = now + .5
            self._visual_scan_after = cache

    def _sync_network_follow(self, state, pawn, source):
        """Follow only this exact owned native cosmetic; never move a player."""
        self.last_binding_observation={'follow_initializing':True,'model':state.model,'pawn':str(pawn),'saved_pawn':str(state.pawn()),
            'source':str(source),'saved_source':str(state.source()),'owner':str(getattr(source,'Owner',None)),
            'controller':str(getattr(source,'Controller',None)),'authority':bool(pawn.HasAuthority())}
        if (not state.model.startswith('Char_') or state.pawn() is None or state.source() is None
                or str(state.pawn()) != str(pawn) or str(state.source()) != str(source) or str(source)==str(pawn)
                or not pawn.HasAuthority() or str(getattr(source,'Owner',None)) != str(pawn)
                or getattr(source,'Controller',None) is not None):
            return False
        parent = source.GetAttachParentActor()
        if parent is not None:
            if str(parent) != str(pawn): return False
            try: source.K2_DetachFromActor(1,1,1)
            except Exception as exc:
                self.last_binding_observation['detach_error']=str(exc)
                return False
        try:
            source.K2_SetActorLocation(NewLocation=pawn.K2_GetActorLocation(),bSweep=False,
                SweepHitResult=unrealsdk.make_struct('HitResult'),bTeleport=True)
            source.K2_SetActorRotation(NewRotation=pawn.K2_GetActorRotation(),bTeleportPhysics=True)
            return True
        except Exception as exc:
            self.last_binding_observation = {'network_follow_error':str(exc),'source':str(source)}
            return False

    def _source_is_bound(self, source, pawn):
        """Observe only our cosmetic source; restore instead of chasing a loose NPC."""
        self.last_binding_observation = {
            "source": str(source), "pawn": str(pawn),
            "controller": str(getattr(source, "Controller", None)),
            "parent": str(source.GetAttachParentActor()) if callable(getattr(source, "GetAttachParentActor", None)) else None,
            "source_location": str(source.K2_GetActorLocation()) if callable(getattr(source, "K2_GetActorLocation", None)) else None,
            "pawn_location": str(pawn.K2_GetActorLocation()) if callable(getattr(pawn, "K2_GetActorLocation", None)) else None,
        }
        if getattr(source, "Controller", None) is not None:
            return False
        parent = getattr(source, "GetAttachParentActor", None)
        if callable(parent):
            try:
                if str(parent()) != str(pawn):
                    follows = parent() is None and str(getattr(source,'Owner',None)) == str(pawn) and any(
                        state.source() is not None and state.pawn() is not None and str(state.source()) == str(source) and str(state.pawn()) == str(pawn) and state.visibility_state.get('network_follow_trial') is True
                        for state in self.worn.values())
                    if not follows: return False
            except Exception:
                return False
        source_location = getattr(source, "K2_GetActorLocation", None)
        pawn_location = getattr(pawn, "K2_GetActorLocation", None)
        if callable(source_location) and callable(pawn_location):
            try:
                a, b = source_location(), pawn_location()
                if (float(a.X) - float(b.X)) ** 2 + (float(a.Y) - float(b.Y)) ** 2 > 100 ** 2:
                    return False
            except Exception:
                return False
        return True

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
        if not (key.startswith('pack:') or key.startswith('Char_Imported')):
            from .native_seating import require_motion_support
            require_motion_support(source_mesh)
        # Restore an existing wearer after validating the replacement. Preserve
        # the same source actor when the user reapplies it.
        old = self.worn.get(owner)
        options = dict(self.options.get(owner, {}))
        if options.get('hide_original_for_lobby') and not pawn.HasAuthority():
            raise RuntimeError('The lobby host must apply a shared BL4 character swap. Your original appearance was kept.')
        self.set_invisible(False)
        self.restore(owner, destroy_source=old is None or str(old.source()) != str(actor), forget=False)
        try:
            self._make_passive(actor)
            if key.startswith('pack:installed:'):
                # Prepared imported actors use their own matching animation clips.
                options['follow_player_pose'] = False
            message = attach._apply_worn_source_appearance_legacy(pawn, player_mesh, player_asset,
                                                                  actor, source_mesh, source_asset, key,
                                                                  follow_player_pose=bool(options.get("follow_player_pose")))
            state = attach._appearance_shell
            if not self._source_is_bound(actor, pawn):
                raise RuntimeError("The model did not stay attached to your player; original appearance restored.")
            # The local-only SDK picker does not enable lobby replication.
            # Animation/weapon ownership must not depend on that optional mode.
            from .appearance_visibility import prepare_local_cosmetic_owner
            prepare_local_cosmetic_owner(state, pawn, actor)
            if not state.get("extras") or any(
                    not bool(getattr(comp, 'bOwnerNoSee', False)) and visible and not hidden
                    for comp, visible, hidden in (
                        (row["comp"], *attach._component_visible(row["comp"])) for row in state["extras"])):
                raise RuntimeError("The original body could not be hidden cleanly; its appearance was restored.")
            set_shadow_visibility(state, [row["comp"] for row in state["extras"]], False)
            set_shadow_visibility(state, [source_mesh], True, group="replacement")
            parts = [(WeakPointer(row["comp"]), row["visible"], row["hidden"], row.get("tick_option")) for row in state["extras"]]
            hidden = bool(getattr(pawn, "bHidden", False))
            authority = bool(options.get("hide_original_for_lobby")) and bool(pawn.HasAuthority()) and prepare_lobby_visibility(state)
            if options.get('hide_original_for_lobby') and pawn.HasAuthority() and not authority:
                raise RuntimeError('The replacement could not enable lobby attachment replication. Original appearance restored.')
            if authority:
                from .appearance_visibility import prepare_original_body_visibility
                if not prepare_original_body_visibility(state,pawn,[row['comp'] for row in state['extras']]):
                    raise RuntimeError('Original body visibility could not replicate; appearance restored.')
                # Hiding the parent actor suppresses its attached native shell
                # on remote viewers. Hide only the original body components.
                attach._call_quiet(pawn, "SetActorHiddenInGame", False)
                if bool(getattr(pawn, 'bHidden', False)):
                    raise RuntimeError('The selected player actor could not remain visible for the lobby. Original appearance restored.')
                attach._call_quiet(pawn, "ForceNetUpdate")
                attach._call_quiet(actor, 'SetActorHiddenInGame', False)
                attach._set_component_visible(source_mesh, True, False)
                attach._call_quiet(actor, 'FlushNetDormancy')
                attach._call_quiet(actor, 'ForceNetUpdate')
                message += ' Lobby attachment and original body component hiding enabled.'
            self.worn[owner] = Wear(owner, WeakPointer(pawn), WeakPointer(actor), key, parts,
                                    WeakPointer(source_mesh) if state.get("source_mesh") is not None else None,
                                    hidden, authority, {name: state[name] for name in ("lobby_visibility", "shadow_visibility", "original_body_visibility", "local_cosmetic_owner") if name in state}, options)
            if authority and key.startswith('Char_') and not key.startswith('Char_Imported'):
                self.worn[owner].visibility_state.update(getattr(self,'_native_motion_session',{}))
            self.desired[owner] = (key, options)
            self.status = message
            self.operation.update(state="applied", code=key, owner=owner, message=message)
            logging.info(f'[Squ1ggs Appearance] applied model={key} target={owner} pawn={pawn} source={actor} lobby={authority}')
        except Exception:
            state = attach._appearance_states.get(str(pawn), {})
            for row in state.get("extras", ()):
                attach._set_component_visible(row["comp"], row["visible"], row["hidden"])
                if row.get("tick_option") is not None:
                    row["comp"].VisibilityBasedAnimTickOption = row["tick_option"]
            restore_lobby_visibility(state)
            from .appearance_visibility import restore_local_cosmetic_owner
            restore_local_cosmetic_owner(state)
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
        # Restore may fail during a native mode transition. Retain ownership
        # and its snapshots until cleanup succeeds so it remains retryable.
        state = self.worn.get(owner)
        if state is None:
            return
        pawn, source = state.pawn(), state.source()
        if (state.visibility_state.get('native_weapon_preview') or state.visibility_state.get('native_weapon_pose')
                or state.visibility_state.get('viewmodel_arms')):
            from . import native_weapon
            native_weapon.restore(state.visibility_state)
            pose = state.visibility_state.pop('native_weapon_pose', None)
            if pose is not None:
                native_weapon._restore_combat_inputs(pose)
            native_weapon.release_viewmodel_arms(state.visibility_state)
        from .animation import restore_vehicle_inputs, restore_worn_animation
        restore_vehicle_inputs(state.visibility_state)
        restore_worn_animation(state.visibility_state)
        restore_lobby_visibility(state.visibility_state)
        from .appearance_visibility import restore_local_cosmetic_owner
        restore_local_cosmetic_owner(state.visibility_state)
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
        self.worn.pop(owner, None)
        self.status = "Original appearance restored."

    def _restore_injured_wearer(self, owner, state):
        """Never leave an NPC cosmetic alive across the player's downed state."""
        try:
            self.restore(owner, forget=True)
        except Exception as exc:
            # A failed cosmetic cleanup must not strand the player invisible
            # or leave the source NPC available for revival/AI possession.
            from .appearance_visibility import restore_owner_camera_view
            try:
                restore_owner_camera_view(state.visibility_state)
            except Exception:
                pass
            for reference, visible, hidden, tick_option in state.parts:
                component = reference()
                if component is not None:
                    attach._set_component_visible(component, visible, hidden)
            pawn, source = state.pawn(), state.source()
            if pawn is not None:
                attach._call_quiet(pawn, 'SetActorHiddenInGame', state.pawn_hidden)
            if source is not None:
                self._make_passive(source)
                self._destroy_source(source)
            self.worn.pop(owner, None)
            logging.error('[Squ1ggs Appearance] Downed cleanup: ' + str(exc))
        finally:
            self.desired.pop(owner, None)
            self.options.pop(owner, None)
            self.retries.pop(owner, None)
        self.status = 'Original appearance restored while downed. Reapply the cosmetic after recovery.'

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

    def _toggle_camera(self):
        """Switch the local native view on the game thread."""
        pc = self._pc()
        pawn = getattr(pc, 'Pawn', None)
        camera = getattr(pc, 'PlayerCameraManager', None)
        if pawn is None or camera is None:
            raise RuntimeError('Load a character into a map first.')
        mode = str(camera.GetActorCameraMode(pawn) or 'Default')
        if mode not in ('Default', 'ThirdPerson'):
            raise RuntimeError('Leave the current camera mode before switching views.')
        wanted = 'ThirdPerson' if mode == 'Default' else 'Default'
        camera.SetActorCameraMode(pawn, wanted, 'Default', .15, False, False)
        if str(camera.GetActorCameraMode(pawn)) != wanted:
            transition = getattr(pc, 'CameraTransition', None)
            if callable(transition):
                transition(wanted, 'Default', .15, False, False)
        if str(camera.GetActorCameraMode(pawn)) != wanted:
            raise RuntimeError('The camera could not switch views.')
        self.status = 'Third-person view.' if wanted == 'ThirdPerson' else 'First-person view.'

    def _execute(self, action, key, owner):
        if action == 'toggle_camera':
            self._toggle_camera()
            self.operation.update(state='complete', message=self.status)
            return
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
            if action == 'apply' and self.options.get(owner, {}).get('hide_original_for_lobby') and not target.HasAuthority():
                raise RuntimeError('The lobby host must apply a shared BL4 character swap.')
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
        for state in tuple(self.worn.values()):
            if state.visibility_state.get('native_frame_driver'):
                from . import native_frame_motion
                saved = state.visibility_state['native_frame_driver']
                if time.monotonic()-saved['heartbeat'] > .25:
                    state.visibility_state['native_frame_motion_error']='PostPhysics heartbeat lost'
                    try: native_frame_motion.restore(state.visibility_state)
                    except Exception as exc:
                        state.visibility_state['native_frame_restore_error']=str(exc)
            if state.visibility_state.get('native_attached_driver'):
                from .animation import _hold_attached_native_driver
                pawn,source=state.pawn(),state.source()
                if pawn is not None and source is not None:
                    _hold_attached_native_driver(state.visibility_state,pawn,source)
            if state.visibility_state.get('network_follow_trial') is True:
                pawn,source=state.pawn(),state.source()
                if pawn is not None and source is not None:
                    if not self._sync_network_follow(state,pawn,source):
                        self.restore(state.owner)
                        self.status = 'Native network follow failed; original appearance restored.'
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
                self._make_passive(source)
                injured = getattr(pawn, 'IsInjured', None)
                if callable(injured) and injured():
                    self._restore_injured_wearer(owner, state)
                    continue
                if not self._source_is_bound(source, pawn):
                    if owner == "self":
                        self.set_invisible(False)
                    self.restore(owner)
                    self.status = "The model lost its attachment; original appearance restored. Choose another character."
                    self.operation.update(state="failed", message=self.status)
                    continue
                if self.invisible and owner == "self":
                    continue
                if state.hide_changed and bool(getattr(pawn, 'bHidden', False)):
                    attach._call_quiet(pawn, 'SetActorHiddenInGame', False)
                    attach._call_quiet(pawn, 'ForceNetUpdate')
                # Restore a hidden shell on vehicle exit before deciding that
                # its body failed. Never hide a wearer behind an unusable model.
                mesh = native._actor_mesh(source)
                attach._call_quiet(source, "SetActorHiddenInGame", False)
                if mesh is not None:
                    attach._set_component_visible(mesh, True, False)
                # Native BL4 actors need movement inputs after _make_passive
                # disables their physics. Imported packs own their clip driver.
                if not (state.model.startswith('pack:') or state.model.startswith('Char_Imported')):
                    from .animation import update_worn_animation
                    state.visibility_state['animation_status'] = update_worn_animation(
                        state.visibility_state, pawn, source, mesh, native._actor_mesh(pawn),
                        lobby=bool(state.hide_changed))
                    from .appearance_visibility import _make_shell_intangible
                    _make_shell_intangible(source)
                    problem = state.visibility_state.get('native_motion_error') or state.visibility_state.get('native_seat_error')
                    if problem:
                        self.restore(owner, forget=True)
                        self.status = 'Character animation unavailable: ' + str(problem) + ' Original appearance restored.'
                        self.operation.update(state='failed', message=self.status)
                        continue
                motion_state = state.visibility_state.get('native_motion_clip', {})
                motion_proxy = motion_state.get('proxy') if motion_state.get('proxy_visible') else None
                motion_proxy = motion_proxy() if motion_proxy else None
                if owner == 'self':
                    from .appearance_visibility import prepare_owner_camera_view
                    prepare_owner_camera_view(state.visibility_state, self._pc(), pawn, source, motion_proxy or mesh)
                if (not (state.model.startswith('pack:') or state.model.startswith('Char_Imported'))
                        and (state.visibility_state.get('native_weapon_trial') is True
                             or 'native_weapon_trial' not in state.visibility_state
                             or state.visibility_state.get('native_weapon_preview'))):
                    from . import native_weapon
                    from .animation import _player_is_driving
                    state.visibility_state['native_weapon_status'] = native_weapon.update(
                        state.visibility_state, pawn, source, mesh,
                        _player_is_driving(pawn, native._actor_mesh(pawn)))
                if not self._ready(source):
                    self.restore(owner, forget=not state.options.get("keep_on_respawn", True))
                    self.status = "Replacement unavailable; original body restored."
                    continue
                if state.hide_changed:
                    from .appearance_visibility import prepare_original_body_visibility
                    if not prepare_original_body_visibility(state.visibility_state,pawn,list(attach._appearance_skeletal_components(pawn))):
                        self.restore(owner)
                        self.status = 'Original body visibility replication lost; appearance restored.'
                        continue
                    state.visibility_state.update(shell=source, render_mesh=mesh, pawn=pawn)
                    if not prepare_lobby_visibility(state.visibility_state):
                        self.last_binding_observation.update(
                            lobby_visibility_stage=state.visibility_state.get('lobby_visibility_stage'),
                            lobby_visibility_error=state.visibility_state.get('lobby_visibility_error'),
                            native_seat_active=bool(state.visibility_state.get('native_seat_clip')),
                            native_seat_error=state.visibility_state.get('native_seat_error'))
                        self.restore(owner)
                        self.status = 'Lobby attachment replication was lost; original appearance restored.'
                        self.operation.update(state='failed', message=self.status)
                        continue
                existing = {str(comp) for ref, *_ in state.parts if (comp := ref()) is not None}
                for comp in attach._appearance_skeletal_components(pawn):
                    if str(getattr(comp, "Name", "")) == "FirstPersonArms":
                        continue
                    if str(comp) not in existing:
                        visible, hidden = attach._component_visible(comp)
                        state.parts.append((WeakPointer(comp), visible, hidden, getattr(comp, "VisibilityBasedAnimTickOption", None)))
                    # Camera changes can reset this on the hidden pose driver.
                    try:
                        comp.VisibilityBasedAnimTickOption = 0
                    except Exception:
                        pass
                    if not state.hide_changed:
                        from .appearance_visibility import hold_local_visual
                        hold_local_visual(source, [comp])
                        continue
                    attach._call_quiet(comp, "SetVisibility", False, False)
                    attach._call_quiet(comp, "SetHiddenInGame", True, False)
                set_shadow_visibility(state.visibility_state, [ref() for ref, *_ in state.parts], False)
                set_shadow_visibility(state.visibility_state, [mesh], True, group="replacement")
                if motion_proxy is not None:
                    attach._call_quiet(motion_proxy, 'SetCastShadow', True)
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
            from .packs import manager
            try:
                manager.tick()
            except Exception as exc:
                logging.error('[Squ1ggs Appearance packs] ' + str(exc))
            from .packs import imported_models
            for owner, worn in list(self.worn.items()):
                if not worn.model.startswith('pack:'):
                    continue
                problem = getattr(imported_models, '_animation_errors', {}).get(str(worn.source()))
                if problem:
                    self.restore(owner, forget=True)
                    self.status = str(problem) + ' Original appearance restored.'
                    self.operation.update(state='failed', message=self.status)
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
                  "appearance_visibility.py", "animation.py", "native_frame_motion.py", "data/bl4_characters.json",
                  "native_eye_camera.py", "native_fp_arms.py", "native_seating.py", "native_motion.py",
                  "native_stock_motion.py", "native_weapon.py", "data/camera_anatomy.json",
                  "data/native_motion_animations.json", "data/native_seat_animations.json", "data/native_stock_motion_animations.json",
                  "data/native_first_person_arms.json", "native_build.py", "data/native_build_reference.json"):
    with open_in_mod_dir(Path(__file__).parent / _relative, binary=True) as _stream:
        _digest.update(_relative.encode("utf-8") + b"\0" + _stream.read())
from .packs.files import SHARED_FILES
for _relative in SHARED_FILES:
    with open_in_mod_dir(Path(__file__).parent / _relative, binary=True) as _stream:
        _digest.update(_relative.encode('utf-8') + b'\0' + _stream.read())
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
