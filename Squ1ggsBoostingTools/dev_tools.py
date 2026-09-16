"""Developer perk and debug camera helpers for Squ1ggs's Boosting Tools."""
from __future__ import annotations

from typing import Any
import time

import unrealsdk
from mods_base import get_pc
from unrealsdk import logging

from .player_economy import _resolve_target_pc_for_index
from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate

_PREFIX = "[Squ1ggs's Boosting Tools | Dev]"
_MIN_DEBUG_SPEED = 0.05
_MAX_DEBUG_SPEED = 50.0
_DEFAULT_DEBUG_SPEED = 1.0
_debug_speed_value: float = _DEFAULT_DEBUG_SPEED
_dcc_cache: Any | None = None
_dcc_cache_until: float = 0.0
_freecam_intent: bool | None = None  # last requested ON/OFF; None = infer from game
_toggle_states_by_player: dict[str, dict[int, bool]] = {}

# Sticky overrides (re-applied from mobility_runtime.background_tick)
_weapons_restricted_sticky: dict[str, bool] = {}  # player_key -> restricted value
_ammo_regen_sticky: dict[str, float] = {}  # player_key -> rate (0 = disabled sticky)
_last_sticky_apply: float = 0.0
_STICKY_INTERVAL = 0.35
_last_loot_perk_batch_at: float = 0.0
_LOOT_PERK_COOLDOWN = 1.25  # Spawn Legendary/Epic — spam AVs pyunrealsdk


def loot_perk_batch_allowed() -> bool:
    """True when Spawn Legendary/Epic (perk 7) may run a new lobby batch."""
    global _last_loot_perk_batch_at
    now = time.monotonic()
    if now - _last_loot_perk_batch_at < _LOOT_PERK_COOLDOWN:
        return False
    _last_loot_perk_batch_at = now
    return True


_DEVPERK_LABELS = {
    0: "Give Experience",
    1: "Give 1 Million Cash",
    2: "Give 100k Eridium",
    3: "Kill All Enemies",
    4: "Grant ALL Customizations and Hover Drives",
    5: "Infinite Ammo",
    6: "God Mode",  # Direct bGodMode / invincible writes — replaces Demigod server perk
    7: "Spawn Legendary/Epic Loot",
}


def _log(message: str) -> None:
    logging.info(f"{_PREFIX} {message}")


def clamp_debug_speed(value: float) -> float:
    try:
        v = float(value)
    except Exception:
        v = _DEFAULT_DEBUG_SPEED
    return max(_MIN_DEBUG_SPEED, min(v, _MAX_DEBUG_SPEED))


def devperk_label(index: int) -> str:
    return _DEVPERK_LABELS.get(int(index), f"Unknown Perk {int(index)}")


def _devperk_player_key_from_pc(pc: Any | None, player_index: int | None = None) -> str:
    """Return a stable-ish key for tracking toggle-only dev perks per player.

    Infinite Ammo is a server toggle. God Mode uses direct field writes (bGodMode / invincible)
    instead of the Demigod ServerActivateDevPerk. The game does not expose a reliable
    readable ON/OFF for ammo, so the UI tracks what this mod last requested.
    """
    ps = getattr(pc, "PlayerState", None) if pc is not None else None
    for attr in ("UniqueId", "PlayerId", "SavedNetworkAddress", "PlayerNamePrivate", "PlayerName"):
        try:
            value = getattr(ps, attr, None) if ps is not None else None
            if callable(value):
                value = value()
            if value not in (None, ""):
                return f"ps:{attr}:{value}"
        except Exception:
            pass
    try:
        name_fn = getattr(ps, "GetPlayerName", None) if ps is not None else None
        if callable(name_fn):
            name = name_fn()
            if name:
                return f"name:{name}"
    except Exception:
        pass
    if pc is not None:
        try:
            return f"pc:{getattr(pc, 'Name', None) or pc}"
        except Exception:
            return f"pc:{pc}"
    return f"party_index:{player_index}"


def _devperk_states_for_player(player_index: int | None = None, pc: Any | None = None) -> dict[int, bool]:
    if pc is None:
        try:
            pc, _ = _pc_for_party_index(player_index)
        except Exception:
            pc = None
    key = _devperk_player_key_from_pc(pc, player_index)
    return _toggle_states_by_player.setdefault(key, {5: False, 6: False})


def devperk_toggle_state(index: int, player_index: int | None = None) -> bool | None:
    """Return cached toggle state for toggled dev perks for one player.

    New/unknown players are assumed OFF until this mod toggles them ON.
    """
    perk = int(index)
    if perk not in (5, 6):
        return None
    return bool(_devperk_states_for_player(player_index).get(perk, False))


def devperk_button_label(index: int, player_index: int | None = None) -> str:
    label = devperk_label(index)
    state = devperk_toggle_state(index, player_index)
    if state is None:
        return label
    return f"{label} [{'ON' if state else 'OFF'}]"


def _is_listen_host_safe() -> bool:
    try:
        world, _gs = _gbc_session_world_and_gamestate()
        return bool(world is not None and _gbc_is_listen_host_world(world))
    except Exception:
        return False


def _pc_for_party_index(player_index: int | None) -> tuple[Any | None, str]:
    # Dev perk server RPCs can be requested from a joined client through that
    # client's own local PlayerController. Do not block all cheats just because
    # we are not the listen host. Only host-side remote targeting should use the
    # PlayerArray resolver.
    if player_index is None:
        pc = get_pc()
        return pc, "" if pc is not None else "No local PlayerController found."
    if not _is_listen_host_safe():
        pc = get_pc()
        if pc is None:
            return None, "No local PlayerController found."
        return pc, "client-local PlayerController"
    pc, err = _resolve_target_pc_for_index(int(player_index))
    return pc, err


def _apply_ulm_god_mode(pc: Any, enabled: bool) -> int:
    """Best-effort god mode on PlayerController + pawn (same fields as ``ulm god``)."""
    pawn = getattr(pc, "Pawn", None) or getattr(pc, "AcknowledgedPawn", None)
    writes = 0
    for obj in (pc, pawn):
        if obj is None:
            continue
        for field in ("bGodMode", "GodMode", "bInvincible", "bCanBeDamaged"):
            if not hasattr(obj, field):
                continue
            value = (not enabled) if field == "bCanBeDamaged" else enabled
            try:
                setattr(obj, field, value)
                writes += 1
            except Exception:
                continue
    return writes


