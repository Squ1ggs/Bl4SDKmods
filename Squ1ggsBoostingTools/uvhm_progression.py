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
PRE_FINAL_GRACE_POLLS = 3
POST_FINAL_GRACE_POLLS = 4
RANK_ACTIVATION_GRACE_POLLS = 4
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
        }

    def cancel(self) -> bool:
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
            message=self._message,
            results=tuple(self._results),
        )

    def tick(self) -> ProgressionStatus:
        """Perform at most one backend/native operation, then return."""
        if not self.running:
            return self.status()
        target = self._current_target()
        if target is None:
            self._fail("Internal error: no current target.")
            return self.status()

        # Resolve on every tick.  Do not assign this object to controller state.
        try:
            pc = self._resolve_pc(target)
        except Exception as exc:  # noqa: BLE001
            self._fail(f"Could not resolve {target.display_name}: {exc}")
            return self.status()
        if pc is None:
            self._fail(
                f"Player {target.display_name!r} ({target.key}) is no longer resolvable."
            )
            return self.status()

        try:
            if self._phase == Phase.READY:
                error = self._backend.readiness_error(pc)
                if error:
                    self._fail(f"{target.display_name} is not ready: {error}")
                else:
                    self._phase = Phase.INCREMENT_OBJECTIVE
                    self._message = f"{target.display_name} is ready."
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

    def _increment(self, pc: Any, token: str, wait_phase: Phase) -> None:
        if not token:
            self._fail("Internal error: missing challenge token.")
            return
        if not self._backend.increment(pc, token, OBJECTIVE_INCREMENT):
            self._fail(f"Challenge increment was rejected for {token}.")
            return
        self._poll_count = 0
        self._phase = wait_phase
        self._message = f"Sent proven +1 command for {token}; allowing game processing time."

    def _poll_complete(self, pc: Any, token: str, *, objective: bool) -> None:
        complete = self._backend.is_complete(pc, token)
        self._poll_count += 1
        stage = self._current_stage()
        assert stage is not None
        is_last_objective = (
            objective and self._objective_index + 1 >= len(stage.objectives)
        )
        grace = (
            PRE_FINAL_GRACE_POLLS
            if is_last_objective
            else 1
            if objective
            else POST_FINAL_GRACE_POLLS
        )
        grace = max(1, min(grace, self._max_polls))
        if complete is True or self._poll_count >= grace:
            self._poll_count = 0
            if objective:
                self._objective_index += 1
                if self._objective_index < len(stage.objectives):
                    self._phase = Phase.INCREMENT_OBJECTIVE
                else:
                    self._phase = Phase.INCREMENT_FINAL
            else:
                self._phase = Phase.VERIFY_RANK
            self._message = (
                f"Confirmed completion of {token}."
                if complete is True
                else f"Applied {token}; continuing after the proven command delay."
            )
            return
        self._message = f"Allowing {token} to settle ({self._poll_count}/{grace})."

    def _verify_rank(self, pc: Any) -> None:
        stage = self._current_stage()
        assert stage is not None
        active = self._backend.is_rank_active(pc, stage.rank)
        verified = active is True
        if not verified:
            self._poll_count += 1
            grace = max(1, min(RANK_ACTIVATION_GRACE_POLLS, self._max_polls))
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
        self._target_index += 1
        self._stage_index = 0
        self._objective_index = 0
        rank_label = (
            f"rank {completed_max_rank}"
            if completed_max_rank is not None and self._max_rank < len(STAGES)
            else "ranks 1-7"
        )
        if self._target_index < len(self._targets):
            self._phase = Phase.READY
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
            )
        )

    def is_complete(self, pc: Any, token: str) -> Optional[bool]:
        lib = self._library()
        fn = getattr(lib, "IsChallengeCompleteForPlayer", None) if lib else None
        if not callable(fn):
            return None
        try:
            result = fn(pc, str(token))
        except Exception:  # noqa: BLE001
            return None
        return result if isinstance(result, bool) else None

    def is_rank_active(self, pc: Any, rank: int) -> Optional[bool]:
        ps = getattr(pc, "PlayerState", None)
        value = getattr(ps, "VaultHunterLevel", None) if ps is not None else None
        try:
            return int(value) >= int(rank)
        except (TypeError, ValueError):
            return None


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
