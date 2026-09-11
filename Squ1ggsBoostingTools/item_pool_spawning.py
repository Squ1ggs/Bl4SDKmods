"""Generic item pool spawning helpers for Squ1ggs's Boosting Tools.

Squ1ggs Boosting Tools loot pool spawn:
``NexusConfigStoreItemPool.SpawnInventoryFromItemPool`` with the pool name
exactly as listed in ``item_pools.json`` (preserve casing; no merge.json).

Extras (raid catalog world-spawn paths, spawn-all caps) are secondary and must not
hijack that path for normal pool rows.
"""
from __future__ import annotations

import contextvars
import json
import os
import pkgutil
import re
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from unrealsdk import logging

from .shinies import (
    DEFAULT_ITEM_LEVEL,
    _get_player_pose,
    _get_pool_store,
    _get_runtime_pc,
    _get_spawn_transform,
    _get_world,
    _spawn_pool,
    _spawn_pose,
)

_ITEM_POOL_CACHE: list[dict[str, str]] | None = None
_GAME_DATA_POOL_ROWS: list[dict[str, str]] | None = None
_CURATED_POOL_KEYS: set[str] | None = None
_POOL_HEALTH_CACHE: dict[str, tuple[bool, str, str, bool]] = {}
_POOL_HEALTH_MTIME: float = -1.0

# Paced queue — SQBT's shared deferred tick. Spawn All is primarily a catalog
# health test, so keep it deliberately slower than single-item spawning.  A zero
# gap here turns the deferred queue into a frame-rate burst and can leave hundreds
# of live pickups in the world before the engine has had a chance to settle.
MAX_SPAWN_ALL_COUNT = 32
# "Spawn this one item" / single-pool count — user-chosen; paced tick keeps it smooth.
MAX_SINGLE_POOL_SPAWN_COUNT = 999
SPAWN_ALL_TEST_COUNT = 1
# One continuous queue — small waves + cooldown felt like "bursts" of loot.
SPAWN_ALL_WAVE_SIZE = 10000
SPAWN_ALL_DEFAULT_GAP_SEC = 0.10
SPAWN_ALL_MASS_AUTO_GAP_THRESHOLD = 40
SPAWN_ALL_VERIFY_SAMPLE_EVERY = 6
_SHAPE_FILL_TYPE_POOLS: tuple[str, ...] = (
    "itempool_sm_05_legendary",
    "itempool_sg_05_legendary",
    "itempool_ar_05_legendary",
    "itempool_smg_all",
    "itempool_shotgun_all",
    "itempool_assaultrifle_all",
)
_SHAPE_FILL_MAX_EXTRA = 400
SPAWN_ALL_WAVE_COOLDOWN_SEC = 0.0
SPAWN_ALL_SEGMENT_SIZE = 0
SPAWN_ALL_SEGMENT_PAUSE_SEC = 0.0
SPAWN_ALL_CLEANUP_EVERY = 16
SPAWN_ALL_CLEANUP_SETTLE_SEC = 0.0
SPAWN_ALL_CLEANUP_RADIUS = 900.0
_BULK_SPAWN_MIN_GAP_SEC = 0.0
_BULK_SPAWN_STEPS_PER_TICK = 1
_BULK_RANDOM_SPREAD = False
_LOOT_VERIFY_RADIUS = 1600.0
_LOOT_VERIFY_CLASSES = ("OakInventory", "OakWeapon", "Inventory")
_LOOT_VERIFY_SCAN_CAP = 500
_BULK_SPAWN_QUEUE: list[tuple[dict[str, str], int, int]] = []
_BULK_SPAWN_REMAINING: list[tuple[dict[str, str], int, int]] = []
_BULK_SPAWN_WAVE_TOTAL = 0
_BULK_SPAWN_WAVE_INDEX = 0
_BULK_SPAWN_WAVE_COOLDOWN_UNTIL = 0.0
_BULK_SPAWN_SEGMENT_COUNT = 0
_BULK_SPAWN_SEGMENT_PAUSE_UNTIL = 0.0
_BULK_SPAWN_HOOK_READY = False
_BULK_SHARED_TICK_QUEUED = False
_BULK_SPAWN_LAST_STEP = 0.0
_BULK_SPAWN_OK = 0
_BULK_SPAWN_FAIL = 0
_BULK_SPAWN_DRAINING = False
_BULK_SPAWN_SUMMARY_PENDING = False
_BULK_SPAWN_SUMMARY_DEFER_UNTIL = 0.0
_BULK_FINISH_SETTLED = False
_BULK_CLEANUP_DUE_AT = 0.0
_BULK_SPAWNS_SINCE_CLEANUP = 0
_BULK_PROTECTED_LOOT_KEYS: set[str] = set()
_BULK_CLEANUP_BASELINE_READY = False
_BULK_TEST_CLEANUP_ENABLED = False
_SPAWN_VERIFY_QUEUE: deque["_SpawnVerifyJob"] = deque()
_SPAWN_PENDING_KEYS: set[str] = set()
_PEARL_NCS_STORE: dict[str, int] = {}
# Test Singular Filtered: same Spawn Selected path (feet verify, no yank)
# for every matching named row, one at a time — never mass Spawn All shortcuts.
_SINGULAR_PATH_TEST = False
_SINGULAR_PATH_TEST_GAP_SEC = 0.35


def configure_bulk_spawn(
    *,
    gap_sec: float | None = None,
    per_tick: int | None = None,
    random_spread: bool | None = None,
) -> None:
    """Spawn All pacing: delay between items, items per tick, random spit vs pile."""
    global _BULK_SPAWN_MIN_GAP_SEC, _BULK_SPAWN_STEPS_PER_TICK, _BULK_RANDOM_SPREAD
    if gap_sec is not None:
        _BULK_SPAWN_MIN_GAP_SEC = max(0.0, min(2.0, float(gap_sec)))
    if per_tick is not None:
        _BULK_SPAWN_STEPS_PER_TICK = max(1, min(12, int(per_tick)))
    if random_spread is not None:
        _BULK_RANDOM_SPREAD = bool(random_spread)
    try:
        from .item_spawn.loot_verify import set_feet_verify_radius

        set_feet_verify_radius(2200.0)
    except Exception:
        pass


def _clear_bulk_spawn_perf_state() -> None:
    try:
        from .loot_shapes import pause_landing_catch, set_bulk_healthcheck_mode

        pause_landing_catch(False)
        set_bulk_healthcheck_mode(False)
    except Exception:
        pass


def _apply_mass_spawn_throttle(*, shaping: bool) -> None:
    """Large Spawn All batches: paced drain (GitHub 3.8.0 style)."""
    global _BULK_SPAWN_MIN_GAP_SEC, _BULK_SPAWN_STEPS_PER_TICK
    if _BULK_SPAWN_MIN_GAP_SEC <= 0.0:
        _BULK_SPAWN_MIN_GAP_SEC = float(SPAWN_ALL_DEFAULT_GAP_SEC)
    if _BULK_SPAWN_STEPS_PER_TICK > 1:
        _BULK_SPAWN_STEPS_PER_TICK = 1
    try:
        from .loot_shapes import pause_landing_catch, set_bulk_healthcheck_mode

        set_bulk_healthcheck_mode(True)
        if not shaping:
            pause_landing_catch(True)
    except Exception:
        pass
    _log_info(
        "Spawn All mass throttle: 1/tick, "
        f"{_BULK_SPAWN_MIN_GAP_SEC:.2f}s gap"
        + (", pin each drop" if shaping else ", pool-trust (no feet scan)")
        + "."
    )


def _bulk_feet_verify_this_step() -> bool:
    """Mass health-check skips find_all on most rows; sample every Nth for silent failures."""
    try:
        from .loot_shapes import landing_armed

        if landing_armed():
            return False
    except Exception:
        pass
    if not bulk_spawn_is_mass():
        return True
    # Flat mass Spawn All: trust pool RPC. find_all cost grows with feet pile size
    # and was the hitch after ~100 items even when each spawn was fast.
    return False

# The five live *_06_pearl parents produce random rolls, but this build's
# parent criteria omit these eight manifest Pearls.  Balanced parent requests
# reserve one requested result for each ground-only supplement, so x10 stays
# exactly ten and Pearl Spawn All stays exactly seventeen.
_PEARL_PARENT_SUPPLEMENT_CATALOGS: frozenset[str] = frozenset(
    {
        "ord_ar_comp_05_legendary_crowsourced",
        "tor_ps_comp_05_legendary_handcannon",
        "dad_ps_comp_05_legendary_soulsurvivor",
        "bor_sg_comp_05_legendary_crazedearl",
        "ted_sg_comp_05_legendary_eigenburst",
        "bor_sm_comp_05_legendary_jailbroken",
        "dad_sm_comp_05_legendary_raiden",
    }
)

# Six omitted names already use their exported *_pearl ids.  The companion
# pool-only patch adds deterministic ids for Jail-Broken and Raiden as well.
_PEARL_SUPPLEMENT_NATIVE_POOL_OVERRIDES: dict[str, str] = {
    "bor_sm_comp_05_legendary_jailbroken": "itempool_bor_sm_05_legendary_jailbroken",
    "dad_sm_comp_05_legendary_raiden": "itempool_dad_sm_05_legendary_raiden",
}

# Current patch `_NCS/Nexus-Data-ItemPoolList.ncs` entries which are embedded
# ItemPoolDef instances and have no standalone pool row in item_pools.json.
_PATCH_INLINE_INVENTORY_DEFS: dict[str, str] = {
    "jak_ar_comp_05_legendary_gomie": "inv'JAK_AR.comp_05_legendary_Gomie'",
    "bor_sr_comp_05_legendary_abyss": "inv'bor_sr.comp_05_legendary_Abyss'",
    "bor_sm_comp_05_legendary_jailbroken": "inv'BOR_SM.comp_05_legendary_Jailbroken'",
    "dad_sm_comp_05_legendary_raiden": "inv'DAD_SM.comp_05_legendary_Raiden'",
    "ord_sr_comp_05_legendary_temper": "inv'ORD_SR.comp_05_legendary_Temper'",
    "jak_sr_comp_05_legendary_burrow": "inv'JAK_SR.comp_05_legendary_Burrow'",
    "vla_repair_kit_comp_05_legendary_bloodiron": "inv'vla_repair_kit.comp_05_legendary_BloodIron'",
    "jak_sg_comp_05_legendary_verce": "inv'JAK_SG.comp_05_legendary_Verce'",
    "tor_hw_comp_05_legendary_loiter": "inv'TOR_HW.comp_05_legendary_Loiter'",
    "tor_shield_comp_05_legendary_hydrowerks": "inv'tor_shield.comp_05_legendary_hydrowerks'",
    # Dump/FModel use Pascal Slippy; all-lowercase often fails soft-resolve.
    "tor_grenade_gadget_comp_05_legendary_slippy": (
        "inv'tor_grenade_gadget.comp_05_legendary_Slippy'"
    ),
}
# Live NCS *_shiny twins that roll a different gun (ISP "wrong family").
# Never call SpawnInventoryFromItemPool on these — dump catalog inv only.
_WRONG_FAMILY_SHINY_POOLS: frozenset[str] = frozenset(
    {
        "itempool_jak_sr_legendary_burrow_shiny",  # rolls Fearstalker
    }
)
# Live *_shiny pool id whose inv comp lives under a different manufacturer prefix.
_SHINY_POOL_CATALOG_OVERRIDES: dict[str, str] = {
    "itempool_mal_sm_05_legendary_mercury_shiny": "vla_sm_comp_05_legendary_mercury",
}
# NCS audit (FModel Nexus-Data-itempool* / ItemPoolList / loot_config):
# - Conflux HAS live pool itempool_mal_sr_05_legendary_conflux_pearl
# - Kaoson: live NCS itempool_vla_sm_05_legendary_KaoSon_shiny (NOT DAD_AR Kaos — that
#   inv comp is ItemPoolList-only and has no inv4 / np_name row; in-game name is Kaoson)
# - Roil: ONLY itempool_mal_sg_05_legendary_roil_shiny → inv'BOR_SM.comp_05_legendary_Roil'
#   (itempool_bor_sm_05_legendary_roil does NOT exist)
# - Rainmaker: inv'bor_sr.comp_05_legendary_rainmaker' in loot_config/inv only —
#   NO itempool_* row at all (itempool_bor_sr_05_legendary_rainmaker is fake)
_NCS_DUMP_ONLY_INVS: dict[str, str] = {
    "bor_sm_comp_05_legendary_roil": "inv'BOR_SM.comp_05_legendary_Roil'",
    "bor_sr_comp_05_legendary_rainmaker": "inv'bor_sr.comp_05_legendary_rainmaker'",
    "jak_sr_comp_05_legendary_burrow": "inv'JAK_SR.comp_05_legendary_Burrow'",
}
# Named L5 dump invs (NCS live catalog) — base comps, no phosphene.
_NAMED_BASE_DUMP_INVS: dict[str, str] = {
    "vla_sr_comp_05_legendary_crowdsourced": "inv'VLA_SR.comp_05_legendary_CrowdSourced'",
    "dad_ar_comp_05_legendary_lumberjack": "inv'DAD_AR.comp_05_legendary_Lumberjack'",
    "ord_ar_comp_05_legendary_goalkeeper": "inv'ORD_AR.comp_05_legendary_Goalkeeper'",
    "ted_ar_comp_05_legendary_laserdisc": "inv'TED_AR.comp_05_legendary_laserdisc'",
    "jak_ar_comp_05_legendary_bonnieclyde": "inv'JAK_AR.comp_05_legendary_BonnieClyde'",
    "dad_ar_comp_05_legendary_kaos": "inv'DAD_AR.comp_05_legendary_Kaos'",
    "tor_sg_comp_05_legendary_cormano": "inv'TOR_SG.comp_05_legendary_Cormano'",
}
# FModel: Roil/Rainmaker only have mal_sg *_shiny twins — always force those.
# Midnight shiny is optional (same-family); never force it onto non-shiny Selected rows.
_DUMP_CATALOG_NATIVE_POOLS: dict[str, str] = {
    "bor_sm_comp_05_legendary_roil": "itempool_mal_sg_05_legendary_roil_shiny",
    "bor_sr_comp_05_legendary_rainmaker": "itempool_mal_sg_05_legendary_rainmaker_shiny",
    "vla_sr_comp_05_legendary_crowdsourced": "itempool_vla_sr_05_legendary_CrowdSourced_shiny",
}
_FORCE_SHINY_NATIVE_CATALOGS: frozenset[str] = frozenset(
    {
        "bor_sm_comp_05_legendary_roil",
        "bor_sr_comp_05_legendary_rainmaker",
    }
)
_FAKE_BASE_ITEMPOOLS: frozenset[str] = frozenset(
    {
        "itempool_bor_sm_05_legendary_roil",
        "itempool_bor_sr_05_legendary_rainmaker",
        # Spawn All _spawn_shiny=0 strips mal_sg *_shiny → these ghosts do not exist.
        "itempool_mal_sg_05_legendary_roil",
        "itempool_mal_sg_05_legendary_rainmaker",
        "itempool_patch_inline_jak_sr_burrow",
        "itempool_vla_sr_05_legendary_crowdsourced",
        "itempool_vla_sr_comp_05_legendary_crowdsourced",
    }
)
# Ground @U when dump inv / live mal_sg shiny miss (Lootlemon / shiny_serials).
_DUMP_ONLY_GROUND_SERIALS: dict[str, str] = {
    "bor_sm_comp_05_legendary_roil": (
        "@Ugv?-o35E/MjK>a&hbmN~5;bgS9;zm)B<dt84C)T*4=NO@7HSRRVeEGpzvt~TJw2X(@8vN3?f%ZuX?OlBf2Y/1"
    ),
    "bor_sr_comp_05_legendary_rainmaker": (
        "@Ugxp/&35E/MjK>a/hbmN~5;bI~9;zj(Ch8?BCaP0+P=8RNP`6O)Q2h`OV-LmnJ#Uxk>GAw~FNfi8_jis?yYpXpIPGqS*JU{"
    ),
    "vla_sr_comp_05_legendary_crowdsourced": (
        "@Uguq~c35E/MjK>aIi7M2g7By@rC8{QB4(cW<45/*Q7AhR79qJz9VeF?EzUS>SJw2X(ujMfO?fy>DX?OlRl)vxf>ANl;m&pJ"
    ),
}
# itempool8 deleted the base Crow-Sourced pool — dump/merge before native NCS.
_DUMP_FIRST_NCS_MISSING_POOLS: frozenset[str] = frozenset(
    {
        "itempool_ord_ar_05_legendary_crowsourced",
    }
)
# These pearls live as dump ItemPoolList inline defs, not a standalone itempool_*.
_PEARL_ITEMPOOLLIST_CATALOGS: frozenset[str] = frozenset(
    {
        "jak_ar_comp_05_legendary_gomie",
        "bor_sm_comp_05_legendary_jailbroken",
        "jak_sr_comp_05_legendary_burrow",
        "ord_ar_comp_05_legendary_pchonk",
    }
)
_STALE_OK_METHODS = frozenset(
    {
        "shiny_legacy_pool",
        "pearl_shiny_legacy",
        "bl4_shiny_world",
        "shiny_pool_api",
        "pearl_shiny_attempt",
        "pool_spawn",
        "ncs_verified_pool",
        "pearl_merge_inline",
        "bl4_pearl_merge_inline",
        "pearl_loyalty_mail",
        "pearl_loyalty_mail_fallback",
        "ncs_live_pool",
        "ncs_shiny_pool",
        "shiny_merge_inline",
    }
)
_BULK_VERIFY_MAX_ATTEMPTS = 12
_SPAWN_SESSION_OK = 0
_SPAWN_SESSION_FAIL = 0
_SPAWN_SESSION_STARTED_ISO: str = ""
_SPAWN_LOG_DIR = Path(__file__).resolve().parent / "logs"
_SPAWN_LOG_JSONL = _SPAWN_LOG_DIR / "spawn_test.jsonl"
_SPAWN_LOG_SUMMARY = _SPAWN_LOG_DIR / "spawn_test_summary.txt"
_SPAWN_FAILURES_LOG = _SPAWN_LOG_DIR / "spawn_failures.log"
_SPAWN_BATCH_LAST = _SPAWN_LOG_DIR / "spawn_batch_last.txt"
_SPAWN_BATCH_TRACE = _SPAWN_LOG_DIR / "spawn_batch_trace.log"
_SPAWN_BATCH_CHECKPOINT = _SPAWN_LOG_DIR / "spawn_batch_checkpoint.txt"
_SPAWN_LOG_MAX_SUMMARY_FAILS = 200

# Native engine crash quarantine.  These are not ordinary Python failures: the
# call never returns, so they must be rejected before entering Unreal.  Evidence:
# Slippy reproducibly produced EXCEPTION_STACK_OVERFLOW on GameThread at Spawn All
# row 144/630 (2026-08-05), with START but no RETURNED checkpoint.
_CRASH_UNSAFE_CATALOGS: dict[str, str] = {
    "tor_grenade_gadget_comp_05_legendary_slippy": (
        "confirmed native ItemPool_FishGrenade_Slippy GameThread stack overflow"
    ),
}
_CRASH_UNSAFE_POOLS: dict[str, str] = {
    "itempool_fishgrenade_slippy": (
        "confirmed native ItemPool_FishGrenade_Slippy GameThread stack overflow"
    ),
}
# Safe, pool-free fallbacks for entries whose native ItemPool is known to crash
# the game before Python can catch an exception.  Keep these explicit: an
# arbitrary serial should never silently bypass the native-crash quarantine.
_CRASH_SAFE_SERIALS: dict[str, str] = {
    "tor_grenade_gadget_comp_05_legendary_slippy": "@Uge8>*m/*xI!cYNCDpKpCxgneY",
}

_pearl_spawn_delivery: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
    "pearl_spawn_delivery",
    default={},
)


def _yank_singular_loot_in_front(*, before_keys: set[str] | None = None) -> None:
    """Disabled — post-spawn teleport is not natural front spawn.

    Placement must come from Squ1ggs NCS spit / exact dump Translation.
    """
    return


def _set_pearl_spawn_delivery(
    method: str,
    detail: str = "",
    *,
    skip_verify: bool = False,
    loot_verified: bool = False,
) -> None:
    _pearl_spawn_delivery.set(
        {
            "method": str(method or "").strip()[:64],
            "detail": str(detail or "").strip()[:240],
            "skip_verify": "1" if skip_verify else "",
            "loot_verified": "1" if loot_verified else "",
        }
    )
    # Do not yank here — no before_keys snapshot. Pump yanks once after spawn
    # when needed; yanking the whole world pile made items appear then vanish.


def _clear_pearl_spawn_delivery() -> None:
    _pearl_spawn_delivery.set({})


def _pearl_spawn_delivery_info() -> dict[str, str]:
    return dict(_pearl_spawn_delivery.get({}))


_TRUSTED_PEARL_GROUND_METHODS = frozenset(
    {
        "ncs_verified_pool",
        "ncs_pool",
        "ncs_generic_direct",
        "ncs_legacy_generic",
        "ncs_legacy_named",
        "pearl_serial",
        "pearl_merge",
        "pearl_merge_inline",
        "pearl_comp",
        "pearl_shiny",
        "bl4_pearl",
        "bl4_pearl_router",
        "bl4_pearl_merge_inline",
        "bl4_generic_pearl",
        "pearl_serial_retry",
        "dump_serial_ground",
        "dump_serial_retry",
        "legacy_pool_api",
        "native_store_api",
        "registered_pool_api",
        "inline_merge_comp",
        "discovery_generic_pearl",
        "ncs_live_pool",
        "ncs_shiny_pool",
        "pool_spawn",
        "patch_inline_verified",
        "shiny_merge_inline",
    }
)
_TRUSTED_DUMP_FIRST_METHODS = frozenset(
    {
        "dump_serial_ground",
        "dump_serial_retry",
        "pearl_serial",
        "pearl_serial_bulk",
        "pearl_merge",
        "pearl_merge_inline",
        "shiny_merge_inline",
        "ncs_shiny_pool",
        "ncs_live_pool",
        "ncs_named_pool",
        "pool_spawn",
        "patch_inline_verified",
        "patch_inline",
        "bl4_pearl_merge_inline",
        "dump_itempoollist",
        "dump_inline_comp",
        "dump_inv_lean",
        "dump_inv_def",
        "dump_inv_soft",
        "dump_inv_verified",
        "dump_inv_companion",
        "serial_ground",
        "ground_drop",
    }
)


def _log_info(message: str) -> None:
    logging.info(f"[Squ1ggs's Boosting Tools | Loot Pool Spawner] {_public_spawn_text(message)}")


def _log_warning(message: str) -> None:
    logging.warning(f"[Squ1ggs's Boosting Tools | Loot Pool Spawner] {_public_spawn_text(message)}")


def _public_spawn_text(value: object) -> str:
    """Remove backend implementation names from user-shareable logs."""
    text = str(value or "")
    text = re.sub(r"\bncs_[a-z0-9_]+\b", "pool_route", text, flags=re.IGNORECASE)
    text = re.sub(r"NexusConfigStoreItemPool", "loot pool service", text, flags=re.IGNORECASE)
    text = re.sub(r"BL4 Item Spawner", "external pool backend", text, flags=re.IGNORECASE)
    text = re.sub(r"Item Spawner", "Loot Pool Spawner", text, flags=re.IGNORECASE)
    text = re.sub(r"\bNCS(?:\s+store)?\b", "pool service", text, flags=re.IGNORECASE)
    return text


def _public_spawn_method(method: object) -> str:
    value = str(method or "").strip()[:64]
    low = value.lower()
    if low.startswith("ncs_") or low.startswith("pool_spawn"):
        return "pool_spawn"
    if "dump" in low or low in ("shiny_dump_inv", "pearl_shiny_inline"):
        try:
            from .loot_shapes import landing_label

            land = landing_label()
            if land:
                return land
        except Exception:
            pass
        return "ground_drop"
    return _public_spawn_text(value)[:64]


def _crash_quarantine_reason(entry: dict[str, str] | None) -> str:
    row = entry or {}
    catalog = str(row.get("catalog_key") or "").strip().lower()
    pool = str(row.get("itempool") or "").strip().lower()
    return _CRASH_UNSAFE_CATALOGS.get(catalog) or _CRASH_UNSAFE_POOLS.get(pool) or ""


def _method_is_trusted_dump_first(method: str) -> bool:
    method_l = str(method or "").strip().lower()
    if not method_l:
        return False
    if method_l in _TRUSTED_DUMP_FIRST_METHODS:
        return True
    return method_l.startswith(("pearl_merge", "dump_serial"))


def _bulk_dump_delivery_trusted(entry: dict[str, str], method: str) -> bool:
    """Dump-first / live pool reported ground delivery — skip same-tick feet scan."""
    delivery = _pearl_spawn_delivery_info()
    method_l = str(method or delivery.get("method") or "").strip().lower()
    # Shaped Spawn All cannot feet-verify (loot is yanked into slots). Trust the
    # spawn path when it reported success — rejecting pool_spawn here caused
    # 291/295 silent_empty with almost nothing on the silhouette.
    if _landing_shape_armed() and method_l in (
        "pool_spawn",
        "ncs_shiny_pool",
        "ncs_named_pool",
        "ncs_legacy",
        "ncs_legacy_bulk",
        "ncs_live_pool",
    ):
        if delivery.get("skip_verify") == "1" or delivery.get("loot_verified") == "1":
            return True
    if _bulk_trust_pool_delivery() and method_l in (
        "pool_spawn",
        "ncs_shiny_pool",
        "ncs_named_pool",
        "ncs_legacy",
        "ncs_legacy_bulk",
        "ncs_live_pool",
    ):
        if _is_named_unique_legendary_row(entry or {}, wants_shiny=False):
            dm = str(delivery.get("method") or method_l).strip().lower()
            if delivery.get("skip_verify") == "1" or delivery.get("loot_verified") == "1":
                if dm.startswith("dump_") or dm in _NAMED_UNIQUE_DUMP_METHODS:
                    return True
            return False
        if delivery.get("skip_verify") == "1" or delivery.get("loot_verified") == "1":
            return True
    # ISP-style lean singular: trust SpawnLootFromDef / dump return without find_all.
    if delivery.get("skip_verify") == "1" and (
        method_l in _TRUSTED_DUMP_FIRST_METHODS
        or method_l.startswith(("shiny_serial", "dump_", "pearl_serial", "pearl_merge", "ncs_"))
    ):
        return True
    if delivery.get("loot_verified") != "1":
        return False
    if method_l in _TRUSTED_PEARL_GROUND_METHODS or method_l in _TRUSTED_DUMP_FIRST_METHODS:
        pass
    else:
        return False
    catalog = str(entry.get("catalog_key") or "").strip().lower()
    pool = str(entry.get("itempool") or "").strip()
    if _pool_needs_dump_first(pool, catalog):
        return True
    try:
        from .item_spawn.pearlescent_manifest import pearlescent_row

        row = pearlescent_row(catalog)
        if row and row.get("comp_class") in ("pearl_pool", "p6", "pearl_world"):
            return True
    except Exception:  # noqa: BLE001
        pass
    return bool(catalog and _is_pearl_catalog(catalog))


def _landing_shape_armed() -> bool:
    """Shape landing places loot away from the feet, so feet scans cannot judge it."""
    try:
        from .loot_shapes import landing_armed

        return bool(landing_armed())
    except Exception:  # noqa: BLE001
        return False


def _skip_loot_verify() -> bool:
    # Singular-path test still feet-verifies. Spawn Selected drains like Spawn All.
    if _SINGULAR_PATH_TEST:
        return False
    if _BULK_SPAWN_DRAINING:
        return True
    return _landing_shape_armed()


def _is_wrong_family_shiny_pool(pool: str) -> bool:
    return str(pool or "").strip().lower() in _WRONG_FAMILY_SHINY_POOLS


def _inv_handle_casing_variants(*handles: str) -> list[str]:
    """Upper/lower root + Pascal/lower legendary|pearl tails — dump is casing-sensitive.

    Keep distinct casings (dedupe exact string only). Soft refs often fail on the
    wrong capitalisation even when the lower form looks identical.
    """
    out: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        h = str(raw or "").strip()
        if not h or h in seen:
            return
        seen.add(h)
        out.append(h)

    def _pascal_name(tail: str) -> str:
        return "".join(
            part[:1].upper() + part[1:].lower()
            for part in re.split(r"[_\s]+", str(tail or ""))
            if part
        )

    for handle in handles:
        h = str(handle or "").strip()
        if not h:
            continue
        add(h)
        match = re.match(r"^inv'([^']+)\.([^']+)'$", h, re.IGNORECASE)
        if not match:
            continue
        root, comp = match.group(1), match.group(2)
        add(f"inv'{root.upper()}.{comp}'")
        add(f"inv'{root.lower()}.{comp}'")
        add(f"inv'{root.upper()}.{comp.lower()}'")
        add(f"inv'{root.lower()}.{comp.lower()}'")
        # Match dump Pascal (comp_05_legendary_Slippy / Jailbroken), not
        # broken head_05LegendarySlippy tokens from a naive whole-comp pascalize.
        legen = re.match(r"(?i)^(comp_05_)(legendary_)(.+)$", comp)
        if legen:
            prefix, _mid, tail = legen.group(1), legen.group(2), legen.group(3)
            pascal = _pascal_name(tail)
            for r in (root, root.upper(), root.lower()):
                for mid_c in ("legendary_", "Legendary_"):
                    add(f"inv'{r}.{prefix}{mid_c}{tail.lower()}'")
                    add(f"inv'{r}.{prefix}{mid_c}{pascal}'")
            continue
        pearl = re.match(r"(?i)^(comp_06_)(pearl_)(.+)$", comp)
        if pearl:
            prefix, _mid, tail = pearl.group(1), pearl.group(2), pearl.group(3)
            pascal = _pascal_name(tail)
            for r in (root, root.upper(), root.lower()):
                for mid_c in ("pearl_", "Pearl_"):
                    add(f"inv'{r}.{prefix}{mid_c}{tail.lower()}'")
                    add(f"inv'{r}.{prefix}{mid_c}{pascal}'")
    return out


def _catalog_inv_handles(catalog: str) -> list[str]:
    """All known inv handles for a dump/patch catalog (patch + merge + dump index)."""
    cat = str(catalog or "").strip().lower()
    seeds: list[str] = []
    ncs = str(_NCS_DUMP_ONLY_INVS.get(cat) or "").strip()
    if ncs:
        seeds.append(ncs)
    base_dump = str(_NAMED_BASE_DUMP_INVS.get(cat) or "").strip()
    if base_dump:
        seeds.append(base_dump)
    patch = str(_PATCH_INLINE_INVENTORY_DEFS.get(cat) or "").strip()
    if patch:
        seeds.append(patch)
    try:
        from .item_spawn.legendary_dump_manifest import dump_inv_handles_for_catalog

        seeds.extend(dump_inv_handles_for_catalog(cat) or [])
    except Exception:  # noqa: BLE001
        pass
    try:
        from .item_spawn.pearl_comp_spawn import merge_payload_for_pearl_catalog

        payload = merge_payload_for_pearl_catalog(cat)
        if payload:
            seeds.extend(str(h) for h in (payload.get("handle_variants") or []) if h)
            for item in payload.get("items") or []:
                if isinstance(item, dict):
                    handle = (
                        ((item.get("item") or {}).get("item") or {}).get("handle")
                        if isinstance(item.get("item"), dict)
                        else None
                    )
                    if handle:
                        seeds.append(str(handle))
    except Exception:  # noqa: BLE001
        pass
    if cat and not seeds:
        match = re.match(r"^(.+)_(comp_0[56]_.+)$", cat)
        if match:
            root, comp = match.group(1), match.group(2)
            seeds.extend(
                [
                    f"inv'{root}.{comp}'",
                    f"inv'{root.upper()}.{comp}'",
                ]
            )
    return _inv_handle_casing_variants(*seeds)


def _spawn_proven_catalog_ground(
    catalog: str,
    *,
    count: int,
    level: int,
    display: str,
    pool: str = "",
    prefer_serial: bool = True,
    wants_shiny: bool | None = None,
    allow_native: bool = True,
    raise_on_miss: bool = True,
) -> int:
    """Rock-solid ground spawn for NCS dump-only / patch-inline catalogs.

    Normal legendaries: inline comp / dump inv (bl4_item_spawner parity).
    Shinies: dedicated *_shiny itempools + customization.
    ``allow_native=False`` skips live ItemPool calls (crash quarantine).
    """
    cat = str(catalog or "").strip().lower()
    label = str(display or cat or pool).strip() or "item"
    want = max(1, int(count))
    lvl = max(1, int(level))
    trust_rpc = (
        bool(_SINGULAR_PATH_TEST) or _spawn_queue_is_selected()
    ) and bool(allow_native)
    must_verify = not _skip_loot_verify() and not trust_rpc
    shiny_row = (
        bool(wants_shiny)
        if wants_shiny is not None
        else _wants_shiny_spawn(pool=pool, display=label)
    )

    handles = _catalog_inv_handles(cat)

    def _try_inline_comp_paths() -> int:
        if not handles:
            return 0
        from .item_spawn.comp_loot_drop import (
            spawn_inv_handles_at_feet,
            spawn_named_comp_inline_at_feet,
        )

        if not shiny_row:
            allow_list = (not bulk_spawn_is_mass()) or (cat in _CRASH_UNSAFE_CATALOGS)
            if allow_list:
                try:
                    from .item_spawn.item_pool_list_spawn import spawn_itempoollist_inv_at_feet

                    list_spawned, list_err = spawn_itempoollist_inv_at_feet(
                        handles[:4],
                        count=want,
                        level=lvl,
                        require_loot_verify=must_verify,
                        wants_shiny=False,
                    )
                    if list_spawned > 0:
                        _set_pearl_spawn_delivery(
                            "dump_itempoollist",
                            handles[0],
                            skip_verify=not must_verify,
                            loot_verified=must_verify,
                        )
                        return int(list_spawned)
                    if list_err:
                        _log_warning(f"{label}: ItemPoolList missed ({list_err}).")
                except Exception as list_exc:  # noqa: BLE001
                    _log_warning(f"{label}: ItemPoolList failed ({list_exc!r}).")

            inline_spawned, _inline_err = spawn_named_comp_inline_at_feet(
                handles[:6],
                count=want,
                level=lvl,
                skip_verify=not must_verify,
            )
            if inline_spawned > 0:
                _set_pearl_spawn_delivery(
                    "dump_inline_comp",
                    handles[0],
                    skip_verify=not must_verify,
                    loot_verified=must_verify,
                )
                return int(inline_spawned)
        # ItemPoolList for shiny rows (after inline miss in bulk-only paths).
        allow_list = (not bulk_spawn_is_mass()) or (cat in _CRASH_UNSAFE_CATALOGS)
        if allow_list and shiny_row:
            try:
                from .item_spawn.item_pool_list_spawn import spawn_itempoollist_inv_at_feet

                list_spawned, list_err = spawn_itempoollist_inv_at_feet(
                    handles[:4],
                    count=want,
                    level=lvl,
                    require_loot_verify=must_verify,
                    wants_shiny=shiny_row,
                )
                if list_spawned > 0:
                    _set_pearl_spawn_delivery(
                        "dump_itempoollist",
                        handles[0],
                        skip_verify=True,
                        loot_verified=True,
                    )
                    return int(list_spawned)
                if list_err:
                    _log_warning(f"{label}: ItemPoolList missed ({list_err}).")
            except Exception as list_exc:  # noqa: BLE001
                _log_warning(f"{label}: ItemPoolList failed ({list_exc!r}).")

        if cat:
            try:
                from .item_spawn.pearl_comp_spawn import try_spawn_pearl_comp_world

                merge = try_spawn_pearl_comp_world(
                    cat,
                    count=want,
                    level=lvl,
                    pool_name=pool if shiny_row else None,
                    drop_only=True,
                    skip_verify=not must_verify,
                )
                if merge.ok:
                    _set_pearl_spawn_delivery(
                        str(merge.method or "pearl_merge_inline"),
                        cat,
                        skip_verify=True,
                        loot_verified=True,
                    )
                    return want
            except Exception as merge_exc:  # noqa: BLE001
                _log_warning(f"{label}: merge missed ({merge_exc!r}).")

        spawned, err = spawn_inv_handles_at_feet(
            handles[:6],
            count=want,
            level=lvl,
            skip_verify=not must_verify,
        )
        if spawned > 0:
            _set_pearl_spawn_delivery(
                "dump_inv_verified",
                handles[0],
                skip_verify=True,
                loot_verified=True,
            )
            return int(spawned)
        if _BULK_SPAWN_DRAINING:
            _log_info(f"{label}: dump inv miss (trying next route).")
        else:
            _log_warning(f"{label}: dump inv missed ({err or 'empty'}).")
        return 0

    # Normal legendaries: comp-first (dump has no dedicated non-shiny itempool rows).
    if not shiny_row:
        inline_hit = _try_inline_comp_paths()
        if inline_hit > 0:
            return inline_hit

    if prefer_serial and cat:
        try:
            from .item_spawn.pearl_serial_spawn import try_spawn_catalog_via_serial

            ok, method = try_spawn_catalog_via_serial(cat, count=want)
            if ok:
                _set_pearl_spawn_delivery(
                    str(method or "pearl_serial"),
                    cat,
                    loot_verified=True,
                )
                return want
        except Exception as serial_exc:  # noqa: BLE001
            _log_warning(f"{label}: @U missed ({serial_exc!r}).")
        if shiny_row:
            shiny_serial = _curated_serial_for_dump_catalog(cat, pool, label)
            if shiny_serial:
                try:
                    from .item_spawn.pearl_serial_spawn import try_deliver_serial_comprehensive

                    ok, via = try_deliver_serial_comprehensive(
                        shiny_serial, want, prefer_ground=True, ground_only=True
                    )
                    if ok:
                        _set_pearl_spawn_delivery(
                            f"shiny_serial:{via}",
                            cat,
                            loot_verified=True,
                        )
                        return want
                except Exception as shiny_exc:  # noqa: BLE001
                    _log_warning(f"{label}: shiny @U missed ({shiny_exc!r}).")

    if shiny_row or not handles:
        inline_hit = _try_inline_comp_paths()
        if inline_hit > 0:
            return inline_hit

    # Registered NCS pool — shiny rows only, or non-shiny rows with a real base pool.
    if trust_rpc:
        for native in _native_legendary_pool_candidates(cat, pool, wants_shiny=shiny_row):
            native_l = str(native or "").strip().lower()
            if not native_l or native_l in _FAKE_BASE_ITEMPOOLS:
                continue
            if not _pool_matches_shiny_intent(native_l, shiny_row):
                continue
            if not _strict_registered_native_pool(native):
                continue
            try:
                hit = spawn_item_pool(native, lvl, want)
            except Exception:  # noqa: BLE001
                continue
            if hit > 0:
                _set_pearl_spawn_delivery(
                    "pool_spawn",
                    native,
                    loot_verified=True,
                )
                return int(hit)

    if prefer_serial and cat and shiny_row:
        shiny_serial = _curated_serial_for_dump_catalog(cat, pool, label)
        if shiny_serial:
            try:
                from .item_spawn.pearl_serial_spawn import try_deliver_serial_comprehensive

                ok, via = try_deliver_serial_comprehensive(
                    shiny_serial, want, prefer_ground=True, ground_only=True
                )
                if ok:
                    _set_pearl_spawn_delivery(
                        f"shiny_serial_retry:{via}",
                        cat,
                        loot_verified=True,
                    )
                    return want
            except Exception:  # noqa: BLE001
                pass

    if raise_on_miss:
        raise RuntimeError(
            f"{label}: no ground loot (serial/ItemPoolList/merge/dump all missed). "
            "Stand on open ground and retry."
        )
    return 0


def _patch_inline_catalog_from_pool(pool: str) -> str:
    low = str(pool or "").strip().lower()
    prefix = "itempool_patch_inline_"
    if not low.startswith(prefix):
        return ""
    rest = low[len(prefix) :]
    marker = "_comp_05_legendary_"
    for cat in _PATCH_INLINE_INVENTORY_DEFS:
        if marker not in cat:
            continue
        root, uniq = cat.split(marker, 1)
        if f"{root}_{uniq}".lower() == rest:
            return cat
    return ""


def _spawn_crash_safe_serial(entry: dict[str, str], count: int, *, level: int = DEFAULT_ITEM_LEVEL) -> int | None:
    """Dump/serial ground spawn for quarantined native pools — never call Unreal ItemPool.

    Slippy's ItemPool_FishGrenade_Slippy overflows GameThread; stay on dump inv /
    StealthPredator list / @U only. Reuse proven dump routes (inline-first) so
    Spawn All does not hitch on ItemPoolList scans.
    """
    catalog = str(entry.get("catalog_key") or "").strip().lower()
    pool = str(entry.get("itempool") or "").strip()
    display = str(entry.get("display_name") or catalog or pool).strip() or "item"
    if not catalog:
        catalog = _patch_inline_catalog_from_pool(pool)
        if pool.lower() == "itempool_fishgrenade_slippy":
            catalog = "tor_grenade_gadget_comp_05_legendary_slippy"
    if not catalog:
        return None
    want = max(1, int(count))
    lvl = max(1, int(level))
    try:
        hit = _spawn_proven_catalog_ground(
            catalog,
            count=want,
            level=lvl,
            display=display,
            pool="",
            prefer_serial=True,
            wants_shiny=False,
            allow_native=False,
        )
        if hit > 0:
            return int(hit)
    except Exception as exc:  # noqa: BLE001
        _log_warning(f"{display}: crash-safe dump missed ({exc!r}).")
    serial = _CRASH_SAFE_SERIALS.get(catalog)
    if not serial:
        return None
    try:
        return _deliver_catalog_serial_ground_only(serial, want, display)
    except Exception as serial_exc:  # noqa: BLE001
        _log_warning(f"{display}: crash-safe @U missed ({serial_exc!r}).")
        return None


def _spawn_log_paths() -> tuple[Path, Path, Path]:
    return _SPAWN_LOG_JSONL, _SPAWN_LOG_SUMMARY, _SPAWN_FAILURES_LOG


def _bulk_trace(entry: dict[str, str], index: int, state: str, detail: str = "") -> None:
    """Durable pre-spawn checkpoint; survives a native game crash mid-pool."""
    from datetime import datetime, timezone

    display = str(entry.get("display_name") or entry.get("itempool") or "pool").strip()
    pool = str(entry.get("itempool") or "").strip()
    catalog = str(entry.get("catalog_key") or "").strip()
    public_detail = _public_spawn_text(detail)
    line = (
        f"{datetime.now(timezone.utc).isoformat()} | {state} | "
        f"{index}/{_BULK_SPAWN_WAVE_TOTAL} | {display} | pool={pool} | "
        f"catalog={catalog} | {public_detail[:240]}\n"
    )
    try:
        _SPAWN_LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _SPAWN_BATCH_TRACE.open("a", encoding="utf-8") as handle:
            handle.write(line)
        _SPAWN_BATCH_CHECKPOINT.write_text(line, encoding="utf-8")
    except OSError as exc:
        _log_warning(f"Could not write Spawn All checkpoint: {exc}")


def _invalidate_pool_health_cache() -> None:
    global _POOL_HEALTH_MTIME
    _POOL_HEALTH_MTIME = -1.0


def record_spawn_result(
    entry: dict[str, str] | None,
    *,
    ok: bool,
    method: str,
    detail: str,
    count: int = 1,
    level: int = DEFAULT_ITEM_LEVEL,
    display_name: str = "",
    observed: bool = False,
    delivery_channel: str = "ground",
) -> None:
    """Append one spawn attempt to spawn_test.jsonl and refresh on-disk summaries."""
    from datetime import datetime, timezone

    global _SPAWN_SESSION_OK, _SPAWN_SESSION_FAIL

    row = entry or {}
    display = str(display_name or row.get("display_name") or row.get("itempool") or "pool").strip()
    pool = str(row.get("itempool", "") or "")
    catalog = str(row.get("catalog_key", "") or "")
    category = str(row.get("category", "Other") or "Other")
    method = _public_spawn_method(method or ("ok" if ok else "fail"))
    detail = _public_spawn_text(detail).strip()[:500]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    channel = str(delivery_channel or "ground").strip().lower()[:32] or "ground"
    reported_ok = bool(ok)
    confirmed_ok = bool(reported_ok and observed)
    if confirmed_ok:
        _SPAWN_SESSION_OK += 1
    else:
        _SPAWN_SESSION_FAIL += 1

    payload = {
        "ts_iso": ts,
        "display_name": display,
        "pool_name": pool,
        "catalog_key": catalog,
        "category": category,
        "count": max(1, int(count)),
        "level": max(1, int(level)),
        "ok": confirmed_ok,
        "reported_ok": reported_ok,
        # Keep the original field ground-specific and record backpack/reward
        # confirmation separately.  Old JSONL rows remain readable through the
        # delivery_observed fallback used by the summary loader below.
        "loot_observed": bool(observed and channel == "ground"),
        "delivery_observed": bool(observed),
        "delivery_channel": channel,
        "method": method,
        "detail": detail,
    }

    status = "OK" if confirmed_ok else ("UNVERIFIED" if reported_ok else "FAIL")
    console_line = (
        f"Spawn {status} [{category}] {display} ({pool or catalog}) "
        f"x{payload['count']} @{payload['level']} — {method}: {detail[:160]}"
    )
    # Dump/Spawn All already has the trace file. Console-spamming every OK
    # line is the "same thing running constantly" loop.
    if confirmed_ok:
        if not bulk_spawn_active():
            _log_info(console_line)
    else:
        _log_warning(console_line)

    try:
        _SPAWN_LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _SPAWN_LOG_JSONL.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        if not confirmed_ok:
            fail_line = f"{ts} | {display} | pool={pool} | catalog={catalog} | {detail}"
            with _SPAWN_FAILURES_LOG.open("a", encoding="utf-8") as fh:
                fh.write(fail_line + "\n")
        if not bulk_spawn_active():
            _rewrite_spawn_summary()
            _invalidate_pool_health_cache()
    except OSError as exc:
        _log_warning(f"Could not write spawn log: {exc}")


def _rewrite_spawn_summary() -> None:
    from datetime import datetime, timezone

    entries: list[dict[str, object]] = []
    sanitized_existing = False
    try:
        if _SPAWN_LOG_JSONL.is_file():
            with _SPAWN_LOG_JSONL.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                        old_method = str(row.get("method") or "")
                        old_detail = str(row.get("detail") or "")
                        row["method"] = _public_spawn_method(old_method)
                        row["detail"] = _public_spawn_text(old_detail)
                        sanitized_existing = sanitized_existing or (
                            row["method"] != old_method or row["detail"] != old_detail
                        )
                        entries.append(row)
                    except Exception:
                        continue
    except OSError:
        entries = []

    if sanitized_existing:
        try:
            with _SPAWN_LOG_JSONL.open("w", encoding="utf-8") as handle:
                for entry in entries:
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            _log_warning(f"Could not sanitize existing spawn log: {exc}")

    def _entry_observed(entry: dict[str, object]) -> bool:
        return bool(entry.get("delivery_observed", entry.get("loot_observed", False)))

    oks = [e for e in entries if e.get("ok") and _entry_observed(e)]
    unverified = [
        e
        for e in entries
        if not (e.get("ok") and _entry_observed(e))
        and bool(e.get("reported_ok") or e.get("ok"))
    ]
    fails = [
        e
        for e in entries
        if not e.get("ok") and not bool(e.get("reported_ok"))
    ]
    total_ok = len(oks)
    total_fail = len(fails)

    by_cat_fail: dict[str, list[str]] = {}
    # Only THIS session's fails — older runs (e.g. 291 silent_empty) were drowning
    # the summary so it looked like "many fails" after a clean 290/5 pass.
    session_fails = fails
    if _SPAWN_SESSION_STARTED_ISO:
        session_fails = [
            e
            for e in fails
            if str(e.get("ts_iso") or "") >= _SPAWN_SESSION_STARTED_ISO
        ]
    for entry in session_fails[-_SPAWN_LOG_MAX_SUMMARY_FAILS:]:
        cat = str(entry.get("category") or "Other")
        label = str(entry.get("display_name") or entry.get("pool_name") or "?")
        pool = str(entry.get("pool_name") or "")
        detail = _public_spawn_text(entry.get("detail") or "")[:120]
        by_cat_fail.setdefault(cat, []).append(f"  - {label} | {pool} | {detail}")

    by_cat_ok: dict[str, int] = {}
    for entry in oks:
        cat = str(entry.get("category") or "Other")
        by_cat_ok[cat] = by_cat_ok.get(cat, 0) + 1

    lines = [
        "Squ1ggs Boosting Tools — spawn test summary",
        f"updated: {datetime.now(timezone.utc).isoformat()}",
        f"log file: {_SPAWN_LOG_JSONL}",
        f"failures-only: {_SPAWN_FAILURES_LOG}",
        f"all-time log: {total_ok} observed OK, {len(unverified)} unverified, "
        f"{total_fail} fail ({len(entries)} rows)",
        f"session: {_SPAWN_SESSION_OK} ok, {_SPAWN_SESSION_FAIL} fail",
        "",
        "Successes by category (all-time observed):",
    ]
    if not by_cat_ok:
        lines.append("  (none recorded)")
    else:
        for cat in sorted(by_cat_ok):
            lines.append(f"  [{cat}] {by_cat_ok[cat]} ok")

    lines += ["", "This session failures:"]
    if not by_cat_fail:
        lines.append("  (none this session)")
    else:
        for cat in sorted(by_cat_fail):
            lines.append(f"[{cat}]")
            lines.extend(by_cat_fail[cat][-20:])

    try:
        _SPAWN_LOG_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        _log_warning(f"Could not write spawn summary: {exc}")


def clear_spawn_log_session(*, clear_files: bool = False) -> None:
    """Reset session counters; optionally truncate on-disk spawn logs."""
    global _SPAWN_SESSION_OK, _SPAWN_SESSION_FAIL, _BULK_SPAWN_OK, _BULK_SPAWN_FAIL
    global _BULK_SPAWN_SUMMARY_PENDING, _BULK_SPAWN_REMAINING, _BULK_SPAWN_WAVE_TOTAL
    global _BULK_SPAWN_WAVE_INDEX, _BULK_SPAWN_WAVE_COOLDOWN_UNTIL
    global _BULK_SPAWN_SUMMARY_DEFER_UNTIL, _BULK_FINISH_SETTLED, _SINGULAR_PATH_TEST
    global _SPAWN_SESSION_STARTED_ISO
    from datetime import datetime, timezone

    _SPAWN_SESSION_OK = 0
    _SPAWN_SESSION_FAIL = 0
    _SPAWN_SESSION_STARTED_ISO = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _BULK_SPAWN_OK = 0
    _BULK_SPAWN_FAIL = 0
    _BULK_SPAWN_SUMMARY_PENDING = False
    _BULK_SPAWN_SUMMARY_DEFER_UNTIL = 0.0
    _BULK_FINISH_SETTLED = False
    _SINGULAR_PATH_TEST = False
    _BULK_SPAWN_REMAINING.clear()
    _BULK_SPAWN_WAVE_TOTAL = 0
    _BULK_SPAWN_WAVE_INDEX = 0
    _BULK_SPAWN_WAVE_COOLDOWN_UNTIL = 0.0
    _SPAWN_VERIFY_QUEUE.clear()
    _SPAWN_PENDING_KEYS.clear()
    try:
        from .item_spawn.loot_verify import reset_claimed_loot_keys

        reset_claimed_loot_keys()
    except Exception:  # noqa: BLE001
        pass
    if not clear_files:
        _log_info("Spawn log session counters reset (files kept).")
        return
    try:
        _SPAWN_LOG_DIR.mkdir(parents=True, exist_ok=True)
        for path in (
            _SPAWN_LOG_JSONL,
            _SPAWN_FAILURES_LOG,
            _SPAWN_BATCH_LAST,
            _SPAWN_BATCH_TRACE,
            _SPAWN_BATCH_CHECKPOINT,
        ):
            if path.is_file():
                path.write_text("", encoding="utf-8")
        _rewrite_spawn_summary()
        _invalidate_pool_health_cache()
        _log_info("Spawn logs cleared (spawn_test.jsonl + spawn_failures.log).")
    except OSError as exc:
        _log_warning(f"Could not clear spawn logs: {exc}")


def _bulk_spawn_simple_mode() -> bool:
    return bool(_BULK_SPAWN_DRAINING or bulk_spawn_active())


def bulk_spawn_active() -> bool:
    """True while a Spawn All / singular-test batch is queued or draining."""
    return bool(
        _BULK_SPAWN_QUEUE
        or _BULK_SPAWN_REMAINING
        or _BULK_CLEANUP_DUE_AT
        or (_SINGULAR_PATH_TEST and _SPAWN_VERIFY_QUEUE)
    )


def _bulk_spawn_ui_active() -> bool:
    """True until batch finish settle + summary are done (progress bar / deferred tick)."""
    return bool(
        bulk_spawn_active()
        or _SPAWN_VERIFY_QUEUE
        or _BULK_SPAWN_SUMMARY_PENDING
        or _BULK_SPAWN_DRAINING
    )


def bulk_spawn_draining() -> bool:
    return bool(_BULK_SPAWN_DRAINING)


def _spawn_queue_is_single() -> bool:
    """True only for the Singular-path test (deferred feet verify)."""
    return bool(_SINGULAR_PATH_TEST)


def _spawn_queue_is_selected() -> bool:
    """True for Spawn Selected / Spawn this one item (one-row queue)."""
    if _SINGULAR_PATH_TEST:
        return False
    return int(_BULK_SPAWN_WAVE_TOTAL) == 1


def _bulk_trust_pool_delivery() -> bool:
    """Trust live NCS pool_spawn for Spawn All and Spawn Selected (same drain path).

    Singular-path test still requires feet loot. Selected uses the same live-first
    drain as Spawn All Filtered — no separate verify-defer gate (that caused lag).
    """
    if _SINGULAR_PATH_TEST:
        return False
    return bool(_BULK_SPAWN_DRAINING)


def bulk_spawn_is_mass() -> bool:
    """True for large Spawn All waves — skip per-item pickup scans."""
    if _SINGULAR_PATH_TEST or _spawn_queue_is_selected():
        return False
    return int(_BULK_SPAWN_WAVE_TOTAL) > 8 or bool(_BULK_SPAWN_REMAINING)


def _spawn_named_l5_bulk_mode() -> bool:
    """Spawn All Filtered mass batch — live pool first, no slow dump/@U chain per row."""
    if _SINGULAR_PATH_TEST or _spawn_queue_is_selected():
        return False
    return bool(_BULK_SPAWN_DRAINING and bulk_spawn_is_mass())


def _is_named_singular_row(entry: dict[str, str]) -> bool:
    """Named guns (catalog / > rows) — what Spawn Named Item exercises."""
    if str(entry.get("catalog_key") or "").strip():
        return True
    name = str(entry.get("display_name") or "").strip()
    return name.startswith(">")


def _is_named_unique_legendary_row(entry: dict[str, str], *, wants_shiny: bool = False) -> bool:
    """True for a specific legendary gun (Laser Disker), not mixed AR/PS 05 pools.

    Named uniques (Laser Disker) have no live base pool. The registered
    *_shiny twin is the dedicated unique row and drops the gun on the ground.
    Mixed pools (itempool_ar_05_legendary, Enhancements 05, AR 03 Rare) stay
    on their own live NCS ids. Synthetic base itempool_*_05_legendary_token
    names silent-OK with no loot.
    """
    if wants_shiny:
        return False
    catalog = str(entry.get("catalog_key") or "").strip().lower()
    if "_comp_05_legendary_" not in catalog:
        return False
    pool = str(entry.get("itempool") or "").strip().lower()
    if pool.endswith("_shiny") or "_shiny_" in pool:
        return False
    return True


def _bulk_row_requires_loot_verify(entry: dict[str, str]) -> bool:
    """Named L5 / unregistered pools must not count as ok without feet loot."""
    if _is_named_unique_legendary_row(entry, wants_shiny=False):
        return True
    pool = str(entry.get("itempool") or "").strip()
    if pool and not _strict_registered_native_pool(pool):
        cat = str(entry.get("catalog_key") or "").strip().lower()
        if cat and "_comp_05_legendary_" in cat:
            return True
    return False


_NAMED_UNIQUE_DUMP_METHODS = frozenset(
    {
        "dump_serial_ground",
        "dump_itempoollist",
        "dump_inline_comp",
        "dump_inv_def",
        "dump_inv_selected_rescue",
        "dump_inv_companion",
        "dump_inv_lean",
        "dump_inv_verified",
        "patch_inline_verified",
        "serial_ground",
        # Registered *_shiny twin without phosphene apply (dump miss fallback).
        "ncs_named_twin",
    }
)


def _spawn_named_unique_via_registered_twin(
    entry: dict[str, str],
    *,
    catalog: str,
    display: str,
    count: int,
    level: int,
) -> int:
    """Ground-drop the registered NCS twin (usually *_shiny) without phosphene apply.

    Many named L5s have no live base itempool — only the *_shiny twin is in NCS.
    SpawnInventoryFromItemPool still drops that unique. We do NOT call
    prepare_shiny_pool_context / apply phosphene: save cosmetics decide look.
    """
    row = dict(entry)
    pool = str(row.get("itempool") or "").strip()
    twin = _registered_named_unique_ncs_pool(catalog, pool) or ""
    if not twin:
        return 0
    want = max(1, int(count))
    lvl = max(1, int(level))
    try:
        from .item_spawn.ncs_pool_spawn import spawn_legacy_itempool

        hit, _err = spawn_legacy_itempool([twin], count=want, level=lvl)
    except Exception:  # noqa: BLE001
        hit = 0
    if hit <= 0:
        try:
            hit = int(spawn_item_pool(twin, lvl, want) or 0)
        except Exception:  # noqa: BLE001
            hit = 0
    if hit <= 0:
        return 0
    _set_pearl_spawn_delivery(
        "ncs_named_twin",
        twin,
        skip_verify=True,
        loot_verified=False,
    )
    _log_info(
        f"Spawned {display} via NCS twin {twin} "
        "(no phosphene apply — cosmetics decide look)."
    )
    return int(hit)


def _named_unique_base_after_dump_miss(
    entry: dict[str, str],
    *,
    catalog: str,
    display: str,
    count: int,
    level: int,
) -> int:
    """Loot-tab named L5 after dump/@U miss — NCS twin ground drop, never mail."""
    try:
        proven = _spawn_proven_catalog_ground(
            catalog,
            count=count,
            level=level,
            display=display,
            pool="",
            prefer_serial=True,
            wants_shiny=False,
            allow_native=False,
        )
    except RuntimeError:
        proven = 0
    if proven > 0:
        return int(proven)
    twin_hit = _spawn_named_unique_via_registered_twin(
        entry,
        catalog=catalog,
        display=display,
        count=count,
        level=level,
    )
    if twin_hit > 0:
        return twin_hit
    raise RuntimeError(
        f"{display}: named legendary dump / @U / NCS twin missed (catalog={catalog}). "
        "Try Spawn All Filtered on this weapon tab, or the type pool "
        "(AR / SG / SM / PS / SR 05 Legendary)."
    )


def _spawn_named_l5_dump_inv(
    entry: dict[str, str],
    *,
    catalog: str,
    pool: str,
    display: str,
    count: int,
    level: int,
    skip_pool: bool = False,
) -> int:
    """Named L5 non-shiny — dump inv'ROOT.comp_* first (no phosphene). Pool only if skip_pool=False."""
    row = dict(entry)
    cat = str(catalog or row.get("catalog_key") or "").strip().lower()
    if not cat:
        return 0
    want = max(1, int(count))
    lvl = max(1, int(level))
    bulk = _spawn_named_l5_bulk_mode()
    if bulk:
        skip_pool = False
    live_shiny = _registered_named_unique_ncs_pool(cat, pool) or ""
    selected = _spawn_queue_is_selected()
    before_keys = _selected_feet_loot_keys() if selected else None

    from .item_spawn.shiny_pool_lookup import (
        inline_payload_for_base_legendary,
        inv_handles_for_named_unique,
    )

    handles: list[str] = []
    seen_h: set[str] = set()

    def add_handle(raw: str) -> None:
        text = str(raw or "").strip()
        if not text:
            return
        if not text.lower().startswith("inv'"):
            text = f"inv'{text}'"
        low = text.lower()
        if low in seen_h:
            return
        seen_h.add(low)
        handles.append(text)

    dump_inv = str(row.get("dump_inv") or "").strip()
    if dump_inv:
        add_handle(dump_inv)
    for handle in inv_handles_for_named_unique(cat, live_shiny) or []:
        add_handle(handle)
    for handle in _catalog_inv_handles(cat):
        add_handle(handle)
    try:
        from .item_spawn.comp_loot_drop import _comp_inv_handle_variants

        for base in list(handles):
            inner = base.replace("inv'", "").replace("'", "")
            for variant in _comp_inv_handle_variants(inner) or []:
                add_handle(variant)
    except Exception:  # noqa: BLE001
        pass
    try_handles = handles[:8]

    def _feet_ok() -> bool:
        if before_keys is None:
            return False
        return _selected_saw_new_loot(before_keys)

    def _finish(method: str, detail: str, spawned: int, *, verified: bool = False) -> int:
        trust = bool(verified or (before_keys is not None and _feet_ok()))
        _set_pearl_spawn_delivery(
            method,
            detail,
            skip_verify=not trust,
            loot_verified=trust,
        )
        _log_info(f"Spawned {display} via {method} ({detail}).")
        return int(spawned)

    ui_pool = str(pool or row.get("itempool") or "").strip()
    try_names: list[str] = []
    seen_pool: set[str] = set()

    def add_pool(raw: str) -> None:
        name = str(raw or "").strip()
        low = name.lower()
        if not name or low in seen_pool:
            return
        if low.endswith("_shiny") or "_shiny_" in low:
            return
        seen_pool.add(low)
        try_names.append(name)

    if ui_pool:
        add_pool(ui_pool)
    for cand in _native_legendary_pool_candidates(cat, ui_pool, wants_shiny=False):
        if _pool_matches_shiny_intent(cand, False):
            add_pool(cand)
    for cand in _pool_name_candidates(ui_pool):
        add_pool(cand)

    # 1) Live pool — Item Spawner trusts SpawnInventoryFromItemPool RPC (defer feet verify).
    if not skip_pool:
        from .item_spawn.ncs_pool_spawn import spawn_legacy_itempool

        for cand in try_names:
            for native in _pool_name_candidates(cand):
                try:
                    pool_hit, _err = spawn_legacy_itempool([native], count=want, level=lvl)
                except Exception:
                    pool_hit = 0
                if pool_hit > 0:
                    return _finish(
                        "pool_spawn",
                        native,
                        pool_hit,
                        verified=_feet_ok(),
                    )

        # 2) Bundled bl4_item_spawner router when the mod is loaded (Matts / hooked widget).
        try:
            from .item_spawn.bl4_spawn_delegate import bl4_item_spawner_available

            if bl4_item_spawner_available():
                import bl4_item_spawner as bis

                for cand in try_names:
                    try:
                        bis.CONTROLLER._spawn_from_pool(
                            cand, want, lvl, skip_raid_bridge=True
                        )
                    except Exception:
                        continue
                    return _finish("bl4_pool", cand, want, verified=_feet_ok())
        except Exception as exc:  # noqa: BLE001
            _log_warning(f"{display}: bl4_item_spawner pool miss ({exc})")

    if bulk:
        return _spawn_named_unique_via_registered_twin(
            row,
            catalog=cat,
            display=display,
            count=want,
            level=lvl,
        )

    # 3) ItemPoolList embed (dump boss lists — base inv, no phosphene).
    if try_handles:
        try:
            from .item_spawn.item_pool_list_spawn import spawn_itempoollist_inv_at_feet

            ipl_hit, _ipl_err = spawn_itempoollist_inv_at_feet(
                try_handles,
                count=want,
                level=lvl,
                require_loot_verify=False,
                wants_shiny=False,
            )
            if ipl_hit > 0:
                return _finish(
                    "dump_itempoollist",
                    try_handles[0],
                    ipl_hit,
                    verified=_feet_ok(),
                )
        except Exception as exc:  # noqa: BLE001
            _log_warning(f"{display}: ItemPoolList spawn failed ({exc})")

    # 4) Inline inv comp (__synthetic merge — SpawnLootFromData / SpawnLootFromDef).
    payload = inline_payload_for_base_legendary(live_shiny, catalog=cat)
    if payload and try_handles:
        payload = dict(payload)
        payload["handle_variants"] = try_handles
        payload["items"] = [{"item": {"item": {"handle": try_handles[0]}}}]
    from .item_spawn.comp_loot_drop import spawn_from_merge_payload

    if payload:
        spawned, inline_err = spawn_from_merge_payload(
            payload,
            count=want,
            level=lvl,
            skip_verify=True,
            pool_name="",
            drop_only=False,
        )
        if spawned > 0:
            return _finish(
                "dump_inline_comp",
                try_handles[0] if try_handles else cat,
                spawned,
                verified=_feet_ok(),
            )
        if inline_err:
            _log_warning(f"{display}: inline inv miss ({inline_err})")

    # 5) @U serial (discovery_row backup).
    try:
        from .item_spawn.pearl_serial_spawn import (
            serials_for_catalog,
            try_spawn_catalog_via_serial,
        )

        ok, via = try_spawn_catalog_via_serial(cat, count=want)
        if ok:
            return _finish("dump_serial_ground", via, want, verified=_feet_ok())
        seen_serial: set[str] = set()
        for serial in serials_for_catalog(cat):
            serial = str(serial or "").strip()
            if not serial.startswith("@U") or serial in seen_serial:
                continue
            seen_serial.add(serial)
            try:
                n = _deliver_catalog_serial_ground_only(serial, want, display)
            except Exception:  # noqa: BLE001
                n = 0
            if n > 0:
                return _finish("dump_serial_ground", serial[:48], n, verified=_feet_ok())
    except Exception as exc:  # noqa: BLE001
        _log_warning(f"{display}: @U serial paths failed ({exc})")

    serial = str(_curated_serial_for_dump_catalog(cat, pool, display) or "").strip()
    if serial.startswith("@U"):
        try:
            n = _deliver_catalog_serial_ground_only(serial, want, display)
        except Exception:  # noqa: BLE001
            n = 0
        if n > 0:
            return _finish("dump_serial_ground", serial[:48], n, verified=_feet_ok())

    return 0


# Back-compat alias
_spawn_named_l5_verified = _spawn_named_l5_dump_inv


def bulk_spawn_status() -> dict[str, Any]:
    """Structured Spawn All progress for the desktop progress bar."""
    queued = len(_BULK_SPAWN_QUEUE)
    pending = len(_BULK_SPAWN_REMAINING)
    total = int(_BULK_SPAWN_WAVE_TOTAL)
    now = time.monotonic()
    pausing = bool(_BULK_SPAWN_SEGMENT_PAUSE_UNTIL and now < _BULK_SPAWN_SEGMENT_PAUSE_UNTIL)
    cleaning = bool(_BULK_CLEANUP_DUE_AT and now < _BULK_CLEANUP_DUE_AT)
    active = bool(
        queued
        or pending
        or pausing
        or cleaning
        or _SPAWN_VERIFY_QUEUE
        or _bulk_spawn_ui_active()
    )
    done = max(0, total - queued - pending) if total else 0
    return {
        "active": active,
        "queued": bool(queued or pending),
        "index": done,
        "total": total,
        "ok": int(_BULK_SPAWN_OK),
        "failed": int(_BULK_SPAWN_FAIL),
        "wave": int(_BULK_SPAWN_WAVE_INDEX),
        "message": bulk_spawn_status_line(),
    }


def bulk_spawn_status_line() -> str:
    """Human-readable spawn-queue progress (for dump + UI)."""
    queued = len(_BULK_SPAWN_QUEUE)
    pending = len(_BULK_SPAWN_REMAINING)
    total = int(_BULK_SPAWN_WAVE_TOTAL)
    singular_test = bool(_SINGULAR_PATH_TEST)
    selected = _spawn_queue_is_selected()
    single = singular_test or selected
    if singular_test:
        label = "Singular test"
    elif selected:
        label = "Spawn selected"
    else:
        label = "Spawn All batch"
    if total <= 0 and queued <= 0 and pending <= 0:
        if _BULK_SPAWN_SUMMARY_PENDING:
            return f"{label}: finishing — settling loot…"
        return f"{label}: idle"
    now = time.monotonic()
    verifying = len(_SPAWN_VERIFY_QUEUE)
    if _BULK_SPAWN_SUMMARY_PENDING and queued <= 0 and pending <= 0:
        done = max(0, total)
        if verifying:
            return (
                f"Spawn All batch: finishing {done}/{total} "
                f"(verifying {verifying}, {_BULK_SPAWN_OK} ok / {_BULK_SPAWN_FAIL} fail)"
            )
        if _BULK_SPAWN_SUMMARY_DEFER_UNTIL and now < float(_BULK_SPAWN_SUMMARY_DEFER_UNTIL):
            return (
                f"Spawn All batch: finishing {done}/{total} "
                f"— settling loot ({_BULK_SPAWN_OK} ok / {_BULK_SPAWN_FAIL} fail)"
            )
        return (
            f"Spawn All batch: finishing {done}/{total} "
            f"({_BULK_SPAWN_OK} ok / {_BULK_SPAWN_FAIL} fail)"
        )
    if _BULK_CLEANUP_DUE_AT:
        left = max(0.0, _BULK_CLEANUP_DUE_AT - now)
        return (
            f"{label}: cleanup in {left:.1f}s "
            f"({_BULK_SPAWN_OK} ok / {_BULK_SPAWN_FAIL} fail so far)"
        )
    if _BULK_SPAWN_SEGMENT_PAUSE_UNTIL and now < _BULK_SPAWN_SEGMENT_PAUSE_UNTIL:
        left = max(0.0, _BULK_SPAWN_SEGMENT_PAUSE_UNTIL - now)
        return (
            f"{label}: breather {left:.1f}s — pick up loot, then auto-continues "
            f"({_BULK_SPAWN_OK} ok / {_BULK_SPAWN_FAIL} fail so far)"
        )
    done = max(0, total - queued - pending)
    if singular_test:
        verify_bit = f", verifying {verifying}" if verifying else ""
        return (
            f"Singular test: {done}/{max(1, total)} "
            f"({_BULK_SPAWN_OK} ok / {_BULK_SPAWN_FAIL} fail{verify_bit})"
        )
    if single:
        return (
            f"Spawn selected: {done}/{max(1, total)} "
            f"({_BULK_SPAWN_OK} ok / {_BULK_SPAWN_FAIL} fail)"
        )
    wave = int(_BULK_SPAWN_WAVE_INDEX)
    return (
        f"Spawn All batch: {done}/{total} processed "
        f"(wave {wave}, {queued} active, {pending} queued, "
        f"{_BULK_SPAWN_OK} ok / {_BULK_SPAWN_FAIL} fail this batch)"
    )


def dump_spawn_log(*, log_to_console: bool = True, full: bool = False) -> str:
    """Refresh summary from spawn_test.jsonl.

    Console stays short by default — the all-time category wall lives in the
    summary file. Pass full=True (sqbt_spawn_dump) when you want the wall.
    """
    _rewrite_spawn_summary()
    text = ""
    try:
        if _SPAWN_LOG_SUMMARY.is_file():
            text = _SPAWN_LOG_SUMMARY.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = "(could not read summary)"
    if log_to_console:
        total = int(_BULK_SPAWN_WAVE_TOTAL or (_BULK_SPAWN_OK + _BULK_SPAWN_FAIL))
        if total > 1:
            _log_info(
                f"Spawn All finished: {_BULK_SPAWN_OK} ok, {_BULK_SPAWN_FAIL} fail "
                f"(details in spawn_test_summary.txt)"
            )
        elif total == 1:
            _log_info(
                f"Spawn selected finished: {_BULK_SPAWN_OK} ok, {_BULK_SPAWN_FAIL} fail"
            )
        if full:
            _log_info("Spawn log dump — share these files after Spawn All / pool tests:")
            _log_info(f"  {_SPAWN_LOG_JSONL}")
            _log_info(f"  {_SPAWN_LOG_SUMMARY}")
            _log_info(f"  {_SPAWN_FAILURES_LOG}")
            _log_info(f"  crash checkpoint: {_SPAWN_BATCH_CHECKPOINT}")
            _log_info(f"  ordered trace: {_SPAWN_BATCH_TRACE}")
            for line in text.splitlines()[:24]:
                _log_info(line)
            if len(text.splitlines()) > 24:
                _log_info("  … (see spawn_test_summary.txt for full summary)")
    return text


def log_spawn_failure(label: str, entry: dict[str, str] | None, detail: str) -> None:
    """Persist spawn failures for later debugging (visible + on-disk)."""
    record_spawn_result(
        entry,
        ok=False,
        method="failure",
        detail=detail,
        display_name=label,
    )


def _load_pool_health() -> dict[str, tuple[bool, str, str, bool]]:
    """Latest locally observed pool result; absent logs remain unclassified."""
    global _POOL_HEALTH_CACHE, _POOL_HEALTH_MTIME
    path = _SPAWN_LOG_JSONL
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if mtime == _POOL_HEALTH_MTIME:
        return _POOL_HEALTH_CACHE
    latest: dict[str, tuple[bool, str, str, bool]] = {}
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                detail = str(row.get("detail", "")).strip()
                method = str(row.get("method", "")).strip()
                reported = bool(row.get("reported_ok", row.get("ok", False)))
                observed = bool(row.get("delivery_observed", row.get("loot_observed", False)))
                val = (
                    bool(row.get("ok", False) and observed),
                    detail[:240],
                    method[:64],
                    reported,
                )
                pool = str(row.get("pool_name", "")).strip().lower()
                catalog = str(row.get("catalog_key", "")).strip().lower()
                if pool:
                    latest[pool] = val
                if catalog:
                    latest[f"catalog:{catalog}"] = val
    except OSError:
        return {}
    _POOL_HEALTH_CACHE = latest
    _POOL_HEALTH_MTIME = mtime
    return _POOL_HEALTH_CACHE


def _spawn_health_key(entry: dict[str, str]) -> str:
    catalog = str(entry.get("catalog_key") or "").strip().lower()
    if catalog:
        return f"catalog:{catalog}"
    return str(entry.get("itempool") or "").strip().lower()


def _spawn_pending_keys() -> set[str]:
    pending = set(_SPAWN_PENDING_KEYS)
    for job in _SPAWN_VERIFY_QUEUE:
        pending.add(_spawn_health_key(job.entry))
    return pending


def pool_health(entry: dict[str, str]) -> tuple[str, str]:
    """User-facing spawn hint from latest log + in-flight verify queue."""
    key = _spawn_health_key(entry)
    if key and key in _spawn_pending_keys():
        return "Pending", "Spawn queued — verifying loot…"

    pool = str(entry.get("itempool", "")).strip().lower()
    catalog = str(entry.get("catalog_key", "")).strip().lower()
    observed = _load_pool_health()
    keys = [f"catalog:{catalog}"] if catalog else []
    if pool:
        keys.append(pool)
    for lookup in keys:
        if not lookup:
            continue
        hit = observed.get(lookup)
        if hit is None:
            continue
        ok, detail, method, reported = hit
        if ok and method.lower() in _STALE_OK_METHODS:
            continue
        if ok:
            if method.lower() in {"pool_spawn", "ncs_live_pool", "ncs_verified_pool"}:
                return "OK", "Verified pool roll (random parts)."
            if method.lower().startswith("bl4_"):
                return "OK", f"BL4 spawn ({method})."
            return "OK", "Verified in last spawn test."
        if reported:
            return "Unverified", "Spawn call returned, but no nearby pickup was observed."
        return "Failed", detail
    return "", ""


def _curated_registered_pool_keys() -> set[str]:
    """Trusted pool names from item_pools.json only (not game_data gap-fill)."""
    global _CURATED_POOL_KEYS
    if _CURATED_POOL_KEYS is not None:
        return set(_CURATED_POOL_KEYS)
    keys: set[str] = set()
    try:
        blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], "item_pools.json")
        if blob:
            data = json.loads(blob.decode("utf-8"))
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict):
                        pool = str(entry.get("itempool", "")).strip().lower()
                        if pool:
                            keys.add(pool)
    except Exception:  # noqa: BLE001
        keys = set()
    _CURATED_POOL_KEYS = keys
    return set(keys)


def _nearby_loot_keys(near_loc: object, *, radius: float = _LOOT_VERIFY_RADIUS) -> set[str]:
    """Nearby inventory fingerprint — delegates to loot_verify (skips mid-ImGui)."""
    from .item_spawn.loot_verify import nearby_loot_keys

    return nearby_loot_keys(near_loc, radius=radius)


def _is_dedicated_classmod_catalog(catalog: str) -> bool:
    from .item_spawn.classmod_comp_spawn import is_dedicated_classmod_catalog

    return is_dedicated_classmod_catalog(catalog)


def _is_generic_subjugator_classmod(catalog: str) -> bool:
    """Alias — dedicated single-comp legendary classmods (not broad VH roll pools)."""
    return _is_dedicated_classmod_catalog(catalog)


def _is_classmod_pool(pool_name: str) -> bool:
    low = str(pool_name or "").strip().lower()
    return "class_mod" in low or "classmod" in low


def _is_classmod_entry(entry: dict[str, str], catalog: str = "") -> bool:
    cat = str(catalog or entry.get("catalog_key") or "").strip().lower()
    if cat.startswith("classmod_"):
        return True
    if str(entry.get("category", "")).strip().lower() == "class mod":
        return True
    return _is_classmod_pool(str(entry.get("itempool", "")))


def _resolve_catalog_serial(catalog: str, entry: dict[str, str] | None = None) -> str | None:
    """Best @U serial for a named catalog row (raid JSON, pearl index, Item Spawner bridge)."""
    cat = str(catalog or "").strip().lower()
    if entry:
        direct = str(entry.get("serial", "")).strip()
        if direct.startswith("@U"):
            return direct
    try:
        from .standalone_spawning import row_for_catalog

        row = row_for_catalog(cat)
        if row.serial and str(row.serial).startswith("@U"):
            return str(row.serial)
    except Exception:  # noqa: BLE001
        pass
    try:
        from .item_spawn.pearl_serial_spawn import serial_for_catalog

        hit = serial_for_catalog(cat)
        if hit and str(hit).startswith("@U"):
            return str(hit)
    except Exception:  # noqa: BLE001
        pass
    return None


def _capture_loot_snapshot(*, force_scan: bool = False) -> tuple[object | None, set[str] | None]:
    """Player feet pose + nearby loot keys; bulk defers its one scan until verification."""
    try:
        from .item_spawn.spawn_pc import resolve_spawn_pc

        pc = resolve_spawn_pc()
    except Exception:
        pc = _get_runtime_pc()
    if pc is None:
        return None, None
    pose = _get_player_pose(pc)
    if pose is None:
        return None, None
    # Spawn All skips the per-row scan for speed; a single queued row must scan for
    # real, otherwise an empty before-set makes pre-existing ground loot read as new.
    if (
        not force_scan
        and (_BULK_SPAWN_DRAINING or bulk_spawn_active())
        and not _spawn_queue_is_single()
    ):
        return pose[0], set()
    from .item_spawn.loot_verify import feet_weapon_loot_keys, verify_available

    if not verify_available():
        return pose[0], None
    return pose[0], feet_weapon_loot_keys(pose[0])


def _loot_gained_since(before_loc: object | None, before_keys: set[str] | None) -> bool:
    """True when a new unclaimed weapon/pickup appears near feet — PlayerTick only."""
    if before_loc is None or before_keys is None:
        return False
    from .item_spawn.loot_verify import unclaimed_loot_gain, verify_available

    if not verify_available():
        return False
    return bool(unclaimed_loot_gain(before_loc, before_keys))


def _claim_loot_since(before_loc: object | None, before_keys: set[str] | None) -> None:
    if before_loc is None or before_keys is None:
        return
    from .item_spawn.loot_verify import claim_loot_keys, unclaimed_loot_gain

    claim_loot_keys(unclaimed_loot_gain(before_loc, before_keys))


@dataclass
class _SpawnVerifyJob:
    entry: dict[str, str]
    level: int
    count: int
    before_loc: object | None
    before_keys: set[str]
    spawned: int
    method: str
    detail: str
    display: str
    attempts: int = 0
    max_attempts: int = 40
    from_bulk: bool = False
    needs_snapshot: bool = False
    ncs_pool: str = ""
    next_ncs_store: int = 1
    tried_ncs_stores: set[int] = field(default_factory=set)
    exact_ncs_probe: bool = False
    inline_fallback_attempted: bool = False
    dump_fallback_attempted: bool = False
    serial_fallback_attempted: bool = False
    resolved_catalog: str = ""
    next_check_at: float = 0.0
    no_retry: bool = False
    respawn_attempted: bool = False


def _resolve_catalog_spawn_pool(
    catalog: str, pool: str, *, wants_shiny: bool | None = None
) -> str:
    """Map fake/synthetic dump pools to live NCS ids from FModel audit."""
    cat = str(catalog or "").strip().lower()
    pool_s = str(pool or "").strip()
    pool_l = pool_s.lower()
    native = str(_DUMP_CATALOG_NATIVE_POOLS.get(cat) or "").strip()
    if not native:
        return pool_s
    pool_is_shiny = pool_l.endswith("_shiny") or "_shiny_" in pool_l
    # Roil/Rainmaker: only mal_sg *_shiny exists. Always force that twin.
    if cat in _FORCE_SHINY_NATIVE_CATALOGS:
        if (
            not pool_l
            or pool_l in _FAKE_BASE_ITEMPOOLS
            or pool_l == native.lower().removesuffix("_shiny")
            or not pool_is_shiny
        ):
            return native
        return pool_s
    # Midnight etc: only rewrite to *_shiny when the row wants shiny.
    shiny_intent = (
        bool(wants_shiny)
        if wants_shiny is not None
        else pool_is_shiny
    )
    if shiny_intent and (
        not pool_l
        or pool_l in _FAKE_BASE_ITEMPOOLS
        or not pool_is_shiny
    ):
        return native
    return pool_s


def _next_ncs_store_from_method(method: str) -> int:
    match = re.search(r"_s(\d+)$", str(method or ""))
    return int(match.group(1)) + 1 if match else 1


def _enqueue_spawn_verify(
    *,
    entry: dict[str, str],
    level: int,
    count: int,
    before_loc: object | None,
    before_keys: set[str] | None,
    spawned: int,
    method: str,
    detail: str,
    display: str,
    from_bulk: bool,
) -> None:
    global _BULK_SPAWN_SUMMARY_PENDING

    _ensure_bulk_spawn_hook()
    health_key = _spawn_health_key(entry)
    if health_key:
        _SPAWN_PENDING_KEYS.add(health_key)
    catalog = str(entry.get("catalog_key") or "").strip().lower()
    exact_ncs_probe = str(entry.get("pearl_supplement") or "").strip() == "1"
    pearl_job = str(entry.get("category") or "").strip().lower() == "pearl"
    if catalog:
        try:
            from .item_spawn.pearlescent_manifest import is_pearlescent_catalog

            pearl_job = pearl_job or is_pearlescent_catalog(catalog)
        except Exception:  # noqa: BLE001
            pass
    _SPAWN_VERIFY_QUEUE.append(
        _SpawnVerifyJob(
            entry=dict(entry),
            level=level,
            count=count,
            before_loc=before_loc,
            before_keys=set(before_keys) if before_keys is not None else set(),
            spawned=spawned,
            method=str(method or "pool_spawn")[:64],
            detail=str(detail or "")[:500],
            display=str(display or "pool"),
            from_bulk=bool(from_bulk),
            needs_snapshot=before_loc is None or before_keys is None,
            # Each attempt runs on a later game tick, so this still gives the
            # pickup time to appear without adding visible wall-clock pauses.
            max_attempts=(
                12
                if exact_ncs_probe
                else (16 if pearl_job else (10 if from_bulk and not _spawn_queue_is_single() else 14))
            ),
            # A pickup needs a few frames to exist in the world; checking on the
            # same tick as the RPC always reads "empty" and triggers a needless
            # re-roll, which is what produced doubles and bogus silent_empty.
            next_check_at=time.monotonic()
            + (0.05 if (from_bulk and not _spawn_queue_is_single()) else 0.45),
            ncs_pool=(
                str(entry.get("itempool") or "").strip()
                or (
                    str(detail or "").strip()
                    if str(method or "").startswith(
                        ("ncs_pending_", "ncs_generic_pending_", "ncs_pool", "ncs_legacy", "pearl_serial")
                    )
                    else ""
                )
            ),
            resolved_catalog=str(entry.get("catalog_key") or "").strip().lower(),
            next_ncs_store=_next_ncs_store_from_method(method),
            tried_ncs_stores={
                int(match.group(1))
                for match in [re.search(r"_s(\d+)$", str(method or ""))]
                if match is not None
            },
            exact_ncs_probe=exact_ncs_probe,
            no_retry=False,
        )
    )
    if from_bulk:
        _BULK_SPAWN_SUMMARY_PENDING = True


def _clear_spawn_pending(entry: dict[str, str]) -> None:
    key = _spawn_health_key(entry)
    if key:
        _SPAWN_PENDING_KEYS.discard(key)


def _pearl_verify_fallback_mail(job: _SpawnVerifyJob) -> bool:
    """Pearl ground spawn — no mail auto-fallback (user wants live rolls at feet)."""
    return False


def _retry_next_ncs_store(job: _SpawnVerifyJob) -> bool:
    """Probe the next config layer only after the prior layer stayed empty."""
    if not job.ncs_pool:
        return False
    from .item_spawn.ncs_pool_spawn import nexus_store_count, spawn_itempool_on_store

    total = nexus_store_count()
    # Live config layers hold named/direct pools; the CDO (index 0) commonly
    # accepts the RPC but only resolves broad mixed pools. Probe live layers
    # before the CDO so a silent CDO return cannot mask the actual pool.
    store_order = [*range(1, total), 0] if total > 1 else [0]
    store_index = next(
        (index for index in store_order if index not in job.tried_ncs_stores),
        None,
    )
    if store_index is None:
        return False

    snap_loc, snap_keys = _capture_loot_snapshot(force_scan=job.exact_ncs_probe)
    if snap_loc is None:
        return False

    job.tried_ncs_stores.add(store_index)
    job.next_ncs_store = store_index + 1
    spawned, err = spawn_itempool_on_store(
        job.ncs_pool,
        store_index=store_index,
        count=job.count,
        level=job.level,
    )
    job.before_loc = snap_loc
    job.before_keys = set(snap_keys)
    job.attempts = 0
    job.detail = (
        f"{job.ncs_pool} (NCS store {store_index + 1}/{total})"
        if spawned > 0
        else f"{job.ncs_pool} store {store_index + 1}/{total}: {err or 'rejected'}"
    )
    return True


def _apply_pearl_customization_for_catalog(catalog_key: str) -> None:
    """Force phosphene / shiny cosmetic on a nearby pearl drop after base-pool spawn."""
    catalog = str(catalog_key or "").strip().lower()
    if not catalog:
        return
    try:
        from .item_spawn.pearlescent_manifest import PEARL_SHINY_POOLS
        from .item_spawn.shiny_pool_lookup import lookup_shiny_pool
        from .item_spawn.spawn_pc import resolve_spawn_pc
        from bl4_item_spawner.shiny_pool_spawn import apply_phosphene_nearby

        shiny = PEARL_SHINY_POOLS.get(catalog)
        row = lookup_shiny_pool(shiny or "") if shiny else None
        if not row:
            return
        customization = str(row.get("customization") or "").strip()
        inv_handle = str(row.get("inv_handle") or "").strip()
        pc = resolve_spawn_pc()
        if pc is not None and customization:
            apply_phosphene_nearby(pc, customization, inv_handle)
    except Exception:  # noqa: BLE001
        pass


def _apply_verified_pearl_customization(job: _SpawnVerifyJob) -> None:
    """Force the dump's phosphene customization after an ungated base-pool drop."""
    catalog = job.resolved_catalog or str(job.entry.get("catalog_key") or "").strip().lower()
    if catalog:
        _apply_pearl_customization_for_catalog(catalog)


def _retry_pearl_serial(job: _SpawnVerifyJob) -> bool:
    """Ground @U retry when passive loot scan missed a dump-first spawn."""
    if job.serial_fallback_attempted:
        return False
    job.serial_fallback_attempted = True
    display = str(job.display or "item")
    hit = _try_curated_dump_serial(job.entry, count=job.count, display=display)
    if hit is None:
        catalog = job.resolved_catalog or str(job.entry.get("catalog_key") or "").strip().lower()
        if catalog:
            try:
                serial_hit = _try_catalog_serial_grant(
                    catalog, job.entry, count=job.count, display=display
                )
                if serial_hit is not None:
                    hit = int(serial_hit)
            except Exception:  # noqa: BLE001
                hit = None
    if hit is None or hit <= 0:
        return False
    snap_loc, snap_keys = _capture_loot_snapshot(force_scan=job.exact_ncs_probe)
    if snap_loc is not None:
        job.before_loc = snap_loc
        job.before_keys = set(snap_keys or ())
    job.attempts = 0
    job.method = "dump_serial_retry"
    job.detail = "curated @U ground retry"
    return True


def _retry_pearl_dump_fallback(job: _SpawnVerifyJob) -> bool:
    """Dump inv / proven retry for pearl-tier and named dump rows."""
    if job.dump_fallback_attempted:
        return False
    job.dump_fallback_attempted = True
    catalog = job.resolved_catalog or str(job.entry.get("catalog_key") or "").strip().lower()
    display = str(job.display or catalog or "pearl")
    if not catalog:
        return False
    before_loc, before_keys = _capture_loot_snapshot(force_scan=job.exact_ncs_probe)
    try:
        proven = _spawn_proven_catalog_ground(
            catalog,
            count=job.count,
            level=job.level,
            display=display,
            pool=str(job.entry.get("itempool") or ""),
            prefer_serial=True,
            wants_shiny=_wants_shiny_spawn(
                pool=str(job.entry.get("itempool") or ""),
                display=display,
                entry=job.entry,
            ),
            allow_native=False,
            raise_on_miss=False,
        )
        if proven > 0:
            job.before_loc = before_loc
            job.before_keys = set(before_keys or ())
            job.attempts = 0
            job.method = "dump_proven_retry"
            job.detail = catalog
            return True
    except RuntimeError:
        pass
    handles = _named_pearl_dump_handles(catalog) or _catalog_inv_handles(catalog)
    if not handles:
        handles = _lean_inv_handles_for_named(job.entry, catalog)
    if handles:
        try:
            from .item_spawn.item_pool_list_spawn import spawn_itempoollist_inv_at_feet

            wants_shiny = _wants_shiny_spawn(
                pool=str(job.entry.get("itempool") or ""),
                display=display,
                entry=job.entry,
            )
            ipl_hit, _ipl_err = spawn_itempoollist_inv_at_feet(
                handles[:6],
                count=job.count,
                level=job.level,
                require_loot_verify=False,
                wants_shiny=wants_shiny,
            )
            if ipl_hit > 0:
                job.before_loc = before_loc
                job.before_keys = set(before_keys or ())
                job.attempts = 0
                job.method = "dump_itempoollist_retry"
                job.detail = handles[0]
                return True
        except Exception:  # noqa: BLE001
            pass
        from .item_spawn.comp_loot_drop import (
            spawn_inv_handles_at_feet,
            spawn_named_comp_inline_at_feet,
        )

        wants_shiny = _wants_shiny_spawn(
            pool=str(job.entry.get("itempool") or ""),
            display=display,
            entry=job.entry,
        )
        spawn_fn = (
            spawn_inv_handles_at_feet if wants_shiny else spawn_named_comp_inline_at_feet
        )
        spawned, _err = spawn_fn(
            handles[:6],
            count=job.count,
            level=job.level,
            skip_verify=True,
        )
        if spawned > 0:
            job.before_loc = before_loc
            job.before_keys = set(before_keys or ())
            job.attempts = 0
            job.method = "dump_inv_retry"
            job.detail = handles[0]
            return True
    _log_warning(f"{display}: dump inv retry missed.")
    return False


def _retry_pearl_inline(job: _SpawnVerifyJob) -> bool:
    """Merge inline retry for pearl-tier rows."""
    if job.inline_fallback_attempted:
        return False
    job.inline_fallback_attempted = True
    catalog = job.resolved_catalog or str(job.entry.get("catalog_key") or "").strip().lower()
    pool = str(job.entry.get("itempool") or "").strip()
    display = str(job.display or catalog or "pearl")
    if not catalog:
        return False
    before_loc, before_keys = _capture_loot_snapshot(force_scan=job.exact_ncs_probe)
    try:
        from .item_spawn.pearl_comp_spawn import try_spawn_pearl_comp_world

        merge = try_spawn_pearl_comp_world(
            catalog,
            count=job.count,
            level=job.level,
            pool_name=pool or None,
            drop_only=True,
        )
        if merge.ok:
            job.before_loc = before_loc
            job.before_keys = set(before_keys or ())
            job.attempts = 0
            job.method = str(merge.method or "pearl_merge_retry")
            job.detail = str(merge.detail or catalog)[:240]
            return True
    except Exception:  # noqa: BLE001
        pass
    _log_warning(f"{display}: merge inline retry missed.")
    return False


def _retry_native_pool_respawn(job: _SpawnVerifyJob) -> bool:
    """Re-roll the same NCS pool once when loot landed after the first RPC tick."""
    if job.respawn_attempted:
        return False
    pool = str(
        job.ncs_pool or job.entry.get("itempool") or job.detail or ""
    ).strip()
    if not pool.lower().startswith("itempool_"):
        return False
    job.respawn_attempted = True
    from .item_spawn.ncs_pool_spawn import spawn_itempool_names, spawn_legacy_itempool

    snap_loc, snap_keys = _capture_loot_snapshot()
    spawned, _err = spawn_itempool_names(
        [pool],
        count=max(1, int(job.count)),
        level=job.level,
        require_loot_verify=False,
    )
    if spawned <= 0:
        spawned, _err = spawn_legacy_itempool(
            [pool],
            count=max(1, int(job.count)),
            level=job.level,
        )
    if spawned <= 0:
        return False
    if snap_loc is not None:
        job.before_loc = snap_loc
        job.before_keys = set(snap_keys or ())
    job.attempts = 0
    job.method = "pool_respawn_retry"
    job.detail = pool[:240]
    job.next_check_at = time.monotonic() + 0.35
    return True


def _pump_spawn_verify_queue(*, max_jobs: int = 2) -> int:
    """Check deferred loot snapshots on later PlayerTicks (not during ImGui)."""
    global _BULK_SPAWN_OK, _BULK_SPAWN_FAIL

    if not _SPAWN_VERIFY_QUEUE:
        return 0
    if time.monotonic() < _SPAWN_VERIFY_QUEUE[0].next_check_at:
        return 0
    from .item_spawn.loot_verify import verify_available

    if not verify_available():
        job = _SPAWN_VERIFY_QUEUE[0]
        job.attempts += 1
        if job.from_bulk:
            job.next_check_at = time.monotonic() + 0.08
        if job.attempts >= job.max_attempts:
            record_spawn_result(
                job.entry,
                ok=False,
                method="verify_unavailable",
                detail=f"{job.display}: loot verifier unavailable for too long.",
                count=job.count,
                level=job.level,
            )
            _clear_spawn_pending(job.entry)
            if job.from_bulk:
                _BULK_SPAWN_FAIL += 1
            _SPAWN_VERIFY_QUEUE.popleft()
        return 0

    processed = 0
    limit = max(1, int(max_jobs))
    while _SPAWN_VERIFY_QUEUE and processed < limit:
        job = _SPAWN_VERIFY_QUEUE[0]
        if job.needs_snapshot or job.before_loc is None:
            snap_loc, snap_keys = _capture_loot_snapshot()
            if snap_loc is not None:
                job.before_loc = snap_loc
                job.before_keys = set(snap_keys or ())
                job.needs_snapshot = False
            else:
                job.attempts += 1
                if job.from_bulk:
                    job.next_check_at = time.monotonic() + 0.08
                if job.attempts >= job.max_attempts:
                    if _pearl_verify_fallback_mail(job):
                        _SPAWN_VERIFY_QUEUE.popleft()
                        processed += 1
                        continue
                    record_spawn_result(
                        job.entry,
                        ok=False,
                        method="verify_unavailable",
                        detail=f"{job.display}: could not verify loot (no player snapshot).",
                        count=job.count,
                        level=job.level,
                    )
                    _clear_spawn_pending(job.entry)
                    if job.from_bulk:
                        _BULK_SPAWN_FAIL += 1
                    _SPAWN_VERIFY_QUEUE.popleft()
                    processed += 1
                break

        if _loot_gained_since(job.before_loc, job.before_keys):
            _apply_verified_pearl_customization(job)
            _claim_loot_since(job.before_loc, job.before_keys)
            record_spawn_result(
                job.entry,
                ok=True,
                method=job.method,
                detail=job.detail,
                count=job.count,
                level=job.level,
                observed=True,
            )
            _clear_spawn_pending(job.entry)
            if job.from_bulk:
                _BULK_SPAWN_OK += 1
            _SPAWN_VERIFY_QUEUE.popleft()
            processed += 1
            continue

        job.attempts += 1
        if job.from_bulk:
            # Selected needs a beat for live NCS to land before dump escalate.
            if _spawn_queue_is_selected():
                gap = 0.20
            elif _spawn_queue_is_single():
                gap = 0.15
            else:
                gap = 0.05
            job.next_check_at = time.monotonic() + gap
        catalog = job.resolved_catalog or str(job.entry.get("catalog_key") or "").strip().lower()
        needs_dump_escalation = bool(
            catalog
            and (
                catalog in _PATCH_INLINE_INVENTORY_DEFS
                or catalog in _NCS_DUMP_ONLY_INVS
                or str(job.entry.get("dump_named_legendary") or "").strip() == "1"
                or "_comp_05_legendary_" in catalog
                or "_comp_06_pearl_" in catalog
                or _pool_needs_dump_first(
                    str(job.entry.get("itempool") or ""),
                    catalog,
                )
            )
        )
        if job.exact_ncs_probe and job.attempts >= 2:
            # itempool8/DLC pools can live on a different loaded config layer.
            # Probe each distinct layer first, allowing two short observation
            # ticks per layer, then retain the ground-only inline/serial routes.
            if _retry_next_ncs_store(job):
                break
            if job.ncs_pool and _retry_pearl_inline(job):
                break
            if _retry_pearl_serial(job):
                break
            job.attempts = job.max_attempts
        elif (
            needs_dump_escalation
            and not job.no_retry
            and job.attempts >= (1 if _spawn_queue_is_selected() else 1)
        ):
            # Selected waits about a second for its asynchronous live pickup.
            # First-check escalation caused live + dump duplicate copies.
            if _retry_pearl_dump_fallback(job):
                break
            if _retry_pearl_serial(job):
                break
            if job.ncs_pool and _retry_pearl_inline(job):
                break
        elif (
            not _spawn_queue_is_selected()
            and not job.no_retry
            and job.attempts >= 4
            and _retry_native_pool_respawn(job)
        ):
            break
        elif not job.no_retry and job.attempts >= 6 and _retry_pearl_serial(job):
            break
        elif not job.no_retry and job.attempts >= 8 and _retry_pearl_dump_fallback(job):
            break
        elif not job.no_retry and job.attempts >= 10 and _retry_next_ncs_store(job):
            break
        elif not job.no_retry and job.attempts >= 12 and job.ncs_pool and _retry_pearl_inline(job):
            break
        if job.attempts >= job.max_attempts:
            if _spawn_queue_is_selected() and needs_dump_escalation:
                rescued, rescue_method, rescue_detail = _rescue_selected_silent_empty(
                    job.entry,
                    level=job.level,
                    count=job.count,
                )
                if rescued > 0:
                    _apply_verified_pearl_customization(job)
                    record_spawn_result(
                        job.entry,
                        ok=True,
                        method=rescue_method,
                        detail=rescue_detail,
                        count=job.count,
                        level=job.level,
                        observed=True,
                    )
                    _clear_spawn_pending(job.entry)
                    if job.from_bulk:
                        _BULK_SPAWN_OK += 1
                    _SPAWN_VERIFY_QUEUE.popleft()
                    processed += 1
                    continue
            if _pearl_verify_fallback_mail(job):
                _SPAWN_VERIFY_QUEUE.popleft()
                processed += 1
                continue
            fail_detail = (
                f"{job.display}: spawn returned via {job.method}, but the passive loot scan "
                "did not identify a new pickup; no retry was issued."
                if job.no_retry
                else f"{job.display}: spawn via {job.method} but no loot at feet "
                f"(silent empty). Stand on open ground and retry. "
                "Or try Spawn All Filtered / the type pool "
                "(AR / SG / SM / PS / SR 05 Legendary)."
            )
            record_spawn_result(
                job.entry,
                ok=False,
                method="silent_empty",
                detail=fail_detail,
                count=job.count,
                level=job.level,
            )
            _clear_spawn_pending(job.entry)
            if job.from_bulk:
                _BULK_SPAWN_FAIL += 1
            _SPAWN_VERIFY_QUEUE.popleft()
            processed += 1
        else:
            break
    return processed


def _bulk_spawn_blocked_by_verify() -> bool:
    """Wait for pending verify before the next drop (singular/Selected = every row)."""
    if not _SPAWN_VERIFY_QUEUE:
        return False
    if _SINGULAR_PATH_TEST or _spawn_queue_is_single() or _spawn_queue_is_selected():
        return True
    try:
        job = _SPAWN_VERIFY_QUEUE[0]
        return bool(job.exact_ncs_probe) or str(job.entry.get("category") or "").strip().lower() == "pearl"
    except Exception:
        return False


def _maybe_write_bulk_spawn_summary() -> None:
    global _BULK_SPAWN_SUMMARY_PENDING, _BULK_SPAWN_SUMMARY_DEFER_UNTIL, _BULK_FINISH_SETTLED
    global _SINGULAR_PATH_TEST

    if bulk_spawn_active() or _SPAWN_VERIFY_QUEUE:
        return
    if not _BULK_SPAWN_SUMMARY_PENDING:
        return
    # Spread finish hitch: settle this tick, rewrite 45k jsonl on a later tick.
    if _BULK_SPAWN_SUMMARY_DEFER_UNTIL and time.monotonic() < float(_BULK_SPAWN_SUMMARY_DEFER_UNTIL):
        return
    was_singular_test = bool(_SINGULAR_PATH_TEST)
    _SINGULAR_PATH_TEST = False
    _BULK_SPAWN_SUMMARY_PENDING = False
    _BULK_SPAWN_SUMMARY_DEFER_UNTIL = 0.0
    _BULK_FINISH_SETTLED = False
    _clear_bulk_spawn_perf_state()
    _rewrite_spawn_summary()
    _invalidate_pool_health_cache()
    try:
        from .item_spawn.pearl_spawn_ring import set_bulk_pile_mode

        set_bulk_pile_mode(False)
    except Exception:  # noqa: BLE001
        pass
    if was_singular_test:
        try:
            from .item_spawn.loot_verify import set_feet_verify_radius

            set_feet_verify_radius(None)
        except Exception:  # noqa: BLE001
            pass
    from datetime import datetime, timezone

    total = int(_BULK_SPAWN_WAVE_TOTAL or (_BULK_SPAWN_OK + _BULK_SPAWN_FAIL))
    if was_singular_test:
        done_label = "singular test done"
    elif total > 1:
        done_label = "spawn all done"
    else:
        done_label = "spawn selected done"
    summary = (
        f"{datetime.now(timezone.utc).isoformat()} | "
        f"{done_label}: {_BULK_SPAWN_OK} ok, {_BULK_SPAWN_FAIL} fail\n"
        f"jsonl: {_SPAWN_LOG_JSONL}\n"
        f"summary: {_SPAWN_LOG_SUMMARY}\n"
    )
    try:
        _SPAWN_LOG_DIR.mkdir(parents=True, exist_ok=True)
        _SPAWN_BATCH_LAST.write_text(summary, encoding="utf-8")
    except OSError:
        pass
    dump_spawn_log(log_to_console=True, full=False)


def _deliver_catalog_serial_ground_only(serial: str, count: int, display: str) -> int:
    """Ground @U only — fails if delivery RPC fails."""
    serial = str(serial or "").strip()
    count = max(1, min(int(count), 32))
    if not serial.startswith("@U"):
        raise RuntimeError(f"{display}: invalid @U serial")
    from .item_spawn.pearl_serial_spawn import try_deliver_serial_comprehensive

    ok, via = try_deliver_serial_comprehensive(serial, count, prefer_ground=True, ground_only=True)
    if ok:
        _log_info(f"Spawned {display} at feet via @U serial ({via}).")
        return count
    raise RuntimeError(f"{display}: ground @U serial failed ({via})")


def _try_catalog_serial_grant(
    catalog: str,
    entry: dict[str, str] | None,
    *,
    count: int,
    display: str,
) -> int | None:
    try:
        from .item_spawn.squ1ggs_spawn_bridge import deliver_catalog_serial_ground_only

        ok, method = deliver_catalog_serial_ground_only(catalog, count=count)
        if ok:
            _log_info(f"Spawned {display} at feet via {method}.")
            return count
    except Exception:  # noqa: BLE001
        pass
    serial = _resolve_catalog_serial(catalog, entry)
    serials: list[str] = []
    try:
        from .item_spawn.pearl_serial_spawn import serials_for_catalog

        serials = list(serials_for_catalog(catalog))
    except Exception:  # noqa: BLE001
        pass
    if serial and serial not in serials:
        serials.insert(0, serial)
    elif serial and not serials:
        serials = [serial]
    last_exc: Exception | None = None
    for candidate in serials:
        try:
            return _deliver_catalog_serial_ground_only(candidate, count, display)
        except RuntimeError as exc:
            last_exc = exc
            continue
    try:
        from .item_spawn.pearl_serial_spawn import try_deliver_serial

        for candidate in serials:
            if try_deliver_serial(candidate, count):
                _log_info(f"Spawned {display} via backpack @U serial.")
                return count
    except Exception:  # noqa: BLE001
        pass
    if last_exc is not None:
        _log_warning(f"{display}: @U serial paths failed ({last_exc}); trying native pools.")
    return None


def _is_comp05_legendary_pearl_pool(pool_name: str) -> bool:
    """comp_05 legendary pearl rows (Handcannon, Conflux, …) — NCS, not comp_06 merge pipeline."""
    from .item_spawn.comp_tier import is_comp05_legendary_pearl_pool

    return is_comp05_legendary_pearl_pool(pool_name)


def _is_comp06_pearl_pool(pool_name: str) -> bool:
    """True pearlescent pools (comp_06_pearl_*), not comp_05 legendary pearl tier."""
    from .item_spawn.comp_tier import is_comp06_pearl_pool

    return is_comp06_pearl_pool(pool_name)


def _ar_pearl_pool_hint() -> str:
    return (
        "No comp_06 pearl assault rifles exist in game data. "
        "Use > Ord AR 05 Legendary Crow-Sourced Pearl (pearl-tier legendary) "
        "or > Gomie (jak_ar comp_05 legendary, not pearl)."
    )


def _try_catalog_native_pool_spawn(
    pool_try: list[str],
    *,
    level: int,
    count: int,
    display: str,
    before_loc: Any,
    before_keys: set[str],
    require_loot: bool = False,
) -> int | None:
    """Live NCS itempools — Squ1ggs pool spawn first, then verified/native fallbacks."""
    if not pool_try:
        return None

    def _accept(spawned: int) -> int | None:
        if spawned <= 0:
            return None
        if require_loot:
            from .item_spawn.loot_verify import verify_available

            if not verify_available():
                return None
            if not _loot_gained_since(before_loc, before_keys):
                return None
        return count

    from .item_spawn.ncs_pool_spawn import spawn_itempool_names, spawn_legacy_itempool
    from .standalone_spawning import spawn_native_pool

    registered = _registered_pool_keys()
    seen: set[str] = set()
    for name in pool_try:
        low = str(name or "").strip().lower()
        if not low or low in seen:
            continue
        seen.add(low)
        try:
            spawned, _ = spawn_legacy_itempool([name], count=count, level=level)
            hit = _accept(spawned)
            if hit is not None:
                _log_info(f"Spawned {display} via NCS pool {name}.")
                return hit
        except Exception:  # noqa: BLE001
            pass
        if low in registered:
            try:
                hit = spawn_item_pool(name, level, count)
                accepted = _accept(int(hit or 0))
                if accepted is not None:
                    _log_info(f"Spawned {display} via registered NCS pool {name}.")
                    return accepted
            except Exception:  # noqa: BLE001
                pass
        try:
            hit = spawn_native_pool(name, count=count, level=level)
            if getattr(hit, "ok", False) and (
                not require_loot
                or _loot_gained_since(before_loc, before_keys)
                or _spawn_method_trustworthy(str(getattr(hit, "method", "")))
            ):
                _log_info(f"Spawned {display} via native pool {name} (part rolls).")
                return count
        except Exception:  # noqa: BLE001
            pass
        try:
            spawned, _ = spawn_itempool_names([name], count=count, level=level)
            hit = _accept(spawned)
            if hit is not None:
                _log_info(f"Spawned {display} via verified NCS pool {name}.")
                return hit
        except Exception:  # noqa: BLE001
            pass
    return None


def _dump_inv_catalog_spawn(
    row: dict[str, str],
    catalog: str,
    *,
    count: int,
    level: int,
    skip_verify: bool,
) -> int:
    from .item_spawn.comp_loot_drop import spawn_named_comp_inline_at_feet

    # Original Item Spawner: inline ItemPoolDef / SpawnLootFromData, not exact-inv
    # only (that skipped the library path named legendaries actually use).
    uniq = _lean_inv_handles_for_named(row, catalog)
    patch = str(_PATCH_INLINE_INVENTORY_DEFS.get(catalog) or "").strip()
    if patch and patch.lower() not in {h.lower() for h in uniq}:
        uniq = [patch, *uniq]
    uniq = uniq[:8]
    if not uniq:
        return 0
    spawned, err = spawn_named_comp_inline_at_feet(
        uniq,
        count=count,
        level=level,
        skip_verify=bool(skip_verify),
    )
    if spawned <= 0:
        if err:
            _log_warning(f"dump inline missed ({err}).")
        return 0
    if spawned > 0:
        _set_pearl_spawn_delivery(
            "dump_inv_def",
            uniq[0],
            skip_verify=bool(skip_verify),
            loot_verified=not skip_verify,
        )
        return spawned
    return 0


def _spawn_ncs_first_named(
    entry: dict[str, str],
    *,
    level: int,
    count: int,
    display: str,
    wants_shiny: bool = False,
) -> int:
    """Named catalog rows — dump base inv for uniques; live NCS for shiny/pearl/mixed."""
    row = dict(entry)
    pool = str(row.get("itempool") or "").strip()
    catalog = str(row.get("catalog_key") or "").strip().lower()
    skip_verify = _skip_loot_verify()
    named_unique = _is_named_unique_legendary_row(row, wants_shiny=wants_shiny)

    # Base named L5 (weapon tab): dump inv comp — not live pool / *_shiny.
    if (
        named_unique
        and catalog
        and "_comp_05_legendary_" in catalog
        and not wants_shiny
    ):
        dump_hit = _spawn_named_l5_dump_inv(
            row,
            catalog=catalog,
            pool=pool,
            display=display,
            count=count,
            level=level,
            skip_pool=not _spawn_named_l5_bulk_mode(),
        )
        if dump_hit:
            return dump_hit
        if _spawn_named_l5_bulk_mode():
            raise RuntimeError(
                f"{display}: named pool + NCS twin missed (catalog={catalog})."
            )
        return _named_unique_base_after_dump_miss(
            row,
            catalog=catalog,
            display=display,
            count=count,
            level=level,
        )

    # Live NCS for shiny rows, pearls, mixed pools (Spawn All + Selected).
    if (
        _BULK_SPAWN_DRAINING
        and pool
        and not (named_unique and not wants_shiny)
        and "_comp_05_" not in pool.lower()
        and "_comp_06_" not in pool.lower()
    ):
        if wants_shiny and not _is_wrong_family_shiny_pool(pool):
            try:
                from .item_spawn.shiny_pearl_spawn import (
                    _apply_shiny_customization_for_pool,
                    prepare_shiny_pool_context,
                )

                prepare_shiny_pool_context(pool)
            except Exception:  # noqa: BLE001
                pass
        bulk_hit = _try_bulk_native_pool_spawn(
            pool,
            level=level,
            count=count,
            catalog=catalog,
            wants_shiny=wants_shiny,
        )
        if bulk_hit:
            if wants_shiny and not bulk_spawn_is_mass():
                try:
                    from .item_spawn.shiny_pearl_spawn import _apply_shiny_customization_for_pool

                    _apply_shiny_customization_for_pool(pool)
                except Exception:  # noqa: BLE001
                    pass
            return bulk_hit

    if wants_shiny and pool and not _BULK_SPAWN_DRAINING:
        dumped = _try_shiny_dump_world(
            pool,
            count=count,
            level=level,
            display=display,
            catalog=catalog,
        )
        if dumped:
            return dumped
        if _is_wrong_family_shiny_pool(pool):
            if catalog:
                return _spawn_proven_catalog_ground(
                    catalog,
                    count=count,
                    level=level,
                    display=display,
                    pool=pool,
                    prefer_serial=True,
                    wants_shiny=True,
                )
            raise RuntimeError(
                f"{display}: wrong-family shiny pool blocked — no catalog dump available."
            )

    dump_first = bool(
        str(row.get("dump_named_legendary") or "").strip() == "1"
        or catalog in _PATCH_INLINE_INVENTORY_DEFS
        or bool(_patch_inline_catalog_from_pool(pool))
        or _pool_needs_dump_first(pool, catalog)
    )
    if (
        dump_first
        and bulk_spawn_is_mass()
        and catalog
        and "_comp_05_legendary_" in catalog
        and not wants_shiny
    ):
        dump_first = False
    if dump_first and catalog and not wants_shiny:
        dump_hit = _dump_inv_catalog_spawn(
            row, catalog, count=count, level=level, skip_verify=skip_verify
        )
        if dump_hit:
            _log_info(f"Spawned {display} via dump inv.")
            return dump_hit

    pools = _named_pool_candidates(row) or ([pool] if pool else [])

    if not (named_unique and not wants_shiny):
        for pname in pools:
            try:
                hit = spawn_item_pool(pname, level, count)
            except Exception:  # noqa: BLE001
                hit = 0
            if hit:
                _set_pearl_spawn_delivery(
                    "pool_spawn",
                    pname,
                    skip_verify=True,
                    loot_verified=False,
                )
                _log_info(f"Spawned {display} via item pool {pname}.")
                return int(hit)

    if not (named_unique and not wants_shiny):
        before_loc, before_keys = _capture_loot_snapshot()
        native_hit = _try_catalog_native_pool_spawn(
            pools,
            level=level,
            count=count,
            display=display,
            before_loc=before_loc,
            before_keys=before_keys,
        )
        if native_hit is not None:
            return native_hit

        from .item_spawn.bl4_spawn_delegate import try_bl4_item_spawner_entry

        bl4_hit = try_bl4_item_spawner_entry(
            row,
            count=count,
            level=level,
            catalog=catalog,
        )
        if bl4_hit is not None:
            _log_info(f"Spawned {display} via the external pool backend.")
            return bl4_hit

    if catalog and not wants_shiny:
        dump_hit = _dump_inv_catalog_spawn(
            row, catalog, count=count, level=level, skip_verify=skip_verify
        )
        if dump_hit:
            _log_info(f"Spawned {display} via dump inv.")
            return dump_hit
        serial_hit = _try_catalog_serial_grant(
            catalog, row, count=count, display=display
        )
        if serial_hit is not None:
            return serial_hit
        return _spawn_catalog_named(
            catalog,
            level=level,
            count=count,
            display=display,
            wants_shiny=wants_shiny,
            entry=row,
        )

    if not wants_shiny and catalog and "_comp_05_legendary_" in catalog:
        if _spawn_queue_is_selected() or _SINGULAR_PATH_TEST:
            raise RuntimeError(
                f"{display}: named legendary missed verified ground delivery "
                f"(catalog={catalog}). Stand on open ground and retry."
            )

    if wants_shiny:
        raise RuntimeError(f"{display}: no new ground loot")
    raise RuntimeError(f"{display}: no catalog_key or NCS pool for named spawn ({pool})")


def _prepare_pearl_spawn_context(catalog: str, manifest_pool: str = "") -> None:
    """Unlock shiny/phosphene cosmetics before Raid2 / comp_06 pearl spawns."""
    from .item_spawn.shiny_pearl_spawn import (
        prepare_shiny_pool_context,
        primary_shiny_pool_for_catalog,
    )

    shiny = primary_shiny_pool_for_catalog(catalog, manifest_pool)
    if shiny:
        prepare_shiny_pool_context(shiny)


def _spawn_pearl_dump_verified(
    entry: dict[str, str],
    *,
    level: int,
    count: int,
    display: str,
    wants_shiny: bool = False,
) -> int:
    """
    Named pearl — fast native pool for pearl_pool tier, else merge / serial / NCS.
    OK when delivery is trusted or a weapon pickup appears at feet.
    """
    row = dict(entry)
    pool = str(row.get("itempool") or "").strip()
    catalog = str(row.get("catalog_key") or "").strip().lower()
    pools = _named_pool_candidates(row) or ([pool] if pool else [])

    manifest = None
    if catalog:
        try:
            from .item_spawn.pearlescent_manifest import pearlescent_row

            manifest = pearlescent_row(catalog)
        except Exception:  # noqa: BLE001
            manifest = None

    if manifest and manifest.get("comp_class") == "pearl_pool":
        return _escalate_pearl_catalog_spawn(
            catalog,
            pool,
            level=level,
            title=display,
        )

    if manifest and manifest.get("comp_class") == "p6" and pool:
        fast = _try_fast_pearl_named_pool(
            pool,
            catalog,
            level=level,
            count=count,
        )
        if fast:
            return fast

    if _bulk_spawn_simple_mode():
        # Crow / parent-supplement pearls: never NCS-first (deleted pool silent-OKs).
        if catalog and (
            _pool_needs_dump_first(pool, catalog)
            or catalog in _PEARL_PARENT_SUPPLEMENT_CATALOGS
        ):
            return _escalate_pearl_catalog_spawn(
                catalog,
                pool,
                level=level,
                title=display,
            )
        if pools:
            from .item_spawn.ncs_pool_spawn import spawn_legacy_itempool

            spawned, _err = spawn_legacy_itempool(pools, count=count, level=level)
            if spawned > 0:
                _set_pearl_spawn_delivery("ncs_legacy_bulk", pools[0])
                return spawned
        if catalog:
            serial_hit = _try_catalog_serial_grant(
                catalog, row, count=count, display=display
            )
            if serial_hit:
                _set_pearl_spawn_delivery("pearl_serial_bulk", catalog, loot_verified=True)
                return serial_hit
        if pool:
            hit = spawn_item_pool(pool, level, count)
            if hit:
                _set_pearl_spawn_delivery("pool_spawn_bulk", pool)
                return hit
        raise RuntimeError(f"{display}: bulk pearl spawn failed (no NCS pool)")

    if catalog:
        _prepare_pearl_spawn_context(catalog, pool)

    def _path_ok(
        spawned: int,
        before_loc: object | None,
        before_keys: set[str] | None,
        method: str,
        detail: str,
        *,
        defer_only: bool = False,
    ) -> int | None:
        if spawned <= 0:
            return None
        if defer_only:
            _set_pearl_spawn_delivery(method, detail)
            return spawned
        if before_loc is not None and before_keys is not None:
            if _loot_gained_since(before_loc, before_keys):
                if catalog:
                    _apply_pearl_customization_for_catalog(catalog)
                _claim_loot_since(before_loc, before_keys)
                _set_pearl_spawn_delivery(method, detail, loot_verified=True)
                return spawned
            method_l = str(method or "").lower()
            if method_l.startswith(("pearl_merge", "dump_serial", "pearl_serial")):
                if _pool_needs_dump_first(pool, catalog):
                    _set_pearl_spawn_delivery(method, detail, loot_verified=True)
                    return spawned
            return None
        _set_pearl_spawn_delivery(method, detail)
        return spawned

    def _try_merge_inline() -> int | None:
        before_loc, before_keys = _capture_loot_snapshot()
        try:
            from .item_spawn.pearl_comp_spawn import try_spawn_pearl_comp_world

            merge = try_spawn_pearl_comp_world(
                catalog,
                count=count,
                level=level,
                pool_name=pool or None,
                drop_only=True,
            )
            if merge.ok:
                hit = _path_ok(
                    count,
                    before_loc,
                    before_keys,
                    str(merge.method or "pearl_merge"),
                    catalog,
                )
                if hit:
                    _log_info(f"Spawned {display} via merge inline ({catalog}).")
                    return hit
        except Exception:  # noqa: BLE001
            pass
        return None

    # Curated @U first — bundled Lootlemon serials do not need live NCS.
    if catalog:
        before_loc, before_keys = _capture_loot_snapshot()
        serial_hit = _try_catalog_serial_grant(
            catalog, row, count=count, display=display
        )
        if serial_hit is not None:
            hit = _path_ok(serial_hit, before_loc, before_keys, "pearl_serial", catalog)
            if hit:
                _log_info(f"Spawned {display} via @U serial ({catalog}).")
                return hit
            if _pool_needs_dump_first(pool, catalog):
                _set_pearl_spawn_delivery("pearl_serial", catalog, loot_verified=True)
                return max(1, int(serial_hit))

    # FModel merge inline when @U misses.
    if catalog:
        merge_hit = _try_merge_inline()
        if merge_hit:
            return merge_hit

    if pools:
        before_loc, before_keys = _capture_loot_snapshot()
        from .item_spawn.ncs_pool_spawn import spawn_itempool_names

        spawned, _err = spawn_itempool_names(
            pools,
            count=count,
            level=level,
            require_loot_verify=True,
        )
        hit = _path_ok(spawned, before_loc, before_keys, "ncs_verified_pool", pools[0])
        if hit:
            _log_info(f"Spawned {display} via verified NCS {pools[0]}.")
            return hit

    if catalog:
        from .item_spawn.shiny_pearl_spawn import spawn_named_pearl_shiny

        before_loc, before_keys = _capture_loot_snapshot()
        attempted, verified, method, shiny_pool = spawn_named_pearl_shiny(
            catalog,
            pool,
            count=count,
            level=level,
        )
        if attempted and verified and _loot_gained_since(before_loc, before_keys):
            _claim_loot_since(before_loc, before_keys)
            _set_pearl_spawn_delivery(
                method or "pearl_shiny",
                shiny_pool or pool or catalog,
                loot_verified=True,
            )
            _log_info(f"Spawned {display} via shiny pool {shiny_pool}.")
            return count

    try:
        from .item_spawn.bl4_spawn_delegate import try_bl4_item_spawner_entry

        before_loc, before_keys = _capture_loot_snapshot()
        bl4 = try_bl4_item_spawner_entry(
            row,
            count=count,
            level=level,
            catalog=catalog,
        )
        if bl4 and before_loc is not None and before_keys is not None:
            if _loot_gained_since(before_loc, before_keys):
                _claim_loot_since(before_loc, before_keys)
                _set_pearl_spawn_delivery("bl4_pearl", pool or catalog, loot_verified=True)
                _log_info(f"Spawned {display} via BL4 dump pipeline (feet verified).")
                return bl4
    except Exception:  # noqa: BLE001
        pass

    if pools:
        before_loc, before_keys = _capture_loot_snapshot()
        from .item_spawn.ncs_pool_spawn import spawn_legacy_itempool

        spawned, _err = spawn_legacy_itempool(pools, count=count, level=level)
        if spawned > 0:
            if catalog:
                _apply_pearl_customization_for_catalog(catalog)
            hit = _path_ok(spawned, before_loc, before_keys, "ncs_legacy", pool or catalog)
            if hit:
                return hit
            _set_pearl_spawn_delivery("ncs_legacy", pool or catalog)
            return spawned

    raise RuntimeError(
        f"{display}: pearl spawn failed — no weapon loot at feet "
        f"(merge, NCS, shiny, BL4, serial). Stand on open ground and retry."
    )


def _spawn_pearl_serial_first(
    entry: dict[str, str],
    *,
    level: int,
    count: int,
    display: str,
    wants_shiny: bool = False,
) -> int:
    """Alias — dump-first verified pearl spawn."""
    return _spawn_pearl_dump_verified(
        entry,
        level=level,
        count=count,
        display=display,
        wants_shiny=wants_shiny,
    )


def _spawn_comp06_pearl_named(
    entry: dict[str, str],
    *,
    level: int,
    count: int,
    display: str,
) -> int:
    """True comp_06 pearlescents — serial bookmark first, then NCS/shiny fallbacks."""
    return _spawn_pearl_serial_first(
        entry,
        level=level,
        count=count,
        display=display,
    )


def _catalog_key_from_itempool(pool_name: str) -> str:
    """itempool_ord_ar_05_legendary_crowsourced → ord_ar_comp_05_legendary_crowsourced."""
    pool_l = str(pool_name or "").strip().lower()
    if not pool_l.startswith("itempool_"):
        return ""
    try:
        from .item_spawn.shiny_pearl_spawn import catalog_key_from_shiny_pool

        hit = str(catalog_key_from_shiny_pool(pool_name) or "").strip().lower()
        if hit:
            return hit
    except Exception:  # noqa: BLE001
        pass
    if pool_l.endswith("_pearl"):
        stem = pool_l[: -len("_pearl")]
        match = re.match(r"^itempool_(.+)_05_legendary_(.+)$", stem)
        if match:
            return f"{match.group(1)}_comp_05_legendary_{match.group(2)}"
    # Dedicated classmod pools: itempool_classmod_corpohacker_05_legendary_raid2
    # → classmod_corpohacker_comp_05_legendary_raid2
    match = re.match(r"^itempool_(classmod_[a-z0-9_]+)_05_legendary_(.+)$", pool_l)
    if match:
        return f"{match.group(1)}_comp_05_legendary_{match.group(2)}"
    return ""


def _pool_needs_dump_first(pool: str, catalog: str) -> bool:
    """Dump inv / merge before silent native pools (deleted NCS, pearl supplements, Raid3).

    Do NOT blanket every named L5 catalog — that forced dump/yank for guns that
    have live itempool_*_05_legendary_* rows and broke natural front spit.
    """
    pool_l = str(pool or "").strip().lower()
    cat = str(catalog or "").strip().lower()
    if pool_l in _DUMP_FIRST_NCS_MISSING_POOLS:
        return True
    if cat in _PATCH_INLINE_INVENTORY_DEFS or cat in _NCS_DUMP_ONLY_INVS:
        return True
    # Midnight base: no live non-shiny pool — dump Pascal inv (not CrowdSourced_shiny).
    if cat in _NAMED_BASE_DUMP_INVS and not (
        pool_l.endswith("_shiny") or "_shiny_" in pool_l
    ):
        return True
    if cat in _PEARL_PARENT_SUPPLEMENT_CATALOGS:
        return True
    if cat and "crowsourced" in cat and "crowdsourced" not in cat:
        return True
    # Synthetic UI pool ids (itempool_*_comp_05_*) are not live NCS rows.
    if "_comp_05_" in pool_l or "_comp_06_" in pool_l:
        return True
    # True pearls / Raid3 / blackmarket — dump/@U before silent native.
    if "_comp_06_pearl_" in cat:
        return True
    if "blackmarket_comp" in pool_l or cat.endswith("_discjockey") or "discjockey" in cat:
        return True
    try:
        from .item_spawn.pearlescent_manifest import is_pearlescent_catalog

        if cat and is_pearlescent_catalog(cat):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        from .item_spawn.raid3_content import RAID3_CATALOG_KEYS

        if cat in RAID3_CATALOG_KEYS:
            return True
    except Exception:  # noqa: BLE001
        pass
    # All *_shiny rows: dump / @U first (NCS often silent-empty, esp. DLC).
    if pool_l.endswith("_shiny") or "_shiny_" in pool_l:
        return True
    # Named L5 catalog with NO live registered non-comp pool → dump only.
    if cat and "_comp_05_legendary_" in cat:
        for cand in _native_legendary_pool_candidates(cat, pool_l, wants_shiny=False):
            cand_l = str(cand or "").strip().lower()
            if cand_l.endswith("_shiny") or "_shiny_" in cand_l:
                continue
            if _strict_registered_native_pool(cand):
                return False
        return True
    return False


def _rewrite_pearl_pool_entry(entry: dict[str, str]) -> dict[str, str]:
    """itempool8 deleted base Crow pool — always use *_pearl pool for pearl catalog rows."""
    row = dict(entry)
    catalog = str(row.get("catalog_key") or "").strip().lower()
    pool_l = str(row.get("itempool") or "").strip().lower()
    if not catalog or catalog not in _PEARL_PARENT_SUPPLEMENT_CATALOGS:
        return row
    if pool_l.endswith("_pearl"):
        return row
    try:
        from .item_spawn.pearlescent_manifest import pearlescent_row

        manifest = pearlescent_row(catalog)
        if manifest and manifest.get("itempool"):
            row["itempool"] = str(manifest["itempool"])
            if str(row.get("category") or "").strip().lower() not in ("pearl",):
                row["category"] = "Pearl"
    except Exception:  # noqa: BLE001
        pass
    return row


def _curated_serial_for_entry(catalog: str, pool: str, display: str) -> str | None:
    catalog = str(catalog or "").strip().lower()
    pool = str(pool or "").strip()
    display = str(display or "").strip()
    if _wants_shiny_spawn(pool=pool, display=display) or "midnight defiance" in display.lower():
        try:
            from .shinies import serial_for_shiny_pool

            hit = serial_for_shiny_pool(pool)
            if hit:
                return hit
        except Exception:  # noqa: BLE001
            pass
        try:
            from .item_spawn.shiny_pool_lookup import serial_for_shiny_pool as dump_serial

            hit = dump_serial(pool)
            if hit:
                return hit
        except Exception:  # noqa: BLE001
            pass
    dump_only = str(_DUMP_ONLY_GROUND_SERIALS.get(catalog) or "").strip()
    if dump_only:
        return dump_only
    if catalog:
        try:
            from .item_spawn.pearl_serial_spawn import serials_for_catalog

            serials = list(serials_for_catalog(catalog) or [])
            if serials:
                return str(serials[0])
        except Exception:  # noqa: BLE001
            pass
    return None


def _shiny_pool_for_dump_catalog(catalog: str, pool: str = "") -> str:
    """Map dump catalog / synthetic pool → NCS *_shiny itempool name when known."""
    cat = str(catalog or "").strip().lower()
    pool_l = str(pool or "").strip().lower()
    mapped = str(_DUMP_CATALOG_NATIVE_POOLS.get(cat) or "").strip()
    if mapped:
        return mapped
    if pool_l.endswith("_shiny") or "_shiny_" in pool_l:
        return str(pool or "").strip()
    match = re.match(r"^([a-z0-9]+)_([a-z0-9]+)_comp_05_legendary_(.+)$", cat)
    if match:
        return (
            f"itempool_{match.group(1)}_{match.group(2)}_05_legendary_"
            f"{match.group(3)}_shiny"
        )
    return ""


def _registered_named_unique_ncs_pool(catalog: str, pool: str = "") -> str | None:
    """Live Nexus id for a named unique — the registered *_shiny twin.

    Base ``itempool_*_05_legendary_token`` is not in ncs_native_itempools.json.
    The *_shiny sibling is (Laser Disker, Buzzymuzz, Chuck, …). Drop All Shinies
    and Selected shiny already drop those guns. Save cosmetics decide shiny vs
    normal look — the pool still spits the unique on the ground.
    """
    seen: set[str] = set()
    candidates: list[str] = []
    mapped = _shiny_pool_for_dump_catalog(catalog, pool)
    if mapped:
        candidates.append(mapped)
    for cand in _native_legendary_pool_candidates(catalog, pool, wants_shiny=True):
        candidates.append(cand)
    for cand in candidates:
        raw = str(cand or "").strip()
        low = raw.lower()
        if not low or low in seen:
            continue
        seen.add(low)
        if _is_wrong_family_shiny_pool(raw):
            continue
        native = _strict_registered_native_pool(raw)
        if native:
            return native
    return None


def _native_legendary_pool_candidates(
    catalog: str, pool: str = "", *, wants_shiny: bool = True
) -> list[str]:
    """Real NCS pool names for a dump catalog (never synthetic itempool_*_comp_05_*)."""
    cat = str(catalog or "").strip().lower()
    pool_l = str(pool or "").strip()
    out: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        raw = str(name or "").strip()
        if not raw:
            return
        low = raw.lower()
        if "_comp_05_" in low or "_comp_06_" in low or low in seen:
            return
        seen.add(low)
        out.append(raw)

    # Roil / Rainmaker: FModel has ONLY mal_sg *_shiny + BOR_SM/bor_sr inv.
    # Never synthesize itempool_bor_* or stripped mal_sg without _shiny.
    mapped = str(_DUMP_CATALOG_NATIVE_POOLS.get(cat) or "").strip()
    if mapped:
        add(mapped)
        if pool_l and pool_l.lower() == mapped.lower():
            return out
        return out

    if pool_l and "_comp_05_" not in pool_l.lower() and "_comp_06_" not in pool_l.lower():
        if _pool_matches_shiny_intent(pool_l, wants_shiny):
            add(pool_l)
    # tor_grenade_gadget_comp_05_legendary_slippy / ord_shield_comp_05_…
    # → itempool_tor_grenade_gadget_05_legendary_slippy (not synthetic *comp*).
    if "_comp_05_legendary_" in cat:
        left, token = cat.split("_comp_05_legendary_", 1)
        parts = [p for p in left.split("_") if p]
        if len(parts) >= 2 and token:
            mfr, wtype = parts[0], "_".join(parts[1:])
            add(f"itempool_{mfr}_{wtype}_05_legendary_{token}")
            try:
                from .item_spawn.raid3_content import RAID3_PRIMARY_POOL_OVERRIDES

                raid_shiny = str(RAID3_PRIMARY_POOL_OVERRIDES.get(cat) or "").strip()
                if raid_shiny:
                    if raid_shiny.lower().endswith("_shiny"):
                        base = raid_shiny[: -len("_shiny")]
                        if _pool_matches_shiny_intent(base, wants_shiny):
                            add(base)
                    if _pool_matches_shiny_intent(raid_shiny, wants_shiny):
                        add(raid_shiny)
            except Exception:  # noqa: BLE001
                pass
            if wants_shiny:
                add(f"itempool_{mfr}_{wtype}_05_legendary_{token}_shiny")
            pascal = "".join(part[:1].upper() + part[1:] for part in token.split("_") if part)
            if pascal and pascal.lower() != token:
                add(f"itempool_{mfr}_{wtype}_05_legendary_{pascal}")
                if wants_shiny:
                    add(f"itempool_{mfr}_{wtype}_05_legendary_{pascal}_shiny")
    elif "_comp_06_pearl_" in cat:
        left, token = cat.split("_comp_06_pearl_", 1)
        parts = [p for p in left.split("_") if p]
        if len(parts) >= 2 and token:
            mfr, wtype = parts[0], "_".join(parts[1:])
            add(f"itempool_{mfr}_{wtype}_06_pearl_{token}")
            pascal = "".join(part[:1].upper() + part[1:] for part in token.split("_") if part)
            if pascal and pascal.lower() != token:
                add(f"itempool_{mfr}_{wtype}_06_pearl_{pascal}")
    return out


def _curated_serial_for_dump_catalog(catalog: str, pool: str, display: str) -> str | None:
    """@U for dump-named L5s that lack pearl catalog serials (Bubbles / Lucian / …)."""
    hit = _curated_serial_for_entry(catalog, pool, display)
    if hit:
        return hit
    shiny_pool = _shiny_pool_for_dump_catalog(catalog, pool)
    if shiny_pool:
        try:
            from .shinies import serial_for_shiny_pool

            hit = serial_for_shiny_pool(shiny_pool)
            if hit:
                return hit
        except Exception:  # noqa: BLE001
            pass
        try:
            from .item_spawn.shiny_pool_lookup import serial_for_shiny_pool as dump_serial

            hit = dump_serial(shiny_pool)
            if hit:
                return hit
        except Exception:  # noqa: BLE001
            pass
    # Token from catalog tail: …_legendary_bubbles → bubbles / lucians_flank alias.
    cat = str(catalog or "").strip().lower()
    token = ""
    if "legendary_" in cat:
        token = cat.rsplit("legendary_", 1)[-1]
    if token:
        try:
            from .shinies import serial_for_shiny_pool

            hit = serial_for_shiny_pool(f"itempool_x_x_05_legendary_{token}_shiny")
            if hit:
                return hit
        except Exception:  # noqa: BLE001
            pass
    return None


def _try_curated_dump_serial(
    entry: dict[str, str],
    *,
    count: int,
    display: str,
) -> int | None:
    """Lootlemon @U first — works without live NCS (FModel/dump curated serials)."""
    catalog = str(entry.get("catalog_key") or "").strip().lower()
    pool = str(entry.get("itempool") or "").strip()
    serial = _curated_serial_for_dump_catalog(catalog, pool, display)
    if not serial:
        return None
    before_loc, before_keys = _capture_loot_snapshot()
    from .item_spawn.pearl_serial_spawn import try_deliver_serial_comprehensive

    ok, via = try_deliver_serial_comprehensive(
        serial, count, prefer_ground=True, ground_only=True
    )
    if not ok:
        return None
    trust_serial = _pool_needs_dump_first(pool, catalog) or (
        catalog and "_comp_05_legendary_" in catalog
    )
    if before_loc is not None and before_keys is not None and _loot_gained_since(before_loc, before_keys):
        _claim_loot_since(before_loc, before_keys)
        _set_pearl_spawn_delivery("dump_serial_ground", via, loot_verified=True)
        return max(1, int(count))
    if trust_serial:
        _set_pearl_spawn_delivery("dump_serial_ground", via, loot_verified=True)
        _log_info(f"{display}: ground @U via {via} (dump serial, no NCS required).")
        return max(1, int(count))
    return None


def _resolve_pearl_catalog_from_pool(pool_name: str) -> str:
    """Map live pearl pool ids to catalog_key via bundled pearl_spawn_serials aliases."""
    pool_l = str(pool_name or "").strip().lower()
    if not pool_l:
        return ""
    try:
        from .item_spawn.squ1ggs_spawn_bridge import catalog_key_from_pool

        hit = catalog_key_from_pool(pool_name, None)
        if hit:
            return hit
        from .item_spawn.mod_data import read_mod_json
        from pathlib import Path

        doc = read_mod_json(
            Path(__file__).resolve().parent
            / "item_spawn"
            / "data"
            / "reference"
            / "pearl_spawn_serials.json"
        )
        aliases = doc.get("native_pool_aliases") if isinstance(doc, dict) else {}
        if isinstance(aliases, dict):
            for catalog, alias_pool in aliases.items():
                if str(alias_pool or "").strip().lower() == pool_l:
                    return str(catalog).strip().lower()
    except Exception:  # noqa: BLE001
        pass
    return ""


def _lean_inv_handles_for_named(entry: dict[str, str], catalog: str) -> list[str]:
    """At most two inv handles — ISP-style, no combinatorial casing explosion."""
    from .item_spawn.legendary_dump_manifest import dump_inv_handles_for_catalog

    out: list[str] = []
    seen: set[str] = set()

    def add(handle: str) -> None:
        raw = str(handle or "").strip()
        if not raw:
            return
        low = raw.lower()
        if low in seen:
            return
        seen.add(low)
        out.append(raw)

    add(str(entry.get("dump_inv") or "").strip())
    ncs = str(_NCS_DUMP_ONLY_INVS.get(str(catalog or "").strip().lower()) or "").strip()
    add(ncs)
    base_dump = str(
        _NAMED_BASE_DUMP_INVS.get(str(catalog or "").strip().lower()) or ""
    ).strip()
    add(base_dump)
    try:
        from .item_spawn.shiny_pool_lookup import inv_handles_for_named_unique

        pool = str(entry.get("itempool") or "").strip()
        cat = str(catalog or "").strip().lower()
        live_shiny = _registered_named_unique_ncs_pool(cat, pool) or ""
        for handle in inv_handles_for_named_unique(cat, live_shiny) or []:
            add(handle)
    except Exception:  # noqa: BLE001
        pass
    for handle in _catalog_inv_handles(catalog)[:6]:
        add(handle)
    return out[:8]


def _spawn_named_legendary_lean(
    entry: dict[str, str],
    *,
    catalog: str,
    pool: str,
    display: str,
    count: int,
    level: int,
    wants_shiny: bool,
) -> int | None:
    """Dump/@U lean for dump-first catalogs (Roil, missing NCS, Raid3, …).

    Spawn Selected uses the same live-first path as Spawn All — not this alone.
    Never raise mid-path — caller decides.
    """
    prefer_dump = bool(
        _SINGULAR_PATH_TEST
        or _pool_needs_dump_first(pool, catalog)
    )
    drain_trust = bool(_BULK_SPAWN_DRAINING and not _SINGULAR_PATH_TEST)

    def _try_native_named() -> int | None:
        for native in _native_legendary_pool_candidates(
            catalog, pool, wants_shiny=wants_shiny
        ):
            native_l = native.lower()
            if native_l in _FAKE_BASE_ITEMPOOLS:
                continue
            if not _pool_matches_shiny_intent(native_l, wants_shiny):
                continue
            before_loc, before_keys = (None, None)
            must_see = bool(not drain_trust)
            if must_see:
                before_loc, before_keys = _capture_loot_snapshot()
            try:
                spawned = spawn_item_pool(native, level, count)
                if spawned <= 0:
                    continue
                if must_see:
                    if before_loc is None or before_keys is None:
                        continue
                    _yank_singular_loot_in_front(before_keys=before_keys)
                    if not _loot_gained_since(before_loc, before_keys):
                        continue
                    _claim_loot_since(before_loc, before_keys)
                    _set_pearl_spawn_delivery(
                        "ncs_named_pool",
                        native,
                        loot_verified=True,
                    )
                    return int(spawned)
                _set_pearl_spawn_delivery(
                    "ncs_named_pool",
                    native,
                    skip_verify=True,
                    loot_verified=False,
                )
                return int(spawned)
            except Exception:  # noqa: BLE001
                continue
        return None

    def _try_dump_and_serial() -> int | None:
        if catalog and (
            catalog in _NCS_DUMP_ONLY_INVS
            or catalog in _PATCH_INLINE_INVENTORY_DEFS
            or catalog in _NAMED_BASE_DUMP_INVS
        ):
            try:
                hit = _spawn_proven_catalog_ground(
                    catalog,
                    count=count,
                    level=level,
                    display=display,
                    pool=pool,
                    prefer_serial=True,
                    wants_shiny=wants_shiny,
                    allow_native=False,
                )
                if hit > 0:
                    return int(hit)
            except RuntimeError:
                pass
        handles = _lean_inv_handles_for_named(entry, catalog)
        if not handles and catalog:
            handles = _catalog_inv_handles(catalog)[:2]
        if handles:
            from .item_spawn.comp_loot_drop import (
                spawn_inv_handles_at_feet,
                spawn_named_comp_inline_at_feet,
            )

            spawn_fn = (
                spawn_named_comp_inline_at_feet
                if not wants_shiny
                else spawn_inv_handles_at_feet
            )
            dump_spawned, _dump_err = spawn_fn(
                handles,
                count=count,
                level=level,
                skip_verify=True,
            )
            if dump_spawned > 0:
                _set_pearl_spawn_delivery(
                    "dump_inv_lean",
                    handles[0],
                    loot_verified=True,
                    skip_verify=True,
                )
                return int(dump_spawned)
        if catalog:
            from .item_spawn.pearl_serial_spawn import try_spawn_catalog_via_serial

            try:
                serial_ok, serial_method = try_spawn_catalog_via_serial(
                    catalog, count=count
                )
            except Exception as serial_exc:  # noqa: BLE001
                serial_ok, serial_method = False, str(serial_exc)
            if serial_ok:
                _set_pearl_spawn_delivery(
                    str(serial_method or "pearl_serial"),
                    catalog,
                    skip_verify=True,
                    loot_verified=True,
                )
                return max(1, int(count))
        dump_serial = str(_DUMP_ONLY_GROUND_SERIALS.get(catalog) or "").strip()
        if not dump_serial and catalog:
            dump_serial = str(
                _curated_serial_for_dump_catalog(catalog, pool, display) or ""
            ).strip()
        if dump_serial:
            try:
                return _deliver_catalog_serial_ground_only(
                    dump_serial, count, display
                )
            except Exception:  # noqa: BLE001
                pass
        return None

    if prefer_dump:
        dump_hit = _try_dump_and_serial()
        if dump_hit is not None and dump_hit > 0:
            return int(dump_hit)
        if catalog:
            try:
                return _spawn_proven_catalog_ground(
                    catalog,
                    count=count,
                    level=level,
                    display=display,
                    pool=pool,
                    prefer_serial=True,
                    wants_shiny=wants_shiny,
                )
            except RuntimeError:
                return None
        native_hit = _try_native_named()
        if native_hit is not None and native_hit > 0:
            return int(native_hit)
        return None

    native_hit = _try_native_named()
    if native_hit is not None and native_hit > 0:
        return int(native_hit)
    dump_hit = _try_dump_and_serial()
    if dump_hit is not None and dump_hit > 0:
        return int(dump_hit)

    if wants_shiny:
        shiny_serial = _curated_serial_for_dump_catalog(catalog, pool, display)
        if shiny_serial:
            try:
                from .item_spawn.pearl_serial_spawn import try_deliver_serial_comprehensive

                ok, via = try_deliver_serial_comprehensive(
                    shiny_serial, count, prefer_ground=True, ground_only=True
                )
                if ok:
                    _set_pearl_spawn_delivery(
                        f"shiny_serial:{via}",
                        catalog or pool,
                        skip_verify=True,
                        loot_verified=False,
                    )
                    return max(1, int(count))
            except Exception:  # noqa: BLE001
                pass
        shiny_pool = _shiny_pool_for_dump_catalog(catalog, pool)
        if shiny_pool:
            try:
                from .item_spawn.shiny_pearl_spawn import spawn_shiny_from_dump

                dumped, _err, method = spawn_shiny_from_dump(
                    shiny_pool, count=count, level=level, catalog=catalog
                )
                if dumped > 0:
                    _set_pearl_spawn_delivery(
                        str(method or "shiny_dump"),
                        shiny_pool,
                        skip_verify=True,
                        loot_verified=False,
                    )
                    return int(dumped)
            except Exception:  # noqa: BLE001
                pass
    return None


def _ensure_entry_catalog(entry: dict[str, str]) -> dict[str, str]:
    """Resolve catalog_key from pool aliases / raid catalog so singles always have comp tier."""
    row = dict(entry)
    catalog = str(row.get("catalog_key") or "").strip().lower()
    pool = str(row.get("itempool") or "").strip()
    pool_l = pool.lower()
    if not catalog:
        catalog = _patch_inline_catalog_from_pool(pool)
        if catalog:
            row["catalog_key"] = catalog
    if not catalog and pool_l:
        catalog = _catalog_key_from_itempool(pool)
        if catalog:
            row["catalog_key"] = catalog
    if not catalog and pool_l:
        catalog = _resolve_pearl_catalog_from_pool(pool)
        if not catalog:
            try:
                from .standalone_spawning import _load_catalog

                for key, crow in _load_catalog().items():
                    for field in ("itempool", "native_pool", "synthetic_pool"):
                        if str(crow.get(field, "")).strip().lower() == pool_l:
                            catalog = str(key).strip().lower()
                            break
                    if catalog:
                        break
            except Exception:  # noqa: BLE001
                pass
        if catalog:
            row["catalog_key"] = catalog
    if not catalog and pool_l:
        try:
            from .item_spawn.pearlescent_manifest import pearlescent_row_for_pool

            hit = pearlescent_row_for_pool(pool)
            if hit:
                row["catalog_key"] = hit["catalog_key"]
                if not str(row.get("itempool") or "").strip():
                    row["itempool"] = hit["itempool"]
        except Exception:  # noqa: BLE001
            pass
    # Do NOT auto-attach dump_inv to every named legendary — that forced a slow
    # find_all verify path on Roil/Rainmaker and froze Spawn Selected.
    return row


def _should_verify_named_spawn_loot(entry: dict[str, str], catalog: str, pool: str) -> bool:
    """Verify feet loot for named pearl rows; generic type pools trust pool when marked verified."""
    from .item_spawn.pearlescent_manifest import is_pearlescent_catalog

    pool_l = str(pool or "").strip().lower()
    if _is_generic_pearl_pool(pool_l):
        return False
    if str(entry.get("category", "")).strip().lower() == "pearl":
        return True
    if _is_generic_rarity_type_pool(pool_l):
        return False
    if catalog and is_pearlescent_catalog(catalog):
        return True
    if _looks_like_named_item_pool(pool_l) or catalog:
        return True
    return False


def _game_data_path():
    from pathlib import Path

    return Path(__file__).resolve().parent / "data" / "game_data.json"


def _pool_is_cosmetic(pool_key: str) -> bool:
    """Cosmetic unlock pools are rewards/unlocks, not physical ground loot."""
    low = str(pool_key or "").strip().lower()
    return low.startswith("cosmetics_") or low.startswith("itempool_cosmetic")


@lru_cache(maxsize=1)
def _dump_backed_shiny_pool_keys() -> frozenset[str]:
    """Exact live shiny pools exported by the current base + patch NCS dump."""
    path = (
        Path(__file__).resolve().parent
        / "item_spawn"
        / "data"
        / "reference"
        / "ncs_shiny_pools.json"
    )
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return frozenset()
    rows = doc.get("pools") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return frozenset()
    return frozenset(
        str(row.get("itempool") or "").strip().lower()
        for row in rows
        if isinstance(row, dict) and str(row.get("itempool") or "").strip()
    )


_POOL_ITEM_TOKEN_RE = re.compile(r"_(?:05_)?legendary_(.+)$")
_DUMP_COMP_RE = re.compile(r"^([A-Za-z0-9_]+)\.comp_05_legendary_([A-Za-z0-9_]+)$")


def _pool_item_token(pool_key: str) -> str:
    """itempool_mal_sg_05_legendary_reminisce_shiny -> reminisce"""
    low = str(pool_key or "").strip().lower()
    if not low.startswith("itempool_"):
        return ""
    body = low[len("itempool_") :]
    for suffix in ("_shiny", "_pearl"):
        if body.endswith(suffix):
            body = body[: -len(suffix)]
            break
    match = _POOL_ITEM_TOKEN_RE.search(body)
    return match.group(1).strip("_") if match else ""


@lru_cache(maxsize=1)
def _dump_legendary_catalog_index() -> dict[str, str]:
    """Item name -> catalog key, read from the dump's inv comp list.

    A pool name cannot be trusted to describe its item (the Scoot'n'Shoot pool
    is named mal_sg while the comp is TOR_PS), so the comp list is the source of
    truth.  Names claimed by more than one comp are dropped rather than guessed.
    """
    base = Path(__file__).resolve().parent
    sources = (
        base / "item_spawn" / "data" / "reference" / "supplemental_inv_comp_hotfix_9.json",
        base / "data" / "game_data.json",
    )
    found: dict[str, set[str]] = {}
    for path in sources:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        items = doc.get("items") if isinstance(doc, dict) else None
        if not isinstance(items, list):
            continue
        for raw in items:
            match = _DUMP_COMP_RE.match(str(raw or "").strip())
            if not match:
                continue
            prefix, name = match.group(1), match.group(2)
            found.setdefault(name.lower(), set()).add(
                f"{prefix}_comp_05_legendary_{name}".lower()
            )
    return {name: next(iter(keys)) for name, keys in found.items() if len(keys) == 1}


def _dump_catalog_key_for_pool(pool_key: str) -> str:
    # Live NCS first — the older supplemental dump still lists comps that were
    # cut, which is how rows ended up pointing at items that no longer exist.
    try:
        from .item_spawn.ncs_live_catalog import comp_for_pool_token

        handle = comp_for_pool_token(pool_key)
        if handle:
            return handle.replace(".", "_", 1).lower()
    except Exception:  # noqa: BLE001
        pass
    token = _pool_item_token(pool_key)
    if not token:
        return ""
    return _dump_legendary_catalog_index().get(token, "")


def _pool_is_ui_skippable(pool_key: str) -> bool:
    # Raw game_data contributes 100+ Cosmetics_* pools.  They do not expose @U
    # item serials and SpawnInventoryFromItemPool cannot create useful pickups,
    # so keep them out of this physical-loot tool rather than reporting false OKs.
    # Do not hide ammo/currency/weapon rows — user asked to keep the full list.
    low = str(pool_key or "").strip().lower()
    if low in (
        "itempool_fishgrenade_slippy",
    ):
        return True
    return (not pool_key) or _pool_is_cosmetic(pool_key)


def _entry_is_spawn_skippable(entry: dict[str, str]) -> bool:
    """Drop rows that crash or duplicate another list entry (Slippy → Fishing pools)."""
    pool = str(entry.get("itempool") or "").strip().lower()
    catalog = str(entry.get("catalog_key") or "").strip().lower()
    if pool == "itempool_fishgrenade_slippy":
        return True
    if catalog == "tor_grenade_gadget_comp_05_legendary_slippy":
        return True
    return _pool_is_ui_skippable(pool)


def _pool_is_dead_shiny(pool_key: str) -> bool:
    """Shiny pool the current base + patch NCS dump no longer exports."""
    low = str(pool_key or "").strip().lower()
    if not (low.endswith("_shiny") or "_shiny_" in low):
        return False
    live_shinies = _dump_backed_shiny_pool_keys()
    return bool(live_shinies) and low not in live_shinies


def _base_itempool_from_shiny(pool: str) -> str:
    """itempool_…_LeadBalloon_shiny → itempool_…_LeadBalloon (casing preserved)."""
    raw = str(pool or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    if low.endswith("_shiny"):
        return raw[: -len("_shiny")]
    return ""


def _category_for_pool_key(pool_key: str) -> str:
    low = pool_key.lower()
    if "classmod" in low or "class_mod" in low:
        return "Class Mod"
    if "enhancement" in low:
        return "Enhancement"
    if "shield" in low:
        return "Shield"
    if "grenade" in low or "ordnance" in low or "gadget" in low:
        return "Ordnance"
    if "repair_kit" in low or "repkit" in low:
        return "Repkit"
    if "_hw_" in low or low.startswith("itempool_hw"):
        return "Heavy"
    if "_ar_" in low:
        return "Assault Rifle"
    if "_ps_" in low:
        return "Pistol"
    if "_sm_" in low:
        return "SMG"
    if "_sg_" in low:
        return "Shotgun"
    if "_sr_" in low:
        return "Sniper"
    if "pearl" in low:
        return "Pearl"
    if low.endswith("_shiny") or "_shiny_" in low:
        return "Shiny"
    if "ammo" in low:
        return "Ammo"
    if "currency" in low or "cash" in low or "eridium" in low:
        return "Currency"
    return "Other"


def _display_name_for_pool(pool_key: str) -> str:
    body = pool_key[9:] if pool_key.lower().startswith("itempool_") else pool_key
    try:
        from .item_spawn.legendary_dump_manifest import pretty_title_for_catalog_or_pool

        pretty = pretty_title_for_catalog_or_pool(pool=pool_key, fallback="")
        if pretty:
            return pretty
    except Exception:  # noqa: BLE001
        pass
    return body.replace("_", " ").title()


def _pretty_display_for_pool_row(
    *,
    pool: str,
    catalog_key: str = "",
    fallback: str = "",
) -> str:
    """Curated / np_names title — never overwrite a row with a different gun's label.

    The converted NCS dump maps some pool names to the wrong unique (e.g. Disc
    Jockey's blackmarket pool can list Boomslang; np_barrel is Cooper Duper).
    Use that only as a last resort when the fallback is empty.
    """
    try:
        from .item_spawn.legendary_dump_manifest import pretty_title_for_catalog_or_pool

        pretty = pretty_title_for_catalog_or_pool(
            catalog=str(catalog_key or "").strip(),
            pool=str(pool or "").strip(),
            fallback=str(fallback or "").strip(),
        )
        if pretty:
            return _strip_patch_display_prefix(pretty)
    except Exception:  # noqa: BLE001
        pass
    return _strip_patch_display_prefix(str(fallback or pool or "").strip())


def _strip_patch_display_prefix(name: str) -> str:
    """UI lists show the gun name only — never 'Patch - …'."""
    text = str(name or "").strip()
    low = text.lower()
    for prefix in ("patch - ", "patch-", "patch: ", "patch "):
        if low.startswith(prefix):
            return text[len(prefix) :].strip() or text
    return text


def _load_game_data_pool_rows() -> list[dict[str, str]]:
    """Optional gap-fill from game_data.json — never overrides item_pools.json casing."""
    global _GAME_DATA_POOL_ROWS
    if _GAME_DATA_POOL_ROWS is not None:
        return list(_GAME_DATA_POOL_ROWS)
    rows: list[dict[str, str]] = []
    try:
        path = _game_data_path()
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            names = data.get("item_pools", [])
            if isinstance(names, list):
                seen: set[str] = set()
                for raw in names:
                    pool = str(raw or "").strip()
                    low = pool.lower()
                    if not pool or low in seen or _pool_is_ui_skippable(pool):
                        continue
                    seen.add(low)
                    rows.append(
                        {
                            "display_name": _display_name_for_pool(pool),
                            "itempool": pool,
                            "category": _category_for_pool_key(pool),
                            "source": "game_data",
                        }
                    )
    except Exception:
        rows = []
    _GAME_DATA_POOL_ROWS = rows
    return list(rows)


def reload_item_pool_catalog() -> None:
    """Clear cached pool list (after data file edits)."""
    global _ITEM_POOL_CACHE, _GAME_DATA_POOL_ROWS, _CURATED_POOL_KEYS
    _ITEM_POOL_CACHE = None
    _GAME_DATA_POOL_ROWS = None
    _CURATED_POOL_KEYS = None
    try:
        from .item_spawn.legendary_dump_manifest import dump_named_legendary_ui_rows

        dump_named_legendary_ui_rows.cache_clear()
    except Exception:  # noqa: BLE001
        pass


def load_item_pools() -> list[dict[str, str]]:
    """Squ1ggs catalog: curated item_pools.json first (exact pool name casing)."""
    global _ITEM_POOL_CACHE
    if _ITEM_POOL_CACHE is not None:
        return list(_ITEM_POOL_CACHE)
    blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], "item_pools.json")
    if blob is None:
        raise RuntimeError("Could not load item_pools.json from package data.")
    data = json.loads(blob.decode("utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("item_pools.json must contain a JSON list.")
    by_low: dict[str, dict[str, str]] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        pool = str(entry.get("itempool", "")).strip()
        catalog_key = str(entry.get("catalog_key", "")).strip()
        if not catalog_key and _pool_is_dead_shiny(pool):
            # Shiny pool the live dump no longer exports: without a catalog key
            # the spawn has no dump/serial fallback and can only ever miss.
            catalog_key = _dump_catalog_key_for_pool(pool)
        display = str(entry.get("display_name", pool)).strip() or pool
        display = _pretty_display_for_pool_row(
            pool=pool,
            catalog_key=catalog_key,
            fallback=display,
        )
        category = str(entry.get("category", "Other")).strip() or "Other"
        low = pool.lower()
        if not pool or _pool_is_cosmetic(pool):
            continue
        override_cat = str(_SHINY_POOL_CATALOG_OVERRIDES.get(low) or "").strip()
        if override_cat:
            catalog_key = override_cat
        derived = _category_for_pool_key(f"{pool} {display}")
        if derived == "Currency":
            category = derived
        # Shinies live only under Shiny — never mixed into AR / Shotgun / etc.
        if low.endswith("_shiny") or "_shiny_" in low:
            category = "Shiny"
        # Preserve original casing from JSON — Nexus store is case-sensitive for some ids.
        row: dict[str, str] = {"display_name": display, "itempool": pool, "category": category}
        if catalog_key:
            row["catalog_key"] = catalog_key
        by_low[low] = row
    for row in _load_game_data_pool_rows():
        low = row["itempool"].lower()
        if low in _DUMP_FIRST_NCS_MISSING_POOLS:
            continue
        if low.endswith("_shiny") or "_shiny_" in low:
            row = dict(row)
            row["category"] = "Shiny"
        if low not in by_low:
            by_low[low] = dict(row)
    try:
        ncs_blob = pkgutil.get_data(
            __package__ or __name__.rpartition(".")[0],
            "item_spawn/data/reference/ncs_native_itempools.json",
        )
        if ncs_blob:
            ncs_rows = json.loads(ncs_blob.decode("utf-8"))
            if isinstance(ncs_rows, list):
                for entry in ncs_rows:
                    if not isinstance(entry, dict):
                        continue
                    pool = str(entry.get("itempool") or "").strip()
                    low = pool.lower()
                    if not pool or low in by_low or _pool_is_cosmetic(pool):
                        continue
                    catalog_key = str(entry.get("catalog_key") or "").strip()
                    override_cat = str(_SHINY_POOL_CATALOG_OVERRIDES.get(low) or "").strip()
                    if override_cat:
                        catalog_key = override_cat
                    if not catalog_key:
                        catalog_key = (
                            _catalog_key_from_itempool(pool)
                            or _dump_catalog_key_for_pool(pool)
                        )
                    display = _pretty_display_for_pool_row(
                        pool=pool,
                        catalog_key=catalog_key,
                        fallback=str(entry.get("display_name") or pool),
                    )
                    category = str(entry.get("category") or _category_for_pool_key(pool)).strip()
                    if low.endswith("_shiny") or "_shiny_" in low:
                        category = "Shiny"
                    row = {"display_name": display, "itempool": pool, "category": category}
                    if catalog_key:
                        row["catalog_key"] = catalog_key
                    by_low[low] = row
    except Exception:  # noqa: BLE001
        pass
    # For each shiny row, ensure a non-shiny legendary twin exists under its weapon tab.
    for low, row in list(by_low.items()):
        if not (low.endswith("_shiny") or "_shiny_" in low):
            continue
        row["category"] = "Shiny"
        override_cat = str(_SHINY_POOL_CATALOG_OVERRIDES.get(low) or "").strip()
        if override_cat:
            row["catalog_key"] = override_cat
        if not str(row.get("catalog_key") or "").strip():
            cat = _catalog_key_from_itempool(row.get("itempool", "")) or _dump_catalog_key_for_pool(
                row.get("itempool", "")
            )
            if cat:
                row["catalog_key"] = cat
        base = _base_itempool_from_shiny(str(row.get("itempool") or ""))
        if not base:
            continue
        base_low = base.lower()
        cat_key = str(row.get("catalog_key") or "").strip()
        if base_low in by_low:
            existing = by_low[base_low]
            if str(existing.get("category") or "").strip().lower() == "shiny":
                existing["category"] = _category_for_pool_key(base)
            if cat_key and not str(existing.get("catalog_key") or "").strip():
                existing["catalog_key"] = cat_key
            continue
        twin_cat = _category_for_pool_key(base)
        if twin_cat in ("Shiny", "Pearl", "Other"):
            twin_cat = _category_for_pool_key(f"{base} legendary")
        twin_display = _pretty_display_for_pool_row(
            pool=base,
            catalog_key=cat_key,
            fallback=base,
        )
        twin: dict[str, str] = {
            "display_name": twin_display,
            "itempool": base,
            "category": twin_cat if twin_cat not in ("Shiny",) else "Other",
        }
        if cat_key:
            twin["catalog_key"] = cat_key
        by_low[base_low] = twin
    _ITEM_POOL_CACHE = sorted(
        by_low.values(),
        key=lambda row: (row.get("category", "Other"), row.get("display_name", "").lower()),
    )
    return list(_ITEM_POOL_CACHE)


def item_pool_categories() -> list[str]:
    preferred = [
        "All",
        "Assault Rifle",
        "Pistol",
        "SMG",
        "Sniper",
        "Shotgun",
        "Heavy",
        "Class Mod",
        "Enhancement",
        "Shield",
        "Ordnance",
        "Repkit",
        "Ammo",
        "Currency",
        "Pearl",
        "Shiny",
        "Other",
    ]
    found = {entry["category"] for entry in load_item_pools()}
    ordered = [category for category in preferred if category == "All" or category in found]
    for category in sorted(found):
        if category not in ordered:
            ordered.append(category)
    return ordered


def _compact_pool_search_text(text: str) -> str:
    return re.sub(r"[\s\-_]+", "", (text or "").strip().lower())


def _pool_search_matches(needle: str, *haystacks: str) -> bool:
    raw = (needle or "").strip().lower()
    if not raw:
        return True
    compact = _compact_pool_search_text(raw)
    for hay in haystacks:
        low = (hay or "").lower()
        if raw in low:
            return True
        if compact and compact in _compact_pool_search_text(low):
            return True
    return False


def _pearl_child_rows(parent_pool: str) -> list[dict[str, str]]:
    from .standalone_spawning import expanded_pearl_pool_children

    rows: list[dict[str, str]] = []
    for child in expanded_pearl_pool_children(parent_pool):
        title = str(child.get("display_name") or child.get("catalog_key") or "item").strip()
        rows.append(
            {
                # ASCII marker — imgui fonts often render ↳/★ as "?".
                "display_name": f"> {title}",
                "itempool": child["itempool"],
                "category": child.get("category", "Pearl"),
                "catalog_key": child.get("catalog_key", ""),
                "parent_pool": parent_pool,
            }
        )
    return rows


def _balanced_generic_pearl_request(
    entry: dict[str, str],
    *,
    level: int,
    count: int,
) -> list[tuple[dict[str, str], int, int]]:
    """Keep an exact total while adding Pearls omitted by the live parent pool."""
    pool = str(entry.get("itempool") or "").strip()
    total = max(1, min(int(count), MAX_SINGLE_POOL_SPAWN_COUNT))
    if not _is_generic_pearl_pool(pool):
        return [(dict(entry), max(1, int(level)), total)]

    children = _pearl_child_rows(pool)
    supplements = [
        dict(child)
        for child in children
        if str(child.get("catalog_key") or "").strip().lower()
        in _PEARL_PARENT_SUPPLEMENT_CATALOGS
    ]
    # Small requests remain ordinary random parent rolls.  At a roster-sized
    # request (Spawn All, x3 PS, x10, etc.), guarantee every omitted name once.
    if not supplements or total < len(children):
        return [(dict(entry), max(1, int(level)), total)]

    native_count = total - len(supplements)
    rows: list[tuple[dict[str, str], int, int]] = []
    if native_count > 0:
        parent = dict(entry)
        parent["display_name"] = (
            f"{str(entry.get('display_name') or pool).strip()} "
            f"(random x{native_count})"
        )
        rows.append((parent, max(1, int(level)), native_count))
    for child in supplements:
        child["pearl_supplement"] = "1"
        child["parent_pool"] = pool
        rows.append((child, max(1, int(level)), 1))
    return rows


def _raid_catalog_ui_rows() -> list[dict[str, str]]:
    from .standalone_spawning import all_raid_spawn_ui_rows

    out: list[dict[str, str]] = []
    for row in all_raid_spawn_ui_rows():
        title = str(row.get("display_name") or row.get("catalog_key") or row.get("itempool") or "item")
        catalog = str(row.get("catalog_key", "")).strip()
        # Named single-comp classmod rows (Artificer, Bombastic, Grim Sister, …)
        # have no working spawn path on this build — hidden from the UI.
        if catalog.lower().startswith("classmod_"):
            continue
        out.append(
            {
                "display_name": f"> {title}" if catalog else title,
                "itempool": str(row.get("itempool", "")),
                "category": str(row.get("category", "Shiny")),
                "catalog_key": catalog,
            }
        )
    return out


def _registered_pool_keys() -> set[str]:
    """Lowercased pool names from curated item_pools.json (trusted silent spawn)."""
    return {str(e.get("itempool", "")).strip().lower() for e in load_item_pools() if e.get("itempool")}


def _is_generic_pearl_pool(pool_name: str) -> bool:
    from .standalone_spawning import is_generic_pearl_itempool

    return bool(is_generic_pearl_itempool(pool_name))


def _spawn_named_unique_pool_first(
    entry: dict[str, str],
    *,
    catalog: str,
    pool: str,
    display: str,
    count: int,
    level: int,
) -> int:
    """Named L5 non-shiny: live base pool / BL4 backend first (22:02 proven path)."""
    row = dict(entry)
    cat = str(catalog or row.get("catalog_key") or "").strip().lower()
    want = max(1, int(count))
    lvl = max(1, int(level))
    pool_names: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        raw = str(name or "").strip()
        low = raw.lower()
        if not raw or low in seen or low.endswith("_shiny") or "_shiny_" in low:
            return
        seen.add(low)
        pool_names.append(raw)

    add(str(pool or row.get("itempool") or "").strip())
    for cand in _named_pool_candidates(row):
        add(cand)
    if cat:
        for cand in _native_legendary_pool_candidates(cat, pool, wants_shiny=False):
            add(cand)
    if _BULK_SPAWN_DRAINING:
        for pname in pool_names:
            bulk_hit = _try_bulk_native_pool_spawn(
                pname,
                level=lvl,
                count=want,
                catalog=cat,
                wants_shiny=False,
            )
            if bulk_hit:
                return int(bulk_hit)
    verify_pools = bool(_SINGULAR_PATH_TEST) and not _skip_loot_verify()
    for pname in pool_names:
        before_loc: object | None = None
        before_keys: set[str] | None = None
        if verify_pools:
            before_loc, before_keys = _capture_loot_snapshot()
        try:
            hit = spawn_item_pool(pname, lvl, want)
        except Exception:  # noqa: BLE001
            hit = 0
        if not hit:
            continue
        if verify_pools:
            if before_loc is None or before_keys is None:
                continue
            if not _loot_gained_since(before_loc, before_keys):
                continue
            _claim_loot_since(before_loc, before_keys)
            _set_pearl_spawn_delivery(
                "pool_spawn",
                pname,
                skip_verify=False,
                loot_verified=True,
            )
        else:
            _set_pearl_spawn_delivery(
                "pool_spawn",
                pname,
                skip_verify=True,
                loot_verified=True,
            )
        _log_info(f"Spawned {display} via item pool {pname}.")
        return int(hit)
    return 0


def _spawn_named_unique_legendary_ground(
    entry: dict[str, str],
    *,
    catalog: str,
    pool: str,
    display: str,
    count: int,
    level: int,
    raise_on_miss: bool = True,
) -> int:
    """Named L5 dump path — ItemPoolList inv-only, inline comp, merge, @U. No *_shiny pools."""
    row = dict(entry)
    cat = str(catalog or row.get("catalog_key") or "").strip().lower()
    if not cat:
        if raise_on_miss:
            raise RuntimeError(f"{display}: named unique missing catalog_key.")
        return 0
    live_shiny = _registered_named_unique_ncs_pool(cat, pool) or ""
    want = max(1, int(count))
    lvl = max(1, int(level))
    trust = bulk_spawn_is_mass() or _skip_loot_verify()

    from .item_spawn.shiny_pool_lookup import (
        inline_payload_for_base_legendary,
        inv_handles_for_named_unique,
    )

    handles = list(inv_handles_for_named_unique(cat, live_shiny) or [])
    dump_inv = str(row.get("dump_inv") or "").strip()
    if dump_inv and dump_inv.lower() not in {h.lower() for h in handles}:
        handles.insert(0, dump_inv)
    if not handles:
        match = re.match(r"^(.+)_(comp_0[56]_.+)$", cat)
        if match:
            root, comp = match.group(1), match.group(2)
            handles = [f"inv'{root}.{comp}'", f"inv'{root.upper()}.{comp}'"]

    if handles:
        from .item_spawn.item_pool_list_spawn import spawn_itempoollist_inv_at_feet

        list_spawned, _list_err = spawn_itempoollist_inv_at_feet(
            handles[:2],
            count=want,
            level=lvl,
            require_loot_verify=not trust,
            wants_shiny=False,
        )
        if list_spawned > 0:
            _set_pearl_spawn_delivery(
                "dump_itempoollist",
                handles[0],
                skip_verify=trust,
                loot_verified=not trust,
            )
            _log_info(f"Spawned {display} via ItemPoolList dump.")
            return int(list_spawned)

    if handles:
        from .item_spawn.comp_loot_drop import spawn_named_comp_inline_at_feet

        inline_spawned, _inline_err = spawn_named_comp_inline_at_feet(
            handles[:4],
            count=want,
            level=lvl,
            skip_verify=trust,
        )
        if inline_spawned > 0:
            _set_pearl_spawn_delivery(
                "dump_inline_comp",
                handles[0],
                skip_verify=trust,
                loot_verified=not trust,
            )
            _log_info(f"Spawned {display} via inline comp (no phosphene).")
            return int(inline_spawned)

    base_payload = inline_payload_for_base_legendary(live_shiny, catalog=cat)
    if base_payload:
        from .item_spawn.comp_loot_drop import spawn_from_merge_payload

        merged, _merge_err = spawn_from_merge_payload(
            base_payload,
            count=want,
            level=lvl,
            skip_verify=trust,
            pool_name="",
            drop_only=True,
        )
        if merged > 0:
            detail = handles[0] if handles else cat
            _set_pearl_spawn_delivery(
                "dump_inv_merge",
                detail,
                skip_verify=trust,
                loot_verified=not trust,
            )
            _log_info(f"Spawned {display} via dump merge (no phosphene).")
            return int(merged)

    serial_hit = _try_curated_dump_serial(row, count=want, display=display)
    if serial_hit is not None and serial_hit > 0:
        _log_info(f"Spawned {display} via dump @U.")
        return int(serial_hit)

    if raise_on_miss:
        raise RuntimeError(
            f"{display}: named legendary missed — ItemPoolList / inline / merge / @U failed "
            f"(catalog={cat}). Stand on open ground."
        )
    return 0


def _wants_shiny_spawn(*, pool: str, display: str, entry: dict[str, str] | None = None) -> bool:
    """True when this UI row should drop a shiny.

    Spawn All Filtered on All / weapon tabs stamps ``_spawn_shiny=0`` so named
    L5 rows that only have ``*_shiny`` NCS ids still drop the normal legendary
    (dump). The Shiny category stamps ``_spawn_shiny=1``.
    """
    if entry is not None:
        flag = str(entry.get("_spawn_shiny") or "").strip()
        if flag == "1":
            return True
        if flag == "0":
            return False
    pool_l = str(pool or "").strip().lower()
    if pool_l.endswith("_shiny") or "_shiny_" in pool_l:
        return True
    return bool(re.search(r"\bshiny\b", str(display or ""), re.IGNORECASE))



def _spawn_non_shiny_dump_companion(
    catalog: str,
    *,
    level: int,
    count: int = 1,
    display: str = "",
    before_loc: object | None = None,
    before_keys: set[str] | None = None,
) -> tuple[int, str]:
    """After a shiny preload, dump the base (non-shiny) legendary for the same catalog.

    Returns (spawned_count, delivery_method). Count is 0 unless feet loot verifies.
    """
    catalog_l = str(catalog or "").strip().lower()
    if not catalog_l:
        return 0, ""
    # Crow-Sourced Pearl (ORD AR) vs Crowd-Sourced / Midnight Defiance (VLA SR) are different guns.
    # Never auto-dump companions for either — fuzzy "crow*" dump matches the wrong gun.
    if "crowdsourced" in catalog_l or "crowsourced" in catalog_l:
        return 0, ""
    display_l = str(display or "").strip().lower()
    display_compact = display_l.replace("-", "").replace(" ", "")
    if (
        "midnight defiance" in display_l
        or "crowd-sourced" in display_l
        or "crow-sourced" in display_l
        or "crowdsourced" in display_compact
        or "crowsourced" in display_compact
    ):
        return 0, ""

    def _verified(spawned: int, method: str, keys_before: set[str]) -> tuple[int, str]:
        if spawned <= 0:
            return 0, ""
        if before_loc is None:
            return int(spawned), method
        from .item_spawn.loot_verify import unclaimed_loot_gain, verify_available

        if not verify_available():
            return int(spawned), method
        gained = unclaimed_loot_gain(before_loc, keys_before)
        if gained:
            return int(spawned), method
        return 0, ""

    try:
        import re

        from .item_spawn.comp_loot_drop import (
            spawn_inv_handles_at_feet,
            spawn_named_comp_inline_at_feet,
        )
        from .item_spawn.item_pool_list_spawn import spawn_itempoollist_inv_at_feet
        from .item_spawn.legendary_dump_manifest import dump_inv_handles_for_catalog

        handles = list(_catalog_inv_handles(catalog_l) or [])
        if not handles:
            handles = list(dump_inv_handles_for_catalog(catalog_l) or [])
        if not handles:
            match = re.match(r"^(.+)_(comp_0[56]_.+)$", catalog_l)
            if match:
                root, comp = match.group(1), match.group(2)
                handles = [
                    f"inv'{root}.{comp}'",
                    f"inv'{root.upper()}.{comp}'",
                ]
        if not handles:
            return 0, ""
        want = max(1, int(count))
        lvl = max(1, int(level))
        keys_before = set(before_keys or [])
        if before_loc is not None and not keys_before:
            keys_before = _feet_loot_keys_at(before_loc)

        inline_spawned, _inline_err = spawn_named_comp_inline_at_feet(
            handles[:6],
            count=want,
            level=lvl,
            skip_verify=False,
        )
        hit, method = _verified(inline_spawned, "dump_inline_comp", keys_before)
        if hit:
            label = display or catalog_l
            _log_info(f"Dumped non-shiny legendary for {label} via inline comp.")
            return hit, method

        inv_spawned, _inv_err = spawn_inv_handles_at_feet(
            handles[:3],
            count=want,
            level=lvl,
            skip_verify=False,
        )
        hit, method = _verified(inv_spawned, "dump_inv_verified", keys_before)
        if hit:
            label = display or catalog_l
            _log_info(f"Dumped non-shiny legendary for {label} via inv handle.")
            return hit, method

        list_spawned, _list_err = spawn_itempoollist_inv_at_feet(
            handles[:4],
            count=want,
            level=lvl,
            require_loot_verify=False,
            wants_shiny=False,
        )
        hit, method = _verified(list_spawned, "dump_itempoollist", keys_before)
        if hit:
            label = display or catalog_l
            _log_info(f"Dumped non-shiny legendary for {label} via ItemPoolList.")
            return hit, method
        return 0, ""
    except Exception as exc:
        _log_warning(f"Non-shiny dump companion failed ({exc!r}).")
        return 0, ""


def _try_shiny_dump_world(
    pool: str,
    *,
    count: int,
    level: int,
    display: str,
    catalog: str = "",
) -> int:
    """Dump-first world spawn for *_shiny rows. Never mail."""
    pool_name = str(pool or "").strip()
    if not pool_name:
        return 0
    try:
        from .item_spawn.shiny_pearl_spawn import spawn_shiny_from_dump

        dumped, dump_err, dump_method = spawn_shiny_from_dump(
            pool_name,
            count=count,
            level=level,
            catalog=catalog,
        )
        if dumped > 0:
            method = str(dump_method or "dump_serial_ground").strip() or "dump_serial_ground"
            _set_pearl_spawn_delivery(
                method,
                pool_name,
                skip_verify=False,
                loot_verified=True,
            )
            _log_info(f"Spawned {display} via dump shiny ({method}).")
            return int(dumped)
        if dump_err:
            _log_warning(f"{display}: shiny dump missed ({dump_err}).")
    except Exception as exc:
        _log_warning(f"{display}: shiny dump failed ({exc!r}).")
    return 0


def _pool_matches_shiny_intent(pool_name: str, wants_shiny: bool) -> bool:
    low = str(pool_name or "").strip().lower()
    if not low:
        return False
    is_shiny = low.endswith("_shiny") or "_shiny_" in low
    return is_shiny if wants_shiny else not is_shiny


def _named_pool_candidates(entry: dict[str, str]) -> list[str]:
    """Dedicated item pools for a singular/catalog row (random part rolls)."""
    catalog = str(entry.get("catalog_key", "")).strip().lower()
    pool = str(entry.get("itempool", "")).strip()
    display = str(entry.get("display_name", "")).strip()
    wants_shiny = _wants_shiny_spawn(pool=pool, display=display, entry=entry)
    out: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        raw = str(name or "").strip()
        if not raw:
            return
        low = raw.lower()
        if low in seen or _is_generic_pearl_pool(raw):
            return
        if not _pool_matches_shiny_intent(raw, wants_shiny):
            return
        # Never substitute a base legendary when the UI row asked for shiny.
        if wants_shiny and not (low.endswith("_shiny") or "_shiny_" in low):
            return
        seen.add(low)
        out.append(raw)

    add(pool)
    if not catalog:
        return out
    from .item_spawn.pearlescent_manifest import (
        PEARL_BASE_LEGENDARY_POOLS,
        named_pearl_ncs_pool_try_order,
    )
    from .standalone_spawning import RAID2_SPAWN_HINTS, native_pool_for_catalog, row_for_catalog

    for pname in named_pearl_ncs_pool_try_order(catalog, pool):
        add(pname)
    add(PEARL_BASE_LEGENDARY_POOLS.get(catalog))
    add(native_pool_for_catalog(catalog))
    hints = RAID2_SPAWN_HINTS.get(catalog, {}) if isinstance(RAID2_SPAWN_HINTS, dict) else {}
    add(hints.get("native_pool") if isinstance(hints, dict) else None)
    try:
        row = row_for_catalog(catalog)
        add(getattr(row, "native_pool", None))
    except Exception:
        pass
    if wants_shiny:
        bases = list(out)
        for base in bases:
            if not base.lower().endswith("_shiny") and "_shiny_" not in base.lower():
                add(f"{base}_shiny")
        shiny_first = [p for p in out if p.lower().endswith("_shiny") or "_shiny_" in p.lower()]
        rest = [p for p in out if p not in shiny_first]
        return shiny_first + rest
    return out


def _looks_like_named_item_pool(pool_name: str) -> bool:
    """True for dedicated legendary/pearl item pools (not generic type pools)."""
    low = str(pool_name or "").strip().lower()
    if not low:
        return False
    if low in {
        "itempool_ar_06_pearl",
        "itempool_ps_06_pearl",
        "itempool_sm_06_pearl",
        "itempool_sg_06_pearl",
        "itempool_sr_06_pearl",
    }:
        return False
    if re.search(r"_05_legendary$", low) or re.search(r"_06_pearl$", low):
        return False
    return bool(
        "_05_legendary_" in low
        or "_06_pearl_" in low
        or (low.endswith("_shiny") and "legendary" in low)
    )


def _is_generic_rarity_type_pool(pool_name: str) -> bool:
    """Broad item-type pools whose reliable implementation lives in F1 Item Spawner."""
    low = str(pool_name or "").strip().lower()
    return bool(
        re.search(r"_05_legendary$", low)
        or re.search(r"_06_pearl$", low)
    )


def _spawn_pearl_world_named(
    row: dict[str, str],
    *,
    catalog: str,
    pool: str,
    level: int,
    display: str,
) -> int:
    """Pearl-world rows (Abyss, Gomie, Temper, …): live NCS pool then dump fallback."""
    return _escalate_pearl_catalog_spawn(
        catalog,
        pool,
        level=level,
        title=display,
    )


def _spawn_pearl_child_entry(child: dict[str, str], *, level: int, count: int) -> int:
    """Named pearlescent — pearl_pool uses fast escalate; comp_06 tries live pool first."""
    row = _ensure_entry_catalog(dict(child))
    catalog = str(row.get("catalog_key") or "").strip().lower()
    if not catalog:
        display = str(row.get("display_name") or "pearl").strip()
        raise RuntimeError(f"{display}: missing catalog_key for pearl spawn")
    display = str(row.get("display_name") or catalog).strip()
    pool = str(row.get("itempool") or "").strip()

    manifest = None
    try:
        from .item_spawn.pearlescent_manifest import pearlescent_row

        manifest = pearlescent_row(catalog)
    except Exception:  # noqa: BLE001
        manifest = None

    comp_class = str(manifest.get("comp_class") or "") if manifest else ""
    total = 0
    for _ in range(max(1, int(count))):
        if comp_class == "pearl_pool":
            total += _escalate_pearl_catalog_spawn(
                catalog,
                pool,
                level=level,
                title=display,
            )
        elif comp_class == "p6" and pool:
            # Singular / Spawn Selected: escalate (serial/dump/live). Fast live
            # pool alone silent-OKs Constable/Herald/Juliet/… with no feet loot.
            if _SINGULAR_PATH_TEST or _spawn_queue_is_single():
                total += _escalate_pearl_catalog_spawn(
                    catalog,
                    pool,
                    level=level,
                    title=display,
                )
            else:
                hit = _try_fast_pearl_named_pool(
                    pool,
                    catalog,
                    level=level,
                    count=1,
                )
                if hit:
                    total += hit
                else:
                    total += _spawn_pearl_dump_verified(
                        row,
                        level=level,
                        count=1,
                        display=display,
                    )
        elif comp_class == "pearl_world":
            total += _spawn_pearl_world_named(
                row,
                catalog=catalog,
                pool=pool,
                level=level,
                display=display,
            )
        else:
            total += _escalate_pearl_catalog_spawn(
                catalog,
                pool,
                level=level,
                title=display,
            )
    return total


def _try_fast_pearl_named_pool(
    pool: str,
    catalog: str,
    *,
    level: int,
    count: int,
) -> int:
    """One live *_pearl / comp_06 pool roll — RPC ok still needs feet verify."""
    pool_l = str(pool or "").strip()
    if not pool_l.lower().startswith("itempool_"):
        return 0
    from .item_spawn.ncs_pool_spawn import spawn_itempool_names, spawn_legacy_itempool

    spawned, _err = spawn_itempool_names(
        [pool_l],
        count=max(1, int(count)),
        level=level,
        require_loot_verify=False,
    )
    if spawned <= 0:
        spawned, _err = spawn_legacy_itempool(
            [pool_l],
            count=max(1, int(count)),
            level=level,
        )
    if spawned <= 0:
        return 0
    if catalog:
        _apply_pearl_customization_for_catalog(catalog)
    # Never claim verified here — silent empties were counting OK for P6/pearls.
    _set_pearl_spawn_delivery("ncs_live_pool", pool_l, loot_verified=False)
    return int(spawned)


def _spawn_pearl_type_pool_roll(
    pool: str,
    level: int,
    count: int,
    *,
    display: str = "",
) -> int:
    """One live NCS roll on PS/SM/SG/SR/AR 06 Pearl — same path pool buttons use."""
    pool_l = str(pool or "").strip().lower()
    if not pool_l:
        raise RuntimeError("No pearl type pool")
    label = str(display or pool_l).strip()
    before_loc, before_keys = _capture_loot_snapshot()
    native_hit = _try_catalog_native_pool_spawn(
        [pool_l],
        level=level,
        count=max(1, int(count)),
        display=label,
        before_loc=before_loc,
        before_keys=before_keys,
        require_loot=True,
    )
    if native_hit is not None:
        return native_hit
    raise RuntimeError(f"{label}: type pool roll failed ({pool_l})")


def _verified_ncs_pool_spawn(
    pool_names: list[str],
    *,
    level: int,
    count: int = 1,
) -> tuple[int, str | None]:
    """One named pool roll on the live loot-pool service. No world scan."""
    from .item_spawn.ncs_pool_spawn import spawn_itempool_names

    names = [str(n).strip() for n in pool_names if str(n).strip()]
    if not names:
        return 0, "no pool names"
    spawned, err = spawn_itempool_names(
        names[:1],
        count=max(1, int(count)),
        level=level,
        require_loot_verify=False,
    )
    if err:
        return 0, err
    if spawned <= 0:
        return 0, "silent empty"
    return spawned, None


def _try_direct_generic_pearl_ncs(pool_l: str, level: int, count: int) -> int | None:
    """
    Squ1ggs pool spawn — live itempool_*_06_pearl via SpawnInventoryFromItemPool.

    This is what worked before SQBT stopped calling generic pools directly
    (bl4 logs: registered_pool_api on itempool_ps_06_pearl, etc.).
    """
    from .item_spawn.ncs_pool_spawn import spawn_legacy_itempool
    from .item_spawn.squ1ggs_spawn_bridge import spawn_native_pool, try_ncs_native_for_pool

    total = max(1, min(int(count), MAX_SINGLE_POOL_SPAWN_COUNT))
    lvl = max(1, int(level))

    hit = spawn_native_pool(pool_l, count=total, level=lvl)
    if hit.ok:
        _set_pearl_spawn_delivery(
            str(hit.method or "ncs_pool"),
            str(hit.detail or pool_l)[:240],
            loot_verified=False,
        )
        _log_info(f"Generic pearl {pool_l}: direct native NCS ({hit.detail}).")
        return total

    spawned, err = spawn_legacy_itempool([pool_l], count=total, level=lvl)
    if spawned > 0:
        _set_pearl_spawn_delivery("ncs_legacy_generic", pool_l, loot_verified=False)
        _log_info(f"Generic pearl {pool_l}: legacy NCS x{spawned}.")
        return spawned

    native = try_ncs_native_for_pool(pool_l, None, count=total, level=lvl)
    if native.ok:
        _set_pearl_spawn_delivery(
            str(native.method or "ncs_native_pool"),
            str(native.detail or pool_l)[:240],
            loot_verified=False,
        )
        _log_info(f"Generic pearl {pool_l}: native store ({native.detail}).")
        return total

    if err:
        _log_warning(f"Generic pearl {pool_l}: direct NCS miss ({err})")
    return None


def _named_pearl_live_ncs_pool(catalog: str, pool: str) -> str | None:
    """Dump-registered standalone itempool, or None when this pearl is dump-inv only."""
    from .item_spawn.pearlescent_manifest import (
        itempool_in_dump,
        ncs_dump_inv_pool,
        pearlescent_row,
    )

    if catalog in _PATCH_INLINE_INVENTORY_DEFS or catalog in _PEARL_ITEMPOOLLIST_CATALOGS:
        return None
    row = pearlescent_row(catalog)
    if row and row["comp_class"] == "pearl_world":
        cand = str(pool or "").strip()
        if not cand.lower().startswith("itempool_") and row:
            cand = str(row["itempool"] or "").strip()
        if cand.lower().startswith("itempool_") and itempool_in_dump(cand):
            return cand
        return None
    cand = str(pool or "").strip()
    if not cand.lower().startswith("itempool_") and row:
        cand = str(row["itempool"] or "").strip()
    if not cand.lower().startswith("itempool_"):
        return None
    if ncs_dump_inv_pool(cand):
        return None
    if itempool_in_dump(cand):
        return cand
    return None


def _named_pearl_dump_handles(catalog: str) -> list[str]:
    handles: list[str] = []
    patch_inv = str(_PATCH_INLINE_INVENTORY_DEFS.get(catalog) or "").strip()
    if patch_inv:
        handles.append(patch_inv)
    # Crow-Sourced Pearl: FModel dump + merge payload use this handle; itempool8 may
    # delete the live base pool, so force the canonical inv token early.
    if catalog == "ord_ar_comp_05_legendary_crowsourced":
        handles.append("inv'ORD_AR.comp_05_legendary_crowsourced'")
        handles.append("inv'ORD_AR.comp_05_legendary_Crowsourced'")
    if catalog:
        from .item_spawn.legendary_dump_manifest import dump_inv_handles_for_catalog

        handles.extend(dump_inv_handles_for_catalog(catalog))
    seen: set[str] = set()
    uniq: list[str] = []
    for handle in handles:
        low = handle.lower()
        if not handle or low in seen:
            continue
        seen.add(low)
        uniq.append(handle)
    return uniq


def _escalate_pearl_catalog_spawn(
    catalog: str,
    pool: str,
    *,
    level: int,
    title: str = "",
) -> int:
    """Named pearl: dump inv / ItemPoolList first, live NCS only if dump has a pool.

    Never serial/mail. Spawn All must not find_all-verify with a huge pile already down.
    """
    catalog = str(catalog or "").strip().lower()
    pool = str(pool or "").strip()
    label = str(title or catalog or pool or "pearl").strip()
    bulk = bool(_BULK_SPAWN_DRAINING)
    landing = False
    try:
        from .loot_shapes import landing_armed

        landing = landing_armed()
    except Exception:
        landing = False
    skip_verify = bool(bulk or landing)

    # Pearl-world / patch-inline (Gomie, Abyss, Temper, Burrow/PRISM): dump/@U
    # first. Proven raises on total miss — catch so live NCS can still land.
    if catalog in _PATCH_INLINE_INVENTORY_DEFS:
        try:
            proven = _spawn_proven_catalog_ground(
                catalog,
                count=1,
                level=level,
                display=label,
                pool=pool,
                prefer_serial=True,
            )
            if proven > 0:
                return proven
        except RuntimeError as proven_exc:
            _log_warning(f"{label}: proven miss → live pool ({proven_exc})")

    # Pearl-world rows with live NCS pools (Jailbroken, Gomie, …): pool roll next,
    # including after patch-inline proven miss (dump/@U often fails on some saves).
    try:
        from .item_spawn.pearlescent_manifest import pearlescent_row

        manifest = pearlescent_row(catalog)
    except Exception:  # noqa: BLE001
        manifest = None
    if (
        manifest
        and str(manifest.get("comp_class") or "") == "pearl_world"
        and pool
        and str(pool).lower().startswith("itempool_")
        and not _is_wrong_family_shiny_pool(pool)
        and not (
            str(pool).lower().endswith("_shiny")
            and "burrow" in str(pool).lower()
        )
    ):
        live_hit = _try_fast_pearl_named_pool(pool, catalog, level=level, count=1)
        if live_hit:
            return live_hit
    # Manifest base pool when UI queued Burrow_shiny / wrong-family for PRISM.
    if (
        manifest
        and str(manifest.get("comp_class") or "") == "pearl_world"
        and pool
        and (
            _is_wrong_family_shiny_pool(pool)
            or (
                str(pool).lower().endswith("_shiny")
                and "burrow" in str(pool).lower()
            )
        )
    ):
        base_pool = str(manifest.get("itempool") or "").strip()
        if base_pool and base_pool.lower() != str(pool).lower():
            live_hit = _try_fast_pearl_named_pool(
                base_pool, catalog, level=level, count=1
            )
            if live_hit:
                return live_hit

    ncs_miss = "no live pool"

    # Crow-Sourced Pearl (and peer *_pearl / parent-supplement rows): bulk native
    # often silent-OKs with no loot. Dump/serial first even during Spawn All.
    pearl_needs_dump_first = bool(
        catalog in _PEARL_PARENT_SUPPLEMENT_CATALOGS
        or str(pool).lower().endswith("_pearl")
        or "crowsourced" in catalog
    )
    if bulk and pool and not pearl_needs_dump_first:
        bulk_hit = _try_bulk_native_pool_spawn(pool, level=level, count=1)
        if bulk_hit:
            return bulk_hit

    if catalog and not skip_verify:
        _prepare_pearl_spawn_context(catalog, pool)

    live_pearl_pool_tried = False

    # Crow / *_pearl: live pool roll first on this build (@U FromSerial often rejects ground).
    if pearl_needs_dump_first and pool and str(pool).lower().endswith("_pearl"):
        live_pearl_pool_tried = True
        live_pool = _named_pearl_live_ncs_pool(catalog, pool) or pool
        from .item_spawn.ncs_pool_spawn import spawn_itempool_names, spawn_legacy_itempool

        spawned, ncs_err = spawn_itempool_names(
            [live_pool],
            count=1,
            level=level,
            require_loot_verify=False,
        )
        if spawned <= 0:
            spawned, ncs_err = spawn_legacy_itempool(
                [live_pool],
                count=1,
                level=level,
            )
        if spawned > 0:
            if catalog and not skip_verify:
                _apply_pearl_customization_for_catalog(catalog)
            _set_pearl_spawn_delivery(
                "ncs_live_pool",
                live_pool,
                loot_verified=True,
            )
            _log_info(f"{label}: pool roll {live_pool}.")
            return spawned
        ncs_miss = ncs_err or ncs_miss

    # Probe whether the FModel/dump inv is loaded (skip when native pool already tried).
    if catalog and not live_pearl_pool_tried:
        try:
            from .item_spawn.inventory_def_ptr import find_live_inventory_def

            probe_handles = _named_pearl_dump_handles(catalog)
            if not probe_handles:
                match = re.match(r"^(.+)_(comp_0[56]_.+)$", catalog)
                if match:
                    root, comp = match.group(1), match.group(2)
                    probe_handles = [
                        f"inv'{root}.{comp}'",
                        f"inv'{root.upper()}.{comp}'",
                    ]
            live_hit = None
            for h in probe_handles[:4]:
                live_hit = find_live_inventory_def(h)
                if live_hit is not None:
                    break
            if live_hit is None:
                ncs_miss = "live_inv:missing (dump/FModel name may not be loaded)"
            else:
                ncs_miss = "live_inv:ok"
        except Exception as probe_exc:
            ncs_miss = f"live_inv:probe_failed:{probe_exc}"

    # Merge inline first — Crow/pearl FModel payloads exist even when live NCS deleted the pool.
    if catalog or pool:
        try:
            from .item_spawn.pearl_comp_spawn import try_spawn_pearl_comp_world

            merge = try_spawn_pearl_comp_world(
                catalog,
                count=1,
                level=level,
                pool_name=pool or None,
                drop_only=True,
                skip_verify=skip_verify,
            )
            if merge.ok:
                if catalog and not skip_verify:
                    _apply_pearl_customization_for_catalog(catalog)
                _set_pearl_spawn_delivery(
                    str(merge.method or "pearl_merge_inline"),
                    catalog or pool,
                    loot_verified=bool(pearl_needs_dump_first or skip_verify),
                )
                _log_info(f"{label}: dump merge inline ({merge.detail}).")
                return 1
            ncs_miss = f"{ncs_miss}; merge:{merge.detail or merge.method}"
        except Exception as merge_exc:
            ncs_miss = f"{ncs_miss}; merge:{merge_exc}"

    handles = _named_pearl_dump_handles(catalog)
    if not handles and catalog:
        # Build inv'ord_ar.comp_05_legendary_crowsourced' when dump index misses.
        match = re.match(r"^(.+)_(comp_0[56]_.+)$", catalog)
        if match:
            root, comp = match.group(1), match.group(2)
            handles = [
                f"inv'{root}.{comp}'",
                f"inv'{root.upper()}.{comp}'",
            ]

    if catalog in _PEARL_ITEMPOOLLIST_CATALOGS and handles:
        from .item_spawn.item_pool_list_spawn import spawn_itempoollist_inv_at_feet

        list_spawned, list_err = spawn_itempoollist_inv_at_feet(
            handles,
            count=1,
            level=level,
            require_loot_verify=not skip_verify,
        )
        if list_spawned > 0:
            _set_pearl_spawn_delivery("dump_itempoollist", handles[0], loot_verified=not skip_verify)
            _log_info(f"{label}: dump ItemPoolList / type pearl {handles[0]}.")
            return list_spawned
        ncs_miss = f"itempoollist:{list_err or 'empty'}"

    if handles:
        from .item_spawn.comp_loot_drop import spawn_inv_handles_at_feet

        inv_spawned, inv_err = spawn_inv_handles_at_feet(
            handles[:2] if skip_verify else handles,
            count=1,
            level=level,
            skip_verify=skip_verify,
        )
        if inv_spawned > 0:
            if catalog and not skip_verify:
                _apply_pearl_customization_for_catalog(catalog)
            _set_pearl_spawn_delivery(
                "dump_inv_def",
                handles[0],
                loot_verified=bool(pearl_needs_dump_first or skip_verify),
            )
            _log_info(f"{label}: dump inv {handles[0]}.")
            return inv_spawned
        ncs_miss = f"{ncs_miss}; dump_inv:{inv_err or 'empty'}"

    # Crow-Sourced Pearl: skip crow-first @U — FromSerial ground fails on many saves; native *_pearl pool is faster.

    live_pool = _named_pearl_live_ncs_pool(catalog, pool)
    if live_pool and not live_pearl_pool_tried:
        from .item_spawn.ncs_pool_spawn import spawn_itempool_names, spawn_legacy_itempool

        spawned, ncs_err = spawn_itempool_names(
            [live_pool],
            count=1,
            level=level,
            require_loot_verify=not skip_verify,
        )
        if spawned <= 0 and not skip_verify:
            spawned, ncs_err = spawn_legacy_itempool(
                [live_pool],
                count=1,
                level=level,
            )
        if spawned > 0:
            if catalog and not skip_verify:
                _apply_pearl_customization_for_catalog(catalog)
            _set_pearl_spawn_delivery(
                "ncs_live_pool",
                live_pool,
                loot_verified=True,
            )
            _log_info(f"{label}: pool roll {live_pool}.")
            return spawned
        ncs_miss = ncs_err or ncs_miss
        if not skip_verify:
            from .item_spawn.item_pool_list_spawn import spawn_live_named_itempool_def

            def_spawned, def_err = spawn_live_named_itempool_def(
                live_pool,
                count=1,
                level=level,
            )
            if def_spawned > 0:
                if catalog:
                    _apply_pearl_customization_for_catalog(catalog)
                _set_pearl_spawn_delivery("live_itempool_def", live_pool, loot_verified=True)
                _log_info(f"{label}: live ItemPoolDef {live_pool}.")
                return def_spawned
            if def_err:
                ncs_miss = f"{ncs_miss}; def:{def_err}"

    if pool and _pool_matches_shiny_intent(pool, True):
        from .item_spawn.ncs_pool_spawn import spawn_itempool_names, spawn_legacy_itempool

        spawned, pool_err = spawn_itempool_names(
            [pool],
            count=1,
            level=level,
            require_loot_verify=not skip_verify,
        )
        if spawned <= 0 and not skip_verify:
            spawned, pool_err = spawn_legacy_itempool(
                [pool],
                count=1,
                level=level,
            )
        if spawned > 0:
            _set_pearl_spawn_delivery(
                "pool_spawn",
                pool,
                loot_verified=True,
            )
            _log_info(f"{label}: shiny pool roll {pool}.")
            return spawned
        if pool_err:
            ncs_miss = f"{ncs_miss}; shiny_pool:{pool_err}"

    # Ground @U — skip dump-first pearls (@U ground fails on many saves).
    if catalog and not pearl_needs_dump_first:
        try:
            serial_hit = _try_catalog_serial_grant(
                catalog,
                {"catalog_key": catalog, "itempool": pool},
                count=1,
                display=label,
            )
            if serial_hit:
                _set_pearl_spawn_delivery(
                    "pearl_serial",
                    catalog,
                    loot_verified=not skip_verify,
                )
                _log_info(f"{label}: ground @U serial.")
                return int(serial_hit)
        except Exception as serial_exc:
            ncs_miss = f"{ncs_miss}; serial:{serial_exc}"

    # Last resort: live pearl pool even when dump-first was preferred (bulk trusted).
    if pearl_needs_dump_first and pool:
        bulk_hit = _try_bulk_native_pool_spawn(pool, level=level, count=1)
        if bulk_hit:
            return bulk_hit

    raise RuntimeError(f"{label}: no dump ground spawn ({ncs_miss})")


def _spawn_generic_pearl_child_dump(child: dict[str, str], *, level: int) -> int:
    """One pearlescent from a generic type-pool child row (dump-first escalation)."""
    catalog = str(child.get("catalog_key") or "").strip().lower()
    pool = str(child.get("itempool") or "").strip()
    title = str(child.get("display_name") or catalog or "pearl").strip()
    return _escalate_pearl_catalog_spawn(catalog, pool, level=level, title=title)


def _spawn_proven_pearl_supplement(
    entry: dict[str, str],
    *,
    level: int,
    count: int = 1,
) -> int:
    """Ground-spawn a Pearl omitted by its generic parent pool.

    These are physical weapons.  Pool Spawner must never silently turn them
    into Reward Center mail; an unavailable ground route is logged as a failure.
    """
    catalog = str(entry.get("catalog_key") or "").strip().lower()
    pool = str(entry.get("itempool") or "").strip()
    total = max(1, min(int(count), MAX_SINGLE_POOL_SPAWN_COUNT))
    if catalog not in _PEARL_PARENT_SUPPLEMENT_CATALOGS:
        raise RuntimeError(f"Not a Pearl parent supplement: {catalog or pool}")
    spawned = 0
    for _ in range(total):
        spawned += _escalate_pearl_catalog_spawn(
            catalog, pool, level=level, title=catalog
        )
    return spawned


def _spawn_generic_pearl_pool_entries(pool: str, level: int, count: int) -> int:
    """
    PS/SG/SM/SR/AR 06 Pearl — direct live NCS on itempool_*_06_pearl first (Squ1ggs pool spawn),
    then named dump children for pearls that need merge/serial/named pools.
    """
    from .item_spawn.comp_spawn_catalog import (
        generic_pearl_pool_spawnable,
        generic_pearl_spawn_targets,
    )

    pool_l = str(pool or "").strip().lower()
    total = max(1, min(int(count), MAX_SINGLE_POOL_SPAWN_COUNT))

    if not generic_pearl_pool_spawnable(pool_l):
        raise RuntimeError(
            _ar_pearl_pool_hint()
            if pool_l == "itempool_ar_06_pearl"
            else f"Not a generic pearl pool: {pool}"
        )

    # Preserve the proven game-native parent-pool behaviour for every count.
    # One x10 request must stay one pool call producing ten drops; expanding it
    # into named comp rows is not valid on this build and silently returns empty.
    direct = _try_direct_generic_pearl_ncs(pool_l, level=level, count=total)
    if direct is not None and direct > 0:
        return direct

    try:
        from .item_spawn.bl4_spawn_delegate import try_bl4_generic_pearl_pool_when_loaded

        bl4_total = try_bl4_generic_pearl_pool_when_loaded(pool_l, count=total, level=level)
        if bl4_total is not None and bl4_total > 0:
            _set_pearl_spawn_delivery("bl4_generic_pearl", pool_l, loot_verified=True)
            _log_info(f"Generic pearl pool {pool_l}: {bl4_total} via BL4 inline expansion.")
            return bl4_total
    except Exception as exc:  # noqa: BLE001
        _log_warning(f"Generic pearl pool {pool_l}: BL4 expansion skipped ({exc})")

    targets = generic_pearl_spawn_targets(pool_l, total)
    if not targets:
        raise RuntimeError(f"No pearlescents mapped to generic pool {pool}.")

    ok = 0
    errors: list[str] = []
    import random

    child_order = list(targets)
    random.shuffle(child_order)
    for child in child_order:
        from .item_spawn.pearl_spawn_ring import bump_ring_index

        bump_ring_index()
        title = str(child.get("display_name") or child.get("catalog_key") or pool_l).strip()
        try:
            hit = _spawn_generic_pearl_child_dump(child, level=level)
            if hit > 0:
                ok += hit
                if total == 1:
                    break
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{title}: {exc}")

    if ok > 0:
        _log_info(f"Generic pearl pool {pool_l}: {ok}/{len(targets)} via dump-first named expansion.")
        return ok

    raise RuntimeError(
        f"Generic pearl pool {pool} failed for all {len(targets)} roll(s). "
        + " | ".join(errors[-4:])
    )


def _spawn_generic_via_item_spawner(pool: str, level: int, count: int) -> int:
    """Native NCS pool path for broad legendary/pearl type pools."""
    from .item_spawn.bl4_spawn_delegate import try_bl4_item_spawner_pool

    bl4_hit = try_bl4_item_spawner_pool(
        pool,
        count=count,
        level=level,
        display_name=pool,
        category="Pearl" if "_06_pearl" in pool.lower() else "Other",
    )
    if bl4_hit is not None:
        return bl4_hit

    if _is_generic_pearl_pool(pool):
        return _spawn_generic_pearl_pool_entries(pool, level, count)

    from .item_spawn.squ1ggs_spawn_bridge import try_ncs_native_for_pool

    hit = try_ncs_native_for_pool(pool, None, count=max(1, int(count)), level=max(1, int(level)))
    if hit.ok:
        _log_info(f"Routed generic rarity pool {pool} through bundled native spawn.")
        return max(1, int(count))

    raise RuntimeError(hit.detail or f"Could not spawn generic pool {pool}")


def _spawn_via_item_spawner_pool(
    pool_or_catalog: str,
    *,
    level: int,
    count: int,
    display: str,
    skip_raid_bridge: bool = True,
) -> int:
    """Bundled pool path: native NCS, raid bridge, then @U serial backup."""
    from .item_spawn.squ1ggs_spawn_bridge import (
        RAID2_CATALOG_KEYS,
        RAID3_CATALOG_KEYS,
        catalog_key_from_pool,
        spawn_raid2_catalog,
        spawn_raid3_catalog,
        try_ncs_native_for_pool,
        try_serial_backup_for_pool,
    )

    token = str(pool_or_catalog or "").strip()
    catalog = catalog_key_from_pool(token, None)
    n = max(1, int(count))
    lvl = max(1, int(level))

    if not skip_raid_bridge and catalog:
        if catalog in RAID2_CATALOG_KEYS:
            hit = spawn_raid2_catalog(catalog, count=n, level=lvl)
            if hit.ok:
                _log_info(f"Routed {display} through bundled Raid 2 bridge.")
                return n
        if catalog in RAID3_CATALOG_KEYS:
            hit = spawn_raid3_catalog(catalog, count=n, level=lvl)
            if hit.ok:
                _log_info(f"Routed {display} through bundled Raid 3 bridge.")
                return n

    hit = try_ncs_native_for_pool(token, None, count=n, level=lvl)
    if hit.ok:
        _log_info(f"Routed {display} through bundled native pool path.")
        return n

    if catalog and _is_pearl_catalog(catalog):
        serial_hit = try_serial_backup_for_pool(token, None, count=n, level=lvl)
        if serial_hit.ok:
            _log_info(f"Routed {display} through bundled pearl @U serial.")
            return n
        if token:
            try:
                pool_hit = spawn_item_pool(token, lvl, n)
                if pool_hit:
                    return pool_hit
            except Exception:  # noqa: BLE001
                pass
        raise RuntimeError(
            serial_hit.detail
            or hit.detail
            or f"comp_06 pearl NCS failed for {display} — use named pool row or generic 06 Pearl tier"
        )

    from .item_spawn.comp_tier import comp_tier_for_catalog

    if catalog:
        tier = comp_tier_for_catalog(catalog, pool_name=token)
        if tier in ("comp_05_legendary", "comp_05_legendary_pearl") and token:
            try:
                pool_hit = spawn_item_pool(token, lvl, n)
                if pool_hit:
                    return pool_hit
            except Exception:  # noqa: BLE001
                pass

    hit = try_serial_backup_for_pool(token, None, count=n, level=lvl)
    if hit.ok:
        _log_info(f"Routed {display} through bundled @U serial backup.")
        return n

    raise RuntimeError(hit.detail or f"Bundled spawn failed for {display}")


def _is_pearl_catalog(catalog: str) -> bool:
    return "_comp_06_pearl_" in str(catalog or "").strip().lower()


def _pearl_live_native_pool_candidates(
    catalog: str,
    entry: dict[str, str] | None = None,
) -> list[str]:
    """Live Nexus aliases only (e.g. Locust) — registered pools even if merge-tagged synthetic."""
    from .item_spawn.pearl_serial_spawn import native_pool_for_catalog
    from .standalone_spawning import RAID2_SPAWN_HINTS, _load_native_pools, _norm_pool_key, _resolve_native_pool

    native_index = _load_native_pools()
    catalog_l = str(catalog or "").strip().lower()
    seen: set[str] = set()
    ordered: list[str] = []

    def add(pool: str | None) -> None:
        raw = str(pool or "").strip()
        if not raw or _is_generic_pearl_pool(raw):
            return
        resolved = _resolve_native_pool(raw, native_index)
        if not resolved or _norm_pool_key(resolved) not in native_index:
            return
        low = resolved.lower()
        if low in seen:
            return
        seen.add(low)
        ordered.append(resolved)

    add(native_pool_for_catalog(catalog_l))
    if entry:
        add(str(entry.get("native_pool") or ""))
        add(str(entry.get("itempool") or ""))
    hints = RAID2_SPAWN_HINTS.get(catalog_l, {}) if isinstance(RAID2_SPAWN_HINTS, dict) else {}
    if isinstance(hints, dict):
        add(str(hints.get("native_pool") or ""))
    return ordered


def _spawn_pearl_catalog_world(
    catalog: str,
    entry: dict[str, str],
    *,
    level: int,
    count: int,
    display: str,
) -> int:
    """Pearl world entry — dump serial first, verified pools (same as pool child rolls)."""
    row = dict(entry)
    catalog_l = str(catalog or row.get("catalog_key") or "").strip().lower()
    if catalog_l:
        row["catalog_key"] = catalog_l
    return _spawn_pearl_child_entry(row, level=level, count=count)


def _try_pearl_world_spawn(
    entry: dict[str, str],
    *,
    count: int = 1,
    display: str = "",
    level: int = DEFAULT_ITEM_LEVEL,
) -> int | None:
    """Retry world spawn for pearl rows — never mail/inbox."""
    display = str(display or entry.get("display_name") or "pearl").strip()
    pool = str(entry.get("itempool") or "").strip().lower()
    catalog = str(entry.get("catalog_key") or "").strip().lower()
    rows: list[dict[str, str]] = []
    if catalog and _is_pearl_catalog(catalog):
        rows.append(dict(entry))
    elif _is_generic_pearl_pool(pool):
        rows.extend(_pearl_child_rows(pool))
    else:
        return None
    last_detail = ""
    for row in rows:
        cat = str(row.get("catalog_key") or "").strip().lower()
        if not cat:
            continue
        try:
            return _spawn_pearl_catalog_world(
                cat,
                row,
                level=level,
                count=max(1, int(count)),
                display=str(row.get("display_name") or display),
            )
        except Exception as exc:  # noqa: BLE001
            last_detail = str(exc)
    if last_detail:
        _log_warning(f"{display}: pearl world retry failed ({last_detail}).")
    return None


def _mark_named_display(entry: dict[str, str]) -> dict[str, str]:
    """Prefix singular rows with tier tag + ASCII '>' (imgui often shows ↳/★ as '?')."""
    from .item_spawn.comp_tier import comp_tier_for_catalog, comp_tier_for_pool, tier_display_name

    name = str(entry.get("display_name", "")).strip()
    pool = str(entry.get("itempool", ""))
    catalog = str(entry.get("catalog_key", "")).strip()
    try:
        from .item_spawn.legendary_dump_manifest import pretty_title_for_catalog_or_pool

        pretty = pretty_title_for_catalog_or_pool(catalog=catalog, pool=pool, fallback="")
        if pretty:
            name = pretty
        elif re.search(r"\b0[56]\s+legendary\b", name, re.I) or re.search(
            r"patch\s*-\s*", name, re.I
        ):
            fallback_pretty = pretty_title_for_catalog_or_pool(
                catalog=catalog, pool=pool, fallback=name
            )
            if fallback_pretty:
                name = fallback_pretty
    except Exception:  # noqa: BLE001
        pass
    tier = comp_tier_for_catalog(catalog, pool_name=pool) if catalog else comp_tier_for_pool(pool)
    if catalog or _looks_like_named_item_pool(pool):
        out = dict(entry)
        out["display_name"] = tier_display_name(
            name or pool or catalog,
            tier,
            catalog_key=catalog,
            pool_name=pool,
        )
        if not str(out["display_name"]).startswith(">"):
            out["display_name"] = f"> {out['display_name']}"
        if tier != "unknown":
            out["comp_tier"] = tier
        if tier in ("comp_06_pearl", "comp_05_legendary_pearl"):
            out["category"] = "Pearl"
        return out
    return entry


def _is_pearl_pool_row(entry: dict[str, str]) -> bool:
    """Pearl tab: type pools + singular named pearlescents (dump NCS)."""
    pool = str(entry.get("itempool", "")).strip().lower()
    catalog = str(entry.get("catalog_key", "")).strip().lower()
    if _is_generic_pearl_pool(pool):
        return True
    if str(entry.get("category", "")).strip().lower() == "pearl":
        return True
    try:
        from .item_spawn.pearlescent_manifest import is_pearlescent_catalog, pearlescent_row_for_pool

        if catalog and is_pearlescent_catalog(catalog):
            return True
        if pearlescent_row_for_pool(pool):
            return True
    except Exception:
        pass
    if "_06_pearl_" in pool or pool.endswith("_pearl"):
        try:
            from .item_spawn.comp_tier import comp_tier_for_catalog

            if catalog and comp_tier_for_catalog(catalog, pool_name=pool) == "comp_05_legendary":
                return False
        except Exception:  # noqa: BLE001
            pass
        return True
    return False


_CATEGORY_UI_ORDER: dict[str, int] = {
    "Assault Rifle": 10,
    "Pistol": 20,
    "SMG": 30,
    "Sniper": 40,
    "Shotgun": 50,
    "Heavy": 60,
    "Class Mod": 70,
    "Enhancement": 80,
    "Shield": 90,
    "Ordnance": 100,
    "Repkit": 110,
    "Ammo": 120,
    "Currency": 130,
    "Other": 140,
    "Shiny": 150,
    "Pearl": 160,
}


def _category_sort_rank(category: str) -> int:
    return _CATEGORY_UI_ORDER.get(str(category or "Other").strip(), 145)


def _pool_filter_sort_key(
    row: dict[str, str],
    *,
    wants_shiny: bool,
    deprioritize_pearls: bool,
) -> tuple:
    is_pearl = _is_pearl_pool_row(row)
    is_child = str(row.get("display_name", "")).strip().startswith(">")
    pool = str(row.get("itempool", "")).lower()
    cat = str(row.get("category", "Other"))

    if deprioritize_pearls and is_pearl:
        return (2, _category_sort_rank(cat), str(row.get("display_name", "")).lower())

    return (
        0 if is_child and not is_pearl else (1 if is_child else 0),
        0 if wants_shiny == ("_shiny" in pool) else 1,
        0 if pool.endswith("_05_legendary") else 1,
        _category_sort_rank(cat),
        str(row.get("display_name", "")).lower(),
    )


def _entry_matches_category(entry: dict[str, str], category: str) -> bool:
    """Category filter — ``Shiny`` also matches ``*_shiny`` pool names regardless of row tag."""
    if category == "All":
        return True
    cat = str(entry.get("category", "Other"))
    pool = str(entry.get("itempool", "")).lower()
    if category == "Shiny":
        return cat == "Shiny" or pool.endswith("_shiny") or "_shiny_" in pool
    if category == "Pearl":
        return _is_pearl_pool_row(entry)
    return cat == category


def _pool_row_is_currency(entry: dict[str, str]) -> bool:
    cat = str(entry.get("category") or "").strip().lower()
    if cat == "currency":
        return True
    blob = (
        f"{entry.get('itempool', '')} {entry.get('display_name', '')} "
        f"{entry.get('catalog_key', '')}"
    ).lower()
    return any(
        tok in blob
        for tok in (
            "currency",
            "cash",
            "money",
            "eridium",
            "bigmoney",
            "nomoney",
            "lootbat_cash",
            "gift_cash",
        )
    )


def _pool_row_is_ai_gun(entry: dict[str, str]) -> bool:
    """Oversized NPC / mech / mounted guns that look wrong in shaped piles."""
    blob = (
        f"{entry.get('itempool', '')} {entry.get('display_name', '')}"
    ).lower()
    markers = (
        "dahlmech",
        "dahlgrunt",
        "brute_",
        "brute ",
        "meathead",
        "soldier_",
        "soldierblighted",
        "facelaser",
        "face_laser",
        "blackmarket_comp_bor_hw",
        "streamer",
        "spiderjumbo",
        "splicespider",
        "chaingun",
        "flamespitter",
        "crashflamer",
        "rocketgun",
        "shoulderlaser",
        "energygun",
        "_emp",
        "flamethrower",
    )
    return any(tok in blob for tok in markers)


def filter_item_pools(
    search: str = "",
    category: str = "All",
    limit: int = 100,
    *,
    exclude_currency: bool = False,
    exclude_ai_guns: bool = False,
) -> list[dict[str, str]]:
    needle = (search or "").strip().lower()
    category = category or "All"
    if category == "Pearl":
        limit = max(limit, 250)
    results: list[dict[str, str]] = []
    seen_pools: set[str] = set()
    by_pool: dict[str, dict[str, str]] = {}

    def append_entry(entry: dict[str, str]) -> bool:
        entry = _mark_named_display(entry)
        if _entry_is_spawn_skippable(entry):
            return False
        if exclude_currency and _pool_row_is_currency(entry):
            return False
        if exclude_ai_guns and _pool_row_is_ai_gun(entry):
            return False
        pool_key = entry.get("itempool", "").strip().lower()
        catalog_key = str(entry.get("catalog_key", "")).strip().lower()
        if (
            "_06_pearl_" in pool_key
            and pool_key.endswith("_shiny")
            and "shiny" not in needle
        ):
            return False
        shiny_bit = "1" if (pool_key.endswith("_shiny") or "_shiny_" in pool_key) else "0"
        dedupe_key = f"{catalog_key}|{shiny_bit}" if catalog_key else pool_key
        if dedupe_key and dedupe_key in seen_pools:
            if not catalog_key:
                existing = by_pool.get(pool_key)
                if existing is not None:
                    cat = str(entry.get("catalog_key", "")).strip()
                    if cat and not str(existing.get("catalog_key", "")).strip():
                        existing["catalog_key"] = cat
                    child_name = str(entry.get("display_name", "")).strip()
                    if child_name.startswith(">") and not str(existing.get("display_name", "")).startswith(">"):
                        existing["display_name"] = child_name
            return False
        if dedupe_key:
            seen_pools.add(dedupe_key)
        if pool_key and not catalog_key:
            by_pool[pool_key] = entry
        results.append(entry)
        return False

    # Pearl tab: type pools + singular named pearlescents (dump NCS).
    pearl_tab = category == "Pearl"
    if pearl_tab or (category == "All" and "pearl" in needle):
        from .item_spawn.pearlescent_manifest import generic_pool_ui_rows, ui_rows_for_pearlescents

        for row in generic_pool_ui_rows():
            if needle and not _pool_search_matches(
                needle, row["display_name"], row["itempool"], row.get("catalog_key", "")
            ):
                continue
            if append_entry(dict(row)):
                return results
        for row in ui_rows_for_pearlescents():
            if needle and not _pool_search_matches(
                needle,
                row["display_name"],
                row["itempool"],
                row.get("catalog_key", ""),
            ):
                continue
            if append_entry(dict(row)):
                return results

    if pearl_tab:
        results.sort(
            key=lambda row: _pool_filter_sort_key(
                row, wants_shiny=False, deprioritize_pearls=False
            )
        )
        return results[:limit] if limit > 0 else results

    # Curated Squ1ggs list first (working pools).
    for entry in load_item_pools():
        if not _entry_matches_category(entry, category):
            continue
        if (
            category == "All"
            and str(entry.get("category", "")).strip().lower() == "pearl"
            and not needle
        ):
            continue
        pool_key = str(entry.get("itempool", "")).strip().lower()
        if _is_generic_pearl_pool(pool_key):
            # Generic pearl tiers (SM/PS/SG/SR 06 Pearl): hidden in default All
            # browse, shown under Pearl/weapon tabs or when searching "pearl".
            if category == "All" and "pearl" not in needle:
                continue
            if not needle or _pool_search_matches(
                needle,
                entry["display_name"],
                entry["itempool"],
                str(entry.get("category") or ""),
            ):
                if append_entry(dict(entry)):
                    return results
            for child in _pearl_child_rows(entry["itempool"]):
                if not _entry_matches_category(child, category):
                    continue
                if needle and not _pool_search_matches(
                    needle,
                    child["display_name"],
                    child["itempool"],
                    child.get("catalog_key", ""),
                    str(child.get("category") or ""),
                ):
                    continue
                if append_entry(child):
                    return results
            continue
        if needle and not _pool_search_matches(
            needle,
            entry["display_name"],
            entry["itempool"],
            str(entry.get("catalog_key") or ""),
            str(entry.get("category") or ""),
        ):
            continue
        if append_entry(dict(entry)):
            return results
        for child in _pearl_child_rows(entry["itempool"]):
            if not _entry_matches_category(child, category):
                continue
            if needle and not _pool_search_matches(
                needle,
                child["display_name"],
                child["itempool"],
                child.get("catalog_key", ""),
            ):
                continue
            if append_entry(child):
                return results

    # Raid catalog rows after curated list (named world-spawn candidates).
    for entry in _raid_catalog_ui_rows():
        if not _entry_matches_category(entry, category):
            continue
        if needle and not _pool_search_matches(
            needle,
            entry.get("display_name", ""),
            entry.get("itempool", ""),
            entry.get("catalog_key", ""),
        ):
            continue
        if append_entry(entry):
            return results
    # Dump named L5s with no dedicated itempool (Draupner, Ichor, …).
    if category != "Pearl":
        from .item_spawn.legendary_dump_manifest import dump_named_legendary_ui_rows

        catalog_from_curated: set[str] = {
            str(row.get("catalog_key") or "").strip().lower()
            for row in results
            if str(row.get("catalog_key") or "").strip()
            and not (
                str(row.get("itempool") or "").strip().lower().endswith("_shiny")
                or "_shiny_" in str(row.get("itempool") or "").strip().lower()
            )
        }
        for entry in dump_named_legendary_ui_rows():
            dump_cat = str(entry.get("catalog_key") or "").strip().lower()
            if dump_cat and dump_cat in catalog_from_curated:
                continue
            if not _entry_matches_category(dict(entry), category):
                continue
            if needle and not _pool_search_matches(
                needle,
                entry.get("display_name", ""),
                entry.get("itempool", ""),
                entry.get("catalog_key", ""),
            ):
                continue
            if append_entry(dict(entry)):
                return results
    # When searching a broad term such as "legendary", show exact/base pools
    # before their noisy *_shiny variants. An explicit "shiny" search still
    # ranks shiny rows first. Default All browse keeps pearl rows at the bottom.
    wants_shiny = "shiny" in needle
    deprioritize_pearls = category == "All" and "pearl" not in needle
    results.sort(
        key=lambda row: _pool_filter_sort_key(
            row,
            wants_shiny=wants_shiny,
            deprioritize_pearls=deprioritize_pearls,
        )
    )
    return results[:limit] if limit > 0 else results


def _pool_name_candidates(pool_name: str) -> list[str]:
    """Try native-store casing first, then original, then lowercase."""
    raw = str(pool_name or "").strip()
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        cand = str(name or "").strip()
        if not cand or cand in seen:
            return
        seen.add(cand)
        out.append(cand)

    try:
        from .standalone_spawning import _load_native_pools, _resolve_native_pool

        add(_resolve_native_pool(raw, _load_native_pools()))
    except Exception:  # noqa: BLE001
        pass
    add(raw)
    add(raw.lower())
    # Strip accidental double itempool_ prefix from bad catalog rows.
    low = raw.lower()
    if low.startswith("itempool_itempool_"):
        fixed = raw[len("itempool_") :] if raw.lower().startswith("itempool_") else raw
        add(fixed)
        add(fixed.lower())
    return out


def _strict_registered_native_pool(pool_name: str) -> str | None:
    """Exact-casing live NCS pool name iff the pool is in ncs_native_itempools.json."""
    raw = str(pool_name or "").strip()
    if not raw:
        return None
    try:
        from .item_spawn.squ1ggs_spawn_bridge import _load_native_pools, _norm_pool_key

        return _load_native_pools().get(_norm_pool_key(raw))
    except Exception:  # noqa: BLE001
        return None


def _try_fast_live_pool_spawn(pool: str, *, level: int, count: int) -> int:
    """Anonymous type pools only: one live SpawnInventoryFromItemPool attempt."""
    name = str(pool or "").strip()
    if not name:
        return 0
    pool_l = name.lower()
    if "_comp_05_" in pool_l or "_comp_06_" in pool_l:
        return 0
    if pool_l in _DUMP_FIRST_NCS_MISSING_POOLS or pool_l in _FAKE_BASE_ITEMPOOLS:
        return 0
    native = _strict_registered_native_pool(name)
    if not native:
        return 0
    from .item_spawn.ncs_pool_spawn import spawn_itempool_names, spawn_legacy_itempool

    spawned = 0
    try:
        spawned, _err = spawn_itempool_names(
            [native],
            count=count,
            level=level,
            require_loot_verify=False,
        )
    except Exception:
        spawned = 0
    if spawned <= 0:
        try:
            spawned, _err = spawn_legacy_itempool([native], count=count, level=level)
        except Exception:
            spawned = 0
    if spawned > 0:
        # Never mark loot_verified — callers must dump-verify named rows.
        _set_pearl_spawn_delivery(
            "pool_spawn",
            native,
            skip_verify=True,
            loot_verified=False,
        )
        return int(spawned)
    return 0


def _is_curated_spawn_all_row(entry: dict[str, str]) -> bool:
    """Legacy named-only predicate — Spawn All Filtered no longer uses this.

    Kept for diagnostics. Shrinking All to L5/shiny/pearl dropped hundreds of
    real pools (ammo/type/manufacturer) that GitHub 3.8.0 still queued.
    """
    cat = str(entry.get("category") or "").strip().lower()
    pool = str(entry.get("itempool") or "").strip().lower()
    display = str(entry.get("display_name") or "").strip().lower()
    if cat in ("shiny", "pearl"):
        return True
    if str(entry.get("catalog_key") or "").strip():
        return True
    if str(entry.get("dump_named_legendary") or "").strip() == "1":
        return True
    if "[l5]" in display or "[pearl]" in display or "[p6]" in display:
        return True
    if "_05_legendary" in pool or "_06_pearl" in pool:
        return True
    if pool.endswith("_shiny") or "_shiny_" in pool or pool.endswith("_pearl"):
        return True
    return False


def _try_bulk_native_pool_spawn(
    pool: str,
    *,
    level: int,
    count: int,
    catalog: str = "",
    wants_shiny: bool = False,
) -> int:
    """Spawn All / Selected: live NCS path (GitHub 3.8.0). Skip dump/pearl escalation."""
    name = str(pool or "").strip()
    if not name or not _BULK_SPAWN_DRAINING:
        return 0
    if "_comp_05_" in name.lower() or "_comp_06_" in name.lower():
        return 0
    from .item_spawn.ncs_pool_spawn import spawn_legacy_itempool

    try_names: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        low = str(raw or "").strip().lower()
        if not low or low in seen:
            return
        seen.add(low)
        try_names.append(str(raw or "").strip())

    add(name)
    cat = str(catalog or "").strip().lower()
    if cat:
        for cand in _native_legendary_pool_candidates(cat, name, wants_shiny=wants_shiny):
            if _pool_matches_shiny_intent(cand, wants_shiny):
                add(cand)
    for cand in try_names:
        if not _pool_matches_shiny_intent(cand, wants_shiny):
            continue
        for native in _pool_name_candidates(cand):
            if not _pool_matches_shiny_intent(native, wants_shiny):
                continue
            try:
                spawned, _err = spawn_legacy_itempool([native], count=count, level=level)
            except Exception:
                spawned = 0
            if spawned > 0:
                _set_pearl_spawn_delivery(
                    "pool_spawn",
                    native,
                    skip_verify=True,
                    loot_verified=False,
                )
                return int(spawned)
    # 3.8.97 fallback: raw UI pool id even when absent from bundled ncs_native_itempools.json.
    raw = str(name or "").strip()
    if raw and raw not in try_names:
        try:
            spawned, _err = spawn_legacy_itempool([raw], count=count, level=level)
        except Exception:
            spawned = 0
        if spawned > 0:
            _set_pearl_spawn_delivery(
                "pool_spawn",
                raw,
                skip_verify=True,
                loot_verified=False,
            )
            return int(spawned)
    return 0


def spawn_item_pool(pool_name: str, level: int = DEFAULT_ITEM_LEVEL, count: int = 1) -> int:
    """Squ1ggs pool spawn: SpawnInventoryFromItemPool near the local player."""
    pool_name = str(pool_name or "").strip()
    if not pool_name:
        raise RuntimeError("No item pool selected.")
    pool_l = pool_name.lower()
    # Synthetic UI ids silent-OK with zero loot — never call NCS on these.
    if "_comp_05_" in pool_l or "_comp_06_" in pool_l:
        raise RuntimeError(
            f"Synthetic pool {pool_name} is not a live NCS row — use dump catalog / live *_05_* id."
        )
    count = max(1, min(int(count), MAX_SINGLE_POOL_SPAWN_COUNT))
    level = max(1, int(level))

    from .item_spawn.ncs_pool_spawn import spawn_legacy_itempool

    # Live registered pools spawn directly via NCS (the proven baseline).
    # Only unregistered/synthetic pools need the BL4 Item Spawner pipeline.
    native_err: str | None = None
    native_name = _strict_registered_native_pool(pool_name)
    if native_name:
        spawned, native_err = spawn_legacy_itempool([native_name], count=count, level=level)
        if spawned > 0:
            if _BULK_SPAWN_DRAINING and bulk_spawn_is_mass():
                _set_pearl_spawn_delivery(
                    "pool_spawn",
                    native_name,
                    skip_verify=True,
                    loot_verified=True,
                )
            _log_info(f"Spawned item pool {native_name} x{count} at level {level} (native NCS).")
            return spawned
        if "pearl" not in native_name.lower():
            _log_warning(
                f"Native pool spawn failed for {native_name} ({native_err}); trying the external pool backend."
            )

    from .item_spawn.bl4_spawn_delegate import try_bl4_item_spawner_pool

    bl4_hit = try_bl4_item_spawner_pool(
        pool_name,
        count=count,
        level=level,
        display_name=pool_name,
        category="Other",
        skip_raid_bridge=False,
    )
    if bl4_hit is not None:
        _log_info(f"Spawned loot pool {pool_name} x{count} via the external pool backend.")
        return bl4_hit

    spawned, err = spawn_legacy_itempool([pool_name], count=count, level=level)
    if spawned > 0:
        _log_info(f"Spawned item pool {pool_name} x{count} at level {level}.")
        return spawned
    raise RuntimeError(
        err or native_err or f"SpawnInventoryFromItemPool failed for '{pool_name}'."
    )


def _spawn_method_trustworthy(method: str) -> bool:
    """Inline/comp/serial spawns often pass without showing in the nearby-loot scan."""
    m = str(method or "").lower()
    if m == "ncs_comp_handle" or m.startswith(("bl4_", "pearl_")):
        return True
    return any(
        tok in m
        for tok in (
            "serial_ground",
            "serial_drop",
            "serial_backup",
            "pearl_serial",
            "shiny_atu",
            "fromserial",
        )
    )


def _spawn_catalog_named(
    catalog: str,
    *,
    level: int,
    count: int,
    display: str,
    wants_shiny: bool = False,
    entry: dict[str, str] | None = None,
) -> int:
    """Singular catalog item: @U serial (Raid 2), native pools, raid bridge, Item Spawner."""
    from .standalone_spawning import (
        RAID2_SPAWN_HINTS,
        RAID3_CATALOG_KEYS,
        catalog_spawn_row,
        native_pool_for_catalog,
        row_for_catalog,
        spawn_native_pool,
        spawn_raid2_catalog,
        spawn_raid3_catalog,
    )
    from .item_spawn.raid2_content import RAID2_CATALOG_KEYS

    catalog_l = str(catalog or "").strip().lower()
    patch_inv_handle = _PATCH_INLINE_INVENTORY_DEFS.get(catalog_l)
    if patch_inv_handle:
        from .item_spawn.comp_loot_drop import spawn_inv_handles_at_feet

        patch_spawned, patch_err = spawn_inv_handles_at_feet(
            [patch_inv_handle],
            count=count,
            level=level,
            skip_verify=_skip_loot_verify(),
        )
        if patch_spawned > 0:
            _set_pearl_spawn_delivery(
                "patch_inline_verified",
                patch_inv_handle,
                loot_verified=True,
            )
            return patch_spawned
        _log_warning(
            f"{display}: patch inline inventory definition failed ({patch_err or 'rejected'})."
        )

    is_pearl = _is_pearl_catalog(catalog_l)
    if is_pearl:
        row = dict(entry or {"catalog_key": catalog_l})
        row["catalog_key"] = catalog_l
        if entry:
            for key in ("itempool", "display_name", "category", "native_pool"):
                if entry.get(key):
                    row[key] = str(entry[key])
        return _spawn_comp06_pearl_named(
            row,
            level=level,
            count=count,
            display=display,
        )

    catalog_serial = _resolve_catalog_serial(catalog_l, entry)
    before_loc, before_keys = _capture_loot_snapshot()

    catalog_row = catalog_spawn_row(catalog_l)

    try:
        from .item_spawn.raid2_content import (  # noqa: PLC0415
            RAID2_SHINY_POOL_OVERRIDES,
            primary_itempool_key_for_catalog as _r2_primary_pool,
        )
    except Exception:  # noqa: BLE001
        RAID2_SHINY_POOL_OVERRIDES = {}
        _r2_primary_pool = None

    # Dedicated item pools → random parts for that named item.
    pool_try: list[str] = []
    seen: set[str] = set()
    for cand in (
        str((entry or {}).get("itempool") or "").strip() or None,
        catalog_row.get("itempool"),
        _r2_primary_pool(catalog, wants_shiny=wants_shiny) if _r2_primary_pool else None,
        RAID2_SHINY_POOL_OVERRIDES.get(catalog) if wants_shiny else None,
        native_pool_for_catalog(catalog),
        (RAID2_SPAWN_HINTS.get(catalog) or {}).get("native_pool"),
        getattr(row_for_catalog(catalog), "native_pool", None),
        catalog_row.get("native_pool"),
    ):
        name = str(cand or "").strip()
        low = name.lower()
        if not name or low in seen or _is_generic_pearl_pool(name):
            continue
        if not _pool_matches_shiny_intent(name, wants_shiny):
            continue
        if wants_shiny and not (low.endswith("_shiny") or "_shiny_" in low):
            shiny = f"{name}_shiny"
            if shiny.lower() not in seen and _pool_matches_shiny_intent(shiny, True):
                seen.add(shiny.lower())
                pool_try.append(shiny)
            continue
        seen.add(low)
        pool_try.append(name)

    # Live NCS pools first (Gomie, Lockjaw, Crow-Sourced, named pearls with pool ids).
    native_hit = _try_catalog_native_pool_spawn(
        pool_try,
        level=level,
        count=count,
        display=display,
        before_loc=before_loc,
        before_keys=before_keys,
    )
    if native_hit is not None:
        return native_hit

    # @U serial when ground/backpack RPCs work (Raid 2 comps without live pools).
    try:
        from .item_spawn.pearl_serial_spawn import serials_for_catalog

        has_serial = bool(catalog_serial or serials_for_catalog(catalog_l))
    except Exception:  # noqa: BLE001
        has_serial = bool(catalog_serial)
    if has_serial:
        serial_hit = _try_catalog_serial_grant(
            catalog_l, entry, count=count, display=display
        )
        if serial_hit is not None:
            return serial_hit

    catalog_serial = catalog_serial or _resolve_catalog_serial(catalog, entry)

    if catalog in RAID3_CATALOG_KEYS:
        result = spawn_raid3_catalog(catalog, count=count, level=level)
    else:
        result = spawn_raid2_catalog(
            catalog, count=count, level=level, wants_shiny=wants_shiny
        )
    if result.ok and (
        _loot_gained_since(before_loc, before_keys)
        or _spawn_method_trustworthy(str(getattr(result, "method", "")))
    ):
        _log_info(f"Spawned {display} via {result.method}.")
        return count

    try:
        pool_key = ""
        try:
            from .item_spawn.raid2_content import (  # noqa: PLC0415
                primary_itempool_key_for_catalog as _r2_primary,
            )
            from .item_spawn.raid3_content import (  # noqa: PLC0415
                primary_itempool_key_for_catalog as _r3_primary,
            )

            pool_key = (
                (_r3_primary(catalog) if catalog in RAID3_CATALOG_KEYS else "")
                or (_r2_primary(catalog, wants_shiny=wants_shiny) if _r2_primary else "")
                or ""
            )
        except Exception:  # noqa: BLE001
            pool_key = ""
        if not pool_key:
            row = row_for_catalog(catalog)
            pool_key = str(getattr(row, "native_pool", "") or "") or f"itempool_{catalog}"
        _spawn_via_item_spawner_pool(
            pool_key,
            level=level,
            count=count,
            display=display,
            skip_raid_bridge=True,
        )
        if _loot_gained_since(before_loc, before_keys):
            return count
        serial_hit = _try_catalog_serial_grant(
            catalog_l, entry, count=count, display=display
        )
        if serial_hit is not None:
            return serial_hit
        raise RuntimeError(
            f"{display}: Loot Pool Spawner returned OK but no nearby loot appeared (silent empty)."
        )
    except Exception as isp_exc:
        if is_pearl:
            raise RuntimeError(
                f"{display}: pearl world spawn failed ({isp_exc}). "
                "Use a named pearl row — items spawn at your feet, not via mail."
            ) from isp_exc
        native_hit = _try_catalog_native_pool_spawn(
            pool_try,
            level=level,
            count=count,
            display=display,
            before_loc=before_loc,
            before_keys=before_keys,
        )
        if native_hit is not None:
            return native_hit
        serial_hit = _try_catalog_serial_grant(
            catalog, entry, count=count, display=display
        )
        if serial_hit is not None:
            return serial_hit
        last_detail = ""
        try:
            last_detail = str(result.detail)
        except Exception:
            last_detail = ""
        raise RuntimeError(
            f"{display}: could not world-spawn. "
            f"Last error: {last_detail}. Loot Pool Spawner: {isp_exc}. "
            f"Logged to Squ1ggsBoostingTools/logs/spawn_failures.log — "
            f"try `ulm spawn_pool <exact_name>` to verify casing."
        ) from isp_exc


def _is_ordnance_catalog(catalog: str, entry: dict[str, str] | None = None) -> bool:
    low = str(catalog or "").strip().lower()
    if "grenade" in low or low.startswith("tor_grenade"):
        return True
    if entry:
        cat = str(entry.get("category", "")).strip().lower()
        if cat in ("ordnance", "grenade", "grenades"):
            return True
        pool = str(entry.get("itempool", "")).strip().lower()
        if "fishgrenade" in pool or pool.startswith("itempool_fishgrenade"):
            return True
    return False


def _accept_singular_world_spawn(catalog: str, *, loot_verified: bool) -> bool:
    if loot_verified:
        return True
    low = str(catalog or "").strip().lower()
    return any(tag in low for tag in ("_shield_", "_hw_", "_heavy", "grenade"))


def _safe_singular_world_spawn(
    catalog: str,
    entry: dict[str, str],
    *,
    level: int,
    count: int,
) -> tuple[bool, str]:
    """Native pool + inline comp only — never merge-expand (prevents Slippy stack overflow)."""
    from .item_spawn.raid3_content import primary_itempool_key_for_catalog as _r3_primary
    from .item_spawn.squ1ggs_spawn_bridge import (
        _try_inline_comp_spawn,
        spawn_native_pool,
    )
    from .standalone_spawning import RAID3_CATALOG_KEYS, native_pool_for_catalog, row_for_catalog

    catalog_l = str(catalog or "").strip().lower()
    last_detail = ""
    primary = ""
    if catalog_l in RAID3_CATALOG_KEYS:
        primary = str(_r3_primary(catalog_l) or "").strip()
    if not primary:
        try:
            primary = str(row_for_catalog(catalog_l).itempool or "").strip()
        except Exception:  # noqa: BLE001
            primary = ""
    if not primary:
        primary = str(entry.get("itempool", "")).strip()

    candidates: list[str] = []
    seen: set[str] = set()
    for cand in _named_pool_candidates(entry):
        key = str(cand or "").strip()
        low = key.lower()
        if not key or low in seen:
            continue
        seen.add(low)
        candidates.append(key)
    for cand in (
        str(entry.get("itempool", "")).strip(),
        str(entry.get("native_pool", "")).strip(),
        native_pool_for_catalog(catalog_l) or "",
        primary,
    ):
        key = str(cand or "").strip()
        low = key.lower()
        if not key or low in seen:
            continue
        seen.add(low)
        candidates.append(key)

    before_loc, before_keys = _capture_loot_snapshot()
    for cand in candidates:
        hit = spawn_native_pool(cand, count=count, level=level)
        if getattr(hit, "ok", False):
            if _accept_singular_world_spawn(
                catalog_l, loot_verified=_loot_gained_since(before_loc, before_keys)
            ):
                return True, str(getattr(hit, "detail", "") or cand)
        last_detail = str(getattr(hit, "detail", "") or last_detail)

    inline = _try_inline_comp_spawn(catalog_l, primary, count, level)
    if inline is not None and inline.ok:
        return True, str(inline.detail or "inline_comp")
    if inline is not None:
        last_detail = str(inline.detail or last_detail)

    return False, last_detail or "no safe world path"


def _spawn_classmod_dedicated(
    catalog: str,
    entry: dict[str, str],
    *,
    level: int,
    count: int,
    display: str,
) -> int:
    """Named single-comp classmods (Subjugator / itempool_classmod_*_05_legendary_NN)."""
    from .item_spawn.bl4_spawn_delegate import try_bl4_item_spawner_entry
    from .item_spawn.classmod_comp_spawn import try_spawn_classmod_comp_world

    catalog_l = str(catalog or "").strip().lower()
    pool = str(entry.get("itempool", "")).strip()
    before_loc, before_keys = _capture_loot_snapshot()

    bl4_hit = try_bl4_item_spawner_entry(
        entry,
        count=count,
        level=level,
        catalog=catalog_l or None,
    )
    if bl4_hit is not None and _loot_gained_since(before_loc, before_keys):
        _log_info(f"Spawned {display} via the external pool backend.")
        return bl4_hit

    hit = try_spawn_classmod_comp_world(
        catalog_l, count=count, level=level, pool_name=pool or None
    )
    if hit.ok:
        _log_info(f"Spawned {display} via {hit.method} ({hit.detail}).")
        return count

    # Loot-verified native call only — synthetic classmod pools silent-empty on
    # this build and the BL4 pipeline reports false OKs for them.
    candidates = _pool_name_candidates(pool)
    if candidates:
        from .item_spawn.ncs_pool_spawn import spawn_itempool_names

        spawned, _pool_err = spawn_itempool_names(candidates, count=count, level=level)
        if spawned > 0:
            _log_info(f"Spawned {display} via native pool (verified).")
            return spawned

    catalog_serial = _resolve_catalog_serial(catalog_l, entry)
    if catalog_serial:
        from .item_spawn.pearl_serial_spawn import try_deliver_serial

        if try_deliver_serial(catalog_serial, count):
            _log_info(f"Spawned {display} via serial backpack fallback.")
            return count

    raise RuntimeError(
        hit.detail or f"{display}: dedicated class mod spawn failed (inline/native/serial)"
    )


def _spawn_singular_catalog_row(
    catalog: str,
    entry: dict[str, str],
    *,
    level: int,
    count: int,
    display: str,
    wants_shiny: bool = False,
) -> int:
    """Named raid/catalog rows — world spawn with part rolls, then @U serial if needed."""
    catalog_l = str(catalog or "").strip().lower()
    if _is_generic_subjugator_classmod(catalog_l):
        return _spawn_classmod_dedicated(catalog_l, entry, level=level, count=count, display=display)

    catalog_serial = _resolve_catalog_serial(catalog_l, entry)

    if _is_ordnance_catalog(catalog_l, entry):
        ok, last_detail = _safe_singular_world_spawn(
            catalog_l, entry, level=level, count=count
        )
        if ok:
            return count
        raise RuntimeError(f"{display}: ordnance spawn failed ({last_detail or 'no path'})")

    try:
        return _spawn_catalog_named(
            catalog,
            level=level,
            count=count,
            display=display,
            wants_shiny=wants_shiny,
            entry=entry,
        )
    except RuntimeError as exc:
        if _is_pearl_catalog(catalog_l):
            raise
        pool_from_entry = str(entry.get("itempool") or "").strip()
        pool_candidates = [pool_from_entry] if pool_from_entry else []
        before_loc, before_keys = _capture_loot_snapshot()
        native_hit = _try_catalog_native_pool_spawn(
            pool_candidates,
            level=level,
            count=count,
            display=display,
            before_loc=before_loc,
            before_keys=before_keys,
        )
        if native_hit is not None:
            return native_hit
        serial_hit = _try_catalog_serial_grant(
            catalog_l, entry, count=count, display=display
        )
        if serial_hit is not None:
            return serial_hit
        raise exc


def spawn_item_pool_entry(
    entry: dict[str, str],
    level: int = DEFAULT_ITEM_LEVEL,
    count: int = 1,
) -> int:
    """Spawn one UI row; OK/FAIL recorded after deferred feet-loot verify on PlayerTick."""
    _clear_pearl_spawn_delivery()
    entry = _normalize_spawn_all_entry(entry)
    catalog = str(entry.get("catalog_key", "")).strip().lower()
    pool = str(entry.get("itempool", "")).strip()
    display = str(entry.get("display_name", pool or catalog)).strip() or (pool or catalog)
    method = "classmod_spawn" if _is_classmod_entry(entry, catalog) else "pool_spawn"
    wants_shiny_row = _wants_shiny_spawn(pool=pool, display=display, entry=entry)

    # Bulk: keep the full NCS → native → BL4 → serial → merge chain. Only skip
    # the hitchy find_all verify between items — do not short-circuit on NCS RPC.
    verify_loot = not _BULK_SPAWN_DRAINING
    if _BULK_SPAWN_DRAINING and _is_generic_pearl_pool(pool):
        verify_loot = False
    if verify_loot and _SPAWN_VERIFY_QUEUE and not _BULK_SPAWN_DRAINING:
        raise RuntimeError(
            f"{display}: previous ground spawn is still being verified; retry in a moment."
        )
    exact_ncs_probe = str(entry.get("pearl_supplement") or "").strip() == "1"
    before_loc, before_keys = (
        _capture_loot_snapshot(force_scan=exact_ncs_probe)
        if verify_loot
        else (None, None)
    )
    try:
        spawned = _spawn_item_pool_entry_impl(entry, level=level, count=count)
    except Exception as exc:
        if not _BULK_SPAWN_DRAINING:
            record_spawn_result(
                entry,
                ok=False,
                method="error",
                detail=str(exc),
                count=count,
                level=level,
            )
        raise
    delivery = _pearl_spawn_delivery_info()
    pearl_row = str(entry.get("category", "")).strip().lower() == "pearl" or (
        catalog and _is_pearl_catalog(catalog)
    )
    if delivery.get("loot_verified") == "1" or delivery.get("skip_verify") == "1":
        verify_loot = False
        if delivery.get("loot_verified") == "1":
            _claim_loot_since(before_loc, before_keys)
    elif pearl_row and not _BULK_SPAWN_DRAINING:
        verify_loot = True
    elif wants_shiny_row and _is_wrong_family_shiny_pool(pool):
        # Always feet-verify Burrow-style rows — NCS twin lies about success.
        verify_loot = True
    elif delivery.get("skip_verify") == "1" or delivery.get("loot_verified") == "1":
        verify_loot = False
    # Bulk dump path: never find_all-scan between spawns. That was the hitch.
    if _BULK_SPAWN_DRAINING:
        verify_loot = False
    ok_method = delivery.get("method") or method
    ok_detail = delivery.get("detail") or delivery.get("method") or f"spawned x{spawned}"
    if _BULK_SPAWN_DRAINING:
        # Caller (Spawn All Filtered) counts OK only after a new pickup appears.
        return spawned
    if verify_loot:
        _enqueue_spawn_verify(
            entry=entry,
            level=level,
            count=count,
            before_loc=before_loc,
            before_keys=before_keys,
            spawned=spawned,
            method=str(ok_method),
            detail=str(ok_detail),
            display=display,
            from_bulk=False,
        )
        return spawned
    record_spawn_result(
        entry,
        ok=True,
        method=str(ok_method),
        detail=str(ok_detail),
        count=count,
        level=level,
    )
    return spawned


def _spawn_item_pool_entry_impl(
    entry: dict[str, str],
    level: int = DEFAULT_ITEM_LEVEL,
    count: int = 1,
) -> int:
    """Spawn one UI row (internal — see spawn_item_pool_entry for logging)."""
    entry = _ensure_entry_catalog(entry)
    quarantine_reason = _crash_quarantine_reason(entry)
    if quarantine_reason:
        safe_spawned = _spawn_crash_safe_serial(entry, count, level=level)
        if safe_spawned is not None:
            return safe_spawned
        raise RuntimeError(f"Blocked before Unreal call: {quarantine_reason}")
    entry = _rewrite_pearl_pool_entry(entry)
    pool = str(entry.get("itempool", "")).strip()
    catalog = str(entry.get("catalog_key", "")).strip().lower()
    display = str(entry.get("display_name", pool or catalog)).strip() or (pool or catalog)
    wants_shiny = _wants_shiny_spawn(pool=pool, display=display, entry=entry)
    pool = _resolve_catalog_spawn_pool(catalog, pool, wants_shiny=wants_shiny)
    # UI sometimes stores synthetic itempool_*_comp_05_* ids. Live NCS uses
    # itempool_*_05_legendary_* (no "comp"). Prefer real candidates so heavies
    # / L5 named rows don't silent-OK an empty fake pool.
    if catalog and ("_comp_05_" in pool.lower() or "_comp_06_" in pool.lower() or not pool):
        for cand in _native_legendary_pool_candidates(
            catalog, pool, wants_shiny=wants_shiny
        ):
            if not _pool_matches_shiny_intent(cand, wants_shiny):
                continue
            pool = cand
            break
    if pool:
        entry["itempool"] = pool
    pool_l = pool.lower()
    wants_shiny = _wants_shiny_spawn(pool=pool, display=display, entry=entry)

    # Prefer a live registered NCS twin when the UI row is synthetic / base-only
    # (dump often has only *_shiny). Honor shiny intent — never force shiny on
    # All / weapon-tab Spawn All Filtered rows stamped _spawn_shiny=0.
    if catalog and pool and not _strict_registered_native_pool(pool):
        for cand in _native_legendary_pool_candidates(
            catalog, pool, wants_shiny=wants_shiny
        ):
            if not _pool_matches_shiny_intent(cand, wants_shiny):
                continue
            if _strict_registered_native_pool(cand):
                pool = cand
                entry["itempool"] = pool
                pool_l = pool.lower()
                wants_shiny = _wants_shiny_spawn(pool=pool, display=display, entry=entry)
                break

    # Loot-tab named legendaries (no shiny prefix): dump inv'ROOT.comp_* only — never
    # *_shiny pools (phosphene). Shiny tab + pearls + mixed 05 pools stay on NCS.
    named_unique_base = _is_named_unique_legendary_row(entry, wants_shiny=False)
    if named_unique_base and catalog and not wants_shiny:
        dump_hit = _spawn_named_l5_dump_inv(
            entry,
            catalog=catalog,
            pool=pool,
            display=display,
            count=count,
            level=level,
            skip_pool=not _spawn_named_l5_bulk_mode(),
        )
        if dump_hit:
            return dump_hit
        if _spawn_named_l5_bulk_mode():
            raise RuntimeError(
                f"{display}: named pool + NCS twin missed (catalog={catalog})."
            )
        return _named_unique_base_after_dump_miss(
            entry,
            catalog=catalog,
            display=display,
            count=count,
            level=level,
        )

    # Test Singular path kept for command stub only — prefer dump before silent NCS.
    if (
        _SINGULAR_PATH_TEST
        and catalog
        and "_comp_05_legendary_" in catalog
        and (
            not wants_shiny
            or catalog in _PATCH_INLINE_INVENTORY_DEFS
            or _is_wrong_family_shiny_pool(pool)
        )
    ):
        lean_hit = _spawn_named_legendary_lean(
            entry,
            catalog=catalog,
            pool=pool,
            display=display,
            count=count,
            level=level,
            wants_shiny=wants_shiny,
        )
        if lean_hit is not None and lean_hit > 0:
            return int(lean_hit)
        return _spawn_proven_catalog_ground(
            catalog,
            count=count,
            level=level,
            display=display,
            pool=pool,
            prefer_serial=True,
            wants_shiny=wants_shiny,
        )

    # NCS dump-only / fake base pools: never SpawnInventoryFromItemPool on missing rows.
    # Roil = BOR_SM SMG parts; Rainmaker = bor_sr sniper parts. Live NCS only has
    # mal_sg *_shiny twins — those silent-empty when stripped or cosmetics miss.
    # Dump the correct inv first (part locks intact), then shiny pool / @U.
    # Midnight non-shiny: NOT dump-only — base dump inv via Selected lean / proven
    # (forcing shiny here is why Selected only dropped shinies).
    if not catalog:
        catalog = _patch_inline_catalog_from_pool(pool) or _catalog_key_from_itempool(pool)
        if catalog:
            entry["catalog_key"] = catalog
    midnight_base = (
        catalog == "vla_sr_comp_05_legendary_crowdsourced" and not wants_shiny
    )
    fake_or_dump_only = (
        (pool_l in _FAKE_BASE_ITEMPOOLS and not midnight_base)
        or catalog in _NCS_DUMP_ONLY_INVS
    )
    if fake_or_dump_only:
        if not catalog:
            if "burrow" in pool_l:
                catalog = "jak_sr_comp_05_legendary_burrow"
            elif "roil" in pool_l:
                catalog = "bor_sm_comp_05_legendary_roil"
            elif "rainmaker" in pool_l:
                catalog = "bor_sr_comp_05_legendary_rainmaker"
            elif "crowdsourced" in pool_l or "midnight" in display.lower():
                catalog = "vla_sr_comp_05_legendary_crowdsourced"
        if catalog:
            entry["catalog_key"] = catalog
        native_pool = str(_DUMP_CATALOG_NATIVE_POOLS.get(catalog) or "").strip()
        if native_pool and wants_shiny:
            entry["itempool"] = native_pool
            pool = native_pool
            pool_l = pool.lower()
        if catalog:
            # Proven raises on total miss — catch so shiny/live + @U below can run.
            try:
                dump_hit = _spawn_proven_catalog_ground(
                    catalog,
                    count=count,
                    level=level,
                    display=display,
                    pool=pool if wants_shiny else "",
                    prefer_serial=True,
                    wants_shiny=wants_shiny,
                    allow_native=False,
                )
            except RuntimeError:
                dump_hit = 0
            if dump_hit > 0:
                return int(dump_hit)
        # Live native *_shiny when known. Roil/Rainmaker always; Midnight only if shiny.
        if native_pool and (
            wants_shiny or catalog in _FORCE_SHINY_NATIVE_CATALOGS
        ):
            hit = _try_fast_pearl_named_pool(
                native_pool, catalog, level=level, count=count
            )
            if hit:
                return hit
        serial_hit = _try_curated_dump_serial(entry, count=count, display=display)
        if serial_hit is not None:
            return serial_hit
        dump_serial = str(_DUMP_ONLY_GROUND_SERIALS.get(catalog) or "").strip()
        if dump_serial:
            try:
                return _deliver_catalog_serial_ground_only(
                    dump_serial, count, display
                )
            except Exception:  # noqa: BLE001
                pass
        if catalog:
            return _spawn_proven_catalog_ground(
                catalog,
                count=count,
                level=level,
                display=display,
                pool=pool,
                prefer_serial=True,
                wants_shiny=wants_shiny,
                allow_native=False,
            )
        raise RuntimeError(
            f"{display}: dump-only catalog has no inv / serial "
            f"(pool={pool or 'none'})"
        )

    serial_hit = _try_curated_dump_serial(entry, count=count, display=display)
    if serial_hit is not None:
        return serial_hit

    if not catalog and pool_l:
        catalog = str(entry.get("catalog_key") or "").strip().lower()
    # Solo shiny dump — Spawn All uses live NCS first (GitHub 3.8.0).
    if wants_shiny and pool and not _BULK_SPAWN_DRAINING:
        dumped = _try_shiny_dump_world(
            pool,
            count=count,
            level=level,
            display=display,
            catalog=catalog,
        )
        if dumped:
            return dumped
        if _is_wrong_family_shiny_pool(pool):
            cat = catalog or _catalog_key_from_itempool(pool)
            if cat:
                return _spawn_proven_catalog_ground(
                    cat,
                    count=count,
                    level=level,
                    display=display,
                    pool=pool,
                    prefer_serial=True,
                )
            raise RuntimeError(
                f"{display}: blocked wrong-family shiny pool "
                f"({pool}) — no catalog dump (would spawn Fearstalker)."
            )

    # Dedicated single-comp classmods (incl. Loveless / Raid2) — merge inline BEFORE
    # bulk NCS. Fake pool ids like itempool_classmod_corpohacker_05_legendary_raid2
    # are not live NCS rows; silent RPC "ok" + lag with zero loot.
    from .item_spawn.classmod_comp_spawn import (
        is_dedicated_classmod_catalog,
        is_dedicated_classmod_inline_pool,
        is_native_roll_classmod_pool,
    )

    if not catalog and pool:
        catalog = _catalog_key_from_itempool(pool)
        if catalog:
            entry["catalog_key"] = catalog
    if catalog and _is_generic_subjugator_classmod(catalog):
        return _spawn_classmod_dedicated(catalog, entry, level=level, count=count, display=display)
    if catalog and is_dedicated_classmod_catalog(catalog):
        return _spawn_classmod_dedicated(catalog, entry, level=level, count=count, display=display)
    if pool and is_dedicated_classmod_inline_pool(pool):
        return _spawn_classmod_dedicated(
            catalog or _catalog_key_from_itempool(pool),
            entry,
            level=level,
            count=count,
            display=display,
        )

    # Named uniques: dump-only above — skip live pool (silent RPC / shiny twin).
    bulk_hit = 0
    if (
        _BULK_SPAWN_DRAINING
        and pool
        and not _SINGULAR_PATH_TEST
        and not (named_unique_base and not wants_shiny)
        and "_comp_05_" not in pool_l
        and "_comp_06_" not in pool_l
        and not is_dedicated_classmod_inline_pool(pool)
    ):
        if wants_shiny and not _is_wrong_family_shiny_pool(pool) and not bulk_spawn_is_mass():
            try:
                from .item_spawn.shiny_pearl_spawn import prepare_shiny_pool_context

                prepare_shiny_pool_context(pool)
            except Exception:  # noqa: BLE001
                pass
        bulk_hit = _try_bulk_native_pool_spawn(
            pool,
            level=level,
            count=count,
            catalog=catalog,
            wants_shiny=wants_shiny,
        )
    if bulk_hit:
        if wants_shiny and not bulk_spawn_is_mass():
            try:
                from .item_spawn.shiny_pearl_spawn import _apply_shiny_customization_for_pool

                _apply_shiny_customization_for_pool(pool)
            except Exception:  # noqa: BLE001
                pass
        return bulk_hit

    from .item_spawn.pearlescent_manifest import is_pearlescent_catalog, pearlescent_row

    if str(entry.get("pearl_supplement") or "").strip() == "1" and not (
        catalog and is_pearlescent_catalog(catalog)
    ):
        return _spawn_proven_pearl_supplement(
            entry,
            level=level,
            count=count,
        )

    # (subjugator / dedicated already handled above)

    from .item_spawn.comp_tier import (
        comp_tier_for_catalog,
        comp_tier_for_pool,
        is_invalid_ar_pearl_pool,
    )

    tier = comp_tier_for_catalog(catalog, pool_name=pool) if catalog else comp_tier_for_pool(pool)

    if catalog and is_pearlescent_catalog(catalog):
        manifest = pearlescent_row(catalog)
        row = dict(entry)
        if manifest:
            row["catalog_key"] = catalog
            m_pool = str(manifest.get("itempool") or "").strip()
            # UI sometimes queues Burrow_shiny for non-shiny PRISM (Fearstalker twin).
            if m_pool and not wants_shiny and (
                _is_wrong_family_shiny_pool(pool)
                or (
                    pool_l.endswith("_shiny")
                    and (
                        "burrow" in pool_l
                        or str(manifest.get("comp_class") or "") == "pearl_world"
                    )
                )
            ):
                row["itempool"] = m_pool
                pool = m_pool
                pool_l = pool.lower()
                entry["itempool"] = m_pool
            else:
                row["itempool"] = manifest["itempool"]
        return _spawn_pearl_child_entry(row, level=level, count=count)

    # Patch ItemPoolList exports (Abyss, Gomie, Temper, Burrow, …): proven dump/@U,
    # then live NCS base pool (never Burrow_shiny → Fearstalker).
    if catalog and catalog in _PATCH_INLINE_INVENTORY_DEFS and not wants_shiny:
        try:
            return _spawn_proven_catalog_ground(
                catalog,
                count=count,
                level=level,
                display=display,
                pool=pool,
                prefer_serial=True,
            )
        except RuntimeError:
            manifest_pool = ""
            try:
                from .item_spawn.pearlescent_manifest import pearlescent_row

                row_m = pearlescent_row(catalog)
                if row_m:
                    manifest_pool = str(row_m.get("itempool") or "").strip()
            except Exception:  # noqa: BLE001
                manifest_pool = ""
            for cand in (
                manifest_pool,
                pool,
                *_native_legendary_pool_candidates(catalog, pool),
            ):
                cand_s = str(cand or "").strip()
                if not cand_s.lower().startswith("itempool_"):
                    continue
                if _is_wrong_family_shiny_pool(cand_s):
                    continue
                if cand_s.lower().endswith("_shiny"):
                    continue
                hit = _try_fast_pearl_named_pool(
                    cand_s, catalog, level=level, count=count
                )
                if hit:
                    return hit
            raise
    if wants_shiny and (
        _is_wrong_family_shiny_pool(pool)
        or (catalog and catalog in _PATCH_INLINE_INVENTORY_DEFS)
    ):
        if not catalog:
            catalog = _catalog_key_from_itempool(pool) or catalog
        if catalog:
            return _spawn_proven_catalog_ground(
                catalog,
                count=count,
                level=level,
                display=display,
                pool=pool,
                prefer_serial=True,
            )

    # Dump-named / explicit dump_inv / Raid3 dump-first: ISP-style lean path.
    # Named L5 weapon-tab rows use dump inv above — skip lean here.
    named_unique_base = _is_named_unique_legendary_row(entry, wants_shiny=False)
    if not wants_shiny and not named_unique_base and (
        str(entry.get("dump_named_legendary") or "").strip() == "1"
        or str(entry.get("dump_inv") or "").strip()
        or _pool_needs_dump_first(pool, catalog)
    ):
        lean_hit = _spawn_named_legendary_lean(
            entry,
            catalog=catalog,
            pool=pool,
            display=display,
            count=count,
            level=level,
            wants_shiny=False,
        )
        if lean_hit is not None and lean_hit > 0:
            return int(lean_hit)
        native_pools = _native_legendary_pool_candidates(catalog, pool)
        if str(entry.get("dump_named_legendary") or "").strip() == "1" and not native_pools:
            raise RuntimeError(
                f"{display}: dump inv / serial failed — no ground loot "
                f"(DLC package unloaded or no curated @U)."
            )
        # Live pool row: fall through to normal pool spawn below.
    if is_invalid_ar_pearl_pool(pool):
        raise RuntimeError(_ar_pearl_pool_hint())

    # comp_05 legendary pearl tier — also in manifest; keep for curated list rows without manifest hit.
    if tier == "comp_05_legendary_pearl":
        if not catalog:
            catalog = _resolve_pearl_catalog_from_pool(pool)
        row = dict(entry)
        if catalog:
            row["catalog_key"] = catalog
        if catalog and is_pearlescent_catalog(catalog):
            return _spawn_pearl_child_entry(row, level=level, count=count)
        return _spawn_ncs_first_named(
            row,
            level=level,
            count=count,
            display=display,
            wants_shiny=wants_shiny,
        )

    # comp_06 named — manifest or curated list.
    if tier == "comp_06_pearl" and not _is_generic_pearl_pool(pool):
        row = dict(entry)
        if catalog:
            row["catalog_key"] = catalog
        if catalog and is_pearlescent_catalog(catalog):
            return _spawn_pearl_child_entry(row, level=level, count=count)
        return _spawn_comp06_pearl_named(
            row,
            level=level,
            count=count,
            display=display,
        )

    # Raid-2 comp_05 legendaries (Gomie, Lockjaw, Abyss, …) — NOT pearls despite serial file name.
    if tier == "comp_05_legendary" and catalog:
        row = dict(entry)
        row["catalog_key"] = catalog
        return _spawn_ncs_first_named(
            row,
            level=level,
            count=count,
            display=display,
            wants_shiny=wants_shiny,
        )

    # Generic pearl tiers only — named comp_06 handled above.
    is_pearl_row = _is_generic_pearl_pool(pool)

    # Live registered NCS pools spawn directly via SpawnInventoryFromItemPool.
    # Never for *_shiny or fake base pools missing from Nexus itempool shards.
    native_name = _strict_registered_native_pool(pool)
    if (
        native_name
        and not wants_shiny
        and pool_l not in _FAKE_BASE_ITEMPOOLS
        and not is_pearl_row
        and (_is_classmod_pool(pool) or not _is_generic_rarity_type_pool(pool))
    ):
        try:
            return spawn_item_pool(native_name, level, count)
        except Exception as native_exc:  # noqa: BLE001
            _log_warning(f"{display}: native NCS spawn failed ({native_exc}); trying fallbacks.")

    if is_pearl_row:
        return _spawn_generic_pearl_pool_entries(pool, level, count)

    before_loc, before_keys = _capture_loot_snapshot()
    from .item_spawn.bl4_spawn_delegate import try_bl4_item_spawner_entry

    bl4_hit = try_bl4_item_spawner_entry(
        entry,
        count=count,
        level=level,
        catalog=catalog,
    )
    if bl4_hit is not None:
        if _is_classmod_entry(entry, catalog) and not _loot_gained_since(before_loc, before_keys):
            _log_warning(
                f"{display}: Loot Pool Spawner reported OK but no class mod at feet — trying native pool."
            )
        else:
            _log_info(f"Spawned {display} via the external pool backend.")
            return bl4_hit

    if pool and is_native_roll_classmod_pool(pool):
        try:
            return spawn_item_pool(pool, level, count)
        except Exception as native_exc:  # noqa: BLE001
            try:
                return _spawn_via_item_spawner_pool(
                    pool,
                    level=level,
                    count=count,
                    display=display,
                    skip_raid_bridge=True,
                )
            except Exception as bundled_exc:  # noqa: BLE001
                raise RuntimeError(
                    f"{display}: class mod native failed ({native_exc}); bundled ({bundled_exc})"
                ) from bundled_exc

    try:
        if catalog:
            row = dict(entry)
            row["catalog_key"] = catalog
            return _spawn_singular_catalog_row(
                catalog,
                row,
                level=level,
                count=count,
                display=display,
                wants_shiny=wants_shiny,
            )

        # Exact *_shiny itempool: dump inv_handle first (NCS pool is often silent-empty).
        if pool_l.endswith("_shiny") or "_shiny_" in pool_l:
            try:
                from .item_spawn.shiny_pearl_spawn import spawn_shiny_from_dump

                dumped, dump_err, dump_method = spawn_shiny_from_dump(
                    pool, count=count, level=level, catalog=catalog
                )
                if dumped > 0:
                    method = str(dump_method or "dump_serial_ground").strip() or "dump_serial_ground"
                    _set_pearl_spawn_delivery(
                        method,
                        pool,
                        loot_verified=True,
                    )
                    return dumped
                if dump_err:
                    _log_warning(f"{display}: dump inv spawn missed ({dump_err}); trying NCS pool.")
            except Exception as dump_exc:  # noqa: BLE001
                _log_warning(f"{display}: dump inv spawn failed ({dump_exc}); trying NCS pool.")
            try:
                return spawn_item_pool(pool, level, count)
            except Exception as pool_exc:  # noqa: BLE001
                _log_warning(f"{display}: shiny pool failed ({pool_exc}); trying Loot Pool Spawner.")
            try:
                return _spawn_via_item_spawner_pool(
                    pool,
                    level=level,
                    count=count,
                    display=display,
                    skip_raid_bridge=True,
                )
            except Exception as shiny_exc:  # noqa: BLE001
                if not catalog:
                    raise
                _log_warning(f"{display}: Loot Pool Spawner shiny failed ({shiny_exc}); trying catalog.")

        if pool:
            if _is_generic_pearl_pool(pool):
                return _spawn_generic_pearl_pool_entries(pool, level, count)
            if _is_generic_rarity_type_pool(pool):
                return _spawn_generic_via_item_spawner(pool, level, count)
            if _is_classmod_pool(pool) and is_native_roll_classmod_pool(pool):
                try:
                    return spawn_item_pool(pool, level, count)
                except Exception as class_exc:  # noqa: BLE001
                    return _spawn_via_item_spawner_pool(
                        pool,
                        level=level,
                        count=count,
                        display=display,
                        skip_raid_bridge=True,
                    )
            try:
                return spawn_item_pool(pool, level, count)
            except Exception as pool_exc:  # noqa: BLE001
                if _looks_like_named_item_pool(pool):
                    try:
                        return _spawn_via_item_spawner_pool(
                            pool,
                            level=level,
                            count=count,
                            display=display,
                            skip_raid_bridge=True,
                        )
                    except Exception:
                        pass
                # Event loot / airship / silent-empty legendaries → F1 expand path.
                try:
                    return _spawn_via_item_spawner_pool(
                        pool,
                        level=level,
                        count=count,
                        display=display,
                        skip_raid_bridge=True,
                    )
                except Exception as isp_exc:  # noqa: BLE001
                    raise RuntimeError(
                        f"{display}: item pool failed ({pool_exc}); "
                        f"Loot Pool Spawner fallback failed ({isp_exc})"
                    ) from isp_exc

        raise RuntimeError(f"{display}: no itempool or catalog_key on row")
    except Exception as exc:  # noqa: BLE001
        raise


def _stamp_spawn_shiny_intent(row: dict[str, str]) -> None:
    """Explicit shiny vs normal legendary — Spawn Selected never inferred this before."""
    if str(row.get("_spawn_shiny") or "").strip() in ("0", "1"):
        return
    pool_l = str(row.get("itempool") or "").strip().lower()
    category_l = str(row.get("category") or "").strip().lower()
    display_l = str(row.get("display_name") or "").strip().lower()
    if category_l == "shiny" or pool_l.endswith("_shiny") or "_shiny_" in pool_l:
        row["_spawn_shiny"] = "1"
    elif category_l and category_l != "shiny":
        row["_spawn_shiny"] = "0"
    elif re.search(r"\bshiny\b", display_l):
        row["_spawn_shiny"] = "1"
    else:
        row["_spawn_shiny"] = "0"


def _normalize_spawn_all_entry(entry: dict[str, str]) -> dict[str, str]:
    """Resolve catalog + live pool ids before Spawn All / Spawn Selected queues a row."""
    row = _rewrite_pearl_pool_entry(_ensure_entry_catalog(dict(entry)))
    _stamp_spawn_shiny_intent(row)
    pool = str(row.get("itempool") or "").strip()
    catalog = str(row.get("catalog_key") or "").strip().lower()
    display = str(row.get("display_name") or "").strip()
    wants_shiny_row = _wants_shiny_spawn(pool=pool, display=display, entry=row)
    pool = _resolve_catalog_spawn_pool(catalog, pool, wants_shiny=wants_shiny_row)
    pool_l = pool.lower()
    # UI rows sometimes store itempool_JAK_sg_… — live NCS ids are lowercase.
    if pool and pool_l.startswith("itempool_") and pool != pool_l:
        reg = _strict_registered_native_pool(pool_l) or pool_l
        if reg:
            pool = reg
            pool_l = pool.lower()
    wants_shiny_row = _wants_shiny_spawn(pool=pool, display=display, entry=row)
    if catalog and (
        "_comp_05_" in pool_l or "_comp_06_" in pool_l or not pool
    ):
        for cand in _native_legendary_pool_candidates(
            catalog, pool, wants_shiny=wants_shiny_row
        ):
            if not _pool_matches_shiny_intent(cand, wants_shiny_row):
                continue
            pool = cand
            pool_l = pool.lower()
            break
    # Only remap to a live *_shiny twin when this row is meant to be shiny.
    # Spawn All on All / weapon tabs stamps _spawn_shiny=0 so named L5s dump
    # as normal legendaries instead of being rewritten onto shiny pools.
    if wants_shiny_row and catalog and pool and not _strict_registered_native_pool(pool):
        for cand in _native_legendary_pool_candidates(
            catalog, pool, wants_shiny=True
        ):
            if _strict_registered_native_pool(cand):
                pool = cand
                pool_l = pool.lower()
                break
    if pool:
        row["itempool"] = pool
    if catalog:
        row["catalog_key"] = catalog
    display = str(row.get("display_name") or "").strip()
    if _wants_shiny_spawn(pool=pool, display=display, entry=row):
        if not catalog:
            cat = _catalog_key_from_itempool(pool) or _patch_inline_catalog_from_pool(pool)
            if cat:
                row["catalog_key"] = cat
                catalog = cat
        # Patch-inline / missing *_shiny NCS row (Verce): keep catalog for dump/@U.
        if catalog and catalog in _PATCH_INLINE_INVENTORY_DEFS:
            row["dump_named_legendary"] = "1"
    if _pool_needs_dump_first(pool, catalog):
        row["dump_named_legendary"] = "1"
    _stamp_spawn_shiny_intent(row)
    return row


def _dedupe_spawn_all_rows(
    entries: list[dict[str, str]],
    *,
    level: int,
    count: int,
) -> list[tuple[dict[str, str], int, int]]:
    # Keep the five proven parent pools, but reserve one requested roll for each
    # manifest Pearl that their live criteria omit.  The supplements use routes
    # which were observed producing pickups in this build.  Total drops remain
    # 17 and all calls still run in the no-gap Pearl burst.
    expanded: list[dict[str, str]] = []
    for entry in entries:
        pool = str(entry.get("itempool") or "").strip()
        if _is_generic_pearl_pool(pool):
            children = _pearl_child_rows(pool)
            if children:
                for row, _row_level, row_count in _balanced_generic_pearl_request(
                    entry,
                    level=level,
                    count=len(children),
                ):
                    row["spawn_all_count"] = str(row_count)
                    expanded.append(row)
                continue
        expanded.append(_normalize_spawn_all_entry(entry))

    # Prefer a named/catalog row over an otherwise identical anonymous pool
    # row. Keep BOTH the normal legendary and its *_shiny twin (same catalog).
    named_pools = {
        str(entry.get("itempool") or "").strip().lower()
        for entry in expanded
        if str(entry.get("catalog_key") or "").strip()
        and str(entry.get("itempool") or "").strip()
    }
    seen_named: set[str] = set()
    seen_anonymous_pool: set[str] = set()
    out: list[tuple[dict[str, str], int, int]] = []
    for entry in expanded:
        catalog = str(entry.get("catalog_key") or "").strip().lower()
        pool = str(entry.get("itempool") or "").strip().lower()
        if catalog:
            shiny_bit = "1" if (pool.endswith("_shiny") or "_shiny_" in pool) else "0"
            key = f"{catalog}|{shiny_bit}|{pool}"
            if key in seen_named:
                continue
            seen_named.add(key)
        elif pool:
            anonymous_key = pool
            if pool in named_pools or anonymous_key in seen_anonymous_pool:
                continue
            seen_anonymous_pool.add(anonymous_key)
        row_count = max(1, int(entry.get("spawn_all_count") or count))
        out.append((_normalize_spawn_all_entry(entry), level, row_count))
    return out


def _shape_fill_rank(entry: dict[str, str]) -> int:
    from .loot_shapes import is_shape_fill_pool_name

    pool = str(entry.get("itempool") or "").strip()
    cat = str(entry.get("category") or "").strip().lower()
    if cat == "smg" or "_sm_" in pool.lower() or "smg" in pool.lower():
        return 0
    if cat == "shotgun" or "_sg_" in pool.lower():
        return 1
    if cat == "assault rifle" or "_ar_" in pool.lower():
        return 2
    if is_shape_fill_pool_name(pool):
        return 3
    return 9


def _dump_shape_fill_rows(*, level: int, count: int) -> list[tuple[dict[str, str], int, int]]:
    rows: list[tuple[dict[str, str], int, int]] = []
    for pool in _SHAPE_FILL_TYPE_POOLS:
        rows.append(
            (
                {
                    "display_name": _display_name_for_pool(pool),
                    "itempool": pool,
                    "category": _category_for_pool_key(pool),
                    "shape_fill": "1",
                },
                level,
                count,
            )
        )
    return rows


def _spawn_row_drop_total(rows: list[tuple[dict[str, str], int, int]]) -> int:
    return sum(max(1, int(cnt)) for _entry, _level, cnt in rows)


def _extend_rows_until_shape_complete(
    rows: list[tuple[dict[str, str], int, int]],
    *,
    shape: str,
    profile: str,
    fill: bool,
) -> list[tuple[dict[str, str], int, int]]:
    """Pad the spawn queue until total drops cover the silhouette (geometry unchanged)."""
    if not fill:
        return rows
    from .loot_shapes import is_shape_fill_pool_name, shape_complete_slot_count

    want = int(shape_complete_slot_count(shape, profile=profile))
    if want <= 0:
        return rows
    have = _spawn_row_drop_total(rows)
    extra = min(_SHAPE_FILL_MAX_EXTRA, max(0, want - have))
    if extra <= 0:
        return rows
    fillers = [
        row for row in rows
        if is_shape_fill_pool_name(str(row[0].get("itempool") or ""))
    ]
    fillers.sort(key=lambda row: _shape_fill_rank(row[0]))
    if not fillers:
        level = rows[0][1] if rows else DEFAULT_ITEM_LEVEL
        # Fill pads with one drop per queued call so slot count matches land plan.
        fillers = _dump_shape_fill_rows(level=level, count=1)
    if not fillers and rows:
        # Repeat the requested row(s) when nothing else qualifies as a filler.
        src, lvl, _cnt = rows[0]
        fillers = [(dict(src), lvl, 1)]
    if not fillers:
        return rows
    out = list(rows)
    idx = 0
    while extra > 0:
        src, lvl, cnt = fillers[idx % len(fillers)]
        use_cnt = max(1, min(int(cnt) if int(cnt) > 0 else 1, extra))
        copy = dict(src)
        copy["shape_fill"] = "1"
        out.append((copy, lvl, use_cnt))
        extra -= use_cnt
        idx += 1
    filled = _spawn_row_drop_total(out)
    if filled < want:
        _log_warning(
            f"Shape fill queued {filled}/{want} drops (cap {_SHAPE_FILL_MAX_EXTRA} extra)."
        )
    return out


def _enqueue_spawn_all_wave(rows: list[tuple[dict[str, str], int, int]]) -> int:
    for row in rows:
        _BULK_SPAWN_QUEUE.append(row)
    return len(rows)


def _start_next_spawn_all_wave() -> bool:
    """Pull the next paced wave from _BULK_SPAWN_REMAINING; False if batch is done."""
    global _BULK_SPAWN_WAVE_INDEX, _BULK_SPAWN_WAVE_COOLDOWN_UNTIL

    if not _BULK_SPAWN_REMAINING:
        return False
    wave_size = max(1, int(SPAWN_ALL_WAVE_SIZE))
    chunk = _BULK_SPAWN_REMAINING[:wave_size]
    _BULK_SPAWN_REMAINING[:] = _BULK_SPAWN_REMAINING[wave_size:]
    _BULK_SPAWN_WAVE_INDEX += 1
    _enqueue_spawn_all_wave(chunk)
    done = max(0, _BULK_SPAWN_WAVE_TOTAL - len(_BULK_SPAWN_REMAINING) - len(_BULK_SPAWN_QUEUE))
    _log_info(
        f"Spawn All wave {_BULK_SPAWN_WAVE_INDEX}: +{len(chunk)} pools "
        f"({done}/{_BULK_SPAWN_WAVE_TOTAL} total, ~{_BULK_SPAWN_MIN_GAP_SEC}s between drops)."
    )
    _BULK_SPAWN_WAVE_COOLDOWN_UNTIL = 0.0
    return True


def spawn_all_filtered_item_pools(
    search: str = "",
    category: str = "All",
    *,
    level: int = DEFAULT_ITEM_LEVEL,
    count: int = 1,
) -> tuple[int, int]:
    """Compatibility wrapper: queue bulk work instead of blocking the game thread."""
    return queue_all_filtered_item_pools(
        search,
        category,
        level=level,
        count=count,
    ), 0


def _loot_object_addr(obj: object) -> int:
    try:
        get_address = getattr(obj, "_get_address", None)
        if callable(get_address):
            return int(get_address() or 0)
    except Exception:
        pass
    return 0


def _nearby_loot_addrs() -> set[int]:
    return {addr for addr in (_loot_object_addr(obj) for obj in _bulk_nearby_loot_objects()) if addr}


def _destroy_loot_addrs(addrs: set[int]) -> int:
    """Remove specific world pickups (shiny load drop after the legendary dump lands)."""
    want = {int(a) for a in addrs if int(a)}
    if not want:
        return 0
    destroyed = 0
    for obj in _bulk_nearby_loot_objects():
        if _loot_object_addr(obj) not in want:
            continue
        for method_name in ("K2_DestroyActor", "DestroyActor", "Destroy"):
            method = getattr(obj, method_name, None)
            if not callable(method):
                continue
            try:
                method()
                destroyed += 1
                break
            except Exception:
                continue
    return destroyed


def _destroy_loot_keys(want_keys: set[str], *, near_loc: object | None = None) -> int:
    """Remove world pickups whose verifier fingerprint is in want_keys."""
    want = {str(k) for k in want_keys if str(k)}
    if not want:
        return 0
    from .item_spawn.loot_verify import (
        _FEET_WEAPON_RADIUS,
        _FEET_WEAPON_RADIUS_OVERRIDE,
        _LOOT_VERIFY_SCAN_CAP,
        _WEAPON_LOOT_CLASSES,
        _stable_object_key,
        verify_available,
    )

    if not verify_available():
        return 0
    if near_loc is None:
        try:
            from .item_spawn.spawn_pc import resolve_spawn_pc
            from .item_spawn.loot_verify import player_location_from_pc

            near_loc = player_location_from_pc(resolve_spawn_pc())
        except Exception:
            near_loc = None
    if near_loc is None:
        return 0

    try:
        import unrealsdk

        ox = float(getattr(near_loc, "X"))
        oy = float(getattr(near_loc, "Y"))
        oz = float(getattr(near_loc, "Z"))
    except Exception:
        return 0

    radius = float(_FEET_WEAPON_RADIUS_OVERRIDE or _FEET_WEAPON_RADIUS)
    radius_sq = radius * radius
    destroyed = 0
    scanned = 0
    for cls in _WEAPON_LOOT_CLASSES:
        if scanned >= _LOOT_VERIFY_SCAN_CAP:
            break
        try:
            objs = list(unrealsdk.find_all(cls, False) or [])
        except Exception:
            continue
        for obj in reversed(objs):
            if scanned >= _LOOT_VERIFY_SCAN_CAP:
                break
            scanned += 1
            try:
                name = str(getattr(obj, "Name", "") or "")
                if not name or "Default__" in name:
                    continue
                loc = None
                for attr in ("K2_GetActorLocation", "GetActorLocation"):
                    fn = getattr(obj, attr, None)
                    if callable(fn):
                        loc = fn()
                        break
                if loc is None:
                    loc = getattr(obj, "Location", None)
                if loc is None:
                    continue
                dx = float(loc.X) - ox
                dy = float(loc.Y) - oy
                dz = float(loc.Z) - oz
                if dx * dx + dy * dy + dz * dz > radius_sq:
                    continue
                key = _stable_object_key(obj, cls, name)
                if key not in want:
                    continue
                for method_name in ("K2_DestroyActor", "DestroyActor", "Destroy"):
                    method = getattr(obj, method_name, None)
                    if not callable(method):
                        continue
                    try:
                        method()
                        destroyed += 1
                        break
                    except Exception:
                        continue
            except Exception:
                continue
    return destroyed


def _feet_loot_keys_at(near_loc: object | None) -> set[str]:
    if near_loc is None:
        return set()
    from .item_spawn.loot_verify import feet_weapon_loot_keys, verify_available

    if not verify_available():
        return set()
    return feet_weapon_loot_keys(near_loc)


def _bulk_loot_key(obj: object) -> str:
    try:
        return f"{type(obj).__name__}:{getattr(obj, 'Name', '')}:{obj}"
    except Exception:
        return f"id:{id(obj)}"


def _bulk_nearby_loot_objects() -> list[object]:
    """Narrow, paused scan used only by Spawn All test cleanup."""
    try:
        import unrealsdk

        pc = _get_runtime_pc()
        pose = _get_player_pose(pc) if pc is not None else None
        if pose is None:
            return []
        origin = pose[0]
        ox, oy, oz = float(origin.X), float(origin.Y), float(origin.Z)
    except Exception:
        return []

    radius_sq = float(SPAWN_ALL_CLEANUP_RADIUS) ** 2
    found: list[object] = []
    seen: set[str] = set()
    scanned = 0
    # These are the same narrow classes used by the existing loot verifier.
    for class_name in ("OakPickup", "OakInventoryPickup", "OakWeapon", "OakInventory"):
        if scanned >= _LOOT_VERIFY_SCAN_CAP:
            break
        try:
            objects = list(unrealsdk.find_all(class_name, False) or [])
        except Exception:
            continue
        for obj in objects:
            if scanned >= _LOOT_VERIFY_SCAN_CAP:
                break
            scanned += 1
            try:
                name = str(getattr(obj, "Name", "") or "")
                if not name or "Default__" in name:
                    continue
                loc = None
                for attr in ("K2_GetActorLocation", "GetActorLocation"):
                    fn = getattr(obj, attr, None)
                    if callable(fn):
                        loc = fn()
                        break
                if loc is None:
                    loc = getattr(obj, "Location", None)
                if loc is None:
                    continue
                dx = float(loc.X) - ox
                dy = float(loc.Y) - oy
                dz = float(loc.Z) - oz
                if dx * dx + dy * dy + dz * dz > radius_sq:
                    continue
                key = _bulk_loot_key(obj)
                if key not in seen:
                    seen.add(key)
                    found.append(obj)
            except Exception:
                continue
    return found


def _capture_bulk_cleanup_baseline() -> None:
    global _BULK_CLEANUP_BASELINE_READY
    if _BULK_CLEANUP_BASELINE_READY:
        return
    _BULK_PROTECTED_LOOT_KEYS.clear()
    _BULK_PROTECTED_LOOT_KEYS.update(_bulk_loot_key(obj) for obj in _bulk_nearby_loot_objects())
    # Also claim every pre-existing verifier key once.  Bulk jobs intentionally
    # avoid a costly before-scan per item, so this prevents an equipped weapon or
    # old ground drop from becoming a false OK for the first tested pool.
    try:
        from .item_spawn.loot_verify import claim_loot_keys, feet_weapon_loot_keys

        pc = _get_runtime_pc()
        pose = _get_player_pose(pc) if pc is not None else None
        if pose is not None:
            claim_loot_keys(feet_weapon_loot_keys(pose[0]))
    except Exception:  # noqa: BLE001
        pass
    _BULK_CLEANUP_BASELINE_READY = True
    if not _spawn_queue_is_single():
        _log_info(
            f"Spawn All cleanup protected {len(_BULK_PROTECTED_LOOT_KEYS)} pre-existing nearby loot object(s)."
        )


def _cleanup_bulk_test_loot() -> tuple[int, int]:
    """Destroy only nearby loot created after this Spawn All batch began."""
    destroyed = 0
    failed = 0
    for obj in _bulk_nearby_loot_objects():
        if _bulk_loot_key(obj) in _BULK_PROTECTED_LOOT_KEYS:
            continue
        did_destroy = False
        for method_name in ("K2_DestroyActor", "DestroyActor", "Destroy"):
            method = getattr(obj, method_name, None)
            if not callable(method):
                continue
            try:
                method()
                destroyed += 1
                did_destroy = True
                break
            except Exception:
                continue
        if not did_destroy:
            failed += 1
    _log_info(
        f"Spawn All cleanup: removed {destroyed} test loot actor(s); "
        f"{failed} non-actor inventory object(s) left for engine cleanup."
    )
    return destroyed, failed


def _schedule_bulk_test_cleanup() -> None:
    global _BULK_CLEANUP_DUE_AT
    if _BULK_CLEANUP_DUE_AT:
        return
    _BULK_CLEANUP_DUE_AT = time.monotonic() + float(SPAWN_ALL_CLEANUP_SETTLE_SEC)


def _maybe_bulk_segment_pause() -> None:
    """Track batch progress and optionally pause when explicitly configured."""
    global _BULK_SPAWN_SEGMENT_COUNT, _BULK_SPAWN_SEGMENT_PAUSE_UNTIL

    if not (bulk_spawn_active() or _BULK_SPAWN_SUMMARY_PENDING):
        return
    _BULK_SPAWN_SEGMENT_COUNT += 1
    global _BULK_SPAWNS_SINCE_CLEANUP
    _BULK_SPAWNS_SINCE_CLEANUP += 1
    if (
        _BULK_TEST_CLEANUP_ENABLED
        and _BULK_SPAWNS_SINCE_CLEANUP >= int(SPAWN_ALL_CLEANUP_EVERY)
    ):
        _schedule_bulk_test_cleanup()
    if SPAWN_ALL_SEGMENT_SIZE <= 0 or SPAWN_ALL_SEGMENT_PAUSE_SEC <= 0:
        return
    if _BULK_SPAWN_SEGMENT_COUNT < int(SPAWN_ALL_SEGMENT_SIZE):
        return
    _BULK_SPAWN_SEGMENT_COUNT = 0
    _BULK_SPAWN_SEGMENT_PAUSE_UNTIL = time.monotonic() + float(SPAWN_ALL_SEGMENT_PAUSE_SEC)
    try:
        from .item_spawn.pearl_spawn_ring import reset_pile_slot

        reset_pile_slot()
    except Exception:  # noqa: BLE001
        pass
    _log_info(
        f"Spawn All breather ({SPAWN_ALL_SEGMENT_PAUSE_SEC:.0f}s) — "
        f"pick up loot nearby ({_BULK_SPAWN_OK} ok so far), then auto-continues."
    )


def _bulk_pickup_addrs(*, fresh: bool) -> set[int]:
    try:
        from .loot_shapes import landing_armed, pickup_address_set

        # Shaped dumps pin by actor, not feet scans. find_all here is the pearl hitch.
        if landing_armed():
            return set()
        return set(pickup_address_set(fresh=fresh))
    except Exception:
        return set()


def _record_bulk_ground_result(
    entry: dict[str, str],
    *,
    level: int,
    count: int,
    before_addrs: set[int],
    method: str,
    detail: str,
    fail_method: str = "silent_empty",
    fail_detail: str | None = None,
) -> bool:
    """True when a new world pickup appeared after this Spawn All item."""
    global _BULK_SPAWN_OK, _BULK_SPAWN_FAIL
    landing = False
    try:
        from .loot_shapes import landing_armed

        landing = bool(landing_armed())
    except Exception:
        landing = False
    after_addrs: set[int] = set()
    if landing:
        gained = True
    elif bulk_spawn_is_mass() and not before_addrs:
        gained = True
    else:
        after_addrs = _bulk_pickup_addrs(fresh=True)
        gained = bool(after_addrs - before_addrs)
    display = str(entry.get("display_name") or entry.get("itempool") or "item")
    method_l = str(method or "").strip().lower()
    named_unique_base = _is_named_unique_legendary_row(entry, wants_shiny=False)
    if named_unique_base and method_l in (
        "pool_spawn",
        "ncs_shiny_pool",
        "ncs_named_pool",
        "ncs_live_pool",
        "ncs_legacy",
        "ncs_legacy_bulk",
    ):
        delivery = _pearl_spawn_delivery_info()
        dm = str(delivery.get("method") or method_l).strip().lower()
        if not dm.startswith("dump_") and dm not in _NAMED_UNIQUE_DUMP_METHODS:
            if landing:
                pass
            elif bulk_spawn_is_mass() and not before_addrs:
                gained = False
            else:
                gained = bool(after_addrs - before_addrs)
    # Spawn All may trust silent live RPC. Spawn Selected uses the same trust.
    if (
        not gained
        and not named_unique_base
        and not _SINGULAR_PATH_TEST
        and not _spawn_queue_is_selected()
        and method_l in (
            "ncs_verified_pool",
            "dump_inv_def",
            "pool_spawn",
            "ncs_shiny_pool",
            "ncs_named_pool",
            "ncs_live_pool",
            "ncs_legacy",
            "ncs_legacy_bulk",
        )
    ):
        gained = True
    if not gained and _bulk_dump_delivery_trusted(entry, method):
        gained = True
    if gained:
        _BULK_SPAWN_OK += 1
        record_spawn_result(
            entry,
            ok=True,
            method=method,
            detail=detail,
            count=count,
            level=level,
            observed=True,
        )
        return True
    _BULK_SPAWN_FAIL += 1
    record_spawn_result(
        entry,
        ok=False,
        method=fail_method,
        detail=str(fail_detail or f"{display}: no new ground loot")[:500],
        count=count,
        level=level,
        observed=False,
    )
    return False


def _rescue_selected_silent_empty(
    entry: dict[str, str],
    *,
    level: int,
    count: int,
) -> tuple[int, str, str]:
    """When Selected live pool_spawn RPC-ok with zero ground loot, dump/@U now.

    Dump 18:23: Whiskey Foxtrot / Star Helix logged pool_spawn + loot_observed
    while nothing landed — same pools work in Spawn All. Do NOT retry live NCS.
    """
    row = dict(entry)
    catalog = str(row.get("catalog_key") or "").strip().lower()
    pool = str(row.get("itempool") or "").strip()
    display = str(row.get("display_name") or pool or catalog or "item").strip()
    wants_shiny = _wants_shiny_spawn(pool=pool, display=display, entry=row)
    if not catalog:
        catalog = _catalog_key_from_itempool(pool) or _patch_inline_catalog_from_pool(pool)
        if catalog:
            row["catalog_key"] = catalog
    if not catalog:
        return 0, "silent_empty", f"{display}: no catalog for dump rescue"
    want = max(1, int(count))
    lvl = max(1, int(level))
    handles = _lean_inv_handles_for_named(row, catalog)
    if not handles:
        handles = _catalog_inv_handles(catalog)[:6]
    if handles:
        try:
            from .item_spawn.item_pool_list_spawn import spawn_itempoollist_inv_at_feet

            ipl_hit, _ipl_err = spawn_itempoollist_inv_at_feet(
                handles[:6],
                count=want,
                level=lvl,
                require_loot_verify=False,
                wants_shiny=wants_shiny,
            )
            if ipl_hit > 0:
                _set_pearl_spawn_delivery(
                    "dump_itempoollist",
                    handles[0],
                    loot_verified=False,
                    skip_verify=True,
                )
                return int(ipl_hit), "dump_itempoollist", handles[0]
        except Exception:  # noqa: BLE001
            pass
        from .item_spawn.comp_loot_drop import (
            spawn_inv_handles_at_feet,
            spawn_named_comp_inline_at_feet,
        )

        spawn_fn = (
            spawn_inv_handles_at_feet if wants_shiny else spawn_named_comp_inline_at_feet
        )
        try:
            dumped, _err = spawn_fn(
                handles[:6],
                count=want,
                level=lvl,
                skip_verify=True,
            )
        except Exception:  # noqa: BLE001
            dumped = 0
        if dumped > 0:
            _set_pearl_spawn_delivery(
                "dump_inv_selected_rescue",
                handles[0],
                loot_verified=True,
                skip_verify=False,
            )
            return int(dumped), "dump_inv_selected_rescue", handles[0]
    try:
        hit = _spawn_proven_catalog_ground(
            catalog,
            count=want,
            level=lvl,
            display=display,
            pool=pool,
            prefer_serial=True,
            wants_shiny=wants_shiny,
            allow_native=False,
        )
        if hit > 0:
            delivery = _pearl_spawn_delivery_info()
            method = str(delivery.get("method") or "dump_proven")
            detail = str(delivery.get("detail") or method)
            return int(hit), method, detail
    except Exception:  # noqa: BLE001
        pass
    dump_serial = str(_DUMP_ONLY_GROUND_SERIALS.get(catalog) or "").strip()
    if not dump_serial:
        dump_serial = str(
            _curated_serial_for_dump_catalog(catalog, pool, display) or ""
        ).strip()
    if dump_serial:
        try:
            n = _deliver_catalog_serial_ground_only(dump_serial, want, display)
            if n > 0:
                return int(n), "serial_selected_rescue", catalog
        except Exception:  # noqa: BLE001
            pass
    if not wants_shiny:
        twin_hit = _spawn_named_unique_via_registered_twin(
            row,
            catalog=catalog,
            display=display,
            count=want,
            level=lvl,
        )
        if twin_hit > 0:
            return int(twin_hit), "ncs_named_twin", catalog
    return 0, "silent_empty", (
        f"{display}: live pool silent-empty; dump/@U/NCS twin missed. "
        "Try Spawn All Filtered or the type pool (AR / SG / SM / PS / SR 05 Legendary)."
    )


def _selected_feet_loot_keys() -> set[str]:
    """Weapon/pickup keys near the player — not the whole-world address set."""
    try:
        from .item_spawn.loot_verify import (
            feet_weapon_loot_keys,
            player_location_from_pc,
            set_feet_verify_radius,
        )

        try:
            from .item_spawn.spawn_pc import resolve_spawn_pc

            pc = resolve_spawn_pc()
        except Exception:
            pc = _get_runtime_pc()
        # Wider than default 420uu — Selected front-pile can land a bit out.
        set_feet_verify_radius(1400.0)
        loc = player_location_from_pc(pc)
        if loc is None:
            return set()
        return set(feet_weapon_loot_keys(loc))
    except Exception:
        return set()


def _selected_saw_new_loot(before_keys: set[str]) -> bool:
    after = _selected_feet_loot_keys()
    return bool(after - before_keys)


def pump_bulk_spawn_queue(*, max_steps: int = _BULK_SPAWN_STEPS_PER_TICK) -> int:
    """Process queued pool spawns on the game thread (min gap enforced)."""
    global _BULK_SPAWN_LAST_STEP, _BULK_SPAWN_OK, _BULK_SPAWN_FAIL, _BULK_SPAWN_DRAINING
    if not _BULK_SPAWN_QUEUE:
        return 0
    _ensure_bulk_spawn_hook()
    processed = 0
    limit = max(1, min(int(max_steps), _BULK_SPAWN_STEPS_PER_TICK))
    while processed < limit and _BULK_SPAWN_QUEUE:
        if _bulk_spawn_blocked_by_verify():
            _pump_spawn_verify_queue(max_jobs=1)
            break
        now = time.monotonic()
        if (
            _BULK_SPAWN_LAST_STEP
            and (now - _BULK_SPAWN_LAST_STEP) < _BULK_SPAWN_MIN_GAP_SEC
        ):
            break
        entry, level, count = _BULK_SPAWN_QUEUE.pop(0)
        _BULK_SPAWN_LAST_STEP = time.monotonic()
        processed += 1
        batch_index = max(
            1,
            _BULK_SPAWN_WAVE_TOTAL
            - len(_BULK_SPAWN_QUEUE)
            - len(_BULK_SPAWN_REMAINING),
        )
        quarantine_reason = _crash_quarantine_reason(entry)
        if quarantine_reason:
            before_addrs = (
                _bulk_pickup_addrs(fresh=False)
                if _bulk_feet_verify_this_step()
                else set()
            )
            try:
                safe_spawned = _spawn_crash_safe_serial(entry, count, level=level)
            except Exception as exc:  # noqa: BLE001
                safe_spawned = None
                quarantine_reason = f"{quarantine_reason}; safe serial failed: {exc}"
            if safe_spawned is None:
                _bulk_trace(entry, batch_index, "SKIPPED_UNSAFE", quarantine_reason)
                _BULK_SPAWN_FAIL += 1
                record_spawn_result(
                    entry,
                    ok=False,
                    method="crash_quarantined",
                    detail=f"Skipped before Unreal call: {quarantine_reason}",
                    count=count,
                    level=level,
                )
                _maybe_bulk_segment_pause()
                continue
            try:
                from .loot_shapes import after_dump_spawn, landing_armed

                if landing_armed():
                    after_dump_spawn(max(1, int(count)))
            except Exception:
                pass
            if _record_bulk_ground_result(
                entry,
                level=level,
                count=count,
                before_addrs=before_addrs,
                method="serial_ground",
                detail="safe pool-free spawn",
            ):
                _bulk_trace(entry, batch_index, "SAFE_SERIAL_RETURNED")
            else:
                _bulk_trace(entry, batch_index, "ERROR", "no new ground loot")
            _maybe_bulk_segment_pause()
            continue
        if _BULK_SPAWN_SUMMARY_PENDING:
            _bulk_trace(entry, batch_index, "START")
        _BULK_SPAWN_DRAINING = True
        # Spawn Selected uses verify-defer + dump rescue; Spawn All trusts live pools.
        single_queue = bool(_SINGULAR_PATH_TEST) or _spawn_queue_is_selected()
        verify_before_loc, verify_before_keys = (
            _capture_loot_snapshot()
            if single_queue
            else (None, None)
        )
        before_addrs = (
            _bulk_pickup_addrs(fresh=True)
            if (
                single_queue
                or _bulk_feet_verify_this_step()
                or (
                    _bulk_row_requires_loot_verify(entry)
                    and not bulk_spawn_is_mass()
                )
            )
            else set()
        )
        batch_slot = max(0, int(_BULK_SPAWN_OK) + int(_BULK_SPAWN_FAIL))
        try:
            from .loot_shapes import landing_armed, peek_spawn_land_index, register_land_slot_pool

            if landing_armed():
                idx = peek_spawn_land_index()
                pool_reg = str(entry.get("itempool") or entry.get("pool") or "").strip()
                if idx is not None and pool_reg:
                    register_land_slot_pool(int(idx), pool_reg)
        except Exception:
            pass
        try:
            from .item_spawn.pearl_spawn_ring import bump_ring_index

            bump_ring_index()
            spawned_n = spawn_item_pool_entry(entry, level, count)
            try:
                from .loot_shapes import after_dump_spawn, landing_armed

                if landing_armed():
                    after_dump_spawn(max(1, int(count)))
                elif single_queue:
                    method_hint = str(
                        (_pearl_spawn_delivery_info() or {}).get("method") or ""
                    ).lower()
                    if method_hint in ("", "pool_spawn") or (
                        method_hint.startswith(
                            ("ncs_", "pool_", "registered_", "legacy_", "native_")
                        )
                        and "dump_" not in method_hint
                    ):
                        _yank_singular_loot_in_front(before_keys=verify_before_keys)
            except Exception:
                if single_queue:
                    _yank_singular_loot_in_front(before_keys=verify_before_keys)
            delivery = _pearl_spawn_delivery_info()
            method = str(delivery.get("method") or "pool_spawn")
            detail = str(delivery.get("detail") or delivery.get("method") or "spawned")
            display = str(entry.get("display_name") or entry.get("itempool") or "item").strip()
            if (
                single_queue
                and spawned_n <= 0
                and _is_named_unique_legendary_row(entry, wants_shiny=False)
            ):
                rescued, rescue_method, rescue_detail = _rescue_selected_silent_empty(
                    entry,
                    level=level,
                    count=count,
                )
                if rescued > 0:
                    _BULK_SPAWN_OK += 1
                    record_spawn_result(
                        entry,
                        ok=True,
                        method=rescue_method,
                        detail=rescue_detail,
                        count=count,
                        level=level,
                        observed=True,
                    )
                    if _BULK_SPAWN_SUMMARY_PENDING:
                        _bulk_trace(entry, batch_index, "SELECTED_RESCUE")
                    _maybe_bulk_segment_pause()
                    continue
            if (
                single_queue
                and delivery.get("skip_verify") == "1"
                and (
                    str(delivery.get("method") or "").strip().lower().startswith("dump_")
                    or str(delivery.get("method") or "").strip().lower()
                    in _NAMED_UNIQUE_DUMP_METHODS
                    or str(delivery.get("method") or "").strip().lower()
                    == "ncs_named_twin"
                )
            ):
                _BULK_SPAWN_OK += 1
                record_spawn_result(
                    entry,
                    ok=True,
                    method=method,
                    detail=detail,
                    count=count,
                    level=level,
                    observed=True,
                )
                if _BULK_SPAWN_SUMMARY_PENDING:
                    _bulk_trace(entry, batch_index, "RETURNED")
            elif (
                single_queue
                and not _landing_shape_armed()
                and delivery.get("loot_verified") != "1"
                and delivery.get("skip_verify") != "1"
            ):
                _enqueue_spawn_verify(
                    entry=entry,
                    level=level,
                    count=count,
                    before_loc=verify_before_loc,
                    before_keys=verify_before_keys,
                    spawned=max(1, int(count)),
                    method=method,
                    detail=detail,
                    display=display,
                    from_bulk=True,
                )
                if _BULK_SPAWN_SUMMARY_PENDING:
                    _bulk_trace(entry, batch_index, "VERIFY_DEFER")
            elif single_queue:
                _BULK_SPAWN_OK += 1
                record_spawn_result(
                    entry,
                    ok=True,
                    method=method,
                    detail=detail,
                    count=count,
                    level=level,
                    observed=True,
                )
                if _BULK_SPAWN_SUMMARY_PENDING:
                    _bulk_trace(entry, batch_index, "RETURNED")
            elif _record_bulk_ground_result(
                entry,
                level=level,
                count=count,
                before_addrs=before_addrs,
                method=method,
                detail=detail,
            ):
                if _BULK_SPAWN_SUMMARY_PENDING:
                    _bulk_trace(entry, batch_index, "RETURNED")
            elif _bulk_row_requires_loot_verify(entry) and _spawn_queue_is_selected():
                rescued, rescue_method, rescue_detail = _rescue_selected_silent_empty(
                    entry,
                    level=level,
                    count=count,
                )
                if rescued > 0 and _record_bulk_ground_result(
                    entry,
                    level=level,
                    count=count,
                    before_addrs=before_addrs,
                    method=rescue_method,
                    detail=rescue_detail,
                ):
                    if _BULK_SPAWN_SUMMARY_PENDING:
                        _bulk_trace(entry, batch_index, "RESCUED")
                elif _BULK_SPAWN_SUMMARY_PENDING:
                    _bulk_trace(entry, batch_index, "ERROR", "no new ground loot")
            elif _bulk_dump_delivery_trusted(entry, method):
                _BULK_SPAWN_OK += 1
                record_spawn_result(
                    entry,
                    ok=True,
                    method=method,
                    detail=detail,
                    count=count,
                    level=level,
                    observed=True,
                )
                if _BULK_SPAWN_SUMMARY_PENDING:
                    _bulk_trace(entry, batch_index, "RETURNED")
            elif _BULK_SPAWN_SUMMARY_PENDING:
                _bulk_trace(entry, batch_index, "ERROR", "no new ground loot")
        except Exception as exc:  # noqa: BLE001
            try:
                from .loot_shapes import after_dump_spawn, landing_armed

                if landing_armed():
                    after_dump_spawn(max(1, int(count)))
            except Exception:
                pass
            from .item_spawn.pearlescent_manifest import is_pearlescent_catalog

            catalog = str(entry.get("catalog_key") or "").strip().lower()
            if catalog and is_pearlescent_catalog(catalog):
                if _record_bulk_ground_result(
                    entry,
                    level=level,
                    count=count,
                    before_addrs=before_addrs,
                    method="pool_spawn",
                    detail="ground loot after pearl path",
                    fail_method="pearl_queue",
                    fail_detail=str(exc)[:500],
                ):
                    if _BULK_SPAWN_SUMMARY_PENDING:
                        _bulk_trace(entry, batch_index, "RETURNED")
                elif _BULK_SPAWN_SUMMARY_PENDING:
                    _bulk_trace(entry, batch_index, "ERROR", str(exc))
                continue
            pearl_hit = _try_pearl_world_spawn(
                entry,
                count=count,
                display=str(entry.get("display_name") or "pearl"),
                level=level,
            )
            if pearl_hit is not None:
                try:
                    from .loot_shapes import after_dump_spawn, landing_armed

                    if landing_armed():
                        after_dump_spawn(max(1, int(count)))
                except Exception:
                    pass
                _record_bulk_ground_result(
                    entry,
                    level=level,
                    count=count,
                    before_addrs=before_addrs,
                    method="pearl_fallback",
                    detail="fallback returned",
                )
                continue
            _BULK_SPAWN_FAIL += 1
            record_spawn_result(
                entry,
                ok=False,
                method="bulk_queue",
                detail=str(exc)[:500],
                count=count,
                level=level,
            )
        finally:
            _BULK_SPAWN_DRAINING = False
            _maybe_bulk_segment_pause()
    return processed


def cancel_bulk_spawn_batch(*, log: bool = True) -> tuple[int, int]:
    """Abort an in-progress Spawn All / singular-test batch (clears queue + waves)."""
    global _BULK_SPAWN_SUMMARY_PENDING, _BULK_SPAWN_REMAINING, _BULK_SPAWN_WAVE_TOTAL
    global _BULK_SPAWN_WAVE_INDEX, _BULK_SPAWN_WAVE_COOLDOWN_UNTIL, _BULK_SHARED_TICK_QUEUED
    global _BULK_SPAWN_SEGMENT_COUNT, _BULK_SPAWN_SEGMENT_PAUSE_UNTIL
    global _BULK_CLEANUP_DUE_AT, _BULK_SPAWNS_SINCE_CLEANUP, _BULK_CLEANUP_BASELINE_READY
    global _BULK_SPAWN_SUMMARY_DEFER_UNTIL, _BULK_FINISH_SETTLED, _SINGULAR_PATH_TEST

    abandoned = len(_BULK_SPAWN_QUEUE) + len(_BULK_SPAWN_REMAINING)
    verifying = len(_SPAWN_VERIFY_QUEUE)
    was_singular = bool(_SINGULAR_PATH_TEST)
    if not abandoned and not _BULK_SPAWN_SUMMARY_PENDING and not verifying:
        if log:
            _log_info("Spawn cancel: no batch running.")
        return 0, _BULK_SPAWN_OK
    _BULK_SPAWN_QUEUE.clear()
    _BULK_SPAWN_REMAINING.clear()
    _SINGULAR_PATH_TEST = False
    try:
        from .loot_shapes import clear_spawn_landing

        clear_spawn_landing()
    except Exception:
        pass
    _clear_bulk_spawn_perf_state()
    _SPAWN_VERIFY_QUEUE.clear()
    _BULK_SPAWN_WAVE_TOTAL = 0
    _BULK_SPAWN_WAVE_INDEX = 0
    _BULK_SPAWN_WAVE_COOLDOWN_UNTIL = 0.0
    _BULK_SHARED_TICK_QUEUED = False
    _BULK_SPAWN_SEGMENT_COUNT = 0
    _BULK_SPAWN_SEGMENT_PAUSE_UNTIL = 0.0
    _BULK_CLEANUP_DUE_AT = 0.0
    _BULK_SPAWNS_SINCE_CLEANUP = 0
    _BULK_PROTECTED_LOOT_KEYS.clear()
    _BULK_CLEANUP_BASELINE_READY = False
    _BULK_SPAWN_SUMMARY_PENDING = False
    _BULK_SPAWN_SUMMARY_DEFER_UNTIL = 0.0
    _BULK_FINISH_SETTLED = False
    _rewrite_spawn_summary()
    _invalidate_pool_health_cache()
    try:
        from .item_spawn.pearl_spawn_ring import set_bulk_pile_mode

        set_bulk_pile_mode(False)
    except Exception:  # noqa: BLE001
        pass
    try:
        from .item_spawn.loot_verify import set_feet_verify_radius

        set_feet_verify_radius(None)
    except Exception:
        pass
    ok, fail = _BULK_SPAWN_OK, _BULK_SPAWN_FAIL
    if log:
        kind = "Singular test" if was_singular else "Spawn All"
        _log_info(
            f"{kind} cancelled ({abandoned} pools not spawned, "
            f"{verifying} verify jobs dropped). Batch so far: {ok} ok, {fail} fail."
        )
    return abandoned, ok


def bulk_spawn_queue_depth() -> int:
    return len(_BULK_SPAWN_QUEUE)


def _bulk_spawn_tick(*_args: object, **_kwargs: object) -> None:
    """One spawn per deferred tick; segment pauses; auto-continue waves."""
    global _BULK_SPAWN_WAVE_COOLDOWN_UNTIL, _BULK_SPAWN_SEGMENT_PAUSE_UNTIL
    global _BULK_CLEANUP_DUE_AT, _BULK_SPAWNS_SINCE_CLEANUP

    now = time.monotonic()
    if _BULK_SPAWN_SUMMARY_PENDING:
        _capture_bulk_cleanup_baseline()
        if _SPAWN_VERIFY_QUEUE:
            _pump_spawn_verify_queue(
                max_jobs=1 if _SINGULAR_PATH_TEST else max(1, _BULK_SPAWN_STEPS_PER_TICK)
            )
            # Singular test: never spawn the next row until this one's verify
            # finishes (same pacing as clicking Spawn Selected repeatedly).
            if _SINGULAR_PATH_TEST and _SPAWN_VERIFY_QUEUE:
                return
    if _BULK_CLEANUP_DUE_AT:
        if now < _BULK_CLEANUP_DUE_AT:
            return
        _cleanup_bulk_test_loot()
        _BULK_CLEANUP_DUE_AT = 0.0
        _BULK_SPAWNS_SINCE_CLEANUP = 0
        now = time.monotonic()
    if _BULK_SPAWN_SEGMENT_PAUSE_UNTIL:
        if now < _BULK_SPAWN_SEGMENT_PAUSE_UNTIL:
            return
        _BULK_SPAWN_SEGMENT_PAUSE_UNTIL = 0.0

    if _BULK_SPAWN_QUEUE:
        pump_bulk_spawn_queue(max_steps=_BULK_SPAWN_STEPS_PER_TICK)
        if not _BULK_SPAWN_QUEUE and _BULK_SPAWN_REMAINING:
            _BULK_SPAWN_WAVE_COOLDOWN_UNTIL = (
                time.monotonic() + float(SPAWN_ALL_WAVE_COOLDOWN_SEC)
            )
    elif _BULK_SPAWN_REMAINING:
        now = time.monotonic()
        if now < _BULK_SPAWN_WAVE_COOLDOWN_UNTIL:
            return
        if _start_next_spawn_all_wave():
            pump_bulk_spawn_queue(max_steps=_BULK_SPAWN_STEPS_PER_TICK)
    if not _BULK_SPAWN_QUEUE and not _BULK_SPAWN_REMAINING:
        global _BULK_FINISH_SETTLED, _BULK_SPAWN_SUMMARY_DEFER_UNTIL
        if not _BULK_FINISH_SETTLED:
            _BULK_FINISH_SETTLED = True
            _clear_bulk_spawn_perf_state()
            # Singular feet test: never settle/catch — that re-teleports the pile
            # and was wiping visible drops after the run.
            if not _SINGULAR_PATH_TEST:
                try:
                    from .loot_shapes import arm_deferred_catch, settle_landing_loot

                    # Same pin budget as Drop All — avoid a big find_all hitch on the complete tick,
                    # but pull enough leftovers that house/globe aren't a few slots short.
                    settle_landing_loot(limit=96)
                    arm_deferred_catch(28.0)
                except Exception:
                    pass
            # Rewrite spawn_test.jsonl / console dump on a later tick.
            _BULK_SPAWN_SUMMARY_DEFER_UNTIL = time.monotonic() + 0.45
        if _BULK_TEST_CLEANUP_ENABLED and _BULK_SPAWNS_SINCE_CLEANUP > 0:
            _schedule_bulk_test_cleanup()
            return
        _pump_spawn_verify_queue(max_jobs=1)
    _maybe_write_bulk_spawn_summary()


def _bulk_shared_tick_action() -> tuple[bool, str]:
    """One spawn step via SQBT's proven-live shared deferred tick."""
    global _BULK_SHARED_TICK_QUEUED
    _BULK_SHARED_TICK_QUEUED = False
    _bulk_spawn_tick()
    if _bulk_spawn_ui_active():
        _schedule_bulk_shared_tick()
    return True, "SQBT spawn queue advanced."


def _schedule_bulk_shared_tick() -> None:
    """Queue exactly one follow-up tick (never stack duplicate deferred actions)."""
    global _BULK_SHARED_TICK_QUEUED
    if _BULK_SHARED_TICK_QUEUED:
        return
    _ensure_bulk_spawn_hook()
    from . import spawn_deferred as deferred

    _BULK_SHARED_TICK_QUEUED = True
    deferred.queue_action("SQBT loot pool spawn", _bulk_shared_tick_action)


def _ensure_bulk_spawn_hook() -> None:
    global _BULK_SPAWN_HOOK_READY
    if _BULK_SPAWN_HOOK_READY:
        return
    try:
        from . import spawn_deferred as deferred

        if not hasattr(deferred, "queue_action"):
            raise RuntimeError("SQBT deferred queue has no queue_action")
        _BULK_SPAWN_HOOK_READY = True
    except Exception as exc:
        raise RuntimeError(f"Could not attach Spawn All to shared tick: {exc}") from exc


def queue_item_pool_entry(
    entry: dict[str, str],
    *,
    level: int = DEFAULT_ITEM_LEVEL,
    count: int = 1,
    shape: str = "none",
    settle: str = "none",
    drop_height: float = 520.0,
    line_length: float = 900.0,
    radius: float = 220.0,
    spacing: float = 140.0,
    z_bias: float = 30.0,
    spawn_then_shape: bool = False,
    stay_in_air: bool = True,
    peel_after: float = 0.0,
    land_profile: str = "bulk",
    fill_until_complete: bool = False,
    shape_text: str = "",
) -> None:
    """Queue one pool row for paced spawning on the next UI ticks."""
    global _BULK_SPAWN_OK, _BULK_SPAWN_FAIL, _BULK_SPAWN_SUMMARY_PENDING
    global _BULK_SPAWN_WAVE_TOTAL, _BULK_SPAWN_WAVE_INDEX
    global _BULK_CLEANUP_BASELINE_READY, _BULK_TEST_CLEANUP_ENABLED
    global _BULK_SPAWN_SUMMARY_DEFER_UNTIL, _BULK_FINISH_SETTLED, _SINGULAR_PATH_TEST
    _ensure_bulk_spawn_hook()
    shape_l = str(shape or "none").strip().lower()
    if shape_text or shape_l in ("text", "text_shape", "words", "word", "write"):
        try:
            from .loot_shapes import set_shape_text  # noqa: PLC0415

            set_shape_text(shape_text)
            shape = "text"
            shape_l = "text"
        except Exception:
            pass
    settle_l = str(settle or "none").strip().lower()
    if shape_l not in ("", "none", "off", "no", "vanilla") or settle_l not in ("", "none"):
        configure_bulk_spawn(random_spread=False)
    count = max(1, min(int(count), MAX_SINGLE_POOL_SPAWN_COUNT))
    level = max(1, int(level))
    # Stuck verify-only leftovers blocked Selected ("already queued") and made
    # new_batch clear dead (clear ran only when verify was already empty).
    if not _BULK_SPAWN_QUEUE and not _BULK_SPAWN_REMAINING:
        if _SPAWN_VERIFY_QUEUE or _SPAWN_PENDING_KEYS:
            _SPAWN_VERIFY_QUEUE.clear()
            _SPAWN_PENDING_KEYS.clear()
    request_key = _spawn_health_key(entry)
    if request_key:
        queued_entries = [row[0] for row in _BULK_SPAWN_QUEUE]
        queued_entries.extend(row[0] for row in _BULK_SPAWN_REMAINING)
        queued_entries.extend(job.entry for job in _SPAWN_VERIFY_QUEUE)
        if any(_spawn_health_key(row) == request_key for row in queued_entries):
            display = str(entry.get("display_name") or entry.get("itempool") or "Pool")
            raise RuntimeError(f"{display} is already queued or being verified.")
    new_batch = not (_BULK_SPAWN_QUEUE or _BULK_SPAWN_REMAINING or _SPAWN_VERIFY_QUEUE)
    if new_batch:
        _SINGULAR_PATH_TEST = False
        _BULK_SPAWN_OK = 0
        _BULK_SPAWN_FAIL = 0
        _BULK_SPAWN_SUMMARY_PENDING = True
        _BULK_SPAWN_SUMMARY_DEFER_UNTIL = 0.0
        _BULK_FINISH_SETTLED = False
        _BULK_CLEANUP_BASELINE_READY = False
        _BULK_TEST_CLEANUP_ENABLED = False
        # Stale verify jobs made Selected raise "already queued or being verified"
        # after a prior silent RETURNED (dump 20:18 Bugbear / 20:24 Whiskey Foxtrot).
        _SPAWN_VERIFY_QUEUE.clear()
        _SPAWN_PENDING_KEYS.clear()
        from .item_spawn.loot_verify import reset_claimed_loot_keys
        from .item_spawn.pearl_spawn_ring import set_bulk_pile_mode

        reset_claimed_loot_keys()
        # Singular Spawn selected: always drop in a front pile, never the 360°
        # ring that can land behind. Spawn All may turn this off later.
        set_bulk_pile_mode(True)
        try:
            from .loot_shapes import clear_spawn_landing

            # Wipe any leftover silhouette from a prior shaped Spawn All so a
            # single drop is not teleported into an old behind-the-player slot.
            if shape_l in ("", "none", "off", "no", "vanilla"):
                clear_spawn_landing()
        except Exception as land_exc:
            _log_warning(f"Could not clear prior land-in-shape: {land_exc}")
    pool = str(entry.get("itempool") or "").strip()
    # Same resolve as Spawn All Filtered — rewrite synthetic *_comp_05_* / casing
    # to live NCS ids before queue. Without this, Selected skips live-first
    # ("_comp_05_" in pool) while Spawn All spawns the same gun fine.
    rows = _balanced_generic_pearl_request(
        _normalize_spawn_all_entry(entry),
        level=level,
        count=count,
    )
    if fill_until_complete and shape_l not in ("", "none", "off", "no", "vanilla"):
        rows = _extend_rows_until_shape_complete(
            rows,
            shape=shape_l,
            profile=land_profile,
            fill=True,
        )
    if new_batch:
        try:
            from .loot_shapes import begin_spawn_landing, pause_catch_for_shape, set_bulk_healthcheck_mode

            begin_spawn_landing(
                max(1, _spawn_row_drop_total(rows)),
                shape=shape,
                settle=settle,
                drop_height=drop_height,
                line_length=line_length,
                radius=radius,
                spacing=spacing,
                z_bias=z_bias,
                spawn_then_shape=spawn_then_shape,
                stay_in_air=stay_in_air,
                peel_after=peel_after,
                land_profile=land_profile,
                shape_text=shape_text,
            )
            pause_catch_for_shape(shape)
            if shape_l not in ("", "none", "off", "no", "vanilla") or settle_l not in ("", "none"):
                set_bulk_healthcheck_mode(True)
        except Exception as land_exc:
            _log_warning(f"Could not arm land-in-shape: {land_exc}")
    _BULK_SPAWN_QUEUE.extend(rows)
    if count > 1 and _is_generic_pearl_pool(pool):
        supplement_count = sum(
            row_count
            for row, _row_level, row_count in rows
            if str(row.get("pearl_supplement") or "").strip() == "1"
        )
        if supplement_count:
            _log_info(
                f"Queued balanced {pool} x{count}: "
                f"{count - supplement_count} random parent roll(s) + "
                f"{supplement_count} missing named Pearl(s)."
            )
        else:
            _log_info(f"Queued one native {pool} call for exactly {count} drops.")
    if new_batch:
        _BULK_SPAWN_WAVE_TOTAL = len(_BULK_SPAWN_QUEUE)
        _BULK_SPAWN_WAVE_INDEX = 1
        if _spawn_queue_is_selected():
            display = str(entry.get("display_name") or pool or "item").strip()
            _log_info(f"Spawn selected: {display} x{count} @ {level}")
    else:
        _BULK_SPAWN_WAVE_TOTAL += len(rows)
    _schedule_bulk_shared_tick()


def queue_all_filtered_item_pools(
    search: str = "",
    category: str = "All",
    *,
    level: int = DEFAULT_ITEM_LEVEL,
    count: int = 1,
    gap_sec: float | None = None,
    per_tick: int | None = None,
    random_spread: bool | None = None,
    shape: str = "none",
    settle: str = "none",
    drop_height: float = 520.0,
    line_length: float = 900.0,
    radius: float = 220.0,
    spacing: float = 140.0,
    z_bias: float = 30.0,
    spawn_then_shape: bool = False,
    stay_in_air: bool = True,
    peel_after: float = 0.0,
    land_profile: str = "bulk",
    fill_until_complete: bool = False,
    shape_text: str = "",
    exclude_currency: bool = False,
    exclude_ai_guns: bool = False,
) -> int:
    """Queue filtered pools for paced spawning outside the BLImGui callback."""
    global _BULK_SPAWN_OK, _BULK_SPAWN_FAIL, _BULK_SPAWN_SUMMARY_PENDING
    global _BULK_SPAWN_REMAINING, _BULK_SPAWN_WAVE_TOTAL, _BULK_SPAWN_WAVE_INDEX
    global _BULK_SPAWN_WAVE_COOLDOWN_UNTIL, _BULK_SPAWN_SEGMENT_COUNT, _BULK_SPAWN_SEGMENT_PAUSE_UNTIL
    global _BULK_SPAWN_LAST_STEP
    global _BULK_CLEANUP_DUE_AT, _BULK_SPAWNS_SINCE_CLEANUP, _BULK_CLEANUP_BASELINE_READY
    global _BULK_TEST_CLEANUP_ENABLED
    global _BULK_SPAWN_SUMMARY_DEFER_UNTIL, _BULK_FINISH_SETTLED, _SINGULAR_PATH_TEST

    shape_l = str(shape or "none").strip().lower()
    settle_l = str(settle or "none").strip().lower()
    shape_text_l = str(shape_text or "").strip()
    if shape_text_l or shape_l in ("text", "text_shape", "words", "word", "write"):
        try:
            from .loot_shapes import set_shape_text  # noqa: PLC0415

            shape_text_l = set_shape_text(shape_text_l)
            shape_l = "text"
            shape = "text"
        except Exception:
            pass
    if shape_l not in ("", "none", "off", "no", "vanilla") or settle_l not in ("", "none"):
        random_spread = False
        try:
            from .loot_shapes import _party_count

            in_coop = int(_party_count()) >= 2
        except Exception:
            in_coop = False
        if per_tick is None:
            per_tick = 1 if in_coop else 2
        else:
            per_tick = max(1, min(2 if in_coop else 3, int(per_tick)))
        if gap_sec is None and not in_coop:
            gap_sec = 0.06
    if random_spread is None:
        random_spread = False
    configure_bulk_spawn(gap_sec=gap_sec, per_tick=per_tick, random_spread=random_spread)
    if _BULK_SPAWN_QUEUE or _BULK_SPAWN_REMAINING or _SPAWN_VERIFY_QUEUE:
        raise RuntimeError(
            f"A spawn batch is already running ({len(_BULK_SPAWN_QUEUE)} active, "
            f"{len(_BULK_SPAWN_REMAINING)} pending, "
            f"{len(_SPAWN_VERIFY_QUEUE)} verifying). Wait for it to finish."
        )

    entries = filter_item_pools(
        search,
        category,
        limit=0,
        exclude_currency=bool(exclude_currency),
        exclude_ai_guns=bool(exclude_ai_guns),
    )
    if not entries:
        raise RuntimeError("No loot pools match the current search/category filter.")
    # Spawn All Filtered must queue the FULL filtered list (same as GitHub 3.8.0 /
    # sqbt-v1.1.1). Do not shrink All to "named L5 + shiny + pearl" — that cut
    # ~450 rows (ammo/type/manufacturer/etc.) and made dumps look like only ~305 ran.
    _ensure_bulk_spawn_hook()
    _SINGULAR_PATH_TEST = False
    requested_count = max(1, min(int(count), MAX_SPAWN_ALL_COUNT))
    # Spawn All is a health-check pass, not a mass-loot multiplier.  One result
    # per row is enough to exercise every route and keeps a stale UI count from
    # multiplying a large catalog into thousands of simultaneous pickups.
    count = SPAWN_ALL_TEST_COUNT
    if requested_count != count:
        _log_warning(
            f"Spawn All safety mode uses x{count} per pool (requested x{requested_count}). "
            "Spawn the selected pool separately when multiple copies are needed."
        )
    level = max(1, int(level))
    # Prefer steady 1/tick pacing — UI "items per tick" of 2+ reads as bursty.
    if per_tick is None or int(per_tick) <= 0:
        per_tick = 1
    else:
        per_tick = max(1, min(2, int(per_tick)))
    if gap_sec is None:
        gap_sec = float(SPAWN_ALL_DEFAULT_GAP_SEC)
    configure_bulk_spawn(gap_sec=gap_sec, per_tick=per_tick, random_spread=random_spread)
    # Fresh session counters so summary "This session failures" isn't yesterday's 291.
    clear_spawn_log_session(clear_files=False)
    _BULK_SPAWN_OK = 0
    _BULK_SPAWN_FAIL = 0
    _BULK_SPAWN_SUMMARY_PENDING = True
    _BULK_SPAWN_SUMMARY_DEFER_UNTIL = 0.0
    _BULK_FINISH_SETTLED = False
    _SPAWN_VERIFY_QUEUE.clear()
    _SPAWN_PENDING_KEYS.clear()
    _BULK_SPAWN_REMAINING.clear()
    _BULK_SPAWN_WAVE_INDEX = 0
    _BULK_SPAWN_WAVE_COOLDOWN_UNTIL = 0.0
    _BULK_SPAWN_SEGMENT_COUNT = 0
    _BULK_SPAWN_SEGMENT_PAUSE_UNTIL = 0.0
    _BULK_SPAWN_LAST_STEP = 0.0
    _BULK_CLEANUP_DUE_AT = 0.0
    _BULK_SPAWNS_SINCE_CLEANUP = 0
    _BULK_PROTECTED_LOOT_KEYS.clear()
    _BULK_CLEANUP_BASELINE_READY = False
    # Never delete Spawn All loot — cleanup made piles look like "only a couple dropped"
    # and caused stop/start hitching every 16 items.
    shaping = shape_l not in ("", "none", "off", "no", "vanilla") or settle_l not in ("", "none")
    _BULK_TEST_CLEANUP_ENABLED = False
    try:
        _SPAWN_LOG_DIR.mkdir(parents=True, exist_ok=True)
        _SPAWN_BATCH_TRACE.write_text("", encoding="utf-8")
        _SPAWN_BATCH_CHECKPOINT.write_text(
            "Spawn All queued; first START checkpoint pending.\n",
            encoding="utf-8",
        )
    except OSError as exc:
        _log_warning(f"Could not initialize Spawn All trace: {exc}")
    from .item_spawn.loot_verify import reset_claimed_loot_keys
    from .item_spawn.pearl_spawn_ring import set_bulk_pile_mode

    reset_claimed_loot_keys()
    set_bulk_pile_mode(not _BULK_RANDOM_SPREAD)

    all_rows = _dedupe_spawn_all_rows(entries, level=level, count=count)
    all_rows = _extend_rows_until_shape_complete(
        all_rows,
        shape=shape_l,
        profile=land_profile,
        fill=bool(fill_until_complete),
    )
    total_drops = _spawn_row_drop_total(all_rows)
    _BULK_SPAWN_WAVE_TOTAL = len(all_rows)
    if _BULK_SPAWN_WAVE_TOTAL >= int(SPAWN_ALL_MASS_AUTO_GAP_THRESHOLD):
        _apply_mass_spawn_throttle(shaping=shaping)
    wave_size = max(1, int(SPAWN_ALL_WAVE_SIZE))
    first_wave = all_rows[:wave_size]
    _BULK_SPAWN_REMAINING[:] = all_rows[wave_size:]
    _BULK_SPAWN_WAVE_INDEX = 1
    queued = _enqueue_spawn_all_wave(first_wave)
    try:
        from .loot_shapes import begin_spawn_landing, pause_catch_for_shape

        begin_spawn_landing(
            max(1, int(total_drops)),
            shape=shape_l,
            settle=settle,
            drop_height=drop_height,
            line_length=line_length,
            radius=radius,
            spacing=spacing,
            z_bias=z_bias,
            spawn_then_shape=spawn_then_shape,
            stay_in_air=stay_in_air,
            peel_after=peel_after,
            land_profile=land_profile,
            shape_text=shape_text_l,
        )
        pause_catch_for_shape(shape_l)
    except Exception as land_exc:
        _log_warning(f"Could not arm Spawn All land-in-shape: {land_exc}")
    _schedule_bulk_shared_tick()
    wave_count = (
        1 + (len(_BULK_SPAWN_REMAINING) + wave_size - 1) // wave_size
        if _BULK_SPAWN_REMAINING
        else 1
    )
    wave_note = ""
    if _BULK_SPAWN_REMAINING:
        wave_note = (
            f" Auto-continues in {wave_count} wave(s) of up to {wave_size} "
            f"({len(_BULK_SPAWN_REMAINING)} more after this wave)."
        )
    _log_info(
        f"Spawn All: wave 1/{wave_count} — "
        f"{queued}/{_BULK_SPAWN_WAVE_TOTAL} pools (x{count}, level {level}, "
        f"up to {_BULK_SPAWN_STEPS_PER_TICK} per tick @ {_BULK_SPAWN_MIN_GAP_SEC}s gap).{wave_note}"
    )
    return _BULK_SPAWN_WAVE_TOTAL


def queue_singular_path_test_filtered(
    search: str = "",
    category: str = "All",
    *,
    level: int = DEFAULT_ITEM_LEVEL,
    gap_sec: float | None = None,
    named_only: bool = True,
) -> int:
    """Queue filtered rows using Spawn Selected semantics (feet verify, 1 at a time).

    Unlike Spawn All Filtered this never mass-throttles, never skips verify, and
    waits for each feet check before the next item. Defaults to named catalog / >
    rows so ammo/type pools are not burned through by accident.
    """
    global _BULK_SPAWN_OK, _BULK_SPAWN_FAIL, _BULK_SPAWN_SUMMARY_PENDING
    global _BULK_SPAWN_REMAINING, _BULK_SPAWN_WAVE_TOTAL, _BULK_SPAWN_WAVE_INDEX
    global _BULK_SPAWN_WAVE_COOLDOWN_UNTIL, _BULK_SPAWN_SEGMENT_COUNT, _BULK_SPAWN_SEGMENT_PAUSE_UNTIL
    global _BULK_SPAWN_LAST_STEP
    global _BULK_CLEANUP_DUE_AT, _BULK_SPAWNS_SINCE_CLEANUP, _BULK_CLEANUP_BASELINE_READY
    global _BULK_TEST_CLEANUP_ENABLED
    global _BULK_SPAWN_SUMMARY_DEFER_UNTIL, _BULK_FINISH_SETTLED, _SINGULAR_PATH_TEST

    if _BULK_SPAWN_QUEUE or _BULK_SPAWN_REMAINING or _SPAWN_VERIFY_QUEUE:
        raise RuntimeError(
            f"A spawn batch is already running ({len(_BULK_SPAWN_QUEUE)} active, "
            f"{len(_BULK_SPAWN_REMAINING)} pending, "
            f"{len(_SPAWN_VERIFY_QUEUE)} verifying). Wait for it to finish."
        )

    entries = filter_item_pools(search, category, limit=0)
    if named_only:
        entries = [row for row in entries if _is_named_singular_row(row)]
    if not entries:
        hint = (
            "No named items match (catalog / > rows). "
            "Narrow search/category, or turn off Named only."
            if named_only
            else "No loot pools match the current search/category filter."
        )
        raise RuntimeError(hint)

    _ensure_bulk_spawn_hook()
    # Same feet path as Spawn Selected — never shape/mass shortcuts.
    gap = float(_SINGULAR_PATH_TEST_GAP_SEC if gap_sec is None else gap_sec)
    gap = max(float(_SINGULAR_PATH_TEST_GAP_SEC), min(2.0, gap))
    configure_bulk_spawn(gap_sec=gap, per_tick=1, random_spread=False)
    level = max(1, int(level))
    _SINGULAR_PATH_TEST = True
    _BULK_SPAWN_OK = 0
    _BULK_SPAWN_FAIL = 0
    _BULK_SPAWN_SUMMARY_PENDING = True
    _BULK_SPAWN_SUMMARY_DEFER_UNTIL = 0.0
    _BULK_FINISH_SETTLED = False
    _SPAWN_VERIFY_QUEUE.clear()
    _SPAWN_PENDING_KEYS.clear()
    _BULK_SPAWN_REMAINING.clear()
    _BULK_SPAWN_WAVE_INDEX = 1
    _BULK_SPAWN_WAVE_COOLDOWN_UNTIL = 0.0
    _BULK_SPAWN_SEGMENT_COUNT = 0
    _BULK_SPAWN_SEGMENT_PAUSE_UNTIL = 0.0
    _BULK_SPAWN_LAST_STEP = 0.0
    _BULK_CLEANUP_DUE_AT = 0.0
    _BULK_SPAWNS_SINCE_CLEANUP = 0
    _BULK_PROTECTED_LOOT_KEYS.clear()
    _BULK_CLEANUP_BASELINE_READY = False
    # Keep loot so fails stay inspectable; no mid-batch delete.
    _BULK_TEST_CLEANUP_ENABLED = False
    try:
        _SPAWN_LOG_DIR.mkdir(parents=True, exist_ok=True)
        _SPAWN_BATCH_TRACE.write_text("", encoding="utf-8")
        _SPAWN_BATCH_CHECKPOINT.write_text(
            "Singular path test queued; first START checkpoint pending.\n",
            encoding="utf-8",
        )
    except OSError as exc:
        _log_warning(f"Could not initialize singular-test trace: {exc}")

    from .item_spawn.loot_verify import reset_claimed_loot_keys, set_feet_verify_radius
    from .item_spawn.pearl_spawn_ring import set_bulk_pile_mode

    reset_claimed_loot_keys()
    set_bulk_pile_mode(True)
    try:
        set_feet_verify_radius(2200.0)
    except Exception:
        pass
    # Wipe any leftover silhouette/catch from a prior shaped Spawn All so
    # singular feet drops are not teleported into old slots mid-test.
    try:
        from .loot_shapes import clear_spawn_landing

        clear_spawn_landing()
    except Exception:
        pass

    seen_catalog: set[str] = set()
    seen_pool: set[str] = set()
    all_rows: list[tuple[dict[str, str], int, int]] = []
    for entry in entries:
        catalog = str(entry.get("catalog_key") or "").strip().lower()
        pool = str(entry.get("itempool") or "").strip().lower()
        if catalog:
            if catalog in seen_catalog:
                continue
            seen_catalog.add(catalog)
        elif pool:
            if pool in seen_pool:
                continue
            seen_pool.add(pool)
        all_rows.append((_normalize_spawn_all_entry(entry), level, 1))

    if not all_rows:
        _SINGULAR_PATH_TEST = False
        raise RuntimeError("No singular rows left after dedupe.")

    _BULK_SPAWN_WAVE_TOTAL = len(all_rows)
    _BULK_SPAWN_QUEUE.extend(all_rows)
    try:
        from .loot_shapes import begin_spawn_landing, clear_spawn_landing, pause_catch_for_shape

        clear_spawn_landing()
        begin_spawn_landing(
            max(1, int(_BULK_SPAWN_WAVE_TOTAL)),
            shape="none",
            settle="none",
            drop_height=520.0,
            line_length=900.0,
            radius=220.0,
            spacing=140.0,
            z_bias=30.0,
            spawn_then_shape=False,
            stay_in_air=True,
            peel_after=0.0,
            land_profile="bulk",
        )
        pause_catch_for_shape("none")
    except Exception as land_exc:
        _log_warning(f"Could not arm singular-test landing: {land_exc}")

    _schedule_bulk_shared_tick()
    scope = f"category={category or 'All'}"
    if search:
        scope += f", search={search!r}"
    named_note = "named only" if named_only else "all filtered rows"
    _log_info(
        f"Singular test: {_BULK_SPAWN_WAVE_TOTAL} item(s) ({named_note}, {scope}) "
        f"— Spawn Selected path, 1/tick, {gap:.2f}s gap, feet verify each. "
        "Stop spawn list cancels. World loot only (not mail)."
    )
    return _BULK_SPAWN_WAVE_TOTAL


def grant_all_filtered_item_pools_rewards(
    search: str = "",
    category: str = "All",
) -> tuple[int, int]:
    """Send @U serials via loyalty rewards for filtered rows that have catalog serials."""
    from .serial_rewards import grant_serials_via_loyalty_rewards

    from .standalone_spawning import catalog_spawn_row

    serials: list[str] = []
    for entry in filter_item_pools(search, category, limit=0):
        catalog = str(entry.get("catalog_key", "")).strip().lower()
        serial = None
        if catalog:
            row = catalog_spawn_row(catalog)
            serial = row.get("serial")
        if isinstance(serial, str) and serial.startswith("@U"):
            serials.append(serial)
    if not serials:
        raise RuntimeError("No @U serials for current filter (pearls / Raid 2 comps only).")
    grant_serials_via_loyalty_rewards(serials, all_players=False)
    return len(serials), 0


from mods_base import command


@command(
    "sqbt_spawn_cancel",
    description="Cancel an in-progress Spawn All / singular-test batch (stops queued waves).",
)
def _cmd_sqbt_spawn_cancel(_args: object = None) -> None:
    cancel_bulk_spawn_batch(log=True)


@command(
    "sqbt_spawn_dump",
    description="Refresh spawn OK/FAIL summary and print log paths (after Spawn All / pool tests).",
)
def _cmd_sqbt_spawn_dump(_args: object = None) -> None:
    dump_spawn_log(log_to_console=True, full=True)


@command(
    "sqbt_spawn_log_clear",
    description="Clear Squ1ggsBoostingTools spawn_test.jsonl and spawn_failures.log.",
)
def _cmd_sqbt_spawn_log_clear(_args: object = None) -> None:
    clear_spawn_log_session(clear_files=True)


@command(
    "sqbt_spawn_singular_test",
    description="Removed — use Spawn All Filtered or Spawn Selected.",
)
def _cmd_sqbt_spawn_singular_test(args: object = None) -> None:
    del args
    _log_warning(
        "sqbt_spawn_singular_test removed. Use Spawn All Filtered or Spawn Selected."
    )
