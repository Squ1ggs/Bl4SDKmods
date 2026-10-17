"""Shared Serial Store persistence for BLImGui and the desktop bridge."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

SERIAL_STORE_FILE_NAME = "Squ1ggsBoostingTools_saved_serials.json"

_entries: list[dict[str, str]] = []
_groups: list[str] = []
_loaded = False
_loaded_stamp: tuple[str, int, int] | None = None
_last_generated_id = 0


def _clean_group_name(group: str) -> str:
    return str(group or "").strip() or "Default"


def _remember_group(group: str) -> None:
    """Keep a pack name even before it has a serial, so New list shows immediately."""
    global _groups
    name = _clean_group_name(group)
    if name.casefold() == "all":
        return
    if name not in _groups:
        _groups.append(name)


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
    """Prefer Documents Saved file so EXE + game share one library."""
    preferred = _preferred_store_path()
    try:
        if preferred.exists():
            return preferred
    except Exception:
        pass
    # Migrate older Win64/cwd copies into Documents once, then prefer Documents.
    for path in _candidate_paths():
        try:
            if not path.exists():
                continue
            if path.resolve() == preferred.resolve():
                return preferred
            try:
                preferred.parent.mkdir(parents=True, exist_ok=True)
                if not preferred.exists():
                    preferred.write_bytes(path.read_bytes())
                return preferred if preferred.exists() else path
            except Exception:
                return path
        except Exception:
            continue
    return None


def path_for_write() -> Path:
    """Always write Documents Saved when possible (stable across EXE / game cwd)."""
    preferred = _preferred_store_path()
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        # Seed Documents from an older cwd copy if Documents is still empty.
        if not preferred.exists():
            for path in _candidate_paths():
                try:
                    if path.exists() and path.resolve() != preferred.resolve():
                        preferred.write_bytes(path.read_bytes())
                        break
                except Exception:
                    continue
        return preferred
    except Exception:
        pass
    read = path_for_read()
    if read is not None:
        return read
    for path in _candidate_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            continue
    return preferred


def _preferred_store_path() -> Path:
    try:
        return (
            Path.home()
            / "Documents"
            / "My Games"
            / "Borderlands 4"
            / "Saved"
            / SERIAL_STORE_FILE_NAME
        )
    except Exception:
        return Path(SERIAL_STORE_FILE_NAME)


def new_id() -> str:
    """Return a unique, sortable id even during a large pack import."""
    global _last_generated_id
    candidate = max(int(time.time() * 1000), _last_generated_id + 1)
    taken = {str(row.get("id") or "") for row in _entries}
    while str(candidate) in taken:
        candidate += 1
    _last_generated_id = candidate
    return str(candidate)


def _file_stamp(path: Path | None) -> tuple[str, int, int] | None:
    if path is None:
        return None
    try:
        stat = path.stat()
        return str(path.resolve()), stat.st_mtime_ns, stat.st_size
    except OSError:
        return None


def reload_entries(*, force: bool = False) -> list[dict[str, str]]:
    global _entries, _groups, _loaded, _loaded_stamp
    read_path = path_for_read()
    stamp = _file_stamp(read_path)
    if _loaded and not force and stamp == _loaded_stamp:
        return list(_entries)
    _entries = []
    _groups = []
    _loaded = True
    _loaded_stamp = stamp
    try:
        if read_path is None:
            return []
        with open(read_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            raw_groups = data.get("groups") or []
            if isinstance(raw_groups, list):
                for raw in raw_groups:
                    _remember_group(str(raw or ""))
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
            group_name = _clean_group_name(str(row.get("group") or "Default"))
            _remember_group(group_name)
            out.append(
                {
                    "id": str(row.get("id") or f"loaded_{index}_{abs(hash(serial))}"),
                    "name": str(row.get("name") or f"Serial {index + 1}").strip(),
                    "group": group_name,
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
    global _entries, _groups, _loaded_stamp
    write_path = path_for_write()
    names = sorted({_clean_group_name(g) for g in _groups if _clean_group_name(g).casefold() != "all"})
    for row in _entries:
        names.append(_clean_group_name(str(row.get("group") or "Default")))
    _groups = sorted({name for name in names if name and name.casefold() != "all"})
    with open(write_path, "w", encoding="utf-8") as fh:
        json.dump({"entries": _entries, "groups": _groups}, fh, indent=2, sort_keys=True)
    _loaded_stamp = _file_stamp(write_path)
    return write_path


def groups() -> list[str]:
    reload_entries()
    seen = {_clean_group_name(str(e.get("group") or "Default")) for e in _entries}
    seen.update(_clean_group_name(g) for g in _groups)
    seen.discard("")
    seen = {name for name in seen if name.casefold() != "all"}
    return ["All", *(sorted(seen) or ["Default"])]


def group_counts() -> dict[str, int]:
    """True per-pack sizes (ignores List filter / search) for pack header badges."""
    reload_entries()
    counts: dict[str, int] = {}
    for row in _entries:
        name = _clean_group_name(str(row.get("group") or "Default"))
        if not name or name.casefold() == "all":
            continue
        counts[name] = counts.get(name, 0) + 1
    for raw in _groups:
        name = _clean_group_name(raw)
        if name and name.casefold() != "all":
            counts.setdefault(name, 0)
    return counts


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
    clean_group = _clean_group_name(group)
    _remember_group(clean_group)
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
            serials.append(str(row.get("serial") or "").strip())
    return [s for s in serials if s]


def rename_group(old_group: str, new_group: str) -> int:
    """Rename a pack (group) across all members. Returns how many rows changed."""
    global _entries
    reload_entries()
    old = _clean_group_name(old_group)
    new = _clean_group_name(new_group)
    if old == new:
        return 0
    if old.lower() == "all":
        raise ValueError("Cannot rename the All filter.")
    changed = 0
    for row in _entries:
        if _clean_group_name(str(row.get("group") or "Default")) == old:
            row["group"] = new
            changed += 1
    had_name = old in _groups
    if changed <= 0 and not had_name:
        raise ValueError(f"No pack named “{old}”.")
    _groups = [new if name == old else name for name in _groups]
    _remember_group(new)
    save_entries()
    return changed or (1 if had_name else 0)


def create_group(group: str) -> str:
    """Remember a pack name immediately. No placeholder serial is written."""
    reload_entries()
    name = _clean_group_name(group) if str(group or "").strip() else "New pack"
    if name.lower() == "all":
        raise ValueError("Cannot create a pack named All.")
    _remember_group(name)
    save_entries()
    return name


def delete_group(group: str) -> int:
    """Delete every entry in a pack. Returns how many rows removed."""
    global _entries
    reload_entries(force=True)
    name = str(group or "").strip() or "Default"
    if name.lower() == "all":
        raise ValueError("Cannot delete the All filter — pick a pack name.")
    before = len(_entries)
    # Case-insensitive pack match (UI "GZO" vs stored "gzo").
    want = name.casefold()
    had_name = any(_clean_group_name(g).casefold() == want for g in _groups)
    _entries = [
        row
        for row in _entries
        if str(row.get("group") or "Default").strip().casefold() != want
    ]
    _groups = [g for g in _groups if _clean_group_name(g).casefold() != want]
    deleted = before - len(_entries)
    if deleted <= 0 and not had_name:
        raise ValueError(f"No pack named “{name}”.")
    save_entries()
    return deleted or (1 if had_name else 0)


def export_json(*, group: str = "All") -> str:
    """Shareable JSON library (same schema as import)."""
    rows = filter_entries(group=group)
    payload = {
        "entries": [
            {
                "id": str(row.get("id") or ""),
                "name": str(row.get("name") or ""),
                "group": str(row.get("group") or "Default"),
                "serial": str(row.get("serial") or ""),
            }
            for row in rows
            if str(row.get("serial") or "").strip()
        ]
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def export_text(*, group: str = "All") -> str:
    """Simple shareable txt: `# PackName` headers and one serial per line."""
    rows = filter_entries(group=group)
    if not rows:
        return ""
    by_group: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        g = str(row.get("group") or "Default").strip() or "Default"
        by_group.setdefault(g, []).append(row)
    lines: list[str] = []
    for g in sorted(by_group.keys()):
        lines.append(f"# {g}")
        for row in by_group[g]:
            serial = str(row.get("serial") or "").strip()
            if serial:
                lines.append(serial)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def import_merge_text(text: str, *, default_group: str = "Imported") -> dict[str, Any]:
    """Merge txt/JSON into the library. Never wipes existing entries.

    Duplicates are skipped per list only — the same code may live in several lists.
    """
    reload_entries()
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Nothing to import.")
    incoming: list[tuple[str, str, str]] = []
    if raw.startswith("{") or raw.startswith("["):
        try:
            data = json.loads(raw)
        except Exception as exc:
            raise ValueError(f"Could not parse JSON library: {exc}") from exc
        entries = data.get("entries", data) if isinstance(data, dict) else data
        if not isinstance(entries, list):
            raise ValueError("JSON library must contain an entries list.")
        for index, row in enumerate(entries):
            if not isinstance(row, dict):
                continue
            serial = str(row.get("serial") or "").strip()
            if not serial:
                continue
            name = str(row.get("name") or f"Imported {index + 1}").strip()
            group = str(row.get("group") or default_group).strip() or default_group
            incoming.append((name, group, serial))
    else:
        current_group = str(default_group or "Imported").strip() or "Imported"
        pack_index = 0
        for line in raw.replace("\r\n", "\n").split("\n"):
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                title = s.lstrip("#").strip() or "Imported"
                current_group = title
                pack_index = 0
                continue
            pack_index += 1
            name = current_group if pack_index == 1 else f"{current_group} #{pack_index}"
            incoming.append((name, current_group, s))
    if not incoming:
        raise ValueError("No serials found in that file.")
    existing = {
        (str(e.get("group") or "").strip().casefold(), str(e.get("serial") or "").strip())
        for e in _entries
    }
    added = 0
    skipped = 0
    for name, group, serial in incoming:
        key = (_clean_group_name(group).strip().casefold(), serial)
        if key in existing:
            skipped += 1
            continue
        save_entry(name=name, group=group, serial=serial)
        existing.add(key)
        added += 1
    return {"added": added, "skipped": skipped, "total": len(incoming)}
