"""Shiny drop helpers for Squ1ggs's Boosting Tools."""

import math
import time
from collections.abc import Sequence
from typing import Any

import unrealsdk
from mods_base import ENGINE, command, get_pc
from unrealsdk import logging
from unrealsdk.unreal import UObject

MAX_ITEM_LEVEL = 999999
DEFAULT_ITEM_LEVEL = 70
SPAWN_FORWARD_OFFSET = 90.0
SPAWN_HEIGHT_OFFSET = 45.0
# Tight ring in front of the player (was a long zig-zag that stretched far).
SPAWN_CIRCLE_RADIUS = 110.0
SPAWN_CIRCLE_HEIGHT_STEP = 2.5
# Cap only for accidental "All" without fill. Fill-until-complete may exceed this up to shape want.
MAX_DROP_ALL_SHINIES = 250
# Hard ceiling when padding a silhouette. House wants ~420; keep well under that —
# recent D3D12 AVs lined up with 420-slot shiny house dumps.
MAX_SHINY_SHAPE_FILL = 220
# Legacy blocking pace (unused by default — kept for env/opt-in sync).
DROP_ALL_SHINIES_PACE_SEC = 0.08
# Frame-paced world drops: keep at 1 — higher per-tick rates AVd under shape find_all.
DROP_ALL_SHINIES_PER_TICK = 1

