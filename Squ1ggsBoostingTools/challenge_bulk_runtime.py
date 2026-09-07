"""Nonblocking direct completion for selected non-UVHM challenge categories."""
from __future__ import annotations

import time
from typing import Any

from unrealsdk import logging

from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate
from .uvhm_progression import TargetIdentity, resolve_lobby_pc, selected_lobby_identity, snapshot_lobby_identities


_PREFIX = "[Squ1ggs Boosting Tools | Challenges]"
_pending: tuple[int, str, tuple[str, ...]] | None = None
_targets: tuple[TargetIdentity, ...] = ()
_for_all = False
_rows: tuple[tuple[str, int], ...] = ()
_index = 0
_ok = 0
_failed = 0
_active = False
_message = "Idle."
_last_error = ""
_last_tick_at = 0.0
_CHALLENGE_BATCH = 16


CATEGORY_LABELS: tuple[str, ...] = (
    "All non-UVHM",
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
    "collectibles": ("challenge_tutorial_collectible_", "challenge_collect_"),
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
        "cowbell_challenges_characters_",
        "challenge_robodealer_",
    ),
    "shinies": ("challenge_shiny_",),
    "world": (
        "challenge_misc_world",
        "challenge_misc_worldevent",
        "worldevents_",
        "worldboss_",
        "cowbell_challenges_world_",
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


def _log(message: str) -> None:
    try:
        logging.info(f"{_PREFIX} {message}")
    except Exception:
        pass


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
    _log(f"Applied {token} +{amount} -> {describe_target(pc)}")


def _is_uvhm(token: str) -> bool:
    return "uvh" in token.casefold().replace("-", "_")


def _is_vault_card_or_junk(token: str) -> bool:
    """Vault-card dailies/weeklies + demo/test noise — not part of All non-UVHM boosts."""
    key = token.casefold().replace("-", "_")
    if key.startswith(("vc1_", "vc2_", "vc3_", "vc4_", "vcchallenge_")):
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
        result.append((token, int(goals.get(token) or 1)))
    return tuple(result)


def catalog_rows(search: str = "", category: str = "All non-UVHM", *, limit: int = 500) -> tuple[tuple[str, int], ...]:
    """Filtered challenge rows for UI pickers (non-UVHM only)."""
    rows = _load_rows(category)
    needle = str(search or "").strip().casefold()
    if needle:
        rows = tuple(
            (token, goal)
            for token, goal in rows
            if needle in token.casefold() or needle in token.replace("_", " ").casefold()
        )
    cap = max(1, min(int(limit or 500), 2000))
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
    global _pending, _message
    if not confirmed:
        _message = "A second confirmation click is required."
        return False
    if _active or _pending is not None:
        _message = "Another non-UVHM challenge workflow is already active."
        return False
    cleaned_tokens: list[str] = []
    if tokens:
        for raw in tokens:
            token = str(raw or "").strip()
            if token and token not in cleaned_tokens:
                cleaned_tokens.append(token)
    _pending = (int(player_index), str(category), tuple(cleaned_tokens))
    if cleaned_tokens:
        _message = f"Confirmed {len(cleaned_tokens)} selected challenge(s) queued for the game tick."
    elif int(player_index) < 0:
        _message = "Confirmed all-players request queued for the game tick."
    else:
        _message = "Confirmed request queued for the game tick."
    return True


def cancel() -> bool:
    global _pending, _active, _message
    if _pending is not None:
        _pending = None
        _message = "Queued request cancelled."
        return True
    if not _active:
        return False
    _active = False
    _message = f"Cancelled after {_index}/{len(_rows)} challenges."
    return True


def status() -> dict[str, Any]:
    token = _rows[_index][0] if _active and 0 <= _index < len(_rows) else ""
    return {
        "active": bool(_active or _pending is not None),
        "queued": _pending is not None,
        "target": _target_label(),
        "for_all": bool(_for_all),
        "index": _index,
        "total": len(_rows),
        "ok": _ok,
        "failed": _failed,
        "token": token,
        "message": _message,
        "last_error": _last_error,
        "categories": list(CATEGORY_LABELS),
    }


def _consume_request() -> None:
    global _pending, _targets, _for_all, _rows, _index, _ok, _failed, _active, _message, _last_error
    request = _pending
    if request is None:
        return
    _pending = None
    world, _gs = _gbc_session_world_and_gamestate()
    if not _gbc_is_listen_host_world(world):
        _message = "Request refused: run this on the listen host."
        return
    player_index, category, tokens = request
    try:
        rows = _load_token_rows(tokens) if tokens else _load_rows(category)
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
        _message = f"Could not start: {exc}"
        _last_error = str(exc)
        return
    _targets = tuple(targets)
    _for_all = bool(for_all)
    _rows = rows
    _index = 0
    _ok = 0
    _failed = 0
    _last_error = ""
    _active = True
    if tokens:
        _message = f"Started {len(rows)} selected challenge(s) for {label}."
    else:
        _message = f"Started {category}: {len(rows)} challenges for {label}."
    _log(_message)


def runtime_tick(*_args: Any, **_kwargs: Any) -> None:
    global _last_tick_at, _index, _ok, _failed, _active, _message, _last_error
    now = time.monotonic()
    if now - _last_tick_at < 0.12:
        return
    _last_tick_at = now
    try:
        from .session_guards import session_safe

        if not session_safe():
            if _pending is not None or _active:
                cancel()
            return
    except Exception:
        pass
    if _pending is not None:
        _consume_request()
        return
    if not _active or not _targets:
        return
    if _index >= len(_rows):
        _active = False
        _message = f"Complete: {_ok} accepted, {_failed} failed for {_target_label()}."
        _log(_message)
        return
    batch_end = min(len(_rows), _index + _CHALLENGE_BATCH)
    while _index < batch_end:
        token, amount = _rows[_index]
        try:
            from mods_base import get_pc

            owner = get_pc()
            if _for_all:
                if owner is None:
                    raise RuntimeError("local player controller is unavailable")
                applied_n = 0
                last_err = ""
                for identity in _targets:
                    try:
                        _apply_one(token, amount, identity, owner)
                        applied_n += 1
                    except Exception as exc:
                        last_err = str(exc)
                if applied_n == 0:
                    raise RuntimeError(last_err or "per-player challenge apply failed for all targets")
            else:
                _apply_one(token, amount, _targets[0], owner)
            _ok += 1
        except Exception as exc:
            _failed += 1
            _last_error = f"{token}: {type(exc).__name__}: {exc}"
            _log(_last_error)
        _index += 1
    _message = f"Applied {_index}/{len(_rows)} challenges -> {_target_label()}."