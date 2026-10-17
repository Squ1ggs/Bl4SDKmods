"""Dedicated BL4 Mod Menu tab for BMS interactive object spawning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

IO_TAB_TITLE = "BMS · IO"


@dataclass(slots=True)
class IoUi:
    world_prop_filter: str = ""
    world_prop_selected: str = ""
    world_prop_idx: int = 0
    io_category: str = "All"
    io_category_idx: int = 0
    status_text: str = "Ready."
    error_text: str = ""
    spawn_pending: bool = False
    spawn_pending_since: float = 0.0


def draw_io_tab(controller: Any) -> None:
    """Tab body — registered separately from the main BMS (Char_*) tab."""
    if getattr(controller, "_drawing_io_ui", False):
        return
    controller._drawing_io_ui = True
    try:
        ui = getattr(controller, "io_ui", None)
        if ui is None or not hasattr(ui, "io_category"):
            controller.io_ui = IoUi()
            ui = controller.io_ui
        try:
            from .spawn_safe import poll_spawn_status  # noqa: PLC0415

            poll_spawn_status(ui, controller=controller)
        except Exception:
            pass
        try:
            from blimgui import imgui  # noqa: PLC0415
        except Exception:
            import blimgui as bg  # noqa: PLC0415

            imgui = bg.imgui
        from .world_props_ui import draw_io_spawner_panel  # noqa: PLC0415

        def _activate() -> tuple[bool, str]:
            return controller.activate_last_io(ui=ui)

        draw_io_spawner_panel(
            imgui,
            ui,
            run_line=lambda line: controller.run_encounter_line(line, defer=True, ui=ui),
            activate_fn=_activate,
            id_prefix="io_tab",
        )
        if bool(getattr(ui, "spawn_pending", False)):
            import time as _time  # noqa: PLC0415

            since = float(getattr(ui, "spawn_pending_since", 0.0) or 0.0)
            elapsed = max(0.0, _time.monotonic() - since) if since > 0.0 else 0.0
            imgui.text_colored(
                (1.0, 0.85, 0.25, 1.0),
                f"Spawn timer: {elapsed:.1f}s — detecting (world stays running)",
            )
        if ui.status_text:
            imgui.separator()
            imgui.text_wrapped(ui.status_text)
        if ui.error_text:
            imgui.text_colored((1.0, 0.45, 0.45, 1.0), ui.error_text)
    except Exception as exc:  # noqa: BLE001
        try:
            import blimgui as bg  # noqa: PLC0415

            bg.imgui.text_colored((1.0, 0.45, 0.45, 1.0), f"BMS · IO tab error: {exc}")
        except Exception:
            pass
    finally:
        controller._drawing_io_ui = False
