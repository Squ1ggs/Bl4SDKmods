"""Post-spawn activation for interactive objects (IO_*).

``oak_spawnai`` only places the actor — script states stay idle. Carryables often
work without activation; AscensionBeam / switches / chests need SetScriptStateEnabled
+ Activate/SetUsable (same path as Squ1ggs ``oak_activate_last``).

Some machines (Maurice's legendary vending, player bank, etc.) need a second
``oak_spawn`` PersistentLevel pass after ``oak_spawnai`` before they are usable.
That dual sequence is crash-guarded and deferred across game ticks.
"""

from __future__ import annotations

from typing import Any

# Machines that historically need oak_spawnai first, then a world PersistentLevel
# duplicate. Keep this conservative — only known crashy / locked IOs.
# Do NOT put goldenchest / Lootable_* here: substring match would dual-spawn
# Lootable_GoldenChest and freeze via PersistentLevel oak_spawn of the map chest.
# Do NOT put playerbank here: dual world duplicate freezes the host and kicks guests.
_DUAL_WORLD_SPAWN_SUBSTR: tuple[str, ...] = (
    # Maurice / Black Market are OakVendingMachine world-placed only — not dual.
    "vendingmachine_munitions_splice",
    "lostloot",
)

_WORLD_P_IO_PREFIX = "/Game/Maps/WorldLevels/World_P.World_P:PersistentLevel."

# Proven working machine from unrealsdk dump: IO_VendingMachine_BlackMarket
# (Maurice's Black Market). Legend_Legendary is the same in-world vendor —
# keep aliases pointed at BlackMarket so the list is one clear row.
# Values: (spawnai_name, persistent_short).
_OAK_DUAL_VENDING: dict[str, tuple[str, str]] = {
    "io_vendingmachine_blackmarket": ("io_VendingMachine_BlackMarket", "IO_VendingMachine_BlackMarket"),
    "vendingmachine_blackmarket": ("io_VendingMachine_BlackMarket", "IO_VendingMachine_BlackMarket"),
    "blackmarket": ("io_VendingMachine_BlackMarket", "IO_VendingMachine_BlackMarket"),
    "black_market": ("io_VendingMachine_BlackMarket", "IO_VendingMachine_BlackMarket"),
    # Legacy / alternate names → same working Black Market dual.
    "io_vendingmachine_legend_legendary": (
        "io_VendingMachine_BlackMarket",
        "IO_VendingMachine_BlackMarket",
    ),
    "vendingmachine_legend_legendary": (
        "io_VendingMachine_BlackMarket",
        "IO_VendingMachine_BlackMarket",
    ),
    "maurice": ("io_VendingMachine_BlackMarket", "IO_VendingMachine_BlackMarket"),
    "maurices": ("io_VendingMachine_BlackMarket", "IO_VendingMachine_BlackMarket"),
}

# Hide from EXE/catalog — one Maurice's Black Market row only.
_HIDDEN_IO_TOKENS: frozenset[str] = frozenset(
    {
        "io_vendingmachine_legend_a",
        "vendingmachine_legend_a",
        "io_vendingmachine_legend_legendary",
        "vendingmachine_legend_legendary",
    }
)

# Prefer game-data casing for PersistentLevel / template needles.
_CANONICAL_IO_TOKENS: dict[str, str] = {
    "io_vendingmachine_blackmarket": "IO_VendingMachine_BlackMarket",
    "io_playerbank": "IO_PlayerBank",
    "io_vendingmachine_legend_legendary": "IO_VendingMachine_Legend_Legendary",
    "io_vendingmachine_legend_a": "IO_VendingMachine_Legend_A",
    "io_vendingmachine_munitions_splice": "IO_VendingMachine_Munitions_Splice",
    "lootable_goldenchest": "Lootable_GoldenChest",
}

