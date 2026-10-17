"""Check native-only SDK layout, dynamic tuning, source syntax and isolation."""
from pathlib import Path
import ast
import json
import sys
import types
import hashlib
import builtins

APP = Path(__file__).resolve().parents[1]
MOD = APP / "resources/Squ1ggsBoostingTools"
for path in MOD.rglob("*.py"):
    ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
for filename in ("__init__.py", "backend_actions.py", "dev_tools.py", "dev_smoke.py"):
    tree = ast.parse((MOD / filename).read_text(encoding="utf-8"))
    bound = set(dir(builtins)) | {"__file__", "__name__", "__package__", "__spec__"}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        else:
            bound.update(n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            continue
        unresolved = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} - bound
        assert not unresolved, f"Unbound import-time names in {filename}: {sorted(unresolved)}"
sys.modules["mods_base"] = types.SimpleNamespace(open_in_mod_dir=lambda path, binary=False: open(path, "rb" if binary else "r"))
context = {"__file__": str(APP / "tools/manifest_structure_harness.py"), "__name__": "native_runtime_check"}
prefix = (APP / "tools/manifest_structure_harness.py").read_text(encoding="utf-8").split("manifest = panel.get_panel_manifest()")[0]
exec(compile(prefix, context["__file__"], "exec"), context)
panel = context["panel"]
manifest = panel.get_panel_manifest()
text = json.dumps(manifest)
assert "appearance_apply_selected" in text
assert not any(token in text for token in ("imported_vehicle", "imported_model", "character_appearances"))
assert [tab["id"] for tab in manifest["tabs"][:3]] == ["home", "builds", "auto_lobby"]
original = panel._development_panel_manifest
def with_slider():
    live = original()
    def walk(node):
        if isinstance(node, dict):
            if node.get("action") == "tuning_apply" and not node.get("fields"):
                node["fields"] = [{"key": "test_speed", "type": "number", "default": 123}]
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(live)
    return live
panel._development_panel_manifest = with_slider
assert "test_speed" in json.dumps(panel.get_panel_manifest()), "Reviewed layout lost live tuning fields"
for relative in ("data/imported_models.json", "data/imported_vehicles.json", "imported_models.py", "imported_vehicles.py",
                 "assets/imported_characters", "assets/imported_vehicles", "appearance_runtime_refresh.py"):
    assert not (MOD / relative).exists(), f"Private content remains in native candidate: {relative}"
assert "_cmd_sqbt_vehicle," not in (MOD / "__init__.py").read_text(encoding="utf-8")
assert "imported_vehicles.tick()" not in (MOD / "external_bridge.py").read_text(encoding="utf-8")
core = MOD / "native_appearance"
receipt = json.loads((core / "shared_core_hashes.json").read_text(encoding="utf-8"))
for relative, expected in receipt["files"].items():
    assert hashlib.sha256((core / relative).read_bytes()).hexdigest() == expected, relative
rows = json.loads((core / "data/bl4_characters.json").read_text(encoding="utf-8"))
assert {row["name"] for row in rows if row["group"] == "Vault Hunters"} == {"Vex", "Rafa", "Amon", "Harlowe", "C4SH", "Loveless"}
assert len({row["code"] for row in rows}) == 1649
assert "tick_appearance_runtime()" not in (MOD / "external_bridge.py").read_text(encoding="utf-8")
assert '"native_appearances"' in text
print("PASS: Python source, native SDK layout, dynamic tuning fields and import-control isolation")
