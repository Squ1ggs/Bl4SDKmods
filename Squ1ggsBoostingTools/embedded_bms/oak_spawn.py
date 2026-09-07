"""BMS spawn backend — BL4 Oak Spawner (oak_spawnai / OakSpawner) with Summon fallbacks.

Borderlands Mob Spawner (BMS) uses this module; keep ``oak_*`` naming for Squ1ggs console lines.
"""



from __future__ import annotations



import logging

import time

from typing import Any



from .spawn_core import (

    clamp_deploy_count,

    effective_spawn_spacing,

    find_new_characters_near,

    is_boss_actor_code,

    player_pawn_keys,

    snapshot_character_keys,

)



_log = logging.getLogger("bl4_mob_spawner_hookedwidget.oak_spawn")



ACTOR_EXTRA_LOADS: dict[str, tuple[str, ...]] = {

    "Char_TubaBoss": (

        "/Game/DLC/Tuba/AI/Bosses/TubaBoss/Char_TubaBoss",

        "/Game/DLC/Tuba/AI/Bosses/TubaBoss/Character/Char_TubaBoss",

        "/Game/DLC/Tuba/AI/Bosses/TubaBoss/Script_TubaBoss",

        "/Game/DLC/Tuba/AI/Bosses/TubaBoss/Script_TubaBoss_WaterBuoyance",

        "/Game/DLC/Tuba/AI/Bosses/Tuba/Char_TubaBoss",

        "/Game/DLC/Tuba/AI/TubaBoss/Char_TubaBoss",

        "/Game/DLC/Tuba/AI/Char_TubaBoss",

        "/Game/DLC/Tuba/Bosses/TubaBoss/Char_TubaBoss",

    ),

    "Char_BigBoss": (

        "/Game/AI/Bosses/BigBoss/Char_BigBoss",

        "/Game/AI/Bosses/BigBoss/Character/Char_BigBoss",

        "/Game/AI/Bosses/BigBoss/Script_BigBoss",

        "/Game/DLC/Raid2/AI/Bosses/GrassBoss/_Design/Script_BigBoss",

    ),

    "Char_BigBoss_TRUE": (

        "/Game/AI/Bosses/BigBoss/Char_BigBoss_TRUE",

        "/Game/AI/Bosses/BigBoss/Character/Char_BigBoss_TRUE",

        "/Game/AI/Bosses/BigBoss/Script_BigBoss",

        "/Game/DLC/Raid2/AI/Bosses/GrassBoss/_Design/Script_BigBoss",

    ),

    "Char_UberBigBoss": (

        "/Game/DLC/Raid2/AI/Bosses/UberGrassBoss/Char_UberBigBoss",

        "/Game/DLC/Raid2/AI/Bosses/UberGrassBoss/Character/Char_UberBigBoss",

        "/Game/DLC/Raid2/AI/Bosses/UberGrassBoss/Script_UberBigBoss",

        "/Game/AI/Bosses/BigBoss/Char_UberBigBoss",

    ),

    "Char_GrassBoss": (

        "/Game/AI/Bosses/GrassBoss/Char_GrassBoss",

        "/Game/AI/Bosses/GrassBoss/Character/Char_GrassBoss",

        "/Game/AI/Bosses/GrassBoss/Script_GrassBoss",

    ),

    "Char_NPC_Claptrap": (

        "/Game/AI/NPC/_Unique/Claptrap/Char_NPC_Claptrap",

        "/Game/AI/NPC/_Unique/Claptrap/_Design/Character/Char_NPC_Claptrap",

        "/Game/AI/NPC/_Unique/Claptrap/Script_NPC_Claptrap",

        "/Game/AI/NPC/_Unique/Claptrap/Model/Rig/SK_Claptrap_Skeleton",

        "/Game/AI/NPC/_Unique/Claptrap/Animation/BPAnim_Claptrap",

    ),

    "IO_VendingMachine_BlackMarket": (

        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine",

        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine_BlackMarket",

        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/BlackMarket/Script_VendingMachine_BlackMarket",

        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/IO_VendingMachine_BlackMarket",

    ),

    "io_VendingMachine_BlackMarket": (

        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine",

        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine_BlackMarket",

        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/BlackMarket/Script_VendingMachine_BlackMarket",

        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/IO_VendingMachine_BlackMarket",

    ),

}





