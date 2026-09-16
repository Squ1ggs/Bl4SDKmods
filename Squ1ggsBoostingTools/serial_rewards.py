"""Loyalty reward grant + serial injection for Squ1ggs Boosting Tools."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, List, Optional, Tuple

import unrealsdk
from mods_base import command, get_pc
from unrealsdk import find_all, find_class, find_object, make_struct

from .party_helpers import (
    _gbc_find_pc_for_player_state,
    _gbc_resolve_player_index_for_name_substring,
    _gbc_run_session_timer_from_give_serial,
    _gbc_session_world_and_gamestate,
)
from unrealsdk.unreal import FGbxDefPtr, UObject
from unrealsdk import logging

# Default reward def (edit here). Same id as Nexus rewards'ChallengeReward_Loyalty_Jakobs'.
DEFAULT_REWARD_DEF_NAME = "ChallengeReward_Loyalty_Jakobs"

# Generic manufacturer loyalty packages (Nexus ids). Order matches in-game "Loyalty Reward" list;
# Ripper uses ChallengeReward_Loyalty_Borg in Nexus data. Each successful Give_Serial advances to the next.
LOYALTY_REWARD_DEF_NAMES: Tuple[str, ...] = (
    "ChallengeReward_Loyalty_Daedalus",
    "ChallengeReward_Loyalty_Jakobs",
    "ChallengeReward_Loyalty_Maliwan",
    "ChallengeReward_Loyalty_Order",
    "ChallengeReward_Loyalty_Borg",  # Ripper (UI)
    "ChallengeReward_Loyalty_Tediore",
    "ChallengeReward_Loyalty_Torgue",
    "ChallengeReward_Loyalty_Vladof",
)

# In-memory only; resets when the game restarts.
_loyalty_rotation_index: int = 0

# ScriptStruct paths for FGbxDefPtr.ref (same as bl4_reward_generator when find_object cannot resolve by name).
REWARDS_DEF_SCRIPT_PATHS = (
    "/Script/GbxGame.GbxRewardsDef",
    "/Script/OakGame.GbxRewardsDef",
)

_PATCH_RETRY_ATTEMPTS = 8
_PATCH_RETRY_DELAY_SEC = 0.08
_CHUNK_DELIVERY_MAX_RETRIES = 16
_TICK_PATCH_MAX_ATTEMPTS = 180
_TICK_PATCH_LOG_EVERY = 30
# Keep reward SerialNumbers payloads under the observed client-delivery failure boundary.
# Large packs (~500) AV'd with 25/pkg + short gaps (same class as GZO package 18/23 crash).
_MAX_SERIAL_DELIVERY_CHARS = 32000
_SERIAL_DELIVERY_SAFE_CHARS = 24000
_SERIAL_DELIVERY_PER_SERIAL_OVERHEAD_CHARS = 16
_SERIAL_DELIVERY_MAX_ITEMS_PER_PACKAGE = 12
# Gap between targeted packages on the tick hook (no game-thread sleeps).
# create_and_override already writes SerialNumbers — no AllPlayers/patch/open pipeline.
_SERIAL_DELIVERY_PRE_OPEN_DELAY_SEC = 0.0
# Base gap; _delivery_chunk_gap raises this for 200+/400+/500+ dumps.
_SERIAL_DELIVERY_POST_OPEN_DELAY_SEC = 0.28
_SERIAL_DELIVERY_PATCH_MAX_ATTEMPTS = 1
_SERIAL_DELIVERY_PATCH_LOG_EVERY = 30
# Defer open-rewards until the whole send finishes once this many serials queue.
_SERIAL_DELIVERY_DEFER_OPEN_SERIALS = 200
# Extra cool-down after every N packages on huge sends.
_SERIAL_DELIVERY_COOLDOWN_EVERY = 6
_SERIAL_DELIVERY_COOLDOWN_SEC = 2.2
# Level rewrite of 500 @U codes on the click frame AVs — defer past this size.
_SERIAL_DELIVERY_DEFER_LEVEL_SERIALS = 80
# Exact Pearl fallbacks create and patch a reward package synchronously, but the
# package is not ready for Server_OpenPackage in that same game frame.  Opening
# immediately can return without an exception while doing nothing.  Claims are
# therefore paced on the existing UMG tick and verified against the backpack.
_EXACT_PACKAGE_OPEN_DELAY_SEC = 0.25
_EXACT_PACKAGE_INVENTORY_VERIFY_DELAY_SEC = 0.20
_EXACT_PACKAGE_INVENTORY_VERIFY_TIMEOUT_SEC = 2.50
_pending_exact_package_claims: List[dict[str, Any]] = []
# Opening many Server_OpenPackage calls in one frame freezes / crashes BL4
# (ACCESS_VIOLATION via pyunrealsdk) and can blank backpack visibility in MP.
# Auto-open: one mail package per tick, newest-first (re-query live index), 3–5s gap.
_REWARD_OPEN_FIRST_DELAY_SEC = 2.0
_REWARD_OPEN_GAP_SEC = 4.0
_REWARD_OPEN_GAP_LARGE_SEC = 5.0
_REWARD_OPEN_LARGE_QUEUE_PACKAGES = 12
_REWARD_OPEN_RESUME_DELAY_SEC = 3.0
_pending_reward_open_jobs: List[dict[str, Any]] = []
_reward_open_paused = False
# After Complete ALL non-UVHM, Reward Center often has hundreds of packages.
# Block "Open pending rewards (everyone)" until the user force-confirms.
_open_all_blocked_after_challenge_bulk: bool = False
_OPEN_ALL_CHALLENGE_WARN_PACKAGES: int = 40
# GiveReward + SerialNumbers patch during a lobby join is a common host AV.
_serial_party_count_seen: int = -1
_serial_join_quiet_until: float = 0.0
_SERIAL_JOIN_QUIET_SEC: float = 12.0


def _live_party_count_for_serial() -> int:
    try:
        _world, gs = _gbc_session_world_and_gamestate()
        pa = getattr(gs, "PlayerArray", None) if gs is not None else None
        if pa is None:
            return 0
        return int(len(pa))
    except Exception:
        return 0


def _note_serial_party_join_quiet() -> bool:
    """Detect party size changes and arm a quiet window. Returns True while quiet."""
    global _serial_party_count_seen, _serial_join_quiet_until
    now = time.monotonic()
    count = _live_party_count_for_serial()
    prev = int(_serial_party_count_seen)
    if prev < 0:
        _serial_party_count_seen = count
    elif count != prev:
        _serial_party_count_seen = count
        until = now + float(_SERIAL_JOIN_QUIET_SEC)
        if until > float(_serial_join_quiet_until or 0.0):
            _serial_join_quiet_until = until
            _log_info(
                f"Lobby party {prev}->{count}: pausing serial mail / reward opens "
                f"for {_SERIAL_JOIN_QUIET_SEC:.0f}s (join churn)."
            )
            _set_serial_delivery_status(
                f"Lobby join/leave detected ({prev}→{count}) — pausing serial mail "
                f"~{_SERIAL_JOIN_QUIET_SEC:.0f}s so BL4 can settle.",
                hold_sec=float(_SERIAL_JOIN_QUIET_SEC) + 4.0,
                log=True,
            )
    try:
        from .loot_shapes import _in_join_quiet

        if _in_join_quiet(now):
            return True
    except Exception:
        pass
    return now < float(_serial_join_quiet_until or 0.0)


def _serial_mail_join_quiet() -> bool:
    """True while a lobby join/leave makes GiveReward / package opens unsafe."""
    return bool(_note_serial_party_join_quiet())


def _serial_delivery_sync_preferred() -> bool:
    """Opt into the old blocking hybrid path (time.sleep on the game thread). Default: off."""
    raw = os.environ.get("SQU1GGS_SERIAL_SYNC_DELIVERY", "").strip().lower()
    return raw in ("1", "true", "yes", "on")

def _clamp_serial_delivery_delay(value: float) -> float:
    try:
        return max(0.0, min(5.0, float(value)))
    except Exception:
        return 0.0


def set_serial_delivery_timing(pre_open_delay: float | None = None, post_open_delay: float | None = None) -> tuple[float, float]:
    """Set automatic chunk-delivery delays. Values are clamped to 0..5 seconds."""
    global _SERIAL_DELIVERY_PRE_OPEN_DELAY_SEC, _SERIAL_DELIVERY_POST_OPEN_DELAY_SEC
    if pre_open_delay is not None:
        _SERIAL_DELIVERY_PRE_OPEN_DELAY_SEC = _clamp_serial_delivery_delay(pre_open_delay)
    if post_open_delay is not None:
        _SERIAL_DELIVERY_POST_OPEN_DELAY_SEC = _clamp_serial_delivery_delay(post_open_delay)
    return (_SERIAL_DELIVERY_PRE_OPEN_DELAY_SEC, _SERIAL_DELIVERY_POST_OPEN_DELAY_SEC)


def serial_delivery_timing() -> tuple[float, float]:
    """Return current automatic chunk-delivery delays: post-delivery, post-open."""
    return (_SERIAL_DELIVERY_PRE_OPEN_DELAY_SEC, _SERIAL_DELIVERY_POST_OPEN_DELAY_SEC)


# Same contract as Legit Builder SERIAL_API_URL (POST JSON {"deserialized": "…"} → {"serial_b85": "…"}).
_DEFAULT_GENIE_SERIALIZE_API_URL = "https://save-editor.be/nicnl/api.php"
_BASE85_TOKEN_RE = re.compile(r"^@[!-~]+$")
# BL4-style deserialized human line: leading root tuple then first pipe (e.g. "7, 0, 1, 60| …").
_DESERIALIZED_HUMAN_HEAD_RE = re.compile(r"^\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\|")


def _genie_serialize_api_url() -> str:
    raw = os.environ.get("GENIE_SERIALIZE_API_URL", "").strip()
    return raw or _DEFAULT_GENIE_SERIALIZE_API_URL


def _genie_serialize_enabled() -> bool:
    raw = os.environ.get("GENIE_SERIALIZE_ENABLED", "").strip().lower()
    if not raw:
        return True
    return raw not in ("0", "false", "no", "off")


def _looks_like_base85(s: str) -> bool:
    t = (s or "").strip()
    return len(t) >= 10 and bool(_BASE85_TOKEN_RE.match(t))


def _looks_like_deserialized_human(s: str) -> bool:
    t = (s or "").strip()
    if not t or _looks_like_base85(t):
        return False
    if "|" not in t:
        return False
    return bool(_DESERIALIZED_HUMAN_HEAD_RE.match(t))


def _normalize_serial_b85(b85: str) -> str:
    b = b85.strip()
    if not b:
        return b
    return b if b.startswith("@") else f"@{b}"


def _base85_serial_starts(text: str) -> list[int]:
    """@Ug starts a serial at start, after whitespace, or after YAML/JSON punctuation.

    Mid-payload ``@Ug`` after Base85 letters must not split. STBX save YAML uses
    ``serial: '@Ug…'`` so a quote/colon before ``@Ug`` is a valid boundary.
    """
    return [
        m.start()
        for m in re.finditer(r"(?:^|(?<=[\s'\"`:=(\[{,]))@Ug", text, re.IGNORECASE)
    ]


def _extract_yaml_serial_fields(raw: str) -> list[str]:
    """Pull ``serial: '@U…'`` / ``serial: \"@U…\"`` / ``serial: @U…`` from save YAML."""
    found: list[str] = []
    seen: set[str] = set()

    def _add(serial: str) -> None:
        s = str(serial or "").strip()
        if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
            s = s[1:-1].strip()
        if not s.startswith("@U") or len(s) < 12 or s in seen:
            return
        seen.add(s)
        found.append(s)

    text = str(raw or "")
    for pattern in (
        r"\bserial\s*:\s*'([^']+)'",
        r'\bserial\s*:\s*"([^"]+)"',
        r"\bserial\s*:\s*(@U\S+)",
    ):
        for m in re.finditer(pattern, text, re.IGNORECASE):
            _add(m.group(1))
    return found


def _is_single_pasted_base85(text: str) -> bool:
    """One contiguous @U line — never split on `` ` `` / punctuation inside Base85."""
    t = str(text or "").strip()
    if not t.startswith("@U"):
        return False
    if "\n" in t or "\r" in t:
        return False
    return len(_base85_serial_starts(t)) <= 1


def _join_wrapped_serial_lines(raw: str) -> list[str]:
    """Rejoin paste lines broken mid-serial (e.g. backtick → newline in chat exports)."""
    out: list[str] = []
    buf = ""
    for line in str(raw or "").replace("\r", "\n").split("\n"):
        piece = line.strip()
        if not piece:
            continue
        if not buf:
            buf = piece
            continue
        if piece.startswith("@U") or looks_like_serial_file_path(piece):
            out.append(buf)
            buf = piece
        elif buf.startswith("@U"):
            buf += piece
        else:
            out.append(buf)
            buf = piece
    if buf:
        out.append(buf)
    return out


def looks_like_serial_file_path(raw: str) -> bool:
    s = str(raw or "").strip().strip("\"'")
    if not s:
        return False
    if not re.search(r"\.(txt|docx|csv|md|json|log|ya?ml)$", s, re.I):
        return False
    return bool(re.match(r"^[A-Za-z]:[\\/]", s) or s.startswith("\\\\") or re.search(r"[\\/]", s))


