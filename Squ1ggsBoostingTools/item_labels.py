"""Party Bay / inventory display labels from @U + bundled gzo_parts_map.

Live DisplayName on the InventoryItem wins when present. Otherwise decode
manufacturer / type / rarity / lore name from the serial via GZO part ids.
Shallow only — no NHA memory scans (those hitch/AV on fat packs).
"""
from __future__ import annotations

import json
import pkgutil
import re
from typing import Any

_GZO_PARTS_MAP: dict[str, dict[str, str]] | None = None
_GZO_TYPE_ID_INDEX: dict[int, tuple[str, dict[str, str]]] | None = None

_GZO_MAKER_PREFIXES = {
    "DAD": "Daedalus",
    "JAK": "Jakobs",
    "ORD": "Order",
    "TED": "Tediore",
    "TOR": "Torgue",
    "VLA": "Vladof",
    "MAL": "Maliwan",
    "BOR": "Ripper",
    "RIP": "Ripper",
    "COV": "CoV",
    "ATL": "Atlas",
    "HYP": "Hyperion",
    "C4SH": "C4SH",
}

_GZO_TYPE_SUFFIXES = {
    "PS": "Pistol",
    "SG": "Shotgun",
    "AR": "Assault Rifle",
    "SMG": "SMG",
    "SM": "SMG",
    "SR": "Sniper",
    "HW": "Heavy Weapon",
    "HEAVY": "Heavy Weapon",
    "SHIELD": "Shield",
    "ARMOR_SHIELD": "Shield",
    "ENERGY_SHIELD": "Shield",
    "GADGET": "Ordnance",
    "GRENADE_GADGET": "Ordnance",
    "TURRET_GADGET": "Ordnance",
    "HEAVY_WEAPON_GADGET": "Ordnance",
    "TERMINAL_GADGET": "Ordnance",
    "TERMINAL_BARRIER": "Ordnance",
    "BARRIER": "Ordnance",
    "ORDNANCE": "Ordnance",
    "ENHANCEMENT": "Enhancement",
    "REPAIR_KIT": "Repkit",
    "REPKIT": "Repkit",
    "CLASS_MOD": "Classmod",
    "CLASSMOD": "Classmod",
}

# Extra substring → type when family labels are noisy (e.g. BOR_TERMINAL_BARRIER).
_GZO_TYPE_HINTS: tuple[tuple[str, str], ...] = (
    ("classmod", "Classmod"),
    ("class_mod", "Classmod"),
    ("repair_kit", "Repkit"),
    ("repkit", "Repkit"),
    ("enhancement", "Enhancement"),
    ("grenade_gadget", "Ordnance"),
    ("turret_gadget", "Ordnance"),
    ("heavy_weapon_gadget", "Ordnance"),
    ("terminal_barrier", "Ordnance"),
    ("terminal_gadget", "Ordnance"),
    ("_gadget", "Ordnance"),
    ("energy_shield", "Shield"),
    ("armor_shield", "Shield"),
    ("_shield", "Shield"),
    ("shield", "Shield"),
)

_GZO_CLASS_NAMES = {
    "siren": "Siren",
    "dark_siren": "Siren",
    "forgeknight": "Paladin",
    "paladin": "Paladin",
    "exo_soldier": "Exo Soldier",
    "gravitar": "Gravitar",
    "ai": "AI",
    "c4sh": "C4SH",
    "robodealer": "C4SH",
    "corpohacker": "Loveless",
    "corpo_hacker": "Loveless",
    "hacker": "Loveless",
    "loveless": "Loveless",
}

_GUN_TYPES = frozenset(
    {"Pistol", "Shotgun", "Assault Rifle", "SMG", "Sniper", "Heavy Weapon"}
)

_RARITY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("pearlescent", "Pearlescent"),
    ("pearl", "Pearlescent"),
    ("legendary", "Legendary"),
    ("epic", "Epic"),
    ("uncommon", "Uncommon"),
    ("common", "Common"),
    ("rare", "Rare"),
)

# Composition rarity keys in gzo_parts_map (prefer over free-text keyword guess).
_COMP_RARITY_RE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?:^|\.)(?:base_)?comp_06_pearl(?:escent)?(?:_|$)", re.I), "Pearlescent"),
    (re.compile(r"(?:^|\.)(?:base_)?comp_05_legendary(?:_|$)", re.I), "Legendary"),
    (re.compile(r"(?:^|\.)(?:base_)?comp_04_epic(?:_|$)", re.I), "Epic"),
    (re.compile(r"(?:^|\.)(?:base_)?comp_03_rare(?:_|$)", re.I), "Rare"),
    (re.compile(r"(?:^|\.)(?:base_)?comp_02_uncommon(?:_|$)", re.I), "Uncommon"),
    (re.compile(r"(?:^|\.)(?:base_)?comp_01_common(?:_|$)", re.I), "Common"),
)

# Unique lore name on legendary / pearl compositions (guns + most gear).
_UNIQUE_COMP_RE = re.compile(
    r"(?:^|\.)(?:base_)?comp_0(?:5_legendary|6_pearl(?:escent)?)_(.+)$",
    re.I,
)

# Some shields/grenades use bare comp_05_<name> without the legendary token.
_COMP05_NAMED_RE = re.compile(
    r"(?:^|\.)(?:base_)?comp_05_(?!legendary(?:_|$)|pearl(?:escent)?(?:_|$))(.+)$",
    re.I,
)

# Named barrels sometimes carry the unique slug (e.g. part_barrel_01_prism).
_NAMED_BARREL_RE = re.compile(r"(?:^|\.)part_barrel_\d+_(.+)$", re.I)

# Non-gun unique carriers: shields, enhancements, repkits, ordnance.
# Firmware is handled separately (enhancements only) — never via this list for guns/classmods.
_NAMED_PART_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|\.)part_unique_(.+)$", re.I),
    re.compile(r"(?:^|\.)part_core_[a-z0-9]+_(.+)$", re.I),
    re.compile(r"(?:^|\.)part_augment_unique_(.+)$", re.I),
    re.compile(r"(?:^|\.)part_body_armor_(.+)$", re.I),
    # Avoid rarity stubs + mundane frame bits (mag_sg / body_b → "Mag Sg" / "B").
    re.compile(
        r"(?:^|\.)part_body_(?!ele_|armor(?:_|$)|mag_|scope_|grip_|stock_|underbarrel_|"
        r"0?\d+[_\-]?(?:common|uncommon|rare|epic|legendary|pearl)|[a-d]$)"
        r"(.+)$",
        re.I,
    ),
    re.compile(r"(?:^|\.)leg_body_(.+)$", re.I),
)

