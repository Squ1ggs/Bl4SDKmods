"""Named XYZ warp marks — save / teleport / list for the local pawn."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from unrealsdk import logging

_PREFIX = "[Squ1ggs Boosting Tools | WarpMarks]"
_FILE_NAME = "sqbt_warp_marks.json"
_marks: dict[str, list[float]] = {}
_loaded = False
_NAME_RE = re.compile(r"^[\w \-'.]{1,48}$")


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
    except Exception:
        pass


def _path() -> Path:
    try:
        from mods_base import SETTINGS_DIR

        return Path(SETTINGS_DIR) / _FILE_NAME
    except Exception:
        return Path(__file__).resolve().parent / _FILE_NAME


def _load() -> None:
    global _marks, _loaded
    if _loaded:
        return
    _loaded = True
    path = _path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _marks = {}
        return
    out: dict[str, list[float]] = {}
    if isinstance(raw, dict):
        for key, vals in raw.items():
            label = str(key or "").strip()
            if not label or not isinstance(vals, (list, tuple)) or len(vals) < 3:
                continue
            try:
                out[label] = [float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3]) if len(vals) > 3 else 0.0]
            except Exception:
                continue
    _marks = out


def _save() -> None:
    path = _path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_marks, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        _log(f"Could not save warp marks: {exc}")


def list_marks() -> list[dict[str, Any]]:
    _load()
    rows: list[dict[str, Any]] = []
    for name, vals in sorted(_marks.items()):
        rows.append(
            {
                "id": name,
                "name": name,
                "x": vals[0],
                "y": vals[1],
                "z": vals[2],
                "yaw": vals[3] if len(vals) > 3 else 0.0,
                "title": f"{name}  ({vals[0]:.0f}, {vals[1]:.0f}, {vals[2]:.0f})",
            }
        )
    return rows


def save_mark(name: str) -> str:
    from mods_base import get_pc

    label = str(name or "").strip() or "Mark"
    if not _NAME_RE.fullmatch(label):
        raise ValueError("Warp mark name must be 1–48 letters/numbers/spaces.")
    pc = get_pc()
    if pc is None:
        raise RuntimeError("No local player.")
    pawn = None
    for attr in ("OakCharacter", "Pawn", "AcknowledgedPawn"):
        try:
            pawn = getattr(pc, attr, None)
        except Exception:
            pawn = None
        if pawn is not None:
            break
    if pawn is None:
        raise RuntimeError("No local pawn — load into a character first.")
    loc = pawn.K2_GetActorLocation()
    try:
        yaw = float(pawn.K2_GetActorRotation().Yaw)
    except Exception:
        yaw = 0.0
    _load()
    _marks[label] = [float(loc.X), float(loc.Y), float(loc.Z), yaw]
    _save()
    _log(f"Saved warp mark {label!r}")
    return f"Saved warp mark '{label}' at ({loc.X:.0f}, {loc.Y:.0f}, {loc.Z:.0f})."


def go_mark(name: str) -> str:
    from .travel import teleport_local_pawn_to

    label = str(name or "").strip()
    _load()
    vals = _marks.get(label)
    if not vals:
        raise RuntimeError(f"No warp mark named '{label}'.")
    yaw = float(vals[3]) if len(vals) > 3 else 0.0
    msg = teleport_local_pawn_to(float(vals[0]), float(vals[1]), float(vals[2]), yaw=yaw)
    _log(f"Warped to {label!r}")
    return f"Warped to '{label}'. {msg}"


def delete_mark(name: str) -> str:
    label = str(name or "").strip()
    _load()
    if label not in _marks:
        raise RuntimeError(f"No warp mark named '{label}'.")
    del _marks[label]
    _save()
    return f"Deleted warp mark '{label}'."
