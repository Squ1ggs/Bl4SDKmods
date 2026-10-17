"""BMS group spawner — sequenced Char_* packs on SQBT's bundled mob spawner."""
from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any

_SAVE_NAME = "Squ1ggsBoostingTools_encounters.json"
_MAX_WAVES = 200
_MAX_COUNT = 80
_MAX_WAVE_TOTAL = 80
_MAX_TYPES = 16
_SPAWN_GRACE_S = 3.0
_SPAWN_ARM_S = 14.0
_TICK_MIN_S = 0.12
_DEATH_QUIET_S = 1.4

_ADVANCE = ("on_clear", "timed", "manual")
_LOOP = ("off", "last", "all")

_options: dict[str, Any] = {}
_waves: list[dict[str, Any]] = []
_running = False
_complete = False
_wave_index = 0
_message = "Idle — add groups, then Start."
_jobs: deque[dict[str, Any]] = deque()
_spawn_phase = False
_spawn_next_at = 0.0
_spawn_in_flight = False
_tick_in_flight = False
_last_tick_at = 0.0
_last_death_at = 0.0
_pre_keys: set[str] = set()
_wave_keys: set[str] = set()
_expected = 0
_grace_until = 0.0
_seen_alive = False
_watch_until = 0.0
_timed_until = 0.0
_between_until = 0.0


def _clamp_int(value: object, lo: int, hi: int, default: int) -> int:
    try:
        n = int(value)  # type: ignore[arg-type]
    except Exception:
        return default
    return max(lo, min(hi, n))


def _clamp_float(value: object, lo: float, hi: float, default: float) -> float:
    try:
        n = float(value)  # type: ignore[arg-type]
    except Exception:
        return default
    if n != n:
        return default
    return max(lo, min(hi, n))


def default_options() -> dict[str, Any]:
    return {
        "advance": "on_clear",
        "loop": "off",
        "timed_seconds": 25.0,
        "between_waves": 1.5,
        "first_delay": 0.4,
        "burst": 2,
        "stagger": 0.45,
        "distance": 900.0,
        "spacing": 125.0,
        "aggro_mode": "attack_me",
        "spawn_anchor": "local",
        "player_index": 0,
    }


