"""Golden chest open/close helper keybinds."""

from __future__ import annotations

import re
import time
from typing import Any, Optional

from mods_base import get_pc, keybind
from unrealsdk import find_all, find_object, logging
from unrealsdk.unreal import WrappedStruct

_PREFIX = "[Squ1ggs's Boosting Tools | GoldenChest]"
_STATE_KEY_PATH = "/Script/GbxEngine.GbxActorStateMachineStateKey"
_CLOSE_AFTER_DETACH_DELAY_S = 0.75
# Logo text spawns chests ~1400uu out; open must cover that range (seed sits ~160uu).
_OPEN_RADIUS_UU = 6000.0
# Delayed close must run on the game thread (BP tick), never threading.Timer —
# Timer callbacks calling UObject methods crash the game.
_pending_close_due: float = 0.0
_pending_close_script: Any | None = None
_pending_close_scripts: list[Any] = []
# AI / logo chests we have seen (find_all alone often misses older oak_spawnai copies).
_RECENT_GOLDEN_CHESTS: list[Any] = []
_MAX_RECENT = 48
_CHEST_LIST_CACHE: list[Any] = []
_CHEST_LIST_CACHE_AT: float = 0.0
_CHEST_LIST_CACHE_TTL_S = 1.75
_NUMBERED_CHEST_RE = re.compile(r"lootable_goldenchest_\d+", re.I)


def _log(msg: str, *args: Any) -> None:
    logging.info(_PREFIX + " " + (msg % args if args else msg))


def _log_err(msg: str, *args: Any) -> None:
    logging.error(_PREFIX + " " + (msg % args if args else msg))


def _get_player_pawn() -> Optional[Any]:
    pc = get_pc()
    if pc is None:
        return None
    return getattr(pc, "OakCharacter", None) or getattr(pc, "Pawn", None)


def _distance_sq(a: Any, b: Any) -> float:
    dx = float(a.X - b.X)
    dy = float(a.Y - b.Y)
    dz = float(a.Z - b.Z)
    return dx * dx + dy * dy + dz * dz


def _is_golden_chest_actor(actor: Any) -> bool:
    text = str(actor or "").lower()
    return "lootable_goldenchest" in text or "goldenchest" in text


def _is_map_seed_chest(chest: Any) -> bool:
    """True for PersistentLevel.Lootable_GoldenChest (no instance suffix)."""
    text = str(chest or "")
    low = text.lower()
    if "lootable_goldenchest_" in low:
        return False
    return low.endswith("lootable_goldenchest'") or low.endswith("lootable_goldenchest")


def remember_golden_chest(actor: Any) -> None:
    """Keep AI-spawned chests discoverable after find_all drops older instances."""
    if actor is None or not _is_golden_chest_actor(actor):
        return
    key = str(actor)
    global _RECENT_GOLDEN_CHESTS
    _RECENT_GOLDEN_CHESTS = [c for c in _RECENT_GOLDEN_CHESTS if str(c) != key]
    _RECENT_GOLDEN_CHESTS.append(actor)
    if len(_RECENT_GOLDEN_CHESTS) > _MAX_RECENT:
        _RECENT_GOLDEN_CHESTS = _RECENT_GOLDEN_CHESTS[-_MAX_RECENT:]


def _script_from_chest(chest: Any) -> Optional[Any]:
    try:
        instances = getattr(getattr(chest, "ScriptData", None), "Instances", None)
        if instances:
            return instances[0]
    except Exception:
        return None
    return None


def _iter_find_all(class_name: str) -> list[Any]:
    try:
        return list(find_all(class_name, False))
    except TypeError:
        pass
    except Exception:
        pass
    try:
        return list(find_all(class_name))
    except Exception:
        return []


def _alive_from_spawner(spawner: Any) -> list[Any]:
    try:
        comp = spawner.GetSpawnerComponent()
    except Exception:
        return []
    for args in ((0, False), (0, True), (0,)):
        try:
            actors = comp.GetAliveActors(*args)
            try:
                return [actors[i] for i in range(len(actors))]
            except Exception:
                return list(actors)
        except Exception:
            continue
    return []


def _shape_pins_heavy() -> bool:
    """Many frozen shape pickups — skip full LootableObject find_all on chest open."""
    try:
        from Squ1ggsBoostingTools.loot_shapes import held_pin_count

        return int(held_pin_count()) >= 140
    except Exception:
        return False