def read_ulm_god_mode(pc: Any | None) -> bool | None:
    """Live god-mode read (ULM-style ``bGodMode`` / invincible). None if no readable fields."""
    if pc is None:
        return None
    pawn = getattr(pc, "Pawn", None) or getattr(pc, "AcknowledgedPawn", None)
    seen = False
    for obj in (pc, pawn):
        if obj is None:
            continue
        for field in ("bGodMode", "GodMode", "bInvincible"):
            if not hasattr(obj, field):
                continue
            seen = True
            try:
                if bool(getattr(obj, field)):
                    return True
            except Exception:
                continue
    return False if seen else None


def _remember_devperk_state(perk: int, want: bool, player_index: int | None, pc: Any | None) -> None:
    """Cache toggle state under PC key and local/None key so All-target sticky stays aligned."""
    states = _devperk_states_for_player(player_index, pc)
    states[int(perk)] = bool(want)
    try:
        local_pc, _ = _pc_for_party_index(None)
    except Exception:
        local_pc = None
    if local_pc is None or pc is None:
        return
    try:
        same = local_pc is pc or str(getattr(local_pc, "Name", "")) == str(getattr(pc, "Name", ""))
    except Exception:
        same = False
    if not same:
        return
    local_states = _devperk_states_for_player(None, local_pc)
    if local_states is not states:
        local_states[int(perk)] = bool(want)


def set_god_mode(enabled: bool, player_index: int | None = None) -> str:
    """Set God Mode to an explicit ON/OFF (EXE sticky toggles)."""
    pc, err = _pc_for_party_index(player_index)
    if pc is None:
        raise RuntimeError(err or "No PlayerController found.")
    want = bool(enabled)
    writes = _apply_ulm_god_mode(pc, want)
    if writes <= 0:
        raise RuntimeError("God Mode: no godmode-style fields found on PC/pawn.")
    _remember_devperk_state(6, want, player_index, pc)
    _log(f"God Mode {'ON' if want else 'OFF'} ({writes} field writes).")
    return f"God Mode {'ON' if want else 'OFF'}"


def set_infinite_ammo(enabled: bool, player_index: int | None = None) -> str:
    """Toggle infinite ammo perk toward an explicit ON/OFF using cached state."""
    pc, err = _pc_for_party_index(player_index)
    if pc is None:
        raise RuntimeError(err or "No PlayerController found.")
    states = _devperk_states_for_player(player_index, pc)
    current = bool(states.get(5, False))
    want = bool(enabled)
    if current == want:
        return f"Infinite Ammo already {'ON' if want else 'OFF'}"
    fn = getattr(pc, "ServerActivateDevPerk", None)
    if not callable(fn):
        raise RuntimeError("Selected PlayerController does not expose ServerActivateDevPerk.")
    fn(5)
    states[5] = want
    _log(f"Infinite Ammo {'ON' if want else 'OFF'}.")
    return f"Infinite Ammo {'ON' if want else 'OFF'}"


def activate_devperk(index: int, player_index: int | None = None) -> str:
    perk = int(index)
    if perk < 0 or perk > 7:
        raise ValueError("Dev perk index must be 0 through 7.")
    pc, err = _pc_for_party_index(player_index)
    if pc is None:
        raise RuntimeError(err or "No PlayerController found.")
    return activate_devperk_on_pc(perk, pc, player_index=player_index)


def activate_devperk_on_pc(index: int, pc: Any, *, player_index: int | None = None) -> str:
    """Run a dev perk on a specific PlayerController (ULM target picker / host actions)."""
    perk = int(index)
    if perk < 0 or perk > 7:
        raise ValueError("Dev perk index must be 0 through 7.")
    if pc is None:
        raise RuntimeError("No PlayerController.")

    if perk == 6:
        live = read_ulm_god_mode(pc)
        cached = bool(_devperk_states_for_player(player_index, pc).get(6, False))
        current = bool(live) if live is not None else cached
        new_state = not current
        writes = _apply_ulm_god_mode(pc, new_state)
        if writes <= 0:
            raise RuntimeError("God Mode: no godmode-style fields found on PC/pawn.")
        _remember_devperk_state(6, new_state, player_index, pc)
        _log(f"God Mode {'ON' if new_state else 'OFF'} ({writes} field writes).")
        return "God Mode"

    fn = getattr(pc, "ServerActivateDevPerk", None)
    if not callable(fn):
        raise RuntimeError("Selected PlayerController does not expose ServerActivateDevPerk.")
    fn(perk)
    if perk == 5:
        states = _devperk_states_for_player(player_index, pc)
        states[5] = not bool(states.get(5, False))
    label = devperk_label(perk)
    _log(f"{label} on {getattr(pc, 'Name', '?')}.")
    return label


def _live_local_player() -> Any | None:
    try:
        players = [x for x in unrealsdk.find_all("OakLocalPlayer") if "Default__" not in getattr(x, "Name", "")]
        return players[0] if players else None
    except Exception:
        return None


def _is_freecam_controller(obj: Any | None) -> bool:
    if obj is None:
        return False
    try:
        label = str(getattr(obj, "Class", "")) + str(obj)
        return "DebugCameraController" in label
    except Exception:
        return False


_is_debug_camera_controller = _is_freecam_controller  # legacy alias


def _unwrap_gameplay_pc(pc: Any | None) -> Any | None:
    """Walk off a DebugCameraController shell back to the real PlayerController."""
    if not _is_freecam_controller(pc):
        return pc
    for attr in ("OriginalControllerRef", "OriginalController"):
        try:
            original = getattr(pc, attr, None)
            if original is not None and not _is_freecam_controller(original):
                return original
        except Exception:
            pass
    try:
        cm = getattr(pc, "CheatManager", None)
        outer = getattr(cm, "Outer", None) if cm is not None else None
        if outer is not None and not _is_freecam_controller(outer):
            return outer
    except Exception:
        pass
    return pc


_unwrap_debug_camera_controller = _unwrap_gameplay_pc  # legacy alias


def _session_raw_pc() -> Any | None:
    """Unmodified local controller pointer (may still be the freecam shell)."""
    try:
        pc = get_pc()
        if pc is not None:
            return pc
    except Exception:
        pass
    lp = _live_local_player()
    if lp is not None:
        try:
            pc = getattr(lp, "PlayerController", None)
            if pc is not None:
                return pc
        except Exception:
            pass
    return None


