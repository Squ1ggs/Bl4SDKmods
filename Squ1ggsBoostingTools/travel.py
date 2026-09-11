
"""Map and travel-station helpers for Squ1ggs's Boosting Tools.

This intentionally keeps only the travel pieces needed by the BLImGui menu.
"""
from __future__ import annotations

import json
import pkgutil
import time
from typing import Any

from mods_base import ENGINE, get_pc
from unrealsdk import find_class, logging

_PREFIX = "[Squ1ggs's Boosting Tools | Travel]"
_DEFAULT_MAP_ROWS: list[dict[str, str]] = [
    {"map": "World_P", "display_name": "World_P - Main World"},
    {"map": "Elpis_P", "display_name": "Elpis_P - Elpis"},
    {"map": "Elpiselevator_P", "display_name": "Elpiselevator_P - Elpis Elevator"},
    {"map": "Intro_P", "display_name": "Intro_P - Tutorial Level"},
    {"map": "FrontEnd_P", "display_name": "FrontEnd_P - Title Screen World"},
    {"map": "Cello_P", "display_name": "Cello_P - Bounty Pack 2 DLC"},
    {"map": "Raid1_P", "display_name": "Raid1_P - Bloomreaper DLC"},
    {"map": "Raid2_P", "display_name": "Raid2_P - Raid 2"},
    {"map": "Tuba_P", "display_name": "Tuba_P - Tuba DLC"},
    {"map": "Mandolin1_P", "display_name": "Mandolin1_P - Mandolin DLC"},
    {"map": "Cowbell_P", "display_name": "Cowbell_P - Mad Ellie DLC Main World"},
    {"map": "Banjo_P", "display_name": "Banjo_P - Bounty Pack 1 DLC"},
    {"map": "Harp_P", "display_name": "Harp_P - Harp DLC"},
    {"map": "VaultoftheDamned_P", "display_name": "VaultoftheDamned_P - Mad Ellie DLC Vault"},
    {"map": "Fortress_Grasslands_P", "display_name": "Fortress_Grasslands_P - Idolator Sol Map"},
    {"map": "Fortress_Shatteredlands_P", "display_name": "Fortress_Shatteredlands_P - Callis the Ripper Queen Map"},
    {"map": "Fortress_Mountains_P", "display_name": "Fortress_Mountains_P - Vile Lictor Map"},
    {"map": "Vault_Grasslands_P", "display_name": "Vault_Grasslands_P - Fadefields Vault"},
    {"map": "Vault_Mountains_P", "display_name": "Vault_Mountains_P - Terminus Range Vault"},
    {"map": "Vault_ShatteredLands_P", "display_name": "Vault_ShatteredLands_P - Carcadia Burn Vault"},
    {"map": "UpperCity_P", "display_name": "UpperCity_P - Upper Dominion"},
    {"map": "bespoke_visionquest", "display_name": "bespoke_visionquest - Dev Testing Map"},
]

# These worlds can exist in extracted data but are not safe public fast-travel
# destinations. In particular, FrontEnd/Intro are lifecycle worlds and the
# vision-quest map is explicitly development content.
_BLOCKED_TRAVEL_MAPS = {
    "frontend_p",
    "intro_p",
    "mandolin1_p",
    "tuba_p",
}

_STATION_CACHE: list[dict[str, str]] | None = None
_MAP_CACHE: list[dict[str, str]] | None = None
_PENDING_TRAVEL: tuple[str, str, float] | None = None
_PENDING_TELEPORT: tuple[float, float, float, float, str, float] | None = None
# x, y, z, yaw, expect_world (normalized), execute_at
_POST_TELEPORT_AFTER_TRAVEL: tuple[float, float, float, float, str, float] | None = None
_TRAVEL_HOOK_READY = False
_TRAVEL_HOOK_ERROR = ""
_TRAVEL_DELAY_SECONDS = 0.50

