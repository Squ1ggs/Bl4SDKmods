"""Host-side auto lobby loop — paced boosts that remember between sessions.

Runs on the game thread in small steps so the host does not freeze the lobby.
Heavy jobs (challenges / UVHM) and light boosts (MAX ALL / bank / cosmetics)
start at most once per enable unless you turn Repeat heavy jobs on.

Drop All Shinies (phosphene pools) runs first when enabled. Optional mail drip
and per-guest kick timers run after the boost cycle finishes.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from unrealsdk import logging

_PREFIX = "[Squ1ggsBoostingTools | AutoLobby]"
# Keep cycles calm — stacking challenges + mail + shinies too tightly has crashed hosts.
_MIN_INTERVAL_SEC = 30.0
_DEFAULT_INTERVAL_SEC = 90.0
_STEP_GAP_SEC = 1.5
_HEAVY_STEP_GAP_SEC = 4.0
_MIN_DRIP_SEC = 60.0
_MIN_KICK_SEC = 30.0
_MAX_DRIP_COUNT = 200
_DEFAULT_DRIP_COUNT = 150
_DEFAULT_DRIP_GUNS = 100
# Jobs that need a longer gap / rest after finish (missing this used to skip the cycle rest).
_HEAVY_JOBS = frozenset({"missions", "challenges", "uvhm", "drop_shinies"})
# Wait after guest has a live pawn before Max All / mail (character-select lag).
_GUEST_READY_SETTLE_SEC = 12.0
_GUEST_SAVE_DATA_WAIT_CAP_SEC = 30.0
_DRIP_SHAPE_SAFE = frozenset()  # filled lazily from loot_shapes
_DRIP_SHAPE_PIN_CAP = 180


def _drip_shape_allowed() -> frozenset[str]:
    """Auto Lobby into-shape: flat 2D only (GitHub-era lobby-safe set)."""
    global _DRIP_SHAPE_SAFE
    if _DRIP_SHAPE_SAFE:
        return _DRIP_SHAPE_SAFE
    try:
        from .loot_shapes import SHAPE_2D_NAMES

        allowed = {str(n).strip().lower() for n in SHAPE_2D_NAMES if str(n).strip()}
    except Exception:
        allowed = {
            "circle",
            "spiral",
            "rings",
            "double_ring",
            "smiley",
            "skyfall",
            "grid",
            "star",
            "heart",
        }
    allowed.add("none")
    _DRIP_SHAPE_SAFE = frozenset(allowed)
    return _DRIP_SHAPE_SAFE


def _normalize_drip_shape(raw: Any) -> str:
    shape = str(raw or "none").strip().lower()
    if shape in ("", "off", "no", "vanilla", "feet", "pile"):
        return "none"
    if shape == "text":
        return "none"
    # Legacy Auto configs may still have house / 3D — fold to feet pile.
    if shape not in _drip_shape_allowed():
        return "none"
    return shape


def _drip_shape_settle(shape: str) -> str:
    if shape == "none":
        return "none"
    if shape == "skyfall":
        return "rain"
    # 2D Auto shapes: snap onto slots (held silhouette guests can Use).
    return "snap"

_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "interval_sec": _DEFAULT_INTERVAL_SEC,
    "max_all": True,
    "cosmetics": True,
    "missions": False,
    "missions_redo_completed": False,
    "challenges": False,
    "uvhm": True,
    # Progression only: exclude host, wait for guests, process each seen guest once.
    "progression_guests_only": True,
    "bank_space": False,
    "backpack_size": 500,
    "bank_size": 500,
    "drop_shinies": False,
    "repeat_heavy": False,
    # Keep guests from yanking host to title / lobby while Auto Lobby runs.
    "block_menu_pull": True,
    # Arm SHiFT friend-request autoaccept while Auto Lobby runs (same as Home sticky).
    "shift_autoaccept": False,
    # Seconds between SHiFT friends-UI Open cycles while Auto Lobby has AA armed.
    "shift_autoaccept_interval_sec": 25.0,
    # Mail drip between cycles: codes → host mail → open → spill backpack on the ground
    # so the whole lobby can loot (Boost target All / any — ground pile is shared).
    "item_drip": False,
    # How to deliver: drop on ground (host spill) | mail to guests | both.
    "item_drip_deliver": "drop",  # drop | mail | both
    # When mailing: also send a copy to the host (default off — guests only).
    "item_drip_include_host": False,
    "item_drip_mode": "random_gzo",  # random_gzo | pack
    "item_drip_listing": "Modded",  # Legit | Modded | All
    "item_drip_pack": "",
    # Guest-mail Item list (copy only). Used when deliver is mail/both; blank falls back to drop list / GZO.
    "item_drip_mail_pack": "",
    "item_drip_count": _DEFAULT_DRIP_COUNT,
    "item_drip_level": 50,
    "item_drip_interval_sec": 120,
    # none = soft lobby feet pile; otherwise held silhouette guests can Use.
    "item_drip_shape": "none",
    # Timed Clear world loot (shapes + ground) for the whole lobby.
    "loot_cleanup": False,
    "loot_cleanup_interval_sec": 300,
    # After a full cycle, kick each guest once (fair timer).
    "auto_kick": False,
    # ON = only kick guests who were present for a complete start→finish cycle (recommended).
    "kick_after_full_run_only": True,
    "kick_delay_sec": 180,
    "kick_drop_bonus_sec": 240,
    # Shorter kick wait when this run mailed serials (Reward Center — no ground loot time).
    "kick_mail_delay_sec": 90,
    # Persist SHiFT / platform names that Auto kick must never remove.
    "kick_exempt_names": [],
}

_JOB_LABELS: dict[str, str] = {
    "max_all": "MAX ALL",
    "bank_space": "Bank / backpack",
    "cosmetics": "Cosmetics",
    "missions": "All missions",
    "challenges": "Challenges (non-UVHM)",
    "uvhm": "UVHM progression",
    "drop_shinies": "Drop All Shinies",
    "item_drip": "Auto items",
    "item_mail": "Mail serials",
}

_BOOL_KEYS = (
    "enabled",
    "max_all",
    "cosmetics",
    "missions",
    "missions_redo_completed",
    "challenges",
    "uvhm",
    "progression_guests_only",
    "bank_space",
    "drop_shinies",
    "repeat_heavy",
    "block_menu_pull",
    "shift_autoaccept",
    "item_drip",
    "item_drip_include_host",
    "loot_cleanup",
    "auto_kick",
    "kick_after_full_run_only",
)

# True when Auto Lobby turned SHiFT autoaccept on (so stop does not wipe Home sticky).
_shift_aa_armed_by_auto = False
# User turned Home sticky OFF while Auto Lobby still wanted AA — do not re-arm until Auto stops.
_shift_aa_user_disabled = False

_cfg: dict[str, Any] = dict(_DEFAULTS)
_loaded = False
_next_cycle_at = 0.0
_queue: list[str] = []
_step_at = 0.0
_last_msg = "Idle."
_heavy_done: set[str] = set()
_log_at = 0.0
_current_job: str = ""
_watching_job: str = ""
_cycle_total: int = 0
_cycle_done: int = 0
_guest_progress_done: dict[str, set[str]] = {}
# Last MAX ALL / cosmetics burst per guest — UVHM waits a moment after it.
_guest_boost_at: dict[str, float] = {}
_UVHM_AFTER_BOOST_SEC = 10.0
# Character-name keys seen this Auto session — new key = leave/rejoin on another char.
_seen_guest_keys: set[str] = set()
_next_drip_at = 0.0
_session_dropped_items = False
_session_mailed_items = False
_kick_at: dict[int, float] = {}
_kick_armed_indices: set[int] = set()
_cycle_finished_once = False
_cycle_start_guest_indices: set[int] = set()
_guests_earned_kick: set[int] = set()
# Character keys already mailed this join — leave/rejoin clears via roster note.
_mailed_guest_keys: set[str] = set()
_host_mailed_session = False
# key -> monotonic when guest first had a live world pawn this join.
_guest_ready_since: dict[str, float] = {}
_drip_phase = ""  # "" | "wait_mail" | "drop"
_drip_drop_at = 0.0
_drip_last_count = 0
_drip_drop_rounds = 0
_drip_last_remaining = -1
_drip_stalled_rounds = 0
_join_pause_log_at = 0.0
_drip_pending_guest_mail: list[str] = []
_drip_guest_mail_started = False
_MAX_DRIP_DROP_ROUNDS = 24  # Soft lobby spills ~10/pass; 150-bag needs more paced rounds.
_next_loot_cleanup_at = 0.0
_last_party_n: int = 0
_idle_msg_at = 0.0
# True when _run_step put the job back (character not ready / busy) — do not advance cycle.
_step_deferred = False


def _settings_path() -> Path:
    docs = Path.home() / "Documents" / "My Games" / "Borderlands 4" / "Saved"
    return docs / "Squ1ggsBoostingTools_auto_lobby.json"


def _clamp_interval(raw: Any) -> float:
    try:
        value = float(raw)
    except Exception:
        value = _DEFAULT_INTERVAL_SEC
    return max(_MIN_INTERVAL_SEC, min(3600.0, value))


def _clamp_drip_interval(raw: Any) -> float:
    try:
        value = float(raw)
    except Exception:
        value = 120.0
    return max(_MIN_DRIP_SEC, min(3600.0, value))


def _serial_delivery_busy() -> bool:
    try:
        from .serial_rewards import serial_delivery_progress

        prog = serial_delivery_progress()
        if isinstance(prog, dict) and (prog.get("active") or prog.get("queued") or prog.get("finishing")):
            return True
    except Exception:
        pass
    return False


def _lobby_join_quiet() -> bool:
    """True while a guest is joining/leaving — pause drip spill + boost steps.

    Reuses the existing serial join-quiet window (and loot-shape quiet if armed).
    Does not touch hold/bridge peers.
    """
    try:
        from .serial_rewards import _serial_mail_join_quiet

        if _serial_mail_join_quiet():
            return True
    except Exception:
        pass
    try:
        from .loot_shapes import _in_join_quiet

        if _in_join_quiet():
            return True
    except Exception:
        pass
    return False


def _pick_pack_serials(pack_name: str, count: int) -> list[str]:
    """Return a shallow copy of @U codes from an Item list — never removes or mutates the store."""
    pack = str(pack_name or "").strip()
    need = max(1, min(_MAX_DRIP_COUNT, int(count) or 1))
    try:
        from . import serial_store

        rows = serial_store.filter_entries(group=pack or "All")
        # Case-insensitive group match when catalog id casing differs.
        if not rows and pack and pack.casefold() != "all":
            for g in serial_store.groups() or []:
                if str(g).strip().casefold() == pack.casefold():
                    rows = serial_store.filter_entries(group=str(g).strip())
                    pack = str(g).strip()
                    break
    except Exception as exc:
        _log(f"Item list read failed ({pack or 'All'}): {exc!r}")
        return []
    # Copy strings only — drip must not delete/move entries out of Item lists.
    serials = [
        str(r.get("serial") or "").strip()
        for r in list(rows)
        if str(r.get("serial") or "").strip()
    ]
    if not serials:
        return []
    pool = list(serials)
    random.shuffle(pool)
    picked = pool[:need]
    _log(
        f"Auto-drop copied {len(picked)} code(s) from Item list "
        f"“{pack or 'All'}” ({len(serials)} in list — list unchanged)."
    )
    return picked


def _pick_drip_serials() -> list[str]:
    count = int(_cfg.get("item_drip_count") or _DEFAULT_DRIP_COUNT)
    mode = str(_cfg.get("item_drip_mode") or "random_gzo").lower()
    pack = str(_cfg.get("item_drip_pack") or "").strip()
    # Named drop list wins (Both mode: type DROP list even if source still says GZO).
    if mode == "pack" or pack:
        return _pick_pack_serials(pack, count)

    listing = str(_cfg.get("item_drip_listing") or "Modded")
    fetch_limit = max(800, int(count) * 4)
    try:
        from .bridge_catalog import catalog_gzo

        result = catalog_gzo({"listing": listing, "limit": fetch_limit, "search": ""})
    except Exception as exc:
        _log(f"Drip GZO read failed: {exc!r}")
        return []
    rows = [r for r in list(result.get("rows") or []) if isinstance(r, dict)]
    if not rows:
        return []

    def _serial(row: dict[str, Any]) -> str:
        return str(row.get("serial") or "").strip()

    weapons = [
        r
        for r in rows
        if _serial(r) and str(r.get("category") or "") == "Weapons"
    ]
    gear = [
        r
        for r in rows
        if _serial(r)
        and str(r.get("category") or "")
        in ("Class Mods", "Shields", "Enhancements", "Repkits")
    ]
    # Lobby pile default mix: ~100 guns + classmods/repkits/enhancements/shields.
    if count >= _DEFAULT_DRIP_GUNS:
        gun_n = min(_DEFAULT_DRIP_GUNS, count, len(weapons) or count)
    else:
        gun_n = min(count, max(1, (count * 2) // 3), len(weapons) or count)
    gear_n = max(0, count - gun_n)
    if not weapons and gear:
        gun_n = 0
        gear_n = count
    elif weapons and not gear:
        gun_n = min(count, len(weapons))
        gear_n = 0

    random.shuffle(weapons)
    random.shuffle(gear)
    picked: list[str] = []
    seen: set[str] = set()

    def _take(pool: list[dict[str, Any]], need: int) -> None:
        for row in pool:
            if len(picked) >= count or need <= 0:
                return
            serial = _serial(row)
            if not serial or serial in seen:
                continue
            seen.add(serial)
            picked.append(serial)
            need -= 1

    _take(weapons, gun_n)
    _take(gear, max(0, count - len(picked)))
    if len(picked) < count:
        leftover = [r for r in rows if _serial(r) and _serial(r) not in seen]
        random.shuffle(leftover)
        _take(leftover, count - len(picked))
    return picked[:count]


def _drip_deliver_mode() -> str:
    raw = str(_cfg.get("item_drip_deliver") or "drop").strip().lower()
    if raw in ("mail", "mail_only", "guests", "guest_mail"):
        return "mail"
    if raw in ("both", "drop_and_mail", "mail_and_drop", "all"):
        return "both"
    return "drop"


def _pick_mail_serials() -> list[str]:
    """Codes for guest mail — prefer mail list, else drop list / GZO. Always a copy."""
    count = int(_cfg.get("item_drip_count") or _DEFAULT_DRIP_COUNT)
    mail_pack = str(_cfg.get("item_drip_mail_pack") or "").strip()
    if mail_pack:
        return _pick_pack_serials(mail_pack, count)
    mode = str(_cfg.get("item_drip_mode") or "random_gzo").lower()
    if mode == "pack":
        return _pick_pack_serials(str(_cfg.get("item_drip_pack") or ""), count)
    return _pick_drip_serials()


def _shift_ui_busy() -> bool:
    """True while SHiFT friends overlay is held open for autoaccept."""
    try:
        from . import shift_friend_autoaccept as shift_aa

        st = shift_aa.status()
        return bool(st.get("ui_open") or st.get("oneshot_active"))
    except Exception:
        return False


def _run_item_drip() -> None:
    """Ground-drop path only (mail is once-per-join via item_mail jobs).

    Drop = codes → host mail → open → spill backpack. Guest mail is queued from
    the boost cycle as item_mail@guest so it never spams the host when alone.
    """
    global _session_dropped_items, _drip_phase, _drip_drop_at, _drip_last_count
    global _drip_last_remaining, _drip_stalled_rounds
    global _drip_pending_guest_mail, _drip_guest_mail_started
    if not _drop_enabled():
        return
    if _shift_ui_busy():
        _set_msg("Auto-drop waiting — SHiFT friends UI open (autoaccept cycle).")
        return
    if _lobby_join_quiet():
        _set_msg("Auto items waiting — guest joining/leaving; will start after lobby settles.")
        return
    if _drip_phase:
        _set_msg("Auto items already in progress (mail → open → drop pack).")
        return
    if _serial_delivery_busy():
        _set_msg("Auto items waiting — a mail send is already in progress.")
        return

    from .bridge_actions_extended import deliver_serials

    _drip_pending_guest_mail = []
    _drip_guest_mail_started = False

    drop_serials = _pick_drip_serials()
    if not drop_serials:
        mode = str(_cfg.get("item_drip_mode") or "random_gzo").lower()
        if mode == "pack" or str(_cfg.get("item_drip_pack") or "").strip():
            _set_msg("Auto-drop — no serials in that Item list (copies only; list unchanged).")
        else:
            _set_msg(
                "Auto-drop — no GZO codes cached (Serials → GZO / Lootlemon → Refresh GZO)."
            )
        return

    shape = _normalize_drip_shape(_cfg.get("item_drip_shape"))
    if shape != "none" and len(drop_serials) > _DRIP_SHAPE_PIN_CAP:
        drop_serials = drop_serials[:_DRIP_SHAPE_PIN_CAP]
    host_idx = _host_player_index()
    result = deliver_serials(
        {
            "serials": drop_serials,
            "count": 1,
            "level_override": "yes",
            "level": int(_cfg.get("item_drip_level") or 50),
            "mode": "player",
            "player_index": host_idx,
            "open_rewards": True,
        }
    )
    ok = bool(result.get("ok", True))
    if not ok:
        _set_msg(str(result.get("message") or "Auto-drop mail failed."))
        return
    _drip_last_count = len(drop_serials)
    _drip_phase = "wait_mail"
    _drip_drop_at = 0.0
    _drip_drop_rounds = 0
    _drip_last_remaining = -1
    _drip_stalled_rounds = 0
    _session_dropped_items = True
    shape_note = f" → {shape} shape" if shape != "none" else " → ground pile"
    _set_msg(
        f"Auto-drop: mailing {_drip_last_count} code(s) to you (host), opening, then "
        f"dropping backpack{shape_note} for guests to loot."
    )


def _host_player_index() -> int:
    try:
        from .party_helpers import _list_party_players

        for row in _list_party_players() or []:
            if not isinstance(row, dict):
                continue
            if bool(row.get("is_host")):
                return int(row.get("index") or 0)
    except Exception:
        pass
    return 0


def _tick_drip_followup(now: float) -> None:
    """After mail+open finishes, spill host backpack (retry until empty / capped)."""
    global _drip_phase, _drip_drop_at, _session_dropped_items, _drip_drop_rounds
    global _drip_last_remaining, _drip_stalled_rounds, _next_drip_at
    global _drip_pending_guest_mail, _drip_guest_mail_started
    if _drip_phase not in ("wait_mail", "drop"):
        return
    if _lobby_join_quiet():
        if _drip_phase == "drop" or (_drip_phase == "wait_mail" and not _serial_delivery_busy()):
            _drip_drop_at = max(float(_drip_drop_at or 0.0), now + 1.5)
            # Rate-limit — was flooding the log every tick during join quiet.
            global _join_pause_log_at
            if now - float(_join_pause_log_at or 0.0) >= 4.0:
                _join_pause_log_at = now
                _set_msg(
                    "Auto-drop: pausing backpack drop while a guest joins/leaves — "
                    "will resume after lobby settles."
                )
        return
    if _drip_phase == "wait_mail":
        if _serial_delivery_busy():
            return
        if _drip_drop_at <= 0:
            settle = max(2.5, min(40.0, 2.0 + float(_drip_last_count) * 0.12))
            _drip_drop_at = now + settle
            _set_msg(
                f"Auto-drop: mail/open done ({_drip_last_count}) — "
                f"dropping backpack in {int(settle)}s…"
            )
            return
        if now < _drip_drop_at:
            return
        _drip_phase = "drop"
        _drip_drop_rounds = 0
    if _drip_phase != "drop":
        return
    if _drip_drop_at > 0 and now < _drip_drop_at:
        return
    from .bridge_actions_extended import faafo_drop_backpack

    host_idx = _host_player_index()
    shape = _normalize_drip_shape(_cfg.get("item_drip_shape"))
    settle = _drip_shape_settle(shape)
    try:
        payload: dict[str, Any] = {
            "player_index": host_idx,
            "shape": shape,
            "settle": settle,
            "land_profile": "shiny",
            "soft_lobby": True,
            "soft_lobby_spread": shape == "none",
        }
        if shape != "none":
            # Sep 23 "perfect! nearly" path (3.11.7): held silhouette + pickup-safe
            # ForceNet + Use→backpack (not Stay-off Attract — that regressed grab).
            payload["stay_in_air"] = "yes"
            payload["spawn_then_shape"] = "no"
            payload["fill_until_complete"] = "no"
            # Soft SpillOut + deferred catch (hard settle find_all AVd backpack→shape).
            payload["soft_lobby"] = True
            payload["radius"] = 200
            payload["spacing"] = 72
            payload["drop_height"] = 440 if shape == "skyfall" else 120
            payload["z_bias"] = 18
        result = faafo_drop_backpack(payload)
        ok = bool(result.get("ok", True))
        msg = str(result.get("message") or "Backpack drop finished.")
    except Exception as exc:
        ok = False
        msg = f"Backpack drop failed: {exc!r}"
    _drip_drop_rounds += 1
    lower = msg.lower()
    still_full = "partial" in lower or "remaining=" in lower
    remaining = 0
    if "remaining=" in lower:
        try:
            remaining = int(lower.split("remaining=", 1)[1].split()[0].strip(".,;"))
        except Exception:
            remaining = 1 if still_full else 0
    if remaining > 0:
        if remaining == _drip_last_remaining:
            _drip_stalled_rounds += 1
        else:
            _drip_stalled_rounds = 0
        _drip_last_remaining = remaining
    if ok and (not still_full or remaining <= 0):
        _drip_phase = ""
        _drip_drop_at = 0.0
        _drip_drop_rounds = 0
        _drip_last_remaining = -1
        _drip_stalled_rounds = 0
        _drip_pending_guest_mail = []
        _drip_guest_mail_started = False
        gap = max(_MIN_DRIP_SEC, float(_cfg.get("item_drip_interval_sec") or 120))
        _next_drip_at = now + gap
        _session_dropped_items = True
        _set_msg(
            f"Auto-drop complete: mailed {_drip_last_count} → host pack → "
            f"{'shape' if _normalize_drip_shape(_cfg.get('item_drip_shape')) != 'none' else 'ground'}. "
            f"Next drop in {int(gap)}s (loops while Auto Lobby is on)."
        )
        return
    # Soft → shape: bag remaining can plateau while SpillOut/catch still fills the
    # silhouette (used to stall after 2 identical remaining → 180s wait while timer ran).
    shape_now = _normalize_drip_shape(_cfg.get("item_drip_shape"))
    stall_limit = 8 if shape_now != "none" else 2
    if shape_now != "none":
        try:
            from .loot_shapes import held_pin_count, landing_armed

            if landing_armed() or held_pin_count() > 0:
                # Shape is still catching — do not treat flat remaining as a stall yet.
                stall_limit = max(stall_limit, 12)
        except Exception:
            pass
    if _drip_drop_rounds >= _MAX_DRIP_DROP_ROUNDS or _drip_stalled_rounds >= stall_limit:
        _drip_phase = ""
        _drip_drop_at = 0.0
        _drip_last_remaining = -1
        _drip_stalled_rounds = 0
        _drip_pending_guest_mail = []
        _drip_guest_mail_started = False
        gap = max(_MIN_DRIP_SEC, float(_cfg.get("item_drip_interval_sec") or 120))
        _next_drip_at = now + gap
        _set_msg(
            f"Auto-drop pause: backpack drop stalled after {_drip_drop_rounds} pass(es). "
            f"Next drop in {int(gap)}s (still looping)."
        )
        return
    _drip_drop_at = now + 2.2
    _set_msg(
        f"Auto-drop: dropping backpack pass {_drip_drop_rounds}/{_MAX_DRIP_DROP_ROUNDS}…"
    )


def _run_loot_cleanup() -> None:
    """Clear world loot for the whole lobby (shapes + ground hide)."""
    global _next_loot_cleanup_at
    try:
        from .loot_shapes import cleanup_world_loot

        msg = cleanup_world_loot()
        _set_msg(f"Auto clear world loot: {msg}")
    except Exception as exc:
        _set_msg(f"Auto clear world loot failed: {exc!r}")
    gap = max(60.0, float(_cfg.get("loot_cleanup_interval_sec") or 300))
    _next_loot_cleanup_at = time.monotonic() + gap


def _tick_loot_cleanup(now: float) -> None:
    global _next_loot_cleanup_at
    if not _cfg.get("enabled") or not _cfg.get("loot_cleanup"):
        return
    if _lobby_join_quiet() or _progression_busy() or _drip_phase:
        return
    if _next_loot_cleanup_at <= 0:
        _next_loot_cleanup_at = now + max(60.0, float(_cfg.get("loot_cleanup_interval_sec") or 300))
        return
    if now < _next_loot_cleanup_at:
        return
    _run_loot_cleanup()


def _clamp_kick_sec(raw: Any, default: float) -> float:
    try:
        value = float(raw)
    except Exception:
        value = default
    return max(_MIN_KICK_SEC, min(3600.0, value))


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _log(msg: str) -> None:
    global _log_at
    now = time.monotonic()
    # Rate-limit only the chatty “Waiting on …” heartbeats so step logs (MAX ALL / cosmetics) stay visible.
    if "Waiting on" in str(msg):
        if now - _log_at < 4.0:
            return
    _log_at = now
    logging.info(f"{_PREFIX} {msg}")
    try:
        from . import runtime_log

        runtime_log.note(f"auto_lobby: {msg}")
    except Exception:
        pass


def _normalize_cfg(merged: dict[str, Any]) -> dict[str, Any]:
    merged["interval_sec"] = _clamp_interval(merged.get("interval_sec"))
    for key in _BOOL_KEYS:
        merged[key] = _truthy(merged.get(key), bool(_DEFAULTS[key]))
    try:
        merged["backpack_size"] = max(40, min(2000, int(merged.get("backpack_size") or 500)))
        merged["bank_size"] = max(40, min(2000, int(merged.get("bank_size") or 500)))
    except Exception:
        merged["backpack_size"] = 500
        merged["bank_size"] = 500
    mode = str(merged.get("item_drip_mode") or "random_gzo").strip().lower()
    merged["item_drip_mode"] = "pack" if mode == "pack" else "random_gzo"
    # DROP list selected → always treat as Item-list mode (parity with EXE start).
    if str(merged.get("item_drip_pack") or "").strip():
        merged["item_drip_mode"] = "pack"
    deliver = str(merged.get("item_drip_deliver") or "drop").strip().lower()
    if deliver in ("mail", "mail_only", "guests", "guest_mail"):
        merged["item_drip_deliver"] = "mail"
    elif deliver in ("both", "drop_and_mail", "mail_and_drop", "all"):
        merged["item_drip_deliver"] = "both"
    else:
        merged["item_drip_deliver"] = "drop"
    listing = str(merged.get("item_drip_listing") or "Modded").strip()
    if listing.lower() not in ("legit", "modded", "all"):
        listing = "Modded"
    else:
        listing = listing[:1].upper() + listing[1:].lower()
        if listing.lower() == "all":
            listing = "All"
    merged["item_drip_listing"] = listing
    merged["item_drip_pack"] = str(merged.get("item_drip_pack") or "").strip()
    merged["item_drip_mail_pack"] = str(merged.get("item_drip_mail_pack") or "").strip()
    try:
        count = int(merged.get("item_drip_count") or _DEFAULT_DRIP_COUNT)
    except Exception:
        count = _DEFAULT_DRIP_COUNT
    # Old UI capped at 10 — treat leftover tiny values as the new lobby-pile default.
    if count in (3, 10):
        count = _DEFAULT_DRIP_COUNT
    merged["item_drip_count"] = max(1, min(_MAX_DRIP_COUNT, count))
    try:
        merged["item_drip_level"] = max(1, min(100, int(merged.get("item_drip_level") or 50)))
    except Exception:
        merged["item_drip_level"] = 50
    merged["item_drip_interval_sec"] = _clamp_drip_interval(merged.get("item_drip_interval_sec"))
    merged["item_drip_shape"] = _normalize_drip_shape(merged.get("item_drip_shape"))
    try:
        cu = float(merged.get("loot_cleanup_interval_sec") or 300)
    except Exception:
        cu = 300.0
    merged["loot_cleanup_interval_sec"] = max(60.0, min(3600.0, cu))
    merged["kick_delay_sec"] = _clamp_kick_sec(merged.get("kick_delay_sec"), 180.0)
    merged["kick_drop_bonus_sec"] = _clamp_kick_sec(merged.get("kick_drop_bonus_sec"), 240.0)
    merged["kick_mail_delay_sec"] = _clamp_kick_sec(merged.get("kick_mail_delay_sec"), 90.0)
    try:
        saa = float(merged.get("shift_autoaccept_interval_sec") or 25.0)
    except Exception:
        saa = 25.0
    merged["shift_autoaccept_interval_sec"] = max(8.0, min(180.0, saa))
    merged["kick_exempt_names"] = _normalize_kick_exempt_names(merged.get("kick_exempt_names"))
    return merged


def _normalize_kick_exempt_names(raw: Any) -> list[str]:
    """Unique display names for never-kick list (preserve first casing)."""
    if raw is None:
        return []
    items: list[Any]
    if isinstance(raw, str):
        items = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    elif isinstance(raw, (list, tuple, set)):
        items = list(raw)
    else:
        items = []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        name = str(item or "").strip()
        if not name:
            continue
        key = "".join(ch for ch in name.lower() if ch.isalnum())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(name[:120])
    return out[:64]


def load() -> dict[str, Any]:
    global _cfg, _loaded
    path = _settings_path()
    merged = dict(_DEFAULTS)
    had_enabled = False
    defaults_rev = 0
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key in _DEFAULTS:
                    if key in data:
                        merged[key] = data[key]
                had_enabled = _truthy(data.get("enabled"), False)
                try:
                    defaults_rev = int(data.get("_defaults_rev", 0) or 0)
                except Exception:
                    defaults_rev = 0
    except Exception as exc:
        _log(f"Could not read settings: {exc!r}")
    # 3.10.42 factory flip: non-UVHM challenges off, cosmetics/hover on.
    migrated_defaults = False
    if defaults_rev < 42:
        merged["challenges"] = False
        merged["cosmetics"] = True
        merged["_defaults_rev"] = 42
        migrated_defaults = True
    else:
        merged["_defaults_rev"] = defaults_rev
    _cfg = _normalize_cfg(merged)
    # Never auto-resume after crash / game restart — Start must be explicit.
    if _cfg.get("enabled") or had_enabled:
        _cfg["enabled"] = False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_cfg, indent=2), encoding="utf-8")
            if had_enabled:
                _log("Cleared sticky enabled from last session (press Start to run again).")
        except Exception:
            pass
    elif migrated_defaults:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_cfg, indent=2), encoding="utf-8")
            _log("Applied factory defaults: cosmetics on, non-UVHM challenges off.")
        except Exception:
            pass
    _loaded = True
    return dict(_cfg)


def save(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    global _cfg
    if cfg is not None:
        merged = dict(_DEFAULTS)
        merged.update(cfg)
        _cfg = _normalize_cfg(merged)
    elif not _loaded:
        load()
    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_cfg, indent=2), encoding="utf-8")
    except Exception as exc:
        _log(f"Could not save settings: {exc!r}")
    return dict(_cfg)


def _job_label(job: str) -> str:
    key = str(job or "").strip()
    base, target_idx, guest_key = _job_parts(key)
    label = _JOB_LABELS.get(base, base or "—")
    if guest_key:
        guest = _guest_by_key(guest_key)
        who = str((guest or {}).get("name") or guest_key)
        return f"{label} · {who}"
    return f"{label} · guest {target_idx}" if target_idx is not None else label


def _job_parts(job: str) -> tuple[str, int | None, str | None]:
    """Return (base, player_index, guest_key). Prefer #key so index reshuffles are safe."""
    text = str(job or "").strip()
    if "#" in text:
        base, raw_key = text.split("#", 1)
        key = str(raw_key or "").strip().casefold()
        return base.strip(), None, key or None
    if "@" not in text:
        return text, None, None
    base, raw_idx = text.rsplit("@", 1)
    try:
        return base.strip(), int(raw_idx), None
    except Exception:
        return text, None, None


