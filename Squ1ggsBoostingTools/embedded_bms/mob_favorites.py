"""Mob Spawner favorites — Char_* actors and encounter IO lines (settings/bl4_mob_spawner_hookedwidget.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "settings" / "squ1ggs_bms_favorites.json"
LEGACY_SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "settings" / "squ1ggs_bms.json"

_favorite_mobs: set[str] = set()  # lowercase code keys
_favorite_mob_labels: dict[str, str] = {}
_favorite_mob_codes: dict[str, str] = {}  # lowercase -> canonical Char_* code
_favorite_encounters: set[str] = set()
_favorite_encounter_labels: dict[str, str] = {}


def _load_settings() -> dict[str, Any]:
    source = SETTINGS_PATH if SETTINGS_PATH.is_file() else LEGACY_SETTINGS_PATH
    if not source.is_file():
        return {}
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_settings(extra: dict[str, Any]) -> None:
    data = _load_settings()
    data.update(extra)
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    except OSError:
        pass


def _init_from_settings() -> None:
    global _favorite_mobs, _favorite_mob_labels, _favorite_mob_codes, _favorite_encounters, _favorite_encounter_labels
    data = _load_settings()
    _favorite_mobs = set(str(x) for x in data.get("favorite_mobs", []) if str(x).strip())
    raw_mob_labels = data.get("favorite_mob_labels", {}) or {}
    _favorite_mob_labels = {
        str(k).lower(): str(v)
        for k, v in dict(raw_mob_labels).items()
        if str(k).strip() and str(v).strip()
    }
    raw_mob_codes = data.get("favorite_mob_codes", {}) or {}
    _favorite_mob_codes = {
        str(k).lower(): str(v)
        for k, v in dict(raw_mob_codes).items()
        if str(k).strip() and str(v).strip()
    }
    for key in list(_favorite_mobs):
        if key not in _favorite_mob_codes:
            _favorite_mob_codes[key] = key
    _favorite_encounters = set(
        str(x) for x in data.get("favorite_encounters", []) if str(x).strip()
    )
    raw_enc_labels = data.get("favorite_encounter_labels", {}) or {}
    _favorite_encounter_labels = {
        str(k): str(v) for k, v in dict(raw_enc_labels).items() if str(k).strip() and str(v).strip()
    }


_init_from_settings()


def _save_mob_favorites() -> None:
    for key in list(_favorite_mob_labels):
        if key not in _favorite_mobs:
            _favorite_mob_labels.pop(key, None)
    for key in list(_favorite_mob_codes):
        if key not in _favorite_mobs:
            _favorite_mob_codes.pop(key, None)
    _save_settings(
        {
            "favorite_mobs": sorted(_favorite_mobs),
            "favorite_mob_labels": dict(sorted(_favorite_mob_labels.items())),
            "favorite_mob_codes": dict(sorted(_favorite_mob_codes.items())),
        }
    )


def _save_encounter_favorites() -> None:
    for key in list(_favorite_encounter_labels):
        if key not in _favorite_encounters:
            _favorite_encounter_labels.pop(key, None)
    _save_settings(
        {
            "favorite_encounters": sorted(_favorite_encounters),
            "favorite_encounter_labels": dict(sorted(_favorite_encounter_labels.items())),
        }
    )


def mob_code_key(code: str) -> str:
    return str(code or "").strip().lower()


def encounter_key(cmd: str) -> str:
    return str(cmd or "").strip()


def is_favorite_mob(code: str) -> bool:
    return mob_code_key(code) in _favorite_mobs


def is_favorite_encounter(cmd: str) -> bool:
    return encounter_key(cmd) in _favorite_encounters


def toggle_favorite_mob(code: str, label: str) -> None:
    key = mob_code_key(code)
    if not key:
        return
    canonical = str(code or "").strip()
    if key in _favorite_mobs:
        _favorite_mobs.discard(key)
    else:
        _favorite_mobs.add(key)
        _favorite_mob_labels[key] = str(label or canonical).strip() or canonical
        _favorite_mob_codes[key] = canonical
    _save_mob_favorites()


def toggle_favorite_encounter(cmd: str, label: str) -> None:
    key = encounter_key(cmd)
    if not key:
        return
    if key in _favorite_encounters:
        _favorite_encounters.discard(key)
    else:
        _favorite_encounters.add(key)
        _favorite_encounter_labels[key] = str(label or cmd).strip()[:120] or key[:80]
    _save_encounter_favorites()


def remove_favorite_mob(code: str) -> None:
    key = mob_code_key(code)
    if key and key in _favorite_mobs:
        _favorite_mobs.discard(key)
        _save_mob_favorites()


def remove_favorite_encounter(cmd: str) -> None:
    key = encounter_key(cmd)
    if key and key in _favorite_encounters:
        _favorite_encounters.discard(key)
        _save_encounter_favorites()


def clear_all_favorites() -> None:
    _favorite_mobs.clear()
    _favorite_encounters.clear()
    _save_mob_favorites()
    _save_encounter_favorites()


def sort_mob_entries_first(entries: list[Any]) -> list[Any]:
    return sorted(
        entries,
        key=lambda row: (
            0 if mob_code_key(getattr(row, "code", "")) in _favorite_mobs else 1,
            str(getattr(row, "display_name", "")).lower(),
        ),
    )


def favorite_mob_rows() -> list[tuple[str, str]]:
    """Return (code, label) for pinned Char_* mobs."""
    out: list[tuple[str, str]] = []
    for key in sorted(_favorite_mobs):
        code = _favorite_mob_codes.get(key, key)
        label = _favorite_mob_labels.get(key, code)
        out.append((code, label))
    return out


def favorite_encounter_rows() -> list[tuple[str, str, str]]:
    """Return (label, cmd, key) for pinned encounter lines."""
    out: list[tuple[str, str, str]] = []
    for key in sorted(_favorite_encounters):
        label = _favorite_encounter_labels.get(key, key[:48])
        out.append((label, key, key))
    return out


def draw_favorites_section(
    imgui: Any,
    ui: Any,
    *,
    spawn_mob: Callable[..., tuple[bool, str]],
    run_encounter: Callable[[str], tuple[bool, str]],
    id_prefix: str = "mob_fav",
) -> None:
    """Pinned favorites bar at the top of the Mob Spawner tab."""
    mob_rows = favorite_mob_rows()
    enc_rows = favorite_encounter_rows()
    total = len(mob_rows) + len(enc_rows)

    imgui.text_wrapped(
        "★ **Favorites** — use **+** on Char_* rows, encounter IO, or io_* world props below. "
        "Saved in settings/bl4_mob_spawner_hookedwidget.json.",
    )
    imgui.text_disabled(f"Pinned: {total} ({len(mob_rows)} mobs · {len(enc_rows)} encounters)")

    if not total:
        imgui.text_colored((0.75, 0.82, 0.95, 1.0), "No favorites yet — use Add favorite on a mob or encounter.")
        imgui.spacing()
        return

    if mob_rows:
        imgui.text("Mob favorites")
        for code, label in mob_rows:
            btn = f"{label}##{id_prefix}_mob_{code[:28]}"
            if imgui.small_button(btn):
                n = int(getattr(ui, "squ1ggs_deploy_count", 1) or 1)
                ok, msg = spawn_mob(code, count=n)
                ui.status_text = msg
                ui.error_text = "" if ok else msg
            if imgui.is_item_hovered():
                imgui.set_tooltip(code)
            imgui.same_line()
            if imgui.small_button(f"-##{id_prefix}_rm_mob_{code[:24]}"):
                remove_favorite_mob(code)
            if imgui.is_item_hovered():
                imgui.set_tooltip(f"Remove {label} from favorites")
            imgui.same_line()
        imgui.new_line()

    if enc_rows:
        imgui.text("Encounter favorites")
        for label, cmd, key in enc_rows:
            btn = f"{label}##{id_prefix}_enc_{key[:20]}"
            if imgui.small_button(btn):
                ok, msg = run_encounter(cmd)
                ui.status_text = msg
                ui.error_text = "" if ok else msg
            if imgui.is_item_hovered():
                imgui.set_tooltip(cmd[:160])
            imgui.same_line()
            if imgui.small_button(f"-##{id_prefix}_rm_enc_{key[:16]}"):
                remove_favorite_encounter(cmd)
            if imgui.is_item_hovered():
                imgui.set_tooltip(f"Remove {label} from favorites")
            imgui.same_line()
        imgui.new_line()

    if imgui.small_button(f"Clear all favorites##{id_prefix}_clear"):
        clear_all_favorites()

    imgui.spacing()