# Curated one-click destinations: station/map travel + deferred teleport to arena coords.
TRAVEL_DESTINATION_PRESETS: list[dict[str, Any]] = [
    {
        "id": "tuba_boss_arena",
        "label": "Tuba Boss Arena",
        "description": (
            "Tuba DLC boss pool (teleport only if already on Tuba_P; else LT_DLC_Tuba + arena TP). "
            "Resurrect stations near the pool are world objects, not catalog fast-travel IDs."
        ),
        "travel_cmd": "gbx.servertraveltostation Tuba_P.LT_DLC_Tuba",
        "expect_world": "Tuba_P",
        "x": 131621.31,
        "y": -96302.90,
        "z": -20786.09,
        "yaw": 0.0,
        "teleport_delay": 4.0,
    },
    {
        "id": "dev_testing_map",
        "label": "Dev Testing Map",
        "description": "Travel to bespoke_visionquest (Dev Testing Map).",
        "travel_cmd": "gbx.servertraveltomap bespoke_visionquest",
        "expect_world": "bespoke_visionquest",
        "x": 0.0,
        "y": 0.0,
        "z": 200.0,
        "yaw": 0.0,
        "teleport_delay": 3.0,
    },
]


def _norm_map_name(value: str) -> str:
    return str(value or '').strip().lower()


def canonical_travel_map_name(map_name: str) -> str:
    """Return the deduped/canonical map name for case-variant map ids."""
    needle = _norm_map_name(map_name)
    if not needle:
        return str(map_name or '').strip()
    for row in load_travel_maps():
        if _norm_map_name(str(row.get('map', ''))) == needle:
            return str(row.get('map', map_name))
    return str(map_name or '').strip()


def _display_with_canonical_map_name(display: str, canonical: str, original: str) -> str:
    display = str(display or canonical).strip()
    original = str(original or '').strip()
    canonical = str(canonical or original).strip()
    if original and canonical and display.startswith(original):
        return canonical + display[len(original):]
    return display


def _log(message: str) -> None:
    logging.info(f"{_PREFIX} {message}")


def _world_context(pc: Any) -> Any:
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


def _try_call(label: str, fn: Any, cmd: str, pc: Any) -> bool:
    if not callable(fn):
        return False
    for args in ((cmd,), (cmd, True), (cmd, False), (cmd, pc)):
        try:
            fn(*args)
            _log(f"{label} ok: {cmd}")
            return True
        except TypeError:
            continue
        except Exception as exc:
            _log(f"{label} failed ({cmd}): {exc!r}")
            return False
    return False


def _try_kismet_execute(cmd: str, world: Any, pc: Any) -> bool:
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
        contexts: list[Any] = []
        if world is not None:
            contexts.append(world)
        if pc is not None:
            contexts.append(pc)
        try:
            gv = getattr(ENGINE, "GameViewport", None)
            if gv is not None:
                contexts.append(gv)
        except Exception:
            pass
        seen: set[int] = set()
        for ctx in contexts:
            if ctx is None or id(ctx) in seen:
                continue
            seen.add(id(ctx))
            for args in ((ctx, cmd, pc), (ctx, cmd)):
                try:
                    fn(*args)
                    _log(f"KismetSystemLibrary.ExecuteConsoleCommand ok: {cmd}")
                    return True
                except TypeError:
                    continue
                except Exception as exc:
                    _log(f"Kismet ExecuteConsoleCommand failed ({cmd}): {exc!r}")
                    return False
    return False


def _try_viewport_console(cmd: str, pc: Any) -> bool:
    try:
        gv = getattr(ENGINE, "GameViewport", None)
        vc = getattr(gv, "ViewportConsole", None) if gv is not None else None
    except Exception:
        vc = None
    if vc is None:
        return False
    for name in ("ConsoleCommand", "SendToConsole"):
        if _try_call(f"ViewportConsole.{name}", getattr(vc, name, None), cmd, pc):
            return True
    return False


def _try_engine_exec(cmd: str, world: Any) -> bool:
    fn = getattr(ENGINE, "Exec", None)
    if not callable(fn):
        return False
    for ctx in (world, getattr(ENGINE, "GameViewport", None), ENGINE):
        if ctx is None:
            continue
        try:
            out = fn(ctx, cmd)
        except TypeError:
            continue
        except Exception as exc:
            _log(f"ENGINE.Exec failed ({cmd}): {exc!r}")
            return False
        if out is False:
            continue
        _log(f"ENGINE.Exec ok: {cmd} (returned {out!r})")
        return True
    return False


