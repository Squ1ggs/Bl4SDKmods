"""Probe Grassroots Campaigner + side-mission challenge state (console / Maybe tab).

Token: Challenges_Achievements_24_missions_side

NCS truth (not COS / IncrementChallenge):
  - bUseCustomMissionList + MissionDefs (98 side/micro missions)
  - ChallengeTiers GoalValue: 10, 25, 50, 75, 98  → card \"1/10\" = first tier
  - AssociatedStat: stats.achievements.24_missions_side
  - COS bits / GetChallengeProgress can disagree with the card
"""

from __future__ import annotations

from typing import Any

from mods_base import command, get_pc
from unrealsdk import logging

_LOG = "[SQBT Grassroots probe]"
_GRASSROOTS_TOKEN = "Challenges_Achievements_24_missions_side"
_SIDE_MISC_TOKEN = "Challenge_Misc_World_CompleteSideMissions"
_RELATED_NEEDLES: tuple[str, ...] = (
    "missions_side",
    "sidemission",
    "side_mission",
    "completesidemissions",
    "grassroots",
    "campaigner",
    "24_missions",
    "achievements",
)
_SURFACE_CLASSES: tuple[str, ...] = (
    "MissionProgressRole",
    "OakMissionProgressRole",
    "GbxMissionProgressComponent",
    "OakUIDataCollector_Mission",
    "OakChallengeProgressRoleCharacter",
    "OakChallengeProgressRole",
    "OakChallengeManager",
    "OakProfileProgressVault",
)


def _note(msg: str) -> None:
    line = f"{_LOG} {msg}"
    logging.info(line)
    try:
        from . import runtime_log

        runtime_log.note(f"grassroots_probe: {msg}")
    except Exception:
        pass


def _safe(obj: Any, attr: str, default: Any = None) -> Any:
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


def _pc_for_index(player_index: int | None) -> Any | None:
    try:
        from .dev_tools import _pc_for_party_index

        pc, _err = _pc_for_party_index(player_index)
        if pc is not None:
            return pc
    except Exception:
        pass
    try:
        return get_pc()
    except Exception:
        return None


def _load_mission_bundle() -> dict[str, Any]:
    try:
        from .data_files import read_data_json

        raw = read_data_json("grassroots_missions.json")
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _catalog_goal(token: str) -> int | None:
    try:
        from .data_files import read_data_json

        raw = read_data_json("challenge_catalog.json")
        rows = raw.get("challenges") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            return None
        want = str(token or "").casefold()
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("token") or "").casefold() == want:
                return max(1, int(row.get("goal") or 1))
    except Exception:
        return None
    return None


def _progress_blob(pc: Any, token: str) -> dict[str, Any]:
    from .challenge_increment import (
        _handles_for_token,
        _read_complete,
        _read_progress,
        challenge_already_complete,
    )

    out: dict[str, Any] = {
        "token": token,
        "catalog_goal": _catalog_goal(token),
        "already_complete": False,
        "handles": [],
        "progress": [],
        "complete_flags": [],
    }
    try:
        out["already_complete"] = bool(challenge_already_complete(pc, token))
    except Exception as ex:
        out["already_complete_err"] = repr(ex)
    try:
        handles = list(_handles_for_token(token) or [])
    except Exception as ex:
        out["handles_err"] = repr(ex)
        handles = []
    for handle in handles[:4]:
        out["handles"].append(repr(handle)[:120])
        try:
            out["progress"].append(_read_progress(pc, handle))
        except Exception as ex:
            out["progress"].append(f"err:{ex!r}")
        try:
            out["complete_flags"].append(_read_complete(pc, handle))
        except Exception as ex:
            out["complete_flags"].append(f"err:{ex!r}")
    return out