def _gameplay_pc() -> Any | None:
    """Local PlayerController with freecam possession stripped when possible."""
    raw = _session_raw_pc()
    if raw is not None:
        unwrapped = _unwrap_gameplay_pc(raw)
        if unwrapped is not None:
            return unwrapped
    try:
        return _unwrap_gameplay_pc(get_pc())
    except Exception:
        return None


_live_pc = _gameplay_pc  # legacy alias


def _invalidate_dcc_cache() -> None:
    global _dcc_cache, _dcc_cache_until
    _dcc_cache = None
    _dcc_cache_until = 0.0


def _cached_dcc() -> Any | None:
    global _dcc_cache, _dcc_cache_until
    now = time.monotonic()
    # A negative lookup is still a valid cache result. Without this, bridge
    # status polling ran find_all("DebugCameraController") every refresh while
    # freecam was off.
    if now < float(_dcc_cache_until or 0.0):
        return _dcc_cache
    found: Any | None = None
    for candidate in (_session_raw_pc(),):
        if _is_freecam_controller(candidate):
            found = candidate
            break
        try:
            cm = getattr(candidate, "CheatManager", None) if candidate is not None else None
            ref = getattr(cm, "DebugCameraControllerRef", None) if cm is not None else None
            if ref is not None:
                found = ref
                break
        except Exception:
            pass
    if found is None and _freecam_intent is True:
        try:
            cams = [
                x
                for x in unrealsdk.find_all("DebugCameraController", False)
                if "Default__" not in getattr(x, "Name", "")
            ]
            found = cams[0] if cams else None
        except Exception:
            found = None
    _dcc_cache = found
    _dcc_cache_until = now + (2.0 if found is not None else 10.0)
    return found


_live_dcc = _cached_dcc  # legacy alias


def _freecam_ref_on_pc(pc: Any | None) -> Any | None:
    if pc is None:
        return None
    try:
        cm = getattr(pc, "CheatManager", None)
        if cm is not None:
            ref = getattr(cm, "DebugCameraControllerRef", None)
            if ref is not None:
                return ref
    except Exception:
        pass
    return None


def _freecam_shell_active() -> bool:
    """True when OakLocalPlayer/get_pc still points at DebugCameraController."""
    raw = _session_raw_pc()
    if _is_freecam_controller(raw):
        return True
    try:
        return _is_freecam_controller(get_pc())
    except Exception:
        return False


def _freecam_is_live() -> bool:
    if _freecam_shell_active():
        return True
    gp = _gameplay_pc()
    if _freecam_ref_on_pc(gp) is not None and _freecam_intent is not False:
        return True
    return False


def _cheat_call(cm: Any, method_names: tuple[str, ...]) -> str | None:
    for name in method_names:
        fn = getattr(cm, name, None)
        if callable(fn):
            fn()
            return name
    return None


def _cheat_exec(target: Any, command: str) -> bool:
    for attr in ("ConsoleCommand", "ClientExec"):
        fn = getattr(target, attr, None)
        if callable(fn):
            try:
                fn(command)
                return True
            except Exception:
                continue
    return False


def _ensure_cheat_manager(pc: Any) -> Any:
    cm = getattr(pc, "CheatManager", None)
    if cm is not None:
        return cm
    cheat_class = getattr(pc, "CheatClass", None)
    if cheat_class is None:
        raise RuntimeError("PlayerController has no CheatClass.")
    cm = unrealsdk.construct_object(cheat_class, pc, "OakCheatManager_Squ1ggsBoostingTools")
    pc.CheatManager = cm
    return cm


def _resolve_local_cheat_context() -> tuple[Any, Any, Any]:
    """Return (raw_pc, gameplay_pc, CheatManager) for local freecam work."""
    raw = _session_raw_pc()
    gp = _gameplay_pc()
    if gp is None or _is_freecam_controller(gp):
        gp = _original_player_controller_for_debugcam()
    if gp is None or _is_freecam_controller(gp):
        raise RuntimeError("No local Oak PlayerController found for freecam.")
    cm = _ensure_cheat_manager(gp)
    return raw, gp, cm


_resolve_local_cheat = _resolve_local_cheat_context


def _freecam_original_player(raw_pc: Any | None) -> Any | None:
    for attr in ("OriginalPlayer", "Player"):
        try:
            player = getattr(raw_pc, attr, None) if raw_pc is not None else None
            if player is not None:
                return player
        except Exception:
            pass
    return _live_local_player()


def _try_freecam_method(
    label: str,
    target: Any | None,
    method_name: str,
    arg_options: tuple[tuple[Any, ...], ...] = (),
) -> str:
    fn = getattr(target, method_name, None) if target is not None else None
    if not callable(fn):
        return ""
    last_type_error: Exception | None = None
    for args in ((), *arg_options):
        try:
            fn(*args)
            suffix = "" if not args else f"({len(args)} arg)"
            return f"{label}.{method_name}{suffix}"
        except TypeError as exc:
            last_type_error = exc
            continue
        except Exception as exc:
            return f"{label}.{method_name} failed: {exc!r}"
    if last_type_error is not None:
        return f"{label}.{method_name} failed: {last_type_error!r}"
    return ""


def _restore_local_player_controller(gameplay_pc: Any | None) -> str | None:
    if gameplay_pc is None or _is_freecam_controller(gameplay_pc):
        return None
    lp = _live_local_player()
    if lp is None:
        return None
    try:
        lp.PlayerController = gameplay_pc
        return "lp.PlayerController=gp"
    except Exception as exc:
        return f"lp.PlayerController failed: {exc!r}"


def _clear_freecam_ref(cm: Any | None) -> str | None:
    if cm is None:
        return None
    try:
        if getattr(cm, "DebugCameraControllerRef", None) is not None:
            cm.DebugCameraControllerRef = None
            return "cm.DebugCameraControllerRef=None"
    except Exception as exc:
        return f"cm.DebugCameraControllerRef clear failed: {exc!r}"
    return None


