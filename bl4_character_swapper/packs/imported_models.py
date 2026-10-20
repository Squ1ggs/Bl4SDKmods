"""Opt-in custom-character preview; built-in actor appearance code stays unchanged."""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_data_path = Path(__file__).parent / "data" / "imported_models.json"
_models: dict[str, dict[str, Any]] | None = None
_pack_cache: dict[str, tuple[int, int, str]] = {}
_packages: dict[str, Any] = {}
_actors: dict[str, tuple[Any, str]] = {}
_animation_state: dict[str, tuple[str, str]] = {}
_material_state: dict[str, str] = {}
_material_retry_after: dict[str, float] = {}
_peer_body_masks: dict[str, dict[str, Any]] = {}
_last_tick = 0.0
_last_scan = 0.0


@dataclass
class _ImportedDeployment:
    """The common placement list must not keep a dangling imported actor."""
    label: str
    source: Any
    reference: Any
    actor_key: str
    class_name: str

    @property
    def actor(self) -> Any:
        return self.reference()


def _track_actor(actor: Any, model_id: str) -> Any:
    from unrealsdk.unreal import WeakPointer
    reference = WeakPointer(actor)
    _actors[str(actor)] = (reference, model_id)
    return reference


def live_actors() -> list[tuple[Any, str]]:
    """Resolve Unreal weak references before any reflected actor access."""
    live = []
    for key, (reference, model_id) in list(_actors.items()):
        actor = reference()
        if actor is None or str(getattr(actor, 'Name', '')) == 'None':
            _forget_actor(key)
            continue
        live.append((actor, model_id))
    return live


def _forget_actor(key: str) -> None:
    _clear_owner_view(key)
    if "cosmetic_effect:" + key in _packages:
        from . import imported_effects
        imported_effects.clear(key)
    weapon = _packages.pop("cosmetic_weapon:" + key, None)
    if weapon is not None:
        from . import imported_weapons
        imported_weapons.clear(None,weapon)
    _actors.pop(key, None)
    _animation_state.pop(key, None)
    _material_state.pop(key, None)
    _material_retry_after.pop(key, None)
    _restore_peer_body_mask(key)
    for cache_key in list(_packages):
        if cache_key in ("render_component:" + key, "preview_ground:" + key, "weapon_retry:" + key, "effect_retry:" + key, "animation_report:" + key) or cache_key.startswith(("material:" + key + ":", "flatmaterial:" + key + ":")):
            _packages.pop(cache_key, None)


def _prepare_materials(actor: Any, model_id: str) -> None:
    if model_id != "sora" and not models()[model_id].get("slot_textures"):
        return
    from . import imported_materials
    from . import engine as oak
    key = str(actor)
    component = oak._actor_mesh(actor)
    def material_stamp():
        return (str(component), tuple(str(component.GetMaterial(index))
                    for index in range(int(component.GetNumMaterials()))))
    stamp = material_stamp()
    if _material_state.get(key) == stamp:
        return
    imported_materials.prepare_actor(actor, model_id)
    _material_state[key] = material_stamp()
    _material_retry_after.pop(key, None)


def models() -> dict[str, dict[str, Any]]:
    global _models
    if _models is None:
        from .registry import character_models
        _models = character_models()
    return _models


def model_for_code(code: str) -> dict[str, Any] | None:
    return next((row for row in models().values() if row["code"] == code), None)


def pack_ready(row: dict[str, Any]) -> bool:
    from .companion_pak import _game_paks_dir
    folder = _game_paks_dir()
    if folder is None or not row.get("sha256"):
        return False
    files = {row["pak"]: row["sha256"], **row.get("containers", {})}
    for extension in row.get("animation_extensions", []):
        files.update({extension["pak"]: extension["sha256"], **extension.get("containers", {})})
    return all(_file_hash_matches(folder / name, expected) for name, expected in files.items())


def _file_hash_matches(path: Path, expected: str) -> bool:
    if not path.is_file() or not expected:
        return False
    st = path.stat()
    stamp = (st.st_mtime_ns, st.st_size)
    cached = _pack_cache.get(str(path))
    if cached is not None and cached[:2] == stamp:
        return cached[2] == expected
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    _pack_cache[str(path)] = (*stamp, actual)
    return actual == expected