# Enhancements (and similar) can be named by their firmware slug.
_FIRMWARE_UNIQUE_RE = re.compile(r"(?:^|\.)part_firmware_(.+)$", re.I)

# Shared ClassMod part bags (firmware / universal stats) — safe to expand on classmods only.
_CLASSMOD_SHARED_BAG_SETS = frozenset({234, 247})

_DAMAGE_TYPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?:^|[_\.])(?:incendiary|fire)(?:[_\.]|$)", re.I), "Fire"),
    (re.compile(r"(?:^|[_\.])(?:shock|electric)(?:[_\.]|$)", re.I), "Shock"),
    (re.compile(r"(?:^|[_\.])cryo(?:[_\.]|$)", re.I), "Cryo"),
    (re.compile(r"(?:^|[_\.])corrosive(?:[_\.]|$)", re.I), "Corrosive"),
    (re.compile(r"(?:^|[_\.])(?:radiation|rad)(?:[_\.]|$)", re.I), "Radiation"),
    (re.compile(r"(?:^|[_\.])kinetic(?:[_\.]|$)", re.I), "Kinetic"),
)

_WEAK_BARREL_SUFFIXES = frozenset(
    {
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "base",
        "body",
        "stock",
        "mag",
        "scope",
        "grip",
        "foregrip",
        "armor",
        "energy",
        "common",
        "uncommon",
        "rare",
        "epic",
        "legendary",
        "pearl",
        "pearlescent",
    }
)

# Class-mod legendary comps often end in 01..06; keep named DLC/raid tokens.
_CLASSMOD_NAMED_TOKENS = frozenset(
    {
        "raid1",
        "raid2",
        "cowbell",
        "tuba",
        "dlc1",
        "dlc2",
        "harmonica",
    }
)

# Numbered classmod legendary / leg_body slots lack lore slugs in GZO — map spawn → card name.
# Keys are lowercase `set.leaf` (and bare leaf for unique corpohacker 01–06 only when set known).
_CLASSMOD_DISPLAY_BY_PART: dict[str, str] = {
    "classmod_dark_siren.leg_body_cowbell": "Configuration",
    "classmod_dark_siren.comp_05_legendary_cowbell": "Configuration",
    "classmod_dark_siren.leg_body_raid1": "Misericorde",
    "classmod_dark_siren.comp_05_legendary_raid1": "Misericorde",
    "classmod_dark_siren.leg_body_raid2": "Grim Sister",
    "classmod_dark_siren.comp_05_legendary_raid2": "Grim Sister",
    "classmod_dark_siren.leg_body_tuba": "Living Weapon",
    "classmod_dark_siren.comp_05_legendary_tuba": "Living Weapon",
    "classmod_exo_soldier.leg_body_cowbell": "Reaparición",
    "classmod_exo_soldier.comp_05_legendary_cowbell": "Reaparición",
    "classmod_exo_soldier.leg_body_raid1": "Overdriver",
    "classmod_exo_soldier.comp_05_legendary_raid1": "Overdriver",
    "classmod_exo_soldier.leg_body_raid2": "Bombastic",
    "classmod_exo_soldier.comp_05_legendary_raid2": "Bombastic",
    "classmod_exo_soldier.leg_body_tuba": "Power-Puncher",
    "classmod_exo_soldier.comp_05_legendary_tuba": "Power-Puncher",
    "classmod_gravitar.leg_body_cowbell": "Phlebotomist",
    "classmod_gravitar.comp_05_legendary_cowbell": "Phlebotomist",
    "classmod_gravitar.leg_body_raid1": "Trooper",
    "classmod_gravitar.comp_05_legendary_raid1": "Trooper",
    "classmod_gravitar.leg_body_raid2": "Plasmaphile",
    "classmod_gravitar.comp_05_legendary_raid2": "Plasmaphile",
    "classmod_gravitar.leg_body_tuba": "Chirurgeon",
    "classmod_gravitar.comp_05_legendary_tuba": "Chirurgeon",
    "classmod_paladin.leg_body_cowbell": "Tempest",
    "classmod_paladin.comp_05_legendary_cowbell": "Tempest",
    "classmod_paladin.leg_body_raid1": "Lamplighter",
    "classmod_paladin.comp_05_legendary_raid1": "Lamplighter",
    "classmod_paladin.leg_body_raid2": "Artificer",
    "classmod_paladin.comp_05_legendary_raid2": "Artificer",
    "classmod_paladin.leg_body_tuba": "Damned",
    "classmod_paladin.comp_05_legendary_tuba": "Damned",
    "classmod_robodealer.leg_body_raid1": "Hooligan",
    "classmod_robodealer.comp_05_legendary_raid1": "Hooligan",
    "classmod_robodealer.leg_body_raid2": "Prestidigitator",
    "classmod_robodealer.comp_05_legendary_raid2": "Prestidigitator",
    "classmod_robodealer.leg_body_tuba": "Trainer",
    "classmod_robodealer.comp_05_legendary_tuba": "Trainer",
    "classmod_corpohacker.leg_body_01": "Devourer",
    "classmod_corpohacker.comp_05_legendary_01": "Devourer",
    "classmod_corpohacker.leg_body_02": "Virophile",
    "classmod_corpohacker.comp_05_legendary_02": "Virophile",
    "classmod_corpohacker.leg_body_03": "Montage Maker",
    "classmod_corpohacker.comp_05_legendary_03": "Montage Maker",
    "classmod_corpohacker.leg_body_04": "Memory Hoarder",
    "classmod_corpohacker.comp_05_legendary_04": "Memory Hoarder",
    "classmod_corpohacker.leg_body_05": "Trackstar",
    "classmod_corpohacker.comp_05_legendary_05": "Trackstar",
    "classmod_corpohacker.leg_body_06": "Functional Human",
    "classmod_corpohacker.comp_05_legendary_06": "Functional Human",
    "classmod_corpohacker.leg_body_dlc1": "Martyr",
    "classmod_corpohacker.comp_05_legendary_dlc1": "Martyr",
    "classmod_corpohacker.leg_body_cowbell": "Martyr",
    "classmod_corpohacker.comp_05_legendary_cowbell": "Martyr",
    "classmod_corpohacker.leg_body_dlc2": "Programmer",
    "classmod_corpohacker.comp_05_legendary_dlc2": "Programmer",
    "classmod_corpohacker.leg_body_harmonica": "Programmer",
    "classmod_corpohacker.comp_05_legendary_harmonica": "Programmer",
    "classmod_corpohacker.leg_body_raid1": "Boomer",
    "classmod_corpohacker.comp_05_legendary_raid1": "Boomer",
    "classmod_corpohacker.leg_body_raid2": "Plague Engineer",
    "classmod_corpohacker.comp_05_legendary_raid2": "Plague Engineer",
    "classmod_corpohacker.leg_body_tuba": "Puppetmaster",
    "classmod_corpohacker.comp_05_legendary_tuba": "Puppetmaster",
}