def _restore_freecam_player_handoff(raw_pc: Any | None, gameplay_pc: Any | None) -> list[str]:
    """Reattach OakLocalPlayer + view to the real PlayerController (controller reattach)."""
    if raw_pc is None or gameplay_pc is None or not _is_freecam_controller(raw_pc):
        return []
    player = _freecam_original_player(raw_pc)
    pawn = _pawn_for_pc(gameplay_pc)
    tried: list[str] = []
    if player is not None:
        try:
            gameplay_pc.Player = player
            tried.append("gp.Player=OriginalPlayer")
        except Exception as exc:
            tried.append(f"gp.Player failed: {exc!r}")
        try:
            player.PlayerController = gameplay_pc
            tried.append("OriginalPlayer.PlayerController=gp")
        except Exception as exc:
            tried.append(f"OriginalPlayer.PlayerController failed: {exc!r}")
    restore_lp = _restore_local_player_controller(gameplay_pc)
    if restore_lp:
        tried.append(restore_lp)
    if pawn is not None:
        for label, target, method_name, arg_options in (
            ("gp", gameplay_pc, "ClientSetViewTarget", ((pawn,),)),
            ("gp", gameplay_pc, "SetViewTargetWithBlend", ((pawn,), (pawn, 0.0))),
            ("gp", gameplay_pc, "Possess", ((pawn,),)),
        ):
            result = _try_freecam_method(label, target, method_name, arg_options)
            if result:
                tried.append(result)
            if not _freecam_shell_active():
                return tried
    return tried


def _force_freecam_off(raw_pc: Any | None, gameplay_pc: Any, cm: Any) -> list[str]:
    """Escalating shutdown when native DisableDebugCamera leaves the DCC shell."""
    tried: list[str] = []
    for label, target, method_name in (
        ("raw", raw_pc, "DisableDebugCamera"),
        ("raw", raw_pc, "ToggleDebugCamera"),
        ("gp", gameplay_pc, "DisableDebugCamera"),
        ("gp", gameplay_pc, "ToggleDebugCamera"),
        ("cm", cm, "DisableDebugCamera"),
        ("cm", cm, "ToggleDebugCamera"),
    ):
        result = _try_freecam_method(label, target, method_name)
        if result:
            tried.append(result)
        if not _freecam_shell_active():
            clear = _clear_freecam_ref(cm)
            if clear:
                tried.append(clear)
            return tried
    for label, target, method_name in (
        ("cm", cm, "ViewSelf"),
        ("raw", _session_raw_pc(), "ServerViewSelf"),
        ("gp", gameplay_pc, "ServerViewSelf"),
    ):
        result = _try_freecam_method(label, target, method_name)
        if result:
            tried.append(result)
        if not _freecam_shell_active():
            clear = _clear_freecam_ref(cm)
            if clear:
                tried.append(clear)
            return tried
    for label, target in (("raw", _session_raw_pc()), ("gp", gameplay_pc), ("cm", cm)):
        if _cheat_exec(target, "ToggleDebugCamera"):
            tried.append(f"{label}.exec.ToggleDebugCamera")
        if not _freecam_shell_active():
            clear = _clear_freecam_ref(cm)
            if clear:
                tried.append(clear)
            return tried
    tried.extend(_restore_freecam_player_handoff(raw_pc, gameplay_pc))
    if not _freecam_shell_active():
        clear = _clear_freecam_ref(cm)
        if clear:
            tried.append(clear)
        return tried
    for cmd in ("DisableDebugCamera", "viewself"):
        if _cheat_exec(gameplay_pc, cmd):
            tried.append(f"gp.exec.{cmd}")
        if not _freecam_shell_active():
            break
    clear = _clear_freecam_ref(cm)
    if clear:
        tried.append(clear)
    _restore_local_player_controller(gameplay_pc)
    _invalidate_dcc_cache()
    return tried


def _try_call(fn: Any, *args: Any) -> bool:
    try:
        fn(*args)
        return True
    except Exception:
        return False


def _log_freecam_stuck(raw_pc: Any | None, gameplay_pc: Any, cm: Any, tried: list[str]) -> None:
    parts = [f"tried={','.join(tried) or 'none'}"]
    for label, obj in (("raw", raw_pc), ("gp", gameplay_pc), ("cm", cm)):
        if obj is None:
            continue
        try:
            name = getattr(obj, "Name", type(obj).__name__)
        except Exception:
            name = "?"
        parts.append(f"{label}={name}")
        if label == "cm":
            try:
                ref = getattr(obj, "DebugCameraControllerRef", None)
                if ref is not None:
                    parts.append(f"dcc_ref={getattr(ref, 'Name', ref)}")
            except Exception:
                pass
    _log("Freecam still active after shutdown — " + "; ".join(parts))


def _apply_speed_to_freecam(dcc: Any | None) -> None:
    if dcc is None:
        return
    try:
        _apply_debug_speed_to_controller(dcc, _debug_speed_value)
    except Exception:
        pass


def enable_debug_cam(player_index: int | None = None) -> str:
    del player_index  # local-only; party target ignored
    global _freecam_intent
    if _freecam_is_live():
        _freecam_intent = True
        _apply_speed_to_freecam(_cached_dcc() or _freecam_ref_on_pc(_gameplay_pc()))
        return "Freecam already active — reapplied speed."

    raw, gp, cm = _resolve_local_cheat_context()
    _invalidate_dcc_cache()
    used = _cheat_call(cm, ("EnableDebugCamera", "ToggleDebugCamera"))
    if used is None:
        raise RuntimeError("CheatManager has no EnableDebugCamera or ToggleDebugCamera.")
    _freecam_intent = True
    dcc = _freecam_ref_on_pc(gp) or _cached_dcc()
    _apply_speed_to_freecam(dcc)
    _log(f"Freecam enabled via {used}.")
    return "Freecam enabled locally."


def disable_debug_cam(player_index: int | None = None) -> str:
    return force_disable_debug_cam(player_index)


def force_disable_debug_cam(player_index: int | None = None) -> str:
    del player_index
    global _freecam_intent
    if not _freecam_shell_active() and not _freecam_is_live() and _freecam_intent is not True:
        _freecam_intent = False
        return "Freecam already off."

    raw, gp, cm = _resolve_local_cheat_context()
    was_live = _freecam_shell_active() or _freecam_is_live()
    tried: list[str] = []
    _invalidate_dcc_cache()
    used = _cheat_call(cm, ("DisableDebugCamera", "ToggleDebugCamera"))
    if used:
        tried.append(f"cm.{used}")
    if _freecam_shell_active():
        for _ in range(3):
            _invalidate_dcc_cache()
            tried.extend(_force_freecam_off(_session_raw_pc(), gp, cm))
            if not _freecam_shell_active():
                break
    clear = _clear_freecam_ref(cm)
    if clear:
        tried.append(clear)
    _restore_local_player_controller(gp)
    _freecam_intent = False
    _invalidate_dcc_cache()
    still_live = _freecam_shell_active()
    if was_live and still_live:
        _log_freecam_stuck(_session_raw_pc(), gp, cm, tried)
        return (
            "Freecam still active — try «Freecam OFF (force)» again or console: sqbt_freecam_off"
        )
    return "Freecam disabled locally." if was_live else "Freecam was not active."


