"""User-configurable in-game keybinds driven from the desktop EXE Keybinds tab."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from mods_base import keybind
from unrealsdk import logging

_PREFIX = "[Squ1ggs's Boosting Tools | Keybinds]"
_SLOT_COUNT = 12
_SCHEMA = 1

# Safe boost / utility actions the EXE may bind (no bulk scrapes / lobby-wide mail).
BINDABLE_ACTIONS: tuple[dict[str, Any], ...] = (
    {"id": "max_all", "label": "MAX ALL", "action": "max_all", "payload": {}},
    {"id": "max_cash", "label": "Max cash", "action": "max_cash", "payload": {}},
    {"id": "max_eridium", "label": "Max eridium", "action": "max_eridium", "payload": {}},
    {
        "id": "player_level_70",
        "label": "Player level 70",
        "action": "give_experience",
        "payload": {"track": "player", "level": 70},
    },
    {
        "id": "spec_level_701",
        "label": "Spec level 701",
        "action": "give_experience",
        "payload": {"track": "specialization", "level": 701},
    },
    {"id": "max_sdu", "label": "Max SDU", "action": "max_sdu", "payload": {}},
    {"id": "black_market_spawn", "label": "Spawn black market machine", "action": "black_market", "payload": {"action": "spawn"}},
    {"id": "black_market_cooldown", "label": "Reset black market cooldown", "action": "black_market", "payload": {"action": "cooldown"}},
    {"id": "black_market_visited", "label": "Mark black market visited", "action": "black_market", "payload": {"action": "visited"}},
    {"id": "god_mode", "label": "God mode (toggle)", "action": "devperk_activate", "payload": {"perk_index": 6}},
    {
        "id": "unlock_cosmetics",
        "label": "Unlock all cosmetics",
        "action": "devperk_activate",
        "payload": {"perk_index": 4},
    },
    {"id": "infinite_ammo", "label": "Infinite ammo (toggle)", "action": "devperk_activate", "payload": {"perk_index": 5}},
    {"id": "freecam_toggle", "label": "Toggle freecam", "action": "freecam_toggle", "payload": {}},
    {
        "id": "teleport_me_to_target",
        "label": "Me → target",
        "action": "teleport_party",
        "payload": {"mode": "me_to_selected"},
    },
    {
        "id": "teleport_target_to_me",
        "label": "Target → me",
        "action": "teleport_party",
        "payload": {"mode": "selected_to_me"},
    },
    {"id": "golden_chest_open", "label": "Open golden chest(s)", "action": "golden_chest", "payload": {"action": "open"}},
    {"id": "golden_chest_close", "label": "Close golden chest(s)", "action": "golden_chest", "payload": {"action": "close"}},
    {
        "id": "world_text_spawn",
        "label": "Spawn world text (electisafe)",
        "action": "barrel_logo",
        "payload": {
            "row1": "MODS",
            "row2": "ARE",
            "row3": "FREE",
            "actor": "electisafe",
            "distance": 1400,
            "height": 750,
            "spacing": 70,
            "scale": 0.45,
            "max_props": 256,
        },
    },
    {
        "id": "world_text_spawn_goldenchest",
        "label": "Spawn world text (goldenchest)",
        "action": "barrel_logo",
        "payload": {
            "row1": "MODS",
            "row2": "ARE",
            "row3": "FREE",
            "actor": "goldenchest",
            "distance": 1400,
            "height": 750,
            "spacing": 70,
            "scale": 0.45,
            "max_props": 256,
        },
    },
    {"id": "world_text_clear", "label": "Clear world text", "action": "barrel_logo_clear", "payload": {}},
    {"id": "rewards_open_everyone", "label": "Open pending rewards (everyone)", "action": "rewards_open_everyone", "payload": {}},
    {"id": "kill_all_enemies", "label": "Kill all enemies", "action": "kill_all_enemies", "payload": {}},
    {"id": "no_target_toggle", "label": "Toggle no-target", "action": "mobility_toggle_no_target", "payload": {}},
    {"id": "force_fly_toggle", "label": "Toggle force fly", "action": "mobility_force_fly", "payload": {}},
    {"id": "infinite_jump_toggle", "label": "Toggle infinite jump", "action": "mobility_infinite_jump", "payload": {}},
)

SUGGESTED_KEYS: tuple[str, ...] = (
    "F5",
    "F6",
    "F7",
    "F8",
    "F9",
    "F10",
    "F11",
    "F12",
    "NumPadOne",
    "NumPadTwo",
    "NumPadThree",
    "NumPadFour",
    "NumPadFive",
    "NumPadSix",
    "NumPadSeven",
    "NumPadEight",
    "NumPadNine",
    "NumPadZero",
    "Home",
    "End",
    "Insert",
    "Delete",
    "PageUp",
    "PageDown",
    "Comma",
    "Period",
    "Slash",
    "Semicolon",
    "Quote",
    "LeftBracket",
    "RightBracket",
    "Backslash",
)

_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

_slot_config: list[dict[str, Any]] = [{"action_id": "", "key": ""} for _ in range(_SLOT_COUNT)]
_slot_keybinds: list[Any] = []


def _log(msg: str) -> None:
    try:
        logging.info(f"{_PREFIX} {msg}")
    except Exception:
        pass


def _config_paths() -> list[Path]:
    """Durable locations first — never rely on files inside the mod package (updates wipe that folder)."""
    paths: list[Path] = []
    try:
        paths.append(
            Path.home()
            / "Documents"
            / "My Games"
            / "Borderlands 4"
            / "Saved"
            / "Squ1ggsBoostingTools_user_keybinds.json"
        )
    except Exception:
        pass
    try:
        cwd = Path.cwd()
        # Next to other oak2 mod settings (survives Install / update mod folder).
        paths.append(cwd / "sdk_mods" / "settings" / "Squ1ggsBoostingTools_user_keybinds.json")
        paths.append(cwd / "sdk_mods" / "Squ1ggsBoostingTools_user_keybinds.json")
    except Exception:
        pass
    try:
        # Legacy: inside the mod package — read/migrate only, never preferred for writes.
        paths.append(Path(__file__).resolve().parent / "Squ1ggsBoostingTools_user_keybinds.json")
    except Exception:
        pass
    return paths


def _config_path_for_write() -> Path:
    durable = _config_paths()
    # Skip the last legacy mod-package path when choosing where to write.
    candidates = durable[:-1] if len(durable) > 1 else durable
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            continue
    return candidates[0] if candidates else durable[-1]


_ACTION_ID_ALIASES = {
    "no_target_on": "no_target_toggle",
    "no_target_off": "no_target_toggle",
    "force_fly_on": "force_fly_toggle",
    "force_fly_off": "force_fly_toggle",
    "infinite_jump_on": "infinite_jump_toggle",
    "infinite_jump_off": "infinite_jump_toggle",
    "freecam_disable": "freecam_toggle",
}


def _action_by_id(action_id: str) -> dict[str, Any] | None:
    want = str(action_id or "").strip()
    want = _ACTION_ID_ALIASES.get(want, want)
    for row in BINDABLE_ACTIONS:
        if row["id"] == want:
            return row
    return None


def _normalize_key(raw: str) -> str:
    text = str(raw or "").strip()
    if not text or text.lower() in {"none", "null", "unbound", "off"}:
        return ""
    # Allow common aliases from the EXE capture UI.
    aliases = {
        " ": "SpaceBar",
        "space": "SpaceBar",
        "esc": "Escape",
        "escape": "Escape",
        "ctrl": "LeftControl",
        "control": "LeftControl",
        "alt": "LeftAlt",
        "shift": "LeftShift",
        "np0": "NumPadZero",
        "np1": "NumPadOne",
        "np2": "NumPadTwo",
        "np3": "NumPadThree",
        "np4": "NumPadFour",
        "np5": "NumPadFive",
        "np6": "NumPadSix",
        "np7": "NumPadSeven",
        "np8": "NumPadEight",
        "np9": "NumPadNine",
    }
    low = text.lower()
    if low in aliases:
        return aliases[low]
    if len(text) == 1 and text.isalpha():
        return text.upper()
    if _KEY_RE.fullmatch(text):
        return text
    return ""


def _fire_slot(slot: int) -> None:
    try:
        cfg = _slot_config[int(slot)]
    except Exception:
        return
    action_id = str(cfg.get("action_id") or "").strip()
    if not action_id:
        return
    row = _action_by_id(action_id)
    if row is None:
        _log(f"Slot {slot + 1}: unknown action_id {action_id!r}")
        return
    try:
        from .backend_actions import run_action  # noqa: PLC0415

        result = run_action(str(row["action"]), dict(row.get("payload") or {}))
        msg = result.get("message") if isinstance(result, dict) else result
        _log(f"Slot {slot + 1} ({row['label']}): {msg}")
    except Exception as exc:  # noqa: BLE001
        _log(f"Slot {slot + 1} failed: {type(exc).__name__}: {exc}")


def _make_callback(slot: int) -> Callable[[], None]:
    def _cb() -> None:
        _fire_slot(slot)

    return _cb


def _apply_slot_to_keybind(slot: int) -> None:
    if slot < 0 or slot >= len(_slot_keybinds):
        return
    kb = _slot_keybinds[slot]
    cfg = _slot_config[slot]
    key = _normalize_key(str(cfg.get("key") or ""))
    action_id = str(cfg.get("action_id") or "").strip()
    row = _action_by_id(action_id)
    label = row["label"] if row else f"Custom {slot + 1}"
    try:
        kb.key = key
    except Exception:
        try:
            setattr(kb, "key", key)
        except Exception:
            pass
    for attr, value in (
        ("display_name", f"SQBT: {label}" if action_id else f"SQBT Custom {slot + 1}"),
        ("description", f"Squ1ggs Boosting Tools custom bind slot {slot + 1}: {label}"),
    ):
        try:
            setattr(kb, attr, value)
        except Exception:
            pass


def _save_config() -> Path:
    path = _config_path_for_write()
    payload = {
        "schema": _SCHEMA,
        "slots": [
            {"action_id": str(cfg.get("action_id") or ""), "key": _normalize_key(str(cfg.get("key") or ""))}
            for cfg in _slot_config
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_config() -> None:
    loaded_from: Path | None = None
    for path in _config_paths():
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        slots = data.get("slots") if isinstance(data, dict) else None
        if not isinstance(slots, list):
            continue
        for i in range(_SLOT_COUNT):
            row = slots[i] if i < len(slots) and isinstance(slots[i], dict) else {}
            _slot_config[i] = {
                "action_id": str(row.get("action_id") or "").strip(),
                "key": _normalize_key(str(row.get("key") or "")),
            }
        for i in range(_SLOT_COUNT):
            _apply_slot_to_keybind(i)
        loaded_from = path
        _log(f"Loaded user keybinds from {path}")
        break
    if loaded_from is None:
        return
    # If we loaded a legacy in-package file, migrate it to a durable path now.
    try:
        write_path = _config_path_for_write()
        if write_path.resolve() != loaded_from.resolve():
            _save_config()
            _log(f"Migrated user keybinds to {write_path}")
    except Exception:
        pass


def build_keybinds() -> list[Any]:
    """Create the mods_base keybind objects (call once at import / build_mod time)."""
    global _slot_keybinds
    if _slot_keybinds:
        return list(_slot_keybinds)
    built: list[Any] = []
    for i in range(_SLOT_COUNT):
        kb = keybind(
            f"SQBT Custom Bind {i + 1}",
            "",
            callback=_make_callback(i),
            display_name=f"SQBT Custom {i + 1}",
            description=f"Configurable Squ1ggs Boosting Tools bind slot {i + 1} (set from the EXE Keybinds tab).",
        )
        built.append(kb)
    _slot_keybinds = built
    load_config()
    return list(_slot_keybinds)


def status_payload() -> dict[str, Any]:
    slots_out: list[dict[str, Any]] = []
    for i, cfg in enumerate(_slot_config):
        action_id = str(cfg.get("action_id") or "")
        row = _action_by_id(action_id)
        live_key = ""
        try:
            live_key = str(getattr(_slot_keybinds[i], "key", None) or "")
        except Exception:
            live_key = ""
        key = _normalize_key(str(cfg.get("key") or live_key or ""))
        slots_out.append(
            {
                "slot": i,
                "label": f"Custom {i + 1}",
                "action_id": action_id,
                "action_label": row["label"] if row else "",
                "key": key,
                "bound": bool(key and action_id),
            }
        )
    return {
        "ok": True,
        "message": f"{sum(1 for s in slots_out if s['bound'])} custom keybind(s) set.",
        "slots": slots_out,
        "actions": [
            {"id": row["id"], "label": row["label"], "action": row["action"]} for row in BINDABLE_ACTIONS
        ],
        "keys": list(SUGGESTED_KEYS),
        "slot_count": _SLOT_COUNT,
    }


def set_bind(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        slot = int(payload.get("slot"))
    except Exception:
        return {"ok": False, "message": "slot must be an integer 0..%s." % (_SLOT_COUNT - 1)}
    if slot < 0 or slot >= _SLOT_COUNT:
        return {"ok": False, "message": f"slot out of range 0..{_SLOT_COUNT - 1}."}
    action_id = str(payload.get("action_id") or payload.get("action") or "").strip()
    if action_id and _action_by_id(action_id) is None:
        return {"ok": False, "message": f"Unknown action_id {action_id!r}."}
    key = _normalize_key(str(payload.get("key") or ""))
    if key and not action_id:
        return {"ok": False, "message": "Pick an action before setting a key."}
    # Prevent two slots sharing the same key.
    if key:
        for i, cfg in enumerate(_slot_config):
            if i != slot and _normalize_key(str(cfg.get("key") or "")) == key:
                return {"ok": False, "message": f"Key {key} is already used by Custom {i + 1}."}
    _slot_config[slot] = {"action_id": action_id, "key": key}
    _apply_slot_to_keybind(slot)
    path = _save_config()
    label = (_action_by_id(action_id) or {}).get("label") or "(cleared)"
    return {
        "ok": True,
        "message": f"Custom {slot + 1}: {label} → {key or 'unbound'} (saved {path.name}).",
        **{k: v for k, v in status_payload().items() if k != "ok" and k != "message"},
    }


def clear_bind(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        slot = int(payload.get("slot"))
    except Exception:
        return {"ok": False, "message": "slot must be an integer."}
    return set_bind({"slot": slot, "action_id": "", "key": ""})


# Build at import so __init__ can pass the list into build_mod.
CUSTOM_KEYBINDS = build_keybinds()
