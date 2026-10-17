"""Regenerate the reviewed SDK-mod bundle hashes after an explicit source audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


APP = Path(__file__).resolve().parents[1]
MOD = APP / "resources" / "Squ1ggsBoostingTools"
OUT = APP / "release_bundle_hashes.json"


def main() -> None:
    hashes = {
        path.relative_to(MOD).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in MOD.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and "logs" not in path.parts
        and path.suffix not in (".pyc", ".pyo")
    }
    OUT.write_text(
        json.dumps(dict(sorted(hashes.items())), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(hashes)} reviewed hashes to {OUT}")


if __name__ == "__main__":
    main()