def toggle_debug_cam(player_index: int | None = None) -> str:
    if _freecam_shell_active() or _freecam_is_live() or _freecam_intent is True:
        return force_disable_debug_cam(player_index)
    return enable_debug_cam(player_index)


def is_debug_cam_active() -> bool:
    return _freecam_shell_active() or _freecam_is_live()


def debug_cam_status() -> str:
    state = "ON" if (_freecam_shell_active() or _freecam_is_live()) else "OFF"
    speed = get_debug_cam_speed()
    return f"Freecam {state} · speed {speed:.2f}x"


def _apply_debug_speed_to_controller(dcc: Any, speed: float) -> None:
    try:
        dcc.SetPawnMovementSpeedScale(float(speed))
        return
    except Exception:
        pass
    try:
        dcc.SpeedScale = float(speed)
        return
    except Exception as exc:
        raise RuntimeError(f"Speed set failed: {exc!r}")


def _debug_cam_for_pc(pc: Any | None) -> Any | None:
    ref = _freecam_ref_on_pc(pc)
    if ref is not None:
        return ref
    return _cached_dcc()


def set_debug_cam_speed(value: float, player_index: int | None = None) -> str:
    global _debug_speed_value
    _debug_speed_value = clamp_debug_speed(value)
    del player_index
    dcc = _debug_cam_for_pc(_gameplay_pc())
    if dcc is None:
        return f"Freecam speed stored at {_debug_speed_value:.2f}x (no active freecam)."
    _apply_debug_speed_to_controller(dcc, _debug_speed_value)
    return f"Freecam speed set to {_debug_speed_value:.2f}x."


def get_debug_cam_speed() -> float:
    return float(_debug_speed_value)


DEBUG_CAMERA_MODES: tuple[str, ...] = (
    "Default",
    "ThirdPerson",
    "Fixed",
    "Orbit",
    "ThirdPersonViewModel",
    "FixedViewModel",
    "OrbitViewModel",
    "WideOrbitViewModel",
    "ThirdPersonReverse",
)


def _player_camera_manager(pc: Any | None) -> Any | None:
    if pc is None:
        return None
    for attr in ("PlayerCameraManager", "CameraManager"):
        try:
            cm = getattr(pc, attr, None)
            if cm is not None:
                return cm
        except Exception:
            pass
    return None


def _vector_xyz(value: Any) -> dict[str, float] | None:
    if value is None:
        return None
    try:
        return {
            "x": float(getattr(value, "X", 0.0)),
            "y": float(getattr(value, "Y", 0.0)),
            "z": float(getattr(value, "Z", 0.0)),
        }
    except Exception:
        return None


def _rotator_pyr(value: Any) -> dict[str, float] | None:
    if value is None:
        return None
    try:
        return {
            "pitch": float(getattr(value, "Pitch", 0.0)),
            "yaw": float(getattr(value, "Yaw", 0.0)),
            "roll": float(getattr(value, "Roll", 0.0)),
        }
    except Exception:
        return None


def get_debug_cam_location() -> dict[str, object]:
    """Current freecam transform for bridge / EXE status."""
    dcc = _debug_cam_for_pc(_gameplay_pc()) or _cached_dcc()
    if dcc is None:
        return {}
    loc = _vector_xyz(_actor_location(dcc))
    rot = None
    try:
        rot = _rotator_pyr(getattr(dcc, "GetControlRotation", None)() if callable(getattr(dcc, "GetControlRotation", None)) else getattr(dcc, "ControlRotation", None))
    except Exception:
        rot = None
    out: dict[str, object] = {}
    if loc:
        out["location"] = loc
    if rot:
        out["rotation"] = rot
    return out


def debug_cam_info() -> dict[str, object]:
    return {
        "active": is_debug_cam_active(),
        "status": debug_cam_status(),
        "speed": get_debug_cam_speed(),
        "modes": list(DEBUG_CAMERA_MODES),
        **get_debug_cam_location(),
    }


def set_freecam_distance(value: float, player_index: int | None = None) -> str:
    del player_index
    if not is_debug_cam_active():
        raise RuntimeError("Freecam is not active.")
    _, gp, _cm = _resolve_local_cheat()
    pcm = _player_camera_manager(gp)
    if pcm is None:
        raise RuntimeError("No PlayerCameraManager on local PC.")
    dist = max(16.0, min(8192.0, float(value)))
    setattr(pcm, "FreeCamDistance", dist)
    return f"Freecam distance set to {dist:.0f}."


def set_freecam_offset(x: float, y: float, z: float, player_index: int | None = None) -> str:
    del player_index
    if not is_debug_cam_active():
        raise RuntimeError("Freecam is not active.")
    _, gp, _cm = _resolve_local_cheat()
    pcm = _player_camera_manager(gp)
    if pcm is None:
        raise RuntimeError("No PlayerCameraManager on local PC.")
    try:
        offset = unrealsdk.make_struct("Vector", X=float(x), Y=float(y), Z=float(z))
        setattr(pcm, "FreeCamOffset", offset)
    except Exception as exc:
        raise RuntimeError(f"Could not set FreeCamOffset: {exc}") from exc
    return f"Freecam offset set to ({x:.1f}, {y:.1f}, {z:.1f})."


def copy_debug_cam_location() -> str:
    if not is_debug_cam_active():
        raise RuntimeError("Freecam is not active.")
    _, gp, cm = _resolve_local_cheat_context()
    for target, label in ((cm, "cm"), (gp, "gp")):
        for method in ("BugIt", "LogLoc"):
            hit = _try_freecam_method(label, target, method)
            if hit:
                loc = get_debug_cam_location().get("location")
                suffix = ""
                if isinstance(loc, dict):
                    suffix = f" @ ({loc.get('x', 0):.0f}, {loc.get('y', 0):.0f}, {loc.get('z', 0):.0f})"
                return f"Copied debug cam location via {hit}.{suffix}"
    loc = get_debug_cam_location().get("location")
    if isinstance(loc, dict):
        return (
            f"Location ({loc.get('x', 0):.1f}, {loc.get('y', 0):.1f}, {loc.get('z', 0):.1f}) "
            "(BugIt/LogLoc unavailable — coords from DCC only)."
        )
    raise RuntimeError("Could not read debug cam location.")


