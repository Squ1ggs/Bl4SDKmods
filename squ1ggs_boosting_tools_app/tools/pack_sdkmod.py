#!/usr/bin/env python3
"""Build Squ1ggsBoostingTools.sdkmod (zip) for mod-only GitHub hotfixes.

Users with an existing EXE can Install update and get only the Python mod —
no full portable redownload — when the release attaches this asset and notes
``mod X.Y.Z`` in the body.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "resources" / "Squ1ggsBoostingTools"
SKIP_SUFFIXES = {".pyc", ".pyo", ".sdkmod", ".log", ".jsonl"}
SKIP_NAMES = {".git", "__pycache__", ".DS_Store", "Thumbs.db"}


def should_skip(path: Path) -> bool:
    name = path.name
    if name in SKIP_NAMES or name.startswith("."):
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def build_sdkmod(src: Path, out: Path) -> Path:
    if not src.is_dir() or not (src / "__init__.py").is_file():
        raise SystemExit(f"Missing mod folder: {src}")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    folder_name = "Squ1ggsBoostingTools"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if not path.is_file() or should_skip(path):
                continue
            if any(part in SKIP_NAMES for part in path.parts):
                continue
            arc = f"{folder_name}/{path.relative_to(src).as_posix()}"
            zf.write(path, arcname=arc)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        type=Path,
        default=DEFAULT_SRC,
        help="Mod folder to pack (default: resources/Squ1ggsBoostingTools)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output .sdkmod path (default: ../dist_squ1ggs_boosting_tools_<ver>/Squ1ggsBoostingTools.sdkmod)",
    )
    args = parser.parse_args()
    version = "dev"
    try:
        text = (args.src / "_mod_version.py").read_text(encoding="utf-8")
        for line in text.splitlines():
            if "__version__" in line and "=" in line:
                version = line.split("=", 1)[1].strip().strip("\"'")
                break
    except Exception:
        pass
    out = args.out
    if out is None:
        out = ROOT.parent / f"dist_squ1ggs_boosting_tools_sdkmod" / "Squ1ggsBoostingTools.sdkmod"
    path = build_sdkmod(args.src, out)
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Wrote {path} ({size_mb:.1f} MB) — mod {version}")
    print("Attach on GitHub Releases as Squ1ggsBoostingTools.sdkmod")
    print(f'Put \"mod **{version}**\" in the release body so the EXE detects a mod-only update.')


if __name__ == "__main__":
    main()
