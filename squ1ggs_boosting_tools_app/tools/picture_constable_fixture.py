"""Constable catalog identity with the reported L51 / pearl / Radiation edits."""
from pathlib import Path
import json
import sys
exec((Path(__file__).with_name('card_rarity_matrix.py')).read_text().split('cases = []')[0])
original = '@Ugd_t@FnkbUx;)ToRG/))s7AF$^+Vl5^+m-&<w5O1%/fL_4K#dY4gd'
human = codec.serial_to_human(original).replace('0, 1, 60|', '0, 1, 51|')
human = human.replace('||', '||{1:61}', 1).replace('{1:[60 51]}', '{1:[57 51]}')
serial = codec.human_to_serial(human)
meta = labels.meta_from_serial(serial)
assert meta['rarity'] == 'Pearlescent', meta
assert meta['damage_type'] == 'Radiation', meta
assert 'Constable' in meta['display_name'], meta
print(json.dumps({'serial': serial, 'meta': meta}))
