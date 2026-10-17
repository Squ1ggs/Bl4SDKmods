"""Shared party/player helpers for Squ1ggs's Boosting Tools.

This intentionally excludes GenieBotControl's lobby/session kick timers and lobby control commands.
"""
from __future__ import annotations

import time
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


_SHIFT_SESSION_CACHE: list[dict[str, Any]] = []
_SHIFT_SESSION_CACHE_TS: float = 0.0
_SHIFT_SESSION_CACHE_TTL_SEC: float = 5.0


def _safe_name_str(raw: Any) -> str:
    try:
        text = str(raw or "").strip()
    except Exception:
        return ""
    if not text or text.startswith("<") or text.lower() in {"none", "null"}:
        return ""
    if "oakplayercontroller" in text.lower() or "default__" in text.lower():
        return ""
    return text[:200]


def _guess_platform_kind(*blobs: str) -> str:
    """Best-effort xbox|psn|steam|epic|other from id/name text."""
    hay = " ".join(str(b or "") for b in blobs).lower()
    if not hay.strip():
        return ""
    if any(x in hay for x in ("xbox", "xbl", "live", "gdk", "xsapi")):
        return "xbox"
    if any(x in hay for x in ("psn", "playstation", "sony", "np_")):
        return "psn"
    if any(x in hay for x in ("steam", "steamid", "valve")):
        return "steam"
    if any(x in hay for x in ("epic", "eos", "egs")):
        return "epic"
    return "other"


_PLATFORM_NAME_ATTRS: tuple[str, ...] = (
    "PlatformName",
    "PlatformUserName",
    "OnlinePlayerName",
    "PlatformPlayerName",
    "UniqueProxyName",
    "Nickname",
    "GamerTag",
    "Gamertag",
)
_PLATFORM_ID_ATTRS: tuple[str, ...] = (
    "PlatformUserId",
    "PlatformId",
    "UniqueNetId",
    "UniqueId",
    "OnlineId",
    "AccountId",
    "ShiftAccountId",
    "SHiFTAccountId",
    "ShiftId",
)
_DISPLAY_NAME_ATTRS: tuple[str, ...] = (
    "PlayerNamePrivate",
    "PlayerName",
    "CachedPlayerName",
    "DisplayName",
    "UserName",
)


def _pc_for_player_state(ps: Any) -> Any | None:
    """Resolve the live PlayerController for this PlayerState (ULM-style naming)."""
    if ps is None:
        return None
    try:
        local_pc = get_pc()
    except Exception:
        local_pc = None
    try:
        if local_pc is not None and getattr(local_pc, "PlayerState", None) is ps:
            return local_pc
    except Exception:
        pass
    world, _gs = _gbc_session_world_and_gamestate()
    try:
        return _gbc_find_pc_for_player_state(ps, world)
    except Exception:
        return None