def _actor_load_paths(actor_def: str) -> tuple[str, ...]:

    key = (actor_def or "").strip()

    if not key:

        return ()

    hits = ACTOR_EXTRA_LOADS.get(key)

    if hits:

        return hits

    low = key.lower()

    for name, paths in ACTOR_EXTRA_LOADS.items():

        if name.lower() == low:

            return paths

    return ()





def _normalize_actor_token(code: str) -> str:

    raw = (code or "").strip()

    if not raw:

        return ""

    low = raw.lower()

    for prefix in ("oak_spawnai ", "oak_spawn ", "oak_spawnai ", "oak_spawn "):

        if low.startswith(prefix):

            return raw.split(None, 1)[1].strip() if len(raw.split(None, 1)) > 1 else ""

    if low.startswith("oak_"):

        return raw[4:].strip()

    return raw





def _strip_level_path_prefix(name: str) -> str:

    """``PersistentLevel.Lootable_GoldenChest`` → ``Lootable_GoldenChest``."""

    raw = (name or "").strip()

    if not raw:

        return raw

    low = raw.lower()

    for marker in (":persistentlevel.", ".persistentlevel.", "persistentlevel."):

        idx = low.rfind(marker)

        if idx >= 0:

            return raw[idx + len(marker) :].strip()

    return raw





def _resolve_spawn_name(ssp: Any, name: str) -> str:

    resolve_fn = getattr(ssp, "_resolve_actor_def_name", None)

    if not callable(resolve_fn):

        return name

    try:

        resolved, suggestions = resolve_fn(name)

        if resolved and str(resolved).strip():

            if str(resolved).strip().lower() != str(name).strip().lower():

                _log.info("Resolved %s -> %s (alt: %s)", name, resolved, suggestions[:3])

            return str(resolved).strip()

    except Exception as ex:  # noqa: BLE001

        _log.debug("Actor name resolve failed for %s: %s", name, ex)

    return name





def _is_ai_spawn_code(name: str, ssp: Any) -> bool:

    text = (name or "").strip()

    if not text:

        return False

    low = text.lower()

    if low.startswith("char_") or low.startswith("io_"):

        return True

    looks = getattr(ssp, "_looks_like_actor_def", None)

    if callable(looks):

        try:

            return bool(looks(text))

        except Exception:

            pass

    return False





def _spawn_reference_loc() -> Any | None:

    try:

        from ..item_spawn.spawn_pc import resolve_spawn_pc



        pc = resolve_spawn_pc()

        pawn = getattr(pc, "Pawn", None) if pc is not None else None

        if pawn is None:

            return None

        for meth in ("K2_GetActorLocation", "GetActorLocation"):

            fn = getattr(pawn, meth, None)

            if callable(fn):

                try:

                    return fn()

                except Exception:

                    pass

    except Exception:

        pass

    return None





def _wait_for_spawn(

    before: set[str],

    *,

    expected_code: str,

    radius: float,

    timeout: float,

) -> Any | None:

    deadline = time.monotonic() + max(0.05, float(timeout))

    while time.monotonic() < deadline:

        near = _spawn_reference_loc()

        if near is not None:

            hits = find_new_characters_near(

                before,

                near,

                radius=radius,

                exclude_keys=player_pawn_keys(),

                expected_code=expected_code,

            )

            if hits:

                return hits[0]

        time.sleep(0.12)

    return None