def _exec_console(cmd: str) -> bool:
    pc = get_pc()
    if pc is None:
        raise RuntimeError("No PlayerController available.")
    world = _world_context(pc)
    if _try_kismet_execute(cmd, world, pc):
        return True
    if _try_viewport_console(cmd, pc):
        return True
    if _try_engine_exec(cmd, world):
        return True
    if _try_call("PlayerController.ServerExec", getattr(pc, "ServerExec", None), cmd, pc):
        return True
    if str(cmd).lstrip().lower().startswith("gbx.") and _try_call(
        "PlayerController.ServerGbxConsoleCommand",
        getattr(pc, "ServerGbxConsoleCommand", None),
        cmd,
        pc,
    ):
        return True
    for name in ("SendToConsole", "ConsoleCommand"):
        if _try_call(f"PlayerController.{name}", getattr(pc, name, None), cmd, pc):
            return True
    raise RuntimeError("Could not run travel console command.")


def _validate_host_context() -> None:
    pc = get_pc()
    if pc is None:
        raise RuntimeError("Load into an active game before travelling.")
    world = _world_context(pc)
    if world is None or getattr(world, "GameState", None) is None:
        raise RuntimeError("The active world is not ready for travel.")
    try:
        if not bool(pc.HasAuthority()):
            raise RuntimeError("Fast travel must be requested by the host.")
    except RuntimeError:
        raise
    except Exception:
        pass


def _current_world_map_name() -> str:
    pc = get_pc()
    if pc is None:
        return ""
    world = _world_context(pc)
    if world is None:
        return ""
    for attr in ("Name",):
        try:
            name = str(getattr(world, attr, "") or "")
            if name:
                return name.split(".")[0]
        except Exception:
            pass
    try:
        return str(world).split(".")[-1].split(":")[0]
    except Exception:
        return ""


def _make_travel_vector(x: float, y: float, z: float) -> Any:
    try:
        library = find_class("KismetMathLibrary").ClassDefaultObject
        return library.MakeVector(float(x), float(y), float(z))
    except Exception:
        return None


def teleport_local_pawn_to(
    x: float,
    y: float,
    z: float,
    *,
    yaw: float = 0.0,
) -> str:
    """Teleport the local player pawn to world coordinates (no debug cam required)."""
    pc = get_pc()
    if pc is None:
        raise RuntimeError("No PlayerController available.")
    pawn = None
    for attr in ("Pawn", "AcknowledgedPawn", "Character"):
        try:
            pawn = getattr(pc, attr, None)
        except Exception:
            pawn = None
        if pawn is not None:
            break
    if pawn is None:
        raise RuntimeError("No local pawn to teleport.")
    location = _make_travel_vector(x, y, z)
    if location is None:
        raise RuntimeError("Could not build a location vector for teleport.")
    rotation = None
    try:
        rotation = pawn.K2_GetActorRotation()
    except Exception:
        rotation = None
    if rotation is not None and yaw:
        try:
            rotation.Yaw = float(yaw)
        except Exception:
            pass
    ok = False
    try:
        ok = bool(pawn.K2_TeleportTo(location, rotation))
    except Exception:
        ok = False
    if not ok:
        try:
            ok = bool(pawn.K2_SetActorLocation(location, False, None, False))
        except Exception as exc:
            raise RuntimeError(f"Teleport failed: {exc!r}") from exc
    if not ok:
        raise RuntimeError("Teleport RPC returned false.")
    _log(f"Teleported local pawn to ({x:g}, {y:g}, {z:g}).")
    return f"Teleported to ({x:g}, {y:g}, {z:g})."


def list_travel_presets() -> list[dict[str, Any]]:
    return [dict(row) for row in TRAVEL_DESTINATION_PRESETS]


def _find_travel_preset(preset_id: str) -> dict[str, Any] | None:
    needle = str(preset_id or "").strip().casefold()
    if not needle:
        return None
    for row in TRAVEL_DESTINATION_PRESETS:
        if str(row.get("id", "")).casefold() == needle:
            return row
        if str(row.get("label", "")).casefold() == needle:
            return row
    return None