# Token substring (lower) → (enable states, disable states)
_IO_STATE_PRESETS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "playerbank": (
        ("ActiveIdle", "Unlocked", "Available", "Enabled", "Usable", "Useable", "Interactive", "InteractionEnabled", "Active", "Idle"),
        ("Locked", "Disabled", "Inactive", "Blocked", "Unavailable", "IsInUse"),
    ),
    "player_bank": (
        ("ActiveIdle", "Unlocked", "Available", "Enabled", "Usable", "Useable", "Interactive", "InteractionEnabled", "Active", "Idle"),
        ("Locked", "Disabled", "Inactive", "Blocked", "Unavailable", "IsInUse"),
    ),
    "ascensionbeam_singletp": (
        ("Active", "Enabled", "Idle", "Ready"),
        ("Disabled", "Deactivated", "Inactive"),
    ),
    "ascensionbeam_manager": (
        ("Enabled", "Active", "Idle"),
        ("Disabled", "Deactivated"),
    ),
    "ascensionbeam_v4": (
        ("Idle", "Active", "Start", "Enabled"),
        ("Disabled", "Deactivated", "Complete"),
    ),
    "ascensionbeam": (
        ("Activated", "Activating", "Active", "Enabled", "Idle"),
        ("Deactivated", "Disabled", "Inactive"),
    ),
    "ascensioncapsule": (
        ("Active", "Enabled", "Idle", "Open"),
        ("Disabled", "Deactivated", "Locked"),
    ),
    "vending": (
        ("Active", "ActiveIdle", "ActiveIdle_Anim", "Enabled", "Usable", "Useable"),
        ("Disabled", "IsInUse", "InUse_Anim", "Dispensing_Anim"),
    ),
    "chest": (
        ("Idle", "Active", "ActiveIdle", "Enabled", "Usable", "Unlocked", "Open"),
        ("Locked", "Disabled", "IsInUse"),
    ),
    "switch": (
        ("Active", "Enabled", "Usable", "Useable", "Interactive", "Idle"),
        ("Disabled", "Locked", "Inactive"),
    ),
    "door": (
        ("Active", "Enabled", "Open", "Unlocked", "Idle"),
        ("Locked", "Disabled", "Closed"),
    ),
}

_GENERIC_ENABLE = (
    "Active",
    "ActiveIdle",
    "ActiveIdle_Anim",
    "Enabled",
    "Enable",
    "Usable",
    "Useable",
    "Interactive",
    "InteractionEnabled",
    "Available",
    "Unlocked",
    "Idle",
    "Ready",
    "Open",
)
_GENERIC_DISABLE = (
    "IsInUse",
    "InUse_Anim",
    "Dispensing_Anim",
    "Disabled",
    "Disable",
    "Inactive",
    "Locked",
    "Blocked",
    "Unavailable",
    "Deactivated",
)


def _is_black_market_io(code: str) -> bool:
    low = (code or "").lower().replace("-", "_").replace(" ", "")
    return "blackmarket" in low


