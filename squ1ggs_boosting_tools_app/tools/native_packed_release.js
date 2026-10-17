"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const vm = require("node:vm");
const asar = require("@electron/asar");
const root = path.resolve(__dirname, "..");
const pkg = require(path.join(root, "package.json"));
const packed = path.resolve(root, pkg.build.directories.output, "win-unpacked");
const archive = path.join(packed, "resources/app.asar");
const members = asar.listPackage(archive).map(p => p.replace(/^[/\\]+/, "").replace(/\\/g, "/"));
let appFiles = 0;
for (const member of members) {
  if (member.startsWith("node_modules/")) continue;
  const archiveMember = path.normalize(member);
  const stat = asar.statFile(archive, archiveMember, false);
  if (stat.files || stat.link) continue;
  const source = path.join(root, member);
  assert(fs.existsSync(source), `Unexpected packaged app file: ${member}`);
  // electron-builder removes development/build metadata from package.json.
  if (member !== "package.json") assert(asar.extractFile(archive, archiveMember).equals(fs.readFileSync(source)), `Packaged app differs: ${member}`);
  appFiles++;
}
function packedModule(member) {
  const context = {module: {exports: {}}, console};
  vm.runInNewContext(asar.extractFile(archive, path.normalize(member)).toString("utf8"), context, {filename: member});
  return context.module.exports;
}
const schema = packedModule("renderer/release_ui_schema.js");
const restrict = packedModule("renderer/release_manifest_guard.js");
assert.deepEqual(Array.from(schema.tabs.slice(0, 3), t => t.id), ["home", "builds", "auto_lobby"]);
const appearance = schema.tabs.find(t => t.id === "appearance");
assert(appearance?.sections.some(s => s.multiselect?.catalog === "native_appearances"));
assert(!/imported_model|imported_vehicle|character_appearances/.test(JSON.stringify(schema)));
const injected = JSON.parse(JSON.stringify(schema));
injected.tabs.find(t => t.id === "appearance").sections.push({title: "Foreign packs", actions: [{action: "imported_model_apply"}]});
injected.tabs.push({id: "private_test", sections: []});
assert(!/Foreign packs|private_test|imported_model/.test(JSON.stringify(restrict(injected, schema))));
const actions = JSON.parse(asar.extractFile(archive, "lib/release_actions.json"));
for (const action of ["appearance_preview_selected", "appearance_apply_selected", "appearance_restore", "appearance_clear_previews"]) assert(actions.includes(action), action);
assert(!actions.some(a => /imported_model|imported_vehicle/.test(a)));
const packedPkg = JSON.parse(asar.extractFile(archive, "package.json"));
assert.equal(packedPkg.version, pkg.version);
assert.equal(packedPkg.main, pkg.main);
assert.deepEqual(packedPkg.dependencies, pkg.dependencies);
const sdk = path.join(packed, "resources/sdkmod/Squ1ggsBoostingTools");
const expected = require(path.join(root, "release_bundle_hashes.json"));
const actual = {};
for (const entry of fs.readdirSync(sdk, {recursive: true})) {
  const full = path.join(sdk, entry);
  const relative = entry.replace(/\\/g, "/");
  assert(!/(^|\/)(__pycache__|logs)(\/|$)|\.py[co]$/i.test(relative), `Runtime artifact: ${relative}`);
  assert(!/(^|\/)(imported_models|imported_vehicles|appearance_runtime_refresh)\.py$|assets\/imported_|data\/imported_(models|vehicles)\.json/i.test(relative), `Private content: ${relative}`);
  if (fs.statSync(full).isFile()) actual[relative] = crypto.createHash("sha256").update(fs.readFileSync(full)).digest("hex");
}
assert.deepEqual(actual, expected, "Packed SDK differs from the reviewed bundle");
const modVersion = fs.readFileSync(path.join(sdk, "_mod_version.py"), "utf8").match(/__version__:\s*str\s*=\s*"([^"]+)"/)[1];
assert.equal(modVersion.split(".")[2], pkg.version.split(".")[2], "EXE/mod patch versions differ");
const catalog = JSON.parse(fs.readFileSync(path.join(sdk, "native_appearance/data/bl4_characters.json"), "utf8"));
assert.equal(new Set(catalog.map(r => r.code)).size, 1649);
console.log(`PASS: ${appFiles} app files and ${Object.keys(actual).length} SDK files match source; packaged native-only Appearance, menu guard, catalog and EXE ${pkg.version}/mod ${modVersion} verified.`);
