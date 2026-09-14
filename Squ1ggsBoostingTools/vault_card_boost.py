"""Standalone vault-card 1/2/3/4 maxing for Squ1ggs Boosting Tools."""

from __future__ import annotations

from typing import Any, Callable

from .vault_cards import apply_max_to_all_vault_cards

_MAX_WALLET = 2_147_483_647
# NCS Oak2_VaultCardXP_Progression levelcap — not 9_999_999 (that broke XP bars).
_MAX_VAULT_XP_LEVEL = 9_999


def _economy_max_vault_cards(
    target_pc: Any,
    *,
    log: Callable[[str], None],
) -> tuple[bool, str]:
    del log
    from .player_economy import (
        _MAX_WALLET_AMOUNT,
        _do_set_currency_absolute,
        _set_experience_level_via_bp,
    )

    ps = getattr(target_pc, "PlayerState", None)
    if ps is None:
        return False, "no PlayerState"

    ok_bits: list[str] = []
    fail = False

    for kind in ("vaultcard1", "vaultcard2", "vaultcard3", "vaultcard4"):
        ok, message = _do_set_currency_absolute(kind, _MAX_WALLET_AMOUNT, pc=target_pc)
        if ok:
            ok_bits.append(f"{kind}={message}")
        else:
            ok_bits.append(f"{kind}=FAIL: {message}")
            fail = True

    # Direct BP writes use the already-resolved PlayerState and do not depend on display names.
    # Slots 2–5 = vault card 1–4 XP (when ExperienceState is long enough).
    es = getattr(ps, "ExperienceState", None)
    if es is not None:
        try:
            n = len(es)
        except Exception:  # noqa: BLE001
            n = 0
        for slot in range(2, min(n, 6)):
            if _set_experience_level_via_bp(ps, slot, _MAX_VAULT_XP_LEVEL):
                ok_bits.append(f"slot{slot}=BP@{_MAX_VAULT_XP_LEVEL}")
            else:
                fail = True

    summary = ", ".join(ok_bits) if ok_bits else "no writes"
    return not fail, summary


def max_all_vault_cards_for_pc(
    target_pc: Any,
    *,
    log: Callable[[str], None] | None = None,
    allow_fallback: bool = True,
) -> tuple[bool, str]:
    """Max all vault cards (tokens + XP) on one PlayerController."""
    log_fn = log or (lambda _m: None)
    ps = getattr(target_pc, "PlayerState", None)
    if ps is None:
        return False, "no PlayerState on target PlayerController"

    try:
        ok, bits = apply_max_to_all_vault_cards(target_pc, ps, selector="all")
    except Exception as exc:  # noqa: BLE001
        ok, bits = False, [f"internal vault-card path failed: {type(exc).__name__}: {exc}"]
    summary = "; ".join(bits[:14])
    if ok:
        log_fn(f"Vault cards max (Boosting Tools): {summary}")
        return True, summary
    log_fn(f"Vault cards max partial (Boosting Tools): {summary}")
    # Double wallet/XP writes hitch the host ~3–5s and can kick lobby guests.
    if not allow_fallback:
        return False, summary

    ok, summary = _economy_max_vault_cards(target_pc, log=log_fn)
    log_fn(f"Vault cards max (direct fallback): {summary}")
    return ok, summary


def max_vault_card_three_for_pc(
    target_pc: Any,
    *,
    log: Callable[[str], None] | None = None,
) -> tuple[bool, str]:
    """Max Raid 3 / vault card 3 only."""
    log_fn = log or (lambda _m: None)
    ps = getattr(target_pc, "PlayerState", None)
    if ps is None:
        return False, "no PlayerState"

    try:
        ok, bits = apply_max_to_all_vault_cards(target_pc, ps, selector="raid3")
    except Exception as exc:  # noqa: BLE001
        ok, bits = False, [f"internal vault-card path failed: {type(exc).__name__}: {exc}"]
    summary = "; ".join(bits[:10])
    log_fn(f"Vault card 3 (Boosting Tools): {summary}")
    if ok:
        return True, summary

    from .player_economy import _do_set_currency_absolute, _set_experience_level_via_bp

    currency_ok, currency_message = _do_set_currency_absolute(
        "vaultcard3",
        _MAX_WALLET,
        pc=target_pc,
    )
    xp_ok = _set_experience_level_via_bp(ps, 4, _MAX_VAULT_XP_LEVEL)
    return (
        currency_ok and xp_ok,
        f"vaultcard3 currency={'OK' if currency_ok else 'FAIL'} ({currency_message}); "
        f"XP slot 4={'OK' if xp_ok else 'FAIL'} at {_MAX_VAULT_XP_LEVEL}",
    )