SHINY_ITEMPOOLS: tuple[str, ...] = (
    "itempool_bor_sg_05_legendary_convergence_shiny",
    "itempool_bor_sg_05_legendary_GoldenGod_shiny",
    "itempool_bor_sg_05_legendary_GoreMaster_shiny",
    "itempool_bor_sg_05_legendary_PlumbBob_shiny",
    "itempool_bor_sm_05_legendary_falke_shiny",
    "itempool_bor_sm_05_legendary_hellfire_shiny",
    "itempool_bor_sm_05_legendary_Prince_shiny",
    "itempool_bor_sr_05_legendary_Stray_shiny",
    "itempool_bor_sr_05_legendary_tankbuster_shiny",
    "itempool_bor_sr_05_legendary_Vamoose_shiny",
    "itempool_dad_ar_05_legendary_Cormano_shiny",
    "itempool_dad_ar_05_legendary_DarkHard_shiny",
    "itempool_dad_ar_05_legendary_DiscyBusiness_shiny",
    "itempool_dad_ar_05_legendary_LightGun_shiny",
    "itempool_dad_ar_05_legendary_Lumberjack_shiny",
    "itempool_dad_ar_05_legendary_mercredi_shiny",
    "itempool_dad_ar_05_legendary_om_shiny",
    "itempool_dad_ar_05_legendary_star_helix_shiny",
    "itempool_dad_ps_05_legendary_Rangefinder_shiny",
    "itempool_dad_ps_05_legendary_silversliver_shiny",
    "itempool_dad_ps_05_legendary_soulsurvivor_shiny",
    "itempool_dad_ps_05_legendary_Zipgun_shiny",
    "itempool_dad_sg_05_legendary_Bod_shiny",
    "itempool_dad_sg_05_legendary_Cannonbrawl_shiny",
    "itempool_dad_sg_05_legendary_HeartGun_shiny",
    "itempool_dad_sg_05_legendary_misslaser_shiny",
    "itempool_dad_sm_05_legendary_bloodstarved_shiny",
    "itempool_dad_sm_05_legendary_follower_shiny",
    "itempool_dad_sm_05_legendary_Luty_shiny",
    "itempool_jak_ar_05_legendary_BonnieClyde_shiny",
    "itempool_jak_ar_05_legendary_fishward_shiny",
    "itempool_jak_ar_05_legendary_Rowan_shiny",
    "itempool_jak_ar_05_legendary_rowdy_shiny",
    "itempool_jak_ps_05_legendary_KingsGambit_shiny",
    "itempool_jak_ps_05_legendary_manifest_shiny",
    "itempool_jak_ps_05_legendary_Phantom_Flame_shiny",
    "itempool_jak_ps_05_legendary_QuickDraw_shiny",
    "itempool_jak_ps_05_legendary_seventh_sense_shiny",
    "itempool_jak_ps_05_legendary_Shalashaska_shiny",
    "itempool_jak_ps_05_legendary_shoals_shiny",
    "itempool_jak_sg_05_legendary_Hellwalker_shiny",
    "itempool_jak_sg_05_legendary_RainbowVomit_shiny",
    "itempool_jak_sg_05_legendary_Slugger_shiny",
    "itempool_jak_sg_05_legendary_TKsWave_shiny",
    "itempool_jak_sr_05_legendary_Ballista_shiny",
    "itempool_jak_sr_05_legendary_Boomslang_shiny",
    "itempool_jak_sr_05_legendary_Truck_shiny",
    "itempool_mal_sg_05_legendary_CrazedEarl_shiny",
    "itempool_mal_sg_05_legendary_fearstalker_shiny",
    "itempool_mal_sg_05_legendary_hemorrhage_shiny",
    "itempool_mal_sg_05_legendary_Kaleidosplode_shiny",
    "itempool_mal_sg_05_legendary_jailbroken_shiny",
    "itempool_mal_sg_05_legendary_kickballer_shiny",
    "itempool_mal_sg_05_legendary_mantra_shiny",
    "itempool_mal_sg_05_legendary_rainmaker_shiny",
    "itempool_mal_sg_05_legendary_reminisce_shiny",
    "itempool_mal_sg_05_legendary_roil_shiny",
    "itempool_mal_sg_05_legendary_scootshoot_shiny",
    "itempool_mal_sg_05_legendary_Sweet_Embrace_shiny",
    "itempool_mal_sg_05_legendary_Unstable_shiny",
    "itempool_mal_sm_05_legendary_brickhouse_shiny",
    "itempool_mal_sm_05_legendary_flashcyclone_shiny",
    "itempool_mal_sm_05_legendary_mercury_shiny",
    "itempool_mal_sm_05_legendary_OhmIGot_shiny",
    "itempool_mal_sm_05_legendary_PlasmaCoil_shiny",
    "itempool_mal_sm_05_legendary_songbird_shiny",
    "itempool_mal_sr_05_legendary_Asher_shiny",
    "itempool_mal_sr_05_legendary_complex_root_shiny",
    "itempool_mal_sr_05_legendary_katagawa_shiny",
    "itempool_ord_ar_05_legendary_GMR_shiny",
    "itempool_ord_ar_05_legendary_Goalkeeper_shiny",
    "itempool_ord_ps_05_legendary_Bully_shiny",
    "itempool_ord_ps_05_legendary_NoisyCricket_shiny",
    "itempool_ord_ps_05_legendary_Rhythm_shiny",
    "itempool_ord_ps_05_legendary_RocketReload_shiny",
    "itempool_ord_ps_05_legendary_Roulette_shiny",
    "itempool_ord_ps_05_legendary_sunspot_shiny",
    "itempool_ord_sr_05_legendary_Fisheye_shiny",
    "itempool_ord_sr_05_legendary_Ishmael_shiny",
    "itempool_ord_sr_05_legendary_seamstress_shiny",
    "itempool_ord_sr_05_legendary_Symmetry_shiny",
    "itempool_ted_ar_05_legendary_Chuck_shiny",
    "itempool_ted_ar_05_legendary_DividedFocus_shiny",
    "itempool_ted_ar_05_legendary_laserdisc_shiny",
    "itempool_ted_ar_05_legendary_murder_shiny",
    "itempool_ted_ps_05_legendary_ATLien_shiny",
    "itempool_ted_ps_05_legendary_EarlyExcess_shiny",
    "itempool_ted_ps_05_legendary_Inscriber_shiny",
    "itempool_ted_ps_05_legendary_RubysGrasp_shiny",
    "itempool_ted_ps_05_legendary_shammy_shiny",
    "itempool_ted_ps_05_legendary_Sideshow_shiny",
    "itempool_ted_sg_05_legendary_anarchy_shiny",
    "itempool_ted_sg_05_legendary_CommBD_shiny",
    "itempool_ted_sg_05_legendary_HeavyTurret_shiny",
    "itempool_tor_ar_05_legendary_Bugbear_shiny",
    "itempool_tor_ar_05_legendary_ColdShoulder_shiny",
    "itempool_tor_ar_05_legendary_Fleabag_shiny",
    "itempool_tor_ar_05_legendary_lockjaw_shiny",
    "itempool_tor_ar_05_legendary_PotatoThrower_shiny",
    "itempool_tor_PS_05_legendary_Breadth_shiny",
    "itempool_tor_ps_05_legendary_QueensRest_shiny",
    "itempool_tor_ps_05_legendary_Roach_shiny",
    "itempool_tor_sg_05_legendary_arctic_shiny",
    "itempool_tor_sg_05_legendary_Demo_shiny",
    "itempool_tor_sg_05_legendary_Doeshot_shiny",
    "itempool_tor_sg_05_legendary_LeadBalloon_shiny",
    "itempool_tor_sg_05_legendary_Linebacker_shiny",
    "itempool_vla_ar_05_legendary_bubbles_shiny",
    "itempool_vla_ar_05_legendary_DualDamage_shiny",
    "itempool_vla_ar_05_legendary_lasercutter_shiny",
    "itempool_vla_ar_05_legendary_Lucian_shiny",
    "itempool_vla_ar_05_legendary_WF_shiny",
    "itempool_vla_ar_05_legendary_WomboCombo_shiny",
    "itempool_vla_sm_05_legendary_BeeGun_shiny",
    "itempool_vla_sm_05_legendary_KaoSon_shiny",
    "itempool_vla_sm_05_legendary_Onslaught_shiny",
    "itempool_vla_sm_06_pearl_Locust_shiny",
    "itempool_vla_sr_05_legendary_CrowdSourced_shiny",
    "itempool_vla_sr_05_legendary_Finnty_shiny",
    "itempool_vla_sr_05_legendary_StopGap_shiny",
    "itempool_tor_ps_06_pearl_herald_shiny",
    "itempool_mal_sm_06_pearl_juliet_shiny",
    "itempool_jak_sg_06_pearl_constable_shiny",
    "itempool_dad_sm_06_pearl_screwed_shiny",
    "itempool_ted_sg_06_pearl_sharkbait_shiny",
    "itempool_ord_ar_05_legendary_crowsourced_pearl_shiny",
    "itempool_ted_sg_05_legendary_eigenburst_pearl_shiny",
    "itempool_tor_ps_05_legendary_handcannon_pearl_shiny",
    "itempool_mal_sr_05_legendary_conflux_pearl_shiny",
    "itempool_bor_sr_05_legendary_abyss_shiny",
    "itempool_jak_ar_05_legendary_gomie_shiny",
    "itempool_dad_sm_05_legendary_raiden_shiny",
    "itempool_ord_sr_05_legendary_temper_shiny",
)


