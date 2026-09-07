"""Live GameState / OakWorldSettings setattr helpers (Aug 2026 dump Lab)."""

from __future__ import annotations

from typing import Any


def _live_world_settings() -> Any | None:
    try:
        import unrealsdk

        engine = unrealsdk.get_engine()
        world = getattr(getattr(engine, "GameViewport", None), "World", None)
        ws = getattr(world, "WorldSettings", None) if world is not None else None
        if ws is not None:
            return ws
        lvl = getattr(world, "PersistentLevel", None) if world is not None else None
        return getattr(lvl, "WorldSettings", None) if lvl is not None else None
    except Exception:
        return None


def _live_game_state() -> Any | None:
    try:
        import unrealsdk

        engine = unrealsdk.get_engine()
        world = getattr(getattr(engine, "GameViewport", None), "World", None)
        if world is not None:
            gs = getattr(world, "GameState", None)
            if gs is not None:
                return gs
        for cls in ("OakGameState", "GbxGameState"):
            for gs in list(unrealsdk.find_all(cls, False) or []):
                if gs is None:
                    continue
                try:
                    path = str(getattr(gs, "_path_name", lambda: "")() or gs).lower()
                except Exception:
                    path = str(gs).lower()
                if "default__" in path:
                    continue
                return gs
    except Exception:
        return None
    return None


def _resolve_root(name: str) -> Any | None:
    key = str(name or "").strip().lower()
    if key in ("worldsettings", "world", "ws"):
        return _live_world_settings()
    if key in ("gamestate", "gs"):
        return _live_game_state()
    return None


def _set_path(root: Any, path: str, value: Any) -> bool:
    parts = [p for p in str(path or "").split(".") if p]
    if not parts:
        return False
    cur = root
    for part in parts[:-1]:
        nxt = getattr(cur, part, None)
        if nxt is None:
            return False
        cur = nxt
    try:
        setattr(cur, parts[-1], value)
        return True
    except Exception:
        return False


def write_live_attr(payload: dict[str, Any] | None = None) -> tuple[bool, str]:
    payload = payload or {}
    root_name = str(payload.get("root") or payload.get("target") or "").strip()
    path = str(payload.get("path") or payload.get("field") or "").strip()
    if not root_name or not path:
        return False, "root and path required."
    root = _resolve_root(root_name)
    if root is None:
        return False, f"No live {root_name} — load into a map."
    kind = str(payload.get("kind") or payload.get("type") or "bool").strip().lower()
    raw = payload.get("value")
    if kind == "bool":
        if isinstance(raw, str):
            val = raw.strip().lower() not in ("0", "false", "no", "off", "")
        else:
            val = bool(raw)
    elif kind == "int":
        try:
            val = int(raw)
        except Exception:
            return False, "value must be int."
    else:
        try:
            val = float(raw)
        except Exception:
            return False, "value must be float."
    if not _set_path(root, path, val):
        return False, f"Write failed: {root_name}.{path}"
    if kind == "float" and ".Value" in path:
        base_path = path.replace(".Value", ".BaseValue")
        if base_path != path:
            _set_path(root, base_path, val)
    return True, f"{root_name}.{path}={val!r}"
