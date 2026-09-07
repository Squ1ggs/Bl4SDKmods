"""Interactive object picker — catalog + favorites for IO spawner tab."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

RunLineFn = Callable[[str], tuple[bool, str]]

MOD_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = MOD_DIR.parent.parent.parent / "settings" / "squ1ggs_bms_favorites.json"
LEGACY_SETTINGS_PATH = MOD_DIR.parent.parent.parent / "settings" / "squ1ggs_bms.json"
PRESETS_PATH = MOD_DIR.parent / "gbx_actor_deploy" / "data" / "oak_spawnai_presets.txt"
CATALOG_PATH = MOD_DIR / "data" / "io_spawn_catalog.json"

_favorite_world_props: set[str] = set()
_favorite_world_prop_labels: dict[str, str] = {}
_presets_cache: list[tuple[str, str, str, str]] | None = None
_presets_mtime_ns: int | None = None
_catalog_cache: list[tuple[str, str, str, str]] | None = None
_catalog_mtime_ns: int | None = None
_categories_cache: list[str] | None = None
_io_filter_cache_key: tuple[str, str, int] | None = None
_io_filter_cache_rows: list[tuple[str, str, str, str]] | None = None


def _invalidate_io_filter_cache() -> None:
    global _io_filter_cache_key, _io_filter_cache_rows
    _io_filter_cache_key = None
    _io_filter_cache_rows = None


def is_worldpath_catalog_row(token: str, row_cat: str) -> bool:
    """Duplicate PersistentLevel picker rows — hidden unless show WorldPaths is on."""
    cat = str(row_cat or "").strip()
    if cat == "WorldPath":
        return True
    return str(token or "").strip().lower().startswith("persistentlevel.")


def _cached_filtered_presets(
    query: str, category: str = "", *, show_worldpaths: bool = False
) -> list[tuple[str, str, str, str]]:
    """Rebuild IO filter only when search/category/favorites change."""
    global _io_filter_cache_key, _io_filter_cache_rows
    key = (
        str(query or "").strip().lower(),
        str(category or "").strip().lower(),
        len(_favorite_world_props),
        bool(show_worldpaths),
    )
    if _io_filter_cache_rows is not None and _io_filter_cache_key == key:
        return list(_io_filter_cache_rows)
    rows = _sort_favorites_first(_filter_presets(query, category=category, show_worldpaths=show_worldpaths))
    _io_filter_cache_key = key
    _io_filter_cache_rows = rows
    return list(rows)


def _load_settings() -> dict[str, Any]:
    source = SETTINGS_PATH if SETTINGS_PATH.is_file() else LEGACY_SETTINGS_PATH
    if not source.is_file():
        return {}
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_settings(extra: dict[str, Any]) -> None:
    data = _load_settings()
    data.update(extra)
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    except OSError:
        pass


def _init_favorites_from_settings() -> None:
    global _favorite_world_props, _favorite_world_prop_labels
    data = _load_settings()
    _favorite_world_props = set(str(x) for x in data.get("favorite_world_props", []) if str(x).strip())
    raw_labels = data.get("favorite_world_prop_labels", {}) or {}
    _favorite_world_prop_labels = {
        str(k): str(v) for k, v in dict(raw_labels).items() if str(k).strip() and str(v).strip()
    }


_init_favorites_from_settings()


def _save_favorites() -> None:
    for key in list(_favorite_world_prop_labels):
        if key not in _favorite_world_props:
            _favorite_world_prop_labels.pop(key, None)
    _save_settings(
        {
            "favorite_world_props": sorted(_favorite_world_props),
            "favorite_world_prop_labels": dict(sorted(_favorite_world_prop_labels.items())),
        }
    )


def _is_io_token(token: str) -> bool:
    """Accept IO_*, Lootable_*, and PersistentLevel / World_P path forms."""
    raw = (token or "").strip()
    if not raw:
        return False
    low = raw.lower()
    if low.startswith("io_") or low.startswith("lootable_"):
        return True
    if "persistentlevel.io_" in low or "persistentlevel.lootable_" in low:
        return True
    if low.startswith("persistentlevel.io_") or low.startswith("persistentlevel.lootable_"):
        return True
    return False


_WORLD_P_IO_PREFIX = "/Game/Maps/WorldLevels/World_P.World_P:PersistentLevel."


def _short_io_token(token: str) -> str:
    """Normalize paths / aliases to a short IO_* / Lootable_* token when possible."""
    raw = (token or "").strip()
    if not raw:
        return ""
    if ":" in raw:
        raw = raw.rsplit(":", 1)[-1]
    if "." in raw:
        # PersistentLevel.IO_PlayerBank or ...PersistentLevel.IO_PlayerBank
        tail = raw.rsplit(".", 1)[-1]
        if tail.lower().startswith(("io_", "lootable_")):
            return tail
    return raw


def _world_path_cmd(token: str) -> str:
    try:
        from .io_activate import world_path_cmd  # noqa: PLC0415

        return world_path_cmd(token)
    except Exception:
        short = _short_io_token(token)
        if not short:
            return ""
        return f"oak_spawn {_WORLD_P_IO_PREFIX}{short}"


# Machines that often spawn Locked via oak_spawnai / script aliases — prefer world path.
# Keep this narrow: blanket "vendingmachine" forced oak_spawn find_all and hitch'd EXE clicks.
# Dual-sequence machines keep oak_spawnai; controller appends the world pass automatically.
# PlayerBank: NEVER world path — PersistentLevel duplicate freezes host / kicks lobby.
_PREFER_WORLD_PATH_SUBSTR: tuple[str, ...] = (
    "lostloot",
    "goldenchest",
    "firmware",
)

_DUAL_KEEP_AI_CMD_SUBSTR: tuple[str, ...] = (
    # Maurice / Black Market: world-template oak_spawn only (OakVendingMachine).
    "vendingmachine_munitions_splice",
    "lostloot",
    "goldenchest",
)


def _is_dual_auto_machine(token: str) -> bool:
    low = _short_io_token(token).lower().replace("-", "_")
    return any(s in low for s in _DUAL_KEEP_AI_CMD_SUBSTR)


def _prefer_world_path(token: str) -> bool:
    low = _short_io_token(token).lower()
    if _is_dual_auto_machine(low):
        return False
    return any(s in low for s in _PREFER_WORLD_PATH_SUBSTR)


def _parse_preset_line(raw: str) -> tuple[str, str, str, str] | None:
    line = raw.strip()
    if not line or line.startswith("#"):
        return None
    desc = ""
    cmd = line
    if " - " in line:
        cmd, desc = [x.strip() for x in line.split(" - ", 1)]
    elif "|" in line:
        cmd, desc = [x.strip() for x in line.split("|", 1)]
    cmd = cmd.strip()
    if not cmd.lower().startswith(("oak_spawnai", "oak_spawnai", "oak_spawn", "oak_spawn")):
        return None
    parts = cmd.split()
    if len(parts) < 2:
        return None
    token = parts[1].strip()
    if not _is_io_token(token):
        return None
    short = _short_io_token(token)
    is_world = "persistentlevel." in token.lower() or token.lower().startswith("/game/")
    label_base = (desc or short or token).strip()[:120]
    if is_world and "world" not in label_base.lower() and "persistent" not in label_base.lower():
        label = f"{label_base} (PersistentLevel)"[:120]
        category = "WorldPath"
        display_token = f"PersistentLevel.{short}" if short else token
    else:
        label = label_base
        category = "Presets"
        display_token = short or token
    return display_token, label, cmd, category


def _read_catalog_rows() -> list[tuple[str, str, str, str]]:
    global _catalog_cache, _catalog_mtime_ns, _categories_cache
    if not CATALOG_PATH.is_file():
        return []
    try:
        st = CATALOG_PATH.stat()
        mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
    except OSError:
        return []
    if _catalog_cache is not None and _catalog_mtime_ns == mtime_ns:
        return list(_catalog_cache)
    try:
        doc = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows: list[tuple[str, str, str, str]] = []
    cats: list[str] = []
    seen: set[str] = set()
    if isinstance(doc, dict):
        cats = [str(c) for c in doc.get("categories", []) if str(c).strip()]
        for entry in doc.get("entries", []):
            if not isinstance(entry, dict):
                continue
            token = str(entry.get("token", "") or "").strip()
            if not _is_io_token(token):
                continue
            short = _short_io_token(token)
            try:
                from .io_activate import (  # noqa: PLC0415
                    canonical_io_token,
                    is_hidden_io_token,
                    is_oak_dual_vending,
                    oak_dual_cmd,
                )

                if is_hidden_io_token(token):
                    continue
                if is_catalog_excluded_io(token, str(entry.get("label", "") or "")):
                    continue
                short = canonical_io_token(token) or short
            except Exception:
                is_oak_dual_vending = lambda _t: False  # type: ignore[assignment,misc]
                oak_dual_cmd = lambda _t: ""  # type: ignore[assignment,misc]
            label = str(entry.get("label", short or token) or short or token).strip()[:120]
            cmd = str(entry.get("cmd", f"oak_spawnai {short}") or f"oak_spawnai {short}").strip()
            category = str(entry.get("category", "Other") or "Other").strip()[:48]
            # One row only: Maurice's Black Market (IO_VendingMachine_BlackMarket).
            if is_oak_dual_vending(short):
                label = "Maurice's Black Market Machine"
                cmd = oak_dual_cmd(short) or "oak_dual IO_VendingMachine_BlackMarket"
                category = "Presets"
                short = "IO_VendingMachine_BlackMarket"
            key = short.lower()
            # Collapse any alias / leftover dual rows onto a single Maurice key.
            if is_oak_dual_vending(short) or "maurice" in label.lower() or "black market" in label.lower():
                key = "io_vendingmachine_blackmarket"
                short = "IO_VendingMachine_BlackMarket"
                label = "Maurice's Black Market Machine"
                cmd = "oak_dual IO_VendingMachine_BlackMarket"
                category = "Presets"
            if key and key not in seen:
                seen.add(key)
                # Prefer unlocked world path for banks / vending / similar machines.
                # Dual-auto / oak-dual machines keep their curated command.
                # PlayerBank: never PersistentLevel clone (freezes host / kicks lobby).
                if is_oak_dual_vending(short) or key == "io_vendingmachine_blackmarket":
                    pass
                elif "playerbank" in short.lower() or short.lower() in ("bank", "io_playerbank"):
                    cmd = f"oak_spawnai {short if short.lower().startswith('io_') else 'IO_PlayerBank'}"
                elif _prefer_world_path(short):
                    wcmd = _world_path_cmd(short)
                    if wcmd:
                        cmd = wcmd
                elif _is_dual_auto_machine(short):
                    cmd = f"oak_spawnai {short}"
                rows.append((short, label, cmd, category))
            # Extra PersistentLevel rows only for machines that still need a manual
            # world-path pick. Dual-auto / oak-dual / PlayerBank stay as one row.
            if (
                short.lower().startswith("io_")
                and not _is_dual_auto_machine(short)
                and not is_oak_dual_vending(short)
                and "playerbank" not in short.lower()
            ):
                wkey = f"persistentlevel.{short.lower()}"
                if wkey not in seen:
                    seen.add(wkey)
                    wcmd = _world_path_cmd(short)
                    if wcmd:
                        rows.append(
                            (
                                f"PersistentLevel.{short}",
                                f"{label} (PersistentLevel)",
                                wcmd,
                                "WorldPath",
                            )
                        )
    # Merge preset-file lines (includes hand-tuned PersistentLevel paths).
    if PRESETS_PATH.is_file():
        try:
            for raw in PRESETS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
                got = _parse_preset_line(raw)
                if got is None:
                    continue
                token, label, cmd, category = got
                key = token.lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append((token, label, cmd, category))
        except OSError:
            pass
    if "WorldPath" not in cats:
        cats = ["WorldPath", *cats]
    _catalog_cache = rows
    _catalog_mtime_ns = mtime_ns
    _categories_cache = cats or sorted({r[3] for r in rows})
    return list(rows)


def load_world_prop_presets(*, reload: bool = False) -> list[tuple[str, str, str]]:
    """Legacy API — (token, label, cmd)."""
    return [(t, l, c) for t, l, c, _cat in load_io_entries(reload=reload)]


def load_io_entries(*, reload: bool = False) -> list[tuple[str, str, str, str]]:
    """Return (token, label, full_command, category)."""
    global _presets_cache, _presets_mtime_ns, _catalog_cache
    if reload:
        _presets_cache = None
        _catalog_cache = None
        _invalidate_io_filter_cache()
    catalog_rows = _read_catalog_rows()
    if catalog_rows:
        return catalog_rows
    if not PRESETS_PATH.is_file():
        return []
    try:
        st = PRESETS_PATH.stat()
        mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
    except OSError:
        return []
    if not reload and _presets_cache is not None and _presets_mtime_ns == mtime_ns:
        return list(_presets_cache)
    rows: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    try:
        text = PRESETS_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for raw in text.splitlines():
        got = _parse_preset_line(raw)
        if got is None:
            continue
        token, label, cmd, category = got
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append((token, label, cmd, category))
    _presets_cache = rows
    _presets_mtime_ns = mtime_ns
    return list(rows)


def load_io_categories(*, reload: bool = False, show_worldpaths: bool = False) -> list[str]:
    if reload:
        _read_catalog_rows()
    if _categories_cache:
        cats = list(_categories_cache)
    else:
        rows = load_io_entries(reload=reload)
        cats = sorted({r[3] for r in rows})
    if not show_worldpaths:
        cats = [c for c in cats if c != "WorldPath"]
    return cats


def _filter_presets(
    query: str, category: str = "", *, show_worldpaths: bool = False
) -> list[tuple[str, str, str, str]]:
    q = (query or "").strip().lower()
    cat = (category or "").strip().lower()
    rows = load_io_entries()
    out: list[tuple[str, str, str, str]] = []
    for token, label, cmd, row_cat in rows:
        if not show_worldpaths and is_worldpath_catalog_row(token, row_cat):
            continue
        if cat and cat not in ("all", "*") and row_cat.lower() != cat:
            continue
        if q:
            blob = f"{token} {label} {cmd} {row_cat}".lower()
            if q not in blob:
                continue
        out.append((token, label, cmd, row_cat))
    return out


def _sort_favorites_first(rows: list[tuple[str, str, str, str]]) -> list[tuple[str, str, str, str]]:
    return sorted(rows, key=lambda row: (0 if row[0].lower() in _favorite_world_props else 1, row[3].lower(), row[1].lower()))


def _remove_favorite(token: str) -> None:
    low = str(token or "").strip().lower()
    if low in _favorite_world_props:
        _favorite_world_props.discard(low)
        _favorite_world_prop_labels.pop(low, None)
        _save_favorites()
        _invalidate_io_filter_cache()


def _toggle_favorite(token: str, label: str) -> None:
    key = token.strip()
    if not key:
        return
    low = key.lower()
    if low in _favorite_world_props:
        _favorite_world_props.discard(low)
    else:
        _favorite_world_props.add(low)
        _favorite_world_prop_labels[low] = label
    _save_favorites()
    _invalidate_io_filter_cache()


def _imgui_bool(ret: Any) -> bool:
    try:
        if isinstance(ret, tuple):
            return bool(ret[0])
        return bool(ret)
    except Exception:
        return False


def _draw_io_list(
    imgui: Any,
    ui: Any,
    hits: list[tuple[str, str, str, str]],
    *,
    run_line: RunLineFn,
    id_prefix: str,
    list_height: float,
) -> None:
    sel = str(getattr(ui, "world_prop_selected", "") or "").strip()
    idx = int(getattr(ui, "world_prop_idx", 0) or 0)
    if hits:
        idx = max(0, min(len(hits) - 1, idx))
        ui.world_prop_idx = idx
    else:
        idx = 0

    child_began = False
    try:
        child_open = _imgui_bool(imgui.begin_child(f"##{id_prefix}_wplist", (0, list_height)))
        child_began = True
        if child_open:
            cap = 80
            for i, (token, label, cmd, category) in enumerate(hits[:cap]):
                fav = token.lower() in _favorite_world_props
                if imgui.small_button(f"{'−' if fav else '+'}##{id_prefix}_wpf_{i}"):
                    _toggle_favorite(token, label)
                imgui.same_line()
                row_label = f"{'★ ' if fav else ''}{label}  ·  {token}"
                if category and category != "Presets":
                    row_label += f"  [{category}]"
                clicked, _sel = imgui.selectable(f"{row_label}##{id_prefix}_wp_{i}", i == idx)
                if clicked:
                    ui.world_prop_idx = i
                    ui.world_prop_selected = token
    finally:
        if child_began:
            imgui.end_child()
    if len(hits) > 80:
        imgui.text_disabled(f"Showing first 80 of {len(hits)} — narrow search or pick a category.")

    if hits:
        token, label, cmd, _category = hits[idx]
        ui.world_prop_selected = token
        imgui.text_wrapped(f"Selected: {token}")
        imgui.text_disabled(cmd[:140])

        if imgui.button(f"Spawn##{id_prefix}_spawn"):
            ok, msg = run_line(cmd)
            ui.status_text = msg
            ui.error_text = "" if ok else msg
        imgui.same_line()
        fav_now = token.lower() in _favorite_world_props
        fav_label = "Unfavorite" if fav_now else "Add favorite"
        if imgui.button(f"{fav_label}##{id_prefix}_fav"):
            _toggle_favorite(token, label)
        imgui.same_line()
        if imgui.button(f"Copy command##{id_prefix}_copy"):
            ui.status_text = cmd
    elif str(getattr(ui, "world_prop_filter", "") or "").strip() or str(getattr(ui, "io_category", "") or "").strip():
        imgui.text_colored((1.0, 0.75, 0.35, 1.0), "No entries matched — clear filters or run build_io_catalog.py.")


def draw_world_props_section(
    imgui: Any,
    ui: Any,
    *,
    run_line: RunLineFn,
    id_prefix: str = "mob_wp",
) -> None:
    imgui.text_wrapped(
        "Quick io_* presets. For the full catalog use the **Interactive Objects** tab (F1 → Mod Menu).",
    )
    if imgui.button(f"Open IO tab hint##{id_prefix}_hint"):
        ui.status_text = "F1 → BL4 Mod Menu → Interactive Objects tab."
    imgui.same_line()
    if imgui.button(f"Reload list##{id_prefix}_reload"):
        load_io_entries(reload=True)
        _invalidate_io_filter_cache()
    imgui.text_disabled(f"Catalog: {CATALOG_PATH.name if CATALOG_PATH.is_file() else PRESETS_PATH.name}")

    _cf, ui.world_prop_filter = imgui.input_text(
        f"Search io_*##{id_prefix}_filt",
        str(getattr(ui, "world_prop_filter", "") or ""),
        96,
    )
    hits = _cached_filtered_presets(
        str(ui.world_prop_filter),
        show_worldpaths=bool(getattr(ui, "show_worldpaths", False)),
    )
    imgui.text_disabled(f"Matches: {len(hits)}  ·  Favorites: {len(_favorite_world_props)}")
    _draw_io_list(imgui, ui, hits, run_line=run_line, id_prefix=id_prefix, list_height=220.0)
    _draw_favorites_row(imgui, ui, run_line=run_line, id_prefix=id_prefix)


def draw_io_spawner_panel(
    imgui: Any,
    ui: Any,
    *,
    run_line: RunLineFn,
    activate_fn: Callable[[], tuple[bool, str]] | None = None,
    id_prefix: str = "io_tab",
) -> None:
    imgui.text_wrapped(
        "Spawn **IO_*** interactives via Squ1ggs SSP. Pick one machine and Spawn — "
        "Maurice's Black Market / bank finish setup automatically after a short settle. "
        "If Maurice's Black Market looks blank, wait 2–3s or spawn any other IO nearby "
        "once (that wake-up finishes the machine), then Activate last IO if needed. "
        "Star favorites — saved in settings/bl4_mob_spawner_hookedwidget.json.",
    )
    if imgui.button(f"Player Bank##{id_prefix}_bank"):
        # AI + activate only — world PersistentLevel clone freezes / kicks lobby.
        ok, msg = run_line("oak_spawnai IO_PlayerBank")
        if ok:
            try:
                if callable(activate_fn):
                    _a_ok, a_msg = activate_fn()
                else:
                    from .io_activate import activate_spawned_io  # noqa: PLC0415

                    _a_ok, a_msg = activate_spawned_io("IO_PlayerBank")
                msg = f"{msg}; {a_msg}"
            except Exception as act_ex:  # noqa: BLE001
                msg = f"{msg}; activate: {type(act_ex).__name__}"
        ui.status_text = msg
        ui.error_text = "" if ok else msg
    imgui.same_line()
    if imgui.button(f"Activate last IO##{id_prefix}_act"):
        if callable(activate_fn):
            ok, msg = activate_fn()
            ui.status_text = msg
            ui.error_text = "" if ok else msg
        else:
            try:
                from .io_activate import activate_spawned_io  # noqa: PLC0415

                ok, msg = activate_spawned_io()
                ui.status_text = msg
                ui.error_text = "" if ok else msg
            except Exception as ex:  # noqa: BLE001
                ui.error_text = str(ex)
    imgui.same_line()
    if imgui.button(f"Ascension SingleTP##{id_prefix}_asc_tp"):
        run_line("oak_spawnai IO_AscensionBeam_SingleTP")
    imgui.same_line()
    if imgui.button(f"Ascension V1 beam##{id_prefix}_asc_v1"):
        run_line("oak_spawnai IO_AscensionBeam")
    imgui.same_line()
    if imgui.button(f"Reload catalog##{id_prefix}_reload"):
        load_io_entries(reload=True)
        _invalidate_io_filter_cache()
    imgui.text_disabled(
        "Ascension tip: SingleTP is simplest. Full V2 needs Manager + V4 + Waypoints (map wiring) — "
        "spawn alone may only show mesh/FX.",
    )
    src = CATALOG_PATH if CATALOG_PATH.is_file() else PRESETS_PATH
    total = len(load_io_entries())
    imgui.text_disabled(f"{total} entries · {src.name}")

    show_wp = bool(getattr(ui, "show_worldpaths", False))
    _wp_changed, show_wp = imgui.checkbox(f"Show WorldPaths##{id_prefix}_worldpath", show_wp)
    ui.show_worldpaths = show_wp
    if _wp_changed:
        _invalidate_io_filter_cache()
        if not show_wp and str(getattr(ui, "io_category", "")).strip() == "WorldPath":
            ui.io_category = "All"
            ui.io_category_idx = 0
    if imgui.is_item_hovered():
        imgui.set_tooltip(
            "PersistentLevel duplicate rows (advanced). Most IOs use oak_spawnai — "
            "only enable for bank/vending fallbacks."
        )
    if show_wp:
        imgui.same_line()
        imgui.text_disabled("(PersistentLevel duplicates visible)")

    categories = ["All"] + load_io_categories(show_worldpaths=show_wp)
    cat_idx = int(getattr(ui, "io_category_idx", 0) or 0)
    cat_idx = max(0, min(len(categories) - 1, cat_idx))
    ui.io_category_idx = cat_idx
    ui.io_category = categories[cat_idx] if categories else "All"
    if categories:
        _cc, ui.io_category_idx = imgui.combo(
            f"Category##{id_prefix}_cat",
            cat_idx,
            categories,
        )
        ui.io_category = categories[int(ui.io_category_idx)]

    _cf, ui.world_prop_filter = imgui.input_text(
        f"Search##{id_prefix}_filt",
        str(getattr(ui, "world_prop_filter", "") or ""),
        96,
    )
    cat_filter = "" if str(ui.io_category).lower() == "all" else str(ui.io_category)
    hits = _cached_filtered_presets(
        str(ui.world_prop_filter), category=cat_filter, show_worldpaths=show_wp
    )
    imgui.text_disabled(f"Matches: {len(hits)}  ·  Favorites: {len(_favorite_world_props)}")
    _draw_io_list(imgui, ui, hits, run_line=run_line, id_prefix=id_prefix, list_height=420.0)
    _draw_favorites_row(imgui, ui, run_line=run_line, id_prefix=id_prefix)


def _draw_favorites_row(imgui: Any, ui: Any, *, run_line: RunLineFn, id_prefix: str) -> None:
    if not _favorite_world_props:
        return
    imgui.separator()
    imgui.text("Favorites")
    for fav_key in sorted(_favorite_world_props):
        label = _favorite_world_prop_labels.get(fav_key, fav_key)
        if imgui.small_button(f"{label}##{id_prefix}_favbtn_{fav_key[:24]}"):
            cmd = f"oak_spawnai {fav_key}"
            for token, lbl, full, _cat in load_io_entries():
                if token.lower() == fav_key:
                    cmd = full
                    label = lbl
                    break
            ok, msg = run_line(cmd)
            ui.status_text = msg
            ui.error_text = "" if ok else msg
        if imgui.is_item_hovered():
            imgui.set_tooltip(fav_key)
        imgui.same_line()
        if imgui.small_button(f"-##{id_prefix}_rm_fav_{fav_key[:20]}"):
            _remove_favorite(fav_key)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Remove from favorites")
        imgui.same_line()
    imgui.new_line()
    if imgui.small_button(f"Clear all favorites##{id_prefix}_clear_fav"):
        _favorite_world_props.clear()
        _favorite_world_prop_labels.clear()
        _save_favorites()
        _invalidate_io_filter_cache()

