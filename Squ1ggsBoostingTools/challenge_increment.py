"""Shared challenge increment helpers for local + remote (incl. console) players.

Dump-backed write path (OakChallengeBlueprintLibrary):
  IncrementChallengeForPlayer(OwnerContext, OakPC, Challenge:FGameDataHandle@16413, IncrementCount)

The Challenges UI reads PlayerState.ChallengeObjectiveStates — numeric RPCs alone often
false-OK on remote/console clients without moving their UI. Always pair library/RPC
calls with COS writes on the *target* PlayerState (listen-host authoritative).
"""
from __future__ import annotations

from typing import Any, Optional

CHALLENGE_TYPE_HANDLE = 16413

_LIBRARY_CDO: Any = None
_INCREMENT_FN: Any = None
_TEARDOWN_HOOKED = False


def _clear_library_cache(_reason: str = "") -> None:
    """Drop cached UObjects after map/menu teardown — they go stale."""
    global _LIBRARY_CDO, _INCREMENT_FN
    del _reason
    _LIBRARY_CDO = None
    _INCREMENT_FN = None


def _challenge_library() -> Any:
    """Resolve OakChallengeBlueprintLibrary CDO once (static/reuse), not every apply."""
    global _LIBRARY_CDO, _TEARDOWN_HOOKED
    if _LIBRARY_CDO is not None:
        return _LIBRARY_CDO

    import unrealsdk

    cdo: Any = None
    for class_name in (
        "OakChallengeBlueprintLibrary",
        "/Script/OakGame.OakChallengeBlueprintLibrary",
    ):
        try:
            cls = unrealsdk.find_class(class_name)
            cdo = getattr(cls, "ClassDefaultObject", None) if cls is not None else None
            if cdo is not None:
                break
        except Exception:
            continue
    if cdo is None:
        try:
            cls = unrealsdk.find_object("Class", "/Script/OakGame.OakChallengeBlueprintLibrary")
            cdo = getattr(cls, "ClassDefaultObject", None) if cls is not None else None
        except Exception:
            cdo = None
    if cdo is not None:
        _LIBRARY_CDO = cdo
        if not _TEARDOWN_HOOKED:
            try:
                from .session_guards import register_teardown_listener

                register_teardown_listener(_clear_library_cache)
                _TEARDOWN_HOOKED = True
            except Exception:
                pass
    return cdo


def _increment_fn() -> Any:
    global _INCREMENT_FN
    if _INCREMENT_FN is not None:
        return _INCREMENT_FN
    lib = _challenge_library()
    if lib is None:
        return None
    fn = getattr(lib, "IncrementChallengeForPlayer", None)
    if callable(fn):
        _INCREMENT_FN = fn
        return fn
    return None


def _world_context(pc: Any) -> Any:
    if pc is None:
        return None
    for getter in (
        lambda: getattr(pc, "World", None),
        lambda: getattr(getattr(pc, "Pawn", None), "World", None),
        lambda: getattr(getattr(pc, "AcknowledgedPawn", None), "World", None),
        lambda: getattr(pc, "GameInstance", None),
    ):
        try:
            ctx = getter()
            if ctx is not None:
                return ctx
        except Exception:
            continue
    try:
        import unrealsdk

        engine = getattr(unrealsdk, "ENGINE", None)
        viewport = getattr(engine, "GameViewport", None) if engine is not None else None
        world = getattr(viewport, "World", None) if viewport is not None else None
        if world is not None:
            return world
    except Exception:
        pass
    return None


def _token_labels(token: str) -> list[str]:
    raw = str(token or "").strip()
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for label in (raw, raw.replace("-", "_"), raw.casefold(), raw.replace("-", "_").casefold()):
        if label and label not in seen:
            seen.add(label)
            out.append(label)
    return out


def _handles_for_token(token: str) -> list[Any]:
    try:
        from unrealsdk.unreal import FGameDataHandle
    except Exception:
        return []
    out: list[Any] = []
    for label in _token_labels(token):
        try:
            out.append(FGameDataHandle(CHALLENGE_TYPE_HANDLE, label))
        except Exception:
            continue
    return out


def _try_call(fn: Any, args: tuple[Any, ...]) -> bool:
    try:
        fn(*args)
        return True
    except Exception:
        return False


def _pc_label(pc: Any) -> str:
    if pc is None:
        return "<none>"
    try:
        ps = getattr(pc, "PlayerState", None)
        name = ""
        if ps is not None:
            for attr in ("PlayerNamePrivate", "PlayerName", "GetPlayerName"):
                try:
                    val = getattr(ps, attr, None)
                    if callable(val):
                        val = val()
                    if val:
                        name = str(val)
                        break
                except Exception:
                    continue
        path = str(getattr(pc, "Name", None) or pc)[:80]
        return f"{name or '?'} ({path})"
    except Exception:
        return str(pc)[:80]


def _read_progress(pc: Any, handle: Any) -> Any:
    lib = _challenge_library()
    if lib is None or pc is None or handle is None:
        return None
    fn = getattr(lib, "GetChallengeProgressForPlayer", None)
    if not callable(fn):
        return None
    try:
        return fn(pc, handle)
    except Exception:
        try:
            return fn(pc, pc, handle)
        except Exception:
            return None


