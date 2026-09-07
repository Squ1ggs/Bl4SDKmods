"""Squ1ggs's Boosting Tools — boosting-focused SDK mod (package: Squ1ggsBoostingTools)."""

from __future__ import annotations

# Version must load before any sibling imports that might touch the package.
from ._mod_version import __version__, __version_info__

from mods_base import CoopSupport, Game, build_mod, command
from unrealsdk import logging

from .dev_tools import force_disable_debug_cam
from .travel import travel_to_preset
from .golden_chest_keybinds import CLOSE_GOLDEN_CHEST_KEY, OPEN_GOLDEN_CHEST_KEY
from .user_keybinds import CUSTOM_KEYBINDS
from .player_economy import _cmd_givecurrency, _cmd_giveexperience
from .serial_rewards import _cmd_give_serial
from .inventory_capacity import start_auto_inventory_worker
from . import mobility_runtime as _mobility_runtime  # noqa: F401 — installs HUD tick + jump hooks
from . import loot_shapes as _loot_shapes
from .external_bridge import _cmd_sqbt_bridge, bridge_status_line, start_bridge
from .item_pool_spawning import (
    _cmd_sqbt_spawn_cancel,
    _cmd_sqbt_spawn_dump,
    _cmd_sqbt_spawn_log_clear,
    _cmd_sqbt_spawn_singular_test,
)
from . import pearl_probe_commands as _pearl_probe_commands  # noqa: F401 — registers console commands
from . import echo4_py_bridge as _echo4_py_bridge  # noqa: F401 — registers ``py`` for Echo4 injects
from .shinies import _cmd_probe_shiny

@command("sqbt_travel_tuba_boss", description="Travel to Tuba_P and teleport to the boss arena.")
def _cmd_travel_tuba_boss(_) -> None:
    logging.info(travel_to_preset("tuba_boss_arena"))


@command("sqbt_freecam_off", description="Force-disable debug/freecam and return view to your pawn.")
def _cmd_freecam_off(_) -> None:
    logging.info(force_disable_debug_cam())


