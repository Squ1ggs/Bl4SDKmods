"use strict";

const OPEN_REWARDS_LARGE_WARNING =
  "WARNING: Open rewards on send opens only packages from that delivery (one every 3–5s). All non-UVHM never auto-opens its Reward Center packages. Console / cross-play users may receive 600+ items: leave multiplayer, open in solo, sell junk, and reduce carried items before rejoining.";

const OPEN_ALL_AFTER_CHALLENGE_WARNING =
  "Complete ALL non-UVHM only sends Reward Center packages; opening is blocked in multiplayer. Leave the lobby, open them in solo, sell junk, and reduce carried items before rejoining. Console / cross-play users can otherwise lose backpack visibility online while carrying hundreds of items.";

const SERIAL_RISK_ACK_KEY = "sqbt.serialRiskAcknowledged";
let suppressOpenAllAfterChallenge = false;

function serialRiskAcknowledged() {
  try {
    return localStorage.getItem(SERIAL_RISK_ACK_KEY) === "1";
  } catch {
    return false;
  }
}

function setSerialRiskAcknowledged(on) {
  try {
    if (on) localStorage.setItem(SERIAL_RISK_ACK_KEY, "1");
    else localStorage.removeItem(SERIAL_RISK_ACK_KEY);
  } catch {
    /* ignore */
  }
}

function confirmSerialRisk(message) {
  if (serialRiskAcknowledged()) return true;
  return window.confirm(message);
}

function forceOpenRewardsFieldsOff() {
  for (const key of Object.keys(fieldValues)) {
    if (String(key).endsWith(":open_rewards")) {
      fieldValues[key] = "no";
    }
  }
  for (const wrap of document.querySelectorAll('[data-field-key$=":open_rewards"]')) {
    const select = wrap.querySelector("select");
    if (select) select.value = "no";
  }
}

const i18n = window.SqbtI18n;
function t(key, vars) {
  return i18n.t(key, vars);
}

function compareModVersions(left, right) {
  const parts = (value) => {
    const match = String(value || "")
      .trim()
      .match(/(\d+)\.(\d+)\.(\d+)/);
    return match ? [Number(match[1]), Number(match[2]), Number(match[3])] : null;
  };
  const a = parts(left);
  const b = parts(right);
  if (!a || !b) return 0;
  for (let index = 0; index < 3; index += 1) {
    if (a[index] > b[index]) return 1;
    if (a[index] < b[index]) return -1;
  }
  return 0;
}

function modSyncDiskAhead(modSync) {
  return (
    Boolean(modSync?.diskAhead) ||
    modSync?.reason === "disk-ahead" ||
    (Boolean(modSync?.installedVersion) &&
      Boolean(modSync?.bundledVersion) &&
      compareModVersions(modSync.installedVersion, modSync.bundledVersion) > 0)
  );
}

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

function showMobilityToast(message, kind = "ok") {
  const text = String(message || "").trim();
  if (!text) {
    return;
  }
  if (actionMessage) {
    actionMessage.className = `action-message ${kind === "off" ? "attention" : "ok"}`;
    actionMessage.textContent = text;
  }
  let el = document.getElementById("mobility-toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "mobility-toast";
    el.className = "mobility-toast";
    document.body.appendChild(el);
  }
  el.className = `mobility-toast ${kind}`;
  el.textContent = text;
  el.hidden = false;
  clearTimeout(showMobilityToast._timer);
  showMobilityToast._timer = setTimeout(() => {
    el.hidden = true;
  }, 4500);
}
const gameRootInput = document.getElementById("game-root");
const refreshBtn = document.getElementById("refresh-btn");
const toolSearchInput = document.getElementById("tool-search-input");
const toolSearchResults = document.getElementById("tool-search-results");
const snapRightBtn = document.getElementById("snap-right-btn");
const themeSelect = document.getElementById("theme-select");
const ghostOpacityRange = document.getElementById("ghost-opacity-range");
const ghostOpacityLabel = document.getElementById("ghost-opacity-label");
const langSelect = document.getElementById("lang-select");
const browseGameBtn = document.getElementById("browse-game-btn");
const installModBtn = document.getElementById("install-mod-btn");
const updateBaseSdkBtn = document.getElementById("update-base-sdk-btn");
const sdkStatusLine = document.getElementById("sdk-status-line");
const setupAttention = document.getElementById("setup-attention");
const dismissSetupBtn = document.getElementById("dismiss-setup-btn");
const showSetupBtn = document.getElementById("show-setup-btn");
const setupCard = document.getElementById("setup-card");
const installLocationCard = document.getElementById("install-location-card");
const installLocationDetail = document.getElementById("install-location-detail");
const installLocationStatus = document.getElementById("install-location-status");
const modSyncBanner = document.getElementById("mod-sync-banner");
const modSyncKicker = document.getElementById("mod-sync-kicker");
const modSyncTitle = document.getElementById("mod-sync-title");
const modSyncDetail = document.getElementById("mod-sync-detail");
const modSyncVersions = document.getElementById("mod-sync-versions");
const tabBar = document.getElementById("tab-bar");
const tabContent = document.getElementById("tab-content");
const updateCard = document.getElementById("update-card");
const updateKicker = document.querySelector("#update-card .update-kicker");
const updateTitle = document.getElementById("update-title");
const updateDetail = document.getElementById("update-detail");
const updateOpenBtn = document.getElementById("update-open-btn");
const modSyncNotice = document.getElementById("mod-sync-notice");
const modSyncNoticeKicker = document.getElementById("mod-sync-notice-kicker");
const modSyncNoticeTitle = document.getElementById("mod-sync-notice-title");
const modSyncNoticeDetail = document.getElementById("mod-sync-notice-detail");
const modSyncNoticeDismiss = document.getElementById("mod-sync-notice-dismiss");
const updateDismissBtn = document.getElementById("update-dismiss-btn");
const appVersion = document.getElementById("app-version");
const reportIssueBtn = document.getElementById("report-issue-btn");
const reportIssueFooterBtn = document.getElementById("report-issue-footer-btn");
const reportIssueDialog = document.getElementById("report-issue-dialog");
const reportGithubBtn = document.getElementById("report-github-btn");
const reportDiscordBtn = document.getElementById("report-discord-btn");
const startGuide = document.getElementById("start-guide");
const startGuideTitle = document.getElementById("start-guide-title");
const startGuideFoot = document.getElementById("start-guide-foot");
const startGuideSteps = document.getElementById("start-guide-steps");

let latestStatus = null;
let actionBusy = false;
let manifest = null;
let activeTabId = "home";
const NAV_MODE_KEY = "sqbt-nav-mode";
const PROGRESS_POS_KEY = "sqbt-progress-panel-pos";
let navMode = localStorage.getItem(NAV_MODE_KEY) === "menu" ? "menu" : "tabs";
let navDrawerOpen = false;
let fieldValues = {};
let progressPollTimer = null;
let progressPollInFlight = false;
let progressPollMs = 0;
let challengePaintTimer = null;
const autoLobbyTouchedKeys = new Set();
let autoLobbyPrefillGen = 0;
let lastCatalogRosterSig = "";
let uvhmBusyGraceUntil = 0;
let uvhmErrorShownUntil = 0;
let challengeBusyGraceUntil = 0;
let challengeCompleteShownUntil = 0;
let challengeOptimisticUntil = 0;
let challengeProgressStartedAt = 0;
let challengeProgressTotalHint = 0;
let challengeDisplayMilestone = 0;
let setupDismissed = false;
let setupPinned = false;
let lastSeenConnected = false;
let offlineStreak = 0;
let manifestLoadGen = 0;
let lastSetup = null;
let lastUpdateResult = null;
let lastSeenModVersion = "";
let currentTheme = "default";
let hiddenShapesUnlocked = false;
let lastBaseSdk = null;
let lastModSync = null;
const catalogCache = new Map();
const catalogRowCache = new Map();
const multiselectState = new Map();
const multiselectRows = new Map();
const multiselectSerialById = new Map();
const serialStoreEdit = new Map();
const serialStoreExpanded = new Map();
const itemPoolSelection = new Map();
const itemPoolRows = new Map();
const SERIALS_SEGMENTS = [
  { id: "send", label: "Send" },
  { id: "library", label: "My packs" },
  { id: "codes", label: "GZO / Lootlemon" },
  { id: "mail", label: "Mail" },
];
const SERIALS_SEGMENT_KEY = "sqbt.serialsSegment";
let serialsActiveSegment = "send";
try {
  const savedSeg = String(localStorage.getItem(SERIALS_SEGMENT_KEY) || "").trim();
  if (SERIALS_SEGMENTS.some((row) => row.id === savedSeg)) serialsActiveSegment = savedSeg;
} catch {
  /* ignore */
}
let lastRosterSignature = "";
let lastGlobalPlayersSignature = "";
let lastTabPlayerSelectsSignature = "";
let pendingTargetIndex = null;
let pendingTargetUntil = 0;
const TARGET_STORAGE_KEY = "sqbt.boostTargetIndex";
let stickyTargetIndex = (() => {
  try {
    const raw = localStorage.getItem(TARGET_STORAGE_KEY);
    if (raw === null || raw === "") return null;
    const n = Number(raw);
    return Number.isNaN(n) ? null : n;
  } catch {
    return null;
  }
})();
let targetResyncQueued = false;
let targetResyncLast = 0;
let autoTargetInitialized = false;
let lastProgressHtml = "";
let lastChallengeStatus = null;
let lastUvhmStatus = null;
let lastSpawnAllStatus = null;
let lastSerialDeliveryStatus = null;
let lastAutoLobbyStatus = null;
let lastShapeStatus = null;
let lastVacuumStatus = null;
let pendingUpdateUrl = "";
const STATUS_CATALOG_TABS = new Set(["serials", "world", "vehicle", "progression"]);
const poolBrowserSignatures = new Map();

const FAVORITE_BUCKET_BY_CATALOG = Object.freeze({
  item_pools: "itempools",
  travel_maps: "travel_maps",
  travel_stations: "travel_stations",
  mob_actors: "mobs",
  io_spawns: "ios",
  serial_store: "serial_store",
  gzo: "gzo",
  lootlemon: "lootlemon",
});
let listFavorites = {
  itempools: [],
  travel_maps: [],
  travel_stations: [],
  mobs: [],
  ios: [],
  serial_store: [],
  gzo: [],
  lootlemon: [],
};

function favoriteBucketForCatalog(catalog) {
  return FAVORITE_BUCKET_BY_CATALOG[String(catalog || "").trim()] || "";
}

function favoriteIdSet(bucket) {
  return new Set((listFavorites[bucket] || []).map((id) => String(id).toLowerCase()));
}

function isListFavorite(bucket, id) {
  const needle = String(id || "").trim().toLowerCase();
  if (!needle || !bucket) return false;
  return favoriteIdSet(bucket).has(needle);
}

function sortRowsFavoritesFirst(rows, idFn, bucket) {
  const list = Array.isArray(rows) ? rows.slice() : [];
  const fav = favoriteIdSet(bucket);
  if (!list.length || !fav.size) return list;
  return list.sort((a, b) => {
    const aFav = fav.has(String(idFn(a) || "").toLowerCase()) ? 0 : 1;
    const bFav = fav.has(String(idFn(b) || "").toLowerCase()) ? 0 : 1;
    return aFav - bFav;
  });
}

function poolFavoriteId(row) {
  return String(row?.itempool || row?.catalog_key || "").trim();
}

function catalogFavoriteId(row, field) {
  const valueKey = field?.valueKey || "id";
  return String(row?.[valueKey] || row?.map || row?.station || row?.id || "").trim();
}

async function refreshListFavorites() {
  try {
    const result = await window.sqbt.getListFavorites();
    if (result?.ok && result.favorites) {
      listFavorites = { ...listFavorites, ...result.favorites };
    }
  } catch {
    /* keep last known */
  }
}

async function toggleRowFavorite(bucket, id, refreshFn) {
  const value = String(id || "").trim();
  if (!bucket || !value) return;
  try {
    const result = await window.sqbt.toggleListFavorite(bucket, value);
    if (result?.ok && result.favorites) {
      listFavorites = { ...listFavorites, ...result.favorites };
    }
  } catch (error) {
    if (actionMessage) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error);
    }
    return;
  }
  if (typeof refreshFn === "function") refreshFn();
}

function makeFavoriteButton(bucket, id, onChanged) {
  const fav = isListFavorite(bucket, id);
  const button = document.createElement("button");
  button.type = "button";
  button.className = `fav-toggle${fav ? " is-favorite" : ""}`;
  button.title = fav ? "Remove from favourites" : "Add to favourites";
  button.setAttribute("aria-label", button.title);
  button.textContent = fav ? "★" : "+";
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    toggleRowFavorite(bucket, id, onChanged);
  });
  return button;
}

const TAB_ICONS = Object.freeze({
  home: "assets/bl4/tab-home.png",
  player: "assets/icons/tab-player.svg",
  keybinds: "assets/icons/tab-keybinds.svg",
  progression: "assets/bl4/tab-progression.png",
  loot: "assets/bl4/tab-loot.png",
  serials: "assets/bl4/tab-serials.png",
  backpack: "assets/icons/tab-player.svg",
  pack_bay: "assets/icons/tab-save-pack.svg",
  party_bay: "assets/icons/tab-live-pack.svg",
  debug_cam: "assets/icons/tab-mobility.svg",
  mobility: "assets/icons/tab-mobility.svg",
  vehicle: "assets/icons/tab-vehicle.svg",
  damage: "assets/bl4/tab-damage.png",
  resources: "assets/icons/tab-kits.svg",
  world: "assets/bl4/tab-world.png",
  mob_io: "assets/icons/tab-mob.svg",
  loot_shapes: "assets/icons/tab-shapes.svg",
  faafo: "assets/bl4/tab-damage.png",
  activity: "assets/icons/tab-support.svg",
  toggles: "assets/icons/tab-mobility.svg",
});

