"""Remove runtime-only files before packaging the reviewed SDK mod."""
from __future__ import annotations

import shutil
from pathlib import Path


MOD = Path(__file__).resolve().parents[1] / "resources" / "Squ1ggsBoostingTools"


def main() -> None:
    removed = 0
    for directory in [MOD / "logs", *MOD.rglob("__pycache__")]:
        if directory.exists():
            directory.resolve().relative_to(MOD.resolve())
            shutil.rmtree(directory)
            removed += 1
    for pattern in ("*.pyc", "*.pyo"):
        for path in MOD.rglob(pattern):
            path.unlink(missing_ok=True)
            removed += 1
    print(f"Removed {removed} runtime artifact path(s)")


if __name__ == "__main__":
    main()
