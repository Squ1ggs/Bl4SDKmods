"use strict";

const statusDot = document.getElementById("status-dot");
const statusHeadline = document.getElementById("status-headline");
const statusDetail = document.getElementById("status-detail");
const metaBridge = document.getElementById("meta-bridge");
const metaModVersion = document.getElementById("meta-mod-version");
const metaSession = document.getElementById("meta-session");
const metaTarget = document.getElementById("meta-target");
const metaSpawn = document.getElementById("meta-spawn");
const metaFreecam = document.getElementById("meta-freecam");
const rosterList = document.getElementById("roster-list");
const globalTargetSelect = document.getElementById("global-target-select");
const spawnAnchorSelect = document.getElementById("spawn-anchor-select");
const setupMessage = document.getElementById("setup-message");
const settingsModeNote = document.getElementById("settings-mode-note");
const actionMessage = document.getElementById("action-message");
const gameRootInput = document.getElementById("game-root");
const refreshBtn = document.getElementById("refresh-btn");
const snapRightBtn = document.getElementById("snap-right-btn");
const browseGameBtn = document.getElementById("browse-game-btn");
const installModBtn = document.getElementById("install-mod-btn");
const dismissSetupBtn = document.getElementById("dismiss-setup-btn");
const showSetupBtn = document.getElementById("show-setup-btn");
const setupCard = document.getElementById("setup-card");
const tabBar = document.getElementById("tab-bar");
const tabContent = document.getElementById("tab-content");
const updateCard = document.getElementById("update-card");
const updateTitle = document.getElementById("update-title");
const updateDetail = document.getElementById("update-detail");
const updateOpenBtn = document.getElementById("update-open-btn");
const updateDismissBtn = document.getElementById("update-dismiss-btn");
const appVersion = document.getElementById("app-version");

let latestStatus = null;
let actionBusy = false;
let manifest = null;
let activeTabId = "home";
let fieldValues = {};
let progressPollTimer = null;
let setupDismissed = false;
const catalogCache = new Map();
const catalogRowCache = new Map();
const multiselectState = new Map();
const multiselectRows = new Map();
const serialStoreEdit = new Map();
const itemPoolSelection = new Map();
const itemPoolRows = new Map();
let lastRosterSignature = "";
let lastGlobalPlayersSignature = "";
let pendingTargetIndex = null;
let pendingTargetUntil = 0;
let lastProgressHtml = "";
let lastChallengeStatus = null;
let lastUvhmStatus = null;
let pendingUpdateUrl = "";
const STATUS_CATALOG_TABS = new Set(["serials", "world", "vehicle", "progression"]);
const poolBrowserSignatures = new Map();

const TAB_ICONS = Object.freeze({
  home: "assets/bl4/tab-home.png",
  player: "assets/bl4/tab-player.png",
  keybinds: "emoji:⌨️",
  progression: "assets/bl4/tab-progression.png",
  loot: "assets/bl4/tab-loot.png",
  serials: "assets/bl4/tab-serials.png",
  mobility: "emoji:🏃",
  vehicle: "emoji:🏎️",
  damage: "assets/bl4/tab-damage.png",
  resources: "assets/bl4/tab-resources.png",
  world: "assets/bl4/tab-world.png",
  mob_io: "emoji:👾",
  activity: "assets/bl4/tab-support.png",
});

const ACTION_ICON_RULES = Object.freeze([
  [/\bcash\b/i, "assets/bl4/tab-cash.png"],
  [/cosmetic/i, "emoji:🎨"],
  [/max_sdu|backpack|bank/i, "emoji:🎒"],
  [/open.*reward|rewards_open/i, "emoji:🎁"],
  [/shiny/i, "assets/bl4/tab-home.png"],
  [/freecam/i, "emoji:🎥"],
  [/teleport|me.*target|target.*me/i, "emoji:↔️"],
  [/spawn|loot|drop|golden_chest/i, "assets/bl4/tab-loot.png"],
  [/serial|deliver|mail|reward/i, "assets/bl4/tab-serials.png"],
  [/currency|cash|eridium|resource|wallet/i, "assets/bl4/tab-resources.png"],
  [/experience|challenge|uvhm|progress/i, "assets/bl4/tab-progression.png"],
  [/damage|perk|god|rarity/i, "assets/bl4/tab-damage.png"],
  [/vehicle/i, "emoji:🏎️"],
  [/mobility|teleport|freecam|fly|speed|jump|glide|dash/i, "emoji:🏃"],
  [/mob|actor|npc|boss|\bio\b/i, "emoji:👾"],
  [/player|target|cosmetic|sdu|max_all|inventory/i, "assets/bl4/tab-player.png"],
]);

function setIconLabel(element, label, iconPath = "") {
  element.textContent = "";
  if (iconPath) {
    const emojiIcon = iconPath.startsWith("emoji:");
    const icon = document.createElement(emojiIcon ? "span" : "img");
    icon.className = emojiIcon ? "control-icon control-emoji" : "control-icon";
    if (emojiIcon) icon.textContent = iconPath.slice(6);
    else icon.src = iconPath;
    if (!emojiIcon) icon.alt = "";
    icon.setAttribute("aria-hidden", "true");
    element.appendChild(icon);
  }
  const text = document.createElement("span");
  text.textContent = label;
  element.appendChild(text);
}

function actionIcon(actionDef) {
  const searchable = `${actionDef?.action || ""} ${actionDef?.label || ""} ${JSON.stringify(actionDef?.payload || {})}`;
  return ACTION_ICON_RULES.find(([pattern]) => pattern.test(searchable))?.[1] || "";
}

function actionAccent(actionDef) {
  const searchable = `${actionDef?.action || ""} ${actionDef?.label || ""}`;
  if (/spawn|loot|drop|serial|deliver|mail|cosmetic|rarity|reward/i.test(searchable)) return "pink";
  if (/currency|cash|eridium|experience|challenge|player|target|mobility|teleport|freecam|vehicle|mob|npc|boss/i.test(searchable)) {
    return "cyan";
  }
  return "violet";
}

function decorateActionButton(button, label, actionDef) {
  button.dataset.accent = actionAccent(actionDef);
  setIconLabel(button, label, actionIcon(actionDef));
}

function actionsEnabled() {
  if (!latestStatus?.connected) return false;
  if (latestStatus.actionsAvailable === true) return true;
  if (latestStatus.state === "ready" || latestStatus.state === "connected") return true;
  const raw = latestStatus.raw || {};
  return Boolean(raw.actions_available || raw.has_local_pc || (raw.players && raw.players.length));
}

function renderUpdateStatus(result) {
  const current = String(result?.currentVersion || "").replace(/^v/i, "");
  if (appVersion) {
    appVersion.textContent = current ? `v${current}` : "Version unavailable";
  }

  if (!result?.ok || !result.updateAvailable || !result.latestVersion) {
    pendingUpdateUrl = "";
    updateCard?.classList.add("hidden");
    return;
  }

  const latest = String(result.latestVersion).replace(/^v/i, "");
  pendingUpdateUrl = result.releaseUrl || "";
  const appBehind = Boolean(result.appUpdateAvailable);
  const modBehind = Boolean(result.modUpdateAvailable);

  if (updateTitle) {
    if (appBehind) {
      updateTitle.textContent = `Download v${latest} from GitHub`;
    } else if (modBehind) {
      updateTitle.textContent = `Download the latest release (mod v${result.latestModVersion})`;
    } else {
      updateTitle.textContent = `Download the new version from GitHub`;
    }
  }
  if (updateDetail) {
    const lines = [];
    if (appBehind) {
      lines.push(
        `Your app is v${current || "unknown"}; GitHub has v${latest}. Download the portable zip, replace this EXE, then press Install / update mod folder and fully restart Borderlands 4.`
      );
    }
    if (modBehind) {
      lines.push(
        `Your mod is v${result.currentModVersion || "unknown"}; GitHub release includes mod v${result.latestModVersion}. Download the latest portable if needed, then Install / update mod folder and fully restart Borderlands 4.`
      );
    }
    if (!lines.length) {
      lines.push(
        `A newer Squ1ggs Boosting Tools release is on GitHub (v${latest}). Download it, then use Install / update mod folder.`
      );
    }
    updateDetail.textContent = lines.join(" ");
  }
  if (updateOpenBtn) {
    updateOpenBtn.textContent = "Download update";
  }
  updateCard?.classList.remove("hidden");
}

async function refreshUpdateStatus(force = false) {
  try {
    const modVersion = latestStatus?.raw?.mod_version || "";
    renderUpdateStatus(await window.sqbt.checkForUpdates(force, modVersion));
  } catch {
    updateCard?.classList.add("hidden");
    if (appVersion) appVersion.textContent = "Version unavailable";
  }
}

function playerNameForIndex(players, index) {
  if (Number(index) === -1) return "All players";
  const row = (players || []).find((p) => Number(p.index) === Number(index));
  return row?.name || "";
}

function applyTargetMeta(targetIdx, targetName) {
  if (Number(targetIdx) === -1 || targetName === "All players") {
    metaTarget.textContent = "All players";
  } else if (targetIdx != null && targetName) {
    metaTarget.textContent = `${targetName} (#${targetIdx})`;
  } else if (targetIdx != null) {
    metaTarget.textContent = `#${targetIdx}`;
  } else {
    metaTarget.textContent = "—";
  }
}

function effectiveTargetIndex(raw) {
  const remote = raw?.target_player_index;
  if (pendingTargetIndex != null && Date.now() < pendingTargetUntil) {
    if (remote != null && Number(remote) === Number(pendingTargetIndex)) {
      pendingTargetIndex = null;
      pendingTargetUntil = 0;
      return Number(remote);
    }
    return Number(pendingTargetIndex);
  }
  if (pendingTargetIndex != null && Date.now() >= pendingTargetUntil) {
    pendingTargetIndex = null;
    pendingTargetUntil = 0;
  }
  return remote;
}

function setStatusUi(payload) {
  latestStatus = payload;
  const state = payload?.state || "disconnected";
  statusDot.className = "status-dot " + state;
  statusHeadline.textContent = payload?.headline || "Unknown";
  statusDetail.textContent = payload?.detail || "";
  statusDetail.classList.remove("attention");
  const raw = payload?.raw || {};
  metaBridge.textContent = payload?.connected ? "Online" : "Offline";
  metaModVersion.textContent = raw.mod_version || "—";
  if (payload?.connected && raw.bridge_features && raw.bridge_features.manifest !== true) {
    statusDetail.textContent =
      (payload.detail || "") + " · Fully restart Borderlands 4 to load the latest mod version.";
    statusDetail.classList.add("attention");
  } else if (!payload?.connected) {
    const detail = String(payload?.detail || "");
    if (/install|sdk mod|restart/i.test(detail)) {
      statusDetail.classList.add("attention");
    }
  }
  metaSession.textContent = raw.session || "—";
  const targetIdx = effectiveTargetIndex(raw);
  if (raw && targetIdx != null && Number(targetIdx) !== Number(raw.target_player_index)) {
    raw.target_player_index = targetIdx;
    raw.target_player_name = playerNameForIndex(raw.players, targetIdx) || raw.target_player_name;
  }
  const targetName =
    Number(targetIdx) === -1
      ? "All players"
      : raw.target_player_name || playerNameForIndex(raw.players, targetIdx) || "";
  applyTargetMeta(targetIdx, targetName);
  metaSpawn.textContent = raw.spawn_anchor_label || raw.spawn_anchor || "—";
  if (metaFreecam) {
    const fc = raw.freecam || {};
    metaFreecam.textContent = fc.status || (fc.active ? "ON" : "OFF");
  }
  if (spawnAnchorSelect && raw.spawn_anchor) {
    spawnAnchorSelect.value = raw.spawn_anchor;
  }
  renderRoster(raw.players || [], targetIdx);
  refreshGlobalTargetSelect();
  refreshPlayerSelects();
  refreshActionButtons();
  if (
    payload?.connected &&
    Array.isArray(raw.players) &&
    raw.players.length &&
    (targetIdx == null || targetIdx === "") &&
    !(pendingTargetIndex != null && Date.now() < pendingTargetUntil)
  ) {
    selectTarget(Number(raw.players[0].index));
  }
  if (payload?.connected && STATUS_CATALOG_TABS.has(activeTabId)) {
    window.setTimeout(() => reloadCatalogSelects(), 0);
  }
  // Connected + game path known → never leave users stuck on the setup card.
  if (payload?.connected && (gameRootInput?.value || "").trim()) {
    hideSetupAfterConfigured(gameRootInput.value);
  }
  // Once the live mod version is known, re-check GitHub so an outdated mod
  // (even on a current EXE) can still show the update card.
  if (payload?.connected && raw.mod_version) {
    window.setTimeout(() => refreshUpdateStatus(false), 0);
  }
}

function renderRoster(players, targetIndex) {
  const signature = JSON.stringify(players) + ":" + String(targetIndex ?? "");
  if (signature === lastRosterSignature && rosterList.childElementCount > 0) {
    return;
  }
  lastRosterSignature = signature;
  rosterList.innerHTML = "";
  if (!players.length) {
    const li = document.createElement("li");
    li.textContent = "No players in roster yet.";
    rosterList.appendChild(li);
    return;
  }
  for (const row of players) {
    const li = document.createElement("li");
    if (row.index === targetIndex) li.classList.add("active");
    const name = document.createElement("span");
    name.textContent = row.name || `Player ${row.index}`;
    const idx = document.createElement("span");
    idx.className = "muted";
    idx.textContent = `#${row.index}`;
    li.append(name, idx);
    li.addEventListener("click", () => selectTarget(row.index));
    rosterList.appendChild(li);
  }
  refreshPlayerSelects();
}

function refreshActionButtons() {
  const enabled = actionsEnabled() && !actionBusy;
  tabContent.querySelectorAll("[data-run-action]").forEach((button) => {
    button.disabled = !enabled;
  });
  if (globalTargetSelect && latestStatus?.raw?.players?.length) {
    globalTargetSelect.disabled = !actionsEnabled();
  }
}

