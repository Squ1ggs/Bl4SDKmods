"""Exercise the release registration and optional Appearance startup boundary."""
import argparse
import ast
import builtins
from pathlib import Path
from types import SimpleNamespace


def check_registration(source):
    tree = ast.parse(source)
    names = dict(vars(builtins))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names[node.name] = object()
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names[alias.asname or alias.name.split('.')[0]] = object()
        else:
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                    names[child.id] = object()
    names['CUSTOM_KEYBINDS'] = []
    call = next(node.value for node in tree.body if isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                and node.value.func.id == 'build_mod')
    for keyword in call.keywords:
        if keyword.arg in ('commands', 'keybinds'):
            eval(compile(ast.Expression(keyword.value), 'release-registration', 'eval'), names)


class OptionalModule:
    def __getattr__(self, name):
        return self
    def __call__(self, *args, **kwargs):
        return self
    def __bool__(self):
        return False
    def __iter__(self):
        return iter(())


def check_enable(source):
    tree = ast.parse(source)
    enable = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_on_enable')
    events = []
    def unavailable():
        events.append('appearance')
        raise RuntimeError('simulated unavailable Appearance tick')
    def importer(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'appearance_adapter':
            return SimpleNamespace(controller=unavailable)
        if name == 'external_bridge':
            return SimpleNamespace(bridge_started=lambda: True, bridge_status_line=lambda: 'Online')
        return OptionalModule()
    env = {'__builtins__': {**vars(builtins), '__import__': importer},
           'logging': SimpleNamespace(info=lambda text: None, warning=lambda text: events.append(str(text))),
           'start_bridge': lambda: events.append('bridge'), 'bridge_status_line': lambda: 'Online',
           '_mobility_runtime': OptionalModule(), '_loot_shapes': OptionalModule(), '__version__': 'test'}
    exec(compile(ast.Module(body=[enable], type_ignores=[]), 'release-enable', 'exec'), env)
    env['_on_enable']()
    assert events[0] == 'bridge', events
    assert 'appearance' in events
    assert any('desktop bridge remains active' in row for row in events)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mod', type=Path, default=Path(__file__).resolve().parents[1] / 'resources/Squ1ggsBoostingTools')
    source = (parser.parse_args().mod / '__init__.py').read_text(encoding='utf-8')
    check_registration(source)
    broken = source.replace('commands=[', 'commands=[\n        _cmd_sqbt_vehicle,', 1)
    try:
        check_registration(broken)
    except NameError as error:
        assert '_cmd_sqbt_vehicle' in str(error)
    else:
        raise AssertionError('registration check missed the reported missing command')
    check_enable(source)
    print('PASS: release command/keybind registration resolves; reported missing-command regression detected; Appearance startup failure leaves bridge startup intact.')


if __name__ == '__main__':
    main()
