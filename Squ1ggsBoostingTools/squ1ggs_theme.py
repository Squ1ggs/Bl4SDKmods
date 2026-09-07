"""Squ1ggs Boosting Tools — BLImGui accent palette + window chrome."""

from __future__ import annotations

from typing import Any

from ._mod_version import __version__ as PANEL_VERSION
BRAND_TAGLINE = "Boosting Tools // build a session, reward the squad, move on."
BRAND_SHORT = "Squ1ggs"

# Core palette (BLImGui cyber color keys)
ACCENT_PRIMARY = "violet"
ACCENT_SECONDARY = "sky"
ACCENT_INFO = "sky"
ACCENT_SUCCESS = "emerald"
ACCENT_WARN = "orange"
ACCENT_DANGER = "rose"
ACCENT_MUTED = "slate"
ACCENT_VIOLET = "violet"

TAB_ACCENTS: tuple[str, ...] = (
    ACCENT_PRIMARY,
    ACCENT_INFO,
    ACCENT_SECONDARY,
    ACCENT_VIOLET,
    ACCENT_WARN,
    ACCENT_SUCCESS,
    ACCENT_INFO,
    ACCENT_SECONDARY,
    ACCENT_DANGER,
    ACCENT_SUCCESS,
    ACCENT_PRIMARY,
    ACCENT_WARN,
    ACCENT_MUTED,
)

TAB_SHORT_LABELS: tuple[str, ...] = (
    "Home",
    "Player",
    "UVHM",
    "Loot",
    "Serials",
    "Mobility",
    "On Foot",
    "Vehicle",
    "Damage",
    "Kits",
    "World",
    "Shapes",
    "Activity",
)

TAB_ROW_SPLIT = 6

CARD_ACCENTS: dict[str, str] = {
    "serial": ACCENT_PRIMARY,
    "currency": ACCENT_SUCCESS,
    "experience": ACCENT_INFO,
    "inventory": ACCENT_INFO,
    "sdu": ACCENT_SECONDARY,
    "dev": ACCENT_DANGER,
    "rarity": ACCENT_VIOLET,
    "serial_tools": ACCENT_INFO,
    "serial_store": ACCENT_PRIMARY,
    "gzo": ACCENT_SECONDARY,
    "lootlemon": ACCENT_WARN,
    "itempool": ACCENT_SUCCESS,
    "forge": ACCENT_PRIMARY,
    "mobility": ACCENT_INFO,
    "world": ACCENT_SECONDARY,
    "travel": ACCENT_INFO,
    "log": ACCENT_MUTED,
    "command_deck": ACCENT_PRIMARY,
}

# Semantic button roles (teal / amber / emerald row)
BTN_MAX_ALL = ACCENT_SECONDARY
BTN_CASH = ACCENT_SUCCESS
BTN_ERIDIUM = ACCENT_VIOLET
BTN_XP = ACCENT_INFO
BTN_SPEC = ACCENT_PRIMARY
BTN_GIVE = ACCENT_PRIMARY
BTN_DANGER = ACCENT_DANGER
BTN_NEUTRAL = ACCENT_MUTED
BTN_HIGHLIGHT = ACCENT_WARN

_LEGACY_ACCENT_MAP: dict[str, str] = {
    "purple": ACCENT_VIOLET,
    "cyan": ACCENT_INFO,
    "gold": ACCENT_SECONDARY,
    "green": ACCENT_SUCCESS,
    "pink": ACCENT_DANGER,
    "red": ACCENT_DANGER,
    "yellow": ACCENT_WARN,
    "blue": ACCENT_INFO,
    "orange": ACCENT_WARN,
    "teal": ACCENT_PRIMARY,
    "amber": ACCENT_SECONDARY,
    "emerald": ACCENT_SUCCESS,
    "rose": ACCENT_DANGER,
    "sky": ACCENT_INFO,
    "slate": ACCENT_MUTED,
    "violet": ACCENT_VIOLET,
}


def resolve_accent(name: str) -> str:
    key = str(name or ACCENT_PRIMARY).strip().lower()
    return _LEGACY_ACCENT_MAP.get(key, key)


