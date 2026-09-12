"""Custom BLImGui panel for Squ1ggs's Boosting Tools."""
from __future__ import annotations

from typing import Any, Callable
import re
import json
import os
import time
import threading
import pkgutil
import urllib.request
import urllib.parse
import html
from pathlib import Path

import blimgui as _blimgui
try:
    from blimgui import cyber as _cyber
except Exception:  # fall back cleanly if an older BLImGui is installed
    _cyber = None
from mods_base import command, keybind, get_pc
import unrealsdk
from unrealsdk import logging

from .golden_chest_keybinds import _close_golden_chest, _open_golden_chest
from .party_helpers import (
    _kick_party_player_by_index,
    _list_party_players as _scan_party_players,
    _gbc_find_pc_for_player_state,
    _gbc_normalize_name,
    _gbc_session_world_and_gamestate,
    _gbc_is_listen_host_world,
)
from .player_economy import _do_boost_maxsdu, _do_give_currency, _do_give_experience, _do_set_currency_absolute
from .serial_rewards import (
    _do_give_serial,
    _do_give_serial_to_player_indices,
    _all_party_player_indices_for_serial_delivery,
    _expand_serial_token,
    _split_base85_blob,
    _resolve_give_serial_strings,
    _serial_delivery_chunks,
    _serial_delivery_chunk_stats,
    serial_delivery_progress,
    serial_delivery_status,
    serial_delivery_timing,
    set_serial_delivery_timing,
    open_all_party_reward_packages,
)
from . import mobility_runtime as _mobility_runtime
from . import uvhm_runtime as _uvhm_runtime
from . import challenge_bulk_runtime as _challenge_bulk_runtime
from . import mobility_ui as _mobility_ui
from . import tuning_ui as _tuning_ui
from . import rarity_weights as _rarity_weights
from . import serial_store as _serial_store_mod
from . import mob_spawner_ui as _mob_spawner_ui
from . import world_spawn_ui as _world_spawn_ui
from . import encounter_ui as _encounter_ui
from .squ1ggs_theme import (
    ACCENT_DANGER,
    ACCENT_INFO,
    ACCENT_MUTED,
    ACCENT_PRIMARY,
    ACCENT_SECONDARY,
    ACCENT_SUCCESS,
    ACCENT_VIOLET,
    ACCENT_WARN,
    BRAND_TAGLINE,
    BTN_CASH,
    BTN_DANGER,
    BTN_ERIDIUM,
    BTN_GIVE,
    BTN_HIGHLIGHT,
    BTN_MAX_ALL,
    BTN_NEUTRAL,
    BTN_SPEC,
    BTN_XP,
    PANEL_VERSION,
    TAB_ACCENTS,
    TAB_ROW_SPLIT,
    TAB_SHORT_LABELS,
    begin_card as _theme_begin_card,
    card_accent,
    draw_brand_banner,
    end_card as _theme_end_card,
    metric as _theme_metric,
    pop_window_style,
    push_squ1ggs_window_style,
    resolve_accent,
    section_header as _theme_section_header,
)
from .serial_converter import human_to_serial as _human_to_serial, serial_to_human as _serial_to_human
from .dev_tools import activate_devperk, clamp_debug_speed, clear_ammo_regen_sticky, clear_weapons_restricted_sticky, copy_debug_cam_location, destroy_looked_at_actor, damage_looked_at_actor, devperk_button_label, devperk_label, devperk_toggle_state, enable_debug_cam, force_disable_debug_cam, get_debug_cam_speed, inspect_looked_at_actor, set_ammo_regen_rate, set_ammo_regen_sticky, set_debug_cam_speed, set_freecam_distance, set_vehicle_actions_locked, set_weapons_restricted, set_weapons_restricted_sticky, toggle_debug_cam, toggle_weapons_restricted, teleport_pawn_to_debug_cam
from .item_pool_spawning import (
    DEFAULT_ITEM_LEVEL as _ITEMPOOL_DEFAULT_LEVEL,
    bulk_spawn_active,
    bulk_spawn_status_line,
    filter_item_pools,
    grant_all_filtered_item_pools_rewards,
    item_pool_categories,
    load_item_pools,
    queue_all_filtered_item_pools,
    cancel_bulk_spawn_batch,
    spawn_item_pool,
)
from .travel import canonical_travel_map_name, filter_travel_maps, filter_travel_stations, travel_to_map, travel_to_preset, travel_to_station
from .inventory_capacity import (
    _DEFAULT_BACKPACK_SIZE,
    _DEFAULT_BANK_SIZE,
    auto_apply_inventory_sizes_if_needed,
    clamp_container_size,
    load_inventory_settings,
    save_inventory_settings,
    save_extra_settings,
    set_inventory_sizes_for_all_party,
    set_inventory_sizes_for_party_index,
)


def _canonicalize_travel_map_values(values) -> set[str]:
    out: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if text:
            out.add(canonical_travel_map_name(text))
    return out


def _canonicalize_travel_map_descriptions(raw) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        canon = canonical_travel_map_name(str(key or "").strip())
        text = str(value or "").strip()
        if canon and text and canon not in out:
            out[canon] = text
    return out

WINDOW_TITLE = "Squ1ggs's Boosting Tools"
_last_action_status: str = ""
_log_lines: list[str] = []
_selected_player_index: int = 0
_selected_player_delivery_name: str = ""
_serial_text: str = ""
_serial_tools_input: str = ""
_serial_tools_serialized: str = ""
_serial_tools_deserialized: str = ""
_serial_tools_parts_breakdown: str = ""
_serial_tools_status: str = "Paste a @U serial or deserialized serial text above."
_serial_store_entries: list[dict[str, str]] = []
_serial_store_selected_ids: set[str] = set()
_serial_store_active_id: str = ""
_serial_store_name: str = ""
_serial_store_group: str = "Default"
_serial_store_serial: str = ""
_serial_store_group_filter_index: int = 0
_serial_store_player_index: int = 0
_serial_store_status: str = "Add named @U/deserialized serials, group them, multi-select, then deliver to the selected target."
_gzo_url: str = "https://save-editor.be/GZO/Borderlands4/Codes.html"
_gzo_entries: list[dict[str, str]] = []
_gzo_selected_ids: set[str] = set()
_gzo_active_id: str = ""
_gzo_search: str = ""
_gzo_listing_index: int = 0
_gzo_category_filter_index: int = 0
_gzo_type_filter_index: int = 0
_gzo_manufacturer_filter_index: int = 0
_gzo_rarity_filter_index: int = 0
_gzo_creator_filter_index: int = 0
_gzo_player_index: int = 0
_gzo_status: str = "Click Load Cache or Refresh GZO to populate the BL4 Codes catalog."
_gzo_last_refresh: float = 0.0
_gzo_cache_autoload_attempted: bool = False
_lootlemon_categories: list[dict[str, str]] = [
    {"name": "Weapons", "url": "https://www.lootlemon.com/db/borderlands-4/weapons"},
    {"name": "Shields", "url": "https://www.lootlemon.com/db/borderlands-4/shields"},
    {"name": "Ordnance", "url": "https://www.lootlemon.com/db/borderlands-4/ordnance"},
    {"name": "Repkits", "url": "https://www.lootlemon.com/db/borderlands-4/repkits"},
    {"name": "Class Mods", "url": "https://www.lootlemon.com/db/borderlands-4/class-mods"},
    {"name": "Enhancements", "url": "https://www.lootlemon.com/db/borderlands-4/enhancements"},
]
_lootlemon_entries: list[dict[str, str]] = []
_lootlemon_selected_ids: set[str] = set()
_lootlemon_active_id: str = ""
_lootlemon_search: str = ""
_lootlemon_category_index: int = 0
_lootlemon_player_index: int = 0
_lootlemon_status: str = "Click Load Cache or Refresh Lootlemon to populate BL4 codes."
_lootlemon_last_refresh: float = 0.0
_lootlemon_cache_autoload_attempted: bool = False
_serial_store_search: str = ""
_currency_amount: int = 1000000
_currency_kind_index: int = 0
_exp_level: int = 70
_exp_track_index: int = 0
_inventory_settings = load_inventory_settings()
_backpack_size: int = int(_inventory_settings.get("backpack_size", _DEFAULT_BACKPACK_SIZE))
_bank_size: int = int(_inventory_settings.get("bank_size", _DEFAULT_BANK_SIZE))
_auto_inventory_sizes: bool = bool(_inventory_settings.get("auto_inventory_sizes", False))
_auto_inventory_last_log: float = 0.0
_debug_cam_speed: float = get_debug_cam_speed()
_serial_delivery_override_level: bool = False
_serial_delivery_level: int = 70
_serial_delivery_advanced_timing: bool = False
_serial_delivery_pre_open_delay: float = 0.0
_serial_delivery_post_open_delay: float = 0.05
_serial_level_override_cache: dict[tuple, tuple] = {}
_gzo_delivery_override_level: bool = False
_gzo_delivery_level: int = 70
_lootlemon_delivery_override_level: bool = False
_lootlemon_delivery_level: int = 70
_async_refresh_lock = threading.RLock()
_gzo_refresh_thread: threading.Thread | None = None
_gzo_refresh_result: tuple[list[dict[str, str]] | None, str | None, list[str]] | None = None
_gzo_refresh_progress: dict[str, object] = {"running": False, "label": "Idle", "done": 0, "total": 0, "found": 0}
_active_tab: int = 0
_loot_view: int = 0
_serial_view: int = 0
_world_view: int = 0
_loot_shape_index: int = 0
_loot_shape_radius: int = 220
_loot_shape_spacing: int = 140
_loot_shape_per_ring: int = 28
_loot_shape_z_bias: int = 18
_loot_shape_stack_height: int = 0
_loot_shape_settle_index: int = 0
_loot_shape_drop_height: int = 440
_loot_shape_line_length: int = 900
_loot_shape_include_consumables: bool = False
_loot_shape_stay_in_air: bool = True
_loot_shape_peel_after: int = 4
_loot_shape_status: str = "Choose a shape, then Place Fully (recommended for co-op)."
_ui_no_target_on: bool = False
_ui_force_fly_on: bool = False
_ui_inf_jump_on: bool = False
_ui_weapons_restricted_on: bool = False
_ui_vehicle_lock_on: bool = False
_feature_search: str = ""
_feature_jump_label: str = ""
_uvhm_all_confirm_until: float = 0.0
_challenge_bulk_confirm_until: float = 0.0
_challenge_bulk_category_index: int = 0
_challenge_single_search: str = ""
_challenge_single_row: int = 0
_challenge_single_confirm_until: float = 0.0
_challenge_single_confirm_token: str = ""
_itempool_search: str = ""
_itempool_filter_cache_key: tuple[str, str, int] | None = None
_itempool_filter_cache_rows: list[dict[str, str]] | None = None
_travel_station_filter_cache_key: tuple[str, str] | None = None
_travel_station_filter_cache_rows: list[dict[str, str]] | None = None
_itempool_category: str = "All"
_itempool_selected_index: int = 0
_itempool_count: int = 1
_itempool_spawn_gap: float = 0.12
_itempool_spawn_per_tick: int = 1
_itempool_random_spread: bool = False
_itempool_singular_named_only: bool = True
_itempool_shape_index: int = 0
_itempool_settle_index: int = 0
_itempool_drop_height: int = 440
_itempool_z_bias: int = 18
_itempool_line_length: int = 900
_itempool_shape_radius: int = 220
_itempool_shape_spacing: int = 68
_itempool_stay_in_air: bool = True
_itempool_peel_after: int = 4
_itempool_fill_until_complete: bool = False
_itempool_spawn_then_shape: bool = False
_itempool_level: int = _ITEMPOOL_DEFAULT_LEVEL
_itempool_page: int = 0
_itempool_spawn_target_index: int = 0
_ITEMPOOL_PAGE_SIZE: int = 40
_travel_map_search: str = ""
_travel_station_search: str = ""
_travel_selected_map_index: int = 0
_travel_selected_station_index: int = 0
_travel_show_all_stations: bool = bool(_inventory_settings.get("travel_show_all_stations", False))
_travel_block_local: bool = False
_travel_allow_vehicle: bool = False
_party_cache_rows: list[tuple[int, str]] = []
_party_cache_expires: float = 0.0
_party_refresh_pending: bool = False
_session_mode_cache: str = "Joined Client"
_session_mode_cache_expires: float = 0.0
_UI_WORLD_CACHE_SECONDS = 0.35
_favorite_itempools: set[str] = set(str(x) for x in _inventory_settings.get("favorite_itempools", []) if str(x).strip())
_favorite_travel_maps: set[str] = _canonicalize_travel_map_values(_inventory_settings.get("favorite_travel_maps", []))
_favorite_travel_stations: set[str] = set(str(x) for x in _inventory_settings.get("favorite_travel_stations", []) if str(x).strip())
_favorite_gzo_serials: set[str] = set(str(x) for x in _inventory_settings.get("favorite_gzo_serials", []) if str(x).strip())
_favorite_lootlemon_serials: set[str] = set(
    str(x) for x in _inventory_settings.get("favorite_lootlemon_serials", []) if str(x).strip()
)

_favorite_itempool_descriptions: dict[str, str] = {str(k): str(v) for k, v in dict(_inventory_settings.get("favorite_itempool_descriptions", {}) or {}).items() if str(k).strip() and str(v).strip()}
_favorite_travel_map_descriptions: dict[str, str] = _canonicalize_travel_map_descriptions(_inventory_settings.get("favorite_travel_map_descriptions", {}) or {})
_favorite_travel_station_descriptions: dict[str, str] = {str(k): str(v) for k, v in dict(_inventory_settings.get("favorite_travel_station_descriptions", {}) or {}).items() if str(k).strip() and str(v).strip()}
_favorite_gzo_descriptions: dict[str, str] = {
    str(k): str(v)
    for k, v in dict(_inventory_settings.get("favorite_gzo_descriptions", {}) or {}).items()
    if str(k).strip() and str(v).strip()
}
_favorite_lootlemon_descriptions: dict[str, str] = {
    str(k): str(v)
    for k, v in dict(_inventory_settings.get("favorite_lootlemon_descriptions", {}) or {}).items()
    if str(k).strip() and str(v).strip()
}

_CURRENCY_KINDS = ["cash", "eridium", "vaultcard1", "vaultcard2", "vaultcard3", "vaultcard4", "vaultcard5"]
_EXP_TRACKS = [
    "player",
    "specialization",
    "vaultcard_xp_1",
    "vaultcard_xp_2",
    "vaultcard_xp_3",
    "vaultcard_xp_4",
    "vaultcard_xp_5",
]
_MAX_WALLET_AMOUNT = 2_147_483_647
_MAX_PLAYER_LEVEL = 70
_MAX_SPEC_LEVEL = 701
_MAX_VAULT_CARD_LEVEL = 9_999  # NCS Oak2_VaultCardXP_Progression levelcap



def _wrapped_text(text: str, accent: str | None = None) -> None:
    """Draw text that wraps to the current content width, including cyber-muted text.

    BLImGui/imgui.text does not wrap, and the cyber.muted helper uses colored text
    without wrapping. Use this for any explanatory/status text inside cards so it
    cannot spill outside the card bounds.
    """
    imgui = _blimgui.imgui
    color_pushed = False
    if accent and _cyber:
        color = getattr(_cyber, accent.upper(), None) if isinstance(accent, str) else None
        try:
            if color is not None:
                imgui.push_style_color(imgui.Col_.text, _cyber._v4(color))
                color_pushed = True
        except Exception:
            color_pushed = False
    try:
        try:
            imgui.text_wrapped(str(text))
        except Exception:
            imgui.text(str(text))
    finally:
        if color_pushed:
            try:
                imgui.pop_style_color()
            except Exception:
                pass

def _muted_wrapped(text: str) -> None:
    _wrapped_text(text, "muted")


def _set_action_status(message: str, accent: str = ACCENT_INFO) -> None:
    global _last_action_status
    _last_action_status = str(message or "").strip()
    if _last_action_status:
        _log(_last_action_status)


def _list_party_players(*, force: bool = False) -> list[tuple[int, str]]:
    """Return immutable UI data; request live UObject work after the frame."""
    now = time.monotonic()
    if force or now >= _party_cache_expires:
        _request_party_snapshot()
    return list(_party_cache_rows)


def _request_party_snapshot() -> None:
    global _party_refresh_pending
    if _party_refresh_pending:
        return
    _party_refresh_pending = True
    try:
        _blimgui.defer_post_frame(_update_party_snapshot)
    except Exception:
        _party_refresh_pending = False


def _update_party_snapshot() -> None:
    """Read Unreal roster/session state only after the ImGui frame has ended."""
    global _party_cache_rows, _party_cache_expires, _party_refresh_pending
    global _session_mode_cache, _session_mode_cache_expires
    try:
        rows = list(_scan_party_players())
    except Exception:
        rows = []
    label = "Joined Client"
    try:
        world, _gs = _gbc_session_world_and_gamestate()
        if world is not None and _gbc_is_listen_host_world(world):
            label = "Listen Host"
    except Exception:
        pass
    now = time.monotonic()
    _party_cache_rows = rows
    _party_cache_expires = now + _UI_WORLD_CACHE_SECONDS
    _session_mode_cache = label
    _session_mode_cache_expires = now + _UI_WORLD_CACHE_SECONDS
    _party_refresh_pending = False


def _refresh_party_players() -> None:
    global _party_cache_expires, _session_mode_cache_expires
    _party_cache_expires = 0.0
    _session_mode_cache_expires = 0.0
    _request_party_snapshot()
    _log("Party refresh queued safely.")


def _session_mode_label() -> str:
    now = time.monotonic()
    if now >= _session_mode_cache_expires:
        _request_party_snapshot()
    return _session_mode_cache


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(int(minimum), min(int(value), int(maximum)))


def _max_level_for_track(track_index: int) -> int:
    if int(track_index) == 0:
        return _MAX_PLAYER_LEVEL
    if int(track_index) == 1:
        return _MAX_SPEC_LEVEL
    return _MAX_VAULT_CARD_LEVEL


def _default_level_for_track(track_index: int) -> int:
    if int(track_index) == 1:
        return _MAX_SPEC_LEVEL
    if int(track_index) == 0:
        return _MAX_PLAYER_LEVEL
    return 1


def _log(message: str) -> None:
    line = f"[Squ1ggs's Boosting Tools | UI] {message}"
    logging.info(line)
    _log_lines.append(line)
    del _log_lines[:-80]


_mobility_runtime.bind_ui_callbacks(_log, lambda msg, _accent: _log(msg))


class _PanelController:
    window_owned = False


_PANEL_CONTROLLER = _PanelController()


def _apply_panel_window_layout(imgui: Any) -> None:
    cond = getattr(getattr(imgui, "Cond_", None), "first_use_ever", None)
    if cond is None:
        cond = getattr(imgui, "ImGuiCond_FirstUseEver", 4)
    try:
        imgui.set_next_window_size((1120, 820), cond)
    except TypeError:
        try:
            imgui.set_next_window_size((1120, 820))
        except Exception:
            pass
    try:
        constraints = getattr(imgui, "set_next_window_size_constraints", None)
        if callable(constraints):
            constraints((420, 280), (8000, 8000))
    except Exception:
        pass


_SHINY_DROP_TOOLTIP = (
    "World drop only — not mail. If they are not shiny, cosmetics are not loaded on this save. "
    "Story done: start a new game in UVHM and Drop All Shinies should work."
)


def _button(
    label: str,
    fn: Callable[[], None],
    accent: str = ACCENT_PRIMARY,
    width: float = 0.0,
    height: float = 0.0,
    *,
    tooltip: str = "",
) -> None:
    imgui = _blimgui.imgui
    accent = resolve_accent(accent)
    pressed = _cyber.cyber_button(label, accent, width, height) if _cyber else imgui.button(label)
    if tooltip and imgui.is_item_hovered():
        imgui.set_tooltip(tooltip)
    if pressed:
        def _run() -> None:
            try:
                fn()
            except Exception as exc:
                _log(f"{label} failed: {exc!r}")

        try:
            _blimgui.defer_post_frame(_run)
        except Exception as exc:
            _log(f"{label} could not be queued safely: {exc!r}")


_CARD_STACK: list[str] = []
_CHILD_DEPTH = 0


def _note_child_begun() -> None:
    global _CHILD_DEPTH
    _CHILD_DEPTH += 1


def _note_child_ended() -> None:
    global _CHILD_DEPTH
    if _CHILD_DEPTH > 0:
        _CHILD_DEPTH -= 1


def _recover_imgui_child_stack() -> None:
    """Close children left open by a draw exception — an unbalanced Begin/EndChild
    corrupts ImGui's window stack and hard-crashes the game on the next End()."""
    global _CHILD_DEPTH
    imgui = _blimgui.imgui
    while _CHILD_DEPTH > 0:
        _CHILD_DEPTH -= 1
        try:
            imgui.end_child()
        except Exception:  # noqa: BLE001
            break
    _CHILD_DEPTH = 0
    _CARD_STACK.clear()


def _sq_section_header(title: str, accent: str = ACCENT_PRIMARY) -> None:
    _theme_section_header(_cyber, _blimgui.imgui, title, accent)


def _sq_begin_card(title: str, card_key: str, height: float) -> bool:
    """Foldable card sections — collapse headers so the window can shrink/resize cleanly."""
    global _CARD_STACK
    imgui = _blimgui.imgui
    label = f"{title}##sqcard_{card_key}"
    opened = True
    try:
        flags = getattr(imgui, "TreeNodeFlags_DefaultOpen", None)
        if flags is None:
            flags = getattr(imgui, "ImGuiTreeNodeFlags_DefaultOpen", 0)
        if flags:
            ret = imgui.collapsing_header(label, int(flags))
        else:
            ret = imgui.collapsing_header(label)
        if isinstance(ret, tuple):
            opened = bool(ret[0])
        else:
            opened = bool(ret)
        mode = "collapse"
        if opened and float(height or 0) >= 400.0:
            # Workspace cards fill remaining height so lists grow/shrink with the window.
            body_h = _remaining_child_height(220.0, 36.0)
            try:
                imgui.begin_child(f"##sqcard_body_{card_key}", (0, float(body_h)), True)
                # If the call didn't raise, a child was begun and MUST be ended later,
                # regardless of the returned visibility flag.
                mode = "collapse_child"
                _note_child_begun()
            except TypeError:
                try:
                    imgui.begin_child(f"##sqcard_body_{card_key}", (0, float(body_h)))
                    mode = "collapse_child"
                    _note_child_begun()
                except Exception:
                    mode = "collapse"
            except Exception:
                mode = "collapse"
        _CARD_STACK.append(mode)
        return opened
    except Exception:
        opened = _theme_begin_card(_cyber, title, card_accent(card_key), height)
        _CARD_STACK.append("cyber")
        return opened


def _sq_end_card() -> None:
    global _CARD_STACK
    imgui = _blimgui.imgui
    mode = _CARD_STACK.pop() if _CARD_STACK else ""
    if mode == "collapse_child":
        try:
            imgui.end_child()
            _note_child_ended()
        except Exception:
            pass
    elif mode == "cyber":
        _theme_end_card(_cyber)


def _sq_metric(label: str, value: str, accent: str = ACCENT_PRIMARY) -> None:
    _theme_metric(_cyber, label, value, accent)


def _input_text(label: str, value: str, max_len: int = 4096) -> str:
    imgui = _blimgui.imgui
    try:
        changed, new_value = imgui.input_text(label, value, max_len)
        return str(new_value) if changed else value
    except TypeError:
        try:
            changed, new_value = imgui.input_text(label, value)
            return str(new_value) if changed else value
        except Exception as exc:
            _log(f"input_text unavailable for {label}: {exc!r}")
            return value


def _input_text_multiline(label: str, value: str, max_len: int = 65536, width: int = 760, height: int = 135) -> str:
    """Text box that accepts pasted lists of serials. Falls back to single-line BLImGui if needed."""
    imgui = _blimgui.imgui
    multiline = getattr(imgui, "input_text_multiline", None)
    if callable(multiline):
        for args in (
            (label, value, max_len, width, height),
            (label, value, width, height),
            (label, value, max_len),
            (label, value),
        ):
            try:
                changed, new_value = multiline(*args)
                return str(new_value) if changed else value
            except TypeError:
                continue
            except Exception as exc:
                _log(f"input_text_multiline unavailable for {label}: {exc!r}")
                break
    return _input_text(label, value, max_len)

def _copy_text_to_clipboard(label: str, text: str) -> None:
    imgui = _blimgui.imgui
    if not str(text or ""):
        _log(f"{label}: nothing to copy.")
        return
    for name in ("set_clipboard_text", "SetClipboardText"):
        fn = getattr(imgui, name, None)
        if callable(fn):
            try:
                fn(str(text))
                _log(f"Copied {label} to clipboard.")
                return
            except Exception as exc:
                _log(f"Copy {label} failed via {name}: {exc!r}")
    try:
        import pyperclip  # type: ignore
        pyperclip.copy(str(text))
        _log(f"Copied {label} to clipboard.")
        return
    except Exception:
        pass
    _log(f"Clipboard copy unavailable for {label}; select the output text and copy manually.")


def _serials_from_entries(entries: list[dict[str, str]]) -> list[str]:
    out: list[str] = []
    for e in entries:
        if not e:
            continue
        serial = str(e.get("serial", "")).strip()
        if serial:
            out.append(serial)
    return out


def _copy_serial_list_to_clipboard(label: str, entries: list[dict[str, str]]) -> int:
    serials = _serials_from_entries(entries)
    if not serials:
        _copy_text_to_clipboard(label, "")
        return 0
    _copy_text_to_clipboard(label, "\n".join(serials))
    return len(serials)


def _serial_with_level_override(serial: str, level: int) -> str:
    raw = str(serial or "").strip()
    if not raw:
        return raw
    level_i = _clamp_int(level, 1, _MAX_PLAYER_LEVEL)
    human = _serial_to_human(raw) if raw.startswith("@U") else raw
    new_human, count = re.subn(r"^(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*)\d+", rf"\g<1>{level_i}", human, count=1)
    if count <= 0:
        raise ValueError("could not find leading item level in serial")
    return _human_to_serial(new_human)


def _serials_with_level_override(serials: list[str], enabled: bool, level: int) -> tuple[list[str], int, str | None]:
    if not enabled:
        return list(serials), 0, None
    level_i = _clamp_int(level, 1, _MAX_PLAYER_LEVEL)
    cleaned = tuple(str(s or "").strip() for s in serials if str(s or "").strip())
    key = (True, level_i, len(cleaned), hash(cleaned))
    cached = _serial_level_override_cache.get(key)
    if cached is not None:
        out, changed, error = cached
        return list(out), changed, error
    out: list[str] = []
    changed = 0
    for i, serial in enumerate(cleaned):
        try:
            out.append(_serial_with_level_override(serial, level_i))
            changed += 1
        except Exception as exc:
            result = (list(serials), changed, f"Level override failed on serial #{i + 1}: {exc}")
            _serial_level_override_cache[key] = result
            return list(result[0]), result[1], result[2]
    result = (out, changed, None)
    if len(_serial_level_override_cache) > 24:
        _serial_level_override_cache.clear()
    _serial_level_override_cache[key] = result
    return list(out), changed, None


def _draw_catalog_level_override(prefix: str, enabled: bool, level: int) -> tuple[bool, int]:
    new_enabled = _checkbox(f"Override delivery level###sqbt_{prefix}_override_level", bool(enabled))
    imgui = _blimgui.imgui
    imgui.same_line()
    new_level = _input_int_clamped(f"Level###sqbt_{prefix}_delivery_level", int(level), 1, _MAX_PLAYER_LEVEL)
    if new_enabled:
        _muted_wrapped(f"Deliver buttons deserialize selected serials, set level to {new_level}, reserialize, then deliver.")
    else:
        _muted_wrapped("Deliver buttons use catalog serial levels as-is.")
    return new_enabled, new_level


def _serial_delivery_parts_label(serials: list[str]) -> str:
    chunks = _serial_delivery_chunks(serials)
    if not chunks:
        return "Delivery split: no valid serials."
    total_raw = sum(len(str(x or "").strip()) for x in serials if str(x or "").strip())
    stats = _serial_delivery_chunk_stats(serials)
    if len(chunks) == 1:
        st = stats[0] if stats else {"serials": 0, "raw_chars": 0, "estimated_chars": 0}
        return f"Delivery split: 1 part | {st['serials']} serial(s) | {st['raw_chars']} raw chars | {st['estimated_chars']} estimated payload chars."
    preview = ", ".join(f"P{st['index']}={st['serials']} serials/{st['estimated_chars']} chars" for st in stats[:6])
    if len(stats) > 6:
        preview += ", ..."
    return f"Delivery split: {len(chunks)} parts | {len(serials)} serial(s) | {total_raw} raw chars | {preview}"


def _draw_serial_delivery_split_controls(serials: list[str]) -> None:
    global _serial_delivery_advanced_timing, _serial_delivery_pre_open_delay, _serial_delivery_post_open_delay
    imgui = _blimgui.imgui
    chunks = _serial_delivery_chunks(serials)
    if not chunks:
        _muted_wrapped("Delivery split: no valid serials selected yet.")
        return
    current_pre, current_post = serial_delivery_timing()
    if abs(float(current_pre) - float(_serial_delivery_pre_open_delay)) > 0.001 or abs(float(current_post) - float(_serial_delivery_post_open_delay)) > 0.001:
        _serial_delivery_pre_open_delay, _serial_delivery_post_open_delay = set_serial_delivery_timing(
            _serial_delivery_pre_open_delay,
            _serial_delivery_post_open_delay,
        )
    _muted_wrapped(_serial_delivery_parts_label(serials))
    if len(chunks) > 1:
        approx = len(chunks) * max(0.02, float(_serial_delivery_post_open_delay))
        _muted_wrapped(
            f"Auto delivery (non-blocking ticks): targeted GiveReward per package → "
            f"wait {_serial_delivery_post_open_delay:.2f}s → next part "
            f"(~{approx:.1f}s for {len(chunks)} part(s)). Selected target only — no lobby-wide mail."
        )
    _serial_delivery_advanced_timing = _checkbox("Advanced delivery timing###sqbt_serial_adv_timing", bool(_serial_delivery_advanced_timing))
    if _serial_delivery_advanced_timing:
        _muted_wrapped("Tune only if clients miss rewards. Wait clamps 0.00–5.00 seconds.")
        new_pre = _input_float_slider("Reserved (unused)###sqbt_serial_pre_open", _serial_delivery_pre_open_delay, 0.0, 5.0, "%.2fs")
        new_post = _input_float_slider("Wait between packages###sqbt_serial_post_open", _serial_delivery_post_open_delay, 0.0, 5.0, "%.2fs")
        new_pre = max(0.0, min(5.0, float(new_pre)))
        new_post = max(0.0, min(5.0, float(new_post)))
        if abs(new_pre - _serial_delivery_pre_open_delay) > 0.001 or abs(new_post - _serial_delivery_post_open_delay) > 0.001:
            _serial_delivery_pre_open_delay, _serial_delivery_post_open_delay = set_serial_delivery_timing(new_pre, new_post)
        imgui.same_line()
        _button("Reset 0.00/0.05", lambda: set_serial_delivery_timing(0.0, 0.05), ACCENT_INFO, 130, 0)
        imgui.same_line()
        _button("Safe 0.00/0.20", lambda: set_serial_delivery_timing(0.00, 0.20), ACCENT_WARN, 140, 0)


def _set_gzo_refresh_progress(label: str, done: int = 0, total: int = 0, found: int = 0, running: bool = True) -> None:
    with _async_refresh_lock:
        _gzo_refresh_progress.update({"running": running, "label": label, "done": int(done), "total": int(total), "found": int(found)})


def _draw_gzo_refresh_progress() -> None:
    prog = dict(_gzo_refresh_progress)
    if not prog.get("running") and str(prog.get("label") or "Idle") == "Idle":
        return
    label = str(prog.get("label") or "")
    done = int(prog.get("done") or 0)
    total = max(1, int(prog.get("total") or 1))
    found = int(prog.get("found") or 0)
    imgui = _blimgui.imgui
    try:
        imgui.progress_bar(min(1.0, float(done) / float(total)), (520, 0), f"{label} ({found} codes)")
    except Exception:
        _muted_wrapped(f"{label} ({found} codes)")


