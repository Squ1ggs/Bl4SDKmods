"""Extended localhost bridge actions used by the desktop application."""
from __future__ import annotations

import re
import threading
from typing import Any

from . import mobility_runtime
from . import legit_builder_core
from .bridge_catalog import run_catalog
from .challenge_bulk_runtime import CATEGORY_LABELS, cancel as challenge_cancel, request_selected as challenge_request, status as challenge_status
from .dev_tools import (
    activate_devperk,
    set_ammo_regen_rate,
    set_weapons_restricted,
    teleport_pawn_to_debug_cam,
)
from .golden_chest_keybinds import close_golden_chest, open_golden_chest  # noqa: F401
from .inventory_capacity import set_inventory_sizes_for_all_party, set_inventory_sizes_for_party_index
from .item_pool_spawning import (
    DEFAULT_ITEM_LEVEL,
    filter_item_pools,
    queue_item_pool_entry,
    queue_all_filtered_item_pools,
    cancel_bulk_spawn_batch,
    bulk_spawn_active,
    bulk_spawn_status,
)
from . import spawn_targets
from .movement_adjustments import set_no_target

_OPEN_REWARDS_LARGE_WARNING = (
    "Open rewards runs one mail package at a time with a 3–5s wait between opens "
    "(never bulk-open — that can crash or blank backpacks in multiplayer). "
    "Large sends (250+) still take a while; prefer solo for big opens, then bank/mule before rejoining MP."
)
from .panel_manifest import get_panel_manifest
from .party_helpers import _kick_party_player_by_index, _list_party_players
from .player_economy import _resolve_target_pc_for_index, _set_max_sdu_points_on_pc, max_all_for_target
from . import rarity_weights
from .serial_converter import human_to_serial, serial_to_human
from .serial_rewards import (
    _do_give_serial_to_player_indices,
    _expand_serial_token,
    _extract_yaml_serial_fields,
    _is_single_pasted_base85,
    _join_wrapped_serial_lines,
    open_all_party_reward_packages,
    serial_delivery_progress,
    serial_delivery_status,
)
from .shinies import drop_all_shinies
from .travel import travel_to_map, travel_to_preset, travel_to_station
from . import uvhm_runtime
from . import world_spawn
from . import loot_shapes
from .backend_actions import (
    _boost_target_indices,
    _boost_targets_from_payload,
    _fail,
    _ok,
    _payload_player_index,
    _player_rows,
    _resolve_pc,
    freecam_disable,
    freecam_enable,
    freecam_pull_target,
    freecam_set_speed,
    get_target_player_index,
    give_currency,
    give_experience,
    max_all,
    party_roster,
    set_target_player,
    lab_pc_rpc,
    lab_live_attr,
)


def _serials_from_text(raw: str) -> list[str]:
    """One pasted line is one serial. Split only on a new @U prefix, never on ` ' @ inside Base85."""
    out: list[str] = []
    seen: set[str] = set()

    def _unwrap(token: str) -> str:
        s = str(token or "").strip()
        if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
            s = s[1:-1].strip()
        if len(s) >= 2 and s[0] == "`" and s[-1] == "`" and s.count("`") == 2:
            s = s[1:-1].strip()
        return s.rstrip("'\"`,}])")

    def _add(token: str) -> None:
        s = _unwrap(token)
        if not s or s in seen:
            return
        # Keep @U and human (comma) forms; resolve_serials converts later.
        if not (s.startswith("@U") or ("," in s and any(ch.isdigit() for ch in s))):
            return
        seen.add(s)
        out.append(s)

    # Save-editor / STBX YAML: inventory.items.*.serial: '@U…'
    yaml_hits = _extract_yaml_serial_fields(raw)
    if yaml_hits:
        for serial in yaml_hits:
            _add(serial)
        return out

    # Moxsy-style: one @U per line
    non_empty = [ln.strip() for ln in str(raw or "").replace("\r", "\n").split("\n") if ln.strip()]
    at_u_lines = [ln for ln in non_empty if ln.startswith("@U") or re.match(r"^['\"]@U", ln)]
    if len(non_empty) >= 2 and len(at_u_lines) >= max(2, int(0.8 * len(non_empty))):
        for ln in at_u_lines:
            _add(ln)
        return out

    for line in _join_wrapped_serial_lines(raw):
        token = _unwrap(line)
        if not token:
            continue
        idx = token.find("@U")
        if idx >= 0:
            blob = token[idx:]
            if _is_single_pasted_base85(blob):
                _add(blob)
            else:
                for part in _expand_serial_token(blob):
                    _add(part)
            continue
        # Human serial paste: commas + digits, no @U
        if "," in token and any(ch.isdigit() for ch in token):
            _add(token)
    return out

def _all_player_indices() -> list[int]:
    from .party_helpers import _gbc_session_world_and_gamestate

    _world, gs = _gbc_session_world_and_gamestate()
    pa = getattr(gs, "PlayerArray", None) if gs is not None else None
    if pa is None:
        return []
    out: list[int] = []
    for idx in range(len(pa)):
        try:
            ps = pa[idx]
        except Exception:
            continue
        if ps is None:
            continue
        out.append(idx)
    return out


def _indices_for_mode(mode: str, player_index: int | None) -> list[int]:
    mode_l = str(mode or "selected").strip().lower()
    if mode_l in ("all", "everyone", "lobby"):
        return _all_player_indices()
    if mode_l in ("player", "pick_player", "specific"):
        if player_index is None or str(player_index).strip() == "":
            return []
        idx = int(player_index)
        if idx < 0:
            return _all_player_indices()
        return [idx]
    if mode_l in ("nonhost", "non_host", "each_nonhost", "all_non_host"):
        from .party_helpers import _gbc_session_world_and_gamestate

        world, gs = _gbc_session_world_and_gamestate()
        if world is None or gs is None:
            return []
        from mods_base import get_pc

        host_pc = get_pc()
        host_ps = getattr(host_pc, "PlayerState", None) if host_pc is not None else None
        pa = getattr(gs, "PlayerArray", None)
        if pa is None:
            return []
        out: list[int] = []
        for idx in range(len(pa)):
            try:
                ps = pa[idx]
            except Exception:
                continue
            if ps is None:
                continue
            if host_ps is not None and ps is host_ps:
                continue
            out.append(idx)
        return out
    # selected (and aliases): honor explicit index, including -1 = all players
    if player_index is not None and str(player_index).strip() != "":
        idx = int(player_index)
        if idx < 0:
            return _all_player_indices()
        return [idx]
    idx = int(get_target_player_index())
    if idx < 0:
        return _all_player_indices()
    return [idx]

def _apply_level_override(serials: list[str], enabled: bool, level: int) -> tuple[list[str], str | None]:
    if not enabled:
        return list(serials), None
    try:
        level_i = max(1, min(int(level or DEFAULT_ITEM_LEVEL), 100))
    except Exception:
        level_i = int(DEFAULT_ITEM_LEVEL)
    out: list[str] = []
    warnings: list[str] = []
    level_re = re.compile(r"^(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*)\d+")
    try:
        from .serial_converter import rewrite_item_level
    except Exception:
        rewrite_item_level = None  # type: ignore[assignment]
    for index, serial in enumerate(serials):
        raw = str(serial or "").strip()
        if not raw:
            continue
        try:
            if raw.startswith("@U") and rewrite_item_level is not None:
                out.append(str(rewrite_item_level(raw, level_i)))
                continue
            human = serial_to_human(raw) if raw.startswith("@U") else raw
            new_human, count = level_re.subn(rf"\g<1>{level_i}", human, count=1)
            if count <= 0:
                raise ValueError("could not find leading item level (expected N, 0, 1, LEVEL| …)")
            converted = human_to_serial(new_human)
            if not converted or not str(converted).startswith("@U"):
                raise ValueError("human→@U re-encode failed after level rewrite")
            out.append(converted)
        except Exception as exc:
            # Newer/DLC serial layouts may not be understood by the optional
            # converter yet. Delivery is more important than a level rewrite:
            # keep the original valid @U code and report that override was skipped.
            out.append(raw)
            warnings.append(f"serial #{index + 1}: {exc}")
    warning = None
    if warnings:
        warning = f"Level override skipped for {len(warnings)} serial(s); original serial delivered ({warnings[0]})."
    return out, warning


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _serials_from_resolved_list(items: list[Any]) -> list[str]:
    """Keep each already-resolved row as one serial.

    Re-running ``_serials_from_text`` on a clean @U list splits on characters
    inside Base85 and silently drops codes (238 selected → ~104 queued).
    """
    out: list[str] = []
    for raw in items:
        token = str(raw or "").strip()
        if len(token) >= 2 and ((token[0] == token[-1] == '"') or (token[0] == token[-1] == "'")):
            token = token[1:-1].strip()
        if not token:
            continue
        if token.startswith("@U"):
            out.append(token)
            continue
        if "," in token and any(ch.isdigit() for ch in token):
            out.append(token)
            continue
        out.extend(_serials_from_text(token))
    return out


def _dedupe_serials_preserve_order(serials: list[str]) -> tuple[list[str], int]:
  seen: set[str] = set()
  out: list[str] = []
  dupes = 0
  for raw in serials:
    token = str(raw or "").strip()
    if not token:
      continue
    if token in seen:
      dupes += 1
      continue
    seen.add(token)
    out.append(token)
  return out, dupes