def _normalize_options(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = default_options()
    src = raw if isinstance(raw, dict) else {}
    advance = str(src.get("advance") or base["advance"]).strip().lower()
    if advance not in _ADVANCE:
        advance = "on_clear"
    loop = str(src.get("loop") or base["loop"]).strip().lower()
    if loop not in _LOOP:
        loop = "off"
    base.update(
        {
            "advance": advance,
            "loop": loop,
            "timed_seconds": _clamp_float(src.get("timed_seconds"), 5.0, 300.0, 25.0),
            "between_waves": _clamp_float(src.get("between_waves"), 0.0, 30.0, 1.5),
            "first_delay": _clamp_float(src.get("first_delay"), 0.0, 15.0, 0.4),
            "burst": _clamp_int(src.get("burst"), 1, 8, 2),
            "stagger": _clamp_float(src.get("stagger"), 0.15, 5.0, 0.45),
            "distance": _clamp_float(src.get("distance") or src.get("spawn_distance"), 600.0, 4000.0, 900.0),
            "spacing": _clamp_float(src.get("spacing") or src.get("spawn_spacing"), 40.0, 800.0, 125.0),
            "aggro_mode": str(src.get("aggro_mode") or "attack_me").strip() or "attack_me",
            "spawn_anchor": str(src.get("spawn_anchor") or "local").strip().lower() or "local",
            "player_index": _clamp_int(src.get("player_index") or src.get("party_index"), 0, 3, 0),
        }
    )
    return base


def _normalize_entry(raw: object) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    code = str(raw.get("code") or raw.get("actor_id") or raw.get("actor") or "").strip()
    if not code:
        return None
    count = _clamp_int(raw.get("count"), 1, _MAX_COUNT, 1)
    return {"code": code, "count": count}


def _normalize_wave(raw: object) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    entries: list[dict[str, Any]] = []
    raw_entries = raw.get("entries")
    if isinstance(raw_entries, list) and raw_entries:
        for item in raw_entries:
            entry = _normalize_entry(item)
            if entry is None:
                continue
            matched = next((e for e in entries if e["code"].lower() == entry["code"].lower()), None)
            if matched is not None:
                matched["count"] = _clamp_int(int(matched["count"]) + int(entry["count"]), 1, _MAX_COUNT, 1)
            else:
                entries.append(entry)
    else:
        entry = _normalize_entry(raw)
        if entry is not None:
            entries.append(entry)
    if not entries:
        return None
    entries = entries[:_MAX_TYPES]
    total = 0
    trimmed: list[dict[str, Any]] = []
    for entry in entries:
        room = _MAX_WAVE_TOTAL - total
        if room <= 0:
            break
        n = min(int(entry["count"]), room)
        trimmed.append({"code": entry["code"], "count": n})
        total += n
    label = str(raw.get("label") or "").strip()
    if not label:
        label = ", ".join(f"{e['code']}×{e['count']}" for e in trimmed)
    return {"label": label[:96], "entries": trimmed, "count": total}


def _burst_sizes(total: int, burst: int) -> list[int]:
    total = max(1, int(total))
    burst = max(1, int(burst))
    out: list[int] = []
    left = total
    flip = False
    while left > 0:
        size = min(burst if not flip else max(1, burst - 1), left)
        out.append(size)
        left -= size
        flip = not flip
    return out


def _build_jobs(wave: dict[str, Any], options: dict[str, Any]) -> deque[dict[str, Any]]:
    burst = int(options.get("burst") or 2)
    jobs: deque[dict[str, Any]] = deque()
    # Round-robin types so a mixed wave does not dump one species first.
    queues = [deque(_burst_sizes(int(e["count"]), burst)) for e in wave["entries"]]
    codes = [str(e["code"]) for e in wave["entries"]]
    while any(queues):
        for idx, q in enumerate(queues):
            if not q:
                continue
            jobs.append({"code": codes[idx], "count": int(q.popleft())})
    return jobs


def status() -> dict[str, Any]:
    return {
        "ok": True,
        "running": _running,
        "complete": _complete,
        "message": _message,
        "wave_index": _wave_index,
        "wave_total": len(_waves),
        "alive": len(_live_keys()),
        "expected": _expected,
        "spawn_phase": _spawn_phase,
        "options": dict(_options or default_options()),
        "waves": list(_waves),
        "saves": [row["name"] for row in _load_saves()],
    }


def set_options(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global _options, _message
    _options = _normalize_options({**( _options or default_options()), **(payload or {})})
    _message = "Group options updated."
    return status()


def set_plan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global _waves, _options, _message, _running, _complete, _wave_index
    payload = payload or {}
    if "options" in payload or any(k in payload for k in default_options()):
        raw_opts = payload.get("options") if isinstance(payload.get("options"), dict) else payload
        _options = _normalize_options(raw_opts if isinstance(raw_opts, dict) else {})
    waves_in = payload.get("waves")
    if isinstance(waves_in, list):
        cleaned: list[dict[str, Any]] = []
        for raw in waves_in[:_MAX_WAVES]:
            wave = _normalize_wave(raw)
            if wave is not None:
                cleaned.append(wave)
        _waves = cleaned
    _running = False
    _complete = False
    _wave_index = 0
    _jobs.clear()
    _message = f"Plan set ({len(_waves)} group(s))."
    return status()


def add_wave(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    codes = payload.get("codes")
    if isinstance(codes, str):
        codes = [codes]
    entries: list[dict[str, Any]] = []
    if isinstance(codes, list) and codes:
        count = _clamp_int(payload.get("count"), 1, _MAX_COUNT, 1)
        for code in codes:
            token = str(code or "").strip()
            if token:
                entries.append({"code": token, "count": count})
    else:
        wave = _normalize_wave(payload)
        if wave is not None:
            _waves.append(wave)
            return status()
    wave = _normalize_wave({"entries": entries, "label": str(payload.get("label") or "")})
    if wave is None:
        return {"ok": False, "message": "Tick at least one Char_* (or mix) to add a wave."}
    if len(_waves) >= _MAX_WAVES:
        return {"ok": False, "message": f"Cap is {_MAX_WAVES} waves."}
    _waves.append(wave)
    return status()


def remove_wave(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    idx = _clamp_int(payload.get("wave_index") if payload.get("wave_index") is not None else payload.get("index"), 0, 10_000, -1)
    if idx < 0 or idx >= len(_waves):
        return {"ok": False, "message": "Pick a wave to remove."}
    _waves.pop(idx)
    return status()


def clear_plan(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global _waves, _running, _complete, _wave_index, _message
    stop({})
    _waves = []
    _wave_index = 0
    _complete = False
    _message = "Group list cleared."
    return status()


def _snapshot_keys() -> set[str]:
    try:
        from .embedded_bms.spawn_core import player_pawn_keys, snapshot_character_keys

        return snapshot_character_keys(exclude_keys=player_pawn_keys())
    except Exception:
        return set()


def _live_keys() -> set[str]:
    if not _wave_keys:
        return set()
    now = _snapshot_keys()
    return {key for key in _wave_keys if key in now}


def _begin_wave(index: int, *, delay: float) -> None:
    global _spawn_phase, _spawn_next_at, _expected, _grace_until, _seen_alive
    global _watch_until, _timed_until, _pre_keys, _wave_keys, _message, _wave_index
    _wave_index = index
    wave = _waves[index]
    opts = _options or default_options()
    _jobs.clear()
    _jobs.extend(_build_jobs(wave, opts))
    _expected = int(wave.get("count") or 0)
    _pre_keys = _snapshot_keys()
    _wave_keys = set()
    _seen_alive = False
    _spawn_phase = True
    now = time.monotonic()
    _spawn_next_at = now + max(0.0, float(delay))
    _grace_until = 0.0
    _watch_until = 0.0
    _timed_until = 0.0
    _message = f"Group {index + 1}/{len(_waves)}: spawning {wave.get('label') or ''}."


def start(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global _running, _complete, _message, _options, _between_until
    if payload:
        merged = {**(_options or default_options()), **payload}
        if isinstance(payload.get("options"), dict):
            merged.update(payload["options"])
        _options = _normalize_options(merged)
        if isinstance(payload.get("waves"), list):
            set_plan(payload)
    if not _waves:
        return {"ok": False, "message": "Add at least one wave first."}
    if not _host_ok():
        return {"ok": False, "message": "Host / in-world session required for encounters."}
    stop({"keep_plan": True})
    _complete = False
    _running = True
    _between_until = 0.0
    opts = _options or default_options()
    _begin_wave(0, delay=float(opts.get("first_delay") or 0.4))
    return status()


def stop(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global _running, _spawn_phase, _message, _spawn_in_flight
    _running = False
    _spawn_phase = False
    _jobs.clear()
    _spawn_in_flight = False
    if not (payload or {}).get("keep_plan"):
        _message = "Groups stopped."
    return status()


def next_wave(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not _waves:
        return {"ok": False, "message": "No waves in the plan."}
    if not _running:
        start({})
        return status()
    _advance(force=True)
    return status()


def clear_live(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """User-opt-in: destroy BMS-tracked mobs. Not used on wave advance."""
    stop({})
    try:
        from .embedded_bms import get_controller

        destroyed, failed = get_controller().clear_tracked()
        return {**status(), "ok": True, "message": f"Cleared live mobs (destroyed={destroyed}, failed={failed})."}
    except Exception as exc:
        return {"ok": False, "message": f"Clear live failed: {exc!r}"}


def _host_ok() -> bool:
    try:
        from . import world_spawn

        return bool(world_spawn.is_host())
    except Exception:
        return False


def _spawn_job(job: dict[str, Any]) -> None:
    global _message
    opts = _options or default_options()
    try:
        from .embedded_bms import get_controller
        from .embedded_bms.spawn_core import disable_world_spawn_budget

        disable_world_spawn_budget(True)
        controller = get_controller()
        ui = controller.ui
        ui.aggro_mode = str(opts.get("aggro_mode") or "attack_me")
        ui.spawn_anchor = str(opts.get("spawn_anchor") or "local")
        ui.party_index = int(opts.get("player_index") or 0)
        ui.spawn_distance = float(opts.get("distance") or 900.0)
        ui.spawn_spacing = float(opts.get("spacing") or 125.0)
        ok, msg = controller.spawn_mob(str(job["code"]), count=int(job["count"]), defer=True)
        _message = msg if ok else f"Spawn failed: {msg}"
    except Exception as exc:
        _message = f"Spawn failed: {exc!r}"


def _finish_spawn_phase() -> None:
    global _spawn_phase, _grace_until, _watch_until, _timed_until, _message
    _spawn_phase = False
    now = time.monotonic()
    _grace_until = now + _SPAWN_GRACE_S
    _watch_until = now + _SPAWN_ARM_S
    opts = _options or default_options()
    if opts.get("advance") == "timed":
        _timed_until = now + float(opts.get("timed_seconds") or 25.0)
    _message = f"Group {_wave_index + 1}: in the world — waiting ({opts.get('advance')})."


def _advance(*, force: bool = False) -> None:
    global _complete, _running, _message, _last_death_at, _between_until
    _last_death_at = time.monotonic()
    opts = _options or default_options()
    nxt = _wave_index + 1
    if nxt < len(_waves):
        delay = 0.0 if force else float(opts.get("between_waves") or 0.0)
        _begin_wave(nxt, delay=max(delay, _DEATH_QUIET_S if not force else 0.15))
        return
    loop = str(opts.get("loop") or "off")
    if loop == "last" and _waves:
        _begin_wave(len(_waves) - 1, delay=float(opts.get("between_waves") or 1.5))
        _message = "Loop last wave."
        return
    if loop == "all" and _waves:
        _begin_wave(0, delay=float(opts.get("between_waves") or 1.5))
        _message = "Loop encounter from wave 1."
        return
    _running = False
    _complete = True
    _spawn_phase = False
    _jobs.clear()
    _message = "Groups complete."
    _between_until = 0.0


def tick() -> None:
    global _tick_in_flight, _last_tick_at, _spawn_in_flight, _spawn_next_at
    global _seen_alive, _wave_keys, _message
    if not _running or _tick_in_flight:
        return
    now = time.monotonic()
    if now - _last_tick_at < _TICK_MIN_S:
        return
    _last_tick_at = now
    _tick_in_flight = True
    try:
        if _spawn_in_flight:
            return
        if _spawn_phase:
            if now < _spawn_next_at:
                return
            if not _jobs:
                _finish_spawn_phase()
                return
            job = _jobs.popleft()
            _spawn_in_flight = True
            try:
                _spawn_job(job)
            finally:
                _spawn_in_flight = False
            _spawn_next_at = time.monotonic() + float((_options or default_options()).get("stagger") or 0.45)
            return
        live = _snapshot_keys()
        new_keys = live - _pre_keys
        if new_keys:
            _wave_keys |= new_keys
            _seen_alive = True
        alive = {key for key in _wave_keys if key in live}
        opts = _options or default_options()
        advance = str(opts.get("advance") or "on_clear")
        if advance == "manual":
            _message = f"Group {_wave_index + 1}: {len(alive)} alive — press Next group."
            return
        if advance == "timed" and _timed_until and now >= _timed_until:
            _advance()
            return
        if now < _grace_until:
            return
        if _seen_alive and not alive:
            _advance()
            return
        if not _seen_alive and _watch_until and now >= _watch_until:
            _message = f"Group {_wave_index + 1}: never saw live AI — advancing."
            _advance()
            return
        _message = f"Group {_wave_index + 1}: {len(alive)}/{_expected} alive."
    except Exception as exc:
        _message = f"Group tick: {exc!r}"
    finally:
        _tick_in_flight = False


def _save_paths() -> list[Path]:
    paths = [
        Path.home() / "Documents" / "My Games" / "Borderlands 4" / "Saved" / _SAVE_NAME,
        Path(__file__).resolve().parent / _SAVE_NAME,
    ]
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def _load_saves() -> list[dict[str, Any]]:
    for path in _save_paths():
        try:
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            plans = data.get("plans") if isinstance(data, dict) else None
            if isinstance(plans, list):
                return [p for p in plans if isinstance(p, dict) and str(p.get("name") or "").strip()]
        except Exception:
            continue
    return []


def _write_saves(plans: list[dict[str, Any]]) -> Path:
    path = _save_paths()[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "plans": plans}, indent=2), encoding="utf-8")
    return path


def save_named(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    name = str((payload or {}).get("name") or "").strip()[:64]
    if not name:
        return {"ok": False, "message": "Name the encounter before saving."}
    if not _waves:
        return {"ok": False, "message": "Nothing to save."}
    plans = [p for p in _load_saves() if str(p.get("name")) != name]
    plans.append({"name": name, "options": _options or default_options(), "waves": list(_waves)})
    _write_saves(plans)
    return {**status(), "message": f"Saved encounter '{name}'."}


def load_named(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    name = str((payload or {}).get("name") or "").strip()
    for plan in _load_saves():
        if str(plan.get("name")) == name:
            return set_plan(plan)
    return {"ok": False, "message": f"No saved encounter named '{name}'."}


def delete_named(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    name = str((payload or {}).get("name") or "").strip()
    plans = [p for p in _load_saves() if str(p.get("name")) != name]
    _write_saves(plans)
    return {**status(), "message": f"Deleted '{name}'."}


def catalog_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, wave in enumerate(_waves):
        rows.append(
            {
                "id": f"wave:{idx}",
                "wave_index": idx,
                "title": f"Group {idx + 1}: {wave.get('label')}",
                "label": wave.get("label") or "",
                "count": wave.get("count") or 0,
            }
        )
    return rows
