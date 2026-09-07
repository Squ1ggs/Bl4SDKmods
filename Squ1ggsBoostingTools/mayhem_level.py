"""Mayhem unlock cap + session level (OakPlayerState / OakGameState dumps)."""

from __future__ import annotations

from typing import Any

import unrealsdk
from unrealsdk import logging

from .black_market import (
    _call_noarg,
    _obj_path,
    _owners_for_index,
    _write_attr,
)
from .lab_live_roots import _live_game_state

_PREFIX = "[Squ1ggs Boosting Tools | Mayhem]"
_CAP_FIELD = "HighestUnlockedMayhemLevel"
_SESSION_FIELD = "MayhemLevel"
_NET_TOUCH = ("FlushNetDormancy", "ForceNetUpdate", "MarkDirtyForReplication")
_ONREP_NAMES = (
    "OnRep_HighestUnlockedMayhemLevel",
    "OnRep_MayhemLevel",
    "OnRep_ReplicatedPlayerStats",
    "OnRep_GbxProgression",
)
_COLLECTOR_CLASSES = (
    "OakUIDataCollector_Takedown",
    "OakUIDataCollector_Progression",
    "OakUIDataCollector_PlayerStats",
)
_COLLECTOR_REFRESH = (
    "Refresh",
    "RefreshData",
    "UpdateData",
    "RequestRefresh",
    "Collect",
    "OnRefresh",
)
_RELOAD_HINT = "Reload save after — kiosk UI usually will not update until then."
# Vanilla: first normal clear sets rank 0→1 (unlocks Mayhem mode). Rank 5 unlocks Hardcore.
_MAYHEM_MODE_MIN = 1
_HARDCORE_MODE_MIN = 5
_TAKEDOWN_MODE_METHODS = (
    "ChangeTakedownMode",
    "SetTakedownMode",
    "ServerChangeTakedownMode",
    "ClientChangeTakedownMode",
)


def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")


def _clamp_cap(level: int) -> int:
    return max(0, min(99, int(level)))


def _unlock_cap_for_request(level: int) -> int:
    """Floor unlock writes so Mayhem mode is available without a normal clear."""
    return max(_MAYHEM_MODE_MIN, _clamp_cap(level))


def _clamp_session(level: int) -> int:
    return max(0, min(99, int(level)))


def _touch_replication(obj: Any) -> list[str]:
    hits: list[str] = []
    if obj is None:
        return hits
    for name in _NET_TOUCH:
        if _call_noarg(obj, name):
            hits.append(name)
    for name in _ONREP_NAMES:
        if _call_noarg(obj, name):
            hits.append(name)
    return hits


def _collect_targets(owners: list[Any], pcs: list[Any]) -> list[Any]:
    targets: list[Any] = []
    seen: set[int] = set()

    def _add(obj: Any) -> None:
        if obj is None:
            return
        key = id(obj)
        if key in seen:
            return
        seen.add(key)
        targets.append(obj)

    for ps in owners:
        _add(ps)
    for pc in pcs:
        _add(pc)
        _add(getattr(pc, "PlayerState", None))
        pawn = getattr(pc, "OakCharacter", None) or getattr(pc, "Pawn", None)
        _add(pawn)
        if pawn is not None:
            gm = getattr(pawn, "GbxProgressionManager", None)
            _add(gm)
            _add(getattr(gm, "DataMgr", None) if gm is not None else None)
        for coll in _find_collectors_on_pc(pc):
            _add(coll)
    _add(_live_game_state())
    return targets


def _find_collectors_on_pc(pc: Any) -> list[Any]:
    if pc is None:
        return []
    pc_name = str(getattr(pc, "Name", "") or "").lower()
    out: list[Any] = []
    seen: set[int] = set()
    for cls in _COLLECTOR_CLASSES:
        try:
            items = list(unrealsdk.find_all(cls, False) or [])
        except Exception:
            items = []
        for coll in items:
            if coll is None or id(coll) in seen:
                continue
            outer = getattr(coll, "Outer", None)
            path = _obj_path(coll).lower()
            if outer is pc or (pc_name and pc_name in path):
                seen.add(id(coll))
                out.append(coll)
    return out