def card_accent(card_key: str) -> str:
    return CARD_ACCENTS.get(str(card_key or "").strip().lower(), ACCENT_PRIMARY)


def _v4(cyber: Any | None, accent: str) -> Any:
    if cyber is None:
        return None
    key = resolve_accent(accent).upper()
    color = getattr(cyber, key, None)
    if color is None:
        color = getattr(cyber, "TEAL", None)
    return cyber._v4(color) if color is not None else None


def push_squ1ggs_window_style(imgui: Any, cyber: Any | None) -> int:
    """Teal-tinted window chrome on top of BLImGui cyber defaults."""
    if cyber is None:
        return 0
    base = 0
    try:
        base = int(cyber.push_cyber_window_style())
    except Exception:
        base = 0
    extra = 0
    try:
        col = imgui.Col_
        pushes: list[tuple[Any, Any]] = []
        teal = _v4(cyber, ACCENT_PRIMARY)
        amber = _v4(cyber, ACCENT_SECONDARY)
        slate = _v4(cyber, ACCENT_MUTED)
        if teal is not None:
            pushes.append((col.border, teal))
            pushes.append((col.separator, teal))
        if amber is not None:
            pushes.append((col.title_bg_active, amber))
        if slate is not None:
            pushes.append((col.text_disabled, slate))
        for c, v in pushes:
            try:
                imgui.push_style_color(c, v)
                extra += 1
            except Exception:
                pass
    except Exception:
        pass
    return base + extra


def pop_window_style(imgui: Any, count: int) -> None:
    if count <= 0:
        return
    try:
        imgui.pop_style_color(count)
    except Exception:
        pass


def section_header(cyber: Any | None, imgui: Any, title: str, accent: str = ACCENT_PRIMARY) -> None:
    accent = resolve_accent(accent)
    if cyber is not None:
        try:
            cyber.section_header(title, accent)
            return
        except Exception:
            pass
    imgui.separator()
    imgui.text(title.upper())


def begin_card(cyber: Any | None, title: str, accent: str, height: float) -> bool:
    accent = resolve_accent(accent)
    if cyber is not None:
        try:
            return bool(cyber.begin_card(title, accent, float(height)))
        except Exception:
            pass
    return True


def end_card(cyber: Any | None) -> None:
    if cyber is not None:
        try:
            cyber.end_card()
        except Exception:
            pass


def metric(cyber: Any | None, label: str, value: str, accent: str = ACCENT_PRIMARY) -> None:
    accent = resolve_accent(accent)
    if cyber is not None:
        try:
            cyber.metric(label, value, accent)
            return
        except Exception:
            pass


def draw_brand_banner(cyber: Any | None, imgui: Any, *, version: str, session: str, players: int) -> None:
    """Top hero strip for the boosting panel."""
    if cyber is not None:
        try:
            cyber.title("SQU1GGS // Boosting Tools", BRAND_TAGLINE)
        except Exception:
            imgui.text("SQU1GGS // Boosting Tools")
    else:
        imgui.text("SQU1GGS // Boosting Tools")
        imgui.text_wrapped(BRAND_TAGLINE)
    try:
        teal = _v4(cyber, ACCENT_PRIMARY)
        if teal is not None:
            imgui.push_style_color(imgui.Col_.text, teal)
        imgui.text_wrapped(f"{BRAND_SHORT} v{version}  |  {session}  |  {players} player(s) connected")
        if teal is not None:
            imgui.pop_style_color()
    except Exception:
        imgui.text_wrapped(f"{BRAND_SHORT} v{version} | {session} | {players} player(s)")
    try:
        amber = _v4(cyber, ACCENT_SECONDARY)
        if amber is not None:
            imgui.push_style_color(imgui.Col_.text, amber)
        imgui.text_wrapped("HOST CONSOLE  /  rewards  /  builds  /  mobility  /  world control")
        if amber is not None:
            imgui.pop_style_color()
    except Exception:
        pass
    imgui.spacing()
