"""Dev smoke probes — secret Ctrl+Alt+Shift+F9 support panel.

Small pass/fail checks for common “why isn’t X working?” cases. Results go to the
EXE panel and unrealsdk.log as ``[Squ1ggs's Boosting Tools | DevSmoke]``.

Rows may set ``kind``:
- ``check`` (default): counts toward pass/fail
- ``info``: status only (never fails the suite)
"""

from __future__ import annotations

from typing import Any, Callable

from unrealsdk import logging

_PREFIX = "[Squ1ggs's Boosting Tools | DevSmoke]"


def _log(msg: str) -> None:
    logging.info(f"{_PREFIX} {msg}")


def _row(name: str, ok: bool, detail: str, *, kind: str = "check") -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "detail": str(detail or "")[:420],
        "kind": "info" if kind == "info" else "check",
    }


def _find_live(class_name: str) -> list[Any]:
    import unrealsdk

    try:
        objs = list(unrealsdk.find_all(class_name, False) or [])
    except TypeError:
        try:
            objs = list(unrealsdk.find_all(class_name) or [])
        except Exception:
            return []
    except Exception:
        return []
    out: list[Any] = []
    for obj in objs:
        name = str(getattr(obj, "Name", "") or "")
        if not name or name.startswith("Default__"):
            continue
        out.append(obj)
    return out


def _fgbx_ok() -> tuple[bool, str]:
    try:
        from .currency_give import fgbx_def_ptr_api_ok

        if fgbx_def_ptr_api_ok():
            return True, "FGbxDefPtr API present"
        return (
            False,
            "FGbxDefPtr missing — Oak2 SDK 0.3+ required "
            "(EXE Setup → Update base SDK → fully restart BL4)",
        )
    except Exception as exc:
        return False, f"fgbx check failed: {exc}"


def _host_ok() -> tuple[bool, str]:
    try:
        from . import world_spawn

        host = bool(world_spawn.is_host())
        return host, "listen/host session" if host else "joined client — many RPCs need host"
    except Exception as exc:
        return False, f"host check failed: {exc}"


def _pc_ok() -> tuple[bool, str]:
    try:
        from mods_base import get_pc

        pc = get_pc()
        if pc is None:
            return False, "no local PC — load a character in-world"
        name = str(getattr(pc, "Name", "") or pc)[:80]
        return True, f"PC={name}"
    except Exception as exc:
        return False, str(exc)


def _local_pawn() -> Any | None:
    try:
        from mods_base import get_pc

        pc = get_pc()
        if pc is None:
            return None
        for attr in ("Pawn", "AcknowledgedPawn", "ControlledPawn"):
            pawn = getattr(pc, attr, None)
            if pawn is not None:
                return pawn
        return None
    except Exception:
        return None


def smoke_sdk() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ok, detail = _fgbx_ok()
    rows.append(_row("FGbxDefPtr", ok, detail))
    try:
        from unrealsdk.unreal import FGameDataHandle

        h = FGameDataHandle(16430, "Challenge_Misc_World_CompleteSideMissions")
        rows.append(_row("FGameDataHandle ctor", True, str(h)[:120]))
    except Exception as exc:
        rows.append(_row("FGameDataHandle ctor", False, str(exc)))
    try:
        from unrealsdk.unreal import WrappedStruct

        rows.append(_row("WrappedStruct import", True, str(WrappedStruct)))
    except Exception as exc:
        rows.append(_row("WrappedStruct import", False, str(exc)))
    try:
        import unrealsdk

        ver = getattr(unrealsdk, "__version__", None) or getattr(unrealsdk, "VERSION", None)
        rows.append(_row("unrealsdk", True, f"version={ver!r}"))
    except Exception as exc:
        rows.append(_row("unrealsdk", False, str(exc)))
    return rows