def _is_heavy_job(job: str) -> bool:
    return _job_parts(job)[0] in _HEAVY_JOBS


def _guest_by_key(key: str) -> dict[str, Any] | None:
    want = str(key or "").strip().casefold()
    if not want:
        return None
    return next((row for row in _guest_targets() if str(row.get("key") or "") == want), None)


def _guest_has_world_pawn(player_index: int) -> bool:
    """True when the guest finished character select and has a live gameplay pawn."""
    return _guest_world_pawn(player_index) is not None


def _guest_world_pawn(player_index: int) -> Any:
    try:
        from .party_helpers import (
            _gbc_find_pc_for_player_state,
            _gbc_session_world_and_gamestate,
            _pc_is_camera_shell,
        )
        from mods_base import get_pc
    except Exception:
        return None
    try:
        world, gs = _gbc_session_world_and_gamestate()
        pa = getattr(gs, "PlayerArray", None) if gs is not None else None
        if pa is None:
            return None
        ps = pa[int(player_index)]
        if ps is None:
            return None
        local_ps = getattr(get_pc(), "PlayerState", None)
        if local_ps is not None and ps is local_ps:
            return None
        pc = _gbc_find_pc_for_player_state(ps, world)
        if pc is None or _pc_is_camera_shell(pc):
            return None
        return getattr(pc, "Pawn", None)
    except Exception:
        return None


