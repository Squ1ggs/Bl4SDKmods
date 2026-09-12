"""Shared Serial Store persistence for BLImGui and the desktop bridge."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

SERIAL_STORE_FILE_NAME = "Squ1ggsBoostingTools_saved_serials.json"

_entries: list[dict[str, str]] = []
_loaded = False


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    try:
        cwd = Path.cwd()
        paths.append(cwd / "sdk_mods" / SERIAL_STORE_FILE_NAME)
        paths.append(cwd / SERIAL_STORE_FILE_NAME)
    except Exception:
        pass
    try:
        paths.append(Path.home() / "Documents" / "My Games" / "Borderlands 4" / "Saved" / SERIAL_STORE_FILE_NAME)
    except Exception:
        pass
    try:
        paths.append(Path(__file__).resolve().parent / SERIAL_STORE_FILE_NAME)
    except Exception:
        pass
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def path_for_read() -> Path | None:
    for path in _candidate_paths():
        try:
            if path.exists():
                return path
        except Exception:
            continue
    return None


def path_for_write() -> Path:
    for path in _candidate_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            continue
    return Path(SERIAL_STORE_FILE_NAME)


def new_id() -> str:
    return str(int(time.time() * 1000))


def reload_entries(*, force: bool = False) -> list[dict[str, str]]:
    global _entries, _loaded
    if _loaded and not force:
        return list(_entries)
    _entries = []
    _loaded = True
    try:
        read_path = path_for_read()
        if read_path is None:
            return []
        with open(read_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        entries = data.get("entries", data) if isinstance(data, dict) else data
        if not isinstance(entries, list):
            return []
        out: list[dict[str, str]] = []
        for index, row in enumerate(entries):
            if not isinstance(row, dict):
                continue
            serial = str(row.get("serial", "")).strip()
            if not serial:
                continue
            out.append(
                {
                    "id": str(row.get("id") or f"loaded_{index}_{abs(hash(serial))}"),
                    "name": str(row.get("name") or f"Serial {index + 1}").strip(),
                    "group": str(row.get("group") or "Default").strip() or "Default",
                    "serial": serial,
                }
            )
        _entries = out
    except Exception:
        _entries = []
    return list(_entries)


def sync_entries(entries: list[dict[str, str]]) -> Path:
    """Replace in-memory entries and persist (for BLImGui sync)."""
    global _entries, _loaded
    _entries = [dict(row) for row in entries if isinstance(row, dict)]
    _loaded = True
    return save_entries()


def save_entries() -> Path:
    global _entries
    write_path = path_for_write()
    with open(write_path, "w", encoding="utf-8") as fh:
        json.dump({"entries": _entries}, fh, indent=2, sort_keys=True)
    return write_path


def groups() -> list[str]:
    reload_entries()
    seen = sorted({str(e.get("group") or "Default") for e in _entries})
    return ["All", *(seen or ["Default"])]


def filter_entries(*, search: str = "", group: str = "All") -> list[dict[str, str]]:
    reload_entries()
    rows = list(_entries)
    group_name = str(group or "All").strip() or "All"
    if group_name != "All":
        rows = [e for e in rows if str(e.get("group") or "Default") == group_name]
    query = str(search or "").strip().lower()
    if query:
        rows = [
            e
            for e in rows
            if query
            in " ".join(
                str(e.get(key, ""))
                for key in ("name", "group", "serial", "id")
            ).lower()
        ]
    return rows


def get_entry(entry_id: str) -> dict[str, str] | None:
    reload_entries()
    wanted = str(entry_id or "").strip()
    if not wanted:
        return None
    for row in _entries:
        if str(row.get("id", "")) == wanted:
            return dict(row)
    return None


def save_entry(
    *,
    entry_id: str = "",
    name: str,
    group: str,
    serial: str,
    validate_serial: Any | None = None,
) -> dict[str, str]:
    """Create or update a saved serial entry."""
    global _entries
    reload_entries()
    clean_name = str(name or "").strip()
    clean_group = str(group or "Default").strip() or "Default"
    clean_serial = str(serial or "").strip()
    if not clean_serial:
        raise ValueError("Serial is required before saving.")
    if not clean_name:
        # Auto-name from serial so Save entry works with paste-only.
        snippet = clean_serial.replace("\n", " ").strip()
        if len(snippet) > 40:
            snippet = snippet[:37] + "…"
        clean_name = snippet or "Saved serial"
    if validate_serial is not None:
        validate_serial(clean_serial)
    entry_id = str(entry_id or "").strip()
    if entry_id:
        for row in _entries:
            if str(row.get("id", "")) == entry_id:
                row.update({"name": clean_name, "group": clean_group, "serial": clean_serial})
                save_entries()
                return dict(row)
    entry = {
        "id": entry_id or new_id(),
        "name": clean_name,
        "group": clean_group,
        "serial": clean_serial,
    }
    _entries.append(entry)
    save_entries()
    return dict(entry)


def delete_entries(entry_ids: list[str]) -> int:
    global _entries
    reload_entries()
    wanted = {str(item).strip() for item in entry_ids if str(item).strip()}
    if not wanted:
        raise ValueError("No entry id(s) provided.")
    before = len(_entries)
    _entries = [e for e in _entries if str(e.get("id", "")) not in wanted]
    deleted = before - len(_entries)
    if deleted <= 0:
        raise ValueError("No matching saved serials were deleted.")
    save_entries()
    return deleted


def duplicate_entry(entry_id: str) -> dict[str, str]:
    source = get_entry(entry_id)
    if source is None:
        raise ValueError("Select a saved serial before duplicating.")
    copy_name = f"{str(source.get('name') or 'Serial').strip() or 'Serial'} Copy"
    return save_entry(name=copy_name, group=str(source.get("group") or "Default"), serial=str(source.get("serial") or ""))


def serials_for_ids(entry_ids: list[str]) -> list[str]:
    reload_entries()
    wanted = {str(item).strip() for item in entry_ids if str(item).strip()}
    serials: list[str] = []
    for row in _entries:
        if str(row.get("id", "")) in wanted:
            serials.append(str(row.get("serial", "")).strip())
    return [s for s in serials if s]
