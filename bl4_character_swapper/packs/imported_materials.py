from __future__ import annotations
from .registry import texture_root

from typing import Any

from pathlib import Path

from datetime import datetime, timezone

import json

import math

import traceback

def _save_report(name: str, result: dict) -> None:
    """Keep the latest live result available after a chat or game restart."""
    try:
        from mods_base import SETTINGS_DIR
        folder = Path(SETTINGS_DIR) / "appearance_pack_logs"
        folder.mkdir(exist_ok=True)
        report = {"recorded_at": datetime.now(timezone.utc).isoformat(), **result}
        (folder / (name + ".json")).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass

def _checked_object(value: Any, base: str, context: str) -> Any:
    """Validate SDK return values before handing them to reflected setters."""
    import unrealsdk
    from . import engine as oak
    value = oak._unwrap(value)
    cls = getattr(value, "Class", None) if value is not None else None
    if cls is None or not cls._inherits(unrealsdk.find_class(base)):
        kind = str(getattr(cls, "Name", type(value).__name__))
        raise RuntimeError(f"{context}: expected {base}, got {kind}")
    return value

def _preview_mesh(actor: Any) -> Any:
    from . import imported_models
    from . import engine as oak
    experiment = imported_models._packages.get("render_component:" + str(actor))
    return experiment[1] if experiment is not None else oak._actor_mesh(actor)

def prepare_actor(actor: Any, model_id: str) -> None:
    """Bind the confirmed native shader before an imported actor is shown."""
    if model_id != "sora":
        _prepare_recipe_actor(actor, model_id)
        return
    result = _apply_game_parent({"material_profile": "simple"}, actor=actor)
    if not result["ok"]:
        raise RuntimeError(result["message"])

def _prepare_recipe_actor(actor: Any, model_id: str, *, component=None) -> None:
    """Bind ordinary recipe diffuse maps through the proven BL4 simple shader."""
    from . import imported_models
    from . import engine as oak
    row = imported_models.models()[model_id]
    mapping = row.get("slot_textures")
    if not mapping:
        raise RuntimeError("This character has no native BL4 material recipe")
    source = _checked_object(imported_models._load("MaterialInterface", "/Game/World/Interactives/Lootables/AmmoChest/OrderAmmoChest/Model/MI_Order_AmmoChest_SkelMesh.MI_Order_AmmoChest_SkelMesh"), "MaterialInterface", "BL4 simple shader")
    base_info = next((parameter.ParameterInfo for parameter in source.TextureParameterValues if str(parameter.ParameterInfo.Name) == "BaseColor"), None)
    if base_info is None:
        raise RuntimeError("BL4 simple shader has no BaseColor parameter")
    normal = _checked_object(imported_models._load("Texture2D", "/Game/Common/Texture/Proxy/T_Proxy_N.T_Proxy_N"), "Texture", "Native normal proxy")
    packed = _checked_object(imported_models._load("Texture2D", "/Game/Common/Texture/Proxy/T_Proxy_Dielectric_C.T_Proxy_Dielectric_C"), "Texture", "Native nonmetal proxy")
    if row.get("surface_profile") == "matte":
        import unrealsdk
        from mods_base import ObjectFlags
        surface_rg = tuple(float(value) for value in row.get("surface_comp_rg", (.95, .95)))
        if len(surface_rg) != 2 or any(not math.isfinite(value) or not 0 <= value <= 1 for value in surface_rg):
            raise RuntimeError("Recipe surface channels must contain two values from zero to one")
        key = "recipeMatteSurface:" + model_id + ":" + repr(surface_rg)
        saved_path = imported_models._packages.get(key)
        packed = None
        if isinstance(saved_path, str):
            try:
                packed = unrealsdk.find_object("TextureRenderTarget2D", saved_path)
            except ValueError:
                pass
        if packed is None:
            library = unrealsdk.find_class("KismetRenderingLibrary").ClassDefaultObject
            # Native dielectric proxy readback is (128,128,0,255).
            # Keep its nonmetal B channel and use a high-roughness trial in
            # both remaining channels; their exact ordering is not recovered.
            colour = unrealsdk.make_struct("LinearColor", R=surface_rg[0],G=surface_rg[1],B=0,A=1)
            packed = _checked_object(library.CreateRenderTarget2D(actor,16,16,2,colour,False,False),
                                     "TextureRenderTarget2D", "Create matte surface proxy")
            library.ClearRenderTarget2D(actor,packed,colour)
            packed.ObjectFlags |= int(ObjectFlags.KEEP_ALIVE)
            imported_models._packages[key] = oak._object_path_name(packed)
    component = component if component is not None else _preview_mesh(actor)
    mesh = oak._mesh_asset_for_kind(component)
    invisible_slots = tuple(row.get("preview_invisible_slots", ()))
    available_slots = {str(slot.MaterialSlotName) for slot in mesh.Materials}
    if any(name not in available_slots for name in invisible_slots):
        raise RuntimeError("Recipe invisible material slot does not exist on this mesh")
    invisible = (_checked_object(imported_models._load("MaterialInterface", "/Game/AI/_Shared/Materials/MI_Color_Invisible.MI_Color_Invisible"),
                                 "MaterialInterface", "Recipe invisible preview overlay") if invisible_slots else None)
    bindings = []
    for index, slot in enumerate(mesh.Materials):
        name = str(slot.MaterialSlotName)
        path = mapping.get(name)
        if not path or not path.startswith(row["mesh"].split("/SK_", 1)[0] + "/Textures/"):
            raise RuntimeError("Missing or out-of-namespace diffuse map for slot " + name)
        filename = row.get("runtime_texture_files", {}).get(name)
        texture = (_runtime_recipe_texture(actor, model_id, filename) if filename else
                   _checked_object(imported_models._load("Texture2D", path), "Texture", "Recipe texture " + name))
        if bool(getattr(texture, "VirtualTextureStreaming", False)):
            raise RuntimeError("BL4 simple shader requires ordinary diffuse textures")
        bindings.append((index,name,texture))
    retained = _bind_colour_maps(component,source,base_info,bindings,normal,packed,
                                 normal_name="Normal",packed_name="Comp",invisible=invisible,invisible_slots=invisible_slots)
    for index, material, texture in retained:
        imported_models._packages[f"material:{actor}:{model_id}:{index}"] = (material,texture,normal,packed)

