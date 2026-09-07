"""World-drop pearlescent / comp rows via LootFunctionLibrary (merge inline path)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import unrealsdk
from unrealsdk.unreal import IGNORE_STRUCT

from .inventory_def_ptr import (
    build_inventory_fgame_data_handles,
    build_inventory_fgbx_def_ptr,
    find_live_inventory_def,
    iter_inventory_item_def_providers,
)
from .loot_verify import nearby_loot_keys, player_location_from_pc, verify_available
from .ncs_pool_spawn import (
    _get_player_pose,
    _get_spawn_transform,
    _quat_from_rotation,
    _spawn_pose,
)
from .runtime_cache import get_world
from .spawn_pc import resolve_spawn_pc

MAX_ITEM_LEVEL = 999999
INV_HANDLE_RE = re.compile(r"(?i)\binv'([^']+)'")
_FORCE_EXACT_LOOT_PATTERN = False
LEGENDARY_COMP_SUFFIX_RE = re.compile(r"(?i)comp_05_legendary_([a-z0-9_]+)")
PEARL_COMP_SUFFIX_RE = re.compile(r"(?i)comp_06_pearl_([a-z0-9_]+)")
LEGENDARY_SPAWN_SERIAL_RE = re.compile(r"^([A-Za-z0-9_]+)\.(comp_05_legendary_.+)$", re.IGNORECASE)
PEARL_SPAWN_SERIAL_RE = re.compile(r"^([A-Za-z0-9_]+)\.(comp_06_pearl_.+)$", re.IGNORECASE)
_SCRIPT_STRUCT_CACHE: dict[str, list[Any]] = {}
_ALL_SCRIPT_STRUCTS_BY_NAME: dict[str, list[Any]] | None = None
_INLINE_ITEM_POOL_CANDIDATE_CACHE: dict[tuple[str, str], list[Any]] = {}
_ITEM_POOL_WINNER_CACHE: dict[tuple[str, str], int] = {}


def clear_item_pool_winner_cache() -> None:
    """Forget feet-spit winners so a shaped dump can rediscover the at-transform candidate."""
    _ITEM_POOL_WINNER_CACHE.clear()


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _invoke_callable_variants(
    bound: Any,
    label: str,
    positional_batches: Sequence[tuple[Any, ...]],
    keyword_batches: Sequence[dict[str, Any]],
) -> tuple[bool, str | None]:
    errors: list[str] = []
    for args in positional_batches:
        try:
            bound(*args)
            return True, None
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{label} positional{args[:3]!r}: {exc}")
    for kwargs in keyword_batches:
        try:
            bound(**kwargs)
            return True, None
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{label} kwargs{list(kwargs.keys())}: {exc}")
    return False, errors[0] if errors else None


def _pascalize_comp_tail(tail: str) -> str:
    if not tail:
        return tail
    parts = [part for part in tail.split("_") if part]
    if not parts:
        return tail
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _comp_inv_handle_variants(spawn_serial: str) -> list[str]:
    """Nexus rows use inv'ROOT.comp_*' — try dump + supplemental casing variants."""
    raw = spawn_serial.strip()
    match = LEGENDARY_SPAWN_SERIAL_RE.match(raw) or PEARL_SPAWN_SERIAL_RE.match(raw)
    if match is None:
        return []
    inv_root, comp_key = match.group(1), match.group(2)
    comp_variants = {comp_key, comp_key.lower()}
    tail_match = LEGENDARY_COMP_SUFFIX_RE.search(comp_key)
    if tail_match:
        tail = tail_match.group(1).lower()
        pascal = _pascalize_comp_tail(tail)
        # Dump / DLC comps often use Legendary_* (capital L) or Pascal tails.
        for mid in ("legendary", "Legendary"):
            comp_variants.add(f"comp_05_{mid}_{tail}")
            comp_variants.add(f"comp_05_{mid}_{pascal}")
        # Exact dump casings the naive pascalize misses.
        _EXACT_TAILS = {
            "discjockey": "DiscJockey",
            "lucian": "Lucian",
            "bubbles": "bubbles",
            "boomslang": "Boomslang",
        }
        exact = _EXACT_TAILS.get(tail.replace("_", ""))
        if exact:
            for mid in ("legendary", "Legendary"):
                comp_variants.add(f"comp_05_{mid}_{exact}")
    pearl_tail_match = PEARL_COMP_SUFFIX_RE.search(comp_key)
    if pearl_tail_match:
        tail = pearl_tail_match.group(1).lower()
        pascal = _pascalize_comp_tail(tail)
        for mid in ("pearl", "Pearl"):
            comp_variants.add(f"comp_06_{mid}_{tail}")
            comp_variants.add(f"comp_06_{mid}_{pascal}")
    inv_roots = _dedupe_preserve_order([inv_root, inv_root.upper(), inv_root.lower()])
    if inv_root.upper().startswith("CLASSMOD_"):
        inv_roots = _dedupe_preserve_order([inv_root.lower(), *inv_roots])
    handles: list[str] = []
    for inv_name in inv_roots:
        for comp in _dedupe_preserve_order(sorted(comp_variants, key=str.lower)):
            handles.append(f"inv'{inv_name}.{comp}'")
    return _dedupe_preserve_order(handles)


def _def_ptr_tokens_from_inv_handle(inv_handle: str) -> list[str]:
    """Token list for FGbxDefPtr / provider resolution (matches Item Spawner)."""
    raw = str(inv_handle or "").strip()
    if not raw:
        return []
    out: list[str] = []

    def add(token: str) -> None:
        t = str(token or "").strip()
        if t and t not in out:
            out.append(t)

    add(raw)
    match = re.match(r"inv'([^']+)'", raw, re.IGNORECASE)
    if not match:
        return out
    inner = match.group(1)
    add(inner)
    if "." in inner:
        root, _, tail = inner.partition(".")
        add(f"{root}:{tail}")
        add(tail)
    if "." not in inner:
        return out
    # Cap casing variants — full combinatorial expansion froze Spawn Selected.
    for variant_handle in _comp_inv_handle_variants(inner)[:4]:
        add(variant_handle)
        inner_match = re.match(r"inv'([^']+)'", variant_handle, re.IGNORECASE)
        if inner_match:
            add(inner_match.group(1))
    return out


def _build_fgbx_def_ptr_struct(token: str) -> Any | None:
    token = str(token or "").strip()
    if not token:
        return None
    token_l = token.lower()
    if ".comp_" in token_l or token_l.startswith("inv'"):
        hit = build_inventory_fgbx_def_ptr(token)
        if hit is not None:
            return hit
    struct_names = (
        "FGbxDefPtr",
        "GbxDefPtr",
        "/Script/GbxGame.FGbxDefPtr",
        "/Script/OakGame.FGbxDefPtr",
    )
    kwargs_sets: tuple[dict[str, Any], ...] = (
        {"_experimental_name": token},
        {"name": token},
        {"Name": token},
        {"DefName": token},
    )
    for struct_name in struct_names:
        for kwargs in kwargs_sets:
            try:
                return unrealsdk.make_struct(struct_name, **kwargs)
            except Exception:
                continue
    try:
        from unrealsdk.unreal import FGbxDefPtr  # pyright: ignore[reportMissingImports]

        for type_arg in ("GbxInventoryDef", "InventoryDef", "OakInventoryDef"):
            try:
                ptr = FGbxDefPtr(token, type=type_arg)
                inst = getattr(ptr, "_experimental_instance", None)
                return inst if inst is not None else ptr
            except Exception:
                continue
        ptr = FGbxDefPtr()
        for attr in ("_experimental_name", "name", "Name", "DefName"):
            try:
                setattr(ptr, attr, token)
                inst = getattr(ptr, "_experimental_instance", None)
                return inst if inst is not None else ptr
            except Exception:
                continue
    except Exception:
        pass
    return None


def _reflected_script_structs(struct_names: Sequence[str]) -> list[Any]:
    """Resolve loaded UScriptStructs when make_struct's short-name lookup fails."""
    global _ALL_SCRIPT_STRUCTS_BY_NAME
    wanted = {
        str(name or "").strip().rsplit(".", 1)[-1].rsplit("/", 1)[-1].lower()
        for name in struct_names
        if str(name or "").strip()
    }
    cache_key = "|".join(sorted(wanted))
    if cache_key in _SCRIPT_STRUCT_CACHE:
        return list(_SCRIPT_STRUCT_CACHE[cache_key])
    if _ALL_SCRIPT_STRUCTS_BY_NAME is None:
        by_name: dict[str, list[Any]] = {}
        seen: set[int] = set()
        try:
            objects = list(unrealsdk.find_all("ScriptStruct", False) or [])
        except Exception:
            objects = []
        for obj in objects:
            name = str(getattr(obj, "Name", "") or "").strip().lower()
            if not name:
                continue
            key = id(obj)
            try:
                key = int(getattr(obj, "_get_address", lambda: 0)() or 0) or key
            except Exception:
                pass
            if key in seen:
                continue
            seen.add(key)
            by_name.setdefault(name, []).append(obj)
        _ALL_SCRIPT_STRUCTS_BY_NAME = by_name
    out = [obj for name in wanted for obj in _ALL_SCRIPT_STRUCTS_BY_NAME.get(name, ())]
    _SCRIPT_STRUCT_CACHE[cache_key] = out
    return list(out)


