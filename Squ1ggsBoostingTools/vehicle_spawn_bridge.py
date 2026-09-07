"""Vehicle spawn catalog + summon helpers for the desktop bridge."""
from __future__ import annotations

from typing import Any


def _engine() -> Any:
    from . import tuning_embed as tuning

    return tuning.get_engine("bvm")


def reload_catalog(*, deep: bool = False) -> int:
    eng = _engine()
    return int(eng._reload_vehicle_spawn_catalog(log=False, deep_offline=deep))


def list_entries(*, search: str = "", category: str = "All", limit: int = 500) -> list[dict[str, Any]]:
    eng = _engine()
    if not getattr(eng, "_vehicle_spawn_catalog", None):
        reload_catalog(deep=False)
    query = str(search or "").strip().casefold()
    cat = str(category or "All").strip().casefold()
    rows: list[dict[str, Any]] = []
    for entry in eng._vehicle_spawn_entries():
        label = str(eng._vehicle_spawn_display_label(entry))
        row_cat = str(entry.get("category") or "unknown")
        if cat not in ("", "all") and row_cat.casefold() != cat:
            continue
        hay = " ".join(
            [
                label,
                str(entry.get("id") or ""),
                row_cat,
                " ".join(str(a) for a in (entry.get("aliases") or ())[:6]),
            ]
        ).casefold()
        if query and not all(token in hay for token in query.split()):
            continue
        flags: list[str] = []
        if entry.get("unreleased"):
            flags.append("unreleased")
        if entry.get("verified"):
            flags.append("verified")
        rows.append(
            {
                "id": str(entry.get("id") or ""),
                "label": label,
                "title": label,
                "vehicle": label,
                "category": row_cat,
                "flags": ", ".join(flags),
            }
        )
    return rows[: max(1, min(int(limit or 500), 2000))]


def categories() -> list[str]:
    seen = sorted({str(row.get("category") or "") for row in list_entries(limit=5000) if row.get("category")})
    return ["All", *(seen or ["unknown"])]


def resolve_entry(*, vehicle: str = "", vehicle_id: str = "") -> dict[str, Any] | None:
    eng = _engine()
    label = str(vehicle or "").strip()
    if label:
        hit = eng._vehicle_spawn_entry_by_label(label)
        if hit is not None:
            return hit
    token = str(vehicle_id or vehicle or "").strip()
    if token:
        return eng._resolve_vehicle_spawn_token(token)
    return None


def spawn_entry(entry: dict[str, Any]) -> bool:
    eng = _engine()
    return bool(eng._spawn_vehicle_entry(entry))
