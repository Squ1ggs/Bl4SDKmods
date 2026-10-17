"""Story / side / DLC missions on the host — status, accept, complete, travel repairs.

Mission completion is shared lobby progress: the host world owns every mission
record, so finishing one credits connected guests too. The Boost target only
supplies mission acceptance (``ServerActivateMission``).

Native reads and calls are pinned to Borderlands4.exe PE timestamp 0x6aa81051
(image size 0x31b8c000). Any other build refuses before the first read; all reads
go through ReadProcessMemory so a stale pointer fails instead of crashing.
One native write per tick, the mission list is re-read after each one, and an
unexpected result stops the job — uncertain writes are never retried.
"""

from __future__ import annotations

import ctypes as C
import re
import struct
import time
from typing import Any

import unrealsdk
from unrealsdk import logging

from .data_files import read_data_json

_PREFIX = "[Squ1ggs Boosting Tools | Missions]"

_PE_TIMESTAMP = 0x6AA81051
_PE_IMAGE_SIZE = 0x31B8C000
_CODE_FINGERPRINTS = {
    0xF19EE4: "5657534883ec204489c789d34889cee8a412ebff84c074504889f1e830f40200",
    0xD80660: "4157415641554154565755534883ec68488b05c9f2970b4831e048894424604c",
    0xD82E30: "4157415641554154565755534883ec7889d34889ce488b05f4ca970b4831e048",
    0x5F7DAC: "564883ec30488b05887b100c4831e04889442428488b4108488b48204885c974",
    0xD83366: "564883ec204889d6488b4108488b48684885c9751048c706000000004889f048",
    0x3A18C8: "41565657534881ec380100004889d6488b0562e0350c4831e048898424300100",
    0x3D32A5C: "5657534883ec404489c3488b05d3ce9c084831e0488944243880fa070f87bb00",
}
_VT_GAME_INSTANCE = 0xB752920
_VT_SHARD = 0xB7DC120
_VT_MISSION_INTERFACE = 0xB975980
_VT_MISSION_RECORD = 0xB973820
_VT_RECORD_SLOT_F8 = 0xD80660
_VT_RECORD_SLOT_110 = 0x419FEFA
_FN_RECORD_STATUS = 0xF19EE4  # (record, u8 status, bool) — 6 = completed
_FN_STORAGE_STATUS = 0x3D32A5C  # (storage, u8 status, bool) — 2 = available
_ACCEPTED_FNAME = 0xCB80808

_STATUS_COMPLETE = 6
_STATUS_AVAILABLE = 2
_ELIGIBLE = ("available", "active", "accepted")
# These catalogued follow-ups can retain an unset status after their parent
# completes. Only existing, reviewed shared records may use the reset path.
_SIDE_CHAIN_PARENTS = {
    "Mission_Micro_BackMcCrackyPt2": "Mission_Micro_BackMcCrackyPt1",
    "Mission_Micro_BackMcCrackyPt3": "Mission_Micro_BackMcCrackyPt2",
}
_BASE_WORLD_PATH = "/Game/Maps/WorldLevels/World_P.World_P"
_NON_GAMEPLAY_WORLD_MARKERS = ("frontend", "mainmenu", "loading", "entry", "startup")

# Replayable Takedown runs — the game never saves these.
_NONPERSISTENT = frozenset(
    {"Mission_DLC_Tuba_Base", "Mission_DLC_Tuba_Hardcore", "Mission_DLC_Tuba_TimerBase"}
)
# Travel checkpoints that gate later missions; repaired automatically while a batch waits.
_BATCH_REPAIRS = ("electi", "heist", "vending", "clapgen", "cowbell_ellie", "cowbell_hatchery")

_STEP_GAP = 0.2
_STALL_LIMIT = 10.0
_STICKY_SEC = 4.0
_RESULT_KINDS = (
    "completed",
    "already_completed",
    "locked",
    "unsupported",
    "blocked",
    "failed",
)
SCOPES = ("current", "story", "side", "dlc", "all")
SCOPE_LABELS = {
    "current": "Tracked mission",
    "story": "Story",
    "side": "Side",
    "dlc": "DLC",
    "all": "All missions",
}

_catalog: dict[str, dict[str, Any]] | None = None
_checkpoints: list[dict[str, str]] | None = None
_native: "_Native | None" = None
_job: dict[str, Any] | None = None
_last_step_at = 0.0
_sticky_until = 0.0


def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")
    try:
        from . import runtime_log

        runtime_log.note(f"Missions: {msg}")
    except Exception:
        pass


def _load_catalog() -> dict[str, dict[str, Any]]:
    global _catalog, _checkpoints
    if _catalog is None:
        data = read_data_json("mission_catalog.json", {})
        _catalog = {str(r["name"]): r for r in data.get("missions", [])}
        _checkpoints = list(data.get("travel_checkpoints", []))
    return _catalog


