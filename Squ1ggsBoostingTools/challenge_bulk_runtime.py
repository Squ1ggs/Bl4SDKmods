"""Nonblocking direct completion for selected non-UVHM challenge categories."""
from __future__ import annotations

import time
from typing import Any

from unrealsdk import logging

from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate
from .uvhm_progression import TargetIdentity, resolve_lobby_pc, selected_lobby_identity, snapshot_lobby_identities


_PREFIX = "[Squ1ggs Boosting Tools | Challenges]"
_pending: tuple[int, str, tuple[str, ...]] | None = None
_pending_rows: tuple[tuple[str, int], ...] | None = None
_targets: tuple[TargetIdentity, ...] = ()
_for_all = False
_rows: tuple[tuple[str, int], ...] = ()
_index = 0
_target_index = 0
_ok = 0
_failed = 0
_active = False
_message = "Idle."
_last_error = ""
_last_tick_at = 0.0
# Brief EXE sticky after finish/cancel so the progress bar can show Complete then hide.
# Keep short — long sticky + status polls used to re-arm the floating bar forever.
_sticky_phase = ""
_sticky_until = 0.0
_STICKY_COMPLETE_SEC = 2.0
_STICKY_CANCEL_SEC = 1.2
# Remote-target pacing only. Host-local jobs stay fast even in a live lobby —
# COS/library writes do not need the guest replication throttle.
_remote_target_pacing = False
# Identity keys for players who left mid-job — skip without failing every remaining token.
_dead_targets: set[str] = set()
# Transient resolve misses (guest join reshuffles PlayerArray). Local host never
# permanently dies from one None; remotes need several consecutive misses.
_resolve_misses: dict[str, int] = {}
_RESOLVE_MISS_KILL = 8
_skipped = 0
# ULM challenge_complete._queue_tick_config baseline:
#   solo: batch=1, pause ~50ms
#   lobby: batch=2, pause every 3 (~35ms)
# Local 6/tick drained All non-UVHM in ~11s and reward-flooded the session (crash).
# Remote 3/tick @ 70ms outran guest reward posting — keep remote at 2@100ms.
_CHALLENGE_TICK_GAP_LOCAL = 0.05
_CHALLENGE_TICK_GAP_REMOTE = 0.10
_CHALLENGE_BATCH_LOCAL = 1
_CHALLENGE_BATCH_REMOTE = 2
# ULM-style: do not log every apply (that flooded sqbt_runtime + force-flush on status polls).
_PROGRESS_LOG_EVERY = 50
_progress_log_counter = 0
# UI bar steps — jump every 50 so Complete ALL non-UVHM stays visibly moving.
_ui_milestone_index = 0
# MAX ALL: when challenges + UVHM both checked, UVHM starts after challenges finish
# (never stack both starts — that was skipped entirely before).
_followup_uvhm: dict[str, Any] | None = None
_followup_log_at = 0.0


def arm_followup_uvhm(*, for_all: bool, player_index: int = 0, max_rank: int = 7) -> None:
    """Queue UVHM to start once the current bulk challenge job completes."""
    global _followup_uvhm, _followup_log_at
    from . import give_everything

    if give_everything.attach_challenge_uvhm_followup():
        _followup_uvhm = None
        return
    _followup_uvhm = {
        "for_all": bool(for_all),
        "player_index": int(player_index),
        "max_rank": max(1, min(7, int(max_rank or 7))),
    }
    _followup_log_at = 0.0


def clear_followup_uvhm() -> None:
    global _followup_uvhm, _followup_log_at
    _followup_uvhm = None
    _followup_log_at = 0.0


def _fire_followup_uvhm() -> None:
    """Start armed UVHM after challenges. Retries next tick if still blocked."""
    global _followup_uvhm, _message, _followup_log_at
    pending = _followup_uvhm
    if not pending:
        return
    # Apply loop must be fully idle (Complete sticky is fine — UVHM gates on running/queued).
    if _active or _pending is not None:
        return
    try:
        from . import uvhm_runtime
        from . import hold_session

        max_rank = int(pending.get("max_rank") or 7)
        # quiet=True: cooldown/busy retries must not paint a fake UVHM error sticky.
        if pending.get("for_all"):
            ok = uvhm_runtime.request_all(confirmed=True, max_rank=max_rank, quiet=True)
        else:
            ok = uvhm_runtime.request_selected(
                int(pending.get("player_index") or 0),
                max_rank=max_rank,
                quiet=True,
            )
        if ok:
            _followup_uvhm = None
            _followup_log_at = 0.0
            try:
                hold_session.arm_for_job("uvhm")
            except Exception:
                pass
            _log("UVHM 1–7 starting after challenges.")
            # Keep Complete sticky/message so the EXE paints Finished; UVHM has its own row.
        else:
            # Keep armed — next idle tick retries (cooldown / transient busy).
            st = uvhm_runtime.status()
            reason = str(st.get("message") or "waiting")
            # Only overwrite when Complete sticky already expired.
            if not (_sticky_phase == "complete" and time.monotonic() < float(_sticky_until)):
                _message = f"Starting UVHM next ({reason})"
            now = time.monotonic()
            if now - float(_followup_log_at or 0.0) >= 5.0:
                _followup_log_at = now
                _log(f"UVHM follow-up deferred: {reason}")
    except Exception as exc:
        _log(f"UVHM follow-up error: {type(exc).__name__}: {exc}")


