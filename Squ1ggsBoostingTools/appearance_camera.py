"""Read an appearance's head height without changing its mesh or animation."""
from __future__ import annotations

from typing import Any


def model_eye_height(mesh: Any, pawn_z: float) -> float | None:
    candidates = []
    try:
        count = min(1024, max(0, int(mesh.GetNumBones())))
        for index in range(count):
            bone = mesh.GetBoneName(index)
            name = str(bone).casefold()
            if name == "head" or name.endswith("_head"):
                candidates.insert(0, bone)
            elif "head" in name and not any(word in name for word in ("end", "ik", "weapon")):
                candidates.append(bone)
        for bone in candidates:
            pos = mesh.GetSocketLocation(bone)
            height = float(pos.Z) - float(pawn_z)
            if -1024.0 <= height <= 4096.0:
                return height
    except Exception:
        pass
    try:
        bounds = mesh.Bounds
        if float(bounds.BoxExtent.Z) > 0:
            height = float(bounds.Origin.Z) + float(bounds.BoxExtent.Z) * 0.8 - float(pawn_z)
            return max(-1024.0, min(4096.0, height))
    except Exception:
        pass
    return None
