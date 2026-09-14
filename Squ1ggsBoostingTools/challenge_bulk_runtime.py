"""Nonblocking direct completion for selected non-UVHM challenge categories."""
from __future__ import annotations

import time
from typing import Any

from unrealsdk import logging

from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate
from .uvhm_progression import TargetIdentity, resolve_lobby_pc, selected_lobby_identity, snapshot_lobby_identities


_PREFIX = "[Squ1ggs Boosting Tools | Challenges]"
# (player_index, category, tokens, prebuilt_rows)
_pending: tuple[int, str, tuple[str, ...], tuple[tuple[str, int], ...]] | None = None
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
_catalog_cache: tuple[tuple[str, int], ...] | None = None
# Remote-target pacing only. Host-local jobs stay fast even in a live lobby —
# COS/library writes do not need the guest replication throttle.
_remote_target_pacing = False
# ULM-style batches (see ultra_local_menu challenge_complete._queue_tick_config):
# solo/host-local can drain several tokens per tick; remote stays tiny.
_CHALLENGE_TICK_GAP_LOCAL = 0.04
_CHALLENGE_TICK_GAP_REMOTE = 0.10
_CHALLENGE_BATCH_LOCAL = 6
_CHALLENGE_BATCH_REMOTE = 2


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


_last_apply_log_at = 0.0
_apply_log_count = 0


def _log(message: str) -> None:
    try:
        logging.info(f"{_PREFIX} {message}")
    except Exception:
        pass
    try:
        from . import runtime_log

        runtime_log.note(f"challenge: {message}")
    except Exception:
        pass


def _log_apply_throttled(token: str, amount: int, who: str) -> None:
    """Do not spam unrealsdk with 1200+ apply lines — that starved the EXE progress bar."""
    global _last_apply_log_at, _apply_log_count
    _apply_log_count += 1
    now = time.monotonic()
    if _apply_log_count <= 3 or _apply_log_count % 50 == 0 or (now - _last_apply_log_at) >= 0.75:
        _last_apply_log_at = now
        _log(f"Applied {token} +{amount} -> {who} (#{_apply_log_count})")


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


def _apply_one(token: str, amount: int, identity: TargetIdentity, owner: Any) -> None:
    from .challenge_increment import describe_target, increment_challenge

    pc = resolve_lobby_pc(identity)
    if pc is None:
        raise RuntimeError(f"selected player {identity.display_name!r} is no longer resolvable")
    if not _pc_matches_identity(pc, identity):
        raise RuntimeError(
            f"resolved PC {describe_target(pc)} does not match target {identity.display_name!r} "
            "(refusing to apply to wrong player)"
        )
    if not increment_challenge(pc, token, amount, owner_pc=owner):
        raise RuntimeError(f"challenge increment failed for {describe_target(pc)}")
    _log_apply_throttled(token, amount, describe_target(pc))


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
    global _catalog_cache
    if _catalog_cache is not None:
        return list(_catalog_cache)

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
    _catalog_cache = tuple(result)
    return list(_catalog_cache)


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
    global _pending, _message, _rows, _index
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
    cleaned_tokens: list[str] = []
    if tokens:
        for raw in tokens:
            token = str(raw or "").strip()
            if token and token not in cleaned_tokens:
                cleaned_tokens.append(token)
    try:
        rows = (
            _load_token_rows(cleaned_tokens)
            if cleaned_tokens
            else _load_rows(str(category))
        )
        if not rows:
            raise ValueError(f"No non-UVHM challenges matched {category!r}.")
    except Exception as exc:
        _message = f"Could not build challenge list: {exc}"
        return False
    # Prebuild on the bridge thread so status already has a real total — never
    # lie with "Building challenge list…" while the game tick is just waiting.
    _rows = rows
    _index = 0
    _pending = (int(player_index), str(category), tuple(cleaned_tokens), rows)
    who = "all players" if int(player_index) < 0 else "selected player"
    if cleaned_tokens:
        _message = (
            f"Queued {len(rows)} selected challenge(s) for {who} — starting…"
        )
    else:
        _message = (
            f"Queued {category}: {len(rows)} challenges for {who} — starting…"
        )
    # Activate immediately on the bridge/HTTP path when listen-host is already OK.
    # Waiting solely for BP_TickWidget left jobs stuck on "waiting for game tick"
    # whenever session_safe briefly blocked the shared UMG tick.
    try:
        _consume_request()
    except Exception as exc:
        _message = f"Queued but could not activate yet: {exc}"
        _log(_message)
    return True