def _split_base85_blob(text: str) -> list[str]:
    t = text.strip()
    if not t:
        return []
    if _is_single_pasted_base85(t):
        return [t]
    starts = _base85_serial_starts(t)
    if not starts:
        return [t] if t.startswith("@U") else []

    def _clean(part: str) -> str:
        # Strip closing quotes / YAML-JSON punctuation only from the tail.
        return part.strip().rstrip("'\"`,}])")

    if len(starts) == 1:
        part = _clean(t[starts[0] :])
        return [part] if part else []
    starts.append(len(t))
    out: list[str] = []
    for i in range(len(starts) - 1):
        part = _clean(t[starts[i] : starts[i + 1]])
        if part:
            out.append(part)
    return out


def _expand_serial_token(p: str) -> List[str]:
    """One token -> one or more serial strings without corrupting Base85.

    BL4 Base85 serials can contain punctuation and embedded @Uw fragments, so do
    not split on every @U prefix — only on @Ug (start of a new serial).
    """
    t = p.strip()
    if not t:
        return []
    if _looks_like_deserialized_human(t):
        return [t]
    if _is_single_pasted_base85(t):
        return [t]
    parts = _split_base85_blob(t)
    return parts if parts else [t]


def _serialize_deserialized_to_b85(deserialized: str) -> str:
    url = _genie_serialize_api_url()
    payload = json.dumps({"deserialized": deserialized}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        # HTTPError subclasses URLError; handle before URLError.
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} from serialize API: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Serialize API network error: {e}") from e

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Serialize API returned invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError("Serialize API returned non-object JSON")
    err = data.get("error")
    if err:
        raise RuntimeError(str(err))
    b85 = data.get("serial_b85")
    if not isinstance(b85, str) or not b85.strip():
        raise RuntimeError("Serialize API response missing serial_b85")
    return _normalize_serial_b85(b85)


def _resolve_give_serial_strings(raw_serials: List[str]) -> Optional[List[str]]:
    """Convert deserialized human lines to Base85 via HTTP; abort whole command on first failure."""
    out: List[str] = []
    for idx, s in enumerate(raw_serials):
        t = s.strip()
        if not t:
            continue
        if _looks_like_base85(t):
            out.append(t)
            continue
        if _looks_like_deserialized_human(t):
            if not _genie_serialize_enabled():
                _log_error(
                    "Give_Serial: deserialized human serial detected but GENIE_SERIALIZE_ENABLED is off "
                    "(unset or set to 1/true to allow HTTP serialize)."
                )
                return None
            try:
                b85 = _serialize_deserialized_to_b85(t)
            except Exception as e:
                _log_error(f"Give_Serial: serialize failed for serial #{idx + 1}: {e}")
                return None
            out.append(b85)
            continue
        out.append(t)
    return out


def _log_info(message: str) -> None:
    logging.info(f"[Squ1ggs Boosting Tools | Serial] {message}")


def _log_warning(message: str) -> None:
    logging.warning(f"[Squ1ggs Boosting Tools | Serial] {message}")


def _log_error(message: str) -> None:
    logging.error(f"[Squ1ggs Boosting Tools | Serial] {message}")


def _normalize_nexus_reward_def_arg(s: str) -> str:
    t = (s or "").strip()
    low = t.lower()
    if low.startswith("rewards'") and t.endswith("'") and len(t) > len("rewards'x'"):
        return t[len("rewards'") : -1].strip()
    if low.startswith('rewards"') and t.endswith('"') and len(t) > len('rewards"x"'):
        return t[len('rewards"') : -1].strip()
    return t


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(float(text))
        except Exception:
            return None
    return None


def _is_fgbx_def_ptr(o: Any) -> bool:
    if o is None:
        return False
    try:
        from unrealsdk.unreal import FGbxDefPtr as _FG

        return isinstance(o, _FG)
    except Exception:
        return type(o).__name__ == "FGbxDefPtr"


def _coerce_make_gbx_reward_ref_result(o: Any, depth: int = 0) -> Optional[Any]:
    if o is None or depth > 4:
        return None
    if _is_fgbx_def_ptr(o):
        return o
    for attr in (
        "RewardsDef",
        "RewardDef",
        "Reward",
        "Def",
        "DefPtr",
        "GbxDefPtr",
        "value",
        "Value",
    ):
        try:
            v = getattr(o, attr, None)
        except Exception:
            v = None
        if v is None:
            continue
        c = _coerce_make_gbx_reward_ref_result(v, depth + 1)
        if c is not None:
            return c
    if type(o).__name__ == "WrappedStruct" or "Struct" in type(o).__name__:
        try:
            for name in dir(o):
                if name.startswith("_"):
                    continue
                try:
                    v = getattr(o, name, None)
                except Exception:
                    continue
                if v is None or callable(v):
                    continue
                if _is_fgbx_def_ptr(v):
                    return v
                c = _coerce_make_gbx_reward_ref_result(v, depth + 1)
                if c is not None:
                    return c
        except Exception:
            pass
    return None


def _try_make_gbx_reward_ref(lib: Any, pc: Any, mgr: Optional[Any], path: str) -> Optional[Any]:
    mk = getattr(lib, "MakeGbxRewardRef", None)
    if not callable(mk):
        return None
    world = getattr(pc, "World", None)
    owner = None
    for attr in ("GbxRewardsOwner", "RewardsOwner", "RewardOwner"):
        try:
            owner = getattr(pc, attr, None)
            if owner is not None:
                break
        except Exception:
            pass
    tail = path.split("/")[-1]
    seen_id: set = set()
    uniq_ids: List[str] = []
    for s in (path, path.strip(), "rewards'" + tail + "'", "rewards'" + path + "'"):
        if s and s not in seen_id:
            seen_id.add(s)
            uniq_ids.append(s)

    def _try_mk_pair(a: Any, b: Any) -> Optional[Any]:
        try:
            r = mk(a, b)
        except TypeError:
            return None
        except Exception:
            return None
        for candidate in (r, b):
            c = _coerce_make_gbx_reward_ref_result(candidate)
            if c is not None:
                return c
        return None

    struct_names = (
        "RewardRef",
        "GbxRewardRef",
        "FGbxRewardRef",
        "GbxRewardsRewardRef",
        "OakRewardRef",
    )
    for rid in uniq_ids:
        for sn in struct_names:
            try:
                blank = make_struct(sn)
            except Exception:
                continue
            for _label, a, b in (
                ("rid+outStruct", rid, blank),
                ("outStruct+rid", blank, rid),
            ):
                c = _try_mk_pair(a, b)
                if c is not None:
                    return c

        for ctx in (
            pc,
            mgr,
            world,
            owner,
            getattr(pc, "PlayerState", None),
            getattr(pc, "GameInstance", None),
        ):
            if ctx is None:
                continue
            for a, b in ((rid, ctx), (ctx, rid)):
                c = _try_mk_pair(a, b)
                if c is not None:
                    return c

    return None


def _get_gbx_rewards_blueprint_library() -> Optional[Any]:
    try:
        cls = find_class("GbxRewards_BlueprintFunctions")
        if cls is not None:
            cdo = getattr(cls, "ClassDefaultObject", None)
            if cdo is not None:
                return cdo
    except Exception:
        pass
    try:
        objs = find_all("GbxRewards_BlueprintFunctions", False) or []
        if objs:
            return objs[-1]
    except Exception:
        pass
    return None


def _find_rewards_manager_on_pc(pc: Any) -> Tuple[Optional[Any], Optional[str]]:
    for name in (
        "GbxRewardsManager",
        "RewardsManager",
        "RewardManager",
        "MyRewardsManager",
    ):
        try:
            m = getattr(pc, name, None)
            if m is not None:
                return (m, name)
        except Exception:
            pass
    try:
        for name in dir(pc):
            if name.startswith("_") or "reward" not in name.lower():
                continue
            try:
                m = getattr(pc, name, None)
            except Exception:
                continue
            if m is None or callable(m):
                continue
            cls = getattr(m, "Class", None)
            cname = str(getattr(cls, "Name", "") or "")
            if "Reward" in cname:
                return (m, name)
    except Exception:
        pass
    return (None, None)



def _pc_for_player_index(player_index: int) -> Optional[Any]:
    world, gs = _gbc_session_world_and_gamestate()
    if world is None or gs is None:
        return None
    pa = getattr(gs, "PlayerArray", None)
    if pa is None:
        return None
    try:
        if player_index < 0 or player_index >= len(pa):
            return None
        ps = pa[player_index]
    except Exception:
        return None
    if ps is None:
        return None
    return _gbc_find_pc_for_player_state(ps, world)


def _manager_for_player_index(player_index: int) -> Optional[Any]:
    pc = _pc_for_player_index(player_index)
    if pc is None:
        return None
    mgr, _ = _find_rewards_manager_on_pc(pc)
    return mgr


def _package_count(mgr: Any) -> int:
    try:
        pkgs = getattr(mgr, "packages", None)
        return len(pkgs) if pkgs is not None else 0
    except Exception:
        return 0


def _snapshot_player_package_counts(player_indices: List[int]) -> dict[int, int]:
    out: dict[int, int] = {}
    for idx in player_indices:
        mgr = _manager_for_player_index(idx)
        if mgr is not None:
            out[int(idx)] = _package_count(mgr)
    return out

def _find_rewards_def_struct() -> Optional[Any]:
    """Resolve the GbxRewardsDef ScriptStruct for FGbxDefPtr.ref (bl4_reward_generator path)."""
    for class_name in ("ScriptStruct", "Object"):
        for object_path in REWARDS_DEF_SCRIPT_PATHS:
            try:
                resolved = find_object(class_name, object_path)
            except Exception:
                resolved = None
            if isinstance(resolved, UObject):
                return resolved
    try:
        for candidate in find_all("ScriptStruct", False) or []:
            if getattr(candidate, "Name", None) == "GbxRewardsDef":
                return candidate
    except Exception:
        pass
    return None


def _assign_fgbx_def_ptr_fields(ptr: Any, name: str, ref: Any) -> bool:
    """
    pyunrealsdk builds differ: some expose FGbxDefPtr as .name/.ref, others as _experimental_* only.
    Try both so the same mod works across SDK drops (e.g. Apple vs SDK DLL sets).
    """
    for name_attr, ref_attr in (("name", "ref"), ("_experimental_name", "_experimental_ref")):
        try:
            setattr(ptr, name_attr, name)
            setattr(ptr, ref_attr, ref)
            return True
        except Exception:
            continue
    return False


def _make_reward_def_ptr(reward_name: str) -> Optional[FGbxDefPtr]:
    """Build FGbxDefPtr from reward id (pyunrealsdk v1.10+: FGbxDefPtr(name, type=...))."""
    try:
        from gbx_def_ptr_helpers import build_reward_def_invoke_candidates  # noqa: PLC0415

        for _tag, ptr in build_reward_def_invoke_candidates(reward_name):
            if isinstance(ptr, FGbxDefPtr):
                return ptr
    except ImportError:
        pass
    tail = (reward_name or "").strip().split("/")[-1]
    if not tail:
        return None
    try:
        return FGbxDefPtr(tail, type="GbxRewardsDef")
    except Exception:
        pass
    try:
        return FGbxDefPtr(tail)
    except Exception:
        return None


def _resolve_def_for_give(pc: Any, lib: Any, def_path: str) -> Optional[Any]:
    path = _normalize_nexus_reward_def_arg(def_path)
    if not path:
        return None
    mgr_for_ref, _ = _find_rewards_manager_on_pc(pc)
    resolved = _try_make_gbx_reward_ref(lib, pc, mgr_for_ref, path)
    if resolved is None:
        resolved = _make_reward_def_ptr(path)
        if resolved is not None:
            _log_info(f"Resolved reward def via FGbxDefPtr(name={path!r}, GbxRewardsDef struct).")
    return resolved


def _give_reward_def(def_path: str, all_players: bool, *, target_pc: Any = None) -> bool:
    if _serial_mail_join_quiet():
        _log_warning("GiveReward skipped: lobby join/leave quiet window.")
        return False
    pc = target_pc if target_pc is not None else get_pc()
    if pc is None:
        _log_error("No player controller.")
        return False
    lib = _get_gbx_rewards_blueprint_library()
    if lib is None:
        _log_error("GbxRewards_BlueprintFunctions not found.")
        return False

    def_u = _resolve_def_for_give(pc, lib, def_path)
    if def_u is None:
        _log_error(f"Could not resolve reward def '{def_path}'.")
        return False

    mgr, mgr_attr = _find_rewards_manager_on_pc(pc)
    world = getattr(pc, "World", None)

    if all_players:
        ptr_all: List[Any] = []
        if isinstance(def_u, FGbxDefPtr):
            ptr_all.append(def_u)
        else:
            try:
                ptr_all.append(FGbxDefPtr(def_u))
            except Exception as e:
                _log_warning(f"FGbxDefPtr(def) failed ({e}); will try raw def.")
            ptr_all.append(def_u)

        def _all_players_arg_variants(ptr: Any) -> List[Tuple[str, Tuple[Any, ...]]]:
            vs: List[Tuple[str, Tuple[Any, ...]]] = [
                ("ptr", (ptr,)),
                ("ptr_pc", (ptr, pc)),
                ("pc_ptr", (pc, ptr)),
            ]
            if mgr is not None:
                vs += [
                    ("ptr_mgr", (ptr, mgr)),
                    ("mgr_ptr", (mgr, ptr)),
                ]
            if world is not None:
                vs += [
                    ("ptr_world", (ptr, world)),
                    ("world_ptr", (world, ptr)),
                ]
            return vs

        give_all = getattr(lib, "GiveRewardAllPlayers", None)
        if not callable(give_all):
            _log_error("GiveRewardAllPlayers not callable.")
            return False
        for ptr in ptr_all:
            for order_name, args in _all_players_arg_variants(ptr):
                try:
                    give_all(*args)
                    _log_info(f"GiveRewardAllPlayers OK ({order_name}).")
                    return True
                except TypeError as e:
                    _log_warning(f"GiveRewardAllPlayers {order_name} TypeError: {e}")
                except Exception as e:
                    _log_warning(f"GiveRewardAllPlayers {order_name}: {e}")
                    return False
        _log_error("GiveRewardAllPlayers: all variants failed.")
        return False

    give_fn = getattr(lib, "GiveReward", None)
    if not callable(give_fn):
        _log_error("GiveReward not callable on library.")
        return False

    contexts: List[Any] = [pc]
    if mgr is not None:
        contexts.append(mgr)

    ptr_candidates: List[Any] = []
    if isinstance(def_u, FGbxDefPtr):
        ptr_candidates.append(def_u)
    else:
        try:
            ptr_candidates.append(FGbxDefPtr(def_u))
        except Exception as e:
            _log_warning(f"FGbxDefPtr(def) failed ({e}); will try raw def UObject.")
        ptr_candidates.append(def_u)

    for ptr in ptr_candidates:
        for ctx in contexts:
            ctx_label = "PC" if ctx is pc else ("PC.%s" % (mgr_attr or "manager"))
            for order_name, args in (
                ("RewardDef_then_OwnerContext", (ptr, ctx)),
                ("swapped_OwnerContext_first", (ctx, ptr)),
            ):
                try:
                    give_fn(*args)
                    _log_info(f"GiveReward OK: {order_name} {ctx_label}")
                    return True
                except TypeError as e:
                    _log_warning(f"GiveReward {order_name} {ctx_label} TypeError: {e}")
                except Exception as e:
                    _log_warning(f"GiveReward {order_name} {ctx_label}: {e}")
                    return False
    _log_error("GiveReward: all argument orderings failed.")
    return False