def _runtime_recipe_texture(actor: Any, model_id: str, relative_file: str) -> Any:
    """Load a locally prepared recipe colour map and keep its allocation alive."""
    import hashlib
    import unrealsdk
    from mods_base import ObjectFlags
    from . import imported_models
    from . import engine as oak
    root = (texture_root(model_id)).resolve()
    filename = (root / relative_file).resolve()
    if not filename.is_relative_to(root) or filename.suffix.lower() != ".png" or not filename.is_file():
        raise RuntimeError("Recipe colour image must be a PNG inside its character texture folder")
    digest = hashlib.sha256(filename.read_bytes()).hexdigest()
    key = "runtimeRecipeTexture:" + model_id + ":" + digest
    saved_path = imported_models._packages.get(key)
    if isinstance(saved_path, str):
        try:
            return _checked_object(unrealsdk.find_object("Texture2D", saved_path), "Texture2D", "Retained recipe image")
        except ValueError:
            pass
    library = unrealsdk.find_class("KismetRenderingLibrary").ClassDefaultObject
    texture = _checked_object(library.ImportFileAsTexture2D(actor, str(filename)), "Texture2D", "Import recipe image")
    texture.ObjectFlags |= int(ObjectFlags.KEEP_ALIVE)
    imported_models._packages[key] = oak._object_path_name(texture)
    return texture