def _title_from_slug(text: str) -> str:
    text = re.sub(r"[_\-]+", " ", str(text or "")).strip()
    return " ".join(
        w.upper() if w.lower() in ("smg", "ai", "cov") else w.capitalize()
        for w in text.split()
    )


def _load_parts_map() -> dict[str, dict[str, str]]:
    global _GZO_PARTS_MAP, _GZO_TYPE_ID_INDEX
    if _GZO_PARTS_MAP is not None:
        return _GZO_PARTS_MAP
    data: dict[str, dict[str, str]] = {}
    blob: bytes | None = None
    try:
        blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], "gzo_parts_map.json")
    except Exception:
        blob = None
    if not blob:
        try:
            from pathlib import Path

            path = Path(__file__).with_name("gzo_parts_map.json")
            if path.is_file():
                blob = path.read_bytes()
        except Exception:
            blob = None
    try:
        if blob:
            raw = json.loads(blob.decode("utf-8", "replace"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, dict):
                        data[str(k)] = {str(pk): str(pv) for pk, pv in v.items()}
    except Exception:
        data = {}
    _GZO_PARTS_MAP = data
    idx: dict[int, tuple[str, dict[str, str]]] = {}
    for key, table in data.items():
        m = re.match(r"\s*(\d+)\s*\|\s*(.+?)\s*$", str(key))
        if m:
            idx[int(m.group(1))] = (m.group(2), table)
    _GZO_TYPE_ID_INDEX = idx
    return data


def _type_id_index() -> dict[int, tuple[str, dict[str, str]]]:
    _load_parts_map()
    return _GZO_TYPE_ID_INDEX or {}


def type_info_from_id(type_id: int) -> dict[str, str]:
    label_table = _type_id_index().get(int(type_id))
    if not label_table:
        return {
            "type_id": str(type_id),
            "set": "",
            "manufacturer": "",
            "type": "",
            "character_class": "",
        }
    label = label_table[0]
    raw = label.strip()
    low = raw.lower()
    info = {
        "type_id": str(type_id),
        "set": raw,
        "manufacturer": "",
        "type": "",
        "character_class": "",
    }
    if "classmod" in low or "class_mod" in low:
        info["type"] = "Classmod"
        tail = low.replace("classmod", "").replace("class_mod", "").strip("_")
        info["character_class"] = (
            _GZO_CLASS_NAMES.get(tail, _title_from_slug(tail)) if tail else ""
        )
        return info
    pieces = re.split(r"[_\s]+", raw)
    if pieces:
        prefix = pieces[0].upper()
        if prefix in _GZO_MAKER_PREFIXES:
            info["manufacturer"] = _GZO_MAKER_PREFIXES[prefix]
        # Prefer longest suffix match (grenade_gadget before gadget).
        for i in range(1, len(pieces)):
            suffix = "_".join(pieces[i:]).upper()
            if suffix in _GZO_TYPE_SUFFIXES:
                info["type"] = _GZO_TYPE_SUFFIXES[suffix]
                break
        if not info["type"]:
            alone = pieces[0].upper()
            if alone in _GZO_TYPE_SUFFIXES:
                info["type"] = _GZO_TYPE_SUFFIXES[alone]
    if not info["type"]:
        for key, val in _GZO_TYPE_HINTS:
            if key in low:
                info["type"] = val
                break
    if not info["manufacturer"] and pieces:
        for piece in pieces:
            pref = piece.upper()
            if pref in _GZO_MAKER_PREFIXES:
                info["manufacturer"] = _GZO_MAKER_PREFIXES[pref]
                break
            if pref.startswith("BOR"):
                info["manufacturer"] = "Ripper"
                break
    return info


def category_for_type(item_type: str) -> str:
    t = str(item_type or "").strip()
    if t in _GUN_TYPES:
        return "Guns"
    if t == "Shield":
        return "Shields"
    if t in ("Ordnance", "Gadget"):
        return "Ordnance"
    if t == "Repkit":
        return "Repkits"
    if t == "Enhancement":
        return "Enhancements"
    if t == "Classmod":
        return "Class Mods"
    return "Other"


def _leaf_part_name(part_name: str) -> str:
    text = str(part_name or "").strip()
    if "." in text:
        return text.rsplit(".", 1)[-1].strip()
    return text


_INGAME_PART_NAMES: tuple[dict[str, str], dict[str, str]] | None = None


def _load_ingame_part_names() -> tuple[dict[str, str], dict[str, str]]:
    """set.part / part → in-game name (comp_05_legendary_murder → Murmur)."""
    global _INGAME_PART_NAMES
    if _INGAME_PART_NAMES is not None:
        return _INGAME_PART_NAMES
    by_set: dict[str, str] = {}
    by_leaf: dict[str, str] = {}
    blob: bytes | None = None
    try:
        blob = pkgutil.get_data(__package__ or __name__.rpartition(".")[0], "ingame_part_names.json")
    except Exception:
        blob = None
    if not blob:
        try:
            from pathlib import Path

            path = Path(__file__).with_name("ingame_part_names.json")
            if path.is_file():
                blob = path.read_bytes()
        except Exception:
            blob = None
    try:
        if blob:
            raw = json.loads(blob.decode("utf-8", "replace"))
            if isinstance(raw, dict):
                by_set = {str(k).lower(): str(v) for k, v in (raw.get("by_set") or {}).items() if v}
                by_leaf = {str(k).lower(): str(v) for k, v in (raw.get("by_leaf") or {}).items() if v}
    except Exception:
        by_set, by_leaf = {}, {}
    _INGAME_PART_NAMES = (by_set, by_leaf)
    return _INGAME_PART_NAMES


def _ingame_part_name(part_name: str, set_label: str = "") -> str:
    by_set, by_leaf = _load_ingame_part_names()
    full = str(part_name or "").strip().lower()
    if not full:
        return ""
    leaf = _leaf_part_name(full)
    if "." in full and by_set.get(full):
        return by_set[full]
    set_low = str(set_label or "").strip().lower()
    if set_low and by_set.get(f"{set_low}.{leaf}"):
        return by_set[f"{set_low}.{leaf}"]
    return by_leaf.get(leaf, "")


def _humanize_unique_token(token: str) -> str:
    """SilverSliver / soul_survivor / PRISM → display-friendly label."""
    raw = str(token or "").strip()
    if not raw:
        return ""
    # Split CamelCase / acronyms: SilverSliver, NoisyCricket, ATLien, PRISM.
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    spaced = spaced.replace("_", " ").replace("-", " ")
    words: list[str] = []
    for word in spaced.split():
        if not word:
            continue
        if word.isupper() and 2 <= len(word) <= 8:
            words.append(word)
        elif word.isupper():
            words.append(word.capitalize())
        elif any(ch.isupper() for ch in word[1:]):
            words.append(word)
        else:
            words.append(word.capitalize())
    return " ".join(words).strip()


def _is_weak_unique_token(token: str) -> bool:
    t = str(token or "").strip().lower()
    if not t or len(t) <= 1:
        return True
    if re.fullmatch(r"\d+", t):
        return True
    # Class-mod numbered slots (01..06) lack inv_name_part in GZO alone.
    if re.fullmatch(r"0?\d{1,2}", t):
        return True
    if re.fullmatch(
        r"(?:0?\d+[_\-]?)?(?:common|uncommon|rare|epic|legendary|pearl|pearlescent)",
        t,
    ):
        return True
    if t in _WEAK_BARREL_SUFFIXES:
        return True
    if t.startswith("ele_"):
        return True
    return False


def _token_from_named_patterns(leaf: str, *, allow_firmware: bool = False) -> str:
    patterns: tuple[re.Pattern[str], ...] = (
        _UNIQUE_COMP_RE,
        _COMP05_NAMED_RE,
        _NAMED_BARREL_RE,
        *_NAMED_PART_RES,
    )
    if allow_firmware:
        patterns = (*patterns, _FIRMWARE_UNIQUE_RE)
    for pattern in patterns:
        m = pattern.search(leaf)
        if not m:
            continue
        token = str(m.group(1) or "").strip()
        if not token:
            continue
        low = token.lower()
        # Allow known class-mod DLC/raid lore tokens that look "weak" otherwise.
        if low in _CLASSMOD_NAMED_TOKENS:
            return token
        if _is_weak_unique_token(token):
            continue
        if token.lower().startswith("ele_"):
            continue
        # Single-letter / tiny body suffixes (b, d, mag_sg leftovers).
        if len(low) <= 2 and not low in _CLASSMOD_NAMED_TOKENS:
            continue
        return token
    return ""


def _classmod_display_from_parts(names: list[str], *, set_label: str = "") -> str:
    """Resolve known classmod legendary/body spawn codes to in-game titles."""
    set_low = str(set_label or "").strip().lower()
    bodies: list[str] = []
    comps: list[str] = []
    for raw in names:
        leaf = _leaf_part_name(raw).lower()
        full = str(raw or "").strip().lower()
        if re.search(r"(?:^|\.)(?:leg_)?body_", leaf):
            bodies.append(str(raw or ""))
            continue
        if not re.search(r"(?:^|\.)(?:base_)?comp_05_legendary_", leaf):
            continue
        # Only our classmod table — never foreign gun/shield legendaries (Firewerks).
        if full.startswith("classmod_"):
            comps.append(str(raw or ""))
            continue
        if set_low and _CLASSMOD_DISPLAY_BY_PART.get(f"{set_low}.{leaf}"):
            comps.append(str(raw or ""))
    for name in bodies + comps:
        leaf = _leaf_part_name(name)
        if not leaf:
            continue
        candidates = []
        low_full = str(name or "").strip().lower()
        if "." in low_full:
            candidates.append(low_full)
        if set_low:
            candidates.append(f"{set_low}.{leaf.lower()}")
        for key in candidates:
            hit = _CLASSMOD_DISPLAY_BY_PART.get(key)
            if hit:
                return hit
        if name in bodies:
            hit = _ingame_part_name(name, set_low)
            if hit:
                return hit
    return ""


def _unique_display_from_part_names(
    names: list[str],
    *,
    set_label: str = "",
    item_type: str = "",
) -> str:
    """Prefer legendary/pearl comps, then other unique carriers across all item types."""
    type_low = str(item_type or "").strip().casefold()
    set_low = str(set_label or "").strip().casefold()
    is_classmod = type_low == "classmod" or "classmod" in set_low
    allow_firmware = type_low in ("enhancement",)
    if is_classmod:
        known = _classmod_display_from_parts(names, set_label=set_label)
        if known:
            return known
    for name in names:
        leaf = _leaf_part_name(name)
        full = str(name or "").strip().lower()
        if is_classmod and not full.startswith("classmod_"):
            if re.search(r"comp_05_legendary_|part_unique_", leaf, re.I):
                continue
        m = _UNIQUE_COMP_RE.search(leaf)
        if m:
            token = str(m.group(1) or "").strip()
            low = token.lower()
            if low in _CLASSMOD_NAMED_TOKENS or (
                token and not _is_weak_unique_token(token)
            ):
                return _ingame_part_name(name, set_label) or _humanize_unique_token(token)
    for name in names:
        leaf = _leaf_part_name(name)
        full = str(name or "").strip().lower()
        if _UNIQUE_COMP_RE.search(leaf):
            continue
        if is_classmod and not full.startswith("classmod_"):
            if re.search(r"part_unique_|comp_05_legendary_|part_firmware_", leaf, re.I):
                continue
        if not allow_firmware and _FIRMWARE_UNIQUE_RE.search(leaf):
            continue
        token = _token_from_named_patterns(leaf, allow_firmware=allow_firmware)
        if token:
            return _ingame_part_name(name, set_label) or _humanize_unique_token(token)
    return ""


def _guess_rarity_from_part_names(names: list[str]) -> str:
    # Composition rarity is resolved before unique/body heuristics.
    for name in names:
        leaf = _leaf_part_name(name)
        for pattern, label in _COMP_RARITY_RE:
            if pattern.search(leaf):
                return label
        if _COMP05_NAMED_RE.search(leaf):
            return "Legendary"
    for name in names:
        leaf = _leaf_part_name(name)
        if re.search(r"(?:^|\.)part_unique_", leaf, re.I):
            return "Legendary"
    hay = " ".join(names).lower()
    if not hay:
        return ""
    for needle, label in _RARITY_PATTERNS:
        if needle in hay:
            return label
    return ""


def _guess_damage_type_from_part_names(names: list[str]) -> str:
    """Best-effort elemental tag from part names (not a full game decode)."""
    for name in names:
        leaf = _leaf_part_name(name)
        for pattern, label in _DAMAGE_TYPE_PATTERNS:
            if pattern.search(leaf):
                return label
    return ""


def _prioritize_classmod_part_names(names: list[str], *, limit: int = 96) -> list[str]:
    """Keep passive/skill parts when truncating heavy classmod part lists."""
    scored: list[tuple[int, str]] = []
    for raw in names:
        s = str(raw or "").strip()
        if not s:
            continue
        low = s.lower()
        leaf = _leaf_part_name(low)
        root = low[: low.rfind(".")] if "." in low else ""
        score = 5
        if re.search(r"passive_|skilltree|progressgraph|(?:^|\.)skill", leaf):
            score = 1
        elif re.search(r"(?:^|\.)(?:body_|leg_body_)", leaf):
            score = 0
        elif re.search(r"comp_05_|comp_06_pearl|pearl_", leaf):
            score = 0
        elif re.search(r"part_firmware_|firmware", leaf):
            score = 3
        elif re.search(r"part_unv_|part_sec_", leaf):
            score = 4
        elif re.search(r"part_stat_|stat_", leaf):
            score = 7
        elif root and re.search(r"_(?:ps|sg|sm|ar|sr|hw)$", root) and not root.startswith(
            "classmod"
        ):
            score = 9
        scored.append((score, s))
    scored.sort(key=lambda t: t[0])
    out: list[str] = []
    seen: set[str] = set()
    stat_kept = 0
    for score, s in scored:
        if score >= 9 and not re.search(r"comp_06_pearl|pearl_", s, re.I):
            continue
        if score >= 7:
            if stat_kept >= 12:
                continue
            stat_kept += 1
        key = s.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _own_part_names_from_human(human: str, type_id: int) -> list[str]:
    """Parts from the item's own set only (bare {part} and {own_set:part} refs)."""
    label_table = _type_id_index().get(int(type_id))
    if not label_table:
        return []
    names: list[str] = []
    for raw_set, raw_part in re.findall(r"\{\s*(\d+)(?:\s*:\s*(\d+))?\s*\}", human):
        if raw_part and int(raw_set) != int(type_id):
            continue
        part_name = label_table[1].get(str(int(raw_part or raw_set)), "")
        if part_name:
            names.append(str(part_name))
    return names


def _rooted_part_names_from_human(human: str, *, limit: int = 400) -> list[str]:
    """Every part as ``root.part`` in serial order, bags expanded, repeats kept.

    Naming needs the shared roots (``energy_shield.`` / ``grenade_gadget.``),
    passive repeats (class mod prefix points) and serial order (tie-breaks)."""
    idx = _type_id_index()
    m = re.match(r"\s*(\d+)\s*,", human)
    default_set = int(m.group(1)) if m else 0
    names: list[str] = []

    def _add(part_set: int, part_id: int) -> None:
        label_table = idx.get(part_set)
        if not label_table:
            return
        part_name = str(label_table[1].get(str(part_id), "") or "")
        if not part_name:
            return
        root = str(label_table[0] or "").strip()
        names.append(part_name if "." in part_name or not root else f"{root}.{part_name}")

    for tok in re.finditer(r"\{\s*(\d+)\s*(?::\s*(?:\[([^\]]*)\]|(\d+)))?\s*\}", human):
        if len(names) >= limit:
            break
        first, bag, single = tok.group(1), tok.group(2), tok.group(3)
        if bag is not None:
            for pid in re.findall(r"\d+", bag):
                _add(int(first), int(pid))
        elif single is not None:
            _add(int(first), int(single))
        else:
            _add(default_set, int(first))
    return names[:limit]


def _part_names_from_human(human: str, *, limit: int = 96) -> list[str]:
    idx = _type_id_index()
    names: list[str] = []
    m = re.match(r"\s*(\d+)\s*,", human)
    default_set = int(m.group(1)) if m else 0
    header_info = type_info_from_id(default_set) if default_set else {}
    header_is_classmod = str(header_info.get("type") or "").strip().casefold() == "classmod"
    header_set = str(header_info.get("set") or "").strip()

    def _append_part(part_set: int, part_id: int) -> None:
        nonlocal names
        # Classmod pearl override: keep ONLY pearl rarity markers from foreign sets.
        # Never import Firewerks / Eigenburst / shield uniques into the classmod card.
        if header_is_classmod and part_set != default_set:
            foreign = type_info_from_id(part_set)
            foreign_type = str(foreign.get("type") or "").strip()
            foreign_set = str(foreign.get("set") or "").strip().lower()
            if foreign_type.casefold() != "classmod" and not foreign_set.startswith(
                "classmod_"
            ):
                label_table = idx.get(part_set)
                if label_table:
                    part_name = label_table[1].get(str(part_id), "")
                    if part_name and re.search(r"comp_06_pearl|pearl_", str(part_name), re.I):
                        leaf = _leaf_part_name(str(part_name))
                        names.append(leaf or str(part_name))
                return
        label_table = idx.get(part_set)
        if not label_table:
            return
        part_name = label_table[1].get(str(part_id), "")
        if not part_name:
            return
        if header_is_classmod and header_set and "." not in str(part_name):
            root = str(label_table[0] or "")
            if root.lower().startswith("classmod_"):
                names.append(f"{root}.{part_name}")
                return
        names.append(str(part_name))

    # Flat refs first so legendary comps are not truncated by bag flood.
    refs = re.findall(r"\{\s*(\d+)(?:\s*:\s*(\d+))?\s*\}", human)
    for raw_set, raw_part in refs:
        part_set = int(raw_set) if raw_part else default_set
        part_id = int(raw_part or raw_set)
        _append_part(part_set, part_id)

    # Classmods only: expand shared ClassMod bags (234/247). Never expand every
    # bag on guns — that flooded the 96-part cap and wiped Damage / real names.
    if header_is_classmod:
        for raw_set, body in re.findall(r"\{\s*(\d+)\s*:\s*\[([^\]]*)\]\s*\}", human):
            part_set = int(raw_set)
            if part_set not in _CLASSMOD_SHARED_BAG_SETS and part_set != default_set:
                continue
            for tok in re.findall(r"\d+", body):
                _append_part(part_set, int(tok))
        return _prioritize_classmod_part_names(names, limit=limit)

    if len(names) <= max(1, int(limit)):
        return names
    scored: list[tuple[int, str]] = []
    for raw in names:
        s = str(raw or "").strip()
        if not s:
            continue
        leaf = _leaf_part_name(s).lower()
        score = 5
        if re.search(r"comp_05_legendary_|comp_06_pearl|part_unique_", leaf):
            score = 0
        elif re.search(r"part_barrel_.+_", leaf) and not re.search(
            r"part_barrel_\d+_[a-h]$", leaf
        ):
            score = 1
        elif re.search(r"part_firmware_", leaf):
            score = 6
        elif re.search(r"part_body_mag_|part_scope_|part_grip_|part_stock_", leaf):
            score = 7
        scored.append((score, s))
    scored.sort(key=lambda t: t[0])
    out: list[str] = []
    seen: set[str] = set()
    for _score, s in scored:
        key = s.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _fallback_display_name(
    manufacturer: str,
    item_type: str,
    character_class: str,
    set_label: str,
) -> str:
    if item_type == "Classmod":
        pieces = [p for p in (character_class, "Class Mod") if p]
        display = " ".join(pieces).strip()
        if display:
            return display
    pieces = [p for p in (manufacturer, item_type or character_class) if p]
    display = " ".join(pieces).strip()
    if display:
        return display
    return str(set_label or "").replace("_", " ").strip()


def meta_from_serial(serial: str) -> dict[str, Any]:
    """Decode manufacturer / type / category / rarity / lore name from an @U serial."""
    out: dict[str, Any] = {
        "type_id": "",
        "set": "",
        "manufacturer": "",
        "item_type": "",
        "type": "",
        "character_class": "",
        "category": "Other",
        "rarity": "",
        "damage_type": "",
        "display_name": "",
        "unique_name": "",
        "part_names": [],
        "dps": None,
        "value": None,
        "meta_ok": False,
    }
    text = str(serial or "").strip()
    if not text.startswith("@U"):
        return out
    try:
        from . import serial_converter

        human = serial_converter.serial_to_human(text)
    except Exception:
        return out
    m = re.match(r"\s*(\d+)\s*,", human)
    if not m:
        return out
    type_id = int(m.group(1))
    info = type_info_from_id(type_id)
    item_type = str(info.get("type") or "")
    manufacturer = str(info.get("manufacturer") or "")
    character_class = str(info.get("character_class") or "")
    category = category_for_type(item_type)
    part_names: list[str] = []
    rarity = ""
    unique_name = ""
    damage_type = ""
    name_parts: list[str] = []
    try:
        part_names = _part_names_from_human(human, limit=96)
        name_parts = _rooted_part_names_from_human(human)
        rarity = _guess_rarity_from_part_names(name_parts)
        if item_type.strip().casefold() != "classmod":
            unique_name = _unique_display_from_part_names(
                [
                    n
                    for n in _own_part_names_from_human(human, type_id)
                    if _UNIQUE_COMP_RE.search(_leaf_part_name(n))
                ],
                set_label=str(info.get("set") or ""),
                item_type=item_type,
            )
        if not unique_name:
            unique_name = _unique_display_from_part_names(
                name_parts if item_type.strip().casefold() == "classmod" else part_names,
                set_label=str(info.get("set") or ""),
                item_type=item_type,
            )
        damage_type = _guess_damage_type_from_part_names(name_parts)
    except Exception:
        part_names = []
        name_parts = []
        rarity = ""
        unique_name = ""
        damage_type = ""
    # Enhancements: bare firmware without rarity comps still deserves a rarity tag.
    if not rarity and any(
        re.search(r"(?:^|\.)part_firmware_", _leaf_part_name(n), re.I) for n in part_names
    ):
        rarity = "Legendary"
    fallback = _fallback_display_name(
        manufacturer, item_type, character_class, str(info.get("set") or "")
    )
    display = unique_name or fallback
    out.update(
        {
            "type_id": str(type_id),
            "set": str(info.get("set") or ""),
            "manufacturer": manufacturer,
            "item_type": item_type,
            "type": item_type,
            "character_class": character_class,
            "category": category,
            "rarity": rarity,
            "damage_type": damage_type,
            "display_name": display,
            "unique_name": unique_name,
            "part_names": part_names[:96],
            "name_parts": name_parts,
            "dps": None,
            "value": None,
            "meta_ok": True,
        }
    )
    return out


_WEAK_LIVE_NAME_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"cannot\s*reveal", re.I),
    re.compile(r"can'?t\s*reveal", re.I),
    re.compile(r"could\s*not\s*reveal", re.I),
    re.compile(r"^unknown(?:\s+item)?$", re.I),
    re.compile(r"^unidentified", re.I),
    re.compile(r"^none$", re.I),
    re.compile(r"^null$", re.I),
    re.compile(r"^n/?a$", re.I),
    re.compile(r"^item\s*#?\d*$", re.I),
    re.compile(r"^occupied\s+slot$", re.I),
)


