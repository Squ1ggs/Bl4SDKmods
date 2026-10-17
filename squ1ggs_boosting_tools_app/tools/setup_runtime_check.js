"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const paths = require("../lib/game_paths");
const {detectBaseSdk} = require("../lib/oak2_sdk");
const scratch = path.resolve(__dirname, "../../../.workspace-temp");
fs.mkdirSync(scratch, {recursive: true});
const fixture = fs.mkdtempSync(path.join(scratch, "setup-secondary-drive-"));
try {
  const game = path.join(fixture, "Games/Borderlands 4");
  const binaries = path.join(game, "OakGame/Binaries/Win64");
  const plugins = path.join(binaries, "Plugins");
  const mods = path.join(game, "sdk_mods");
  fs.mkdirSync(plugins, {recursive: true});
  fs.mkdirSync(mods);
  fs.writeFileSync(path.join(binaries, "Borderlands4.exe"), "fixture");
  for (const input of [game, binaries, path.join(game, "OakGame"), mods, path.join(binaries, "Borderlands4.exe")]) {
    assert.equal(paths.normalizeGameRoot(input), game);
  }
  const tool = path.join(fixture, "Downloads/Squ1ggs");
  fs.mkdirSync(tool, {recursive: true});
  fs.writeFileSync(path.join(tool, "Squ1ggsBoostingTools.exe"), "fixture");
  assert.equal(paths.normalizeGameRoot(tool), null);
  assert.equal(paths.resolveGameRoot(tool), null);
  fs.writeFileSync(path.join(binaries, "dsound.dll"), "fixture");
  fs.writeFileSync(path.join(plugins, "unrealsdk.dll"), "fixture");
  fs.writeFileSync(path.join(mods, "mods_base.sdkmod"), "fixture");
  fs.writeFileSync(path.join(mods, ".sqbt_oak2_sdk_version"), "0.3");
  assert.equal(detectBaseSdk(game).installed, false);
  fs.writeFileSync(path.join(plugins, "pyunrealsdk.dll"), "fixture");
  assert.equal(detectBaseSdk(game).installed, false);
  fs.writeFileSync(path.join(plugins, "python314.dll"), "fixture");
  assert.equal(detectBaseSdk(game).installed, false);
  fs.writeFileSync(path.join(plugins, "python314.zip"), "fixture");
  const installed = detectBaseSdk(game);
  assert(installed.installed && installed.hasPythonPlugin && installed.hasPythonRuntime);
  assert(installed.pythonMessage.includes("No separate Python"));
  assert.equal(detectBaseSdk(tool).gameRoot, null);
  console.log("PASS: secondary-drive/nested game paths; wrong tool folder rejected; missing embedded Python detected; complete SDK accepted without system Python.");
} finally {
  assert(path.relative(scratch, fixture).startsWith("setup-secondary-drive-"));
  fs.rmSync(fixture, {recursive: true});
}