def _travel_checkpoints() -> list[dict[str, str]]:
    _load_catalog()
    return list(_checkpoints or [])


def _ordered_mission_names(names: list[str]) -> list[str]:
    """Keep campaign order, then side chains, then DLC; eligibility still gates writes."""
    catalog = _load_catalog()
    groups = {"story": 0, "side": 1, "dlc": 2}
    anchors: dict[tuple[int, str], int] = {}
    keys: dict[str, tuple[int, int, int, int]] = {}
    for position, name in enumerate(names):
        group = groups.get(str(catalog.get(name, {}).get("category")), 3)
        # Appended catalog discoveries must not put part 2/3 after unrelated
        # DLC. Do not infer prerequisites or change any native mission state.
        match = re.match(r"^(.*?)(?:part|pt)(\d+)$", name, re.IGNORECASE)
        chain = match.group(1).casefold() if match else name.casefold()
        part = int(match.group(2)) if match else 0
        anchor = anchors.setdefault((group, chain), position)
        keys[name] = (group, anchor, part, position)
    return sorted(names, key=keys.__getitem__)


def _scope_key(scope: str) -> str:
    text = str(scope or "current").strip().lower()
    for key, label in SCOPE_LABELS.items():
        if text in (key, label.lower()):
            return key
    return text


def _is_gameplay_world_path(world_path: str) -> bool:
    lower_path = str(world_path or "").casefold()
    return bool(
        lower_path
        and "/maps/" in lower_path
        and not any(marker in lower_path for marker in _NON_GAMEPLAY_WORLD_MARKERS)
    )


def _title(name: str) -> str:
    return str(_load_catalog().get(name, {}).get("title") or name)


def _record_result(
    name: str,
    outcome: str,
    reason: str,
    *,
    before: str | None = None,
    after: str | None = None,
    operation: str | None = None,
    uncertain: bool = False,
) -> None:
    """Record one terminal, observed result for a mission.

    Results are append-only for a run.  Presentation code may decorate these
    rows, but it must not turn an unconfirmed write into a completed result.
    """
    job = _job
    if job is None or outcome not in _RESULT_KINDS:
        return
    if name in job["result_names"]:
        return
    row = {
        "name": name,
        "title": _title(name),
        "outcome": outcome,
        "reason": str(reason),
        "before": before,
        "after": after,
        "operation": operation,
        "uncertain": bool(uncertain),
    }
    if outcome not in ("completed", "already_completed"):
        _log(f"result={outcome} mission={name} title={_title(name)} before={before} reason={reason}")
    job["results"].append(row)
    job["result_names"].add(name)
    if outcome == "completed":
        job["done"].append(name)
    elif outcome == "already_completed":
        job["already"].append(name)
    elif outcome in ("locked", "blocked"):
        job["blocked"].append(_title(name))


def _result_counts(job: dict[str, Any]) -> dict[str, int]:
    counts = {key: 0 for key in _RESULT_KINDS}
    for row in job.get("results") or ():
        kind = str(row.get("outcome") or "")
        if kind in counts:
            counts[kind] += 1
    return counts


