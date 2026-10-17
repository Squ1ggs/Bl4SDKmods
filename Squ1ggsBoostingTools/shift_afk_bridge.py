"""
SQBT SHiFT link bridge — Azalea ShiftFriendAutomation polls /sqbt_shift.

Cohtml (Azalea SHiFT UI management) talks to:
  127.0.0.1:51974–51977
and requires JSON with service == "squ1ggs-boosting-tools" + a 32-hex instance.

Native SDK has no friend-accept API; Azalea's Cohtml drives Accept when
auto_accept is true and the SHiFT UI stays Open. Credit:
  https://save-editor.be/GZO/Mods.html#/borderlands-4
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

_PREFIX = "[SQBT]"
_HOST = "127.0.0.1"
_AFK_PORTS = (51974, 51975, 51976, 51977)
_SERVICE = "squ1ggs-boosting-tools"
_PATH = "/sqbt_shift"

_lock = threading.Lock()
_started = False
_server: ThreadingHTTPServer | None = None
_thread: threading.Thread | None = None
_PORT = 0
_INSTANCE = uuid.uuid4().hex
_last_report: dict[str, Any] = {}
_force_until: float = 0.0


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
    except Exception:
        pass


def force_auto_accept(seconds: float) -> None:
    """Temporarily advertise auto_accept=true for Cohtml (Accept now)."""
    global _force_until
    try:
        hold = max(0.0, float(seconds))
    except Exception:
        hold = 0.0
    _force_until = time.time() + hold if hold > 0.0 else 0.0


def _auto_accept_enabled() -> bool:
    if _force_until > time.time():
        return True
    try:
        from . import shift_friend_autoaccept

        return bool(shift_friend_autoaccept.is_enabled())
    except Exception:
        return False


def _payload() -> dict[str, Any]:
    enabled = _auto_accept_enabled()
    return {
        "ok": True,
        "service": _SERVICE,
        "instance": _INSTANCE,
        "auto_accept": bool(enabled),
        "autoAccept": bool(enabled),
        "enabled": bool(enabled),
        "timestamp": time.time(),
        "source": "squ1ggs-boosting-tools",
        "product": "Squ1ggsBoostingTools",
    }


class _SqbtShiftHandler(BaseHTTPRequestHandler):
    server_version = "SQBTShiftLink/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _json(self, status: int, data: Any) -> None:
        body = json.dumps(data).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Sqbt-Instance")
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            return

    def do_OPTIONS(self) -> None:
        self._json(200, {"ok": True})

    def do_GET(self) -> None:
        path = (self.path or "").split("?", 1)[0]
        if path in ("/", "/status", "/health"):
            self._json(
                200,
                {
                    "ok": True,
                    "service": _SERVICE,
                    "port": int(_PORT),
                    "auto_accept": _auto_accept_enabled(),
                },
            )
            return
        if path == _PATH:
            self._json(200, _payload())
            return
        self._json(404, {"ok": False, "message": "Not found"})

    def do_POST(self) -> None:
        global _last_report
        path = (self.path or "").split("?", 1)[0]
        if path != _PATH:
            self._json(404, {"ok": False, "message": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            data = json.loads(raw or "{}")
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        with _lock:
            _last_report = {
                "at": time.time(),
                "running": bool(data.get("running")),
                "accepted": int(data.get("accepted") or 0),
                "failed": int(data.get("failed") or 0),
                "message": str(data.get("message") or "")[:200],
            }
        if _last_report.get("running") or _last_report.get("accepted") or _last_report.get("failed"):
            _log(
                f"SHiFT link report: running={_last_report.get('running')} "
                f"accepted={_last_report.get('accepted')} failed={_last_report.get('failed')}"
            )
        self._json(200, _payload())


class _SqbtShiftServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_afk_shift_bridge() -> bool:
    """Bind one SQBT link port. Name kept for call-site compatibility."""
    global _started, _server, _thread, _PORT
    if _started and _server is not None:
        return True
    for port in _AFK_PORTS:
        try:
            server = _SqbtShiftServer((_HOST, int(port)), _SqbtShiftHandler)
        except OSError:
            continue
        except Exception:
            continue
        _server = server
        _PORT = int(port)
        _thread = threading.Thread(
            target=_server.serve_forever,
            name="SQBTShiftLink",
            daemon=True,
        )
        _thread.start()
        _started = True
        _log(
            f"SHiFT SQBT link on http://{_HOST}:{_PORT}{_PATH} "
            f"(Azalea Cohtml; auto_accept follows sticky)"
        )
        return True
    _log(
        f"SHiFT SQBT link: could not bind {_AFK_PORTS} — "
        "Azalea Cohtml will not see SQBT (port busy?)"
    )
    return False


def stop_afk_shift_bridge() -> None:
    global _server, _thread, _started, _PORT
    try:
        if _server is not None:
            _server.shutdown()
            _server.server_close()
    except Exception:
        pass
    _server = None
    _thread = None
    _started = False
    _PORT = 0


def afk_shift_status() -> dict[str, Any]:
    with _lock:
        report = dict(_last_report)
    return {
        "started": bool(_started),
        "port": int(_PORT),
        "instance": _INSTANCE,
        "service": _SERVICE,
        "path": _PATH,
        "auto_accept": _auto_accept_enabled(),
        "last_report": report,
    }


def bound_port() -> int:
    return int(_PORT)
