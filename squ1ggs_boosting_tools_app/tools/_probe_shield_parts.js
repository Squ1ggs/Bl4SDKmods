"use strict";
const path = require("node:path");
const { loadStatData, resolveAttribute, buildStatContext } = require("../lib/nexus/serial_card_stats");
const { evaluateNexusCardStats } = require("../lib/nexus_card_stats");

const data = loadStatData({
  legitItemsPath: path.join(__dirname, "..", "resources", "LegitItems"),
});
const set = "ord_shield";
const keys = [...data.invRoots.get(set).parts.keys()].sort();
const interesting = keys.filter((k) =>
  /capacity|amp|resist|generous|trick|firmware|body_energy|cindershelly|unv_|aug_|comp_05/i.test(k)
);
console.log("interesting", interesting);

function run(picked, label) {
  const ctx = buildStatContext(data, {
    set,
    partKeys: picked,
    partRoots: picked.map(() => set),
    level: 70,
  });
  const cap = resolveAttribute("shield_capacity", ctx);
  const rate = resolveAttribute("shield_regen_rate", ctx);
  const delay = resolveAttribute("shield_regen_delay", ctx);
  console.log(
    label,
    "cap",
    cap,
    "rate",
    rate,
    "delay",
    delay,
    "mods",
    (ctx.modifiers.get("shield_capacity")?.ordered || []).map((m) => `${m.kind}:${m.value}`)
  );
}

const base = [
  "comp_05_legendary_cindershelly",
  "part_body_energy",
  "part_unique_cindershelly",
];
run(base, "BASE");

for (const extra of interesting) {
  if (base.includes(extra)) continue;
  run([...base, extra], `+${extra}`);
}
