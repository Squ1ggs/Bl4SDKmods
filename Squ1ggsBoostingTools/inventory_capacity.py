"""Backpack / bank container size helpers for Squ1ggs's Boosting Tools."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from mods_base import ENGINE
from unrealsdk import logging

from .party_helpers import _gbc_resolve_player_display_name

_PREFIX = "[Squ1ggs's Boosting Tools | Inventory]"

_MIN_CONTAINER_SIZE = 1
# No artificial 9999 cap — allow any positive int up to signed 32-bit (engine-safe).
_MAX_CONTAINER_SIZE = 2_147_483_647
_DEFAULT_BACKPACK_SIZE = 70
_DEFAULT_BANK_SIZE = 500

# Auto-apply tuning. PlayerState exists before the profile/inventory containers
# are fully settled. The bank is especially late-loaded and may be reset by the
# game after early writes. The earlier repeated-write approach worked best in
# practice, so automatic mode performs a short silent burst and only reports the
# final pass.
_AUTO_DEFER_SECONDS = 0.0
_AUTO_RETRY_SECONDS = 0.75
# Do not force-write matching UObject containers for minutes after every join.
# Repeated writes (including replication notifications) from a Python tick were
# the last recorded activity before native pyunrealsdk access violations.
_AUTO_STABILIZE_SECONDS = 0.0
_AUTO_POLL_SECONDS = 5.0

_SETTINGS_FILE_NAME = "Squ1ggsBoostingTools_settings.json"
_settings_lock = threading.RLock()
_background_started = False
_background_stop = False
_last_background_log = 0.0
_auto_apply_lock = threading.RLock()
_settings_cache: dict[str, Any] | None = None

_DEFAULT_SETTINGS = {
    "auto_inventory_sizes": False,
    "backpack_size": _DEFAULT_BACKPACK_SIZE,
    "bank_size": _DEFAULT_BANK_SIZE,
}


def _candidate_settings_paths() -> list[Path]:
    """Prefer durable paths outside the mod package (Install / update wipes the package folder)."""
    paths: list[Path] = []
    try:
        paths.append(
            Path.home()
            / "Documents"
            / "My Games"
            / "Borderlands 4"
            / "Saved"
            / _SETTINGS_FILE_NAME
        )
    except Exception:
        pass
    try:
        cwd = Path.cwd()
        paths.append(cwd / "sdk_mods" / "settings" / _SETTINGS_FILE_NAME)
        paths.append(cwd / "sdk_mods" / _SETTINGS_FILE_NAME)
        paths.append(cwd / _SETTINGS_FILE_NAME)
    except Exception:
        pass
    # Legacy read/migrate only — files next to this module are deleted on folder sync.
    try:
        paths.append(Path(__file__).resolve().parent / _SETTINGS_FILE_NAME)
    except Exception:
        pass

    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def _settings_path_for_read() -> Path:
    for path in _candidate_settings_paths():
        try:
            if path.exists():
                return path
        except Exception:
            pass
    return _candidate_settings_paths()[0]


def _settings_path_for_write() -> Path:
    durable = _candidate_settings_paths()
    candidates = durable[:-1] if len(durable) > 1 else durable
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            test = path.parent / (path.name + ".tmp")
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
            return path
        except Exception:
            continue
    return candidates[0] if candidates else durable[0]


def load_inventory_settings() -> dict[str, Any]:
    global _settings_cache
    with _settings_lock:
        if _settings_cache is not None:
            return dict(_settings_cache)
        settings = dict(_DEFAULT_SETTINGS)
        path = _settings_path_for_read()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                settings.update(raw)
        except Exception:
            pass
        settings["auto_inventory_sizes"] = bool(settings.get("auto_inventory_sizes", False))
        settings["backpack_size"] = clamp_container_size(settings.get("backpack_size", _DEFAULT_BACKPACK_SIZE), _DEFAULT_BACKPACK_SIZE)
        settings["bank_size"] = clamp_container_size(settings.get("bank_size", _DEFAULT_BANK_SIZE), _DEFAULT_BANK_SIZE)
        _settings_cache = dict(settings)
        return settings


def save_inventory_settings(*, auto_inventory_sizes: bool | None = None, backpack_size: int | None = None, bank_size: int | None = None) -> dict[str, Any]:
    global _settings_cache
    with _settings_lock:
        settings = load_inventory_settings()
        if auto_inventory_sizes is not None:
            settings["auto_inventory_sizes"] = bool(auto_inventory_sizes)
        if backpack_size is not None:
            settings["backpack_size"] = clamp_container_size(backpack_size, _DEFAULT_BACKPACK_SIZE)
        if bank_size is not None:
            settings["bank_size"] = clamp_container_size(bank_size, _DEFAULT_BANK_SIZE)
        path = _settings_path_for_write()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(settings, indent=2, sort_keys=True), encoding="utf-8")
        except Exception as exc:
            _log(f"Could not save inventory settings: {exc!r}")
        _settings_cache = dict(settings)
        return settings



def save_extra_settings(**extra: Any) -> dict[str, Any]:
    """Persist additional Squ1ggs Boost UI settings alongside inventory settings."""
    global _settings_cache
    with _settings_lock:
        settings = load_inventory_settings()
        settings.update(extra)
        path = _settings_path_for_write()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(settings, indent=2, sort_keys=True), encoding="utf-8")
        except Exception as exc:
            _log(f"Could not save extra settings: {exc!r}")
        _settings_cache = dict(settings)
        return settings

def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")


def clamp_container_size(value: int, default: int = 70) -> int:
    try:
        v = int(value)
    except Exception:
        v = int(default)
    return max(_MIN_CONTAINER_SIZE, min(v, _MAX_CONTAINER_SIZE))


def _get_game_state() -> Any | None:
    try:
        if ENGINE is None:
            return None
        viewport = getattr(ENGINE, "GameViewport", None)
        if viewport is None:
            return None
        world = getattr(viewport, "World", None)
    except Exception:
        world = None
    return getattr(world, "GameState", None) if world is not None else None


def get_party_player_states() -> list[tuple[int, str, Any]]:
    gs = _get_game_state()
    pa = getattr(gs, "PlayerArray", None) if gs is not None else None
    if pa is None:
        return []
    try:
        n = len(pa)
    except Exception:
        return []
    out: list[tuple[int, str, Any]] = []
    for i in range(n):
        try:
            ps = pa[i]
        except Exception:
            ps = None
        if ps is not None:
            out.append((i, _gbc_resolve_player_display_name(ps), ps))
    return out


def get_player_state_by_party_index(index: int | None) -> Any | None:
    if index is None:
        return None
    for i, _name, ps in get_party_player_states():
        if i == int(index):
            return ps
    return None


def _set_attr_integer(attr: Any, size: int) -> bool:
    """Set a GbxAttributeInteger-like struct's Value/BaseValue fields."""
    if attr is None:
        return False
    wrote = False
    for field in ("Value", "BaseValue"):
        try:
            setattr(attr, field, int(size))
            wrote = True
        except Exception:
            pass
    for method_name in ("SetValue", "SetBaseValue"):
        method = getattr(attr, method_name, None)
        if callable(method):
            try:
                method(int(size))
                wrote = True
            except Exception:
                pass
    return wrote