def _unique_gbx_rewards_managers() -> List[Any]:
    try:
        raw = list(unrealsdk.find_all("GbxRewardsManager", False) or [])
    except Exception as e:
        _log_warning(f"find_all GbxRewardsManager: {e}")
        return []
    seen: set[int] = set()
    out: List[Any] = []
    for obj in raw:
        if obj is None:
            continue
        oid = id(obj)
        if oid in seen:
            continue
        seen.add(oid)
        out.append(obj)
    return out




def _live_gbx_rewards_managers() -> List[Any]:
    """Only real in-world reward managers. Never return the class default object."""
    out: List[Any] = []
    seen: set[int] = set()
    for rm in _unique_gbx_rewards_managers():
        text = str(rm)
        if "Default__" in text:
            continue
        outer = getattr(rm, "Outer", None)
        if "OakPlayerController" not in str(outer):
            continue
        oid = id(rm)
        if oid in seen:
            continue
        seen.add(oid)
        out.append(rm)
    return out


def _open_all_live_reward_packages() -> int:
    """Legacy entry — never bulk-open; same paced queue as Open pending rewards."""
    return open_all_party_reward_packages()


def open_all_party_reward_packages() -> int:
    """Queue every pending reward package for paced opening (never one-frame bulk open)."""
    packages, managers = _queue_open_all_pending_packages()
    if packages > 0:
        _log_info(
            f"Queued paced open for {packages} pending package(s) on {managers} manager(s)."
        )
        return managers
    _log_warning("SQBT found no pending reward packages to queue for opening.")
    return 0


def _open_manager_all_packages(mgr: Any) -> bool:
    """Never call Server_OpenAllPackages (MP crash / backpack blank). Queue paced opens."""
    if mgr is None:
        return False
    try:
        n = int(_package_count(mgr) or 0)
    except Exception:
        n = 0
    if n <= 0:
        return False
    total, _note = _queue_reward_open_jobs(
        [(None, 0, 0, n)],
        label="legacy open-all",
    )
    return total > 0


def _package_indices_since(mgr: Any, before_count: int) -> List[int]:
    """Package indices created at/after ``before_count``, newest first (diagnostics only)."""
    if mgr is None:
        return []
    pkgs = getattr(mgr, "packages", None)
    try:
        n = len(pkgs) if pkgs is not None else 0
    except Exception:
        n = 0
    start = max(0, int(before_count))
    if start >= n:
        return []
    return list(range(n - 1, start - 1, -1))


def _open_manager_package_index(mgr: Any, package_index: int) -> bool:
    open_one = getattr(mgr, "Server_OpenPackage", None)
    if not callable(open_one):
        return False
    try:
        open_one(int(package_index))
        return True
    except Exception as exc:
        _log_warning(f"Server_OpenPackage({package_index}) failed on manager {mgr}: {exc!r}")
        return False


def block_open_all_after_challenge_bulk(*, reason: str = "Complete ALL non-UVHM") -> None:
    """Flip the guard used by Open pending rewards after mass challenge completion."""
    global _open_all_blocked_after_challenge_bulk
    _open_all_blocked_after_challenge_bulk = True
    cancel_pending_reward_opens(reason, log=True)


def clear_open_all_challenge_block() -> None:
    global _open_all_blocked_after_challenge_bulk
    _open_all_blocked_after_challenge_bulk = False


def open_all_blocked_after_challenge_bulk() -> bool:
    return bool(_open_all_blocked_after_challenge_bulk)


def cancel_pending_reward_opens(reason: str = "session teardown", *, log: bool = True) -> None:
    global _pending_reward_open_jobs, _reward_open_paused
    if not _pending_reward_open_jobs:
        _reward_open_paused = False
        return
    n = sum(
        max(0, len(list(job.get("indices") or [])) - int(job.get("cursor") or 0))
        for job in _pending_reward_open_jobs
    )
    # Prefer live remaining when jobs use opens_left (newer path).
    try:
        live_n = _reward_open_packages_remaining()
        if live_n > 0:
            n = live_n
    except Exception:
        pass
    _pending_reward_open_jobs.clear()
    _reward_open_paused = False
    if log and n > 0:
        _set_serial_delivery_status(
            f"Reward open queue cancelled ({reason}). {n} package(s) left — open Reward Center yourself.",
            hold_sec=15.0,
            log=True,
        )


def pause_pending_reward_opens(reason: str = "session pause", *, log: bool = True) -> None:
    """Stop opening until back in-world; queue is kept and resumes automatically."""
    global _reward_open_paused
    if not _pending_reward_open_jobs:
        _reward_open_paused = False
        return
    if _reward_open_paused:
        return
    _reward_open_paused = True
    n = _reward_open_packages_remaining()
    if log and n > 0:
        _set_serial_delivery_status(
            f"Reward open paused ({reason}). {n} package(s) will resume when you load back in.",
            hold_sec=12.0,
            log=True,
        )


def resume_pending_reward_opens() -> None:
    global _reward_open_paused
    if not _reward_open_paused or not _pending_reward_open_jobs:
        _reward_open_paused = False
        return
    _reward_open_paused = False
    now = time.time()
    resume_at = now + _REWARD_OPEN_RESUME_DELAY_SEC
    for job in _pending_reward_open_jobs:
        job["wait_until"] = max(float(job.get("wait_until") or 0.0), resume_at)
    n = _reward_open_packages_remaining()
    if n > 0:
        _set_serial_delivery_status(
            f"Resuming reward open… {n} package(s) left.",
            hold_sec=20.0,
            log=True,
        )


def _reward_open_packages_remaining() -> int:
    total = 0
    for job in _pending_reward_open_jobs:
        if "opens_left" in job:
            before = int(job.get("before_count") or 0)
            live = _reward_open_job_live_remaining(job)
            if live is not None:
                total += live
            else:
                total += max(0, int(job.get("opens_left") or 0))
            continue
        indices = list(job.get("indices") or [])
        cursor = int(job.get("cursor") or 0)
        total += max(0, len(indices) - cursor)
    return total


def _reward_open_job_live_remaining(job: dict[str, Any]) -> int | None:
    """How many packages still sit above before_count (None if manager unavailable)."""
    before = int(job.get("before_count") or 0)
    identity = job.get("identity")
    tidx: Optional[int] = None
    if identity is not None:
        tidx = _resolve_serial_target_index(identity)
    if tidx is None:
        try:
            tidx = int(job.get("player_index"))
        except Exception:
            tidx = None
    if tidx is None:
        return None
    mgr = _manager_for_player_index(int(tidx))
    if mgr is None:
        return None
    try:
        n = int(_package_count(mgr) or 0)
    except Exception:
        return None
    return max(0, n - before)


def _reward_open_gap_sec(remaining_packages: int) -> float:
    try:
        n = max(1, int(remaining_packages))
    except Exception:
        n = 1
    if n >= int(_REWARD_OPEN_LARGE_QUEUE_PACKAGES):
        return float(_REWARD_OPEN_GAP_LARGE_SEC)
    return float(_REWARD_OPEN_GAP_SEC)


def _queue_reward_open_jobs(
    specs: List[tuple[Any, int, int, int]],
    *,
    label: str,
) -> tuple[int, str]:
    """Queue paced Server_OpenPackage work (one newest package every 3–5s).

    Each spec is ``(identity, player_index, before_count, package_count)``.
    Opens always target the live newest index so prior opens cannot stale-index crash.
    """
    global _pending_reward_open_jobs, _reward_open_paused
    total = 0
    for _identity, _idx, _before, count in specs:
        try:
            total += max(0, int(count))
        except Exception:
            pass
    if total <= 0:
        return 0, " No new reward packages to open."
    now = time.time()
    for i, (identity, player_index, before_count, pkg_count) in enumerate(specs):
        try:
            count = max(0, int(pkg_count))
            before = max(0, int(before_count))
        except Exception:
            continue
        if count <= 0:
            continue
        _pending_reward_open_jobs.append({
            "identity": identity,
            "player_index": int(player_index),
            "before_count": before,
            "opens_left": count,
            "wait_until": now + _REWARD_OPEN_FIRST_DELAY_SEC + (i * 0.15),
            "label": str(label or "rewards"),
        })
    _reward_open_paused = False
    gap = _reward_open_gap_sec(total)
    eta = max(3, int(round(total * gap)))
    note = (
        f" Opening rewards one-by-one (~{gap:.0f}s between packages, ~{eta}s total). "
        "Stay in-world until the status says Rewards opened."
    )
    _set_serial_delivery_status(
        f"Opening rewards ({total} mail package(s), ~{gap:.0f}s apart)…",
        hold_sec=max(45.0, float(eta) + 30.0),
        log=True,
    )
    return total, note