def smoke_host() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ok, detail = _pc_ok()
    rows.append(_row("Local player", ok, detail))
    ok, detail = _host_ok()
    rows.append(_row("Session authority", ok, detail))
    try:
        pawn = _local_pawn()
        rows.append(
            _row(
                "Pawn",
                pawn is not None,
                str(getattr(pawn, "Name", "") or pawn or "missing — main menu / loading?"),
            )
        )
    except Exception as exc:
        rows.append(_row("Pawn", False, str(exc)))
    return rows


def smoke_bridge() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .external_bridge import bridge_started, bridge_status_line

        started = bool(bridge_started())
        rows.append(_row("HTTP bridge", started, bridge_status_line()))
    except Exception as exc:
        rows.append(_row("HTTP bridge", False, str(exc)))
    try:
        from ._mod_version import __version__

        rows.append(_row("Mod version", True, __version__))
    except Exception as exc:
        rows.append(_row("Mod version", False, str(exc)))
    try:
        from . import runtime_log

        blob = runtime_log.status_blob()
        rows.append(
            _row(
                "Runtime log",
                True,
                f"{blob.get('path')} ring={blob.get('ring_lines')} file={blob.get('file_bytes')}B",
                kind="info",
            )
        )
    except Exception as exc:
        rows.append(_row("Runtime log", False, str(exc)))
    return rows


def smoke_catalog() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from . import shinies

        helpers = []
        for name in ("drop_all_shinies", "grant_all_shiny_serials", "load_shiny_serials"):
            if callable(getattr(shinies, name, None)):
                helpers.append(name)
        rows.append(
            _row(
                "Shinies world/mail APIs",
                "drop_all_shinies" in helpers and "grant_all_shiny_serials" in helpers,
                f"found={','.join(helpers) or 'none'}",
            )
        )
    except Exception as exc:
        rows.append(_row("Shinies world/mail APIs", False, str(exc)))
    try:
        from .item_pool_spawning import load_item_pools

        pools = load_item_pools()
        n = len(pools)
        rows.append(_row("Loot pool catalog", n >= 50, f"{n} item_pools.json row(s)"))
    except Exception as exc:
        rows.append(_row("Loot pool catalog", False, str(exc)))
    try:
        from .challenge_bulk_runtime import catalog_rows

        sample = catalog_rows("", "All non-UVHM", limit=200)
        n = len(sample)
        rows.append(_row("Challenge catalog", n > 0, f"{n} challenge row(s) in sample (limit=200)"))
    except Exception as exc:
        rows.append(_row("Challenge catalog", False, str(exc)))
    return rows


def smoke_vault() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    vaults = _find_live("OakProfileProgressVault") or _find_live("OakProfileVault")
    if not vaults:
        rows.append(_row("Progress vault", False, "no live OakProfileProgressVault"))
        return rows
    vault = vaults[0]
    vault_name = str(getattr(vault, "Name", "") or vault)
    rows.append(_row("Progress vault", True, vault_name[:80]))
    role_classes = (
        "MissionProgressRole",
        "MissionSourceStateRole",
        "MissionTaskStateRole",
        "OakChallengeProgressRoleCharacter",
        "UnlockablesProgressRolePerCharacter",
    )
    challenge_aliases = (
        "OakChallengeProgressRoleCharacter",
        "OakChallengeProgressRole",
        "OakChallengeProgressRoleBase",
    )
    for role in role_classes:
        present = False
        detail = "missing — open in-game Challenges once"
        try:
            val = getattr(vault, role, None)
            if val is not None:
                present = True
                detail = f"attr on vault ({getattr(val, 'Name', type(val).__name__)})"
        except Exception:
            pass
        search_names = challenge_aliases if "Challenge" in role else (role,)
        if not present:
            for hint in search_names:
                live_roles = _find_live(hint)
                for obj in live_roles:
                    try:
                        outer = getattr(obj, "Outer", None)
                        oname = str(getattr(outer, "Name", "") or "")
                        if outer is vault or oname == vault_name or "OakProfileProgressVault" in oname:
                            present = True
                            detail = f"live {getattr(obj, 'Name', hint)} (Outer={oname or 'vault'})"
                            break
                    except Exception:
                        continue
                if present:
                    break
                if live_roles:
                    present = True
                    detail = f"live={len(live_roles)} ({hint})"
                    break
        if not present and "Challenge" in role:
            mgrs = _find_live("OakChallengeManager")
            if mgrs:
                present = True
                detail = "manager live — open Challenges once if challenge unlocks look stale"
        rows.append(_row(f"Vault.{role}", present, detail))
    return rows