def _spawn_once_deploy(

    actor_def: str,

    *,

    count: int,

    distance: float,

    spacing: float,

) -> tuple[bool, str]:

    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
    except Exception as ex:  # noqa: BLE001

        return False, f"BL4 Oak Spawner import failed: {ex}"



    name = _strip_level_path_prefix(_resolve_spawn_name(ssp, actor_def))

    if not name:

        return False, "empty actor code"



    deploy_fn = getattr(ssp, "_spawn_deployed_actor", None)

    if not callable(deploy_fn):

        return False, "BL4 Oak Spawner deploy path unavailable"



    n = max(1, int(count))

    spc = effective_spawn_spacing(float(spacing), n, actor_code=name)

    try:

        actor = deploy_fn(

            name,

            class_override=None,

            distance=float(distance),

            z_offset=float(getattr(ssp, "_DEFAULT_Z_OFFSET", -100.0)),

            scale=1.0,

            delay=0.0,

            enable=(),

            disable=(),

            generated_only=False,

            activate=False,

            count=n,

            spacing=spc,

        )

    except Exception as ex:  # noqa: BLE001

        return False, f"oak_spawn failed: {ex}"



    if actor is not None:

        return True, f"oak_spawn: {name} -> {actor}"



    # Level-path objects (full UE path) often need raw console forward.

    if "/" in name or ":" in name or "persistentlevel" in name.lower():

        try:

            from gbx_actor_deploy import _pc_console_raw  # noqa: PLC0415



            for cmd in (f"oak_spawn {name}", f"oak_spawn {name}"):

                ok, msg = _pc_console_raw(cmd)

                if ok:

                    return True, str(msg)

        except Exception as ex:  # noqa: BLE001

            _log.debug("console deploy forward failed for %s: %s", name, ex)



    return False, f"Oak Spawner could not deploy {name}. Try: oak_spawn {name}"





