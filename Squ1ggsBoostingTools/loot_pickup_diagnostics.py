"""Bounded reflected pickup state; no serial-memory reads or actor mutations."""
import json
import re
from collections import Counter
from pathlib import Path

import unrealsdk


def inspect() -> dict:
    from . import loot_shapes
    from unrealsdk.unreal import WeakPointer, UFunction
    result = {"pinned": len(loot_shapes._pinned_slots),
              "released_held": len(loot_shapes._released_held_pins),
              "held": sum(bool(row.get("hold")) for row in loot_shapes._pinned_slots),
              "cached_serials": sum(str(row.get("serial") or "").startswith("@U") for row in loot_shapes._pinned_slots),
              "functions": [], "properties": [], "pickups": []}
    seen_functions = set()
    seen_properties = set()
    from . import native_pickup_handoff
    control = native_pickup_handoff._control
    if control is not None:
        controlled = control["actor"]()
        from .loot_junk_diagnostics import _read
        result["handoff_actor"] = None if controlled is None else {
            "name": str(controlled), "hidden": bool(controlled.bHidden),
            "identity": _read(int(controlled._get_address()) + 0x798, 5).hex(),
        }
    result["transaction_structs"] = []
    for struct in unrealsdk.find_all("ScriptStruct", False):
        name = str(struct.Name)
        if "transaction" not in name.lower() or len(result["transaction_structs"]) >= 60:
            continue
        result["transaction_structs"].append({
            "name": name, "size": int(struct._get_struct_size()),
            "fields": [{"name": str(prop.Name), "type": type(prop).__name__,
                        "struct": str(prop.Struct) if type(prop).__name__ == "ZStructProperty" else None}
                       for prop in struct._properties()],
        })
    result["spawn_pattern_stores"] = []
    for store in unrealsdk.find_all("NexusConfigStoreSpawnPattern", False)[:3]:
        item = {"object": str(store), "fields": [], "functions": []}
        for parent in store.Class._superfields():
            for prop in parent._properties():
                try:
                    value = getattr(store, str(prop.Name))
                    item["fields"].append({"name": str(prop.Name), "type": type(prop).__name__, "value": str(value)[:16000]})
                except Exception:
                    pass
            for function in parent._fields():
                if isinstance(function, UFunction):
                    item["functions"].append(str(function))
        result["spawn_pattern_stores"].append(item)
    classes = []
    for class_name in ("InventoryPickup", "OakInventoryPickup", "OakPickup", "NexusConfigStoreItemPool"):
        try:
            cls = unrealsdk.find_class(class_name)
        except ValueError:
            continue
        classes.append(cls)
    junk_classes = [cls for cls in unrealsdk.find_all("Class", False)
                    if "junk" in str(cls.Name).lower()][:12]
    result["junk_classes"] = [str(cls) for cls in junk_classes]
    classes.extend(junk_classes)
    inventory_libraries = [cls for cls in unrealsdk.find_all("Class", False)
                           if "library" in str(cls.Name).lower()
                           and any(term in str(cls.Name).lower() for term in ("inventory", "item", "loot", "pickup"))][:18]
    result["inventory_libraries"] = [str(cls) for cls in inventory_libraries]
    classes.extend(inventory_libraries)
    from .dev_tools import _gameplay_pc
    from .item_spawn.pearl_serial_spawn import _SERIAL_INVENTORY_ATTRS
    pc = _gameplay_pc()
    roots = [pc, getattr(pc, "Pawn", None), getattr(pc, "PlayerState", None), getattr(pc, "CheatManager", None)]
    for root in list(roots):
        if root is not None:
            for name in (*_SERIAL_INVENTORY_ATTRS, "BackpackContainer", "CachedInventoryChannel", "CachedGbxInventoryChannel", "StructuredInteractableUserState"):
                try:
                    value = getattr(root, name, None)
                except AttributeError:
                    value = None
                if value is not None and getattr(value, "Class", None) is not None:
                    roots.append(value)
    for root in roots:
        if root is not None:
            classes.append(root.Class)
    result["inventory_roots"] = [str(root) for root in roots if root is not None]
    from .inventory_capacity import get_party_player_states
    result["players"] = []
    for index, name, ps in get_party_player_states():
        state = {"index": index, "name": name, "player_state": str(ps)}
        for field in ("Owner", "PawnPrivate", "BackpackContainer"):
            try:
                value = getattr(ps, field, None)
                if field == "BackpackContainer" and value is not None:
                    state["backpack_max_size"] = str(getattr(value, "MaxSize", None))
                else:
                    state[field] = str(value)
            except Exception as exc:
                state[field + "_error"] = repr(exc)[:256]
        try:
            wrapper = getattr(ps, "BackpackItems", None)
            items = getattr(wrapper, "items", None)
            if items is None:
                items = getattr(wrapper, "Items", None)
            state["backpack_entry_count"] = len(items) if items is not None else None
            if items is not None:
                scanned = min(len(items), 512)
                state["entries_scanned"] = scanned
                state["unequipped_valid_handles"] = sum(
                    int(items[i].InventoryItem.EquipSlot) == -1
                    and int(items[i].InventoryItem.Handle.Handle) >= 0 for i in range(scanned))
                state["slot_groups"] = dict(Counter(
                    f"equip={int(items[i].InventoryItem.EquipSlot)},flags={items[i].InventoryItem.Flags},handle_valid={int(items[i].InventoryItem.Handle.Handle) >= 0}"
                    for i in range(scanned)))
                if scanned:
                    slot = items[0]
                    state["slot_fields"] = [{"name": str(prop.Name), "type": type(prop).__name__}
                                            for prop in slot._type._properties()]
                    inv = getattr(slot, "InventoryItem", None)
                    state["inventory_item_type"] = type(inv).__name__
                    if inv is not None:
                        state["inventory_item_fields"] = [{"name": str(prop.Name), "type": type(prop).__name__}
                                                          for prop in inv._type._properties()]
                        state["item_schema"] = {}
                        for field in ("Item", "Handle"):
                            value = getattr(inv, field, None)
                            if value is not None:
                                state["item_schema"][field] = {"struct": str(value._type),
                                    "fields": [{"name": str(prop.Name), "type": type(prop).__name__}
                                               for prop in value._type._properties()]}
                        state["sample_slot_scalars"] = [
                            {"index": i, "replication_id": int(items[i].ReplicationID),
                             "max_quantity": int(items[i].MaxQuantity),
                             "equip_slot": int(items[i].InventoryItem.EquipSlot),
                             "flags": str(items[i].InventoryItem.Flags)}
                            for i in range(min(scanned, 3))]
        except Exception as exc:
            state["backpack_items_error"] = repr(exc)[:256]
        result["players"].append(state)
    for cls in classes:
        for parent in cls._superfields():
            for function in parent._fields():
                if (not isinstance(function, UFunction) or str(function) in seen_functions
                        or (cls not in inventory_libraries and cls not in junk_classes and not re.search(r"junk|pickup|attract|loot|onused|usedby|serveruse|clientuse|inventory|serial|grant|give|collect|add.*item", str(function.Name), re.I))
                        or len(result["functions"]) >= 200):
                    continue
                seen_functions.add(str(function))
                fields = [{"name": str(prop.Name), "type": type(prop).__name__, "flags": int(prop.PropertyFlags)}
                          for prop in function._properties() if int(prop.PropertyFlags) & 0x80]
                for index, prop in enumerate([prop for prop in function._properties() if int(prop.PropertyFlags) & 0x80]):
                    if type(prop).__name__ == "ZStructProperty":
                        struct = prop.Struct
                        fields[index]["struct"] = str(struct)
                        fields[index]["members"] = [{"name": str(member.Name), "type": type(member).__name__,
                                                     "struct": str(member.Struct) if type(member).__name__ == "ZStructProperty" else None}
                                                    for member in struct._properties()]
                result["functions"].append({"path": str(function), "flags": int(function.FunctionFlags), "fields": fields})
            for prop in parent._properties():
                key = str(parent) + "." + str(prop.Name)
                if key not in seen_properties and re.search(r"junk|pickup|attract|loot|usable|inventory|instigat|owner|interact", str(prop.Name), re.I):
                    seen_properties.add(key)
                    result["properties"].append({"class": str(parent), "name": str(prop.Name), "type": type(prop).__name__})
    actors = {}
    for row in list(loot_shapes._pinned_slots)[:2]:
        reference = row.get("reference")
        actor = reference() if reference is not None else loot_shapes._live_pickup(int(row.get("addr") or 0))
        if actor is not None:
            actors[str(actor)] = WeakPointer(actor)
    world_pickups = [actor for actor in unrealsdk.find_all("InventoryPickup", False)
                     if "Default__" not in str(actor)]
    result["world_pickup_count"] = len(world_pickups)
    for actor in world_pickups[-4:]:
        if "Default__" not in str(actor):
            actors.setdefault(str(actor), WeakPointer(actor))
    for reference in list(actors.values())[:4]:
        actor = reference()
        if actor is None:
            continue
        state = {"actor": str(actor)}
        if "native_interfaces" not in result:
            try:
                from . import loot_native_inspect
                import importlib
                importlib.reload(loot_native_inspect)
                result["native_interfaces"] = loot_native_inspect.inspect(actor)
            except Exception as exc:
                result["native_interfaces"] = {"error": repr(exc)}
        state["native_structs"] = {}
        for field in ("BodyData", "BrainTaskData", "Item"):
            try:
                value = getattr(actor, field)
                if getattr(value, "Class", None) is not None:
                    state["native_structs"][field] = {
                        "object": str(value),
                        "fields": [{"name": str(prop.Name), "type": type(prop).__name__}
                                   for prop in value.Class._properties()],
                        "functions": [str(func) for func in value.Class._fields()
                                      if isinstance(func, UFunction)],
                    }
                    continue
                struct = value._type
                state["native_structs"][field] = {
                    "type": str(struct),
                    "size": int(struct._get_struct_size()),
                    "fields": [{"name": str(prop.Name), "type": type(prop).__name__,
                                "offset": int(prop.Offset_Internal)}
                               for prop in struct._properties()],
                }
            except Exception as exc:
                state["native_structs"][field] = {"error": repr(exc)[:160]}
        state["all_pickup_properties"] = [{"class": str(parent), "name": str(prop.Name),
                                           "type": type(prop).__name__, "offset": int(prop.Offset_Internal)}
                                          for parent in actor.Class._superfields()
                                          if str(parent.Name) in ("InventoryPickup", "InventoryBase")
                                          for prop in parent._properties()]
        try:
            library = unrealsdk.find_class("JunkSystemFunctionLibrary").ClassDefaultObject
            response = library.GetJunkAttachedToActor(Actor=actor, OutJunkIds=[])
            ids = response[1] if isinstance(response, tuple) and len(response) > 1 else []
            from .loot_junk_diagnostics import _read
            state["attached_junk_ids"] = [_read(int(token._get_address()), int(token._type._get_struct_size())).hex()
                                          for token in list(ids)[:4]]
        except Exception as exc:
            state["attached_junk_error"] = repr(exc)[:256]
        for name in ("Owner", "Instigator", "bHidden", "bReplicates", "bOnlyRelevantToOwner",
                     "bNetUseOwnerRelevancy", "NetDormancy", "UsableActorState", "ReplicatedMovement"):
            try:
                state[name] = str(getattr(actor, name))
            except AttributeError:
                pass
        result["pickups"].append(state)
    folder = Path(__file__).parent / "logs"
    folder.mkdir(exist_ok=True)
    (folder / "loot_pickup_diagnostics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