def travel_to_preset(preset_id: str) -> str:
    """One-click curated destination — travel if needed, then teleport to arena coords."""
    preset = _find_travel_preset(preset_id)
    if preset is None:
        raise RuntimeError(f"Unknown travel preset {preset_id!r}.")
    expect = _norm_map_name(str(preset.get("expect_world", "")))
    here = _norm_map_name(_current_world_map_name())
    x = float(preset.get("x", 0.0))
    y = float(preset.get("y", 0.0))
    z = float(preset.get("z", 0.0))
    yaw = float(preset.get("yaw", 0.0) or 0.0)
    label = str(preset.get("label") or preset_id)
    if expect and here == expect:
        return teleport_local_pawn_to(x, y, z, yaw=yaw)
    cmd = str(preset.get("travel_cmd") or "").strip()
    if not cmd:
        raise RuntimeError(f"Preset {label!r} has no travel command.")
    delay = float(preset.get("teleport_delay", 4.0) or 4.0)
    global _POST_TELEPORT_AFTER_TRAVEL
    _POST_TELEPORT_AFTER_TRAVEL = (x, y, z, yaw, expect, 0.0)
    try:
        return _queue_travel(cmd, f"{label} (travel + arena teleport)", teleport_delay=delay)
    except Exception:
        _POST_TELEPORT_AFTER_TRAVEL = None
        raise


def _queue_travel(cmd: str, description: str, *, teleport_delay: float | None = None) -> str:
    global _PENDING_TRAVEL, _POST_TELEPORT_AFTER_TRAVEL
    _validate_host_context()
    install_travel_queue()
    if not _TRAVEL_HOOK_READY:
        raise RuntimeError(
            "The safe game-thread travel queue is unavailable"
            + (f": {_TRAVEL_HOOK_ERROR}" if _TRAVEL_HOOK_ERROR else ".")
        )
    if _PENDING_TRAVEL is not None or _PENDING_TELEPORT is not None:
        raise RuntimeError("Another travel request is already queued.")
    execute_at = time.monotonic() + _TRAVEL_DELAY_SECONDS
    if _POST_TELEPORT_AFTER_TRAVEL is not None and teleport_delay is not None:
        x, y, z, yaw, expect, _ = _POST_TELEPORT_AFTER_TRAVEL
        _POST_TELEPORT_AFTER_TRAVEL = (
            x,
            y,
            z,
            yaw,
            expect,
            execute_at + float(teleport_delay),
        )
    _PENDING_TRAVEL = (
        str(cmd),
        str(description),
        execute_at,
    )
    _log(f"Queued outside BLImGui: {description}")
    return (
        f"Queued {description}. Travel runs on the next game tick "
        "(keep BL4 focused; no need to close the EXE)."
    )


def pending_travel() -> bool:
    return _PENDING_TRAVEL is not None or _PENDING_TELEPORT is not None


def cancel_pending_travel() -> bool:
    global _PENDING_TRAVEL, _PENDING_TELEPORT, _POST_TELEPORT_AFTER_TRAVEL
    changed = False
    if _PENDING_TRAVEL is not None:
        _PENDING_TRAVEL = None
        changed = True
    if _PENDING_TELEPORT is not None:
        _PENDING_TELEPORT = None
        changed = True
    if _POST_TELEPORT_AFTER_TRAVEL is not None:
        _POST_TELEPORT_AFTER_TRAVEL = None
        changed = True
    if changed:
        _log("Cancelled queued travel.")
    return changed


def _schedule_post_travel_teleport() -> None:
    global _PENDING_TELEPORT, _POST_TELEPORT_AFTER_TRAVEL
    pending = _POST_TELEPORT_AFTER_TRAVEL
    _POST_TELEPORT_AFTER_TRAVEL = None
    if pending is None:
        return
    x, y, z, yaw, expect, execute_at = pending
    if execute_at <= 0.0:
        execute_at = time.monotonic() + 4.0
    _PENDING_TELEPORT = (x, y, z, yaw, expect, execute_at)
    _log(f"Scheduled arena teleport to ({x:g}, {y:g}, {z:g}) on {expect or 'any world'}.")


def abort_pending_travel(reason: str = "session teardown") -> None:
    """Drop deferred travel / teleport without executing during menu load."""
    global _PENDING_TRAVEL, _PENDING_TELEPORT
    had = _PENDING_TRAVEL is not None or _PENDING_TELEPORT is not None
    _PENDING_TRAVEL = None
    _PENDING_TELEPORT = None
    if had:
        _log(f"Deferred travel cleared ({reason}).")


