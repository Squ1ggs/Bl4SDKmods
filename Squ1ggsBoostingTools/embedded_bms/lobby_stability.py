"""Generation-aware spawn request gating for listen-host lobbies."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

_log = logging.getLogger("bl4_mob_spawner_hookedwidget.lobby_stability")

_STABLE_FOR_SEC = 0.05
_REQUEST_TIMEOUT_SEC = 15.0
_generation = 0
_signature: tuple[str, tuple[str, ...]] | None = None
_changed_at = 0.0

SpawnFn = Callable[[], tuple[bool, str]]


def _object_key(obj: Any) -> str:
    if obj is None:
        return ""
    try:
        get_path_name = getattr(obj, "GetPathName", None)
        if callable(get_path_name):
            return str(get_path_name() or "")
    except Exception:
        pass
    try:
        name = getattr(obj, "Name", None)
        if name:
            return str(name)
    except Exception:
        pass
    try:
        return str(obj)
    except Exception:
        return f"<{type(obj).__name__}:{id(obj)}>"


def _pawn_from_pc(pc: Any) -> Any:
    if pc is None:
        return None
    for attr in ("OakCharacter", "Pawn", "AcknowledgedPawn"):
        try:
            pawn = getattr(pc, attr, None)
        except Exception:
            pawn = None
        if pawn is not None:
            return pawn
    return None


def _host_context() -> tuple[Any, Any, Any]:
    try:
        from mods_base import ENGINE, get_pc  # noqa: PLC0415

        pc = get_pc()
        viewport = getattr(ENGINE, "GameViewport", None) if ENGINE is not None else None
        world = getattr(viewport, "World", None) if viewport is not None else None
        return pc, _pawn_from_pc(pc), world
    except Exception:
        return None, None, None


def _is_authoritative_world(world: Any) -> bool:
    if world is None:
        return False
    try:
        get_net_mode = getattr(world, "GetNetMode", None)
        mode = get_net_mode() if callable(get_net_mode) else getattr(world, "NetMode", None)
    except Exception:
        mode = None
    text = str(mode or "").casefold()
    if "client" in text and "listen" not in text:
        return False
    try:
        return int(mode) != 3
    except (TypeError, ValueError):
        return True


def _roster_keys(host_pc: Any, world: Any) -> tuple[str, ...]:
    """Read the current world's bounded PlayerArray without global UObject scans."""
    keys: list[str] = []
    try:
        game_state = getattr(world, "GameState", None)
        players = getattr(game_state, "PlayerArray", None) if game_state is not None else None
        if players is None:
            players = ()
        for index, player_state in enumerate(list(players)[:16]):
            if player_state is None:
                continue
            key = ""
            for field in ("UniqueId", "PlatformUserId", "PlayerId", "PlayerNamePrivate"):
                try:
                    value = getattr(player_state, field, None)
                except Exception:
                    continue
                text = str(value or "").strip()
                if text and not text.startswith("<"):
                    key = f"{field}={text}"
                    break
            keys.append(key or f"roster_index={index}")
    except Exception:
        keys = []
    if not keys and host_pc is not None:
        keys.append(_object_key(host_pc))
    return tuple(keys)


def _invalidate_backend(reason: str) -> None:
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

        invalidate = getattr(ssp, "_invalidate_spawn_runtime_cache", None)
        if callable(invalidate):
            invalidate(reason)
    except Exception:
        _log.debug("backend cache invalidation unavailable", exc_info=True)


def _queue_thin_air_prewarm() -> None:
    """Build the reusable OakSpawner on PlayerTick so the first BMS click is not ~3s."""
    try:
        from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

        def _do() -> tuple[bool, str]:
            ok = bool(ssp.prewarm_thin_air_spawner())
            return ok, "OakSpawner prewarmed" if ok else "OakSpawner prewarm skipped"

        deferred.queue_action("Prewarm OakSpawner", _do)
    except Exception:
        _log.debug("thin-air spawner prewarm unavailable", exc_info=True)


def observe_generation() -> tuple[int, bool, Any, Any, Any]:
    """Return generation/stability plus freshly resolved host PC, pawn, and world."""
    global _generation, _signature, _changed_at
    now = time.monotonic()
    host_pc, host_pawn, world = _host_context()
    signature = (_object_key(world), _roster_keys(host_pc, world))
    if signature != _signature:
        previous = _signature
        _signature = signature
        _generation += 1
        _changed_at = now
        transition = "initial lobby bind" if previous is None else "world/roster transition"
        _invalidate_backend(f"lobby generation {_generation}: {transition}")
        _log.info("lobby generation=%s world=%s roster=%s", _generation, signature[0], signature[1])
        if host_pawn is not None and world is not None:
            _queue_thin_air_prewarm()
    ready = (
        host_pc is not None
        and host_pawn is not None
        and world is not None
        and _is_authoritative_world(world)
    )
    stable = ready and (now - _changed_at) >= _STABLE_FOR_SEC
    return _generation, stable, host_pc, host_pawn, world


def current_generation() -> int:
    return observe_generation()[0]


def _resolve_anchor(anchor: str, party_index: int) -> Any:
    if anchor != "party":
        return None
    try:
        from Squ1ggsBoostingTools.dev_tools import _pc_for_party_index  # noqa: PLC0415

        pc, _err = _pc_for_party_index(max(1, int(party_index)))
        return pc
    except Exception:
        return None


def _resolve_npc_anchor(host_pawn: Any, anchor: str) -> Any:
    if anchor != "npc_nearest":
        return None
    try:
        from .spawn_anchor import nearest_npc  # noqa: PLC0415

        return nearest_npc(host_pawn, max_distance=6000.0)
    except Exception:
        return None


