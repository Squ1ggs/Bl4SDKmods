"""Black market: spawn helpers + purchase cooldown clear only."""

from __future__ import annotations

import time
from typing import Any

import unrealsdk
from unrealsdk import logging

from .party_helpers import (
    _gbc_find_pc_for_player_state,
    _gbc_find_remote_pc_name_fallback,
    _gbc_is_listen_host_world,
    _gbc_resolve_player_display_name,
    _gbc_session_world_and_gamestate,
)
from .player_economy import _resolve_target_pc_for_index

_PREFIX = "[Squ1ggs Boosting Tools | BlackMarket]"
# Dump ready value when unlocked (unix end-time when on purchase cooldown).
_COOLDOWN_PAST = 1
_WORLD_BM_PATH = (
    "/Game/Maps/WorldLevels/World_P.World_P:PersistentLevel.IO_VendingMachine_BlackMarket"
)

_pending_ready_until = 0.0
_pending_ready_index = 0
_pending_ready_tick = 0.0
_true_bm_loc: tuple[float, float, float] | None = None


def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")


def _obj_path(obj: Any) -> str:
    try:
        path = getattr(obj, "_path_name", None)
        if callable(path):
            return str(path())
    except Exception:
        pass
    try:
        return str(obj)
    except Exception:
        return "?"


def _is_default_obj(obj: Any) -> bool:
    return "default__" in _obj_path(obj).lower()


def _call_noarg(obj: Any, name: str) -> bool:
    fn = getattr(obj, name, None)
    if not callable(fn):
        return False
    try:
        fn()
        return True
    except TypeError:
        try:
            fn(0)
            return True
        except Exception:
            return False
    except Exception:
        return False


def _write_attr(obj: Any, name: str, value: Any) -> bool:
    if obj is None:
        return False
    try:
        setattr(obj, name, value)
        return True
    except Exception:
        return False


def _read_int(obj: Any, name: str) -> int | None:
    if obj is None:
        return None
    try:
        return int(getattr(obj, name) or 0)
    except Exception:
        return None


def _read_bool(obj: Any, name: str) -> bool | None:
    if obj is None:
        return None
    try:
        return bool(getattr(obj, name))
    except Exception:
        return None


def _touch_net(obj: Any, *, reps: bool = True) -> None:
    if obj is None:
        return
    names = ["FlushNetDormancy", "ForceNetUpdate"]
    if reps:
        names.append("OnRep_BlackMarketCooldownTimestamp")
    for name in names:
        _call_noarg(obj, name)


def _ping_pc_timers(pc: Any) -> list[str]:
    """Refresh purchase timer UI. Never call ClientCallBlackMarketCooldownEvent."""
    hits: list[str] = []
    if _call_noarg(pc, "ClientSyncVendingMachineTimer"):
        hits.append("ClientSyncVendingMachineTimer")
    return hits


def _write_cooldown_owners(owners: list[Any], pcs: list[Any]) -> int:
    """Write BlackMarketCooldownTimestamp on pawn + PlayerState + PC."""
    wrote = 0
    targets: list[Any] = []
    seen: set[int] = set()

    def _add(obj: Any) -> None:
        if obj is None or id(obj) in seen:
            return
        seen.add(id(obj))
        targets.append(obj)

    for owner in owners:
        _add(owner)
    for pc in pcs:
        _add(pc)
        _add(getattr(pc, "PlayerState", None))
        _add(getattr(pc, "OakCharacter", None) or getattr(pc, "Pawn", None))
    for obj in targets:
        if _write_attr(obj, "BlackMarketCooldownTimestamp", _COOLDOWN_PAST):
            wrote += 1
            _touch_net(obj, reps=True)
            _call_noarg(obj, "OnRep_BlackMarketCooldownTimestamp")
    return wrote


def _vendor_rows(machine: Any) -> list[Any]:
    rows: list[Any] = []
    try:
        data = getattr(machine, "StoredInventoryData", None)
        invs = getattr(data, "StoredVendorInventories", None) if data is not None else None
        if invs is None:
            return rows
        try:
            n = len(invs)
        except Exception:
            n = 1
        for i in range(max(1, int(n))):
            try:
                rows.append(invs[i])
            except Exception:
                break
    except Exception:
        return []
    return rows


