"""OakUIScript_LootFeed Appear* — on-screen loot popup (Squ1ggs Boosting Tools)."""

from __future__ import annotations

import inspect
from typing import Any

APPEAR_NAMES: tuple[str, ...] = (
    "AppearAmmo",
    "AppearCash",
    "AppearCommon",
    "AppearUncommon",
    "AppearRare",
    "AppearEpic",
    "AppearLegendary",
    "AppearEridium",
    "AppearDLC",
    "AppearMail",
)

_KIND_ALIASES: dict[str, str] = {
    "appearammo": "AppearAmmo",
    "ammo": "AppearAmmo",
    "appearcash": "AppearCash",
    "cash": "AppearCash",
    "appearcommon": "AppearCommon",
    "common": "AppearCommon",
    "appearuncommon": "AppearUncommon",
    "uncommon": "AppearUncommon",
    "appearrare": "AppearRare",
    "rare": "AppearRare",
    "appearepic": "AppearEpic",
    "epic": "AppearEpic",
    "appearlegendary": "AppearLegendary",
    "legendary": "AppearLegendary",
    "appeareridium": "AppearEridium",
    "eridium": "AppearEridium",
    "appeardlc": "AppearDLC",
    "dlc": "AppearDLC",
    "appearmail": "AppearMail",
    "mail": "AppearMail",
}

# Nexus uiwidget0.json — OwningWidgetDef works via FGbxDefPtr without opening inventory.
_KNOWN_WIDGET_DEF_NAMES: tuple[str, ...] = (
    "def_lootfeed",
    "GbxUIDef'def_lootfeed'",
    "uiwidget'def_lootfeed'",
)

_LOOT_FEED_UIDEF_CACHE: Any | None = None
_LOOT_FEED_AUTO_SCAN_DONE = False
_POS_X = 0.5
_POS_Y = 0.82
_WIDGET_PATH_OVERRIDE = ""


def set_widget_path_override(path: str) -> None:
    global _WIDGET_PATH_OVERRIDE, _LOOT_FEED_AUTO_SCAN_DONE, _LOOT_FEED_UIDEF_CACHE
    _WIDGET_PATH_OVERRIDE = str(path or "").strip()
    _LOOT_FEED_AUTO_SCAN_DONE = False
    _LOOT_FEED_UIDEF_CACHE = None


def _normalize_appear_name(kind: str) -> str:
    raw = str(kind or "").strip()
    if not raw:
        return ""
    alias = _KIND_ALIASES.get(raw.replace(" ", "").lower())
    if alias:
        return alias
    if raw.startswith("Appear"):
        return raw
    return "Appear" + raw[:1].upper() + raw[1:]


def _safe_full_name(obj: Any) -> str:
    for getter in ("get_full_name", "GetFullName", "GetPathName"):
        try:
            fn = getattr(obj, getter, None)
            if callable(fn):
                hit = str(fn() or "").strip()
                if hit:
                    return hit
        except Exception:  # noqa: BLE001
            continue
    return str(obj)


def _find_loot_feed_cdo() -> Any | None:
    import unrealsdk

    for cls_name in ("OakUIScript_LootFeed", "Object"):
        try:
            obj = unrealsdk.find_object(cls_name, "/Script/OakGame.Default__OakUIScript_LootFeed")
        except Exception:  # noqa: BLE001
            obj = None
        if obj is not None:
            return obj
    return None


def _get_world_context() -> Any | None:
    try:
        from mods_base import get_pc

        pc = get_pc()
        if pc is not None:
            return pc
    except Exception:  # noqa: BLE001
        pass
    try:
        import unrealsdk

        for cls_name in ("OakPlayerController", "PlayerController"):
            for pc in list(unrealsdk.find_all(cls_name, False) or []):
                try:
                    nm = str(getattr(getattr(pc, "Class", None), "Name", "") or "")
                except Exception:  # noqa: BLE001
                    nm = ""
                if "Default__" in nm:
                    continue
                return pc
    except Exception:  # noqa: BLE001
        pass
    return None