def _queue_reward_open_since_for_identities(
    identities: List[Any],
    before_counts: dict[str, int],
    *,
    label: str = "GZO delivery",
) -> tuple[int, str]:
    specs: List[tuple[Any, int, int, int]] = []
    seen: set[str] = set()
    for identity in identities:
        key = str(getattr(identity, "key", "") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        tidx = _resolve_serial_target_index(identity)
        if tidx is None:
            continue
        mgr = _manager_for_player_index(int(tidx))
        if mgr is None:
            continue
        before = int(before_counts.get(key, 0))
        try:
            n = int(_package_count(mgr) or 0)
        except Exception:
            n = 0
        count = max(0, n - before)
        if count > 0:
            specs.append((identity, int(tidx), before, count))
    total, note = _queue_reward_open_jobs(specs, label=label)
    if total > 0:
        _log_info(f"Queued batched open for {total} new mail package(s) ({label}).")
    return total, note


def _pending_reward_package_specs() -> List[tuple[Any, int, int, int]]:
    """Collect (identity, player_index, before_count, package_count) for every live manager."""
    specs: List[tuple[Any, int, int, int]] = []
    seen: set[int] = set()

    def _add(player_index: int, mgr: Any) -> None:
        if mgr is None:
            return
        oid = id(mgr)
        if oid in seen:
            return
        seen.add(oid)
        try:
            n = int(_package_count(mgr) or 0)
        except Exception:
            n = 0
        if n > 0:
            specs.append((None, int(player_index), 0, n))

    local_pc = get_pc()
    if local_pc is not None:
        local_mgr, _ = _find_rewards_manager_on_pc(local_pc)
        _add(0, local_mgr)
    _world, game_state = _gbc_session_world_and_gamestate()
    player_array = getattr(game_state, "PlayerArray", None) if game_state is not None else None
    try:
        party_count = len(player_array) if player_array is not None else 0
    except Exception:
        party_count = 0
    for player_index in range(party_count):
        mgr = _manager_for_player_index(player_index)
        _add(player_index, mgr)
    for mgr in _live_gbx_rewards_managers():
        _add(0, mgr)
    return specs


def count_pending_reward_packages() -> int:
    return sum(max(0, int(spec[3] or 0)) for spec in _pending_reward_package_specs())


def _queue_open_all_pending_packages() -> tuple[int, int]:
    """Queue every pending package on live party managers (paced). Returns (packages, managers)."""
    specs = _pending_reward_package_specs()
    total, _note = _queue_reward_open_jobs(specs, label="pending rewards")
    return total, len(specs)


def _process_pending_reward_open_jobs() -> None:
    if not _pending_reward_open_jobs or _reward_open_paused:
        return
    if _serial_mail_join_quiet():
        return
    try:
        from .session_guards import session_safe

        if not session_safe():
            pause_pending_reward_opens("left session")
            return
    except Exception:
        pass
    now = time.time()
    job = _pending_reward_open_jobs[0]
    if now < float(job.get("wait_until") or 0.0):
        return
    identity = job.get("identity")
    tidx: Optional[int] = None
    if identity is not None:
        tidx = _resolve_serial_target_index(identity)
    if tidx is None:
        try:
            tidx = int(job.get("player_index"))
        except Exception:
            tidx = None
    if tidx is None:
        _pending_reward_open_jobs.pop(0)
        return
    mgr = _manager_for_player_index(int(tidx))
    if mgr is None:
        _pending_reward_open_jobs.pop(0)
        return

    # Newest-first live open: never reuse stale indices after a prior open removes a package.
    if "opens_left" in job or "before_count" in job:
        before = int(job.get("before_count") or 0)
        opens_left = int(job.get("opens_left") or 0)
        try:
            n = int(_package_count(mgr) or 0)
        except Exception:
            n = 0
        if n <= before or opens_left <= 0:
            _pending_reward_open_jobs.pop(0)
        else:
            opened = _open_manager_package_index(mgr, n - 1)
            job["opens_left"] = opens_left - 1
            try:
                n_after = int(_package_count(mgr) or 0)
            except Exception:
                n_after = max(0, n - 1)
            if n_after <= before or int(job["opens_left"]) <= 0:
                _pending_reward_open_jobs.pop(0)
            else:
                remaining = max(0, n_after - before)
                job["wait_until"] = now + _reward_open_gap_sec(remaining)
            if not opened:
                _log_warning(
                    f"Server_OpenPackage({n - 1}) returned false (player {tidx}); "
                    "continuing paced queue."
                )
    else:
        # Legacy index-list jobs (should be rare after this build).
        indices = list(job.get("indices") or [])
        cursor = int(job.get("cursor") or 0)
        if cursor >= len(indices):
            _pending_reward_open_jobs.pop(0)
        else:
            try:
                n = int(_package_count(mgr) or 0)
            except Exception:
                n = 0
            if n <= 0:
                _pending_reward_open_jobs.pop(0)
            else:
                _open_manager_package_index(mgr, n - 1)
                job["cursor"] = cursor + 1
                if int(job["cursor"]) >= len(indices):
                    _pending_reward_open_jobs.pop(0)
                else:
                    remaining = _reward_open_packages_remaining()
                    job["wait_until"] = now + _reward_open_gap_sec(remaining)

    remaining = _reward_open_packages_remaining()
    if _pending_reward_open_jobs and not _reward_open_paused:
        gap = _reward_open_gap_sec(max(1, remaining))
        _set_serial_delivery_status(
            f"Opening rewards… {remaining} package(s) left (~{gap:.0f}s between opens).",
            hold_sec=45.0,
            log=False,
        )
    elif not _pending_reward_open_jobs:
        _set_serial_delivery_status(
            "Rewards opened.",
            hold_sec=20.0,
            log=True,
        )


def _open_manager_packages_since(mgr: Any, before_count: int) -> int:
    """Legacy sync open — prefer paced queue for more than one package."""
    try:
        n = int(_package_count(mgr) or 0)
    except Exception:
        n = 0
    before = max(0, int(before_count))
    count = max(0, n - before)
    if count <= 0:
        return 0
    if count == 1:
        return 1 if _open_manager_package_index(mgr, n - 1) else 0
    total, _note = _queue_reward_open_jobs([(None, 0, before, count)], label="sync open")
    return total


def _open_reward_packages_since_for_identities(
    identities: List[Any],
    before_counts: dict[str, int],
) -> int:
    """Queue paced open for packages created during this serial-delivery sequence."""
    total, _note = _queue_reward_open_since_for_identities(
        identities,
        before_counts,
        label="serial delivery",
    )
    return 1 if total > 0 else 0


def _open_reward_packages_for_indices(player_indices: List[int]) -> int:
    """Queue paced open ONLY on the managers for these party indices (never bulk)."""
    specs: List[tuple[Any, int, int, int]] = []
    seen: set[int] = set()
    for idx in player_indices:
        try:
            i = int(idx)
        except Exception:
            continue
        if i in seen:
            continue
        seen.add(i)
        mgr = _manager_for_player_index(i)
        if mgr is None:
            _log_warning(f"Targeted open: no GbxRewardsManager for player index {i}.")
            continue
        try:
            n = int(_package_count(mgr) or 0)
        except Exception:
            n = 0
        if n > 0:
            specs.append((None, i, 0, n))
    total, _note = _queue_reward_open_jobs(specs, label="targeted open")
    if total:
        _log_info(f"Queued paced open for {total} package(s) on {len(specs)} targeted manager(s).")
    else:
        _log_warning("Targeted open: no target managers had packages to open.")
    return 1 if total > 0 else 0


def _delete_manager_packages_since(mgr: Any, before_count: int) -> int:
    """Delete packages created after ``before_count`` on one manager (newest→oldest)."""
    if mgr is None:
        return 0
    delete_fn = getattr(mgr, "Server_DeletePackage", None)
    if not callable(delete_fn):
        return 0
    pkgs = getattr(mgr, "packages", None)
    try:
        n = len(pkgs) if pkgs is not None else 0
    except Exception:
        n = 0
    start = max(0, int(before_count))
    deleted = 0
    # Delete from the highest index down so earlier indices stay valid as the
    # array shrinks after each Server_DeletePackage call.
    for i in range(n - 1, start - 1, -1):
        try:
            delete_fn(i)
            deleted += 1
        except Exception as exc:
            _log_warning(f"Server_DeletePackage({i}) failed on manager {mgr}: {exc!r}")
    return deleted


def _suppress_non_target_packages(before_counts: dict[int, int], target_indices: List[int]) -> int:
    """Remove the freshly-created reward package on every non-target party member.

    ``GiveRewardAllPlayers`` hands a real loyalty package to the whole lobby.  For a
    targeted send we delete each non-target's new package before it is opened so
    only the intended player actually receives an item.
    """
    targets = {int(i) for i in target_indices}
    suppressed = 0
    for idx, before in list(before_counts.items()):
        try:
            i = int(idx)
        except Exception:
            continue
        if i in targets:
            continue
        mgr = _manager_for_player_index(i)
        if mgr is None:
            continue
        removed = _delete_manager_packages_since(mgr, int(before))
        if removed:
            suppressed += 1
    if suppressed:
        _log_info(f"Suppressed loyalty package for {suppressed} non-target player(s).")
    return suppressed


def _snapshot_all_party_package_counts(target_indices: List[int]) -> dict[int, int]:
    """Snapshot package counts for the WHOLE party (targets + everyone else)."""
    all_indices = list(_all_party_player_indices_for_serial_delivery())
    for i in target_indices:
        try:
            iv = int(i)
        except Exception:
            continue
        if iv not in all_indices:
            all_indices.append(iv)
    return _snapshot_player_package_counts(all_indices)


def _ensure_backpack_capacity_for_indices(player_indices: List[int], serial_count: int) -> int:
    """Expand backpack only when capacity is known and too small for this delivery.

    Never rewrite size on every send — that was flipping players' backpacks when
    MaxSize reads failed (treated as 0) or headroom forced a bump each time.
    """
    if not player_indices:
        return 0
    try:
        from .inventory_capacity import (
            clamp_container_size,
            get_player_state_by_party_index,
            set_backpack_size_for_player_state,
        )
    except Exception as exc:
        _log_warning(f"Could not import inventory capacity helpers before serial delivery: {exc!r}")
        return 0

    def _read_backpack_max(ps: Any) -> int | None:
        try:
            container = getattr(ps, "BackpackContainer", None)
            max_size = getattr(container, "MaxSize", None) if container is not None else None
            if max_size is None:
                return None
            values: list[int] = []
            for field in ("Value", "BaseValue"):
                try:
                    raw = getattr(max_size, field, None)
                    if raw is None:
                        continue
                    values.append(int(raw))
                except Exception:
                    continue
            if not values:
                return None
            cur = max(values)
            return cur if cur > 0 else None
        except Exception:
            return None

    def _read_backpack_used(ps: Any) -> int:
        try:
            items = getattr(getattr(ps, "BackpackItems", None), "items", None)
            if items is None:
                items = getattr(getattr(ps, "BackpackContainer", None), "items", None)
            return max(0, int(len(items)))
        except Exception:
            return 0

    need_items = max(1, int(serial_count or 0))
    changed = 0
    for idx in player_indices:
        try:
            ps = get_player_state_by_party_index(int(idx))
            if ps is None:
                continue
            cur = _read_backpack_max(ps)
            if cur is None:
                # Don't guess — rewriting MaxSize when we cannot read it is what
                # kept auto-changing backpacks on every code delivery.
                continue
            used = _read_backpack_used(ps)
            # Need room for current items + new serials + small padding (not +100 always).
            target_size = clamp_container_size(max(cur, used + need_items + 8))
            if cur >= target_size:
                continue
            set_backpack_size_for_player_state(ps, target_size)
            changed += 1
        except Exception as exc:
            _log_warning(f"Backpack pre-size failed for player index {idx}: {exc!r}")
    if changed:
        _log_info(f"Expanded backpack for {changed} target player(s) to fit {need_items} serial(s).")
    return changed


def _serial_delivery_char_count(serials: List[str]) -> int:
    return sum(len(str(s or "").strip()) for s in serials if str(s or "").strip())


def _serial_delivery_estimated_payload_chars(serials: List[str]) -> int:
    # The engine stores SerialNumbers as an array, not just one concatenated string.
    # Count a little overhead per entry so a package with many small serials does
    # not land close to the real client replication limit.
    total = 0
    for raw in serials:
        text = str(raw or "").strip()
        if text:
            total += len(text) + _SERIAL_DELIVERY_PER_SERIAL_OVERHEAD_CHARS
    return total


def _max_items_per_delivery_package(total_serials: int) -> int:
    """Fewer serials per loyalty package as dumps grow — 25/pkg AVd near ~500."""
    n = max(0, int(total_serials or 0))
    if n >= 500:
        return 6
    if n >= 400:
        return 8
    if n >= 200:
        return 10
    if n >= 80:
        return 12
    return max(1, int(_SERIAL_DELIVERY_MAX_ITEMS_PER_PACKAGE or 12))


def _delivery_chunk_gap(
    chunk_len: int,
    total_serials: int,
    *,
    package_index: int = 0,
) -> float:
    """Pace mail grants so ~500-code packs do not hitch or AV mid-send."""
    gap = float(_SERIAL_DELIVERY_POST_OPEN_DELAY_SEC or 0.0)
    if total_serials >= 500:
        gap = max(gap, 1.25)
    elif total_serials >= 400:
        gap = max(gap, 1.00)
    elif total_serials >= 200:
        gap = max(gap, 0.70)
    elif total_serials >= 80:
        gap = max(gap, 0.45)
    if chunk_len >= 10:
        gap = max(gap, 0.55)
    elif chunk_len >= 6:
        gap = max(gap, 0.40)
    every = max(1, int(_SERIAL_DELIVERY_COOLDOWN_EVERY or 6))
    if package_index > 0 and package_index % every == 0:
        gap = max(gap, float(_SERIAL_DELIVERY_COOLDOWN_SEC or 2.0))
    return max(0.0, gap)


def _chunk_serials_for_delivery(
    serials: List[str],
    max_chars: int = _SERIAL_DELIVERY_SAFE_CHARS,
    *,
    max_items: int | None = None,
) -> List[List[str]]:
    """Split serials into reward-package sized chunks.

    Cap by estimated payload chars **and** item count. Large dumps use fewer
    items per package so GiveReward + SerialNumbers writes stay under the AV line.
    """
    cleaned = [str(s or "").strip() for s in (serials or []) if str(s or "").strip()]
    chunks: List[List[str]] = []
    current: List[str] = []
    current_chars = 0
    limit = max(1, int(max_chars or _SERIAL_DELIVERY_SAFE_CHARS))
    item_cap = max(1, int(max_items if max_items is not None else _max_items_per_delivery_package(len(cleaned))))
    for text in cleaned:
        n = len(text) + _SERIAL_DELIVERY_PER_SERIAL_OVERHEAD_CHARS
        if current and (current_chars + n > limit or len(current) >= item_cap):
            chunks.append(current)
            current = []
            current_chars = 0
        raw_n = len(text)
        if raw_n > _MAX_SERIAL_DELIVERY_CHARS:
            _log_warning(
                f"Single serial is {raw_n} raw chars, exceeding {_MAX_SERIAL_DELIVERY_CHARS}; "
                "delivering it alone because individual serials cannot be split."
            )
        current.append(text)
        current_chars += n
    if current:
        chunks.append(current)
    return chunks


def _serial_delivery_chunks(serials: List[str]) -> List[List[str]]:
    """Public-ish helper for the UI: preview exactly how delivery will split."""
    return _chunk_serials_for_delivery(serials)


def _serial_delivery_chunk_stats(serials: List[str]) -> List[dict[str, int]]:
    """Return per-package stats for display without exposing engine objects."""
    out: List[dict[str, int]] = []
    for i, chunk in enumerate(_chunk_serials_for_delivery(serials), 1):
        out.append({
            "index": i,
            "serials": len(chunk),
            "raw_chars": _serial_delivery_char_count(chunk),
            "estimated_chars": _serial_delivery_estimated_payload_chars(chunk),
        })
    return out


def _serial_delivery_chunks_desc(chunks: List[List[str]]) -> str:
    if len(chunks) <= 1:
        return f"1 package, {_serial_delivery_char_count(chunks[0]) if chunks else 0} chars"
    sizes = [f"{_serial_delivery_char_count(c)} raw/{_serial_delivery_estimated_payload_chars(c)} est" for c in chunks]
    return f"{len(chunks)} packages, char payloads: " + ", ".join(sizes[:8]) + (", ..." if len(sizes) > 8 else "")


def _apply_level_override_to_serials(serials: List[str], level: int) -> tuple[List[str], str | None]:
    """Rewrite leading item level on @U / human serials. Safe to call per chunk on tick."""
    try:
        from .serial_converter import human_to_serial, rewrite_item_level, serial_to_human
    except Exception as exc:
        return list(serials), f"Level override unavailable ({exc})"
    try:
        level_i = max(1, min(int(level or 70), 100))
    except Exception:
        level_i = 70
    level_re = re.compile(r"^(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*)\d+")
    out: List[str] = []
    warnings: List[str] = []
    for index, serial in enumerate(serials):
        raw = str(serial or "").strip()
        if not raw:
            continue
        try:
            if raw.startswith("@U"):
                # Header-only rewrite (MSBT) — survives codes that fail full part parse.
                out.append(str(rewrite_item_level(raw, level_i)))
                continue
            human = raw
            new_human, count = level_re.subn(rf"\g<1>{level_i}", human, count=1)
            if count <= 0:
                raise ValueError("could not find leading item level")
            converted = human_to_serial(new_human)
            if not converted or not str(converted).startswith("@U"):
                raise ValueError("human→@U re-encode failed after level rewrite")
            out.append(str(converted))
        except Exception as exc:
            out.append(raw)
            warnings.append(f"#{index + 1}:{exc}")
    warning = None
    if warnings:
        warning = f"Level override skipped for {len(warnings)} serial(s) ({warnings[0]})."
    return out, warning

def _read_package_serials(package: Any) -> List[str]:
    out: List[str] = []
    contents = getattr(package, "contents", None)
    if contents is None:
        return out
    try:
        rows = list(contents)
    except Exception:
        return out
    for entry in rows:
        nums = getattr(entry, "SerialNumbers", None)
        if nums is None:
            continue
        try:
            for value in nums:
                text = str(value or "").strip()
                if text:
                    out.append(text)
        except Exception:
            continue
    return out


def _verify_package_serials(package: Any, serials: List[str]) -> Tuple[bool, int, int]:
    actual = _read_package_serials(package)
    expected = [str(s or "").strip() for s in serials if str(s or "").strip()]
    got = set(actual)
    want = set(expected)
    missing = want - got
    return (not missing and len(got) >= len(want), len(got), len(missing))


def _apply_serials_to_package(package: Any, serials: List[str]) -> int:
    """
    Write the full serial batch onto ``contents[0].SerialNumbers``.

    Do not use RewardsDataIndex one-serial-per-content mapping — that caps weekly
    templates at ~5 items and wipes a full multi-serial write.
    """
    if not serials:
        return 0
    work = [str(s).strip() for s in serials if str(s).strip()]
    if not work:
        return 0
    contents = getattr(package, "contents", None)
    if contents is None:
        return 0
    try:
        n_contents = len(contents)
    except Exception:
        return 0
    if n_contents == 0:
        return 0

    try:
        entry = contents[0]
    except Exception:
        return 0
    serial_numbers = getattr(entry, "SerialNumbers", None)
    if serial_numbers is None:
        return 0
    try:
        if hasattr(serial_numbers, "clear"):
            serial_numbers.clear()
        for s in work:
            if hasattr(serial_numbers, "append"):
                serial_numbers.append(s)
        for i in range(1, n_contents):
            try:
                other = contents[i]
                other_sns = getattr(other, "SerialNumbers", None)
                if other_sns is not None and hasattr(other_sns, "clear"):
                    other_sns.clear()
                if hasattr(other, "RewardsDataIndex"):
                    try:
                        setattr(other, "RewardsDataIndex", -1)
                    except Exception:
                        pass
            except Exception:
                pass
        try:
            while len(contents) > 1 and hasattr(contents, "pop"):
                contents.pop()
        except Exception:
            pass
        ok, got, missing = _verify_package_serials(package, work)
        if not ok:
            _log_warning(f"Serial verify after write failed: package has {got}, missing {missing}.")
            return 0
        _log_info(f"SerialNumbers write: {len(work)} serial(s) on contents[0] (verified {got}).")
        return 1
    except Exception as e:
        _log_warning(f"SerialNumbers write (contents[0] full batch): {e}")
        return 0


def _package_matches_expected_reward(package: Any, expected_reward: str) -> bool:
    """Fail closed when a new package exposes a different reward definition."""
    reward_def = getattr(package, "RewardsDef", None)
    if reward_def is None:
        return False
    expected = str(expected_reward or "").strip().split("/")[-1].casefold()
    markers: List[str] = [str(reward_def)]
    for obj in (reward_def, getattr(reward_def, "instance", None)):
        if obj is None:
            continue
        for attr in ("Name", "name", "_experimental_name", "UniqueName"):
            try:
                value = getattr(obj, attr, None)
            except Exception:
                value = None
            if value is not None:
                markers.append(str(value))
    return bool(expected and any(expected in marker.casefold() for marker in markers))


def _patch_manager_package_since(
    mgr: Any,
    serials: List[str],
    before_count: int,
    package_offset: int = 0,
    *,
    expected_reward: str = "",
) -> bool:
    pkgs = getattr(mgr, "packages", None)
    if pkgs is None:
        return False
    try:
        n_pkg = len(pkgs)
    except Exception:
        return False
    expected_count = max(0, int(before_count)) + max(0, int(package_offset or 0)) + 1
    if n_pkg != expected_count:
        # Ambiguous package creation: never patch when an unrelated reward may
        # have arrived or the expected package has not appeared yet.
        return False
    start = max(0, int(before_count))
    # Chunked deliveries may create several reward packages before the tick job
    # sees them.  Use package_offset to map chunk 0 -> first new package,
    # chunk 1 -> second new package, etc., instead of every job overwriting the
    # newest package.
    preferred = start + max(0, int(package_offset or 0))
    candidate_indices: List[int] = []
    if preferred < n_pkg:
        candidate_indices.append(preferred)
    for i in candidate_indices:
        try:
            package = pkgs[i]
        except Exception:
            continue
        if expected_reward and not _package_matches_expected_reward(package, expected_reward):
            _log_warning(
                f"Refusing to patch package {i}: RewardsDef does not match {expected_reward!r}."
            )
            continue
        if _apply_serials_to_package(package, serials) > 0:
            ok, got, missing = _verify_package_serials(package, serials)
            if ok:
                return True
            _log_warning(f"Patched package {i}, but verify has {got} serial(s), missing {missing}.")
    return False

def _patch_all_managers_last_package(serials: List[str]) -> Tuple[int, int]:
    """Returns (managers_with_patch, total_managers)."""
    managers = _unique_gbx_rewards_managers()
    if not managers:
        return (0, 0)
    patched = 0
    for mgr in managers:
        pkgs = getattr(mgr, "packages", None)
        if pkgs is None:
            continue
        try:
            n = len(pkgs)
        except Exception:
            continue
        if n <= 0:
            continue
        try:
            package = pkgs[n - 1]
        except Exception:
            continue
        if _apply_serials_to_package(package, serials) > 0:
            patched += 1
    return (patched, len(managers))


def _patch_single_player_index_last_package(serials: List[str], player_index: int) -> Tuple[int, int]:
    """Patch last package on the GbxRewardsManager for PlayerArray[player_index]. Returns (patched, 1)."""
    mgr = _manager_for_player_index(player_index)
    if mgr is None:
        _log_error(f"Give_Serial: index patch: no GbxRewardsManager for player index {player_index}.")
        return (0, 0)
    pkgs = getattr(mgr, "packages", None)
    if pkgs is None:
        return (0, 1)
    try:
        n_pkg = len(pkgs)
    except Exception:
        return (0, 1)
    if n_pkg <= 0:
        return (0, 1)
    try:
        package = pkgs[n_pkg - 1]
    except Exception:
        return (0, 1)
    if _apply_serials_to_package(package, serials) > 0:
        return (1, 1)
    return (0, 1)


def _patch_player_indices_since_counts(
    serials: List[str],
    before_counts: dict[int, int],
    package_offset: int = 0,
    *,
    expected_reward: str = "",
) -> Tuple[int, int]:
    if not before_counts:
        return (0, 0)
    patched = 0
    for idx, before in list(before_counts.items()):
        mgr = _manager_for_player_index(int(idx))
        if mgr is None:
            continue
        if _patch_manager_package_since(
            mgr,
            serials,
            int(before),
            package_offset,
            expected_reward=expected_reward,
        ):
            patched += 1
    return (patched, len(before_counts))

def _patch_player_indices_last_package(serials: List[str], player_indices: List[int]) -> Tuple[int, int]:
    """Patch last reward package for specific PlayerArray indices. Returns (patched_count, target_count)."""
    seen: set[int] = set()
    targets: List[int] = []
    for idx in player_indices:
        try:
            i = int(idx)
        except Exception:
            continue
        if i in seen:
            continue
        seen.add(i)
        targets.append(i)
    if not targets:
        return (0, 0)
    patched = 0
    total = 0
    for idx in targets:
        p, t = _patch_single_player_index_last_package(serials, idx)
        total += max(1, t)
        if p > 0:
            patched += 1
    return (patched, len(targets))


def _backpack_occupied_snapshot(pc: Any = None) -> dict[int, tuple[int, str]]:
    """Return a cheap occupied-slot signature for post-reward verification.

    Do not run the full inventory inspector here: boosted backpack capacities can
    expose thousands of empty backing slots.  We only stringify occupied items.
    """
    target_pc = pc if pc is not None else get_pc()
    ps = getattr(target_pc, "PlayerState", None) if target_pc is not None else None
    wrapper = getattr(ps, "BackpackItems", None) if ps is not None else None
    entries = getattr(wrapper, "items", None) if wrapper is not None else None
    try:
        slots = list(entries) if entries is not None else []
    except Exception:
        return {}
    out: dict[int, tuple[int, str]] = {}
    for index, slot in enumerate(slots):
        try:
            inv_item = getattr(slot, "InventoryItem", None)
        except Exception:
            inv_item = None
        if inv_item is None:
            continue
        signature_parts: List[str] = []
        for attr in (
            "Handle",
            "SourceItemHandle",
            "ItemHandle",
            "ItemSerial",
            "Serial",
            "item",
        ):
            try:
                value = getattr(inv_item, attr, None)
            except Exception:
                value = None
            if value is None:
                continue
            try:
                text = str(value).strip()
            except Exception:
                text = ""
            if text and text.lower() not in ("none", "null"):
                signature_parts.append(f"{attr}={text[:160]}")
        # Empty backing entries can still expose an InventoryItem wrapper.  Do
        # not stringify or record those wrappers across a 1,200-slot backpack.
        if not signature_parts:
            continue
        try:
            replication_id = int(getattr(slot, "ReplicationID", 0) or 0)
        except Exception:
            replication_id = 0
        preview = "|".join(signature_parts)[:240]
        out[index] = (replication_id, preview)
    return out


def _find_exact_package_index(mgr: Any, serials: List[str], hint: int = -1) -> int:
    """Find the package containing all expected serials, despite shifted indices."""
    try:
        packages = getattr(mgr, "packages", None)
        count = len(packages) if packages is not None else 0
    except Exception:
        return -1
    indices: List[int] = []
    if 0 <= int(hint) < count:
        indices.append(int(hint))
    indices.extend(i for i in range(count - 1, -1, -1) if i not in indices)
    for index in indices:
        try:
            verified, _actual, _missing = _verify_package_serials(packages[index], serials)
        except Exception:
            verified = False
        if verified:
            return index
    return -1


def _queue_exact_package_claim(
    mgr: Any,
    serials: List[str],
    package_hint: int,
    *,
    diagnostic_entry: Optional[dict[str, str]] = None,
    diagnostic_level: int = 60,
) -> None:
    now = time.time()
    _pending_exact_package_claims.append({
        "manager": mgr,
        "serials": list(serials),
        "package_hint": int(package_hint),
        "stage": "wait_open",
        "ready_at": now + _EXACT_PACKAGE_OPEN_DELAY_SEC,
        "deadline": now + _EXACT_PACKAGE_OPEN_DELAY_SEC + _EXACT_PACKAGE_INVENTORY_VERIFY_TIMEOUT_SEC,
        "backpack_before": {},
        "opened_index": -1,
        "diagnostic_entry": dict(diagnostic_entry or {}),
        "diagnostic_level": max(1, int(diagnostic_level or 60)),
    })
    _log_info(
        f"Queued exact serial package at index {package_hint} for deferred claim "
        f"({len(serials)} item(s)); awaiting package replication."
    )


def _record_exact_package_claim_result(claim: dict[str, Any], *, observed: bool, detail: str) -> None:
    """Append the async claim result to the normal spawn JSONL/dump when requested."""
    entry = dict(claim.get("diagnostic_entry") or {})
    if not entry:
        return
    serials = list(claim.get("serials") or [])
    try:
        from .item_pool_spawning import record_spawn_result

        record_spawn_result(
            entry,
            ok=bool(observed),
            method="exact_reward_backpack",
            detail=str(detail or ""),
            count=max(1, len(serials)),
            level=max(1, int(claim.get("diagnostic_level") or 60)),
            observed=bool(observed),
            delivery_channel="backpack",
        )
    except Exception as exc:
        _log_warning(f"Could not append exact package claim result to spawn dump: {exc!r}")


def _process_pending_exact_package_claims() -> None:
    """Open one exact package at a time and log only observed inventory delivery."""
    if not _pending_exact_package_claims:
        return
    try:
        from .session_guards import session_safe

        if not session_safe():
            cancel_deferred_reward_work("left session")
            return
    except Exception:
        pass
    claim = _pending_exact_package_claims[0]
    now = time.time()
    if now < float(claim.get("ready_at") or 0.0):
        return
    mgr = claim.get("manager")
    serials = list(claim.get("serials") or [])
    hint = int(claim.get("package_hint") or -1)
    stage = str(claim.get("stage") or "wait_open")

    if stage == "wait_open":
        package_index = _find_exact_package_index(mgr, serials, hint)
        if package_index < 0:
            if now < float(claim.get("deadline") or 0.0):
                claim["ready_at"] = now + 0.10
                return
            _log_warning(
                "Exact serial package claim not sent: the verified package was no longer "
                "observable after replication wait. Backpack delivery was not confirmed."
            )
            _record_exact_package_claim_result(
                claim,
                observed=False,
                detail="verified reward package disappeared before its deferred open; backpack unchanged",
            )
            _pending_exact_package_claims.pop(0)
            return
        open_one = getattr(mgr, "Server_OpenPackage", None)
        if not callable(open_one):
            _log_warning(
                "Exact serial package is verified in the Reward Center, but "
                "Server_OpenPackage is unavailable; claim it manually in-game."
            )
            _record_exact_package_claim_result(
                claim,
                observed=False,
                detail="verified reward package could not be opened automatically; backpack unchanged",
            )
            _pending_exact_package_claims.pop(0)
            return
        claim["backpack_before"] = _backpack_occupied_snapshot()
        try:
            open_one(package_index)
        except Exception as exc:
            _log_warning(f"Exact package open request failed: {exc!r}")
            _record_exact_package_claim_result(
                claim,
                observed=False,
                detail=f"exact package open request raised {exc!r}; backpack unchanged",
            )
            _pending_exact_package_claims.pop(0)
            return
        claim["stage"] = "verify_inventory"
        claim["opened_index"] = package_index
        claim["ready_at"] = now + _EXACT_PACKAGE_INVENTORY_VERIFY_DELAY_SEC
        claim["deadline"] = now + _EXACT_PACKAGE_INVENTORY_VERIFY_TIMEOUT_SEC
        _log_info(
            f"Exact package open request sent for index {package_index} "
            f"({len(serials)} item(s)); awaiting backpack verification."
        )
        return

    if stage == "verify_inventory":
        before = dict(claim.get("backpack_before") or {})
        after = _backpack_occupied_snapshot()
        changed = [index for index, signature in after.items() if before.get(index) != signature]
        if changed:
            _log_info(
                f"Exact package delivery confirmed in local backpack: "
                f"{len(changed)} new/changed occupied slot(s) after opening "
                f"{len(serials)} serial item(s)."
            )
            _record_exact_package_claim_result(
                claim,
                observed=True,
                detail=(
                    f"backpack delivery observed after exact package open; "
                    f"{len(changed)} new/changed occupied slot(s)"
                ),
            )
            _pending_exact_package_claims.pop(0)
            return
        if now < float(claim.get("deadline") or 0.0):
            claim["ready_at"] = now + 0.10
            return
        package_index = _find_exact_package_index(mgr, serials, hint)
        location = "still present in the Reward Center" if package_index >= 0 else "no longer present in the Reward Center"
        _log_warning(
            f"Exact package open returned but backpack delivery was not observed within "
            f"{_EXACT_PACKAGE_INVENTORY_VERIFY_TIMEOUT_SEC:.1f}s; package is {location}."
        )
        _record_exact_package_claim_result(
            claim,
            observed=False,
            detail=(
                f"exact package open returned but backpack delivery was not observed; "
                f"package {location}"
            ),
        )
        _pending_exact_package_claims.pop(0)
        return

    _log_warning(f"Dropping exact package claim with unknown stage {stage!r}.")
    _pending_exact_package_claims.pop(0)


def cancel_deferred_reward_work(reason: str = "session teardown") -> None:
    """Drop queued mail delivery without touching reward managers."""
    global _pending_serial_delivery_sequences, _pending_exact_package_claims
    had = bool(_pending_serial_delivery_sequences or _pending_exact_package_claims)
    try:
        _pending_serial_delivery_sequences.clear()
    except Exception:
        pass
    try:
        _pending_exact_package_claims.clear()
    except Exception:
        pass
    pause_pending_reward_opens(reason, log=False)
    if had:
        _set_serial_delivery_status(
            f"Serial delivery cancelled ({reason}).",
            hold_sec=15.0,
            log=True,
        )


def _tick_cb(*_args: Any, **_kwargs: Any) -> None:
    try:
        from .session_guards import session_safe

        if not session_safe():
            if _pending_serial_delivery_sequences or _pending_exact_package_claims:
                cancel_deferred_reward_work("left session")
            elif _pending_reward_open_jobs:
                pause_pending_reward_opens("left session")
            return
        if _reward_open_paused and _pending_reward_open_jobs:
            resume_pending_reward_opens()
    except Exception:
        pass
    try:
        _process_pending_reward_open_jobs()
    except Exception as exc:
        _log_warning(f"Reward open tick failed: {exc!r}")
    try:
        _process_pending_serial_delivery_sequences()
    except Exception as exc:
        _log_warning(f"Serial delivery tick failed: {exc!r}")
    try:
        _process_pending_exact_package_claims()
    except Exception as exc:
        _log_warning(f"Exact package claim tick failed: {exc!r}")
    uvhm_busy = False
    try:
        # This UMG tick is proven live in BL4. Share it with the UVHM state
        # machine so queued progression cannot depend solely on PlayerTick.
        from . import uvhm_runtime

        uvhm_runtime.runtime_tick(*_args, **_kwargs)
        uvhm_status = uvhm_runtime.status()
        uvhm_busy = bool(uvhm_status.get("running") or uvhm_status.get("queued"))
    except Exception as exc:
        _log_warning(f"UVHM shared tick failed: {exc!r}")
    try:
        from . import hold_session

        hold_session.runtime_tick(*_args, **_kwargs)
    except Exception as exc:
        _log_warning(f"Keep-lobby shared tick failed: {exc!r}")
    try:
        from . import challenge_bulk_runtime

        if not uvhm_busy:
            challenge_bulk_runtime.runtime_tick(*_args, **_kwargs)
    except Exception as exc:
        _log_warning(f"Bulk challenge shared tick failed: {exc!r}")
    try:
        from . import map_scout

        map_scout.runtime_tick(*_args, **_kwargs)
    except Exception:
        pass
    try:
        from . import map_party_escort

        map_party_escort.runtime_tick(*_args, **_kwargs)
    except Exception:
        pass
    try:
        from . import shinies

        shinies.shiny_drop_runtime_tick(*_args, **_kwargs)
    except Exception as exc:
        _log_warning(f"Shiny drop shared tick failed: {exc!r}")
    try:
        from . import loot_shapes

        loot_shapes.tick_drop_motion()
    except Exception:
        pass
    try:
        from . import loot_coil

        loot_coil.runtime_tick(*_args, **_kwargs)
    except Exception:
        pass

# mobility_runtime owns SQBT's single proven BP_TickWidget hook and invokes
# _tick_cb. Keeping a second hook here caused duplicate Python dispatch every
# HUD frame even while all reward/progression queues were idle.



_pending_serial_delivery_sequences: List[dict[str, Any]] = []
_serial_delivery_status_message: str = "Idle"
_serial_delivery_status_until: float = 0.0


def _set_serial_delivery_status(message: str, *, hold_sec: float = 30.0, log: bool = False) -> None:
    global _serial_delivery_status_message, _serial_delivery_status_until
    text = str(message or "").strip() or "Idle"
    _serial_delivery_status_message = text
    try:
        _serial_delivery_status_until = time.time() + max(1.0, float(hold_sec))
    except Exception:
        _serial_delivery_status_until = time.time() + 30.0
    if log:
        _log_info(text)


def serial_delivery_status() -> str:
    """Lightweight UI/HUD poller for the active chunked delivery state."""
    prog = serial_delivery_progress()
    if prog.get("active"):
        return str(prog.get("message") or "")
    if _serial_delivery_status_message and time.time() <= float(_serial_delivery_status_until or 0.0):
        return _serial_delivery_status_message
    return ""


def reward_open_progress() -> dict[str, Any]:
    """Read-only progress for the paced reward-open queue (after delivery or manual open)."""
    idle = {
        "active": False,
        "fraction": 0.0,
        "message": "",
        "label": "",
        "index": 0,
        "total": 0,
        "phase": "",
        "paused": False,
    }
    if not _pending_reward_open_jobs:
        return idle
    total = 0
    for job in _pending_reward_open_jobs:
        total += len(list(job.get("indices") or []))
    remaining = _reward_open_packages_remaining()
    if total <= 0 and remaining <= 0:
        return idle
    total = max(total, remaining)
    opened = max(0, total - remaining)
    whole = max(0.0, min(1.0, float(opened) / float(total)))
    pct = int(round(whole * 100.0))
    gap = _reward_open_gap_sec(max(1, remaining))
    eta = max(1, int(round(remaining * gap)))
    paused_note = " · paused" if _reward_open_paused else ""
    message = f"Opening rewards: {opened}/{total} packages ({pct}%){paused_note}"
    if remaining > 0 and not _reward_open_paused:
        message = f"{message} · ~{eta}s left"
    label = f"{opened}/{total} · {pct}%"
    return {
        "active": True,
        "fraction": whole,
        "percent": pct,
        "message": message,
        "label": label,
        "stage": "reward_open",
        "phase": "reward_open",
        "index": opened,
        "total": total,
        "scope": "reward mail",
        "wait_remaining": float(eta),
        "paused": bool(_reward_open_paused),
        "packages_remaining": remaining,
    }


def serial_delivery_progress() -> dict[str, Any]:
    """Return active chunked-delivery or reward-open progress for menu/HUD rendering.

    fraction is 0..1 across the whole multi-package delivery.  This is intentionally
    read-only so UI polling never mutates the delivery state machine.
    """
    if not _pending_serial_delivery_sequences:
        return reward_open_progress()
    seq = _pending_serial_delivery_sequences[0]
    chunks = list(seq.get("chunks") or [])
    total = len(chunks)
    idx = max(0, int(seq.get("index") or 0))
    stage = str(seq.get("stage") or "deliver")
    scope = str(seq.get("scope_label") or "targeted players")
    if total <= 0:
        return {"active": False, "fraction": 0.0, "message": "", "label": "", "index": 0, "total": 0}
    idx = min(idx, total - 1)
    now = time.time()

    stage_start = {
        "deliver": 0.00,
        "patch": 0.08,
        "pre_open_wait": 0.18,
        "open": 0.52,
        "chunk_open_wait": 0.52,
        "post_open_wait": 0.64,
        "wait": 0.64,
    }.get(stage, 0.0)
    stage_end = {
        "deliver": 0.08,
        "patch": 0.18,
        "pre_open_wait": 0.52,
        "open": 0.64,
        "chunk_open_wait": 0.64,
        "post_open_wait": 1.00,
        "wait": 1.00,
    }.get(stage, stage_start)

    wait_remaining = 0.0
    if stage in ("pre_open_wait", "post_open_wait", "wait"):
        wait_until = float(seq.get("wait_until") or 0.0)
        wait_remaining = max(0.0, wait_until - now)
        duration = _SERIAL_DELIVERY_PRE_OPEN_DELAY_SEC if stage == "pre_open_wait" else _SERIAL_DELIVERY_POST_OPEN_DELAY_SEC
        try:
            duration = max(0.001, float(duration))
        except Exception:
            duration = 1.0
        elapsed_frac = max(0.0, min(1.0, 1.0 - (wait_remaining / duration)))
        chunk_frac = stage_start + ((stage_end - stage_start) * elapsed_frac)
    else:
        chunk_frac = stage_start

    whole = max(0.0, min(1.0, (idx + max(0.0, min(1.0, chunk_frac))) / float(total)))
    pct = int(round(whole * 100.0))
    friendly = {
        "deliver": "sending package",
        "patch": "patching serials",
        "pre_open_wait": f"opening in {wait_remaining:.1f}s",
        "open": "opening rewards",
        "chunk_open_wait": "opening rewards",
        "post_open_wait": f"next package in {wait_remaining:.1f}s",
        "wait": f"waiting {wait_remaining:.1f}s",
    }.get(stage, stage)
    message = f"Serial delivery {idx + 1}/{total}: {friendly} ({pct}%)"
    label = f"{idx + 1}/{total} · {pct}%"
    return {
        "active": True,
        "fraction": whole,
        "percent": pct,
        "message": message,
        "label": label,
        "stage": stage,
        "index": idx + 1,
        "total": total,
        "scope": scope,
        "wait_remaining": wait_remaining,
    }


def _next_loyalty_reward_name() -> Tuple[str, int, int]:
    global _loyalty_rotation_index
    n = len(LOYALTY_REWARD_DEF_NAMES)
    if n:
        idx = _loyalty_rotation_index % n
        name = LOYALTY_REWARD_DEF_NAMES[idx]
        _loyalty_rotation_index = (_loyalty_rotation_index + 1) % n
        return name, idx + 1, n
    return DEFAULT_REWARD_DEF_NAME, 1, 1


def _snapshot_serial_target_identity(player_index: int) -> Any:
    from .uvhm_progression import selected_lobby_identity

    return selected_lobby_identity(int(player_index))


def _resolve_serial_target_index(identity: Any) -> Optional[int]:
    """Resolve a primitive identity to its current party index; never reuse a stale index."""
    from .uvhm_progression import resolve_lobby_pc

    pc = resolve_lobby_pc(identity)
    if pc is None:
        return None
    ps = getattr(pc, "PlayerState", None)
    for index in _all_party_player_indices_for_serial_delivery():
        candidate = _pc_for_player_index(index)
        if candidate is pc:
            return index
        if ps is not None and candidate is not None and getattr(candidate, "PlayerState", None) is ps:
            return index
    return None


def _grant_serials_to_player_index(serials: List[str], player_index: int) -> bool:
    """
    Grant serials to **one** party index only (Item Serial / create_and_override path).

    Never uses GiveRewardAllPlayers — guests and host alike get a direct GiveReward.
    """
    if _serial_mail_join_quiet():
        _log_warning("Serial grant deferred: lobby join/leave quiet window.")
        return False
    try:
        from .session_guards import session_safe

        if not session_safe():
            _log_warning("Serial grant skipped: not in a safe in-world session.")
            return False
    except Exception:
        pass
    chunk = [str(s).strip() for s in (serials or []) if str(s).strip()]
    if not chunk:
        return False
    return bool(
        _do_give_serial_chunk(
            chunk,
            False,
            serial_only_player_index=int(player_index),
        )
    )


def _queue_serial_delivery_sequence(
    serials: List[str],
    player_indices: List[int],
    *,
    scope_label: str,
    open_rewards: bool = False,
    level_override: bool = False,
    level: int = 70,
) -> int:
    """
    Tick-paced targeted delivery — one player index at a time, never lobby-wide mail.

    Stages: deliver (targeted grant) → short post wait → next chunk. No patch/suppress/
    open-per-chunk (those used to freeze the host on big GZO dumps). Optional single
    open-rewards pass runs once after the full sequence completes.

    Returns the number of resolved target players queued (0 = nothing will deliver).
    """
    try:
        from .session_guards import session_safe

        if not session_safe():
            _log_error("Give_Serial: refused — not in a safe in-world session.")
            return 0
    except Exception:
        pass
    cleaned = [str(s).strip() for s in (serials or []) if str(s).strip()]
    chunks = _chunk_serials_for_delivery(
        cleaned,
        max_items=_max_items_per_delivery_package(len(cleaned)),
    )
    if not chunks:
        _log_error("No serial strings after delivery chunking.")
        return 0
    targets: List[int] = []
    target_identities: List[Any] = []
    seen: set[int] = set()
    for idx in player_indices:
        try:
            i = int(idx)
        except Exception:
            continue
        if i in seen:
            continue
        seen.add(i)
        try:
            identity = _snapshot_serial_target_identity(i)
        except Exception as exc:
            _log_error(f"Give_Serial: could not snapshot stable identity for index {i}: {exc}")
            continue
        if identity is None:
            _log_error(f"Give_Serial: no lobby identity for index {i}.")
            continue
        targets.append(i)
        target_identities.append(identity)
    if not targets:
        _log_error("Give_Serial: no target player indices.")
        return 0

    _ensure_backpack_capacity_for_indices(targets, len(cleaned))
    _gbc_run_session_timer_from_give_serial()
    # Baseline party size so a mid-send join can arm the quiet pause.
    global _serial_party_count_seen
    _serial_party_count_seen = _live_party_count_for_serial()
    defer_open = bool(open_rewards) and len(cleaned) >= int(_SERIAL_DELIVERY_DEFER_OPEN_SERIALS)
    if len(chunks) > 1 or len(targets) > 1:
        _log_info(
            f"Targeted serial delivery for {scope_label}: {len(cleaned)} serial(s), "
            f"{len(targets)} player(s), {_serial_delivery_chunks_desc(chunks)}"
            f"{' (open rewards after all packages)' if defer_open else ''}."
        )
    else:
        _log_info(
            f"Targeted serial delivery for {scope_label}: 1 package, {len(cleaned)} serial(s) → index {targets[0]}."
        )
    _set_serial_delivery_status(
        f"Serial delivery queued: {len(chunks)} package(s) × {len(targets)} player(s) ({scope_label})",
        log=True,
    )
    before_counts_by_key: dict[str, int] = {}
    for i, identity in zip(targets, target_identities):
        mgr = _manager_for_player_index(i)
        before_counts_by_key[str(getattr(identity, "key", "") or "")] = (
            _package_count(mgr) if mgr else 0
        )
    try:
        level_i = max(1, min(int(level or 70), 100))
    except Exception:
        level_i = 70
    _pending_serial_delivery_sequences.append({
        "chunks": chunks,
        "targets": target_identities,
        "scope_label": scope_label,
        "index": 0,
        "target_i": 0,
        "stage": "deliver",
        "wait_until": 0.0,
        "open_rewards": bool(open_rewards),
        "defer_open_until_end": bool(defer_open),
        "level_override": bool(level_override),
        "level": level_i,
        "before_counts_by_key": before_counts_by_key,
        "chunk_before_counts_by_key": dict(before_counts_by_key),
        "opened_per_chunk": False,
        "total_serials": len(cleaned),
        "delivered_serials": 0,
        "chunk_retries": 0,
    })
    # Do not grant on the click/frame that queues — first package runs on the next
    # BP_Tick so the menu stays responsive (create_and_override used to sleep here).
    return len(targets)


def _snapshot_identity_package_counts(identities: List[Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for identity in identities:
        key = str(getattr(identity, "key", "") or "")
        if not key:
            continue
        tidx = _resolve_serial_target_index(identity)
        mgr = _manager_for_player_index(int(tidx)) if tidx is not None else None
        out[key] = _package_count(mgr) if mgr else 0
    return out


def _finish_serial_delivery_sequence(
    seq: dict[str, Any],
    chunks: List[Any],
    targets: List[Any],
    scope_label: str,
) -> None:
    opened_note = " Open reward mail in-game to claim."
    if bool(seq.get("opened_per_chunk")):
        opened_note = " Rewards opened after each package."
    elif bool(seq.get("open_rewards")):
        try:
            from .session_guards import session_safe

            if not session_safe():
                opened_note = " Skipped open rewards (left session)."
            else:
                before_counts = dict(seq.get("before_counts_by_key") or {})
                if before_counts:
                    opened, open_note = _queue_reward_open_since_for_identities(
                        targets,
                        before_counts,
                        label=scope_label,
                    )
                    opened_note = open_note if opened > 0 else " No new reward packages to open."
                else:
                    live_specs: List[tuple[Any, int, int, int]] = []
                    for identity in targets:
                        tidx = _resolve_serial_target_index(identity)
                        if tidx is None:
                            continue
                        mgr = _manager_for_player_index(int(tidx))
                        if mgr is None:
                            continue
                        try:
                            n = int(_package_count(mgr) or 0)
                        except Exception:
                            n = 0
                        if n > 0:
                            live_specs.append((identity, int(tidx), 0, n))
                    if live_specs:
                        _total, opened_note = _queue_reward_open_jobs(
                            live_specs,
                            label=scope_label,
                        )
                        if not str(opened_note).strip():
                            opened_note = " No new reward packages to open."
                    else:
                        opened_note = " Could not open rewards (targets left)."
        except Exception as exc:
            opened_note = f" Skipped open rewards ({exc!r})."
    msg = (
        f"Serial delivery complete for {scope_label} "
        f"({len(chunks)} package(s) → {len(targets)} player(s))."
    )
    total = int(seq.get("total_serials") or sum(len(c) for c in chunks))
    delivered = int(seq.get("delivered_serials") or 0)
    if total > 0 and delivered < total:
        msg += f" WARNING: only {delivered}/{total} serial(s) were confirmed in mail."
    msg += opened_note
    _set_serial_delivery_status(msg, hold_sec=20.0, log=True)


def _process_pending_serial_delivery_sequences() -> None:
    if not _pending_serial_delivery_sequences:
        return
    if _serial_mail_join_quiet():
        # Keep sequences queued; resume after join quiet (do not cancel).
        return
    try:
        from .session_guards import session_safe

        if not session_safe():
            cancel_deferred_reward_work("left session")
            return
    except Exception:
        pass
    remaining: List[dict[str, Any]] = []
    now = time.time()
    for seq in list(_pending_serial_delivery_sequences):
        try:
            chunks = list(seq.get("chunks") or [])
            targets = list(seq.get("targets") or [])
            scope_label = str(seq.get("scope_label") or "selected player")
            idx = int(seq.get("index") or 0)
            target_i = int(seq.get("target_i") or 0)
            stage = str(seq.get("stage") or "deliver")

            if idx >= len(chunks):
                _finish_serial_delivery_sequence(seq, chunks, targets, scope_label)
                continue

            if stage == "chunk_open_wait":
                if _reward_open_packages_remaining() > 0:
                    remaining.append(seq)
                    continue
                post_until = float(seq.get("wait_until") or 0.0)
                if post_until <= 0.0:
                    seq["wait_until"] = now + float(_SERIAL_DELIVERY_POST_OPEN_DELAY_SEC or 0.0)
                    remaining.append(seq)
                    continue
                if now < post_until:
                    remaining.append(seq)
                    continue
                seq["chunk_before_counts_by_key"] = _snapshot_identity_package_counts(targets)
                seq["wait_until"] = 0.0
                seq["index"] = idx + 1
                seq["target_i"] = 0
                seq["stage"] = "deliver"
                if idx + 1 >= len(chunks):
                    seq["opened_per_chunk"] = True
                    _finish_serial_delivery_sequence(seq, chunks, targets, scope_label)
                    continue
                remaining.append(seq)
                continue

            if stage in ("post_wait", "wait"):
                if now < float(seq.get("wait_until") or 0.0):
                    remaining.append(seq)
                    continue
                if target_i + 1 < len(targets):
                    seq["target_i"] = target_i + 1
                    seq["stage"] = "deliver"
                else:
                    # Large sends: never open mid-stream — grant all packages first,
                    # then one paced open pass at the end (avoids grant+open AV stacking).
                    open_now = bool(seq.get("open_rewards")) and not bool(
                        seq.get("defer_open_until_end")
                    )
                    if open_now:
                        chunk_before = dict(seq.get("chunk_before_counts_by_key") or {})
                        opened, _open_note = _queue_reward_open_since_for_identities(
                            targets,
                            chunk_before,
                            label=scope_label,
                        )
                        if opened > 0:
                            seq["opened_per_chunk"] = True
                            seq["stage"] = "chunk_open_wait"
                            seq["wait_until"] = 0.0
                            remaining.append(seq)
                            continue
                    seq["chunk_before_counts_by_key"] = _snapshot_identity_package_counts(targets)
                    seq["index"] = idx + 1
                    seq["target_i"] = 0
                    seq["stage"] = "deliver"
                    if idx + 1 >= len(chunks):
                        _finish_serial_delivery_sequence(seq, chunks, targets, scope_label)
                        continue
                remaining.append(seq)
                continue

            if stage != "deliver":
                _set_serial_delivery_status(
                    f"Serial delivery dropped: unknown stage {stage!r}",
                    hold_sec=20.0,
                    log=True,
                )
                continue

            # Never grant on the same tick as a live reward-open (large-send AV class).
            if _reward_open_packages_remaining() > 0:
                remaining.append(seq)
                continue

            chunk = list(chunks[idx])
            if bool(seq.get("level_override")):
                chunk, _lvl_warn = _apply_level_override_to_serials(
                    chunk, int(seq.get("level") or 70)
                )
            identity = targets[target_i]
            tidx = _resolve_serial_target_index(identity)
            if tidx is None:
                _set_serial_delivery_status(
                    f"Serial delivery cancelled: target {getattr(identity, 'display_name', '?')} "
                    "left the lobby or changed identity.",
                    hold_sec=20.0,
                    log=True,
                )
                continue
            _set_serial_delivery_status(
                f"Serial delivery {idx + 1}/{len(chunks)} → player index {tidx}: "
                f"{len(chunk)} serial(s) ({scope_label})",
                hold_sec=20.0,
                log=True,
            )
            ok = _grant_serials_to_player_index(chunk, tidx)
            if not ok:
                if _serial_mail_join_quiet():
                    # Do not burn retries — lobby churn made GiveReward unsafe.
                    seq["stage"] = "post_wait"
                    seq["wait_until"] = time.time() + 0.75
                    remaining.append(seq)
                    continue
                retries = int(seq.get("chunk_retries") or 0) + 1
                seq["chunk_retries"] = retries
                if retries >= _CHUNK_DELIVERY_MAX_RETRIES:
                    _set_serial_delivery_status(
                        f"Serial delivery stopped: package {idx + 1}/{len(chunks)} failed after "
                        f"{retries} retries (player index {tidx}). "
                        f"Delivered {int(seq.get('delivered_serials') or 0)}/{int(seq.get('total_serials') or 0)} serial(s).",
                        hold_sec=30.0,
                        log=True,
                    )
                    continue
                backoff = min(1.15, 0.12 * retries)
                _set_serial_delivery_status(
                    f"Serial delivery retry {retries}/{_CHUNK_DELIVERY_MAX_RETRIES} for package "
                    f"{idx + 1}/{len(chunks)} ({len(chunk)} serial(s))…",
                    hold_sec=20.0,
                    log=True,
                )
                seq["stage"] = "post_wait"
                seq["wait_until"] = time.time() + backoff
                remaining.append(seq)
                continue
            seq["chunk_retries"] = 0
            seq["delivered_serials"] = int(seq.get("delivered_serials") or 0) + len(chunk)
            total_serials = int(seq.get("total_serials") or 0)
            gap = _delivery_chunk_gap(
                len(chunk) if isinstance(chunk, (list, tuple)) else 1,
                total_serials,
                package_index=idx + 1,
            )
            seq["stage"] = "post_wait"
            seq["wait_until"] = time.time() + max(0.0, gap)
            remaining.append(seq)
        except Exception as exc:
            _set_serial_delivery_status(
                f"Serial delivery sequence tick failed: {exc!r}",
                hold_sec=20.0,
                log=True,
            )
    _pending_serial_delivery_sequences[:] = remaining


def _do_give_serial_to_player_indices(
    serials: List[str],
    player_indices: List[int],
    *,
    scope_label: str = "selected players",
    open_rewards: bool = False,
    level_override: bool = False,
    level: int = 70,
) -> int:
    """
    Targeted serial delivery to the given player indices only.

    Default: tick-driven queue using Item Serial ``target_player_index`` (no lobby mail).
    ``SQU1GGS_SERIAL_SYNC_DELIVERY=1`` forces a blocking loop (still targeted — never AllPlayers).
    Returns how many players were queued/targeted.
    """
    if _serial_delivery_sync_preferred():
        work = list(serials)
        if level_override:
            work, _warn = _apply_level_override_to_serials(work, level)
        _do_give_serial_to_player_indices_sync(
            work,
            player_indices,
            scope_label=scope_label,
            open_rewards=open_rewards,
        )
        try:
            return len({int(x) for x in player_indices})
        except Exception:
            return len(player_indices or [])
    return int(
        _queue_serial_delivery_sequence(
            serials,
            player_indices,
            scope_label=scope_label,
            open_rewards=open_rewards,
            level_override=level_override,
            level=level,
        )
        or 0
    )


def _do_give_serial_to_player_indices_sync(
    serials: List[str],
    player_indices: List[int],
    *,
    scope_label: str = "selected players",
    open_rewards: bool = False,
) -> None:
    """Blocking targeted delivery (debug). Prefer the tick queue."""
    if not serials:
        _log_error("No serial strings after parsing (comma-separated non-empty segments).")
        return
    targets: List[int] = []
    seen: set[int] = set()
    for idx in player_indices:
        try:
            i = int(idx)
        except Exception:
            continue
        if i in seen:
            continue
        seen.add(i)
        targets.append(i)
    if not targets:
        _log_error("Give_Serial: no target player indices.")
        return
    target_identities: List[Any] = []
    for target_index in targets:
        try:
            target_identities.append(_snapshot_serial_target_identity(target_index))
        except Exception as exc:
            _log_error(f"Give_Serial: could not snapshot stable identity for index {target_index}: {exc}")
            return

    chunks = _chunk_serials_for_delivery(serials)
    if not chunks:
        _log_error("No serial strings after delivery chunking.")
        return

    try:
        _pending_serial_delivery_sequences.clear()
    except Exception:
        pass

    _ensure_backpack_capacity_for_indices(targets, len(serials))
    _gbc_run_session_timer_from_give_serial()
    before_counts = _snapshot_identity_package_counts(target_identities)
    _set_serial_delivery_status(
        f"Sync targeted delivery: {len(chunks)} package(s) → {len(targets)} player(s) ({scope_label})",
        hold_sec=30.0,
        log=True,
    )
    gap = float(_SERIAL_DELIVERY_POST_OPEN_DELAY_SEC or 0.05)
    for chunk_index, chunk in enumerate(chunks, 1):
        for identity in target_identities:
            tidx = _resolve_serial_target_index(identity)
            if tidx is None:
                _set_serial_delivery_status(
                    f"Sync delivery cancelled: target {getattr(identity, 'display_name', '?')} "
                    "left the lobby or changed identity.",
                    hold_sec=20.0,
                    log=True,
                )
                return
            _set_serial_delivery_status(
                f"Sync delivery {chunk_index}/{len(chunks)} → index {tidx}",
                hold_sec=15.0,
                log=True,
            )
            if not _grant_serials_to_player_index(chunk, int(tidx)):
                _set_serial_delivery_status(
                    f"Sync delivery stopped on package {chunk_index} (index {tidx}).",
                    hold_sec=20.0,
                    log=True,
                )
                return
            if gap > 0:
                time.sleep(min(gap, 0.25))
    opened_note = ""
    if open_rewards:
        opened, open_note = _queue_reward_open_since_for_identities(
            target_identities,
            before_counts,
            label=scope_label,
        )
        opened_note = open_note if opened > 0 else " No new reward packages to open."
    _set_serial_delivery_status(
        f"Sync delivery complete for {scope_label} ({len(chunks)} package(s)).{opened_note}",
        hold_sec=20.0,
        log=True,
    )


def _all_party_player_indices_for_serial_delivery() -> List[int]:
    try:
        _world, gs = _gbc_session_world_and_gamestate()
        pa = getattr(gs, "PlayerArray", None) if gs is not None else None
        if pa is None:
            return []
        return [i for i in range(len(pa))]
    except Exception:
        return []


def _do_give_serial(
    serials: List[str],
    all_players: bool,
    *,
    serial_only_player_index: Optional[int] = None,
) -> bool:
    """Standalone Item Serial reward path with optional precise party targeting."""
    return bool(
        _do_give_serial_chunk(
            serials,
            all_players,
            serial_only_player_index=serial_only_player_index,
        )
    )

def _do_give_serial_chunk(
    serials: List[str],
    all_players: bool,
    *,
    serial_only_player_index: Optional[int] = None,
) -> bool:
    global _loyalty_rotation_index
    if not serials:
        _log_error("No serial strings after parsing (comma-separated non-empty segments).")
        return False

    _gbc_run_session_timer_from_give_serial()

    n = len(LOYALTY_REWARD_DEF_NAMES)
    if n:
        reward_name = LOYALTY_REWARD_DEF_NAMES[_loyalty_rotation_index % n]
        slot = _loyalty_rotation_index % n + 1
        _log_info(f"Loyalty rotation: using {reward_name} ({slot}/{n}).")
    else:
        reward_name = DEFAULT_REWARD_DEF_NAME
        _log_info(f"Loyalty rotation list empty; using default {reward_name}.")

    local_pc = get_pc()
    target_pc = None
    target_indices: List[int] = []
    if serial_only_player_index is not None:
        target_index = int(serial_only_player_index)
        target_pc = _pc_for_player_index(target_index)
        if target_pc is None:
            _log_error(f"Give_Serial: no live PlayerController for player index {serial_only_player_index}.")
            return False
        target_indices = [target_index]
    elif all_players:
        target_indices = _all_party_player_indices_for_serial_delivery()
    else:
        local_ps = getattr(local_pc, "PlayerState", None) if local_pc is not None else None
        for candidate_index in _all_party_player_indices_for_serial_delivery():
            candidate_pc = _pc_for_player_index(candidate_index)
            candidate_ps = getattr(candidate_pc, "PlayerState", None) if candidate_pc is not None else None
            if candidate_pc is local_pc or (local_ps is not None and candidate_ps is local_ps):
                target_indices = [candidate_index]
                break

    captured_managers: List[Tuple[Any, int]] = []
    captured_manager_ids: set[int] = set()
    for target_index in target_indices:
        captured_pc = (
            target_pc
            if serial_only_player_index is not None and target_index == int(serial_only_player_index)
            else _pc_for_player_index(target_index)
        )
        manager, _manager_attr = _find_rewards_manager_on_pc(captured_pc)
        if manager is None:
            _log_error(
                f"Give_Serial: no rewards manager for player index {target_index}; "
                "refusing an unverified grant."
            )
            return False
        manager_id = id(manager)
        if manager_id in captured_manager_ids:
            _log_error(
                f"Give_Serial: player index {target_index} resolved to a duplicate rewards manager; "
                "refusing an ambiguous grant."
            )
            return False
        captured_manager_ids.add(manager_id)
        captured_managers.append((manager, _package_count(manager)))
    if serial_only_player_index is not None and len(captured_managers) != 1:
        _log_error(
            f"Give_Serial: no rewards manager snapshot for player index {serial_only_player_index}; "
            "refusing an unverified targeted grant."
        )
        return False
    if all_players:
        if not target_indices or len(captured_managers) != len(target_indices):
            _log_error(
                "Give_Serial all: could not capture one distinct rewards manager per target; "
                "refusing an unverified lobby grant."
            )
            return False
    local_mgr, _local_mgr_attr = _find_rewards_manager_on_pc(get_pc())
    local_before_count = _package_count(local_mgr) if local_mgr is not None else 0

    if not _give_reward_def(
        reward_name,
        bool(all_players and serial_only_player_index is None),
        target_pc=target_pc,
    ):
        return False

    if n:
        _loyalty_rotation_index = (_loyalty_rotation_index + 1) % n

    def _patch_captured_managers() -> Tuple[int, int]:
        patched = 0
        for manager, before_count in captured_managers:
            if _patch_manager_package_since(
                manager,
                serials,
                before_count,
                expected_reward=reward_name,
            ):
                patched += 1
        return patched, len(captured_managers)

    if serial_only_player_index is not None:
        scope = f"player index {serial_only_player_index} only"
        patch_fn = _patch_captured_managers
    elif all_players:
        scope = "all players"
        patch_fn = _patch_captured_managers
    else:
        scope = "local player"

        def patch_fn() -> Tuple[int, int]:
            if captured_managers:
                return _patch_captured_managers()
            if local_mgr is None:
                return (0, 0)
            return (
                (1, 1)
                if _patch_manager_package_since(
                    local_mgr,
                    serials,
                    local_before_count,
                    expected_reward=reward_name,
                )
                else (0, 1)
            )

    # Never sleep on the game thread — a failed patch returns False and the tick
    # queue retries with backoff (sleep here was hitching / AV'ing ~500 sends).
    patched, total = patch_fn()
    if total > 0 and patched == total:
        if serial_only_player_index is not None:
            _log_info(
                f"Serials applied to last package for player index {serial_only_player_index} "
                f"({scope})."
            )
        else:
            _log_info(
                f"Serials applied to last package on {patched} / {total} GbxRewardsManager instance(s) "
                f"({scope})."
            )
        return True

    _log_error(
        "Serial override failed: no newly created target package could be verified. "
        "The delivery was not reported as successful."
    )
    return False


@command(
    "Give_Serial",
    description=(
        "Grant a reward mail package via bl4_reward_generator, patch SerialNumbers with your @U code(s). "
        "Base85 @U… tokens may be comma-separated. Deserialized human lines use HTTP serialize when enabled. "
        "Usage: Give_Serial serial … | Give_Serial … all | Give_Serial … index N all | "
        "Give_Serial … name <substring> all"
    ),
)
def _cmd_give_serial(args: argparse.Namespace) -> None:
    parts: List[str] = list(getattr(args, "parts", None) or [])
    all_players = False
    if parts and parts[-1].lower() == "all":
        all_players = True
        parts = parts[:-1]
    serial_only_index: Optional[int] = None
    name_i: Optional[int] = None
    for i, tok in enumerate(parts):
        if tok.lower() == "name":
            name_i = i
            break
    if name_i is not None:
        name_sub = " ".join(parts[name_i + 1:]).strip()
        parts = parts[:name_i]
        if not name_sub:
            _log_error("Give_Serial: name keyword requires a substring after it (example: … name Dunkie all).")
            return
        _, gs = _gbc_session_world_and_gamestate()
        if gs is None:
            _log_error("Give_Serial: no GameState (cannot resolve name).")
            return
        idx, err = _gbc_resolve_player_index_for_name_substring(gs, name_sub)
        if err:
            _log_error(f"Give_Serial: {err}")
            return
        serial_only_index = idx
    elif len(parts) >= 2 and parts[-2].lower() == "index":
        idx_val = _safe_int(parts[-1])
        if idx_val is None:
            _log_error("Give_Serial: expected integer after index (example: … index 2 all).")
            return
        serial_only_index = idx_val
        parts = parts[:-2]
    if serial_only_index is not None:
        # Trailing `all` is legacy CLI sugar; grants are always single-target GiveReward.
        all_players = False
    if not parts:
        _log_error(
            "Usage: Give_Serial <serial>[,serial…] [index N|name <substring>] [all] — "
            "index/name send to that player only (never lobby-wide mail). "
            "Deserialized human serials: wrap each line in double quotes (shlex); requires network serialize."
        )
        return
    expanded: List[str] = []
    for p in parts:
        expanded.extend(_expand_serial_token(p))
    if not expanded:
        _log_error("No serial strings after parsing (use commas between Base85 serials or quoted human lines).")
        return
    serials = _resolve_give_serial_strings(expanded)
    if serials is None:
        return
    if not serials:
        _log_error("No serial strings after resolving (empty list).")
        return
    _do_give_serial(serials, all_players, serial_only_player_index=serial_only_index)


_cmd_give_serial.add_argument(
    "parts",
    nargs="+",
    help="Base85 serial(s) and/or quoted deserialized line(s); optional … index N all or … name substring all",
)


def grant_serials_via_loyalty_rewards(
    serials: List[str],
    *,
    all_players: bool = False,
    auto_open: bool = False,
    diagnostic_entry: Optional[dict[str, str]] = None,
    diagnostic_level: int = 60,
) -> int:
    """Grant @U serials through loyalty rewards; optionally queue a verified local claim."""
    cleaned = [s.strip() for s in serials if isinstance(s, str) and s.strip().startswith("@U")]
    if not cleaned:
        return 0
    local_mgr = None
    before_count = -1
    if auto_open and not all_players:
        local_mgr, _manager_attr = _find_rewards_manager_on_pc(get_pc())
        if local_mgr is not None:
            before_count = _package_count(local_mgr)

    if not _do_give_serial(cleaned, all_players):
        return 0

    if auto_open and not all_players:
        queued = False
        if local_mgr is not None and before_count >= 0:
            try:
                packages = getattr(local_mgr, "packages", None)
                package_count = len(packages) if packages is not None else 0
            except Exception:
                package_count = 0
            if package_count > before_count:
                # Do not call Server_OpenPackage on this frame.  A successful
                # Python return is not evidence that the replicated package was
                # consumed or that an inventory item appeared.
                _queue_exact_package_claim(
                    local_mgr,
                    cleaned,
                    before_count,
                    diagnostic_entry=diagnostic_entry,
                    diagnostic_level=diagnostic_level,
                )
                queued = True
        if not queued:
            _log_warning(
                "Exact serial package is verified in the Reward Center but could not be "
                "queued for an automatic verified claim; open it manually in-game."
            )
    return len(cleaned)