def _pawn_save_data_loaded(pawn: Any) -> bool:
    """Pawn can exist before the guest's save replicates (empty SDU pools, level 1)."""
    try:
        from .player_economy import _SDU_POINTS_POOL_INDEX

        mgr = getattr(pawn, "GbxProgressionManager", None)
        container = getattr(mgr, "ProgressPointsContainer", None) if mgr is not None else None
        pools = getattr(container, "PointsAcquiredPerPool", None) if container is not None else None
        return pools is not None and len(pools) > int(_SDU_POINTS_POOL_INDEX)
    except Exception:
        return False


def _guest_is_boost_ready(guest: dict[str, Any] | None) -> bool:
    """Require live pawn + settle time so Max All/mail do not fire mid character-select."""
    if not guest:
        return False
    key = str(guest.get("key") or "")
    try:
        idx = int(guest.get("index"))
    except Exception:
        return False
    if not key:
        return False
    pawn = _guest_world_pawn(idx)
    if pawn is None:
        _guest_ready_since.pop(key, None)
        return False
    now = time.monotonic()
    since = _guest_ready_since.get(key)
    if since is None:
        _guest_ready_since[key] = now
        return False
    elapsed = now - float(since)
    if elapsed < _GUEST_READY_SETTLE_SEC:
        return False
    if _pawn_save_data_loaded(pawn):
        return True
    return elapsed >= _GUEST_READY_SETTLE_SEC + _GUEST_SAVE_DATA_WAIT_CAP_SEC