def _iter_black_market_machines() -> list[Any]:
    found: list[Any] = []
    seen: set[int] = set()

    def _add(obj: Any) -> None:
        if obj is None or _is_default_obj(obj):
            return
        key = id(obj)
        if key in seen:
            return
        path = _obj_path(obj).lower()
        name = str(getattr(obj, "Name", "") or "").lower()
        if "blackmarket" not in path and "blackmarket" not in name:
            return
        seen.add(key)
        found.append(obj)

    for cls, name in (
        ("OakVendingMachine", _WORLD_BM_PATH),
        ("OakVendingMachine", "IO_VendingMachine_BlackMarket"),
    ):
        try:
            _add(unrealsdk.find_object(cls, name))
        except Exception:
            pass
    try:
        raw = list(unrealsdk.find_all("OakVendingMachine", False) or [])
    except Exception:
        raw = []
    for obj in raw:
        _add(obj)
    return found


def _pawn_loc() -> Any | None:
    try:
        from mods_base import get_pc

        pc = get_pc()
        pawn = getattr(pc, "OakCharacter", None) or getattr(pc, "Pawn", None) if pc is not None else None
        if pawn is None:
            return None
        return pawn.K2_GetActorLocation()
    except Exception:
        return None


def _dist_sq(a: Any, b: Any) -> float:
    dx = float(a.X) - float(b.X)
    dy = float(a.Y) - float(b.Y)
    dz = float(a.Z) - float(b.Z)
    return dx * dx + dy * dy + dz * dz


def _find_world_shop() -> Any | None:
    for cls in ("OakVendingMachine", "OakInteractiveObject", "Actor"):
        for name in (_WORLD_BM_PATH, "IO_VendingMachine_BlackMarket"):
            try:
                obj = unrealsdk.find_object(cls, name)
            except Exception:
                obj = None
            if obj is None or _is_default_obj(obj):
                continue
            path = _obj_path(obj).lower()
            if "blackmarket" not in path and "blackmarket" not in str(getattr(obj, "Name", "") or "").lower():
                continue
            return obj
    for machine in _iter_black_market_machines():
        if "persistentlevel" in _obj_path(machine).lower():
            return machine
    return None


def _nearest_machine() -> Any | None:
    machines = _iter_black_market_machines()
    if not machines:
        return None
    loc = _pawn_loc()
    if loc is None:
        return machines[0]
    best = machines[0]
    best_d = None
    for machine in machines:
        try:
            d = _dist_sq(machine.K2_GetActorLocation(), loc)
        except Exception:
            continue
        if best_d is None or d < best_d:
            best = machine
            best_d = d
    return best


def _machines_for_purchase_clear() -> list[Any]:
    """Nearest first, then world shop, then every other live BM actor."""
    out: list[Any] = []
    seen: set[int] = set()

    def _add(machine: Any) -> None:
        if machine is None or id(machine) in seen:
            return
        seen.add(id(machine))
        out.append(machine)

    _add(_nearest_machine())
    _add(_find_world_shop())
    loc = _pawn_loc()
    scored: list[tuple[float, Any]] = []
    for machine in _iter_black_market_machines():
        try:
            d = _dist_sq(machine.K2_GetActorLocation(), loc) if loc is not None else 0.0
        except Exception:
            d = 9e18
        scored.append((d, machine))
    scored.sort(key=lambda t: t[0])
    for _d, machine in scored:
        _add(machine)
    return out


def _save_true_loc(machine: Any) -> None:
    """Remember weekly shop world location before oak_dual relocates it."""
    global _true_bm_loc
    if _true_bm_loc is not None or machine is None:
        return
    try:
        loc = machine.K2_GetActorLocation()
        _true_bm_loc = (float(loc.X), float(loc.Y), float(loc.Z))
        _log(f"saved true BM loc x={_true_bm_loc[0]:.0f} y={_true_bm_loc[1]:.0f} z={_true_bm_loc[2]:.0f}")
    except Exception:
        pass


