"""Localhost HTTP bridge for the Squ1ggs Boosting Tools desktop app."""
from __future__ import annotations

import copy
import json
import os
from urllib.parse import parse_qs, unquote
import threading
import time
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from unrealsdk import logging

from mods_base import command

from . import backend_actions
from .bridge_catalog import run_catalog
from ._mod_version import __version__ as _PACKAGE_VERSION

_HOST = "127.0.0.1"
# Preferred ports. Hyper-V / WinNAT excluded ranges (WSA 10013) are skipped at
# bind time; if every candidate is reserved, we bind port 0 and let Windows pick.
_PORT = 50675
_PORT_CANDIDATES: tuple[int, ...] = (
    *range(50675, 50685),
    *range(55175, 55185),
    *range(49775, 49785),
)
_PREFIX = "[Squ1ggs Boosting Tools | Bridge]"
_PRODUCT_ID = "squ1ggs-boosting-tools"

_server: ThreadingHTTPServer | None = None
_thread: threading.Thread | None = None
_started = False
_lock = threading.RLock()
_queue: deque[dict[str, Any]] = deque()
_results: dict[str, dict[str, Any]] = {}
_abandoned: set[str] = set()
_last_bridge_error = ""
_tick_registered = False
_last_process_tick = 0.0
_tick_count = 0
_last_live_tick = 0.0
_last_status_refresh = 0.0
_last_exe_reclaim = 0.0
_status_cache: dict[str, Any] = {
    "ok": True,
    "message": "Squ1ggs Boosting Tools bridge online.",
    "name": "Squ1ggs Boosting Tools",
    "mod_version": str(_PACKAGE_VERSION),
    "product_id": _PRODUCT_ID,
    "product_author": "Squ1ggs",
    "bridge_protocol": "1.0",
    "connection_state": "in_menu_or_loading",
    "actions_available": False,
    "session": "No session",
    "gameplay_ready": False,
    "has_local_pc": False,
    "players": [],
}

_READ_ONLY_ACTIONS = frozenset(
    {
        "activity_log",
        "legit_forge_validate",
        "legit_forge_build",
        "legit_forge_max_passives",
        "legit_forge_append_part",
        "challenge_bulk_status",
        "uvhm_status",
        "panel_manifest",
        "catalog",
        "keybinds_status",
        "gzo_refresh_status",
        "lootlemon_refresh_status",
        "shiny_drop_status",
        "serial_delivery_status",
    }
)


def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")


def _now() -> float:
    try:
        return time.monotonic()
    except Exception:
        return time.time()


def _snapshot_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    try:
        return copy.deepcopy(payload)
    except Exception:
        try:
            return dict(payload)
        except Exception:
            return {}


def _status_payload() -> dict[str, Any]:
    # HTTP requests run on worker threads. Unreal objects must only be touched
    # by the game-thread tick, so status serves the latest tick-built snapshot.
    with _lock:
        base = _snapshot_payload(_status_cache)
        base["bridge"] = {
            "host": _HOST,
            "port": _PORT,
            "started": _started,
            "queue_depth": len(_queue),
            "last_error": _last_bridge_error,
            "tick_count": _tick_count,
            "last_tick_age": (max(0.0, _now() - _last_live_tick) if _last_live_tick else None),
        }
        base["product_id"] = _PRODUCT_ID
        base["product_author"] = "Squ1ggs"
    return base


def _refresh_status_cache() -> None:
    global _last_status_refresh, _status_cache, _last_bridge_error
    now = _now()
    if now - _last_status_refresh < 5.0:
        return
    _last_status_refresh = now
    try:
        snapshot = backend_actions.get_status()
        with _lock:
            _status_cache = _snapshot_payload(snapshot)
    except Exception as exc:
        _last_bridge_error = f"status refresh: {exc!r}"


