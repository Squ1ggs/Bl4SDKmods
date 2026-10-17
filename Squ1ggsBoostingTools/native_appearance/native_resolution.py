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

from typing import Dict, List, Tuple
from pathlib import Path
import json
import time
from mods_base import ENGINE, get_pc, open_in_mod_dir
from unrealsdk import find_class, make_struct
_LOADED_SPAWN_PACKAGES = set()
_FAILED_SPAWN_PACKAGES = set()
with open_in_mod_dir(Path(__file__).parent / "data/bl4_characters.json", binary=True) as _stream:
    _rows = json.load(_stream)
_ACTOR_BODY_PACKAGES = {row["code"].casefold(): tuple(row.get("packages", ())) for row in _rows}
del _rows

def _actor_body_packages(actor_def: str) -> Tuple[str, ...]:
    """Real /Game packages for this actor def, from the Nexus body table.

    Freecam look-at only loads a few packages. Guessing /Game/InteractiveObjects
    misses DLC floors and mission doors whose mesh lives somewhere else.
    """
    global _ACTOR_BODY_PACKAGES
    if _ACTOR_BODY_PACKAGES is None:
        loaded: Dict[str, Tuple[str, ...]] = {}
        path = Path(__file__).resolve().parent / "data" / "actor_body_paths.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            _log_warn(f"actor body paths unreadable: {exc}")
            raw = {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                pkgs: List[str] = []
                rows = value if isinstance(value, list) else [value]
                for row in rows:
                    pkg = _spawnai_path_package(str(row or ""))
                    if pkg and pkg not in pkgs:
                        pkgs.append(pkg)
                alias = _alias_key(str(key))
                if alias and pkgs:
                    # Body_ is the uasset that exists. The actor-named path is a
                    # guess and was being tried first, so the real mesh never loaded.
                    pkgs.sort(key=lambda pkg: (
                        0 if pkg.rsplit("/", 1)[-1].lower().startswith("body_")
                        else 1 if pkg.rsplit("/", 1)[-1].lower().startswith("script_")
                        else 2
                    ))
                    loaded[alias] = tuple(pkgs[:3])
        _ACTOR_BODY_PACKAGES = loaded
    return _ACTOR_BODY_PACKAGES.get(_alias_key(actor_def), ())

def _actor_class_packages(actor_def: str) -> Tuple[str, ...]:
    """Packages that own the actor blueprint, not just the Body_ mesh."""
    wanted = _alias_key(actor_def)
    pkgs = list(_actor_body_packages(actor_def))
    if not pkgs:
        return ()
    def _rank(pkg: str) -> Tuple[int, str]:
        leaf = pkg.rsplit("/", 1)[-1].lower()
        if leaf == wanted or leaf == f"{wanted}_c":
            return (0, leaf)
        for prefix in ("char_", "io_", "actor_", "vehicle_", "vh_", "proj_", "pickup_"):
            if leaf.startswith(prefix):
                return (1, leaf)
        if leaf.startswith("body_") or leaf.startswith("script_"):
            return (3, leaf)
        return (2, leaf)
    pkgs.sort(key=_rank)
    return tuple(pkgs)

def _alias_key(name: str) -> str:
    return name.strip().lower().replace(" ", "").replace("-", "_")

def _alive_actors_for_spawner_component(comp: Any) -> List[Any]:
    for args in ((0, False), (0, True)):
        try:
            actors = comp.GetAliveActors(*args)
            try:
                return [actors[i] for i in range(len(actors))]
            except Exception:
                return list(actors)
        except Exception:
            continue
    return []

def _call_load_package(package: str, flags: int = 0) -> Any:
    try:
        try:
            return unrealsdk_load_package(package, int(flags))
        except TypeError:
            return unrealsdk_load_package(package)
    except NameError:
        import unrealsdk as _unrealsdk

        try:
            return _unrealsdk.load_package(package, int(flags))
        except TypeError:
            return _unrealsdk.load_package(package)

def _class_for_actor_name(actor_def: str) -> Any | None:
    """Resolve a spawnable class from a native def, registry, then actor packages."""
    wanted = str(actor_def or "").strip()
    if not wanted:
        return None
    for name in (wanted, f"{wanted}_C"):
        try:
            cls = find_class(name)
        except Exception:
            cls = None
        if cls is not None:
            return _usable_spawn_class(cls) or cls
        for type_name in (
            "BlueprintGeneratedClass",
            "GbxActorScriptClass",
            "Class",
            "GbxActorDef",
            "OakActorDef",
            "GbxCharacterDef",
            "OakCharacterDef",
        ):
            try:
                obj = find_object(type_name, name)
            except Exception:
                obj = None
            found = _usable_spawn_class(obj)
            if found is not None:
                return found
    # AssetRegistryHelpers.GetAsset loads through the engine asset path, which
    # can succeed when unrealsdk.load_package returns None on instance maps.
    found = _class_from_registry(wanted)
    if found is not None:
        return found
    # Name lookup through the same FGbxDefPtr table OakSpawner uses.
    try:
        shell = _make_actor_def_shell(wanted)
    except Exception:
        shell = None
    found = _usable_spawn_class(shell)
    if found is not None:
        return found
    paths: List[str] = []
    for bit in (
        str(shell or ""),
        str(getattr(shell, "_experimental_instance", "") or "") if shell is not None else "",
    ):
        for path in _cooked_paths_in(bit):
            if path not in paths:
                paths.append(path)
    registry = None
    try:
        helpers = find_class("AssetRegistryHelpers")
        cdo = getattr(helpers, "ClassDefaultObject", None) if helpers is not None else None
        registry = cdo.GetAssetRegistry() if cdo is not None else None
    except Exception:
        registry = None
    assets = None
    if registry is not None:
        for method_name in ("GetAssetsByName", "K2_GetAssetsByName"):
            method = getattr(registry, method_name, None)
            if not callable(method):
                continue
            try:
                assets = method(wanted)
                break
            except TypeError:
                try:
                    assets = method(wanted, True)
                    break
                except Exception:
                    continue
            except Exception:
                continue
    try:
        rows = list(assets or [])
    except Exception:
        rows = [assets] if assets is not None else []
    for row in rows[:8]:
        bits = [str(row)]
        for attr in ("ObjectPath", "PackageName", "AssetName", "SoftObjectPath", "PackagePath"):
            try:
                bits.append(str(getattr(row, attr, "") or ""))
            except Exception:
                continue
        for bit in bits:
            for path in _cooked_paths_in(bit):
                if path not in paths:
                    paths.append(path)
            text = str(bit or "").strip()
            if text.startswith("/Game/") and "/Game/" not in "".join(_cooked_paths_in(text)):
                candidate = text if "." in text else f"{text}.{wanted}"
                if candidate not in paths:
                    paths.append(candidate)
    # Actor blueprint packages first. Body_ is mesh-only and is not a spawn class.
    for pkg in _actor_class_packages(wanted)[:3]:
        asset = pkg.rsplit("/", 1)[-1]
        for path in (f"{pkg}.{asset}_C", f"{pkg}.{wanted}_C", f"{pkg}.{wanted}", pkg):
            if path not in paths:
                paths.append(path)
    for path in paths[:6]:
        found = _try_soft_load_class(path)
        if found is not None:
            return found
    return None

def _class_from_registry(wanted: str) -> Any | None:
    """Resolve a spawn class by loading AssetData rows (GetAsset), not load_package."""
    for row in _registry_named_assets(wanted)[:12]:
        obj = _registry_get_asset(row)
        found = _usable_spawn_class(obj)
        if found is not None:
            _log_info(f"registry GetAsset class for {wanted!r} -> {found}")
            return found
        bits = [str(row)]
        for attr in ("ObjectPath", "PackageName", "AssetName", "SoftObjectPath", "PackagePath"):
            try:
                bits.append(str(getattr(row, attr, "") or ""))
            except Exception:
                continue
        for bit in bits:
            for path in _cooked_paths_in(bit):
                found = _try_soft_load_class(path)
                if found is not None:
                    return found
            text = str(bit or "").strip()
            if text.startswith("/Game/"):
                candidate = text if "." in text else f"{text}.{wanted}"
                found = _try_soft_load_class(candidate)
                if found is not None:
                    return found
    return None

def _console_exec_one(cmd: str, world: Any, pc: Any) -> bool:
    for path in ("KismetSystemLibrary", "Engine.KismetSystemLibrary"):
        try:
            cls = find_class(path)
        except Exception:
            cls = None
        if cls is None:
            continue
        cdo = getattr(cls, "ClassDefaultObject", None)
        fn = getattr(cdo, "ExecuteConsoleCommand", None) if cdo is not None else None
        if not callable(fn):
            continue
        for args in ((world, cmd, pc), (world, cmd), (pc, cmd)):
            if args[0] is None:
                continue
            try:
                fn(*args)
                _log_info(f"console load sent: {cmd}")
                return True
            except TypeError:
                continue
            except Exception as exc:
                _log_warn(f"console load failed ({cmd}): {exc}")
                return False
    return False

def _console_load_package(package: str) -> bool:
    """Ask the game loader to pull a package the SDK LoadPackage call missed.

    ExecuteConsoleCommand returning without an error does not mean the package
    loaded. Callers must load_package again and keep the result.
    """
    package = str(package or "").strip()
    if not package:
        return False
    asset = package.rsplit("/", 1)[-1]
    commands = (
        f"obj load {package}",
        f"obj load {package}.{asset}",
    )
    pc = get_pc()
    world = None
    try:
        gv = getattr(ENGINE, "GameViewport", None)
        world = getattr(gv, "World", None) if gv is not None else None
    except Exception:
        world = None
    sent = False
    for cmd in commands:
        if _console_exec_one(cmd, world, pc):
            sent = True
            break
    return sent

def _cooked_paths_in(text: str) -> List[str]:
    raw = str(text or "")
    out: List[str] = []
    start = 0
    while True:
        i = raw.find("/Game/", start)
        if i < 0:
            break
        j = i
        while j < len(raw) and raw[j] not in " \t\r\n'\"<>":
            j += 1
        path = raw[i:j].rstrip(".,)")
        if path and path not in out:
            out.append(path)
        start = max(j, i + 6)
    return out

def _legacy_fgbx_def_ptr(name: str, ref: Any) -> Any:
    import unrealsdk as _unrealsdk

    try:
        ptr = _unrealsdk.unreal.FGbxDefPtr(name, type=ref or "GbxActorDef")
        return ptr
    except Exception:
        pass
    shell = _unrealsdk.unreal.FGbxDefPtr(name)
    if ref is not None:
        try:
            shell._experimental_ref = ref
        except Exception:
            pass
    try:
        shell._experimental_name = name
    except Exception:
        pass
    return shell

def _load_one_spawn_package(package: str) -> bool:
    """Load one actor package. Try the long name and Package.Asset.

    On the dev testing map a miss is not cached. The last dump blacklisted
    Body_BruceBuddy and the flowers body after one empty LoadPackage, so the
    rest of that session never tried again.
    """
    package = _spawnai_path_package(str(package or ""))
    if not package:
        return False
    if package in _LOADED_SPAWN_PACKAGES:
        return True
    if package in _FAILED_SPAWN_PACKAGES:
        return False
    asset = package.rsplit("/", 1)[-1]
    names = (package, f"{package}.{asset}")
    result = None
    # Thin maps: one quick try. Sleeps + flag fans hitch the click and still miss.
    flag_passes = (0,) if not _mesh_already_streamed() else (0, 1, 2)
    for flags in flag_passes:
        for name in names:
            try:
                result = _call_load_package(name, flags)
            except Exception as exc:
                _log_warn(f"load_package {name} failed: {exc}")
                result = None
            if result is not None:
                break
        if result is not None:
            break
    if result is None and _mesh_already_streamed():
        _console_load_package(package)
        time.sleep(0.08)
        for flags in (0, 1):
            try:
                result = _call_load_package(package, flags)
            except Exception:
                result = None
            if result is not None:
                break
        # Console load can mount the package while the SDK still returns None.
        if result is None:
            for type_name in ("Package", "Object"):
                try:
                    result = find_object(type_name, package)
                except Exception:
                    result = None
                if result is not None:
                    break
    if result is not None:
        _LOADED_SPAWN_PACKAGES.add(package)
        _FAILED_SPAWN_PACKAGES.discard(package)
        _log_info(f"load_package {package} -> {result}")
        return True
    if _on_dev_testing_map():
        _log_warn(f"load_package {package} returned no package on Dev Testing Map")
        return False
    _FAILED_SPAWN_PACKAGES.add(package)
    _log_warn(f"load_package {package} returned no package; skipping retries this session")
    return False

def _make_actor_def_shell(actor_def: str) -> Any:
    name = str(actor_def or "").strip()
    if not name:
        return None
    import unrealsdk as _unrealsdk

    ref = find_object("ScriptStruct", "/Script/GbxSpawn.GbxActorDef")
    # Empty ptr + name/ref assignment is the thin-air form that resolves the def
    # table without a constructor type argument.
    try:
        shell = _unrealsdk.unreal.FGbxDefPtr()
        try:
            shell._experimental_name = name
        except Exception:
            pass
        if ref is not None:
            try:
                shell._experimental_ref = ref
            except Exception:
                pass
        if str(getattr(shell, "_experimental_name", "") or "") == name:
            return shell
    except Exception:
        pass
    try:
        from gbx_def_ptr_helpers import build_actor_fgbx_def_ptr  # noqa: PLC0415

        shell = build_actor_fgbx_def_ptr(name)
        if shell is not None:
            return shell
    except Exception:
        pass
    for type_arg in (ref, "GbxActorDef", "/Script/GbxSpawn.GbxActorDef"):
        if type_arg is None:
            continue
        try:
            return _unrealsdk.unreal.FGbxDefPtr(name, type=type_arg)
        except Exception:
            continue
    try:
        return _legacy_fgbx_def_ptr(name, ref)
    except Exception:
        return None

def _mesh_already_streamed() -> bool:
    """Open worlds already have actor meshes. Mission/instance maps often do not."""
    if _on_dev_testing_map():
        return False
    blobs: List[str] = []
    try:
        gv = getattr(ENGINE, "GameViewport", None)
        world = getattr(gv, "World", None) if gv is not None else None
        blobs.append(str(world or ""))
    except Exception:
        pass
    try:
        pc = get_pc()
        pawn = getattr(pc, "Pawn", None) if pc is not None else None
        blobs.append(str(pawn or ""))
    except Exception:
        pass
    blob = " ".join(blobs).lower()
    # Main open worlds stream actor bodies for PushActorDef. Small instance maps
    # (Vision Quest, elevators, intro, mission CoS, etc.) often leave total=1.
    open_world_tokens = (
        "world_p",
        "elpis_p",
        "fortress_",
        "vault_",
        "uppercity",
        "cowbell_p",
        "banjo_p",
        "cello_p",
        "harmonica_p",
        "harp_p",
        "viola_p",
        "tuba_p",
        "raid1_p",
        "raid2_p",
    )
    return any(token in blob for token in open_world_tokens)

def _on_dev_testing_map() -> bool:
    """True when the pawn or world is the vision-quest dev map.

    That map does not already have NPC and IO meshes in memory. A shell fired
    before the body package loads has nothing to draw.
    """
    blobs: List[str] = []
    try:
        gv = getattr(ENGINE, "GameViewport", None)
        world = getattr(gv, "World", None) if gv is not None else None
        blobs.append(str(world or ""))
    except Exception:
        pass
    try:
        pc = get_pc()
        pawn = getattr(pc, "Pawn", None) if pc is not None else None
        blobs.append(str(pawn or ""))
    except Exception:
        pass
    blob = " ".join(blobs)
    return "Bespoke_VisionQuest" in blob or "bespoke_visionquest" in blob.lower()

def _registry_get_asset(row: Any) -> Any | None:
    """Load a UObject from AssetData via AssetRegistryHelpers.GetAsset."""
    if row is None:
        return None
    cdo = _registry_helpers_cdo()
    if cdo is None:
        return None
    method = getattr(cdo, "GetAsset", None)
    if not callable(method):
        return None
    for args in ((row,), (row, False), (row, True)):
        try:
            return method(*args)
        except TypeError:
            continue
        except Exception:
            return None
    return None

def _registry_helpers_cdo() -> Any | None:
    try:
        helpers = find_class("AssetRegistryHelpers")
    except Exception:
        helpers = None
    if helpers is None:
        return None
    return getattr(helpers, "ClassDefaultObject", None)

def _registry_named_assets(wanted: str) -> List[Any]:
    wanted = str(wanted or "").strip()
    if not wanted:
        return []
    cdo = _registry_helpers_cdo()
    if cdo is None:
        return []
    try:
        registry = cdo.GetAssetRegistry()
    except Exception:
        registry = None
    if registry is None:
        return []
    assets = None
    for method_name in ("GetAssetsByName", "K2_GetAssetsByName"):
        method = getattr(registry, method_name, None)
        if not callable(method):
            continue
        try:
            assets = method(wanted)
            break
        except TypeError:
            try:
                assets = method(wanted, True)
                break
            except Exception:
                continue
        except Exception:
            continue
    try:
        rows = list(assets or [])
    except Exception:
        rows = [assets] if assets is not None else []
    # Also ask by package name for curated Char_/IO_ paths.
    for pkg in _actor_class_packages(wanted)[:3]:
        leaf = pkg.rsplit("/", 1)[-1]
        method = getattr(registry, "GetAssetsByPackageName", None)
        if not callable(method):
            continue
        for name in (pkg, leaf):
            try:
                more = method(name)
            except TypeError:
                try:
                    more = method(name, False)
                except Exception:
                    continue
            except Exception:
                continue
            try:
                rows.extend(list(more or []))
            except Exception:
                if more is not None:
                    rows.append(more)
    out: List[Any] = []
    seen: set[int] = set()
    for row in rows:
        if row is None:
            continue
        key = id(row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out

def _soft_path_text(value: Any) -> str:
    texts = [str(value or "")]
    for attr in ("AssetPathName", "AssetPath", "ObjectPath", "Path", "PathName", "Name"):
        try:
            texts.append(str(getattr(value, attr, "") or ""))
        except Exception:
            continue
    for text in texts:
        for path in _cooked_paths_in(text):
            return path
    return ""

def _spawnai_path_package(path: str) -> str:
    """Normalize /Game/Foo.Asset_C into /Game/Foo for load_package."""
    path = str(path or "").strip()
    if not path:
        return ""
    if "." in path:
        path = path.split(".", 1)[0]
    if path.endswith("_C"):
        path = path[:-2]
    return path

def _try_soft_load_class(path: str) -> Any | None:
    """Resolve a cooked SoftObject/Class path without requiring load_package success."""
    path = str(path or "").strip().strip("'\"")
    if not path.startswith("/Game/"):
        return None
    package = path.split(".", 1)[0]
    asset = path.rsplit(".", 1)[-1] if "." in path else path.rsplit("/", 1)[-1]
    _load_one_spawn_package(package)
    object_path = path if "." in path else f"{package}.{asset}"
    for candidate in (object_path, f"{object_path}_C" if not object_path.endswith("_C") else object_path):
        for type_name in (
            "BlueprintGeneratedClass",
            "GbxActorScriptClass",
            "Class",
            "Blueprint",
            "GbxActorDef",
            "OakActorDef",
            "GbxCharacterDef",
            "OakCharacterDef",
        ):
            try:
                obj = find_object(type_name, candidate)
            except Exception:
                obj = None
            found = _usable_spawn_class(obj)
            if found is not None:
                return found
        try:
            cls = find_class(candidate.rsplit(".", 1)[-1])
        except Exception:
            cls = None
        if cls is not None:
            return _usable_spawn_class(cls) or cls
    # SoftObjectPath TryLoad when the SDK exposes it.
    try:
        soft = make_struct("SoftObjectPath")
    except Exception:
        soft = None
    if soft is not None:
        for attr, value in (("AssetPathName", path), ("Path", path)):
            try:
                setattr(soft, attr, value)
            except Exception:
                continue
        for method_name in ("TryLoad", "LoadSynchronous", "ResolveObject"):
            method = getattr(soft, method_name, None)
            if not callable(method):
                continue
            try:
                obj = method()
            except TypeError:
                try:
                    obj = method(None)
                except Exception:
                    continue
            except Exception:
                continue
            found = _usable_spawn_class(obj)
            if found is not None:
                return found
    return None

def _usable_spawn_class(obj: Any, depth: int = 0) -> Any | None:
    """Turn a loaded def or blueprint into a class deferred-spawn will accept."""
    if obj is None or depth > 4:
        return None
    class_name = str(getattr(getattr(obj, "Class", None), "Name", "") or "")
    type_name = type(obj).__name__
    obj_name = str(getattr(obj, "Name", "") or "")
    if "BlueprintGenerated" in class_name or "BlueprintGenerated" in type_name:
        return obj
    if class_name in ("Class", "GbxActorScriptClass") or (
        "Class" in type_name and obj_name and not obj_name.endswith("Def")
    ):
        if obj_name.endswith("_C") or class_name in ("Class", "GbxActorScriptClass"):
            return obj
    inst = getattr(obj, "_experimental_instance", None)
    if inst is not None and inst is not obj:
        found = _usable_spawn_class(inst, depth + 1)
        if found is not None:
            return found
    for attr in (
        "GeneratedClass",
        "ActorClass",
        "PawnClass",
        "CharacterClass",
        "DefaultActorClass",
        "NativeClass",
        "Blueprint",
        "GeneratedBlueprint",
        "ActorBlueprint",
        "SoftClass",
        "ActorSoftClass",
        "CharacterSoftClass",
    ):
        try:
            child = getattr(obj, attr, None)
        except Exception:
            child = None
        if child is None or child is obj:
            continue
        if attr in ("SoftClass", "ActorSoftClass", "CharacterSoftClass"):
            soft_path = _soft_path_text(child)
            if soft_path:
                found = _try_soft_load_class(soft_path)
                if found is not None:
                    return found
            continue
        found = _usable_spawn_class(child, depth + 1)
        if found is not None:
            return found
    try:
        cdo = getattr(obj, "ClassDefaultObject", None)
    except Exception:
        cdo = None
    if cdo is not None and cdo is not obj:
        owner = getattr(cdo, "Class", None)
        if owner is not None and owner is not obj:
            found = _usable_spawn_class(owner, depth + 1)
            if found is not None:
                return found
    # Native def string often embeds the cooked /Game path even when unloaded.
    for bit in (str(obj), obj_name, class_name):
        for path in _cooked_paths_in(bit):
            found = _try_soft_load_class(path)
            if found is not None:
                return found
    return None

def _world_from_pc(pc: Any) -> Any:
    try:
        gv = getattr(ENGINE, "GameViewport", None)
        world = getattr(gv, "World", None) if gv is not None else None
        if world is not None:
            return world
    except Exception:
        pass
    try:
        return getattr(pc, "World", None)
    except Exception:
        return None
