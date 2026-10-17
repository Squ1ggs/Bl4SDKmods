"""Check rendered Home button routes without issuing any gameplay actions."""
import ast
from pathlib import Path
import sys

app = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
harness = app / 'tools/manifest_structure_harness.py'
env = {'__file__': str(harness), '__name__': 'home_routes_test'}
exec(harness.read_text(encoding='utf-8').split('curated = load_module')[0], env)
root = app / 'resources/Squ1ggsBoostingTools'
core = ast.parse((root / 'backend_actions.py').read_text(encoding='utf-8'))
extended = ast.parse((root / 'bridge_actions_extended.py').read_text(encoding='utf-8'))
known = {node.name for node in extended.body if isinstance(node, ast.FunctionDef)}
for node in ast.walk(core):
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == '_ACTIONS':
        known.update(key.value for key in node.value.keys if isinstance(key, ast.Constant))
for node in extended.body:
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == '_EXTENDED_ACTION_NAMES' for target in targets):
            known.update(ast.literal_eval(node.value))

buttons = []
def walk(value):
    if isinstance(value, dict):
        if value.get('action') and value.get('label'):
            buttons.append(value)
        for item in value.values():
            walk(item)
    elif isinstance(value, list):
        for item in value:
            walk(item)
walk(env['by_id']['home'])
missing = [(button.get('label'), button['action']) for button in buttons if button['action'] not in known]
assert any(button.get('label') == 'Auto revive' for button in buttons)
assert any(button.get('action') == 'low_power' for button in buttons)
assert not missing, missing
for button in buttons:
    if button.get('toggle'):
        assert button.get('payloadOn', {}).get('enabled') is True, button
        assert button.get('payloadOff', {}).get('enabled') is False, button
print(f'PASS: {len(buttons)} Home actions resolve to registered handlers; toggle payloads checked.')