def smoke_currency() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ok, detail = _fgbx_ok()
    rows.append(_row("FGbxDefPtr (currency)", ok, detail))
    try:
        from mods_base import get_pc

        pc = get_pc()
        if pc is None:
            rows.append(_row("GiveCurrency surface", False, "no PC"))
        else:
            hit = None
            for name in (
                "GiveCurrency",
                "ServerGiveCurrency",
                "ClientGiveCurrency",
                "GiveCurrencyAmount",
            ):
                fn = getattr(pc, name, None)
                if callable(fn):
                    hit = name
                    break
            if hit:
                rows.append(_row("GiveCurrency surface", True, f"PC.{hit}"))
            else:
                lib_ok = False
                try:
                    import unrealsdk

                    for path_name in (
                        "/Script/GbxGame.GbxCurrencyFunctionLibrary",
                        "GbxCurrencyFunctionLibrary",
                    ):
                        try:
                            cls = unrealsdk.find_class(path_name)
                            cdo = getattr(cls, "ClassDefaultObject", None) if cls else None
                            if cdo is not None and callable(getattr(cdo, "GiveCurrency", None)):
                                lib_ok = True
                                rows.append(_row("GiveCurrency surface", True, f"library {path_name}"))
                                break
                        except Exception:
                            continue
                except Exception:
                    pass
                if not lib_ok:
                    rows.append(
                        _row(
                            "GiveCurrency surface",
                            False,
                            "missing on PC/library — often clears after Oak2 0.3+ SDK update",
                        )
                    )
    except Exception as exc:
        rows.append(_row("GiveCurrency surface", False, str(exc)))
    return rows


def smoke_challenges() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .challenge_increment import _challenge_library

        lib = _challenge_library()
        rows.append(
            _row(
                "Challenge library",
                lib is not None,
                str(getattr(lib, "Name", "") or lib or "missing OakChallengeBlueprintLibrary"),
            )
        )
    except Exception as exc:
        rows.append(_row("Challenge library", False, str(exc)))
    mgrs = _find_live("OakChallengeManager")
    rows.append(
        _row(
            "OakChallengeManager",
            bool(mgrs),
            f"live={len(mgrs)}" if mgrs else "none — open Challenges menu",
        )
    )
    return rows


def smoke_world() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from mods_base import ENGINE

        viewport = getattr(ENGINE, "GameViewport", None) if ENGINE is not None else None
        world = getattr(viewport, "World", None) if viewport is not None else None
        rows.append(_row("World", world is not None, str(getattr(world, "Name", "") or world or "no world")))
    except Exception as exc:
        rows.append(_row("World", False, str(exc)))
    ws = _find_live("OakWorldSettings") or _find_live("WorldSettings")
    rows.append(
        _row(
            "WorldSettings",
            bool(ws),
            f"live={len(ws)}" if ws else "No live worldsettings — load into a map",
        )
    )
    ncs = _find_live("NexusConfigStoreMissions")
    rows.append(_row("NCS Missions", bool(ncs), f"live={len(ncs)}" if ncs else "none"))
    return rows


