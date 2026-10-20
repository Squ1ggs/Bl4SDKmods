from __future__ import annotations
from typing import Any
import re
import unrealsdk
from unrealsdk import logging

def _get_driven_vehicle_actor_from_pawn(pawn: Any) -> Any | None:
    if pawn is None:
        return None
    try:
        vdc = getattr(pawn, "VehicleDriverComponent", None)
        if vdc is None:
            for attr in ("VehicleDriver", "GbxVehicleDriverComponent", "OakVehicleDriverComponent"):
                vdc = getattr(pawn, attr, None)
                if vdc is not None:
                    break
        if vdc is None:
            if _looks_like_vehicle_actor(pawn):
                return pawn
            return None
        vds = getattr(vdc, "VehicleDriverState", None) or getattr(vdc, "DriverState", None)
        if vds is None:
            vds = vdc
        for attr in ("DrivenVehicle", "CurrentVehicle", "VehicleActor", "OccupiedVehicle", "MountedVehicle"):
            dv = getattr(vds, attr, None)
            if dv is not None:
                return dv
        for attr in ("DrivenVehicle", "CurrentVehicle", "VehicleActor", "OccupiedVehicle", "MountedVehicle"):
            dv = getattr(pawn, attr, None)
            if dv is not None:
                return dv
        if _looks_like_vehicle_actor(pawn):
            return pawn
        return None
    except Exception:
        if _looks_like_vehicle_actor(pawn):
            return pawn
        return None

def _resolve_oak_vehicle_movement_from_vehicle_actor(vehicle: Any) -> tuple[str, Any] | None:
    if vehicle is None:
        return None
    for attr in (
        "OakVehicleMovement",
        "VehicleMovement",
        "VehicleMovementComp",
        "ChaosVehicleMovement",
        "WheeledVehicleMovement",
    ):
        try:
            comp = getattr(vehicle, attr, None)
        except Exception:
            continue
        if comp is not None:
            return (f"DrivenVehicle.{attr}", comp)
    return None

def _object_identity(obj: Any) -> int:
    if obj is None:
        return 0
    try:
        return int(getattr(obj, "_get_address", lambda: 0)() or 0)
    except Exception:
        return id(obj)

def _object_type_text(obj: Any) -> str:
    if obj is None:
        return ""
    bits: list[str] = []
    for value in (
        getattr(obj, "Name", ""),
        getattr(getattr(obj, "Class", None), "Name", ""),
    ):
        try:
            if value:
                bits.append(str(value))
        except Exception:
            pass
    try:
        bits.append(repr(obj)[:240])
    except Exception:
        pass
    return " ".join(bits).lower()

def _resolved_def_instance(value: Any) -> Any | None:
    if value is None:
        return None
    for name in ("instance", "_experimental_instance"):
        try:
            instance = getattr(value, name, None)
        except Exception:
            instance = None
        if instance is not None:
            return instance
    return value

def _vehicle_definition_instances(vehicle: Any, *extra_roots: Any) -> list[tuple[str, Any]]:
    """Resolve the live OakVehicleDef behind the vehicle's FGbxDefPtr."""
    candidates: list[tuple[str, Any]] = []
    roots = (vehicle, *extra_roots)
    for root_index, root in enumerate(roots):
        if root is None:
            continue
        for path in (
            "VehicleDef",
            "OakVehicleMovement.VehicleDef",
            "VehicleMovementComp.VehicleDef",
            "VehicleMovementComponent.VehicleDef",
            "GbxActorData.GbxActorDef",
            "ActorData.GbxActorDef",
            "GbxActorDef",
            "ActorDef",
        ):
            value = _resolve_relative(root, path)
            instance = _resolved_def_instance(value)
            if instance is not None:
                prefix = "vehicle" if root_index == 0 else f"root[{root_index}]"
                candidates.append((f"{prefix}.{path}", instance))
    unique: list[tuple[str, Any]] = []
    seen: set[int] = set()
    for path, instance in candidates:
        ident = _object_identity(instance)
        if ident in seen:
            continue
        seen.add(ident)
        unique.append((path, instance))
    return unique

def _looks_like_vehicle_actor(obj: Any) -> bool:
    text = _object_type_text(obj)
    return (
        "oakvehicle" in text
        or "personalvehicle" in text
        or "bpvehicle" in text
        or "bp_vehicle" in text
    ) and "weapon" not in text and "projectile" not in text

def _resolve_relative(root: Any, path: str) -> Any | None:
    obj = root
    for part in path.split("."):
        try:
            obj = getattr(obj, part, None)
        except Exception:
            return None
        if obj is None:
            return None
    return obj

