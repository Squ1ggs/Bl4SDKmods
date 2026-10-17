"""Mixed mob spawner tab."""

from __future__ import annotations

from typing import Any, Callable

import blimgui as _blimgui

from . import world_spawn as _spawn
from .squ1ggs_theme import ACCENT_INFO, ACCENT_PRIMARY, ACCENT_SUCCESS

_PAGE_SIZE = 14
_state: dict[str, Any] = {
    "search": "",
    "category_index": 0,
    "page": 0,
    "selected_index": 0,
    "count": 1,
    "aggro_index": 0,
    "anchor_index": 0,
    "party_index": 2,
    "status": "",
}

_AGGRO = [
    ("attack_me", "Attack host"),
    ("attack_party", "Attack party player"),
    ("free_for_all", "Attack each other"),
    ("none", "No forced aggro"),
]

_ANCHORS = [
    ("local", "From me"),
    ("party", "From selected player"),
    ("npc_nearest", "Near nearest NPC"),
]


def _categories() -> list[str]:
    return ["All", *_spawn.categories()]


def _current_rows() -> list[dict[str, str]]:
    cats = _categories()
    idx = max(0, min(int(_state["category_index"]), len(cats) - 1))
    return _spawn.filter_entries(str(_state["search"]), cats[idx])


def _page_rows() -> list[dict[str, str]]:
    rows = _current_rows()
    page = max(0, int(_state["page"]))
    start = page * _PAGE_SIZE
    return rows[start : start + _PAGE_SIZE]


def _selected_row() -> dict[str, str] | None:
    rows = _page_rows()
    if not rows:
        return None
    idx = max(0, min(int(_state["selected_index"]), len(rows) - 1))
    return rows[idx]


def draw_world_spawn_tab(
    *,
    button: Callable[..., None],
    input_text: Callable[..., str],
    combo: Callable[..., int],
    checkbox: Callable[[str, bool], bool],
    muted_wrapped: Callable[[str], None],
    begin_card: Callable[..., bool],
    end_card: Callable[[], None],
    tab_height: float,
) -> None:
    del checkbox
    imgui = _blimgui.imgui
    cats = _categories()
    all_rows = _current_rows()
    page_rows = _page_rows()
    max_page = max(0, (len(all_rows) - 1) // _PAGE_SIZE) if all_rows else 0
    if int(_state["page"]) > max_page:
        _state["page"] = max_page

    muted_wrapped(
        "Spawns prebuilt groups of enemies and NPCs via the bundled mob spawner. "
        "Placement needs an in-world character and local session authority."
    )
    if not _spawn.is_host():
        muted_wrapped(
            "No local session authority was detected. You can configure the menu, "
            "but the game may reject the spawn request."
        )

    opened = begin_card("Mixed Mob Spawner", ACCENT_PRIMARY, min(420.0, tab_height * 0.72))
    if opened:
        _state["search"] = input_text("Search group###sqbt_ws_search", str(_state["search"]), 96)
        _state["category_index"] = combo("Category###sqbt_ws_cat", int(_state["category_index"]), cats)

        if page_rows:
            labels = [f"{r['mix_id']}  [{r['category']}]" for r in page_rows]
            _state["selected_index"] = combo("Spawn group###sqbt_ws_pick", int(_state["selected_index"]), labels)
        else:
            muted_wrapped("No spawn groups match the filter.")

        changed, count = imgui.input_int("Quantity###sqbt_ws_count", int(_state["count"]))
        if changed:
            _state["count"] = max(1, min(int(count), 100))
        _state["aggro_index"] = combo(
            "Aggro target###sqbt_ws_aggro",
            int(_state["aggro_index"]),
            [label for _mode, label in _AGGRO],
        )
        _state["anchor_index"] = combo(
            "Spawn location###sqbt_ws_anchor",
            int(_state["anchor_index"]),
            [label for _mode, label in _ANCHORS],
        )
        aggro_idx = max(0, min(int(_state["aggro_index"]), len(_AGGRO) - 1))
        anchor_idx = max(0, min(int(_state["anchor_index"]), len(_ANCHORS) - 1))
        if _AGGRO[aggro_idx][0] == "attack_party" or _ANCHORS[anchor_idx][0] == "party":
            changed, party_index = imgui.input_int(
                "Party index (1-based)###sqbt_ws_party",
                int(_state["party_index"]),
            )
            if changed:
                _state["party_index"] = max(1, min(int(party_index), 8))

        button("Spawn Selected", _do_spawn_selected, ACCENT_SUCCESS, 140, 0)
        imgui.same_line()
        button("Prev Page", lambda: _state.update(page=max(0, int(_state["page"]) - 1)), ACCENT_INFO, 95, 0)
        imgui.same_line()
        button("Next Page", lambda: _state.update(page=min(max_page, int(_state["page"]) + 1)), ACCENT_INFO, 95, 0)
        muted_wrapped(f"Showing {len(page_rows)} of {len(all_rows)} spawn groups (page {int(_state['page']) + 1}/{max_page + 1}).")

        status = str(_state.get("status") or _spawn.last_status() or "")
        if status:
            muted_wrapped(status)
    end_card()


def _do_spawn_selected() -> None:
    row = _selected_row()
    if row is None:
        _state["status"] = "Nothing selected."
        return
    mix_id = str(row.get("mix_id", ""))
    aggro_idx = max(0, min(int(_state["aggro_index"]), len(_AGGRO) - 1))
    anchor_idx = max(0, min(int(_state["anchor_index"]), len(_ANCHORS) - 1))
    _ok, msg = _spawn.spawn_mix_def(
        mix_id,
        count=int(_state["count"]),
        aggro_mode=_AGGRO[aggro_idx][0],
        party_index=int(_state["party_index"]),
        spawn_anchor=_ANCHORS[anchor_idx][0],
    )
    _state["status"] = msg
