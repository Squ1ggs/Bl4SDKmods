"""Spawn dump ItemPoolList inline ItemPoolDefs (Gomie / patch raid lists).

Nexus-Data-ItemPoolList.json stores some named legendaries as embedded
ItemPoolDef instances (binstance + inv'ROOT.comp_*'), not as itempool_* rows.
Those must be rolled from the live ItemPoolList object — never serial/mail.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import unrealsdk

# Patch Nexus-Data-ItemPoolList.json export names.
_DUMP_ITEMPOOLLIST_NAMES: tuple[str, ...] = (
    "ItemPoolList_Raid2_Thol",
    "ItemPoolList_Raid2_Thol_True",
    "ItemPoolList_Raid2_Subjugator",
    "ItemPoolList_Raid2_Subjugator_True",
    "ItemPoolList_BetaMaxxx",
    "ItemPoolList_BetaMaxxx_TRUE",
    "ItemPoolList_StealthPredator",
    "ItemPoolList_StealthPredator_TrueBoss",
)

# Ordonite / dedicated-drop lists — base inv comps (no phosphene customization).
_ORDONITE_ITEMPOOLLIST_NAMES: tuple[str, ...] = (
    "ItemPoolList_Ordonite_Meathead",
    "ItemPoolList_Ordonite_Meathead_TRUE",
    "ItemPoolList_Ordonite_Splice",
    "ItemPoolList_Ordonite_Splice_TRUE",
    "ItemPoolList_Ordonite_Phalanx",
    "ItemPoolList_Ordonite_Phalanx_TRUE",
    "ItemPoolList_Ordonite_Pangolin",
    "ItemPoolList_Ordonite_Pangolin_TRUE",
    "ItemPoolList_Ordonite_Cat",
    "ItemPoolList_Ordonite_Cat_TRUE",
    "ItemPoolList_Ordonite_PGG_Activity",
    "ItemPoolList_Ordonite_PGG_Mission",
)

# Dump-accurate preferred lists (NCS patch ItemPoolList).
_INV_PREFERRED_LISTS: dict[str, tuple[str, ...]] = {
    "jak_ar.comp_05_legendary_gomie": (
        "ItemPoolList_Raid2_Thol",
        "ItemPoolList_Raid2_Thol_True",
    ),
    "bor_sm.comp_05_legendary_jailbroken": (
        "ItemPoolList_Raid2_Subjugator",
        "ItemPoolList_Raid2_Subjugator_True",
        "ItemPoolList_Raid2_Thol",
        "ItemPoolList_Raid2_Thol_True",
    ),
    "jak_sr.comp_05_legendary_burrow": (
        "ItemPoolList_BetaMaxxx",
        "ItemPoolList_BetaMaxxx_TRUE",
    ),
    # FishGrenade_Slippy crashes GameThread; StealthPredator embeds Slippy inline.
    "tor_grenade_gadget.comp_05_legendary_slippy": (
        "ItemPoolList_StealthPredator",
        "ItemPoolList_StealthPredator_TrueBoss",
    ),
}

_HANDLE_RE = re.compile(r"(?i)(?:inv|itempool)'([^']+)'")
_NAMED_POOL_RE = re.compile(r"(?i)itempool'([^']+)'")
_LIVE_LIST_CACHE: dict[str, Any] = {}
_MATCH_CACHE: dict[str, tuple[str, ...]] = {}


def _inv_inner(inv_handle: str) -> str:
    raw = str(inv_handle or "").strip()
    match = re.match(r"(?i)inv'([^']+)'", raw)
    return (match.group(1) if match else raw).strip()


def _needles(inv_handle: str) -> tuple[str, ...]:
    inner = _inv_inner(inv_handle)
    if not inner:
        return ()
    tail = inner.split(".")[-1]
    out = [inner.lower(), tail.lower()]
    if "." in inner:
        root, _, rest = inner.partition(".")
        out.append(f"{root.lower()}.{rest.lower()}")
    return tuple(dict.fromkeys(n for n in out if n))


def _as_seq(value: Any) -> list[Any]:
    if value is None or isinstance(value, (str, bytes, int, float, bool)):
        return []
    try:
        return list(value)
    except Exception:
        pass
    try:
        return [value[i] for i in range(len(value))]
    except Exception:
        return []


def _blob(value: Any, *, depth: int = 0, seen: set[int] | None = None) -> str:
    if value is None or depth > 10:
        return ""
    seen = seen if seen is not None else set()
    key = id(value)
    if key in seen:
        return ""
    seen.add(key)
    parts: list[str] = []
    try:
        parts.append(str(value))
    except Exception:
        pass
    for attr in (
        "Handle",
        "handle",
        "Name",
        "_experimental_name",
        "DefName",
        "ItemPool",
        "itempool",
        "Item",
        "item",
        "Instance",
        "instance",
        "Items",
        "items",
    ):
        try:
            child = getattr(value, attr, None)
        except Exception:
            child = None
        if child is None or child is value:
            continue
        parts.append(_blob(child, depth=depth + 1, seen=seen))
        for el in _as_seq(child):
            parts.append(_blob(el, depth=depth + 1, seen=seen))
    return " ".join(parts).lower()


def _matches(value: Any, needles: tuple[str, ...]) -> bool:
    if not needles:
        return False
    blob = _blob(value)
    return any(needle in blob for needle in needles)


def _named_pools_from(value: Any) -> list[str]:
    blob = _blob(value)
    return [match.group(1) for match in _NAMED_POOL_RE.finditer(blob)]


def _live_pool_is_shiny(value: Any) -> bool:
    """True when a live ItemPoolDef/provider embeds a *_shiny roll or shiny cosmetic."""
    blob = _blob(value)
    if "cosmetics_weapon_shiny" in blob:
        return True
    if "_shiny" in blob and "itempool_" in blob:
        return True
    return False


def _filter_live_pools(values: list[Any], *, wants_shiny: bool) -> list[Any]:
    out: list[Any] = []
    seen: set[int] = set()
    for value in values:
        if value is None:
            continue
        key = id(value)
        if key in seen:
            continue
        seen.add(key)
        if _live_pool_is_shiny(value) == bool(wants_shiny):
            out.append(value)
    return out


def _find_list(name: str) -> Any | None:
    cached = _LIVE_LIST_CACHE.get(name.lower())
    if cached is not None:
        return cached
    obj = None
    for cls in ("ItemPoolList", "/Script/GbxGame.ItemPoolList", "Object"):
        try:
            obj = unrealsdk.find_object(cls, name)
        except Exception:
            obj = None
        if obj is not None:
            break
    if obj is not None:
        _LIVE_LIST_CACHE[name.lower()] = obj
    return obj


@lru_cache(maxsize=1)
def _catalog_itempoollist_index() -> dict[str, tuple[str, ...]]:
    """NCS-derived catalog_key → ItemPoolList names with embedded base inv rows."""
    path = (
        Path(__file__).resolve().parent
        / "data"
        / "reference"
        / "named_unique_itempoollist.json"
    )
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, tuple[str, ...]] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            cat = str(key or "").strip().lower()
            if not cat:
                continue
            if isinstance(value, list):
                names = tuple(str(v).strip() for v in value if str(v).strip())
            else:
                names = ()
            if names:
                out[cat] = names
    return out


def _catalog_key_from_inv_handle(inv_handle: str) -> str:
    inner = _inv_inner(inv_handle).lower()
    if "." not in inner:
        return inner.replace(".", "_")
    root, _, comp = inner.partition(".")
    return f"{root}_{comp}"


def _iter_dump_lists(inv_handle: str) -> list[Any]:
    inner = _inv_inner(inv_handle).lower()
    preferred = _INV_PREFERRED_LISTS.get(inner, ())
    catalog_lists = _catalog_itempoollist_index().get(
        _catalog_key_from_inv_handle(inv_handle), ()
    )
    names: list[str] = []
    seen_names: set[str] = set()

    def add_name(name: str) -> None:
        raw = str(name or "").strip()
        low = raw.lower()
        if not low or low in seen_names:
            return
        seen_names.add(low)
        names.append(raw)

    for name in (*preferred, *catalog_lists, *_ORDONITE_ITEMPOOLLIST_NAMES, *_DUMP_ITEMPOOLLIST_NAMES):
        add_name(name)
    found: list[Any] = []
    seen: set[int] = set()
    for name in names:
        obj = _find_list(name)
        if obj is None:
            continue
        key = id(obj)
        if key in seen:
            continue
        seen.add(key)
        found.append(obj)
    return found


def _iter_all_itempool_lists() -> list[Any]:
    out: list[Any] = []
    seen: set[int] = set()
    try:
        objs = list(unrealsdk.find_all("ItemPoolList", False) or [])
    except Exception:
        objs = []
    for obj in objs:
        if obj is None:
            continue
        key = id(obj)
        if key in seen:
            continue
        seen.add(key)
        out.append(obj)
    return out


_GENERIC_PEARL_BY_SUFFIX: tuple[tuple[str, str], ...] = (
    ("_ar", "itempool_ar_06_pearl"),
    ("_sr", "itempool_sr_06_pearl"),
    ("_sm", "itempool_sm_06_pearl"),
    ("_sg", "itempool_sg_06_pearl"),
    ("_ps", "itempool_ps_06_pearl"),
)


def _generic_pearl_pool_names_for_inv(inv_handle: str) -> list[str]:
    """Live type pearl parents that can roll this inv-comp (AR/SR/SM/SG/PS 06 pearl)."""
    inner = _inv_inner(inv_handle).lower()
    root = inner.split(".", 1)[0]
    out: list[str] = []
    for suffix, pool in _GENERIC_PEARL_BY_SUFFIX:
        if root.endswith(suffix) and pool not in out:
            out.append(pool)
    return out


def _find_named_itempool(name: str) -> Any | None:
    raw = str(name or "").strip()
    if not raw:
        return None
    labels = [raw, f"itempool'{raw}'"]
    for label in labels:
        for cls in ("ItemPoolDef", "/Script/GbxGame.ItemPoolDef", "Object"):
            try:
                obj = unrealsdk.find_object(cls, label)
            except Exception:
                obj = None
            if obj is not None:
                return obj
    return None


def _hits_from_entries(entries: Any, needles: tuple[str, ...]) -> list[Any]:
    hits: list[Any] = []
    seen_ids: set[int] = set()
    for entry in _as_seq(entries):
        if not _matches(entry, needles):
            continue
        for value in _entry_pools(entry):
            key = id(value)
            if key in seen_ids:
                continue
            seen_ids.add(key)
            hits.append(value)
        if hits:
            return hits
    return hits


def _entry_pools(entry: Any) -> list[Any]:
    provider = None
    for attr in ("ItemPool", "itempool", "Pool", "pool"):
        try:
            provider = getattr(entry, attr, None)
        except Exception:
            provider = None
        if provider is not None:
            break
    if provider is None:
        provider = entry
    item = None
    for attr in ("Item", "item"):
        try:
            item = getattr(provider, attr, None)
        except Exception:
            item = None
        if item is not None:
            break
    if item is None:
        item = provider
    values: list[Any] = []
    for attr in ("Instance", "instance"):
        try:
            inst = getattr(item, attr, None)
        except Exception:
            inst = None
        if inst is not None:
            values.append(inst)
    if item is not None:
        values.append(item)
    if provider is not None and provider is not item:
        values.append(provider)
    return values


def live_itempool_values_for_inv(inv_handle: str) -> list[Any]:
    """Live ItemPoolDef / provider objects whose dump handle matches inv_handle."""
    needles = _needles(inv_handle)
    if not needles:
        return []
    cache_key = _inv_inner(inv_handle).lower()
    lists = _iter_dump_lists(inv_handle)
    # Never find_all every live ItemPoolList. After Spawn All the world is full of
    # loaded lists; a substring match then rolls a fat world/raid pool (extra guns)
    # instead of the one dump inv. Gomie / Jail-Broken stay on preferred dump lists.

    for lst in lists:
        pools = None
        for attr in ("ItemPools", "itempools", "Pools", "pools"):
            try:
                pools = getattr(lst, attr, None)
            except Exception:
                pools = None
            if pools is not None:
                break
        hits = _hits_from_entries(pools, needles)
        if hits:
            try:
                list_name = str(getattr(lst, "Name", "") or "")
            except Exception:
                list_name = ""
            if list_name:
                _MATCH_CACHE[cache_key] = (list_name,)
            return hits

    for pool_name in _generic_pearl_pool_names_for_inv(inv_handle):
        pool_obj = _find_named_itempool(pool_name)
        if pool_obj is None:
            continue
        items = None
        for attr in ("Items", "items", "ItemPools", "itempools"):
            try:
                items = getattr(pool_obj, attr, None)
            except Exception:
                items = None
            if items is not None:
                break
        hits = _hits_from_entries(items if items is not None else pool_obj, needles)
        if hits:
            _MATCH_CACHE[cache_key] = (pool_name,)
            return hits
    return []


def named_itempools_for_inv(inv_handle: str) -> list[str]:
    needles = _needles(inv_handle)
    if not needles:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for lst in _iter_dump_lists(inv_handle):
        pools = None
        for attr in ("ItemPools", "itempools"):
            try:
                pools = getattr(lst, attr, None)
            except Exception:
                pools = None
            if pools is not None:
                break
        for entry in _as_seq(pools):
            if not _matches(entry, needles):
                continue
            for name in _named_pools_from(entry):
                low = name.lower()
                if low in seen:
                    continue
                seen.add(low)
                names.append(name)
    return names


def spawn_live_named_itempool_def(
    pool_name: str,
    *,
    count: int = 1,
    level: int = 60,
) -> tuple[int, str | None]:
    """World-drop a live ItemPoolDef found by dump/manifest pool name."""
    name = str(pool_name or "").strip()
    if not name:
        return 0, "no pool name"
    obj = _find_named_itempool(name)
    if obj is None:
        return 0, f"no live ItemPoolDef {name}"
    from .comp_loot_drop import drop_item_pool_values

    return drop_item_pool_values(
        [obj],
        cache_key=("named_def", name.lower()),
        count=count,
        level=level,
    )


def spawn_itempoollist_inv_at_feet(
    inv_handles: list[str],
    *,
    count: int = 1,
    level: int = 60,
    require_loot_verify: bool = True,
    wants_shiny: bool = True,
) -> tuple[int, str | None]:
    """World-drop the dump ItemPoolList row that wraps this inv handle."""
    handles = [str(h).strip() for h in inv_handles if str(h).strip()]
    if not handles:
        return 0, "no inv handle"
    errors: list[str] = []

    def _pool_ok(name: str) -> bool:
        low = str(name or "").strip().lower()
        if not low:
            return False
        is_shiny = low.endswith("_shiny") or "_shiny_" in low
        return is_shiny if wants_shiny else not is_shiny

    for handle in handles:
        live = _filter_live_pools(
            live_itempool_values_for_inv(handle),
            wants_shiny=bool(wants_shiny),
        )
        if live:
            from .comp_loot_drop import drop_item_pool_values

            spawned, err = drop_item_pool_values(
                live,
                cache_key=("itempoollist", handle.lower(), "1" if wants_shiny else "0"),
                count=count,
                level=level,
            )
            if spawned > 0:
                return spawned, None
            if err:
                errors.append(err)
        # Named itempool_* rolls are shiny-only for many uniques — never use them
        # for normal legendary rows (Laser Disker / Early Excess would phosphene).
        named: list[str] = []
        if wants_shiny:
            named = [n for n in named_itempools_for_inv(handle) if _pool_ok(n)]
            if named:
                from .ncs_pool_spawn import spawn_itempool_names

                spawned, err = spawn_itempool_names(
                    named,
                    count=count,
                    level=level,
                    require_loot_verify=require_loot_verify,
                )
                if spawned > 0:
                    return spawned, None
                if err:
                    errors.append(err)
        if not live and not named:
            errors.append(f"no live ItemPoolList row for {handle}")
    return 0, errors[0] if errors else "no live ItemPoolList row"