def _make_reflected_struct(
    struct_names: Sequence[str],
    field_sets: Sequence[dict[str, Any]],
) -> Any | None:
    """Construct by name first, then by reflected template/WrappedStruct."""
    for struct_name in struct_names:
        for fields in field_sets:
            try:
                return unrealsdk.make_struct(struct_name, **fields)
            except Exception:
                continue

    try:
        from unrealsdk.unreal import WrappedStruct
    except Exception:
        WrappedStruct = None  # type: ignore[assignment,misc]

    for template in _reflected_script_structs(struct_names):
        for fields in field_sets:
            try:
                return unrealsdk.make_struct(template, **fields)
            except Exception:
                pass
            for factory in (
                (lambda: unrealsdk.make_struct(template)),
                ((lambda: WrappedStruct(template)) if WrappedStruct is not None else None),
            ):
                if factory is None:
                    continue
                try:
                    value = factory()
                    for field_name, field_value in fields.items():
                        setattr(value, field_name, field_value)
                    return value
                except Exception:
                    continue
    return None


def _item_spawner_tokens(inv_handle: str) -> list[str]:
    """Few FGbxDefPtr tokens — original Item Spawner, no combinatorial casing scan."""
    raw = str(inv_handle or "").strip()
    out: list[str] = []

    def add(token: str) -> None:
        text = str(token or "").strip()
        if text and text not in out:
            out.append(text)

    add(raw)
    match = re.match(r"inv'([^']+)'", raw, re.IGNORECASE)
    if not match:
        return out
    inner = match.group(1)
    add(inner)
    if "." in inner:
        root, _, tail = inner.partition(".")
        add(f"inv'{root.upper()}.{tail}'")
        add(f"{root.upper()}.{tail}")
        add(f"inv'{root.lower()}.{tail}'")
        add(f"{root.lower()}.{tail}")
    return out[:6]


def _build_item_spawner_selection(inv_handle: str) -> Any | None:
    """InventoryItemSelectionData the way bl4_item_spawner built it (no find_all)."""
    for token in _item_spawner_tokens(inv_handle):
        provider = None
        for struct_name in ("FGbxDefPtr", "GbxDefPtr", "/Script/GbxGame.FGbxDefPtr"):
            for kwargs in (
                {"_experimental_name": token},
                {"name": token},
                {"Name": token},
            ):
                try:
                    provider = unrealsdk.make_struct(struct_name, **kwargs)
                    break
                except Exception:
                    continue
            if provider is not None:
                break
        if provider is None:
            continue
        provider_struct = None
        for provider_name in (
            "InventoryItemDefProvider",
            "/Script/GbxGame.InventoryItemDefProvider",
        ):
            try:
                provider_struct = unrealsdk.make_struct(
                    provider_name, bInstance=False, Instance=provider
                )
                break
            except Exception:
                continue
        if provider_struct is None:
            continue
        criteria_struct: Any = IGNORE_STRUCT
        for criteria_name in (
            "InventorySelectionCriteria",
            "/Script/GbxGame.InventorySelectionCriteria",
        ):
            try:
                criteria_struct = unrealsdk.make_struct(criteria_name, Criteria=[])
                break
            except Exception:
                continue
        for selection_name in (
            "InventoryItemSelectionData",
            "/Script/GbxGame.InventoryItemSelectionData",
        ):
            for kwargs in (
                {"item": provider_struct, "Criteria": criteria_struct},
                {"Item": provider_struct, "Criteria": criteria_struct},
                {"item": provider_struct},
                {"Item": provider_struct},
            ):
                try:
                    return unrealsdk.make_struct(selection_name, **kwargs)
                except Exception:
                    continue
    return None