def _make_oak_vehicle_def_ptr(def_id: str) -> Any | None:
    name = str(def_id or "").strip()
    if not name:
        return None
    if name.lower().startswith("pv_"):
        name = "PV_" + name[3:]
    elif not name.startswith("PV_"):
        name = f"PV_{name}"
    try:
        from unrealsdk.unreal import FGbxDefPtr  # type: ignore[import-not-found]

        ptr = FGbxDefPtr(name, type="OakVehicleDef")
        inst = getattr(ptr, "_experimental_instance", None)
        if inst is not None:
            return inst
        return ptr
    except Exception:
        pass
    struct_names = (
        "FGbxDefPtr",
        "GbxDefPtr",
        "/Script/GbxGame.FGbxDefPtr",
        "/Script/OakGame.FGbxDefPtr",
    )
    kwarg_sets: tuple[dict[str, Any], ...] = (
        {"_experimental_name": name, "_experimental_ref": "OakVehicleDef"},
        {"name": name, "ref": "OakVehicleDef"},
        {"_experimental_name": name},
        {"name": name},
    )
    for struct_name in struct_names:
        for kwargs in kwarg_sets:
            try:
                return unrealsdk.make_struct(struct_name, **kwargs)
            except Exception:
                continue
        try:
            ws = unrealsdk.make_struct(struct_name)
            for na, ra in (("name", "ref"), ("_experimental_name", "_experimental_ref")):
                try:
                    setattr(ws, na, name)
                    setattr(ws, ra, "OakVehicleDef")
                    return ws
                except Exception:
                    continue
        except Exception:
            continue
    return None

def _try_call_ue_variants(
    obj: Any, method_names: tuple[str, ...], arg_sets: tuple[tuple[Any, ...], ...]
) -> tuple[bool, str]:
    last_err = ""
    for method_name in method_names:
        try:
            fn = getattr(obj, method_name, None)
        except Exception:
            fn = None
        if not callable(fn):
            continue
        for args in arg_sets:
            try:
                fn(*args)
                return True, f"{method_name}{args!r}"
            except TypeError:
                continue
            except Exception as exc:
                last_err = f"{method_name}{args!r}: {exc}"
    return False, last_err or "no callable method matched"

def _try_execute_console_line(pc: Any, line: str) -> tuple[bool, str]:
    payload = str(line or "").strip()
    if not payload:
        return False, "empty console line"
    for meth in ("ConsoleCommand", "ClientConsoleCommand"):
        try:
            fn = getattr(pc, meth, None)
        except Exception:
            fn = None
        if not callable(fn):
            continue
        for args in ((payload,), (payload, True)):
            try:
                fn(*args)
                return True, f"{meth}({payload!r})"
            except TypeError:
                continue
            except Exception as exc:
                return False, str(exc)
    return False, "ConsoleCommand unavailable"

def _personal_vehicle_state_roots(pc: Any) -> list[Any]:
    roots: list[Any] = []
    seen: set[int] = set()

    def add(obj: Any) -> None:
        if obj is None:
            return
        oid = _object_identity(obj)
        if oid and oid in seen:
            return
        if oid:
            seen.add(oid)
        roots.append(obj)

    add(pc)
    for attr in ("PlayerState", "OakPlayerState"):
        try:
            add(getattr(pc, attr, None))
        except Exception:
            continue
    for root in list(roots):
        try:
            add(getattr(root, "PersonalVehicleState", None))
        except Exception:
            pass
    return roots

def _write_personal_vehicle_def(pc: Any, vehicle_def: Any, def_id: str) -> tuple[bool, str]:
    for root in _personal_vehicle_state_roots(pc):
        for attr in ("VehicleDef", "PersonalVehicleDef", "SelectedVehicleDef"):
            try:
                if hasattr(root, attr):
                    setattr(root, attr, vehicle_def)
                    return True, f"{attr} on {type(root).__name__}"
            except Exception as exc:
                return False, str(exc)
        for attr in ("PersonalVehicleState",):
            try:
                state = getattr(root, attr, None)
            except Exception:
                state = None
            if state is None:
                continue
            try:
                setattr(state, "VehicleDef", vehicle_def)
                return True, f"PersonalVehicleState.VehicleDef on {type(root).__name__}"
            except Exception:
                pass
    ptr = _make_oak_vehicle_def_ptr(def_id)
    arg_sets: tuple[tuple[Any, ...], ...] = ()
    if ptr is not None:
        arg_sets = ((ptr,), (def_id,), (ptr, True), (def_id, True))
    ok, how = _try_call_ue_variants(
        pc,
        ("ServerSetPersonalVehicleDef", "SetPersonalVehicleDef", "ClientSetPersonalVehicleDef"),
        arg_sets,
    )
    return ok, how