def _make_position_struct(x: float, y: float) -> Any:
    import unrealsdk

    make_struct = getattr(unrealsdk, "make_struct", None)
    if not callable(make_struct):
        return (float(x), float(y))
    for path, kw in (
        ("/Script/CoreUObject.Vector2f", {"X": x, "Y": y}),
        ("/Script/CoreUObject.Vector2f", {"x": x, "y": y}),
        ("Vector2f", {"X": x, "Y": y}),
        ("/Script/CoreUObject.Vector2D", {"X": x, "Y": y}),
    ):
        try:
            return make_struct(path, **kw)
        except Exception:  # noqa: BLE001
            try:
                return make_struct(path, kw)
            except Exception:  # noqa: BLE001
                continue
    return (float(x), float(y))


def _resolve_widget_path_override(text: str) -> Any | None:
    t = (text or "").strip()
    if not t:
        return None
    if (t[0] == t[-1]) and t[0] in {'"', "'"}:
        t = t[1:-1].strip()
    import unrealsdk

    for cn in ("Object", "GbxUIDef", "OakUIDef", "Field"):
        try:
            o = unrealsdk.find_object(cn, t)
        except Exception:  # noqa: BLE001
            o = None
        if o is not None:
            return o
    return None


def _static_widget_def_variants() -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    try:
        from unrealsdk.unreal import FGbxDefPtr
    except Exception:  # noqa: BLE001
        return out
    for name in _KNOWN_WIDGET_DEF_NAMES:
        try:
            ptr = FGbxDefPtr()
            ptr._experimental_name = name  # type: ignore[attr-defined]
            out.append((f"static:{name}", ptr))
        except Exception:  # noqa: BLE001
            continue
    return out


def _coerce_owning_widget_def(uidef_obj: Any | None) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    if uidef_obj is not None:
        try:
            from unrealsdk.unreal import FGbxDefPtr

            for attr in ("Def", "DefRef", "Ref", "UIDef", "WidgetDef", "Asset"):
                try:
                    ptr = FGbxDefPtr()
                    setattr(ptr, attr, uidef_obj)
                    out.append((f"FGbxDefPtr.{attr}", ptr))
                    break
                except Exception:  # noqa: BLE001
                    continue
            try:
                ptr = FGbxDefPtr()
                ptr._experimental_name = _safe_full_name(uidef_obj)  # type: ignore[attr-defined]
                out.append(("FGbxDefPtr._experimental_name", ptr))
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            pass
        out.append(("raw_UObject", uidef_obj))
    out.extend(_static_widget_def_variants())
    return out


def _find_loot_feed_uidef_object() -> Any | None:
    global _LOOT_FEED_UIDEF_CACHE, _LOOT_FEED_AUTO_SCAN_DONE
    if _WIDGET_PATH_OVERRIDE:
        hit = _resolve_widget_path_override(_WIDGET_PATH_OVERRIDE)
        if hit is not None:
            return hit
    if _LOOT_FEED_AUTO_SCAN_DONE:
        return _LOOT_FEED_UIDEF_CACHE

    import unrealsdk

    for path in _KNOWN_WIDGET_DEF_NAMES:
        for cn in ("GbxUIDef", "OakUIDef", "Object"):
            try:
                hit = unrealsdk.find_object(cn, path)
            except Exception:  # noqa: BLE001
                hit = None
            if hit is not None:
                _LOOT_FEED_AUTO_SCAN_DONE = True
                _LOOT_FEED_UIDEF_CACHE = hit
                return hit

    best = None
    best_score = -1
    for cls_name in ("GbxUIDef", "OakUIDef"):
        try:
            batch = list(unrealsdk.find_all(cls_name, False) or [])[:1200]
        except Exception:  # noqa: BLE001
            continue
        for obj in batch:
            fn = _safe_full_name(obj).lower()
            score = 0
            if "lootfeed" in fn.replace("_", "") or "loot_feed" in fn:
                score += 10
            if "def_lootfeed" in fn:
                score += 8
            if "loot" in fn and "feed" in fn:
                score += 5
            if "ui_loot" in fn.replace(" ", ""):
                score += 4
            if score > best_score:
                best_score = score
                best = obj

    _LOOT_FEED_AUTO_SCAN_DONE = True
    _LOOT_FEED_UIDEF_CACHE = best if best is not None and best_score > 0 else None
    return _LOOT_FEED_UIDEF_CACHE