def usable_display_name(text: str) -> str:
    """Reject live FText / placeholder names that beat a good GZO decode."""
    raw = str(text or "").strip()
    if not raw or len(raw) < 2:
        return ""
    if raw.startswith("@U") or raw.startswith("@u"):
        return ""
    if raw.startswith("{") or "InstanceId" in raw:
        return ""
    if raw.startswith("Default__") or raw.startswith("default__"):
        return ""
    if "/" in raw and ("Game" in raw or "Script" in raw or raw.startswith("/")):
        return ""
    if raw.startswith("FGameDataHandle") or "ObjectProperty" in raw:
        return ""
    for pattern in _WEAK_LIVE_NAME_RES:
        if pattern.search(raw):
            return ""
    return raw


def level_from_serial(serial: str) -> int | None:
    """Parse item level from an @U (human header field 4)."""
    text = str(serial or "").strip()
    if not text.startswith("@U"):
        return None
    try:
        from . import serial_converter

        human = str(serial_converter.serial_to_human(text) or "").strip()
    except Exception:
        return None
    try:
        m = re.match(r"\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*(\d+)", human)
        if m:
            return int(m.group(1))
    except Exception:
        return None
    return None


def title_bits_from_serial(serial: str) -> dict[str, Any]:
    """Name / rarity / type / level for Pack Bay and other offline @U lists."""
    meta = meta_from_serial(serial)
    level = level_from_serial(serial)
    pretty = usable_display_name(str(meta.get("display_name") or meta.get("unique_name") or ""))
    if not pretty:
        pretty = usable_display_name(
            " ".join(
                p
                for p in (
                    str(meta.get("manufacturer") or "").strip(),
                    str(meta.get("item_type") or "").strip(),
                )
                if p
            )
        )
    return {
        "display_name": pretty,
        "unique_name": str(meta.get("unique_name") or "").strip(),
        "rarity": str(meta.get("rarity") or "").strip(),
        "manufacturer": str(meta.get("manufacturer") or "").strip(),
        "item_type": str(meta.get("item_type") or "").strip(),
        "level": level,
        "meta_ok": bool(meta.get("meta_ok")),
        "set": str(meta.get("set") or "").strip(),
        "name_parts": list(meta.get("name_parts") or []),
    }