def _guest_job_token(base: str, guest: dict[str, Any]) -> str:
    return f"{base}#{str(guest.get('key') or '').casefold()}"


def _resolve_step_target(
    job_key: str,
) -> tuple[str, int | None, dict[str, Any] | None, str]:
    """Map a queued job to a live guest. Returns (base, index, guest, status).

    status: ok | waiting | gone | host_mail | lobby
    """
    base, idx, key = _job_parts(job_key)
    if key:
        guest = _guest_by_key(key)
        if guest is None:
            return base, None, None, "gone"
        live_idx = int(guest["index"])
        if not _guest_is_boost_ready(guest):
            return base, live_idx, guest, "waiting"
        return base, live_idx, guest, "ok"
    if idx is not None:
        host_idx = int(_host_player_index())
        if base == "item_mail" and int(idx) == host_idx:
            return base, int(idx), None, "host_mail"
        guest = _guest_target_for_index(int(idx))
        if guest is None:
            return base, int(idx), None, "gone"
        if not _guest_is_boost_ready(guest):
            return base, int(guest["index"]), guest, "waiting"
        return base, int(guest["index"]), guest, "ok"
    return base, None, None, "lobby"


def status() -> dict[str, Any]:
    if not _loaded:
        load()
    enabled = bool(_cfg.get("enabled"))
    queued = list(_queue)
    current = str(_current_job or "")
    if not current and _watching_job and _progression_busy():
        current = str(_watching_job)
    next_in = max(0.0, _next_cycle_at - time.monotonic()) if enabled else 0.0
    drip_in = max(0.0, _next_drip_at - time.monotonic()) if enabled and _cfg.get("item_drip") else 0.0
    cleanup_in = (
        max(0.0, _next_loot_cleanup_at - time.monotonic())
        if enabled and _cfg.get("loot_cleanup") and _next_loot_cleanup_at > 0
        else 0.0
    )
    drip_drop_in = (
        max(0.0, _drip_drop_at - time.monotonic())
        if _drip_phase == "wait_mail" and _drip_drop_at > 0
        else 0.0
    )
    kick_left = []
    now = time.monotonic()
    for idx, deadline in sorted(_kick_at.items()):
        kick_left.append({"player_index": idx, "seconds": max(0.0, deadline - now)})
    guest_watch = bool(
        enabled
        and _cfg.get("progression_guests_only")
        and (
            _cfg.get("challenges")
            or _cfg.get("uvhm")
            or _cfg.get("max_all")
            or _cfg.get("missions")
            or _cfg.get("cosmetics")
            or _cfg.get("bank_space")
            or _mail_enabled()
        )
    )
    guest_targets = _guest_targets() if guest_watch or enabled else []
    guest_runs: list[dict[str, Any]] = []
    required = _required_guest_jobs() if enabled else set()
    req_n = len(required)
    for guest in guest_targets:
        done = _guest_progress_done.get(str(guest.get("key") or ""), set())
        done_n = len(done & required) if required else 0
        guest_runs.append(
            {
                "name": str(guest.get("name") or guest.get("key") or "?"),
                "index": int(guest.get("index") or 0),
                "done": done_n,
                "total": req_n,
                "complete": bool(required) and required.issubset(done),
            }
        )
    if current:
        phase = "running"
        detail = f"Running {_job_label(current)}"
    elif queued:
        phase = "queued"
        detail = f"Next: {_job_label(queued[0])}"
    elif enabled and kick_left:
        phase = "kicking"
        soon = min(kick_left, key=lambda row: row["seconds"])
        detail = f"Kick timers — next in {int(soon['seconds'])}s"
    elif guest_watch:
        phase = "waiting"
        pending = [g["name"] for g in guest_runs if not g.get("complete")]
        if pending:
            detail = f"Finishing: {', '.join(pending[:3])}" + ("…" if len(pending) > 3 else "")
        elif guest_targets:
            detail = f"Watching {len(guest_targets)} guest(s) for new joins"
        else:
            detail = "Host skipped — waiting for guests to join"
    elif enabled:
        phase = "waiting"
        detail = f"Next cycle in {int(next_in)}s"
    else:
        phase = "idle"
        detail = "Off"
    return {
        "config": dict(_cfg),
        "enabled": enabled,
        "active": enabled,
        "queued": queued,
        "queued_labels": [_job_label(j) for j in queued],
        "current_job": current,
        "current_label": _job_label(current) if current else "",
        "next_cycle_in": next_in,
        "next_drip_in": drip_in,
        "next_loot_cleanup_in": cleanup_in,
        "drip_phase": str(_drip_phase or ""),
        "drip_drop_in": drip_drop_in,
        "drip_count": int(_drip_last_count or 0),
        "drip_drop_round": int(_drip_drop_rounds or 0),
        "interval_sec": float(_cfg.get("interval_sec") or _DEFAULT_INTERVAL_SEC),
        "cycle_total": int(_cycle_total),
        "cycle_done": int(_cycle_done),
        "progress_index": int(_cycle_done),
        "progress_total": max(1, int(_cycle_total) or 1) if enabled else 0,
        "phase": phase,
        "message": _last_msg,
        "detail": detail,
        "last": _last_msg,
        "heavy_done": sorted(_heavy_done),
        "kick_timers": kick_left,
        "progression_guests_only": bool(_cfg.get("progression_guests_only")),
        "guest_count": len(guest_targets),
        "guest_runs": guest_runs,
        "session_dropped_items": bool(_session_dropped_items),
        "session_mailed_items": bool(_session_mailed_items),
    }


def _sync_hold_for_auto_lobby() -> None:
    """Arm No main menu while Auto Lobby runs when block_menu_pull is on."""
    try:
        from . import hold_session
    except Exception:
        return
    want = bool(_cfg.get("enabled") and _cfg.get("block_menu_pull"))
    try:
        if want:
            hold_session.arm_for_job("auto_lobby")
        else:
            hold_session.release_job("auto_lobby")
    except Exception:
        pass


def _sync_shift_autoaccept_for_auto_lobby() -> None:
    """Arm SHiFT autoaccept while Auto Lobby runs when the checkbox is on.

    Does not persist ON to disk (load must not inherit Auto Lobby's arm).
    If the user turns Home sticky OFF mid-run, stay off until Auto Lobby stops.
    Applies Auto Lobby's Open-cycle timer while armed; restores default on release.
    """
    global _shift_aa_armed_by_auto, _shift_aa_user_disabled
    want = bool(_cfg.get("enabled") and _cfg.get("shift_autoaccept"))
    try:
        from . import shift_friend_autoaccept as shift_aa
    except Exception:
        return
    try:
        if want:
            try:
                shift_aa.set_cycle_interval_sec(
                    float(_cfg.get("shift_autoaccept_interval_sec") or 25.0),
                    override=True,
                )
            except Exception:
                pass
            if _shift_aa_armed_by_auto and not shift_aa.is_enabled():
                # User clicked OFF on Home while Auto Lobby still had the box checked.
                _shift_aa_user_disabled = True
                _shift_aa_armed_by_auto = False
                return
            if not shift_aa.is_enabled() and not _shift_aa_user_disabled:
                shift_aa.set_enabled(True, persist=False)
                _shift_aa_armed_by_auto = True
        else:
            if _shift_aa_armed_by_auto:
                shift_aa.set_enabled(False, persist=False)
                _shift_aa_armed_by_auto = False
            _shift_aa_user_disabled = False
            try:
                shift_aa.clear_cycle_interval_override()
            except Exception:
                pass
    except Exception:
        pass


def _reset_session_runtime() -> None:
    global _kick_at, _kick_armed_indices, _session_dropped_items, _session_mailed_items
    global _cycle_finished_once, _next_drip_at
    global _drip_phase, _drip_drop_at, _drip_last_count, _drip_drop_rounds
    global _drip_last_remaining, _drip_stalled_rounds
    global _drip_pending_guest_mail, _drip_guest_mail_started
    global _cycle_start_guest_indices, _guests_earned_kick
    global _next_loot_cleanup_at, _mailed_guest_keys, _host_mailed_session, _idle_msg_at
    global _guest_ready_since
    _kick_at.clear()
    _kick_armed_indices.clear()
    _cycle_start_guest_indices.clear()
    _guests_earned_kick.clear()
    _mailed_guest_keys.clear()
    _guest_ready_since.clear()
    _host_mailed_session = False
    _session_dropped_items = False
    _session_mailed_items = False
    _cycle_finished_once = False
    _next_drip_at = 0.0
    _drip_phase = ""
    _drip_drop_at = 0.0
    _drip_last_count = 0
    _drip_drop_rounds = 0
    _drip_last_remaining = -1
    _drip_stalled_rounds = 0
    _drip_pending_guest_mail = []
    _drip_guest_mail_started = False
    _next_loot_cleanup_at = 0.0
    _idle_msg_at = 0.0
    # Keep _guest_progress_done across Auto Lobby stop/start so UVHM/Challenges
    # do not re-run the same character until they leave and return (roster note
    # clears keys on leave so a rejoin still gets a full run).