def _load(kind: str, path: str) -> Any:
    import unrealsdk
    try:
        found = unrealsdk.find_object(kind, path)
    except Exception:
        found = None
    if found is not None:
        return _retain_imported_asset(found, path)
    package = path.split(".", 1)[0]
    # A Python UObject wrapper does not keep its Unreal allocation alive.
    # Retry a missing object even when its package was loaded earlier.
    loaded = unrealsdk.load_package(package)
    if loaded is None:
        from .imported_package_loader import load_package
        loaded = load_package(package)
    _packages[package] = loaded
    try:
        return _retain_imported_asset(unrealsdk.find_object(kind, path), path)
    except ValueError as exc:
        raise RuntimeError(f"Package {package} loaded, but its {kind} object is missing: {path}") from exc


def _retain_imported_asset(asset: Any, path: str) -> Any:
    """Keep the small imported asset set alive for this game process."""
    from .imported_package_loader import is_imported_path
    if is_imported_path(path) and hasattr(asset, "ObjectFlags"):
        from mods_base import ObjectFlags
        asset.ObjectFlags |= int(ObjectFlags.KEEP_ALIVE)
    return asset


def check(model_id: str = "sora") -> str:
    row = models()[model_id]
    if not pack_ready(row):
        raise RuntimeError("The matching imported-character PAK is missing or changed. Install the supplied pack and restart BL4.")
    cls = _load("Class", row["actor_class"])
    mesh = _load("SkeletalMesh", row["mesh"])
    if cls is None or mesh is None:
        raise RuntimeError("The PAK is present, but BL4 did not load its actor/mesh. Restart after installing it; check the game log if loading still fails.")
    from . import engine as oak
    component = oak._actor_mesh(cls.ClassDefaultObject)
    if component is None or oak._mesh_asset_for_kind(component) is None:
        raise RuntimeError("The imported actor's default mesh was not preserved. Your current appearance was not changed.")
    return f"{row['name']}: actor and skeletal mesh loaded. Rendering and multiplayer still require the preview test."


def spawn(model_id: str = "sora", *, side_offset_cm: float = 0.0) -> Any:
    row = models()[model_id]
    from . import engine as oak
    from .dev_tools import _gameplay_pc, _appearance_mesh_ready
    pc = _gameplay_pc()
    pawn = getattr(pc, "Pawn", None) if pc is not None else None
    if pawn is None:
        raise RuntimeError("Load a character into a map first.")
    if not pawn.HasAuthority():
        raise RuntimeError("The host must spawn imported characters. Each viewing player needs the matching model pack.")
    check(model_id)
    cls = _load("Class", row["actor_class"])
    _pc, _pawn, world, gs = oak._spawn_context()
    if gs is None or world is None:
        raise RuntimeError("No live world")
    z_offset = 0.0
    if row.get("align_capsule_ground"):
        z_offset = float(cls.ClassDefaultObject.CapsuleComponent.GetScaledCapsuleHalfHeight()) - float(pawn.CapsuleComponent.GetScaledCapsuleHalfHeight())
    from ..native_helpers import _preview_spawn_transform
    transform = _preview_spawn_transform(pawn, z_offset=z_offset)
    side_offset_cm = max(-300.0, min(300.0, float(side_offset_cm)))
    if side_offset_cm:
        right = pawn.GetActorRightVector()
        transform.Translation.X += float(right.X) * side_offset_cm
        transform.Translation.Y += float(right.Y) * side_offset_cm
    actor = oak._spawn_actor_deferred(gs, world, cls, transform, class_name=row["actor_class"])
    if actor is None:
        raise RuntimeError("The imported actor did not spawn. Your appearance was not changed.")
    if row.get("align_capsule_ground"):
        _packages["preview_ground:" + str(actor)] = True
    component = oak._actor_mesh(actor)
    if not _appearance_mesh_ready(actor, component):
        actor.K2_DestroyActor()
        raise RuntimeError("The imported actor has no ready mesh. Your appearance was not changed.")
    actor.SetActorEnableCollision(False)
    movement = getattr(actor, "CharacterMovement", None)
    if movement is not None:
        movement.StopMovementImmediately()
        movement.DisableMovement()
    try:
        _prepare_presentation(actor, model_id)
        _prepare_materials(actor, model_id)
    except Exception as exc:
        key = str(actor)
        actor.K2_DestroyActor()
        _forget_actor(key)
        raise RuntimeError(f"{row['name']}'s native colour setup failed: {exc}. Your appearance was not changed.") from exc
    reference = _track_actor(actor, model_id)
    oak._SPAWNED.append(_ImportedDeployment(label=row["code"], source=None, reference=reference,
                                           actor_key=oak._actor_key(actor), class_name=oak._class_name(actor)))
    return actor


