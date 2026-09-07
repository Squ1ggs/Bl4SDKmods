"""Best-effort aggro / target forcing for spawned Oak / Gbx AI characters."""

from __future__ import annotations

import logging
from typing import Any, Iterable

_log = logging.getLogger("bl4_mob_spawner.aggro")


def _sdk_log(message: str) -> None:
    """Write to unrealsdk.log so ULM dumps capture aggro steps."""
    try:
        from unrealsdk import logging as ue_log  # noqa: PLC0415

        ue_log.info(f"[MobSpawner] {message}")
    except Exception:
        _log.info("%s", message)

AGGRO_METHOD_HINTS = (
    "setfocus",
    "settarget",
    "setenemy",
    "attacktarget",
    "addaggro",
    "addthreat",
    "forcetarget",
    "engage",
    "startcombat",
    "entercombat",
    "registerthreat",
    "notifythreat",
    "setaggro",
    "acquiretarget",
    "movetoactor",
    "attackactor",
    "setattacktarget",
    "setcurrenttarget",
    "setaitarget",
    "forceaggro",
    "setaggrotarget",
    "setfocusactor",
    "setenemytarget",
)

TEAM_METHOD_HINTS = (
    "teamattitude",
    "setteam",
    "attitude",
    "setattitudeto",
    "addteam",
    "setgroup",
    "hostile",
)

WAKE_METHOD_HINTS = (
    "spawndefaultcontroller",
    "possess",
    "restartlogic",
    "runbehaviortree",
    "activateai",
)

SPAWN_TRICK_METHOD_HINTS = (
    "spawntrick",
    "completetrick",
    "finishtrick",
    "stoptrick",
    "onrep_waitingforspawntrick",
)

FACTION_METHOD_HINTS = (
    "characterarmy",
    "characterclan",
    "characterenemytype",
    "groupteamhandle",
    "teamhandle",
)

TEAM_ATTITUDE_METHODS = (
    "SetTeamAttitudeTowards",
    "SetAttitudeTowards",
    "SetTeamAttitude",
)

DAMAGE_METHOD_HINTS = ("takedamage", "receivedamage", "applydamage", "dealdamage")

COMBAT_SCRIPT_STATES = (
    "Active",
    "Combat",
    "Engaged",
    "Aggressive",
    "Awake",
    "Hostile",
    "BossFight",
    "CombatStarted",
    "IntroComplete",
    "Phase1",
    "SpawnComplete",
)

# Enabling Idle_Combat / Intro keeps Thol (Char_BigBoss) standing still — UberBigBoss
# does not use those gates the same way, which is why Invincible Thol wakes and base Thol does not.
IDLE_SCRIPT_STATES = (
    "Idle",
    "Idle_Combat",
    "Intro",
    "BossIntro",
    "Waiting",
    "Passive",
    "Cinematic",
    "SpawnTrick",
)

BOSS_NAME_TOKENS = ("boss", "terramorph", "tubaboss", "bigboss", "raid", "trueboss", "uber", "grassboss", "bitterblight")

# Per-actor tweaks from dump / spawn behavior (raid bosses need intro/script wake).
ACTOR_AGGRO_PROFILES: dict[str, dict[str, Any]] = {
    "Char_TubaBoss": {
        "damage_amount": 50.0,
        "extra_script_states": (
            "BossActive",
            "Combat",
            "Engaged",
            "Spawned",
            "TubaFight",
            "Water",
            "Active",
            "IntroComplete",
            "BossFight",
            "Phase1",
            "SpawnComplete",
            "Aggressive",
            "Awake",
            "Hostile",
        ),
        "disable_script_states": IDLE_SCRIPT_STATES,
        "script_event_methods": (
            "GbxActorScriptEvt__OnStartedSwimming",
            "GbxActorScriptEvt__OnStoppedSwimming",
            "OnBeginPlay",
            "OnInit",
            "StartBossFight",
            "OnBossFightStarted",
            "SkipIntro",
            "FinishIntro",
            "BeginCombat",
            "ActivateEncounter",
        ),
        "flags": {
            "bAlwaysAwareInThreatArea": True,
            "bWaitingForSpawnTrick": False,
            "bCanBeTargeted": True,
            "bTargetable": True,
            "bPassiveAI": False,
            "bBossIntroComplete": True,
            "bIntroFinished": True,
            "bCombatStarted": True,
            "bCanAttack": True,
            "bInvulnerable": False,
            "bGodMode": False,
            "bIsInvulnerable": False,
        },
    },
    "Char_BigBoss": {
        "damage_amount": 75.0,
        "extra_script_states": (
            "BossFight",
            "Combat",
            "Engaged",
            "Active",
            "IntroComplete",
            "Phase1",
            "SpawnComplete",
            "Aggressive",
            "Awake",
            "Hostile",
        ),
        "disable_script_states": IDLE_SCRIPT_STATES,
        "script_event_methods": (
            "OnBeginPlay",
            "OnInit",
            "CE_ToCenter",
            "CE_CenterReached",
            "StartBossFight",
            "OnBossFightStarted",
            "SkipIntro",
            "FinishIntro",
        ),
        "flags": {
            "bPassiveAI": False,
            "bWaitingForSpawnTrick": False,
            "bBossIntroComplete": True,
            "bIntroFinished": True,
            "bCombatStarted": True,
            "bAlwaysAwareInThreatArea": True,
            "bCanBeTargeted": True,
            "bCanAttack": True,
            "bInvulnerable": False,
            "bGodMode": False,
            "bIsInvulnerable": False,
        },
    },
    "Char_BigBoss_TRUE": {
        "damage_amount": 80.0,
        "extra_script_states": (
            "BossFight",
            "Combat",
            "Engaged",
            "Active",
            "IntroComplete",
            "Phase1",
            "SpawnComplete",
            "Aggressive",
            "Awake",
            "Hostile",
        ),
        "disable_script_states": IDLE_SCRIPT_STATES,
        "script_event_methods": (
            "OnBeginPlay",
            "OnInit",
            "CE_ToCenter",
            "CE_CenterReached",
            "StartBossFight",
            "OnBossFightStarted",
            "SkipIntro",
            "FinishIntro",
        ),
        "flags": {
            "bPassiveAI": False,
            "bWaitingForSpawnTrick": False,
            "bBossIntroComplete": True,
            "bIntroFinished": True,
            "bCombatStarted": True,
            "bAlwaysAwareInThreatArea": True,
            "bCanAttack": True,
            "bInvulnerable": False,
            "bIsInvulnerable": False,
        },
    },
    "Char_UberBigBoss": {
        "damage_amount": 50.0,
        "extra_script_states": ("BossFight", "Combat", "Engaged", "Active", "IntroComplete", "Phase1"),
        "disable_script_states": IDLE_SCRIPT_STATES,
        "flags": {
            "bPassiveAI": False,
            "bWaitingForSpawnTrick": False,
            "bBossIntroComplete": True,
            "bCombatStarted": True,
            "bAlwaysAwareInThreatArea": True,
        },
    },
    "Char_GrassBoss": {
        "damage_amount": 45.0,
        "extra_script_states": (
            "BossFight",
            "Combat",
            "Engaged",
            "Active",
            "IntroComplete",
            "Phase1",
            "SpawnComplete",
            "Aggressive",
            "Awake",
            "Hostile",
        ),
        "disable_script_states": IDLE_SCRIPT_STATES,
        "script_event_methods": (
            "OnBeginPlay",
            "OnInit",
            "StartBossFight",
            "OnBossFightStarted",
            "SkipIntro",
            "FinishIntro",
            "BeginCombat",
            "ActivateEncounter",
        ),
        "flags": {
            "bPassiveAI": False,
            "bWaitingForSpawnTrick": False,
            "bBossIntroComplete": True,
            "bIntroFinished": True,
            "bCombatStarted": True,
            "bAlwaysAwareInThreatArea": True,
            "bCanBeTargeted": True,
            "bCanAttack": True,
            "bInvulnerable": False,
            "bGodMode": False,
            "bIsInvulnerable": False,
        },
    },
    "Char_GrassBoss_TrueBoss": {
        "damage_amount": 55.0,
        "extra_script_states": (
            "BossFight",
            "Combat",
            "Engaged",
            "Active",
            "IntroComplete",
            "Phase1",
            "SpawnComplete",
            "Aggressive",
            "Awake",
            "Hostile",
        ),
        "disable_script_states": IDLE_SCRIPT_STATES,
        "script_event_methods": (
            "OnBeginPlay",
            "OnInit",
            "StartBossFight",
            "OnBossFightStarted",
            "SkipIntro",
            "FinishIntro",
            "BeginCombat",
            "ActivateEncounter",
        ),
        "flags": {
            "bPassiveAI": False,
            "bWaitingForSpawnTrick": False,
            "bBossIntroComplete": True,
            "bIntroFinished": True,
            "bCombatStarted": True,
            "bAlwaysAwareInThreatArea": True,
            "bCanAttack": True,
            "bInvulnerable": False,
            "bIsInvulnerable": False,
        },
    },
}

