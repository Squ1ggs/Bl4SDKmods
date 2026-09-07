"""Low-overhead Squ1ggs runtime flight log for crash triage.

Design goals:
- Never hitch the game: hot paths only append a short string to an in-memory ring.
- Disk I/O only on enable/disable, bridge actions, exceptions, explicit flush, or a
  slow dirty flush (default ≥ 8s). Hard AVs still lose the last unflushed lines —
  that is expected; the trail up to the last action usually shows what was running.
- File lives next to spawn logs: ``Squ1ggsBoostingTools/logs/sqbt_runtime.log``.
"""

from __future__ import annotations

import atexit
import threading
import time
import traceback
from collections import deque
from pathlib import Path
from typing import Any

_PREFIX = "[Squ1ggs Boosting Tools | Runtime]"
_LOG_DIR = Path(__file__).resolve().parent / "logs"
_LOG_PATH = _LOG_DIR / "sqbt_runtime.log"
_MAX_LINES = 400
_MAX_FILE_BYTES = 512_000
_FLUSH_MIN_INTERVAL = 8.0

_lock = threading.Lock()
_ring: deque[str] = deque(maxlen=_MAX_LINES)
_pending: list[str] = []
_dirty = False
_last_flush = 0.0
_session_id = ""
_enabled = False


def log_path() -> str:
    return str(_LOG_PATH)


def log_dir() -> str:
    return str(_LOG_DIR)


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _line(level: str, message: str) -> str:
    text = str(message or "").replace("\r", " ").replace("\n", " | ").strip()
    if len(text) > 480:
        text = text[:477] + "..."
    return f"{_stamp()} [{level}] {text}"


def note(message: str, *, level: str = "INFO") -> None:
    """Append to the ring only. Safe on any thread / tick."""
    global _dirty
    if not message:
        return
    with _lock:
        line = _line(level, message)
        _ring.append(line)
        _pending.append(line)
        _dirty = True


def warn(message: str) -> None:
    note(message, level="WARN")


def error(message: str) -> None:
    note(message, level="ERROR")


def exception(message: str, exc: BaseException | None = None) -> None:
    detail = f"{message}: {exc!r}" if exc is not None else message
    note(detail, level="ERROR")
    if exc is not None:
        try:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            for raw in tb.strip().splitlines()[-8:]:
                note(raw.strip(), level="TB")
        except Exception:
            pass
    flush(force=True)


def _rotate_if_needed(path: Path) -> None:
    try:
        if path.is_file() and path.stat().st_size >= _MAX_FILE_BYTES:
            bak = path.with_suffix(".log.prev")
            try:
                if bak.exists():
                    bak.unlink()
            except Exception:
                pass
            path.replace(bak)
    except Exception:
        pass


def flush(*, force: bool = False) -> bool:
    """Write only new lines since the last flush. Returns True if a write happened."""
    global _dirty, _last_flush
    now = time.monotonic()
    with _lock:
        if not _dirty and not force:
            return False
        if not force and (now - _last_flush) < _FLUSH_MIN_INTERVAL:
            return False
        if not _pending and not force:
            _dirty = False
            return False
        # Never re-append the whole ring — that ballooned the dump and hitchd I/O
        # on every status poll / action begin.
        chunk = ("\n".join(_pending) + "\n") if _pending else ""
        _pending.clear()
        _dirty = False
        _last_flush = now
    if not chunk:
        return False
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(_LOG_PATH)
        with _LOG_PATH.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(chunk)
            fh.flush()
        return True
    except Exception:
        with _lock:
            # Best-effort: lost pending lines stay in the ring for tail().
            _dirty = True
        return False


def maybe_flush_slow() -> None:
    """Call from a rare tick path; no-op unless dirty and interval elapsed."""
    flush(force=False)


def mark_action(action: str, *, ok: bool | None = None, detail: str = "") -> None:
    """Bridge / user action breadcrumb. Flushes so a mid-action crash leaves a trail."""
    name = str(action or "?").strip() or "?"
    if ok is None:
        note(f"action begin {name}" + (f" — {detail}" if detail else ""))
    elif ok:
        note(f"action ok {name}" + (f" — {detail}" if detail else ""))
    else:
        note(f"action FAIL {name}" + (f" — {detail}" if detail else ""), level="WARN")
    flush(force=True)


def session_start(*, mod_version: str = "", bridge: str = "") -> None:
    global _session_id, _enabled
    _session_id = f"{int(time.time())}-{mod_version or 'unknown'}"
    _enabled = True
    note("=" * 56)
    note(f"session start id={_session_id} mod={mod_version or '?'} {bridge}".strip())
    try:
        import platform
        import sys

        note(
            f"python={sys.version.split()[0]} platform={platform.platform()} "
            f"pid={__import__('os').getpid()}"
        )
    except Exception:
        pass
    flush(force=True)


def session_end(*, reason: str = "disable") -> None:
    global _enabled
    note(f"session end reason={reason} id={_session_id or '?'}")
    flush(force=True)
    _enabled = False


def tail(limit: int = 40) -> list[str]:
    n = max(1, min(int(limit or 40), _MAX_LINES))
    with _lock:
        items = list(_ring)[-n:]
    return items


def status_blob() -> dict[str, Any]:
    with _lock:
        lines = len(_ring)
        dirty = _dirty
    exists = False
    size = 0
    try:
        if _LOG_PATH.is_file():
            exists = True
            size = int(_LOG_PATH.stat().st_size)
    except Exception:
        pass
    return {
        "path": log_path(),
        "dir": log_dir(),
        "ring_lines": lines,
        "dirty": dirty,
        "file_exists": exists,
        "file_bytes": size,
        "session_id": _session_id,
        "enabled": _enabled,
    }


def _atexit_flush() -> None:
    try:
        note("process exit (atexit flush)")
        flush(force=True)
    except Exception:
        pass


atexit.register(_atexit_flush)