def _clear_machine_cooldown(machine: Any) -> list[str]:
    """Purchase timer fields only. Does not touch WaitForCooldownEnd / CooldownEnd."""
    hits: list[str] = []
    if _write_attr(machine, "BlackMarketCooldownTimestamp", _COOLDOWN_PAST):
        hits.append("machine.cooldown")
    for row in _vendor_rows(machine):
        if _write_attr(row, "OverrideRemainingTime", 0):
            hits.append("OverrideRemainingTime=0")
    return hits


def _player_array_states() -> tuple[list[Any], str]:
    world, gs = _gbc_session_world_and_gamestate()
    if world is None or gs is None:
        return [], "no world or GameState"
    if not _gbc_is_listen_host_world(world):
        return [], "listen host only (open console on the host)"
    pa = getattr(gs, "PlayerArray", None)
    if pa is None:
        return [], "PlayerArray missing"
    out: list[Any] = []
    try:
        for ps in pa:
            if ps is not None:
                out.append(ps)
    except Exception as exc:
        return [], f"PlayerArray read failed: {exc}"
    return out, ""


def _pc_for_ps(ps: Any) -> Any | None:
    world, _gs = _gbc_session_world_and_gamestate()
    if world is None:
        return None
    pc = _gbc_find_pc_for_player_state(ps, world)
    if pc is not None:
        return pc
    try:
        from mods_base import get_pc

        host_pc = get_pc()
        host_ps = getattr(host_pc, "PlayerState", None) if host_pc is not None else None
        name = _gbc_resolve_player_display_name(ps)
        return _gbc_find_remote_pc_name_fallback(ps, host_ps, name, "[SQBT]")
    except Exception:
        return None


def _find_all_oak_player_states() -> list[Any]:
    found: list[Any] = []
    try:
        raw = list(unrealsdk.find_all("OakPlayerState", False) or [])
    except Exception:
        raw = []
    for obj in raw:
        if obj is None or _is_default_obj(obj):
            continue
        found.append(obj)
    return found


def _owners_for_index(player_index: int) -> tuple[list[Any], list[Any], str]:
    pa, err = _player_array_states()
    if err:
        return [], [], err
    if int(player_index) < 0:
        targets = list(pa)
    elif int(player_index) >= len(pa):
        return [], [], f"player index {player_index} out of range (0..{max(0, len(pa) - 1)})"
    else:
        targets = [pa[int(player_index)]]

    owners: list[Any] = []
    pcs: list[Any] = []
    seen: set[int] = set()

    def _add(obj: Any) -> None:
        if obj is None:
            return
        key = id(obj)
        if key in seen:
            return
        seen.add(key)
        owners.append(obj)

    live = _find_all_oak_player_states()
    for ps in targets:
        _add(ps)
        pc = _pc_for_ps(ps)
        if pc is not None:
            pcs.append(pc)
            _add(getattr(pc, "PlayerState", None))
            _add(pc)
        path = _obj_path(ps)
        for extra in live:
            if extra is ps or _obj_path(extra) == path:
                _add(extra)
    if int(player_index) < 0:
        for extra in live:
            _add(extra)
    if not owners:
        pc, pc_err = _resolve_target_pc_for_index(max(0, int(player_index)))
        if pc is None:
            return [], [], pc_err or "No target player."
        _add(getattr(pc, "PlayerState", None))
        _add(pc)
        pcs.append(pc)
    return owners, pcs, ""