async function selectTarget(index) {
  actionMessage.textContent = "";
  const idx = Number(index);
  pendingTargetIndex = idx;
  pendingTargetUntil = Date.now() + 4000;
  if (latestStatus?.raw) {
    latestStatus.raw.target_player_index = idx;
    latestStatus.raw.target_player_name = playerNameForIndex(latestStatus.raw.players, idx);
  }
  applyTargetMeta(idx, playerNameForIndex(latestStatus?.raw?.players, idx));
  refreshGlobalTargetSelect();
  renderRoster(latestStatus?.raw?.players || [], idx);
  // Keep catalog "Send to" dropdowns aligned with Boost target so GZO/Lootlemon
  // deliveries match what users just clicked in the roster.
  for (const key of Object.keys(fieldValues)) {
    if (key.endsWith(":deliver_player_index")) {
      fieldValues[key] = String(idx);
    }
  }
  refreshPlayerSelects();
  try {
    const { data } = await window.sqbt.postAction("set_target_player", { player_index: idx });
    actionMessage.textContent = data?.message || "Target updated.";
    if (data?.ok === false) {
      pendingTargetIndex = null;
      pendingTargetUntil = 0;
      const remote = latestStatus?.raw?.target_player_index;
      const fallback =
        remote != null && remote !== ""
          ? Number(remote)
          : Number((latestStatus?.raw?.players || [])[0]?.index ?? 0);
      if (latestStatus?.raw) {
        latestStatus.raw.target_player_index = fallback;
        latestStatus.raw.target_player_name = playerNameForIndex(latestStatus.raw.players, fallback);
      }
      applyTargetMeta(fallback, playerNameForIndex(latestStatus?.raw?.players, fallback));
      refreshGlobalTargetSelect();
      renderRoster(latestStatus?.raw?.players || [], fallback);
      return;
    }
    const confirmed = data?.player_index != null ? Number(data.player_index) : idx;
    pendingTargetIndex = confirmed;
    pendingTargetUntil = Date.now() + 2500;
    if (latestStatus?.raw) {
      latestStatus.raw.target_player_index = confirmed;
      latestStatus.raw.target_player_name =
        data?.name || playerNameForIndex(latestStatus.raw.players, confirmed);
    }
    applyTargetMeta(confirmed, latestStatus?.raw?.target_player_name || "");
    refreshGlobalTargetSelect();
    renderRoster(latestStatus?.raw?.players || [], confirmed);
  } catch (error) {
    pendingTargetIndex = null;
    pendingTargetUntil = 0;
    actionMessage.textContent = `Target update failed: ${String(error?.message || error)}`;
  }
}

async function selectSpawnAnchor(anchor) {
  actionMessage.textContent = "";
  const { data } = await window.sqbt.postAction("set_spawn_anchor", { spawn_anchor: anchor });
  actionMessage.textContent = data?.message || "Spawn location updated.";
}

function sectionKey(tabId, section) {
  return `${tabId}:${section.title}`;
}

function actionFieldKey(sectionId, actionDef, field) {
  return `${sectionId}:${actionDef.action}:${field.key}`;
}

function sectionFieldKey(sectionId, field) {
  return `${sectionId}:__section__:${field.key}`;
}

function fieldStorageKey(sectionId, actionDef, field) {
  if (actionDef?.action === "__section__") {
    return sectionFieldKey(sectionId, field);
  }
  return actionFieldKey(sectionId, actionDef, field);
}

function mergeSectionFieldsIntoPayload(sectionId, payload) {
  if (!manifest?.tabs?.length) {
    return payload;
  }
  const colon = sectionId.indexOf(":");
  if (colon < 0) {
    return payload;
  }
  const tabId = sectionId.slice(0, colon);
  const sectionTitle = sectionId.slice(colon + 1);
  const tab = manifest.tabs.find((row) => row.id === tabId);
  const section = tab?.sections?.find((row) => row.title === sectionTitle);
  for (const field of section?.fields || []) {
    const key = sectionFieldKey(sectionId, field);
    let value = fieldValues[key];
    if (value === undefined || value === "") {
      value = field.default ?? "";
    }
    if (field.type === "number") {
      if (value === "" || value == null) {
        continue;
      }
      value = Number(value);
    }
    payload[field.key] = value;
  }
  return payload;
}

function fieldKey(sectionId, field) {
  return `${sectionId}:${field.key}`;
}

function catalogCacheKey(name, params) {
  return `${name}:${JSON.stringify(params || {})}`;
}

function formatCatalogError(catalogName, error) {
  const text = String(error?.message || error || "Catalog unavailable.");
  const lower = text.toLowerCase();
  if (catalogName === "gzo" || lower.includes("gzo")) {
    return "No GZO cache — open the GZO tab in-game once to refresh, then Retry.";
  }
  if (catalogName === "lootlemon" || lower.includes("lootlemon")) {
    return "No Lootlemon cache — open the Lootlemon tab in-game once to refresh, then Retry.";
  }
  if (catalogName === "serial_store") {
    return "No saved serials yet — save entries in My Library below.";
  }
  if (lower.includes("abort") || lower.includes("fetch") || lower.includes("unreachable")) {
    return "Connect in-game first, then click Retry or refocus the dropdown.";
  }
  return text;
}

async function loadCatalog(name, params = {}) {
  const key = catalogCacheKey(name, params);
  if (catalogCache.has(key)) {
    return catalogCache.get(key);
  }
  const result = await window.sqbt.getCatalog(name, params);
  if (!result.ok) {
    throw new Error(result.message || "Catalog unavailable.");
  }
  catalogCache.set(key, result.data);
  return result.data;
}

function applyCatalogSelection(sectionId, actionDef, field, selectEl, fieldKey) {
  fieldValues[fieldKey] = selectEl.value;
  const rows = catalogRowCache.get(fieldKey) || [];
  const valueKey = field.valueKey || "id";
  const row = rows.find((entry) => String(entry[valueKey] || "") === selectEl.value);
  if (field.sendEntry && row) {
    fieldValues[`${fieldKey}:entry`] = row;
  } else {
    delete fieldValues[`${fieldKey}:entry`];
  }
  if (field.fillField) {
    const targetKey = actionFieldKey(sectionId, actionDef, { key: field.fillField });
    fieldValues[targetKey] = selectEl.value;
  }
}

function catalogParamsForField(sectionId, field, actionDef) {
  const params = {};
  if (field.catalogParam) {
    params[field.catalogParam] =
      fieldValues[actionFieldKey(sectionId, actionDef, { key: field.catalogParam })] ||
      fieldValues[fieldKey(sectionId, { key: field.catalogParam })] ||
      "";
  }
  for (const dep of field.catalogParamsFrom || []) {
    params[dep] =
      fieldValues[actionFieldKey(sectionId, actionDef, { key: dep })] ||
      fieldValues[fieldKey(sectionId, { key: dep })] ||
      "";
  }
  if (field.search) {
    params.search =
      fieldValues[`${actionFieldKey(sectionId, actionDef, field)}:search`] ||
      fieldValues[`${fieldKey(sectionId, field)}:search`] ||
      "";
  }
  return params;
}

function multiselectParams(sectionId, config) {
  const params = { limit: 500 };
  params.search = fieldValues[`${sectionId}:search`] || "";
  for (const filter of config.filters || []) {
    const param = filter.catalogParam || filter.key;
    params[param] = fieldValues[`${sectionId}:${filter.key}`] ?? filter.default ?? "";
  }
  return params;
}

function multiselectRowId(row, config) {
  const idKey = config.idKey || config.valueKey || "id";
  return String(row[idKey] || row.serial || row.id || "");
}

const WORLD_SPAWN_ACTIONS = new Set([
  "shiny_drop_all",
  "spawn_item_pool",
  "spawn_item_pool_all",
  "spawn_mix",
  "spawn_mob",
  "spawn_mobs",
  "spawn_io",
  "spawn_ios",
  "spawn_encounter",
]);

function getMultiselectConfig(sectionId) {
  const box = tabContent.querySelector(`[data-multiselect-section="${sectionId}"]`);
  if (!box?.dataset.multiselectConfig) return {};
  try {
    return JSON.parse(box.dataset.multiselectConfig);
  } catch {
    return {};
  }
}

function preferredDeliveryPlayerIndex(players) {
  const list = Array.isArray(players) ? players : [];
  // Prefer the Boost target dropdown the user is looking at over a stale status index.
  if (globalTargetSelect && !globalTargetSelect.disabled && globalTargetSelect.value !== "") {
    const fromUi = Number(globalTargetSelect.value);
    if (!Number.isNaN(fromUi)) {
      if (fromUi === -1) return -1;
      if (list.some((row) => Number(row.index) === fromUi)) return fromUi;
    }
  }
  const target = effectiveTargetIndex(latestStatus?.raw || {});
  if (target != null && Number(target) === -1) return -1;
  if (target != null && list.some((row) => Number(row.index) === Number(target))) {
    return Number(target);
  }
  const host = list.find((row) => row.is_host || row.host);
  if (host) return Number(host.index);
  if (list.length) return Number(list[0].index);
  return 0;
}

function enrichPayload(action, payload) {
  const next = { ...(payload || {}) };
  if (WORLD_SPAWN_ACTIONS.has(action) && spawnAnchorSelect?.value && !next.spawn_anchor) {
    next.spawn_anchor = spawnAnchorSelect.value;
  }
  // Stamp the EXE boost-target index for player-scoped boosts when the action
  // did not already choose a specific index (e.g. typed kick field).
  const BOOST_TARGET_ACTIONS = new Set([
    "challenge_bulk_start",
    "challenge_complete_selected",
    "uvhm_start",
    "give_currency",
    "give_experience",
    "max_all",
    "max_cash",
    "max_eridium",
    "max_sdu",
    "inventory_set_sizes",
    "shiny_mail_all",
    "teleport_party",
    "party_kick",
    "shiny_drop_all",
    "devperk_activate",
    "weapons_restricted",
    "ammo_regen",
    "vehicle_actions_locked",
  ]);
  // These actions need a single concrete player — never stamp "All players" (-1).
  const BOOST_TARGET_NO_ALL = new Set(["party_kick", "teleport_party", "uvhm_start"]);
  const existing = next.player_index;
  const hasExplicit =
    existing !== undefined && existing !== null && existing !== "";
  if (BOOST_TARGET_ACTIONS.has(action) && !hasExplicit) {
    const idx = preferredDeliveryPlayerIndex(latestStatus?.raw?.players || []);
    if (idx != null && idx !== "") {
      if (!(Number(idx) === -1 && BOOST_TARGET_NO_ALL.has(action))) {
        next.player_index = Number(idx);
      }
    }
  }
  return next;
}

function applyDeliveryRecipient(payload, sectionId) {
  const players = latestStatus?.raw?.players || [];
  let playerIndex = fieldValues[`${sectionId}:deliver_player_index`];
  if (playerIndex === undefined || playerIndex === "") {
    playerIndex = preferredDeliveryPlayerIndex(players);
  }
  const n = Number(playerIndex);
  payload.player_index = n;
  payload.mode = n === -1 ? "all" : "player";
  const openRaw = fieldValues[`${sectionId}:open_rewards`];
  if (openRaw === undefined || openRaw === "" || openRaw === "yes" || openRaw === true) {
    payload.open_rewards = true;
  } else {
    payload.open_rewards = openRaw === "no" || openRaw === false ? false : Boolean(openRaw);
  }
  return payload;
}

function poolBrowserRowId(row) {
  const pool = String(row.itempool || "");
  const catalog = String(row.catalog_key || "");
  return `${catalog}|${pool}`;
}

function poolBrowserParams(sectionId, config) {
  const search = fieldValues[`${sectionId}:search`] || "";
  let category = fieldValues[`${sectionId}:category`] ?? config.defaultCategory ?? "All";
  const needle = search.trim().toLowerCase();
  if (needle.includes("shiny") && category === "All") {
    category = "Shiny";
  }
  return { search, category, limit: 2000 };
}

function applyItemPoolPayload(sectionId, payload) {
  const search = fieldValues[`${sectionId}:search`] || "";
  let category = fieldValues[`${sectionId}:category`] || "All";
  if (search.trim().toLowerCase().includes("shiny") && category === "All") {
    category = "Shiny";
  }
  payload.search = search;
  payload.category = category;
  const selected = itemPoolSelection.get(sectionId);
  if (selected) {
    payload.entry = selected;
    if (!payload.itempool && selected.itempool) payload.itempool = selected.itempool;
    if (!payload.display_name && selected.display_name) payload.display_name = selected.display_name;
    if (!payload.catalog_key && selected.catalog_key) payload.catalog_key = selected.catalog_key;
  }
  return payload;
}

