"""Embedded Borderlands Mob Spawner (BMS) for Squ1ggsBoostingTools."""

from __future__ import annotations

from typing import Any

# When True, BMS UI lives inside SQBT only — do not register F1 shared-menu tabs.
EMBEDDED_IN_SQBT = True

_CONTROLLER: Any | None = None


def get_controller() -> Any:
    """Lazy singleton — registers spawn tick + deferred drain on first use."""
    global _CONTROLLER
    if _CONTROLLER is not None:
        return _CONTROLLER
    from . import controller as _ctrl  # noqa: PLC0415

    _CONTROLLER = _ctrl.CONTROLLER
    try:
        from ..spawn_deferred import claim_drain_owner
        from ..embedded_oak import engine as ssp

        _CONTROLLER._ensure_spawn_tick_hook()
        claim_drain_owner("Squ1ggsBoostingTools")
        ssp.clear_spawn_player_controller_override()
    except Exception:
        pass
    return _CONTROLLER
