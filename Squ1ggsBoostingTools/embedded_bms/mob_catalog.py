"""Mob and mix spawn catalogs bundled with BMS (standalone; no gbx_actor_deploy required)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from unrealsdk import logging

DeployFn = Callable[..., tuple[bool, str]]


def _read_catalog_json(path: Path) -> Any | None:
    """Load bundled actor catalog (folder install or .sdkmod via open_in_mod_dir)."""
    try:
        from mods_base import open_in_mod_dir

        with open_in_mod_dir(path, binary=True) as fh:
            return json.loads(fh.read().decode("utf-8"))
    except Exception:
        pass
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

MAX_CATALOG_DEPLOY_COUNT = 999


def _clamp_catalog_count(count: int | float, *, max_cap: int | None = None) -> int:
    try:
        n = int(count)
    except (TypeError, ValueError):
        n = 1
    cap = max(1, min(MAX_CATALOG_DEPLOY_COUNT, int(max_cap if max_cap is not None else MAX_CATALOG_DEPLOY_COUNT)))
    return max(1, min(cap, n))


def _deploy_catalog_actor(deploy_fn: DeployFn, code: str, count: int) -> tuple[bool, str]:
    """Call deploy_fn once with a count when supported (Mob Spawner), else loop."""
    n = _clamp_catalog_count(count)
    try:
        return deploy_fn(code, count=n)
    except TypeError:
        last_msg = ""
        ok_any = False
        for _ in range(n):
            ok, msg = deploy_fn(code)
            last_msg = msg
            ok_any = ok_any or ok
            if not ok:
                break
        return ok_any, last_msg

MOD_DIR = Path(__file__).resolve().parent
CATALOG_JSON = MOD_DIR / "data" / "squ1ggs_actor_catalog.json"


@dataclass(slots=True)
class Squ1ggsActorEntry:
    code: str
    display_name: str
    notes: str = ""
    section_id: str = ""
    section_title: str = ""


@dataclass(slots=True)
class Squ1ggsCatalog:
    sections: list[dict[str, Any]]
    flat: list[Squ1ggsActorEntry]

    @property
    def section_titles(self) -> list[str]:
        return [str(s.get("title") or s.get("id") or "?") for s in self.sections]

    def entries_for_section(self, section_idx: int) -> list[Squ1ggsActorEntry]:
        if section_idx < 0 or section_idx >= len(self.sections):
            return []
        sec = self.sections[section_idx]
        out: list[Squ1ggsActorEntry] = []
        sid = str(sec.get("id") or "")
        title = str(sec.get("title") or "")
        for row in sec.get("entries") or []:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            out.append(
                Squ1ggsActorEntry(
                    code=code,
                    display_name=str(row.get("display_name") or code).strip(),
                    notes=str(row.get("notes") or "").strip(),
                    section_id=sid,
                    section_title=title,
                )
            )
        return out

    def search(self, section_idx: int, query: str, *, limit: int = 500) -> list[Squ1ggsActorEntry]:
        q = (query or "").strip().lower()
        pool = self.entries_for_section(section_idx)
        if not q:
            return pool[:limit]
        hits: list[Squ1ggsActorEntry] = []
        for row in pool:
            hay = f"{row.code} {row.display_name} {row.notes}".lower()
            if q in hay:
                hits.append(row)
                if len(hits) >= limit:
                    break
        return hits

    def search_all(self, query: str, *, limit: int = 500) -> list[Squ1ggsActorEntry]:
        q = (query or "").strip().lower()
        if not q:
            return self.flat[:limit]
        hits: list[Squ1ggsActorEntry] = []
        for row in self.flat:
            hay = f"{row.code} {row.display_name} {row.notes} {row.section_title}".lower()
            if q in hay:
                hits.append(row)
                if len(hits) >= limit:
                    break
        return hits


_CATALOG_CACHE: Squ1ggsCatalog | None = None
_SEARCH_CACHE_KEY: tuple[Any, ...] | None = None
_SEARCH_CACHE_HITS: list[Squ1ggsActorEntry] | None = None


def clear_squ1ggs_catalog_cache() -> None:
    global _CATALOG_CACHE, _SEARCH_CACHE_KEY, _SEARCH_CACHE_HITS
    _CATALOG_CACHE = None
    _SEARCH_CACHE_KEY = None
    _SEARCH_CACHE_HITS = None


def _cached_catalog_hits(
    catalog: Squ1ggsCatalog,
    *,
    sec_idx: int,
    query: str,
    search_all: bool,
    fav_sig: int = 0,
) -> list[Squ1ggsActorEntry]:
    global _SEARCH_CACHE_KEY, _SEARCH_CACHE_HITS
    key = (id(catalog), int(sec_idx), str(query or "").strip().lower(), bool(search_all), int(fav_sig))
    if _SEARCH_CACHE_HITS is not None and _SEARCH_CACHE_KEY == key:
        return list(_SEARCH_CACHE_HITS)
    if search_all:
        hits = catalog.search_all(query)
    else:
        hits = catalog.search(sec_idx, query)
    _SEARCH_CACHE_KEY = key
    _SEARCH_CACHE_HITS = hits
    return list(hits)


def load_squ1ggs_catalog(*, force: bool = False) -> Squ1ggsCatalog | None:
    global _CATALOG_CACHE
    if force:
        clear_squ1ggs_catalog_cache()
    if _CATALOG_CACHE is not None and not force:
        return _CATALOG_CACHE
    payload = _read_catalog_json(CATALOG_JSON)
    if not isinstance(payload, dict):
        logging.warning(f"[BMS] Actor catalog unavailable at {CATALOG_JSON}")
        return None
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return None
    flat: list[Squ1ggsActorEntry] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        sid = str(sec.get("id") or "")
        title = str(sec.get("title") or "")
        for row in sec.get("entries") or []:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            flat.append(
                Squ1ggsActorEntry(
                    code=code,
                    display_name=str(row.get("display_name") or code).strip(),
                    notes=str(row.get("notes") or "").strip(),
                    section_id=sid,
                    section_title=title,
                )
            )
    _CATALOG_CACHE = Squ1ggsCatalog(sections=sections, flat=flat)
    return _CATALOG_CACHE


def _collapsing_show(ret: Any) -> bool:
    try:
        if isinstance(ret, tuple):
            return bool(ret[0])
        return bool(ret)
    except Exception:
        return False


def _imgui_bool(ret: Any) -> bool:
    """Normalize bool / (bool, …) returns from imgui_bundle bindings."""
    return _collapsing_show(ret)


def _ui_set_attr(ui: Any, name: str, value: Any) -> None:
    """Set on slotted dataclasses; ignore if the host UI type has no slot."""
    try:
        setattr(ui, name, value)
    except AttributeError:
        pass


def _ui_get_attr(ui: Any, name: str, default: Any) -> Any:
    return getattr(ui, name, default)


def draw_squ1ggs_quick_pick(
    imgui: Any,
    ui: Any,
    *,
    deploy_fn: DeployFn,
    sync_filter_fn: Callable[[str], None] | None = None,
    id_prefix: str = "sq",
    list_height: float = 220.0,
    is_favorite: Callable[[str], bool] | None = None,
    toggle_favorite: Callable[[str, str], None] | None = None,
    sort_entries: Callable[[list[Squ1ggsActorEntry]], list[Squ1ggsActorEntry]] | None = None,
) -> None:
    """
    Shared ImGui block: section combo, filter, pick list, deploy buttons.

    ``deploy_fn`` receives gbxactor code (Char_*).
    ``sync_filter_fn`` optionally sets main catalog filter when a row is picked.
    """
    catalog = load_squ1ggs_catalog()
    if catalog is None:
        imgui.text_disabled(f"Missing {CATALOG_JSON.name} — bundled actor catalog unavailable.")
        return

    if not hasattr(ui, "squ1ggs_section_idx"):
        _ui_set_attr(ui, "squ1ggs_section_idx", 0)
    if not hasattr(ui, "squ1ggs_filter"):
        _ui_set_attr(ui, "squ1ggs_filter", "")
    if not hasattr(ui, "squ1ggs_selected_code"):
        _ui_set_attr(ui, "squ1ggs_selected_code", "")
    if not hasattr(ui, "squ1ggs_deploy_count"):
        _ui_set_attr(ui, "squ1ggs_deploy_count", 1)
    if not hasattr(ui, "squ1ggs_multi_select"):
        _ui_set_attr(ui, "squ1ggs_multi_select", set())
    if not hasattr(ui, "squ1ggs_multi_select_mode"):
        _ui_set_attr(ui, "squ1ggs_multi_select_mode", False)
    if not hasattr(ui, "squ1ggs_search_all"):
        _ui_set_attr(ui, "squ1ggs_search_all", False)

    sec_idx = max(0, min(int(_ui_get_attr(ui, "squ1ggs_section_idx", 0)), len(catalog.sections) - 1))
    titles = catalog.section_titles
    shortcuts = (
        ("Dedicated bosses", 0),
        ("True bosses", 1),
        ("Boss-rank", 2),
        ("NPCs", 3),
        ("Enemies", 4),
    )
    first_shortcut = True
    for label, idx in shortcuts:
        if idx >= len(catalog.sections):
            continue
        if not first_shortcut:
            imgui.same_line()
        first_shortcut = False
        if imgui.small_button(f"{label}##{id_prefix}_sec_{idx}"):
            ui.squ1ggs_section_idx = idx
            ui.squ1ggs_filter = ""
    imgui.spacing()
    if _imgui_bool(imgui.begin_combo(f"Category##{id_prefix}_sec", titles[sec_idx] if titles else "(none)")):
        for i, label in enumerate(titles):
            _clicked, selected = imgui.selectable(label, i == sec_idx)
            if _clicked:
                ui.squ1ggs_section_idx = i
        imgui.end_combo()

    sec = catalog.sections[sec_idx] if catalog.sections else {}
    subtitle = str(sec.get("subtitle") or "").strip()
    if subtitle:
        imgui.text_disabled(subtitle[:280])

    imgui.set_next_item_width(-280)
    _cf, ui.squ1ggs_filter = imgui.input_text(f"Search name / code##{id_prefix}_filt", str(ui.squ1ggs_filter), 96)
    imgui.same_line()
    if imgui.small_button(f"Clear##{id_prefix}_clr"):
        ui.squ1ggs_filter = ""
    imgui.same_line()
    if imgui.small_button(f"Reload##{id_prefix}_reload"):
        catalog = load_squ1ggs_catalog(force=True)
        if catalog is None:
            ui.error_text = "Catalog reload failed — rebuild squ1ggs_actor_catalog.json first."
        else:
            ui.status_text = f"Reloaded Squ1ggs catalog ({len(catalog.flat)} actors)."
            ui.error_text = ""
    _sa, ui.squ1ggs_search_all = imgui.checkbox(
        f"Search all sections##{id_prefix}_all",
        bool(ui.squ1ggs_search_all),
    )
    _cc, ui.squ1ggs_deploy_count = imgui.input_int(f"Spawn count##{id_prefix}_cnt", int(ui.squ1ggs_deploy_count))
    max_cap = int(getattr(ui, "max_deploy_count", MAX_CATALOG_DEPLOY_COUNT))
    ui.squ1ggs_deploy_count = _clamp_catalog_count(ui.squ1ggs_deploy_count, max_cap=max_cap)

    _ms, ui.squ1ggs_multi_select_mode = imgui.checkbox(
        f"Multi-select##{id_prefix}_msel",
        bool(ui.squ1ggs_multi_select_mode),
    )
    if ui.squ1ggs_multi_select_mode:
        sel_n = len(ui.squ1ggs_multi_select)
        imgui.same_line()
        imgui.text_disabled(f"Selected: {sel_n}")
        if sel_n and imgui.small_button(f"Clear##{id_prefix}_msel_clr"):
            ui.squ1ggs_multi_select.clear()

    if bool(ui.squ1ggs_search_all):
        hits = _cached_catalog_hits(
            catalog,
            sec_idx=sec_idx,
            query=str(ui.squ1ggs_filter),
            search_all=True,
        )
        scope_note = "all sections"
    else:
        hits = _cached_catalog_hits(
            catalog,
            sec_idx=sec_idx,
            query=str(ui.squ1ggs_filter),
            search_all=False,
        )
        scope_note = titles[sec_idx] if titles else "section"
    if sort_entries is not None:
        hits = sort_entries(hits)
    fav_count = sum(1 for row in hits if is_favorite and is_favorite(row.code))
    fav_note = f" · ★ {fav_count} in list" if is_favorite and fav_count else ""
    imgui.text_disabled(
        f"Matches: {len(hits)} in {scope_note} ({len(catalog.flat)} total catalog){fav_note}",
    )

    child_began = False
    try:
        child_open = _imgui_bool(imgui.begin_child(f"##{id_prefix}_list", (0, list_height)))
        child_began = True
        if child_open:
            list_cap = 250
            for row in hits[:list_cap]:
                fav = bool(is_favorite and is_favorite(row.code))
                multi_on = bool(ui.squ1ggs_multi_select_mode)
                in_multi = row.code in ui.squ1ggs_multi_select
                if toggle_favorite is not None:
                    fav_btn = "−" if fav else "+"
                    if imgui.small_button(f"{fav_btn}##{id_prefix}_fav_{row.code[:40]}"):
                        toggle_favorite(row.code, row.display_name)
                    imgui.same_line()
                prefix = "★ " if fav else ""
                if multi_on and in_multi:
                    prefix = "☑ " + prefix
                sec_hint = ""
                if bool(ui.squ1ggs_search_all):
                    sec_hint = f" [{row.section_title[:28]}]"
                label = f"{prefix}{row.display_name}{sec_hint}  ·  {row.code}"
                is_sel = in_multi if multi_on else row.code == str(ui.squ1ggs_selected_code)
                clicked, _sel = imgui.selectable(
                    f"{label}##{id_prefix}_{row.code}",
                    is_sel,
                )
                if clicked:
                    if multi_on:
                        if in_multi:
                            ui.squ1ggs_multi_select.discard(row.code)
                        else:
                            ui.squ1ggs_multi_select.add(row.code)
                    else:
                        ui.squ1ggs_selected_code = row.code
                        if sync_filter_fn is not None:
                            sync_filter_fn(row.code)
    finally:
        if child_began:
            imgui.end_child()

    code = str(getattr(ui, "squ1ggs_selected_code", "") or "").strip()
    if code and not ui.squ1ggs_multi_select_mode:
        imgui.text_wrapped(f"Selected: {code}")

    if ui.squ1ggs_multi_select_mode and ui.squ1ggs_multi_select:
        if imgui.button(f"Spawn selected ({len(ui.squ1ggs_multi_select)})##{id_prefix}_mspawn"):
            n = int(ui.squ1ggs_deploy_count)
            ok_any = False
            last_msg = ""
            for picked in sorted(ui.squ1ggs_multi_select):
                ok, msg = _deploy_catalog_actor(deploy_fn, picked, n)
                last_msg = msg
                ok_any = ok_any or ok
            ui.error_text = "" if ok_any else last_msg
            ui.status_text = last_msg
        imgui.same_line()
        if toggle_favorite is not None and imgui.button(f"Favorite selected##{id_prefix}_mfav"):
            for picked in sorted(ui.squ1ggs_multi_select):
                row_label = picked
                for row in hits:
                    if row.code == picked:
                        row_label = row.display_name
                        break
                toggle_favorite(picked, row_label)
            ui.status_text = f"Favorited {len(ui.squ1ggs_multi_select)} actor(s)."
        imgui.same_line()
        if imgui.button(f"Select visible##{id_prefix}_mvis"):
            for row in hits[:250]:
                ui.squ1ggs_multi_select.add(row.code)
            ui.status_text = f"Selected {min(len(hits), 250)} visible row(s)."

    if imgui.button(f"Spawn selected##{id_prefix}_deploy"):
        if not code:
            ui.error_text = "Pick an actor from the Squ1ggs list first."
        else:
            n = int(ui.squ1ggs_deploy_count)
            ok_any, last_msg = _deploy_catalog_actor(deploy_fn, code, n)
            ui.error_text = "" if ok_any else last_msg
            ui.status_text = last_msg

    imgui.same_line()
    if toggle_favorite is not None and code:
        fav_now = bool(is_favorite and is_favorite(code))
        fav_label = "Unfavorite" if fav_now else "Add favorite"
        if imgui.button(f"{fav_label}##{id_prefix}_fav"):
            row_label = code
            for row in hits:
                if row.code == code:
                    row_label = row.display_name
                    break
            toggle_favorite(code, row_label)

    if sync_filter_fn is not None:
        imgui.same_line()
        if imgui.button(f"Filter main catalog##{id_prefix}_sync"):
            if code:
                sync_filter_fn(code)
                ui.status_text = f"Main filter → {code}"
            else:
                ui.error_text = "Pick an actor first."

    imgui.text_disabled(
        "Boss picker for Char_* spawns. Use **F1 → Mob Spawner** (or Ctrl+F6) for aggro modes and spawn distance.",
    )
