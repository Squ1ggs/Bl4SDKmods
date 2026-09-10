"""Run UObject / RPC work off the ImGui draw path (bundled for Squ1ggs Boosting Tools)."""

from __future__ import annotations

import logging
from collections import deque
from typing import Callable

_log = logging.getLogger("Squ1ggsBoostingTools.spawn_deferred")

_pending: deque[tuple[str, Callable[[], tuple[bool, str]]]] = deque()
last_status: str = "Ready."
last_ok: bool = True
_drain_owner: str | None = None
_flushing = False


def claim_drain_owner(owner: str) -> None:
    global _drain_owner
    _drain_owner = str(owner or "") or None


def release_drain_owner(owner: str) -> None:
    global _drain_owner
    if _drain_owner == str(owner or ""):
        _drain_owner = None


def queue_action(label: str, fn: Callable[[], tuple[bool, str]]) -> str:
    global last_status
    _pending.append((str(label or "action"), fn))
    last_status = f"Queued: {label} — close menu or wait one frame."
    return last_status


def has_pending() -> bool:
    return bool(_pending)


def pending_label_count(prefix: str) -> int:
    """Count queued work for one feature without exposing the queue itself."""
    needle = str(prefix or "").strip().lower()
    if not needle:
        return 0
    return sum(1 for label, _fn in _pending if str(label).lower().startswith(needle))


def clear_pending(*, reason: str = "cleared") -> int:
    global last_status, last_ok
    n = len(_pending)
    _pending.clear()
    if n:
        last_ok = False
        last_status = f"Deferred queue {reason} ({n} dropped)."
    return n


def flush_tick(*, max_items: int = 1, owner: str | None = None) -> None:
    global last_status, last_ok, _flushing
    if _drain_owner is not None and owner is not None and owner != _drain_owner:
        return
    if _flushing:
        return
    try:
        from .session_guards import session_safe

        if not session_safe():
            if _pending:
                clear_pending(reason="left session")
            return
    except Exception:
        pass
    try:
        import blimgui as _blg  # noqa: PLC0415

        if bool(getattr(_blg, "_IN_IMGUI_FRAME", False)):
            return
    except Exception:
        pass
    _flushing = True
    try:
        for _ in range(max(1, int(max_items))):
            if not _pending:
                return
            label, fn = _pending.popleft()
            try:
                _ok, msg = fn()
                last_ok = bool(_ok)
                last_status = str(msg or ("OK" if _ok else "Failed"))
            except Exception as exc:  # noqa: BLE001
                last_ok = False
                last_status = f"{label} failed: {type(exc).__name__}: {exc}"
                _log.exception("deferred action %s failed", label)
    finally:
        _flushing = False


def gameplay_ready() -> bool:
    try:
        from mods_base import ENGINE, get_pc  # noqa: PLC0415

        if ENGINE is None:
            return False
        viewport = getattr(ENGINE, "GameViewport", None)
        if viewport is None or getattr(viewport, "World", None) is None:
            return False
        pc = get_pc()
        if pc is None:
            return False
        pawn = getattr(pc, "Pawn", None)
        if pawn is None:
            get_pawn = getattr(pc, "GetPawn", None)
            pawn = get_pawn() if callable(get_pawn) else None
        return pawn is not None
    except Exception:
        return False