def _actor_location(actor: Any | None) -> Any | None:
    if actor is None:
        return None
    for name in ("K2_GetActorLocation", "GetActorLocation"):
        try:
            fn = getattr(actor, name, None)
            if callable(fn):
                return fn()
        except Exception:
            pass
    try:
        root = getattr(actor, "RootComponent", None)
        if root is not None:
            return getattr(root, "RelativeLocation", None)
    except Exception:
        pass
    return None


def _original_player_controller_for_debugcam() -> Any | None:
    dcc = _cached_dcc()
    if dcc is not None:
        for attr in ("OriginalControllerRef", "OriginalController", "PendingSwapConnection"):
            try:
                pc = getattr(dcc, attr, None)
                if pc is not None and "PlayerController" in str(getattr(pc, "Class", "")):
                    return _unwrap_gameplay_pc(pc)
            except Exception:
                pass
    try:
        pcs = [x for x in unrealsdk.find_all("OakPlayerController") if "Default__" not in getattr(x, "Name", "")]
        if pcs:
            return _unwrap_gameplay_pc(pcs[0])
    except Exception:
        pass
    return _gameplay_pc()


def _player_pawn_from_original_pc() -> tuple[Any | None, Any | None]:
    pc = _original_player_controller_for_debugcam()
    if pc is None:
        return None, None
    for attr in ("OakCharacter", "Character", "Pawn", "AcknowledgedPawn"):
        try:
            pawn = getattr(pc, attr, None)
            if pawn is not None:
                return pc, pawn
        except Exception:
            pass
    for fn_name in ("GetPawn", "K2_GetPawn"):
        try:
            fn = getattr(pc, fn_name, None)
            if callable(fn):
                pawn = fn()
                if pawn is not None:
                    return pc, pawn
        except Exception:
            pass
    try:
        chars = [x for x in unrealsdk.find_all("OakCharacter") if "Default__" not in getattr(x, "Name", "")]
        for ch in chars:
            try:
                if getattr(ch, "Controller", None) == pc:
                    return pc, ch
            except Exception:
                pass
        if chars:
            return pc, chars[0]
    except Exception:
        pass
    return pc, None


def _pawn_for_pc(pc: Any | None) -> Any | None:
    if pc is None:
        return None
    for attr in ("OakCharacter", "Character", "Pawn", "AcknowledgedPawn"):
        try:
            pawn = getattr(pc, attr, None)
            if pawn is not None:
                return pawn
        except Exception:
            pass
    for fn_name in ("GetPawn", "K2_GetPawn"):
        try:
            fn = getattr(pc, fn_name, None)
            if callable(fn):
                pawn = fn()
                if pawn is not None:
                    return pawn
        except Exception:
            pass
    try:
        chars = [x for x in unrealsdk.find_all("OakCharacter") if "Default__" not in getattr(x, "Name", "")]
        for ch in chars:
            try:
                if getattr(ch, "Controller", None) == pc:
                    return ch
            except Exception:
                pass
    except Exception:
        pass
    return None


def set_weapons_restricted(restricted: bool, player_index: int | None = None) -> str:
    """Set ``OakCharacter.bWeaponsRestricted`` on the selected player's pawn."""
    pc, err = _pc_for_party_index(player_index)
    if pc is None:
        raise RuntimeError(err or "No PlayerController found.")
    return set_weapons_restricted_on_pc(restricted, pc)


def set_weapons_restricted_on_pc(restricted: bool, pc: Any) -> str:
    """Set ``OakCharacter.bWeaponsRestricted`` on a specific PlayerController's pawn."""
    if pc is None:
        raise RuntimeError("No PlayerController.")
    pawn = _pawn_for_pc(pc)
    if pawn is None:
        raise RuntimeError("No OakCharacter/pawn on selected PlayerController.")
    if not hasattr(pawn, "bWeaponsRestricted"):
        raise RuntimeError("Pawn does not expose bWeaponsRestricted.")
    setattr(pawn, "bWeaponsRestricted", bool(restricted))
    rep = getattr(pawn, "OnRep_WeaponsRestricted", None)
    if callable(rep):
        try:
            rep()
        except Exception:
            pass
    state = "ON (weapons blocked)" if restricted else "OFF (weapons allowed)"
    _log(f"Weapons restricted {state} on {getattr(pawn, 'Name', '?')}.")
    return f"Weapons restricted {state}"


def _personal_vehicle_state_roots(pc: Any) -> list[Any]:
    roots: list[Any] = []
    seen: set[int] = set()

    def add(obj: Any) -> None:
        if obj is None:
            return
        try:
            oid = id(obj)
        except Exception:
            oid = 0
        if oid and oid in seen:
            return
        if oid:
            seen.add(oid)
        roots.append(obj)

    add(pc)
    for attr in ("PlayerState", "OakPlayerState"):
        try:
            add(getattr(pc, attr, None))
        except Exception:
            continue
    for root in list(roots):
        try:
            add(getattr(root, "PersonalVehicleState", None))
        except Exception:
            pass
    return roots


def _write_gbx_lock_blocked(container: Any, field: str, locked: bool) -> bool:
    if container is None:
        return False
    try:
        lock = getattr(container, field, None)
    except Exception:
        return False
    if lock is None or not hasattr(lock, "bLocked"):
        return False
    try:
        setattr(lock, "bLocked", bool(locked))
        return True
    except Exception:
        return False


def set_vehicle_actions_locked(locked: bool, player_index: int | None = None) -> str:
    pc, err = _pc_for_party_index(player_index)
    if pc is None:
        raise RuntimeError(err or "No PlayerController found.")
    return set_vehicle_actions_locked_on_pc(locked, pc)


def set_vehicle_actions_locked_on_pc(locked: bool, pc: Any) -> str:
    """Set ``PersonalVehicleState.VehicleActionsLock.bLocked`` on a PlayerController."""
    if pc is None:
        raise RuntimeError("No PlayerController.")
    ok = False
    for root in _personal_vehicle_state_roots(pc):
        pvs: Any = root
        try:
            if not hasattr(pvs, "VehicleActionsLock"):
                pvs = getattr(root, "PersonalVehicleState", None)
        except Exception:
            pvs = None
        if pvs is not None and _write_gbx_lock_blocked(pvs, "VehicleActionsLock", bool(locked)):
            ok = True
    if not ok:
        raise RuntimeError("VehicleActionsLock.bLocked not found on target PlayerController.")
    state = "locked (no summon/use)" if locked else "unlocked"
    _log(f"Vehicle actions {state} on {getattr(pc, 'Name', '?')}.")
    return f"Vehicle lock {state}"