def _write_drop_transform(
    transform: Any, location: Any, rotation: Any, *, use_quat: bool
) -> None:
    try:
        setattr(transform, "Translation", location)
    except Exception:
        pass
    rot_value = rotation
    if use_quat:
        try:
            rot_value = _quat_from_rotation(rotation)
        except Exception:
            rot_value = rotation
    try:
        setattr(transform, "Rotation", rot_value)
    except Exception:
        pass


def _build_selection_data_from_provider(provider: Any) -> Any | None:
    provider_struct_names = (
        "InventoryItemDefProvider",
        "GbxGame.InventoryItemDefProvider",
        "/Script/GbxGame.InventoryItemDefProvider",
        "OakGame.InventoryItemDefProvider",
        "/Script/OakGame.InventoryItemDefProvider",
    )
    criteria_struct_names = (
        "InventorySelectionCriteria",
        "GbxGame.InventorySelectionCriteria",
        "/Script/GbxGame.InventorySelectionCriteria",
        "OakGame.InventorySelectionCriteria",
        "/Script/OakGame.InventorySelectionCriteria",
    )
    selection_struct_names = (
        "InventoryItemSelectionData",
        "GbxGame.InventoryItemSelectionData",
        "/Script/GbxGame.InventoryItemSelectionData",
        "OakGame.InventoryItemSelectionData",
        "/Script/OakGame.InventoryItemSelectionData",
    )
    # ``provider`` may already be an InventoryItemDefProvider from the
    # runtime builder; do not wrap it in a second provider union.
    direct = _make_reflected_struct(
        selection_struct_names,
        ({"Item": provider}, {"item": provider}),
    )
    if direct is not None:
        return direct
    provider_fields: list[dict[str, Any]] = [
        # Raw NCS itempool JSON is items[].item.item.handle: the provider's
        # field is Item, not only the inline-instance union used previously.
        {"Item": provider},
        {"item": provider},
        {"Definition": provider},
        {"definition": provider},
        {"Handle": provider},
        {"handle": provider},
        {"bInstance": False, "Instance": provider},
        {"binstance": False, "instance": provider},
        {"bInstance": True, "Instance": provider},
        {"binstance": True, "instance": provider},
    ]
    empty_criteria: list[dict[str, Any]] = [{"Criteria": []}, {"criteria": []}, {}]
    for provider_kwargs in provider_fields:
        provider_struct = _make_reflected_struct(provider_struct_names, (provider_kwargs,))
        if provider_struct is None:
            continue
        criteria_candidates: list[Any] = [IGNORE_STRUCT]
        for criteria_kwargs in empty_criteria:
            criteria_struct = _make_reflected_struct(criteria_struct_names, (criteria_kwargs,))
            if criteria_struct is not None:
                criteria_candidates.insert(0, criteria_struct)
        for criteria_struct in criteria_candidates:
            for item_key, criteria_key in (
                ("item", "criteria"),
                ("item", "Criteria"),
                ("Item", "criteria"),
                ("Item", "Criteria"),
            ):
                selection = _make_reflected_struct(
                    selection_struct_names,
                    (
                        {item_key: provider_struct, criteria_key: criteria_struct},
                        {item_key: provider_struct},
                    ),
                )
                if selection is not None:
                    return selection
    return None


def _build_selection_data_for_inv_handle(inv_handle: str, *, _retried: bool = False) -> Any | None:
    from .inventory_def_ptr import iter_inventory_item_def_providers, reset_inventory_def_scriptstruct_cache

    tokens = _def_ptr_tokens_from_inv_handle(inv_handle)
    for token in tokens:
        provider = _build_fgbx_def_ptr_struct(token)
        if provider is None:
            continue
        selection = _build_selection_data_from_provider(provider)
        if selection is not None:
            return selection
    for provider in iter_inventory_item_def_providers(tokens):
        selection = _build_selection_data_from_provider(provider)
        if selection is not None:
            return selection
    if not _retried:
        reset_inventory_def_scriptstruct_cache()
        return _build_selection_data_for_inv_handle(inv_handle, _retried=True)
    return None


def _extract_inv_handles(value: Any) -> list[str]:
    try:
        blob = json.dumps(value, ensure_ascii=False)
    except Exception:
        blob = str(value)
    return _dedupe_preserve_order(
        [f"inv'{match.group(1)}'" for match in INV_HANDLE_RE.finditer(blob)]
    )


def handles_from_pool_payload(pool_data: Mapping[str, Any]) -> list[str]:
    variants = pool_data.get("handle_variants")
    if isinstance(variants, list) and variants:
        inv_only = [str(v) for v in variants if str(v).strip().lower().startswith("inv'")]
        if inv_only:
            return _dedupe_preserve_order(inv_only)
    inv_handles = _extract_inv_handles(pool_data.get("items"))
    if inv_handles:
        return inv_handles
    spawn_serial = str(pool_data.get("spawn_serial") or "").strip()
    if spawn_serial:
        return _comp_inv_handle_variants(spawn_serial) or [f"inv'{spawn_serial}'"]
    return []


def _get_blueprint_library(class_name: str) -> Any | None:
    try:
        return unrealsdk.find_class(class_name).ClassDefaultObject
    except Exception:
        return None


def _field_chain(value: Any, *, limit: int = 96) -> list[Any]:
    """Return a reflected ChildProperties/Children chain without looping."""
    out: list[Any] = []
    current = getattr(value, "ChildProperties", None)
    if current is None:
        current = getattr(value, "Children", None)
    seen: set[int] = set()
    while current is not None and len(out) < limit:
        key = id(current)
        if key in seen:
            break
        seen.add(key)
        out.append(current)
        nxt = getattr(current, "Next", None)
        if nxt is current:
            break
        current = nxt
    return out