def _spawn_once_ai(

    actor_def: str,

    *,

    count: int,

    distance: float,

    spacing: float,

    extra_loads: tuple[str, ...],

    bossish: bool,

    allow_console_fallback: bool,

    fast_path: bool = False,
    async_fire: bool = False,

) -> tuple[bool, str]:

    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
    except Exception as ex:  # noqa: BLE001

        return False, f"BL4 Oak Spawner import failed: {ex}"



    name = _resolve_spawn_name(ssp, actor_def)

    if not name:

        return False, "empty actor code"



    is_large_boss_fn = getattr(ssp, "_is_large_boss_like", None)

    is_boss = bool(bossish)

    if callable(is_large_boss_fn):

        try:

            is_boss = is_boss or bool(is_large_boss_fn(name))

        except Exception:

            is_boss = is_boss or "boss" in name.lower()



    n = max(1, int(count))

    dist = max(float(distance), 900.0) if is_boss else float(distance)

    spc = effective_spawn_spacing(float(spacing), n, actor_code=name, bossish=is_boss)

    loads = tuple(extra_loads or ()) or tuple(_actor_load_paths(name))

    scan_radius = max(4500.0 if is_boss else 2200.0, float(distance) * 3.0)

    before = set() if fast_path else snapshot_character_keys(exclude_keys=player_pawn_keys())

    # Keep polls short enough for lobbies, long enough for thin-air bosses to appear.
    # The 0.35s window caused false "may still stream in" after PushActorDef.
    if fast_path:
        poll_cap = 1.25 if is_boss else 0.85
    else:
        poll_cap = 1.0 if is_boss else 0.70

    # Match the proven oak_spawnai console setup. ``single_spawn`` skips the
    # spawn-point/style initialization and can leave the temporary spawner with
    # zero native rows, which is why BMS buttons reported success but made no mob.
    use_single = bool(async_fire)

    spawn_direct = getattr(ssp, "_spawnai_fresh_spawner_direct", None)

    if not callable(spawn_direct):

        return False, "BL4 Oak Spawner direct path unavailable"



    if fast_path:

        try:

            actor = spawn_direct(

                name,

                distance=dist,

                count=n,

                spacing=spc,

                extra_loads=loads,

                # Keep package probing lean on the game thread. Current Oak Spawner still
                # permits synthetic FGbxDefPtr shells in coop-safe mode.
                coop_safe=True,

                single_spawn=use_single,

                # BMS already detects the actor on later frames. Waiting here
                # blocks PlayerTick and causes the visible post-click hitch.
                poll_timeout=0.0 if async_fire else poll_cap,

            )

        except Exception as ex:  # noqa: BLE001

            actor = None

            _log.debug("oak_spawnai fast direct failed for %s: %s", name, ex)
            if async_fire:
                return False, f"Oak Spawner async fire failed for {name}: {ex}"

        if actor is not None:

            return True, f"oak_spawnai: {name} -> {actor}"

        if async_fire:
            # Zero-poll direct calls normally return None after successfully
            # firing PushActorDef. A fallback here could create a duplicate
            # while that first actor streams into the world.
            return True, f"Oak Spawner async fired: {name} (detecting on later frames)"

        cached_fn = getattr(ssp, "_spawn_cached_actor_def", None)

        if callable(cached_fn):

            try:

                cached = cached_fn(name, distance=dist, count=n, spacing=spc)

                if cached is not None:

                    return True, f"oak_spawnai: {name} -> {cached} (cached)"

            except Exception as ex:  # noqa: BLE001

                _log.debug("cached spawn failed for %s: %s", name, ex)

        deploy_fn = getattr(ssp, "_spawn_deployed_actor", None)

        if callable(deploy_fn):

            try:

                deployed = deploy_fn(name, distance=dist, count=n, spacing=spc)

                if deployed is not None:

                    return True, f"oak_spawnai: {name} -> {deployed} (deploy)"

            except Exception as ex:  # noqa: BLE001

                _log.debug("deploy fallback failed for %s: %s", name, ex)

        from .spawn_core import (  # noqa: PLC0415
            DLC_OAK_CACHE_ACTORS,
            oak_cache_prerequisite_message,
            try_auto_cache_actor_def,
        )

        if is_boss and str(name).strip().lower() in DLC_OAK_CACHE_ACTORS:
            cached, _ = try_auto_cache_actor_def(name)
            if not cached:
                prereq = oak_cache_prerequisite_message(name)
                if prereq:
                    return False, prereq

        # Thin-air PushActorDef often completes after the poll window. Treat as
        # fired so UI/Echo4 async detect can finish instead of hard-failing.
        return True, f"Oak fast spawn: {name} (may still stream in — check nearby)"



    spawn_direct = getattr(ssp, "_spawnai_fresh_spawner_direct", None)

    if not callable(spawn_direct):

        return False, "BL4 Oak Spawner direct path unavailable"



    try:

        actor = spawn_direct(

            name,

            distance=dist,

            count=n,

            spacing=spc,

            extra_loads=loads,

            # Lean package probing, while still allowing the synthetic def fallback.
            coop_safe=True,

            single_spawn=use_single,

            poll_timeout=poll_cap,

        )

    except Exception as ex:  # noqa: BLE001

        actor = None

        _log.debug("oak_spawnai direct failed for %s: %s", name, ex)



    if actor is not None:

        return True, f"oak_spawnai: {name} -> {actor}"



    # Prefer async detect over blocking sleeps (lobby-safe). Brief settle only.
    if not fast_path:

        seen = _wait_for_spawn(

            before,

            expected_code=name,

            radius=scan_radius,

            timeout=0.15,

        )

        if seen is not None:

            return True, f"oak_spawnai: {name} -> {seen} (detected)"



    deploy_fn = getattr(ssp, "_spawn_deployed_actor", None)

    if callable(deploy_fn):

        try:

            deployed = deploy_fn(name, distance=dist, count=n, spacing=spc)

            if deployed is not None:

                return True, f"oak_spawnai: {name} -> {deployed} (deploy)"

        except Exception as ex:  # noqa: BLE001

            _log.debug("deploy fallback failed for %s: %s", name, ex)



    if allow_console_fallback:

        try:

            from gbx_actor_deploy import _pc_console_raw  # noqa: PLC0415



            for cmd in (f"oak_spawnai {name}", f"oak_spawnai {name}"):

                ok, msg = _pc_console_raw(cmd)

                if ok:

                    return True, str(msg)

        except Exception as ex:  # noqa: BLE001

            _log.debug("console AI forward failed for %s: %s", name, ex)



    hint = f"Try console: oak_probe {name}" if name.startswith("Char_") else f"oak_spawnai {name}"

    return False, f"Oak Spawner could not spawn {name} (no actor after {poll_cap:g}s). {hint}"





