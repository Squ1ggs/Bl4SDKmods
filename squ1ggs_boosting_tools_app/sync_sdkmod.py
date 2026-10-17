"""Validate the reviewed release bundle; never pull the private development mod."""
from pathlib import Path
import hashlib
import json

APP = Path(__file__).resolve().parent
MOD = APP / "resources" / "Squ1ggsBoostingTools"

def main():
    expected = json.loads((APP / "release_bundle_hashes.json").read_text(encoding="utf-8"))
    actual = {p.relative_to(MOD).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in MOD.rglob("*") if p.is_file() and "__pycache__" not in p.parts
              and "logs" not in p.parts
              and p.suffix not in (".pyc", ".pyo")}
    if actual != expected:
        changed = sorted(k for k in actual.keys() | expected.keys() if actual.get(k) != expected.get(k))
        raise SystemExit("Release bundle changed; review and refresh its audit before packing: " + ", ".join(changed[:20]))
    print("Reviewed native release bundle verified; imported characters and vehicle swaps remain excluded.")

if __name__ == "__main__":
    main()