function collectPayload(sectionId, actionDef) {
  const payload = { ...(actionDef.payload || {}) };
  mergeSectionFieldsIntoPayload(sectionId, payload);

  if (actionDef.action === "spawn_item_pool" || actionDef.action === "spawn_item_pool_all") {
    applyItemPoolPayload(sectionId, payload);
    for (const field of actionDef.fields || []) {
      const key = actionFieldKey(sectionId, actionDef, field);
      let value = fieldValues[key];
      if (value === undefined || value === "") {
        value = field.default ?? "";
      }
      if (field.type === "number") {
        if (value === "" || value == null) continue;
        value = Number(value);
      }
      payload[field.key] = value;
    }
    return payload;
  }

  if (actionDef.deliverMultiselect) {
    const selected = multiselectState.get(sectionId) || new Set();
    const rows = multiselectRows.get(sectionId) || [];
    const config = getMultiselectConfig(sectionId);
    payload.serials = rows
      .filter((row) => selected.has(multiselectRowId(row, config)))
      .map((row) => String(row.serial || row[config.valueKey || "serial"] || "").trim())
      .filter((serial) => serial.startsWith("@U") || (serial.includes(",") && /\d/.test(serial)));
    if (fieldValues[`${sectionId}:level_override`] === "yes") {
      payload.level_override = true;
      payload.level = Number(fieldValues[`${sectionId}:level`] || 60);
    }
    payload._selected_count = selected.size;
    return applyDeliveryRecipient(payload, sectionId);
  }

  if (actionDef.spawnMultiselect) {
    const selected = multiselectState.get(sectionId) || new Set();
    const rows = multiselectRows.get(sectionId) || [];
    const config = getMultiselectConfig(sectionId);
    const valueKey = config.valueKey || "code";
    const values = rows
      .filter((row) => selected.has(multiselectRowId(row, config)))
      .map((row) => String(row[valueKey] || "").trim())
      .filter(Boolean);
    if (actionDef.action === "spawn_ios") {
      payload.cmds = values;
    } else {
      payload.codes = values;
    }
  }

  if (actionDef.challengeMultiselect) {
    const selected = multiselectState.get(sectionId) || new Set();
    const rows = multiselectRows.get(sectionId) || [];
    const config = getMultiselectConfig(sectionId);
    payload.tokens = rows
      .filter((row) => selected.has(multiselectRowId(row, config)))
      .map((row) => String(row.token || row[config.valueKey || "token"] || "").trim())
      .filter(Boolean);
  }

  if (actionDef.deliverStore) {
    // Same selection/serial rules as GZO/Lootlemon deliverMultiselect.
    // Previously only accepted @U and matched row.id loosely, so human serials
    // and some selected rows were dropped → "no serials" / silent no-op.
    const selected = multiselectState.get(sectionId) || new Set();
    const rows = multiselectRows.get(sectionId) || [];
    const config = getMultiselectConfig(sectionId);
    payload.serials = rows
      .filter((row) => selected.has(multiselectRowId(row, config)))
      .map((row) => String(row.serial || row[config.valueKey || "serial"] || "").trim())
      .filter((serial) => serial.startsWith("@U") || (serial.includes(",") && /\d/.test(serial)));
    if (fieldValues[`${sectionId}:level_override`] === "yes") {
      payload.level_override = true;
      payload.level = Number(fieldValues[`${sectionId}:level`] || 60);
    }
    payload._selected_count = selected.size;
    return applyDeliveryRecipient(payload, sectionId);
  }

  if (actionDef.action === "serial_store_save") {
    syncSerialStoreEditFromForm(sectionId);
    const edit = serialStoreEdit.get(sectionId) || {};
    payload.id = edit.id || "";
    payload.name = edit.name || "";
    payload.group = edit.group || "Default";
    payload.serial = edit.serial || "";
    return payload;
  }

  if (actionDef.action === "serial_store_delete") {
    payload.ids = [...(multiselectState.get(sectionId) || new Set())];
    return payload;
  }

  if (actionDef.action === "serial_store_duplicate") {
    const edit = serialStoreEdit.get(sectionId) || {};
    payload.id = edit.id || [...(multiselectState.get(sectionId) || [])][0] || "";
    return payload;
  }

  for (const field of actionDef.fields || []) {
    const key = actionFieldKey(sectionId, actionDef, field);
    if (field.type === "hidden") {
      payload[field.key] = fieldValues[key] ?? field.default ?? "";
      continue;
    }
    if (field.type === "select" && field.catalogParam) {
      continue;
    }
    if (field.type === "catalog_select" && field.fillField) {
      const serial = fieldValues[key] || "";
      if (field.fillAsSerial) {
        payload[field.fillField] = serial ? [serial] : [];
      } else {
        payload[field.fillField] = serial;
      }
      continue;
    }
    if (field.type === "catalog_select") {
      payload[field.key] = fieldValues[key] ?? "";
      continue;
    }
    let value = fieldValues[key];
    if (value === undefined || value === "") {
      value = field.default ?? "";
    }
    if (field.type === "number") {
      if (value === "" || value == null) {
        continue;
      }
      value = Number(value);
    }
    if (field.type === "player_select") {
      if (value === "" || value == null) {
        value = preferredDeliveryPlayerIndex(latestStatus?.raw?.players || []);
      }
      payload.player_index = Number(value);
      if (actionDef.action === "deliver_serials") {
        payload.mode = Number(value) === -1 ? "all" : "player";
      }
      continue;
    }
    if (field.key === "open_rewards") {
      payload.open_rewards = String(value).toLowerCase() === "yes" || value === true;
      continue;
    }
    if (field.key === "level_override") {
      payload.level_override = String(value).toLowerCase() === "yes" || value === true;
      continue;
    }
    if (field.type === "textarea" && field.key === "serials") {
      payload.serials = String(value)
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.startsWith("@U") || (line.includes(",") && /\d/.test(line)));
      continue;
    }
    payload[field.key] = value;
  }
  for (const field of actionDef.fields || []) {
    if (field.type !== "catalog_select" || !field.sendEntry) {
      continue;
    }
    const key = actionFieldKey(sectionId, actionDef, field);
    const entry = fieldValues[`${key}:entry`];
    if (entry && typeof entry === "object") {
      payload.entry = entry;
      if (!payload.itempool && entry.itempool) payload.itempool = entry.itempool;
      if (!payload.display_name && entry.display_name) payload.display_name = entry.display_name;
      if (!payload.catalog_key && entry.catalog_key) payload.catalog_key = entry.catalog_key;
    }
  }
  if (actionDef.action === "deliver_serials") {
    if (payload.level != null && payload.level !== "") {
      payload.level = Number(payload.level);
    }
    if (payload.open_rewards === undefined) {
      payload.open_rewards = true;
    }
    if (payload.player_index === undefined || payload.player_index === "") {
      payload.player_index = preferredDeliveryPlayerIndex(latestStatus?.raw?.players || []);
      payload.mode = Number(payload.player_index) === -1 ? "all" : "player";
    }
  }
  return payload;
}

async function runAction(action, payload, confirmText, context = {}) {
  if (confirmText && !window.confirm(confirmText)) {
    return;
  }
  if (action === "set_target_player" && (payload.player_index === undefined || payload.player_index === "")) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = "Pick a player in the dropdown first.";
    return;
  }
  actionBusy = true;
  refreshActionButtons();
  actionMessage.className = "action-message muted";
  actionMessage.textContent = "Running…";
  const finalPayload = enrichPayload(action, payload);
  let timeout = 12;
  if (action === "shiny_drop_all") {
    timeout = 20;
  } else if (action === "spawn_item_pool" || action === "spawn_item_pool_all") {
    timeout = 45;
  } else if (action === "spawn_mobs" || action === "spawn_ios") {
    timeout = 30;
  } else if (action === "gzo_refresh_start" || action === "lootlemon_refresh_start") {
    timeout = 30;
  }
  if (action === "deliver_serials") {
    const selectedHint = Number(finalPayload._selected_count || 0);
    delete finalPayload._selected_count;
    if (!Array.isArray(finalPayload.serials) || !finalPayload.serials.length) {
      actionMessage.className = "action-message error";
      actionMessage.textContent =
        selectedHint > 0
          ? "Selected library entries have no usable serial (@U or human like 300, 0, 1, 60| …). Re-save them or pick different rows."
          : "Tick at least one serial in the list (or paste @U / human serials) first. Use Send to for the recipient.";
      actionBusy = false;
      refreshActionButtons();
      return;
    }
    let deliverIdx = finalPayload.player_index;
    if (deliverIdx === undefined || deliverIdx === "" || Number.isNaN(Number(deliverIdx))) {
      deliverIdx = preferredDeliveryPlayerIndex(latestStatus?.raw?.players || []);
    }
    finalPayload.player_index = Number(deliverIdx);
    finalPayload.mode = Number(finalPayload.player_index) === -1 ? "all" : "player";
    if (finalPayload.open_rewards === undefined) {
      finalPayload.open_rewards = true;
    }
  }
  if (
    (action === "spawn_mobs" && !(finalPayload.codes || []).length) ||
    (action === "spawn_ios" && !(finalPayload.cmds || []).length)
  ) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = "Tick at least one entry in the list first.";
    actionBusy = false;
    refreshActionButtons();
    return;
  }
  if (action === "challenge_complete_selected" && !(finalPayload.tokens || []).length) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = "Tick at least one challenge first.";
    actionBusy = false;
    refreshActionButtons();
    return;
  }
  if (action === "spawn_item_pool" && !finalPayload.entry && !finalPayload.itempool) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = "Select a pool from the filtered list above first.";
    actionBusy = false;
    refreshActionButtons();
    return;
  }
  try {
    const { httpStatus, data } = await window.sqbt.postAction(action, finalPayload, timeout);
    if (data?.ok === false || httpStatus === 202) {
      actionMessage.className = "action-message error";
    }
    actionMessage.textContent = data?.message || JSON.stringify(data);
    if (action === "activity_log" && data?.lines) {
      renderActivityLog(data.lines);
    }
    if (action === "mobility_status" || action === "mobility_apply" || action === "mobility_load_preset") {
      applyMobilityValues(data?.current || data?.values);
      renderMobilityStatus(data);
    }
    if (action === "serial_convert") {
      renderSerialConvertResult(data);
    }
    if (action.startsWith("tuning_") && data?.values) {
      applyFieldValues(data.values);
    }
    if (action === "challenge_bulk_start" || action === "uvhm_start" || action === "uvhm_start_all") {
      const panel = document.getElementById("sqbt-progress-panel");
      if (panel) {
        panel.classList.remove("hidden");
        if (action === "challenge_bulk_start") {
          lastChallengeStatus = {
            active: true,
            queued: true,
            index: 0,
            total: 1,
            message: "Starting…",
          };
        } else {
          lastUvhmStatus = {
            active: true,
            queued: true,
            running: true,
            progress_index: 0,
            progress_total: 7,
            message: "Starting…",
          };
        }
        lastProgressHtml = "";
        renderProgressPanel(null, null);
      }
      startProgressPoll();
    }
    if (action === "max_all" || action === "shiny_drop_all" || action === "deliver_serials") {
      actionMessage.textContent = data?.message || actionMessage.textContent;
      if (action === "shiny_drop_all" && data?.ok) {
        window.setTimeout(async () => {
          try {
            const { data: statusData } = await window.sqbt.postAction("shiny_drop_status", {});
            if (statusData?.status || statusData?.message) {
              actionMessage.textContent = `${data.message} · ${statusData.status || statusData.message}`;
            }
          } catch {
            /* ignore status poll errors */
          }
        }, 800);
      }
    }
    if (action === "serial_store_save" && data?.entry && context.sectionId) {
      serialStoreEdit.set(context.sectionId, { ...data.entry });
      refreshMultiselectSection(context.sectionId, context.config || { catalog: "serial_store" });
    }
    if (
      (action === "serial_store_delete" || action === "serial_store_duplicate") &&
      context.sectionId
    ) {
      if (data?.entry && context.sectionId) {
        serialStoreEdit.set(context.sectionId, { ...data.entry });
      }
      refreshMultiselectSection(context.sectionId, context.config || { catalog: "serial_store" });
    }
    if (action === "challenge_bulk_status") {
      renderProgressPanel(data?.challenge, null);
    }
    if (action === "uvhm_status") {
      renderProgressPanel(null, data?.uvhm);
    }
  } catch (error) {
    const text = String(error?.message || error);
    if (/fetch failed|aborted|network|econnrefused/i.test(text)) {
      actionMessage.className = "action-message attention";
      actionMessage.textContent =
        "Lost connection to Borderlands 4 (the game may have crashed or is still loading). " +
        "Fully restart Borderlands 4, wait for it to finish loading, then retry.";
    } else {
      actionMessage.className = "action-message error";
      actionMessage.textContent = text;
    }
  } finally {
    actionBusy = false;
    refreshActionButtons();
  }
}

function applyFieldValues(values) {
  if (!values || typeof values !== "object") return;
  for (const [key, value] of Object.entries(values)) {
    for (const node of tabContent.querySelectorAll("[data-field-key]")) {
      const fk = node.dataset.fieldKey || "";
      if (!fk.endsWith(`:${key}`)) continue;
      const input = node.querySelector("input, select, textarea");
      if (!input) continue;
      input.value = String(value);
      fieldValues[fk] = input.value;
    }
  }
}

function stopProgressPoll() {
  if (progressPollTimer) {
    clearInterval(progressPollTimer);
    progressPollTimer = null;
  }
}

function isChallengeBusy(challenge) {
  return Boolean(challenge && (challenge.active || challenge.queued));
}

function isUvhmBusy(uvhm) {
  return Boolean(uvhm && (uvhm.active || uvhm.queued || uvhm.running));
}

function renderProgressPanel(challenge, uvhm) {
  const panel = document.getElementById("sqbt-progress-panel");
  if (!panel) return;

  // null means keep cached value (manual status for one job must not wipe the other).
  if (challenge !== null) lastChallengeStatus = challenge;
  if (uvhm !== null) lastUvhmStatus = uvhm;

  const challengeState = lastChallengeStatus;
  const uvhmState = lastUvhmStatus;

  const clampPct = (value, total) => {
    const safeTotal = Math.max(1, Number(total || 0));
    const safeValue = Math.max(0, Number(value || 0));
    return Math.min(100, Math.max(0, Math.round((safeValue / safeTotal) * 100)));
  };

  const challengeBusy = isChallengeBusy(challengeState);
  const uvhmBusy = isUvhmBusy(uvhmState);
  const busy = challengeBusy || uvhmBusy;

  let html = "";
  if (challengeBusy) {
    const total = Math.max(1, Number(challengeState.total || challengeState.progress_total || 0));
    const index = Math.max(0, Number(challengeState.index || challengeState.progress_index || 0));
    const pct = clampPct(index, total);
    const detail = challengeState.message || `Queued · ${index}/${total}`;
    const token = challengeState.token ? ` · ${challengeState.token}` : "";
    html += `<h4>Challenge bulk</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${index}/${total} · OK ${challengeState.ok || 0} · fail ${challengeState.failed || 0}${token}</p>
      <p class="progress-meta muted">${detail}</p>`;
  }
  if (uvhmBusy) {
    const total = Math.max(1, Number(uvhmState.progress_total || uvhmState.total || uvhmState.steps_total || 7));
    const index = Math.max(0, Number(uvhmState.progress_index || uvhmState.index || uvhmState.step || 0));
    const pct = clampPct(index, total);
    const detail = uvhmState.message || `Step ${index}/${total}`;
    html += `<h4>UVHM progression</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${detail}</p>`;
  }

  let nextHtml = html;
  if (busy) {
    panel.classList.remove("hidden");
  } else if (activeTabId === "progression") {
    panel.classList.remove("hidden");
    nextHtml = `<p class="muted">No active challenge or UVHM job. Start one below.</p>`;
  } else {
    panel.classList.add("hidden");
    nextHtml = "";
  }

  if (nextHtml === lastProgressHtml) {
    return;
  }
  lastProgressHtml = nextHtml;
  panel.innerHTML = nextHtml;
}

