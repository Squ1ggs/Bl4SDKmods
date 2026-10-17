"""Curated actor option lists for World text (prop logo) dropdowns."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_PROPS: tuple[str, ...] = (
    "electisafe",
    "barrel",
    "goldenchest",
    "moneybox",
    "ammogeyser",
    "breakable_chest",
    "firmware",
    "bank",
    "lostloot",
    "blackmarket",
    "munitions",
    "vending",
)

# Hand-picked IO tokens that clone well as logo glyphs (from io_spawn_catalog).
_IO_CURATED: tuple[str, ...] = (
    "IO_ElectiSafe",
    "IO_Lootable_Heist_MoneyBox",
    "IO_AmmoGeyser",
    "IO_FirmwareTransferMachine",
    "IO_PlayerBank",
    "IO_LostLoot_Machine",
    "IO_VendingMachine_Munitions",
    "IO_VendingMachine_BlackMarket",
    "IO_VendingMachine_Health",
    "IO_VendingMachine_ResupplyStation",
    "IO_VendingMachine_Legend_Legendary",
    "IO_Chest_BreakableLock_Lootable",
    "Lootable_GoldenChest",
    "IO_BipBipVendingMachine",
)

_NPC_CURATED: tuple[str, ...] = (
    "Char_NPC_Claptrap",
    "Char_NPC_Hermes",
    "Char_NPC_Zane",
    "Char_NPC_Amara",
    "Char_NPC_Pickle",
    "Char_NPC_CrackMaBacky",
    "Char_NPC_PrisonBuddy",
    "Char_NPC_IslandGuide",
    "Char_NPC_BoltInventor",
    "Char_NPC_FallenAristocrat",
    "Char_NPC_BuddyScrap",
    "Char_NPC_BuddyNudge",
    "Char_NPC_MeatheadBasic",
    "Char_NPC_GruntBasic",
    "Char_NPC_StrikerBasic",
    "Char_NPC_PhalanxBasic",
    "Char_NPC_DahlGruntSMG",
    "Char_NPC_GunToterBadass_Male",
    "Char_NPC_GunToterBadass_Female",
    "Char_TargetDummy",
)


def _io_catalog_path() -> Path:
    return Path(__file__).resolve().parent / "embedded_bms" / "data" / "io_spawn_catalog.json"


def _game_data_path() -> Path:
    return Path(__file__).resolve().parent / "embedded_oak" / "data" / "game_data.json"


@lru_cache(maxsize=1)
def _extra_io_tokens() -> tuple[str, ...]:
    """Pull a few extra lootable/vending tokens from the BMS IO catalog."""
    path = _io_catalog_path()
    if not path.is_file():
        return ()
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ()
    rows = raw if isinstance(raw, list) else []
    if isinstance(raw, dict):
        for key in ("items", "entries", "ios", "data"):
            if isinstance(raw.get(key), list):
                rows = raw[key]
                break
    out: list[str] = []
    seen = {t.lower() for t in _IO_CURATED}
    needles = (
        "vending",
        "lootable",
        "chest",
        "safe",
        "bank",
        "geyser",
        "firmware",
        "market",
        "ammo",
        "electi",
        "money",
        "munitions",
        "lostloot",
        "resupply",
    )
    for row in rows:
        if not isinstance(row, dict):
            continue
        token = str(row.get("token") or "").strip()
        if not token or token.lower() in seen:
            continue
        low = token.lower()
        if not any(n in low for n in needles):
            continue
        if low.startswith("io_trackable") or "datalayer" in low:
            continue
        out.append(token)
        seen.add(low)
        if len(out) >= 40:
            break
    return tuple(out)


@lru_cache(maxsize=1)
def _extra_npc_tokens() -> tuple[str, ...]:
    path = _game_data_path()
    if not path.is_file():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ()
    enemies = raw.get("enemies") if isinstance(raw, dict) else None
    if not isinstance(enemies, list):
        return ()
    seen = {t.lower() for t in _NPC_CURATED}
    out: list[str] = []
    for name in enemies:
        token = str(name or "").strip()
        if not token or token.lower() in seen:
            continue
        if not (token.startswith("Char_NPC") or token.startswith("Char_NPC_")):
            continue
        if token.endswith("_SHARED"):
            continue
        out.append(token)
        seen.add(token.lower())
        if len(out) >= 30:
            break
    return tuple(out)


def logo_actor_select_options() -> list[str]:
    """Flat select options: props first, then IO tokens, then NPCs."""
    options: list[str] = []
    seen: set[str] = set()

    def _add(token: str) -> None:
        t = str(token or "").strip()
        if not t:
            return
        key = t.lower()
        if key in seen:
            return
        seen.add(key)
        options.append(t)

    for token in _PROPS:
        _add(token)
    for token in _IO_CURATED:
        _add(token)
    for token in _extra_io_tokens():
        _add(token)
    for token in _NPC_CURATED:
        _add(token)
    for token in _extra_npc_tokens():
        _add(token)
    return options


DEFAULT_LOGO_ACTOR = "electisafe"
