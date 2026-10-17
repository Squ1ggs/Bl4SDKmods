"""Temporary pickup RPC observation; callbacks never change or block a call."""
from __future__ import annotations
import time
import unrealsdk.hooks as hooks
from unrealsdk.unreal import WeakPointer

_events = []
_installed = []


def _record(phase, obj, args, _ret, function):
    try:
        row = {"at": time.monotonic(), "phase": phase, "function": str(function.func.Name), "controller": str(obj)}
        _events.append(row)
        del _events[:-32]
        usable = getattr(args, "Usable", None)
        if usable is not None:
            reference = WeakPointer(usable)
            target = reference()
            row["usable"] = str(target) if target is not None else None
            row["usable_live"] = target is not None
        for name in ("UseType", "bWasHeld", "bAutoTrash"):
            value = getattr(args, name, None)
            if value is not None:
                row[name] = value if isinstance(value, (bool, int, float)) else str(value)
        junk = getattr(args, "JunkId", None)
        if junk is not None:
            row["junk_type"] = str(junk._type)
            row["junk"] = {str(prop.Name): str(getattr(junk, str(prop.Name)))[:128]
                           for prop in junk._type._properties()
                           if type(prop).__name__ in ("ZIntProperty", "ZInt64Property", "ZUInt32Property", "ZUInt64Property", "ZNameProperty")}
    except Exception as exc:
        if "row" in locals():
            row["error"] = repr(exc)[:256]
    return None


def _pre(obj, args, ret, function):
    return _record("pre", obj, args, ret, function)


def _post(obj, args, ret, function):
    return _record("post", obj, args, ret, function)


def install():
    if _installed:
        return list(_installed)
    for path in ("/Script/OakGame.OakPlayerController:ServerUseObject",
                 "/Script/OakGame.OakPlayerController:ServerUseJunkObject",
                 "/Script/GbxGame.GbxPlayerController:ExecuteInventoryTransactionOnServer",
                 "/Script/GbxGame.GbxPlayerController:ExecuteInventoryTransactionOnClient"):
        for kind, callback in ((hooks.Type.PRE, _pre), (hooks.Type.POST_UNCONDITIONAL, _post)):
            ident = "Squ1ggsBoostingTools.pickup_trace." + path + "." + str(kind)
            hooks.remove_hook(path, kind, ident)
            if hooks.add_hook(path, kind, ident, callback):
                _installed.append((path, str(kind)))
    return list(_installed)


def snapshot():
    remaining = sum(hooks.has_hook(path, typ,
                    "Squ1ggsBoostingTools.pickup_trace." + path + "." + str(typ))
                    for path in ("/Script/OakGame.OakPlayerController:ServerUseObject",
                                 "/Script/OakGame.OakPlayerController:ServerUseJunkObject",
                                 "/Script/GbxGame.GbxPlayerController:ExecuteInventoryTransactionOnServer",
                                 "/Script/GbxGame.GbxPlayerController:ExecuteInventoryTransactionOnClient")
                    for typ in (hooks.Type.PRE, hooks.Type.POST_UNCONDITIONAL))
    return {"installed": list(_installed), "remaining_hooks": remaining, "events": list(_events)}


def remove():
    # Remove every identifier owned by this observer, including hooks left by
    # an earlier reload whose add_hook returned False (already installed).
    for path in ("/Script/OakGame.OakPlayerController:ServerUseObject",
                 "/Script/OakGame.OakPlayerController:ServerUseJunkObject",
                 "/Script/GbxGame.GbxPlayerController:ExecuteInventoryTransactionOnServer",
                 "/Script/GbxGame.GbxPlayerController:ExecuteInventoryTransactionOnClient"):
        for typ in (hooks.Type.PRE, hooks.Type.POST_UNCONDITIONAL):
            ident = "Squ1ggsBoostingTools.pickup_trace." + path + "." + str(typ)
            hooks.remove_hook(path, typ, ident)
    _installed.clear()