const ACTION_ICON_RULES = Object.freeze([
  [/hold.?session|no.?main.?menu/i, "emoji:🚫"],
  [/force.?fly|infinite.?jump|noclip|no.?target|glide|dash|\bfly\b|jump|walkable|time.?dilation|mobility_/i, "assets/icons/tab-mobility.svg"],
  [/\bfreecam\b|debug.?cam/i, "assets/icons/tab-mobility.svg"],
  [/teleport|me_to_|_to_me|party.?slot/i, "assets/bl4/tab-world.png"],
  [/loot_shape|place.?fully|quick.?arrange|shape|type.?pile|rarity.?lane/i, "assets/icons/tab-shapes.svg"],
  [/golden.?chest/i, "assets/bl4/tab-loot.png"],
  [/shiny/i, "assets/bl4/tab-home.png"],
  [/fog|fast.?travel|travel_map|travel_station|world_text|barrel_logo/i, "assets/bl4/tab-world.png"],
  [/spawn.?all|item.?pool|world.?spawn|drop.?all|\bspawn\b/i, "assets/bl4/tab-loot.png"],
  [/\bcash\b/i, "assets/bl4/tab-cash.png"],
  [/cosmetic|max_sdu|backpack|bank|\bsdu\b/i, "assets/icons/tab-player.svg"],
  [/open.*reward|rewards_open/i, "assets/bl4/tab-serials.png"],
  [/serial|deliver|mail|\breward\b/i, "assets/bl4/tab-serials.png"],
  [/kit|shield|repkit|\bbrc\b|recovery/i, "assets/icons/tab-kits.svg"],
  [/currency|eridium|resource|wallet/i, "assets/bl4/tab-resources.png"],
  [/experience|challenge|uvhm|progress/i, "assets/bl4/tab-progression.png"],
  [/god.?mode|infinite.?ammo|devperk|damage.?look|faafo_|lock.?look|lock.?move|invert.?look/i, "assets/bl4/tab-damage.png"],
  [/vehicle|weapons.?restricted/i, "assets/icons/tab-vehicle.svg"],
  [/\bmobs?\b|\bnpc\b|\bboss\b|\bio\b|encounter|char_/i, "assets/icons/tab-mob.svg"],
  [/max_all|\bplayer\b/i, "assets/icons/tab-player.svg"],
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
  if (actionDef?.icon) return actionDef.icon;
  const searchable = `${actionDef?.action || ""} ${actionDef?.label || ""}`;
  return ACTION_ICON_RULES.find(([pattern]) => pattern.test(searchable))?.[1] || "";
}

function actionAccent(actionDef) {
  const explicit = String(actionDef?.accent || "").trim().toLowerCase();
  if (explicit) return explicit;
  const searchable = `${actionDef?.action || ""} ${actionDef?.label || ""}`;
  if (/hold.?session|no.?main.?menu/i.test(searchable)) return "amber";
  if (/god.?mode|kill.?all|damage/i.test(searchable)) return "coral";
  if (/challenge|uvhm|progress/i.test(searchable)) return "violet";
  if (/max_all|cosmetic|golden.?chest|black.?market/i.test(searchable)) return "gold";
  if (/reward|mail|serial|deliver/i.test(searchable)) return "mint";
  if (/fog|freecam|teleport|world/i.test(searchable)) return "slate";
  if (/spawn|loot|drop|shiny|rarity/i.test(searchable)) return "pink";
  if (/fly|jump|sprint|mobility|noclip/i.test(searchable)) return "cyan";
  return "cyan";
}

let suppressActionClicksUntil = 0;
document.addEventListener(
  "mousedown",
  (event) => {
    const el = event.target;
    if (el && (el.tagName === "SELECT" || el.tagName === "OPTION")) {
      suppressActionClicksUntil = Date.now() + 500;
    }
  },
  true
);
document.addEventListener(
  "click",
  (event) => {
    if (Date.now() >= suppressActionClicksUntil) return;
    const btn = event.target?.closest?.("button[data-run-action]");
    if (!btn) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  },
  true
);

function decorateActionButton(button, label, actionDef) {
  button.dataset.accent = actionAccent(actionDef);
  let finalLabel = label;
  if (actionDef?.action === "teleport_party") {
    const mode = String(actionDef?.payload?.mode || "").toLowerCase();
    button.dataset.teleportParty = "1";
    button.dataset.teleportMode = mode;
    finalLabel = teleportPartyButtonLabel(actionDef);
  }
  setIconLabel(button, finalLabel, actionIcon(actionDef));
}

function boostTargetDisplayName() {
  const raw = latestStatus?.raw || {};
  const idx = effectiveTargetIndex(raw);
  if (idx == null || Number(idx) === -1) return "selected";
  const name = String(raw.target_player_name || playerNameForIndex(raw.players, idx) || "").trim();
  return name || "selected";
}

function teleportPartyButtonLabel(actionDef) {
  const mode = String(actionDef?.payload?.mode || "").toLowerCase();
  const name = boostTargetDisplayName();
  if (mode === "me_to_selected" || mode === "local_to_selected") return `Me → ${name}`;
  if (mode === "selected_to_me" || mode === "selected_to_local") return `${name} → me`;
  return actionDef?.label || "Teleport";
}

function refreshTeleportPartyLabels() {
  for (const button of document.querySelectorAll("button[data-teleport-party='1']")) {
    const mode = String(button.dataset.teleportMode || "").toLowerCase();
    const name = boostTargetDisplayName();
    const label =
      mode === "me_to_selected" || mode === "local_to_selected"
        ? `Me → ${name}`
        : `${name} → me`;
    const icon = button.querySelector("img")?.getAttribute("src") || "";
    setIconLabel(button, label, icon);
  }
}

function friendlyActionError(text) {
  const raw = String(text || "");
  // Handler bugs (e.g. double kwargs) are not EXE/SDK drift — show the real error.
  if (/got multiple values for argument/i.test(raw)) {
    return raw.replace(/^TypeError\((['"`])(.*)\1\)$/i, "$2") || raw;
  }
  if (/TypeError|unexpected keyword|got an unexpected/i.test(raw)) {
    return (
      "The tools list in this window is out of date with the game. " +
      "Press Refresh status (top-right). If you just installed an SDK update, fully restart " +
      "Borderlands 4 first, load a character, then wait for Online — this window should reload itself."
    );
  }
  return raw;
}

function actionsEnabled() {
  if (!latestStatus?.connected) return false;
  if (latestStatus.actionsAvailable === true) return true;
  if (latestStatus.state === "ready" || latestStatus.state === "connected") return true;
  const raw = latestStatus.raw || {};
  return Boolean(raw.actions_available || raw.has_local_pc || (raw.players && raw.players.length));
}

let pendingCanApply = false;
let pendingOpenSetup = false;
let updateApplying = false;
let knownAppVersion = "";

const REPORT_GITHUB_NEW = "https://github.com/Squ1ggs/Bl4SDKmods/issues/new";
const REPORT_DISCORD = "https://discord.gg/DqetrAK2sJ";

function openReportIssueDialog() {
  if (reportIssueDialog && typeof reportIssueDialog.showModal === "function") {
    reportIssueDialog.showModal();
    return;
  }
  window.sqbt.openExternal(buildGithubIssueUrl());
}

function buildGithubIssueUrl() {
  const exe =
    knownAppVersion ||
    String(appVersion?.textContent || "")
      .replace(/^v/i, "")
      .replace(/version unavailable/i, "")
      .trim() ||
    "unknown";
  const mod = String(latestStatus?.raw?.mod_version || "").trim() || "unknown";
  const connection = latestStatus?.connected
    ? "Connected"
    : String(latestStatus?.state || "Offline");
  const session = String(latestStatus?.raw?.session || latestStatus?.session || "").trim() || "—";
  const body = [
    "### What went wrong",
    "",
    "(What broke / what you expected)",
    "",
    "### Steps to reproduce",
    "1.",
    "2.",
    "",
    "### Versions (auto-filled from the app)",
    `- EXE: v${exe}`,
    `- Mod: ${mod}`,
    `- Game connection: ${connection}`,
    `- Session: ${session}`,
    "",
    "### Extra notes",
    "",
    "(Optional: screenshot, which tab/button, host/client)",
    "",
  ].join("\n");
  const params = new URLSearchParams({
    title: "[SQBT] ",
    body,
  });
  return `${REPORT_GITHUB_NEW}?${params.toString()}`;
}

function showSetupCard() {
  setupPinned = true;
  if (setupCard) setupCard.classList.remove("is-hidden");
  if (showSetupBtn) showSetupBtn.classList.add("hidden");
  setupCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderUpdateStatus(result) {
  lastUpdateResult = result || null;
  const current = String(result?.currentVersion || "").replace(/^v/i, "");
  if (current) knownAppVersion = current;
  if (appVersion) {
    appVersion.textContent = current ? `v${current}` : t("footer.unavailable");
  }

  if (!result?.ok || !result.updateAvailable || !result.latestVersion) {
    pendingUpdateUrl = "";
    pendingCanApply = false;
    pendingOpenSetup = false;
    if (result?.needsGameRestartForMod) {
      pendingUpdateUrl = result.releaseUrl || "";
      if (updateKicker) {
        updateKicker.textContent = t("update.modRestartKicker");
      }
      if (updateTitle) {
        updateTitle.textContent = t("update.modRestartTitle");
      }
      if (updateDetail) {
        updateDetail.textContent = t("update.modRestartDetail", {
          disk: result.diskModVersion || result.currentModVersion || "latest",
          live: result.liveModVersion || "an older build",
        });
      }
      if (updateOpenBtn) {
        updateOpenBtn.textContent = t("update.gotIt");
        updateOpenBtn.disabled = false;
      }
      pendingCanApply = false;
      updateCard?.classList.remove("hidden");
      return;
    }
    updateCard?.classList.add("hidden");
    return;
  }

  const latest = String(result.latestVersion).replace(/^v/i, "");
  pendingUpdateUrl = result.releaseUrl || "";
  pendingCanApply = Boolean(result.canApply);
  const appBehind = Boolean(result.appUpdateAvailable);
  const modBehind = Boolean(result.modUpdateAvailable);
  // Mod updates come with a newer EXE (auto-sync on launch) — never send people to Setup.
  pendingOpenSetup = false;

  if (updateTitle) {
    if (appBehind) {
      updateTitle.textContent = pendingCanApply
        ? t("update.installApp", { latest })
        : t("update.downloadApp", { latest });
    } else if (modBehind) {
      updateTitle.textContent = t("update.newerMod", { latest: result.latestModVersion || latest });
    } else {
      updateTitle.textContent = pendingCanApply ? t("update.installNew") : t("update.downloadNew");
    }
  }
  if (updateKicker) {
    updateKicker.textContent = t("update.githubKicker");
  }
  if (updateDetail) {
    const lines = [];
    if (appBehind) {
      lines.push(
        pendingCanApply
          ? t("update.appBehindApply", { current: current || t("sync.unknown"), latest })
          : t("update.appBehindManual", { current: current || t("sync.unknown"), latest })
      );
    }
    if (modBehind) {
      lines.push(
        t("update.modBehind", {
          current: result.currentModVersion || t("sync.unknown"),
          latest: result.latestModVersion || latest,
        })
      );
    }
    if (!lines.length) {
      lines.push(t("update.generic", { latest }));
    }
    lines.push(t("update.githubRequired"));
    lines.push(t("update.restartAfter"));
    updateDetail.textContent = lines.join(" ");
  }
  if (updateOpenBtn) {
    updateOpenBtn.textContent = pendingCanApply ? t("update.install") : t("update.openGithub");
    updateOpenBtn.disabled = updateApplying;
  }
  updateCard?.classList.remove("hidden");
}

async function refreshUpdateStatus(force = false) {
  try {
    const modVersion = latestStatus?.raw?.mod_version || "";
    renderUpdateStatus(await window.sqbt.checkForUpdates(force, modVersion));
  } catch {
    updateCard?.classList.add("hidden");
    if (appVersion) appVersion.textContent = t("footer.unavailable");
  }
}

function playerNameForIndex(players, index) {
  if (Number(index) === -1) return "All players";
  const row = (players || []).find((p) => Number(p.index) === Number(index));
  return row?.name || "";
}

function applyTargetMeta(targetIdx, targetName) {
  if (Number(targetIdx) === -1 || targetName === "All players") {
    metaTarget.textContent = t("target.all");
  } else if (targetIdx != null && targetName) {
    metaTarget.textContent = `${targetName} (#${targetIdx})`;
  } else if (targetIdx != null) {
    metaTarget.textContent = `#${targetIdx}`;
  } else {
    metaTarget.textContent = "—";
  }

  const stickyLabel = document.querySelector(".sticky-target-bar .target-control-label > span");
  if (stickyLabel) {
    const who =
      Number(targetIdx) === -1
        ? "All players"
        : String(targetName || "").trim() || (targetIdx != null && targetIdx !== "" ? `#${targetIdx}` : "—");
    stickyLabel.textContent = `Editing: ${who}`;
  }
}

function persistStickyTarget(idx) {
  const n = Number(idx);
  if (Number.isNaN(n)) return;
  stickyTargetIndex = n;
  try {
    localStorage.setItem(TARGET_STORAGE_KEY, String(n));
  } catch {
    /* ignore */
  }
}

function stickyTargetInRoster(players) {
  if (stickyTargetIndex == null) return false;
  // "All players" (-1) is always a valid sticky target.
  if (Number(stickyTargetIndex) === -1) return true;
  return (players || []).some((row) => Number(row.index) === Number(stickyTargetIndex));
}

function clearStickyTargetIfGone(players) {
  if (stickyTargetIndex == null) return;
  if (!(players || []).length) return;
  if (stickyTargetInRoster(players)) return;
  stickyTargetIndex = null;
  try {
    localStorage.removeItem(TARGET_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function maybeResyncStickyTarget(raw) {
  const players = raw?.players || [];
  if (!players.length || !stickyTargetInRoster(players)) return;
  if (pendingTargetIndex != null && Date.now() < pendingTargetUntil) return;
  const remote = raw?.target_player_index;
  if (remote == null || remote === "" || Number(remote) === Number(stickyTargetIndex)) return;
  if (targetResyncQueued) return;
  if (Date.now() - targetResyncLast < 5000) return;
  targetResyncQueued = true;
  targetResyncLast = Date.now();
  window.setTimeout(() => {
    targetResyncQueued = false;
    if (stickyTargetInRoster(latestStatus?.raw?.players || [])) {
      selectTarget(stickyTargetIndex);
    }
  }, 250);
}

function refreshBackpackIfActive() {
  if (activeTabId !== "backpack" && activeTabId !== "pack_bay" && activeTabId !== "party_bay") {
    return;
  }
  for (const box of tabContent.querySelectorAll("[data-multiselect-section]")) {
    const sectionId = box.dataset.multiselectSection;
    const configJson = box.dataset.multiselectConfig;
    if (!sectionId || !configJson) continue;
    try {
      const config = JSON.parse(configJson);
      if (config.catalog !== "backpack") continue;
      catalogCache.delete(catalogCacheKey("backpack", multiselectParams(sectionId, config)));
      refreshMultiselectSection(sectionId, config);
    } catch {
      /* ignore */
    }
  }
}

function effectiveTargetIndex(raw) {
  const remote = raw?.target_player_index;
  const players = raw?.players || [];
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
  if (stickyTargetInRoster(players)) {
    return Number(stickyTargetIndex);
  }
  if (remote != null && remote !== "") return Number(remote);
  return remote;
}

function localizeStatusHeadline(headline) {
  const raw = String(headline || "").trim();
  const map = {
    "Connected!": "status.connectedBang",
    "Connected — enter a save": "status.enterSave",
    "Game not responding": "status.notResponding",
    "Game not connected": "status.notConnected",
    Unknown: "status.unknown",
  };
  return map[raw] ? t(map[raw]) : raw || t("status.unknown");
}

function localizeStatusDetail(headline, detail) {
  const head = String(headline || "").trim();
  const text = String(detail || "");
  if (head === "Connected!" && (text === "lets mod" || !text)) return t("status.letsMod");
  if (head === "Connected — enter a save") return t("status.enterSaveDetail");
  if (head === "Game not responding") return t("status.notRespondingDetail");
  if (head === "Game not connected") {
    const message = text.split("  →  ")[0] || text;
    return t("status.notConnectedDetail", { message });
  }
  return text;
}

function localizeSpawnLabel(raw) {
  const value = String(raw || "").trim();
  const map = {
    local: "spawn.local",
    party: "spawn.party",
    npc_nearest: "spawn.npc",
    freecam: "spawn.freecam",
    "From me": "spawn.local",
    "From selected player": "spawn.party",
    "Near nearest NPC": "spawn.npc",
    "At debug cam": "spawn.freecam",
  };
  return map[value] ? t(map[value]) : value || "—";
}

function bridgeConnectedHeld() {
  // True while Online, or during the short offline hysteresis that avoids UI flicker.
  if (latestStatus?.connected) return true;
  return Boolean(lastSeenConnected && offlineStreak > 0 && offlineStreak < 3);
}

function clearToolsToWaiting(message) {
  manifest = null;
  if (tabBar) tabBar.innerHTML = "";
  hideToolSearchResults();
  const msg = String(message || "").trim();
  const gameOff =
    !msg || /fetch failed|econnrefused|not running|still loading|game not connected/i.test(msg);
  const needsSetup = !gameOff && setupNeedsUserAction();
  if (!tabContent) return;
  tabContent.innerHTML = needsSetup
    ? `<div class="panel-section panel-section-featured">
      <h3>${t("waiting.tools")}</h3>
      <p class="setup-attention">${msg || t("waiting.manifestUnavailable")}</p>
      <ol class="section-guide">
        <li>${t("waiting.setup1")}</li>
        <li>${t("waiting.toolsSetup2")}</li>
        <li>${t("waiting.toolsSetup3")}</li>
      </ol>
    </div>`
    : `<div class="panel-section panel-section-featured">
      <h3>${t("waiting.tools")}</h3>
      <p class="setup-attention">${msg || t("waiting.manifestUnavailable")}</p>
      <ol class="section-guide">
        <li>${t("waiting.toolsAuto1")}</li>
        <li>${t("waiting.toolsAuto2")}</li>
        <li>${t("waiting.toolsAuto3")}</li>
      </ol>
    </div>`;
}

function setStatusUi(payload) {
  const incoming = payload || {};
  const wasConnected = Boolean(lastSeenConnected);
  let connectedNow = Boolean(incoming.connected);
  // Hold Online through 2 brief offline polls so tab switches / catalog loads
  // cannot flash the "Start Borderlands 4" waiting panel.
  if (!connectedNow && lastSeenConnected) {
    offlineStreak += 1;
    if (offlineStreak < 3) {
      connectedNow = true;
      payload = {
        ...incoming,
        connected: true,
        state: latestStatus?.state || incoming.state || "connected",
        headline: latestStatus?.headline || incoming.headline || "Connected!",
        detail: latestStatus?.detail || incoming.detail || "",
        raw: { ...(latestStatus?.raw || {}), ...(incoming.raw || {}) },
        actionsAvailable:
          incoming.actionsAvailable === true ||
          latestStatus?.actionsAvailable === true ||
          true,
      };
    }
  } else if (connectedNow) {
    offlineStreak = 0;
  }

  latestStatus = payload;
  const state = payload?.state || "disconnected";
  // Connected payloads must always get a green class — some themes previously
  // made --ok reddish, and unknown state names left the default red dot.
  const dotState = payload?.connected
    ? state === "in_menu_or_loading"
      ? "in_menu_or_loading"
      : "connected"
    : state;
  statusDot.className = "status-dot " + dotState;
  if (payload?.connected) statusDot.classList.add("is-online");
  else statusDot.classList.remove("is-online");
  statusHeadline.textContent = localizeStatusHeadline(payload?.headline || "Unknown");
  statusDetail.textContent = localizeStatusDetail(payload?.headline, payload?.detail || "");
  statusDetail.classList.remove("attention");
  const raw = payload?.raw || {};
  metaBridge.textContent = payload?.connected ? t("status.online") : t("status.offline");
  const liveMod = raw.mod_version || "";
  const diskMod = lastModSync?.installedVersion || "";
  if (liveMod && diskMod && String(liveMod) !== String(diskMod)) {
    metaModVersion.textContent = t("status.modLiveVsDisk", { live: liveMod, disk: diskMod });
  } else {
    metaModVersion.textContent = liveMod || "—";
  }
  if (payload?.connected && raw.bridge_features && raw.bridge_features.manifest !== true) {
    const base = localizeStatusDetail(payload?.headline, payload.detail || "");
    statusDetail.textContent = `${base} · ${t("status.restartMod")}`;
    statusDetail.classList.add("attention");
  } else if (
    payload?.connected &&
    lastModSync?.bundledVersion &&
    raw.mod_version &&
    String(raw.mod_version) !== String(lastModSync.bundledVersion)
  ) {
    const base = localizeStatusDetail(payload?.headline, payload.detail || "");
    const disk = lastModSync.installedVersion || "";
    const bundled = lastModSync.bundledVersion;
    const diskMatchesBundled = disk && String(disk) === String(bundled);
    const diskAhead = disk && bundled && compareModVersions(disk, bundled) > 0;
    statusDetail.textContent = `${base} · ${
      diskMatchesBundled
        ? t("status.modMismatch", {
            game: raw.mod_version,
            exe: bundled,
          })
        : diskAhead
          ? t("status.modDiskAhead", {
              disk: disk || t("sync.notInstalled"),
              exe: bundled,
            })
          : t("status.modDiskBehind", {
              disk: disk || t("sync.notInstalled"),
              exe: bundled,
            })
    }`;
    statusDetail.classList.add("attention");
  } else if (!payload?.connected) {
    statusDetail.classList.add("attention");
  }
  metaSession.textContent = raw.session || "—";
  clearStickyTargetIfGone(raw.players || []);
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
  refreshTeleportPartyLabels();
  metaSpawn.textContent = localizeSpawnLabel(raw.spawn_anchor_label || raw.spawn_anchor || "—");
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
  maybeResyncStickyTarget(raw);
  refreshActionButtons();
  if (payload?.connected) {
    syncStickyTogglesFromStatus(raw);
  }
  if (raw.auto_lobby) {
    const st = normalizeAutoLobbyStatus(raw.auto_lobby);
    if (st) {
      lastAutoLobbyStatus = st;
      // Waiting cycles ride the normal status poll — only start the heavy poller while jobs run.
      if (isAutoLobbyBusy(st) && !progressPollTimer) startProgressPoll();
      else renderProgressPanel(null, null, null);
    }
  }
  if (
    payload?.connected &&
    Array.isArray(raw.players) &&
    raw.players.length &&
    !autoTargetInitialized &&
    !(pendingTargetIndex != null && Date.now() < pendingTargetUntil)
  ) {
    autoTargetInitialized = true;
    if (stickyTargetInRoster(raw.players)) {
      selectTarget(Number(stickyTargetIndex));
    } else if (targetIdx == null || targetIdx === "") {
      selectTarget(Number(raw.players[0].index));
    }
  } else if (payload?.connected && targetIdx != null && targetIdx !== "") {
    autoTargetInitialized = true;
  }
  if (payload?.connected && STATUS_CATALOG_TABS.has(activeTabId)) {
    // Roster-change only — reloading catalogs every status poll scrolled the page and flipped lists.
    const rosterSig = JSON.stringify(
      (Array.isArray(raw.players) ? raw.players : []).map((row) => [
        row.index,
        row.name || row.display_name || "",
      ])
    );
    if (rosterSig !== lastCatalogRosterSig) {
      lastCatalogRosterSig = rosterSig;
      window.setTimeout(() => reloadCatalogSelects(), 0);
    }
  }
  // Collapse Setup once when we go Online. Keep it hidden on later polls unless
  // the user clicked Setup. Status polls used to snap the card back open.
  if (!setupPinned && payload?.connected && !lastSeenConnected) {
    hideSetupAfterConfigured(gameRootInput?.value || "");
  }
  // Drop Home "Start here" once buttons unlock — only re-render Home when that
  // checklist should appear/disappear (not on every status poll).
  const nowActions = Boolean(
    payload?.connected &&
      (payload.actionsAvailable === true ||
        payload?.raw?.actions_available ||
        payload?.raw?.has_local_pc ||
        (payload?.raw?.players && payload.raw.players.length))
  );
  const crossedActionsUnlock = nowActions && !window.__sqbtHadActions;
  const crossedFirstConnect = Boolean(payload?.connected && !lastSeenConnected);
  window.__sqbtHadActions = nowActions;
  if (
    activeTabId === "home" &&
    manifest?.tabs?.length &&
    (crossedActionsUnlock || crossedFirstConnect)
  ) {
    window.setTimeout(() => {
      const current = manifest.tabs.find((row) => row.id === activeTabId);
      if (current) renderTab(current);
    }, 0);
  }
  // Once the live mod version is known, re-check GitHub so an outdated mod
  // (even on a current EXE) can still show the update card.
  if (payload?.connected && raw.mod_version) {
    window.setTimeout(() => refreshUpdateStatus(false), 0);
  }
  updateStartGuide();
  const modVersion = String(raw.mod_version || "");
  if (
    connectedNow &&
    (!lastSeenConnected || (modVersion && modVersion !== lastSeenModVersion))
  ) {
    if (modVersion) lastSeenModVersion = modVersion;
    loadManifest().catch(() => {});
  }
  // Sustained Offline again — hide tool tabs until the game is Online (old dash / waiting UI).
  if (!connectedNow && wasConnected) {
    clearToolsToWaiting(t("waiting.manifestUnavailable"));
  }
  lastSeenConnected = connectedNow;
}

function isPlaceholderPlayerRow(row) {
  const rawName = String(row?.name || "").trim();
  if (!rawName) return !row?.is_host;
  if (/^Player\s*\d+$/i.test(rawName) && !row?.is_host) return true;
  return false;
}

function renderRoster(players, targetIndex) {
  const filtered = (players || []).filter((row) => !isPlaceholderPlayerRow(row));
  const signature = JSON.stringify(filtered) + ":" + String(targetIndex ?? "");
  if (signature === lastRosterSignature && rosterList.childElementCount > 0) {
    return;
  }
  lastRosterSignature = signature;
  rosterList.innerHTML = "";
  if (!filtered.length) {
    const li = document.createElement("li");
    li.textContent = t("roster.empty");
    rosterList.appendChild(li);
    return;
  }
  for (const row of filtered) {
    const li = document.createElement("li");
    if (row.index === targetIndex) li.classList.add("active");
    const name = document.createElement("span");
    const rawName = String(row.name || "").trim();
    const base = rawName || (row.is_host ? "Host" : `Player ${row.index}`);
    const lvl = row.level != null && row.level !== "" ? Number(row.level) : NaN;
    name.textContent = Number.isFinite(lvl) && lvl > 0 ? `${base} · L${lvl}` : base;
    const idx = document.createElement("span");
    idx.className = "muted";
    idx.textContent = `#${row.index}`;
    li.append(name, idx);
    li.dataset.playerIndex = String(row.index);
    li.dataset.playerName = name.textContent || "";
    li.addEventListener("click", () => selectTarget(row.index));
    li.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      showPlayerKickMenu(event.clientX, event.clientY, row.index, name.textContent || `Player ${row.index}`);
    });
    rosterList.appendChild(li);
  }
  refreshPlayerSelects();
}

let playerKickMenuEl = null;

function hidePlayerKickMenu() {
  if (playerKickMenuEl) {
    playerKickMenuEl.remove();
    playerKickMenuEl = null;
  }
}

function showPlayerKickMenu(x, y, playerIndex, playerName) {
  hidePlayerKickMenu();
  const idx = Number(playerIndex);
  if (!Number.isFinite(idx) || idx < 0) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = "Pick a single Boost target player before kicking.";
    return;
  }
  const players = latestStatus?.raw?.players || [];
  const row = players.find((p) => Number(p?.index) === idx);
  if (row?.is_host) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = "You can't kick yourself (host).";
    return;
  }
  const menu = document.createElement("div");
  menu.className = "player-context-menu";
  menu.style.left = `${Math.max(8, x)}px`;
  menu.style.top = `${Math.max(8, y)}px`;
  const kickBtn = document.createElement("button");
  kickBtn.type = "button";
  kickBtn.textContent = `Kick ${playerName} from lobby`;
  kickBtn.addEventListener("click", async () => {
    hidePlayerKickMenu();
    const ok = window.confirm(`Kick ${playerName} (#${idx}) from the lobby?`);
    if (!ok) return;
    actionMessage.className = "action-message muted";
    actionMessage.textContent = "Kicking…";
    try {
      const { data } = await window.sqbt.postAction("party_kick", {
        player_index: idx,
        reason: "Squ1ggs Boosting Tools",
      });
      const failed = data?.ok === false;
      actionMessage.className = failed ? "action-message error" : "action-message ok";
      actionMessage.textContent =
        data?.message || (failed ? "Kick failed (host only)." : "Kick requested.");
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error || "Kick failed.");
    }
  });
  menu.appendChild(kickBtn);
  document.body.appendChild(menu);
  playerKickMenuEl = menu;
}

document.addEventListener(
  "click",
  () => {
    hidePlayerKickMenu();
  },
  true
);
document.addEventListener(
  "keydown",
  (event) => {
    if (event.key === "Escape") hidePlayerKickMenu();
  },
  true
);

function refreshActionButtons() {
  const enabled = actionsEnabled() && !actionBusy;
  tabContent.querySelectorAll("[data-run-action]").forEach((button) => {
    const action = String(button.getAttribute("data-run-action") || "");
    let allow = enabled;
    if (allow && action === "rewards_open_everyone" && suppressOpenAllAfterChallenge) {
      // Soft gate — still clickable after confirm, but make the risk obvious.
      button.title =
        "Complete ALL just ran — bank / mule before opening every pending package (Serials tab).";
      button.classList.add("is-caution");
    } else if (action === "rewards_open_everyone") {
      button.classList.remove("is-caution");
    }
    button.disabled = !allow;
  });
  if (globalTargetSelect && latestStatus?.raw?.players?.length) {
    globalTargetSelect.disabled = !actionsEnabled();
  }
}

function syncBoostTargetFromSendTo(value) {
  const idx = Number(value);
  if (!Number.isFinite(idx)) return;
  const top =
    globalTargetSelect && !globalTargetSelect.disabled ? String(globalTargetSelect.value) : "";
  if (top === String(idx)) return;
  selectTarget(idx);
}

async function selectTarget(index) {
  actionMessage.textContent = "";
  const idx = Number(index);
  persistStickyTarget(idx);
  pendingTargetIndex = idx;
  pendingTargetUntil = Date.now() + 8000;
  if (latestStatus?.raw) {
    latestStatus.raw.target_player_index = idx;
    latestStatus.raw.target_player_name = playerNameForIndex(latestStatus.raw.players, idx);
  }
  applyTargetMeta(idx, playerNameForIndex(latestStatus?.raw?.players, idx));
  refreshTeleportPartyLabels();
  refreshGlobalTargetSelect();
  // Force the dropdown to the clicked index even if rebuild skipped an update.
  if (globalTargetSelect) {
    const want = String(idx);
    if (![...globalTargetSelect.options].some((opt) => opt.value === want)) {
      const opt = document.createElement("option");
      opt.value = want;
      opt.textContent =
        playerNameForIndex(latestStatus?.raw?.players || [], idx) || `Player ${idx}`;
      globalTargetSelect.appendChild(opt);
    }
    globalTargetSelect.value = want;
  }
  renderRoster(latestStatus?.raw?.players || [], idx);
  // Keep catalog "Send to" dropdowns aligned with Boost target so GZO/Lootlemon
  // deliveries match what users just clicked in the roster.
  for (const key of Object.keys(fieldValues)) {
    if (
      key.endsWith(":deliver_player_index") ||
      key.endsWith(":player_index")
    ) {
      fieldValues[key] = String(idx);
    }
  }
  for (const select of document.querySelectorAll("select[data-role='player-select']")) {
    if ([...select.options].some((opt) => opt.value === String(idx))) {
      select.value = String(idx);
      const wrap = select.closest("[data-field-key]");
      const fieldKeyName = wrap?.dataset.fieldKey || "";
      const deliverKey = select.dataset.deliverPlayerKey || "";
      if (deliverKey) fieldValues[deliverKey] = String(idx);
      else if (fieldKeyName) fieldValues[fieldKeyName] = String(idx);
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
    pendingTargetUntil = Date.now() + 6000;
    persistStickyTarget(confirmed);
    if (latestStatus?.raw) {
      latestStatus.raw.target_player_index = confirmed;
      latestStatus.raw.target_player_name =
        data?.name || playerNameForIndex(latestStatus.raw.players, confirmed);
    }
    applyTargetMeta(confirmed, latestStatus?.raw?.target_player_name || "");
    refreshTeleportPartyLabels();
    refreshGlobalTargetSelect();
    renderRoster(latestStatus?.raw?.players || [], confirmed);
    refreshBackpackIfActive();
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

const FLY_PRESET_SPEEDS = {
  cruise: 750,
  fast: 5500,
};

function formatFlySpeedStatus(speed, preset, flying) {
  const n = Math.round(Number(speed || 0));
  const p = String(preset || "fast").trim().toLowerCase();
  const label =
    p === "custom" || !FLY_PRESET_SPEEDS[p] ? `custom ${n.toLocaleString()}` : `${p} (${n.toLocaleString()})`;
  if (flying) {
    return `Active fly speed: ${label} — hold WASD to move up/down/around.`;
  }
  return `Saved fly speed: ${label} — press Apply fly speed, then turn Force fly ON (green button).`;
}

function updateFlySpeedLivePanels(speed, preset, flying) {
  const text = formatFlySpeedStatus(speed, preset, flying);
  for (const el of document.querySelectorAll("[data-fly-speed-live]")) {
    el.textContent = text;
    el.className = flying ? "fly-speed-live ok" : "fly-speed-live muted";
  }
}

function wireFlySpeedControls(sectionId) {
  const modeKey = sectionFieldKey(sectionId, { key: "fly_speed_mode" });
  const presetKey = sectionFieldKey(sectionId, { key: "fly_preset" });
  const speedKey = sectionFieldKey(sectionId, { key: "fly_speed" });
  const modeNode = document.querySelector(`[data-field-key="${modeKey}"] select`);
  const presetNode = document.querySelector(`[data-field-key="${presetKey}"] select`);
  const speedNode = document.querySelector(`[data-field-key="${speedKey}"] input`);
  if (!modeNode && !presetNode && !speedNode) {
    return;
  }
  const syncPresetNumber = () => {
    if (!presetNode || !speedNode) return;
    if (String(modeNode?.value || "preset") !== "preset") return;
    const preset = String(presetNode.value || "fast").toLowerCase();
    const num = FLY_PRESET_SPEEDS[preset];
    if (num != null) {
      speedNode.value = String(num);
      fieldValues[speedKey] = String(num);
    }
  };
  presetNode?.addEventListener("change", syncPresetNumber);
  modeNode?.addEventListener("change", syncPresetNumber);
  speedNode?.addEventListener("input", () => {
    if (!speedNode || !modeNode) return;
    if (String(modeNode.value || "preset") === "custom") return;
    modeNode.value = "custom";
    fieldValues[modeKey] = "custom";
  });
  syncPresetNumber();
}

function fieldStorageKey(sectionId, actionDef, field) {
  if (actionDef?.action === "__section__") {
    return sectionFieldKey(sectionId, field);
  }
  return actionFieldKey(sectionId, actionDef, field);
}

const TOGGLE_STICKY_STORAGE = "sqbt.stickyToggles.v1";

function toggleStickyKey(sectionId, actionDef) {
  return `${sectionId}::${actionDef.action}::${actionDef.label}`;
}

function readStickyToggle(key) {
  try {
    const map = JSON.parse(localStorage.getItem(TOGGLE_STICKY_STORAGE) || "{}");
    if (!map || typeof map !== "object" || !Object.prototype.hasOwnProperty.call(map, key)) {
      return undefined;
    }
    return Boolean(map[key]);
  } catch {
    return undefined;
  }
}

function writeStickyToggle(key, on) {
  try {
    const raw = localStorage.getItem(TOGGLE_STICKY_STORAGE);
    const map = raw ? JSON.parse(raw) : {};
    if (!map || typeof map !== "object") {
      return;
    }
    map[key] = Boolean(on);
    localStorage.setItem(TOGGLE_STICKY_STORAGE, JSON.stringify(map));
  } catch {
    /* ignore quota / private mode */
  }
}

function initialToggleOn(sectionId, actionDef) {
  if (actionDef?.syncKey) {
    const sticky = latestStatus?.sticky_toggles || latestStatus?.raw?.sticky_toggles;
    if (sticky && Object.prototype.hasOwnProperty.call(sticky, actionDef.syncKey)) {
      return Boolean(sticky[actionDef.syncKey]);
    }
  }
  if (actionDef?.sticky) {
    const stored = readStickyToggle(toggleStickyKey(sectionId, actionDef));
    if (stored !== undefined) return stored;
  }
  return Boolean(actionDef?.defaultOn);
}

function syncMobilityToggleButtons(syncKey, on) {
  if (!syncKey) return;
  const state = Boolean(on);
  document.querySelectorAll(`button[data-sync-key="${syncKey}"]`).forEach((button) => {
    const sectionId = button.dataset.sectionId || "";
    const label = button.dataset.toggleLabel || button.textContent || "";
    button.dataset.toggleOn = state ? "1" : "0";
    button.dataset.accent = state ? "cyan" : "pink";
    button.classList.toggle("is-toggle-on", state);
    button.classList.toggle("is-toggle-off", !state);
    if (button.dataset.stickyToggle === "1" && sectionId) {
      writeStickyToggle(`${sectionId}::${button.dataset.runAction}::${label}`, state);
    }
    setIconLabel(button, `${label} — ${state ? "ON" : "OFF"}`, actionIcon({ action: button.dataset.runAction, label }));
  });
  if (latestStatus) {
    if (!latestStatus.sticky_toggles || typeof latestStatus.sticky_toggles !== "object") {
      latestStatus.sticky_toggles = {};
    }
    latestStatus.sticky_toggles[syncKey] = state;
    if (latestStatus.raw) {
      if (!latestStatus.raw.sticky_toggles || typeof latestStatus.raw.sticky_toggles !== "object") {
        latestStatus.raw.sticky_toggles = {};
      }
      latestStatus.raw.sticky_toggles[syncKey] = state;
    }
  }
  if (typeof fillTogglesBoard === "function") {
    try {
      fillTogglesBoard();
    } catch {
      /* board may not be on-screen */
    }
  }
}

function startSerialDeliveryPoll(initialMessage, options = {}) {
  const started = Date.now();
  const maxMs = Math.max(60000, Number(options.maxMs || 0) || 120000);
  const totalHint = Math.max(1, Number(options.total || options.packages || 1));
  lastSerialDeliveryStatus = {
    active: true,
    queued: true,
    index: 0,
    total: totalHint,
    percent: 0,
    message: initialMessage || "Queuing mail…",
    label: `0/${totalHint}`,
    scope: options.scope || "",
  };
  renderProgressPanel(null, null, null, lastSerialDeliveryStatus);
  // Keep the bottom line quiet — live detail lives in the floating HUD.
  actionMessage.className = "action-message muted";
  actionMessage.textContent = initialMessage || "Serial delivery running (see progress window)…";
  const pollDeliver = async () => {
    try {
      const { data: statusData } = await window.sqbt.postAction("serial_delivery_status", {}, 8);
      const prog = statusData?.status || statusData?.progress || null;
      const active = Boolean(prog?.active);
      const msg = String(prog?.message || statusData?.message || "").trim();
      if (prog && typeof prog === "object") {
        lastSerialDeliveryStatus = { ...prog, active };
        renderProgressPanel(null, null, null, lastSerialDeliveryStatus);
      }
      if (active && Date.now() - started < maxMs) {
        window.setTimeout(pollDeliver, 900);
        return;
      }
      if (!active) {
        lastSerialDeliveryStatus = {
          active: false,
          finishing: true,
          finishing_until: Date.now() + 2800,
          percent: 100,
          index: Number(prog?.total || prog?.index || 1),
          total: Number(prog?.total || 1),
          label: prog?.label || "done",
          scope: prog?.scope || "",
          stage: prog?.stage || "done",
          message: msg || "Delivery complete.",
        };
        renderProgressPanel(null, null, null, lastSerialDeliveryStatus);
        actionMessage.className = "action-message ok";
        actionMessage.textContent = msg
          ? `${initialMessage || "Serial delivery"} · ${msg}`
          : initialMessage || "Serial delivery complete.";
        window.setTimeout(() => {
          lastSerialDeliveryStatus = null;
          renderProgressPanel(null, null, null, null);
        }, 2800);
      } else if (Date.now() - started >= maxMs) {
        // Timed out while mod still reported active — drop the stuck bar.
        lastSerialDeliveryStatus = null;
        renderProgressPanel(null, null, null, null);
        actionMessage.className = "action-message attention";
        actionMessage.textContent =
          msg || "Serial delivery status timed out — check Reward Center / mail.";
      }
    } catch {
      /* ignore status poll errors */
    }
  };
  window.setTimeout(pollDeliver, 400);
}
function paintToggleButton(button, actionDef, on) {
  const state = Boolean(on);
  button.dataset.toggleOn = state ? "1" : "0";
  button.dataset.accent = state ? "cyan" : "pink";
  button.classList.toggle("is-toggle-on", state);
  button.classList.toggle("is-toggle-off", !state);
  const icon = actionIcon(actionDef);
  setIconLabel(button, `${actionDef.label} — ${state ? "ON" : "OFF"}`, icon);
}

function syncStickyTogglesFromStatus(raw) {
  const sticky = raw?.sticky_toggles;
  if (sticky && typeof sticky === "object") {
    document.querySelectorAll("button[data-sync-key]").forEach((button) => {
      const key = button.dataset.syncKey;
      if (!key || !Object.prototype.hasOwnProperty.call(sticky, key)) return;
      const on = Boolean(sticky[key]);
      const sectionId = button.dataset.sectionId || "";
      const label = button.dataset.toggleLabel || "";
      button.dataset.toggleOn = on ? "1" : "0";
      button.dataset.accent = on ? "cyan" : "pink";
      button.classList.toggle("is-toggle-on", on);
      button.classList.toggle("is-toggle-off", !on);
      if (label) {
        setIconLabel(
          button,
          `${label} — ${on ? "ON" : "OFF"}`,
          actionIcon({ action: button.dataset.runAction, label })
        );
      }
      if (button.dataset.stickyToggle === "1" && sectionId) {
        writeStickyToggle(
          `${sectionId}::${button.dataset.runAction}::${button.dataset.toggleLabel}`,
          on
        );
      }
    });
  }
  fillTogglesBoard();
  if (sticky && typeof sticky === "object" && sticky.fly_speed != null) {
    updateFlySpeedLivePanels(
      sticky.fly_speed,
      sticky.fly_preset,
      Boolean(sticky.force_fly || sticky.force_fly_all)
    );
  }
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
    if (field.type === "checkbox") {
      // Unchecked must send false — never fall back to a True default and re-arm jobs.
      if (value === undefined) value = field.default ?? false;
      payload[field.key] = value === true || String(value).toLowerCase() === "true";
      continue;
    }
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

function syncSectionFieldsFromDom(sectionId) {
  if (!tabContent || !sectionId) return;
  const root =
    tabContent.querySelector(`[data-section-id="${CSS.escape(sectionId)}"]`) || tabContent;
  for (const wrap of root.querySelectorAll("[data-field-key]")) {
    const key = wrap.dataset.fieldKey || "";
    if (!key.startsWith(`${sectionId}:`)) continue;
    const input = wrap.querySelector("input, select, textarea");
    if (!input) continue;
    if (input.type === "checkbox") fieldValues[key] = Boolean(input.checked);
    else fieldValues[key] = input.value;
  }
}

function markAutoLobbyFieldTouched(fieldKey) {
  if (!fieldKey || !String(fieldKey).includes("auto_lobby:")) return;
  autoLobbyTouchedKeys.add(fieldKey);
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
    return "No GZO codes cached yet — press Refresh GZO, then Reload list.";
  }
  if (catalogName === "lootlemon" || lower.includes("lootlemon")) {
    return "No Lootlemon codes cached yet — press Refresh Lootlemon, then Reload list.";
  }
  if (catalogName === "serial_store") {
    return "No saved packs yet — paste codes, type a pack name, then Save. Import a file also works (it only adds).";
  }
  if (lower.includes("abort") || lower.includes("timed out")) {
    return actionsEnabled()
      ? "Catalog timed out — stay in-game unpaused, then Reload list."
      : "Connect in-game first, then Reload list.";
  }
  if (lower.includes("fetch") || lower.includes("unreachable")) {
    return actionsEnabled()
      ? "Could not load catalog — Reload list or refresh status."
      : "Connect in-game first, then Reload list.";
  }
  return text;
}

function catalogEmptyHtml(catalogName, config = null) {
  if (catalogName === "serial_store") {
    return `<div class="serial-empty-state">
      <p class="serial-empty-title">No saved items yet</p>
      <p class="muted small">Paste codes, type a pack name, then Save. Import a file only adds — it never replaces your packs.</p>
    </div>`;
  }
  if (catalogName === "gzo") {
    return `<div class="serial-empty-state">
      <p class="serial-empty-title">GZO codes not loaded</p>
      <p class="muted small">Press Refresh GZO (needs network), then Reload list.</p>
    </div>`;
  }
  if (catalogName === "lootlemon") {
    return `<div class="serial-empty-state">
      <p class="serial-empty-title">Lootlemon codes not loaded</p>
      <p class="muted small">Press Refresh Lootlemon — first sync can take a few minutes.</p>
    </div>`;
  }
  if (catalogName === "backpack") {
    if (config?.params?.party_bay) {
      return `<div class="serial-empty-state">
      <p class="serial-empty-title">No Party Bay rows</p>
      <p class="muted small">Pick one Boost target (not All players), then Snap once. If status says 0 occupied, that player’s pack is empty on the host — not a UI glitch.</p>
    </div>`;
    }
    if (config?.params?.pack_bay || config?.source === "save_yaml") {
      return `<div class="serial-empty-state">
      <p class="serial-empty-title">No Pack Bay rows</p>
      <p class="muted small">Press Rescan from autosave after you loot. Needs a readable character .sav on disk.</p>
    </div>`;
    }
  }
  return `<p class="muted">Nothing matches these filters.</p>`;
}

function promptTextDialog({
  title = "Name",
  kicker = "Library",
  detail = "",
  label = "Name",
  defaultValue = "",
  okLabel = "Save",
} = {}) {
  return new Promise((resolve) => {
    const dialog = document.getElementById("sqbt-prompt-dialog");
    const form = document.getElementById("sqbt-prompt-form");
    const titleEl = document.getElementById("sqbt-prompt-title");
    const kickerEl = document.getElementById("sqbt-prompt-kicker");
    const detailEl = document.getElementById("sqbt-prompt-detail");
    const labelEl = document.getElementById("sqbt-prompt-label");
    const input = document.getElementById("sqbt-prompt-input");
    const okBtn = document.getElementById("sqbt-prompt-ok");
    if (!dialog || !form || !input) {
      const fallback = window.prompt(title, defaultValue);
      resolve(fallback == null ? null : String(fallback));
      return;
    }
    if (titleEl) titleEl.textContent = title;
    if (kickerEl) kickerEl.textContent = kicker;
    if (detailEl) {
      detailEl.textContent = detail || "";
      detailEl.classList.toggle("hidden", !detail);
    }
    if (labelEl) labelEl.textContent = label;
    if (okBtn) okBtn.textContent = okLabel;
    input.value = String(defaultValue || "");
    const onClose = () => {
      dialog.removeEventListener("close", onClose);
      const value = dialog.returnValue === "ok" ? String(input.value || "") : null;
      resolve(value);
    };
    dialog.addEventListener("close", onClose);
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "open");
    window.setTimeout(() => {
      input.focus();
      input.select();
    }, 30);
  });
}

function readSerialsSegment() {
  try {
    const saved = String(localStorage.getItem(SERIALS_SEGMENT_KEY) || "").trim();
    if (SERIALS_SEGMENTS.some((row) => row.id === saved)) return saved;
  } catch {
    /* ignore */
  }
  return serialsActiveSegment || "send";
}

function writeSerialsSegment(segmentId) {
  serialsActiveSegment = segmentId;
  try {
    localStorage.setItem(SERIALS_SEGMENT_KEY, segmentId);
  } catch {
    /* ignore */
  }
}

function serialsSegmentForSection(section) {
  const title = String(section.title || "").toLowerCase();
  if (section.serialStore || title.includes("library") || title.includes("my packs")) return "library";
  if (section.serialSendList || title === "send") return "send";
  if (
    section.catalog === "gzo" ||
    section.catalog === "lootlemon" ||
    title.includes("gzo") ||
    title.includes("lootlemon") ||
    title.includes("browse")
  ) {
    return "codes";
  }
  if (title.includes("mail") || title.includes("reward") || title.includes("pending")) return "mail";
  return "send";
}

function serialsSegmentHint(active) {
  if (active === "library") return "My packs — save / import / export @U packs here.";
  if (active === "codes") return "GZO + Lootlemon community codes — Refresh if the list is empty.";
  if (active === "mail") return "Mailbox / Reward Center — open pending rewards here.";
  return "Send serials. Tabs above: My packs (library) · GZO / Lootlemon · Mail.";
}

function applySerialsSegment(segmentId) {
  const active = SERIALS_SEGMENTS.some((row) => row.id === segmentId) ? segmentId : "send";
  writeSerialsSegment(active);
  tabContent.querySelectorAll("[data-serials-segment]").forEach((el) => {
    el.classList.toggle("hidden", el.dataset.serialsSegment !== active);
  });
  tabContent.querySelectorAll(".serials-segment-btn").forEach((btn) => {
    const on = btn.dataset.segment === active;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
  const hint = tabContent.querySelector(".serials-segment-hint");
  if (hint) hint.textContent = serialsSegmentHint(active);
}

function renderSerialsSegmentNav() {
  const nav = document.createElement("nav");
  nav.className = "serials-segment-nav";
  nav.setAttribute("role", "tablist");
  nav.setAttribute("aria-label", "Serials sections");
  const active = readSerialsSegment();
  for (const row of SERIALS_SEGMENTS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "serials-segment-btn";
    btn.dataset.segment = row.id;
    btn.textContent = row.label;
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", row.id === active ? "true" : "false");
    if (row.id === active) btn.classList.add("active");
    if (row.id === "library") {
      btn.title = "Saved serial packs (My packs / library)";
      btn.classList.add("serials-segment-emphasis");
    } else if (row.id === "codes") {
      btn.title = "Browse GZO and Lootlemon codes";
      btn.classList.add("serials-segment-emphasis");
    }
    btn.addEventListener("click", () => applySerialsSegment(row.id));
    nav.appendChild(btn);
  }
  const hint = document.createElement("p");
  hint.className = "serials-segment-hint muted small";
  hint.textContent = serialsSegmentHint(active);
  nav.appendChild(hint);
  return nav;
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
  const params = { limit: 2000 };
  params.search = fieldValues[`${sectionId}:search`] || "";
  for (const filter of config.filters || []) {
    const param = filter.catalogParam || filter.key;
    params[param] = fieldValues[`${sectionId}:${filter.key}`] ?? filter.default ?? "";
  }
  if ((config.kind || "") === "backpack" || config.catalog === "backpack") {
    params.player_index = preferredDeliveryPlayerIndex(latestStatus?.raw?.players || []);
  }
  if (config.params && typeof config.params === "object") {
    Object.assign(params, config.params);
  }
  return params;
}

function multiselectRowId(row, config) {
  const idKey = config.idKey || config.valueKey || "id";
  return String(row[idKey] || row.serial || row.id || "");
}

function isDeliverableSerial(serial) {
  const s = String(serial || "").trim();
  if (!s) return false;
  return s.startsWith("@U") || (s.includes(",") && /\d/.test(s));
}

function rememberMultiselectSerial(sectionId, rowId, serial) {
  const s = String(serial || "").trim();
  if (!s || !rowId) return;
  if (!multiselectSerialById.has(sectionId)) {
    multiselectSerialById.set(sectionId, new Map());
  }
  multiselectSerialById.get(sectionId).set(String(rowId), s);
}

function rowSerialValue(row, config) {
  return String(row.serial || row[config.valueKey || "serial"] || "").trim();
}

function cacheMultiselectRows(sectionId, rows, config) {
  for (const row of rows || []) {
    const rowId = multiselectRowId(row, config);
    const serial = rowSerialValue(row, config);
    if (serial) rememberMultiselectSerial(sectionId, rowId, serial);
  }
}

function formatMultiselectSelectedLabel(sectionId, config) {
  const selected = multiselectState.get(sectionId) || new Set();
  const rows = multiselectRows.get(sectionId) || [];
  const rowIds = new Set(rows.map((row) => multiselectRowId(row, config)));
  let onScreen = 0;
  for (const id of selected) {
    if (rowIds.has(id)) onScreen += 1;
  }
  const offScreen = selected.size - onScreen;
  if (offScreen > 0) {
    return `${selected.size} selected (${offScreen} off-screen)`;
  }
  return `${selected.size} selected`;
}

function collectSelectedSerials(sectionId, config) {
  const selected = multiselectState.get(sectionId) || new Set();
  const rows = multiselectRows.get(sectionId) || [];
  const cache = multiselectSerialById.get(sectionId) || new Map();
  const rowById = new Map();
  for (const row of rows) {
    const rowId = multiselectRowId(row, config);
    rowById.set(rowId, row);
    const serial = rowSerialValue(row, config);
    if (serial) rememberMultiselectSerial(sectionId, rowId, serial);
  }
  const serials = [];
  const libraryRows = [];
  const seen = new Set();
  for (const id of selected) {
    const row = rowById.get(id);
    let serial = row ? rowSerialValue(row, config) : "";
    if (!serial) serial = String(cache.get(String(id)) || "").trim();
    if (!isDeliverableSerial(serial)) continue;
    if (seen.has(serial)) continue;
    seen.add(serial);
    serials.push(serial);
    const title = String(
      (row && (row.title || row.name || row[config.labelKey || "title"])) || serial.slice(0, 48)
    ).trim();
    libraryRows.push({ serial, title, name: title });
  }
  return { serials, rows: libraryRows, selectedCount: selected.size };
}

function refreshAllSerialStoreSections() {
  for (const box of document.querySelectorAll("[data-multiselect-section]")) {
    const sectionId = box.dataset.multiselectSection;
    if (!sectionId) continue;
    const config = getMultiselectConfig(sectionId);
    if (config?.catalog !== "serial_store") continue;
    catalogCache.delete(catalogCacheKey("serial_store", multiselectParams(sectionId, config)));
    refreshMultiselectSection(sectionId, config);
  }
}

const WORLD_SPAWN_ACTIONS = new Set([
  "shiny_drop_all",
  "spawn_item_pool",
  "spawn_item_pool_all",
  "spawn_item_pool_singular_test",
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

function hostPlayerIndex(players) {
  const list = Array.isArray(players) ? players : [];
  const host = list.find((row) => row.is_host || row.host);
  if (host && host.index != null && host.index !== "") return Number(host.index);
  return 0;
}

function playerOptionLabel(row) {
  const rawName = String(row?.name || "").trim();
  const base = rawName || (row?.is_host ? "Host" : `Player ${row?.index}`);
  const lvl = row?.level != null && row?.level !== "" ? Number(row.level) : NaN;
  const levelBit = Number.isFinite(lvl) && lvl > 0 ? ` · L${lvl}` : "";
  return `${base}${levelBit} (#${row?.index})`;
}

function preferredDeliveryPlayerIndex(players) {
  const list = Array.isArray(players) ? players : [];
  // Roster / dropdown click sets pendingTargetIndex immediately. The <select>
  // value can lag (or stay on host 0) — that made UVHM hit Squ1ggs while the
  // roster highlight showed a guest. Pending wins while fresh.
  if (pendingTargetIndex != null && Date.now() < pendingTargetUntil) {
    const pending = Number(pendingTargetIndex);
    if (!Number.isNaN(pending)) {
      if (pending === -1) return -1;
      if (list.some((row) => Number(row.index) === pending)) return pending;
    }
  }
  const target = effectiveTargetIndex(latestStatus?.raw || {});
  if (target != null && Number(target) === -1) return -1;
  if (target != null && list.some((row) => Number(row.index) === Number(target))) {
    return Number(target);
  }
  // Dropdown last — only when it agrees with a live roster row.
  if (globalTargetSelect && !globalTargetSelect.disabled && globalTargetSelect.value !== "") {
    const fromUi = Number(globalTargetSelect.value);
    if (!Number.isNaN(fromUi)) {
      if (fromUi === -1) return -1;
      if (list.some((row) => Number(row.index) === fromUi)) return fromUi;
    }
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
    "mobility_force_fly",
    "mobility_infinite_jump",
    "backpack_scan_status",
    "backpack_relevel_selected",
    "backpack_export_txt",
    "faafo_drop_backpack",
  ]);
  // These actions need a single concrete player — never stamp "All players" (-1).
  // uvhm_start accepts All and routes to all-lobby on the bridge.
  const BOOST_TARGET_NO_ALL = new Set([
    "party_kick",
    "teleport_party",
    "backpack_scan_status",
    "backpack_relevel_selected",
    "backpack_export_txt",
  ]);
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
  if (action === "uvhm_start") {
    const players = latestStatus?.raw?.players || [];
    const idx = Number(
      next.player_index != null && next.player_index !== ""
        ? next.player_index
        : preferredDeliveryPlayerIndex(players)
    );
    if (!Number.isNaN(idx)) next.player_index = idx;
    const name =
      playerNameForIndex(players, idx) ||
      latestStatus?.raw?.target_player_name ||
      boostTargetDisplayName();
    if (name && name !== "selected") next.target_name = String(name).trim();
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
  if (openRaw === "yes" || openRaw === true) {
    payload.open_rewards = true;
  } else if (openRaw === "no" || openRaw === false) {
    payload.open_rewards = false;
  } else if (openRaw === undefined || openRaw === "") {
    payload.open_rewards = true;
  } else {
    payload.open_rewards = Boolean(openRaw);
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
  const params = { search, category, limit: 2000 };
  for (const toggle of config.toggles || []) {
    const key = `${sectionId}:${toggle.key}`;
    const on = fieldValues[key] === undefined ? Boolean(toggle.default) : Boolean(fieldValues[key]);
    params[toggle.key] = on ? "1" : "0";
  }
  return params;
}

function applyItemPoolPayload(sectionId, payload) {
  const search = fieldValues[`${sectionId}:search`] || "";
  let category = fieldValues[`${sectionId}:category`] || "All";
  if (search.trim().toLowerCase().includes("shiny") && category === "All") {
    category = "Shiny";
  }
  payload.search = search;
  payload.category = category;
  const sectionEl = tabContent?.querySelector(`[data-section-id="${sectionId}"]`);
  let toggles = [];
  try {
    const raw = sectionEl?.dataset?.poolBrowserConfig;
    if (raw) toggles = JSON.parse(raw).toggles || [];
  } catch {
    toggles = [];
  }
  for (const toggle of toggles) {
    const key = `${sectionId}:${toggle.key}`;
    const on = fieldValues[key] === undefined ? Boolean(toggle.default) : Boolean(fieldValues[key]);
    payload[toggle.key] = on ? "1" : "0";
  }
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
  // Stop must not re-merge lobby checkboxes / accidentally re-arm.
  if (actionDef.action === "auto_lobby_stop") {
    return { enabled: false };
  }
  // Auto Lobby: trust what is on screen right now (off stays off, typed amounts win).
  if (
    actionDef.action === "auto_lobby_start" ||
    actionDef.action === "auto_lobby_set"
  ) {
    syncSectionFieldsFromDom(sectionId);
  }
  mergeSectionFieldsIntoPayload(sectionId, payload);
  if (actionDef.action === "auto_lobby_start") {
    payload.enabled = true;
    autoLobbyTouchedKeys.clear();
  }
  if (actionDef.action === "auto_lobby_set") {
    autoLobbyTouchedKeys.clear();
  }

  if (actionDef.action === "spawn_item_pool" || actionDef.action === "spawn_item_pool_all" || actionDef.action === "spawn_item_pool_singular_test") {
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

  if (actionDef.deliverFromPaste) {
    const area = document.querySelector(`textarea[data-serial-paste-area="${sectionId}"]`);
    const raw = area?.value || "";
    payload.__serials_raw = raw;
    payload.serials = raw;
    if (fieldValues[`${sectionId}:level_override`] === "yes") {
      payload.level_override = true;
      payload.level = Number(fieldValues[`${sectionId}:level`] || 70);
    }
    return applyDeliveryRecipient(payload, sectionId);
  }

  if (actionDef.deliverMultiselect) {
    const config = getMultiselectConfig(sectionId);
    const picked = collectSelectedSerials(sectionId, config);
    payload.serials = picked.serials;
    if (fieldValues[`${sectionId}:level_override`] === "yes") {
      payload.level_override = true;
      payload.level = Number(fieldValues[`${sectionId}:level`] || 70);
    }
    payload._selected_count = picked.selectedCount;
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

  if (actionDef.backpackMultiselect) {
    const selected = multiselectState.get(sectionId) || new Set();
    const rows = multiselectRows.get(sectionId) || [];
    const config = getMultiselectConfig(sectionId);
    const valueKey = config.valueKey || "slot";
    payload.slots = rows
      .filter((row) => selected.has(multiselectRowId(row, config)))
      .map((row) => Number(row[valueKey] ?? row.slot))
      .filter((n) => !Number.isNaN(n));
  }

  if (actionDef.packBayCopy || actionDef.action === "pack_bay_open_toolbox") {
    const config = getMultiselectConfig(sectionId);
    const picked = collectSelectedSerials(sectionId, config);
    payload.serials = picked.serials;
  }

  if (actionDef.action === "backpack_scan_status") {
    const config = getMultiselectConfig(sectionId);
    if (config?.params && typeof config.params === "object") {
      Object.assign(payload, config.params);
    }
    if (config?.source === "save_yaml") {
      payload.pack_bay = true;
    }
  }

  if (actionDef.deliverStore) {
    const config = getMultiselectConfig(sectionId);
    const picked = collectSelectedSerials(sectionId, config);
    payload.serials = picked.serials;
    if (fieldValues[`${sectionId}:level_override`] === "yes") {
      payload.level_override = true;
      payload.level = Number(fieldValues[`${sectionId}:level`] || 70);
    }
    payload._selected_count = picked.selectedCount;
    return applyDeliveryRecipient(payload, sectionId);
  }

  if (actionDef.addSelectedToLibrary) {
    const config = getMultiselectConfig(sectionId);
    const picked = collectSelectedSerials(sectionId, config);
    payload.rows = picked.rows;
    payload.serials = picked.serials;
    payload.titles = picked.rows.map((row) => row.title || row.name || "");
    if (!payload.group) {
      const cat = String(config?.catalog || "").toLowerCase();
      if (config?.params?.party_bay) payload.group = "Live Pack";
      else if (config?.params?.pack_bay || config?.source === "save_yaml") payload.group = "Save Pack";
      else payload.group = cat === "lootlemon" ? "Lootlemon" : cat === "gzo" ? "GZO" : "Imported";
    }
    payload._selected_count = picked.selectedCount;
    return payload;
  }

  if (actionDef.action === "serial_store_import_serials") {
    const nameKey = actionFieldKey(sectionId, actionDef, { key: "name" });
    if (payload.name === undefined || payload.name === "") {
      payload.name = fieldValues[nameKey] || "";
    }
    if (!payload.group) payload.group = String(payload.name || "").trim() || "Paste";
    const hasSerials = Array.isArray(payload.serials) && payload.serials.length;
    if (!hasSerials) {
      const convertText = String(fieldValues[`${sectionId}:serial_convert:input`] || "").trim();
      const pasteEl = document.querySelector(
        `[data-section-id="${sectionId}"] textarea[data-serial-paste-area]`
      );
      const pasteText = String(pasteEl?.value || "").trim();
      const text = String(payload.input || payload.text || convertText || pasteText || "").trim();
      if (text) payload.text = text;
    }
    return payload;
  }

  if (actionDef.action === "serial_store_save") {
    syncSerialStoreEditFromForm(sectionId);
    const edit = serialStoreEdit.get(sectionId) || {};
    let serial = String(edit.serial || "").trim();
    if (!serial) {
      const pasteEl = serialStoreSectionEl(sectionId)?.querySelector(
        "textarea[data-serial-paste-area]"
      );
      serial = String(pasteEl?.value || "").trim();
    }
    let name = String(edit.name || "").trim();
    if (!name && serial) {
      name = serial.replace(/\s+/g, " ").slice(0, 40);
      if (serial.length > 40) name += "…";
    }
    let group = String(edit.group || "").trim();
    // Never treat the Pack filter value "All" as a destination pack.
    if (!group || group.toLowerCase() === "all") group = "Default";
    payload.id = edit.id || "";
    payload.name = name;
    payload.group = group;
    payload.serial = serial;
    if (!payload.serial) {
      throw new Error("Paste codes into the box, then Save.");
    }
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

  if (actionDef.action === "serial_store_create_group") {
    return payload;
  }

  if (actionDef.action === "serial_store_delete_group") {
    syncSerialStoreEditFromForm(sectionId);
    const edit = serialStoreEdit.get(sectionId) || {};
    let group = String(edit.group || "").trim();
    if (!group || group.toLowerCase() === "all") {
      group = String(fieldValues[`${sectionId}:group`] || "").trim();
    }
    payload.group = group;
    if (!payload.group || payload.group.toLowerCase() === "all") {
      throw new Error("Set a Pack name (or filter to one pack) before Delete pack.");
    }
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
    if (field.type === "checkbox") {
      payload[field.key] = value === true || String(value).toLowerCase() === "true";
      continue;
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
    if (field.key === "include_consumables" || field.key === "random_spread") {
      payload[field.key] = String(value).toLowerCase() === "yes" || value === true;
      continue;
    }
    if (field.key === "level_override") {
      payload.level_override = String(value).toLowerCase() === "yes" || value === true;
      continue;
    }
    if (field.type === "textarea" && field.key === "serials") {
      // Placeholder — resolved asynchronously in runAction so file paths work too.
      payload.serials = String(value);
      payload.__serials_raw = String(value);
      continue;
    }
    if (field.land_profile) {
      payload.land_profile = field.land_profile;
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
    if (payload.mail_to_self || actionDef.mailToSelf) {
      payload.player_index = hostPlayerIndex(latestStatus?.raw?.players || []);
      payload.mode = "player";
      delete payload.mail_to_self;
    } else if (payload.player_index === undefined || payload.player_index === "") {
      payload.player_index = preferredDeliveryPlayerIndex(latestStatus?.raw?.players || []);
      payload.mode = Number(payload.player_index) === -1 ? "all" : "player";
    }
  }
  if (actionDef.action === "mobility_infinite_jump" || actionDef.action === "mobility_force_fly") {
    if (payload.player_index === undefined || payload.player_index === "") {
      payload.player_index = preferredDeliveryPlayerIndex(latestStatus?.raw?.players || []);
    }
  }
  return payload;
}

function boostTargetConfirmLabel() {
  const players = latestStatus?.raw?.players || [];
  const idx = preferredDeliveryPlayerIndex(players);
  if (Number(idx) === -1) {
    return "ALL PLAYERS (entire lobby)";
  }
  const name =
    playerNameForIndex(players, idx) ||
    latestStatus?.raw?.target_player_name ||
    `player #${idx}`;
  return `${name} (Boost target #${idx})`;
}

function buildDropBackpackConfirm(base) {
  const who = boostTargetConfirmLabel();
  const allPlayers = who.startsWith("ALL PLAYERS");
  const head = allPlayers
    ? "WARNING: Boost target is ALL PLAYERS — this can spill EVERYONE'S backpack onto the ground."
    : `Boost target right now: ${who}`;
  return [
    head,
    "",
    "Look at Boost target (under the tabs) before you continue.",
    "If you only want your own loot dropped, select yourself — not All players, and not a friend unless they asked.",
    "",
    base || "Spill that player's whole backpack onto the ground?",
  ].join("\n");
}

async function runAction(action, payload, confirmText, context = {}) {
  let prompt = confirmText || "";
  if (action === "faafo_drop_backpack") {
    prompt = buildDropBackpackConfirm(prompt);
  }
  if (action === "uvhm_start") {
    const who = boostTargetConfirmLabel();
    const allLobby = who.startsWith("ALL PLAYERS") || Number(payload?.player_index) === -1;
    if (allLobby) {
      prompt =
        "Run UVHM for the entire lobby (safe all-lobby path — missing remotes are skipped)?\n\n" +
        "This is the same as Progression → Start UVHM (all lobby).";
    } else {
      prompt =
        `Start UVHM 1–7 for ${who}?\n\n` +
        "Look at that name carefully — if it says YOU / the host, cancel and click the guest in Boost target first.\n" +
        "Set Boost target to All players (or use Start UVHM all lobby) for everyone.";
    }
  }
  if (action === "uvhm_start_all") {
    prompt =
      prompt ||
      "Run UVHM for the entire lobby (safe all-lobby path — missing remotes are skipped)?";
  }
  if (prompt && !window.confirm(prompt)) {
    return;
  }
  if (action === "set_target_player" && (payload.player_index === undefined || payload.player_index === "")) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = t("action.pickPlayer");
    return;
  }
  if (action === "serial_store_export_text" || action === "serial_store_export_json") {
    const sectionId = context.sectionId || "";
    const groupKey = `${sectionId}:group`;
    if (payload.group == null || payload.group === "") {
      payload.group = fieldValues[groupKey] || "All";
    }
  }
  if (action === "serial_store_create_group") {
    const next = await promptTextDialog({
      kicker: "My packs",
      title: "New pack",
      detail: "Name the pack, paste codes, then Save. Import adds — it never wipes.",
      label: "Pack name",
      defaultValue: "New pack",
      okLabel: "Create",
    });
    if (next == null) return;
    const cleaned = String(next).trim();
    if (!cleaned) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = "Pack name is required.";
      return;
    }
    payload.group = cleaned;
    payload.name = cleaned;
  }
  if (action === "serial_store_delete_group") {
    const sectionId = context.sectionId || "";
    if (!payload.group) {
      syncSerialStoreEditFromForm(sectionId);
      const edit = serialStoreEdit.get(sectionId) || {};
      payload.group = String(edit.group || fieldValues[`${sectionId}:group`] || "").trim();
    }
    const pack = String(payload.group || "").trim();
    if (!pack || pack.toLowerCase() === "all") {
      actionMessage.className = "action-message error";
      actionMessage.textContent = "Pick a pack name first (not All).";
      return;
    }
    if (!window.confirm(`Delete entire pack "${pack}" and all of its serials?`)) {
      return;
    }
    payload.group = pack;
  }
  if (action === "serial_store_import_merge") {
    try {
      const text = await pickLibraryImportText();
      if (text == null) return;
      payload.text = text;
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error || "Import cancelled.");
      return;
    }
  }
  actionBusy = true;
  refreshActionButtons();
  actionMessage.className = "action-message muted";
  actionMessage.textContent = "Running…";
  let resolvedAction = action;
  const finalPayload = enrichPayload(action, payload);
  // Boost target All → safe all-lobby UVHM (same machine as uvhm_start_all).
  if (resolvedAction === "uvhm_start" && Number(finalPayload.player_index) === -1) {
    resolvedAction = "uvhm_start_all";
    finalPayload.confirmed = true;
  }
  if (resolvedAction === "deliver_serials") {
    const raw =
      finalPayload.__serials_raw != null
        ? String(finalPayload.__serials_raw)
        : Array.isArray(finalPayload.serials)
          ? finalPayload.serials.join("\n")
          : String(finalPayload.serials || "");
    // Multiselect / send-list already supplies a clean serial array — only resolve
    // text when the payload still looks like pasted text / file paths.
    const needsResolve =
      typeof finalPayload.serials === "string" ||
      (Array.isArray(finalPayload.serials) &&
        finalPayload.serials.some((line) => looksLikeSerialFilePath(String(line || ""))));
    if (needsResolve || finalPayload.__serials_raw != null) {
      const resolved = await resolveSerialInputText(raw);
      delete finalPayload.__serials_raw;
      if (!resolved.serials.length) {
        actionBusy = false;
        refreshActionButtons();
        actionMessage.className = "action-message error";
        actionMessage.textContent =
          resolved.message ||
          "No usable serials found. Paste @U codes or a .txt / .docx path.";
        return;
      }
      finalPayload.serials = resolved.serials;
    } else {
      delete finalPayload.__serials_raw;
    }
  }
  let timeout = 12;
  if (action === "shiny_drop_all") {
    timeout = 20;
  } else if (action === "spawn_item_pool" || action === "spawn_item_pool_all" || action === "spawn_item_pool_singular_test") {
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
          ? `${selectedHint} row(s) selected but none had a deliverable serial. Use Select all filtered (loads off-screen rows), or re-save entries with @U / human serials.`
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
    // Queue returns quickly; scale wait so large GZO batches don't false-timeout.
    const nSerials = finalPayload.serials.length;
    // Match in-game chunking: large packs use fewer serials per mail package.
    const perPkg = nSerials >= 500 ? 6 : nSerials >= 200 ? 10 : 12;
    const packages = Math.max(1, Math.ceil(nSerials / perPkg));
    const selectedHintCount = selectedHint || nSerials;
    if (nSerials >= 25) {
      let confirmText = `Deliver ${nSerials} unique serial(s) in ~${packages} mail package(s)?`;
      if (nSerials >= 400) {
        confirmText =
          `${confirmText}\n\nLarge pack: paced mail (~1s+ between packages). Stay in-world until delivery finishes.`;
      }
      if (selectedHintCount > nSerials) {
        confirmText = `Deliver ${nSerials} unique serial(s) (${selectedHintCount} row(s) selected) in ~${packages} mail package(s)?`;
      }
      if (finalPayload.open_rewards) {
        confirmText = `${OPEN_REWARDS_LARGE_WARNING}\n\n${confirmText}`;
      }
      if (!confirmSerialRisk(confirmText)) {
        actionBusy = false;
        refreshActionButtons();
        actionMessage.className = "action-message muted";
        actionMessage.textContent = "Cancelled.";
        return;
      }
    } else if (finalPayload.open_rewards) {
      if (
        !confirmSerialRisk(
          `${OPEN_REWARDS_LARGE_WARNING}\n\nContinue with auto-open for ${nSerials} item(s)?`
        )
      ) {
        actionBusy = false;
        refreshActionButtons();
        actionMessage.className = "action-message muted";
        actionMessage.textContent = "Cancelled.";
        return;
      }
    }
    timeout = Math.min(480, Math.max(45, 20 + packages * 8));
  }
  if (
    (action === "spawn_mobs" && !(finalPayload.codes || []).length) ||
    (action === "bms_group_add" && !(finalPayload.codes || []).length) ||
    (action === "spawn_ios" && !(finalPayload.cmds || []).length)
  ) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = t("action.tickEntry");
    actionBusy = false;
    refreshActionButtons();
    return;
  }
  if (action === "challenge_complete_selected" && !(finalPayload.tokens || []).length) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = t("action.tickChallenge");
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
  if (action === "backpack_relevel_selected") {
    if (Number(finalPayload.player_index) === -1) {
      actionMessage.className = "action-message error";
      actionMessage.textContent =
        "Pick one player in Boost target (not All players) before releveling backpack gear.";
      actionBusy = false;
      refreshActionButtons();
      return;
    }
    if (!Array.isArray(finalPayload.slots) || !finalPayload.slots.length) {
      actionMessage.className = "action-message error";
      actionMessage.textContent =
        "Tick at least one backpack item in the list above, pick a new level, then relevel.";
      actionBusy = false;
      refreshActionButtons();
      return;
    }
  }
  if (action === "backpack_export_txt") {
    if (Number(finalPayload.player_index) === -1) {
      actionMessage.className = "action-message error";
      actionMessage.textContent =
        "Pick one player in Boost target (not All players) before exporting backpack @U.";
      actionBusy = false;
      refreshActionButtons();
      return;
    }
  }
  if (action === "rewards_open_everyone") {
    if (lastChallengeStatus?.active) {
      actionBusy = false;
      refreshActionButtons();
      actionMessage.className = "action-message error";
      actionMessage.textContent =
        "Complete ALL / challenge bulk is still running — leave Open pending rewards off (often hundreds of packages).";
      return;
    }
    if (suppressOpenAllAfterChallenge) {
      const players = latestStatus?.raw?.players || [];
      if (Array.isArray(players) && players.length > 1) {
        actionBusy = false;
        refreshActionButtons();
        actionMessage.className = "action-message error";
        actionMessage.textContent = OPEN_ALL_AFTER_CHALLENGE_WARNING;
        return;
      }
      if (
        !window.confirm(
          `${OPEN_ALL_AFTER_CHALLENGE_WARNING}\n\nYou appear to be solo. Open every pending package now (paced)?`
        )
      ) {
        actionBusy = false;
        refreshActionButtons();
        actionMessage.className = "action-message muted";
        actionMessage.textContent = "Cancelled — leave Open pending rewards off after Complete ALL.";
        return;
      }
      finalPayload.force = true;
      finalPayload.confirmed_large = true;
    }
  }
  try {
    if (resolvedAction === "deliver_serials" || resolvedAction === "rewards_open_everyone") {
      // Show the floating bar immediately — first mail/pack send can sit on the
      // bridge while codes convert / queue (second click feels instant).
      const nSerials = Array.isArray(finalPayload.serials) ? finalPayload.serials.length : 0;
      const perPkg = nSerials >= 500 ? 6 : nSerials >= 200 ? 10 : 12;
      const packagesGuess = Math.max(
        1,
        resolvedAction === "rewards_open_everyone"
          ? 1
          : Math.ceil(Math.max(1, nSerials) / perPkg)
      );
      lastSerialDeliveryStatus = {
        active: true,
        queued: true,
        index: 0,
        total: packagesGuess,
        percent: 0,
        message:
          resolvedAction === "rewards_open_everyone"
            ? "Opening pending rewards…"
            : "Queuing mail / packs…",
        label: `0/${packagesGuess}`,
        scope: resolvedAction === "rewards_open_everyone" ? "everyone" : "",
      };
      lastProgressHtml = "";
      renderProgressPanel(null, null, null, lastSerialDeliveryStatus);
      startProgressPoll();
    }
    let { httpStatus, data } = await window.sqbt.postAction(resolvedAction, finalPayload, timeout);
    if (data?.ok === false && resolvedAction === "rewards_open_everyone" && data?.needs_force && !finalPayload.force) {
      const pendingN = Number(data?.packages || 0);
      const detail = pendingN > 0 ? ` (${pendingN} pending)` : "";
      if (
        window.confirm(
          `${data.message || OPEN_ALL_AFTER_CHALLENGE_WARNING}${detail}\n\nOpen all pending packages anyway?`
        )
      ) {
        finalPayload.force = true;
        finalPayload.confirmed_large = true;
        const retry = await window.sqbt.postAction(resolvedAction, finalPayload, timeout);
        httpStatus = retry.httpStatus;
        data = retry.data || data;
        if (data?.ok) suppressOpenAllAfterChallenge = false;
      } else {
        actionMessage.className = "action-message muted";
        actionMessage.textContent = "Cancelled — bank / mule before opening mass challenge mail.";
        actionBusy = false;
        refreshActionButtons();
        return;
      }
    }
    if (data?.ok === false || httpStatus === 202) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = friendlyActionError(data?.message || JSON.stringify(data));
      if (
        (resolvedAction === "deliver_serials" || resolvedAction === "rewards_open_everyone") &&
        lastSerialDeliveryStatus?.queued &&
        !lastSerialDeliveryStatus?.finishing
      ) {
        lastSerialDeliveryStatus = null;
        lastProgressHtml = "";
        renderProgressPanel(null, null, null, null);
      }
    } else {
      actionMessage.className = "action-message ok";
      actionMessage.textContent = data?.message || "Done.";
      if (action === "rewards_open_everyone" && data?.ok) {
        suppressOpenAllAfterChallenge = false;
      }
    }
    if (data?.warning && String(data.warning).trim()) {
      const base = String(actionMessage.textContent || "").trim();
      actionMessage.textContent = base ? `${base} ${data.warning}` : String(data.warning);
      if (actionMessage.className === "action-message ok") {
        actionMessage.className = "action-message attention";
      }
    }
    if (action === "mobility_force_fly" && data?.ok !== false) {
      actionMessage.className = "action-message ok";
      actionMessage.textContent = data?.message || actionMessage.textContent;
      showMobilityToast(data?.message, data?.force_fly_on ? "ok" : "off");
      if (!finalPayload.apply_speed_only && !finalPayload.reapply_only) {
        const syncKey = "force_fly";
        syncMobilityToggleButtons(syncKey, Boolean(data?.force_fly_on));
        // Legacy Force fly (all) sticky — keep UI off; fly is host-only now.
        syncMobilityToggleButtons("force_fly_all", false);
      }
      if (data?.fly_speed != null) {
        applyFieldValues({ fly_speed: data.fly_speed });
        updateFlySpeedLivePanels(
          data.fly_speed,
          data.fly_preset,
          Boolean(data?.force_fly_on)
        );
      }
    }
    if (action === "mobility_infinite_jump" && data?.ok !== false) {
      showMobilityToast(data?.message, data?.infinite_jump_on ? "ok" : "off");
      const scope = String(data?.infinite_jump_scope || finalPayload.scope || "target").toLowerCase();
      const on = Boolean(data?.infinite_jump_on);
      if (scope === "all") {
        syncMobilityToggleButtons("infinite_jump_all", on);
        syncMobilityToggleButtons("infinite_jump", on);
      } else {
        syncMobilityToggleButtons("infinite_jump", on);
        // Turning a single target off must not leave the All button stuck ON.
        if (!on) syncMobilityToggleButtons("infinite_jump_all", false);
      }
    }
    if (action === "mobility_noclip" && data?.ok !== false) {
      syncMobilityToggleButtons("noclip", Boolean(data?.noclip));
      if (Object.prototype.hasOwnProperty.call(data || {}, "force_fly")) {
        syncMobilityToggleButtons("force_fly", Boolean(data.force_fly));
      }
      if (data?.fly_speed != null) {
        applyFieldValues({ fly_speed: data.fly_speed });
        updateFlySpeedLivePanels(
          data.fly_speed,
          data.fly_preset,
          Boolean(data?.force_fly)
        );
      }
    }
    if (action === "map_fog_hide" && data?.ok !== false) {
      syncMobilityToggleButtons("map_fog", Boolean(data?.hidden));
    }
    if (action === "hold_session" && data?.ok !== false) {
      syncMobilityToggleButtons("hold_session", Boolean(data?.enabled));
    }
    if (action === "god_mode") {
      if (data?.ok !== false && httpStatus !== 202) {
        const on = Object.prototype.hasOwnProperty.call(data || {}, "god_mode")
          ? Boolean(data.god_mode)
          : Boolean(finalPayload.enabled);
        syncMobilityToggleButtons("god_mode", on);
      } else {
        // Revert optimistic paint when the bridge rejected the toggle.
        syncMobilityToggleButtons("god_mode", !Boolean(finalPayload.enabled));
      }
    }
    if (action === "infinite_ammo") {
      if (data?.ok !== false && httpStatus !== 202) {
        const on = Object.prototype.hasOwnProperty.call(data || {}, "infinite_ammo")
          ? Boolean(data.infinite_ammo)
          : Boolean(finalPayload.enabled);
        syncMobilityToggleButtons("infinite_ammo", on);
      } else {
        syncMobilityToggleButtons("infinite_ammo", !Boolean(finalPayload.enabled));
      }
    }
    if (action === "rarity_weights_set" && data?.ok && data?.weights) {
      applyFieldValues(data.weights);
    }
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
    if (action === "black_market" && data?.values) {
      applyFieldValues(data.values);
    }
    if (
      action === "shiny_drop_all" ||
      action === "loot_shape_place" ||
      action === "loot_shape_arrange" ||
      action === "loot_shape_clear" ||
      action === "loot_cleanup" ||
      String(action || "").startsWith("loot_shape")
    ) {
      lastProgressHtml = "";
      startProgressPoll();
    }
    if (action === "auto_lobby_start" || action === "auto_lobby_set" || action === "auto_lobby_stop") {
      if (action === "auto_lobby_stop") {
        lastAutoLobbyStatus = {
          enabled: false,
          active: false,
          message: "Off.",
          detail: "Off",
          queued: [],
          queued_labels: [],
          current_job: "",
          current_label: "",
          next_cycle_in: 0,
          cycle_total: 0,
          cycle_done: 0,
          phase: "idle",
        };
      } else {
        const st = normalizeAutoLobbyStatus(data?.auto_lobby || data);
        if (st) lastAutoLobbyStatus = st;
        else if (action === "auto_lobby_start") {
          lastAutoLobbyStatus = {
            enabled: true,
            active: true,
            message: "Armed — first cycle in a couple of seconds.",
            detail: "Armed",
            next_cycle_in: 2,
            interval_sec: 60,
            queued_labels: [],
            cycle_total: 0,
            cycle_done: 0,
          };
        }
      }
      lastProgressHtml = "";
      if (action === "auto_lobby_stop") {
        renderProgressPanel(null, null, null);
        const stillBusy =
          isChallengeBusy(lastChallengeStatus) ||
          isUvhmBusy(lastUvhmStatus) ||
          isSpawnAllBusy(lastSpawnAllStatus) ||
          isSerialDeliveryBusy(lastSerialDeliveryStatus) ||
          isShapeBusy(lastShapeStatus);
        if (!stillBusy) stopProgressPoll();
        else startProgressPoll();
      } else {
        startProgressPoll();
      }
    }
    if (
      resolvedAction === "challenge_bulk_start" ||
      resolvedAction === "challenge_complete_selected" ||
      resolvedAction === "uvhm_start" ||
      resolvedAction === "uvhm_start_all" ||
      resolvedAction === "spawn_item_pool_all" ||
      resolvedAction === "spawn_item_pool_singular_test" ||
      resolvedAction === "loot_vacuum_nearby"
    ) {
      // Only slam the progress HUD when the bridge accepted the job — failed starts
      // used to leave active:true forever if a later poll was skipped.
      if (data?.ok !== false && httpStatus !== 202) {
        const panel = document.getElementById("sqbt-progress-panel");
        if (panel) {
          panel.classList.remove("hidden");
          if (resolvedAction === "challenge_bulk_start" || resolvedAction === "challenge_complete_selected") {
            const fromMod = data?.challenge && typeof data.challenge === "object" ? data.challenge : null;
            const queuedN = Math.max(
              0,
              Number(
                fromMod?.progress_total ||
                  fromMod?.total ||
                  data?.queued_count ||
                  data?.progress_total ||
                  data?.count ||
                  0
              )
            );
            const shortMsg =
              fromMod?.message ||
              (queuedN > 0 ? `Queued ${queuedN} challenges — starting…` : "Queued — starting…");
            lastChallengeStatus = normalizeChallengeStatus({
              active: true,
              queued: Boolean(fromMod?.queued ?? true),
              running: Boolean(fromMod?.running ?? true),
              phase: fromMod?.phase || "queued",
              index: Number(fromMod?.index || fromMod?.progress_index || 0),
              total: queuedN,
              progress_index: Number(fromMod?.progress_index || fromMod?.index || 0),
              progress_total: queuedN,
              ok: Number(fromMod?.ok || 0),
              failed: Number(fromMod?.failed || 0),
              skipped: Number(fromMod?.skipped || 0),
              message: shortMsg,
              // Always optimistic until a status poll confirms live progress —
              // otherwise a missed poll freezes the bar at 0/N · queued forever.
              _optimistic: true,
            });
            challengeOptimisticUntil = Date.now() + 45000;
            challengeCompleteShownUntil = 0;
            challengeProgressStartedAt = Date.now();
            challengeProgressTotalHint = queuedN;
            challengeDisplayMilestone = 0;
            if (data?.advisory) {
              try {
                actionMessage.textContent = String(data.advisory);
              } catch {
                /* ignore */
              }
            }
            if (
              data?.ok &&
              (data?.suppress_open_all || String(finalPayload.category || "") === "All non-UVHM")
            ) {
              suppressOpenAllAfterChallenge = true;
              forceOpenRewardsFieldsOff();
            }
          } else if (resolvedAction === "spawn_item_pool_all" || resolvedAction === "spawn_item_pool_singular_test") {
            lastSpawnAllStatus = {
              active: true,
              queued: true,
              index: 0,
              total: Math.max(1, Number(data?.queued || 1)),
              ok: 0,
              failed: 0,
              message: data?.message || (resolvedAction === "spawn_item_pool_singular_test" ? "Singular test…" : "Queuing filtered pools…"),
            };
          } else if (resolvedAction === "loot_vacuum_nearby") {
            const fromMod = data?.vacuum && typeof data.vacuum === "object" ? data.vacuum : null;
            lastVacuumStatus = {
              active: true,
              queued: Number(fromMod?.queued || fromMod?.total || data?.vacuum?.total || 1),
              index: Number(fromMod?.index || 0),
              total: Math.max(1, Number(fromMod?.total || 1)),
              ok: Number(fromMod?.ok || 0),
              failed: Number(fromMod?.failed || 0),
              piled: Number(fromMod?.piled || 0),
              message: fromMod?.message || data?.message || "Loot vacuum armed…",
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
          renderProgressPanel(null, null, null);
        }
        startProgressPoll();
      }
    }
    if (action === "max_all" || action === "shiny_drop_all" || action === "deliver_serials" || action === "rewards_open_everyone") {
      actionMessage.textContent = data?.message || actionMessage.textContent;
      if (action === "max_all" && data?.ok) {
        // Challenges and UVHM are never stacked from MAX ALL — arm whichever queued.
        if (data?.challenges_queued) {
          const queuedN = Math.max(
            0,
            Number(data?.queued_count || data?.progress_total || data?.challenge?.progress_total || 0)
          );
          lastChallengeStatus = normalizeChallengeStatus({
            active: true,
            queued: true,
            running: true,
            phase: "queued",
            index: 0,
            total: queuedN,
            progress_index: 0,
            progress_total: queuedN,
            ok: 0,
            failed: 0,
            skipped: 0,
            message:
              queuedN > 0
                ? `MAX ALL · queued ${queuedN} challenges — starting…`
                : "MAX ALL · challenges queued — starting…",
            _optimistic: true,
          });
          challengeOptimisticUntil = Date.now() + 45000;
          challengeCompleteShownUntil = 0;
          challengeProgressStartedAt = Date.now();
          challengeProgressTotalHint = queuedN;
          challengeDisplayMilestone = 0;
          suppressOpenAllAfterChallenge = true;
          forceOpenRewardsFieldsOff();
          lastProgressHtml = "";
          renderProgressPanel(null, null, null);
          startProgressPoll();
        } else if (data?.uvhm_queued) {
          lastUvhmStatus = {
            active: true,
            queued: true,
            running: true,
            progress_index: 0,
            progress_total: 7,
            message: "UVHM queued from MAX ALL…",
          };
          lastProgressHtml = "";
          renderProgressPanel(null, null, null);
          startProgressPoll();
        }
      }
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
      if (action === "deliver_serials" && data?.ok) {
        // Paste-send: clear the box so the next batch is obvious.
        for (const area of document.querySelectorAll("textarea[data-serial-paste-area]")) {
          if (String(area.value || "").trim()) area.value = "";
        }
        const nSerials = Array.isArray(finalPayload.serials) ? finalPayload.serials.length : 0;
        const perPkg = nSerials >= 500 ? 6 : nSerials >= 200 ? 10 : 12;
        const packages = Math.max(
          1,
          Number(data?.packages || 0) || Math.ceil(nSerials / perPkg)
        );
        const openPollMs = finalPayload.open_rewards
          ? Math.min(1200000, Math.max(180000, packages * 1800 + 120000))
          : Math.min(600000, Math.max(120000, packages * 1200 + 45000));
        startSerialDeliveryPoll(data.message || actionMessage.textContent, {
          maxMs: openPollMs,
          total: packages,
          packages,
        });
        startProgressPoll();
      }
      if (action === "rewards_open_everyone" && data?.ok) {
        const packages = Math.max(1, Number(data?.packages || data?.opened || 1));
        const etaMs = Math.max(60000, Number(data?.eta_sec || 0) * 1000 + 45000);
        startSerialDeliveryPoll(data.message || actionMessage.textContent, {
          maxMs: Math.min(900000, Math.max(120000, etaMs)),
          total: packages,
          packages,
          scope: "everyone",
        });
        startProgressPoll();
      }
    }
    if (action === "serial_store_save" && data?.ok !== false && context.sectionId) {
      const savedGroup = String(
        data?.entry?.group || data?.group || serialStoreEdit.get(context.sectionId)?.group || "Default"
      ).trim() || "Default";
      // Keep destination pack selected; clear codes so the next paste stays in the same pack.
      serialStoreEdit.set(context.sectionId, {
        id: "",
        name: "",
        group: savedGroup,
        serial: "",
      });
      rememberSerialStorePackNames(context.sectionId, [
        ...serialStoreKnownPackNames(context.sectionId),
        savedGroup,
      ]);
      fieldValues[`${context.sectionId}:group`] = savedGroup;
      renderSerialStoreForm(context.sectionId);
      refreshMultiselectSection(context.sectionId, context.config || { catalog: "serial_store" });
    }
    if (action === "serial_store_export_text" && data?.ok && data?.text) {
      downloadTextFile(
        `sqbt-library-${String(data.group || "all").replace(/[^\w.-]+/g, "_")}.txt`,
        String(data.text)
      );
    }
    if (action === "backpack_export_txt" && data?.ok && data?.text) {
      downloadTextFile(
        `sqbt-party-bay-p${String(data.player_index ?? "x")}-${Number(data.count || 0)}serials.txt`,
        String(data.text)
      );
    }
    if (action === "serial_store_export_json" && data?.ok && data?.text) {
      downloadTextFile(
        `sqbt-library-${String(data.group || "all").replace(/[^\w.-]+/g, "_")}.json`,
        String(data.text)
      );
    }
    if (action === "serial_store_create_group" && data?.ok && context.sectionId) {
      const group = String(data.group || "New pack");
      serialStoreEdit.set(context.sectionId, {
        id: "",
        name: "",
        group,
        serial: "",
      });
      renderSerialStoreForm(context.sectionId);
      refreshAllSerialStoreSections();
    }
    if (
      (action === "serial_store_delete" ||
        action === "serial_store_duplicate" ||
        action === "serial_store_rename_group" ||
        action === "serial_store_delete_group") &&
      context.sectionId
    ) {
      if (data?.entry && context.sectionId) {
        serialStoreEdit.set(context.sectionId, { ...data.entry });
      }
      refreshMultiselectSection(context.sectionId, context.config || { catalog: "serial_store" });
    }
    if (
      (action === "serial_store_add_selected" ||
        action === "serial_store_import_text" ||
        action === "serial_store_import_serials" ||
        action === "serial_store_import_merge") &&
      data?.ok
    ) {
      refreshAllSerialStoreSections();
    }
    if (
      (action === "warp_mark_save" ||
        action === "warp_mark_delete" ||
        action === "warp_mark_list") &&
      data?.ok
    ) {
      for (const key of [...catalogCache.keys()]) {
        if (String(key).startsWith("warp_marks")) catalogCache.delete(key);
      }
      window.setTimeout(() => {
        for (const node of tabContent.querySelectorAll("[data-role='catalog-select']")) {
          const select = node.tagName === "SELECT" ? node : node.querySelector("select");
          const fieldJson = node.dataset.catalogField;
          const sectionId = node.dataset.sectionId;
          if (!select || !fieldJson || !sectionId) continue;
          try {
            const field = JSON.parse(fieldJson);
            if (field?.catalog !== "warp_marks") continue;
            const actionDef = { action: node.dataset.actionName || "catalog" };
            populateCatalogSelect(select, field, sectionId, actionDef, node);
          } catch {
            /* ignore */
          }
        }
      }, 0);
    }
    if (action === "backpack_scan_status" && context.sectionId && data?.ok !== false) {
      const config = getMultiselectConfig(context.sectionId);
      if (config?.catalog === "backpack") {
        catalogCache.delete(
          catalogCacheKey("backpack", multiselectParams(context.sectionId, config))
        );
        refreshMultiselectSection(context.sectionId, config);
      }
    }
    if (action === "backpack_relevel_selected" && data?.ok && context.sectionId) {
      const config = getMultiselectConfig(context.sectionId);
      if (config?.catalog === "backpack") {
        catalogCache.delete(
          catalogCacheKey("backpack", multiselectParams(context.sectionId, config))
        );
        refreshMultiselectSection(context.sectionId, config);
      }
    }
    if (action === "pack_bay_open_toolbox" && data?.ok) {
      const url = String(data.open_url || "https://scooterstoolbox.com").trim();
      if (url && typeof window.sqbt?.openExternal === "function") {
        try {
          await window.sqbt.openExternal(url);
        } catch {
          /* message already shows copy status */
        }
      }
    }
    if (action === "pack_bay_disable" && data?.ok) {
      await loadManifest();
    }
    if (action === "challenge_bulk_status") {
      renderProgressPanel(data?.challenge, null, null);
    }
    if (action === "uvhm_status") {
      renderProgressPanel(null, data?.uvhm, null);
    }
    if (action === "spawn_item_pool_status" || action === "spawn_item_pool_cancel") {
      renderProgressPanel(null, null, data?.spawn_all);
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
      actionMessage.textContent = friendlyActionError(text);
    }
  } finally {
    actionBusy = false;
    refreshActionButtons();
  }
}

function applyFieldValues(values) {
  if (!values || typeof values !== "object") return;
  const focused = document.activeElement;
  // If the user is typing anywhere in the tools panel, do not rewrite fields.
  if (
    focused &&
    tabContent?.contains(focused) &&
    (focused.matches("input, textarea, select") || focused.isContentEditable)
  ) {
    return;
  }
  for (const [key, value] of Object.entries(values)) {
    for (const node of tabContent.querySelectorAll("[data-field-key]")) {
      const fk = node.dataset.fieldKey || "";
      if (!fk.endsWith(`:${key}`)) continue;
      const input = node.querySelector("input, select, textarea");
      if (!input) continue;
      // Never clobber a field the user is actively editing (typing / spinner).
      if (focused === input) continue;
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
  progressPollMs = 0;
  if (challengePaintTimer) {
    clearInterval(challengePaintTimer);
    challengePaintTimer = null;
  }
}

function ensureChallengePaintTimer(challengeBusy) {
  if (!challengeBusy) {
    if (challengePaintTimer) {
      clearInterval(challengePaintTimer);
      challengePaintTimer = null;
    }
    return;
  }
  if (challengePaintTimer) return;
  // Repaint milestone estimate between status polls (large bulks finish too fast for 1-by-1).
  challengePaintTimer = setInterval(() => {
    if (!isChallengeBusy(lastChallengeStatus)) {
      clearInterval(challengePaintTimer);
      challengePaintTimer = null;
      return;
    }
    lastProgressHtml = "";
    renderProgressPanel(null, null, null);
  }, 200);
}

function loadProgressPanelPos() {
  try {
    const raw = localStorage.getItem(PROGRESS_POS_KEY);
    if (!raw) return null;
    const pos = JSON.parse(raw);
    if (Number.isFinite(pos?.left) && Number.isFinite(pos?.top)) return pos;
  } catch {
    /* ignore */
  }
  return null;
}

function saveProgressPanelPos(left, top) {
  try {
    localStorage.setItem(PROGRESS_POS_KEY, JSON.stringify({ left, top }));
  } catch {
    /* ignore */
  }
}

let progressPanelDragging = false;

function clampProgressPanelPos(panel, left, top) {
  const width = Math.max(120, panel.offsetWidth || panel.getBoundingClientRect().width || 320);
  const height = Math.max(48, panel.offsetHeight || panel.getBoundingClientRect().height || 80);
  const maxL = Math.max(8, window.innerWidth - width - 8);
  const maxT = Math.max(8, window.innerHeight - height - 8);
  return {
    left: Math.min(maxL, Math.max(8, Number(left) || 8)),
    top: Math.min(maxT, Math.max(8, Number(top) || 8)),
  };
}

function applyProgressPanelPosition(panel) {
  if (!panel || progressPanelDragging) return;
  if (!panel.classList.contains("is-floating") || panel.classList.contains("hidden")) {
    panel.style.left = "";
    panel.style.top = "";
    panel.style.right = "";
    panel.classList.remove("has-custom-pos");
    return;
  }
  const pos = loadProgressPanelPos();
  if (!pos) {
    panel.style.left = "";
    panel.style.top = "";
    panel.style.right = "";
    panel.classList.remove("has-custom-pos");
    return;
  }
  const clamped = clampProgressPanelPos(panel, pos.left, pos.top);
  panel.classList.add("has-custom-pos");
  panel.style.right = "auto";
  panel.style.left = `${clamped.left}px`;
  panel.style.top = `${clamped.top}px`;
}

function ensureProgressPanelDrag(panel) {
  if (!panel || panel.dataset.dragBound === "1") return;
  panel.dataset.dragBound = "1";
  let dragging = false;
  let startX = 0;
  let startY = 0;
  let origL = 0;
  let origT = 0;
  panel.addEventListener("pointerdown", (ev) => {
    if (!panel.classList.contains("is-floating") || panel.classList.contains("hidden")) return;
    if (ev.target?.closest?.("button, a, input, select, textarea")) return;
    const handle = ev.target?.closest?.("[data-progress-drag]");
    if (!handle) return;
    dragging = true;
    progressPanelDragging = true;
    try {
      panel.setPointerCapture(ev.pointerId);
    } catch {
      /* ignore */
    }
    const rect = panel.getBoundingClientRect();
    startX = ev.clientX;
    startY = ev.clientY;
    origL = rect.left;
    origT = rect.top;
    panel.classList.add("is-dragging", "has-custom-pos");
    panel.style.right = "auto";
    panel.style.left = `${origL}px`;
    panel.style.top = `${origT}px`;
    ev.preventDefault();
  });
  panel.addEventListener("pointermove", (ev) => {
    if (!dragging) return;
    const clamped = clampProgressPanelPos(
      panel,
      origL + (ev.clientX - startX),
      origT + (ev.clientY - startY)
    );
    panel.style.right = "auto";
    panel.style.left = `${clamped.left}px`;
    panel.style.top = `${clamped.top}px`;
  });
  const endDrag = (ev) => {
    if (!dragging) return;
    dragging = false;
    panel.classList.remove("is-dragging");
    try {
      panel.releasePointerCapture(ev.pointerId);
    } catch {
      /* ignore */
    }
    // Prefer live rect so we save where the panel actually sits after the drag.
    const rect = panel.getBoundingClientRect();
    const clamped = clampProgressPanelPos(panel, rect.left, rect.top);
    panel.classList.add("has-custom-pos");
    panel.style.right = "auto";
    panel.style.left = `${clamped.left}px`;
    panel.style.top = `${clamped.top}px`;
    saveProgressPanelPos(clamped.left, clamped.top);
    // Clear after save so a mid-drag poll cannot re-apply the old position.
    progressPanelDragging = false;
  };
  panel.addEventListener("pointerup", endDrag);
  panel.addEventListener("pointercancel", endDrag);
}

function isChallengeBusy(challenge) {
  if (!challenge) {
    challengeCompleteShownUntil = 0;
    challengeBusyGraceUntil = 0;
    return false;
  }
  const phase = String(challenge.phase || "").toLowerCase();
  const msg = String(challenge.message || "");
  // Optimistic placeholder past grace with no poll confirm — never stick forever.
  if (challenge._optimistic) {
    if (!challengeOptimisticUntil || Date.now() >= challengeOptimisticUntil) {
      challengeCompleteShownUntil = 0;
      challengeBusyGraceUntil = 0;
      challengeOptimisticUntil = 0;
      return false;
    }
    return true;
  }
  const live = Boolean(challenge.active || challenge.queued || challenge.running);
  const looksComplete =
    phase === "complete" ||
    phase === "cancelled" ||
    /^complete:/i.test(msg) ||
    /^cancelled/i.test(msg);

  // Sticky complete/cancel from the mod (or Complete: message) — brief flash then hide.
  if (looksComplete && !(challenge.queued || challenge.running)) {
    // Mod may keep active=true only during sticky; treat as finishing UI.
    if (!challenge.queued && !challenge.running && (phase === "complete" || phase === "cancelled" || /^complete:/i.test(msg))) {
      if (!challengeCompleteShownUntil) challengeCompleteShownUntil = Date.now() + 2800;
      challengeBusyGraceUntil = 0;
      challengeOptimisticUntil = 0;
      return Date.now() < challengeCompleteShownUntil;
    }
  }
  if (!live && looksComplete) {
    if (!challengeCompleteShownUntil) challengeCompleteShownUntil = Date.now() + 2800;
    challengeBusyGraceUntil = 0;
    challengeOptimisticUntil = 0;
    return Date.now() < challengeCompleteShownUntil;
  }
  if (!live) {
    challengeCompleteShownUntil = 0;
    challengeBusyGraceUntil = 0;
    challengeOptimisticUntil = 0;
    return false;
  }
  challengeCompleteShownUntil = 0;
  challengeBusyGraceUntil = Date.now() + 3500;
  challengeOptimisticUntil = 0;
  return true;
}

function isUvhmBusy(uvhm) {
  const phase = String(uvhm?.phase || "").toLowerCase();
  if (phase === "error" || phase === "cancelled") {
    if (!uvhmErrorShownUntil) uvhmErrorShownUntil = Date.now() + 4500;
    uvhmBusyGraceUntil = 0;
    return Date.now() < uvhmErrorShownUntil;
  }
  // Sticky complete — keep bar + green ✓ visible briefly (with or without active flag).
  if (phase === "complete" && uvhm && !uvhm.queued && !uvhm.running) {
    if (!uvhmErrorShownUntil) uvhmErrorShownUntil = Date.now() + 2800;
    uvhmBusyGraceUntil = 0;
    return Date.now() < uvhmErrorShownUntil;
  }
  // Idle — hide.
  if (!uvhm || phase === "idle") {
    uvhmErrorShownUntil = 0;
    uvhmBusyGraceUntil = 0;
    return false;
  }
  uvhmErrorShownUntil = 0;
  const live = Boolean(
    uvhm &&
      (uvhm.active || uvhm.queued || uvhm.running) &&
      phase !== "complete" &&
      phase !== "idle"
  );
  if (live) {
    uvhmBusyGraceUntil = Date.now() + 3500;
    return true;
  }
  // Brief gaps between ranks / ticks used to hide the bar for a flash.
  if (Date.now() < uvhmBusyGraceUntil) {
    if (phase === "complete" || phase === "idle" || !phase) {
      uvhmBusyGraceUntil = 0;
      return false;
    }
    return true;
  }
  return false;
}

function isSpawnAllBusy(spawnAll) {
  // Trust live active/queued only — index<total after cancel/idle left the bar stuck forever.
  return Boolean(spawnAll && (spawnAll.active || spawnAll.queued));
}
function isVacuumBusy(vacuum) {
  return Boolean(vacuum && (vacuum.active || Number(vacuum.queued || 0) > 0));
}
function isSerialDeliveryBusy(prog) {
  if (!prog) return false;
  if (prog.finishing) {
    const until = Number(prog.finishing_until || 0);
    if (until > 0 && Date.now() >= until) return false;
    return true;
  }
  return Boolean(prog.active || prog.queued);
}

function isAutoLobbyArmed(st) {
  return Boolean(st && (st.enabled || st.active));
}

function isAutoLobbyBusy(st) {
  // Only "working" phases should slam the bridge. Waiting between cycles uses status polls.
  if (!isAutoLobbyArmed(st)) return false;
  const phase = String(st.phase || "").toLowerCase();
  if (phase === "running" || phase === "queued" || phase === "kicking") return true;
  if (st.current_job) return true;
  if (Array.isArray(st.queued) && st.queued.length) return true;
  if (Array.isArray(st.queued_labels) && st.queued_labels.length) return true;
  return false;
}

let shapeHoldUiUntil = 0;

function isShapeBusy(st) {
  if (!st) return false;
  const phase = String(st.phase || "").toLowerCase();
  if (!phase || phase === "idle") {
    shapeHoldUiUntil = 0;
    return false;
  }
  // Actively placing / publishing — always show.
  if (st.active || phase === "dumping" || phase === "publishing" || phase === "active") {
    shapeHoldUiUntil = 0;
    return true;
  }
  // ready/held are sustained states — show briefly, then hide so the bar cannot stick.
  if (phase === "ready" || phase === "held") {
    if (!shapeHoldUiUntil) shapeHoldUiUntil = Date.now() + 5000;
    return Date.now() < shapeHoldUiUntil;
  }
  return false;
}

function challengeMilestoneStep(total) {
  const totalI = Math.max(0, Number(total) || 0);
  if (totalI <= 0) return 1;
  if (totalI <= 40) return 1;
  return Math.max(50, Math.ceil(totalI / 10));
}

function snapChallengeMilestone(rawIndex, total) {
  const totalI = Math.max(0, Number(total) || 0);
  const raw = Math.max(0, Number(rawIndex) || 0);
  if (totalI <= 0) return 0;
  if (raw >= totalI) return totalI;
  const step = challengeMilestoneStep(totalI);
  return Math.min(totalI, Math.floor(raw / step) * step);
}

/** Milestone bar for large bulks — fallback estimate only until live status advances. */
function challengeDisplayIndex(challengeState) {
  const total = Math.max(
    0,
    Number(challengeState?.total || challengeState?.progress_total || challengeProgressTotalHint || 0)
  );
  const serverRaw = Math.max(
    0,
    Number(challengeState?.progress_index ?? challengeState?.index ?? 0),
    Number(challengeState?.raw_index || 0),
    Number(challengeState?.ok || 0) +
      Number(challengeState?.failed || 0) +
      Number(challengeState?.skipped || 0)
  );
  const phase = String(challengeState?.phase || "").toLowerCase();
  if (phase === "complete") {
    challengeDisplayMilestone = total;
    return total;
  }
  const serverSnap = snapChallengeMilestone(serverRaw, total);
  let estSnap = 0;
  if (
    challengeProgressStartedAt > 0 &&
    total > 0 &&
    (challengeState?.running || challengeState?.active || challengeState?._optimistic)
  ) {
    // ULM-safe solo pacing is 1/tick (~50ms) plus game overhead: roughly 65–75s
    // for 1209. Once the bridge reports progress, trust it instead of estimating.
    const elapsedMs = Date.now() - challengeProgressStartedAt;
    const estRaw =
      serverRaw > 0 ? serverRaw : Math.min(total * 0.08, (elapsedMs / 1000) * (total / 75));
    estSnap = snapChallengeMilestone(estRaw, total);
    if (serverRaw > 0 && estSnap <= 0) estSnap = challengeMilestoneStep(total);
  }
  const next = Math.max(challengeDisplayMilestone, serverSnap, estSnap);
  challengeDisplayMilestone = next;
  return next;
}

function normalizeChallengeStatus(raw) {
  if (!raw || typeof raw !== "object") return null;
  const total = Math.max(0, Number(raw.total || raw.progress_total || 0));
  const rawIndex = Math.max(
    0,
    Number(raw.progress_index ?? raw.index ?? 0),
    Number(raw.ok || 0) + Number(raw.failed || 0) + Number(raw.skipped || 0)
  );
  const index = total > 0 ? Math.min(rawIndex, total) : rawIndex;
  const msg = String(raw.message || "");
  const live = Boolean(raw.active || raw.queued || raw.running);
  return {
    ...raw,
    active: live,
    queued: Boolean(raw.queued),
    running: Boolean(raw.running || (raw.active && !raw.queued)),
    phase: String(raw.phase || (raw.queued ? "queued" : raw.active ? "running" : "idle")),
    total,
    progress_total: total,
    index,
    progress_index: index,
    ok: Number(raw.ok || 0),
    failed: Number(raw.failed || 0),
    skipped: Number(raw.skipped || 0),
    token: String(raw.token || ""),
    message: msg,
    _optimistic: Boolean(raw._optimistic),
  };
}

function challengeProgressDetail(message) {
  const text = String(message || "").trim();
  if (!text) return "";
  const withoutAdvisory = text
    .replace(/Leave Open pending rewards[\s\S]*/i, "")
    .replace(/Bank \/ mule first[\s\S]*/i, "")
    .trim();
  const line = (withoutAdvisory || text).split(/\n/)[0].trim();
  return line.length > 140 ? `${line.slice(0, 137)}…` : line;
}

function normalizeShapeStatus(raw) {
  if (!raw || typeof raw !== "object") return null;
  const prog = raw.shape_progress && typeof raw.shape_progress === "object" ? raw.shape_progress : raw;
  return {
    active: Boolean(prog.active),
    phase: String(prog.phase || ""),
    shape: String(prog.shape || ""),
    pins: Number(prog.pins || 0),
    synced: Number(prog.synced || 0),
    hold: Boolean(prog.hold),
    coop: Boolean(prog.coop),
    message: String(prog.message || raw.message || ""),
    detail: String(prog.detail || ""),
    hint: String(prog.hint || ""),
    progress_index: Number(prog.progress_index || 0),
    progress_total: Number(prog.progress_total || 0),
  };
}


function normalizeAutoLobbyStatus(raw) {
  if (!raw || typeof raw !== "object") return null;
  const cfg = raw.config && typeof raw.config === "object" ? raw.config : null;
  const enabledFlag =
    raw.enabled != null ? Boolean(raw.enabled) : cfg && cfg.enabled != null ? Boolean(cfg.enabled) : Boolean(raw.active);
  return {
    enabled: enabledFlag,
    active: enabledFlag,
    queued: Array.isArray(raw.queued) ? raw.queued : [],
    queued_labels: Array.isArray(raw.queued_labels) ? raw.queued_labels : [],
    current_job: String(raw.current_job || ""),
    current_label: String(raw.current_label || ""),
    next_cycle_in: Number(raw.next_cycle_in || 0),
    drip_phase: String(raw.drip_phase || ""),
    drip_drop_in: Number(raw.drip_drop_in || 0),
    drip_count: Number(raw.drip_count || 0),
    drip_drop_round: Number(raw.drip_drop_round || 0),
    interval_sec: Number(raw.interval_sec || (cfg && cfg.interval_sec) || 0),
    cycle_total: Number(raw.cycle_total || raw.progress_total || 0),
    cycle_done: Number(raw.cycle_done || raw.progress_index || 0),
    phase: String(raw.phase || ""),
    message: String(raw.message || raw.last || ""),
    detail: String(raw.detail || ""),
    last: String(raw.last || raw.message || ""),
  };
}




function renderProgressPanel(challenge, uvhm, spawnAll, serial = undefined) {
  const panel = document.getElementById("sqbt-progress-panel");
  if (!panel) return;

  // null means keep cached value (manual status for one job must not wipe the other).
  // undefined for serial also keeps cache; explicit null clears serial job.
  if (challenge !== null) lastChallengeStatus = challenge;
  if (uvhm !== null) lastUvhmStatus = uvhm;
  if (spawnAll !== null) lastSpawnAllStatus = spawnAll;
  if (serial !== undefined) lastSerialDeliveryStatus = serial;

  const challengeState = lastChallengeStatus;
  const uvhmState = lastUvhmStatus;
  const spawnState = lastSpawnAllStatus;
  const serialState = lastSerialDeliveryStatus;
  const autoLobbyState = lastAutoLobbyStatus;
  const vacuumState = lastVacuumStatus;

  const clampPct = (value, total) => {
    const safeTotal = Math.max(1, Number(total || 0));
    const safeValue = Math.max(0, Number(value || 0));
    return Math.min(100, Math.max(0, Math.round((safeValue / safeTotal) * 100)));
  };

  const challengeBusy = isChallengeBusy(challengeState);
  const uvhmBusy = isUvhmBusy(uvhmState);
  const spawnBusy = isSpawnAllBusy(spawnState);
  const serialBusy = isSerialDeliveryBusy(serialState);
  const autoLobbyArmed = isAutoLobbyArmed(autoLobbyState);
  const autoLobbyBusy = isAutoLobbyBusy(autoLobbyState);
  const shapeState = lastShapeStatus;
  const shapeBusy = isShapeBusy(shapeState);
  const vacuumBusy = isVacuumBusy(vacuumState);
  // Floating bar: live jobs only. Auto Lobby "armed / waiting" still paints when armed,
  // but idle armed must not keep the panel stuck after other jobs finish without status.
  const busy =
    challengeBusy ||
    uvhmBusy ||
    spawnBusy ||
    serialBusy ||
    autoLobbyBusy ||
    autoLobbyArmed ||
    shapeBusy ||
    vacuumBusy;

  let html = "";
  if (shapeBusy) {
    const total = Math.max(1, Number(shapeState.progress_total || shapeState.pins || 1));
    const index = Math.max(0, Number(shapeState.progress_index || shapeState.synced || 0));
    const phase = String(shapeState.phase || "");
    const pct =
      phase === "ready" || phase === "held"
        ? 100
        : phase === "dumping"
          ? Math.max(12, clampPct(index, total))
          : clampPct(index, total);
    const title =
      phase === "publishing"
        ? "Co-op shape publish"
        : phase === "ready"
          ? "Co-op shape ready"
          : phase === "dumping"
            ? "Placing shape"
            : "Loot shape";
    const countLine = shapeState.detail || `${shapeState.shape || "shape"} · ${index}/${total}`;
    const hint = shapeState.hint || shapeState.message || "";
    html += `<div data-progress-job="shape"><h4>${title}</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${countLine}</p>
      <p class="progress-meta muted">${hint}</p></div>`;
  }
  if (autoLobbyArmed && !challengeBusy && !uvhmBusy) {
    const total = Math.max(0, Number(autoLobbyState.cycle_total || 0));
    const done = Math.max(0, Number(autoLobbyState.cycle_done || 0));
    const phase = String(autoLobbyState.phase || "").toLowerCase();
    const current =
      autoLobbyState.current_label ||
      (autoLobbyState.queued_labels && autoLobbyState.queued_labels[0]) ||
      "";
    const waiting = phase === "waiting" || (!current && Number(autoLobbyState.next_cycle_in || 0) > 0);
    const interval = Math.max(1, Number(autoLobbyState.interval_sec || 90));
    let pct = 10;
    if (total > 0) pct = clampPct(done, total);
    else if (waiting)
      pct = Math.max(
        6,
        Math.min(94, Math.round(100 - (Number(autoLobbyState.next_cycle_in) / interval) * 100))
      );
    const queueBit =
      autoLobbyState.queued_labels && autoLobbyState.queued_labels.length
        ? ` · next: ${autoLobbyState.queued_labels.slice(0, 2).join(", ")}`
        : "";
    const countLine = current
      ? `Now: ${current}${queueBit}`
      : waiting
        ? `Next cycle in ${Math.max(0, Math.round(Number(autoLobbyState.next_cycle_in) || 0))}s`
        : autoLobbyState.detail || "Armed";
    const detail = challengeProgressDetail(
      autoLobbyState.detail || autoLobbyState.message || autoLobbyState.last || ""
    );
    const dripCountdown =
      autoLobbyState.drip_phase === "wait_mail" && autoLobbyState.drip_drop_in > 0
        ? `BACKPACK SPILL STARTS IN ${Math.ceil(autoLobbyState.drip_drop_in)}s — stand clear`
        : "";
    html += `<div data-progress-job="auto-lobby"><h4>Auto Lobby</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${countLine}</p>
      ${dripCountdown ? `<p class="progress-danger-countdown">${dripCountdown}</p>` : ""}
      ${detail ? `<p class="progress-meta muted">${detail}</p>` : ""}
      <button type="button" class="progress-stop-btn" data-auto-lobby-stop="1">Stop Auto Lobby</button></div>`;
  } else if (autoLobbyArmed && (challengeBusy || uvhmBusy)) {
    const watch =
      autoLobbyState.current_label ||
      (challengeBusy ? "Challenges" : "UVHM") ||
      "progression";
    html += `<div data-progress-job="auto-lobby-watch"><p class="progress-meta muted">Auto Lobby · waiting on ${watch}</p>
      <button type="button" class="progress-stop-btn" data-auto-lobby-stop="1">Stop Auto Lobby</button></div>`;
  }
  if (challengeBusy) {
    const rawTotal = Number(
      challengeState.total || challengeState.progress_total || challengeProgressTotalHint || 0
    );
    const index = challengeDisplayIndex(challengeState);
    const waitingTick =
      (rawTotal <= 0 && Boolean(challengeState.queued || challengeState._optimistic)) ||
      (Boolean(challengeState._optimistic) && index <= 0 && Boolean(challengeState.queued));
    const total = rawTotal > 0 ? rawTotal : 1;
    const pct = waitingTick ? 8 : clampPct(Math.min(index, total), total);
    const detail =
      challengeProgressDetail(challengeState.message) ||
      (waitingTick ? "Queued — waiting for world tick…" : `Working · ${index}/${total}`);
    const tokenRaw = String(challengeState.token || "");
    const token =
      tokenRaw.length > 28 ? ` · ${tokenRaw.slice(0, 25)}…` : tokenRaw ? ` · ${tokenRaw}` : "";
    const skipBit =
      Number(challengeState.skipped || 0) > 0 ? ` · skip ${challengeState.skipped}` : "";
    const countLine = waitingTick
      ? rawTotal > 0
        ? `Starting ${rawTotal}…`
        : "Starting…"
      : `${Math.min(index, total)}/${total} · OK ${challengeState.ok || 0} · fail ${challengeState.failed || 0}${skipBit}${token}`;
    html += `<div data-progress-job="challenge"><h4>Challenge bulk${
      String(challengeState.phase || "").toLowerCase() === "complete" ||
      /^complete:/i.test(String(challengeState.message || ""))
        ? ' <span class="progress-done-tick" title="Finished">✓</span>'
        : ""
    }</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${countLine}</p>
      <p class="progress-meta muted">${detail}</p>
      <button type="button" class="progress-stop-btn" data-challenge-stop="1">Stop challenges</button></div>`;
  }
  if (uvhmBusy) {
    const total = Math.max(1, Number(uvhmState.progress_total || uvhmState.total || uvhmState.steps_total || 7));
    const index = Math.max(0, Number(uvhmState.progress_index || uvhmState.index || uvhmState.step || 0));
    // Round to whole ranks for the bar so settle creep does not thrash the sticky panel.
    const pct = clampPct(index, total);
    let detail = String(uvhmState.message || `Step ${index}/${total}`);
    detail = detail.replace(/Allowing .+ to settle \(\d+\/\d+\)\.?/i, "Waiting for challenge settle…");
    if (detail.length > 120) detail = `${detail.slice(0, 117)}…`;
    const target = uvhmState.target_name ? `${uvhmState.target_name} · ` : "";
    const rankBit =
      uvhmState.rank != null && uvhmState.rank !== ""
        ? `rank ${uvhmState.rank}${uvhmState.max_rank ? `/${uvhmState.max_rank}` : ""} · `
        : "";
    const uvhmDone = String(uvhmState.phase || "").toLowerCase() === "complete";
    html += `<div data-progress-job="uvhm"><h4>UVHM progression${
      uvhmDone ? ' <span class="progress-done-tick" title="Finished">✓</span>' : ""
    }</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${target}${rankBit}${detail}</p></div>`;
  }
  if (spawnBusy) {
    const total = Math.max(1, Number(spawnState.total || 0));
    const index = Math.max(0, Number(spawnState.index || 0));
    const pct = clampPct(index, total);
    const detail = spawnState.message || `Queued · ${index}/${total}`;
    html += `<h4>Spawn all filtered</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${index}/${total} · OK ${spawnState.ok || 0} · fail ${spawnState.failed || 0}</p>
      <p class="progress-meta muted">${detail}</p>`;
  }
  if (vacuumBusy) {
    const total = Math.max(1, Number(vacuumState.total || vacuumState.progress_total || 1));
    const index = Math.max(0, Number(vacuumState.progress_index ?? vacuumState.index ?? 0));
    const pct = clampPct(index, total);
    const detail = vacuumState.message || `Vacuum · ${index}/${total}`;
    html += `<div data-progress-job="vacuum"><h4>Loot vacuum</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${index}/${total} · bag ${vacuumState.ok || 0} · piles ${vacuumState.piled || 0} · fail ${vacuumState.failed || 0}</p>
      <p class="progress-meta muted">${detail}</p>
      <button type="button" class="progress-stop-btn" data-vacuum-stop="1">Stop vacuum</button></div>`;
  }
  if (serialBusy) {
    const total = Math.max(1, Number(serialState.total || 1));
    const index = Math.max(0, Number(serialState.index || 0));
    const pctRaw = Number(serialState.percent);
    const pct = Number.isFinite(pctRaw)
      ? Math.min(100, Math.max(0, Math.round(pctRaw)))
      : clampPct(index, total);
    const stage = String(serialState.stage || serialState.phase || "");
    const title =
      stage === "reward_open" || /open/i.test(stage)
        ? "Opening rewards"
        : "Serial delivery";
    const detail = serialState.message || `Package ${index}/${total}`;
    const scope = serialState.scope ? ` · ${serialState.scope}` : "";
    html += `<div data-progress-job="serial"><h4>${title}</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${serialState.label || `${index}/${total}`}${scope}</p>
      <p class="progress-meta muted">${detail}</p></div>`;
  }

  let nextHtml = html;
  if (busy && nextHtml) {
    nextHtml =
      `<div class="progress-drag-handle" data-progress-drag="1" title="Drag to move">Move</div>` +
      nextHtml;
  }
  panel.classList.toggle("is-floating", busy);
  if (busy) {
    panel.classList.remove("hidden");
  } else {
    // Hide as soon as jobs finish — no idle placeholder stuck on Progression.
    panel.classList.add("hidden");
    nextHtml = "";
  }

  ensureProgressPanelDrag(panel);

  // Prefer in-place UVHM bar/text updates to avoid sticky-panel flicker.
  // Skip when Auto Lobby / other jobs share the panel so siblings stay fresh.
  const existingUvhm = panel.querySelector('[data-progress-job="uvhm"]');
  const nextHasUvhm = nextHtml.includes('data-progress-job="uvhm"');
  const existingChallenge = panel.querySelector('[data-progress-job="challenge"]');
  const nextHasChallenge = nextHtml.includes('data-progress-job="challenge"');
  const soloChallenge =
    busy &&
    existingChallenge &&
    nextHasChallenge &&
    !uvhmBusy &&
    !spawnBusy &&
    !autoLobbyArmed &&
    !shapeBusy &&
    !vacuumBusy &&
    !serialBusy;
  if (soloChallenge) {
    const tmp = document.createElement("div");
    tmp.innerHTML = nextHtml;
    const fresh = tmp.querySelector('[data-progress-job="challenge"]');
    if (fresh) {
      const h4 = existingChallenge.querySelector("h4");
      const freshH4 = fresh.querySelector("h4");
      const span = existingChallenge.querySelector(".progress-bar > span");
      const metas = existingChallenge.querySelectorAll(".progress-meta");
      const freshSpan = fresh.querySelector(".progress-bar > span");
      const freshMetas = fresh.querySelectorAll(".progress-meta");
      if (h4 && freshH4) h4.innerHTML = freshH4.innerHTML;
      if (span && freshSpan) span.style.width = freshSpan.style.width;
      freshMetas.forEach((node, i) => {
        if (metas[i]) metas[i].textContent = node.textContent;
      });
      lastProgressHtml = nextHtml;
      applyProgressPanelPosition(panel);
      return;
    }
  }
  const soloUvhm =
    busy &&
    existingUvhm &&
    nextHasUvhm &&
    !challengeBusy &&
    !spawnBusy &&
    !autoLobbyArmed &&
    !shapeBusy &&
    !vacuumBusy &&
    !serialBusy;
  if (soloUvhm) {
    const tmp = document.createElement("div");
    tmp.innerHTML = nextHtml;
    const fresh = tmp.querySelector('[data-progress-job="uvhm"]');
    if (fresh) {
      const h4 = existingUvhm.querySelector("h4");
      const freshH4 = fresh.querySelector("h4");
      const span = existingUvhm.querySelector(".progress-bar > span");
      const meta = existingUvhm.querySelector(".progress-meta");
      const freshSpan = fresh.querySelector(".progress-bar > span");
      const freshMeta = fresh.querySelector(".progress-meta");
      if (h4 && freshH4) h4.innerHTML = freshH4.innerHTML;
      if (span && freshSpan) span.style.width = freshSpan.style.width;
      if (meta && freshMeta) meta.textContent = freshMeta.textContent;
      lastProgressHtml = nextHtml;
      applyProgressPanelPosition(panel);
      return;
    }
  }
  if (nextHtml === lastProgressHtml) {
    applyProgressPanelPosition(panel);
    return;
  }
  // Never wipe the panel DOM mid-drag — that jumps the bar off the pointer.
  if (progressPanelDragging) {
    lastProgressHtml = nextHtml;
    return;
  }
  lastProgressHtml = nextHtml;
  panel.innerHTML = nextHtml;
  applyProgressPanelPosition(panel);
}

async function pollProgressOnce() {
  if (!actionsEnabled()) return;
  if (progressPollInFlight) return;
  progressPollInFlight = true;
  try {
    const challengeBusy = isChallengeBusy(lastChallengeStatus);
    const uvhmBusy = isUvhmBusy(lastUvhmStatus);
    const shapeBusy = isShapeBusy(lastShapeStatus);
    const spawnBusy = isSpawnAllBusy(lastSpawnAllStatus);
    const serialBusy = isSerialDeliveryBusy(lastSerialDeliveryStatus);
    const autoBusy = isAutoLobbyBusy(lastAutoLobbyStatus);
    const vacuumBusy = isVacuumBusy(lastVacuumStatus);
    const heavyProgress = challengeBusy || uvhmBusy;

    // During UVHM / challenges, skip unrelated status actions so the bridge
    // is not slammed with 6 parallel posts every half-second (disconnect risk).
    const jobs = [
      window.sqbt.postAction("challenge_bulk_status", {}),
      // While challenges own the game thread, skip UVHM status so polls stay light.
      challengeBusy && !uvhmBusy
        ? Promise.resolve({ data: lastUvhmStatus ? { uvhm: lastUvhmStatus } : null })
        : window.sqbt.postAction("uvhm_status", {}),
      heavyProgress
        ? Promise.resolve({ data: null })
        : window.sqbt.postAction("spawn_item_pool_status", {}),
      heavyProgress || serialBusy
        ? Promise.resolve({ data: lastSerialDeliveryStatus ? { status: lastSerialDeliveryStatus } : null })
        : window.sqbt.postAction("serial_delivery_status", {}, 8),
      // Only poll Auto Lobby while a cycle step is actually running — waiting
      // between cycles uses the normal 5s status payload (was flooding disconnects).
      autoBusy && !heavyProgress
        ? window.sqbt.postAction("auto_lobby_get", {})
        : Promise.resolve({ data: null }),
      shapeBusy
        ? window.sqbt.postAction("loot_shape_status", {})
        : Promise.resolve({ data: null }),
      vacuumBusy && !heavyProgress
        ? window.sqbt.postAction("loot_vacuum_status", {})
        : Promise.resolve({ data: null }),
    ];
    const [challengeRes, uvhmRes, spawnRes, serialRes, autoLobbyRes, shapeRes, vacuumRes] = await Promise.all(jobs);
    const challengeRaw = challengeRes.data?.challenge;
    // Prefer nested challenge object; fall back to top-level fields. Never wipe a
    // live "Starting…" cache with null when a poll returns a thin/error payload.
    const challenge = normalizeChallengeStatus(
      challengeRaw && typeof challengeRaw === "object"
        ? challengeRaw
        : challengeRes.data?.active != null ||
            challengeRes.data?.queued != null ||
            challengeRes.data?.running != null ||
            challengeRes.data?.progress_index != null ||
            challengeRes.data?.index != null
          ? {
              active: Boolean(challengeRes.data.active),
              queued: Boolean(challengeRes.data.queued),
              running: Boolean(challengeRes.data.running),
              phase: challengeRes.data.phase || "",
              index: challengeRes.data.progress_index ?? challengeRes.data.index ?? 0,
              progress_index: challengeRes.data.progress_index ?? challengeRes.data.index ?? 0,
              total: challengeRes.data.progress_total ?? challengeRes.data.total ?? 0,
              progress_total: challengeRes.data.progress_total ?? challengeRes.data.total ?? 0,
              ok: challengeRes.data.accepted ?? challengeRes.data.ok ?? 0,
              failed: challengeRes.data.failed || 0,
              skipped: challengeRes.data.skipped || 0,
              token: challengeRes.data.token || "",
              message: challengeRes.data.message || "",
            }
          : null
    );
    const uvhm = uvhmRes.data?.uvhm ?? null;
    const spawnAll = spawnRes.data?.spawn_all ?? null;
    const serial =
      serialRes.data?.status || serialRes.data?.progress || null;
    if (challenge) {
      // Confirmed live status replaces optimistic start snapshot.
      lastChallengeStatus = challenge;
      if (!challenge._optimistic) challengeOptimisticUntil = 0;
    }
    if (uvhm) lastUvhmStatus = uvhm;
    if (spawnAll) lastSpawnAllStatus = spawnAll;
    if (challengeRes.data?.suppress_open_all) {
      suppressOpenAllAfterChallenge = true;
    }
    if (serial && typeof serial === "object") {
      lastSerialDeliveryStatus = serial;
    } else if (!isSerialDeliveryBusy(lastSerialDeliveryStatus)) {
      lastSerialDeliveryStatus = null;
    }
    // Drop idle caches so a finished job cannot keep the floating bar up.
    if (lastChallengeStatus && !isChallengeBusy(lastChallengeStatus)) {
      lastChallengeStatus = null;
      challengeOptimisticUntil = 0;
      challengeProgressStartedAt = 0;
      challengeProgressTotalHint = 0;
      challengeDisplayMilestone = 0;
    }
    if (lastSpawnAllStatus && !isSpawnAllBusy(lastSpawnAllStatus)) {
      lastSpawnAllStatus = null;
    }
    if (lastUvhmStatus && !isUvhmBusy(lastUvhmStatus)) {
      const phase = String(lastUvhmStatus.phase || "").toLowerCase();
      if (phase === "idle" || phase === "" || phase === "complete" || phase === "error" || phase === "cancelled") {
        lastUvhmStatus = null;
      }
    }
    if (lastSerialDeliveryStatus && !isSerialDeliveryBusy(lastSerialDeliveryStatus)) {
      lastSerialDeliveryStatus = null;
    }
    if (lastShapeStatus && !isShapeBusy(lastShapeStatus)) {
      lastShapeStatus = null;
    }
    const autoLobbyRaw =
      autoLobbyRes.data?.auto_lobby ||
      (autoLobbyRes.data?.enabled != null || autoLobbyRes.data?.config
        ? autoLobbyRes.data
        : null);
    const autoLobby = normalizeAutoLobbyStatus(autoLobbyRaw);
    if (autoLobby) lastAutoLobbyStatus = autoLobby;
    if (shapeRes.data) {
      const shape = normalizeShapeStatus(shapeRes.data);
      if (shape) lastShapeStatus = shape;
    }
    if (vacuumRes.data?.vacuum && typeof vacuumRes.data.vacuum === "object") {
      lastVacuumStatus = vacuumRes.data.vacuum;
    }
    if (lastVacuumStatus && !isVacuumBusy(lastVacuumStatus)) {
      lastVacuumStatus = null;
    }
    renderProgressPanel(null, null, null);
    const busy =
      isChallengeBusy(lastChallengeStatus) ||
      isUvhmBusy(lastUvhmStatus) ||
      isSpawnAllBusy(lastSpawnAllStatus) ||
      isSerialDeliveryBusy(lastSerialDeliveryStatus) ||
      isAutoLobbyBusy(lastAutoLobbyStatus) ||
      isShapeBusy(lastShapeStatus) ||
      isVacuumBusy(lastVacuumStatus);
    if (busy) {
      // Challenges finish in seconds — poll fast or the bar stays on 0/N queued.
      const pollMs = challengeBusy ? 350 : uvhmBusy ? 500 : heavyProgress ? 800 : 1000;
      ensureChallengePaintTimer(challengeBusy);
      if (!progressPollTimer || progressPollMs !== pollMs) {
        if (progressPollTimer) {
          clearInterval(progressPollTimer);
          progressPollTimer = null;
        }
        progressPollMs = pollMs;
        progressPollTimer = setInterval(() => {
          pollProgressOnce();
        }, pollMs);
      }
    } else {
      stopProgressPoll();
      // Keep the Auto Lobby waiting panel alive via status (armed but idle).
      if (isAutoLobbyArmed(lastAutoLobbyStatus)) {
        renderProgressPanel(null, null, null);
      }
    }
  } catch {
    /* bridge may be busy */
  } finally {
    progressPollInFlight = false;
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
    opt.textContent = actionsEnabled() ? t("target.none") : t("target.connect");
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
      allOpt.textContent = t("target.all");
      globalTargetSelect.appendChild(allOpt);
      for (const row of players) {
        if (isPlaceholderPlayerRow(row)) continue;
        const opt = document.createElement("option");
        opt.value = String(row.index);
        opt.textContent = playerOptionLabel(row);
        globalTargetSelect.appendChild(opt);
      }
    }
  }
  const next =
    pendingTargetIndex != null && Date.now() < pendingTargetUntil
      ? String(pendingTargetIndex)
      : stickyTargetInRoster(players)
        ? String(stickyTargetIndex)
        : targetIndex != null &&
            (Number(targetIndex) === -1 || players.some((row) => Number(row.index) === Number(targetIndex)))
          ? String(targetIndex)
          : previous;
  if (next !== "" && [...globalTargetSelect.options].some((opt) => opt.value === next)) {
    if (document.activeElement === globalTargetSelect) {
      // Don't yank an open Boost target dropdown.
    } else if (globalTargetSelect.value !== next) {
      globalTargetSelect.value = next;
    }
  }
}

function refreshPlayerSelects() {
  refreshGlobalTargetSelect();
  const players = latestStatus?.raw?.players || [];
  const playersSig = JSON.stringify(players);
  const globalIdx =
    globalTargetSelect && !globalTargetSelect.disabled && globalTargetSelect.value !== ""
      ? String(globalTargetSelect.value)
      : "";
  const needRebuild = playersSig !== lastTabPlayerSelectsSignature;
  if (needRebuild) lastTabPlayerSelectsSignature = playersSig;
  for (const select of tabContent.querySelectorAll("select[data-role='player-select']")) {
    if (select === globalTargetSelect) continue;
    const fieldWrap = select.closest("[data-field-key]");
    const fieldKeyName = fieldWrap?.dataset.fieldKey || "";
    const deliverKey = select.dataset.deliverPlayerKey || "";
    const includeAll = select.dataset.includeAll === "1" || Boolean(deliverKey);
    let current = deliverKey
      ? fieldValues[deliverKey]
      : fieldValues[fieldKeyName] || select.value || "";
    // Only follow the global Boost target when the per-action field was never set.
    if (globalIdx !== "" && (current === undefined || current === "")) {
      current = globalIdx;
    }
    if (current === undefined || current === "") {
      current = String(preferredDeliveryPlayerIndex(players));
    }
    if (needRebuild || select.options.length === 0) {
      if (document.activeElement === select) {
        // Keep open dropdown intact; only sync value below if still valid.
      } else {
        select.innerHTML = "";
        if (includeAll) {
          const allOpt = document.createElement("option");
          allOpt.value = "-1";
          allOpt.textContent = t("target.all");
          select.appendChild(allOpt);
        } else if (current === "-1") {
          // Dropdown has no All option — fall back to preferred concrete player.
          current = String(preferredDeliveryPlayerIndex(players.filter((p) => Number(p.index) !== -1)));
        }
        for (const row of players) {
          if (isPlaceholderPlayerRow(row)) continue;
          const opt = document.createElement("option");
          opt.value = String(row.index);
          opt.textContent = playerOptionLabel(row);
          select.appendChild(opt);
        }
        if (!players.length) {
          const opt = document.createElement("option");
          opt.value = "0";
          opt.textContent = actionsEnabled() ? t("target.host") : t("target.connect");
          select.appendChild(opt);
          current = "0";
        }
      }
    } else if (!includeAll && current === "-1") {
      current = String(preferredDeliveryPlayerIndex(players.filter((p) => Number(p.index) !== -1)));
    }
    if (![...select.options].some((opt) => opt.value === String(current))) {
      current = String(preferredDeliveryPlayerIndex(players));
    }
    if (document.activeElement === select) {
      // Don't yank value while user is choosing.
    } else if (select.value !== String(current)) {
      select.value = String(current);
    }
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

function bindExternalLinks(root) {
  if (!root) return;
  for (const link of root.querySelectorAll("a[href]")) {
    if (link.dataset.externalBound) continue;
    link.dataset.externalBound = "1";
    link.addEventListener("click", (event) => {
      event.preventDefault();
      if (link.classList.contains("js-open-setup")) {
        showSetupCard();
        return;
      }
      const href = link.getAttribute("href");
      if (href) window.sqbt.openExternal(href);
    });
  }
}

async function prefillAutoLobbyFields() {
  const gen = ++autoLobbyPrefillGen;
  try {
    const { data } = await window.sqbt.postAction("auto_lobby_get", {});
    if (gen !== autoLobbyPrefillGen) return;
    const cfg = data?.config || data?.auto_lobby?.config || {};
    if (!cfg || typeof cfg !== "object") return;
    const focused = document.activeElement;
    const editing =
      focused &&
      tabContent?.contains(focused) &&
      (focused.matches("input, textarea, select") || focused.isContentEditable);
    const sectionId = "auto_lobby:Auto Lobby";
    for (const [key, value] of Object.entries(cfg)) {
      const fk = `${sectionId}:__section__:${key}`;
      if (autoLobbyTouchedKeys.has(fk)) continue;
      if (typeof value === "boolean") fieldValues[fk] = value;
      else if (value != null) fieldValues[fk] = value;
    }
    if (editing) return;
    // Refresh visible inputs if the tab is open — never clobber an active edit.
    for (const wrap of document.querySelectorAll(`[data-section-id="${sectionId}"] [data-field-key]`)) {
      const key = wrap.getAttribute("data-field-key");
      if (!key || fieldValues[key] === undefined) continue;
      if (autoLobbyTouchedKeys.has(key)) continue;
      const input = wrap.querySelector("input, select, textarea");
      if (!input || document.activeElement === input) continue;
      if (input.type === "checkbox") input.checked = Boolean(fieldValues[key]);
      else input.value = String(fieldValues[key]);
    }
  } catch {
    /* bridge may be busy */
  }
}

function updateStartGuide() {
  if (!startGuide) return;
  const ready = actionsEnabled();
  // Keep Start here until buttons unlock (main menu "connected" is not enough).
  startGuide.hidden = ready;
  startGuide.setAttribute("aria-hidden", ready ? "true" : "false");
  startGuide.classList.toggle("hidden", ready);
  startGuide.classList.toggle("is-hidden", ready);
  startGuide.classList.toggle("is-ready", ready);
  startGuide.style.display = ready ? "none" : "";
  if (startGuideSteps) startGuideSteps.classList.toggle("hidden", ready);
  if (ready) return;

  const connected = Boolean(
    latestStatus?.connected ||
      ["ready", "connected", "in_menu_or_loading"].includes(String(latestStatus?.state || ""))
  );
  const hasPath = Boolean((gameRootInput?.value || "").trim() || lastModSync?.gameRoot);
  const baseOk = Boolean(lastBaseSdk?.installed);
  const needsSetup = !hasPath || !baseOk;

  if (startGuideTitle) {
    startGuideTitle.textContent = needsSetup
      ? hasPath
        ? t("guide.oneTime")
        : t("guide.setFolder")
      : connected
        ? t("guide.loadCharacter")
        : t("guide.getOnline");
  }
  const setupLink = `<a href="#setup" class="js-open-setup">${t("chrome.setup")}</a>`;
  if (startGuideSteps) {
    startGuideSteps.innerHTML = needsSetup
      ? `<li><strong>${t("guide.step1")}</strong></li>
         <li><strong>${t("guide.step2")}</strong></li>
         <li>${t("guide.step3", { setup: setupLink })}</li>
         <li><strong>${t("guide.step4")}</strong></li>`
      : connected
        ? `<li><strong>${t("guide.stepLoadChar")}</strong></li>
           <li><strong>${t("guide.stepWaitButtons")}</strong></li>
           <li>${t("guide.stepWrongDrive", { setup: setupLink })}</li>`
        : `<li><strong>${t("guide.step1")}</strong></li>
           <li><strong>${t("guide.step2")}</strong></li>
           <li>${t("guide.step3", { setup: setupLink })}</li>
           <li><strong>${t("guide.step4")}</strong></li>`;
  }
  if (startGuideSteps) bindExternalLinks(startGuideSteps);
  if (startGuideFoot) {
    startGuideFoot.innerHTML = !hasPath
      ? t("guide.footNoPath", { setup: setupLink })
      : needsSetup
        ? t("guide.footNeedSdk", { setup: setupLink })
        : connected
          ? t("guide.footEnterSave", { setup: setupLink })
          : t("guide.footInGame", { setup: setupLink });
    bindExternalLinks(startGuideFoot);
  }
}

function applyInstallLocationUi(setup = null) {
  const stored = String(setup?.storedGameRoot || "").trim();
  const resolved = String(setup?.gameRoot || gameRootInput?.value || "").trim();
  const candidates = Array.isArray(setup?.candidates) ? setup.candidates.filter(Boolean) : [];
  const pathSource = setup?.pathSource || (stored ? "stored" : resolved ? "detected" : "none");
  const hasPath = Boolean(resolved);
  if (installLocationCard) {
    installLocationCard.classList.toggle("is-set", hasPath);
    installLocationCard.classList.toggle("is-missing", !hasPath);
  }
  if (installLocationDetail) {
    installLocationDetail.innerHTML = hasPath ? t("install.detailSet") : t("install.detailMissing");
  }
  if (installLocationStatus) {
    if (!hasPath) {
      installLocationStatus.textContent =
        candidates.length > 0
          ? t("install.candidates", { list: candidates.slice(0, 3).join(" · ") })
          : t("install.noFolder");
    } else if (pathSource === "stored") {
      installLocationStatus.textContent = t("install.saved");
    } else {
      installLocationStatus.textContent = t("install.detected");
    }
  }
  if (browseGameBtn) {
    browseGameBtn.textContent = hasPath ? t("install.changeFolder") : t("install.setFolder");
    browseGameBtn.classList.add("primary");
  }
}

function setupNeedsUserAction(setup = null) {
  const hasPath = Boolean(
    String(setup?.gameRoot || gameRootInput?.value || lastModSync?.gameRoot || "").trim()
  );
  const baseOk = Boolean((setup?.baseSdk || lastBaseSdk)?.installed);
  const syncFailed =
    lastModSync && lastModSync.ok === false && lastModSync.reason !== "no-game-root";
  return !hasPath || !baseOk || Boolean(syncFailed);
}

function updateSetupVisibility(setup) {
  if (setup && Object.prototype.hasOwnProperty.call(setup, "setupDismissed")) {
    setupDismissed = Boolean(setup.setupDismissed);
  }
  const needs = setupNeedsUserAction(setup);
  // Only force Setup open when something still needs the user (path / oak2 / sync fail).
  // Auto-sync success stays collapsed — use the header Setup button if needed.
  const hide = setupPinned ? false : !needs;
  if (!needs) {
    setupPinned = false;
  }
  if (setupCard) setupCard.classList.toggle("is-hidden", hide);
  if (showSetupBtn) showSetupBtn.classList.toggle("hidden", !hide);
  updateStartGuide();
}

function showModSyncNotice(state, { kicker, title, detail } = {}) {
  if (!modSyncNotice) return;
  modSyncNotice.classList.remove("hidden", "is-restart", "is-updated", "is-ok");
  if (state) modSyncNotice.classList.add(`is-${state}`);
  if (modSyncNoticeKicker) modSyncNoticeKicker.textContent = kicker || t("sync.kicker");
  if (modSyncNoticeTitle) modSyncNoticeTitle.textContent = title || "";
  if (modSyncNoticeDetail) modSyncNoticeDetail.textContent = detail || "";
}

function hideModSyncNotice() {
  modSyncNotice?.classList.add("hidden");
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

function decodeHtmlEntities(text) {
  return String(text || "")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&apos;/gi, "'");
}

function looksLikeSerialFilePath(raw) {
  let s = String(raw || "").trim();
  if (
    (s.startsWith('"') && s.endsWith('"')) ||
    (s.startsWith("'") && s.endsWith("'"))
  ) {
    s = s.slice(1, -1).trim();
  }
  if (!s) return false;
  if (!/\.(txt|docx|csv|md|json|log|ya?ml)$/i.test(s)) return false;
  return /^[A-Za-z]:[\\/]/.test(s) || s.startsWith("\\\\") || /[\\/]/.test(s);
}

function isSinglePastedBase85(text) {
  const t = String(text || "").trim();
  if (!t.startsWith("@U")) return false;
  if (/[\r\n]/.test(t)) return false;
  const re = /(?:^|\s)@Ug/gi;
  let count = 0;
  let m;
  while ((m = re.exec(t)) !== null) {
    count += 1;
  }
  return count <= 1;
}

function joinWrappedSerialLines(raw) {
  const out = [];
  let buf = "";
  for (const line of String(raw || "").replace(/\r/g, "\n").split("\n")) {
    const piece = line.trim();
    if (!piece) {
      if (buf) {
        out.push(buf);
        buf = "";
      }
      continue;
    }
    if (!buf) {
      buf = piece;
      continue;
    }
    if (piece.startsWith("@U") || looksLikeSerialFilePath(piece)) {
      out.push(buf);
      buf = piece;
    } else if (buf.startsWith("@U")) {
      buf += piece;
    } else {
      out.push(buf);
      buf = piece;
    }
  }
  if (buf) out.push(buf);
  return out;
}

function splitBase85SerialBlob(blob) {
  const text = String(blob || "").trim();
  if (!text) return [];
  if (isSinglePastedBase85(text)) return [text];
  const starts = [];
  // STBX / save YAML: serial: '@Ug…' — allow quote / colon / equals before @Ug.
  const re = /(?:^|[\s'"`:=\(\[{,])@Ug/gi;
  let m;
  while ((m = re.exec(text)) !== null) {
    const at = text[m.index] === "@" ? m.index : m.index + (m[0].length - 3);
    starts.push(at);
  }
  if (!starts.length) {
    return text.startsWith("@U") ? [text] : [];
  }
  if (starts.length === 1) {
    return [text.slice(starts[0]).trim()];
  }
  const out = [];
  for (let i = 0; i < starts.length; i += 1) {
    let part = text.slice(starts[i], starts[i + 1] ?? text.length).trim();
    part = part.replace(/['"`]+\s*$/, "").replace(/[,}\]]+\s*$/, "").trim();
    if (part) out.push(part);
  }
  return out;
}

/** Pull serial: '@U…' / serial: "@U…" / serial: @U… from save/editor YAML. */
function extractYamlSerialFields(rawText) {
  const found = [];
  const seen = new Set();
  const push = (serial) => {
    let cleaned = String(serial || "").trim();
    if (
      (cleaned.startsWith('"') && cleaned.endsWith('"')) ||
      (cleaned.startsWith("'") && cleaned.endsWith("'"))
    ) {
      cleaned = cleaned.slice(1, -1).trim();
    }
    if (!cleaned.startsWith("@U") || cleaned.length < 12) return;
    if (seen.has(cleaned)) return;
    seen.add(cleaned);
    found.push(cleaned);
  };
  const text = String(rawText || "");
  const patterns = [
    /\bserial\s*:\s*'([^']+)'/gi,
    /\bserial\s*:\s*"([^"]+)"/gi,
    /\bserial\s*:\s*(@U\S+)/gi,
  ];
  for (const re of patterns) {
    let m;
    while ((m = re.exec(text)) !== null) {
      push(m[1]);
    }
  }
  return found;
}

function extractSerialsFromText(rawText) {
  const text = decodeHtmlEntities(String(rawText || ""));
  const found = [];
  const seen = new Set();
  const push = (serial) => {
    let cleaned = String(serial || "").trim();
    if (
      (cleaned.startsWith('"') && cleaned.endsWith('"')) ||
      (cleaned.startsWith("'") && cleaned.endsWith("'"))
    ) {
      cleaned = cleaned.slice(1, -1).trim();
    }
    if (cleaned.startsWith("`") && cleaned.endsWith("`")) {
      const inner = cleaned.slice(1, -1);
      if (!inner.includes("`")) {
        cleaned = inner.trim();
      }
    }
    cleaned = cleaned.replace(/['"`]+$/, "").trim();
    if (!cleaned) return;
    if (!(cleaned.startsWith("@U") || (cleaned.includes(",") && /\d/.test(cleaned)))) {
      return;
    }
    if (seen.has(cleaned)) return;
    seen.add(cleaned);
    found.push(cleaned);
  };

  // Save-editor / STBX YAML: inventory.items.*.serial: '@U…'
  for (const serial of extractYamlSerialFields(text)) {
    push(serial);
  }
  if (found.length) {
    return found;
  }

  // Moxsy-style .txt: one @U per line — never rejoin / mid-split.
  const nonEmpty = String(text || "")
    .replace(/\r/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const atULines = nonEmpty.filter((line) => line.startsWith("@U") || /^['"]@U/.test(line));
  if (nonEmpty.length >= 2 && atULines.length >= Math.max(2, Math.floor(0.8 * nonEmpty.length))) {
    for (const line of atULines) {
      push(line);
    }
    return found;
  }
  const pushAtUParts = (blob) => {
    for (const token of splitBase85SerialBlob(blob)) {
      push(token);
    }
  };
  for (const line of joinWrappedSerialLines(text)) {
    const trimmed = line.trim();
    if (trimmed.includes("@U")) {
      pushAtUParts(trimmed);
    } else if (/^\s*\d+\s*,\s*\d+/.test(trimmed)) {
      push(trimmed);
    }
  }
  return found;
}

async function resolveSerialInputText(rawText) {
  const text = String(rawText || "");
  const whole = text.trim();
  if (isSinglePastedBase85(whole)) {
    return { ok: true, serials: [whole], message: "Ready: 1 serial(s)" };
  }
  const lines = text.split(/\r?\n/);
  const serials = [];
  const seen = new Set();
  const notes = [];
  const pushMany = (items) => {
    for (const item of items) {
      if (!item || seen.has(item)) continue;
      seen.add(item);
      serials.push(item);
    }
  };

  // Whole textarea is a single file path (common when users paste one quoted path).
  if (looksLikeSerialFilePath(text.trim()) && lines.filter((l) => l.trim()).length === 1) {
    const result = await window.sqbt.readSerialSource(text.trim());
    if (!result?.ok) {
      return { ok: false, serials: [], message: result?.message || "Could not read serial file." };
    }
    pushMany(result.serials || []);
    return {
      ok: true,
      serials,
      message: result.message || `Loaded ${serials.length} serial(s).`,
    };
  }

  for (const line of joinWrappedSerialLines(text)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (looksLikeSerialFilePath(trimmed)) {
      const result = await window.sqbt.readSerialSource(trimmed);
      if (!result?.ok) {
        notes.push(result?.message || `Failed: ${trimmed}`);
        continue;
      }
      pushMany(result.serials || []);
      if (result.message) notes.push(result.message);
      continue;
    }
    pushMany(extractSerialsFromText(trimmed));
  }

  // Fallback: scrape @U tokens from the whole blob (fenced markdown dumps).
  if (!serials.length) {
    pushMany(extractSerialsFromText(text));
  }

  return {
    ok: serials.length > 0,
    serials,
    message:
      serials.length > 0
        ? `Ready: ${serials.length} serial(s)${notes.length ? ` (${notes[0]})` : ""}`
        : notes[0] || "Paste @U / human serials, or a .txt / .docx path like \"C:\\\\Users\\\\…\\\\BP 4 Gear.txt\".",
  };
}

function applyTheme(theme) {
  const raw = String(theme || "").trim().toLowerCase().replaceAll("_", "-");
  const known = {
    default: "default",
    scooters: "scooters",
    "scooters-girly": "scooters-girly",
    girly: "scooters-girly",
    tina: "scooters-girly",
    claptrap: "claptrap",
    "cl4p-tp": "claptrap",
    moxxi: "moxxi",
    crimson: "crimson",
    "red-black": "crimson",
    psycho: "psycho",
    bandit: "psycho",
    maliwan: "maliwan",
  };
  currentTheme = known[raw] || "default";
  document.documentElement.setAttribute("data-theme", currentTheme);
  if (themeSelect) themeSelect.value = currentTheme;
}

function applyLocale(locale, { refresh = true } = {}) {
  const next = i18n.setLocale(locale || i18n.detectBrowserLocale());
  i18n.fillLocaleSelect(langSelect, next);
  i18n.applyDom();
  if (refresh) refreshLocalizedChrome();
  return next;
}

function refreshLocalizedChrome() {
  if (lastSetup) applyInstallLocationUi(lastSetup);
  applyBaseSdkUi(lastBaseSdk, lastModSync);
  if (lastModSync || lastBaseSdk) applyModSyncUi(lastModSync, lastBaseSdk);
  if (lastUpdateResult) renderUpdateStatus(lastUpdateResult);
  if (latestStatus) setStatusUi(latestStatus);
  else updateStartGuide();
  if (typeof renderTabs === "function") {
    if (manifest?.tabs?.length && tabBar?.children?.length) {
      for (const button of tabBar.querySelectorAll("button[data-tab-id]")) {
        const tab = manifest.tabs.find((row) => row.id === button.dataset.tabId);
        if (tab) setIconLabel(button, i18n.tabLabel(tab), TAB_ICONS[tab.id] || "");
      }
    } else {
      renderTabs();
    }
  }
}

const HIDDEN_SHAPE_OPTIONS = [
  { value: "forbidden_one", label: "the forbidden one" },
  { value: "forbidden_pair", label: "the forbidden pair" },
];

function applyShapeLayoutDefaults(sectionId, actionDef, shapeField, shapeValue, allFields, sectionEl) {
  if (!shapeField?.land_profile || !manifest?.land_layout_defaults) return;
  const profile = String(shapeField.land_profile || "shiny");
  const table = manifest.land_layout_defaults[profile];
  if (!table) return;
  const shape = String(shapeValue || "none").toLowerCase();
  if (shape === "none" || shape === "off") return;
  const row = table[shape] || table.circle || table.house;
  if (!row) return;
  for (const sibling of allFields || []) {
    if (
      sibling.key !== "radius" &&
      sibling.key !== "spacing" &&
      sibling.key !== "drop_height" &&
      sibling.key !== "z_bias"
    ) {
      continue;
    }
    let val = row[sibling.key];
    // Car: keep the player inside the silhouette — near-ground drop on first select.
    if (sibling.key === "drop_height" && shape === "car" && (val == null || val === "")) {
      val = 8;
    }
    // UFO: hover above the party by default.
    if (shape === "ufo") {
      if (sibling.key === "z_bias" && (val == null || val === "")) val = 175;
      if (sibling.key === "drop_height" && (val == null || val === "")) val = 220;
    }
    if (val == null) continue;
    const skey = actionFieldKey(sectionId, actionDef, sibling);
    fieldValues[skey] = String(val);
    const wrap = sectionEl?.querySelector(`[data-field-key="${skey}"]`);
    const input = wrap?.querySelector("input[type='number']");
    if (input) input.value = String(val);
  }
}

function injectHiddenShapeOptions() {
  if (!hiddenShapesUnlocked) return;
  for (const select of document.querySelectorAll("select.js-shape-select")) {
    if (select.querySelector('option[value="forbidden_one"]')) continue;
    const og = document.createElement("optgroup");
    og.label = "…";
    og.dataset.hiddenShapes = "1";
    for (const row of HIDDEN_SHAPE_OPTIONS) {
      const opt = document.createElement("option");
      opt.value = row.value;
      opt.textContent = row.label;
      og.appendChild(opt);
    }
    select.appendChild(og);
  }
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
  addWrap.innerHTML =
    "<span>Paste @U serials — one per line, or space-separated on one line. Browse a .txt / .yaml / .docx also works.</span>";
  const addArea = document.createElement("textarea");
  addArea.rows = 4;
  addArea.dataset.serialPasteArea = sectionId;
  addArea.placeholder =
    "@U…\n@U…\nor @U… @U… (space between)\nor Browse a gear list / STBX yaml";
  addWrap.appendChild(addArea);

  const btnRow = document.createElement("div");
  btnRow.className = "serial-add-actions";

  const browseBtn = document.createElement("button");
  browseBtn.type = "button";
  browseBtn.className = "ghost";
  browseBtn.textContent = "Browse file…";
  browseBtn.title = "Load a file into the paste box — then Send items or Add to library.";

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "ghost";
  addBtn.textContent = "Add to queue";
  addBtn.title = "Optional: build a mixed queue. Most people just paste and Send items.";

  const clearPasteBtn = document.createElement("button");
  clearPasteBtn.type = "button";
  clearPasteBtn.className = "ghost serial-clear-paste-btn";
  clearPasteBtn.textContent = "Clear";
  clearPasteBtn.title = "Clear the paste box.";
  clearPasteBtn.addEventListener("click", () => {
    addArea.value = "";
    addArea.focus();
    actionMessage.className = "action-message muted";
    actionMessage.textContent = "Paste box cleared.";
  });

  const fillPasteBox = (lines, note) => {
    if (!lines.length) {
      actionMessage.className = "action-message error";
      actionMessage.textContent =
        note ||
        "No @U / human serials found. For STBX / save YAML, look for lines like serial: '@U…'.";
      return;
    }
    addArea.value = lines.map((line) => String(line).trim()).filter(Boolean).join("\n\n");
    addArea.focus();
    actionMessage.className = "action-message ok";
    actionMessage.textContent =
      note || `Loaded ${lines.length} serial(s) — press Send items, or Add to library.`;
  };

  const appendSerials = (lines, note) => {
    if (!lines.length) {
      actionMessage.className = "action-message error";
      actionMessage.textContent =
        note ||
        "No @U / human serials found. For STBX / save YAML, look for lines like serial: '@U…'.";
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
    renderSerialSendListRows(sectionId, box);
    const fold = box.querySelector(".serial-queue-fold");
    if (fold) fold.open = true;
    actionMessage.className = "action-message ok";
    actionMessage.textContent = note || `Added ${lines.length} serial(s) to queue.`;
  };

  addBtn.addEventListener("click", async () => {
    addBtn.disabled = true;
    browseBtn.disabled = true;
    actionMessage.className = "action-message muted";
    actionMessage.textContent = "Reading serials…";
    try {
      const resolved = await resolveSerialInputText(addArea.value);
      appendSerials(resolved.serials || [], resolved.message);
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error || "Could not read serials.");
    } finally {
      addBtn.disabled = false;
      browseBtn.disabled = false;
    }
  });

  browseBtn.addEventListener("click", async () => {
    addBtn.disabled = true;
    browseBtn.disabled = true;
    actionMessage.className = "action-message muted";
    actionMessage.textContent = "Opening file…";
    try {
      const result = await window.sqbt.pickSerialFile();
      if (result?.cancelled) {
        actionMessage.className = "action-message muted";
        actionMessage.textContent = "File pick cancelled.";
        return;
      }
      if (!result?.ok) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = result?.message || "Could not read that file.";
        return;
      }
      // Browse always fills the paste box — never the optional queue or My Library.
      fillPasteBox(result.serials || [], result.message);
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error || "File pick failed.");
    } finally {
      addBtn.disabled = false;
      browseBtn.disabled = false;
    }
  });

  const libraryBtn = document.createElement("button");
  libraryBtn.type = "button";
  libraryBtn.className = "ghost serial-save-library-btn";
  libraryBtn.textContent = "Save to My packs";
  libraryBtn.title = "Save the paste box into a named pack.";
  libraryBtn.addEventListener("click", async () => {
    if (!actionsEnabled()) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = "Connect in-game first before saving a pack.";
      return;
    }
    libraryBtn.disabled = true;
    actionMessage.className = "action-message muted";
    actionMessage.textContent = "Reading paste box…";
    try {
      const resolved = await resolveSerialInputText(addArea.value);
      const serials = resolved.serials || [];
      if (!serials.length) {
        actionMessage.className = "action-message error";
        actionMessage.textContent =
          resolved.message || "Paste or Browse serials into the box first.";
        return;
      }
      const name = await promptTextDialog({
        kicker: "My packs",
        title: serials.length === 1 ? "Name this entry" : "Name this pack",
        detail:
          serials.length === 1
            ? "Saved under My packs → that pack name."
            : `${serials.length} serials will share this pack name.`,
        label: "Pack name",
        defaultValue: "",
        okLabel: "Save pack",
      });
      if (name == null) {
        actionMessage.className = "action-message muted";
        actionMessage.textContent = "Library save cancelled.";
        return;
      }
      const cleanName = String(name).trim();
      if (!cleanName) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = "Enter a pack name.";
        return;
      }
      await runAction(
        "serial_store_import_serials",
        {
          name: cleanName,
          group: cleanName,
          serials,
        },
        "",
        { sectionId, config: { catalog: "serial_store" } }
      );
      if (activeTabId === "serials") {
        const lib =
          tabContent.querySelector('[data-section-title="My packs"]') ||
          tabContent.querySelector('[data-section-title="My Library"]');
        if (lib) lib.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error || "Could not save to library.");
    } finally {
      libraryBtn.disabled = false;
    }
  });

  btnRow.append(browseBtn, clearPasteBtn, addBtn);

  // Send items + Add to library land here when the action card renders.
  const sendBtnSlot = document.createElement("div");
  sendBtnSlot.className = "serial-send-btn-slot";
  sendBtnSlot.dataset.serialSendBtn = sectionId;
  btnRow.append(sendBtnSlot, libraryBtn);

  // Send options (Send to / amount / open rewards) stay visible under the button row.
  const primarySlot = document.createElement("div");
  primarySlot.className = "serial-send-primary-slot";
  primarySlot.dataset.serialSendPrimary = sectionId;

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

  const queueDetails = document.createElement("details");
  queueDetails.className = "serial-queue-fold";
  const queueSummary = document.createElement("summary");
  queueSummary.textContent = "Optional queue list";
  const queueHint = document.createElement("p");
  queueHint.className = "muted small";
  queueHint.textContent =
    "Rarely needed. Add to queue to mix sets, then use Send queued under Optional queue below.";
  queueDetails.append(queueSummary, queueHint, meta, listEl);

  box.append(addWrap, btnRow, primarySlot, queueDetails);
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
    listEl.innerHTML = `<p class="muted">Queue empty — paste above and press Send items. Add to queue only to mix sets.</p>`;
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
  if (statusEl) statusEl.textContent = `${rows.length} in queue`;
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
    const bucket = favoriteBucketForCatalog(catalogName);
    const rows = sortRowsFavoritesFirst(
      data.rows || data.maps || data.stations || [],
      (row) => catalogFavoriteId(row, field),
      bucket
    );
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
      const favMark = isListFavorite(bucket, opt.value) ? "★ " : "";
      opt.textContent = favMark + (extra ? `${label} · ${extra}` : label);
      selectEl.appendChild(opt);
    }
    const key = actionFieldKey(sectionId, actionDef, field);
    catalogRowCache.set(key, rows);
    const current = fieldValues[key] || "";
    if (current) {
      selectEl.value = current;
      applyCatalogSelection(sectionId, actionDef, field, selectEl, key);
    }
    if (wrapEl) {
      wrapEl.dataset.catalogError = "";
      const selectRow = wrapEl.querySelector(".catalog-select-row") || wrapEl;
      let favBtn = selectRow.querySelector(".fav-toggle-catalog");
      if (!favBtn && bucket) {
        favBtn = document.createElement("button");
        favBtn.type = "button";
        favBtn.className = "fav-toggle fav-toggle-catalog";
        selectRow.appendChild(favBtn);
      }
      if (favBtn && bucket) {
        const syncFavBtn = () => {
          const value = String(selectEl.value || "").trim();
          const fav = value && isListFavorite(bucket, value);
          favBtn.disabled = !value;
          favBtn.classList.toggle("is-favorite", Boolean(fav));
          favBtn.textContent = fav ? "★" : "+";
          favBtn.title = fav ? "Remove from favourites" : "Add current selection to favourites";
        };
        favBtn.onclick = (event) => {
          event.preventDefault();
          event.stopPropagation();
          const value = String(selectEl.value || "").trim();
          if (!value) return;
          toggleRowFavorite(bucket, value, () => {
            populateCatalogSelect(selectEl, field, sectionId, actionDef, wrapEl);
          });
        };
        selectEl.addEventListener("change", syncFavBtn);
        syncFavBtn();
      }
    }
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
  if (field.tooltip) {
    wrap.title = field.tooltip;
  }
  if (field.type === "textarea" || field.wide || field.key === "serials") {
    wrap.classList.add("field-wide");
  }
  const key = fieldStorageKey(sectionId, actionDef, field);
  if (fieldValues[key] === undefined) {
    fieldValues[key] = field.default ?? "";
  }

  const title = document.createElement("span");
  title.textContent = field.label || field.key;
  wrap.appendChild(title);

  if (field.type === "checkbox") {
    wrap.classList.add("field-check");
    if (field.compact) {
      wrap.classList.add("field-compact");
    }
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = fieldValues[key] === true || String(fieldValues[key]).toLowerCase() === "true";
    input.addEventListener("change", () => {
      fieldValues[key] = input.checked;
      markAutoLobbyFieldTouched(key);
    });
    wrap.appendChild(input);
    wrap.dataset.fieldKey = key;
    return wrap;
  }

  if (field.type === "player_select") {
    const select = document.createElement("select");
    select.dataset.role = "player-select";
    if (field.includeAll) {
      select.dataset.includeAll = "1";
    }
    select.addEventListener("change", () => {
      fieldValues[key] = select.value;
      // Keep Boost target (top bar) in lockstep with any Send to / Target player picker.
      syncBoostTargetFromSendTo(select.value);
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
    const selectRow = document.createElement("div");
    selectRow.className = "catalog-select-row";
    selectRow.appendChild(select);
    wrap.appendChild(selectRow);
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
    const groups = field.option_groups;
    if (Array.isArray(groups) && groups.length) {
      for (const group of groups) {
        const og = document.createElement("optgroup");
        og.label = String(group.label || "");
        for (const option of group.options || []) {
          const opt = document.createElement("option");
          opt.value = option;
          const labels = field.option_labels || {};
          const badges = field.option_badges || {};
          const base = labels[option] || String(option).replaceAll("_", " ");
          opt.textContent = badges[option] && !String(base).includes("NEW")
            ? `✦ NEW · ${base}`
            : base;
          og.appendChild(opt);
        }
        input.appendChild(og);
      }
      if (groups.some((group) => String(group.label || "").toLowerCase().includes("3d"))) {
        input.classList.add("js-shape-select");
      }
    } else {
      for (const option of field.options || []) {
        const opt = document.createElement("option");
        opt.value = option;
        const labels = field.option_labels || {};
        opt.textContent = labels[option] || String(option).replaceAll("_", " ");
        input.appendChild(opt);
      }
    }
    input.addEventListener("change", () => {
      if (field.key === "open_rewards" && String(input.value).toLowerCase() === "yes") {
        if (
          !confirmSerialRisk(`${OPEN_REWARDS_LARGE_WARNING}\n\nTurn Open rewards ON for this send?`)
        ) {
          input.value = "no";
          fieldValues[key] = "no";
          return;
        }
      }
      fieldValues[key] = input.value;
      markAutoLobbyFieldTouched(key);
      if (field.key === "shape" && field.land_profile) {
        applyShapeLayoutDefaults(sectionId, actionDef, field, input.value, allFields, sectionEl);
      }
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
    input.inputMode = "numeric";
    if (field.min != null) input.min = String(field.min);
    if (field.max != null) input.max = String(field.max);
    if (field.step != null) input.step = String(field.step);
    // Wheel over a focused number field steals edits / feels like arrows "don't work".
    input.addEventListener(
      "wheel",
      (event) => {
        if (document.activeElement === input) {
          event.preventDefault();
        }
      },
      { passive: false }
    );
  } else {
    input = document.createElement("input");
    input.type = "text";
    if (field.placeholder) input.placeholder = field.placeholder;
    if (field.key === "backpack_size" || field.key === "bank_size") {
      input.inputMode = "numeric";
      input.autocomplete = "off";
      input.spellcheck = false;
      input.addEventListener("input", () => {
        const cleaned = String(input.value || "").replace(/[^\d]/g, "");
        if (cleaned !== input.value) input.value = cleaned;
      });
    }
  }
  if (field.key === "shape") {
    const retired = String(fieldValues[key] || "");
    if (retired === "psycho_mask") fieldValues[key] = "psycho";
    if (retired === "bl_logo") fieldValues[key] = "circle";
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
    markAutoLobbyFieldTouched(key);
    refreshCatalogSiblings();
  });
  input.addEventListener("change", () => {
    if (field.type === "number" && input.value !== "") {
      const parsed = Number(input.value);
      if (!Number.isFinite(parsed)) {
        input.value = String(field.default ?? field.min ?? 0);
      } else {
        let next = parsed;
        if (field.min != null) next = Math.max(Number(field.min), next);
        if (field.max != null) next = Math.min(Number(field.max), next);
        input.value = String(next);
      }
    }
    fieldValues[key] = input.value;
    markAutoLobbyFieldTouched(key);
    refreshCatalogSiblings();
  });
  wrap.appendChild(input);
  wrap.dataset.fieldKey = key;
  if (field.key === "open_rewards") {
    const ackWrap = document.createElement("label");
    ackWrap.className = "serial-risk-ack field-serial-risk-ack";
    ackWrap.title =
      "Skip amount / console-backpack confirmations after you acknowledge the risks.";
    const ackBox = document.createElement("input");
    ackBox.type = "checkbox";
    ackBox.checked = serialRiskAcknowledged();
    const ackText = document.createElement("span");
    ackText.textContent = "Don't warn again (amounts / console)";
    ackBox.addEventListener("change", () => {
      setSerialRiskAcknowledged(ackBox.checked);
    });
    ackWrap.append(ackBox, ackText);
    wrap.appendChild(ackWrap);
  }
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
    const bucket = favoriteBucketForCatalog(config.catalog);
    const rows = sortRowsFavoritesFirst(
      data.rows || [],
      (row) => poolFavoriteId(row),
      bucket
    );
    const rowsSig = `${cacheKey}:${rows.map((row) => `${poolBrowserRowId(row)}:${isListFavorite(bucket, poolFavoriteId(row)) ? 1 : 0}`).join("|")}`;
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
      const favId = poolFavoriteId(row);
      const wrap = document.createElement("div");
      wrap.className = "list-row-with-fav";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "pool-browser-row";
      if (rowId === selectedId) button.classList.add("is-selected");
      if (isListFavorite(bucket, favId)) button.classList.add("is-favorite");
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
      wrap.append(
        makeFavoriteButton(bucket, favId, () => refreshPoolBrowser(sectionId, config)),
        button
      );
      listEl.appendChild(wrap);
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

  const toggleWrap = document.createElement("div");
  toggleWrap.className = "pool-browser-toggles";
  for (const toggle of config.toggles || []) {
    const key = `${sectionId}:${toggle.key}`;
    if (fieldValues[key] === undefined) {
      fieldValues[key] = Boolean(toggle.default);
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pool-filter-toggle";
    btn.dataset.toggleKey = toggle.key;
    btn.title = toggle.tooltip || toggle.label || toggle.key;
    btn.style.setProperty("--toggle-accent", toggle.color || "#3ddc97");
    const paint = () => {
      const on = Boolean(fieldValues[key]);
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = toggle.label || toggle.key;
    };
    paint();
    btn.addEventListener("click", () => {
      fieldValues[key] = !Boolean(fieldValues[key]);
      paint();
      refreshPoolBrowser(sectionId, config);
    });
    toggleWrap.appendChild(btn);
  }

  const meta = document.createElement("div");
  meta.className = "multiselect-meta pool-browser-meta-row";
  meta.innerHTML = `<span class="multiselect-count badge pool-browser-count">0</span>
    <span class="pool-browser-selected muted small">Click a pool below to select it</span>`;

  toolbar.append(searchWrap, categoryWrap);
  if (toggleWrap.childElementCount) toolbar.appendChild(toggleWrap);
  toolbar.appendChild(meta);
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

function renderSerialStorePackList(sectionId, config, listEl, rows, selected, countEl, bucket) {
  if (!serialStoreExpanded.has(sectionId)) {
    serialStoreExpanded.set(sectionId, new Set());
  }
  const expanded = serialStoreExpanded.get(sectionId);
  const byGroup = new Map();
  for (const row of rows) {
    const g = String(row.group || "Default").trim() || "Default";
    if (!byGroup.has(g)) byGroup.set(g, []);
    byGroup.get(g).push(row);
  }
  const packNames = [...byGroup.keys()].sort((a, b) => a.localeCompare(b));
  // Auto-expand when filtering a single pack, or when only one pack exists.
  if (packNames.length === 1) expanded.add(packNames[0]);
  const filterGroup = String(fieldValues[`${sectionId}:group`] || "All");
  if (filterGroup && filterGroup !== "All") expanded.add(filterGroup);

  for (const packName of packNames) {
    const members = byGroup.get(packName) || [];
    const details = document.createElement("details");
    details.className = "serial-store-pack";
    details.open = expanded.has(packName);
    details.addEventListener("toggle", () => {
      if (details.open) expanded.add(packName);
      else expanded.delete(packName);
    });
    const summary = document.createElement("summary");
    summary.className = "serial-store-pack-summary";
    const title = document.createElement("span");
    title.className = "serial-store-pack-title";
    title.textContent = `${packName} (${members.length})`;
    const actions = document.createElement("span");
    actions.className = "serial-store-pack-actions";
    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.textContent = "Rename";
    renameBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const next = await promptTextDialog({
        kicker: "My packs",
        title: "Rename pack",
        detail: `Current name: ${packName}`,
        label: "New pack name",
        defaultValue: packName,
        okLabel: "Rename",
      });
      if (next == null) return;
      const cleaned = String(next).trim();
      if (!cleaned || cleaned === packName) return;
      try {
        const { data } = await window.sqbt.postAction("serial_store_rename_group", {
          old_group: packName,
          new_group: cleaned,
        });
        actionMessage.className = data?.ok === false ? "action-message error" : "action-message ok";
        actionMessage.textContent = data?.message || "Renamed.";
        if (data?.ok !== false) {
          expanded.delete(packName);
          expanded.add(cleaned);
          refreshAllSerialStoreSections();
        }
      } catch (error) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = String(error?.message || error);
      }
    });
    const selectPackBtn = document.createElement("button");
    selectPackBtn.type = "button";
    selectPackBtn.textContent = "Select";
    selectPackBtn.title = "Tick only this pack’s rows (clears other packs first)";
    selectPackBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const next = new Set();
      for (const row of members) {
        const rowId = multiselectRowId(row, config);
        next.add(rowId);
        const serial = rowSerialValue(row, config);
        if (serial) rememberMultiselectSerial(sectionId, rowId, serial);
      }
      multiselectState.set(sectionId, next);
      expanded.add(packName);
      if (countEl) countEl.textContent = formatMultiselectSelectedLabel(sectionId, config);
      refreshMultiselectSection(sectionId, config);
      actionMessage.className = "action-message muted";
      actionMessage.textContent = `Selected ${next.size} row(s) in pack “${packName}”.`;
    });
    const collectPackSerials = () => {
      const next = new Set();
      const serials = [];
      const seen = new Set();
      for (const row of members) {
        const rowId = multiselectRowId(row, config);
        next.add(rowId);
        const serial = rowSerialValue(row, config);
        if (serial) rememberMultiselectSerial(sectionId, rowId, serial);
        if (isDeliverableSerial(serial) && !seen.has(serial)) {
          seen.add(serial);
          serials.push(serial);
        }
      }
      multiselectState.set(sectionId, next);
      return serials;
    };
    const sendPackBtn = document.createElement("button");
    sendPackBtn.type = "button";
    sendPackBtn.textContent = "Send pack";
    sendPackBtn.title =
      "Mail every @U in this pack (uses Override level above when set to yes)";
    sendPackBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const serials = collectPackSerials();
      if (!serials.length) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = `Pack “${packName}” has no deliverable @U serials.`;
        return;
      }
      const levelFields = packDeliveryLevelFields(sectionId);
      const levelNote = levelFields.level_override
        ? ` releveled to ${levelFields.level}`
        : "";
      await runAction(
        "deliver_serials",
        {
          serials,
          mode: "player",
          open_rewards: true,
          _selected_count: serials.length,
          ...levelFields,
        },
        `Mail all ${serials.length} serial(s) from pack “${packName}”${levelNote}?`,
        { sectionId, config, deliverStore: true }
      );
    });
    const sendPackLvlBtn = document.createElement("button");
    sendPackLvlBtn.type = "button";
    sendPackLvlBtn.textContent = "Send @lvl";
    sendPackLvlBtn.title = "Mail this pack releveled to the level box above (Override level)";
    sendPackLvlBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const serials = collectPackSerials();
      if (!serials.length) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = `Pack “${packName}” has no deliverable @U serials.`;
        return;
      }
      const levelFields = packDeliveryLevelFields(sectionId, { force: true });
      await runAction(
        "deliver_serials",
        {
          serials,
          mode: "player",
          open_rewards: true,
          _selected_count: serials.length,
          ...levelFields,
        },
        `Mail all ${serials.length} serial(s) from pack “${packName}” releveled to ${levelFields.level}?`,
        { sectionId, config, deliverStore: true }
      );
    });
    const addPackBtn = document.createElement("button");
    addPackBtn.type = "button";
    addPackBtn.textContent = "Add";
    addPackBtn.title = "Select this pack in Add to pack, then paste codes and Save entry";
    addPackBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      focusSerialStoreAddToPack(sectionId, packName);
    });
    const exportBtn = document.createElement("button");
    exportBtn.type = "button";
    exportBtn.textContent = "Export .txt";
    exportBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await runAction("serial_store_export_text", { group: packName }, "", {
        sectionId,
        config,
      });
    });
    const exportJsonBtn = document.createElement("button");
    exportJsonBtn.type = "button";
    exportJsonBtn.textContent = "Export .json";
    exportJsonBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await runAction("serial_store_export_json", { group: packName }, "", {
        sectionId,
        config,
      });
    });
    const deletePackBtn = document.createElement("button");
    deletePackBtn.type = "button";
    deletePackBtn.textContent = "Delete";
    deletePackBtn.title = "Delete this entire named pack";
    deletePackBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await runAction("serial_store_delete_group", { group: packName }, "", {
        sectionId,
        config,
      });
    });
    actions.append(
      selectPackBtn,
      sendPackBtn,
      sendPackLvlBtn,
      addPackBtn,
      renameBtn,
      exportBtn,
      exportJsonBtn,
      deletePackBtn
    );
    summary.append(title, actions);
    details.appendChild(summary);

    const body = document.createElement("div");
    body.className = "serial-store-pack-body";
    for (const row of members) {
      const rowId = multiselectRowId(row, config);
      const wrap = document.createElement("div");
      wrap.className = "list-row-with-fav";
      if (bucket) {
        wrap.appendChild(
          makeFavoriteButton(bucket, rowId, () => refreshMultiselectSection(sectionId, config))
        );
      }
      const label = document.createElement("label");
      label.className = "multiselect-row";
      if (isListFavorite(bucket, rowId)) label.classList.add("is-favorite");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = selected.has(rowId);
      cb.addEventListener("change", () => {
        if (cb.checked) selected.add(rowId);
        else selected.delete(rowId);
        if (cb.checked) {
          const serial = rowSerialValue(row, config);
          if (serial) rememberMultiselectSerial(sectionId, rowId, serial);
        }
        if (countEl) countEl.textContent = formatMultiselectSelectedLabel(sectionId, config);
      });
      const text = document.createElement("button");
      text.type = "button";
      text.className = "serial-store-entry-link";
      const titleText = String(row[config.labelKey || "title"] || row.name || rowId);
      const serial = String(row.serial || "");
      const snip = serial.length > 36 ? `${serial.slice(0, 32)}…` : serial;
      text.textContent = snip ? `${titleText} · ${snip}` : titleText;
      text.title = "Click to edit in the form above";
      text.addEventListener("click", (event) => {
        event.preventDefault();
        serialStoreEdit.set(sectionId, {
          id: row.id,
          name: row.name || row.title,
          group: row.group || "Default",
          serial: row.serial || "",
        });
        renderSerialStoreForm(sectionId);
        actionMessage.className = "action-message muted";
        actionMessage.textContent = `Editing “${titleText}” — Save to update.`;
      });
      label.append(cb, text);
      wrap.appendChild(label);
      body.appendChild(wrap);
    }
    details.appendChild(body);
    listEl.appendChild(details);
  }
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
  let data;
  if (config.catalog === "backpack" && (config.params?.pack_bay || config.source === "save_yaml")) {
    // Pack Bay: decrypt latest character autosave in the EXE — no game-thread scan.
    if (typeof window.sqbt?.packBayScan === "function") {
      data = await window.sqbt.packBayScan({
        limit: Number(params.limit) || 200,
        path: params.save_path || "",
        steamid: params.steamid || "",
      });
    } else {
      data = { ok: false, message: "Pack Bay save reader unavailable in this build.", rows: [] };
    }
    // Name + level via the same GZO decode Party Bay uses (bridge / in-game mod).
    if (data?.ok && Array.isArray(data.rows) && data.rows.length && typeof window.sqbt?.postAction === "function") {
      try {
        const serials = data.rows.map((row) => String(row?.serial || "").trim()).filter((s) => s.startsWith("@U"));
        if (serials.length) {
          const labeled = await window.sqbt.postAction("bay_label_serials", { serials }, 60);
          const labeledRows = labeled?.data?.rows;
          if (labeled?.data?.ok && Array.isArray(labeledRows) && labeledRows.length) {
            const bySerial = new Map(labeledRows.map((row) => [String(row.serial || ""), row]));
            data.rows = data.rows.map((row, index) => {
              const hit = bySerial.get(String(row.serial || ""));
              if (!hit) return row;
              return {
                ...row,
                id: row.id != null ? row.id : String(index),
                slot: row.slot != null ? row.slot : index,
                title: hit.title || row.title,
                display_name: hit.display_name || row.display_name,
                rarity: hit.rarity || row.rarity,
                manufacturer: hit.manufacturer || row.manufacturer,
                item_type: hit.item_type || row.item_type,
                level: hit.level != null ? hit.level : row.level,
              };
            });
            const named = Number(labeled.data.named || 0);
            const leveled = Number(labeled.data.leveled || 0);
            const baseMsg = String(data.message || "").trim();
            data.message = `${baseMsg} Named ${named}/${serials.length}, leveled ${leveled}/${serials.length}.`.trim();
          }
        }
      } catch {
        /* keep raw serial titles if label pass fails */
      }
    }
  } else {
    data = await loadCatalog(config.catalog, params);
  }
    const bucket = favoriteBucketForCatalog(config.catalog);
    const rows = sortRowsFavoritesFirst(
      data.rows || [],
      (row) => multiselectRowId(row, config),
      bucket
    );
    multiselectRows.set(sectionId, rows);
    cacheMultiselectRows(sectionId, rows, config);
    if (!multiselectState.has(sectionId)) {
      multiselectState.set(sectionId, new Set());
    }
    const selected = multiselectState.get(sectionId);
    listEl.innerHTML = "";
    if (!rows.length) {
      listEl.innerHTML = catalogEmptyHtml(config.catalog, config);
      if (data.message && statusEl) statusEl.textContent = data.message;
    } else if (config.catalog === "serial_store") {
      renderSerialStorePackList(sectionId, config, listEl, rows, selected, countEl, bucket);
    } else {
      for (const row of rows) {
        const rowId = multiselectRowId(row, config);
        const wrap = document.createElement("div");
        wrap.className = "list-row-with-fav";
        if (bucket) {
          wrap.appendChild(
            makeFavoriteButton(bucket, rowId, () => refreshMultiselectSection(sectionId, config))
          );
        }
        const label = document.createElement("label");
        label.className = "multiselect-row";
        if (isListFavorite(bucket, rowId)) label.classList.add("is-favorite");
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = selected.has(rowId);
        cb.addEventListener("change", () => {
          if (cb.checked) selected.add(rowId);
          else selected.delete(rowId);
          if (cb.checked) {
            const serial = rowSerialValue(row, config);
            if (serial) rememberMultiselectSerial(sectionId, rowId, serial);
          }
          if (countEl) countEl.textContent = formatMultiselectSelectedLabel(sectionId, config);
        });
        const text = document.createElement("span");
        const title = String(row[config.labelKey || "title"] || row.name || rowId);
        const extraBits = [row.type, row.manufacturer, row.creator, row.group || row.listing || row.category];
        if (config.kind === "backpack" || config.catalog === "backpack") {
          if (row.level != null && row.level !== "") extraBits.unshift(`L${row.level}`);
          const serial = String(row.serial || "");
          if (serial.startsWith("@U")) {
            extraBits.push(serial.length > 40 ? `${serial.slice(0, 36)}…` : serial);
          } else {
            extraBits.push("no @U — cannot relevel");
          }
        }
        const extra = extraBits.filter((bit, idx, arr) => bit && arr.indexOf(bit) === idx).join(" · ");
        text.textContent = extra ? `${title} · ${extra}` : title;
        label.append(cb, text);
        wrap.appendChild(label);
        listEl.appendChild(wrap);
      }
    }
    if (countEl) countEl.textContent = formatMultiselectSelectedLabel(sectionId, config);
    const totalFiltered = Number(data.total || rows.length || 0);
    if (statusEl) {
      const base = data.message || `${rows.length} entries`;
      if (totalFiltered > rows.length) {
        statusEl.textContent = `${base} · ${totalFiltered} match filters (list capped — Select all filtered loads all before Deliver)`;
      } else {
        statusEl.textContent = base;
      }
    }
    const listByFilter = {
      group: data.groups,
      listing: data.listings,
      category: data.categories,
      type: data.types,
      manufacturer: data.manufacturers,
      creator: data.creators,
    };
    if (config.catalog === "serial_store" && Array.isArray(data.groups)) {
      rememberSerialStorePackNames(sectionId, data.groups);
      fillSerialStorePackSelect(sectionId);
    }
    for (const filterSelect of box.querySelectorAll("select[data-filter-key]")) {
      const key = filterSelect.dataset.filterKey || "";
      const listKey = filterSelect.dataset.filterList || key;
      const list = listByFilter[key] || listByFilter[listKey];
      if (!Array.isArray(list) || !list.length) continue;
      const current = fieldValues[`${sectionId}:${key}`] || "All";
      filterSelect.innerHTML = "";
      for (const item of list) {
        const opt = document.createElement("option");
        opt.value = item;
        opt.textContent = item;
        filterSelect.appendChild(opt);
      }
      filterSelect.value = list.includes(current) ? current : "All";
      fieldValues[`${sectionId}:${key}`] = filterSelect.value;
    }
    box.dataset.catalogError = "";
  } catch (error) {
    listEl.innerHTML = catalogEmptyHtml(config.catalog) || `<p class="muted">${formatCatalogError(config.catalog, error)}</p>`;
    if (config.catalog !== "serial_store" && config.catalog !== "gzo" && config.catalog !== "lootlemon") {
      listEl.innerHTML = `<p class="muted">${formatCatalogError(config.catalog, error)}</p>`;
    } else if (String(error?.message || "").trim()) {
      // Prefer curated empty-state copy; keep status line for the raw reason.
      if (statusEl) statusEl.textContent = formatCatalogError(config.catalog, error);
    }
    if (statusEl && !statusEl.textContent) statusEl.textContent = "";
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

const SERIAL_STORE_NEW_PACK = "__new__";
/** @type {Map<string, string[]>} */
const serialStorePackNames = new Map();

function serialStoreSectionEl(sectionId) {
  if (!tabContent || !sectionId) return null;
  return (
    tabContent.querySelector(`[data-section-id="${CSS.escape(sectionId)}"]`) ||
    tabContent.querySelector(`[data-section-id="${sectionId}"]`)
  );
}

function rememberSerialStorePackNames(sectionId, groups) {
  const names = new Set(["Default"]);
  for (const raw of groups || []) {
    const g = String(raw || "").trim();
    if (!g || g.toLowerCase() === "all") continue;
    names.add(g);
  }
  const edit = serialStoreEdit.get(sectionId);
  const editGroup = String(edit?.group || "").trim();
  if (editGroup && editGroup.toLowerCase() !== "all") names.add(editGroup);
  const sorted = [...names].sort((a, b) => a.localeCompare(b));
  serialStorePackNames.set(sectionId, sorted);
  return sorted;
}

function serialStoreKnownPackNames(sectionId) {
  const cached = serialStorePackNames.get(sectionId);
  if (cached?.length) return cached;
  const fromRows = [];
  for (const row of multiselectRows.get(sectionId) || []) {
    fromRows.push(String(row.group || "Default").trim() || "Default");
  }
  return rememberSerialStorePackNames(sectionId, fromRows);
}

function fillSerialStorePackSelect(sectionId) {
  const sectionEl = serialStoreSectionEl(sectionId);
  const form = sectionEl?.querySelector(".serial-store-form");
  if (!form) return;
  const packSelect = form.querySelector("[data-store-pack-select]");
  const groupInput = form.querySelector("[data-store-group]");
  if (!packSelect) return;
  const edit = serialStoreEdit.get(sectionId) || { group: "Default" };
  const wanted = String(edit.group || "Default").trim() || "Default";
  const packs = serialStoreKnownPackNames(sectionId);
  if (wanted.toLowerCase() !== "all" && !packs.includes(wanted)) {
    packs.push(wanted);
    packs.sort((a, b) => a.localeCompare(b));
    serialStorePackNames.set(sectionId, packs);
  }
  const prev = packSelect.value;
  packSelect.innerHTML = "";
  for (const pack of packs) {
    const opt = document.createElement("option");
    opt.value = pack;
    opt.textContent = pack;
    packSelect.appendChild(opt);
  }
  const newOpt = document.createElement("option");
  newOpt.value = SERIAL_STORE_NEW_PACK;
  newOpt.textContent = "＋ New pack…";
  packSelect.appendChild(newOpt);
  if (wanted && packs.includes(wanted)) {
    packSelect.value = wanted;
    if (groupInput) {
      groupInput.value = "";
      groupInput.hidden = true;
    }
  } else if (prev === SERIAL_STORE_NEW_PACK || (wanted && !packs.includes(wanted))) {
    packSelect.value = SERIAL_STORE_NEW_PACK;
    if (groupInput) {
      groupInput.hidden = false;
      groupInput.value = wanted === "Default" ? "" : wanted;
    }
  } else {
    packSelect.value = packs[0] || "Default";
    if (groupInput) {
      groupInput.value = "";
      groupInput.hidden = true;
    }
  }
}

function syncSerialStoreEditFromForm(sectionId) {
  const sectionEl = serialStoreSectionEl(sectionId);
  if (!sectionEl) return;
  const edit = serialStoreEdit.get(sectionId) || { id: "", name: "", group: "Default", serial: "" };
  const nameInput = sectionEl.querySelector("[data-store-name]");
  const packSelect = sectionEl.querySelector("[data-store-pack-select]");
  const groupInput = sectionEl.querySelector("[data-store-group]");
  const serialInput = sectionEl.querySelector("[data-store-serial]");
  if (nameInput) edit.name = nameInput.value;
  if (packSelect) {
    if (packSelect.value === SERIAL_STORE_NEW_PACK) {
      edit.group = String(groupInput?.value || "").trim() || "Default";
    } else {
      edit.group = String(packSelect.value || "").trim() || "Default";
    }
  } else if (groupInput) {
    edit.group = groupInput.value;
  }
  if (serialInput) edit.serial = serialInput.value;
  if (!edit.group || String(edit.group).toLowerCase() === "all") edit.group = "Default";
  serialStoreEdit.set(sectionId, edit);
}

function renderSerialStoreForm(sectionId) {
  const sectionEl = serialStoreSectionEl(sectionId);
  const form = sectionEl?.querySelector(".serial-store-form");
  if (!form) return;
  const edit = serialStoreEdit.get(sectionId) || { id: "", name: "", group: "Default", serial: "" };
  if (!edit.group || String(edit.group).toLowerCase() === "all") edit.group = "Default";
  serialStoreEdit.set(sectionId, edit);
  const nameInput = form.querySelector("[data-store-name]");
  const serialInput = form.querySelector("[data-store-serial]");
  if (nameInput) nameInput.value = edit.name || "";
  if (serialInput) serialInput.value = edit.serial || "";
  fillSerialStorePackSelect(sectionId);
}

function focusSerialStoreAddToPack(sectionId, packName) {
  const cleaned = String(packName || "").trim() || "Default";
  const edit = serialStoreEdit.get(sectionId) || {};
  edit.group = cleaned;
  edit.id = "";
  edit.name = "";
  serialStoreEdit.set(sectionId, edit);
  rememberSerialStorePackNames(sectionId, [...serialStoreKnownPackNames(sectionId), cleaned]);
  // Show that pack in the list after save — filter is separate from destination select.
  fieldValues[`${sectionId}:group`] = cleaned;
  renderSerialStoreForm(sectionId);
  const sectionEl = serialStoreSectionEl(sectionId);
  const form = sectionEl?.querySelector(".serial-store-form");
  const serialField = sectionEl?.querySelector("textarea[data-store-serial]");
  form?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  if (serialField) serialField.focus();
  const config = getMultiselectConfig(sectionId);
  if (config) {
    catalogCache.delete(catalogCacheKey("serial_store", multiselectParams(sectionId, config)));
    refreshMultiselectSection(sectionId, config);
  }
  actionMessage.className = "action-message muted";
  actionMessage.textContent = `Pack “${cleaned}” selected — paste codes, then Save entry.`;
}

function packDeliveryLevelFields(sectionId, { force = false } = {}) {
  const overrideOn = force || fieldValues[`${sectionId}:level_override`] === "yes";
  if (!overrideOn) return {};
  return {
    level_override: true,
    level: Number(fieldValues[`${sectionId}:level`] || 70) || 70,
  };
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
  search.placeholder =
    config.catalog === "serial_store"
      ? "Search library…"
      : config.catalog === "gzo" || config.catalog === "lootlemon"
        ? "Search codes…"
        : "Search…";
  search.value = fieldValues[searchKey];
  let searchDebounce = 0;
  search.addEventListener("input", () => {
    fieldValues[searchKey] = search.value;
    catalogCache.delete(catalogCacheKey(config.catalog, multiselectParams(sectionId, config)));
    window.clearTimeout(searchDebounce);
    searchDebounce = window.setTimeout(() => {
      // Keep focus if the list remounts mid-type.
      const keepFocus = document.activeElement === search;
      const caret = keepFocus ? search.selectionStart : null;
      refreshMultiselectSection(sectionId, config).then(() => {
        if (!keepFocus) return;
        const again = document.querySelector(
          `[data-multiselect-section="${sectionId}"] input[type="search"]`
        );
        if (again) {
          again.focus();
          if (caret != null) {
            try {
              again.setSelectionRange(caret, caret);
            } catch {
              /* ignore */
            }
          }
        }
      });
    }, 220);
  });
  toolbar.appendChild(search);

  const primaryFilters = [];
  const advancedFilters = [];
  for (const filter of config.filters || []) {
    if (filter.advanced) advancedFilters.push(filter);
    else primaryFilters.push(filter);
  }

  const appendFilterControl = (filter, host) => {
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
    filterSelect.dataset.filterKey = filter.key;
    filterSelect.dataset.filterList = filter.catalogParam || filter.key;
    filterSelect.value = fieldValues[filterKey];
    filterSelect.addEventListener("change", () => {
      fieldValues[filterKey] = filterSelect.value;
      if (filter.key === "category" || filter.key === "type" || filter.key === "manufacturer") {
        if (filter.key === "category") {
          const typeKey = `${sectionId}:type`;
          fieldValues[typeKey] = "All";
          const typeSelect = box.querySelector('select[data-filter-key="type"]');
          if (typeSelect) typeSelect.value = "All";
        }
        if (filter.key === "category" || filter.key === "type") {
          const makerKey = `${sectionId}:manufacturer`;
          fieldValues[makerKey] = "All";
          const makerSelect = box.querySelector('select[data-filter-key="manufacturer"]');
          if (makerSelect) makerSelect.value = "All";
        }
        const creatorKey = `${sectionId}:creator`;
        fieldValues[creatorKey] = "All";
        const creatorSelect = box.querySelector('select[data-filter-key="creator"]');
        if (creatorSelect) creatorSelect.value = "All";
      }
      catalogCache.delete(catalogCacheKey(config.catalog, multiselectParams(sectionId, config)));
      refreshMultiselectSection(sectionId, config);
    });
    filterWrap.append(filterLabel, filterSelect);
    host.appendChild(filterWrap);
  };

  for (const filter of primaryFilters) appendFilterControl(filter, toolbar);
  if (advancedFilters.length) {
    const adv = document.createElement("details");
    adv.className = "multiselect-advanced-filters";
    const summary = document.createElement("summary");
    summary.textContent = "More filters";
    const advBody = document.createElement("div");
    advBody.className = "multiselect-advanced-filters-body";
    for (const filter of advancedFilters) appendFilterControl(filter, advBody);
    adv.append(summary, advBody);
    toolbar.appendChild(adv);
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
    deliverWrap.innerHTML = "<span>Send to</span>";
    const deliverPlayer = document.createElement("select");
    deliverPlayer.dataset.role = "player-select";
    deliverPlayer.dataset.deliverPlayerKey = deliverPlayerKey;
    deliverPlayer.dataset.includeAll = "1";
    deliverPlayer.addEventListener("change", () => {
      fieldValues[deliverPlayerKey] = deliverPlayer.value;
      syncBoostTargetFromSendTo(deliverPlayer.value);
    });
    deliverWrap.appendChild(deliverPlayer);
    toolbar.appendChild(deliverWrap);

    const openWrap = document.createElement("label");
    openWrap.className = "multiselect-filter";
    openWrap.innerHTML = "<span>Open rewards</span>";
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
    if (fieldValues[openRewardsKey] === undefined || fieldValues[openRewardsKey] === "") {
      fieldValues[openRewardsKey] = "yes";
    }
    openToggle.value =
      fieldValues[openRewardsKey] === "yes" || fieldValues[openRewardsKey] === true ? "yes" : "no";
    openToggle.addEventListener("change", () => {
      if (openToggle.value === "yes") {
        if (
          !confirmSerialRisk(`${OPEN_REWARDS_LARGE_WARNING}\n\nTurn Open rewards ON for this send?`)
        ) {
          openToggle.value = "no";
          fieldValues[openRewardsKey] = "no";
          return;
        }
      }
      fieldValues[openRewardsKey] = openToggle.value;
    });
    openWrap.appendChild(openToggle);
    toolbar.appendChild(openWrap);

    const ackWrap = document.createElement("label");
    ackWrap.className = "multiselect-filter serial-risk-ack";
    ackWrap.title =
      "Skip amount / console-backpack confirmations after you acknowledge the risks.";
    const ackBox = document.createElement("input");
    ackBox.type = "checkbox";
    ackBox.checked = serialRiskAcknowledged();
    const ackText = document.createElement("span");
    ackText.textContent = "Don't warn again";
    ackBox.addEventListener("change", () => {
      setSerialRiskAcknowledged(ackBox.checked);
    });
    ackWrap.append(ackBox, ackText);
    toolbar.appendChild(ackWrap);
  }

  if (config.levelOverride) {
    const levelOverrideKey = `${sectionId}:level_override`;
    const levelKey = `${sectionId}:level`;
    if (fieldValues[levelOverrideKey] === undefined) fieldValues[levelOverrideKey] = "no";
    if (fieldValues[levelKey] === undefined) fieldValues[levelKey] = "70";
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
    levelInput.max = "70";
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
    refreshBtn.className = "primary";
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
  selectAllBtn.addEventListener("click", async () => {
    const selected = multiselectState.get(sectionId) || new Set();
    selectAllBtn.disabled = true;
    if (statusEl) statusEl.textContent = "Loading full filtered list…";
    try {
      const params = { ...multiselectParams(sectionId, config), limit: 10000 };
      const data = await loadCatalog(config.catalog, params);
      let rows = sortRowsFavoritesFirst(
        data.rows || [],
        (row) => multiselectRowId(row, config),
        favoriteBucketForCatalog(config.catalog)
      );
      // My Library: Pack=All must not select every pack — only expanded packs
      // (or the specific pack filter when set).
      if (config.catalog === "serial_store" || config?.serialStore) {
        const filterGroup = String(fieldValues[`${sectionId}:group`] || params.group || "All");
        if (filterGroup && filterGroup !== "All") {
          rows = rows.filter(
            (row) => String(row.group || "Default").trim() === filterGroup
          );
        } else {
          const expanded = serialStoreExpanded.get(sectionId) || new Set();
          if (expanded.size) {
            rows = rows.filter((row) =>
              expanded.has(String(row.group || "Default").trim() || "Default")
            );
          } else if (rows.length) {
            if (statusEl) {
              statusEl.textContent =
                "Expand a pack (or set Pack filter), then Select all filtered — or use Select on a pack header.";
            }
            selectAllBtn.disabled = false;
            return;
          }
        }
      }
      selected.clear();
      cacheMultiselectRows(sectionId, rows, config);
      for (const row of rows) {
        selected.add(multiselectRowId(row, config));
      }
      multiselectState.set(sectionId, selected);
      if (countEl) countEl.textContent = formatMultiselectSelectedLabel(sectionId, config);
      const total = Number(data.total || rows.length || 0);
      if (statusEl) {
        statusEl.textContent =
          total > rows.length
            ? `Selected ${selected.size} — loaded ${rows.length} of ${total}`
            : `Selected ${selected.size} filtered row(s)`;
      }
    } catch (error) {
      const rows = multiselectRows.get(sectionId) || [];
      selected.clear();
      for (const row of rows) {
        selected.add(multiselectRowId(row, config));
      }
      multiselectState.set(sectionId, selected);
      if (countEl) countEl.textContent = formatMultiselectSelectedLabel(sectionId, config);
      if (statusEl) statusEl.textContent = `Selected visible rows only (${formatCatalogError(config.catalog, error)})`;
    } finally {
      selectAllBtn.disabled = false;
      refreshMultiselectSection(sectionId, config);
    }
  });
  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.textContent = "Clear";
  clearBtn.addEventListener("click", () => {
    multiselectState.set(sectionId, new Set());
    multiselectSerialById.set(sectionId, new Map());
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

function downloadTextFile(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "sqbt-library.txt";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function pickLibraryImportText() {
  return new Promise((resolve, reject) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".txt,.json,text/plain,application/json";
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (!file) {
        resolve(null);
        return;
      }
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("Could not read that file."));
      reader.readAsText(file);
    });
    input.addEventListener("cancel", () => resolve(null));
    input.click();
  });
}

function renderSerialStoreSection(section, sectionId, sectionEl) {
  if (!serialStoreEdit.has(sectionId)) {
    serialStoreEdit.set(sectionId, { id: "", name: "", group: "Default", serial: "" });
  }
  if (!serialStoreExpanded.has(sectionId)) {
    serialStoreExpanded.set(sectionId, new Set());
  }

  const form = document.createElement("div");
  form.className = "serial-store-form fields-grid";
  const nameWrap = document.createElement("label");
  nameWrap.className = "field";
  nameWrap.innerHTML = "<span>Item name <span class='muted'>(optional)</span></span>";
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.dataset.storeName = "1";
  nameInput.placeholder = "Auto from serial if empty";
  nameInput.addEventListener("input", () => {
    const edit = serialStoreEdit.get(sectionId) || {};
    edit.name = nameInput.value;
    serialStoreEdit.set(sectionId, edit);
  });
  nameWrap.appendChild(nameInput);

  const groupWrap = document.createElement("label");
  groupWrap.className = "field serial-store-pack-dest";
  groupWrap.innerHTML = "<span>Add to pack</span>";
  const packSelect = document.createElement("select");
  packSelect.dataset.storePackSelect = "1";
  packSelect.title = "Pick an existing pack, or New pack…";
  const groupInput = document.createElement("input");
  groupInput.type = "text";
  groupInput.dataset.storeGroup = "1";
  groupInput.placeholder = "New pack name…";
  groupInput.hidden = true;
  const syncPackDest = () => {
    const edit = serialStoreEdit.get(sectionId) || {};
    if (packSelect.value === SERIAL_STORE_NEW_PACK) {
      groupInput.hidden = false;
      edit.group = String(groupInput.value || "").trim() || "Default";
    } else {
      groupInput.hidden = true;
      groupInput.value = "";
      edit.group = String(packSelect.value || "").trim() || "Default";
    }
    if (!edit.group || String(edit.group).toLowerCase() === "all") edit.group = "Default";
    serialStoreEdit.set(sectionId, edit);
  };
  packSelect.addEventListener("change", syncPackDest);
  groupInput.addEventListener("input", () => {
    if (packSelect.value !== SERIAL_STORE_NEW_PACK) return;
    const edit = serialStoreEdit.get(sectionId) || {};
    edit.group = groupInput.value;
    serialStoreEdit.set(sectionId, edit);
  });
  groupWrap.append(packSelect, groupInput);

  const serialWrap = document.createElement("label");
  serialWrap.className = "field field-wide";
  serialWrap.innerHTML = "<span>Codes</span>";
  const serialInput = document.createElement("textarea");
  serialInput.rows = 4;
  serialInput.dataset.storeSerial = "1";
  serialInput.placeholder = "Paste @U codes here — one per line is fine";
  serialInput.addEventListener("input", () => {
    const edit = serialStoreEdit.get(sectionId) || {};
    edit.serial = serialInput.value;
    serialStoreEdit.set(sectionId, edit);
  });
  const serialTools = document.createElement("div");
  serialTools.className = "serial-store-serial-tools";
  const newBtn = document.createElement("button");
  newBtn.type = "button";
  newBtn.className = "secondary";
  newBtn.textContent = "New";
  newBtn.title = "Clear the box to add another code";
  newBtn.addEventListener("click", () => {
    serialStoreEdit.set(sectionId, { id: "", name: "", group: "Default", serial: "" });
    renderSerialStoreForm(sectionId);
    actionMessage.className = "action-message muted";
    actionMessage.textContent = "New — pick Add to pack (or New pack…), paste codes, then Save.";
  });
  const convertBtn = document.createElement("button");
  convertBtn.type = "button";
  convertBtn.className = "secondary";
  convertBtn.textContent = "Convert";
  convertBtn.title = "Convert human ↔ @U in this box (same as the old Convert serials tool)";
  convertBtn.addEventListener("click", async () => {
    const raw = String(serialInput.value || "").trim();
    if (!raw) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = "Paste a serial into the Serial box first.";
      return;
    }
    actionMessage.className = "action-message muted";
    actionMessage.textContent = "Converting…";
    try {
      const { data } = await window.sqbt.postAction("serial_convert", { input: raw });
      if (data?.ok === false) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = data?.message || "Convert failed.";
        return;
      }
      const results = Array.isArray(data?.results) ? data.results : [];
      let next = "";
      if (results.length > 1) {
        next = results.map((row) => row.serial || row.human || "").filter(Boolean).join("\n");
      } else if (data?.serial) {
        next = String(data.serial);
      } else if (data?.human && raw.startsWith("@U")) {
        next = String(data.human);
      } else {
        next = String(data?.message || raw);
      }
      serialInput.value = next;
      const edit = serialStoreEdit.get(sectionId) || {};
      edit.serial = next;
      serialStoreEdit.set(sectionId, edit);
      actionMessage.className = "action-message ok";
      actionMessage.textContent = data?.message || "Converted.";
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error);
    }
  });
  serialTools.append(newBtn, convertBtn);
  serialWrap.append(serialInput, serialTools);

  form.append(nameWrap, groupWrap, serialWrap);
  sectionEl.appendChild(form);
  renderSerialStoreForm(sectionId);

  const shareBar = document.createElement("div");
  shareBar.className = "serial-store-share-bar";
  shareBar.innerHTML =
    "<span class='muted small'>Pick Add to pack → paste codes → Save. Pack Add selects that pack. Send @lvl mails releveled. Import merges; Export shares.</span>";
  sectionEl.appendChild(shareBar);

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
        label: "Pack",
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
  const hasWideField = fields.some(
    (field) => field.type === "textarea" || field.wide || field.key === "serials"
  );
  const landHeavy = fields.some((field) =>
    [
      "shape",
      "fill_until_complete",
      "spawn_then_shape",
      "drop_height",
      "radius",
      "spacing",
      "line_length",
      "z_bias",
      "stay_in_air",
    ].includes(String(field.key || ""))
  );
  // Tall land/shape cards must span the row — half-width left empty "missing button" holes.
  if (hasWideField || landHeavy || fields.length >= 5 || actionDef.fullWidth) {
    card.classList.add("action-card-full");
  }

  if (featured && fields.length) {
    const title = document.createElement("h4");
    title.className = "action-card-title";
    title.textContent = actionDef.label;
    card.appendChild(title);
  }
  if (fields.length) {
    const fieldsWrap = document.createElement("div");
    fieldsWrap.className = "fields-grid action-fields";
    if (actionDef.action === "max_all") {
      fieldsWrap.classList.add("max-all-fields");
      card.classList.add("action-card-full");
    }
    if (hasWideField) {
      fieldsWrap.classList.add("fields-grid-serials");
    }
    let activeFold = null;
    let activeFoldGrid = null;
    for (const field of fields) {
      const foldName = String(field.field_fold || "").trim();
      let target = fieldsWrap;
      if (foldName) {
        if (!activeFold || activeFold.dataset.foldName !== foldName) {
          activeFold = document.createElement("details");
          activeFold.className = "field-fold";
          activeFold.dataset.foldName = foldName;
          const summary = document.createElement("summary");
          summary.textContent = foldName;
          activeFoldGrid = document.createElement("div");
          activeFoldGrid.className = "fields-grid field-fold-grid";
          activeFold.append(summary, activeFoldGrid);
          fieldsWrap.appendChild(activeFold);
        }
        target = activeFoldGrid;
      } else {
        activeFold = null;
        activeFoldGrid = null;
      }
      const node = renderField(sectionId, actionDef, field, sectionEl, fields);
      if (node) target.appendChild(node);
    }
    card.appendChild(fieldsWrap);
  }

  const isToggle = String(actionDef.type || "").toLowerCase() === "toggle";
  const button = document.createElement("button");
  button.type = "button";
  if (actionDef.tooltip) {
    button.title = actionDef.tooltip;
  }
  button.dataset.runAction = actionDef.action;

  if (isToggle) {
    button.dataset.sectionId = sectionId;
    button.dataset.toggleLabel = actionDef.label;
    if (actionDef.sticky) button.dataset.stickyToggle = "1";
    if (actionDef.syncKey) button.dataset.syncKey = actionDef.syncKey;
    paintToggleButton(button, actionDef, initialToggleOn(sectionId, actionDef));
    button.addEventListener("click", () => {
      const currentlyOn = button.dataset.toggleOn === "1";
      const nextOn = !currentlyOn;
      const base = collectPayload(sectionId, actionDef);
      const flip = nextOn
        ? { ...(actionDef.payloadOn || { enabled: true }) }
        : { ...(actionDef.payloadOff || { enabled: false }) };
      const payload = { ...base, ...flip };
      const context = {
        sectionId,
        config: sectionEl.querySelector("[data-multiselect-config]")?.dataset.multiselectConfig
          ? JSON.parse(sectionEl.querySelector("[data-multiselect-config]").dataset.multiselectConfig)
          : { catalog: "serial_store" },
      };
      paintToggleButton(button, actionDef, nextOn);
      if (actionDef.syncKey) {
        syncMobilityToggleButtons(actionDef.syncKey, nextOn);
      }
      if (actionDef.sticky) writeStickyToggle(toggleStickyKey(sectionId, actionDef), nextOn);
      runAction(actionDef.action, payload, actionDef.confirm || "", context);
    });
  } else {
    decorateActionButton(
      button,
      actionDef.action === "max_all" && featured && fields.length
        ? "Run MAX ALL"
        : featured && fields.length
          ? "Run"
          : actionDef.label,
      actionDef
    );
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
  }
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

const TOGGLE_BOARD_ROWS = Object.freeze([
  ["god_mode", "God mode"],
  ["infinite_ammo", "Infinite ammo"],
  ["no_target", "No target"],
  ["ammo_regen", "Ammo regen x5"],
  ["weapons_restricted", "Weapons restricted"],
  ["force_fly", "Force fly (host)"],
  ["force_fly_all", "Force fly (all)"],
  ["infinite_jump", "Infinite jump"],
  ["infinite_jump_all", "Infinite jump (all)"],
  ["vehicle_jump", "Vehicle jump"],
  ["noclip", "Noclip"],
  ["fall_through_map", "Fall through map"],
  ["auto_apply", "Auto-apply on load"],
  ["shoot_sprint", "Shoot while sprinting"],
  ["zoom_sprint", "Zoom while sprinting"],
  ["zoom_injured", "Zoom while downed"],
  ["auto_revive", "Auto revive"],
  ["map_fog", "Hide map fog"],
  ["hold_session", "No main menu"],
]);

/** How Toggles-tab rows map to bridge actions. null = not clickable. */
const TOGGLE_BOARD_ACTIONS = Object.freeze({
  god_mode: {
    action: "god_mode",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  infinite_ammo: {
    action: "infinite_ammo",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  no_target: {
    action: "pawn_no_target",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  ammo_regen: {
    action: "ammo_regen",
    payloadOn: { rate: 5.0 },
    payloadOff: { rate: 0.0 },
  },
  weapons_restricted: {
    action: "weapons_restricted",
    payloadOn: { restricted: true },
    payloadOff: { restricted: false },
  },
  force_fly: {
    action: "mobility_force_fly",
    payloadOn: { enabled: true, scope: "target" },
    payloadOff: { enabled: false, scope: "target" },
  },
  force_fly_all: {
    action: "mobility_force_fly",
    payloadOn: { enabled: true, scope: "all" },
    payloadOff: { enabled: false, scope: "all" },
  },
  infinite_jump: {
    action: "mobility_infinite_jump",
    payloadOn: { enabled: true, scope: "target" },
    payloadOff: { enabled: false, scope: "target" },
  },
  infinite_jump_all: {
    action: "mobility_infinite_jump",
    payloadOn: { enabled: true, scope: "all" },
    payloadOff: { enabled: false, scope: "all" },
  },
  vehicle_jump: {
    action: "bvm_vehicle_jump",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  noclip: {
    action: "mobility_noclip",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  fall_through_map: {
    action: "faafo_fall_through_map",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  auto_apply: {
    action: "mobility_auto_apply",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  shoot_sprint: {
    action: "character_flag",
    payloadOn: { flag: "shoot_sprint", enabled: true },
    payloadOff: { flag: "shoot_sprint", enabled: false },
  },
  zoom_sprint: {
    action: "character_flag",
    payloadOn: { flag: "zoom_sprint", enabled: true },
    payloadOff: { flag: "zoom_sprint", enabled: false },
  },
  zoom_injured: {
    action: "character_flag",
    payloadOn: { flag: "zoom_injured", enabled: true },
    payloadOff: { flag: "zoom_injured", enabled: false },
  },
  auto_revive: {
    action: "character_flag",
    payloadOn: { flag: "auto_revive", enabled: true },
    payloadOff: { flag: "auto_revive", enabled: false },
  },
  map_fog: {
    action: "map_fog_hide",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  hold_session: {
    action: "hold_session",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
});

function patchStickyToggleLocal(key, on) {
  if (!latestStatus) latestStatus = {};
  if (!latestStatus.sticky_toggles || typeof latestStatus.sticky_toggles !== "object") {
    latestStatus.sticky_toggles = {};
  }
  latestStatus.sticky_toggles[key] = Boolean(on);
  if (latestStatus.raw && typeof latestStatus.raw === "object") {
    if (!latestStatus.raw.sticky_toggles || typeof latestStatus.raw.sticky_toggles !== "object") {
      latestStatus.raw.sticky_toggles = {};
    }
    latestStatus.raw.sticky_toggles[key] = Boolean(on);
  }
}

function renderTogglesBoard(sectionEl) {
  const host = document.createElement("div");
  host.className = "toggles-board";
  host.id = "toggles-board";
  sectionEl.appendChild(host);
  fillTogglesBoard();
}

function fillTogglesBoard() {
  const host = document.getElementById("toggles-board");
  if (!host) return;
  const sticky = latestStatus?.sticky_toggles || latestStatus?.raw?.sticky_toggles || {};
  host.innerHTML = "";
  const list = document.createElement("ul");
  list.className = "toggles-board-list";
  let anyOn = false;
  for (const [key, label] of TOGGLE_BOARD_ROWS) {
    const on = Boolean(sticky[key]);
    if (on) anyOn = true;
    const spec = TOGGLE_BOARD_ACTIONS[key];
    const row = document.createElement("li");
    row.className = on ? "toggles-board-row is-on" : "toggles-board-row is-off";
    if (!spec) {
      row.classList.add("is-disabled");
      row.title = "Party-wide Force fly is disabled (unreliable). Use Infinite jump (all).";
    } else {
      row.classList.add("is-clickable");
      row.title = on ? `Click to turn ${label} OFF` : `Click to turn ${label} ON`;
      row.tabIndex = 0;
      row.setAttribute("role", "button");
      row.addEventListener("click", () => toggleBoardRow(key, label, !on));
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggleBoardRow(key, label, !on);
        }
      });
    }
    const name = document.createElement("span");
    name.className = "toggles-board-name";
    name.textContent = label;
    const state = document.createElement("span");
    state.className = "toggles-board-state";
    if (!spec) {
      state.textContent = "N/A";
    } else {
      state.textContent = on ? "ON" : "OFF";
    }
    row.append(name, state);
    list.appendChild(row);
  }
  host.appendChild(list);
  const note = document.createElement("p");
  note.className = "muted small";
  const speed = sticky.fly_speed;
  const preset = sticky.fly_preset;
  const extra = [];
  if (preset) extra.push(`Fly preset: ${preset}`);
  if (speed != null && speed !== "") extra.push(`Fly speed: ${speed}`);
  extra.push(anyOn ? "Click a row to toggle." : "All listed sticky boosts are off — click a row to enable.");
  note.textContent = extra.join(" · ");
  host.appendChild(note);
}

let toggleBoardBusy = false;
async function toggleBoardRow(key, label, wantOn) {
  if (toggleBoardBusy) return;
  const spec = TOGGLE_BOARD_ACTIONS[key];
  if (!spec) return;
  toggleBoardBusy = true;
  actionMessage.className = "action-message muted";
  actionMessage.textContent = `${wantOn ? "Enabling" : "Disabling"} ${label}…`;
  try {
    const payload = wantOn ? { ...spec.payloadOn } : { ...spec.payloadOff };
    await runAction(spec.action, payload, "", {});
    patchStickyToggleLocal(key, wantOn);
    if (key === "force_fly" || key === "infinite_jump" || key === "infinite_jump_all" || key === "noclip" || key === "map_fog" || key === "hold_session") {
      syncMobilityToggleButtons(key, wantOn);
    } else {
      syncMobilityToggleButtons(key, wantOn);
    }
    if (key === "force_fly") syncMobilityToggleButtons("force_fly_all", false);
    fillTogglesBoard();
  } catch (error) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = String(error?.message || error);
  } finally {
    toggleBoardBusy = false;
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
  const isWhatsNewCollapsible =
    Array.isArray(section.whats_new) && section.whats_new.length && section.whats_new_collapsible;

  if (isWhatsNewCollapsible) {
    sectionEl.classList.add("panel-section-whats-new");
    const details = document.createElement("details");
    details.className = "whats-new-collapsible";
    const summary = document.createElement("summary");
    summary.className = "whats-new-trigger";
    const ver = String(manifest?.version || "").trim();
    summary.textContent = ver ? `What's new · v${ver}` : "What's new";
    const body = document.createElement("div");
    body.className = "whats-new-body";
    const whatsList = document.createElement("ul");
    whatsList.className = "whats-new-list";
    for (const note of section.whats_new) {
      const li = document.createElement("li");
      li.textContent = String(note);
      whatsList.appendChild(li);
    }
    body.appendChild(whatsList);
    details.append(summary, body);
    sectionEl.appendChild(details);
    return sectionEl;
  }

  if (section.title === "Most used" || section.title === "Essentials" || section.featured) {
    sectionEl.classList.add("panel-section-featured");
  }
  if (section.title === "Most used" || section.title === "Essentials") {
    sectionEl.classList.add("panel-section-most-used");
  }
  const aura = String(section.aura || "").trim().toLowerCase();
  if (aura) {
    sectionEl.dataset.aura = aura;
    sectionEl.classList.add("panel-section-aura", `panel-section-aura-${aura}`);
  }
  const sectionId = sectionKey(tabId, section);
  sectionEl.dataset.sectionId = sectionId;
  if (section.title) sectionEl.dataset.sectionTitle = String(section.title);
  const heading = document.createElement("h3");
  heading.textContent = section.title;
  sectionEl.appendChild(heading);
  if (tabId === "serials") {
    sectionEl.dataset.serialsSegment = serialsSegmentForSection(section);
  }

  if (Array.isArray(section.whats_new) && section.whats_new.length) {
    const whatsNew = document.createElement("div");
    whatsNew.className = "whats-new-box";
    const showInnerTitle = String(section.title || "").trim().toLowerCase() !== "what's new";
    if (showInnerTitle) {
      const whatsTitle = document.createElement("p");
      whatsTitle.className = "whats-new-title";
      whatsTitle.textContent = "What's new";
      whatsNew.appendChild(whatsTitle);
    }
    const whatsList = document.createElement("ul");
    whatsList.className = "whats-new-list";
    for (const note of section.whats_new) {
      const li = document.createElement("li");
      li.textContent = String(note);
      whatsList.appendChild(li);
    }
    whatsNew.appendChild(whatsList);
    sectionEl.appendChild(whatsNew);
  }

  if (Array.isArray(section.guide) && section.guide.length) {
    const guide = document.createElement("ol");
    guide.className = "section-guide";
    for (const step of section.guide) {
      const item = document.createElement("li");
      item.textContent = String(step);
      guide.appendChild(item);
    }
    sectionEl.appendChild(guide);
  }

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

  if (Array.isArray(section.quickLinks) && section.quickLinks.length) {
    const links = document.createElement("div");
    links.className = "action-grid action-grid-featured home-quick-links";
    for (const row of section.quickLinks) {
      const tabId = String(row.tab || "").trim();
      const label = String(row.label || tabId).trim();
      if (!tabId || !label) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "home-quick-link";
      decorateActionButton(button, label, { action: `nav:${tabId}` });
      button.title = `Open ${tabId} tab`;
      button.addEventListener("click", () => {
        activeTabId = tabId;
        if (tabId === "serials" && row.segment) {
          writeSerialsSegment(String(row.segment));
        }
        renderTabs();
        const current = manifest.tabs.find((item) => item.id === activeTabId);
        if (current) renderTab(current);
      });
      links.appendChild(button);
    }
    if (links.childElementCount) sectionEl.appendChild(links);
  }

  if (section.danger) {
    // Only the Home safety card should vanish after Got it — never blank other sections.
    if (String(section.title || "") === "Before you boost" && safetyBannerDismissed()) {
      return null;
    }
    if (String(section.title || "") === "Before you boost") {
      const wrap = document.createElement("div");
      wrap.className = "section-danger-wrap";
      const danger = document.createElement("p");
      danger.className = "section-danger small";
      danger.textContent = section.danger;
      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.className = "section-danger-dismiss";
      dismiss.textContent = "Got it";
      dismiss.title = "Dismiss this reminder";
      dismiss.addEventListener("click", () => {
        dismissSafetyBanner();
        const sectionRoot = wrap.closest(".panel-section");
        wrap.remove();
        if (sectionRoot) sectionRoot.remove();
        renderSafetyBanner();
      });
      wrap.append(danger, dismiss);
      sectionEl.appendChild(wrap);
    } else {
      const danger = document.createElement("p");
      danger.className = "section-danger small";
      danger.textContent = section.danger;
      sectionEl.appendChild(danger);
    }
  } else if (section.title === "Before you boost" && safetyBannerDismissed()) {
    return null;
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
    if (section.fields.some((field) => field.key === "fly_speed_mode")) {
      const live = document.createElement("p");
      live.className = "fly-speed-live muted";
      live.dataset.flySpeedLive = "1";
      live.textContent =
        "Pick preset or type a number → Apply fly speed → turn Force fly ON → hold WASD.";
      sectionEl.appendChild(live);
      wireFlySpeedControls(sectionId);
      const sticky = latestStatus?.sticky_toggles || latestStatus?.raw?.sticky_toggles || {};
      if (sticky.fly_speed != null) {
        updateFlySpeedLivePanels(
          sticky.fly_speed,
          sticky.fly_preset,
          Boolean(sticky.force_fly || sticky.force_fly_all)
        );
      }
    }
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
  const fieldsSidebar = String(section.layout || "").trim() === "fields_sidebar";

  if (section.keybindsEditor) {
    renderKeybindsEditor(sectionEl);
    return sectionEl;
  }

  if (section.togglesBoard) {
    renderTogglesBoard(sectionEl);
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
  if (fieldsSidebar) {
    actionsWrap.className = "action-grid action-grid-fields-sidebar";
  } else {
    actionsWrap.className = featured ? "action-grid action-grid-featured" : "action-grid";
  }
  const sidebarWrap = fieldsSidebar ? document.createElement("div") : null;
  if (sidebarWrap) {
    sidebarWrap.className = "action-sidebar";
  }
  const fieldActionsWrap = featured ? document.createElement("div") : null;
  if (fieldActionsWrap) {
    fieldActionsWrap.className = "action-cards-stack";
  }
  const foldHosts = new Map();
  const foldOrder = [];
  const hostFor = (actionDef) => {
    const fold = String(actionDef.fold || "").trim();
    if (!fold) return actionsWrap;
    let rec = foldHosts.get(fold);
    if (!rec) {
      const details = document.createElement("details");
      details.className = "action-fold";
      const summary = document.createElement("summary");
      summary.textContent = fold;
      const hint = document.createElement("p");
      hint.className = "fold-hint muted small";
      hint.textContent =
        String(actionDef.foldHint || "").trim() ||
        "Build a list of mob packs, then start them so they spawn one group after another.";
      const inner = document.createElement("div");
      inner.className = featured ? "action-grid action-grid-featured" : "action-grid";
      details.append(summary, hint, inner);
      rec = { details, inner };
      foldHosts.set(fold, rec);
      foldOrder.push(rec);
    }
    return rec.inner;
  };
  const placeCard = (card, actionDef, host) => {
    if (fieldsSidebar && sidebarWrap && !(actionDef.fields || []).length) {
      sidebarWrap.appendChild(card);
      return;
    }
    host.appendChild(card);
  };
  let partyBaySendRow = null;

  for (const actionDef of section.actions || []) {
    const actionHost = hostFor(actionDef);
    if (section.multiselect || section.serialStore || section.serialSendList) {
      const button = document.createElement("button");
      button.type = "button";
      decorateActionButton(button, actionDef.label, actionDef);
      if (actionDef.tooltip) button.title = actionDef.tooltip;
      button.dataset.runAction = actionDef.action;
      button.addEventListener("click", async () => {
        const context = {
          sectionId,
          config: section.multiselect || { catalog: section.serialSendList ? "serial_send_list" : "serial_store" },
        };
        if (actionDef.importSerialFile) {
          try {
            actionMessage.className = "action-message muted";
            actionMessage.textContent = "Opening file…";
            const result = await window.sqbt.pickSerialFile();
            if (result?.cancelled) {
              actionMessage.className = "action-message muted";
              actionMessage.textContent = "File pick cancelled.";
              return;
            }
            if (!result?.ok) {
              actionMessage.className = "action-message error";
              actionMessage.textContent = result?.message || "Could not read that file.";
              return;
            }
            const text =
              String(result.text || "").trim() ||
              (Array.isArray(result.serials) ? result.serials.join("\n") : "");
            if (!text) {
              actionMessage.className = "action-message error";
              actionMessage.textContent = result?.message || "No serials found in that file.";
              return;
            }
            const payload = {
              ...(actionDef.payload || {}),
              text,
              group: "Import",
              source_name: result.path ? String(result.path).split(/[/\\]/).pop() : "",
              filename: result.path ? String(result.path).split(/[/\\]/).pop() : "",
            };
            runAction(actionDef.action, payload, actionDef.confirm || "", context);
          } catch (error) {
            actionMessage.className = "action-message error";
            actionMessage.textContent = String(error?.message || error || "File pick failed.");
          }
          return;
        }
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
              let num = Number(value);
              if (!Number.isFinite(num)) num = Number(field.default) || 0;
              if (field.min != null) num = Math.max(Number(field.min), num);
              if (field.max != null) num = Math.min(Number(field.max), num);
              payload[field.key] = num;
              continue;
            }
            payload[field.key] = value;
          }
        }
        runAction(actionDef.action, payload, actionDef.confirm || "", context);
      });
      // For send-list, also render field controls (Send to / amount / etc.).
      if (section.serialSendList && (actionDef.fields || []).length) {
        const card = document.createElement("div");
        card.className = "action-card action-card-full";
        if (actionDef.deliverFromPaste) {
          card.classList.add("serial-send-primary-card");
        } else {
          card.classList.add("deliver-selected-card");
        }
        if (actionDef.deliverFromPaste) {
          const tip = document.createElement("p");
          tip.className = "serial-send-primary-tip";
          tip.textContent =
            "Send options — Send to matches Boost target (top bar). Change either and both update.";
          card.appendChild(tip);
        }
        const fieldsWrap = document.createElement("div");
        fieldsWrap.className = "fields-grid action-fields";
        for (const field of actionDef.fields || []) {
          const node = renderField(sectionId, actionDef, field, sectionEl, actionDef.fields);
          if (node) fieldsWrap.appendChild(node);
        }
        card.appendChild(fieldsWrap);
        const primarySlot = sectionEl.querySelector(
          `.serial-send-primary-slot[data-serial-send-primary="${sectionId}"]`
        );
        const sendBtnSlot = sectionEl.querySelector(
          `.serial-send-btn-slot[data-serial-send-btn="${sectionId}"]`
        );
        if (actionDef.deliverFromPaste && primarySlot) {
          primarySlot.appendChild(card);
          if (sendBtnSlot) {
            button.classList.add("serial-send-primary-btn");
            sendBtnSlot.appendChild(button);
          } else {
            button.classList.add("serial-send-primary-btn");
            card.appendChild(button);
          }
        } else if (actionDef.deliverMultiselect) {
          card.appendChild(button);
          const queueFold = sectionEl.querySelector(".serial-queue-fold");
          if (queueFold) queueFold.appendChild(card);
          else actionHost.appendChild(card);
        } else {
          card.appendChild(button);
          actionHost.appendChild(card);
        }
      } else if (
        actionDef.deliverMultiselect ||
        actionDef.deliverStore ||
        actionDef.spawnMultiselect ||
        actionDef.backpackMultiselect ||
        actionDef.packBayCopy ||
        actionDef.addSelectedToLibrary ||
        (actionDef.fields || []).length
      ) {
        const card = document.createElement("div");
        card.className = "action-card deliver-selected-card";
        if ((actionDef.fields || []).some((field) => field.type === "textarea" || field.wide || field.key === "serials")) {
          card.classList.add("action-card-full");
        }        if (actionDef.deliverMultiselect || actionDef.deliverStore) {
          const tip = document.createElement("p");
          tip.className = "muted small";
          tip.textContent =
            "Tick rows above, choose Send to. Open rewards defaults to Yes so mail appears; set No if you want it to stay pending.";
          card.appendChild(tip);
        }
        if (actionDef.backpackMultiselect && actionDef.action === "backpack_relevel_selected") {
          const tip = document.createElement("p");
          tip.className = "muted small";
          tip.textContent = "Tick rows above, set New item level, then try rewrite.";
          card.appendChild(tip);
        } else if (actionDef.backpackMultiselect && actionDef.action === "backpack_export_txt") {
          const tip = document.createElement("p");
          tip.className = "muted small";
          tip.textContent = "Tick rows to export, or leave none ticked for the full last Snap.";
          card.appendChild(tip);
        }
        if (actionDef.addSelectedToLibrary) {
          const tip = document.createElement("p");
          tip.className = "muted small";
          const bayName =
            activeTabId === "pack_bay" ? "Save Pack" : activeTabId === "party_bay" ? "Live Pack" : "bay";
          tip.textContent = `Tick ${bayName} rows above, then add their @U codes into My packs.`;
          card.appendChild(tip);
        }
        if (actionDef.packBayCopy && actionDef.action === "deliver_serials") {
          const tip = document.createElement("p");
          tip.className = "muted small";
          const mailSelf = Boolean(actionDef.payload?.mail_to_self) || activeTabId === "pack_bay";
          tip.textContent = mailSelf
            ? "Tick Save Pack rows above, then mail those @U codes to yourself."
            : "Tick Live Pack rows above, choose Send to, then mail.";
          card.appendChild(tip);
        } else if (actionDef.packBayCopy && actionDef.action === "pack_bay_open_toolbox") {
          const tip = document.createElement("p");
          tip.className = "muted small";
          tip.textContent =
            "Tick rows to copy @U first, then Scooter's Toolbox opens in your browser — paste there to deep-edit.";
          card.appendChild(tip);
        } else if (actionDef.packBayCopy) {
          const tip = document.createElement("p");
          tip.className = "muted small";
          tip.textContent = "Tick bay rows above, then copy their @U codes to the clipboard.";
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
        // Party Bay: keep Rewrite beside Send-to (same row).
        if (
          activeTabId === "party_bay" &&
          actionDef.packBayCopy &&
          actionDef.action === "deliver_serials"
        ) {
          partyBaySendRow = document.createElement("div");
          partyBaySendRow.className = "bay-pair-row";
          partyBaySendRow.appendChild(card);
          actionHost.appendChild(partyBaySendRow);
        } else if (
          activeTabId === "party_bay" &&
          actionDef.action === "backpack_relevel_selected" &&
          partyBaySendRow
        ) {
          partyBaySendRow.appendChild(card);
          partyBaySendRow = null;
        } else {
          actionHost.appendChild(card);
        }
      } else {
        actionHost.appendChild(button);
      }
    } else if (featured && String(actionDef.type || "").toLowerCase() === "toggle" && (actionDef.fields || []).length > 0) {
      fieldActionsWrap.appendChild(renderActionCard(sectionId, actionDef, sectionEl, featured));
    } else if (featured && String(actionDef.type || "").toLowerCase() === "toggle") {
      const button = document.createElement("button");
      button.type = "button";
      if (actionDef.tooltip) button.title = actionDef.tooltip;
      button.dataset.runAction = actionDef.action;
      button.dataset.sectionId = sectionId;
      button.dataset.toggleLabel = actionDef.label;
      if (actionDef.sticky) button.dataset.stickyToggle = "1";
      if (actionDef.syncKey) button.dataset.syncKey = actionDef.syncKey;
      paintToggleButton(button, actionDef, initialToggleOn(sectionId, actionDef));
      button.addEventListener("click", () => {
        const currentlyOn = button.dataset.toggleOn === "1";
        const nextOn = !currentlyOn;
        const base = collectPayload(sectionId, actionDef);
        const flip = nextOn
          ? { ...(actionDef.payloadOn || { enabled: true }) }
          : { ...(actionDef.payloadOff || { enabled: false }) };
        paintToggleButton(button, actionDef, nextOn);
        if (actionDef.syncKey) {
          syncMobilityToggleButtons(actionDef.syncKey, nextOn);
        }
        if (actionDef.sticky) writeStickyToggle(toggleStickyKey(sectionId, actionDef), nextOn);
        runAction(actionDef.action, { ...base, ...flip }, actionDef.confirm || "", { sectionId });
      });
      actionHost.appendChild(button);
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
      if (fieldsSidebar && sidebarWrap) {
        const card = document.createElement("div");
        card.className = "action-card";
        card.appendChild(button);
        sidebarWrap.appendChild(card);
      } else {
        actionHost.appendChild(button);
      }
    } else {
      placeCard(renderActionCard(sectionId, actionDef, sectionEl, featured), actionDef, actionHost);
    }
  }
  if (sidebarWrap && sidebarWrap.childElementCount > 0) {
    actionsWrap.appendChild(sidebarWrap);
  }
  if (actionsWrap.childElementCount > 0) {
    sectionEl.appendChild(actionsWrap);
  }
  for (const rec of foldOrder) {
    sectionEl.appendChild(rec.details);
  }
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
    // Hide Home "Start here" only when actions unlock (main menu Online is not enough).
    if (String(section.title || "") === "Start here" && actionsEnabled()) {
      continue;
    }
    const sectionEl = renderSection(section, tab.id);
    if (sectionEl) tabContent.appendChild(sectionEl);
  }
  if (tab.id === "serials") {
    const nav = renderSerialsSegmentNav();
    tabContent.prepend(nav);
    applySerialsSegment(readSerialsSegment());
  }
  // Keep the global #sqbt-progress-panel; refresh visibility from cache.
  renderProgressPanel(null, null, null);
  if (actionsEnabled()) {
    const progressBusy =
      isChallengeBusy(lastChallengeStatus) ||
      isUvhmBusy(lastUvhmStatus) ||
      isSpawnAllBusy(lastSpawnAllStatus) ||
      isSerialDeliveryBusy(lastSerialDeliveryStatus) ||
      isAutoLobbyBusy(lastAutoLobbyStatus) ||
      isShapeBusy(lastShapeStatus) ||
      isVacuumBusy(lastVacuumStatus);
    if (
      progressBusy ||
      tab.id === "progression" ||
      tab.id === "loot" ||
      tab.id === "serials" ||
      tab.id === "auto_lobby"
    ) {
      pollProgressOnce();
    }
    if (tab.id === "auto_lobby" && actionsEnabled()) {
      prefillAutoLobbyFields();
    }
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
  if (tab.id === "toggles") {
    fillTogglesBoard();
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

function renderSafetyBanner() {
  const el = document.getElementById("safety-banner");
  const textEl = document.getElementById("safety-banner-text");
  const dismissBtn = document.getElementById("safety-banner-dismiss");
  if (!el) return;
  const text = String(manifest?.safety_banner || "").trim();
  if (!text || safetyBannerDismissed()) {
    el.classList.add("hidden");
    if (textEl) textEl.textContent = "";
    return;
  }
  el.classList.remove("hidden");
  if (textEl) textEl.textContent = text;
  else el.textContent = text;
  if (dismissBtn && !dismissBtn.dataset.bound) {
    dismissBtn.dataset.bound = "1";
    dismissBtn.addEventListener("click", () => {
      dismissSafetyBanner();
      renderSafetyBanner();
      if (activeTabId === "home" && manifest?.tabs?.length) {
        const current = manifest.tabs.find((row) => row.id === activeTabId);
        if (current) renderTab(current);
      }
    });
  }
}

const SAFETY_BANNER_DISMISS_KEY = "sqbt.safetyBannerDismissed";

function safetyBannerDismissed() {
  try {
    return localStorage.getItem(SAFETY_BANNER_DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

function dismissSafetyBanner() {
  try {
    localStorage.setItem(SAFETY_BANNER_DISMISS_KEY, "1");
  } catch {
    /* ignore */
  }
}

function initNavModeControls() {
  const tabsBtn = document.getElementById("nav-mode-tabs");
  const menuBtn = document.getElementById("nav-mode-menu");
  const burger = document.getElementById("nav-burger-btn");
  if (tabsBtn && !tabsBtn.dataset.bound) {
    tabsBtn.dataset.bound = "1";
    tabsBtn.addEventListener("click", () => setNavMode("tabs"));
  }
  if (menuBtn && !menuBtn.dataset.bound) {
    menuBtn.dataset.bound = "1";
    menuBtn.addEventListener("click", () => setNavMode("menu"));
  }
  if (burger && !burger.dataset.bound) {
    burger.dataset.bound = "1";
    burger.addEventListener("click", () => {
      navDrawerOpen = !navDrawerOpen;
      applyNavMode();
    });
  }
  applyNavMode();
}

function applyNavMode() {
  document.body.classList.toggle("nav-mode-menu", navMode === "menu");
  document.body.classList.toggle("nav-mode-tabs", navMode !== "menu");
  const chrome = document.querySelector(".nav-chrome");
  if (chrome) {
    chrome.classList.toggle("nav-mode-menu", navMode === "menu");
    chrome.classList.toggle("nav-mode-tabs", navMode !== "menu");
  }
  const tabsBtn = document.getElementById("nav-mode-tabs");
  const menuBtn = document.getElementById("nav-mode-menu");
  const burger = document.getElementById("nav-burger-btn");
  const drawer = document.getElementById("nav-drawer");
  if (tabsBtn) tabsBtn.classList.toggle("active", navMode !== "menu");
  if (menuBtn) menuBtn.classList.toggle("active", navMode === "menu");
  if (tabBar) {
    const hideTabs = navMode === "menu";
    tabBar.classList.toggle("nav-tabs-hidden", hideTabs);
    tabBar.style.display = hideTabs ? "none" : "";
  }
  if (burger) {
    burger.classList.toggle("hidden", navMode !== "menu");
    burger.setAttribute("aria-expanded", navDrawerOpen && navMode === "menu" ? "true" : "false");
  }
  if (drawer) {
    const show = navMode === "menu" && navDrawerOpen;
    drawer.classList.toggle("hidden", !show);
  }
}

function setNavMode(mode) {
  navMode = mode === "menu" ? "menu" : "tabs";
  try {
    localStorage.setItem(NAV_MODE_KEY, navMode);
  } catch (_) {
    /* ignore */
  }
  // Menu mode: hide tabs and open the drawer immediately.
  navDrawerOpen = navMode === "menu";
  applyNavMode();
  renderTabs();
}

function renderTabs() {
  initNavModeControls();
  tabBar.innerHTML = "";
  const drawer = document.getElementById("nav-drawer");
  if (drawer) drawer.innerHTML = "";
  if (!manifest?.tabs?.length) {
    const needsSetup = setupNeedsUserAction();
    tabContent.innerHTML = needsSetup
      ? `<div class="panel-section panel-section-featured">
      <h3>${t("waiting.game")}</h3>
      <ol class="section-guide">
        <li>${t("waiting.setup1")}</li>
        <li>${t("waiting.setup2")}</li>
        <li>${t("waiting.setup3")}</li>
        <li>${t("waiting.setup4")}</li>
      </ol>
    </div>`
      : `<div class="panel-section panel-section-featured">
      <h3>${t("waiting.game")}</h3>
      <ol class="section-guide">
        <li>${t("waiting.auto1")}</li>
        <li>${t("waiting.auto2")}</li>
        <li>${t("waiting.auto3")}</li>
        <li>${t("waiting.auto4")}</li>
      </ol>
    </div>`;
    return;
  }
  for (const tab of manifest.tabs) {
    if (tab.hidden) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.tabId = tab.id;
    setIconLabel(button, i18n.tabLabel(tab), TAB_ICONS[tab.id] || "");
    button.className = tab.id === activeTabId ? "active" : "";
    button.addEventListener("click", () => {
      activeTabId = tab.id;
      renderTabs();
      const current = manifest.tabs.find((row) => row.id === activeTabId);
      if (current) renderTab(current);
    });
    tabBar.appendChild(button);
    if (drawer) {
      const item = document.createElement("button");
      item.type = "button";
      item.dataset.navDrawerItem = "1";
      item.dataset.tabId = tab.id;
      setIconLabel(item, i18n.tabLabel(tab), TAB_ICONS[tab.id] || "");
      item.className = tab.id === activeTabId ? "active" : "";
      item.addEventListener("click", () => {
        activeTabId = tab.id;
        navDrawerOpen = false;
        renderTabs();
        const current = manifest.tabs.find((row) => row.id === activeTabId);
        if (current) renderTab(current);
      });
      drawer.appendChild(item);
    }
  }
  applyNavMode();
  const visibleTabs = (manifest?.tabs || []).filter((tab) => !tab.hidden);
  let current = visibleTabs.find((row) => row.id === activeTabId) || visibleTabs[0];
  if (current) {
    activeTabId = current.id;
  } else if (activeTabId === "backpack" || activeTabId === "pack_bay" || activeTabId === "party_bay") {
    activeTabId = "serials";
    current = visibleTabs.find((row) => row.id === "serials") || visibleTabs[0];
  }
  renderSafetyBanner();
  if (current) renderTab(current);
  injectHiddenShapeOptions();
}

/** Refresh tab / drawer labels without wiping the open tab (preserves input focus). */
function renderTabBarOnly() {
  if (!manifest?.tabs?.length || !tabBar) return;
  initNavModeControls();
  tabBar.innerHTML = "";
  const drawer = document.getElementById("nav-drawer");
  if (drawer) drawer.innerHTML = "";
  for (const tab of manifest.tabs) {
    if (tab.hidden) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.tabId = tab.id;
    setIconLabel(button, i18n.tabLabel(tab), TAB_ICONS[tab.id] || "");
    button.className = tab.id === activeTabId ? "active" : "";
    button.addEventListener("click", () => {
      activeTabId = tab.id;
      renderTabs();
      const current = manifest.tabs.find((row) => row.id === activeTabId);
      if (current) renderTab(current);
    });
    tabBar.appendChild(button);
    if (drawer) {
      const item = document.createElement("button");
      item.type = "button";
      item.dataset.navDrawerItem = "1";
      item.dataset.tabId = tab.id;
      setIconLabel(item, i18n.tabLabel(tab), TAB_ICONS[tab.id] || "");
      item.className = tab.id === activeTabId ? "active" : "";
      item.addEventListener("click", () => {
        activeTabId = tab.id;
        navDrawerOpen = false;
        renderTabs();
        const current = manifest.tabs.find((row) => row.id === activeTabId);
        if (current) renderTab(current);
      });
      drawer.appendChild(item);
    }
  }
  applyNavMode();
  renderSafetyBanner();
}

function buildToolSearchIndex() {
  const items = [];
  for (const tab of manifest?.tabs || []) {
    const tabLabel = String(tab.label || tab.id || "");
    for (const section of tab.sections || []) {
      const sectionTitle = String(section.title || "");
      for (const actionDef of section.actions || []) {
        const label = String(actionDef.label || "").trim();
        if (!label) continue;
        items.push({
          tabId: tab.id,
          tabLabel,
          sectionTitle,
          label,
          action: String(actionDef.action || ""),
          haystack: `${tabLabel} ${sectionTitle} ${label} ${actionDef.action || ""}`.toLowerCase(),
        });
      }
    }
  }
  return items;
}

function hideToolSearchResults() {
  if (!toolSearchResults) return;
  toolSearchResults.classList.add("hidden");
  toolSearchResults.innerHTML = "";
}

function renderToolSearchResults(query) {
  if (!toolSearchResults) return;
  const q = String(query || "").trim().toLowerCase();
  if (q.length < 2) {
    hideToolSearchResults();
    return;
  }
  const tokens = q.split(/\s+/).filter(Boolean);
  const matches = buildToolSearchIndex()
    .filter((row) => tokens.every((tok) => row.haystack.includes(tok)))
    .slice(0, 12);
  toolSearchResults.innerHTML = "";
  if (!matches.length) {
    const empty = document.createElement("p");
    empty.className = "muted small tool-search-empty";
    empty.textContent = t("search.none");
    toolSearchResults.appendChild(empty);
    toolSearchResults.classList.remove("hidden");
    return;
  }
  for (const row of matches) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tool-search-hit";
    btn.setAttribute("role", "option");
    btn.innerHTML = `<strong>${escapeHtml(row.label)}</strong><span class="muted small">${escapeHtml(
      `${row.tabLabel} · ${row.sectionTitle}`
    )}</span>`;
    btn.addEventListener("click", () => jumpToTool(row));
    toolSearchResults.appendChild(btn);
  }
  toolSearchResults.classList.remove("hidden");
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function jumpToTool(row) {
  if (!row?.tabId || !manifest?.tabs?.length) return;
  hideToolSearchResults();
  if (toolSearchInput) toolSearchInput.value = "";
  activeTabId = row.tabId;
  if (row.tabId === "serials") {
    const needle = `${row.sectionTitle || ""} ${row.label || ""}`.toLowerCase();
    if (row.segment && SERIALS_SEGMENTS.some((s) => s.id === String(row.segment))) {
      writeSerialsSegment(String(row.segment));
    } else if (/gzo|lootlemon|browse/.test(needle)) writeSerialsSegment("codes");
    else if (/library|my packs/.test(needle)) writeSerialsSegment("library");
    else if (/mail|pending|reward|shiny mail/.test(needle)) writeSerialsSegment("mail");
  }
  renderTabs();
  window.setTimeout(() => {
    const sectionEl = [...tabContent.querySelectorAll("[data-section-title]")].find(
      (node) => String(node.dataset.sectionTitle || "") === String(row.sectionTitle || "")
    );
    let target = null;
    if (row.action) {
      const buttons = sectionEl
        ? sectionEl.querySelectorAll(`[data-run-action="${CSS.escape(row.action)}"]`)
        : tabContent.querySelectorAll(`[data-run-action="${CSS.escape(row.action)}"]`);
      for (const btn of buttons) {
        const text = String(btn.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
        if (text.includes(String(row.label || "").toLowerCase()) || !row.label) {
          target = btn;
          break;
        }
      }
      if (!target && buttons.length) target = buttons[0];
    }
    if (!target) target = sectionEl;
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    const flashHost = target.closest(".action-card") || target;
    flashHost.classList.add("tool-search-flash");
    window.setTimeout(() => flashHost.classList.remove("tool-search-flash"), 1600);
  }, 40);
}

async function loadManifest() {
  const gen = ++manifestLoadGen;
  const result = await window.sqbt.getManifest();
  if (gen !== manifestLoadGen) return;
  if (!result.ok) {
    // Keep tools only through a brief Online blip — not while truly Offline.
    if (manifest?.tabs?.length && bridgeConnectedHeld()) {
      if (actionMessage) {
        actionMessage.className = "action-message muted";
        actionMessage.textContent = String(result.message || "").trim()
          ? `Tools list refresh skipped: ${result.message}`
          : "";
      }
      return;
    }
    clearToolsToWaiting(result.message);
    return;
  }
  // Do not paint the full tools UI until the bridge is Online in-game.
  if (!bridgeConnectedHeld()) {
    clearToolsToWaiting(t("waiting.manifestUnavailable"));
    return;
  }
  const focused = document.activeElement;
  const editing =
    focused &&
    tabContent?.contains(focused) &&
    (focused.matches?.("input, textarea, select") || focused.isContentEditable);
  manifest = result.manifest;
  // Never wipe the open tab mid-keystroke — that is the “can't edit fields” bug.
  if (editing) {
    renderTabBarOnly();
    return;
  }
  renderTabs();
  if (toolSearchInput?.value) renderToolSearchResults(toolSearchInput.value);
}

function setModSyncBanner(state, { kicker, title, detail, versions } = {}) {
  if (!modSyncBanner) return;
  const states = ["ok", "updated", "restart", "need-sdk", "need-path", "error"];
  for (const name of states) {
    modSyncBanner.classList.toggle(`is-${name}`, name === state);
  }
  modSyncBanner.dataset.state = state || "";
  if (modSyncKicker) modSyncKicker.textContent = kicker || t("sync.kicker");
  if (modSyncTitle) modSyncTitle.textContent = title || "";
  if (modSyncDetail) modSyncDetail.textContent = detail || "";
  if (modSyncVersions) {
    modSyncVersions.textContent = versions || "";
    modSyncVersions.classList.toggle("hidden", !versions);
  }
}

function formatModVersions(modSync) {
  if (!modSync?.bundledVersion && !modSync?.installedVersion) return "";
  const installed = modSync.installedVersion || t("sync.notInstalled");
  const bundled = modSync.bundledVersion || t("sync.unknown");
  if (modSync.installedVersion && modSync.bundledVersion && modSync.installedVersion === modSync.bundledVersion) {
    return t("sync.versionsMatch", { bundled });
  }
  return t("sync.versionsDiff", { installed, bundled });
}

function applyBaseSdkUi(baseSdk, modSync = null) {
  if (baseSdk) lastBaseSdk = baseSdk;
  if (modSync) lastModSync = modSync;
  const installed = Boolean(baseSdk?.installed);
  const belowMin = Boolean(baseSdk?.belowMin || baseSdk?.needsOak2_03);
  const updateAvailable = Boolean(baseSdk?.updateAvailable) || belowMin;
  const version = String(baseSdk?.version || "").trim();
  const latest = String(baseSdk?.latestVersion || "").trim();
  const minVersion = String(baseSdk?.minVersion || "0.3").trim();
  const hasGameRoot = Boolean(baseSdk?.gameRoot || gameRootInput.value);
  if (sdkStatusLine) {
    if (!hasGameRoot) {
      sdkStatusLine.textContent = t("sdk.pickFolder");
    } else if (!installed) {
      sdkStatusLine.textContent = t("sdk.notFound");
    } else if (belowMin) {
      sdkStatusLine.textContent = t("sdk.tooOld", {
        version: version || t("sync.unknown"),
        min: minVersion,
      });
    } else if (updateAvailable && latest) {
      sdkStatusLine.textContent = t("sdk.updateAvail", {
        tracked: version ? t("sdk.tracked", { version }) : "",
        latest,
      });
    } else {
      sdkStatusLine.textContent = t("sdk.installed", {
        tracked: version ? t("sdk.ver", { version }) : "",
        latest: latest ? t("sdk.latestBit", { latest }) : "",
      });
    }
  }
  if (installModBtn) {
    if (!installed || belowMin) {
      installModBtn.textContent = belowMin ? t("sdk.install03") : t("sdk.install");
      installModBtn.classList.add("primary");
      installModBtn.classList.remove("ghost");
    } else {
      installModBtn.textContent = t("sdk.forceReinstall");
      installModBtn.classList.remove("primary");
      installModBtn.classList.add("ghost");
    }
  }
  if (updateBaseSdkBtn) {
    const showUpdate = installed && (updateAvailable || belowMin);
    updateBaseSdkBtn.classList.toggle("hidden", !showUpdate);
    updateBaseSdkBtn.disabled = false;
    updateBaseSdkBtn.textContent = belowMin ? t("sdk.updateBase03") : t("sdk.updateBase");
  }
  if (setupAttention) {
    if (!hasGameRoot) {
      setupAttention.classList.remove("hidden");
      setupAttention.innerHTML = t("setup.attentionDrive");
    } else if (!installed) {
      setupAttention.classList.remove("hidden");
      setupAttention.innerHTML = t("setup.attentionFirst");
    } else if (belowMin) {
      setupAttention.classList.remove("hidden");
      setupAttention.innerHTML = t("setup.attentionOak", {
        min: minVersion,
        version: version || t("sync.unknown"),
      });
    } else {
      setupAttention.classList.add("hidden");
      setupAttention.innerHTML = "";
    }
  }
  if (!hasGameRoot) {
    setModSyncBanner("need-path", {
      kicker: t("sync.setFolderKicker"),
      title: t("sync.setFolderTitle"),
      detail: t("sync.setFolderDetail"),
      versions: formatModVersions(modSync),
    });
  } else if (!installed) {
    setModSyncBanner("need-sdk", {
      kicker: t("sync.sdkMissingKicker"),
      title: t("sync.sdkMissingTitle"),
      detail: t("sync.sdkMissingDetail"),
      versions: formatModVersions(modSync),
    });
  } else if (belowMin) {
    setModSyncBanner("need-sdk", {
      kicker: t("sync.oakRequiredKicker"),
      title: t("sync.oakRequiredTitle", { min: minVersion }),
      detail: t("sync.oakRequiredDetail"),
      versions: formatModVersions(modSync),
    });
  } else if (!modSync) {
    setModSyncBanner("ok", {
      kicker: t("sync.kicker"),
      title: t("sync.autoTitle"),
      detail: t("sync.autoDetail"),
      versions: "",
    });
  }
  // Only force the Setup panel open when the user still must act (path / oak2).
  if (!hasGameRoot || !installed || belowMin) {
    setupPinned = true;
    if (setupCard) setupCard.classList.remove("is-hidden");
    if (showSetupBtn) showSetupBtn.classList.add("hidden");
  } else if (updateAvailable) {
    // Base SDK update is optional — keep Setup reachable, do not force it open.
    if (showSetupBtn && setupCard?.classList.contains("is-hidden")) {
      showSetupBtn.classList.remove("hidden");
    }
  }
}

function applyModSyncUi(modSync, baseSdk = null) {
  if (modSync) lastModSync = modSync;
  const resolvedBase = baseSdk || lastBaseSdk;
  const hasGameRoot = Boolean(modSync?.gameRoot || gameRootInput.value);
  const versions = formatModVersions(modSync);

  if (!hasGameRoot) {
    hideModSyncNotice();
    setModSyncBanner("need-path", {
      kicker: t("sync.setFolderKicker"),
      title: t("sync.setFolderTitle"),
      detail: t("sync.setFolderDetail"),
      versions,
    });
    updateSetupVisibility({ gameRoot: "", baseSdk: resolvedBase });
    return;
  }

  if (resolvedBase && !resolvedBase.installed) {
    hideModSyncNotice();
    setModSyncBanner("need-sdk", {
      kicker: t("sync.sdkMissingKicker"),
      title: t("sync.sdkMissingTitle"),
      detail: t("sync.sdkMissingDetail"),
      versions,
    });
    updateSetupVisibility({ gameRoot: modSync.gameRoot || gameRootInput.value, baseSdk: resolvedBase });
    return;
  }

  if (modSync?.updated && modSync.ok) {
    setModSyncBanner(
      modSync.gameRunning ? "restart" : "updated",
      {
        kicker: modSync.gameRunning ? t("sync.restartKicker") : t("sync.updatedKicker"),
        title: modSync.gameRunning
          ? t("sync.gameOpenTitle")
          : t("sync.nowVersionTitle", { version: modSync.bundledVersion || "bundled" }),
        detail: modSync.gameRunning ? t("sync.gameOpenDetail") : t("sync.copiedDetail"),
        versions,
      }
    );
    showModSyncNotice(modSync.gameRunning ? "restart" : "updated", {
      kicker: modSync.gameRunning ? t("sync.restartKicker") : t("sync.updatedKicker"),
      title: modSync.gameRunning
        ? t("sync.noticeGameOpenTitle")
        : t("sync.noticeUpdatedTitle", { version: modSync.bundledVersion || "bundled" }),
      detail: modSync.gameRunning ? t("sync.noticeGameOpenDetail") : t("sync.noticeUpdatedDetail"),
    });
    if (setupMessage) {
      setupMessage.className = "setup-message attention";
      setupMessage.textContent = modSync.message || "";
    }
    if (actionMessage) {
      actionMessage.className = "action-message ok";
      actionMessage.textContent = modSync.gameRunning
        ? t("sync.actionGameOpen")
        : modSync.message || t("sync.actionUpdated");
    }
    // Keep Setup collapsed — the top notice is enough.
    setupPinned = false;
    updateSetupVisibility({
      gameRoot: modSync.gameRoot || gameRootInput.value,
      baseSdk: resolvedBase,
      setupDismissed: true,
    });
    return;
  }

  if (modSync?.ok === false && modSync.reason !== "no-game-root") {
    hideModSyncNotice();
    setModSyncBanner("error", {
      kicker: t("sync.failKicker"),
      title: t("sync.failTitle"),
      detail: modSync.message || t("sync.failDetail"),
      versions,
    });
    if (setupMessage) {
      setupMessage.className = "setup-message attention";
      setupMessage.textContent = modSync.message || "";
    }
    setupPinned = true;
    updateSetupVisibility({
      gameRoot: modSync.gameRoot || gameRootInput.value,
      baseSdk: resolvedBase,
    });
    return;
  }

  const match =
    Boolean(modSync?.installedVersion) &&
    Boolean(modSync?.bundledVersion) &&
    modSync.installedVersion === modSync.bundledVersion;

  if (match || modSync?.reason === "already-current") {
    setModSyncBanner("ok", {
      kicker: t("sync.upToDateKicker"),
      title: t("sync.upToDateTitle", { version: modSync.bundledVersion || t("sync.unknown") }),
      detail: t("sync.upToDateDetail"),
      versions,
    });
    hideModSyncNotice();
    setupPinned = false;
    updateSetupVisibility({
      gameRoot: modSync.gameRoot || gameRootInput.value,
      baseSdk: resolvedBase,
      setupDismissed: true,
    });
    return;
  }

  if (modSyncDiskAhead(modSync)) {
    const diskVersion = modSync.installedVersion || t("sync.unknown");
    const bundledVersion = modSync.bundledVersion || t("sync.unknown");
    setModSyncBanner(modSync.gameRunning ? "restart" : "ok", {
      kicker: t("sync.diskAheadKicker"),
      title: t("sync.diskAheadTitle", { disk: diskVersion, exe: bundledVersion }),
      detail: t("sync.diskAheadDetail", { disk: diskVersion }),
      versions,
    });
    hideModSyncNotice();
    setupPinned = false;
    updateSetupVisibility({
      gameRoot: modSync.gameRoot || gameRootInput.value,
      baseSdk: resolvedBase,
      setupDismissed: true,
    });
    return;
  }

  setModSyncBanner("updated", {
    kicker: t("sync.kicker"),
    title: t("sync.willUpdateTitle"),
    detail: t("sync.willUpdateDetail"),
    versions,
  });
  showModSyncNotice("updated", {
    kicker: t("sync.kicker"),
    title: t("syncNotice.relaunchTitle"),
    detail: t("syncNotice.relaunchDetail"),
  });
  setupPinned = false;
  updateSetupVisibility({
    gameRoot: modSync.gameRoot || gameRootInput.value,
    baseSdk: resolvedBase,
    setupDismissed: true,
  });
}

async function applyGameFolderPickResult(result) {
  if (!result?.ok || result.cancelled) return false;
  if (result.gameRoot) gameRootInput.value = result.gameRoot;
  applyInstallLocationUi({
    gameRoot: result.gameRoot,
    storedGameRoot: result.storedGameRoot || result.gameRoot,
    pathSource: result.pathSource || "stored",
    candidates: result.candidates || [],
  });
  lastSetup = {
    ...(lastSetup || {}),
    gameRoot: result.gameRoot,
    storedGameRoot: result.storedGameRoot || result.gameRoot,
    pathSource: result.pathSource || "stored",
    candidates: result.candidates || [],
  };
  if (result.baseSdk || result.modSync) {
    applyBaseSdkUi(result.baseSdk, result.modSync);
    applyModSyncUi(result.modSync, result.baseSdk);
  }
  updateSetupVisibility({
    ...(lastSetup || {}),
    gameRoot: result.gameRoot,
  });
  return true;
}

async function loadSetup() {
  const setup = await window.sqbt.getSetup();
  await refreshListFavorites();
  // Prefer a real saved/detected root — never pretend a missing default C: path is set.
  let resolved =
    setup.gameRoot ||
    setup.storedGameRoot ||
    (setup.candidates || []).find(Boolean) ||
    "";
  lastSetup = setup;
  gameRootInput.value = resolved;
  applyTheme(setup.theme || "default");
  applyLocale(setup.locale || i18n.detectBrowserLocale(), { refresh: false });
  applyGhostOpacityUi(setup.ghostOpacity != null ? setup.ghostOpacity : 1);
  hiddenShapesUnlocked = Boolean(setup.hiddenShapes);
  injectHiddenShapeOptions();
  applyInstallLocationUi(setup);
  applyBaseSdkUi(setup.baseSdk, setup.modSync);
  applyModSyncUi(setup.modSync, setup.baseSdk);
  updateSetupVisibility({
    ...setup,
    gameRoot: resolved,
    setupDismissed: setup.setupDismissed || !setupNeedsUserAction({ ...setup, gameRoot: resolved }),
  });
  if (!setupNeedsUserAction({ ...setup, gameRoot: resolved }) && !setup.setupDismissed) {
    window.sqbt.dismissSetup().catch(() => {});
  }
  if (settingsModeNote) {
    settingsModeNote.textContent =
      setup.settingsMode === "appdata" || setup.isPackaged
        ? t("setup.appdata")
        : t("setup.devmode");
  }
  // Default Steam/Epic path first; if still missing, pop the folder picker once.
  if (!resolved && typeof window.sqbt.promptMissingGameFolder === "function") {
    try {
      const prompted = await window.sqbt.promptMissingGameFolder();
      if (prompted?.ok && prompted.gameRoot) {
        resolved = prompted.gameRoot;
        await applyGameFolderPickResult(prompted);
        if (setupMessage) {
          setupMessage.className = "setup-message attention";
          setupMessage.textContent = prompted.skipped
            ? "Borderlands 4 folder detected."
            : "Install folder saved. Squ1ggs mod auto-syncs on EXE launch.";
        }
      }
    } catch {
      /* user can still use Set install folder */
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
        actionMessage.textContent = t("snap.ok");
      } else {
        actionMessage.className = "action-message error";
        actionMessage.textContent = result?.message || t("snap.fail");
      }
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error || t("snap.error"));
    }
  });
}

if (themeSelect) {
  themeSelect.addEventListener("change", async () => {
    const next = themeSelect.value || "default";
    applyTheme(next);
    try {
      await window.sqbt.setTheme(next);
      actionMessage.className = "action-message ok";
      actionMessage.textContent = t(`theme.on.${next}`) || t("theme.saved");
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error || t("theme.fail"));
    }
  });
}

function applyGhostOpacityUi(opacity) {
  const pct = Math.round(Math.max(0.55, Math.min(1, Number(opacity) || 1)) * 100);
  if (ghostOpacityRange) ghostOpacityRange.value = String(pct);
  if (ghostOpacityLabel) ghostOpacityLabel.textContent = `${pct}%`;
}

let ghostOpacitySaveTimer = null;
if (ghostOpacityRange) {
  ghostOpacityRange.addEventListener("input", () => {
    const pct = Number(ghostOpacityRange.value) || 100;
    applyGhostOpacityUi(pct / 100);
    if (ghostOpacitySaveTimer) window.clearTimeout(ghostOpacitySaveTimer);
    ghostOpacitySaveTimer = window.setTimeout(async () => {
      try {
        const result = await window.sqbt.setGhostOpacity(pct / 100);
        applyGhostOpacityUi(result?.ghostOpacity ?? pct / 100);
      } catch {
        /* keep local label */
      }
    }, 120);
  });
}

if (langSelect) {
  langSelect.addEventListener("change", async () => {
    const next = applyLocale(langSelect.value);
    try {
      await window.sqbt.setLocale(next);
      actionMessage.className = "action-message ok";
      actionMessage.textContent = t("lang.saved");
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error || t("lang.fail"));
    }
  });
}

const watchaDialog = document.getElementById("watcha-dialog");
const watchaNsfwDialog = document.getElementById("watcha-nsfw-dialog");
const watchaContinueBtn = document.getElementById("watcha-continue-btn");
const watchaGotItBtn = document.getElementById("watcha-got-it-btn");

async function finishHiddenShapeUnlock() {
  hiddenShapesUnlocked = true;
  try {
    await window.sqbt.unlockHiddenShapes();
  } catch {
    /* still show the options in this session */
  }
  injectHiddenShapeOptions();
  watchaNsfwDialog?.close();
  actionMessage.className = "action-message ok";
  actionMessage.textContent = "two extra 3D shapes unlocked. keep those off public SBT posts.";
}

if (watchaContinueBtn) {
  watchaContinueBtn.addEventListener("click", () => {
    watchaDialog?.close();
    watchaNsfwDialog?.showModal();
  });
}
if (watchaGotItBtn) {
  watchaGotItBtn.addEventListener("click", () => {
    finishHiddenShapeUnlock();
  });
}

window.addEventListener("keydown", (event) => {
  const tag = String(event.target?.tagName || "").toLowerCase();
  const typing = tag === "input" || tag === "textarea";
  if (!(event.ctrlKey && event.altKey && event.shiftKey && event.key === "F9")) return;
  if (typing) return;
  event.preventDefault();
  unlockDevSmokePanel();
  if (hiddenShapesUnlocked) {
    injectHiddenShapeOptions();
    actionMessage.className = "action-message ok";
    actionMessage.textContent = "Dev smoke panel open. Hidden shapes already unlocked.";
    return;
  }
  watchaDialog?.showModal();
});

const devSmokeCard = document.getElementById("dev-smoke-card");
const devSmokeOut = document.getElementById("dev-smoke-out");
const devSmokeHideBtn = document.getElementById("dev-smoke-hide-btn");
const devRuntimeLogPath = document.getElementById("dev-runtime-log-path");
const devRuntimeLogTailBtn = document.getElementById("dev-runtime-log-tail-btn");
const devRuntimeLogFlushBtn = document.getElementById("dev-runtime-log-flush-btn");
const devRuntimeLogOpenBtn = document.getElementById("dev-runtime-log-open-btn");
let devSmokeUnlocked = false;

function unlockDevSmokePanel() {
  devSmokeUnlocked = true;
  if (devSmokeCard) {
    devSmokeCard.classList.remove("hidden");
    devSmokeCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  refreshDevRuntimeLogPath();
}

function runtimeLogPathFromStatus() {
  const raw = latestStatus?.raw || {};
  return String(raw.runtime_log?.path || raw.runtime_log?.dir || "").trim();
}

async function refreshDevRuntimeLogPath() {
  if (!devSmokeUnlocked || !devRuntimeLogPath) return;
  try {
    const { data } = await window.sqbt.postAction("runtime_log", { op: "status" }, 12);
    const p = String(data?.path || runtimeLogPathFromStatus() || "").trim();
    const bytes = data?.file_bytes != null ? ` (${data.file_bytes}B)` : "";
    const ring = data?.ring_lines != null ? ` ring=${data.ring_lines}` : "";
    devRuntimeLogPath.textContent = p
      ? `Flight log: ${p}${bytes}${ring}`
      : "Flight log: unavailable (mod offline?)";
  } catch (_error) {
    const p = runtimeLogPathFromStatus();
    devRuntimeLogPath.textContent = p
      ? `Flight log: ${p}`
      : "Flight log: connect in-game first";
  }
}

async function runDevSmoke(suite) {
  if (!devSmokeOut) return;
  const token = "";
  devSmokeOut.textContent = `Running ${suite}…`;
  actionMessage.className = "action-message muted";
  actionMessage.textContent = `Dev smoke: ${suite}…`;
  try {
    const { data } = await window.sqbt.postAction("dev_smoke", { suite, token }, 45);
    const text = String(data?.message || JSON.stringify(data, null, 2) || "No response");
    devSmokeOut.textContent = text;
    actionMessage.className = data?.ok ? "action-message ok" : "action-message error";
    actionMessage.textContent = data?.ok
      ? `Dev smoke [${suite}] passed — see panel + unrealsdk.log`
      : `Dev smoke [${suite}] failed — see panel + unrealsdk.log`;
    refreshDevRuntimeLogPath();
  } catch (error) {
    const msg = String(error?.message || error || "Dev smoke failed");
    devSmokeOut.textContent = msg;
    actionMessage.className = "action-message error";
    actionMessage.textContent = msg;
  }
}

if (devSmokeHideBtn) {
  devSmokeHideBtn.addEventListener("click", () => {
    devSmokeCard?.classList.add("hidden");
  });
}
document.querySelectorAll("[data-dev-smoke]").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (!devSmokeUnlocked) return;
    const suite = btn.getAttribute("data-dev-smoke") || "all";
    runDevSmoke(suite);
  });
});

if (devRuntimeLogTailBtn) {
  devRuntimeLogTailBtn.addEventListener("click", async () => {
    if (!devSmokeUnlocked || !devSmokeOut) return;
    try {
      const { data } = await window.sqbt.postAction("runtime_log", { op: "tail", limit: 80 }, 15);
      const lines = Array.isArray(data?.lines) ? data.lines : [];
      devSmokeOut.textContent =
        lines.length > 0
          ? lines.join("\n")
          : String(data?.message || "(empty runtime log)");
      refreshDevRuntimeLogPath();
    } catch (error) {
      devSmokeOut.textContent = String(error?.message || error);
    }
  });
}
if (devRuntimeLogFlushBtn) {
  devRuntimeLogFlushBtn.addEventListener("click", async () => {
    if (!devSmokeUnlocked) return;
    try {
      const { data } = await window.sqbt.postAction("runtime_log", { op: "flush" }, 12);
      actionMessage.className = "action-message ok";
      actionMessage.textContent = String(data?.message || "Runtime log flushed");
      refreshDevRuntimeLogPath();
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error);
    }
  });
}
if (devRuntimeLogOpenBtn) {
  devRuntimeLogOpenBtn.addEventListener("click", async () => {
    if (!devSmokeUnlocked) return;
    try {
      let target = runtimeLogPathFromStatus();
      if (!target) {
        const { data } = await window.sqbt.postAction("runtime_log", { op: "status" }, 12);
        target = String(data?.path || data?.dir || "").trim();
      }
      if (!target) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = "No runtime log path yet — enable the mod in-game first.";
        return;
      }
      const result = await window.sqbt.openPath(target);
      if (!result?.ok) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = String(result?.message || "Could not open path");
        return;
      }
      actionMessage.className = "action-message ok";
      actionMessage.textContent = `Opened ${result.path || target}`;
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error);
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
  globalTargetSelect.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    const value = globalTargetSelect.value;
    const idx = Number(value);
    if (!Number.isFinite(idx) || idx < 0) {
      actionMessage.textContent = "Pick a single Boost target player before kicking.";
      return;
    }
    const label =
      globalTargetSelect.selectedOptions?.[0]?.textContent?.trim() || `Player ${idx}`;
    showPlayerKickMenu(event.clientX, event.clientY, idx, label);
  });
}

browseGameBtn.addEventListener("click", async () => {
  const result = await window.sqbt.pickGameFolder();
  if (result.ok) {
    await applyGameFolderPickResult(result);
    if (!(result.modSync?.updated && result.modSync?.ok) && setupMessage) {
      setupMessage.className = "setup-message";
      setupMessage.textContent = result.baseSdk?.installed
        ? "Install folder saved. Squ1ggs mod auto-syncs on EXE launch."
        : "Install folder saved. Base SDK missing — press Install SDK + Squ1ggs mod once.";
    }
  }
});

async function runInstall({ forceBaseSdk = false, includeBaseSdk = false } = {}) {
  setupPinned = true;
  if (setupCard) setupCard.classList.remove("is-hidden");
  setupMessage.className = "setup-message";
  setupMessage.textContent = forceBaseSdk
    ? "Updating base oak2 SDK…"
    : "Installing / updating…";
  if (installModBtn) installModBtn.disabled = true;
  if (updateBaseSdkBtn) updateBaseSdkBtn.disabled = true;
  try {
    const result = await window.sqbt.installSdkmod({
      forceBaseSdk,
      includeBaseSdk: includeBaseSdk || forceBaseSdk,
    });
    if (result?.cancelled) {
      setupMessage.className = "setup-message";
      setupMessage.textContent = result.message || "Cancelled.";
      return;
    }
    const base =
      result?.message || "Install finished without a status message.";
    if (result?.ok) {
      setupMessage.className = "setup-message attention";
      setupMessage.textContent = result?.needsGameRestart
        ? `${base}  →  Fully restart Borderlands 4 now (quit to desktop). Load a character — this window should go Online.`
        : base;
      if (result.gameRoot) gameRootInput.value = result.gameRoot;
      actionMessage.className = "action-message ok";
      actionMessage.textContent = setupMessage.textContent;
    } else {
      setupMessage.className = "setup-message attention";
      setupMessage.textContent = base;
    }
    await loadSetup();
    try {
      await window.sqbt.getStatus().then(setStatusUi);
      await loadManifest();
    } catch {
      /* game may still be restarting */
    }
  } catch (error) {
    setupMessage.className = "setup-message attention";
    setupMessage.textContent = `Install failed: ${String(error?.message || error)}`;
  } finally {
    if (installModBtn) installModBtn.disabled = false;
    if (updateBaseSdkBtn) updateBaseSdkBtn.disabled = false;
  }
}

installModBtn.addEventListener("click", async () => {
  // Main process confirms before downloading oak2 when needed.
  const setup = await window.sqbt.getSetup();
  const missing = !setup?.baseSdk?.installed;
  await runInstall({
    includeBaseSdk: missing,
    forceBaseSdk: false,
  });
});

if (updateBaseSdkBtn) {
  updateBaseSdkBtn.addEventListener("click", async () => {
    await runInstall({ forceBaseSdk: true, includeBaseSdk: true });
  });
}

if (dismissSetupBtn) {
  dismissSetupBtn.addEventListener("click", async () => {
    setupPinned = false;
    await window.sqbt.dismissSetup();
    updateSetupVisibility({ gameRoot: gameRootInput.value, setupDismissed: true });
  });
}

if (showSetupBtn) {
  showSetupBtn.addEventListener("click", () => {
    showSetupCard();
  });
}

if (typeof window.sqbt.onUpdateProgress === "function") {
  window.sqbt.onUpdateProgress((info) => {
    if (info?.message) {
      if (setupMessage && setupPinned) {
        setupMessage.className = "setup-message";
        setupMessage.textContent = String(info.message);
      }
      if (updateDetail) {
        updateDetail.textContent = String(info.message);
      }
    }
  });
}

if (typeof window.sqbt.onModSync === "function") {
  window.sqbt.onModSync((info) => applyModSyncUi(info, lastBaseSdk));
}

if (updateOpenBtn) {
  updateOpenBtn.addEventListener("click", async () => {
    if (updateApplying) return;
    if (!pendingCanApply) {
      if (updateOpenBtn.textContent === "Got it") {
        updateCard?.classList.add("hidden");
        return;
      }
      if (pendingUpdateUrl) window.sqbt.openExternal(pendingUpdateUrl);
      return;
    }
    updateApplying = true;
    updateOpenBtn.disabled = true;
    updateOpenBtn.textContent = "Installing…";
    if (updateDetail) updateDetail.textContent = "Downloading update from GitHub…";
    try {
      const modVersion = latestStatus?.raw?.mod_version || "";
      const result = await window.sqbt.applyGithubUpdate(modVersion);
      if (result?.ok) {
        if (updateTitle) updateTitle.textContent = "Update installed";
        if (updateDetail) {
          updateDetail.textContent = result.message || "Update installed. Fully restart Borderlands 4.";
        }
        updateOpenBtn.textContent = result.restartApp ? "Reopening once…" : "Installed";
        if (result.needsGameRestart && actionMessage) {
          actionMessage.className = "action-message ok";
          actionMessage.textContent = result.message || "Mod updated. Fully restart Borderlands 4.";
        }
        if (result.restartApp && updateDetail) {
          updateDetail.textContent =
            "Closing and reopening once to finish the EXE update. After it comes back, you can close normally.";
        }
        if (!result.restartApp) {
          window.setTimeout(() => refreshUpdateStatus(true), 1200);
        }
      } else {
        if (updateDetail) {
          updateDetail.textContent = result?.message || "Update failed.";
        }
        updateOpenBtn.textContent = pendingCanApply ? "Install update" : "Open GitHub";
        updateOpenBtn.disabled = false;
      }
    } catch (error) {
      if (updateDetail) {
        updateDetail.textContent = `Update failed: ${String(error?.message || error)}`;
      }
      updateOpenBtn.textContent = pendingCanApply ? "Install update" : "Open GitHub";
      updateOpenBtn.disabled = false;
    } finally {
      updateApplying = false;
    }
  });
}

if (updateDismissBtn) {
  updateDismissBtn.addEventListener("click", () => {
    updateCard?.classList.add("hidden");
  });
}

if (reportIssueBtn) {
  reportIssueBtn.addEventListener("click", () => openReportIssueDialog());
}
if (reportIssueFooterBtn) {
  reportIssueFooterBtn.addEventListener("click", () => openReportIssueDialog());
}
if (reportGithubBtn) {
  reportGithubBtn.addEventListener("click", () => {
    window.sqbt.openExternal(buildGithubIssueUrl());
    reportIssueDialog?.close?.();
  });
}
if (reportDiscordBtn) {
  reportDiscordBtn.addEventListener("click", () => {
    window.sqbt.openExternal(REPORT_DISCORD);
    reportIssueDialog?.close?.();
  });
}

if (modSyncNoticeDismiss) {
  modSyncNoticeDismiss.addEventListener("click", () => hideModSyncNotice());
}

bindExternalLinks(startGuide);
i18n.fillLocaleSelect(langSelect, i18n.detectBrowserLocale());
if (toolSearchInput) {
  toolSearchInput.addEventListener("input", () => renderToolSearchResults(toolSearchInput.value));
  toolSearchInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      toolSearchInput.value = "";
      hideToolSearchResults();
    }
  });
  toolSearchInput.addEventListener("focus", () => {
    if (toolSearchInput.value.trim().length >= 2) renderToolSearchResults(toolSearchInput.value);
  });
}
document.addEventListener("click", (event) => {
  const challengeStop = event.target?.closest?.("[data-challenge-stop]");
  if (challengeStop) {
    event.preventDefault();
    event.stopPropagation();
    if (!actionsEnabled() || actionBusy) return;
    runAction("challenge_bulk_cancel", {}, "", {
      sectionId: "progression:challenges",
      actionDef: { action: "challenge_bulk_cancel", label: "Stop challenges" },
    });
    return;
  }
  const vacuumStop = event.target?.closest?.("[data-vacuum-stop]");
  if (vacuumStop) {
    event.preventDefault();
    event.stopPropagation();
    if (!actionsEnabled() || actionBusy) return;
    lastVacuumStatus = null;
    runAction("loot_vacuum_cancel", {}, "", {
      sectionId: "world:Loot gather",
      actionDef: { action: "loot_vacuum_cancel", label: "Stop vacuum" },
    });
    return;
  }
  const stopBtn = event.target?.closest?.("[data-auto-lobby-stop]");
  if (stopBtn) {
    event.preventDefault();
    event.stopPropagation();
    if (!actionsEnabled() || actionBusy) return;
    runAction("auto_lobby_stop", { enabled: false }, "", {
      sectionId: "auto_lobby:Auto Lobby",
      actionDef: { action: "auto_lobby_stop", label: "Stop Auto Lobby" },
    });
    return;
  }
  if (!toolSearchResults || toolSearchResults.classList.contains("hidden")) return;
  // Results live in .tool-search-bar; also ignore hit buttons explicitly so a
  // bubble order quirk cannot dismiss before jumpToTool runs.
  const t = event.target;
  if (t?.closest?.(".tool-search-bar") || t?.closest?.(".tool-search-hit")) return;
  hideToolSearchResults();
});
window.sqbt.onStatus(setStatusUi);
loadSetup();
window.sqbt.getStatus().then(setStatusUi);
loadManifest();
window.setTimeout(() => refreshUpdateStatus(false), 900);

let resizeUiTimer = null;
window.addEventListener("resize", () => {
  document.body.classList.add("is-resizing");
  clearTimeout(resizeUiTimer);
  resizeUiTimer = window.setTimeout(() => {
    document.body.classList.remove("is-resizing");
    applyProgressPanelPosition(document.getElementById("sqbt-progress-panel"));
  }, 150);
});
