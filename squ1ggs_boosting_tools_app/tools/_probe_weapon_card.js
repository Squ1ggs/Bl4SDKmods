"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const statsPath = path.join(
  __dirname,
  "..",
  "renderer",
  "editor",
  "data",
  "parts_stats_data.js"
);
const code = fs.readFileSync(statsPath, "utf8");
const ctx = { window: {} };
vm.runInNewContext(code, ctx);
const by = ctx.window.PARTS_STATS_DATA.by_part_code;
const keys = Object.keys(by);
const bounce = keys.filter((k) => /bounce/i.test(k)).slice(0, 20);
const cores = keys.filter((k) => /part_core/i.test(k)).slice(0, 30);
const legend = keys.filter((k) => /legendary|unique|firmware|licensed/i.test(k)).slice(0, 40);
console.log("bounce", bounce);
console.log("cores", cores.slice(0, 15));
console.log("legendish", legend.slice(0, 25));

// Sample damage_scale aggregation for a fake weapon part set
const sampleParts = [
  "jakobs.part_barrel_01",
  "jakobs.part_body_01",
  "jakobs.part_core_jak_bouncepass",
  "jakobs.part_mag_01",
];
function lookup(code) {
  if (by[code]) return by[code];
  const leaf = code.includes(".") ? code.slice(code.lastIndexOf(".") + 1) : code;
  if (by[leaf]) return by[leaf];
  const hit = keys.find((k) => k.toLowerCase().endsWith(leaf.toLowerCase()) || k.toLowerCase().includes(leaf.toLowerCase()));
  return hit ? by[hit] : null;
}
for (const p of sampleParts) {
  const rows = lookup(p);
  console.log(p, "->", rows ? rows.filter((r) => /damage/i.test(r.stat_field)).slice(0, 3) : null);
}
