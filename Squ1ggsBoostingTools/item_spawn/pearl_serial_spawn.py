"""@U serial world/backpack delivery for pearlescent (comp_06_pearl_*) items."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import unrealsdk
from unrealsdk import logging

from .mod_data import read_mod_json

MOD_DIR = Path(__file__).resolve().parent
SERIALS_PATH = MOD_DIR / "data" / "reference" / "pearl_spawn_serials.json"

_SERIAL_BY_CATALOG: dict[str, str] = {}
_SERIALS_BY_CATALOG: dict[str, list[str]] = {}
_NATIVE_POOL_BY_CATALOG: dict[str, str] = {}
_TITLE_BY_CATALOG: dict[str, str] = {}
_CATALOG_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "tor_ps_comp_06_pearl_herald": ("herald",),
    "jak_sg_comp_06_pearl_constable": ("constable", "loomingconstable"),
    "mal_sm_comp_06_pearl_juliet": ("julietssparkle", "juliet", "julietssparkle"),
    "dad_sm_comp_06_pearl_screwed": ("screwstonian", "screwed"),
    "vla_sm_comp_06_pearl_locust": ("parasite", "locust"),
    "ted_sg_comp_06_pearl_sharkbait": ("sharkbait",),
    "bor_sm_comp_05_legendary_jailbroken": ("jailbroken", "jailbrokengatling"),
    "dad_sm_comp_05_legendary_raiden": ("raiden",),
    "bor_sr_comp_05_legendary_abyss": ("abyss", "abyssripper"),
    "jak_ar_comp_05_legendary_gomie": ("gomie",),
    "ord_sr_comp_05_legendary_temper": ("temper", "solartemper"),
    "jak_sr_comp_05_legendary_burrow": ("burrow", "prism", "prisms"),
    "vla_hw_comp_05_legendary_splatoon": ("splatoon", "flakcannon", "flak", "inkling"),
    "vla_hw_comp_05_legendary_flak": ("flakcannon", "flak"),
    "vla_hw_comp_05_legendary_atlinggun": ("atlinggun", "atling"),
    "mal_hw_comp_05_legendary_barrel": ("barrel",),
    "mal_hw_comp_05_legendary_bottledlightning": ("bottledlightning",),
    "mal_hw_comp_05_legendary_gammavoid": ("gammavoid",),
    "mal_hw_comp_05_legendary_ichor": ("ichor",),
    "tor_hw_comp_05_legendary_ravenfire": ("ravenfire",),
    "tor_hw_comp_05_legendary_sidewinder": ("sidewinder",),
    "tor_hw_comp_05_legendary_dahlfather": ("dahlfather", "heimdahl"),
    "tor_hw_comp_05_legendary_javelin": ("javelin", "sprezzatura"),
    "bor_hw_comp_05_legendary_draupner": ("draupner",),
    "bor_hw_comp_05_legendary_jetset": ("jetset", "jetsetter"),
    "bor_hw_comp_05_legendary_discjockey": ("discjockey", "disc jockey"),
    "dad_ar_comp_05_legendary_firstimpression": ("firstimpression",),
    "dad_ar_comp_05_legendary_lumberjack": ("lumberjack", "bloodylumberjack"),
    "jak_ar_comp_05_legendary_bonnieclyde": ("bonnieclyde", "bonnieandclyde"),
    "dad_ar_comp_05_legendary_harddark": ("harddark", "darkhard"),
    "dad_sm_comp_05_legendary_loarmaster": ("loarmaster",),
    "jak_ar_comp_05_legendary_screenwriter": ("screenwriter",),
    "mal_sm_comp_05_legendary_firework": ("firework", "matadorsmatch", "matadormatch"),
    "tor_ar_comp_05_legendary_lockjaw": ("lockjaw",),
    "tor_sg_comp_05_legendary_unstable_kor": ("unstablekor", "unstable_kor"),
    "ord_shield_comp_05_legendary_collector": ("collector",),
    "tor_grenade_gadget_comp_05_legendary_slippy": ("slippy", "fishgrenade"),
    "bor_sg_comp_05_legendary_crazedearl": ("crazedearl",),
    "dad_ps_comp_05_legendary_soulsurvivor": ("soulsurvivor",),
    "mal_sr_comp_05_legendary_conflux": ("conflux",),
    "ord_ar_comp_05_legendary_crowsourced": ("crowsourced", "crow sourced"),
    "ted_sg_comp_05_legendary_eigenburst": ("eigenburst",),
    "tor_ps_comp_05_legendary_handcannon": ("handcannon",),
}
_LOADED = False


def _norm_match_name(text: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _append_catalog_serial(catalog_key: str, serial: str) -> None:
    key = str(catalog_key or "").strip().lower()
    serial = str(serial or "").strip()
    if not key or not serial.startswith("@U"):
        return
    bucket = _SERIALS_BY_CATALOG.setdefault(key, [])
    if serial not in bucket:
        bucket.append(serial)
    if key not in _SERIAL_BY_CATALOG:
        _SERIAL_BY_CATALOG[key] = serial


def _catalog_match_tokens(catalog_key: str, title: str = "") -> set[str]:
    key = catalog_key.strip().lower()
    tokens: set[str] = set()
    for piece in (title, *_CATALOG_NAME_ALIASES.get(key, ())):
        norm = _norm_match_name(piece)
        if norm:
            tokens.add(norm)
    if "_comp_06_pearl_" in key:
        tokens.add(_norm_match_name(key.split("_comp_06_pearl_", 1)[-1]))
    if "_comp_05_legendary_" in key:
        tokens.add(_norm_match_name(key.split("_comp_05_legendary_", 1)[-1]))
    return tokens


def _merge_extra_serial_sources() -> None:
    lootlemon = MOD_DIR.parent / "squ1ggs_lootlemon_codes.json"
    ncs_shiny = MOD_DIR / "data" / "reference" / "ncs_shiny_serials.json"
    # Include alias-only catalogs (First Impression, etc.) even before pearl_spawn_serials.json has them.
    catalog_keys = set(_SERIALS_BY_CATALOG) | set(_CATALOG_NAME_ALIASES)
    catalog_tokens = {
        key: _catalog_match_tokens(key, _TITLE_BY_CATALOG.get(key, ""))
        for key in catalog_keys
    }

    def ingest_row(name: str, serial: str, row_id: str = "") -> None:
        serial = str(serial or "").strip()
        if not serial.startswith("@U"):
            return
        row_tokens = {_norm_match_name(name), _norm_match_name(row_id)}
        row_tokens.discard("")
        for catalog_key, tokens in catalog_tokens.items():
            if tokens & row_tokens:
                _append_catalog_serial(catalog_key, serial)

    doc = read_mod_json(lootlemon)
    for row in doc.get("entries", []) if isinstance(doc, dict) else []:
        if isinstance(row, dict):
            ingest_row(str(row.get("name", "")), str(row.get("serial", "")), str(row.get("id", "")))

    doc = read_mod_json(ncs_shiny)
    rows = doc if isinstance(doc, list) else []
    for row in rows:
        if isinstance(row, dict):
            ingest_row(
                str(row.get("display_name") or row.get("name") or ""),
                str(row.get("serial", "")),
                str(row.get("id", "")),
            )


def _load() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    doc = read_mod_json(SERIALS_PATH)
    if not isinstance(doc, dict):
        logging.warning(
            f"[Squ1ggs Boosting Tools] Missing {SERIALS_PATH.name} — pearl serial spawn disabled."
        )
        return
    by_cat = doc.get("by_catalog_key")
    if isinstance(by_cat, dict):
        for catalog_key, row in by_cat.items():
            if not isinstance(row, dict):
                continue
            title = str(row.get("title", "")).strip()
            key = str(catalog_key).strip().lower()
            if title:
                _TITLE_BY_CATALOG[key] = title
            primary = str(row.get("serial", "")).strip()
            extras = row.get("serials")
            if primary.startswith("@U"):
                _append_catalog_serial(key, primary)
            if isinstance(extras, list):
                for item in extras:
                    if isinstance(item, str):
                        _append_catalog_serial(key, item)
                    elif isinstance(item, dict):
                        _append_catalog_serial(key, str(item.get("serial", "")))
    _merge_extra_serial_sources()
    aliases = doc.get("native_pool_aliases")
    if isinstance(aliases, dict):
        for catalog_key, pool in aliases.items():
            pool_name = str(pool).strip()
            if pool_name:
                _NATIVE_POOL_BY_CATALOG[str(catalog_key).strip().lower()] = pool_name


def new_item_catalog_keys() -> frozenset[str]:
    _load()
    return frozenset(_SERIAL_BY_CATALOG.keys())


def display_title_for_catalog(catalog_key: str) -> str | None:
    _load()
    return _TITLE_BY_CATALOG.get(catalog_key.strip().lower())


def catalog_has_serial_path(catalog_key: str) -> bool:
    _load()
    key = catalog_key.strip().lower()
    return bool(serials_for_catalog(key)) or key in _NATIVE_POOL_BY_CATALOG


def serials_for_catalog(catalog_key: str) -> list[str]:
    _load()
    return list(_SERIALS_BY_CATALOG.get(catalog_key.strip().lower(), []))


def serial_for_catalog(catalog_key: str) -> str | None:
    _load()
    serials = serials_for_catalog(catalog_key)
    return serials[0] if serials else None


def native_pool_for_catalog(catalog_key: str) -> str | None:
    _load()
    return _NATIVE_POOL_BY_CATALOG.get(catalog_key.strip().lower())


def _iter_pcs() -> list[Any]:
    out: list[Any] = []
    for class_name in ("OakPlayerController", "Oak2PlayerController", "PlayerController"):
        try:
            out.extend(list(unrealsdk.find_all(class_name, exact=False)))
        except Exception:
            continue
    seen: set[int] = set()
    uniq: list[Any] = []
    for pc in out:
        addr = id(pc)
        try:
            addr = int(getattr(pc, "_get_address", lambda: 0)() or 0)
        except Exception:
            pass
        if addr in seen:
            continue
        seen.add(addr)
        name = str(getattr(pc, "Name", "") or "")
        if "Default__" in name:
            continue
        uniq.append(pc)
    return uniq


def _get_pc() -> Any | None:
    try:
        from .spawn_pc import resolve_spawn_pc

        pc = resolve_spawn_pc()
        if pc is not None:
            return pc
    except Exception:
        pass
    pcs = _iter_pcs()
    with_pawn = [p for p in pcs if getattr(p, "Pawn", None) is not None]
    return (with_pawn or pcs)[0] if (with_pawn or pcs) else None


def _invoke_serial_method(target: Any, method: str, serial: str, count: int) -> bool:
    fn = getattr(target, method, None)
    if not callable(fn):
        return False
    attempts: list[tuple[tuple[Any, ...], dict[str, Any]]] = [
        ((serial,), {}),
        ((serial, count), {}),
        ((), {"Serial": serial}),
        ((), {"serial": serial}),
        ((), {"ItemSerial": serial}),
        ((), {"ItemSerialString": serial}),
        ((serial, count), {"Count": count}),
    ]
    for args, kwargs in attempts:
        try:
            fn(*args, **kwargs)
            return True
        except TypeError:
            continue
        except Exception:
            continue
    return False


_GROUND_SERIAL_METHODS: tuple[str, ...] = (
    "ServerSpawnItemFromSerial",
    "Server_SpawnItemFromSerial",
    "ServerGiveItemFromSerial",
    "Server_GiveItemFromSerial",
    "SpawnItemFromSerial",
    "SpawnInventoryItemFromSerial",
    "K2_SpawnItemFromSerial",
    "NetSpawnItemFromSerial",
    "Multicast_SpawnItemFromSerial",
    "ServerAddWeaponFromSerial",
    "Server_AddWeaponFromSerial",
)

_BACKPACK_SERIAL_METHODS: tuple[str, ...] = (
    "ServerAddItemFromSerial",
    "Server_AddItemFromSerial",
    "ServerCreateItemFromSerial",
    "Server_CreateItemFromSerial",
    "AddItemFromSerial",
    "AddInventoryItemFromSerial",
    "TryAddItemFromItemSerialString",
    "Server_AddItemToBackpackFromSerial",
    "AddItemToBackpackFromSerial",
    "K2_AddItemFromSerial",
)


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


_SERIAL_INVENTORY_ATTRS: tuple[str, ...] = (
    "InventoryComponent",
    "InventoryManager",
    "OakInventoryComponent",
    "OakInventoryManager",
    "PlayerInventory",
    "BackpackInventory",
    "ItemInventory",
    "WeaponInventory",
    "GbxInventoryComponent",
)


def _iter_serial_targets() -> list[tuple[str, Any]]:
    """PC, pawn, inventory, and backpack objects that may accept @U serial RPCs."""
    targets: list[tuple[str, Any]] = []
    seen: set[int] = set()

    def add(label: str, obj: Any) -> None:
        if obj is None:
            return
        addr = id(obj)
        try:
            addr = int(getattr(obj, "_get_address", lambda: 0)() or 0) or addr
        except Exception:
            pass
        if addr in seen:
            return
        seen.add(addr)
        targets.append((label, obj))

    pc = _get_pc()
    add("pc", pc)
    if pc is None:
        return targets

    pawn = _safe_getattr(pc, "Pawn")
    add("pawn", pawn)
    for attr in _SERIAL_INVENTORY_ATTRS:
        add(f"pc.{attr}", _safe_getattr(pc, attr))
        if pawn is not None:
            add(f"pawn.{attr}", _safe_getattr(pawn, attr))

    ps = _safe_getattr(pc, "PlayerState")
    add("playerstate", ps)
    if ps is not None:
        for bag in ("BackpackContainer", "BankContainer", "LostLootManager"):
            add(bag.lower(), _safe_getattr(ps, bag))
        for attr in _SERIAL_INVENTORY_ATTRS:
            add(f"playerstate.{attr}", _safe_getattr(ps, attr))

    return targets


def _discover_serial_methods(obj: Any) -> list[str]:
    out: list[str] = []
    try:
        names = dir(obj)
    except Exception:
        return out
    for name in names:
        low = str(name).lower()
        if "serial" not in low:
            continue
        if not any(token in low for token in ("from", "spawn", "add", "create", "import")):
            continue
        fn = _safe_getattr(obj, name)
        if callable(fn):
            out.append(str(name))
    return out


def _kismet_execute_console(line: str, pc: Any | None) -> tuple[bool, str]:
    s = str(line or "").strip()
    if not s:
        return False, "empty command"
    try:
        ksl = unrealsdk.find_class("KismetSystemLibrary")
    except Exception:
        return False, "KismetSystemLibrary missing"
    if ksl is None:
        return False, "KismetSystemLibrary missing"
    kfn = getattr(ksl, "ExecuteConsoleCommand", None)
    if not callable(kfn):
        cdo = getattr(ksl, "ClassDefaultObject", None)
        kfn = getattr(cdo, "ExecuteConsoleCommand", None) if cdo is not None else None
    if not callable(kfn):
        return False, "ExecuteConsoleCommand missing"
    contexts: list[Any] = []
    seen: set[int] = set()

    def add(obj: Any) -> None:
        if obj is None:
            return
        try:
            key = int(getattr(obj, "_get_address", lambda: 0)() or 0) or id(obj)
        except Exception:
            key = id(obj)
        if key in seen:
            return
        seen.add(key)
        contexts.append(obj)

    add(pc)
    if pc is not None:
        add(getattr(pc, "Pawn", None))
        try:
            add(getattr(pc, "World", None))
        except Exception:
            pass
    try:
        eng = getattr(unrealsdk, "ENGINE", None)
        gv = getattr(eng, "GameViewport", None) if eng is not None else None
        add(getattr(gv, "World", None) if gv is not None else None)
    except Exception:
        pass
    last = ""
    for ctx in contexts:
        for pack in ((ctx, s, pc), (ctx, s), (s,)):
            if pack[0] is None and len(pack) == 2:
                continue
            try:
                kfn(*pack)
                return True, "Kismet.ExecuteConsoleCommand"
            except TypeError:
                continue
            except Exception as exc:  # noqa: BLE001
                last = str(exc)
    return False, last or "Kismet console failed"


def _viewport_console(line: str) -> tuple[bool, str]:
    s = str(line or "").strip()
    if not s:
        return False, "empty command"
    try:
        eng = getattr(unrealsdk, "ENGINE", None)
        gv = getattr(eng, "GameViewport", None) if eng is not None else None
        con = getattr(gv, "ViewportConsole", None) if gv is not None else None
    except Exception:
        return False, "ViewportConsole missing"
    if con is None:
        return False, "ViewportConsole missing"
    last = ""
    for meth in ("ConsoleCommand", "SendTextToConsole", "OutputText"):
        fn = getattr(con, meth, None)
        if not callable(fn):
            continue
        for pack in ((s,), (s, False), (s, True)):
            try:
                fn(*pack)
                return True, f"ViewportConsole.{meth}"
            except Exception as exc:  # noqa: BLE001
                last = str(exc)
    return False, last or "ViewportConsole failed"


def _invoke_pc_console(pc: Any | None, command: str) -> tuple[bool, str]:
    if pc is None:
        return False, "no pc"
    for meth in ("ConsoleCommand", "ClientConsoleCommand"):
        fn = getattr(pc, meth, None)
        if not callable(fn):
            continue
        try:
            fn(command)
            return True, meth
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
    return False, "PC console unavailable"


def _deliver_serial_via_console_commands(serial: str, pc: Any | None) -> tuple[bool, str]:
    # ExecuteConsoleCommand returns normally even when the command name is not
    # registered.  Treating that as success produced the exact false positives
    # seen in spawn_test.jsonl: Kismet "accepted" SpawnFromSerial while no loot
    # actor or inventory item was created.  Only real *FromSerial bound methods
    # are allowed to report success; console probes remain diagnostic-only.
    return False, "unverified console serial commands disabled"


def _deliver_serial_via_methods(
    serial: str,
    count: int,
    *,
    methods: tuple[str, ...],
    console_cmds: tuple[str, ...],
) -> tuple[bool, str]:
    count = max(1, min(int(count), 32))
    for label, target in _iter_serial_targets():
        for _ in range(count):
            delivered = False
            for method in methods:
                if _invoke_serial_method(target, method, serial, 1):
                    delivered = True
                    return True, f"{label}.{method}"
            for method in _discover_serial_methods(target):
                if method in methods:
                    continue
                if _invoke_serial_method(target, method, serial, 1):
                    delivered = True
                    return True, f"{label}.{method}"
            if not delivered:
                pc_hint = target if label == "pc" else _get_pc()
                ok, via = _deliver_serial_via_console_commands(serial, pc_hint)
                if ok:
                    return True, via
                for console_cmd in console_cmds:
                    for meth in ("ConsoleCommand", "ClientConsoleCommand"):
                        fn = _safe_getattr(target, meth)
                        if not callable(fn):
                            continue
                        try:
                            fn(console_cmd)
                            return True, f"{label}.{meth}"
                        except Exception:
                            continue
                break
    return False, ""


def try_deliver_serial_comprehensive(
    serial: str,
    count: int = 1,
    *,
    prefer_ground: bool = True,
    ground_only: bool = False,
) -> tuple[bool, str]:
    """Try *FromSerial* RPCs. ``ground_only=True`` never uses backpack or mail."""
    serial = serial.strip()
    if not serial.startswith("@U"):
        return False, "invalid serial"
    ground_cmds = (
        f"spawnfromserial {serial}",
        f"SpawnFromSerial {serial}",
        f"SpawnItemFromSerial {serial}",
        f"spawnitemfromserial {serial}",
    )
    pack_cmds = (
        f"additemfromserial {serial}",
        f"AddItemFromSerial {serial}",
    )
    ok, via = _deliver_serial_via_methods(
        serial, count, methods=_GROUND_SERIAL_METHODS, console_cmds=ground_cmds
    )
    if ok:
        return True, via
    ok, via = _deliver_serial_via_console_commands(serial, _get_pc())
    if ok:
        return True, via
    if ground_only:
        return False, "ground FromSerial failed (no mail/backpack fallback)"
    if prefer_ground:
        ok, via = _deliver_serial_via_methods(
            serial, count, methods=_BACKPACK_SERIAL_METHODS, console_cmds=pack_cmds
        )
        if ok:
            return True, via
    else:
        ok, via = _deliver_serial_via_methods(
            serial, count, methods=_BACKPACK_SERIAL_METHODS, console_cmds=pack_cmds
        )
        if ok:
            return True, via
        ok, via = _deliver_serial_via_methods(
            serial, count, methods=_GROUND_SERIAL_METHODS, console_cmds=ground_cmds
        )
        if ok:
            return True, via
    return False, "no FromSerial RPC matched"


def try_deliver_serial_ground(serial: str, count: int = 1) -> bool:
    """Spawn item near the player via *Spawn*FromSerial RPCs (no mail)."""
    ok, _via = try_deliver_serial_comprehensive(serial, count, prefer_ground=True)
    return ok


def try_deliver_serial(serial: str, count: int = 1) -> bool:
    """Backpack delivery via *Add*FromSerial (explicit serial UI only)."""
    ok, _via = try_deliver_serial_comprehensive(serial, count, prefer_ground=False)
    return ok


def try_spawn_catalog_via_serial(catalog_key: str, count: int = 1) -> tuple[bool, str]:
    """World @U spawn only — tries each bundled serial at the player's feet (never mail/backpack)."""
    _load()
    key = catalog_key.strip().lower()
    serials = serials_for_catalog(key)
    if not serials:
        return False, "no_pearl_serial"
    errors: list[str] = []
    for index, serial in enumerate(serials):
        ok, via = try_deliver_serial_comprehensive(
            serial,
            count,
            prefer_ground=True,
            ground_only=True,
        )
        if ok:
            tag = "pearl_serial_ground" if index == 0 else f"pearl_serial_ground_alt{index + 1}"
            return True, f"{tag}:{via}"
        errors.append(f"#{index + 1}:{via or 'fail'}")
    logging.warning(
        f"[Squ1ggs Boosting Tools] Pearl @U ground failed for {key} "
        f"after {len(serials)} serial(s): {' | '.join(errors[:4])}"
    )
    return False, f"ground @U failed ({' | '.join(errors[:4])})"
