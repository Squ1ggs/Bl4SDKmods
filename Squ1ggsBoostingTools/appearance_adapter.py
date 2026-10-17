"""EXE adapter for the same appearance-only service used by the standalone mod."""
from __future__ import annotations
from .native_appearance.runtime import CONTROLLER


def controller():
    CONTROLLER.acquire("sqbt")
    return CONTROLLER


def _owner(ctrl, payload):
    if str(payload.get("scope") or "local") != "local":
        raise RuntimeError("Lobby-wide replication is not validated; use a local appearance change.")
    targets = ctrl._targets()
    if payload.get("appearance_target") != "selected":
        if "self" not in targets:
            raise RuntimeError("Load your character in-world first.")
        return "self"
    from .backend_actions import get_target_player_index, _resolve_pc
    raw = payload.get("player_index")
    index = get_target_player_index() if raw is None or raw == "" else int(raw)
    if index < 0:
        raise RuntimeError("Select exactly one lobby player for the appearance change.")
    pc, error = _resolve_pc(index)
    pawn = getattr(pc, "Pawn", None)
    owner = next((key for key, target in targets.items() if str(target) == str(pawn)), None)
    if owner is None:
        raise RuntimeError(error or "The selected player has no live character.")
    if owner != "self" and not pawn.HasAuthority():
        raise RuntimeError("Only the host can change another lobby player's appearance.")
    return owner


def _options(payload):
    def flag(key, default):
        value = payload.get(key, default)
        return value is True or str(value).casefold() in ("true", "1", "yes", "on")
    return {"keep_on_respawn": flag("keep_on_respawn", True),
            "follow_player_pose": flag("follow_player_pose", False),
            "hide_original_for_lobby": flag("hide_original_for_lobby", False)}


def apply(payload=None):
    payload = payload or {}
    codes = payload.get("codes")
    if codes is None:
        codes = [payload.get("code")]
    if not isinstance(codes, list) or len(codes) != 1 or not isinstance(codes[0], str):
        raise RuntimeError("Select exactly one native BL4 character.")
    code = codes[0].strip()
    ctrl = controller()
    if not any(row["code"] == code for row in ctrl.catalog):
        raise RuntimeError("That character is not part of the native BL4 catalog.")
    owner = _owner(ctrl, payload)
    accepted = ctrl.request("apply", model=code, owner=owner, options=_options(payload))
    return {"ok": accepted, "message": ctrl.status, "appearance": ctrl.snapshot(owner)}


def apply_looked_at(payload=None):
    from .dev_tools import _selected_debug_cam_actor
    from .native_appearance import native_helpers as native
    from unrealsdk.unreal import WeakPointer
    payload = payload or {}
    ctrl = controller()
    actor = _selected_debug_cam_actor()
    if actor is None or any(str(actor) == str(pawn) for pawn in ctrl._targets().values()):
        raise RuntimeError("Look at a native NPC or enemy in freecam first.")
    definition = getattr(getattr(actor, "GbxActorData", None), "GbxActorDef", None)
    code = str(getattr(definition, "_experimental_name", ""))
    if not any(row["code"] == code for row in ctrl.catalog) or not ctrl._ready(actor):
        raise RuntimeError("The looked-at actor has no usable native character model.")
    # Clone the looked-at actor; never wear, detach or later destroy the actual
    # map NPC or somebody else's player pawn.
    ctrl.templates[code] = WeakPointer(actor)
    return apply({**payload, "codes": [code]})


def preview(payload=None):
    payload = payload or {}
    codes = payload.get("codes")
    if not isinstance(codes, list) or len(codes) != 1:
        raise RuntimeError("Select exactly one native BL4 character to preview.")
    ctrl = controller()
    if not any(row["code"] == codes[0] for row in ctrl.catalog):
        raise RuntimeError("That character is not part of the native BL4 catalog.")
    ctrl._targets()
    accepted = ctrl.request("preview", model=codes[0])
    return {"ok": accepted, "message": ctrl.status, "appearance": ctrl.snapshot()}


def clear_previews(payload=None):
    ctrl = controller()
    accepted = ctrl.request("clear")
    return {"ok": accepted, "message": ctrl.status, "appearance": ctrl.snapshot()}


def restore(payload=None):
    payload = payload or {}
    ctrl = controller()
    action = "restore_all" if payload.get("appearance_target") == "all" else "restore"
    owner = "self" if action == "restore_all" else _owner(ctrl, payload)
    accepted = ctrl.request(action, owner=owner)
    return {"ok": accepted, "message": ctrl.status, "appearance": ctrl.snapshot(owner)}


def status():
    return CONTROLLER.snapshot()


def is_invisible():
    return CONTROLLER.invisible


def invisible(payload=None):
    ctrl = controller()
    value = (payload or {}).get("enabled", False)
    enabled = value is True or str(value).casefold() in ("true", "1", "yes", "on")
    ctrl.set_invisible(enabled)
    return {"ok": True, "message": "Invisible body ON." if enabled else "Invisible body OFF.",
            "character_invisible": ctrl.invisible}


def rendered_mesh(pawn):
    from .native_appearance.native_helpers import _actor_mesh
    for state in list(CONTROLLER.worn.values()):
        current = state.pawn()
        if current is not None and str(current) == str(pawn):
            source = state.source()
            return _actor_mesh(source) if source is not None else None
    return None


def runtime_tick():
    # Appearance itself has one shared hook. This is only the existing SQBT
    # model-height camera feature, which is separate from attachment ownership.
    from .dev_tools import _tick_model_camera_height
    _tick_model_camera_height()


def release():
    CONTROLLER.release("sqbt")


def catalog(payload=None):
    # /catalog is also served from the HTTP thread: only metadata/cached rows
    # belong here. Hook registration and UObject operations stay on game ticks.
    ctrl = CONTROLLER
    if not ctrl.catalog:
        ctrl.load_catalog()
    payload = payload or {}
    search = str(payload.get("search") or "").casefold().split()
    group = str(payload.get("group") or "All")
    rows = [{**row, "code": row["key"], "display_name": row["name"], "selectable": True,
             "notes": row["availability"].replace("_", " ")}
            for row in ctrl.choices()
            if (group == "All" or row["group"] == group)
            and all(token in (row["name"] + " " + row["key"] + " " + row["group"]).casefold() for token in search)]
    return {"ok": True, "rows": rows, "total": len(rows),
            "groups": ["All", *sorted({row["group"] for row in ctrl.choices()})],
            "message": "Native BL4 catalog; selected content loads on demand. Missing content reports a failure without hiding your original body."}