def _iris_texture(actor: Any, library: Any) -> Any:
    """Draw an iris into the lens's centred disk UVs using native Canvas."""
    import unrealsdk
    def colour(rgb):
        return unrealsdk.make_struct("LinearColor", R=rgb[0], G=rgb[1], B=rgb[2], A=1.0)
    def point(x, y):
        return unrealsdk.make_struct("Vector2D", X=x, Y=y)
    size = 256.0
    white = colour((0.75, 0.72, 0.68))
    texture = _checked_object(library.CreateRenderTarget2D(actor, int(size), int(size), 2, white, False, False),
                              "TextureRenderTarget2D", "Create Sora iris texture")
    library.ClearRenderTarget2D(actor, texture, white)
    outputs = library.BeginDrawCanvasToRenderTarget(
        actor, texture, None, point(0.0, 0.0), unrealsdk.make_struct("DrawToRenderTargetContext"))
    parts = list(outputs) if isinstance(outputs, (tuple, list)) else []
    # pyunrealsdk puts Ellipsis first for a void return, followed by the
    # output arguments in declaration order (it does not mutate inputs).
    if parts and (parts[0] is None or parts[0] is Ellipsis):
        parts.pop(0)
    if len(parts) != 3:
        _save_report("sora_iris_canvas", {"type": type(outputs).__name__, "value": str(outputs)})
        if parts and str(getattr(parts[-1], "RenderTarget", None)) == str(texture):
            library.EndDrawCanvasToRenderTarget(actor, parts[-1])
        raise RuntimeError(f"BL4 returned unexpected iris Canvas outputs ({type(outputs).__name__}: {outputs})")
    canvas, _size, context = parts
    try:
        canvas = _checked_object(canvas, "Canvas", "Sora iris Canvas")
        if str(getattr(context, "RenderTarget", None)) != str(texture):
            raise RuntimeError("The iris draw context does not match its render target")
        centre = point(size * 0.5, size * 0.5)
        def circle(radius, rgb, position=centre):
            canvas.K2_DrawPolygon(None, position, point(radius, radius), 64, colour(rgb))
        # The KH iris/pupil were procedural. Recreate the visible detail on
        # the original lens geometry; both eyes use the same centred UV disk.
        circle(size * 0.48, (0.004, 0.012, 0.035))
        for step in range(32):
            t = step / 31.0
            radius = size * (0.45 - t * 0.29)
            rgb = (0.012 + 0.04 * t, 0.08 + 0.27 * t, 0.25 + 0.4 * t)
            circle(radius, rgb)
        for index in range(64):
            angle = index * math.tau / 64.0
            c, s = math.cos(angle), math.sin(angle)
            inner = size * (0.18 + 0.02 * (index % 3))
            outer = size * (0.4 + 0.025 * (index % 2))
            rgb = (0.025, 0.18, 0.38) if index % 2 else (0.07, 0.37, 0.64)
            canvas.K2_DrawLine(point(size * 0.5 + c * inner, size * 0.5 + s * inner),
                               point(size * 0.5 + c * outer, size * 0.5 + s * outer), 1.0, colour(rgb))
        circle(size * 0.16, (0.002, 0.008, 0.025))
        circle(size * 0.14, (0.001, 0.002, 0.004))
        circle(size * 0.035, (0.9, 0.92, 0.95), point(size * 0.41, size * 0.39))
    finally:
        library.EndDrawCanvasToRenderTarget(actor, context)
    return texture

