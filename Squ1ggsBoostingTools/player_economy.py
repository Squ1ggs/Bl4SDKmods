"""Targeted currency, experience, and SDU point helpers for lobby players."""

from __future__ import annotations

import argparse
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from mods_base import command
from unrealsdk import find_all, find_class, find_object, logging
from unrealsdk.unreal import FGbxDefPtr, UObject

from .party_helpers import (
    _gbc_find_pc_for_player_state,
    _gbc_find_remote_pc_name_fallback,
    _gbc_is_listen_host_world,
    _gbc_resolve_player_display_name,
    _gbc_resolve_player_index_for_name_substring,
    _gbc_session_world_and_gamestate,
)
from .currency_give import (
    give_currency_by_needle,
    read_currency_amount,
    resolve_currency_slot_idx,
    set_currency_to_target,
)

_PREFIX = "[Squ1ggs's Boosting Tools | Economy]"


def _log(msg: str, *args: Any) -> None:
    logging.info(_PREFIX + " " + (msg % args if args else msg))


def _log_err(msg: str, *args: Any) -> None:
    logging.error(_PREFIX + " " + (msg % args if args else msg))


_CURRENCY_KIND_ALIASES: Dict[str, str] = {
    "cash": "Cash",
    "money": "Cash",
    "eridium": "eridium",
    "vaultcard1": "VaultCard01_Tokens",
    "vaultcard_1": "VaultCard01_Tokens",
    "vc1": "VaultCard01_Tokens",
    "vaultcard2": "VaultCard02_Tokens",
    "vaultcard_2": "VaultCard02_Tokens",
    "vc2": "VaultCard02_Tokens",
    "vaultcard3": "VaultCard03_Tokens",
    "vaultcard_3": "VaultCard03_Tokens",
    "vc3": "VaultCard03_Tokens",
    "vaultcard4": "VaultCard04_Tokens",
    "vaultcard_4": "VaultCard04_Tokens",
    "vc4": "VaultCard04_Tokens",
}

# OakPlayerState.ExperienceState fixed slots (aliases → index).
#   0 — Player/character level
#   1 — Specialization level
#   2 — Vault card 01 XP
#   3 — Vault card 02 XP
#   4 — Vault card 03 XP (Raid 3)
#   5 — Vault card 04 XP (Desert Dreams)
# Level changes now go through OakPlayerState.BP_SetExperienceLevel using an
# FGbxDefPtr to /Script/GbxGame.GbxExperienceDef. This is much safer than
# writing ExperienceState fields directly, because the engine updates related
# level/XP state itself. For Character, the working token is exactly
# FGbxDefPtr(name="Character", ref="/Script/GbxGame.GbxExperienceDef").
_MAX_PLAYER_LEVEL_ENGINE = 70
_MAX_SPEC_LEVEL_ENGINE = 701
# NCS Oak2_VaultCardXP_Progression levelcap (Engine/Content/_NCS).
_MAX_VAULT_XP_LEVEL_ENGINE = 9_999


def _clamp_engine_experience_level(track_index: int, level: int) -> int:
    lv = max(0, int(level))
    if track_index == 0:
        return min(lv, _MAX_PLAYER_LEVEL_ENGINE)
    if track_index == 1:
        return min(lv, _MAX_SPEC_LEVEL_ENGINE)
    return min(lv, _MAX_VAULT_XP_LEVEL_ENGINE)


_EXPERIENCE_TRACK_ALIASES: Dict[str, int] = {
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "character": 0,
    "player": 0,
    "main": 0,
    "level": 0,
    "specialization": 1,
    "spec": 1,
    "arsenal": 1,
    "vaultcard_xp_1": 2,
    "vaultcard1_xp": 2,
    "vc1_xp": 2,
    "vaultcard_xp_2": 3,
    "vaultcard2_xp": 3,
    "vc2_xp": 3,
    "vaultcard_xp_3": 4,
    "vaultcard3_xp": 4,
    "vc3_xp": 4,
    "vaultcard_xp_4": 5,
    "vaultcard4_xp": 5,
    "vc4_xp": 5,
}


def _normalize_track_key(track_raw: str) -> str:
    """Strip BOM / ZWSP, Unicode-normalize (e.g. fullwidth digits → ASCII), lowercase for alias lookup."""
    s = unicodedata.normalize("NFKC", (track_raw or "").strip())
    for ch in ("\ufeff", "\u200b", "\u200c", "\u200d"):
        s = s.replace(ch, "")
    return s.strip().lower()

_CURRENCY_DEF_SCRIPT_PATHS = (
    "/Script/GbxGame.GbxCurrencyDef",
    "/Script/OakGame.GbxCurrencyDef",
)

_INT32_MAX = 2_147_483_647
_MAX_WALLET_AMOUNT = 2_147_483_647
_SDU_POINTS_POOL_INDEX = 2
_MAX_SDU_POINTS = 3225

# --- Cumulative total XP (ExperiencePoints) vs level — from workspace `xp.md` (BL4 / Oak) ---
# Under-shooting total XP for a level causes HUD counter glitches; use documented curves + margin.
_CHAR_XP_ANCHOR_L50 = 3_430_227
_CHAR_XP_ANCHOR_L60 = 5_714_893
_SPEC_XP_ANCHOR_L701 = 7_431_910_510
# Vault XP (tracks 2–4): NCS Oak2_VaultCardXP_Progression exponential
# (basevalue=1, basemultiplier=2, multiplier=8, power=2.25, levelcap=9999).
# Do NOT use save-sample anchors — those wrote multi-trillion ExperiencePoints
# and blocked further leveling.
_VAULT_XP_NCS_BASEVALUE = 1.0
_VAULT_XP_NCS_BASEMULTIPLIER = 2.0
_VAULT_XP_NCS_MULTIPLIER = 8.0
_VAULT_XP_NCS_POWER = 2.25


