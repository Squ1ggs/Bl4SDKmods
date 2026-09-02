"""Synchronize the desktop app's bundled SDK mod from the live source tree."""
from __future__ import annotations

import shutil
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
SOURCE = APP_DIR.parent / "Squ1ggsBoostingTools"
DESTINATION = APP_DIR / "resources" / "Squ1ggsBoostingTools"
EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", "logs", "tools"}


def _ignore(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        path = Path(directory, name)
        if name in EXCLUDED_DIRS:
            ignored.add(name)
        elif path.is_file() and (
            name.endswith((".pyc", ".pyo", ".sdkmod", ".log", ".jsonl"))
            or name.startswith("spawn_batch_")
            or name.startswith("spawn_test_")
        ):
            ignored.add(name)
    return ignored


def main() -> None:
    if not SOURCE.is_dir():
        raise SystemExit(f"SDK mod source not found: {SOURCE}")
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    shutil.copytree(SOURCE, DESTINATION, ignore=_ignore)
    print(f"Synced SDK mod resource: {SOURCE} -> {DESTINATION}")


if __name__ == "__main__":
    main()