def _bound_ufunction(owner: Any, function_name: str) -> Any | None:
    """Find the UFunction backing a blueprint-library bound method."""
    for path in (
        f"/Script/GbxGame.ItemPoolFunctionLibrary:{function_name}",
        f"/Script/OakGame.ItemPoolFunctionLibrary:{function_name}",
    ):
        try:
            hit = unrealsdk.find_object("Function", path)
            if hit is not None:
                return hit
        except Exception:
            continue
    cls = getattr(owner, "Class", None)
    hops = 0
    while cls is not None and hops < 12:
        hops += 1
        child = getattr(cls, "Children", None)
        seen: set[int] = set()
        while child is not None and len(seen) < 4096:
            key = id(child)
            if key in seen:
                break
            seen.add(key)
            if str(getattr(child, "Name", "") or "") == function_name:
                return child
            nxt = getattr(child, "Next", None)
            if nxt is child:
                break
            child = nxt
        nxt_cls = getattr(cls, "SuperField", None)
        if nxt_cls is cls:
            break
        cls = nxt_cls
    return None


def _property_inner_name(prop: Any) -> str:
    for attr in ("Struct", "Inner", "PropertyClass", "MetaClass", "StructClass"):
        try:
            inner = getattr(prop, attr, None)
            name = str(getattr(inner, "Name", "") or "").strip()
            if name:
                return name
        except Exception:
            continue
    return ""


def _function_param_specs(ufunction: Any | None) -> list[tuple[str, Any, int]]:
    if ufunction is None:
        return []
    out: list[tuple[str, Any, int]] = []
    for prop in _field_chain(ufunction, limit=64):
        name = str(getattr(prop, "Name", "") or "").strip()
        try:
            flags = int(getattr(prop, "PropertyFlags", 0) or 0)
        except Exception:
            flags = 0
        if not name or name in ("ReturnValue", "Return", "__Result") or flags & 0x400:
            continue
        out.append((name, prop, flags))
    return out


def _item_pool_ptr_candidates(pool_name: str) -> list[Any]:
    raw = str(pool_name or "").strip()
    if raw.lower().startswith("itempool'") and raw.endswith("'"):
        raw = raw[9:-1]
    if not raw:
        return []
    labels = _dedupe_preserve_order([raw, f"itempool'{raw}'"])
    out: list[Any] = []
    try:
        from unrealsdk.unreal import FGbxDefPtr

        for label in labels:
            for type_arg in ("ItemPoolDef", "GbxItemPoolDef"):
                try:
                    ptr = FGbxDefPtr(label, type=type_arg)
                    out.append(getattr(ptr, "_experimental_instance", None) or ptr)
                except Exception:
                    continue
    except Exception:
        pass
    for label in labels:
        ptr = _make_reflected_struct(
            ("FGbxDefPtr", "GbxDefPtr", "/Script/GbxGame.FGbxDefPtr"),
            (
                {"_experimental_name": label},
                {"Name": label},
                {"name": label},
                {"DefName": label},
            ),
        )
        if ptr is not None:
            out.append(ptr)
    return out


def _inline_item_pool_candidates(inv_handle: str, pool_name: str = "") -> list[Any]:
    """Build the patch's ItemPoolDef -> ItemPoolProviderDef reflected chain."""
    cache_key = (str(inv_handle).strip().lower(), str(pool_name).strip().lower())
    cached = _INLINE_ITEM_POOL_CANDIDATE_CACHE.get(cache_key)
    if cached is not None:
        return list(cached)
    selection = _build_selection_data_for_inv_handle(inv_handle)
    direct_ptrs = _item_pool_ptr_candidates(pool_name)
    out: list[Any] = list(direct_ptrs)
    if selection is None:
        return out

    entry = _make_reflected_struct(
        (
            "ItemPoolEntry",
            "GbxGame.ItemPoolEntry",
            "/Script/GbxGame.ItemPoolEntry",
        ),
        ({"Item": selection}, {"item": selection}),
    )
    item_values = [entry] if entry is not None else [selection]
    pool_def = _make_reflected_struct(
        ("ItemPoolDef", "GbxGame.ItemPoolDef", "/Script/GbxGame.ItemPoolDef"),
        (
            {"Items": item_values},
            {"items": item_values},
            {"Items": [selection]},
            {"items": [selection]},
        ),
    )
    if pool_def is None:
        return out
    provider_names = (
        "ItemPoolProviderDef",
        "GbxGame.ItemPoolProviderDef",
        "/Script/GbxGame.ItemPoolProviderDef",
    )
    inline_provider_fields: list[dict[str, Any]] = [
        {"ItemPool": pool_def},
        {"itempool": pool_def},
        {"Item": pool_def},
        {"item": pool_def},
        {"Definition": pool_def},
        {"bInstance": True, "Instance": pool_def},
        {"binstance": True, "instance": pool_def},
    ]
    pointer_provider_fields: list[dict[str, Any]] = []
    for ptr in direct_ptrs:
        pointer_provider_fields.extend(
            ({"ItemPool": ptr}, {"Item": ptr}, {"Definition": ptr})
        )

    inline_providers: list[Any] = []
    pointer_providers: list[Any] = []
    for fields in inline_provider_fields:
        provider = _make_reflected_struct(provider_names, (fields,))
        if provider is not None:
            inline_providers.append(provider)
    for fields in pointer_provider_fields:
        provider = _make_reflected_struct(provider_names, (fields,))
        if provider is not None:
            pointer_providers.append(provider)
    # Try the engine-owned registered definition first (lowest native risk),
    # then the patch's exact embedded definition when that name rolls empty.
    result = [*pointer_providers, *out, *inline_providers, pool_def]
    _INLINE_ITEM_POOL_CANDIDATE_CACHE[cache_key] = list(result)
    return result


def _default_struct_for_property(prop: Any) -> Any | None:
    inner = None
    for attr in ("Struct", "Inner", "StructClass"):
        try:
            inner = getattr(prop, attr, None)
        except Exception:
            inner = None
        if inner is not None:
            break
    if inner is None:
        return None
    try:
        from unrealsdk.unreal import WrappedStruct

        return WrappedStruct(inner)
    except Exception:
        try:
            return unrealsdk.make_struct(inner)
        except Exception:
            return None


