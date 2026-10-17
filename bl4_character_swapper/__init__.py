# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 RDPSqu1ggs
"""Standalone BL4 appearance mod; no desktop app or SQBT installation needed."""
from argparse import Namespace
import sys

from mods_base import build_mod, Game, CoopSupport, command, keybind
from unrealsdk import hooks, logging
from .runtime import CONTROLLER, Model, register_model, unregister_model

TITLE = "Appearance"
HOOK = "/Script/GbxUIUMG.GbxUIUMGTickWidget:BP_TickWidget"
HOOK_ID = "squ1ggs_appearance.game_tick"
HOOK_TYPE = getattr(hooks.Type, "POST_UNCONDITIONAL", hooks.Type.POST)
_BLIMGUI = None
_BLIMGUI_MODE = ""
_WINDOW_OWNED = False
_WINDOW_DRAW = None
VERSION = "0.1.2"
BLIMGUI_DOWNLOAD = "https://github.com/juso40/blimgui/raw/ff5be35f41d69f28056befdd1bfb8caddae5892b/blimgui.zip"
BLIMGUI_PAGE = "https://bl-sdk.github.io/oak2-mod-db/mods/blimgui/"


def _log(message: str) -> None:
    logging.info("[Squ1ggs Appearance] " + str(message))

def _tick(*_args):
    CONTROLLER.tick()

def on_enable():
    sqbt = sys.modules.get("Squ1ggsBoostingTools.dev_tools")
    if sqbt is not None and (getattr(sqbt, "_appearance_states", {}) or
                            getattr(sqbt, "_appearance_pending", {}).get("code")):
        raise RuntimeError("Restore SQBT's current appearance before enabling the standalone swapper.")
    CONTROLLER.acquire("standalone")
    _try_register_blimgui()
    _log(f"{VERSION} enabled. BLImGui is strongly recommended for the character picker; use F10 or type asw_help in the SDK console. Also included in Squ1ggs Boosting Tools.")


def _try_register_blimgui() -> bool:
    global _BLIMGUI, _BLIMGUI_MODE
    if _BLIMGUI is not None:
        return True
    try:
        import blimgui
        from imgui_bundle import imgui as _imgui  # noqa: F401
        from .ui import draw
        if all(callable(getattr(blimgui, name, None)) for name in ("register_tab", "open_registered_tab", "remove_tab")):
            blimgui.register_tab(TITLE, draw, author="RDPSqu1ggs")
            mode = "tabs"
        elif all(callable(getattr(blimgui, name, None)) for name in ("create_window", "is_window_open", "close_window")):
            mode = "window"
        else:
            raise RuntimeError("This BLImGui build exposes neither the supported window API nor tab API")
        _BLIMGUI = blimgui
        _BLIMGUI_MODE = mode
        _log(f"BLImGui found ({mode} interface); F10 opens the character picker.")
        return True
    except Exception as exc:
        _BLIMGUI = None
        _BLIMGUI_MODE = ""
        _log(f"BLImGui UI unavailable ({exc}); console commands remain available. BLImGui is strongly recommended: {BLIMGUI_PAGE} — type asw_help.")
        return False

def _owns_window():
    if not _WINDOW_OWNED or _BLIMGUI is None:
        return False
    current = getattr(getattr(_BLIMGUI, "IMPL", None), "_draw_callback", None)
    return current is None or current is _WINDOW_DRAW


def on_disable():
    global _BLIMGUI, _BLIMGUI_MODE, _WINDOW_OWNED, _WINDOW_DRAW
    # SDK enable/disable callbacks run in the game context.
    try:
        CONTROLLER.release("standalone")
    except Exception as exc:
        _log(f"Appearance cleanup failed: {exc}")
    if _BLIMGUI is not None:
        try:
            if _BLIMGUI_MODE == "tabs":
                _BLIMGUI.remove_tab(TITLE)
            elif _owns_window() and _BLIMGUI.is_window_open():
                _BLIMGUI.close_window()
        except Exception as exc:
            _log(f"Could not remove the BLImGui tab cleanly: {exc}")
    _BLIMGUI = None
    _BLIMGUI_MODE = ""
    _WINDOW_OWNED = False
    _WINDOW_DRAW = None

