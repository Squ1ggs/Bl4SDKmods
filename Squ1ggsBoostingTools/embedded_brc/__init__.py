"""Embedded Resources & Cooldowns for Squ1ggsBoostingTools."""
from __future__ import annotations

from typing import Any

EMBEDDED_IN_SQBT = True

_ENGINE: Any | None = None


def get_engine() -> Any:
    global _ENGINE
    if _ENGINE is None:
        from . import engine as _ENGINE  # noqa: PLC0415
    return _ENGINE


def on_enable() -> None:
    get_engine()._on_enable()


def on_disable() -> None:
    get_engine()._on_disable()


def draw_tab() -> None:
    get_engine()._draw_blimgui_tab()
