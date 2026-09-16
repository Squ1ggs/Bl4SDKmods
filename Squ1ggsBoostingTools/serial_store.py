"""Shared Serial Store persistence for BLImGui and the desktop bridge."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

SERIAL_STORE_FILE_NAME = "Squ1ggsBoostingTools_saved_serials.json"

_entries: list[dict[str, str]] = []
_loaded = False
_last_generated_id = 0


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
    """Return a unique, sortable id even during a large pack import."""
    global _last_generated_id
    candidate = max(int(time.time() * 1000), _last_generated_id + 1)
    taken = {str(row.get("id") or "") for row in _entries}
    while str(candidate) in taken:
        candidate += 1
    _last_generated_id = candidate
    return str(candidate)


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
            serials.append(str(row.get("serial") or "").strip())
    return [s for s in serials if s]


def rename_group(old_group: str, new_group: str) -> int:
    """Rename a pack (group) across all members. Returns how many rows changed."""
    global _entries
    reload_entries()
    old = str(old_group or "").strip() or "Default"
    new = str(new_group or "").strip() or "Default"
    if old == new:
        return 0
    if old.lower() == "all":
        raise ValueError("Cannot rename the All filter.")
    changed = 0
    for row in _entries:
        if str(row.get("group") or "Default") == old:
            row["group"] = new
            changed += 1
    if changed <= 0:
        raise ValueError(f"No pack named “{old}”.")
    save_entries()
    return changed


def create_group(group: str) -> str:
    """Name a pack for the editor — first real serial Save creates it.

    Returns the cleaned pack name (no placeholder serials).
    """
    name = str(group or "").strip() or "New pack"
    if name.lower() == "all":
        raise ValueError("Cannot create a pack named All.")
    return name


def delete_group(group: str) -> int:
    """Delete every entry in a pack. Returns how many rows removed."""
    global _entries
    reload_entries()
    name = str(group or "").strip() or "Default"
    if name.lower() == "all":
        raise ValueError("Cannot delete the All filter — pick a pack name.")
    before = len(_entries)
    _entries = [row for row in _entries if str(row.get("group") or "Default") != name]
    deleted = before - len(_entries)
    if deleted <= 0:
        raise ValueError(f"No pack named “{name}”.")
    save_entries()
    return deleted


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
    """Merge txt/JSON into the library. Never wipes existing entries. Skips duplicate serials."""
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
    existing = {str(e.get("serial") or "").strip() for e in _entries}
    added = 0
    skipped = 0
    for name, group, serial in incoming:
        if serial in existing:
            skipped += 1
            continue
        save_entry(name=name, group=group, serial=serial)
        existing.add(serial)
        added += 1
    return {"added": added, "skipped": skipped, "total": len(incoming)}
