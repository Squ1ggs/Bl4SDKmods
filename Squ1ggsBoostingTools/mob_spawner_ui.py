"""Embed bundled Borderlands Mob Spawner (BMS) inside Squ1ggs Boosting Tools World workspace."""

from __future__ import annotations

from typing import Any, Callable

import blimgui as _blimgui

from .embedded_bms import get_controller
from .squ1ggs_theme import ACCENT_PRIMARY


def draw_mob_spawner_tab(
    *,
    muted_wrapped: Callable[[str], None],
    begin_card: Callable[..., bool],
    end_card: Callable[[], None],
    tab_height: float,
) -> None:
    controller: Any = get_controller()

    opened = begin_card("Mob Spawner (BMS)", ACCENT_PRIMARY, tab_height)
    if not opened:
        return
    try:
        controller.draw_ui()
    except Exception as exc:  # noqa: BLE001
        imgui = _blimgui.imgui
        imgui.text_colored((1.0, 0.45, 0.45, 1.0), f"Mob Spawner UI error: {exc}")
        muted_wrapped("Bundled BMS failed to draw — check unrealsdk.log if spawn actions fail.")
    end_card()
