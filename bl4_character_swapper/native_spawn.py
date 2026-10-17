# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 RDPSqu1ggs
"""One owned native character request, advanced on separate game ticks.

Uses the same FGbxDefPtr/PushActorDef/ResetSpawner sequence as SQBT's native
spawner. It never edits authored map spawners, scans for a vaguely matching
world actor, changes global spawn limits, or loads the whole catalog. Definition
and class resolution use the extracted EXE helpers, including SDK fallbacks.
"""
from __future__ import annotations
import time
import unrealsdk
from unrealsdk.unreal import WeakPointer
from . import native_helpers as native
from . import attachment as attach
from . import native_resolution as resolve


def alive(component):
    return resolve._alive_actors_for_spawner_component(component)[:16]


class NativeSpawn:
    def __init__(self, row, pawn, world):
        self.row = row
        self.code = row.get("spawn_code", row["code"])
        self.pawn = WeakPointer(pawn)
        self.world = str(world)
        self.deadline = time.monotonic() + 25.0
        self.packages = iter(dict.fromkeys(row.get("packages", ())))
        self.spawner = None
        self.component = None
        self.definition = None
        self.direct_source = None
        self.finished = False
        self.message = "Loading selected character."

    def _fire(self, pawn, world):
        # Preserve the EXE's map distinction: open worlds use OakSpawner;
        # instance maps may need a native class instead of an unresolved row.
        helpers = unrealsdk.find_class("GameplayStatics")
        gs = getattr(helpers, "ClassDefaultObject", None)
        if gs is None:
            raise RuntimeError("The SDK cannot access native character spawning in this session.")
        location, forward = pawn.K2_GetActorLocation(), pawn.GetActorForwardVector()
        transform = unrealsdk.make_struct("Transform")
        transform.Rotation.W = 1.0
        transform.Scale3D.X = transform.Scale3D.Y = transform.Scale3D.Z = 1.0
        transform.Translation.X = float(location.X) + float(forward.X) * 350.0
        transform.Translation.Y = float(location.Y) + float(forward.Y) * 350.0
        transform.Translation.Z = float(location.Z)
        actor_class = resolve._class_for_actor_name(self.code) if not resolve._mesh_already_streamed() else None
        if actor_class is not None:
            for template in (getattr(actor_class, "ClassDefaultObject", None), actor_class,
                             getattr(actor_class, "DefaultObject", None)):
                mesh = native._actor_mesh(template) if template is not None else None
                if mesh is None or native._mesh_asset_for_kind(mesh) is None:
                    continue
                actor = native._spawn_actor_deferred(gs, world, actor_class, transform,
                                                     source=template, class_name=self.code)
                if actor is not None:
                    self.direct_source = WeakPointer(actor)
                    self.message = "Waiting for the native character template to render."
                    return
        # Keep both paths used by the EXE: the live native type and its
        # compatibility shell builder. A failure in one must not lose the other.
        definition = None
        live_definition = getattr(getattr(pawn, "GbxActorData", None), "GbxActorDef", None)
        definition_type = getattr(live_definition, "_type", None)
        if definition_type is not None:
            try:
                definition = unrealsdk.unreal.FGbxDefPtr(self.code, type=definition_type)
            except Exception:
                pass
        if definition is None:
            definition = resolve._make_actor_def_shell(self.code)
        # pyunrealsdk 1.10 exposes _name even before the pointer resolves.
        # _experimental_name belongs to older SDKs; reading it on a current
        # unresolved pointer attempts an Unreal field lookup and raises.
        definition_name = (getattr(definition, "_name", None)
                           or getattr(definition, "_experimental_name", None))
        if definition is None or str(definition_name) != self.code:
            raise RuntimeError("The SDK could not construct the selected character definition.")
        self.definition = definition
        cls = unrealsdk.find_class("OakSpawner")
        if cls is None or gs is None:
            raise RuntimeError("The SDK cannot access native character spawning in this session.")
        spawner = native._spawn_actor_deferred(gs, world, cls, transform, class_name="OakSpawner")
        if spawner is None:
            raise RuntimeError("BL4 did not create the character's temporary spawner.")
        self.spawner = WeakPointer(spawner)
        component = spawner.GetSpawnerComponent()
        if component is None:
            raise RuntimeError("The temporary character spawner has no spawn component.")
        self.component = WeakPointer(component)
        for target in (spawner, component):
            for field in ("bInfinite", "bUnlimitedSpawns", "bAllowRespawn", "bRespawnEnabled"):
                try:
                    if hasattr(target, field):
                        setattr(target, field, False)
                except Exception:
                    pass
            for field in ("MaxAliveActors", "MaxSpawnCount", "NumActorsToSpawn", "SpawnCount"):
                try:
                    if hasattr(target, field):
                        setattr(target, field, 1)
                except Exception:
                    pass
        # This helper is for ONE appearance. Never apply the full spawner's
        # unlimited-cap/respawn overrides to a cosmetic source.
        for name in ("SetSpawnerEnabled", "SetSpawnPointEnabled"):
            attach._call_quiet(component, name, True)
        component.PushActorDef("Squ1ggsAppearance", definition, True)
        try:
            component.ResetSpawner(True)
        except TypeError:
            component.ResetSpawner()
        self.message = "Waiting for the selected native character to appear."

    def step(self, world):
        """Return an actor only from this owned helper; keep it until render-ready."""
        pawn = self.pawn()
        if self.finished:
            return None
        if str(world) != self.world or pawn is None:
            raise RuntimeError("Character loading cancelled because the session changed.")
        if time.monotonic() >= self.deadline:
            raise RuntimeError("The selected character did not load. Its content or DLC may be unavailable here.")
        if self.direct_source is not None:
            return self.direct_source()
        if self.spawner is None:
            package = next(self.packages, None)
            if package is not None:
                # Only metadata-backed package names. One load call per tick;
                # a None return does not prove absence (SDK loads can return it).
                if not package.startswith("/Game/"):
                    raise RuntimeError("The character catalog contains an invalid package path.")
                try:
                    unrealsdk.load_package(package)
                except Exception:
                    pass
                return None
            self._fire(pawn, world)
            return None
        component = self.component() if self.component else None
        if component is None:
            raise RuntimeError("The temporary character spawner expired while loading.")
        actors = alive(component)
        # Keep at most one source. Unexpected extra actors belong exclusively
        # to this helper; never touch actors from any map or another request.
        for extra in actors[1:]:
            attach._call_quiet(extra, "K2_DestroyActor")
        if actors:
            attach._call_quiet(component, "SetSpawnerEnabled", False)
            attach._call_quiet(component, "SetSpawnPointEnabled", False)
            return actors[0]
        return None

    def detach(self):
        """Transfer the helper's lifetime with its actor, without destroying it."""
        self.finished = True
        return self.spawner

    def cancel(self):
        if self.direct_source is not None:
            attach._call_quiet(self.direct_source(), "K2_DestroyActor")
        component = self.component() if self.component else None
        if component is not None:
            attach._call_quiet(component, "SetSpawnerEnabled", False)
            attach._call_quiet(component, "SetSpawnPointEnabled", False)
            for actor in alive(component):
                attach._call_quiet(actor, "K2_DestroyActor")
        spawner = self.spawner() if self.spawner else None
        attach._call_quiet(spawner, "K2_DestroyActor")
        self.finished = True