def set_weapons_restricted_sticky(restricted: bool, player_index: int | None = None) -> str:
    """Set weapons restricted and keep re-applying until cleared."""
    msg = set_weapons_restricted(restricted, player_index)
    pc, _ = _pc_for_party_index(player_index)
    key = _devperk_player_key_from_pc(pc, player_index)
    _weapons_restricted_sticky[key] = bool(restricted)
    return msg + " (sticky ON)"


def clear_weapons_restricted_sticky(player_index: int | None = None) -> str:
    pc, err = _pc_for_party_index(player_index)
    if pc is None:
        raise RuntimeError(err or "No PlayerController found.")
    key = _devperk_player_key_from_pc(pc, player_index)
    _weapons_restricted_sticky.pop(key, None)
    return "Weapons restricted sticky cleared."


def _write_gbx_pair(container: Any, field: str, value: float) -> bool:
    if container is None:
        return False
    try:
        st = getattr(container, field, None)
    except Exception:
        return False
    if st is None:
        return False
    ok = False
    for sub in ("Value", "BaseValue"):
        if hasattr(st, sub):
            try:
                current = getattr(st, sub)
                new_value = int(round(value)) if isinstance(current, int) else float(value)
                setattr(st, sub, new_value)
                ok = True
            except Exception:
                continue
    return ok


def set_ammo_regen_rate(rate: float, player_index: int | None = None) -> str:
    """Set ``OakCharacter.ammoregenrate`` on the selected pawn."""
    pc, err = _pc_for_party_index(player_index)
    if pc is None:
        raise RuntimeError(err or "No PlayerController found.")
    pawn = _pawn_for_pc(pc)
    if pawn is None:
        raise RuntimeError("No OakCharacter/pawn on selected PlayerController.")
    if not hasattr(pawn, "ammoregenrate"):
        raise RuntimeError("Pawn does not expose ammoregenrate.")
    val = max(0.0, float(rate))
    if not _write_gbx_pair(pawn, "ammoregenrate", val):
        raise RuntimeError("Could not write ammoregenrate Value/BaseValue.")
    _log(f"Ammo regen rate set to {val} on {getattr(pawn, 'Name', '?')}.")
    return f"Ammo regen rate = {val}"


def set_ammo_regen_sticky(rate: float, player_index: int | None = None) -> str:
    msg = set_ammo_regen_rate(rate, player_index)
    pc, _ = _pc_for_party_index(player_index)
    key = _devperk_player_key_from_pc(pc, player_index)
    val = max(0.0, float(rate))
    if val <= 0.0:
        _ammo_regen_sticky.pop(key, None)
        return msg + " (sticky OFF)"
    _ammo_regen_sticky[key] = val
    return msg + " (sticky ON)"


def clear_ammo_regen_sticky(player_index: int | None = None) -> str:
    pc, err = _pc_for_party_index(player_index)
    if pc is None:
        raise RuntimeError(err or "No PlayerController found.")
    key = _devperk_player_key_from_pc(pc, player_index)
    _ammo_regen_sticky.pop(key, None)
    return "Ammo regen sticky cleared."


def sticky_combat_tick() -> None:
    """Re-apply weapons restricted / ammo regen overrides (~0.35s)."""
    global _last_sticky_apply
    if not _weapons_restricted_sticky and not _ammo_regen_sticky:
        return
    now = time.monotonic()
    if now - _last_sticky_apply < _STICKY_INTERVAL:
        return
    _last_sticky_apply = now
    try:
        live_pcs = [
            candidate
            for candidate in unrealsdk.find_all("OakPlayerController", exact=False)
            if "Default__" not in str(getattr(candidate, "Name", ""))
        ]
    except Exception:
        live_pcs = []
    pcs_by_key = {_devperk_player_key_from_pc(pc): pc for pc in live_pcs}
    for player_key, restricted in list(_weapons_restricted_sticky.items()):
        try:
            pc = pcs_by_key.get(player_key)
            if pc is None:
                continue
            pawn = _pawn_for_pc(pc)
            if pawn is not None and hasattr(pawn, "bWeaponsRestricted"):
                setattr(pawn, "bWeaponsRestricted", bool(restricted))
        except Exception:
            continue
    for player_key, rate in list(_ammo_regen_sticky.items()):
        try:
            pc = pcs_by_key.get(player_key)
            if pc is None:
                continue
            pawn = _pawn_for_pc(pc)
            if pawn is not None:
                _write_gbx_pair(pawn, "ammoregenrate", float(rate))
        except Exception:
            continue


def toggle_weapons_restricted(player_index: int | None = None) -> str:
    pc, err = _pc_for_party_index(player_index)
    if pc is None:
        raise RuntimeError(err or "No PlayerController found.")
    pawn = _pawn_for_pc(pc)
    if pawn is None:
        raise RuntimeError("No OakCharacter/pawn on selected PlayerController.")
    try:
        current = bool(getattr(pawn, "bWeaponsRestricted", False))
    except Exception:
        current = False
    return set_weapons_restricted(not current, player_index)


