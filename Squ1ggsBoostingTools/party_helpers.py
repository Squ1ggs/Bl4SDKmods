"""Shared party/player helpers for Squ1ggs's Boosting Tools.

This intentionally excludes GenieBotControl's lobby/session kick timers and lobby control commands.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from mods_base import ENGINE, get_pc
from unrealsdk import find_all, logging

_PREFIX = "[Squ1ggs's Boosting Tools]"


def _log(msg: str, *args: Any) -> None:
    logging.info(_PREFIX + " " + (msg % args if args else msg))


def _is_obj_cdo(obj: Any) -> bool:
    cls = getattr(obj, "Class", None)
    if cls is None:
        return False
    cdo = getattr(cls, "ClassDefaultObject", None)
    return cdo is not None and obj is cdo


def _gbc_net_driver(world: Any) -> Optional[Any]:
    if world is None:
        return None
    nd = getattr(world, "NetDriver", None)
    if nd is not None:
        return nd
    gnd = getattr(world, "GetNetDriver", None)
    if callable(gnd):
        try:
            return gnd()
        except Exception:
            pass
    return None


def _gbc_pc_has_listen_authority() -> bool:
    pc = get_pc()
    if pc is None:
        return False
    try:
        return bool(pc.HasAuthority())
    except Exception:
        return True


def _gbc_is_listen_host_world(world: Any) -> bool:
    if world is None:
        return False
    if not _gbc_pc_has_listen_authority():
        return False
    try:
        from unrealsdk.unreal import ENetMode

        mode = world.GetNetMode()
        if mode in (ENetMode.NM_ListenServer, ENetMode.NM_Standalone):
            return True
    except Exception:
        pass
    try:
        # 0 = Standalone, 2 = ListenServer — both allow host-side economy writes.
        return int(world.GetNetMode()) in (0, 2)
    except Exception:
        return True


def _gbc_session_world_and_gamestate() -> Tuple[Optional[Any], Optional[Any]]:
    try:
        if ENGINE is None:
            return None, None
        viewport = getattr(ENGINE, "GameViewport", None)
        if viewport is None:
            return None, None
        w = getattr(viewport, "World", None)
    except Exception:
        w = None
    if w is None:
        return None, None
    try:
        return w, getattr(w, "GameState", None)
    except Exception:
        return w, None


def _gbc_resolve_player_display_name(ps: Any) -> str:
    if ps is None:
        return "(no ps)"
    gpn = getattr(ps, "GetPlayerName", None)
    if callable(gpn):
        try:
            s = gpn()
            if s is not None:
                return str(s)[:200]
        except Exception:
            pass
    for attr in ("PlayerName", "PlayerNamePrivate", "CachedPlayerName"):
        raw = getattr(ps, attr, None)
        if raw is None:
            continue
        if isinstance(raw, str):
            return raw[:200] if raw else "(no name)"
        if callable(raw):
            try:
                s = raw()
                if s is not None:
                    return str(s)[:200]
            except Exception:
                continue
            continue
        return str(raw)[:200]
    try:
        return str(getattr(ps, "PlayerId", None) or ps)[:80]
    except Exception:
        return "(unknown)"


def _gbc_normalize_name(s: str) -> str:
    """Lowercase alnum-only name for loose matching (SHiFT vs PlayerName)."""
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def _gbc_resolve_player_index_for_name_substring(gs: Any, name_sub: str) -> Tuple[Optional[int], str]:
    t = (name_sub or "").strip()
    if not t:
        return None, "empty name substring"
    pa = getattr(gs, "PlayerArray", None)
    if pa is None:
        return None, "PlayerArray missing"
    try:
        n = len(pa)
    except Exception:
        return None, "could not read PlayerArray length"
    want = _gbc_normalize_name(t)
    raw_key = t.lower()
    if not want and not raw_key:
        return None, "empty name substring"
    scored: List[Tuple[int, int]] = []  # (score, index)
    for i in range(n):
        try:
            ps = pa[i]
        except Exception:
            continue
        if ps is None:
            continue
        nm = _gbc_resolve_player_display_name(ps)
        nm_norm = _gbc_normalize_name(nm)
        nm_low = nm.lower()
        score = -1
        if want and nm_norm == want:
            score = 1000
        elif raw_key and nm_low == raw_key:
            score = 900
        elif want and nm_norm.startswith(want) and len(want) >= 3:
            score = 700 + min(len(want), 50)
        elif want and want.startswith(nm_norm) and len(nm_norm) >= 3:
            # Typed SHiFT display ("echo4mods") contains engine name ("echo4")
            score = 650 + min(len(nm_norm), 50)
        elif want and len(want) >= 3 and (want in nm_norm or nm_norm in want):
            score = 400 + min(len(want), len(nm_norm), 40)
        elif raw_key in nm_low or (len(nm_low) >= 3 and nm_low in raw_key):
            score = 200
        if score >= 0:
            scored.append((score, i))
    if not scored:
        return None, "no name contains %r — refresh the GUI player list" % t
    scored.sort(key=lambda x: (-x[0], x[1]))
    best_score, best_i = scored[0]
    ties = [i for s, i in scored if s == best_score]
    if len(ties) > 1:
        return None, "ambiguous %r — indices %s" % (t, ties)
    return best_i, ""


def _gbc_find_pc_for_player_state(ps: Any, world: Optional[Any] = None) -> Optional[Any]:
    if ps is None:
        return None
    if world is not None:
        nd = _gbc_net_driver(world)
        conns = getattr(nd, "ClientConnections", None) if nd is not None else None
        if conns is not None:
            try:
                n = len(conns)
            except Exception:
                n = 0
            for i in range(n):
                try:
                    c = conns[i]
                except Exception:
                    continue
                if c is None:
                    continue
                if getattr(c, "PlayerState", None) is ps:
                    rpc = getattr(c, "PlayerController", None)
                    if rpc is not None:
                        return rpc
    gpc = getattr(ps, "GetPlayerController", None)
    if callable(gpc):
        try:
            c = gpc()
            if c is not None:
                return c
        except Exception:
            pass
    owner = getattr(ps, "Owner", None)
    if owner is not None:
        for meth in ("GetOwnerController", "GetController", "GetPlayerController"):
            m = getattr(owner, meth, None)
            if callable(m):
                try:
                    c = m()
                    if c is not None and getattr(c, "PlayerState", None) is ps:
                        return c
                except Exception:
                    pass
    for cls in ("OakPlayerController", "PlayerController"):
        try:
            objs = find_all(cls, False) or []
        except Exception:
            objs = []
        for obj in objs:
            if obj is None or _is_obj_cdo(obj):
                continue
            if getattr(obj, "PlayerState", None) is ps:
                return obj
    return None



def _gbc_find_remote_pc_name_fallback(ps: Any, host_ps: Any, display_name: str, log_prefix: str) -> Optional[Any]:
    """Fallback resolver: scan OakPlayerController/PlayerController by PlayerState display name."""
    wanted = (display_name or _gbc_resolve_player_display_name(ps) or "").strip().lower()
    if not wanted:
        return None
    host_name = _gbc_resolve_player_display_name(host_ps).strip().lower() if host_ps is not None else ""
    for cls in ("OakPlayerController", "PlayerController"):
        try:
            objs = find_all(cls, False) or []
        except Exception:
            objs = []
        for obj in objs:
            if obj is None or _is_obj_cdo(obj):
                continue
            ops = getattr(obj, "PlayerState", None)
            if ops is None or ops is host_ps:
                continue
            nm = _gbc_resolve_player_display_name(ops).strip().lower()
            if not nm:
                continue
            if nm == wanted or wanted in nm or nm in wanted:
                if host_name and nm == host_name:
                    continue
                return obj
    return None


def _gbc_resolve_remote_pc_for_party_kick(
    ps: Any,
    world: Any,
    host_ps: Any,
    display_name: str,
    log_prefix: str,
) -> Optional[Any]:
    """Same resolution path for manual kick: NetDriver -> PS -> find_all, then name fallback."""
    rpc = _gbc_find_pc_for_player_state(ps, world)
    if rpc is not None and getattr(rpc, "PlayerState", None) is not host_ps:
        try:
            pc_path = str(getattr(rpc, "PathName", rpc))[:160]
        except Exception:
            pc_path = str(rpc)[:160]
        _log("%s: resolved remote pc via PlayerState match for %s -> %s", log_prefix, display_name, pc_path)
        return rpc
    _log(
        "%s: PlayerState match failed for %s; trying OakPlayerController PlayerName match",
        log_prefix,
        display_name,
    )
    rpc = _gbc_find_remote_pc_name_fallback(ps, host_ps, display_name, log_prefix)
    if rpc is None:
        _log("%s: no remote OakPlayerController found for %s", log_prefix, display_name)
    return rpc


def _gbc_party_kick_remote_pc(remote_pc: Any, reason: str) -> bool:
    """Call ClientPartyKick(reason). reason must be a Python str (wide string binding)."""
    fn = getattr(remote_pc, "ClientPartyKick", None)
    if not callable(fn):
        _log("gbc_party_kick_remote_pc: ClientPartyKick not callable on %s", type(remote_pc).__name__)
        return False
    try:
        fn(str(reason))
        return True
    except Exception as e:
        _log("gbc_party_kick_remote_pc: ClientPartyKick failed: %s", e)
        return False


def _kick_party_player_by_index(player_index: int, reason: str = "Kicked by host") -> bool:
    """Kick the selected remote party member by GameState.PlayerArray index."""
    world, gs = _gbc_session_world_and_gamestate()
    if world is None or gs is None:
        _log("Kick Player: no active world/game state.")
        return False
    if not _gbc_is_listen_host_world(world):
        _log("Kick Player: only the listen host can kick party players.")
        return False
    pa = getattr(gs, "PlayerArray", None)
    if pa is None:
        _log("Kick Player: GameState.PlayerArray missing.")
        return False
    try:
        ps = pa[int(player_index)]
    except Exception:
        _log("Kick Player: invalid party player index %s.", player_index)
        return False
    host_pc = get_pc()
    host_ps = getattr(host_pc, "PlayerState", None) if host_pc is not None else None
    display_name = _gbc_resolve_player_display_name(ps)
    if ps is None:
        _log("Kick Player: selected PlayerState is missing.")
        return False
    if host_ps is not None and ps is host_ps:
        _log("Kick Player: refusing to kick the local host (%s).", display_name)
        return False
    remote_pc = _gbc_resolve_remote_pc_for_party_kick(ps, world, host_ps, display_name, "Kick Player")
    if remote_pc is None:
        return False
    ok = _gbc_party_kick_remote_pc(remote_pc, reason)
    if ok:
        _log("Kick Player: requested party kick for %s.", display_name)
    return ok

def _ps_has_stable_id(ps: Any) -> bool:
    for attr in ("UniqueId", "UniqueNetId", "PlatformUserId", "PlayerId"):
        try:
            value = getattr(ps, attr, None)
            if callable(value):
                value = value()
        except Exception:
            continue
        text = str(value or "").strip()
        if not text or text.lower() in {"none", "0", "null"}:
            continue
        if text.startswith("<"):
            continue
        return True
    return False


def _ps_placeholder_display_name(name: str) -> bool:
    """Unreal default slot labels like 'Player 1' when no real identity is present."""
    import re

    return bool(re.fullmatch(r"Player\s*\d+", str(name or "").strip(), flags=re.IGNORECASE))


def _list_party_players() -> List[Tuple[int, str]]:
    """Live lobby members only — drop empty/placeholder PlayerArray stubs."""
    world, gs = _gbc_session_world_and_gamestate()
    pa = getattr(gs, "PlayerArray", None) if gs is not None else None
    if pa is None:
        return []
    try:
        n = len(pa)
    except Exception:
        return []
    try:
        local_pc = get_pc()
    except Exception:
        local_pc = None
    local_ps = getattr(local_pc, "PlayerState", None) if local_pc is not None else None
    out: List[Tuple[int, str]] = []
    for i in range(n):
        try:
            ps = pa[i]
        except Exception:
            ps = None
        if ps is None:
            continue
        name = _gbc_resolve_player_display_name(ps)
        if not str(name or "").strip():
            # Empty labels become "Player N" in the EXE and confuse the dropdown.
            if local_ps is not None and ps is local_ps:
                name = f"Host (#{i})"
            else:
                continue
        if local_ps is not None and ps is local_ps:
            # Prefer a non-placeholder host label when the engine still says "Player 0".
            if _ps_placeholder_display_name(name):
                for attr in ("OnlinePlayerName", "PlatformPlayerName", "Nickname", "DisplayName"):
                    try:
                        alt = str(getattr(ps, attr, "") or "").strip()
                    except Exception:
                        alt = ""
                    if alt and not _ps_placeholder_display_name(alt):
                        name = alt
                        break
                if _ps_placeholder_display_name(name):
                    name = f"Host (#{i})"
            out.append((i, name))
            continue
        # Remotes: ignore engine placeholder stubs even if a controller object exists.
        # Those "Player 1" rows are empty seats and confuse kick/fly/target UIs.
        if _ps_placeholder_display_name(name) and not _ps_has_stable_id(ps):
            continue
        if _ps_placeholder_display_name(name):
            # Controller-backed placeholders are still ghosts in practice — skip.
            continue
        pc = _gbc_find_pc_for_player_state(ps, world)
        if pc is not None:
            out.append((i, name))
            continue
        # No controller: keep only rows with a real id AND a non-placeholder name.
        if _ps_has_stable_id(ps) and not _ps_placeholder_display_name(name):
            out.append((i, name))
    # Solo fallback — never return an empty roster while a local PC exists.
    if not out and local_ps is not None:
        for i in range(n):
            try:
                ps = pa[i]
            except Exception:
                ps = None
            if ps is local_ps:
                out.append((i, _gbc_resolve_player_display_name(ps)))
                break
        if not out:
            out.append((0, _gbc_resolve_player_display_name(local_ps)))
    return out


def _gbc_run_session_timer_from_give_serial() -> None:
    # GenieBotControl used this to trigger its lobby/session kick timer. Removed on purpose.
    return None