class _Native:
    """Build-gated reader for the host mission list."""

    def __init__(self) -> None:
        k = C.WinDLL("kernel32", use_last_error=True)
        k.GetModuleHandleW.argtypes = [C.c_wchar_p]
        k.GetModuleHandleW.restype = C.c_void_p
        k.GetCurrentProcess.restype = C.c_void_p
        k.ReadProcessMemory.argtypes = [
            C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t),
        ]
        k.ReadProcessMemory.restype = C.c_bool
        self._k = k
        self._proc = k.GetCurrentProcess()
        self.base = int(k.GetModuleHandleW(None) or 0)
        if not self.base:
            raise RuntimeError("Could not resolve the game module")
        self._check_build()
        self.world_addr = 0
        self.world_path = ""
        self.names: dict[str, str] = {}
        for name in _load_catalog():
            self.names[self._fname_hex(name)] = name
        self.status_names = {
            self._fname_hex(s): s
            for s in ("None", "locked", "available", "active", "completed", "failed")
        }
        self.status_names[self.read(self.base + _ACCEPTED_FNAME, 8).hex()] = "accepted"

    def read(self, address: int, size: int) -> bytes:
        if not 0x10000 < address < 0x800000000000 or not 0 < size <= 16384:
            raise ValueError("Mission read out of range")
        buf = C.create_string_buffer(size)
        got = C.c_size_t()
        if not self._k.ReadProcessMemory(self._proc, C.c_void_p(address), buf, size, C.byref(got)) or got.value != size:
            raise OSError("Mission memory unreadable")
        return buf.raw

    def u64(self, address: int) -> int:
        return struct.unpack("<Q", self.read(address, 8))[0]

    def array(self, address: int, limit: int) -> tuple[int, int]:
        data, count, cap = struct.unpack("<Qii", self.read(address, 16))
        if not 0 <= count <= cap <= limit or (count and not data):
            raise ValueError("Mission array bounds unexpected")
        return data, count

    def _check_build(self) -> None:
        pe = struct.unpack("<I", self.read(self.base + 0x3C, 4))[0]
        stamp = struct.unpack("<I", self.read(self.base + pe + 8, 4))[0]
        image = struct.unpack("<I", self.read(self.base + pe + 24 + 56, 4))[0]
        if stamp != _PE_TIMESTAMP or image != _PE_IMAGE_SIZE:
            raise RuntimeError(
                "Missions are not supported on this game build yet "
                f"(PE {stamp:#x}) — wait for an SQBT update."
            )
        for rva, expected in _CODE_FINGERPRINTS.items():
            if self.read(self.base + rva, 32).hex() != expected:
                raise RuntimeError(f"Mission code fingerprint mismatch at {rva:#x}")

    def _fname_hex(self, label: str) -> str:
        token = unrealsdk.make_struct("/Script/CoreUObject.SToken", Name=label)
        return self.read(token._get_address() + 4, 8).hex()

    def _variant(self, address: int) -> tuple[int, str | None]:
        raw = self.read(address, 16)
        return raw[0], (raw[4:12].hex() if raw[0] == 3 else None)

    def _fact(self, storage: int, offset: int) -> tuple[int, str | None] | None:
        if not storage:
            return None
        fields = self.u64(storage + 8)
        value = self.u64(fields + offset) if fields else 0
        return self._variant(value + 0x38) if value else None

    def _world(self) -> Any:
        from mods_base import ENGINE

        world = getattr(getattr(ENGINE, "GameViewport", None), "World", None)
        if world is None:
            raise RuntimeError("No playable world is loaded")
        try:
            world_path = str(world._path_name() or "")
        except Exception as exc:
            raise RuntimeError(f"Could not identify the current world: {exc}") from exc
        if not _is_gameplay_world_path(world_path):
            raise RuntimeError(f"Not in a supported gameplay world ({world_path or 'unknown'})")
        try:
            from .session_guards import session_safe

            if not session_safe():
                raise RuntimeError("The current world or player is still loading")
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Could not confirm a stable gameplay session: {exc}") from exc
        addr = int(world._get_address())
        if self.world_addr and addr != self.world_addr:
            raise RuntimeError("World changed — start the missions again")
        self.world_addr = addr
        self.world_path = world_path
        return world

    def _interface(self) -> int:
        world = self._world()
        gi = getattr(world, "OwningGameInstance", None)
        if gi is None:
            raise RuntimeError("No game instance")
        gi_addr = int(gi._get_address())
        if self.u64(gi_addr) != self.base + _VT_GAME_INSTANCE:
            raise RuntimeError("Unexpected game instance layout")
        shard = self.u64(self.u64(gi_addr + 0x518) + 0x38)
        if self.u64(shard) != self.base + _VT_SHARD:
            raise RuntimeError("Unexpected mission shard")
        iface = self.u64(self.u64(shard + 0x180) + 0xE0)
        if self.u64(iface) != self.base + _VT_MISSION_INTERFACE:
            raise RuntimeError("Unexpected mission interface")
        return iface

    def snapshot(self) -> dict[str, Any]:
        iface = self._interface()
        data, count = self.array(iface + 0x60, 2000)
        rows: dict[str, dict[str, Any]] = {}
        dupes: set[str] = set()
        for i in range(count):
            entry = self.read(data + i * 32, 32)
            record = struct.unpack_from("<Q", entry, 16)[0]
            if not record or self.u64(record) != self.base + _VT_MISSION_RECORD:
                continue
            name = self.names.get(entry[4:12].hex())
            if name is None:
                continue
            if name in rows:
                dupes.add(name)
                continue
            definition = self.u64(record + 0xA0)
            storage = self.u64(record + 0xA8)
            exits, exit_count = self.array(definition + 0x70, 100)
            status = self._fact(storage, 0x20)
            rows[name] = {
                "token": entry[:12],
                "record": record,
                "storage": storage,
                "shared": self.read(definition + 0x538, 1)[0] == 0,
                "generated": self.read(definition + 0x750, 1)[0] != 0,
                "status": self.status_names.get(status[1]) if status and status[1] else None,
                "exit": self._fact(storage, 0x68),
                "exit_names": [self.read(exits + j * 0x60, 8).hex() for j in range(exit_count)],
            }
        for name in dupes:
            rows.pop(name, None)
        tracked: list[str] = []
        tracker = self.u64(iface + 0x188)
        if tracker:
            tokens, n = self.array(tracker + 0x160, 100)
            for j in range(n):
                hit = self.names.get(self.read(tokens + j * 12 + 4, 8).hex())
                if hit:
                    tracked.append(hit)
        return {"rows": rows, "tracked": tracked, "world_path": self.world_path}

    def check_row(self, name: str, row: dict[str, Any]) -> None:
        if row["generated"] or not row["shared"]:
            raise ValueError(f"{_title(name)} is not an ordinary shared mission")
        expected = [self._fname_hex(x) for x in _load_catalog()[name].get("exits") or []]
        fact = row["exit"]
        if fact is None or fact[0] == 0:
            selected = "0" * 16
        elif fact[0] == 3 and fact[1]:
            selected = fact[1]
        else:
            raise ValueError(f"{_title(name)} has an unexpected exit state")
        if row["exit_names"] != expected or expected.count(selected) != 1:
            raise ValueError(f"{_title(name)} has an unreviewed or ambiguous exit")

    def _check_record(self, row: dict[str, Any]) -> None:
        record, storage = row["record"], row["storage"]
        vt = self.u64(record)
        if (
            self.u64(vt + 0xF8) != self.base + _VT_RECORD_SLOT_F8
            or self.u64(vt + 0x110) != self.base + _VT_RECORD_SLOT_110
        ):
            raise RuntimeError("Mission record callbacks differ from the supported build")
        if self.u64(record + 0xA8) != storage or self.read(storage, 1) == b"\0":
            raise RuntimeError("Mission storage is no longer valid")

    def reset(self, row: dict[str, Any]) -> None:
        self._check_record(row)
        fn = C.CFUNCTYPE(None, C.c_void_p, C.c_uint8, C.c_bool)(self.base + _FN_STORAGE_STATUS)
        fn(row["storage"], _STATUS_AVAILABLE, False)

    def complete(self, row: dict[str, Any]) -> None:
        self._check_record(row)
        fn = C.CFUNCTYPE(None, C.c_void_p, C.c_uint8, C.c_bool)(self.base + _FN_RECORD_STATUS)
        fn(row["record"], _STATUS_COMPLETE, False)

    def accept(self, name: str, row: dict[str, Any], pc: Any) -> None:
        raw = row["token"]
        token = unrealsdk.make_struct(
            "/Script/CoreUObject.SToken",
            Hash=struct.unpack("<i", raw[:4])[0],
            Name=name,
        )
        if self.read(token._get_address(), 12) != raw:
            raise RuntimeError(f"{_title(name)} token mismatch")
        ps = getattr(pc, "PlayerState", None)
        if ps is None:
            raise RuntimeError("Boost target has no PlayerState")
        pc.ServerActivateMission(token, 1, True, int(ps.StableIndex))


