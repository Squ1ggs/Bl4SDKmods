"""Weak references to detected tool spawns, including passive NPCs."""
from __future__ import annotations

from typing import Any
from unrealsdk.unreal import WeakPointer

_spawns: dict[str, tuple[Any, str]] = {}


def register(actor: Any, code: str) -> None:
    if actor is None:
        return
    try:
        import unrealsdk
        player_keys = {str(pawn) for pc in unrealsdk.find_all("OakPlayerController", False)
                       if (pawn := getattr(pc, "Pawn", None)) is not None}
    except Exception:
        return
    if player_keys and str(actor) not in player_keys:
        _spawns[str(actor)] = (WeakPointer(actor), str(code))


def live() -> dict[str, Any]:
    return {key: actor for key, (reference, _code) in list(_spawns.items())
            if (actor := reference()) is not None}
