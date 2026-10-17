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

def draw():
    global _search, _model, _owner, _group, _follow_pose, _keep_respawn
    from imgui_bundle import imgui
    imgui.text("BL4 Character Swapper · 0.1.2")
    imgui.text_disabled("Created by RDPSqu1ggs · github.com/Squ1ggs/Bl4SDKmods")
    imgui.text_disabled("Standalone SDK mod · also included in Squ1ggs Boosting Tools")
    choices = CONTROLLER.choices()
    groups = ["All", *sorted({row["group"] for row in choices})]
    if _group not in groups:
        _group = "All"
    if imgui.begin_combo("Character group", _group):
        for group in groups:
            selected, _ = imgui.selectable(group, _group == group)
            if selected:
                _group = group
        imgui.end_combo()
    _, _search = imgui.input_text("Find character", _search)
    rows = [row for row in choices if (_group == "All" or row["group"] == _group)
            and all(term in (row["name"] + " " + row["key"]).casefold() for term in _search.casefold().split())]
    current = next((row["name"] for row in rows if row["key"] == _model), "Choose a character")
    if imgui.begin_combo("Character", current):
        for row in rows[:250]:
            label = row["name"] + (" · load on demand" if row["availability"] == "load_on_demand" else "")
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
    _, _follow_pose = imgui.checkbox("Follow player animation (matching rigs)", _follow_pose)
    _, _keep_respawn = imgui.checkbox("Reapply after respawn", _keep_respawn)
    imgui.begin_disabled(not any(row["key"] == _model for row in rows) or bool(CONTROLLER.pending or CONTROLLER.spawn_job))
    if imgui.button("Preview beside me"):
        CONTROLLER.request("preview", model=_model)
    imgui.same_line()
    if imgui.button("Apply to selected player"):
        CONTROLLER.request("apply", model=_model, owner=_owner,
                           options={"follow_player_pose": _follow_pose, "keep_on_respawn": _keep_respawn})
    imgui.end_disabled()
    if imgui.button("Restore selected player"):
        CONTROLLER.request("restore", owner=_owner)
    imgui.same_line()
    if imgui.button("Restore everyone"):
        CONTROLLER.request("restore_all")
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
