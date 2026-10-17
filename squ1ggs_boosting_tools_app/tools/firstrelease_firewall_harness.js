"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.join(__dirname, "..");
const allowlistSrc = fs.readFileSync(path.join(root, "renderer/release_tab_allowlist.js"), "utf8");
const appSrc = fs.readFileSync(path.join(root, "renderer/app.js"), "utf8").replace(/\r\n/g, "\n");
const offline = JSON.parse(
  fs.readFileSync(path.join(root, "renderer/offline_manifest.json"), "utf8"),
);

const context = { window: {} };
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, "renderer/release_ui_schema.js"), "utf8"), context);
vm.runInContext(fs.readFileSync(path.join(root, "renderer/release_manifest_guard.js"), "utf8"), context);
vm.runInContext(allowlistSrc, context);

const fnStart = appSrc.indexOf("/** First-release EXE: drop any live/private tabs not on the bundled allowlist. */");
const fnEnd = appSrc.indexOf("\nasync function finishHiddenShapeUnlock", fnStart);
assert(fnStart > 0 && fnEnd > fnStart, "lockManifestToFirstRelease missing");
vm.runInContext(appSrc.slice(fnStart, fnEnd), context);

const allow = context.window.SQBT_RELEASE_TAB_ALLOWLIST;
assert(Array.isArray(allow) && allow.length >= 20, "allowlist missing");
assert(!allow.includes("appearance"), "allowlist must not include later private tabs");

const offlineIds = (offline.tabs || []).map((t) => t.id);
assert.deepEqual([...allow], offlineIds, "allowlist must match stripped offline_manifest tabs");

const locked = context.lockManifestToFirstRelease({
  tabs: [
    { id: "home", label: "Home" },
    { id: "appearance", label: "Later private tab" },
    { id: "loot", label: "Loot" },
    { id: "imported_models", label: "Later private tab" },
  ],
  lobby: {
    sections: [
      { tabId: "home" },
      { tabId: "appearance" },
      { tabId: "loot" },
    ],
  },
});
assert.deepEqual(
  locked.tabs.map((t) => t.id),
  ["home", "loot"],
  "live private tabs must be stripped from UI",
);
assert.deepEqual(
  locked.lobby.sections.map((s) => s.tabId),
  ["home", "loot"],
);

const modRoot = path.join(root, "resources", "Squ1ggsBoostingTools");
const forbiddenName = /(appearance|imported_model|imported_vehicle|vehicle_appearance|sqbt_character)/i;
const badFiles = [];
for (const entry of fs.readdirSync(modRoot, { recursive: true })) {
  const name = String(entry).replace(/\\/g, "/");
  if (forbiddenName.test(name)) badFiles.push(name);
}
assert.deepEqual(badFiles, [], `firstrelease bundle has later-feature files:\n${badFiles.join("\n")}`);

console.log("ALL OK: firstrelease UI allowlist firewall + stripped bundle files");
