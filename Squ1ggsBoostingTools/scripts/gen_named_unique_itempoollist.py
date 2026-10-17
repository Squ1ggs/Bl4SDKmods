"""One-off: scan NCS ItemPoolList exports → named_unique_itempoollist.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

INV_RE = re.compile(r"inv'([A-Za-z0-9_]+)\.(comp_05_legendary_[^']+)'", re.I)
LIST_RE = re.compile(
    r'"itempoollist":\s*\{[^}]*"value":\s*"(ItemPoolList_[^"]+)"'
)


def main() -> None:
    ncs = Path(r"C:\Users\picto\Documents\bl4fmodel\ncs_json")
    inv_to_lists: dict[str, set[str]] = {}
    for path in sorted(ncs.rglob("Nexus-Data-ItemPoolList*.json")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in LIST_RE.finditer(text):
            list_name = m.group(1)
            chunk = text[m.start() : m.start() + 12000]
            for root, comp in INV_RE.findall(chunk):
                inner = f"{root.lower()}.{comp.lower()}"
                inv_to_lists.setdefault(inner, set()).add(list_name)

    out: dict[str, list[str]] = {}
    for inner, lists in sorted(inv_to_lists.items()):
        if "comp_05_legendary_" not in inner:
            continue
        root, _, comp = inner.partition(".")
        out[f"{root}_{comp}"] = sorted(lists)

    dest = (
        Path(__file__).resolve().parents[1]
        / "item_spawn"
        / "data"
        / "reference"
        / "named_unique_itempoollist.json"
    )
    dest.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {len(out)} catalogs to {dest}")


if __name__ == "__main__":
    main()