def _char_segment1_total_xp(level: float) -> float:
    """Total cumulative XP for character levels 11–50 (polynomial from xp.md)."""
    return (
        20.435970 * level**3
        + 445.422020 * level**2
        + -5301.029340 * level
        + 27953.516161
    )


def _spec_segment1_total_xp(level: float) -> float:
    """Specialization total XP, levels 11–31."""
    return (
        83.390778 * level**3
        + -2314.676389 * level**2
        + 41061.771085 * level
        + -216525.913214
    )


def _spec_segment2_total_xp(level: float) -> float:
    """Specialization total XP, levels 32–200."""
    return (
        20.903278 * level**3
        + 1701.317660 * level**2
        + -74334.753724 * level
        + 1403361.683375
    )


def _spec_segment3_total_xp(level: float) -> float:
    """Specialization total XP, levels 250–450."""
    return (
        16.708444 * level**3
        + 4297.272805 * level**2
        + -645890.804295 * level
        + 46158303.367444
    )


def _spec_segment4_total_xp(level: float) -> float:
    """Specialization total XP, levels 500–701."""
    return (
        14.960904 * level**3
        + 6708.446543 * level**2
        + -1773218.961259 * level
        + 224787945.740717
    )


def _xp_safety_margin(total: int) -> int:
    """Deprecated — overshooting total XP past the next-level threshold blocks leveling."""
    return 0


def _vault_ncs_cumulative_total_xp(level: int) -> int:
    """
    Cumulative ExperiencePoints to sit at ``level`` with an empty bar, from
    Nexus ``Oak2_VaultCardXP_Progression`` (sum of per-level costs).

    cost(i) = Multiplier * (BaseValue + BaseMultiplier * i^Power)
    """
    lv = max(0, min(int(level), _MAX_VAULT_XP_LEVEL_ENGINE))
    if lv <= 1:
        return 0
    total = 0.0
    for i in range(1, lv):
        total += _VAULT_XP_NCS_MULTIPLIER * (
            _VAULT_XP_NCS_BASEVALUE
            + _VAULT_XP_NCS_BASEMULTIPLIER * (float(i) ** _VAULT_XP_NCS_POWER)
        )
    return max(0, int(round(total)))


def _vault_track_cumulative_total_xp(level: int, prior_level: int, prior_points: int) -> int:
    """Lifetime ExperiencePoints for vault-card tracks at ExperienceLevel ``level``."""
    lvl = max(0, min(int(level), _MAX_VAULT_XP_LEVEL_ENGINE))
    if lvl <= 0:
        return 0
    # Prefer NCS curve — prior-row scaling amplified broken trillion-point saves.
    return _vault_ncs_cumulative_total_xp(lvl)


def _character_cumulative_total_xp(level: int) -> int | None:
    """
    Cumulative total XP for OakPlayerState ExperienceState slot 0 (character level).
    Anchors L50 / L60 from xp.md; polynomial segment for 11–50; linear bridge 50–60; extrapolate past 60.
    """
    if level <= 1:
        return 0
    L = float(level)
    if level < 11:
        # xp.md: levels 1–10 are manually tuned — ramp toward segment-1 at 11 instead of mis-fitting the cubic.
        t = (level - 1) / 10.0
        base = _char_segment1_total_xp(11.0)
        return max(0, int(round(base * t)))
    if level <= 50:
        est = int(round(_char_segment1_total_xp(L)))
        if level == 50:
            return max(est, _CHAR_XP_ANCHOR_L50)
        return max(0, est)
    if level <= 60:
        t = (level - 50) / 10.0
        return int(round(_CHAR_XP_ANCHOR_L50 + t * (_CHAR_XP_ANCHOR_L60 - _CHAR_XP_ANCHOR_L50)))
    per = (_CHAR_XP_ANCHOR_L60 - _CHAR_XP_ANCHOR_L50) / 10.0
    return int(round(_CHAR_XP_ANCHOR_L60 + (level - 60) * per))


def _specialization_cumulative_total_xp(level: int) -> int | None:
    """
    Cumulative total XP for ExperienceState slot 1 (specialization).
    Piecewise curves + linear bridges in gaps (201–249, 451–499) from xp.md; anchor near 701.
    """
    if level <= 1:
        return 0
    L = float(level)
    if level < 11:
        t = (level - 1) / 10.0
        base = _spec_segment1_total_xp(11.0)
        return max(0, int(round(base * t)))
    if level <= 31:
        return max(0, int(round(_spec_segment1_total_xp(L))))
    if level <= 200:
        return max(0, int(round(_spec_segment2_total_xp(L))))
    if level < 250:
        y200 = _spec_segment2_total_xp(200.0)
        y250 = _spec_segment3_total_xp(250.0)
        t = (L - 200.0) / 50.0
        return max(0, int(round(y200 + t * (y250 - y200))))
    if level <= 450:
        return max(0, int(round(_spec_segment3_total_xp(L))))
    if level < 500:
        y450 = _spec_segment3_total_xp(450.0)
        y500 = _spec_segment4_total_xp(500.0)
        t = (L - 450.0) / 50.0
        return max(0, int(round(y450 + t * (y500 - y450))))
    if level <= 701:
        est = int(round(_spec_segment4_total_xp(L)))
        if level == 701:
            return max(est, _SPEC_XP_ANCHOR_L701)
        return max(0, est)
    # Past 701 (e.g. RequiredForNextLevel at cap uses lvl+1 == 702): extrapolate segment 4.
    return max(0, int(round(_spec_segment4_total_xp(L))))


def _cumulative_floor_for_track(track_index: int, level: int, prior_lvl: int, prior_pts: int) -> int:
    """Minimum lifetime ExperiencePoints to sit at ``level`` with an empty bar (HUD thresholds)."""
    lv = max(0, int(level))
    if track_index == 0:
        return int(_character_cumulative_total_xp(lv))
    if track_index == 1:
        return int(_specialization_cumulative_total_xp(lv))
    return _vault_track_cumulative_total_xp(lv, prior_lvl, prior_pts)


