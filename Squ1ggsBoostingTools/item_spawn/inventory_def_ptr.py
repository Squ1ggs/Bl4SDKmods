"""FGbxDefPtr / FGameDataHandle builders for inv'ROOT.comp_*' inline loot (SDK 0.3+)."""

from __future__ import annotations

import re
from typing import Any, Iterable

import unrealsdk

_INV_HANDLE_RE = re.compile(r"(?i)inv'([^']+)'")

_INVENTORY_DEF_TYPES: tuple[str, ...] = (
    "GbxInventoryDef",
    "/Script/GbxGame.GbxInventoryDef",
    "GbxInvDef",
    "/Script/GbxGame.GbxInvDef",
    "InventoryDef",
    "OakInventoryDef",
    "/Script/OakGame.OakInventoryDef",
    "GbxInventoryItemDef",
    "/Script/GbxGame.GbxInventoryItemDef",
    "GbxInventoryCompDef",
    "/Script/GbxGame.GbxInventoryCompDef",
    "InvCompDef",
    "/Script/GbxGame.InvCompDef",
    "InventoryBalanceData",
    "OakInventoryBalanceData",
    "GbxInventoryBalanceData",
    "WeaponBalanceData",
    "InventoryItemData",
    "OakInventoryItemData",
)

_INV_DEF_SCRIPTSTRUCT_CACHE: Any | None = None


def _label_from_token(token: str) -> str:
    raw = str(token or "").strip()
    if not raw:
        return ""
    match = _INV_HANDLE_RE.match(raw)
    if match:
        return match.group(1).strip()
    if raw.lower().startswith("inv'") and raw.endswith("'"):
        return raw[4:-1].strip()
    return raw


def find_inventory_def_scriptstruct() -> Any | None:
    global _INV_DEF_SCRIPTSTRUCT_CACHE
    if _INV_DEF_SCRIPTSTRUCT_CACHE is not None:
        return _INV_DEF_SCRIPTSTRUCT_CACHE
    for path in _INVENTORY_DEF_TYPES:
        try:
            ref = unrealsdk.find_object("ScriptStruct", path)
        except Exception:
            ref = None
        if ref is not None:
            _INV_DEF_SCRIPTSTRUCT_CACHE = ref
            return ref
    return None


_LIVE_INV_DEF_CLASSES: tuple[str, ...] = (
    "GbxInventoryDef",
    "/Script/GbxGame.GbxInventoryDef",
    "OakInventoryDef",
    "/Script/OakGame.OakInventoryDef",
    "GbxInventoryItemDef",
    "/Script/GbxGame.GbxInventoryItemDef",
    "GbxInventoryCompDef",
    "/Script/GbxGame.GbxInventoryCompDef",
    "InvCompDef",
    "/Script/GbxGame.InvCompDef",
    "InventoryDef",
    "InventoryBalanceData",
    "OakInventoryBalanceData",
    "WeaponBalanceData",
    "Object",
)


def find_live_inventory_def(token: str) -> Any | None:
    """Loaded inv'ROOT.comp_*' UObject, if NCS already has the definition."""
    label = _label_from_token(token)
    if not label:
        return None
    names = [label]
    if "." in label:
        root, _, tail = label.partition(".")
        names.extend(
            (
                f"{root.lower()}.{tail}",
                f"{root.upper()}.{tail}",
                f"{root}.{tail[:1].upper() + tail[1:]}" if tail else label,
                f"{root}:{tail}",
                f"{root.lower()}:{tail}",
                f"{root.upper()}:{tail}",
                tail,
            )
        )
    seen: set[str] = set()
    for name in names:
        low = name.strip()
        if not low or low.lower() in seen:
            continue
        seen.add(low.lower())
        for cls in _LIVE_INV_DEF_CLASSES:
            try:
                obj = unrealsdk.find_object(cls, low)
            except Exception:
                obj = None
            if obj is not None:
                return obj
    scanned = _scan_live_inventory_defs(label)
    if scanned is not None:
        return scanned
    return None