def _list_golden_chest_quick() -> list[Any]:
    """Fast path: remembered spawns + script outers + logo deploys (no world-wide LootableObject scan)."""
    chests: list[Any] = []
    seen: set[str] = set()

    def _add(actor: Any) -> None:
        if actor is None or not _is_golden_chest_actor(actor):
            return
        key = str(actor)
        if key in seen:
            return
        seen.add(key)
        chests.append(actor)
        remember_golden_chest(actor)

    for actor in list(_RECENT_GOLDEN_CHESTS):
        _add(actor)

    for script_cls in ("Script_Lootable_GoldenChest_C", "Script_Lootable_GoldenChest"):
        try:
            for script in _iter_find_all(script_cls):
                try:
                    _add(getattr(script, "Outer", None))
                except Exception:
                    continue
        except Exception:
            continue

    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as oak  # noqa: PLC0415
    except Exception:
        oak = None
    if oak is not None:
        try:
            for deployed in getattr(oak, "_SPAWNED", []) or []:
                actor = getattr(deployed, "actor", None)
                label = str(getattr(deployed, "label", "") or "").lower()
                if label == "barrel_logo" or "goldenchest" in label or "golden" in label:
                    _add(actor)
                elif _is_golden_chest_actor(actor):
                    _add(actor)
        except Exception:
            pass
    return chests


def _list_golden_chest_actors(*, allow_full_scan: bool = True) -> list[Any]:
    global _CHEST_LIST_CACHE, _CHEST_LIST_CACHE_AT
    now = time.monotonic()
    heavy = _shape_pins_heavy()
    if heavy:
        quick = _list_golden_chest_quick()
        if quick:
            return quick
        if not allow_full_scan:
            return quick
    elif (
        _CHEST_LIST_CACHE
        and now - float(_CHEST_LIST_CACHE_AT or 0.0) < float(_CHEST_LIST_CACHE_TTL_S)
    ):
        return list(_CHEST_LIST_CACHE)

    chests: list[Any] = []
    seen: set[str] = set()

    def _add(actor: Any) -> None:
        if actor is None or not _is_golden_chest_actor(actor):
            return
        key = str(actor)
        if key in seen:
            return
        seen.add(key)
        chests.append(actor)
        remember_golden_chest(actor)

    if not heavy:
        for actor in _list_golden_chest_quick():
            _add(actor)

    try:
        for obj in _iter_find_all("LootableObject"):
            _add(obj)
    except Exception as e:
        _log_err("Could not scan LootableObject instances: %s", e)

    # Dump path: Script_Lootable_GoldenChest_C lives under each chest Outer.
    for script_cls in ("Script_Lootable_GoldenChest_C", "Script_Lootable_GoldenChest"):
        try:
            for script in _iter_find_all(script_cls):
                try:
                    _add(getattr(script, "Outer", None))
                except Exception:
                    continue
        except Exception:
            continue

    for actor in list(_RECENT_GOLDEN_CHESTS):
        _add(actor)

    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as oak  # noqa: PLC0415
    except Exception:
        oak = None
    if oak is not None:
        try:
            for deployed in getattr(oak, "_SPAWNED", []) or []:
                actor = getattr(deployed, "actor", None)
                label = str(getattr(deployed, "label", "") or "").lower()
                if label == "barrel_logo" or "goldenchest" in label or "golden" in label:
                    _add(actor)
                elif _is_golden_chest_actor(actor):
                    _add(actor)
                source = getattr(deployed, "source", None)
                if source is not None:
                    for alive in _alive_from_spawner(source):
                        _add(alive)
        except Exception:
            pass

    # Nearby OakSpawner alive rows (covers AI chests find_all missed).
    pawn = _get_player_pawn()
    player_loc = None
    if pawn is not None:
        try:
            player_loc = pawn.K2_GetActorLocation()
        except Exception:
            player_loc = None
    if player_loc is not None:
        max_sq = (_OPEN_RADIUS_UU * 2.0) ** 2
        try:
            for spawner in _iter_find_all("OakSpawner"):
                try:
                    sl = spawner.K2_GetActorLocation()
                    if _distance_sq(sl, player_loc) > max_sq:
                        continue
                except Exception:
                    continue
                for alive in _alive_from_spawner(spawner):
                    _add(alive)
        except Exception:
            pass

    _CHEST_LIST_CACHE = list(chests)
    _CHEST_LIST_CACHE_AT = now
    return chests