def _dedupe_pools(names: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        low = str(name).lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(str(name))
    return tuple(out)


SHINY_ITEMPOOLS = _dedupe_pools(SHINY_ITEMPOOLS)

# Extra aliases: itempool weapon token → shiny_serials.json id
_SHINY_POOL_ALIASES: dict[str, str] = {
    "om": "oscar_mike",
    "prince": "prince_harming",
    "stray": "stray",
    "tankbuster": "tankbuster",
    "vamoose": "vamoose",
    "darkhard": "hard_dark",
    "discybusiness": "discy_business",
    "lumberjack": "bloody_lumberjack",
    "starhelix": "star_helix",
    "soulsurvivor": "soul_survivor",
    "zipgun": "zip_gun",
    "cannonbrawl": "cannonbrawl",
    "heartgun": "heart_gun",
    "bloodstarved": "blood_starved",
    "luty": "luty_madlad",
    "bonnieclyde": "bonnie_and_clyde",
    "rowan": "rowan",
    "rowdy": "rowdy",
    "kingsgambit": "kings_gambit",
    "phantomflame": "phantom_flame",
    "quickdraw": "quick_draw",
    "seventhsense": "seventh_sense",
    "shalashaska": "shalashaska",
    "rainbowvomit": "rainbow_vomit",
    "slugger": "hot_slugger",
    "tkswave": "tks_wave",
    "ballista": "borstel_ballista",
    "truck": "truck",
    "crazedearl": "crazedearl",
    "kaleidosplode": "kaleidosplode",
    "sweetembrace": "sweet_embrace",
    "ohmigot": "ohm_i_got",
    "plasmacoil": "plasma_coil",
    "songbird": "songbird",
    "asher": "ashers_rise",
    "katagawa": "katagawas_revenge",
    "gmr": "gmr",
    "noisycricket": "noisy_cricket",
    "rocketreload": "rocket_reload",
    "sunspot": "sunspot",
    "fisheye": "fisheye",
    "seamstress": "seamstress",
    "symmetry": "symmetry",
    "dividedfocus": "divided_focus",
    "laserdisc": "laserdisc",
    "atlient": "atlien",
    "rubysgrasp": "rubys_grasp",
    "commbd": "comm_bd",
    "heavyturret": "heavy_turret",
    "coldshoulder": "cold_shoulder",
    "potatothrower": "potato_thrower_iv",
    "queensrest": "queens_rest",
    "leadballoon": "lead_balloon",
    "linebacker": "linebacker",
    "dualdamage": "dual_damage",
    "lasercutter": "lasercutter",
    "lucian": "lucians_flank",
    "wf": "wunderfizz",
    "wombocombo": "wombo_combo",
    "beegun": "birts_bees",
    "kaoson": "kaoson",
    "locust": "Locust",
    "crowdsourced": "midnight_defiance",
    "finnty": "finnity_xxx_l",
    "stopgap": "stop_gap",
    "jailbroken": "jailbroken",
    "lockjaw": "lockjaw",
    "shammy": "shammy",
}


def _norm_key(text: str) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


_SHINY_SERIAL_CACHE: list[dict[str, str]] | None = None
_SHINY_BY_NORM: dict[str, str] | None = None


def load_shiny_serial_entries() -> list[dict[str, str]]:
    """Load curated shiny @U rows from package data (same list as Shiny Mail)."""
    global _SHINY_SERIAL_CACHE
    if _SHINY_SERIAL_CACHE is not None:
        return list(_SHINY_SERIAL_CACHE)
    import json
    import pkgutil

    blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], "shiny_serials.json")
    if blob is None:
        # Prefer on-disk sibling when imported outside the package zip.
        from pathlib import Path

        path = Path(__file__).with_name("shiny_serials.json")
        if path.is_file():
            blob = path.read_bytes()
    if blob is None:
        raise RuntimeError("Could not load shiny_serials.json")
    data = json.loads(blob.decode("utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("shiny_serials.json must be a list")
    rows: list[dict[str, str]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        serial = str(entry.get("serial", "")).strip()
        if not serial.startswith("@U"):
            continue
        rows.append(
            {
                "id": str(entry.get("id", "")).strip(),
                "display_name": str(entry.get("display_name", "")).strip(),
                "serial": serial,
            }
        )
    if not rows:
        raise RuntimeError("No @U serials in shiny_serials.json")
    _SHINY_SERIAL_CACHE = rows
    return list(rows)


def load_shiny_serials() -> list[str]:
    return [row["serial"] for row in load_shiny_serial_entries()]


def _shiny_lookup_table() -> dict[str, str]:
    global _SHINY_BY_NORM
    if _SHINY_BY_NORM is not None:
        return _SHINY_BY_NORM
    table: dict[str, str] = {}
    for row in load_shiny_serial_entries():
        serial = row["serial"]
        for key in (row.get("id"), row.get("display_name")):
            norm = _norm_key(str(key or ""))
            if norm and norm not in table:
                table[norm] = serial
    for alias, target_id in _SHINY_POOL_ALIASES.items():
        serial = table.get(_norm_key(target_id))
        if serial:
            table[_norm_key(alias)] = serial
    _SHINY_BY_NORM = table
    return table


def weapon_token_from_shiny_pool(pool_name: str) -> str:
    """Extract weapon token from ``itempool_*_legendary_X_shiny`` / pearl pools."""
    import re

    low = str(pool_name or "").strip().lower()
    if low.startswith("itempool_"):
        low = low[len("itempool_") :]
    if low.endswith("_shiny"):
        low = low[: -len("_shiny")]
    m = re.match(r"^[a-z0-9]+_[a-z0-9]+_\d{2}_(?:legendary|pearl)_(.+)$", low)
    if m:
        return m.group(1)
    # Fallback: last underscore segment
    parts = [p for p in low.split("_") if p]
    return parts[-1] if parts else low


def serial_for_shiny_pool(pool_name: str) -> str | None:
    """Map a *_shiny itempool name to a curated shiny @U serial when possible."""
    try:
        table = _shiny_lookup_table()
    except Exception:
        return None
    token = weapon_token_from_shiny_pool(pool_name)
    candidates = [
        token,
        token.replace("_", ""),
        _SHINY_POOL_ALIASES.get(_norm_key(token), ""),
    ]
    for cand in candidates:
        norm = _norm_key(cand)
        if norm and norm in table:
            return table[norm]
    # Try full display-ish token match against every key containing token.
    want = _norm_key(token)
    if want:
        for key, serial in table.items():
            if want == key or want in key or key in want:
                return serial
    return None


def grant_shiny_serials(
    serials: Sequence[str],
    *,
    all_players: bool = False,
    player_indices: Sequence[int] | None = None,
) -> int:
    """Deliver shiny @U codes via loyalty mail (true Cosmetics_Weapon_Shiny_* skins)."""
    cleaned = [str(s).strip() for s in serials if str(s or "").strip().startswith("@U")]
    if not cleaned:
        return 0
    from .serial_rewards import (
        _do_give_serial_to_player_indices,
        _all_party_player_indices_for_serial_delivery,
    )

    if all_players:
        indices = list(_all_party_player_indices_for_serial_delivery() or [])
        if not indices:
            indices = [0]
        _do_give_serial_to_player_indices(cleaned, indices, scope_label="all party players (shiny)")
        return len(cleaned)
    if player_indices is not None:
        indices = [int(i) for i in player_indices]
        if not indices:
            return 0
        label = (
            f"shiny target index {indices[0]}"
            if len(indices) == 1
            else f"shiny targets ({len(indices)})"
        )
        _do_give_serial_to_player_indices(cleaned, indices, scope_label=label)
        return len(cleaned)
    # Legacy fallback: first party index (host) when no boost target was provided.
    try:
        indices = list(_all_party_player_indices_for_serial_delivery() or [])
    except Exception:
        indices = []
    if indices:
        _do_give_serial_to_player_indices(cleaned, [int(indices[0])], scope_label="local shiny")
    else:
        _do_give_serial_to_player_indices(cleaned, [0], scope_label="local shiny")
    return len(cleaned)


def grant_all_shiny_serials(
    *,
    all_players: bool = False,
    player_indices: Sequence[int] | None = None,
) -> int:
    serials = load_shiny_serials()
    n = grant_shiny_serials(serials, all_players=all_players, player_indices=player_indices)
    _log_info(
        f"Granted {n}/{len(serials)} shiny serial(s) via mailbox "
        f"(all_players={all_players}, targets={list(player_indices) if player_indices is not None else None})."
    )
    return n


def _log_info(message: str) -> None:
    logging.info(f"[Squ1ggs's Boosting Tools | Shinies] {message}")


def _log_warning(message: str) -> None:
    logging.warning(f"[Squ1ggs's Boosting Tools | Shinies] {message}")


def _make_vector(x: float, y: float, z: float) -> Any:
    return unrealsdk.make_struct("Vector", X=x, Y=y, Z=z)


def _make_rotator(pitch: float, yaw: float, roll: float = 0.0) -> Any:
    return unrealsdk.make_struct("Rotator", Pitch=pitch, Yaw=yaw, Roll=roll)


def _get_world() -> UObject | None:
    viewport = getattr(ENGINE, "GameViewport", None)
    world = getattr(viewport, "World", None)
    if world is not None:
        return world

    for class_name in ("OakPlayerController", "PlayerController"):
        try:
            objects = unrealsdk.find_all(class_name, False) or []
        except Exception:
            continue
        for obj in objects:
            if obj is None:
                continue
            candidate = getattr(obj, "World", None)
            if candidate is not None:
                return candidate
            pawn = getattr(obj, "Pawn", None)
            candidate = getattr(pawn, "World", None) if pawn is not None else None
            if candidate is not None:
                return candidate
    return None


def _get_runtime_pc() -> UObject | None:
    pc = get_pc()
    if pc is not None:
        return pc

    for class_name in ("OakPlayerController", "PlayerController"):
        try:
            objects = unrealsdk.find_all(class_name, False) or []
        except Exception:
            continue
        for obj in objects:
            if obj is not None:
                return obj
    return None


def _get_spawn_transform(pc: UObject) -> Any | None:
    pawn = getattr(pc, "Pawn", None)
    if pawn is None:
        return None

    player_location = pawn.K2_GetActorLocation()
    for getter_name in ("K2_GetActorTransform", "GetActorTransform", "GetTransform"):
        getter = getattr(pawn, getter_name, None)
        if not callable(getter):
            continue
        try:
            transform = getter()
            setattr(transform, "Translation", _make_vector(player_location.X, player_location.Y, player_location.Z))
            return transform
        except Exception:
            continue
    return None


def _pose_from_pc_pawn(pc: UObject) -> tuple[Any, Any] | None:
    pawn = getattr(pc, "Pawn", None)
    if pawn is None:
        return None
    try:
        return pawn.K2_GetActorLocation(), pawn.K2_GetActorRotation()
    except Exception:
        return None


def _get_player_pose(pc: UObject) -> tuple[Any, Any] | None:
    try:
        from .spawn_targets import resolve_pose  # noqa: PLC0415

        return resolve_pose(pc)
    except Exception:
        return _pose_from_pc_pawn(pc)


def _resolve_drop_pose(pc: UObject, *, prefer_pawn: bool) -> tuple[Any, Any] | None:
    """Party-target drops use that PC's pawn; local drops may use F3 spawn anchor."""
    if prefer_pawn:
        return _pose_from_pc_pawn(pc)
    try:
        return _get_player_pose(pc)
    except RuntimeError:
        return _pose_from_pc_pawn(pc)


def _spawn_pose(
    player_location: Any,
    player_rotation: Any,
    index: int,
    *,
    total: int = 1,
    local_offsets: list[tuple[float, float, float]] | None = None,
) -> tuple[Any, Any]:
    """Place drops on a small circle, or on loot-shape local offsets when provided."""
    import math as _math

    yaw_rad = _math.radians(float(getattr(player_rotation, "Yaw", 0.0) or 0.0))
    if local_offsets and 0 <= int(index) < len(local_offsets):
        lx, ly, lz = local_offsets[int(index)]
        fx, fy = _math.cos(yaw_rad), _math.sin(yaw_rad)
        rx, ry = -_math.sin(yaw_rad), _math.cos(yaw_rad)
        new_x = float(player_location.X) + fx * float(lx) + rx * float(ly)
        new_y = float(player_location.Y) + fy * float(lx) + ry * float(ly)
        new_z = float(player_location.Z) + float(SPAWN_HEIGHT_OFFSET) + float(lz)
        from .loot_shapes import rotator_for_world_slot

        return _make_vector(new_x, new_y, new_z), rotator_for_world_slot(index, new_x, new_y, new_z)

    forward_x = _math.cos(yaw_rad)
    forward_y = _math.sin(yaw_rad)
    n = max(1, int(total))
    i = int(index) % n
    angle = yaw_rad + (2.0 * _math.pi * float(i) / float(n))
    cx = float(player_location.X) + forward_x * float(SPAWN_FORWARD_OFFSET)
    cy = float(player_location.Y) + forward_y * float(SPAWN_FORWARD_OFFSET)
    r = float(SPAWN_CIRCLE_RADIUS)
    new_x = cx + _math.cos(angle) * r
    new_y = cy + _math.sin(angle) * r
    new_z = float(player_location.Z) + float(SPAWN_HEIGHT_OFFSET) + (float(i) * float(SPAWN_CIRCLE_HEIGHT_STEP))
    from .loot_shapes import rotator_for_world_slot

    return _make_vector(new_x, new_y, new_z), rotator_for_world_slot(index, new_x, new_y, new_z)


def _get_pool_store() -> UObject:
    configs = unrealsdk.find_all("NexusConfigStoreItemPool", False)
    if not configs:
        raise RuntimeError("NexusConfigStoreItemPool not found.")
    return list(configs)[-1]


def _spawn_pool(config: UObject, world: UObject, transform: Any, level: int, pool_name: str, location: Any, rotation: Any) -> None:
    # ULM/dump: FTransform.Rotation is a Quat. Assigning a Rotator makes NCS ignore XY.
    try:
        from .item_spawn.ncs_pool_spawn import apply_world_spawn_transform

        apply_world_spawn_transform(transform, location, rotation)
    except Exception:
        try:
            setattr(transform, "Translation", location)
        except Exception:
            pass

    config.SpawnInventoryFromItemPool(world, transform, level, pool_name)


def _resolve_native_pool_name(pool_name: str) -> str:
    # Prefer live Nexus casing (TitleCase ids) — lowercase silent-miss / wrong loot.
    try:
        from .standalone_spawning import (  # noqa: PLC0415
            _load_native_pools,
            _resolve_native_pool,
        )

        native = _resolve_native_pool(pool_name, _load_native_pools())
        if native:
            return native
    except Exception:
        pass
    return pool_name


def _pc_for_party_index(party_index: int | None) -> UObject | None:
    """Resolve a 0-based PlayerArray / Give_Serial index to a PC, else local PC."""
    if party_index is None:
        return _get_runtime_pc()
    try:
        from .party_helpers import (  # noqa: PLC0415
            _gbc_find_pc_for_player_state,
            _gbc_session_world_and_gamestate,
        )

        world, gs = _gbc_session_world_and_gamestate()
        pa = getattr(gs, "PlayerArray", None) if gs is not None else None
        if pa is not None:
            idx = int(party_index)
            if 0 <= idx < len(pa):
                ps = pa[idx]
                pc = _gbc_find_pc_for_player_state(ps, world) if ps is not None else None
                if pc is not None:
                    return pc
    except Exception:
        pass
    # Do not consult sibling mods or silently redirect an explicit target.
    return None


_pending_shiny_drop_jobs: list[dict[str, Any]] = []
_shiny_drop_status_message: str = ""
_shiny_drop_status_until: float = 0.0


def shiny_drop_status() -> str:
    """UI poller for active Drop All Shinies progress."""
    import time

    if _pending_shiny_drop_jobs:
        job = _pending_shiny_drop_jobs[0]
        pools = list(job.get("pools") or [])
        idx = int(job.get("index") or 0)
        return f"Running Shiny pools {min(idx, len(pools))}/{len(pools)}…"
    if _shiny_drop_status_message and time.time() <= float(_shiny_drop_status_until or 0.0):
        return _shiny_drop_status_message
    return ""


def _set_shiny_drop_status(message: str, *, hold_sec: float = 12.0, log: bool = False) -> None:
    global _shiny_drop_status_message, _shiny_drop_status_until
    import time

    text = str(message or "").strip()
    _shiny_drop_status_message = text
    _shiny_drop_status_until = time.time() + max(1.0, float(hold_sec))
    if log and text:
        _log_info(text)


_SHAPE_FILL_TYPE_POOLS: tuple[str, ...] = (
    "itempool_sm_05_legendary",
    "itempool_sg_05_legendary",
    "itempool_ar_05_legendary",
    "itempool_smg_all",
    "itempool_shotgun_all",
    "itempool_assaultrifle_all",
)


def _extend_shiny_pools_until_shape(pools: list[str], shape: str) -> list[str]:
    """Repeat SMG/SG/AR shinies (or dump type pools) until drop count fills the silhouette."""
    from .loot_shapes import is_shape_fill_pool_name, shape_complete_slot_count

    want = int(shape_complete_slot_count(shape, profile="shiny"))
    if want <= 0:
        return pools
    want = min(int(MAX_SHINY_SHAPE_FILL), want)
    extra = min(max(0, want - len(pools)), max(0, int(MAX_SHINY_SHAPE_FILL) - len(pools)))
    if extra <= 0:
        return pools
    fillers = [p for p in pools if is_shape_fill_pool_name(p)]
    if not fillers:
        fillers = list(_SHAPE_FILL_TYPE_POOLS)
    if not fillers and pools:
        fillers = [pools[0]]
    if not fillers:
        return pools
    out = list(pools)
    idx = 0
    while extra > 0:
        out.append(fillers[idx % len(fillers)])
        extra -= 1
        idx += 1
    if len(out) < want:
        _log_warning(f"Shape fill queued {len(out)}/{want} shiny drops (cap {MAX_SHINY_SHAPE_FILL}).")
    return out


def _queue_shiny_itempool_drop(
    pools: Sequence[str],
    level: int,
    *,
    target_party_index: int | None = None,
    shape: str = "none",
    settle: str = "none",
    drop_height: float = 440.0,
    line_length: float = 900.0,
    radius: float = 220.0,
    spacing: float = 140.0,
    spawn_then_shape: bool = False,
    stay_in_air: bool = True,
    peel_after: float = 0.0,
    land_profile: str = "shiny",
    fill_until_complete: bool = False,
    shape_text: str = "",
) -> int:
    """Enqueue tick-paced world drops (never blocks the host with time.sleep)."""
    import os

    level = max(1, min(MAX_ITEM_LEVEL, int(level)))
    if shape_text or str(shape or "").strip().lower() in ("text", "text_shape", "words", "word", "write"):
        try:
            from .loot_shapes import set_shape_text  # noqa: PLC0415

            set_shape_text(shape_text)
            shape = "text"
        except Exception:
            pass
    pool_list = [str(p).strip() for p in pools if str(p).strip()]
    # Cap curated list first; fill-until-complete may pad past the cap up to silhouette want.
    if len(pool_list) > MAX_DROP_ALL_SHINIES:
        _log_warning(
            f"Drop All Shinies capped at {MAX_DROP_ALL_SHINIES}/{len(pool_list)} "
            f"(use Item Pools → Spawn All Filtered for a narrowed set)."
        )
        pool_list = pool_list[:MAX_DROP_ALL_SHINIES]
    if fill_until_complete:
        pool_list = _extend_shiny_pools_until_shape(pool_list, shape)
    if str(shape or "").strip().lower() == "text" or bool(str(shape_text or "").strip()):
        try:
            from .loot_shapes import text_shape_slot_count  # noqa: PLC0415

            want = int(text_shape_slot_count(shape_text or None, profile=land_profile))
            if want > 0 and len(pool_list) > want:
                pool_list = pool_list[:want]
        except Exception:
            pass
    if not pool_list:
        raise RuntimeError("No shiny itempools to drop.")

    # Opt-in legacy blocking path (freezes host — only for debugging).
    sync = os.environ.get("SQU1GGS_SHINY_DROP_SYNC", "").strip().lower() in ("1", "true", "yes", "on")
    if sync:
        _spawn_all_shinies_blocking(level, pool_list, target_party_index=target_party_index)
        return len(pool_list)

    where = f"party index {int(target_party_index)}" if target_party_index is not None else "local feet"
    if _pending_shiny_drop_jobs:
        _log_warning("Replacing previous shiny drop queue with a new request.")
        try:
            from .loot_shapes import finish_drop_jobs, set_bulk_healthcheck_mode

            set_bulk_healthcheck_mode(False)
            finish_drop_jobs()
        except Exception:
            pass
        _pending_shiny_drop_jobs.clear()
    _set_shiny_drop_status(
        f"Queued {len(pool_list)} Shiny-eligible pool calls @ level {level} near {where}",
        hold_sec=20.0,
        log=True,
    )
    from .loot_shapes import normalize_drop_mode

    settle_l = normalize_drop_mode(settle)
    shape_l = str(shape or "none").strip().lower()
    if shape_l in ("", "off", "no", "vanilla"):
        shape_l = "none"
    local_offsets: list[tuple[float, float, float]] = []
    if shape_l != "none" or settle_l != "none":
        try:
            from .loot_shapes import begin_spawn_landing, set_bulk_healthcheck_mode

            begin_spawn_landing(
                len(pool_list),
                shape=shape_l,
                settle=settle_l,
                drop_height=drop_height,
                line_length=line_length,
                radius=radius,
                spacing=spacing,
                spawn_then_shape=spawn_then_shape,
                stay_in_air=stay_in_air,
                peel_after=peel_after,
                land_profile=land_profile,
                shape_text=shape_text,
            )
            # Same catch throttle as Spawn All shaped — one find_all cadence, not per dump.
            set_bulk_healthcheck_mode(True)
            # Do NOT call shape_offsets again here — begin_spawn_landing builds the
            # plan lazily. A second full silhouette bake froze the host at start.
        except Exception as land_exc:
            _log_warning(f"Could not arm land-in-shape for dump: {land_exc!r}")
    try:
        from .loot_shapes import pause_catch_for_shape

        pause_catch_for_shape(shape_l)
    except Exception:
        pass
    _pending_shiny_drop_jobs.append(
        {
            "pools": pool_list,
            "level": level,
            "target_party_index": target_party_index,
            "local_offsets": local_offsets,
            "index": 0,
            "spawned": 0,
            "failed": [],
            "shape": shape_l,
            "settle": settle_l,
            "drop_height": float(drop_height),
            "spawn_then_shape": bool(spawn_then_shape),
        }
    )
    return len(pool_list)


def _process_pending_shiny_drop_jobs() -> None:
    if not _pending_shiny_drop_jobs:
        return
    import os

    remaining: list[dict[str, Any]] = []
    per_tick = max(1, int(DROP_ALL_SHINIES_PER_TICK or 1))
    try:
        # Shaped dumps must stay at 1/tick — 2+ under house find_all correlated with D3D12 AVs.
        shaped = any(
            str(j.get("shape") or "none").strip().lower() not in ("", "none", "off")
            for j in _pending_shiny_drop_jobs
        )
        env_cap = 1 if shaped else 2
        per_tick = max(1, min(int(os.environ.get("SQU1GGS_SHINY_DROP_PER_TICK", str(per_tick))), env_cap))
    except (TypeError, ValueError):
        pass

    for job in list(_pending_shiny_drop_jobs):
        try:
            pools = list(job.get("pools") or [])
            idx = int(job.get("index") or 0)
            level = int(job.get("level") or DEFAULT_ITEM_LEVEL)
            target_i = job.get("target_party_index")
            try:
                target_party_index = int(target_i) if target_i is not None else None
            except (TypeError, ValueError):
                target_party_index = None

            if idx >= len(pools):
                spawned = int(job.get("spawned") or 0)
                failed = list(job.get("failed") or [])
                if failed:
                    _set_shiny_drop_status(
                        f"Shiny pool run done: {spawned}/{len(pools)} calls returned, {len(failed)} failed. "
                        "Phosphene needs an edited save with shiny cosmetics loaded.",
                        hold_sec=20.0,
                        log=True,
                    )
                else:
                    _set_shiny_drop_status(
                        f"Shiny pool run done: {spawned} calls returned. "
                        "Use an edited save if these dropped as normal legendaries.",
                        hold_sec=16.0,
                        log=True,
                    )
                continue

            world = _get_world()
            pc = _pc_for_party_index(target_party_index)
            if world is None or pc is None:
                _set_shiny_drop_status(
                    "Shiny drop stopped: player or world unavailable.",
                    hold_sec=20.0,
                    log=True,
                )
                remaining.append(job)
                continue

            transform = _get_spawn_transform(pc)
            player_pose = _resolve_drop_pose(pc, prefer_pawn=target_party_index is not None)
            if transform is None or player_pose is None:
                _set_shiny_drop_status(
                    "Shiny drop stopped: could not derive spawn pose.",
                    hold_sec=20.0,
                    log=True,
                )
                remaining.append(job)
                continue

            player_location, player_rotation = player_pose
            end = min(len(pools), idx + per_tick)
            config = _get_pool_store()
            from .loot_shapes import spawn_drop_pose

            offsets = list(job.get("local_offsets") or [])
            shape_l = str(job.get("shape") or "none").strip().lower()
            settle_l = str(job.get("settle") or "none").strip().lower()
            # Shape / drop-from-above: dump onto slots; don't find_all every item (that's the hitch).
            catch_dump = shape_l not in ("", "none") or settle_l not in ("", "none")
            batch_spawned = 0
            for i in range(idx, end):
                pool_name = pools[i]
                try:
                    from .loot_shapes import register_land_slot_pool

                    register_land_slot_pool(i, pool_name)
                except Exception:
                    pass
                spawn_name = _resolve_native_pool_name(pool_name)
                slot = spawn_drop_pose(i, pool_name=pool_name) if catch_dump else None
                if slot is not None:
                    location = _make_vector(slot[0], slot[1], slot[2])
                    from .loot_shapes import rotator_for_world_slot

                    rotation = rotator_for_world_slot(i, slot[0], slot[1], slot[2])
                else:
                    location, rotation = _spawn_pose(
                        player_location,
                        player_rotation,
                        i,
                        total=len(pools),
                        local_offsets=offsets or None,
                    )
                try:
                    dumped = 0
                    # Live NCS first — dump/@U was ~250ms/item and caused shiny drop lag.
                    try:
                        _spawn_pool(
                            config, world, transform, level, spawn_name, location, rotation
                        )
                        dumped = 1
                    except Exception:
                        dumped = 0
                    if dumped <= 0:
                        try:
                            from .item_spawn.shiny_pearl_spawn import spawn_shiny_from_dump

                            dumped, _dump_err, _dump_method = spawn_shiny_from_dump(
                                spawn_name,
                                count=1,
                                level=level,
                                location=location if catch_dump else None,
                                rotation=rotation if catch_dump else None,
                            )
                        except Exception:
                            dumped = 0
                    if dumped <= 0:
                        try:
                            from .item_spawn.shiny_pearl_spawn import prepare_shiny_pool_context

                            prepare_shiny_pool_context(spawn_name)
                        except Exception:
                            pass
                        _spawn_pool(
                            config, world, transform, level, spawn_name, location, rotation
                        )
                        dumped = 1
                    job["spawned"] = int(job.get("spawned") or 0) + 1
                    batch_spawned += 1
                except Exception as exc:
                    failed = list(job.get("failed") or [])
                    failed.append(pool_name)
                    job["failed"] = failed
                    _log_warning(f"Failed to spawn {pool_name}: {exc}")
            if catch_dump and batch_spawned > 0:
                try:
                    from .loot_shapes import after_dump_spawn

                    after_dump_spawn(batch_spawned)
                except Exception:
                    pass
            job["index"] = end
            if end < len(pools):
                remaining.append(job)
            else:
                spawned = int(job.get("spawned") or 0)
                failed = list(job.get("failed") or [])
                shape_done = str(job.get("shape") or "none")
                settle_done = str(job.get("settle") or "none")
                if shape_done not in ("", "none") and settle_done in ("", "none"):
                    settle_msg = f"Pinned onto {shape_done} (no spit)."
                elif shape_done in ("", "none") and settle_done in ("", "none"):
                    settle_msg = "Spawned at feet (land-in-shape none)."
                else:
                    settle_msg = (
                        f"Dropping from above into {shape_done or 'silhouette'} ({settle_done})."
                    )
                if failed:
                    _set_shiny_drop_status(
                        f"Shiny pool run done: {spawned}/{len(pools)} calls returned, {len(failed)} failed. "
                        f"{settle_msg} Phosphene needs an edited save with shiny cosmetics loaded.",
                        hold_sec=20.0,
                        log=True,
                    )
                else:
                    _set_shiny_drop_status(
                        f"Shiny pool run done: {spawned} calls returned. {settle_msg} "
                        "Use an edited save if these dropped as normal legendaries.",
                        hold_sec=16.0,
                        log=True,
                    )
        except Exception as exc:
            _set_shiny_drop_status(f"Shiny drop tick failed: {exc!r}", hold_sec=20.0, log=True)
            remaining.append(job)
    _pending_shiny_drop_jobs[:] = remaining
    if not remaining:
        try:
            from .loot_shapes import (
                landing_armed,
                pause_landing_catch,
                set_bulk_healthcheck_mode,
                settle_landing_loot,
                tick_drop_motion,
            )

            pause_landing_catch(False)
            set_bulk_healthcheck_mode(False)
            if landing_armed():
                # House/globe leftovers: a 12-item settle left the silhouette a few short.
                settle_landing_loot(limit=96)
            tick_drop_motion()
        except Exception:
            pass


def _shiny_drop_tick_cb(*_args: Any, **_kwargs: Any) -> None:
    shiny_drop_runtime_tick(*_args, **_kwargs)


_shiny_drop_last_tick_at = 0.0
_shiny_drop_tick_in_progress = False


def cancel_pending_shiny_drops(reason: str = "session teardown") -> None:
    """Stop queued shiny world drops without touching live pickups."""
    if not _pending_shiny_drop_jobs:
        return
    _pending_shiny_drop_jobs.clear()
    try:
        from .loot_shapes import finish_drop_jobs, set_bulk_healthcheck_mode

        set_bulk_healthcheck_mode(False)
        finish_drop_jobs()
    except Exception:
        pass
    _set_shiny_drop_status(f"Shiny drop queue cancelled ({reason}).", hold_sec=12.0, log=True)


def shiny_drop_runtime_tick(*args: Any, **_kwargs: Any) -> None:
    """Drain shiny queues on the shared Squ1ggs UMG tick (serial_rewards hook)."""
    global _shiny_drop_last_tick_at, _shiny_drop_tick_in_progress
    if not _pending_shiny_drop_jobs:
        return
    try:
        from .session_guards import session_safe

        if not session_safe():
            cancel_pending_shiny_drops("left session")
            return
    except Exception:
        pass
    if _shiny_drop_tick_in_progress:
        return
    try:
        from .uvhm_runtime import _is_host_tick_context  # noqa: PLC0415

        if not _is_host_tick_context(args):
            return
    except Exception:
        pass
    now = time.monotonic()
    if now - _shiny_drop_last_tick_at < 0.15:
        return
    _shiny_drop_last_tick_at = now
    _shiny_drop_tick_in_progress = True
    try:
        _process_pending_shiny_drop_jobs()
    except Exception as exc:
        _log_warning(f"Shiny drop tick failed: {exc!r}")
    finally:
        _shiny_drop_tick_in_progress = False


# Shiny drops piggyback serial_rewards' BP_TickWidget hook — do NOT register a second UMG hook
# (duplicate hooks + blimgui post-frame caused EXCEPTION_ACCESS_VIOLATION under heavy spawns).


def _spawn_all_shinies_blocking(
    level: int,
    pools: Sequence[str],
    *,
    target_party_index: int | None = None,
) -> None:
    """Blocking drop with time.sleep — freezes host; opt-in via SQU1GGS_SHINY_DROP_SYNC=1."""
    import time

    world = _get_world()
    pc = _pc_for_party_index(target_party_index)
    if world is None or pc is None:
        raise RuntimeError("Player or world is not available.")

    transform = _get_spawn_transform(pc)
    player_pose = _resolve_drop_pose(pc, prefer_pawn=target_party_index is not None)
    if transform is None or player_pose is None:
        raise RuntimeError("Could not derive a spawn transform.")

    config = _get_pool_store()
    player_location, player_rotation = player_pose
    pool_list = list(pools)
    spawned = 0
    failed: list[str] = []

    _log_info(f"Spawning {len(pool_list)} shiny itempools at level {level} (blocking sync).")
    for index, pool_name in enumerate(pool_list):
        if index > 0:
            time.sleep(DROP_ALL_SHINIES_PACE_SEC)
        location, rotation = _spawn_pose(player_location, player_rotation, index, total=len(pool_list))
        spawn_name = _resolve_native_pool_name(pool_name)
        try:
            _spawn_pool(config, world, transform, level, spawn_name, location, rotation)
            spawned += 1
        except Exception as exc:
            failed.append(pool_name)
            _log_warning(f"Failed to spawn {pool_name}: {exc}")

    if failed:
        _log_warning(f"Spawned {spawned}/{len(pool_list)} shiny itempools. Failed: {', '.join(failed)}")
    else:
        _log_info(f"Spawned all {spawned} shiny itempools.")


def drop_all_shinies(
    level: int = DEFAULT_ITEM_LEVEL,
    *,
    target_party_index: int | None = None,
    shape: str = "none",
    settle: str = "none",
    drop_height: float = 440.0,
    line_length: float = 900.0,
    radius: float = 220.0,
    spacing: float = 140.0,
    spawn_then_shape: bool = False,
    stay_in_air: bool = True,
    peel_after: float = 0.0,
    land_profile: str = "shiny",
    fill_until_complete: bool = False,
    shape_text: str = "",
) -> int:
    """World-drop every curated shiny itempool (tick-paced; does not freeze the host).

    ``target_party_index`` is 0-based (same as Give_Serial index / party PC list).
    When set, drops near that player's feet; otherwise near the local player.
    ``shape`` none = pile at feet. ``settle`` none = no overhead drop.
    """
    return _queue_shiny_itempool_drop(
        SHINY_ITEMPOOLS,
        level,
        target_party_index=target_party_index,
        shape=shape,
        settle=settle,
        drop_height=drop_height,
        line_length=line_length,
        radius=radius,
        spacing=spacing,
        spawn_then_shape=spawn_then_shape,
        stay_in_air=stay_in_air,
        peel_after=peel_after,
        land_profile=land_profile,
        fill_until_complete=fill_until_complete,
        shape_text=shape_text,
    )


def drop_all_shiny_itempools(
    level: int = DEFAULT_ITEM_LEVEL,
    *,
    target_party_index: int | None = None,
) -> int:
    """Alias for :func:`drop_all_shinies` (world pools)."""
    return drop_all_shinies(level, target_party_index=target_party_index)


def probe_shiny_gate() -> str:
    """No runtime unlock — phosphene needs an edited save with shiny cosmetics loaded."""
    msg = (
        "Shiny/phosphene is save-gated. This mod does not unlock cosmetics. "
        "Load an edited save that already has Unlockable_Weapons.Shiny_* / story-complete, then Drop All Shinies."
    )
    _log_info(msg)
    return msg


@command("sqbt_probe_shiny", description="Remind that shiny/phosphene needs an edited save (no unlock).")
def _cmd_probe_shiny(_args: object) -> None:
    logging.info(probe_shiny_gate())
