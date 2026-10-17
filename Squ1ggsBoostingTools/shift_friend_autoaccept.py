"""SHiFT friend auto-accept.

Uses ShiftUIFunctionLibrary.Open(0) so the friends overlay can run, holds it
open briefly while Azalea’s Cohtml accepter (via SQBT /sqbt_shift) runs, then
Close only if still visible. Not a continuous Cohtml pulse.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from mods_base import get_pc
from unrealsdk import find_all, find_class, logging

_LOG = "[SQBT SHiFT autoaccept]"
_STATE_PATH = Path(__file__).resolve().parent / "data" / "shift_autoaccept_state.json"

_ZERO_ARG_ACCEPT_METHODS: tuple[str, ...] = (
    "AcceptAllPendingFriendRequests",
    "AcceptAllFriendRequests",
    "AcceptAllIncomingFriendRequests",
    "AcceptAllPendingInvitations",
    "AcceptAllFriendInvites",
    "AcceptAllPendingFriends",
    "ApproveAllPendingFriendRequests",
    "RespondToAllFriendRequests",
)

_REQUEST_ACCEPT_METHODS: tuple[str, ...] = (
    "Accept",
    "Approve",
    "Confirm",
    "AcceptInvitation",
    "AcceptFriendRequest",
    "Join",
    "RespondToInvitation",
)

_OWNER_CLASS_HINTS: tuple[str, ...] = (
    "ShiftSessionManager",
    "OakShiftSessionManager",
    "SocialManager",
    "OakSocialManager",
    "OakShiftSubsystem",
    "OakShiftUISubsystem",
)

_PENDING_FIELD_RE = re.compile(
    r"(pending|incoming|outstanding|waiting).*(friend|invite|request|invitation)"
    r"|(friend|invite|request|invitation).*(pending|incoming|outstanding|waiting)",
    re.I,
)

# Cheap AcceptAll between UI cycles.
_POLL_INTERVAL_SEC = 10.0
# Open overlay periodically while armed (default; Auto Lobby can override).
_DEFAULT_CYCLE_INTERVAL_SEC = 25.0
_MIN_CYCLE_INTERVAL_SEC = 8.0
_MAX_CYCLE_INTERVAL_SEC = 180.0
_CYCLE_INTERVAL_SEC = _DEFAULT_CYCLE_INTERVAL_SEC
# Hold open long enough for Azalea Cohtml to poll /sqbt_shift (~2s cadence).
_CYCLE_OPEN_SEC = 6.0
_ONESHOT_OPEN_SEC = 12.0
# Don't slam Open on the enable click.
_ENABLE_WARMUP_SEC = 1.5
_OWNERS_CACHE_TTL_SEC = 12.0
# Only ignore true duplicate spam (same want); real ON↔OFF always applies.
_TOGGLE_DEBOUNCE_SEC = 0.35
# Re-assert GameOnly while overlay is held (SHiFT re-captures mouse otherwise).
_INPUT_RESTORE_INTERVAL_SEC = 0.35
_last_input_restore_at: float = 0.0

_enabled: bool = False
_last_poll: float = 0.0
_last_cycle: float = 0.0
_cycle_open_until: float = 0.0
_enable_ready_at: float = 0.0
_oneshot_until: float = 0.0
_ui_open: bool = False
_did_deep_this_window: bool = False
_last_hits: int = 0
_last_error: str = ""
_last_note: str = ""
_last_owner_sigs: list[str] = []
_owners_cache: list[tuple[str, Any]] = []
_owners_cache_ts: float = 0.0
_bootstrapped: bool = False
_last_set_enabled_at: float = 0.0
_last_set_enabled_val: bool | None = None
# True when Auto Lobby (or similar) forced a non-default cycle gap.
_cycle_interval_overridden: bool = False


def _log(msg: str) -> None:
    logging.info(f"{_LOG} {msg}")
    try:
        from . import runtime_log

        runtime_log.note(f"shift_aa: {msg}")
    except Exception:
        pass


def _runtime(msg: str) -> None:
    try:
        from . import runtime_log

        runtime_log.note(f"shift_aa: {msg}")
    except Exception:
        pass


def _persist(enabled: bool) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(
            json.dumps({"enabled": bool(enabled)}, indent=0) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def _load_persisted() -> bool | None:
    try:
        if not _STATE_PATH.is_file():
            return None
        doc = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and "enabled" in doc:
            return bool(doc.get("enabled"))
    except Exception:
        return None
    return None


def _ensure_bootstrapped() -> None:
    global _enabled, _bootstrapped, _last_poll, _last_cycle, _enable_ready_at
    if _bootstrapped:
        return
    _bootstrapped = True
    persisted = _load_persisted()
    if persisted is not None:
        _enabled = bool(persisted)
        now = time.time()
        _last_poll = now if _enabled else 0.0
        # A persisted ON state used to leave _last_cycle at zero, so the first
        # runtime tick opened SHiFT immediately after warmup and briefly captured
        # movement. Treat bootstrap as the start of the first cycle interval.
        _last_cycle = now
        _enable_ready_at = now + _ENABLE_WARMUP_SEC if _enabled else 0.0


def _is_cdo(obj: Any) -> bool:
    if obj is None:
        return True
    cls = getattr(obj, "Class", None)
    cdo = getattr(cls, "ClassDefaultObject", None) if cls is not None else None
    if cdo is not None and obj is cdo:
        return True
    try:
        nm = str(getattr(obj, "Name", "") or "")
    except Exception:
        nm = ""
    return nm.startswith("Default__")


def _obj_sig(obj: Any) -> str:
    try:
        path = str(getattr(obj, "_path_name", lambda: "")() or "")
    except Exception:
        path = ""
    if path:
        return path[-80:]
    try:
        return str(getattr(obj, "Name", "") or type(obj).__name__)
    except Exception:
        return type(obj).__name__


def _add_owner(out: list[tuple[str, Any]], seen: set[int], label: str, obj: Any) -> None:
    if obj is None or _is_cdo(obj):
        return
    oid = id(obj)
    if oid in seen:
        return
    seen.add(oid)
    out.append((label, obj))


def _ui_library_cdo() -> Any | None:
    try:
        cls = find_class("ShiftUIFunctionLibrary")
    except Exception:
        return None
    if cls is None:
        return None
    return getattr(cls, "ClassDefaultObject", None)


def _fmt_ue_result(out: Any) -> str:
    """Unreal void returns often stringify as Ellipsis — not an error."""
    if out is None:
        return "ok"
    text = str(out).strip()
    if text in ("Ellipsis", "<Ellipsis>", "...", "None"):
        return "ok"
    return repr(out)


def _ui_library_call(name: str) -> tuple[bool, str]:
    """Call ShiftUIFunctionLibrary CDO method. Returns (ok, detail).

    ``Open(0)`` — local user index. ``Close`` / visibility are zero-arg.
    """
    cdo = _ui_library_cdo()
    if cdo is None:
        return False, "ShiftUIFunctionLibrary missing"
    fn = getattr(cdo, name, None)
    if not callable(fn):
        return False, f"ShiftUIFunctionLibrary.{name} missing"

    low = str(name or "").strip().lower()
    attempts: list[tuple[Any, ...]] = []
    if low == "open":
        attempts.extend([(0,), (1,), ()])
    elif low == "close":
        attempts.extend([(), (0,)])
    else:
        attempts.append(())

    last = f"ShiftUIFunctionLibrary.{name}: no matching args"
    for args in attempts:
        try:
            out = fn(*args)
            return True, f"ShiftUIFunctionLibrary.{name}{args!r} -> {_fmt_ue_result(out)}"
        except Exception as exc:
            last = f"ShiftUIFunctionLibrary.{name}{args!r}: {exc}"
            continue
    return False, last


def _ui_is_visible() -> bool:
    ok, detail = _ui_library_call("IsVisible")
    if not ok:
        return False
    low = detail.lower()
    return "-> true" in low or "-> True" in detail or detail.endswith("True")


def _list_field_names(obj: Any) -> list[str]:
    names: list[str] = []
    try:
        fields = getattr(obj, "_fields", None)
        if callable(fields):
            for field in fields():
                try:
                    names.append(str(getattr(field, "Name", "") or field))
                except Exception:
                    continue
            return names
    except Exception:
        pass
    try:
        props = getattr(obj, "_properties", None)
        if callable(props):
            for prop in props():
                try:
                    names.append(str(getattr(prop, "Name", "") or prop))
                except Exception:
                    continue
    except Exception:
        pass
    return names


def _collect_owners(*, deep: bool = False) -> list[tuple[str, Any]]:
    global _owners_cache, _owners_cache_ts
    now = time.monotonic()
    if (
        not deep
        and _owners_cache
        and (now - _owners_cache_ts) < _OWNERS_CACHE_TTL_SEC
        and _owners_cache_ts > 0.0
    ):
        return list(_owners_cache)

    out: list[tuple[str, Any]] = []
    seen: set[int] = set()
    pc = None
    try:
        pc = get_pc()
    except Exception:
        pc = None
    _add_owner(out, seen, "player_controller", pc)
    if pc is not None:
        for label, attr in (
            ("shift_session_manager", "ShiftSessionManager"),
            ("oak_shift_session_manager", "OakShiftSessionManager"),
            ("social_manager", "SocialManager"),
            ("oak_social_manager", "OakSocialManager"),
            ("local_player", "Player"),
            ("local_player", "LocalPlayer"),
        ):
            try:
                _add_owner(out, seen, label, getattr(pc, attr, None))
            except Exception:
                continue

    cdo = _ui_library_cdo()
    if cdo is not None:
        oid = id(cdo)
        if oid not in seen:
            seen.add(oid)
            out.append(("shift_ui_library", cdo))

    if deep:
        for hint in _OWNER_CLASS_HINTS:
            try:
                for obj in find_all(hint, exact=False):
                    _add_owner(out, seen, hint, obj)
            except Exception:
                continue

    if not deep:
        _owners_cache = list(out)
        _owners_cache_ts = now
    return out


def _try_accept_methods(owners: list[tuple[str, Any]]) -> int:
    global _last_error
    hits = 0
    for label, obj in owners:
        for method_name in _ZERO_ARG_ACCEPT_METHODS:
            fn = getattr(obj, method_name, None)
            if not callable(fn):
                continue
            try:
                fn()
                hits += 1
                _log(f"called {label}.{method_name}()")
            except TypeError:
                continue
            except Exception as exc:
                _last_error = f"{label}.{method_name}: {type(exc).__name__}: {exc}"[:220]
    return hits


def _try_pending_request_accepts(owners: list[tuple[str, Any]]) -> int:
    """Walk pending friend/invite lists and Accept each entry (ULM deep-scan lean)."""
    global _last_error
    hits = 0
    for label, obj in owners:
        for field in _list_field_names(obj):
            low = field.lower()
            if not (
                _PENDING_FIELD_RE.search(field)
                or any(x in low for x in ("pending", "request", "invitation", "incoming", "offer"))
            ):
                continue
            try:
                val = getattr(obj, field, None)
            except Exception:
                continue
            if val is None or isinstance(val, (str, bytes)):
                continue
            if not hasattr(val, "__iter__"):
                continue
            try:
                req_list = list(val)
            except Exception:
                continue
            for req in req_list:
                for method in _REQUEST_ACCEPT_METHODS:
                    fn = getattr(req, method, None)
                    if not callable(fn):
                        continue
                    try:
                        if method == "RespondToInvitation":
                            fn(True)
                        else:
                            fn()
                        hits += 1
                        _log(f"called {label}.{field}.{method}()")
                        break
                    except TypeError:
                        continue
                    except Exception as exc:
                        _last_error = (
                            f"{label}.{field}.{method}: {type(exc).__name__}: {exc}"
                        )[:220]
                        continue
    return hits


def _restore_gameplay_input() -> None:
    """SHiFT Open can capture mouse/move — restore GameOnly so lobby stays playable."""
    try:
        from mods_base import get_pc

        pc = get_pc()
    except Exception:
        pc = None
    if pc is None:
        return
    try:
        lib_cls = find_class("WidgetBlueprintLibrary")
        lib = getattr(lib_cls, "ClassDefaultObject", None) if lib_cls is not None else None
    except Exception:
        lib = None
    if lib is not None:
        for name, args in (
            ("ClearAllUserFocus", (pc,)),
            ("SetInputMode_GameOnly", (pc, True)),
            ("SetInputMode_GameOnly", (pc,)),
            ("SetFocusToGameViewport", ()),
        ):
            fn = getattr(lib, name, None)
            if not callable(fn):
                continue
            try:
                fn(*args)
            except TypeError:
                continue
            except Exception:
                continue
    for attr, value in (
        ("bShowMouseCursor", False),
        ("bEnableMouseOverEvents", False),
        ("bEnableClickEvents", False),
        ("bBlockInput", False),
    ):
        try:
            setattr(pc, attr, value)
        except Exception:
            pass
    for name in ("ResetIgnoreLookInput", "ResetIgnoreMoveInput", "ResetIgnoreInputFlags"):
        fn = getattr(pc, name, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass


def _open_friends_ui() -> bool:
    global _ui_open, _last_note
    if _ui_is_visible():
        _ui_open = True
        _last_note = "ShiftUI already visible"
        _restore_gameplay_input()
        return True
    ok, detail = _ui_library_call("Open")
    _last_note = detail
    if ok:
        _ui_open = True
        _restore_gameplay_input()
        _log(f"opened friends UI: {detail}")
        return True
    _log(f"open failed: {detail}")
    return False


def _close_friends_ui(*, force: bool = False) -> bool:
    """Close only when overlay looks open — avoids Back-navigating a parent menu."""
    global _ui_open, _last_note
    visible = _ui_is_visible()
    if not force and not _ui_open and not visible:
        return False
    if not visible and not force:
        _ui_open = False
        return False
    ok, detail = _ui_library_call("Close")
    _last_note = detail
    _ui_open = False
    if ok:
        _log(f"closed friends UI: {detail}")
    return ok


def _run_accept_pass(*, deep: bool) -> int:
    global _last_hits, _last_owner_sigs, _last_poll
    owners = _collect_owners(deep=deep)
    _last_owner_sigs = [f"{label}:{_obj_sig(obj)}" for label, obj in owners][:16]
    hits = _try_accept_methods(owners)
    if deep:
        hits += _try_pending_request_accepts(owners)
    _last_hits = hits
    _last_poll = time.time()
    return hits


def _begin_open_window(*, oneshot: bool = False) -> bool:
    global _cycle_open_until, _last_cycle, _oneshot_until, _did_deep_this_window
    # Ensure PAK Cohtml can see auto_accept=true on its poll ports.
    try:
        from . import shift_afk_bridge

        shift_afk_bridge.start_afk_shift_bridge()
        hold = _ONESHOT_OPEN_SEC if oneshot else _CYCLE_OPEN_SEC
        # Accept now / cycle: force auto_accept for the whole hold so Cohtml starts
        # even if sticky just flipped or warmup has not settled.
        shift_afk_bridge.force_auto_accept(hold + 1.0)
    except Exception:
        pass
    if not _open_friends_ui():
        return False
    now = time.time()
    hold = _ONESHOT_OPEN_SEC if oneshot else _CYCLE_OPEN_SEC
    until = now + hold
    _cycle_open_until = until
    _last_cycle = now
    _did_deep_this_window = False
    if oneshot:
        _oneshot_until = until
    _run_accept_pass(deep=True)
    _did_deep_this_window = True
    return True


def set_enabled(enabled: bool, *, persist: bool = True) -> None:
    global _enabled, _last_poll, _last_hits, _last_error, _owners_cache_ts
    global _cycle_open_until, _last_cycle, _last_note, _enable_ready_at, _oneshot_until
    global _last_set_enabled_at, _last_set_enabled_val, _ui_open, _last_input_restore_at
    _ensure_bootstrapped()
    want = bool(enabled)
    now = time.time()
    # Ignore only true duplicate spam (same want while already there).
    # Real ON↔OFF flips always apply so the EXE sticky can stick.
    if want == _enabled and (now - _last_set_enabled_at) < _TOGGLE_DEBOUNCE_SEC:
        return
    _last_set_enabled_at = now
    _last_set_enabled_val = want

    was = _enabled
    _enabled = want
    _last_poll = now if _enabled else 0.0
    _last_hits = 0
    _last_error = ""
    _last_note = ""
    _owners_cache_ts = 0.0
    _cycle_open_until = 0.0
    _oneshot_until = 0.0
    # Warm up — do NOT Open on the enable click (that fights the EXE toggle).
    _enable_ready_at = now + _ENABLE_WARMUP_SEC if _enabled else 0.0
    _last_cycle = now if _enabled else now
    if was and not _enabled:
        # Force Close + GameOnly — soft Close left overlay up and ate mouse/move.
        _close_friends_ui(force=True)
        _restore_gameplay_input()
        _last_input_restore_at = now
        _ui_open = False
        try:
            from . import shift_afk_bridge

            shift_afk_bridge.force_auto_accept(0.0)
        except Exception:
            pass
    elif not _enabled:
        # Idempotent OFF (already off) still frees input if SHiFT got stuck.
        _close_friends_ui(force=True)
        _restore_gameplay_input()
        _last_input_restore_at = now
    if _enabled:
        try:
            from . import shift_afk_bridge

            shift_afk_bridge.start_afk_shift_bridge()
        except Exception as exc:
            _log(f"AFK bridge start failed: {exc!r}")
    if persist:
        _persist(_enabled)
    _log(
        f"{'enabled' if _enabled else 'disabled'} "
        f"(hold Open ~{_CYCLE_OPEN_SEC:g}s every {_CYCLE_INTERVAL_SEC:g}s after "
        f"{_ENABLE_WARMUP_SEC:g}s warmup; SQBT /sqbt_shift → Azalea accepter)"
    )


def is_enabled() -> bool:
    _ensure_bootstrapped()
    return bool(_enabled)


def _clamp_cycle_interval(raw: Any) -> float:
    try:
        value = float(raw)
    except Exception:
        value = _DEFAULT_CYCLE_INTERVAL_SEC
    return max(_MIN_CYCLE_INTERVAL_SEC, min(_MAX_CYCLE_INTERVAL_SEC, value))


def get_cycle_interval_sec() -> float:
    return float(_CYCLE_INTERVAL_SEC)


def set_cycle_interval_sec(seconds: float | None, *, override: bool = True) -> float:
    """How often to Open the friends UI while armed (seconds between cycles).

    Auto Lobby passes its timer here. Pass None (or override=False with default)
    to restore the built-in ~25s gap when Auto Lobby stops.
    """
    global _CYCLE_INTERVAL_SEC, _cycle_interval_overridden
    if seconds is None or (not override and not _cycle_interval_overridden):
        _CYCLE_INTERVAL_SEC = _DEFAULT_CYCLE_INTERVAL_SEC
        _cycle_interval_overridden = False
        return float(_CYCLE_INTERVAL_SEC)
    _CYCLE_INTERVAL_SEC = _clamp_cycle_interval(seconds)
    _cycle_interval_overridden = bool(override)
    return float(_CYCLE_INTERVAL_SEC)


def clear_cycle_interval_override() -> float:
    """Restore default Open cadence (used when Auto Lobby releases AA)."""
    return set_cycle_interval_sec(None, override=False)


def status() -> dict[str, Any]:
    _ensure_bootstrapped()
    age = (time.time() - _last_poll) if _last_poll else 0.0
    return {
        "enabled": bool(_enabled),
        "interval_sec": _POLL_INTERVAL_SEC,
        "cycle_interval_sec": float(_CYCLE_INTERVAL_SEC),
        "cycle_interval_overridden": bool(_cycle_interval_overridden),
        "open_hold_sec": _CYCLE_OPEN_SEC,
        "ui_open": bool(_ui_open) or _ui_is_visible(),
        "oneshot_active": bool(_oneshot_until > time.time()),
        "last_poll_age_sec": round(age, 1),
        "last_hits": int(_last_hits),
        "last_error": str(_last_error or ""),
        "last_note": str(_last_note or ""),
        "owners": list(_last_owner_sigs[:8]),
        "note": (
            f"Open(0) hold ~{_CYCLE_OPEN_SEC:g}s every ~{_CYCLE_INTERVAL_SEC:g}s; "
            "Azalea Cohtml Accept via SQBT /sqbt_shift on 51974–77."
        ),
    }


def accept_once(*, deep: bool = True, open_ui: bool = True) -> dict[str, Any]:
    """One-shot: force /sqbt_shift auto_accept, Open SHiFT, hold for Cohtml."""
    del deep  # Cohtml Accept is the real path; SDK AcceptAll is unused here
    if not open_ui:
        return {
            "ok": False,
            "hits": 0,
            "opened": False,
            "closed": False,
            "message": "Accept now needs the SHiFT UI open.",
        }
    bridge_port = 0
    try:
        from . import shift_afk_bridge

        shift_afk_bridge.start_afk_shift_bridge()
        shift_afk_bridge.force_auto_accept(_ONESHOT_OPEN_SEC + 1.0)
        bridge_port = int(shift_afk_bridge.bound_port() or 0)
    except Exception as exc:
        _log(f"Accept now bridge arm failed: {exc!r}")
    ok = _begin_open_window(oneshot=True)
    if ok:
        msg = (
            f"Accept now: SHiFT open ~{_ONESHOT_OPEN_SEC:g}s, "
            f"auto_accept on"
            + (f" (link :{bridge_port})" if bridge_port else "")
            + ". Leave the compact overlay up — requests accept themselves."
        )
    else:
        msg = f"Accept now: could not Open SHiFT ({_last_note})."
    _log(msg)
    return {
        "ok": bool(ok),
        "hits": int(_last_hits),
        "opened": bool(ok),
        "closed": False,
        "bridge_port": bridge_port,
        "owners": list(_last_owner_sigs[:6]),
        "message": msg,
    }


def tick() -> None:
    """Mobility HUD tick — rate-limited; never find_all every frame."""
    global _last_poll, _last_hits, _last_owner_sigs, _last_cycle, _cycle_open_until
    global _oneshot_until, _did_deep_this_window, _last_input_restore_at
    _ensure_bootstrapped()
    now = time.time()

    # Finish an open window (auto or oneshot).
    if _cycle_open_until > 0.0:
        if now < _cycle_open_until:
            # Keep movement free while SHiFT stays visible for Cohtml accept.
            if now - _last_input_restore_at >= _INPUT_RESTORE_INTERVAL_SEC:
                _restore_gameplay_input()
                _last_input_restore_at = now
            if now - _last_poll >= 0.75:
                _run_accept_pass(deep=not _did_deep_this_window)
                _did_deep_this_window = True
            return
        _close_friends_ui(force=True)
        _restore_gameplay_input()
        _last_input_restore_at = now
        _cycle_open_until = 0.0
        _oneshot_until = 0.0
        _last_cycle = now
        return

    if not _enabled:
        return
    if _enable_ready_at and now < _enable_ready_at:
        return
    # Never let an automatic SHiFT UI cycle overlap map/character load. Open(0)
    # captures movement input; keep resetting the cycle clock until gameplay is
    # safely armed, then wait the normal full interval.
    try:
        from .session_guards import session_safe

        if not session_safe():
            _last_cycle = now
            return
    except Exception:
        _last_cycle = now
        return

    if now - _last_cycle >= _CYCLE_INTERVAL_SEC:
        if _begin_open_window(oneshot=False):
            return
        _last_cycle = now
        _run_accept_pass(deep=False)
        return

    if now - _last_poll >= _POLL_INTERVAL_SEC:
        _run_accept_pass(deep=False)
