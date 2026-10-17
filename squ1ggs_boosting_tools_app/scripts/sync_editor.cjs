/**
 * Sync Simple Builder datasets from a local Scooter's Toolbox checkout.
 * Usage: node scripts/sync_editor.cjs "D:\\new edit"
 */
const fs = require("fs");
const path = require("path");

const srcRoot = path.resolve(process.argv[2] || "D:\\new edit");
const assets = path.join(srcRoot, "assets");
const dest = path.join(__dirname, "..", "renderer", "editor");

const dataFiles = [
  "stx_dataset.js",
  "stx_dataset_supplement.js",
  "stx_raid2_supplement.js",
  "part_display_overrides.js",
  "stx_rarities.js",
  "weapon_stats_data.js",
  "parts_stats_data.js",
  "stx_editor_extract.js",
  "stx_new_item_codes.js",
  "legacy_classmod_names.js",
  "legacy_classmod_skills_full.js",
  "classmod_perk_meta.js",
  "perk_thumb_urls.js",
  "classmod_manifest_items.js",
  "inv_comp_tag_data.js",
  "part_ref_meta.js",
  "skin_data.js",
  "stx_rarities_extract.js",
  "stx_nexus_gap_supplement.js",
  "stx_rarities_supplement_patch.js",
  "stx_rarities_raid2_patch.js",
  "stx_rarities_community_pearl_patch.js",
  "stx_dataset_repkit_label_patch.js",
];
const jsFiles = [
  "stx-simple-builder-core.js",
  "cc-item-slug.js",
  "cc-build-stats-rebuild.js",
  "rebuild-presets-random.js",
  "cc-custom-select-rebuild.js",
  "cc-base85-rebuild.js",
  "stx-nicnl-serial-pack.js",
];

function copyOne(from, to) {
  fs.mkdirSync(path.dirname(to), { recursive: true });
  fs.copyFileSync(from, to);
  console.log("OK", path.relative(dest, to));
}

if (!fs.existsSync(assets)) {
  console.error("Missing assets at", assets);
  process.exit(1);
}

for (const f of dataFiles) {
  const from = path.join(assets, "data", f);
  if (!fs.existsSync(from)) {
    console.warn("MISS", f);
    continue;
  }
  copyOne(from, path.join(dest, "data", f));
}
for (const f of jsFiles) {
  const from = path.join(assets, "js", f);
  if (!fs.existsSync(from)) {
    console.warn("MISS", f);
    continue;
  }
  copyOne(from, path.join(dest, "js", f));
}
const css = path.join(assets, "css", "cc-build-stats-panel.css");
if (fs.existsSync(css)) copyOne(css, path.join(dest, "css", "cc-build-stats-panel.css"));
console.log("Applying SQBT-only editor overlays…");
require("child_process").execFileSync(process.execPath, [path.join(__dirname, "apply_sqbt_editor_overlays.cjs")], {
  stdio: "inherit",
});
console.log("Done. Re-check renderer/editor/index.html if DOM ids changed upstream.");
