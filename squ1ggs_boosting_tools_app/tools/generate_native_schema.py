"""Export the reviewed native runtime schema; never regenerate from a private mod."""
from pathlib import Path
import json
import re

APP = Path(__file__).resolve().parents[1]
MOD = APP / "resources/Squ1ggsBoostingTools"
schema = json.loads((MOD / "data/release_native_manifest.json").read_text(encoding="utf-8"))
version = re.search(r'__version__:\s*str\s*=\s*"([^"]+)"', (MOD / "_mod_version.py").read_text(encoding="utf-8")).group(1)
schema["version"] = version
(APP / "renderer/release_ui_schema.js").write_text('"use strict";\nconst SQBT_RELEASE_UI_SCHEMA = ' + json.dumps(schema, ensure_ascii=False) + ';\nif (typeof module !== "undefined") module.exports = SQBT_RELEASE_UI_SCHEMA;\nelse window.SQBT_RELEASE_UI_SCHEMA = SQBT_RELEASE_UI_SCHEMA;\n', encoding="utf-8", newline="\n")
(APP / "renderer/offline_manifest.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
(APP / "lib/release_actions.json").write_bytes((MOD / "data/release_actions.json").read_bytes())
print("Exported reviewed native schema and action boundary")
