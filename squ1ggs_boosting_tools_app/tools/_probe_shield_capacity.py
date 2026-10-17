import json
import re
from pathlib import Path

LEGIT = Path(__file__).resolve().parents[1] / "resources" / "LegitItems"
RAW = (LEGIT / "Nexus-Data-inv4.json").read_text(encoding="utf-8")

for m in re.finditer(
    r'attributetomodify"\s*:\s*"attribute\'shield_capacity\'"[\s\S]{0,260}',
    RAW,
):
    chunk = m.group(0)
    prev = RAW[max(0, m.start() - 600) : m.start()]
    names = re.findall(r'"([a-z0-9_]+)"\s*:\s*\{\s*"inv', prev)
    name = names[-1] if names else "?"
    mt = re.search(r'modifiertype"\s*:\s*"([^"]+)"', chunk)
    mv = re.search(r'constant"\s*:\s*"([^"]+)"', chunk) or re.search(
        r'attribute"\s*:\s*"([^"]+)"', chunk
    )
    print(
        f"{name:42} {(mt.group(1) if mt else '?'):18} {(mv.group(1) if mv else '?')}"
    )
