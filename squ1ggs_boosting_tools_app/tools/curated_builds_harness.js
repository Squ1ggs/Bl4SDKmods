"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { analyzeItem } = require("../lib/item_analysis");

const modRoot = path.resolve(__dirname, "../resources/Squ1ggsBoostingTools");
const definitions = fs.readFileSync(path.join(modRoot, "curated_builds.py"), "utf8");
const overrideBlock = definitions.match(
  /OPTIMIZED_ITEM_OVERRIDES:[\s\S]+?\ndef _source_index/
);
assert(overrideBlock, "optimized build serial map is missing");
const serials = Array.from(
  overrideBlock[0].matchAll(/"serial":\s*"([^"]+)"/g),
  (match) => match[1]
);
assert(serials.length >= 10, "expected a useful optimized build set");
assert.equal(new Set(serials).size, serials.length, "optimized build serials must be unique");

(async () => {
  for (const serial of serials) {
    const result = await analyzeItem(serial);
    assert.equal(result.ok, true, `could not decode ${serial.slice(0, 18)}`);
    assert.equal(result.exact, true, `serial was not exact ${serial.slice(0, 18)}`);
    assert.equal(
      result.identity?.round_trip_exact,
      true,
      `serial did not round-trip ${serial.slice(0, 18)}`
    );
  }
  const truck = await analyzeItem(
    "@Ugy3L+35E/MOza2Bi7M2g5_J<b4^<C!5A~@ss5+=Vs6VJ$sBoy32m"
  );
  assert.match(truck.decoded_human || "", /^\s*24\s*,/);
  assert.match(truck.decoded_human || "", /\{18\}/);
  assert.match(truck.decoded_human || "", /\{70\}/);

  const appSource = fs.readFileSync(path.join(__dirname, "..", "renderer", "app.js"), "utf8");
  assert.match(appSource, /Skills: \$\{skills\}/);
  assert.match(appSource, /God roll: \$\{row\.roll\}/);
  assert.match(appSource, /function decodedSerialHasPartId/);
  console.log(`ALL OK (${serials.length} optimized build serials)`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