_GZO_PARTS_MAP: dict[str, dict[str, str]] | None = None
_GZO_TYPE_ID_INDEX: dict[int, tuple[str, dict[str, str]]] | None = None
_GZO_MAKER_PREFIXES = {
    "DAD": "Daedalus", "JAK": "Jakobs", "ORD": "Order", "TED": "Tediore",
    "TOR": "Torgue", "VLA": "Vladof", "MAL": "Maliwan", "BOR": "Ripper",
    "RIP": "Ripper", "COV": "CoV", "ATL": "Atlas", "HYP": "Hyperion",
}
_GZO_TYPE_SUFFIXES = {
    "PS": "Pistol", "SG": "Shotgun", "AR": "Assault Rifle", "SMG": "SMG", "SR": "Sniper",
    "HW": "Heavy Weapon", "HEAVY": "Heavy Weapon", "SHIELD": "Shield", "GADGET": "Gadget",
    "ENHANCEMENT": "Enhancement", "REPAIR_KIT": "Repkit", "REPKIT": "Repkit", "CLASS_MOD": "Classmod",
}
_GZO_CLASS_NAMES = {
    "siren": "Siren", "dark_siren": "Siren", "forgeknight": "Paladin", "paladin": "Paladin",
    "exo_soldier": "Exo Soldier", "gravitar": "Gravitar", "ai": "AI", "c4sh": "C4SH",
}