def _cumulative_next_floor_for_track(track_index: int, level: int, prior_lvl: int, prior_pts: int) -> int:
    """
    Cumulative lifetime XP threshold to finish ``level`` and reach ``level + 1`` at 0 bar.
    Used for ExperiencePointsRequiredForNextLevel.
    """
    lv = max(0, int(level))
    if track_index == 0:
        return int(_character_cumulative_total_xp(lv + 1))
    if track_index == 1:
        return int(_specialization_cumulative_total_xp(lv + 1))
    if lv >= _MAX_VAULT_XP_LEVEL_ENGINE:
        cur = _vault_track_cumulative_total_xp(lv, prior_lvl, prior_pts)
        prev1 = _vault_track_cumulative_total_xp(max(0, lv - 1), prior_lvl, prior_pts)
        step = max(1, cur - prev1)
        return cur + step
    return _vault_track_cumulative_total_xp(lv + 1, prior_lvl, prior_pts)


def _coerce_experience_requirement_pair(req_prev: int, req_next: int) -> tuple[int, int]:
    """Keep Next strictly above Prev so UI / logic never sees an inverted range."""
    rp = max(0, int(req_prev))
    rn = max(0, int(req_next))
    if rn <= rp:
        rn = rp + max(1, rp // 1_000_000 or 1)
    return rp, rn


_EXPERIENCE_DEF_SCRIPT_PATHS = (
    "/Script/GbxGame.GbxExperienceDef",
    "/Script/OakGame.GbxExperienceDef",
)

_EXPERIENCE_TRACK_TOKEN_FALLBACKS: Dict[int, Tuple[str, ...]] = {
    0: ("Character",),
    1: ("Specialization", "Specialisation"),
    2: ("VaultCard01", "VaultCard1", "VaultCard01_XP", "VaultCard01_Experience"),
    3: ("VaultCard02", "VaultCard2", "VaultCard02_XP", "VaultCard02_Experience"),
    4: ("VaultCard03", "VaultCard3", "VaultCard03_XP", "VaultCard03_Experience"),
    5: ("VaultCard04", "VaultCard4", "VaultCard04_XP", "VaultCard04_Experience"),
}


def _find_experience_def_struct() -> Optional[Any]:
    for object_path in _EXPERIENCE_DEF_SCRIPT_PATHS:
        try:
            resolved = find_object("ScriptStruct", object_path)
        except Exception:
            resolved = None
        if isinstance(resolved, UObject):
            return resolved
    try:
        for candidate in find_all("ScriptStruct", False) or []:
            if getattr(candidate, "Name", None) == "GbxExperienceDef" or str(candidate).endswith("GbxExperienceDef'"):
                return candidate
    except Exception:
        pass
    return None


def _make_experience_def_ptr(token_name: str) -> Optional[FGbxDefPtr]:
    struct_u = _find_experience_def_struct()
    if struct_u is None:
        _log_err("Could not resolve GbxExperienceDef ScriptStruct.")
        return None
    tail = (token_name or "").strip().split("/")[-1]
    if not tail:
        return None
    try:
        from unrealsdk.unreal import FGbxDefPtr as _FGbxDefPtr  # pyright: ignore[reportMissingImports]
    except Exception:
        _FGbxDefPtr = FGbxDefPtr  # type: ignore[misc, assignment]
    if struct_u is not None:
        for type_arg in (struct_u, "GbxExperienceDef", "/Script/GbxGame.GbxExperienceDef"):
            try:
                return _FGbxDefPtr(tail, type=type_arg)  # type: ignore[call-arg,misc]
            except Exception:
                continue
        try:
            return _FGbxDefPtr(tail)  # type: ignore[call-arg,misc]
        except Exception:
            pass
    try:
        ptr = FGbxDefPtr()
    except Exception as e:
        _log_err("FGbxDefPtr allocation failed for experience: %s", e)
        return None
    if not _assign_fgbx_def_ptr_fields(ptr, tail, struct_u):
        _log_err("FGbxDefPtr: could not set name/ref for experience token %r.", tail)
        return None
    return ptr


def _experience_state_token_name(row: Any) -> Optional[str]:
    """Best-effort extraction of the SName token shown as Name: 'Character' in runtime dumps."""
    try:
        eid = getattr(row, "ExperienceId", None)
    except Exception:
        eid = None
    if eid is None:
        return None
    for attr in ("Name", "name"):
        try:
            value = getattr(eid, attr)
            if isinstance(value, str) and value:
                return value
        except Exception:
            pass
    try:
        text = str(eid)
    except Exception:
        return None
    m = re.search(r"Name:\s*'([^']+)'", text)
    if m:
        return m.group(1)
    m = re.search(r'Name:\s*"([^"]+)"', text)
    if m:
        return m.group(1)
    return None


def _candidate_experience_tokens(track_index: int, row: Any) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for token in (_experience_state_token_name(row), *(_EXPERIENCE_TRACK_TOKEN_FALLBACKS.get(track_index, ()))):
        if token and token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _assign_fgbx_def_ptr_fields(ptr: Any, name: str, ref: Any) -> bool:
    for name_attr, ref_attr in (("name", "ref"), ("_experimental_name", "_experimental_ref")):
        try:
            setattr(ptr, name_attr, name)
            setattr(ptr, ref_attr, ref)
            return True
        except Exception:
            continue
    return False


def _find_currency_def_struct() -> Optional[Any]:
    for class_name in ("ScriptStruct", "Object"):
        for object_path in _CURRENCY_DEF_SCRIPT_PATHS:
            try:
                resolved = find_object(class_name, object_path)
            except Exception:
                resolved = None
            if isinstance(resolved, UObject):
                return resolved
    try:
        for candidate in find_all("ScriptStruct", False) or []:
            if getattr(candidate, "Name", None) == "GbxCurrencyDef":
                return candidate
    except Exception:
        pass
    return None


def _make_currency_def_ptr(token_tail: str) -> Optional[FGbxDefPtr]:
    struct_u = _find_currency_def_struct()
    if struct_u is None:
        _log_err("Could not resolve GbxCurrencyDef ScriptStruct.")
        return None
    tail = (token_tail or "").strip().split("/")[-1]
    if not tail:
        return None
    try:
        ptr = FGbxDefPtr()
    except Exception:
        return None
    if not _assign_fgbx_def_ptr_fields(ptr, tail, struct_u):
        _log_err("FGbxDefPtr: could not set name/ref for currency.")
        return None
    return ptr


def _get_currency_function_library() -> Optional[Any]:
    try:
        cls = find_class("GbxCurrencyFunctionLibrary")
        if cls is not None:
            cdo = getattr(cls, "ClassDefaultObject", None)
            if cdo is not None:
                return cdo
    except Exception:
        pass
    try:
        objs = find_all("GbxCurrencyFunctionLibrary", False) or []
        if objs:
            return objs[-1]
    except Exception:
        pass
    return None


def _safe_int(tok: str) -> Optional[int]:
    t = (tok or "").strip().replace(",", "")
    if not t or t[0] not in "-0123456789":
        return None
    try:
        return int(t)
    except ValueError:
        try:
            return int(float(t))
        except ValueError:
            return None


def _parse_name_suffix(parts: List[str]) -> Tuple[List[str], str]:
    """Split [... tokens before `name` ...] and name substring (joined)."""
    low = [p.lower() for p in parts]
    try:
        ni = low.index("name")
    except ValueError:
        return parts, ""
    head = parts[:ni]
    tail = " ".join(parts[ni + 1 :]).strip()
    return head, tail


def _resolve_target_pc_for_name(name_sub: str) -> Tuple[Optional[Any], str]:
    world, gs = _gbc_session_world_and_gamestate()
    if world is None or gs is None:
        return None, "no world or GameState"
    if not _gbc_is_listen_host_world(world):
        return None, "listen host only (open console on host)"
    pa = getattr(gs, "PlayerArray", None)
    if pa is None:
        return None, "PlayerArray missing"
    idx, err = _gbc_resolve_player_index_for_name_substring(gs, name_sub)
    if err:
        return None, err
    try:
        ps = pa[idx]
    except Exception as e:
        return None, "PlayerArray read failed: %s" % e
    if ps is None:
        return None, "null PlayerState at index %s" % idx
    pc = _gbc_find_pc_for_player_state(ps, world)
    if pc is None:
        return None, "no PlayerController for that player — run gbc_players"
    return pc, ""


def _resolve_target_pc_for_index(player_index: int) -> Tuple[Optional[Any], str]:
    world, gs = _gbc_session_world_and_gamestate()
    if world is None or gs is None:
        return None, "no world or GameState"
    if not _gbc_is_listen_host_world(world):
        return None, "listen host only (open console on host)"
    pa = getattr(gs, "PlayerArray", None)
    if pa is None:
        return None, "PlayerArray missing"
    try:
        n_pa = len(pa)
    except Exception as e:
        return None, "PlayerArray length failed: %s" % e
    if player_index < 0 or player_index >= n_pa:
        return None, "player index %s out of range (0..%s)" % (player_index, max(0, n_pa - 1))
    try:
        ps = pa[player_index]
    except Exception as e:
        return None, "PlayerArray[%s] read failed: %s" % (player_index, e)
    if ps is None:
        return None, "null PlayerState at index %s" % player_index
    pc = _gbc_find_pc_for_player_state(ps, world)
    if pc is None:
        from mods_base import get_pc

        host_pc = get_pc()
        host_ps = getattr(host_pc, "PlayerState", None) if host_pc is not None else None
        name = _gbc_resolve_player_display_name(ps)
        pc = _gbc_find_remote_pc_name_fallback(ps, host_ps, name, "[SQBT]")
    if pc is None:
        return None, "no PlayerController for player index %s — run gbc_players" % player_index
    return pc, ""


def _resolve_target_pc_from_parts(parts: List[str], command_name: str) -> Tuple[Optional[Any], str]:
    if not parts:
        return None, "Usage: %s name <substring> | %s index N" % (command_name, command_name)
    head, name_sub = _parse_name_suffix(parts)
    if name_sub:
        return _resolve_target_pc_for_name(name_sub)
    if len(parts) == 2 and parts[0].lower() == "index":
        idx = _safe_int(parts[1])
        if idx is None:
            return None, "%s: expected integer after index" % command_name
        return _resolve_target_pc_for_index(idx)
    return None, "Usage: %s name <substring> | %s index N" % (command_name, command_name)


def _give_currency_on_pc(target_pc: Any, currency_token: str, amount: int) -> bool:
    """Additive GiveCurrency — prefer live wallet def ptr (see currency_give)."""
    from .currency_give import give_currency_on_pc

    ok, message = give_currency_on_pc(target_pc, currency_token, int(amount))
    if ok:
        _log("%s", message)
    else:
        _log_err("%s", message)
    return bool(ok)


def _give_currency_on_pc_detailed(target_pc: Any, currency_token: str, amount: int) -> tuple[bool, str]:
    from .currency_give import give_currency_on_pc

    return give_currency_on_pc(target_pc, currency_token, int(amount))


def _target_character_for_pc(target_pc: Any) -> Optional[Any]:
    for attr in ("Pawn", "AcknowledgedPawn", "Character", "MyCharacter"):
        try:
            obj = getattr(target_pc, attr, None)
        except Exception:
            obj = None
        if obj is not None:
            return obj
    try:
        ps = getattr(target_pc, "PlayerState", None)
    except Exception:
        ps = None
    if ps is not None:
        for attr in ("PawnPrivate", "Pawn", "Character"):
            try:
                obj = getattr(ps, attr, None)
            except Exception:
                obj = None
            if obj is not None:
                return obj
    return None


def _set_max_sdu_points_on_pc(target_pc: Any) -> bool:
    character = _target_character_for_pc(target_pc)
    if character is None:
        _log_err("boost_maxsdu: could not resolve target character/pawn from PlayerController.")
        return False
    try:
        mgr = getattr(character, "GbxProgressionManager", None)
    except Exception as e:
        _log_err("boost_maxsdu: reading GbxProgressionManager failed: %s", e)
        return False
    if mgr is None:
        _log_err("boost_maxsdu: target character has no GbxProgressionManager.")
        return False
    try:
        container = getattr(mgr, "ProgressPointsContainer", None)
        pools = getattr(container, "PointsAcquiredPerPool", None) if container is not None else None
    except Exception as e:
        _log_err("boost_maxsdu: reading PointsAcquiredPerPool failed: %s", e)
        return False
    if pools is None:
        _log_err("boost_maxsdu: ProgressPointsContainer.PointsAcquiredPerPool missing.")
        return False
    try:
        n_pools = len(pools)
    except Exception as e:
        _log_err("boost_maxsdu: PointsAcquiredPerPool length failed: %s", e)
        return False
    if _SDU_POINTS_POOL_INDEX < 0 or _SDU_POINTS_POOL_INDEX >= n_pools:
        _log_err(
            "boost_maxsdu: pool index %s out of range (length %s).",
            _SDU_POINTS_POOL_INDEX,
            n_pools,
        )
        return False
    try:
        old_value = int(pools[_SDU_POINTS_POOL_INDEX])
    except Exception:
        old_value = 0
    try:
        pools[_SDU_POINTS_POOL_INDEX] = _MAX_SDU_POINTS
    except Exception as e:
        _log_err("boost_maxsdu: direct PointsAcquiredPerPool write failed: %s", e)
        return False
    try:
        setattr(mgr, "ProgressGraphsArrayDirty", 3)
    except Exception:
        pass
    _log(
        "boost_maxsdu: set PointsAcquiredPerPool[%s] %s -> %s.",
        _SDU_POINTS_POOL_INDEX,
        old_value,
        _MAX_SDU_POINTS,
    )
    return True


def _get_experience_level_via_bp(ps: Any, track_index: int) -> int | None:
    """Best-effort BP_GetExperienceLevel for one ExperienceState track."""
    es = getattr(ps, "ExperienceState", None)
    if es is None:
        return None
    try:
        n = len(es)
        if track_index < 0 or track_index >= n:
            return None
        row = es[track_index]
    except Exception:
        return None
    for token in _candidate_experience_tokens(track_index, row):
        xp_def = _make_experience_def_ptr(token)
        if xp_def is None:
            continue
        try:
            return int(ps.BP_GetExperienceLevel(xp_def))
        except Exception:
            continue
    try:
        return int(getattr(row, "ExperienceLevel"))
    except Exception:
        return None


def _ensure_experience_level_via_bp(ps: Any, track_index: int, level: int, *, attempts: int = 3) -> bool:
    """Set experience level and verify readback; retry if the game settles short."""
    target = _clamp_engine_experience_level(track_index, max(0, int(level)))
    last_set_ok = False
    for _ in range(max(1, int(attempts))):
        last_set_ok = _set_experience_level_via_bp(ps, track_index, target)
        if not last_set_ok:
            continue
        after = _get_experience_level_via_bp(ps, track_index)
        if after is not None and int(after) == target:
            return True
        # Wrong readback → retry; None readback → keep trying until last attempt.
    after = _get_experience_level_via_bp(ps, track_index)
    if after is not None:
        return int(after) == target
    return bool(last_set_ok)


def _set_experience_level_via_bp(ps: Any, track_index: int, level: int) -> bool:
    es = getattr(ps, "ExperienceState", None)
    if es is None:
        _log_err("PlayerState has no ExperienceState array.")
        return False
    try:
        n = len(es)
    except Exception as e:
        _log_err("ExperienceState length: %s", e)
        return False
    if track_index < 0 or track_index >= n:
        _log_err("Experience track index %s out of range (0..%s).", track_index, max(0, n - 1))
        return False

    requested = max(0, int(level))
    lvl = _clamp_engine_experience_level(track_index, requested)
    if lvl != requested:
        _log(
            "ExperienceState[%s]: clamped requested level %s to %s (engine cap for this track).",
            track_index,
            requested,
            lvl,
        )

    try:
        row = es[track_index]
    except Exception as e:
        _log_err("ExperienceState[%s] read failed: %s", track_index, e)
        return False

    candidates = _candidate_experience_tokens(track_index, row)
    if not candidates:
        _log_err("ExperienceState[%s]: could not determine experience token name.", track_index)
        return False

    last_error: Optional[Exception] = None
    for token in candidates:
        xp_def = _make_experience_def_ptr(token)
        if xp_def is None:
            continue
        try:
            before = ps.BP_GetExperienceLevel(xp_def)
        except Exception:
            before = None
        try:
            ps.BP_SetExperienceLevel(xp_def, lvl)
        except Exception as e:
            last_error = e
            continue
        try:
            after = ps.BP_GetExperienceLevel(xp_def)
        except Exception:
            after = None
        if after == lvl or (before is not None and after is not None and after == lvl):
            _log(
                "ExperienceState[%s]: BP_SetExperienceLevel token=%r level %s -> %s (requested %s).",
                track_index,
                token,
                before,
                after,
                requested,
            )
            # Repair prior dumps that left ExperiencePoints past the next-level floor.
            try:
                floor_xp = _cumulative_floor_for_track(track_index, lvl, 0, 0)
                next_floor = _cumulative_next_floor_for_track(track_index, lvl, 0, 0)
                cur_xp = getattr(row, "ExperiencePoints", None)
                if cur_xp is not None and int(cur_xp) >= int(next_floor) and lvl > 0:
                    setattr(row, "ExperiencePoints", int(floor_xp))
                    _log(
                        "ExperienceState[%s]: clamped ExperiencePoints %s -> %s (was past next-level).",
                        track_index,
                        cur_xp,
                        floor_xp,
                    )
            except Exception as clamp_exc:  # noqa: BLE001
                _log(
                    "ExperienceState[%s]: XP clamp skipped (%s).",
                    track_index,
                    type(clamp_exc).__name__,
                )
            return True

    if last_error is not None:
        _log_err("BP_SetExperienceLevel failed for ExperienceState[%s]: %s", track_index, last_error)
    else:
        _log_err("BP_SetExperienceLevel failed for ExperienceState[%s].", track_index)
    return False


def _resolve_economy_pc(
    *,
    pc: Any | None = None,
    name_sub: str = "",
    player_index: int | None = None,
) -> tuple[Any | None, str]:
    """Resolve PlayerController for currency writes (host/standalone or direct PC)."""
    if pc is not None:
        return pc, ""
    if player_index is not None:
        resolved, err = _resolve_target_pc_for_index(int(player_index))
        if resolved is not None:
            return resolved, ""
        if err:
            return None, err
    name = (name_sub or "").strip()
    if name:
        resolved, err = _resolve_target_pc_for_name(name)
        if resolved is not None:
            return resolved, ""
        if err and "listen host only" not in err.lower():
            return None, err
    try:
        from mods_base import get_pc  # noqa: PLC0415

        local = get_pc()
    except Exception:
        local = None
    if local is not None:
        return local, ""
    return None, "no PlayerController — select a party player or load in-world as host"


def _do_set_currency_absolute(
    kind_raw: str,
    amount: int,
    name_sub: str = "",
    *,
    pc: Any | None = None,
    player_index: int | None = None,
) -> tuple[bool, str]:
    """Set wallet to an absolute amount (instant HUD) when possible."""
    resolved_pc, err = _resolve_economy_pc(pc=pc, name_sub=name_sub, player_index=player_index)
    if resolved_pc is None:
        return False, err or "no PlayerController"
    needle = str(kind_raw or "").strip().lower()
    target = max(0, min(_MAX_WALLET_AMOUNT, int(amount)))
    try:
        ok, msg = set_currency_to_target(resolved_pc, needle, target)
        if ok:
            return True, msg
        idx, _slot_name = resolve_currency_slot_idx(resolved_pc, needle)
        if idx is not None:
            after = read_currency_amount(resolved_pc, idx)
            if after is not None and after >= min(target, 1):
                return True, f"{needle} readback {after} ({msg})"
    except Exception as ex:  # noqa: BLE001
        _log("Internal set_currency_to_target failed (%s); trying direct GiveCurrency.", ex)
    key = (kind_raw or "").strip().lower()
    token = _CURRENCY_KIND_ALIASES.get(key)
    if not token:
        return False, f"unknown currency kind {kind_raw!r}"
    try:
        idx, _slot_name = resolve_currency_slot_idx(resolved_pc, needle)
        before = read_currency_amount(resolved_pc, idx) if idx is not None else None
        if before is not None and before >= target:
            return True, f"{needle} already {before}"
        delta = target - int(before or 0)
        if delta > 0:
            ok, give_msg = give_currency_by_needle(resolved_pc, needle, delta)
            if not ok:
                return False, give_msg
            if idx is not None:
                after = read_currency_amount(resolved_pc, idx)
                if after is not None and after >= min(target, 1):
                    return True, f"GiveCurrency +{delta} → {after} ({give_msg})"
            return True, give_msg
    except Exception:
        pass
    if _give_currency_on_pc(resolved_pc, token, target):
        return True, f"GiveCurrency direct {needle} -> {target}"
    return False, f"currency set failed for {needle} (target {target})"


def _do_give_currency(kind_raw: str, amount: int, name_sub: str) -> None:
    if not name_sub:
        _log_err(
            "Usage: givecurrency <kind> <amount> name <substring>  — kinds: cash, eridium, "
            "vaultcard1, vaultcard2, vaultcard3, vaultcard4"
        )
        return
    key = (kind_raw or "").strip().lower()
    token = _CURRENCY_KIND_ALIASES.get(key)
    if not token:
        _log_err(
            "Unknown currency kind %r — use cash, eridium, vaultcard1, vaultcard2, vaultcard3, vaultcard4.",
            kind_raw,
        )
        return
    if amount == 0:
        _log_err("Amount must be non-zero.")
        return
    if amount < -_INT32_MAX:
        _log_err("Negative amount out of int32 range.")
        return
    if amount > _MAX_WALLET_AMOUNT:
        _log_err("Amount above supported max wallet/int32 limit (%s).", _MAX_WALLET_AMOUNT)
        return
    pc, err = _resolve_target_pc_for_name(name_sub)
    if pc is None:
        _log_err("givecurrency: %s", err)
        return

    # GiveCurrency takes a 32-bit integer amount in current SDK builds, so large
    # wallet targets are delivered in int32-safe chunks.
    remaining = int(amount)
    if remaining < 0:
        if not _give_currency_on_pc(pc, token, remaining):
            _log_err("givecurrency failed for token=%s amount=%s.", token, remaining)
        return

    chunks = 0
    while remaining > 0:
        chunk = min(remaining, _INT32_MAX)
        if not _give_currency_on_pc(pc, token, chunk):
            _log_err("givecurrency failed for token=%s chunk=%s remaining=%s.", token, chunk, remaining)
            return
        remaining -= chunk
        chunks += 1
    if chunks > 1:
        _log("GiveCurrency delivered %s total to token=%s in %s chunks.", amount, token, chunks)


def _do_give_experience(track_raw: str, level: int, name_sub: str) -> None:
    if not name_sub:
        _log_err(
            "Usage: giveexperience <track> <level> name <substring>  — slots: 0 player level, 1 specialization, "
            "2 vault card 01, 3 vault card 02, 4 vault card 03, 5 vault card 04 "
            "(or aliases character/player, specialization, vaultcard_xp_1/2/3/4), or digit 0..5."
        )
        return
    tkey = _normalize_track_key(track_raw)
    if tkey not in _EXPERIENCE_TRACK_ALIASES:
        _log_err(
            "Unknown track %r — use slots 0..5 or character/player, specialization, vaultcard_xp_1/2/3/4.",
            track_raw,
        )
        return
    if level < 0:
        _log_err("Level must be non-negative.")
        return
    world, gs = _gbc_session_world_and_gamestate()
    if world is None or gs is None:
        _log_err("giveexperience: no world or GameState")
        return
    if not _gbc_is_listen_host_world(world):
        _log_err("giveexperience: listen host only")
        return
    player_idx, err = _gbc_resolve_player_index_for_name_substring(gs, name_sub)
    if err:
        _log_err("giveexperience: %s", err)
        return
    pa = getattr(gs, "PlayerArray", None)
    if pa is None:
        _log_err("giveexperience: PlayerArray missing")
        return
    try:
        ps = pa[player_idx]
    except Exception as e:
        _log_err("giveexperience: could not read PlayerState: %s", e)
        return
    if ps is None:
        _log_err("giveexperience: null PlayerState")
        return
    es = getattr(ps, "ExperienceState", None)
    try:
        es_n = len(es) if es is not None else 0
    except Exception:
        es_n = 0
    track_idx = _EXPERIENCE_TRACK_ALIASES[tkey]
    if track_idx < 0 or track_idx >= es_n:
        _log_err(
            "giveexperience: slot %s for track %r out of range (ExperienceState length %s).",
            track_idx,
            track_raw,
            es_n,
        )
        return
    if not _set_experience_level_via_bp(ps, track_idx, level):
        _log_err("giveexperience: BP_SetExperienceLevel failed.")


def _do_boost_maxsdu(parts: List[str]) -> None:
    pc, err = _resolve_target_pc_from_parts(parts, "boost_maxsdu")
    if pc is None:
        _log_err("boost_maxsdu: %s", err)
        return
    if not _set_max_sdu_points_on_pc(pc):
        _log_err("boost_maxsdu: failed.")


def max_all_for_target(
    *,
    name: str = "",
    player_index: int | None = None,
    pc: Any | None = None,
    options: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """
    Same Max All as Squ1ggs Boosting Tools ImGui button (cash/eridium/level/spec/SDU/vault).

    ``player_index`` is **0-based** ``PlayerArray`` index (host is usually ``0``).
    Prefer a live ``pc`` / index so SHiFT display names do not break delivery after lobby churn.
    """
    name_sub = (name or "").strip()
    pidx = int(player_index) if player_index is not None else None
    # Prefer index/pc over display-name string — SHiFT labels often differ from GetPlayerName().
    resolved_pc, err = _resolve_economy_pc(pc=pc, name_sub="", player_index=pidx)
    if resolved_pc is None and name_sub:
        resolved_pc, err = _resolve_economy_pc(pc=None, name_sub=name_sub, player_index=None)
    if resolved_pc is None:
        return False, err or "no PlayerController for max_all"
    pc = resolved_pc

    ps = getattr(pc, "PlayerState", None)
    engine_name = ""
    if ps is not None:
        try:
            from .party_helpers import _gbc_resolve_player_display_name  # noqa: PLC0415

            engine_name = str(_gbc_resolve_player_display_name(ps) or "").strip()
        except Exception:
            engine_name = ""
        if not engine_name or engine_name.startswith("("):
            for attr in ("PlayerNamePrivate", "PlayerName", "DisplayName", "Name"):
                try:
                    raw = getattr(ps, attr, None)
                except Exception:
                    raw = None
                text = str(raw or "").strip()
                if text and "OakPlayer" not in text and "PlayerController" not in text:
                    engine_name = text
                    break
    # Always prefer PlayerArray/engine name for XP+SDU name paths.
    apply_name = engine_name or name_sub

    bits: list[str] = []
    label = apply_name or (f"index {pidx}" if pidx is not None else "local")
    opts = dict(options or {})

    def _want(key: str) -> bool:
        if key not in opts:
            return True
        val = opts.get(key)
        if isinstance(val, bool):
            return val
        return str(val or "").strip().lower() in ("1", "true", "yes", "on")

    cash_ok = erid_ok = True
    if _want("max_cash"):
        cash_ok, cash_msg = _do_set_currency_absolute(
            "cash",
            _MAX_WALLET_AMOUNT,
            apply_name,
            pc=pc,
            player_index=pidx,
        )
        bits.append(f"cash={'OK' if cash_ok else 'FAIL'}: {cash_msg[:100]}")
    else:
        bits.append("cash=skipped")
    if _want("max_eridium"):
        erid_ok, erid_msg = _do_set_currency_absolute(
            "eridium",
            _MAX_WALLET_AMOUNT,
            apply_name,
            pc=pc,
            player_index=pidx,
        )
        bits.append(f"eridium={'OK' if erid_ok else 'FAIL'}: {erid_msg[:100]}")
    else:
        bits.append("eridium=skipped")

    if _want("max_sdu"):
        try:
            if _set_max_sdu_points_on_pc(pc):
                bits.append("SDU max (pc)")
            elif apply_name:
                _do_boost_maxsdu(["name", apply_name])
                bits.append("SDU max (name)")
            else:
                bits.append("SDU FAIL: no pc/name path")
        except Exception as ex:  # noqa: BLE001
            bits.append(f"SDU FAIL: {ex}")
    else:
        bits.append("SDU=skipped")

    if _want("max_vault_cards"):
        try:
            from .vault_card_boost import max_all_vault_cards_for_pc  # noqa: PLC0415

            vc_ok, vc_msg = max_all_vault_cards_for_pc(pc, log=_log)
            bits.append(f"vault cards={'OK' if vc_ok else 'partial'}: {vc_msg[:120]}")
        except Exception as ex:  # noqa: BLE001
            for vc_kind in ("vaultcard1", "vaultcard2", "vaultcard3", "vaultcard4"):
                _do_set_currency_absolute(
                    vc_kind,
                    _MAX_WALLET_AMOUNT,
                    apply_name,
                    pc=pc,
                    player_index=pidx,
                )
            if apply_name:
                for vc_xp in ("vaultcard_xp_1", "vaultcard_xp_2", "vaultcard_xp_3", "vaultcard_xp_4"):
                    _do_give_experience(vc_xp, 9_999, apply_name)
            bits.append(f"vault fallback ({type(ex).__name__})")
    else:
        bits.append("vault=skipped")

    # Apply player/spec LAST — vault OnRep / XP writes must not leave character short of cap.
    ok_p = False
    ok_s = False
    if ps is not None:
        if _want("max_player_level"):
            ok_p = _ensure_experience_level_via_bp(ps, 0, _MAX_PLAYER_LEVEL_ENGINE)
            got_p = _get_experience_level_via_bp(ps, 0)
            bits.append(f"player BP={'OK' if ok_p else 'FAIL'} (now={got_p})")
            if (not ok_p) and apply_name:
                try:
                    _do_give_experience("player", _MAX_PLAYER_LEVEL_ENGINE, apply_name)
                    ok_p = (_get_experience_level_via_bp(ps, 0) or 0) >= _MAX_PLAYER_LEVEL_ENGINE
                    bits.append(f"player level {_MAX_PLAYER_LEVEL_ENGINE} (name fallback)")
                except Exception as ex:  # noqa: BLE001
                    bits.append(f"player level FAIL: {ex}")
        else:
            ok_p = True
            bits.append("player=skipped")
        if _want("max_spec_level"):
            ok_s = _ensure_experience_level_via_bp(ps, 1, 701)
            got_s = _get_experience_level_via_bp(ps, 1)
            bits.append(f"spec BP={'OK' if ok_s else 'FAIL'} (now={got_s})")
            if (not ok_s) and apply_name:
                try:
                    _do_give_experience("specialization", 701, apply_name)
                    ok_s = (_get_experience_level_via_bp(ps, 1) or 0) >= 701
                    bits.append("spec 701 (name fallback)")
                except Exception as ex:  # noqa: BLE001
                    bits.append(f"spec FAIL: {ex}")
        else:
            ok_s = True
            bits.append("spec=skipped")
    elif apply_name:
        if _want("max_player_level"):
            try:
                _do_give_experience("player", _MAX_PLAYER_LEVEL_ENGINE, apply_name)
                ok_p = True
                bits.append(f"player level {_MAX_PLAYER_LEVEL_ENGINE} (name)")
            except Exception as ex:  # noqa: BLE001
                bits.append(f"player level FAIL: {ex}")
        else:
            ok_p = True
            bits.append("player=skipped")
        if _want("max_spec_level"):
            try:
                _do_give_experience("specialization", 701, apply_name)
                ok_s = True
                bits.append("spec 701 (name)")
            except Exception as ex:  # noqa: BLE001
                bits.append(f"spec FAIL: {ex}")
        else:
            ok_s = True
            bits.append("spec=skipped")
    else:
        bits.append("player/spec skipped (no PS/name)")

    ok = bool(cash_ok and erid_ok and ok_p and ok_s)
    summary = f"Squ1ggs max_all ({label}): " + "; ".join(bits[:14])
    _log(summary)
    return ok, summary


@command(
    "givecurrency",
    description=(
        "Listen host: GbxCurrencyFunctionLibrary.GiveCurrency for one player. "
        "Usage: givecurrency <kind> <amount> name <substring>  — kinds: cash, eridium, "
        "vaultcard1, vaultcard2, vaultcard3, vaultcard4. "
        "Verify in-game: client wallet updates; ambiguous name → gbc_players."
    ),
)
def _cmd_givecurrency(args: argparse.Namespace) -> None:
    parts = [str(p) for p in (getattr(args, "parts", None) or [])]
    head, name_sub = _parse_name_suffix(parts)
    if len(head) < 2:
        _log_err("Usage: givecurrency <kind> <amount> name <substring>")
        return
    kind_raw = head[0]
    amt = _safe_int(head[1])
    if amt is None:
        _log_err("givecurrency: expected integer amount after kind, got %r", head[1])
        return
    _do_give_currency(kind_raw, amt, name_sub)


_cmd_givecurrency.add_argument(
    "parts",
    nargs="+",
    help="kind amount name substring (multi-word name after name)",
)


@command(
    "giveexperience",
    description=(
        "Listen host: set one player's experience level via OakPlayerState.BP_SetExperienceLevel "
        "using a GbxExperienceDef FGbxDefPtr. Slots: 0 player, 1 specialization, "
        "2 vault 01, 3 vault 02, 4 vault 03. Character uses token 'Character'; other tracks reuse "
        "their ExperienceState token when available. Usage: giveexperience <track> <level> name <substring>."
    ),
)
def _cmd_giveexperience(args: argparse.Namespace) -> None:
    parts = [str(p) for p in (getattr(args, "parts", None) or [])]
    head, name_sub = _parse_name_suffix(parts)
    if len(head) < 2:
        _log_err("Usage: giveexperience <track> <level> name <substring>")
        return
    track_raw = head[0]
    lvl = _safe_int(head[1])
    if lvl is None:
        _log_err("giveexperience: expected integer level, got %r", head[1])
        return
    _do_give_experience(track_raw, lvl, name_sub)


_cmd_giveexperience.add_argument(
    "parts",
    nargs="+",
    help="track level name substring",
)
