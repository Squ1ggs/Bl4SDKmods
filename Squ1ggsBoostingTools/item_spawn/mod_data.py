"""Read bundled JSON from folder or .sdkmod installs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from mods_base import open_in_mod_dir
except ImportError:  # Release tooling runs outside UnrealSDK.
    open_in_mod_dir = None


def read_mod_json(path: Path) -> Any | None:
    try:
        if open_in_mod_dir is None:
            return json.loads(path.read_text(encoding="utf-8"))
        with open_in_mod_dir(path, binary=True) as fh:
            return json.loads(fh.read().decode("utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def mod_data_exists(path: Path) -> bool:
    return read_mod_json(path) is not None