def _normalize_item_type_key(item_type: str) -> str:
    t = str(item_type or "").strip().lower()
    if not t:
        return ""
    if "class" in t:
        return "classmod"
    if "shield" in t:
        return "shield"
    if "enhancement" in t:
        return "enhancement"
    if "rep" in t:
        return "repkit"
    if "grenade" in t or "ordnance" in t or "gadget" in t:
        return "ordnance"
    if any(x in t for x in ("smg", "pistol", "shotgun", "sniper", "assault", "rifle", "heavy", "weapon")):
        return "weapon"
    return t


def _card_perk_kind(leaf: str, item_type: str) -> str:
    """Return card-row role for a part leaf, or '' if it should not appear on the card.

    In-game cards show legendary/unique perks, firmware, licensed lines, classmod
    skills/passives — not mundane body / scope / grip / stock / base barrel bits.
    """
    low = _leaf_part_name(leaf).lower()
    if not low:
        return ""
    # Always skip raw rarity comps / cosmetics.
    if re.search(
        r"(?:^|\.)(?:base_comp_|comp_0[1-4]_|comp_05_legendary$|comp_06_pearl|"
        r"skin_|decal_|material_|cosmetic_)",
        low,
    ):
        return ""
    kind = _normalize_item_type_key(item_type)

    # Shared high-signal carriers across gear.
    if re.search(r"(?:^|\.)part_unique_", low):
        return "unique"
    if re.search(r"(?:^|\.)part_firmware_|firmware", low):
        return "firmware"
    if re.search(r"licensed|barrel_licensed", low):
        return "licensed"
    if re.search(r"(?:^|\.)(?:base_)?comp_05_(?!legendary(?:_|$))", low) or re.search(
        r"comp_05_legendary_.+", low
    ):
        return "legendary"
    if re.search(r"(?:^|\.)(?:base_)?comp_06_pearl.+", low):
        return "pearl"
    if re.search(r"augment_unique|part_augment", low):
        return "augment"
    # Manufacturer legendary cores (Bounce Pass, etc.) — before mundane frame skip.
    if re.search(r"(?:^|\.)part_core_", low):
        return "legendary"

    if kind == "classmod":
        if re.search(r"(?:^|\.)part_firmware_|firmware", low):
            return "firmware"
        if re.search(
            r"universal|part_unv_|unv_|part_stat_unv|stat_mod_unv|"
            r"part_stat_(?:gun|weapon|player|char)",
            low,
        ):
            return "universal"
        if re.search(r"secondary|part_sec_|part_stat_sec", low):
            return "secondary"
        if re.search(r"passive_|skill|perk", low):
            return "skill"
        if re.search(r"part_stat", low):
            return "universal"
        return ""

    if re.search(r"pearl_stat|pearl_elem|stat_mod|part_stat", low):
        return "stat"

    if kind == "shield":
        if re.search(r"nova|spike|roid|turtle|amp|absorb|firmware|unique|legendary|payload|perk|core_", low):
            return "perk"
        return ""

    if kind in ("enhancement", "repkit", "ordnance"):
        if re.search(r"firmware|unique|legendary|passive_|part_stat|payload|augment|perk|core_", low):
            return "perk"
        return ""

    # Weapons: legendary perk pools, unique barrels, firmware, licensed, secondary effects.
    if re.search(r"legendary_perk|leg_perk|part_legendary", low):
        return "legendary"
    if re.search(r"part_unique_barrel|part_barrel_unique|barrel_.+unique|unique_barrel", low):
        return "unique"
    if re.search(r"(?:^|\.)part_secondary_|part_multi_|part_element", low):
        return "secondary"
    # Named underbarrel / payload legendary gadgets (bounce grenade, etc.).
    if re.search(
        r"(?:underbarrel|payload).+(?:unique|legendary|bounce|mirv|nuke|missile|grenade)",
        low,
    ) or re.search(r"(?:unique|legendary).+(?:underbarrel|payload)", low):
        return "legendary"
    # Mundane weapon frame — never show on the card.
    if re.search(
        r"(?:^|\.|_)(?:body|scope|sight|grip|stock|foregrip|underbarrel|"
        r"magazine|mag|barrel|receiver|rail)(?:_|$|\.)",
        low,
    ):
        return ""
    return ""


