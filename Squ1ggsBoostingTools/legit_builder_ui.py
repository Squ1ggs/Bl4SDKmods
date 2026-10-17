"""Compact in-game legit item builder tab for Squ1ggs Boosting Tools."""

from __future__ import annotations

import re
from typing import Any, Callable

import blimgui as _blimgui

from . import legit_builder_core as _core
from .squ1ggs_theme import ACCENT_DANGER, ACCENT_INFO, ACCENT_PRIMARY, ACCENT_SECONDARY, ACCENT_SUCCESS

_DISCLAIMER = (
    "Build gear from flattened Nexus inv rules. Outputs should still be verified at "
    "https://save-editor.be before use on saves you care about."
)

_state: dict[str, Any] = {
    "type_index": 0,
    "manufacturer_index": 0,
    "root_index": 0,
    "root_search": "",
    "parts_text": "",
    "level": 70,
    "unlock_rules": False,
    "status": "Pick type + manufacturer, add part keys (one per line), then Validate or Build.",
    "human": "",
    "base85": "",
}


def _pretty_label(value: str) -> str:
    return str(value or "").replace("_", " ").title()


def _type_options() -> list[str]:
    seen: set[str] = set()
    order = [
        "pistol", "smg", "shotgun", "assault_rifle", "sniper", "shield",
        "repair_kit", "enhancement", "gadget", "heavy", "class_mod",
    ]
    for row in _core.roots():
        t = str(row.get("item_type", "")).strip()
        if t:
            seen.add(t)
    return [t for t in order if t in seen] + sorted(seen.difference(order))


def _manufacturer_options(item_type: str) -> list[str]:
    out: set[str] = set()
    for row in _core.roots():
        if str(row.get("item_type", "")) != item_type:
            continue
        m = str(row.get("manufacturer", "")).strip()
        if m:
            out.add(m)
    return sorted(out)


def _root_options(item_type: str, manufacturer: str, search: str) -> list[dict[str, Any]]:
    q = search.strip().lower()
    rows = [
        r for r in _core.roots()
        if str(r.get("item_type", "")) == item_type and str(r.get("manufacturer", "")) == manufacturer
    ]
    if q:
        rows = [
            r for r in rows
            if q in str(r.get("key", "")).lower()
            or q in str(r.get("name", "")).lower()
            or q in str(r.get("build_label", "")).lower()
        ]
    return sorted(rows, key=lambda r: (int(r.get("serial") or 0), str(r.get("key") or "")))


def _selected_root() -> dict[str, Any] | None:
    types = _type_options()
    if not types:
        return None
    t_idx = max(0, min(int(_state["type_index"]), len(types) - 1))
    item_type = types[t_idx]
    mans = _manufacturer_options(item_type)
    if not mans:
        return None
    m_idx = max(0, min(int(_state["manufacturer_index"]), len(mans) - 1))
    roots = _root_options(item_type, mans[m_idx], str(_state["root_search"]))
    if not roots:
        return None
    r_idx = max(0, min(int(_state["root_index"]), len(roots) - 1))
    return roots[r_idx]


def _parse_parts_lines(text: str) -> list[str]:
    out: list[str] = []
    for line in str(text or "").splitlines():
        token = line.strip()
        if token and not token.startswith("#"):
            out.append(token)
    return out


def _passive_base_key(part_key: str) -> str:
    key = str(part_key or "").strip().lower()
    return re.sub(r"_tier_\d+$", "", key)


def _max_passive_lines_for_root(root_key: str) -> tuple[list[str], int]:
    """One max-tier passive_points line per passive on a class mod root."""
    if not root_key:
        return [], 0
    best: dict[str, tuple[int, str]] = {}
    scanned = 0
    try:
        parts = _core.search_parts(root_key, "passive_", table="passive_points", limit=2000)
    except Exception:
        return [], 0
    for part in parts:
        key = str(part.get("key") or part.get("internal") or "").strip()
        if not key.lower().startswith("passive_"):
            continue
        m = re.search(r"_tier_(\d+)$", key.lower())
        if not m:
            continue
        scanned += 1
        try:
            tier = int(m.group(1))
        except Exception:
            tier = 0
        base = _passive_base_key(key)
        table = str(part.get("table") or "passive_points").strip()
        line = f"{table}:{key}" if table else key
        if not line:
            continue
        old = best.get(base)
        if old is None or tier > old[0]:
            best[base] = (tier, line)
    return [line for _tier, line in sorted(best.values(), key=lambda item: item[1].lower())], scanned