def deliver_serials(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from .session_guards import session_safe

        if not session_safe():
            return _fail("Load a character in-world first (not main menu / travel).")
    except Exception:
        pass
    serials = payload.get("serials")
    if isinstance(serials, str):
        serials = _serials_from_text(serials)
    elif isinstance(serials, list):
        serials = _serials_from_resolved_list(serials)
    else:
        serials = _serials_from_text(str(payload.get("text") or ""))
    if not serials:
        return _fail("No serials in payload (paste @U or human/deserialized codes).")
    # Human / deserialized lines → @U (same path as ImGui Give_Serial), including self-send.
    try:
        from .serial_rewards import _resolve_give_serial_strings

        resolved = _resolve_give_serial_strings(list(serials))
    except Exception as exc:
        return _fail(f"Could not convert serial(s) for delivery: {exc}")
    if not resolved:
        return _fail(
            "Could not convert those codes to @U serials. "
            "Use Convert first, or paste @U / valid human lines (serialize must be enabled)."
        )
    serials = [str(s).strip() for s in resolved if str(s).strip()]
    if not serials:
        return _fail("No @U serials after conversion.")
    raw_count = len(serials)
    serials, duplicate_serials = _dedupe_serials_preserve_order(serials)
    if not serials:
        return _fail("No @U serials in payload after deduplication.")
    try:
        count = max(1, min(int(payload.get("count") or payload.get("amount") or 1), 99))
    except Exception:
        count = 1
    if count > 1:
        serials = [serial for serial in serials for _ in range(count)]
    override_warning = None
    level_override = _coerce_bool(payload.get("level_override"), default=False)
    try:
        level_i = int(payload.get("level") or DEFAULT_ITEM_LEVEL)
    except Exception:
        level_i = int(DEFAULT_ITEM_LEVEL)
    # Rewriting 500+ @U codes on the click/frame AVs — defer to per-package tick work.
    defer_level = level_override and len(serials) >= 80
    if level_override and not defer_level:
        serials, override_warning = _apply_level_override(
            serials, True, level_i
        )
    mode = str(payload.get("mode") or "player").strip().lower()
    player_raw = payload.get("player_index")
    player_index = None
    if player_raw not in (None, ""):
        try:
            player_index = int(player_raw)
        except Exception:
            player_index = None
    # Always resolve a real recipient — never leave "selected"/empty as nobody.
    if mode in ("selected", "roster", ""):
        mode = "all" if player_index is not None and int(player_index) < 0 else "player"
    if mode in ("player", "pick_player") and player_index is None:
        try:
            player_index = int(get_target_player_index())
        except Exception:
            player_index = 0
    if mode in ("player", "pick_player") and player_index is not None and int(player_index) < 0:
        mode = "all"
        player_index = None
    if mode in ("player", "pick_player"):
        indices = _indices_for_mode("player", player_index)
    else:
        indices = _indices_for_mode(mode, player_index)
    if not indices:
        # Last resort: host slot 0 so we never queue mail to nobody.
        indices = _indices_for_mode("player", 0)
    if not indices:
        return _fail("No delivery targets available. Connect in-game as host and pick Send to.")
    open_raw = payload.get("open_rewards")
    open_rewards = _coerce_bool(open_raw, default=False)
    open_rewards_suppressed = False
    try:
        if open_rewards and bool(challenge_status().get("active")):
            open_rewards = False
            open_rewards_suppressed = True
    except Exception:
        pass
    scope = str(payload.get("mode") or "player")
    if len(indices) == 1:
        scope = f"player {indices[0]}"
    elif mode in ("all", "everyone", "lobby"):
        scope = "all players"
    queued = _do_give_serial_to_player_indices(
        serials,
        indices,
        scope_label=scope,
        open_rewards=open_rewards,
        level_override=bool(defer_level),
        level=level_i,
    )
    try:
        queued_n = int(queued or 0)
    except Exception:
        queued_n = 0
    if queued_n <= 0:
        return _fail(
            "Could not resolve any live recipients for that Send to choice. "
            "Refresh status, pick a name in Send to (or All players), then try again."
        )
    try:
        selected_n = int(payload.get("_selected_count") or 0)
    except Exception:
        selected_n = 0
    skipped = max(0, selected_n - len(serials)) if selected_n > len(serials) else 0
    message = f"Queued {len(serials)} serial(s) for {queued_n} player(s) ({scope})."
    if duplicate_serials > 0:
        message = (
            f"{message} Skipped {duplicate_serials} duplicate serial(s) "
            f"({raw_count} selected → {len(serials)} unique)."
        )
    if skipped > 0:
        message = (
            f"{message} {skipped} selected row(s) had no usable serial or were not loaded "
            f"(checked {selected_n} selected) — use Select all filtered, then Deliver."
        )
    if open_rewards_suppressed:
        message = (
            f"{message} Open rewards forced Off while Complete ALL / challenge bulk is running "
            "(Reward Center often has hundreds of packages)."
        )
    elif open_rewards:
        if len(serials) >= 200:
            message = (
                f"{message} Large send: mail packages first, then rewards open one-by-one "
                "(~4s between opens — stay in-world until status says Rewards opened)."
            )
        else:
            message = (
                f"{message} Rewards will open one-by-one in the background "
                "(~4s between packages — stay in-world until status says Rewards opened)."
            )
    if defer_level:
        message = (
            f"{message} Level override to {level_i} runs per mail package "
            "(safer for large packs)."
        )
    open_warning = ""
    if open_rewards and len(serials) >= 250:
        open_warning = _OPEN_REWARDS_LARGE_WARNING
        message = f"{message} {open_warning}"
    if override_warning:
        message = f"{message} {override_warning}"
    return _ok(
        message,
        count=len(serials),
        players=queued_n,
        warning=override_warning or open_warning or "",
        open_rewards=open_rewards,
        selected_count=selected_n,
        skipped=skipped,
        open_rewards_suppressed=bool(open_rewards_suppressed),
        packages=max(1, (len(serials) + 5) // 6) if len(serials) >= 500 else max(1, (len(serials) + 11) // 12),
    )


def serial_store_save(payload: dict[str, Any]) -> dict[str, Any]:
    from . import serial_store

    group = str(payload.get("group") or "Default").strip() or "Default"
    if group.lower() == "all":
        group = "Default"
    name = str(payload.get("name") or "").strip()
    entry_id = str(payload.get("id") or payload.get("entry_id") or "")
    raw_serial = str(payload.get("serial") or payload.get("text") or "")
    # Multi-line / multi-@U paste → one library row per serial in the same pack.
    serials = _serials_from_text(raw_serial)
    if not serials:
        single = raw_serial.strip()
        if single:
            serials = [single]
    if not serials:
        return _fail("Serial is required before saving.")
    try:
        if entry_id and len(serials) == 1:
            entry = serial_store.save_entry(
                entry_id=entry_id,
                name=name,
                group=group,
                serial=serials[0],
            )
            return _ok(f"Saved {entry.get('name') or 'entry'}.", entry=entry, group=group)
        added: list[dict[str, str]] = []
        for index, serial in enumerate(serials, start=1):
            entry_name = name
            if not entry_name:
                snippet = serial.replace("\n", " ").strip()
                entry_name = (snippet[:37] + "…") if len(snippet) > 40 else (snippet or "Saved serial")
            elif len(serials) > 1:
                entry_name = f"{name} #{index}"
            added.append(
                serial_store.save_entry(name=entry_name, group=group, serial=serial)
            )
    except ValueError as exc:
        return _fail(str(exc))
    if len(added) == 1:
        return _ok(f"Saved {added[0].get('name') or 'entry'}.", entry=added[0], group=group)
    return _ok(
        f"Saved {len(added)} serial(s) to pack “{group}”.",
        entry=added[-1],
        entries=added,
        added=len(added),
        group=group,
    )


def serial_store_import_serials(payload: dict[str, Any]) -> dict[str, Any]:
    """Save one or more paste-box serials into My Library under a named set."""
    from . import serial_store

    name = str(payload.get("name") or "").strip()
    group = str(payload.get("group") or name or "Paste").strip() or "Paste"
    raw = payload.get("serials")
    if isinstance(raw, list):
        serials = [str(item).strip() for item in raw if str(item).strip()]
    else:
        serials = _serials_from_text(str(raw or payload.get("text") or ""))
    if not name:
        return _fail("Enter a name for this library set.")
    if not serials:
        return _fail("No serials to save. Paste or Browse into the send box first.")
    added: list[dict[str, str]] = []
    try:
        for index, serial in enumerate(serials, start=1):
            entry_name = name if len(serials) == 1 else f"{name} #{index}"
            added.append(
                serial_store.save_entry(name=entry_name, group=group, serial=serial)
            )
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(
        f"Saved {len(added)} serial(s) to My Library under “{group}”.",
        added=len(added),
        group=group,
        entries=added,
    )


def serial_store_add_selected(payload: dict[str, Any]) -> dict[str, Any]:
    """Import ticked GZO / Lootlemon / queue rows into My Library."""
    from . import serial_store

    group = str(payload.get("group") or "Imported").strip() or "Imported"
    rows = payload.get("rows")
    titles = payload.get("titles")
    serials_raw = payload.get("serials")
    items: list[tuple[str, str]] = []
    if isinstance(rows, list) and rows:
        for row in rows:
            if not isinstance(row, dict):
                continue
            serial = str(row.get("serial") or "").strip()
            if not serial:
                continue
            title = str(row.get("title") or row.get("name") or serial[:48]).strip() or serial[:48]
            items.append((title, serial))
    elif isinstance(serials_raw, list):
        title_list = titles if isinstance(titles, list) else []
        for index, serial in enumerate(serials_raw):
            s = str(serial).strip()
            if not s:
                continue
            title = ""
            if index < len(title_list):
                title = str(title_list[index] or "").strip()
            items.append((title or s[:48], s))
    if not items:
        return _fail("Tick one or more catalog rows first, then Add to library.")
    existing = {str(e.get("serial") or "").strip() for e in serial_store.reload_entries()}
    added = 0
    skipped = 0
    saved: list[dict[str, str]] = []
    try:
        for title, serial in items:
            if serial in existing:
                skipped += 1
                continue
            entry = serial_store.save_entry(name=title, group=group, serial=serial)
            existing.add(serial)
            saved.append(entry)
            added += 1
    except ValueError as exc:
        return _fail(str(exc))
    if added <= 0 and skipped:
        return _ok(
            f"All {skipped} selected serial(s) were already in My Library.",
            added=0,
            skipped=skipped,
            group=group,
        )
    msg = f"Added {added} serial(s) to My Library under “{group}”."
    if skipped:
        msg += f" Skipped {skipped} duplicate(s)."
    return _ok(msg, added=added, skipped=skipped, group=group, entries=saved)


def serial_store_delete(payload: dict[str, Any]) -> dict[str, Any]:
    from . import serial_store

    raw_ids = payload.get("ids") or payload.get("entry_ids") or payload.get("id")
    if isinstance(raw_ids, str):
        ids = [raw_ids.strip()] if raw_ids.strip() else []
    elif isinstance(raw_ids, list):
        ids = [str(item).strip() for item in raw_ids if str(item).strip()]
    else:
        ids = []
    try:
        deleted = serial_store.delete_entries(ids)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(f"Deleted {deleted} saved serial(s).", deleted=deleted)


def serial_store_duplicate(payload: dict[str, Any]) -> dict[str, Any]:
    from . import serial_store

    entry_id = str(payload.get("id") or payload.get("entry_id") or "").strip()
    if not entry_id:
        return _fail("Select a saved serial before duplicating.")
    try:
        entry = serial_store.duplicate_entry(entry_id)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(f"Duplicated as {entry.get('name') or 'copy'}.", entry=entry)


def serial_store_export_text(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import serial_store

    payload = payload or {}
    group = str(payload.get("group") or "All").strip() or "All"
    try:
        text = serial_store.export_text(group=group)
    except Exception as exc:
        return _fail(repr(exc))
    if not str(text or "").strip():
        return _fail("Library is empty — nothing to export.")
    label = "all packs" if group == "All" else f"pack “{group}”"
    return _ok(f"Exported {label}.", text=text, group=group)


def serial_store_import_merge(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import serial_store

    payload = payload or {}
    text = str(payload.get("text") or payload.get("input") or "")
    default_group = str(payload.get("group") or payload.get("name") or "Imported").strip() or "Imported"
    try:
        result = serial_store.import_merge_text(text, default_group=default_group)
    except ValueError as exc:
        return _fail(str(exc))
    added = int(result.get("added") or 0)
    skipped = int(result.get("skipped") or 0)
    return _ok(
        f"Imported {added} serial(s) into My Library "
        f"(skipped {skipped} duplicate(s)). Expand packs below to browse/edit — nothing was wiped.",
        **result,
    )


def serial_store_rename_group(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import serial_store

    payload = payload or {}
    old = str(payload.get("old_group") or payload.get("group") or "").strip()
    new = str(payload.get("new_group") or payload.get("name") or "").strip()
    try:
        changed = serial_store.rename_group(old, new)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(f"Renamed pack “{old}” → “{new}” ({changed} entr(y/ies)).", changed=changed)


def serial_store_create_group(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import serial_store

    payload = payload or {}
    name = str(payload.get("group") or payload.get("name") or "").strip()
    try:
        cleaned = serial_store.create_group(name)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(
        f"Pack “{cleaned}” ready — set Pack name, paste serials, then Save entry.",
        group=cleaned,
        entry={"id": "", "name": "", "group": cleaned, "serial": ""},
    )


def serial_store_delete_group(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import serial_store

    payload = payload or {}
    name = str(payload.get("group") or payload.get("name") or "").strip()
    try:
        deleted = serial_store.delete_group(name)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(f"Deleted pack “{name}” ({deleted} entr(y/ies)).", deleted=deleted, group=name)


def serial_store_export_json(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import serial_store

    payload = payload or {}
    group = str(payload.get("group") or "All").strip() or "All"
    try:
        text = serial_store.export_json(group=group)
    except Exception as exc:
        return _fail(repr(exc))
    if not str(text or "").strip() or '"entries": []' in text.replace(" ", ""):
        # Still allow empty structured export when library truly empty.
        rows = serial_store.filter_entries(group=group)
        if not rows:
            return _fail("Library is empty — nothing to export.")
    label = "all packs" if group == "All" else f"pack “{group}”"
    return _ok(f"Exported {label} as JSON.", text=text, group=group)


def serial_delivery_status_action(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    prog = serial_delivery_progress()
    msg = str(prog.get("message") or serial_delivery_status() or "Serial delivery idle.")
    return _ok(msg, status=prog, progress=prog)


def max_sdu(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    details: list[str] = []
    for idx in indices:
        pc, err = _resolve_pc(idx)
        if pc is None:
            details.append(f"index {idx}: {err}")
            continue
        if _set_max_sdu_points_on_pc(pc):
            ok_n += 1
            details.append(f"index {idx}: OK")
        else:
            details.append(f"index {idx}: Max SDU failed")
    if ok_n == 0:
        return _fail("; ".join(details) or "Max SDU failed.")
    if len(indices) == 1:
        return _ok(f"Max SDU applied to player index {indices[0]}.")
    return _ok(f"Max SDU applied to {ok_n}/{len(indices)} player(s).")


def inventory_set_sizes(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        backpack = int(payload.get("backpack_size") or 500)
        bank = int(payload.get("bank_size") or 500)
    except Exception:
        return _fail("backpack_size and bank_size must be integers.")
    scope = str(payload.get("scope") or "target").lower()
    player_index = _payload_player_index(payload)
    if scope == "all" or (player_index is not None and player_index < 0) or (
        player_index is None and get_target_player_index() < 0
    ):
        count = set_inventory_sizes_for_all_party(backpack, bank)
        return _ok(f"Set inventory sizes for {count} player(s).")
    idx = get_target_player_index() if player_index is None else int(player_index)
    try:
        name = set_inventory_sizes_for_party_index(idx, backpack, bank)
    except Exception as exc:
        return _fail(repr(exc))
    return _ok(f"Backpack={backpack}, bank={bank} for {name}.")


def party_refresh(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    return party_roster()


def party_kick(payload: dict[str, Any]) -> dict[str, Any]:
    raw_index = payload.get("player_index")
    if raw_index is None or str(raw_index).strip() == "":
        player_index = get_target_player_index()
    else:
        try:
            player_index = int(raw_index)
        except Exception:
            return _fail("player_index required.")
    if player_index < 0:
        return _fail("Pick a single player to kick (All players is not valid for kick).")
    reason = str(payload.get("reason") or "Squ1ggs Boosting Tools")
    if _kick_party_player_by_index(player_index, reason=reason):
        return _ok(f"Kick requested for index {player_index}.")
    return _fail(f"Could not kick index {player_index}.")


def _player_index_from_payload(payload: dict[str, Any]) -> int:
    parsed = _payload_player_index(payload)
    if parsed is None:
        return get_target_player_index()
    return int(parsed)


def _single_target_index(payload: dict[str, Any] | None = None) -> int:
    """Resolve one boost-target index; empty/missing payload falls back to live target."""
    return _player_index_from_payload(payload or {})


def _uvhm_max_rank_from_payload(payload: dict[str, Any]) -> int:
    raw = payload.get("max_rank")
    if raw is None or str(raw).strip() == "":
        return 7
    rank = int(raw)
    return max(1, min(7, rank))


def _progression_job_busy() -> str:
    try:
        uvhm = uvhm_runtime.status()
        if bool(uvhm.get("running") or uvhm.get("queued")):
            return "UVHM"
    except Exception:
        pass
    try:
        bulk = challenge_status()
        if bool(bulk.get("active") or bulk.get("queued")):
            return "bulk challenges"
    except Exception:
        pass
    return ""


def uvhm_start(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    idx = _player_index_from_payload(payload)
    max_rank = _uvhm_max_rank_from_payload(payload)
    if idx < 0:
        return _fail(
            "Start UVHM (target) needs one Boost target player — "
            "set the player bar under the tabs (not All players), or use Start UVHM (all lobby)."
        )
    try:
        from .uvhm_progression import selected_lobby_identity

        identity = selected_lobby_identity(int(idx))
    except Exception as exc:
        return _fail(
            f"Could not resolve Boost target index {idx} in the lobby: {exc}. "
            "Refresh status / pick the player again, then retry."
        )
    if uvhm_runtime.request_selected(idx, max_rank=max_rank):
        who = getattr(identity, "display_name", None) or f"index {idx}"
        try:
            from . import hold_session

            hold_session.arm_for_job("uvhm")
        except Exception:
            pass
        return _ok(f"UVHM workflow queued for {who} (up to rank {max_rank}).")
    st = uvhm_runtime.status()
    return _fail(st.get("message") or st.get("detail_message") or "UVHM request failed.")


def uvhm_start_all(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    max_rank = _uvhm_max_rank_from_payload(payload)
    if uvhm_runtime.request_all(confirmed=bool(payload.get("confirmed", True)), max_rank=max_rank):
        try:
            from . import hold_session

            hold_session.arm_for_job("uvhm")
        except Exception:
            pass
        return _ok(f"All-lobby UVHM workflow queued (up to rank {max_rank}).")
    return _fail(uvhm_runtime.status().get("message") or "UVHM all-lobby request failed.")


def uvhm_cancel(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    if uvhm_runtime.cancel():
        try:
            from . import hold_session

            hold_session.release_job("uvhm")
        except Exception:
            pass
        return _ok("UVHM cancelled.")
    return _fail("Nothing to cancel.")


def uvhm_resume(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    if uvhm_runtime.resume():
        try:
            from . import hold_session

            hold_session.arm_for_job("uvhm")
        except Exception:
            pass
        return _ok("UVHM resumed.")
    return _fail("UVHM could not resume.")


def uvhm_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    return _ok("UVHM status.", uvhm=uvhm_runtime.status())


def challenge_bulk_start(payload: dict[str, Any]) -> dict[str, Any]:
    category = str(payload.get("category") or CATEGORY_LABELS[0])
    idx = _player_index_from_payload(payload)
    if not bool(payload.get("confirmed", True)):
        return _fail("Confirmation required for challenge bulk.")
    # Complete ALL may only queue rewards. It must never auto-open its hundreds
    # of packages in a multiplayer session (especially unsafe for console peers).
    payload["open_rewards"] = False
    tokens_raw = payload.get("tokens") or payload.get("token")
    tokens: list[str] = []
    if isinstance(tokens_raw, str) and tokens_raw.strip():
        tokens = [tokens_raw.strip()]
    elif isinstance(tokens_raw, list):
        tokens = [str(t).strip() for t in tokens_raw if str(t).strip()]
    if challenge_request(idx, category, confirmed=True, tokens=tokens or None):
        who = "All players" if int(idx) < 0 else f"player index {idx}"
        try:
            from . import hold_session

            hold_session.arm_for_job("challenges")
        except Exception:
            pass
        # Full All non-UVHM floods Reward Center — keep Open pending rewards off.
        mass_all = (not tokens) and str(category).strip() == "All non-UVHM"
        if mass_all:
            try:
                from .serial_rewards import block_open_all_after_challenge_bulk

                block_open_all_after_challenge_bulk(reason="Complete ALL non-UVHM")
            except Exception:
                pass
        st = challenge_status()
        total = int(st.get("total") or st.get("progress_total") or 0)
        if tokens:
            note = f"Queued {len(tokens)} selected challenge(s) for {who}."
            advisory = ""
        else:
            note = f"Queued {total} · {category} for {who}."
            advisory = (
                "All non-UVHM only sends Reward Center packages; it never opens them. "
                "Console/cross-play users can receive 600+ items: leave multiplayer, open "
                "the rewards in solo, sell junk and reduce carried items before rejoining."
                if mass_all
                else ""
            )
        return _ok(
            note,
            suppress_open_all=bool(mass_all),
            category=category,
            challenge=st,
            queued_count=total,
            progress_total=total,
            advisory=advisory,
        )
    return _fail(challenge_status().get("message") or "Challenge bulk failed.")


def challenge_complete_selected(payload: dict[str, Any]) -> dict[str, Any]:
    """Complete one or more explicitly selected challenge tokens (not a whole category)."""
    tokens_raw = payload.get("tokens") or payload.get("token")
    tokens: list[str] = []
    if isinstance(tokens_raw, str) and tokens_raw.strip():
        tokens = [tokens_raw.strip()]
    elif isinstance(tokens_raw, list):
        tokens = [str(t).strip() for t in tokens_raw if str(t).strip()]
    if not tokens:
        return _fail("Select at least one challenge first.")
    idx = _player_index_from_payload(payload)
    if not bool(payload.get("confirmed", True)):
        return _fail("Confirmation required.")
    if challenge_request(idx, "All non-UVHM", confirmed=True, tokens=tokens):
        who = "All players" if int(idx) < 0 else f"player index {idx}"
        try:
            from . import hold_session

            hold_session.arm_for_job("challenges")
        except Exception:
            pass
        st = challenge_status()
        return _ok(
            f"Queued {len(tokens)} selected challenge(s) for {who}.",
            count=len(tokens),
            challenge=st,
            queued_count=int(st.get("total") or len(tokens)),
            progress_total=int(st.get("total") or len(tokens)),
        )
    return _fail(challenge_status().get("message") or "Could not queue selected challenges.")


def challenge_bulk_cancel(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    if challenge_cancel():
        try:
            from . import hold_session

            hold_session.release_job("challenges")
        except Exception:
            pass
        return _ok("Challenge bulk cancelled.")
    return _fail("Nothing to cancel.")


def challenge_bulk_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    st = challenge_status()
    suppress = False
    try:
        from .serial_rewards import open_all_blocked_after_challenge_bulk

        suppress = bool(open_all_blocked_after_challenge_bulk())
    except Exception:
        suppress = False
    # Never spread st["ok"] (accepted-count int) onto the response — it overwrites
    # bridge ok:True and makes EXE polls look failed while the count is still 0.
    return _ok(
        "Challenge bulk status.",
        challenge=st,
        categories=list(CATEGORY_LABELS),
        suppress_open_all=suppress,
        active=st.get("active"),
        queued=st.get("queued"),
        running=st.get("running"),
        phase=st.get("phase"),
        message=st.get("message"),
        index=st.get("index"),
        progress_index=st.get("progress_index"),
        total=st.get("total"),
        progress_total=st.get("progress_total"),
        accepted=st.get("ok"),
        failed=st.get("failed"),
        skipped=st.get("skipped"),
        token=st.get("token"),
    )


def _resolve_item_pool_entry(payload: dict[str, Any]) -> dict[str, str] | None:
    """Match BLImGui: use the full catalog row (itempool + catalog_key), not pool name alone."""
    raw_entry = payload.get("entry")
    if isinstance(raw_entry, dict):
        pool = str(raw_entry.get("itempool") or "").strip()
        catalog = str(raw_entry.get("catalog_key") or "").strip()
        display = str(raw_entry.get("display_name") or "").strip()
        if pool or catalog:
            out: dict[str, str] = {}
            for key, value in raw_entry.items():
                if value is None:
                    continue
                text = str(value).strip()
                if text:
                    out[str(key)] = text
            if display and "display_name" not in out:
                out["display_name"] = display
            return out

    itempool = str(payload.get("itempool") or payload.get("pool") or "").strip()
    catalog_key = str(payload.get("catalog_key") or "").strip()
    display = str(payload.get("display_name") or "").strip()
    search = str(payload.get("search") or "")
    category = str(payload.get("category") or "All").strip() or "All"

    if catalog_key or itempool or display:
        rows = filter_item_pools(search=search, category=category, limit=0)
        if catalog_key:
            cat_l = catalog_key.casefold()
            for row in rows:
                if str(row.get("catalog_key") or "").casefold() == cat_l:
                    return dict(row)
        if itempool:
            pool_l = itempool.casefold()
            for row in rows:
                if str(row.get("itempool") or "").casefold() == pool_l:
                    return dict(row)
        if display:
            disp_l = display.casefold()
            for row in rows:
                if str(row.get("display_name") or "").casefold() == disp_l:
                    return dict(row)
    return None


def _loot_landing_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    shape = str(payload.get("shape") if payload.get("shape") is not None else "none").strip() or "none"
    from .loot_shapes import clamp_layout_params, normalize_drop_mode

    settle = normalize_drop_mode(payload.get("settle") if payload.get("settle") is not None else "none")
    layout = clamp_layout_params(
        radius=payload.get("radius", 200),
        spacing=payload.get("spacing", 72),
        line_length=payload.get("line_length", 520),
        drop_height=payload.get("drop_height", 440),
        z_bias=payload.get("z_bias", 18),
    )
    raw_defer = payload.get("spawn_then_shape")
    if isinstance(raw_defer, bool):
        spawn_then_shape = raw_defer
    else:
        spawn_then_shape = str(raw_defer or "").strip().lower() in ("1", "true", "yes", "on")
    stay_raw = payload.get("stay_in_air")
    stay_in_air = True if stay_raw is None or str(stay_raw).strip() == "" else str(stay_raw).strip().lower() in ("1", "true", "yes", "on")
    float_grab_raw = payload.get("float_on_grab")
    float_on_grab = str(float_grab_raw or "").strip().lower() in ("1", "true", "yes", "on")
    fill_raw = payload.get("fill_until_complete")
    if isinstance(fill_raw, bool):
        fill_until_complete = fill_raw
    else:
        fill_until_complete = str(fill_raw or "").strip().lower() in ("1", "true", "yes", "on")
    try:
        peel_after = max(0.0, min(60.0, float(payload.get("peel_after") or 0)))
    except Exception:
        peel_after = 0.0
    land_profile = str(payload.get("land_profile") or payload.get("layout_profile") or "bulk").strip().lower()
    if land_profile not in ("shiny", "bulk"):
        land_profile = "bulk"
    shape_text = str(payload.get("shape_text") or payload.get("text") or "").strip()
    if shape_text or shape.lower() in ("text", "text_shape", "words", "word", "write"):
        try:
            from .loot_shapes import sanitize_shape_text, set_shape_text  # noqa: PLC0415

            shape_text = set_shape_text(shape_text)
            if sanitize_shape_text(shape_text):
                shape = "text"
        except Exception:
            pass
    return {
        "shape": shape,
        "settle": settle,
        "drop_height": float(layout["drop_height"]),
        "line_length": float(layout["line_length"]),
        "radius": float(layout["radius"]),
        "spacing": float(layout["spacing"]),
        "z_bias": float(layout["z_bias"]),
        "spawn_then_shape": spawn_then_shape,
        "stay_in_air": stay_in_air,
        "float_on_grab": float_on_grab,
        "peel_after": peel_after,
        "land_profile": land_profile,
        "fill_until_complete": fill_until_complete,
        "shape_text": shape_text,
    }


def spawn_item_pool_action(payload: dict[str, Any]) -> dict[str, Any]:
    entry = _resolve_item_pool_entry(payload)
    if entry is None:
        return _fail("Select a pool from the filtered list above first.")
    itempool = str(entry.get("itempool") or "").strip()
    display = str(entry.get("display_name") or itempool).strip()
    try:
        level = int(payload.get("level") or DEFAULT_ITEM_LEVEL)
        count = int(payload.get("count") or 1)
    except Exception:
        return _fail("level and count must be integers.")
    where = spawn_targets.apply_from_payload(payload, default_party_index=get_target_player_index())
    try:
        requested = max(1, count)
        queue_item_pool_entry(entry, level=level, count=requested, **_loot_landing_kwargs(payload))
        return _ok(
            f"Queued {requested} item(s) from {display} near {where} (level {level}).",
            queued=requested,
        )
    except Exception as exc:
        return _fail(repr(exc))


def spawn_item_pool_all_action(payload: dict[str, Any]) -> dict[str, Any]:
    busy = _progression_job_busy()
    if busy:
        return _fail(f"Spawn All Filtered cannot start while {busy} is running.")
    search = str(payload.get("search") or "").strip()
    category = str(payload.get("category") or "All").strip() or "All"
    try:
        level = int(payload.get("level") or DEFAULT_ITEM_LEVEL)
        count = int(payload.get("count") or 1)
    except Exception:
        return _fail("level and count must be integers.")
    gap = payload.get("spawn_gap", payload.get("gap_sec"))
    per_tick = payload.get("spawn_per_tick", payload.get("per_tick"))
    spread_raw = payload.get("random_spread", payload.get("spawn_spread"))
    if isinstance(spread_raw, str):
        random_spread = spread_raw.strip().lower() in ("1", "true", "yes", "on")
    elif spread_raw is None:
        random_spread = None
    else:
        random_spread = bool(spread_raw)
    try:
        gap_sec = None if gap is None or str(gap).strip() == "" else float(gap)
    except Exception:
        gap_sec = None
    try:
        per_tick_n = None if per_tick is None or str(per_tick).strip() == "" else int(per_tick)
    except Exception:
        per_tick_n = None
    where = spawn_targets.apply_from_payload(payload, default_party_index=get_target_player_index())
    try:
        rows = filter_item_pools(
            search=search,
            category=category,
            limit=0,
            exclude_currency=_coerce_bool(payload.get("exclude_currency"), default=False),
            exclude_ai_guns=_coerce_bool(payload.get("exclude_ai_guns"), default=False),
        )
        if not rows:
            return _fail("No item pools match the current search/category filter.")
        land = _loot_landing_kwargs(payload)
        shape_l = str(land.get("shape") or "none").strip().lower()
        if (
            "fill_until_complete" not in payload
            and shape_l not in ("", "none", "off", "no", "vanilla")
        ):
            # Spawn All owns silhouette padding. Selected-item actions must
            # remain one requested item, but a shaped bulk request should not
            # silently stop halfway because an older client omitted this field.
            land["fill_until_complete"] = True
        queued = queue_all_filtered_item_pools(
            search,
            category,
            level=level,
            count=max(1, count),
            gap_sec=gap_sec,
            per_tick=per_tick_n,
            random_spread=random_spread,
            exclude_currency=_coerce_bool(payload.get("exclude_currency"), default=False),
            exclude_ai_guns=_coerce_bool(payload.get("exclude_ai_guns"), default=False),
            **land,
        )
        spread_label = "random spit" if random_spread else "no random spit"
        shape_l = str(land.get("shape") or "none")
        settle_l = str(land.get("settle") or "none")
        if shape_l not in ("", "none") or settle_l not in ("", "none"):
            spread_label = f"{shape_l}/{settle_l}"
        return _ok(
            f"Queued {queued} filtered pool(s) near {where} "
            f"({spread_label}, delay {gap_sec if gap_sec is not None else 0}s, "
            f"{per_tick_n or 2}/tick @ level {level}).",
            queued=queued,
            spawn_all=bulk_spawn_status(),
        )
    except Exception as exc:
        return _fail(repr(exc))


def spawn_item_pool_singular_test_action(payload: dict[str, Any]) -> dict[str, Any]:
    """Removed — use Spawn All Filtered."""
    del payload
    return _fail(
        "Test Singular Filtered was removed. Use Spawn All Filtered or Spawn Selected / Spawn Named Item."
    )


def spawn_item_pool_cancel(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    abandoned, ok = cancel_bulk_spawn_batch(log=True)
    running = bulk_spawn_active()
    if abandoned == 0 and not running:
        return _ok("Spawn batch was not running.", spawn_all=bulk_spawn_status())
    return _ok(
        f"Stopped spawn list ({abandoned} left unspawned, {ok} already ok).",
        spawn_all=bulk_spawn_status(),
    )


def spawn_item_pool_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    status = bulk_spawn_status()
    return _ok(str(status.get("message") or "Spawn All batch: idle"), spawn_all=status)


def travel_map(payload: dict[str, Any]) -> dict[str, Any]:
    map_name = str(payload.get("map") or payload.get("map_name") or "").strip()
    if not map_name:
        return _fail("map required.")
    return _ok(travel_to_map(map_name))


def travel_station(payload: dict[str, Any]) -> dict[str, Any]:
    station = str(payload.get("station") or "").strip()
    if not station:
        return _fail("station required.")
    return _ok(travel_to_station(station))


def travel_preset(payload: dict[str, Any]) -> dict[str, Any]:
    preset_id = str(payload.get("preset") or payload.get("preset_id") or payload.get("id") or "").strip()
    if not preset_id:
        preset_id = "tuba_boss_arena"
    try:
        return _ok(travel_to_preset(preset_id))
    except Exception as exc:
        return _fail(str(exc))


def spawn_mix(payload: dict[str, Any]) -> dict[str, Any]:
    mix_id = str(payload.get("mix_id") or payload.get("id") or "").strip()
    if not mix_id:
        return _fail("mix_id required.")
    try:
        count = max(1, min(int(payload.get("count") or 1), 999))
    except Exception:
        return _fail("count must be an integer.")
    try:
        _raise_spawn_caps()
        ok, msg = world_spawn.spawn_mix_def(
            mix_id,
            count=count,
            aggro_mode=str(payload.get("aggro_mode") or "attack_me"),
            party_index=int(
                payload.get("player_index")
                if payload.get("player_index") is not None and str(payload.get("player_index")).strip() != ""
                else (payload.get("party_index") or get_target_player_index())
            ),
            spawn_anchor=str(payload.get("spawn_anchor") or "local"),
        )
        return _ok(msg) if ok else _fail(msg)
    except Exception as exc:
        return _fail(repr(exc))


def _apply_bms_ui(controller: Any, payload: dict[str, Any]) -> None:
    ui = controller.ui
    if "aggro_mode" in payload:
        ui.aggro_mode = str(payload.get("aggro_mode") or "attack_me")
    # Prefer live roster player_index (0-based). Legacy party_index still accepted as-is.
    # All (-1) is not a spawn seat — keep the previous party index / host instead of clamping to 0.
    if payload.get("player_index") is not None and str(payload.get("player_index")).strip() != "":
        try:
            parsed_idx = int(payload.get("player_index"))
            if parsed_idx >= 0:
                ui.party_index = parsed_idx
        except Exception:
            pass
    elif "party_index" in payload:
        try:
            ui.party_index = max(0, int(payload.get("party_index") or 0))
        except Exception:
            pass
    if "spawn_anchor" in payload:
        anchor = str(payload.get("spawn_anchor") or "local").strip().lower()
        if anchor in ("local", "party", "npc_nearest"):
            ui.spawn_anchor = anchor
    if "spawn_distance" in payload:
        try:
            ui.spawn_distance = float(payload.get("spawn_distance"))
        except Exception:
            pass
    if "spawn_spacing" in payload:
        try:
            ui.spawn_spacing = float(payload.get("spawn_spacing"))
        except Exception:
            pass


def _raise_spawn_caps() -> None:
    """Lift SpawnManager caps once per map — never find_all on every BMS click."""
    try:
        from .embedded_oak import engine as oak
        from mods_base import get_pc

        pc = get_pc()
        world = getattr(getattr(pc, "Pawn", None), "GetWorld", lambda: None)() if pc else None
        if world is None and pc is not None:
            try:
                world = pc.GetWorld()
            except Exception:
                world = None
        # Once-per-map path. Calling _overdrive_spawn_manager every click find_all's
        # SpawnManager and freezes the lobby when held shapes filled the UObject graph.
        oak._overdrive_spawn_manager_if_needed(world)
    except Exception:
        pass


def _bms_group_result(result: dict[str, Any]) -> dict[str, Any]:
    extra = {k: v for k, v in result.items() if k not in ("ok", "message")}
    msg = str(result.get("message") or "OK")
    if result.get("ok") is False:
        return _fail(msg, **extra)
    return _ok(msg, **extra)


def bms_group_add(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.add_wave(payload or {}))


def bms_group_remove(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.remove_wave(payload or {}))


def bms_group_clear_plan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.clear_plan(payload or {}))


def bms_group_set_options(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.set_options(payload or {}))


def bms_group_start(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.start(payload or {}))


def bms_group_stop(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.stop(payload or {}))


def bms_group_next(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.next_wave(payload or {}))


def bms_group_status(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    _ = payload
    return _bms_group_result(enc.status())


def bms_group_clear_live(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.clear_live(payload or {}))


def bms_group_save(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.save_named(payload or {}))


def bms_group_load(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.load_named(payload or {}))


def bms_group_delete_save(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import encounter_builder as enc

    return _bms_group_result(enc.delete_named(payload or {}))


def spawn_mob(payload: dict[str, Any]) -> dict[str, Any]:
    code = str(payload.get("code") or "").strip()
    if not code:
        return _fail("code required.")
    if not world_spawn.is_host():
        return _fail("Host / in-world session required for mob spawn.")
    try:
        count = max(1, min(int(payload.get("count") or 1), 999))
    except Exception:
        return _fail("count must be an integer.")
    try:
        from .embedded_bms import get_controller

        _raise_spawn_caps()
        controller = get_controller()
        _apply_bms_ui(controller, payload)
        ok, msg = controller.spawn_mob(code, count=count, defer=True)
        return _ok(msg) if ok else _fail(msg)
    except Exception as exc:
        return _fail(repr(exc))


def spawn_mobs(payload: dict[str, Any]) -> dict[str, Any]:
    raw_codes = payload.get("codes")
    if isinstance(raw_codes, str):
        codes = [raw_codes.strip()] if raw_codes.strip() else []
    elif isinstance(raw_codes, list):
        codes = [str(c).strip() for c in raw_codes if str(c).strip()]
    else:
        single = str(payload.get("code") or "").strip()
        codes = [single] if single else []
    if not codes:
        return _fail("Select at least one mob to spawn.")
    if not world_spawn.is_host():
        return _fail("Host / in-world session required for mob spawn.")
    try:
        count = max(1, min(int(payload.get("count") or 1), 999))
    except Exception:
        return _fail("count must be an integer.")
    try:
        from .embedded_bms import get_controller

        _raise_spawn_caps()
        controller = get_controller()
        _apply_bms_ui(controller, payload)
        queued = 0
        last_msg = ""
        for code in codes:
            ok, msg = controller.spawn_mob(code, count=count, defer=True)
            last_msg = msg
            if ok:
                queued += 1
            else:
                return _fail(f"Stopped after {queued} spawn(s): {msg}")
        return _ok(f"Queued {queued} mob type(s) × {count} each.", queued=queued, count=count, detail=last_msg)
    except Exception as exc:
        return _fail(repr(exc))


def barrel_logo(payload: dict[str, Any]) -> dict[str, Any]:
    """Spawn prop-pixel world text (barrel/chest/bank/etc glyphs)."""
    text = str(payload.get("text") or "").strip()
    if not text:
        row1 = str(payload.get("row1") or "").strip()
        row2 = str(payload.get("row2") or "").strip()
        row3 = str(payload.get("row3") or "").strip()
        text = "|".join(part for part in (row1, row2, row3) if part)
    if not text:
        return _fail("Enter text (use | between lines).")
    custom = str(payload.get("custom_actor") or "").strip()
    try:
        from .logo_actor_options import DEFAULT_LOGO_ACTOR
    except Exception:
        DEFAULT_LOGO_ACTOR = "electisafe"
    actor = (
        custom
        or str(payload.get("actor") or payload.get("barrel_name") or DEFAULT_LOGO_ACTOR).strip()
        or DEFAULT_LOGO_ACTOR
    )
    try:
        distance = float(payload.get("distance") or 1400)
        height = float(payload.get("height") or 750)
        spacing = float(payload.get("spacing") or 70)
        scale = float(payload.get("scale") or 0.45)
        max_props = max(0, min(int(payload.get("max_props") or 0), 2000))
    except Exception:
        return _fail("distance/height/spacing/scale/max_props must be numbers.")
    try:
        from .embedded_oak.engine import _logo_coop_heavy, _spawn_barrel_logo

        if _logo_coop_heavy():
            return _fail(
                "Co-op shape guest sync is still running — wait until the held shape finishes "
                "syncing (or clear pins), then spawn world text again. Spawning 180+ props during "
                "guest net push can crash BL4."
            )
        queued = int(
            _spawn_barrel_logo(
                barrel_name=actor,
                text=text,
                distance=distance,
                height=height,
                spacing=spacing,
                scale=scale,
                max_props=max_props,
            )
            or 0
        )
    except Exception as exc:
        return _fail(repr(exc))
    if queued <= 0:
        return _fail(
            f"Could not queue world text for {actor!r}. Use barrel, or spawn that actor "
            "once from Mob/IO then retry."
        )
    return _ok(
        f"Queued world text for {actor!r} ({queued} letter props). "
        "Seeds via Mob/IO first if needed, waits until that actor exists, then clones the text "
        "(same pattern as barrel — not just one prop).",
        spawned=queued,
        queued=queued,
        actor=actor,
    )


def barrel_logo_clear(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from .embedded_oak import engine as oak

        try:
            oak.cancel_logo_job()
        except Exception:
            pass
        try:
            oak.clear_logo_pins()
        except Exception:
            pass
        before = len(getattr(oak, "_SPAWNED", []) or [])
        kept = []
        for row in list(getattr(oak, "_SPAWNED", []) or []):
            if str(getattr(row, "label", "") or "").lower() == "barrel_logo":
                actor = getattr(row, "actor", None)
                try:
                    if actor is not None:
                        destroy = getattr(actor, "K2_DestroyActor", None) or getattr(actor, "Destroy", None)
                        if callable(destroy):
                            destroy()
                except Exception:
                    pass
                continue
            kept.append(row)
        oak._SPAWNED[:] = kept
        removed = before - len(kept)
        return _ok(f"Cleared {removed} barrel-logo prop(s).")
    except Exception as exc:
        return _fail(repr(exc))


def spawn_io(payload: dict[str, Any]) -> dict[str, Any]:
    cmd = str(payload.get("cmd") or "").strip()
    token = str(payload.get("token") or "").strip()
    # Alias shortcuts must map to catalog tokens. Bare "goldenchest" is not an
    # is_io_code() and falls through to run_oak_line — that crashed the game.
    _IO_TOKEN_ALIASES = {
        "goldenchest": "Lootable_GoldenChest",
        "golden_chest": "Lootable_GoldenChest",
        "golden": "Lootable_GoldenChest",
        "lootable_goldenchest": "Lootable_GoldenChest",
    }

    def _alias(raw: str) -> str:
        key = raw.lower().replace("-", "_").replace(" ", "")
        return _IO_TOKEN_ALIASES.get(key, raw)

    def _token_from_cmd(raw_cmd: str) -> str:
        parts = raw_cmd.split(None, 1)
        if len(parts) == 2 and parts[0].lower() in ("oak_spawnai", "oak_spawn", "oak_dual", "asd_dual"):
            return parts[1].strip()
        return ""

    if token:
        token = _alias(token)
    if not cmd and token:
        cmd = f"oak_spawnai {token}"
    elif cmd:
        extracted = _token_from_cmd(cmd)
        if extracted:
            token = _alias(extracted)
            prefix = cmd.split(None, 1)[0]
            cmd = f"{prefix} {token}"
        elif token:
            token = _alias(token)
    if not cmd:
        return _fail("cmd or token required.")
    if not world_spawn.is_host():
        return _fail("Host / in-world session required for IO spawn.")
    try:
        from .embedded_bms import get_controller
        from .embedded_bms.io_activate import (
            is_oak_dual_vending,
            needs_dual_world_spawn,
            oak_dual_cmd,
            short_io_token,
        )

        # Prefer the short IO token (Lootable_GoldenChest), never the whole cmd line.
        short = short_io_token(token) or short_io_token(_token_from_cmd(cmd)) or token
        if short and is_oak_dual_vending(short):
            cmd = oak_dual_cmd(short) or f"oak_dual {short}"
        elif short and needs_dual_world_spawn(short):
            # Keep a clean oak_spawnai <Token> line for dual machines only.
            cmd = f"oak_spawnai {short}"

        _raise_spawn_caps()
        controller = get_controller()
        _apply_bms_ui(controller, payload)
        activate = str(payload.get("activate") or "yes").strip().lower() in ("1", "true", "yes", "on")
        # Activation belongs inside the deferred spawn action. Doing it here
        # races the queue and reports "no last IO" before the object exists.
        ok, msg = controller.run_encounter_line(cmd, defer=True, activate=activate)
        return _ok(msg) if ok else _fail(msg)
    except Exception as exc:
        return _fail(repr(exc))


def spawn_ios(payload: dict[str, Any]) -> dict[str, Any]:
    raw_cmds = payload.get("cmds") or payload.get("codes")
    if isinstance(raw_cmds, str):
        cmds = [raw_cmds.strip()] if raw_cmds.strip() else []
    elif isinstance(raw_cmds, list):
        cmds = [str(c).strip() for c in raw_cmds if str(c).strip()]
    else:
        single = str(payload.get("cmd") or "").strip()
        cmds = [single] if single else []
    if not cmds:
        return _fail("Select at least one IO object to spawn.")
    try:
        count = max(1, min(int(payload.get("count") or 1), 999))
    except Exception:
        return _fail("count must be an integer.")
    _raise_spawn_caps()
    queued = 0
    last_msg = ""
    for cmd in cmds:
        for _ in range(count):
            result = spawn_io({**payload, "cmd": cmd})
            last_msg = str(result.get("message") or "")
            if not result.get("ok"):
                return _fail(f"Stopped after {queued} IO spawn(s): {last_msg}")
            queued += 1
    return _ok(f"Queued {queued} IO spawn(s) (×{count} each type).", queued=queued, count=count, detail=last_msg)


def spawn_encounter(payload: dict[str, Any]) -> dict[str, Any]:
    line = str(payload.get("line") or payload.get("cmd") or "").strip()
    if not line:
        return _fail("line required.")
    if not world_spawn.is_host():
        return _fail("Host / in-world session required for encounter spawn.")
    try:
        from .embedded_bms import get_controller

        controller = get_controller()
        _apply_bms_ui(controller, payload)
        ok, msg = controller.run_encounter_line(line, defer=True)
        return _ok(msg) if ok else _fail(msg)
    except Exception as exc:
        return _fail(repr(exc))


def bms_reaggro(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    if not world_spawn.is_host():
        return _fail("Host / in-world session required.")
    try:
        from .embedded_bms import get_controller

        controller = get_controller()
        ok, msg = controller.reaggro_tracked(defer=True)
        return _ok(msg) if ok else _fail(msg)
    except Exception as exc:
        return _fail(repr(exc))


def bms_clear(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    if not world_spawn.is_host():
        return _fail("Host / in-world session required.")
    try:
        from .embedded_bms import get_controller

        controller = get_controller()
        destroyed, failed = controller.clear_tracked()
        return _ok(f"Cleared tracked spawns: {destroyed} destroyed, {failed} failed.", destroyed=destroyed, failed=failed)
    except Exception as exc:
        return _fail(repr(exc))


def bms_activate_io(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    if not world_spawn.is_host():
        return _fail("Host / in-world session required.")
    try:
        from .embedded_bms import get_controller

        controller = get_controller()
        ok, msg = controller.activate_last_io()
        return _ok(msg) if ok else _fail(msg)
    except Exception as exc:
        return _fail(repr(exc))


def golden_chest(payload: dict[str, Any]) -> dict[str, Any]:
    from .golden_chest_keybinds import close_golden_chest, open_golden_chest

    action = str(payload.get("action") or "open").lower()
    if action == "close":
        ok, message = close_golden_chest()
        return _ok(message) if ok else _fail(message)
    ok, message = open_golden_chest()
    return _ok(message) if ok else _fail(message)


def _spawn_black_market_machine(
    payload: dict[str, Any],
    *,
    passes: int = 1,
) -> dict[str, Any]:
    spawn_payload = {
        **payload,
        "cmd": "oak_dual IO_VendingMachine_BlackMarket",
        "token": "IO_VendingMachine_BlackMarket",
        "activate": "yes",
    }
    msgs: list[str] = []
    ok_any = False
    n = max(1, int(passes))
    for pass_i in range(1, n + 1):
        spawned = spawn_io(spawn_payload)
        msgs.append(f"pass{pass_i}:{spawned.get('message') or spawned.get('ok')}")
        if spawned.get("ok"):
            ok_any = True
    return {"ok": ok_any, "message": " | ".join(msgs)}


def _clear_and_respawn_black_market(payload: dict[str, Any], idx: int) -> dict[str, Any]:
    """Write timer=ready, destroy nearby shop, respawn fresh."""
    return _destroy_and_respawn_black_market(payload, idx, clear_timer=True, reroll=False)


def _reroll_and_respawn_black_market(payload: dict[str, Any], idx: int) -> dict[str, Any]:
    """Destroy nearby shop, reroll stock RPC, respawn fresh."""
    return _destroy_and_respawn_black_market(payload, idx, clear_timer=False, reroll=True)


def _destroy_and_respawn_black_market(
    payload: dict[str, Any],
    idx: int,
    *,
    clear_timer: bool,
    reroll: bool,
) -> dict[str, Any]:
    from .spawn_deferred import pending_label_count

    pending = pending_label_count("Oak dual IO_VendingMachine_BlackMarket")
    if pending:
        return _fail(
            f"Black market machine is still setting up ({pending} step(s) remain); wait before respawning."
        )
    from .black_market import (
        apply_black_market,
        destroy_nearby_black_market_machines,
        read_shop_stock,
        read_state,
        request_ready_followup,
        reroll_black_market_parts,
    )

    if clear_timer:
        apply_black_market(
            idx,
            clear_cooldown=True,
            poke_machines=False,
            snapshot=False,
        )
    removed, remove_failed = destroy_nearby_black_market_machines()
    reroll_msg = ""
    if reroll:
        rolled = reroll_black_market_parts(idx)
        if not rolled.get("ok"):
            return _fail(
                f"Removed {removed} shop(s), but reroll failed: {rolled.get('message') or ''}"
            )
        reroll_msg = str(rolled.get("message") or "Reroll OK")
    request_ready_followup(idx, 10.0)
    # One dual queue after remove — a second pass would immediately duplicate the new shop.
    spawned = _spawn_black_market_machine(payload, passes=1)
    snap = read_state(idx)
    stock = read_shop_stock()
    if not spawned.get("ok"):
        label = "Cooldown clear" if clear_timer else "Reroll"
        return _fail(
            f"{label}: removed {removed} shop(s), but respawn failed. "
            + str(spawned.get("message") or "")
        )
    verb = "Purchase timer cleared" if clear_timer else "Stock rerolled"
    msg = f"{verb} — removed {removed} nearby shop(s), respawn queued."
    if reroll_msg:
        msg += f" {reroll_msg}"
    msg += " " + str(spawned.get("message") or "")
    if stock.get("ok"):
        msg += f" ({stock.get('message')})"
    return _ok(
        msg,
        cooldown=snap.get("cooldown"),
        visited=snap.get("visited"),
        removed=removed,
        remove_failed=remove_failed,
        serials=stock.get("serials"),
        slot_count=stock.get("slot_count"),
    )


def black_market(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .black_market import apply_black_market, read_state

    payload = payload or {}
    idx = _single_target_index(payload)
    action = str(payload.get("action") or "").strip().lower()

    if action in ("status", "read", ""):
        snap = read_state(idx)
        if not snap.get("ok"):
            return _fail(str(snap.get("message") or "Black market status failed."))
        from .black_market import read_shop_stock

        stock = read_shop_stock()
        serials = stock.get("serials") or []
        preview = " | ".join(str(s)[:28] for s in serials[:3])
        if len(serials) > 3:
            preview += f" … +{len(serials) - 3} more"
        msg = str(snap.get("message") or "")
        if stock.get("ok"):
            msg += f"; {stock.get('message')}"
            if preview:
                msg += f" [{preview}]"
        return _ok(
            msg,
            cooldown=snap.get("cooldown"),
            visited=snap.get("visited"),
            serials=serials,
            slot_count=stock.get("slot_count"),
            machine_path=stock.get("machine_path"),
        )

    if action in ("stock", "serials", "inventory"):
        from .black_market import read_shop_stock

        stock = read_shop_stock(prefer_world=bool(payload.get("world")))
        if not stock.get("ok"):
            return _fail(str(stock.get("message") or "Black market stock read failed."))
        return _ok(
            str(stock.get("message")),
            serials=stock.get("serials"),
            slot_count=stock.get("slot_count"),
            machine_path=stock.get("machine_path"),
            is_world_shop=stock.get("is_world_shop"),
        )

    if action in ("reroll", "reroll_parts", "shuffle"):
        return _reroll_and_respawn_black_market(payload, idx)

    if action in ("spawn", "spawn_machine", "machine"):
        from .black_market import destroy_nearby_black_market_machines, request_ready_followup
        from .spawn_deferred import pending_label_count

        pending = pending_label_count("Oak dual IO_VendingMachine_BlackMarket")
        if pending:
            return _ok(
                f"Black market machine is already setting up ({pending} step(s) remain). "
                "Wait ~10s, then try Spawn again."
            )

        apply_black_market(
            idx,
            clear_cooldown=True,
            poke_machines=False,
            snapshot=False,
        )
        destroy_nearby_black_market_machines()
        request_ready_followup(idx, 10.0)
        spawned = _spawn_black_market_machine(payload, passes=2)
        if not spawned.get("ok"):
            return _fail(
                str(spawned.get("message") or "Black market spawn failed.")
                + " Stand on flat ground in open space and retry."
            )
        return _ok(f"Spawn black market machine queued. {spawned.get('message')}")

    if action in ("cooldown", "clear", "clear_cooldown", "reset", "ready", "both"):
        return _clear_and_respawn_black_market(payload, idx)

    return _fail(
        "Unsupported black market action. Use spawn, cooldown, status, stock, or reroll."
    )


def mayhem_level(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .mayhem_level import apply_payload

    payload = dict(payload or {})
    if "player_index" not in payload and "index" not in payload:
        payload["player_index"] = _single_target_index(payload)
    result = apply_payload(payload)
    if result.get("ok"):
        return _ok(str(result.get("message") or "ok"), **{k: v for k, v in result.items() if k not in ("ok", "message")})
    return _fail(str(result.get("message") or "Mayhem write failed."))


def devperk_activate(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        perk_index = int(payload.get("perk_index"))
    except Exception:
        return _fail("perk_index required.")
    if perk_index == 7:
        from .dev_tools import loot_perk_batch_allowed

        if not loot_perk_batch_allowed():
            return _fail(
                "Spawn Legendary/Epic Loot is on cooldown — wait a second (spam freezes/crashes)."
            )
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    details: list[str] = []
    for idx in indices:
        try:
            details.append(activate_devperk(perk_index, player_index=idx))
            ok_n += 1
        except Exception as exc:
            details.append(f"index {idx}: {exc}")
    if ok_n == 0:
        return _fail("; ".join(details) or "Dev perk failed.")
    if len(indices) == 1:
        return _ok(details[0])
    return _ok(f"Dev perk applied to {ok_n}/{len(indices)} player(s).")


def shiny_drop_status_action(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .shinies import shiny_drop_status

    return _ok(shiny_drop_status() or "Idle.", status=shiny_drop_status())


def shiny_drop_all(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    busy = _progression_job_busy()
    if busy:
        return _fail(f"Drop All Shinies cannot start while {busy} is running.")
    try:
        from .uvhm_runtime import _is_host_tick_context  # noqa: PLC0415
        from .party_helpers import _gbc_is_listen_host_world, _gbc_session_world_and_gamestate

        world, _ = _gbc_session_world_and_gamestate()
        if not _gbc_is_listen_host_world(world):
            return _fail("Drop all shinies requires host / listen server — be session host, in-world, unpaused.")
    except Exception:
        pass
    try:
        level = int(payload.get("level") or DEFAULT_ITEM_LEVEL)
    except Exception:
        level = int(DEFAULT_ITEM_LEVEL)
    anchor = str(payload.get("spawn_anchor") or spawn_targets.mode() or "local").strip().lower()
    parsed = _payload_player_index(payload)
    idx = get_target_player_index() if parsed is None else int(parsed)
    where = spawn_targets.apply_from_payload(
        {"spawn_anchor": anchor, "player_index": idx},
        default_party_index=get_target_player_index(),
    )
    target_idx = idx if anchor == "party" and idx >= 0 else None
    shape = str(payload.get("shape") if payload.get("shape") is not None else "none").strip() or "none"
    from .loot_shapes import clamp_layout_params, normalize_drop_mode

    settle = normalize_drop_mode(payload.get("settle") if payload.get("settle") is not None else "none")
    layout = clamp_layout_params(
        radius=payload.get("radius", 300),
        spacing=payload.get("spacing", 90),
        line_length=payload.get("line_length", 520),
        drop_height=payload.get("drop_height", 440),
    )
    drop_height = float(layout["drop_height"])
    line_length = float(layout["line_length"])
    radius = float(layout["radius"])
    spacing = float(layout["spacing"])
    try:
        land = _loot_landing_kwargs(payload)
        count = drop_all_shinies(
            level=level,
            target_party_index=target_idx,
            shape=str(land.get("shape") or "none"),
            settle=str(land.get("settle") or "none"),
            drop_height=float(land.get("drop_height") or 440),
            line_length=float(land.get("line_length") or 520),
            radius=float(land.get("radius") or 300),
            spacing=float(land.get("spacing") or 90),
            spawn_then_shape=bool(land.get("spawn_then_shape")),
            stay_in_air=bool(land.get("stay_in_air", True)),
            float_on_grab=bool(land.get("float_on_grab", False)),
            peel_after=float(land.get("peel_after") or 0),
            land_profile=str(land.get("land_profile") or "shiny"),
            fill_until_complete=bool(land.get("fill_until_complete")),
            shape_text=str(land.get("shape_text") or ""),
        )
    except Exception as exc:
        return _fail(str(exc))
    return _ok(
        f"Queued {count} Shiny-eligible pool call(s) near {where} → {shape} ({settle}). "
        "Stay host and unpaused until the queue finishes; Shiny rarity still needs loaded unlocks.",
        count=count,
    )


def spawn_text_shape(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """EXE Shapes → Loot text: 3-line world-style lettering made of loot."""
    payload = dict(payload or {})
    from .loot_shapes import (  # noqa: PLC0415
        get_text_layout,
        sanitize_shape_text,
        set_text_layout,
        text_shape_slot_count,
    )

    text = set_text_layout(
        row1=payload.get("row1", ""),
        row2=payload.get("row2", ""),
        row3=payload.get("row3", ""),
        text=payload.get("text") or payload.get("shape_text"),
        distance=payload.get("distance"),
        height=payload.get("height"),
        spacing=payload.get("spacing"),
        scale=payload.get("scale"),
    )
    layout = get_text_layout()
    if not sanitize_shape_text(text):
        return _fail("Enter Line 1–3 (A-Z, 0-9), like World text.")
    source = str(payload.get("source") or "shiny").strip().lower()
    try:
        level = int(payload.get("level") or DEFAULT_ITEM_LEVEL)
    except Exception:
        level = int(DEFAULT_ITEM_LEVEL)
    is_shiny = source in ("shiny", "shinies")
    # Soft fit only — glyph pitch comes from set_text_layout, not land radius.
    fit_r = max(220.0, min(400.0, float(layout["distance"]) * 0.55))
    land = {
        "shape": "text",
        "shape_text": text,
        "text": text,
        "settle": str(payload.get("settle") or "slow"),
        "radius": payload.get("radius", fit_r),
        "spacing": payload.get("spacing", layout["spacing"]),
        "drop_height": payload.get("drop_height", 200),
        "line_length": payload.get("line_length", 520),
        "z_bias": payload.get("z_bias", 12),
        "stay_in_air": payload.get("stay_in_air", "yes"),
        "float_on_grab": payload.get("float_on_grab", "no"),
        "peel_after": payload.get("peel_after", 0),
        # One gun per glyph pixel (pad short shiny lists; trim overflow in drop queue).
        "fill_until_complete": True,
        "land_profile": "shiny" if is_shiny else "bulk",
        "spawn_anchor": payload.get("spawn_anchor") or "local",
        "player_index": payload.get("player_index"),
        "level": level,
    }
    if is_shiny:
        return shiny_drop_all(land)
    pool = str(payload.get("itempool") or payload.get("pool") or "itempool_ar_05_legendary").strip()
    entry = _resolve_item_pool_entry({"itempool": pool, "display_name": pool})
    if entry is None:
        entry = {"itempool": pool, "display_name": pool}
    want = max(1, int(text_shape_slot_count(text, profile="bulk")))
    where = spawn_targets.apply_from_payload(land, default_party_index=get_target_player_index())
    try:
        queue_item_pool_entry(
            entry,
            level=level,
            count=want,
            **{k: v for k, v in _loot_landing_kwargs(land).items() if k != "fill_until_complete"},
            fill_until_complete=False,
        )
    except Exception as exc:
        return _fail(repr(exc))
    return _ok(
        f"Queued ~{want} item(s) as loot text '{text}' from {pool} near {where}.",
        text=text,
        queued=want,
        itempool=pool,
        **{k: layout[k] for k in ("row1", "row2", "row3", "distance", "height", "spacing", "scale")},
    )

def shiny_mail_all(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .shinies import grant_all_shiny_serials

    payload = payload or {}
    mode = str(payload.get("mode") or "selected").strip().lower()
    player_index = _payload_player_index(payload)
    # Boost target All (-1) must mail the whole lobby even when mode is "selected".
    all_players = mode in {"all", "lobby", "everyone", "party"} or (
        player_index is not None and int(player_index) < 0
    ) or (player_index is None and get_target_player_index() < 0)
    if all_players:
        count = grant_all_shiny_serials(all_players=True)
        return _ok(f"Queued {count} shiny @U serial(s) via mailbox (entire lobby).", count=count)
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    count = grant_all_shiny_serials(all_players=False, player_indices=indices)
    if len(indices) == 1:
        scope = f"target player index {indices[0]}"
    else:
        scope = f"{len(indices)} boost targets"
    return _ok(f"Queued {count} shiny @U serial(s) via mailbox ({scope}).", count=count)


def kill_all_enemies(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .dev_tools import _gameplay_pc, activate_devperk_on_pc

    pc = _gameplay_pc()
    if pc is None:
        return _fail("No local PlayerController (run on host).")
    return _ok(activate_devperk_on_pc(3, pc))


def vehicle_actions_locked(payload: dict[str, Any]) -> dict[str, Any]:
    from .dev_tools import set_vehicle_actions_locked

    locked = bool(payload.get("locked", True))
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    details: list[str] = []
    for idx in indices:
        try:
            details.append(set_vehicle_actions_locked(locked, player_index=idx))
            ok_n += 1
        except Exception as exc:
            details.append(f"index {idx}: {exc}")
    if ok_n == 0:
        return _fail("; ".join(details) or "Vehicle lock failed.")
    if len(indices) == 1:
        return _ok(details[0])
    return _ok(f"Vehicle lock applied to {ok_n}/{len(indices)} player(s).")


def rarity_weights_set(payload: dict[str, Any]) -> dict[str, Any]:
    payload = payload or {}
    preset = str(payload.get("preset") or "").lower()
    if preset == "reset":
        rarity_weights.reset_all()
        msg = rarity_weights.apply_modifiers(log_result=True)
        return _ok(msg, weights=rarity_weights.weights_snapshot())
    if preset in ("legendary", "pearlescent", "pearlescent", "pearl"):
        key = "legendary" if preset == "legendary" else "pearlescent"
        rarity_weights.set_only(key)
        msg = rarity_weights.apply_modifiers(log_result=True)
        return _ok(msg, weights=rarity_weights.weights_snapshot())
    keys = {row[0] for row in rarity_weights.RARITY_ROWS}
    if any(k in payload and str(payload.get(k) or "").strip() != "" for k in keys):
        msg = rarity_weights.set_from_payload(payload)
        return _ok(msg, weights=rarity_weights.weights_snapshot())
    if preset in ("apply", "set", ""):
        msg = rarity_weights.apply_modifiers(log_result=True)
        return _ok(msg, weights=rarity_weights.weights_snapshot())
    return _fail("preset must be legendary, pearlescent, reset, or send slider values.")


def loot_feed_appear(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import loot_feed as feed

    payload = payload or {}
    kind = str(payload.get("kind") or payload.get("appear") or "").strip()
    msg = feed.appear(kind)
    low = str(msg or "").lower()
    if (
        not msg
        or low.startswith("pick a ")
        or " not available" in low
        or " missing" in low
        or "could not" in low
        or "failed" in low
        or "error" in low
        or ": " in low and not low.endswith("played.")
    ):
        if low.endswith("played."):
            return _ok(msg)
        return _fail(msg or "Loot feed appear failed.")
    return _ok(msg)


def god_mode(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .dev_tools import set_god_mode

    payload = payload or {}
    enabled = bool(payload.get("enabled", True))
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    details: list[str] = []
    for idx in indices:
        try:
            details.append(set_god_mode(enabled, player_index=idx))
        except Exception as exc:
            details.append(f"index {idx}: {exc}")
    ok_n = sum(1 for d in details if "ON" in d or "OFF" in d)
    if ok_n <= 0:
        return _fail("; ".join(details) or "God Mode failed.")
    return _ok(
        f"God Mode {'ON' if enabled else 'OFF'} ({ok_n}).",
        god_mode=enabled,
        details=details,
    )


def infinite_ammo(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .dev_tools import set_infinite_ammo

    payload = payload or {}
    enabled = bool(payload.get("enabled", True))
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    details: list[str] = []
    for idx in indices:
        try:
            details.append(set_infinite_ammo(enabled, player_index=idx))
        except Exception as exc:
            details.append(f"index {idx}: {exc}")
    ok_n = sum(1 for d in details if "ON" in d or "OFF" in d or "already" in d.lower())
    if ok_n <= 0:
        return _fail("; ".join(details) or "Infinite Ammo failed.")
    return _ok(
        f"Infinite Ammo {'ON' if enabled else 'OFF'} ({ok_n}).",
        infinite_ammo=enabled,
        details=details,
    )


def pawn_no_target(payload: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(payload.get("enabled", True))
    try:
        from . import mobility_runtime

        msg = mobility_runtime.set_no_target_enabled(enabled)
        return _ok(msg, no_target=bool(mobility_runtime.no_target_enabled()))
    except Exception as exc:
        return _fail(str(exc))


def pawn_gravity(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        scale = float(payload.get("scale") or 1.0)
    except Exception:
        return _fail("scale must be a number.")
    mobility_runtime.gravity_scale = max(0.0, min(10.0, scale))
    mobility_runtime.schedule_debounced_apply("gravity")
    return _ok(f"Gravity scale {scale}.")


def weapons_restricted(payload: dict[str, Any]) -> dict[str, Any]:
    restricted = bool(payload.get("restricted", True))
    sticky = bool(payload.get("sticky", True))
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    details: list[str] = []
    for idx in indices:
        try:
            if sticky:
                from .dev_tools import set_weapons_restricted_sticky

                details.append(set_weapons_restricted_sticky(restricted, player_index=idx))
            else:
                details.append(set_weapons_restricted(restricted, player_index=idx))
            ok_n += 1
        except Exception as exc:
            details.append(f"index {idx}: {exc}")
    if ok_n <= 0:
        return _fail("; ".join(details) or "Weapons restricted failed.")
    return _ok(
        f"Weapons restricted {'ON' if restricted else 'OFF'} ({ok_n}).",
        weapons_restricted=restricted,
        details=details,
    )


def ammo_regen(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        rate = float(payload.get("rate") or 0.0)
    except Exception:
        return _fail("rate must be a number.")
    sticky = bool(payload.get("sticky", True))
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    details: list[str] = []
    for idx in indices:
        try:
            if sticky:
                from .dev_tools import set_ammo_regen_sticky

                details.append(set_ammo_regen_sticky(rate, player_index=idx))
            else:
                details.append(set_ammo_regen_rate(rate, player_index=idx))
            ok_n += 1
        except Exception as exc:
            details.append(f"index {idx}: {exc}")
    if ok_n == 0:
        return _fail("; ".join(details) or "Ammo regen failed.")
    return _ok(
        details[0] if len(indices) == 1 else f"Ammo regen applied to {ok_n}/{len(indices)} player(s).",
        ammo_regen=rate > 0.0,
        rate=rate,
        details=details,
    )


def teleport_party(payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "").lower()
    if mode in ("all_to_me", "everyone_to_me", "lobby_to_me"):
        try:
            rows = list(_list_party_players() or [])
        except Exception:
            rows = []
        if not rows:
            return _fail("No party members found.")
        local_idx = mobility_runtime.local_party_index()
        if local_idx is None:
            local_idx = 0
        moved = 0
        for row in rows:
            try:
                slot = int(row[0])
            except Exception:
                continue
            if slot == int(local_idx):
                continue
            try:
                mobility_runtime.teleport_party_slot_to_local(slot)
                moved += 1
            except Exception:
                continue
        if moved <= 0:
            return _fail("No other players to teleport (solo lobby?).")
        return _ok(f"Teleported {moved} player(s) to you.")
    parsed = _payload_player_index(payload)
    idx = get_target_player_index() if parsed is None else int(parsed)
    if idx < 0:
        return _fail("Pick a single player to teleport (All players is not valid).")
    who = ""
    try:
        for row in _list_party_players():
            if int(row[0]) == int(idx):
                who = str(row[1] or "").strip()
                break
    except Exception:
        who = ""
    label = who or f"player #{idx}"
    if mode in ("me_to_selected", "local_to_selected"):
        mobility_runtime.teleport_local_to_selected(idx)
        return _ok(f"Teleported you to {label}.")
    if mode in ("selected_to_me", "selected_to_local"):
        mobility_runtime.teleport_selected_to_local(idx)
        return _ok(f"Teleported {label} to you.")
    return _fail("mode must be all_to_me, me_to_selected, or selected_to_me.")


def mobility_preset_apply(payload: dict[str, Any]) -> dict[str, Any]:
    preset = str(payload.get("preset") or "fast").lower()
    if preset == "reset":
        mobility_runtime.reset_all()
        return _ok("Mobility reset.")
    if preset == "fast":
        mobility_runtime.apply_preset(
            speed=3.0,
            walk=2200.0,
            jump=480.0,
            glide_s=2200.0,
            glide_b=3600.0,
            glide_air=6.0,
            dash=2400.0,
            zero_vault=True,
        )
        return _ok("Applied Fast mobility preset.")
    if preset == "moon":
        mobility_runtime.apply_preset(
            speed=mobility_runtime.speed_scale,
            walk=mobility_runtime.walk_speed,
            jump=900.0,
            gravity=0.45,
            zero_vault=True,
        )
        return _ok("Applied Moon mobility preset.")
    if preset in ("wall_walk", "wallwalk"):
        mobility_runtime.apply_preset(
            speed=max(mobility_runtime.speed_scale, 3.0),
            walk=max(mobility_runtime.walk_speed, 2200.0),
            jump=mobility_runtime.jump_goal,
            step=700.0,
            floor_angle=89.9,
            zero_vault=True,
        )
        return _ok("Applied Wall Walk mobility preset.")
    return _fail("preset must be fast, moon, wall_walk, or reset.")


def character_flag(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import character_flags as flags

    payload = payload or {}
    flag = str(payload.get("flag") or "").strip().lower()
    if "enabled" in payload:
        enabled = _as_bool(payload.get("enabled"), True)
    else:
        idx = _single_target_index(payload)
        enabled = not flags.is_on(flag, idx)
    indices = _boost_targets_from_payload(payload)
    return _ok(flags.set_flag(flag, indices, enabled))


def lab_intrinsic_element(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import character_flags as flags

    payload = payload or {}
    try:
        option = int(payload.get("option") if payload.get("option") not in (None, "") else 1)
    except Exception:
        option = 1
    try:
        element = int(payload.get("element") if payload.get("element") not in (None, "") else 0)
    except Exception:
        element = 0
    barrel = str(payload.get("barrel_compat") or "").strip().lower()
    barrel_compat = None
    if barrel in ("1", "true", "yes", "on"):
        barrel_compat = True
    elif barrel in ("0", "false", "no", "off"):
        barrel_compat = False
    indices = _boost_targets_from_payload(payload)
    return _ok(
        flags.set_intrinsic_element(
            indices,
            option=option,
            element=element,
            barrel_compat=barrel_compat,
        )
    )


def mobility_infinite_jump(payload: dict[str, Any]) -> dict[str, Any]:
    scope = str(payload.get("scope") or "target").lower()
    if "enabled" in payload:
        enabled = _as_bool(payload.get("enabled"), True)
    elif scope == "all":
        # Prefer the sticky all-mode flag so a brief empty roster cannot flip ON→OFF.
        all_on = bool(getattr(mobility_runtime, "_infinite_jump_all_mode", False)) or bool(
            mobility_runtime.infinite_jump_indices
        )
        enabled = not all_on
    else:
        idx_probe = mobility_runtime.normalize_mobility_target_index(_single_target_index(payload))
        enabled = int(idx_probe) not in mobility_runtime.infinite_jump_indices
    if scope == "all":
        mobility_runtime.set_infinite_jump_all(enabled)
        return _ok(
            f"Infinite jump {'ON' if enabled else 'OFF'} for all.",
            infinite_jump_on=enabled,
            infinite_jump_scope="all",
        )
    idx = mobility_runtime.normalize_mobility_target_index(_single_target_index(payload))
    mobility_runtime.set_infinite_jump_for_index(idx, enabled)
    who = ""
    try:
        for row_idx, name in _list_party_players():
            if int(row_idx) == int(idx):
                who = str(name or "").strip()
                break
    except Exception:
        who = ""
    label = who or f"player #{idx}"
    return _ok(
        f"Infinite jump {'ON' if enabled else 'OFF'} for {label}.",
        infinite_jump_on=enabled,
        infinite_jump_scope="target",
    )


def _apply_fly_speed_from_payload(payload: dict[str, Any]) -> float:
    """Preset vs custom — custom mode always uses the number field."""
    mode = str(payload.get("fly_speed_mode") or "preset").strip().lower()
    if mode == "custom":
        return mobility_runtime.set_force_fly_speed_value(
            payload.get("fly_speed"),
            preset="custom",
        )
    preset = payload.get("fly_preset") or mobility_runtime.force_fly_preset or "fast"
    return float(mobility_runtime.apply_fly_preset(preset, prefer_preset=True))


def mobility_force_fly(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("apply_speed_only") or payload.get("reapply_only"):
        try:
            applied_speed = _apply_fly_speed_from_payload(payload)
        except Exception:
            applied_speed = float(mobility_runtime.force_fly_speed)
            if "fly_speed" in payload:
                try:
                    applied_speed = mobility_runtime.set_force_fly_speed_value(
                        payload["fly_speed"],
                        preset="custom",
                    )
                except Exception:
                    pass
        count = mobility_runtime.reapply_all_force_fly() if mobility_runtime.force_fly_targets else 0
        speed = float(applied_speed)
        mode = str(payload.get("fly_speed_mode") or "preset").strip().lower()
        if mode == "custom":
            label = f"custom {speed:.0f}"
        else:
            label = f"{mobility_runtime.force_fly_preset} ({speed:.0f})"
        try:
            from ._mod_version import __version__ as _mod_ver
        except Exception:
            _mod_ver = "?"
        speed_line = f"ACTIVE fly speed: {speed:.0f} ({label}) [mod {_mod_ver}]"
        if count:
            return _ok(
                f"{speed_line}. Already flying — hold WASD to move.",
                fly_speed=speed,
                fly_preset=str(mobility_runtime.force_fly_preset),
                reapplied=count,
            )
        return _ok(
            f"{speed_line}. Turn Force fly ON, then hold WASD.",
            fly_speed=speed,
            fly_preset=str(mobility_runtime.force_fly_preset),
            reapplied=0,
        )
    scope = str(payload.get("scope") or "target").lower()
    idx = mobility_runtime.normalize_mobility_target_index(_single_target_index(payload))
    want_all = scope == "all" or int(_single_target_index(payload)) < 0
    if "enabled" in payload:
        enabled = _as_bool(payload.get("enabled"), True)
    elif want_all:
        enabled = not mobility_runtime.force_fly_enabled_for_index(-1)
    else:
        enabled = not mobility_runtime.force_fly_enabled_for_index(idx)
    # Preset/custom from the EXE fields must apply on toggle too — not only "Apply fly speed".
    if enabled or payload.get("fly_preset") or payload.get("fly_speed") is not None:
        try:
            _apply_fly_speed_from_payload(payload)
        except Exception:
            pass
    if want_all:
        mobility_runtime.set_force_fly_all(enabled)
    else:
        mobility_runtime.set_force_fly_for_index(idx, enabled)
    if enabled and mobility_runtime.force_fly_targets:
        mobility_runtime.reapply_all_force_fly()
    speed = float(mobility_runtime.force_fly_speed)
    preset = str(getattr(mobility_runtime, "force_fly_preset", "fast"))
    if want_all:
        return _ok(
            f"Force fly {'ON' if enabled else 'OFF'} for you at {preset} ({speed:.0f}). "
            + ("Hold WASD to move." if enabled else ""),
            fly_speed=speed,
            fly_preset=preset,
            force_fly_on=enabled,
            force_fly_scope="all",
        )
    return _ok(
        f"Force fly {'ON' if enabled else 'OFF'} — {preset} ({speed:.0f}). "
        + ("Hold WASD to move." if enabled else ""),
        fly_speed=speed,
        fly_preset=preset,
        force_fly_on=enabled,
        force_fly_scope="target",
    )


def bvm_vehicle_jump(payload: dict[str, Any]) -> dict[str, Any]:
    """EXE vehicle-jump toggle / test. Sit in a vehicle first."""
    from . import tuning_embed as te

    try:
        eng = te.get_engine("bvm")
    except Exception as exc:
        return _fail(str(exc))
    action = str(payload.get("action") or "").strip().lower()
    if action == "test":
        try:
            n = int(eng._apply_custom_vehicle_jump(log_result=True) or 0)
        except Exception as exc:
            return _fail(str(exc))
        if n <= 0:
            return _fail("Vehicle jump failed — sit in a vehicle first.")
        return _ok("Vehicle jump fired.")
    interval = payload.get("interval")
    if interval is None:
        interval = payload.get("bvm_jump_repeat_interval")
    if interval is not None:
        try:
            eng._jump_repeat_interval_opt.value = max(0.08, min(1.0, float(interval)))
        except Exception:
            pass
    if "enabled" not in payload:
        return _fail("enabled or action=test is required.")
    enabled = _as_bool(payload.get("enabled"), False)
    try:
        eng._repeat_jump_press_opt.value = enabled
    except Exception as exc:
        return _fail(str(exc))
    return _ok("Unlimited vehicle jumps ON." if enabled else "Unlimited vehicle jumps OFF.")


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return default


def _apply_mobility_fields(payload: dict[str, Any]) -> None:
    floats = {
        "speed_scale": "speed_scale",
        "walk_speed": "walk_speed",
        "jump_goal": "jump_goal",
        "gravity_scale": "gravity_scale",
        "max_step_height": "max_step_height",
        "walkable_floor_angle": "walkable_floor_angle",
        "walkable_floor_z": "walkable_floor_z",
        "glide_speed": "glide_speed",
        "glide_boost": "glide_boost",
        "glide_air_control": "glide_air_control",
        "dash_speed": "dash_speed",
    }
    for key, attr in floats.items():
        if key not in payload:
            continue
        try:
            setattr(mobility_runtime, attr, float(payload[key]))
        except Exception:
            pass
    if "zero_vault_costs" in payload:
        mobility_runtime.zero_vault_costs = _as_bool(payload.get("zero_vault_costs"), True)
    if "fly_speed" in payload:
        try:
            mobility_runtime.force_fly_speed = mobility_runtime.clamp_force_fly_speed(payload["fly_speed"])
        except Exception:
            pass


def mobility_apply(payload: dict[str, Any]) -> dict[str, Any]:
    if not mobility_runtime.is_listen_host():
        return _fail("Host session required for mobility apply.")
    _apply_mobility_fields(payload)
    mobility_runtime.apply_all()
    if "fly_speed" in payload and mobility_runtime.force_fly_targets:
        mobility_runtime.reapply_all_force_fly()
    msg = str(mobility_runtime.status_message or "Mobility applied.")
    values = mobility_runtime.preset_dict()
    values["fly_speed"] = float(mobility_runtime.force_fly_speed)
    return _ok(msg, values=values, current=values)


def mobility_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    current = mobility_runtime.preset_dict()
    current["fly_speed"] = float(mobility_runtime.force_fly_speed)
    return _ok(
        str(mobility_runtime.status_message or "Mobility status."),
        current=current,
        values=current,
        defaults={
            k: mobility_runtime.DEFAULT_PRESET[k]
            for k in current
            if k in mobility_runtime.DEFAULT_PRESET
        },
        time_dilation=float(mobility_runtime.time_dilation),
        noclip=bool(mobility_runtime.get_noclip_enabled()),
        fall_through_map=bool(mobility_runtime.get_fall_through_map_enabled()),
        auto_apply_on_load=bool(mobility_runtime.get_auto_apply_on_load()),
        infinite_jump=sorted(int(x) for x in mobility_runtime.infinite_jump_indices),
        infinite_jump_label=mobility_runtime.enabled_infinite_names(),
        fly_speed=float(mobility_runtime.force_fly_speed),
    )


def vehicle_spawn(payload: dict[str, Any]) -> dict[str, Any]:
    from . import vehicle_spawn_bridge as vspawn

    entry = vspawn.resolve_entry(
        vehicle=str(payload.get("vehicle") or payload.get("pick") or payload.get("label") or ""),
        vehicle_id=str(payload.get("vehicle_id") or payload.get("id") or ""),
    )
    if entry is None:
        return _fail("Select a vehicle from the catalog first.")
    try:
        ok = vspawn.spawn_entry(entry)
    except Exception as exc:
        return _fail(repr(exc))
    label = str(entry.get("label") or entry.get("id") or "vehicle")
    return _ok(f"Spawn requested: {label}.", vehicle=label) if ok else _fail(f"Spawn failed for {label}.")


def vehicle_spawn_catalog_reload(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import vehicle_spawn_bridge as vspawn

    payload = payload or {}
    try:
        count = vspawn.reload_catalog(deep=bool(payload.get("deep", True)))
    except Exception as exc:
        return _fail(repr(exc))
    return _ok(f"Reloaded {count} vehicle spawn entries.", count=count)


def mobility_save_preset(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    mobility_runtime.save_current_preset()
    return _ok(str(mobility_runtime.status_message or "Saved mobility preset."))


def mobility_load_preset(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    apply_now = _as_bool(payload.get("apply_now"), True)
    mobility_runtime.load_saved_preset(apply_now=apply_now)
    return _ok(
        str(mobility_runtime.status_message or "Loaded mobility preset."),
        values=mobility_runtime.preset_dict(),
        applied=apply_now,
    )


def mobility_zero_vault(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    mobility_runtime.zero_vault_now()
    return _ok(str(mobility_runtime.status_message or "Zero vault costs applied."))


def mobility_noclip(payload: dict[str, Any]) -> dict[str, Any]:
    enabled = _as_bool(payload.get("enabled"), True)
    mobility_runtime.set_noclip_enabled(enabled)
    mobility_runtime.apply_noclip()
    return _ok(
        str(mobility_runtime.status_message or f"Noclip {'ON' if enabled else 'OFF'}."),
        noclip=bool(mobility_runtime.get_noclip_enabled()),
        fall_through_map=bool(mobility_runtime.get_fall_through_map_enabled()),
        force_fly=bool(mobility_runtime.force_fly_enabled_for_index(0)),
    )


def faafo_fall_through_map(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    enabled = _as_bool(payload.get("enabled"), True)
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    details: list[str] = []
    for idx in indices:
        try:
            msg = mobility_runtime.set_fall_through_for_index(int(idx), bool(enabled))
            details.append(msg)
            lower = str(msg).lower()
            if "failed" in lower:
                continue
            ok_n += 1
        except Exception as exc:
            details.append(f"index {idx}: {exc}")
    if ok_n == 0:
        return _fail("; ".join(details) or "Fall through map failed.")
    sticky = any(mobility_runtime.fall_through_enabled_for_index(i) for i in indices)
    if len(indices) == 1:
        return _ok(
            details[0],
            fall_through_map=sticky,
            noclip=bool(mobility_runtime.get_noclip_enabled()),
        )
    return _ok(
        f"Fall through map {'ON' if enabled else 'OFF'} for {ok_n}/{len(indices)} player(s).",
        fall_through_map=sticky,
        noclip=bool(mobility_runtime.get_noclip_enabled()),
    )


def mobility_time(payload: dict[str, Any]) -> dict[str, Any]:
    if _as_bool(payload.get("reset")):
        mobility_runtime.reset_time()
        return _ok("Time dilation reset to normal.")
    try:
        mobility_runtime.time_dilation = max(0.0, min(64.0, float(payload.get("dilation") or 1.0)))
    except Exception:
        return _fail("dilation must be a number.")
    mobility_runtime.set_time()
    return _ok(f"Time dilation set to {mobility_runtime.time_dilation:.2f}x.")


def mobility_auto_apply(payload: dict[str, Any]) -> dict[str, Any]:
    enabled = _as_bool(payload.get("enabled"), False)
    mobility_runtime.set_auto_apply_on_load(enabled)
    return _ok(f"Auto-apply on load {'ON' if enabled else 'OFF'}.")


def mobility_players_only(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    mobility_runtime.toggle_players_only()
    return _ok(str(mobility_runtime.status_message or "Toggled players-only mode."))


def mobility_delete_ground(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    mobility_runtime.delete_ground_loot()
    return _ok(str(mobility_runtime.status_message or "Delete ground items requested."))


def loot_shape_place_fully(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    busy = _progression_job_busy()
    if busy:
        return _fail(f"Place Fully cannot start while {busy} is running.")
    msg = loot_shapes.arrange_from_payload(payload or {}, mode="place_fully")
    return _ok(msg, summary=loot_shapes.get_last_layout_summary())


def loot_shape_arrange(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    msg = loot_shapes.arrange_from_payload(payload or {}, mode="quick")
    return _ok(msg, summary=loot_shapes.get_last_layout_summary())


def loot_shape_clear(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    return _ok(loot_shapes.soft_clear_ground_loot())


def loot_cleanup(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    return _ok(loot_shapes.cleanup_world_loot())


def loot_gather_nearby(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import loot_coil

    payload = payload or {}
    try:
        max_items = int(payload.get("max_items") or payload.get("count") or 400)
    except Exception:
        max_items = 400
    scope = str(payload.get("scope") or payload.get("reel_scope") or "me")
    try:
        radius_m = float(payload.get("radius_m") or payload.get("radius") or 0)
    except Exception:
        radius_m = 0.0
    idx = _payload_player_index(payload)
    return _ok(
        loot_coil.reel_ground_loot(
            max_items=max_items,
            scope=scope,
            radius_m=radius_m,
            player_index=idx,
        )
    )


def loot_vacuum_nearby(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fast snap nearby ground loot to feet (not backpack / not mail)."""
    from . import loot_coil

    payload = payload or {}
    try:
        max_items = int(payload.get("max_items") or payload.get("count") or 200)
    except Exception:
        max_items = 200
    scope = str(payload.get("scope") or payload.get("reel_scope") or "me")
    try:
        if payload.get("radius_m") is not None:
            radius_m = float(payload.get("radius_m"))
        elif payload.get("radius") is not None:
            radius_m = float(payload.get("radius"))
        else:
            radius_m = 40.0
    except Exception:
        radius_m = 40.0
    idx = _payload_player_index(payload)
    msg = loot_coil.start_vacuum(
        max_items=max_items,
        scope=scope,
        radius_m=radius_m,
        player_index=idx,
    )
    st = loot_coil.vacuum_status()
    low = str(msg).lower()
    if any(
        bit in low
        for bit in (
            "needs the listen host",
            "wait until",
            "no ground loot",
            "no live pawn",
            "could not read",
        )
    ):
        return _fail(msg, vacuum=st)
    return _ok(msg, vacuum=st)


def loot_vacuum_cancel(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import loot_coil

    del _payload
    return _ok(loot_coil.cancel_vacuum(), vacuum=loot_coil.vacuum_status())


def loot_vacuum_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import loot_coil

    del _payload
    st = loot_coil.vacuum_status()
    return _ok(str(st.get("message") or "Loot vacuum idle."), vacuum=st)


def guest_map_assist_start(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import map_party_escort

    payload = payload or {}
    try:
        hops = int(payload.get("hops") or 6)
    except Exception:
        hops = 6
    try:
        radius = float(payload.get("radius") or 12000)
    except Exception:
        radius = 12000.0
    all_guests = bool(payload.get("all_guests") or payload.get("all") or payload.get("party"))
    if all_guests and not bool(payload.get("confirmed", False)):
        return _fail("Confirmation required to escort all guests.")
    idx = _single_target_index(payload) if not all_guests else None
    msg = map_party_escort.start(
        player_index=idx,
        all_guests=all_guests,
        hops=hops,
        radius=radius,
    )
    st = map_party_escort.status()
    if not st.get("active"):
        return _fail(msg, escort=st)
    return _ok(msg, escort=st)


def guest_map_assist_cancel(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import map_party_escort

    del _payload
    return _ok(map_party_escort.cancel(), escort=map_party_escort.status())


def guest_map_assist_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import map_party_escort

    del _payload
    st = map_party_escort.status()
    return _ok(str(st.get("message") or "Guest map assist status."), escort=st)


def warp_mark_save(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import warp_marks

    payload = payload or {}
    name = str(payload.get("name") or payload.get("label") or "Mark").strip()
    try:
        return _ok(warp_marks.save_mark(name), marks=warp_marks.list_marks())
    except Exception as exc:
        return _fail(str(exc))


def warp_mark_go(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import warp_marks

    payload = payload or {}
    name = str(payload.get("name") or payload.get("label") or "").strip()
    if not name:
        rows = warp_marks.list_marks()
        if not rows:
            return _fail("No warp marks saved yet.")
        name = str(rows[0].get("name") or "")
    try:
        return _ok(warp_marks.go_mark(name))
    except Exception as exc:
        return _fail(str(exc))


def warp_mark_delete(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import warp_marks

    payload = payload or {}
    name = str(payload.get("name") or payload.get("label") or "").strip()
    if not name:
        return _fail("Pick a warp mark name to delete.")
    try:
        return _ok(warp_marks.delete_mark(name), marks=warp_marks.list_marks())
    except Exception as exc:
        return _fail(str(exc))


def warp_mark_list(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import warp_marks

    del _payload
    rows = warp_marks.list_marks()
    return _ok(f"{len(rows)} warp mark(s).", marks=rows)


def host_map_sweep_start(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import map_scout

    payload = payload or {}
    try:
        # Keep 0 as "all main POIs" — do not use `or 8` (0 is valid).
        raw_hops = payload.get("hops")
        hops = int(raw_hops) if raw_hops is not None else 0
    except Exception:
        hops = 0
    try:
        radius = float(payload.get("radius") if payload.get("radius") is not None else 0)
    except Exception:
        radius = 0.0
    mode = str(payload.get("mode") or payload.get("sweep_mode") or "poi").strip().lower()
    msg = map_scout.start(hops=hops, radius=radius, mode=mode)
    st = map_scout.status()
    if not st.get("active") and "armed" not in msg.lower():
        return _fail(msg, scout=st)
    return _ok(msg, scout=st)


def host_map_sweep_cancel(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import map_scout

    del _payload
    return _ok(map_scout.cancel(), scout=map_scout.status())


def host_map_sweep_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import map_scout

    del _payload
    st = map_scout.status()
    return _ok(str(st.get("message") or "Host map sweep status."), scout=st)


# Legacy bridge action IDs (EXE macros, old keybind saves).
loot_coil_reel = loot_gather_nearby
map_party_escort_start = guest_map_assist_start
map_party_escort_cancel = guest_map_assist_cancel
map_party_escort_status = guest_map_assist_status
map_scout_start = host_map_sweep_start
map_scout_cancel = host_map_sweep_cancel
map_scout_status = host_map_sweep_status


def loot_shape_reapply(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    return _ok(loot_shapes.reapply_last_layout(), summary=loot_shapes.get_last_layout_summary())


def loot_shape_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    return _ok(
        loot_shapes.get_status(),
        summary=loot_shapes.get_last_layout_summary(),
        shapes=list(loot_shapes.SHAPE_NAMES),
    )


def loot_shape_stop_drop(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    return _ok(loot_shapes.finish_drop_jobs(), summary=loot_shapes.get_last_layout_summary())


def map_fog_hide(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import map_fog_hide as fog

    payload = payload or {}
    if "enabled" in payload:
        enabled = bool(payload.get("enabled"))
    else:
        enabled = not fog.is_hidden()
    msg = fog.set_hidden(enabled)
    return _ok(msg, hidden=fog.is_hidden())


def hold_session(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import hold_session as hold

    payload = payload or {}
    if "enabled" in payload:
        enabled = bool(payload.get("enabled"))
    else:
        enabled = not hold.is_enabled()
    before = hold.is_enabled()
    msg = hold.set_enabled(enabled)
    after = hold.is_enabled()
    if enabled and not after:
        return _fail(msg or "No main menu needs the listen-server host.", enabled=False)
    if (not enabled) and before and after:
        return _fail(msg or "Could not turn No main menu off.", enabled=True)
    return _ok(msg, enabled=after)


def map_fog_unlock(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import map_fog_unlock as fog

    payload = payload or {}
    radius = payload.get("radius")
    if radius is None:
        radius = payload.get("unfog_radius")
    try:
        radius_f = float(radius) if radius is not None and str(radius).strip() != "" else None
    except Exception:
        radius_f = None
    msg = fog.expand_unfog_radius(radius=radius_f)
    return _ok(msg)


def oak_travel(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        from mods_base import get_pc
    except Exception as exc:
        return _fail(f"get_pc failed: {exc}")
    pc = get_pc()
    if pc is None:
        return _fail("No player controller.")
    action = str(payload.get("action") or "").strip().lower()
    notes: list[str] = []
    status = getattr(pc, "TravelStatus", None)
    if action in ("cancel", "cancel_countdown", "interrupt"):
        fn = getattr(pc, "ServerInterruptTravelCountdown", None)
        if callable(fn):
            try:
                fn()
                notes.append("ok")
            except TypeError:
                try:
                    fn(0)
                    notes.append("ok")
                except Exception as exc:
                    notes.append(f"interrupt fail:{exc}")
            except Exception as exc:
                notes.append(f"interrupt fail:{exc}")
        else:
            notes.append("missing")
        if status is not None:
            # Match No main menu / live-edit: pin at 4 then clear leave flags.
            try:
                setattr(status, "CountdownTime", 4.0)
            except Exception:
                pass
            try:
                setattr(status, "bIsTravelingToMainMenu", False)
            except Exception:
                pass
            try:
                setattr(status, "status", 0)
            except Exception:
                pass
            try:
                setattr(pc, "TravelStatus", status)
            except Exception:
                pass
        if any(n.startswith("interrupt fail") or n == "missing" for n in notes) and "ok" not in notes:
            return _fail("Could not cancel the travel countdown.")
        return _ok("Travel countdown cancelled (pinned at 4s).")
    elif action in ("disallow_local", "local_lock", ""):
        want = bool(payload.get("enabled", True))
        wrote = False
        if status is not None:
            try:
                setattr(status, "bDisallowLocalTravel", want)
                wrote = True
            except Exception:
                pass
        try:
            setattr(pc, "bDisallowLocalTravel", want)
            wrote = True
        except Exception:
            pass
        if not wrote:
            return _fail("Could not change local fast travel.")
        return _ok("Local fast travel blocked." if want else "Local fast travel allowed.")
    return _fail("Unknown travel action.")


def world_personal_vehicle(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    want = bool(payload.get("enabled", True))
    n = 0
    try:
        import unrealsdk

        worlds = list(unrealsdk.find_all("OakWorldSettings", False) or [])
    except Exception:
        worlds = []
    for ws in worlds:
        if ws is None:
            continue
        try:
            path = str(getattr(ws, "_path_name", lambda: "")() or ws).lower()
        except Exception:
            path = str(ws).lower()
        if "default__" in path:
            continue
        try:
            setattr(ws, "bAllowPersonalVehicle", want)
            n += 1
        except Exception:
            continue
    if n:
        return _ok("Personal vehicles allowed here." if want else "Personal vehicles blocked here.")
    return _fail("Could not change personal vehicles for this world.")


def mobility_toggle_no_target(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    mobility_runtime.toggle_no_target()
    enabled = mobility_runtime.no_target_enabled()
    return _ok(f"No-target mode {'ON' if enabled else 'OFF'}.")


def teleport_party_slot(payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "").strip().lower()
    try:
        slot = max(0, min(3, int(payload.get("slot") or 0)))
    except Exception:
        return _fail("slot must be 0-3 (party slots P1-P4).")
    idx = _single_target_index(payload)
    if mode in ("me_to_slot", "local_to_slot"):
        mobility_runtime.teleport_local_to_party_slot(slot)
        return _ok(f"Teleported you to party slot P{slot + 1}.")
    if mode in ("slot_to_me", "slot_to_local"):
        mobility_runtime.teleport_party_slot_to_local(slot)
        return _ok(f"Teleported party slot P{slot + 1} to you.")
    if mode in ("selected_to_slot", "target_to_slot"):
        mobility_runtime.teleport_selected_to_party_slot(slot, idx)
        return _ok(f"Teleported selected player to party slot P{slot + 1}.")
    return _fail("mode must be me_to_slot, slot_to_me, or selected_to_slot.")


def tuning_apply(payload: dict[str, Any]) -> dict[str, Any]:
    from . import tuning_bridge_fields as tbf
    from . import tuning_embed as te

    module = str(payload.get("module") or "").strip().lower()
    if module not in ("bpm", "bvm", "bdam", "brc"):
        return _fail("module must be bpm, bvm, bdam, or brc.")
    values = payload.get("values")
    if not isinstance(values, dict):
        values = {
            k: v
            for k, v in payload.items()
            if k not in ("module", "values") and not str(k).startswith("_")
        }
    if values:
        tbf.write_values(module, values)
    try:
        msg = te.apply_module(module)
    except Exception as exc:
        return _fail(str(exc))
    return _ok(msg, values=tbf.read_values(module), **te.status_module(module))


def tuning_reset(payload: dict[str, Any]) -> dict[str, Any]:
    from . import tuning_bridge_fields as tbf
    from . import tuning_embed as te

    module = str(payload.get("module") or "").strip().lower()
    if module not in ("bpm", "bvm", "bdam", "brc"):
        return _fail("module must be bpm, bvm, bdam, or brc.")
    try:
        msg = te.reset_module(module)
    except Exception as exc:
        return _fail(str(exc))
    return _ok(msg, values=tbf.read_values(module))


def tuning_preset(payload: dict[str, Any]) -> dict[str, Any]:
    from . import tuning_bridge_fields as tbf
    from . import tuning_embed as te

    module = str(payload.get("module") or "").strip().lower()
    preset = str(payload.get("preset") or "").strip().lower()
    if not preset:
        return _fail("preset is required.")
    try:
        msg = te.preset_module(module, preset)
    except Exception as exc:
        return _fail(str(exc))
    return _ok(msg, values=tbf.read_values(module))


def tuning_status(payload: dict[str, Any]) -> dict[str, Any]:
    from . import tuning_bridge_fields as tbf
    from . import tuning_embed as te

    module = str(payload.get("module") or "").strip().lower()
    if module not in ("bpm", "bvm", "bdam", "brc"):
        return _fail("module must be bpm, bvm, bdam, or brc.")
    return _ok("Tuning status.", values=tbf.read_values(module), **te.status_module(module))


def _parse_legit_parts(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("parts")
    if isinstance(raw, list):
        return [str(line).strip() for line in raw if str(line).strip() and not str(line).strip().startswith("#")]
    out: list[str] = []
    for line in str(raw or payload.get("parts_text") or "").replace("\r", "\n").split("\n"):
        token = line.strip()
        if token and not token.startswith("#"):
            out.append(token)
    return out


def _legit_root_key(payload: dict[str, Any]) -> str:
    return str(payload.get("root_key") or payload.get("root") or "").strip()


def _legit_unlock_rules(payload: dict[str, Any]) -> bool:
    return _as_bool(payload.get("unlock_rules"), False)


def _legit_level(payload: dict[str, Any]) -> int:
    try:
        return max(1, min(70, int(payload.get("level") or 70)))
    except Exception:
        return 70


def _max_passive_lines(root_key: str) -> tuple[list[str], int]:
    best: dict[str, tuple[int, str]] = {}
    scanned = 0
    try:
        parts = legit_builder_core.search_parts(root_key, "passive_", table="passive_points", limit=2000)
    except Exception:
        return [], 0
    for part in parts:
        key = str(part.get("key") or part.get("internal") or "").strip()
        if not key.lower().startswith("passive_"):
            continue
        match = re.search(r"_tier_(\d+)$", key.lower())
        if not match:
            continue
        scanned += 1
        try:
            tier = int(match.group(1))
        except Exception:
            tier = 0
        base = re.sub(r"_tier_\d+$", "", key.lower())
        table = str(part.get("table") or "passive_points").strip()
        line = f"{table}:{key}" if table else key
        old = best.get(base)
        if old is None or tier > old[0]:
            best[base] = (tier, line)
    return [line for _tier, line in sorted(best.values(), key=lambda item: item[1].lower())], scanned


def legit_forge_validate(payload: dict[str, Any]) -> dict[str, Any]:
    root_key = _legit_root_key(payload)
    if not root_key:
        return _fail("root_key required.")
    parts = _parse_legit_parts(payload)
    if _legit_unlock_rules(payload):
        return _ok(f"Unlock mode: {len(parts)} part line(s) accepted without validation.", ok=True, parts=parts)
    result = legit_builder_core.validate(root_key, parts)
    if result.get("ok"):
        return _ok("Validation OK.", validation=result, parts=parts)
    errors = result.get("errors") or []
    warnings = result.get("warnings") or []
    return _fail("; ".join(str(err) for err in errors[:6]) or "Validation failed.", validation=result, errors=errors, warnings=warnings)


def legit_forge_build(payload: dict[str, Any]) -> dict[str, Any]:
    root_key = _legit_root_key(payload)
    if not root_key:
        return _fail("root_key required.")
    parts = _parse_legit_parts(payload)
    level = _legit_level(payload)
    unlock = _legit_unlock_rules(payload)
    try:
        human = legit_builder_core.build_human(root_key, parts, level=level)
        base85 = legit_builder_core.build_base85(root_key, parts, level=level, validate_first=not unlock)
    except Exception as exc:
        return _fail(repr(exc))
    if not str(base85 or "").startswith("@U"):
        return _fail("Build did not produce a valid @U serial.", human=human, base85=base85)
    return _ok("Built serial.", human=human, base85=base85, serial=base85, root_key=root_key, parts=parts)


def legit_forge_give(payload: dict[str, Any]) -> dict[str, Any]:
    serial = str(payload.get("serial") or payload.get("base85") or "").strip()
    if not serial.startswith("@U"):
        built = legit_forge_build(payload)
        if not built.get("ok"):
            return built
        serial = str(built.get("serial") or built.get("base85") or "").strip()
    if not serial.startswith("@U"):
        return _fail("Build a Base85 serial first.")
    payload = dict(payload)
    payload["serials"] = [serial]
    return deliver_serials(payload)


def legit_forge_max_passives(payload: dict[str, Any]) -> dict[str, Any]:
    root_key = _legit_root_key(payload)
    if not root_key:
        return _fail("root_key required.")
    root = legit_builder_core.get_root(root_key)
    if not root:
        return _fail(f"Unknown root {root_key!r}.")
    if str(root.get("item_type") or "").lower() != "class_mod":
        return _fail("Max passives only works on class mod roots.")
    if not _legit_unlock_rules(payload):
        return _fail("Turn on Unlock rules before adding every max passive.")
    max_lines, scanned = _max_passive_lines(root_key)
    if not max_lines:
        return _fail(f"No passive_points parts found for {root_key} (scanned {scanned}).")
    parts = [line for line in _parse_legit_parts(payload) if not line.lower().startswith("passive_points:")]
    parts.extend(max_lines)
    parts_text = "\n".join(parts)
    label = str(root.get("build_label") or root_key)
    return _ok(
        f"Added {len(max_lines)} max-tier passive part(s) for {label}.",
        parts=parts,
        parts_text=parts_text,
        added=len(max_lines),
    )


def legit_forge_append_part(payload: dict[str, Any]) -> dict[str, Any]:
    root_key = _legit_root_key(payload)
    if not root_key:
        return _fail("root_key required.")
    line = str(payload.get("pick") or payload.get("part_line") or payload.get("part") or "").strip()
    if not line:
        return _fail("Select a part from the catalog first.")
    parts = _parse_legit_parts(payload)
    if line not in parts:
        parts.append(line)
    parts_text = "\n".join(parts)
    return _ok(f"Appended {line}.", parts=parts, parts_text=parts_text)


def serial_convert(payload: dict[str, Any]) -> dict[str, Any]:
    raw = str(payload.get("input") or payload.get("text") or "").strip()
    if not raw:
        return _fail("input required.")
    level_override = _coerce_bool(payload.get("level_override"), default=False)
    try:
        level_i = max(1, min(int(payload.get("level") or DEFAULT_ITEM_LEVEL), 100))
    except Exception:
        level_i = int(DEFAULT_ITEM_LEVEL)
    lines = [line.strip() for line in raw.replace("\r\n", "\n").split("\n") if line.strip()]
    if not lines:
        return _fail("input required.")
    results: list[dict[str, str]] = []
    errors: list[str] = []
    level_re = re.compile(r"^(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*)\d+")
    for index, line in enumerate(lines, 1):
        try:
            if line.startswith("@U"):
                human = serial_to_human(line)
                if level_override:
                    human, count = level_re.subn(rf"\g<1>{level_i}", human, count=1)
                    if count <= 0:
                        raise ValueError("could not find leading item level")
                    serial = human_to_serial(human)
                else:
                    serial = line
            else:
                human = line
                if level_override:
                    human, count = level_re.subn(rf"\g<1>{level_i}", human, count=1)
                    if count <= 0:
                        raise ValueError("could not find leading item level")
                serial = human_to_serial(human)
            if not serial or not str(serial).startswith("@U"):
                raise ValueError("conversion produced no @U serial")
            results.append({"serial": str(serial), "human": str(human)})
        except Exception as exc:
            errors.append(f"line {index}: {exc}")
    if not results:
        return _fail(errors[0] if errors else "Conversion failed.")
    first = results[0]
    message = first["human"] if len(results) == 1 and not first["serial"].startswith(raw[:2]) else (
        first["serial"] if len(results) == 1 else f"Converted {len(results)} serial(s)."
    )
    if len(results) == 1 and raw.startswith("@U") and not level_override:
        message = first["human"]
    elif len(results) == 1:
        message = first["serial"]
    if errors:
        message = f"{message} ({len(errors)} line(s) failed)"
    return _ok(
        message,
        serial=first["serial"],
        human=first["human"],
        results=results,
        errors=errors,
        count=len(results),
    )


def activity_log(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    from .item_pool_spawning import clear_spawn_log_session, dump_spawn_log

    if payload.get("clear"):
        clear_spawn_log_session(clear_files=True)
        return _ok("Spawn activity log cleared.", lines=[])
    lines = dump_spawn_log(log_to_console=False).splitlines()
    return _ok(f"{len(lines)} log line(s).", lines=lines[-80:])


def rewards_open_everyone(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Queue paced open for every pending reward package (never bulk-open in one frame)."""
    payload = payload or {}
    force = _coerce_bool(payload.get("force") or payload.get("confirmed_large"), default=False)
    try:
        if bool(challenge_status().get("active")):
            return _fail(
                "Complete ALL / challenge bulk is still running. Do not Open pending rewards yet — "
                "that pass often leaves hundreds of packages. Wait until it finishes, bank / mule, "
                "then open in solo if you really need every package.",
                opened=0,
                needs_force=False,
                challenge_bulk_active=True,
            )
    except Exception:
        pass
    packages, managers = 0, 0
    try:
        from .serial_rewards import (
            _OPEN_ALL_CHALLENGE_WARN_PACKAGES,
            _queue_open_all_pending_packages,
            _reward_open_gap_sec,
            clear_open_all_challenge_block,
            count_pending_reward_packages,
            open_all_blocked_after_challenge_bulk,
        )

        pending = int(count_pending_reward_packages() or 0)
        blocked = bool(open_all_blocked_after_challenge_bulk())
        party_count = len(list(_player_rows() or []))
        large_multiplayer_open = (
            party_count > 1
            and (blocked or pending >= int(_OPEN_ALL_CHALLENGE_WARN_PACKAGES))
        )
        if large_multiplayer_open:
            return _fail(
                f"Large pending-reward opening is blocked in multiplayer "
                f"({pending} package(s) pending). Complete ALL only "
                "sends these rewards. Leave the lobby, open them in solo, sell junk and reduce "
                "carried items before rejoining; console/cross-play backpacks can disappear online "
                "when holding hundreds of items.",
                opened=0,
                needs_force=False,
                packages=pending,
                suppress_open_all=True,
                solo_required=True,
            )
        if (
            not blocked
            and not force
            and pending >= int(_OPEN_ALL_CHALLENGE_WARN_PACKAGES)
        ):
            return _fail(
                f"{pending} pending mail package(s) — that is a long paced open. "
                "Confirm again to open all of them, or bank / mule first.",
                opened=0,
                needs_force=True,
                packages=pending,
            )
        packages, managers = _queue_open_all_pending_packages()
        gap_fn = _reward_open_gap_sec
        if packages > 0 and blocked:
            clear_open_all_challenge_block()
    except Exception as exc:
        return _fail(f"Could not queue reward opens: {exc!r}", opened=0)
    if packages > 0:
        gap = float(gap_fn(max(1, int(packages))))
        eta = max(2, int(round(packages * gap)))
        return _ok(
            f"Opening {packages} mail package(s) paced (~{eta}s). Stay in-world until done.",
            opened=managers,
            packages=packages,
            eta_sec=eta,
        )
    return _fail("No pending rewards could be queued for opening.", opened=0)


_ll_refresh_lock = threading.Lock()
_ll_refresh_thread: threading.Thread | None = None
_ll_refresh_busy = False
_ll_refresh_message = ""
_ll_refresh_count = 0


def gzo_refresh_start(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Kick off background GZO scrape (same path as in-game Refresh)."""
    del _payload
    try:
        from .blimgui_panel import _gzo_refresh_catalog, _gzo_status
    except Exception as exc:
        return _fail(f"GZO catalog unavailable: {exc}")
    try:
        _gzo_refresh_catalog()
    except Exception as exc:
        return _fail(f"GZO catalog refresh failed: {exc}")
    return _ok(str(_gzo_status or "GZO refresh started."), busy=True)


def gzo_refresh_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    try:
        from .blimgui_panel import (
            _gzo_entries,
            _gzo_refresh_thread,
            _gzo_status,
            _poll_gzo_refresh_result,
        )
    except Exception as exc:
        return _fail(f"GZO catalog unavailable: {exc}")
    try:
        _poll_gzo_refresh_result()
    except Exception as exc:
        return _fail(f"GZO catalog status failed: {exc}")
    busy = _gzo_refresh_thread is not None and _gzo_refresh_thread.is_alive()
    count = len(_gzo_entries) if isinstance(_gzo_entries, list) else 0
    msg = str(_gzo_status or ("Refreshing GZO…" if busy else "GZO idle."))
    return _ok(msg, busy=busy, count=count)


def lootlemon_refresh_start(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Kick off background Lootlemon scrape so the game/EXE stay responsive."""
    del _payload
    global _ll_refresh_thread, _ll_refresh_busy, _ll_refresh_message, _ll_refresh_count
    with _ll_refresh_lock:
        if _ll_refresh_thread is not None and _ll_refresh_thread.is_alive():
            return _ok(_ll_refresh_message or "Lootlemon refresh already running.", busy=True)

        def _worker() -> None:
            global _ll_refresh_busy, _ll_refresh_message, _ll_refresh_count
            try:
                from . import blimgui_panel as panel

                panel._lootlemon_refresh_catalog()
                entries = getattr(panel, "_lootlemon_entries", []) or []
                _ll_refresh_count = len(entries) if isinstance(entries, list) else 0
                _ll_refresh_message = str(
                    getattr(panel, "_lootlemon_status", None)
                    or f"Loaded {_ll_refresh_count} Lootlemon code(s)."
                )
            except Exception as exc:
                _ll_refresh_message = f"Lootlemon catalog unavailable: {exc}"
                _ll_refresh_count = 0
            finally:
                _ll_refresh_busy = False

        _ll_refresh_busy = True
        _ll_refresh_message = "Refreshing Lootlemon in the background…"
        _ll_refresh_count = 0
        _ll_refresh_thread = threading.Thread(
            target=_worker,
            name="Squ1ggs Lootlemon Refresh",
            daemon=True,
        )
        _ll_refresh_thread.start()
    return _ok(_ll_refresh_message, busy=True)


def lootlemon_refresh_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    with _ll_refresh_lock:
        busy = bool(_ll_refresh_busy) or (
            _ll_refresh_thread is not None and _ll_refresh_thread.is_alive()
        )
        msg = _ll_refresh_message or ("Refreshing Lootlemon…" if busy else "Lootlemon idle.")
        count = int(_ll_refresh_count or 0)
    if not busy and not msg:
        try:
            from .blimgui_panel import _lootlemon_entries, _lootlemon_status

            count = len(_lootlemon_entries) if isinstance(_lootlemon_entries, list) else 0
            msg = str(_lootlemon_status or f"{count} Lootlemon code(s) cached.")
        except Exception as exc:
            return _fail(f"Lootlemon catalog unavailable: {exc}")
    return _ok(msg, busy=busy, count=count)


def panel_manifest(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    return _ok("Panel manifest.", manifest=get_panel_manifest())


def _faafo_apply(payload: dict[str, Any] | None, fn: Any, **kwargs: Any) -> dict[str, Any]:
    from . import faafo as _faafo

    _faafo.ensure_launch_hook()
    indices = _boost_targets_from_payload(payload)
    if not indices:
        return _fail("No boost target players in lobby.")
    ok_n = 0
    details: list[str] = []
    for idx in indices:
        try:
            msg = str(fn(player_index=idx, **kwargs) or "")
            details.append(msg)
            lower = msg.lower()
            if "failed" in lower and "ok" not in lower:
                continue
            ok_n += 1
        except Exception as exc:
            details.append(f"index {idx}: {exc}")
    if ok_n == 0:
        return _fail("; ".join(details) or "FAAFO action failed.")
    if len(indices) == 1:
        return _ok(details[0])
    return _ok(f"FAAFO applied to {ok_n}/{len(indices)} player(s).")


def faafo_launch(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import faafo as _faafo

    payload = payload or {}
    try:
        z = float(payload.get("z") if payload.get("z") is not None else payload.get("z_boost") or _faafo._DEFAULT_LAUNCH_Z)
    except Exception:
        return _fail("z must be a number.")
    return _faafo_apply(payload, _faafo.do_launch, z_boost=z)


def faafo_drop_backpack(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import faafo as _faafo
    from .loot_shapes import (
        arm_deferred_catch,
        arm_overhead_catch,
        begin_spawn_landing,
        landing_armed,
        normalize_drop_mode,
        settle_landing_loot,
    )

    payload = payload or {}
    land = _loot_landing_kwargs(payload)
    shape_l = str(land.get("shape") or "none").strip().lower()
    if shape_l in ("", "off", "no", "vanilla"):
        shape_l = "none"
    settle_l = normalize_drop_mode(str(land.get("settle") or "none"))
    land_wanted = shape_l != "none" or settle_l != "none"
    est = 64
    # Never splat fill_until_complete into begin_spawn_landing (TypeError → fake "app out of date").
    if land_wanted:
        indices = _boost_targets_from_payload(payload)
        if indices:
            try:
                pc, _ = _resolve_pc(indices[0])
                if pc is not None:
                    cnt = _faafo._backpack_occupied_count(pc)
                    if cnt and int(cnt) > 0:
                        est = max(8, min(400, int(cnt)))
            except Exception:
                pass
        begin_spawn_landing(
            est,
            shape=shape_l,
            settle=settle_l,
            drop_height=float(land.get("drop_height") or 440),
            line_length=float(land.get("line_length") or 520),
            radius=float(land.get("radius") or 200),
            spacing=float(land.get("spacing") or 72),
            z_bias=float(land.get("z_bias") or 18),
            spawn_then_shape=bool(land.get("spawn_then_shape")),
            stay_in_air=bool(land.get("stay_in_air", True)),
            float_on_grab=bool(land.get("float_on_grab", False)),
            peel_after=float(land.get("peel_after") or 0),
            land_profile=str(land.get("land_profile") or "shiny"),
        )
        arm_overhead_catch(max(24.0, est * 0.12))
    result = _faafo_apply(payload, _faafo.do_drop_backpack)
    # SpillOut dumps at feet — same end sweep Drop All / Spawn All use so catch pulls into slots.
    if land_wanted:
        try:
            if landing_armed():
                from .loot_shapes import pull_new_pickups_into_shape

                settle_landing_loot(limit=max(32, min(200, int(est))))
                # Immediate extra sweeps: settle alone can't finish a 300+ pack in one pass.
                for _ in range(6):
                    if pull_new_pickups_into_shape(limit=12, fresh=True) <= 0:
                        break
                arm_deferred_catch(max(28.0, float(est) * 0.12))
        except Exception:
            pass
    return result


def faafo_empty_backpack(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import faafo as _faafo

    return _faafo_apply(payload or {}, _faafo.do_empty_backpack)


def faafo_ffyl(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import faafo as _faafo

    return _faafo_apply(payload or {}, _faafo.do_ffyl)


def faafo_kill(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import faafo as _faafo

    return _faafo_apply(payload or {}, _faafo.do_kill)


def faafo_invert_look(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import faafo as _faafo

    payload = payload or {}
    try:
        seconds = float(payload.get("seconds") if payload.get("seconds") is not None else _faafo._DEFAULT_INVERT_SECS)
    except Exception:
        return _fail("seconds must be a number.")
    return _faafo_apply(payload, _faafo.do_invert_look, seconds=seconds)


def faafo_lock_look(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import faafo as _faafo

    payload = payload or {}
    try:
        seconds = float(payload.get("seconds") if payload.get("seconds") is not None else _faafo._DEFAULT_LOCK_SECS)
    except Exception:
        return _fail("seconds must be a number.")
    return _faafo_apply(payload, _faafo.do_lock_look, seconds=seconds)


def faafo_lock_move(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import faafo as _faafo

    payload = payload or {}
    try:
        seconds = float(payload.get("seconds") if payload.get("seconds") is not None else _faafo._DEFAULT_LOCK_SECS)
    except Exception:
        return _fail("seconds must be a number.")
    return _faafo_apply(payload, _faafo.do_lock_move, seconds=seconds)


def faafo_lock_both(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import faafo as _faafo

    payload = payload or {}
    try:
        seconds = float(payload.get("seconds") if payload.get("seconds") is not None else _faafo._DEFAULT_LOCK_SECS)
    except Exception:
        return _fail("seconds must be a number.")
    return _faafo_apply(payload, _faafo.do_lock_both, seconds=seconds)


def faafo_unlock(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import faafo as _faafo

    return _faafo_apply(payload or {}, _faafo.do_unlock)


def catalog_action(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or payload.get("catalog") or "").strip()
    inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    return run_catalog(name, inner if isinstance(inner, dict) else {})


def keybinds_status(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    del _payload
    from .user_keybinds import status_payload

    return status_payload()


def keybinds_set(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .user_keybinds import set_bind

    return set_bind(payload or {})


def keybinds_clear(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .user_keybinds import clear_bind

    return clear_bind(payload or {})


def backpack_scan_status(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """UI trigger only — sheet reload happens in the EXE / catalog refresh.

    Avoids a double backpack walk (action + catalog) which hitchs fat packs.
    """
    payload = payload or {}
    if bool(payload.get("pack_bay")) or str(payload.get("sheet") or "").strip().lower() == "bay":
        return _ok("Refreshing Pack Bay from autosave…", count=0, save_yaml=True)
    idx = _single_target_index(payload)
    if idx < 0:
        return _fail("Pick one boost target (not All players) to snap their backpack.")
    return _ok(
        f"Snapping backpack for player index {int(idx)}…",
        count=0,
        player_index=int(idx),
        party_bay=True,
    )


def backpack_relevel_selected(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .backpack_tools import relevel_backpack_slots

    payload = payload or {}
    idx = _single_target_index(payload)
    if idx < 0:
        return _fail("Pick one boost target (not All players) to relevel backpack gear.")
    slots_raw = payload.get("slots") or payload.get("slot_indices") or []
    if isinstance(slots_raw, (str, int)):
        slots_raw = [slots_raw]
    slots: list[int] = []
    for item in slots_raw if isinstance(slots_raw, (list, tuple, set)) else []:
        try:
            slots.append(int(item))
        except (TypeError, ValueError):
            continue
    if not slots:
        return _fail("Tick at least one backpack item first.")
    level = int(payload.get("level") or DEFAULT_ITEM_LEVEL)
    result = relevel_backpack_slots(idx, slots, level)
    if result.get("ok"):
        return _ok(
            str(result.get("message") or "Done."),
            updated=int(result.get("updated") or 0),
            failed=int(result.get("failed") or 0),
            level=int(result.get("level") or level),
        )
    return _fail(
        str(result.get("message") or "Relevel failed."),
        updated=int(result.get("updated") or 0),
        failed=int(result.get("failed") or 0),
    )


def backpack_export_txt(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Download Party Bay @U dump as .txt (ticked rows, or full snap if none ticked)."""
    from .backpack_tools import export_backpack_txt

    payload = payload or {}
    idx = _single_target_index(payload)
    if idx < 0:
        return _fail("Pick one boost target (not All players) to export backpack @U.")
    slots_raw = payload.get("slots") or payload.get("slot_indices") or []
    if isinstance(slots_raw, (str, int)):
        slots_raw = [slots_raw]
    slots: list[int] = []
    for item in slots_raw if isinstance(slots_raw, (list, tuple, set)) else []:
        try:
            slots.append(int(item))
        except (TypeError, ValueError):
            continue
    result = export_backpack_txt(
        idx,
        slot_indices=slots or None,
        include_equipped=True,
    )
    if not result.get("ok"):
        return _fail(str(result.get("message") or "Export failed."))
    return _ok(
        str(result.get("message") or "Exported."),
        text=str(result.get("text") or ""),
        count=int(result.get("count") or 0),
        player_index=int(idx),
    )


def pack_bay_enable(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import pack_bay

    del _payload
    return _ok(pack_bay.enable_for_local_test(), enabled=True)


def pack_bay_disable(_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import pack_bay

    del _payload
    return _ok(pack_bay.disable_for_local_test(), enabled=False)


def pack_bay_copy_selected(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Copy ticked bay @U serials to the Windows clipboard (local test helper)."""
    payload = payload or {}
    serials_raw = payload.get("serials") or []
    if isinstance(serials_raw, str):
        serials_raw = [serials_raw]
    serials: list[str] = []
    for item in serials_raw if isinstance(serials_raw, (list, tuple, set)) else []:
        text = str(item or "").strip()
        if text.startswith("@U"):
            serials.append(text)
    if not serials:
        return _fail("Tick at least one bay row with an @U serial first.")
    copied, err = _copy_text_to_windows_clipboard("\n".join(serials))
    if not copied:
        return _fail(err or "Clipboard copy failed.")
    return _ok(f"Copied {len(serials)} @U serial(s) to clipboard.", count=len(serials))


def pack_bay_open_toolbox(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Copy ticked @U (if any) and tell the EXE to open scooterstoolbox.com."""
    from .pack_bay import TOOLBOX_URL

    payload = payload or {}
    serials_raw = payload.get("serials") or []
    if isinstance(serials_raw, str):
        serials_raw = [serials_raw]
    serials: list[str] = []
    for item in serials_raw if isinstance(serials_raw, (list, tuple, set)) else []:
        text = str(item or "").strip()
        if text.startswith("@U"):
            serials.append(text)
    copied = 0
    if serials:
        ok, err = _copy_text_to_windows_clipboard("\n".join(serials))
        if not ok:
            return _fail(err or "Clipboard copy failed.")
        copied = len(serials)
        msg = f"Copied {copied} @U — opening Scooter's Toolbox. Paste there to edit."
    else:
        msg = "Opening Scooter's Toolbox (nothing ticked — copy serials first if you need them)."
    return _ok(msg, count=copied, open_url=TOOLBOX_URL)


def bay_label_serials(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Name + level Pack Bay / pasted @U rows via the same GZO decode Party Bay uses."""
    from . import item_labels

    payload = payload or {}
    raw_rows = payload.get("rows")
    serials: list[str] = []
    if isinstance(raw_rows, list) and raw_rows:
        for row in raw_rows:
            if isinstance(row, dict):
                serials.append(str(row.get("serial") or "").strip())
            else:
                serials.append(str(row or "").strip())
    else:
        for key in ("serials", "items", "codes"):
            blob = payload.get(key)
            if isinstance(blob, list):
                serials.extend(str(x or "").strip() for x in blob)
                break
            if isinstance(blob, str) and blob.strip():
                serials.extend(line.strip() for line in blob.splitlines() if line.strip())
                break
    out: list[dict[str, Any]] = []
    named = 0
    leveled = 0
    for index, serial in enumerate(serials):
        if not serial.startswith("@U"):
            continue
        bits = item_labels.title_bits_from_serial(serial)
        pretty = str(bits.get("display_name") or "").strip()
        rarity = str(bits.get("rarity") or "").strip()
        manufacturer = str(bits.get("manufacturer") or "").strip()
        item_type = str(bits.get("item_type") or "").strip()
        level = bits.get("level")
        if pretty:
            named += 1
        else:
            snip = serial if len(serial) <= 40 else f"{serial[:36]}…"
            pretty = snip
        bits_list: list[str] = []
        if rarity:
            bits_list.append(rarity)
        if manufacturer and manufacturer.casefold() not in pretty.casefold():
            bits_list.append(manufacturer)
        if item_type and item_type.casefold() not in pretty.casefold():
            bits_list.append(item_type)
        suffix = f" · {' / '.join(bits_list)}" if bits_list else ""
        label = f"{pretty}{suffix}"
        if isinstance(level, int):
            label = f"{label} L{level}"
            leveled += 1
        row: dict[str, Any] = {
            "id": str(index),
            "slot": int(index),
            "serial": serial,
            "title": f"#{index} — {label}",
            "display_name": pretty,
        }
        if rarity:
            row["rarity"] = rarity
        if manufacturer:
            row["manufacturer"] = manufacturer
        if item_type:
            row["item_type"] = item_type
        if isinstance(level, int):
            row["level"] = level
        out.append(row)
    return _ok(
        f"Named {named}/{len(out)} · leveled {leveled}/{len(out)}.",
        rows=out,
        named=named,
        leveled=leveled,
    )


def _copy_text_to_windows_clipboard(blob: str) -> tuple[bool, str]:
    try:
        import ctypes

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        if not user32.OpenClipboard(None):
            return False, "Could not open clipboard."
        try:
            user32.EmptyClipboard()
            size = (len(blob) + 1) * 2
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
            if not handle:
                return False, "Clipboard alloc failed."
            locked = kernel32.GlobalLock(handle)
            if not locked:
                kernel32.GlobalFree(handle)
                return False, "Clipboard lock failed."
            try:
                ctypes.memmove(locked, blob.encode("utf-16-le") + b"\x00\x00", size)
            finally:
                kernel32.GlobalUnlock(handle)
            user32.SetClipboardData(CF_UNICODETEXT, handle)
        finally:
            user32.CloseClipboard()
    except Exception as exc:
        return False, f"Clipboard copy failed: {exc}"
    return True, ""


_EXTENDED_ALIASES: dict[str, str] = {
    "serial_delivery_status": "serial_delivery_status_action",
    "spawn_item_pool": "spawn_item_pool_action",
    "spawn_item_pool_all": "spawn_item_pool_all_action",
    "spawn_item_pool_singular_test": "spawn_item_pool_singular_test_action",
    "catalog": "catalog_action",
    "shiny_drop_status": "shiny_drop_status_action",
    "loot_coil_reel": "loot_gather_nearby",
    "map_scout_start": "host_map_sweep_start",
    "map_scout_cancel": "host_map_sweep_cancel",
    "map_scout_status": "host_map_sweep_status",
    "map_party_escort_start": "guest_map_assist_start",
    "map_party_escort_cancel": "guest_map_assist_cancel",
    "map_party_escort_status": "guest_map_assist_status",
}

_EXTENDED_ACTION_NAMES: tuple[str, ...] = (
    "keybinds_status",
    "keybinds_set",
    "keybinds_clear",
    "rewards_open_everyone",
    "deliver_serials",
    "serial_store_save",
    "serial_store_import_serials",
    "serial_store_add_selected",
    "serial_store_delete",
    "serial_store_duplicate",
    "serial_store_export_text",
    "serial_store_export_json",
    "serial_store_import_merge",
    "serial_store_rename_group",
    "serial_store_create_group",
    "serial_store_delete_group",
    "serial_delivery_status",
    "gzo_refresh_start",
    "gzo_refresh_status",
    "lootlemon_refresh_start",
    "lootlemon_refresh_status",
    "max_sdu",
    "inventory_set_sizes",
    "party_refresh",
    "party_kick",
    "uvhm_start",
    "uvhm_start_all",
    "uvhm_cancel",
    "uvhm_resume",
    "uvhm_status",
    "challenge_bulk_start",
    "challenge_complete_selected",
    "challenge_bulk_cancel",
    "challenge_bulk_status",
    "spawn_item_pool",
    "spawn_item_pool_all",
    "spawn_item_pool_singular_test",
    "spawn_item_pool_cancel",
    "spawn_item_pool_status",
    "travel_map",
    "travel_station",
    "travel_preset",
    "spawn_mix",
    "spawn_mob",
    "spawn_mobs",
    "barrel_logo",
    "barrel_logo_clear",
    "spawn_io",
    "spawn_ios",
    "spawn_encounter",
    "bms_group_add",
    "bms_group_remove",
    "bms_group_clear_plan",
    "bms_group_set_options",
    "bms_group_start",
    "bms_group_stop",
    "bms_group_next",
    "bms_group_status",
    "bms_group_clear_live",
    "bms_group_save",
    "bms_group_load",
    "bms_group_delete_save",
    "bms_reaggro",
    "bms_clear",
    "bms_activate_io",
    "golden_chest",
    "black_market",
    "mayhem_level",
    "devperk_activate",
    "god_mode",
    "infinite_ammo",
    "kill_all_enemies",
    "shiny_drop_all",
    "spawn_text_shape",
    "shiny_drop_status",
    "shiny_mail_all",
    "rarity_weights_set",
    "loot_feed_appear",
    "pawn_no_target",
    "pawn_gravity",
    "weapons_restricted",
    "vehicle_actions_locked",
    "ammo_regen",
    "faafo_launch",
    "faafo_drop_backpack",
    "faafo_empty_backpack",
    "faafo_ffyl",
    "faafo_kill",
    "faafo_invert_look",
    "faafo_lock_look",
    "faafo_lock_move",
    "faafo_lock_both",
    "faafo_unlock",
    "faafo_fall_through_map",
    "teleport_party",
    "mobility_preset_apply",
    "mobility_apply",
    "mobility_status",
    "mobility_save_preset",
    "mobility_load_preset",
    "mobility_zero_vault",
    "mobility_noclip",
    "mobility_time",
    "mobility_auto_apply",
    "mobility_players_only",
    "mobility_delete_ground",
    "loot_shape_place_fully",
    "loot_shape_arrange",
    "loot_shape_clear",
    "loot_cleanup",
    "loot_gather_nearby",
    "loot_coil_reel",
    "loot_vacuum_nearby",
    "loot_vacuum_cancel",
    "loot_vacuum_status",
    "guest_map_assist_start",
    "guest_map_assist_cancel",
    "guest_map_assist_status",
    "map_party_escort_start",
    "map_party_escort_cancel",
    "map_party_escort_status",
    "warp_mark_save",
    "warp_mark_go",
    "warp_mark_delete",
    "warp_mark_list",
    "host_map_sweep_start",
    "host_map_sweep_cancel",
    "host_map_sweep_status",
    "map_scout_start",
    "map_scout_cancel",
    "map_scout_status",
    "loot_shape_reapply",
    "loot_shape_status",
    "loot_shape_stop_drop",
    "map_fog_hide",
    "hold_session",
    "map_fog_unlock",
    "oak_travel",
    "world_personal_vehicle",
    "mobility_toggle_no_target",
    "character_flag",
    "lab_intrinsic_element",
    "mobility_infinite_jump",
    "mobility_force_fly",
    "bvm_vehicle_jump",
    "vehicle_spawn",
    "vehicle_spawn_catalog_reload",
    "teleport_party_slot",
    "tuning_apply",
    "tuning_reset",
    "tuning_preset",
    "tuning_status",
    "legit_forge_validate",
    "legit_forge_build",
    "legit_forge_give",
    "legit_forge_max_passives",
    "legit_forge_append_part",
    "serial_convert",
    "activity_log",
    "backpack_scan_status",
    "backpack_relevel_selected",
    "backpack_export_txt",
    "pack_bay_enable",
    "pack_bay_disable",
    "pack_bay_copy_selected",
    "pack_bay_open_toolbox",
    "bay_label_serials",
    "panel_manifest",
    "catalog",
    "lab_pc_rpc",
    "lab_live_attr",
)


def _build_extended_actions() -> dict[str, Any]:
    """Bind by name so one missing function cannot wipe the whole EXE table."""
    g = globals()
    out: dict[str, Any] = {}
    for action in _EXTENDED_ACTION_NAMES:
        fn_name = _EXTENDED_ALIASES.get(action, action)
        fn = g.get(fn_name)
        if callable(fn):
            out[action] = fn
    return out


EXTENDED_ACTIONS: dict[str, Any] = _build_extended_actions()
