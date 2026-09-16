"""Synchronize the desktop app's bundled SDK mod from the live source tree."""
from __future__ import annotations

import shutil
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
DOCS_SOURCE = APP_DIR.parent / "Squ1ggsBoostingTools"
# Prefer the live Steam install so packs never ship a stale Documents mirror.
STEAM_SOURCE = Path(
    r"c:\Program Files (x86)\Steam\steamapps\common\Borderlands 4\sdk_mods\Squ1ggsBoostingTools"
)
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


def _resolve_source() -> Path:
    if STEAM_SOURCE.is_dir() and (STEAM_SOURCE / "_mod_version.py").is_file():
        return STEAM_SOURCE
    if DOCS_SOURCE.is_dir() and (DOCS_SOURCE / "_mod_version.py").is_file():
        return DOCS_SOURCE
    raise SystemExit(
        "SDK mod source not found. Expected Steam sdk_mods or "
        f"{DOCS_SOURCE}"
    )


def main() -> None:
    source = _resolve_source()
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    shutil.copytree(source, DESTINATION, ignore=_ignore)
    print(f"Synced SDK mod resource: {source} -> {DESTINATION}")


if __name__ == "__main__":
    main()