def _loot_spawn_pattern_from_labels(prop: Any, labels: Sequence[str]) -> Any | None:
    try:
        from unrealsdk.unreal import FGbxDefPtr

        for label in labels:
            for type_arg in ("SpawnPatternDef", "GbxSpawnPatternDef"):
                try:
                    ptr = FGbxDefPtr(label, type=type_arg)
                    return getattr(ptr, "_experimental_instance", None) or ptr
                except Exception:
                    continue
    except Exception:
        pass
    for label in labels:
        value = _make_reflected_struct(
            ("FGbxDefPtr", "GbxDefPtr", "/Script/GbxGame.FGbxDefPtr"),
            (
                {"_experimental_name": label},
                {"Name": label},
                {"name": label},
                {"DefName": label},
            ),
        )
        if value is not None:
            return value
    return _default_struct_for_property(prop)


def _exact_loot_spawn_pattern(prop: Any) -> Any | None:
    """No random spit — drop on the FTransform we pass (shape / drop-from-above)."""
    return _loot_spawn_pattern_from_labels(
        prop,
        (
            "spawn_pattern'spawnpattern_loot_at_location'",
            "spawnpattern_loot_at_location",
            "spawn_pattern'spawnpattern_atlocation'",
            "spawnpattern_atlocation",
            "spawn_pattern'spawnpattern_exact'",
            "spawnpattern_exact",
            "spawn_pattern'spawnpattern_none'",
            "spawnpattern_none",
            "spawn_pattern'spawnpattern_zero'",
            "spawnpattern_zero",
        ),
    )


def _default_loot_spawn_pattern(prop: Any) -> Any | None:
    """Build the concrete world-loot pattern used by the game's own actors."""
    return _loot_spawn_pattern_from_labels(
        prop,
        (
            "spawn_pattern'spawnpattern_default_loot'",
            "spawnpattern_default_loot",
            "spawn_pattern'spawnpattern_lootable_upandforward'",
            "spawnpattern_lootable_upandforward",
        ),
    )


def _pool_function_arg(
    name: str,
    prop: Any,
    *,
    world: Any,
    pc: Any,
    transform: Any,
    level: int,
    pool_value: Any,
) -> tuple[bool, Any]:
    low = name.lower()
    prop_type = type(prop).__name__.lower()
    pawn = getattr(pc, "Pawn", None)
    if "worldcontext" in low:
        return True, world
    if "itempool" in low and "pattern" not in low:
        return True, pool_value
    if "transform" in low:
        return True, transform
    if "location" in low:
        return True, getattr(transform, "Translation", None)
    if "rotation" in low:
        return True, getattr(transform, "Rotation", None)
    if "gamestage" in low or low in ("level", "itemlevel"):
        return True, level
    if "actor" in low or "owner" in low:
        return True, pawn or pc
    if "pattern" in low:
        # Never fall back to upandforward — it adds a second spit that lands
        # behind the pawn even when Translation is already in front.
        exact = _exact_loot_spawn_pattern(prop)
        if exact is not None:
            return True, exact
        return True, None
    if "count" in low or "quantity" in low or "number" in low:
        return True, 1
    if "bool" in prop_type:
        return True, False
    if "int" in prop_type or "byte" in prop_type or "enum" in prop_type:
        return True, 1
    if "float" in prop_type or "double" in prop_type:
        return True, 1.0
    if "array" in prop_type or "set" in prop_type:
        return True, []
    default_struct = _default_struct_for_property(prop)
    if default_struct is not None:
        return True, default_struct
    return False, None


def drop_item_pool_values(
    candidates: Sequence[Any],
    *,
    cache_key: tuple[str, str],
    count: int = 1,
    level: int = 60,
) -> tuple[int, str | None]:
    """World-drop live/reflected ItemPoolDef values via ItemPoolFunctionLibrary."""
    values = [value for value in candidates if value is not None]
    if not values:
        return 0, "no ItemPoolDef candidates"
    world = get_world()
    pc = resolve_spawn_pc()
    if world is None or pc is None:
        return 0, "Player or world is not available."
    spawn_transform = _get_spawn_transform(pc)
    player_pose = _get_player_pose(pc)
    if spawn_transform is None or player_pose is None:
        return 0, "Could not derive a spawn transform."
    player_location, player_rotation = player_pose
    spawned = 0
    last_err: str | None = None
    want = max(1, min(int(count), 32))
    for index in range(want):
        location, rotation = _spawn_pose(player_location, player_rotation, index)
        try:
            from .ncs_pool_spawn import apply_world_spawn_transform

            apply_world_spawn_transform(spawn_transform, location, rotation)
        except Exception:
            try:
                setattr(spawn_transform, "Translation", location)
            except Exception:
                pass
        ok, err = _drop_item_pool_candidates(
            values,
            world=world,
            pc=pc,
            transform=spawn_transform,
            level=level,
            cache_key=cache_key,
        )
        if ok:
            spawned += 1
            continue
        last_err = err
        break
    if spawned > 0:
        return spawned, None
    return 0, last_err or "item-pool runtime call rejected"


def _spawn_via_item_pool_library(
    *,
    inv_handle: str,
    pool_name: str,
    world: Any,
    pc: Any,
    transform: Any,
    level: int,
) -> tuple[bool, str | None]:
    """Use the runtime API which consumes ItemPoolDef, including inline defs."""
    candidates: list[Any] = []
    try:
        from .item_pool_list_spawn import live_itempool_values_for_inv

        candidates.extend(live_itempool_values_for_inv(inv_handle))
    except Exception:
        pass
    candidates.extend(_inline_item_pool_candidates(inv_handle, pool_name))
    if not candidates:
        return False, f"could not build ItemPoolDef for {inv_handle}"
    return _drop_item_pool_candidates(
        candidates,
        world=world,
        pc=pc,
        transform=transform,
        level=level,
        cache_key=(str(inv_handle).strip().lower(), str(pool_name).strip().lower()),
    )