def spawn_actor_def(

    code: str,

    *,

    count: int = 1,

    distance: float = 350.0,

    spacing: float = 125.0,

    allow_summon_fallback: bool = False,

    max_count: int | None = None,

    fast_path: bool = False,
    async_fire: bool = False,

) -> tuple[bool, str]:

    actor_def = _strip_level_path_prefix(_normalize_actor_token(code))

    if not actor_def:

        return False, "empty actor code"

    # Dumps include inheritance/faction parents such as
    # Char_ArmyBandit_SHARED. Remap to a concrete child when known.
    from .spawn_core import (  # noqa: PLC0415
        abstract_actor_code_message,
        is_abstract_actor_code,
        resolve_concrete_actor_code,
    )

    remapped = resolve_concrete_actor_code(actor_def)
    if remapped.lower() != actor_def.lower():
        actor_def = remapped

    if is_abstract_actor_code(actor_def):

        return False, abstract_actor_code_message(actor_def)



    n = clamp_deploy_count(count, max_cap=max_count)

    bossish = is_boss_actor_code(actor_def) or "boss" in actor_def.lower() or "raid" in actor_def.lower()

    extra = _actor_load_paths(actor_def)



    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
    except Exception as ex:  # noqa: BLE001

        return False, f"BL4 Oak Spawner import failed: {ex}"



    if _is_ai_spawn_code(actor_def, ssp):

        return _spawn_once_ai(

            actor_def,

            count=n,

            distance=distance,

            spacing=effective_spawn_spacing(float(spacing), n, actor_code=actor_def),

            extra_loads=extra,

            bossish=bossish,

            allow_console_fallback=bool(allow_summon_fallback),

            fast_path=bool(fast_path),
            async_fire=bool(async_fire),

        )



    return _spawn_once_deploy(

        actor_def,

        count=n,

        distance=distance,

        spacing=float(spacing),

    )





def oak_available() -> tuple[bool, str]:

    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
        return True, str(getattr(ssp, "_BUILD_TAG", "loaded"))

    except Exception as ex:  # noqa: BLE001

        return False, str(ex)





def run_oak_line(line: str) -> tuple[bool, str]:

    line = (line or "").strip()

    if not line:

        return False, "empty line"

    low = line.lower()

    for prefix in ("oak_spawnai ", "oak_spawnai ", "oak_spawn ", "oak_spawn "):

        if low.startswith(prefix):

            name = line.split(None, 1)[1].strip() if len(line.split(None, 1)) > 1 else ""

            if name and not name.startswith("-"):

                # PersistentLevel / full UE IO paths must use the deploy/template path.
                # Routing them through oak_spawnai after stripping caused hard crashes
                # on Maurice vending and similar machines.
                name_low = name.lower()
                is_world_cmd = low.startswith("oak_spawn ") and not low.startswith("oak_spawnai ")
                if (
                    "persistentlevel." in name_low
                    or name_low.startswith("/game/")
                    or (is_world_cmd and (name_low.startswith("io_") or name_low.startswith("lootable_")))
                ):
                    try:
                        from .io_activate import safe_world_io_spawn  # noqa: PLC0415

                        return safe_world_io_spawn(name)
                    except Exception as ex:  # noqa: BLE001
                        return False, f"world oak_spawn failed safely: {type(ex).__name__}: {ex}"

                return spawn_actor_def(name, count=1, allow_summon_fallback=True)

    try:

        from gbx_actor_deploy import _pc_console_raw  # noqa: PLC0415



        ok, msg = _pc_console_raw(line)

        return bool(ok), str(msg)

    except Exception as ex:  # noqa: BLE001

        return False, str(ex)




