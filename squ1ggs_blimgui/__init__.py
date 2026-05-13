"""
Tuning GUI — ImGui panel for BL4 movement/damage tuning mods (player / vehicle / damage).

On disk this package is ``squ1ggs_blimgui`` (folder name unchanged for saves and imports).
Requires the separate **blimgui** mod. Each sub-panel appears only if the matching mod is
installed (``bl4_player_movement``, ``bl4_vehicle_movement``, ``bl4_damage_and_more``).
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import threading
from pathlib import Path
from typing import Any, Callable

from mods_base import CoopSupport, Game, build_mod, command, keybind
from unrealsdk import logging

__version__ = "1.1.0"
__author__ = "Squ1ggs"
MOD_NAME = "Tuning GUI"
LOG_PREFIX = "[TUNING-GUI]"
TAB_TITLE = "Tuning GUI"
_SETTINGS_DIR = Path(__file__).resolve().parent.parent / "settings"
_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_PATH = _SETTINGS_DIR / "squ1ggs_blimgui.json"
_LEGACY_SETTINGS_PATH = _SETTINGS_DIR / "squ1ggs_blimgui_tuning.json"

if not SETTINGS_PATH.exists() and _LEGACY_SETTINGS_PATH.exists():
    with contextlib.suppress(OSError):
        shutil.copy2(_LEGACY_SETTINGS_PATH, SETTINGS_PATH)

_blimgui_tab_registered = False
_blimgui_register_retry_token = 0


def _log(msg: str) -> None:
    logging.info(f"{LOG_PREFIX} {msg}")


def _begin_tab_item_draw(imgui: Any, label: str) -> bool:
    """Bindings differ: ``begin_tab_item`` may return ``bool`` or ``(opened, ...)``."""
    r = imgui.begin_tab_item(label)
    if isinstance(r, tuple) and len(r) >= 1:
        return bool(r[0])
    return bool(r)


def _try_import(name: str) -> Any | None:
    try:
        return __import__(name, fromlist=["__doc__"])
    except Exception:
        return None


def _imgui_mod():
    import blimgui  # noqa: F401 — initializes Oak2 imgui_bundle path for this process

    return blimgui


def _imgui_bundle():
    import blimgui as bg

    return bg.imgui


def _scope_combo(imgui: Any, mod: Any, *, apply_scope_attr: str) -> None:
    labels: tuple[str, ...] = getattr(mod, "_SCOPE_SPINNER_CHOICES", ("Local (you only)",))
    keys = ("local", "all", "others")
    cur = getattr(mod, apply_scope_attr, "local")
    try:
        idx = keys.index(str(cur).lower()) if str(cur).lower() in keys else 0
    except ValueError:
        idx = 0
    ch, ni = imgui.combo("Apply tuning to##sq_scope", idx, list(labels))
    if ch and 0 <= int(ni) < len(keys):
        setattr(mod, apply_scope_attr, keys[int(ni)])
        _log(f"scope → {keys[int(ni)]}")


def _draw_sliders_zip(
    imgui: Any,
    sliders: list[Any],
    specs: tuple[tuple[str, float, float, float, float, str], ...],
    *,
    apply_attr: Callable[[str, float], None],
) -> None:
    for opt, spec in zip(sliders, specs, strict=True):
        attr, lo, hi, _step, _def, title = spec[0], spec[1], spec[2], spec[3], spec[4], spec[5]
        try:
            cur = float(opt.value)
        except Exception:
            cur = float(_def)
        cid = f"{title}###sq_sl_{attr}"
        ch, nv = imgui.slider_float(cid, cur, float(lo), float(hi))
        if ch:
            try:
                opt.value = float(nv)
            except Exception:
                pass
            apply_attr(attr, float(nv))


def _draw_player(imgui: Any) -> None:
    m = _try_import("bl4_player_movement")
    if m is None:
        imgui.text_colored((1.0, 0.55, 0.45, 1.0), "bl4_player_movement is not installed or failed to import.")
        return
    imgui.text_wrapped("On-foot CharacterMovement. Load in-world on foot (not in a vehicle) for best results.")
    _scope_combo(imgui, m, apply_scope_attr="BPM_APPLY_SCOPE")
    if imgui.collapsing_header("Core (walk / jump / gravity / mass)", True):
        _draw_sliders_zip(imgui, m._slider_core, m._CORE_SPECS, apply_attr=m._apply_field)  # type: ignore[attr-defined]
    if imgui.collapsing_header("Advanced", True):
        _draw_sliders_zip(imgui, m._slider_extra, m._EXTRA_SPECS, apply_attr=m._apply_field)  # type: ignore[attr-defined]
    if imgui.collapsing_header("Vault power (driver pawn)", True):
        imgui.text_wrapped("Same OakCharacterMovement vault .Value paths as the Mods menu.")
        try:
            vs = m._vault_cost_slider  # type: ignore[attr-defined]
            cur = float(vs.value)
        except Exception:
            cur = 12.0
        ch, nv = imgui.slider_float("Uniform vault cost##sq_bpm_vault", cur, 0.0, 200.0)
        if ch:
            try:
                vs.value = float(nv)
            except Exception:
                pass
            try:
                m._on_vault_cost_slider(None, float(nv))  # type: ignore[attr-defined]
            except Exception:
                m._vault_set_uniform(float(nv), label="imgui")  # type: ignore[attr-defined]
        if imgui.button("Zero vault costs##sq_bpm_v0"):
            m._vault_zero()  # type: ignore[attr-defined]
        imgui.same_line()
        if imgui.button("Log vault + movement##sq_bpm_show"):
            m._vault_show()  # type: ignore[attr-defined]
            m._show_all()  # type: ignore[attr-defined]
    if imgui.collapsing_header("Presets", False):
        for btn in m._preset_buttons:  # type: ignore[attr-defined]
            label = str(getattr(btn, "display_name", "preset"))
            pid = getattr(btn, "identifier", label)
            if imgui.button(f"{label}###sq_{pid}"):
                try:
                    name = str(pid).replace("bpm_preset_btn_", "")
                    m._apply_preset(name)  # type: ignore[attr-defined]
                except Exception:
                    pass
    if imgui.button("Reset all floats##sq_bpm_rst"):
        m._reset_all()  # type: ignore[attr-defined]


def _draw_vehicle(imgui: Any) -> None:
    m = _try_import("bl4_vehicle_movement")
    if m is None:
        imgui.text_colored((1.0, 0.55, 0.45, 1.0), "bl4_vehicle_movement is not installed or failed to import.")
        return
    imgui.text_wrapped("Vehicle / Chaos movement. Enter a vehicle first, then tune.")
    _scope_combo(imgui, m, apply_scope_attr="BVM_APPLY_SCOPE")
    if imgui.collapsing_header("Core (speed / jump / gravity / mass)", True):
        _draw_sliders_zip(imgui, m._slider_core, m._CORE_SPECS, apply_attr=m._apply_field)  # type: ignore[attr-defined]
    if imgui.collapsing_header("Advanced", True):
        _draw_sliders_zip(imgui, m._slider_extra, m._EXTRA_SPECS, apply_attr=m._apply_field)  # type: ignore[attr-defined]
    if imgui.collapsing_header("Vault power (driver pawn)", True):
        try:
            vs = m._vault_cost_slider  # type: ignore[attr-defined]
            cur = float(vs.value)
        except Exception:
            cur = 12.0
        ch, nv = imgui.slider_float("Uniform vault cost##sq_bvm_vault", cur, 0.0, 200.0)
        if ch:
            try:
                vs.value = float(nv)
            except Exception:
                pass
            try:
                m._on_vault_cost_slider(None, float(nv))  # type: ignore[attr-defined]
            except Exception:
                m._vault_set_uniform(float(nv), label="imgui")  # type: ignore[attr-defined]
        if imgui.button("Zero vault costs##sq_bvm_v0"):
            m._vault_zero()  # type: ignore[attr-defined]
        imgui.same_line()
        if imgui.button("Log vault + movement##sq_bvm_show"):
            m._vault_show()  # type: ignore[attr-defined]
            m._show_all()  # type: ignore[attr-defined]
    if imgui.collapsing_header("Presets", False):
        for btn in m._preset_buttons:  # type: ignore[attr-defined]
            label = str(getattr(btn, "display_name", "preset"))
            pid = getattr(btn, "identifier", label)
            if imgui.button(f"{label}###sq_{pid}"):
                try:
                    name = str(pid).replace("bvm_preset_btn_", "")
                    m._apply_preset(name)  # type: ignore[attr-defined]
                except Exception:
                    pass
    if imgui.button("Reset all floats##sq_bvm_rst"):
        m._reset_all()  # type: ignore[attr-defined]


def _draw_damage(imgui: Any) -> None:
    d = _try_import("bl4_damage_and_more")
    if d is None:
        imgui.text_colored((1.0, 0.55, 0.45, 1.0), "bl4_damage_and_more is not installed or failed to import.")
        return
    imgui.text_wrapped("DamageState / DamageCauserData on the local pawn. Load in-world.")

    mo = d._master_opt  # type: ignore[attr-defined]
    so = d._sticky_opt  # type: ignore[attr-defined]
    oid_m = str(getattr(mo, "identifier", "bdam_master"))
    oid_s = str(getattr(so, "identifier", "bdam_sticky"))
    try:
        mcur = bool(mo.value)
    except Exception:
        mcur = True
    chm, nmv = imgui.checkbox(f"Enable damage tuning###sq_{oid_m}", mcur)
    if chm:
        try:
            mo.value = bool(nmv)
        except Exception:
            pass
        try:
            d._on_master(None, bool(nmv))  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        scur = bool(so.value)
    except Exception:
        scur = False
    chs, nsv = imgui.checkbox(f"Sticky re-apply (~0.35s)###sq_{oid_s}", scur)
    if chs:
        try:
            so.value = bool(nsv)
        except Exception:
            pass
        try:
            d._on_sticky(None, bool(nsv))  # type: ignore[attr-defined]
        except Exception:
            pass

    def _apply_slider_batch(sliders: list[Any], specs: tuple[Any, ...]) -> None:
        for opt, spec in zip(sliders, specs, strict=True):
            attr = spec[0]
            lo, hi, _step, _def, title = spec[1], spec[2], spec[3], spec[4], spec[5]
            try:
                cur = float(opt.value)
            except Exception:
                cur = float(_def)
            ch, nv = imgui.slider_float(f"{title}###sqbd_{attr}", cur, float(lo), float(hi))
            if ch:
                try:
                    opt.value = float(nv)
                except Exception:
                    pass
                d._apply_damage_tuning(log_hits=False)  # type: ignore[attr-defined]

    if imgui.collapsing_header("Incoming (DamageState)", True):
        _apply_slider_batch(d._slider_ds, d._DS_SPECS)  # type: ignore[attr-defined]
    if imgui.collapsing_header("Intrinsic armor", True):
        opt = d._slider_intrinsic  # type: ignore[attr-defined]
        spec = d._INTRINSIC_ARMOR_SPEC  # type: ignore[attr-defined]
        lo, hi, _step, _def, title = spec[1], spec[2], spec[3], spec[4], spec[5]
        try:
            cur = float(opt.value)
        except Exception:
            cur = float(_def)
        ch, nv = imgui.slider_float(f"{title}###sqbd_intr", cur, float(lo), float(hi))
        if ch:
            try:
                opt.value = float(nv)
            except Exception:
                pass
            d._apply_damage_tuning(log_hits=False)  # type: ignore[attr-defined]
    if imgui.collapsing_header("Outgoing (DamageCauserData)", True):
        _apply_slider_batch(d._slider_dcd, d._DCD_SPECS)  # type: ignore[attr-defined]
    if imgui.collapsing_header("Advanced", False):
        _apply_slider_batch(d._slider_adv, d._ADV_DS_SPECS)  # type: ignore[attr-defined]
    if imgui.button("Apply now##sqbd_apply"):
        d._apply_damage_tuning(log_hits=True)  # type: ignore[attr-defined]
    imgui.same_line()
    if imgui.button("Reset sliders##sqbd_rst"):
        d._on_reset_btn(None)  # type: ignore[attr-defined]
    imgui.same_line()
    if imgui.button("Probe##sqbd_prb"):
        d.bdam_probe_impl()  # type: ignore[attr-defined]


def _draw_tuning_tab() -> None:
    imgui = _imgui_bundle()
    has_p = _try_import("bl4_player_movement") is not None
    has_v = _try_import("bl4_vehicle_movement") is not None
    has_d = _try_import("bl4_damage_and_more") is not None
    n = sum(1 for x in (has_p, has_v, has_d) if x)

    imgui.text_wrapped(
        f"Tuning GUI — {n} companion mod(s) loaded. "
        "If you only see a demo / hello-world panel, open the tab titled "
        f"{TAB_TITLE!r} here (this mod registers after blimgui loads).",
    )
    imgui.separator()
    if n == 0:
        imgui.text_wrapped(
            "No companion tuning mods detected. Install one or more of: "
            "**bl4_player_movement**, **bl4_vehicle_movement**, **bl4_damage_and_more** (folders under sdk_mods).",
        )
    elif n == 1:
        if has_p:
            _draw_player(imgui)
        elif has_v:
            _draw_vehicle(imgui)
        else:
            _draw_damage(imgui)
    else:
        if imgui.begin_tab_bar("TuningGuiInner##tg"):
            if has_p and _begin_tab_item_draw(imgui, "Player"):
                _draw_player(imgui)
                imgui.end_tab_item()
            if has_v and _begin_tab_item_draw(imgui, "Vehicle"):
                _draw_vehicle(imgui)
                imgui.end_tab_item()
            if has_d and _begin_tab_item_draw(imgui, "Damage"):
                _draw_damage(imgui)
                imgui.end_tab_item()
            imgui.end_tab_bar()

    imgui.separator()
    imgui.text_disabled("made by Squ1ggs")


def _register_tab() -> None:
    global _blimgui_tab_registered
    try:
        bg = _imgui_mod()
        tabs = getattr(bg, "TABS", None)
        if isinstance(tabs, dict) and TAB_TITLE in tabs:
            _blimgui_tab_registered = True
            return
        bg.register_tab(TAB_TITLE, _draw_tuning_tab)
        _blimgui_tab_registered = True
        _log(f"Registered BLImGui tab {TAB_TITLE!r}")
    except Exception as ex:
        _log(f"Could not register BLImGui tab (is blimgui enabled?): {ex}")


def _unregister_tab() -> None:
    global _blimgui_tab_registered
    if not _blimgui_tab_registered:
        return
    try:
        bg = _imgui_mod()
        tabs = getattr(bg, "TABS", None)
        if isinstance(tabs, dict) and TAB_TITLE in tabs:
            bg.remove_tab(TAB_TITLE)
    except Exception:
        pass
    _blimgui_tab_registered = False


def _on_enable() -> None:
    global _blimgui_register_retry_token
    _blimgui_register_retry_token += 1
    token = _blimgui_register_retry_token

    def _attempt(attempt: int = 0) -> None:
        if token != _blimgui_register_retry_token:
            return
        if _blimgui_tab_registered:
            return
        _register_tab()
        if token != _blimgui_register_retry_token:
            return
        if not _blimgui_tab_registered and attempt < 120:
            threading.Timer(0.25, lambda: _attempt(attempt + 1)).start()

    _attempt()


def _on_disable() -> None:
    global _blimgui_register_retry_token
    _blimgui_register_retry_token += 1
    _unregister_tab()


def _open_blimgui_menu() -> None:
    try:
        _register_tab()
        bg = _imgui_mod()
        bg.open_mod_menu()
    except Exception as ex:
        logging.warning(f"{LOG_PREFIX} open_mod_menu failed: {ex}")


@command("sqgui_open", description="Open the BL4 Mod Menu on the Tuning GUI tab (requires blimgui).")
def sqgui_open(_args: argparse.Namespace) -> None:  # noqa: ARG001
    _open_blimgui_menu()


KEY_OPEN_MENU = keybind(
    "sqgui_open_mod_menu",
    key="F1",
    callback=_open_blimgui_menu,
    display_name="Open BL4 Mod Menu (Tuning GUI)",
    description=(
        "Opens the ImGui mod menu (same key as blimgui's default) and ensures the "
        "Tuning GUI tab is registered. Rebind in Mods → Keybinds if it conflicts."
    ),
)


_squ1ggs_gui_mod = build_mod(
    name=MOD_NAME,
    author=__author__,
    description="ImGui Tuning GUI tab for player / vehicle / damage mods (requires blimgui).",
    version=__version__,
    supported_games=Game.BL4,
    coop_support=CoopSupport.ClientSide,
    settings_file=SETTINGS_PATH,
    commands=[sqgui_open],
    keybinds=[KEY_OPEN_MENU],
    options=[],
    on_enable=_on_enable,
    on_disable=_on_disable,
)