def _drop_item_pool_candidates(
    candidates: Sequence[Any],
    *,
    world: Any,
    pc: Any,
    transform: Any,
    level: int,
    cache_key: tuple[str, str],
) -> tuple[bool, str | None]:
    library = _get_blueprint_library("ItemPoolFunctionLibrary")
    function_name = "SpawnItemsFromItemPoolUsingTransform_Drop"
    bound = getattr(library, function_name, None) if library is not None else None
    if not callable(bound):
        return False, "dedicated item-pool drop function unavailable"
    ufunction = _bound_ufunction(library, function_name)
    specs = _function_param_specs(ufunction)
    if not candidates:
        return False, "no ItemPoolDef candidates"

    pool_spec = next(
        ((name, prop) for name, prop, _flags in specs if "itempool" in name.lower()),
        None,
    )
    inner_name = _property_inner_name(pool_spec[1]).lower() if pool_spec else ""
    indexed_candidates = list(enumerate(candidates))
    candidate_key = cache_key
    winner_index = _ITEM_POOL_WINNER_CACHE.get(candidate_key)
    if winner_index is not None:
        indexed_candidates.sort(key=lambda pair: 0 if pair[0] == winner_index else 1)
    elif inner_name:
        indexed_candidates.sort(
            key=lambda value: (
                0
                if inner_name in type(value[1]).__name__.lower()
                or type(value[1]).__name__.lower() in inner_name
                else 1
            )
        )

    errors: list[str] = []
    player_loc = player_location_from_pc(pc)
    landing = False
    try:
        from ..loot_shapes import landing_armed

        landing = landing_armed()
    except Exception:
        landing = False
    # Shaped dump: find_all verify is the hitch. Trust the transform call.
    can_verify = (not landing) and verify_available() and player_loc is not None
    spawn_loc = getattr(transform, "Translation", None) if transform is not None else None

    def _verify_keys() -> set[str]:
        if not can_verify:
            return set()
        keys: set[str] = set()
        if player_loc is not None:
            keys |= nearby_loot_keys(player_loc)
        try:
            if spawn_loc is None or player_loc is None:
                return keys
            dx = float(spawn_loc.X) - float(player_loc.X)
            dy = float(spawn_loc.Y) - float(player_loc.Y)
            dz = float(spawn_loc.Z) - float(player_loc.Z)
            if (dx * dx + dy * dy + dz * dz) > 40000.0:
                keys |= nearby_loot_keys(spawn_loc)
        except Exception:
            pass
        return keys
    signature = ",".join(
        f"{name}:{type(prop).__name__}/{_property_inner_name(prop) or '-'}"
        for name, prop, _flags in specs
    )
    for original_index, pool_value in indexed_candidates:
        before = _verify_keys() if can_verify else set()
        kwargs: dict[str, Any] = {}
        unresolved: list[str] = []
        for name, prop, flags in specs:
            # A true output param is initialized by the function. Const refs also
            # carry OutParm, so only skip non-const output fields.
            if flags & 0x100 and not flags & 0x2:
                continue
            known, value = _pool_function_arg(
                name,
                prop,
                world=world,
                pc=pc,
                transform=transform,
                level=level,
                pool_value=pool_value,
            )
            if known:
                kwargs[name] = value
            else:
                unresolved.append(name)
        if unresolved:
            errors.append(f"unresolved params {unresolved}; signature={signature}")
            continue
        try:
            bound(**kwargs)
            if not can_verify or _verify_keys() - before:
                _ITEM_POOL_WINNER_CACHE[candidate_key] = original_index
                return True, None
            errors.append(
                f"{type(pool_value).__name__}: dedicated pool call returned no loot at feet; "
                f"signature={signature}"
            )
            # The function accepted this exact signature. Do not invoke the same
            # candidate again through a packed parameter block.
            continue
        except Exception as exc:  # noqa: BLE001
            errors.append(f"kwargs {type(pool_value).__name__}: {exc}")

        if ufunction is not None:
            try:
                from unrealsdk.unreal import WrappedStruct

                parms = WrappedStruct(ufunction)
                for key, value in kwargs.items():
                    setattr(parms, key, value)
                bound(parms)
                if not can_verify or _verify_keys() - before:
                    _ITEM_POOL_WINNER_CACHE[candidate_key] = original_index
                    return True, None
                errors.append(
                    f"packed {type(pool_value).__name__}: dedicated pool call returned no loot at feet; "
                    f"signature={signature}"
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"packed {type(pool_value).__name__}: {exc}")
    detail = errors[-1] if errors else "item-pool runtime call rejected"
    if signature and "signature=" not in detail:
        detail = f"{detail}; signature={signature}"
    return False, detail[:1000]


def _spawn_loot_from_exact_def(
    bound: Any,
    *,
    inv_handle: str,
    context_targets: Sequence[Any],
    spawn_transform: Any,
    level: int,
) -> tuple[bool, str | None]:
    """Use LootFunctionLibrary.SpawnLootFromDef_Drop for inline list entries.

    Patch NCS ItemPoolLists frequently embed an ``inv'ROOT.comp_*'`` directly
    instead of registering a standalone itempool name.  This reflected API can
    consume that exact definition without first constructing the selection-data
    wrapper required by SpawnLootFromData_Drop.
    """
    if not callable(bound):
        return False, "SpawnLootFromDef_Drop unavailable"
    tokens = _def_ptr_tokens_from_inv_handle(inv_handle)
    definitions: list[Any] = []
    seen: set[int] = set()

    def add(value: Any) -> None:
        if value is None:
            return
        key = id(value)
        if key in seen:
            return
        seen.add(key)
        definitions.append(value)

    for token in tokens:
        add(find_live_inventory_def(token))
        add(build_inventory_fgbx_def_ptr(token))
        for handle in build_inventory_fgame_data_handles(token):
            add(handle)
    for provider in iter_inventory_item_def_providers(tokens):
        add(provider)

    errors: list[str] = []
    for target in context_targets:
        for definition in definitions:
            ok, err = _invoke_callable_variants(
                bound,
                "SpawnLootFromDef_Drop",
                [
                    (target, spawn_transform, definition, level),
                    (target, definition, spawn_transform, level),
                    (target, definition, level),
                ],
                [
                    {
                        "WorldContextObject": target,
                        "Transform": spawn_transform,
                        "LootDef": definition,
                        "gamestage": level,
                    },
                    {
                        "WorldContextObject": target,
                        "Transform": spawn_transform,
                        "ItemDef": definition,
                        "GameStage": level,
                    },
                    {
                        "WorldContextObject": target,
                        "SpawnTransform": spawn_transform,
                        "Definition": definition,
                        "GameStage": level,
                    },
                ],
            )
            if ok:
                return True, None
            if err:
                errors.append(err)
    return False, errors[0] if errors else f"no exact definition for {inv_handle}"