def _iter_callables(obj: Any, hints: Iterable[str]) -> list[str]:
    if obj is None:
        return []
    names: list[str] = []
    try:
        for name in dir(obj):
            if name.startswith("_"):
                continue
            low = name.lower()
            if not any(h in low for h in hints):
                continue
            fn = getattr(obj, name, None)
            if callable(fn):
                names.append(name)
    except Exception:
        return []
    return names


def _try_call(fn: Any, *args: Any) -> bool:
    try:
        fn(*args)
        return True
    except Exception:
        return False


def _try_setattr(obj: Any, attr: str, value: Any) -> bool:
    try:
        setattr(obj, attr, value)
        return True
    except Exception:
        return False


def _iter_child_components(root: Any, *, limit: int = 64) -> list[Any]:
    """Walk common UE component lists on actors."""
    out: list[Any] = []
    seen: set[int] = set()
    queue: list[Any] = [root]
    attrs = (
        "BlueprintCreatedComponents",
        "InstanceComponents",
        "Children",
        "ComponentTemplates",
    )
    while queue and len(out) < limit:
        obj = queue.pop(0)
        if obj is None:
            continue
        oid = id(obj)
        if oid in seen:
            continue
        seen.add(oid)
        out.append(obj)
        for attr in attrs:
            try:
                val = getattr(obj, attr, None)
            except Exception:
                continue
            if val is None:
                continue
            try:
                items = list(val)
            except TypeError:
                items = [val]
            for item in items:
                if item is not None and id(item) not in seen:
                    queue.append(item)
    return out


def _find_territory_components(mob: Any) -> list[Any]:
    """Return GbxTerritoryComponent instances attached to a spawned character."""
    found: list[Any] = []
    seen: set[int] = set()
    for comp in _iter_child_components(mob):
        try:
            cls = str(getattr(comp, "Class", "") or comp.__class__.__name__)
        except Exception:
            cls = str(comp)
        if "GbxTerritoryComponent" not in cls and "TerritoryComponent" not in cls:
            continue
        oid = id(comp)
        if oid in seen:
            continue
        seen.add(oid)
        found.append(comp)
    if found:
        return found
    try:
        import unrealsdk  # noqa: PLC0415

        owner_key = str(mob)
        for cn in ("GbxTerritoryComponent",):
            try:
                pool = list(unrealsdk.find_all(cn, False) or [])
            except Exception:
                try:
                    pool = list(unrealsdk.find_all(cn) or [])
                except Exception:
                    pool = []
            for comp in pool:
                try:
                    owner = getattr(comp, "GetOwner", None)
                    if callable(owner) and str(owner()) == owner_key:
                        oid = id(comp)
                        if oid not in seen:
                            seen.add(oid)
                            found.append(comp)
                except Exception:
                    continue
    except Exception:
        pass
    return found


def _poke_territory_area(area: Any, *, everywhere: bool = True, radius: float = 50000.0) -> int:
    """Expand Threat/Combat/Patrol territory so manually spawned AI sees the player."""
    if area is None:
        return 0
    changed = 0
    if everywhere and _try_setattr(area, "bEverywhere", True):
        changed += 1
    for attr, value in (("Radius", float(radius)), ("Height", float(radius))):
        if _try_setattr(area, attr, value):
            changed += 1
    return changed


def poke_territory_settings(mob: Any, *, boss: bool = False) -> str:
    """
    Apply GbxTerritorySettings from live-editor dumps (Pawn / GbxGameSpawner).

    Manually spawned raid bosses often ignore the player because ThreatTerritory /
    CombatTerritory are empty and bAlwaysAwareInThreatArea lives on the territory
    component settings struct — not the pawn root.
    """
    if mob is None:
        return "territory skipped (no mob)"
    comps = _find_territory_components(mob)
    if not comps:
        return "territory skipped (no GbxTerritoryComponent)"
    radius = 80000.0 if boss else 50000.0
    touched = 0
    for comp in comps:
        settings = None
        try:
            settings = getattr(comp, "settings", None)
        except Exception:
            settings = None
        if settings is None:
            continue
        if _try_setattr(settings, "bAlwaysAwareInThreatArea", True):
            touched += 1
        if boss and _try_setattr(settings, "bUseCombatProxy", False):
            touched += 1
        for field in ("ThreatTerritory", "CombatTerritory", "PatrolTerritory"):
            try:
                area = getattr(settings, field, None)
            except Exception:
                area = None
            if area is not None:
                touched += _poke_territory_area(area, everywhere=True, radius=radius)
        for meth in ("RefreshTerritory", "UpdateTerritory", "RebuildTerritory", "OnTerritoryChanged"):
            fn = getattr(comp, meth, None)
            if callable(fn) and _try_call(fn):
                touched += 1
    msg = f"territory poke components={len(comps)} touches={touched}"
    if touched:
        _sdk_log(msg)
    return msg