def _engine() -> _Native:
    global _native
    if _native is None:
        _native = _Native()
    return _native


# --- travel checkpoint repairs (facts; no native offsets) -------------------


def _parent_status_fact(fact: str) -> str:
    parts = fact.split(".")
    return ".".join(parts[:3] + ["Status"])


def _repair_checkpoint(cp: dict[str, str]) -> str:
    """Return 'repaired', 'already', 'parent' (parent unfinished) or 'unexpected'."""
    from .lobby_facts import read_fact, write_name_fact

    parent, _v = read_fact(_parent_status_fact(cp["fact"]))
    if parent != "completed":
        return "parent"
    before, _v = read_fact(cp["fact"])
    if before == "completed":
        return "already"
    if before != "none":
        return "unexpected"
    write_name_fact(cp["fact"], "Completed")
    after, _v = read_fact(cp["fact"])
    return "repaired" if after == "completed" else "unexpected"


def repair_travel(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mark travel checkpoints done for missions the host already finished."""
    counts = {"repaired": 0, "already": 0, "parent": 0, "unexpected": 0}
    errors: list[str] = []
    for cp in _travel_checkpoints():
        try:
            counts[_repair_checkpoint(cp)] += 1
        except Exception as exc:
            errors.append(f"{cp.get('key')}: {exc}")
    msg = (
        f"Travel unlocks: repaired {counts['repaired']}, already OK {counts['already']}, "
        f"waiting on story {counts['parent']}"
    )
    if counts["unexpected"] or errors:
        msg += f", skipped {counts['unexpected'] + len(errors)}"
    _log(msg + (f" errors={errors[:3]}" if errors else ""))
    return {"ok": not errors, "message": msg + ".", **counts}


# --- job ---------------------------------------------------------------------


def _resolve_target(job: dict[str, Any]) -> Any:
    from mods_base import get_pc

    identity = job.get("identity")
    if identity is None:
        return get_pc()
    from .uvhm_progression import resolve_lobby_pc

    return resolve_lobby_pc(identity)


def _busy_reason() -> str:
    try:
        from . import uvhm_runtime

        st = uvhm_runtime.status()
        if st.get("running") or st.get("queued"):
            return "UVHM"
    except Exception:
        pass
    try:
        from . import challenge_bulk_runtime

        st = challenge_bulk_runtime.status()
        if st.get("running") or st.get("queued"):
            return "bulk challenges"
    except Exception:
        pass
    return ""


def is_running() -> bool:
    return _job is not None and _job.get("state") == "running"


def _needs_guest_credit(host: Any, identity: Any) -> bool:
    """Host completion says nothing about a visitor's saved campaign."""
    from .uvhm_progression import _pc_matches_identity, snapshot_lobby_identities

    if identity is not None and not _pc_matches_identity(host, identity):
        return True
    return any(
        not _pc_matches_identity(host, player)
        for player in snapshot_lobby_identities()
    )


def start(
    scope: str,
    player_index: int,
    *,
    redo_completed: bool = False,
    mission_names: list[str] | None = None,
) -> dict[str, Any]:
    global _job, _sticky_until
    scope = _scope_key(scope)
    if scope not in SCOPES:
        return {"ok": False, "message": f"Unknown mission scope {scope!r}."}
    if is_running():
        return {"ok": False, "message": "A mission job is already running — cancel it first."}
    busy = _busy_reason()
    if busy:
        return {"ok": False, "message": f"Wait for {busy} to finish first."}
    try:
        from .lobby_facts import host_pc

        host = host_pc()
        engine = _engine()
        engine.world_addr = 0
        snap = engine.snapshot()
    except Exception as exc:
        return {"ok": False, "message": f"Missions unavailable: {exc}"}
    rows = snap["rows"]
    catalog = _load_catalog()
    if scope == "current":
        if len(snap["tracked"]) != 1:
            return {"ok": False, "message": "Track exactly one story/side/DLC mission first."}
        names = list(snap["tracked"])
    else:
        names = [n for n, r in catalog.items() if scope == "all" or r.get("category") == scope]
    if mission_names is not None:
        selected = list(dict.fromkeys(str(name) for name in mission_names))
        if not selected or any(
            name not in catalog or catalog[name].get("category") != "side"
            for name in selected
        ):
            return {"ok": False, "message": "The requested Grassroots mission is not a catalogued side mission."}
        names = selected
    names = _ordered_mission_names([n for n in names if n not in _NONPERSISTENT])
    identity = None
    who = "host"
    if int(player_index) >= 0:
        try:
            from .uvhm_progression import selected_lobby_identity

            identity = selected_lobby_identity(int(player_index))
            who = identity.display_name
        except Exception as exc:
            return {"ok": False, "message": f"Boost target unavailable: {exc}"}
    initial = {n for n in names if (rows.get(n) or {}).get("status") == "completed"}
    try:
        guest_credit = scope != "current" and _needs_guest_credit(host, identity)
    except Exception as exc:
        return {"ok": False, "message": f"Could not confirm mission guest credit targets: {exc}"}
    world_path = str(snap.get("world_path") or "")
    world_label = "base world" if world_path == _BASE_WORLD_PATH else (world_path.rsplit("/", 1)[-1] or "gameplay world")
    _job = {
        "scope": scope,
        "pending": names,
        "current": None,
        "phase": "prepare",
        "redo": bool(redo_completed or guest_credit),
        "guest_credit": bool(guest_credit),
        "repair_checked": set(),
        "initial_completed": initial,
        "identity": identity,
        "who": who,
        "world_path": world_path,
        "done": [],
        "already": [],
        "repaired": [],
        "blocked": [],
        "results": [],
        "result_names": set(),
        "verify": None,
        "pause_reason": "",
        "stall_since": None,
        "total": len(names),
        "state": "running",
        "message": (
            f"Queued {len(names)} mission(s) · {SCOPE_LABELS[scope]} · "
            f"accept as {who} · {world_label}"
            + (" · replaying host-completed missions for guest credit" if guest_credit else "")
        ),
    }
    _sticky_until = 0.0
    try:
        from . import hold_session

        hold_session.arm_for_job("missions")
    except Exception:
        pass
    _log(_job["message"])
    return {"ok": True, "message": _job["message"], **status()}


def start_grassroots_turnin(player_index: int) -> dict[str, Any]:
    """Replay one real Grassroots side mission after bulk challenge completion."""
    try:
        raw = read_data_json("grassroots_missions.json", {})
        mission_defs = [str(name) for name in raw.get("mission_defs", []) if str(name)]
        catalog = _load_catalog()
        snap = _engine().snapshot()
        rows = snap["rows"]
    except Exception as exc:
        return {"ok": False, "message": f"Grassroots side mission unavailable: {exc}"}

    # Prefer an already completed, ordinary mission so the run can exercise a
    # genuine accept/turn-in cycle. Fall back to an available one for fresh saves.
    candidates = [
        name for name in mission_defs
        if name in catalog and catalog[name].get("category") == "side"
        and name not in _NONPERSISTENT
    ]
    for wanted in ("completed", "available", "active", "accepted"):
        for name in candidates:
            row = rows.get(name)
            if not row or row.get("status") != wanted:
                continue
            try:
                _engine().check_row(name, row)
            except Exception:
                continue
            return start("side", player_index, redo_completed=True, mission_names=[name])
    return {
        "ok": False,
        "message": "No supported Grassroots side mission is available to accept and turn in.",
    }


def _finish(state: str, message: str) -> None:
    global _sticky_until
    if _job is None:
        return
    _job["state"] = state
    _job["message"] = message
    _job["current"] = None
    _sticky_until = time.monotonic() + _STICKY_SEC
    try:
        from . import hold_session

        hold_session.release_job("missions")
    except Exception:
        pass
    _log(message)


def cancel() -> bool:
    if not is_running():
        return False
    _finish("cancelled", "Mission job cancelled — finished missions stay finished.")
    return True


def status() -> dict[str, Any]:
    if _job is None:
        return {"active": False, "running": False, "phase": "idle", "message": "No mission job.", "index": 0, "total": 0}
    running = _job["state"] == "running"
    shown = running or time.monotonic() < _sticky_until
    counts = _result_counts(_job)
    done = counts["completed"] + counts["already_completed"]
    out = {
        "active": shown,
        "running": running,
        "phase": _job["state"] if not running else "running",
        "message": _job["message"],
        "index": done,
        "total": _job["total"],
        "completed": counts["completed"],
        "already": counts["already_completed"],
        "locked": counts["locked"],
        "unsupported": counts["unsupported"],
        "blocked_count": counts["blocked"],
        "failed": counts["failed"],
        "uncertain": sum(1 for row in _job["results"] if row.get("uncertain")),
        "results": [dict(row) for row in _job["results"][-80:]],
        "pause_reason": _job.get("pause_reason") or "",
        "world_path": _job.get("world_path") or "",
        "save_persistence": "unverified_until_save_reload",
        "guest_credit": bool(_job.get("guest_credit")),
        "repaired": list(_job["repaired"]),
    }
    if _job["blocked"]:
        out["blocked"] = list(_job["blocked"][:40])
    return out


def _pick_next(rows: dict[str, Any]) -> bool:
    """Move the next eligible mission into ``current``; settle finished ones."""
    job = _job
    assert job is not None
    keep: list[str] = []
    picked = None
    for name in job["pending"]:
        if picked is not None:
            keep.append(name)
            continue
        st = (rows.get(name) or {}).get("status")
        if st == "completed":
            if name in job["initial_completed"] and job["redo"]:
                picked = name
                continue
            if name in job["initial_completed"]:
                _record_result(
                    name,
                    "already_completed",
                    "Game snapshot already reported completed before this run.",
                    before="completed",
                    after="completed",
                )
            else:
                _record_result(
                    name,
                    "completed",
                    "Game snapshot reported completed while processing prerequisites.",
                    after="completed",
                )
            continue
        parent = _SIDE_CHAIN_PARENTS.get(name)
        repair_chain = (
            name in rows and st in (None, "locked") and parent is not None
            and (rows.get(parent) or {}).get("status") == "completed"
        )
        if st in _ELIGIBLE or repair_chain:
            picked = name
            continue
        keep.append(name)
    job["pending"] = keep
    if picked is None:
        return False
    job["current"] = picked
    job["phase"] = "prepare"
    job["stall_since"] = None
    return True


def _stalled_repair() -> bool:
    """One gated travel-checkpoint repair while missions wait. True if one was written."""
    job = _job
    assert job is not None
    for cp in _travel_checkpoints():
        key = cp.get("key")
        if key not in _BATCH_REPAIRS or key in job["repaired"]:
            continue
        result = _repair_checkpoint(cp)
        if result == "repaired":
            job["repaired"].append(key)
            job["message"] = f"Repaired travel requirement {key} — rechecking locked missions…"
            _log(job["message"])
            return True
        if result in ("already", "unexpected"):
            job["repaired"].append(key)
    return False


def _final_repair() -> bool:
    """Check every scoped checkpoint, one per tick, even without a stall."""
    job = _job
    assert job is not None
    checked = job.setdefault("repair_checked", set())
    scoped = set(job["initial_completed"]) | set(job["done"]) | set(job["already"])
    for cp in _travel_checkpoints():
        key = cp["key"]
        if key in checked or cp.get("parent") not in scoped:
            continue
        result = _repair_checkpoint(cp)
        if result not in ("repaired", "already"):
            raise RuntimeError(f"Travel requirement {key} could not be confirmed ({result})")
        checked.add(key)
        if result == "repaired" and key not in job["repaired"]:
            job["repaired"].append(key)
        job["message"] = f"Travel requirement {key}: {result}"
        return True
    return False


def _finish_verified_operation(name: str, verify: dict[str, Any], got: str | None) -> None:
    """Apply state-machine progress only after the settle snapshot agrees."""
    job = _job
    assert job is not None
    op = str(verify["operation"])
    before = verify.get("before")
    if op == "complete":
        _record_result(
            name,
            "completed",
            "Game mission record reported completed on the settle snapshot.",
            before=before,
            after=got,
            operation=op,
        )
        job["current"] = None
        job["phase"] = "prepare"
        job["message"] = f"{_title(name)} verified completed ({len(job['done'])}/{job['total']})"
    elif op == "accept" and got == "completed":
        _record_result(
            name,
            "completed",
            "Game completed the mission during acceptance; no completion write was issued.",
            before=before,
            after=got,
            operation=op,
        )
        job["current"] = None
        job["phase"] = "prepare"
        job["message"] = f"{_title(name)} verified completed during accept"
    else:
        if op == "reset":
            job["initial_completed"].discard(name)
        job["phase"] = str(verify["next_phase"])
        job["message"] = f"{_title(name)}: {op} verified ({got})"
    job["verify"] = None
    job.pop("issued", None)


def _step() -> None:
    job = _job
    assert job is not None
    engine = _engine()
    snap = engine.snapshot()
    rows = snap["rows"]
    pc = _resolve_target(job)
    if pc is None or getattr(pc, "PlayerState", None) is None:
        if job.get("current"):
            _record_result(
                str(job["current"]),
                "blocked",
                "Boost target left the lobby before the operation could be confirmed.",
            )
        _finish("stopped", "Boost target left the lobby — mission job stopped.")
        return

    verify = job.get("verify")
    if verify:
        name = str(verify["name"])
        after = rows.get(name)
        got = (after or {}).get("status")
        if got not in tuple(verify["want"]):
            raise RuntimeError(
                f"{_title(name)}: {verify['operation']} did not remain confirmed "
                f"(status {got}) — not retrying"
            )
        _finish_verified_operation(name, verify, got)
        # The fresh snapshot verified the previous tick. Continue to select or
        # issue the next operation, still at most one native write this tick.

    if job["current"] is None:
        if not _pick_next(rows):
            if not job["pending"]:
                if _final_repair():
                    return
                counts = _result_counts(job)
                _finish(
                    "complete",
                    f"Missions done · verified {counts['completed']}, already completed "
                    f"{counts['already_completed']}, unsupported {counts['unsupported']}. "
                    "Save persistence still requires a normal save/reload.",
                )
                return
            if _stalled_repair():
                job["stall_since"] = None
                return
            now = time.monotonic()
            if job["stall_since"] is None:
                job["stall_since"] = now
            waited = now - job["stall_since"]
            job["message"] = f"{len(job['pending'])} mission(s) still locked — waiting for the story to unlock them…"
            if waited >= _STALL_LIMIT:
                for pending_name in list(job["pending"]):
                    pending_status = (rows.get(pending_name) or {}).get("status")
                    if pending_status in ("locked", "available", None):
                        outcome = "locked"
                        reason = (
                            "Prerequisites remained locked after the guarded wait; nothing was forced."
                        )
                    elif pending_status == "failed":
                        outcome = "failed"
                        reason = "The game mission record reported failed."
                    else:
                        outcome = "blocked"
                        reason = f"Mission could not proceed from observed state {pending_status!r}."
                    _record_result(
                        pending_name,
                        outcome,
                        reason,
                        before=pending_status,
                        after=pending_status,
                    )
                _finish(
                    "stopped",
                    f"Stopped · completed {len(job['done'])}, already done {len(job['already'])}, "
                    f"{len(job['pending'])} still locked (prerequisites not met — nothing was forced).",
                )
            return

    name = job["current"]
    row = rows.get(name)
    if row is None:
        job["pending"].append(name)
        job["current"] = None
        return
    try:
        engine.check_row(name, row)
    except ValueError as exc:
        _record_result(
            name,
            "unsupported",
            str(exc),
            before=(row or {}).get("status"),
        )
        job["current"] = None
        job["message"] = f"Skipped unsupported mission: {_title(name)}"
        return
    st = row["status"]
    phase = job["phase"]
    redo_this = job["redo"] and name in job["initial_completed"]
    if st == "completed" and not (phase == "prepare" and redo_this):
        _record_result(
            name,
            "completed",
            "Game snapshot reported completed before another write was needed.",
            before=st,
            after=st,
        )
        job["current"] = None
        job["message"] = f"{_title(name)} verified completed ({len(job['done'])}/{job['total']})"
        return
    parent = _SIDE_CHAIN_PARENTS.get(name)
    repair_chain = (
        st in (None, "locked") and parent is not None
        and (rows.get(parent) or {}).get("status") == "completed"
    )
    if st == "completed" or repair_chain:
        op = "reset"
    elif st in ("active", "accepted"):
        op = "complete"
    elif st == "available" and phase in ("prepare", "accept"):
        op = "accept"
    else:
        raise ValueError(f"{_title(name)} changed outside this job ({st}) — stopped")

    before = st
    _log(
        f"operation={op} mission={name} title={_title(name)} before={st} "
        f"settled={len(job['done']) + len(job['already'])}/{job['total']} "
        f"guest_credit={bool(job.get('guest_credit'))}"
    )
    job["issued"] = op
    if op == "reset":
        engine.reset(row)
        # A few mission records (notably The Final Quarrel) settle directly
        # into Accepted after the storage-status reset. That is already a
        # valid state for the normal verified completion path; demanding an
        # intermediate Available snapshot would stop the whole Give everything
        # chain before challenges and UVHM can run.
        want, next_phase = ("available", "accepted", "active", "completed"), "accept"
    elif op == "accept":
        engine.accept(name, row, pc)
        want, next_phase = ("accepted", "active", "completed"), "complete"
    else:
        engine.complete(row)
        want, next_phase = ("completed",), "prepare"
    after = engine.snapshot()["rows"].get(name)
    got = (after or {}).get("status")
    if got not in want:
        raise RuntimeError(f"{_title(name)}: {op} did not take (status {got}) — not retrying")
    job["verify"] = {
        "name": name,
        "operation": op,
        "before": before,
        "first_after": got,
        "want": tuple(want),
        "next_phase": next_phase,
    }
    job["message"] = f"{_title(name)}: {op} observed ({got}); confirming…"
    _log(job["message"])


def runtime_tick(*_args: Any, **_kwargs: Any) -> None:
    global _last_step_at
    if not is_running():
        return
    now = time.monotonic()
    if now - _last_step_at < _STEP_GAP:
        return
    try:
        from .serial_rewards import _serial_mail_join_quiet

        if _serial_mail_join_quiet():
            if _job is not None:
                _job["pause_reason"] = "guest_join_leave"
                _job["message"] = "Paused for guest join/leave — resuming after settle…"
            return
    except Exception:
        pass
    try:
        from .session_guards import session_safe

        if not session_safe():
            if _job is not None:
                _job["pause_reason"] = "session_not_safe"
                _job["message"] = "Paused until the lobby and world are stable…"
            return
    except Exception:
        pass
    busy = _busy_reason()
    if busy:
        if _job is not None:
            _job["pause_reason"] = busy.casefold().replace(" ", "_")
            _job["message"] = f"Paused for {busy} — resuming when it finishes…"
        return
    if _job is not None:
        _job["pause_reason"] = ""
    _last_step_at = now
    try:
        _step()
    except Exception as exc:
        issued = bool(_job and _job.get("issued"))
        if _job and _job.get("current"):
            name = str(_job["current"])
            verify = _job.get("verify") or {}
            _record_result(
                name,
                "failed",
                str(exc),
                before=verify.get("before"),
                after=None,
                operation=str(_job.get("issued") or "") or None,
                uncertain=issued,
            )
        if _job:
            _job.pop("issued", None)
            _job["verify"] = None
        prefix = "Uncertain result" if issued else "Stopped"
        _finish("stopped", f"{prefix}: {exc}")


def preview(scope: str) -> dict[str, Any]:
    scope = _scope_key(scope or "all")
    if scope not in SCOPES:
        return {"ok": False, "message": f"Unknown mission scope {scope!r}."}
    try:
        snap = _engine().snapshot()
    except Exception as exc:
        return {"ok": False, "message": f"Missions unavailable: {exc}"}
    rows = snap["rows"]
    if scope == "current":
        names = list(snap["tracked"])
    else:
        names = [n for n, r in _load_catalog().items() if scope == "all" or r.get("category") == scope]
    counts: dict[str, int] = {}
    for n in names:
        st = (rows.get(n) or {}).get("status") or "not loaded"
        counts[st] = counts.get(st, 0) + 1
    parts = ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    tracked = ", ".join(_title(n) for n in snap["tracked"]) or "none"
    world_path = str(snap.get("world_path") or "")
    world_label = "base world" if world_path == _BASE_WORLD_PATH else (world_path.rsplit("/", 1)[-1] or "gameplay world")
    msg = (
        f"{SCOPE_LABELS[scope]}: {len(names)} mission(s) — {parts or 'none'}. "
        f"Tracked: {tracked}. World: {world_label}."
    )
    return {
        "ok": True,
        "message": msg,
        "counts": counts,
        "tracked": [_title(n) for n in snap["tracked"]],
        "world_path": world_path,
    }


def clear_runtime_state() -> None:
    """World teardown: drop cached pointers; a running job stops."""
    global _native
    if is_running():
        _finish("stopped", "World changed — mission job stopped.")
    _native = None
