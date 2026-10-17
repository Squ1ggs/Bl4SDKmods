"""Nonblocking UVHM rank 1-7 progression.

The state machine owns only primitive target identities.  Unreal objects are
resolved for one tick and then discarded; callers must drive :meth:`tick` from
the game thread (for example, an existing UI/HUD tick), never a Python thread.

``Challenge_UVH_Rankup_1_Trait`` exists in the current catalog with a 100,000
goal, but it is deliberately *not* part of rank 1.  The supplied progression
sequence names Firmware, BMVM, and TrueBoss as the rank-1 objectives.  Treating
Trait as another prerequisite without evidence would invent game behaviour.

Current NCS challenge data proves ranks 6 and 7 are each a single direct
rank-up challenge (rather than an objective list plus a separate final):
Bloomreaper unlocks rank 6, and the Subjugator/Thol parent fact unlocks rank 7.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Protocol, Sequence


# The supplied, field-tested command list uses exactly +1 for every objective
# and final token.  Larger catalog-scaled amounts are not equivalent here.
OBJECTIVE_INCREMENT = 1
PRE_FINAL_GRACE_POLLS = 8
POST_FINAL_GRACE_POLLS = 16
RANK_ACTIVATION_GRACE_POLLS = 20
# Rank-up objective challenges each have a one-count goal. Wait for the guest's
# challenge-complete state to replicate before advancing the rank sequence.
OBJECTIVE_VERIFY_POLLS = 40
# Remote reads are not authoritative. Keep a paced +1 sequence rather than
# repeating the same stale read for 6.4 seconds per objective.
GUEST_OBJECTIVE_GRACE_POLLS = 8
# Empty polls after finishing one lobby player before resolving the next PC.
BETWEEN_TARGET_BREATHE_POLLS = 18
TRAIT_CATALOG_ONLY = "Challenge_UVH_Rankup_1_Trait"


@dataclass(frozen=True)
class Stage:
    rank: int
    objectives: tuple[str, ...]
    final: str


STAGES: tuple[Stage, ...] = (
    Stage(
        1,
        (
            "Challenge_UVH_Rankup_1_Firmware",
            "Challenge_UVH_Rankup_1_BMVM",
            "Challenge_UVH_Rankup_1_TrueBoss",
        ),
        "UVH_Rankup_1_FinalChallenge",
    ),
    Stage(
        2,
        (
            "Challenge_UVH_Rankup_2_Kratch",
            "Challenge_UVH_Rankup_2_Creep",
            "Challenge_UVH_Rankup_2_Order",
            "Challenge_UVH_Rankup_2_Ripper",
        ),
        "UVH_Rankup_2_FinalChallenge",
    ),
    Stage(
        3,
        (
            "Challenge_UVH_Rankup_3_Cat",
            "Challenge_UVH_Rankup_3_Pangolin",
            "Challenge_UVH_Rankup_3_Order",
            "Challenge_UVH_Rankup_3_Ripper",
        ),
        "UVH_Rankup_3_FinalChallenge",
    ),
    Stage(
        4,
        (
            "Challenge_UVH_Rankup_4_Beast",
            "Challenge_UVH_Rankup_4_Order",
            "Challenge_UVH_Rankup_4_Ripper",
            "Challenge_UVH_Rankup_4_Thresher",
        ),
        "UVH_Rankup_4_FinalChallenge",
    ),
    Stage(
        5,
        (
            "Challenge_UVH_Rankup_5_GL",
            "Challenge_UVH_Rankup_5_MOU",
            "Challenge_UVH_Rankup_5_SL",
        ),
        "UVH_Rankup_5_FinalChallenge",
    ),
    Stage(6, (), "Challenge_UVH_Rankup_6_Bloomreaper"),
    Stage(7, (), "Challenge_UVH_Rankup_7_Parent"),
)


def _catalog_validation_error() -> Optional[str]:
    from .data_files import read_data_json  # noqa: PLC0415

    raw = read_data_json("challenge_catalog.json", default=None)
    if raw is None:
        return "challenge catalog is unavailable (data/challenge_catalog.json missing)"
    rows = (raw.get("challenges") or raw.get("rows")) if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return "challenge catalog has no rows list"
    known = {
        str(row.get("token") or "")
        for row in rows
        if isinstance(row, dict) and str(row.get("token") or "")
    }
    required = {token for stage in STAGES for token in (*stage.objectives, stage.final)}
    missing = sorted(required - known)
    if missing:
        return f"challenge catalog is missing required UVHM tokens: {', '.join(missing)}"
    return None


CATALOG_VALIDATION_ERROR = _catalog_validation_error()


def _uobject_addr(obj: Any) -> int:
    if obj is None:
        return 0
    try:
        addr = int(obj._get_address() or 0)
    except Exception:
        return 0
    if addr <= 0 or addr == 0xFFFFFFFFFFFFFFFF:
        return 0
    if addr >= 0xFFFF000000000000:
        return 0
    return addr


def _uobject_live(obj: Any) -> bool:
    """Reject poison / freed wrappers before ForceNet / UI poke (0xffffffff AV)."""
    return bool(_uobject_addr(obj))


def read_vault_hunter_level(pc: Any) -> Optional[int]:
    """Return VaultHunterLevel only when it is a sane UVHM rank (0..7).

    Remote/guest PlayerState often exposes junk or stale values outside that
    range; treating those as ``>= 7`` made UVHM finish in one tick.
    """
    if pc is None or not _uobject_live(pc):
        return None
    try:
        ps = getattr(pc, "PlayerState", None)
    except Exception:
        return None
    if ps is None or not _uobject_live(ps):
        return None
    try:
        value = getattr(ps, "VaultHunterLevel", None)
    except Exception:
        return None
    if value is None:
        return None
    try:
        level = int(value)
    except (TypeError, ValueError):
        return None
    if level < 0 or level > len(STAGES):
        return None
    return level


def _pc_is_local_host(pc: Any) -> bool:
    try:
        from mods_base import get_pc

        local = get_pc()
    except Exception:
        return False
    if local is None or pc is None:
        return False
    try:
        if pc is local:
            return True
    except Exception:
        pass
    try:
        return getattr(local, "PlayerState", None) is getattr(pc, "PlayerState", None)
    except Exception:
        return False


def _pc_matches_identity(pc: Any, identity: TargetIdentity) -> bool:
    if pc is None or identity is None:
        return False
    try:
        from .party_helpers import _gbc_resolve_player_display_name

        ps = getattr(pc, "PlayerState", None)
        if ps is None or not _uobject_live(ps):
            return False
        name = _gbc_resolve_player_display_name(ps)
        if _player_state_key(ps, name) == identity.key:
            return True
        # Soft match after join UniqueId churn — never accept a different player.
        want = str(getattr(identity, "display_name", "") or "").strip().casefold()
        have = str(name or "").strip().casefold()
        return bool(want and have and want == have)
    except Exception:
        return False


def nudge_uvhm_client_ui(pc: Any) -> None:
    """Push UVHM / challenge state to a player's client so the pause menu refreshes.

    Remotes often keep a stale UVHM screen until they toggle menu/game/menu.
    Host listen-server: ForceNet + OnRep poke + progression UI collectors.
    Safe no-op if APIs are missing.
    """
    if pc is None or not _uobject_live(pc):
        return
    # find_all + ForceNet during lobby join churn is a common null+0x70 AV.
    try:
        from .serial_rewards import _serial_mail_join_quiet

        if _serial_mail_join_quiet():
            return
    except Exception:
        pass
    try:
        ps = getattr(pc, "PlayerState", None)
    except Exception:
        ps = None
    if ps is not None and not _uobject_live(ps):
        ps = None
    # Re-touch VaultHunterLevel so OnRep can fire for connected clients.
    if ps is not None:
        try:
            cur = getattr(ps, "VaultHunterLevel", None)
            if cur is not None:
                setattr(ps, "VaultHunterLevel", int(cur))
        except Exception:  # noqa: BLE001
            pass
    try:
        mgr = getattr(pc, "OakChallengeManager", None)
    except Exception:
        mgr = None
    if mgr is not None and not _uobject_live(mgr):
        mgr = None
    for obj in (ps, pc, mgr):
        if obj is None or not _uobject_live(obj):
            continue
        for name in (
            "FlushNetDormancy",
            "ForceNetUpdate",
            "MarkDirtyForReplication",
        ):
            fn = getattr(obj, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    continue
        for name in (
            "OnRep_VaultHunterLevel",
            "OnRep_ChallengeObjectiveStates",
            "OnRep_GbxProgression",
            "OnRep_ReplicatedPlayerStats",
        ):
            fn = getattr(obj, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    continue
    # Zero-arg Client* RPCs on a remote PC ship default/null params to the guest.
    client_rpcs = () if not _pc_is_local_host(pc) else (
        "ClientIncrementChallengeForPlayer",
        "ClientCompleteChallenge",
        "ClientUpdateChallengeProgress",
        "ClientRefreshChallengeUI",
        "ClientNotifyChallengeUpdated",
    )
    for name in client_rpcs:
        if not _uobject_live(pc):
            return
        fn = getattr(pc, name, None)
        if not callable(fn):
            continue
        try:
            fn()
        except TypeError:
            continue
        except Exception:  # noqa: BLE001
            continue
    # Progression collectors owned by this PC (same idea as Mayhem UI nudge).
    try:
        import unrealsdk

        pc_name = str(getattr(pc, "Name", "") or "").lower()
        for cls in (
            "OakUIDataCollector_Progression",
            "OakUIDataCollector_PlayerStats",
            "OakUIDataCollector_Challenges",
        ):
            try:
                items = list(unrealsdk.find_all(cls, False) or [])
            except Exception:  # noqa: BLE001
                items = []
            for coll in items[:80]:
                if coll is None or not _uobject_live(coll):
                    continue
                try:
                    outer = getattr(coll, "Outer", None)
                    path = str(
                        getattr(coll, "PathName", None) or getattr(coll, "Name", "") or ""
                    ).lower()
                except Exception:
                    continue
                if outer is not pc and not (pc_name and pc_name in path):
                    continue
                for meth in ("Refresh", "RefreshData", "UpdateData", "RequestRefresh", "Collect"):
                    fn = getattr(coll, meth, None)
                    if not callable(fn):
                        continue
                    try:
                        fn()
                        break
                    except Exception:  # noqa: BLE001
                        continue
    except Exception:  # noqa: BLE001
        pass


@dataclass(frozen=True)
class TargetIdentity:
    """Stable, serializable player identity; never contains a UObject."""

    key: str
    display_name: str


class Phase(str, Enum):
    IDLE = "idle"
    READY = "ready"
    INCREMENT_OBJECTIVE = "increment_objective"
    WAIT_OBJECTIVE = "wait_objective"
    INCREMENT_FINAL = "increment_final"
    WAIT_FINAL = "wait_final"
    VERIFY_RANK = "verify_rank"
    BREATHE = "breathe"
    CANCELLED = "cancelled"
    COMPLETE = "complete"
    ERROR = "error"


class ProgressionBackend(Protocol):
    """One backend method is invoked per tick after target resolution."""

    def readiness_error(self, pc: Any) -> Optional[str]: ...

    def increment(self, pc: Any, token: str, amount: int) -> bool: ...

    def is_complete(self, pc: Any, token: str) -> Optional[bool]: ...

    def is_rank_active(self, pc: Any, rank: int) -> Optional[bool]: ...


@dataclass(frozen=True)
class ProgressionStatus:
    phase: Phase
    running: bool
    target_mode: str
    target_number: int
    target_count: int
    target_name: str
    rank: int
    token: str
    poll_count: int
    settle_grace: int
    message: str
    results: tuple[str, ...]


class UVHMProgression:
    """Game-thread, one-operation-per-tick UVHM 1-7 progression controller."""

    def __init__(
        self,
        resolve_pc: Callable[[TargetIdentity], Any],
        backend: ProgressionBackend,
        *,
        max_polls: int = 300,
    ) -> None:
        self._resolve_pc = resolve_pc
        self._backend = backend
        self._max_polls = max(1, int(max_polls))
        self._targets: tuple[TargetIdentity, ...] = ()
        self._mode = "selected"
        self._target_index = 0
        self._stage_index = 0
        self._objective_index = 0
        self._poll_count = 0
        self._settle_grace = 0
        self._phase = Phase.IDLE
        self._message = "Idle."
        self._cancel_resume_phase: Optional[Phase] = None
        self._results: list[str] = []
        self._max_rank = len(STAGES)

    def start_selected(self, target: TargetIdentity, *, max_rank: int = 7) -> None:
        self._start((target,), "selected", max_rank=max_rank)

    def start_all(
        self,
        targets: Iterable[TargetIdentity],
        *,
        confirmed: bool,
        max_rank: int = 7,
    ) -> None:
        if not confirmed:
            raise ValueError("All-lobby UVHM progression requires explicit confirmation.")
        snapshot = tuple(targets)
        self._start(snapshot, "all", max_rank=max_rank)

    def _start(
        self,
        targets: Sequence[TargetIdentity],
        mode: str,
        *,
        max_rank: int = 7,
    ) -> None:
        if self.running:
            raise RuntimeError("UVHM progression is already running.")
        snapshot = tuple(targets)
        if not snapshot:
            raise ValueError("No target players were selected.")
        if any(not isinstance(t, TargetIdentity) or not t.key for t in snapshot):
            raise ValueError("Every target must have a stable TargetIdentity.")
        keys = [t.key for t in snapshot]
        if len(set(keys)) != len(keys):
            raise ValueError("Target snapshot contains duplicate player identities.")
        self._targets = snapshot
        self._mode = mode
        self._target_index = 0
        self._stage_index = 0
        self._objective_index = 0
        self._poll_count = 0
        self._settle_grace = 0
        self._phase = Phase.READY
        self._message = "Queued; waiting for readiness check."
        self._cancel_resume_phase = None
        self._results = []
        rank = int(max_rank)
        if rank < 1 or rank > len(STAGES):
            raise ValueError(f"max_rank must be between 1 and {len(STAGES)}.")
        self._max_rank = rank

    @property
    def running(self) -> bool:
        return self._phase in {
            Phase.READY,
            Phase.INCREMENT_OBJECTIVE,
            Phase.WAIT_OBJECTIVE,
            Phase.INCREMENT_FINAL,
            Phase.WAIT_FINAL,
            Phase.VERIFY_RANK,
            Phase.BREATHE,
        }

    def acknowledge_complete(self) -> None:
        """Drop leftover COMPLETE after the EXE sticky flash so status stays idle."""
        if self._phase != Phase.COMPLETE:
            return
        self._phase = Phase.IDLE
        self._message = "Idle."
        self._cancel_resume_phase = None

    def cancel(self) -> bool:
        # Do not wipe ERROR/COMPLETE/IDLE into a blank Idle — teardown listeners
        # used to call cancel() and erase the EXE status line immediately.
        if self._phase in (Phase.ERROR, Phase.COMPLETE, Phase.IDLE):
            return False
        if not self.running:
            return False
        self._cancel_resume_phase = self._phase
        self._phase = Phase.CANCELLED
        self._message = "Cancelled safely between native calls."
        return True

    def resume(self) -> bool:
        if self._phase != Phase.CANCELLED or self._cancel_resume_phase is None:
            return False
        self._phase = self._cancel_resume_phase
        self._cancel_resume_phase = None
        self._message = "Resumed."
        return True

    def status(self) -> ProgressionStatus:
        target = self._current_target()
        stage = self._current_stage()
        return ProgressionStatus(
            phase=self._phase,
            running=self.running,
            target_mode=self._mode,
            target_number=min(self._target_index + 1, len(self._targets)),
            target_count=len(self._targets),
            target_name=target.display_name if target else "",
            rank=stage.rank if stage else 0,
            token=self._current_token(),
            poll_count=self._poll_count,
            settle_grace=max(0, int(self._settle_grace or 0)),
            message=self._message,
            results=tuple(self._results),
        )

    def tick(self) -> ProgressionStatus:
        """Perform at most one backend/native operation, then return."""
        if not self.running:
            return self.status()
        if self._phase == Phase.BREATHE:
            self._poll_breathe()
            return self.status()
        target = self._current_target()
        if target is None:
            self._fail("Internal error: no current target.")
            return self.status()

        # Resolve on every tick.  Do not assign this object to controller state.
        try:
            pc = self._resolve_pc(target)
        except Exception as exc:  # noqa: BLE001
            return self._skip_or_fail_unresolvable(
                target, f"Could not resolve {target.display_name}: {exc}"
            )
        if pc is None:
            return self._skip_or_fail_unresolvable(
                target,
                f"Player {target.display_name!r} ({target.key}) is no longer resolvable.",
            )

        try:
            # Reject host-bleed / name-fallback mismatches before any native work.
            if not _pc_matches_identity(pc, target):
                return self._skip_or_fail_unresolvable(
                    target,
                    f"Resolved controller is not {target.display_name} "
                    f"(identity mismatch — refusing UVHM apply).",
                )
            if self._phase == Phase.READY:
                error = self._backend.readiness_error(pc)
                if error:
                    self._fail(f"{target.display_name} is not ready: {error}")
                else:
                    # MAX ALL re-queue after a full 1–7 complete used to re-fire
                    # FinalChallenge on already-maxed players (poison AV).
                    # Guests often show a junk/stale VaultHunterLevel >= 7 while
                    # still at rank 0 — that caused instant fake "complete".
                    if self._should_skip_already_maxed(pc, target):
                        vhl = read_vault_hunter_level(pc)
                        self._results.append(
                            f"skipped-already:{target.display_name}:VHL={vhl}"
                        )
                        self._message = (
                            f"{target.display_name} already at UVHM "
                            f"{self._max_rank} (VHL={vhl}); skipping re-apply."
                        )
                        self._advance_target(completed_max_rank=self._max_rank)
                    else:
                        self._phase = Phase.INCREMENT_OBJECTIVE
                        last = self._results[-1] if self._results else ""
                        check = (
                            f"; rank {self._max_rank} challenge check={last.rsplit('=', 1)[-1]}"
                            if last.startswith(f"vhl-untrusted:{target.display_name}:")
                            else ""
                        )
                        self._message = (
                            f"{target.display_name} is ready "
                            f"(VHL={read_vault_hunter_level(pc)}{check})."
                        )
            elif self._phase == Phase.INCREMENT_OBJECTIVE:
                self._increment(pc, self._current_token(), Phase.WAIT_OBJECTIVE)
            elif self._phase == Phase.WAIT_OBJECTIVE:
                self._poll_complete(pc, self._current_token(), objective=True)
            elif self._phase == Phase.INCREMENT_FINAL:
                self._increment(pc, self._current_token(), Phase.WAIT_FINAL)
            elif self._phase == Phase.WAIT_FINAL:
                self._poll_complete(pc, self._current_token(), objective=False)
            elif self._phase == Phase.VERIFY_RANK:
                self._verify_rank(pc)
        except Exception as exc:  # noqa: BLE001
            self._fail(
                f"{self._phase.value} failed for {target.display_name}: "
                f"{type(exc).__name__}: {exc}"
            )
        finally:
            # Explicitly drop the tick-local UObject reference.
            pc = None
        return self.status()

    def _poll_breathe(self) -> None:
        """Give the game a quiet stretch after finishing one player before the next."""
        self._poll_count += 1
        grace = max(1, min(BETWEEN_TARGET_BREATHE_POLLS, self._max_polls))
        self._settle_grace = grace
        if self._poll_count < grace:
            self._message = (
                f"Letting challenge state settle before next player "
                f"({self._poll_count}/{grace})."
            )
            return
        self._poll_count = 0
        self._phase = Phase.READY
        nxt = self._current_target()
        self._message = (
            f"{nxt.display_name} is next."
            if nxt is not None
            else "Ready."
        )

    def _increment(self, pc: Any, token: str, wait_phase: Phase) -> None:
        if not token:
            self._fail("Internal error: missing challenge token.")
            return
        if wait_phase == Phase.WAIT_OBJECTIVE:
            already_done = self._backend.is_complete(pc, token)
            if already_done is True:
                self._advance_objective(token, already_done=True)
                return
        if not self._backend.increment(pc, token, OBJECTIVE_INCREMENT):
            self._fail(f"Challenge increment was rejected for {token}.")
            return
        self._poll_count = 0
        self._phase = wait_phase
        self._message = f"Sent +1 for {token}; waiting for the target's saved challenge state."

    def _poll_complete(self, pc: Any, token: str, *, objective: bool) -> None:
        # Intermediate one-count objectives are safe to verify. FinalChallenge
        # rank-ups mutate challenge state and remain on the delay + VHL check
        # path because immediate final-token reads can crash the game.
        if objective:
            try:
                complete = self._backend.is_complete(pc, token)
            except Exception:
                complete = None
            if complete is True:
                self._advance_objective(token, already_done=False)
                return
            self._poll_count += 1
            guest_read = getattr(self._backend, "objective_reads_authoritative", None)
            remote_unverified = callable(guest_read) and not guest_read(pc)
            grace = max(1, min(GUEST_OBJECTIVE_GRACE_POLLS if remote_unverified else OBJECTIVE_VERIFY_POLLS, self._max_polls))
            self._settle_grace = grace
            if self._poll_count >= grace:
                # Host-side guest challenge reads are not authoritative (the
                # same restriction applies to ordinary bulk challenges). Keep
                # the field-tested +1 sequence paced, without calling a stale
                # read a verified objective or retrying a rank-up command.
                if remote_unverified:
                    self._results.append(f"objective-unverified:{self.status().target_name}:{token}")
                    self._advance_objective(token, already_done=False)
                    self._message = f"{token}: guest completion read unconfirmed; continuing paced command sequence."
                    return
                detail = "could not read" if complete is None else "did not complete"
                self._fail(
                    f"{token} {detail} for {self.status().target_name} after "
                    f"{grace} checks; UVHM progression stopped before claiming success."
                )
                return
            self._message = (
                f"Waiting for {self.status().target_name}'s {token} to complete "
                f"({self._poll_count}/{grace})."
            )
            return

        stage = self._current_stage()
        assert stage is not None
        # Positive completion AND rank evidence can end the wait early. An
        # unreadable/stale guest result keeps the existing proven grace delay.
        try:
            if self._backend.is_complete(pc, token) is True and self._backend.is_rank_active(pc, stage.rank) is True:
                self._poll_count = 0
                self._phase = Phase.VERIFY_RANK
                self._message = f"{token} and UVHM rank {stage.rank} verified; checking rank before advancing."
                return
        except Exception:
            pass
        self._poll_count += 1
        grace = POST_FINAL_GRACE_POLLS
        grace = max(1, min(grace, self._max_polls))
        self._settle_grace = grace
        if self._poll_count >= grace:
            self._poll_count = 0
            self._phase = Phase.VERIFY_RANK
            self._message = f"Applied {token}; continuing after the proven command delay."
            return
        self._message = f"Allowing {token} to settle ({self._poll_count}/{grace})."

    def _advance_objective(self, token: str, *, already_done: bool) -> None:
        stage = self._current_stage()
        assert stage is not None
        self._poll_count = 0
        self._objective_index += 1
        if self._objective_index < len(stage.objectives):
            self._phase = Phase.INCREMENT_OBJECTIVE
        else:
            self._phase = Phase.INCREMENT_FINAL
        state = "was already complete" if already_done else "is verified complete"
        self._message = f"{token} {state}; continuing UVHM rank {stage.rank}."

    def _verify_rank(self, pc: Any) -> None:
        stage = self._current_stage()
        assert stage is not None
        active = self._backend.is_rank_active(pc, stage.rank)
        verified = active is True
        if not verified:
            self._poll_count += 1
            grace = max(1, min(RANK_ACTIVATION_GRACE_POLLS, self._max_polls))
            self._settle_grace = grace
            if self._poll_count < grace:
                self._message = (
                    f"Waiting after UVHM rank {stage.rank} final command "
                    f"({self._poll_count}/{grace})."
                )
                return

        self._poll_count = 0
        target = self._current_target()
        self._results.append(
            f"{target.display_name if target else 'target'}: UVHM rank {stage.rank} "
            + ("verified" if verified else "commands applied")
        )
        # Guests often keep a stale UVHM menu until they toggle pause — push net + collectors.
        try:
            nudge_uvhm_client_ui(pc)
        except Exception:  # noqa: BLE001
            pass
        if stage.rank >= self._max_rank:
            self._advance_target(completed_max_rank=stage.rank)
            return
        self._stage_index += 1
        self._objective_index = 0
        if self._stage_index < len(STAGES):
            next_stage = STAGES[self._stage_index]
            if next_stage.rank > self._max_rank:
                self._advance_target(completed_max_rank=stage.rank)
                return
            self._phase = (
                Phase.INCREMENT_OBJECTIVE
                if next_stage.objectives
                else Phase.INCREMENT_FINAL
            )
            self._message = (
                f"UVHM rank {stage.rank} {'verified' if verified else 'command sequence applied'}; advancing to rank "
                f"{next_stage.rank}."
            )
            return
        self._advance_target(completed_max_rank=stage.rank)

    def _advance_target(self, *, completed_max_rank: int | None = None) -> None:
        finished = self._current_target()
        # One more UI nudge when leaving this player (esp. remotes / all-lobby).
        try:
            pc = resolve_lobby_pc(finished) if finished is not None else None
            if pc is not None:
                nudge_uvhm_client_ui(pc)
        except Exception:  # noqa: BLE001
            pass
        self._target_index += 1
        self._stage_index = 0
        self._objective_index = 0
        rank_label = (
            f"rank {completed_max_rank}"
            if completed_max_rank is not None and self._max_rank < len(STAGES)
            else "ranks 1-7"
        )
        if self._target_index < len(self._targets):
            self._poll_count = 0
            self._phase = Phase.BREATHE
            self._message = (
                f"Completed {finished.display_name if finished else 'target'} up to {rank_label}; "
                "advancing to the next snapshotted player."
            )
        else:
            self._phase = Phase.COMPLETE
            if self._max_rank < len(STAGES):
                self._message = (
                    f"UVHM up to rank {self._max_rank} completed for every target."
                )
            else:
                self._message = "UVHM ranks 1-7 completed for every target."
            if any(row.startswith("objective-unverified:") for row in self._results):
                self._message = "UVHM command sequence finished; guest objective completion needs save/reload confirmation."


    def _skip_or_fail_unresolvable(self, target: TargetIdentity, reason: str) -> ProgressionStatus:
        """Lobby churn: skip missing remotes and keep the all-lobby job alive."""
        note = str(reason).strip() or f"{target.display_name} is no longer resolvable."
        self._results.append(f"skipped:{target.display_name}:{note}")
        if self._target_index + 1 < len(self._targets):
            self._message = (
                f"Skipped {target.display_name} (left / unresolvable); continuing."
            )
            self._advance_target()
            return self.status()
        self._fail(note)
        return self.status()

    def _should_skip_already_maxed(self, pc: Any, target: TargetIdentity) -> bool:
        """True only when UVHM max rank is confirmed — never trust guest VHL alone."""
        vhl = read_vault_hunter_level(pc)
        if vhl is None or vhl < int(self._max_rank):
            return False
        # Local host VHL is authoritative; remotes need challenge proof.
        if _pc_is_local_host(pc):
            return True
        try:
            final_token = stage_for_rank(int(self._max_rank)).final
        except Exception:
            final_token = STAGES[-1].final if STAGES else ""
        if not final_token:
            return False
        # is_complete can AV on some finals mid-settle — READY is pre-mutate, safer.
        confirmed = self._backend.is_complete(pc, final_token)
        if confirmed is True:
            return True
        # Remote VHL says maxed but rank-up challenge is incomplete/unknown → run it.
        self._results.append(
            f"vhl-untrusted:{target.display_name}:VHL={vhl}:"
            f"rank{self._max_rank}_complete={confirmed!r}"
        )
        return False

    def _fail(self, message: str) -> None:
        self._phase = Phase.ERROR
        self._message = str(message)

    def _current_target(self) -> Optional[TargetIdentity]:
        if 0 <= self._target_index < len(self._targets):
            return self._targets[self._target_index]
        return None

    def _current_stage(self) -> Optional[Stage]:
        if 0 <= self._stage_index < len(STAGES):
            return STAGES[self._stage_index]
        return None

    def _current_token(self) -> str:
        stage = self._current_stage()
        if stage is None:
            return ""
        if self._phase in (Phase.INCREMENT_FINAL, Phase.WAIT_FINAL, Phase.VERIFY_RANK):
            return stage.final
        if 0 <= self._objective_index < len(stage.objectives):
            return stage.objectives[self._objective_index]
        return ""


class UnrealChallengeBackend:
    """Minimal live backend using shared challenge_increment helpers.

    Increment prefers OakChallengeBlueprintLibrary with FGameDataHandle, then
    falls back to ServerIncrementChallengeForPlayer. Completion/rank polls still
    use the challenge library CDO resolved per call (never cached).
    """

    @staticmethod
    def _library() -> Any:
        import unrealsdk

        for class_name in (
            "OakChallengeBlueprintLibrary",
            "/Script/OakGame.OakChallengeBlueprintLibrary",
        ):
            try:
                cls = unrealsdk.find_class(class_name)
                cdo = getattr(cls, "ClassDefaultObject", None) if cls is not None else None
                if cdo is not None:
                    return cdo
            except Exception:  # noqa: BLE001
                continue
        return None

    def readiness_error(self, pc: Any) -> Optional[str]:
        if CATALOG_VALIDATION_ERROR:
            return CATALOG_VALIDATION_ERROR
        from .challenge_increment import readiness_error as _challenge_readiness_error

        return _challenge_readiness_error(pc)

    def objective_reads_authoritative(self, pc: Any) -> bool:
        return _pc_is_local_host(pc)

    def increment(self, pc: Any, token: str, amount: int) -> bool:
        from .challenge_increment import increment_challenge

        owner_pc = None
        try:
            from mods_base import get_pc

            owner_pc = get_pc()
        except Exception:  # noqa: BLE001
            owner_pc = None
        return bool(
            increment_challenge(
                pc,
                str(token),
                int(amount),
                owner_pc=owner_pc,
                state_writes=_pc_is_local_host(pc),
                remote_fallback_rpc=not _pc_is_local_host(pc),
            )
        )

    def is_complete(self, pc: Any, token: str) -> Optional[bool]:
        try:
            from .challenge_increment import (
                _handles_for_token,
                _read_complete,
                _read_progress,
            )

            observed_incomplete = False
            for handle in _handles_for_token(str(token))[:2]:
                result = _read_complete(pc, handle)
                if isinstance(result, bool):
                    if result:
                        return True
                    observed_incomplete = True
                    # Rank-up objectives in the game catalog all have a goal
                    # of one. Some guest PlayerStates expose progress before
                    # their complete bit catches up.
                    progress = _read_progress(pc, handle)
                    if isinstance(progress, (int, float)) and progress >= 1:
                        return True
            if observed_incomplete:
                return False
        except Exception:  # noqa: BLE001
            pass
        return None

    def is_rank_active(self, pc: Any, rank: int) -> Optional[bool]:
        value = read_vault_hunter_level(pc)
        if value is None:
            return None
        return int(value) >= int(rank)


def snapshot_lobby_identities() -> tuple[TargetIdentity, ...]:
    """Snapshot current lobby players as primitive identities in lobby order."""
    from .party_helpers import (
        _gbc_resolve_player_display_name,
        _gbc_session_world_and_gamestate,
    )

    _world, gs = _gbc_session_world_and_gamestate()
    players = getattr(gs, "PlayerArray", None) if gs is not None else None
    if players is None:
        return ()
    result: list[TargetIdentity] = []
    for index in range(len(players)):
        ps = players[index]
        if ps is None:
            continue
        name = _gbc_resolve_player_display_name(ps)
        key = _player_state_key(ps, name)
        result.append(TargetIdentity(key=key, display_name=name))
    return tuple(result)


def selected_lobby_identity(player_index: int) -> TargetIdentity:
    """Capture one selected lobby row as a stable identity."""
    from .party_helpers import (
        _gbc_resolve_player_display_name,
        _gbc_session_world_and_gamestate,
    )

    _world, gs = _gbc_session_world_and_gamestate()
    players = getattr(gs, "PlayerArray", None) if gs is not None else None
    try:
        ps = players[int(player_index)]
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Selected lobby player {player_index} is unavailable.") from exc
    name = _gbc_resolve_player_display_name(ps)
    return TargetIdentity(key=_player_state_key(ps, name), display_name=name)


def resolve_lobby_pc(identity: TargetIdentity) -> Any:
    """Re-resolve a snapshotted identity to its current PC; returns no cached object."""
    from mods_base import get_pc

    from .party_helpers import (
        _gbc_find_pc_for_player_state,
        _gbc_find_remote_pc_name_fallback,
        _gbc_resolve_player_display_name,
        _gbc_session_world_and_gamestate,
    )

    world, gs = _gbc_session_world_and_gamestate()
    players = getattr(gs, "PlayerArray", None) if gs is not None else None
    if players is None:
        return None
    for index in range(len(players)):
        ps = players[index]
        if ps is None:
            continue
        name = _gbc_resolve_player_display_name(ps)
        if _player_state_key(ps, name) != identity.key:
            continue
        local = get_pc()
        if local is not None and getattr(local, "PlayerState", None) is ps:
            return local
        pc = _gbc_find_pc_for_player_state(ps, world)
        if pc is not None:
            return pc
        host_ps = getattr(local, "PlayerState", None) if local is not None else None
        return _gbc_find_remote_pc_name_fallback(ps, host_ps, name, "[SQBT]")
    return None


def _player_state_key(ps: Any, display_name: str) -> str:
    """Extract a stable primitive key, falling back to normalized display name."""
    for attr in ("UniqueId", "UniqueNetId", "PlayerId", "PlatformUserId"):
        try:
            value = getattr(ps, attr, None)
            if value is not None:
                text = str(value).strip()
                if text and text.lower() not in {"none", "0"}:
                    return f"{attr}:{text}"
        except Exception:  # noqa: BLE001
            continue
    normalized = "".join(ch for ch in str(display_name).casefold() if ch.isalnum())
    if not normalized:
        raise ValueError("Player has no stable ID or usable display name.")
    return f"name:{normalized}"


def stage_for_rank(rank: int) -> Stage:
    """Return a supported UVHM stage."""
    rank = int(rank)
    for stage in STAGES:
        if stage.rank == rank:
            return stage
    raise ValueError(f"Unsupported UVHM rank {rank}; supported ranks are 1-7.")

