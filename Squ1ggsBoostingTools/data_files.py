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


def read_data_json(relative_name: str, default: Any = _MISSING) -> Any:
    """Read ``data/<relative_name>`` from the package (folder or zip)."""
    try:
        blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], f"data/{relative_name}")
        if blob:
            return json.loads(blob.decode("utf-8"))
    except Exception:  # noqa: BLE001
        pass
    try:
        path = _DATA_DIR / relative_name
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    logging.warning(
        f"[Squ1ggs's Boosting Tools] data/{relative_name} unavailable — feature limited this session."
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