def _prepare_presentation(actor: Any, model_id: str) -> None:
    """Apply the pack's measured mesh-to-actor orientation on every viewer."""
    from . import engine as oak
    import unrealsdk
    row = models()[model_id]
    yaw = row.get("mesh_yaw_degrees")
    if yaw is None:
        return
    component = oak._actor_mesh(actor)
    for bone in row.get('preview_hidden_bones', ()):
        if int(component.GetBoneIndex(bone)) < 0:
            raise RuntimeError('Configured cosmetic bone is missing: ' + bone)
        # PBO_None keeps physics untouched. The original mesh/animations stay
        # intact; only the reviewed accessory branch is collapsed for display.
        component.HideBoneByName(bone, 0)
    if row.get("align_capsule_ground"):
        _align_capsule_ground(actor, component, row)
    current = component.RelativeRotation
    pitch = float(row.get("mesh_pitch_degrees", 0))
    roll = float(row.get("mesh_roll_degrees", 0))
    if all(abs((actual - desired + 180) % 360 - 180) < .1 for actual,desired in
           ((float(current.Pitch),pitch),(float(current.Yaw),float(yaw)),(float(current.Roll),roll))):
        return
    rotation = unrealsdk.make_struct("Rotator", Pitch=pitch, Yaw=float(yaw), Roll=roll)
    component.K2_SetRelativeRotation(rotation, False, unrealsdk.make_struct("HitResult"), True)


def _align_capsule_ground(actor: Any, component: Any, row: dict) -> None:
    """Match capsule bottom heights for recipe previews and worn imports."""
    import unrealsdk
    import sys
    vehicles = sys.modules.get(__package__ + '.imported_vehicles')
    seated = getattr(vehicles, '_driver_visual', None)
    if seated and seated['component']() == component:
        return
    parent = actor.GetAttachParentActor()
    own_half_height = float(actor.CapsuleComponent.GetScaledCapsuleHalfHeight())
    mesh_z = float(row["mesh_z_offset_cm"])
    if parent is not None and getattr(parent, "CapsuleComponent", None) is not None:
        _packages.pop("preview_ground:" + str(actor), None)
        mesh_z += own_half_height - float(parent.CapsuleComponent.GetScaledCapsuleHalfHeight())
    elif actor.HasAuthority() and not _packages.get("preview_ground:" + str(actor)):
        # Old previews inherited the player's centre; correct the mismatch once.
        from .dev_tools import _gameplay_pc
        pawn = _gameplay_pc().Pawn
        player_half_height = float(pawn.CapsuleComponent.GetScaledCapsuleHalfHeight())
        current = actor.K2_GetActorLocation()
        position = unrealsdk.make_struct("Vector", X=float(current.X), Y=float(current.Y),
            Z=float(current.Z) + own_half_height - player_half_height)
        actor.K2_SetActorLocation(position, False, unrealsdk.make_struct("HitResult"), True)
        _packages["preview_ground:" + str(actor)] = True
    current_location = component.RelativeLocation
    if abs(float(current_location.Z) - mesh_z) > .1:
        location = unrealsdk.make_struct("Vector", X=float(current_location.X), Y=float(current_location.Y), Z=mesh_z)
        component.K2_SetRelativeLocation(location, False, unrealsdk.make_struct("HitResult"), True)


def _restore_peer_body_mask(key: str) -> None:
    state = _peer_body_masks.pop(key, None)
    if state is None:
        return
    from ..appearance_visibility import restore_shadow_visibility
    restore_shadow_visibility(state)
    from .dev_tools import _call_quiet
    for reference, visible, hidden in state["parts"]:
        component = reference()
        if component is not None:
            _call_quiet(component, "SetVisibility", visible, False)
            _call_quiet(component, "SetHiddenInGame", hidden, False)