def _chests_in_radius(chests: list[Any], radius_uu: float) -> list[tuple[float, Any]]:
    pawn = _get_player_pawn()
    if pawn is None:
        return [(0.0, c) for c in chests]
    try:
        player_loc = pawn.K2_GetActorLocation()
    except Exception:
        return [(0.0, c) for c in chests]
    out: list[tuple[float, Any]] = []
    max_sq = float(radius_uu) * float(radius_uu)
    for chest in chests:
        try:
            chest_loc = chest.K2_GetActorLocation()
            dist_sq = _distance_sq(chest_loc, player_loc)
        except Exception:
            continue
        if dist_sq <= max_sq:
            out.append((dist_sq, chest))
    out.sort(key=lambda row: row[0])
    return out


def _is_logo_spawned_chest(chest: Any) -> bool:
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as oak  # noqa: PLC0415
    except Exception:
        return False
    try:
        chest_key = str(chest)
        for deployed in getattr(oak, "_SPAWNED", []) or []:
            actor = getattr(deployed, "actor", None)
            if actor is None:
                continue
            if actor is not chest and str(actor) != chest_key:
                continue
            return str(getattr(deployed, "label", "") or "").lower() == "barrel_logo"
    except Exception:
        return False
    return False


def _is_spawned_or_logo_chest(chest: Any) -> bool:
    if _is_logo_spawned_chest(chest):
        return True
    return bool(_NUMBERED_CHEST_RE.search(str(chest or "")))


def _open_script(script: Any) -> bool:
    state_key = _new_state_key()
    if state_key is None:
        return False
    try:
        # Dump-backed: Success then Open (same as live map chest).
        script.Success__OnStateEnabled(state_key, False)
        script.Open__OnStateEnabled(state_key, False)
        _log("Called Success + Open on %s", script)
        return True
    except Exception as e:
        _log_err("Open failed on %s: %s", script, e)
        return False


def _new_state_key() -> Optional[WrappedStruct]:
    try:
        return WrappedStruct(find_object("ScriptStruct", _STATE_KEY_PATH))
    except Exception as e:
        _log_err("Could not create GbxActorStateMachineStateKey: %s", e)
        return None


def open_golden_chest() -> tuple[bool, str]:
    """Open every scripted golden chest in range (spawned copies + logos + nearby map).

    Live log showed Open only seeing one oak_spawnai copy plus the map seed —
    older AI copies fall out of find_all. We now also walk scripts/Outers,
    remembered spawns, _SPAWNED, and nearby OakSpawner alive actors.
    """
    chests = _list_golden_chest_actors()
    if not chests:
        return False, "No golden chest nearby (spawn world text / World tools, or stand near a map chest)."

    ranked = _chests_in_radius(chests, _OPEN_RADIUS_UU)
    if not ranked:
        ranked = _chests_in_radius(chests, _OPEN_RADIUS_UU * 2.0)
    if not ranked:
        return False, "No golden chest in range."

    logo_rows = [(d, c) for d, c in ranked if _is_logo_spawned_chest(c)]
    spawned_rows = [(d, c) for d, c in ranked if _is_spawned_or_logo_chest(c) and not _is_logo_spawned_chest(c)]
    seed_rows = [(d, c) for d, c in ranked if _is_map_seed_chest(c)]
    other_rows = [
        (d, c)
        for d, c in ranked
        if not _is_logo_spawned_chest(c) and not _is_spawned_or_logo_chest(c) and not _is_map_seed_chest(c)
    ]
    # Prefer AI / logo copies first; still open the map seed if it is in range.
    ordered = logo_rows + spawned_rows + other_rows + seed_rows

    opened = 0
    opened_scripts: set[str] = set()
    skipped_no_script = 0
    for dist_sq, chest in ordered:
        script = _script_from_chest(chest)
        if script is None:
            skipped_no_script += 1
            continue
        script_key = str(script)
        if script_key in opened_scripts:
            continue
        if _open_script(script):
            opened_scripts.add(script_key)
            opened += 1
            remember_golden_chest(chest)
            _log("Opened chest at %.0f uu: %s", float(dist_sq) ** 0.5, chest)

    if opened <= 0:
        if skipped_no_script:
            return False, (
                f"Found {skipped_no_script} golden chest mesh(es) but none had ScriptData yet. "
                "Wait a moment after world-text spawn, or open the seed chest once."
            )
        return False, "No golden chest script available to open."

    spawned_n = sum(1 for _, c in spawned_rows if _script_from_chest(c) is not None)
    logo_n = sum(1 for _, c in logo_rows if _script_from_chest(c) is not None)
    bits = [f"Opened {opened} golden chest(s)"]
    if spawned_n:
        bits.append(f"{spawned_n} spawned")
    if logo_n:
        bits.append(f"{logo_n} logo")
    if seed_rows:
        bits.append(f"{len(seed_rows)} map")
    return True, " — ".join(bits) if len(bits) == 1 else f"{bits[0]} ({', '.join(bits[1:])})."