def read_state(player_index: int) -> dict[str, Any]:
    owners, pcs, err = _owners_for_index(int(player_index))
    if err:
        return {"ok": False, "message": err, "cooldown": None, "visited": None}
    cooldown: int | None = None
    visited: bool | None = None
    for owner in owners:
        if cooldown is None:
            cooldown = _read_int(owner, "BlackMarketCooldownTimestamp")
        if visited is None:
            visited = _read_bool(owner, "bBlackMarketMachineDiscovered")
    for pc in pcs:
        if cooldown is None:
            cooldown = _read_int(pc, "BlackMarketCooldownTimestamp")
        pawn = getattr(pc, "OakCharacter", None) or getattr(pc, "Pawn", None)
        if cooldown is None:
            cooldown = _read_int(pawn, "BlackMarketCooldownTimestamp")
        if visited is None:
            visited = _read_bool(pc, "bBlackMarketMachineDiscovered")
            if visited is None:
                visited = _read_bool(pawn, "bBlackMarketMachineDiscovered")
    now = int(time.time())
    ready = cooldown is not None and cooldown <= now
    return {
        "ok": True,
        "message": f"cooldown={cooldown} visited={visited} now={now} ready={ready}",
        "cooldown": cooldown,
        "visited": visited,
    }


def _is_world_shop(machine: Any) -> bool:
    """True for PersistentLevel IO_VendingMachine_BlackMarket (not spawn copies)."""
    return str(getattr(machine, "Name", "") or "") == "IO_VendingMachine_BlackMarket"


def _read_stock_serials(machine: Any) -> list[str]:
    rows = _vendor_rows(machine)
    if not rows:
        return []
    row = rows[0]
    out: list[str] = []
    try:
        serials = getattr(row, "Serials", None)
        if serials is None:
            return out
        for i in range(len(serials)):
            out.append(str(serials[i]))
    except Exception:
        pass
    return out


def read_shop_stock(*, prefer_world: bool = False) -> dict[str, Any]:
    """Read live 8-slot stock from nearest shop or PersistentLevel world shop."""
    machine = _find_world_shop() if prefer_world else (_nearest_machine() or _find_world_shop())
    if machine is None:
        return {
            "ok": False,
            "message": "No black market machine loaded.",
            "serials": [],
            "slot_count": 0,
        }
    serials = _read_stock_serials(machine)
    rows = _vendor_rows(machine)
    override = _read_int(rows[0], "OverrideRemainingTime") if rows else None
    path = _obj_path(machine)
    short = path.rsplit(".", 1)[-1] if "." in path else path
    return {
        "ok": True,
        "message": f"stock {len(serials)}/8 on {short}",
        "serials": serials,
        "slot_count": len(serials),
        "machine_path": path,
        "is_world_shop": _is_world_shop(machine),
        "shuffle_requested": _read_bool(machine, "bShuffleRequested"),
        "override_remaining": override,
    }


def reroll_black_market_parts(player_index: int) -> dict[str, Any]:
    """Host RPC — rolls new BM parts (call before respawn so fresh shop gets new stock)."""
    _owners, pcs, err = _owners_for_index(int(player_index))
    if err:
        return {"ok": False, "message": err}
    if not pcs:
        return {"ok": False, "message": "No PlayerController for reroll."}
    pc = pcs[0]
    fn = getattr(pc, "ServerRerollBlackMarketParts", None)
    if not callable(fn):
        return {"ok": False, "message": "ServerRerollBlackMarketParts not on PlayerController."}
    try:
        fn()
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "message": f"Reroll failed: {type(ex).__name__}: {ex}"}
    _log("ServerRerollBlackMarketParts")
    return {"ok": True, "message": "Reroll requested."}


def apply_black_market(
    player_index: int,
    *,
    clear_cooldown: bool = False,
    poke_machines: bool = True,
    snapshot: bool = True,
) -> str:
    """Clear purchase cooldown only. Use-timer / map / stock are not supported."""
    owners, pcs, err = _owners_for_index(int(player_index))
    if err:
        return err
    if not clear_cooldown:
        snap = read_state(int(player_index))
        return str(snap.get("message") or "Black market unchanged.")
    wrote = _write_cooldown_owners(owners, pcs)
    vend = 0
    machine_hits: list[str] = []
    if poke_machines:
        seen: set[int] = set()
        for target in _machines_for_purchase_clear():
            if id(target) in seen:
                continue
            seen.add(id(target))
            hits = _clear_machine_cooldown(target)
            if hits:
                vend += 1
                machine_hits.extend(hits[:8])
                _log("cooldown " + _obj_path(target) + " " + ",".join(hits[:12]))
    pings: list[str] = []
    for pc in pcs:
        pings.extend(_ping_pc_timers(pc))
    notes = (
        f"purchase_cd={_COOLDOWN_PAST} wrote={wrote} machines={vend} "
        f"hits={','.join(machine_hits[:10]) or 'none'} "
        f"sync={','.join(pings) or 'skip'}"
    )
    if not snapshot:
        _log(notes)
        return notes
    snap = read_state(int(player_index))
    msg = notes + "; " + str(snap.get("message") or "")
    _log(msg)
    return msg