def _repair_peer_body_mask(actor: Any) -> None:
    """Restore an attached cosmetic's visibility without changing its pose.

    Imported replacements leave the parent pawn globally visible. Mask its
    original components only when the replacement is available on this viewer.
    """
    from .dev_tools import _appearance_skeletal_components, _call_quiet, _component_visible
    from . import engine as oak
    from unrealsdk.unreal import WeakPointer
    key = str(actor)
    parent = actor.GetAttachParentActor()
    state = _peer_body_masks.get(key)
    if actor.HasAuthority() or parent is None or getattr(parent, "PlayerState", None) is None:
        _restore_peer_body_mask(key)
        return
    if state is not None and str(state["pawn"]()) != str(parent):
        _restore_peer_body_mask(key)
        state = None
    tracked = _actors.get(key)
    row = models().get(tracked[1]) if tracked else None
    # A passive attached Character is not sufficient identity. Only registered,
    # hash-matching local packs may hide a player's original components.
    if row is None or not pack_ready(row):
        _restore_peer_body_mask(key)
        return
    mesh = oak._actor_mesh(actor)
    if mesh is None or oak._mesh_asset_for_kind(mesh) is None:
        _restore_peer_body_mask(key)
        return
    needs_materials = tracked[1] == "sora" or bool(row.get("slot_textures"))
    if needs_materials and _material_state.get(key) != str(mesh):
        _restore_peer_body_mask(key)
        return
    if state is None:
        state = {"pawn": WeakPointer(parent), "actor": WeakPointer(actor), "parts": []}
        _peer_body_masks[key] = state
    # No server visibility or gameplay changes from a viewing client.
    _call_quiet(actor, "SetActorHiddenInGame", False)
    _call_quiet(mesh, "SetOwnerNoSee", False)
    _call_quiet(mesh, "SetOnlyOwnerSee", False)
    _call_quiet(mesh, "SetVisibility", True, False)
    _call_quiet(mesh, "SetHiddenInGame", False, False)
    visible, hidden = _component_visible(mesh)
    if not visible or hidden or bool(getattr(actor, "bHidden", False)):
        _restore_peer_body_mask(key)
        return
    known = {str(component) for reference, *_ in state["parts"] if (component := reference()) is not None}
    for component in _appearance_skeletal_components(parent):
        if str(getattr(component, "Name", "")) == "FirstPersonArms":
            continue
        if str(component) not in known:
            visible, hidden = _component_visible(component)
            state["parts"].append((WeakPointer(component), visible, hidden))
        _call_quiet(component, "SetVisibility", False, False)
        _call_quiet(component, "SetHiddenInGame", True, False)


    from ..appearance_visibility import set_shadow_visibility
    set_shadow_visibility(state, [ref() for ref, *_ in state["parts"]], False)
    set_shadow_visibility(state, [mesh], True, group="replacement")


def _discover_peer_cosmetics() -> None:
    """Discover only passive Character actors attached directly to players."""
    from .dev_tools import _gameplay_pc, _actor_still_alive
    import unrealsdk
    pc = _gameplay_pc()
    pawn = getattr(pc, "Pawn", None)
    if pawn is None or pawn.HasAuthority():
        for key in list(_peer_body_masks):
            _restore_peer_body_mask(key)
        return
    found = set()
    for actor in unrealsdk.find_all("Character", False):
        try:
            if "Default__" in str(actor) or not _actor_still_alive(actor):
                continue
            parent = actor.GetAttachParentActor()
            if parent is None or getattr(parent, "PlayerState", None) is None:
                continue
            if getattr(actor, "Controller", None) is not None or bool(getattr(actor, "bActorEnableCollision", True)):
                continue
            if str(actor.RootComponent.AttachParent) != str(parent.RootComponent):
                continue
            found.add(str(actor))
            _repair_peer_body_mask(actor)
        except Exception:
            continue
    for key in set(_peer_body_masks) - found:
        _restore_peer_body_mask(key)


def animation_for_motion(speed: float, falling: bool, crouched: bool = False) -> str:
    if falling:
        return "jump"
    if crouched:
        return "crouch_walk" if speed >= 10.0 else "crouch_idle"
    return "run" if speed >= 450.0 else "walk" if speed >= 10.0 else "idle"


def _clear_owner_view(actor_key: str) -> None:
    saved = _packages.pop("owner_view:" + actor_key, None)
    if not isinstance(saved, dict) or not saved.get("hidden_actor_added"):
        return
    controller = saved.get("controller")
    controller = controller() if controller is not None else None
    if controller is not None:
        controller.HiddenActors = [entry for entry in list(controller.HiddenActors)
                                  if entry is not None and str(entry) != actor_key]