def _bump_replication(container: Any) -> None:
    if container is None:
        return
    for rep_field in ("ArrayReplicationKey", "ReplicationKey", "LastReplicationKey"):
        try:
            cur = int(getattr(container, rep_field))
            setattr(container, rep_field, cur + 1)
        except Exception:
            pass
    for method_name in ("MarkItemDirty", "MarkArrayDirty", "ForceNetUpdate", "OnRep_MaxSize"):
        method = getattr(container, method_name, None)
        if callable(method):
            try:
                method()
            except TypeError:
                try:
                    method(container)
                except Exception:
                    pass
            except Exception:
                pass


def _container_max_size(ps: Any, container_name: str) -> Any | None:
    container = getattr(ps, container_name, None) if ps is not None else None
    return getattr(container, "MaxSize", None) if container is not None else None


def _container_values_match(ps: Any, container_name: str, size: int) -> bool:
    attr = _container_max_size(ps, container_name)
    if attr is None:
        return False
    for field in ("Value", "BaseValue"):
        try:
            if int(getattr(attr, field)) != int(size):
                return False
        except Exception:
            return False
    return True


def _safe_obj_name(obj: Any) -> str:
    for attr in ("Name", "name"):
        try:
            value = getattr(obj, attr)
            if value:
                return str(value)
        except Exception:
            pass
    try:
        return str(obj)
    except Exception:
        return "unknown"


