"""Deterministic curated gear loadouts resolved from SQBT's bundled item catalog.

The definitions deliberately contain item names, not copied serials.  Every row
is resolved against the same catalog used by the Codes and Item Builder tabs so
the delivered item, card preview, and saved personal build share one identity.
"""
from __future__ import annotations

from typing import Any, Iterable


BUILD_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "vex_kinetic_incarnate",
        "name": "Vex · Kinetic Incarnate",
        "character": "Vex",
        "playstyle": "Kinetic crits, bleed and lifesteal",
        "notes": "A survivable Incarnate starter package with kinetic bossing and mobbing options.",
        "skills": (
            "Incarnate · Leeching Attunement 5/5 · Bloodletter 5/5 · Material Components 5/5 · "
            "Essence Leech · Heartpiercer · Blood Is Power 3/5 · Grave Sustenance"
        ),
        "featured_home": True,
        "sources": (
            {
                "label": "Mobalytics · Kinetic Witch",
                "url": "https://mobalytics.gg/borderlands-4/builds/vex-kinetic-witch-incarnate",
            },
            {
                "label": "Game8 · endgame tier list",
                "url": "https://game8.co/games/Borderlands-4/archives/548535",
            },
        ),
        "items": (
            "Hot Slugger",
            "Bod",
            "Seventh Sense",
            "Triple Bypass",
            "Teen Witch",
            "Undead Eye",
        ),
    },
    {
        "id": "vex_dead_ringer",
        "name": "Vex · Dead Ringer Minions",
        "character": "Vex",
        "playstyle": "Reaper/Spectre summons, lifesteal and cooldown",
        "notes": "Teen Witch and Super Soldier keep the summon loop safe while Slippy supplies melee-scaled burst.",
        "skills": "Dead Ringer · Reaper/Spectre summons · summon duration · kill-skill cooldown · lifesteal",
        "sources": (
            {
                "label": "GameRant · Dead Ringer Reaper",
                "url": "https://gamerant.com/borderlands-4-bl4-best-vex-siren-reaper-build-dead-ringer/",
            },
        ),
        "items": (
            "Hot Slugger",
            "Hellfire",
            "Slippy",
            "Triple Bypass",
            "Super Soldier",
            "Teen Witch",
        ),
    },
    {
        "id": "rafa_ricochet",
        "name": "Rafa · Ricochet",
        "character": "Rafa",
        "playstyle": "Peacebreaker, ricochets and sticky boss damage",
        "notes": "Hot Slugger handles packs; Bod and Kaoson cover sticky single-target damage.",
        "skills": (
            "Peacebreaker Cannons · Juerga 5/5 · Inspirado 3/3 · Vitriol 5/5 · "
            "Temerario 5/5 · Soltado · Resiliencia"
        ),
        "featured_home": True,
        "sources": (
            {
                "label": "Mobalytics · Ricochet Rafa",
                "url": "https://mobalytics.gg/borderlands-4/profile/nicktew/builds/ricochet-rafa-endgame",
            },
        ),
        "items": (
            "Hot Slugger",
            "Bod",
            "Kaoson",
            "Dancer",
            "Firewerks",
            "Shiny War Paint",
            "Blind Box",
        ),
    },
    {
        "id": "rafa_peacebreaker",
        "name": "Rafa · Peacebreaker Beam Team",
        "character": "Rafa",
        "playstyle": "Long-duration cannons and sustained gun damage",
        "notes": "A practical cannon package with Swarm support, cooldown recovery and high-value gun options.",
        "skills": "Peacebreaker Cannons · Instinto · Juerga · Inspirado · Vitriol · Temerario · Soltado",
        "sources": (
            {
                "label": "GameRant · Peacebreaker Beam Team",
                "url": "https://gamerant.com/best-rafa-build-peacebreaker-cannons-bl4-borderlands-4/",
            },
        ),
        "items": (
            "Hot Slugger",
            "Bod",
            "Swarm",
            "Triple Bypass",
            "Super Soldier",
            "Dancer",
        ),
    },
    {
        "id": "rafa_arc_knives",
        "name": "Rafa · Arc-Knives",
        "character": "Rafa",
        "playstyle": "Fast melee marks, Overdrive and close-range burst",
        "notes": "SQBT practical variant: movement, cooldown and survivability gear around Arc-Knives.",
        "skills": "Arc-Knives · Overdrive · melee marks · movement speed · action-skill cooldown",
        "sources": (
            {
                "label": "Lootlemon · Rafa skill tree",
                "url": "https://www.lootlemon.com/class/rafa",
            },
        ),
        "items": (
            "Sho Kunai",
            "Hot Slugger",
            "Shiny War Paint",
            "Super Soldier",
            "Dancer",
            "Bismuth-Tipped Dagger",
        ),
    },
    {
        "id": "harlowe_chroma",
        "name": "Harlowe · CHROMA Radiation",
        "character": "Harlowe",
        "playstyle": "Fast hits during CHROMA radiation windows",
        "notes": "Fast weapons, cooldown support and a mobbing shield for CHROMA burst windows.",
        "skills": (
            "CHROMA Accelerator · Neutron Capture · Chain Reactor · Decoherence · "
            "Confirmative Reality · Neutron Decay"
        ),
        "sources": (
            {
                "label": "Mobalytics · CHROMA endgame",
                "url": "https://mobalytics.gg/borderlands-4/builds/radiation-chroma-harlowe-endgame-nicktew",
            },
            {
                "label": "Lootlemon · Harlowe skill tree",
                "url": "https://www.lootlemon.com/class/harlowe",
            },
        ),
        "items": (
            "Katagawa's Revenge",
            "Aegon's Dream",
            "Lucian's Flank",
            "Skeptic",
            "Scientist",
            "Firewerks",
            "Shiny War Paint",
        ),
    },
    {
        "id": "harlowe_cryo_stasis",
        "name": "Harlowe · Cryo Stasis",
        "character": "Harlowe",
        "playstyle": "Zero-Point control, Cryo/Radiation and rapid cooldown",
        "notes": "Bio-Robot supplies the status loop; Skeptic is included as a strong cooldown alternative.",
        "skills": (
            "Zero-Point · Inertia · Cold Plunge · Creative Overflow · Neutron Decay · "
            "Parallel Circuit · Keep Ice On That"
        ),
        "sources": (
            {
                "label": "Mobalytics · Cryohawk",
                "url": "https://mobalytics.gg/borderlands-4/builds/cryohawk-zero-point-harlowe",
            },
        ),
        "items": (
            "Ohm I got",
            "Aegon's Dream",
            "Plasma Coil",
            "Jelly",
            "Triple Bypass",
            "Super Soldier",
            "Bio-Robot",
            "Skeptic",
        ),
    },
    {
        "id": "amon_onslaughter",
        "name": "Amon · Onslaughter",
        "character": "Amon",
        "playstyle": "Close-range fire and melee pressure",
        "notes": "High-capacity protection and fire-oriented class mods with close-range weapons.",
        "skills": "Onslaughter · Calamity · Thermal Diffusion · Raging Inferno · Reactive Armor",
        "sources": (
            {
                "label": "Mobalytics · Onslaughter guide",
                "url": "https://mobalytics.gg/borderlands-4/builds/fisticuffs-amon-ancientrune",
            },
        ),
        "items": (
            "Hot Slugger",
            "Kaoson",
            "Heavyweight",
            "Firewerks",
            "Furnace",
            "Forge Master",
            "Shiny War Paint",
        ),
    },
    {
        "id": "amon_freeze_crucible",
        "name": "Amon · Freeze Crucible",
        "character": "Amon",
        "playstyle": "Frost Axe control into point-blank Jakobs crits",
        "notes": "SQBT practical variant: freeze priority targets, then finish with a high-damage shotgun.",
        "skills": (
            "Crucible · Twin Tempers · Raging Inferno · Reactive Armor · Executioner · "
            "Gathering Storm · Conflangarang"
        ),
        "sources": (
            {
                "label": "Mobalytics · Stormbringer",
                "url": "https://mobalytics.gg/borderlands-4/builds/hammer-time-amon",
            },
        ),
        "items": (
            "Hot Slugger",
            "Hellwalker",
            "Sho Kunai",
            "Triple Bypass",
            "Super Soldier",
            "Forge Master",
        ),
    },
    {
        "id": "c4sh_gloam",
        "name": "C4SH · Gloam Cleromancy",
        "character": "C4SH",
        "playstyle": "High-rate elemental fire, Fortune and no-reload loops",
        "notes": "Windrider is rolled for the core Gloam, Dusty Trail and Dealer's Bluff skill package.",
        "skills": (
            "Cleromancy · From Gloam Till Glow 5/5 · Dusty Trail · Dealer's Bluff · "
            "War Wagon · Nothing Beats Lead"
        ),
        "sources": (
            {
                "label": "Mobalytics · No-Reload C4SH",
                "url": "https://mobalytics.gg/borderlands-4/builds/no-reload-gun-c4sh",
            },
        ),
        "items": (
            "Windrider",
            "Plasma Coil",
            "Lucian's Flank",
            "Shiny War Paint",
            "Sho Kunai",
            "Watts 4 Dinner",
        ),
    },
    {
        "id": "loveless_vpn_sniper",
        "name": "Loveless · VPN Sniper",
        "character": "Loveless",
        "playstyle": "Slow, high-damage sniper burst",
        "notes": (
            "Truck carries the exact Torgue Impact and Daedalus Shotgun-ammo parts; Solar Temper covers bossing."
        ),
        "skills": (
            "Visual Paradox Nexus · Stack Overflow · accelerat.exe · Methodical · Disdain · "
            "Refactored Damage Formula · Killing Machine"
        ),
        "sources": (
            {
                "label": "Mobalytics · Loveshot.exe",
                "url": "https://mobalytics.gg/borderlands-4/builds/loveshot-sniper-loveless-ratore",
            },
        ),
        "items": (
            "Truck",
            "Solar Temper",
            "Triple Bypass",
            "Montage Maker",
            "Guardian Angel",
            "Watts 4 Dinner",
        ),
    },
)

