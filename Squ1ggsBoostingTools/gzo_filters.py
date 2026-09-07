"""Canonical GZO item-type / category labels for catalog + in-game filters."""

from __future__ import annotations

import re

TYPE_ALIASES = {
    "shield": "Shield",
    "classmod": "Classmod",
    "class mod": "Classmod",
    "class_mod": "Classmod",
    "weapon": "Weapon",
    "grenade": "Grenade",
    "gadget": "Gadget",
    "repkit": "Repkit",
    "repair kit": "Repkit",
    "repair_kit": "Repkit",
    "enhancement": "Enhancement",
    "pistol": "Pistol",
    "shotgun": "Shotgun",
    "smg": "SMG",
    "sniper": "Sniper",
    "assault rifle": "Assault Rifle",
    "assault_rifle": "Assault Rifle",
    "assault riffle": "Assault Rifle",
    "assault_riffle": "Assault Rifle",
    "heavy": "Heavy Weapon",
    "heavy weapon": "Heavy Weapon",
    "hw": "Heavy Weapon",
}

TYPE_ORDER = (
    "Pistol",
    "SMG",
    "Shotgun",
    "Assault Rifle",
    "Sniper",
    "Heavy Weapon",
    "Weapon",
    "Shield",
    "Gadget",
    "Grenade",
    "Repkit",
    "Enhancement",
    "Classmod",
)

CATEGORY_ORDER = (
    "Weapons",
    "Shields",
    "Ordnance",
    "Class Mods",
    "Enhancements",
    "Repkits",
    "Other",
)

TYPE_TO_CATEGORY = {
    "Pistol": "Weapons",
    "SMG": "Weapons",
    "Shotgun": "Weapons",
    "Assault Rifle": "Weapons",
    "Sniper": "Weapons",
    "Heavy Weapon": "Weapons",
    "Weapon": "Weapons",
    "Shield": "Shields",
    "Gadget": "Ordnance",
    "Grenade": "Ordnance",
    "Classmod": "Class Mods",
    "Enhancement": "Enhancements",
    "Repkit": "Repkits",
}


def _norm_key(text: str) -> str:
    text = str(text or "").strip().lower()
    text = text.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text)


def normalize_type(raw: str) -> str:
    key = _norm_key(raw)
    if not key:
        return ""
    if key in TYPE_ALIASES:
        return TYPE_ALIASES[key]
    for alias, label in TYPE_ALIASES.items():
        if alias in key:
            return label
    return str(raw or "").strip()


def item_category(item_type: str) -> str:
    label = normalize_type(item_type)
    if not label:
        return "Other"
    return TYPE_TO_CATEGORY.get(label, "Other")


def ordered_labels(values: list[str], order: tuple[str, ...]) -> list[str]:
    seen = {str(v).strip() for v in values if str(v).strip()}
    return [x for x in order if x in seen] + sorted(seen.difference(order), key=str.lower)


def catalog_type_options() -> list[str]:
    return ["All", *TYPE_ORDER]


def catalog_category_options() -> list[str]:
    return ["All", *CATEGORY_ORDER]