def _cos_row_dump(pc: Any, token: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    ps = _safe(pc, "PlayerState")
    cos = _safe(ps, "ChallengeObjectiveStates") if ps is not None else None
    if cos is None:
        return hits
    try:
        from .challenge_objective_state import _identifier_text, _identifier_variants

        variants = {v.casefold() for v in _identifier_variants(token)}
    except Exception:
        variants = {str(token).casefold()}
    try:
        rows = list(cos)
    except Exception as ex:
        return [{"err": repr(ex)}]
    for index, row in enumerate(rows):
        try:
            ident = _identifier_text(getattr(row, "ChallengeIdentifier", None))
        except Exception:
            ident = ""
        if ident.casefold() not in variants and not any(n in ident.casefold() for n in _RELATED_NEEDLES):
            continue
        blob: dict[str, Any] = {"index": index, "identifier": ident[:160]}
        try:
            completed = getattr(row, "CompletedObjectives", None)
            items = getattr(completed, "items", None) or getattr(completed, "Items", None)
            if items is not None:
                sample = []
                for item in list(items)[:6]:
                    if isinstance(item, int):
                        sample.append(hex(item & 0xFFFFFFFF))
                    else:
                        bf = getattr(item, "BitField", None)
                        sample.append(hex(int(bf) & 0xFFFFFFFF) if isinstance(bf, int) else repr(item)[:40])
                blob["completed_bits"] = sample
        except Exception as ex:
            blob["completed_err"] = repr(ex)
        hits.append(blob)
        if len(hits) >= 8:
            break
    return hits


def _scan_cos_tokens(pc: Any) -> list[str]:
    hits: list[str] = []
    ps = _safe(pc, "PlayerState")
    cos = _safe(ps, "ChallengeObjectiveStates") if ps is not None else None
    if cos is None:
        return hits
    try:
        from .challenge_objective_state import _identifier_text

        for key in list(cos)[:4000]:
            try:
                text = _identifier_text(getattr(key, "ChallengeIdentifier", None)) or str(key)
            except Exception:
                text = str(key)
            low = text.casefold()
            if any(n in low for n in _RELATED_NEEDLES):
                hits.append(text[:160])
                if len(hits) >= 40:
                    break
    except Exception as ex:
        hits.append(f"<scan_err {ex!r}>")
    return hits


def _interesting_names(obj: Any, *, limit: int = 80) -> list[str]:
    names: list[str] = []
    try:
        fields = getattr(obj, "_fields", None)
        if callable(fields):
            for field in fields():
                try:
                    names.append(str(getattr(field, "Name", "") or field))
                except Exception:
                    continue
    except Exception:
        pass
    if not names:
        try:
            for name in dir(obj):
                if name.startswith("_"):
                    continue
                names.append(str(name))
        except Exception:
            return []
    out: list[str] = []
    for name in names:
        low = name.casefold()
        if any(
            n in low
            for n in (
                "mission",
                "quest",
                "side",
                "stat",
                "achievement",
                "challenge",
                "progress",
                "complete",
                "objective",
                "tier",
            )
        ):
            out.append(name)
            if len(out) >= limit:
                break
    return out


def _surface_dump(pc: Any) -> list[dict[str, Any]]:
    """Live Mission/Challenge/Stat surfaces that may own the 1/10 counter."""
    import unrealsdk

    rows: list[dict[str, Any]] = []
    roots: list[tuple[str, Any]] = [("pc", pc), ("ps", _safe(pc, "PlayerState"))]
    for cls in _SURFACE_CLASSES:
        try:
            batch = list(unrealsdk.find_all(cls, False) or [])
        except Exception:
            batch = []
        for obj in batch[:6]:
            if obj is None:
                continue
            roots.append((f"{cls}:{_safe(obj, 'Name', '?')}", obj))
    seen: set[int] = set()
    for label, obj in roots:
        if obj is None:
            continue
        try:
            oid = int(obj._get_address() or 0)
        except Exception:
            oid = id(obj)
        if oid in seen or oid <= 0:
            continue
        seen.add(oid)
        names = _interesting_names(obj)
        sample: dict[str, str] = {}
        for name in names[:16]:
            low_name = name.casefold()
            # Skip huge arrays that flood the log / tempt Live Editor deep walks.
            if any(
                bad in low_name
                for bad in (
                    "challengeobjectivestates",
                    "replicatedchallenge",
                    "inventory",
                    "backpack",
                )
            ):
                continue
            try:
                val = getattr(obj, name, None)
            except Exception:
                continue
            if callable(val):
                continue
            try:
                text = repr(val)
            except Exception:
                continue
            if len(text) > 120:
                text = text[:120] + "…"
            if any(n in low_name for n in ("stat", "mission", "progress", "complete", "tier")):
                sample[name] = text
        rows.append(
            {
                "label": str(label)[:120],
                "class": type(obj).__name__,
                "interesting_fields": names[:24],
                "sample": sample,
            }
        )
        if len(rows) >= 24:
            break
    return rows


def _mission_name_hits(mission_defs: list[str]) -> dict[str, Any]:
    """Best-effort: how many Grassroots MissionDefs appear as live object names."""
    import unrealsdk

    want = {str(m).casefold() for m in mission_defs if m}
    found: list[str] = []
    scanned = 0
    for cls in ("OakMission", "GbxMission", "Mission", "OakMissionInstance"):
        try:
            batch = list(unrealsdk.find_all(cls, False) or [])
        except Exception:
            batch = []
        for obj in batch[:800]:
            scanned += 1
            name = str(_safe(obj, "Name", "") or "")
            low = name.casefold()
            if low in want or any(w in low for w in list(want)[:20]):
                found.append(name[:120])
                if len(found) >= 40:
                    break
        if len(found) >= 40:
            break
    return {"scanned": scanned, "name_hits": found, "hit_count": len(found)}


def _tier_for_progress(progress: int, tiers: list[int]) -> dict[str, Any]:
    ordered = sorted(int(t) for t in tiers if int(t) > 0)
    if not ordered:
        return {"progress": progress, "ui_hint": f"{progress}/?"}
    for goal in ordered:
        if progress < goal:
            return {
                "progress": progress,
                "current_tier_goal": goal,
                "ui_hint": f"{progress}/{goal}",
                "final_goal": ordered[-1],
                "all_tiers": ordered,
            }
    return {
        "progress": progress,
        "current_tier_goal": ordered[-1],
        "ui_hint": f"{progress}/{ordered[-1]}",
        "final_goal": ordered[-1],
        "all_tiers": ordered,
        "complete": True,
    }


def probe_grassroots_campaigner(*, player_index: int | None = None) -> dict[str, Any]:
    """Dump Grassroots + mission-list / tier / AssociatedStat surfaces."""
    pc = _pc_for_index(player_index)
    bundle = _load_mission_bundle()
    mission_defs = [str(x) for x in (bundle.get("mission_defs") or []) if str(x).strip()]
    tiers = [int(t.get("goal") or 0) for t in (bundle.get("challenge_tiers") or []) if isinstance(t, dict)]
    if not tiers:
        tiers = [10, 25, 50, 75, 98]
    report: dict[str, Any] = {
        "ok": pc is not None,
        "token": _GRASSROOTS_TOKEN,
        "player_index": player_index,
        "pc": str(_safe(pc, "Name", "?")) if pc is not None else None,
        "associated_stat": bundle.get("associated_stat") or "stats.achievements.24_missions_side",
        "mission_def_count": len(mission_defs),
        "challenge_tiers": tiers,
        "tier_explain": (
            "In-game card X/Y uses ChallengeTiers (first Y=10), not catalog goal 98. "
            "1/10 means one listed side/micro mission counted toward the first reward tier."
        ),
    }
    if pc is None:
        report["message"] = "No PlayerController for probe."
        _note(report["message"])
        return report

    report["grassroots"] = _progress_blob(pc, _GRASSROOTS_TOKEN)
    report["side_misc"] = _progress_blob(pc, _SIDE_MISC_TOKEN)
    g = report["grassroots"]
    prog_vals = [p for p in (g.get("progress") or []) if isinstance(p, (int, float))]
    # UI can show 1/10 while GetChallengeProgress still returns 0 — treat max known as card progress.
    card_progress = int(max(prog_vals) if prog_vals else 0)
    report["tier_status"] = _tier_for_progress(card_progress, tiers)
    report["cos_side_hits"] = _scan_cos_tokens(pc)
    report["cos_row_dump"] = _cos_row_dump(pc, _GRASSROOTS_TOKEN)
    report["surfaces"] = _surface_dump(pc)
    report["mission_live"] = _mission_name_hits(mission_defs)
    report["mission_defs_sample"] = mission_defs[:8]

    _note(
        f"pc={report['pc']} goal={g.get('catalog_goal')} lib_progress={g.get('progress')!r} "
        f"complete={g.get('complete_flags')!r} tier={report['tier_status'].get('ui_hint')} "
        f"missions={len(mission_defs)} assoc={report['associated_stat']}"
    )
    _note(
        f"CompleteSideMissions progress={report['side_misc'].get('progress')!r} "
        f"complete={report['side_misc'].get('complete_flags')!r}"
    )
    _note(f"COS side hits ({len(report['cos_side_hits'])}): {report['cos_side_hits'][:8]}")
    _note(f"COS row dump: {report['cos_row_dump'][:2]!r}"[:400])
    _note(
        f"surfaces ({len(report['surfaces'])}): "
        + ", ".join(str(s.get('label')) for s in report['surfaces'][:8])
    )
    for surf in report["surfaces"][:6]:
        if surf.get("sample"):
            _note(f"surface sample {surf.get('label')}: {surf.get('sample')!r}"[:350])
    _note(
        f"mission live hits={report['mission_live'].get('hit_count')} "
        f"scanned={report['mission_live'].get('scanned')} "
        f"sample={report['mission_live'].get('name_hits', [])[:6]!r}"
    )
    report["diagnosis"] = (
        "Grassroots is a custom MissionDefs list (98) + AssociatedStat "
        f"{report['associated_stat']}. Card 1/10 is tier GoalValue=10, not a broken 10-goal. "
        "IncrementChallenge/COS cannot finish it — need mission completes (or a stat write API). "
        "Dump MissionProgressRole / OakChallengeProgressRoleCharacter / stat owner next."
    )
    report["message"] = report["diagnosis"]
    _note(report["diagnosis"])
    return report


@command(
    "sqbt_probe_grassroots",
    description="Probe Grassroots Campaigner (mission-list tiers + AssociatedStat surfaces).",
)
def _cmd_probe_grassroots(_args: object) -> None:
    del _args
    probe_grassroots_campaigner(player_index=None)