def _refresh_collectors(pcs: list[Any]) -> list[str]:
    hits: list[str] = []
    for pc in pcs:
        for coll in _find_collectors_on_pc(pc):
            label = type(coll).__name__
            for meth in _COLLECTOR_REFRESH:
                if _call_noarg(coll, meth):
                    hits.append(f"{label}.{meth}")
    return hits


def _nudge_takedown_ios(pcs: list[Any]) -> list[str]:
    """Best-effort: poke nearby takedown IO scripts so kiosk UI rebuilds."""
    hits: list[str] = []
    for pc in pcs:
        pawn = getattr(pc, "OakCharacter", None) or getattr(pc, "Pawn", None)
        if pawn is None:
            continue
        try:
            loc = pawn.K2_GetActorLocation()
        except Exception:
            continue
        try:
            actors = list(unrealsdk.find_all("Actor", False) or [])
        except Exception:
            actors = []
        for actor in actors[:4000]:
            if actor is None:
                continue
            path = _obj_path(actor).lower()
            if "takedown" not in path and "ui_script_takedown" not in path:
                continue
            try:
                aloc = actor.K2_GetActorLocation()
                dx = float(aloc.X) - float(loc.X)
                dy = float(aloc.Y) - float(loc.Y)
                dz = float(aloc.Z) - float(loc.Z)
                if dx * dx + dy * dy + dz * dz > 8000.0 * 8000.0:
                    continue
            except Exception:
                continue
            for meth in ("deactivate", "Activate"):
                if _call_noarg(actor, meth):
                    hits.append(f"{meth}@{path[-48:]}")
            # Prefer Mayhem mode on the kiosk when Rank already unlocks it.
            for meth in _TAKEDOWN_MODE_METHODS:
                fn = getattr(actor, meth, None)
                if not callable(fn):
                    continue
                for arg in (1, "Mayhem", "MayhemMode", "ETakedownMode::Mayhem"):
                    try:
                        fn(arg)
                        hits.append(f"{meth}({arg})@{path[-40:]}")
                        break
                    except Exception:
                        try:
                            fn(Mode=arg)
                            hits.append(f"{meth}(Mode={arg})@{path[-40:]}")
                            break
                        except Exception:
                            continue
    return hits[:12]


def _try_mission_progress_nudge(pcs: list[Any]) -> list[str]:
    """Best-effort: poke MissionProgress roles so Base-complete gates refresh after Rank write."""
    hits: list[str] = []
    classes = (
        "MissionProgressRole",
        "OakMissionProgressRole",
        "GbxMissionProgressComponent",
    )
    methods = (
        "Refresh",
        "RefreshMissions",
        "ForceNetUpdate",
        "MarkDirtyForReplication",
        "NotifyMissionGraphChanged",
    )
    for pc in pcs:
        for cls in classes:
            try:
                items = list(unrealsdk.find_all(cls, False) or [])
            except Exception:
                items = []
            for obj in items[:40]:
                if obj is None:
                    continue
                for meth in methods:
                    if _call_noarg(obj, meth):
                        hits.append(f"{cls}.{meth}")
    return hits[:8]


def nudge_mayhem_after_write(*, pc: Any = None, ps: Any = None) -> str:
    """Call after ULM setattr — tries live UI refresh without save reload."""
    pcs: list[Any] = []
    owners: list[Any] = []
    if pc is not None:
        pcs.append(pc)
    if ps is not None:
        owners.append(ps)
        if pc is None:
            try:
                from .party_helpers import _gbc_find_pc_for_player_state

                found = _gbc_find_pc_for_player_state(ps)
                if found is not None:
                    pcs.append(found)
            except Exception:
                pass
    rep: list[str] = []
    for obj in _collect_targets(owners, pcs):
        rep.extend(_touch_replication(obj))
    refresh = _refresh_collectors(pcs)
    ios = _nudge_takedown_ios(pcs)
    bits = [
        f"rep={','.join(dict.fromkeys(rep)[:8]) or 'none'}",
        f"collectors={','.join(refresh[:6]) or 'none'}",
        f"io={','.join(ios[:4]) or 'none'}",
    ]
    msg = "Mayhem UI nudge: " + "; ".join(bits) + f" {_RELOAD_HINT}"
    _log(msg)
    return msg


