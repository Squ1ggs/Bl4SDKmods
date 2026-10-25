# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 RDPSqu1ggs
"""Render cached choices and enqueue actions; never inspect UObjects in ImGui."""
from .runtime import CONTROLLER

_search = ""
_model = ""
_owner = "self"
_group = "All"
_follow_pose = False
_keep_respawn = True
_game = 'All games'
_role = 'All characters'

def draw():
    global _search, _model, _owner, _group, _follow_pose, _keep_respawn, _game, _role
    from imgui_bundle import imgui
    from . import VERSION
    imgui.text(f"BL4 Character Swapper · {VERSION}")
    imgui.text_disabled("Created by RDPSqu1ggs · github.com/Squ1ggs/Bl4SDKmods")
    imgui.text_disabled("Standalone SDK mod · also included in Squ1ggs Boosting Tools")
    imgui.text_disabled("Visual swaps change appearance only; skills and controls stay the same.")
    choices = CONTROLLER.choices()
    from .packs.catalog import GAME_FILTERS, matches
    for label, options, current in [('Game', GAME_FILTERS, _game), ('Characters', ('All characters', 'Vault Hunters', 'Other characters'), _role)]:
        if imgui.begin_combo(label, current):
            for option in options:
                selected, _ = imgui.selectable(option, option == current)
                if selected:
                    if label == 'Game': _game = option
                    else: _role = option
            imgui.end_combo()
    groups = ["All", *sorted({row["group"] for row in choices if row.get('game', 'Borderlands 4') == 'Borderlands 4'})]
    if _group not in groups:
        _group = "All"
    if imgui.begin_combo("BL4 category", _group):
        for group in groups:
            selected, _ = imgui.selectable(group, _group == group)
            if selected:
                _group = group
        imgui.end_combo()
    _, _search = imgui.input_text("Find character", _search)
    rows = [row for row in choices if matches(row, _game, _role, _group)
            and all(term in (row["name"] + " " + row["key"]).casefold() for term in _search.casefold().split())]
    current = next((row["name"] for row in rows if row["key"] == _model), "Choose a character")
    if imgui.begin_combo("Character", current):
        for row in rows[:250]:
            label = row["name"] + (' · preview' if not row.get('apply_enabled', True) else " · load on demand" if row["availability"] == "load_on_demand" else "")
            selected, _ = imgui.selectable(label + "##" + row["key"], row["key"] == _model)
            if selected:
                _model = row["key"]
        imgui.end_combo()
    if len(rows) > 250:
        imgui.text_disabled(f"Showing the first 250 of {len(rows)} matches. Type a name to narrow the list.")
    targets = list(CONTROLLER.players)
    if not any(row["key"] == _owner for row in targets):
        _owner = "self"
    label = next((row["name"] for row in targets if row["key"] == _owner), "Me")
    if imgui.begin_combo("Change appearance for", label):
        for row in targets:
            selected, _ = imgui.selectable(row["name"] + "##" + row["key"], row["key"] == _owner)
            if selected:
                _owner = row["key"]
        imgui.end_combo()
    _, _keep_respawn = imgui.checkbox("Reapply after respawn", _keep_respawn)
    imgui.begin_disabled(not any(row["key"] == _model for row in rows) or bool(CONTROLLER.pending or CONTROLLER.spawn_job))
    if imgui.button("Preview beside me"):
        CONTROLLER.request("preview", model=_model)
    imgui.same_line()
    imgui.begin_disabled(not next((row.get('apply_enabled', True) for row in rows if row['key'] == _model), True))
    if imgui.button("Apply to selected player"):
        CONTROLLER.request("apply", model=_model, owner=_owner,
                           options={"follow_player_pose": True, "keep_on_respawn": _keep_respawn})
    imgui.end_disabled()
    imgui.end_disabled()
    if imgui.button("Restore selected player"):
        CONTROLLER.request("restore", owner=_owner)
    imgui.same_line()
    if imgui.button("Restore everyone"):
        CONTROLLER.request("restore_all")
    if imgui.button("Switch first / third person"):
        CONTROLLER.request("toggle_camera")
    imgui.text_disabled("F9: switch view / F10: character menu")
    if imgui.button("Remove unworn previews"):
        CONTROLLER.request("clear")
    imgui.separator()
    imgui.text_wrapped(CONTROLLER.status)
    if not rows:
        imgui.text_wrapped("No native character matches this search.")
    imgui.text_disabled("Local appearance display. Peer visibility still needs multiplayer validation.")
    if imgui.collapsing_header("Credits and licence"):
        imgui.text_wrapped("Appearance mod and conversion work: RDPSqu1ggs. BL4 models: Gearbox / 2K. SDK and BLImGui: their respective authors.")
        imgui.text_wrapped("Code: GPL-3.0-or-later, without warranty. Redistribution follows the included licence and copyright notices. Game assets have separate ownership.")
