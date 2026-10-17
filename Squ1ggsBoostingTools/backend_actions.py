"""Live game actions for the Squ1ggs Boosting Tools localhost bridge (no BLImGui required)."""
from __future__ import annotations

from typing import Any

from mods_base import get_pc

from .dev_tools import (
    copy_debug_cam_location,
    damage_looked_at_actor,
    debug_cam_info,
    destroy_looked_at_actor,
    enable_debug_cam,
    force_disable_debug_cam,
    get_debug_cam_speed,
    inspect_looked_at_actor,
    set_debug_cam_speed,
    set_freecam_distance,
    set_freecam_offset,
    teleport_pawn_to_debug_cam,
)
from .party_helpers import (
    _gbc_is_listen_host_world,
    _gbc_resolve_player_display_name,
    _gbc_session_world_and_gamestate,
    _list_party_players,
    _player_identity_for_ps,
)
from .player_economy import (
    _CURRENCY_KIND_ALIASES,
    _EXPERIENCE_TRACK_ALIASES,
    _MAX_WALLET_AMOUNT,
    _do_set_currency_absolute,
    _get_experience_level_via_bp,
    _give_currency_on_pc_detailed,
    _normalize_track_key,
    _resolve_target_pc_for_index,
    _set_experience_level_via_bp,
    max_all_for_target,
)
from .spawn_deferred import gameplay_ready
from . import spawn_targets
from .travel import travel_to_map, travel_to_preset, travel_to_station
from ._mod_version import __version__ as _MOD_VERSION
_target_player_index: int = 0
_last_action: str = ""
_last_error: str = ""
_extended_import_error: str = ""


def _fgbx_ok() -> bool:
    try:
        from .currency_give import fgbx_def_ptr_api_ok

        return bool(fgbx_def_ptr_api_ok())
    except Exception:
        return False


def _runtime_log_status() -> dict[str, Any]:
    try:
        from . import runtime_log

        return dict(runtime_log.status_blob())
    except Exception as exc:
        return {"path": "", "error": repr(exc)}


def _auto_lobby_status() -> dict[str, Any]:
    try:
        from . import auto_lobby

        return dict(auto_lobby.status())
    except Exception as exc:
        return {"enabled": False, "error": repr(exc), "last": ""}