_NEAR_PLAYER_RADIUS = 3500.0
_placed_bm_actors: list[Any] = []


def remember_placed_black_market(actor: Any) -> None:
    """Track shops we placed/relocated so refresh can remove them."""
    if actor is None or _is_default_obj(actor):
        return
    for existing in _placed_bm_actors:
        if existing is actor:
            return
    _placed_bm_actors.append(actor)


def _script_names(machine: Any) -> str:
    bits: list[str] = []
    try:
        data = getattr(machine, "ScriptData", None)
        inst = getattr(data, "Instances", None) if data is not None else None
        if inst is None:
            return ""
        for i in range(int(len(inst))):
            try:
                bits.append(type(inst[i]).__name__)
            except Exception:
                break
    except Exception:
        pass
    return " ".join(bits)


def _looks_like_black_market(machine: Any) -> bool:
    if machine is None or _is_default_obj(machine):
        return False
    blob = " ".join(
        (
            _obj_path(machine),
            str(getattr(machine, "Name", "") or ""),
            _script_names(machine),
        )
    ).lower()
    return "blackmarket" in blob or "vendingmachine_blackmarket" in blob


def _collect_nearby_black_market_machines(*, radius: float) -> list[Any]:
    """Find BM shops near the player, including OakVendingMachine_* copies and _SPAWNED."""
    loc = _pawn_loc()
    radius_sq = float(radius) * float(radius)
    out: list[Any] = []
    seen: set[int] = set()

    def _add(machine: Any, *, force: bool = False) -> None:
        if machine is None or _is_default_obj(machine):
            return
        key = id(machine)
        if key in seen:
            return
        if not force and not _looks_like_black_market(machine):
            return
        if loc is not None:
            try:
                if _dist_sq(machine.K2_GetActorLocation(), loc) > radius_sq:
                    return
            except Exception:
                if not force:
                    return
        seen.add(key)
        out.append(machine)

    for machine in list(_placed_bm_actors):
        _add(machine, force=True)
    for machine in _iter_black_market_machines():
        _add(machine)
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp

        for item in list(getattr(ssp, "_SPAWNED", None) or []):
            label = str(getattr(item, "label", "") or "").lower()
            actor = getattr(item, "actor", None)
            if "blackmarket" in label or "vendingmachine_blackmarket" in label:
                _add(actor, force=True)
            elif actor is not None:
                _add(actor)
    except Exception:
        pass
    # Copies are often named OakVendingMachine_* with no "blackmarket" in the path —
    # pick nearby vending machines that carry a BlackMarket script.
    try:
        raw = list(unrealsdk.find_all("OakVendingMachine", False) or [])
    except Exception:
        raw = []
    for obj in raw:
        _add(obj)
    return out


def _destroy_actor_safe(actor: Any) -> bool:
    for name in ("K2_DestroyActor", "DestroyActor", "Destroy"):
        fn = getattr(actor, name, None)
        if callable(fn):
            try:
                fn()
                return True
            except Exception:
                pass
    return False