# Exact serials whose visible and hidden parts were decoded before inclusion.
# These replace generic catalog rolls for the build-defining item while normal
# named items continue to resolve from the bundled catalog.
OPTIMIZED_ITEM_OVERRIDES: dict[str, dict[str, Any]] = {
    "Hot Slugger": {
        "serial": "@Ugd_t@FnkbUWIs??RH1&NdZON-VxdwZ9>(5>;d/aL)6?Vm_gW6a-/p`eop$HHQ+EA)F3SM",
        "type": "Shotgun",
        "roll": "Fixed Hot Slugger core · Jakobs grip/foregrip",
    },
    "Triple Bypass": {
        "serial": "@Ugr$xKm/*xI!pKXYM-}RPwL#}=4I0$>LW9m%0R",
        "type": "Repkit",
        "roll": "Huge payload · Amp next shot · Deadeye firmware",
    },
    "Undead Eye": {
        "serial": "@Ug!pHG35E/MOpgs}hssnhgW7FSxen^~LFG=}GN{^x1J!OGsCH=q",
        "type": "Class Mod",
        "roll": "Blood Shot 5/5 · sniper damage · max health · Deadeye",
    },
    "Teen Witch": {
        "serial": "@Ug!pHG35E/MjO+(Ghx*jtR3C#%VNfRxs>DH!Jg5)~Rl5b%ZbP;E2><",
        "type": "Class Mod",
        "roll": "Grave Sustenance 5/5 · Conjunction 2/2 · gun crit chance · lifesteal",
    },
    "Dancer": {
        "serial": "@Uge8Cmm/*xI!pMH0I;cvuFsPLV^}?W19Ms8!Dxpx}P_-Kcs@;cbmlgm",
        "type": "Class Mod",
        "roll": "Temerario 5/5 · Soltado 1/1 · The Thrill 1/5 · action-skill damage/cooldown",
    },
    "Skeptic": {
        "serial": "@Ugr$K7m/*xI!pMH0HmFYBL4`xLMde4`FsLyGHOHXh8dUB6f@(JpRJ*+Z",
        "type": "Class Mod",
        "roll": "Bright Future 3/5 · Indiscrete Math 2/5 · stasis damage · max health",
    },
    "Scientist": {
        "serial": "@Ugr$K7m/*xI!pMH0HK<SBLG42ILWM-_M4d;?N&QRJ?hmMTbwIUy4FC",
        "type": "Class Mod",
        "roll": "Action at a Distance 5/5 · elemental damage · splash damage · Skillcraft",
    },
    "Bio-Robot": {
        "serial": "@Ugr$K7m/*xI!pMH0I;cwBLFF;1y9QO~pyr`kqH?2Br)n1(RJ(GZ+Pww<",
        "type": "Class Mod",
        "roll": "Confirmative Reality 3/3 · Sustenance 2/5 · gun damage · Skillcraft",
    },
    "Furnace": {
        "serial": "@Ug#2fK35E/MjO+)RgR0c;R4;?tZBV%m>h?j+F{ro(RlC)o+GVJAVF3",
        "type": "Class Mod",
        "roll": "Raging Inferno 5/5 · fire damage · skill crit chance",
    },
    "Shiny War Paint": {
        "serial": "@Ugr$N8m/*xI!pMH0MLp_#vq9%84QkZ+(t^%c0R",
        "type": "Repkit",
        "roll": "Large payload · all damage · Deadeye firmware",
    },
    "Windrider": {
        "serial": "@UgeA%bm/*xI!pMH0c&Kxz6b5zDph_In$b$-@P%R9qhe6fu45)VHK(%`f00",
        "type": "Class Mod",
        "roll": "From Gloam Till Glow 5/5 · Dusty Trail 1/1 · Dealer's Bluff 1/1 · gun/all damage",
    },
    "Montage Maker": {
        "serial": "@UgeA!am/!d+!pMH0cBn-CFsK;@71N+z98}ALTA@(+Qnd>Qs$D!#?bZSS",
        "type": "Class Mod",
        "roll": "Methodical 5/5 · Refactored Damage Formula 1/1 · sniper/melee damage",
    },
    "Truck": {
        "serial": "@Ugy3L+35E/MOza2Bi7M2g5_J<b4^<C!5A~@ss5+=Vs6VJ$sBoy32m",
        "type": "Sniper",
        "roll": "Torgue Impact Gyrojets · Daedalus Multi-Loader Shotgun Ammo",
    },
}