def _ok_status(message: str, st: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge status dict into _ok without double-passing message/ok."""
    extra = dict(st or {})
    extra.pop("message", None)
    extra.pop("ok", None)
    return _ok(message, **extra)


def auto_lobby_get(payload: dict[str, Any] | None = None, **_kwargs: Any) -> dict[str, Any]:
    del payload, _kwargs
    from . import auto_lobby

    return _ok_status("Auto lobby settings.", auto_lobby.status())


def auto_lobby_set(payload: dict[str, Any] | None = None, **_kwargs: Any) -> dict[str, Any]:
    from . import auto_lobby

    data = dict(payload or {})
    data.update(_kwargs)
    st = auto_lobby.apply_config(data)
    return _ok_status(str(st.get("last") or st.get("message") or "Saved."), st)


def auto_lobby_start(payload: dict[str, Any] | None = None, **_kwargs: Any) -> dict[str, Any]:
    from . import auto_lobby

    data = dict(payload or {})
    data.update(_kwargs)
    st = auto_lobby.start(data)
    return _ok_status(str(st.get("last") or st.get("message") or "Auto lobby on."), st)


def auto_lobby_stop(payload: dict[str, Any] | None = None, **_kwargs: Any) -> dict[str, Any]:
    del payload, _kwargs
    from . import auto_lobby

    st = auto_lobby.stop()
    return _ok_status(str(st.get("last") or st.get("message") or "Auto lobby off."), st)


def runtime_log_action(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dev-only: flush / tail the low-overhead crash flight log."""
    from . import runtime_log

    payload = payload or {}
    op = str(payload.get("op") or payload.get("mode") or "status").strip().lower()
    if op in ("flush", "write"):
        runtime_log.note("manual flush from EXE")
        runtime_log.flush(force=True)
        return _ok("Runtime log flushed.", **runtime_log.status_blob())
    if op in ("tail", "read"):
        try:
            limit = int(payload.get("limit") if payload.get("limit") not in (None, "") else 60)
        except Exception:
            limit = 60
        lines = runtime_log.tail(limit)
        return _ok(
            "\n".join(lines) if lines else "(empty — enable mod / run an action first)",
            lines=lines,
            **runtime_log.status_blob(),
        )
    if op in ("note", "mark"):
        msg = str(payload.get("message") or payload.get("text") or "").strip()
        if msg:
            runtime_log.note(f"EXE note: {msg}")
            runtime_log.flush(force=True)
        return _ok("Noted.", **runtime_log.status_blob())
    return _ok("Runtime log status.", **runtime_log.status_blob())


def get_target_player_index() -> int:
    """Live boost-target index (never import this int by value into other modules)."""
    return int(_target_player_index)


def _ok(message: str = "OK", **extra: Any) -> dict[str, Any]:
    return {"ok": True, "message": message, **extra}


def _fail(message: str, **extra: Any) -> dict[str, Any]:
    global _last_error
    _last_error = message
    return {"ok": False, "message": message, **extra}


def _session_label() -> str:
    world, _gs = _gbc_session_world_and_gamestate()
    if world is None:
        return "No session"
    if _gbc_is_listen_host_world(world):
        return "Listen host"
    return "Joined client"


def _player_level_for_index(index: int) -> int | None:
    """Best-effort character level for roster / Boost target labels (track 0)."""
    try:
        pc, _err = _resolve_target_pc_for_index(int(index))
    except Exception:
        return None
    if pc is None:
        return None
    fn = getattr(pc, "GetPlayerLevel", None)
    if callable(fn):
        try:
            level = int(fn() or 0)
            if level > 0:
                return level
        except Exception:
            pass
    ps = getattr(pc, "PlayerState", None)
    if ps is None:
        return None
    try:
        level = _get_experience_level_via_bp(ps, 0)
    except Exception:
        return None
    if level is None:
        return None
    try:
        level_i = int(level)
    except Exception:
        return None
    return level_i if level_i > 0 else None


def _player_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        local_ps = getattr(get_pc(), "PlayerState", None)
    except Exception:
        local_ps = None
    _world, gs = _gbc_session_world_and_gamestate()
    pa = getattr(gs, "PlayerArray", None) if gs is not None else None
    for index, name in _list_party_players():
        is_host = False
        ps = None
        if pa is not None:
            try:
                ps = pa[int(index)]
            except Exception:
                ps = None
        if local_ps is not None and ps is not None:
            is_host = ps is local_ps
        if not is_host and local_ps is None and int(index) == 0:
            is_host = True
        ident: dict[str, str] = {}
        try:
            ident = _player_identity_for_ps(ps, display_name=str(name or ""))
        except Exception:
            ident = {
                "name": str(name or ""),
                "shift_name": str(name or ""),
                "platform_name": "",
                "platform_kind": "",
            }
        display = str(ident.get("name") or name or "").strip() or str(name)
        row: dict[str, Any] = {
            "index": int(index),
            "name": display,
            "shift_name": str(ident.get("shift_name") or display),
            "platform_name": str(ident.get("platform_name") or ""),
            "platform_kind": str(ident.get("platform_kind") or ""),
            "is_host": bool(is_host),
        }
        level = _player_level_for_index(int(index))
        if level is not None:
            row["level"] = int(level)
        rows.append(row)
    return rows


def _resolve_pc(player_index: int | None = None) -> tuple[Any | None, str]:
    idx = get_target_player_index() if player_index is None else int(player_index)
    pc, err = _resolve_target_pc_for_index(idx)
    if pc is None:
        return None, err or f"No PlayerController for party index {idx}."
    return pc, ""


def set_target_player(player_index: int) -> dict[str, Any]:
    global _target_player_index
    try:
        idx = int(player_index)
    except Exception:
        return _fail("player_index must be an integer (use -1 for All players).")
    if idx < 0:
        _target_player_index = -1
        name = "All players"
        return _ok("Target set to All players.", player_index=_target_player_index, name=name)
    _target_player_index = idx
    rows = _player_rows()
    name = next((r["name"] for r in rows if r["index"] == _target_player_index), "")
    if spawn_targets.mode() == "party":
        spawn_targets.set_target("party", _target_player_index)
    return _ok(f"Target set to index {_target_player_index}.", player_index=_target_player_index, name=name)


def _payload_player_index(payload: dict[str, Any] | None) -> int | None:
    """Parse optional player_index from bridge payload; empty string means unset."""
    if not isinstance(payload, dict):
        return None
    raw = payload.get("player_index")
    if raw is None:
        return None
    if isinstance(raw, str) and not raw.strip():
        return None
    text = str(raw).strip().lower()
    if text in ("all", "everyone", "lobby", "party", "*"):
        return -1
    try:
        return int(raw)
    except Exception:
        return None


def _live_party_indices() -> list[int]:
    """Concrete lobby indices for All-players boosts (roster, with PlayerArray fallback)."""
    rows = _player_rows()
    if rows:
        return [int(r["index"]) for r in rows]
    # Roster filter can be empty mid-transition; fall back to any live PlayerArray slot.
    _world, gs = _gbc_session_world_and_gamestate()
    pa = getattr(gs, "PlayerArray", None) if gs is not None else None
    if pa is None:
        return []
    out: list[int] = []
    try:
        n = len(pa)
    except Exception:
        return []
    for idx in range(n):
        try:
            if pa[idx] is not None:
                out.append(int(idx))
        except Exception:
            continue
    return out


def _boost_target_indices(player_index: int | None = None) -> list[int]:
    """Resolve boost targets: -1 expands to every live lobby member."""
    idx = get_target_player_index() if player_index is None else int(player_index)
    if idx < 0:
        return _live_party_indices()
    return [idx]


def _boost_targets_from_payload(payload: dict[str, Any] | None = None) -> list[int]:
    """Expand payload ``player_index`` (incl. -1 / All) to concrete party indices."""
    return _boost_target_indices(_payload_player_index(payload if isinstance(payload, dict) else None))


def set_spawn_anchor(payload: dict[str, Any]) -> dict[str, Any]:
    label = spawn_targets.apply_from_payload(payload, default_party_index=_target_player_index)
    return _ok(f"Spawn location set to {label}.", spawn_anchor=spawn_targets.mode())


def _sticky_toggle_status() -> dict[str, Any]:
    out: dict[str, Any] = {
        "force_fly": False,
        "force_fly_all": False,
        "infinite_jump": False,
        "infinite_jump_all": False,
        "vehicle_jump": False,
        "noclip": False,
        "fall_through_map": False,
        "auto_apply": False,
        "shoot_sprint": False,
        "zoom_sprint": False,
        "zoom_injured": False,
        "auto_revive": False,
        "no_death_penalty": False,
        "map_fog": False,
        "hud_hidden": False,
        "fps_shown": False,
        "low_power": False,
        "photo_clean": False,
        "photo_freecam": False,
        "photo_wide": False,
        "hold_session": False,
        "god_mode": False,
        "shift_friend_autoaccept": False,
        "infinite_ammo": False,
        "no_target": False,
        "weapons_restricted": False,
        "ammo_regen": False,
        "vehicle_lock": False,
        "fly_speed": 16000.0,
        "fly_preset": "fast",
    }
    try:
        from . import mobility_runtime as mr

        idx = int(_target_player_index)
        out["force_fly"] = bool(mr.force_fly_enabled_for_index(idx if idx >= 0 else 0))
        try:
            rows = _player_rows()
            indices = [int(r.get("index", 0)) for r in rows]
            out["force_fly_all"] = bool(indices) and all(
                mr.force_fly_enabled_for_index(i) for i in indices
            )
            if idx < 0:
                out["force_fly"] = bool(out["force_fly_all"])
        except Exception:
            out["force_fly_all"] = False
        jump_on = idx in getattr(mr, "infinite_jump_indices", set()) if idx >= 0 else False
        out["infinite_jump"] = bool(jump_on)
        try:
            all_mode = bool(getattr(mr, "_infinite_jump_all_mode", False))
            rows = _player_rows()
            indices = [int(r.get("index", 0)) for r in rows]
            jump_set = {int(x) for x in (mr.infinite_jump_indices or set())}
            # Sticky all-mode must win over brief roster gaps (missing pawn → false OFF).
            out["infinite_jump_all"] = bool(all_mode) or (
                bool(indices) and all(i in jump_set for i in indices)
            )
            if idx < 0 or all_mode:
                out["infinite_jump"] = bool(out["infinite_jump_all"] or jump_on)
        except Exception:
            out["infinite_jump_all"] = bool(getattr(mr, "_infinite_jump_all_mode", False))
        out["noclip"] = bool(mr.get_noclip_enabled())
        out["fall_through_map"] = bool(mr.fall_through_enabled_for_index(idx if idx >= 0 else 0))
        try:
            rows = _player_rows()
            indices = [int(r.get("index", 0)) for r in rows]
            if idx < 0:
                out["fall_through_map"] = bool(indices) and all(
                    mr.fall_through_enabled_for_index(i) for i in indices
                )
        except Exception:
            pass
        out["auto_apply"] = bool(mr.get_auto_apply_on_load())
        out["fly_speed"] = float(mr.force_fly_speed)
        out["fly_preset"] = str(getattr(mr, "force_fly_preset", "fast") or "fast")
    except Exception:
        pass
    try:
        from . import character_flags as cf

        idx = int(_target_player_index)
        out["shoot_sprint"] = bool(cf.is_on("shoot_sprint", idx))
        out["zoom_sprint"] = bool(cf.is_on("zoom_sprint", idx))
        out["zoom_injured"] = bool(cf.is_on("zoom_injured", idx))
        out["auto_revive"] = bool(cf.is_on("auto_revive", idx))
        out["no_death_penalty"] = bool(cf.is_on("no_death_penalty", idx))
    except Exception:
        pass
    try:
        from .map_fog_hide import is_hidden as _map_fog_hidden

        out["map_fog"] = bool(_map_fog_hidden())
    except Exception:
        out["map_fog"] = False
    try:
        from .hud_visibility import is_hidden as _hud_hidden

        out["hud_hidden"] = bool(_hud_hidden())
    except Exception:
        out["hud_hidden"] = False
    try:
        from .fps_display import is_shown as _fps_shown

        out["fps_shown"] = bool(_fps_shown())
    except Exception:
        out["fps_shown"] = False
    try:
        from .host_power import is_enabled as _low_power_on

        out["low_power"] = bool(_low_power_on())
    except Exception:
        out["low_power"] = False
    try:
        from .photo_mode import active_preset as _photo_active

        active = _photo_active()
        for key in ("clean", "freecam", "wide"):
            out[f"photo_{key}"] = active == key
    except Exception:
        pass
    try:
        from .hold_session import is_enabled as _hold_session_on

        out["hold_session"] = bool(_hold_session_on())
    except Exception:
        out["hold_session"] = False
    try:
        from . import shift_friend_autoaccept as shift_aa

        out["shift_friend_autoaccept"] = bool(shift_aa.is_enabled())
    except Exception:
        out["shift_friend_autoaccept"] = False
    try:
        from . import tuning_embed as te

        eng = te.get_engine("bvm")
        out["vehicle_jump"] = bool(getattr(eng, "BVM_REPEAT_JUMP_PRESS", False))
    except Exception:
        pass
    try:
        from . import dev_tools as dt

        idx = int(_target_player_index)
        pc, _ = dt._pc_for_party_index(idx if idx >= 0 else None)
        live_god = dt.read_ulm_god_mode(pc)
        # Prefer live ULM fields so sticky UI matches the game (avoids ON/OFF thrash).
        out["god_mode"] = (
            bool(live_god)
            if live_god is not None
            else bool(dt.devperk_toggle_state(6, idx if idx >= 0 else None))
        )
        out["infinite_ammo"] = bool(dt.devperk_toggle_state(5, idx if idx >= 0 else None))
        key = dt._devperk_player_key_from_pc(pc, idx if idx >= 0 else None)
        out["weapons_restricted"] = bool(dt._weapons_restricted_sticky.get(key, False))
        out["ammo_regen"] = float(dt._ammo_regen_sticky.get(key, 0.0) or 0.0) > 0.0
        out["vehicle_lock"] = bool(dt._vehicle_lock_state.get(key, False))
        if idx < 0:
            # All players is ON only when every current member is ON. Reading
            # just the host made mixed lobbies look fully enabled.
            states: list[dict[str, bool]] = []
            for row in _player_rows():
                target = int(row["index"])
                target_pc, _ = dt._pc_for_party_index(target)
                live = dt.read_ulm_god_mode(target_pc)
                target_key = dt._devperk_player_key_from_pc(target_pc, target)
                states.append({
                    "god_mode": bool(live) if live is not None else bool(dt.devperk_toggle_state(6, target)),
                    "infinite_ammo": bool(dt.devperk_toggle_state(5, target)),
                    "weapons_restricted": bool(dt._weapons_restricted_sticky.get(target_key, False)),
                    "ammo_regen": float(dt._ammo_regen_sticky.get(target_key, 0.0) or 0.0) > 0.0,
                    "vehicle_lock": bool(dt._vehicle_lock_state.get(target_key, False)),
                })
            for field in ("god_mode", "infinite_ammo", "weapons_restricted", "ammo_regen", "vehicle_lock"):
                out[field] = bool(states) and all(state[field] for state in states)
    except Exception:
        pass
    try:
        from .appearance_adapter import is_invisible

        out["character_invisible"] = bool(is_invisible())
    except Exception:
        out["character_invisible"] = False
    try:
        from . import dev_tools as dt

        out["third_person"] = bool(dt.camera_view_info().get("active"))
        out["model_camera_height"] = bool(dt._model_camera_height_enabled)
    except Exception:
        out["third_person"] = False
        out["model_camera_height"] = False
    try:
        from . import mobility_runtime as mr

        out["no_target"] = bool(mr.no_target_enabled())
    except Exception:
        pass
    return out


def _peer_status_fields() -> dict[str, Any]:
    try:
        from .peer_session import status_fields

        return dict(status_fields())
    except Exception:
        return {
            "product_id": "squ1ggs-boosting-tools",
            "product_author": "Squ1ggs",
            "peer_overlap": [],
            "peer_paused": [],
        }


_peer_pause_last = 0.0


def _challenge_bulk_status_snapshot() -> dict[str, Any]:
    """Small live bulk-challenge counters for the EXE progress bar."""
    try:
        from .challenge_bulk_runtime import status as challenge_status

        st = challenge_status()
    except Exception:
        return {}
    if not isinstance(st, dict):
        return {}
    keys = (
        "active",
        "queued",
        "running",
        "phase",
        "index",
        "progress_index",
        "raw_index",
        "total",
        "progress_total",
        "ok",
        "failed",
        "skipped",
        "token",
        "message",
    )
    return {key: st.get(key) for key in keys}


def _give_everything_status_snapshot() -> dict[str, Any]:
    try:
        from . import give_everything

        st = give_everything.status()
        return dict(st) if isinstance(st, dict) else {}
    except Exception:
        return {}


def get_status() -> dict[str, Any]:
    global _peer_pause_last
    try:
        import time as _time

        now = _time.monotonic()
        if now - _peer_pause_last >= 8.0:
            _peer_pause_last = now
            from .peer_session import pause_overlapping_peers

            pause_overlapping_peers()
    except Exception:
        pass
    pc = get_pc()
    gameplay = gameplay_ready()
    has_pc = pc is not None
    rows = _player_rows()
    if _target_player_index < 0:
        target_name = "All players"
    else:
        target_name = next((r["name"] for r in rows if r["index"] == _target_player_index), "")
    if has_pc and rows:
        connection_state = "ready"
    elif has_pc:
        connection_state = "connected"
    elif rows:
        connection_state = "connected"
    else:
        connection_state = "in_menu_or_loading"
    return _ok(
        "Squ1ggs Boosting Tools bridge online.",
        name="Squ1ggs Boosting Tools",
        mod_version=_MOD_VERSION,
        bridge_protocol="1.0",
        connection_state=connection_state,
        actions_available=bool(has_pc or rows),
        session=_session_label(),
        gameplay_ready=gameplay,
        has_local_pc=has_pc,
        players=rows,
        target_player_index=_target_player_index,
        target_player_name=target_name,
        spawn_anchor=spawn_targets.mode(),
        spawn_anchor_label=spawn_targets.label(),
        required_oak2_sdk="0.3",
        fgbx_def_ptr_ok=_fgbx_ok(),
        bridge_features={
            "manifest": True,
            "catalog": True,
            "mobility": True,
            "bms": True,
            "legit_forge": True,
            "runtime_log": True,
        },
        freecam=debug_cam_info(),
        last_action=_last_action,
        last_error=_last_error,
        sticky_toggles=_sticky_toggle_status(),
        runtime_log=_runtime_log_status(),
        auto_lobby=_auto_lobby_status(),
        challenge_bulk=_challenge_bulk_status_snapshot(),
        give_everything=_give_everything_status_snapshot(),
        **_peer_status_fields(),
    )


def party_roster() -> dict[str, Any]:
    rows = _player_rows()
    return _ok(f"{len(rows)} player(s) in roster.", players=rows, target_player_index=_target_player_index)


def _currency_amount_for_pc(pc: Any, needle: str) -> int | None:
    try:
        from .currency_give import read_currency_amount, resolve_currency_slot_idx

        idx, _err = resolve_currency_slot_idx(pc, needle)
        if idx is None:
            return None
        return read_currency_amount(pc, int(idx))
    except Exception:
        return None


def _party_player_info_row(index: int, name: str = "") -> dict[str, Any]:
    """Read-only level / VHP / wallet snapshot for one party index."""
    row: dict[str, Any] = {"index": int(index), "name": str(name or "")}
    try:
        pc, err = _resolve_target_pc_for_index(int(index))
    except Exception as exc:
        row["ok"] = False
        row["error"] = str(exc)
        return row
    if pc is None:
        row["ok"] = False
        row["error"] = err or "no PlayerController"
        return row
    row["ok"] = True
    if not row["name"]:
        try:
            ps_name = _gbc_resolve_player_display_name(getattr(pc, "PlayerState", None))
            row["name"] = str(ps_name or f"Player {index}")
        except Exception:
            row["name"] = f"Player {index}"
    level = _player_level_for_index(int(index))
    if level is not None:
        row["level"] = int(level)
    ps = getattr(pc, "PlayerState", None)
    if ps is not None:
        try:
            spec = _get_experience_level_via_bp(ps, 1)
            if spec is not None:
                row["spec_level"] = int(spec)
        except Exception:
            pass
        try:
            es = getattr(ps, "ExperienceState", None)
            if es is not None:
                for track_i, key in ((0, "experience_points"), (1, "spec_experience_points")):
                    try:
                        if track_i < len(es):
                            xp = getattr(es[track_i], "ExperiencePoints", None)
                            if xp is not None:
                                row[key] = int(xp)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            vhl = getattr(ps, "VaultHunterLevel", None)
            if vhl is not None:
                row["vault_hunter_level"] = int(vhl)
        except Exception:
            pass
        try:
            row["is_host"] = bool(getattr(get_pc(), "PlayerState", None) is ps)
        except Exception:
            pass
    # Every readable currency slot (cash, eridium, vault tokens, …).
    currencies: list[dict[str, Any]] = []
    try:
        from .currency_give import iter_currency_slots

        for slot_idx, _slot, slot_name, amount in iter_currency_slots(pc):
            label = str(slot_name or f"slot_{slot_idx}").strip() or f"slot_{slot_idx}"
            currencies.append({"name": label, "amount": int(amount), "slot": int(slot_idx)})
            low = label.lower().replace(" ", "").replace("-", "_")
            if "cash" in low and "cash" not in row:
                row["cash"] = int(amount)
            elif "eridium" in low and "eridium" not in row:
                row["eridium"] = int(amount)
    except Exception:
        cash = _currency_amount_for_pc(pc, "cash")
        if cash is not None:
            row["cash"] = int(cash)
        eridium = _currency_amount_for_pc(pc, "eridium")
        if eridium is not None:
            row["eridium"] = int(eridium)
    if currencies:
        row["currencies"] = currencies
    return row


def party_player_info(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Live Pack readout: levels / VHP / all currency slots for selected player(s)."""
    payload = payload or {}
    want_all = str(payload.get("all") or "").strip().lower() in ("1", "true", "yes", "on")
    rows_out: list[dict[str, Any]] = []
    if want_all:
        for index, name in _list_party_players():
            rows_out.append(_party_player_info_row(int(index), str(name)))
    else:
        raw_idx = payload.get("player_index")
        if raw_idx is None or str(raw_idx).strip() == "":
            raw_idx = _target_player_index
        try:
            idx = int(raw_idx)
        except Exception:
            return _fail("player_index must be an integer.")
        if idx < 0:
            return _fail("Pick one player (Whose pack) — All is not supported here. Use Refresh all lobby.")
        name = ""
        for i, n in _list_party_players():
            if int(i) == idx:
                name = str(n)
                break
        rows_out.append(_party_player_info_row(idx, name))

    def _fmt(r: dict[str, Any]) -> str:
        if not r.get("ok"):
            label = str(r.get("name") or f"#{r.get('index')}")
            return f"{label} — {r.get('error') or 'failed'}"
        lines = [str(r.get("name") or f"#{r.get('index')}")]
        if "level" in r:
            lines.append(f"Character level: {r['level']}")
        if "experience_points" in r:
            lines.append(f"Character XP: {int(r['experience_points']):,}")
        if "spec_level" in r:
            lines.append(f"Specialization level: {r['spec_level']}")
        if "spec_experience_points" in r:
            lines.append(f"Specialization XP: {int(r['spec_experience_points']):,}")
        if "vault_hunter_level" in r:
            lines.append(f"Vault Hunter points: {r['vault_hunter_level']}")
        for cur in r.get("currencies") or []:
            try:
                lines.append(f"{cur.get('name')}: {int(cur.get('amount') or 0):,}")
            except Exception:
                continue
        if not r.get("currencies"):
            if "cash" in r:
                lines.append(f"Cash: {int(r['cash']):,}")
            if "eridium" in r:
                lines.append(f"Eridium: {int(r['eridium']):,}")
        return "\n".join(lines)

    lines = [_fmt(r) for r in rows_out]
    msg = "\n\n".join(lines) if len(lines) > 1 else (lines[0] if lines else "No players.")
    return _ok(msg, players=rows_out, count=len(rows_out), fields="party_stats")


def give_currency(payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(payload.get("kind") or payload.get("currency") or "").strip().lower()
    token = _CURRENCY_KIND_ALIASES.get(kind)
    if not token:
        return _fail(f"Unknown currency kind {kind!r}.", kinds=sorted(_CURRENCY_KIND_ALIASES))

    mode = str(payload.get("mode") or "delta").strip().lower()
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")

    if mode in ("absolute", "set", "target"):
        try:
            target = int(payload.get("amount") or payload.get("target") or 0)
        except Exception:
            return _fail("amount/target must be an integer for absolute currency set.")
        if target < 0 or target > _MAX_WALLET_AMOUNT:
            return _fail(f"target must be 0..{_MAX_WALLET_AMOUNT}.")
        ok_n = 0
        details: list[str] = []
        for idx in indices:
            pc, err = _resolve_pc(idx)
            if pc is None:
                details.append(f"index {idx}: {err}")
                continue
            ok, detail = _do_set_currency_absolute(kind, target, pc=pc, player_index=idx)
            details.append(f"index {idx}: {detail}")
            if ok:
                ok_n += 1
        if ok_n == 0:
            return _fail("; ".join(details) or "Currency set failed.")
        if len(indices) == 1:
            return _ok(details[0])
        return _ok(f"Set {kind}={target} for {ok_n}/{len(indices)} player(s).")

    try:
        amount = int(payload.get("amount") or 0)
    except Exception:
        return _fail("amount must be an integer.")
    if amount == 0:
        return _fail("amount must be non-zero for delta give.")
    ok_n = 0
    fails: list[str] = []
    for idx in indices:
        pc, err = _resolve_pc(idx)
        if pc is None:
            fails.append(f"index {idx}: {err}")
            continue
        # Match MAX ALL / absolute path for vault cards and other wallets:
        # additive GiveCurrency alone often no-ops when the slot is cold; set to
        # current+delta via the same absolute helper that maxing uses.
        if amount > 0:
            from .currency_give import read_currency_amount, resolve_currency_slot_idx

            slot_idx, _slot_name = resolve_currency_slot_idx(pc, kind)
            before = read_currency_amount(pc, slot_idx) if slot_idx is not None else 0
            target = min(_MAX_WALLET_AMOUNT, int(before or 0) + int(amount))
            ok, detail = _do_set_currency_absolute(kind, target, pc=pc, player_index=idx)
            if ok:
                ok_n += 1
                continue
            # Fall through to additive GiveCurrency with the real error retained.
            ok2, detail2 = _give_currency_on_pc_detailed(pc, token, amount)
            if ok2:
                ok_n += 1
            else:
                fails.append(f"index {idx}: {detail}; fallback: {detail2}")
            continue
        ok, detail = _give_currency_on_pc_detailed(pc, token, amount)
        if ok:
            ok_n += 1
        else:
            fails.append(f"index {idx}: {detail}")
    if ok_n == 0:
        return _fail("; ".join(fails) or f"GiveCurrency failed for {kind} amount={amount}.")
    if len(indices) == 1:
        return _ok(f"Gave {amount} {kind} to player index {indices[0]}.")
    return _ok(f"Gave {amount} {kind} to {ok_n}/{len(indices)} player(s).")


def give_experience(payload: dict[str, Any]) -> dict[str, Any]:
    track_raw = str(payload.get("track") or payload.get("slot") or "player")
    try:
        level = int(payload.get("level") or 0)
    except Exception:
        return _fail("level must be an integer.")
    if level < 0:
        return _fail("level must be non-negative.")

    tkey = _normalize_track_key(track_raw)
    if tkey not in _EXPERIENCE_TRACK_ALIASES:
        return _fail(
            f"Unknown track {track_raw!r}.",
            tracks=sorted(_EXPERIENCE_TRACK_ALIASES),
        )
    track_idx = _EXPERIENCE_TRACK_ALIASES[tkey]

    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    names: list[str] = []
    fails: list[str] = []
    for idx in indices:
        pc, err = _resolve_pc(idx)
        if pc is None:
            fails.append(f"index {idx}: {err}")
            continue
        ps = getattr(pc, "PlayerState", None)
        if ps is None:
            fails.append(f"index {idx}: Target has no PlayerState.")
            continue
        if not _set_experience_level_via_bp(ps, track_idx, level):
            fails.append(f"index {idx}: BP_SetExperienceLevel failed")
            continue
        ok_n += 1
        names.append(_gbc_resolve_player_display_name(ps))
    if ok_n == 0:
        return _fail("; ".join(fails) or f"BP_SetExperienceLevel failed for track {track_raw} level {level}.")
    if len(indices) == 1:
        return _ok(f"Set {track_raw} to level {level} for {names[0]} (index {indices[0]}).")
    if ok_n < len(indices):
        return _ok(
            f"Set {track_raw} to level {level} for {ok_n}/{len(indices)} player(s). "
            f"Failed: {'; '.join(fails)}"
        )
    return _ok(f"Set {track_raw} to level {level} for {ok_n}/{len(indices)} player(s).")


_UVHM_AFTER_BOOST_SEC = 10.0


def _indices_include_guest(indices: list[int]) -> bool:
    try:
        rows = _player_rows() or []
    except Exception:
        return True
    want = {int(i) for i in indices}
    return any(
        isinstance(r, dict) and int(r.get("index", -1)) in want and not r.get("is_host")
        for r in rows
    )


def max_all(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}

    def _flag(key: str, default: bool) -> bool:
        if key not in payload:
            return default
        val = payload.get(key)
        if isinstance(val, bool):
            return val
        return str(val or "").strip().lower() in ("1", "true", "yes", "on")

    def _amount(key: str, default: int) -> int:
        if key not in payload:
            return int(default)
        try:
            return int(float(payload.get(key)))
        except Exception:
            return int(default)

    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    details: list[str] = []
    fails: list[str] = []
    extras: list[str] = []
    uvhm_queued = False
    challenges_queued = False
    challenge_meta: dict[str, Any] = {}
    amount_opts = {
        "max_cash_amount": _amount("max_cash_amount", 2_147_483_647),
        "max_eridium_amount": _amount("max_eridium_amount", 2_147_483_647),
        "max_sdu_amount": _amount("max_sdu_amount", 3225),
        "max_vault_cards_amount": _amount("max_vault_cards_amount", 2_147_483_647),
        "max_vault_cards_xp_amount": _amount("max_vault_cards_xp_amount", 9_999),
        "max_player_level_amount": _amount("max_player_level_amount", 70),
        "max_spec_level_amount": _amount("max_spec_level_amount", 701),
    }
    for idx in indices:
        ok, detail = max_all_for_target(
            player_index=idx,
            options={
                "max_cash": _flag("max_cash", True),
                "max_eridium": _flag("max_eridium", True),
                "max_sdu": _flag("max_sdu", True),
                "max_vault_cards": _flag("max_vault_cards", True),
                "max_player_level": _flag("max_player_level", True),
                "max_spec_level": _flag("max_spec_level", True),
                **amount_opts,
            },
        )
        details.append(detail)
        if ok:
            ok_n += 1
        else:
            fails.append(f"index {idx}: {detail}")

    if _flag("max_cosmetics", True):
        try:
            from .dev_tools import activate_devperk

            cos_ok = 0
            for idx in indices:
                try:
                    activate_devperk(4, player_index=idx)
                    cos_ok += 1
                except Exception as exc:
                    extras.append(f"cosmetics index {idx}: {exc}")
            if cos_ok:
                extras.append(f"cosmetics+hover {cos_ok}/{len(indices)}")
        except Exception as exc:
            extras.append(f"cosmetics failed: {exc}")

    if _flag("max_mayhem", False):
        try:
            from .mayhem_level import _MAYHEM_LEVEL_CAP, set_unlock_cap

            rank = max(1, min(_MAYHEM_LEVEL_CAP, _amount("max_mayhem_amount", _MAYHEM_LEVEL_CAP)))
            may_ok = 0
            for idx in indices:
                try:
                    if set_unlock_cap(idx, rank).get("ok"):
                        may_ok += 1
                except Exception as exc:
                    extras.append(f"mayhem index {idx}: {exc}")
            extras.append(f"Mayhem Rank {rank} {may_ok}/{len(indices)}")
        except Exception as exc:
            extras.append(f"mayhem failed: {exc}")

    if fails:
        return _fail(
            f"MAX ALL applied to {ok_n}/{len(indices)} player(s). Failed: {'; '.join(fails)}",
            missions_queued=False, challenges_queued=False, uvhm_queued=False,
        )

    if _flag("max_missions", False):
        from . import give_everything

        followup = give_everything.queue_after_max_all(
            -1 if len(indices) > 1 else int(indices[0]),
            challenges=_flag("max_challenges", False),
            uvhm=_flag("max_uvhm_challenges", False),
            redo_completed=_flag("max_missions_redo_completed", False),
        )
        if not followup.get("ok"):
            return _fail("MAX ALL economy options were applied, but missions were not queued: "
                         + str(followup.get("message") or "unknown error"), missions_queued=False)
        return _ok(" · ".join(details + extras + [str(followup.get("message"))]),
                   missions_queued=True, challenges_queued=_flag("max_challenges", False),
                   uvhm_queued=_flag("max_uvhm_challenges", False),
                   give_everything=followup.get("give_everything"), mission=followup.get("mission"))

    def _progression_busy_label() -> str:
        try:
            from . import uvhm_runtime

            st = uvhm_runtime.status()
            if st.get("running") or st.get("queued"):
                return "UVHM"
            try:
                cool = float(st.get("post_complete_cooldown") or 0.0)
            except Exception:
                cool = 0.0
            if cool > 0.0:
                return "UVHM (just finished — settling)"
        except Exception:
            pass
        try:
            from . import challenge_bulk_runtime

            st = challenge_bulk_runtime.status()
            # running/queued only — Complete sticky keeps active=true briefly.
            if st.get("running") or st.get("queued"):
                return "challenges"
        except Exception:
            pass
        return ""

    # Challenges before UVHM — UVHM waits if challenges arm; never stack both starts.
    if _flag("max_challenges", False):
        busy = _progression_busy_label()
        if busy:
            extras.append(f"challenges skipped — {busy} already running")
        else:
            try:
                from .bridge_actions_extended import challenge_bulk_start

                # All players when Boost target is All / multi-index; else single target.
                player_index = -1 if len(indices) > 1 else int(indices[0])
                result = challenge_bulk_start(
                    {
                        "category": "All non-UVHM",
                        "confirmed": True,
                        "player_index": player_index,
                    }
                )
                if result.get("ok", True):
                    challenges_queued = True
                    extras.append(str(result.get("message") or "Challenges queued"))
                    for key in ("queued_count", "progress_total", "challenge", "count"):
                        if key in result:
                            challenge_meta[key] = result.get(key)
                else:
                    extras.append(str(result.get("message") or "Challenge queue failed"))
            except Exception as exc:
                extras.append(f"challenges failed: {exc}")

    if _flag("max_uvhm_challenges", False):
        busy = _progression_busy_label()
        if challenges_queued:
            # Do not start UVHM on the same click — arm a follow-up so it runs
            # after All non-UVHM finishes (previously this was silently skipped).
            try:
                from . import challenge_bulk_runtime

                challenge_bulk_runtime.arm_followup_uvhm(
                    for_all=len(indices) > 1,
                    player_index=int(indices[0]) if indices else 0,
                    max_rank=7,
                )
                uvhm_queued = True
                extras.append("UVHM 1–7 armed — starts after challenges finish")
            except Exception as exc:
                extras.append(f"UVHM follow-up arm failed: {exc}")
        elif busy:
            extras.append(f"UVHM skipped — {busy} already running")
        else:
            try:
                from . import uvhm_runtime
                from .bridge_actions_extended import uvhm_start, uvhm_start_all

                if _indices_include_guest(indices):
                    uvhm_runtime.defer_start(_UVHM_AFTER_BOOST_SEC)
                if len(indices) > 1:
                    result = uvhm_start_all({"confirmed": True, "max_rank": 7})
                else:
                    result = uvhm_start(
                        {
                            "confirmed": True,
                            "max_rank": 7,
                            "player_index": int(indices[0]),
                        }
                    )
                if result.get("ok", True):
                    uvhm_queued = True
                    extras.append(str(result.get("message") or "UVHM 1–7 queued"))
                else:
                    extras.append(str(result.get("message") or "UVHM queue failed"))
            except Exception as exc:
                extras.append(f"UVHM failed: {exc}")

    if ok_n == 0 and not extras:
        return _fail("; ".join(details) or "max_all failed.")
    extra_txt = (" · " + "; ".join(extras)) if extras else ""
    if len(indices) == 1 and ok_n == 1:
        msg = f"{details[0]}{extra_txt}"
    elif fails:
        msg = (
            f"MAX ALL applied to {ok_n}/{len(indices)} player(s). "
            f"Failed: {'; '.join(fails)}{extra_txt}"
        )
    else:
        msg = f"MAX ALL applied to {ok_n}/{len(indices)} player(s).{extra_txt}"
    return (_fail if fails else _ok)(
        msg,
        missions_queued=False,
        uvhm_queued=uvhm_queued,
        challenges_queued=challenges_queued,
        **challenge_meta,
    )

def _max_currency_kind(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Same absolute max path as MAX ALL / blimgui Max Cash|Eridium buttons."""
    payload = payload or {}
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    details: list[str] = []
    for idx in indices:
        pc, err = _resolve_pc(idx)
        if pc is None:
            details.append(f"index {idx}: {err}")
            continue
        ok, detail = _do_set_currency_absolute(
            kind,
            _MAX_WALLET_AMOUNT,
            "",
            pc=pc,
            player_index=idx,
        )
        details.append(f"index {idx}: {detail}")
        if ok:
            ok_n += 1
    if ok_n == 0:
        return _fail("; ".join(details) or f"max {kind} failed.")
    if len(indices) == 1:
        return _ok(f"Max {kind}: {details[0]}")
    return _ok(f"Max {kind} applied to {ok_n}/{len(indices)} player(s).")


def max_cash(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _max_currency_kind("cash", payload)


def max_eridium(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _max_currency_kind("eridium", payload)


def freecam_enable(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    try:
        message = enable_debug_cam()
        return _ok(message, freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def freecam_disable(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    try:
        message = force_disable_debug_cam()
        return _ok(message, freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def freecam_toggle(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    try:
        from .dev_tools import is_debug_cam_active, toggle_debug_cam
        from . import runtime_log

        message = toggle_debug_cam()
        on = bool(is_debug_cam_active())
        try:
            runtime_log.note(f"freecam: toggle → {'ON' if on else 'OFF'} ({message})")
        except Exception:
            pass
        return _ok(message, freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def freecam_set_speed(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        speed = float(payload.get("speed") or payload.get("value") or 1.0)
    except Exception:
        return _fail("speed must be a number.")
    try:
        message = set_debug_cam_speed(speed)
        return _ok(message, freecam=debug_cam_info(), speed=get_debug_cam_speed())
    except Exception as exc:
        return _fail(str(exc))


def freecam_pull_target(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    player_index = payload.get("player_index")
    idx = _target_player_index if player_index is None else int(player_index)
    try:
        message = teleport_pawn_to_debug_cam(idx)
        return _ok(message, freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def freecam_move_placed(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    try:
        from .dev_tools import freecam_move_placed as _move

        return _ok(_move(), freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def freecam_turn_placed(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        degrees = float(payload.get("degrees") if payload.get("degrees") is not None else 45.0)
    except Exception:
        return _fail("degrees must be a number.")
    try:
        from .dev_tools import freecam_turn_placed as _turn

        return _ok(_turn(degrees), freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def freecam_set_distance(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        distance = float(payload.get("distance") or payload.get("value") or 256.0)
    except Exception:
        return _fail("distance must be a number.")
    try:
        message = set_freecam_distance(distance)
        return _ok(message, freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def _record_camera_control(payload: dict[str, Any], before: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    from time import time
    rows = globals().setdefault("_camera_control_history", [])
    rows.append({"time": time(), "request": {key: payload[key] for key in
                 ("enabled", "toggle", "mode", "distance", "shoulder", "height") if key in payload},
                 "before": before, "after": result.get("camera"),
                 "ok": result.get("ok"), "message": result.get("message")})
    del rows[:-12]
    return result


def camera_third_person(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    before = {}
    try:
        from .dev_tools import camera_view_info, reset_third_person_view, set_third_person_view

        before = camera_view_info()
        toggle = payload.get("toggle") is True or str(payload.get("toggle", "")).casefold() in ("true", "on", "1")
        # and send no camera controls. Keep that button usable until repacked.
        if not any(key in payload for key in ("toggle", "enabled", "mode", "distance", "shoulder", "height", "fov")):
            toggle = True
        disable = bool(before.get("active")) if toggle else (
            payload.get("enabled") is False or str(payload.get("enabled", "")).casefold() in ("false", "off", "0")
        )
        if disable:
            return _record_camera_control(payload, before, _ok(reset_third_person_view(), camera=camera_view_info()))
        message = set_third_person_view(
            str(payload.get("mode") or "ThirdPerson"),
            distance=float(payload.get("distance") or 256.0),
            shoulder=float(payload.get("shoulder") or 0.0),
            height=float(payload.get("height") or 0.0),
            fov=(
                float(payload["fov"])
                if payload.get("fov") not in (None, "")
                else None
            ),
        )
        return _record_camera_control(payload, before, _ok(message, camera=camera_view_info()))
    except Exception as exc:
        return _record_camera_control(payload, before, _fail(str(exc)))




def camera_view_reset(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    try:
        from .dev_tools import camera_view_info, reset_third_person_view

        return _ok(reset_third_person_view(), camera=camera_view_info())
    except Exception as exc:
        return _fail(str(exc))


def camera_view_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from .dev_tools import camera_view_info
        from .appearance_adapter import status
        return _ok("Local camera and appearance status.", camera=camera_view_info(), appearance=status())
    except Exception as exc:
        return _fail(str(exc))


def freecam_copy_location(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    try:
        message = copy_debug_cam_location()
        return _ok(message, freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def freecam_inspect_target(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    try:
        return _ok(inspect_looked_at_actor(), freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def freecam_destroy_target(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    try:
        return _ok(destroy_looked_at_actor(), freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def freecam_damage_target(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        amount = float(payload.get("amount", 999999.0))
    except Exception:
        amount = 999999.0
    try:
        return _ok(damage_looked_at_actor(amount), freecam=debug_cam_info())
    except Exception as exc:
        return _fail(str(exc))


def travel_map(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    map_name = str(payload.get("map") or payload.get("map_name") or "").strip()
    if not map_name:
        return _fail("map required.")
    return _ok(travel_to_map(map_name))


def travel_station(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    station = str(payload.get("station") or "").strip()
    if not station:
        return _fail("station required.")
    return _ok(travel_to_station(station))


def travel_preset(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    preset_id = str(payload.get("preset") or payload.get("preset_id") or payload.get("id") or "").strip()
    if not preset_id:
        preset_id = "tuba_boss_arena"
    try:
        return _ok(travel_to_preset(preset_id))
    except Exception as exc:
        return _fail(str(exc))


def lab_pc_rpc(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a dumped OakPlayerController method. Lab tests only."""
    payload = payload or {}
    method = str(payload.get("method") or payload.get("rpc") or "").strip()
    token = str(payload.get("token") or payload.get("mission") or "").strip()
    if not method:
        return _fail("method required.")
    pc = get_pc()
    if pc is None:
        return _fail("Load a character first.")
    fn = getattr(pc, method, None)
    if not callable(fn):
        return _fail(f"{method} is not on this player controller.")
    notes: list[str] = []
    if token:
        try:
            from unrealsdk.unreal import FGbxDefPtr

            for type_arg in ("MissionDef", "Mission", None):
                try:
                    ptr = FGbxDefPtr(token, type=type_arg) if type_arg else FGbxDefPtr(token)
                    fn(ptr)
                    return _ok(f"{method}({token}) ok")
                except Exception as exc:
                    notes.append(str(exc)[:80])
        except Exception:
            pass
        try:
            fn(token)
            return _ok(f"{method}({token}) ok")
        except Exception as exc:
            notes.append(str(exc)[:80])
    try:
        fn()
        return _ok(f"{method}() ok")
    except Exception as exc:
        notes.append(str(exc)[:80])
    return _fail(f"{method} missed: " + " | ".join(notes[-3:]))


def lab_live_attr(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write a bool/int/float on live GameState or OakWorldSettings (Lab dump paths)."""
    from .lab_live_roots import write_live_attr

    ok, msg = write_live_attr(payload or {})
    return _ok(msg) if ok else _fail(msg)


def character_flag(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import character_flags as flags

    payload = payload or {}
    flag = str(payload.get("flag") or "").strip().lower()
    if "enabled" in payload:
        enabled = str(payload.get("enabled")).strip().lower() not in ("0", "false", "no", "off", "")
    else:
        idx = _payload_player_index(payload)
        enabled = not flags.is_on(flag, int(idx if idx is not None else 0))
    indices = _boost_targets_from_payload(payload)
    result: dict[str, Any] = {}
    message = flags.set_flag(flag, indices, enabled, result=result)
    if not result.get("ok"):
        return _fail(message, character_flag=flag, **result)
    return _ok(message, character_flag=flag, enabled=enabled, applied=result["applied"])


def lab_intrinsic_element(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import character_flags as flags

    payload = payload or {}
    try:
        option = int(payload.get("option") if payload.get("option") not in (None, "") else 1)
    except Exception:
        option = 1
    try:
        element = int(payload.get("element") if payload.get("element") not in (None, "") else 0)
    except Exception:
        element = 0
    barrel = str(payload.get("barrel_compat") or "").strip().lower()
    barrel_compat = None
    if barrel in ("1", "true", "yes", "on"):
        barrel_compat = True
    elif barrel in ("0", "false", "no", "off"):
        barrel_compat = False
    indices = _boost_targets_from_payload(payload)
    return _ok(flags.set_intrinsic_element(indices, option=option, element=element, barrel_compat=barrel_compat))


def dev_smoke(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ctrl+Alt+Shift+F9 Dev panel — small pass/fail probes from live game + unrealsdk.log."""
    from . import dev_smoke as smoke

    payload = payload or {}
    suite = str(payload.get("suite") or payload.get("test") or "all").strip() or "all"
    token = str(payload.get("token") or payload.get("mission") or "").strip()
    result = smoke.run_suite(suite, token=token)
    if result.get("ok"):
        return _ok(str(result.get("message") or "ok"), **{k: v for k, v in result.items() if k != "message"})
    return _fail(str(result.get("message") or "smoke failed"), **{k: v for k, v in result.items() if k != "message"})


def black_market(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import bridge_actions_extended as ext

    return ext.black_market(payload or {})


def mayhem_level(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import bridge_actions_extended as ext

    return ext.mayhem_level(payload or {})


def desktop_session_end(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Stop queued/high-network desktop jobs when the EXE closes."""
    stopped: list[str] = []
    try:
        from . import uvhm_runtime

        if uvhm_runtime.cancel():
            stopped.append("UVHM")
    except Exception:
        pass
    try:
        from . import challenge_bulk_runtime

        if challenge_bulk_runtime.cancel():
            stopped.append("bulk challenges")
    except Exception:
        pass
    try:
        from . import shinies

        shinies.cancel_pending_shiny_drops("desktop EXE closed")
    except Exception:
        pass
    try:
        from . import item_pool_spawning

        queued, _done = item_pool_spawning.cancel_bulk_spawn_batch(log=False)
        if queued:
            stopped.append("pool spawn")
    except Exception:
        pass
    try:
        from . import serial_rewards

        serial_rewards.cancel_deferred_reward_work("desktop EXE closed")
    except Exception:
        pass
    try:
        from . import loot_shapes

        loot_shapes.abandon_world_loot(schedule_orphan_absorb=False)
        stopped.append("shape network work")
    except Exception:
        pass
    try:
        from . import auto_lobby

        auto_lobby.abandon()
        stopped.append("auto lobby")
    except Exception:
        pass
    try:
        from . import hold_session

        hold_session.stop_hold(force=True)
    except Exception:
        pass
    try:
        from . import dev_tools

        from .appearance_adapter import release as release_appearance
        release_appearance()
        dev_tools.reset_third_person_view()
        stopped.append("local view")
    except Exception:
        pass
    detail = ", ".join(stopped) if stopped else "no active bulk jobs"
    return _ok(f"Desktop session closed safely ({detail}).")


_ACTIONS: dict[str, Any] = {
    "status": lambda _p: get_status(),
    "party_roster": lambda _p: party_roster(),
    "party_player_info": party_player_info,
    "set_target_player": set_target_player,
    "set_spawn_anchor": set_spawn_anchor,
    "give_currency": give_currency,
    "give_experience": give_experience,
    "max_all": max_all,
    "max_cash": max_cash,
    "max_eridium": max_eridium,
    "freecam_enable": freecam_enable,
    "freecam_toggle": freecam_toggle,
    "freecam_disable": freecam_disable,
    "freecam_set_speed": freecam_set_speed,
    "freecam_pull_target": freecam_pull_target,
    "freecam_move_placed": freecam_move_placed,
    "freecam_turn_placed": freecam_turn_placed,
    "freecam_set_distance": freecam_set_distance,
    "camera_third_person": camera_third_person,
    "camera_view_reset": camera_view_reset,
    "camera_view_status": camera_view_status,
    "freecam_copy_location": freecam_copy_location,
    "freecam_inspect_target": freecam_inspect_target,
    "freecam_destroy_target": freecam_destroy_target,
    "freecam_damage_target": freecam_damage_target,
    "travel_map": travel_map,
    "travel_station": travel_station,
    "travel_preset": travel_preset,
    "lab_pc_rpc": lab_pc_rpc,
    "lab_live_attr": lab_live_attr,
    "character_flag": character_flag,
    "lab_intrinsic_element": lab_intrinsic_element,
    "dev_smoke": dev_smoke,
    "runtime_log": runtime_log_action,
    "black_market": black_market,
    "mayhem_level": mayhem_level,
    "desktop_session_end": desktop_session_end,
    "auto_lobby_get": auto_lobby_get,
    "auto_lobby_set": auto_lobby_set,
    "auto_lobby_start": auto_lobby_start,
    "auto_lobby_stop": auto_lobby_stop,
}


def _refresh_extended_actions() -> None:
    """Load EXE actions without a module-level import (that circular-import wiped travel)."""
    global _extended_import_error
    try:
        import importlib
        import sys

        pkg = (__package__ or "Squ1ggsBoostingTools") + ".bridge_actions_extended"
        ext = sys.modules.get(pkg)
        extra = getattr(ext, "EXTENDED_ACTIONS", None) if ext is not None else None
        if extra is None:
            from . import bridge_actions_extended as ext

            extra = getattr(ext, "EXTENDED_ACTIONS", None)
        if extra is None:
            ext = importlib.reload(ext)  # type: ignore[arg-type]
            extra = getattr(ext, "EXTENDED_ACTIONS", None)
        if not isinstance(extra, dict):
            extra = {}
        extra = dict(extra)
        aliases = {
            "spawn_item_pool_action": "spawn_item_pool",
            "spawn_item_pool_all_action": "spawn_item_pool_all",
            "spawn_item_pool_singular_test_action": "spawn_item_pool_singular_test",
            "serial_delivery_status_action": "serial_delivery_status",
            "catalog_action": "catalog",
            "shiny_drop_status_action": "shiny_drop_status",
        }
        mod_name = getattr(ext, "__name__", "")
        for n in dir(ext):
            if n.startswith("_"):
                continue
            fn = getattr(ext, n, None)
            if not callable(fn):
                continue
            if mod_name and getattr(fn, "__module__", "") != mod_name:
                continue
            extra.setdefault(n, fn)
            alias = aliases.get(n)
            if alias:
                extra.setdefault(alias, fn)
        if extra:
            _ACTIONS.update(extra)
            _extended_import_error = ""
            return
        _extended_import_error = "EXTENDED_ACTIONS missing after load"
    except Exception as exc:
        _extended_import_error = repr(exc)
        try:
            from unrealsdk import logging

            logging.warning(f"[Squ1ggs Boosting Tools | Bridge] extended actions: {exc!r}")
        except Exception:
            pass


def run_action(action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global _last_action, _last_error
    _refresh_extended_actions()
    name = str(action or "").strip()
    handler = _ACTIONS.get(name)
    if handler is None:
        try:
            from . import bridge_actions_extended as ext

            candidate = getattr(ext, name, None)
            if callable(candidate):
                _ACTIONS[name] = candidate
                handler = candidate
        except Exception:
            handler = None
    if handler is None:
        extra = f" Extended load: {_extended_import_error}." if _extended_import_error else ""
        return _fail(f"Unknown action {name!r}.{extra}", known=sorted(_ACTIONS))
    _last_action = name
    _last_error = ""
    data = payload if isinstance(payload, dict) else {}
    try:
        if name == "set_target_player":
            raw_idx = data.get("player_index", _target_player_index)
            if raw_idx is None or str(raw_idx).strip() == "":
                raw_idx = _target_player_index
            result = handler(int(raw_idx))
        elif name in ("status", "party_roster"):
            result = handler(data)
        else:
            result = handler(data)
    except TypeError:
        return _fail(
            "The desktop app is out of date with the loaded SDK. "
            "Press Refresh status. If you just installed an SDK update, fully restart "
            "Borderlands 4 first, load a character, then wait for Online."
        )
    except Exception as exc:
        text = repr(exc)
        if "TypeError" in text or "unexpected keyword" in text.lower():
            return _fail(
                "The desktop app is out of date with the loaded SDK. "
                "Press Refresh status. If you just installed an SDK update, fully restart "
                "Borderlands 4 first, load a character, then wait for Online."
            )
        return _fail(text)
    if isinstance(result, dict):
        return result
    return _ok(str(result))


def camera_model_height(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from .dev_tools import camera_view_info, set_model_camera_height

        raw = (payload or {}).get("enabled", False)
        enabled = raw is True or str(raw).casefold() in ("true", "on", "1")
        return _ok(set_model_camera_height(enabled), camera=camera_view_info())
    except Exception as exc:
        return _fail(str(exc))


def appearance_apply_looked_at(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from . import appearance_adapter
        return appearance_adapter.apply_looked_at(_payload)
    except Exception as exc:
        return _fail(str(exc))


def appearance_apply_selected(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from . import appearance_adapter
        return appearance_adapter.apply(payload)
    except Exception as exc:
        return _fail(str(exc))


def character_invisibility(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from . import appearance_adapter
        return appearance_adapter.invisible(payload)
    except Exception as exc:
        return _fail(str(exc))


def appearance_restore(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from . import appearance_adapter
        return appearance_adapter.restore(_payload)
    except Exception as exc:
        return _fail(str(exc))


def appearance_preview_selected(payload=None):
    try:
        from .appearance_adapter import preview
        return preview(payload)
    except Exception as exc:
        return _fail(str(exc))


def appearance_clear_previews(payload=None):
    try:
        from .appearance_adapter import clear_previews
        return clear_previews(payload)
    except Exception as exc:
        return _fail(str(exc))

_ACTIONS['appearance_apply_looked_at'] = appearance_apply_looked_at
_ACTIONS['appearance_apply_selected'] = appearance_apply_selected
_ACTIONS['appearance_clear_previews'] = appearance_clear_previews
_ACTIONS['appearance_preview_selected'] = appearance_preview_selected
_ACTIONS['appearance_restore'] = appearance_restore
_ACTIONS['camera_model_height'] = camera_model_height
_ACTIONS['camera_view_status'] = camera_view_status
_ACTIONS['character_invisibility'] = character_invisibility

# Native-only release action boundary (also applies to direct bridge requests).
_RELEASE_ACTIONS = frozenset({'auto_lobby_set', 'party_player_info', 'bms_group_start', 'spawn_encounter', 'appearance_apply_selected', 'weapons_restricted', 'loot_shape_place_fully', 'pawn_gravity', 'faafo_empty_backpack', 'serial_store_delete', 'lootlemon_refresh_status', 'fps_display', 'loot_shape_stop_drop', 'map_scout_start', 'keybinds_status', 'mobility_force_fly', 'pack_bay_copy_selected', 'shift_friend_autoaccept', 'vehicle_actions_locked', 'rarity_weights_set', 'photo_preset', 'serial_store_export_text', 'pack_bay_enable', 'gzo_refresh_start', 'guest_map_assist_cancel', 'travel_station', 'catalog', 'keybinds_set', 'loot_feed_appear', 'spawn_item_pool_singular_test', 'freecam_toggle', 'bms_group_next', 'god_mode', 'serial_store_import_merge', 'shiny_drop_all', 'deliver_serials', 'serial_store_add_selected', 'spawn_ios', 'mobility_noclip', 'rewards_open_everyone', 'auto_lobby_get', 'party_refresh', 'freecam_move_placed', 'teleport_party', 'mobility_delete_ground', 'tuning_status', 'loot_shape_arrange', 'bms_group_stop', 'appearance_preview_selected', 'dev_smoke', 'map_party_escort_start', 'faafo_fall_through_map', 'camera_view_reset', 'freecam_disable', 'mission_status', 'pack_bay_open_toolbox', 'freecam_set_speed', 'spawn_mobs', 'loot_shape_status', 'mayhem_level', 'serial_store_create_group', 'bms_group_add', 'faafo_ffyl', 'guest_map_assist_start', 'mobility_time', 'guest_map_assist_status', 'travel_map', 'auto_lobby_stop', 'freecam_set_distance', 'freecam_turn_placed', 'bms_group_set_options', 'max_all', 'give_everything', 'loot_coil_reel', 'spawn_item_pool_all', 'shift_friend_autoaccept_once', 'lab_intrinsic_element', 'loot_cleanup', 'party_roster', 'challenge_bulk_start', 'loot_shape_reapply', 'loot_vacuum_cancel', 'uvhm_status', 'spawn_item_pool', 'set_spawn_anchor', 'give_currency', 'mobility_load_preset', 'freecam_pull_target', 'mission_cancel', 'black_market', 'give_everything_status', 'inventory_set_sizes', 'loot_shape_clear', 'mobility_preset_apply', 'serial_store_delete_group', 'max_sdu', 'character_flag', 'mobility_save_preset', 'editor_pack_serial', 'pack_bay_disable', 'spawn_mix', 'serial_delivery_status', 'teleport_party_slot', 'serial_store_import_serials', 'mobility_players_only', 'activity_log', 'backpack_scan_status', 'bms_group_load', 'tuning_reset', 'backpack_export_txt', 'bms_group_clear_plan', 'faafo_kill', 'faafo_lock_move', 'shiny_drop_status', 'shiny_mail_all', 'map_fog_hide', 'serial_store_rename_group', 'backpack_refresh_view', 'uvhm_start', 'appearance_apply_looked_at', 'tuning_apply', 'barrel_logo_clear', 'mission_start', 'bms_group_save', 'spawn_io', 'legit_forge_max_passives', 'serial_store_save', 'world_personal_vehicle', 'console_safety_get', 'bms_group_delete_save', 'faafo_drop_backpack', 'spawn_item_pool_cancel', 'faafo_lock_both', 'infinite_ammo', 'freecam_damage_target', 'bms_group_clear_live', 'serial_convert', 'bvm_vehicle_jump', 'mobility_status', 'host_map_sweep_start', 'hud_hide', 'freecam_copy_location', 'status', 'bms_clear', 'give_experience', 'low_power', 'map_party_escort_cancel', 'mobility_auto_apply', 'legit_forge_validate', 'faafo_unlock', 'legit_forge_append_part', 'warp_mark_go', 'map_scout_status', 'bms_reaggro', 'tuning_preset', 'host_map_sweep_cancel', 'camera_third_person', 'freecam_inspect_target', 'host_map_sweep_status', 'kill_all_enemies', 'mission_travel_repair', 'faafo_invert_look', 'ammo_regen', 'party_kick', 'bay_label_serials', 'map_fog_unlock', 'loot_gather_nearby', 'map_scout_cancel', 'spawn_item_pool_status', 'loot_vacuum_status', 'freecam_enable', 'bms_group_status', 'keybinds_clear', 'bms_group_remove', 'appearance_restore', 'devperk_activate', 'lab_pc_rpc', 'spawn_mob', 'give_everything_cancel', 'challenge_bulk_status', 'set_target_player', 'uvhm_resume', 'golden_chest', 'desktop_session_end', 'auto_lobby_start', 'bms_activate_io', 'vehicle_spawn', 'travel_preset', 'pawn_no_target', 'mobility_toggle_no_target', 'faafo_lock_look', 'challenge_complete_selected', 'legit_forge_give', 'appearance_clear_previews', 'mobility_infinite_jump', 'barrel_logo', 'mobility_zero_vault', 'panel_manifest', 'map_party_escort_status', 'spawn_text_shape', 'max_eridium', 'warp_mark_list', 'warp_mark_save', 'character_invisibility', 'vehicle_spawn_catalog_reload', 'open_bank_anywhere', 'mobility_apply', 'uvhm_start_all', 'gzo_refresh_status', 'max_cash', 'serial_store_duplicate', 'editor_spawn_serial', 'freecam_destroy_target', 'serial_store_export_json', 'hold_session', 'lab_live_attr', 'lootlemon_refresh_start', 'loot_vacuum_nearby', 'camera_model_height', 'faafo_launch', 'challenge_bulk_cancel', 'oak_travel', 'runtime_log', 'editor_analyze_serial', 'warp_mark_delete', 'console_safety_set', 'mission_preview', 'backpack_relevel_selected', 'camera_view_status', 'uvhm_cancel', 'legit_forge_build'})
_ACTIONS = {k: v for k, v in _ACTIONS.items() if k in _RELEASE_ACTIONS}