def _gzo_load_parts_map() -> dict[str, dict[str, str]]:
    global _GZO_PARTS_MAP, _GZO_TYPE_ID_INDEX
    if _GZO_PARTS_MAP is not None:
        return _GZO_PARTS_MAP
    data: dict[str, dict[str, str]] = {}
    try:
        blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], "gzo_parts_map.json")
        if blob:
            raw = json.loads(blob.decode("utf-8", "replace"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, dict):
                        data[str(k)] = {str(pk): str(pv) for pk, pv in v.items()}
    except Exception as exc:
        _log(f"GZO parts map load failed: {exc!r}")
    _GZO_PARTS_MAP = data
    idx: dict[int, tuple[str, dict[str, str]]] = {}
    for key, table in data.items():
        m = re.match(r"\s*(\d+)\s*\|\s*(.+?)\s*$", str(key))
        if m:
            idx[int(m.group(1))] = (m.group(2), table)
    _GZO_TYPE_ID_INDEX = idx
    return data


def _gzo_type_id_index() -> dict[int, tuple[str, dict[str, str]]]:
    _gzo_load_parts_map()
    return _GZO_TYPE_ID_INDEX or {}


def _gzo_title_from_slug(text: str) -> str:
    text = re.sub(r"[_\-]+", " ", str(text or "")).strip()
    return " ".join(w.upper() if w.lower() in ("smg", "ai", "cov") else w.capitalize() for w in text.split())


def _gzo_type_info_from_id(type_id: int) -> dict[str, str]:
    label_table = _gzo_type_id_index().get(int(type_id))
    if not label_table:
        return {"type_id": str(type_id), "set": "", "manufacturer": "", "type": "", "character_class": ""}
    label = label_table[0]
    raw = label.strip()
    low = raw.lower()
    info = {"type_id": str(type_id), "set": raw, "manufacturer": "", "type": "", "character_class": ""}
    if "classmod" in low or "class_mod" in low:
        info["type"] = "Classmod"
        tail = low.replace("classmod", "").replace("class_mod", "").strip("_")
        info["character_class"] = _GZO_CLASS_NAMES.get(tail, _gzo_title_from_slug(tail)) if tail else ""
        return info
    pieces = re.split(r"[_\s]+", raw)
    if pieces:
        prefix = pieces[0].upper()
        if prefix in _GZO_MAKER_PREFIXES:
            info["manufacturer"] = _GZO_MAKER_PREFIXES[prefix]
        suffix = "_".join(pieces[1:]).upper() if len(pieces) > 1 else pieces[0].upper()
        if suffix in _GZO_TYPE_SUFFIXES:
            info["type"] = _GZO_TYPE_SUFFIXES[suffix]
    if not info["type"]:
        for key, val in _GZO_TYPE_SUFFIXES.items():
            if key.lower() in low:
                info["type"] = val
                break
    return info


def _serial_parts_breakdown_text(human: str) -> str:
    human = str(human or "").strip()
    if not human:
        return ""
    m = re.match(r"\s*(\d+)\s*,", human)
    if not m:
        return "Could not find a leading typeID in the deserialized serial."
    type_id = int(m.group(1))
    idx = _gzo_type_id_index()
    type_info = _gzo_type_info_from_id(type_id)
    lines = ["Item TypeID: %s" % type_id]
    if type_info.get("set"):
        lines.append("Primary Set: %s" % type_info["set"])
    if type_info.get("manufacturer") or type_info.get("type") or type_info.get("character_class"):
        meta = " | ".join(x for x in (type_info.get("manufacturer"), type_info.get("type"), type_info.get("character_class")) if x)
        lines.append("Detected: " + meta)
    lines.append("")
    refs = re.findall(r"\{\s*(\d+)(?:\s*:\s*(\d+))?\s*\}", human)
    if not refs:
        lines.append("No {part} or {partSet:part} references found.")
        return "\n".join(lines)
    lines.append("Parts Breakdown:")
    for raw_set, raw_part in refs:
        part_set = int(raw_set) if raw_part else type_id
        part_id = int(raw_part or raw_set)
        label_table = idx.get(part_set)
        set_label = label_table[0] if label_table else "UnknownSet"
        part_name = ""
        if label_table:
            part_name = label_table[1].get(str(part_id), "")
        if part_name:
            lines.append(f"  {{{raw_set + (':' + raw_part if raw_part else '')}}}  set {part_set} {set_label} / part {part_id}: {part_name}")
        else:
            lines.append(f"  {{{raw_set + (':' + raw_part if raw_part else '')}}}  set {part_set} {set_label} / part {part_id}: <unknown>")
    return "\n".join(lines)

def _serial_tools_convert() -> None:
    global _serial_tools_serialized, _serial_tools_deserialized, _serial_tools_parts_breakdown, _serial_tools_status
    text = str(_serial_tools_input or "").strip()
    if not text:
        _serial_tools_serialized = ""
        _serial_tools_deserialized = ""
        _serial_tools_parts_breakdown = ""
        _serial_tools_status = "Paste a @U serial or deserialized serial text above."
        return
    try:
        if text.startswith("@U"):
            human = _serial_to_human(text)
            serial = _human_to_serial(human)
        else:
            serial = _human_to_serial(text)
            human = _serial_to_human(serial)
        _serial_tools_serialized = serial
        _serial_tools_deserialized = human
        _serial_tools_parts_breakdown = _serial_parts_breakdown_text(human)
        _serial_tools_status = "Converted successfully."
    except Exception as exc:
        _serial_tools_serialized = ""
        _serial_tools_deserialized = ""
        _serial_tools_parts_breakdown = ""
        _serial_tools_status = f"Conversion failed: {exc}"
        _log(f"Serial Tools conversion failed: {exc!r}")


def _parse_serial_text(raw: str) -> list[str]:
    """Parse menu input into serial/deserialized tokens without corrupting Base85.

    Important: BL4 Base85 serials may contain punctuation such as semicolons,
    commas, braces, equals signs, plus signs, etc. Older UI code split on
    semicolons/commas/spaces, which could truncate valid serials. Treat each
    non-empty line as one full serial/deserialized line. If a user pastes
    multiple Base85 serials on one line, split only at a new @U serial prefix.
    """
    tokens: list[str] = []
    for line in (raw or "").splitlines():
        text = line.strip()
        if not text:
            continue

        # Deserialized human serials contain spaces and pipes, so a whole line
        # must be preserved exactly.
        if "|" in text:
            tokens.append(text)
            continue

        # Base85 serials should be one-per-line. If several were pasted onto
        # one line, split only at @Ug (new serial), not @Uw inside Base85.
        parts = _split_base85_blob(text)
        if len(parts) > 1:
            tokens.extend(parts)
            continue

        tokens.append(text)
    return tokens


def _input_int(label: str, value: int) -> int:
    imgui = _blimgui.imgui
    try:
        changed, new_value = imgui.input_int(label, int(value))
        return int(new_value) if changed else int(value)
    except Exception as exc:
        _log(f"input_int unavailable for {label}: {exc!r}")
        return int(value)



def _input_float_slider(label: str, value: float, minimum: float, maximum: float, fmt: str = "%.2f") -> float:
    """BLImGui float slider with safe fallback for older imgui bindings."""
    imgui = _blimgui.imgui
    value = float(value)
    for name in ("slider_float", "drag_float"):
        fn = getattr(imgui, name, None)
        if callable(fn):
            for args in (
                (label, value, float(minimum), float(maximum), fmt),
                (label, value, float(minimum), float(maximum)),
            ):
                try:
                    changed, new_value = fn(*args)
                    return float(new_value) if changed else value
                except TypeError:
                    continue
                except Exception as exc:
                    _log(f"{name} unavailable for {label}: {exc!r}")
                    break
    # Fallback keeps the menu usable even on BLImGui builds without sliders.
    return float(_input_int(label, int(round(value))))

def _input_int_clamped(label: str, value: int, minimum: int, maximum: int) -> int:
    new_value = _input_int(label, value)
    clamped = _clamp_int(new_value, minimum, maximum)
    if new_value != clamped:
        _log(f"{label} capped at {clamped:,}.")
    return clamped




def _checkbox(label: str, value: bool) -> bool:
    imgui = _blimgui.imgui
    try:
        changed, new_value = imgui.checkbox(label, bool(value))
        return bool(new_value) if changed else bool(value)
    except Exception as exc:
        _log(f"checkbox unavailable for {label}: {exc!r}")
        return bool(value)

def _combo(label: str, current: int, items: list[str]) -> int:
    imgui = _blimgui.imgui
    if not items:
        return 0
    current = max(0, min(int(current), len(items) - 1))
    try:
        changed, new_idx = imgui.combo(label, current, items)
        return max(0, min(int(new_idx), len(items) - 1)) if changed else current
    except Exception:
        # Fallback for BLImGui builds without combo support: cycle with a button.
        imgui.text_wrapped(f"{label}: {items[current]}")
        if imgui.button(f"Next {label}"):
            return (current + 1) % len(items)
        return current


def _remember_selected_player_name() -> None:
    global _selected_player_delivery_name
    name = _selected_player_name()
    if name:
        _selected_player_delivery_name = name


def _resolve_delivery_player_by_name() -> tuple[int | None, str]:
    """Re-match the last selected display name when party indices shift (guests leave)."""
    global _selected_player_delivery_name

    players = _list_party_players()
    if not players:
        return None, ""
    want = _gbc_normalize_name(_selected_player_delivery_name)
    if want:
        hits = [
            (int(i), n)
            for i, n in players
            if want == _gbc_normalize_name(n) or (len(want) >= 4 and want in _gbc_normalize_name(n))
        ]
        if len(hits) == 1:
            return hits[0][0], hits[0][1]
        if len(hits) > 1:
            exact = [(i, n) for i, n in hits if _gbc_normalize_name(n) == want]
            if len(exact) == 1:
                return exact[0][0], exact[0][1]
        return None, ""
    idx = _selected_player_index_value()
    name = _selected_player_name()
    if name:
        _selected_player_delivery_name = name
    return idx, name or ""


def _selected_player_name() -> str:
    players = _list_party_players()
    if not players:
        return ""
    idx = max(0, min(_selected_player_index, len(players) - 1))
    return players[idx][1]


def _selected_player_index_value() -> int | None:
    players = _list_party_players()
    if not players:
        return None
    idx = max(0, min(_selected_player_index, len(players) - 1))
    return players[idx][0]


def _sync_spawn_target() -> str:
    """Apply the global lobby target + spawn location to shared placement helpers."""
    from . import spawn_targets  # noqa: PLC0415

    global _itempool_spawn_target_index
    target_labels = [label for _mode, label in spawn_targets.MODES]
    _itempool_spawn_target_index = max(0, min(_itempool_spawn_target_index, len(target_labels) - 1))
    target_mode = spawn_targets.MODES[_itempool_spawn_target_index][0]
    party_idx = _selected_player_index_value() if target_mode == "party" else None
    spawn_targets.set_target(target_mode, party_idx)
    return spawn_targets.label()

def _selected_player_controller() -> Any | None:
    """PlayerController for the selected party row (listen host)."""
    pidx = _selected_player_index_value()
    if pidx is None:
        return None
    world, gs = _gbc_session_world_and_gamestate()
    if gs is None:
        return None
    pa = getattr(gs, "PlayerArray", None)
    if pa is None:
        return None
    try:
        ps = pa[int(pidx)]
    except Exception:  # noqa: BLE001
        return None
    if ps is None:
        return None
    return _gbc_find_pc_for_player_state(ps, world)


def _all_party_player_indices() -> list[int]:
    return [int(i) for i, _name in _list_party_players()]


def _host_player_index_value() -> int | None:
    try:
        pc = get_pc()
    except Exception:
        pc = None
    host_ps = getattr(pc, "PlayerState", None) if pc is not None else None
    _world, gs = _gbc_session_world_and_gamestate()
    pa = getattr(gs, "PlayerArray", None) if gs is not None else None
    if pa is None:
        return None
    try:
        n = len(pa)
    except Exception:
        return None
    host_name = ""
    try:
        host_name = str(getattr(host_ps, "PlayerName", "") or getattr(host_ps, "SavedNetworkAddress", "") or "")
    except Exception:
        host_name = ""
    for i in range(n):
        try:
            ps = pa[i]
        except Exception:
            ps = None
        if ps is None:
            continue
        if host_ps is not None and ps is host_ps:
            return i
        try:
            if host_ps is not None and getattr(ps, "Name", None) == getattr(host_ps, "Name", None):
                return i
        except Exception:
            pass
        if host_name:
            try:
                pn = str(getattr(ps, "PlayerName", "") or getattr(ps, "SavedNetworkAddress", "") or "")
                if pn and pn == host_name:
                    return i
            except Exception:
                pass
    return None


def _non_host_party_player_indices() -> list[int]:
    all_indices = _all_party_player_indices()
    host_idx = _host_player_index_value()
    if host_idx is None:
        return []
    return [i for i in all_indices if i != host_idx]


def _deliver_serials_with_target(serials: list[str], mode: str, source_label: str) -> str:
    if not serials:
        return "No valid serials to deliver."
    mode = (mode or "selected").lower().strip()
    chunks = _serial_delivery_chunks(serials)
    split_note = f" Split into {len(chunks)} package part(s)." if len(chunks) > 1 else ""

    def _selected_indices() -> tuple[list[int], str]:
        idx, name = _resolve_delivery_player_by_name()
        if idx is None:
            return [], "selected player is no longer available"
        return [int(idx)], f"selected player {idx} {name}"

    # "all" = all selected codes → the selected target only (never the whole lobby).
    if mode in ("all", "selected", "sel", ""):
        indices, who = _selected_indices()
        if not indices:
            return f"Serial delivery cancelled: {who}."
        _do_give_serial_to_player_indices(serials, indices, scope_label=who)
        return f"Queued {len(serials)} serial(s) for {who} only.{split_note}"

    if mode in ("nonhost", "non_host", "all_non_host"):
        # Still targeted per guest — never GiveRewardAllPlayers.
        indices = _non_host_party_player_indices()
        if not indices:
            return "No non-host party players found."
        _do_give_serial_to_player_indices(serials, indices, scope_label="each non-host (targeted)")
        return (
            f"Queued {len(serials)} serial(s) for {len(indices)} non-host player(s) "
            f"(each gets their own mail only).{split_note}"
        )

    indices, who = _selected_indices()
    if not indices:
        return f"Serial delivery cancelled: {who}."
    _do_give_serial_to_player_indices(serials, indices, scope_label=who)
    return f"Queued {len(serials)} serial(s) for {who} only.{split_note}"



def _draw_inline_target_selector(label: str = "Target Player") -> None:
    """Compact shared target selector for serial catalog pages.

    Delivery buttons use the global selected player.  Showing this selector on
    Lootlemon/GZO avoids switching back to the Boosting tab just to retarget.
    """
    global _selected_player_index
    imgui = _blimgui.imgui
    # ImGui IDs after ### must be unique per visible combo/button. Reusing
    # ###inline_target_player on UVHM + Challenge + catalog pages caused the
    # Dear ImGui conflicting-ID popup on the Progression tab.
    id_slug = "".join(ch if ch.isalnum() else "_" for ch in str(label).casefold()) or "target"
    players = _list_party_players()
    if not players:
        imgui.text_wrapped(f"{label}: no party players found")
        imgui.same_line()
        _button(
            f"Refresh Players###sqbt_refresh_{id_slug}_empty",
            _refresh_party_players,
            "cyan",
            145,
            0,
        )
        return
    labels = [f"{idx}: {name}" for idx, name in players]
    if _selected_player_index < 0 or _selected_player_index >= len(labels):
        _selected_player_index = 0
    _selected_player_index = _combo(
        f"{label}###sqbt_inline_target_{id_slug}",
        _selected_player_index,
        labels,
    )
    imgui.same_line()
    _button(
        f"Refresh Players###sqbt_refresh_{id_slug}",
        _refresh_party_players,
        "cyan",
        145,
        0,
    )
    _remember_selected_player_name()
    selected_name = _selected_player_name() or "None"
    selected_idx = _selected_player_index_value()
    _muted_wrapped(f"Selected delivery target: {selected_idx if selected_idx is not None else '?'}: {selected_name}")

def _give_currency_selected() -> None:
    name = _selected_player_name()
    if not name:
        _log("No party player selected.")
        return
    amount = _clamp_int(_currency_amount, -_MAX_WALLET_AMOUNT, _MAX_WALLET_AMOUNT)
    if amount != _currency_amount:
        _log(f"Currency amount capped at {amount:,}.")
    _do_give_currency(_CURRENCY_KINDS[_currency_kind_index], amount, name)
    _log(f"Requested {amount} {_CURRENCY_KINDS[_currency_kind_index]} for {name}.")


def _give_experience_selected() -> None:
    name = _selected_player_name()
    if not name:
        _log("No party player selected.")
        return
    level = _clamp_int(_exp_level, 0, _max_level_for_track(_exp_track_index))
    if level != _exp_level:
        _log(f"{_EXP_TRACKS[_exp_track_index]} target level capped at {level}.")
    _do_give_experience(_EXP_TRACKS[_exp_track_index], level, name)
    _log(f"Requested {_EXP_TRACKS[_exp_track_index]} level {level} for {name}.")


def _max_player_level_selected() -> None:
    name = _selected_player_name()
    if not name:
        _log("No party player selected.")
        return
    _do_give_experience("player", _MAX_PLAYER_LEVEL, name)
    _log(f"Requested player level {_MAX_PLAYER_LEVEL} for {name}.")


def _max_spec_level_selected() -> None:
    name = _selected_player_name()
    if not name:
        _log("No party player selected.")
        return
    _do_give_experience("specialization", 701, name)
    _log(f"Requested specialization level 701 for {name}.")


def _max_currency_selected() -> None:
    pc = _selected_player_controller()
    pidx = _selected_player_index_value()
    name = _selected_player_name()
    if pc is None and pidx is None and not name:
        _log("No party player selected.")
        return
    ok, msg = _do_set_currency_absolute(
        "cash",
        _MAX_WALLET_AMOUNT,
        name or "",
        pc=pc,
        player_index=pidx,
    )
    label = name or (f"index {pidx}" if pidx is not None else "local")
    _log(f"Max cash for {label}: {'OK' if ok else 'FAIL'} — {msg}")


def _max_eridium_selected() -> None:
    pc = _selected_player_controller()
    pidx = _selected_player_index_value()
    name = _selected_player_name()
    if pc is None and pidx is None and not name:
        _log("No party player selected.")
        return
    ok, msg = _do_set_currency_absolute(
        "eridium",
        _MAX_WALLET_AMOUNT,
        name or "",
        pc=pc,
        player_index=pidx,
    )
    label = name or (f"index {pidx}" if pidx is not None else "local")
    _log(f"Max eridium for {label}: {'OK' if ok else 'FAIL'} — {msg}")




def _max_all_selected() -> None:
    pc = _selected_player_controller()
    pidx = _selected_player_index_value()
    name = _selected_player_name()
    if pc is None and pidx is None and not name:
        _log("No party player selected.")
        return
    label = name or (f"index {pidx}" if pidx is not None else "local")
    if name:
        _do_give_experience("player", _MAX_PLAYER_LEVEL, name)
        _do_give_experience("specialization", 701, name)
    cash_ok, cash_msg = _do_set_currency_absolute(
        "cash",
        _MAX_WALLET_AMOUNT,
        name or "",
        pc=pc,
        player_index=pidx,
    )
    erid_ok, erid_msg = _do_set_currency_absolute(
        "eridium",
        _MAX_WALLET_AMOUNT,
        name or "",
        pc=pc,
        player_index=pidx,
    )
    if name:
        _do_boost_maxsdu(["name", name])
    if pc is not None:
        from .vault_card_boost import max_all_vault_cards_for_pc

        vc_ok, vc_msg = max_all_vault_cards_for_pc(pc, log=_log)
        _log(
            f"Max All for {label}: player 60, spec 701, cash ({'OK' if cash_ok else 'FAIL'}: {cash_msg[:80]}), "
            f"eridium ({'OK' if erid_ok else 'FAIL'}: {erid_msg[:80]}), "
            f"max SDU, vault cards 1–5 ({'OK' if vc_ok else 'partial'}: {vc_msg[:120]}).",
        )
    else:
        for vc_kind in ("vaultcard1", "vaultcard2", "vaultcard3", "vaultcard4", "vaultcard5"):
            _do_set_currency_absolute(
                vc_kind,
                _MAX_WALLET_AMOUNT,
                name or "",
                pc=pc,
                player_index=pidx,
            )
        if name:
            for vc_xp in (
                "vaultcard_xp_1",
                "vaultcard_xp_2",
                "vaultcard_xp_3",
                "vaultcard_xp_4",
                "vaultcard_xp_5",
            ):
                _do_give_experience(vc_xp, _MAX_VAULT_CARD_LEVEL, name)
        _log(
            f"Max All for {label}: cash ({'OK' if cash_ok else 'FAIL'}), eridium ({'OK' if erid_ok else 'FAIL'}), "
            f"vault tokens {_MAX_WALLET_AMOUNT:,}."
            + (" vault XP via name." if name else " (no name — XP/SDU skipped)."),
        )




def _set_inventory_sizes_selected() -> None:
    idx = _selected_player_index_value()
    if idx is None:
        _log("No party player selected.")
        return
    bp = clamp_container_size(_backpack_size, _DEFAULT_BACKPACK_SIZE)
    bank = clamp_container_size(_bank_size, _DEFAULT_BANK_SIZE)
    name = set_inventory_sizes_for_party_index(idx, bp, bank)
    _log(f"Set inventory sizes for {name}: backpack {bp}, bank {bank}.")


def _set_inventory_sizes_all_party() -> None:
    bp = clamp_container_size(_backpack_size, _DEFAULT_BACKPACK_SIZE)
    bank = clamp_container_size(_bank_size, _DEFAULT_BANK_SIZE)
    count = set_inventory_sizes_for_all_party(bp, bank)
    _log(f"Set inventory sizes for {count} party player(s): backpack {bp}, bank {bank}.")

def _drop_all_shinies_selected() -> None:
    """World-drop curated shiny itempools (same NCS API as downloads bl4_item_spawner)."""
    try:
        from .shinies import DEFAULT_ITEM_LEVEL, drop_all_shinies
        from . import spawn_targets  # noqa: PLC0415
        from .loot_shapes import DROP_MODE_NAMES, visible_shape_names

        where = _sync_spawn_target()
        target_mode = spawn_targets.mode()
        party_idx = _selected_player_index_value() if target_mode == "party" else None
        shape_opts = ["none", *visible_shape_names()]
        settle_opts = list(DROP_MODE_NAMES)
        shape = shape_opts[max(0, min(_itempool_shape_index, len(shape_opts) - 1))]
        settle = settle_opts[max(0, min(_itempool_settle_index, len(settle_opts) - 1))]
        n = drop_all_shinies(
            DEFAULT_ITEM_LEVEL,
            target_party_index=party_idx,
            shape=shape,
            settle=settle,
            drop_height=float(_itempool_drop_height),
            line_length=float(_itempool_line_length),
            radius=float(_itempool_shape_radius),
            spacing=float(_itempool_shape_spacing),
            spawn_then_shape=_itempool_spawn_then_shape,
            stay_in_air=_itempool_stay_in_air,
            peel_after=float(_itempool_peel_after),
            land_profile="shiny",
            fill_until_complete=_itempool_fill_until_complete,
        )
        _log(
            f"Drop All Shinies: queued {n} shiny itempools @ level {DEFAULT_ITEM_LEVEL} near {where} "
            "(tick-paced ground loot — not mail)."
        )
    except Exception as ex:  # noqa: BLE001
        _log(f"Drop All Shinies failed: {ex}")


def _drop_backpack_into_shape() -> None:
    """Spill boost-target backpack, catch into land fields (same bridge as EXE Loot tab)."""
    try:
        from .bridge_actions_extended import EXTENDED_ACTIONS
        from .loot_shapes import DROP_MODE_NAMES, visible_shape_names

        shape_opts = ["none", *visible_shape_names()]
        settle_opts = list(DROP_MODE_NAMES)
        shape = shape_opts[max(0, min(_itempool_shape_index, len(shape_opts) - 1))]
        settle = settle_opts[max(0, min(_itempool_settle_index, len(settle_opts) - 1))]
        payload = {
            "player_index": _selected_player_index_value(),
            "shape": shape,
            "settle": settle,
            "drop_height": float(_itempool_drop_height),
            "line_length": float(_itempool_line_length),
            "radius": float(_itempool_shape_radius),
            "spacing": float(_itempool_shape_spacing),
            "z_bias": float(_itempool_z_bias),
            "spawn_then_shape": _itempool_spawn_then_shape,
            "stay_in_air": "yes" if _itempool_stay_in_air else "no",
            "peel_after": float(_itempool_peel_after),
            "fill_until_complete": "yes" if _itempool_fill_until_complete else "no",
            "land_profile": "shiny",
        }
        fn = EXTENDED_ACTIONS.get("faafo_drop_backpack")
        if fn is None:
            _log("Missing faafo_drop_backpack action.")
            return
        result = fn(payload)
        _log(str((result or {}).get("message") or result))
    except Exception as exc:  # noqa: BLE001
        _log(f"Drop backpack → shape failed: {exc}")


def _load_shiny_serials() -> list[str]:
    from .shinies import load_shiny_serials

    return load_shiny_serials()


def _deliver_all_shiny_serials_selected(mode: str = "all") -> None:
    """Shiny Target / All / Guest — same targeting as serial delivery buttons."""
    try:
        serials = _load_shiny_serials()
    except Exception as ex:  # noqa: BLE001
        _log(f"Shiny serial load failed: {ex}")
        return
    msg = _deliver_serials_with_target(serials, mode, "shiny")
    _log(msg)


def _activate_devperk_selected(perk_index: int) -> None:
    idx = _selected_player_index_value()
    name = _selected_player_name() or "selected player"
    perk = int(perk_index)
    label = activate_devperk(perk, idx)
    if perk in (5, 6):
        enabled = bool(devperk_toggle_state(perk, idx))
        verb = "Activated" if enabled else "Deactivated"
        accent = ACCENT_INFO if enabled else ACCENT_SECONDARY
        _set_action_status(f"{verb} {label} for {name}.", accent)
        return
    if perk == 4:
        _set_action_status(f"Granted ALL customizations + hover drives for {name}.", ACCENT_DANGER)
        return
    _set_action_status(f"Activated {label} for {name}.", ACCENT_SUCCESS)


def _activate_cosmetics_unlock() -> None:
    """Dev perk #4 — unlock all cosmetics/hover drives without kicking lobby members."""
    _activate_devperk_selected(4)


def _enable_debug_cam_selected() -> None:
    message = enable_debug_cam(_selected_player_index_value())
    _log(message)


def _force_disable_debug_cam_selected() -> None:
    message = force_disable_debug_cam(_selected_player_index_value())
    _log(message)


def _toggle_debug_cam_selected() -> None:
    idx = _selected_player_index_value()
    name = _selected_player_name() or "selected player"
    message = toggle_debug_cam(idx)
    _log(f"{message} Target: {name}.")


def _apply_debug_cam_speed(log_result: bool = True) -> None:
    global _debug_cam_speed
    idx = _selected_player_index_value()
    name = _selected_player_name() or "selected player"
    _debug_cam_speed = clamp_debug_speed(_debug_cam_speed)
    message = set_debug_cam_speed(_debug_cam_speed, idx)
    if log_result:
        _log(f"{message} Target: {name}.")


def _set_debug_cam_speed_preset(value: float) -> None:
    """Set a debug cam speed preset, update the slider value, and apply immediately."""
    global _debug_cam_speed
    _debug_cam_speed = clamp_debug_speed(value)
    _apply_debug_cam_speed(True)


def _teleport_pawn_to_debug_cam_selected() -> None:
    idx = _selected_player_index_value()
    name = _selected_player_name() or "selected player"
    message = teleport_pawn_to_debug_cam(idx)
    _log(f"{message} Target: {name}.")


def _copy_debug_cam_location_selected() -> None:
    try:
        message = copy_debug_cam_location()
        _log(message)
    except Exception as exc:
        _log(f"Copy cam location failed: {exc}")


def _inspect_looked_at_selected() -> None:
    try:
        _log(inspect_looked_at_actor())
    except Exception as exc:
        _log(f"Inspect looked-at failed: {exc}")


def _destroy_looked_at_selected() -> None:
    try:
        _log(destroy_looked_at_actor())
    except Exception as exc:
        _log(f"Destroy looked-at failed: {exc}")


def _damage_looked_at_selected() -> None:
    try:
        _log(damage_looked_at_actor())
    except Exception as exc:
        _log(f"Damage looked-at failed: {exc}")


def _max_sdu_selected() -> None:
    name = _selected_player_name()
    if not name:
        _log("No party player selected.")
        return
    _do_boost_maxsdu(["name", name])
    _log(f"Requested max SDU for {name}.")


def _give_serial_selected(mode: str = "selected") -> None:
    global _serial_delivery_override_level, _serial_delivery_level
    raw = (_serial_text or "").strip()
    if not raw:
        _log("Paste at least one Base85 serial first.")
        return
    expanded = _parse_serial_text(raw)
    serials = _resolve_give_serial_strings(expanded)
    if not serials:
        _log("No valid serials after parsing/resolving.")
        return
    serials, changed, error = _serials_with_level_override(serials, _serial_delivery_override_level, _serial_delivery_level)
    if error:
        _log(error)
        return
    status = _deliver_serials_with_target(serials, mode, "Boosting Menu")
    if changed:
        status += f" Level override: {changed} serial(s) set to level {_clamp_int(_serial_delivery_level, 1, _MAX_PLAYER_LEVEL)}."
    _log(status)



def _kick_selected_player() -> None:
    idx = _selected_player_index_value()
    name = _selected_player_name()
    if idx is None or not name:
        _log("No party player selected.")
        return
    _kick_party_player_by_index(idx, "Kicked by host")

def _small_same_line_button(label: str, fn: Callable[[], None], accent: str = "purple") -> None:
    imgui = _blimgui.imgui
    imgui.same_line()
    _button(label, fn, accent)


def _draw_target_bar(players: list[tuple[int, str]], labels: list[str]) -> None:
    global _selected_player_index, _itempool_spawn_target_index
    imgui = _blimgui.imgui
    from . import spawn_targets as _spawn_targets  # noqa: PLC0415

    opened = _sq_begin_card("Lobby Target", "target_player", 168.0)
    if opened:
        _sq_section_header("Who is affected", ACCENT_INFO)
        _selected_player_index = _combo("Party Player###sqbt_party_player", _selected_player_index, labels)
        _remember_selected_player_name()
        imgui.same_line()
        _button("Refresh###sqbt_party_refresh", _refresh_party_players, ACCENT_INFO, 90, 0)
        imgui.same_line()
        _button("Kick###sqbt_party_kick", _kick_selected_player, BTN_DANGER, 70, 0)
        selected = _selected_player_name() or "None"
        _muted_wrapped(
            f"Effect target: {selected} — boosts, mail delivery, UVHM, challenges, and max-all use this player."
        )
        imgui.separator()
        _sq_section_header("World spawn location", ACCENT_SECONDARY)
        target_labels = [label for _mode, label in _spawn_targets.MODES]
        _itempool_spawn_target_index = _combo(
            "Drop / spawn near###sqbt_global_spawn_target",
            max(0, min(_itempool_spawn_target_index, len(target_labels) - 1)),
            target_labels,
        )
        where = _sync_spawn_target()
        if _spawn_targets.mode() == "party":
            _muted_wrapped(f"World loot and spawns anchor on {selected} ({where}).")
        elif _spawn_targets.mode() == "npc_nearest":
            _muted_wrapped("World loot and spawns resolve the nearest live NPC when you run an action.")
        else:
            _muted_wrapped(f"World loot and spawns anchor on you ({where}).")
    _sq_end_card()


def _draw_quick_max() -> None:
    imgui = _blimgui.imgui
    opened = _sq_begin_card("Quick Max", "quick_max", 132.0)
    if opened:
        _sq_section_header("One-Click Caps", ACCENT_SECONDARY)
        _button("MAX ALL", _max_all_selected, BTN_MAX_ALL, 118, 0)
        imgui.same_line()
        _button("CASH", _max_currency_selected, BTN_CASH, 88, 0)
        imgui.same_line()
        _button("ERIDIUM", _max_eridium_selected, BTN_ERIDIUM, 98, 0)
        imgui.same_line()
        _button("LV 70", _max_player_level_selected, BTN_XP, 72, 0)
        imgui.same_line()
        _button("SPEC 701", _max_spec_level_selected, BTN_SPEC, 92, 0)
        _muted_wrapped(
            f"Caps: cash/eridium/vault {_MAX_WALLET_AMOUNT:,} | player {_MAX_PLAYER_LEVEL} | "
            f"spec {_MAX_SPEC_LEVEL} | vault XP {_MAX_VAULT_CARD_LEVEL:,}"
        )
    _sq_end_card()


_quick_mods_status: str = ""
_ammo_regen_rate: float = 5.0


def _sqbt_set_no_target(enabled: bool) -> None:
    """Apply AI targetability directly to the selected live controller."""
    global _quick_mods_status
    try:
        pc, pawn = _sqbt_selected_pc_pawn()
        if pc is None:
            raise RuntimeError("no selected PlayerController")
        writes = 0
        if pawn is not None:
            for attr, value in (
                ("bTargetable", not bool(enabled)),
                ("bCanBeTargeted", not bool(enabled)),
                ("bIgnoreAIAggro", bool(enabled)),
                ("bNeverTarget", bool(enabled)),
            ):
                try:
                    setattr(pawn, attr, value)
                    writes += 1
                except Exception:
                    pass
        try:
            lib = unrealsdk.find_class("GbxTargetingFunctionLibrary").ClassDefaultObject
            lib.LockTargetableByAI(pc, "sqbt_no_target", bool(enabled), bool(enabled))
            writes += 1
        except Exception:
            pass
        if writes <= 0:
            raise RuntimeError("no targetability API or pawn fields were writable")
        _quick_mods_status = f"No Target {'On' if enabled else 'Off'} ({writes} write(s))."
        _log(_quick_mods_status)
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"No Target failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_set_gravity(value: float) -> None:
    """Set GravityScale on the selected pawn's live movement objects."""
    global _quick_mods_status
    try:
        _pc, pawn = _sqbt_selected_pc_pawn()
        if pawn is None:
            raise RuntimeError("no selected pawn")
        candidates: list[Any] = [pawn]
        for attr in ("CharacterMovement", "MovementComponent", "PawnMovement", "Movement", "OakCharacterMovement"):
            try:
                obj = getattr(pawn, attr, None)
            except Exception:
                obj = None
            if obj is not None and obj not in candidates:
                candidates.append(obj)
        writes = 0
        for obj in candidates:
            try:
                setattr(obj, "GravityScale", float(value))
                writes += 1
            except Exception:
                continue
        if writes <= 0:
            raise RuntimeError("GravityScale was not writable")
        _quick_mods_status = f"GravityScale {float(value):g} applied ({writes} write(s))."
        _log(_quick_mods_status)
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Gravity failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_selected_pc_pawn() -> tuple[Any | None, Any | None]:
    idx = _selected_player_index_value()
    try:
        from .dev_tools import _pc_for_party_index  # noqa: PLC0415

        pc, _err = _pc_for_party_index(idx)
    except Exception:
        pc = get_pc()
    if pc is None:
        pc = get_pc()
    pawn = None
    if pc is not None:
        pawn = getattr(pc, "Pawn", None) or getattr(pc, "AcknowledgedPawn", None)
    return pc, pawn


def _sqbt_force_fly(enabled: bool) -> None:
    global _quick_mods_status
    try:
        index = _selected_player_index_value()
        if index is None:
            raise RuntimeError("no selected party player")
        _mobility_runtime.set_force_fly_for_index(int(index), bool(enabled))
        _quick_mods_status = _mobility_runtime.status_message
        _log(str(_quick_mods_status))
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Force fly failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_infinite_jump(enabled: bool) -> None:
    global _quick_mods_status
    try:
        index = _selected_player_index_value()
        if index is None:
            raise RuntimeError("no selected party player")
        _mobility_runtime.set_infinite_jump_for_index(int(index), bool(enabled))
        _quick_mods_status = _mobility_runtime.status_message
        _log(str(_quick_mods_status))
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Infinite jump failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_weapons_restricted(restricted: bool) -> None:
    global _quick_mods_status
    try:
        _quick_mods_status = set_weapons_restricted(bool(restricted), _selected_player_index_value())
        _log(str(_quick_mods_status))
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Weapons restricted failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_weapons_restricted_sticky(restricted: bool) -> None:
    global _quick_mods_status
    try:
        _quick_mods_status = set_weapons_restricted_sticky(bool(restricted), _selected_player_index_value())
        _log(str(_quick_mods_status))
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Weapons restricted sticky failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_toggle_weapons_restricted() -> None:
    global _quick_mods_status
    try:
        _quick_mods_status = toggle_weapons_restricted(_selected_player_index_value())
        _log(str(_quick_mods_status))
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Weapons restricted toggle failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_vehicle_lock(locked: bool) -> None:
    global _quick_mods_status
    try:
        _quick_mods_status = set_vehicle_actions_locked(bool(locked), _selected_player_index_value())
        _log(str(_quick_mods_status))
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Vehicle lock failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_kill_all_enemies() -> None:
    global _quick_mods_status
    try:
        from .dev_tools import activate_devperk_on_pc, _gameplay_pc

        pc = _gameplay_pc()
        if pc is None:
            raise RuntimeError("No local PlayerController (host).")
        _quick_mods_status = activate_devperk_on_pc(3, pc)
        _log(str(_quick_mods_status))
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Kill all failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_ammo_regen(apply_sticky: bool) -> None:
    global _quick_mods_status, _ammo_regen_rate
    try:
        if apply_sticky:
            _quick_mods_status = set_ammo_regen_sticky(_ammo_regen_rate, _selected_player_index_value())
        else:
            _quick_mods_status = set_ammo_regen_rate(_ammo_regen_rate, _selected_player_index_value())
        _log(str(_quick_mods_status))
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Ammo regen failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_ammo_regen_off() -> None:
    global _quick_mods_status, _ammo_regen_rate
    try:
        _ammo_regen_rate = 0.0
        _quick_mods_status = set_ammo_regen_sticky(0.0, _selected_player_index_value())
        _log(str(_quick_mods_status))
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Ammo regen off failed: {ex}"
        _log(_quick_mods_status)


def _sqbt_clear_combat_sticky() -> None:
    global _quick_mods_status
    try:
        idx = _selected_player_index_value()
        parts = [
            clear_weapons_restricted_sticky(idx),
            clear_ammo_regen_sticky(idx),
        ]
        _quick_mods_status = " | ".join(parts)
        _log(_quick_mods_status)
    except Exception as ex:  # noqa: BLE001
        _quick_mods_status = f"Clear sticky failed: {ex}"
        _log(_quick_mods_status)


def _draw_quick_mods(scope: str = "hub") -> None:
    """Standalone local-cheat controls on the Squ1ggs main hub."""
    global _quick_mods_status
    imgui = _blimgui.imgui
    push_id = getattr(imgui, "push_id", None)
    pop_id = getattr(imgui, "pop_id", None)
    scope_key = "".join(ch if ch.isalnum() else "_" for ch in str(scope).casefold()) or "hub"
    if callable(push_id):
        push_id(f"sqbt_quick_mods_{scope_key}")
    try:
        opened = _sq_begin_card("Quick Mods", f"quick_mods_{scope_key}", 320.0)
        if opened:
            _sq_section_header("Local Cheats", ACCENT_PRIMARY)
            _muted_wrapped(
                "God Mode uses invincible fields (not Demigod). Kill All runs on your local host PC. "
                "Weapon/vehicle locks use the party picker above. Force fly clears low-gravity first."
            )
            god_label = "God Mode (toggle)"
            _button(god_label, lambda: _activate_devperk_selected(6), ACCENT_SUCCESS, 160, 0)
            imgui.same_line()
            _button("Kill All Enemies", _sqbt_kill_all_enemies, ACCENT_DANGER, 150, 0)
            imgui.same_line()
            _button("Inf Ammo", lambda: _activate_devperk_selected(5), ACCENT_INFO, 100, 0)
            imgui.same_line()
            _button("Dev Loot", lambda: _activate_devperk_selected(7), ACCENT_PRIMARY, 100, 0)

            def _flip_no_target() -> None:
                global _ui_no_target_on
                _ui_no_target_on = not _ui_no_target_on
                _sqbt_set_no_target(_ui_no_target_on)

            def _flip_force_fly() -> None:
                global _ui_force_fly_on
                _ui_force_fly_on = not _ui_force_fly_on
                _sqbt_force_fly(_ui_force_fly_on)

            def _flip_inf_jump() -> None:
                global _ui_inf_jump_on
                _ui_inf_jump_on = not _ui_inf_jump_on
                _sqbt_infinite_jump(_ui_inf_jump_on)

            _button(
                f"NoTarget {'ON' if _ui_no_target_on else 'OFF'}",
                _flip_no_target,
                ACCENT_INFO if _ui_no_target_on else ACCENT_DANGER,
                140,
                0,
            )
            imgui.same_line()
            _button("Low Gravity", lambda: _sqbt_set_gravity(0.05), ACCENT_SECONDARY, 120, 0)
            imgui.same_line()
            _button("Gravity Normal", lambda: _sqbt_set_gravity(1.0), ACCENT_INFO, 130, 0)
            imgui.same_line()
            _button("Float Up", lambda: _sqbt_set_gravity(-0.2), ACCENT_PRIMARY, 100, 0)
            _button(
                f"Force Fly {'ON' if _ui_force_fly_on else 'OFF'}",
                _flip_force_fly,
                ACCENT_SUCCESS if _ui_force_fly_on else ACCENT_DANGER,
                140,
                0,
            )
            imgui.same_line()
            _button(
                f"Inf Jump {'ON' if _ui_inf_jump_on else 'OFF'}",
                _flip_inf_jump,
                ACCENT_SUCCESS if _ui_inf_jump_on else ACCENT_DANGER,
                130,
                0,
            )
            _sq_section_header("Weapons / vehicle locks", ACCENT_WARN)
            _muted_wrapped(
                "``bWeaponsRestricted`` blocks firing. ``VehicleActionsLock`` blocks summon/use. "
                "Use OFF to restore when missions or UI block actions."
            )

            def _flip_weapons_restricted() -> None:
                global _ui_weapons_restricted_on
                _ui_weapons_restricted_on = not _ui_weapons_restricted_on
                _sqbt_weapons_restricted(_ui_weapons_restricted_on)

            def _flip_vehicle_lock() -> None:
                global _ui_vehicle_lock_on
                _ui_vehicle_lock_on = not _ui_vehicle_lock_on
                _sqbt_vehicle_lock(_ui_vehicle_lock_on)

            _button(
                f"Weapons Restricted {'ON' if _ui_weapons_restricted_on else 'OFF'}",
                _flip_weapons_restricted,
                ACCENT_DANGER if _ui_weapons_restricted_on else ACCENT_SUCCESS,
                210,
                0,
            )
            imgui.same_line()
            _button(
                f"Vehicle lock {'ON' if _ui_vehicle_lock_on else 'OFF'}",
                _flip_vehicle_lock,
                ACCENT_DANGER if _ui_vehicle_lock_on else ACCENT_SUCCESS,
                170,
                0,
            )
            imgui.same_line()
            _button("Sticky: allow weapons", lambda: _sqbt_weapons_restricted_sticky(False), ACCENT_SUCCESS, 160, 0)
            imgui.same_line()
            _button("Sticky: block weapons", lambda: _sqbt_weapons_restricted_sticky(True), ACCENT_DANGER, 160, 0)
            _sq_section_header("Ammo regen (pawn ammoregenrate)", ACCENT_INFO)
            _muted_wrapped(
                "``OakCharacter.ammoregenrate`` — also in **BL4 Resources & Cooldowns** mod menu. "
                "Apply once or Sticky to keep the rate if the game resets it."
            )
            global _ammo_regen_rate
            ch_rate, _ammo_regen_rate = imgui.slider_float(
                "Ammo regen rate##sqbt_ammo_regen",
                float(_ammo_regen_rate),
                0.0,
                100.0,
            )
            if ch_rate:
                _ammo_regen_rate = max(0.0, float(_ammo_regen_rate))
            _button("Apply ammo regen", lambda: _sqbt_ammo_regen(False), ACCENT_INFO, 140, 0)
            imgui.same_line()
            _button("Sticky ammo regen", lambda: _sqbt_ammo_regen(True), ACCENT_SUCCESS, 150, 0)
            imgui.same_line()
            _button("Ammo regen OFF", lambda: _sqbt_ammo_regen_off(), ACCENT_DANGER, 120, 0)
            _button("Clear combat sticky##sqbt_clear_sticky", _sqbt_clear_combat_sticky, ACCENT_MUTED, 180, 0)
            _sq_section_header("F.A.A.F.O.", ACCENT_DANGER)
            _muted_wrapped(
                "Party-aware chaos on the boost target. Full kit is also on the desktop F.A.A.F.O. tab."
            )

            def _faafo_run(action: str, **extra: Any) -> None:
                global _quick_mods_status
                try:
                    from .bridge_actions_extended import EXTENDED_ACTIONS

                    payload = {"player_index": _selected_player_index_value(), **extra}
                    fn = EXTENDED_ACTIONS.get(action)
                    if fn is None:
                        _quick_mods_status = f"Missing action {action}"
                        return
                    result = fn(payload)
                    _quick_mods_status = str((result or {}).get("message") or result)
                except Exception as exc:
                    _quick_mods_status = f"FAAFO {action}: {exc}"

            _button("Launch", lambda: _faafo_run("faafo_launch"), ACCENT_DANGER, 100, 0)
            imgui.same_line()
            _button("Drop pack", lambda: _faafo_run("faafo_drop_backpack"), ACCENT_WARN, 110, 0)
            imgui.same_line()
            _button("Empty pack", lambda: _faafo_run("faafo_empty_backpack"), ACCENT_DANGER, 110, 0)
            _button("FFYL", lambda: _faafo_run("faafo_ffyl"), ACCENT_WARN, 90, 0)
            imgui.same_line()
            _button("Kill", lambda: _faafo_run("faafo_kill"), ACCENT_DANGER, 90, 0)
            imgui.same_line()
            _button("Invert look", lambda: _faafo_run("faafo_invert_look"), ACCENT_PRIMARY, 120, 0)
            _button("Lock look", lambda: _faafo_run("faafo_lock_look"), ACCENT_WARN, 110, 0)
            imgui.same_line()
            _button("Lock move", lambda: _faafo_run("faafo_lock_move"), ACCENT_WARN, 110, 0)
            imgui.same_line()
            _button("Lock both", lambda: _faafo_run("faafo_lock_both"), ACCENT_DANGER, 110, 0)
            imgui.same_line()
            _button("Unlock", lambda: _faafo_run("faafo_unlock"), ACCENT_SUCCESS, 100, 0)
            _sq_section_header("Party Teleport", ACCENT_INFO)
            _muted_wrapped("Uses the party picker above. Host/listen-server only.")
            _tp_name = _selected_player_name() or "Selected"
            _button(
                f"Me → {_tp_name}",
                lambda: _mobility_runtime.teleport_local_to_selected(_selected_player_index_value()),
                ACCENT_SUCCESS,
                180,
                0,
            )
            imgui.same_line()
            _button(
                f"{_tp_name} → Me",
                lambda: _mobility_runtime.teleport_selected_to_local(_selected_player_index_value()),
                ACCENT_PRIMARY,
                180,
                0,
            )
            if _quick_mods_status:
                _muted_wrapped(str(_quick_mods_status)[:220])
        _sq_end_card()
    finally:
        if callable(pop_id):
            pop_id()


def _draw_serial_card() -> None:
    global _serial_text, _serial_delivery_override_level, _serial_delivery_level
    imgui = _blimgui.imgui
    opened = _sq_begin_card("Serial Rewards", "serial", 400.0)
    if opened:
        imgui.text_wrapped(
            "Paste one or more serials below. Delivery goes to the selected target only "
            "(Item Serial path — no lobby-wide mail)."
        )
        delivery = serial_delivery_status()
        if delivery:
            _wrapped_text(delivery, ACCENT_INFO)
        prog = serial_delivery_progress()
        if prog.get("active"):
            try:
                imgui.progress_bar(float(prog.get("fraction") or 0.0), (520, 0), str(prog.get("label") or ""))
            except Exception:
                pass
        _serial_delivery_override_level, _serial_delivery_level = _draw_catalog_level_override(
            "serial",
            _serial_delivery_override_level,
            _serial_delivery_level,
        )
        _serial_text = _input_text_multiline("Serial Input###sqbt_serials", _serial_text, 65536, width=520, height=145)
        preview_serials = _parse_serial_text((_serial_text or "").strip()) if (_serial_text or "").strip() else []
        if preview_serials:
            resolved = _resolve_give_serial_strings(preview_serials) or []
            if resolved:
                _draw_serial_delivery_split_controls(resolved)
        _button("Give Selected", lambda: _give_serial_selected("selected"), BTN_GIVE)
        imgui.same_line(); _button("Give All Codes", lambda: _give_serial_selected("all"), BTN_HIGHLIGHT)
        imgui.same_line(); _button("Give Non-Host", lambda: _give_serial_selected("nonhost"), ACCENT_INFO)
        imgui.same_line()
        if (_cyber.cyber_button("Clear Serials", BTN_DANGER) if _cyber else imgui.button("Clear Serials")):
            _serial_text = ""
            _log("Cleared serial input.")
        _button(
            "Open Everyone's Rewards",
            open_all_party_reward_packages,
            ACCENT_SUCCESS,
            220,
            0,
        )
        _muted_wrapped("Opens every queued reward package for all live players in the lobby.")
    _sq_end_card()


def _draw_currency_card() -> None:
    global _currency_kind_index, _currency_amount
    imgui = _blimgui.imgui
    opened = _sq_begin_card("Currency", "currency", 190.0)
    if opened:
        _currency_kind_index = _combo("Currency Kind###sqbt_currency_kind", _currency_kind_index, _CURRENCY_KINDS)
        _currency_amount = _input_int_clamped("Currency Amount###sqbt_currency_amount", _currency_amount, -_MAX_WALLET_AMOUNT, _MAX_WALLET_AMOUNT)
        _button("Give Currency", _give_currency_selected, BTN_CASH)
        imgui.same_line(); _button("Max Cash", _max_currency_selected, BTN_CASH)
        imgui.same_line(); _button("Max Eridium", _max_eridium_selected, BTN_ERIDIUM)
        imgui.same_line(); _button("Max All", _max_all_selected, BTN_MAX_ALL)
        imgui.spacing()
        _sq_metric("Max Cash", f"{_MAX_WALLET_AMOUNT:,}", BTN_CASH)
        _sq_metric("Max Eridium", f"{_MAX_WALLET_AMOUNT:,}", BTN_ERIDIUM)
    _sq_end_card()


def _draw_experience_card() -> None:
    global _exp_track_index, _exp_level
    imgui = _blimgui.imgui
    opened = _sq_begin_card("Experience", "experience", 170.0)
    if opened:
        previous_exp_track_index = _exp_track_index
        _exp_track_index = _combo("XP Track###sqbt_exp_track", _exp_track_index, _EXP_TRACKS)
        if _exp_track_index != previous_exp_track_index:
            _exp_level = _default_level_for_track(_exp_track_index)
        max_track_level = _max_level_for_track(_exp_track_index)
        _exp_level = _input_int_clamped("Target Level###sqbt_exp_level", _exp_level, 0, max_track_level)
        _button("Set Level", _give_experience_selected, BTN_XP)
        imgui.same_line(); _button("Max Player", _max_player_level_selected, BTN_XP)
        imgui.same_line(); _button("Max Spec", _max_spec_level_selected, BTN_SPEC)
        _muted_wrapped(f"Range for {_EXP_TRACKS[_exp_track_index]}: 0–{max_track_level:,}")
    _sq_end_card()


def _draw_inventory_size_card() -> None:
    global _backpack_size, _bank_size, _auto_inventory_sizes, _auto_inventory_last_log
    imgui = _blimgui.imgui
    opened = _sq_begin_card("Backpack / Bank Size", "inventory", 175.0)
    if opened:
        old_bp, old_bank, old_auto = _backpack_size, _bank_size, _auto_inventory_sizes
        _backpack_size = clamp_container_size(_input_int("Backpack Size", _backpack_size), _DEFAULT_BACKPACK_SIZE)
        _bank_size = clamp_container_size(_input_int("Bank Size", _bank_size), _DEFAULT_BANK_SIZE)
        _auto_inventory_sizes = _checkbox("Automatic Backpack and Bank Size for Party", _auto_inventory_sizes)
        if (old_bp, old_bank, old_auto) != (_backpack_size, _bank_size, _auto_inventory_sizes):
            save_inventory_settings(
                auto_inventory_sizes=_auto_inventory_sizes,
                backpack_size=_backpack_size,
                bank_size=_bank_size,
            )
            _log(f"Saved inventory auto settings: auto={_auto_inventory_sizes}, backpack {_backpack_size}, bank {_bank_size}.")
        if not _auto_inventory_sizes:
            auto_apply_inventory_sizes_if_needed(False, _backpack_size, _bank_size, source="ui-reset")
        _button("Set for Selected", _set_inventory_sizes_selected, ACCENT_INFO)
        imgui.same_line(); _button("Apply All Party", _set_inventory_sizes_all_party, BTN_SPEC)
        _muted_wrapped("Writes PlayerState BackpackContainer / BankContainer MaxSize.")
    _sq_end_card()


def _draw_sdu_card() -> None:
    imgui = _blimgui.imgui
    opened = _sq_begin_card("SDU · Chest · Shinies", "sdu", 245.0)
    if opened:
        _button("Max SDU", _max_sdu_selected, BTN_XP, 120, 0)
        imgui.same_line(); _button("Open Golden Chest", _open_golden_chest, BTN_HIGHLIGHT, 175, 0)
        imgui.same_line(); _button("Close Chest", _close_golden_chest, BTN_DANGER, 115, 0)
        _button(
            "Drop All Shinies",
            _drop_all_shinies_selected,
            BTN_HIGHLIGHT,
            155,
            0,
            tooltip=_SHINY_DROP_TOOLTIP,
        )
        imgui.same_line()

        def _flip_map_fog_hide() -> None:
            from . import map_fog_hide as fog

            _set_action_status(fog.set_hidden(not fog.is_hidden()))

        try:
            from . import map_fog_hide as _fog_hide_ui

            fog_on = _fog_hide_ui.is_hidden()
        except Exception:
            fog_on = False
        _button(
            f"Hide map fog {'ON' if fog_on else 'OFF'}",
            _flip_map_fog_hide,
            ACCENT_SUCCESS if fog_on else ACCENT_MUTED,
            175,
            0,
            tooltip=(
                "Hides the map fog overlay this session. Open the map after turning it on. "
                "Fog comes back after reload. Does not unlock safehouses."
            ),
        )
        imgui.same_line()

        def _flip_hold_session() -> None:
            from . import hold_session as hold

            _set_action_status(hold.set_enabled(not hold.is_enabled()))

        try:
            from . import hold_session as _hold_ui

            hold_on = _hold_ui.is_enabled()
        except Exception:
            hold_on = False
        _button(
            f"Hold session {'ON' if hold_on else 'OFF'}",
            _flip_hold_session,
            ACCENT_SUCCESS if hold_on else ACCENT_MUTED,
            160,
            0,
            tooltip=(
                "Host only. Cancels travel-to-menu countdown and blocks return to main menu. "
                "Turn OFF before you quit to the menu yourself."
            ),
        )
        imgui.same_line()

        def _flip_shoot_sprint() -> None:
            from . import character_flags as flags

            idx = _selected_player_index_value()
            indices = [int(idx)] if idx is not None else [0]
            on = not flags.is_on("shoot_sprint", indices[0])
            _set_action_status(flags.set_flag("shoot_sprint", indices, on))

        def _flip_zoom_sprint() -> None:
            from . import character_flags as flags

            idx = _selected_player_index_value()
            indices = [int(idx)] if idx is not None else [0]
            on = not flags.is_on("zoom_sprint", indices[0])
            _set_action_status(flags.set_flag("zoom_sprint", indices, on))

        try:
            from . import character_flags as _sprint_flags

            _sp_idx = _selected_player_index_value()
            _sp_i = int(_sp_idx) if _sp_idx is not None else 0
            shoot_on = _sprint_flags.is_on("shoot_sprint", _sp_i)
            zoom_on = _sprint_flags.is_on("zoom_sprint", _sp_i)
        except Exception:
            shoot_on = False
            zoom_on = False
        _button(
            f"Shoot while sprinting {'ON' if shoot_on else 'OFF'}",
            _flip_shoot_sprint,
            ACCENT_SUCCESS if shoot_on else ACCENT_MUTED,
            210,
            0,
            tooltip="Fire while sprinting. Stays on this session.",
        )
        imgui.same_line()
        _button(
            f"Zoom while sprinting {'ON' if zoom_on else 'OFF'}",
            _flip_zoom_sprint,
            ACCENT_SUCCESS if zoom_on else ACCENT_MUTED,
            210,
            0,
            tooltip="ADS while sprinting. Stays on this session.",
        )
        imgui.same_line()

        def _black_market_run(action: str) -> None:
            try:
                from .bridge_actions_extended import EXTENDED_ACTIONS

                fn = EXTENDED_ACTIONS.get("black_market")
                if fn is None:
                    _set_action_status("Missing black_market action")
                    return
                result = fn({"player_index": _selected_player_index_value(), "action": action})
                _set_action_status(str((result or {}).get("message") or result))
            except Exception as exc:
                _set_action_status(f"Black market: {exc}")

        _button("Spawn BM machine", lambda: _black_market_run("spawn"), ACCENT_PRIMARY, 160, 0)
        imgui.same_line()
        _button("Clear BM purchase CD", lambda: _black_market_run("cooldown"), ACCENT_PRIMARY, 175, 0)
        imgui.same_line()
        _button("Reroll BM stock", lambda: _black_market_run("reroll"), ACCENT_SECONDARY, 145, 0)
        imgui.same_line(); _button("Shiny Mail Selected", lambda: _deliver_all_shiny_serials_selected("selected"), BTN_GIVE, 165, 0)
        imgui.same_line(); _button("Shiny Mail All Codes", lambda: _deliver_all_shiny_serials_selected("all"), BTN_MAX_ALL, 165, 0)
        imgui.same_line(); _button("Shiny Mail Guest", lambda: _deliver_all_shiny_serials_selected("nonhost"), ACCENT_INFO, 145, 0)
        try:
            from .shinies import shiny_drop_status

            drop_live = shiny_drop_status()
            if drop_live:
                _wrapped_text(drop_live, ACCENT_INFO)
        except Exception:
            pass
        _muted_wrapped(
            "Drop All Shinies / Loot Pools → Shiny = world loot pools (random parts, tick-paced). "
            "Shiny Mail* = fixed @U serials to mailbox (no part rolls)."
        )
    _sq_end_card()


def _draw_cosmetics_quick() -> None:
    """Main-hub cosmetics unlock (not buried in Cheats fold-out)."""
    imgui = _blimgui.imgui
    _sq_section_header("Cosmetics", ACCENT_DANGER)
    _muted_wrapped(
        "Unlock every cosmetic + hover drive on the selected target. "
        "Host: party pick above. Client: self only."
    )
    _button("Unlock All Cosmetics + Hover Drives", _activate_cosmetics_unlock, BTN_DANGER, 380, 0)
    imgui.spacing()


def _draw_dev_tools_card() -> None:
    global _debug_cam_speed
    imgui = _blimgui.imgui
    opened = _sq_begin_card("Cheats / Debug Cam", "dev", 320.0)
    if opened:
        mode = _session_mode_label()
        _sq_section_header("Cheats / Debug", ACCENT_INFO)
        _muted_wrapped(
            f"Session: {mode}. Cheats target the selected player on host. "
            "As a joined client, cheats run on your local PlayerController; "
            "Teleport Pawn to Debug Cam remains host-only."
        )
        perks = [
            (0, "Give Experience", ACCENT_INFO),
            (1, "Give 1 Million Cash", ACCENT_SECONDARY),
            (2, "Give 100k Eridium", ACCENT_PRIMARY),
            (3, "Kill All Enemies", ACCENT_DANGER),
            (5, "Infinite Ammo (toggle)", ACCENT_INFO),
            (6, "God Mode (toggle)", ACCENT_SECONDARY),
            (7, "Spawn Legendary/Epic Loot", ACCENT_PRIMARY),
        ]
        for i, (perk, label, accent) in enumerate(perks):
            _button(label, lambda perk=perk: _activate_devperk_selected(perk), accent, 220, 0)
            if i % 2 == 0:
                imgui.same_line()
        imgui.spacing()
        _button("Freecam ON", _enable_debug_cam_selected, ACCENT_SUCCESS, 120, 0)
        imgui.same_line()
        _button("Freecam OFF (force)", _force_disable_debug_cam_selected, ACCENT_DANGER, 170, 0)
        imgui.same_line()
        _button("Toggle Debug Cam", _toggle_debug_cam_selected, ACCENT_SECONDARY, 170, 0)
        imgui.same_line()
        _button("Teleport Pawn to Debug Cam", _teleport_pawn_to_debug_cam_selected, ACCENT_INFO, 260, 0)
        _old_debug_cam_speed = float(_debug_cam_speed)
        _debug_cam_speed = clamp_debug_speed(_input_float_slider("Debug Cam Speed", _old_debug_cam_speed, 0.05, 50.0, "%.2fx"))
        if abs(float(_debug_cam_speed) - _old_debug_cam_speed) > 0.0001:
            try:
                _blimgui.defer_post_frame(lambda: _apply_debug_cam_speed(False))
            except Exception as exc:
                _log(f"Debug Cam Speed could not be queued safely: {exc!r}")
        _button("1x", lambda: _set_debug_cam_speed_preset(1.0), ACCENT_INFO, 66, 0)
        imgui.same_line()
        _button("5x", lambda: _set_debug_cam_speed_preset(5.0), ACCENT_PRIMARY, 66, 0)
        imgui.same_line()
        _button("10x", lambda: _set_debug_cam_speed_preset(10.0), ACCENT_SECONDARY, 72, 0)
        imgui.same_line()
        _button("Apply Debug Cam Speed", _apply_debug_cam_speed, ACCENT_INFO, 230, 0)
        _button("Copy Cam Loc", _copy_debug_cam_location_selected, ACCENT_INFO, 150, 0)
        imgui.same_line()
        _button("Inspect Looked-At", _inspect_looked_at_selected, ACCENT_SECONDARY, 170, 0)
        imgui.same_line()
        _button("Destroy Looked-At", _destroy_looked_at_selected, ACCENT_DANGER, 170, 0)
        imgui.same_line()
        _button("Damage Looked-At", _damage_looked_at_selected, ACCENT_PRIMARY, 160, 0)
        _muted_wrapped(
            "Speed is clamped 0.05x to 50x. Presets update the slider and apply to the local debug cam. "
            "Inspect / Destroy / Damage use freecam SelectedActor (CheatManager.DestroyTarget / DamageTarget) — "
            "enable freecam, look at a world object, then click. Refuses player/camera shells. No DestroyAll."
        )
    _sq_end_card()


_SERIAL_STORE_FILE_NAME = "Squ1ggsBoostingTools_saved_serials.json"


def _serial_store_candidate_paths() -> list[Path]:
    paths: list[Path] = []
    try:
        cwd = Path.cwd()
        paths.append(cwd / "sdk_mods" / _SERIAL_STORE_FILE_NAME)
        paths.append(cwd / _SERIAL_STORE_FILE_NAME)
    except Exception:
        pass
    try:
        paths.append(Path.home() / "Documents" / "My Games" / "Borderlands 4" / "Saved" / _SERIAL_STORE_FILE_NAME)
    except Exception:
        pass
    try:
        paths.append(Path(__file__).resolve().parent / _SERIAL_STORE_FILE_NAME)
    except Exception:
        pass
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def _serial_store_path_for_read() -> Path | None:
    for path in _serial_store_candidate_paths():
        try:
            if path.exists():
                return path
        except Exception:
            continue
    return None


def _serial_store_path_for_write() -> Path:
    for path in _serial_store_candidate_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            continue
    return Path(_SERIAL_STORE_FILE_NAME)


def _serial_store_new_id() -> str:
    return _serial_store_mod.new_id()


def _serial_store_load() -> None:
    global _serial_store_entries
    if _serial_store_entries:
        return
    _serial_store_entries = _serial_store_mod.reload_entries(force=True)
    if _serial_store_entries:
        _log(f"Serial Store loaded {len(_serial_store_entries)} saved serial(s).")


def _serial_store_save() -> None:
    try:
        path = _serial_store_mod.sync_entries(_serial_store_entries)
        _log(f"Serial Store saved {len(_serial_store_entries)} serial(s) to {path.name}.")
    except Exception as exc:
        _log(f"Serial Store save failed: {exc!r}")


def _serial_store_groups() -> list[str]:
    groups = sorted({str(e.get("group") or "Default") for e in _serial_store_entries})
    return ["All"] + (groups or ["Default"])


def _serial_store_filtered_entries() -> list[dict[str, str]]:
    groups = _serial_store_groups()
    idx = max(0, min(int(_serial_store_group_filter_index), len(groups) - 1))
    group = groups[idx]
    if group == "All":
        return list(_serial_store_entries)
    return [e for e in _serial_store_entries if str(e.get("group") or "Default") == group]


def _serial_store_set_active(entry: dict[str, str]) -> None:
    global _serial_store_active_id, _serial_store_name, _serial_store_group, _serial_store_serial
    _serial_store_active_id = str(entry.get("id", ""))
    _serial_store_name = str(entry.get("name", ""))
    _serial_store_group = str(entry.get("group", "Default")) or "Default"
    _serial_store_serial = str(entry.get("serial", ""))


def _serial_store_clear_form() -> None:
    global _serial_store_active_id, _serial_store_name, _serial_store_group, _serial_store_serial, _serial_store_status
    _serial_store_active_id = ""
    _serial_store_name = ""
    _serial_store_group = "Default"
    _serial_store_serial = ""
    _serial_store_status = "Ready for a new saved serial."


def _serial_store_save_form() -> None:
    global _serial_store_active_id, _serial_store_status
    name = (_serial_store_name or "").strip()
    group = (_serial_store_group or "Default").strip() or "Default"
    serial_text = (_serial_store_serial or "").strip()
    if not name:
        _serial_store_status = "Name is required before saving."
        _log("Serial Store: name is required before saving.")
        return
    if not serial_text:
        _serial_store_status = "Serial is required before saving."
        _log("Serial Store: serial is required before saving.")
        return
    # Validate/normalize enough to catch obvious mistakes, but keep the original text for deserialized lines.
    expanded = _parse_serial_text(serial_text)
    resolved = _resolve_give_serial_strings(expanded)
    if not resolved:
        _serial_store_status = "Could not resolve the serial text into a deliverable serial."
        _log("Serial Store: save blocked because serial could not be resolved.")
        return
    if _serial_store_active_id:
        for e in _serial_store_entries:
            if str(e.get("id")) == _serial_store_active_id:
                e.update({"name": name, "group": group, "serial": serial_text})
                _serial_store_status = f"Updated {name}."
                _serial_store_save()
                return
    _serial_store_active_id = _serial_store_new_id()
    _serial_store_entries.append({"id": _serial_store_active_id, "name": name, "group": group, "serial": serial_text})
    _serial_store_status = f"Saved {name}."
    _serial_store_save()


def _serial_store_delete_active() -> None:
    global _serial_store_entries, _serial_store_active_id, _serial_store_selected_ids, _serial_store_status
    if not _serial_store_active_id:
        _serial_store_status = "No saved serial selected to delete."
        return
    old_count = len(_serial_store_entries)
    _serial_store_entries = [e for e in _serial_store_entries if str(e.get("id")) != _serial_store_active_id]
    _serial_store_selected_ids.discard(_serial_store_active_id)
    deleted = old_count - len(_serial_store_entries)
    _serial_store_clear_form()
    _serial_store_status = f"Deleted {deleted} saved serial(s)."
    _serial_store_save()

def _serial_store_duplicate_active() -> None:
    global _serial_store_active_id, _serial_store_name, _serial_store_group, _serial_store_serial, _serial_store_status
    if not _serial_store_active_id:
        _serial_store_status = "Select a saved serial before duplicating."
        return
    _serial_store_active_id = ""
    _serial_store_name = ((_serial_store_name or "Serial").strip() or "Serial") + " Copy"
    _serial_store_status = "Duplicated into a new unsaved entry. Review, then Save."


def _serial_store_select_all_filtered(filtered: list[dict[str, str]]) -> None:
    _serial_store_selected_ids.update(str(e.get("id", "")) for e in filtered if str(e.get("id", "")))


def _serial_store_group_counts() -> dict[str, int]:
    counts: dict[str, int] = {"All": len(_serial_store_entries)}
    for e in _serial_store_entries:
        group = str(e.get("group") or "Default") or "Default"
        counts[group] = counts.get(group, 0) + 1
    return counts


def _serial_store_import_from_tools() -> None:
    global _serial_store_serial, _serial_store_status
    src = (_serial_tools_serialized or _serial_tools_deserialized or _serial_tools_input or "").strip()
    if not src:
        _serial_store_status = "Serial Tools has no output/input to import."
        return
    _serial_store_serial = src
    _serial_store_status = "Imported text from Serial Tools. Add a name/group, then save."


def _serial_store_selected_entries() -> list[dict[str, str]]:
    if _serial_store_selected_ids:
        return [e for e in _serial_store_entries if str(e.get("id")) in _serial_store_selected_ids]
    if _serial_store_active_id:
        return [e for e in _serial_store_entries if str(e.get("id")) == _serial_store_active_id]
    return []


def _serial_store_deliver_selected(mode: str = "selected") -> None:
    global _serial_store_status
    entries = _serial_store_selected_entries()
    if not entries:
        _serial_store_status = "Select one or more saved serials first."
        _log("Serial Store: no saved serials selected.")
        return
    raw_serials: list[str] = []
    for e in entries:
        raw_serials.extend(_parse_serial_text(str(e.get("serial", ""))))
    serials = _resolve_give_serial_strings(raw_serials)
    if not serials:
        _serial_store_status = "Selected entries did not resolve to any deliverable serials."
        _log("Serial Store: selected entries did not resolve to any serials.")
        return
    names = ", ".join(str(e.get("name", "Serial")) for e in entries[:4])
    if len(entries) > 4:
        names += f", +{len(entries) - 4} more"
    _serial_store_status = _deliver_serials_with_target(serials, mode, "Serial Store")
    _log(f"Serial Store delivered {len(serials)} serial(s) from {names}: {_serial_store_status}")




_LOOTLEMON_CACHE_FILE_NAME = "Squ1ggsBoostingTools_lootlemon_codes.json"
_LOOTLEMON_SERIAL_RE = re.compile(r"@U\S+")
_LOOTLEMON_ITEM_PATH_RE = re.compile(r"^/(weapon|shield|grenade-mod|repkit|class-mod|enhancement)/[^/?#]+-bl4/?$", re.I)
_LOOTLEMON_BAD_NAME_TOKENS = ("function", "const ", "var ", "let ", "textarea", "script", "placeholder", "discord", "{", "}", "=>")
_LOOTLEMON_HTTP_THROTTLE_SEC = 0.22


def _lootlemon_cache_candidate_paths() -> list[Path]:
    paths: list[Path] = []
    try:
        cwd = Path.cwd()
        paths.append(cwd / "sdk_mods" / _LOOTLEMON_CACHE_FILE_NAME)
        paths.append(cwd / _LOOTLEMON_CACHE_FILE_NAME)
    except Exception:
        pass
    try:
        paths.append(Path.home() / "Documents" / "My Games" / "Borderlands 4" / "Saved" / _LOOTLEMON_CACHE_FILE_NAME)
    except Exception:
        pass
    try:
        paths.append(Path(__file__).resolve().parent / _LOOTLEMON_CACHE_FILE_NAME)
    except Exception:
        pass
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key); out.append(path)
    return out