def _objects_for_aggro(attacker: Any) -> list[Any]:
    out: list[Any] = [attacker]
    for attr in ("Controller", "AIController", "Character", "Brain", "GbxBrain"):
        try:
            v = getattr(attacker, attr, None)
            if v is not None and v not in out:
                out.append(v)
        except Exception:
            continue
    return out


def _profile_for_code(actor_code: str) -> dict[str, Any] | None:
    code = (actor_code or "").strip()
    if not code:
        return None
    if code in ACTOR_AGGRO_PROFILES:
        return ACTOR_AGGRO_PROFILES[code]
    low = code.lower()
    for key, prof in ACTOR_AGGRO_PROFILES.items():
        if key.lower() == low:
            return prof
    if "tubaboss" in low or "terramorph" in low:
        return ACTOR_AGGRO_PROFILES.get("Char_TubaBoss")
    if "uberbigboss" in low:
        return ACTOR_AGGRO_PROFILES.get("Char_UberBigBoss")
    if "bigboss" in low:
        return ACTOR_AGGRO_PROFILES.get("Char_BigBoss_TRUE" if "true" in low else "Char_BigBoss")
    if "grassboss" in low:
        return ACTOR_AGGRO_PROFILES.get("Char_GrassBoss_TrueBoss" if "true" in low else "Char_GrassBoss")
    return None


def _is_likely_boss(actor: Any, actor_code: str = "") -> bool:
    hay = f"{actor} {actor_code}".lower()
    return any(tok in hay for tok in BOSS_NAME_TOKENS)


def poke_targetable_flags(actor: Any, *, enable: bool = True) -> int:
    """Let AI pick this actor as a valid target (needed for mob-vs-mob)."""
    writes = 0
    for attr, value in (
        ("bTargetable", enable),
        ("bCanBeTargeted", enable),
        ("bIgnoreAIAggro", not enable),
        ("bNeverTarget", not enable),
    ):
        if _try_setattr(actor, attr, value):
            writes += 1
    return writes


def complete_spawn_trick(mob: Any) -> tuple[bool, str]:
    """SSP-spawned enemies often sit in bWaitingForSpawnTrick — clear that gate."""
    if mob is None:
        return False, "no mob"
    try:
        from .spawn_core import is_aggroable_character  # noqa: PLC0415

        if not is_aggroable_character(mob):
            return False, "not an AI character"
    except Exception:
        pass
    parts: list[str] = []
    ok = False

    if _try_setattr(mob, "bWaitingForSpawnTrick", False):
        parts.append("bWaitingForSpawnTrick=False")
        ok = True

    # Dump evidence: live enemies expose OnRep_WaitingForSpawnTrick — fire after clear.
    on_rep = getattr(mob, "OnRep_WaitingForSpawnTrick", None)
    if callable(on_rep) and _try_call(on_rep):
        parts.append("OnRep_WaitingForSpawnTrick()")
        ok = True

    for meth in _iter_callables(mob, SPAWN_TRICK_METHOD_HINTS):
        fn = getattr(mob, meth, None)
        if not callable(fn):
            continue
        if _try_call(fn):
            parts.append(f"{meth}()")
            ok = True

    stop = getattr(mob, "StopTrickLocal", None)
    if callable(stop):
        for args in ((), (True,), (False,)):
            if _try_call(stop, *args):
                parts.append(f"StopTrickLocal{args!r}")
                ok = True
                break

    ctrl = getattr(mob, "Controller", None)
    if ctrl is None:
        # SpawnDefaultController null-AV'd on some NPC shells — skip friendlies.
        name = str(getattr(mob, "Name", "") or "").lower()
        path = str(mob).lower()
        if "npc_" in name or "npc_" in path or "friendly" in path:
            parts.append("skip SpawnDefaultController (npc/friendly)")
        else:
            spawn_ctrl = getattr(mob, "SpawnDefaultController", None)
            if callable(spawn_ctrl):
                try:
                    if _try_call(spawn_ctrl):
                        parts.append("SpawnDefaultController()")
                        ok = True
                        ctrl = getattr(mob, "Controller", None)
                except Exception:
                    parts.append("SpawnDefaultController failed")

    if ctrl is not None:
        for meth in ("RunBehaviorTree", "ActivateAI", "RestartLogic"):
            fn = getattr(ctrl, meth, None)
            if callable(fn) and _try_call(fn):
                parts.append(f"Controller.{meth}()")
                ok = True

    return ok, "; ".join(parts) if parts else "spawn trick clear failed"


def assign_ffa_character_factions(mobs: list[Any]) -> int:
    """Give each mob a distinct army/clan slot so BL4 AI may treat peers as hostile."""
    changed = 0
    for i, mob in enumerate(mobs):
        if mob is None:
            continue
        slot = 200 + i
        for meth in ("SetCharacterArmy", "SetCharacterClan", "SetCharacterEnemyType"):
            fn = getattr(mob, meth, None)
            if not callable(fn):
                continue
            for arg in (slot, str(slot), i, i + 1):
                if _try_call(fn, arg):
                    changed += 1
                    break
        assign_ffa_team_slots([mob])
    return changed


def try_fire_profile_script_events(mob: Any, actor_code: str = "") -> tuple[bool, str]:
    """Boss-specific script event pings (e.g. TubaBoss swim / intro scripts)."""
    profile = _profile_for_code(actor_code)
    if not profile:
        return False, "no profile events"
    methods = profile.get("script_event_methods") or ()
    fired: list[str] = []
    for script_obj in _walk_script_objects(mob):
        for meth in methods:
            fn = getattr(script_obj, meth, None)
            if callable(fn) and _try_call(fn):
                fired.append(meth)
    return bool(fired), ", ".join(fired) if fired else "no profile script events"


