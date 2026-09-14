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
_MIN_DRIP_SEC = 60.0
_MIN_KICK_SEC = 30.0
_MAX_DRIP_COUNT = 10

_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "interval_sec": _DEFAULT_INTERVAL_SEC,
    "max_all": True,
    "cosmetics": False,
    "challenges": False,
    "uvhm": False,
    "bank_space": False,
    "backpack_size": 500,
    "bank_size": 500,
    "drop_shinies": False,
    "repeat_heavy": False,
    # Keep guests from yanking host to title / lobby while Auto Lobby runs.
    "block_menu_pull": True,
    # Mail drip between cycles (mailbox — not world spawn). GZO = community codes.
    "item_drip": False,
    "item_drip_mode": "random_gzo",  # random_gzo | pack
    "item_drip_listing": "Legit",  # Legit | Modded | All
    "item_drip_pack": "",
    "item_drip_count": 3,
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
    "item_drip": "Item drip (mail)",
}

_BOOL_KEYS = (
    "enabled",
    "max_all",
    "cosmetics",
    "challenges",
    "uvhm",
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
_next_drip_at = 0.0
_session_dropped_items = False
_kick_at: dict[int, float] = {}
_kick_armed_indices: set[int] = set()
_cycle_finished_once = False


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
    count = int(_cfg.get("item_drip_count") or 3)
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

    listing = str(_cfg.get("item_drip_listing") or "Legit")
    try:
        from .bridge_catalog import catalog_gzo

        result = catalog_gzo({"listing": listing, "limit": 400, "search": ""})
    except Exception as exc:
        _log(f"Drip GZO read failed: {exc!r}")
        return []
    rows = list(result.get("rows") or []) if isinstance(result, dict) else []
    serials = [
        str(r.get("serial") or "").strip()
        for r in rows
        if isinstance(r, dict) and str(r.get("serial") or "").strip()
    ]
    if not serials:
        return []
    random.shuffle(serials)
    return serials[:count]


def _run_item_drip() -> None:
    global _session_dropped_items
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

    result = deliver_serials(
        {
            "serials": serials,
            "count": 1,
            "level_override": "yes",
            "level": int(_cfg.get("item_drip_level") or 50),
            "mode": "all",
            "open_rewards": False,
        }
    )
    ok = bool(result.get("ok", True))
    if ok:
        _session_dropped_items = True
        _set_msg(
            str(
                result.get("message")
                or f"GZO drip mailed {len(serials)} code(s) to the lobby (Reward Center)."
            )
        )
    else:
        _set_msg(str(result.get("message") or "Item drip mail failed."))


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
    if now - _log_at < 0.4:
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
    listing = str(merged.get("item_drip_listing") or "Legit").strip()
    if listing.lower() not in ("legit", "modded", "all"):
        listing = "Legit"
    else:
        listing = listing[:1].upper() + listing[1:].lower()
        if listing.lower() == "all":
            listing = "All"
    merged["item_drip_listing"] = listing
    merged["item_drip_pack"] = str(merged.get("item_drip_pack") or "").strip()
    try:
        merged["item_drip_count"] = max(1, min(_MAX_DRIP_COUNT, int(merged.get("item_drip_count") or 3)))
    except Exception:
        merged["item_drip_count"] = 3
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
    return _JOB_LABELS.get(key, key or "—")


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
    kick_left = []
    now = time.monotonic()
    for idx, deadline in sorted(_kick_at.items()):
        kick_left.append({"player_index": idx, "seconds": max(0.0, deadline - now)})
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
    _kick_at.clear()
    _kick_armed_indices.clear()
    _session_dropped_items = False
    _cycle_finished_once = False
    _next_drip_at = 0.0


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


def _guest_indices() -> list[int]:
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
        if bool(row.get("is_host")) or idx < 0:
            continue
        out.append(idx)
    return out


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
    if _cfg.get("challenges"):
        if _cfg.get("repeat_heavy") or "challenges" not in _heavy_done:
            jobs.append("challenges")
    if _cfg.get("uvhm"):
        if _cfg.get("repeat_heavy") or "uvhm" not in _heavy_done:
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
    from .backend_actions import max_all
    from .bridge_actions_extended import (
        challenge_bulk_start,
        devperk_activate,
        inventory_set_sizes,
        shiny_drop_all,
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
        _heavy_done.add("cosmetics")
        _set_msg(str(result.get("message") or "Cosmetics + hover drives unlocked."))
        return
    if job == "challenges":
        if _progression_busy():
            _queue.insert(0, job)
            _set_msg("Waiting — another progression job is still running.")
            return
        try:
            from . import hold_session

            hold_session.arm_for_job("auto_lobby")
        except Exception:
            pass
        result = challenge_bulk_start({"category": "All non-UVHM"})
        _heavy_done.add("challenges")
        _watching_job = "challenges"
        _set_msg(str(result.get("message") or "Challenges started."))
        return
    if job == "uvhm":
        if _progression_busy():
            _queue.insert(0, job)
            _set_msg("Waiting — another progression job is still running.")
            return
        try:
            from . import hold_session

            hold_session.arm_for_job("auto_lobby")
        except Exception:
            pass
        # Lobby-wide UVHM so guests actually finish ranks 1–7.
        result = uvhm_start_all({"confirmed": True, "max_rank": 7})
        _heavy_done.add("uvhm")
        _watching_job = "uvhm"
        _set_msg(str(result.get("message") or "UVHM started."))
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

    if _watching_job and not _progression_busy():
        _watching_job = ""
        if not _queue:
            _cycle_finished_once = True
            _arm_kick_timers(now)
            gap = _clamp_interval(_cfg.get("interval_sec"))
            if now >= _next_cycle_at:
                _next_cycle_at = now + gap
            _set_msg(f"Heavy job done — next cycle in {int(max(0, _next_cycle_at - now))}s.")

    # Independent mail drip timer (does not block the boost queue).
    if _cfg.get("item_drip") and not _queue and not _progression_busy():
        if _next_drip_at <= 0:
            _next_drip_at = now + float(_cfg.get("item_drip_interval_sec") or 120)
        elif now >= _next_drip_at:
            try:
                _run_item_drip()
            except Exception as exc:
                _set_msg(f"item_drip failed: {exc!r}")
            # If mail is still busy, retry sooner; otherwise wait the full drip interval.
            retry = 20.0 if _serial_delivery_busy() else float(_cfg.get("item_drip_interval_sec") or 120)
            _next_drip_at = now + max(_MIN_DRIP_SEC, retry)

    if _queue:
        if now < _step_at:
            return
        job = _queue.pop(0)
        _current_job = job
        try:
            _run_step(job)
        except Exception as exc:
            _set_msg(f"{job} failed: {exc!r}")
        _cycle_done = min(int(_cycle_total), int(_cycle_done) + 1)
        _current_job = ""
        _step_at = now + _STEP_GAP_SEC
        if not _queue and not _progression_busy():
            gap = _clamp_interval(_cfg.get("interval_sec"))
            _next_cycle_at = now + gap
            _cycle_finished_once = True
            _arm_kick_timers(now)
            _set_msg(f"Cycle done — next in {int(gap)}s.")
        return

    if _watching_job or _progression_busy():
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
        _next_cycle_at = now + _clamp_interval(_cfg.get("interval_sec"))
        _cycle_total = 0
        _cycle_done = 0
        if _cfg.get("item_drip") or _cfg.get("auto_kick"):
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