def _request_personal_vehicle(pc: Any) -> tuple[bool, str]:
    arg_sets: tuple[tuple[Any, ...], ...] = ((), (True,), (False,))
    return _try_call_ue_variants(
        pc,
        (
            "ServerRequestPersonalVehicle",
            "RequestPersonalVehicle",
            "ClientRequestPersonalVehicle",
            "SummonPersonalVehicle",
        ),
        arg_sets,
    )

def _unlock_token_for_vehicle(def_id: str, entry: dict[str, Any] | None = None) -> str | None:
    if entry is not None:
        token = str(entry.get("unlock") or "").strip()
        if token:
            return token
    stem = def_id[3:] if def_id.startswith("PV_") else def_id
    if stem.lower() == "shatterlandv1":
        return "Unlockable_Vehicles.ShatterlandV1"
    return f"Unlockable_Vehicles.{stem}"

def _try_unlock_vehicle_for_spawn(pc: Any, def_id: str, entry: dict[str, Any] | None = None) -> tuple[bool, str]:
    token = _unlock_token_for_vehicle(def_id, entry)
    if not token:
        return False, "no unlock token"
    return _try_unlock_unlockable(pc, token)

def _get_player_state(pc: Any) -> Any | None:
    for attr in ("PlayerState", "OakPlayerState"):
        try:
            ps = getattr(pc, attr, None)
            if ps is not None:
                return ps
        except Exception:
            continue
    return None

def _try_unlock_unlockable(pc: Any, token: str) -> tuple[bool, str]:
    ps = _get_player_state(pc)
    if ps is None:
        return False, "no PlayerState"
    try:
        import ultra_local_menu as ulm

        inv = getattr(ulm, "_invoke_client_unlock_unlockable", None)
        if callable(inv):
            ok, err, tag = inv(ps, token)
            if ok:
                return True, tag or token
            last = err or "ulm unlock failed"
        else:
            last = "ulm unlock helper missing"
    except Exception as exc:
        last = str(exc)
    fn = getattr(ps, "ClientUnlockUnlockable", None)
    if not callable(fn):
        return False, last
    candidates: list[Any] = []
    try:
        from unrealsdk.unreal import FGbxDefPtr  # type: ignore[import-not-found]

        ptr = FGbxDefPtr(token, type="UnlockableEntryDef")
        inst = getattr(ptr, "_experimental_instance", None)
        if inst is not None:
            candidates.extend([inst, ptr])
    except Exception:
        pass
    candidates.append(token)
    if "." in token:
        ledger, entry = token.split(".", 1)
        for lv, ev in ((ledger, entry), (f"/Script/OakGame.{ledger}", entry)):
            for args in ((lv, ev), (ev, lv)):
                try:
                    fn(*args)
                    return True, f"ClientUnlockUnlockable({lv},{ev})"
                except Exception as exc:
                    last = str(exc)
    for arg in candidates:
        try:
            fn(arg)
            return True, f"ClientUnlockUnlockable({token})"
        except TypeError:
            continue
        except Exception as exc:
            last = str(exc)
    return False, last

def _spawn_personal_vehicle_for_pc(
    pc: Any,
    def_id: str,
    *,
    probe: bool = False,
    entry: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    notes: list[str] = []
    if not probe:
        unlock_ok, unlock_detail = _try_unlock_vehicle_for_spawn(pc, def_id, entry)
        if unlock_ok:
            notes.append(f"unlock:{unlock_detail}")
    ptr = _make_oak_vehicle_def_ptr(def_id)
    if ptr is None:
        return False, f"could not build OakVehicleDef ptr for {def_id}"
    wrote, write_how = _write_personal_vehicle_def(pc, ptr, def_id)
    if wrote:
        notes.append(write_how)
    requested, req_how = _request_personal_vehicle(pc)
    if requested:
        notes.append(req_how)
    if probe:
        return wrote or requested, " | ".join(notes) if notes else "no native summon methods accepted args"
    if wrote and requested:
        return True, " | ".join(notes)
    for line in (
        f"oak_spawn {def_id}",
        f"oak_spawn {def_id[3:]}",
        f"spawnvehicle {def_id}",
        f"summonvehicle {def_id}",
    ):
        ok, how = _try_execute_console_line(pc, line)
        if ok:
            return True, how
    if notes:
        return wrote or requested, "partial: " + " | ".join(notes)
    return False, "summon failed — try vehicle_move_spawn_probe " + def_id[3:]


def _resolve_vehicle_spawn_token(token):
    from .vehicle_catalog import HOST_VEHICLE_CHOICES
    return next(({'id': key, 'label': label} for key, label, _ in HOST_VEHICLE_CHOICES if token == key), None)