def _card_perk_label(leaf: str, kind: str) -> str:
    low = _leaf_part_name(leaf)
    if low.lower() == "part_secondary_ammo_sg":
        return "Daedalus Multi-Loader · Shotgun Ammo"
    # Prefer lore / unique tokens when present.
    token = _token_from_named_patterns(low)
    if token and not _is_weak_unique_token(token):
        return _ingame_part_name(leaf) or _humanize_unique_token(token)
    pretty = _title_from_slug(low)
    # Drop noisy prefixes from titles.
    pretty = re.sub(
        r"^(?:Part|Comp|Base Comp|Passive Points|Passive)\s+",
        "",
        pretty,
        flags=re.I,
    ).strip()
    if kind == "firmware" and pretty and not pretty.lower().startswith("firmware"):
        return f"Firmware · {pretty}"
    if kind == "licensed" and pretty and "licen" not in pretty.lower():
        return f"Licensed · {pretty}"
    return pretty


def card_fields_from_serial(serial: str) -> dict[str, Any]:
    """Offline Cohtml/CSS card model fields from @U.

    Only surfaces perk / skill / firmware / unique / licensed lines the way an
    in-game card would — not mundane body/scope/grip/stock/barrel frame parts.
    Does not invent absolute DPS (scales come from the EXE parts table).
    Classmod passives stack as ×1–×5; absolute red-text quotes are not in @U.
    """
    bits = title_bits_from_serial(serial)
    meta = meta_from_serial(serial)
    item_type = str(bits.get("item_type") or meta.get("item_type") or "").strip()
    type_key = _normalize_item_type_key(item_type)
    part_names = [str(p).strip() for p in (meta.get("part_names") or []) if str(p).strip()]
    stacked: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in part_names:
        leaf = _leaf_part_name(raw)
        kind = _card_perk_kind(leaf, item_type)
        if not kind:
            continue
        label = _card_perk_label(leaf, kind)
        if not label:
            continue
        key = f"{kind}:{label.casefold()}"
        if key in stacked:
            stacked[key]["count"] = min(5, int(stacked[key].get("count") or 1) + 1)
            continue
        stacked[key] = {
            "name": label,
            "effect": "",
            "code": leaf,
            "kind": kind,
            "count": 1,
        }
        order.append(key)
        # Classmods: keep collecting skills past the old 14-cap so heavy mods
        # still feed perk_rows / Nexus. Non-skills stop early.
        if type_key == "classmod":
            if len(order) >= 256:
                break
        elif len(order) >= 14:
            break
    perk_rows: list[dict[str, Any]] = []
    perk_lines: list[str] = []
    # Classmods: no practical perk cap — modded cards need every skill/part row.
    perk_cap = 256 if type_key == "classmod" else 12
    # Classmods: emit skills first so the card spill/list is perk-led.
    if type_key == "classmod":
        order = [k for k in order if k.startswith("skill:")] + [
            k for k in order if not k.startswith("skill:")
        ]
    for key in order:
        row = stacked[key]
        n = max(1, min(5, int(row.get("count") or 1)))
        name = str(row.get("name") or "").strip()
        kind = str(row.get("kind") or "")
        # Classmod skills: keep bare name; card UI shows icon + ×N.
        if type_key == "classmod" and kind == "skill" and n > 1:
            line = f"{name} ×{n}"
        elif n > 1:
            line = f"{name} ×{n}"
        else:
            line = name
        perk_rows.append(
            {
                "name": name,
                "effect": "",
                "code": str(row.get("code") or ""),
                "kind": kind,
                "count": n,
                "value": f"×{n}" if type_key == "classmod" and kind == "skill" else "",
            }
        )
        perk_lines.append(line)
        if len(perk_rows) >= perk_cap:
            break
    element = str(meta.get("damage_type") or "").strip()
    out = dict(bits)
    out.update(
        {
            # `parts` feeds Cohtml description/secondary — keep perk-only.
            "parts": list(perk_lines[:perk_cap]),
            "perk_rows": perk_rows[:perk_cap],
            "perk_lines": perk_lines[:perk_cap],
            "stats": [],
            "element": element,
            "damage_type": element,
            "part_names": part_names[:96],
            "set": str(meta.get("set") or bits.get("set") or ""),
            "type_id": str(meta.get("type_id") or bits.get("type_id") or ""),
            # Real red-text quotes aren't in @U; don't fake with the item name.
            "red_text": [],
        }
    )
    return out