def smoke_deferred() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from bl4_world_tools import deferred, hooks

        rows.append(_row("bl4_world_tools.deferred", True, f"pending={deferred.has_pending()}"))
        # Probe only — do not call hooks.register() (side effect / re-hook risk).
        has_reg = callable(getattr(hooks, "register", None))
        already = bool(getattr(hooks, "_registered", False) or getattr(hooks, "is_registered", False))
        if callable(getattr(hooks, "is_registered", None)):
            try:
                already = bool(hooks.is_registered())
            except Exception:
                pass
        rows.append(
            _row(
                "bl4_world_tools tick hook",
                has_reg,
                "already registered" if already else ("register() available" if has_reg else "no tick hook API"),
            )
        )
    except Exception as exc:
        rows.append(_row("bl4_world_tools", False, f"not importable: {exc}"))
    try:
        import blimgui as bg

        has = hasattr(bg, "register_post_frame")
        rows.append(_row("blimgui post-frame", has, "register_post_frame present" if has else "missing"))
    except Exception as exc:
        rows.append(_row("blimgui", False, str(exc)))
    return rows


def smoke_travel() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from . import travel

        n = 0
        for attr in dir(travel):
            if "preset" not in attr.lower():
                continue
            val = getattr(travel, attr, None)
            if isinstance(val, dict):
                n = max(n, len(val))
            elif isinstance(val, (list, tuple)):
                n = max(n, len(val))
        fn_ok = callable(getattr(travel, "travel_to_preset", None))
        rows.append(
            _row(
                "Travel module",
                fn_ok and n > 0,
                f"travel_to_preset={'yes' if fn_ok else 'no'} presets≈{n}",
            )
        )
    except Exception as exc:
        rows.append(_row("Travel module", False, str(exc)))
    return rows


def smoke_rewards() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mgrs = _find_live("GbxRewardsManager")
    rows.append(_row("GbxRewardsManager", bool(mgrs), f"live={len(mgrs)}" if mgrs else "none"))
    return rows


def smoke_peers() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from mods_base.mod_list import get_ordered_mod_list
        from .peer_session import _BUNDLED_STANDALONES, _mod_folder_name

        watch = set(_BUNDLED_STANDALONES) | {"bl4_item_spawner"}
        enabled: list[str] = []
        for mod in list(get_ordered_mod_list() or []):
            try:
                if not getattr(mod, "is_enabled", False):
                    continue
            except Exception:
                continue
            folder = _mod_folder_name(mod)
            key = folder.lower()
            if key == "squ1ggsboostingtools":
                continue
            if key in watch:
                enabled.append(folder)
        if enabled:
            rows.append(
                _row(
                    "Overlapping spawn mods",
                    False,
                    ", ".join(enabled) + " still enabled — disable in Mods if spawn fights SQBT",
                )
            )
        else:
            rows.append(_row("Overlapping spawn mods", True, "no enabled conflicting peers"))
    except Exception as exc:
        rows.append(_row("Overlapping spawn mods", False, str(exc)))
    return rows


def smoke_zoom_flag() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from . import character_flags as flags

        for key, label in (
            ("zoom_injured", "Zoom while downed"),
            ("zoom_sprint", "Zoom while sprinting"),
            ("shoot_sprint", "Shoot while sprinting"),
        ):
            on = bool(flags.is_on(key, 0))
            rows.append(_row(label, True, f"currently={'on' if on else 'off'}", kind="info"))
    except Exception as exc:
        rows.append(_row("Character flags", False, str(exc)))
    return rows


def smoke_mobility() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from . import mobility_runtime as mob

        has_fly = callable(getattr(mob, "set_force_fly_for_index", None))
        has_stamp = callable(getattr(mob, "_stamp_force_fly_speed", None))
        has_wish = callable(getattr(mob, "_force_fly_wish_dir", None))
        active = len(getattr(mob, "force_fly_targets", {}) or {})
        rows.append(
            _row(
                "Force fly APIs",
                has_fly and has_stamp and has_wish,
                f"set/stamp/wish={'y' if has_fly else 'n'}/{'y' if has_stamp else 'n'}/{'y' if has_wish else 'n'} "
                f"active_targets={active}",
            )
        )
        rows.append(
            _row(
                "Force fly active",
                True,
                f"{active} target(s)" if active else "off",
                kind="info",
            )
        )
    except Exception as exc:
        rows.append(_row("Force fly APIs", False, str(exc)))
    return rows


