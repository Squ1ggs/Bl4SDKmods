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
_sticky_phase = ""
_sticky_until = 0.0
_STICKY_SEC = 4.0
# Remote-target pacing only. Host-local jobs stay fast even in a live lobby —
# COS/library writes do not need the guest replication throttle.
_remote_target_pacing = False
# Identity keys for players who left mid-job — skip without failing every remaining token.
_dead_targets: set[str] = set()
_skipped = 0
# ULM challenge_complete._queue_tick_config:
#   solo: batch=1, pause ~50ms
#   lobby: batch=2, pause every 3 (~35ms)
# Local 6/tick drained All non-UVHM in ~11s and reward-flooded the session (crash).
_CHALLENGE_TICK_GAP_LOCAL = 0.05
_CHALLENGE_TICK_GAP_REMOTE = 0.10
_CHALLENGE_BATCH_LOCAL = 1
_CHALLENGE_BATCH_REMOTE = 2
# ULM-style: do not log every apply (that flooded sqbt_runtime + force-flush on status polls).
_PROGRESS_LOG_EVERY = 25
_progress_log_counter = 0
# UI bar steps — keep readable while apply stays 1/tick.
_ui_milestone_index = 0


def _milestone_step(total: int) -> int:
    """~20 bar steps for large bulks (min 25) — matches slower ULM-safe apply."""
    total_i = max(0, int(total or 0))
    if total_i <= 0:
        return 1
    if total_i <= 40:
        return 1
    return max(25, (total_i + 19) // 20)


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
    """Apply one challenge. Returns 'ok' | 'skip' | raises on hard failure."""
    from .challenge_increment import (
        challenge_already_complete,
        describe_target,
        increment_challenge,
    )

    key = str(getattr(identity, "key", "") or "")
    if key and key in _dead_targets:
        return "skip"
    pc = resolve_lobby_pc(identity)
    if pc is None:
        if key:
            _dead_targets.add(key)
        _log(f"Skip {identity.display_name} (left / unresolvable) for remaining challenges.")
        return "skip"
    if not _pc_matches_identity(pc, identity):
        if key:
            _dead_targets.add(key)
        _log(f"Skip {identity.display_name} (identity mismatch) for remaining challenges.")
        return "skip"
    # Re-running Complete ALL after a finish still "accepted" 1209 and re-mailed
    # hundreds of packages — skip already-done tokens (ULM-safe).
    try:
        if challenge_already_complete(pc, token):
            return "skip"
    except Exception:
        pass
    if not increment_challenge(pc, token, amount, owner_pc=owner):
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
    who = "all players" if int(player_index) < 0 else f"player index {int(player_index)}"
    if cleaned_tokens:
        _message = f"Queued {len(rows)} selected challenge(s) for {who} — waiting for world tick…"
    else:
        _message = f"Queued {len(rows)} · {category} for {who} — waiting for world tick…"
    return True


def _arm_sticky(phase: str, message: str) -> None:
    global _sticky_phase, _sticky_until, _message
    _sticky_phase = str(phase or "")
    _sticky_until = time.monotonic() + float(_STICKY_SEC)
    if message:
        _message = str(message)


def _clear_sticky() -> None:
    global _sticky_phase, _sticky_until
    _sticky_phase = ""
    _sticky_until = 0.0


def cancel() -> bool:
    global _pending, _pending_rows, _active, _message
    if _pending is not None:
        _pending = None
        _pending_rows = None
        _arm_sticky("cancelled", "Queued request cancelled.")
        return True
    if not _active:
        return False
    _active = False
    _pending_rows = None
    _arm_sticky("cancelled", f"Cancelled after {_index}/{len(_rows)} challenges.")
    return True


def status() -> dict[str, Any]:
    global _ui_milestone_index
    sticky_live = bool(_sticky_phase) and time.monotonic() < float(_sticky_until)
    if not sticky_live and _sticky_phase:
        _clear_sticky()
    live = bool(_active or _pending is not None)
    phase = "running" if live else ("idle" if not sticky_live else str(_sticky_phase))
    if sticky_live and not live:
        phase = str(_sticky_phase)
    token = _rows[_index][0] if _active and 0 <= _index < len(_rows) else ""
    # EXE busy through sticky complete/cancel so the bar does not stick on optimistic active.
    sticky_busy = sticky_live and phase in ("complete", "cancelled")
    total_rows = len(_rows)
    if live or sticky_live:
        # Count skips too — otherwise already-done tokens leave the bar at 0.
        raw_index = min(
            total_rows,
            max(int(_index), int(_ok) + int(_failed) + int(_skipped)),
        )
    else:
        raw_index = 0
    # Distinct phase while waiting to arm so the EXE does not look "stuck queued".
    if _pending is not None and not _active:
        phase = "queued"
    # Monotonic milestone bar — jumps in chunks (ULM dump style), not every token.
    if phase in ("complete", "cancelled") or (not live and sticky_busy):
        bar_index = total_rows if phase == "complete" else _snap_milestone(raw_index, total_rows)
        _ui_milestone_index = bar_index
    elif live:
        snapped = _snap_milestone(raw_index, total_rows)
        if snapped > int(_ui_milestone_index):
            _ui_milestone_index = snapped
        # Always show at least the first step once work has started.
        if raw_index > 0 and int(_ui_milestone_index) <= 0 and total_rows > 0:
            _ui_milestone_index = min(total_rows, _milestone_step(total_rows))
        bar_index = int(_ui_milestone_index)
    else:
        bar_index = 0
        _ui_milestone_index = 0
    step = _milestone_step(total_rows) if total_rows else 1
    return {
        "active": bool(live or sticky_busy),
        "queued": _pending is not None,
        "running": bool(_active),
        "phase": phase,
        "target": _target_label(),
        "for_all": bool(_for_all),
        "index": bar_index,
        "progress_index": bar_index,
        "raw_index": raw_index,
        "milestone_step": step,
        "target_index": _target_index,
        "target_total": len(_targets),
        "total": len(_rows),
        "progress_total": len(_rows),
        "ok": _ok,
        "failed": _failed,
        "skipped": _skipped,
        "token": token,
        "message": _message,
        "last_error": _last_error,
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
        return
    if _index >= len(_rows):
        _active = False
        skip_bit = f", {_skipped} skipped" if _skipped else ""
        msg = f"Complete: {_ok} accepted, {_failed} failed{skip_bit} for {_target_label()}."
        _arm_sticky("complete", msg)
        _log(msg)
        try:
            from . import hold_session

            hold_session.release_job("challenges")
        except Exception:
            pass
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

    # Drain ULM-safe batches (solo 1 / remote 2) — never the old local-6 flood.
    budget = max(1, int(_batch_size()))
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
        return

    while budget > 0 and _active and _index < len(_rows):
        token, amount = _rows[_index]
        # Prefer next live target; wrap if current is dead.
        hops = 0
        while hops < len(_targets):
            identity = _targets[min(_target_index, len(_targets) - 1)]
            key = str(getattr(identity, "key", "") or "")
            if key and key in _dead_targets:
                _target_index = (_target_index + 1) % len(_targets)
                hops += 1
                continue
            break
        identity = _targets[min(_target_index, len(_targets) - 1)]
        try:
            outcome = _apply_one(token, amount, identity, owner)
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
        _target_index += 1
        if _target_index >= len(_targets):
            _target_index = 0
            _index += 1
        budget -= 1

    if _index >= len(_rows):
        _active = False
        skip_bit = f", {_skipped} skipped" if _skipped else ""
        msg = f"Complete: {_ok} accepted, {_failed} failed{skip_bit} for {_target_label()}."
        _arm_sticky("complete", msg)
        _log(msg)
        try:
            from . import hold_session

            hold_session.release_job("challenges")
        except Exception:
            pass
        return

    player_progress = (
        f", player {_target_index + 1}/{len(_targets)}"
        if len(_targets) > 1 and _index < len(_rows)
        else ""
    )
    batch_bit = f" (+{applied_this_tick} this tick)" if applied_this_tick > 1 else ""
    skip_bit = f", skip {_skipped}" if _skipped else ""
    _message = (
        f"Working {_index}/{len(_rows)} · OK {_ok} · fail {_failed}{skip_bit}"
        f"{player_progress}{batch_bit} -> {_target_label()}."
    )
    _log_progress(_message)