def spawn_from_merge_payload(
    pool_data: Mapping[str, Any],
    *,
    count: int = 1,
    level: int = 60,
    drop_only: bool = False,
    pool_name: str = "",
    skip_verify: bool = False,
    at_location: Any = None,
    at_rotation: Any = None,
) -> tuple[int, str | None]:
    """Spawn using merge.json-shaped __synthetic pearl rows (Item Spawner parity)."""
    handles = handles_from_pool_payload(pool_data)
    if not handles:
        return 0, "inline itempool row has no inv handle"

    count = max(1, min(int(count), 32))
    level = max(1, min(MAX_ITEM_LEVEL, int(level)))

    world = get_world()
    pc = resolve_spawn_pc()
    if world is None or pc is None:
        return 0, "Player or world is not available."

    spawn_transform = _get_spawn_transform(pc)
    player_pose = _get_player_pose(pc)
    if spawn_transform is None or player_pose is None:
        return 0, "Could not derive a spawn transform."

    resolved_pool_name = str(pool_name or pool_data.get("__itempool_name") or "").strip()
    exact_inv = bool(
        pool_data.get("__shiny_inline")
        or pool_data.get("__exact_inv")
        or resolved_pool_name.lower().endswith("_shiny")
        or "_shiny_" in resolved_pool_name.lower()
    )
    named_comp_row = bool(not exact_inv and not resolved_pool_name)
    item_pool_lib = _get_blueprint_library("ItemPoolFunctionLibrary")
    item_pool_drop_fn = (
        getattr(item_pool_lib, "SpawnItemsFromItemPoolUsingTransform_Drop", None)
        if item_pool_lib is not None
        else None
    )
    loot_lib = _get_blueprint_library("LootFunctionLibrary")
    drop_loot_fn = getattr(loot_lib, "SpawnLootFromData_Drop", None) if loot_lib is not None else None
    drop_def_fn = getattr(loot_lib, "SpawnLootFromDef_Drop", None) if loot_lib is not None else None
    attach_loot_fn = getattr(loot_lib, "SpawnLootFromData_Attach", None) if loot_lib is not None else None
    if (
        not callable(item_pool_drop_fn)
        and not callable(drop_loot_fn)
        and not callable(drop_def_fn)
    ):
        return 0, "No physical item-pool or loot drop function is available"

    player_location, player_rotation = player_pose
    player_loc = player_location_from_pc(pc) or player_location
    before = set()
    if not skip_verify and verify_available() and player_loc is not None:
        before = nearby_loot_keys(player_loc)
    pawn = getattr(pc, "Pawn", None)
    context_targets_objs: list[Any] = []
    seen_ids: set[int] = set()
    for obj in (pawn, pc, world):
        if obj is None:
            continue
        oid = id(obj)
        if oid in seen_ids:
            continue
        seen_ids.add(oid)
        context_targets_objs.append(obj)

    errors: list[str] = []
    spawned_total = 0
    global _FORCE_EXACT_LOOT_PATTERN
    was_exact = _FORCE_EXACT_LOOT_PATTERN
    pile_exact = False
    try:
        from .pearl_spawn_ring import bulk_pile_mode

        pile_exact = bool(bulk_pile_mode())
    except Exception:
        pile_exact = False
    # Named unique comps: original Item Spawner uses SpawnLootFromData with the
    # engine default pattern. Forcing spawnpattern_exact (often unresolved) made
    # the library call return OK with no pickup. Keep exact pin for shiny/exact-inv.
    _FORCE_EXACT_LOOT_PATTERN = bool(exact_inv or pile_exact)

    for index in range(count):
        if at_location is not None:
            location = at_location
            rotation = at_rotation if at_rotation is not None else player_rotation
        else:
            location, rotation = _spawn_pose(player_location, player_rotation, index)
        try:
            # Original Item Spawner / Nexus Discovery inline drop: Rotator, not Quat.
            setattr(spawn_transform, "Translation", location)
            setattr(spawn_transform, "Rotation", rotation)
        except Exception:
            try:
                setattr(spawn_transform, "Translation", location)
            except Exception:
                pass

        spawned = False
        named_inline = (not exact_inv) and (not resolved_pool_name)
        for inv_handle in handles:
            if named_inline and callable(drop_def_fn):
                ok, err = _spawn_loot_from_exact_def(
                    drop_def_fn,
                    inv_handle=inv_handle,
                    context_targets=context_targets_objs,
                    spawn_transform=spawn_transform,
                    level=level,
                )
                if ok:
                    if skip_verify or not verify_available() or player_loc is None:
                        spawned = True
                        break
                    if nearby_loot_keys(player_loc) - before:
                        spawned = True
                        break
                    if named_inline:
                        spawned = True
                        break
                    errors.append(f"SpawnLootFromDef_Drop silent-empty {inv_handle}")
                elif err:
                    errors.append(err)

            if spawned:
                break

            if not exact_inv and resolved_pool_name:
                ok, err = _spawn_via_item_pool_library(
                    inv_handle=inv_handle,
                    pool_name=resolved_pool_name,
                    world=world,
                    pc=pc,
                    transform=spawn_transform,
                    level=level,
                )
                if ok:
                    spawned = True
                    break
                if err:
                    errors.append(err)

            selection = (
                _build_selection_data_for_inv_handle(inv_handle)
                or _build_item_spawner_selection(inv_handle)
                if named_inline
                else _build_selection_data_for_inv_handle(inv_handle)
            )
            if selection is None:
                if named_inline:
                    errors.append(f"no Item Spawner selection for {inv_handle}")
                    continue
                ok, err = _spawn_loot_from_exact_def(
                    drop_def_fn,
                    inv_handle=inv_handle,
                    context_targets=context_targets_objs,
                    spawn_transform=spawn_transform,
                    level=level,
                )
                if ok:
                    spawned = True
                    break
                if exact_inv and resolved_pool_name and callable(item_pool_drop_fn):
                    ok, pool_err = _spawn_via_item_pool_library(
                        inv_handle=inv_handle,
                        pool_name=resolved_pool_name,
                        world=world,
                        pc=pc,
                        transform=spawn_transform,
                        level=level,
                    )
                    if ok:
                        spawned = True
                        break
                    if pool_err:
                        errors.append(pool_err)
                errors.append(err or f"no selection struct for {inv_handle}")
                continue

            if not drop_only and not named_inline and callable(attach_loot_fn):
                for target in context_targets_objs:
                    ok, err = _invoke_callable_variants(
                        attach_loot_fn,
                        "SpawnLootFromData_Attach",
                        [
                            (target, selection, level),
                            (target, spawn_transform, selection, level),
                        ],
                        [
                            {
                                "WorldContextObject": target,
                                "LootData": selection,
                                "gamestage": level,
                            },
                            {
                                "WorldContextObject": target,
                                "Transform": spawn_transform,
                                "LootData": selection,
                                "gamestage": level,
                            },
                        ],
                    )
                    if ok:
                        spawned = True
                        break
                    if err:
                        errors.append(err)
                if spawned:
                    break

            if named_inline and callable(attach_loot_fn):
                for target in context_targets_objs:
                    ok, err = _invoke_callable_variants(
                        attach_loot_fn,
                        "SpawnLootFromData_Attach",
                        [
                            (target, selection, level),
                            (target, spawn_transform, selection, level),
                        ],
                        [
                            {
                                "WorldContextObject": target,
                                "LootData": selection,
                                "gamestage": level,
                            },
                            {
                                "WorldContextObject": target,
                                "Transform": spawn_transform,
                                "LootData": selection,
                                "gamestage": level,
                            },
                        ],
                    )
                    if ok:
                        if skip_verify or not verify_available() or player_loc is None:
                            spawned = True
                            break
                        if nearby_loot_keys(player_loc) - before:
                            spawned = True
                            break
                        if named_inline:
                            spawned = True
                            break
                        errors.append(
                            f"SpawnLootFromData_Attach silent-empty {inv_handle}"
                        )
                    elif err:
                        errors.append(err)
                if spawned:
                    break

            if not spawned and not named_inline:
                ok, err = _spawn_loot_from_exact_def(
                    drop_def_fn,
                    inv_handle=inv_handle,
                    context_targets=context_targets_objs,
                    spawn_transform=spawn_transform,
                    level=level,
                )
                if ok:
                    spawned = True
                elif err:
                    errors.append(err)

            if spawned:
                break

            rot_modes = (False,) if named_inline else (False, True)
            for use_quat in rot_modes:
                _write_drop_transform(
                    spawn_transform, location, rotation, use_quat=use_quat
                )
                for target in context_targets_objs:
                    ok, err = _invoke_callable_variants(
                        drop_loot_fn,
                        "SpawnLootFromData_Drop",
                        [
                            (target, spawn_transform, selection, level),
                            (target, selection, level),
                        ],
                        [
                            {
                                "WorldContextObject": target,
                                "Transform": spawn_transform,
                                "LootData": selection,
                                "gamestage": level,
                            },
                            {
                                "WorldContextObject": target,
                                "LootData": selection,
                                "gamestage": level,
                            },
                        ],
                    )
                    if ok:
                        if skip_verify or not verify_available() or player_loc is None:
                            spawned = True
                            break
                        if nearby_loot_keys(player_loc) - before:
                            spawned = True
                            break
                        if named_inline:
                            spawned = True
                            break
                        errors.append(
                            f"SpawnLootFromData_Drop silent-empty "
                            f"({'quat' if use_quat else 'rotator'}) {inv_handle}"
                        )
                    elif err:
                        errors.append(err)
                if spawned:
                    break
            if spawned:
                break

        if spawned:
            spawned_total += 1

    _FORCE_EXACT_LOOT_PATTERN = was_exact
    if spawned_total <= 0:
        detail = errors[-1] if errors else "inline merge spawn failed"
        tried = ", ".join(handles[:4])
        return 0, f"{detail} (tried {tried})"

    if spawned_total > 0 and (skip_verify or named_comp_row):
        return spawned_total, None

    if not skip_verify and verify_available() and player_loc is not None:
        gained = nearby_loot_keys(player_loc) - before
        if len(gained) < count:
            runtime_detail = errors[0] if errors else "compatibility call returned silently"
            return 0, (
                f"physical item-pool verification found {len(gained)}/{count} drops; "
                f"{runtime_detail}"
            )

    return spawned_total, None