def _on_enable() -> None:
    from . import tuning_embed as _tuning_embed
    from .companion_pak import ensure_companion_pak

    try:
        from . import runtime_log

        runtime_log.session_start(mod_version=__version__, bridge="enabling")
    except Exception:
        pass

    companion = ensure_companion_pak()
    if companion.ok and companion.restart_required:
        logging.warning(f"Squ1ggsBoostingTools: {companion.detail}")
    elif companion.ok:
        logging.info(f"Squ1ggsBoostingTools: {companion.detail}")
    else:
        logging.warning(f"Squ1ggsBoostingTools: {companion.detail}")
    try:
        from . import runtime_log

        runtime_log.note(f"companion_pak: {companion.detail}")
    except Exception:
        pass

    try:
        from .item_spawn.inventory_def_ptr import find_inventory_def_scriptstruct

        find_inventory_def_scriptstruct()
    except Exception:
        pass
    try:
        _mobility_runtime.enable_mobility_runtime()
    except Exception as exc:
        try:
            from . import runtime_log

            runtime_log.exception("mobility enable failed", exc)
        except Exception:
            pass
    try:
        from .faafo import ensure_launch_hook

        ensure_launch_hook()
    except Exception:
        pass
    try:
        from .currency_give import fgbx_def_ptr_api_ok

        if not fgbx_def_ptr_api_ok():
            logging.warning(
                "Squ1ggsBoostingTools: Oak2 SDK 0.3+ required (FGbxDefPtr missing). "
                "Desktop app → Setup → Update base SDK, then fully restart Borderlands 4."
            )
            try:
                from . import runtime_log

                runtime_log.warn("FGbxDefPtr missing — Oak2 SDK 0.3+ required")
            except Exception:
                pass
    except Exception:
        pass
    try:
        from .peer_session import pause_overlapping_peers

        paused = pause_overlapping_peers()
        if paused:
            logging.info(
                "Squ1ggsBoostingTools: paused extra mods (already included): "
                + ", ".join(paused)
            )
            try:
                from . import runtime_log

                runtime_log.note("paused peers: " + ", ".join(paused))
            except Exception:
                pass
    except Exception as exc:
        logging.warning(f"Squ1ggsBoostingTools: peer session scan failed: {exc!r}")
    _tuning_embed.enable_all()
    start_bridge()
    try:
        from .external_bridge import bridge_started

        if not bridge_started():
            from .peer_session import pause_overlapping_peers

            pause_overlapping_peers()
            start_bridge()
    except Exception:
        pass
    try:
        from .peer_session import reclaim_runtime_hooks

        reclaim_runtime_hooks()
    except Exception:
        pass
    try:
        from .peer_session import still_enabled_bundled_standalones

        leftover = still_enabled_bundled_standalones()
        if leftover:
            logging.warning(
                "Squ1ggsBoostingTools: still enabled alongside SQBT (paused failed): "
                + ", ".join(leftover)
            )
            try:
                from . import runtime_log

                runtime_log.warn("peers still enabled: " + ", ".join(leftover))
            except Exception:
                pass
    except Exception:
        pass
    try:
        from .session_guards import install_session_teardown_hooks

        install_session_teardown_hooks()
    except Exception as exc:
        logging.warning(f"Squ1ggsBoostingTools: session teardown hooks failed: {exc!r}")
    try:
        _loot_shapes.install_loot_shapes_hooks()
    except Exception as exc:
        logging.warning(f"Squ1ggsBoostingTools: loot shapes hooks failed: {exc!r}")
        try:
            from . import runtime_log

            runtime_log.exception("loot shapes hooks failed", exc)
        except Exception:
            pass
    logging.info(
        f"Squ1ggsBoostingTools {__version__}: Enabled. {bridge_status_line()} "
        "Desktop app: click Setup → Install / update mod folder → fully restart the game → load a character → Online."
    )
    try:
        from . import runtime_log

        runtime_log.note(f"enabled {bridge_status_line()}")
        runtime_log.flush(force=True)
    except Exception:
        pass


def _on_disable() -> None:
    try:
        from .peer_session import restore_overlapping_peers

        restore_overlapping_peers()
    except Exception:
        pass
    try:
        from .external_bridge import stop_bridge

        stop_bridge()
    except Exception:
        pass
    try:
        from . import tuning_embed as _tuning_embed

        _tuning_embed.disable_all()
    except Exception:
        pass
    try:
        # Infinite Jump stamps JumpMaxCount=999; restore on disable or it sticks mid-session.
        _mobility_runtime.disable_mobility_runtime()
    except Exception as exc:
        logging.warning(f"Squ1ggsBoostingTools: mobility disable cleanup failed: {exc!r}")
    logging.info(f"Squ1ggsBoostingTools {__version__}: Disabled.")
    try:
        from . import runtime_log

        runtime_log.session_end(reason="disable")
    except Exception:
        pass


start_auto_inventory_worker()

build_mod(
    name="Squ1ggs's Boosting Tools",
    author="Squ1ggs",
    description=(
        "Squ1ggs Boosting Tools desktop bridge and SDK commands. Drive live actions "
        "from the portable EXE while the localhost bridge is online (port 50675+)."
    ),
    supported_games=Game.BL4,
    coop_support=CoopSupport.Unknown,
    on_enable=_on_enable,
    on_disable=_on_disable,
    keybinds=[
        OPEN_GOLDEN_CHEST_KEY,
        CLOSE_GOLDEN_CHEST_KEY,
        *CUSTOM_KEYBINDS,
    ],
    commands=[
        _cmd_travel_tuba_boss,
        _cmd_freecam_off,
        _cmd_give_serial,
        _cmd_givecurrency,
        _cmd_giveexperience,
        _cmd_sqbt_bridge,
        _cmd_sqbt_spawn_dump,
        _cmd_sqbt_spawn_cancel,
        _cmd_sqbt_spawn_log_clear,
        _cmd_sqbt_spawn_singular_test,
        _cmd_probe_shiny,
    ],
)
