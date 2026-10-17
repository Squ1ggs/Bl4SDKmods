"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const asar = require("@electron/asar");

const root = path.join(__dirname, "..");
const pkg = require(path.join(root, "package.json"));
const output = path.resolve(
  root,
  pkg.build.directories.output,
  "win-unpacked",
  "resources",
  "app.asar",
);
assert(fs.existsSync(output), `packed app.asar missing: ${output}`);

const forbidden = [
  /appearance_/i,
  /["']appearance["']/i,
  /imported_model/i,
  /imported_vehicle/i,
  /vehicle_appearance/i,
  /sqbt_character/i,
  /character swap/i,
  /vehicle swap/i,
];
const textExtensions = new Set([".js", ".json", ".html", ".md", ".txt"]);
const hits = [];
for (const member of asar.listPackage(output)) {
  const clean = member.replace(/^[/\\]+/, "");
  if (!textExtensions.has(path.extname(clean).toLowerCase())) continue;
  const stat = asar.statFile(output, clean, false);
  if (!stat || stat.files || stat.link) continue;
  const text = asar.extractFile(output, clean).toString("utf8");
  for (const pattern of forbidden) {
    if (pattern.test(text)) hits.push(`${clean}: ${pattern}`);
  }
}
assert.deepEqual(hits, [], `later-feature references found in packed app:\n${hits.join("\n")}`);

const sdkRoot = path.resolve(
  root,
  pkg.build.directories.output,
  "win-unpacked",
  "resources",
  "sdkmod",
  "Squ1ggsBoostingTools",
);
assert(fs.existsSync(sdkRoot), `packed sdkmod missing: ${sdkRoot}`);
const sdkHits = [];
const nameBan = /(appearance|imported_model|imported_vehicle|vehicle_appearance|sqbt_character)/i;
for (const entry of fs.readdirSync(sdkRoot, { recursive: true })) {
  const name = String(entry).replace(/\\/g, "/");
  if (nameBan.test(name)) sdkHits.push(name);
  const fullPath = path.join(sdkRoot, String(entry));
  if (fs.statSync(fullPath).isFile() && new Set([".py", ".json", ".md", ".txt", ".js", ".html"]).has(path.extname(name).toLowerCase())) {
    const text = fs.readFileSync(fullPath, "utf8");
    for (const pattern of forbidden) {
      if (pattern.test(text)) sdkHits.push(`${name}: ${pattern}`);
    }
  }
  if (/(^|\/)(__pycache__|logs)(\/|$)|\.py[co]$/i.test(name)) sdkHits.push(`${name}: runtime artifact`);

}
assert.deepEqual(sdkHits, [], `packed sdkmod has later-feature files:\n${sdkHits.join("\n")}`);

const allowlistMember = "renderer/release_tab_allowlist.js";
assert(
  asar.listPackage(output).some((m) => m.replace(/^[/\\]+/, "").replace(/\\/g, "/") === allowlistMember),
  "packed app must include release_tab_allowlist.js",
);

console.log("ALL OK: packed app + sdkmod contain no later-feature references");