def _player_key(ps: Any, fallback_index: int) -> str:
    """Return a key that changes when a player leaves and rejoins.

    PlayerId can be reused between joins, so include object identity/name when
    possible.  This prevents automatic inventory state from thinking a freshly
    joined PlayerState has already completed its stabilization passes.
    """
    parts: list[str] = [f"idx:{fallback_index}"]
    for field in ("PlayerId", "StableIndex"):
        try:
            parts.append(f"{field}:{getattr(ps, field)}")
        except Exception:
            pass
    parts.append(f"obj:{_safe_obj_name(ps)}")
    try:
        parts.append(f"addr:{getattr(ps, '_addr', id(ps))}")
    except Exception:
        parts.append(f"id:{id(ps)}")
    return "|".join(parts)


def _container_items_len(ps: Any, items_name: str) -> int | None:
    try:
        items_container = getattr(ps, items_name)
        items = getattr(items_container, "items")
        return len(items)
    except Exception:
        return None


def _inventory_looks_loaded(ps: Any) -> bool:
    """True once backpack/bank containers are writable.

    The previous auto path waited for owner/pawn and item arrays. In BL4 those
    signals are not reliable for every lobby/client state, which meant the
    automatic checkbox could stay armed but never actually write the values.
    Manual Apply works as soon as the containers exist, so automatic mode now
    uses the same readiness rule and keeps correcting resets during stabilization.
    """
    if ps is None:
        return False
    for container_name in ("BackpackContainer", "BankContainer"):
        container = getattr(ps, container_name, None)
        if container is None or getattr(container, "MaxSize", None) is None:
            return False
    return True

def set_container_size_on_player_state(ps: Any, container_name: str, size: int) -> bool:
    if ps is None:
        raise RuntimeError("PlayerState is not available.")
    container = getattr(ps, container_name, None)
    if container is None:
        raise RuntimeError(f"{container_name} is not available on PlayerState.")
    max_size = getattr(container, "MaxSize", None)
    if max_size is None:
        raise RuntimeError(f"{container_name}.MaxSize is not available.")
    size = clamp_container_size(size)
    if not _set_attr_integer(max_size, size):
        raise RuntimeError(f"Could not write {container_name}.MaxSize Value/BaseValue.")
    _bump_replication(container)
    _bump_replication(getattr(ps, container_name.replace("Container", "Items"), None))
    return True


def set_backpack_size_for_player_state(ps: Any, size: int) -> bool:
    return set_container_size_on_player_state(ps, "BackpackContainer", size)


def set_bank_size_for_player_state(ps: Any, size: int) -> bool:
    return set_container_size_on_player_state(ps, "BankContainer", size)


def set_inventory_sizes_for_player_state(ps: Any, backpack_size: int, bank_size: int) -> tuple[bool, bool]:
    bp = set_backpack_size_for_player_state(ps, backpack_size)
    bank = set_bank_size_for_player_state(ps, bank_size)
    return bp, bank


def set_inventory_sizes_for_party_index(index: int | None, backpack_size: int, bank_size: int) -> str:
    ps = get_player_state_by_party_index(index)
    if ps is None:
        raise RuntimeError("Selected party player was not found.")
    name = _gbc_resolve_player_display_name(ps)
    set_inventory_sizes_for_player_state(ps, backpack_size, bank_size)
    return name


def set_inventory_sizes_for_all_party(backpack_size: int, bank_size: int) -> int:
    count = 0
    errors: list[str] = []
    for _idx, name, ps in get_party_player_states():
        try:
            set_inventory_sizes_for_player_state(ps, backpack_size, bank_size)
            count += 1
        except Exception as exc:
            errors.append(f"{name}: {exc!r}")
    if errors:
        _log("Some inventory size updates failed: " + "; ".join(errors[:4]))
    return count


# State used by the BLImGui panel for automatic party application.
_auto_state: dict[str, dict[str, Any]] = {}
_auto_last_sizes: tuple[int, int] | None = None