def _process_queue(*_args: Any, **_kwargs: Any) -> None:
    global _last_bridge_error, _last_process_tick, _tick_count, _last_live_tick
    # Several controller subclasses can dispatch in the same frame. Register
    # all viable paths for compatibility, then do the work only once.
    now = _now()
    if now - _last_process_tick < 0.0025:
        return
    _last_process_tick = now
    _last_live_tick = now
    _tick_count += 1
    _refresh_status_cache()
    # Keep heavy game-thread actions spread across frames instead of allowing a
    # desktop burst to execute six UObject/RPC operations in one frame.
    for _ in range(2):
        with _lock:
            if not _queue:
                break
            item = _queue.popleft()
            rid = str(item.get("id") or "")
            was_abandoned = bool(rid) and rid in _abandoned
            if rid:
                _abandoned.discard(rid)
        action = str(item.get("action") or "")
        payload = item.get("payload") or {}
        # Skip noisy status polls — those would fill the flight log for no crash value.
        _flight = action not in (
            "status",
            "party_roster",
            "get_manifest",
            "manifest",
            "spawn_item_pool_status",
            "shiny_drop_status",
            "runtime_log",
        )
        if _flight:
            try:
                from . import runtime_log

                runtime_log.mark_action(action)
            except Exception:
                pass
        try:
            result = backend_actions.run_action(action, _snapshot_payload(payload))
        except Exception as exc:
            _last_bridge_error = repr(exc)
            result = {"ok": False, "message": repr(exc)}
            try:
                from . import runtime_log

                runtime_log.exception(f"action {action!r}", exc)
            except Exception:
                pass
        if not bool(result.get("ok", False)):
            _last_bridge_error = f"{action}: {result.get('message') or 'action failed'}"
            _log(f"Action {action!r} failed: {result.get('message') or result!r}")
            if _flight:
                try:
                    from . import runtime_log

                    runtime_log.mark_action(
                        action,
                        ok=False,
                        detail=str(result.get("message") or "failed")[:200],
                    )
                except Exception:
                    pass
        else:
            # Clear sticky bridge errors so a prior failure does not keep showing
            # while loot / other actions are succeeding.
            _last_bridge_error = ""
            if _flight:
                try:
                    from . import runtime_log

                    runtime_log.mark_action(action, ok=True)
                except Exception:
                    pass
        with _lock:
            # The polling HTTP thread already gave up and returned 202 for this id —
            # nothing will ever pop it back out, so don't let it sit in _results forever.
            if not was_abandoned:
                _results[rid or uuid.uuid4().hex] = result
    try:
        from . import runtime_log

        runtime_log.maybe_flush_slow()
    except Exception:
        pass


def _register_tick_hook() -> None:
    global _tick_registered
    if _tick_registered:
        return
    # mobility_runtime is imported before this module and its single proven-live
    # UMG tick calls _process_queue(). Do not register controller/viewport hooks
    # here: several paths may dispatch in one frame and caused measurable stutter.
    _tick_registered = True