def _apply_game_parent(payload: dict, *, actor: Any = None) -> dict:
    """Reuse a cooked BL4 shader with Sora's UV0 colour maps."""
    import unrealsdk
    from . import imported_models
    from .dev_tools import _actor_still_alive
    from . import engine as oak
    worn = set()
    if payload.get("preview_only"):
        from .dev_tools import _appearance_states
        worn = {str(state.get("shell")) for state in _appearance_states.values()}
    simple = payload.get("material_profile") == "simple"
    source_path = ("/Game/World/Interactives/Lootables/AmmoChest/OrderAmmoChest/Model/MI_Order_AmmoChest_SkelMesh.MI_Order_AmmoChest_SkelMesh"
                   if simple else "/Game/Common/MaterialTemplateLibrary/Character/MI_Template_Char_Mouth.MI_Template_Char_Mouth")
    source = imported_models._load("MaterialInterface", source_path)
    library = unrealsdk.find_class("KismetRenderingLibrary").ClassDefaultObject
    base_name, normal_name, packed_name = (("BaseColor", "Normal", "Comp") if simple
                                         else ("Base Color Map", "Normal Map", "AORS Map"))
    parameter_info = next((parameter.ParameterInfo for parameter in source.TextureParameterValues if str(parameter.ParameterInfo.Name) == base_name), None)
    if parameter_info is None:
        raise RuntimeError(f"BL4 material template has no verified {base_name} parameter")
    invisible = (_checked_object(imported_models._load("MaterialInterface", "/Game/AI/_Shared/Materials/MI_Color_Invisible.MI_Color_Invisible"),
                                 "MaterialInterface", "Sora invisible eye lens")
                 if simple else None)
    # Use BL4's own neutral normal and nonmetal surface map. These avoid
    # guessing this shader's normal decoding and packed channel convention.
    native_normal = native_packed = None
    if simple and not payload.get("base_color_only"):
        native_normal = _checked_object(imported_models._load("Texture2D", "/Game/Common/Texture/Proxy/T_Proxy_N.T_Proxy_N"),
                                        "Texture", "BL4 neutral normal")
        native_packed = _checked_object(imported_models._load("Texture2D", "/Game/Common/Texture/Proxy/T_Proxy_Dielectric_C.T_Proxy_Dielectric_C"),
                                        "Texture", "BL4 nonmetal surface map")
        if any(bool(getattr(texture, "VirtualTextureStreaming", False)) for texture in (native_normal, native_packed)):
            raise RuntimeError("The native Sora shader needs ordinary, non-virtual surface textures")
    diffuse = {"p_ex001_F_mat0_Inst": "p_ex001_F_0d00", "p_ex001_mat0_Inst": "p_ex001_0d00",
               "p_ex001_mat1_Inst": "p_ex001_0d01", "p_ex001_mat2_Inst": "p_ex001_0d02", "p_ex001_mat3_Inst": "p_ex001_0d00"}
    colors = {"p_ex001_hair_Inst": (0.12, 0.035, 0.012), "p_ex001_hair_Inst_Inst": (0.12, 0.035, 0.012),
              "p_ex001_M_mat0_Inst": (0.06, 0.008, 0.008), "p_ex001_E_mat0_Inst": (0.75, 0.72, 0.68),
              "p_ex001_E_mat1_Inst": (0.8, 0.8, 0.8), "p_ex001_E_mat3_Inst": (0.008, 0.004, 0.004)}
    count = 0
    actors = [(actor, "sora")] if actor is not None else imported_models.live_actors()
    for actor, model_id in actors:
        if model_id != "sora" or str(actor) in worn or not _actor_still_alive(actor):
            continue
        component = _preview_mesh(actor)
        mesh = oak._mesh_asset_for_kind(component)
        def solid(rgb):
            color = unrealsdk.make_struct("LinearColor", R=rgb[0], G=rgb[1], B=rgb[2], A=1.0)
            texture = _checked_object(
                # Constants above are linear RGB, like Blender's shader
                # inputs. Use a linear render target for constant colours.
                library.CreateRenderTarget2D(actor, 16, 16, 2, color, False, False),
                "TextureRenderTarget2D", "Create Sora constant colour texture",
            )
            if texture is None:
                raise RuntimeError("Could not create the imported material's constant texture")
            library.ClearRenderTarget2D(actor, texture, color)
            return texture
        normal = None if payload.get("base_color_only") else native_normal if simple else solid((0.5, 0.5, 1.0))
        packed = None if payload.get("base_color_only") else native_packed if simple else solid((1.0, 0.8, 0.0))
        bindings = []
        eye_slots = {"p_ex001_E_mat0_Inst", "p_ex001_E_mat1_Inst", "p_ex001_Eyelens_Inst"}
        for index, slot in enumerate(mesh.Materials):
            name = str(slot.MaterialSlotName)
            if payload.get("eye_layers_only") and name not in eye_slots:
                continue
            if payload.get("diagnostic_flat_colour"):
                texture = solid((1.0, 0.0, 0.0))
            elif simple and name == "p_ex001_Eyelens_Inst":
                texture = _iris_texture(actor, library)
            elif name in diffuse:
                texture_name = diffuse[name]
                if payload.get("runtime_png"):
                    key = "runtimeTexture:" + texture_name
                    # Store names rather than raw wrappers: wrappers can outlive
                    # collected Unreal allocations and crash when dereferenced.
                    saved_path = imported_models._packages.get(key)
                    texture = None
                    if isinstance(saved_path, str):
                        try:
                            texture = unrealsdk.find_object("Texture2D", saved_path)
                        except ValueError:
                            pass
                    if texture is None:
                        filename = texture_root("sora") / (texture_name + ".png")
                        if not filename.is_file():
                            raise RuntimeError(f"Missing Sora colour image: {filename.name}")
                        try:
                            texture = _checked_object(library.ImportFileAsTexture2D(actor, str(filename)),
                                                      "Texture2D", f"Import {filename.name}")
                        except Exception as exc:
                            raise RuntimeError(f"Runtime PNG import failed for slot {index} ({name}): {exc}") from exc
                        from mods_base import ObjectFlags
                        texture.ObjectFlags |= int(ObjectFlags.KEEP_ALIVE)
                    imported_models._packages[key] = oak._object_path_name(texture)
                else:
                    texture = imported_models._load("Texture2D", f"/Game/ImportedCharacters/Sora/Textures/{texture_name}.{texture_name}")
            else:
                texture = solid(colors.get(name, (0.7, 0.7, 0.7)))
            texture = _checked_object(texture, "Texture", f"Colour texture for slot {index} ({name})")
            bindings.append((index, name, texture))
        # Resolve every texture before changing any render binding. If a
        # reflected setter fails, restore this preview's previous materials.
        retained = _bind_colour_maps(component, source, parameter_info, bindings, normal, packed,
                                     normal_name=normal_name, packed_name=packed_name, invisible=invisible,
                                     invisible_slots=("p_ex001_E_mat1_Inst",) if simple else ("p_ex001_Eyelens_Inst",))
        for index, material, texture in retained:
            imported_models._packages[f"material:{actor}:{index}"] = (material, texture, normal, packed)
        count += 1
    message = (f"Applied Sora colour maps through a cooked BL4 shader on {count} imported actor(s)."
               if count else "No matching Sora preview found. Spawn a Sora preview first.")
    return {"ok": bool(count), "message": message}