@dataclass
class SpawnRequest:
    label: str
    fn: SpawnFn
    generation: int
    world_key: str
    anchor: str = "local"
    party_index: int = 2
    timeout: float = _REQUEST_TIMEOUT_SEC
    created_at: float = field(default_factory=time.monotonic)
    state: str = "waiting_for_stable_lobby"
    breadcrumbs: list[str] = field(default_factory=list)
    status_ui: Any = None

    def _crumb(self, message: str) -> None:
        stamp = time.monotonic() - self.created_at
        crumb = f"{stamp:.2f}s {message}"
        if not self.breadcrumbs or self.breadcrumbs[-1] != crumb:
            self.breadcrumbs.append(crumb)
            self.breadcrumbs[:] = self.breadcrumbs[-8:]

    def _result(self, ok: bool, message: str) -> tuple[bool, str]:
        ui = self.status_ui
        if ui is not None:
            try:
                ui.status_text = message
                ui.error_text = message if self.state == "failed" else ""
                # Only the pre-fire lobby wait holds the UI timer. Background
                # detect must not re-arm it (that left the timer running forever).
                ui.spawn_pending = self.state == "waiting_for_stable_lobby"
                if not ui.spawn_pending:
                    try:
                        ui.spawn_pending_since = 0.0
                    except Exception:
                        pass
            except Exception:
                pass
        return ok, message

    def execute(self) -> tuple[bool, str]:
        """Run once stable, or requeue this same request without firing."""
        generation, stable, _host_pc, host_pawn, world = observe_generation()
        elapsed = time.monotonic() - self.created_at
        if world is not None and not _is_authoritative_world(world):
            self.state = "failed"
            self._crumb("host authority unavailable")
            return self._result(False, f"{self.label}: failed — listen host authority required")
        if elapsed >= self.timeout:
            self.state = "failed"
            self._crumb("timeout waiting for stable lobby")
            return self._result(False, f"{self.label}: failed after {elapsed:.1f}s [{'; '.join(self.breadcrumbs)}]")

        if generation != self.generation:
            current_world_key = _object_key(world)
            if self.world_key and current_world_key != self.world_key:
                self.state = "failed"
                self._crumb(f"world changed {self.world_key}->{current_world_key}")
                return self._result(False, f"{self.label}: failed because the world changed")
            self._crumb(f"generation {self.generation}->{generation}")
            self._crumb("actor-def/spawner cache invalidated")
            self.generation = generation
            stable = False

        anchor_pc = _resolve_anchor(self.anchor, self.party_index)
        anchor_actor = _resolve_npc_anchor(host_pawn, self.anchor)
        if self.anchor == "party" and anchor_pc is None:
            stable = False
            self._crumb(f"party anchor {self.party_index} unavailable")
        # Serialize only briefly: a stuck 18s detect job used to block every new
        # spawn until this request timed out at 15s ("nothing spawns"). Allow the
        # next fire once detection has already had a short head start.
        try:
            from Squ1ggsBoostingTools.embedded_bms import controller as bms  # noqa: PLC0415

            prior = getattr(getattr(bms, "CONTROLLER", None), "_async_spawn", None)
            if prior is not None:
                prior_age = time.monotonic() - float(getattr(prior, "started_at", self.created_at) or self.created_at)
                if prior_age < 1.25:
                    stable = False
                    self._crumb("waiting for prior detection")
        except Exception:
            pass

        if not stable:
            self.state = "waiting_for_stable_lobby"
            self._crumb(f"waiting generation {self.generation}")
            from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415

            deferred.queue_action(self.label, self.execute)
            return self._result(True, f"{self.label}: waiting_for_stable_lobby (generation {self.generation})")

        try:
            from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

            self.state = "fired"
            self._crumb(f"fired generation {self.generation} anchor={self.anchor}")
            # Resolve the target now, scope the placement override, and always clear it.
            if self.anchor == "npc_nearest" and anchor_actor is not None:
                context = ssp.spawn_at_actor(anchor_actor, clear_on_exit=True)
            else:
                context = ssp.spawn_at_player_controller(anchor_pc, clear_on_exit=True)
            with context:
                ok, msg = self.fn()
        except Exception as exc:  # noqa: BLE001
            self.state = "failed"
            self._crumb(f"{type(exc).__name__}: {exc}")
            return self._result(False, f"{self.label}: failed [{'; '.join(self.breadcrumbs)}]")

        msg_lower = str(msg).lower()
        # Do not requeue "may still stream in" forever — that burned 15s retries
        # with the same failed fire. Async detect / SSP fallback handles settle.
        if not ok:
            self.state = "failed"
            self._crumb(str(msg))
        elif "detect" in msg_lower:
            self.state = "detecting"
            self._crumb("detecting")
        else:
            self._crumb(f"backend result: {str(msg)[:120]}")
        return self._result(bool(ok), f"{self.state}: {msg}")


def make_request(
    label: str,
    fn: SpawnFn,
    *,
    anchor: str = "local",
    party_index: int = 2,
    status_ui: Any = None,
) -> SpawnRequest:
    generation, _stable, _host_pc, _host_pawn, world = observe_generation()
    requested_anchor = str(anchor).strip().lower()
    normalized_anchor = requested_anchor if requested_anchor in ("party", "npc_nearest") else "local"
    return SpawnRequest(
        label=str(label or "spawn"),
        fn=fn,
        generation=generation,
        world_key=_object_key(world),
        anchor=normalized_anchor,
        party_index=max(1, int(party_index)),
        status_ui=status_ui,
    )


