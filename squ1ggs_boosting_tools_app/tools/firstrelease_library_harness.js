"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../renderer/app.js"), "utf8").replace(/\r\n/g, "\n");
const context = { catalogCache: new Map(), calls: 0,
  catalogCacheKey: (name, params) => name + JSON.stringify(params),
  window: { sqbt: { getCatalog: async (name) => {
    context.calls++;
    return {ok: true, data: {rows: context.calls === 1 ? [] : [{id: "legacy", group: "Old item list"}]}};
  }}}};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf("async function loadCatalog("), source.indexOf("function applyCatalogSelection(")), context);

(async () => {
  assert.equal((await context.loadCatalog("serial_store", {})).rows.length, 0);
  assert.equal((await context.loadCatalog("serial_store", {})).rows[0].group, "Old item list");
  await context.loadCatalog("serial_groups", {});
  await context.loadCatalog("serial_groups", {});
  assert.equal(context.calls, 4, "saved libraries must refetch on open");
  await context.loadCatalog("mob_actors", {});
  await context.loadCatalog("mob_actors", {});
  assert.equal(context.calls, 5, "large unrelated catalogs should retain caching");
  // Execute the connection transition refresh with both saved and curated lists.
  const start = source.indexOf("  if (crossedActionsUnlock || crossedFirstConnect) {");
  const end = source.indexOf("  if (\n    activeTabId === \"home\"", start);
  const boxes = [{dataset: {multiselectSection: "picks"}}];
  const refreshed = [];
  Object.assign(context, {crossedActionsUnlock: true, crossedFirstConnect: true,
    refreshAllSerialStoreSections: () => refreshed.push("legacy"),
    tabContent: {querySelectorAll: () => boxes},
    getMultiselectConfig: () => ({catalog: "curated_builds"}),
    multiselectParams: () => ({}),
    refreshMultiselectSection: id => refreshed.push(id)});
  context.window.setTimeout = callback => callback();
  vm.runInContext(source.slice(start, end), context);
  assert.deepEqual(refreshed, ["legacy", "picks"]);
  context.crossedActionsUnlock = context.crossedFirstConnect = false;
  vm.runInContext(source.slice(start, end), context);
  assert.equal(refreshed.length, 2, "ordinary status polls must not collapse lists");
  console.log("ALL OK: legacy library reload, reconnect and ordinary catalog caching");
})().catch(error => {console.error(error); process.exit(1);});
