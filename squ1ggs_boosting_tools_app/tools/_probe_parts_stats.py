from pathlib import Path
import re

p = Path(__file__).resolve().parents[1] / "renderer" / "editor" / "data" / "parts_stats_data.js"
text = p.read_text(encoding="utf-8")
print("size", len(text))
print("damage fields", text.count('"stat_field":"damage"'))
print("bounce", text.lower().find("bounce"))
idx = text.lower().find("bounce")
if idx > 0:
    print(text[max(0, idx - 100) : idx + 160])
# sample one damage row
m = re.search(r'"([^"]+)":\[(\{[^{}]*"stat_field":"damage"[^{}]*\})', text)
if m:
    print("sample key", m.group(1))
    print("sample row", m.group(2)[:300])
# passive / classmod-ish
for needle in ("passive_points", "part_passive", "universal", "secondary"):
    print(needle, text.lower().find(needle.lower()))