def _travel_queue_tick(*_args: Any, **_kwargs: Any) -> None:
    """Execute deferred travel on the game thread (EXE or in-game panel).

    Brief session_safe blips must not cancel a queued travel — teardown hooks
    already call abort_pending_travel. Skipping until safe avoids the Dev Map
    \"nothing happened\" no-op.
    """
    try:
        from .session_guards import session_safe

        if not session_safe():
            return
    except Exception:
        pass
    global _PENDING_TRAVEL, _PENDING_TELEPORT
    pending_tp = _PENDING_TELEPORT
    if pending_tp is not None and time.monotonic() >= pending_tp[5]:
        _PENDING_TELEPORT = None
        x, y, z, yaw, expect, _at = pending_tp
        here = _norm_map_name(_current_world_map_name())
        if expect and here and here != expect:
            _log(f"Deferred teleport skipped — expected {expect!r}, currently {here!r}.")
        else:
            try:
                msg = teleport_local_pawn_to(x, y, z, yaw=yaw)
                _log(f"Deferred teleport ok: {msg}")
            except Exception as exc:
                _log(f"Deferred teleport failed: {type(exc).__name__}: {exc}")
        return

    pending = _PENDING_TRAVEL
    if pending is None or time.monotonic() < pending[2]:
        return
    _PENDING_TRAVEL = None
    cmd, description, _execute_at = pending
    try:
        _validate_host_context()
        _exec_console(cmd)
        _log(f"Executed deferred travel: {description}")
        _schedule_post_travel_teleport()
    except Exception as exc:
        global _POST_TELEPORT_AFTER_TRAVEL
        _POST_TELEPORT_AFTER_TRAVEL = None
        _log(f"Deferred travel failed ({description}): {type(exc).__name__}: {exc}")


def install_travel_queue() -> bool:
    global _TRAVEL_HOOK_READY, _TRAVEL_HOOK_ERROR
    if _TRAVEL_HOOK_READY:
        return True
    # mobility_runtime owns SQBT's single proven UMG dispatcher and invokes
    # _travel_queue_tick, avoiding another always-on Python hook.
    _TRAVEL_HOOK_READY = True
    _TRAVEL_HOOK_ERROR = ""
    return _TRAVEL_HOOK_READY


def load_travel_stations() -> list[dict[str, str]]:
    global _STATION_CACHE
    if _STATION_CACHE is not None:
        return list(_STATION_CACHE)
    blob = pkgutil.get_data(__package__ or __name__.rpartition('.')[0], 'travelstations.json')
    if blob is None:
        raise RuntimeError('Could not load travelstations.json from package data.')
    data = json.loads(blob.decode('utf-8'))
    rows = data.get('stations') if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError('travelstations.json must contain a stations list.')
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        station = str(row.get('station', '')).strip()
        world = str(row.get('world', '')).strip()
        if not station:
            continue
        if not world and '.' in station:
            world = station.split('.', 1)[0]
        display = str(row.get('display_name') or (station.split('.', 1)[1] if '.' in station else station)).strip()
        category = str(row.get('category') or 'Standard').strip()
        out.append({
            'station': station,
            'world': world,
            'display_name': display,
            'category': category,
            'typedef': str(row.get('typedef', '')).strip(),
            'dest': str(row.get('dest', '')).strip(),
        })
    _STATION_CACHE = out
    return list(out)


