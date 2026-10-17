"""Tuning tabs inside the SQBT panel (standalone mod or embedded fallback)."""
from __future__ import annotations

from typing import Callable

import blimgui as _blimgui

from . import tuning_embed as _tuning

_STEMS = {
    "bpm": "bl4_player_movement",
    "bvm": "bl4_vehicle_movement",
    "bdam": "bl4_damage_and_more",
    "brc": "bl4_resources_and_cooldowns",
}


def _hint(short: str) -> str:
    if _tuning.backend_kind(short) == "standalone":
        return f"Driving enabled mod {_STEMS[short]} — same settings JSON, one panel."
    return "Built-in copy (install the standalone mod anytime; SQBT switches automatically)."


def _draw(short: str, title: str, extra: str, muted_wrapped: Callable[[str], None]) -> None:
    imgui = _blimgui.imgui
    imgui.text_wrapped(title)
    note = _hint(short)
    if extra:
        note = f"{note} {extra}"
    muted_wrapped(note)
    try:
        _tuning.draw_tab(short)
    except Exception as exc:
        imgui.text_wrapped(f"{title} failed: {exc!r}")


def draw_player_movement_tab(*, muted_wrapped: Callable[[str], None], tab_height: float) -> None:
    _draw("bpm", "Player Movement — walk, jump, glide, vault.", "", muted_wrapped)


def draw_vehicle_tab(*, muted_wrapped: Callable[[str], None], tab_height: float) -> None:
    _draw("bvm", "Vehicle Movement — handling + spawn catalog.", "Get in a vehicle first.", muted_wrapped)


def draw_damage_tab(*, muted_wrapped: Callable[[str], None], tab_height: float) -> None:
    _draw("bdam", "Damage & More — combat sliders on your pawn.", "", muted_wrapped)


def draw_resources_tab(*, muted_wrapped: Callable[[str], None], tab_height: float) -> None:
    _draw("brc", "Kits & Shields — repair kits, shields, regen, recovery.", "", muted_wrapped)
