"""Game facts (``FactsBlueprintLibrary``) — mission status and global values.

Facts are shared host-world state: the owner PC only picks the fact store, so the
host PC is used unless a caller needs a specific player's context.
"""

from __future__ import annotations

from typing import Any

import unrealsdk

_LIB_PATH = "/Script/GbxGame.Default__FactsBlueprintLibrary"
_lib: Any = None


def _facts() -> Any:
    global _lib
    if _lib is None:
        _lib = unrealsdk.find_object("FactsBlueprintLibrary", _LIB_PATH)
    if _lib is None:
        raise RuntimeError("FactsBlueprintLibrary is unavailable")
    return _lib


def host_pc() -> Any:
    from mods_base import get_pc

    pc = get_pc()
    if pc is None or getattr(pc, "PlayerState", None) is None:
        raise RuntimeError("No host player controller — load into the world first")
    return pc


def read_fact(address: str, owner: Any = None) -> tuple[str, int]:
    """Return (name value casefolded, int value)."""
    out = _facts().ReadFact(
        OwnerContext=owner if owner is not None else host_pc(),
        AddressString=address,
        AsName="None",
        AsInt=0,
        AsBool=False,
    )
    return str(out[1]).casefold(), int(out[2])


def write_name_fact(address: str, value: str, owner: Any = None) -> None:
    _facts().WriteFact(
        OwnerContext=owner if owner is not None else host_pc(),
        AddressString=address,
        AsName=value,
        AsInt=0,
        AsBool=False,
    )


def write_int_fact(address: str, value: int, owner: Any = None) -> None:
    _facts().WriteFact(
        OwnerContext=owner if owner is not None else host_pc(),
        AddressString=address,
        AsName="None",
        AsInt=int(value),
        AsBool=False,
    )
