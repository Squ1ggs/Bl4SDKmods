"""Spawn WorldPainter GbxActor mix defs via console (host / in-world)."""

from __future__ import annotations

import json
import pkgutil
from typing import Any

from unrealsdk import logging

from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate

_PREFIX = "[Squ1ggs Boosting Tools | World Spawn]"

_CATALOG_CACHE: list[dict[str, str]] | None = None
_ENEMY_CACHE: list[str] | None = None
_MIX_CURSOR: dict[str, int] = {}
_last_status: str = ""


def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")


def is_host() -> bool:
    try:
        world, _gs = _gbc_session_world_and_gamestate()
        return bool(_gbc_is_listen_host_world(world))
    except Exception:
        return False


def load_catalog() -> list[dict[str, str]]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return list(_CATALOG_CACHE)
    blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], "squ1ggs_world_spawn_catalog.json")
    if blob is None:
        _CATALOG_CACHE = []
        return []
    data = json.loads(blob.decode("utf-8"))
    rows = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        _CATALOG_CACHE = []
        return []
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        mix_id = str(row.get("mix_id", "")).strip()
        if not mix_id:
            continue
        out.append({
            "mix_id": mix_id,
            "category": str(row.get("category", "Other")).strip() or "Other",
            "source": str(row.get("source", "")).strip(),
        })
    _CATALOG_CACHE = out
    return list(out)


def categories() -> list[str]:
    cats = sorted({str(r.get("category", "Other")) for r in load_catalog()})
    return cats or ["Other"]


def filter_entries(search: str = "", category: str = "") -> list[dict[str, str]]:
    q = (search or "").strip().lower()
    cat = (category or "").strip()
    rows = load_catalog()
    if cat and cat != "All":
        rows = [r for r in rows if str(r.get("category", "")) == cat]
    if q:
        rows = [r for r in rows if q in str(r.get("mix_id", "")).lower() or q in str(r.get("category", "")).lower()]
    return rows


def last_status() -> str:
    return str(_last_status or "")


def _concrete_enemies() -> list[str]:
    global _ENEMY_CACHE
    if _ENEMY_CACHE is not None:
        return list(_ENEMY_CACHE)
    blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], "data/game_data.json")
    data = json.loads(blob.decode("utf-8")) if blob else {}
    rows = data.get("enemies", []) if isinstance(data, dict) else []
    enemies = {
        str(code).strip() for code in rows
        if str(code).strip().lower().startswith("char_")
        and not str(code).strip().lower().endswith("_shared")
    }
    _ENEMY_CACHE = sorted(enemies)
    return list(_ENEMY_CACHE)


def _resolve_mix_member(mix_id: str) -> str:
    """Resolve a WorldPainter Mix_* family to a real spawnable Char_* member."""
    low = mix_id.lower()
    aliases = {
        "bandit": ("guntoter", "psycho", "scav"),
        "order": ("order", "grunt"),
        "redguard": ("redguard",),
        "bat": ("bat",),
        "beast": ("beast",),
        "cat": ("cat",),
        "creep": ("creep",),
        "thresher": ("thresher",),
        "pangolin": ("pangolin",),
        "ripper": ("ripper",),
    }
    wanted = next((tokens for key, tokens in aliases.items() if key in low), ())
    enemies = _concrete_enemies()
    candidates = [code for code in enemies if any(token in code.lower() for token in wanted)]
    if not candidates:
        candidates = [
            code for code in enemies
            if any(token in code.lower() for token in ("grunt", "guntoter", "psycho"))
            and "boss" not in code.lower()
        ]
    if not candidates:
        return ""
    cursor = _MIX_CURSOR.get(low, 0)
    _MIX_CURSOR[low] = cursor + 1
    return candidates[cursor % len(candidates)]


def spawn_mix_def(
    mix_id: str,
    *,
    count: int = 1,
    aggro_mode: str = "attack_me",
    party_index: int = 2,
    spawn_anchor: str = "local",
) -> tuple[bool, str]:
    global _last_status
    token = str(mix_id or "").strip()
    if not token:
        _last_status = "No mix id selected."
        return False, _last_status
    if not is_host():
        _last_status = "Local session authority is unavailable; the game cannot accept this spawn request."
        return False, _last_status
    member = _resolve_mix_member(token)
    if not member:
        _last_status = f"Could not resolve `{token}` to a concrete Char_* definition."
        return False, _last_status
    try:
        from .embedded_bms import get_controller

        controller = get_controller()
        count = max(1, min(int(count), 999))
        controller.ui.aggro_mode = str(aggro_mode or "attack_me")
        controller.ui.party_index = max(0, int(party_index))
        requested_anchor = str(spawn_anchor or "local").strip().lower()
        controller.ui.spawn_anchor = (
            requested_anchor
            if requested_anchor in ("local", "party", "npc_nearest")
            else "local"
        )
        ok, msg = controller.spawn_mob(member, count=count, defer=True)
        _last_status = (
            f"{token} -> {member} x{count} "
            f"[{controller.ui.spawn_anchor}; {controller.ui.aggro_mode}]: {msg}"
        )
        _log(_last_status)
        return bool(ok), _last_status
    except Exception as exc:
        _last_status = f"Could not spawn `{token}` as `{member}`: {exc!r}"
    _log(_last_status)
    return False, _last_status