_SUITES: dict[str, Callable[[], list[dict[str, Any]]]] = {
    "sdk": smoke_sdk,
    "host": smoke_host,
    "bridge": smoke_bridge,
    "catalog": smoke_catalog,
    "vault": smoke_vault,
    "currency": smoke_currency,
    "challenges": smoke_challenges,
    "world": smoke_world,
    "deferred": smoke_deferred,
    "travel": smoke_travel,
    "rewards": smoke_rewards,
    "peers": smoke_peers,
    "zoom": smoke_zoom_flag,
    "mobility": smoke_mobility,
}

_ALL_ORDER = (
    "bridge",
    "sdk",
    "host",
    "world",
    "vault",
    "catalog",
    "currency",
    "challenges",
    "rewards",
    "deferred",
    "travel",
    "peers",
    "mobility",
    "zoom",
)

_SUITE_HELP = (
    "all, sdk, host, bridge, catalog, vault, currency, "
    "challenges, world, deferred, travel, rewards, peers, mobility, zoom"
)


def run_suite(suite: str = "all", *, token: str = "") -> dict[str, Any]:
    name = str(suite or "all").strip().lower() or "all"
    del token  # reserved for future suite filters
    rows: list[dict[str, Any]] = []
    if name == "all":
        for key in _ALL_ORDER:
            rows.extend(_SUITES[key]())
    elif name in _SUITES:
        rows = _SUITES[name]()
    else:
        return {
            "ok": False,
            "message": f"Unknown suite {name!r}. Use: {_SUITE_HELP}",
            "results": [],
        }

    checks = [r for r in rows if r.get("kind") != "info"]
    infos = [r for r in rows if r.get("kind") == "info"]
    passed = sum(1 for r in checks if r.get("ok"))
    failed = sum(1 for r in checks if not r.get("ok"))
    lines = [
        f"{'INFO' if r.get('kind') == 'info' else ('PASS' if r['ok'] else 'FAIL')}  {r['name']}: {r['detail']}"
        for r in rows
    ]
    summary = (
        f"Dev smoke [{name}]: {passed} pass, {failed} fail"
        + (f", {len(infos)} info" if infos else "")
    )
    tips: list[str] = []
    if any(r["name"].startswith("FGbxDefPtr") and not r["ok"] for r in checks):
        tips.append(
            "TIP: FGbxDefPtr fail → EXE Setup → Update base SDK → fully quit BL4 → relaunch. "
            "Currency / many grants need Oak2 0.3+."
        )
    if any(r["name"] == "Session authority" and not r["ok"] for r in checks):
        tips.append("TIP: Host or listen-server for many authority RPCs.")
    if any("Challenge" in r["name"] and not r["ok"] for r in checks):
        tips.append("TIP: Open in-game Challenges once so vault challenge roles load.")
    if any(r["name"] == "Shinies world/mail APIs" and not r["ok"] for r in checks):
        tips.append("TIP: Shinies helpers missing — reinstall Squ1ggs mod folder from the EXE.")
    if any(r["name"] == "Loot pool catalog" and not r["ok"] for r in checks):
        tips.append("TIP: item_pools.json missing/corrupt — reinstall Squ1ggs mod folder.")
    _log(summary)
    for line in lines:
        _log(line)
    for tip in tips:
        _log(tip)
    try:
        from . import runtime_log

        runtime_log.note(f"dev_smoke [{name}] {summary}")
        runtime_log.flush(force=True)
    except Exception:
        pass
    message = summary + "\n" + "\n".join(lines)
    if tips:
        message += "\n\n" + "\n".join(tips)
    return {
        "ok": failed == 0,
        "message": message,
        "results": rows,
        "passed": passed,
        "failed": failed,
        "info": len(infos),
        "suite": name,
        "tips": tips,
    }