def spawn_inv_handles_at_feet(
    inv_handles: Sequence[str],
    *,
    count: int = 1,
    level: int = 60,
    skip_verify: bool = False,
    at_location: Any = None,
    at_rotation: Any = None,
) -> tuple[int, str | None]:
    """Compat wrapper — prefer spawn_from_merge_payload when possible."""
    handles = [str(h).strip() for h in inv_handles if str(h).strip()]
    payload = {
        "__synthetic": True,
        "__exact_inv": True,
        "handle_variants": handles,
        "items": [{"item": {"item": {"handle": handles[0]}}}] if handles else [],
    }
    return spawn_from_merge_payload(
        payload,
        count=count,
        level=level,
        skip_verify=bool(skip_verify),
        at_location=at_location,
        at_rotation=at_rotation,
    )


def spawn_named_comp_inline_at_feet(
    inv_handles: Sequence[str],
    *,
    count: int = 1,
    level: int = 60,
    skip_verify: bool = False,
) -> tuple[int, str | None]:
    """Normal legendary comp spawn — dump inv'ROOT.comp_* only (Item Spawner parity).

    Not an itempool roll: same gun as the *_shiny NCS row with phosphene parts omitted.
    """
    handles = [str(h).strip() for h in inv_handles if str(h).strip()]
    if not handles:
        return 0, "no inv handle"
    payload = {
        "__synthetic": True,
        "__exact_inv": False,
        "handle_variants": handles,
        "items": [{"item": {"item": {"handle": handles[0]}}}],
    }
    return spawn_from_merge_payload(
        payload,
        count=count,
        level=level,
        skip_verify=skip_verify,
        pool_name="",
        drop_only=False,
    )