_INV_SCAN_CACHE: dict[str, Any] = {}
_INV_SCAN_DONE = False


def _scan_live_inventory_defs(label: str) -> Any | None:
    """Match dump inv tokens against loaded inventory defs (Abyss / Temper)."""
    global _INV_SCAN_DONE
    key = str(label or "").strip().lower()
    if not key:
        return None
    if ".comp_" not in key and "comp_" not in key:
        _INV_SCAN_CACHE[key] = None
        return None
    if key in _INV_SCAN_CACHE:
        return _INV_SCAN_CACHE[key]
    if not _INV_SCAN_DONE:
        tail_index: dict[str, Any] = {}
        classes = (
            "GbxInventoryCompDef",
            "InvCompDef",
            "GbxInventoryDef",
            "GbxInventoryItemDef",
        )
        for cls in classes:
            try:
                objs = list(unrealsdk.find_all(cls, False) or [])
            except Exception:
                continue
            for obj in objs:
                if obj is None:
                    continue
                try:
                    name = str(getattr(obj, "Name", "") or "").strip()
                except Exception:
                    name = ""
                if not name:
                    continue
                tail_index.setdefault(name.lower(), obj)
                try:
                    blob = str(obj).strip().lower()
                except Exception:
                    blob = name.lower()
                if blob and blob not in tail_index:
                    tail_index[blob] = obj
        _INV_SCAN_CACHE.update(tail_index)
        _INV_SCAN_DONE = True
    hit = _INV_SCAN_CACHE.get(key)
    if hit is not None:
        return hit
    tail = key.split(".")[-1]
    hit = _INV_SCAN_CACHE.get(tail)
    if hit is not None:
        _INV_SCAN_CACHE[key] = hit
        return hit
    for stored, obj in list(_INV_SCAN_CACHE.items()):
        if tail and tail in stored and (key in stored or stored.endswith(tail)):
            _INV_SCAN_CACHE[key] = obj
            return obj
    _INV_SCAN_CACHE[key] = None
    return None


def reset_inventory_def_scriptstruct_cache() -> None:
    """Clear cached ScriptStruct ref (stale pointer → \"no selection struct\" on pearl inline)."""
    global _INV_DEF_SCRIPTSTRUCT_CACHE
    _INV_DEF_SCRIPTSTRUCT_CACHE = None


def _fgbx_def_ptr_shell(label: str, type_arg: Any) -> Any | None:
    try:
        from unrealsdk.unreal import FGbxDefPtr  # pyright: ignore[reportMissingImports]
    except Exception:
        return None
    try:
        ptr = FGbxDefPtr(label, type=type_arg)
    except Exception:
        return None
    inst = getattr(ptr, "_experimental_instance", None)
    return inst if inst is not None else ptr


def build_inventory_fgbx_def_ptr(token: str) -> Any | None:
    label = _label_from_token(token)
    if not label:
        return None

    ref = find_inventory_def_scriptstruct()
    type_args: list[Any] = []
    if ref is not None:
        type_args.append(ref)
    for candidate in _INVENTORY_DEF_TYPES:
        if candidate not in type_args:
            type_args.append(candidate)

    for type_arg in type_args:
        shell = _fgbx_def_ptr_shell(label, type_arg)
        if shell is not None:
            return shell

    struct_names = (
        "FGbxDefPtr",
        "GbxDefPtr",
        "/Script/GbxGame.FGbxDefPtr",
        "/Script/OakGame.FGbxDefPtr",
    )
    kwargs_sets: tuple[dict[str, Any], ...] = (
        {"_experimental_name": label},
        {"name": label},
        {"Name": label},
        {"DefName": label},
    )
    for struct_name in struct_names:
        for kwargs in kwargs_sets:
            try:
                return unrealsdk.make_struct(struct_name, **kwargs)
            except Exception:
                continue

    try:
        from unrealsdk.unreal import FGbxDefPtr  # pyright: ignore[reportMissingImports]

        ptr = FGbxDefPtr()
        for attr in ("_experimental_name", "name", "Name", "DefName"):
            try:
                setattr(ptr, attr, label)
                inst = getattr(ptr, "_experimental_instance", None)
                return inst if inst is not None else ptr
            except Exception:
                continue
    except Exception:
        pass
    return None


