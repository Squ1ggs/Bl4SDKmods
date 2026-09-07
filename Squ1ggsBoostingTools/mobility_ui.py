"""Mobility tab UI for Squ1ggs Boosting Tools."""

from __future__ import annotations

from typing import Any, Callable

import blimgui as _blimgui

from . import mobility_runtime as _mob
from .squ1ggs_theme import ACCENT_DANGER, ACCENT_INFO, ACCENT_PRIMARY, ACCENT_SECONDARY, ACCENT_SUCCESS, ACCENT_WARN


def draw_mobility_tab(
    *,
    button: Callable[..., None],
    input_float_slider: Callable[..., float],
    checkbox: Callable[[str, bool], bool],
    muted_wrapped: Callable[[str], None],
    begin_card: Callable[..., bool],
    end_card: Callable[[], None],
    tab_height: float,
    teleport_to_party_slot: Callable[[int], None] | None = None,
    teleport_me_to_slot: Callable[[int], None] | None = None,
    teleport_slot_to_me: Callable[[int], None] | None = None,
    teleport_me_to_selected: Callable[[], None] | None = None,
    teleport_selected_to_me: Callable[[], None] | None = None,
) -> None:
    imgui = _blimgui.imgui
    before = _mob.preset_dict()

    muted_wrapped(
        "Session-authority note: slider edits debounce and apply after you stop dragging. "
        "Infinite Jump resets the native jump counter while airborne so every hop uses your JumpGoal height."
    )
    if not _mob.is_listen_host():
        muted_wrapped(
            "No local session authority was detected. Controls remain editable, "
            "but server-owned movement values may reject Apply."
        )

    opened = begin_card("Apply / Presets", ACCENT_PRIMARY, min(220.0, tab_height * 0.32))
    if opened:
        button("Apply Now", _mob.apply_all, ACCENT_SUCCESS, 120, 0)
        imgui.same_line()
        button("Save Preset", _mob.save_current_preset, ACCENT_INFO, 125, 0)
        imgui.same_line()
        button("Load Saved", lambda: _mob.load_saved_preset(True), ACCENT_SECONDARY, 115, 0)
        imgui.same_line()
        button("Reset Defaults", _mob.reset_all, ACCENT_WARN, 135, 0)

        old_auto = _mob.get_auto_apply_on_load()
        new_auto = checkbox("Auto apply saved preset on game load###sqbt_mob_auto_load", old_auto)
        if new_auto != old_auto:
            _mob.set_auto_apply_on_load(new_auto)

        button("Fast", lambda: _mob.apply_preset(speed=5.0, walk=3200.0, jump=560.0, glide_s=2600.0, glide_b=4200.0, glide_air=6.0, dash=3000.0, zero_vault=True), ACCENT_INFO, 80, 0)
        imgui.same_line()
        button("Moon", lambda: _mob.apply_preset(speed=_mob.speed_scale, walk=_mob.walk_speed, jump=1200.0, gravity=0.45, zero_vault=True), ACCENT_SECONDARY, 80, 0)
        imgui.same_line()
        button("Wall Walk", lambda: _mob.apply_preset(speed=max(_mob.speed_scale, 5.0), walk=max(_mob.walk_speed, 3200.0), jump=_mob.jump_goal, step=700.0, floor_angle=89.9, zero_vault=True), ACCENT_SUCCESS, 110, 0)
        imgui.same_line()
        button("Zero Vault Now", _mob.zero_vault_now, ACCENT_WARN, 145, 0)

        if _mob.status_message:
            muted_wrapped(_mob.status_message)
    end_card()

    opened = begin_card("Speed / Jump / Gravity", ACCENT_INFO, min(260.0, tab_height * 0.38))
    if opened:
        _mob.speed_scale = max(0.05, min(25.0, input_float_slider("Speed Scale###sqbt_mob_speed", float(_mob.speed_scale), 0.05, 25.0, "%.2fx")))
        _mob.walk_speed = max(50.0, min(10000.0, input_float_slider("Walk / Ground Speed###sqbt_mob_walk", float(_mob.walk_speed), 50.0, 10000.0, "%.0f")))
        _mob.jump_goal = max(0.0, min(10000.0, input_float_slider("JumpGoal Height###sqbt_mob_jump", float(_mob.jump_goal), 0.0, 10000.0, "%.0f")))
        _mob.gravity_scale = max(0.0, min(10.0, input_float_slider("Gravity Scale###sqbt_mob_gravity", float(_mob.gravity_scale), 0.0, 10.0, "%.2f")))
        _mob.zero_vault_costs = checkbox("Zero vault power costs on apply###sqbt_mob_zero_vault", bool(_mob.zero_vault_costs))
        muted_wrapped("Host boosting presets live here. Full on-foot sliders are on the **Player Movement** tab.")
    end_card()

    opened = begin_card("Sprint combat", ACCENT_PRIMARY, min(160.0, tab_height * 0.28))
    if opened:
        muted_wrapped("Fire or ADS while sprinting. Stays on this session until you turn it off.")
        from . import character_flags as _flags

        contexts = _mob.live_party_contexts()
        indices = [int(row[0]) for row in contexts] or [0]
        shoot_on = any(_flags.is_on("shoot_sprint", i) for i in indices)
        zoom_on = any(_flags.is_on("zoom_sprint", i) for i in indices)

        def _flip_shoot() -> None:
            _flags.set_flag("shoot_sprint", indices, not shoot_on)

        def _flip_zoom() -> None:
            _flags.set_flag("zoom_sprint", indices, not zoom_on)

        button(
            f"Shoot while sprinting {'ON' if shoot_on else 'OFF'}",
            _flip_shoot,
            ACCENT_SUCCESS if shoot_on else ACCENT_INFO,
            220,
            0,
        )
        imgui.same_line()
        button(
            f"Zoom while sprinting {'ON' if zoom_on else 'OFF'}",
            _flip_zoom,
            ACCENT_SUCCESS if zoom_on else ACCENT_INFO,
            220,
            0,
        )
    end_card()

    opened = begin_card("Infinite Jump", ACCENT_SUCCESS, min(240.0, tab_height * 0.36))
    if opened:
        button("All ON", lambda: _mob.set_infinite_jump_all(True), ACCENT_SUCCESS, 90, 0)
        imgui.same_line()
        button("All OFF", lambda: _mob.set_infinite_jump_all(False), ACCENT_DANGER, 95, 0)
        contexts = _mob.live_party_contexts()
        if not contexts:
            muted_wrapped("No live party players found.")
        for idx, name, _pc, _pawn, _move in contexts:
            enabled = int(idx) in _mob.infinite_jump_indices
            label = f"P{int(idx) + 1} Infinite Jump [{'ON' if enabled else 'OFF'}]"
            button(label, lambda i=int(idx), e=not enabled: _mob.set_infinite_jump_for_index(i, e), ACCENT_SUCCESS if enabled else ACCENT_INFO, 250, 0)
            try:
                imgui.same_line()
                imgui.text_wrapped(str(name))
            except Exception:
                pass
        muted_wrapped(f"Enabled: {_mob.enabled_infinite_names()}.")
    end_card()

    opened = begin_card("Wall / Step", ACCENT_WARN, min(210.0, tab_height * 0.32))
    if opened:
        _mob.max_step_height = max(
            0.0,
            min(1000.0, input_float_slider("Max Step Height###sqbt_mob_step", float(_mob.max_step_height), 0.0, 1000.0, "%.0f")),
        )
        old_angle = float(_mob.walkable_floor_angle)
        _mob.walkable_floor_angle = max(
            0.0,
            min(89.9, input_float_slider("Walkable Floor Angle###sqbt_mob_floor_angle", float(_mob.walkable_floor_angle), 0.0, 89.9, "%.1f")),
        )
        if abs(old_angle - float(_mob.walkable_floor_angle)) > 0.0001:
            _mob.recalc_floor_z_from_angle()
        _mob.walkable_floor_z = max(
            0.0,
            min(1.0, input_float_slider("Walkable Floor Z###sqbt_mob_floor_z", float(_mob.walkable_floor_z), 0.0, 1.0, "%.3f")),
        )
        muted_wrapped("Wall Walk preset uses high step height, 89.9° angle, and low floor Z.")
    end_card()

    opened = begin_card("Glide / Utility", ACCENT_WARN, min(250.0, tab_height * 0.38))
    if opened:
        _mob.glide_speed = max(0.0, min(30000.0, input_float_slider("Glide Speed###sqbt_mob_glide", float(_mob.glide_speed), 0.0, 30000.0, "%.0f")))
        _mob.glide_boost = max(0.0, min(30000.0, input_float_slider("Glide Boost###sqbt_mob_glide_boost", float(_mob.glide_boost), 0.0, 30000.0, "%.0f")))
        _mob.dash_speed = max(0.0, min(30000.0, input_float_slider("Dash Speed###sqbt_mob_dash", float(_mob.dash_speed), 0.0, 30000.0, "%.0f")))
        _mob.time_dilation = max(0.0, min(64.0, input_float_slider("Time Dilation###sqbt_mob_time", float(_mob.time_dilation), 0.0, 64.0, "%.2fx")))
        muted_wrapped("0.00 = hard pause. Values like 0.01 only slow the game.")
        button("Apply Time", _mob.set_time, ACCENT_INFO, 110, 0)
        imgui.same_line()
        button("Reset Time", _mob.reset_time, ACCENT_SECONDARY, 110, 0)
        imgui.same_line()
        button("Players Only", _mob.toggle_players_only, ACCENT_PRIMARY, 120, 0)
        nt_label = "No Target [ON]" if _mob.no_target_enabled() else "No Target [OFF]"
        imgui.same_line()
        button(nt_label, _mob.toggle_no_target, ACCENT_SUCCESS if _mob.no_target_enabled() else ACCENT_INFO, 145, 0)
        imgui.same_line()
        button("Delete Ground Items", _mob.delete_ground_loot, ACCENT_DANGER, 170, 0)
        old_nc = _mob.get_noclip_enabled()
        new_nc = checkbox("Noclip host pawn###sqbt_mob_noclip", old_nc)
        if new_nc != old_nc:
            _mob.set_noclip_enabled(new_nc)
            _mob.apply_noclip()
        muted_wrapped(
            "Noclip auto-enables Force fly so you don't freefall. "
            "For fall-through floors use FAAFO → Fall through map. "
            "No Target is live-only and not saved between launches."
        )
    end_card()

    if (
        callable(teleport_to_party_slot)
        or callable(teleport_me_to_slot)
        or callable(teleport_slot_to_me)
        or callable(teleport_me_to_selected)
        or callable(teleport_selected_to_me)
    ):
        opened = begin_card("Party Teleport", ACCENT_INFO, min(220.0, tab_height * 0.36))
        if opened:
            muted_wrapped(
                "Host/listen-server. Uses the Rewards Hub party target where noted. "
                "P1–P4 are live party slots."
            )
            if callable(teleport_me_to_selected) or callable(teleport_selected_to_me):
                if callable(teleport_me_to_selected):
                    button("Me → Selected", teleport_me_to_selected, ACCENT_SUCCESS, 140, 0)
                    imgui.same_line()
                if callable(teleport_selected_to_me):
                    button("Selected → Me", teleport_selected_to_me, ACCENT_PRIMARY, 140, 0)
            if callable(teleport_me_to_slot):
                muted_wrapped("Teleport me to party slot:")
                button("Me→P1", lambda: teleport_me_to_slot(0), ACCENT_INFO, 84, 0)
                imgui.same_line()
                button("Me→P2", lambda: teleport_me_to_slot(1), ACCENT_INFO, 84, 0)
                imgui.same_line()
                button("Me→P3", lambda: teleport_me_to_slot(2), ACCENT_INFO, 84, 0)
                imgui.same_line()
                button("Me→P4", lambda: teleport_me_to_slot(3), ACCENT_INFO, 84, 0)
            if callable(teleport_slot_to_me):
                muted_wrapped("Bring party slot to me:")
                button("P1→Me", lambda: teleport_slot_to_me(0), ACCENT_SECONDARY, 84, 0)
                imgui.same_line()
                button("P2→Me", lambda: teleport_slot_to_me(1), ACCENT_SECONDARY, 84, 0)
                imgui.same_line()
                button("P3→Me", lambda: teleport_slot_to_me(2), ACCENT_SECONDARY, 84, 0)
                imgui.same_line()
                button("P4→Me", lambda: teleport_slot_to_me(3), ACCENT_SECONDARY, 84, 0)
            if callable(teleport_to_party_slot):
                muted_wrapped("Teleport Rewards Hub target to slot:")
                button("To P1", lambda: teleport_to_party_slot(0), ACCENT_INFO, 84, 0)
                imgui.same_line()
                button("To P2", lambda: teleport_to_party_slot(1), ACCENT_INFO, 84, 0)
                imgui.same_line()
                button("To P3", lambda: teleport_to_party_slot(2), ACCENT_INFO, 84, 0)
                imgui.same_line()
                button("To P4", lambda: teleport_to_party_slot(3), ACCENT_INFO, 84, 0)
        end_card()

    after = _mob.preset_dict()
    if _changed_enough(before, after):
        _mob.schedule_debounced_apply("mobility slider")
    else:
        _mob.apply_pending_if_due()


def _changed_enough(a: dict[str, Any], b: dict[str, Any]) -> bool:
    keys = (
        "speed_scale",
        "walk_speed",
        "jump_goal",
        "gravity_scale",
        "max_step_height",
        "walkable_floor_angle",
        "walkable_floor_z",
        "glide_speed",
        "glide_boost",
        "glide_air_control",
        "dash_speed",
        "zero_vault_costs",
    )
    for key in keys:
        if isinstance(a.get(key), bool) or isinstance(b.get(key), bool):
            if bool(a.get(key)) != bool(b.get(key)):
                return True
        else:
            try:
                if abs(float(a.get(key, 0.0)) - float(b.get(key, 0.0))) > 0.0001:
                    return True
            except Exception:
                if a.get(key) != b.get(key):
                    return True
    return False
