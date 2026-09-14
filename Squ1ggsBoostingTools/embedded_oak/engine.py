from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pathlib import Path

import mods_base as _mods_base
from mods_base import ENGINE, CoopSupport, Game, build_mod, command, get_pc, keybind
from unrealsdk import find_all, find_class, find_object, logging, make_struct

_LOG_PREFIX = "[Squ1ggsSpawn]"
_BUILD_TAG = "oak-hookedwidget-1.1.0-2026-07-26"

_DEFAULT_DISTANCE = 350.0
_DEFAULT_Z_OFFSET = -100.0
_DEFAULT_SCALE = 1.0
_DEFAULT_DELAY = 1.0
_DEFAULT_ACTIVATE_ENABLE = ("Active", "ActiveIdle_Anim")
_DEFAULT_ACTIVATE_DISABLE = ("IsInUse", "InUse_Anim", "Dispensing_Anim")

# When set, ``_spawn_context`` anchors Oak placements on this PC's pawn (guest spawn)
# or directly on an actor (NPC/aim target). Authority/world always stay local.
_SPAWN_PC_OVERRIDE: Optional[Any] = None
_SPAWN_ACTOR_OVERRIDE: Optional[Any] = None
_SPAWN_PC_OVERRIDE_LOCK = threading.Lock()

# Extra states to try for objects whose script is not the Lost Loot script.
# Unknown states are harmless: SetScriptStateEnabled usually no-ops or raises, and
# failures are logged as warnings. Bank/locker-style objects commonly do not expose
# UpdateAnimState, so these names give oak_spawn bank a broader activation pass.
_GENERIC_ENABLE_STATES = (
    "Active", "ActiveIdle", "ActiveIdle_Anim", "Enabled", "Enable", "Usable", "Useable",
    "Interactive", "InteractionEnabled", "Available", "Unlocked", "Idle",
    "Open", "Closed", "Bank", "PlayerBank", "Ready",
)
_GENERIC_DISABLE_STATES = (
    "IsInUse", "InUse_Anim", "Dispensing_Anim", "Disabled", "Disable",
    "Inactive", "Locked", "Blocked", "Unavailable",
)
_PRESET_ENABLE_STATES: Dict[str, Tuple[str, ...]] = {
    "bank": ("ActiveIdle", "Unlocked", "Available", "Enabled", "Usable", "Useable", "Interactive", "InteractionEnabled", "Active", "Idle"),
    "playerbank": ("ActiveIdle", "Unlocked", "Available", "Enabled", "Usable", "Useable", "Interactive", "InteractionEnabled", "Active", "Idle"),
    "player_bank": ("ActiveIdle", "Unlocked", "Available", "Enabled", "Usable", "Useable", "Interactive", "InteractionEnabled", "Active", "Idle"),
    "goldenchest": ("Idle", "Active", "ActiveIdle", "ActiveIdle_Anim", "Enabled", "Usable", "Useable", "Unlocked", "Open"),
    "golden": ("Idle", "Active", "ActiveIdle", "ActiveIdle_Anim", "Enabled", "Usable", "Useable", "Unlocked", "Open"),
    "golden_chest": ("Idle", "Active", "ActiveIdle", "ActiveIdle_Anim", "Enabled", "Usable", "Useable", "Unlocked", "Open"),
    "goldchest": ("Idle", "Active", "ActiveIdle", "ActiveIdle_Anim", "Enabled", "Usable", "Useable", "Unlocked", "Open"),
    "io_ascensionbeam": ("Activated", "Activating", "Active", "Enabled", "Idle"),
    "io_ascensionbeam_v4": ("Idle", "Active", "Start", "Enabled"),
    "io_ascensionbeam_manager": ("Enabled", "Active", "Idle"),
    "io_ascensionbeam_singletp": ("Active", "Enabled", "Idle", "Ready"),
}
_PRESET_DISABLE_STATES: Dict[str, Tuple[str, ...]] = {
    "bank": ("Locked", "Disabled", "Inactive", "Blocked", "Unavailable", "IsInUse"),
    "playerbank": ("Locked", "Disabled", "Inactive", "Blocked", "Unavailable", "IsInUse"),
    "player_bank": ("Locked", "Disabled", "Inactive", "Blocked", "Unavailable", "IsInUse"),
    "goldenchest": ("IsInUse", "InUse_Anim", "Disabled", "Locked", "Blocked"),
    "golden": ("IsInUse", "InUse_Anim", "Disabled", "Locked", "Blocked"),
    "golden_chest": ("IsInUse", "InUse_Anim", "Disabled", "Locked", "Blocked"),
    "goldchest": ("IsInUse", "InUse_Anim", "Disabled", "Locked", "Blocked"),
}

# Known shortcuts. Lost Loot is confirmed from your working one-liner.
# For the other aliases, class_name may be None: the mod will discover a live
# template actor by scanning common actor-ish classes for the keyword.
_ALIASES: Dict[str, Tuple[Optional[str], Tuple[str, ...]]] = {
    "lostloot": (
        "OakLostLootMachine",
        ("IO_LostLoot_Machine", "LostLoot_Machine", "OakLostLootMachine", "LostLoot", "Lost_Loot"),
    ),
    "lostlootmachine": (
        "OakLostLootMachine",
        ("IO_LostLoot_Machine", "LostLoot_Machine", "OakLostLootMachine", "LostLoot", "Lost_Loot"),
    ),
    "lost_loot": (
        "OakLostLootMachine",
        ("IO_LostLoot_Machine", "LostLoot_Machine", "OakLostLootMachine", "LostLoot", "Lost_Loot"),
    ),
    "golden": (None, ("Lootable_GoldenChest", "GoldenChest", "Golden_Chest", "GoldChest", "Golden")),
    "goldenchest": (None, ("Lootable_GoldenChest", "GoldenChest", "Golden_Chest", "GoldChest", "Golden")),
    "golden_chest": (None, ("Lootable_GoldenChest", "GoldenChest", "Golden_Chest", "GoldChest", "Golden")),
    "firmware": (
        None,
        ("IO_FirmwareTransferMachine", "FirmwareTransferMachine", "Firmware"),
    ),
    "bank": (None, ("IO_PlayerBank", "PersistentLevel.IO_PlayerBank", "PlayerBank", "Player_Bank", "Bank")),
    "barrel": (None, ("Barrel", "ExplosiveBarrel", "Explosive_Barrel", "ExplodingObject_Barrel")),
    "barrels": (None, ("Barrel", "ExplosiveBarrel", "Explosive_Barrel", "ExplodingObject_Barrel")),
    "playerbank": (None, ("IO_PlayerBank", "PersistentLevel.IO_PlayerBank", "PlayerBank", "Player_Bank", "Bank")),
    "player_bank": (None, ("IO_PlayerBank", "PersistentLevel.IO_PlayerBank", "PlayerBank", "Player_Bank", "Bank")),
    # Confirmed via WhatAmILookingAt: live machines are OakVendingMachine in a
    # World_P/_Generated_/… PersistentLevel (UAID suffix), not a thin-air actor-def.
    "blackmarket": (
        "OakVendingMachine",
        (
            "IO_VendingMachine_BlackMarket",
            "VendingMachine_BlackMarket",
            "BlackMarket",
        ),
    ),
    "black_market": (
        "OakVendingMachine",
        (
            "IO_VendingMachine_BlackMarket",
            "VendingMachine_BlackMarket",
            "BlackMarket",
        ),
    ),
    "io_vendingmachine_blackmarket": (
        "OakVendingMachine",
        (
            "IO_VendingMachine_BlackMarket",
            "VendingMachine_BlackMarket",
            "BlackMarket",
        ),
    ),
    "vending": (
        "OakVendingMachine",
        ("IO_VendingMachine_Munitions", "VendingMachine_Munitions", "VendingMachine", "Munitions"),
    ),
    "munitions": (
        "OakVendingMachine",
        ("IO_VendingMachine_Munitions", "VendingMachine_Munitions", "Munitions"),
    ),
    "breakable_chest": (
        None,
        ("IO_Chest_BreakableLock_Lootable", "Chest_BreakableLock_Lootable", "BreakableLock", "Breakable_Chest"),
    ),
    "moneybox": (None, ("IO_Lootable_Heist_MoneyBox", "MoneyBox", "Heist_MoneyBox")),
    "electisafe": (None, ("IO_ElectiSafe", "ElectiSafe", "Electi_Safe")),
    "ammogeyser": (None, ("IO_AmmoGeyser", "AmmoGeyser", "Ammo_Geyser")),
    "maurice": (
        "OakVendingMachine",
        (
            "IO_VendingMachine_Legend_Legendary",
            "VendingMachine_Legend_Legendary",
            "Legend_Legendary",
        ),
    ),
    "io_vendingmachine_legend_legendary": (
        "OakVendingMachine",
        (
            "IO_VendingMachine_Legend_Legendary",
            "VendingMachine_Legend_Legendary",
            "Legend_Legendary",
        ),
    ),
    "io_vendingmachine_legend_a": (
        "OakVendingMachine",
        (
            "IO_VendingMachine_Legend_A",
            "VendingMachine_Legend_A",
            "Legend_A",
        ),
    ),
}

_CLASS_SCAN_ORDER: Tuple[str, ...] = (
    # Specific / likely deployables first. Missing classes are harmless.
    "OakLostLootMachine",
    "OakVendingMachine",
    "LootableObject",
    "OakInteractiveObject",
    "OakInteractableObject",
    "OakUsableActor",
    "OakUseableActor",
    "OakMissionScriptedActor",
    "OakLootable",
    "OakLootableContainer",
    "OakChest",
    "OakActor",
    # Broad fallback. This can be larger, so it is intentionally last.
    "Actor",
)

# Dropdown keywords -> PersistentLevel / oak_spawnai tokens (from io_spawn_catalog / dumps).
_LOGO_ACTOR_CANONICAL: Dict[str, str] = {
    "goldenchest": "Lootable_GoldenChest",
    "golden": "Lootable_GoldenChest",
    "golden_chest": "Lootable_GoldenChest",
    "firmware": "IO_FirmwareTransferMachine",
    "bank": "IO_PlayerBank",
    "playerbank": "IO_PlayerBank",
    "player_bank": "IO_PlayerBank",
    "lostloot": "IO_LostLoot_Machine",
    "lostlootmachine": "IO_LostLoot_Machine",
    "lost_loot": "IO_LostLoot_Machine",
    "blackmarket": "IO_VendingMachine_BlackMarket",
    "black_market": "IO_VendingMachine_BlackMarket",
    "munitions": "IO_VendingMachine_Munitions",
    "vending": "IO_VendingMachine_Munitions",
    "breakable_chest": "IO_Chest_BreakableLock_Lootable",
    "moneybox": "IO_Lootable_Heist_MoneyBox",
    "electisafe": "IO_ElectiSafe",
    "ammogeyser": "IO_AmmoGeyser",
}


@dataclass
class DeployedActor:
    label: str
    source: Any
    actor: Any
    actor_key: str = ""
    class_name: str = ""


_SPAWNED: List[DeployedActor] = []
# Runtime-only cache of FGbxDefPtr values discovered from live actors.
# These pointers cannot be reconstructed from strings in the current SDK, so
# cache while the source actor is loaded, then spawn later in the same session.
_ACTOR_DEF_CACHE: Dict[str, Any] = {}
_ACTOR_DEF_CACHE_SOURCE: Dict[str, str] = {}

# Offline deploy presets — filled after ``_alias_key`` is defined (see bottom of alias helpers).
_DEPLOY_OFFLINE_PRESETS: Dict[str, Tuple[str, Tuple[str, ...], Tuple[str, ...]]] = {}


def _option_text_value(option: Any, default: str) -> str:
    """Read a text option value across SDK option API variants."""
    if option is None:
        return default
    for attr in ("value", "current_value", "Value", "CurrentValue"):
        try:
            value = getattr(option, attr)
        except Exception:
            continue
        try:
            if callable(value):
                value = value()
        except Exception:
            pass
        if value is not None:
            text = _normalize_logo_row_text(str(value))
            if text:
                return text
    return _normalize_logo_row_text(default)


def _normalize_logo_row_text(text: str) -> str:
    """Normalize mod-menu/console logo text: trim and auto-uppercase."""
    return str(text or "").strip().upper()


def _option_float_value(option: Any, default: float) -> float:
    """Read a numeric option value across SDK option API variants."""
    if option is None:
        return float(default)
    for attr in ("value", "current_value", "Value", "CurrentValue"):
        try:
            value = getattr(option, attr)
        except Exception:
            continue
        try:
            if callable(value):
                value = value()
        except Exception:
            pass
        if value is not None:
            try:
                return float(value)
            except Exception:
                continue
    return float(default)


def _make_float_option(identifier: str, display_name: str, default: float, description: str, *, minimum: float = 0.0, maximum: float = 10000.0, increment: float = 50.0) -> Optional[Any]:
    """Create a persistent mod-menu numeric option when supported by this SDK build."""
    for class_name in ("SliderOption", "FloatOption", "SpinnerOption", "NumberOption", "NumericOption"):
        cls = getattr(_mods_base, class_name, None)
        if cls is None:
            continue
        attempts = (
            lambda: cls(identifier, default, minimum, maximum, increment, display_name=display_name, description=description),
            lambda: cls(identifier, default, min_value=minimum, max_value=maximum, increment=increment, display_name=display_name, description=description),
            lambda: cls(identifier, default, min_value=minimum, max_value=maximum, step=increment, name=display_name, description=description),
            lambda: cls(identifier, display_name, default, minimum, maximum, increment, description=description),
            lambda: cls(display_name, default, minimum, maximum, increment, description=description),
            lambda: cls(identifier, default, minimum, maximum, increment),
            lambda: cls(identifier, default),
        )
        for attempt in attempts:
            try:
                return attempt()
            except TypeError:
                continue
            except Exception:
                continue
    return None

_ValueOptionBase = getattr(_mods_base, "ValueOption", None)

if _ValueOptionBase is not None:
    @dataclass
    class LogoTextOption(_ValueOptionBase):  # type: ignore[misc]
        """Visible free-text mod-menu option for the console mod menu.

        mods_base itself only ships Bool/Slider/Spinner/Dropdown/Keybind/Button.
        There is no stock TextOption, so Oak Spawner provides this tiny ValueOption and
        patches console_mod_menu to open a free text input screen for it.
        """
        def _from_json(self, value: Any) -> None:
            self.value = _normalize_logo_row_text(str(value))
else:
    LogoTextOption = None  # type: ignore[assignment,misc]


def _make_text_option(identifier: str, display_name: str, default: str, description: str) -> Optional[Any]:
    """Create a visible free-text option backed by Oak Spawner's custom menu screen."""
    if LogoTextOption is None:
        return None
    try:
        return LogoTextOption(
            identifier=identifier,
            value=_normalize_logo_row_text(default),
            display_name=display_name,
            description=description,
        )
    except Exception as exc:
        try:
            logging.warning(f"{_LOG_PREFIX} LogoTextOption create failed for {identifier}: {exc}")
        except Exception:
            pass
        return None


def _install_logo_text_menu_support() -> None:
    """Teach console_mod_menu how to edit LogoTextOption values.

    Keybinds get a custom screen by patching the menu's option handler.  This does
    the same thing for row text: press the row option, type any text, press enter.
    The value is uppercased and saved immediately.

    Detection is by option identifier / class name — not ``isinstance`` — so
    ``rlm squ1ggs_spawn`` does not break editing after a class-identity change.
    """
    if LogoTextOption is None:
        return
    try:
        from dataclasses import dataclass as _dataclass, field as _field
        from console_mod_menu.draw import draw as _draw
        from console_mod_menu.option_formatting import draw_option_header as _draw_option_header
        from console_mod_menu.screens import (
            AbstractScreen as _AbstractScreen,
            draw_standard_commands as _draw_standard_commands,
            handle_standard_command_input as _handle_standard_command_input,
            push_screen as _push_screen,
        )
        from console_mod_menu.screens.mod import OptionListScreen as _OptionListScreen
    except Exception as exc:
        try:
            logging.warning(f"{_LOG_PREFIX} console_mod_menu text editor hook unavailable: {exc}")
        except Exception:
            pass
        return

    def _is_logo_text_option(option: Any) -> bool:
        if option is None:
            return False
        try:
            if LogoTextOption is not None and isinstance(option, LogoTextOption):
                return True
        except Exception:
            pass
        try:
            cls_name = type(option).__name__
            if "LogoText" in cls_name:
                return True
        except Exception:
            pass
        for attr in ("identifier", "Identifier", "id"):
            try:
                ident = str(getattr(option, attr, "") or "")
            except Exception:
                continue
            if ident.lower().startswith("oak_logo_"):
                return True
        return False

    @_dataclass
    class _LogoTextOptionScreen(_AbstractScreen):  # type: ignore[misc]
        mod: Any
        option: Any
        name: str = _field(init=False)

        def __post_init__(self) -> None:
            self.name = self.option.display_name

        def draw(self) -> None:  # noqa: D102
            _draw_option_header(self.option)
            try:
                cur = str(getattr(self.option, "value", "") or "")
            except Exception:
                cur = ""
            _draw(f"Current: {cur or '(empty)'}")
            _draw("Type the new row text and press Enter.")
            _draw("Text is auto-capitalized. Leave blank to keep current value.")
            _draw("Example: we have been")
            _draw("Tip: free text also works via console: oak_logo_set row1 YOUR TEXT")
            _draw_standard_commands()

        def handle_input(self, line: str) -> bool:  # noqa: D102
            if _handle_standard_command_input(line):
                return True
            text = _normalize_logo_row_text(line)
            if not text:
                return False
            self.option.value = text
            try:
                self.mod.save_settings()
            except Exception as exc:
                try:
                    logging.warning(f"{_LOG_PREFIX} failed saving logo text option: {exc}")
                except Exception:
                    pass
            try:
                _draw(f"Saved: {text}")
            except Exception:
                pass
            return True

    _orig = getattr(_OptionListScreen, "_oak_logo_text_orig_handle", None)
    if _orig is None:
        _orig = _OptionListScreen.handle_option_input
        _OptionListScreen._oak_logo_text_orig_handle = _orig  # type: ignore[attr-defined]

    def _oak_handle_option_input(self: Any, line: str) -> bool:
        try:
            option = self.drawn_options[int(line) - 1]
        except (ValueError, IndexError):
            return _orig(self, line)
        if _is_logo_text_option(option):
            _push_screen(_LogoTextOptionScreen(self.mod, option))
            return True
        return _orig(self, line)

    _OptionListScreen.handle_option_input = _oak_handle_option_input
    _OptionListScreen._oak_logo_text_patched = True  # type: ignore[attr-defined]
    try:
        logging.info(f"{_LOG_PREFIX} console_mod_menu LogoText editor hooked (oak_logo_* free text).")
    except Exception:
        pass


def _apply_logo_text_to_option(option: Any, text: str) -> bool:
    if option is None:
        return False
    try:
        option.value = _normalize_logo_row_text(text)
    except Exception:
        return False
    return True