def _lootlemon_cache_path_for_read() -> Path | None:
    for path in _lootlemon_cache_candidate_paths():
        try:
            if path.exists():
                return path
        except Exception:
            continue
    return None


def _lootlemon_cache_path_for_write() -> Path:
    for path in _lootlemon_cache_candidate_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            continue
    return Path(_LOOTLEMON_CACHE_FILE_NAME)


def _lootlemon_ascii(text: str) -> str:
    text = html.unescape(str(text or ""))
    return "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in text)


def _lootlemon_clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", _lootlemon_ascii(text)).strip()

def _lootlemon_is_valid_serial(serial: str) -> bool:
    serial = str(serial or "").strip()
    return bool(serial.startswith("@U") and len(serial) >= 20 and "xxxx" not in serial.lower() and _LOOTLEMON_SERIAL_RE.fullmatch(serial))


def _lootlemon_clean_name(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    text = _lootlemon_clean_spaces(text)
    text = re.sub(r"^Copy\s+", "", text, flags=re.I)
    text = re.sub(r"\s+Code$", "", text, flags=re.I)
    if not text or any(tok in text.lower() for tok in _LOOTLEMON_BAD_NAME_TOKENS):
        return "Lootlemon Serial"
    return text[:96]


def _lootlemon_fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Squ1ggsBoostingTools/1.0 (+Lootlemon Codes tab)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    return raw.decode("utf-8", "replace")


def _lootlemon_abs_url(href: str) -> str:
    return urllib.parse.urljoin("https://www.lootlemon.com", str(href or ""))


def _lootlemon_slugify_name(text: str) -> str:
    text = _lootlemon_clean_spaces(text).lower()
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text



def _lootlemon_extract_ordnance_table_links(page_html: str) -> list[str]:
    """Fallback for BL4 Ordnance pages that expose table rows without static item hrefs."""
    text = re.sub(r"<[^>]+>", "\n", str(page_html or ""))
    lines = [_lootlemon_clean_spaces(x) for x in text.splitlines()]
    lines = [x for x in lines if x]
    type_values = {"Heavy", "Grenade"}
    makers = {"Daedalus", "Jakobs", "Maliwan", "Order", "Ripper", "Tediore", "Torgue", "Vladof"}
    skip_names = {"Rarity", "Name", "Ordnance Type", "Manufacturer", "Elements", "Content", "Sources", "Filters", "Types", "advertisement"}
    out: list[str] = []
    seen: set[str] = set()
    for i in range(0, max(0, len(lines) - 2)):
        name, typ, maker = lines[i], lines[i + 1], lines[i + 2]
        if typ not in type_values or maker not in makers:
            continue
        if name in skip_names or name in type_values or name in makers:
            continue
        if len(name) < 2 or len(name) > 80:
            continue
        low = name.lower()
        if any(bad in low for bad in ("image", "borderlands", "database", "filter", "advertisement", "lootlemon")):
            continue
        slug = _lootlemon_slugify_name(name)
        if not slug:
            continue
        url = f"https://www.lootlemon.com/grenade-mod/{slug}-bl4"
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out

def _open_external_url(url: str, label: str = "URL") -> bool:
    url = str(url or "").strip()
    if not url:
        _log(f"{label}: no URL available to open.")
        return False
    try:
        unrealsdk.find_class(
            "/Script/Engine.KismetSystemLibrary"
        ).ClassDefaultObject.LaunchURL(url)
        _log(f"Opened {label}: {url}")
        return True
    except Exception as exc:
        _log(f"Could not open {label}: {exc!r}")
        return False


def _lootlemon_open_url(url: str) -> None:
    global _lootlemon_status
    if _open_external_url(url, "Lootlemon item page"):
        _lootlemon_status = "Opened Lootlemon item page."
    else:
        _lootlemon_status = "Could not open Lootlemon item page; see Activity Log."


def _lootlemon_extract_item_links(page_html: str, category_url: str) -> list[str]:
    """Extract Lootlemon BL4 item detail links from a category page.

    Best-of-both-worlds parser:
    - keeps the old category-relative /db/borderlands-4/<category>/<slug> links
      which were needed for Repkits/Enhancements and any hydrated slug data;
    - also accepts real BL4 detail paths such as /grenade-mod/atling-gun-bl4,
      which fixes Ordnance.
    """
    links: list[str] = []
    seen: set[str] = set()
    category_url = str(category_url or "").rstrip("/")
    category_name = category_url.rstrip("/").split("/")[-1].lower()

    legacy_detail_markers = (
        "/weapon/", "/shield/", "/ordnance/", "/grenade/", "/heavy/",
        "/repkit/", "/rep-kit/", "/class-mod/", "/enhancement/", "/bonus-item/",
    )

    def add_link(raw: str) -> None:
        raw = html.unescape(str(raw or "")).strip()
        if not raw:
            return
        full_url = _lootlemon_abs_url(raw).split("#", 1)[0].rstrip("/")
        parsed = urllib.parse.urlparse(full_url)
        if parsed.netloc and parsed.netloc.lower() != "www.lootlemon.com":
            return
        clean_url = f"https://www.lootlemon.com{parsed.path.rstrip('/')}"
        lower_url = clean_url.lower()
        if any(x in lower_url for x in ("/about", "/contact", "/privacy", "/builds", "/calculator", "/credits", "/support")):
            return

        ok = False

        # New/direct Lootlemon BL4 item pages, e.g. /grenade-mod/atling-gun-bl4.
        if _LOOTLEMON_ITEM_PATH_RE.match(parsed.path):
            ok = True

        # Old behavior: keep detail pages nested under the category page.  This is
        # required for categories whose item URLs are emitted as
        # /db/borderlands-4/repkits/<slug> or /db/borderlands-4/enhancements/<slug>.
        if category_url and lower_url.startswith((category_url + "/").lower()):
            ok = True

        # Old behavior: accept known item marker paths that may not match the
        # strict -bl4 route.
        if any(marker in lower_url for marker in legacy_detail_markers):
            ok = True

        if not ok:
            return
        if clean_url not in seen:
            seen.add(clean_url)
            links.append(clean_url)

    # Normal anchors plus URLs embedded in hydrated JSON/script data.
    for href in re.findall(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>", page_html, flags=re.I|re.S):
        add_link(href)
    for raw in re.findall(r"https?://www\.lootlemon\.com/[^\"'<>\s)]+", page_html, flags=re.I):
        add_link(raw)

    # Direct item detail paths.
    for raw in re.findall(r"/(?:weapon|shield|grenade-mod|repkit|rep-kit|class-mod|enhancement)/[^\"'<>\s)]+-bl4/?", page_html, flags=re.I):
        add_link(raw)

    # Category-relative hydrated routes from the old parser.  These brought in
    # Repkits and Enhancements before the strict Ordnance path fix.
    for raw in re.findall(r"/(?:db/)?borderlands-4/[^\"'<>\s)]+", page_html, flags=re.I):
        add_link(raw)

    # Hydrated item objects sometimes provide name/title plus slug instead of an href.
    for m in re.finditer(r"[\"'](?:name|title)[\"']\s*:\s*[\"']([^\"']{2,96})[\"'](?:(?![{}]).){0,300}?[\"']slug[\"']\s*:\s*[\"']([^\"']{2,120})[\"']", page_html, flags=re.I|re.S):
        slug = m.group(2).strip("/")
        add_link(category_url + "/" + slug)
    for m in re.finditer(r"[\"']slug[\"']\s*:\s*[\"']([^\"']{2,120})[\"'](?:(?![{}]).){0,300}?[\"'](?:name|title)[\"']\s*:\s*[\"']([^\"']{2,96})[\"']", page_html, flags=re.I|re.S):
        slug = m.group(1).strip("/")
        add_link(category_url + "/" + slug)

    # Ordnance fallback: names in the rendered table may not be emitted as static hrefs.
    if category_name == "ordnance":
        for u in _lootlemon_extract_ordnance_table_links(page_html):
            add_link(u)

    return links

def _lootlemon_extract_meta(detail_html: str, fallback_name: str, category: str) -> dict[str, str]:
    title = fallback_name
    m = re.search(r"<h1[^>]*>(.*?)</h1>", detail_html, flags=re.I|re.S)
    if m:
        title = _lootlemon_clean_name(m.group(1))
    if title == "Lootlemon Serial":
        m = re.search(r"<title[^>]*>(.*?)</title>", detail_html, flags=re.I|re.S)
        if m:
            title = _lootlemon_clean_name(m.group(1).split("•")[0].split("-")[0])
    rarity = ""
    rm = re.search(r"Rarity\s*</[^>]+>\s*<[^>]+>([^<]+)", detail_html, flags=re.I|re.S)
    if rm:
        rarity = _lootlemon_clean_spaces(rm.group(1))[:48]
    manufacturer = ""
    mm = re.search(r"Manufacturer\s*</[^>]+>\s*<[^>]+>([^<]+)", detail_html, flags=re.I|re.S)
    if mm:
        manufacturer = _lootlemon_clean_spaces(mm.group(1))[:48]
    return {"name": title or fallback_name, "category": category, "rarity": rarity, "manufacturer": manufacturer}


def _lootlemon_extract_codes_from_detail(detail_html: str, url: str, category: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    base_name = url.rstrip('/').split('/')[-1].replace('-', ' ').title()
    meta = _lootlemon_extract_meta(detail_html, base_name, category)
    text = detail_html
    serials: list[str] = []
    for m in _LOOTLEMON_SERIAL_RE.finditer(text):
        serial = html.unescape(m.group(0)).strip().rstrip(".,;)")
        if not serial.startswith("@U"):
            continue
        if "xxxx" in serial.lower() or len(serial) < 20:
            continue
        if serial not in serials:
            serials.append(serial)
    for i, serial in enumerate(serials):
        name = str(meta.get("name") or base_name)
        # Prefer nearby Copy <Name> Code label when present.
        idx = text.find(serial)
        if idx >= 0:
            near = text[max(0, idx-800):idx+200]
            cm = re.search(r"Copy\s+([^<>{}\n\r]{2,120}?)\s+Code", near, flags=re.I)
            if cm:
                name = _lootlemon_clean_name(cm.group(1))
        if len(serials) > 1:
            name = f"{name} #{i+1}"
        eid = f"lootlemon:{category}:{name}:{i}:{abs(hash(serial))}"
        row = dict(meta)
        row.update({"id": eid, "name": _lootlemon_clean_name(name), "serial": serial, "url": url, "source": "Lootlemon"})
        out.append(row)
    return out


def _lootlemon_load_cache(silent: bool = False) -> bool:
    global _lootlemon_entries, _lootlemon_status, _lootlemon_active_id
    try:
        path = _lootlemon_cache_path_for_read()
        if path is None:
            if not silent:
                _lootlemon_status = "No Lootlemon cache found. Click Refresh Lootlemon."
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("entries", data) if isinstance(data, dict) else data
        if not isinstance(entries, list):
            raise ValueError("cache did not contain an entries list")
        cleaned: list[dict[str, str]] = []
        seen: set[str] = set()
        for e in entries:
            if not isinstance(e, dict):
                continue
            serial = str(e.get("serial", "")).strip()
            if not _lootlemon_is_valid_serial(serial):
                continue
            key = serial
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({
                "id": str(e.get("id") or f"lootlemon:{len(cleaned)}"),
                "name": _lootlemon_clean_name(str(e.get("name", "Lootlemon Serial"))),
                "category": _lootlemon_clean_spaces(str(e.get("category", ""))) or "Lootlemon",
                "rarity": _lootlemon_clean_spaces(str(e.get("rarity", ""))),
                "manufacturer": _lootlemon_clean_spaces(str(e.get("manufacturer", ""))),
                "url": str(e.get("url", "")),
                "source": "Lootlemon",
                "serial": serial,
            })
        _lootlemon_entries = cleaned
        _lootlemon_active_id = cleaned[0]["id"] if cleaned and not _lootlemon_active_id else _lootlemon_active_id
        if not silent:
            _lootlemon_status = f"Loaded {len(cleaned)} cached Lootlemon code(s)."
        return True
    except Exception as exc:
        if not silent:
            _lootlemon_status = f"Lootlemon cache load failed: {exc}"
        _log(f"Lootlemon cache load failed: {exc!r}")
        return False


def _lootlemon_save_cache() -> None:
    try:
        path = _lootlemon_cache_path_for_write()
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"updated": int(time.time()), "source": "Lootlemon BL4", "entries": _lootlemon_entries}, f, indent=2, sort_keys=True)
    except Exception as exc:
        _log(f"Lootlemon cache save failed: {exc!r}")


def _lootlemon_refresh_catalog() -> None:
    global _lootlemon_entries, _lootlemon_status, _lootlemon_last_refresh, _lootlemon_active_id
    try:
        from . import runtime_log

        runtime_log.note("Lootlemon catalog refresh started (throttled HTTP — avoid during game load).")
    except Exception:
        pass
    all_entries: list[dict[str, str]] = []
    seen_serials: set[str] = set()
    try:
        for cat in _lootlemon_categories:
            cname = str(cat["name"]); curl = str(cat["url"])
            _lootlemon_status = f"Fetching Lootlemon {cname} list..."
            list_html = _lootlemon_fetch(curl)
            time.sleep(_LOOTLEMON_HTTP_THROTTLE_SEC)
            links = _lootlemon_extract_item_links(list_html, curl)
            # Some pages may have inline serials; parse the list itself too.
            for row in _lootlemon_extract_codes_from_detail(list_html, curl, cname):
                if row["serial"] not in seen_serials:
                    seen_serials.add(row["serial"]); all_entries.append(row)
            for idx, link in enumerate(links):
                try:
                    _lootlemon_status = f"Fetching Lootlemon {cname}: {idx+1}/{len(links)}"
                    detail = _lootlemon_fetch(link)
                    time.sleep(_LOOTLEMON_HTTP_THROTTLE_SEC)
                    for row in _lootlemon_extract_codes_from_detail(detail, link, cname):
                        if row["serial"] not in seen_serials:
                            seen_serials.add(row["serial"]); all_entries.append(row)
                except Exception as inner:
                    _log(f"Lootlemon detail scrape failed for {link}: {inner!r}")
        all_entries.sort(key=lambda e: (str(e.get("category", "")).lower(), str(e.get("name", "")).lower()))
        _lootlemon_entries = all_entries
        _lootlemon_last_refresh = time.time()
        _lootlemon_active_id = all_entries[0]["id"] if all_entries else ""
        _lootlemon_save_cache()
        _lootlemon_status = f"Loaded and cached {len(all_entries)} Lootlemon BL4 code(s)."
    except Exception as exc:
        _lootlemon_status = f"Lootlemon refresh failed: {exc}"
        _log(f"Lootlemon refresh failed: {exc!r}")


def _lootlemon_category_names() -> list[str]:
    return ["All"] + [str(c["name"]) for c in _lootlemon_categories]


def _lootlemon_filtered_entries() -> list[dict[str, str]]:
    query = _lootlemon_search.lower().strip()
    cats = _lootlemon_category_names()
    cat = cats[max(0, min(_lootlemon_category_index, len(cats)-1))]
    out: list[dict[str, str]] = []
    for e in _lootlemon_entries:
        if cat != "All" and str(e.get("category", "")) != cat:
            continue
        hay = " ".join(str(e.get(k, "")) for k in ("name", "category", "rarity", "manufacturer", "serial", "url")).lower()
        if query and query not in hay:
            continue
        out.append(e)
    return _sort_favorites_first(out, "serial", _favorite_lootlemon_serials)


def _lootlemon_active_entry() -> dict[str, str] | None:
    for e in _lootlemon_entries:
        if str(e.get("id", "")) == _lootlemon_active_id:
            return e
    return _lootlemon_entries[0] if _lootlemon_entries else None


def _lootlemon_selected_entries() -> list[dict[str, str]]:
    return [e for e in _lootlemon_entries if str(e.get("id", "")) in _lootlemon_selected_ids]


def _lootlemon_select_all_filtered(entries: list[dict[str, str]]) -> None:
    for e in entries:
        eid = str(e.get("id", ""))
        if eid:
            _lootlemon_selected_ids.add(eid)


def _lootlemon_import_selected_to_store() -> None:
    global _lootlemon_status
    _serial_store_load()
    entries = _lootlemon_selected_entries()
    if not entries:
        active = _lootlemon_active_entry()
        entries = [active] if active else []
    existing = {str(e.get("serial", "")).strip() for e in _serial_store_entries}
    added = 0; skipped = 0
    for e in entries:
        if not e:
            continue
        serial = str(e.get("serial", "")).strip()
        if not _LOOTLEMON_SERIAL_RE.fullmatch(serial):
            continue
        if serial in existing:
            skipped += 1; continue
        group = "Lootlemon - " + (str(e.get("category", "")) or "BL4")
        _serial_store_entries.append({
            "id": _serial_store_new_id() + f"_{added}",
            "name": _lootlemon_clean_name(str(e.get("name", "Lootlemon Serial"))),
            "group": group,
            "serial": serial,
            "created": str(int(time.time())),
            "updated": str(int(time.time())),
        })
        existing.add(serial); added += 1
    _serial_store_save()
    _lootlemon_status = f"Imported {added} Lootlemon serial(s) to Serial Store" + (f"; skipped {skipped} duplicate(s)." if skipped else ".")


def _lootlemon_copy_selected_serials() -> None:
    global _lootlemon_status
    entries = _lootlemon_selected_entries()
    if not entries:
        active = _lootlemon_active_entry()
        entries = [active] if active else []
    count = _copy_serial_list_to_clipboard("selected Lootlemon serials", entries)
    _lootlemon_status = f"Copied {count} selected Lootlemon serial(s) to clipboard." if count else "Select one or more Lootlemon serials to copy."


def _lootlemon_deliver_selected(mode: str = "selected") -> None:
    global _lootlemon_status, _lootlemon_delivery_override_level, _lootlemon_delivery_level
    entries = _lootlemon_selected_entries()
    if not entries:
        active = _lootlemon_active_entry()
        entries = [active] if active else []
    serials = [str(e.get("serial", "")).strip() for e in entries if e and _lootlemon_is_valid_serial(str(e.get("serial", "")).strip())]
    if not serials:
        _lootlemon_status = "Select one or more valid Lootlemon serials first."
        return
    serials, changed, error = _serials_with_level_override(serials, _lootlemon_delivery_override_level, _lootlemon_delivery_level)
    if error:
        _lootlemon_status = error
        _log(_lootlemon_status)
        return
    _lootlemon_status = _deliver_serials_with_target(serials, mode, "Lootlemon Codes")
    if changed:
        _lootlemon_status += f" Level override: {changed} serial(s) set to level {_clamp_int(_lootlemon_delivery_level, 1, _MAX_PLAYER_LEVEL)}."
    _log(f"Lootlemon Codes delivered {len(serials)} serial(s): {_lootlemon_status}")


def _draw_lootlemon_codes_tab() -> None:
    global _lootlemon_search, _lootlemon_category_index, _lootlemon_player_index, _lootlemon_active_id, _lootlemon_cache_autoload_attempted, _lootlemon_delivery_override_level, _lootlemon_delivery_level
    imgui = _blimgui.imgui
    opened = _sq_begin_card("Lootlemon Codes", "lootlemon", _tab_card_height(780.0))
    if opened:
        if not _lootlemon_cache_autoload_attempted and not _lootlemon_entries:
            _lootlemon_cache_autoload_attempted = True
            _lootlemon_load_cache(silent=True)
        imgui.text_wrapped("Cached Lootlemon BL4 code catalog")
        _muted_wrapped("Scrapes BL4 item pages for Copy Code serials, caches them locally, and lets you multi-select/import/deliver. All labels are ASCII-only.")
        _button("Load Cache", _lootlemon_load_cache, "cyan", 110, 0)
        imgui.same_line(); _button("Refresh Lootlemon", _lootlemon_refresh_catalog, "gold", 170, 0)
        imgui.same_line(); _button("Copy Selected", _lootlemon_copy_selected_serials, "purple", 130, 0)
        imgui.same_line(); _button("Import Selected To Store", _lootlemon_import_selected_to_store, "purple", 210, 0)
        _lootlemon_delivery_override_level, _lootlemon_delivery_level = _draw_catalog_level_override(
            "lootlemon",
            _lootlemon_delivery_override_level,
            _lootlemon_delivery_level,
        )
        imgui.separator()
        _lootlemon_search = _input_text("Search###lootlemon_search", _lootlemon_search, 256)
        _lootlemon_category_index = _combo("Category###lootlemon_category", _lootlemon_category_index, _lootlemon_category_names())
        filtered = _lootlemon_filtered_entries()
        imgui.text_wrapped(f"{len(filtered)} shown / {len(_lootlemon_entries)} loaded | {len(_lootlemon_selected_ids)} selected")
        _button("Select All", lambda: _lootlemon_select_all_filtered(filtered), "purple", 110, 0)
        imgui.same_line(); _button("Clear", lambda: _lootlemon_selected_ids.clear(), "pink", 80, 0)
        active_preview = _lootlemon_active_entry()
        active_serial = str((active_preview or {}).get("serial", "")).strip()
        ll_fav_label = (
            "Unfavorite Selected"
            if active_serial and _is_favorite(active_serial, _favorite_lootlemon_serials)
            else "Favorite Selected"
        )
        imgui.same_line(); _button(ll_fav_label, _toggle_active_lootlemon_favorite, "purple", 170, 0)
        columns = getattr(imgui, "columns", None); next_column = getattr(imgui, "next_column", None); using_columns = False
        if callable(columns) and callable(next_column):
            try:
                columns(2, "sqbt_lootlemon_codes_columns", True); using_columns = True
            except Exception:
                try: columns(2); using_columns = True
                except Exception: using_columns = False
        imgui.text_wrapped("CODES")
        child_open = _begin_child_region("sqbt_lootlemon_codes_list", 430.0)
        try:
            if not filtered:
                imgui.text_wrapped("No Lootlemon codes loaded/matching. Click Load Cache or Refresh Lootlemon.")
            for index, e in enumerate(filtered):
                eid = str(e.get("id", ""))
                serial = str(e.get("serial", "")).strip()
                fav = _is_favorite(serial, _favorite_lootlemon_serials)
                if imgui.small_button(f"{'−' if fav else '+'}###sqbt_llfav_{index}_{eid}"):
                    _toggle_serial_favorite(
                        serial,
                        _favorite_lootlemon_serials,
                        _favorite_lootlemon_descriptions,
                        label="Lootlemon",
                        display_name=str(e.get("name", "")),
                    )
                imgui.same_line()
                checked = "[X]" if eid in _lootlemon_selected_ids else "[ ]"
                active = "> " if eid == _lootlemon_active_id else "  "
                meta = " / ".join(x for x in [str(e.get("category", "")), str(e.get("manufacturer", "")), str(e.get("rarity", ""))] if x)
                fav_prefix = _fav_prefix(serial, _favorite_lootlemon_serials)
                label = (
                    f"{active}{checked} {fav_prefix}{e.get('name','Lootlemon Serial')}"
                    f"{_fav_description(serial, _favorite_lootlemon_descriptions)}    {meta}###lootlemon_row_{eid}"
                )
                if _selectable_row(label, eid == _lootlemon_active_id):
                    _lootlemon_active_id = eid
                    if eid in _lootlemon_selected_ids: _lootlemon_selected_ids.discard(eid)
                    else: _lootlemon_selected_ids.add(eid)
        finally:
            if child_open: _end_child_region()
        if using_columns: next_column()
        imgui.text_wrapped("DETAILS")
        active = _lootlemon_active_entry()
        if active:
            imgui.text_wrapped(str(active.get("name", "Lootlemon Serial")))
            _muted_wrapped(" | ".join(x for x in [str(active.get("category", "")), str(active.get("manufacturer", "")), str(active.get("rarity", "")), str(active.get("url", ""))] if x))
            _input_text_multiline("Serial###lootlemon_active_serial", str(active.get("serial", "")), 65536, width=620, height=190)
            _draw_favorite_description_editor(
                "Favorite note###lootlemon_fav_note",
                str(active.get("serial", "")).strip(),
                _favorite_lootlemon_serials,
                _favorite_lootlemon_descriptions,
            )
            _button("Copy Serial", lambda: _copy_text_to_clipboard("Lootlemon serial", str(active.get("serial", ""))), "purple", 130, 0)
            imgui.same_line(); _button("Open Item Page", lambda: _lootlemon_open_url(str(active.get("url", ""))), "gold", 150, 0)
            imgui.same_line(); _button("Open Link", lambda: _lootlemon_open_url(str(active.get("url", ""))), "purple", 110, 0)
            imgui.same_line(); _button("Import This", lambda: (_lootlemon_selected_ids.add(str(active.get("id", ""))), _lootlemon_import_selected_to_store()), "cyan", 120, 0)
        else:
            imgui.text_wrapped("Select a Lootlemon code to preview its serial.")
        if using_columns:
            try: columns(1)
            except Exception: pass
        imgui.separator()
        _muted_wrapped(
            f"{len(_lootlemon_selected_entries())} selected | Delivery goes to the lobby target at the top "
            "(tick-paced packages — does not freeze the host). Open reward mail to claim."
        )
        imgui.same_line(); _button("Deliver Selected", lambda: _lootlemon_deliver_selected("selected"), "purple", 165, 0)
        imgui.same_line(); _button("Deliver All Selected", lambda: _lootlemon_deliver_selected("all"), "gold", 175, 0)
        imgui.same_line(); _button("Deliver Non-Host", lambda: _lootlemon_deliver_selected("nonhost"), "cyan", 185, 0)
        imgui.text_wrapped(_lootlemon_status)
    _sq_end_card()

_GZO_LISTING_FILTERS = ["All", "Legit", "Modded"]
_GZO_CACHE_VERSION = 3
_GZO_CACHE_FILE_NAME = "Squ1ggsBoostingTools_gzo_codes.json"
_GZO_BAD_TEXT_TOKENS = (
    "<textarea", "</textarea", "<script", "</script", "const ", "function(",
    "base85.search", "discordurl", "creator\":", "rarity\":", "tacklebox",
    "placeholder=", "submit-base85", "json.parse", "autoUps", "document.",
    "data-", "class=", "id=", "textarea", "script", "onclick", "function",
    "{\"", "\":\"", "\",\"",
)
_GZO_SERIAL_RE = re.compile(r"@U[0-9A-Za-z!#$%&()*+\-;<=>?@^_`{/}~]{12,}")


_GZO_HTTP_THROTTLE_SEC = 0.18


def _gzo_url_join(base: str, url: str) -> str:
    try:
        return urllib.parse.urljoin(base, str(url or ""))
    except Exception:
        return str(url or "")


def _gzo_fetch_text(url: str, timeout: float = 12.0) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Squ1ggsBoostingTools/1.0 (+BL4 GZO Codes tab)",
            "Accept": "text/html,application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(4_000_000)
    return raw.decode("utf-8", "replace")


def _gzo_entry_id(entry: dict[str, str]) -> str:
    base = "|".join(str(entry.get(k, "")) for k in ("name", "serial", "listing", "source"))
    return str(abs(hash(base)))


def _gzo_cache_candidate_paths() -> list[Path]:
    paths: list[Path] = []
    try:
        cwd = Path.cwd()
        paths.append(cwd / "sdk_mods" / _GZO_CACHE_FILE_NAME)
        paths.append(cwd / _GZO_CACHE_FILE_NAME)
    except Exception:
        pass
    try:
        paths.append(Path.home() / "Documents" / "My Games" / "Borderlands 4" / "Saved" / _GZO_CACHE_FILE_NAME)
    except Exception:
        pass
    try:
        paths.append(Path(__file__).resolve().parent / _GZO_CACHE_FILE_NAME)
    except Exception:
        pass
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def _gzo_cache_path_for_read() -> Path | None:
    for path in _gzo_cache_candidate_paths():
        try:
            if path.exists():
                return path
        except Exception:
            continue
    return None


def _gzo_cache_path_for_write() -> Path:
    for path in _gzo_cache_candidate_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            continue
    return Path(_GZO_CACHE_FILE_NAME)


def _gzo_normalize_cached_entry(e: dict) -> dict[str, str] | None:
    from . import gzo_filters

    try:
        serial = str(e.get("serial", "")).strip()
        if not _gzo_is_valid_serial(serial):
            return None
        row = {
            "id": "",
            "name": _gzo_clean_name(str(e.get("name", "GZO Serial"))) or "GZO Serial",
            "serial": serial,
            "listing": _gzo_ascii(str(e.get("listing", "GZO")) or "GZO"),
            "type": _gzo_ascii(gzo_filters.normalize_type(str(e.get("type", "") or e.get("item_type", "")))),
            "rarity": _gzo_ascii(str(e.get("rarity", ""))),
            "manufacturer": _gzo_ascii(str(e.get("manufacturer", ""))),
            "creator": _gzo_ascii(str(e.get("creator", ""))),
            "character_class": _gzo_ascii(str(e.get("character_class", ""))),
            "tags": _gzo_ascii(str(e.get("tags", ""))),
            "extra_tags": _gzo_ascii(str(e.get("extra_tags", ""))),
            "source": _gzo_ascii(str(e.get("source", "GZO Cache")) or "GZO Cache"),
        }
        if _gzo_has_bad_text(" ".join(str(row.get(k, "")) for k in ("name", "type", "rarity", "manufacturer", "creator", "tags"))):
            return None
        row["id"] = _gzo_entry_id(row)
        return row
    except Exception:
        return None


def _gzo_load_cache(silent: bool = False) -> bool:
    global _gzo_entries, _gzo_selected_ids, _gzo_active_id, _gzo_status, _gzo_last_refresh
    try:
        path = _gzo_cache_path_for_read()
        if path is None:
            if not silent:
                _gzo_status = "No GZO cache found. Click Refresh GZO."
            return False
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict) or int(payload.get("version", 0) or 0) != _GZO_CACHE_VERSION:
            if not silent:
                _gzo_status = "GZO cache is from an older parser. Click Refresh GZO to rebuild it."
            return False
        entries = payload.get("entries", [])
        if not isinstance(entries, list):
            raise ValueError("cache did not contain an entries list")
        cleaned: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw in entries:
            if not isinstance(raw, dict):
                continue
            row = _gzo_normalize_cached_entry(raw)
            if not row:
                continue
            serial = row.get("serial", "")
            if serial in seen:
                continue
            seen.add(serial)
            cleaned.append(row)
        _gzo_entries = cleaned
        ids = {str(e.get("id", "")) for e in cleaned}
        _gzo_selected_ids = {eid for eid in _gzo_selected_ids if eid in ids}
        if cleaned and (_gzo_active_id not in ids):
            _gzo_active_id = str(cleaned[0].get("id", ""))
        elif not cleaned:
            _gzo_active_id = ""
        try:
            _gzo_last_refresh = float(payload.get("updated", 0)) if isinstance(payload, dict) else 0.0
        except Exception:
            _gzo_last_refresh = 0.0
        _gzo_status = f"Loaded {len(cleaned)} cached GZO code(s)."
        return bool(cleaned)
    except Exception as exc:
        if not silent:
            _gzo_status = f"GZO cache load failed: {exc}"
        _log(f"GZO cache load failed: {exc!r}")
        return False


