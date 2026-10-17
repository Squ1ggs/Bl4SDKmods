"""Standalone PlayerState challenge-objective reconciliation helpers.

Mission-backed challenges do not accept ordinary numeric increments.  BL4
mirrors their objective completion in ``PlayerState.ChallengeObjectiveStates``
and their loaded completion flags in ``ReplicatedChallengeCompletion``.  Keep
the small amount of code needed to update those structures in this standalone
mod instead of borrowing Ultra Local Menu at runtime.
"""

from __future__ import annotations

import re
from typing import Any, Callable

LogFn = Callable[[str], None]
CHALLENGE_TYPE_HANDLE = 16413
COMPLETE_WORD = 0xFFFFFFFF


def _log(log: LogFn | None, message: str) -> None:
    if log is not None:
        log(message)


def preferred_challenge_identifier(token: str) -> str:
    value = str(token or "").strip()
    if value.startswith("Challenge_") and not value.startswith("Challenges_"):
        return f"Challenges_{value[len('Challenge_') :]}"
    return value


def _identifier_variants(token: str) -> tuple[str, ...]:
    value = str(token or "").strip()
    if not value:
        return ()
    preferred = preferred_challenge_identifier(value)
    candidates = [preferred, value]
    if value.startswith("Challenges_"):
        candidates.append(f"Challenge_{value[len('Challenges_') :]}")
    elif value.startswith("Challenge_"):
        candidates.append(f"Challenges_{value[len('Challenge_') :]}")
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))


def _identifier_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    for attribute in ("Name", "name", "_name", "_experimental_name", "DefName"):
        try:
            candidate = getattr(value, attribute, None)
        except Exception:
            candidate = None
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().rsplit("/", 1)[-1]
    try:
        rendered = str(value).strip()
    except Exception:
        return ""
    for pattern in (
        r"Name:\s*'([^']+)'",
        r'Name:\s*"([^"]+)"',
        r"['\"](Challenges?_[^'\"]+)['\"]",
    ):
        match = re.search(pattern, rendered)
        if match:
            return match.group(1).strip()
    return rendered if rendered.startswith(("Challenge_", "Challenges_")) else ""


def _append(sequence: Any, value: Any) -> bool:
    for method_name in ("append", "Append", "Add"):
        method = getattr(sequence, method_name, None)
        if not callable(method):
            continue
        try:
            method(value)
            return True
        except Exception:
            continue
    try:
        sequence[len(list(sequence))] = value
        return True
    except Exception:
        return False


def _make_bit_item(array_index: int) -> Any | None:
    try:
        import unrealsdk
    except Exception:
        return None
    for name in ("GbxReplicatedBitArrayItem", "GbxFastReplicatedBitArrayItem"):
        for kwargs in (
            {
                "BitField": COMPLETE_WORD,
                "ArrayIndex": int(array_index),
                "ReplicationID": int(array_index) + 1,
                "ReplicationKey": 0,
                "MostRecentArrayReplicationKey": -1,
            },
            {"BitField": COMPLETE_WORD, "ArrayIndex": int(array_index)},
            {"BitField": COMPLETE_WORD},
        ):
            try:
                value = unrealsdk.make_struct(name, **kwargs)
            except Exception:
                value = None
            if value is not None:
                return value
    return None


def _max_completed_objectives(bit_array: Any, *, ensure_slots: int = 4) -> int:
    if bit_array is None:
        return 0
    for items_name in ("items", "Items"):
        try:
            sequence = getattr(bit_array, items_name, None)
        except Exception:
            sequence = None
        if sequence is None:
            continue
        writes = 0
        try:
            count = len(list(sequence))
        except Exception:
            count = 0
        while count < max(1, int(ensure_slots)):
            if _append(sequence, COMPLETE_WORD):
                count += 1
                writes += 1
                continue
            item = _make_bit_item(count)
            if item is None or not _append(sequence, item):
                break
            count += 1
            writes += 1
        for index in range(count):
            try:
                item = sequence[index]
            except Exception:
                continue
            if isinstance(item, int):
                if item != COMPLETE_WORD:
                    try:
                        sequence[index] = COMPLETE_WORD
                        writes += 1
                    except Exception:
                        pass
                continue
            try:
                current = getattr(item, "BitField", None)
            except Exception:
                current = None
            if current == COMPLETE_WORD:
                continue
            if isinstance(current, int):
                try:
                    setattr(item, "BitField", COMPLETE_WORD)
                    try:
                        sequence[index] = item
                    except Exception:
                        pass
                    writes += 1
                except Exception:
                    pass
                continue
            replacement = _make_bit_item(index)
            if replacement is not None:
                try:
                    sequence[index] = replacement
                    writes += 1
                except Exception:
                    pass
        return writes
    return 0


def _complete_row(rows: Any, index: int, row: Any) -> int:
    try:
        completed = getattr(row, "CompletedObjectives", None)
    except Exception:
        completed = None
    if completed is None:
        return 0
    writes = _max_completed_objectives(completed)
    try:
        setattr(row, "CompletedObjectives", completed)
    except Exception:
        pass
    try:
        rows[index] = row
    except Exception:
        pass
    return writes