async function pollProgressOnce() {
  if (!actionsEnabled()) return;
  try {
    const [challengeRes, uvhmRes] = await Promise.all([
      window.sqbt.postAction("challenge_bulk_status", {}),
      window.sqbt.postAction("uvhm_status", {}),
    ]);
    const challenge = challengeRes.data?.challenge ?? null;
    const uvhm = uvhmRes.data?.uvhm ?? null;
    // Poll always refreshes both caches (unlike manual single-job status).
    lastChallengeStatus = challenge;
    lastUvhmStatus = uvhm;
    renderProgressPanel(null, null);
    const busy = isChallengeBusy(challenge) || isUvhmBusy(uvhm);
    if (busy) {
      if (!progressPollTimer) {
        progressPollTimer = setInterval(() => {
          pollProgressOnce();
        }, 800);
      }
    } else {
      stopProgressPoll();
    }
  } catch {
    /* bridge may be busy */
  }
}

function startProgressPoll() {
  stopProgressPoll();
  lastProgressHtml = "";
  pollProgressOnce();
}

function refreshGlobalTargetSelect() {
  if (!globalTargetSelect) return;
  const players = latestStatus?.raw?.players || [];
  const targetIndex = effectiveTargetIndex(latestStatus?.raw || {});
  const previous = globalTargetSelect.value;
  const playersSig = JSON.stringify(players);
  const needsRebuild = playersSig !== lastGlobalPlayersSignature || globalTargetSelect.options.length === 0;
  if (!players.length) {
    lastGlobalPlayersSignature = playersSig;
    globalTargetSelect.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = actionsEnabled() ? "No players in lobby" : "Connect in-game…";
    globalTargetSelect.appendChild(opt);
    globalTargetSelect.disabled = true;
    return;
  }
  globalTargetSelect.disabled = !actionsEnabled();
  if (needsRebuild) {
    // Avoid wiping an open dropdown mid-click — only rebuild when roster changes.
    const open = document.activeElement === globalTargetSelect;
    if (!open) {
      lastGlobalPlayersSignature = playersSig;
      globalTargetSelect.innerHTML = "";
      const allOpt = document.createElement("option");
      allOpt.value = "-1";
      allOpt.textContent = "All players";
      globalTargetSelect.appendChild(allOpt);
      for (const row of players) {
        const opt = document.createElement("option");
        opt.value = String(row.index);
        opt.textContent = `${row.name || `Player ${row.index}`} (#${row.index})`;
        globalTargetSelect.appendChild(opt);
      }
    }
  }
  const next =
    targetIndex != null && (Number(targetIndex) === -1 || players.some((row) => Number(row.index) === Number(targetIndex)))
      ? String(targetIndex)
      : previous;
  if (next !== "" && [...globalTargetSelect.options].some((opt) => opt.value === next)) {
    if (globalTargetSelect.value !== next) {
      globalTargetSelect.value = next;
    }
  }
}

function refreshPlayerSelects() {
  refreshGlobalTargetSelect();
  const players = latestStatus?.raw?.players || [];
  for (const select of tabContent.querySelectorAll("select[data-role='player-select']")) {
    if (select === globalTargetSelect) continue;
    const fieldWrap = select.closest("[data-field-key]");
    const fieldKeyName = fieldWrap?.dataset.fieldKey || "";
    const deliverKey = select.dataset.deliverPlayerKey || "";
    const includeAll = select.dataset.includeAll === "1" || Boolean(deliverKey);
    let current = deliverKey
      ? fieldValues[deliverKey]
      : fieldValues[fieldKeyName] || select.value || "";
    if (current === undefined || current === "") {
      current = String(preferredDeliveryPlayerIndex(players));
      if (deliverKey) fieldValues[deliverKey] = current;
      else if (fieldKeyName) fieldValues[fieldKeyName] = current;
    }
    select.innerHTML = "";
    if (includeAll) {
      const allOpt = document.createElement("option");
      allOpt.value = "-1";
      allOpt.textContent = "All players";
      select.appendChild(allOpt);
    }
    for (const row of players) {
      const opt = document.createElement("option");
      opt.value = String(row.index);
      opt.textContent = `${row.name || `Player ${row.index}`} (#${row.index})`;
      select.appendChild(opt);
    }
    if (!players.length) {
      const opt = document.createElement("option");
      opt.value = "0";
      opt.textContent = actionsEnabled() ? "Host (#0)" : "Connect in-game…";
      select.appendChild(opt);
      current = "0";
    }
    if (![...select.options].some((opt) => opt.value === String(current))) {
      current = String(preferredDeliveryPlayerIndex(players));
    }
    select.value = String(current);
    if (deliverKey) fieldValues[deliverKey] = select.value;
    else if (fieldKeyName) fieldValues[fieldKeyName] = select.value;
  }
}

function reloadCatalogSelects() {
  for (const node of tabContent.querySelectorAll("[data-role='catalog-select']")) {
    const select = node.tagName === "SELECT" ? node : node.querySelector("select");
    if (!select) continue;
    const fieldJson = node.dataset.catalogField;
    const sectionId = node.dataset.sectionId;
    if (!fieldJson || !sectionId) continue;
    try {
      const field = JSON.parse(fieldJson);
      const actionDef = { action: node.dataset.actionName || "catalog" };
      populateCatalogSelect(select, field, sectionId, actionDef, node);
    } catch {
      /* ignore parse errors */
    }
  }
  for (const box of tabContent.querySelectorAll("[data-multiselect-section]")) {
    const sectionId = box.dataset.multiselectSection;
    const configJson = box.dataset.multiselectConfig;
    if (!sectionId || !configJson) continue;
    try {
      const config = JSON.parse(configJson);
      if (config.localOnly || config.catalog === "serial_send_list") {
        renderSerialSendListRows(sectionId, box);
        continue;
      }
      refreshMultiselectSection(sectionId, config);
    } catch {
      /* ignore */
    }
  }
}

function updateSetupVisibility(setup) {
  setupDismissed = Boolean(setup?.setupDismissed);
  const hasPath = Boolean((setup?.gameRoot || "").trim());
  // Once a game folder is known, keep the big setup card collapsed so tabs stay usable.
  // Users can reopen it with "Show setup".
  const hide = setupDismissed || hasPath;
  if (setupCard) setupCard.classList.toggle("is-hidden", hide);
  if (showSetupBtn) showSetupBtn.classList.toggle("hidden", !hide);
}

function hideSetupAfterConfigured(gameRoot) {
  const root = String(gameRoot || gameRootInput?.value || "").trim();
  setupDismissed = true;
  updateSetupVisibility({ gameRoot: root, setupDismissed: true });
  if (root) {
    window.sqbt.dismissSetup().catch(() => {});
  }
}

function applyMobilityValues(current) {
  if (!current || typeof current !== "object") return;
  for (const [key, value] of Object.entries(current)) {
    for (const node of tabContent.querySelectorAll("[data-field-key]")) {
      const fk = node.dataset.fieldKey || "";
      if (!fk.endsWith(`:${key}`)) continue;
      const input = node.querySelector("input, select, textarea");
      if (!input) continue;
      if (key === "zero_vault_costs") {
        input.value = value ? "yes" : "no";
        fieldValues[fk] = input.value;
        continue;
      }
      input.value = String(value);
      fieldValues[fk] = input.value;
    }
  }
}

function renderMobilityStatus(data) {
  if (!data) return;
  let panel = document.getElementById("mobility-status-panel");
  if (!panel) {
    panel = document.createElement("pre");
    panel.id = "mobility-status-panel";
    panel.className = "activity-log";
    tabContent.appendChild(panel);
  }
  const lines = [
    data.message || "",
    data.infinite_jump_label ? `Infinite jump: ${data.infinite_jump_label}` : "",
    data.noclip != null ? `Noclip: ${data.noclip ? "ON" : "OFF"}` : "",
    data.time_dilation != null ? `Time dilation: ${data.time_dilation}x` : "",
    data.current ? `Current: ${JSON.stringify(data.current, null, 2)}` : "",
  ].filter(Boolean);
  panel.textContent = lines.join("\n\n");
}

function renderSerialConvertResult(data) {
  if (!data) return;
  let panel = document.getElementById("serial-convert-panel");
  if (!panel) {
    panel = document.createElement("pre");
    panel.id = "serial-convert-panel";
    panel.className = "result-panel activity-log";
    tabContent.appendChild(panel);
  }
  const lines = [];
  if (Array.isArray(data.results) && data.results.length) {
    lines.push(`Converted ${data.results.length} serial(s):`);
    for (const row of data.results) {
      lines.push(`@U: ${row.serial || ""}`);
      lines.push(`Human: ${String(row.human || "").slice(0, 500)}`);
      lines.push("");
    }
  } else {
    lines.push(data.message || "");
    if (data.serial) lines.push(`@U serial: ${data.serial}`);
    if (data.human) lines.push(`Human: ${String(data.human).slice(0, 800)}`);
  }
  if (Array.isArray(data.errors) && data.errors.length) {
    lines.push("Errors:");
    lines.push(...data.errors.map((e) => String(e)));
  }
  panel.textContent = lines.filter((line, idx, arr) => !(line === "" && arr[idx - 1] === "")).join("\n");
}

function renderSerialSendList(section, sectionId, sectionEl) {
  const box = document.createElement("div");
  box.className = "multiselect-box serial-send-list";
  box.dataset.multiselectSection = sectionId;
  box.dataset.multiselectConfig = JSON.stringify({
    catalog: "serial_send_list",
    kind: "serial",
    valueKey: "serial",
    labelKey: "title",
    idKey: "id",
    // Client-side queue only — never hit the SDK catalog bridge.
    localOnly: true,
  });

  const addWrap = document.createElement("label");
  addWrap.className = "field field-wide";
  addWrap.innerHTML = "<span>Add serials (@U or human, one per line)</span>";
  const addArea = document.createElement("textarea");
  addArea.rows = 4;
  addArea.placeholder = "@U... or 300, 0, 1, 60| 2, 2002|| {9}";
  addWrap.appendChild(addArea);

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.textContent = "Add to send list";
  addBtn.addEventListener("click", () => {
    const lines = String(addArea.value || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.startsWith("@U") || (line.includes(",") && /\d/.test(line)));
    if (!lines.length) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = "Paste at least one @U or human serial line first.";
      return;
    }
    const rows = multiselectRows.get(sectionId) || [];
    const selected = multiselectState.get(sectionId) || new Set();
    for (const line of lines) {
      const id = `${Date.now()}-${rows.length}-${Math.random().toString(36).slice(2, 7)}`;
      rows.push({
        id,
        serial: line,
        title: line.startsWith("@U") ? `${line.slice(0, 28)}…` : line.slice(0, 48),
      });
      selected.add(id);
    }
    multiselectRows.set(sectionId, rows);
    multiselectState.set(sectionId, selected);
    addArea.value = "";
    renderSerialSendListRows(sectionId, box);
    actionMessage.className = "action-message ok";
    actionMessage.textContent = `Added ${lines.length} serial(s) to send list.`;
  });

  const meta = document.createElement("div");
  meta.className = "multiselect-meta";
  meta.innerHTML = `<span class="multiselect-count badge">0 selected</span>
    <span class="multiselect-status muted small">Queue is empty</span>`;

  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.textContent = "Clear list";
  clearBtn.addEventListener("click", () => {
    multiselectRows.set(sectionId, []);
    multiselectState.set(sectionId, new Set());
    renderSerialSendListRows(sectionId, box);
  });
  meta.appendChild(clearBtn);

  const listEl = document.createElement("div");
  listEl.className = "multiselect-list";

  box.append(addWrap, addBtn, meta, listEl);
  sectionEl.appendChild(box);
  if (!multiselectRows.has(sectionId)) multiselectRows.set(sectionId, []);
  if (!multiselectState.has(sectionId)) multiselectState.set(sectionId, new Set());
  renderSerialSendListRows(sectionId, box);
}

function renderSerialSendListRows(sectionId, box) {
  const listEl = box.querySelector(".multiselect-list");
  const countEl = box.querySelector(".multiselect-count");
  const statusEl = box.querySelector(".multiselect-status");
  if (!listEl) return;
  const rows = multiselectRows.get(sectionId) || [];
  const selected = multiselectState.get(sectionId) || new Set();
  listEl.innerHTML = "";
  if (!rows.length) {
    listEl.innerHTML = `<p class="muted">No serials queued yet.</p>`;
  } else {
    for (const row of rows) {
      const label = document.createElement("label");
      label.className = "multiselect-row";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = selected.has(row.id);
      cb.addEventListener("change", () => {
        if (cb.checked) selected.add(row.id);
        else selected.delete(row.id);
        if (countEl) countEl.textContent = `${selected.size} selected`;
      });
      const text = document.createElement("span");
      text.textContent = row.title || row.serial;
      label.append(cb, text);
      listEl.appendChild(label);
    }
  }
  if (countEl) countEl.textContent = `${selected.size} selected`;
  if (statusEl) statusEl.textContent = `${rows.length} in send list`;
}

