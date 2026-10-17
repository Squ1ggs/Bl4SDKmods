from pathlib import Path
import re, collections, json

root = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Borderlands 4\sdk_mods\Squ1ggsBoostingTools")
gzo = json.loads((root / "gzo_parts_map.json").read_text(encoding="utf-8"))
hits = []
for table_key, table in gzo.items():
    if not isinstance(table, dict):
        continue
    for pid, name in table.items():
        low = str(name).lower()
        if "bounce" in low or "pass" in low and "passive" not in low:
            hits.append(name)
print("bounce/pass samples", hits[:30], "count", len(hits))

stats = Path(r"C:\Users\picto\Documents\New folder (4)\squ1ggs_boosting_tools_app\renderer\editor\data\parts_stats_data.js").read_text(encoding="utf-8")
fields = collections.Counter(re.findall(r'"stat_field":"([^"]+)"', stats))
print("top fields", fields.most_common(25))
print("damage nonzero", len(re.findall(r'"stat_field":"damage","stat_value":(?!0(?:\.0+)?(?:[,}]))', stats)))