def _source_index(source_rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for raw in source_rows:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("title") or raw.get("name") or "").strip()
        serial = str(raw.get("serial") or "").strip()
        if not name or not serial.startswith("@U") or any(ch.isspace() for ch in serial):
            continue
        key = name.casefold()
        if key in index and str(index[key].get("serial") or "") != serial:
            duplicates.add(key)
            continue
        index[key] = dict(raw)
    # An ambiguous name must never silently pick one of several serials.
    for key in duplicates:
        index.pop(key, None)
    return index


def catalog(
    source_rows: Iterable[dict[str, Any]],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve definitions to exact catalog serials and return grouped UI rows."""
    payload = payload or {}
    search = str(payload.get("search") or "").strip().casefold()
    wanted_group = str(payload.get("group") or "All").strip() or "All"
    wanted_character = str(payload.get("character") or "All").strip() or "All"
    featured_only = str(payload.get("featured_only") or "").strip().casefold() in (
        "1",
        "true",
        "yes",
        "on",
    )
    try:
        limit = max(1, min(int(payload.get("limit") or 500), 10_000))
    except Exception:
        limit = 500
    source = _source_index(source_rows)
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    group_meta: dict[str, dict[str, str]] = {}
    groups: list[str] = []

    for build in BUILD_DEFINITIONS:
        if featured_only and not bool(build.get("featured_home")):
            continue
        group = str(build["name"])
        character = str(build["character"])
        groups.append(group)
        group_meta[group] = {
            "id": str(build["id"]),
            "character": character,
            "playstyle": str(build["playstyle"]),
            "notes": str(build["notes"]),
            "skills": str(build.get("skills") or ""),
            "featured_home": bool(build.get("featured_home")),
            "sources": [
                {
                    "label": str(source.get("label") or "Build reference"),
                    "url": str(source.get("url") or ""),
                }
                for source in build.get("sources") or ()
                if isinstance(source, dict) and str(source.get("url") or "").startswith("https://")
            ],
            "provenance": (
                "Public endgame recommendations plus clearly labelled SQBT practical variants; "
                "exact items resolved by SQBT."
            ),
        }
        if wanted_group not in ("", "All") and wanted_group != group:
            continue
        if wanted_character not in ("", "All") and wanted_character != character:
            continue
        for position, item_name in enumerate(build["items"], start=1):
            hit = source.get(str(item_name).casefold())
            optimized = OPTIMIZED_ITEM_OVERRIDES.get(str(item_name))
            if optimized is not None:
                hit = {**(hit or {}), **optimized}
            if hit is None:
                missing.append(
                    {
                        "build": group,
                        "item": str(item_name),
                        "reason": "No single exact bundled catalog match.",
                    }
                )
                continue
            row = dict(hit)
            row.update(
                {
                    "id": f"{build['id']}:{position}:{item_name}",
                    "title": str(item_name),
                    "name": str(item_name),
                    "display_name": str(item_name),
                    "group": group,
                    "build_id": str(build["id"]),
                    "character": character,
                    "playstyle": str(build["playstyle"]),
                    "position": position,
                    "roll": str((optimized or {}).get("roll") or ""),
                    "verified_roll": bool(optimized),
                    "provenance": (
                        "decoded_optimized_serial"
                        if optimized
                        else "bundled_catalog_exact_name"
                    ),
                }
            )
            haystack = " ".join(
                str(row.get(key) or "")
                for key in ("title", "group", "character", "playstyle", "category", "type")
            ).casefold()
            if search and search not in haystack:
                continue
            rows.append(row)

    filtered_groups = [
        group
        for group in groups
        if wanted_group in ("", "All") or wanted_group == group
        if wanted_character in ("", "All")
        or group_meta.get(group, {}).get("character") == wanted_character
    ]
    group_counts = {
        group: sum(1 for row in rows if str(row.get("group") or "") == group)
        for group in filtered_groups
    }
    total = len(rows)
    return {
        "rows": rows[:limit],
        "total": total,
        "groups": ["All", *filtered_groups],
        "group_counts": group_counts,
        "group_meta": {group: group_meta[group] for group in filtered_groups},
        "characters": [
            "All",
            *sorted(
                {
                    str(row["character"])
                    for row in BUILD_DEFINITIONS
                    if not featured_only or bool(row.get("featured_home"))
                }
            ),
        ],
        "missing": missing,
    }


def validate_definitions(source_rows: Iterable[dict[str, Any]]) -> list[str]:
    """Return deterministic catalog-definition errors for build/smoke gates."""
    data = catalog(source_rows, {"limit": 10_000})
    errors: list[str] = []
    for row in data.get("missing") or []:
        errors.append(f"{row.get('build')}: {row.get('item')} — {row.get('reason')}")
    seen_ids: set[str] = set()
    for row in data.get("rows") or []:
        row_id = str(row.get("id") or "")
        serial = str(row.get("serial") or "")
        if not row_id or row_id in seen_ids:
            errors.append(f"Duplicate or empty curated row id: {row_id!r}")
        seen_ids.add(row_id)
        if not serial.startswith("@U") or any(ch.isspace() for ch in serial):
            errors.append(f"{row_id}: invalid serial")
    return errors