def _persist_logo_options() -> None:
    """Write current logo option values into settings/squ1ggs_spawn.json."""
    try:
        path = Path(__file__).resolve().parent.parent / "settings" / "squ1ggs_spawn.json"
        data: dict[str, Any] = {}
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        opts = data.get("options")
        if not isinstance(opts, dict):
            opts = {}
        for key, option, default in (
            ("oak_logo_row_1", _LOGO_ROW1_OPTION, _LOGO_ROW1_DEFAULT),
            ("oak_logo_row_2", _LOGO_ROW2_OPTION, _LOGO_ROW2_DEFAULT),
            ("oak_logo_row_3", _LOGO_ROW3_OPTION, _LOGO_ROW3_DEFAULT),
            ("oak_logo_actor", _LOGO_ACTOR_OPTION, _LOGO_ACTOR_DEFAULT),
        ):
            opts[key] = _option_text_value(option, default)
        if _LOGO_DISTANCE_OPTION is not None:
            opts["oak_logo_distance"] = _option_float_value(
                _LOGO_DISTANCE_OPTION, _LOGO_DISTANCE_DEFAULT
            )
        data["options"] = opts
        data.setdefault("enabled", True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    except Exception as exc:
        try:
            logging.warning(f"{_LOG_PREFIX} persist logo options failed: {exc}")
        except Exception:
            pass


def _make_spinner_option(identifier: str, display_name: str, choices: Sequence[str], default: str, description: str) -> Optional[Any]:
    """Create a persistent dropdown/choice option when this SDK exposes one.

    Free-text LogoTextOption is preferred; spinners are a fallback when typing in
    the console mods menu is awkward. Console ``oak_logo_set`` / ``oak_barrellogo``
    stay fully free-form.
    """
    values = tuple(str(v) for v in choices)
    if default not in values:
        values = (default,) + values
    for class_name in (
        "SpinnerOption", "DropdownOption", "DropDownOption", "ChoiceOption",
        "SelectOption", "SelectionOption", "EnumOption",
    ):
        cls = getattr(_mods_base, class_name, None)
        if cls is None:
            continue
        attempts = (
            lambda: cls(identifier, default, values, display_name=display_name, description=description),
            lambda: cls(identifier, default, choices=values, display_name=display_name, description=description),
            lambda: cls(identifier, default, options=values, display_name=display_name, description=description),
            lambda: cls(identifier, default, values=values, display_name=display_name, description=description),
            lambda: cls(identifier, display_name, default, values, description=description),
            lambda: cls(display_name, default, values, description=description),
            lambda: cls(identifier, default, values),
        )
        for attempt in attempts:
            try:
                return attempt()
            except TypeError:
                continue
            except Exception:
                continue
    return None


def _log_info(message: str) -> None:
    logging.info(f"{_LOG_PREFIX} {message}")


def _log_warn(message: str) -> None:
    logging.warning(f"{_LOG_PREFIX} {message}")


def _log_error(message: str) -> None:
    logging.error(f"{_LOG_PREFIX} {message}")


def _unwrap(value: Any) -> Any:
    return value[0] if isinstance(value, (list, tuple)) else value


def _pawn(pc: Any) -> Any:
    for attr in ("OakCharacter", "Pawn", "AcknowledgedPawn"):
        try:
            pawn = getattr(pc, attr, None)
        except Exception:
            pawn = None
        if pawn is not None:
            return pawn
    return None


def _world_from_pc(pc: Any) -> Any:
    try:
        gv = getattr(ENGINE, "GameViewport", None)
        world = getattr(gv, "World", None) if gv is not None else None
        if world is not None:
            return world
    except Exception:
        pass
    try:
        return getattr(pc, "World", None)
    except Exception:
        return None


def _gameplay_statics() -> Any:
    try:
        return find_object("GameplayStatics", "/Script/Engine.Default__GameplayStatics")
    except Exception:
        try:
            return find_class("GameplayStatics").ClassDefaultObject
        except Exception as exc:
            _log_error(f"GameplayStatics lookup failed: {exc}")
            return None


class spawn_at_player_controller:
    """Temporarily anchor Oak spawn transforms on ``pc``'s pawn (guest-safe)."""

    def __init__(self, pc: Any | None, *, clear_on_exit: bool = False) -> None:
        # Accept accidental (pc, idx, name) peek tuples.
        if isinstance(pc, (tuple, list)):
            pc = pc[0] if pc else None
        self.pc = pc
        self.clear_on_exit = bool(clear_on_exit)
        self._prev: Any | None = None
        self._prev_actor: Any | None = None

    def __enter__(self) -> "spawn_at_player_controller":
        global _SPAWN_ACTOR_OVERRIDE, _SPAWN_PC_OVERRIDE
        with _SPAWN_PC_OVERRIDE_LOCK:
            self._prev = _SPAWN_PC_OVERRIDE
            self._prev_actor = _SPAWN_ACTOR_OVERRIDE
            _SPAWN_PC_OVERRIDE = self.pc
            _SPAWN_ACTOR_OVERRIDE = None
        return self

    def __exit__(self, *exc: object) -> None:
        global _SPAWN_ACTOR_OVERRIDE, _SPAWN_PC_OVERRIDE
        with _SPAWN_PC_OVERRIDE_LOCK:
            _SPAWN_PC_OVERRIDE = None if self.clear_on_exit else self._prev
            _SPAWN_ACTOR_OVERRIDE = None if self.clear_on_exit else self._prev_actor


class spawn_at_actor:
    """Temporarily anchor Oak placement directly on an NPC or other live actor."""

    def __init__(self, actor: Any | None, *, clear_on_exit: bool = False) -> None:
        self.actor = actor
        self.clear_on_exit = bool(clear_on_exit)
        self._prev_actor: Any | None = None
        self._prev_pc: Any | None = None

    def __enter__(self) -> "spawn_at_actor":
        global _SPAWN_ACTOR_OVERRIDE, _SPAWN_PC_OVERRIDE
        with _SPAWN_PC_OVERRIDE_LOCK:
            self._prev_actor = _SPAWN_ACTOR_OVERRIDE
            self._prev_pc = _SPAWN_PC_OVERRIDE
            _SPAWN_ACTOR_OVERRIDE = self.actor
            _SPAWN_PC_OVERRIDE = None
        return self

    def __exit__(self, *exc: object) -> None:
        global _SPAWN_ACTOR_OVERRIDE, _SPAWN_PC_OVERRIDE
        with _SPAWN_PC_OVERRIDE_LOCK:
            _SPAWN_ACTOR_OVERRIDE = None if self.clear_on_exit else self._prev_actor
            _SPAWN_PC_OVERRIDE = None if self.clear_on_exit else self._prev_pc


def clear_spawn_player_controller_override() -> None:
    """Clear leaked placement overrides without exposing raw global writes."""
    global _SPAWN_ACTOR_OVERRIDE, _SPAWN_PC_OVERRIDE
    with _SPAWN_PC_OVERRIDE_LOCK:
        _SPAWN_PC_OVERRIDE = None
        _SPAWN_ACTOR_OVERRIDE = None


def _invalidate_spawn_runtime_cache(reason: str = "world/roster transition") -> None:
    """Drop session UObject/FGbxDefPtr references after lobby generation changes."""
    clear_spawn_player_controller_override()
    _ACTOR_DEF_CACHE.clear()
    _ACTOR_DEF_CACHE_SOURCE.clear()
    _SPAWNED.clear()
    # Packages that "loaded" without exposing a usable def must be retryable.
    _LOADED_SPAWN_PACKAGES.clear()
    _FAILED_SPAWN_PACKAGES.clear()
    global _THIN_AIR_SPAWNER_TEMPLATE, _THIN_AIR_SPAWNER_WORLD_KEY
    global _SPAWN_MANAGER_OVERDRIVEN_KEY, _ASYNC_PACKAGE_WARMED
    _THIN_AIR_SPAWNER_TEMPLATE = None
    _THIN_AIR_SPAWNER_WORLD_KEY = ""
    _SPAWN_MANAGER_OVERDRIVEN_KEY = ""
    _ASYNC_PACKAGE_WARMED.clear()
    _log_info(f"invalidated actor-def/spawner runtime references: {reason}")


def _spawn_context() -> Tuple[Optional[Any], Optional[Any], Optional[Any], Optional[Any]]:
    """Resolve host world + pawn used for placement.

    Placement overrides only change *where* the actor appears.
    World / GameplayStatics always come from the local listen-host controller.
    """
    local_pc = get_pc()
    override = _SPAWN_PC_OVERRIDE
    # Defend against callers accidentally passing peek tuples / non-PC objects.
    if isinstance(override, (tuple, list)):
        override = override[0] if override else None
    actor_override = _SPAWN_ACTOR_OVERRIDE
    anchor_pc = override if override is not None else local_pc
    if anchor_pc is None and local_pc is None:
        _log_error("No PlayerController.")
        return None, None, None, None

    pawn = actor_override if actor_override is not None else (_pawn(anchor_pc) if anchor_pc is not None else None)
    if pawn is None and local_pc is not None and anchor_pc is not local_pc:
        # Guest pawn not readable on host — fall back to local placement rather than abort.
        _log_warn("Spawn anchor pawn missing; falling back to local host pawn.")
        pawn = _pawn(local_pc)
        anchor_pc = local_pc
    if pawn is None:
        _log_error("No Pawn / OakCharacter.")
        return (local_pc or anchor_pc), None, None, None

    host_pc = local_pc if local_pc is not None else anchor_pc
    world = _world_from_pc(host_pc)
    if world is None:
        _log_error("No World.")
        return host_pc, pawn, None, None
    gs = _gameplay_statics()
    # Return host PC for authority; pawn may be guest's for location.
    return host_pc, pawn, world, gs


def _spawn_transform(pawn: Any, *, distance: float, z_offset: float, scale: float) -> Any:
    return _spawn_transform_for_index(
        pawn,
        index=0,
        count=1,
        distance=distance,
        spacing=0.0,
        z_offset=z_offset,
        scale=scale,
    )


def _spawn_transform_for_index(
    pawn: Any,
    *,
    index: int,
    count: int,
    distance: float,
    spacing: float,
    z_offset: float,
    scale: float,
) -> Any:
    """ADA-style row placement: center multiple spawned actors in front of the player."""
    loc = pawn.K2_GetActorLocation()
    fwd = pawn.GetActorForwardVector()
    total = max(1, int(count))
    offset = (float(index) - (float(total) - 1.0) / 2.0) * float(spacing)
    return make_struct(
        "Transform",
        Rotation=make_struct("Quat", X=0.0, Y=0.0, Z=0.0, W=1.0),
        Translation=make_struct(
            "Vector",
            X=float(loc.X + fwd.X * distance - fwd.Y * offset),
            Y=float(loc.Y + fwd.Y * distance + fwd.X * offset),
            Z=float(loc.Z + z_offset),
        ),
        Scale3D=make_struct("Vector", X=float(scale), Y=float(scale), Z=float(scale)),
    )


def _thin_air_spawner_is_valid(spawner: Any) -> bool:
    if spawner is None:
        return False
    try:
        comp = spawner.GetSpawnerComponent()
        return comp is not None
    except Exception:
        return False


def _hide_spawner_actor(spawner: Any) -> None:
    try:
        spawner.SetActorHiddenInGame(True)
    except Exception:
        pass


def _ensure_thin_air_spawner_template(
    gs: Any,
    world: Any,
    cls: Any,
    transform: Any,
) -> Any | None:
    """Hidden template OakSpawner — duplicate per fire, never ResetSpawner on template."""
    global _THIN_AIR_SPAWNER_TEMPLATE, _THIN_AIR_SPAWNER_WORLD_KEY
    world_key = str(world)
    if (
        _THIN_AIR_SPAWNER_TEMPLATE is not None
        and world_key == _THIN_AIR_SPAWNER_WORLD_KEY
        and _thin_air_spawner_is_valid(_THIN_AIR_SPAWNER_TEMPLATE)
    ):
        return _THIN_AIR_SPAWNER_TEMPLATE

    spawner = _spawn_actor_deferred(
        gs,
        world,
        cls,
        transform,
        class_name="OakSpawner",
        source=None,
        collision_handling=1,
    )
    if spawner is None:
        return None
    _hide_spawner_actor(spawner)
    _THIN_AIR_SPAWNER_TEMPLATE = spawner
    _THIN_AIR_SPAWNER_WORLD_KEY = world_key
    return spawner


def _spawn_thin_air_spawner_for_fire(
    gs: Any,
    world: Any,
    cls: Any,
    transform: Any,
    *,
    async_mode: bool,
) -> tuple[Any | None, bool]:
    """Return (spawner, duplicated_from_template).

    Async BMS: duplicate a fresh OakSpawner per click so ResetSpawner does not
    despawn actors from the previous disposable spawner.
    """
    if async_mode:
        template = _ensure_thin_air_spawner_template(gs, world, cls, transform)
        if template is not None:
            dup = _duplicate_oak_spawner_at(template, transform, index=0)
            if dup is not None:
                return dup, True
    spawner = _spawn_actor_deferred(
        gs,
        world,
        cls,
        transform,
        class_name="OakSpawner",
        source=None,
        collision_handling=1,
    )
    return spawner, False


def prewarm_thin_air_spawner(*, distance: float = 400.0) -> bool:
    """Create the hidden template OakSpawner off the hot spawn-click path."""
    _, pawn, world, gs = _spawn_context()
    if pawn is None or world is None or gs is None:
        return False
    try:
        cls = find_class("OakSpawner")
    except Exception:
        return False
    if cls is None:
        return False
    transform = _spawn_transform_for_index(
        pawn,
        index=0,
        count=1,
        distance=float(distance),
        spacing=0.0,
        z_offset=0.0,
        scale=1.0,
    )
    template = _ensure_thin_air_spawner_template(gs, world, cls, transform)
    if template is None:
        return False
    _overdrive_spawn_manager_if_needed(world)
    try:
        from Squ1ggsBoostingTools.embedded_bms.spawn_core import disable_world_spawn_budget  # noqa: PLC0415

        disable_world_spawn_budget(True)
    except Exception:
        pass
    try:
        _overdrive_spawner_component_fast(template.GetSpawnerComponent())
    except Exception:
        pass
    _log_info(f"prewarmed thin-air OakSpawner template at {template.K2_GetActorLocation()}")
    return True


def _spawn_actor_deferred(
    gs: Any,
    world: Any,
    cls: Any,
    transform: Any,
    *,
    class_name: str = "Actor",
    source: Optional[Any] = None,
    collision_handling: int = 1,
) -> Optional[Any]:
    """Spawn an actor with the safer ADA deferred-spawn wrapper.

    If a source template is provided, copy its actor data before FinishSpawningActor so
    script/deployable actors initialize with the same data as their live template.
    """
    try:
        raw = gs.BeginDeferredActorSpawnFromClass(world, cls, transform, int(collision_handling), None, 1)
        actor = _unwrap(raw)
    except Exception as exc:
        _log_error(f"BeginDeferredActorSpawnFromClass failed for {class_name}: {exc}")
        return None
    if actor is None:
        _log_error("BeginDeferredActorSpawnFromClass returned None.")
        return None

    if source is not None:
        _copy_actor_data(source, actor)

    try:
        raw2 = gs.FinishSpawningActor(actor, transform, 0)
        return _unwrap(raw2)
    except Exception as exc:
        _log_error(f"FinishSpawningActor failed for {class_name}: {exc}")
        return None



def _actor_mesh(actor: Any) -> Any:
    """ADA-style mesh lookup for non-deployable actors such as OakWeapon."""
    for attr in ("Mesh", "CharacterMesh", "SkeletalMeshComponent", "GbxSkeletalMeshComponent", "MeshComponent"):
        try:
            mesh = getattr(actor, attr, None)
        except Exception:
            mesh = None
        if mesh is not None:
            return mesh
    for cls_path in ("/Script/OakGame.GbxSkeletalMeshComponent", "/Script/Engine.SkeletalMeshComponent"):
        try:
            cls = find_object("Class", cls_path)
            mesh = actor.GetComponentByClass(cls)
        except Exception:
            mesh = None
        if mesh is not None:
            return mesh
    return None


def _mesh_asset_for_kind(mesh: Any) -> Any:
    for attr in ("SkeletalMesh", "SkinnedAsset"):
        try:
            asset = getattr(mesh, attr, None)
        except Exception:
            asset = None
        if asset is not None:
            return asset
    return None


def _set_skeletal_mesh_asset(mesh: Any, mesh_asset: Any) -> None:
    for func_name in ("SetSkeletalMeshAsset", "SetSkeletalMesh"):
        func = getattr(mesh, func_name, None)
        if callable(func):
            func(mesh_asset)
            return
    raise RuntimeError("No skeletal mesh setter found")


def _material_at(comp: Any, index: int) -> Any:
    try:
        return comp.GetMaterial(int(index))
    except Exception:
        return None


def _copy_material_slots(src_mesh: Any, dst_mesh: Any, max_slots: int = 64) -> int:
    copied = 0
    for idx in range(max_slots):
        mat = _material_at(src_mesh, idx)
        if mat is None:
            continue
        try:
            dst_mesh.SetMaterial(idx, mat)
            copied += 1
        except Exception:
            pass
    return copied


def _show_actor_mesh(actor: Any, mesh: Any) -> None:
    try:
        actor.SetActorHiddenInGame(False)
    except Exception:
        pass
    try:
        mesh.SetHiddenInGame(False, True)
    except Exception:
        pass
    try:
        mesh.SetVisibility(True, True)
    except Exception:
        pass


def _refresh_component(component: Any) -> None:
    for func_name in ("RegisterComponent", "RecreatePhysicsState", "UpdateBounds", "MarkRenderDynamicDataDirty"):
        func = getattr(component, func_name, None)
        if callable(func):
            try:
                func()
            except Exception:
                pass


def _spawn_skeletal_mesh_actor(gs: Any, world: Any, transform: Any) -> Optional[Any]:
    try:
        actor_cls = find_object("Class", "/Script/Engine.SkeletalMeshActor")
    except Exception as exc:
        _log_warn(f"SkeletalMeshActor class lookup failed: {exc}")
        return None
    return _spawn_actor_deferred(gs, world, actor_cls, transform, class_name="SkeletalMeshActor", source=None, collision_handling=2)


def _find_generic_skeletal_source(name: str, generated_only: bool = True) -> Optional[Any]:
    """Find any live actor by name that has a skeletal mesh, mirroring ADA's generic source path."""
    needles = [n.lower() for n in _default_class_and_needles(name)[1] if n]
    scan_classes = ("OakWeapon", "OakInventory", "OakActor", "Actor")
    for allow_non_generated in ((not generated_only), True):
        for class_name in scan_classes:
            try:
                actors = list(find_all(class_name, False))
            except TypeError:
                try:
                    actors = list(find_all(class_name))
                except Exception:
                    continue
            except Exception:
                continue
            for actor in actors:
                try:
                    text = str(actor)
                except Exception:
                    continue
                low = text.lower()
                if "/script/" in low or "default__" in low:
                    continue
                if generated_only and not allow_non_generated and "_generated_" not in low:
                    continue
                if needles and not any(n in low for n in needles):
                    continue
                mesh = _actor_mesh(actor)
                if mesh is not None and _mesh_asset_for_kind(mesh) is not None:
                    return actor
    return None


def _spawn_generic_skeletal_duplicate(
    name: str,
    *,
    source: Any,
    distance: float,
    z_offset: float,
    scale: float,
    count: int,
    spacing: float,
) -> Optional[Any]:
    _, pawn, world, gs = _spawn_context()
    if pawn is None or world is None or gs is None:
        return None
    src_mesh = _actor_mesh(source)
    mesh_asset = _mesh_asset_for_kind(src_mesh)
    if src_mesh is None or mesh_asset is None:
        _log_error(f"{name}: generic source has no usable skeletal mesh.")
        return None
    _log_info(f"Using generic skeletal source {source}.")
    total = max(1, int(count))
    first_actor: Optional[Any] = None
    spawned = 0
    for idx in range(total):
        transform = _spawn_transform_for_index(pawn, index=idx, count=total, distance=distance, spacing=spacing, z_offset=z_offset, scale=scale)
        actor = _spawn_skeletal_mesh_actor(gs, world, transform)
        if actor is None:
            continue
        dst_mesh = _actor_mesh(actor)
        if dst_mesh is None:
            _destroy_actor(actor)
            continue
        try:
            _set_skeletal_mesh_asset(dst_mesh, mesh_asset)
            _copy_material_slots(src_mesh, dst_mesh, max_slots=64)
            _show_actor_mesh(actor, dst_mesh)
            _refresh_component(dst_mesh)
        except Exception as exc:
            _destroy_actor(actor)
            _log_warn(f"{name}: generic skeletal setup failed: {exc}")
            continue
        _SPAWNED.append(DeployedActor(label=name, source=source, actor=actor, actor_key=_actor_key(actor), class_name=_class_name(actor)))
        if first_actor is None:
            first_actor = actor
        spawned += 1
        _log_info(f"Spawned {name.lower()} generic skeletal duplicate {idx + 1}/{total}: {actor}")
    if spawned <= 0:
        _log_error(f"{name}: no generic skeletal actors spawned.")
        return None
    _log_info(f"Sampler: spawned {spawned}/{total} type=actor name={name!r} kind=single parts=0 distance={distance:g}uu")
    return first_actor

def _alias_key(name: str) -> str:
    return name.strip().lower().replace(" ", "").replace("-", "_")


def _register_offline_preset(
    actor_def: str,
    loads: Tuple[str, ...],
    *aliases: str,
    alt_defs: Tuple[str, ...] = (),
) -> None:
    for alias in aliases:
        _DEPLOY_OFFLINE_PRESETS[_alias_key(alias)] = (actor_def, loads, alt_defs)


_register_offline_preset(
    "Lootable_GoldenChest",
    (
        "/Game/GameData/Lootables/ActorScripts/Script_Lootable_GoldenChest",
        "/Game/GameData/Lootables/Lootable_GoldenChest",
    ),
    "goldenchest",
    "golden",
    "golden_chest",
    "goldchest",
    alt_defs=("io_Lootable_GoldenChest",),
)
_register_offline_preset(
    # Prefer world IO_PlayerBank (usable/unlocked) over Script_PlayerBank which
    # often lands Locked when spawned thin-air without a live PersistentLevel template.
    "IO_PlayerBank",
    ("/Game/InteractiveObjects/GameSystemMachines/PlayerBank/Script_PlayerBank",),
    "bank",
    "playerbank",
    "player_bank",
    "IO_PlayerBank",
    "io_PlayerBank",
    alt_defs=("PlayerBank",),
)
_register_offline_preset(
    "Chest_BreakableLock_Lootable",
    (
        "/Game/InteractiveObjects/MissionSpecific/Mission_Side_City/Chest_BreakableLock/Script_Chest_BreakableLock_Lootable",
    ),
    "breakable_chest_script",
    alt_defs=("io_Chest_BreakableLock_Lootable",),
)
_register_offline_preset(
    "VendingMachine",
    ("/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine",),
    "vending_script",
    alt_defs=("io_VendingMachine_Munitions",),
)
_register_offline_preset(
    # Black Market needs its own actor-def — do not fold into generic VendingMachine.
    "IO_VendingMachine_BlackMarket",
    (
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine_BlackMarket",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/BlackMarket/Script_VendingMachine_BlackMarket",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/IO_VendingMachine_BlackMarket",
    ),
    "blackmarket",
    "black_market",
    "IO_VendingMachine_BlackMarket",
    "io_VendingMachine_BlackMarket",
    alt_defs=("IO_VendingMachine_BlackMarket", "io_VendingMachine_BlackMarket", "VendingMachine_BlackMarket"),
)
_register_offline_preset(
    "IO_VendingMachine_Munitions",
    (
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/IO_VendingMachine_Munitions",
    ),
    "munitions",
    "vending",
    "IO_VendingMachine_Munitions",
    "io_VendingMachine_Munitions",
    alt_defs=("IO_VendingMachine_Munitions", "io_VendingMachine_Munitions"),
)
_register_offline_preset(
    "IO_LostLoot_Machine",
    ("/Game/InteractiveObjects/GameSystemMachines/LostLoot/Script_LostLoot_Machine",),
    "lostloot",
    "lostlootmachine",
    "lost_loot",
    "IO_LostLoot_Machine",
    "io_LostLoot_Machine",
    alt_defs=("IO_LostLoot_Machine", "io_LostLoot_Machine"),
)
_register_offline_preset(
    "IO_FirmwareTransferMachine",
    (
        "/Game/InteractiveObjects/GameSystemMachines/FirmwareTransfer/Script_FirmwareTransferMachine",
        "/Game/InteractiveObjects/GameSystemMachines/Firmware/Script_FirmwareTransferMachine",
    ),
    "firmware",
    "IO_FirmwareTransferMachine",
    "io_FirmwareTransferMachine",
    alt_defs=("IO_FirmwareTransferMachine", "io_FirmwareTransferMachine"),
)
_register_offline_preset(
    "IO_AmmoGeyser",
    (),
    "ammogeyser",
    "IO_AmmoGeyser",
    "io_AmmoGeyser",
    alt_defs=("IO_AmmoGeyser", "io_AmmoGeyser"),
)
_register_offline_preset(
    "IO_ElectiSafe",
    (),
    "electisafe",
    "IO_ElectiSafe",
    "io_ElectiSafe",
    alt_defs=("IO_ElectiSafe", "io_ElectiSafe"),
)
_register_offline_preset(
    "IO_Lootable_Heist_MoneyBox",
    (),
    "moneybox",
    "IO_Lootable_Heist_MoneyBox",
    "io_Lootable_Heist_MoneyBox",
    alt_defs=("IO_Lootable_Heist_MoneyBox", "io_Lootable_Heist_MoneyBox"),
)
_register_offline_preset(
    "IO_Chest_BreakableLock_Lootable",
    (
        "/Game/InteractiveObjects/MissionSpecific/Mission_Side_City/Chest_BreakableLock/Script_Chest_BreakableLock_Lootable",
    ),
    "breakable_chest",
    "IO_Chest_BreakableLock_Lootable",
    "io_Chest_BreakableLock_Lootable",
    alt_defs=("IO_Chest_BreakableLock_Lootable", "io_Chest_BreakableLock_Lootable", "Chest_BreakableLock_Lootable"),
)


def _default_class_and_needles(name: str) -> Tuple[Optional[str], Tuple[str, ...]]:
    key = _alias_key(name)
    if key in _ALIASES:
        return _ALIASES[key]
    raw = (name or "").strip()
    needles: List[str] = [raw] if raw else []
    # PersistentLevel.IO_* paths: also match the short IO token (ASD-style).
    if "persistentlevel." in raw.lower():
        short = raw.rsplit(".", 1)[-1].strip()
        if short and short not in needles:
            needles.append(short)
    return None, tuple(needles)


def _io_short_token(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    if ":" in raw:
        raw = raw.rsplit(":", 1)[-1]
    if "." in raw:
        tail = raw.rsplit(".", 1)[-1]
        if tail.lower().startswith(("io_", "lootable_")):
            return tail
    if raw.lower().startswith(("io_", "lootable_")):
        return raw
    return ""


def _looks_like_io_name(name: str) -> bool:
    low = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not low:
        return False
    if (
        low.startswith("io_")
        or low.startswith("lootable_")
        or "persistentlevel.io_" in low
        or "persistentlevel.lootable_" in low
        or "playerbank" in low
        or "goldenchest" in low
        or "vendingmachine" in low
        or "lostloot" in low
        or "firmware" in low
        or "blackmarket" in low
    ):
        return True
    # Short aliases used by the EXE / BMS catalog — never treat as Char_ find_all bait.
    if _alias_key(name) in (
        "bank",
        "playerbank",
        "player_bank",
        "io_playerbank",
        "io_player_bank",
        "goldenchest",
        "golden_chest",
        "golden",
        "firmware",
        "blackmarket",
        "black_market",
        "lostloot",
        "lost_loot",
        "vending",
        "munitions",
        "maurice",
        "barrel",
        "barrels",
        "breakable_chest",
        "moneybox",
        "electisafe",
        "ammogeyser",
    ):
        return True
    return False


def _exact_persistent_io_paths(name: str) -> Tuple[str, ...]:
    """Cheap find_object paths for world-placed IO templates (no find_all)."""
    raw = (name or "").strip()
    short = _io_short_token(raw)
    out: List[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        p = (path or "").strip()
        if not p or p in seen:
            return
        seen.add(p)
        out.append(p)

    if raw.startswith("/Game/"):
        _add(raw)
    elif "persistentlevel." in raw.lower():
        if ":" in raw:
            _add(raw)
        else:
            tail = raw.split(".", 1)[-1] if raw.lower().startswith("persistentlevel.") else raw
            _add(f"/Game/Maps/WorldLevels/World_P.World_P:PersistentLevel.{tail}")
    if short:
        _add(f"/Game/Maps/WorldLevels/World_P.World_P:PersistentLevel.{short}")
    return tuple(out)


def _find_exact_loaded_io(
    name: str,
    class_override: Optional[str] = None,
) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    """Resolve a PersistentLevel IO via find_object only (safe on PlayerTick)."""
    paths = _exact_persistent_io_paths(name)
    if not paths:
        return None, None, None
    classes: List[str] = []
    if class_override:
        classes.append(class_override)
    for cls_name in (
        "OakVendingMachine",
        "OakLostLootMachine",
        "LootableObject",
        "OakInteractiveObject",
        "OakLootable",
        "OakLootableContainer",
        "Actor",
    ):
        if cls_name not in classes:
            classes.append(cls_name)
    for cls_name in classes:
        for path in paths:
            try:
                obj = find_object(cls_name, path)
            except Exception:
                obj = None
            if obj is None:
                continue
            cls = _source_class(obj, cls_name)
            if cls is None:
                continue
            _log_info(f"find_object template {cls_name!r}: {path}")
            return cls, obj, cls_name
    return None, None, None


def _safe_find_class(class_name: str) -> Optional[Any]:
    try:
        return find_class(class_name)
    except Exception as exc:
        _log_warn(f"Class lookup failed for {class_name!r}: {exc}")
        return None


def _candidate_sources(class_name: str, needles: Sequence[str], generated_only: bool = True) -> List[Any]:
    try:
        found = list(find_all(class_name, False))
    except TypeError:
        try:
            found = list(find_all(class_name))
        except Exception as exc:
            _log_warn(f"find_all({class_name!r}) failed: {exc}")
            return []
    except Exception as exc:
        _log_warn(f"find_all({class_name!r}) failed: {exc}")
        return []

    lowered = [n.lower() for n in needles if n]
    out: List[Any] = []
    for obj in found:
        text = str(obj)
        low = text.lower()
        if generated_only and "_generated_" not in low:
            continue
        if lowered and not any(n in low for n in lowered):
            continue
        if "/script/" in low or "default__" in low:
            continue
        out.append(obj)
    return out


def _class_display_name(cls: Any) -> str:
    try:
        return str(cls).rsplit(".", 1)[-1].strip("'")
    except Exception:
        return repr(cls)


def _source_class(source: Any, fallback_class_name: Optional[str] = None) -> Optional[Any]:
    try:
        cls = getattr(source, "Class", None)
        if cls is not None:
            return cls
    except Exception:
        pass
    if fallback_class_name:
        return _safe_find_class(fallback_class_name)
    return None


def _candidate_sources_multi(class_names: Sequence[str], needles: Sequence[str], generated_only: bool = True) -> List[Tuple[str, Any]]:
    out: List[Tuple[str, Any]] = []
    seen: set[str] = set()
    for class_name in class_names:
        for obj in _candidate_sources(class_name, needles, generated_only=generated_only):
            key = str(obj)
            if key in seen:
                continue
            seen.add(key)
            out.append((class_name, obj))
    return out


def _find_template(name: str, class_override: Optional[str] = None, generated_only: bool = True) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    default_class, needles = _default_class_and_needles(name)
    class_name = class_override or default_class

    # IO / PersistentLevel: find_object first. find_all(OakInteractiveObject) freezes BL4.
    if _looks_like_io_name(name) or "persistentlevel." in (name or "").lower() or (name or "").startswith("/Game/"):
        exact_cls, exact_src, exact_cn = _find_exact_loaded_io(name, class_override=class_name)
        if exact_cls is not None and exact_src is not None:
            return exact_cls, exact_src, exact_cn or class_name

    # Alias keywords (goldenchest / firmware / …): try canonical PersistentLevel tokens
    # before expensive find_all scans — dump-proven when the world IO is already loaded.
    for needle in needles:
        if not (_looks_like_io_name(needle) or str(needle).lower().startswith("lootable_")):
            continue
        exact_cls, exact_src, exact_cn = _find_exact_loaded_io(needle, class_override=class_name)
        if exact_cls is not None and exact_src is not None:
            return exact_cls, exact_src, exact_cn or class_name
    canon = _LOGO_ACTOR_CANONICAL.get(_alias_key(name))
    if canon and canon not in needles:
        exact_cls, exact_src, exact_cn = _find_exact_loaded_io(canon, class_override=class_name)
        if exact_cls is not None and exact_src is not None:
            return exact_cls, exact_src, exact_cn or class_name

    # Fast path when a class is known or supplied.
    if class_name:
        # Broad interactive / Actor classes: never find_all for IO names (game freeze).
        class_low = class_name.lower()
        io_unsafe_scan = class_low in ("oakinteractiveobject", "oakinteractableobject", "actor")
        if _looks_like_io_name(name) and io_unsafe_scan:
            _log_warn(
                f"Skipping find_all({class_name!r}) for IO {name!r} "
                "(use find_object / OakVendingMachine instead)."
            )
        else:
            cls = _safe_find_class(class_name)
            if cls is not None:
                matches = _candidate_sources(class_name, needles, generated_only=generated_only)
                if not matches and generated_only:
                    matches = _candidate_sources(class_name, needles, generated_only=False)
                if matches:
                    return cls, matches[0], class_name
                _log_warn(f"No live template found in class={class_name!r}; falling back to keyword class scan.")
            else:
                _log_warn(f"Class {class_name!r} is not loaded/valid; falling back to keyword class scan.")

    # Discovery path for things like Golden Chest / Firmware where the class name
    # changes or is not obvious. Spawn with the matched source actor's own Class.
    scan_classes: List[str] = []
    if class_name and class_name.lower() not in ("oakinteractiveobject", "oakinteractableobject", "actor"):
        scan_classes.append(class_name)
    # For IO tokens prefer narrow classes only — never Actor / full interactive scan.
    if _looks_like_io_name(name):
        for c in ("OakVendingMachine", "OakLostLootMachine", "OakLootable", "OakLootableContainer"):
            if c not in scan_classes:
                scan_classes.append(c)
        # Still no broad OakInteractiveObject / Actor — those find_all freezes with held loot.
        if not scan_classes:
            _log_error(
                f"No safe class scan for IO {name!r} (refusing Actor/OakInteractiveObject find_all)."
            )
            return None, None, class_name
        matches = _candidate_sources_multi(scan_classes, needles, generated_only=generated_only)
        if not matches and generated_only:
            _log_info("No _Generated_ matches; retrying non-generated keyword scan (IO-safe classes only).")
            matches = _candidate_sources_multi(scan_classes, needles, generated_only=False)
        if not matches:
            _log_error(
                f"No live template found for IO name={name!r} needles={needles} "
                "(skipped Actor find_all)."
            )
            return None, None, class_name
    else:
        scan_classes.extend(c for c in _CLASS_SCAN_ORDER if c not in scan_classes)
        matches = _candidate_sources_multi(scan_classes, needles, generated_only=generated_only)
        if not matches and generated_only:
            _log_info("No _Generated_ matches; retrying non-generated keyword scan.")
            matches = _candidate_sources_multi(scan_classes, needles, generated_only=False)
        if not matches:
            _log_error(f"No live template found for name={name!r} needles={needles}. Try oak_targets {name} --include-non-generated or oak_spawn {name} --class <known class>.")
            return None, None, class_name

    matched_class_name, source = matches[0]
    cls = _source_class(source, matched_class_name)
    if cls is None:
        _log_error(f"Matched source but could not read/spawn its Class: {source}")
        return None, source, matched_class_name
    _log_info(f"Discovered template via class={matched_class_name!r}: {source}")
    return cls, source, matched_class_name


def _copy_actor_data(source: Any, actor: Any) -> None:
    try:
        src_data = getattr(source, "GbxActorData", None)
        dst_data = getattr(actor, "GbxActorData", None)
    except Exception:
        return
    if src_data is None or dst_data is None:
        return

    # This is the critical line from the console one-liner.  Keep it narrow first.
    for field_name in ("GbxActorDef", "ActorPartList", "ActorPartSelections", "SpawnDetails"):
        try:
            value = getattr(src_data, field_name)
        except Exception:
            continue
        try:
            setattr(dst_data, field_name, value)
            _log_info(f"Copied GbxActorData.{field_name}.")
        except Exception:
            pass

    # Vending machines often stay scripts=0 unless ScriptData rows are mirrored too.
    try:
        src_sd = getattr(source, "ScriptData", None)
        dst_sd = getattr(actor, "ScriptData", None)
    except Exception:
        return
    if src_sd is None or dst_sd is None:
        return
    for field_name in ("Scripts", "Instances", "InstanceDataCache", "ReplicatedInstances"):
        try:
            value = getattr(src_sd, field_name)
        except Exception:
            continue
        try:
            setattr(dst_sd, field_name, value)
            _log_info(f"Copied ScriptData.{field_name}.")
        except Exception as exc:
            _log_warn(f"ScriptData.{field_name} copy failed: {exc}")


def _script_count(actor: Any) -> int:
    try:
        return len(_script_instances(actor))
    except Exception:
        return 0


def _bring_live_actor_to_player(
    source: Any,
    *,
    label: str,
    distance: float,
    z_offset: float,
    scale: float,
    activate: bool,
    enable: Sequence[str],
    disable: Sequence[str],
    delay: float,
) -> Optional[Any]:
    """Relocate a live world machine in front of the player (usable fallback)."""
    _, pawn, _world, _gs = _spawn_context()
    if pawn is None or source is None:
        return None
    transform = _spawn_transform_for_index(
        pawn,
        index=0,
        count=1,
        distance=distance,
        spacing=0.0,
        z_offset=z_offset,
        scale=scale,
    )
    try:
        loc = transform.Translation
        rot = transform.Rotation
    except Exception:
        return None
    if not _try_teleport_actor(source, loc, rot):
        _log_error(f"Failed to relocate live {label}: {source}")
        return None
    _log_info(f"Relocated live {label} to player: {source}")
    _SPAWNED.append(
        DeployedActor(
            label=label,
            source=source,
            actor=source,
            actor_key=_actor_key(source),
            class_name=_class_name(source),
        )
    )
    if activate:
        _schedule_script_activation(
            source,
            label,
            source=source,
            enable=enable,
            disable=disable,
            delay=delay,
        )
    return source


# World-placed OakVendingMachine tokens (WhatAmILookingAt). No thin-air packages exist.
_VENDING_LIVE_ALIASES: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "blackmarket": ("IO_VendingMachine_BlackMarket", ("IO_VendingMachine_BlackMarket", "VendingMachine_BlackMarket", "BlackMarket")),
    "black_market": ("IO_VendingMachine_BlackMarket", ("IO_VendingMachine_BlackMarket", "VendingMachine_BlackMarket", "BlackMarket")),
    "io_vendingmachine_blackmarket": ("IO_VendingMachine_BlackMarket", ("IO_VendingMachine_BlackMarket", "VendingMachine_BlackMarket", "BlackMarket")),
    "vendingmachine_blackmarket": ("IO_VendingMachine_BlackMarket", ("IO_VendingMachine_BlackMarket", "VendingMachine_BlackMarket", "BlackMarket")),
    "maurice": ("IO_VendingMachine_Legend_Legendary", ("IO_VendingMachine_Legend_Legendary", "VendingMachine_Legend_Legendary", "Legend_Legendary")),
    "maurices": ("IO_VendingMachine_Legend_Legendary", ("IO_VendingMachine_Legend_Legendary", "VendingMachine_Legend_Legendary", "Legend_Legendary")),
    "io_vendingmachine_legend_legendary": (
        "IO_VendingMachine_Legend_Legendary",
        ("IO_VendingMachine_Legend_Legendary", "VendingMachine_Legend_Legendary", "Legend_Legendary"),
    ),
    "vendingmachine_legend_legendary": (
        "IO_VendingMachine_Legend_Legendary",
        ("IO_VendingMachine_Legend_Legendary", "VendingMachine_Legend_Legendary", "Legend_Legendary"),
    ),
    "io_vendingmachine_legend_a": (
        "IO_VendingMachine_Legend_A",
        ("IO_VendingMachine_Legend_A", "VendingMachine_Legend_A", "Legend_A"),
    ),
    "vendingmachine_legend_a": (
        "IO_VendingMachine_Legend_A",
        ("IO_VendingMachine_Legend_A", "VendingMachine_Legend_A", "Legend_A"),
    ),
}


def _spawn_live_oak_vending_machine(
    name: str,
    *,
    class_override: Optional[str],
    distance: float,
    z_offset: float,
    scale: float,
    delay: float,
    enable: Sequence[str],
    disable: Sequence[str],
    activate: bool,
    count: int,
    spacing: float,
    pawn: Any,
    world: Any,
    gs: Any,
) -> Optional[Any]:
    """Duplicate (or relocate) a live OakVendingMachine — the only working path."""
    entry_key = _alias_key(name)
    preset = _VENDING_LIVE_ALIASES.get(entry_key)
    if preset is None:
        return None
    canon, needles = preset
    # Temporarily enrich alias needles for this lookup.
    bm_cls, bm_src, bm_cn = _find_template(
        canon,
        class_override or "OakVendingMachine",
        generated_only=False,
    )
    if bm_cls is None or bm_src is None:
        bm_cls, bm_src, bm_cn = _find_template(
            canon,
            class_override or "OakVendingMachine",
            generated_only=True,
        )
    # Keyword scan with explicit needles if alias class path missed Generated UAID actors.
    if bm_cls is None or bm_src is None:
        matches = _candidate_sources("OakVendingMachine", needles, generated_only=False)
        if not matches:
            matches = _candidate_sources("OakVendingMachine", needles, generated_only=True)
        if matches:
            bm_src = matches[0]
            bm_cls = _source_class(bm_src, "OakVendingMachine")
            bm_cn = "OakVendingMachine"
    if bm_cls is None or bm_src is None:
        _log_error(
            f"No live OakVendingMachine template for {name!r} (needles={needles}). "
            "Visit a real machine once (WhatAmILookingAt), then retry. "
            "There is no separate thin-air package/file to load."
        )
        return None

    _log_info(f"Using live OakVendingMachine template for {name!r}: {bm_src}")
    _cache_actor_def(canon, bm_src)
    _cache_actor_def(entry_key, bm_src)

    total = max(1, int(count))
    first_actor: Optional[Any] = None
    for idx in range(total):
        transform = _spawn_transform_for_index(
            pawn,
            index=idx,
            count=total,
            distance=distance,
            spacing=spacing,
            z_offset=z_offset,
            scale=scale,
        )
        actor = _spawn_actor_deferred(
            gs,
            world,
            bm_cls,
            transform,
            class_name=bm_cn or "OakVendingMachine",
            source=bm_src,
            collision_handling=1,
        )
        if actor is None:
            continue
        # Deferred duplicates often land with scripts=0; mirror ScriptData again post-finish.
        _copy_actor_data(bm_src, actor)
        if _script_count(actor) <= 0:
            _log_warn(
                f"OakVendingMachine duplicate for {canon} has no ScriptData; "
                "relocating the live world machine instead (usable)."
            )
            try:
                _destroy_actor(actor)
            except Exception:
                pass
            return _bring_live_actor_to_player(
                bm_src,
                label=canon,
                distance=distance,
                z_offset=z_offset,
                scale=scale,
                activate=activate,
                enable=enable,
                disable=disable,
                delay=delay,
            )
        _SPAWNED.append(
            DeployedActor(
                label=canon,
                source=bm_src,
                actor=actor,
                actor_key=_actor_key(actor),
                class_name=_class_name(actor),
            )
        )
        if first_actor is None:
            first_actor = actor

    if first_actor is not None:
        if activate:
            _schedule_script_activation(
                first_actor,
                canon,
                source=bm_src,
                enable=enable,
                disable=disable,
                delay=delay,
            )
        return first_actor
    return _bring_live_actor_to_player(
        bm_src,
        label=canon,
        distance=distance,
        z_offset=z_offset,
        scale=scale,
        activate=activate,
        enable=enable,
        disable=disable,
        delay=delay,
    )


def _destroy_actor(actor: Any) -> None:
    for func_name in ("K2_DestroyActor", "DestroyActor", "Destroy"):
        func = getattr(actor, func_name, None)
        if callable(func):
            try:
                func()
                return
            except Exception:
                pass

def _script_instance(actor: Any) -> Optional[Any]:
    try:
        instances = actor.ScriptData.Instances
    except Exception:
        return None
    try:
        if len(instances):
            return instances[0]
    except Exception:
        pass
    return None


def _unique_states(*groups: Sequence[str]) -> Tuple[str, ...]:
    out: List[str] = []
    seen: set[str] = set()
    for group in groups:
        for state in group:
            if not state or state in seen:
                continue
            seen.add(state)
            out.append(state)
    return tuple(out)




def _source_schema_enable_states(source: Any) -> Tuple[str, ...]:
    """Return script states implied by a template actor's GbxActorDef schema.

    Player bank proved that usability can be gated by a schema state named
    MachineState whose usable value is ActiveIdle.  The normal broad activation
    pass enabled Active/ActiveIdle_Anim, but not ActiveIdle itself.  Keep this
    helper defensive: if any of the experimental fields are missing, it simply
    returns no extra states.
    """
    try:
        gbx_def = source.GbxActorData.GbxActorDef
        schema = gbx_def._experimental_instance.actorstateschema._experimental_instance
        machines = schema.StateMachines
    except Exception:
        return ()

    out: List[str] = []
    for machine in machines:
        try:
            machine_name = str(machine.Name)
            states = [str(state) for state in machine.States]
        except Exception:
            continue
        low_name = machine_name.lower()
        low_states = {state.lower(): state for state in states}
        # PlayerBank: MachineState has Inactive/ActiveIdle, and use responses
        # select on MachineState.  Enabling ActiveIdle makes the normal prompt
        # usable without firing the OnUsed event directly.
        if low_name == "machinestate" and "activeidle" in low_states:
            out.append(low_states["activeidle"])
        # Bool actor-state machines often use FALSE as the non-busy/default
        # state.  This is harmless for scripts that do not expose it.
        if getattr(machine, "bIsBool", False):
            false_state = low_states.get("false")
            if false_state:
                out.append(false_state)
    return tuple(out)


def _script_instances(actor: Any) -> List[Any]:
    try:
        instances = actor.ScriptData.Instances
    except Exception:
        return []
    try:
        return [instances[i] for i in range(len(instances))]
    except Exception:
        try:
            return list(instances)
        except Exception:
            return []


def _call_if_present(obj: Any, names: Sequence[str], *args: Any, log_calls: bool = True) -> None:
    for name in names:
        try:
            fn = getattr(obj, name, None)
        except Exception:
            fn = None
        if not callable(fn):
            continue
        try:
            fn(*args)
            if log_calls:
                _log_info(f"called {name} on {obj}")
        except TypeError:
            # Some Unreal wrappers expose overloads with different signatures.
            try:
                fn()
                if log_calls:
                    _log_info(f"called {name}() on {obj}")
            except Exception as exc:
                _log_warn(f"{name} failed: {exc}")
        except Exception as exc:
            _log_warn(f"{name} failed: {exc}")


def _poke_actor_enabled(actor: Any, *, log_calls: bool = True) -> None:
    for name, args in (
        ("SetActorHiddenInGame", (False,)),
        ("SetActorEnableCollision", (True,)),
        ("SetActorTickEnabled", (True,)),
    ):
        _call_if_present(actor, (name,), *args, log_calls=log_calls)
    for comp_name in ("RootComponent", "Mesh", "StaticMeshComponent", "CollisionComponent", "InteractionComponent", "UseComponent"):
        try:
            comp = getattr(actor, comp_name, None)
        except Exception:
            comp = None
        if comp is None:
            continue
        _call_if_present(comp, ("SetHiddenInGame",), False, True, log_calls=log_calls)
        _call_if_present(comp, ("SetVisibility",), True, True, log_calls=log_calls)
        _call_if_present(comp, ("SetComponentTickEnabled",), True, log_calls=log_calls)
        _call_if_present(comp, ("SetCollisionEnabled",), 1, log_calls=log_calls)
        _call_if_present(comp, ("SetGenerateOverlapEvents",), True, log_calls=log_calls)


def _script_debug(inst: Any, limit: int = 60) -> None:
    names = []
    for name in dir(inst):
        low = name.lower()
        if any(token in low for token in ("state", "enable", "active", "usable", "use", "interact", "bank", "anim", "open", "lock")):
            names.append(name)
    _log_info(f"script={inst} useful_attrs={names[:limit]}")


def _set_script_states(actor: Any, enable: Sequence[str], disable: Sequence[str], *, debug: bool = False) -> None:
    instances = _script_instances(actor)
    _log_info(f"scripts={len(instances)} actor={actor}")
    _poke_actor_enabled(actor)
    if not instances:
        _log_warn("No ScriptData.Instances found; actor spawned but was not script-activated.")
        return
    for inst in instances:
        if debug:
            _script_debug(inst)
        for state in disable:
            try:
                inst.SetScriptStateEnabled(state, False)
                _log_info(f"disabled script state {state!r}")
            except Exception as exc:
                _log_warn(f"disable {state!r} failed: {exc}")
        for state in enable:
            try:
                inst.SetScriptStateEnabled(state, True)
                _log_info(f"enabled script state {state!r}")
            except Exception as exc:
                _log_warn(f"enable {state!r} failed: {exc}")
        _call_if_present(inst, (
            "UpdateAnimState", "UpdateState", "RefreshState", "Refresh",
            "Activate", "Enable", "SetEnabled", "SetUsable", "SetUseable",
            "SetInteractionEnabled", "SetInteractive",
        ), True)


def _split_states(value: Optional[str], defaults: Sequence[str]) -> Tuple[str, ...]:
    if value is None:
        return tuple(defaults)
    return tuple(part.strip() for part in value.split(",") if part.strip())



def _actor_def_name(def_ptr: Any) -> str:
    """Best-effort stable display name for an FGbxDefPtr."""
    for attr in ("_experimental_name", "Name", "name"):
        try:
            value = getattr(def_ptr, attr, None)
        except Exception:
            value = None
        if value:
            return str(value)
    try:
        text = str(def_ptr)
        if "FGbxDefPtr(" in text and "'" in text:
            return text.split("'", 2)[1]
        return text
    except Exception:
        return ""


def _candidate_actor_def_sources(query: str, *, class_override: Optional[str] = None) -> List[Any]:
    """Find live objects with GbxActorData.GbxActorDef matching a query.

    This is intentionally broader than _find_template: AI actor defs often live
    on OakCharacter sources that are not _Generated_ and may have display names
    such as Char_NPC_Mancubus.
    """
    needles = [query.lower()]
    key = _alias_key(query)
    if key in _ALIASES:
        needles.extend(n.lower() for n in _ALIASES[key][1] if n)
    classes: List[str] = []
    if class_override:
        classes.append(class_override)
    for cls_name in ("OakCharacter", "OakPawn", "OakActor", "Actor"):
        if cls_name not in classes:
            classes.append(cls_name)
    out: List[Any] = []
    seen: set[str] = set()
    for cls_name in classes:
        try:
            objects = list(find_all(cls_name, False))
        except TypeError:
            try:
                objects = list(find_all(cls_name))
            except Exception:
                continue
        except Exception:
            continue
        for obj in objects:
            text = str(obj).lower()
            if "default__" in text or "/script/" in text:
                continue
            try:
                def_ptr = obj.GbxActorData.GbxActorDef
            except Exception:
                continue
            def_name = _actor_def_name(def_ptr).lower()
            haystack = text + " " + def_name
            if needles and not any(n in haystack for n in needles):
                continue
            key_obj = str(obj)
            if key_obj in seen:
                continue
            seen.add(key_obj)
            out.append(obj)
    return out


def _cache_actor_def(alias: str, source: Any) -> bool:
    try:
        def_ptr = source.GbxActorData.GbxActorDef
    except Exception as exc:
        _log_error(f"{source} does not expose GbxActorData.GbxActorDef: {exc}")
        return False
    cache_key = _alias_key(alias)
    _ACTOR_DEF_CACHE[cache_key] = def_ptr
    _ACTOR_DEF_CACHE_SOURCE[cache_key] = str(source)
    _log_info(f"cached actor def {cache_key!r}: {_actor_def_name(def_ptr)} from {source}")
    return True


def _cache_actor_def_from_spawned_actor(alias: str, actor: Any) -> bool:
    """Cache the real GbxActorDef from a successfully spawned actor.

    Direct shell-based spawns can work once, but later calls may fail because the
    synthetic shell no longer resolves cleanly.  A live spawned actor contains the
    real GbxActorData.GbxActorDef, so save it immediately for future calls.
    """
    if actor is None:
        return False
    if _is_spawner_like(actor):
        _log_warn(f"auto-cache skipped spawner-like delta object for {alias!r}: {actor}")
        return False
    try:
        def_ptr = actor.GbxActorData.GbxActorDef
    except Exception as exc:
        _log_warn(f"auto-cache failed for {alias!r}: spawned actor has no GbxActorData.GbxActorDef: {exc}")
        return False

    if def_ptr is None:
        _log_warn(f"auto-cache failed for {alias!r}: spawned actor GbxActorDef is None")
        return False

    cache_key = _alias_key(alias)
    _ACTOR_DEF_CACHE[cache_key] = def_ptr
    _ACTOR_DEF_CACHE_SOURCE[cache_key] = f"auto-spawned:{actor}"
    _log_info(f"auto-cached actor def {cache_key!r}: {_actor_def_name(def_ptr)} from spawned actor {actor}")
    return True



def _nearest_oak_spawners(pawn: Any, limit: int = 8) -> List[Any]:
    try:
        pl = pawn.K2_GetActorLocation()
    except Exception:
        pl = None
    spawners: List[Tuple[float, Any]] = []
    try:
        objects = list(find_all("OakSpawner", False))
    except TypeError:
        try:
            objects = list(find_all("OakSpawner"))
        except Exception as exc:
            _log_error(f"find_all('OakSpawner') failed: {exc}")
            return []
    except Exception as exc:
        _log_error(f"find_all('OakSpawner') failed: {exc}")
        return []
    for sp in objects:
        low = str(sp).lower()
        if "default__" in low or "/script/" in low:
            continue
        dist = 0.0
        if pl is not None:
            try:
                loc = sp.K2_GetActorLocation()
                dx, dy, dz = float(loc.X - pl.X), float(loc.Y - pl.Y), float(loc.Z - pl.Z)
                dist = (dx * dx + dy * dy + dz * dz) ** 0.5
            except Exception:
                dist = 999999999.0
        spawners.append((dist, sp))
    spawners.sort(key=lambda item: item[0])
    return [sp for _, sp in spawners[: max(1, int(limit))]]


def _alive_actors_for_spawner_component(comp: Any) -> List[Any]:
    for args in ((0, False), (0, True)):
        try:
            actors = comp.GetAliveActors(*args)
            try:
                return [actors[i] for i in range(len(actors))]
            except Exception:
                return list(actors)
        except Exception:
            continue
    return []


def _poll_spawner_for_alive_actors(
    comp: Any,
    *,
    timeout: float = 3.0,
    interval: float = 0.15,
) -> List[Any]:
    """Poll a spawner after ResetSpawner because BL4/Oak spawning can be async.

    Some valid actor defs report resolved=True immediately, but GetAliveActors()
    is still empty for a few frames. The old oak_spawnai path checked once and
    falsely reported failure. This waits briefly for the spawner to finish.
    """
    deadline = time.monotonic() + max(0.0, float(timeout))
    last_actors: List[Any] = []

    while True:
        actors = _alive_actors_for_spawner_component(comp)
        if actors:
            # One ResetSpawner should yield at most one primary actor for this path.
            return actors[:1]
        last_actors = actors

        try:
            if int(comp.GetNumAliveActors(0)) > 0:
                actors = _alive_actors_for_spawner_component(comp)
                if actors:
                    return actors
        except Exception:
            pass

        if time.monotonic() >= deadline:
            return last_actors

        time.sleep(max(0.01, float(interval)))


def _spawner_counts(comp: Any) -> Tuple[int, int, int, int]:
    """Best-effort OakSpawner count tuple: alive, spawned, dead, total."""
    out: List[int] = []
    for fn_name in ("GetNumAliveActors", "GetNumSpawnedActors", "GetNumDeadActors", "GetNumTotalActors"):
        try:
            out.append(int(getattr(comp, fn_name)(0)))
        except Exception:
            out.append(-1)
    return out[0], out[1], out[2], out[3]



def _try_teleport_actor(actor: Any, loc: Any, rot: Any) -> bool:
    moved = False
    try:
        moved = bool(actor.K2_TeleportTo(loc, rot))
    except Exception:
        moved = False
    if not moved:
        try:
            actor.RootComponent.RelativeLocation = loc
            moved = True
        except Exception:
            pass
    try:
        cm = getattr(actor, "CharacterMovement", None)
        if cm is not None and hasattr(cm, "StopMovementImmediately"):
            cm.StopMovementImmediately()
    except Exception:
        pass
    return moved




def _duplicate_oak_spawner_at(source_spawner: Any, transform: Any, *, index: int = 0) -> Optional[Any]:
    """Duplicate/spawn a fresh OakSpawner actor near the target transform.

    Existing world spawners can be encounter-owned, exhausted, cooldown-blocked,
    or otherwise unsuitable after one use. For --count N, fresh spawner actors give
    each requested spawn its own isolated spawner state.
    """
    if source_spawner is None:
        return None

    _pc, _pawn, world, gs = _spawn_context()
    if world is None or gs is None:
        return None

    try:
        cls = getattr(source_spawner, "Class", None)
    except Exception:
        cls = None
    if cls is None:
        try:
            cls = find_class("OakSpawner")
        except Exception as exc:
            _log_warn(f"duplicate spawner {index}: OakSpawner class lookup failed: {exc}")
            return None

    spawner = _spawn_actor_deferred(
        gs,
        world,
        cls,
        transform,
        class_name="OakSpawner",
        source=source_spawner,
        collision_handling=2,
    )
    if spawner is None:
        _log_warn(f"duplicate spawner {index}: spawn failed")
        return None

    # Ensure the duplicate is usable and not hidden/disabled.
    _poke_actor_enabled(spawner, log_calls=False)

    try:
        comp = spawner.GetSpawnerComponent()
        for fn_name, args in (
            ("SetSpawnerEnabled", (True,)),
            ("SetSpawnPointEnabled", (True,)),
        ):
            try:
                getattr(comp, fn_name)(*args)
            except Exception:
                pass
    except Exception as exc:
        _log_warn(f"duplicate spawner {index}: component prep failed: {exc}")

    _log_info(f"duplicated OakSpawner {index}: source={source_spawner} duplicate={spawner}")
    return spawner


def _spawners_for_direct_count(
    pawn: Any,
    *,
    count: int,
    distance: float,
    spacing: float,
) -> List[Any]:
    """Return count isolated spawners by duplicating nearest OakSpawner when possible."""
    total = max(1, int(count))
    source_spawners = _nearest_oak_spawners(pawn, limit=max(1, min(8, total)))
    if not source_spawners:
        return []

    out: List[Any] = []
    source = source_spawners[0]

    for idx in range(total):
        transform = _spawn_transform_for_index(
            pawn,
            index=idx,
            count=total,
            distance=distance,
            spacing=spacing,
            z_offset=0.0,
            scale=1.0,
        )
        dup = _duplicate_oak_spawner_at(source, transform, index=idx + 1)
        if dup is not None:
            out.append(dup)

    if len(out) < total:
        _log_warn(
            f"duplicated {len(out)}/{total} OakSpawners; falling back to existing spawners for remaining slots"
        )
        existing = _nearest_oak_spawners(pawn, limit=total)
        for sp in existing:
            if len(out) >= total:
                break
            out.append(sp)

    return out[:total]





def _is_spawner_like(obj: Any) -> bool:
    """Return True for OakSpawner / spawn helper actors that must not count as spawned AI."""
    try:
        cls = getattr(obj, "Class", None)
        cls_text = str(cls or "")
    except Exception:
        cls_text = ""
    try:
        obj_text = str(obj or "")
    except Exception:
        obj_text = ""

    low = (cls_text + " " + obj_text).lower()
    return (
        "oakspawner" in low
        or ".spawner" in low
        or "spawner_" in low
        or "spawnpoint" in low
    )


def _has_actor_def_data(obj: Any) -> bool:
    """Best-effort check for actors that can expose a real GbxActorDef."""
    try:
        return getattr(obj.GbxActorData, "GbxActorDef", None) is not None
    except Exception:
        return False

def _actor_location(actor: Any) -> Optional[Any]:
    try:
        return actor.K2_GetActorLocation()
    except Exception:
        return None


def _distance_sq(a: Any, b: Any) -> float:
    try:
        dx = float(a.X - b.X)
        dy = float(a.Y - b.Y)
        dz = float(a.Z - b.Z)
        return dx * dx + dy * dy + dz * dz
    except Exception:
        return 999999999999.0


def _world_actor_snapshot() -> set[str]:
    """Snapshot currently loaded non-default actors for world-delta spawn detection."""
    seen: set[str] = set()
    for cls_name in ("OakCharacter", "OakPawn", "OakActor", "Actor"):
        try:
            objs = list(find_all(cls_name, False))
        except TypeError:
            try:
                objs = list(find_all(cls_name))
            except Exception:
                continue
        except Exception:
            continue
        for obj in objs:
            low = str(obj).lower()
            if "default__" in low or "/script/" in low:
                continue
            if _is_spawner_like(obj):
                continue
            seen.add(str(obj))
    return seen


def _find_new_world_actors_near(
    before: set[str],
    loc: Any,
    *,
    radius: float = 4000.0,
    expected_name: str = "",
) -> List[Any]:
    """Find actors that appeared after spawn but were not reported by GetAliveActors.

    Some OakSpawner paths spawn valid actors but do not attach them to the spawner's
    alive list. This catches those actors by scanning the world after spawning.
    """
    radius_sq = float(radius) * float(radius)
    needles = [n.lower() for n in _default_class_and_needles(expected_name)[1] if n]
    out: List[Any] = []
    seen: set[str] = set()

    for cls_name in ("OakCharacter", "OakPawn", "OakActor", "Actor"):
        try:
            objs = list(find_all(cls_name, False))
        except TypeError:
            try:
                objs = list(find_all(cls_name))
            except Exception:
                continue
        except Exception:
            continue

        for obj in objs:
            key = str(obj)
            if key in before or key in seen:
                continue
            low = key.lower()
            if "default__" in low or "/script/" in low:
                continue
            if _is_spawner_like(obj):
                continue

            obj_loc = _actor_location(obj)
            if obj_loc is not None and loc is not None:
                if _distance_sq(obj_loc, loc) > radius_sq:
                    continue

            # Prefer matching names, but do not require it because generated actors
            # may use generic runtime names.
            if needles and any(n in low for n in needles):
                out.insert(0, obj)
            else:
                out.append(obj)
            seen.add(key)

    out.sort(key=lambda actor: 0 if _has_actor_def_data(actor) else 1)
    return out

def _spawn_cached_actor_def(
    name: str,
    *,
    distance: float,
    count: int = 1,
    spacing: float = 125.0,
) -> Optional[Any]:
    cache_key = _alias_key(name)
    def_ptr = _ACTOR_DEF_CACHE.get(cache_key)
    if def_ptr is None:
        return None
    _log_info(f"using cached actor def {cache_key!r}: {_actor_def_name(def_ptr)}")
    _, pawn, _world, _gs = _spawn_context()
    if pawn is None:
        return None
    spawners = _nearest_oak_spawners(pawn, limit=max(3, int(count) + 1))
    if not spawners:
        _log_error(f"No live OakSpawner found for cached actor-def spawn {name!r}.")
        return None

    # v10 direct path spawner duplication is applied in oak_spawnai direct function.

    first_actor: Optional[Any] = None
    total_spawned = 0
    for idx in range(max(1, int(count))):
        sp = spawners[idx % len(spawners)]
        try:
            comp = sp.GetSpawnerComponent()
        except Exception as exc:
            _log_warn(f"{sp}: GetSpawnerComponent failed: {exc}")
            continue
        before = set()
        for actor in _alive_actors_for_spawner_component(comp):
            before.add(str(actor))
        world_before = _world_actor_snapshot()
        try:
            comp.DestroyAllActors()
        except Exception:
            pass
        try:
            comp.PushActorDef("SSP", def_ptr, True)
        except Exception as exc:
            _log_error(f"PushActorDef failed for cached {cache_key!r} ({_actor_def_name(def_ptr)}): {exc}")
            return None
        for fn_name, args in (("SetSpawnerEnabled", (True,)), ("SetSpawnPointEnabled", (True,))):
            try:
                getattr(comp, fn_name)(*args)
            except Exception as exc:
                _log_warn(f"{fn_name} failed on {comp}: {exc}")
        try:
            comp.ResetSpawner(True)
        except TypeError:
            try:
                comp.ResetSpawner()
            except Exception as exc:
                _log_warn(f"ResetSpawner failed on {comp}: {exc}")
                continue
        except Exception as exc:
            _log_warn(f"ResetSpawner failed on {comp}: {exc}")
            continue

        actors = [a for a in _alive_actors_for_spawner_component(comp) if str(a) not in before] or _alive_actors_for_spawner_component(comp)
        target_transform = _spawn_transform_for_index(pawn, index=idx, count=max(1, int(count)), distance=distance, spacing=spacing, z_offset=0.0, scale=1.0)
        loc = target_transform.Translation
        try:
            rot = pawn.K2_GetActorRotation()
        except Exception:
            rot = None
        for actor in actors:
            if rot is not None:
                moved = _try_teleport_actor(actor, loc, rot)
            else:
                moved = False
            try:
                actor_loc = actor.K2_GetActorLocation()
            except Exception:
                actor_loc = None
            try:
                scripts = len(actor.ScriptData.Instances)
            except Exception:
                scripts = -1
            _SPAWNED.append(DeployedActor(label=name, source=sp, actor=actor, actor_key=_actor_key(actor), class_name=_class_name(actor)))
            _log_info(f"cached spawn {idx + 1}/{max(1, int(count))}: actor={actor} loc={actor_loc} moved={moved} scripts={scripts} spawner={sp}")
            if first_actor is None:
                first_actor = actor
            total_spawned += 1
    if total_spawned <= 0:
        _log_error(f"Cached actor def {cache_key!r} was found, but no alive actors were returned by spawners.")
        return None
    return first_actor


def _schedule_script_activation(
    actor: Any,
    name: str,
    *,
    source: Optional[Any],
    enable: Sequence[str],
    disable: Sequence[str],
    delay: float,
) -> None:
    key = _alias_key(name)
    final_enable = _unique_states(
        enable,
        _PRESET_ENABLE_STATES.get(key, ()),
        _source_schema_enable_states(source) if source is not None else (),
        _GENERIC_ENABLE_STATES,
    )
    final_disable = _unique_states(
        disable,
        _PRESET_DISABLE_STATES.get(key, ()),
        _GENERIC_DISABLE_STATES,
    )
    threading.Timer(
        max(0.0, float(delay)),
        lambda a=actor, fe=final_enable, fd=final_disable: _set_script_states(a, fe, fd, debug=True),
    ).start()


def _spawn_offline_deploy_preset(
    name: str,
    *,
    distance: float,
    count: int,
    spacing: float,
    coop_safe: bool = True,
) -> Optional[Any]:
    """Thin-air OakSpawner spawn using package loads — no live world template required.

    coop_safe=True (default) caps package probing so logo/BMS offline seeds do not
    freeze the game with hundreds of load_package guesses.
    """
    preset = _DEPLOY_OFFLINE_PRESETS.get(_alias_key(name))
    if preset is None:
        return None
    actor_def, loads, alt_defs = preset
    defs_to_try: List[str] = []
    seen_defs: set[str] = set()
    for candidate in (actor_def, *alt_defs):
        c = str(candidate or "").strip()
        if c and c not in seen_defs:
            seen_defs.add(c)
            defs_to_try.append(c)
    _log_info(
        f"No live template for {name!r}; trying offline deploy via {defs_to_try} "
        f"(packages={loads}, coop_safe={coop_safe})"
    )
    for candidate in defs_to_try:
        actor = _spawnai_fresh_spawner_direct(
            candidate,
            distance=distance,
            count=count,
            spacing=spacing,
            extra_loads=loads,
            coop_safe=bool(coop_safe),
            single_spawn=True,
        )
        if actor is not None:
            return actor
    return None


def _is_player_bank_spawn(name: str) -> bool:
    """True for any bank alias / IO_PlayerBank / PersistentLevel bank path.

    Must catch full world paths — exact entry_key matching missed those and fell
    through to find_all(Actor), which freezes with held loot shapes.
    """
    raw = (name or "").strip()
    if not raw:
        return False
    key = _alias_key(raw)
    if key in ("playerbank", "bank", "player_bank", "io_playerbank", "io_player_bank"):
        return True
    short = _io_short_token(raw)
    if short and _alias_key(short) in ("io_playerbank", "playerbank"):
        return True
    low = raw.lower().replace("-", "_").replace(" ", "")
    return "playerbank" in low or low.endswith(".io_playerbank")


def _find_io_playerbank_template_safe(
    class_override: Optional[str] = None,
) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    """find_object + session spawn only — never find_all (freezes with large held shapes)."""
    exact_cls, exact_src, exact_cn = _find_exact_loaded_io(
        "IO_PlayerBank", class_override=class_override
    )
    if exact_cls is not None and exact_src is not None:
        return exact_cls, exact_src, exact_cn
    for item in reversed(list(_SPAWNED)):
        label = str(getattr(item, "label", "") or "").lower()
        if "playerbank" not in label and "bank" not in label:
            continue
        actor = getattr(item, "actor", None)
        if actor is None:
            continue
        src = getattr(item, "source", None) or actor
        cls = _source_class(src, "IO_PlayerBank")
        if cls is None:
            cls = _source_class(actor, "IO_PlayerBank")
        if cls is not None:
            return cls, src, _class_name(actor) or "IO_PlayerBank"
    return None, None, None


def _spawn_deployed_actor(
    name: str,
    *,
    class_override: Optional[str],
    distance: float,
    z_offset: float,
    scale: float,
    delay: float,
    enable: Sequence[str],
    disable: Sequence[str],
    generated_only: bool,
    activate: bool,
    count: int = 1,
    spacing: float = 125.0,
) -> Optional[Any]:
    _, pawn, world, gs = _spawn_context()
    if pawn is None or world is None or gs is None:
        return None

    # Normalize loose enemy/boss names to the real Char_ actor-def from the dump,
    # but never override curated aliases (golden/bank/...) or offline presets.
    # Never rewrite full PersistentLevel / package paths (vending dual step 2).
    entry_key = _alias_key(name)
    name_looks_like_path = ("/" in name) or (":" in name) or ("persistentlevel." in name.lower())
    if (
        not name_looks_like_path
        and entry_key not in _ALIASES
        and entry_key not in _DEPLOY_OFFLINE_PRESETS
    ):
        resolved_name, name_suggestions = _resolve_actor_def_name(name)
        if resolved_name and resolved_name.strip().lower() != str(name).strip().lower():
            _log_info(
                f"oak_spawn resolved {name!r} -> {resolved_name!r} from game_data.json "
                f"(alternatives: {name_suggestions[:5]})"
            )
            name = resolved_name
            entry_key = _alias_key(name)

    # Large/arena bosses fail when squeezed in at the default 350uu; give them room
    # and clearance unless the caller explicitly set their own distance.
    if _is_large_boss_like(name):
        if abs(float(distance) - _DEFAULT_DISTANCE) < 0.5:
            distance = 900.0
        if spacing <= 130.0:
            spacing = 300.0
        if abs(float(z_offset) - _DEFAULT_Z_OFFSET) < 0.5:
            z_offset = 0.0
        _log_info(f"oak_spawn treating {name!r} as a large boss: distance={distance:g} spacing={spacing:g} z_offset={z_offset:g}")

    cache_key = _alias_key(name)
    # IO / PersistentLevel machines must duplicate the live template. The actor-def
    # cache path goes through OakSpawner and often returns blank shells (scripts=0).
    skip_actor_def_cache = bool(
        name_looks_like_path
        or _looks_like_io_name(name)
        or (_alias_key(name) in _VENDING_LIVE_ALIASES)
    )
    if (not skip_actor_def_cache) and _ACTOR_DEF_CACHE.get(cache_key):
        cached_actor = _spawn_cached_actor_def(
            name,
            distance=distance,
            count=count,
            spacing=spacing,
        )
        if cached_actor is not None:
            _log_info(f"Spawned {name!r} from session actor-def cache (no live template needed).")
            if activate:
                _schedule_script_activation(
                    cached_actor,
                    name,
                    source=None,
                    enable=enable,
                    disable=disable,
                    delay=delay,
                )
            return cached_actor

    # Player bank: prefer a live PersistentLevel.IO_PlayerBank template (unlocked)
    # over Script_PlayerBank offline deploy (often Locked).
    # Match ANY bank-shaped name (full PersistentLevel paths included) — never
    # fall through to _find_template / find_all(Actor).
    if _is_player_bank_spawn(name):
        bank_cls, bank_src, bank_cn = _find_io_playerbank_template_safe(class_override)
        if bank_cls is not None and bank_src is not None:
            _log_info(f"Using live IO_PlayerBank template for {name!r}: {bank_src}")
            _cache_actor_def("IO_PlayerBank", bank_src)
            total = max(1, int(count))
            first_actor: Optional[Any] = None
            for idx in range(total):
                transform = _spawn_transform_for_index(
                    pawn,
                    index=idx,
                    count=total,
                    distance=distance,
                    spacing=spacing,
                    z_offset=z_offset,
                    scale=scale,
                )
                actor = _spawn_actor_deferred(
                    gs,
                    world,
                    bank_cls,
                    transform,
                    class_name=bank_cn,
                    source=bank_src,
                    collision_handling=1,
                )
                if actor is None:
                    continue
                _SPAWNED.append(
                    DeployedActor(
                        label="IO_PlayerBank",
                        source=bank_src,
                        actor=actor,
                        actor_key=_actor_key(actor),
                        class_name=_class_name(actor),
                    )
                )
                if first_actor is None:
                    first_actor = actor
            if first_actor is not None:
                if activate:
                    _schedule_script_activation(
                        first_actor,
                        "playerbank",
                        source=bank_src,
                        enable=enable,
                        disable=disable,
                        delay=delay,
                    )
                return first_actor
        offline_bank = _spawn_offline_deploy_preset(
            name,
            distance=distance,
            count=count,
            spacing=spacing,
            coop_safe=True,
        )
        if offline_bank is not None:
            _log_info(f"Spawned IO_PlayerBank via offline preset for alias {name!r}")
            if activate:
                _schedule_script_activation(
                    offline_bank,
                    "playerbank",
                    source=None,
                    enable=enable,
                    disable=disable,
                    delay=delay,
                )
            return offline_bank
        direct_bank = _spawnai_fresh_spawner_direct(
            "IO_PlayerBank",
            distance=distance,
            count=count,
            spacing=spacing,
            extra_loads=(
                "/Game/InteractiveObjects/GameSystemMachines/PlayerBank/Script_PlayerBank",
            ),
            coop_safe=True,
            single_spawn=True,
        )
        if direct_bank is not None:
            _log_info(f"Spawned IO_PlayerBank via thin-air for alias {name!r}")
            if activate:
                _schedule_script_activation(
                    direct_bank,
                    "playerbank",
                    source=None,
                    enable=enable,
                    disable=disable,
                    delay=delay,
                )
            return direct_bank
        # Never fall through to _find_template — that find_all(Actor) freezes with held shapes.
        _log_error(
            f"IO_PlayerBank spawn failed for {name!r} without world scan "
            "(no live template / offline / thin-air). Visit a bank once or retry later."
        )
        return None

    # World-placed OakVendingMachine shortcut (scripts=0 risk). Skip when the
    # caller asks for OakInteractiveObject / PersistentLevel dual (ASD-shaped).
    override_low = (class_override or "").strip().lower()
    skip_live_vending = name_looks_like_path or override_low in (
        "oakinteractiveobject",
        "interactiveobject",
    )
    if not skip_live_vending and _alias_key(name) in _VENDING_LIVE_ALIASES:
        return _spawn_live_oak_vending_machine(
            name,
            class_override=class_override,
            distance=distance,
            z_offset=z_offset,
            scale=scale,
            delay=delay,
            enable=enable,
            disable=disable,
            activate=activate,
            count=count,
            spacing=spacing,
            pawn=pawn,
            world=world,
            gs=gs,
        )

    cls, source, class_name = _find_template(name, class_override, generated_only=generated_only)
    if cls is None or source is None:
        offline_actor = _spawn_offline_deploy_preset(
            name,
            distance=distance,
            count=count,
            spacing=spacing,
        )
        if offline_actor is not None:
            if activate:
                _schedule_script_activation(
                    offline_actor,
                    name,
                    source=None,
                    enable=enable,
                    disable=disable,
                    delay=delay,
                )
            return offline_actor

        # Universal AI thin-air fallback: any Char_ enemy/boss that has no live
        # template nearby and no offline preset still gets the direct OakSpawner
        # path. This is what makes oak_spawn <boss> work anywhere instead of only
        # when the boss happens to be streamed in near the player.
        if _looks_like_actor_def(name):
            direct_actor = _spawnai_fresh_spawner_direct(
                name,
                distance=distance,
                count=count,
                spacing=spacing,
            )
            if direct_actor is not None:
                _log_info(f"Spawned {name!r} via universal AI thin-air fallback (no live template needed).")
                if activate:
                    _schedule_script_activation(
                        direct_actor,
                        name,
                        source=None,
                        enable=enable,
                        disable=disable,
                        delay=delay,
                    )
                return direct_actor

        generic_source = _find_generic_skeletal_source(name, generated_only=generated_only)
        if generic_source is not None:
            return _spawn_generic_skeletal_duplicate(
                name,
                source=generic_source,
                distance=distance,
                z_offset=z_offset,
                scale=scale,
                count=count,
                spacing=spacing,
            )
        _log_error(
            f"{name!r}: no live template in loaded world cells, no session cache, and offline deploy failed. "
            f"Visit a {name} once and run **oak_cache {name}**, or move near a real instance and retry."
        )
        return None

    _cache_actor_def(name, source)

    # If the matched source is not a deployable/OakCharacter-style actor but does
    # have a skeletal mesh, use ADA's generic SkeletalMeshActor duplicate path.
    if _actor_mesh(source) is not None and _mesh_asset_for_kind(_actor_mesh(source)) is not None:
        low_class = str(class_name or _class_name(source)).lower()
        if "oakweapon" in low_class or "skeletal" in str(source).lower():
            return _spawn_generic_skeletal_duplicate(
                name,
                source=source,
                distance=distance,
                z_offset=z_offset,
                scale=scale,
                count=count,
                spacing=spacing,
            )

    total = max(1, int(count))
    first_actor: Optional[Any] = None
    spawned = 0
    for idx in range(total):
        transform = _spawn_transform_for_index(
            pawn,
            index=idx,
            count=total,
            distance=distance,
            spacing=spacing,
            z_offset=z_offset,
            scale=scale,
        )
        actor = _spawn_actor_deferred(gs, world, cls, transform, class_name=class_name, source=source, collision_handling=1)
        if actor is None:
            continue

        _SPAWNED.append(DeployedActor(label=name, source=source, actor=actor, actor_key=_actor_key(actor), class_name=_class_name(actor)))
        _log_info(f"spawned {idx + 1}/{total} name={name!r} class={class_name} actor={actor} source={source}")
        if first_actor is None:
            first_actor = actor
        spawned += 1

        if activate:
            final_enable = _unique_states(enable, _PRESET_ENABLE_STATES.get(cache_key, ()), _source_schema_enable_states(source), _GENERIC_ENABLE_STATES)
            final_disable = _unique_states(disable, _PRESET_DISABLE_STATES.get(cache_key, ()), _GENERIC_DISABLE_STATES)
            threading.Timer(
                max(0.0, float(delay)),
                lambda actor=actor: _set_script_states(actor, final_enable, final_disable, debug=True),
            ).start()

    if spawned <= 0:
        _log_error(f"{name}: no actors spawned.")
        return None
    return first_actor


def _spawn_from_args(args: argparse.Namespace, name: Optional[str] = None) -> None:
    target = name or str(getattr(args, "name", "") or "").strip()
    if not target:
        _log_error("Usage: oak_spawn <name> [--class ClassName]")
        return
    actor = _spawn_deployed_actor(
        target,
        class_override=getattr(args, "class_name", None),
        distance=float(getattr(args, "distance", _DEFAULT_DISTANCE)),
        z_offset=float(getattr(args, "z_offset", _DEFAULT_Z_OFFSET)),
        scale=float(getattr(args, "scale", _DEFAULT_SCALE)),
        delay=float(getattr(args, "delay", _DEFAULT_DELAY)),
        enable=_split_states(getattr(args, "enable", None), _DEFAULT_ACTIVATE_ENABLE),
        disable=_split_states(getattr(args, "disable", None), _DEFAULT_ACTIVATE_DISABLE),
        generated_only=not bool(getattr(args, "include_non_generated", False)),
        activate=not bool(getattr(args, "no_activate", False)),
        count=int(getattr(args, "count", 1)),
        spacing=float(getattr(args, "spacing", 125.0)),
    )
    if actor is not None:
        _log_info(f"Deployment complete: {actor}")


# 5x7 pixel font for barrel-logo spawning.  # marks spawn cells.
_FONT_5X7: Dict[str, Tuple[str, ...]] = {
    "A": (" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "B": ("#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "),
    "C": (" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"),
    "D": ("#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "),
    "E": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"),
    "F": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "),
    "G": (" ####", "#    ", "#    ", "#  ##", "#   #", "#   #", " ####"),
    "H": ("#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "I": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"),
    "J": ("#####", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "),
    "K": ("#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"),
    "M": ("#   #", "## ##", "# # #", "#   #", "#   #", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    "Q": (" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"),
    "R": ("#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"),
    "S": (" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": ("#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "V": ("#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "),
    "W": ("#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"),
    "X": ("#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"),
    "Y": ("#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "),
    "Z": ("#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"),
    "0": (" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "),
    "1": ("  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"),
    "2": (" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"),
    "3": ("#### ", "    #", "    #", " ### ", "    #", "    #", "#### "),
    "4": ("#   #", "#   #", "#   #", "#####", "    #", "    #", "    #"),
    "5": ("#####", "#    ", "#    ", "#### ", "    #", "    #", "#### "),
    "6": (" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "),
    "7": ("#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "),
    "8": (" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "),
    "9": (" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "),
    " ": ("   ", "   ", "   ", "   ", "   ", "   ", "   "),
}
_LOGO_TEXT = "MODS|ARE|FREE"
_LOGO_ROW1_DEFAULT = "MODS"
_LOGO_ROW2_DEFAULT = "ARE"
_LOGO_ROW3_DEFAULT = "FREE"
_LOGO_DISTANCE_DEFAULT = 1400.0
_LOGO_ACTOR_DEFAULT = "electisafe"
_LOGO_ROW_CHOICES: Tuple[str, ...] = (
    "", "MODS", "ARE", "FREE", "MODS ARE FREE", "JOIN", "GZO", "DISCORD",
    "SCOOTERSGARAGE", "ECHO4", "WELCOME",
    "WE HAVE BEEN", "TRYING TO REACH YOU", "ABOUT YOUR CARS EXTENDED WARRENTY",
    "ABOUT YOUR CARS EXTENDED WARRANTY", "SUBSCRIBE", "LIKE AND FOLLOW",
)
_LOGO_ROW1_OPTION = _make_text_option(
    "oak_logo_row_1",
    "Logo Text Row 1",
    _LOGO_ROW1_DEFAULT,
    "Select this number, then TYPE your text and press Enter. Or console: oak_logo_set row1 YOUR TEXT",
)
_LOGO_ROW2_OPTION = _make_text_option(
    "oak_logo_row_2",
    "Logo Text Row 2",
    _LOGO_ROW2_DEFAULT,
    "Select this number, then TYPE your text and press Enter. Or console: oak_logo_set row2 YOUR TEXT",
)
_LOGO_ROW3_OPTION = _make_text_option(
    "oak_logo_row_3",
    "Logo Text Row 3",
    _LOGO_ROW3_DEFAULT,
    "Select this number, then TYPE your text and press Enter. Or console: oak_logo_set row3 YOUR TEXT",
)
_LOGO_DISTANCE_OPTION = _make_float_option(
    "oak_logo_distance",
    "Barrel Logo Distance",
    _LOGO_DISTANCE_DEFAULT,
    "Permanent forward distance used by the Oak Spawn Barrel Logo keybind and by oak_barrellogo when --distance is omitted.",
    minimum=100.0,
    maximum=5000.0,
    increment=50.0,
)
_LOGO_ACTOR_OPTION = _make_text_option(
    "oak_logo_actor",
    "Logo Actor Override",
    _LOGO_ACTOR_DEFAULT,
    "Select, type keyword (barrel / goldenchest / firmware / bank), Enter. Or: oak_logo_set actor goldenchest",
)
_LOGO_OPTIONS = [
    opt for opt in (
        _LOGO_ROW1_OPTION, _LOGO_ROW2_OPTION, _LOGO_ROW3_OPTION,
        _LOGO_DISTANCE_OPTION, _LOGO_ACTOR_OPTION,
    ) if opt is not None
]
_LOGO_COLORS: Tuple[Tuple[float, float, float, float], ...] = (
    (0.0, 0.75, 1.0, 1.0),   # cyan/blue
    (1.0, 0.0, 1.0, 1.0),    # magenta
    (1.0, 0.16, 0.05, 1.0),  # red/orange
    (1.0, 0.55, 0.0, 1.0),   # orange
)


def _vector(x: float, y: float, z: float) -> Any:
    return make_struct("Vector", X=float(x), Y=float(y), Z=float(z))


def _transform_at(x: float, y: float, z: float, scale: float) -> Any:
    return make_struct(
        "Transform",
        Rotation=make_struct("Quat", X=0.0, Y=0.0, Z=0.0, W=1.0),
        Translation=_vector(x, y, z),
        Scale3D=_vector(scale, scale, scale),
    )


def _text_pixels(text: str) -> Tuple[List[Tuple[int, int, int]], int, int]:
    pixels: List[Tuple[int, int, int]] = []
    cursor = 0
    height = 7
    for char_index, char in enumerate(text.upper()):
        glyph = _FONT_5X7.get(char, _FONT_5X7[" "])
        width = max(len(row) for row in glyph)
        if char == " ":
            cursor += width + 2
            continue
        for y, row in enumerate(glyph):
            for x, cell in enumerate(row):
                if cell != " ":
                    pixels.append((cursor + x, y, char_index))
        cursor += width + 1
    return pixels, max(0, cursor - 1), height


def _logo_text_from_options() -> str:
    row1 = _option_text_value(_LOGO_ROW1_OPTION, _LOGO_ROW1_DEFAULT)
    row2 = _option_text_value(_LOGO_ROW2_OPTION, _LOGO_ROW2_DEFAULT)
    row3 = _option_text_value(_LOGO_ROW3_OPTION, _LOGO_ROW3_DEFAULT)
    rows = [row.strip() for row in (row1, row2, row3) if row and row.strip()]
    return "|".join(rows) if rows else _LOGO_TEXT


def _logo_distance_from_options() -> float:
    return _option_float_value(_LOGO_DISTANCE_OPTION, _LOGO_DISTANCE_DEFAULT)


def _logo_actor_from_options() -> str:
    actor = _option_text_value(_LOGO_ACTOR_OPTION, _LOGO_ACTOR_DEFAULT)
    return actor.strip() or _LOGO_ACTOR_DEFAULT


def _stacked_text_pixels(text: str) -> Tuple[List[Tuple[int, int, int]], int, int]:
    # Render stacked rows, centered to the widest row.  If the user explicitly
    # separates lines with |, honor that.  Also force the default phrase into
    # three rows even if a saved command/config passes it as spaces.
    normalized = (text or "").strip()
    if normalized.upper() == "JOIN GZO DISCORD":
        normalized = "JOIN|GZO|DISCORD"
    if normalized.upper() in ("MODS ARE FREE", "MODSAREFREE"):
        normalized = "MODS|ARE|FREE"
    raw_lines = [part.strip() for part in normalized.split("|") if part.strip()]
    lines = raw_lines if raw_lines else [part.strip() for part in normalized.split() if part.strip()]
    if not lines:
        lines = [text.strip() or _LOGO_TEXT]

    rendered: List[Tuple[List[Tuple[int, int, int]], int, int, int]] = []
    max_width = 0
    line_gap = 2
    total_height = 0
    char_base = 0
    for line in lines:
        line_pixels, width, height = _text_pixels(line)
        rendered.append((line_pixels, width, height, char_base))
        max_width = max(max_width, width)
        total_height += height
        char_base += len(line) + 1
    total_height += max(0, len(lines) - 1) * line_gap

    pixels: List[Tuple[int, int, int]] = []
    y_offset = 0
    for line_pixels, width, height, char_base in rendered:
        x_offset = int(round((max_width - width) / 2.0))
        for x, y, char_index in line_pixels:
            pixels.append((x + x_offset, y + y_offset, char_index + char_base))
        y_offset += height + line_gap
    return pixels, max_width, total_height


def _first_component(actor: Any) -> Optional[Any]:
    for attr in ("Mesh", "StaticMeshComponent", "SkeletalMeshComponent", "BankMesh_SK", "RootComponent"):
        try:
            comp = getattr(actor, attr, None)
        except Exception:
            comp = None
        if comp is not None:
            return comp
    for class_name in ("PrimitiveComponent", "StaticMeshComponent", "SkeletalMeshComponent"):
        try:
            cls = find_class(class_name)
            comp = actor.GetComponentByClass(cls) if hasattr(actor, "GetComponentByClass") else None
        except Exception:
            comp = None
        if comp is not None:
            return comp
    return None


def _freeze_visual_actor(actor: Any) -> None:
    try:
        actor.SetActorEnableCollision(False)
    except Exception:
        pass
    try:
        actor.SetActorTickEnabled(False)
    except Exception:
        pass
    for comp in (getattr(actor, "RootComponent", None), _first_component(actor)):
        if comp is None:
            continue
        for name, args in (
            ("SetCollisionEnabled", (0,)),
            ("SetGenerateOverlapEvents", (False,)),
            ("SetSimulatePhysics", (False,)),
            ("SetEnableGravity", (False,)),
            ("SetComponentTickEnabled", (False,)),
            ("SetVisibility", (True, True)),
            ("SetHiddenInGame", (False, True)),
        ):
            try:
                getattr(comp, name)(*args)
            except Exception:
                pass


def _prepare_logo_barrel(actor: Any) -> None:
    """Keep logo barrels visible/floating, but still damageable/explosive.

    The old logo path used _freeze_visual_actor(), which disabled actor collision,
    component collision, overlap events, and tick.  That made the barrel pixels
    nice and static but also stopped explosive barrel gameplay logic from being
    hit/damaged normally.  This path keeps gameplay collision/tick alive while
    only trying to stop physics/gravity drift.
    """
    try:
        actor.SetActorHiddenInGame(False)
    except Exception:
        pass
    try:
        actor.SetActorEnableCollision(True)
    except Exception:
        pass
    try:
        actor.SetActorTickEnabled(True)
    except Exception:
        pass
    seen: set[str] = set()
    comps: List[Any] = []
    for comp in (getattr(actor, "RootComponent", None), _first_component(actor)):
        if comp is None:
            continue
        key = str(comp)
        if key in seen:
            continue
        seen.add(key)
        comps.append(comp)
    for comp in comps:
        for name, args in (
            ("SetHiddenInGame", (False, True)),
            ("SetVisibility", (True, True)),
            ("SetComponentTickEnabled", (True,)),
            ("SetCollisionEnabled", (1,)),
            ("SetGenerateOverlapEvents", (True,)),
        ):
            try:
                getattr(comp, name)(*args)
            except Exception:
                pass
        # Keep the sign suspended, but don't disable collision/tick.  Some
        # components don't expose these methods; failures are harmless.
        for name, args in (
            ("SetEnableGravity", (False,)),
            ("SetSimulatePhysics", (False,)),
        ):
            try:
                getattr(comp, name)(*args)
            except Exception:
                pass


def _tint_actor(actor: Any, rgba: Tuple[float, float, float, float]) -> None:
    comp = _first_component(actor)
    if comp is None:
        return
    color = make_struct("LinearColor", R=rgba[0], G=rgba[1], B=rgba[2], A=rgba[3])
    # Try material parameter paths common to UE components.  Failures are fine;
    # some barrel materials will ignore tint and keep their native color.
    for fn_name in ("SetVectorParameterValueOnMaterials",):
        fn = getattr(comp, fn_name, None)
        if not callable(fn):
            continue
        for param in ("Color", "BaseColor", "Tint", "EmissiveColor", "GlowColor"):
            try:
                fn(param, color)
            except Exception:
                pass
    for idx in range(4):
        try:
            mid = comp.CreateAndSetMaterialInstanceDynamic(idx)
        except Exception:
            mid = None
        if mid is None:
            continue
        for param in ("Color", "BaseColor", "Tint", "EmissiveColor", "GlowColor"):
            try:
                mid.SetVectorParameterValue(param, color)
            except Exception:
                pass


# World-text spawn job: heavy props paced across ticks. BMS seeds are async —
# we must WAIT until the seed actor exists before cloning letter props.
_LOGO_JOB: Optional[Dict[str, Any]] = None
_LOGO_PENDING: Optional[Dict[str, Any]] = None
# NPC / TargetDummy letter props use CharacterMovement and fall unless pinned.
_LOGO_PINNED: List[Dict[str, Any]] = []
_LOGO_PIN_TICK: int = 0
_LOGO_PER_TICK_BARREL = 24
_LOGO_PER_TICK_HEAVY = 8
_LOGO_PER_TICK_COOP = 3
# Default text MODS|ARE|FREE is ~188 pixels; keep headroom so goldenchest/IO glyphs stay readable.
_LOGO_DEFAULT_CAP_HEAVY = 256
_LOGO_SEED_WAIT_S = 20.0


def _logo_actor_live(actor: Any) -> bool:
    if actor is None:
        return False
    try:
        is_valid = getattr(actor, "IsValid", None)
        if callable(is_valid) and not is_valid():
            return False
        loc = actor.K2_GetActorLocation()
        return loc is not None
    except Exception:
        return False


def _logo_coop_heavy() -> bool:
    """True when co-op shape guest sync / join quiet should not compete with world-text spawns."""
    try:
        from Squ1ggsBoostingTools import loot_shapes as ls

        now = time.monotonic()
        if bool(getattr(ls, "_guest_sync_active", False)):
            return True
        quiet_fn = getattr(ls, "_in_join_quiet", None)
        if callable(quiet_fn) and quiet_fn(now):
            return True
        pins = list(getattr(ls, "_pinned_slots", []) or [])
        if pins and any(row.get("hold") for row in pins):
            pending = sum(1 for row in pins if not row.get("guest_ok"))
            if pending > 0:
                return True
    except Exception:
        pass
    return False


def _logo_per_tick(is_barrel: bool) -> int:
    if _logo_coop_heavy():
        return _LOGO_PER_TICK_COOP
    return _LOGO_PER_TICK_BARREL if is_barrel else _LOGO_PER_TICK_HEAVY


def _logo_is_characterish(*, actor: Any = None, class_name: str = "", barrel_name: str = "") -> bool:
    blob = f"{class_name} {barrel_name} {actor}".lower()
    return any(
        token in blob
        for token in (
            "oakcharacter",
            "oakpawn",
            "char_",
            "targetdummy",
            "pawn'",
            "character'",
        )
    )


def _logo_movement_components(actor: Any) -> List[Any]:
    out: List[Any] = []
    seen: set[str] = set()
    for attr in (
        "CharacterMovement",
        "OakCharacterMovement",
        "GbxCharacterMovement",
        "MovementComponent",
        "PawnMovement",
        "Movement",
    ):
        comp = getattr(actor, attr, None)
        if comp is None:
            continue
        key = str(comp)
        if key in seen:
            continue
        seen.add(key)
        out.append(comp)
    for meth in ("GetMovementComponent", "GetCharacterMovement"):
        fn = getattr(actor, meth, None)
        if not callable(fn):
            continue
        try:
            comp = fn()
        except Exception:
            continue
        if comp is None:
            continue
        key = str(comp)
        if key in seen:
            continue
        seen.add(key)
        out.append(comp)
    return out


def _prepare_logo_character(actor: Any) -> None:
    """Keep NPC / TargetDummy letter props suspended (dump: OakCharacter falls via CMC)."""
    _freeze_visual_actor(actor)
    try:
        actor.SetActorEnableCollision(False)
    except Exception:
        pass
    try:
        setattr(actor, "bCanBeDamaged", False)
    except Exception:
        pass
    try:
        setattr(actor, "bCheatFlying", True)
    except Exception:
        pass
    for comp in _logo_movement_components(actor):
        for attr, value in (
            ("GravityScale", 0.0),
            ("bCheatFlying", True),
            ("MaxWalkSpeed", 0.0),
            ("MaxFlySpeed", 0.0),
            ("MaxAcceleration", 0.0),
            ("BrakingDecelerationWalking", 0.0),
            ("BrakingDecelerationFlying", 0.0),
            ("AirControl", 0.0),
        ):
            try:
                setattr(comp, attr, value)
            except Exception:
                pass
        for meth_name, args in (
            ("StopMovementImmediately", ()),
            ("DisableMovement", ()),
            ("SetMovementMode", (0, 0)),  # MOVE_None
        ):
            meth = getattr(comp, meth_name, None)
            if not callable(meth):
                continue
            try:
                meth(*args)
            except TypeError:
                try:
                    meth(args[0]) if args else meth()
                except Exception:
                    pass
            except Exception:
                pass
        try:
            zero = make_struct("Vector", X=0.0, Y=0.0, Z=0.0)
            setattr(comp, "Velocity", zero)
        except Exception:
            pass
    # Stop AI so they don't walk/ragdoll out of the glyph.
    for getter in ("GetController", "GetAIController"):
        fn = getattr(actor, getter, None)
        if not callable(fn):
            continue
        try:
            ctrl = fn()
        except Exception:
            ctrl = None
        if ctrl is None:
            continue
        for meth_name in ("StopMovement", "PauseLogic", "BrainComponent"):
            try:
                if meth_name == "BrainComponent":
                    brain = getattr(ctrl, "BrainComponent", None)
                    stop = getattr(brain, "StopLogic", None) if brain is not None else None
                    if callable(stop):
                        stop("logo pin")
                else:
                    meth = getattr(ctrl, meth_name, None)
                    if callable(meth):
                        meth()
            except Exception:
                pass


def _logo_pin_actor(actor: Any, transform: Any = None) -> None:
    if actor is None:
        return
    loc = None
    rot = None
    try:
        loc = actor.K2_GetActorLocation()
        rot = actor.K2_GetActorRotation()
    except Exception:
        pass
    if loc is None and transform is not None:
        try:
            loc = getattr(transform, "Translation", None) or getattr(transform, "Location", None)
            rot = getattr(transform, "Rotation", None)
        except Exception:
            pass
    if loc is None:
        return
    key = str(actor)
    for row in _LOGO_PINNED:
        if str(row.get("actor")) == key:
            row["loc"] = loc
            if rot is not None:
                row["rot"] = rot
            return
    _LOGO_PINNED.append({"actor": actor, "loc": loc, "rot": rot})


def clear_logo_pins() -> None:
    _LOGO_PINNED.clear()


def _logo_maintain_pins() -> None:
    """Re-freeze / re-teleport character letter props that gravity pulled down."""
    global _LOGO_PIN_TICK
    if not _LOGO_PINNED:
        return
    if _logo_coop_heavy():
        return
    _LOGO_PIN_TICK = int(_LOGO_PIN_TICK) + 1
    if (_LOGO_PIN_TICK % 4) != 0:
        return
    reapply_freeze = (_LOGO_PIN_TICK % 32) == 0
    alive: List[Dict[str, Any]] = []
    budget = 24
    touched = 0
    for row in list(_LOGO_PINNED):
        if touched >= budget:
            alive.append(row)
            continue
        actor = row.get("actor")
        loc = row.get("loc")
        if actor is None or loc is None or not _logo_actor_live(actor):
            continue
        try:
            cur = actor.K2_GetActorLocation()
            dx = float(cur.X) - float(loc.X)
            dy = float(cur.Y) - float(loc.Y)
            dz = float(cur.Z) - float(loc.Z)
            drifted = (dx * dx + dy * dy + dz * dz) > 25.0  # >5uu
        except Exception:
            continue
        if drifted:
            rot = row.get("rot")
            try:
                if rot is not None and hasattr(actor, "K2_TeleportTo"):
                    actor.K2_TeleportTo(loc, rot)
                else:
                    actor.K2_SetActorLocation(loc, False, None, True)
            except Exception:
                pass
        if drifted or reapply_freeze:
            try:
                _prepare_logo_character(actor)
            except Exception:
                pass
        touched += 1
        alive.append(row)
    _LOGO_PINNED[:] = alive


def _logo_nearest_actor(actors: Sequence[Any]) -> Optional[Any]:
    """Pick the actor closest to the local pawn (same idea as golden-chest keybinds)."""
    if not actors:
        return None
    _, pawn, _world, _gs = _spawn_context()
    if pawn is None:
        return actors[0]
    try:
        loc = pawn.K2_GetActorLocation()
        px, py, pz = float(loc.X), float(loc.Y), float(loc.Z)
    except Exception:
        return actors[0]
    best = None
    best_d = 0.0
    for actor in actors:
        try:
            al = actor.K2_GetActorLocation()
            dx = float(al.X) - px
            dy = float(al.Y) - py
            dz = float(al.Z) - pz
            dist = dx * dx + dy * dy + dz * dz
        except Exception:
            continue
        if best is None or dist < best_d:
            best = actor
            best_d = dist
    return best if best is not None else actors[0]


def _logo_needles_for(name: str) -> Tuple[str, ...]:
    raw = (name or "").strip()
    key = _alias_key(raw)
    canonical = _LOGO_ACTOR_CANONICAL.get(key, raw)
    needles: List[str] = []
    for token in (canonical, raw, key):
        t = str(token or "").strip()
        if t and t not in needles:
            needles.append(t)
        short = _io_short_token(t) if t else ""
        if short and short not in needles:
            needles.append(short)
    _, alias_needles = _default_class_and_needles(raw)
    for n in alias_needles:
        if n and n not in needles:
            needles.append(n)
    return tuple(needles)


def _logo_find_by_needles(needles: Sequence[str]) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    """Find a live logo template by substring across safe classes (post-seed detect)."""
    lowered = [n.lower() for n in needles if n]
    if not lowered:
        return None, None, None
    classes = [
        "OakVendingMachine",
        "OakLostLootMachine",
        "LootableObject",
        "OakInteractiveObject",
    ]
    # NPC / Char_* world-text seeds land as characters, not interactive objects.
    if any(n.startswith("char_") or "char_npc" in n for n in lowered):
        classes = ["OakCharacter", "OakPawn", "Pawn"] + classes
    for class_name in classes:
        try:
            found = list(find_all(class_name, False))
        except TypeError:
            try:
                found = list(find_all(class_name))
            except Exception:
                continue
        except Exception:
            continue
        matches = []
        for obj in found:
            text = str(obj).lower()
            if "default__" in text or "/script/" in text:
                continue
            if any(n in text for n in lowered):
                matches.append(obj)
        if not matches:
            continue
        source = _logo_nearest_actor(matches)
        if source is None:
            continue
        cls = _source_class(source, class_name)
        if cls is not None:
            _log_info(f"Logo template via needle scan {class_name!r}: {source}")
            return cls, source, class_name
    return None, None, None


def _logo_find_from_spawned(needles: Sequence[str]) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    lowered = [n.lower() for n in needles if n]
    for row in reversed(list(_SPAWNED)[-80:]):
        actor = getattr(row, "actor", None)
        if actor is None:
            continue
        blob = f"{getattr(row, 'label', '')} {actor}".lower()
        if any(n in blob for n in lowered):
            cls = _source_class(actor)
            if cls is not None:
                _log_info(f"Logo template via _SPAWNED: {actor}")
                return cls, actor, _class_name(actor)
    return None, None, None


def _logo_resolve_template(
    name: str,
    *,
    deep: bool = False,
) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    """Resolve used while waiting for BMS seed detect."""
    cls, source, class_name = _logo_find_live_template(name)
    if cls is not None and source is not None:
        return cls, source, class_name
    needles = _logo_needles_for(name)
    cls, source, class_name = _logo_find_from_spawned(needles)
    if cls is not None and source is not None:
        return cls, source, class_name
    if deep:
        return _logo_find_by_needles(needles)
    return None, None, None


def _logo_find_live_template(name: str) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    """Live template lookup for world text (same classes BMS / golden-chest keybinds use)."""
    raw = (name or "").strip()
    if not raw:
        return None, None, None
    key = _alias_key(raw)
    canonical = _LOGO_ACTOR_CANONICAL.get(key, raw)
    tokens: List[str] = []
    for token in (canonical, raw):
        t = str(token or "").strip()
        if t and t not in tokens:
            tokens.append(t)

    # PersistentLevel find_object (World_P fixed path).
    for token in tokens:
        if _looks_like_io_name(token) or token.lower().startswith("lootable_"):
            cls, source, class_name = _find_exact_loaded_io(token)
            if cls is not None and source is not None:
                _log_info(f"Logo template via find_object {token!r}: {source}")
                return cls, source, class_name

    # Lootables (golden chest / moneybox / electisafe / …).
    loot_keys = (
        "goldenchest", "golden", "golden_chest", "moneybox", "electisafe", "ammogeyser",
        "breakable_chest",
    )
    if key in loot_keys or canonical.lower().startswith(("lootable_", "io_lootable", "io_electi", "io_ammo")):
        needles = _logo_needles_for(raw)
        lowered = [n.lower() for n in needles]
        try:
            chests = [
                o
                for o in find_all("LootableObject")
                if any(n in str(o).lower() for n in lowered)
            ]
        except Exception as exc:
            _log_warn(f"Logo LootableObject scan failed: {exc}")
            chests = []
        source = _logo_nearest_actor(chests)
        if source is not None:
            cls = _source_class(source, "LootableObject")
            if cls is not None:
                _log_info(f"Logo lootable template: {source}")
                return cls, source, "LootableObject"

    # Barrel: narrow generated OakInteractiveObject scan only.
    if key in ("barrel", "barrels") or "barrel" in key:
        _, needles = _default_class_and_needles(raw if key in ("barrel", "barrels") else "barrel")
        matches = _candidate_sources("OakInteractiveObject", needles, generated_only=True)
        if not matches:
            matches = _candidate_sources("OakInteractiveObject", needles, generated_only=False)
        if matches:
            source = matches[0]
            cls = _source_class(source, "OakInteractiveObject")
            if cls is not None:
                _log_info(f"Logo barrel template: {source}")
                return cls, source, "OakInteractiveObject"

    # Vendors / lost loot (narrow classes only — never Actor; OakInteractiveObject
    # is scanned only on deep detect ticks to avoid hitching while waiting).
    for token in tokens:
        _, needles = _default_class_and_needles(token)
        if not needles:
            needles = (token,)
        for class_name in ("OakVendingMachine", "OakLostLootMachine"):
            matches = _candidate_sources(class_name, needles, generated_only=False)
            if not matches:
                continue
            source = _logo_nearest_actor(matches) or matches[0]
            cls = _source_class(source, class_name)
            if cls is not None:
                _log_info(f"Logo template via narrow {class_name!r}: {source}")
                return cls, source, class_name
    return None, None, None


def _logo_finish_job(job: Dict[str, Any]) -> None:
    _log_info(
        f"Barrel logo finished queued job actor={job.get('barrel_name')!r} "
        f"spawned={int(job.get('spawned') or 0)}"
    )


def cancel_logo_job() -> None:
    global _LOGO_JOB, _LOGO_PENDING
    _LOGO_PENDING = None
    job = _LOGO_JOB
    _LOGO_JOB = None
    if job:
        _logo_finish_job(job)


def _logo_tick_pending_seed() -> bool:
    """Wait for async BMS seed to exist, then start the letter-clone job."""
    global _LOGO_PENDING
    pending = _LOGO_PENDING
    if not pending:
        return False
    if time.monotonic() > float(pending.get("deadline") or 0.0):
        _log_error(
            f"Logo seed detect timed out for {pending.get('barrel_name')!r}. "
            "Only the single BMS seed (if any) remains — clones never started."
        )
        _LOGO_PENDING = None
        return True
    barrel_name = str(pending.get("barrel_name") or "")
    canonical = str(pending.get("canonical") or barrel_name)
    frames = int(pending.get("frames") or 0) + 1
    pending["frames"] = frames
    # Deep needle scan (includes OakInteractiveObject) every ~8 frames only.
    cls, source, class_name = _logo_resolve_template(
        canonical if frames % 4 == 0 else barrel_name,
        deep=(frames % 8 == 0),
    )
    if cls is None or source is None:
        return True  # still waiting
    transforms = list(pending.get("transforms") or [])
    is_barrel = bool(pending.get("is_barrel"))
    _LOGO_PENDING = None
    _log_info(f"Logo seed detected for {barrel_name!r}: {source} — starting {len(transforms)} clones")
    _logo_start_clone_job(
        barrel_name=barrel_name,
        cls=cls,
        source=source,
        class_name=class_name,
        transforms=transforms,
        is_barrel=is_barrel,
    )
    return True


def logo_tick() -> None:
    """Pace world-text prop spawns across frames (called from mobility background tick)."""
    global _LOGO_JOB
    if _logo_coop_heavy() and not _LOGO_JOB:
        return
    if _logo_tick_pending_seed():
        # If we just started a clone job, fall through and spawn the first batch now.
        pass
    job = _LOGO_JOB
    if job:
        pixels: List[Tuple[Any, ...]] = list(job.get("pixels") or [])
        if not pixels:
            _LOGO_JOB = None
            _logo_finish_job(job)
        else:
            _, _pawn, world, gs = _spawn_context()
            if world is not None and gs is not None:
                cls = job.get("cls")
                source = job.get("source")
                class_name = str(job.get("class_name") or "Actor")
                barrel_name = str(job.get("barrel_name") or "")
                is_character = _logo_is_characterish(
                    class_name=class_name, barrel_name=barrel_name
                )
                per_tick = max(1, int(job.get("per_tick") or _logo_per_tick(is_barrel)))
                if _logo_coop_heavy():
                    per_tick = min(per_tick, _LOGO_PER_TICK_COOP)
                batch = pixels[:per_tick]
                job["pixels"] = pixels[per_tick:]
                spawned = int(job.get("spawned") or 0)

                for item in batch:
                    try:
                        transform, char_index = item[0], int(item[1])
                    except Exception:
                        continue
                    actor = _spawn_actor_deferred(
                        gs,
                        world,
                        cls,
                        transform,
                        class_name=class_name,
                        source=source,
                        collision_handling=1,
                    )
                    if actor is None:
                        _log_warn("barrel logo paced spawn failed")
                        continue
                    if is_character or _logo_is_characterish(actor=actor, class_name=class_name):
                        _prepare_logo_character(actor)
                        _logo_pin_actor(actor, transform)
                    else:
                        _prepare_logo_barrel(actor)
                    _tint_actor(actor, _LOGO_COLORS[char_index % len(_LOGO_COLORS)])
                    # Golden-chest letter props need Idle/Unlocked script states or Open won't work.
                    if "golden" in _alias_key(barrel_name):
                        try:
                            _set_script_states(
                                actor,
                                _PRESET_ENABLE_STATES.get(
                                    "goldenchest", ("Idle", "Enabled", "Usable", "Unlocked")
                                ),
                                _PRESET_DISABLE_STATES.get(
                                    "goldenchest", ("Locked", "Blocked", "IsInUse")
                                ),
                                debug=False,
                            )
                        except Exception:
                            pass
                    _SPAWNED.append(
                        DeployedActor(
                            label="barrel_logo",
                            source=source,
                            actor=actor,
                            actor_key=_actor_key(actor),
                            class_name=_class_name(actor),
                        )
                    )
                    spawned += 1
                job["spawned"] = spawned
                if not job.get("pixels"):
                    _LOGO_JOB = None
                    _logo_finish_job(job)
    # Keep NPC / TargetDummy glyphs from falling after the queue finishes.
    _logo_maintain_pins()


def _logo_plan_transforms(
    *,
    pawn: Any,
    text: str,
    distance: float,
    height: float,
    spacing: float,
    scale: float,
    max_props: int,
    is_barrel: bool,
) -> List[Tuple[Any, int]]:
    loc = pawn.K2_GetActorLocation()
    fwd = pawn.GetActorForwardVector()
    rx, ry = -float(fwd.Y), float(fwd.X)
    mag = max((rx * rx + ry * ry) ** 0.5, 0.0001)
    rx, ry = rx / mag, ry / mag
    fx, fy = float(fwd.X), float(fwd.Y)

    pixels, width, rows = _stacked_text_pixels(text)
    cap = int(max_props or 0)
    if cap <= 0 and not is_barrel:
        cap = _LOGO_DEFAULT_CAP_HEAVY
    if cap > 0 and len(pixels) > cap:
        step = float(len(pixels)) / float(cap)
        pixels = [pixels[min(len(pixels) - 1, int(i * step))] for i in range(cap)]
        _log_info(f"Barrel logo thinned to {len(pixels)} props (max_props={cap})")

    center_x = (float(width) - 1.0) / 2.0
    center_y = (float(rows) - 1.0) / 2.0
    base_x = float(loc.X + fx * distance)
    base_y = float(loc.Y + fy * distance)
    base_z = float(loc.Z + height)

    transforms: List[Tuple[Any, int]] = []
    for x, y, char_index in pixels:
        px = base_x + rx * ((float(x) - center_x) * spacing)
        py = base_y + ry * ((float(x) - center_x) * spacing)
        pz = base_z - ((float(y) - center_y) * spacing)
        transforms.append((_transform_at(px, py, pz, scale), int(char_index)))
    return transforms


def _logo_start_clone_job(
    *,
    barrel_name: str,
    cls: Any,
    source: Any,
    class_name: Optional[str],
    transforms: Sequence[Tuple[Any, int]],
    is_barrel: bool,
) -> int:
    global _LOGO_JOB
    per_tick = _logo_per_tick(is_barrel)
    cancel_logo_job()
    _LOGO_JOB = {
        "barrel_name": barrel_name,
        "cls": cls,
        "source": source,
        "class_name": class_name or "Actor",
        "pixels": list(transforms),
        "per_tick": per_tick,
        "spawned": 0,
    }
    _log_info(
        f"Barrel logo queued {len(transforms)} props actor={barrel_name!r} "
        f"class={class_name} per_tick={per_tick} source={source}"
    )
    return len(transforms)


def _logo_queue_async_bms_seed_then_clone(
    *,
    barrel_name: str,
    text: str,
    distance: float,
    height: float,
    spacing: float,
    scale: float,
    max_props: int,
) -> int:
    """Seed ONE actor via deferred BMS spawn_actor_def, then wait+clone letters.

    Dump showed async seed returns before the actor exists; starting clones 3
    frames later left only the single seed. ``logo_tick`` now polls until detect.
    """
    global _LOGO_PENDING
    from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415

    key = _alias_key(barrel_name)
    canonical = _LOGO_ACTOR_CANONICAL.get(key, barrel_name)
    is_barrel = key in ("barrel", "barrels")
    _, pawn, _world, _gs = _spawn_context()
    if pawn is None:
        return 0
    transforms = _logo_plan_transforms(
        pawn=pawn,
        text=text,
        distance=distance,
        height=height,
        spacing=spacing,
        scale=scale,
        max_props=max_props,
        is_barrel=is_barrel,
    )
    if not transforms:
        return 0

    def _seed() -> Tuple[bool, str]:
        try:
            from Squ1ggsBoostingTools.embedded_bms.oak_spawn import spawn_actor_def  # noqa: PLC0415
        except Exception as exc:
            return False, f"BMS spawn unavailable: {exc}"
        ok, msg = spawn_actor_def(
            str(canonical),
            count=1,
            distance=160.0,
            spacing=50.0,
            fast_path=True,
            async_fire=True,
        )
        _log_info(f"Logo deferred BMS seed {canonical!r}: ok={ok} {msg}")
        return bool(ok), str(msg or "")

    def _arm_wait() -> Tuple[bool, str]:
        global _LOGO_PENDING
        _LOGO_PENDING = {
            "barrel_name": barrel_name,
            "canonical": canonical,
            "transforms": transforms,
            "is_barrel": is_barrel,
            "deadline": time.monotonic() + _LOGO_SEED_WAIT_S,
        }
        _log_info(
            f"Logo waiting up to {_LOGO_SEED_WAIT_S:.0f}s for seed detect "
            f"{canonical!r} before cloning {len(transforms)} letter props"
        )
        return True, "logo seed wait armed"

    cancel_logo_job()
    deferred.queue_action(f"logo BMS seed {canonical}", _seed)
    deferred.queue_action(f"logo wait {canonical}", _arm_wait)
    _log_info(
        f"Barrel logo deferred BMS seed+wait+clone for {barrel_name!r} "
        f"(canonical={canonical!r}, planned={len(transforms)})"
    )
    return len(transforms)


def _spawn_barrel_logo(
    *,
    barrel_name: str = "barrel",
    text: str = _LOGO_TEXT,
    distance: float = 1400.0,
    height: float = 750.0,
    spacing: float = 70.0,
    scale: float = 0.45,
    generated_only: bool = False,
    max_props: int = 0,
) -> int:
    """Queue prop-pixel world text. Returns props planned/queued (0 on failure).

    Hot path never calls oak_spawnai/load_package. Live template → paced clones.
    Otherwise queue the same deferred BMS ``spawn_actor_def`` Mob/IO uses, then clone.
    """
    del generated_only
    _, pawn, world, gs = _spawn_context()
    if pawn is None or world is None or gs is None:
        return 0

    actor_key = _alias_key(barrel_name)
    is_barrel = actor_key in ("barrel", "barrels")
    cls, source, class_name = _logo_find_live_template(barrel_name)
    if cls is not None and source is not None:
        transforms = _logo_plan_transforms(
            pawn=pawn,
            text=text,
            distance=distance,
            height=height,
            spacing=spacing,
            scale=scale,
            max_props=max_props,
            is_barrel=is_barrel,
        )
        if not transforms:
            return 0
        return _logo_start_clone_job(
            barrel_name=barrel_name,
            cls=cls,
            source=source,
            class_name=class_name,
            transforms=transforms,
            is_barrel=is_barrel,
        )

    # No live template: NEVER sync-seed (freezes). Use Mob/IO deferred queue.
    return _logo_queue_async_bms_seed_then_clone(
        barrel_name=barrel_name,
        text=text,
        distance=distance,
        height=height,
        spacing=spacing,
        scale=scale,
        max_props=max_props,
    )


# Direct SpawnAI support: build a GbxActorDef shell from an actor-def name, load
# likely actor/script/model packages, spawn a fresh OakSpawner in front of the
# player, then PushActorDef + ResetSpawner. This is the path proven with
# Char_CrazyEarl_Boss and is useful for unique actors whose live template is not
# already nearby.
_KNOWN_SPAWNAI_LOADS: Dict[str, Tuple[str, ...]] = {
    "char_crazyearl_boss": (
        "/Game/DLC/Cowbell/AI/Bosses/CrazyEarl/Char_CrazyEarl_Boss",
        "/Game/DLC/Cowbell/AI/Bosses/CrazyEarl/Character/Char_CrazyEarl_Boss",
        "/Game/DLC/Cowbell/AI/Bosses/CrazyEarl/Animation/BPAnim_CrazyEarl",
    ),
    "char_tubaboss": (
        "/Game/DLC/Tuba/AI/Bosses/TubaBoss/Char_TubaBoss",
        "/Game/DLC/Tuba/AI/Bosses/TubaBoss/Character/Char_TubaBoss",
        "/Game/DLC/Tuba/AI/Bosses/TubaBoss/Script_TubaBoss",
        "/Game/DLC/Tuba/AI/Bosses/TubaBoss/Script_TubaBoss_WaterBuoyance",
        "/Game/DLC/Tuba/PlayerCharacters/Scripts/Script_TubaBoss_WaterBuoyance",
    ),
    "char_targetdummy": (
        "/Game/InteractiveObjects/OakInteractiveObjects/TargetDummy/Char_TargetDummy",
        "/Game/InteractiveObjects/OakInteractiveObjects/TargetDummy/Script_TargetPracticeDummy",
        "/Game/InteractiveObjects/OakInteractiveObjects/TargetDummy/Model/Rig/SK_TargetDummy",
    ),
    "targetdummy": (
        "/Game/InteractiveObjects/OakInteractiveObjects/TargetDummy/Char_TargetDummy",
        "/Game/InteractiveObjects/OakInteractiveObjects/TargetDummy/Script_TargetPracticeDummy",
        "/Game/InteractiveObjects/OakInteractiveObjects/TargetDummy/Model/Rig/SK_TargetDummy",
    ),
    "char_npc_hermes": (
        "/Game/AI/NPC/_Unique/Hermes/Char_NPC_Hermes",
        "/Game/AI/NPC/_Unique/Hermes/Script_NPC_Hermes",
        "/Game/AI/NPC/_Unique/Hermes/Script_Hermes",
        "/Game/AI/NPC/_Unique/Hermes/Model/Rig/SK_Hermes",
    ),
    "char_npc_claptrap": (
        "/Game/AI/NPC/_Unique/Claptrap/Char_NPC_Claptrap",
        "/Game/AI/NPC/_Unique/Claptrap/_Design/Character/Char_NPC_Claptrap",
        "/Game/AI/NPC/_Unique/Claptrap/Script_NPC_Claptrap",
        "/Game/AI/NPC/_Unique/Claptrap/Model/Rig/SK_Claptrap_Skeleton",
        "/Game/AI/NPC/_Unique/Claptrap/Animation/BPAnim_Claptrap",
    ),
    # Confirmed from char_actor_paths: FullPhoenix exposes only a Body package.
    # It must be paired with an FGbxDefPtr shell named Char_NPC_Lilith_FullPhoenix.
    "char_npc_lilith_fullphoenix": (
        "/Game/AI/NPC/_Unique/Lilith/_Design/Character/Body_NPC_Lilith_FullPhoenix",
        "/Game/AI/NPC/_Unique/Lilith/_Design/Character/Script_NPC_Lilith",
        "/Game/AI/NPC/_Unique/Lilith/_Design/Character/Body_NPC_Lilith",
    ),
    "lilith_fullphoenix": (
        "/Game/AI/NPC/_Unique/Lilith/_Design/Character/Body_NPC_Lilith_FullPhoenix",
        "/Game/AI/NPC/_Unique/Lilith/_Design/Character/Script_NPC_Lilith",
        "/Game/AI/NPC/_Unique/Lilith/_Design/Character/Body_NPC_Lilith",
    ),
    "lootable_goldenchest": (
        "/Game/GameData/Lootables/ActorScripts/Script_Lootable_GoldenChest",
        "/Game/GameData/Lootables/Lootable_GoldenChest",
    ),
    "goldenchest": (
        "/Game/GameData/Lootables/ActorScripts/Script_Lootable_GoldenChest",
        "/Game/GameData/Lootables/Lootable_GoldenChest",
    ),
    "golden": (
        "/Game/GameData/Lootables/ActorScripts/Script_Lootable_GoldenChest",
        "/Game/GameData/Lootables/Lootable_GoldenChest",
    ),
    "playerbank": (
        "/Game/InteractiveObjects/GameSystemMachines/PlayerBank/Script_PlayerBank",
    ),
    "bank": (
        "/Game/InteractiveObjects/GameSystemMachines/PlayerBank/Script_PlayerBank",
    ),
    "io_playerbank": (
        "/Game/InteractiveObjects/GameSystemMachines/PlayerBank/Script_PlayerBank",
    ),
    "blackmarket": (
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine_BlackMarket",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/BlackMarket/Script_VendingMachine_BlackMarket",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/IO_VendingMachine_BlackMarket",
    ),
    "black_market": (
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine_BlackMarket",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/BlackMarket/Script_VendingMachine_BlackMarket",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/IO_VendingMachine_BlackMarket",
    ),
    "io_vendingmachine_blackmarket": (
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine_BlackMarket",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/BlackMarket/Script_VendingMachine_BlackMarket",
        "/Game/InteractiveObjects/GameSystemMachines/VendingMachines/IO_VendingMachine_BlackMarket",
    ),
}



# --- Enemy/boss name resolution from the shipped game_data.json dump --------
# BL4 enemy/boss actor-def names are hard to remember exactly (Char_Bat_Mine_Boss_
# Destroyer, Char_CrazyEarl_Boss, ...). The dump lets a user type a loose name like
# "crazyearl" or "destroyer" and have oak_spawn resolve it to the real Char_ def so
# the package guesser and shell builder work against a correct name every time.
_GAME_DATA_ENEMY_NAMES: Optional[List[str]] = None
_GAME_DATA_ENEMY_LOWER: Dict[str, str] = {}


def _oak_game_data_path() -> Any:
    from pathlib import Path  # noqa: PLC0415

    return Path(__file__).resolve().parent / "data" / "game_data.json"


def _load_game_data_enemy_names() -> List[str]:
    """Return the merged, de-duplicated enemy + actor name list from the dump."""
    global _GAME_DATA_ENEMY_NAMES, _GAME_DATA_ENEMY_LOWER
    if _GAME_DATA_ENEMY_NAMES is not None:
        return _GAME_DATA_ENEMY_NAMES
    names: List[str] = []
    seen: set[str] = set()
    try:
        import json  # noqa: PLC0415

        path = _oak_game_data_path()
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            for key in ("enemies", "actors"):
                for entry in data.get(key, []) or ():
                    text = str(entry).strip()
                    low = text.lower()
                    if text and low not in seen:
                        seen.add(low)
                        names.append(text)
    except Exception as exc:
        _log_warn(f"could not load Oak game_data.json enemy names: {exc}")
    _GAME_DATA_ENEMY_NAMES = names
    _GAME_DATA_ENEMY_LOWER = {n.lower(): n for n in names}
    return names


def _oak_norm_tokens(text: str) -> List[str]:
    import re  # noqa: PLC0415

    return [t for t in re.split(r"[^a-z0-9]+", str(text or "").lower()) if t]


def _resolve_actor_def_name(user_input: str) -> Tuple[str, List[str]]:
    """Map a loose user name to a canonical Char_ actor-def name from the dump.

    Returns (best_name, suggestions). If nothing matches, best_name is the raw
    input unchanged so existing exact-name behavior is preserved.
    """
    raw = str(user_input or "").strip()
    if not raw:
        return raw, []
    names = _load_game_data_enemy_names()
    if not names:
        return raw, []
    low = raw.lower()
    if low in _GAME_DATA_ENEMY_LOWER:
        return _GAME_DATA_ENEMY_LOWER[low], []
    if not low.startswith("char") and ("char_" + low) in _GAME_DATA_ENEMY_LOWER:
        return _GAME_DATA_ENEMY_LOWER["char_" + low], []

    # If the user already typed a full, real-looking actor-def name (Char_...), trust
    # it verbatim. The dump can be incomplete, and fuzzy-remapping a valid exact name
    # would break bosses that already spawned fine before.
    if low.startswith("char_") and "_" in raw[5:]:
        return raw, []

    tokens = _oak_norm_tokens(raw)
    if not tokens:
        return raw, []
    # Non-character asset prefixes that should never win a spawn (projectiles,
    # props, decorations, meshes, materials, effects, mixes, interactive objects).
    junk_prefixes = (
        "proj_", "mix_", "io_", "deco", "prop_", "sm_", "sk_", "bp_", "mi_",
        "mat_", "fx_", "anim_", "abp_", "wt_", "vfx_", "sfx_", "cue_",
    )
    scored: List[Tuple[int, int, int, int, str]] = []
    for name in names:
        nl = name.lower()
        if not all(tok in nl for tok in tokens):
            continue
        # 0 = real Char_ actor def, 1 = other Char, 2 = anything else.
        if nl.startswith("char_"):
            category = 0
        elif nl.startswith("char"):
            category = 1
        else:
            category = 2
        junk = 0
        if any(nl.startswith(p) for p in junk_prefixes):
            junk += 5
        for decor in ("true", "clone", "replay", "_add", "bossadd", "decochar", "mini"):
            if decor in nl:
                junk += 1
        # The user is asking about bosses, so prefer boss defs on ties.
        boss_flag = 0 if "boss" in nl else 1
        scored.append((category, junk, boss_flag, len(nl), name))
    if not scored:
        return raw, []
    scored.sort()
    best = scored[0][4]
    suggestions = [row[4] for row in scored[:8]]
    return best, suggestions


def _looks_like_actor_def(name: str) -> bool:
    """True when a name should route through the AI actor-def spawn path."""
    text = str(name or "").strip()
    if not text:
        return False
    low = text.lower()
    if low.startswith("char"):
        return True
    if "boss" in low or "enemy" in low:
        return True
    _load_game_data_enemy_names()
    return low in _GAME_DATA_ENEMY_LOWER


# Big / arena bosses need extra room and stream in slower than trash enemies, so
# Oak Spawner gives them a larger default spawn distance and a longer settle window.
_LARGE_BOSS_TOKENS: Tuple[str, ...] = (
    "boss", "raid", "uber", "colossal", "titan", "bigboss", "worldboss",
    "matriarch", "leviathan", "kraken", "behemoth", "terramorph",
    "gunship", "battlewagon", "drill_boss",
)
# Blocking poll caps — long sleeps freeze listen-server hosts and drop remote clients.
_POLL_TIMEOUT_BOSS = 2.0
_POLL_TIMEOUT_NORMAL = 1.2
_POLL_TIMEOUT_BOSS_UNRESOLVED = 1.5
_POLL_TIMEOUT_NORMAL_UNRESOLVED = 0.8
_POLL_TIMEOUT_BOSS_COOP = 0.45
_POLL_TIMEOUT_NORMAL_COOP = 0.28
_LOADED_SPAWN_PACKAGES: set[str] = set()
_FAILED_SPAWN_PACKAGES: set[str] = set()
_SPAWN_MANAGER_OVERDRIVEN_KEY: str = ""
_ASYNC_PACKAGE_WARMED: set[str] = set()
_THIN_AIR_SPAWNER_TEMPLATE: Any | None = None
_THIN_AIR_SPAWNER_WORLD_KEY: str = ""


def _is_large_boss_like(name: str) -> bool:
    low = str(name or "").strip().lower()
    if not low:
        return False
    return any(tok in low for tok in _LARGE_BOSS_TOKENS)


def _spawnai_poll_timeout(*, actor_def: str, resolved: bool, coop_safe: bool) -> float:
    big = _is_large_boss_like(actor_def)
    if coop_safe:
        return _POLL_TIMEOUT_BOSS_COOP if big else _POLL_TIMEOUT_NORMAL_COOP
    if resolved:
        return _POLL_TIMEOUT_BOSS if big else _POLL_TIMEOUT_NORMAL
    return _POLL_TIMEOUT_BOSS_UNRESOLVED if big else _POLL_TIMEOUT_NORMAL_UNRESOLVED


def _actor_def_name_variants(actor_def: str) -> Tuple[str, ...]:
    """Return the actor-def name plus common runtime variants to try resolving.

    BL4 bosses frequently ship both a base def and a combat-ready ``...TRUE``
    variant, and sometimes only one of them exposes a usable GbxActorDef. Trying
    both (and stripping Replay/Clone decorations) makes resolution far more
    reliable than a single exact name.
    """
    name = str(actor_def or "").strip()
    if not name:
        return ()
    out: List[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        candidate = str(candidate or "").strip()
        if candidate and candidate.lower() not in seen:
            seen.add(candidate.lower())
            out.append(candidate)

    _add(name)
    _add(name + "TRUE")
    _add(name + "_TRUE")
    base = name
    for suffix in ("_Replay_True", "_Replay", "_Clone", "TRUE", "_TRUE"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            _add(base)
    _add(base + "TRUE")
    _add(base + "_TRUE")
    return tuple(out)


def _spawnai_family(actor_def: str) -> str:
    """Return the leading enemy-family token, e.g. Bat from Char_Bat_Mine_Boss_X."""
    name = str(actor_def or "").strip()
    for prefix in ("Char_NPC_", "Char_AI_", "Char_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    name = name.split("_", 1)[0]
    return name.strip()


def _spawnai_core_name(actor_def: str) -> str:
    """Return a compact content-folder-ish name from a Gbx actor def."""
    name = str(actor_def or "").strip()
    for prefix in ("Char_NPC_", "Char_AI_", "Char_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    if name.endswith("_C"):
        name = name[:-2]
    # Drop runtime decorations so CrazyEarl_Boss_Replay_True -> CrazyEarl.
    for suffix in ("_Replay_True", "_Replay", "_Clone", "TRUE", "_TRUE"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    # Char_CrazyEarl_Boss lives in a CrazyEarl folder, not CrazyEarl_Boss.
    if name.lower().endswith("_boss"):
        name = name[:-5]
    return name or str(actor_def or "").strip()


def _spawnai_path_package(path: str) -> str:
    """Normalize /Game/Foo.Asset_C into /Game/Foo for load_package."""
    path = str(path or "").strip()
    if not path:
        return ""
    if "." in path:
        path = path.split(".", 1)[0]
    if path.endswith("_C"):
        path = path[:-2]
    return path


def _spawnai_sibling_packages(actor_def: str, package: str) -> Tuple[str, ...]:
    """Guess nearby Char_/Script_/Body_ assets based on a user supplied --load path."""
    package = _spawnai_path_package(package)
    if not package or "/" not in package:
        return ()
    folder, asset = package.rsplit("/", 1)
    core = _spawnai_core_name(actor_def)
    names = (
        actor_def,
        f"Char_{core}",
        f"Char_NPC_{core}",
        f"Script_{core}",
        f"Script_NPC_{core}",
        f"Body_{core}",
        f"Body_NPC_{core}",
        asset,
    )
    folders = [folder]
    # If the user points at .../_Design/Character/Asset, also try the parent and nearby conventional folders.
    if folder.endswith("/_Design/Character"):
        parent = folder[: -len("/_Design/Character")]
        folders.extend((parent, f"{parent}/_Design/Character"))
    if folder.endswith("/Scripts"):
        parent = folder[: -len("/Scripts")]
        folders.extend((parent, f"{parent}/_Design/Character", f"{parent}/Character"))
    out=[]
    seen=set()
    for f in folders:
        for n in names:
            p=f"{f}/{n}"
            if p not in seen:
                seen.add(p); out.append(p)
    return tuple(out)


def _spawnai_guess_load_packages(
    actor_def: str,
    extra_loads: Sequence[str] = (),
    *,
    lean: bool = False,
) -> Tuple[str, ...]:
    """Guess actor/script/model packages to hot-load for an actor def.

    ``lean=True`` (coop / mob-spawner UI): only known paths + extras + a few
    high-value family roots. Full fan-out was causing multi-second freezes from
    dozens of failed load_package calls on the game thread.
    """
    actor_def = str(actor_def or "").strip()
    key = _alias_key(actor_def)
    core = _spawnai_core_name(actor_def)
    guesses: List[str] = []

    guesses.extend(_KNOWN_SPAWNAI_LOADS.get(key, ()))

    if key.startswith("io_"):
        guesses.extend((
            f"/Game/InteractiveObjects/{actor_def}",
            f"/Game/InteractiveObjects/GameSystemMachines/{actor_def}",
            f"/Game/InteractiveObjects/GameSystemMachines/VendingMachines/{actor_def}",
            f"/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/{actor_def}",
            f"/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_{core}",
            f"/Game/InteractiveObjects/GameSystemMachines/VendingMachines/Scripts/Script_VendingMachine",
            f"/Game/GameData/Lootables/{actor_def}",
        ))

    for extra in extra_loads:
        extra = str(extra or "").strip()
        if extra:
            guesses.append(extra)

    if lean:
        family = _spawnai_family(actor_def)
        is_npc = actor_def.startswith("Char_NPC_")
        if is_npc and family:
            guesses.extend((
                f"/Game/AI/NPC/_Unique/{core}/_Design/Character/{actor_def}",
                f"/Game/AI/NPC/_Unique/{core}/{actor_def}",
                f"/Game/AI/NPC/_Unique/{family}/_Design/Character/{actor_def}",
                f"/Game/AI/NPC/_Unique/{family}/{actor_def}",
            ))
        elif family:
            guesses.extend((
                f"/Game/AI/_Enemies/{family}/_Design/Character/{actor_def}",
                f"/Game/AI/_Enemies/{family}/{actor_def}",
                f"/Game/AI/Enemies/{family}/_Design/Character/{actor_def}",
                f"/Game/AI/NPC/_Unique/{core}/_Design/Character/{actor_def}",
                f"/Game/AI/NPC/_Unique/{core}/{actor_def}",
            ))
        guesses.extend((
            f"/Game/AI/{actor_def}",
            f"/Game/AI/{core}/{actor_def}",
        ))
        out: List[str] = []
        seen: set[str] = set()
        for path in guesses:
            path = _spawnai_path_package(path)
            if not path or path in seen:
                continue
            seen.add(path)
            out.append(path)
        return tuple(out[:6])

    guesses.extend((
        f"/Game/AI/{actor_def}",
        f"/Game/AI/{core}/{actor_def}",
        f"/Game/AI/{core}/Script_{core}",
        f"/Game/AI/NPC_{core}/{actor_def}",
        f"/Game/AI/NPC_{core}/Script_NPC_{core}",
        f"/Game/AI/NPC/{core}/{actor_def}",
        f"/Game/AI/NPC/{core}/Script_NPC_{core}",
        f"/Game/AI/NPC/{core}/Script_{core}",
        f"/Game/AI/NPC/_Unique/{core}/{actor_def}",
        f"/Game/AI/NPC/_Unique/{core}/_Design/Character/{actor_def}",
        f"/Game/AI/NPC/_Unique/{core}/_Design/Character/Char_{core}",
        f"/Game/AI/NPC/_Unique/{core}/_Design/Character/Char_NPC_{core}",
        f"/Game/AI/NPC/_Unique/{core}/_Design/Character/Body_NPC_{core}",
        f"/Game/AI/NPC/_Unique/{core}/Script_NPC_{core}",
        f"/Game/AI/NPC/_Unique/{core}/Script_{core}",
        f"/Game/AI/NPC/_Unique/{core}/Model/Rig/SK_{core}",
        f"/Game/AI/NPC/_Unique/{core}/Animation/BPAnim_{core}",
        f"/Game/AI/NPC/_Gestalt/Custom/{core}/_Design/Character/{actor_def}",
        f"/Game/AI/NPC/_Gestalt/Custom/{core}/_Design/Character/Char_{core}",
        f"/Game/AI/NPC/_Gestalt/Custom/{core}/_Design/Character/Char_NPC_{core}",
        f"/Game/AI/NPC/_Gestalt/Custom/{core}/_Design/Character/Body_NPC_{core}",
        f"/Game/AI/NPC/_Gestalt/Custom/{core}/_Design/Character/Script_NPC_{core}",
    ))

    # Enemy/boss folder conventions. BL4 enemies are grouped under a family folder
    # (Bat, Beast, Brute, Cat, Creep, ...) rather than the NPC "_Unique" layout, so
    # fan out over the common enemy roots for both the exact def and its family.
    family = _spawnai_family(actor_def)
    if family:
        enemy_roots = (
            "/Game/AI/_Enemies",
            "/Game/AI/Enemies",
            "/Game/Enemies",
            "/Game/AI/Char",
            "/Game/Characters",
            "/Game/AI/NPC/_Enemies",
        )
        for root in enemy_roots:
            guesses.extend((
                f"{root}/{family}/{actor_def}",
                f"{root}/{family}/_Design/Character/{actor_def}",
                f"{root}/{family}/_Design/Character/Char_{core}",
                f"{root}/{family}/Char_{family}_SHARED",
                f"{root}/{family}/{family}/{actor_def}",
                f"{root}/{actor_def}",
            ))

    if "target" in key and "dummy" in key:
        guesses.extend(_KNOWN_SPAWNAI_LOADS["char_targetdummy"])

    for extra in extra_loads:
        extra = str(extra or "").strip()
        if not extra:
            continue
        guesses.append(extra)
        guesses.extend(_spawnai_sibling_packages(actor_def, extra))

    out: List[str] = []
    seen: set[str] = set()
    for path in guesses:
        path = _spawnai_path_package(path)
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return tuple(out)


def _spawnai_load_packages(
    actor_def: str,
    extra_loads: Sequence[str] = (),
    *,
    lean: bool = False,
    max_packages: int = 8,
) -> None:
    packages: List[str] = []
    seen_pkgs: set[str] = set()
    variants = _actor_def_name_variants(actor_def)
    if lean:
        # Exact name + TRUE variant only — never append TRUE if already present (avoids TRUETRUE).
        base = str(actor_def or "").strip()
        variants_list = [base]
        low = base.lower()
        if not (low.endswith("true") or low.endswith("_true")):
            variants_list.extend((base + "TRUE", base + "_TRUE"))
        variants = tuple(dict.fromkeys(variants_list))
    for variant in variants:
        for package in _spawnai_guess_load_packages(variant, extra_loads, lean=lean):
            if package not in seen_pkgs:
                seen_pkgs.add(package)
                packages.append(package)
    if lean:
        packages = packages[: max(1, int(max_packages))]
    for package in packages:
        if package in _LOADED_SPAWN_PACKAGES or package in _FAILED_SPAWN_PACKAGES:
            continue
        try:
            result = unrealsdk_load_package(package)
        except NameError:
            # Keep unrealsdk import local so this file still loads in SDK builds
            # where only selected symbols were imported at module top.
            try:
                import unrealsdk as _unrealsdk
                result = _unrealsdk.load_package(package)
            except Exception as exc:
                _log_warn(f"load_package {package} failed: {exc}")
                _FAILED_SPAWN_PACKAGES.add(package)
                continue
        except Exception as exc:
            _log_warn(f"load_package {package} failed: {exc}")
            _FAILED_SPAWN_PACKAGES.add(package)
            continue
        if result is not None:
            _LOADED_SPAWN_PACKAGES.add(package)
            _log_info(f"load_package {package} -> {result}")
        else:
            _FAILED_SPAWN_PACKAGES.add(package)
            _log_warn(f"load_package {package} returned no package; skipping retries this session")


def _spawnai_load_known_packages_only(
    actor_def: str,
    extra_loads: Sequence[str] = (),
    *,
    max_packages: int = 3,
) -> None:
    """Load only curated known paths — safe for async BMS (no family guess fan-out)."""
    key = _alias_key(actor_def)
    packages: List[str] = []
    seen_pkgs: set[str] = set()
    for raw in (*_KNOWN_SPAWNAI_LOADS.get(key, ()), *extra_loads):
        package = _spawnai_path_package(str(raw or "").strip())
        if not package or package in seen_pkgs:
            continue
        seen_pkgs.add(package)
        packages.append(package)
    for package in packages[: max(1, int(max_packages))]:
        if package in _LOADED_SPAWN_PACKAGES or package in _FAILED_SPAWN_PACKAGES:
            continue
        try:
            result = unrealsdk_load_package(package)
        except NameError:
            try:
                import unrealsdk as _unrealsdk
                result = _unrealsdk.load_package(package)
            except Exception as exc:
                _log_warn(f"load_package {package} failed: {exc}")
                _FAILED_SPAWN_PACKAGES.add(package)
                continue
        except Exception as exc:
            _log_warn(f"load_package {package} failed: {exc}")
            _FAILED_SPAWN_PACKAGES.add(package)
            continue
        if result is not None:
            _LOADED_SPAWN_PACKAGES.add(package)
            _log_info(f"load_package {package} -> {result}")
        else:
            _FAILED_SPAWN_PACKAGES.add(package)
            _log_warn(f"load_package {package} returned no package; skipping retries this session")


def _make_actor_def_shell(actor_def: str) -> Any:
    name = str(actor_def or "").strip()
    if not name:
        return None
    try:
        from gbx_def_ptr_helpers import build_actor_fgbx_def_ptr  # noqa: PLC0415

        shell = build_actor_fgbx_def_ptr(name)
        if shell is not None:
            return shell
    except Exception:
        pass
    import unrealsdk as _unrealsdk

    ref = find_object("ScriptStruct", "/Script/GbxSpawn.GbxActorDef")
    for type_arg in (ref, "GbxActorDef", "/Script/GbxSpawn.GbxActorDef"):
        if type_arg is None:
            continue
        try:
            return _unrealsdk.unreal.FGbxDefPtr(name, type=type_arg)
        except Exception:
            continue
    try:
        return _legacy_fgbx_def_ptr(name, ref)
    except Exception:
        return None


def _legacy_fgbx_def_ptr(name: str, ref: Any) -> Any:
    import unrealsdk as _unrealsdk

    try:
        ptr = _unrealsdk.unreal.FGbxDefPtr(name, type=ref or "GbxActorDef")
        return ptr
    except Exception:
        pass
    shell = _unrealsdk.unreal.FGbxDefPtr(name)
    if ref is not None:
        try:
            shell._experimental_ref = ref
        except Exception:
            pass
    try:
        shell._experimental_name = name
    except Exception:
        pass
    return shell


def _find_resolved_actor_def_by_name(actor_def: str) -> Optional[Any]:
    wanted = str(actor_def or "").strip()
    if not wanted:
        return None
    # Prefer live OakCharacters with a resolved instance.
    for cls_name in ("OakCharacter", "OakPawn", "OakActor", "Actor"):
        try:
            objects = list(find_all(cls_name, False))
        except TypeError:
            try:
                objects = list(find_all(cls_name))
            except Exception:
                continue
        except Exception:
            continue
        for obj in objects:
            low = str(obj).lower()
            if "default__" in low or "/script/" in low:
                continue
            try:
                d = obj.GbxActorData.GbxActorDef
            except Exception:
                continue
            def_name = _actor_def_name(d)
            exp_name = getattr(d, "_experimental_name", None)
            obj_name = ""
            try:
                obj_name = str(getattr(obj, "Name", "") or "")
            except Exception:
                pass
            name_match = (
                (exp_name is not None and str(exp_name) == wanted)
                or def_name == wanted
                or obj_name == wanted
            )
            if not name_match:
                continue
            try:
                if getattr(d, "_experimental_instance", None):
                    return d
            except Exception:
                pass
            # Story NPCs (FGameDataHandle) often lack _experimental_instance but still spawn.
            if def_name == wanted or (exp_name is not None and str(exp_name) == wanted) or obj_name == wanted:
                return d
    return None


def _spawnai_object_paths_for_package(actor_def: str, package: str) -> Tuple[str, ...]:
    package = _spawnai_path_package(package)
    if not package:
        return ()
    asset = package.rsplit("/", 1)[-1]
    names = (asset, actor_def, f"{asset}_C", f"{actor_def}_C")
    out=[]; seen=set()
    for name in names:
        p=f"{package}.{name}"
        if p not in seen:
            seen.add(p); out.append(p)
    return tuple(out)


def _spawnai_find_loaded_objects(actor_def: str, extra_loads: Sequence[str] = ()) -> List[Any]:
    """Return loaded UObject candidates for the guessed packages."""
    classes = (
        "GbxActorDef", "OakActorDef", "GbxCharacterDef", "OakCharacterDef",
        "BlueprintGeneratedClass", "GbxActorScriptClass", "Class", "Blueprint",
    )
    out=[]; seen=set()
    for package in _spawnai_guess_load_packages(actor_def, extra_loads):
        for path in _spawnai_object_paths_for_package(actor_def, package):
            for cls_name in classes:
                try:
                    obj = find_object(cls_name, path)
                except Exception:
                    continue
                if obj is None:
                    continue
                key=str(obj)
                if key in seen:
                    continue
                seen.add(key); out.append(obj)
                _log_info(f"resolved loaded actor object {path} class={cls_name}")
    return out


def _spawnai_real_def_from_object(obj: Any, depth: int = 0, seen: Optional[set[str]] = None) -> Optional[Any]:
    """Walk an object/class/default object and return a real exposed GbxActorDef pointer."""
    if obj is None or depth > 4:
        return None
    if seen is None:
        seen = set()
    try:
        key = str(obj)
    except Exception:
        key = repr(obj)
    if key in seen:
        return None
    seen.add(key)

    # Direct actor data on instances/default objects.
    try:
        d = obj.GbxActorData.GbxActorDef
        if d is not None:
            return d
    except Exception:
        pass

    # Some loaded actor-def-like objects are already the instance behind a pointer,
    # but do not create or mutate FGbxDefPtr here; this SDK has read-only internals.
    for attr in (
        "ClassDefaultObject", "GeneratedClass", "ParentClass", "Class",
        "DefaultObject", "ObjectArchetype", "_experimental_instance",
    ):
        try:
            child = getattr(obj, attr, None)
        except Exception:
            child = None
        if child is None or child is obj:
            continue
        d = _spawnai_real_def_from_object(child, depth + 1, seen)
        if d is not None:
            return d
    return None


def _spawnai_resolve_from_loaded_packages_only(
    actor_def: str,
    extra_loads: Sequence[str] = (),
) -> Optional[Any]:
    """Resolve via session cache + find_object on already-loaded packages (no find_all)."""
    key = _alias_key(actor_def)
    cached = _ACTOR_DEF_CACHE.get(key)
    if cached is not None:
        return cached
    packages: List[str] = []
    seen_pkgs: set[str] = set()
    for raw in (
        *_KNOWN_SPAWNAI_LOADS.get(key, ()),
        *extra_loads,
    ):
        pkg = _spawnai_path_package(str(raw or "").strip())
        if pkg and pkg not in seen_pkgs:
            seen_pkgs.add(pkg)
            packages.append(pkg)
    for variant in _actor_def_name_variants(actor_def)[:1]:
        for pkg in _spawnai_guess_load_packages(variant, extra_loads, lean=True)[:4]:
            if pkg not in seen_pkgs:
                seen_pkgs.add(pkg)
                packages.append(pkg)
    classes = (
        "GbxActorDef", "OakActorDef", "GbxCharacterDef", "OakCharacterDef",
        "BlueprintGeneratedClass", "GbxActorScriptClass", "Class", "Blueprint",
    )
    for variant in _actor_def_name_variants(actor_def):
        for package in packages:
            for path in _spawnai_object_paths_for_package(variant, package):
                for cls_name in classes:
                    try:
                        obj = find_object(cls_name, path)
                    except Exception:
                        obj = None
                    if obj is None:
                        continue
                    d = _spawnai_real_def_from_object(obj)
                    if d is not None:
                        _log_info(
                            f"oak_spawnai loaded-package resolve {actor_def!r}: {_actor_def_name(d)}"
                        )
                        return d
    return None


def _queue_async_actor_package_warm(actor_def: str, extra_loads: Sequence[str] = ()) -> None:
    """Defer lean package loads to PlayerTick — not the BMS click hot path."""
    key = _alias_key(actor_def)
    if key in _ASYNC_PACKAGE_WARMED:
        return
    _ASYNC_PACKAGE_WARMED.add(key)
    loads = tuple(extra_loads or ())

    def _warm() -> tuple[bool, str]:
        if key in _KNOWN_SPAWNAI_LOADS:
            _spawnai_load_known_packages_only(actor_def, loads, max_packages=3)
        else:
            _spawnai_load_packages(actor_def, loads, lean=True, max_packages=2)
        return True, f"async warmed packages for {actor_def}"

    try:
        from Squ1ggsBoostingTools import spawn_deferred as deferred  # noqa: PLC0415

        deferred.queue_action(f"Warm spawn packages {actor_def}", _warm)
    except Exception as exc:
        _ASYNC_PACKAGE_WARMED.discard(key)
        _log_warn(f"could not queue async package warm for {actor_def!r}: {exc}")


def _spawnai_resolve_real_actor_def(actor_def: str, extra_loads: Sequence[str] = ()) -> Optional[Any]:
    d = _find_resolved_actor_def_by_name(actor_def) or _ACTOR_DEF_CACHE.get(_alias_key(actor_def))
    if d is not None:
        return d
    # Try the requested name and its common runtime variants (…TRUE, base, etc.).
    for variant in _actor_def_name_variants(actor_def):
        cached = _ACTOR_DEF_CACHE.get(_alias_key(variant))
        if cached is not None:
            return cached
        live = _find_resolved_actor_def_by_name(variant)
        if live is not None:
            return live
        for obj in _spawnai_find_loaded_objects(variant, extra_loads):
            d = _spawnai_real_def_from_object(obj)
            if d is not None:
                _log_info(f"loaded object {obj} exposed real GbxActorData.GbxActorDef: {_actor_def_name(d)}")
                return d
            _log_warn(f"loaded object {obj} did not expose GbxActorData.GbxActorDef")
    return None


def _spawnai_probe(actor_def: str, extra_loads: Sequence[str] = ()) -> None:
    _log_info(f"oak_probe build={_BUILD_TAG} actor_def={actor_def!r} loads={tuple(extra_loads)}")
    _spawnai_load_packages(actor_def, extra_loads)
    found = False
    for obj in _spawnai_find_loaded_objects(actor_def, extra_loads):
        found = True
        d = _spawnai_real_def_from_object(obj)
        if d is not None:
            _log_info(f"PROBE OK object={obj} def={_actor_def_name(d)} ptr={d}")
        else:
            _log_warn(f"PROBE NO_DEF object={obj} type={type(obj)}")
    if not found:
        _log_warn("PROBE found no loaded UObject candidates. The package path may be wrong or the asset name may not match the package name.")




def _safe_set_attr(obj: Any, attr: str, value: Any) -> bool:
    try:
        if not hasattr(obj, attr):
            return False
        setattr(obj, attr, value)
        return True
    except Exception:
        return False


def _bump_attribute_initializer(param: Any, multiplier: int) -> int:
    """BL3-style helper for AttributeInitializationData-backed spawn params."""
    changed = 0
    if param is None:
        return changed

    # Direct range/value fields seen in BL3 BunchList examples.
    for chain in (
        ("Range", "Value"),
        ("Range", "BaseValue"),
        ("Range", "Constant"),
    ):
        try:
            target = param
            for attr in chain[:-1]:
                target = getattr(target, attr)
            setattr(target, chain[-1], multiplier)
            changed += 1
        except Exception:
            pass

    # BL3 pattern:
    # param.AttributeInitializationData.BaseValueScale = multiplier
    # param.AttributeInitializationData.BaseValueConstant = multiplier
    try:
        aid = param.AttributeInitializationData
        for field in ("BaseValueScale", "BaseValueConstant", "BaseValue", "Value"):
            try:
                setattr(aid, field, multiplier)
                changed += 1
            except Exception:
                pass
    except Exception:
        pass

    # Some BL4 structs may expose the same fields directly.
    for field in ("BaseValueScale", "BaseValueConstant", "BaseValue", "Value"):
        if _safe_set_attr(param, field, multiplier):
            changed += 1

    return changed


def _overdrive_spawn_style_object(style: Any, multiplier: int) -> int:
    """Apply BL3-style spawn multiplier edits to a style/SpawnDetails object."""
    if style is None:
        return 0

    changed = 0

    # Common BL3/Oak style knobs.
    for attr in ("SpawnDelay", "WaveDelay", "Cooldown", "SpawnCooldown", "RespawnCooldown", "InitialDelay"):
        if _safe_set_attr(style, attr, 0):
            changed += 1

    for attr in ("bInfinite", "bUnlimitedSpawns", "bAllowRespawn", "bRespawnEnabled", "bEnabled"):
        if _safe_set_attr(style, attr, True):
            changed += 1

    # Params from your BL3 script and likely BL4 equivalents.
    for attr in (
        "NumActorsParam",
        "NumAliveActorsParam",
        "MaxAliveActorsWhenPassive",
        "MaxAliveActorsWhenThreatened",
        "MaxActiveActors",
        "MaxAliveActors",
        "MaxSpawnedActors",
        "SpawnCount",
        "ActorCount",
        "WaveSize",
        "Population",
        "DesiredPopulation",
    ):
        try:
            changed += _bump_attribute_initializer(getattr(style, attr), multiplier)
        except Exception:
            pass

    # BunchList / Encounter-like nested content.
    for seq_attr in ("bunches", "Bunches", "waves", "Waves", "SpawnOptions", "spawnOptions"):
        try:
            seq = getattr(style, seq_attr)
        except Exception:
            continue
        try:
            for item in seq:
                changed += _overdrive_spawn_style_object(item, multiplier)
                for nested_attr in ("SpawnerStyle", "SpawnStyle", "style"):
                    try:
                        changed += _overdrive_spawn_style_object(getattr(item, nested_attr), multiplier)
                    except Exception:
                        pass
        except Exception:
            pass

    return changed


def _held_shape_heavy() -> bool:
    """True when loot-shape pins make find_all unsafe (freezes host + lobby)."""
    try:
        from Squ1ggsBoostingTools import loot_shapes as ls

        pins = list(getattr(ls, "_pinned_slots", []) or [])
        hold_n = sum(1 for row in pins if row.get("hold"))
        if hold_n >= 40:
            return True
        if bool(getattr(ls, "_guest_sync_active", False)):
            return True
        quiet_fn = getattr(ls, "_in_join_quiet", None)
        if callable(quiet_fn) and quiet_fn():
            return True
    except Exception:
        pass
    return False


def _overdrive_spawn_manager(multiplier: int) -> int:
    """Raise global spawn caps similar to the old BL3 SpawnCap hook."""
    if _held_shape_heavy():
        # find_all(SpawnManager) with hundreds of held pickups freezes BL4 for everyone.
        _log_warn("Skipping SpawnManager find_all while a large held shape / join quiet is active.")
        return 0
    changed = 0
    for cls_name in ("SpawnManager", "OakSpawnManager"):
        try:
            managers = list(find_all(cls_name, False))
        except TypeError:
            try:
                managers = list(find_all(cls_name))
            except Exception:
                continue
        except Exception:
            continue

        for mgr in managers:
            for field, value in (
                ("MaxSpawnCost", 2147483647),
                ("MaxActorsSpawnedPerFrame", 2147483647),
                ("MaxSpawnedActors", 2147483647),
                ("MaxAliveActors", 2147483647),
                ("SpawnBudget", 2147483647),
            ):
                if _safe_set_attr(mgr, field, value):
                    changed += 1

    if changed:
        _log_info(f"spawn manager overdrive changed_fields={changed}")
    return changed


def _overdrive_spawn_manager_if_needed(world: Any) -> None:
    """Raise global spawn caps once per map (find_all is too heavy per BMS click)."""
    global _SPAWN_MANAGER_OVERDRIVEN_KEY
    world_key = str(world or "")
    if world_key and world_key == _SPAWN_MANAGER_OVERDRIVEN_KEY:
        return
    if _overdrive_spawn_manager(2147483647) >= 0:
        _SPAWN_MANAGER_OVERDRIVEN_KEY = world_key


def _overdrive_spawner_component_fast(comp: Any) -> int:
    """Cap/infinite flags only — safe on every async thin-air duplicate."""
    if comp is None:
        return 0
    changed = 0
    cap = 2147483647
    targets: List[Any] = [comp]
    for attr in ("OakSpawner", "SpawnDetails", "Activation", "SpawnerStyle", "SpawnerStyleOverride"):
        try:
            sub = getattr(comp, attr)
            if sub is not None:
                targets.append(sub)
        except Exception:
            pass
    try:
        spawner = comp.OakSpawner
        if spawner is not None:
            targets.append(spawner)
    except Exception:
        pass
    for target in targets:
        for field in (
            "bSpawnerEnabled", "bSpawnPointEnabled", "bEnabled", "bActive", "bCanSpawn",
            "bAllowSpawn", "bAllowRespawn", "bRespawnEnabled", "bInfinite", "bUnlimitedSpawns",
        ):
            if _safe_set_attr(target, field, True):
                changed += 1
        for field in (
            "MaxAliveActors", "MaxActiveActors", "MaxSpawnedActors", "MaxActors", "MaxSpawnCount",
            "SpawnLimit", "ActorLimit", "PopulationLimit", "NumActorsToSpawn", "SpawnCount",
        ):
            if _safe_set_attr(target, field, cap):
                changed += 1
    for fn_name, args in (("SetSpawnerEnabled", (True,)), ("SetSpawnPointEnabled", (True,))):
        try:
            getattr(comp, fn_name)(*args)
            changed += 1
        except Exception:
            pass
    return changed


def _construct_extra_spawn_points_for_component(comp: Any, multiplier: int, spacing: float = 250.0) -> int:
    """Create additional OakSpawnPoint objects like the BL3 multiplier script.

    This is best-effort and only runs when the component exposes SpawnPoints.
    """
    try:
        points = comp.SpawnPoints
    except Exception:
        try:
            points = comp.spawnpoints
        except Exception:
            return 0

    try:
        current_len = len(points)
    except Exception:
        return 0

    if current_len >= max(2, multiplier):
        return 0

    try:
        import unrealsdk as _unrealsdk
        world_outer = ENGINE.GameViewport.World.CurrentLevel.OwningWorld.PersistentLevel
    except Exception:
        return 0

    # Source point to copy action/stretch data from, if available.
    try:
        source_point = points[0] if current_len > 0 else None
    except Exception:
        source_point = None

    created = 0
    offsets = [
        (spacing, 0, 0), (-spacing, 0, 0), (0, spacing, 0), (0, -spacing, 0),
        (spacing, spacing, 0), (-spacing, spacing, 0), (spacing, -spacing, 0), (-spacing, -spacing, 0),
        (spacing * 2, 0, 0), (-spacing * 2, 0, 0), (0, spacing * 2, 0), (0, -spacing * 2, 0),
    ]

    for idx in range(max(0, multiplier - current_len)):
        try:
            oak_spawn_point = _unrealsdk.construct_object("OakSpawnPoint", outer=world_outer)
            off = offsets[idx % len(offsets)]
            try:
                oak_spawn_point.SpawnPointComponent.RelativeLocation = _unrealsdk.make_struct(
                    "Vector", X=float(off[0]), Y=float(off[1]), Z=float(off[2])
                )
            except Exception:
                pass

            if source_point is not None:
                for attr in ("SpawnAction", "SpawnStretchType", "StretchyPoint"):
                    try:
                        setattr(oak_spawn_point.SpawnPointComponent, attr, getattr(source_point.SpawnPointComponent, attr))
                    except Exception:
                        pass

            try:
                points.append(oak_spawn_point)
            except Exception:
                try:
                    comp.spawnpoints.append(oak_spawn_point)
                except Exception:
                    continue

            created += 1
        except Exception as exc:
            _log_warn(f"extra spawnpoint creation failed: {exc}")
            break

    if created:
        _safe_set_attr(comp, "SpawnPointUseType", 1)
        _log_info(f"created {created} extra OakSpawnPoint(s) for {comp}")

    return created


def _overdrive_spawner_component(comp: Any, multiplier: int) -> int:
    """Apply BL3-inspired spawner multiplier changes to a BL4 OakSpawnerComponent."""
    desired = max(1, int(multiplier))
    changed = 0

    _overdrive_spawn_manager(desired)

    # Direct component and owner flags/caps.
    targets: List[Any] = [comp]
    for attr in ("OakSpawner", "SpawnDetails", "Activation", "SpawnerStyle", "SpawnerStyleOverride"):
        try:
            sub = getattr(comp, attr)
            if sub is not None:
                targets.append(sub)
        except Exception:
            pass

    try:
        spawner = comp.OakSpawner
        if spawner is not None:
            targets.append(spawner)
            for attr in ("SpawnerComponent", "SpawnPointComponent", "SpawnerStyle", "SpawnerStyleOverride"):
                try:
                    sub = getattr(spawner, attr)
                    if sub is not None:
                        targets.append(sub)
                except Exception:
                    pass
    except Exception:
        pass

    for target in targets:
        for field in (
            "bSpawnerEnabled", "bSpawnPointEnabled", "bEnabled", "bActive", "bCanSpawn",
            "bAllowSpawn", "bAllowRespawn", "bRespawnEnabled", "bInfinite", "bUnlimitedSpawns",
        ):
            if _safe_set_attr(target, field, True):
                changed += 1

        for field in (
            "Count", "SpawnCount", "NumActors", "NumActorsToSpawn", "NumToSpawn",
            "MaxActors", "MaxActorCount", "MaxSpawnCount", "MaxSpawns",
            "MaxAliveActors", "MaxActiveActors", "MaxSpawnedActors",
            "SpawnLimit", "ActorLimit", "PopulationLimit", "DesiredPopulation",
            "WaveCount", "WaveSize", "InitialSpawnCount",
        ):
            if _safe_set_attr(target, field, desired):
                changed += 1

        changed += _overdrive_spawn_style_object(target, desired)

    # Public enable methods.
    for fn_name, args in (
        ("SetSpawnerEnabled", (True,)),
        ("SetSpawnPointEnabled", (True,)),
        ("SetActive", (True,)),
        ("Activate", (True,)),
    ):
        try:
            getattr(comp, fn_name)(*args)
            changed += 1
        except TypeError:
            try:
                getattr(comp, fn_name)()
                changed += 1
            except Exception:
                pass
        except Exception:
            pass

    changed += _construct_extra_spawn_points_for_component(comp, desired)

    _log_info(f"spawner style overdrive multiplier={desired} changed={changed} comp={comp}")
    return changed

def _spawnai_fresh_spawner_direct(
    actor_def: str,
    *,
    distance: float,
    count: int = 1,
    spacing: float = 125.0,
    extra_loads: Sequence[str] = (),
    poll_timeout: float | None = None,
    coop_safe: bool = False,
    single_spawn: bool = False,
) -> Optional[Any]:
    """Spawn an actor-def through a throwaway OakSpawner placed in front of the player.

    v16 intentionally mirrors the proven console path:
      load package(s) -> build FGbxDefPtr shell -> spawn OakSpawner from class ->
      PushActorDef(..., True) -> ResetSpawner(True).

    Important: a console-spawned OakSpawner is not a fully-authored map spawner.
    BL4/Oak keeps its real spawn-row table in native SpawnerStyleDef data that is
    not rebuildable from Python. This path is therefore a reliable disposable
    one-spawn helper, not a true unlimited population spawner. Diagnostics are
    logged so we can see when a duplicate collapses to total=1 or 0.
    """
    _, pawn, world, gs = _spawn_context()
    if pawn is None or world is None or gs is None:
        return None

    actor_def = str(actor_def or "").strip()
    if not actor_def:
        return None

    cache_key = _alias_key(actor_def)
    cached_def = _ACTOR_DEF_CACHE.get(cache_key)
    if cached_def is not None:
        _log_info(
            f"oak_spawnai using session actor-def cache for {actor_def!r}: "
            f"{_actor_def_name(cached_def)} (source={_ACTOR_DEF_CACHE_SOURCE.get(cache_key, '<unknown>')})"
        )

    # Resolve the real GbxActorDef with a few load/settle passes. Async package
    # streaming means the first find_object often misses; retrying helps manual
    # console spawns. Mob spawner / coop paths use coop_safe=True for lean passes.
    populated = False
    try:
        game_state = getattr(world, "GameState", None)
        players = getattr(game_state, "PlayerArray", None) if game_state is not None else None
        populated = len([p for p in list(players or ())[:16] if p is not None]) > 1
    except Exception:
        populated = False

    resolved_def: Optional[Any] = cached_def if cached_def is not None else None
    async_mode = poll_timeout is not None and float(poll_timeout) <= 0.0
    if async_mode:
        _overdrive_spawn_manager_if_needed(world)
    # Async callers (poll_timeout=0): fire FGbxDefPtr shell immediately — package
    # probing and world scans block the game thread ~3s+ even when every path fails.
    if cached_def is None:
        if async_mode:
            # No find_all / load_package on click — only cache + find_object on
            # packages already warmed on a deferred PlayerTick pass.
            resolved_def = _spawnai_resolve_from_loaded_packages_only(actor_def, extra_loads)
            if resolved_def is None:
                _queue_async_actor_package_warm(actor_def, extra_loads)
        elif coop_safe and populated:
            resolve_attempts = 1
            resolve_sleep = 0.05
        elif coop_safe or single_spawn:
            resolve_attempts = 2
            resolve_sleep = 0.02 if single_spawn else 0.05
        else:
            resolve_attempts = 3
            resolve_sleep = 0.2
        if not async_mode:
            for attempt in range(resolve_attempts):
                _spawnai_load_packages(
                    actor_def,
                    extra_loads,
                    lean=bool(coop_safe or single_spawn),
                    max_packages=3 if (coop_safe or single_spawn) else 8,
                )
                resolved_def = _spawnai_resolve_real_actor_def(actor_def, extra_loads)
                if resolved_def is not None:
                    _log_info(f"oak_spawnai resolved real def for {actor_def!r} on pass {attempt + 1}: {_actor_def_name(resolved_def)}")
                    break
                if resolve_sleep > 0.0 and attempt + 1 < resolve_attempts:
                    time.sleep(resolve_sleep)
    if resolved_def is None:
        # Always fall through to FGbxDefPtr synthetic shells. Refusing them under
        # coop_safe broke BMS/Echo4 for every Char_*/IO_* that was not already
        # streamed (ULM: "Oak fast spawn: … may still stream in").
        shell_msg = (
            f"oak_spawnai could not resolve a real GbxActorDef for {actor_def!r} from guessed packages; "
            f"falling back to an FGbxDefPtr shell"
            f"{' (populated lobby)' if populated else ''}. "
            f"If nothing spawns, encounter it once then oak_cache {actor_def}."
        )
        if async_mode:
            _log_info(f"oak_spawnai async fast-fire {actor_def!r} (shell, detect on later frames)")
        else:
            _log_warn(shell_msg)

    # Prefer nearby enabled real spawners only as a class/template source. Do not
    # PushActorDef into real map spawners: testing showed it destroys their native
    # spawn rows and GetNumTotalActors collapses to zero.
    candidates: List[Any] = []
    if not coop_safe and not single_spawn:
        try:
            candidates = [
                o for o in find_all("OakSpawner", False)
                if "default__" not in str(o).lower() and "/script/" not in str(o).lower()
            ]
        except TypeError:
            candidates = [
                o for o in find_all("OakSpawner")
                if "default__" not in str(o).lower() and "/script/" not in str(o).lower()
            ]
        except Exception as exc:
            _log_warn(f"find_all('OakSpawner') failed for oak_spawnai direct path: {exc}")
            candidates = []

    def _score_spawner(sp: Any) -> Tuple[int, float]:
        total = 0
        try:
            total = int(sp.GetSpawnerComponent().GetNumTotalActors(0))
        except Exception:
            pass
        try:
            pl = pawn.K2_GetActorLocation()
            sl = sp.K2_GetActorLocation()
            dist = _distance_sq(pl, sl)
        except Exception:
            dist = 999999999999.0
        # Sort descending by map-spawner total, ascending by distance.
        return total, -dist

    # base is only used as a source of the OakSpawner Class; when no live spawner
    # is loaded we spawn one straight from find_class("OakSpawner") instead of
    # hard-failing with "move near a spawner first".
    base: Optional[Any] = None
    if candidates:
        candidates.sort(key=_score_spawner, reverse=True)
        base = candidates[0]
        _log_info(
            f"oak_spawnai thin-air source={base} source_counts="
            f"{_spawner_counts(base.GetSpawnerComponent()) if hasattr(base, 'GetSpawnerComponent') else None}"
        )
    else:
        if async_mode and _THIN_AIR_SPAWNER_TEMPLATE is not None:
            _log_info("oak_spawnai thin-air: duplicating from prewarmed OakSpawner template.")
        else:
            _log_info("oak_spawnai thin-air: no live OakSpawner nearby; building one from the OakSpawner class.")

    first_actor: Optional[Any] = None
    total_alive = 0
    total = max(1, int(count))

    for idx in range(total):
        if async_mode:
            d = (
                resolved_def
                or _spawnai_resolve_from_loaded_packages_only(actor_def, extra_loads)
                or _make_actor_def_shell(actor_def)
            )
        else:
            d = resolved_def or _spawnai_resolve_real_actor_def(actor_def, extra_loads) or _make_actor_def_shell(actor_def)
        transform = _spawn_transform_for_index(
            pawn,
            index=idx,
            count=total,
            distance=distance,
            spacing=spacing,
            z_offset=0.0,
            scale=1.0,
        )
        scan_loc = transform.Translation
        world_before = set() if async_mode else _world_actor_snapshot()

        cls = None
        if base is not None:
            try:
                cls = base.Class
            except Exception:
                cls = None
        if cls is None:
            try:
                cls = find_class("OakSpawner")
            except Exception as exc:
                _log_error(f"OakSpawner class lookup failed: {exc}")
                return first_actor

        spawner, from_template = _spawn_thin_air_spawner_for_fire(
            gs, world, cls, transform, async_mode=async_mode
        )
        if spawner is None:
            continue
        try:
            comp = spawner.GetSpawnerComponent()
        except Exception as exc:
            _log_warn(f"oak_spawnai direct path: GetSpawnerComponent failed on {spawner}: {exc}")
            continue

        # Best-effort prep. The important proven bits are PushActorDef(..., True)
        # and ResetSpawner(True); do not use False here because it clears rows on
        # real spawners and can under-initialize duplicates.
        if async_mode:
            _overdrive_spawner_component_fast(comp)
        elif single_spawn and int(count) <= 1:
            for fn_name, args in (("SetSpawnerEnabled", (True,)), ("SetSpawnPointEnabled", (True,))):
                try:
                    getattr(comp, fn_name)(*args)
                except Exception:
                    pass
        else:
            _overdrive_spawner_component(comp, max(1, int(count)))
            try:
                comp.SetSpawnerEnabled(True)
            except Exception:
                pass
            try:
                comp.SetSpawnPointEnabled(True)
            except Exception:
                pass
        try:
            comp.PushActorDef("SSP", d, True)
        except Exception as exc:
            _log_error(f"oak_spawnai thin-air PushActorDef failed for {actor_def!r} using {d}: {exc}")
            continue
        try:
            comp.ResetSpawner(True)
        except TypeError:
            try:
                comp.ResetSpawner()
            except Exception as exc:
                _log_warn(f"ResetSpawner failed on {comp}: {exc}")
        except Exception as exc:
            _log_warn(f"ResetSpawner failed on {comp}: {exc}")

        resolved = bool(getattr(d, "_experimental_instance", None))
        # Poll briefly — long blocking waits freeze hosts and drop remote clients.
        # World-delta detection below still catches slow-streaming bosses.
        if poll_timeout is None:
            if coop_safe:
                poll_timeout = _spawnai_poll_timeout(actor_def=actor_def, resolved=resolved, coop_safe=True)
            elif single_spawn:
                poll_timeout = 1.0 if _is_large_boss_like(actor_def) else 0.55
            else:
                poll_timeout = _spawnai_poll_timeout(actor_def=actor_def, resolved=resolved, coop_safe=False)
        # Explicit 0 = skip poll (async callers). Tiny positive timeouts still poll.
        if float(poll_timeout) <= 0.0:
            actors = []
        else:
            actors = _poll_spawner_for_alive_actors(comp, timeout=poll_timeout, interval=0.08 if coop_safe else 0.12)
        if not actors and float(poll_timeout) > 0.0:
            actors = _find_new_world_actors_near(
                world_before,
                scan_loc,
                radius=max(2000.0, float(spacing) * 3.0),
                expected_name=actor_def,
            )
            if actors:
                _log_info(f"world-delta detected {len(actors)} spawned actor(s) for {actor_def}: {actors}")

        if async_mode:
            _log_info(
                f"oak_spawnai async fired {actor_def!r} spawner={spawner} "
                f"from_template={from_template}"
            )
        else:
            alive_count, spawned_count, dead_count, total_count = _spawner_counts(comp)
            _log_info(
                f"oak_spawnai thin-air actor_def={actor_def} resolved={resolved} "
                f"poll={poll_timeout:g}s spawner={spawner} loc={spawner.K2_GetActorLocation()} "
                f"counts=(alive={alive_count}, spawned={spawned_count}, dead={dead_count}, total={total_count}) "
                f"actors={actors}"
            )
        for actor in actors:
            _SPAWNED.append(DeployedActor(label=actor_def, source=spawner, actor=actor, actor_key=_actor_key(actor), class_name=_class_name(actor)))
            _cache_actor_def_from_spawned_actor(actor_def, actor)
            if first_actor is None:
                first_actor = actor
            total_alive += 1

    if total_alive <= 0 and not async_mode:
        _log_warn(
            f"oak_spawnai thin-air queued {actor_def!r}, but no alive actors were returned. "
            "This usually means the actor package was not enough to resolve the FGbxDefPtr or the native spawner rows collapsed."
        )
    return first_actor



def _safe_component_field_dump(comp: Any, needles: Sequence[str]) -> List[Tuple[str, str, Any]]:
    """Return guarded component fields matching needles without tripping bad property wrappers."""
    out: List[Tuple[str, str, Any]] = []
    lowered = tuple(n.lower() for n in needles)
    for name in dir(comp):
        if lowered and not any(n in name.lower() for n in lowered):
            continue
        try:
            value = getattr(comp, name)
            if callable(value):
                continue
            out.append((name, type(value).__name__, value))
        except Exception as exc:
            out.append((name, "ERR", str(exc)))
    return out


@command("oak_spawnerdiag", description="After enabling, assign «Open / Close BL4 Oak Spawner Hooked Widget» under Mods → Keybinds. Log OakSpawner/OakSpawnerComponent diagnostics, including duplicate-spawner row collapse.")
def _cmd_spawnerdiag(args: argparse.Namespace) -> None:
    limit = max(1, int(getattr(args, "limit", 20)))
    try:
        spawners = [o for o in find_all("OakSpawner", False) if "default__" not in str(o).lower() and "/script/" not in str(o).lower()]
    except TypeError:
        spawners = [o for o in find_all("OakSpawner") if "default__" not in str(o).lower() and "/script/" not in str(o).lower()]
    except Exception as exc:
        _log_error(f"oak_spawnerdiag find_all OakSpawner failed: {exc}")
        return

    rows: List[Tuple[int, Tuple[int, int, int, int], bool, bool, Any]] = []
    for idx, sp in enumerate(spawners):
        try:
            comp = sp.GetSpawnerComponent()
            counts = _spawner_counts(comp)
            enabled = bool(comp.IsSpawnerEnabled())
            active = bool(comp.IsActive())
        except Exception:
            continue
        rows.append((idx, counts, enabled, active, sp))
    rows.sort(key=lambda item: item[1][3], reverse=True)
    _log_info(f"oak_spawnerdiag loaded_spawners={len(spawners)} showing={min(limit, len(rows))}")
    for idx, counts, enabled, active, sp in rows[:limit]:
        _log_info(f"  idx={idx} counts(alive,spawned,dead,total)={counts} enabled={enabled} active={active} spawner={sp}")

    if not rows:
        return

    # Create one duplicate and compare totals. This is intentionally diagnostic
    # and proves whether the build can synthesize a full native row table from a
    # spawned OakSpawner actor.
    _, pawn, world, gs = _spawn_context()
    if pawn is None or world is None or gs is None:
        return
    src = rows[0][4]
    transform = _spawn_transform_for_index(pawn, index=0, count=1, distance=float(getattr(args, "distance", _DEFAULT_DISTANCE)), spacing=0.0, z_offset=0.0, scale=1.0)
    dup = _spawn_actor_deferred(gs, world, src.Class, transform, class_name="OakSpawner", source=None, collision_handling=1)
    if dup is None:
        return
    try:
        src_comp = src.GetSpawnerComponent()
        dup_comp = dup.GetSpawnerComponent()
        _log_info(f"  source counts={_spawner_counts(src_comp)} fields={_safe_component_field_dump(src_comp, ('SpawnPoint', 'SpawnerStyle', 'SpawnDetails'))[:12]}")
        _log_info(f"  duplicate counts={_spawner_counts(dup_comp)} fields={_safe_component_field_dump(dup_comp, ('SpawnPoint', 'SpawnerStyle', 'SpawnDetails'))[:12]}")
    except Exception as exc:
        _log_warn(f"oak_spawnerdiag duplicate compare failed: {exc}")


_cmd_spawnerdiag.add_argument("--limit", type=int, default=20, help="How many loaded OakSpawners to log. Default 20.")
_cmd_spawnerdiag.add_argument("--distance", type=float, default=_DEFAULT_DISTANCE, help="Where to place the diagnostic duplicate. Default 350.")




@command("oak_cache", description="Cache a live actor's GbxActorDef for later AI-capable oak_spawnai. Usage: oak_cache mancubus [--class OakCharacter]")
def _cmd_cache(args: argparse.Namespace) -> None:
    name = str(getattr(args, "name", "") or "").strip()
    if not name:
        _log_error("Usage: oak_cache <name> [--class ClassName]")
        return
    class_override = getattr(args, "class_name", None)
    matches = _candidate_actor_def_sources(name, class_override=class_override)
    if not matches:
        _log_error(f"No live actor-def source found for {name!r}. Move near the actor first, then run oak_cache {name}.")
        return
    limit = max(1, int(getattr(args, "limit", 10)))
    _log_info(f"actor-def cache candidates for {name!r}: {min(len(matches), limit)}/{len(matches)}")
    for idx, obj in enumerate(matches[:limit]):
        try:
            def_name = _actor_def_name(obj.GbxActorData.GbxActorDef)
        except Exception:
            def_name = "<unreadable>"
        _log_info(f"  {idx:02d}: def={def_name} obj={obj}")
    pick = max(0, int(getattr(args, "index", 0)))
    if pick >= len(matches):
        _log_error(f"--index {pick} out of range; only {len(matches)} candidates.")
        return
    _cache_actor_def(name, matches[pick])


_cmd_cache.add_argument("name", help="Cache key / search term, e.g. mancubus. Later use oak_spawnai mancubus.")
_cmd_cache.add_argument("--class", dest="class_name", default=None, help="Optional class to search first, e.g. OakCharacter.")
_cmd_cache.add_argument("--index", type=int, default=0, help="Candidate index to cache. Default 0.")
_cmd_cache.add_argument("--limit", type=int, default=10, help="How many candidates to log. Default 10.")


@command("oak_cache_status", description="List runtime actor-def cache entries created by oak_cache.")
def _cmd_cache_status(_: argparse.Namespace) -> None:
    if not _ACTOR_DEF_CACHE:
        _log_info("actor-def cache is empty. Use oak_cache <name> while near a source actor.")
        return
    for key, def_ptr in _ACTOR_DEF_CACHE.items():
        _log_info(f"cache {key!r}: def={_actor_def_name(def_ptr)} source={_ACTOR_DEF_CACHE_SOURCE.get(key, '<unknown>')}")





@command("oak_spawnoverdrive", description="Best-effort BL3-style multiplier patch on loaded OakSpawnerComponents.")
def _cmd_spawnoverdrive(args: Namespace) -> None:
    mult = max(1, int(getattr(args, "multiplier", 10)))
    changed_total = 0
    count = 0
    for cls_name in ("OakSpawnerComponent", "SpawnerComponent"):
        try:
            comps = list(find_all(cls_name, False))
        except TypeError:
            try:
                comps = list(find_all(cls_name))
            except Exception:
                continue
        except Exception:
            continue
        for comp in comps:
            count += 1
            changed_total += _overdrive_spawner_component(comp, mult)
    _log_info(f"oak_spawnoverdrive multiplier={mult} components={count} changed_total={changed_total}")

_cmd_spawnoverdrive.add_argument("multiplier", nargs="?", default=10, type=int)

@command("oak_probe", description="Probe oak_spawnai load paths and report whether they expose a real GbxActorData.GbxActorDef.")
def _cmd_probeai(args: argparse.Namespace) -> None:
    name = str(getattr(args, "name", "") or "").strip()
    if not name:
        _log_error("Usage: oak_probe <actor-def-name> [--load /Game/...]")
        return
    _spawnai_probe(name, tuple(getattr(args, "load", ()) or ()))


_cmd_probeai.add_argument("name", help="Actor-def name to probe, e.g. Char_Robo_Totem_Base.")
_cmd_probeai.add_argument("--load", action="append", default=[], help="Extra package/object path to load/probe. Can be used more than once.")


@command("oak_spawnai", description="Spawn an actor def through a fresh OakSpawner. Supports cached defs and direct names like Char_CrazyEarl_Boss, Char_TargetDummy, Char_NPC_Hermes.")
def _cmd_spawnai(args: argparse.Namespace) -> None:
    name = str(getattr(args, "name", "") or "").strip()
    if not name:
        _log_error("Usage: oak_spawnai <actor-def-name>")
        return
    distance = float(getattr(args, "distance", _DEFAULT_DISTANCE))
    count = max(1, int(getattr(args, "count", 1)))
    spacing = float(getattr(args, "spacing", 125.0))
    extra_loads = tuple(getattr(args, "load", ()) or ())

    actor: Optional[Any] = None
    # Keep the old cache path for live/cached actors, unless explicitly skipped.
    if not bool(getattr(args, "direct_only", False)):
        actor = _spawn_cached_actor_def(name, distance=distance, count=count, spacing=spacing)
    if actor is None:
        actor = _spawnai_fresh_spawner_direct(name, distance=distance, count=count, spacing=spacing, extra_loads=extra_loads)
    if actor is None:
        _log_warn(f"oak_spawnai {name!r} did not return an actor immediately. If it queued/compiled assets, run it again or add --load /Game/.../Script_Asset.")
        return
    _log_info(f"oak_spawnai complete: {actor}")


def _add_spawnai_args(cmd: Any) -> None:
    cmd.add_argument("name", help="Actor-def name or cache key, e.g. Char_CrazyEarl_Boss, Char_TargetDummy, Char_NPC_Hermes, mancubus.")
    cmd.add_argument("--distance", type=float, default=_DEFAULT_DISTANCE, help="Spawn a fresh OakSpawner this far in front. Default 350.")
    cmd.add_argument("--count", type=int, default=1, help="Number of AI actors to request. Default 1.")
    cmd.add_argument("--spacing", type=float, default=125.0, help="Spacing between requested AI actors. Default 125.")
    cmd.add_argument("--load", action="append", default=[], help="Extra package to load before spawning. Can be used more than once, e.g. --load /Game/AI/NPC/_Unique/Hermes/Script_NPC_Hermes")
    cmd.add_argument("--direct-only", action="store_true", help="Skip old oak_cache path and use the fresh-spawner direct path only.")


_add_spawnai_args(_cmd_spawnai)


@command("oak_boss", description="Spawn a boss/enemy with large-boss tuning (900uu out, wide spacing, long settle). Usage: oak_boss crazyearl | Char_CrazyEarl_Boss")
def _cmd_boss(args: argparse.Namespace) -> None:
    name = str(getattr(args, "name", "") or "").strip()
    if not name:
        _log_error("Usage: oak_boss <boss-name-or-Char_def>")
        return
    resolved, suggestions = _resolve_actor_def_name(name)
    if resolved and resolved.strip().lower() != name.strip().lower():
        _log_info(f"oak_boss resolved {name!r} -> {resolved!r} (alternatives: {suggestions[:5]})")
        name = resolved
    distance = float(getattr(args, "distance", 900.0))
    count = max(1, int(getattr(args, "count", 1)))
    spacing = float(getattr(args, "spacing", 300.0))
    extra_loads = tuple(getattr(args, "load", ()) or ())
    coop_safe = bool(getattr(args, "coop_safe", False))
    actor: Optional[Any] = None
    if not bool(getattr(args, "direct_only", False)):
        actor = _spawn_cached_actor_def(name, distance=distance, count=count, spacing=spacing)
    if actor is None:
        actor = _spawnai_fresh_spawner_direct(
            name,
            distance=distance,
            count=count,
            spacing=spacing,
            extra_loads=extra_loads,
            coop_safe=coop_safe,
        )
    if actor is None and not bool(getattr(args, "coop_safe", False)):
        actor = _spawn_deployed_actor(
            name,
            class_override=getattr(args, "class_name", None),
            distance=distance,
            z_offset=0.0,
            scale=float(getattr(args, "scale", _DEFAULT_SCALE)),
            delay=float(getattr(args, "delay", _DEFAULT_DELAY)),
            enable=_split_states(getattr(args, "enable", None), _DEFAULT_ACTIVATE_ENABLE),
            disable=_split_states(getattr(args, "disable", None), _DEFAULT_ACTIVATE_DISABLE),
            generated_only=not bool(getattr(args, "include_non_generated", False)),
            activate=not bool(getattr(args, "no_activate", False)),
            count=count,
            spacing=spacing,
        )
    if actor is None:
        _log_warn(
            f"oak_boss {name!r} did not return an actor. Try oak_probe {name!r}, visit once then oak_cache {name!r}, "
            "or add --load /Game/.../Script_Asset."
        )
        return
    _log_info(f"oak_boss complete: {actor}")


_cmd_boss.add_argument("name", help="Loose boss name (crazyearl) or Char_ actor def.")
_cmd_boss.add_argument("--distance", type=float, default=900.0, help="Forward spawn distance. Default 900 for large bosses.")
_cmd_boss.add_argument("--count", type=int, default=1, help="Number of bosses to request. Default 1.")
_cmd_boss.add_argument("--spacing", type=float, default=300.0, help="Spacing between multiple spawns. Default 300.")
_cmd_boss.add_argument("--load", action="append", default=[], help="Extra package to load before spawning.")
_cmd_boss.add_argument("--coop-safe", action="store_true", help="Short non-blocking settle poll (recommended in multiplayer).")
_cmd_boss.add_argument("--class", dest="class_name", default=None, help="Override Unreal class.")
_cmd_boss.add_argument("--scale", type=float, default=_DEFAULT_SCALE, help="Uniform spawn scale. Default 1.")
_cmd_boss.add_argument("--delay", type=float, default=_DEFAULT_DELAY, help="Seconds before script-state activation. Default 1.")
_cmd_boss.add_argument("--enable", default=None, help="Comma-separated script states to enable.")
_cmd_boss.add_argument("--disable", default=None, help="Comma-separated script states to disable.")
_cmd_boss.add_argument("--no-activate", action="store_true", help="Spawn only; do not toggle ScriptData states.")
_cmd_boss.add_argument("--include-non-generated", action="store_true", help="Allow template actors without _Generated_ in the object name.")
_cmd_boss.add_argument("--direct-only", action="store_true", help="Skip session cache; use fresh-spawner path only.")


@command("oak_lostloot", description="Spawn and activate a Lost Loot machine in front of you.")
def _cmd_lostloot(args: argparse.Namespace) -> None:
    _spawn_from_args(args, "lostloot")


@command("oak_spawn", description="Spawn/duplicate a deployable or generic skeletal actor from a live template. Usage: oak_spawn lostloot|goldenchest|firmware|OakWeapon_2147480142 [--class ClassName]")
def _cmd_spawn(args: argparse.Namespace) -> None:
    _spawn_from_args(args)


def _add_spawn_args(cmd: Any, *, include_name: bool) -> None:
    if include_name:
        cmd.add_argument("name", help="Alias, substring, or exact live actor name, e.g. lostloot, golden, firmware, OakWeapon_2147480142.")
    cmd.add_argument("--class", dest="class_name", default=None, help="Override Unreal class, e.g. OakLostLootMachine.")
    cmd.add_argument("--distance", type=float, default=_DEFAULT_DISTANCE, help="Forward spawn distance. Default 350.")
    cmd.add_argument("--z-offset", type=float, default=_DEFAULT_Z_OFFSET, dest="z_offset", help="Vertical offset. Default -100.")
    cmd.add_argument("--scale", type=float, default=_DEFAULT_SCALE, help="Uniform spawn scale. Default 1.")
    cmd.add_argument("--delay", type=float, default=_DEFAULT_DELAY, help="Seconds before script-state activation. Default 1.")
    cmd.add_argument("--enable", default=None, help="Comma-separated script states to enable. Default Active,ActiveIdle_Anim.")
    cmd.add_argument("--disable", default=None, help="Comma-separated script states to disable. Default IsInUse,InUse_Anim,Dispensing_Anim.")
    cmd.add_argument("--no-activate", action="store_true", help="Spawn only; do not toggle ScriptData states.")
    cmd.add_argument("--include-non-generated", action="store_true", help="Allow template actors without _Generated_ in the object name.")
    cmd.add_argument("--count", type=int, default=1, help="Number of actors to spawn. Default 1.")
    cmd.add_argument("--spacing", type=float, default=125.0, help="Spacing between multiple spawned actors. Default 125.")


_add_spawn_args(_cmd_lostloot, include_name=False)
_add_spawn_args(_cmd_spawn, include_name=True)


@command("oak_targets", description="List live template actors matching an alias/class. Usage: oak_targets lostloot [--class OakLostLootMachine]")
def _cmd_targets(args: argparse.Namespace) -> None:
    name = str(getattr(args, "name", "") or "").strip()
    class_override = getattr(args, "class_name", None)
    generated_only = not bool(getattr(args, "include_non_generated", False))
    default_class, needles = _default_class_and_needles(name)
    class_name = class_override or default_class
    if class_name:
        matches2 = [(class_name, obj) for obj in _candidate_sources(class_name, needles, generated_only=generated_only)]
        if not matches2 and generated_only:
            _log_info("No _Generated_ matches in requested/default class; retrying non-generated search for visibility.")
            matches2 = [(class_name, obj) for obj in _candidate_sources(class_name, needles, generated_only=False)]
        if not matches2:
            _log_info("No matches in requested/default class; scanning common actor classes by keyword.")
            scan_classes = [class_name] + [c for c in _CLASS_SCAN_ORDER if c != class_name]
            matches2 = _candidate_sources_multi(scan_classes, needles, generated_only=generated_only)
            if not matches2 and generated_only:
                matches2 = _candidate_sources_multi(scan_classes, needles, generated_only=False)
    else:
        matches2 = _candidate_sources_multi(_CLASS_SCAN_ORDER, needles, generated_only=generated_only)
        if not matches2 and generated_only:
            _log_info("No _Generated_ matches; retrying non-generated keyword scan for visibility.")
            matches2 = _candidate_sources_multi(_CLASS_SCAN_ORDER, needles, generated_only=False)
    limit = max(1, int(getattr(args, "limit", 20)))
    class_label = class_name if class_name else "<keyword scan>"
    _log_info(f"targets name={name!r} class={class_label!r} needles={needles}: {min(len(matches2), limit)}/{len(matches2)}")
    for idx, (matched_class, obj) in enumerate(matches2[:limit]):
        _log_info(f"  {idx:02d}: class={matched_class} actor_class={_class_display_name(_source_class(obj, matched_class))} obj={obj}")


_cmd_targets.add_argument("name", help="Alias or substring to search, e.g. lostloot, golden, goldenchest, firmware.")
_cmd_targets.add_argument("--class", dest="class_name", default=None, help="Override Unreal class name.")
_cmd_targets.add_argument("--limit", type=int, default=20, help="Maximum matches to log.")
_cmd_targets.add_argument("--include-non-generated", action="store_true", help="Show templates without _Generated_ in the object name.")


@command("oak_barrellogo", description="Spawn pipe-separated barrel text. Example: oak_barrellogo WE HAVE BEEN|TRYING TO REACH YOU|ABOUT YOUR CARS EXTENDED WARRENTY")
def _cmd_barrellogo(args: argparse.Namespace) -> None:
    # Console supports either:
    #   oak_barrellogo WE HAVE BEEN|TRYING TO REACH YOU|ABOUT YOUR CARS EXTENDED WARRENTY
    #   oak_barrellogo --text WE HAVE BEEN|TRYING TO REACH YOU|ABOUT YOUR CARS EXTENDED WARRENTY
    # argparse splits on spaces, so join positional text_parts back together.
    text = str(getattr(args, "text", "") or "").strip()
    parts = getattr(args, "text_parts", None) or []
    if not text and parts:
        text = " ".join(str(part) for part in parts).strip()
    if not text:
        text = _logo_text_from_options()
    _spawn_barrel_logo(
        barrel_name=str(getattr(args, "actor", None) or getattr(args, "barrel", None) or _logo_actor_from_options()),
        text=text,
        distance=(float(getattr(args, "distance")) if getattr(args, "distance", None) is not None else _logo_distance_from_options()),
        height=float(getattr(args, "height", 750.0)),
        spacing=float(getattr(args, "spacing", 70.0)),
        scale=float(getattr(args, "scale", 0.45)),
        generated_only=not bool(getattr(args, "include_non_generated", False)),
        max_props=int(getattr(args, "max_props", 0) or 0),
    )


_cmd_barrellogo.add_argument("text_parts", nargs="*", help="Optional text to render. Use | for rows, e.g. WE HAVE BEEN|TRYING TO REACH YOU|ABOUT YOUR CARS EXTENDED WARRENTY.")
_cmd_barrellogo.add_argument("--actor", default=None, help="Template keyword to use for each pixel/letter block. Overrides mod-menu Logo Actor Override. Example: --actor goldenchest")
_cmd_barrellogo.add_argument("--barrel", dest="actor", default=None, help="Backward-compatible alias for --actor.")
_cmd_barrellogo.add_argument("--text", default="", help="Text to render. Use | to force line breaks. If omitted, keybind/mod-menu rows are used.")
_cmd_barrellogo.add_argument("--distance", type=float, default=None, help="Forward distance from player. If omitted, uses the permanent mod-menu Barrel Logo Distance option.")
_cmd_barrellogo.add_argument("--height", type=float, default=750.0, help="Height above player.")
_cmd_barrellogo.add_argument("--spacing", type=float, default=70.0, help="Barrel spacing in Unreal units.")
_cmd_barrellogo.add_argument("--scale", type=float, default=0.45, help="Uniform barrel scale.")
_cmd_barrellogo.add_argument("--include-non-generated", action="store_true", help="Allow non-_Generated_ barrel templates.")
_cmd_barrellogo.add_argument("--max-props", type=int, default=0, help="Cap spawned props (thin letter pixels). 0 = uncapped.")


@keybind("Oak Spawn Barrel Logo")
def _keybind_barrellogo() -> None:
    _spawn_barrel_logo(text=_logo_text_from_options(), distance=_logo_distance_from_options(), barrel_name=_logo_actor_from_options())




@command("oak_logo_options", description="Log barrel logo mod-menu option status and current keybind rows.")
def _cmd_logo_options(_: argparse.Namespace) -> None:
    _log_info(f"row1_option={_LOGO_ROW1_OPTION} value={_option_text_value(_LOGO_ROW1_OPTION, _LOGO_ROW1_DEFAULT)!r}")
    _log_info(f"row2_option={_LOGO_ROW2_OPTION} value={_option_text_value(_LOGO_ROW2_OPTION, _LOGO_ROW2_DEFAULT)!r}")
    _log_info(f"row3_option={_LOGO_ROW3_OPTION} value={_option_text_value(_LOGO_ROW3_OPTION, _LOGO_ROW3_DEFAULT)!r}")
    _log_info(f"actor={_option_text_value(_LOGO_ACTOR_OPTION, _LOGO_ACTOR_DEFAULT)!r}")
    _log_info(f"distance={_option_float_value(_LOGO_DISTANCE_OPTION, _LOGO_DISTANCE_DEFAULT)}")
    _log_info(f"combined={_logo_text_from_options()!r}")
    _log_info("Edit via mods → BL4 Oak Spawner → Logo Text Row N, or: oak_logo_set row1 YOUR TEXT")


@command(
    "oak_logo_set",
    description="Set barrel logo row/actor/distance from console (works when mods menu text edit fails).",
)
def _cmd_logo_set(args: argparse.Namespace) -> None:
    """
    Usage:
      oak_logo_set row1 WE HAVE BEEN
      oak_logo_set row2 TRYING TO REACH YOU
      oak_logo_set row3 ABOUT YOUR CARS
      oak_logo_set actor goldenchest
      oak_logo_set distance 1600
      oak_logo_set show
    """
    which = str(getattr(args, "which", "") or "").strip().lower()
    rest = getattr(args, "rest", None) or []
    value = " ".join(str(p) for p in rest).strip()
    if which in ("", "help", "?"):
        _log_info("oak_logo_set row1|row2|row3|actor|distance <value>  |  oak_logo_set show")
        return
    if which in ("show", "status", "list"):
        _cmd_logo_options(args)
        return

    key_map = {
        "row1": (_LOGO_ROW1_OPTION, "oak_logo_row_1"),
        "row_1": (_LOGO_ROW1_OPTION, "oak_logo_row_1"),
        "1": (_LOGO_ROW1_OPTION, "oak_logo_row_1"),
        "row2": (_LOGO_ROW2_OPTION, "oak_logo_row_2"),
        "row_2": (_LOGO_ROW2_OPTION, "oak_logo_row_2"),
        "2": (_LOGO_ROW2_OPTION, "oak_logo_row_2"),
        "row3": (_LOGO_ROW3_OPTION, "oak_logo_row_3"),
        "row_3": (_LOGO_ROW3_OPTION, "oak_logo_row_3"),
        "3": (_LOGO_ROW3_OPTION, "oak_logo_row_3"),
        "actor": (_LOGO_ACTOR_OPTION, "oak_logo_actor"),
        "barrel": (_LOGO_ACTOR_OPTION, "oak_logo_actor"),
    }
    if which in ("distance", "dist", "d"):
        if not value:
            _log_warn("oak_logo_set distance <number>")
            return
        try:
            dist = float(value)
        except ValueError:
            _log_warn(f"Not a number: {value!r}")
            return
        if _LOGO_DISTANCE_OPTION is not None:
            try:
                _LOGO_DISTANCE_OPTION.value = dist
            except Exception as exc:
                _log_warn(f"distance option set failed: {exc}")
        _persist_logo_options()
        _log_info(f"Logo distance set to {dist}")
        return

    hit = key_map.get(which)
    if hit is None:
        _log_warn(f"Unknown field {which!r}. Use row1|row2|row3|actor|distance.")
        return
    option, _key = hit
    if not value:
        _log_warn(f"oak_logo_set {which} <text>")
        return
    if which in ("actor", "barrel"):
        text = value.strip().lower()
    else:
        text = _normalize_logo_row_text(value)
    if option is None:
        _log_warn("Logo text option unavailable in this SDK build — writing settings JSON only.")
    else:
        try:
            option.value = text
        except Exception as exc:
            _log_warn(f"option.value set failed: {exc}")
    _persist_logo_options()
    _log_info(f"Logo {which} = {text!r} (saved). Spawn with NumPad logo keybind or oak_barrellogo.")


_cmd_logo_set.add_argument("which", nargs="?", default="help", help="row1|row2|row3|actor|distance|show")
_cmd_logo_set.add_argument("rest", nargs="*", help="New value (spaces allowed).")


@command("oak_status", description="Log actors spawned by BL4 Oak Spawner.")
def _cmd_status(_: argparse.Namespace) -> None:
    _log_info(f"spawned={len(_SPAWNED)}")
    for idx, item in enumerate(_SPAWNED):
        _log_info(f"  {idx:02d}: label={item.label!r} actor={item.actor} source={item.source}")


def _safe_actor_key(actor: Any) -> str:
    try:
        return str(actor)
    except Exception:
        return ""


def _actor_key(actor: Any) -> str:
    return _safe_actor_key(actor)


def _class_name(actor: Any) -> str:
    try:
        cls = getattr(actor, "Class", None)
        name = getattr(cls, "Name", None)
        if name:
            return str(name)
        text = str(cls)
        if "'" in text:
            return text.split("'")[-2].rsplit(".", 1)[-1]
        return text.rsplit(".", 1)[-1].strip("'> ")
    except Exception:
        return ""


def _find_live_spawned_actor(item: DeployedActor) -> Optional[Any]:
    """Return the current live UObject for a tracked actor, or None if it already died.

    Exploded barrels often leave stale Python wrappers behind. Calling K2_DestroyActor
    on those stale wrappers can crash the game, so clear only destroys actors that
    can still be found in the live object table.
    """
    key = item.actor_key or _safe_actor_key(item.actor)
    if not key:
        return None

    class_names: List[str] = []
    if item.class_name:
        class_names.append(item.class_name)
    try:
        source_cls = _class_name(item.source)
        if source_cls and source_cls not in class_names:
            class_names.append(source_cls)
    except Exception:
        pass
    if not class_names:
        class_names.extend(("OakInteractiveObject", "OakLostLootMachine", "Actor"))

    for class_name in class_names:
        try:
            candidates = list(find_all(class_name, False))
        except Exception:
            continue
        for actor in candidates:
            if _safe_actor_key(actor) == key:
                return actor
    return None


def _clear_spawned_actors() -> int:
    destroyed = 0
    skipped_dead = 0
    survivors: List[DeployedActor] = []
    for item in list(_SPAWNED):
        actor = _find_live_spawned_actor(item)
        if actor is None:
            skipped_dead += 1
            continue
        try:
            if bool(getattr(actor, "bActorIsBeingDestroyed", False)):
                skipped_dead += 1
                continue
        except Exception:
            pass
        try:
            actor.K2_DestroyActor()
            destroyed += 1
        except Exception as exc:
            survivors.append(item)
            _log_warn(f"clear skipped live actor {item.actor_key or item.actor}: {exc}")
    _SPAWNED.clear()
    _SPAWNED.extend(survivors)
    if skipped_dead:
        _log_info(f"clear ignored {skipped_dead} actor references that were already gone/exploded.")
    return destroyed


@command("oak_clear", description="Destroy actors spawned by BL4 Oak Spawner.")
def _cmd_clear(_: argparse.Namespace) -> None:
    destroyed = _clear_spawned_actors()
    _log_info(f"cleared {destroyed} spawned actors.")


@keybind("Oak Clear Spawned Actors")
def _keybind_clear_spawned() -> None:
    destroyed = _clear_spawned_actors()
    _log_info(f"cleared {destroyed} spawned actors from keybind.")


@command("oak_activate_last", description="Rerun the broad activation pass on the most recently spawned BL4 Oak Spawner actor.")
def _cmd_activate_last(args: argparse.Namespace) -> None:
    if not _SPAWNED:
        _log_warn("No spawned actors to activate.")
        return
    item = _SPAWNED[-1]
    key = _alias_key(item.label)
    enable = _unique_states(
        _split_states(getattr(args, "enable", None), _DEFAULT_ACTIVATE_ENABLE),
        _PRESET_ENABLE_STATES.get(key, ()),
        _GENERIC_ENABLE_STATES,
    )
    disable = _unique_states(
        _split_states(getattr(args, "disable", None), _DEFAULT_ACTIVATE_DISABLE),
        _PRESET_DISABLE_STATES.get(key, ()),
        _GENERIC_DISABLE_STATES,
    )
    _log_info(f"Re-activating last spawned actor label={item.label!r}: {item.actor}")
    _set_script_states(item.actor, enable, disable, debug=True)


_cmd_activate_last.add_argument("--enable", default=None, help="Comma-separated script states to enable first.")
_cmd_activate_last.add_argument("--disable", default=None, help="Comma-separated script states to disable first.")


@command("oak_scriptdump", description="Dump useful script/method names for the most recently spawned BL4 Oak Spawner actor.")
def _cmd_scriptdump(_: argparse.Namespace) -> None:
    if not _SPAWNED:
        _log_warn("No spawned actors to inspect.")
        return
    item = _SPAWNED[-1]
    _log_info(f"script dump for label={item.label!r} actor={item.actor}")
    for inst in _script_instances(item.actor):
        _script_debug(inst, limit=200)


# Embedded engine — mod registration stripped (Squ1ggsBoostingTools bundles this).