class _SqbtBridgeHandler(BaseHTTPRequestHandler):
    server_version = "SQBTBridge/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _json(self, status: int, data: Any) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Sqbt-Client")
            self.send_header("X-Sqbt-Product", _PRODUCT_ID)
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            return

    def do_OPTIONS(self) -> None:
        self._json(200, {"ok": True})

    def do_GET(self) -> None:
        _maybe_reclaim_from_exe(self)
        path = (self.path or "").split("?", 1)[0]
        if path in ("/", "/status", "/health"):
            self._json(200, _status_payload())
            return
        if path == "/manifest":
            self._json(200, run_catalog("manifest"))
            return
        if path.startswith("/catalog/"):
            raw_path = self.path or ""
            catalog_name = path.split("/catalog/", 1)[1].strip("/")
            query_payload: dict[str, str] = {}
            if "?" in raw_path:
                for key, values in parse_qs(raw_path.split("?", 1)[1]).items():
                    if values:
                        query_payload[unquote(key)] = unquote(values[0])
            self._json(200, run_catalog(catalog_name, query_payload))
            return
        if path == "/actions":
            self._json(200, {"ok": True, "actions": sorted(backend_actions._ACTIONS)})
            return
        self._json(404, {"ok": False, "message": "Not found"})

    def do_POST(self) -> None:
        _maybe_reclaim_from_exe(self)
        path = (self.path or "").split("?", 1)[0]
        if path != "/action":
            self._json(404, {"ok": False, "message": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            data = json.loads(raw or "{}")
        except Exception as exc:
            self._json(400, {"ok": False, "message": f"Bad JSON: {exc!r}"})
            return

        action = str(data.get("action") or "").strip()
        if not action:
            self._json(400, {"ok": False, "message": "Missing action"})
            return

        payload = _snapshot_payload(data.get("payload"))
        try:
            timeout = float(data.get("timeout", 8.0) or 8.0)
        except Exception:
            timeout = 8.0
        timeout = max(1.0, min(timeout, 120.0))

        # Fast path: read-only actions can answer on the HTTP thread.
        if action in _READ_ONLY_ACTIONS:
            self._json(200, backend_actions.run_action(action, payload))
            return

        rid = uuid.uuid4().hex
        enqueued_at = _now()
        with _lock:
            item = {
                "id": rid,
                "action": action,
                "payload": payload,
                "enqueued_at": enqueued_at,
            }
            if action == "desktop_session_end":
                while _queue:
                    stale = _queue.popleft()
                    stale_id = str(stale.get("id") or "")
                    if stale_id:
                        _results[stale_id] = {
                            "ok": False,
                            "message": "Cancelled because the desktop session closed.",
                        }
                        _abandoned.discard(stale_id)
                _queue.appendleft(item)
            else:
                _queue.append(item)

        deadline = enqueued_at + timeout
        while _now() < deadline:
            with _lock:
                result = _results.pop(rid, None)
            if result is not None:
                self._json(200, result)
                return
            time.sleep(0.05)

        with _lock:
            still_queued = any(str(item.get("id") or "") == rid for item in _queue)
            late = _results.pop(rid, None)
        if late is not None:
            self._json(200, late)
            return
        if still_queued:
            _abandoned.add(rid)
        self._json(
            202,
            {
                "ok": True,
                "queued": True,
                "message": (
                    "Action queued — game must be loaded and unpaused for the SDK tick to run it. "
                    "Retry or poll /status."
                ),
            },
        )


def _port_file() -> Any:
    from pathlib import Path

    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    folder = Path(base) / "Squ1ggsBoostingTools"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return folder / "bridge_port.json"


def _write_port_file(port: int) -> None:
    try:
        _port_file().write_text(
            json.dumps({"host": _HOST, "port": int(port), "product_id": _PRODUCT_ID}),
            encoding="utf-8",
        )
    except Exception:
        pass


def _maybe_reclaim_from_exe(handler: BaseHTTPRequestHandler) -> None:
    global _last_exe_reclaim
    try:
        client = str(handler.headers.get("X-Sqbt-Client") or "").strip().lower()
    except Exception:
        return
    if client != "squ1ggs-boosting-tools-exe":
        return
    now = _now()
    # Was 8s — too aggressive with force hook reclaim (pyunrealsdk AV magnet).
    if now - _last_exe_reclaim < 45.0:
        return
    _last_exe_reclaim = now
    try:
        from .peer_session import reclaim_runtime_hooks

        reclaim_runtime_hooks()
    except Exception:
        pass


def _windows_excluded_tcp_ranges() -> list[tuple[int, int]]:
    """Hyper-V / WinNAT / ICS reserve blocks that fail bind with WSA 10013."""
    if os.name != "nt":
        return []
    try:
        import subprocess

        kwargs: dict[str, Any] = {"capture_output": True, "text": True, "timeout": 5}
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if create_no_window:
            kwargs["creationflags"] = create_no_window
        proc = subprocess.run(
            ["netsh", "interface", "ipv4", "show", "excludedportrange", "protocol=tcp"],
            **kwargs,
        )
        ranges: list[tuple[int, int]] = []
        for line in (proc.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                lo, hi = int(parts[0]), int(parts[1])
                if 0 < lo <= hi < 65536:
                    ranges.append((lo, hi))
        return ranges
    except Exception:
        return []


def _port_reserved(port: int, ranges: list[tuple[int, int]]) -> bool:
    return any(lo <= int(port) <= hi for lo, hi in ranges)


class _SqbtBridgeServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def _try_listen(port: int) -> ThreadingHTTPServer | None:
    try:
        return _SqbtBridgeServer((_HOST, int(port)), _SqbtBridgeHandler)
    except OSError:
        return None
    except Exception:
        return None


def _commit_server(server: ThreadingHTTPServer, port: int) -> None:
    global _server, _thread, _started, _PORT, _last_bridge_error
    _server = server
    _PORT = int(port)
    _thread = threading.Thread(
        target=_server.serve_forever,
        name="SQBTBridge",
        daemon=True,
    )
    _thread.start()
    _started = True
    _last_bridge_error = ""
    _write_port_file(_PORT)
    _log(f"Listening on http://{_HOST}:{_PORT}")


def start_bridge() -> None:
    global _started, _last_bridge_error
    if _started:
        return
    _register_tick_hook()
    excluded = _windows_excluded_tcp_ranges()
    tried: set[int] = set()
    for port in _PORT_CANDIDATES:
        if int(port) in tried or _port_reserved(port, excluded):
            continue
        tried.add(int(port))
        server = _try_listen(int(port))
        if server is None:
            continue
        _commit_server(server, int(port))
        return
    # Let Windows pick a free port outside Hyper-V exclusions.
    server = _try_listen(0)
    if server is not None:
        actual = int(server.server_address[1])
        _commit_server(server, actual)
        return
    _last_bridge_error = "no free localhost port (Hyper-V exclusions or another bind)"
    _started = False
    _log(f"Could not bind a localhost bridge port: {_last_bridge_error}")


def bridge_started() -> bool:
    return bool(_started)


def bound_port() -> int:
    return int(_PORT)


def stop_bridge() -> None:
    global _server, _thread, _started
    try:
        if _server is not None:
            _server.shutdown()
            _server.server_close()
    except Exception:
        pass
    _server = None
    _thread = None
    _started = False


def bridge_status_line() -> str:
    if not _started:
        return f"Bridge offline (port {_PORT})."
    return f"Bridge http://{_HOST}:{_PORT} · queue={len(_queue)}"


@command(
    "sqbt_bridge",
    description="Log Squ1ggs Boosting Tools localhost bridge status.",
)
def _cmd_sqbt_bridge(_args: object) -> None:
    # Console commands execute on the game thread, so this is also a safe
    # manual refresh useful when diagnosing hook compatibility.
    _refresh_status_cache()
    logging.info(f"{_PREFIX} {_status_payload()}")