def _states_for_code(code: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    low = (code or "").strip().lower().replace("-", "_")
    best: tuple[tuple[str, ...], tuple[str, ...]] | None = None
    best_len = -1
    for key, pair in _IO_STATE_PRESETS.items():
        if key in low and len(key) > best_len:
            best = pair
            best_len = len(key)
    return best if best is not None else (_GENERIC_ENABLE, _GENERIC_DISABLE)


def is_io_code(code: str) -> bool:
    low = (code or "").strip().lower()
    return (
        low.startswith("io_")
        or low.startswith("io.")
        or low.startswith("lootable_")
        or "persistentlevel.io_" in low
        or "persistentlevel.lootable_" in low
        or low.startswith("persistentlevel.io_")
        or low.startswith("persistentlevel.lootable_")
    )


def short_io_token(token: str) -> str:
    """Normalize paths / aliases to a short IO_* / Lootable_* token when possible."""
    raw = (token or "").strip()
    if not raw:
        return ""
    if ":" in raw:
        raw = raw.rsplit(":", 1)[-1]
    if "." in raw:
        tail = raw.rsplit(".", 1)[-1]
        if tail.lower().startswith(("io_", "lootable_")):
            return tail
    return raw


def canonical_io_token(token: str) -> str:
    """Short IO token with preferred in-game casing when known."""
    short = short_io_token(token)
    if not short:
        return ""
    return _CANONICAL_IO_TOKENS.get(short.lower().replace("-", "_"), short)


def _oak_dual_key(token: str) -> str:
    short = canonical_io_token(token) or short_io_token(token)
    return short.lower().replace("-", "_").replace(" ", "")


def is_hidden_io_token(token: str) -> bool:
    """True for catalog rows that must not appear in EXE/UI dropdowns."""
    return _oak_dual_key(token) in _HIDDEN_IO_TOKENS


def is_audio_io_token(token: str, label: str = "") -> bool:
    """Sound-only / ambient IO actors — not placeable props."""
    short = short_io_token(token).lower().replace("-", "_")
    blob = f"{short} {(label or '').strip()}".lower().replace("-", "_")
    if short.startswith("io_audio_") or short.startswith("audio_io_"):
        return True
    if short.startswith("mandolin_io_audio"):
        return True
    if "audio_io_" in short:
        return True
    if short.startswith("io_") and "_audio_" in short:
        return True
    if blob.startswith("audio ") or " audio " in f" {blob} ":
        return True
    return False


def is_catalog_excluded_io(token: str, label: str = "") -> bool:
    """Hide from EXE/in-game IO lists — non-visual or unsupported spawns."""
    if is_audio_io_token(token, label):
        return True
    short = short_io_token(token).lower().replace("-", "_")
    blob = f"{short} {(label or '').strip()}".lower()
    if "dialogplacer" in blob:
        return True
    return False


def spawn_io_prefers_ai(short: str, cmd: str = "") -> bool:
    """Prefer oak_spawnai — world PersistentLevel paths fail or freeze (esp. PlayerBank)."""
    key = short_io_token(short).lower().replace("-", "_")
    # Always AI for bank — dual/world duplicate hitch kicks co-op lobbies.
    if "playerbank" in key or key in ("bank", "io_playerbank", "player_bank"):
        return True
    try:
        from Squ1ggsBoostingTools.dev_tools import is_debug_cam_active  # noqa: PLC0415
        from Squ1ggsBoostingTools import spawn_targets  # noqa: PLC0415

        at_cam = bool(is_debug_cam_active()) or str(spawn_targets.mode() or "").strip().lower() == "freecam"
    except Exception:
        at_cam = False
    if not at_cam:
        return False
    if _oak_dual_key(short) in _OAK_DUAL_VENDING:
        return False
    if str(cmd or "").strip().lower().startswith(("oak_dual ", "asd_dual ")):
        return False
    return bool(short_io_token(short))


def is_oak_dual_vending(token: str) -> bool:
    """True for Black Market / Maurice — oak_spawnai then PersistentLevel oak_spawn."""
    return _oak_dual_key(token) in _OAK_DUAL_VENDING


# Back-compat alias used by older call sites.
is_asd_dual_vending = is_oak_dual_vending


def oak_dual_names(token: str) -> tuple[str, str] | None:
    """Return (spawnai_name, PersistentLevel short IO_*) for dual vending machines."""
    return _OAK_DUAL_VENDING.get(_oak_dual_key(token))


def oak_dual_cmd(token: str) -> str:
    short = (oak_dual_names(token) or (None, canonical_io_token(token) or short_io_token(token)))[1]
    return f"oak_dual {short}" if short else ""


def oak_prepare_vending_packages(token: str) -> tuple[bool, str]:
    """Load Black Market / Maurice packages before spawnai or world steps (dump-first)."""
    names = oak_dual_names(token)
    if not names:
        return False, f"not an oak dual vending token: {token}"
    spawnai_name, canon = names
    try:
        from .oak_spawn import _actor_load_paths  # noqa: PLC0415
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
    except Exception as ex:  # noqa: BLE001
        return False, f"BL4 Oak Spawner unavailable: {ex}"
    try:
        loads = list(_actor_load_paths(spawnai_name)) + list(_actor_load_paths(canon))
        load_fn = getattr(ssp, "_spawnai_load_packages", None)
        if callable(load_fn):
            load_fn(spawnai_name, loads, lean=False)
            load_fn(canon, loads, lean=False)
            return True, f"loaded packages for {canon}"
    except Exception as ex:  # noqa: BLE001
        return False, f"package load failed: {type(ex).__name__}: {ex}"
    return True, f"package load skipped for {canon}"


def oak_spawnai_vending(
    token: str,
    *,
    distance: float = 350.0,
    spacing: float = 125.0,
) -> tuple[bool, str]:
    """Step 1: async ``oak_spawnai`` (same fire style as mob/IO spawner — no hitch)."""
    names = oak_dual_names(token)
    if not names:
        return False, f"not an oak dual vending token: {token}"
    spawnai_name, _canon = names
    try:
        from .oak_spawn import _actor_load_paths, spawn_actor_def  # noqa: PLC0415
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
    except Exception as ex:  # noqa: BLE001
        return False, f"BL4 Oak Spawner unavailable: {ex}"
    try:
        loads = list(_actor_load_paths(spawnai_name)) + list(_actor_load_paths("IO_VendingMachine_BlackMarket"))
        load_fn = getattr(ssp, "_spawnai_load_packages", None)
        if callable(load_fn):
            load_fn(spawnai_name, loads, lean=False)
            load_fn("IO_VendingMachine_BlackMarket", loads, lean=False)
    except Exception:
        pass
    try:
        ok, msg = spawn_actor_def(
            spawnai_name,
            count=1,
            distance=float(distance),
            spacing=float(spacing),
            allow_summon_fallback=False,
            fast_path=True,
            async_fire=True,
        )
    except Exception as ex:  # noqa: BLE001
        return False, f"oak_spawnai failed safely: {type(ex).__name__}: {ex}"
    fired = bool(ok) or ("stream" in msg.lower()) or msg.lower().startswith("oak_")
    if fired:
        return True, f"oak_spawnai {spawnai_name}: {msg}"
    return False, f"oak_spawnai {spawnai_name}: {msg}"


def _wake_vending_actor(ssp: Any, actor: Any, label: str) -> tuple[bool, str]:
    """Force script/usability wake on a placed vending machine (blank → usable)."""
    if not _actor_still_valid(actor):
        return False, "invalid actor"
    if _is_black_market_io(label):
        try:
            from Squ1ggsBoostingTools import black_market as bm

            bm.restore_black_market_visibility(actor)
            bm.remember_placed_black_market(actor)
        except Exception:
            pass
    try:
        script_count = int(getattr(ssp, "_script_count", lambda _a: 0)(actor) or 0)
    except Exception:
        script_count = 0
    a_ok, a_msg = activate_spawned_io(label, actor=actor)
    poke = getattr(ssp, "_poke_actor_enabled", None)
    if callable(poke):
        try:
            poke(actor)
        except Exception:
            pass
    return True, f"wake {label} scripts={script_count}; {a_msg}"


def oak_wake_vending(token: str) -> tuple[bool, str]:
    """Delayed wake for blank Maurice / Black Market shells after dual settle."""
    names = oak_dual_names(token)
    if not names:
        return False, f"not an oak dual vending token: {token}"
    _spawnai_name, canon = names
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
    except Exception as ex:  # noqa: BLE001
        return False, f"BL4 Oak Spawner unavailable: {ex}"
    path = f"{_WORLD_P_IO_PREFIX}{canon}"
    find_exact = getattr(ssp, "_find_exact_loaded_io", None)
    source = None
    if callable(find_exact):
        try:
            _cls, source, _cn = find_exact(path, class_override="OakVendingMachine")
            if source is None:
                _cls, source, _cn = find_exact(path, class_override="OakInteractiveObject")
        except Exception:
            source = None
    msgs: list[str] = []
    if source is not None:
        _ok, msg = _wake_vending_actor(ssp, source, canon)
        msgs.append(msg)
    # Also wake newest spawned duplicate matching this machine.
    spawned = getattr(ssp, "_SPAWNED", None) or []
    needle = canon.lower()
    for item in reversed(list(spawned)[-8:]):
        actor = getattr(item, "actor", None)
        label = str(getattr(item, "label", "") or "")
        text = f"{actor} {label}".lower()
        if needle not in text and "vendingmachine" not in text:
            continue
        if actor is source:
            continue
        _ok, msg = _wake_vending_actor(ssp, actor, canon)
        msgs.append(msg)
        break
    if msgs:
        return True, "; ".join(msgs)
    return False, f"wake waiting for {canon}"


def _vending_already_at_player(actor: Any) -> bool:
    try:
        from mods_base import get_pc

        pc = get_pc()
        pawn = getattr(pc, "OakCharacter", None) or getattr(pc, "Pawn", None) if pc is not None else None
        if pawn is None or actor is None:
            return False
        loc = pawn.K2_GetActorLocation()
        ml = actor.K2_GetActorLocation()
        dx = float(loc.X) - float(ml.X)
        dy = float(loc.Y) - float(ml.Y)
        dz = float(loc.Z) - float(ml.Z)
        return (dx * dx + dy * dy + dz * dz) <= (700.0 * 700.0)
    except Exception:
        return False


def oak_spawn_vending_world(
    token: str,
    *,
    distance: float = 350.0,
    spacing: float = 125.0,
    activate: bool = True,
) -> tuple[bool, str]:
    """Step 2: prefer move+wake the live PersistentLevel IO (usable first try)."""
    names = oak_dual_names(token)
    if not names:
        return False, f"not an oak dual vending token: {token}"
    _spawnai_name, canon = names
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
    except Exception as ex:  # noqa: BLE001
        return False, f"BL4 Oak Spawner unavailable: {ex}"
    path = f"{_WORLD_P_IO_PREFIX}{canon}"
    find_exact = getattr(ssp, "_find_exact_loaded_io", None)
    source = None
    class_name = "OakVendingMachine"
    if callable(find_exact):
        try:
            _cls, source, class_name = find_exact(path, class_override="OakVendingMachine")
            if source is None:
                _cls, source, class_name = find_exact(path, class_override="OakInteractiveObject")
        except Exception:
            source = None
    if source is None:
        return False, f"oak_spawn waiting for template {path} (retry next tick)"

    script_count = 0
    try:
        script_count = int(getattr(ssp, "_script_count", lambda _a: 0)(source) or 0)
    except Exception:
        script_count = 0

    if _is_black_market_io(canon):
        try:
            from Squ1ggsBoostingTools import black_market as bm

            bm._save_true_loc(source)
        except Exception:
            pass

    # Prefer relocate the live PersistentLevel shop once. If it is already at the
    # player's feet, duplicate instead so Spawn can place another machine.
    if script_count > 0:
        already_here = _is_black_market_io(canon) and _vending_already_at_player(source)
        if not already_here:
            bring = getattr(ssp, "_bring_live_actor_to_player", None)
            if callable(bring):
                try:
                    moved = bring(
                        source,
                        label=canon,
                        distance=float(distance),
                        z_offset=float(getattr(ssp, "_DEFAULT_Z_OFFSET", -100.0)),
                        scale=1.0,
                        activate=bool(activate),
                        enable=(),
                        disable=(),
                        delay=0.15,
                    )
                except Exception as ex:  # noqa: BLE001
                    _wake_vending_actor(ssp, source, canon)
                    return True, f"wake in-place {canon} scripts={script_count} ({type(ex).__name__})"
                if moved is not None and _actor_still_valid(moved):
                    _wake_vending_actor(ssp, moved, canon)
                    return True, f"relocated usable {canon} scripts={script_count} -> {moved}"
            _wake_vending_actor(ssp, source, canon)
            return True, f"woke PersistentLevel {canon} scripts={script_count}"

    deploy_fn = getattr(ssp, "_spawn_deployed_actor", None)
    if not callable(deploy_fn):
        return False, "oak_spawn path unavailable"
    try:
        actor = deploy_fn(
            path,
            class_override=class_name or "OakVendingMachine",
            distance=float(distance),
            z_offset=float(getattr(ssp, "_DEFAULT_Z_OFFSET", -100.0)),
            scale=1.0,
            delay=0.2 if activate else 0.0,
            enable=(),
            disable=(),
            generated_only=False,
            activate=bool(activate),
            count=1,
            spacing=float(spacing),
        )
    except Exception as ex:  # noqa: BLE001
        return False, f"oak_spawn failed safely: {type(ex).__name__}: {ex}"
    if actor is not None and _actor_still_valid(actor):
        _wake_vending_actor(ssp, actor, canon)
        if script_count <= 0:
            _wake_vending_actor(ssp, source, canon)
        return True, f"oak_spawn {canon} -> {actor} (shell scripts={script_count})"
    _wake_vending_actor(ssp, source, canon)
    return False, f"oak_spawn found no live template for {path}; woke shell"


def needs_dual_world_spawn(token: str) -> bool:
    """True for machines that need oak_spawnai then a PersistentLevel oak_spawn."""
    if is_oak_dual_vending(token):
        return False
    low = short_io_token(token).lower().replace("-", "_")
    return any(s in low for s in _DUAL_WORLD_SPAWN_SUBSTR)


def world_path_cmd(token: str) -> str:
    short = canonical_io_token(token)
    if not short:
        return ""
    return f"oak_spawn {_WORLD_P_IO_PREFIX}{short}"


def _actor_still_valid(actor: Any) -> bool:
    if actor is None:
        return False
    try:
        name = str(getattr(actor, "Name", "") or "")
        if not name or name.lower().startswith("none"):
            return False
    except Exception:
        return False
    try:
        is_valid = getattr(actor, "IsValid", None)
        if callable(is_valid) and not bool(is_valid()):
            return False
    except Exception:
        pass
    return True


def activate_spawned_io(code: str = "", actor: Any | None = None) -> tuple[bool, str]:
    """Enable script states + usability on a freshly spawned IO (or last Squ1ggs spawn).

    Fully guarded: activation failures return a message and must never crash BL4.
    """
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
    except Exception as ex:  # noqa: BLE001
        return False, f"BL4 Oak Spawner unavailable: {ex}"

    try:
        target = actor
        label = (code or "").strip()
        if target is None:
            spawned = getattr(ssp, "_SPAWNED", None) or []
            if not spawned:
                return False, "no spawned actor to activate"
            item = spawned[-1]
            target = getattr(item, "actor", None)
            if not label:
                label = str(getattr(item, "label", "") or "")
        if not _actor_still_valid(target):
            return False, "spawned actor missing or invalid"

        enable, disable = _states_for_code(label)
        # Also match short token from PersistentLevel.IO_* / full world paths.
        if "persistentlevel." in label.lower() or "/" in label:
            short = short_io_token(label)
            e2, d2 = _states_for_code(short)
            if e2 != _GENERIC_ENABLE:
                enable, disable = e2, d2
        # Merge Squ1ggs generic/preset lists when available.
        try:
            key_fn = getattr(ssp, "_alias_key", None)
            uniq = getattr(ssp, "_unique_states", None)
            key = key_fn(label) if callable(key_fn) else label.lower()
            presets = getattr(ssp, "_PRESET_ENABLE_STATES", {}) or {}
            generic = getattr(ssp, "_GENERIC_ENABLE_STATES", ()) or ()
            gdis = getattr(ssp, "_GENERIC_DISABLE_STATES", ()) or ()
            if callable(uniq):
                enable = uniq(enable, presets.get(key, ()), generic)
                disable = uniq(disable, gdis)
        except Exception:
            pass

        set_states = getattr(ssp, "_set_script_states", None)
        if not callable(set_states):
            return False, "Squ1ggs _set_script_states missing"
        set_states(target, enable, disable, debug=False)
        try:
            low = f"{label} {target}".lower()
            if "goldenchest" in low or "lootable_goldenchest" in low:
                from Squ1ggsBoostingTools.golden_chest_keybinds import remember_golden_chest  # noqa: PLC0415

                remember_golden_chest(target)
        except Exception:
            pass
        return True, f"activated {label or 'last IO'} (states={len(enable)})"
    except Exception as ex:  # noqa: BLE001
        return False, f"activate skipped (safe): {type(ex).__name__}: {ex}"


def _cache_recent_io_template(ssp: Any, short: str) -> None:
    """If spawnai just placed this IO, cache it so world oak_spawn can duplicate it."""
    cache_fn = getattr(ssp, "_cache_actor_def", None)
    if not callable(cache_fn):
        return
    needle = short.lower()
    spawned = getattr(ssp, "_SPAWNED", None) or []
    for item in reversed(list(spawned)):
        actor = getattr(item, "actor", None)
        if not _actor_still_valid(actor):
            continue
        label = str(getattr(item, "label", "") or "")
        text = f"{actor} {label}".lower()
        if needle in text or needle.replace("io_", "") in text:
            try:
                cache_fn(short, actor)
            except Exception:
                pass
            return


def safe_world_io_spawn(
    token: str,
    *,
    distance: float = 350.0,
    spacing: float = 125.0,
) -> tuple[bool, str]:
    """Duplicate a live PersistentLevel IO template near the player (crash-guarded)."""
    short = canonical_io_token(token) or short_io_token(token)
    if not short:
        return False, "empty IO token"
    low = short.lower().replace("-", "_")
    # PlayerBank live template clone freezes host / kicks lobby — never do it.
    if "playerbank" in low or low in ("bank", "io_playerbank"):
        try:
            a_ok, a_msg = activate_spawned_io(short)
            if a_ok:
                return True, f"player bank activate-only (no world duplicate): {a_msg}"
        except Exception as act_ex:  # noqa: BLE001
            return False, f"player bank: refused world duplicate; activate failed: {act_ex}"
        return False, "player bank: refused world PersistentLevel duplicate (use oak_spawnai)"
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415
    except Exception as ex:  # noqa: BLE001
        return False, f"BL4 Oak Spawner unavailable: {ex}"

    deploy_fn = getattr(ssp, "_spawn_deployed_actor", None)
    if not callable(deploy_fn):
        return False, "world deploy path unavailable"

    try:
        _cache_recent_io_template(ssp, short)
    except Exception:
        pass

    try:
        actor = deploy_fn(
            short,
            class_override=None,
            distance=float(distance),
            z_offset=float(getattr(ssp, "_DEFAULT_Z_OFFSET", -100.0)),
            scale=1.0,
            delay=0.0,
            enable=(),
            disable=(),
            generated_only=False,
            activate=False,
            count=1,
            spacing=float(spacing),
        )
    except Exception as ex:  # noqa: BLE001
        actor = None
        err = f"world oak_spawn failed safely: {type(ex).__name__}: {ex}"
    else:
        err = ""

    if actor is not None and _actor_still_valid(actor):
        return True, f"world oak_spawn: {short} -> {actor}"

    return False, err or f"world oak_spawn found no live template for {short}"


def spawn_and_activate_io(
    code: str,
    *,
    spawn_fn: Any,
) -> tuple[bool, str]:
    """Run ``spawn_fn(code)`` then activate script states for IO_* codes."""
    ok, msg = spawn_fn(code)
    if not ok:
        return ok, msg
    if not is_io_code(code):
        return ok, msg
    a_ok, a_msg = activate_spawned_io(code)
    if a_ok:
        return True, f"{msg}; {a_msg}"
    return True, f"{msg}; activate skipped: {a_msg}"