def invoke_loot_feed_appear(
    bound: Any,
    *,
    pos_x: float | None = None,
    pos_y: float | None = None,
) -> Any:
    """Call Appear*(WorldContext, OwningWidgetDef, Position)."""
    pc = _get_world_context()
    if pc is None:
        raise RuntimeError("Load into the world first (no player controller).")

    wx = float(pos_x if pos_x is not None else _POS_X)
    wy = float(pos_y if pos_y is not None else _POS_Y)
    pos = _make_position_struct(wx, wy)

    uidef = _find_loot_feed_uidef_object()
    wdg_variants = _coerce_owning_widget_def(uidef)
    if not wdg_variants and uidef is not None:
        wdg_variants = [("uidef", uidef)]
    # Some builds accept None / empty OwningWidgetDef and still play the toast.
    wdg_variants = list(wdg_variants) + [("none", None)]

    if uidef is None and _WIDGET_PATH_OVERRIDE:
        raise RuntimeError("Load into the world first, then retry.")

    sig: inspect.Signature | None = None
    try:
        sig = inspect.signature(bound)
    except Exception:  # noqa: BLE001
        sig = None
    param_names = list(sig.parameters.keys()) if sig else []

    last_err: Exception | None = None
    for _label, warg in wdg_variants:
        attempts: list[tuple[tuple[Any, ...] | None, dict[str, Any] | None]] = [
            ((pc, warg, pos), None),
            ((pc, warg, (wx, wy)), None),
            ((pc, pos), None),
            ((pc,), None),
            (
                None,
                {
                    "WorldContextObject": pc,
                    "OwningWidgetDef": warg,
                    "Position": pos,
                },
            ),
            (
                None,
                {
                    "WorldContextObject": pc,
                    "OwningWidgetDef": warg,
                    "Position": (wx, wy),
                },
            ),
            (
                None,
                {
                    "WorldContext": pc,
                    "OwningWidgetDef": warg,
                    "Position": pos,
                },
            ),
            (
                None,
                {
                    "worldcontextobject": pc,
                    "owningwidgetdef": warg,
                    "position": pos,
                },
            ),
        ]
        if param_names and len(param_names) >= 3:
            attempts.append(
                (
                    None,
                    {
                        param_names[0]: pc,
                        param_names[1]: warg,
                        param_names[2]: pos,
                    },
                )
            )
        elif param_names and len(param_names) == 2:
            attempts.append(
                (
                    None,
                    {
                        param_names[0]: pc,
                        param_names[1]: pos,
                    },
                )
            )
        for args, kwargs in attempts:
            try:
                if kwargs is not None:
                    return bound(**kwargs)
                if args is not None:
                    return bound(*args)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue

    msg = str(last_err) if last_err else "all argument patterns failed"
    raise RuntimeError(f"Could not play loot feed ({msg})") from last_err


def appear(kind: str, *, widget_path: str | None = None) -> str:
    if widget_path is not None:
        set_widget_path_override(widget_path)
    name = _normalize_appear_name(kind)
    if not name:
        return "Pick a loot feed action."
    cdo = _find_loot_feed_cdo()
    if cdo is None:
        return "Loot feed library not loaded (OakUIScript_LootFeed missing)."
    fn = getattr(cdo, name, None)
    if not callable(fn):
        return f"{name} is not available on this build."
    try:
        invoke_loot_feed_appear(fn)
    except Exception as exc:  # noqa: BLE001
        return f"{name}: {exc}"
    return f"{name} played."


def clear_loot_feed_cache() -> None:
    global _LOOT_FEED_UIDEF_CACHE, _LOOT_FEED_AUTO_SCAN_DONE
    _LOOT_FEED_UIDEF_CACHE = None
    _LOOT_FEED_AUTO_SCAN_DONE = False