def normalize_live_rarity(text: str) -> str:
    """Map live card rarity strings onto the same labels Electron / QM use."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    hay = raw.lower().replace("::", "_").replace(" ", "_")
    for needle, label in _RARITY_PATTERNS:
        if needle in hay:
            return label
    return raw


def apply_live_card_fields(entry: dict[str, Any], card: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay NHA item-info fields onto an inventory entry. GZO stays fallback.

    Never overwrite ``serial`` / ``@U`` identity. Card strings are display only.
    """
    if not isinstance(entry, dict) or not isinstance(card, dict):
        return entry
    serial = entry.get("serial")
    name = str(card.get("item_name") or card.get("display_name") or "").strip()
    rarity = normalize_live_rarity(str(card.get("rarity") or ""))
    manufacturer = str(card.get("manufacturer") or "").strip()
    item_type = str(card.get("item_type") or card.get("weapon_type") or "").strip()
    damage_type = str(card.get("damage_type") or card.get("bullet_type") or "").strip()
    part_names = card.get("part_names")
    price = card.get("price")
    level = card.get("level")
    if name:
        entry["display_name"] = name
        entry["unique_name"] = name
        entry["card_name"] = name
    if rarity:
        entry["rarity"] = rarity
    if manufacturer:
        entry["manufacturer"] = manufacturer
    if item_type:
        entry["item_type"] = item_type
        entry["type"] = item_type
        entry["category"] = category_for_type(item_type)
    if damage_type:
        entry["damage_type"] = damage_type
    if isinstance(part_names, list) and part_names:
        entry["part_names"] = [str(p) for p in part_names if str(p).strip()][:96]
    if price is not None:
        try:
            value = int(price)
        except (TypeError, ValueError):
            value = None
        if value is not None and value >= 0:
            entry["value"] = value
    if level is not None:
        try:
            live_level = int(level)
        except (TypeError, ValueError):
            live_level = -1
        if live_level >= 0 and int(entry.get("level") or -1) < 0:
            entry["level"] = live_level
    if name or rarity:
        entry["meta_source"] = "live_card"
        entry["meta_ok"] = True
        entry["card_ok"] = True
    if serial is not None:
        entry["serial"] = serial
    return entry