async function populateCatalogSelect(selectEl, field, sectionId, actionDef, wrapEl) {
  const catalogName = field.catalog || "";
  selectEl.innerHTML = "";
  const loading = document.createElement("option");
  loading.value = "";
  loading.textContent = actionsEnabled() ? "Loading…" : "Connect in-game first";
  selectEl.appendChild(loading);
  selectEl.disabled = !actionsEnabled();

  if (!actionsEnabled()) {
    return;
  }

  try {
    const params = catalogParamsForField(sectionId, field, actionDef);
    const data = await loadCatalog(catalogName, params);
    const rows = data.rows || data.maps || data.stations || [];
    selectEl.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    const hint = data.message && !rows.length ? data.message : "";
    placeholder.textContent = rows.length ? "Select…" : hint || "No entries";
    selectEl.appendChild(placeholder);
    const valueKey = field.valueKey || "id";
    const labelKey = field.labelKey || valueKey;
    for (const row of rows) {
      const opt = document.createElement("option");
      opt.value = String(row[valueKey] || "");
      const label = String(row[labelKey] || opt.value);
      const extra = row.category || row.rarity || row.world || row.group || "";
      opt.textContent = extra ? `${label} · ${extra}` : label;
      selectEl.appendChild(opt);
    }
    const key = actionFieldKey(sectionId, actionDef, field);
    catalogRowCache.set(key, rows);
    const current = fieldValues[key] || "";
    if (current) {
      selectEl.value = current;
      applyCatalogSelection(sectionId, actionDef, field, selectEl, key);
    }
    if (wrapEl) wrapEl.dataset.catalogError = "";
  } catch (error) {
    selectEl.innerHTML = "";
    const err = document.createElement("option");
    err.value = "";
    err.textContent = formatCatalogError(catalogName, error);
    selectEl.appendChild(err);
    if (wrapEl) wrapEl.dataset.catalogError = "1";
  }
}

function renderField(sectionId, actionDef, field, sectionEl, allFields) {
  if (field.type === "hidden") {
    const key = fieldStorageKey(sectionId, actionDef, field);
    if (fieldValues[key] === undefined) fieldValues[key] = field.default ?? "";
    return null;
  }

  const wrap = document.createElement("label");
  wrap.className = "field";
  const key = fieldStorageKey(sectionId, actionDef, field);
  if (fieldValues[key] === undefined) {
    fieldValues[key] = field.default ?? "";
  }

  const title = document.createElement("span");
  title.textContent = field.label || field.key;
  wrap.appendChild(title);

  if (field.type === "player_select") {
    const select = document.createElement("select");
    select.dataset.role = "player-select";
    if (field.includeAll) {
      select.dataset.includeAll = "1";
    }
    select.addEventListener("change", () => {
      fieldValues[key] = select.value;
    });
    wrap.appendChild(select);
    wrap.dataset.fieldKey = key;
    refreshPlayerSelects();
    return wrap;
  }

  if (field.type === "catalog_select") {
    wrap.dataset.role = "catalog-select";
    wrap.dataset.sectionId = sectionId;
    wrap.dataset.actionName = actionDef.action;
    wrap.dataset.catalogField = JSON.stringify(field);

    const select = document.createElement("select");
    select.dataset.role = "catalog-select";
    select.addEventListener("change", () => {
      applyCatalogSelection(sectionId, actionDef, field, select, key);
      for (const sibling of allFields || []) {
        if ((sibling.catalogParamsFrom || []).includes(field.key)) {
          const siblingWrap = sectionEl.querySelector(
            `[data-field-key="${actionFieldKey(sectionId, actionDef, sibling)}"]`
          );
          const siblingSelect = siblingWrap?.querySelector("select[data-role='catalog-select']");
          if (siblingSelect) populateCatalogSelect(siblingSelect, sibling, sectionId, actionDef, siblingWrap);
        }
      }
    });
    select.addEventListener("focus", () => {
      if (wrap.dataset.catalogError === "1" || select.options.length <= 1) {
        catalogCache.delete(catalogCacheKey(field.catalog, catalogParamsForField(sectionId, field, actionDef)));
        populateCatalogSelect(select, field, sectionId, actionDef, wrap);
      }
    });
    if (field.search) {
      const searchKey = `${key}:search`;
      if (fieldValues[searchKey] === undefined) fieldValues[searchKey] = "";
      const searchInput = document.createElement("input");
      searchInput.type = "search";
      searchInput.placeholder = "Filter list…";
      searchInput.value = fieldValues[searchKey];
      searchInput.addEventListener("input", () => {
        fieldValues[searchKey] = searchInput.value;
        catalogCache.delete(catalogCacheKey(field.catalog, catalogParamsForField(sectionId, field, actionDef)));
        populateCatalogSelect(select, field, sectionId, actionDef, wrap);
      });
      wrap.appendChild(searchInput);
    }
    wrap.appendChild(select);
    wrap.dataset.fieldKey = key;
    populateCatalogSelect(select, field, sectionId, actionDef, wrap);
    return wrap;
  }

  let input;
  if (field.type === "textarea") {
    input = document.createElement("textarea");
    input.rows = 4;
    if (field.placeholder) input.placeholder = field.placeholder;
  } else if (field.type === "select") {
    input = document.createElement("select");
    for (const option of field.options || []) {
      const opt = document.createElement("option");
      opt.value = option;
      opt.textContent = option;
      input.appendChild(opt);
    }
    input.addEventListener("change", () => {
      fieldValues[key] = input.value;
      if (field.catalogParam) {
        catalogCache.clear();
        for (const sibling of allFields || []) {
          if (sibling.type === "catalog_select") {
            const siblingWrap = sectionEl.querySelector(
              `[data-field-key="${actionFieldKey(sectionId, actionDef, sibling)}"]`
            );
            const siblingSelect = siblingWrap?.querySelector("select[data-role='catalog-select']");
            if (siblingSelect) populateCatalogSelect(siblingSelect, sibling, sectionId, actionDef, siblingWrap);
          }
        }
      }
    });
  } else if (field.type === "number") {
    input = document.createElement("input");
    input.type = "number";
  } else {
    input = document.createElement("input");
    input.type = "text";
    if (field.placeholder) input.placeholder = field.placeholder;
  }
  input.value = fieldValues[key];
  const refreshCatalogSiblings = () => {
    catalogCache.clear();
    for (const sibling of allFields || []) {
      if (sibling.type !== "catalog_select") continue;
      const usesField = (sibling.catalogParamsFrom || []).includes(field.key) || sibling.catalogParam === field.key;
      if (!usesField) continue;
      const siblingWrap = sectionEl.querySelector(
        `[data-field-key="${actionFieldKey(sectionId, actionDef, sibling)}"]`
      );
      const siblingSelect = siblingWrap?.querySelector("select[data-role='catalog-select']");
      if (siblingSelect) populateCatalogSelect(siblingSelect, sibling, sectionId, actionDef, siblingWrap);
    }
  };
  input.addEventListener("input", () => {
    fieldValues[key] = input.value;
    refreshCatalogSiblings();
  });
  input.addEventListener("change", () => {
    fieldValues[key] = input.value;
    refreshCatalogSiblings();
  });
  wrap.appendChild(input);
  wrap.dataset.fieldKey = key;
  return wrap;
}

function renderActivityLog(lines) {
  let panel = document.getElementById("activity-log-panel");
  if (!panel) {
    panel = document.createElement("pre");
    panel.id = "activity-log-panel";
    panel.className = "activity-log";
    tabContent.appendChild(panel);
  }
  panel.textContent = (lines || []).join("\n") || "(empty)";
}

async function refreshPoolBrowser(sectionId, config) {
  const box = tabContent.querySelector(`[data-pool-browser="${sectionId}"]`);
  if (!box) return;
  const listEl = box.querySelector(".pool-browser-list");
  const countEl = box.querySelector(".pool-browser-count");
  const statusEl = box.querySelector(".pool-browser-status");
  const selectedEl = box.querySelector(".pool-browser-selected");
  if (!listEl) return;

  if (!actionsEnabled()) {
    listEl.innerHTML = `<p class="muted">Connect in-game first.</p>`;
    if (countEl) countEl.textContent = "0";
    if (statusEl) statusEl.textContent = "";
    poolBrowserSignatures.delete(sectionId);
    return;
  }

  const params = poolBrowserParams(sectionId, config);
  const cacheKey = catalogCacheKey(config.catalog, params);
  const hadRows = Boolean(listEl.querySelector(".pool-browser-row"));
  const lastRendered = poolBrowserSignatures.get(sectionId) || "";
  if (!hadRows || !lastRendered.startsWith(`${cacheKey}:`)) {
    listEl.innerHTML = `<p class="muted">Loading pools…</p>`;
  }

  try {
    const data = await loadCatalog(config.catalog, params);
    const rows = data.rows || [];
    const rowsSig = `${cacheKey}:${rows.map((row) => poolBrowserRowId(row)).join("|")}`;
    if (rowsSig === lastRendered && hadRows) {
      const total = data.total ?? rows.length;
      if (countEl) {
        countEl.textContent = total > rows.length ? `${rows.length} / ${total}` : String(rows.length);
      }
      if (statusEl) statusEl.textContent = data.message || "";
      return;
    }
    poolBrowserSignatures.set(sectionId, rowsSig);
    itemPoolRows.set(sectionId, rows);
    const total = data.total ?? rows.length;
    if (countEl) {
      countEl.textContent = total > rows.length ? `${rows.length} / ${total}` : String(rows.length);
    }
    if (statusEl) {
      statusEl.textContent = data.message || "";
    }
    const selected = itemPoolSelection.get(sectionId);
    const selectedId = selected ? poolBrowserRowId(selected) : "";
    listEl.innerHTML = "";
    if (!rows.length) {
      const hint =
        params.search && params.category === "All"
          ? "No matches — try category Shiny, Pearl, or a weapon type."
          : "No pools match this filter.";
      listEl.innerHTML = `<p class="muted">${hint}</p>`;
      if (selectedEl) selectedEl.textContent = "None selected";
      return;
    }
    for (const row of rows) {
      const rowId = poolBrowserRowId(row);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "pool-browser-row";
      if (rowId === selectedId) button.classList.add("is-selected");
      const label = document.createElement("span");
      label.className = "pool-browser-label";
      label.textContent = row.display_name || row.itempool || row.catalog_key || "Pool";
      const meta = document.createElement("span");
      meta.className = "pool-browser-meta muted";
      const bits = [row.category, row.itempool].filter(Boolean);
      meta.textContent = bits.join(" · ");
      button.append(label, meta);
      button.addEventListener("click", () => {
        itemPoolSelection.set(sectionId, row);
        if (selectedEl) {
          selectedEl.textContent = row.display_name || row.itempool || "Selected";
        }
        listEl.querySelectorAll(".pool-browser-row.is-selected").forEach((node) => {
          node.classList.remove("is-selected");
        });
        button.classList.add("is-selected");
      });
      listEl.appendChild(button);
    }
    if (selected && selectedEl) {
      selectedEl.textContent = selected.display_name || selected.itempool || "Selected";
    } else if (selectedEl) {
      selectedEl.textContent = "Click a pool below to select it";
    }
  } catch (error) {
    poolBrowserSignatures.delete(sectionId);
    listEl.innerHTML = `<p class="muted">${formatCatalogError(config.catalog, error)}</p>`;
    if (statusEl) statusEl.textContent = "";
  }
}

function renderPoolBrowser(section, sectionId, sectionEl) {
  const config = section.poolBrowser;
  if (!config) return;
  sectionEl.dataset.poolBrowser = "1";

  if (fieldValues[`${sectionId}:search`] === undefined) fieldValues[`${sectionId}:search`] = "";
  if (fieldValues[`${sectionId}:category`] === undefined) {
    fieldValues[`${sectionId}:category`] = config.defaultCategory || "All";
  }

  const box = document.createElement("div");
  box.className = "pool-browser multiselect-box";
  box.dataset.poolBrowser = sectionId;

  const toolbar = document.createElement("div");
  toolbar.className = "multiselect-toolbar pool-browser-toolbar";

  const searchWrap = document.createElement("label");
  searchWrap.className = "target-control-label pool-browser-search";
  searchWrap.innerHTML = "<span>Search pools</span>";
  const searchInput = document.createElement("input");
  searchInput.type = "search";
  searchInput.placeholder = "e.g. shiny, pearl, daedalus, legendary…";
  searchInput.value = fieldValues[`${sectionId}:search`];
  searchInput.addEventListener("input", () => {
    fieldValues[`${sectionId}:search`] = searchInput.value;
    window.clearTimeout(searchInput._debounce);
    searchInput._debounce = window.setTimeout(() => refreshPoolBrowser(sectionId, config), 180);
  });
  searchWrap.appendChild(searchInput);

  const categoryWrap = document.createElement("label");
  categoryWrap.className = "target-control-label";
  categoryWrap.innerHTML = "<span>Category</span>";
  const categorySelect = document.createElement("select");
  for (const option of config.categories || ["All"]) {
    const opt = document.createElement("option");
    opt.value = option;
    opt.textContent = option;
    categorySelect.appendChild(opt);
  }
  categorySelect.value = fieldValues[`${sectionId}:category`];
  categorySelect.addEventListener("change", () => {
    fieldValues[`${sectionId}:category`] = categorySelect.value;
    refreshPoolBrowser(sectionId, config);
  });
  categoryWrap.appendChild(categorySelect);

  const meta = document.createElement("div");
  meta.className = "multiselect-meta pool-browser-meta-row";
  meta.innerHTML = `<span class="multiselect-count badge pool-browser-count">0</span>
    <span class="pool-browser-selected muted small">Click a pool below to select it</span>`;

  toolbar.append(searchWrap, categoryWrap, meta);
  box.appendChild(toolbar);

  const statusEl = document.createElement("p");
  statusEl.className = "pool-browser-status muted small";
  box.appendChild(statusEl);

  const listEl = document.createElement("div");
  listEl.className = "multiselect-list pool-browser-list";
  box.appendChild(listEl);

  sectionEl.appendChild(box);
  window.setTimeout(() => refreshPoolBrowser(sectionId, config), 0);
}