def _milestone_step(total: int) -> int:
    """Bar jumps every 50 completed challenges (min 1 for tiny jobs)."""
    total_i = max(0, int(total or 0))
    if total_i <= 0:
        return 1
    if total_i <= 50:
        return 1
    return 50


def _snap_milestone(raw_index: int, total: int) -> int:
    total_i = max(0, int(total or 0))
    raw = max(0, int(raw_index or 0))
    if total_i <= 0:
        return 0
    if raw >= total_i:
        return total_i
    step = _milestone_step(total_i)
    snapped = (raw // step) * step
    return min(total_i, max(0, snapped))


def _tick_gap() -> float:
    """Seconds between batches. Remote guests stay slower; host-local stays fast."""
    if _remote_target_pacing:
        return float(_CHALLENGE_TICK_GAP_REMOTE)
    return float(_CHALLENGE_TICK_GAP_LOCAL)


def _batch_size() -> int:
    if _remote_target_pacing:
        return int(_CHALLENGE_BATCH_REMOTE)
    return int(_CHALLENGE_BATCH_LOCAL)


def _identity_is_local(identity: TargetIdentity) -> bool:
    """True when the snapshotted identity resolves to the listen-host PC."""
    try:
        from mods_base import get_pc

        local = get_pc()
    except Exception:
        local = None
    if local is None or identity is None:
        return False
    try:
        from .party_helpers import _gbc_resolve_player_display_name
        from .uvhm_progression import _player_state_key

        ps = getattr(local, "PlayerState", None)
        if ps is None:
            return False
        name = _gbc_resolve_player_display_name(ps)
        return _player_state_key(ps, name) == identity.key
    except Exception:
        return False


def _resolve_pc_resilient(identity: TargetIdentity) -> Any:
    """Resolve lobby PC; fall back to local get_pc() when the host identity remaps mid-join."""
    pc = resolve_lobby_pc(identity)
    if pc is not None:
        return pc
    # Guest join can reshuffle PlayerArray for a few ticks so the snapshotted
    # UniqueId key briefly misses — never treat the listen-host as "left".
    try:
        from mods_base import get_pc

        local = get_pc()
    except Exception:
        local = None
    if local is None:
        return None
    try:
        from .party_helpers import _gbc_resolve_player_display_name
        from .uvhm_progression import _player_state_key

        ps = getattr(local, "PlayerState", None)
        if ps is None:
            return None
        name = _gbc_resolve_player_display_name(ps)
        local_key = _player_state_key(ps, name)
        want = str(getattr(identity, "key", "") or "")
        # Same key, or name-key fallback when UniqueId churned to name:…
        if want and (want == local_key or want.casefold() == f"name:{''.join(c for c in name.casefold() if c.isalnum())}"):
            return local
        # Display-name match as last resort for the armed solo/host job.
        if str(getattr(identity, "display_name", "") or "").casefold() == str(name or "").casefold():
            return local
    except Exception:
        pass
    return None


def _mark_resolve_miss(identity: TargetIdentity) -> bool:
    """Return True when the target should be permanently skipped (left lobby)."""
    key = str(getattr(identity, "key", "") or "")
    if not key:
        return False
    if _identity_is_local(identity):
        # Host never permanently dies from a single join-quiet miss.
        _resolve_misses[key] = 0
        return False
    misses = int(_resolve_misses.get(key, 0)) + 1
    _resolve_misses[key] = misses
    if misses < int(_RESOLVE_MISS_KILL):
        return False
    _dead_targets.add(key)
    return True


def _clear_resolve_miss(identity: TargetIdentity) -> None:
    key = str(getattr(identity, "key", "") or "")
    if key:
        _resolve_misses.pop(key, None)

CATEGORY_LABELS: tuple[str, ...] = (
    "All non-UVHM",
    "Vault Hunters — Robo Dealer / Loveless",
    "FL4K / Providence DLC",
    "All DLC / Story Packs",
    "Vault of the Damned",
    "Story challenge flags",
    "Activities",
    "Collectibles",
    "Loot",
    "Weapons",
    "Manufacturers",
    "Combat",
    "Enemies",
    "Elemental",
    "Economy",
    "Character",
    "Shinies",
    "World",
    "Achievements / Misc",
    "Other",
)

# Progress Collectibles grant families (not listed in the main category dropdown).
COLLECTIBLE_FAMILY_LABELS: tuple[str, ...] = (
    "Collectibles — Echo logs",
    "Collectibles — Caches",
    "Collectibles — Shrines",
    "Collectibles — Vault symbols",
    "Collectibles — Speakers",
    "Collectibles — Capsules / Evocariums",
    "Collectibles — Safes",
    "Collectibles — Vault keys",
    "Collectibles — Tutorial discovery",
    "Collectibles — DLC",
)

# Specific category filters. "Other" is computed as leftovers (not matched by any
# rule below). "Combat" is true combat/misc — not every weapon challenge.
_CATEGORY_RULES: dict[str, tuple[str, ...]] = {
    "vault hunters — robo dealer / loveless": (
        "robodealer",
        "robo_dealer",
        "corpohacker",
        "corpo_hacker",
        "loveless",
    ),
    "fl4k / providence dlc": (
        "fl4k",
        "providence",
        "lastresort",
        "last_resort",
        "harmonica",
    ),
    "all dlc / story packs": (
        "_dlc",
        "cowbell_",
        "_cowbell",
        "_banjo_",
        "_cello_",
        "_tuba_",
        "_mandolin_",
        "_harp_",
        "harmonica",
        "_raid1_",
        "_raid2_",
        "providence",
        "lastresort",
        "last_resort",
    ),
    "vault of the damned": (
        "cowbell_",
        "challenge_cowbell_",
        "challenges_achievements_38_cowbell_",
        "challenges_achievements_39_cowbell_",
        "challenges_achievements_40_cowbell_",
        "challenges_achievements_41_cowbell_",
        "challenges_achievements_42_cowbell_",
        "challenges_achievements_43_cowbell_",
        "challenges_achievements_44_cowbell_",
        "challenges_achievements_45_cowbell_",
        "_cowbell_",
    ),
    "story challenge flags": (
        "completemainstory",
        "completesidemissions",
        "challenges_achievements_24_missions_",
        "challenges_achievements_25_missions_",
        "challenges_achievements_26_missions_",
        "challenges_achievements_27_missions_",
        "challenges_achievements_28_missions_",
        "challenges_achievements_29_missions_",
    ),
    "activities": (
        "challenge_tutorial_activity_",
        "challenge_activity_",
        "cowbell_complete_all_activities",
    ),
    "collectibles": (
        "challenge_tutorial_collectible_",
        "challenge_collect_",
        "challenge_echolog_",
    ),
    # Family subsets for Progress → Collectibles grant (still challenge increment).
    # Token stems match Challenge_Collect_* casefold (plural forms).
    "collectibles — echo logs": (
        "challenge_collect_echolog_",
        "challenge_echolog_",
        "challenge_collect_echo_",
        "challenge_collect_recordplayer_",
    ),
    "collectibles — caches": (
        "challenge_collect_caches_",
        "challenge_collect_dahlcaches_",
    ),
    "collectibles — shrines": ("challenge_collect_shrines_",),
    "collectibles — vault symbols": ("vaultsymbols_",),
    "collectibles — speakers": ("challenge_collect_propagandaspeakers_",),
    "collectibles — capsules / evocariums": (
        "challenge_collect_capsules_",
        "challenge_collect_evocariums_",
    ),
    "collectibles — safes": (
        "challenge_collect_safes_",
        "challenge_collect_dlc2_islandsafe_",
    ),
    "collectibles — vault keys": (
        "challenge_collect_vaultkey_",
        "challenge_collect_allkeys",
        "challenge_collect_vaultpower_",
    ),
    "collectibles — tutorial discovery": ("challenge_tutorial_collectible_",),
    "collectibles — dlc": (
        "challenge_collect_dlc1_",
        "challenge_collect_dlc2_",
        "challenge_collect_harmonica_",
        "challenge_collect_cowbell_",
        "challenge_collect_banjo_",
        "challenge_collect_cello_",
        "challenge_collect_tuba_",
        "challenge_collect_mandolin_",
        "challenge_collect_harp_",
    ),
    "loot": ("challenge_loot_",),
    "weapons": (
        "challenge_assault_",
        "challenge_heavyweapon_",
        "challenge_grenade_",
        "challenge_sniper_",
        "challenge_shotgun_",
        "challenge_pistol_",
        "challenge_smg_",
    ),
    "manufacturers": (
        "challenge_jakobs_",
        "challenge_torgue_",
        "challenge_tediore_",
        "challenge_maliwan_",
        "challenge_vladof_",
        "challenge_daedalus_",
        "challenge_order_",
        "challenge_borg_",
        "challenge_ripper_",
        "loyaltychallenge_",
    ),
    "combat": (
        "cowbell_challenges_combat_",
        "_challenge_combat_",
        "challenge_melee_",
        "challenge_shield_",
        "challenge_spareparts_",
        "challenge_repairkit_",
        "challenge_revive",
        "challenge_secondwind",
    ),
    "enemies": (
        "challenge_kill_",
        "challenge_killarmy_",
        "cowbell_challenges_enemies_",
        "_challenge_enemies_",
    ),
    "elemental": (
        "challenge_fire_",
        "challenge_cryo_",
        "challenge_corrosive_",
        "challenge_shock_",
        "challenge_radiation_",
        "challenge_2_status_effects",
        "challenge_all_status_effects",
        "challenge_maliwan_status",
    ),
    "economy": (
        "challenge_sellloot",
        "challenge_tutorial_misc_blackmarket",
        "challenge_getcash",
        "challenge_geteridium",
        "challenge_havecash",
        "challenge_havemorecash",
        "challenge_fishing",
    ),
    "character": (
        "_levelup",
        "challenge_darksiren_",
        "challenge_exosoldier_",
        "challenge_gravitar_",
        "challenge_paladin_",
        "_challenges_characters_",
        "challenge_robodealer_",
    ),
    "shinies": ("challenge_shiny_",),
    "world": (
        "challenge_misc_world",
        "challenge_misc_worldevent",
        "worldevents_",
        "worldboss_",
        "cowbell_challenges_world_",
        "_challenge_world_",
        "_world_rift_",
        "_world_spooky",
    ),
    "achievements / misc": (
        "challenges_achievements_",
        "challenge_misc_",
        "challenge_unlock_",
        "challenge_collection",
        "challenge_firmwareset",
        "challenge_firmwaretransfers",
        "challenge_tutorial_misc_",
    ),
}


def _log(message: str, *, flight: bool = True) -> None:
    try:
        logging.info(f"{_PREFIX} {message}")
    except Exception:
        pass
    if not flight:
        return
    try:
        from . import runtime_log

        runtime_log.note(f"challenges: {message}")
    except Exception:
        pass


def _log_progress(message: str) -> None:
    """Milestone progress only — never per-token (ULM progress_log_every)."""
    global _progress_log_counter
    _progress_log_counter += 1
    if _progress_log_counter <= 3 or _progress_log_counter % max(1, int(_PROGRESS_LOG_EVERY)) == 0:
        _log(message)


def _pc_matches_identity(pc: Any, identity: TargetIdentity) -> bool:
    if pc is None:
        return False
    try:
        from .party_helpers import _gbc_resolve_player_display_name
        from .uvhm_progression import _player_state_key

        ps = getattr(pc, "PlayerState", None)
        if ps is None:
            return False
        name = _gbc_resolve_player_display_name(ps)
        return _player_state_key(ps, name) == identity.key
    except Exception:
        return False


def _apply_one(token: str, amount: int, identity: TargetIdentity, owner: Any) -> str:
    """Apply one challenge. Returns 'ok' | 'skip' | 'retry' | raises on hard failure."""
    from .challenge_increment import (
        challenge_already_complete,
        describe_target,
        increment_challenge,
    )

    key = str(getattr(identity, "key", "") or "")
    if key and key in _dead_targets:
        return "skip"
    pc = _resolve_pc_resilient(identity)
    if pc is None:
        if _mark_resolve_miss(identity):
            _log(f"Skip {identity.display_name} (left / unresolvable) for remaining challenges.")
            return "skip"
        # Transient miss (guest join) — do not burn the token / advance the bar.
        return "retry"
    _clear_resolve_miss(identity)
    # Soft rematch after join — UniqueId key can churn; name match still ok.
    if not _pc_matches_identity(pc, identity) and not _identity_is_local(identity):
        try:
            from .party_helpers import _gbc_resolve_player_display_name

            ps = getattr(pc, "PlayerState", None)
            name = _gbc_resolve_player_display_name(ps) if ps is not None else ""
            if str(getattr(identity, "display_name", "") or "").casefold() != str(name or "").casefold():
                if _mark_resolve_miss(identity):
                    _log(f"Skip {identity.display_name} (identity mismatch) for remaining challenges.")
                    return "skip"
                return "retry"
        except Exception:
            if _mark_resolve_miss(identity):
                _log(f"Skip {identity.display_name} (identity mismatch) for remaining challenges.")
                return "skip"
            return "retry"
    # Host-local: skip already-done to avoid Reward Center floods on re-run.
    # Remotes: IsChallengeCompleteForPlayer is often wrong/stale (fresh guests were
    # skipping ~half the catalog and looking "done" while UI stayed empty).
    is_local = _identity_is_local(identity)
    if is_local:
        try:
            if challenge_already_complete(pc, token):
                return "skip"
        except Exception:
            pass
    if not increment_challenge(pc, token, amount, owner_pc=owner, state_writes=is_local):
        raise RuntimeError(f"challenge increment failed for {describe_target(pc)}")
    # No per-apply flight log — large All non-UVHM (~1200) flooded disk + status flush.
    return "ok"


def _is_uvhm(token: str) -> bool:
    return "uvh" in token.casefold().replace("-", "_")


def _is_vault_card_or_junk(token: str) -> bool:
    """Vault-card dailies/weeklies + demo/test noise — not part of All non-UVHM boosts."""
    key = token.casefold().replace("-", "_")
    if key.startswith(("vc1_", "vc2_", "vc3_", "vc4_", "vc5_", "vcchallenge_")):
        return True
    if "vault_card" in key:
        return True
    if "_demo_" in key or key.endswith("_demo"):
        return True
    if "echolocationtest" in key:
        return True
    return False


def _token_matches_rules(token_key: str, rules: tuple[str, ...]) -> bool:
    return any(rule in token_key for rule in rules)


def _all_specific_rules() -> tuple[str, ...]:
    rules: list[str] = []
    seen: set[str] = set()
    for key, values in _CATEGORY_RULES.items():
        if key in ("other", "all non-uvhm"):
            continue
        for rule in values:
            if rule not in seen:
                seen.add(rule)
                rules.append(rule)
    return tuple(rules)


def _iter_catalog_challenges() -> list[tuple[str, int]]:
    from .data_files import read_data_json  # noqa: PLC0415

    raw = read_data_json("challenge_catalog.json")
    source = raw.get("challenges") if isinstance(raw, dict) else None
    if not isinstance(source, list):
        raise ValueError("challenge catalog has no challenges list")
    result: list[tuple[str, int]] = []
    seen: set[str] = set()
    for row in source:
        if not isinstance(row, dict):
            continue
        token = str(row.get("token") or "").strip()
        if not token or token in seen or _is_uvhm(token) or _is_vault_card_or_junk(token):
            continue
        # Aggregate parents cascade into many child rewards at once.
        if token.startswith("ChallengeParent_"):
            continue
        try:
            goal = max(1, int(row.get("goal") or 1))
        except (TypeError, ValueError):
            goal = 1
        seen.add(token)
        result.append((token, goal))
    return result


def _load_rows(category: str) -> tuple[tuple[str, int], ...]:
    selected_category = str(category or "All non-UVHM").strip()
    category_key = selected_category.casefold()
    source = _iter_catalog_challenges()
    if category_key in ("all non-uvhm", "all"):
        return tuple(source)

    if category_key == "other":
        specific = _all_specific_rules()
        return tuple(
            (token, goal)
            for token, goal in source
            if not _token_matches_rules(token.casefold().replace("-", "_"), specific)
        )

    rules = _CATEGORY_RULES.get(category_key)
    if not rules:
        raise ValueError(f"Unknown challenge category {selected_category!r}.")
    result: list[tuple[str, int]] = []
    for token, goal in source:
        token_key = token.casefold().replace("-", "_")
        if _token_matches_rules(token_key, rules):
            result.append((token, goal))
    return tuple(result)


def _load_token_rows(tokens: list[str] | tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    wanted: list[str] = []
    seen: set[str] = set()
    for raw in tokens:
        token = str(raw or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        wanted.append(token)
    if not wanted:
        raise ValueError("No challenge tokens selected.")
    goals = {token: goal for token, goal in _iter_catalog_challenges()}
    result: list[tuple[str, int]] = []
    for token in wanted:
        if token not in goals:
            raise ValueError(f"Challenge token is unavailable or excluded: {token}")
        result.append((token, int(goals[token])))
    return tuple(result)


def catalog_rows(search: str = "", category: str = "All non-UVHM", *, limit: int = 5000) -> tuple[tuple[str, int], ...]:
    """Filtered challenge rows for UI pickers (non-UVHM only)."""
    rows = _load_rows(category)
    needle = str(search or "").strip().casefold()
    if needle:
        rows = tuple(
            (token, goal)
            for token, goal in rows
            if needle in token.casefold() or needle in token.replace("_", " ").casefold()
        )
    cap = max(1, min(int(limit or 5000), 5000))
    return rows[:cap]


def challenge_display_name(token: str) -> str:
    text = str(token or "").strip()
    if not text:
        return ""
    parts = text.replace("-", "_").split("_")
    if parts and parts[0].casefold() in ("challenge", "challenges", "cowbell"):
        parts = parts[1:]
    pretty = " ".join(p for p in parts if p)
    return pretty.replace("  ", " ").strip()


def _target_label() -> str:
    if _for_all:
        return "All players"
    if len(_targets) == 1:
        return _targets[0].display_name
    if _targets:
        return f"{len(_targets)} players"
    return ""


def request_selected(
    player_index: int,
    category: str,
    *,
    confirmed: bool,
    tokens: list[str] | tuple[str, ...] | None = None,
) -> bool:
    """Queue bulk or selected-token completion. ``player_index == -1`` means all lobby players."""
    global _pending, _pending_rows, _rows, _index, _ok, _failed, _skipped, _message, _last_error
    global _progress_log_counter, _ui_milestone_index
    if not confirmed:
        _message = "A second confirmation click is required."
        return False
    world, _gs = _gbc_session_world_and_gamestate()
    if not _gbc_is_listen_host_world(world):
        _message = "Challenge completion needs the listen host (you must be hosting the lobby)."
        return False
    try:
        from . import uvhm_runtime

        uvhm = uvhm_runtime.status()
        if bool(uvhm.get("running") or uvhm.get("queued")):
            _message = (
                "Complete ALL / bulk challenges cannot start while UVHM is running. "
                "Wait for UVHM to finish or cancel it first."
            )
            return False
    except Exception:
        pass
    if _active or _pending is not None:
        _message = "Another non-UVHM challenge workflow is already active."
        return False
    # Fresh challenge job — drop any stale MAX ALL UVHM follow-up from a prior run.
    clear_followup_uvhm()
    _clear_sticky()
    cleaned_tokens: list[str] = []
    if tokens:
        for raw in tokens:
            token = str(raw or "").strip()
            if token and token not in cleaned_tokens:
                cleaned_tokens.append(token)
    # Load catalog on the bridge thread so the progress bar gets a real total
    # immediately — waiting until the HUD tick left the EXE stuck on "Starting…".
    try:
        rows = _load_token_rows(cleaned_tokens) if cleaned_tokens else _load_rows(str(category))
        if not rows:
            _message = f"No non-UVHM challenges matched {category!r}."
            return False
    except Exception as exc:
        _message = f"Could not load challenges: {exc}"
        _last_error = str(exc)
        return False
    if not cleaned_tokens and str(category).strip().casefold() in ("all", "all non-uvhm", "world"):
        from . import give_everything

        # Give everything already owns its final turn-in. Standalone bulk
        # actions need the same registration step and identity protection.
        give_everything.track_challenge_registration(int(player_index))
    _pending = (int(player_index), str(category), tuple(cleaned_tokens))
    _pending_rows = rows
    _rows = rows
    _index = 0
    _ok = 0
    _failed = 0
    _skipped = 0
    _progress_log_counter = 0
    _ui_milestone_index = 0
    _dead_targets.clear()
    _resolve_misses.clear()
    who = "all players" if int(player_index) < 0 else f"player index {int(player_index)}"
    if cleaned_tokens:
        _message = f"Queued {len(rows)} selected challenge(s) for {who} — waiting for world tick…"
    else:
        _message = f"Queued {len(rows)} · {category} for {who} — waiting for world tick…"
    return True


def _arm_sticky(phase: str, message: str) -> None:
    global _sticky_phase, _sticky_until, _message
    key = str(phase or "").strip().lower()
    _sticky_phase = key
    hold = float(_STICKY_CANCEL_SEC if key == "cancelled" else _STICKY_COMPLETE_SEC)
    _sticky_until = time.monotonic() + hold
    if message:
        _message = str(message)


def _clear_sticky() -> None:
    global _sticky_phase, _sticky_until
    _sticky_phase = ""
    _sticky_until = 0.0


def cancel() -> bool:
    global _pending, _pending_rows, _active, _message
    if _pending is not None:
        clear_followup_uvhm()
        _pending = None
        _pending_rows = None
        _arm_sticky("cancelled", "Queued request cancelled.")
        return True
    if not _active:
        # Idle Stop must NOT wipe an armed MAX ALL UVHM follow-up — that used to
        # silently kill UVHM after challenges finished ("Nothing to cancel").
        return False
    clear_followup_uvhm()
    _active = False
    _pending_rows = None
    _arm_sticky(
        "cancelled",
        f"Cancelled after {_index}/{len(_rows)} challenges — remaining were not applied.",
    )
    return True


def status() -> dict[str, Any]:
    global _ui_milestone_index, _message
    sticky_live = bool(_sticky_phase) and time.monotonic() < float(_sticky_until)
    if not sticky_live and _sticky_phase:
        # Drop terminal copy so EXE "Cancelled…" / "Complete:" text cannot
        # keep the floating bar up after sticky ends.
        if _sticky_phase in ("cancelled", "complete") and not _active and _pending is None:
            _message = "Idle."
        _clear_sticky()
    live = bool(_active or _pending is not None)
    phase = "running" if live else ("idle" if not sticky_live else str(_sticky_phase))
    if sticky_live and not live:
        phase = str(_sticky_phase)
    token = _rows[_index][0] if _active and 0 <= _index < len(_rows) else ""
    # Sticky keeps active for a brief Complete/Cancel flash only — never claim running.
    sticky_busy = sticky_live and phase in ("complete", "cancelled")
    n_targets = max(1, len(_targets))
    rows_n = len(_rows)
    # Multi-seat jobs: bar spans every player × catalog (sequential seats).
    total_units = rows_n * n_targets if n_targets > 1 else rows_n
    if live or sticky_live:
        seat = min(max(0, int(_target_index)), max(0, n_targets - 1))
        cursor = min(max(0, int(_index)), rows_n)
        raw_index = min(
            total_units,
            max(
                seat * rows_n + cursor,
                int(_ok) + int(_failed) + int(_skipped),
            ),
        )
    else:
        raw_index = 0
    # Distinct phase while waiting to arm so the EXE does not look "stuck queued".
    if _pending is not None and not _active:
        phase = "queued"
    # Smooth bar = real cursor. Milestone snap was freezing the EXE at ~15% for long jobs.
    if phase == "complete" or (not live and sticky_busy and phase == "complete"):
        bar_index = total_units
        _ui_milestone_index = bar_index
    elif live or sticky_busy:
        bar_index = int(raw_index)
        if bar_index > int(_ui_milestone_index):
            _ui_milestone_index = bar_index
    else:
        bar_index = 0
        _ui_milestone_index = 0
    current_name = ""
    if _targets and 0 <= int(_target_index) < len(_targets):
        current_name = str(getattr(_targets[_target_index], "display_name", "") or "")
    return {
        "active": bool(live or sticky_busy),
        "queued": _pending is not None,
        "running": bool(_active),
        "phase": phase,
        "target": _target_label(),
        "current_target": current_name,
        "for_all": bool(_for_all),
        "index": bar_index,
        "progress_index": bar_index,
        "raw_index": raw_index,
        "milestone_step": 1,
        "target_index": _target_index,
        "target_total": len(_targets),
        "total": total_units,
        "progress_total": total_units,
        "catalog_total": rows_n,
        "ok": _ok,
        "failed": _failed,
        "skipped": _skipped,
        "unavailable_targets": [str(getattr(target, "display_name", "") or target.key)
                                for target in _targets if str(target.key) in _dead_targets],
        "token": token,
        "message": _message,
        "last_error": _last_error,
        "followup_uvhm": bool(_followup_uvhm),
        "categories": list(CATEGORY_LABELS),
    }


def _consume_request() -> None:
    global _pending, _pending_rows, _targets, _for_all, _rows, _index, _target_index
    global _ok, _failed, _skipped, _active, _message, _last_error, _remote_target_pacing
    request = _pending
    if request is None:
        return
    # Keep queue until start succeeds (same pattern as UVHM).
    world, _gs = _gbc_session_world_and_gamestate()
    if not _gbc_is_listen_host_world(world):
        _message = (
            f"Queued {len(_rows) or len(_pending_rows or ())} challenges — "
            "waiting for listen-host world (stay in lobby / unpause)."
        )
        return
    player_index, category, tokens = request
    try:
        rows = _pending_rows if _pending_rows is not None else (
            _load_token_rows(tokens) if tokens else _load_rows(category)
        )
        if not rows:
            raise ValueError(f"No non-UVHM challenges matched {category!r}.")
        if int(player_index) < 0:
            targets = snapshot_lobby_identities()
            if not targets:
                raise ValueError("No lobby players available.")
            # Guests first — host already-complete skips should not burn the
            # whole first seat while friends wait (sequential All players).
            try:
                remotes = tuple(t for t in targets if not _identity_is_local(t))
                locals_ = tuple(t for t in targets if _identity_is_local(t))
                if remotes:
                    targets = remotes + locals_
            except Exception:
                pass
            for_all = True
            label = "All players"
        else:
            targets = (selected_lobby_identity(player_index),)
            for_all = False
            label = targets[0].display_name
    except Exception as exc:
        _pending = None
        _pending_rows = None
        _message = f"Could not start: {exc}"
        _last_error = str(exc)
        try:
            from . import hold_session

            hold_session.release_job("challenges")
        except Exception:
            pass
        return
    _pending = None
    _pending_rows = None
    _targets = tuple(targets)
    _for_all = bool(for_all)
    # Pace by whether any job target is remote — not by lobby size. Host boosting
    # themselves in a full lobby can still use the fast local batch.
    try:
        _remote_target_pacing = bool(for_all) or any(
            not _identity_is_local(identity) for identity in _targets
        )
    except Exception:
        _remote_target_pacing = len(_targets) > 1 or bool(for_all)
    _rows = rows
    _index = 0
    _target_index = 0
    _ok = 0
    _failed = 0
    _skipped = 0
    _dead_targets.clear()
    _resolve_misses.clear()
    _last_error = ""
    _active = True
    pace = "remote" if _remote_target_pacing else "local"
    if tokens:
        _message = (
            f"Started {len(rows)} selected challenge(s) for {label} "
            f"({pace} {_batch_size()}/tick)."
        )
    else:
        _message = (
            f"Started {category}: {len(rows)} challenges for {label} "
            f"({pace} {_batch_size()}/tick)."
        )
    _log(_message)


def runtime_tick(*_args: Any, **_kwargs: Any) -> None:
    global _last_tick_at, _index, _target_index, _ok, _failed, _skipped, _active, _message, _last_error
    now = time.monotonic()
    if now - _last_tick_at < _tick_gap():
        return
    # Lobby join/leave + bulk challenge RPCs is an AV magnet (null+0x70 dumps).
    # Pause applies until settle — keep the job armed so the bar resumes.
    try:
        from .serial_rewards import _serial_mail_join_quiet

        if _serial_mail_join_quiet():
            # Keep EXE/BLImGui text moving so a pause does not look like a stuck bar.
            if _active and _rows:
                _message = (
                    f"Paused for guest join/leave · {_index}/{len(_rows)} "
                    f"(OK {_ok}, skip {_skipped}) — resuming after settle…"
                )
            return
    except Exception:
        pass
    _last_tick_at = now
    # Always allow queue → armed even during brief menu flicker. Only the
    # apply loop below requires session_safe (UVHM-style: never wipe the queue).
    if _pending is not None:
        _consume_request()
        # If still waiting (listen-host), stop this tick. If armed, fall through
        # and apply the first batch immediately so the bar moves on the same frame.
        if _pending is not None:
            return
    try:
        from .session_guards import session_safe

        if not session_safe():
            return
    except Exception:
        pass
    if not _active or not _targets:
        # Challenges idle — still try armed MAX ALL UVHM follow-up.
        if _followup_uvhm is not None:
            _fire_followup_uvhm()
        return
    try:
        from mods_base import get_pc

        owner = get_pc()
        if owner is None:
            raise RuntimeError("local player controller is unavailable")
    except Exception as exc:
        _failed += 1
        _last_error = f"owner PC unavailable: {type(exc).__name__}: {exc}"
        _log(_last_error)
        return

    # Drain ULM-safe batches (solo 1 / remote 3) — never the old local-6 flood.
    budget = max(1, int(_batch_size()))
    # Read-only skips need not consume the reward/RPC write allowance. Bound
    # scans and wall time so an already-complete catalog cannot hitch a frame.
    scan_budget = 32
    scan_deadline = time.perf_counter() + 0.004
    applied_this_tick = 0
    live_targets = [t for t in _targets if str(getattr(t, "key", "") or "") not in _dead_targets]
    if not live_targets and _targets:
        # Everyone left — finish cleanly instead of spinning fails.
        _active = False
        msg = (
            f"Complete: {_ok} accepted, {_failed} failed, {_skipped} skipped "
            f"(lobby empty mid-job)."
        )
        _arm_sticky("complete", msg)
        _log(msg)
        try:
            from . import hold_session

            hold_session.release_job("challenges")
        except Exception:
            pass
        _fire_followup_uvhm()
        return

    # Sequential seats (not round-robin): finish one player's full catalog, then
    # the next. Round-robin left the EXE stuck on "player 1/2" while both were
    # still sharing every token — looked like player 2 never started.
    while budget > 0 and _active:
        if scan_budget <= 0 or (scan_budget < 32 and time.perf_counter() >= scan_deadline):
            break
        scan_budget -= 1
        if _target_index >= len(_targets):
            break
        identity = _targets[_target_index]
        key = str(getattr(identity, "key", "") or "")
        if key and key in _dead_targets:
            _log(f"Seat {_target_index + 1}/{len(_targets)} skipped (left): {identity.display_name}.")
            _target_index += 1
            _index = 0
            continue
        if _index >= len(_rows):
            finished_name = identity.display_name
            _target_index += 1
            _index = 0
            if _target_index < len(_targets):
                nxt = _targets[_target_index].display_name
                _message = (
                    f"Finished {finished_name} ✓ — starting {nxt} "
                    f"(player {_target_index + 1}/{len(_targets)})."
                )
                _log(_message)
            continue
        token, amount = _rows[_index]
        outcome = "error"
        try:
            outcome = _apply_one(token, amount, identity, owner)
            if outcome == "retry":
                # Guest join settle — hold the cursor; do not burn tokens as skips.
                _message = (
                    f"Waiting for lobby settle · {identity.display_name} "
                    f"{_index}/{len(_rows)} (OK {_ok}, skip {_skipped})…"
                )
                break
            if outcome == "ok":
                _ok += 1
                applied_this_tick += 1
            else:
                _skipped += 1
        except Exception as exc:
            _failed += 1
            _last_error = (
                f"{token} -> {identity.display_name}: {type(exc).__name__}: {exc}"
            )
            _log(_last_error)
        _index += 1
        if outcome != "skip":
            budget -= 1

    if _target_index >= len(_targets) or (
        len(_targets) <= 1 and _index >= len(_rows)
    ):
        _active = False
        # Single-seat: index may hit end without bumping target_index past 0.
        if len(_targets) <= 1 and _index >= len(_rows) and _target_index < len(_targets):
            _target_index = len(_targets)
        skip_bit = f", {_skipped} skipped" if _skipped else ""
        uvhm_bit = " · UVHM next" if _followup_uvhm else ""
        msg = (
            f"Complete: {_ok} accepted, {_failed} failed{skip_bit} "
            f"for {_target_label()}.{uvhm_bit}"
        )
        _arm_sticky("complete", msg)
        _log(msg)
        try:
            from . import hold_session

            hold_session.release_job("challenges")
        except Exception:
            pass
        _fire_followup_uvhm()
        return

    who = _targets[_target_index].display_name if _targets else _target_label()
    seat_bit = (
        f" · player {_target_index + 1}/{len(_targets)}"
        if len(_targets) > 1
        else ""
    )
    batch_bit = f" (+{applied_this_tick} this tick)" if applied_this_tick > 1 else ""
    skip_bit = f", skip {_skipped}" if _skipped else ""
    _message = (
        f"Working {_index}/{len(_rows)} for {who}{seat_bit} · OK {_ok} · fail {_failed}"
        f"{skip_bit}{batch_bit}."
    )
    _log_progress(_message)
