import json
from pathlib import Path

mod = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Borderlands 4\sdk_mods\Squ1ggsBoostingTools")
app = Path(__file__).resolve().parents[1]
print("mod", (mod / "_mod_version.py").read_text(encoding="utf-8"))
print("exe", json.loads((app / "package.json").read_text(encoding="utf-8"))["version"])
print("synced", (app / "resources/Squ1ggsBoostingTools/_mod_version.py").read_text(encoding="utf-8"))
io = json.loads((mod / "embedded_bms/data/io_spawn_catalog.json").read_text(encoding="utf-8"))
wide = sum(1 for e in io["entries"] if e.get("category") == "Wide floors")
print("io", io["count"], "wide", wide, "has_cat", "Wide floors" in io.get("categories", []))
print("travel", json.loads((mod / "travelstations.json").read_text(encoding="utf-8"))["count"])
fw = sorted(p.name for p in (app / "resources/LegitItems").glob("Nexus-Data-Firmware*.json"))
print("firmware", fw)
pm = (mod / "panel_manifest.py").read_text(encoding="utf-8")
print("collectibles", "Give all collectibles" in pm)
print("wide_default", '"default": "Wide floors"' in pm)