def poke_combat_flags(attacker: Any) -> None:
    for attr, value in (
        ("bWantsCombat", True),
        ("bInCombat", True),
        ("bIsInCombat", True),
        ("bAlwaysAwareInThreatArea", True),
        ("bWaitingForSpawnTrick", False),
        ("bPassiveAI", False),
        ("bCanAttack", True),
        ("bUseTeamAttitudes", True),
        ("bAggressiveAI", True),
    ):
        _try_setattr(attacker, attr, value)


def _walk_script_objects(root: Any, *, limit: int = 48) -> list[Any]:
    """Find child script actors that expose SetScriptStateEnabled."""
    out: list[Any] = []
    seen: set[int] = set()
    queue: list[Any] = [root]
    while queue and len(out) < limit:
        obj = queue.pop(0)
        oid = id(obj)
        if oid in seen:
            continue
        seen.add(oid)
        if obj is None:
            continue
        if callable(getattr(obj, "SetScriptStateEnabled", None)):
            out.append(obj)
        for attr in (
            "ScriptData",
            "Scripts",
            "Instances",
            "InstancedScripts",
            "ReplicatedInstances",
            "Children",
            "InstanceComponents",
            "BlueprintCreatedComponents",
        ):
            try:
                val = getattr(obj, attr, None)
            except Exception:
                continue
            if val is None:
                continue
            try:
                items = list(val)
            except TypeError:
                items = [val]
            except Exception:
                continue
            for item in items:
                if item is not None and id(item) not in seen:
                    queue.append(item)
    return out


def enable_combat_script_states(mob: Any) -> int:
    enabled = 0
    for script_obj in _walk_script_objects(mob):
        fn = getattr(script_obj, "SetScriptStateEnabled", None)
        if not callable(fn):
            continue
        for state in IDLE_SCRIPT_STATES:
            _try_call(fn, state, False) or _try_call(fn, state, 0)
        for state in COMBAT_SCRIPT_STATES:
            if _try_call(fn, state, True) or _try_call(fn, state, 1):
                enabled += 1
    return enabled


def wake_ai(attacker: Any) -> tuple[bool, str]:
    if attacker is None:
        return False, "no attacker"
    for meth in _iter_callables(attacker, WAKE_METHOD_HINTS):
        fn = getattr(attacker, meth, None)
        if not callable(fn):
            continue
        if meth.lower() == "spawndefaultcontroller":
            if _try_call(fn):
                return True, f"{meth}()"
        elif meth.lower() == "possess":
            ctrl = getattr(attacker, "Controller", None)
            if ctrl is not None and _try_call(fn, ctrl):
                return True, f"{meth}(Controller)"
        elif _try_call(fn):
            return True, f"{meth}()"
    return False, "no wake RPC"


def prepare_mob_for_combat(mob: Any, *, is_boss: bool | None = None, actor_code: str = "") -> None:
    """Clear spawn-trick / passive gates before forcing targets."""
    if mob is None:
        return
    boss = _is_likely_boss(mob, actor_code) if is_boss is None else bool(is_boss)
    profile = _profile_for_code(actor_code)

    complete_spawn_trick(mob)
    poke_combat_flags(mob)
    poke_targetable_flags(mob, enable=True)
    wake_ai(mob)
    enable_combat_script_states(mob)
    territory_msg = poke_territory_settings(mob, boss=boss)

    if profile:
        for attr, value in (profile.get("flags") or {}).items():
            _try_setattr(mob, str(attr), value)
        for state in profile.get("disable_script_states") or ():
            _disable_script_state_on_mob(mob, str(state))
        for state in profile.get("extra_script_states") or ():
            _enable_script_state_on_mob(mob, str(state))
        try_fire_profile_script_events(mob, actor_code)

    if boss:
        for attr in ("bBossIntroComplete", "bIntroFinished", "bCombatStarted", "bPassiveAI"):
            if attr == "bPassiveAI":
                _try_setattr(mob, attr, False)
            else:
                _try_setattr(mob, attr, True)
        for attr in ("bInvulnerable", "bIsInvulnerable", "bGodMode"):
            _try_setattr(mob, attr, False)
        _try_setattr(mob, "bAlwaysAwareInThreatArea", True)
        _try_setattr(mob, "bCanAttack", True)
        # Sol / Fortress / Tuba-style arenas gate AI until domain triggers or start pads fire.
        arena_radius = 12000.0 if "tuba" in f"{actor_code} {mob}".lower() else 5500.0
        arena_msg = poke_nearby_encounter_starters(near_actor=mob, radius=arena_radius)
        trigger_msg = poke_nearby_trigger_boxes(near_actor=mob, radius=arena_radius)
        if territory_msg.startswith("territory poke"):
            _sdk_log(f"{territory_msg}; {arena_msg}; {trigger_msg}")


def _gameplay_pawn() -> Any | None:
    try:
        from mods_base import get_pc  # noqa: PLC0415

        pc = get_pc()
        if pc is None:
            return None
        return getattr(pc, "Pawn", None) or getattr(pc, "AcknowledgedPawn", None)
    except Exception:
        return None


def _trigger_collision_comp(trigger: Any) -> Any | None:
    for attr in ("CollisionComp", "CollisionComponent", "BrushComponent", "BoxComponent"):
        try:
            comp = getattr(trigger, attr, None)
        except Exception:
            comp = None
        if comp is not None:
            return comp
    for comp in _iter_child_components(trigger, limit=12):
        try:
            cls = str(getattr(comp, "Class", "") or comp)
        except Exception:
            cls = str(comp)
        if "BoxComponent" in cls or "ShapeComponent" in cls or "Collision" in cls:
            return comp
    return None