def set_unlock_cap(player_index: int, level: int) -> dict[str, Any]:
    """Set Mayhem Rank unlock. Rank 1+ = Mayhem mode (no normal clear needed). Rank 5+ = Hardcore."""
    cap = _unlock_cap_for_request(level)
    owners, pcs, err = _owners_for_index(int(player_index))
    if err:
        return {"ok": False, "message": err, "level": cap}
    targets = _collect_targets(owners, pcs)
    wrote = 0
    for obj in targets:
        if _write_attr(obj, _CAP_FIELD, cap):
            wrote += 1
            _touch_replication(obj)
    # Mirror onto GameState session field so HUD/session aren't stuck at 0 after reload.
    gs = _live_game_state()
    if gs is not None and _write_attr(gs, _SESSION_FIELD, cap):
        wrote += 1
        _touch_replication(gs)
    refresh = _refresh_collectors(pcs)
    ios = _nudge_takedown_ios(pcs)
    mission = _try_mission_progress_nudge(pcs)
    gates = []
    if cap >= _MAYHEM_MODE_MIN:
        gates.append("Mayhem mode")
    if cap >= _HARDCORE_MODE_MIN:
        gates.append("Hardcore")
    gate_txt = "+".join(gates) if gates else "none"
    msg = (
        f"Mayhem Rank={cap} (unlocks {gate_txt} without a normal clear) wrote={wrote} "
        f"collectors={','.join(refresh[:6]) or 'none'} "
        f"io={','.join(ios[:4]) or 'none'} "
        f"mission={','.join(mission[:4]) or 'none'}. {_RELOAD_HINT} "
        f"If the kiosk still says complete Normal first, save + reload once — Rank is the gate."
    )
    _log(msg)
    return {"ok": wrote > 0, "message": msg, "level": cap, "wrote": wrote}


def set_session_mayhem(level: int) -> dict[str, Any]:
    val = _clamp_session(level)
    gs = _live_game_state()
    if gs is None:
        return {"ok": False, "message": "No live GameState — load into a map.", "level": val}
    if not _write_attr(gs, _SESSION_FIELD, val):
        return {"ok": False, "message": f"GameState.{_SESSION_FIELD} write failed.", "level": val}
    rep = _touch_replication(gs)
    msg = (
        f"GameState.{_SESSION_FIELD}={val} "
        f"rep={','.join(dict.fromkeys(rep)[:6]) or 'none'} — check HUD."
    )
    _log(msg)
    return {"ok": True, "message": msg, "level": val}


def read_state(player_index: int) -> dict[str, Any]:
    owners, _pcs, err = _owners_for_index(int(player_index))
    if err:
        return {"ok": False, "message": err}
    ps = owners[0] if owners else None
    cap = 0
    if ps is not None:
        try:
            cap = int(getattr(ps, _CAP_FIELD, 0) or 0)
        except Exception:
            cap = 0
    gs = _live_game_state()
    session = 0
    if gs is not None:
        try:
            session = int(getattr(gs, _SESSION_FIELD, 0) or 0)
        except Exception:
            session = 0
    return {
        "ok": True,
        "message": f"cap={cap} session={session}",
        "cap": cap,
        "session": session,
    }


def apply_payload(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    action = str(payload.get("action") or "unlock_cap").strip().lower()
    if action in ("status", "read"):
        idx = int(payload.get("player_index", payload.get("index", 0)) or 0)
        return read_state(idx)
    if action in ("session", "session_mayhem", "hud"):
        try:
            level = int(payload.get("level", payload.get("value", 0)) or 0)
        except Exception:
            return {"ok": False, "message": "level must be int."}
        return set_session_mayhem(level)
    try:
        level = int(payload.get("level", payload.get("value", payload.get("cap", 10))) or 10)
    except Exception:
        return {"ok": False, "message": "level must be int."}
    idx = int(payload.get("player_index", payload.get("index", 0)) or 0)
    return set_unlock_cap(idx, level)
