"""Vault-card discovery, maxing, and reward-token helpers for Boosting Tools."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .currency_give import iter_currency_slots, write_currency_slot_amount
from .data_files import read_data_json, writable_data_path

_MOD_DIR = Path(__file__).resolve().parent
_TOKEN_FILE_NAME = "vault_card_reward_tokens.json"
_MANAGER_EXP_SLOT_DEFAULTS: dict[int, int] = {0: 2, 1: 3, 2: 4, 3: 5}
_DEFAULT_CURRENCY_NEEDLES = ("vaultcard01", "vaultcard02", "vaultcard03", "vaultcard04")
_DEFAULT_EXP_FALLBACKS: dict[int, tuple[str, ...]] = {
    0: ("VaultCard01", "VaultCard1", "VaultCard01_XP"),
    1: ("VaultCard02", "VaultCard2", "VaultCard02_XP"),
    2: ("VaultCard03", "VaultCard3", "VaultCard03_XP", "Raid3", "Raid_3"),
    3: ("VaultCard04", "VaultCard4", "VaultCard04_XP", "VaultCard04_Experience", "Desert"),
}
_MAX_LEVEL = 9_999
_MAX_CURRENCY = 2_147_483_647


@dataclass(slots=True)
class VaultCardEntry:
    index: int
    def_name: str = ""
    dlc_name: str = ""
    display_name: str = ""
    currency_needle: str | None = None
    currency_slot: int | None = None
    currency_name: str | None = None
    currency_amount: int = 0
    exp_slot: int | None = None
    exp_token: str | None = None
    exp_level: int = 0
    exp_xp: int = 0
    exp_unlocked: bool | None = None
    reward_tokens: list[str] = field(default_factory=list)


def _safe_str(value: Any) -> str:
    try:
        return str(value)
    except Exception:  # noqa: BLE001
        return "?"


def gbx_ptr_name(ptr: Any) -> str:
    """Extract a readable name from FGbxDefPtr-like values."""
    if ptr is None:
        return ""
    for attr in ("name", "Name", "_experimental_name"):
        try:
            value = getattr(ptr, attr, None)
            if isinstance(value, str) and value.strip() and value.lower() not in ("none", "null"):
                return value.strip()
        except Exception:  # noqa: BLE001
            continue
    text = _safe_str(ptr)
    for pattern in (
        r"name=['\"]([^'\"]+)['\"]",
        r"Name:\s*'([^']+)'",
        r"FGbxDefPtr\('([^']+)'",
    ):
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return text.split("'")[1] if "'" in text else text[:80]


def experience_state_token(row: Any) -> str | None:
    try:
        experience_id = getattr(row, "ExperienceId", None)
    except Exception:  # noqa: BLE001
        experience_id = None
    if experience_id is None:
        return None
    for attr in ("Name", "name"):
        try:
            value = getattr(experience_id, attr)
            if isinstance(value, str) and value:
                return value
        except Exception:  # noqa: BLE001
            pass
    match = re.search(r"Name:\s*'([^']+)'", _safe_str(experience_id))
    return match.group(1) if match else None


def _resolve_vault_card_def_struct(card: Any) -> Any | None:
    for attr in ("VaultCardDef", "ActivatedVaultCardDef"):
        try:
            value = getattr(card, attr, None)
        except Exception:  # noqa: BLE001
            value = None
        if value is not None:
            return value
    return None


def _extract_reward_unique_names(root: Any, *, limit: int = 256) -> list[str]:
    """Walk live card reward data for RewardData_* unique-name tokens."""
    found: list[str] = []
    seen: set[str] = set()

    def add_token(token: str) -> None:
        value = token.strip()
        if value and value.startswith("RewardData_") and value not in seen:
            seen.add(value)
            found.append(value)

    def walk(obj: Any, depth: int) -> None:
        if obj is None or depth > 8 or len(found) >= limit:
            return
        try:
            unique_name = getattr(obj, "UniqueName", None)
            if isinstance(unique_name, str):
                add_token(unique_name)
        except Exception:  # noqa: BLE001
            pass
        for attr in ("UnlockableRewards", "reward", "Reward", "rewards"):
            try:
                sequence = getattr(obj, attr, None)
                count = len(sequence) if sequence is not None else 0
            except Exception:  # noqa: BLE001
                continue
            for index in range(min(count, 64)):
                try:
                    item = sequence[index]
                except Exception:  # noqa: BLE001
                    continue
                walk(item, depth + 1)
                for sub_attr in ("reward", "Reward"):
                    try:
                        walk(getattr(item, sub_attr, None), depth + 1)
                    except Exception:  # noqa: BLE001
                        pass

    walk(root, 0)
    return found


def _vault_cards_sequence(pc: Any) -> list[Any]:
    manager = getattr(pc, "VaultCardsManager", None)
    cards = getattr(manager, "VaultCards", None) if manager is not None else None
    if cards is None:
        return []
    try:
        count = len(cards)
    except Exception:  # noqa: BLE001
        return []
    result: list[Any] = []
    for index in range(count):
        try:
            result.append(cards[index])
        except Exception:  # noqa: BLE001
            continue
    return result


def _match_exp_slot(
    ps: Any,
    needles: tuple[str, ...],
    *,
    allow_card3_override: bool = False,
) -> tuple[int | None, str | None]:
    states = getattr(ps, "ExperienceState", None)
    if states is None:
        return None, None
    try:
        count = len(states)
    except Exception:  # noqa: BLE001
        return None, None
    queries = [value.lower() for value in needles if value]
    for index in range(count):
        try:
            token = experience_state_token(states[index])
        except Exception:  # noqa: BLE001
            continue
        if token:
            lowered = token.lower()
            if any(query in lowered or lowered in query for query in queries):
                return index, token
    if not allow_card3_override:
        return None, None
    raw = os.environ.get("SQU1GGS_VAULT_CARD3_EXP_SLOT", "").strip()
    if not raw:
        # Retain compatibility with existing user configuration.
        raw = os.environ.get("ECHO4_VAULT_CARD3_EXP_SLOT", "").strip()
    if raw:
        try:
            index = int(raw)
            if 0 <= index < count:
                return index, experience_state_token(states[index])
        except (TypeError, ValueError):
            pass
    return None, None


def _match_currency(
    currency_rows: list[tuple[int, Any, str, int]],
    needles: tuple[str, ...],
) -> tuple[int | None, str | None, int]:
    queries = [value.lower() for value in needles if value]
    for index, _slot, name, amount in currency_rows:
        lowered = name.lower()
        if any(query in lowered for query in queries):
            return index, name, amount
    return None, None, 0


def _load_token_data() -> dict[str, Any]:
    """User-saved token file first (writable), bundled seed data as fallback."""
    user_path = writable_data_path(_TOKEN_FILE_NAME)
    try:
        if user_path.is_file():
            data = json.loads(user_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:  # noqa: BLE001
        pass
    data = read_data_json(_TOKEN_FILE_NAME, default={})
    return data if isinstance(data, dict) else {}


def load_saved_tokens(card_number: int) -> list[str]:
    cards = _load_token_data().get("cards")
    if not isinstance(cards, dict):
        return []
    entry = cards.get(str(card_number))
    tokens = entry.get("tokens") if isinstance(entry, dict) else None
    if not isinstance(tokens, list):
        return []
    return [str(value).strip() for value in tokens if str(value).strip()]


def build_catalog(
    pc: Any,
    ps: Any,
    *,
    currency_rows: list[tuple[int, Any, str, int]],
) -> list[VaultCardEntry]:
    catalog: list[VaultCardEntry] = []
    for index, card in enumerate(_vault_cards_sequence(pc)):
        vault_def = _resolve_vault_card_def_struct(card)
        def_name = gbx_ptr_name(vault_def)
        dlc_name = ""
        display_name = ""
        if vault_def is not None:
            try:
                dlc_name = gbx_ptr_name(getattr(vault_def, "DLCDef", None))
            except Exception:  # noqa: BLE001
                pass
            try:
                exp_def = getattr(vault_def, "ExperienceDef", None)
                display_name = _safe_str(getattr(exp_def, "DisplayName", "") or "")
            except Exception:  # noqa: BLE001
                pass
        needle = (
            _DEFAULT_CURRENCY_NEEDLES[index]
            if index < len(_DEFAULT_CURRENCY_NEEDLES)
            else f"vaultcard{index + 1:02d}"
        )
        fallbacks = _DEFAULT_EXP_FALLBACKS.get(
            index,
            (f"VaultCard{index + 1:02d}", f"VaultCard{index + 1}"),
        )
        exp_slot, exp_token = _match_exp_slot(
            ps,
            (def_name, dlc_name, display_name, *fallbacks),
            allow_card3_override=index == 2,
        )
        if exp_slot is None and index in _MANAGER_EXP_SLOT_DEFAULTS:
            exp_slot = _MANAGER_EXP_SLOT_DEFAULTS[index]
        currency_slot, currency_name, currency_amount = _match_currency(
            currency_rows,
            (needle, def_name, dlc_name, *fallbacks),
        )
        rewards = _extract_reward_unique_names(vault_def) if vault_def is not None else []
        saved_rewards = load_saved_tokens(index + 1)
        rewards = list(dict.fromkeys([*rewards, *saved_rewards]))
        level = xp = 0
        unlocked: bool | None = None
        if exp_slot is not None:
            try:
                row = getattr(ps, "ExperienceState")[exp_slot]
                level = int(getattr(row, "ExperienceLevel", 0) or 0)
                xp = int(getattr(row, "ExperiencePoints", 0) or 0)
                unlocked = bool(getattr(row, "bIsUnlocked", False))
            except Exception:  # noqa: BLE001
                pass
        catalog.append(
            VaultCardEntry(
                index=index,
                def_name=def_name,
                dlc_name=dlc_name,
                display_name=display_name,
                currency_needle=needle,
                currency_slot=currency_slot,
                currency_name=currency_name,
                currency_amount=currency_amount,
                exp_slot=exp_slot,
                exp_token=exp_token,
                exp_level=level,
                exp_xp=xp,
                exp_unlocked=unlocked,
                reward_tokens=rewards,
            )
        )
    return catalog


def select_cards(catalog: list[VaultCardEntry], selector: str) -> list[VaultCardEntry]:
    value = selector.strip().lower()
    if not value or value in ("all", "*"):
        return list(catalog)
    if value in ("3", "03", "card3", "vc3", "raid3", "raid_3", "raid-3"):
        for card in catalog:
            blob = " ".join(
                item.lower()
                for item in (card.def_name, card.dlc_name, card.display_name, card.exp_token or "")
            )
            if "vaultcard3" in blob or "raid3" in blob or "raid_3" in blob:
                return [card]
        return [catalog[2]] if len(catalog) >= 3 else []
    if value in ("4", "04", "card4", "vc4", "raid4", "raid_4", "raid-4", "desert", "desert_dreams"):
        for card in catalog:
            blob = " ".join(
                item.lower()
                for item in (card.def_name, card.dlc_name, card.display_name, card.exp_token or "")
            )
            if "vaultcard4" in blob or "vaultcard04" in blob or "desert" in blob:
                return [card]
        return [catalog[3]] if len(catalog) >= 4 else []
    if value.isdigit():
        index = int(value) - 1 if int(value) >= 1 else int(value)
        return [card for card in catalog if card.index == index]
    for card in catalog:
        blob = " ".join(
            item.lower()
            for item in (card.def_name, card.dlc_name, card.display_name, card.exp_token or "")
        )
        if value in blob:
            return [card]
    return []


def save_tokens_to_file(catalog: list[VaultCardEntry]) -> Path:
    existing: dict[str, Any] = _load_token_data()
    current_cards = existing.get("cards")
    cards = current_cards if isinstance(current_cards, dict) else {}
    for entry in catalog:
        tokens = list(dict.fromkeys(entry.reward_tokens or load_saved_tokens(entry.index + 1)))
        if tokens:
            cards[str(entry.index + 1)] = {
                "def_name": entry.def_name,
                "dlc_name": entry.dlc_name,
                "display_name": entry.display_name,
                "tokens": tokens,
            }
    output = {
        "description": existing.get(
            "description",
            "Vault-card entitlement tokens (runtime scan plus bundled seed).",
        ),
        "cards": cards,
    }
    path = writable_data_path(_TOKEN_FILE_NAME)
    path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return path


def probe_lines(
    pc: Any,
    ps: Any,
    *,
    currency_rows: list[tuple[int, Any, str, int]],
) -> list[str]:
    lines = ["Boosting Tools vault-card catalog:"]
    catalog = build_catalog(pc, ps, currency_rows=currency_rows)
    if not catalog:
        lines.append("  (no VaultCards[] readable; load the vault-card content in-world)")
    for card in catalog:
        lines.append(
            f"  [{card.index}] def={card.def_name or '?'} dlc={card.dlc_name or '?'} "
            f"display={card.display_name or '?'}"
        )
        lines.append(
            f"       currency: slot={card.currency_slot} name={card.currency_name or '?'} "
            f"amount={card.currency_amount}"
        )
        lines.append(
            f"       XP: ExperienceState[{card.exp_slot}] token={card.exp_token or '?'} "
            f"level={card.exp_level} xp={card.exp_xp} unlocked={card.exp_unlocked}"
        )
        lines.append(f"       rewards: {len(card.reward_tokens)} token(s)")
    return lines


def max_vault_cards(
    pc: Any,
    ps: Any,
    entries: list[VaultCardEntry],
    *,
    write_currency: Callable[[Any, int, int], tuple[bool, str]],
    write_experience_slot: Callable[..., list[str]],
    max_level: int,
    max_xp: int | None,
    max_currency: int,
) -> tuple[bool, list[str]]:
    bits: list[str] = []
    ok_all = True
    for card in entries:
        bits.append(f"card[{card.index}] {card.def_name or card.dlc_name or '?'}")
        if card.currency_slot is not None:
            ok, message = write_currency(pc, int(card.currency_slot), int(max_currency))
            bits.append(f"  currency slot {card.currency_slot}: {message}")
            ok_all = ok_all and ok
        elif card.currency_needle:
            bits.append(f"  currency: no slot matched needle {card.currency_needle!r}")
            ok_all = False
        if card.exp_slot is not None:
            bits.extend(
                write_experience_slot(
                    ps,
                    int(card.exp_slot),
                    level=max_level,
                    xp=max_xp,
                )
            )
        else:
            bits.append("  XP: no ExperienceState slot matched")
            ok_all = False
    return ok_all, bits


def grant_vault_card_rewards(
    entries: list[VaultCardEntry],
    *,
    give_def: Callable[[str, int], bool],
    use_saved: bool = True,
) -> tuple[int, int, list[str]]:
    succeeded = failed = 0
    bits: list[str] = []
    for card in entries:
        tokens = list(card.reward_tokens)
        if not tokens and use_saved:
            tokens = load_saved_tokens(card.index + 1)
        if not tokens:
            bits.append(f"card[{card.index}]: no reward tokens")
            continue
        bits.append(f"card[{card.index}]: granting {len(tokens)} reward definition(s)")
        for token in tokens:
            if give_def(token, 1):
                succeeded += 1
            else:
                failed += 1
                bits.append(f"  fail: {token}")
    return succeeded, failed, bits


def _rep_experience_state(ps: Any) -> None:
    on_rep = getattr(ps, "OnRep_ExperienceState", None)
    if callable(on_rep):
        try:
            on_rep()
        except Exception:  # noqa: BLE001
            pass


def _write_experience_slot(
    ps: Any,
    slot_idx: int,
    *,
    level: int,
    xp: int | None = None,
) -> list[str]:
    """Use the Boosting Tools BP setter, with the original raw-row fallback."""
    from .player_economy import (
        _clamp_engine_experience_level,
        _cumulative_floor_for_track,
        _set_experience_level_via_bp,
    )

    target = _clamp_engine_experience_level(slot_idx, level)
    bits: list[str] = []
    if _set_experience_level_via_bp(ps, slot_idx, target):
        bits.append(f"[{slot_idx}] BP_SetExperienceLevel -> {target}")
        return bits

    states = getattr(ps, "ExperienceState", None)
    if states is None:
        return [f"[{slot_idx}] ExperienceState missing"]
    try:
        row = states[slot_idx]
    except Exception as exc:  # noqa: BLE001
        return [f"[{slot_idx}] ExperienceState unreadable: {type(exc).__name__}"]
    try:
        before = getattr(row, "ExperienceLevel", None)
        setattr(row, "ExperienceLevel", target)
        setattr(row, "bIsUnlocked", True)
        bits.append(f"[{slot_idx}].ExperienceLevel: {before} -> {target}")
    except Exception as exc:  # noqa: BLE001
        bits.append(f"[{slot_idx}].ExperienceLevel failed: {type(exc).__name__}")
    try:
        effective_xp = (
            int(xp)
            if xp is not None
            else _cumulative_floor_for_track(slot_idx, target, 0, 0)
        )
        before_xp = getattr(row, "ExperiencePoints", None)
        setattr(row, "ExperiencePoints", effective_xp)
        bits.append(f"[{slot_idx}].ExperiencePoints: {before_xp} -> {effective_xp} (BP fallback)")
    except Exception as exc:  # noqa: BLE001
        bits.append(f"[{slot_idx}].ExperiencePoints failed: {type(exc).__name__}")
    return bits


def _max_amounts() -> tuple[int, int | None, int]:
    try:
        level = max(
            1,
            min(
                _MAX_LEVEL,
                int(
                    os.environ.get(
                        "SQU1GGS_VAULT_CARD_MAX",
                        os.environ.get("ECHO4_VAULT_CARD_MAX", str(_MAX_LEVEL)),
                    )
                ),
            ),
        )
    except (TypeError, ValueError):
        level = _MAX_LEVEL
    try:
        currency = max(
            0,
            min(
                _MAX_CURRENCY,
                int(
                    os.environ.get(
                        "SQU1GGS_MAX_CURRENCY",
                        os.environ.get("ECHO4_MAX_CURRENCY", str(_MAX_CURRENCY)),
                    )
                ),
            ),
        )
    except (TypeError, ValueError):
        currency = _MAX_CURRENCY
    return level, None, currency


def apply_max_to_all_vault_cards(
    pc: Any,
    ps: Any | None = None,
    *,
    selector: str = "all",
) -> tuple[bool, list[str]]:
    """Max vault-card tokens and XP using only Boosting Tools internals."""
    ps_obj = ps if ps is not None else getattr(pc, "PlayerState", None)
    if pc is None or ps_obj is None:
        return False, ["PlayerController or PlayerState missing"]
    catalog = build_catalog(pc, ps_obj, currency_rows=iter_currency_slots(pc))
    if not catalog:
        return False, [
            "VaultCards[] empty; load in-world with vault-card content active, "
            "open the Vault Cards menu once, then retry.",
        ]
    selected = select_cards(catalog, selector)
    if not selected:
        return False, [f"No vault card matched selector {selector!r}."]
    max_level, max_xp, max_currency = _max_amounts()
    ok, bits = max_vault_cards(
        pc,
        ps_obj,
        selected,
        write_currency=write_currency_slot_amount,
        write_experience_slot=_write_experience_slot,
        max_level=max_level,
        max_xp=max_xp,
        max_currency=max_currency,
    )
    _rep_experience_state(ps_obj)
    bits.append("ExperienceState: OnRep once")
    return ok, bits