def poke_nearby_trigger_boxes(
    *,
    near_actor: Any | None = None,
    near_loc: Any | None = None,
    overlap_actor: Any | None = None,
    radius: float = 12000.0,
) -> str:
    """
    Fire overlap / activate methods on nearby OakTriggerBox actors.

    Tuba Boss and similar DLC arenas gate combat behind domain triggers — standing
    inside the box is not enough for a freshly spawned boss until overlap fires.
    """
    origin = near_loc if near_loc is not None else (_actor_loc(near_actor) if near_actor is not None else None)
    if origin is None:
        return "trigger poke skipped (no origin)"
    actor = overlap_actor if overlap_actor is not None else _gameplay_pawn()
    if actor is None:
        return "trigger poke skipped (no overlap actor)"
    radius_sq = float(radius) * float(radius)
    fired = 0
    scanned = 0
    try:
        import unrealsdk  # noqa: PLC0415
    except Exception:
        return "trigger poke skipped (no unrealsdk)"

    overlap_methods = (
        "OnActorBeginOverlap",
        "NotifyActorBeginOverlap",
        "ActorBeginOverlap",
        "ReceiveActorBeginOverlap",
        "OnBeginOverlap",
        "OnComponentBeginOverlap",
    )
    activate_methods = ("Activate", "Trigger", "Start", "BeginPlay", "SetEncounterEnabled")

    seen: set[int] = set()
    for cn in ("OakTriggerBox", "TriggerBox", "TriggerBase", "TriggerVolume", "OakTriggerVolume"):
        try:
            pool = list(unrealsdk.find_all(cn, False) or [])
        except Exception:
            try:
                pool = list(unrealsdk.find_all(cn) or [])
            except Exception:
                pool = []
        for obj in pool:
            if obj is None:
                continue
            oid = id(obj)
            if oid in seen:
                continue
            seen.add(oid)
            loc = _actor_loc(obj)
            if loc is None or _loc_dist_sq(loc, origin) > radius_sq:
                continue
            scanned += 1
            try:
                name = str(getattr(obj, "Name", "") or obj)
            except Exception:
                name = str(obj)
            coll = _trigger_collision_comp(obj)
            done = False
            for meth in overlap_methods:
                fn = getattr(obj, meth, None)
                if not callable(fn):
                    continue
                for args in (
                    (actor, coll),
                    (actor,),
                    (actor, actor),
                    (coll, actor),
                    (),
                ):
                    if _try_call(fn, *args):
                        fired += 1
                        _sdk_log(f"trigger poke: {name}.{meth}{args!r}")
                        done = True
                        break
                if done:
                    break
            if done:
                continue
            for meth in activate_methods:
                fn = getattr(obj, meth, None)
                if callable(fn) and _try_call(fn, True):
                    fired += 1
                    _sdk_log(f"trigger poke: {name}.{meth}(True)")
                    break
                if callable(fn) and _try_call(fn):
                    fired += 1
                    _sdk_log(f"trigger poke: {name}.{meth}()")
                    break
    msg = f"trigger poke scanned={scanned} fired={fired}"
    _sdk_log(msg)
    return msg


_ARENA_START_METHOD_HINTS = (
    "startbossfight",
    "onbossfightstarted",
    "beginbossfight",
    "begincombat",
    "startcombat",
    "activateencounter",
    "beginencounter",
    "startencounter",
    "forceencounter",
    "setencounterenabled",
    "resetencounter",
    "startevent",
    "triggerevent",
    "onactivated",
    "notifyactivated",
    "skipintro",
    "finishintro",
)

_ARENA_NAME_HINTS = (
    "encounter",
    "bossfight",
    "raid",
    "arenastart",
    "startbutton",
    "startpad",
    "idolator",
    "grassboss",
    "sol",
    "tuba",
    "trigger",
    "triggerbox",
    "domain",
    "volume",
    "sequencer",
    "mission",
)


