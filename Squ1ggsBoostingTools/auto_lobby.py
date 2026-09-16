"""Host-side auto lobby loop — paced boosts that remember between sessions.

Runs on the game thread in small steps so the host does not freeze the lobby.
Heavy jobs (challenges / UVHM) start at most once per enable unless you turn
Repeat heavy jobs on.

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
_HEAVY_JOBS = frozenset({"challenges", "uvhm", "drop_shinies", "cosmetics"})

_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "interval_sec": _DEFAULT_INTERVAL_SEC,
    "max_all": True,
    "cosmetics": False,
    "challenges": False,
    "uvhm": False,
    # Progression only: exclude host, wait for guests, process each seen guest once.
    "progression_guests_only": False,
    "bank_space": False,
    "backpack_size": 500,
    "bank_size": 500,
    "drop_shinies": False,
    "repeat_heavy": False,
    # Keep guests from yanking host to title / lobby while Auto Lobby runs.
    "block_menu_pull": True,
    # Mail drip between cycles: codes → host mail → open → spill backpack on the ground
    # so the whole lobby can loot (Boost target All / any — ground pile is shared).
    "item_drip": False,
    "item_drip_mode": "random_gzo",  # random_gzo | pack
    "item_drip_listing": "Modded",  # Legit | Modded | All
    "item_drip_pack": "",
    "item_drip_count": _DEFAULT_DRIP_COUNT,
    "item_drip_level": 50,
    "item_drip_interval_sec": 120,
    # After a full cycle, kick each guest once (fair timer).
    "auto_kick": False,
    "kick_delay_sec": 180,
    "kick_drop_bonus_sec": 240,
}

_JOB_LABELS: dict[str, str] = {
    "max_all": "MAX ALL",
    "bank_space": "Bank / backpack",
    "cosmetics": "Cosmetics",
    "challenges": "Challenges (non-UVHM)",
    "uvhm": "UVHM progression",
    "drop_shinies": "Drop All Shinies",
    "item_drip": "Item drip (mail → me → drop pack)",
}

_BOOL_KEYS = (
    "enabled",
    "max_all",
    "cosmetics",
    "challenges",
    "uvhm",
    "progression_guests_only",
    "bank_space",
    "drop_shinies",
    "repeat_heavy",
    "block_menu_pull",
    "item_drip",
    "auto_kick",
)

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
_next_drip_at = 0.0
_session_dropped_items = False
_kick_at: dict[int, float] = {}
_kick_armed_indices: set[int] = set()
_cycle_finished_once = False
_drip_phase = ""  # "" | "wait_mail" | "drop"
_drip_drop_at = 0.0
_drip_last_count = 0
_drip_drop_rounds = 0
_drip_last_remaining = -1
_drip_stalled_rounds = 0
_MAX_DRIP_DROP_ROUNDS = 14


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


def _pick_drip_serials() -> list[str]:
    count = int(_cfg.get("item_drip_count") or _DEFAULT_DRIP_COUNT)
    mode = str(_cfg.get("item_drip_mode") or "random_gzo").lower()
    if mode == "pack":
        pack = str(_cfg.get("item_drip_pack") or "").strip()
        try:
            from . import serial_store

            rows = serial_store.filter_entries(group=pack or "All")
        except Exception as exc:
            _log(f"Drip pack read failed: {exc!r}")
            return []
        serials = [str(r.get("serial") or "").strip() for r in rows if str(r.get("serial") or "").strip()]
        if not serials:
            return []
        random.shuffle(serials)
        return serials[:count]

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


def _run_item_drip() -> None:
    """Mail N codes to the host, open them, then spill the whole backpack on the ground."""
    global _session_dropped_items, _drip_phase, _drip_drop_at, _drip_last_count
    global _drip_last_remaining, _drip_stalled_rounds
    if _drip_phase:
        _set_msg("Item drip already in progress (mail → open → drop pack).")
        return
    if _serial_delivery_busy():
        _set_msg("Item drip waiting — a mail send is already in progress.")
        return
    serials = _pick_drip_serials()
    if not serials:
        mode = str(_cfg.get("item_drip_mode") or "random_gzo").lower()
        if mode == "pack":
            _set_msg("Item drip — no serials in that My packs group.")
        else:
            _set_msg("Item drip — no GZO codes cached (Serials → GZO / Lootlemon → Refresh GZO).")
        return
    from .bridge_actions_extended import deliver_serials

    host_idx = _host_player_index()
    result = deliver_serials(
        {
            "serials": serials,
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
        _set_msg(str(result.get("message") or "Item drip mail failed."))
        return
    _drip_last_count = len(serials)
    _drip_phase = "wait_mail"
    _drip_drop_at = 0.0
    _drip_drop_rounds = 0
    _drip_last_remaining = -1
    _drip_stalled_rounds = 0
    _session_dropped_items = True
    _set_msg(
        f"GZO drip: mailing {_drip_last_count} code(s) to you (host), opening, then "
        "spilling your backpack on the ground for the lobby to loot."
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
    if _drip_phase not in ("wait_mail", "drop"):
        return
    if _drip_phase == "wait_mail":
        if _serial_delivery_busy():
            return
        if _drip_drop_at <= 0:
            # Larger piles need a longer settle after open before SpillOut.
            settle = max(2.5, min(40.0, 2.0 + float(_drip_last_count) * 0.12))
            _drip_drop_at = now + settle
            _set_msg(
                f"GZO drip: mail/open done ({_drip_last_count}) — "
                f"dropping backpack in {int(settle)}s for lobby loot…"
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
    try:
        result = faafo_drop_backpack({"player_index": host_idx})
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
        _next_drip_at = now + float(_cfg.get("item_drip_interval_sec") or 120)
        _session_dropped_items = True
        _set_msg(
            f"GZO drip complete: mailed {_drip_last_count} → host backpack → ground. "
            f"Lobby can loot. {msg}"
        )
        return
    if _drip_drop_rounds >= _MAX_DRIP_DROP_ROUNDS or _drip_stalled_rounds >= 2:
        _drip_phase = ""
        _drip_drop_at = 0.0
        _drip_last_remaining = -1
        _drip_stalled_rounds = 0
        _next_drip_at = 0.0
        _cfg["item_drip"] = False
        save()
        _set_msg(
            f"GZO drip stopped and disabled: backpack spill made no safe progress "
            f"after {_drip_drop_rounds} pass(es) ({msg}). Clear the host backpack "
            "manually before re-enabling Item drip; no more items will be mailed."
        )
        return
    # Pace more spill passes — one FAAFO call often stops early on big bags.
    _drip_drop_at = now + 1.4
    _set_msg(
        f"GZO drip: spilling backpack pass {_drip_drop_rounds}/{_MAX_DRIP_DROP_ROUNDS} "
        f"(left≈{remaining or '?'})…"
    )


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
    listing = str(merged.get("item_drip_listing") or "Modded").strip()
    if listing.lower() not in ("legit", "modded", "all"):
        listing = "Modded"
    else:
        listing = listing[:1].upper() + listing[1:].lower()
        if listing.lower() == "all":
            listing = "All"
    merged["item_drip_listing"] = listing
    merged["item_drip_pack"] = str(merged.get("item_drip_pack") or "").strip()
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
    merged["kick_delay_sec"] = _clamp_kick_sec(merged.get("kick_delay_sec"), 180.0)
    merged["kick_drop_bonus_sec"] = _clamp_kick_sec(merged.get("kick_drop_bonus_sec"), 240.0)
    return merged


def load() -> dict[str, Any]:
    global _cfg, _loaded
    path = _settings_path()
    merged = dict(_DEFAULTS)
    had_enabled = False
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key in _DEFAULTS:
                    if key in data:
                        merged[key] = data[key]
                had_enabled = _truthy(data.get("enabled"), False)
    except Exception as exc:
        _log(f"Could not read settings: {exc!r}")
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
    base, target_idx = _job_parts(key)
    label = _JOB_LABELS.get(base, base or "—")
    return f"{label} · guest {target_idx}" if target_idx is not None else label


def _job_parts(job: str) -> tuple[str, int | None]:
    text = str(job or "").strip()
    if "@" not in text:
        return text, None
    base, raw_idx = text.rsplit("@", 1)
    try:
        return base, int(raw_idx)
    except Exception:
        return text, None


def _is_heavy_job(job: str) -> bool:
    return _job_parts(job)[0] in _HEAVY_JOBS


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
        and (_cfg.get("challenges") or _cfg.get("uvhm"))
    )
    guest_targets = _guest_targets() if guest_watch else []
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
        detail = (
            f"Watching {len(guest_targets)} processed guest(s) for new joins"
            if guest_targets
            else "Host skipped — waiting for guests to join"
        )
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
        "session_dropped_items": bool(_session_dropped_items),
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


def _reset_session_runtime() -> None:
    global _kick_at, _kick_armed_indices, _session_dropped_items, _cycle_finished_once, _next_drip_at
    global _drip_phase, _drip_drop_at, _drip_last_count, _drip_drop_rounds
    global _drip_last_remaining, _drip_stalled_rounds, _guest_progress_done
    _kick_at.clear()
    _kick_armed_indices.clear()
    _session_dropped_items = False
    _cycle_finished_once = False
    _next_drip_at = 0.0
    _drip_phase = ""
    _drip_drop_at = 0.0
    _drip_last_count = 0
    _drip_drop_rounds = 0
    _drip_last_remaining = -1
    _drip_stalled_rounds = 0
    _guest_progress_done.clear()


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
        _next_cycle_at = time.monotonic() + 2.0
        _queue.clear()
        _heavy_done.clear()
        _current_job = ""
        _watching_job = ""
        _cycle_total = 0
        _cycle_done = 0
        _reset_session_runtime()
        if _cfg.get("item_drip"):
            _next_drip_at = time.monotonic() + float(_cfg.get("item_drip_interval_sec") or 60)
        _set_msg("Armed — first cycle in a couple of seconds.")
    elif not _cfg.get("enabled"):
        _queue.clear()
        _current_job = ""
        _watching_job = ""
        _cycle_total = 0
        _cycle_done = 0
        _reset_session_runtime()
        _set_msg("Off.")
    _sync_hold_for_auto_lobby()
    return status()


def stop(payload: Any = None, **_kwargs: Any) -> dict[str, Any]:
    """Hard off — clear queue and persist enabled=False (ignore other payload keys)."""
    del payload, _kwargs
    global _queue, _current_job, _watching_job, _cycle_total, _cycle_done, _next_cycle_at
    if not _loaded:
        load()
    data = dict(_cfg)
    data["enabled"] = False
    save(data)
    _queue.clear()
    _current_job = ""
    _watching_job = ""
    _cycle_total = 0
    _cycle_done = 0
    _next_cycle_at = 0.0
    _reset_session_runtime()
    _sync_hold_for_auto_lobby()
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


def _progression_busy() -> bool:
    try:
        from . import uvhm_runtime

        st = uvhm_runtime.status()
        if bool(st.get("running") or st.get("queued")):
            return True
    except Exception:
        pass
    try:
        from . import challenge_bulk_runtime

        st = challenge_bulk_runtime.status()
        if bool(st.get("active") or st.get("queued")):
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
        out.append(
            {
                "index": idx,
                "name": name,
                "key": f"{idx}:{name.casefold()}",
            }
        )
    return out


def _guest_indices() -> list[int]:
    return [int(row["index"]) for row in _guest_targets()]


def _guest_target_for_index(player_index: int) -> dict[str, Any] | None:
    idx = int(player_index)
    return next((row for row in _guest_targets() if int(row["index"]) == idx), None)


def _build_cycle_queue() -> list[str]:
    jobs: list[str] = []
    # Shinies / phosphene world dump first so guests can loot while boosts run.
    if _cfg.get("drop_shinies"):
        jobs.append("drop_shinies")
    if _cfg.get("max_all"):
        jobs.append("max_all")
    if _cfg.get("bank_space"):
        jobs.append("bank_space")
    if _cfg.get("cosmetics"):
        if _cfg.get("repeat_heavy") or "cosmetics" not in _heavy_done:
            jobs.append("cosmetics")
    guests_only = bool(_cfg.get("progression_guests_only"))
    guest_targets = _guest_targets() if guests_only else []
    if _cfg.get("challenges"):
        if guests_only:
            for guest in guest_targets:
                done = _guest_progress_done.get(str(guest["key"]), set())
                if _cfg.get("repeat_heavy") or "challenges" not in done:
                    jobs.append(f"challenges@{int(guest['index'])}")
        elif _cfg.get("repeat_heavy") or "challenges" not in _heavy_done:
            jobs.append("challenges")
    if _cfg.get("uvhm"):
        if guests_only:
            for guest in guest_targets:
                done = _guest_progress_done.get(str(guest["key"]), set())
                if _cfg.get("repeat_heavy") or "uvhm" not in done:
                    jobs.append(f"uvhm@{int(guest['index'])}")
        elif _cfg.get("repeat_heavy") or "uvhm" not in _heavy_done:
            jobs.append("uvhm")
    return jobs


def _arm_kick_timers(now: float) -> None:
    if not _cfg.get("auto_kick"):
        return
    delay = float(_cfg.get("kick_delay_sec") or 180)
    if _session_dropped_items or _cfg.get("drop_shinies"):
        delay += float(_cfg.get("kick_drop_bonus_sec") or 240)
    for idx in _guest_indices():
        if idx in _kick_armed_indices:
            continue
        _kick_armed_indices.add(idx)
        _kick_at[idx] = now + delay
        _log(f"Kick timer armed for guest index {idx} in {int(delay)}s.")


def _tick_kick_timers(now: float) -> None:
    if not _cfg.get("auto_kick"):
        _kick_at.clear()
        return
    live = set(_guest_indices())
    # Guest left — drop their timer and move on (do not stop Auto Lobby).
    for idx in list(_kick_at.keys()):
        if idx not in live:
            _kick_at.pop(idx, None)
            _kick_armed_indices.discard(idx)
            _log(f"Guest index {idx} left — kick timer cleared.")
    from .bridge_actions_extended import party_kick

    for idx, deadline in list(_kick_at.items()):
        if now < deadline:
            continue
        _kick_at.pop(idx, None)
        try:
            result = party_kick({"player_index": idx, "reason": "Auto Lobby — session complete"})
            _set_msg(str(result.get("message") or f"Kicked guest index {idx}."))
        except Exception as exc:
            _set_msg(f"Kick index {idx} failed: {exc!r}")


def _run_step(job: str) -> None:
    global _watching_job, _session_dropped_items
    job_key = str(job or "")
    job, guest_idx = _job_parts(job_key)
    from .backend_actions import max_all
    from .bridge_actions_extended import (
        challenge_bulk_start,
        devperk_activate,
        inventory_set_sizes,
        shiny_drop_all,
        uvhm_start,
        uvhm_start_all,
    )

    if job == "max_all":
        result = max_all({})
        _set_msg(str(result.get("message") or "MAX ALL done."))
        return
    if job == "bank_space":
        result = inventory_set_sizes(
            {
                "backpack_size": int(_cfg.get("backpack_size") or 500),
                "bank_size": int(_cfg.get("bank_size") or 500),
                "scope": "target",
            }
        )
        _set_msg(str(result.get("message") or "Bank / backpack sized."))
        return
    if job == "cosmetics":
        result = devperk_activate({"perk_index": 4})
        if result.get("ok", True):
            _heavy_done.add("cosmetics")
        _set_msg(str(result.get("message") or "Cosmetics + hover drives unlocked."))
        return
    if job == "challenges":
        if _progression_busy():
            _queue.insert(0, job_key)
            _set_msg("Waiting — another progression job is still running.")
            return
        guest = _guest_target_for_index(guest_idx) if guest_idx is not None else None
        if guest_idx is not None and guest is None:
            _set_msg(f"Guest index {guest_idx} left before Challenges started — skipped safely.")
            return
        try:
            from . import hold_session

            hold_session.arm_for_job("auto_lobby")
        except Exception:
            pass
        if guest_idx is not None:
            tidx = int(guest_idx)
        else:
            # Boost-target aware: All players → -1, else current target index.
            try:
                from .backend_actions import get_target_player_index

                tidx = int(get_target_player_index())
            except Exception:
                tidx = 0
        result = challenge_bulk_start(
            {"category": "All non-UVHM", "confirmed": True, "player_index": tidx}
        )
        if result.get("ok", True):
            if guest is not None:
                _guest_progress_done.setdefault(str(guest["key"]), set()).add("challenges")
            else:
                _heavy_done.add("challenges")
            _watching_job = job_key
            _set_msg(str(result.get("message") or "Challenges started."))
        else:
            _set_msg(str(result.get("message") or "Challenges failed to start — will retry next cycle."))
        return
    if job == "uvhm":
        if _progression_busy():
            _queue.insert(0, job_key)
            _set_msg("Waiting — another progression job is still running.")
            return
        guest = _guest_target_for_index(guest_idx) if guest_idx is not None else None
        if guest_idx is not None and guest is None:
            _set_msg(f"Guest index {guest_idx} left before UVHM started — skipped safely.")
            return
        try:
            from . import hold_session

            hold_session.arm_for_job("auto_lobby")
        except Exception:
            pass
        if guest_idx is not None:
            result = uvhm_start(
                {"confirmed": True, "max_rank": 7, "player_index": int(guest_idx)}
            )
        else:
            # Default remains lobby-wide UVHM (skips leavers).
            result = uvhm_start_all({"confirmed": True, "max_rank": 7})
        if result.get("ok", True):
            if guest is not None:
                _guest_progress_done.setdefault(str(guest["key"]), set()).add("uvhm")
            else:
                _heavy_done.add("uvhm")
            _watching_job = job_key
            _set_msg(str(result.get("message") or "UVHM started."))
        else:
            _set_msg(str(result.get("message") or "UVHM failed to start — will retry next cycle."))
        return
    if job == "drop_shinies":
        if _progression_busy():
            _queue.insert(0, job)
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
            _watching_job = "drop_shinies"
        _set_msg(str(result.get("message") or "Drop All Shinies started (no shape)."))
        return
    _set_msg(f"Unknown job {job!r}.")


def tick(now: float | None = None) -> None:
    """One small step per host tick. Safe to call often."""
    global _next_cycle_at, _queue, _step_at, _current_job, _watching_job
    global _cycle_total, _cycle_done, _next_drip_at, _cycle_finished_once
    global _drip_phase, _drip_drop_at
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
    _tick_kick_timers(now)
    try:
        _tick_drip_followup(now)
    except Exception as exc:
        _cfg["item_drip"] = False
        _drip_phase = ""
        _drip_drop_at = 0.0
        _next_drip_at = 0.0
        save()
        _set_msg(
            f"Item drip stopped and disabled after spill follow-up failed: {exc!r}. "
            "No more items will be mailed until you re-enable it."
        )

    if _watching_job and not _progression_busy():
        finished = str(_watching_job)
        _watching_job = ""
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
            # Let GZO drip fire during the post-heavy rest (not only after a full interval).
            if _cfg.get("item_drip") and not _drip_phase:
                soon = now + 12.0
                if _next_drip_at <= 0 or _next_drip_at > soon:
                    _next_drip_at = soon
            _set_msg(f"{_job_label(finished)} done — next cycle in {int(max(0, gap))}s.")

    # Independent mail drip timer (does not block the boost queue).
    # Never drip while a heavy progression job is live — mail+challenges stacks crash hosts.
    if (
        _cfg.get("item_drip")
        and not _drip_phase
        and not _queue
        and not _watching_job
        and not _progression_busy()
    ):
        if _next_drip_at <= 0:
            # First drip waits a short beat after Start (not the full interval).
            _next_drip_at = now + min(45.0, float(_cfg.get("item_drip_interval_sec") or 120))
        elif now >= _next_drip_at:
            try:
                _run_item_drip()
            except Exception as exc:
                _set_msg(f"item_drip failed: {exc!r}")
            # If mail is still busy / drip follow-up pending, retry sooner; else full interval.
            retry = (
                20.0
                if (_serial_delivery_busy() or _drip_phase)
                else float(_cfg.get("item_drip_interval_sec") or 120)
            )
            _next_drip_at = now + max(_MIN_DRIP_SEC, retry)

    if _queue:
        if now < _step_at:
            return
        # Do not start the next queued step while a watched heavy job is still live.
        if _watching_job or _progression_busy():
            if now >= _next_cycle_at:
                _next_cycle_at = now + 5.0
                label = _job_label(_watching_job) if _watching_job else "progression"
                _set_msg(f"Waiting on {label}…")
            return
        job = _queue.pop(0)
        _current_job = job
        _set_msg(f"Step: {_job_label(job)}…")
        try:
            _run_step(job)
        except Exception as exc:
            _set_msg(f"{job} failed: {exc!r}")
        _cycle_done = min(int(_cycle_total), int(_cycle_done) + 1)
        _current_job = ""
        gap = _HEAVY_STEP_GAP_SEC if _is_heavy_job(job) else _STEP_GAP_SEC
        _step_at = now + gap
        if not _queue and not _progression_busy() and not _watching_job:
            wait = _clamp_interval(_cfg.get("interval_sec"))
            _next_cycle_at = now + wait
            _cycle_finished_once = True
            _arm_kick_timers(now)
            _set_msg(f"Cycle done — next in {int(wait)}s.")
        return

    if _watching_job or _progression_busy() or _drip_phase:
        if _drip_phase:
            return
        if now >= _next_cycle_at:
            _next_cycle_at = now + 5.0
            if _watching_job:
                _set_msg(f"Waiting on {_job_label(_watching_job)}…")
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
            and (_cfg.get("challenges") or _cfg.get("uvhm"))
        )
        _next_cycle_at = now + (3.0 if guest_watch else _clamp_interval(_cfg.get("interval_sec")))
        _cycle_total = 0
        _cycle_done = 0
        if guest_watch:
            guests = _guest_targets()
            if guests:
                _set_msg("Guest progression complete — watching for newly joined guests.")
            else:
                _set_msg("Guest-only progression armed — host skipped; waiting for guests to join.")
        elif _cfg.get("item_drip") or _cfg.get("auto_kick"):
            _set_msg("Idle boosts — drip / kick timers still active.")
        else:
            _set_msg("Nothing selected — waiting.")
        return
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