def _read_complete(pc: Any, handle: Any) -> Any:
    lib = _challenge_library()
    if lib is None or pc is None or handle is None:
        return None
    fn = getattr(lib, "IsChallengeCompleteForPlayer", None)
    if not callable(fn):
        return None
    try:
        return fn(pc, handle)
    except Exception:
        try:
            return fn(pc, pc, handle)
        except Exception:
            return None


def _write_cos(pc: Any, token: str) -> int:
    """Write ChallengeObjectiveStates on the target PlayerState (UI source of truth)."""
    try:
        from .challenge_objective_state import complete_selected_challenge_objective_states
    except Exception:
        return 0
    try:
        return int(complete_selected_challenge_objective_states(pc, (token,)) or 0)
    except Exception:
        return 0


def _lib_increment_for_player(target_pc: Any, token: str, amount: int) -> bool:
    """Apply library increment to ``target_pc`` only. Prefer verified progress movement."""
    fn = _increment_fn()
    if not callable(fn) or target_pc is None:
        return False
    amount_i = max(1, int(amount))
    world = _world_context(target_pc)
    handles = _handles_for_token(token)
    if not handles:
        return False

    for handle in handles:
        before_prog = _read_progress(target_pc, handle)
        before_done = _read_complete(target_pc, handle)
        attempts: list[tuple[Any, ...]] = [
            # Dump / ticker proven shape first.
            (target_pc, target_pc, handle, amount_i),
        ]
        if world is not None:
            # ULM uses World/GameInstance as OwnerContext.
            attempts.insert(0, (world, target_pc, handle, amount_i))
        called = False
        for args in attempts:
            if _try_call(fn, args):
                called = True
                break
        if not called:
            continue
        # Final / parent rank-up tokens mutate challenge state — skip immediate
        # IsChallengeComplete / progress re-read (AV magnet during AUVHM).
        token_l = str(token or "").casefold()
        if (
            "finalchallenge" in token_l
            or token_l.endswith("_parent")
            or "bloomreaper" in token_l
        ):
            return True
        after_prog = _read_progress(target_pc, handle)
        after_done = _read_complete(target_pc, handle)
        if before_done is True or after_done is True:
            return True
        if before_prog is not None and after_prog is not None and after_prog != before_prog:
            return True
        # Call accepted but progress unread/unchanged — still count as attempted;
        # COS write in increment_challenge covers the UI path.
        return True
    return False


def _lib_increment_for_all(owner_pc: Any, token: str, amount: int) -> bool:
    lib = _challenge_library()
    if lib is None or owner_pc is None:
        return False
    fn = getattr(lib, "IncrementChallengeForAllPlayers", None)
    if not callable(fn):
        return False
    world = _world_context(owner_pc)
    amount_i = max(1, int(amount))
    for handle in _handles_for_token(token):
        attempts: list[tuple[Any, ...]] = []
        if world is not None:
            attempts.append((world, handle, amount_i))
            attempts.append((world, handle))
        attempts.extend(
            (
                (owner_pc, handle, amount_i),
                (owner_pc, handle),
            )
        )
        for args in attempts:
            if _try_call(fn, args):
                return True
    return False


def _server_increment(pc: Any, token: str, amount: int) -> bool:
    if pc is None:
        return False
    fn = getattr(pc, "ServerIncrementChallengeForPlayer", None)
    if not callable(fn):
        return False
    amount_i = max(1, int(amount))
    for label in _token_labels(token)[:2]:
        try:
            fn(label, amount_i)
            return True
        except Exception:
            continue
    return False


def increment_challenge(
    target_pc: Any,
    token: str,
    amount: int,
    *,
    owner_pc: Any | None = None,
    for_all_players: bool = False,
) -> bool:
    """Apply one challenge increment to ``target_pc`` (never substitutes the host).

    Returns True if library/RPC ran and/or ChallengeObjectiveStates were written
    on the target PlayerState.
    """
    token_s = str(token or "").strip()
    if not token_s:
        return False

    if for_all_players:
        host = owner_pc
        if host is None:
            try:
                from mods_base import get_pc

                host = get_pc()
            except Exception:
                host = None
        if _lib_increment_for_all(host or target_pc, token_s, amount):
            # Still COS-write the provided PC when present (caller should loop others).
            if target_pc is not None:
                _write_cos(target_pc, token_s)
            return True
        return False

    if target_pc is None:
        return False

    lib_ok = _lib_increment_for_player(target_pc, token_s, amount)
    rpc_ok = False
    if not lib_ok:
        rpc_ok = _server_increment(target_pc, token_s, amount)
    cos_writes = _write_cos(target_pc, token_s)
    return bool(lib_ok or rpc_ok or cos_writes > 0)


def readiness_error(pc: Any) -> Optional[str]:
    if pc is None:
        return "player controller is missing"
    if getattr(pc, "PlayerState", None) is None:
        return "PlayerState is unavailable"
    lib = _challenge_library()
    has_lib = lib is not None and callable(getattr(lib, "IncrementChallengeForPlayer", None))
    has_rpc = callable(getattr(pc, "ServerIncrementChallengeForPlayer", None))
    has_cos = getattr(getattr(pc, "PlayerState", None), "ChallengeObjectiveStates", None) is not None
    if not has_lib and not has_rpc and not has_cos:
        return "No challenge increment API available"
    return None


def describe_target(pc: Any) -> str:
    return _pc_label(pc)