def _actor_loc(actor: Any) -> Any | None:
    for meth in ("K2_GetActorLocation", "GetActorLocation"):
        fn = getattr(actor, meth, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                continue
    return None


def _loc_dist_sq(a: Any, b: Any) -> float:
    try:
        dx = float(a.X) - float(b.X)
        dy = float(a.Y) - float(b.Y)
        dz = float(a.Z) - float(b.Z)
        return dx * dx + dy * dy + dz * dz
    except Exception:
        return 1e18


def poke_nearby_encounter_starters(
    *,
    near_actor: Any | None = None,
    near_loc: Any | None = None,
    radius: float = 5500.0,
) -> str:
    """
    Fire StartBossFight / ActivateEncounter-style methods on nearby world actors.

    Idolator Sol (Fortress_Grasslands) and similar arenas often leave manually spawned
    bosses dormant until the player hits the world start pad — this best-effort pass
    mimics that without requiring the button.
    """
    origin = near_loc if near_loc is not None else (_actor_loc(near_actor) if near_actor is not None else None)
    if origin is None:
        return "arena poke skipped (no origin)"
    radius_sq = float(radius) * float(radius)
    fired = 0
    scanned = 0
    try:
        import unrealsdk  # noqa: PLC0415
    except Exception:
        return "arena poke skipped (no unrealsdk)"

    class_names = (
        "OakTriggerBox",
        "TriggerBox",
        "TriggerBase",
        "TriggerVolume",
        "OakTriggerVolume",
        "GbxTriggerVolume",
        "LevelSequenceActor",
        "GbxLevelSequenceActor",
        "GbxGameSpawnEncounter",
        "OakSpawnEncounter",
        "SpawnEncounter",
        "OakEncounter",
        "EncounterManager",
        "GbxActionManager",
        "GbxTerritory",
    )
    seen: set[int] = set()
    for cn in class_names:
        try:
            pool = list(unrealsdk.find_all(cn, False) or [])
        except Exception:
            try:
                pool = list(unrealsdk.find_all(cn) or [])
            except Exception:
                pool = []
        for obj in pool:
            if obj is None:
                continue
            oid = id(obj)
            if oid in seen:
                continue
            seen.add(oid)
            try:
                name = str(getattr(obj, "Name", "") or obj)
            except Exception:
                name = str(obj)
            low = name.lower()
            # Prefer name-hinted encounter/start actors; skip pure static meshes unless method matches.
            name_hit = any(h in low for h in _ARENA_NAME_HINTS)
            loc = _actor_loc(obj)
            if loc is None:
                continue
            if _loc_dist_sq(loc, origin) > radius_sq:
                continue
            scanned += 1
            methods = _iter_callables(obj, _ARENA_START_METHOD_HINTS)
            if not methods and not name_hit:
                continue
            if not methods:
                # Name looked relevant — try a few common zero-arg starts.
                for guess in (
                    "Activate",
                    "Start",
                    "Trigger",
                    "BeginPlay",
                    "StartBossFight",
                    "SetEncounterEnabled",
                ):
                    fn = getattr(obj, guess, None)
                    if callable(fn) and _try_call(fn, True):
                        fired += 1
                        _sdk_log(f"arena poke: {name}.{guess}(True)")
                        break
                    if callable(fn) and _try_call(fn):
                        fired += 1
                        _sdk_log(f"arena poke: {name}.{guess}()")
                        break
                continue
            for meth in methods[:4]:
                fn = getattr(obj, meth, None)
                if not callable(fn):
                    continue
                if meth.lower() == "setencounterenabled" and _try_call(fn, True):
                    fired += 1
                    _sdk_log(f"arena poke: {name}.{meth}(True)")
                    break
                if _try_call(fn):
                    fired += 1
                    _sdk_log(f"arena poke: {name}.{meth}()")
                    break
    msg = f"arena poke scanned={scanned} fired={fired}"
    _sdk_log(msg)
    return msg


def _enable_script_state_on_mob(mob: Any, state: str) -> None:
    for script_obj in _walk_script_objects(mob):
        for meth in ("SetScriptStateEnabled", "StaticSetScriptStateEnabled"):
            fn = getattr(script_obj, meth, None)
            if callable(fn):
                _try_call(fn, state, True) or _try_call(fn, state, 1)


def _disable_script_state_on_mob(mob: Any, state: str) -> None:
    for script_obj in _walk_script_objects(mob):
        for meth in ("SetScriptStateEnabled", "StaticSetScriptStateEnabled"):
            fn = getattr(script_obj, meth, None)
            if callable(fn):
                _try_call(fn, state, False) or _try_call(fn, state, 0)


def try_notify_damage_scripts(victim: Any, instigator: Any) -> tuple[bool, str]:
    """Fire script damage events seen on live enemies in dumps (wakes some bosses)."""
    if victim is None:
        return False, "no victim"
    for script_obj in _walk_script_objects(victim):
        for meth in (
            "GbxActorScriptEvt__DamageState_OnTakeAnyDamage",
            "OnTakeAnyDamage",
            "ReceiveAnyDamage",
        ):
            fn = getattr(script_obj, meth, None)
            if not callable(fn):
                continue
            for args in (
                (1.0, None, instigator, instigator),
                (1.0, instigator),
                (instigator, 1.0),
                (),
            ):
                if _try_call(fn, *args):
                    return True, f"{meth}{args!r}"
    return False, "no damage script event"


def try_radial_damage_between(
    attacker: Any,
    victim: Any,
    *,
    amount: float = 5.0,
) -> tuple[bool, str]:
    """GameplayStatics radial ping between two mobs (FFA fallback)."""
    try:
        import unrealsdk  # noqa: PLC0415
    except Exception:
        return False, "no unrealsdk"
    vloc = _actor_location(victim)
    aloc = _actor_location(attacker)
    if vloc is None:
        return False, "no victim location"
    origin = vloc if aloc is None else vloc
    gs_cls = unrealsdk.find_class("GameplayStatics")
    cdo = getattr(gs_cls, "ClassDefaultObject", None) if gs_cls is not None else None
    if cdo is None:
        return False, "no GameplayStatics"
    dmg = max(1.0, float(amount))
    for meth in ("ApplyRadialDamage", "ApplyDamage"):
        fn = getattr(cdo, meth, None)
        if not callable(fn):
            continue
        for args in (
            (dmg, origin, 400.0, None, None, attacker, attacker),
            (dmg, origin, 400.0, None, attacker, attacker),
            (dmg, victim, attacker, attacker),
            (dmg, victim, attacker),
        ):
            if _try_call(fn, *args):
                return True, f"GameplayStatics.{meth}{args!r}"
    recv = getattr(victim, "ReceiveRadialDamage", None)
    if callable(recv):
        for args in ((dmg, None, origin, None, attacker), (dmg, origin, attacker)):
            if _try_call(recv, *args):
                return True, f"ReceiveRadialDamage{args!r}"
    return False, "radial damage failed"


def assign_ffa_team_slots(mobs: list[Any]) -> int:
    """Give each mob a distinct team slot so enemies may target each other."""
    changed = 0
    for i, mob in enumerate(mobs):
        if mob is None:
            continue
        slot = 100 + i
        for meth in ("SetGroupTeamHandle", "SetTeamHandle", "SetTeamIndex", "SetTeamId"):
            fn = getattr(mob, meth, None)
            if callable(fn) and _try_call(fn, slot):
                changed += 1
                break
        for attr in ("TeamHandle", "TeamIndex", "TeamId", "GroupTeamHandle"):
            if _try_setattr(mob, attr, slot):
                changed += 1
    return changed


def try_make_hostile(attacker: Any, target: Any) -> tuple[bool, str]:
    """Best-effort team attitude override so enemies can hate each other (FFA)."""
    if attacker is None or target is None:
        return False, "missing actor for hostility"
    parts: list[str] = []
    ok = False

    for obj in _objects_for_aggro(attacker):
        for meth_name in TEAM_ATTITUDE_METHODS:
            fn = getattr(obj, meth_name, None)
            if not callable(fn):
                continue
            for args in (
                (target, 2),
                (target, 1),
                (target, True),
                (target,),
            ):
                if _try_call(fn, *args):
                    parts.append(f"{meth_name}{args!r}")
                    ok = True

        for meth in _iter_callables(obj, TEAM_METHOD_HINTS):
            fn = getattr(obj, meth, None)
            if not callable(fn):
                continue
            for args in (
                (target, 2),
                (target, 1),
                (target, True),
                (target, "Hostile"),
                (target,),
            ):
                if _try_call(fn, *args):
                    parts.append(f"{meth}{args!r}")
                    ok = True

    return ok, "; ".join(parts) if parts else "no team hostility RPC"


def _damage_amount_for(attacker: Any, target: Any, attacker_code: str = "") -> float:
    prof = _profile_for_code(attacker_code)
    if prof and "damage_amount" in prof:
        return float(prof["damage_amount"])
    if _is_likely_boss(attacker, attacker_code) or _is_likely_boss(target):
        return 15.0
    return 3.0


def try_apply_gameplay_damage(
    victim: Any,
    instigator: Any,
    *,
    amount: float = 1.0,
) -> tuple[bool, str]:
    """Prefer GameplayStatics.ApplyDamage / Oak TakeDamage with a real instigator."""
    if victim is None:
        return False, "no victim"
    try:
        from .spawn_core import is_aggroable_character  # noqa: PLC0415

        if not is_aggroable_character(victim):
            return False, "victim not an AI character (skip damage)"
    except Exception:
        pass
    # Never damage during ImGui draw — null AV through pyunrealsdk.
    try:
        import blimgui as _blg  # noqa: PLC0415

        if bool(getattr(_blg, "_IN_IMGUI_FRAME", False)):
            return False, "blocked during ImGui frame"
    except Exception:
        pass
    dmg = max(1.0, float(amount))
    # Prefer a PlayerController as EventInstigator — pawn-only + None DamageType
    # has null-AV'd mid-frame on raid bosses (Tuba).
    event_pc = None
    if instigator is not None:
        for attr in ("Controller", "PlayerController", "OakPlayerController"):
            try:
                cand = getattr(instigator, attr, None)
            except Exception:
                cand = None
            if cand is not None:
                event_pc = cand
                break
        cn = str(getattr(getattr(instigator, "Class", None), "Name", "") or "")
        if "PlayerController" in cn:
            event_pc = instigator
    try:
        import unrealsdk  # noqa: PLC0415
    except Exception:
        unrealsdk = None  # type: ignore[assignment]

    dmg_type = None
    if unrealsdk is not None:
        for cls_name in ("DamageType", "GbxDamageType", "OakDamageType"):
            try:
                dmg_cls = unrealsdk.find_class(cls_name)
            except Exception:
                dmg_cls = None
            if dmg_cls is not None:
                dmg_type = getattr(dmg_cls, "ClassDefaultObject", None) or dmg_cls
                break

    # Refuse ApplyDamage without a real EventInstigator — None shells crash shipping.
    if event_pc is None and instigator is None:
        return False, "no instigator for damage wake"

    if unrealsdk is not None:
        gs_cls = unrealsdk.find_class("GameplayStatics")
        cdo = getattr(gs_cls, "ClassDefaultObject", None) if gs_cls is not None else None
        if cdo is not None:
            apply_dmg = getattr(cdo, "ApplyDamage", None)
            if callable(apply_dmg):
                arg_sets: list[tuple[Any, ...]] = []
                # Prefer fully-populated arg sets only (no None DamageType / EventInstigator).
                if event_pc is not None and dmg_type is not None:
                    arg_sets.append((victim, dmg, event_pc, instigator, dmg_type))
                if event_pc is not None and dmg_type is not None and instigator is not None:
                    arg_sets.append((victim, dmg, event_pc, instigator, dmg_type))
                if dmg_type is not None and instigator is not None and event_pc is None:
                    # Last resort: pawn as instigator with a real DamageType class.
                    arg_sets.append((victim, dmg, instigator, instigator, dmg_type))
                for args in arg_sets:
                    try:
                        if _try_call(apply_dmg, *args):
                            return True, f"GameplayStatics.ApplyDamage{args!r}"
                    except Exception:
                        continue

    take = getattr(victim, "TakeDamage", None)
    if callable(take) and (event_pc is not None or instigator is not None):
        for args in (
            (dmg, None, event_pc or instigator, instigator),
            (dmg, None, instigator, instigator),
            (dmg, instigator, instigator),
            (dmg, instigator),
        ):
            try:
                if _try_call(take, *args):
                    return True, f"TakeDamage{args!r}"
            except Exception:
                continue
    return False, "ApplyDamage/TakeDamage failed"


def try_damage_wake(
    victim: Any,
    instigator: Any,
    *,
    amount: float = 1.0,
) -> tuple[bool, str]:
    """Tiny damage ping — wakes bosses / pulls FFA aggro when RPCs fail."""
    if victim is None:
        return False, "no victim"
    dmg = max(0.1, float(amount))
    g_ok, g_msg = try_apply_gameplay_damage(victim, instigator, amount=dmg)
    if g_ok:
        return True, g_msg
    arg_sets: tuple[tuple[Any, ...], ...] = (
        (dmg,),
        (dmg, None, instigator, instigator),
        (dmg, None, instigator, instigator, None),
        (dmg, instigator),
        (dmg, instigator, None),
    )
    for obj in (victim,):
        for meth in _iter_callables(obj, DAMAGE_METHOD_HINTS):
            fn = getattr(obj, meth, None)
            if not callable(fn):
                continue
            for args in arg_sets:
                if _try_call(fn, *args):
                    return True, f"{meth}{args!r}"
    return False, "damage wake failed"


def try_wake_oak_brain(attacker: Any, target: Any) -> tuple[bool, str]:
    """Oak/Gbx brain components often own the real focus target."""
    parts: list[str] = []
    ok = False
    for root in _objects_for_aggro(attacker):
        for attr in ("GbxBrain", "Brain", "AIBrain", "OakAIBrain"):
            brain = getattr(root, attr, None)
            if brain is None:
                continue
            for meth in (
                "SetFocusActor",
                "SetTargetActor",
                "SetEnemy",
                "SetFocus",
                "EngageTarget",
                "StartCombat",
            ):
                fn = getattr(brain, meth, None)
                if callable(fn) and _try_call(fn, target):
                    parts.append(f"{attr}.{meth}")
                    ok = True
    return ok, "; ".join(parts) if parts else "no brain wake"


def try_force_target(attacker: Any, target: Any, *, actor_code: str = "") -> tuple[bool, str]:
    """Try focus/target RPCs. Returns (matched, msg) — focus alone is not combat wake."""
    if attacker is None or target is None:
        return False, "missing attacker or target"
    prepare_mob_for_combat(attacker, actor_code=actor_code)
    poke_targetable_flags(target, enable=True)
    b_ok, b_msg = try_wake_oak_brain(attacker, target)
    if b_ok:
        _sdk_log(f"brain focus: {b_msg}")
        return True, f"focus:{b_msg}"
    arg_sets: tuple[tuple[Any, ...], ...] = (
        (target,),
        (target, 1.0),
        (target, True),
        (target, 9999.0),
        (target, 1),
    )
    for obj in _objects_for_aggro(attacker):
        for meth in _iter_callables(obj, AGGRO_METHOD_HINTS):
            fn = getattr(obj, meth, None)
            if not callable(fn):
                continue
            for args in arg_sets:
                if _try_call(fn, *args):
                    msg = f"{obj.__class__.__name__}.{meth}{args!r}"
                    _sdk_log(f"focus RPC: {msg}")
                    return True, f"focus:{msg}"
    return False, "no aggro RPC matched"


def _apply_pair_aggro(
    attacker: Any,
    target: Any,
    *,
    instigator: Any | None,
    damage_wake: bool,
    cross_hostile: bool,
    attacker_code: str = "",
) -> tuple[bool, str]:
    try:
        from .spawn_core import is_aggroable_character  # noqa: PLC0415

        if not is_aggroable_character(attacker):
            return False, "attacker not an AI character"
    except Exception:
        if attacker is None:
            return False, "no attacker"
    boss = _is_likely_boss(attacker, attacker_code)
    focus_ok, focus_msg = try_force_target(attacker, target, actor_code=attacker_code)
    parts = [focus_msg]
    combat_ok = False

    b_ok, b_msg = try_wake_oak_brain(attacker, target)
    if b_ok:
        parts.append(f"focus:{b_msg}")
        focus_ok = True

    trick_ok, trick_msg = complete_spawn_trick(attacker)
    if trick_ok:
        parts.append(f"spawn_trick:{trick_msg}")
        _sdk_log(f"spawn trick: {trick_msg}")

    script_n = enable_combat_script_states(attacker)
    if script_n:
        parts.append(f"script_states={script_n}")

    if cross_hostile:
        h_ok, h_msg = try_make_hostile(attacker, target)
        if h_ok:
            parts.append(h_msg)

    wake_amt = _damage_amount_for(attacker, target, attacker_code)
    # Bosses always need a real combat wake — SetFocus alone leaves them staring.
    # NPC friendlies (Amara / BruceBuddy shells) null-AV on ApplyDamage / SpawnDefaultController.
    code_l = str(attacker_code or "").lower()
    path_l = str(attacker).lower()
    is_npc_shell = (
        "npc_" in code_l
        or "char_npc_" in path_l
        or "/char_npc_" in path_l
        or "friendly" in path_l
    )
    need_wake = (bool(damage_wake) or not focus_ok or boss) and not is_npc_shell
    if is_npc_shell:
        parts.append("npc_shell:skip_damage_wake")
    if need_wake:
        d_inst = instigator if instigator is not None else target
        n_ok, n_msg = try_notify_damage_scripts(attacker, d_inst)
        if n_ok:
            parts.append(n_msg)
            combat_ok = True
            _sdk_log(f"damage script: {n_msg}")
        d_ok, d_msg = try_damage_wake(attacker, d_inst, amount=wake_amt)
        if d_ok:
            parts.append(d_msg)
            combat_ok = True
            _sdk_log(f"damage wake: {d_msg}")
        if cross_hostile:
            r_ok, r_msg = try_radial_damage_between(attacker, target, amount=wake_amt)
            if r_ok:
                parts.append(r_msg)
                combat_ok = True
            d2_ok, d2_msg = try_damage_wake(target, attacker, amount=wake_amt)
            if d2_ok:
                parts.append(f"peer:{d2_msg}")
                combat_ok = True

    if boss:
        # Focus-only is not success for bosses.
        ok = combat_ok or (trick_ok and script_n > 0 and focus_ok)
        tag = "combat_wake" if combat_ok else ("focus_only" if focus_ok else "wake_failed")
        summary = f"{tag}={'; '.join(parts)}"
        _sdk_log(summary)
        return ok, summary

    ok = combat_ok or focus_ok
    tag = "combat_wake" if combat_ok else ("focus_only" if focus_ok else "wake_failed")
    summary = f"{tag}={'; '.join(parts)}"
    _sdk_log(summary)
    return ok, summary


def _normalize_mob_entries(
    mobs: list[Any],
    mob_codes: dict[Any, str] | None,
) -> list[tuple[Any, str]]:
    out: list[tuple[Any, str]] = []
    for mob in mobs:
        if mob is None:
            continue
        code = ""
        if mob_codes:
            code = str(mob_codes.get(mob) or mob_codes.get(id(mob)) or "")
        out.append((mob, code))
    return out


def apply_aggro_mode(
    mobs: list[Any],
    *,
    mode: str,
    primary_target: Any | None,
    secondary_targets: list[Any] | None = None,
    damage_wake: bool = True,
    mob_codes: dict[Any, str] | None = None,
) -> tuple[int, int, str]:
    mode = (mode or "passive").strip().lower()
    if mode in ("passive", "none", "off"):
        return 0, 0, "passive — no aggro applied"
    if not mobs:
        return 0, 0, "no tracked mobs"

    try:
        from .spawn_core import is_aggroable_character  # noqa: PLC0415

        mobs = [m for m in mobs if is_aggroable_character(m)]
    except Exception:
        mobs = [m for m in mobs if m is not None]
    if not mobs:
        return 0, 0, "no aggroable characters (props filtered)"

    entries = _normalize_mob_entries(mobs, mob_codes)
    ok_n = 0
    fail_n = 0
    last = ""

    if mode in ("attack_me", "attack_party", "attack_player", "me", "party"):
        tgt = primary_target
        if tgt is None:
            return 0, len(entries), "no aggro target pawn"
        for mob, code in entries:
            boss = _is_likely_boss(mob, code)
            prepare_mob_for_combat(mob, is_boss=boss, actor_code=code)
            ok, msg = _apply_pair_aggro(
                mob,
                tgt,
                instigator=tgt,
                damage_wake=damage_wake or boss,
                cross_hostile=False,
                attacker_code=code,
            )
            last = msg
            if ok:
                ok_n += 1
            else:
                fail_n += 1
        return ok_n, fail_n, last

    if mode in ("free_for_all", "ffa", "each_other"):
        pool = list(entries)
        if len(pool) < 2:
            return 0, len(pool), "need 2+ mobs for free-for-all"
        mob_actors = [m for m, _c in pool]
        factions = assign_ffa_character_factions(mob_actors)
        teams = assign_ffa_team_slots(mob_actors)
        last = f"ffa factions={factions} teams={teams}"
        for mob, code in pool:
            prepare_mob_for_combat(mob, actor_code=code)
        pair_ok = 0
        pair_fail = 0
        for i, (mob, code) in enumerate(pool):
            for j, (tgt, tgt_code) in enumerate(pool):
                if i == j:
                    continue
                ok, msg = _apply_pair_aggro(
                    mob,
                    tgt,
                    instigator=mob,
                    damage_wake=True,
                    cross_hostile=True,
                    attacker_code=code,
                )
                last = msg
                if ok:
                    pair_ok += 1
                else:
                    pair_fail += 1
        ok_n = pair_ok
        fail_n = pair_fail
        return ok_n, fail_n, last

    if mode in ("nearest_other", "nearest"):
        pool = list(entries)
        mob_only = [m for m, _c in pool]
        code_by_mob = {m: c for m, c in pool}
        for mob, code in pool:
            tgt = _nearest_other(mob, mob_only)
            if tgt is None:
                fail_n += 1
                last = "no nearest other mob"
                continue
            prepare_mob_for_combat(mob, actor_code=code)
            ok, msg = _apply_pair_aggro(
                mob,
                tgt,
                instigator=mob,
                damage_wake=damage_wake,
                cross_hostile=True,
                attacker_code=code,
            )
            last = msg
            if ok:
                ok_n += 1
            else:
                fail_n += 1
        return ok_n, fail_n, last

    return 0, len(entries), f"unknown aggro mode: {mode}"


def _nearest_other(mob: Any, pool: list[Any]) -> Any | None:
    loc = _actor_location(mob)
    best: Any | None = None
    best_d = 1e30
    for other in pool:
        if other is mob:
            continue
        oloc = _actor_location(other)
        if loc is None or oloc is None:
            if best is None:
                best = other
            continue
        d = _dist_sq(loc, oloc)
        if d < best_d:
            best_d = d
            best = other
    return best


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
