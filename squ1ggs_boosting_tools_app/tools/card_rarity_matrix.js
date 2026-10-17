"use strict";
const assert = require('node:assert/strict');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const app = path.resolve(process.argv[2] || path.join(__dirname, '..'));
const root = path.join(app, 'resources', 'Squ1ggsBoostingTools');
const result = spawnSync('python', [path.join(__dirname, 'card_rarity_matrix.py'), root],
  {encoding: 'utf8', windowsHide: true, maxBuffer: 16 * 1024 * 1024});
assert.equal(result.status, 0, result.stderr);
const cases = JSON.parse(result.stdout);
const {decodeSerialCard} = require(path.join(app, 'lib/serial_codec'));
global.window = global;
global.addEventListener = () => {};
require(path.join(app, 'native_item_card'));
const {toNativeCardModel} = require(path.join(app, 'native_card_model'));
for (const row of cases) {
  const decoded = decodeSerialCard(row.serial, root);
  assert.equal(decoded.rarity, row.rarity, JSON.stringify(row));
  assert.equal(decoded.item_type, row.type, JSON.stringify(row));
  assert.equal(decoded.identity.round_trip_exact, true);
  // Exercise propsToEntry: the old direct-model pearl tests skipped this step.
  if (row.rarity === 'Pearlescent') {
    const entry = global.SQBTNativeItemCard.propsToEntry({...decoded, rarity: 'Common'});
    assert.equal(entry.rarity, 'Pearlescent', JSON.stringify(row));
    assert.equal(toNativeCardModel(entry).rarityident, 'pearl', JSON.stringify(row));
  }
}
console.log(`PASS: ${cases.length} pearl serial cases across ${new Set(cases.map(x=>x.set)).size} roots / ${new Set(cases.map(x=>x.type)).size} item types; Python, JS, round-trip and card entry.`);