def teleport_pawn_to_debug_cam(player_index: int | None = None) -> str:
    # Moving a selected pawn to the host/local debug camera requires host-side
    # authority and remote pawn resolution. Keep this one gated off for joined
    # clients; other Cheats / Debug Cam actions remain client-local.
    if not _is_listen_host_safe():
        raise RuntimeError("Teleport Pawn to Debug Cam is host-only.")
    target_pc, err = _pc_for_party_index(player_index)
    if target_pc is None:
        raise RuntimeError(err or "No selected PlayerController found.")

    # Debug cam is local-only. Use the host/local debug cam as the marker/location source.
    # The pawn being moved is still the selected player's pawn.
    dcc = _debug_cam_for_pc(_gameplay_pc())
    if dcc is None:
        raise RuntimeError("No active freecam — enable freecam first.")

    pc = target_pc
    pawn = _pawn_for_pc(pc)
    if pawn is None:
        raise RuntimeError("Could not find pawn/character on selected PlayerController.")

    # Use the freecam spectator pawn location when present; fall back to the controller transform.
    sp = getattr(dcc, "SpectatorPawn", None)
    loc = _actor_location(sp) if sp is not None else None
    if loc is None:
        loc = _actor_location(dcc)
    if loc is None:
        raise RuntimeError("Could not read debug camera/freecam location.")

    try:
        rot = getattr(dcc, "ControlRotation", None)
    except Exception:
        rot = None
    if rot is None:
        try:
            rot = pawn.K2_GetActorRotation()
        except Exception:
            rot = None

    collision_was_enabled = None
    try:
        collision_was_enabled = bool(getattr(pawn, "bActorEnableCollision"))
    except Exception:
        pass

    try:
        try:
            pawn.SetActorEnableCollision(False)
        except Exception:
            try:
                pawn.bActorEnableCollision = False
            except Exception:
                pass

        ok = False
        try:
            ok = bool(pawn.K2_TeleportTo(loc, rot))
        except Exception:
            try:
                ok = bool(pawn.K2_SetActorLocation(loc, False, None, False))
                if rot is not None:
                    try:
                        pawn.K2_SetActorRotation(rot, False)
                    except Exception:
                        pass
            except Exception as exc:
                raise RuntimeError(f"Teleport call failed: {exc!r}")
        return f"Teleported pawn to debug cam location; ok={ok}."
    finally:
        try:
            if collision_was_enabled is not None:
                pawn.SetActorEnableCollision(collision_was_enabled)
            else:
                pawn.SetActorEnableCollision(True)
        except Exception:
            try:
                if collision_was_enabled is not None:
                    pawn.bActorEnableCollision = collision_was_enabled
            except Exception:
                pass


def _actor_label(obj: Any | None) -> str:
    if obj is None:
        return "(none)"
    try:
        name = str(getattr(obj, "Name", "") or "")
    except Exception:
        name = ""
    try:
        cls = str(getattr(getattr(obj, "Class", None), "Name", "") or "")
    except Exception:
        cls = ""
    if name and cls:
        return f"{cls}:{name}"
    return name or cls or repr(obj)


def _selected_debug_cam_actor() -> Any | None:
    """Actor selected by native freecam reticle (DebugCameraController.SelectedActor)."""
    dcc = _debug_cam_for_pc(_gameplay_pc()) or _cached_dcc()
    if dcc is None:
        return None
    for attr in ("SelectedActor", "GetSelectedActor"):
        try:
            val = getattr(dcc, attr, None)
            if callable(val):
                val = val()
            if val is not None:
                return val
        except Exception:
            continue
    return None


def _invoke_cheat_manager(method: str, *args: Any) -> tuple[bool, str]:
    """Call CheatManager.<method>, then console fallbacks (DestroyTarget pattern from ULM)."""
    _raw, gp, cm = _resolve_local_cheat_context()
    if cm is not None:
        fn = getattr(cm, method, None)
        if callable(fn):
            try:
                if args:
                    fn(*args)
                else:
                    fn()
                return True, f"CheatManager.{method}"
            except TypeError:
                try:
                    fn()
                    return True, f"CheatManager.{method}()"
                except Exception as exc:
                    return False, f"CheatManager.{method}: {exc}"
            except Exception as exc:
                return False, f"CheatManager.{method}: {exc}"
    pc = gp or _raw
    if pc is None:
        return False, f"{method}: no PlayerController"
    tail = ""
    if args:
        tail = " " + " ".join(str(a).strip() for a in args if str(a).strip())
    for line in (method + tail, method.lower() + tail, f"cheat {method}{tail}"):
        for attr in ("ConsoleCommand", "ClientConsoleCommand"):
            fn = getattr(pc, attr, None)
            if not callable(fn):
                continue
            try:
                fn(line)
                return True, f"{attr}({line!r})"
            except Exception:
                continue
    return False, f"{method}: no working path"


def inspect_looked_at_actor() -> str:
    """Describe the freecam-selected actor (reticle pick) without destroying it."""
    if not is_debug_cam_active():
        raise RuntimeError("Enable freecam first, then look at an object.")
    selected = _selected_debug_cam_actor()
    if selected is None:
        return "Freecam has no SelectedActor yet — click/look at a world object first."
    return f"Looking at {_actor_label(selected)}"


def destroy_looked_at_actor() -> str:
    """Destroy the actor under freecam selection via CheatManager.DestroyTarget.

    Prefer freecam SelectedActor so we refuse player pawns / OakCharacter when
    identifiable. Falls back to DestroyTarget if selection is empty (native
    path still uses look-at). Does not expose DestroyAll.
    """
    if not is_debug_cam_active():
        raise RuntimeError("Enable freecam first, then look at an object to delete.")

    selected = _selected_debug_cam_actor()
    label = _actor_label(selected) if selected is not None else "(reticle / native target)"

    if selected is not None:
        try:
            cls = str(getattr(getattr(selected, "Class", None), "Name", "") or "")
        except Exception:
            cls = ""
        name = ""
        try:
            name = str(getattr(selected, "Name", "") or "")
        except Exception:
            pass
        deny_bits = (
            "OakPlayerController",
            "PlayerController",
            "DebugCamera",
            "OakCharacter",
            "BPChar_Player",
            "PlayerPawn",
        )
        hay = f"{cls} {name}".lower()
        if any(bit.lower() in hay for bit in deny_bits) and "enemy" not in hay:
            # Still allow enemy OakCharacters (AI); block player shells.
            if "player" in hay or "debugcamera" in hay or "controller" in hay:
                raise RuntimeError(f"Refusing to destroy player/camera object: {label}")

    ok, via = _invoke_cheat_manager("DestroyTarget")
    if not ok:
        raise RuntimeError(f"DestroyTarget failed ({via})")
    return f"Destroyed looked-at target {label} via {via}."


def damage_looked_at_actor(amount: float = 999999.0) -> str:
    """Apply DamageTarget to freecam selection (safer probe than DestroyAll)."""
    if not is_debug_cam_active():
        raise RuntimeError("Enable freecam first.")
    selected = _selected_debug_cam_actor()
    label = _actor_label(selected) if selected is not None else "(reticle)"
    amt = max(1.0, float(amount))
    ok, via = _invoke_cheat_manager("DamageTarget", amt)
    if not ok:
        # Some builds take no args.
        ok, via = _invoke_cheat_manager("DamageTarget")
    if not ok:
        raise RuntimeError(f"DamageTarget failed ({via})")
    return f"Damaged looked-at target {label} ({amt:g}) via {via}."

