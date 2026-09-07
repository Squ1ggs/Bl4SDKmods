"""NCS *_shiny index — inline comp payloads when live shiny pools silent-empty."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_REF = Path(__file__).resolve().parent / "data" / "reference" / "ncs_shiny_pools.json"
_SERIALS_REF = Path(__file__).resolve().parent / "data" / "reference" / "ncs_shiny_serials.json"


def _normalize_pool(pool_name: str) -> str:
    raw = str(pool_name or "").strip()
    if raw.startswith("itempool'") and raw.endswith("'"):
        raw = raw.replace("itempool'", "").rstrip("'")
    return raw.lower()


@lru_cache(maxsize=1)
def _load_index() -> dict[str, dict[str, Any]]:
    if not _REF.is_file():
        return {}
    try:
        doc = json.loads(_REF.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    pools = doc.get("pools")
    if not isinstance(pools, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in pools:
        if not isinstance(row, dict):
            continue
        for field in ("itempool", "entry_key"):
            key = _normalize_pool(str(row.get(field, "")))
            if key:
                out[key] = row
    return out


def lookup_shiny_pool(pool_name: str) -> dict[str, Any] | None:
    return _load_index().get(_normalize_pool(pool_name))


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").strip().lower())


def _pool_weapon_token(pool_name: str) -> str:
    low = _normalize_pool(pool_name)
    if low.endswith("_shiny"):
        low = low[: -len("_shiny")]
    match = re.search(r"_legendary_(.+)$", low) or re.search(r"_pearl_(.+)$", low)
    return _alnum(match.group(1) if match else low)


@lru_cache(maxsize=1)
def _load_serial_index() -> dict[str, str]:
    if not _SERIALS_REF.is_file():
        return {}
    try:
        rows = json.loads(_SERIALS_REF.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(rows, list):
        return {}
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        serial = str(row.get("serial") or "").strip()
        if not serial.startswith("@U"):
            continue
        for field in ("id", "display_name", "name"):
            key = _alnum(str(row.get(field) or ""))
            if key and key not in out:
                out[key] = serial
    return out


def serial_for_shiny_pool(pool_name: str) -> str | None:
    """Dump @U for a shiny pool that has no NCS inv_handle row."""
    token = _pool_weapon_token(pool_name)
    if not token:
        return None
    _EXTRA_TOKEN_ALIASES = {
        "crowdsourced": "midnightdefiance",
        "crowdsourcedshiny": "midnightdefiance",
    }
    token_alnum = _alnum(token)
    alias = _EXTRA_TOKEN_ALIASES.get(token_alnum)
    if alias:
        hit = _load_serial_index().get(alias)
        if hit:
            return hit
    return _load_serial_index().get(token_alnum)


def inline_payload_for_shiny(pool_name: str) -> dict[str, Any] | None:
    """Merge-shaped payload for SpawnLootFromData_* when NCS shiny pool is empty."""
    row = lookup_shiny_pool(pool_name)
    if not row:
        return None
    inv_handle = str(row.get("inv_handle", "")).strip()
    if not inv_handle.lower().startswith("inv'"):
        return None
    payload: dict[str, Any] = {
        "handle_variants": [inv_handle],
        "__shiny_inline": True,
        "itempool": str(row.get("itempool") or pool_name).strip(),
        "items": [{"item": {"item": {"handle": inv_handle}}}],
    }
    customization = str(row.get("customization", "")).strip()
    if customization:
        payload["customizationlist"] = [
            {
                "customization": customization,
                "probability": {
                    "datatablevalue": {"datatable": "gbx_ue_data_table'none'"},
                    "constant": "1.0",
                },
            }
        ]
    return payload


@lru_cache(maxsize=1)
def _live_catalog_handles() -> dict[str, str]:
    """catalog_key (underscore) → dump inv inner handle (ROOT.comp_*)."""
    path = _REF.parent / "ncs_live_catalog.json"
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, str] = {}
    if not isinstance(doc, dict):
        return out
    for key, value in doc.items():
        if not isinstance(value, dict):
            continue
        handle = str(value.get("handle") or "").strip()
        if not handle or "." not in handle:
            continue
        dot_key = str(key or "").strip().lower()
        if "." in dot_key:
            root, comp = dot_key.split(".", 1)
            cat_key = f"{root}_{comp}"
        else:
            cat_key = dot_key.replace(".", "_")
        out[cat_key] = handle
    return out


def inv_handles_for_named_unique(catalog: str, shiny_pool: str = "") -> list[str]:
    """Base inv'ROOT.comp_* handles — same gun as *_shiny, no customizationlist."""
    cat = str(catalog or "").strip().lower()
    pool = str(shiny_pool or "").strip()
    out: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        text = str(raw or "").strip()
        if not text:
            return
        if not text.lower().startswith("inv'"):
            text = f"inv'{text}'"
        low = text.lower()
        if low in seen:
            return
        seen.add(low)
        out.append(text)

    row = lookup_shiny_pool(pool) if pool else None
    if row:
        add(str(row.get("inv_handle") or ""))
    live = _live_catalog_handles().get(cat)
    if live:
        add(live)
    if cat and not out:
        match = re.match(r"^(.+)_(comp_0[56]_.+)$", cat)
        if match:
            root, comp = match.group(1), match.group(2)
            add(f"{root}.{comp}")
            add(f"{root.upper()}.{comp}")
            try:
                from .comp_loot_drop import _comp_inv_handle_variants

                for variant in _comp_inv_handle_variants(f"{root}.{comp}"):
                    add(variant.replace("inv'", "").replace("'", ""))
            except Exception:  # noqa: BLE001
                pass
    return out


def inline_payload_for_base_legendary(
    shiny_pool: str,
    *,
    catalog: str = "",
) -> dict[str, Any] | None:
    """Inline SpawnLootFromData payload — base comp only, never phosphene customization."""
    handles = inv_handles_for_named_unique(catalog, shiny_pool)
    if not handles:
        return None
    return {
        "__synthetic": True,
        "__exact_inv": False,
        "handle_variants": handles,
        "items": [{"item": {"item": {"handle": handles[0]}}}],
    }