def auto_apply_inventory_sizes_if_needed(enabled: bool, backpack_size: int, bank_size: int, *, source: str = "manual") -> int:
    """Deferred automatic capacity apply for current party members.

    Runs from the BLImGui draw path, not a background thread.  It waits for the
    inventory containers to look loaded, then waits a further grace period before
    writing.  After that it keeps reapplying only while values are mismatched or
    during the stabilization window, so late bank resets get corrected without
    permanently spamming writes.
    """
    global _auto_state, _auto_last_sizes
    if not enabled:
        _auto_state = {}
        _auto_last_sizes = None
        return 0

    bp_size = clamp_container_size(backpack_size, _DEFAULT_BACKPACK_SIZE)
    bank_size = clamp_container_size(bank_size, _DEFAULT_BANK_SIZE)
    sizes = (bp_size, bank_size)
    if sizes != _auto_last_sizes:
        _auto_state = {}
        _auto_last_sizes = sizes

    now = time.monotonic()
    players = get_party_player_states()
    live_keys: set[str] = set()
    applied = 0

    for idx, name, ps in players:
        key = _player_key(ps, idx)
        live_keys.add(key)
        state = _auto_state.setdefault(
            key,
            {
                "seen": now,
                "ready_since": None,
                "last": 0.0,
                "last_log": 0.0,
                "name": name,
            },
        )
        state["name"] = name

        if not _inventory_looks_loaded(ps):
            state["ready_since"] = None
            continue

        if state.get("ready_since") is None:
            state["ready_since"] = now
            continue

        ready_since = float(state.get("ready_since") or now)
        if now - ready_since < _AUTO_DEFER_SECONDS:
            continue
        if now - float(state.get("last", 0.0)) < _AUTO_RETRY_SECONDS:
            continue

        backpack_matches = _container_values_match(ps, "BackpackContainer", bp_size)
        bank_matches = _container_values_match(ps, "BankContainer", bank_size)
        # A rebuilt/reset container becomes a mismatch and will still be fixed.
        # Never call into native replication code merely to rewrite an already
        # matching value; doing so every 0.75 s made travel/lobby teardown race
        # stale PlayerState/container UObjects.
        if backpack_matches and bank_matches:
            continue

        try:
            set_inventory_sizes_for_player_state(ps, bp_size, bank_size)
            state["last"] = now
            applied += 1
        except Exception as exc:
            state["last"] = now
            if now - float(state.get("last_log", 0.0)) > 10.0:
                state["last_log"] = now
                _log(f"Automatic inventory size update failed for {name}: {exc!r}")

    # Drop players who left.
    for key in list(_auto_state):
        if key not in live_keys:
            _auto_state.pop(key, None)

    return applied


_last_inventory_tick = 0.0


def game_thread_inventory_tick() -> None:
    """Apply auto inventory sizes on the game thread only (never a Python worker)."""
    global _last_background_log, _last_inventory_tick
    if _background_stop or not _background_started:
        return
    now = time.monotonic()
    if now - _last_inventory_tick < _AUTO_POLL_SECONDS:
        return
    _last_inventory_tick = now
    try:
        if _get_game_state() is None:
            return
        settings = load_inventory_settings()
        if not settings.get("auto_inventory_sizes"):
            return
        count = auto_apply_inventory_sizes_if_needed(
            True,
            int(settings.get("backpack_size", _DEFAULT_BACKPACK_SIZE)),
            int(settings.get("bank_size", _DEFAULT_BANK_SIZE)),
            source="background",
        )
        if count and now - _last_background_log > 20.0:
            _last_background_log = now
            _log(
                f"Auto-applied inventory sizes to {count} party player(s): "
                f"backpack {settings.get('backpack_size')}, bank {settings.get('bank_size')}."
            )
    except Exception as exc:
        if now - _last_background_log > 20.0:
            _last_background_log = now
            _log(f"Automatic inventory tick error: {exc!r}")


def start_auto_inventory_worker() -> None:
    """Enable auto inventory — polled from mobility HUD tick (game thread)."""
    global _background_started, _background_stop
    _background_stop = False
    _background_started = True


def stop_auto_inventory_worker() -> None:
    global _background_stop
    _background_stop = True