@keybind("Open BL4 Character Swapper", key="F10")
def open_ui():
    global _WINDOW_OWNED, _WINDOW_DRAW
    if _BLIMGUI is None and not _try_register_blimgui():
        _log(f"BLImGui is strongly recommended for the character picker: {BLIMGUI_DOWNLOAD}. SDK console controls work without it; type asw_help.")
        return
    try:
        if _BLIMGUI_MODE == "tabs":
            _BLIMGUI.open_registered_tab(TITLE)
        else:
            if _BLIMGUI.is_window_open():
                if _owns_window():
                    _BLIMGUI.close_window()
                    _WINDOW_OWNED = False
                else:
                    _log("Another BLImGui window is open. Close it, then press F10 for Appearance.")
                return
            from .ui import draw
            _BLIMGUI.create_window("BL4 Character Swapper", width=820, height=780, callback=draw)
            _WINDOW_DRAW = draw
            _WINDOW_OWNED = True
    except Exception as exc:
        _log(f"Could not open the BLImGui tab: {exc}. Use asw_help for console controls.")


def _query_models(query: str):
    needle = " ".join(str(query or "").split()).casefold()
    choices = CONTROLLER.choices()
    if not needle:
        return choices
    exact = [row for row in choices if needle in (row["key"].casefold(), row["name"].casefold())]
    return exact or [row for row in choices if needle in row["key"].casefold() or needle in row["name"].casefold()]


def _resolve_model(query: str) -> str | None:
    matches = _query_models(query)
    if len(matches) == 1:
        return matches[0]["key"]
    if not matches:
        _log(f"No native actor matches {query!r}. Run asw_list to see catalog choices.")
        return None
    _log(f"{len(matches)} actors match {query!r}; use a more specific name:")
    for row in matches[:20]:
        _log(f"  {row['key']} — {row['name']} [{row['group']}]")
    return None


def _target_for_index(index: int):
    players = list(CONTROLLER.players)
    if index < 0 or index >= len(players):
        _log(f"Player index {index} is unavailable. Run asw_players to refresh and list targets.")
        return None
    return players[index]


@command("asw_help", description="Show BL4 Character Swapper controls (BLImGui is optional).")
def asw_help(_args: Namespace) -> None:
    for line in (
        "BL4 Character Swapper — works standalone with SDK console controls.",
        "BLImGui is strongly recommended: F10 opens a searchable character picker, preview/apply/restore controls and player selection.",
        f"Official BL4 BLImGui download (1.1, Python 3.14 x64): {BLIMGUI_DOWNLOAD}",
        f"Install instructions / future SDK updates: {BLIMGUI_PAGE}",
        "Created and maintained by RDPSqu1ggs — github.com/Squ1ggs/Bl4SDKmods",
        "  asw_list [search]              Search the native BL4 character catalog.",
        "  asw_players                    List local player and lobby target indexes.",
        "  asw_preview <name or code>     Spawn a preview beside you (host required).",
        "  asw_apply <name or code>       Apply to yourself.",
        "  asw_apply <name or code> --player INDEX   Apply to a lobby player (host).",
        "  asw_restore [--player INDEX]   Restore yourself or a lobby player.",
        "  asw_restore_all                Restore every changed appearance.",
        "  asw_clear                      Remove unworn previews.",
        "F10 supports official BLImGui windows and compatible custom tab menus. Without BLImGui, use the commands above.",
        "Also included in Squ1ggs Boosting Tools: use its Appearance tab without installing this standalone mod or BLImGui.",
        "SDK console, BLImGui and the matching SQBT EXE share one appearance service when used together.",
    ):
        _log(line)


