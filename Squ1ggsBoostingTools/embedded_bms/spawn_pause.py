"""Hard-pause the world during heavy spawn work (not slowmo hitch)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

_saved_dilation: float | None = None
_pause_depth: int = 0


def _world_settings() -> Any | None:
    try:
        import unrealsdk  # noqa: PLC0415

        eng = unrealsdk.find_object("Engine", "Transient.GEngine") or unrealsdk.find_all("Engine")
        if isinstance(eng, list):
            eng = eng[0] if eng else None
        if eng is None:
            from mods_base import ENGINE  # noqa: PLC0415

            eng = ENGINE
        gv = getattr(eng, "GameViewport", None)
        world = getattr(gv, "World", None) if gv is not None else None
        if world is None:
            world = getattr(eng, "GetCurrentWorld", lambda: None)()
        if world is None:
            return None
        pl = getattr(world, "PersistentLevel", None)
        return getattr(pl, "WorldSettings", None) if pl is not None else getattr(world, "WorldSettings", None)
    except Exception:
        return None


def _try_set_game_paused(paused: bool) -> bool:
    try:
        import unrealsdk  # noqa: PLC0415

        gs = unrealsdk.find_class("GameplayStatics")
        cdo = getattr(gs, "ClassDefaultObject", None) if gs is not None else None
        if cdo is None:
            return False
        fn = getattr(cdo, "SetGamePaused", None)
        if not callable(fn):
            return False
        ws = _world_settings()
        world = getattr(getattr(ws, "Outer", None), "Outer", None) if ws is not None else None
        if world is None:
            try:
                from mods_base import ENGINE  # noqa: PLC0415

                world = getattr(getattr(ENGINE, "GameViewport", None), "World", None)
            except Exception:
                world = None
        if world is None:
            return False
        fn(world, bool(paused))
        return True
    except Exception:
        return False


def _set_time_dilation(value: float) -> bool:
    ws = _world_settings()
    if ws is None:
        return False
    try:
        ws.TimeDilation = float(value)
        return True
    except Exception:
        return False


def begin_spawn_pause() -> str:
    """Pause simulation for spawn work. Prefer SetGamePaused; else TimeDilation=0."""
    global _saved_dilation, _pause_depth
    _pause_depth += 1
    if _pause_depth > 1:
        return "pause nested"
    parts: list[str] = []
    if _try_set_game_paused(True):
        parts.append("SetGamePaused")
    ws = _world_settings()
    if ws is not None:
        try:
            _saved_dilation = float(getattr(ws, "TimeDilation", 1.0) or 1.0)
        except Exception:
            _saved_dilation = 1.0
        # 0.0 = hard stop. Do NOT use 0.01 (that only slows the game).
        if _set_time_dilation(0.0):
            parts.append("TimeDilation=0")
    return "+".join(parts) if parts else "pause unavailable"


def end_spawn_pause() -> str:
    global _saved_dilation, _pause_depth
    if _pause_depth <= 0:
        return "not paused"
    _pause_depth -= 1
    if _pause_depth > 0:
        return "pause nested"
    parts: list[str] = []
    if _try_set_game_paused(False):
        parts.append("unpause")
    restore = 1.0 if _saved_dilation is None else float(_saved_dilation)
    if restore <= 0.0:
        restore = 1.0
    if _set_time_dilation(restore):
        parts.append(f"TimeDilation={restore:g}")
    _saved_dilation = None
    return "+".join(parts) if parts else "unpause done"


@contextmanager
def spawn_paused() -> Iterator[None]:
    begin_spawn_pause()
    try:
        yield
    finally:
        end_spawn_pause()
