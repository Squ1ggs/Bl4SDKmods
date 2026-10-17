"""Sequential full-boost workflow for the selected player or current lobby.

Missions, non-UVHM challenges and UVHM all use long-running game-thread jobs.
This coordinator starts exactly one at a time; it never combines their writes.
"""
from __future__ import annotations

import time
from typing import Any


_job: dict[str, Any] | None = None
_last_tick_at = 0.0
_STEP_GAP = 0.35
_TERMINAL_STATUS_SEC = 6.0


def _log(message: str) -> None:
    try:
        from . import runtime_log

        runtime_log.note(f"Give everything: {message}")
    except Exception:
        pass


def _ok(message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": True, "message": message, **extra}


def _fail(message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "message": message, **extra}


def is_running() -> bool:
    return bool(_job and _job.get("state") == "running")


def status() -> dict[str, Any]:
    if _job is None:
        return {
            "active": False,
            "running": False,
            "phase": "idle",
            "message": "No Give everything job.",
        }
    phase = str(_job.get("phase") or "idle")
    state = str(_job.get("state") or "idle")
    display_phase = phase if is_running() else str(_job.get("finished_phase") or phase)
    phase_total = 5 if _job.get("include_discovery") else 4
    progress_index = {"missions": 0, "challenges": 1, "uvhm": 2, "grassroots": 3, "discovery": 4}.get(display_phase, 0)
    if _job.get('discovery_only'):
        phase_total, progress_index = 1, 0
    progress_fraction = 0.0
    child: dict[str, Any] = {}
    if is_running():
        try:
            if display_phase in ("missions", "grassroots"):
                from . import mission_progress

                child = mission_progress.status()
                total = max(0, int(child.get("total") or 0))
                done = max(0, int(child.get("index") or 0))
                progress_fraction = min(1.0, done / total) if total else 0.0
            elif display_phase == "challenges":
                from . import challenge_bulk_runtime

                child = challenge_bulk_runtime.status()
                total = max(0.0, float(child.get("progress_total") or child.get("total") or 0))
                done = max(0.0, float(child.get("progress_index") or child.get("index") or 0))
                progress_fraction = min(1.0, done / total) if total else 0.0
            elif display_phase == "uvhm":
                from . import uvhm_runtime

                child = uvhm_runtime.status()
                progress_fraction = min(1.0, max(0.0, float(child.get("progress_percent") or 0) / 100.0))
            elif display_phase == "discovery":
                from . import map_discovery
                child = map_discovery.status()
                progress_fraction = min(1.0, float(child['progress_percent']) / 100.0) if 'progress_percent' in child else min(1.0, float(child.get('index') or 0) / max(1, int(child.get('total') or 0)))
        except Exception:
            child = {}
    progress_percent = 100.0 if state == "complete" else min(99.5, ((progress_index + progress_fraction) / phase_total) * 100.0)
    if is_running():
        _job["last_progress_percent"] = progress_percent
    else:
        progress_percent = max(0.0, float(_job.get("last_progress_percent") or 0.0))
    terminal_live = not is_running() and time.monotonic() < float(_job.get("terminal_until") or 0.0)
    return {
        "active": is_running() or terminal_live,
        "running": is_running(),
        "phase": display_phase if is_running() else state,
        "workflow_phase": display_phase,
        "phase_number": phase_total if state in ("complete", "partial") else min(phase_total, progress_index + (1 if is_running() else 0)),
        "phase_total": phase_total,
        "progress_percent": progress_percent,
        "progress_index": progress_index + progress_fraction,
        "progress_total": phase_total,
        "child_index": child.get("progress_index", child.get("index", 0)),
        "child_total": child.get("progress_total", child.get("total", 0)),
        "child_message": child.get("message", ""),
        "state": state,
        "message": str(_job.get("message") or ""),
        "player_index": int(_job.get("player_index") or 0),
        "max_all": str(_job.get("max_message") or ""),
        "mission_shortfall": dict(_job.get("mission_shortfall") or {}),
        "challenge_summary": dict(_job.get("challenge_summary") or {}),
        "discovery_summary": dict(_job.get("discovery_summary") or {}),
        "discovery_only": bool(_job.get("discovery_only")),
    }


def _progression_busy() -> str:
    try:
        from . import map_discovery
        if map_discovery.is_running():
            return "map discovery"
    except Exception:
        pass
    try:
        from . import mission_progress

        if mission_progress.is_running():
            return "missions"
    except Exception:
        pass
    try:
        from . import challenge_bulk_runtime

        st = challenge_bulk_runtime.status()
        if st.get("running") or st.get("queued"):
            return "challenges"
    except Exception:
        pass
    try:
        from . import uvhm_runtime

        st = uvhm_runtime.status()
        if st.get("running") or st.get("queued"):
            return "UVHM"
    except Exception:
        pass
    return ""


def start(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply MAX ALL now, then queue missions -> challenges -> UVHM."""
    global _job
    payload = dict(payload or {})
    if is_running():
        return _fail("Give everything is already running.", give_everything=status())

    from .backend_actions import get_target_player_index, max_all
    from . import mission_progress

    raw_index = payload.get("player_index")
    try:
        player_index = (
            int(raw_index)
            if raw_index is not None and str(raw_index).strip()
            else int(get_target_player_index())
        )
    except Exception:
        return _fail("Pick one valid Boost target first.")
    if player_index < -1:
        return _fail("Pick a valid Boost target or All players.")
    # Resolve the target before MAX ALL writes anything. A stale lobby seat
    # must not partially apply economy and only then fail mission startup.
    try:
        from .uvhm_progression import selected_lobby_identity, snapshot_lobby_identities

        targets = tuple(snapshot_lobby_identities()) if player_index == -1 else (selected_lobby_identity(player_index),)
        if not targets:
            return _fail("No boost target players are available in the lobby.")
    except Exception as exc:
        return _fail(f"Boost target unavailable: {exc}")

    busy = _progression_busy()
    if busy:
        return _fail(f"Wait for the current {busy} job to finish or cancel it first.")

    preview = mission_progress.preview("all")
    if not preview.get("ok"):
        return _fail(
            str(preview.get("message") or "Missions are unavailable on this game build."),
            mission=preview,
        )

    max_payload = {
        **payload,
        "player_index": player_index,
        "max_cash": True,
        "max_eridium": True,
        "max_sdu": True,
        "max_vault_cards": True,
        "max_player_level": True,
        "max_spec_level": True,
        "max_mayhem": True,
        "max_mayhem_amount": 20,
        "max_cosmetics": True,
        # The coordinator starts these only after missions finish.
        "max_challenges": False,
        "max_uvhm_challenges": False,
        "max_missions": False,
    }
    max_result = max_all(max_payload)
    if not max_result.get("ok"):
        return _fail(
            str(max_result.get("message") or "MAX ALL failed; the full workflow was not queued."),
            max_all=max_result,
        )

    mission = mission_progress.start("all", player_index, redo_completed=False)
    if not mission.get("ok"):
        return _fail(
            "MAX ALL was applied, but missions could not start: "
            + str(mission.get("message") or "unknown mission error"),
            max_all=max_result,
            mission=mission,
        )

    _job = {
        "state": "running",
        "phase": "missions",
        "player_index": player_index,
        "targets": targets,
        "identity": (getattr(mission_progress, "_job", None) or {}).get("identity"),
        "max_message": str(max_result.get("message") or "MAX ALL applied."),
        "run_grassroots": True,
        "include_discovery": True,
        "message": (
            "MAX ALL applied · missions running · challenges, UVHM and map discovery will follow. This can take several minutes; keep everyone connected."
        ),
    }
    _log(_job["message"])
    return _ok(_job["message"], give_everything=status(), mission=mission, max_all=max_result)


def queue_after_max_all(player_index: int, *, challenges: bool, uvhm: bool, redo_completed: bool = False) -> dict[str, Any]:
    """Queue the selected mission/challenge/UVHM options after economy is applied."""
    global _job
    if is_running():
        return _fail("A MAX ALL progression workflow is already running.")
    busy = _progression_busy()
    if busy:
        return _fail(f"Wait for {busy} to finish before queuing missions.")
    from . import mission_progress

    result = mission_progress.start("all", int(player_index), redo_completed=bool(redo_completed))
    if not result.get("ok"):
        return result
    _job = {"state": "running", "phase": "missions", "player_index": int(player_index),
            "identity": (getattr(mission_progress, "_job", None) or {}).get("identity"),
            "max_message": "Selected MAX ALL economy options applied.",
            "include_challenges": bool(challenges), "include_uvhm": bool(uvhm),
            "run_grassroots": bool(challenges),
            "message": "All missions queued; selected challenges and UVHM will follow in order."}
    return _ok(_job["message"], mission=result, give_everything=status())


def _finish(state: str, message: str) -> None:
    if _job is None:
        return
    shortfall = _job.get("mission_shortfall") or {}
    if state in ("complete", "partial") and _job.get("uvhm_unverified"):
        state = "partial"
        message += " UVHM commands were sent; guest objective completion still needs save/reload confirmation."
    if state == "complete" and shortfall:
        state = "partial"
        message += f" Missions remain partial: {shortfall['completed']}/{shortfall['total']} completed, {shortfall['locked']} locked."
    if state in ("complete", "partial"):
        _job["last_progress_percent"] = 100.0
    elif is_running():
        status()  # Retain the last confirmed progress for stopped/cancelled UI.
    _job["finished_phase"] = str(_job.get("phase") or "")
    _job["state"] = state
    _job["phase"] = state
    _job["message"] = message
    _job["terminal_until"] = time.monotonic() + _TERMINAL_STATUS_SEC
    _log(message)


def track_challenge_registration(player_index: int) -> None:
    """Own the final side turn-in for standalone All/World challenge jobs."""
    global _job
    if is_running():
        return
    from .uvhm_progression import selected_lobby_identity, snapshot_lobby_identities

    targets = tuple(snapshot_lobby_identities()) if player_index == -1 else (selected_lobby_identity(player_index),)
    _job = {
        "state": "running", "phase": "challenges", "player_index": player_index,
        "targets": targets, "identity": targets[0] if player_index >= 0 else None,
        "include_uvhm": False, "run_grassroots": True,
        "standalone_challenges": True,
        "message": "Challenges running; a side-mission turn-in will follow for registration.",
    }


def attach_challenge_uvhm_followup() -> bool:
    """Keep MAX ALL's UVHM before the registration mission, never concurrent."""
    if is_running() and _job.get("standalone_challenges") and _job.get("phase") == "challenges":
        _job["include_uvhm"] = True
        return True
    return False


def start_discovery(player_index: int) -> dict[str, Any]:
    global _job
    if is_running() or _progression_busy():
        return _fail('Wait for the active progression job before discovering locations.')
    from . import map_discovery
    from .uvhm_progression import selected_lobby_identity, snapshot_lobby_identities
    try:
        targets = tuple(snapshot_lobby_identities()) if player_index == -1 else (selected_lobby_identity(player_index),)
        result = map_discovery.start(player_index)
        if not result.get('ok'):
            return result
        _job = dict(state='running', phase='discovery', player_index=player_index,
                    targets=targets, identity=targets[0] if player_index >= 0 else None,
                    include_discovery=True, discovery_only=True, message=result['message'])
        return _ok(result['message'], give_everything=status())
    except Exception as exc:
        return _fail(str(exc))


def cancel() -> dict[str, Any]:
    if not is_running():
        return _fail("No Give everything job is running.", give_everything=status())
    phase = str(_job.get("phase") or "")
    try:
        if phase == "missions":
            from . import mission_progress

            mission_progress.cancel()
        elif phase == "challenges":
            from . import challenge_bulk_runtime

            challenge_bulk_runtime.cancel()
        elif phase == "uvhm":
            from . import uvhm_runtime

            uvhm_runtime.cancel()
        elif phase == "grassroots":
            from . import mission_progress

            mission_progress.cancel()
        elif phase == "discovery":
            from . import map_discovery
            map_discovery.cancel()
    finally:
        _finish("cancelled", "Give everything cancelled — finished work stays applied.")
    return _ok("Give everything cancelled.", give_everything=status())


def _current_player_index() -> int | None:
    assert _job is not None
    index = int(_job["player_index"])
    if index == -1 and _job.get("targets"):
        from .uvhm_progression import snapshot_lobby_identities

        expected = {target.key for target in _job["targets"]}
        current = {target.key for target in snapshot_lobby_identities()}
        if expected != current:
            _finish("stopped", "Lobby players changed; Give everything stopped before boosting a replacement player.")
            return None
        return -1
    identity = _job.get("identity")
    if index < 0 or identity is None:
        return index
    from .uvhm_progression import resolve_lobby_pc
    from .party_helpers import _gbc_session_world_and_gamestate

    pc = resolve_lobby_pc(identity)
    if pc is not None:
        _world, gs = _gbc_session_world_and_gamestate()
        for current, ps in enumerate(list(getattr(gs, "PlayerArray", None) or [])):
            if str(ps) == str(getattr(pc, "PlayerState", None)):
                _job["player_index"] = current
                return current
    _finish("stopped", "The selected player left before the next progression step; no replacement lobby seat was boosted.")
    return None


def _start_challenges() -> bool:
    assert _job is not None
    if not _job.get("include_challenges", True):
        return _start_uvhm()
    from . import challenge_bulk_runtime

    player_index = _current_player_index()
    if player_index is None:
        return False
    if not challenge_bulk_runtime.request_selected(
        player_index,
        "All non-UVHM",
        confirmed=True,
    ):
        reason = str(challenge_bulk_runtime.status().get("message") or "could not queue challenges")
        _finish("stopped", f"Give everything stopped before challenges: {reason}")
        return False
    _job["phase"] = "challenges"
    shortfall = _job.get("mission_shortfall") or {}
    _job["message"] = (
        f"Missions processed ({shortfall['locked']} still locked) · challenges running · UVHM will follow."
        if shortfall else "Missions complete · challenges running · UVHM will follow."
    )
    _log(_job["message"])
    return True


def _start_uvhm() -> bool:
    assert _job is not None
    if not _job.get("include_uvhm", True):
        return _start_grassroots()
    from . import uvhm_runtime

    player_index = _current_player_index()
    if player_index is None:
        return False
    queued = (uvhm_runtime.request_all(confirmed=True, max_rank=7, quiet=True)
              if player_index < 0 else uvhm_runtime.request_selected(player_index, max_rank=7, quiet=True))
    if not queued:
        reason = str(uvhm_runtime.status().get("message") or "could not queue UVHM")
        _finish("stopped", f"Give everything stopped before UVHM: {reason}")
        return False
    _job["phase"] = "uvhm"
    _job["message"] = (
        "Challenges complete · UVHM 1–7 running; locked missions remain listed for review."
        if _job.get("mission_shortfall") else "Missions and challenges complete · UVHM 1–7 running."
    )
    _log(_job["message"])
    return True


def _start_grassroots() -> bool:
    """Finish challenge boosting with one real Grassroots mission turn-in."""
    assert _job is not None
    if not _job.get("run_grassroots", False):
        _finish("complete", "Selected MAX ALL mission/progression options finished.")
        return True
    from . import mission_progress

    player_index = _current_player_index()
    if player_index is None:
        return False
    result = mission_progress.start_grassroots_turnin(player_index)
    if not result.get("ok"):
        _finish("stopped", f"Give everything could not finish Grassroots Campaigner: {result.get('message')}")
        return False
    _job["phase"] = "grassroots"
    _job["message"] = str(result.get("message") or "Turning in a Grassroots side mission.")
    _log(_job["message"])
    return True


def runtime_tick(*_args: Any, **_kwargs: Any) -> None:
    """Advance only on terminal evidence from the currently-owned workflow."""
    global _last_tick_at
    if not is_running() or _job is None:
        return
    now = time.monotonic()
    if now - _last_tick_at < _STEP_GAP:
        return
    _last_tick_at = now

    phase = str(_job.get("phase") or "")
    if int(_job.get("player_index", 0)) == -1 and _job.get("targets"):
        if _current_player_index() is None:
            # Cancel the owned child as well; never leave it writing after the
            # coordinator reports a changed lobby roster.
            if phase in ("missions", "grassroots"):
                from . import mission_progress
                mission_progress.cancel()
            elif phase == "challenges":
                from . import challenge_bulk_runtime
                challenge_bulk_runtime.cancel()
            elif phase == "uvhm":
                from . import uvhm_runtime
                uvhm_runtime.cancel()
            elif phase == "discovery":
                from . import map_discovery
                map_discovery.cancel()
            return
    if phase == "missions":
        from . import mission_progress

        st = mission_progress.status()
        if st.get("running"):
            _job["message"] = str(st.get("message") or "Missions running.")
            return
        terminal = str(st.get("phase") or "")
        # Locked prerequisites are a settled shortfall, not an uncertain native
        # write. Finish the other independent boost stages, retaining the exact
        # missing missions and a partial final result.
        locked = int(st.get("locked") or 0)
        settled = int(st.get("completed") or 0) + int(st.get("already") or 0)
        total = int(st.get("total") or 0)
        unresolved_error = any(int(st.get(key) or 0) for key in ("failed", "unsupported", "blocked_count", "uncertain"))
        if terminal in ("complete", "stopped") and locked > 0 and not unresolved_error and settled + locked == total:
            _job["mission_shortfall"] = {
                "completed": settled, "locked": locked, "total": total,
                "missions": [dict(row) for row in (st.get("results") or []) if row.get("outcome") == "locked"],
            }
            _log(f"Missions settled {settled}/{total}; {locked} locked. Continuing independent challenges and UVHM; final result will remain partial.")
            _start_challenges()
            return
        if terminal == "complete":
            if any(int(st.get(key) or 0) for key in ("failed", "locked", "unsupported", "blocked_count", "uncertain")):
                _finish("stopped", "MAX ALL progression stopped because some missions were blocked, unsupported or failed. Check Mission status.")
                return
            _start_challenges()
        elif terminal in ("cancelled", "stopped"):
            _finish("stopped", f"Give everything stopped after missions: {st.get('message')}")
        return

    if phase == "challenges":
        from . import challenge_bulk_runtime

        st = challenge_bulk_runtime.status()
        if st.get("running") or st.get("queued"):
            _job["message"] = str(st.get("message") or "Challenges running.")
            return
        terminal = str(st.get("phase") or "")
        if terminal == "complete":
            _job["challenge_summary"] = {
                "accepted": int(st.get("ok") or 0), "skipped": int(st.get("skipped") or 0),
                "failed": int(st.get("failed") or 0),
                "unavailable_targets": list(st.get("unavailable_targets") or []),
            }
            if _job["challenge_summary"]["failed"] or _job["challenge_summary"]["unavailable_targets"]:
                _finish("stopped", "Non-UVHM challenges were not completed for every target: "
                        f"{_job['challenge_summary']['failed']} failed writes; unavailable targets: "
                        + (", ".join(_job["challenge_summary"]["unavailable_targets"]) or "none") + ". Check Challenge status before retrying.")
                return
            _start_uvhm()
        elif terminal in ("cancelled", "error"):
            _finish("stopped", f"Give everything stopped after challenges: {st.get('message')}")
        return

    if phase == "uvhm":
        from . import uvhm_runtime

        st = uvhm_runtime.status()
        if st.get("running") or st.get("queued"):
            _job["message"] = str(st.get("message") or "UVHM running.")
            return
        terminal = str(st.get("phase") or "")
        if terminal == "complete":
            _job["uvhm_unverified"] = any(
                str(row).startswith("objective-unverified:") for row in st.get("results", ())
            )
            _start_grassroots()
        elif terminal in ("cancelled", "error"):
            _finish("stopped", f"Give everything stopped during UVHM: {st.get('message')}")
        return

    if phase == "grassroots":
        from . import mission_progress

        st = mission_progress.status()
        if st.get("running"):
            _job["message"] = str(st.get("message") or "Turning in a Grassroots side mission.")
            return
        terminal = str(st.get("phase") or "")
        if terminal == "complete":
            confirmed = any(
                row.get("name") and row.get("outcome") in ("completed", "already_completed")
                for row in (st.get("results") or [])
            )
            if confirmed:
                shortfall = _job.get("mission_shortfall") or {}
                if _job.get("include_discovery"):
                    player_index = _current_player_index()
                    if player_index is None:
                        return
                    from . import map_discovery
                    result = map_discovery.start(player_index)
                    if not result.get('ok'):
                        _finish('partial', 'Boost stages finished, but discovery could not start: ' + str(result.get('message')))
                        return
                    _job['phase'] = 'discovery'
                    _job['message'] = str(result['message'])
                    return
                _finish(
                    "partial" if shortfall else "complete",
                    (
                        f"Challenges, UVHM and Grassroots finished · missions {shortfall['completed']}/{shortfall['total']}; {shortfall['locked']} still locked. Mission status lists the missing prerequisites."
                        if shortfall else "Give everything complete · challenges and UVHM finished, then a Grassroots side mission was accepted and its completion verified. Save and reload the guest to check their campaigner card."
                    ),
                )
            else:
                _finish("stopped", "Grassroots side mission finished without a confirmed mission result; check Mission status.")
        elif terminal in ("cancelled", "stopped"):
            _finish("stopped", f"Give everything stopped during the Grassroots side mission: {st.get('message')}")

    if phase == 'discovery':
        from . import map_discovery
        st = map_discovery.status()
        _job['message'] = str(st.get('message') or '')
        if st.get('running'):
            return
        _job['discovery_summary'] = dict(st)
        shortfall = _job.get('mission_shortfall') or {}
        detail = (f" Missions {shortfall['completed']}/{shortfall['total']}; {shortfall['locked']} still locked." if shortfall else '')
        _finish('complete' if st.get('phase') == 'complete' else 'partial', ('Map discovery finished. ' if _job.get('discovery_only') else 'Boost stages finished. ') + str(st.get('message')) + detail)