def _gzo_save_cache() -> None:
    try:
        path = _gzo_cache_path_for_write()
        with path.open("w", encoding="utf-8") as f:
            # Compact JSON — indented dumps of 2k+ entries hitch the game thread.
            json.dump(
                {
                    "version": _GZO_CACHE_VERSION,
                    "updated": int(time.time()),
                    "source": "GZO BL4",
                    "entries": _gzo_entries,
                },
                f,
                separators=(",", ":"),
                sort_keys=False,
            )
    except Exception as exc:
        _log(f"GZO cache save failed: {exc!r}")


def _gzo_ascii(text: str) -> str:
    """Return UI-safe ASCII text. BLImGui font often renders unicode glyphs as question blocks."""
    try:
        text = html.unescape(str(text or ""))
    except Exception:
        text = str(text or "")
    replacements = {
        "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"',
        "…": "...", "X": "X", "✔": "X", "X": "X", "✕": "X", ">": ">",
        "▷": ">", "*": "*", "◇": "*", "*": "*", "*": "*", "[X]": "[X]", "[ ]": "[ ]",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("ascii", "ignore").decode("ascii")


def _gzo_has_bad_text(text: str) -> bool:
    low = str(text or "").lower()
    return any(tok.lower() in low for tok in _GZO_BAD_TEXT_TOKENS)


def _gzo_is_valid_serial(serial: str) -> bool:
    serial = str(serial or "").strip()
    if not _GZO_SERIAL_RE.fullmatch(serial):
        return False
    # Reject placeholder/demo serials like @Ugxxxxxxxxxxxxx.
    tail = serial[2:].lower()
    if len(set(tail)) <= 2 and ("x" in tail or "0" in tail):
        return False
    return True


def _gzo_clean_name(text: str) -> str:
    text = _gzo_ascii(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -:\t\r\n,.")
    if _gzo_has_bad_text(text) or not text:
        return "GZO Serial"
    # Do not let HTML/JSON fragments become visible rows.
    if re.search(r'[{}<>]|[A-Za-z0-9_]+\s*[:=]\s*["\']', text):
        return "GZO Serial"
    if text.count('"') >= 2 or text.count(',') >= 4:
        return "GZO Serial"
    return text[:96]


def _gzo_json_value(context: str, *keys: str) -> str:
    for key in keys:
        # JSON property near the serial. Allows escaped characters but keeps it simple/safe.
        m = re.search(r'["\']' + re.escape(key) + r'["\']\s*:\s*["\']((?:\\.|[^"\']){1,180})["\']', context, re.I | re.S)
        if m:
            try:
                return _gzo_ascii(json.loads('"' + m.group(1).replace('"', '\"') + '"'))
            except Exception:
                return _gzo_ascii(m.group(1))
    return ""


def _gzo_get_field(obj: dict, *keys: str) -> str:
    """Case-insensitive JSON field helper for the GZO catalog payloads."""
    if not isinstance(obj, dict):
        return ""
    lower_map = {str(k).lower(): v for k, v in obj.items()}
    for key in keys:
        val = obj.get(key)
        if val is None:
            val = lower_map.get(str(key).lower())
        if val is not None and not isinstance(val, (dict, list)):
            return _gzo_ascii(str(val))
    return ""


def _gzo_normalize_listing(*values: str) -> str:
    """Only classify listing as Legit or Modded; do not use item category/type here."""
    joined = " ".join(str(v or "") for v in values).lower()
    # Check Modded first so 'non-legit' never becomes Legit.
    if "modded" in joined or "non-legit" in joined or "nonlegit" in joined or "/modded/" in joined or "listing=modded" in joined:
        return "Modded"
    if "legit" in joined or "/legit/" in joined or "listing=legit" in joined:
        return "Legit"
    return "GZO"


def _gzo_context_listing(source: str, context: str, fallback: str = "") -> str:
    return _gzo_normalize_listing(source, context, fallback)



_GZO_MANUFACTURER_ALIASES = {
    "order": "Order", "jakobs": "Jakobs", "vladof": "Vladof", "ripper": "Ripper", "tediore": "Tediore",
    "torgue": "Torgue", "maliwan": "Maliwan", "daedalus": "Daedalus", "deadlus": "Daedalus",
    "atlas": "Atlas", "hyperion": "Hyperion", "cov": "CoV", "co v": "CoV",
}
_GZO_TYPE_ALIASES = {
    "shield": "Shield", "classmod": "Classmod", "class mod": "Classmod", "class_mod": "Classmod",
    "weapon": "Weapon", "grenade": "Grenade", "gadget": "Gadget", "repkit": "Repkit", "repair kit": "Repkit", "repair_kit": "Repkit",
    "enhancement": "Enhancement", "pistol": "Pistol", "shotgun": "Shotgun", "smg": "SMG", "sniper": "Sniper",
    "assault rifle": "Assault Rifle", "assault_rifle": "Assault Rifle", "assault riffle": "Assault Rifle", "assault_riffle": "Assault Rifle",
    "heavy": "Heavy Weapon", "heavy weapon": "Heavy Weapon",
}
_GZO_RARITY_ALIASES = {"common": "Common", "rare": "Rare", "epic": "Epic", "legendary": "Legendary", "legendr": "Legendary", "legendär": "Legendary", "pearl": "Pearl", "pearlescent": "Pearl", "modded": "Modded"}
_GZO_CLASS_ALIASES = {"siren": "Siren", "paladin": "Paladin", "forgeknight": "Paladin", "gravitar": "Gravitar", "exo soldier": "Exo Soldier", "exo_soldier": "Exo Soldier", "ai": "AI", "c4sh": "C4SH"}


def _gzo_norm_key(text: str) -> str:
    text = html.unescape(str(text or "")).strip().lower()
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def _gzo_tag_values(obj: dict) -> list[str]:
    vals: list[str] = []
    if not isinstance(obj, dict):
        return vals
    for key in ("category", "type", "rarity", "manufacturer", "maker"):
        val = obj.get(key)
        if val is not None and not isinstance(val, (dict, list)):
            vals.append(str(val))
    for key in ("tags", "tag", "labels"):
        val = obj.get(key)
        if isinstance(val, list):
            vals.extend(str(x) for x in val if x is not None and not isinstance(x, (dict, list)))
        elif val is not None and not isinstance(val, dict):
            vals.extend(x.strip() for x in re.split(r"[,|;/]+", str(val)) if x.strip())
    out: list[str] = []
    seen: set[str] = set()
    for v in vals:
        v = _gzo_ascii(str(v)).strip()
        if not v:
            continue
        k = _gzo_norm_key(v)
        if k not in seen:
            seen.add(k); out.append(v)
    return out


def _gzo_classify_tags(tags: list[str]) -> dict[str, str]:
    info = {"manufacturer": "", "type": "", "rarity": "", "character_class": "", "extra_tags": "", "tags": ""}
    extra: list[str] = []
    normalized: list[str] = []
    for raw in tags:
        key = _gzo_norm_key(raw)
        if not key:
            continue
        if key in _GZO_MANUFACTURER_ALIASES:
            val = _GZO_MANUFACTURER_ALIASES[key]
            info["manufacturer"] = info["manufacturer"] or val
            normalized.append(val)
        elif key in _GZO_TYPE_ALIASES:
            val = _GZO_TYPE_ALIASES[key]
            info["type"] = info["type"] or val
            normalized.append(val)
        elif key in _GZO_RARITY_ALIASES:
            val = _GZO_RARITY_ALIASES[key]
            info["rarity"] = info["rarity"] or val
            normalized.append(val)
        elif key in _GZO_CLASS_ALIASES:
            val = _GZO_CLASS_ALIASES[key]
            info["character_class"] = info["character_class"] or val
            normalized.append(val)
        else:
            clean = _gzo_ascii(str(raw)).strip()
            if clean:
                extra.append(clean); normalized.append(clean)
    info["extra_tags"] = ", ".join(extra)
    info["tags"] = ", ".join(normalized)
    return info

def _gzo_meta_label(e: dict[str, str]) -> str:
    parts = []
    for key, title in (("listing", "Listing"), ("type", "Type"), ("manufacturer", "Manufacturer"), ("rarity", "Rarity"), ("creator", "Creator"), ("character_class", "Class"), ("tags", "Tags"), ("extra_tags", "Extra")):
        val = _gzo_ascii(str(e.get(key, ""))).strip()
        if val and val != "GZO":
            parts.append(f"{title}: {val}")
    return " | ".join(parts)


def _gzo_add_entry(out: list[dict[str, str]], seen: set[str], name: str, serial: str, listing: str = "", item_type: str = "", rarity: str = "", maker: str = "", creator: str = "", source: str = "", tags: str = "", character_class: str = "", extra_tags: str = "") -> None:
    serial = str(serial or "").strip()
    if not _gzo_is_valid_serial(serial):
        return
    name = _gzo_clean_name(name)
    if _gzo_has_bad_text(name):
        name = "GZO Serial"
    listing = _gzo_normalize_listing(source, listing)
    if listing == "GZO":
        listing = _gzo_ascii(str(listing or "").strip() or "GZO")
    row_data = {
        "name": name,
        "serial": serial,
        "listing": listing,
        "type": _gzo_ascii(str(item_type or "").strip()),
        "rarity": _gzo_ascii(str(rarity or "").strip()),
        "manufacturer": _gzo_ascii(str(maker or "").strip()),
        "creator": _gzo_ascii(str(creator or "").strip()),
        "character_class": _gzo_ascii(str(character_class or "").strip()),
        "tags": _gzo_ascii(str(tags or "").strip()),
        "extra_tags": _gzo_ascii(str(extra_tags or "").strip()),
        "source": _gzo_ascii(str(source or "").strip()),
    }
    if serial in seen:
        for row in out:
            if str(row.get("serial", "")).strip() == serial:
                for key, val in row_data.items():
                    val = _gzo_ascii(str(val or "")).strip()
                    old = _gzo_ascii(str(row.get(key, ""))).strip()
                    if val and (not old or old == "GZO" or old == "GZO Serial"):
                        row[key] = val
                break
        return
    seen.add(serial)
    row_data["id"] = ""
    out.append(row_data)


def _gzo_walk_json(obj, out: list[dict[str, str]], seen: set[str], source: str, inherited_listing: str = "") -> None:
    if isinstance(obj, dict):
        raw_listing = _gzo_get_field(obj, "targetListing", "listing", "destination", "bucket", "folder", "legitOrModded", "list")
        listing = _gzo_normalize_listing(source, inherited_listing, raw_listing, _gzo_get_field(obj, "txtPath", "path"))
        serial = _gzo_get_field(obj, "base85", "Base85", "serial", "code", "value")
        if isinstance(serial, str) and _gzo_is_valid_serial(serial):
            name = _gzo_get_field(obj, "name", "displayName", "title", "itemName") or "GZO Serial"
            tags_list = _gzo_tag_values(obj)
            classified = _gzo_classify_tags(tags_list)
            item_type = classified.get("type", "")
            rarity = classified.get("rarity", "")
            maker = classified.get("manufacturer", "")
            character_class = classified.get("character_class", "")
            creator = _gzo_get_field(obj, "creator", "author", "creatorName", "owner")
            # Only use deserialized typeID as a narrow fallback for type/class, never as a manufacturer fallback.
            if (not item_type or not character_class) and _gzo_get_field(obj, "deserialized"):
                dm = re.match(r"\s*(\d+)\s*,", _gzo_get_field(obj, "deserialized"))
                if dm:
                    ti = _gzo_type_info_from_id(int(dm.group(1)))
                    if not item_type and ti.get("type"):
                        item_type = ti["type"]
                    if not character_class and ti.get("character_class"):
                        character_class = ti["character_class"]
            _gzo_add_entry(out, seen, str(name), serial, listing, item_type, rarity, maker, creator, source, classified.get("tags", ""), character_class, classified.get("extra_tags", ""))
        for v in obj.values():
            _gzo_walk_json(v, out, seen, source, listing)
    elif isinstance(obj, list):
        for v in obj:
            _gzo_walk_json(v, out, seen, source, inherited_listing)


def _gzo_parse_embedded_json(text: str, out: list[dict[str, str]], seen: set[str], source: str, listing: str) -> None:
    # Handles pages that embed catalog arrays/objects in JS instead of serving pure JSON.
    for m in re.finditer(r"(?:const|let|var)\s+[A-Za-z0-9_$]*\s*=\s*(\[.*?\]|\{.*?\})\s*;", text, re.S):
        chunk = m.group(1)
        if "@U" not in chunk or len(chunk) > 2_500_000:
            continue
        try:
            _gzo_walk_json(json.loads(chunk), out, seen, source, listing)
        except Exception:
            continue


def _gzo_visible_lines(fragment: str) -> list[str]:
    fragment = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"(?i)</(?:div|p|li|h[1-6]|span|button|article|section|tr|td)\s*>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    fragment = html.unescape(fragment)
    lines = []
    for line in re.split(r"[\r\n]+", fragment):
        line = re.sub(r"\s+", " ", line).strip(" -:\t")
        if line:
            lines.append(line)
    return lines


def _gzo_parse_card_html(text: str, out: list[dict[str, str]], seen: set[str], source: str, fallback_listing: str) -> None:
    """Capture GZO's parent card listing label (LEGIT/MODDED) plus visible metadata."""
    for m in _GZO_SERIAL_RE.finditer(text):
        serial = m.group(0)
        if not _gzo_is_valid_serial(serial):
            continue
        before_start = max(0, m.start() - 9000)
        after_end = min(len(text), m.end() + 2500)
        before = text[before_start:m.start()]
        starts = list(re.finditer(r"(?is)(?:>|\b)(LEGIT|MODDED)(?:<|\b)", before))
        if starts:
            card_start = before_start + starts[-1].start()
            listing = starts[-1].group(1).title()
        else:
            card_start = max(0, m.start() - 2500)
            listing = _gzo_normalize_listing(source, fallback_listing)
        fragment = text[card_start:after_end]
        lines = _gzo_visible_lines(fragment)
        visible_before_serial = []
        for line in lines:
            if serial in line or "@U" in line:
                break
            visible_before_serial.append(line)
        if not visible_before_serial:
            continue
        line_listing = _gzo_normalize_listing(listing, " ".join(visible_before_serial[:3]))
        if line_listing in ("Legit", "Modded"):
            listing = line_listing
        non_label = [ln for ln in visible_before_serial if ln.strip().upper() not in ("LEGIT", "MODDED")]
        name = ""
        rarity = maker = item_type = creator = tags = ""
        for ln in non_label:
            low = ln.lower()
            if low.startswith("by "):
                creator = ln[3:].strip()
                continue
            if ("·" in ln or "|" in ln or " / " in ln) and not serial in ln:
                pieces = [x.strip() for x in re.split(r"\s*(?:·|\||/)\s*", ln) if x.strip()]
                if len(pieces) >= 3:
                    rarity, maker, item_type = pieces[0], pieces[1], pieces[2]
                    continue
            if not name and not _gzo_has_bad_text(ln):
                name = ln
        _gzo_add_entry(out, seen, name or "GZO Serial", serial, listing, item_type, rarity, maker, creator, source, tags)


def _gzo_parse_text(text: str, out: list[dict[str, str]], seen: set[str], source: str, listing: str = "") -> list[str]:
    urls: list[str] = []
    for m in re.finditer(r"(?:src|href)=[\"\']([^\"\']+\.(?:js|json|txt|php)(?:\?[^\"\']*)?)[\"\']", text, re.I):
        urls.append(_gzo_url_join(source, m.group(1)))
    for m in re.finditer(r"[\"\']([^\"\']*codes/[^\"\']+\.(?:json|txt|php)(?:\?[^\"\']*)?)[\"\']", text, re.I):
        urls.append(_gzo_url_join(source, m.group(1)))
    try:
        _gzo_walk_json(json.loads(text), out, seen, source, listing)
    except Exception:
        _gzo_parse_embedded_json(text, out, seen, source, listing)
    _gzo_parse_card_html(text, out, seen, source, listing)

    # Last-resort scan, but use JSON/property context and reject HTML/JS noise.
    for m in _GZO_SERIAL_RE.finditer(text):
        serial = m.group(0)
        if not _gzo_is_valid_serial(serial):
            continue
        ctx_start = max(0, m.start() - 1800)
        ctx_end = min(len(text), m.end() + 900)
        context = text[ctx_start:ctx_end]
        name = _gzo_json_value(context, "name", "displayName", "title", "itemName")
        item_type = _gzo_json_value(context, "type", "itemType")
        rarity = _gzo_json_value(context, "rarity")
        maker = _gzo_json_value(context, "manufacturer", "maker")
        creator = _gzo_json_value(context, "creator", "author")
        local_listing = _gzo_context_listing(source, context, listing)
        if not name:
            # Plain text fallback: take the nearest clean line before the serial only.
            before = context[:m.start() - ctx_start]
            before = re.sub(r"<[^>]+>", " ", before)
            before = re.sub(r"[@A-Za-z0-9!#$%&()*+\-;<=>?^_`{/}~]{40,}", " ", before)
            bits = [_gzo_clean_name(x) for x in re.split(r"[\r\n|]+", before) if _gzo_clean_name(x)]
            bits = [x for x in bits if not _gzo_has_bad_text(x)]
            name = bits[-1] if bits else "GZO Serial"
        tags = _gzo_json_value(context, "tags", "tag", "notes")
        _gzo_add_entry(out, seen, name, serial, local_listing, item_type, rarity, maker, creator, source, tags)
    return urls


def _gzo_scrape_catalog_worker_body() -> tuple[list[dict[str, str]], list[str]]:
    base = _gzo_url
    out: list[dict[str, str]] = []
    seen_serials: set[str] = set()
    to_fetch = [base]
    for rel in (
        "codes/api.php?action=list",
        "codes/api.php?action=list&listing=Legit",
        "codes/api.php?action=list&listing=Modded",
        "codes/api.php?action=catalog",
        "codes/api.php?action=catalog&listing=Legit",
        "codes/api.php?action=catalog&listing=Modded",
        "codes/api.php?action=items",
        "codes/catalog.json", "codes/index.json", "codes/manifest.json",
        "codes/Legit/index.json", "codes/Modded/index.json",
        "codes/Legit/manifest.json", "codes/Modded/manifest.json",
    ):
        to_fetch.append(_gzo_url_join(base, rel))
    fetched: set[str] = set()
    errors: list[str] = []
    i = 0
    while i < len(to_fetch) and len(fetched) < 80:
        url = to_fetch[i]; i += 1
        if url in fetched:
            continue
        fetched.add(url)
        try:
            text = _gzo_fetch_text(url)
            time.sleep(_GZO_HTTP_THROTTLE_SEC)
            more = _gzo_parse_text(text, out, seen_serials, url, "Legit" if "/Legit/" in url else ("Modded" if "/Modded/" in url else ""))
            for u in more:
                if u not in fetched and len(to_fetch) < 120:
                    to_fetch.append(u)
        except Exception as exc:
            if len(errors) < 3:
                errors.append(f"{url.rsplit('/',1)[-1]}: {exc}")
    cleaned: list[dict[str, str]] = []
    for e in out:
        if not _gzo_is_valid_serial(str(e.get("serial", ""))):
            continue
        if _gzo_has_bad_text(" ".join(str(e.get(k, "")) for k in ("name", "type", "rarity", "manufacturer", "creator", "tags"))):
            continue
        e["id"] = _gzo_entry_id(e)
        cleaned.append(e)
    return cleaned, errors


def _gzo_refresh_worker() -> None:
    global _gzo_refresh_result
    try:
        entries, errors = _gzo_scrape_catalog_worker_body()
        result: tuple[list[dict[str, str]] | None, str | None, list[str]] = (entries, None, errors)
    except Exception as exc:
        result = (None, str(exc), [])
    with _async_refresh_lock:
        _gzo_refresh_result = result


def _gzo_refresh_catalog() -> None:
    global _gzo_refresh_thread, _gzo_refresh_result, _gzo_status
    try:
        from . import runtime_log

        runtime_log.note("GZO catalog refresh started (throttled HTTP — avoid during game load).")
    except Exception:
        pass
    with _async_refresh_lock:
        if _gzo_refresh_thread is not None and _gzo_refresh_thread.is_alive():
            _gzo_status = "GZO refresh is already running in the background..."
            return
        _gzo_refresh_result = None
        _gzo_status = "Refreshing GZO in the background..."
        _set_gzo_refresh_progress("GZO: queued", 0, 0, len(_gzo_entries), True)
        _gzo_refresh_thread = threading.Thread(target=_gzo_refresh_worker, name="Squ1ggs GZO Refresh", daemon=True)
        _gzo_refresh_thread.start()


def _poll_gzo_refresh_result() -> None:
    global _gzo_entries, _gzo_status, _gzo_last_refresh, _gzo_active_id, _gzo_selected_ids, _gzo_refresh_result
    with _async_refresh_lock:
        result = _gzo_refresh_result
        _gzo_refresh_result = None
    if result is None:
        return
    entries, error, errors = result
    if error is not None:
        _gzo_status = f"GZO refresh failed: {error}"
        _set_gzo_refresh_progress(_gzo_status, 0, 0, 0, False)
        _log(_gzo_status)
        return
    cleaned = list(entries or [])
    _gzo_entries = cleaned
    _gzo_selected_ids = {eid for eid in _gzo_selected_ids if eid in {str(e.get("id", "")) for e in cleaned}}
    _gzo_last_refresh = time.time()
    if cleaned:
        _gzo_save_cache()
        if not _gzo_active_id or _gzo_active_id not in {str(e.get("id", "")) for e in cleaned}:
            _gzo_active_id = cleaned[0].get("id", "")
        _gzo_status = f"Loaded {len(cleaned)} valid GZO code(s) from save-editor.be."
        _set_gzo_refresh_progress(_gzo_status, len(cleaned), len(cleaned), len(cleaned), False)
    else:
        _gzo_active_id = ""
        _gzo_status = "No valid @U codes found. The site may have changed its catalog endpoint or blocked in-game HTTP. " + ("; ".join(errors) if errors else "")
        _set_gzo_refresh_progress(_gzo_status, 0, 0, 0, False)
    _log(_gzo_status)


def _gzo_filter_options(field: str) -> list[str]:
    from . import gzo_filters

    if field == "category":
        vals = {gzo_filters.item_category(str(e.get("type", ""))) for e in _gzo_entries}
        return ["All"] + gzo_filters.ordered_labels(list(vals), gzo_filters.CATEGORY_ORDER)
    if field == "type":
        cat_options = _gzo_filter_options("category")
        want_cat = _gzo_filter_value(cat_options, _gzo_category_filter_index)
        pool = _gzo_entries
        if want_cat != "All":
            pool = [e for e in _gzo_entries if gzo_filters.item_category(str(e.get("type", ""))) == want_cat]
        vals = {gzo_filters.normalize_type(str(e.get("type", ""))) for e in pool}
        vals.discard("")
        return ["All"] + gzo_filters.ordered_labels(list(vals), gzo_filters.TYPE_ORDER)
    vals = sorted(
        {
            _gzo_ascii(str(e.get(field, ""))).strip()
            for e in _gzo_entries
            if _gzo_ascii(str(e.get(field, ""))).strip() and _gzo_ascii(str(e.get(field, ""))).strip() != "GZO"
        },
        key=lambda x: x.lower(),
    )
    return ["All"] + vals


def _gzo_filter_value(options: list[str], idx: int) -> str:
    return options[max(0, min(int(idx), len(options) - 1))] if options else "All"


def _gzo_filtered_entries() -> list[dict[str, str]]:
    entries = list(_gzo_entries)
    filt = _GZO_LISTING_FILTERS[max(0, min(_gzo_listing_index, len(_GZO_LISTING_FILTERS)-1))]
    if filt != "All":
        entries = [e for e in entries if str(e.get("listing", "")).strip().lower() == filt.lower()]
    from . import gzo_filters

    cat_options = _gzo_filter_options("category")
    cat_val = _gzo_filter_value(cat_options, _gzo_category_filter_index)
    if cat_val != "All":
        entries = [e for e in entries if gzo_filters.item_category(str(e.get("type", ""))) == cat_val]
    for field, idx in (
        ("type", _gzo_type_filter_index),
        ("manufacturer", _gzo_manufacturer_filter_index),
        ("rarity", _gzo_rarity_filter_index),
        ("creator", _gzo_creator_filter_index),
    ):
        options = _gzo_filter_options(field)
        val = _gzo_filter_value(options, idx)
        if val != "All":
            if field == "type":
                entries = [
                    e
                    for e in entries
                    if gzo_filters.normalize_type(str(e.get("type", ""))).lower() == val.lower()
                ]
            else:
                entries = [e for e in entries if str(e.get(field, "")).strip().lower() == val.lower()]
    q = (_gzo_search or "").strip().lower()
    if q:
        entries = [e for e in entries if q in " ".join(str(e.get(k, "")) for k in ("name", "listing", "type", "rarity", "manufacturer", "creator", "character_class", "tags", "extra_tags", "serial")).lower()]
    return _sort_favorites_first(entries, "serial", _favorite_gzo_serials)


def _gzo_active_entry() -> dict[str, str] | None:
    for e in _gzo_entries:
        if str(e.get("id", "")) == _gzo_active_id:
            return e
    return _gzo_entries[0] if _gzo_entries else None


def _gzo_selected_entries() -> list[dict[str, str]]:
    return [e for e in _gzo_entries if str(e.get("id", "")) in _gzo_selected_ids]


def _gzo_select_all_filtered(entries: list[dict[str, str]]) -> None:
    for e in entries:
        eid = str(e.get("id", ""))
        if eid:
            _gzo_selected_ids.add(eid)



def _gzo_import_selected_to_store() -> None:
    """Import selected GZO entries into Serial Store without using any non-ASCII UI markers."""
    global _gzo_status, _serial_store_status
    _serial_store_load()
    entries = _gzo_selected_entries()
    if not entries:
        active = _gzo_active_entry()
        entries = [active] if active else []
    valid_entries = []
    existing_serials = {str(e.get("serial", "")).strip() for e in _serial_store_entries}
    for e in entries:
        if not e:
            continue
        serial = str(e.get("serial", "")).strip()
        if not _gzo_is_valid_serial(serial):
            continue
        valid_entries.append(e)
    if not valid_entries:
        _gzo_status = "No selected valid @U GZO serials to import."
        return
    added = 0
    skipped = 0
    for e in valid_entries:
        serial = str(e.get("serial", "")).strip()
        if serial in existing_serials:
            skipped += 1
            continue
        name = _gzo_clean_name(str(e.get("name", "GZO Serial"))) or "GZO Serial"
        listing = _gzo_ascii(str(e.get("listing", "GZO")) or "GZO")
        rarity = _gzo_ascii(str(e.get("rarity", "")))
        group = "GZO"
        if listing and listing.lower() not in ("gzo", "all"):
            group = "GZO - " + listing
        elif rarity:
            group = "GZO - " + rarity
        _serial_store_entries.append({
            "id": _serial_store_new_id(),
            "name": name,
            "group": group,
            "serial": serial,
        })
        existing_serials.add(serial)
        added += 1
    if added:
        _serial_store_save()
    _gzo_status = f"Imported {added} GZO serial(s) to Serial Store" + (f"; skipped {skipped} duplicate(s)." if skipped else ".")
    _serial_store_status = _gzo_status
    _log(_gzo_status)


def _gzo_copy_selected_serials() -> None:
    global _gzo_status
    entries = _gzo_selected_entries()
    if not entries:
        active = _gzo_active_entry()
        entries = [active] if active else []
    count = _copy_serial_list_to_clipboard("selected GZO serials", entries)
    _gzo_status = f"Copied {count} selected GZO serial(s) to clipboard." if count else "Select one or more GZO serials to copy."


def _gzo_deliver_selected(mode: str = "selected") -> None:
    """Deliver selected GZO serials to the GZO Target only (targeted Item Serial grants)."""
    global _gzo_status, _gzo_delivery_override_level, _gzo_delivery_level
    entries = _gzo_selected_entries()
    if not entries:
        active = _gzo_active_entry()
        entries = [active] if active else []
    serials = []
    for e in entries:
        if not e:
            continue
        serial = str(e.get("serial", "")).strip()
        if _gzo_is_valid_serial(serial):
            serials.append(serial)
    if not serials:
        _gzo_status = "Select one or more valid GZO serials first."
        _log("GZO Codes: no valid serials selected.")
        return
    serials, changed, error = _serials_with_level_override(serials, _gzo_delivery_override_level, _gzo_delivery_level)
    if error:
        _gzo_status = error
        _log(_gzo_status)
        return
    _gzo_status = _deliver_serials_with_target(serials, mode, "GZO Codes")
    if changed:
        _gzo_status += f" Level override: {changed} serial(s) set to level {_clamp_int(_gzo_delivery_level, 1, _MAX_PLAYER_LEVEL)}."
    _log(f"GZO Codes delivered {len(serials)} serial(s): {_gzo_status}")

def _draw_gzo_codes_tab() -> None:
    global _gzo_search, _gzo_listing_index, _gzo_category_filter_index, _gzo_type_filter_index, _gzo_manufacturer_filter_index, _gzo_rarity_filter_index, _gzo_creator_filter_index, _gzo_player_index, _gzo_active_id, _gzo_cache_autoload_attempted, _gzo_delivery_override_level, _gzo_delivery_level
    imgui = _blimgui.imgui
    opened = _sq_begin_card("GZO Codes", "gzo", _tab_card_height(780.0))
    if opened:
        if not _gzo_cache_autoload_attempted and not _gzo_entries:
            _gzo_cache_autoload_attempted = True
            _gzo_load_cache(silent=True)
        imgui.text_wrapped("Cached GZO BL4 Codes catalog")
        _muted_wrapped(
            "Catalog from save-editor.be (GZO BL4 Items). "
            "Thank you to Tobgun for feedback, ideas, testing, and bug reports. "
            "Loads cached serials automatically when available. Refresh GZO updates the local cache in the background."
        )
        _button("Load Cache", _gzo_load_cache, "cyan", 110, 0)
        imgui.same_line(); _button("Refresh GZO", _gzo_refresh_catalog, "gold", 130, 0)
        imgui.same_line(); _button("Copy Selected", _gzo_copy_selected_serials, "purple", 130, 0)
        imgui.same_line(); _button("Import Selected To Store", _gzo_import_selected_to_store, "purple", 210, 0)
        _draw_gzo_refresh_progress()
        _gzo_delivery_override_level, _gzo_delivery_level = _draw_catalog_level_override("gzo", _gzo_delivery_override_level, _gzo_delivery_level)
        imgui.separator()
        _gzo_search = _input_text("Search###gzo_search", _gzo_search, 256)
        _gzo_listing_index = _combo("Listing###gzo_listing", _gzo_listing_index, _GZO_LISTING_FILTERS)
        imgui.same_line()
        prev_cat = _gzo_category_filter_index
        _gzo_category_filter_index = _combo("Category###gzo_category", _gzo_category_filter_index, _gzo_filter_options("category"))
        if _gzo_category_filter_index != prev_cat:
            _gzo_type_filter_index = 0
        imgui.same_line()
        type_opts = _gzo_filter_options("type")
        if _gzo_type_filter_index >= len(type_opts):
            _gzo_type_filter_index = 0
        _gzo_type_filter_index = _combo("Type###gzo_type", _gzo_type_filter_index, type_opts)
        _gzo_manufacturer_filter_index = _combo("Manufacturer###gzo_manufacturer", _gzo_manufacturer_filter_index, _gzo_filter_options("manufacturer"))
        imgui.same_line(); _gzo_rarity_filter_index = _combo("Rarity###gzo_rarity", _gzo_rarity_filter_index, _gzo_filter_options("rarity"))
        _gzo_creator_filter_index = _combo("Creator###gzo_creator", _gzo_creator_filter_index, _gzo_filter_options("creator"))
        filtered = _gzo_filtered_entries()
        imgui.text_wrapped(f"{len(filtered)} shown / {len(_gzo_entries)} loaded | {len(_gzo_selected_ids)} selected")
        _button("Select All", lambda: _gzo_select_all_filtered(filtered), "purple", 110, 0)
        imgui.same_line(); _button("Clear", lambda: _gzo_selected_ids.clear(), "pink", 80, 0)
        gzo_preview = _gzo_active_entry()
        gzo_serial = str((gzo_preview or {}).get("serial", "")).strip()
        gzo_fav_label = (
            "Unfavorite Selected"
            if gzo_serial and _is_favorite(gzo_serial, _favorite_gzo_serials)
            else "Favorite Selected"
        )
        imgui.same_line(); _button(gzo_fav_label, _toggle_active_gzo_favorite, "purple", 170, 0)
        columns = getattr(imgui, "columns", None); next_column = getattr(imgui, "next_column", None); using_columns = False
        if callable(columns) and callable(next_column):
            try:
                columns(2, "sqbt_gzo_codes_columns", True); using_columns = True
            except Exception:
                try: columns(2); using_columns = True
                except Exception: using_columns = False
        imgui.text_wrapped("CODES")
        child_open = _begin_child_region("sqbt_gzo_codes_list", 430.0)
        try:
            if not filtered:
                imgui.text_wrapped("No GZO codes loaded/matching. Click Load Cache or Refresh GZO.")
            for index, e in enumerate(filtered):
                eid = str(e.get("id", ""))
                serial = str(e.get("serial", "")).strip()
                fav = _is_favorite(serial, _favorite_gzo_serials)
                if imgui.small_button(f"{'−' if fav else '+'}###sqbt_gzofav_{index}_{eid}"):
                    _toggle_serial_favorite(
                        serial,
                        _favorite_gzo_serials,
                        _favorite_gzo_descriptions,
                        label="GZO",
                        display_name=str(e.get("name", "")),
                    )
                imgui.same_line()
                checked = "[X]" if eid in _gzo_selected_ids else "[ ]"
                active = "> " if eid == _gzo_active_id else "  "
                listing = str(e.get("listing", "")).strip()
                prefix = f"[{listing.upper()}] " if listing in ("Legit", "Modded") else ""
                meta = " | ".join(x for x in [str(e.get("type", "")), str(e.get("manufacturer", "")), str(e.get("rarity", "")), str(e.get("character_class", "")), str(e.get("creator", ""))] if x and x != "GZO")
                fav_prefix = _fav_prefix(serial, _favorite_gzo_serials)
                label = (
                    f"{active}{checked} {fav_prefix}{prefix}{e.get('name','GZO Serial')}"
                    f"{_fav_description(serial, _favorite_gzo_descriptions)}    {meta}###gzo_row_{eid}"
                )
                if _selectable_row(label, eid == _gzo_active_id):
                    _gzo_active_id = eid
                    if eid in _gzo_selected_ids: _gzo_selected_ids.discard(eid)
                    else: _gzo_selected_ids.add(eid)
        finally:
            if child_open: _end_child_region()
        if using_columns: next_column()
        imgui.text_wrapped("DETAILS")
        active = _gzo_active_entry()
        if active:
            imgui.text_wrapped(str(active.get("name", "GZO Serial")))
            _muted_wrapped(_gzo_meta_label(active))
            _input_text_multiline("Serial###gzo_active_serial", str(active.get("serial", "")), 65536, width=620, height=190)
            _draw_favorite_description_editor(
                "Favorite note###gzo_fav_note",
                str(active.get("serial", "")).strip(),
                _favorite_gzo_serials,
                _favorite_gzo_descriptions,
            )
            _button("Copy Serial", lambda: _copy_text_to_clipboard("GZO serial", str(active.get("serial", ""))), "purple", 130, 0)
            imgui.same_line(); _button("Import This", lambda: (_gzo_selected_ids.add(str(active.get("id", ""))), _gzo_import_selected_to_store()), "cyan", 120, 0)
        else:
            imgui.text_wrapped("Select a GZO code to preview its serial.")
        if using_columns:
            try: columns(1)
            except Exception: pass
        imgui.separator()
        _muted_wrapped(
            f"{len(_gzo_selected_entries())} selected | Delivery goes to the lobby target at the top "
            "(tick-paced packages — does not freeze the host). Open reward mail to claim."
        )
        imgui.same_line(); _button("Deliver Selected", lambda: _gzo_deliver_selected("selected"), "purple", 165, 0)
        imgui.same_line(); _button("Deliver All Selected", lambda: _gzo_deliver_selected("all"), "gold", 175, 0)
        imgui.same_line(); _button("Deliver Non-Host", lambda: _gzo_deliver_selected("nonhost"), "cyan", 185, 0)
        live = serial_delivery_status()
        if live:
            imgui.text_wrapped(f"Delivery: {live}")
        imgui.text_wrapped(_gzo_status)
    _sq_end_card()

def _draw_serial_store_tab() -> None:
    global _serial_store_name, _serial_store_group, _serial_store_serial, _serial_store_group_filter_index, _serial_store_player_index, _serial_store_search
    imgui = _blimgui.imgui
    _serial_store_load()
    opened = _sq_begin_card("Serial Store", "serial_store", _tab_card_height(760.0))
    if opened:
        # Header: task name + obvious new action.
        imgui.text_wrapped("Serial Store")
        imgui.same_line(); _button("+ New Serial", _serial_store_clear_form, "cyan", 150, 0)
        imgui.same_line(); _button("Import", _serial_store_import_from_tools, "gold", 105, 0)
        _muted_wrapped("Browse saved serials, edit the active entry, then deliver the checked items from the footer.")
        imgui.separator()

        # Toolbar: search + group filter.
        _serial_store_search = _input_text("Search###serial_store_search", _serial_store_search, 256)
        groups = _serial_store_groups()
        _serial_store_group_filter_index = _combo("Groups###serial_store_groups", _serial_store_group_filter_index, groups)
        imgui.separator()

        filtered = _serial_store_filtered_entries()
        search = (_serial_store_search or "").strip().lower()
        if search:
            filtered = [
                e for e in filtered
                if search in str(e.get("name", "")).lower()
                or search in str(e.get("group", "Default")).lower()
                or search in str(e.get("serial", "")).lower()
            ]

        columns = getattr(imgui, "columns", None)
        next_column = getattr(imgui, "next_column", None)
        using_columns = False
        if callable(columns) and callable(next_column):
            try:
                columns(2, "sqbt_serial_store_browse_edit_columns", True)
                using_columns = True
            except TypeError:
                try:
                    columns(2)
                    using_columns = True
                except Exception:
                    using_columns = False
            except Exception:
                using_columns = False

        # Left pane: browse/select.
        imgui.text_wrapped("SERIALS")
        selected_count = len(_serial_store_selected_entries())
        imgui.text_wrapped(f"{len(filtered)} shown / {len(_serial_store_entries)} saved | {selected_count} selected")
        _button("Select All", lambda: _serial_store_select_all_filtered(filtered), "purple", 110, 0)
        imgui.same_line(); _button("Clear", lambda: _serial_store_selected_ids.clear(), "pink", 80, 0)
        child_open = _begin_child_region("sqbt_serial_store_browser", 405.0)
        try:
            if not filtered:
                imgui.text_wrapped("No saved serials match this search/group.")
            for e in filtered:
                eid = str(e.get("id", ""))
                checked = "[X]" if eid in _serial_store_selected_ids else "[ ]"
                active = "> " if eid == _serial_store_active_id else "  "
                name = str(e.get("name") or "Serial")
                group = str(e.get("group") or "Default")
                label = f"{active}{checked} {name}        {group}###serial_store_row_{eid}"
                if _selectable_row(label, eid == _serial_store_active_id):
                    _serial_store_set_active(e)
                    if eid in _serial_store_selected_ids:
                        _serial_store_selected_ids.discard(eid)
                    else:
                        _serial_store_selected_ids.add(eid)
        finally:
            if child_open:
                _end_child_region()

        if using_columns:
            next_column()

        # Right pane: edit details only.
        imgui.text_wrapped("DETAILS")
        _serial_store_name = _input_text("Name###serial_store_name", _serial_store_name, 256)
        _serial_store_group = _input_text("Group###serial_store_group", _serial_store_group, 256)
        _serial_store_serial = _input_text_multiline("Serial###serial_store_serial", _serial_store_serial, 65536, width=620, height=190)
        _button("Save", _serial_store_save_form, "cyan", 95, 0)
        imgui.same_line(); _button("Duplicate", _serial_store_duplicate_active, "purple", 115, 0)
        imgui.same_line(); _button("Delete", _serial_store_delete_active, "red", 90, 0)
        imgui.same_line(); _button("Copy", lambda: _copy_text_to_clipboard("stored serial", _serial_store_serial), "gold", 80, 0)
        imgui.spacing()
        imgui.text_wrapped(_serial_store_status)

        if using_columns:
            try:
                columns(1)
            except Exception:
                pass

        # Sticky-style footer: delivery is separated from editing.
        imgui.separator()
        selected_count = len(_serial_store_selected_entries())
        imgui.text_wrapped(f"{selected_count} selected")
        imgui.same_line()
        imgui.text_wrapped("Delivery goes to the selected target only (no lobby-wide mail).")
        imgui.same_line(); _button("Deliver Selected", lambda: _serial_store_deliver_selected("selected"), "purple", 165, 0)
        imgui.same_line(); _button("Deliver All Selected", lambda: _serial_store_deliver_selected("all"), "gold", 175, 0)
        imgui.same_line(); _button("Deliver Non-Host", lambda: _serial_store_deliver_selected("nonhost"), "cyan", 185, 0)
    _sq_end_card()

def _draw_serial_tools_tab() -> None:
    global _serial_tools_input
    imgui = _blimgui.imgui
    opened = _sq_begin_card("Serial Tools", "serial_tools", 720.0)
    if opened:
        imgui.text_wrapped("Paste a @U serialized value or deserialized human-readable serial below. The converter returns both formats.")
        new_input = _input_text_multiline("Input###sqbt_serial_tools_input", _serial_tools_input, 65536, width=860, height=120)
        if new_input != _serial_tools_input:
            _serial_tools_input = new_input
            _serial_tools_convert()
        _button("Convert", _serial_tools_convert, "cyan", 120, 0)
        imgui.same_line()
        _button("Clear", _clear_serial_tools, "pink", 100, 0)
        imgui.separator()
        imgui.text_wrapped(_serial_tools_status)
        imgui.text_wrapped("Deserialized Output")
        _input_text_multiline("###sqbt_serial_tools_deserialized", _serial_tools_deserialized, 65536, width=860, height=150)
        _button("Copy Deserialized", lambda: _copy_text_to_clipboard("deserialized serial", _serial_tools_deserialized), "purple", 190, 0)
        imgui.separator()
        imgui.text_wrapped("Parts Breakdown")
        _input_text_multiline("###sqbt_serial_tools_parts", _serial_tools_parts_breakdown, 65536, width=860, height=180)
        _button("Copy Parts Breakdown", lambda: _copy_text_to_clipboard("parts breakdown", _serial_tools_parts_breakdown), "purple", 210, 0)
        imgui.separator()
        imgui.text_wrapped("@U Serialized Output")
        _input_text_multiline("###sqbt_serial_tools_serialized", _serial_tools_serialized, 65536, width=860, height=95)
        _button("Copy Serialized", lambda: _copy_text_to_clipboard("serialized @U serial", _serial_tools_serialized), "purple", 170, 0)
    _sq_end_card()


def _clear_serial_tools() -> None:
    global _serial_tools_input, _serial_tools_serialized, _serial_tools_deserialized, _serial_tools_parts_breakdown, _serial_tools_status
    _serial_tools_input = ""
    _serial_tools_serialized = ""
    _serial_tools_deserialized = ""
    _serial_tools_parts_breakdown = ""
    _serial_tools_status = "Paste a @U serial or deserialized serial text above."
    _log("Cleared Serial Tools input/output.")


def _draw_log_card(full_page: bool = False) -> None:
    imgui = _blimgui.imgui
    card_height = _tab_card_height(650.0, 58.0) if full_page else 120.0
    opened = _sq_begin_card("Activity Log", "log", card_height)
    if opened:
        if (_cyber.cyber_button("Clear Log", "pink") if _cyber else imgui.button("Clear Log")):
            _log_lines.clear()
        visible_lines = _log_lines if full_page else _log_lines[-4:]
        child_height = max(90.0, card_height - 62.0) if full_page else 0.0
        child_open = _begin_child_region("sqbt_activity_log_lines", child_height) if full_page else False
        try:
            for line in visible_lines:
                imgui.text_wrapped(line)
        finally:
            if child_open:
                _end_child_region()
    _sq_end_card()




def _begin_child_region(label: str, height: float) -> bool:
    imgui = _blimgui.imgui
    begin_child = getattr(imgui, "begin_child", None)
    if not callable(begin_child):
        return False
    for args in (
        (label, 0, float(height), True),
        (label, 0.0, float(height), True),
        (label, (0, float(height)), True),
        (label, 0, float(height)),
        (label, (0, float(height))),
    ):
        try:
            begin_child(*args)
            _note_child_begun()
            return True
        except TypeError:
            continue
        except Exception as exc:
            _log(f"begin_child unavailable for {label}: {exc!r}")
            return False
    return False


def _end_child_region() -> None:
    imgui = _blimgui.imgui
    end_child = getattr(imgui, "end_child", None)
    if callable(end_child):
        try:
            end_child()
            _note_child_ended()
        except Exception:
            pass




def _imgui_available_height(default: float = 640.0) -> float:
    """Best-effort available content height for resize-friendly tab panels."""
    imgui = _blimgui.imgui
    for name in ("get_content_region_avail", "get_content_region_available"):
        fn = getattr(imgui, name, None)
        if not callable(fn):
            continue
        try:
            value = fn()
        except Exception:
            continue
        try:
            if isinstance(value, (tuple, list)) and len(value) >= 2:
                return max(220.0, float(value[1]))
            y = getattr(value, "y", None)
            if y is not None:
                return max(220.0, float(y))
        except Exception:
            continue
    return float(default)


def _tab_card_height(default: float = 640.0, bottom_padding: float = 28.0) -> float:
    return max(float(default), _imgui_available_height(default) - float(bottom_padding))


def _remaining_child_height(default: float = 300.0, bottom_padding: float = 70.0) -> float:
    return max(float(default), _imgui_available_height(default) - float(bottom_padding))

def _selectable_row(label: str, selected: bool) -> bool:
    imgui = _blimgui.imgui
    selectable = getattr(imgui, "selectable", None)
    if callable(selectable):
        for args in ((label, selected), (label,)):
            try:
                result = selectable(*args)
                if isinstance(result, tuple):
                    return bool(result[0])
                return bool(result)
            except TypeError:
                continue
            except Exception:
                break
    # Fallback: button rows. Prefix the active row so older BLImGui builds still show selection.
    return imgui.button(("> " if selected else "  ") + label)


def _draw_rewards_hub_layout() -> None:
    """Squ1ggs hub: command deck on top, economy left, rewards right, cheats always visible."""
    imgui = _blimgui.imgui
    columns = getattr(imgui, "columns", None)
    next_column = getattr(imgui, "next_column", None)
    if callable(columns) and callable(next_column):
        try:
            columns(2, "sqbt_hub_columns", False)
        except Exception:
            columns = None
    if callable(columns) and callable(next_column):
        _sq_section_header("Economy & Progression", ACCENT_SUCCESS)
        _draw_currency_card()
        _draw_experience_card()
        _draw_inventory_size_card()
        next_column()
        _sq_section_header("Rewards & Extras", ACCENT_PRIMARY)
        _draw_serial_card()
        _draw_sdu_card()
        _draw_rarity_card()
        try:
            columns(1)
        except Exception:
            pass
    elif _cyber:
        _cyber.two_columns(
            lambda: (
                _sq_section_header("Economy & Progression", ACCENT_SUCCESS),
                _draw_currency_card(),
                _draw_experience_card(),
                _draw_inventory_size_card(),
            ),
            lambda: (
                _sq_section_header("Rewards & Extras", ACCENT_PRIMARY),
                _draw_serial_card(),
                _draw_sdu_card(),
                _draw_rarity_card(),
            ),
            "sqbt_hub_columns",
        )
    else:
        _draw_currency_card()
        _draw_experience_card()
        _draw_inventory_size_card()
        _draw_serial_card()
        _draw_sdu_card()
        _draw_rarity_card()
    imgui.spacing()
    # Always expanded — was buried under Squ1ggs collapsing_header.
    _draw_dev_tools_card()


def _draw_command_deck(players: list[tuple[int, str]], labels: list[str]) -> None:
    """Target picker, quick max, quick mods, and cosmetics on the main Rewards Hub row."""
    imgui = _blimgui.imgui
    _draw_cosmetics_quick()
    columns = getattr(imgui, "columns", None)
    next_column = getattr(imgui, "next_column", None)
    if callable(columns) and callable(next_column):
        try:
            columns(2, "sqbt_command_deck", False)
        except Exception:
            columns = None
    if callable(columns) and callable(next_column):
        _draw_target_bar(players, labels)
        next_column()
        _draw_quick_max()
        try:
            columns(1)
        except Exception:
            pass
    else:
        _draw_target_bar(players, labels)
        _draw_quick_max()
    _draw_quick_mods("deck")


def _draw_three_column_boosting() -> None:
    """Legacy entry — Squ1ggs uses _draw_rewards_hub_layout."""
    _draw_rewards_hub_layout()


def _draw_rarity_card() -> None:
    def _begin_card(title: str, accent: str, height: float) -> bool:
        return _sq_begin_card(title, "rarity", height)

    def _end_card() -> None:
        _sq_end_card()

    _rarity_weights.draw_card(
        button=_button,
        checkbox=_checkbox,
        input_float_slider=_input_float_slider,
        muted_wrapped=_muted_wrapped,
        begin_card=_begin_card,
        end_card=_end_card,
        log=_log,
    )


def _set_active_tab(index: int) -> None:
    global _active_tab
    _active_tab = max(0, min(int(index), len(_TAB_LABELS) - 1))


_TAB_LABELS: tuple[str, ...] = (
    "Home",
    "Player",
    "Progression / UVHM",
    "Loot",
    "Serials",
    "Mobility",
    "Player Movement",
    "Vehicle",
    "Damage & More",
    "Kits & Shields",
    "World",
    "Loot Shapes",
    "Activity",
)

_FEATURE_REGISTRY: tuple[tuple[str, str, int, int], ...] = (
    ("Party target", "player target select recipient kick lobby", 1, 0),
    ("Quick player mods", "god mode notarget cheats perks", 1, 0),
    ("Mobility", "teleport move players fly speed noclip time", 5, 0),
    ("Player movement", "walk sprint jump glide vault friction player_move", 6, 0),
    ("Vehicle movement", "vehicle spawn summon handling boost jump", 7, 0),
    ("Damage tuning", "outgoing incoming damage combat bdam", 8, 0),
    ("Kits & Shields tuning", "repair kit shield second wind ammo brc cooldown", 9, 0),
    ("UVHM completion", "ultimate vault hunter rank challenge progression", 2, 0),
    ("Experience and level", "xp level skill points progression", 2, 0),
    ("Currency and SDUs", "cash eridium money inventory capacity", 2, 0),
    ("Loot Pool Spawner", "loot weapon shield world drop pool", 3, 0),
    ("Serial lab", "serial decode encode converter", 4, 0),
    ("Serial library", "saved serials named library", 4, 1),
    ("GZO catalog", "gzo codes catalog serial", 4, 2),
    ("Lootlemon catalog", "lootlemon item codes serial", 4, 3),
    ("Mob spawner", "spawn enemy boss char bms mob encounter", 10, 0),
    ("BMS group spawner", "bms group wave spawn char mob pack", 10, 1),
    ("Mix spawn groups", "world mix painter group spawn", 10, 2),
    ("Fast travel", "map station travel", 10, 3),
    ("Loot Shapes", "loot shape star rings pile arrange teleport ground", 11, 0),
    ("Activity log", "status errors history log", 12, 0),
)


def _draw_tab_row(indices: range, *, row_label: str = "") -> None:
    imgui = _blimgui.imgui
    if row_label:
        imgui.text_disabled(row_label)
    for index in indices:
        short = TAB_SHORT_LABELS[index] if index < len(TAB_SHORT_LABELS) else _TAB_LABELS[index]
        display = f"[ {short} ]" if _active_tab == index else short
        accent = TAB_ACCENTS[index % len(TAB_ACCENTS)]
        width = max(112.0, min(148.0, 76.0 + len(short) * 5.0))
        _button(display, lambda index=index: _set_active_tab(index), accent, width, 0)
        if index != indices[-1]:
            imgui.same_line()


def _draw_tabs() -> None:
    imgui = _blimgui.imgui
    split = max(1, min(int(TAB_ROW_SPLIT), len(_TAB_LABELS)))
    _draw_tab_row(range(0, split))
    if split < len(_TAB_LABELS):
        _draw_tab_row(range(split, len(_TAB_LABELS)))
    imgui.separator()


def _open_workspace(index: int, subview: int = 0) -> None:
    global _loot_view, _serial_view, _world_view
    _set_active_tab(index)
    if index == 3:
        _loot_view = subview
    elif index == 4:
        _serial_view = subview
    elif index == 10:
        _world_view = subview


def _jump_to_feature(label: str, tab: int, subview: int) -> None:
    global _feature_jump_label
    _feature_jump_label = label
    _open_workspace(tab, subview)


def _draw_feature_palette() -> None:
    global _feature_search
    imgui = _blimgui.imgui
    _feature_search = _input_text("Find a tool###sqbt_feature_search", _feature_search, 128)
    query = " ".join(_feature_search.casefold().split())
    if not query:
        _muted_wrapped("Search by task, for example: UVHM, serial, travel, target, or loot.")
        return
    tokens = query.split()
    matches = [
        row
        for row in _FEATURE_REGISTRY
        if all(token in f"{row[0]} {row[1]}".casefold() for token in tokens)
    ][:8]
    if not matches:
        _muted_wrapped("No matching feature.")
        return
    for position, (label, _keywords, tab, subview) in enumerate(matches):
        _button(
            f"{label}  →  {_TAB_LABELS[tab]}",
            lambda label=label, tab=tab, subview=subview: _jump_to_feature(label, tab, subview),
            ACCENT_INFO,
            240.0,
            0.0,
        )
        if position % 3 != 2 and position != len(matches) - 1:
            imgui.same_line()


def _draw_subnav(labels: tuple[str, ...], active: int, setter: Callable[[int], None]) -> None:
    imgui = _blimgui.imgui
    for index, label in enumerate(labels):
        _button(f"[ {label} ]" if index == active else label, lambda index=index: setter(index), ACCENT_INFO, 150.0, 0.0)
        if index != len(labels) - 1:
            imgui.same_line()
    imgui.separator()


def _set_loot_view(value: int) -> None:
    global _loot_view
    _loot_view = max(0, min(1, int(value)))


def _set_serial_view(value: int) -> None:
    global _serial_view
    _serial_view = max(0, min(2, int(value)))


def _set_world_view(value: int) -> None:
    global _world_view
    _world_view = max(0, min(3, int(value)))


def _draw_loot_workspace() -> None:
    _draw_item_pool_tab()


def _draw_loot_feed_card() -> None:
    """Removed from UI — Appear* loot feed is still a no-op on this build."""
    return


def _draw_serial_workspace() -> None:
    global _serial_view
    _draw_subnav(
        ("My Library", "GZO", "Lootlemon"),
        _serial_view,
        _set_serial_view,
    )
    (_draw_serial_store_tab, _draw_gzo_codes_tab, _draw_lootlemon_codes_tab)[_serial_view]()


def _draw_world_workspace() -> None:
    global _world_view
    _draw_subnav(("Mob Spawner", "BMS groups", "Mix Groups", "Fast Travel"), _world_view, _set_world_view)
    if _world_view == 0:
        _draw_mob_spawner_tab()
    elif _world_view == 1:
        _draw_encounter_builder_tab()
    elif _world_view == 2:
        _draw_world_spawn_tab()
    else:
        _draw_travel_tab()


def _draw_loot_shapes_tab() -> None:
    global _loot_shape_index, _loot_shape_radius, _loot_shape_spacing
    global _loot_shape_per_ring, _loot_shape_include_consumables, _loot_shape_status
    global _loot_shape_z_bias, _loot_shape_stack_height, _loot_shape_settle_index, _loot_shape_drop_height
    global _loot_shape_line_length, _loot_shape_stay_in_air, _loot_shape_peel_after
    from . import loot_shapes

    imgui = _blimgui.imgui
    _sq_section_header("Loot Shapes", ACCENT_WARN)
    _wrapped_text(
        "Pick a shape, then Place Fully. Drop from above is optional. Stay in air keeps 3D up. Stop drop snaps to slots.",
        ACCENT_INFO,
    )
    shapes = loot_shapes.visible_shape_names()
    labels = []
    for name in shapes:
        pretty = loot_shapes.shape_pretty_name(name)
        if name in loot_shapes.SHAPE_3D_NAMES:
            labels.append(f"3D {pretty}")
        else:
            labels.append(pretty)
    settle_names = list(loot_shapes.DROP_MODE_NAMES)
    settle_labels = [s.replace("_", " ") for s in settle_names]
    _loot_shape_index = max(0, min(_loot_shape_index, len(shapes) - 1))
    _loot_shape_settle_index = max(0, min(_loot_shape_settle_index, len(settle_names) - 1))
    try:
        changed, new_idx = imgui.combo("Shape", _loot_shape_index, labels)
        if changed:
            _loot_shape_index = int(new_idx)
            if shapes[_loot_shape_index] == "car":
                _loot_shape_drop_height = 20
    except Exception:
        # Older imgui combo signature
        try:
            prev = _loot_shape_index
            _loot_shape_index = int(imgui.combo("Shape", _loot_shape_index, labels)[1])
            if _loot_shape_index != prev and shapes[_loot_shape_index] == "car":
                _loot_shape_drop_height = 20
        except Exception:
            pass

    _loot_shape_radius = _input_int_clamped("Radius", _loot_shape_radius, 40, 2000)
    _loot_shape_spacing = _input_int_clamped("Spacing", _loot_shape_spacing, 40, 1000)
    _loot_shape_per_ring = _input_int_clamped("Per ring", _loot_shape_per_ring, 4, 80)
    _loot_shape_z_bias = _input_int_clamped("Ground height", _loot_shape_z_bias, 0, 250)
    _loot_shape_stack_height = _input_int_clamped("Pile stack height", _loot_shape_stack_height, 0, 400)
    _loot_shape_settle_index = _combo("Drop from above", _loot_shape_settle_index, settle_labels)
    stay_idx = 0 if _loot_shape_stay_in_air else 1
    stay_idx = _combo("Stay in air", stay_idx, ["yes", "no"])
    _loot_shape_stay_in_air = stay_idx == 0
    _loot_shape_peel_after = _input_int_clamped("Then drop after (sec)", _loot_shape_peel_after, 0, 60)
    _loot_shape_drop_height = _input_int_clamped("Drop height", _loot_shape_drop_height, 0, 1200)
    _loot_shape_line_length = _input_int_clamped("Line length", _loot_shape_line_length, 120, 4000)
    include_idx = 1 if _loot_shape_include_consumables else 0
    include_idx = _combo("Include ammo/cash piles", include_idx, ["no", "yes"])
    _loot_shape_include_consumables = include_idx == 1

    payload = {
        "shape": shapes[_loot_shape_index],
        "radius": _loot_shape_radius,
        "spacing": _loot_shape_spacing,
        "per_ring": _loot_shape_per_ring,
        "z_bias": _loot_shape_z_bias,
        "stack_height": _loot_shape_stack_height,
        "settle": settle_names[_loot_shape_settle_index],
        "stay_in_air": "yes" if _loot_shape_stay_in_air else "no",
        "peel_after": _loot_shape_peel_after,
        "drop_height": _loot_shape_drop_height,
        "line_length": _loot_shape_line_length,
        "include_consumables": _loot_shape_include_consumables,
    }

    def _run(mode: str) -> None:
        global _loot_shape_status
        try:
            _loot_shape_status = loot_shapes.arrange_from_payload(payload, mode=mode)
            _set_action_status(_loot_shape_status)
        except Exception as exc:
            _loot_shape_status = f"Loot Shapes failed: {exc}"
            _set_action_status(_loot_shape_status)

    def _stop_drop() -> None:
        global _loot_shape_status
        try:
            _loot_shape_status = loot_shapes.finish_drop_jobs()
            _set_action_status(_loot_shape_status)
        except Exception as exc:
            _loot_shape_status = f"Stop drop failed: {exc}"
            _set_action_status(_loot_shape_status)

    _button("Place Fully", lambda: _run("place_fully"), ACCENT_SUCCESS, 160.0, 0.0)
    imgui.same_line()
    _button("Quick Arrange", lambda: _run("quick"), ACCENT_INFO, 160.0, 0.0)
    imgui.same_line()
    _button("Re-apply", lambda: _run("reapply"), ACCENT_SECONDARY, 120.0, 0.0)
    imgui.same_line()
    _button("Stop Drop", _stop_drop, ACCENT_WARN, 120.0, 0.0)
    imgui.same_line()
    _button("Soft Clear", lambda: _run("clear"), ACCENT_DANGER, 120.0, 0.0)
    imgui.spacing()
    _wrapped_text(_loot_shape_status, ACCENT_MUTED)
    _wrapped_text(loot_shapes.get_last_layout_summary(), ACCENT_MUTED)


def _draw_home_dashboard(players: list[tuple[int, str]], labels: list[str]) -> None:
    """Task-first landing page with shared target context and fast workspace entry."""
    imgui = _blimgui.imgui
    _sq_section_header("Session Command Center", ACCENT_PRIMARY)
    _wrapped_text(
        "In-world on a character first (not the main menu). Pick the lobby target at the top, "
        "then use the boosts below. Other tools: github.com/Squ1ggs/Bl4SDKmods · scooterstoolbox.com",
        ACCENT_WARN,
    )
    _sq_section_header("Launchpad", ACCENT_SECONDARY)
    launchers = (
        ("UVHM", 2, 0, ACCENT_PRIMARY),
        ("Spawn Loot", 3, 0, ACCENT_SUCCESS),
        ("Decode Serial", 4, 0, ACCENT_INFO),
        ("Move Players", 5, 0, ACCENT_INFO),
        ("Fast Travel", 6, 2, ACCENT_WARN),
    )
    for position, (label, index, subview, accent) in enumerate(launchers):
        _button(label, lambda index=index, subview=subview: _open_workspace(index, subview), accent, 138.0, 0.0)
        if position != len(launchers) - 1:
            imgui.same_line()
    imgui.spacing()

    _sq_section_header("One-click Boosts", ACCENT_SUCCESS)
    _draw_quick_max()
    _draw_quick_mods("home")
    _draw_cosmetics_quick()
    imgui.spacing()

    _sq_section_header("Fine Controls", ACCENT_MUTED)
    _draw_rewards_hub_layout()


def _draw_player_workspace() -> None:
    _sq_section_header("Player Tools", ACCENT_INFO)
    _draw_quick_mods("player")
    _draw_cosmetics_quick()
    _draw_dev_tools_card()


def _start_uvhm_selected() -> None:
    if bool(_challenge_bulk_runtime.status().get("active")):
        _log("UVHM: wait for or cancel the non-UVHM challenge workflow first.")
        return
    index = _selected_player_index_value()
    if index is None:
        _log("UVHM: select a live party player first.")
        return
    if not _uvhm_runtime.request_selected(index):
        state = _uvhm_runtime.status()
        _log(f"UVHM: {state.get('message') or 'could not queue the workflow.'}")
        return
    _log(f"UVHM: queued ranks 1–7 for {_selected_player_name() or f'player {index}'}.")


def _request_uvhm_all() -> None:
    global _uvhm_all_confirm_until
    if bool(_challenge_bulk_runtime.status().get("active")):
        _log("UVHM: wait for or cancel the non-UVHM challenge workflow first.")
        return
    now = time.monotonic()
    if now > _uvhm_all_confirm_until:
        _uvhm_all_confirm_until = now + 10.0
        _log("UVHM: click Confirm All Lobby within 10 seconds to process every current player.")
        return
    _uvhm_all_confirm_until = 0.0
    if not _uvhm_runtime.request_all(confirmed=True):
        state = _uvhm_runtime.status()
        _log(f"UVHM: {state.get('message') or 'could not queue the workflow.'}")
        return
    _log("UVHM: queued confirmed ranks 1–7 workflow for the current lobby.")


def _draw_uvhm_persistent_status() -> None:
    state = _uvhm_runtime.status()
    rank = int(state.get("rank") or 0)
    target = str(state.get("target_name") or "")
    phase = str(state.get("phase") or "idle")
    summary = f"UVHM queue: {phase}"
    if target:
        summary += f" · {target}"
    if rank:
        summary += f" · rank {rank}"
    _muted_wrapped(f"{summary} — {state.get('message') or ''}")


def _draw_uvhm_progression_card() -> None:
    imgui = _blimgui.imgui
    state = _uvhm_runtime.status()
    _wrapped_text(
        "1. Pick the lobby target at the top.  2. Click Start Selected Player.  "
        "3. Keep the host in-game while each rank is completed and verified.",
        ACCENT_INFO,
    )
    selected = _selected_player_name() or "No player selected"
    _muted_wrapped(f"Start target: {selected}")
    _button(
        f"Start Selected: {selected}###uvhm_start_selected",
        _start_uvhm_selected,
        ACCENT_SUCCESS,
        260.0,
        0.0,
    )
    imgui.same_line()
    confirm_label = (
        "Confirm All Lobby"
        if time.monotonic() <= _uvhm_all_confirm_until
        else "All Lobby (confirm)"
    )
    _button(confirm_label, _request_uvhm_all, ACCENT_WARN, 180.0, 0.0)
    imgui.same_line()
    _button("Cancel", _uvhm_runtime.cancel, ACCENT_DANGER, 90.0, 0.0)
    if bool(state.get("can_resume")):
        imgui.same_line()
        _button("Resume", _uvhm_runtime.resume, ACCENT_INFO, 90.0, 0.0)
    _draw_uvhm_persistent_status()
    if not bool(state.get("hook_ready")):
        _wrapped_text(
            "UVHM runtime is not ready: "
            + str(state.get("hook_error") or "no game tick hook is installed"),
            ACCENT_DANGER,
        )
    elif state.get("hook_path"):
        _muted_wrapped(f"Runtime ready: {state.get('hook_path')}")
    tick_count = int(state.get("tick_count") or 0)
    tick_age_raw = state.get("tick_age")
    tick_age = float(tick_age_raw) if isinstance(tick_age_raw, (int, float)) else None
    if bool(state.get("running")) and (tick_age is None or tick_age > 2.0):
        _wrapped_text(
            "The workflow is queued but no recent game tick has processed it. "
            "Close and reopen Boosting Tools once; if this persists, reload the mod.",
            ACCENT_DANGER,
        )
    else:
        age_label = f"{tick_age:.1f}s ago" if tick_age is not None else "not seen yet"
        _muted_wrapped(f"Runtime ticks: {tick_count} · latest {age_label}")
    token = str(state.get("token") or "")
    if token:
        _muted_wrapped(f"Current challenge: {token} · poll {int(state.get('poll_count') or 0)}")
    results = tuple(state.get("results") or ())
    if results:
        _muted_wrapped("Recent verified stages: " + " · ".join(str(item) for item in results[-5:]))
    _muted_wrapped(
        "This follows the supplied working +1 command sequence with pauses; rank activation is verified when exposed. "
        "Rank 6 uses Bloomreaper; rank 7 uses the Subjugator/Thol completion requirement."
    )


def _request_non_uvhm_selected() -> None:
    global _challenge_bulk_confirm_until
    index = _selected_player_index_value()
    if index is None:
        _log("Challenges: select a live party player first.")
        return
    uvhm_state = _uvhm_runtime.status()
    if bool(uvhm_state.get("running")):
        _log("Challenges: wait for or cancel the UVHM workflow first.")
        return
    now = time.monotonic()
    category = _challenge_bulk_runtime.CATEGORY_LABELS[
        max(0, min(_challenge_bulk_category_index, len(_challenge_bulk_runtime.CATEGORY_LABELS) - 1))
    ]
    if now > _challenge_bulk_confirm_until:
        _challenge_bulk_confirm_until = now + 10.0
        _log(
            f"Challenges: click CONFIRM within 10 seconds to permanently complete "
            f"{category} for {_selected_player_name() or 'the selected player'}."
        )
        return
    _challenge_bulk_confirm_until = 0.0
    if not _challenge_bulk_runtime.request_selected(index, category, confirmed=True):
        _log(f"Challenges: {_challenge_bulk_runtime.status().get('message')}")
        return
    _log(f"Challenges: queued confirmed {category} workflow for {_selected_player_name()}.")


def _draw_non_uvhm_challenges_card() -> None:
    global _challenge_bulk_category_index
    global _challenge_single_search, _challenge_single_row
    global _challenge_single_confirm_until, _challenge_single_confirm_token
    imgui = _blimgui.imgui
    state = _challenge_bulk_runtime.status()
    _sq_section_header("Other Challenges", ACCENT_WARN)
    _wrapped_text(
        "Permanently completes the selected non-UVHM challenge category using one direct "
        "catalog-goal command per game tick. Story challenge flags ticks Completemainstory / "
        "Completesidemissions achievement tokens — that is not finishing story in the mission log.",
        ACCENT_DANGER,
    )
    categories = list(_challenge_bulk_runtime.CATEGORY_LABELS)
    _challenge_bulk_category_index = _combo(
        "Challenge Category###sqbt_challenge_category",
        _challenge_bulk_category_index,
        categories,
    )
    category = categories[
        max(0, min(_challenge_bulk_category_index, len(categories) - 1))
    ]
    selected = _selected_player_name() or "No player selected"
    _muted_wrapped(f"Challenge target: {selected}")
    confirming = time.monotonic() <= _challenge_bulk_confirm_until
    _button(
        f"CONFIRM {category}###challenge_bulk_confirm"
        if confirming
        else f"Complete {category} (confirm)###challenge_bulk_confirm",
        _request_non_uvhm_selected,
        ACCENT_DANGER if confirming else ACCENT_WARN,
        280.0,
        0.0,
    )
    imgui.same_line()
    _button(
        "Cancel Challenge Run###sqbt_challenge_cancel",
        _challenge_bulk_runtime.cancel,
        ACCENT_WARN,
        180.0,
        0.0,
    )
    current = int(state.get("index") or 0)
    total = int(state.get("total") or 0)
    _muted_wrapped(
        f"Challenge run: {current}/{total} · accepted {int(state.get('ok') or 0)} · "
        f"failed {int(state.get('failed') or 0)} — {state.get('message') or ''}"
    )
    token = str(state.get("token") or "")
    if token:
        _muted_wrapped(f"Current: {token}")
    error = str(state.get("last_error") or "")
    if error:
        _wrapped_text(f"Latest failure: {error}", ACCENT_DANGER)

    imgui.separator()
    _sq_section_header("Complete one challenge", ACCENT_WARN)
    _muted_wrapped("Filter by the category above, search, click one row, then confirm.")
    changed_search, _challenge_single_search = imgui.input_text(
        "Search challenge###sqbt_challenge_single_search",
        _challenge_single_search,
        128,
    )
    del changed_search
    try:
        rows = _challenge_bulk_runtime.catalog_rows(_challenge_single_search, category, limit=400)
    except Exception as exc:
        rows = ()
        _muted_wrapped(f"Challenge catalog unavailable: {exc}")
    if rows:
        _challenge_single_row = max(0, min(_challenge_single_row, len(rows) - 1))
        _muted_wrapped(f"{len(rows)} challenge(s) — click one to select")
        child_began = False
        try:
            child_open = False
            for args in (
                ("###sqbt_challenge_single_list", (0, 220)),
                ("###sqbt_challenge_single_list", 0, 220, True),
            ):
                try:
                    ret = imgui.begin_child(*args)
                    if isinstance(ret, tuple):
                        child_open = bool(ret[0])
                    else:
                        child_open = bool(ret)
                    break
                except TypeError:
                    continue
            child_began = True
            if child_open:
                for index, (row_token, goal) in enumerate(rows):
                    friendly = _challenge_bulk_runtime.challenge_display_name(row_token)
                    label = f"{friendly + ' — ' if friendly else ''}{row_token}  [goal {goal}]"
                    clicked, _ = imgui.selectable(label, index == _challenge_single_row)
                    if clicked:
                        _challenge_single_row = index
        finally:
            if child_began:
                imgui.end_child()
        pick_token, pick_goal = rows[_challenge_single_row]
        armed = (
            time.monotonic() <= _challenge_single_confirm_until
            and _challenge_single_confirm_token.casefold() == pick_token.casefold()
        )

        def _request_single(token: str = pick_token) -> None:
            global _challenge_single_confirm_until, _challenge_single_confirm_token
            now = time.monotonic()
            if (
                now > _challenge_single_confirm_until
                or _challenge_single_confirm_token.casefold() != token.casefold()
            ):
                _challenge_single_confirm_until = now + 10.0
                _challenge_single_confirm_token = token
                _log(f"Challenges: confirm again within 10s to complete only {token}")
                return
            _challenge_single_confirm_until = 0.0
            _challenge_single_confirm_token = ""
            index = _selected_player_index_value()
            if index is None:
                _log("Challenges: select a party player first.")
                return
            if not _challenge_bulk_runtime.request_selected(
                index, category, confirmed=True, tokens=[token]
            ):
                _log(f"Challenges: {_challenge_bulk_runtime.status().get('message')}")

        _button(
            f"CONFIRM ONLY: {pick_token}###sqbt_challenge_single_go"
            if armed
            else "Complete selected only (confirm)###sqbt_challenge_single_go",
            _request_single,
            ACCENT_DANGER if armed else ACCENT_WARN,
            360.0,
            0.0,
        )
        _muted_wrapped(f"Completion target: {pick_goal}. Only this challenge will be queued.")
    else:
        _muted_wrapped("No challenge tokens match this search/category.")


def _draw_progression_workspace() -> None:
    _sq_section_header("Progression & UVHM", ACCENT_PRIMARY)
    draw_uvhm = globals().get("_draw_uvhm_progression_card")
    if callable(draw_uvhm):
        draw_uvhm()
    else:
        _muted_wrapped("UVHM workflow is loading; reload the mod if this message persists.")
    _draw_non_uvhm_challenges_card()
    _draw_quick_max()
    _draw_experience_card()
    _draw_currency_card()
    _draw_sdu_card()
    _draw_inventory_size_card()

def _save_favorites() -> None:
    # Keep descriptions only for entries which are still favorited.
    for key in list(_favorite_itempool_descriptions):
        if key not in _favorite_itempools:
            _favorite_itempool_descriptions.pop(key, None)
    for key in list(_favorite_travel_map_descriptions):
        if key not in _favorite_travel_maps:
            _favorite_travel_map_descriptions.pop(key, None)
    for key in list(_favorite_travel_station_descriptions):
        if key not in _favorite_travel_stations:
            _favorite_travel_station_descriptions.pop(key, None)
    for key in list(_favorite_gzo_descriptions):
        if not _is_favorite(key, _favorite_gzo_serials):
            _favorite_gzo_descriptions.pop(key, None)
    for key in list(_favorite_lootlemon_descriptions):
        if not _is_favorite(key, _favorite_lootlemon_serials):
            _favorite_lootlemon_descriptions.pop(key, None)
    save_extra_settings(
        favorite_itempools=sorted(_favorite_itempools),
        favorite_travel_maps=sorted(_favorite_travel_maps),
        favorite_travel_stations=sorted(_favorite_travel_stations),
        favorite_gzo_serials=sorted(_favorite_gzo_serials),
        favorite_lootlemon_serials=sorted(_favorite_lootlemon_serials),
        favorite_itempool_descriptions=dict(sorted(_favorite_itempool_descriptions.items())),
        favorite_travel_map_descriptions=dict(sorted(_favorite_travel_map_descriptions.items())),
        favorite_travel_station_descriptions=dict(sorted(_favorite_travel_station_descriptions.items())),
        favorite_gzo_descriptions=dict(sorted(_favorite_gzo_descriptions.items())),
        favorite_lootlemon_descriptions=dict(sorted(_favorite_lootlemon_descriptions.items())),
        travel_show_all_stations=bool(_travel_show_all_stations),
    )


def _is_favorite(value: str, favorites: set[str]) -> bool:
    needle = str(value or "").strip().lower()
    if not needle:
        return False
    return any(str(x).strip().lower() == needle for x in favorites)


def _discard_favorite(value: str, favorites: set[str]) -> None:
    needle = str(value or "").strip().lower()
    if not needle:
        return
    for existing in list(favorites):
        if str(existing).strip().lower() == needle:
            favorites.discard(existing)


def _sort_favorites_first(rows: list[dict[str, str]], id_key: str, favorites: set[str]) -> list[dict[str, str]]:
    fav_low = {str(x).strip().lower() for x in favorites if str(x).strip()}
    return sorted(
        rows,
        key=lambda row: (
            0 if str(row.get(id_key, "")).strip().lower() in fav_low else 1,
            str(row.get("display_name", row.get("name", row.get(id_key, "")))).lower(),
        ),
    )


def _fav_prefix(value: str, favorites: set[str]) -> str:
    return "[FAV] " if _is_favorite(value, favorites) else ""


def _fav_description(value: str, descriptions: dict[str, str]) -> str:
    text = str(descriptions.get(str(value), "")).strip()
    if not text:
        needle = str(value or "").strip().lower()
        for key, raw in descriptions.items():
            if str(key).strip().lower() == needle:
                text = str(raw).strip()
                break
    return f" - {text}" if text else ""


def _draw_favorite_description_editor(label: str, key: str, favorites: set[str], descriptions: dict[str, str]) -> None:
    if not key or not _is_favorite(key, favorites):
        return
    # Prefer the stored favourite key so description edits stick across case variants.
    store_key = key
    for existing in favorites:
        if str(existing).strip().lower() == str(key).strip().lower():
            store_key = str(existing)
            break
    old_text = str(descriptions.get(store_key, descriptions.get(key, "")))
    new_text = _input_text(label, old_text, 128).strip()
    if new_text != old_text:
        if new_text:
            descriptions[store_key] = new_text
        else:
            descriptions.pop(store_key, None)
            descriptions.pop(key, None)
        _save_favorites()


def _invalidate_itempool_filter_cache() -> None:
    global _itempool_filter_cache_key, _itempool_filter_cache_rows
    _itempool_filter_cache_key = None
    _itempool_filter_cache_rows = None


def _invalidate_travel_station_filter_cache() -> None:
    global _travel_station_filter_cache_key, _travel_station_filter_cache_rows
    _travel_station_filter_cache_key = None
    _travel_station_filter_cache_rows = None


def _current_itempool_all_results() -> list[dict[str, str]]:
    """Cached full filter — rebuild only when search/category/favorites change."""
    global _itempool_filter_cache_key, _itempool_filter_cache_rows
    fav_sig = len(_favorite_itempools)
    key = (str(_itempool_search), str(_itempool_category), int(fav_sig))
    if _itempool_filter_cache_rows is not None and _itempool_filter_cache_key == key:
        return _itempool_filter_cache_rows
    rows = _sort_favorites_first(
        filter_item_pools(_itempool_search, _itempool_category, limit=0),
        "itempool",
        _favorite_itempools,
    )
    _itempool_filter_cache_key = key
    _itempool_filter_cache_rows = rows
    return rows


def _current_itempool_results() -> list[dict[str, str]]:
    all_results = _current_itempool_all_results()
    start = max(0, int(_itempool_page)) * _ITEMPOOL_PAGE_SIZE
    return all_results[start:start + _ITEMPOOL_PAGE_SIZE]


def _itempool_batch_progress_text() -> str:
    """GUI-only Spawn All progress; result classifications stay in log files."""
    text = bulk_spawn_status_line()
    text = re.sub(
        r",?\s*\d+\s+ok\s*/\s*\d+\s+fail(?:\s+this batch|\s+so far)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+\)", ")", text).strip()


def _select_itempool_by_name(pool_name: str) -> None:
    """Keep the same item pool selected after favorite sorting moves it."""
    global _itempool_page, _itempool_selected_index
    if not pool_name:
        return
    all_results = _current_itempool_all_results()
    for absolute_index, row in enumerate(all_results):
        if str(row.get("itempool", "")) == pool_name:
            _itempool_page = absolute_index // _ITEMPOOL_PAGE_SIZE
            _itempool_selected_index = absolute_index % _ITEMPOOL_PAGE_SIZE
            return


def _select_travel_map_by_name(map_name: str) -> None:
    """Keep the same map selected after favorite sorting moves it."""
    global _travel_selected_map_index
    if not map_name:
        return
    results = _current_travel_map_results()
    for index, row in enumerate(results):
        if str(row.get("map", "")) == map_name:
            _travel_selected_map_index = index
            return


def _select_travel_station_by_name(station_name: str) -> None:
    """Keep the same travel station selected after favorite sorting moves it."""
    global _travel_selected_station_index
    if not station_name:
        return
    results = _current_travel_station_results()
    for index, row in enumerate(results):
        if str(row.get("station", "")) == station_name:
            _travel_selected_station_index = index
            return


def _spawn_selected_item_pool() -> None:
    global _itempool_selected_index
    results = _current_itempool_results()
    if not results:
        _log("No loot pool selected.")
        return
    _itempool_selected_index = max(0, min(_itempool_selected_index, len(results) - 1))
    entry = results[_itempool_selected_index]
    label = str(entry.get("display_name") or entry.get("itempool") or "?")
    try:
        from .item_pool_spawning import queue_item_pool_entry

        where = _sync_spawn_target()
        from .loot_shapes import DROP_MODE_NAMES, visible_shape_names

        shape_opts = ["none", *visible_shape_names()]
        settle_opts = list(DROP_MODE_NAMES)
        shape = shape_opts[max(0, min(_itempool_shape_index, len(shape_opts) - 1))]
        settle = settle_opts[max(0, min(_itempool_settle_index, len(settle_opts) - 1))]
        queue_item_pool_entry(
            entry,
            level=_itempool_level,
            count=_itempool_count,
            shape=shape,
            settle=settle,
            drop_height=float(_itempool_drop_height),
            z_bias=float(_itempool_z_bias),
            line_length=float(_itempool_line_length),
            radius=float(_itempool_shape_radius),
            spacing=float(_itempool_shape_spacing),
            spawn_then_shape=_itempool_spawn_then_shape,
            stay_in_air=_itempool_stay_in_air,
            peel_after=float(_itempool_peel_after),
            fill_until_complete=_itempool_fill_until_complete,
        )
        land = f"{shape}/{settle}" if shape not in ("", "none") else "feet"
        _log(
            f"Queued: {label} x{_itempool_count} @ level {_itempool_level} near {where} "
            f"({land}) ({entry.get('itempool', '')}) — details recorded in the spawn log."
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"Queue spawn failed — {label}: {exc}")


def _grant_all_filtered_item_pools_rewards() -> None:
    all_results = _current_itempool_all_results()
    if not all_results:
        _log("No loot pools match the current search/category.")
        return
    try:
        n, _ = grant_all_filtered_item_pools_rewards(_itempool_search, _itempool_category)
        _log(f"Granted {n} item(s) via loyalty rewards (check mail).")
    except Exception as exc:  # noqa: BLE001
        _log(f"Grant all filtered (rewards) failed: {exc}")


def _spawn_all_filtered_item_pools() -> None:
    all_results = _current_itempool_all_results()
    if not all_results:
        _log("No loot pools match the current search/category.")
        return
    try:
        _sync_spawn_target()
        from .loot_shapes import DROP_MODE_NAMES, visible_shape_names

        shape_opts = ["none", *visible_shape_names()]
        settle_opts = list(DROP_MODE_NAMES)
        shape = shape_opts[max(0, min(_itempool_shape_index, len(shape_opts) - 1))]
        settle = settle_opts[max(0, min(_itempool_settle_index, len(settle_opts) - 1))]
        queued = queue_all_filtered_item_pools(
            _itempool_search,
            _itempool_category,
            level=_itempool_level,
            count=_itempool_count,
            gap_sec=_itempool_spawn_gap,
            per_tick=_itempool_spawn_per_tick,
            random_spread=_itempool_random_spread,
            shape=shape,
            settle=settle,
            drop_height=float(_itempool_drop_height),
            z_bias=float(_itempool_z_bias),
            line_length=float(_itempool_line_length),
            radius=float(_itempool_shape_radius),
            spacing=float(_itempool_shape_spacing),
            spawn_then_shape=_itempool_spawn_then_shape,
            stay_in_air=_itempool_stay_in_air,
            peel_after=float(_itempool_peel_after),
            fill_until_complete=_itempool_fill_until_complete,
        )
        if shape not in ("", "none"):
            spread = f"{shape}/{settle}"
        _log(
            f"Spawn All started: {queued} pools — {spread}, "
            f"{_itempool_spawn_gap:.2f}s gap, {_itempool_spawn_per_tick}/tick."
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"Spawn all filtered failed: {exc}")


def _spawn_singular_path_test_filtered() -> None:
    """Removed — use Spawn All Filtered."""
    _log("Test Singular Filtered was removed. Use Spawn All Filtered or Spawn Selected.")


def _toggle_selected_itempool_favorite() -> None:
    results = _current_itempool_results()
    if not results:
        _log("No loot pool selected to favorite.")
        return
    idx = max(0, min(_itempool_selected_index, len(results) - 1))
    pool = str(results[idx].get("itempool", ""))
    if not pool:
        return
    if pool in _favorite_itempools:
        _favorite_itempools.remove(pool)
        _favorite_itempool_descriptions.pop(pool, None)
        _log(f"Removed loot pool favorite: {pool}")
    else:
        _favorite_itempools.add(pool)
        _log(f"Added loot pool favorite: {pool}")
    _save_favorites()
    _invalidate_itempool_filter_cache()
    _select_itempool_by_name(pool)


def _toggle_selected_map_favorite() -> None:
    results = _current_travel_map_results()
    if not results:
        _log("No map selected to favorite.")
        return
    idx = max(0, min(_travel_selected_map_index, len(results) - 1))
    name = str(results[idx].get("map", ""))
    if not name:
        return
    if name in _favorite_travel_maps:
        _favorite_travel_maps.remove(name)
        _favorite_travel_map_descriptions.pop(name, None)
        _log(f"Removed map favorite: {name}")
    else:
        _favorite_travel_maps.add(name)
        _log(f"Added map favorite: {name}")
    _save_favorites()
    _select_travel_map_by_name(name)


def _toggle_selected_station_favorite() -> None:
    results = _current_travel_station_results()
    if not results:
        _log("No travel station selected to favorite.")
        return
    idx = max(0, min(_travel_selected_station_index, len(results) - 1))
    station = str(results[idx].get("station", ""))
    if not station:
        return
    if station in _favorite_travel_stations:
        _favorite_travel_stations.remove(station)
        _favorite_travel_station_descriptions.pop(station, None)
        _log(f"Removed travel station favorite: {station}")
    else:
        _favorite_travel_stations.add(station)
        _log(f"Added travel station favorite: {station}")
    _save_favorites()
    _invalidate_travel_station_filter_cache()
    _select_travel_station_by_name(station)


def _toggle_serial_favorite(
    serial: str,
    favorites: set[str],
    descriptions: dict[str, str],
    *,
    label: str,
    display_name: str = "",
) -> None:
    serial = str(serial or "").strip()
    if not serial:
        _log(f"No {label} serial selected to favorite.")
        return
    if _is_favorite(serial, favorites):
        _discard_favorite(serial, favorites)
        for key in list(descriptions):
            if str(key).strip().lower() == serial.lower():
                descriptions.pop(key, None)
        _log(f"Removed {label} favorite.")
    else:
        favorites.add(serial)
        name = str(display_name or "").strip()
        if name:
            descriptions[serial] = name
        _log(f"Added {label} favorite: {name or serial[:48]}")
    _save_favorites()


def _toggle_active_gzo_favorite() -> None:
    active = _gzo_active_entry()
    if not active:
        _log("No GZO code selected to favorite.")
        return
    _toggle_serial_favorite(
        str(active.get("serial", "")),
        _favorite_gzo_serials,
        _favorite_gzo_descriptions,
        label="GZO",
        display_name=str(active.get("name", "")),
    )


def _toggle_active_lootlemon_favorite() -> None:
    active = _lootlemon_active_entry()
    if not active:
        _log("No Lootlemon code selected to favorite.")
        return
    _toggle_serial_favorite(
        str(active.get("serial", "")),
        _favorite_lootlemon_serials,
        _favorite_lootlemon_descriptions,
        label="Lootlemon",
        display_name=str(active.get("name", "")),
    )


def _draw_category_button(label: str, accent: str = "purple") -> None:
    global _itempool_category, _itempool_selected_index, _itempool_page
    def _set() -> None:
        global _itempool_category, _itempool_selected_index, _itempool_page
        _itempool_category = label
        _itempool_selected_index = 0
        _itempool_page = 0
        _invalidate_itempool_filter_cache()
    display = f"[{label}]" if _itempool_category == label else label
    _button(display, _set, accent)


def _draw_item_pool_tab() -> None:
    global _itempool_search, _itempool_category, _itempool_selected_index, _itempool_count, _itempool_level, _itempool_page, _itempool_spawn_target_index
    global _itempool_spawn_gap, _itempool_spawn_per_tick, _itempool_random_spread
    global _itempool_singular_named_only
    global _itempool_shape_index, _itempool_settle_index, _itempool_drop_height, _itempool_z_bias
    global _itempool_line_length, _itempool_shape_radius, _itempool_shape_spacing
    global _itempool_stay_in_air, _itempool_peel_after, _itempool_fill_until_complete
    global _itempool_spawn_then_shape
    imgui = _blimgui.imgui
    opened = _sq_begin_card("Loot Pool Spawner", "itempool", _tab_card_height(700.0))
    if opened:
        if _cyber:
            _muted_wrapped(
                "Filter loot pools, choose a spawn location, then create the world drop."
            )
        else:
            imgui.text_wrapped(
                "Filter loot pools, choose a spawn location, then create the world drop."
            )

        previous_search = _itempool_search
        _itempool_search = _input_text("Search Loot Pools", _itempool_search, 256)
        if _itempool_search != previous_search:
            _itempool_page = 0
            _itempool_selected_index = 0
            _invalidate_itempool_filter_cache()

        try:
            imgui.push_item_width(120)
        except Exception:
            pass
        _itempool_level = _input_int_clamped("Level", _itempool_level, 1, 999999)
        imgui.same_line()
        _itempool_count = _input_int_clamped("Quantity", _itempool_count, 1, 100)
        where = _sync_spawn_target()
        _muted_wrapped(f"World spawns use the lobby target bar: {where}")
        try:
            imgui.pop_item_width()
        except Exception:
            pass

        categories = item_pool_categories()
        if _itempool_category not in categories:
            _itempool_category = "All"
        row = 0
        for category in categories:
            accent = "gold" if category == "All" else ("cyan" if category in ("Assault Rifle", "Pistol", "SMG", "Sniper", "Shotgun", "Heavy") else "purple")
            _draw_category_button(category, accent)
            row += 1
            if row % 8 != 0:
                imgui.same_line()
        imgui.spacing()
        _muted_wrapped(
            "If a named item is missing from the list or does not spawn, try "
            "Spawn All Filtered on this tab, or the related type pool "
            "(AR / SG / SM / PS / SR 05 Legendary; Pearl tab = AR/SR/SM/SG/PS Pearl Pool)."
        )
        if str(_itempool_category).strip().lower() == "pearl":
            _muted_wrapped(
                "Pearl tip: type pools roll random pearls; rows starting with > are named."
            )

        all_results = _current_itempool_all_results()
        total = len(all_results)
        max_page = max(0, (total - 1) // _ITEMPOOL_PAGE_SIZE) if total else 0
        _itempool_page = max(0, min(_itempool_page, max_page))
        results = _current_itempool_results()
        batch_active = bulk_spawn_active()
        if _itempool_selected_index >= len(results):
            _itempool_selected_index = 0

        if results:
            selected = results[max(0, min(_itempool_selected_index, len(results) - 1))]
            start_num = _itempool_page * _ITEMPOOL_PAGE_SIZE + 1
            end_num = _itempool_page * _ITEMPOOL_PAGE_SIZE + len(results)
            status = f"Selected: {selected['itempool']} | Showing {start_num}-{end_num} of {total} | Page {_itempool_page + 1}/{max_page + 1}"
            if _cyber:
                _muted_wrapped(status)
            else:
                imgui.text_wrapped(status)
            if batch_active:
                _muted_wrapped(_itempool_batch_progress_text())

            def _first_page() -> None:
                global _itempool_page, _itempool_selected_index
                _itempool_page = 0
                _itempool_selected_index = 0
            def _prev_page() -> None:
                global _itempool_page, _itempool_selected_index
                _itempool_page = max(0, _itempool_page - 1)
                _itempool_selected_index = 0
            def _next_page() -> None:
                global _itempool_page, _itempool_selected_index
                _itempool_page = min(max_page, _itempool_page + 1)
                _itempool_selected_index = 0
            def _last_page() -> None:
                global _itempool_page, _itempool_selected_index
                _itempool_page = max_page
                _itempool_selected_index = 0

            _button("First", _first_page, "purple", 70, 0); imgui.same_line()
            _button("Prev", _prev_page, "purple", 70, 0); imgui.same_line()
            _button("Next", _next_page, "purple", 70, 0); imgui.same_line()
            _button("Last", _last_page, "purple", 70, 0)

            child_open = _begin_child_region("sqbt_itempool_scroll_list", _remaining_child_height(360.0, 60.0))
            visible_rows = results if child_open else results[:18]
            for index, entry in enumerate(visible_rows):
                pool = str(entry.get("itempool", ""))
                fav = pool in _favorite_itempools
                if imgui.small_button(f"{'−' if fav else '+'}###sqbt_ipfav_{_itempool_page}_{index}"):
                    if fav:
                        _favorite_itempools.discard(pool)
                        _favorite_itempool_descriptions.pop(pool, None)
                    else:
                        _favorite_itempools.add(pool)
                        _favorite_itempool_descriptions[pool] = str(entry.get("display_name", pool))
                    _save_favorites()
                imgui.same_line()
                fav_prefix = _fav_prefix(pool, _favorite_itempools)
                label = f"{fav_prefix}[{entry['category']}] {entry['display_name']}{_fav_description(pool, _favorite_itempool_descriptions)}###itempool_{_itempool_page}_{index}"
                if _selectable_row(label, index == _itempool_selected_index):
                    _itempool_selected_index = index
            if child_open:
                _end_child_region()
            elif len(results) > len(visible_rows):
                imgui.text_wrapped(f"Showing first {len(visible_rows)} result(s) on this page; narrow search for more.")
            selected_pool_name = str(selected.get("itempool", ""))
            fav_label = "Unfavorite Selected" if selected_pool_name in _favorite_itempools else "Favorite Selected"
            has_catalog = bool(str(selected.get("catalog_key", "")).strip())
            is_named = has_catalog or str(selected.get("display_name", "")).lstrip().startswith(">")
            spawn_btn = "Spawn Named Item" if is_named else "Spawn Selected Pool"
            _button(fav_label, _toggle_selected_itempool_favorite, "purple", 170, 0); imgui.same_line()
            _button(spawn_btn, _spawn_selected_item_pool, "gold", 220, 0)
            imgui.same_line()
            _button(
                f"Spawn All Filtered ({total})",
                _spawn_all_filtered_item_pools,
                "cyan",
                220,
                0,
            )
            imgui.same_line()
            _button(
                "Stop spawn list",
                lambda: _log(
                    "Spawn cancelled: "
                    + str(cancel_bulk_spawn_batch(log=True)[0])
                    + " left unspawned."
                ),
                "purple",
                160,
                0,
            )
            _itempool_spawn_gap = _input_float_slider(
                "Delay between items (sec)", _itempool_spawn_gap, 0.0, 2.0, "%.2f"
            )
            _itempool_spawn_per_tick = _input_int_clamped(
                "Items per tick", _itempool_spawn_per_tick, 1, 8
            )
            spread_idx = 1 if _itempool_random_spread else 0
            spread_idx = _combo("Spit random directions", spread_idx, ["no", "yes"])
            _itempool_random_spread = spread_idx == 1

            _sq_section_header("Land arrangement", ACCENT_INFO)
            from .loot_shapes import DROP_MODE_NAMES, SHAPE_3D_NAMES, shape_pretty_name, visible_shape_names

            shape_labels = ["none"]
            for name in visible_shape_names():
                pretty = shape_pretty_name(name)
                shape_labels.append(f"3D {pretty}" if name in SHAPE_3D_NAMES else pretty)
            settle_labels = [s.replace("_", " ") for s in DROP_MODE_NAMES]
            prev_shape_idx = _itempool_shape_index
            _itempool_shape_index = _combo("Shape", _itempool_shape_index, shape_labels)
            if _itempool_shape_index != prev_shape_idx:
                from .loot_shapes import visible_shape_names as _vis_shapes

                vis = list(_vis_shapes())
                sel = ""
                if _itempool_shape_index > 0 and _itempool_shape_index - 1 < len(vis):
                    sel = vis[_itempool_shape_index - 1]
                if sel == "car":
                    _itempool_drop_height = 20
            _itempool_fill_until_complete = _checkbox(
                "Continue until shape complete",
                _itempool_fill_until_complete,
            )
            _muted_wrapped("Pads drops until the silhouette is full (e.g. smiley ≈ 140).")
            sts_idx = 1 if _itempool_spawn_then_shape else 0
            sts_idx = _combo("Spawn all, then shape", sts_idx, ["no", "yes"])
            _itempool_spawn_then_shape = sts_idx == 1
            _itempool_settle_index = _combo("Drop from above", _itempool_settle_index, settle_labels)
            stay_idx = 0 if _itempool_stay_in_air else 1
            stay_idx = _combo("Stay in air", stay_idx, ["yes", "no"])
            _itempool_stay_in_air = stay_idx == 0
            _itempool_peel_after = _input_int_clamped("Then drop after (sec)", _itempool_peel_after, 0, 60)
            _itempool_drop_height = _input_int_clamped("Drop height", _itempool_drop_height, 0, 1200)
            _itempool_z_bias = _input_int_clamped("Ground height", _itempool_z_bias, 0, 250)
            _itempool_shape_radius = _input_int_clamped("Shape radius", _itempool_shape_radius, 40, 2000)
            _itempool_shape_spacing = _input_int_clamped("Shape spacing", _itempool_shape_spacing, 50, 400)
            _itempool_line_length = _input_int_clamped("Line length", _itempool_line_length, 120, 4000)
            _sq_section_header("Drop backpack → shape", ACCENT_WARN)
            _muted_wrapped(
                "Spill the party picker's backpack using the land fields above, then catch into the silhouette "
                "(world loot — not mail)."
            )
            _button("Drop backpack → shape", _drop_backpack_into_shape, ACCENT_WARN, 220, 0)
            _button(
                "Grant All Filtered (Rewards)",
                _grant_all_filtered_item_pools_rewards,
                "purple",
                220,
                0,
            )
            _muted_wrapped(
                "Spawn All: one roll per filtered pool. Shape on lands on the silhouette "
                "(random spit ignored). Cosmetic unlock pools are hidden."
            )
            if str(_itempool_category).strip().lower() == "shiny":
                _muted_wrapped(
                    "Shiny category: Spawn All drops matching *_shiny itempools at your feet "
                    "(paced ground loot). Shiny Mail* is only for fixed @U codes."
                )
            elif is_named:
                _muted_wrapped(
                    "Named item (>) — rolls from that item's dedicated pool when registered."
                )
            _draw_favorite_description_editor("Favorite Description##itempool_fav_desc", selected_pool_name, _favorite_itempools, _favorite_itempool_descriptions)
        else:
            if _cyber:
                _muted_wrapped("No loot pools match the current search/category.")
            else:
                imgui.text_wrapped("No loot pools match the current search/category.")
    _sq_end_card()



def _current_travel_map_results() -> list[dict[str, str]]:
    return _sort_favorites_first(filter_travel_maps(_travel_map_search, limit=80), "map", _favorite_travel_maps)


def _selected_travel_map_name() -> str:
    results = _current_travel_map_results()
    if not results:
        return ""
    idx = max(0, min(_travel_selected_map_index, len(results) - 1))
    return results[idx]["map"]


def _current_travel_station_results() -> list[dict[str, str]]:
    global _travel_station_filter_cache_key, _travel_station_filter_cache_rows
    map_name = "" if _travel_show_all_stations else _selected_travel_map_name()
    key = (str(map_name), str(_travel_station_search), len(_favorite_travel_stations), bool(_travel_show_all_stations))
    if _travel_station_filter_cache_rows is not None and _travel_station_filter_cache_key == key:
        return list(_travel_station_filter_cache_rows)
    rows = _sort_favorites_first(
        filter_travel_stations(map_name, _travel_station_search, limit=0),
        "station",
        _favorite_travel_stations,
    )
    _travel_station_filter_cache_key = key
    _travel_station_filter_cache_rows = rows
    return list(rows)


def _travel_to_selected_map() -> None:
    global _travel_selected_map_index
    results = _current_travel_map_results()
    if not results:
        _log("No map selected.")
        return
    _travel_selected_map_index = max(0, min(_travel_selected_map_index, len(results) - 1))
    row = results[_travel_selected_map_index]
    map_name = str(row["map"])
    _set_action_status(travel_to_map(map_name))
    squ1ggs_boost_tools_close()


def _travel_to_selected_station() -> None:
    global _travel_selected_station_index
    results = _current_travel_station_results()
    if not results:
        _log("No travel station selected.")
        return
    _travel_selected_station_index = max(0, min(_travel_selected_station_index, len(results) - 1))
    row = results[_travel_selected_station_index]
    station = str(row["station"])
    _set_action_status(travel_to_station(station))
    squ1ggs_boost_tools_close()


def _travel_to_tuba_boss_arena() -> None:
    try:
        _set_action_status(travel_to_preset("tuba_boss_arena"))
    except Exception as exc:
        _set_action_status(f"Tuba travel failed: {exc}")
        _log(f"Tuba boss travel failed: {exc!r}")
        return
    squ1ggs_boost_tools_close()


def _draw_travel_tab() -> None:
    global _travel_map_search, _travel_station_search, _travel_selected_map_index, _travel_selected_station_index, _travel_show_all_stations
    imgui = _blimgui.imgui
    opened = _sq_begin_card("Map Travel", "travel", _tab_card_height(760.0))
    if opened:
        if _cyber:
            _muted_wrapped(
                "Pick a map, then a station. You can travel to a station even if it is still locked on the map. "
                "That sends you there; it does not unlock the pin for later."
            )
        else:
            imgui.text_wrapped(
                "Pick a map, then a station. You can travel to a station even if it is still locked on the map. "
                "That sends you there; it does not unlock the pin for later."
            )

        _sq_section_header("Quick destinations", ACCENT_PRIMARY)
        _muted_wrapped(
            "One-click arena teleports — no mission replay. Tuba lands at the boss pool after map travel (~4s)."
        )
        _button("Tuba Boss Arena", _travel_to_tuba_boss_arena, ACCENT_WARN, 220, 0)
        imgui.spacing()

        _sq_section_header("Travel / vehicle", ACCENT_PRIMARY)
        _muted_wrapped(
            "Hide map fog this session, block fast travel, cancel a travel countdown, or allow personal vehicles here."
        )

        def _flip_map_fog_travel() -> None:
            from . import map_fog_hide as fog

            _set_action_status(fog.set_hidden(not fog.is_hidden()))

        try:
            from . import map_fog_hide as _fog_hide_travel

            fog_on = _fog_hide_travel.is_hidden()
        except Exception:
            fog_on = False
        _button(
            f"Hide map fog {'ON' if fog_on else 'OFF'}",
            _flip_map_fog_travel,
            ACCENT_SUCCESS if fog_on else ACCENT_MUTED,
            175,
            0,
            tooltip=(
                "Hides the map fog overlay this session. Open the map after turning it on. "
                "Fog comes back after reload. Does not unlock safehouses."
            ),
        )
        imgui.same_line()

        def _run_world_travel(action: str, extra: dict[str, Any] | None = None) -> None:
            try:
                from .bridge_actions_extended import EXTENDED_ACTIONS

                fn = EXTENDED_ACTIONS.get(action)
                if fn is None:
                    _set_action_status(f"Missing action {action}")
                    return
                payload = {"player_index": _selected_player_index_value(), **(extra or {})}
                result = fn(payload)
                _set_action_status(str((result or {}).get("message") or result))
            except Exception as exc:
                _set_action_status(f"{action}: {exc}")

        def _flip_block_local() -> None:
            global _travel_block_local
            _travel_block_local = not _travel_block_local
            _run_world_travel("oak_travel", {"action": "disallow_local", "enabled": _travel_block_local})

        def _flip_allow_vehicle() -> None:
            global _travel_allow_vehicle
            _travel_allow_vehicle = not _travel_allow_vehicle
            _run_world_travel("world_personal_vehicle", {"enabled": _travel_allow_vehicle})

        _button(
            f"Block local fast travel {'ON' if _travel_block_local else 'OFF'}",
            _flip_block_local,
            ACCENT_WARN if _travel_block_local else ACCENT_MUTED,
            230,
            0,
        )
        imgui.same_line()
        _button(
            "Cancel travel countdown",
            lambda: _run_world_travel("oak_travel", {"action": "cancel_countdown"}),
            ACCENT_PRIMARY,
            200,
            0,
        )

        def _flip_hold_session_travel() -> None:
            from . import hold_session as hold

            _set_action_status(hold.set_enabled(not hold.is_enabled()))

        try:
            from . import hold_session as _hold_travel

            hold_travel_on = _hold_travel.is_enabled()
        except Exception:
            hold_travel_on = False
        _button(
            f"Hold session {'ON' if hold_travel_on else 'OFF'}",
            _flip_hold_session_travel,
            ACCENT_SUCCESS if hold_travel_on else ACCENT_MUTED,
            160,
            0,
            tooltip=(
                "Host only. Cancels travel-to-menu countdown and blocks return to main menu. "
                "Turn OFF before you quit to the menu yourself."
            ),
        )
        _button(
            f"Allow personal vehicles {'ON' if _travel_allow_vehicle else 'OFF'}",
            _flip_allow_vehicle,
            ACCENT_SUCCESS if _travel_allow_vehicle else ACCENT_MUTED,
            250,
            0,
        )
        imgui.spacing()

        _travel_map_search = _input_text("Search Maps", _travel_map_search, 256)
        map_results = _current_travel_map_results()
        if _travel_selected_map_index >= len(map_results):
            _travel_selected_map_index = 0
        selected_map = _selected_travel_map_name()
        if _cyber:
            _cyber.section_header("Maps", "cyan")
        else:
            imgui.separator(); imgui.text("MAPS")
        if map_results:
            selected_row = map_results[max(0, min(_travel_selected_map_index, len(map_results) - 1))]
            if _cyber:
                _muted_wrapped(f"Selected map: {selected_row['map']} | Showing {len(map_results)} map(s).")
            else:
                imgui.text_wrapped(f"Selected map: {selected_row['map']} | Showing {len(map_results)} map(s).")
            child_open = _begin_child_region("sqbt_travel_map_scroll_list", max(220.0, min(320.0, _imgui_available_height(760.0) * 0.28)))
            visible_rows = map_results if child_open else map_results[:10]
            for index, entry in enumerate(visible_rows):
                fav = _fav_prefix(str(entry.get('map', '')), _favorite_travel_maps)
                label = f"{fav}{entry['display_name']}{_fav_description(str(entry.get('map', '')), _favorite_travel_map_descriptions)}###travel_map_{index}"
                if _selectable_row(label, index == _travel_selected_map_index):
                    _travel_selected_map_index = index
                    _travel_selected_station_index = 0
            if child_open:
                _end_child_region()
            selected_map_name = str(selected_row.get("map", ""))
            map_fav_label = "Unfavorite Map" if selected_map_name in _favorite_travel_maps else "Favorite Map"
            _button(map_fav_label, _toggle_selected_map_favorite, "purple", 140, 0); imgui.same_line()
            _button(
                "Travel to Selected Map",
                _travel_to_selected_map,
                "cyan",
                240,
                0,
            )
            _draw_favorite_description_editor("Favorite Description##travel_map_fav_desc", selected_map_name, _favorite_travel_maps, _favorite_travel_map_descriptions)
        else:
            imgui.text_wrapped("No maps match the current search.")

        imgui.spacing()
        _travel_station_search = _input_text("Search Travel Stations", _travel_station_search, 256)
        old_show_all = _travel_show_all_stations
        _travel_show_all_stations = _checkbox("Show All Travel Stations", _travel_show_all_stations)
        if old_show_all != _travel_show_all_stations:
            _travel_selected_station_index = 0
            _invalidate_travel_station_filter_cache()
            save_extra_settings(travel_show_all_stations=bool(_travel_show_all_stations))
        station_results = _current_travel_station_results()
        if _travel_selected_station_index >= len(station_results):
            _travel_selected_station_index = 0
        if _cyber:
            _cyber.section_header("Travel Stations", "gold")
        else:
            imgui.separator(); imgui.text("TRAVEL STATIONS")
        if station_results:
            selected_station = station_results[max(0, min(_travel_selected_station_index, len(station_results) - 1))]
            if _cyber:
                _muted_wrapped(f"Selected station: {selected_station['station']} | Showing {len(station_results)} station(s){' across all maps' if _travel_show_all_stations else ' for ' + (selected_map or 'selected map')}.")
            else:
                imgui.text_wrapped(f"Selected station: {selected_station['station']} | Showing {len(station_results)} station(s){' across all maps' if _travel_show_all_stations else ''}.")
            child_open = _begin_child_region("sqbt_travel_station_scroll_list", _remaining_child_height(360.0, 60.0))
            visible_rows = station_results if child_open else station_results[:16]
            for index, entry in enumerate(visible_rows):
                fav = _fav_prefix(str(entry.get('station', '')), _favorite_travel_stations)
                label = f"{fav}{entry['display_name']}{_fav_description(str(entry.get('station', '')), _favorite_travel_station_descriptions)}###travel_station_{index}"
                if _selectable_row(label, index == _travel_selected_station_index):
                    _travel_selected_station_index = index
            if child_open:
                _end_child_region()
            selected_station_name = str(selected_station.get("station", ""))
            station_fav_label = "Unfavorite Station" if selected_station_name in _favorite_travel_stations else "Favorite Station"
            _button(station_fav_label, _toggle_selected_station_favorite, "purple", 160, 0); imgui.same_line()
            _button(
                "Travel to Selected Station",
                _travel_to_selected_station,
                "gold",
                260,
                0,
            )
            _draw_favorite_description_editor("Favorite Description##travel_station_fav_desc", selected_station_name, _favorite_travel_stations, _favorite_travel_station_descriptions)
        else:
            imgui.text_wrapped("No travel stations match the selected map/search.")
    _sq_end_card()

def _draw_encounter_builder_tab() -> None:
    def _begin_card(title: str, accent: str, height: float) -> bool:
        return _sq_begin_card(title, "world", height)

    def _end_card() -> None:
        _sq_end_card()

    _encounter_ui.draw_encounter_builder_tab(
        muted_wrapped=_muted_wrapped,
        begin_card=_begin_card,
        end_card=_end_card,
        tab_height=_tab_card_height(760.0),
        combo=_combo,
        input_text=_input_text,
    )


def _draw_mob_spawner_tab() -> None:
    def _begin_card(title: str, accent: str, height: float) -> bool:
        return _sq_begin_card(title, "world", height)

    def _end_card() -> None:
        _sq_end_card()

    _mob_spawner_ui.draw_mob_spawner_tab(
        muted_wrapped=_muted_wrapped,
        begin_card=_begin_card,
        end_card=_end_card,
        tab_height=_tab_card_height(760.0),
    )


def _draw_world_spawn_tab() -> None:
    def _begin_card(title: str, accent: str, height: float) -> bool:
        return _sq_begin_card(title, "world", height)

    def _end_card() -> None:
        _sq_end_card()

    _world_spawn_ui.draw_world_spawn_tab(
        button=_button,
        input_text=_input_text,
        combo=_combo,
        checkbox=_checkbox,
        muted_wrapped=_muted_wrapped,
        begin_card=_begin_card,
        end_card=_end_card,
        tab_height=_tab_card_height(760.0),
    )


def _draw_mobility_tab() -> None:
    def _begin_card(title: str, accent: str, height: float) -> bool:
        return _sq_begin_card(title, "mobility", height)

    def _end_card() -> None:
        _sq_end_card()

    _mobility_ui.draw_mobility_tab(
        button=_button,
        input_float_slider=_input_float_slider,
        checkbox=_checkbox,
        muted_wrapped=_muted_wrapped,
        begin_card=_begin_card,
        end_card=_end_card,
        tab_height=_tab_card_height(760.0),
        teleport_to_party_slot=lambda slot: _mobility_runtime.teleport_selected_to_party_slot(
            slot,
            _selected_player_index_value(),
        ),
        teleport_me_to_slot=_mobility_runtime.teleport_local_to_party_slot,
        teleport_slot_to_me=_mobility_runtime.teleport_party_slot_to_local,
        teleport_me_to_selected=lambda: _mobility_runtime.teleport_local_to_selected(
            _selected_player_index_value()
        ),
        teleport_selected_to_me=lambda: _mobility_runtime.teleport_selected_to_local(
            _selected_player_index_value()
        ),
    )


def _draw_player_movement_tab() -> None:
    _tuning_ui.draw_player_movement_tab(
        muted_wrapped=_muted_wrapped,
        tab_height=_tab_card_height(760.0),
    )


def _draw_vehicle_movement_tab() -> None:
    _tuning_ui.draw_vehicle_tab(
        muted_wrapped=_muted_wrapped,
        tab_height=_tab_card_height(760.0),
    )


def _draw_damage_tuning_tab() -> None:
    _tuning_ui.draw_damage_tab(
        muted_wrapped=_muted_wrapped,
        tab_height=_tab_card_height(760.0),
    )


def _draw_resources_tuning_tab() -> None:
    _tuning_ui.draw_resources_tab(
        muted_wrapped=_muted_wrapped,
        tab_height=_tab_card_height(760.0),
    )


def _draw_panel_contents() -> None:
    """Tab body — never call ``imgui.begin()`` here when embedded in BL4 Mod Menu tabs."""
    global _selected_player_index, _serial_text, _currency_amount, _currency_kind_index, _exp_level, _exp_track_index
    imgui = _blimgui.imgui
    _poll_gzo_refresh_result()
    players = _list_party_players()
    draw_brand_banner(_cyber, imgui, version=PANEL_VERSION, session=_session_mode_label(), players=len(players))
    imgui.text_disabled(
        "Tip: Mods → Keybinds → Show/hide BLImGui menu — Squ1ggs's Boosting Tools toggles this panel."
    )
    imgui.spacing()
    if _last_action_status:
        _wrapped_text(f"Last action: {_last_action_status}", ACCENT_INFO)
    labels = [f"[{idx}] {name}" for idx, name in players] or ["No party players found"]

    avail = imgui.get_content_region_avail()
    try:
        body_h = max(180.0, float(getattr(avail, "y", 500.0) or 500.0) - 28.0)
    except Exception:
        body_h = 500.0
    body_began = False
    try:
        imgui.begin_child("##sq_boost_scroll_body", (0, body_h), False)
        body_began = True
    except TypeError:
        try:
            imgui.begin_child("##sq_boost_scroll_body", (0, body_h))
            body_began = True
        except Exception:
            body_began = False
    try:
        _draw_target_bar(players, labels)
        imgui.separator()
        _draw_tabs()
        _draw_feature_palette()
        if _feature_jump_label:
            _wrapped_text(f"Jumped to: {_feature_jump_label}", ACCENT_INFO)
        imgui.separator()

        if _active_tab == 0:
            _draw_home_dashboard(players, labels)
        elif _active_tab == 1:
            _draw_player_workspace()
        elif _active_tab == 2:
            _draw_progression_workspace()
        elif _active_tab == 3:
            _draw_loot_workspace()
        elif _active_tab == 4:
            _draw_serial_workspace()
        elif _active_tab == 5:
            _draw_mobility_tab()
        elif _active_tab == 6:
            _draw_player_movement_tab()
        elif _active_tab == 7:
            _draw_vehicle_movement_tab()
        elif _active_tab == 8:
            _draw_damage_tuning_tab()
        elif _active_tab == 9:
            _draw_resources_tuning_tab()
        elif _active_tab == 10:
            _draw_world_workspace()
        elif _active_tab == 11:
            _draw_loot_shapes_tab()
        elif _active_tab == 12:
            _draw_log_card(full_page=True)

        if _cyber:
            imgui.separator()
            _wrapped_text("SQU1GGS // Boosting Tools  |  release " + PANEL_VERSION, ACCENT_PRIMARY)
    finally:
        if body_began:
            try:
                imgui.end_child()
            except Exception:
                pass


def _sqbt_panel_draw() -> None:
    """Dedicated Squ1ggs Boosting Tools window — never a tab inside BL4 Mod Menu."""
    imgui = _blimgui.imgui
    style_count = push_squ1ggs_window_style(imgui, _cyber)
    try:
        _apply_panel_window_layout(imgui)
        visible, open_state = imgui.begin(WINDOW_TITLE, True)
    finally:
        if style_count:
            imgui.pop_style_color(style_count)

    if open_state is False:
        squ1ggs_boost_tools_close()
        imgui.end()
        return

    if visible:
        try:
            _draw_panel_contents()
        except Exception as exc:
            logging.error(f"[Squ1ggs's Boosting Tools | UI] draw error: {exc!r}")
            _recover_imgui_child_stack()
    imgui.end()


def draw_window() -> None:
    """Back-compat alias — always the standalone SQBT host callback."""
    _sqbt_panel_draw()


def squ1ggs_boost_tools_open() -> None:
    try:
        if hasattr(_blimgui, "close_conflicting_menus"):
            _blimgui.close_conflicting_menus(keep_callback=_sqbt_panel_draw)
        if hasattr(_blimgui, "acquire_imgui_host"):
            _blimgui.acquire_imgui_host(_sqbt_panel_draw, WINDOW_TITLE, width=1120, height=820)
        else:
            _blimgui.create_window(WINDOW_TITLE, width=1120, height=820, callback=_sqbt_panel_draw)
        _PANEL_CONTROLLER.window_owned = True
    except Exception as exc:
        _log(f"failed to open BLImGui panel: {exc!r}")


def squ1ggs_boost_tools_close() -> None:
    _PANEL_CONTROLLER.window_owned = False
    try:
        if hasattr(_blimgui, "close_window_if_draw_callback"):
            _blimgui.close_window_if_draw_callback(_sqbt_panel_draw)
        elif hasattr(_blimgui, "is_window_open") and _blimgui.is_window_open():
            _blimgui.close_window()
    except Exception:
        pass


@keybind("Show/hide BLImGui menu — Squ1ggs's Boosting Tools")
def squ1ggs_boost_tools_toggle() -> None:
    if hasattr(_blimgui, "is_callback_active") and _blimgui.is_callback_active(_sqbt_panel_draw):
        if hasattr(_blimgui, "prepare_menu_toggle") and not _blimgui.prepare_menu_toggle():
            _log("toggle ignored (debounce) — wait briefly or run blimgui_reset")
            return
        squ1ggs_boost_tools_close()
        return
    if hasattr(_blimgui, "prepare_menu_toggle") and not _blimgui.prepare_menu_toggle():
        _log("toggle ignored (debounce or host busy) — wait briefly or run blimgui_reset")
        return
    squ1ggs_boost_tools_open()


@command("sqbt_panel", description="Open Squ1ggs's Boosting Tools BLImGui panel.")
def _cmd_squ1ggs_boost_panel(_) -> None:
    squ1ggs_boost_tools_open()


@command("sqbt_travel_tuba_boss", description="Travel to Tuba_P and teleport to the boss arena.")
def _cmd_travel_tuba_boss(_) -> None:
    logging.info(travel_to_preset("tuba_boss_arena"))


@command("sqbt_freecam_off", description="Force-disable debug/freecam and return view to your pawn.")
def _cmd_freecam_off(_) -> None:
    logging.info(force_disable_debug_cam())
