"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../renderer/app.js"), "utf8");
const code = source.slice(source.indexOf("async function autoInstallMissingSdk("), source.indexOf('installModBtn.addEventListener("click"'));
function scenario(result = {ok: true, needsGameRestart: true}) {
  const calls = [];
  const setup = {baseSdk: {gameRoot: "D:\\Games\\Borderlands 4", installed: false}, modSync: {gameRunning: false}};
  const context = vm.createContext({
    calls, setup, setupMessage: {}, actionMessage: {}, gameRootInput: {},
    setupCard: {classList: {remove() {}}}, installModBtn: {}, updateBaseSdkBtn: {},
    showSetupCard() {}, setStatusUi() {}, loadManifest: async () => {},
    window: {sqbt: {installSdkmod: async options => {calls.push(options); return result;}, getStatus: async () => ({})}},
  });
  vm.runInContext('const automaticSdkSetupAttempts = new Set(); let sdkInstallInProgress = false; let setupPinned = false; async function loadSetup(){ await autoInstallMissingSdk(setup); }\n' + code, context);
  return {context, calls, setup, run: script => vm.runInContext(script, context)};
}
(async () => {
  for (const result of [{ok: true, needsGameRestart: true}, {ok: false, message: "Download failed"}, {ok: false, cancelled: true}]) {
    const s = scenario(result);
    assert(await s.run("autoInstallMissingSdk(setup)"));
    assert.equal(s.calls.length, 1);
    assert.equal(s.calls[0].includeBaseSdk, true);
    assert.equal(await s.run("autoInstallMissingSdk(setup)"), false);
    await s.run("runInstall({includeBaseSdk:true})");
    assert.equal(s.calls.length, 2, "manual retry remains available");
  }
  for (const kind of ["installed", "no-path", "game-running", "busy"]) {
    const s = scenario();
    if (kind === "installed") s.setup.baseSdk.installed = true;
    if (kind === "no-path") s.setup.baseSdk.gameRoot = null;
    if (kind === "game-running") s.setup.modSync.gameRunning = true;
    if (kind === "busy") s.run("sdkInstallInProgress=true");
    await s.run("autoInstallMissingSdk(setup)");
    assert.equal(s.calls.length, 0, kind);
    if (kind === "game-running") assert(s.context.setupMessage.textContent.includes("Close Borderlands 4"));
  }
  assert(source.includes("await autoInstallMissingSdk(prompted)"));
  assert(source.includes("await autoInstallMissingSdk(setup)"));
  assert(source.includes("await autoInstallMissingSdk(result)"));
  console.log("PASS: first-run and selected-folder SDK auto-install; no recursive/repeated prompts; cancelled/failed installs retain manual retry; running game and concurrent installs are guarded.");
})().catch(error => { console.error(error); process.exitCode = 1; });