def _identifier_value(token: str) -> Any:
    preferred = preferred_challenge_identifier(token)
    try:
        from unrealsdk.unreal import FGameDataHandle

        return FGameDataHandle(CHALLENGE_TYPE_HANDLE, preferred)
    except Exception:
        return preferred


def _make_objective_row(token: str) -> Any | None:
    try:
        import unrealsdk
    except Exception:
        return None
    identifier = _identifier_value(token)
    for kwargs in (
        {"ChallengeIdentifier": identifier},
        {"ChallengeIdentifier": preferred_challenge_identifier(token)},
    ):
        try:
            row = unrealsdk.make_struct("ChallengeObjectiveState", **kwargs)
        except Exception:
            row = None
        if row is not None:
            try:
                _max_completed_objectives(getattr(row, "CompletedObjectives", None))
            except Exception:
                pass
            return row
    return None


def _append_objective_row(rows: Any, token: str) -> bool:
    identifier = _identifier_value(token)
    emplace = getattr(rows, "emplace_struct", None)
    if callable(emplace):
        for kwargs in (
            {"ChallengeIdentifier": identifier},
            {"ChallengeIdentifier": preferred_challenge_identifier(token)},
        ):
            try:
                emplace(**kwargs)
                row = rows[len(rows) - 1]
                _complete_row(rows, len(rows) - 1, row)
                return True
            except Exception:
                continue
    row = _make_objective_row(token)
    return row is not None and _append(rows, row)


def complete_selected_challenge_objective_states(
    pc: Any,
    tokens: list[str] | tuple[str, ...],
    *,
    log: LogFn | None = None,
) -> int:
    """Max or append only the requested challenge-objective rows."""
    player_state = getattr(pc, "PlayerState", None) if pc is not None else None
    rows = getattr(player_state, "ChallengeObjectiveStates", None) if player_state else None
    if rows is None:
        return 0
    try:
        entries = list(rows)
    except Exception:
        return 0
    requested = tuple(str(token).strip() for token in tokens if str(token).strip())
    wanted_by_token = {
        token: {variant.casefold() for variant in _identifier_variants(token)}
        for token in requested
    }
    found: set[str] = set()
    writes = 0
    for index, entry in enumerate(entries):
        identifier = _identifier_text(
            getattr(entry, "ChallengeIdentifier", None),
        ).casefold()
        for token, variants in wanted_by_token.items():
            if identifier and identifier in variants:
                writes += _complete_row(rows, index, entry)
                found.add(token)
                break
    for token in requested:
        if token not in found and _append_objective_row(rows, token):
            writes += 1
    _log(
        log,
        f"Targeted ChallengeObjectiveStates: tokens={len(requested)} writes={writes}.",
    )
    return writes


def set_replicated_challenge_completion_bits(pc: Any) -> int:
    """Max every currently loaded replicated challenge-completion word."""
    player_state = getattr(pc, "PlayerState", None) if pc is not None else None
    replicated = (
        getattr(player_state, "ReplicatedChallengeCompletion", None)
        if player_state is not None
        else None
    )
    if replicated is None:
        return 0
    for items_name in ("items", "Items"):
        sequence = getattr(replicated, items_name, None)
        if sequence is None:
            continue
        writes = 0
        try:
            count = len(list(sequence))
        except Exception:
            count = 0
        for index in range(count):
            try:
                item = sequence[index]
                current = getattr(item, "BitField", None)
            except Exception:
                continue
            if not isinstance(current, int) or current == COMPLETE_WORD:
                continue
            try:
                setattr(item, "BitField", COMPLETE_WORD)
                try:
                    sequence[index] = item
                except Exception:
                    pass
                writes += 1
            except Exception:
                continue
        return writes
    return 0


def complete_loaded_challenge_ui(
    pc: Any,
    *,
    log: LogFn | None = None,
    touch_replicated: bool = False,
) -> dict[str, int]:
    """Max the objective bits on every challenge row already loaded by the game."""
    report = {"cos_bits": 0, "replicated_bits": 0, "cos_rows": 0}
    player_state = getattr(pc, "PlayerState", None) if pc is not None else None
    rows = getattr(player_state, "ChallengeObjectiveStates", None) if player_state else None
    if rows is None:
        _log(log, "Loaded-challenge UI complete: PlayerState rows unavailable.")
        return report
    try:
        entries = list(rows)
    except Exception:
        entries = []
    report["cos_rows"] = len(entries)
    for index, row in enumerate(entries):
        if row is not None:
            report["cos_bits"] += _complete_row(rows, index, row)
    if touch_replicated:
        report["replicated_bits"] = set_replicated_challenge_completion_bits(pc)
    _log(
        log,
        "Loaded-challenge UI complete: "
        f"cos_rows={report['cos_rows']} cos_bit_writes={report['cos_bits']} "
        f"replicated_bit_writes={report['replicated_bits']}.",
    )
    return report