async function refreshMultiselectSection(sectionId, config) {
  const box = tabContent.querySelector(`[data-multiselect-section="${sectionId}"]`);
  if (!box) return;
  const listEl = box.querySelector(".multiselect-list");
  const countEl = box.querySelector(".multiselect-count");
  const statusEl = box.querySelector(".multiselect-status");
  if (!listEl) return;

  // Send-serials queue lives in the EXE only (no bridge catalog).
  if (config?.localOnly || config?.catalog === "serial_send_list") {
    renderSerialSendListRows(sectionId, box);
    return;
  }

  if (!actionsEnabled()) {
    listEl.innerHTML = `<p class="muted">Connect in-game first.</p>`;
    if (statusEl) statusEl.textContent = "";
    return;
  }

  listEl.innerHTML = `<p class="muted">Loading…</p>`;
  try {
    const params = multiselectParams(sectionId, config);
    const data = await loadCatalog(config.catalog, params);
    const rows = data.rows || [];
    multiselectRows.set(sectionId, rows);
    if (!multiselectState.has(sectionId)) {
      multiselectState.set(sectionId, new Set());
    }
    const selected = multiselectState.get(sectionId);
    listEl.innerHTML = "";
    if (!rows.length) {
      listEl.innerHTML = `<p class="muted">${data.message || "No entries."}</p>`;
    } else {
      for (const row of rows) {
        const rowId = multiselectRowId(row, config);
        const label = document.createElement("label");
        label.className = "multiselect-row";
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = selected.has(rowId);
        cb.addEventListener("change", () => {
          if (cb.checked) selected.add(rowId);
          else selected.delete(rowId);
          if (countEl) countEl.textContent = `${selected.size} selected`;
          if (config.catalog === "serial_store" && cb.checked) {
            serialStoreEdit.set(sectionId, {
              id: row.id,
              name: row.name || row.title,
              group: row.group || "Default",
              serial: row.serial || "",
            });
            renderSerialStoreForm(sectionId);
          }
        });
        const text = document.createElement("span");
        const title = String(row[config.labelKey || "title"] || row.name || rowId);
        const extra = row.group || row.listing || row.category || "";
        text.textContent = extra ? `${title} · ${extra}` : title;
        label.append(cb, text);
        listEl.appendChild(label);
      }
    }
    if (countEl) countEl.textContent = `${selected.size} selected`;
    if (statusEl) statusEl.textContent = data.message || `${rows.length} entries`;
    if (config.catalog === "serial_store" && Array.isArray(data.groups)) {
      const filterSelect = box.querySelector(".multiselect-filter select");
      if (filterSelect) {
        const current = fieldValues[`${sectionId}:group`] || "All";
        filterSelect.innerHTML = "";
        for (const group of data.groups) {
          const opt = document.createElement("option");
          opt.value = group;
          opt.textContent = group;
          filterSelect.appendChild(opt);
        }
        filterSelect.value = data.groups.includes(current) ? current : "All";
        fieldValues[`${sectionId}:group`] = filterSelect.value;
      }
    }
    box.dataset.catalogError = "";
  } catch (error) {
    listEl.innerHTML = `<p class="muted">${formatCatalogError(config.catalog, error)}</p>`;
    if (statusEl) statusEl.textContent = "";
    box.dataset.catalogError = "1";
  }
}

function sleepMs(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function runCatalogRefresh(sectionId, config, button) {
  if (!actionsEnabled()) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = "Connect in-game first.";
    return;
  }
  const startAction = config.refreshAction;
  const statusAction = config.refreshStatusAction;
  if (!startAction) return;
  const label = button?.textContent || "Refresh";
  if (button) {
    button.disabled = true;
    button.textContent = "Refreshing…";
  }
  actionMessage.className = "action-message muted";
  actionMessage.textContent = `${label} started…`;
  const statusEl = tabContent.querySelector(
    `[data-multiselect-section="${sectionId}"] .multiselect-status`
  );
  try {
    const startTimeout = config.catalog === "lootlemon" ? 30 : 20;
    const { data: startData } = await window.sqbt.postAction(startAction, {}, startTimeout);
    if (statusEl) statusEl.textContent = startData?.message || "Refreshing…";
    actionMessage.textContent = startData?.message || "Refreshing…";
    if (!statusAction) {
      catalogCache.clear();
      await refreshMultiselectSection(sectionId, config);
      return;
    }
    const maxPolls = config.catalog === "lootlemon" ? 180 : 90;
    for (let i = 0; i < maxPolls; i += 1) {
      await sleepMs(2000);
      const { data } = await window.sqbt.postAction(statusAction, {}, 15);
      const msg = data?.message || "Refreshing…";
      if (statusEl) statusEl.textContent = msg;
      actionMessage.textContent = msg;
      if (!data?.busy) {
        catalogCache.delete(catalogCacheKey(config.catalog, multiselectParams(sectionId, config)));
        await refreshMultiselectSection(sectionId, config);
        actionMessage.className = data?.ok === false ? "action-message error" : "action-message ok";
        actionMessage.textContent = msg;
        return;
      }
    }
    actionMessage.className = "action-message error";
    actionMessage.textContent = "Refresh is still running — press Reload list in a minute.";
  } catch (error) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = String(error?.message || error || "Refresh failed.");
  } finally {
    if (button) {
      button.disabled = !actionsEnabled();
      button.textContent = label;
    }
  }
}

function syncSerialStoreEditFromForm(sectionId) {
  const sectionEl = tabContent.querySelector(`[data-section-id="${sectionId}"]`);
  if (!sectionEl) return;
  const edit = serialStoreEdit.get(sectionId) || { id: "", name: "", group: "Default", serial: "" };
  const nameInput = sectionEl.querySelector("[data-store-name]");
  const groupInput = sectionEl.querySelector("[data-store-group]");
  const serialInput = sectionEl.querySelector("[data-store-serial]");
  if (nameInput) edit.name = nameInput.value;
  if (groupInput) edit.group = groupInput.value;
  if (serialInput) edit.serial = serialInput.value;
  serialStoreEdit.set(sectionId, edit);
}

function renderSerialStoreForm(sectionId) {
  const sectionEl = tabContent.querySelector(`[data-section-id="${sectionId}"]`);
  const form = sectionEl?.querySelector(".serial-store-form");
  if (!form) return;
  const edit = serialStoreEdit.get(sectionId) || { id: "", name: "", group: "Default", serial: "" };
  const nameInput = form.querySelector("[data-store-name]");
  const groupInput = form.querySelector("[data-store-group]");
  const serialInput = form.querySelector("[data-store-serial]");
  if (nameInput) nameInput.value = edit.name || "";
  if (groupInput) groupInput.value = edit.group || "Default";
  if (serialInput) serialInput.value = edit.serial || "";
}

function renderMultiselectControls(section, sectionId, sectionEl) {
  const config = section.multiselect;
  const box = document.createElement("div");
  box.className = "multiselect-box";
  box.dataset.multiselectSection = sectionId;
  box.dataset.multiselectConfig = JSON.stringify(config);

  const toolbar = document.createElement("div");
  toolbar.className = "multiselect-toolbar";

  const searchKey = `${sectionId}:search`;
  if (fieldValues[searchKey] === undefined) fieldValues[searchKey] = "";
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "Search catalog…";
  search.value = fieldValues[searchKey];
  search.addEventListener("input", () => {
    fieldValues[searchKey] = search.value;
    catalogCache.delete(catalogCacheKey(config.catalog, multiselectParams(sectionId, config)));
    refreshMultiselectSection(sectionId, config);
  });
  toolbar.appendChild(search);

  for (const filter of config.filters || []) {
    const filterKey = `${sectionId}:${filter.key}`;
    if (fieldValues[filterKey] === undefined) {
      fieldValues[filterKey] = filter.default ?? "";
    }
    const filterWrap = document.createElement("label");
    filterWrap.className = "multiselect-filter";
    const filterLabel = document.createElement("span");
    filterLabel.textContent = filter.label || filter.key;
    const filterSelect = document.createElement("select");
    for (const option of filter.options || []) {
      const opt = document.createElement("option");
      opt.value = option;
      opt.textContent = option;
      filterSelect.appendChild(opt);
    }
    filterSelect.value = fieldValues[filterKey];
    filterSelect.addEventListener("change", () => {
      fieldValues[filterKey] = filterSelect.value;
      catalogCache.delete(catalogCacheKey(config.catalog, multiselectParams(sectionId, config)));
      refreshMultiselectSection(sectionId, config);
    });
    filterWrap.append(filterLabel, filterSelect);
    toolbar.appendChild(filterWrap);
  }

  const deliverPlayerKey = `${sectionId}:deliver_player_index`;
  const openRewardsKey = `${sectionId}:open_rewards`;
  const isSerialDeliver = (config.kind || "serial") === "serial";
  if (isSerialDeliver) {
    if (fieldValues[deliverPlayerKey] === undefined || fieldValues[deliverPlayerKey] === "") {
      fieldValues[deliverPlayerKey] = String(
        preferredDeliveryPlayerIndex(latestStatus?.raw?.players || [])
      );
    }
    if (fieldValues[openRewardsKey] === undefined) fieldValues[openRewardsKey] = "yes";
    const deliverWrap = document.createElement("label");
    deliverWrap.className = "multiselect-filter deliver-to-filter";
    deliverWrap.innerHTML = "<span>Send to (required)</span>";
    const deliverPlayer = document.createElement("select");
    deliverPlayer.dataset.role = "player-select";
    deliverPlayer.dataset.deliverPlayerKey = deliverPlayerKey;
    deliverPlayer.dataset.includeAll = "1";
    deliverPlayer.addEventListener("change", () => {
      fieldValues[deliverPlayerKey] = deliverPlayer.value;
    });
    deliverWrap.appendChild(deliverPlayer);
    toolbar.appendChild(deliverWrap);

    const openWrap = document.createElement("label");
    openWrap.className = "multiselect-filter";
    openWrap.innerHTML = "<span>Open rewards on send</span>";
    const openToggle = document.createElement("select");
    for (const [value, label] of [
      ["yes", "Yes"],
      ["no", "No"],
    ]) {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      openToggle.appendChild(opt);
    }
    openToggle.value = fieldValues[openRewardsKey];
    openToggle.addEventListener("change", () => {
      fieldValues[openRewardsKey] = openToggle.value;
    });
    openWrap.appendChild(openToggle);
    toolbar.appendChild(openWrap);
  }

  if (config.levelOverride) {
    const levelOverrideKey = `${sectionId}:level_override`;
    const levelKey = `${sectionId}:level`;
    if (fieldValues[levelOverrideKey] === undefined) fieldValues[levelOverrideKey] = "no";
    if (fieldValues[levelKey] === undefined) fieldValues[levelKey] = "60";
    const levelWrap = document.createElement("label");
    levelWrap.className = "multiselect-filter";
    const levelToggle = document.createElement("select");
    for (const option of ["no", "yes"]) {
      const opt = document.createElement("option");
      opt.value = option;
      opt.textContent = option === "yes" ? "Override level" : "Use serial level";
      levelToggle.appendChild(opt);
    }
    levelToggle.value = fieldValues[levelOverrideKey];
    levelToggle.addEventListener("change", () => {
      fieldValues[levelOverrideKey] = levelToggle.value;
    });
    const levelInput = document.createElement("input");
    levelInput.type = "number";
    levelInput.min = "1";
    levelInput.max = "60";
    levelInput.value = fieldValues[levelKey];
    levelInput.addEventListener("input", () => {
      fieldValues[levelKey] = levelInput.value;
    });
    levelWrap.append(levelToggle, levelInput);
    toolbar.appendChild(levelWrap);
  }

  if (config.refreshAction) {
    const refreshBtn = document.createElement("button");
    refreshBtn.type = "button";
    refreshBtn.textContent = config.refreshLabel || "Refresh catalog";
    refreshBtn.addEventListener("click", () => {
      runCatalogRefresh(sectionId, config, refreshBtn);
    });
    toolbar.appendChild(refreshBtn);
  }

  const retryBtn = document.createElement("button");
  retryBtn.type = "button";
  retryBtn.textContent = "Reload list";
  retryBtn.addEventListener("click", () => {
    catalogCache.delete(catalogCacheKey(config.catalog, multiselectParams(sectionId, config)));
    refreshMultiselectSection(sectionId, config);
  });
  toolbar.appendChild(retryBtn);
  box.appendChild(toolbar);

  const metaRow = document.createElement("div");
  metaRow.className = "multiselect-meta";
  const countEl = document.createElement("span");
  countEl.className = "multiselect-count badge";
  countEl.textContent = "0 selected";
  const statusEl = document.createElement("span");
  statusEl.className = "multiselect-status muted small";
  metaRow.append(countEl, statusEl);

  const selectAllBtn = document.createElement("button");
  selectAllBtn.type = "button";
  selectAllBtn.textContent = "Select all filtered";
  selectAllBtn.addEventListener("click", () => {
    const rows = multiselectRows.get(sectionId) || [];
    const selected = multiselectState.get(sectionId) || new Set();
    for (const row of rows) {
      selected.add(multiselectRowId(row, config));
    }
    multiselectState.set(sectionId, selected);
    refreshMultiselectSection(sectionId, config);
  });
  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.textContent = "Clear";
  clearBtn.addEventListener("click", () => {
    multiselectState.set(sectionId, new Set());
    refreshMultiselectSection(sectionId, config);
  });
  metaRow.append(selectAllBtn, clearBtn);
  box.appendChild(metaRow);

  const listEl = document.createElement("div");
  listEl.className = "multiselect-list";
  box.appendChild(listEl);
  sectionEl.appendChild(box);

  if (!multiselectState.has(sectionId)) {
    multiselectState.set(sectionId, new Set());
  }
  refreshMultiselectSection(sectionId, config);
  refreshPlayerSelects();
}