def build_inventory_fgame_data_handles(token: str) -> list[Any]:
    label = _label_from_token(token)
    if not label:
        return []
    try:
        from unrealsdk.unreal import FGameDataHandle, FGbxDefPtr  # pyright: ignore[reportMissingImports]
    except Exception:
        return []

    out: list[Any] = []
    seen: set[int] = set()
    ref = find_inventory_def_scriptstruct()
    type_args: list[Any] = []
    if ref is not None:
        type_args.append(ref)
    for candidate in _INVENTORY_DEF_TYPES:
        if candidate not in type_args:
            type_args.append(candidate)

    th_ref: int | None = None
    if ref is not None:
        for attr in ("TypeHandle", "type_handle", "_type_handle"):
            val = getattr(ref, attr, None)
            if isinstance(val, int) and val > 0:
                th_ref = val
                break

    def _add(handle: Any) -> None:
        oid = id(handle)
        if oid in seen:
            return
        seen.add(oid)
        out.append(handle)

    if isinstance(th_ref, int) and th_ref > 0:
        try:
            _add(FGameDataHandle(int(th_ref), label))
        except Exception:
            pass

    for type_arg in type_args:
        try:
            ptr = FGbxDefPtr(label, type=type_arg)
        except Exception:
            continue
        th = getattr(ptr, "_type_handle", None)
        if not isinstance(th, int) or th <= 0:
            if ref is not None:
                for attr in ("TypeHandle", "type_handle", "_type_handle"):
                    th = getattr(ref, attr, None)
                    if isinstance(th, int) and th > 0:
                        break
        if not isinstance(th, int) or th <= 0:
            continue
        try:
            _add(FGameDataHandle(int(th), label))
        except Exception:
            continue
    return out


def iter_inventory_item_def_providers(tokens: Iterable[str]) -> Iterable[Any]:
    """Yield ``InventoryItemDefProvider`` struct candidates for inline comp spawns."""
    provider_names = (
        "InventoryItemDefProvider",
        "/Script/GbxGame.InventoryItemDefProvider",
    )
    seen_keys: set[str] = set()

    for raw_token in tokens:
        token = str(raw_token or "").strip()
        if not token:
            continue
        ptr = build_inventory_fgbx_def_ptr(token)
        handles = build_inventory_fgame_data_handles(token)
        field_sets: list[dict[str, Any]] = []
        if ptr is not None:
            field_sets.extend(
                [
                    {"bInstance": True, "Instance": ptr},
                    {"binstance": True, "instance": ptr},
                    {"bInstance": False, "Instance": ptr},
                    {"binstance": False, "instance": ptr},
                ]
            )
        for handle in handles:
            field_sets.extend(
                [
                    {"Handle": handle, "bInstance": False, "Instance": None},
                    {"handle": handle, "binstance": False, "instance": None},
                    {"Handle": handle, "bInstance": False},
                    {"handle": handle, "binstance": False},
                ]
            )
            if ptr is not None:
                field_sets.extend(
                    [
                        {"Handle": handle, "bInstance": True, "Instance": ptr},
                        {"handle": handle, "binstance": True, "instance": ptr},
                    ]
                )

        for fields in field_sets:
            key = repr(sorted((str(k), repr(v)) for k, v in fields.items()))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            for provider_name in provider_names:
                try:
                    yield unrealsdk.make_struct(provider_name, **fields)
                except Exception:
                    continue