def _prepare_owner_view(actor: Any) -> None:
    """Use the local controller's view list; never change cosmetic ownership."""
    from .dev_tools import _gameplay_pc, _player_camera_manager, _actor_camera_mode, _appearance_states
    from . import engine as oak
    from unrealsdk.unreal import WeakPointer
    key = "owner_view:" + str(actor)
    saved = _packages.get(key)
    pc = _gameplay_pc()
    pawn = getattr(pc, "Pawn", None)
    parent = actor.GetAttachParentActor()
    state = next((state for state in _appearance_states.values() if str(state.get("shell")) == str(actor)), None)
    worn_locally = pawn is not None and str(parent) == str(pawn)
    if not worn_locally:
        if isinstance(saved, dict):
            mesh = saved["mesh"]()
            if mesh is not None:
                mesh.SetOwnerNoSee(saved["owner_no_see"])
            if actor.HasAuthority():
                actor.SetOwner(saved["owner"]() if saved["owner"] is not None else None)
            _clear_owner_view(str(actor))
        return
    component = oak._actor_mesh(actor)
    if saved is not None:
        controller = saved.get("controller")
        controller = controller() if controller is not None else None
        if str(controller) != str(pc):
            _clear_owner_view(str(actor))
            saved = None
    if saved is None:
        owner = getattr(actor, "Owner", None)
        saved = {"mesh":WeakPointer(component), "owner":WeakPointer(owner) if owner is not None else None,
                 "owner_no_see":bool(component.bOwnerNoSee),"controller":WeakPointer(pc),"hidden_actor_added":False}
        _packages[key] = saved
    # Undo the previous prototype's owner/no-see changes before using a
    # strictly viewer-local hidden-actor entry.
    if actor.HasAuthority():
        original_owner = saved["owner"]() if saved["owner"] is not None else None
        if str(getattr(actor,"Owner",None)) != str(original_owner):
            actor.SetOwner(original_owner)
    if bool(component.bOwnerNoSee) != saved["owner_no_see"]:
        component.SetOwnerNoSee(saved["owner_no_see"])
    pcm = _player_camera_manager(pc)
    mode = _actor_camera_mode(pcm, pawn) or "Default"
    camera, origin = pcm.GetCameraLocation(), pawn.K2_GetActorLocation()
    first_person = mode == "Default" and math.hypot(float(camera.X-origin.X),float(camera.Y-origin.Y))<90
    if state is not None:
        state["first_person_body_mask"] = False
    entries = [entry for entry in list(pc.HiddenActors) if entry is not None]
    present = any(str(entry)==str(actor) for entry in entries)
    if first_person and not present:
        pc.HiddenActors = [*entries,actor]
        saved["hidden_actor_added"] = True
    elif not first_person and saved["hidden_actor_added"]:
        pc.HiddenActors = [entry for entry in entries if str(entry)!=str(actor)]
        saved["hidden_actor_added"] = False
    # Keep the native animated viewmodel when older swaps hid all player parts.
    for extra in (state or {}).get("extras", ()):
        original = extra.get("comp")
        if original is not None and str(getattr(original, "Name", "")) == "FirstPersonArms":
            original.SetVisibility(bool(extra.get("visible", True)), False)
            original.SetHiddenInGame(bool(extra.get("hidden", False)), False)


def _animate(actor: Any, model_id: str) -> None:
    row = models()[model_id]
    animations = row.get('animations', {})
    if not animations:
        return  # Explicit static-source previews retain their cooked bind pose.
    from . import engine as oak
    parent = actor.GetAttachParentActor()
    motion = parent if parent is not None else actor
    velocity = motion.GetVelocity()
    speed = math.hypot(float(velocity.X), float(velocity.Y))
    movement = getattr(motion, "CharacterMovement", None)
    falling = int(getattr(movement, "MovementMode", 0)) == 3
    mode = animation_for_motion(speed, falling, bool(getattr(motion, "bIsCrouched", False)))
    component = oak._actor_mesh(actor)
    # Attached cosmetics are hidden in first person. They still need pose and
    # bone updates so changing camera never leaves them in the reference pose.
    component.VisibilityBasedAnimTickOption = 0
    component.bPauseAnims = False
    component.bNoSkeletonUpdate = False
    tick_enabled = getattr(component, 'SetComponentTickEnabled', None)
    if callable(tick_enabled):
        tick_enabled(True)
    if getattr(component, 'LeaderPoseComponent', None) is not None:
        # Compatible rigs follow the actual player's pose, including seats.
        _animation_state.pop(str(actor), None)
        return
    fallback_mode = animation_for_motion(speed, falling)
    candidates = [mode, fallback_mode]
    # Packs with only one verified ground-motion clip should keep moving at
    # both walking and sprinting speeds instead of returning to a still idle.
    if fallback_mode in ('walk', 'run'):
        candidates.append('walk' if fallback_mode == 'run' else 'run')
    selected_mode = next((value for value in candidates if value in animations), 'idle')
    path = animations.get(selected_mode)
    if not path:
        return
    source_speed = float(row.get('animation_speeds_cm_s', {}).get(selected_mode, 0))
    rate = max(.25, min(4.0, speed / source_speed)) if source_speed > 0 and speed >= 10 else 1.0
    set_rate = getattr(component, 'SetPlayRate', None)
    if callable(set_rate):
        set_rate(rate)
    stamp = (str(component), path)
    if _animation_state.get(str(actor)) == stamp:
        playing = getattr(component, 'IsPlaying', None)
        # Jump clips finish once; do not restart them while still airborne.
        if selected_mode == 'jump' or not callable(playing) or playing():
            return
    asset = _load("AnimSequence", path)
    mesh = oak._mesh_asset_for_kind(component)
    if asset is None or mesh is None or str(asset.Skeleton) != str(mesh.Skeleton):
        return
    component.PlayAnimation(asset, selected_mode != "jump")
    if callable(set_rate):
        set_rate(rate)
    _animation_state[str(actor)] = stamp