def _read_name_attrs(obj: Any, attrs: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    if obj is None:
        return out
    for attr in attrs:
        try:
            val = _safe_name_str(getattr(obj, attr, None))
        except Exception:
            val = ""
        if val and val not in out:
            out.append(val)
    return out


def _read_id_blobs(obj: Any) -> list[str]:
    out: list[str] = []
    if obj is None:
        return out
    for attr in _PLATFORM_ID_ATTRS:
        try:
            raw = getattr(obj, attr, None)
            if callable(raw):
                raw = raw()
        except Exception:
            continue
        blob = _safe_name_str(raw)
        if blob and blob not in out:
            out.append(blob)
    return out


def _ps_platform_fields(ps: Any, pc: Any | None = None) -> tuple[str, str]:
    """Return (platform_name, platform_kind) from PlayerState + PlayerController."""
    if ps is None and pc is None:
        return "", ""
    if pc is None:
        pc = _pc_for_player_state(ps)
    platform_name = ""
    id_blobs: list[str] = []
    for obj in (ps, pc):
        for val in _read_name_attrs(obj, _PLATFORM_NAME_ATTRS):
            if not platform_name:
                platform_name = val
            id_blobs.append(val)
        id_blobs.extend(_read_id_blobs(obj))
    # Prefer ULM's gathered "platform" alias when present (PC-aware).
    if pc is not None:
        try:
            from ultra_local_menu import _pc_all_names as _ulm_pc_names  # noqa: PLC0415

            names = dict(_ulm_pc_names(pc) or {})
            ulm_plat = _safe_name_str(names.get("platform"))
            if ulm_plat:
                platform_name = ulm_plat
            for key, val in names.items():
                if str(key).startswith("platform"):
                    blob = _safe_name_str(val)
                    if blob:
                        id_blobs.append(blob)
        except Exception:
            pass
    kind = _guess_platform_kind(*id_blobs)
    return platform_name, kind


def _collect_shift_session_rows_light() -> list[dict[str, Any]]:
    """Cached ShiftSession UserList — prefer ULM helper when available."""
    global _SHIFT_SESSION_CACHE, _SHIFT_SESSION_CACHE_TS
    now = time.monotonic()
    if (
        _SHIFT_SESSION_CACHE_TS > 0.0
        and (now - _SHIFT_SESSION_CACHE_TS) < _SHIFT_SESSION_CACHE_TTL_SEC
    ):
        return list(_SHIFT_SESSION_CACHE)
    rows: list[dict[str, Any]] = []
    try:
        from ultra_local_menu import _collect_shift_session_rows as _ulm_collect  # noqa: PLC0415

        rows = list(_ulm_collect() or [])
    except Exception:
        rows = []
    if not rows:
        try:
            mgr = None
            for hint in ("OakShiftSessionManager", "ShiftSessionManager"):
                try:
                    for obj in find_all(hint, False) or []:
                        if obj is None or _is_obj_cdo(obj):
                            continue
                        mgr = obj
                        break
                except Exception:
                    continue
                if mgr is not None:
                    break
            if mgr is not None:
                for attr in ("UserList", "Users", "Sessions", "ActiveSessions"):
                    try:
                        sess_list = getattr(mgr, attr, None)
                    except Exception:
                        sess_list = None
                    if sess_list is None or isinstance(sess_list, (str, bytes)):
                        continue
                    try:
                        items = list(sess_list)
                    except Exception:
                        continue
                    for i, sess in enumerate(items):
                        if sess is None:
                            continue
                        try:
                            dn = _safe_name_str(getattr(sess, "DisplayName", None))
                            un = _safe_name_str(getattr(sess, "UserName", None))
                            sid = ""
                            for sid_attr in ("ShiftId", "SHiFTId", "ShiftAccountId", "AccountId"):
                                sid = _safe_name_str(getattr(sess, sid_attr, None))
                                if sid:
                                    break
                        except Exception:
                            dn, un, sid = "", "", ""
                        if dn or un:
                            rows.append(
                                {
                                    "session_index": int(i),
                                    "display_name": dn,
                                    "user_name": un,
                                    "shift_id": sid,
                                }
                            )
                    if rows:
                        break
        except Exception:
            rows = []
    _SHIFT_SESSION_CACHE = rows
    _SHIFT_SESSION_CACHE_TS = now
    return list(rows)


def _identity_name_candidates(ps: Any, pc: Any | None, display: str) -> list[str]:
    """All usable aliases from PS + PC (same places ULM party labels read)."""
    candidates: list[str] = []
    if display:
        candidates.append(display)
    for obj in (ps, pc):
        for val in _read_name_attrs(obj, _DISPLAY_NAME_ATTRS):
            if val not in candidates:
                candidates.append(val)
        for val in _read_name_attrs(obj, _PLATFORM_NAME_ATTRS):
            if val not in candidates:
                candidates.append(val)
    if pc is not None:
        try:
            from ultra_local_menu import _pc_all_names as _ulm_pc_names  # noqa: PLC0415

            for val in dict(_ulm_pc_names(pc) or {}).values():
                text = _safe_name_str(val)
                if text and text not in candidates:
                    candidates.append(text)
        except Exception:
            pass
    return candidates


def _match_shift_name_for_ps(
    ps: Any,
    display: str,
    sessions: list[dict[str, Any]],
    *,
    pc: Any | None = None,
) -> str:
    if not sessions:
        return ""
    if pc is None:
        pc = _pc_for_player_state(ps)
    # Prefer ULM's PC↔ShiftSession pairing when available (correct UserList match).
    if pc is not None:
        try:
            from ultra_local_menu import (  # noqa: PLC0415
                _match_shift_session_for_pc as _ulm_match,
            )

            matched = _ulm_match(pc, sessions)
            if isinstance(matched, dict):
                dn = _safe_name_str(matched.get("display_name"))
                un = _safe_name_str(matched.get("user_name"))
                if dn:
                    return dn
                if un:
                    return un
        except Exception:
            pass
    candidates = _identity_name_candidates(ps, pc, display)
    norms = {_gbc_normalize_name(c) for c in candidates if _gbc_normalize_name(c)}
    if not norms:
        return ""
    for row in sessions:
        for key in ("display_name", "user_name"):
            val = _safe_name_str(row.get(key))
            if not val:
                continue
            nn = _gbc_normalize_name(val)
            if nn and (nn in norms or any(nn in n or n in nn for n in norms if len(n) >= 3)):
                return val
    return ""


def _player_identity_for_ps(ps: Any, display_name: str = "") -> dict[str, str]:
    """SHiFT + platform aliases via PlayerController (ULM naming), not PS-only."""
    display = (display_name or _gbc_resolve_player_display_name(ps) or "").strip()
    pc = _pc_for_player_state(ps)
    platform_name, platform_kind = _ps_platform_fields(ps, pc)
    shift_name = ""
    try:
        sessions = _collect_shift_session_rows_light()
        shift_name = _match_shift_name_for_ps(ps, display, sessions, pc=pc)
    except Exception:
        shift_name = ""
    # Prefer matched SHiFT display; else keep engine display name.
    name = shift_name or display
    # If platform name equals the shown name, still keep it when kind is known —
    # otherwise the toggle has nothing distinct to show. Hide only exact dupes
    # with no platform kind (same string, no Xbox/PSN/Steam hint).
    if (
        platform_name
        and _gbc_normalize_name(platform_name) == _gbc_normalize_name(name)
        and not platform_kind
    ):
        platform_name = ""
    elif (
        platform_name
        and _gbc_normalize_name(platform_name) == _gbc_normalize_name(name)
        and platform_kind
    ):
        # Same string as SHiFT — still show "Xbox: Name" when kind differs.
        pass
    return {
        "name": name[:200],
        "shift_name": (shift_name or name)[:200],
        "platform_name": platform_name[:200],
        "platform_kind": platform_kind,
    }


def _player_aliases_for_match(row_or_ps: Any) -> list[str]:
    """Normalized alias list for kick-exempt / name matching."""
    aliases: list[str] = []
    if isinstance(row_or_ps, dict):
        for key in ("name", "shift_name", "platform_name"):
            raw = str(row_or_ps.get(key) or "").strip()
            if raw:
                aliases.append(raw)
    else:
        ident = _player_identity_for_ps(row_or_ps)
        for key in ("name", "shift_name", "platform_name"):
            raw = str(ident.get(key) or "").strip()
            if raw:
                aliases.append(raw)
    out: list[str] = []
    seen: set[str] = set()
    for a in aliases:
        n = _gbc_normalize_name(a)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


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
    return _collapse_duplicate_player_names(out, pa, world, local_pc, local_ps)


def _pc_is_camera_shell(pc: Any) -> bool:
    text = str(getattr(getattr(pc, "Class", None), "Name", "") or pc or "").lower()
    return "debugcamera" in text or "spectator" in text


def _collapse_duplicate_player_names(
    rows: List[Tuple[int, str]],
    pa: Any,
    world: Any,
    local_pc: Any,
    local_ps: Any,
) -> List[Tuple[int, str]]:
    """One dropdown row per person. A camera shell can reuse the local name."""
    if len(rows) < 2 or pa is None:
        return rows
    local_pawn = getattr(local_pc, "Pawn", None) if local_pc is not None else None
    grouped: dict[str, List[Tuple[int, str, bool, bool, bool]]] = {}
    order: List[str] = []
    for index, name in rows:
        try:
            ps = pa[int(index)]
        except Exception:
            ps = None
        pc = local_pc if ps is not None and ps is local_ps else _gbc_find_pc_for_player_state(ps, world)
        camera = _pc_is_camera_shell(pc)
        pawn = None
        if pc is not None:
            try:
                pawn = getattr(pc, "Pawn", None)
            except Exception:
                pawn = None
        same_pawn = pawn is not None and local_pawn is not None and pawn is local_pawn and ps is not local_ps
        key = _gbc_normalize_name(name) or str(name or "").casefold()
        if key not in grouped:
            order.append(key)
            grouped[key] = []
        is_local = ps is not None and local_ps is not None and ps is local_ps
        grouped[key].append(
            (int(index), name, camera or same_pawn, pawn is not None and not camera, is_local)
        )
    collapsed: List[Tuple[int, str]] = []
    for key in order:
        group = grouped[key]
        if len(group) == 1:
            collapsed.append((group[0][0], group[0][1]))
            continue
        local_rows = [row for row in group if row[4]]
        if local_rows:
            collapsed.append((local_rows[0][0], local_rows[0][1]))
            continue
        real = [row for row in group if row[3] and not row[2]]
        if real:
            collapsed.append((real[0][0], real[0][1]))
            continue
        plain = [row for row in group if not row[2]]
        pick = plain[0] if plain else group[0]
        collapsed.append((pick[0], pick[1]))
    collapsed.sort(key=lambda row: row[0])
    return collapsed


def _gbc_run_session_timer_from_give_serial() -> None:
    # GenieBotControl used this to trigger its lobby/session kick timer. Removed on purpose.
    return None