def draw_legit_builder_tab(
    *,
    button: Callable[..., None],
    input_text: Callable[..., str],
    input_text_multiline: Callable[..., str],
    input_int_clamped: Callable[..., int],
    checkbox: Callable[..., bool],
    combo: Callable[..., int],
    muted_wrapped: Callable[[str], None],
    begin_card: Callable[..., bool],
    end_card: Callable[[], None],
    card_accent: str,
    tab_height: float,
    deliver_serials: Callable[[list[str], str], None],
    draw_target_selector: Callable[[], None],
) -> None:
    global _state
    imgui = _blimgui.imgui
    opened = begin_card("Legit Forge", card_accent, tab_height)
    if not opened:
        return
    try:
        muted_wrapped(_DISCLAIMER)
        _state["unlock_rules"] = checkbox(
            "Unlock rules (modded gear — skip legit constraints)###sqbt_legit_unlock",
            bool(_state["unlock_rules"]),
        )
        if _state["unlock_rules"]:
            muted_wrapped(
                "Unlock mode bypasses dependency, exclusion, slot-count, and duplicate-part rules. "
                "Verify output at save-editor.be before using on saves you care about."
            )

        types = _type_options()
        if not types:
            imgui.text_wrapped("Legit rules did not load (missing legit_rules_flat.json).")
            return

        old_type = int(_state["type_index"])
        _state["type_index"] = combo(
            "Item Type###sqbt_legit_type",
            max(0, min(int(_state["type_index"]), len(types) - 1)),
            [_pretty_label(t) for t in types],
        )
        if int(_state["type_index"]) != old_type:
            _state["manufacturer_index"] = 0
            _state["root_index"] = 0

        item_type = types[max(0, min(int(_state["type_index"]), len(types) - 1))]
        mans = _manufacturer_options(item_type) or ["(none)"]
        old_man = int(_state["manufacturer_index"])
        _state["manufacturer_index"] = combo(
            "Manufacturer###sqbt_legit_manufacturer",
            max(0, min(int(_state["manufacturer_index"]), len(mans) - 1)),
            [_pretty_label(m) for m in mans],
        )
        if int(_state["manufacturer_index"]) != old_man:
            _state["root_index"] = 0

        _state["root_search"] = input_text("Root filter###sqbt_legit_root_filter", str(_state["root_search"]), 256)
        manufacturer = mans[max(0, min(int(_state["manufacturer_index"]), len(mans) - 1))]
        roots = _root_options(item_type, manufacturer, str(_state["root_search"]))
        labels = [
            f"#{r.get('serial')}  {r.get('build_label') or r.get('name') or r.get('key')}"
            for r in roots
        ] or ["No matching root"]
        _state["root_index"] = combo(
            "Root###sqbt_legit_root",
            max(0, min(int(_state["root_index"]), len(labels) - 1)),
            labels,
        )

        root = _selected_root()
        if root:
            imgui.text_wrapped(
                f"Root key: {root.get('key')} | parts in tree: {len(root.get('parts') or [])}"
            )

        _state["parts_text"] = input_text_multiline(
            "Part keys (one per line)###sqbt_legit_parts",
            str(_state["parts_text"]),
            65536,
            width=820,
            height=110,
        )
        _state["level"] = input_int_clamped("Level###sqbt_legit_level", int(_state["level"]), 1, 70)
        draw_target_selector()

        root_key = str(root.get("key") if root else "")
        parts = _parse_parts_lines(str(_state["parts_text"]))

        def _add_all_max_passives() -> None:
            if not root_key:
                _state["status"] = "Select a class mod root first."
                return
            if str(root.get("item_type") or "").lower() != "class_mod":
                _state["status"] = "Max passives only works on class mod roots."
                return
            if not _state["unlock_rules"]:
                _state["status"] = "Turn on Unlock rules before adding every max passive."
                return
            max_lines, scanned = _max_passive_lines_for_root(root_key)
            if not max_lines:
                _state["status"] = f"No passive_points parts found for {root_key} (scanned {scanned})."
                return
            kept = [line for line in parts if not str(line).strip().lower().startswith("passive_points:")]
            merged = kept + max_lines
            _state["parts_text"] = "\n".join(merged)
            _state["status"] = f"Added {len(max_lines)} max-tier passive point part(s) for {root.get('build_label') or root_key}."

        def _validate_only() -> None:
            if not root_key:
                _state["status"] = "Select a root first."
                return
            if _state["unlock_rules"]:
                _state["status"] = f"Unlock mode: {len(parts)} part line(s) accepted without validation."
                return
            result = _core.validate(root_key, parts)
            if result.get("ok"):
                _state["status"] = "Validation OK."
            else:
                errs = result.get("errors") or []
                _state["status"] = "Validation failed: " + "; ".join(str(e) for e in errs[:4])

        def _build_serials() -> None:
            if not root_key:
                _state["status"] = "Select a root first."
                return
            try:
                if _state["unlock_rules"]:
                    human = _core.build_human(root_key, parts, level=int(_state["level"]))
                    b85 = _core.build_base85(root_key, parts, level=int(_state["level"]), validate_first=False)
                else:
                    human = _core.build_human(root_key, parts, level=int(_state["level"]))
                    b85 = _core.build_base85(root_key, parts, level=int(_state["level"]), validate_first=True)
                _state["human"] = human
                _state["base85"] = b85
                _state["status"] = "Built serial."
            except Exception as exc:  # noqa: BLE001
                _state["human"] = ""
                _state["base85"] = ""
                _state["status"] = f"Build failed: {exc}"

        def _give_built() -> None:
            serial = str(_state["base85"] or "").strip()
            if not serial.startswith("@U"):
                _state["status"] = "Build a Base85 serial first."
                return
            deliver_serials([serial], "Legit Forge")

        button("Validate", _validate_only, ACCENT_INFO, 110, 0)
        imgui.same_line()
        button("Build @U", _build_serials, ACCENT_SECONDARY, 120, 0)
        imgui.same_line()
        button("Give Built", _give_built, ACCENT_PRIMARY, 120, 0)
        imgui.same_line()
        button(
            "Clear",
            lambda: (_state.update({"parts_text": "", "human": "", "base85": "", "status": "Cleared."})),
            ACCENT_DANGER,
            80,
            0,
        )
        if _state["unlock_rules"] and root and str(root.get("item_type") or "").lower() == "class_mod":
            imgui.spacing()
            button("Add All Max Passives", _add_all_max_passives, ACCENT_PRIMARY, 220, 0)

        imgui.text_wrapped(str(_state["status"]))
        if _state["human"]:
            imgui.text_wrapped(f"Human: {_state['human'][:500]}")
        if _state["base85"]:
            imgui.text_wrapped(f"Base85: {_state['base85'][:120]}")
    finally:
        end_card()
