"""Generate serial-order rarity regressions from each supported GZO item root."""
import importlib.util
import json
from pathlib import Path
import sys
import types

root = Path(sys.argv[1]).resolve()
pkg = types.ModuleType('Squ1ggsBoostingTools')
pkg.__path__ = [str(root)]
sys.modules[pkg.__name__] = pkg

def load(name):
    spec = importlib.util.spec_from_file_location(pkg.__name__ + '.' + name, root / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod

codec = load('serial_converter')
labels = load('item_labels')
idx = labels._type_id_index()
pearls = [(sid, int(pid)) for sid, (_, table) in idx.items()
          for pid, name in table.items() if 'comp_06_pearl' in name.lower()]
assert pearls
supported = {'Pistol', 'Shotgun', 'SMG', 'Assault Rifle', 'Sniper', 'Heavy Weapon',
             'Shield', 'Ordnance', 'Repkit', 'Enhancement', 'Classmod'}
cases = []
for sid, (label, table) in idx.items():
    info = labels.type_info_from_id(sid)
    if info.get('type') not in supported:
        continue
    comps = [(int(pid), name) for pid, name in table.items()
             if 'comp_05_' in name.lower()]
    if not comps:
        continue
    comp, _ = comps[0]
    for psid, pearl in pearls:
        for bag in (False, True):
            hook = f'{{{psid}:[{pearl}]}}' if bag else f'{{{psid}:{pearl}}}'
            human = f'{sid},0,0,70||{hook} {{{comp}}}'
            serial = codec.human_to_serial(human)
            meta = labels.meta_from_serial(serial)
            assert meta['rarity'] == 'Pearlescent', (label, human, meta['rarity'])
            assert meta['type'] == info['type'], (label, meta)
            cases.append({'serial': serial, 'set': label, 'type': info['type'], 'bag': bag, 'rarity': 'Pearlescent'})
        # The original first rarity remains authoritative if pearl is appended.
        serial = codec.human_to_serial(f'{sid},0,0,70||{{{comp}}} {{{psid}:{pearl}}}')
        assert labels.meta_from_serial(serial)['rarity'] == 'Legendary', label
        cases.append({'serial': serial, 'set': label, 'type': info['type'], 'rarity': 'Legendary'})

assert supported <= {case['type'] for case in cases}, {case['type'] for case in cases}
# A unique heuristic before a pearl comp must never hide the composition rarity.
assert labels._guess_rarity_from_part_names(['part_unique_test', 'comp_06_pearl_test']) == 'Pearlescent'
print(json.dumps(cases))
