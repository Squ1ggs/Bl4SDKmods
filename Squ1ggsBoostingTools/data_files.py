"""Zip-safe access to bundled data files.

Works whether the mod is installed as a plain folder or packed inside a
``.sdkmod`` zip (where ``Path(__file__)``-relative reads fail).
"""
from __future__ import annotations

import json
import logging
import pkgutil
from pathlib import Path
from typing import Any

_MOD_DIR = Path(__file__).resolve().parent
_DATA_DIR = _MOD_DIR / "data"
_MISSING = object()

# Memoize parsed JSON — catalog/search paths used to re-read 100–270KB files
# on every bridge request (same pattern as item_spawn/runtime_cache.py).
# key -> (payload, mtime_ns|None). None mtime = immutable pkgutil blob.
_JSON_CACHE: dict[str, tuple[Any, int | None]] = {}


def clear_data_json_cache() -> None:
    """Drop all memoized ``read_data_json`` payloads (tests / hot reload)."""
    _JSON_CACHE.clear()


def read_data_json(relative_name: str, default: Any = _MISSING) -> Any:
    """Read ``data/<relative_name>`` from the package (folder or zip)."""
    name = str(relative_name or "").strip().replace("\\", "/")
    if not name:
        return {} if default is _MISSING else default

    pkg_key = f"pkg:{name}"
    cached = _JSON_CACHE.get(pkg_key)
    if cached is not None:
        return cached[0]

    try:
        blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], f"data/{name}")
        if blob:
            payload = json.loads(blob.decode("utf-8"))
            _JSON_CACHE[pkg_key] = (payload, None)
            return payload
    except Exception:  # noqa: BLE001
        pass

    try:
        path = _DATA_DIR / name
        if path.is_file():
            file_key = f"file:{path.resolve()}"
            try:
                mtime_ns = int(path.stat().st_mtime_ns)
            except Exception:  # noqa: BLE001
                mtime_ns = None
            cached_file = _JSON_CACHE.get(file_key)
            if cached_file is not None and cached_file[1] == mtime_ns:
                return cached_file[0]
            payload = json.loads(path.read_text(encoding="utf-8"))
            _JSON_CACHE[file_key] = (payload, mtime_ns)
            return payload
    except Exception:  # noqa: BLE001
        pass
    logging.warning(
        f"[Squ1ggs's Boosting Tools] data/{name} unavailable — feature limited this session."
    )
    return {} if default is _MISSING else default


def writable_data_path(relative_name: str) -> Path:
    """A writable location for user data; falls back to the settings dir for zips."""
    if _MOD_DIR.is_dir():
        path = _DATA_DIR / relative_name
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:  # noqa: BLE001
            pass
    try:
        from mods_base import SETTINGS_DIR  # noqa: PLC0415

        path = Path(SETTINGS_DIR) / "Squ1ggsBoostingTools" / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:  # noqa: BLE001
        return Path(relative_name)