def apply_config(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge payload into settings and persist. Does not auto-start."""
    global _next_cycle_at, _queue, _heavy_done, _current_job, _watching_job, _cycle_total, _cycle_done
    if not _loaded:
        load()
    data = dict(_cfg)
    payload = payload or {}
    for key in _DEFAULTS:
        if key in payload:
            data[key] = payload[key]
    was_on = bool(_cfg.get("enabled"))
    save(data)
    if _cfg.get("enabled") and not was_on:
        # Start on the next tick — no 2s / 45s arming delay.
        global _last_party_n, _seen_guest_keys, _shift_aa_user_disabled
        _shift_aa_user_disabled = False
        _next_cycle_at = time.monotonic()
        _queue.clear()
        _heavy_done.clear()
        _seen_guest_keys.clear()
        _current_job = ""
        _watching_job = ""
        _cycle_total = 0
        _cycle_done = 0
        _last_party_n = 0
        _reset_session_runtime()
        if _cfg.get("item_drip"):
            # Fire as soon as the boost queue is free (drip waits for empty queue).
            _next_drip_at = time.monotonic() if _drop_enabled() else 0.0
            deliver = _drip_deliver_mode()
            drop_pack = str(_cfg.get("item_drip_pack") or "").strip()
            mail_pack = str(_cfg.get("item_drip_mail_pack") or "").strip()
            mode = str(_cfg.get("item_drip_mode") or "random_gzo").lower()
            bits = [f"deliver={deliver}"]
            if deliver in ("drop", "both"):
                if drop_pack or mode == "pack":
                    bits.append(f"drop-list={drop_pack or 'All'}")
                else:
                    bits.append(f"drop-gzo={_cfg.get('item_drip_listing') or 'Modded'}")
            if deliver in ("mail", "both"):
                bits.append(f"mail-list={mail_pack or drop_pack or 'GZO/drop'}")
                bits.append("mail=once-per-join")
                if _cfg.get("item_drip_include_host"):
                    bits.append("include-host")
            _set_msg("Armed — starting now. Auto items: " + ", ".join(bits) + ".")
        else:
            _set_msg("Armed — starting now.")
        if _cfg.get("loot_cleanup"):
            global _next_loot_cleanup_at
            _next_loot_cleanup_at = time.monotonic() + max(
                60.0, float(_cfg.get("loot_cleanup_interval_sec") or 300)
            )
    elif not _cfg.get("enabled"):
        _cancel_owned_missions()
        _queue.clear()
        _current_job = ""
        _watching_job = ""
        _cycle_total = 0
        _cycle_done = 0
        _reset_session_runtime()
        _set_msg("Off.")
    _sync_hold_for_auto_lobby()
    _sync_shift_autoaccept_for_auto_lobby()
    return status()


def stop(payload: Any = None, **_kwargs: Any) -> dict[str, Any]:
    """Hard off — clear queue and persist enabled=False (ignore other payload keys)."""
    del payload, _kwargs
    global _queue, _current_job, _watching_job, _cycle_total, _cycle_done, _next_cycle_at
    global _last_party_n, _step_at, _seen_guest_keys
    if not _loaded:
        load()
    # Flip enabled first so an in-flight MAX ALL can bail between players.
    data = dict(_cfg)
    data["enabled"] = False
    save(data)
    _cancel_owned_missions()
    _queue.clear()
    _current_job = ""
    _watching_job = ""
    _cycle_total = 0
    _cycle_done = 0
    _next_cycle_at = 0.0
    _step_at = 0.0
    _last_party_n = 0
    _seen_guest_keys.clear()
    _reset_session_runtime()
    _sync_hold_for_auto_lobby()
    _sync_shift_autoaccept_for_auto_lobby()
    try:
        from . import shift_friend_autoaccept as shift_aa

        shift_aa.clear_cycle_interval_override()
    except Exception:
        pass
    _set_msg("Off.")
    return status()


def start(payload: Any = None, **_kwargs: Any) -> dict[str, Any]:
    data = dict(payload or {}) if isinstance(payload, dict) else {}
    data.update(_kwargs)
    data["enabled"] = True
    global _queue, _current_job, _watching_job
    _queue.clear()
    _current_job = ""
    _watching_job = ""
    return apply_config(data)


def _set_msg(msg: str) -> None:
    global _last_msg
    _last_msg = str(msg or "")
    _log(_last_msg)


def _cancel_owned_missions() -> None:
    if _watching_job and _job_parts(_watching_job)[0] == "missions":
        from . import mission_progress

        mission_progress.cancel()


def _progression_busy() -> bool:
    try:
        from . import mission_progress, give_everything

        if mission_progress.is_running() or give_everything.is_running():
            return True
    except Exception:
        pass
    try:
        from . import uvhm_runtime

        st = uvhm_runtime.status()
        if bool(st.get("running") or st.get("queued")):
            return True
        try:
            if float(st.get("post_complete_cooldown") or 0.0) > 0.0:
                return True
        except Exception:
            pass
    except Exception:
        pass
    try:
        from . import challenge_bulk_runtime

        st = challenge_bulk_runtime.status()
        # running/queued only — Complete sticky must not block Auto Lobby UVHM.
        if bool(st.get("running") or st.get("queued")):
            return True
    except Exception:
        pass
    try:
        from .shinies import shiny_drop_status

        text = str(shiny_drop_status() or "").lower()
        if text and "idle" not in text and "done" not in text and text.strip():
            return True
    except Exception:
        pass
    return False


def _uvhm_wait_message() -> str:
    try:
        from . import uvhm_runtime

        st = uvhm_runtime.status()
        cool = float(st.get("post_complete_cooldown") or 0.0)
        if cool > 0.0:
            return (
                f"Waiting ~{int(cool) + 1}s for UVHM settle — "
                "then continue for rejoined / new characters."
            )
        if bool(st.get("running") or st.get("queued")):
            return "Waiting — UVHM still running."
    except Exception:
        pass
    return "Waiting — another progression job is still running."


def _uvhm_run_was_skip() -> bool:
    """True when the last UVHM run skipped every target as already UVHM 7."""
    try:
        from . import uvhm_runtime

        results = [str(r) for r in (uvhm_runtime.status().get("results") or ())]
    except Exception:
        return False
    skipped = any(r.startswith("skipped-already:") for r in results)
    ran = any("UVHM rank" in r for r in results)
    return skipped and not ran


def _watch_wait_message(job_key: str) -> str:
    if job_key and _job_parts(job_key)[0] == "missions":
        from . import mission_progress

        return str(mission_progress.status().get("message") or "Waiting on all missions…")
    if job_key and _job_parts(job_key)[0] == "uvhm":
        try:
            from . import uvhm_runtime

            cool = float(uvhm_runtime.status().get("post_complete_cooldown") or 0.0)
        except Exception:
            cool = 0.0
        if cool > 0.0:
            return (
                f"{_job_label(job_key)} finished — settling ~{int(cool) + 1}s "
                "before the next step."
            )
    label = _job_label(job_key) if job_key else "progression"
    return f"Waiting on {label}…"


def _guest_targets() -> list[dict[str, Any]]:
    try:
        from .backend_actions import _player_rows

        rows = _player_rows() or []
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            idx = int(row.get("index"))
        except Exception:
            continue
        if bool(row.get("is_host")) or idx < 0:
            continue
        name = str(row.get("name") or f"guest {idx}").strip()
        # Character name only — same person keeps UVHM/Challenges done across
        # Auto Lobby stop/start and index reshuffles. Different character = new key.
        key = name.casefold() or f"guest-{idx}"
        out.append(
            {
                "index": idx,
                "name": name,
                "shift_name": str(row.get("shift_name") or name),
                "platform_name": str(row.get("platform_name") or ""),
                "platform_kind": str(row.get("platform_kind") or ""),
                "key": key,
            }
        )
    return out


def _kick_exempt_norm_set() -> set[str]:
    from .party_helpers import _gbc_normalize_name

    return {
        _gbc_normalize_name(n)
        for n in (_cfg.get("kick_exempt_names") or [])
        if _gbc_normalize_name(str(n or ""))
    }


def _guest_is_kick_exempt(guest: dict[str, Any] | None) -> bool:
    if not guest:
        return False
    exempt = _kick_exempt_norm_set()
    if not exempt:
        return False
    from .party_helpers import _gbc_normalize_name, _player_aliases_for_match

    aliases = set(_player_aliases_for_match(guest))
    if not aliases:
        aliases = {_gbc_normalize_name(str(guest.get("name") or ""))}
    return bool(aliases & exempt)


def _guest_indices() -> list[int]:
    return [int(row["index"]) for row in _guest_targets()]


def _guest_target_for_index(player_index: int) -> dict[str, Any] | None:
    idx = int(player_index)
    return next((row for row in _guest_targets() if int(row["index"]) == idx), None)


def _all_party_indices() -> list[int]:
    try:
        from .backend_actions import _player_rows

        rows = _player_rows() or []
    except Exception:
        return []
    out: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            idx = int(row.get("index"))
        except Exception:
            continue
        if idx < 0:
            continue
        out.append(idx)
    return out


def _mail_enabled() -> bool:
    if not _cfg.get("item_drip"):
        return False
    return _drip_deliver_mode() in ("mail", "both")


def _drop_enabled() -> bool:
    if not _cfg.get("item_drip"):
        return False
    return _drip_deliver_mode() in ("drop", "both")


def _required_guest_jobs() -> set[str]:
    """Selected boost/mail jobs each guest must finish before kick credit."""
    jobs: set[str] = set()
    if _cfg.get("max_all"):
        jobs.add("max_all")
    if _cfg.get("bank_space"):
        jobs.add("bank_space")
    if _cfg.get("cosmetics"):
        jobs.add("cosmetics")
    if _cfg.get("missions"):
        jobs.add("missions")
    if _cfg.get("challenges"):
        jobs.add("challenges")
    if _cfg.get("uvhm"):
        jobs.add("uvhm")
    if _mail_enabled():
        jobs.add("item_mail")
    return jobs


def _guest_finished_full_run(guest: dict[str, Any]) -> bool:
    required = _required_guest_jobs()
    if not required:
        return True
    done = _guest_progress_done.get(str(guest.get("key") or ""), set())
    return required.issubset(done)


def _mark_guest_job(guest: dict[str, Any] | None, job: str) -> None:
    if guest is None:
        return
    key = str(guest.get("key") or "")
    if not key:
        return
    _guest_progress_done.setdefault(key, set()).add(str(job))


def _build_cycle_queue() -> list[str]:
    jobs: list[str] = []
    # Shinies / phosphene world dump first so guests can loot while boosts run.
    if _cfg.get("drop_shinies"):
        if _cfg.get("repeat_heavy") or "drop_shinies" not in _heavy_done:
            jobs.append("drop_shinies")

    guests_only = bool(_cfg.get("progression_guests_only"))
    guest_targets = _guest_targets()
    waiting_names: list[str] = []

    if guests_only:
        # Strict per-guest full run — keyed by character so index reshuffles cannot
        # Max All / mail the wrong seat (or the host).
        for guest in guest_targets:
            if not _guest_is_boost_ready(guest):
                waiting_names.append(str(guest.get("name") or guest.get("key") or "?"))
                continue
            done = _guest_progress_done.get(str(guest["key"]), set())
            if _cfg.get("max_all") and "max_all" not in done:
                jobs.append(_guest_job_token("max_all", guest))
            if _cfg.get("bank_space") and "bank_space" not in done:
                jobs.append(_guest_job_token("bank_space", guest))
            if _cfg.get("cosmetics") and "cosmetics" not in done:
                jobs.append(_guest_job_token("cosmetics", guest))
            if _cfg.get("missions") and "missions" not in done:
                jobs.append(_guest_job_token("missions", guest))
            if _cfg.get("challenges") and "challenges" not in done:
                jobs.append(_guest_job_token("challenges", guest))
            if _cfg.get("uvhm") and "uvhm" not in done:
                jobs.append(_guest_job_token("uvhm", guest))
            if _mail_enabled() and "item_mail" not in done:
                jobs.append(_guest_job_token("item_mail", guest))
        if (
            _mail_enabled()
            and _cfg.get("item_drip_include_host")
            and not _host_mailed_session
        ):
            jobs.append(f"item_mail@{_host_player_index()}")
        if not jobs and waiting_names:
            shown = ", ".join(waiting_names[:4])
            _set_msg(
                f"Waiting for character load ({shown}"
                f"{'…' if len(waiting_names) > 4 else ''}) — "
                f"~{int(_GUEST_READY_SETTLE_SEC)}s after they spawn in-world."
            )
        return jobs

    # Lobby-wide mode: light boosts once per enable (or new join re-arm), then
    # per-guest challenges/UVHM/mail so nobody is skipped.
    if _cfg.get("max_all"):
        if _cfg.get("repeat_heavy") or "max_all" not in _heavy_done:
            jobs.append("max_all")
    if _cfg.get("bank_space"):
        if _cfg.get("repeat_heavy") or "bank_space" not in _heavy_done:
            jobs.append("bank_space")
    if _cfg.get("cosmetics"):
        if _cfg.get("repeat_heavy") or "cosmetics" not in _heavy_done:
            jobs.append("cosmetics")
    if _cfg.get("missions"):
        for guest in guest_targets:
            if not _guest_is_boost_ready(guest):
                waiting_names.append(str(guest.get("name") or "?"))
                continue
            done = _guest_progress_done.get(str(guest["key"]), set())
            if _cfg.get("repeat_heavy") or "missions" not in done:
                jobs.append(_guest_job_token("missions", guest))
        if not guest_targets and (_cfg.get("repeat_heavy") or "missions" not in _heavy_done):
            jobs.append("missions")
    if _cfg.get("challenges"):
        for guest in guest_targets:
            if not _guest_is_boost_ready(guest):
                waiting_names.append(str(guest.get("name") or "?"))
                continue
            done = _guest_progress_done.get(str(guest["key"]), set())
            if _cfg.get("repeat_heavy") or "challenges" not in done:
                jobs.append(_guest_job_token("challenges", guest))
        if not guest_targets and (
            _cfg.get("repeat_heavy") or "challenges" not in _heavy_done
        ):
            jobs.append("challenges")
    if _cfg.get("uvhm"):
        for guest in guest_targets:
            if not _guest_is_boost_ready(guest):
                if str(guest.get("name") or "?") not in waiting_names:
                    waiting_names.append(str(guest.get("name") or "?"))
                continue
            done = _guest_progress_done.get(str(guest["key"]), set())
            if _cfg.get("repeat_heavy") or "uvhm" not in done:
                jobs.append(_guest_job_token("uvhm", guest))
        if not guest_targets and (_cfg.get("repeat_heavy") or "uvhm" not in _heavy_done):
            jobs.append("uvhm")
    if _mail_enabled():
        for guest in guest_targets:
            if not _guest_is_boost_ready(guest):
                continue
            key = str(guest["key"])
            done = _guest_progress_done.get(key, set())
            if "item_mail" not in done and key not in _mailed_guest_keys:
                jobs.append(_guest_job_token("item_mail", guest))
        if _cfg.get("item_drip_include_host") and not _host_mailed_session:
            jobs.append(f"item_mail@{_host_player_index()}")
    if not jobs and waiting_names:
        shown = ", ".join(waiting_names[:4])
        _set_msg(
            f"Waiting for character load ({shown}"
            f"{'…' if len(waiting_names) > 4 else ''}) before boosts/mail."
        )
    return jobs


def _note_guest_roster_changes() -> None:
    """Party grow / leave→rejoin → re-arm a full run for that join.

    Leave clears progress so the same character rejoining still gets every
    selected job once (Max All, challenges, mail, …) then kick.
    """
    global _last_party_n, _seen_guest_keys, _next_cycle_at
    guests = _guest_targets()
    n = len(guests)
    keys = {str(g.get("key") or "") for g in guests if str(g.get("key") or "")}
    # Guests who left — clear so a rejoin earns a fresh full run + kick credit.
    for left in list(_guest_progress_done.keys()):
        if left not in keys:
            _guest_progress_done.pop(left, None)
            _seen_guest_keys.discard(left)
            _mailed_guest_keys.discard(left)
            _guest_ready_since.pop(left, None)
    # First observation this Auto session — seed only.
    if _last_party_n == 0 and not _seen_guest_keys:
        _seen_guest_keys = set(keys)
        _last_party_n = n
        return
    new_keys = keys - _seen_guest_keys
    grew = n > _last_party_n
    if new_keys or grew:
        for job in ("max_all", "bank_space", "cosmetics", "missions", "uvhm", "challenges", "drop_shinies"):
            _heavy_done.discard(job)
        if new_keys:
            labels = [
                str(g.get("name") or g.get("key") or "?")
                for g in guests
                if str(g.get("key") or "") in new_keys
            ]
            shown = ", ".join(labels[:6]) or ", ".join(sorted(new_keys)[:6])
            _log(
                f"New guest join ({shown}) — full selected run "
                "(MAX ALL / bank / cosmetics / UVHM / Challenges / mail) queued."
            )
            # Pull next cycle forward so the new guest is not stuck behind interval.
            _next_cycle_at = min(float(_next_cycle_at or 0.0), time.monotonic() + 0.5)
        elif grew:
            _log(
                f"Party grew ({_last_party_n}->{n}) — "
                "selected boosts will re-run for the new join."
            )
            _next_cycle_at = min(float(_next_cycle_at or 0.0), time.monotonic() + 0.5)
    _seen_guest_keys |= keys
    _last_party_n = n


def _kick_delay_seconds() -> float:
    """Base kick wait — shorter when this session mailed serials (no ground loot)."""
    mailed = bool(_session_mailed_items)
    dropped = bool(_session_dropped_items) or bool(_cfg.get("drop_shinies"))
    if mailed and not dropped:
        return float(_cfg.get("kick_mail_delay_sec") or 90)
    delay = float(_cfg.get("kick_delay_sec") or 180)
    if dropped:
        delay += float(_cfg.get("kick_drop_bonus_sec") or 240)
    elif mailed:
        # Mail + other boosts: use the mail timer (still shorter than loot bonus).
        delay = min(delay, float(_cfg.get("kick_mail_delay_sec") or 90))
    return delay


def _arm_kick_timers(now: float) -> None:
    if not _cfg.get("auto_kick"):
        return
    delay = _kick_delay_seconds()
    present = set(_guest_indices())
    full_run_only = bool(_cfg.get("kick_after_full_run_only", True))
    if full_run_only:
        # Strict: only guests who finished every selected job this join.
        for guest in _guest_targets():
            idx = int(guest["index"])
            if idx not in present:
                continue
            if _guest_finished_full_run(guest):
                _guests_earned_kick.add(idx)
        eligible = _guests_earned_kick & present
    else:
        eligible = present
    for idx in eligible:
        guest = _guest_target_for_index(idx)
        if _guest_is_kick_exempt(guest):
            _kick_at.pop(idx, None)
            _kick_armed_indices.discard(idx)
            continue
        if idx in _kick_armed_indices:
            continue
        _kick_armed_indices.add(idx)
        _kick_at[idx] = now + delay
        note = " (full-run only)" if full_run_only else ""
        who = str((guest or {}).get("name") or f"index {idx}")
        _log(f"Kick timer armed for {who} (#{idx}) in {int(delay)}s{note}.")


def _tick_kick_timers(now: float) -> None:
    if not _cfg.get("auto_kick"):
        _kick_at.clear()
        return
    live = set(_guest_indices())
    # Guest left — drop their timer and full-run credit (rejoin needs a new full cycle).
    for idx in list(_kick_at.keys()):
        if idx not in live:
            _kick_at.pop(idx, None)
            _kick_armed_indices.discard(idx)
            _guests_earned_kick.discard(idx)
            _log(f"Guest index {idx} left — kick timer cleared.")
    for idx in list(_guests_earned_kick):
        if idx not in live:
            _guests_earned_kick.discard(idx)
    from .bridge_actions_extended import party_kick

    for idx, deadline in list(_kick_at.items()):
        guest = _guest_target_for_index(idx)
        if _guest_is_kick_exempt(guest):
            _kick_at.pop(idx, None)
            _kick_armed_indices.discard(idx)
            who = str((guest or {}).get("name") or f"index {idx}")
            _log(f"Kick skipped for never-kick friend {who}.")
            continue
        if now < deadline:
            continue
        _kick_at.pop(idx, None)
        try:
            result = party_kick({"player_index": idx, "reason": "Auto Lobby — session complete"})
            _set_msg(str(result.get("message") or f"Kicked guest index {idx}."))
        except Exception as exc:
            _set_msg(f"Kick index {idx} failed: {exc!r}")


def _progression_watch_succeeded(job_base: str) -> bool:
    """True when a watched UVHM/challenges/shiny job finished cleanly."""
    base = str(job_base or "").strip()
    if base == "missions":
        from . import mission_progress

        st = mission_progress.status() or {}
        return (st.get("phase") == "complete" and not any(int(st.get(key) or 0) for key in ("failed", "blocked_count", "uncertain", "locked", "unsupported")))
    if base == "uvhm":
        try:
            from . import uvhm_runtime

            st = uvhm_runtime.status() or {}
        except Exception:
            return True
        phase = str(st.get("phase") or "").lower()
        msg = str(st.get("message") or st.get("detail") or "").lower()
        if phase in ("error", "cancelled"):
            return False
        if "no longer resolvable" in msg or "failed" in msg:
            return False
        # Already-maxed guests complete immediately — that counts as success (skip).
        return True
    if base == "challenges":
        try:
            from . import challenge_bulk_runtime

            st = challenge_bulk_runtime.status() or {}
        except Exception:
            return True
        phase = str(st.get("phase") or "").lower()
        msg = str(st.get("message") or "").lower()
        if phase in ("error", "cancelled"):
            return False
        if "lobby empty" in msg or "left / unresolvable" in msg:
            return False
        return True
    return True


def _run_step(job: str) -> None:
    global _watching_job, _session_dropped_items, _session_mailed_items, _host_mailed_session
    global _step_at, _step_deferred
    _step_deferred = False
    if not _cfg.get("enabled"):
        return
    job_key = str(job or "")
    base, guest_idx, guest, status = _resolve_step_target(job_key)
    job = base
    from .backend_actions import max_all
    from .bridge_actions_extended import (
        challenge_bulk_start,
        deliver_serials,
        devperk_activate,
        inventory_set_sizes,
        shiny_drop_all,
        uvhm_start,
        uvhm_start_all,
    )

    if status == "waiting":
        # Character select / no pawn yet — put job back and wait.
        _queue.insert(0, job_key)
        _step_deferred = True
        who = str((guest or {}).get("name") or "guest")
        _set_msg(
            f"Waiting for {who} to finish joining / pick a character "
            f"(~{int(_GUEST_READY_SETTLE_SEC)}s after they spawn)…"
        )
        _step_at = time.monotonic() + 2.0
        return
    if status == "gone":
        _set_msg(f"{_JOB_LABELS.get(job, job)} skipped — guest left before start.")
        return
    if status == "host_mail" or (
        job == "item_mail"
        and guest_idx is not None
        and int(guest_idx) == int(_host_player_index())
    ):
        if not _cfg.get("item_drip_include_host"):
            _set_msg("Auto mail skipped host (Also mail host is off).")
            return
        is_host_mail = True
    else:
        is_host_mail = status == "host_mail"

    # Never mail the host by accident when include-host is off.
    if job == "item_mail" and guest is None and not is_host_mail and not _cfg.get("item_drip_include_host"):
        _set_msg("Auto mail skipped — no guest target (host never receives unless include-host).")
        return

    if job == "max_all":
        try:
            from .player_economy import max_all_for_target

            if guest_idx is not None:
                indices = [int(guest_idx)]
            else:
                indices = _all_party_indices() or [0]
            ok_n = 0
            for idx in indices:
                if not _cfg.get("enabled"):
                    _set_msg(f"MAX ALL stopped early ({ok_n}/{len(indices)}).")
                    return
                ok, _detail = max_all_for_target(
                    player_index=int(idx),
                    options={
                        "max_cash": True,
                        "max_eridium": True,
                        "max_sdu": True,
                        "max_vault_cards": True,
                        "max_player_level": True,
                        "max_spec_level": True,
                    },
                )
                if ok:
                    ok_n += 1
            if ok_n:
                if guest is not None:
                    _mark_guest_job(guest, "max_all")
                    _guest_boost_at[str(guest.get("key") or "")] = time.monotonic()
                else:
                    _heavy_done.add("max_all")
                _set_msg(f"MAX ALL applied to {ok_n}/{len(indices)} player(s).")
            else:
                # Not ready / failed — retry once they have a pawn (do not mark done).
                if guest is not None:
                    _queue.insert(0, job_key)
                    _step_deferred = True
                    _guest_ready_since.pop(str(guest.get("key") or ""), None)
                    _set_msg(
                        f"MAX ALL missed {guest.get('name') or 'guest'} "
                        "(not in-world yet) — will retry after character load."
                    )
                    _step_at = time.monotonic() + 3.0
                else:
                    _set_msg(f"MAX ALL applied to 0/{len(indices)} player(s).")
        except Exception:
            result = max_all({})
            if result.get("ok", True):
                if guest is not None:
                    _mark_guest_job(guest, "max_all")
                else:
                    _heavy_done.add("max_all")
            _set_msg(str(result.get("message") or "MAX ALL done."))
        return
    if job == "missions":
        from . import mission_progress

        result = mission_progress.start("all", int(guest_idx) if guest_idx is not None else -1,
                                        redo_completed=bool(_cfg.get("missions_redo_completed")))
        if result.get("ok"):
            _watching_job = job_key
            _set_msg(str(result.get("message") or "All missions queued."))
        else:
            _queue.insert(0, job_key)
            _step_deferred = True
            _step_at = time.monotonic() + 3.0
            _set_msg(str(result.get("message") or "Missions could not start; waiting."))
        return
    if job == "bank_space":
        if not _cfg.get("enabled"):
            return
        payload: dict[str, Any] = {
            "backpack_size": int(_cfg.get("backpack_size") or 500),
            "bank_size": int(_cfg.get("bank_size") or 500),
        }
        if guest_idx is not None:
            payload["player_index"] = int(guest_idx)
            payload["scope"] = "target"
        else:
            payload["scope"] = "all"
        result = inventory_set_sizes(payload)
        if result.get("ok", True):
            if guest is not None:
                _mark_guest_job(guest, "bank_space")
            else:
                _heavy_done.add("bank_space")
            _set_msg(str(result.get("message") or "Bank / backpack sized."))
        else:
            if guest is not None:
                _queue.insert(0, job_key)
                _step_deferred = True
                _set_msg(
                    f"Bank/backpack failed for {guest.get('name') or 'guest'} — retrying…"
                )
                _step_at = time.monotonic() + 3.0
            else:
                _set_msg(str(result.get("message") or "Bank / backpack failed."))
        return
    if job == "cosmetics":
        if not _cfg.get("enabled"):
            return
        perk_payload: dict[str, Any] = {"perk_index": 4}
        if guest_idx is not None:
            perk_payload["player_index"] = int(guest_idx)
        else:
            perk_payload["player_index"] = -1
        result = devperk_activate(perk_payload)
        if result.get("ok", True):
            if guest is not None:
                _mark_guest_job(guest, "cosmetics")
                _guest_boost_at[str(guest.get("key") or "")] = time.monotonic()
            else:
                _heavy_done.add("cosmetics")
            _set_msg(str(result.get("message") or "Cosmetics + hover drives unlocked."))
        else:
            if guest is not None:
                _queue.insert(0, job_key)
                _step_deferred = True
                _set_msg(
                    f"Cosmetics failed for {guest.get('name') or 'guest'} — retrying…"
                )
                _step_at = time.monotonic() + 3.0
            else:
                _set_msg(str(result.get("message") or "Cosmetics failed."))
        return
    if job == "item_mail":
        if not _cfg.get("enabled"):
            return
        host_idx = int(_host_player_index())
        if guest_idx is None:
            _set_msg("Auto mail skipped — no target index.")
            return
        if int(guest_idx) == host_idx and not _cfg.get("item_drip_include_host"):
            _set_msg("Auto mail blocked — would have hit host (include-host is off).")
            return
        if guest is None and not is_host_mail:
            _set_msg(f"Guest index {guest_idx} left before mail — skipped safely.")
            return
        serials = _pick_mail_serials()
        if not serials:
            pack = str(_cfg.get("item_drip_mail_pack") or _cfg.get("item_drip_pack") or "").strip()
            if pack:
                _set_msg(f"Auto mail — no serials in Item list “{pack}” (list unchanged).")
            else:
                _set_msg("Auto mail — no GZO codes cached (Serials → Codes → Refresh GZO).")
            if guest is not None:
                _mark_guest_job(guest, "item_mail")
            elif is_host_mail:
                _host_mailed_session = True
            return
        if _serial_delivery_busy():
            _queue.insert(0, job_key)
            _step_deferred = True
            _set_msg("Auto mail waiting — a mail send is already in progress.")
            return
        target_idx = int(guest_idx)
        # Final hard gate: never silently deliver to host unless opted in.
        if target_idx == host_idx and not _cfg.get("item_drip_include_host"):
            _set_msg("Auto mail blocked — host target refused.")
            return
        result = deliver_serials(
            {
                "serials": list(serials),
                "count": 1,
                "level_override": "yes",
                "level": int(_cfg.get("item_drip_level") or 50),
                "mode": "player",
                "player_index": target_idx,
                "open_rewards": True,
            }
        )
        ok = bool(result.get("ok", True))
        if ok:
            _session_mailed_items = True
            if guest is not None:
                _mark_guest_job(guest, "item_mail")
                _mailed_guest_keys.add(str(guest["key"]))
            elif is_host_mail:
                _host_mailed_session = True
            who = str((guest or {}).get("name") or ("host" if is_host_mail else f"#{target_idx}"))
            _set_msg(
                f"Auto mail: queued {len(serials)} code(s) to {who} "
                "(once this join — Item list unchanged)."
            )
        else:
            _set_msg(str(result.get("message") or "Auto mail failed."))
        return
    if job == "challenges":
        if _progression_busy():
            _queue.insert(0, job_key)
            _step_deferred = True
            _set_msg(_uvhm_wait_message())
            return
        if guest_idx is not None and guest is None:
            _set_msg(f"Guest left before Challenges started — skipped safely.")
            return
        try:
            from . import hold_session

            hold_session.arm_for_job("auto_lobby")
        except Exception:
            pass
        if guest_idx is not None:
            tidx = int(guest_idx)
        else:
            try:
                from .backend_actions import get_target_player_index

                tidx = int(get_target_player_index())
            except Exception:
                tidx = 0
        result = challenge_bulk_start(
            {"category": "All non-UVHM", "confirmed": True, "player_index": tidx}
        )
        if result.get("ok", True):
            # Mark done only when the watched job finishes cleanly.
            _watching_job = job_key
            _set_msg(str(result.get("message") or "Challenges started."))
        else:
            _set_msg(str(result.get("message") or "Challenges failed to start — will retry next cycle."))
        return
    if job == "uvhm":
        if _progression_busy():
            _queue.insert(0, job_key)
            _step_deferred = True
            _set_msg(_uvhm_wait_message())
            return
        if guest_idx is not None and guest is None:
            _set_msg("Guest left before UVHM started — skipped safely.")
            return
        try:
            from . import hold_session

            hold_session.arm_for_job("auto_lobby")
        except Exception:
            pass
        if guest is not None:
            since = time.monotonic() - _guest_boost_at.get(str(guest.get("key") or ""), 0.0)
            if since < _UVHM_AFTER_BOOST_SEC:
                try:
                    from . import uvhm_runtime

                    uvhm_runtime.defer_start(_UVHM_AFTER_BOOST_SEC - since)
                except Exception:
                    pass
        if guest_idx is not None:
            result = uvhm_start(
                {"confirmed": True, "max_rank": 7, "player_index": int(guest_idx)}
            )
        else:
            result = uvhm_start_all({"confirmed": True, "max_rank": 7})
        if result.get("ok", True):
            # Already-maxed guests finish immediately inside the UVHM machine.
            # Mark done only after watch confirms success (skip = success).
            _watching_job = job_key
            _set_msg(str(result.get("message") or "UVHM started."))
        else:
            msg = str(result.get("message") or "UVHM failed to start")
            if "just finished" in msg.lower() or "settling" in msg.lower():
                _queue.insert(0, job_key)
                _step_deferred = True
                _set_msg(_uvhm_wait_message())
            else:
                _set_msg(msg + " — will retry next cycle.")
        return
    if job == "drop_shinies":
        if _progression_busy():
            _queue.insert(0, job_key)
            _step_deferred = True
            _set_msg("Waiting — shiny drop skipped while another job runs.")
            return
        result = shiny_drop_all(
            {
                "shape": "none",
                "settle": "none",
                "stay_in_air": "no",
                "spawn_then_shape": "no",
            }
        )
        if result.get("ok", True):
            _session_dropped_items = True
            _heavy_done.add("drop_shinies")
            _watching_job = "drop_shinies"
        _set_msg(str(result.get("message") or "Drop All Shinies started (no shape)."))
        return
    _set_msg(f"Unknown job {job!r}.")


def tick(now: float | None = None) -> None:
    """One small step per host tick. Safe to call often."""
    global _next_cycle_at, _queue, _step_at, _current_job, _watching_job
    global _cycle_total, _cycle_done, _next_drip_at, _cycle_finished_once
    global _cycle_start_guest_indices
    global _drip_phase, _drip_drop_at, _idle_msg_at
    if not _loaded:
        load()
    if not _cfg.get("enabled"):
        return
    try:
        from .session_guards import session_safe

        if not session_safe():
            return
    except Exception:
        pass
    try:
        from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate

        world, _ = _gbc_session_world_and_gamestate()
        if not _gbc_is_listen_host_world(world):
            return
    except Exception:
        return

    now = time.monotonic() if now is None else float(now)
    _sync_hold_for_auto_lobby()
    _sync_shift_autoaccept_for_auto_lobby()
    try:
        _note_guest_roster_changes()
    except Exception:
        pass
    join_quiet = _lobby_join_quiet()
    if join_quiet:
        # Keep due timers from firing the instant quiet ends (guest still settling).
        settle_pad = now + 2.0
        if _next_cycle_at < settle_pad:
            _next_cycle_at = settle_pad
        if _cfg.get("item_drip") and (_next_drip_at <= 0 or _next_drip_at < settle_pad):
            _next_drip_at = settle_pad
        _set_msg("Waiting on lobby join settle — auto-drop and boosts paused.")
        # Advance wait_mail timing only; spill itself is gated inside follow-up.
        try:
            _tick_drip_followup(now)
        except Exception:
            pass
        return

    _tick_kick_timers(now)
    try:
        _tick_drip_followup(now)
    except Exception as exc:
        _drip_phase = ""
        _drip_drop_at = 0.0
        # Keep drip armed — a one-off spill error must not kill the whole lobby drip.
        _next_drip_at = now + max(_MIN_DRIP_SEC, float(_cfg.get("item_drip_interval_sec") or 120))
        _set_msg(
            f"Auto-drop follow-up hit an error ({exc!r}); will retry next interval. "
            "Auto-drop stays enabled."
        )
    try:
        _tick_loot_cleanup(now)
    except Exception:
        pass

    if _watching_job and not _progression_busy():
        finished = str(_watching_job)
        _watching_job = ""
        fin_base, _fin_idx, fin_key = _job_parts(finished)
        ok = _progression_watch_succeeded(fin_base)
        if ok:
            if fin_key:
                _mark_guest_job(_guest_by_key(fin_key), fin_base)
            elif fin_base in ("missions", "challenges", "uvhm", "drop_shinies"):
                _heavy_done.add(fin_base)
            if fin_base == "uvhm" and _uvhm_run_was_skip():
                _set_msg(f"{_job_label(finished)} — already UVHM 7, skipped — continuing.")
            elif fin_base == "uvhm":
                _set_msg(f"{_job_label(finished)} done (ranks 1-7 applied) — continuing.")
            else:
                _set_msg(f"{_job_label(finished)} done.")
        else:
            # Do not mark done — requeue so a late character load / rejoin can retry.
            if fin_base == "missions":
                from . import mission_progress

                _set_msg(f"{_job_label(finished)} incomplete: {mission_progress.status().get('message')}. Other selected jobs will continue; no full-run kick credit was granted.")
            elif fin_key or fin_base in ("challenges", "uvhm"):
                _queue.insert(0, finished)
                _set_msg(
                    f"{_job_label(finished)} did not finish cleanly — will retry."
                )
            else:
                _set_msg(f"{_job_label(finished)} ended with errors.")
        if _cfg.get("auto_kick"):
            _arm_kick_timers(now)
        if not _queue:
            _cycle_finished_once = True
            _arm_kick_timers(now)
            gap = _clamp_interval(_cfg.get("interval_sec"))
            # Extra breathing room after heavy progression before the next cycle.
            if _is_heavy_job(finished):
                gap = max(gap, 60.0)
            # Always apply the gap — waiting heartbeats pin _next_cycle_at ~5s ahead
            # and used to skip the 60s rest (cycles stacked every few seconds).
            _next_cycle_at = now + gap
            # Let GZO drip fire right after the boost cycle (not a long rest).
            if _drop_enabled() and not _drip_phase:
                soon = now + 0.5
                if _next_drip_at <= 0 or _next_drip_at > soon:
                    _next_drip_at = soon
            if ok:
                _set_msg(f"{_job_label(finished)} done — next cycle in {int(max(0, gap))}s.")

    # Independent ground-drop timer (mail is once-per-join via item_mail jobs).
    # Never drip while a heavy progression job is live — mail+challenges stacks crash hosts.
    if (
        _drop_enabled()
        and not _drip_phase
        and not _watching_job
        and not _progression_busy()
    ):
        if _next_drip_at <= 0:
            # Unarmed → fire immediately (Start already sets this; keep for safety).
            _next_drip_at = now
        elif now >= _next_drip_at:
            try:
                _run_item_drip()
            except Exception as exc:
                _set_msg(f"Auto-drop failed: {exc!r}")
            # While mail/open/drop is in flight, nudge soon; once armed for the next
            # full cycle, leave _next_drip_at alone (follow-up sets the interval).
            if _serial_delivery_busy() or _drip_phase:
                _next_drip_at = now + max(15.0, min(_MIN_DRIP_SEC, 30.0))
            elif _next_drip_at <= now:
                _next_drip_at = now + max(
                    _MIN_DRIP_SEC, float(_cfg.get("item_drip_interval_sec") or 120)
                )

    if _queue:
        if not _cfg.get("enabled"):
            _queue.clear()
            return
        if now < _step_at:
            return
        # Do not start the next queued step while a watched heavy job is still live.
        if _watching_job or _progression_busy():
            if now >= _next_cycle_at:
                _next_cycle_at = now + 5.0
                _set_msg(_watch_wait_message(_watching_job))
            return
        job = _queue.pop(0)
        _current_job = job
        _set_msg(f"Step: {_job_label(job)}…")
        try:
            _run_step(job)
        except Exception as exc:
            _set_msg(f"{job} failed: {exc!r}")
        _current_job = ""
        if _step_deferred:
            # Job was put back (character not ready / busy) — do not advance cycle.
            return
        _cycle_done = min(int(_cycle_total), int(_cycle_done) + 1)
        if not _cfg.get("enabled"):
            _queue.clear()
            return
        # Per-guest: arm kick as soon as that guest's full selected run is done
        # (do not wait for other guests still in the queue).
        if _cfg.get("auto_kick") and not _watching_job:
            _arm_kick_timers(now)
        try:
            gap = _HEAVY_STEP_GAP_SEC if _is_heavy_job(job) else _STEP_GAP_SEC
        except Exception:
            gap = _STEP_GAP_SEC
        _step_at = now + gap
        # Always schedule the cycle rest here — gating on progression_busy used to
        # skip the interval (shape still settling after drip) and restart MAX ALL
        # every few seconds with no "Cycle done" log.
        if not _queue and not _watching_job:
            wait = _clamp_interval(_cfg.get("interval_sec"))
            _next_cycle_at = now + wait
            _cycle_finished_once = True
            _arm_kick_timers(now)
            if _progression_busy():
                _set_msg(
                    f"Cycle steps done — resting {int(wait)}s "
                    "(shape/progression still settling)."
                )
            else:
                _set_msg(f"Cycle done — next in {int(wait)}s.")
        return

    if _watching_job or _progression_busy() or _drip_phase:
        if _drip_phase:
            return
        if now >= _next_cycle_at:
            _next_cycle_at = now + 5.0
            if _watching_job:
                _set_msg(_watch_wait_message(_watching_job))
            else:
                _set_msg("Waiting — another progression job is still running.")
        return

    if _cycle_finished_once and _cfg.get("auto_kick"):
        _arm_kick_timers(now)

    if now < _next_cycle_at:
        return

    _queue = _build_cycle_queue()
    if not _queue:
        guest_watch = bool(
            _cfg.get("progression_guests_only")
            and (
                _cfg.get("challenges")
                or _cfg.get("uvhm")
                or _cfg.get("max_all")
                or _cfg.get("missions")
                or _cfg.get("cosmetics")
                or _cfg.get("bank_space")
                or _mail_enabled()
            )
        )
        _next_cycle_at = now + (3.0 if guest_watch else _clamp_interval(_cfg.get("interval_sec")))
        _cycle_total = 0
        _cycle_done = 0
        # Arm kick for anyone who already finished their full selected run.
        if _cfg.get("auto_kick"):
            _arm_kick_timers(now)
        if now - float(_idle_msg_at or 0.0) >= 8.0:
            _idle_msg_at = now
            if guest_watch:
                guests = _guest_targets()
                if guests:
                    not_ready = [
                        str(g.get("name") or g.get("key") or "?")
                        for g in guests
                        if not _guest_is_boost_ready(g)
                    ]
                    pending = [
                        str(g.get("name") or g.get("key") or "?")
                        for g in guests
                        if _guest_is_boost_ready(g) and not _guest_finished_full_run(g)
                    ]
                    if not_ready:
                        _set_msg(
                            f"Waiting for character load: {', '.join(not_ready[:4])}"
                            + ("…" if len(not_ready) > 4 else "")
                            + f" (~{int(_GUEST_READY_SETTLE_SEC)}s after spawn)."
                        )
                    elif pending:
                        _set_msg(
                            f"Waiting to finish run for: {', '.join(pending[:4])}"
                            + ("…" if len(pending) > 4 else "")
                        )
                    else:
                        _set_msg("Guest runs complete — watching for newly joined guests.")
                else:
                    _set_msg("Guest-only armed — waiting for guests to join.")
            elif _drop_enabled() or _cfg.get("auto_kick"):
                _set_msg("Idle boosts — auto drop / kick timers still active.")
            else:
                _set_msg("Auto on — tick a boost job or enable Auto items / kick.")
        return
    _cycle_start_guest_indices = set(_guest_indices())
    _cycle_total = len(_queue)
    _cycle_done = 0
    _step_at = now
    _set_msg(f"Cycle started ({len(_queue)} step(s)).")


def abandon() -> None:
    """Stop mid-cycle on teardown / menu."""
    global _queue, _next_cycle_at, _current_job, _watching_job
    _queue.clear()
    _current_job = ""
    _watching_job = ""
    if _cfg.get("enabled"):
        _next_cycle_at = time.monotonic() + _clamp_interval(_cfg.get("interval_sec"))
        _set_msg("Paused for menu / travel.")
