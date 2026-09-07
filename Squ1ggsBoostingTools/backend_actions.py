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
)
from .player_economy import (
    _CURRENCY_KIND_ALIASES,
    _EXPERIENCE_TRACK_ALIASES,
    _MAX_WALLET_AMOUNT,
    _do_set_currency_absolute,
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
        if local_ps is not None and pa is not None:
            try:
                is_host = pa[int(index)] is local_ps
            except Exception:
                is_host = False
        if not is_host and local_ps is None and int(index) == 0:
            is_host = True
        rows.append({"index": int(index), "name": str(name), "is_host": bool(is_host)})
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
        "map_fog": False,
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
        jump_on = False
        all_mode = bool(getattr(mr, "_infinite_jump_all_mode", False))
        try:
            if all_mode:
                jump_on = True
            elif idx < 0:
                jump_on = False
            elif hasattr(mr, "_may_mutate_infinite_jump"):
                jump_on = bool(mr._may_mutate_infinite_jump(idx))
            else:
                jump_on = idx in getattr(mr, "infinite_jump_indices", set())
        except Exception:
            jump_on = idx in getattr(mr, "infinite_jump_indices", set()) if idx >= 0 else False
        out["infinite_jump"] = bool(jump_on)
        # Trust the latch — comparing live indices made the Toggles row flip OFF
        # while jump was still on, so the next click turned it off.
        out["infinite_jump_all"] = bool(all_mode)
        if idx < 0:
            out["infinite_jump"] = bool(all_mode)
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
    except Exception:
        pass
    try:
        from .map_fog_hide import is_hidden as _map_fog_hidden

        out["map_fog"] = bool(_map_fog_hidden())
    except Exception:
        out["map_fog"] = False
    try:
        from . import tuning_embed as te

        eng = te.get_engine("bvm")
        out["vehicle_jump"] = bool(getattr(eng, "BVM_REPEAT_JUMP_PRESS", False))
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


def get_status() -> dict[str, Any]:
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
        **_peer_status_fields(),
    )


def party_roster() -> dict[str, Any]:
    rows = _player_rows()
    return _ok(f"{len(rows)} player(s) in roster.", players=rows, target_player_index=_target_player_index)


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


def max_all(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    details: list[str] = []
    fails: list[str] = []
    for idx in indices:
        ok, detail = max_all_for_target(
            player_index=idx,
            options={
                "max_cash": payload.get("max_cash", True),
                "max_eridium": payload.get("max_eridium", True),
                "max_sdu": payload.get("max_sdu", True),
                "max_vault_cards": payload.get("max_vault_cards", True),
                "max_player_level": payload.get("max_player_level", True),
                "max_spec_level": payload.get("max_spec_level", True),
            },
        )
        details.append(detail)
        if ok:
            ok_n += 1
        else:
            fails.append(f"index {idx}: {detail}")
    if ok_n == 0:
        return _fail("; ".join(details) or "max_all failed.")
    if len(indices) == 1:
        return _ok(details[0])
    if fails:
        return _ok(
            f"MAX ALL applied to {ok_n}/{len(indices)} player(s). "
            f"Failed: {'; '.join(fails)}"
        )
    return _ok(f"MAX ALL applied to {ok_n}/{len(indices)} player(s).")


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
        from .dev_tools import toggle_debug_cam

        message = toggle_debug_cam()
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
    return _ok(flags.set_flag(flag, indices, enabled))


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


_ACTIONS: dict[str, Any] = {
    "status": lambda _p: get_status(),
    "party_roster": lambda _p: party_roster(),
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
    "freecam_set_distance": freecam_set_distance,
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
