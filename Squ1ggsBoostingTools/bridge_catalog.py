"""Read-only catalog payloads for the Squ1ggs Boosting Tools localhost bridge."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .item_pool_spawning import filter_item_pools, item_pool_categories
from .panel_manifest import get_panel_manifest
from .travel import filter_travel_maps, filter_travel_stations
from . import gzo_filters
from . import world_spawn

_GZO_CACHE_NAMES = (
    "Squ1ggsBoostingTools_gzo_codes.json",
    "MattsSDKBoostingTools_gzo_codes.json",
)
_BMS_DATA = Path(__file__).resolve().parent / "embedded_bms" / "data"
# path resolve key -> (payload, mtime_ns). Same memoize pattern as data_files.read_data_json.
_PATH_JSON_CACHE: dict[str, tuple[Any, int]] = {}


def _ok(message: str = "OK", **extra: Any) -> dict[str, Any]:
    return {"ok": True, "message": message, **extra}


def _fail(message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "message": message, **extra}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _mod_dir() -> Path:
    return Path(__file__).resolve().parent


def clear_path_json_cache() -> None:
    """Drop memoized ``_load_json_path`` payloads (tests / hot reload)."""
    _PATH_JSON_CACHE.clear()


def _load_json_path(path: Path) -> Any:
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    if not resolved.is_file():
        return None
    key = str(resolved)
    try:
        mtime_ns = int(resolved.stat().st_mtime_ns)
    except Exception:
        mtime_ns = -1
    cached = _PATH_JSON_CACHE.get(key)
    if cached is not None and cached[1] == mtime_ns:
        return cached[0]
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if mtime_ns >= 0:
        _PATH_JSON_CACHE[key] = (payload, mtime_ns)
    return payload


def _gzo_cache_paths() -> list[Path]:
    paths: list[Path] = []
    try:
        cwd = Path.cwd()
        paths.append(cwd / "sdk_mods" / _GZO_CACHE_NAMES[0])
        paths.append(cwd / _GZO_CACHE_NAMES[0])
    except Exception:
        pass
    try:
        paths.append(Path.home() / "Documents" / "My Games" / "Borderlands 4" / "Saved" / _GZO_CACHE_NAMES[0])
    except Exception:
        pass
    paths.append(_mod_dir() / _GZO_CACHE_NAMES[0])
    for name in _GZO_CACHE_NAMES:
        paths.append(_mod_dir().parent / name)
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def _search_rows(rows: list[dict[str, Any]], search: str, *keys: str) -> list[dict[str, Any]]:
    query = " ".join(str(search or "").casefold().split())
    if not query:
        return rows
    tokens = query.split()
    out: list[dict[str, Any]] = []
    for row in rows:
        hay = " ".join(str(row.get(key) or "") for key in keys).casefold()
        if all(token in hay for token in tokens):
            out.append(row)
    return out


def get_manifest() -> dict[str, Any]:
    return _ok("Panel manifest.", manifest=get_panel_manifest())


def catalog_item_pools(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    search = str(payload.get("search") or "")
    category = str(payload.get("category") or "All")
    limit = int(payload.get("limit") or 2000)
    exclude_currency = _truthy(payload.get("exclude_currency"))
    exclude_ai_guns = _truthy(payload.get("exclude_ai_guns"))
    rows = filter_item_pools(
        search=search,
        category=category,
        limit=max(1, min(limit, 5000)),
        exclude_currency=exclude_currency,
        exclude_ai_guns=exclude_ai_guns,
    )
    total = len(
        filter_item_pools(
            search=search,
            category=category,
            limit=0,
            exclude_currency=exclude_currency,
            exclude_ai_guns=exclude_ai_guns,
        )
    )
    return _ok(
        f"{len(rows)} pool(s) shown" + (f" of {total}." if total > len(rows) else "."),
        rows=rows,
        total=total,
        categories=item_pool_categories(),
    )


def catalog_travel(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    map_search = str(payload.get("map_search") or payload.get("search") or "")
    station_search = str(payload.get("station_search") or "")
    map_name = str(payload.get("map") or "")
    limit = int(payload.get("limit") or 500)
    maps = filter_travel_maps(search=map_search, limit=max(1, min(limit, 500)))
    stations = filter_travel_stations(
        map_name=map_name,
        search=station_search,
        limit=max(1, min(limit, 500)),
    )
    return _ok("Travel catalog.", maps=maps, stations=stations)


def catalog_travel_maps(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    search = str(payload.get("search") or "")
    rows = filter_travel_maps(search=search, limit=int(payload.get("limit") or 500))
    return _ok(f"{len(rows)} map(s).", rows=rows)


def catalog_travel_stations(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    map_name = str(payload.get("map") or "")
    search = str(payload.get("search") or "")
    rows = filter_travel_stations(map_name=map_name, search=search, limit=int(payload.get("limit") or 500))
    return _ok(f"{len(rows)} station(s).", rows=rows)


def catalog_spawn_mixes(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    search = str(payload.get("search") or "")
    category = str(payload.get("category") or "All")
    rows = world_spawn.filter_entries(search=search, category=category)
    limit = int(payload.get("limit") or 500)
    return _ok(
        f"{len(rows)} mix(es).",
        rows=rows[: max(1, min(limit, 2000))],
        total=len(rows),
        categories=world_spawn.categories(),
    )


_gzo_memory_cache: dict[str, Any] = {"path": "", "mtime": 0.0, "entries": []}


def catalog_gzo(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    search = str(payload.get("search") or "")
    listing_filter = str(payload.get("listing") or "All").strip()
    category_filter = str(payload.get("category") or "All").strip()
    type_filter = str(payload.get("type") or payload.get("item_type") or "All").strip()
    maker_filter = str(payload.get("manufacturer") or "All").strip()
    entries: list[dict[str, str]] = []
    for path in _gzo_cache_paths():
        if not path.is_file():
            continue
        try:
            mtime = float(path.stat().st_mtime)
        except Exception:
            mtime = 0.0
        path_key = str(path)
        if (
            _gzo_memory_cache.get("path") == path_key
            and float(_gzo_memory_cache.get("mtime") or 0) == mtime
            and isinstance(_gzo_memory_cache.get("entries"), list)
            and _gzo_memory_cache["entries"]
        ):
            entries = list(_gzo_memory_cache["entries"])
            break
        data = _load_json_path(path)
        if not isinstance(data, dict):
            continue
        raw_entries = data.get("entries") or []
        if not isinstance(raw_entries, list):
            continue
        parsed: list[dict[str, str]] = []
        for raw in raw_entries:
            if not isinstance(raw, dict):
                continue
            serial = str(raw.get("serial") or raw.get("code") or "").strip()
            if not serial.startswith("@U"):
                continue
            listing = str(raw.get("listing") or "GZO").strip() or "GZO"
            title = str(raw.get("name") or raw.get("title") or raw.get("id") or serial[:24])
            item_type = gzo_filters.normalize_type(
                str(raw.get("type") or raw.get("item_type") or "")
            )
            category = gzo_filters.item_category(item_type)
            manufacturer = str(raw.get("manufacturer") or raw.get("maker") or "").strip()
            rarity = str(raw.get("rarity") or "").strip()
            if listing in ("Legit", "Modded"):
                title = f"[{listing.upper()}] {title}"
            parsed.append(
                {
                    "title": title,
                    "serial": serial,
                    "id": str(raw.get("id") or "").strip() or serial,
                    "listing": listing,
                    "type": item_type,
                    "category": category,
                    "manufacturer": manufacturer,
                    "rarity": rarity,
                    "character_class": str(raw.get("character_class") or "").strip(),
                }
            )
        if parsed:
            _gzo_memory_cache["path"] = path_key
            _gzo_memory_cache["mtime"] = mtime
            _gzo_memory_cache["entries"] = parsed
            entries = list(parsed)
            break
    all_entries = list(entries)
    if listing_filter not in ("", "All"):
        entries = [e for e in entries if str(e.get("listing") or "").lower() == listing_filter.lower()]
    if category_filter not in ("", "All"):
        entries = [e for e in entries if str(e.get("category") or "") == category_filter]
    if type_filter not in ("", "All"):
        want = gzo_filters.normalize_type(type_filter) or type_filter
        entries = [e for e in entries if str(e.get("type") or "").lower() == want.lower()]
    if maker_filter not in ("", "All"):
        entries = [e for e in entries if str(e.get("manufacturer") or "").lower() == maker_filter.lower()]
    type_pool = all_entries
    if category_filter not in ("", "All"):
        type_pool = [e for e in all_entries if str(e.get("category") or "") == category_filter]
    types = ["All", *gzo_filters.ordered_labels([str(e.get("type") or "") for e in type_pool], gzo_filters.TYPE_ORDER)]
    categories = ["All", *gzo_filters.ordered_labels([str(e.get("category") or "") for e in all_entries], gzo_filters.CATEGORY_ORDER)]
    manufacturers = ["All"] + sorted(
        {str(e.get("manufacturer") or "").strip() for e in all_entries if str(e.get("manufacturer") or "").strip()},
        key=str.lower,
    )
    listings = ["All", "Legit", "Modded"]
    filtered = _search_rows(
        entries,
        search,
        "title",
        "serial",
        "id",
        "listing",
        "type",
        "category",
        "manufacturer",
        "rarity",
        "character_class",
    )
    total = len(filtered)
    limit = max(1, min(int(payload.get("limit") or 2000), 10000))
    entries = filtered[:limit]
    extra = {
        "listings": listings,
        "categories": categories,
        "types": types,
        "manufacturers": manufacturers,
        "total": total,
    }
    if not entries:
        hint = " Refresh GZO in-game once, then retry."
        if listing_filter not in ("", "All"):
            hint = f" No {listing_filter} entries in cache.{hint}"
        elif category_filter not in ("", "All") or type_filter not in ("", "All"):
            hint = f" No matches for that item type.{hint}"
        return _ok(f"No GZO cache entries.{hint}", rows=[], **extra)
    if total > len(entries):
        return _ok(
            f"{len(entries)} of {total} GZO code(s) (raise list limit or use Select all filtered before Deliver).",
            rows=entries,
            **extra,
        )
    return _ok(f"{len(entries)} GZO code(s).", rows=entries, **extra)


def catalog_lootlemon(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    search = str(payload.get("search") or "")
    category = str(payload.get("category") or "All")
    dynamic_name = "Squ1ggsBoostingTools_lootlemon_codes.json"
    seed_name = "squ1ggs_lootlemon_codes.json"
    roots: list[Path] = [_mod_dir()]
    try:
        cwd = Path.cwd()
        roots.extend((cwd / "sdk_mods", cwd))
    except Exception:
        pass
    try:
        saved = Path.home() / "Documents" / "My Games" / "Borderlands 4" / "Saved"
        roots.append(saved)
    except Exception:
        pass
    dynamic_paths = [root / dynamic_name for root in roots]
    seed_paths = [root / seed_name for root in roots]
    data: dict[str, Any] | list[Any] | None = None
    # A refreshed writable cache always wins over the bundled lowercase seed.
    # Within each group prefer the newest valid file.
    for candidates in (dynamic_paths, seed_paths):
        existing: list[Path] = []
        for path in candidates:
            try:
                if path.exists():
                    existing.append(path)
            except Exception:
                continue
        existing.sort(
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for path in existing:
            loaded = _load_json_path(path)
            if isinstance(loaded, (dict, list)):
                data = loaded
                break
        if data is not None:
            break
    data = data or {}
    entries: list[dict[str, Any]] = []
    items = data.get("entries") if isinstance(data, dict) else data
    if isinstance(items, list):
        for row in items:
            if not isinstance(row, dict):
                continue
            if category != "All" and str(row.get("category") or "") != category:
                continue
            serial = str(row.get("serial") or "").strip()
            if not serial.startswith("@U"):
                continue
            name = str(row.get("name") or row.get("id") or serial[:24])
            entries.append(
                {
                    "title": name,
                    "serial": serial,
                    "category": str(row.get("category") or ""),
                    "rarity": str(row.get("rarity") or ""),
                }
            )
    category_pool = list(entries)
    filtered = _search_rows(entries, search, "title", "serial", "category", "rarity")
    total = len(filtered)
    limit = max(1, min(int(payload.get("limit") or 2000), 10000))
    entries = filtered[:limit]
    categories = sorted({str(row.get("category") or "") for row in category_pool if row.get("category")})
    if not entries:
        hint = " Lootlemon cache is empty — press Refresh Lootlemon, then Reload list."
        if category != "All":
            hint = f" No {category} entries in cache.{hint}"
        return _ok(f"No Lootlemon entries.{hint}", rows=[], categories=["All", *categories], total=total)
    if total > len(entries):
        return _ok(
            f"{len(entries)} of {total} Lootlemon code(s) (use Select all filtered before Deliver).",
            rows=entries,
            categories=["All", *categories],
            total=total,
        )
    return _ok(f"{len(entries)} Lootlemon code(s).", rows=entries, categories=["All", *categories], total=total)


def _mob_actor_sections() -> list[dict[str, str]]:
    data = _load_json_path(_BMS_DATA / "squ1ggs_actor_catalog.json") or {}
    out: list[dict[str, str]] = []
    for sec in data.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        sid = str(sec.get("id") or "").strip()
        title = str(sec.get("title") or sid).strip()
        if sid:
            out.append({"id": sid, "title": title})
    return out


def catalog_mob_actors(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    search = str(payload.get("search") or "")
    section = str(payload.get("section") or payload.get("category") or "All")
    limit = max(1, min(int(payload.get("limit") or 500), 2000))
    data = _load_json_path(_BMS_DATA / "squ1ggs_actor_catalog.json") or {}
    rows: list[dict[str, Any]] = []
    for sec in data.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        sid = str(sec.get("id") or "")
        title = str(sec.get("title") or "")
        if section not in ("All", "") and section not in (sid, title):
            continue
        for raw in sec.get("entries") or []:
            if not isinstance(raw, dict):
                continue
            code = str(raw.get("code") or "").strip()
            if not code or "_SHARED" in code:
                continue
            rows.append(
                {
                    "code": code,
                    "display_name": str(raw.get("display_name") or code),
                    "notes": str(raw.get("notes") or ""),
                    "section_id": sid,
                    "section_title": title,
                }
            )
    rows = _search_rows(rows, search, "code", "display_name", "notes", "section_title")[:limit]
    sections = _mob_actor_sections()
    return _ok(f"{len(rows)} mob actor(s).", rows=rows, sections=sections)


def catalog_io_spawns(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    search = str(payload.get("search") or "")
    category = str(payload.get("category") or "All")
    limit = max(1, min(int(payload.get("limit") or 500), 2000))
    try:
        from .embedded_bms.world_props_ui import load_io_categories, load_io_entries

        categories = ["All", *load_io_categories()]
        rows: list[dict[str, str]] = []
        for token, label, cmd, row_cat in load_io_entries():
            if category != "All" and row_cat != category:
                continue
            rows.append({"token": token, "label": label, "cmd": cmd, "category": row_cat})
        rows = _search_rows(rows, search, "token", "label", "category", "cmd")[:limit]
        return _ok(f"{len(rows)} IO spawn(s).", rows=rows, categories=categories)
    except Exception as exc:
        return _fail(repr(exc), rows=[], categories=["All"])


def catalog_encounter_presets(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    search = str(payload.get("search") or "")
    limit = max(1, min(int(payload.get("limit") or 100), 500))
    path = _BMS_DATA / "mob_encounter_presets.txt"
    rows: list[dict[str, str]] = []
    if path.is_file():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                label, cmd = [part.strip() for part in line.split("|", 1)]
            else:
                label, cmd = line, line
            if cmd:
                rows.append({"label": label, "line": cmd})
    rows = _search_rows(rows, search, "label", "line")[:limit]
    return _ok(f"{len(rows)} encounter preset(s).", rows=rows)


_LEGIT_TYPE_ORDER = (
    "pistol",
    "smg",
    "shotgun",
    "assault_rifle",
    "sniper",
    "shield",
    "repair_kit",
    "enhancement",
    "gadget",
    "heavy",
    "class_mod",
)


def _legit_type_options() -> list[str]:
    from . import legit_builder_core as core

    seen: set[str] = set()
    for row in core.roots():
        item_type = str(row.get("item_type") or "").strip()
        if item_type:
            seen.add(item_type)
    return [t for t in _LEGIT_TYPE_ORDER if t in seen] + sorted(seen.difference(_LEGIT_TYPE_ORDER))


def _legit_manufacturer_options(item_type: str) -> list[str]:
    from . import legit_builder_core as core

    out: set[str] = set()
    for row in core.roots():
        if str(row.get("item_type") or "") != item_type:
            continue
        manufacturer = str(row.get("manufacturer") or "").strip()
        if manufacturer:
            out.add(manufacturer)
    return sorted(out)


def _legit_root_rows(item_type: str, manufacturer: str, search: str = "") -> list[dict[str, Any]]:
    from . import legit_builder_core as core

    query = str(search or "").strip().lower()
    rows = [
        row
        for row in core.roots()
        if str(row.get("item_type") or "") == item_type and str(row.get("manufacturer") or "") == manufacturer
    ]
    if query:
        rows = [
            row
            for row in rows
            if query in str(row.get("key") or "").lower()
            or query in str(row.get("name") or "").lower()
            or query in str(row.get("build_label") or "").lower()
        ]
    out: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: (int(r.get("serial") or 0), str(r.get("key") or ""))):
        key = str(row.get("key") or "")
        out.append(
            {
                "key": key,
                "build_label": str(row.get("build_label") or row.get("name") or key),
                "serial": row.get("serial"),
                "item_type": str(row.get("item_type") or ""),
                "manufacturer": str(row.get("manufacturer") or ""),
                "part_count": len(row.get("parts") or []),
            }
        )
    return out


def catalog_legit_types(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del payload
    types = _legit_type_options()
    rows = [{"id": item_type, "label": item_type.replace("_", " ").title()} for item_type in types]
    return _ok(f"{len(rows)} item type(s).", rows=rows)


def catalog_legit_manufacturers(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    item_type = str(payload.get("item_type") or "").strip()
    if not item_type:
        return _ok("Select an item type first.", rows=[])
    rows = [{"id": name, "label": name.replace("_", " ").title()} for name in _legit_manufacturer_options(item_type)]
    return _ok(f"{len(rows)} manufacturer(s).", rows=rows)


def catalog_legit_roots(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    item_type = str(payload.get("item_type") or "").strip()
    manufacturer = str(payload.get("manufacturer") or "").strip()
    search = str(payload.get("search") or "")
    limit = max(1, min(int(payload.get("limit") or 500), 2000))
    if not item_type or not manufacturer:
        return _ok("Select item type and manufacturer first.", rows=[])
    rows = _legit_root_rows(item_type, manufacturer, search)[:limit]
    return _ok(f"{len(rows)} root(s).", rows=rows)


def catalog_legit_parts(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import legit_builder_core as core

    payload = payload or {}
    root_key = str(payload.get("root_key") or "").strip()
    search = str(payload.get("search") or "")
    table = str(payload.get("table") or "").strip() or None
    limit = max(1, min(int(payload.get("limit") or 200), 1000))
    if not root_key:
        return _ok("Select an item root first.", rows=[])
    rows: list[dict[str, Any]] = []
    for part in core.search_parts(root_key, search, table=table, limit=limit):
        key = str(part.get("key") or "")
        table_name = str(part.get("table") or "").strip()
        part_line = f"{table_name}:{key}" if table_name else key
        display = str(part.get("display") or key)
        rows.append(
            {
                "part_line": part_line,
                "display": display,
                "key": key,
                "table": table_name,
                "serial_token": str(part.get("serial_token") or ""),
                "rarity": str(part.get("rarity") or ""),
            }
        )
    return _ok(f"{len(rows)} part(s).", rows=rows)


def catalog_serial_store(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import serial_store

    payload = payload or {}
    search = str(payload.get("search") or "")
    group = str(payload.get("group") or "All")
    rows = serial_store.filter_entries(search=search, group=group)
    limit = max(1, min(int(payload.get("limit") or 500), 2000))
    out: list[dict[str, Any]] = []
    for row in rows[:limit]:
        out.append(
            {
                "id": str(row.get("id") or ""),
                "title": str(row.get("name") or row.get("id") or "Serial"),
                "name": str(row.get("name") or ""),
                "group": str(row.get("group") or "Default"),
                "serial": str(row.get("serial") or ""),
            }
        )
    groups = serial_store.groups()
    if not out:
        return _ok(
            "No saved serials yet. Import a pack, or choose New entry, paste a serial, then Save entry.",
            rows=[],
            groups=groups,
        )
    return _ok(f"{len(out)} saved serial(s).", rows=out, groups=groups, total=len(rows))


def catalog_vehicle_spawns(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import vehicle_spawn_bridge as vspawn

    payload = payload or {}
    search = str(payload.get("search") or "")
    category = str(payload.get("category") or "All")
    limit = int(payload.get("limit") or 500)
    try:
        rows = vspawn.list_entries(search=search, category=category, limit=limit)
        categories = vspawn.categories()
    except Exception as exc:
        return _fail(repr(exc), rows=[], categories=["All"])
    if not rows:
        return _ok(
            "No vehicles in catalog. Use Reload vehicle catalog (deep scan) in-game once, then retry.",
            rows=[],
            categories=categories,
        )
    return _ok(f"{len(rows)} vehicle(s).", rows=rows, categories=categories)


def catalog_challenges(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    search = str(payload.get("search") or "")
    category = str(payload.get("category") or "All non-UVHM")
    limit = max(1, min(int(payload.get("limit") or 5000), 5000))
    try:
        from .challenge_bulk_runtime import (
            CATEGORY_LABELS,
            catalog_rows,
            challenge_display_name,
        )

        rows_raw = catalog_rows(search, category, limit=limit)
    except Exception as exc:
        return _fail(f"Challenge catalog unavailable: {exc!r}", rows=[], categories=["All non-UVHM"])
    rows: list[dict[str, Any]] = []
    for token, goal in rows_raw:
        friendly = challenge_display_name(token)
        title = f"{friendly} — {token}" if friendly else token
        rows.append(
            {
                "token": token,
                "goal": int(goal),
                "title": f"{title}  [goal {goal}]",
                "name": friendly or token,
            }
        )
    return _ok(
        f"{len(rows)} challenge(s).",
        rows=rows,
        categories=list(CATEGORY_LABELS),
    )


def catalog_backpack(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .backpack_tools import scan_backpack_rows
    from .backend_actions import get_target_player_index, _payload_player_index

    payload = payload or {}
    parsed = _payload_player_index(payload)
    idx = get_target_player_index() if parsed is None else int(parsed)
    if idx < 0:
        return _fail(
            "Pick one boost target (not All players) to scan their backpack.",
            rows=[],
        )
    rows, message = scan_backpack_rows(idx)
    return _ok(message, rows=rows)


def catalog_bms_groups(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    _ = payload
    rows = enc.catalog_rows()
    st = enc.status()
    return _ok(
        str(st.get("message") or f"{len(rows)} group(s)."),
        rows=rows,
        running=bool(st.get("running")),
        complete=bool(st.get("complete")),
        wave_index=int(st.get("wave_index") or 0),
        wave_total=int(st.get("wave_total") or 0),
        alive=int(st.get("alive") or 0),
        options=st.get("options") or {},
        saves=list(st.get("saves") or []),
    )


_CATALOGS = {
    "manifest": lambda p: get_manifest(),
    "item_pools": catalog_item_pools,
    "travel": catalog_travel,
    "travel_maps": catalog_travel_maps,
    "travel_stations": catalog_travel_stations,
    "spawn_mixes": catalog_spawn_mixes,
    "gzo": catalog_gzo,
    "lootlemon": catalog_lootlemon,
    "serial_store": catalog_serial_store,
    "vehicle_spawns": catalog_vehicle_spawns,
    "mob_actors": catalog_mob_actors,
    "io_spawns": catalog_io_spawns,
    "encounter_presets": catalog_encounter_presets,
    "bms_groups": catalog_bms_groups,
    "challenges": catalog_challenges,
    "backpack": catalog_backpack,
    "legit_types": catalog_legit_types,
    "legit_manufacturers": catalog_legit_manufacturers,
    "legit_roots": catalog_legit_roots,
    "legit_parts": catalog_legit_parts,
}


def run_catalog(name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    handler = _CATALOGS.get(str(name or "").strip().lower())
    if handler is None:
        return _fail(f"Unknown catalog {name!r}.", known=sorted(_CATALOGS))
    return handler(payload or {})
