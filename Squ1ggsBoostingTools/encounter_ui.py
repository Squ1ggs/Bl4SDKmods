"""In-game BMS group spawner (sequenced Char_* packs)."""

from __future__ import annotations

from typing import Callable

import blimgui as _blimgui

from . import encounter_builder as _enc
from .embedded_bms import get_controller
from .squ1ggs_theme import ACCENT_PRIMARY

_save_name = ""
_load_index = 0


def _sync_options_from_bms() -> None:
    try:
        ui = get_controller().ui
    except Exception:
        return
    _enc.set_options(
        {
            "aggro_mode": str(getattr(ui, "aggro_mode", "attack_me") or "attack_me"),
            "spawn_anchor": str(getattr(ui, "spawn_anchor", "local") or "local"),
            "player_index": int(getattr(ui, "party_index", 0) or 0),
            "distance": max(600.0, float(getattr(ui, "spawn_distance", 900.0) or 900.0)),
            "spacing": float(getattr(ui, "spawn_spacing", 125.0) or 125.0),
        }
    )


def draw_encounter_builder_tab(
    *,
    muted_wrapped: Callable[[str], None],
    begin_card: Callable[..., bool],
    end_card: Callable[[], None],
    tab_height: float,
    combo: Callable[..., int],
    input_text: Callable[..., str],
) -> None:
    imgui = _blimgui.imgui
    global _save_name, _load_index
    opened = begin_card("BMS group spawner", ACCENT_PRIMARY, min(420.0, tab_height * 0.62))
    if not opened:
        return
    muted_wrapped(
        "SQBT Mob Spawner groups: pick a Char_* on Mob Spawner, Add as next group, then Start. "
        "On clear = next group when this pack is dead. World spawn only — not mailbox."
    )
    code = ""
    count = 1
    try:
        ui = get_controller().ui
        code = str(getattr(ui, "squ1ggs_selected_code", "") or "").strip()
        count = max(1, int(getattr(ui, "squ1ggs_deploy_count", 1) or 1))
    except Exception:
        pass
    if code:
        imgui.text_wrapped(f"Mob Spawner pick: {code} × {count}")
    else:
        muted_wrapped("No Mob Spawner pick yet — open Mob Spawner, select a Char_*, set count.")
    if imgui.button("Add as next group##enc_add") and code:
        _sync_options_from_bms()
        _enc.add_wave({"codes": [code], "count": count})
    imgui.same_line()
    if imgui.button("Remove last group##enc_pop"):
        st_now = _enc.status()
        total = int(st_now.get("wave_total") or 0)
        if total:
            _enc.remove_wave({"wave_index": total - 1})

    st = _enc.status()
    imgui.text_wrapped(str(st.get("message") or ""))
    waves = st.get("waves") or []
    if waves:
        imgui.text_wrapped(
            f"Plan: {len(waves)} group(s) · current {int(st.get('wave_index') or 0) + 1}/{len(waves)} · "
            f"{'RUNNING' if st.get('running') else 'idle'}"
        )
        for idx, wave in enumerate(waves[:12]):
            imgui.text_wrapped(f"  {idx + 1}. {wave.get('label')} ({wave.get('count')})")
        if len(waves) > 12:
            imgui.text_wrapped(f"  … {len(waves) - 12} more")
    else:
        muted_wrapped("No groups yet.")

    opts = st.get("options") or _enc.default_options()
    adv_labels = ["On clear", "Timed", "Manual"]
    adv_keys = ["on_clear", "timed", "manual"]
    adv_idx = adv_keys.index(str(opts.get("advance") or "on_clear")) if str(opts.get("advance")) in adv_keys else 0
    adv_idx = combo("Advance###enc_adv", adv_idx, adv_labels)
    loop_labels = ["Off", "Repeat last group", "Loop all groups"]
    loop_keys = ["off", "last", "all"]
    loop_idx = loop_keys.index(str(opts.get("loop") or "off")) if str(opts.get("loop")) in loop_keys else 0
    loop_idx = combo("Loop###enc_loop", loop_idx, loop_labels)
    want_adv = adv_keys[adv_idx]
    want_loop = loop_keys[loop_idx]
    if want_adv != str(opts.get("advance")) or want_loop != str(opts.get("loop")):
        _enc.set_options({"advance": want_adv, "loop": want_loop})

    if imgui.button("Start groups##enc_start"):
        _sync_options_from_bms()
        _enc.start({})
    imgui.same_line()
    if imgui.button("Stop##enc_stop"):
        _enc.stop({})
    imgui.same_line()
    if imgui.button("Next group##enc_next"):
        _enc.next_wave({})
    if imgui.button("Clear plan##enc_plan"):
        _enc.clear_plan({})
    imgui.same_line()
    if imgui.button("Clear live mobs##enc_live"):
        _enc.clear_live({})

    saves = list(st.get("saves") or [])
    if saves:
        names = ["(pick saved)", *saves]
        prev = _load_index
        _load_index = combo("Load saved###enc_load", _load_index, names)
        if _load_index != prev and _load_index > 0:
            _enc.load_named({"name": names[_load_index]})
    _save_name = input_text("Save as###enc_save_name", _save_name, 48)
    if imgui.button("Save groups##enc_save") and str(_save_name or "").strip():
        _enc.save_named({"name": _save_name})
    end_card()