def _bind_colour_maps(component: Any, source: Any, parameter_info: Any, bindings: list,
                      normal: Any, packed: Any, *, normal_name: str = "Normal Map",
                      packed_name: str = "AORS Map", invisible: Any = None,
                      invisible_slots: tuple[str, ...] = ("p_ex001_Eyelens_Inst",)) -> list:
    texture_infos = {str(row.ParameterInfo.Name): row.ParameterInfo
                     for row in getattr(source, "TextureParameterValues", ())}
    scalar_infos = {str(row.ParameterInfo.Name): row.ParameterInfo
                    for row in getattr(source, "ScalarParameterValues", ())}
    for name, value in ((normal_name, normal), (packed_name, packed)):
        if value is not None and name not in texture_infos:
            raise RuntimeError(f"BL4 material template has no verified {name} parameter")
    originals = [(index, component.GetMaterial(index)) for index, _, _ in bindings]
    retained = []
    try:
        for index, name, texture in bindings:
            if invisible is not None and name in invisible_slots:
                component.SetMaterial(index, invisible)
                retained.append((index, invisible, texture))
                continue
            material = _checked_object(component.CreateDynamicMaterialInstance(index, source, "None"),
                                       "MaterialInstanceDynamic", f"Create material for slot {index} ({name})")
            material.SetTextureParameterValueByInfo(parameter_info, texture)
            if normal is not None:
                material.SetTextureParameterValueByInfo(texture_infos[normal_name], normal)
            if packed is not None:
                material.SetTextureParameterValueByInfo(texture_infos[packed_name], packed)
            if "Skin Detail Strength" in scalar_infos:
                material.SetScalarParameterValueByInfo(scalar_infos["Skin Detail Strength"], 0.0)
            retained.append((index, material, texture))
    except Exception as exc:
        restore_errors = []
        for original_index, original_material in originals:
            try:
                component.SetMaterial(original_index, original_material)
            except Exception as restore_exc:
                restore_errors.append(f"slot {original_index}: {restore_exc}")
        suffix = f"; restore errors: {', '.join(restore_errors)}" if restore_errors else "; previous materials restored"
        raise RuntimeError(f"Colour binding failed on slot {index} ({name}): {exc}{suffix}") from exc
    return retained