def enrich_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Mutate/return an inventory entry with decoded meta fields.

    Prefers a live item-info overlay (``_live_card`` / ``live_card``) when the
    backpack/world object exists. GZO manufacturer+type is fallback only.
    """
    if not isinstance(entry, dict):
        return entry
    serial = str(entry.get("serial") or "")
    meta = meta_from_serial(serial)
    entry["type_id"] = meta.get("type_id") or entry.get("type_id") or ""
    entry["set"] = meta.get("set") or ""
    entry["manufacturer"] = meta.get("manufacturer") or ""
    entry["item_type"] = meta.get("item_type") or ""
    entry["type"] = meta.get("type") or entry.get("item_type") or ""
    entry["character_class"] = meta.get("character_class") or ""
    entry["category"] = meta.get("category") or "Other"
    entry["rarity"] = meta.get("rarity") or ""
    entry["damage_type"] = meta.get("damage_type") or ""
    # DPS / vendor value are not encoded in @U / GZO parts — keep explicit nulls
    # unless a live card overlay supplies vendor price.
    entry["dps"] = meta.get("dps")
    entry["value"] = meta.get("value")
    unique = str(meta.get("unique_name") or "").strip()
    if unique:
        entry["unique_name"] = unique
    display = str(meta.get("display_name") or "").strip()
    if display:
        entry["display_name"] = display
    else:
        entry["display_name"] = str(entry.get("label") or "Item")
    entry["meta_ok"] = bool(meta.get("meta_ok"))
    entry["meta_source"] = "gzo_guess" if entry["meta_ok"] else "none"
    entry["card_ok"] = False
    try:
        live = entry.pop("_live_card", None)
        if not isinstance(live, dict):
            live = entry.get("live_card")
        apply_live_card_fields(entry, live if isinstance(live, dict) else None)
    except Exception:
        entry["card_ok"] = False
        entry.pop("_live_card", None)
    level = int(entry.get("level") or -1)
    base = str(entry.get("display_name") or entry.get("label") or "Item").strip() or "Item"
    entry["display_name"] = base
    if level >= 0:
        entry["summary"] = f"{base} L{level}"
    else:
        entry["summary"] = base
    return entry
