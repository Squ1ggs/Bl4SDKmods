"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { visibleLicensedParts } = require("../lib/image_item_match");

const rows = [
  {
    category: "Weapon",
    manufacturer: "Jakobs",
    itemType: "Sniper Rifle",
    weaponType: "Sniper Rifle",
    partType: "Legendary Perks",
    code: "Truck (Fixer-Upper)",
    name: "Truck (Fixer-Upper)",
    idRaw: "24:75",
    effects: "Fixer-Upper",
  },
  {
    category: "Weapon",
    manufacturer: "Jakobs",
    itemType: "Sniper Rifle",
    weaponType: "Sniper Rifle",
    partType: "Manufacturer Part",
    code: "JAK_SR.part_mag_torgue_normal",
    name: "Torgue Impact Gyrojets",
    idRaw: "24:18",
    stats: "Torgue Impact Gyrojets",
  },
  {
    category: "Weapon",
    manufacturer: "Jakobs",
    itemType: "Sniper Rifle",
    weaponType: "Sniper Rifle",
    partType: "Manufacturer Part",
    code: "JAK_SR.part_secondary_ammo_sg",
    name: "Secondary Ammo Sg",
    idRaw: "24:70",
    stats: "Daedalus Shotgun Ammo",
  },
];

const state = {};
const posts = [];
let messageListener = null;
const document = {
  readyState: "loading",
  addEventListener() {},
  getElementById() { return null; },
  querySelectorAll() { return []; },
};
const parent = { postMessage: (payload) => posts.push(payload) };
const window = {
  parent,
  STX_DATASET: { ALL_PARTS: rows },
  __STX_SIMPLE_STATE: state,
  addEventListener(type, listener) {
    if (type === "message") messageListener = listener;
  },
  refreshTopSelectors() {},
  refreshBuilder() {},
  refreshOutputs() {},
  refreshBuildStatsCore() {},
  stxTryPlacePartInBestSlot(part) {
    if (part.code.includes("secondary_ammo")) state.slots.secondaryAmmo = part;
    else if (part.code.includes("mag_")) state.slots.mag = part;
    else return false;
    return true;
  },
};
const context = {
  window,
  document,
  MutationObserver: function MutationObserver() {},
  setTimeout(callback) {
    callback();
    return 1;
  },
  clearTimeout() {},
  setInterval() {},
  console,
};

const bridgePath = path.join(__dirname, "..", "renderer", "editor", "js", "sqbt_editor_bridge.js");
vm.runInNewContext(fs.readFileSync(bridgePath, "utf8"), context, { filename: bridgePath });
assert.equal(typeof messageListener, "function");

messageListener({
  source: parent,
  data: {
    source: "sqbt-shell",
    type: "sqbt-load-image-recipe",
    requestId: "truck-exact-parts",
    extracted: {
      title_candidates: ["Sudden Looming Truck"],
      item_type: "Sniper Rifle",
      manufacturer: "Jakobs",
      rarity: "Legendary",
      level: 70,
      perks: [
        "See Fixer-Upper",
        "Torgue-Licensed Impact Magazine - Fires Gyrojets that explode on impact",
        "Daedalus-Licensed Multi-Loader - Secondary fire consumes Shotgun Ammo",
        "Jakobs - Critical Hits will Ricochet Projectiles",
      ],
    },
  },
});

assert.equal(state.mainPart.idRaw, "24:75");
assert.equal(state.slots.mag.idRaw, "24:18");
assert.equal(state.slots.secondaryAmmo.idRaw, "24:70");
const imported = posts.findLast((payload) => payload.type === "sqbt-editor-imported");
assert.equal(imported.ok, true);
assert.equal(imported.resolved_parts.length, 3);
assert.equal(imported.request_id, "truck-exact-parts");
assert.deepEqual(Array.from(imported.resolved_part_ids), ["24:75", "24:18", "24:70"]);
assert.match(imported.message, /3 resolved parts/);

const licensed = visibleLicensedParts(
  "Daedalus-Licensed Multi-Loader - Secondary fire consumes Shotgun Ammo",
  { manufacturer: "Jakobs", itemType: "Sniper Rifle" }
);
assert.equal(licensed.length, 1);
assert.equal(licensed[0].id_raw, "24:70");

const hiddenGrip = { idRaw: "24:999", name: "Hidden catalog grip" };
state.mainPart = rows[0];
state.slots = { mag: rows[1], grip: hiddenGrip };
state.extras = [];
state.level = 60;
messageListener({
  source: parent,
  data: {
    source: "sqbt-shell",
    type: "sqbt-load-image-recipe",
    merge: true,
    extracted: {
      title_candidates: ["Sudden Looming Truck"],
      item_type: "Sniper Rifle",
      manufacturer: "Jakobs",
      rarity: "Legendary",
      level: 70,
      perks: [
        "See Fixer-Upper",
        "Torgue-Licensed Impact Magazine - Fires Gyrojets that explode on impact",
        "Daedalus-Licensed Multi-Loader - Secondary fire consumes Shotgun Ammo",
      ],
    },
  },
});
assert.equal(state.level, 70);
assert.equal(state.mainPart.idRaw, "24:75");
assert.equal(state.slots.grip.idRaw, "24:999");
assert.equal(state.slots.mag.idRaw, "24:18");
assert.equal(state.slots.secondaryAmmo.idRaw, "24:70");

const appSource = fs.readFileSync(
  path.join(__dirname, "..", "renderer", "app.js"),
  "utf8"
);
assert.match(appSource, /level_override:\s*true/);
assert.match(appSource, /imageExtracted/);
assert.match(appSource, /sqbt-picture-final-serial/);
assert.match(appSource, /Give pictured item/);
assert.match(appSource, /async function serialWithExactLevel/);
assert.match(appSource, /The final serial did not verify at level/);
assert.match(appSource, /async function previewTopPictureCandidate/);
assert.match(appSource, /Top match ·/);
assert.match(appSource, /sqbt-picture-level/);
assert.match(appSource, /async function finalizePictureSerialAtLevel/);
assert.match(appSource, /syncBuilder:\s*true/);
assert.match(appSource, /editorPictureLastImport/);
assert.match(appSource, /resolved_part_ids/);
assert.match(appSource, /Final serial is missing pictured part/);
console.log("ALL OK");