def _finish_close_on_script(script: Any) -> None:
    try:
        script.SetScriptStateEnabled("Open", False)
        script.SetScriptStateEnabled("Idle", True)
        _log("Called Open=false + Idle=true on %s", script)
    except Exception as close_e:
        _log_err("Close failed: %s", close_e)


def close_golden_chest() -> tuple[bool, str]:
    global _pending_close_due, _pending_close_script, _pending_close_scripts
    chests = _list_golden_chest_actors()
    ranked = _chests_in_radius(chests, _OPEN_RADIUS_UU) if chests else []
    if not ranked:
        ranked = _chests_in_radius(chests, _OPEN_RADIUS_UU * 2.0) if chests else []
    # Same policy as open: every scripted chest in range (not just nearest).
    scripts: list[Any] = []
    seen_scripts: set[str] = set()
    for _dist, chest in ranked:
        script = _script_from_chest(chest)
        if script is None:
            continue
        key = str(script)
        if key in seen_scripts:
            continue
        seen_scripts.add(key)
        try:
            script.DetachUnclaimedLoot()
            _log("Called DetachUnclaimedLoot on %s", script)
        except Exception as e:
            _log_err("DetachUnclaimedLoot failed; continuing close: %s", e)
        scripts.append(script)
        remember_golden_chest(chest)
    if not scripts:
        return False, "No golden chest nearby to close."

    _pending_close_scripts = list(scripts)
    _pending_close_script = scripts[0]
    _pending_close_due = time.monotonic() + float(_CLOSE_AFTER_DETACH_DELAY_S)
    _log("Scheduled close in %.2fs after detach for %d chest(s).", _CLOSE_AFTER_DETACH_DELAY_S, len(scripts))
    return True, f"Golden chest close requested for {len(scripts)} chest(s)."


def golden_chest_tick() -> None:
    """Process delayed close on the game thread."""
    global _pending_close_due, _pending_close_script, _pending_close_scripts
    if not _pending_close_scripts and _pending_close_script is None:
        return
    if time.monotonic() < float(_pending_close_due or 0.0):
        return
    scripts = list(_pending_close_scripts) if _pending_close_scripts else []
    if _pending_close_script is not None and _pending_close_script not in scripts:
        scripts.append(_pending_close_script)
    _pending_close_scripts = []
    _pending_close_script = None
    _pending_close_due = 0.0
    for script in scripts:
        _finish_close_on_script(script)


# Back-compat aliases used by keybinds / older imports.
_open_golden_chest = lambda: open_golden_chest()  # noqa: E731
_close_golden_chest = lambda: close_golden_chest()  # noqa: E731


def _open_golden_chest_keybind(_=None) -> None:
    open_golden_chest()


def _close_golden_chest_keybind(_=None) -> None:
    close_golden_chest()


OPEN_GOLDEN_CHEST_KEY = keybind(
    "Open Golden Chest",
    "NumPadNine",
    callback=_open_golden_chest_keybind,
    display_name="Open Golden Chest",
    description="Opens all scripted golden chests in range (spawned + logo + nearby map).",
)

CLOSE_GOLDEN_CHEST_KEY = keybind(
    "Close Golden Chest",
    "NumPadZero",
    callback=_close_golden_chest_keybind,
    display_name="Close Golden Chest",
    description="Detaches loot and closes all golden chests in range.",
)