function renderSerialStoreSection(section, sectionId, sectionEl) {
  if (!serialStoreEdit.has(sectionId)) {
    serialStoreEdit.set(sectionId, { id: "", name: "", group: "Default", serial: "" });
  }

  const form = document.createElement("div");
  form.className = "serial-store-form fields-grid";
  const nameWrap = document.createElement("label");
  nameWrap.className = "field";
  nameWrap.innerHTML = "<span>Name</span>";
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.dataset.storeName = "1";
  nameInput.addEventListener("input", () => {
    const edit = serialStoreEdit.get(sectionId) || {};
    edit.name = nameInput.value;
    serialStoreEdit.set(sectionId, edit);
  });
  nameWrap.appendChild(nameInput);

  const groupWrap = document.createElement("label");
  groupWrap.className = "field";
  groupWrap.innerHTML = "<span>Group</span>";
  const groupInput = document.createElement("input");
  groupInput.type = "text";
  groupInput.dataset.storeGroup = "1";
  groupInput.addEventListener("input", () => {
    const edit = serialStoreEdit.get(sectionId) || {};
    edit.group = groupInput.value;
    serialStoreEdit.set(sectionId, edit);
  });
  groupWrap.appendChild(groupInput);

  const serialWrap = document.createElement("label");
  serialWrap.className = "field field-wide";
  serialWrap.innerHTML = "<span>Serial</span>";
  const serialInput = document.createElement("textarea");
  serialInput.rows = 4;
  serialInput.dataset.storeSerial = "1";
  serialInput.placeholder = "@U or human serial text";
  serialInput.addEventListener("input", () => {
    const edit = serialStoreEdit.get(sectionId) || {};
    edit.serial = serialInput.value;
    serialStoreEdit.set(sectionId, edit);
  });
  serialWrap.appendChild(serialInput);

  form.append(nameWrap, groupWrap, serialWrap);
  sectionEl.appendChild(form);
  renderSerialStoreForm(sectionId);

  const config = {
    catalog: "serial_store",
    kind: "serial",
    valueKey: "serial",
    labelKey: "title",
    idKey: "id",
    levelOverride: true,
    filters: [
      {
        key: "group",
        label: "Group",
        type: "select",
        options: ["All"],
        default: "All",
        catalogParam: "group",
      },
    ],
  };
  section.multiselect = config;
  renderMultiselectControls(section, sectionId, sectionEl);
}

function renderActionCard(sectionId, actionDef, sectionEl, featured) {
  const card = document.createElement("div");
  card.className = "action-card";

  const fields = actionDef.fields || [];
  if (featured && fields.length) {
    const title = document.createElement("h4");
    title.className = "action-card-title";
    title.textContent = actionDef.label;
    card.appendChild(title);
  }
  if (fields.length) {
    const fieldsWrap = document.createElement("div");
    fieldsWrap.className = "fields-grid action-fields";
    for (const field of fields) {
      const node = renderField(sectionId, actionDef, field, sectionEl, fields);
      if (node) fieldsWrap.appendChild(node);
    }
    card.appendChild(fieldsWrap);
  }

  const button = document.createElement("button");
  button.type = "button";
  decorateActionButton(button, featured && fields.length ? "Run" : actionDef.label, actionDef);
  if (actionDef.tooltip) {
    button.title = actionDef.tooltip;
  }
  button.dataset.runAction = actionDef.action;
  button.addEventListener("click", () => {
    const payload = collectPayload(sectionId, actionDef);
    const context = {
      sectionId,
      config: sectionEl.querySelector("[data-multiselect-config]")?.dataset.multiselectConfig
        ? JSON.parse(sectionEl.querySelector("[data-multiselect-config]").dataset.multiselectConfig)
        : { catalog: "serial_store" },
    };
    runAction(actionDef.action, payload, actionDef.confirm || "", context);
  });
  card.appendChild(button);

  if (actionDef.note) {
    const note = document.createElement("p");
    note.className = "action-note muted small";
    if (actionDef.note.before) note.append(actionDef.note.before);
    if (actionDef.note.linkUrl) {
      const link = document.createElement("a");
      link.href = actionDef.note.linkUrl;
      link.textContent = actionDef.note.linkLabel || actionDef.note.linkUrl;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        window.sqbt.openExternal(actionDef.note.linkUrl);
      });
      note.appendChild(link);
    }
    if (actionDef.note.after) note.append(actionDef.note.after);
    card.appendChild(note);
  }

  if (actionDef.showResult && actionDef.action === "serial_convert") {
    card.classList.add("action-card-with-result");
  }

  return card;
}

function keyEventToUnrealKey(event) {
  const code = String(event.code || "");
  const map = {
    Space: "SpaceBar",
    Escape: "Escape",
    Backspace: "BackSpace",
    Enter: "Enter",
    Tab: "Tab",
    Delete: "Delete",
    Insert: "Insert",
    Home: "Home",
    End: "End",
    PageUp: "PageUp",
    PageDown: "PageDown",
    ArrowUp: "Up",
    ArrowDown: "Down",
    ArrowLeft: "Left",
    ArrowRight: "Right",
    Comma: "Comma",
    Period: "Period",
    Slash: "Slash",
    Semicolon: "Semicolon",
    Quote: "Quote",
    BracketLeft: "LeftBracket",
    BracketRight: "RightBracket",
    Backslash: "Backslash",
    Minus: "Hyphen",
    Equal: "Equals",
    Backquote: "Tilde",
  };
  if (map[code]) return map[code];
  if (/^F\d{1,2}$/.test(code)) return code;
  const digit = code.match(/^Digit([0-9])$/);
  if (digit) {
    const names = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"];
    return names[Number(digit[1])] || "";
  }
  const numpad = code.match(/^Numpad([0-9])$/);
  if (numpad) {
    const names = [
      "NumPadZero",
      "NumPadOne",
      "NumPadTwo",
      "NumPadThree",
      "NumPadFour",
      "NumPadFive",
      "NumPadSix",
      "NumPadSeven",
      "NumPadEight",
      "NumPadNine",
    ];
    return names[Number(numpad[1])] || "";
  }
  if (/^Key([A-Z])$/.test(code)) return code.slice(3);
  return "";
}

async function refreshKeybindsEditor(host) {
  if (!host) return;
  const statusEl = host.querySelector(".keybinds-status");
  const listEl = host.querySelector(".keybinds-list");
  if (!listEl) return;
  if (!actionsEnabled()) {
    listEl.innerHTML = `<p class="muted">Connect in-game first to edit keybinds.</p>`;
    if (statusEl) statusEl.textContent = "";
    return;
  }
  listEl.innerHTML = `<p class="muted">Loading keybinds…</p>`;
  try {
    const { data } = await window.sqbt.postAction("keybinds_status", {}, 12);
    if (data?.ok === false) {
      listEl.innerHTML = `<p class="muted">${data.message || "Keybinds unavailable."}</p>`;
      return;
    }
    const actions = data.actions || [];
    const keys = data.keys || [];
    const slots = data.slots || [];
    if (statusEl) statusEl.textContent = data.message || "";
    listEl.innerHTML = "";
    for (const slot of slots) {
      const row = document.createElement("div");
      row.className = "keybind-row";
      row.dataset.slot = String(slot.slot);

      const title = document.createElement("div");
      title.className = "keybind-slot-label";
      title.textContent = slot.label || `Custom ${Number(slot.slot) + 1}`;

      const actionSelect = document.createElement("select");
      actionSelect.className = "keybind-action";
      const emptyOpt = document.createElement("option");
      emptyOpt.value = "";
      emptyOpt.textContent = "(unbound)";
      actionSelect.appendChild(emptyOpt);
      for (const action of actions) {
        const opt = document.createElement("option");
        opt.value = action.id;
        opt.textContent = action.label;
        if (action.id === slot.action_id) opt.selected = true;
        actionSelect.appendChild(opt);
      }

      const keySelect = document.createElement("select");
      keySelect.className = "keybind-key-select";
      const keyEmpty = document.createElement("option");
      keyEmpty.value = "";
      keyEmpty.textContent = "(no key)";
      keySelect.appendChild(keyEmpty);
      const keySet = new Set(keys);
      if (slot.key && !keySet.has(slot.key)) keySet.add(slot.key);
      for (const key of [...keySet]) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = key;
        if (key === slot.key) opt.selected = true;
        keySelect.appendChild(opt);
      }

      const keyInput = document.createElement("input");
      keyInput.type = "text";
      keyInput.className = "keybind-key-input";
      keyInput.placeholder = "Click & press a key";
      keyInput.value = slot.key || "";
      keyInput.readOnly = true;
      keyInput.addEventListener("keydown", (event) => {
        event.preventDefault();
        if (event.key === "Escape" || event.key === "Backspace" || event.key === "Delete") {
          keyInput.value = "";
          keySelect.value = "";
          return;
        }
        const unreal = keyEventToUnrealKey(event);
        if (!unreal) return;
        keyInput.value = unreal;
        if (![...keySelect.options].some((opt) => opt.value === unreal)) {
          const opt = document.createElement("option");
          opt.value = unreal;
          opt.textContent = unreal;
          keySelect.appendChild(opt);
        }
        keySelect.value = unreal;
      });
      keySelect.addEventListener("change", () => {
        keyInput.value = keySelect.value || "";
      });

      const saveBtn = document.createElement("button");
      saveBtn.type = "button";
      saveBtn.className = "secondary";
      saveBtn.textContent = "Save";
      saveBtn.addEventListener("click", async () => {
        actionMessage.className = "action-message muted";
        actionMessage.textContent = "Saving keybind…";
        try {
          const { data: result } = await window.sqbt.postAction(
            "keybinds_set",
            {
              slot: Number(slot.slot),
              action_id: actionSelect.value || "",
              key: keyInput.value || keySelect.value || "",
            },
            12
          );
          actionMessage.className = result?.ok === false ? "action-message error" : "action-message ok";
          actionMessage.textContent = result?.message || "Saved.";
          await refreshKeybindsEditor(host);
        } catch (error) {
          actionMessage.className = "action-message error";
          actionMessage.textContent = String(error?.message || error);
        }
      });

      const clearBtn = document.createElement("button");
      clearBtn.type = "button";
      clearBtn.className = "ghost";
      clearBtn.textContent = "Clear";
      clearBtn.addEventListener("click", async () => {
        try {
          const { data: result } = await window.sqbt.postAction("keybinds_clear", { slot: Number(slot.slot) }, 12);
          actionMessage.className = result?.ok === false ? "action-message error" : "action-message ok";
          actionMessage.textContent = result?.message || "Cleared.";
          await refreshKeybindsEditor(host);
        } catch (error) {
          actionMessage.className = "action-message error";
          actionMessage.textContent = String(error?.message || error);
        }
      });

      const controls = document.createElement("div");
      controls.className = "keybind-controls";
      controls.append(actionSelect, keySelect, keyInput, saveBtn, clearBtn);
      row.append(title, controls);
      listEl.appendChild(row);
    }
  } catch (error) {
    listEl.innerHTML = `<p class="muted">Failed to load keybinds: ${String(error?.message || error)}</p>`;
  }
}

function renderKeybindsEditor(sectionEl) {
  const host = document.createElement("div");
  host.className = "keybinds-editor";
  host.dataset.keybindsEditor = "1";
  const status = document.createElement("p");
  status.className = "keybinds-status muted small";
  const list = document.createElement("div");
  list.className = "keybinds-list";
  list.innerHTML = `<p class="muted">Loading…</p>`;
  const refresh = document.createElement("button");
  refresh.type = "button";
  refresh.className = "secondary";
  refresh.textContent = "Refresh list";
  refresh.addEventListener("click", () => refreshKeybindsEditor(host));
  host.append(status, list, refresh);
  sectionEl.appendChild(host);
  refreshKeybindsEditor(host);
}