def load_travel_maps() -> list[dict[str, str]]:
    global _MAP_CACHE
    if _MAP_CACHE is not None:
        return list(_MAP_CACHE)

    # Only offer maps in the packaged, asset-derived curated catalog. The old
    # implementation also appended every world mentioned by station extraction,
    # which exposed title/tutorial/dev or otherwise unverified destinations.
    try:
        blob = pkgutil.get_data(
            __package__ or __name__.rpartition('.')[0],
            'travelmaps_flat.json',
        )
        data = json.loads(blob.decode('utf-8')) if blob is not None else {}
        source_rows = data.get('maps') if isinstance(data, dict) else None
    except Exception as exc:
        _log(f"Could not load curated travel map catalog: {exc!r}")
        source_rows = None
    using_fallback = not isinstance(source_rows, list)
    if using_fallback:
        source_rows = _DEFAULT_MAP_ROWS

    curated_by_norm: dict[str, dict[str, str]] = {}
    preferred_norms: list[str] = []
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get('map', '')).strip()
        if not name:
            continue
        norm = _norm_map_name(name)
        if norm in _BLOCKED_TRAVEL_MAPS:
            continue
        if not using_fallback:
            curated = str(row.get('curated_existing', True)).strip().lower()
            cookable = str(row.get('canbecooked', True)).strip().lower()
            if curated in {'false', '0', 'no'} or cookable in {'false', '0', 'no'}:
                continue
        if norm not in curated_by_norm:
            preferred_norms.append(norm)
            curated_by_norm[norm] = {
                'map': name,
                'display_name': str(row.get('display_name') or name),
            }

    station_world_by_norm: dict[str, str] = {}
    for st in load_travel_stations():
        world = str(st.get('world', '')).strip()
        if not world:
            continue
        station_world_by_norm.setdefault(_norm_map_name(world), world)

    merged: dict[str, dict[str, str]] = {}
    for norm, row in curated_by_norm.items():
        original = row['map']
        canonical = station_world_by_norm.get(norm, original)
        merged[norm] = {
            'map': canonical,
            'display_name': _display_with_canonical_map_name(row['display_name'], canonical, original),
        }

    ordered: list[dict[str, str]] = []
    for norm in preferred_norms:
        row = merged.get(norm)
        if row is not None:
            ordered.append(row)

    _MAP_CACHE = ordered
    return list(ordered)


def filter_travel_maps(search: str = '', limit: int = 80) -> list[dict[str, str]]:
    needle = (search or '').strip().lower()
    results: list[dict[str, str]] = []
    for row in load_travel_maps():
        hay = f"{row['map']} {row['display_name']}".lower()
        if needle and needle not in hay:
            continue
        results.append(row)
        if limit > 0 and len(results) >= limit:
            break
    return results


def filter_travel_stations(map_name: str = '', search: str = '', limit: int = 125) -> list[dict[str, str]]:
    needle = (search or '').strip().lower()
    map_name = (map_name or '').strip()
    map_norm = _norm_map_name(map_name)
    show_all = not map_name or map_name == '__ALL__'
    safe_map_norms = {
        _norm_map_name(str(row.get('map', '')))
        for row in load_travel_maps()
    }
    results: list[dict[str, str]] = []
    for row in load_travel_stations():
        row_map_norm = _norm_map_name(str(row.get('world', '')))
        if row_map_norm not in safe_map_norms:
            continue
        if not show_all and row_map_norm != map_norm:
            continue
        hay = f"{row.get('station','')} {row.get('display_name','')} {row.get('world','')}".lower()
        if needle and needle not in hay:
            continue
        results.append(row)
        if limit > 0 and len(results) >= limit:
            break
    return results


def travel_to_map(map_name: str) -> str:
    map_name = str(map_name or '').strip()
    if not map_name:
        raise RuntimeError('No map selected.')
    safe_maps = {
        _norm_map_name(str(row.get('map', ''))): str(row.get('map', '')).strip()
        for row in load_travel_maps()
    }
    map_name = safe_maps.get(_norm_map_name(map_name), '')
    if not map_name:
        raise RuntimeError('That map is not in the safe curated travel catalog.')
    return _queue_travel(f"servertravel {map_name}", f"travel to map {map_name}")


def travel_to_station(station: str) -> str:
    station = str(station or '').strip()
    if not station:
        raise RuntimeError('No travel station selected.')
    safe_map_norms = {
        _norm_map_name(str(row.get('map', '')))
        for row in load_travel_maps()
    }
    matched = next(
        (
            row for row in load_travel_stations()
            if str(row.get('station', '')).strip().casefold() == station.casefold()
        ),
        None,
    )
    if matched is None:
        raise RuntimeError('That travel station is not in the packaged station catalog.')
    if _norm_map_name(str(matched.get('world', ''))) not in safe_map_norms:
        raise RuntimeError('That travel station belongs to an unsafe or unverified map.')
    station = str(matched.get('station', station)).strip()
    return _queue_travel(
        f"gbx.servertraveltostation {station}",
        f"travel to station {station}",
    )


install_travel_queue()