def cancel() -> bool:
    global _pending, _active, _message, _rows, _index
    if _pending is not None:
        _pending = None
        _rows = ()
        _index = 0
        _message = "Queued request cancelled."
        return True
    if not _active:
        return False
    _active = False
    _message = f"Cancelled after {_index}/{len(_rows)} challenges."
    return True


def status() -> dict[str, Any]:
    token = _rows[_index][0] if _active and 0 <= _index < len(_rows) else ""
    total = len(_rows)
    queued = _pending is not None
    active = bool(_active or queued)
    return {
        "active": active,
        "queued": queued,
        "target": _target_label(),
        "for_all": bool(_for_all),
        "index": _index,
        "progress_index": _index,
        "target_index": _target_index,
        "target_total": len(_targets),
        "total": total,
        "progress_total": total,
        "queued_count": total if queued else 0,
        "ok": _ok,
        "failed": _failed,
        "token": token,
        "message": _message,
        "last_error": _last_error,
        "categories": list(CATEGORY_LABELS),
    }


def _consume_request() -> None:
    global _pending, _targets, _for_all, _rows, _index, _target_index
    global _ok, _failed, _active, _message, _last_error, _remote_target_pacing
    request = _pending
    if request is None:
        return
    # Keep queue until start succeeds (same pattern as UVHM).
    world, _gs = _gbc_session_world_and_gamestate()
    if not _gbc_is_listen_host_world(world):
        _message = "Challenge bulk waiting for listen-host world (stay in lobby / unpause)."
        return
    player_index, category, tokens, rows = request
    try:
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
        _message = f"Could not start: {exc}"
        _last_error = str(exc)
        try:
            from . import hold_session

            hold_session.release_job("challenges")
        except Exception:
            pass
        return
    _pending = None
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
    global _apply_log_count, _last_apply_log_at
    _rows = rows
    _index = 0
    _target_index = 0
    _ok = 0
    _failed = 0
    _apply_log_count = 0
    _last_apply_log_at = 0.0
    _last_error = ""
    _active = True
    pace = "remote" if _remote_target_pacing else "local"
    if tokens:
        _message = (
            f"Starting {len(rows)} selected challenge(s) for {label} "
            f"({pace} {_batch_size()}/tick)."
        )
    else:
        _message = (
            f"Starting {category}: {len(rows)} challenges for {label} "
            f"({pace} {_batch_size()}/tick)."
        )
    _log(_message)


def runtime_tick(*_args: Any, **_kwargs: Any) -> None:
    global _last_tick_at, _index, _target_index, _ok, _failed, _active, _message, _last_error
    now = time.monotonic()
    # Consume queued jobs even during brief menu/inventory flicker — the list is
    # already built; only the host-world check is needed to activate.
    if _pending is not None:
        if now - _last_tick_at < 0.05:
            return
        _last_tick_at = now
        _consume_request()
        return
    if now - _last_tick_at < _tick_gap():
        return
    _last_tick_at = now
    if not _active or not _targets:
        return
    try:
        from . import uvhm_runtime

        uvhm = uvhm_runtime.status()
        if bool(uvhm.get("running") or uvhm.get("queued")):
            _message = (
                f"Paused at {_index}/{len(_rows)} — UVHM is running. "
                "Challenge bulk resumes when UVHM finishes."
            )
            return
    except Exception:
        pass
    try:
        from .session_guards import session_safe

        if not session_safe():
            # Keep the job armed; tell the EXE why the counter is not moving.
            _message = (
                f"Paused at {_index}/{len(_rows)} — unpause / leave inventory so "
                "challenge applies can run."
            )
            return
    except Exception:
        pass
    if _index >= len(_rows):
        _active = False
        _message = f"Complete: {_ok} accepted, {_failed} failed for {_target_label()}."
        _log(_message)
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

    # Drain a small batch per tick (ULM pattern) instead of 1 challenge / 0.18s.
    budget = max(1, int(_batch_size()))
    applied_this_tick = 0
    while budget > 0 and _active and _index < len(_rows):
        token, amount = _rows[_index]
        identity = _targets[min(_target_index, len(_targets) - 1)]
        try:
            _apply_one(token, amount, identity, owner)
            _ok += 1
            applied_this_tick += 1
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
        _message = f"Complete: {_ok} accepted, {_failed} failed for {_target_label()}."
        _log(_message)
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
    _message = (
        f"Applied {_index}/{len(_rows)} challenges{player_progress}{batch_bit} "
        f"-> {_target_label()}."
    )