function renderSection(section, tabId) {
  const sectionEl = document.createElement("section");
  sectionEl.className = "panel-section";
  if (section.title === "Most used" || section.featured) {
    sectionEl.classList.add("panel-section-featured");
  }
  const sectionId = sectionKey(tabId, section);
  sectionEl.dataset.sectionId = sectionId;
  const heading = document.createElement("h3");
  heading.textContent = section.title;
  sectionEl.appendChild(heading);

  if (section.hint) {
    const hint = document.createElement("p");
    hint.className = "section-hint muted small";
    if (section.linkTab) {
      const link = document.createElement("button");
      link.type = "button";
      link.className = "link-button";
      link.textContent = section.hint;
      link.addEventListener("click", () => {
        activeTabId = section.linkTab;
        renderTabs();
        const current = manifest.tabs.find((row) => row.id === activeTabId);
        if (current) renderTab(current);
      });
      hint.appendChild(link);
    } else {
      hint.textContent = section.hint;
    }
    sectionEl.appendChild(hint);
  }

  if (section.warning) {
    const warn = document.createElement("p");
    warn.className = "section-warning small";
    warn.textContent = section.warning;
    sectionEl.appendChild(warn);
  }

  if (section.fields?.length) {
    const shared = document.createElement("div");
    shared.className = "section-shared-fields";
    for (const field of section.fields) {
      const node = renderField(sectionId, { action: "__section__" }, field);
      if (node) {
        shared.appendChild(node);
      }
    }
    sectionEl.appendChild(shared);
  }

  if (section.discordLink) {
    const community = document.createElement("div");
    community.className = "discord-support-card";

    const copy = document.createElement("div");
    copy.className = "discord-support-copy";
    const title = document.createElement("h4");
    title.textContent = section.discordName
      ? `Join Squ1ggs's community (${section.discordName})`
      : "Join Squ1ggs's community";
    const message = document.createElement("p");
    message.className = "muted";
    message.textContent = "Get release updates, ask for help, compare test results, and help shape what gets added next.";
    const invite = document.createElement("button");
    invite.type = "button";
    invite.className = "discord-invite-button";
    invite.textContent = section.discordName
      ? `discord.gg/DqetrAK2sJ (${section.discordName})`
      : "discord.gg/DqetrAK2sJ";
    invite.addEventListener("click", () => window.sqbt.openExternal(section.discordLink));
    copy.append(title, message, invite);

    if (section.discordQr) {
      const qrLink = document.createElement("a");
      qrLink.className = "discord-qr-link";
      qrLink.href = section.discordLink;
      qrLink.title = "Open the Discord invite";
      qrLink.addEventListener("click", (event) => {
        event.preventDefault();
        window.sqbt.openExternal(section.discordLink);
      });
      const qr = document.createElement("img");
      qr.className = "discord-qr";
      qr.src = section.discordQr;
      qr.alt = "QR code for discord.gg/DqetrAK2sJ";
      qr.width = 260;
      qr.height = 260;
      qrLink.appendChild(qr);
      community.append(copy, qrLink);
    } else {
      community.appendChild(copy);
    }
    sectionEl.appendChild(community);
  }

  if (section.kofiLink) {
    const support = document.createElement("p");
    support.className = "kofi-link muted small";
    support.append("Enjoying the tools? ");
    const link = document.createElement("a");
    link.href = section.kofiLink;
    link.textContent = "Support on Ko-fi";
    link.addEventListener("click", (event) => {
      event.preventDefault();
      window.sqbt.openExternal(section.kofiLink);
    });
    support.appendChild(link);
    sectionEl.appendChild(support);
    return sectionEl;
  }

  const featured = section.title === "Most used" || section.featured;

  if (section.keybindsEditor) {
    renderKeybindsEditor(sectionEl);
    return sectionEl;
  }

  if (section.poolBrowser) {
    sectionEl.dataset.poolBrowserConfig = JSON.stringify(section.poolBrowser);
    renderPoolBrowser(section, sectionId, sectionEl);
  } else if (section.serialSendList) {
    renderSerialSendList(section, sectionId, sectionEl);
  } else if (section.serialStore) {
    renderSerialStoreSection(section, sectionId, sectionEl);
  } else if (section.multiselect) {
    renderMultiselectControls(section, sectionId, sectionEl);
  }

  const actionsWrap = document.createElement("div");
  actionsWrap.className = featured ? "action-grid action-grid-featured" : "action-grid";
  const fieldActionsWrap = featured ? document.createElement("div") : null;
  if (fieldActionsWrap) {
    fieldActionsWrap.className = "action-cards-stack";
  }
  for (const actionDef of section.actions || []) {
    if (section.multiselect || section.serialStore || section.serialSendList) {
      const button = document.createElement("button");
      button.type = "button";
      decorateActionButton(button, actionDef.label, actionDef);
      if (actionDef.tooltip) button.title = actionDef.tooltip;
      button.dataset.runAction = actionDef.action;
      button.addEventListener("click", () => {
        const payload = collectPayload(sectionId, actionDef);
        // Field controls (count/level/recipient) live on action cards for send-list.
        if (section.serialSendList) {
          for (const field of actionDef.fields || []) {
            const key = actionFieldKey(sectionId, actionDef, field);
            let value = fieldValues[key];
            if (value === undefined || value === "") value = field.default ?? "";
            if (field.key === "level_override") {
              payload.level_override = String(value).toLowerCase() === "yes";
              continue;
            }
            if (field.type === "player_select") {
              if (value === "" || value == null) {
                value = preferredDeliveryPlayerIndex(latestStatus?.raw?.players || []);
              }
              payload.player_index = Number(value);
              payload.mode = Number(value) === -1 ? "all" : "player";
              continue;
            }
            if (field.key === "open_rewards") {
              payload.open_rewards = String(value).toLowerCase() === "yes";
              continue;
            }
            if (field.type === "number" && value !== "" && value != null) {
              payload[field.key] = Number(value);
              continue;
            }
            payload[field.key] = value;
          }
        }
        const context = {
          sectionId,
          config: section.multiselect || { catalog: section.serialSendList ? "serial_send_list" : "serial_store" },
        };
        runAction(actionDef.action, payload, actionDef.confirm || "", context);
      });
      // For send-list, also render field controls above the button.
      if (section.serialSendList && (actionDef.fields || []).length) {
        const card = document.createElement("div");
        card.className = "action-card";
        const fieldsWrap = document.createElement("div");
        fieldsWrap.className = "fields-grid action-fields";
        for (const field of actionDef.fields || []) {
          const node = renderField(sectionId, actionDef, field, sectionEl, actionDef.fields);
          if (node) fieldsWrap.appendChild(node);
        }
        card.append(fieldsWrap, button);
        actionsWrap.appendChild(card);
      } else if (
        actionDef.deliverMultiselect ||
        actionDef.deliverStore ||
        actionDef.spawnMultiselect ||
        (actionDef.fields || []).length
      ) {
        const card = document.createElement("div");
        card.className = "action-card deliver-selected-card";
        if (actionDef.deliverMultiselect || actionDef.deliverStore) {
          const tip = document.createElement("p");
          tip.className = "muted small";
          tip.textContent =
            "Tick rows above, choose Send to (yourself / friend / All players), keep Open rewards = Yes, then deliver.";
          card.appendChild(tip);
        }
        if ((actionDef.fields || []).length) {
          const fieldsWrap = document.createElement("div");
          fieldsWrap.className = "fields-grid action-fields";
          for (const field of actionDef.fields || []) {
            const node = renderField(sectionId, actionDef, field, sectionEl, actionDef.fields);
            if (node) fieldsWrap.appendChild(node);
          }
          card.appendChild(fieldsWrap);
        }
        card.appendChild(button);
        actionsWrap.appendChild(card);
      } else {
        actionsWrap.appendChild(button);
      }
    } else if (featured && (actionDef.fields || []).length > 0) {
      fieldActionsWrap.appendChild(renderActionCard(sectionId, actionDef, sectionEl, featured));
    } else if (featured && !(actionDef.fields || []).length) {
      const button = document.createElement("button");
      button.type = "button";
      decorateActionButton(button, actionDef.label, actionDef);
      if (actionDef.tooltip) button.title = actionDef.tooltip;
      button.dataset.runAction = actionDef.action;
      button.addEventListener("click", () => {
        const payload = collectPayload(sectionId, actionDef);
        runAction(actionDef.action, payload, actionDef.confirm || "", { sectionId });
      });
      actionsWrap.appendChild(button);
    } else {
      actionsWrap.appendChild(renderActionCard(sectionId, actionDef, sectionEl, featured));
    }
  }
  sectionEl.appendChild(actionsWrap);
  if (fieldActionsWrap && fieldActionsWrap.childElementCount > 0) {
    sectionEl.appendChild(fieldActionsWrap);
  }

  return sectionEl;
}

function renderTab(tab) {
  tabContent.innerHTML = "";
  tabContent.dataset.activeTab = tab.id;
  catalogCache.clear();
  lastRosterSignature = "";
  for (const section of tab.sections || []) {
    tabContent.appendChild(renderSection(section, tab.id));
  }
  // Keep the sticky global #sqbt-progress-panel; refresh visibility from cache.
  renderProgressPanel(null, null);
  if (tab.id === "progression" && actionsEnabled()) {
    pollProgressOnce();
  }
  if (tab.id === "vehicle" && actionsEnabled()) {
    window.sqbt.postAction("vehicle_spawn_catalog_reload", { deep: false }).catch(() => {});
  }
  if (tab.id === "mobility" && actionsEnabled()) {
    window.sqbt.postAction("tuning_status", { module: "bpm" }).then(({ data }) => {
      if (data?.values) applyFieldValues(data.values);
    });
  }
  if (tab.id === "keybinds" && actionsEnabled()) {
    const host = tabContent.querySelector("[data-keybinds-editor]");
    if (host) refreshKeybindsEditor(host);
  }
  if (["damage", "resources", "vehicle"].includes(tab.id) && actionsEnabled()) {
    const moduleMap = { damage: "bdam", resources: "brc", vehicle: "bvm" };
    const mod = moduleMap[tab.id];
    window.sqbt.postAction("tuning_status", { module: mod }).then(({ data }) => {
      if (data?.values) applyFieldValues(data.values);
    });
  }
  refreshActionButtons();
  if (actionsEnabled()) {
    window.setTimeout(() => reloadCatalogSelects(), 0);
  }
}

function renderTabs() {
  tabBar.innerHTML = "";
  if (!manifest?.tabs?.length) {
    tabContent.innerHTML = "<p class='muted'>Connect to the game to load the tool manifest.</p>";
    return;
  }
  for (const tab of manifest.tabs) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.tabId = tab.id;
    setIconLabel(button, tab.short || tab.label, TAB_ICONS[tab.id] || "");
    button.className = tab.id === activeTabId ? "active" : "";
    button.addEventListener("click", () => {
      activeTabId = tab.id;
      renderTabs();
      const current = manifest.tabs.find((row) => row.id === activeTabId);
      if (current) renderTab(current);
    });
    tabBar.appendChild(button);
  }
  const current = manifest.tabs.find((row) => row.id === activeTabId) || manifest.tabs[0];
  activeTabId = current.id;
  renderTab(current);
}

async function loadManifest() {
  const result = await window.sqbt.getManifest();
  if (!result.ok) {
    tabContent.innerHTML = `<p class="setup-attention">${result.message || "Manifest unavailable."}<br><br>
      <strong>Fix:</strong> press <strong>Install / update mod folder</strong> (first use), then
      <strong>fully restart Borderlands 4</strong>, then Refresh status here.</p>`;
    return;
  }
  manifest = result.manifest;
  renderTabs();
}

async function loadSetup() {
  const setup = await window.sqbt.getSetup();
  gameRootInput.value =
    setup.gameRoot || setup.candidates?.[0] || setup.defaultGameRoot || "";
  updateSetupVisibility(setup);
  if (settingsModeNote) {
    if (setup.settingsMode === "appdata" || setup.isPackaged) {
      settingsModeNote.textContent =
        "Game path is saved in your Windows AppData profile, so it survives unzipping a newer portable EXE.";
    } else {
      settingsModeNote.textContent = "Dev mode: settings use the Electron userData folder.";
    }
  }
}

refreshBtn.addEventListener("click", async () => {
  catalogCache.clear();
  await window.sqbt.getStatus().then(setStatusUi);
  await loadManifest();
});

if (snapRightBtn) {
  snapRightBtn.addEventListener("click", async () => {
    try {
      const result = await window.sqbt.snapWindow("right");
      if (result?.ok) {
        actionMessage.className = "action-message ok";
        actionMessage.textContent = "Snapped to the right half of this monitor.";
      } else {
        actionMessage.className = "action-message error";
        actionMessage.textContent = result?.message || "Could not snap window.";
      }
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error || "Snap failed.");
    }
  });
}

if (spawnAnchorSelect) {
  spawnAnchorSelect.addEventListener("change", () => {
    selectSpawnAnchor(spawnAnchorSelect.value);
  });
}

if (globalTargetSelect) {
  globalTargetSelect.addEventListener("change", () => {
    const value = globalTargetSelect.value;
    if (value === "") return;
    selectTarget(Number(value));
  });
}

browseGameBtn.addEventListener("click", async () => {
  const result = await window.sqbt.pickGameFolder();
  if (result.ok) {
    gameRootInput.value = result.gameRoot;
    setupMessage.textContent = "Game folder saved.";
  }
});

installModBtn.addEventListener("click", async () => {
  setupMessage.className = "setup-message";
  setupMessage.textContent = "Updating mod folder…";
  installModBtn.disabled = true;
  try {
    const result = await window.sqbt.installSdkmod();
    const base =
      result?.message || "Mod folder update finished without a status message.";
    if (result?.ok) {
      setupMessage.className = "setup-message attention";
      setupMessage.textContent = result?.needsGameRestart
        ? `${base}  →  Fully restart Borderlands 4 now, then press Refresh status.`
        : base;
    } else {
      setupMessage.className = "setup-message attention";
      setupMessage.textContent = base;
    }
    if (result?.ok && result.gameRoot) {
      gameRootInput.value = result.gameRoot;
      // Collapse setup so tabs stay usable; put the restart hint in the action line.
      hideSetupAfterConfigured(result.gameRoot);
      actionMessage.className = "action-message ok";
      actionMessage.textContent = result?.needsGameRestart
        ? `${base} Fully restart Borderlands 4, then press Refresh status.`
        : base;
    }
  } catch (error) {
    setupMessage.className = "setup-message attention";
    setupMessage.textContent = `Mod folder update failed: ${String(error?.message || error)}`;
  } finally {
    installModBtn.disabled = false;
  }
});

if (dismissSetupBtn) {
  dismissSetupBtn.addEventListener("click", async () => {
    await window.sqbt.dismissSetup();
    updateSetupVisibility({ gameRoot: gameRootInput.value, setupDismissed: true });
  });
}

if (showSetupBtn) {
  showSetupBtn.addEventListener("click", () => {
    if (setupCard) setupCard.classList.remove("is-hidden");
    showSetupBtn.classList.add("hidden");
  });
}

if (updateOpenBtn) {
  updateOpenBtn.addEventListener("click", () => {
    if (pendingUpdateUrl) window.sqbt.openExternal(pendingUpdateUrl);
  });
}

if (updateDismissBtn) {
  updateDismissBtn.addEventListener("click", () => {
    updateCard?.classList.add("hidden");
  });
}

window.sqbt.onStatus(setStatusUi);
loadSetup();
window.sqbt.getStatus().then(setStatusUi);
loadManifest();
window.setTimeout(() => refreshUpdateStatus(false), 900);
