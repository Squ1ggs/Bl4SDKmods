"""Spawn tracking + world scans for mob spawner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import unrealsdk

MAX_DEPLOY_COUNT = 999
_BUDGET_WORLD_KEY = ""
_BUDGET_WANTED: bool | None = None


def disable_world_spawn_budget(enabled: bool = True) -> tuple[int, str]:
    """Toggle BL4's map-level AI spawn budget on loaded OakWorldSettings.

    BL4 queues otherwise-valid OakSpawner requests when the active population
    budget is full, which looks like a roughly 5/6-mob cap until an actor dies.
    This property is map-local and can be restored by the game, so callers
    should verify and reapply it before spawning.
    """
    global _BUDGET_WORLD_KEY, _BUDGET_WANTED
    wanted = bool(enabled)
    settings: list[Any] = []
    active: Any | None = None
    world_key = ""
    try:
        engine = unrealsdk.get_engine()
        world = engine.GameViewport.World
        world_key = str(world)
        active = getattr(world, "WorldSettings", None)
        if active is None:
            active = getattr(getattr(world, "PersistentLevel", None), "WorldSettings", None)
        if active is not None:
            settings.append(active)
    except Exception:
        pass

    # Always verify the live WorldSettings above. Only skip the broader UObject
    # scan after a successful pass for this map; caching the attempt when no
    # live settings were found left the normal ~20-actor budget enabled.
    cached_map = bool(world_key and world_key == _BUDGET_WORLD_KEY and wanted == _BUDGET_WANTED)
    if not cached_map:
        for class_name in ("OakWorldSettings", "GbxGameWorldSettings"):
            try:
                settings.extend(list(unrealsdk.find_all(class_name, False) or ()))
            except TypeError:
                try:
                    settings.extend(list(unrealsdk.find_all(class_name) or ()))
                except Exception:
                    pass
            except Exception:
                pass

    changed = 0
    found = 0
    verified = 0
    live_verified = False
    seen: set[str] = set()
    for obj in settings:
        key = str(obj)
        if obj is None or key in seen:
            continue
        seen.add(key)
        try:
            old = bool(getattr(obj, "bDisableSpawnBudget"))
        except Exception:
            continue
        found += 1
        if old == wanted:
            verified += 1
            if obj is active:
                live_verified = True
        else:
            try:
                setattr(obj, "bDisableSpawnBudget", wanted)
                changed += 1
            except Exception:
                continue
            try:
                if bool(getattr(obj, "bDisableSpawnBudget")) == wanted:
                    verified += 1
                    if obj is active:
                        live_verified = True
            except Exception:
                pass

    state = "disabled" if wanted else "enabled"
    if world_key and found > 0 and live_verified:
        _BUDGET_WORLD_KEY = world_key
        _BUDGET_WANTED = wanted
    elif world_key:
        # Do not cache a failed attempt; the live setting may appear later.
        _BUDGET_WORLD_KEY = ""
        _BUDGET_WANTED = None
    if not live_verified:
        return changed, (
            f"world spawn budget NOT {state} on live map "
            f"({found} loaded settings, {verified} verified, {changed} changed)"
        )
    return changed, (
        f"world spawn budget {state} "
        f"({found} loaded settings, {verified} verified, {changed} changed)"
    )


def is_abstract_actor_code(code: str) -> bool:
    """True for parent/shared character defs which cannot create a live mob."""
    raw = str(code or "").strip().lower()
    return raw.startswith("char_") and (
        raw.endswith("_shared")
        or raw in {
            "char_enemy",
            "char_armybandit",
            "char_armydahl",
            "char_armyorder",
        }
    )


# Concrete stand-ins for family/_SHARED catalog rows (army + common creatures).
_SHARED_CONCRETE_REMAP: dict[str, str] = {
    "char_armybandit_shared": "Char_GunToterAssault_Male",
    "char_armydahl_shared": "Char_DahlGruntSMG",
    "char_armyorder_shared": "Char_GruntAssault",
    "char_armybandit": "Char_GunToterAssault_Male",
    "char_armydahl": "Char_DahlGruntSMG",
    "char_armyorder": "Char_GruntAssault",
    "char_beast_shared": "Char_BeastBasic",
    "char_bat_shared": "Char_BatBasic",
    "char_cat_shared": "Char_CatAdult",
    "char_creep_shared": "Char_CreepBasic",
    "char_thresher_shared": "Char_ThresherBasic",
    "char_kraggon_shared": "Char_KraggonBasic",
    "char_pangolin_shared": "Char_PangolinBasic",
    "char_grunt_shared": "Char_GruntAssault",
    "char_guntoter_shared": "Char_GunToterAssault_Male",
    "char_psycho_shared": "Char_PsychoBasic",
    "char_brute_shared": "Char_BruteBasic",
    "char_soldier_shared": "Char_SoldierAR",
    "char_striker_shared": "Char_StrikerBasic",
    "char_drone_shared": "Char_DroneBasic",
    "char_meathead_shared": "Char_MeatheadBasic",
    "char_phalanx_shared": "Char_PhalanxBasic",
    "char_splice_shared": "Char_SpliceBasic",
    "char_dahlgrunt_shared": "Char_DahlGruntSMG",
    "char_banditturret_shared": "Char_BanditTurret_Chaingun",
}


def resolve_concrete_actor_code(code: str) -> str:
    """Map family/_SHARED rows to a spawnable concrete Char_* (army / creatures)."""
    raw = str(code or "").strip()
    if not raw:
        return raw
    hit = _SHARED_CONCRETE_REMAP.get(raw.lower())
    return hit if hit else raw


def abstract_actor_code_message(code: str) -> str:
    """Return an actionable error for a non-spawnable catalog family row."""
    raw = str(code or "").strip()
    remapped = resolve_concrete_actor_code(raw)
    if remapped.lower() != raw.lower():
        return f"{raw} is a shared/family definition — use {remapped}."
    examples = {
        "char_armybandit_shared": "Char_GunToterAssault_Male",
        "char_armydahl_shared": "Char_DahlGruntSMG",
        "char_armyorder_shared": "Char_GruntAssault",
    }
    example = examples.get(raw.lower())
    suffix = f" Try concrete member {example}." if example else " Pick a concrete child row without _SHARED."
    return f"{raw} is a shared/family definition, not a spawnable character.{suffix}"


def clamp_deploy_count(count: int | float | None, *, default: int = 1, max_cap: int | None = None) -> int:
    try:
        n = int(count if count is not None else default)
    except (TypeError, ValueError):
        n = int(default)
    cap = int(max_cap) if max_cap is not None else MAX_DEPLOY_COUNT
    cap = max(1, min(MAX_DEPLOY_COUNT, cap))
    return max(1, min(cap, n))


def is_boss_actor_code(code: str) -> bool:
    """True for raid/large bosses — wider distance/spacing, skip summon fallback."""
    raw = str(code or "").strip()
    if not raw:
        return False
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

        fn = getattr(ssp, "_is_large_boss_like", None)
        if callable(fn) and fn(raw):
            return True
    except Exception:
        pass
    low = raw.lower()
    return any(tok in low for tok in ("boss", "trueboss", "raid", "bigboss", "grassboss", "tubaboss"))


def prefer_combat_boss_code(code: str) -> str:
    """Prefer combat-ready ``…_TRUE`` defs when that twin actually exists.

    Never invent a missing ``_TRUE`` name — that breaks DLC bosses like Tuba
    (``Char_TubaBoss`` has no ``Char_TubaBoss_TRUE``, and the bad remap also
    skips Tuba package preload keyed to the base def).
    """
    raw = str(code or "").strip()
    if not raw or not is_boss_actor_code(raw):
        return raw
    low = raw.lower()
    if low.endswith("_true") or low.endswith("true") or "trueboss" in low or low.endswith("truetrue"):
        return raw
    # Explicit known twins
    if low == "char_bigboss":
        return "Char_BigBoss_TRUE"
    # No combat twin in content — keep base def (and its ACTOR_EXTRA_LOADS).
    if low in {"char_tubaboss"}:
        return raw

    candidates = (f"{raw}_TRUE", f"{raw}TRUE", f"{raw}_TrueBoss")
    known: set[str] = set()
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

        load_names = getattr(ssp, "_load_game_data_enemy_names", None)
        if callable(load_names):
            known = {str(n).strip().lower() for n in (load_names() or ()) if str(n).strip()}
    except Exception:
        known = set()

    if known:
        for cand in candidates:
            if cand.lower() in known:
                try:
                    from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

                    lower_map = getattr(ssp, "_GAME_DATA_ENEMY_LOWER", None) or {}
                    return str(lower_map.get(cand.lower()) or cand)
                except Exception:
                    return cand
        return raw

    # Without a known list, do not invent ``_TRUE`` — base def is safer.
    return raw


# DLC / mission-streamed bosses that fail thin-air spawn until oak_cache has a live def.
DLC_OAK_CACHE_ACTORS: frozenset[str] = frozenset({"char_tubaboss"})


def oak_cache_prerequisite_message(code: str) -> str | None:
    """Actionable hint when a boss def cannot resolve without a live-world cache."""
    key = str(code or "").strip().lower()
    if key == "char_tubaboss":
        return (
            "Char_TubaBoss did not spawn a new copy — the arena boss may already exist but be "
            "mission-gated (takedown adds must die first). Stand in the water arena, run "
            "oak_cache Char_TubaBoss on the live boss, then BMS: Attack me + Re-aggro. "
            "If nothing wakes, run through the takedown once or use Kill All on adds."
        )
    if key in DLC_OAK_CACHE_ACTORS:
        return (
            f"{code} needs a live actor-def cache before BMS can spawn it. "
            f"Encounter it in-game, then run: oak_cache {code}"
        )
    return None


def try_auto_cache_actor_def(code: str) -> tuple[bool, str]:
    """Best-effort oak_cache from a live world actor matching ``code``."""
    raw = str(code or "").strip()
    if not raw:
        return False, "empty actor code"
    try:
        from Squ1ggsBoostingTools.embedded_oak import engine as ssp  # noqa: PLC0415

        alias_key = getattr(ssp, "_alias_key", lambda s: s.lower())(raw)
        cache = getattr(ssp, "_ACTOR_DEF_CACHE", {}) or {}
        if alias_key in cache:
            return True, f"{raw} already in oak actor-def cache"
        matches = ssp._candidate_actor_def_sources(raw)
        if not matches:
            hint = oak_cache_prerequisite_message(raw)
            return False, hint or f"no live {raw} in world for oak_cache"
        if ssp._cache_actor_def(raw, matches[0]):
            return True, f"auto-cached {raw} from {matches[0]}"
        return False, f"found {raw} candidate but cache failed"
    except Exception as ex:
        return False, f"auto-cache failed: {ex}"


def find_characters_matching_code_near(
    near_loc: Any | None,
    expected_code: str,
    *,
    radius: float = 6000.0,
    exclude_keys: set[str] | None = None,
) -> list[Any]:
    """Late-bind scan: find live characters whose name matches the spawn family token."""
    needle = (expected_code or "").strip().lower()
    if not needle:
        return []
    family = needle.replace("char_", "").replace("_true", "").replace("true", "")
    radius_sq = float(radius) * float(radius)
    exclude = exclude_keys or set()
    out: list[Any] = []
    seen: set[str] = set()
    for cls_name in ("OakCharacter", "GbxAICharacter"):
        for obj in _find_all_class(cls_name):
            key = _actor_key(obj)
            if key in seen or key in exclude or _is_default_or_script(obj):
                continue
            hay = key.lower()
            if needle not in hay and family and family not in hay:
                continue
            if near_loc is not None:
                loc = _actor_location(obj)
                if loc is not None and _dist_sq(loc, near_loc) > radius_sq:
                    continue
            if not is_aggroable_character(obj):
                continue
            out.append(obj)
            seen.add(key)
    return out


def effective_spawn_spacing(
    base_spacing: float,
    count: int,
    *,
    actor_code: str = "",
    bossish: bool | None = None,
) -> float:
    """Widen row spacing when spawning multiple actors so they do not overlap."""
    n = max(1, int(count))
    base = max(25.0, float(base_spacing))
    if n <= 1:
        return base
    code = str(actor_code or "").lower()
    is_boss = bossish if bossish is not None else ("boss" in code or "raid" in code)
    floor = 300.0 if is_boss else 175.0
    scaled = base * (1.0 + 0.4 * (n - 1))
    return max(base, floor, scaled)


def _actor_key(obj: Any) -> str:
    return str(obj)


def _is_default_or_script(obj: Any) -> bool:
    low = str(obj).lower()
    return "default__" in low or "/script/" in low


def _actor_location(actor: Any) -> Any | None:
    for meth in ("K2_GetActorLocation", "GetActorLocation"):
        fn = getattr(actor, meth, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    return None


def _dist_sq(a: Any, b: Any) -> float:
    try:
        dx = float(getattr(a, "X", 0) or 0) - float(getattr(b, "X", 0) or 0)
        dy = float(getattr(a, "Y", 0) or 0) - float(getattr(b, "Y", 0) or 0)
        dz = float(getattr(a, "Z", 0) or 0) - float(getattr(b, "Z", 0) or 0)
        return dx * dx + dy * dy + dz * dz
    except Exception:
        return 1e30


def _find_all_class(class_name: str) -> list[Any]:
    try:
        return list(unrealsdk.find_all(class_name, False))
    except TypeError:
        try:
            return list(unrealsdk.find_all(class_name))
        except Exception:
            return []
    except Exception:
        return []


def snapshot_character_keys(*, exclude_keys: set[str] | None = None) -> set[str]:
    """Snapshot live Oak / AI character keys for world-delta spawn detection."""
    exclude = exclude_keys or set()
    seen: set[str] = set()
    for cls_name in ("OakCharacter", "GbxAICharacter"):
        for obj in _find_all_class(cls_name):
            if _is_default_or_script(obj):
                continue
            key = _actor_key(obj)
            if key in exclude:
                continue
            seen.add(key)
    return seen


def is_aggroable_character(actor: Any) -> bool:
    """True only for Oak/Gbx AI characters — never props, barrels, vendors, pickups."""
    if actor is None:
        return False
    try:
        key = _actor_key(actor).lower()
    except Exception:
        return False
    if _is_default_or_script(actor):
        return False
    # Hard reject world props that sometimes land in ssp._SPAWNED / tracker.
    reject_tokens = (
        "barrel",
        "vending",
        "pickup",
        "projectile",
        "vehicle",
        "spawner",
        "volume",
        "trigger",
        "camera",
        "hologram",
        "decal",
        "emitter",
        "logo",
        "bpp_pfa_",
        "interactiveobject",
    )
    if any(tok in key for tok in reject_tokens):
        return False
    try:
        cn = str(getattr(getattr(actor, "Class", None), "Name", "") or "").lower()
    except Exception:
        cn = ""
    if any(tok in cn for tok in reject_tokens):
        return False
    # Prefer class-name evidence; fall back to path tokens for Oak characters.
    if "character" in cn or "pawn" in cn:
        if "player" in cn:
            return False
        return True
    if "char_" in key or "/char_" in key:
        return True
    return False


def resolve_live_actor(key: str) -> Any | None:
    # Never fall back to generic Actor — that remaps dead character keys onto props.
    for cls_name in ("OakCharacter", "GbxAICharacter", "Pawn"):
        for obj in _find_all_class(cls_name):
            if _actor_key(obj) == key and is_aggroable_character(obj):
                return obj
    return None


def is_player_pawn(actor: Any, *, player_keys: set[str]) -> bool:
    key = _actor_key(actor)
    if key in player_keys:
        return True
    try:
        cn = str(getattr(getattr(actor, "Class", None), "Name", "") or "").lower()
        if "player" in cn:
            return True
    except Exception:
        pass
    return False


def find_new_characters_near(
    before: set[str],
    near_loc: Any | None,
    *,
    radius: float = 6000.0,
    exclude_keys: set[str] | None = None,
    expected_code: str = "",
) -> list[Any]:
    """Return characters that appeared after spawn and are near the reference location."""
    radius_sq = float(radius) * float(radius)
    exclude = exclude_keys or set()
    needle = (expected_code or "").strip().lower()
    out: list[Any] = []
    seen: set[str] = set()

    for cls_name in ("OakCharacter", "GbxAICharacter"):
        for obj in _find_all_class(cls_name):
            key = _actor_key(obj)
            if key in before or key in seen or key in exclude:
                continue
            if _is_default_or_script(obj):
                continue
            if near_loc is not None:
                loc = _actor_location(obj)
                if loc is not None and _dist_sq(loc, near_loc) > radius_sq:
                    continue
            if needle:
                hay = key.lower()
                family = needle.replace("char_", "").replace("_true", "")
                if needle not in hay and family not in hay:
                    # Do NOT track unrelated nearby characters — that polluted aggro
                    # and led to ApplyDamage on wrong actors.
                    continue
            if not is_aggroable_character(obj):
                continue
            out.append(obj)
            seen.add(key)
    return out


def player_pawn_keys() -> set[str]:
    keys: set[str] = set()
    try:
        from ..item_spawn.spawn_pc import resolve_spawn_pc

        pc = resolve_spawn_pc()
        pawn = getattr(pc, "Pawn", None) if pc is not None else None
        if pawn is not None:
            keys.add(_actor_key(pawn))
    except Exception:
        pass
    for cls_name in ("OakPlayerCharacter", "OakCharacter"):
        for obj in _find_all_class(cls_name):
            if _is_default_or_script(obj):
                continue
            try:
                cn = str(getattr(getattr(obj, "Class", None), "Name", "") or "").lower()
                if "player" in cn:
                    keys.add(_actor_key(obj))
            except Exception:
                pass
    return keys


def resolve_aggro_target(mode: str, *, party_index: int = 2) -> tuple[Any | None, str]:
    """Resolve pawn target for attack_me / attack_party modes."""
    mode = (mode or "attack_me").strip().lower()

    def _pawn_from_pc(pc: Any | None) -> Any | None:
        if pc is None:
            return None
        pawn = getattr(pc, "Pawn", None)
        if pawn is not None:
            return pawn
        get_pawn = getattr(pc, "GetPawn", None)
        try:
            return get_pawn() if callable(get_pawn) else None
        except Exception:
            return None

    if mode in ("attack_party", "party"):
        try:
            from Squ1ggsBoostingTools.dev_tools import _pc_for_party_index  # noqa: PLC0415

            pc, err = _pc_for_party_index(max(0, int(party_index)))
            if pc is not None:
                pawn = _pawn_from_pc(pc)
                if pawn is not None:
                    return pawn, err or f"party[{party_index}]"
        except Exception:
            pass
        return None, f"party index {party_index} not found"

    try:
        from ..item_spawn.spawn_pc import resolve_spawn_pc

        pc = resolve_spawn_pc()
    except Exception:
        pc = None
    pawn = _pawn_from_pc(pc) if pc is not None else None
    if pawn is None:
        return None, "no local pawn"
    return pawn, "local player"


@dataclass(slots=True)
class TrackedMob:
    key: str
    code: str = ""
    label: str = ""


@dataclass
class MobTracker:
    mobs: list[TrackedMob] = field(default_factory=list)

    def live_mobs_with_codes(self) -> list[tuple[Any, str]]:
        out: list[tuple[Any, str]] = []
        for item in self.mobs:
            actor = resolve_live_actor(item.key)
            if actor is not None:
                out.append((actor, item.code))
        return out

    def mob_code_map(self) -> dict[Any, str]:
        return {actor: code for actor, code in self.live_mobs_with_codes()}

    def add_actor(self, actor: Any, *, code: str = "") -> None:
        if not is_aggroable_character(actor):
            return
        key = _actor_key(actor)
        if any(m.key == key for m in self.mobs):
            return
        label = ""
        try:
            label = str(getattr(actor, "Name", "") or "")
        except Exception:
            pass
        self.mobs.append(TrackedMob(key=key, code=code, label=label))

    def clear_dead(self) -> int:
        before = len(self.mobs)
        kept: list[TrackedMob] = []
        for m in self.mobs:
            actor = resolve_live_actor(m.key)
            if actor is None:
                continue
            if not is_aggroable_character(actor):
                continue
            kept.append(m)
        self.mobs = kept
        return before - len(self.mobs)

    def destroy_all(self) -> tuple[int, int]:
        destroyed = 0
        failed = 0
        for item in list(self.mobs):
            actor = resolve_live_actor(item.key)
            if actor is None:
                continue
            fn = getattr(actor, "K2_DestroyActor", None)
            if callable(fn):
                try:
                    fn()
                    destroyed += 1
                except Exception:
                    failed += 1
            else:
                failed += 1
        self.mobs.clear()
        return destroyed, failed