@command("asw_list", description="Search the native Borderlands 4 character catalog by name or code.")
def asw_list(args: Namespace) -> None:
    matches = _query_models(" ".join(args.search or []))
    if not matches:
        _log("No native characters match that search. Try a shorter name or an exact actor code.")
        return
    _log(f"Native catalog choices: {len(matches)} (showing up to 50; unloaded content is resolved on demand)")
    for index, row in enumerate(matches[:50]):
        _log(f"  {index}: {row['key']} — {row['name']} [{row['group']}]")


asw_list.add_argument("search", nargs="*", help="Optional name or actor-code filter.")


@command("asw_players", description="List the local player and current lobby player indexes.")
def asw_players(_args: Namespace) -> None:
    players = list(CONTROLLER.players)
    if not players:
        _log("No player pawns are ready yet. Load into a map and retry asw_players.")
        return
    _log("Appearance targets (indexes refresh as the lobby changes):")
    for index, row in enumerate(players):
        _log(f"  {index}: {row['name']} ({'local' if row['key'] == 'self' else 'host target'})")


def _cmd_preview(args: Namespace) -> None:
    key = _resolve_model(" ".join(args.model))
    if key is not None:
        accepted = CONTROLLER.request("preview", model=key)
        _log(f"Queued preview for {key}." if accepted else CONTROLLER.status)


asw_preview = command("asw_preview", description="Load and preview a native character beside you. Host authority is required.")(_cmd_preview)
asw_preview.add_argument("model", nargs="+", help="Unique actor display name or code from asw_list.")


def _cmd_apply(args: Namespace) -> None:
    key = _resolve_model(" ".join(args.model))
    target = _target_for_index(args.player)
    if key is not None and target is not None:
        accepted = CONTROLLER.request("apply", model=key, owner=target["key"])
        _log(f"Queued {key} for player {args.player} ({target['name']})." if accepted else CONTROLLER.status)


asw_apply = command("asw_apply", description="Load and apply a native character to yourself or a lobby player (host required to spawn).")(_cmd_apply)
asw_apply.add_argument("model", nargs="+", help="Unique actor display name or code from asw_list.")
asw_apply.add_argument("--player", type=int, default=0, help="Target index from asw_players; 0 is local player.")


def _cmd_restore(args: Namespace) -> None:
    target = _target_for_index(args.player)
    if target is not None:
        accepted = CONTROLLER.request("restore", owner=target["key"])
        _log(f"Queued restore for {target['name']}." if accepted else CONTROLLER.status)


asw_restore = command("asw_restore", description="Restore yourself or one lobby player's original appearance.")(_cmd_restore)
asw_restore.add_argument("--player", type=int, default=0, help="Target index from asw_players; 0 is local player.")


@command("asw_restore_all", description="Restore every appearance changed by the standalone swapper.")
def asw_restore_all(_args: Namespace) -> None:
    CONTROLLER.request("restore_all")
    _log("Queued restore for all changed players.")


@command("asw_clear", description="Remove unworn character previews created by the standalone swapper.")
def asw_clear(_args: Namespace) -> None:
    CONTROLLER.request("clear")
    _log("Queued removal of unworn previews.")

MOD = build_mod(name="BL4 Character Swapper", author="RDPSqu1ggs", version=VERSION,
          description=f"Standalone BL4 character swaps; no boosting tool required. BLImGui is strongly recommended for the F10 character picker: {BLIMGUI_PAGE} . Console-only controls: asw_help. Supports official BLImGui windows and compatible custom tabs. Also included in Squ1ggs Boosting Tools' Appearance tab; separate standalone/BLImGui installation is unnecessary for EXE users. Multiplayer validation pending.",
          supported_games=Game.BL4, coop_support=CoopSupport.Unknown,
          keybinds=[open_ui], on_enable=on_enable, on_disable=on_disable)