def _hide_and_banish(actor: Any) -> bool:
    """PersistentLevel shops often ignore Destroy — hide + teleport far instead."""
    hits = 0
    try:
        loc = actor.K2_GetActorLocation()
        rot = actor.K2_GetActorRotation()
        if _true_bm_loc is not None:
            loc.X, loc.Y, loc.Z = _true_bm_loc
        else:
            loc.X = float(loc.X) + 50000.0
            loc.Y = float(loc.Y) + 50000.0
            loc.Z = float(loc.Z) - 20000.0
        tele = getattr(actor, "K2_TeleportTo", None)
        if callable(tele):
            tele(loc, rot)
            hits += 1
        else:
            set_loc = getattr(actor, "K2_SetActorLocation", None)
            if callable(set_loc):
                set_loc(loc, False, None, True)
                hits += 1
    except Exception:
        pass
    for name, value in (
        ("SetActorHiddenInGame", True),
        ("SetActorEnableCollision", False),
        ("SetActorTickEnabled", False),
    ):
        fn = getattr(actor, name, None)
        if callable(fn):
            try:
                fn(value)
                hits += 1
            except Exception:
                pass
    return hits > 0


def restore_black_market_visibility(actor: Any) -> None:
    """Undo hide/banish when we bring the weekly shop back to the player."""
    if actor is None:
        return
    for name, value in (
        ("SetActorHiddenInGame", False),
        ("SetActorEnableCollision", True),
        ("SetActorTickEnabled", True),
    ):
        fn = getattr(actor, name, None)
        if callable(fn):
            try:
                fn(value)
            except Exception:
                pass
    remember_placed_black_market(actor)


def destroy_nearby_black_market_machines(*, radius: float = _NEAR_PLAYER_RADIUS) -> tuple[int, int]:
    """Remove shops at the player's feet (destroy copies; banish PersistentLevel world shop)."""
    global _placed_bm_actors
    destroyed = 0
    failed = 0
    kept_memory: list[Any] = []
    for machine in _collect_nearby_black_market_machines(radius=radius):
        path = _obj_path(machine)
        is_world = _is_world_shop(machine) or (
            "persistentlevel" in path.lower() and "io_vendingmachine_blackmarket" in path.lower()
        )
        ok = False
        if not is_world:
            ok = _destroy_actor_safe(machine)
            if ok:
                destroyed += 1
                _log(f"destroyed nearby BM copy {path}")
        if not ok:
            # World shop (or destroy refused): hide + teleport away so it is gone visually.
            if _hide_and_banish(machine):
                destroyed += 1
                ok = True
                _log(f"banished nearby BM {path}")
            else:
                failed += 1
                kept_memory.append(machine)
                _log(f"remove failed nearby BM {path}")
        if not ok:
            kept_memory.append(machine)
    # Drop removed entries from oak _SPAWNED tracking.
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp

        spawned = getattr(ssp, "_SPAWNED", None)
        if isinstance(spawned, list):
            kept = []
            for item in list(spawned):
                label = str(getattr(item, "label", "") or "").lower()
                actor = getattr(item, "actor", None)
                if "blackmarket" in label or "vendingmachine_blackmarket" in label:
                    continue
                if actor is not None and any(actor is m for m in kept_memory):
                    kept.append(item)
                    continue
                if actor is not None and _looks_like_black_market(actor):
                    # Still in remove set → drop from tracker
                    continue
                kept.append(item)
            spawned[:] = kept
    except Exception:
        pass
    _placed_bm_actors = kept_memory
    return destroyed, failed


def cancel_ready_followup() -> None:
    global _pending_ready_until
    _pending_ready_until = 0.0


def request_ready_followup(player_index: int, seconds: float = 10.0) -> None:
    global _pending_ready_until, _pending_ready_index, _pending_ready_tick
    _pending_ready_index = int(player_index)
    _pending_ready_until = time.monotonic() + float(seconds)
    _pending_ready_tick = 0.0


def tick_black_market(now: float | None = None) -> None:
    global _pending_ready_until, _pending_ready_tick
    if _pending_ready_until <= 0.0:
        return
    now = time.monotonic() if now is None else float(now)
    if now - _pending_ready_tick < 2.0:
        return
    _pending_ready_tick = now
    apply_black_market(
        _pending_ready_index,
        clear_cooldown=True,
        poke_machines=False,
        snapshot=False,
    )
    if now >= _pending_ready_until:
        _pending_ready_until = 0.0