def tick() -> None:
    global _last_tick, _last_scan
    now = time.monotonic()
    if now - _last_tick < 0.08:
        return
    _last_tick = now
    import unrealsdk
    from .dev_tools import _actor_still_alive
    if now - _last_scan >= 0.75:
        _last_scan = now
        _discover_peer_cosmetics()
        # Discover only already-loaded custom classes. Never scan/control NPCs.
        for model_id, row in models().items():
            try:
                cls = unrealsdk.find_object("Class", row["actor_class"])
                if cls is None:
                    continue
                for actor in unrealsdk.find_all(str(cls.Name)):
                    if str(actor) == str(cls.ClassDefaultObject) or str(getattr(actor, "Name", "")).startswith("Default__"):
                        continue
                    if _actor_still_alive(actor):
                        _track_actor(actor, model_id)
            except Exception:
                continue
    for actor, model_id in live_actors():
        key = str(actor)
        try:
            _prepare_presentation(actor, model_id)
            _prepare_owner_view(actor)
        except Exception:
            # Camera failures must not suppress materials or animation.
            pass
        if now >= _material_retry_after.get(key, 0.0):
            try:
                _prepare_materials(actor, model_id)
            except Exception as exc:
                _restore_peer_body_mask(key)
                _material_retry_after[key] = now + 10.0
                from . import imported_materials
                imported_materials._save_report("sora_materials_last", {
                    "ok": False, "strategy": "automatic", "actor": key, "message": str(exc),
                })
        try:
            _repair_peer_body_mask(actor)
        except Exception:
            _restore_peer_body_mask(key)
        try:
            _animate(actor, model_id)
        except Exception as exc:
            if now >= _packages.get('animation_report:' + key, 0):
                _packages['animation_report:' + key] = now + 10
                from . import imported_materials
                imported_materials._save_report('imported_animation_last', {'ok': False, 'actor': key, 'model': model_id, 'message': str(exc)})
        if models()[model_id].get('cosmetic_effect') and now >= _packages.get('effect_retry:' + key, 0):
            try:
                from . import imported_effects
                imported_effects.prepare(actor, models()[model_id])
            except Exception as exc:
                _packages['effect_retry:' + key] = now + 10
                from . import imported_materials
                imported_materials._save_report('imported_effect_last', {'ok': False, 'actor': key, 'message': str(exc)})
        if (models()[model_id].get("weapon_bone") or "cosmetic_weapon:" + key in _packages) and now >= _packages.get("weapon_retry:"+key,0):
            try:
                from . import imported_weapons
                imported_weapons.prepare(actor,models()[model_id])
            except Exception as exc:
                _packages["weapon_retry:"+key] = now + 10
                from . import imported_materials
                imported_materials._save_report("imported_weapon_last",{"ok":False,"actor":key,"message":str(exc)})


def clear_previews() -> int:
    from .dev_tools import _appearance_states, _actor_still_alive
    worn = {str(state.get("shell")) for state in _appearance_states.values()}
    count = 0
    for actor, _ in live_actors():
        key = str(actor)
        if key in worn:
            continue
        if _actor_still_alive(actor):
            actor.K2_DestroyActor()
            count += 1
        _forget_actor(key)
    return count
