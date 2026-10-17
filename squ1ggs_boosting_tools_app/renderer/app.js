"use strict";

const OPEN_REWARDS_LARGE_WARNING =
  "WARNING: Open rewards on send opens only packages from that delivery (one every 3–5s). All non-UVHM never auto-opens its Reward Center packages. Console / cross-play users may receive 600+ items: leave multiplayer, open in solo, sell junk, and reduce carried items before rejoining.";

const OPEN_ALL_AFTER_CHALLENGE_WARNING =
  "Complete ALL non-UVHM only sends Reward Center packages; opening that flood is blocked in multiplayer. Leave the lobby, open them in solo, sell junk, and reduce carried items before rejoining. Normal Codes / Serials bulk sends with Open rewards on send still open. Open pending rewards still works for normal bulk mail (confirm if 40+ packages).";

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

function shortenStatusLine(raw, maxLen = 160) {
  let text = String(raw || "").trim();
  if (!text) return "";
  // Strip long @U dumps from unique_piles / arrange status.
  text = text.replace(/@U[^\s,\]]{12,}/g, (m) => `${m.slice(0, 12)}…`);
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen - 1)}…`;
}

function gameFacingLogLines(lines) {
  const rows = Array.isArray(lines) ? lines : [];
  const keep = rows.filter((line) => {
    const s = String(line || "");
    if (/\] action (begin|ok|fail)\b/i.test(s)) return false;
    if (/\] EXE note:/i.test(s)) return false;
    return true;
  });
  return keep.length ? keep : rows.slice(-40);
}

function showRuntimeLogPanel(lines, path) {
  const filtered = gameFacingLogLines(lines);
  const embedded = document.getElementById("sqbt-live-log-body");
  const pathElEmbedded = document.getElementById("sqbt-live-log-path");
  if (pathElEmbedded) pathElEmbedded.textContent = path ? String(path) : "sqbt_runtime.log";
  if (embedded) {
    embedded.textContent = filtered.join("\n") || "(empty — run something in-game)";
    embedded.scrollTop = embedded.scrollHeight;
    return;
  }
  let panel = document.getElementById("sqbt-runtime-log-panel");
  if (!panel) {
    panel = document.createElement("section");
    panel.id = "sqbt-runtime-log-panel";
    panel.className = "runtime-log-panel";
    panel.innerHTML = `
      <div class="runtime-log-head">
        <strong>Runtime log</strong>
        <button type="button" class="ghost-btn" data-runtime-log-close="1">Close</button>
      </div>
      <p class="muted runtime-log-path"></p>
      <pre class="runtime-log-body"></pre>`;
    document.body.appendChild(panel);
    panel.querySelector("[data-runtime-log-close]")?.addEventListener("click", () => {
      panel.classList.add("hidden");
    });
  }
  const pathEl = panel.querySelector(".runtime-log-path");
  const body = panel.querySelector(".runtime-log-body");
  if (pathEl) pathEl.textContent = path ? String(path) : "sqbt_runtime.log";
  if (body) body.textContent = filtered.join("\n");
  panel.classList.remove("hidden");
}

let liveLogPollTimer = null;
let appearancePollToken = 0;
const automaticSdkSetupAttempts = new Set();
let sdkInstallInProgress = false;

function pollAppearanceApply(expectedCode = "", operationId = 0, successState = "applied") {
  const token = ++appearancePollToken;
  const started = Date.now();
  const poll = async () => {
    if (token !== appearancePollToken) return;
    try {
      const { data } = await window.sqbt.postAction("camera_view_status", {}, 8);
      const appearance = data?.appearance || {};
      const state = String(appearance.pending_state || "");
      if (operationId && Number(appearance.operation_id) !== Number(operationId)) {
        actionMessage.className = "action-message attention";
        actionMessage.textContent = "This appearance request was replaced by another appearance action.";
        return;
      }
      if (state === successState && (successState === "preview" || appearance.active)) {
        const offset = Number(appearance.position_error);
        const suffix = Number.isFinite(offset) ? ` (player offset ${offset.toFixed(1)})` : "";
        actionMessage.className = "action-message ok";
        actionMessage.textContent =
          String(appearance.message || `Appearance applied from ${expectedCode || appearance.source || "selected model"}`) +
          suffix;
        return;
      }
      if (["cancelled", "restored", "cleared"].includes(state)) {
        actionMessage.className = "action-message attention";
        actionMessage.textContent = String(appearance.message || "Appearance request cancelled.");
        return;
      }
      if (state === "failed") {
        actionMessage.className = "action-message error";
        actionMessage.textContent =
          String(appearance.pending_error || "The model spawned, but its appearance could not be applied.");
        return;
      }
      if (Date.now() - started < 46000) {
        window.setTimeout(poll, 500);
      } else {
        actionMessage.className = "action-message attention";
        actionMessage.textContent =
          "Appearance is still unconfirmed. Use Appearance status before trying another model.";
      }
    } catch (_error) {
      if (Date.now() - started < 46000) window.setTimeout(poll, 800);
      else {
        actionMessage.className = "action-message error";
        actionMessage.textContent = "Could not confirm the appearance request. Reconnect and check Appearance status.";
      }
    }
  };
  window.setTimeout(poll, 350);
}

async function refreshLiveLogPanel() {
  if (!actionsEnabled()) return;
  try {
    const { data } = await window.sqbt.postAction("runtime_log", { op: "tail", limit: 250 }, 15);
    if (Array.isArray(data?.lines)) {
      showRuntimeLogPanel(data.lines, data?.path || "");
    }
  } catch (_err) {
    /* keep last lines */
  }
}

function startLiveLogPolling() {
  stopLiveLogPolling();
  refreshLiveLogPanel();
  liveLogPollTimer = setInterval(() => {
    if (activeTabId !== "log") {
      stopLiveLogPolling();
      return;
    }
    refreshLiveLogPanel();
  }, 2500);
}

function stopLiveLogPolling() {
  if (liveLogPollTimer) {
    clearInterval(liveLogPollTimer);
    liveLogPollTimer = null;
  }
}

function showMobilityToast(message, kind = "ok") {
  const text = String(message || "").trim();
  if (!text) {
    return;
  }
  if (actionMessage) {
    actionMessage.className = `action-message ${kind === "off" ? "attention" : "ok"}`;
    actionMessage.textContent = shortenStatusLine(text);
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
let navMode = (() => {
  try {
    const raw = String(localStorage.getItem(NAV_MODE_KEY) || "tabs").trim().toLowerCase();
    if (raw === "menu") return "menu";
    // Lobby/Desk renamed to Compact — keep old saved values working.
    if (raw === "compact" || raw === "lobby" || raw === "desk") return "compact";
  } catch {
    /* ignore */
  }
  return "tabs";
})();
let navDrawerOpen = false;
let fieldValues = {};
let progressPollTimer = null;
let progressPollInFlight = false;
let progressPollMs = 0;
let challengePaintTimer = null;
const autoLobbyTouchedKeys = new Set();
let autoLobbyPrefillGen = 0;
/** Block status/prefill remounts briefly while the user is typing in tool fields. */
let userEditingUntil = 0;

function markUserEditing(ms = 4000) {
  userEditingUntil = Math.max(userEditingUntil, Date.now() + Math.max(600, Number(ms) || 4000));
}

function isUserEditingTools() {
  if (Date.now() < userEditingUntil) return true;
  const focused = document.activeElement;
  if (!focused) return false;
  // Anywhere in the window — sticky chrome + tab fields both count.
  if (focused.matches?.("input, textarea, select") || focused.isContentEditable) {
    return true;
  }
  return Boolean(
    tabContent?.contains(focused) &&
      (focused.matches?.("input, textarea, select") || focused.isContentEditable)
  );
}
let lastCatalogRosterSig = "";
let uvhmBusyGraceUntil = 0;
let uvhmErrorShownUntil = 0;
let uvhmCompleteDismissed = false;
let challengeBusyGraceUntil = 0;
let challengeCompleteShownUntil = 0;
/** Once Complete/Cancel flash ends, ignore leftover sticky snapshots until new live work. */
let challengeCompleteDismissed = false;
/** Falling-edge finish flash — show Complete even if the mod jumps straight to idle. */
let challengeFinishFlashUntil = 0;
let uvhmFinishFlashUntil = 0;
let challengeSawLive = false;
let uvhmSawLive = false;
let challengeOptimisticUntil = 0;
let challengeProgressStartedAt = 0;
let challengeProgressTotalHint = 0;
let challengeDisplayMilestone = 0;
/** After Stop, ignore status polls that still claim running (bridge race). */
let challengeCancelHoldUntil = 0;
let uvhmCancelHoldUntil = 0;
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
  { id: "codes", label: "Codes / Lootlemon" },
  { id: "mail", label: "Mail" },
];
const SERIALS_SEGMENT_KEY = "sqbt.serialsSegment";
const EDITOR_CARD_KEY = "sqbt.editorShowItemCard";
const CATALOG_CARD_KEY = "sqbt.catalogShowItemCards";
let editorFrameLoaded = false;
let editorPersistedFrame = null;
let editorParkEl = null;
let editorLatest = {
  serial: "",
  deser: "",
  ready: false,
  preview: null,
  sourceSerial: "",
  analysis: null,
  inspection: null,
  importingSourceUntil: 0,
};
let editorImageResult = null;
let editorImagePreviewUrl = "";
let editorPictureUncertain = false;
let editorPictureTargetLevel = null;
let editorPicturePreview = null;
let editorPictureSelectedSource = "";
let editorPictureFinalizeGen = 0;
let editorPictureLastImport = null;
let editorPreviewTimer = 0;
let editorValidationTimer = 0;
let editorMessageBound = false;
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
let lastMissionStatus = null;
let lastGiveEverythingStatus = null;
let pendingUpdateUrl = "";
const STATUS_CATALOG_TABS = new Set(["serials", "world", "vehicle", "progression", "builds"]);
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
  builds: "assets/icons/tab-save-pack.svg",
  editor: "assets/bl4/tab-loot.png",
  picture_item: "assets/bl4/tab-loot.png",
  camera: "assets/icons/tab-mobility.svg",
  appearance: "assets/icons/tab-player.svg",
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
  freecam: "assets/icons/tab-mobility.svg",
  display: "assets/icons/tab-player.svg",
  loot_shapes: "assets/icons/tab-shapes.svg",
  faafo: "assets/bl4/tab-damage.png",
  activity: "assets/icons/tab-support.svg",
  log: "assets/icons/tab-support.svg",
  support: "assets/icons/tab-support.svg",
  toggles: "assets/icons/tab-mobility.svg",
  auto_lobby: "assets/bl4/tab-home.png",
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
  [/give_everything|max_all|\bplayer\b/i, "assets/icons/tab-player.svg"],
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
  if (/give_everything|max_all|cosmetic|golden.?chest|black.?market/i.test(searchable)) return "gold";
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
  if (actionDef?.shine) {
    button.classList.add("action-shine");
    button.dataset.shine = "1";
  }
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
  if (uiPreviewOnline) return true;
  if (!latestStatus?.connected) return false;
  if (latestStatus.actionsAvailable === true) return true;
  if (latestStatus.state === "ready" || latestStatus.state === "connected") return true;
  const raw = latestStatus.raw || {};
  return Boolean(raw.actions_available || raw.has_local_pc || (raw.players && raw.players.length));
}

let uiPreviewOnline = false;
const UI_PREVIEW_KEY = "sqbt.uiPreviewOnline";
// Never restore sticky offline-preview across launches — combo only.
try {
  localStorage.removeItem(UI_PREVIEW_KEY);
} catch {
  /* ignore */
}

function previewOnlinePayload() {
  return {
    connected: true,
    state: "ready",
    headline: "Connected!",
    detail: "Offline browse — connect Borderlands for live actions",
    actionsAvailable: true,
    raw: {
      session: "UI preview",
      mod_version: String(latestStatus?.raw?.mod_version || lastModSync?.installedVersion || "preview"),
      actions_available: true,
      has_local_pc: true,
      players: [{ index: 0, name: "Preview Host", is_host: true, host: true }],
      target_player_index: 0,
      target_player_name: "Preview Host",
      spawn_anchor: "local",
      spawn_anchor_label: "From me",
      bridge_features: { manifest: true },
    },
  };
}

async function setUiPreviewOnline(on) {
  uiPreviewOnline = Boolean(on);
  // Session-only: do not persist across EXE restarts.
  try {
    localStorage.removeItem(UI_PREVIEW_KEY);
  } catch {
    /* ignore */
  }
  if (uiPreviewOnline) {
    lastSeenConnected = true;
    offlineStreak = 0;
    setStatusUi(previewOnlinePayload());
    await loadManifest({ allowOffline: true });
    if (actionMessage) {
      actionMessage.className = "action-message ok";
      actionMessage.textContent = "Browsing offline (no game connected).";
    }
    return;
  }
  if (actionMessage) {
    actionMessage.className = "action-message muted";
    actionMessage.textContent = "Waiting for Borderlands connection…";
  }
  try {
    const status = await window.sqbt.getStatus();
    setStatusUi(status);
  } catch {
    setStatusUi({
      connected: false,
      state: "disconnected",
      headline: "Game not connected",
      detail: "Start Borderlands with the SDK mod for live actions.",
      raw: null,
    });
  }
  if (!latestStatus?.connected) {
    clearToolsToWaiting(t("waiting.manifestUnavailable"));
  }
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
    const modOnly =
      modBehind && !appBehind && Boolean(result.sdkmodUrl);
    if (appBehind) {
      lines.push(
        pendingCanApply
          ? t("update.appBehindApply", { current: current || t("sync.unknown"), latest })
          : t("update.appBehindManual", { current: current || t("sync.unknown"), latest })
      );
    }
    if (modBehind) {
      lines.push(
        t(modOnly ? "update.modBehindSdkmod" : "update.modBehind", {
          current: result.currentModVersion || t("sync.unknown"),
          latest: result.latestModVersion || latest,
        })
      );
    }
    if (!lines.length) {
      lines.push(t("update.generic", { latest }));
    }
    lines.push(t(modOnly ? "update.githubRequiredModOnly" : "update.githubRequired"));
    lines.push(t(modOnly ? "update.restartAfterModOnly" : "update.restartAfter"));
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
  // Empty/transient roster mid join-leave — keep sticky so UI does not snap to host.
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
  const lobbyLiveOpen = Boolean(
    navMode === "compact" &&
      tabContent?.querySelector('[data-desk-band-wrap="party_bay"].desk-band-open')
  );
  if (
    activeTabId !== "backpack" &&
    activeTabId !== "pack_bay" &&
    activeTabId !== "party_bay" &&
    !lobbyLiveOpen
  ) {
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
    me: "spawn.local",
    "From me": "spawn.local",
    "From selected player": "spawn.party",
    "Near nearest NPC": "spawn.npc",
    "At debug cam": "spawn.freecam",
    "nearest NPC": "spawn.npc",
  };
  if (map[value]) return t(map[value]);
  // Never surface Unreal class names (OakPlayerController_…) in the status bar.
  let cleaned = value
    .replace(/\bOak(?:2)?PlayerController(?:_\w+)?\b/gi, "player")
    .replace(/\bPlayerController(?:_\w+)?\b/gi, "player")
    .replace(/\bDefault__\w+\b/gi, "player")
    .replace(/\s{2,}/g, " ")
    .trim();
  if (/^selected player:/i.test(cleaned)) {
    const name = cleaned.replace(/^selected player:\s*/i, "").trim();
    if (!name || /^player(?:\s+\d+)?$/i.test(name)) return t("spawn.party");
    return `selected player: ${name}`;
  }
  if (/playercontroller|oakplayer/i.test(cleaned)) return t("spawn.party");
  return cleaned || "—";
}

function bridgeConnectedHeld() {
  if (uiPreviewOnline) return true;
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
  // While UI preview is on, ignore real offline polls so tabs stay usable.
  if (uiPreviewOnline && !incoming.__uiPreview && !incoming.connected) {
    return;
  }
  const wasConnected = Boolean(lastSeenConnected);
  let connectedNow = Boolean(incoming.connected) || uiPreviewOnline;
  // Hold Online through 2 brief offline polls so tab switches / catalog loads
  // cannot flash the "Start Borderlands 4" waiting panel.
  if (!connectedNow && lastSeenConnected && !uiPreviewOnline) {
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
  applyBridgeChallengeSnapshot(payload?.raw || {});
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
    (String(raw.mod_version) !== String(lastModSync.installedVersion || lastModSync.bundledVersion) ||
      compareModVersions(lastModSync.installedVersion || lastModSync.bundledVersion, lastModSync.bundledVersion) < 0)
  ) {
    const base = localizeStatusDetail(payload?.headline, payload.detail || "");
    const disk = lastModSync.installedVersion || "";
    const bundled = lastModSync.bundledVersion;
    const diskMatchesBundled = disk && String(disk) === String(bundled);
    const diskAhead = disk && bundled && compareModVersions(disk, bundled) > 0;
    const liveMatchesDisk =
      disk && raw.mod_version && String(raw.mod_version) === String(disk);
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
    // Disk-ahead after a mod-only hotfix is OK once the game is on disk — don't alarm.
    if (!(diskAhead && liveMatchesDisk)) {
      statusDetail.classList.add("attention");
    }
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
      if (!isUserEditingTools()) {
        window.setTimeout(() => reloadCatalogSelects(), 0);
      }
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
  if (crossedActionsUnlock || crossedFirstConnect) {
    window.setTimeout(() => {
      // Repaint the library once on connection, without collapsing it on roster polls.
      refreshAllSerialStoreSections();
      for (const box of tabContent.querySelectorAll("[data-multiselect-section]")) {
        const sectionId = box.dataset.multiselectSection;
        const config = getMultiselectConfig(sectionId);
        if (config?.catalog === "curated_builds") {
          catalogCache.delete(catalogCacheKey(config.catalog, multiselectParams(sectionId, config)));
          refreshMultiselectSection(sectionId, config);
        }
      }
    }, 0);
  }
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
  if (!connectedNow && wasConnected && !uiPreviewOnline) {
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
  pendingTargetUntil = Date.now() + 30000;
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
    pendingTargetUntil = Date.now() + 20000;
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
/** syncKey → timestamp; status polls skip overwriting during grace. */
const stickyToggleGraceUntil = Object.create(null);

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

function beginStickyToggleChange(key, on) {
  if (!key) return;
  // Keep polling from undoing a click for the whole bridge request.
  stickyToggleGraceUntil[key] = Infinity;
  patchStickyToggleLocal(key, on);
  syncMobilityToggleButtons(key, on);
}

function finishStickyToggleChange(key) {
  if (key) stickyToggleGraceUntil[key] = Date.now() + 2500;
}

function reconcileFailedToggle(button, actionDef, sectionId, previousOn, result) {
  if (result && result.ok !== false) return;
  paintToggleButton(button, actionDef, previousOn);
  if (actionDef.syncKey) {
    delete stickyToggleGraceUntil[actionDef.syncKey];
    patchStickyToggleLocal(actionDef.syncKey, previousOn);
    syncMobilityToggleButtons(actionDef.syncKey, previousOn);
  }
  if (actionDef.sticky) writeStickyToggle(toggleStickyKey(sectionId, actionDef), previousOn);
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
          finishing_until: Date.now() + 1200,
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
    const now = Date.now();
    document.querySelectorAll("button[data-sync-key]").forEach((button) => {
      const key = button.dataset.syncKey;
      if (!key || !Object.prototype.hasOwnProperty.call(sticky, key)) return;
      // Don't let a mid-flight status poll undo a local sticky click.
      if (stickyToggleGraceUntil[key] && now < stickyToggleGraceUntil[key]) return;
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
  let section = manifest.tabs.find((row) => row.id === tabId)?.sections?.find(
    (row) => row.title === sectionTitle
  );
  // Compact used to paint under lobby:Title — still resolve fields by title.
  if (!section?.fields?.length && sectionTitle) {
    for (const tab of manifest.tabs) {
      const hit = (tab.sections || []).find((row) => row.title === sectionTitle && row.fields?.length);
      if (hit) {
        section = hit;
        break;
      }
    }
  }
  for (const field of section?.fields || []) {
    const key = sectionFieldKey(sectionId, field);
    if (field.type === "kick_exempt") {
      const raw = fieldValues[key];
      payload[field.key] = Array.isArray(raw)
        ? raw.map((n) => String(n || "").trim()).filter(Boolean)
        : [];
      continue;
    }
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
    if (wrap.dataset.role === "kick-exempt") continue;
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
    return "No saved lists yet — paste codes, type a list name, then Save. Import a file also works (it only adds).";
  }
  if (catalogName === "serial_groups") {
    return "No Item lists yet — create one under Serials → Item lists (Save to list), then it shows here without restarting.";
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
      <p class="muted small">Paste codes, type a list name, then Save. Import a file only adds — it never replaces your lists.</p>
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

const SERIAL_STORE_NEW_PACK = "__new__";

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
    const inputWrap = document.getElementById("sqbt-prompt-input-wrap");
    const selectWrap = document.getElementById("sqbt-prompt-select-wrap");
    const select = document.getElementById("sqbt-prompt-select");
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
    if (selectWrap) selectWrap.hidden = true;
    if (select) {
      select.innerHTML = "";
      select.onchange = null;
    }
    if (inputWrap) inputWrap.hidden = false;
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

/** Pick an existing item build, or type a new name. Returns the build name or null. */
function promptPackPickDialog({
  title = "Add to Builds",
  kicker = "Builds",
  detail = "",
  packs = [],
  suggested = "",
  okLabel = "Save",
  newLabel = "＋ New named build…",
} = {}) {
  const known = [];
  const seen = new Set();
  for (const raw of packs || []) {
    const name = String(raw || "").trim();
    if (!name || name.toLowerCase() === "all") continue;
    const key = name.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    known.push(name);
  }
  known.sort((a, b) => a.localeCompare(b));
  if (!known.includes("Default")) known.unshift("Default");
  const want = String(suggested || "").trim();
  if (want && want.toLowerCase() !== "all" && !known.some((p) => p.toLowerCase() === want.toLowerCase())) {
    known.push(want);
    known.sort((a, b) => a.localeCompare(b));
  }

  return new Promise((resolve) => {
    const dialog = document.getElementById("sqbt-prompt-dialog");
    const form = document.getElementById("sqbt-prompt-form");
    const titleEl = document.getElementById("sqbt-prompt-title");
    const kickerEl = document.getElementById("sqbt-prompt-kicker");
    const detailEl = document.getElementById("sqbt-prompt-detail");
    const labelEl = document.getElementById("sqbt-prompt-label");
    const selectLabel = document.getElementById("sqbt-prompt-select-label");
    const input = document.getElementById("sqbt-prompt-input");
    const inputWrap = document.getElementById("sqbt-prompt-input-wrap");
    const selectWrap = document.getElementById("sqbt-prompt-select-wrap");
    const select = document.getElementById("sqbt-prompt-select");
    const okBtn = document.getElementById("sqbt-prompt-ok");
    if (!dialog || !form || !input || !select || !selectWrap) {
      promptTextDialog({
        title,
        kicker,
        detail,
        label: "Build name",
        defaultValue: want || "Default",
        okLabel,
      }).then(resolve);
      return;
    }
    if (titleEl) titleEl.textContent = title;
    if (kickerEl) kickerEl.textContent = kicker;
    if (detailEl) {
      detailEl.textContent =
        detail || "Pick a build you already have, or create a new named build.";
      detailEl.classList.toggle("hidden", false);
    }
    if (selectLabel) selectLabel.textContent = "Build";
    if (labelEl) labelEl.textContent = "New build name";
    if (okBtn) okBtn.textContent = okLabel;
    select.innerHTML = "";
    for (const pack of known) {
      const opt = document.createElement("option");
      opt.value = pack;
      opt.textContent = pack;
      select.appendChild(opt);
    }
    const newOpt = document.createElement("option");
    newOpt.value = SERIAL_STORE_NEW_PACK;
    newOpt.textContent = newLabel;
    select.appendChild(newOpt);
    selectWrap.hidden = false;
    const syncInput = () => {
      const isNew = select.value === SERIAL_STORE_NEW_PACK;
      if (inputWrap) inputWrap.hidden = !isNew;
      if (isNew && !String(input.value || "").trim()) {
        input.value = want && !known.includes(want) ? want : "";
      }
    };
    if (want && known.includes(want)) {
      select.value = want;
      input.value = "";
    } else if (want && !known.includes(want)) {
      select.value = SERIAL_STORE_NEW_PACK;
      input.value = want;
    } else {
      select.value = known[0] || SERIAL_STORE_NEW_PACK;
      input.value = "";
    }
    syncInput();
    select.onchange = syncInput;
    const onClose = () => {
      dialog.removeEventListener("close", onClose);
      select.onchange = null;
      if (dialog.returnValue !== "ok") {
        resolve(null);
        return;
      }
      if (select.value === SERIAL_STORE_NEW_PACK) {
        resolve(String(input.value || ""));
      } else {
        resolve(String(select.value || ""));
      }
    };
    dialog.addEventListener("close", onClose);
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "open");
    window.setTimeout(() => {
      if (select.value === SERIAL_STORE_NEW_PACK) {
        input.focus();
        input.select();
      } else {
        select.focus();
      }
    }, 30);
  });
}

function allKnownSerialStorePackNames() {
  const names = new Set(["Default"]);
  try {
    if (typeof serialStorePackNames !== "undefined") {
      for (const list of serialStorePackNames.values()) {
        for (const name of list || []) {
          const g = String(name || "").trim();
          if (g && g.toLowerCase() !== "all") names.add(g);
        }
      }
    }
  } catch {
    /* ignore */
  }
  try {
    for (const [sectionId, rows] of multiselectRows.entries()) {
      const cfg = getMultiselectConfig(sectionId);
      if (cfg && cfg.catalog && cfg.catalog !== "serial_store") continue;
      for (const row of rows || []) {
        const g = String(row.group || "Default").trim() || "Default";
        if (g.toLowerCase() !== "all") names.add(g);
      }
    }
  } catch {
    /* ignore */
  }
  return [...names].sort((a, b) => a.localeCompare(b));
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
  if (section.serialSendList || title === "send" || title.startsWith("send serial")) return "send";
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
  if (active === "codes") return "Codes + Lootlemon community codes — Refresh if the list is empty.";
  if (active === "mail") return "Mailbox / Reward Center — open pending rewards here.";
  return "Send serials. Open Builds for saved item sets, or use Codes / Lootlemon and Mail here.";
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
  // Codes tab: force a fresh list load so Lootlemon is not stuck empty after browsing GZO.
  if (active === "library") {
    bustSerialStoreCatalog();
    tabContent.querySelectorAll("[data-multiselect-section]").forEach((box) => {
      const sectionId = box.dataset.multiselectSection;
      const configJson = box.dataset.multiselectConfig;
      if (!sectionId || !configJson) return;
      try {
        const config = JSON.parse(configJson);
        if (config.catalog !== "serial_store") return;
        refreshMultiselectSection(sectionId, config).catch(() => {});
      } catch {
        /* ignore */
      }
    });
  }
  if (active === "codes") {
    for (const key of [...catalogCache.keys()]) {
      if (String(key).startsWith("gzo:") || String(key).startsWith("lootlemon:")) {
        catalogCache.delete(key);
      }
    }
    tabContent.querySelectorAll("[data-multiselect-section]").forEach((box) => {
      if (box.closest(".hidden")) return;
      const sectionId = box.dataset.multiselectSection;
      const configJson = box.dataset.multiselectConfig;
      if (!sectionId || !configJson) return;
      try {
        const config = JSON.parse(configJson);
        if (config.catalog !== "gzo" && config.catalog !== "lootlemon") return;
        refreshMultiselectSection(sectionId, config).catch(() => {});
      } catch {
        /* ignore */
      }
    });
  }
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
    if (row.id === "codes") {
      btn.title = "Browse Codes and Lootlemon catalogs";
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

function deskBandKey(section) {
  return String(section?.lobby_band || section?.desk_band || section?.compact_band || "")
    .trim()
    .toLowerCase();
}

function isDeskBandHeader(section) {
  return Boolean(
    section?.lobby_band_header || section?.desk_band_header || section?.compact_band_header
  );
}

/** Group Desk sections into intro + bands so we can mount one band at a time. */
function groupDeskSections(sections) {
  const intro = [];
  const bands = [];
  let current = null;
  for (const section of sections || []) {
    if (!section || typeof section !== "object") continue;
    if (isDeskBandHeader(section)) {
      const bandKey = deskBandKey(section);
      if (!bandKey) continue;
      current = {
        id: bandKey,
        header: section,
        sections: [],
      };
      bands.push(current);
      continue;
    }
    if (!current) {
      intro.push(section);
      continue;
    }
    current.sections.push(section);
  }
  return { intro, bands };
}

function mountDeskBand(band, bodyEl, tabId) {
  if (!band || !bodyEl || bodyEl.dataset.mounted === "1") return;
  bodyEl.dataset.mounted = "1";
  bodyEl.textContent = "";
  const parts = [];
  // Use the real tool tab id (auto_lobby, loot, …) so field keys / Save / Start
  // match Tabs mode — never "lobby:…" or Compact settings go missing.
  const fieldTabId = String(band.id || tabId || "lobby").trim() || "lobby";
  if (band.header && (band.header.quickLinks || band.header.actions || band.header.fields)) {
    // Header already rendered above; only mount body sections here.
  }
  for (const section of band.sections || []) {
    const sectionEl = renderSection(section, fieldTabId);
    if (sectionEl) {
      bodyEl.appendChild(sectionEl);
      parts.push(sectionEl);
    }
  }
  if (!parts.length) {
    const empty = document.createElement("p");
    empty.className = "muted small";
    empty.textContent = "Nothing in this band.";
    bodyEl.appendChild(empty);
  }
  armDeskLazyCatalogs();
  if (actionsEnabled()) {
    // Catalog <select>s only for this freshly mounted band — not the whole Desk.
    reloadCatalogSelectsIn(bodyEl);
  }
  if (band.id === "toggles") fillTogglesBoard();
  if (band.id === "keybinds" && actionsEnabled()) {
    const host = bodyEl.querySelector("[data-keybinds-editor]");
    if (host) refreshKeybindsEditor(host);
  }
  if (band.id === "log") {
    // Embed only — no floating runtime overlay.
    refreshLiveLogPanel().catch(() => {});
  }
  if (band.id === "vehicle" && actionsEnabled()) {
    window.sqbt.postAction("vehicle_spawn_catalog_reload", { deep: false }).catch(() => {});
  }
  if (["damage", "resources", "vehicle", "mobility"].includes(band.id) && actionsEnabled()) {
    const moduleMap = { damage: "bdam", resources: "brc", vehicle: "bvm", mobility: "bpm" };
    const mod = moduleMap[band.id];
    if (mod) {
      window.sqbt.postAction("tuning_status", { module: mod }).then(({ data }) => {
        if (data?.values) applyFieldValues(data.values);
      });
    }
  }
  if (band.id === "auto_lobby" && actionsEnabled()) {
    prefillAutoLobbyFields();
  }
}

function expandDeskBand(bandId, { scroll = true } = {}) {
  if (!tabContent || tabContent.dataset.activeTab !== "lobby") return;
  const safeId = String(bandId || "").trim().toLowerCase();
  if (!safeId) return;
  const wrap = tabContent.querySelector(`[data-desk-band-wrap="${CSS.escape(safeId)}"]`);
  if (!wrap) return;
  // Accordion: unmount other bands so Desk never holds the whole UI in DOM.
  tabContent.querySelectorAll("[data-desk-band-wrap]").forEach((other) => {
    if (other === wrap) return;
    other.classList.remove("desk-band-open");
    const otherBody = other.querySelector("[data-desk-band-body]");
    if (!otherBody) return;
    otherBody.hidden = true;
    if (otherBody.dataset.mounted === "1") {
      otherBody.dataset.mounted = "0";
      otherBody.innerHTML =
        '<p class="muted small">Click Open or Jump to load this area.</p>';
    }
  });
  wrap.classList.add("desk-band-open");
  const body = wrap.querySelector("[data-desk-band-body]");
  if (body) {
    body.hidden = false;
    const band = deskBandCache.get(safeId);
    if (band) mountDeskBand(band, body, "lobby");
  }
  tabContent.querySelectorAll(".desk-jump-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.deskBand === safeId);
  });
  if (scroll) {
    wrap.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

const deskBandCache = new Map();

function paintLobbyAccordion(tab) {
  deskBandCache.clear();
  disconnectDeskCatalogObserver();
  const { intro, bands } = groupDeskSections(tab.sections || []);

  for (const section of intro) {
    const sectionEl = renderSection(section, tab.id);
    if (sectionEl) tabContent.appendChild(sectionEl);
  }

  const nav = document.createElement("nav");
  nav.className = "desk-jump-nav";
  nav.setAttribute("aria-label", "Compact areas");
  const kicker = document.createElement("p");
  kicker.className = "desk-jump-kicker muted small";
  kicker.textContent = "Open one area (keeps the bridge happy)";
  nav.appendChild(kicker);
  const row = document.createElement("div");
  row.className = "desk-jump-row";

  for (const band of bands) {
    deskBandCache.set(band.id, band);
    const wrap = document.createElement("section");
    wrap.className = "desk-band-wrap";
    wrap.dataset.deskBandWrap = band.id;
    wrap.id = `sqbt-desk-${band.id}`;

    const headerEl = renderSection(band.header, tab.id);
    if (headerEl) {
      headerEl.classList.add("panel-section-desk-divider");
      const openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.className = "desk-band-open-btn";
      openBtn.textContent = "Open";
      openBtn.addEventListener("click", () => expandDeskBand(band.id, { scroll: false }));
      headerEl.appendChild(openBtn);
      wrap.appendChild(headerEl);
    }

    const body = document.createElement("div");
    body.className = "desk-band-body";
    body.dataset.deskBandBody = band.id;
    body.hidden = true;
    const placeholder = document.createElement("p");
    placeholder.className = "muted small";
    placeholder.textContent = "Click Open or Jump to load this area.";
    body.appendChild(placeholder);
    wrap.appendChild(body);
    tabContent.appendChild(wrap);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "desk-jump-btn";
    btn.dataset.deskBand = band.id;
    btn.textContent = DESK_JUMP_LABELS[band.id] || String(band.header?.title || band.id);
    btn.title = String(band.header?.title || band.id);
    btn.addEventListener("click", () => expandDeskBand(band.id, { scroll: true }));
    row.appendChild(btn);
  }

  nav.appendChild(row);
  tabContent.prepend(nav);
}

function renderLobbyView() {
  const layout = manifest?.lobby;
  if (!layout?.sections?.length) {
    tabContent.innerHTML =
      '<div class="panel-section"><h3>Compact</h3><p class="muted">Compact layout unavailable — use Tabs mode.</p></div>';
    return;
  }
  parkEditorFrameIfNeeded();
  tabContent.innerHTML = "";
  tabContent.dataset.activeTab = "lobby";
  catalogCache.clear();
  lastRosterSignature = "";
  stopLiveLogPolling();
  disconnectDeskCatalogObserver();
  // Never show the floating runtime-log overlay when entering Compact.
  document.getElementById("sqbt-runtime-log-panel")?.classList.add("hidden");
  paintLobbyAccordion({ id: "lobby", sections: layout.sections });
  renderProgressPanel(null, null, null);
  refreshActionButtons();
  if (actionsEnabled()) pollProgressOnce();
}

function reloadCatalogSelectsIn(root) {
  const scope = root || tabContent;
  if (!scope) return;
  for (const node of scope.querySelectorAll("[data-role='catalog-select']")) {
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
}

const DESK_JUMP_LABELS = Object.freeze({
  editor: "Editor",
  home: "Home",
  auto_lobby: "Auto",
  serials: "Serials",
  loot: "Loot",
  loot_shapes: "Shapes",
  progression: "Progress",
  player: "Player",
  mobility: "Fly",
  vehicle: "Vehicle",
  damage: "Damage",
  resources: "Kits",
  world: "World",
  toggles: "Toggles",
  keybinds: "Keys",
  faafo: "FAAFO",
  mob_io: "Mob/IO",
  freecam: "Freecam",
  display: "Display",
  pack_bay: "Save",
  party_bay: "Live",
  log: "Log",
  support: "Help",
});

let deskCatalogObserver = null;

function disconnectDeskCatalogObserver() {
  if (deskCatalogObserver) {
    deskCatalogObserver.disconnect();
    deskCatalogObserver = null;
  }
}

function ensureDeskLazyCatalog(box) {
  if (!box || box.dataset.lazyCatalog !== "1") return;
  if (box.dataset.lazyCatalogLoaded === "1") return;
  box.dataset.lazyCatalogLoaded = "1";
  const sectionId = box.dataset.multiselectSection;
  const configJson = box.dataset.multiselectConfig;
  if (!sectionId || !configJson) return;
  try {
    const config = JSON.parse(configJson);
    refreshMultiselectSection(sectionId, config).catch(() => {});
  } catch {
    /* ignore */
  }
}

function loadDeskBandLazyCatalogs(bandEl) {
  if (!bandEl || !tabContent) return;
  let node = bandEl.nextElementSibling;
  while (node) {
    if (node.classList?.contains("panel-section-desk-band")) break;
    node.querySelectorAll?.("[data-multiselect-section][data-lazy-catalog='1']").forEach((box) => {
      ensureDeskLazyCatalog(box);
    });
    if (node.matches?.("[data-multiselect-section][data-lazy-catalog='1']")) {
      ensureDeskLazyCatalog(node);
    }
    node = node.nextElementSibling;
  }
}

function armDeskLazyCatalogs() {
  disconnectDeskCatalogObserver();
  if (!tabContent || tabContent.dataset.activeTab !== "lobby") return;
  const boxes = tabContent.querySelectorAll("[data-multiselect-section][data-lazy-catalog='1']");
  if (!boxes.length) return;
  deskCatalogObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        ensureDeskLazyCatalog(entry.target);
        deskCatalogObserver?.unobserve(entry.target);
      }
    },
    { root: null, rootMargin: "160px 0px", threshold: 0.01 }
  );
  for (const box of boxes) deskCatalogObserver.observe(box);
}

async function loadCatalog(name, params = {}) {
  const key = catalogCacheKey(name, params);
  // Saved libraries can change through the in-game menu or another app window.
  // Fetch them when opened; never retain a startup empty result indefinitely.
  if (name !== "serial_store" && name !== "serial_groups" && catalogCache.has(key)) {
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
  // Mob/IO catalogs are 1600–2100+ rows — 2000 clipped IO All and hid whole categories.
  const catalog = String(config?.catalog || "");
  const params = {
    limit: catalog === "io_spawns" || catalog === "mob_actors" ? 10000 : 2000,
  };
  params.search = fieldValues[`${sectionId}:search`] || "";
  for (const filter of config.filters || []) {
    const param = filter.catalogParam || filter.key;
    params[param] = fieldValues[`${sectionId}:${filter.key}`] ?? filter.default ?? "";
  }
  if ((config.kind || "") === "backpack" || config.catalog === "backpack") {
    const players = latestStatus?.raw?.players || [];
    const sectionPlayer =
      fieldValues[sectionFieldKey(sectionId, { key: "player_index" })] ??
      fieldValues[`${sectionId}:player_index`];
    let idx =
      sectionPlayer !== undefined && sectionPlayer !== ""
        ? Number(sectionPlayer)
        : preferredDeliveryPlayerIndex(players);
    // Live Pack never digs "All players".
    if (config.params?.party_bay && Number(idx) === -1) {
      idx = preferredDeliveryPlayerIndex(players.filter((p) => Number(p.index) !== -1));
    }
    if (Number.isFinite(idx)) params.player_index = Number(idx);
  }
  if (config.params && typeof config.params === "object") {
    Object.assign(params, config.params);
  }
  // Item lists paint from the saved name. Card hover decodes. A full-pack
  // decode here made Save / New list sit on "Loading…" so the pack looked missing.
  if (config.catalog === "serial_store") params.enrich_limit = 0;
  return params;
}

function multiselectRowId(row, config) {
  const idKey = config.idKey || config.valueKey || "id";
  return String(row[idKey] || row.serial || row.id || "");
}

function isDeliverableSerial(serial) {
  const s = String(serial || "").trim();
  if (!s) return false;
  // Whole @U only — never deliver a mid-serial fragment (one item → two backpack junk).
  if (s.startsWith("@U")) {
    if (/\s/.test(s)) return false;
    if (s.length < 12) return false;
    return true;
  }
  return s.includes(",") && /\d/.test(s);
}

/** Keep whole @U codes; never mid-cut Base85. Preserve every selected row (incl. dups). */
function sanitizeDeliverableSerials(serials) {
  const out = [];
  for (const raw of serials || []) {
    let s = String(raw || "").trim();
    if (!s) continue;
    if (s.startsWith("@U")) {
      // Already one contiguous code (GZO row / catalog) — do not re-split.
      if (!/\s/.test(s) && isDeliverableSerial(s)) {
        out.push(s);
        continue;
      }
      // Multi-line / whitespace paste only: split on whitespace-bounded @Ug.
      const parts = splitBase85SerialBlob(s);
      for (const part of parts.length ? parts : [s]) {
        const token = String(part || "").trim();
        if (!isDeliverableSerial(token)) continue;
        out.push(token);
      }
      continue;
    }
    if (!isDeliverableSerial(s)) continue;
    out.push(s);
  }
  return out;
}

function catalogShowItemCards() {
  try {
    const v = localStorage.getItem(CATALOG_CARD_KEY);
    // Default ON — in-game Cohtml cards. Toggle must fully hide when off.
    if (v === null || v === "") return true;
    return v === "1";
  } catch {
    return true;
  }
}

function setCatalogShowItemCards(on) {
  try {
    localStorage.setItem(CATALOG_CARD_KEY, on ? "1" : "0");
  } catch {
    /* ignore */
  }
  if (!on) {
    if (catalogPreviewDebounceTimer) {
      clearTimeout(catalogPreviewDebounceTimer);
      catalogPreviewDebounceTimer = 0;
    }
    catalogPreviewDebounceSerial = "";
    document.querySelectorAll(".sqbt-catalog-native-preview").forEach((host) => {
      host.hidden = true;
      host.replaceChildren();
      delete host.dataset.seeded;
      delete host.dataset.previewKey;
      delete host.dataset.paintReq;
      const split = host.closest(".catalog-preview-split");
      if (split) split.classList.add("cards-off");
    });
  } else {
    document.querySelectorAll(".catalog-preview-split.cards-off").forEach((split) => {
      split.classList.remove("cards-off");
    });
  }
}

function rarityCardClass(rarity) {
  const r = String(rarity || "").toLowerCase();
  if (r.includes("pearl") || r.includes("pearlescent")) return "rarity-pearl";
  if (r.includes("legend")) return "rarity-legendary";
  if (r.includes("epic") || r.includes("purple")) return "rarity-epic";
  if (r.includes("rare") || r.includes("blue")) return "rarity-rare";
  if (r.includes("uncommon") || r.includes("green")) return "rarity-uncommon";
  if (r.includes("common") || r.includes("white")) return "rarity-common";
  if (r.includes("unique") || r.includes("orange")) return "rarity-legendary";
  return "rarity-unknown";
}

function catalogCardPropsFromRow(row, title, sectionId = "") {
  const decoded = String(row.full_name || row.display_name || "").trim();
  const rawTitle = String(title || "").trim();
  // Card title = decoded game name when known; never fall back to a raw @U serial.
  const cardTitle =
    (decoded && !/^@U/i.test(decoded) ? decoded : "") ||
    (rawTitle && !/^@U/i.test(rawTitle) ? rawTitle : "") ||
    String(row.type_label || row.item_type || row.type || "").trim() ||
    "Item";
  const rarityGuess =
    row.rarity ||
    (/\blegend/i.test(cardTitle) ? "Legendary" : "") ||
    (/\bpearl/i.test(cardTitle) ? "Pearlescent" : "") ||
    (/\bepic/i.test(cardTitle) ? "Epic" : "") ||
    (/\brare/i.test(cardTitle) ? "Rare" : "") ||
    "Legendary";
  const rawType = row.type || row.item_type || row.weapon_type || row.category || "";
  const partsFromNames = Array.isArray(row.part_names)
    ? row.part_names
        .map((x) =>
          String(x || "")
            .replace(/^.*\./, "")
            .replace(/[_-]+/g, " ")
            .trim()
        )
        .filter(Boolean)
    : [];
  const parts = Array.isArray(row.parts)
    ? row.parts
    : Array.isArray(row.perk_lines)
      ? row.perk_lines
      : partsFromNames;
  const bakedLevel =
    row.level != null && row.level !== "" && Number.isFinite(Number(row.level))
      ? Number(row.level)
      : null;
  const props = {
    title: cardTitle,
    display_name: decoded && !/^@U/i.test(decoded) ? decoded : "",
    card_name: String(row.card_name || "").trim(),
    full_name: String(row.full_name || "").trim(),
    user_label: String(row.user_label || row.name || "").trim(),
    rarity: rarityGuess,
    level: bakedLevel != null ? bakedLevel : "",
    // Keep baked serial level for Override=no even after UI level overwrites `level`.
    serial_level: bakedLevel != null ? bakedLevel : "",
    manufacturer: row.manufacturer || row.maker || "",
    itemType: rawType,
    type_label: row.type_label || "",
    listing: row.listing || "",
    parts,
    perk_rows: Array.isArray(row.perk_rows) ? row.perk_rows : [],
    stats: Array.isArray(row.stats) ? row.stats : [],
    element: row.element || row.damage_type || "",
    serial: row.serial || "",
    red_text: Array.isArray(row.red_text) ? row.red_text : [],
    part_names: Array.isArray(row.part_names) ? row.part_names : [],
    set: row.set || "",
    type_id: row.type_id || "",
  };
  if (sectionId) props._catalogSectionId = String(sectionId);
  // Seed level from Serials UI before enrich when the row has none (GZO cache).
  if (!(Number(props.level) > 0) && sectionId) {
    props.level = resolveNexusCardLevel(props, sectionId);
  }
  return props;
}

let partsStatsLoadPromise = null;
let weaponStatsLoadPromise = null;

function ensurePartsStatsData() {
  if (window.PARTS_STATS_DATA && window.PARTS_STATS_DATA.by_part_code) {
    return Promise.resolve(window.PARTS_STATS_DATA);
  }
  if (partsStatsLoadPromise) return partsStatsLoadPromise;
  partsStatsLoadPromise = new Promise((resolve) => {
    const existing = document.querySelector('script[data-sqbt-parts-stats="1"]');
    if (existing) {
      const wait = () => {
        if (window.PARTS_STATS_DATA?.by_part_code) resolve(window.PARTS_STATS_DATA);
        else setTimeout(wait, 40);
      };
      wait();
      return;
    }
    const script = document.createElement("script");
    script.src = "editor/data/parts_stats_data.js";
    script.async = true;
    script.dataset.sqbtPartsStats = "1";
    script.onload = () => resolve(window.PARTS_STATS_DATA || null);
    script.onerror = () => resolve(null);
    document.head.appendChild(script);
  });
  return partsStatsLoadPromise;
}

function ensureWeaponStatsData() {
  if (window.WEAPON_STATS_DATA) {
    return Promise.resolve(window.WEAPON_STATS_DATA);
  }
  if (weaponStatsLoadPromise) return weaponStatsLoadPromise;
  weaponStatsLoadPromise = fetch("editor/data/weapon_stats_data.js")
    .then((r) => r.text())
    .then((text) => {
      const patched = String(text || "").replace(
        /^\s*(?:const|let|var)\s+WEAPON_STATS_DATA\s*=/,
        "window.WEAPON_STATS_DATA ="
      );
      // eslint-disable-next-line no-eval
      (0, eval)(patched);
      return window.WEAPON_STATS_DATA || null;
    })
    .catch(() => null);
  return weaponStatsLoadPromise;
}

function lookupPartStatRows(byCode, partCode) {
  if (!byCode || !partCode) return null;
  const raw = String(partCode).trim();
  if (!raw) return null;
  if (byCode[raw]) return byCode[raw];
  const low = raw.toLowerCase();
  if (byCode[low]) return byCode[low];
  const leaf = raw.includes(".") ? raw.slice(raw.lastIndexOf(".") + 1) : raw;
  if (byCode[leaf]) return byCode[leaf];
  if (byCode[leaf.toLowerCase()]) return byCode[leaf.toLowerCase()];
  const hit = Object.keys(byCode).find(
    (k) => k.toLowerCase() === low || k.toLowerCase().endsWith("." + leaf.toLowerCase())
  );
  return hit ? byCode[hit] : null;
}

function _weaponTypeCodeFromParts(partNames, itemType) {
  const blob = `${(partNames || []).join(" ")} ${itemType || ""}`.toLowerCase();
  if (/\b(sg|shotgun)\b/.test(blob) || /\.sg\./.test(blob)) return "SG";
  if (/\b(sm|smg)\b/.test(blob) || /\.sm\./.test(blob)) return "SM";
  if (/\b(ar|assault)\b/.test(blob) || /\.ar\./.test(blob)) return "AR";
  if (/\b(ps|pistol)\b/.test(blob) || /\.ps\./.test(blob)) return "PS";
  if (/\b(sr|sniper)\b/.test(blob) || /\.sr\./.test(blob)) return "SR";
  if (/\b(hw|heavy)\b/.test(blob) || /\.hw\./.test(blob)) return "HW";
  const t = String(itemType || "").toLowerCase();
  if (t.includes("shotgun")) return "SG";
  if (t.includes("smg") || t.includes("submachine")) return "SM";
  if (t.includes("assault") || (t.includes("rifle") && !t.includes("sniper"))) return "AR";
  if (t.includes("pistol")) return "PS";
  if (t.includes("sniper")) return "SR";
  if (t.includes("heavy")) return "HW";
  return "";
}

function _mfrPrefixFromParts(partNames, manufacturer) {
  const map = {
    jakobs: "JAK",
    daedalus: "DAD",
    tediore: "TED",
    torgue: "TOR",
    order: "ORD",
    vladof: "VLA",
    maliwan: "MAL",
    ripper: "BOR",
    borg: "BOR",
    atlas: "ATL",
    hyperion: "HYP",
    cov: "COV",
  };
  const m = String(manufacturer || "").toLowerCase();
  for (const [name, pref] of Object.entries(map)) {
    if (m.includes(name)) return pref;
  }
  const blob = (partNames || []).join(" ").toLowerCase();
  for (const [name, pref] of Object.entries(map)) {
    if (blob.includes(name) || blob.includes(pref.toLowerCase() + "_")) return pref;
  }
  return "";
}

function _lookupWeaponInitRow(table, partLeaf, mfrPrefix) {
  if (!table?.rows) return null;
  const leaf = String(partLeaf || "")
    .replace(/^part_/i, "")
    .toLowerCase();
  const keys = Object.keys(table.rows);
  for (const rowName of keys) {
    if (leaf && rowName.toLowerCase().includes(leaf)) return table.rows[rowName];
  }
  if (mfrPrefix) {
    const nums = leaf.match(/(\d+)/g) || [];
    for (const rowName of keys) {
      if (!rowName.toUpperCase().startsWith(mfrPrefix)) continue;
      if (!nums.length) return table.rows[rowName];
      const rNums = rowName.match(/(\d+)/g) || [];
      if (nums.some((n) => rNums.includes(n))) return table.rows[rowName];
    }
  }
  return null;
}

function estimateWeaponPrimaryStats(partNames, itemType, manufacturer, level = 70) {
  const W = window.WEAPON_STATS_DATA;
  const by = window.PARTS_STATS_DATA?.by_part_code;
  if (!W || !Array.isArray(partNames) || !partNames.length) return [];
  const typeCode = _weaponTypeCodeFromParts(partNames, itemType);
  if (!typeCode) return [];
  const mfrPrefix = _mfrPrefixFromParts(partNames, manufacturer);
  let barrelRow = null;
  let magRow = null;
  for (const code of partNames) {
    const leaf = String(code).includes(".")
      ? String(code).slice(String(code).lastIndexOf(".") + 1)
      : String(code);
    const low = leaf.toLowerCase();
    if (!barrelRow && /barrel|unique_barrel/.test(low)) {
      barrelRow = _lookupWeaponInitRow(W[`Weapon_${typeCode}_Barrel_Init`], leaf, mfrPrefix);
    }
    if (!magRow && /(^|_)mag(_|$)|magazine/.test(low)) {
      magRow = _lookupWeaponInitRow(W[`Weapon_${typeCode}_Magazine_Init`], leaf, mfrPrefix);
    }
  }
  if (!barrelRow) {
    const table = W[`Weapon_${typeCode}_Barrel_Init`];
    if (table?.rows) {
      const keys = Object.keys(table.rows);
      const prefer = mfrPrefix
        ? keys.find((k) => k.toUpperCase().startsWith(mfrPrefix))
        : keys[0];
      barrelRow = table.rows[prefer] || table.rows[keys[0]] || null;
    }
  }
  if (!magRow) {
    const table = W[`Weapon_${typeCode}_Magazine_Init`];
    if (table?.rows) {
      const keys = Object.keys(table.rows);
      const prefer = mfrPrefix
        ? keys.find((k) => k.toUpperCase().startsWith(mfrPrefix))
        : keys[0];
      magRow = table.rows[prefer] || table.rows[keys[0]] || null;
    }
  }
  let damageScale = Number(barrelRow?.damage_scale) || 1;
  let fireRate = Number(barrelRow?.firerate_value) || 0;
  let accuracy = Number(barrelRow?.accuracy_value) || 0;
  let reload = Number(magRow?.reloadtime_value) || 0;
  let magazine = Number(magRow?.maxloadedammo_value) || 0;
  if (Number(magRow?.damage_scale) > 0) damageScale *= Number(magRow.damage_scale);
  const mfrName = Object.keys(W.WeaponManufacturer_Init?.rows || {}).find((k) =>
    String(manufacturer || "")
      .toLowerCase()
      .includes(k.toLowerCase())
  );
  const mfrRow = mfrName ? W.WeaponManufacturer_Init.rows[mfrName] : null;
  if (Number(mfrRow?.damage_scale) > 0) damageScale *= Number(mfrRow.damage_scale);
  if (Number(mfrRow?.firerate_scale) > 0) fireRate *= Number(mfrRow.firerate_scale);

  if (by) {
    for (const code of partNames) {
      const rows = lookupPartStatRows(by, code);
      if (!Array.isArray(rows)) continue;
      for (const row of rows) {
        const field = String(row.stat_field || "").toLowerCase();
        const combine = String(row.combine || "").toLowerCase();
        let val = Number(row.stat_value);
        if (!Number.isFinite(val) || val <= 0) continue;
        if (row.invert) val = 1 / val;
        if (field === "damage_scale" && (combine === "mul" || combine === "scale" || !combine)) {
          damageScale *= val;
        } else if (field.includes("firerate") && field.includes("scale")) {
          fireRate *= val;
        } else if (field.includes("reload") && field.includes("scale")) {
          reload *= val;
        } else if (field.includes("accuracy") && field.includes("scale")) {
          accuracy *= val;
        } else if (field.includes("mag") && field.includes("scale")) {
          magazine *= val;
        }
      }
    }
  }

  // Offline est: init tables are relative — map into L70-ish Nexus card range.
  // Old *850 read as mid-game even when parts said legendary.
  const levelHint = Number(level);
  const lvl = Number.isFinite(levelHint) && levelHint > 0 ? levelHint : 70;
  const damage = Math.max(1, Math.round(damageScale * (140 + lvl * 140)));
  const out = [];
  if (damage > 1) out.push({ label: "Damage", value: String(damage) });
  if (accuracy > 0) out.push({ label: "Accuracy", value: `${Math.round(accuracy * 10) / 10}%` });
  if (reload > 0) out.push({ label: "Reload", value: `${Math.round(reload * 100) / 100}s` });
  if (fireRate > 0) out.push({ label: "Fire Rate", value: String(Math.round(fireRate * 100) / 100) });
  if (magazine > 0) out.push({ label: "Magazine", value: String(Math.round(magazine)) });
  if (damage > 1 && fireRate > 0) {
    out.push({ label: "DPS", value: String(Math.round(damage * fireRate)) });
  }
  return out;
}

function scaleStatsFromPartNames(partNames) {
  const data = window.PARTS_STATS_DATA;
  const by = data?.by_part_code;
  if (!by || !Array.isArray(partNames) || !partNames.length) return [];
  const SCALE_LABELS = {
    damage_scale: "Damage",
    firerate_scale: "Fire Rate",
    fire_rate_scale: "Fire Rate",
    reload_scale: "Reload",
    reloadtime_scale: "Reload",
    accuracy_scale: "Accuracy",
    magsize_scale: "Magazine",
    magazine_scale: "Magazine",
    crit_scale: "Crit",
    criticalhitdamage_scale: "Crit",
  };
  const acc = Object.create(null);
  for (const code of partNames) {
    const rows = lookupPartStatRows(by, code);
    if (!Array.isArray(rows)) continue;
    for (const row of rows) {
      if (!row) continue;
      const field = String(row.stat_field || "").toLowerCase();
      const label = SCALE_LABELS[field];
      if (!label) continue;
      const combine = String(row.combine || "").toLowerCase();
      let val = Number(row.stat_value);
      if (!Number.isFinite(val)) continue;
      if (combine === "mul" || combine === "scale" || field.endsWith("_scale")) {
        if (val <= 0) continue;
        if (row.invert) val = val !== 0 ? 1 / val : val;
        acc[label] = (acc[label] == null ? 1 : acc[label]) * val;
      }
    }
  }
  const out = [];
  for (const label of ["Damage", "Fire Rate", "Reload", "Accuracy", "Magazine", "Crit"]) {
    const mult = acc[label];
    if (!Number.isFinite(mult) || Math.abs(mult - 1) < 0.001) continue;
    const pct = (mult - 1) * 100;
    const pretty =
      Math.abs(pct) < 500
        ? `${pct >= 0 ? "+" : ""}${pct.toFixed(0)}% ${label}`
        : `${label} ×${mult.toFixed(2)}`;
    out.push({ label: `${label} scale`, value: pretty });
  }
  return out;
}

/** Never soft-cap classmod secondary — modded classmods need every perk/part row. */
function softCapNativeSecondary(secondary, itemType) {
  return Array.isArray(secondary) ? secondary : [];
}

/**
 * Card Nexus level for Codes/GZO/Lootlemon/Editor preview.
 * - Override level ON → UI level box (card Lvl + stat math).
 * - Override OFF → item/serial baked level when known.
 * - Editor / locked preview → explicit props.level.
 * - Else endgame 70 so thin catalog rows are not stuck at baked L1–30 Damage.
 */
function resolveNexusCardLevel(props, sectionId) {
  const base = props && typeof props === "object" ? props : {};
  const sid =
    String(sectionId || base._catalogSectionId || "").trim() ||
    String(base._previewSectionId || "").trim();
  const hasOverrideToggle =
    Boolean(sid) && fieldValues[`${sid}:level_override`] !== undefined;
  const overrideRaw = hasOverrideToggle
    ? String(fieldValues[`${sid}:level_override`] ?? "yes").toLowerCase()
    : "";
  const overrideOn = hasOverrideToggle
    ? overrideRaw === "yes" || overrideRaw === "true"
    : true;
  if (sid && overrideOn) {
    const rawUi = Number(fieldValues[`${sid}:level`]);
    if (Number.isFinite(rawUi) && rawUi > 0) return rawUi;
  }
  if (hasOverrideToggle && !overrideOn) {
    const serialLvl = Number(base.serial_level ?? base.raw?.level ?? base.level);
    if (Number.isFinite(serialLvl) && serialLvl > 0) return serialLvl;
  }
  const explicit = Number(base.level);
  if (
    Number.isFinite(explicit) &&
    explicit > 0 &&
    (base._previewLevelLocked || base._fromEditor)
  ) {
    return explicit;
  }
  if (Number.isFinite(explicit) && explicit > 0 && !hasOverrideToggle) {
    return explicit;
  }
  return 70;
}

/** Re-paint the section preview card after Override / level box changes. */
function refreshCatalogCardsForSectionLevel(sectionId) {
  const sid = String(sectionId || "").trim();
  if (!sid) return;
  const host =
    document.querySelector(`[data-catalog-preview="${sid}"]`) ||
    document.querySelector(`[data-multiselect-section="${sid}"] .catalog-preview-host`) ||
    document.querySelector(`[data-multiselect-section="${sid}"] [data-catalog-preview]`);
  if (!host) return;
  const serial = String(host.dataset.previewSerial || "").trim();
  if (!serial) return;
  const serialLevel = Number(host.dataset.previewSerialLevel);
  delete host.dataset.previewKey;
  const base = {
    serial,
    _catalogSectionId: sid,
    serial_level: Number.isFinite(serialLevel) && serialLevel > 0 ? serialLevel : "",
  };
  paintCatalogNativePreview(host, {
    ...base,
    level: resolveNexusCardLevel(base, sid),
    _previewLevelLocked: true,
  }).catch(() => {});
}

async function attachPartScaleStats(props) {
  let base = props && typeof props === "object" ? props : {};
  const serialForAnalysis = String(base.serial || "").trim();
  if (serialForAnalysis.startsWith("@U") && typeof window.sqbt?.analyzeItem === "function") {
    try {
      const analyzed = await window.sqbt.analyzeItem(serialForAnalysis, {
        level: resolveNexusCardLevel(base),
      });
      if (analyzed?.ok && analyzed?.card_props) {
        // Decoded identity/parts fill gaps; explicit preview choices (notably a
        // requested level) remain presentation inputs until Build repacks them.
        base = {
          ...analyzed.card_props,
          ...base,
          // The final serial owns parts, element and stats; UI snapshots can
          // arrive late or contain empty arrays while the builder imports.
          ...analyzed.card_props,
          title: base.title || analyzed.card_props.display_name,
          level: base.level || analyzed.card_props.level,
          serial: analyzed.serial,
          identity: analyzed.identity,
          provenance: analyzed.provenance,
          unknowns: analyzed.unknowns,
          conflicts: analyzed.conflicts,
        };
      }
    } catch {
      // Existing card fallback remains available when deterministic analysis
      // cannot run (for example, Python is absent on an unpacked dev machine).
    }
  }
  const hasDamageHeadline = (stats) =>
    Array.isArray(stats) &&
    stats.some((s) => {
      const lab = String(s?.label || s?.key || "").trim();
      if (!/^(damage|dps)$/i.test(lab)) return false;
      const n = Number(String(s?.value ?? "").replace(/,/g, "").replace(/[^\d.-]/g, ""));
      return Number.isFinite(n) && n > 0;
    });
  const pickPositiveStat = (preferred, fallback) => {
    const a = Number(preferred);
    if (Number.isFinite(a) && a > 0) return a;
    const b = Number(fallback);
    if (Number.isFinite(b) && b > 0) return b;
    return null;
  };
  const itemTypeHint = String(base.itemType || base.type_label || base.type || "");
  const namesHint = Array.isArray(base.part_names) ? base.part_names : [];
  const equipBlobHint = `${itemTypeHint} ${namesHint.join(" ")}`.toLowerCase();
  const explicitWeaponType =
    /pistol|shotgun|smg|submachine|sniper|assault|rifle|heavy\s*(?:weapon|gun)/i.test(
      itemTypeHint
    );
  const explicitEquipmentType =
    /shield|repkit|repair|ordnance|grenade|gadget|enhancement|class\s*mod|classmod/i.test(
      itemTypeHint
    );
  // Modded weapons legitimately carry shield/gadget/classmod parts. Their
  // decoded serial-header type wins; foreign parts must not suppress Damage.
  const isNonGunEquipment =
    explicitEquipmentType ||
    (!explicitWeaponType &&
      /shield|repkit|repair|ordnance|grenade|gadget|enhancement|class\s*mod|classmod/.test(
        equipBlobHint
      ));
  // Prefer Nexus offline calc (closest to live BaseValues) when we have parts.
  const names = namesHint;
  if (
    (names.length || String(base.serial || "").startsWith("@U")) &&
    typeof window.sqbt?.nexusCardStats === "function"
  ) {
    try {
      const level = resolveNexusCardLevel(base);
      const nexus = await window.sqbt.nexusCardStats({
        serial: base.serial || "",
        part_names: names,
        itemType: base.type_label || base.itemType || base.type || "",
        type_label: base.type_label || "",
        manufacturer: base.manufacturer || "",
        set: base.set || "",
        rarity: base.rarity || "",
        level,
        element: base.element || base.damage_type || "",
        display_name: base.display_name || base.title || "",
        title: base.title || base.display_name || "",
      });
      const applyNexus = (src) => {
        const equipment =
          src.native_equipment ||
          src.raw?.native_equipment ||
          null;
        const secondary =
          (Array.isArray(src.native_secondary) && src.native_secondary.length
            ? src.native_secondary
            : null) ||
          (Array.isArray(src.raw?.native_secondary) && src.raw.native_secondary.length
            ? src.raw.native_secondary
            : null) ||
          base.native_secondary;
        const firmware =
          (Array.isArray(src.native_firmware) && src.native_firmware.length
            ? src.native_firmware
            : null) ||
          (Array.isArray(src.raw?.native_firmware) && src.raw.native_firmware.length
            ? src.raw.native_firmware
            : null) ||
          base.native_firmware;
        const firmwareBlock = src.firmware_block || src.raw?.firmware_block || base.firmware_block || null;
        const nativeGroups =
          (src.native_groups && typeof src.native_groups === "object"
            ? src.native_groups
            : null) ||
          (src.raw?.native_groups && typeof src.raw.native_groups === "object"
            ? src.raw.native_groups
            : null) ||
          base.native_groups ||
          {};
        const textLines =
          (Array.isArray(src.native_text) && src.native_text.length
            ? src.native_text
            : null) ||
          (Array.isArray(src.raw?.native_text) && src.raw.native_text.length
            ? src.raw.native_text
            : null) ||
          base.native_text ||
          base.manufacturer_flavor;
        const red =
          (Array.isArray(src.red_text) && src.red_text.length
            ? src.red_text
            : null) ||
          (Array.isArray(src.raw?.red_text) && src.raw.red_text.length
            ? src.raw.red_text
            : null) ||
          base.red_text;
        const inferredType =
          (src.raw && src.raw.item_type) ||
          base.type_label ||
          base.itemType ||
          base.type ||
          "";
        const partBlob = (Array.isArray(base.part_names) ? base.part_names : [])
          .concat(Array.isArray(names) ? names : [])
          .join(" ");
        const looksClassmod =
          /class\s*mod|classmod/i.test(`${inferredType} ${base.itemType || ""} ${base.type_label || ""}`) ||
          /classmod_/i.test(partBlob) ||
          (/passive_(?:blue|green|red)/i.test(partBlob) &&
            !/\.(?:part_barrel|part_grip|part_mag)_/i.test(partBlob));
        const looksNonGunEquip =
          looksClassmod ||
          isNonGunEquipment ||
          /enhancement|shield|repkit|repair|ordnance|grenade|gadget/i.test(
            `${base.itemType || ""} ${base.type_label || ""} ${base.type || ""}`
          );
        const gunLikeLeak = /pistol|shotgun|assault|smg|submachine|sniper|heavy|firewerk|eigenburst|juliet/i.test(
          `${inferredType} ${src.raw?.item_type || ""} ${src.display_name || ""} ${src.native_equipment?.type_label || ""}`
        );
        // Pearl/NCS gun typing must not stick after offline equipment resolve.
        let nextItemType = inferredType || base.itemType || base.type_label || "";
        let nextTypeLabel = base.type_label || inferredType || "";
        if (looksClassmod) {
          if (gunLikeLeak || !nextItemType) nextItemType = "Classmod";
          if (gunLikeLeak || !nextTypeLabel || /pistol|shotgun|assault|smg|sniper|heavy/i.test(nextTypeLabel)) {
            nextTypeLabel =
              String(src.native_equipment?.type_label || "").trim() ||
              (/class/i.test(String(inferredType)) ? inferredType : "Class Mod");
            if (/pistol|shotgun|assault|smg|sniper|heavy/i.test(nextTypeLabel)) {
              nextTypeLabel = "Class Mod";
            }
          }
        } else if (looksNonGunEquip) {
          nextItemType = base.itemType || base.type_label || inferredType;
          nextTypeLabel = base.type_label || base.itemType || inferredType;
          if (gunLikeLeak) {
            nextItemType = base.itemType || base.type_label || nextItemType;
            nextTypeLabel = base.type_label || base.itemType || nextTypeLabel;
          }
        } else {
          nextItemType = base.itemType || inferredType;
          nextTypeLabel = base.type_label || inferredType;
        }
        // When the live firmware widget can paint, keep tier text out of secondary.
        let mergedSecondary = Array.isArray(secondary) ? [...secondary] : [];
        if (!firmwareBlock && Array.isArray(firmware) && firmware.length) {
          const seen = new Set(
            mergedSecondary.map((r) => String(r?.value || "").toLowerCase().trim()).filter(Boolean)
          );
          for (const row of firmware) {
            const key = String(row?.value || "").toLowerCase().trim();
            if (!key || seen.has(key)) continue;
            seen.add(key);
            mergedSecondary.push(row);
          }
        }
        return {
          ...base,
          level,
          itemType: nextItemType,
          type_label: nextTypeLabel,
          set: (src.raw && src.raw.set) || base.set || "",
          full_name: String(src.full_name || src.raw?.full_name || base.full_name || "").trim(),
          display_name: (() => {
            const fromSrc = String(src.display_name || src.raw?.display_name || "").trim();
            const fromBase = String(base.display_name || base.title || "").trim();
            // Pearl/NCS gun names must not overwrite crafted equipment titles.
            if (
              looksNonGunEquip &&
              fromSrc &&
              gunLikeLeak &&
              fromBase &&
              !/^@U/i.test(fromBase)
            ) {
              return fromBase;
            }
            if (fromSrc && !/^@U/i.test(fromSrc)) return fromSrc;
            return fromBase && !/^@U/i.test(fromBase) ? fromBase : base.display_name;
          })(),
          title: (() => {
            const fromSrc = String(src.display_name || src.raw?.display_name || "").trim();
            const fromBase = String(base.display_name || base.title || "").trim();
            if (
              looksNonGunEquip &&
              fromSrc &&
              gunLikeLeak &&
              fromBase &&
              !/^@U/i.test(fromBase)
            ) {
              return fromBase;
            }
            if (fromSrc && !/^@U/i.test(fromSrc)) return fromSrc;
            return fromBase && !/^@U/i.test(fromBase) ? fromBase : base.title;
          })(),
          stats:
            looksNonGunEquip && gunLikeLeak
              ? Array.isArray(base.stats) && base.stats.length
                ? base.stats
                : (Array.isArray(src.stats) ? src.stats : []).filter(
                    (s) => !/^(damage|dps)$/i.test(String(s?.label || "").trim())
                  )
              : Array.isArray(src.stats) && src.stats.length
                ? src.stats
                : base.stats,
          stats_source: src.source || "offline_nexus",
          stats_note: src.ok ? "" : "Partial Nexus — unknown parts may still differ from GZO",
          element_text: src.raw?.element_text || base.element_text || "",
          element_text2: src.raw?.element_text2 || base.element_text2 || "",
          value: src.raw?.value != null ? src.raw.value : base.value,
          // Keep numeric Damage + DPS for comparisons/fallbacks. The Cohtml model
          // paints the native primary group instead of inventing a DPS headline.
          // Pearl gun duals must not inject weapon Damage onto Enhancement/etc.
          damage:
            looksNonGunEquip && gunLikeLeak
              ? null
              : pickPositiveStat(src.raw?.damage, base.damage),
          dps:
            looksNonGunEquip && gunLikeLeak
              ? null
              : pickPositiveStat(src.raw?.dps, base.dps),
          crit: src.raw?.crit != null ? src.raw.crit : base.crit,
          magazine: src.raw?.magazine != null ? src.raw.magazine : base.magazine,
          fire_rate: src.raw?.fire_rate != null ? src.raw.fire_rate : base.fire_rate,
          accuracy: src.raw?.accuracy != null ? src.raw.accuracy : base.accuracy,
          reload: src.raw?.reload != null ? src.raw.reload : base.reload,
          damage_radius: src.raw?.damage_radius != null ? src.raw.damage_radius : base.damage_radius,
          projectile_count:
            src.raw?.projectile_count != null ? src.raw.projectile_count : base.projectile_count,
          shot_cost: src.raw?.shot_cost != null ? src.raw.shot_cost : base.shot_cost,
          native_equipment: (() => {
            const eq = equipment || base.native_equipment;
            if (!(looksNonGunEquip && gunLikeLeak && eq && typeof eq === "object")) return eq;
            return {
              ...eq,
              type_label: nextTypeLabel || eq.type_label || nextItemType,
            };
          })(),
          native_groups:
            looksNonGunEquip && gunLikeLeak
              ? base.native_groups || {}
              : nativeGroups,
          native_secondary: softCapNativeSecondary(
            mergedSecondary,
            nextItemType || nextTypeLabel
          ),
          native_firmware: Array.isArray(firmware) ? firmware : base.native_firmware,
          firmware_block: firmwareBlock,
          manufacturer_flavor: Array.isArray(textLines) ? textLines : base.manufacturer_flavor,
          red_text: red,
          raw: (() => {
            const raw = src.raw || base.raw;
            if (!(looksNonGunEquip && gunLikeLeak && raw && typeof raw === "object")) return raw;
            return {
              ...raw,
              item_type: nextItemType || raw.item_type,
              display_name:
                String(base.display_name || base.title || "").trim() || raw.display_name,
              damage: null,
              dps: null,
            };
          })(),
          part_names:
            Array.isArray(base.part_names) && base.part_names.length
              ? base.part_names
              : Array.isArray(names) && names.length
                ? names
                : base.part_names,
        };
      };
      // Weapons need a Damage/DPS headline. Mag/Crit-only Nexus used to short-circuit
      // and leave Codes cards with a blank Damage block.
      if (nexus && (nexus.ok || (Array.isArray(nexus.stats) && nexus.stats.length))) {
        const applied = applyNexus(nexus);
        const source = String(applied.stats_source || nexus.source || "");
        // Baked NCS at the wrong preview level must not lock in tiny Damage.
        if (source.includes("level_mismatch")) {
          Object.assign(base, {
            ...applied,
            damage: null,
            dps: null,
            stats: (applied.stats || []).filter(
              (s) => !/^(damage|dps)$/i.test(String(s?.label || "").trim())
            ),
          });
        } else if (
          isNonGunEquipment ||
          /class\s*mod|classmod/i.test(`${applied.itemType || ""} ${applied.type_label || ""}`) ||
          hasDamageHeadline(applied.stats)
        ) {
          return applied;
        } else {
          // Keep Nexus secondary/equipment; fall through to estimate for Damage.
          Object.assign(base, applied);
        }
      }
    } catch {
      /* fall through to coarse estimate */
    }
  }
  if (
    Array.isArray(base.stats) &&
    (isNonGunEquipment
      ? base.stats.some((s) =>
          /damage|dps|fire|reload|mag|accuracy|crit|capacit|heal|radius|charge/i.test(
            String(s?.label || s)
          )
        )
      : hasDamageHeadline(base.stats))
  ) {
    return {
      ...base,
      stats_source: base.stats_source || "provided",
      stats_note: base.stats_note || "",
    };
  }
  if (!names.length) return base;
  await Promise.all([ensurePartsStatsData(), ensureWeaponStatsData()]);
  const itemType = String(base.itemType || base.type_label || base.type || "");
  const equipBlob = `${itemType} ${names.join(" ")}`.toLowerCase();
  // Never invent gun damage for shields / grenades / repkits — leave blank vs fake DPS.
  const explicitWeapon =
    /pistol|shotgun|smg|submachine|sniper|assault|rifle|heavy\s*(?:weapon|gun)/i.test(
      itemType
    );
  const explicitEquipment =
    /shield|repkit|repair|ordnance|grenade|gadget|enhancement|class\s*mod|classmod/i.test(
      itemType
    );
  const isEquipment =
    explicitEquipment ||
    (!explicitWeapon &&
      /shield|repkit|repair|ordnance|grenade|gadget|enhancement|class\s*mod|classmod/.test(
        equipBlob
      ));
  const isWeapon =
    !isEquipment &&
    (/weapon|pistol|shotgun|smg|rifle|sniper|heavy|assault/i.test(itemType) ||
      names.some((n) => /\.(ps|sg|sm|ar|sr|hw)\./i.test(String(n))));
  let stats = [];
  let stats_source = "";
  if (isWeapon) {
    stats = estimateWeaponPrimaryStats(
      names,
      itemType,
      base.manufacturer || "",
      resolveNexusCardLevel(base)
    );
    if (stats.length) stats_source = "sqbt_estimate";
  }
  if (!stats.length && isWeapon) {
    stats = scaleStatsFromPartNames(names);
    if (stats.length) stats_source = "sqbt_scale";
  }
  if (!stats.length) return base;
  // Merge estimate Damage into partial Nexus rows (keep Mag/Crit/etc.).
  const merged = Array.isArray(base.stats) && base.stats.length
    ? [
        ...stats.filter((s) => /^(damage|dps)$/i.test(String(s?.label || "").trim())),
        ...base.stats.filter((s) => !/^(damage|dps)$/i.test(String(s?.label || "").trim())),
      ]
    : stats;
  // Fallback only — nexus is preferred when available.
  // Keep Mag/Crit/etc. from Nexus; only mark Damage/DPS as estimate — don't brand the whole card.
  const hadNexusBody =
    String(base.stats_source || "").includes("nexus") ||
    Array.isArray(base.native_secondary) ||
    Number.isFinite(Number(base.crit)) ||
    Number.isFinite(Number(base.magazine));
  return {
    ...base,
    level: resolveNexusCardLevel(base),
    stats: merged,
    stats_source: base.stats_source ? `${base.stats_source}+${stats_source}` : stats_source,
    stats_note: hadNexusBody
      ? ""
      : base.stats_note || "Fallback estimate — not live/GZO Nexus values",
    damage_headline_estimate: true,
  };
}

const catalogCardEnrichCache = new Map();
/** Bump when enrich output shape changes so stale thin Legit rows re-decode. */
const CATALOG_CARD_ENRICH_CACHE_VER = 13;
let catalogCardPaintSeq = 0;
let catalogCardEnrichActive = 0;
/** @type {{ serial: string, start: () => void, cancel?: () => void }[]} */
const catalogCardEnrichQueue = [];
const catalogCardEnrichWaiters = new Map();
/** Only the hovered/focused serial stays ahead of the queue (Legit packs can be 2000+). */
let catalogCardEnrichFocusSerial = "";
const CATALOG_CARD_ENRICH_MAX = 2;
let catalogPreviewDebounceTimer = 0;
let catalogPreviewDebounceSerial = "";

function setCatalogCardEnrichFocus(serial) {
  catalogCardEnrichFocusSerial = String(serial || "").trim();
  if (!catalogCardEnrichFocusSerial || !catalogCardEnrichQueue.length) return;
  const focus = catalogCardEnrichFocusSerial;
  const keep = [];
  for (const job of catalogCardEnrichQueue) {
    if (job.serial === focus) keep.push(job);
    else if (typeof job.cancel === "function") job.cancel();
  }
  catalogCardEnrichQueue.length = 0;
  catalogCardEnrichQueue.push(...keep);
}

function catalogCardPropsHaveBody(props) {
  return (
    (Array.isArray(props?.parts) && props.parts.length > 0) ||
    (Array.isArray(props?.perk_rows) && props.perk_rows.length > 0) ||
    (Array.isArray(props?.red_text) && props.red_text.length > 0) ||
    (Array.isArray(props?.part_names) && props.part_names.length > 0)
  );
}

function _pumpCatalogCardEnrichQueue() {
  while (
    catalogCardEnrichActive < CATALOG_CARD_ENRICH_MAX &&
    catalogCardEnrichQueue.length
  ) {
    const focus = catalogCardEnrichFocusSerial;
    let idx = 0;
    if (focus) {
      const hit = catalogCardEnrichQueue.findIndex((j) => j.serial === focus);
      if (hit >= 0) idx = hit;
    }
    const job = catalogCardEnrichQueue.splice(idx, 1)[0];
    if (job) job.start();
  }
}

function catalogPartCodes(props) {
  const names = Array.isArray(props?.part_names) ? props.part_names : [];
  return names.filter((n) => {
    const s = String(n || "").trim();
    if (!s) return false;
    // A bare part_* token has no inventory root and is not enough for the native
    // resolver. Require a full root.leaf code before skipping serial decode.
    return /^[a-z0-9_]+\.[a-z0-9_+.-]+$/i.test(s);
  });
}

function catalogNeedsBridgeEnrich(props) {
  const base = props && typeof props === "object" ? props : {};
  if (base._forceBridgeEnrich) return true;
  const serial = String(base.serial || "").trim();
  if (!serial.startsWith("@U")) return false;
  const codes = catalogPartCodes(base);
  // Enough coded parts for Nexus — skip the live bridge.
  if (codes.length >= 4) return false;
  return true;
}

/** Full in-game name (prefixes included) from the row, when the decode only knows the bare name. */
function catalogPinnedCardName(props, decodedName) {
  const pinned = String(props?.card_name || "").trim();
  if (pinned) return pinned;
  const label = String(props?.user_label || "")
    .trim()
    .replace(/^\[(?:legit|modded)\]\s*/i, "");
  const decoded = String(decodedName || "").trim();
  if (!label || !decoded || /^(?:@U|#|★)/i.test(label) || /[—·]/.test(label)) return "";
  return label.length > decoded.length && label.toLowerCase().includes(decoded.toLowerCase()) ? label : "";
}

function withPinnedCardName(props, card) {
  if (!card || typeof card !== "object") return card;
  const name = String(card.full_name || "").trim() || catalogPinnedCardName(props, card.display_name);
  if (!name) return card;
  const listing = String(card.listing || props?.listing || "").trim();
  const listingPrefix = /^(legit|modded)$/i.test(listing) ? `[${listing.toUpperCase()}] ` : "";
  return { ...card, display_name: name, title: `${listingPrefix}${name}` };
}

async function enrichCatalogCardProps(props) {
  return withPinnedCardName(props, await enrichCatalogCardPropsDecoded(props));
}

async function enrichCatalogCardPropsDecoded(props) {
  const base = props && typeof props === "object" ? props : {};
  const serial = String(base.serial || "").trim();
  if (!serial.startsWith("@U")) return base;
  // Thin Legit rows often ship human perk labels without part codes. That used to
  // short-circuit enrich and leave Nexus with nothing → blank classmod icons +
  // ~level-1 damage on weapons. Always decode when coded parts are scarce.
  if (!catalogNeedsBridgeEnrich(base)) {
    const pretty = String(base.display_name || "").trim();
    if (pretty && pretty !== String(base.title || "").trim()) {
      return { ...base, title: pretty };
    }
    return base;
  }
  if (catalogCardEnrichCache.has(serial)) {
    const hit = catalogCardEnrichCache.get(serial);
    if (hit && hit._enrich_ver !== CATALOG_CARD_ENRICH_CACHE_VER) {
      catalogCardEnrichCache.delete(serial);
    }
  }
  if (catalogCardEnrichCache.has(serial)) {
    const hit = catalogCardEnrichCache.get(serial);
    // Empty prior decode: retry (perk filter / stats may have improved this build).
    const empty =
      hit &&
      hit._enriched &&
      !(hit.perk_rows || []).length &&
      !(hit.parts || []).length &&
      !(hit.part_names || []).length;
    if (!empty) {
      const merged = { ...base, ...hit };
      // Prefer richer part_names from either side.
      const codes = catalogPartCodes(merged);
      if (codes.length < catalogPartCodes(hit).length) {
        merged.part_names = hit.part_names;
      }
      return merged;
    }
    catalogCardEnrichCache.delete(serial);
  }
  if (catalogCardEnrichWaiters.has(serial)) {
    await catalogCardEnrichWaiters.get(serial);
    return catalogCardEnrichCache.has(serial)
      ? { ...base, ...catalogCardEnrichCache.get(serial) }
      : base;
  }
  if (typeof window.sqbt?.postAction !== "function") return base;

  let resolveWait;
  let cancelled = false;
  const waitPromise = new Promise((resolve) => {
    resolveWait = resolve;
  });
  catalogCardEnrichWaiters.set(serial, waitPromise);

  const runJob = () =>
    new Promise((resolve) => {
      if (cancelled) {
        resolve();
        return;
      }
      catalogCardEnrichActive += 1;
      (async () => {
        try {
          const { data } = await window.sqbt.postAction(
            "bay_label_serials",
            { serials: [serial] },
            6
          );
          const hit = Array.isArray(data?.rows) ? data.rows[0] : null;
          if (!hit || typeof hit !== "object") {
            return;
          }
          const extra = {
            rarity: hit.rarity || base.rarity,
            manufacturer: hit.manufacturer || base.manufacturer,
            itemType: hit.item_type || hit.type || base.itemType,
            type_label: hit.type_label || base.type_label || "",
            // Hover enrichment identifies the item/parts, but a locked preview
            // level must stay at the UI level or Damage is stripped/miscaled.
            level:
              base._previewLevelLocked && Number(base.level) > 0
                ? base.level
                : hit.level != null && hit.level !== ""
                  ? hit.level
                  : base.level,
            parts: Array.isArray(hit.parts) ? hit.parts : [],
            perk_rows: Array.isArray(hit.perk_rows) ? hit.perk_rows : [],
            perk_lines: Array.isArray(hit.perk_lines) ? hit.perk_lines : [],
            stats: Array.isArray(hit.stats) ? hit.stats : [],
            element: hit.element || hit.damage_type || base.element,
            red_text: Array.isArray(hit.red_text) ? hit.red_text : [],
            part_names: Array.isArray(hit.part_names) ? hit.part_names : [],
            set: hit.set || base.set || "",
            type_id: hit.type_id || base.type_id || "",
            _enriched: true,
            _enrich_ver: CATALOG_CARD_ENRICH_CACHE_VER,
          };
          const pretty = String(hit.display_name || "").trim();
          if (pretty) {
            // Always use the decoded game name on the card. User nicknames stay on the list chip.
            const listing = String(hit.listing || base.listing || "").trim();
            const listingPrefix =
              listing && /^(legit|modded)$/i.test(listing)
                ? `[${listing.toUpperCase()}] `
                : "";
            extra.display_name = pretty;
            extra.title = `${listingPrefix}${pretty}`;
          }
          catalogCardEnrichCache.set(serial, extra);
        } catch {
          // Bridge timeouts are transient (especially while rapidly hovering).
          // Do not turn one timeout into a permanent blank card.
        } finally {
          catalogCardEnrichActive = Math.max(0, catalogCardEnrichActive - 1);
          resolveWait();
          catalogCardEnrichWaiters.delete(serial);
          resolve();
          _pumpCatalogCardEnrichQueue();
        }
      })();
    });

  if (catalogCardEnrichActive < CATALOG_CARD_ENRICH_MAX) {
    await runJob();
  } else {
    await new Promise((resolve) => {
      const job = {
        serial,
        start: () => {
          runJob().then(resolve);
        },
        cancel: () => {
          cancelled = true;
          resolveWait();
          catalogCardEnrichWaiters.delete(serial);
          resolve();
        },
      };
      catalogCardEnrichQueue.push(job);
      // Prefer the focused hover serial — drop other waiting mass-list jobs.
      if (catalogCardEnrichFocusSerial && serial === catalogCardEnrichFocusSerial) {
        setCatalogCardEnrichFocus(serial);
      }
    });
  }
  return catalogCardEnrichCache.has(serial)
    ? { ...base, ...catalogCardEnrichCache.get(serial) }
    : base;
}

function _catalogSerialStrip(serial) {
  const s = String(serial || "").trim();
  if (!s.startsWith("@U")) return null;
  const strip = document.createElement("div");
  strip.className = "sqbt-catalog-serial-strip";
  const code = document.createElement("code");
  code.className = "sqbt-catalog-serial-code";
  code.textContent = s.length > 64 ? `${s.slice(0, 60)}…` : s;
  code.title = s;
  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "ghost sqbt-catalog-serial-copy";
  copyBtn.textContent = "Copy @U";
  copyBtn.title = "Copy full serial";
  copyBtn.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(s);
      copyBtn.textContent = "Copied";
      window.setTimeout(() => {
        copyBtn.textContent = "Copy @U";
      }, 1200);
    } catch {
      copyBtn.textContent = "Failed";
      window.setTimeout(() => {
        copyBtn.textContent = "Copy @U";
      }, 1200);
    }
  });
  strip.appendChild(code);
  strip.appendChild(copyBtn);
  return strip;
}

function paintCatalogCardHost(host, props) {
  const serial = String(props?.serial || "").trim();
  const mountCard = (cardEl) => {
    if (!host || !cardEl) return cardEl;
    const strip = _catalogSerialStrip(serial);
    if (strip) host.replaceChildren(strip, cardEl);
    else host.replaceChildren(cardEl);
    return cardEl;
  };
  const existing = host?.querySelector?.(".sqbt-native-card");
  if (
    existing &&
    window.SQBTNativeItemCard &&
    typeof window.SQBTNativeItemCard.propsToEntry === "function" &&
    typeof window.SQBTNativeItemCard.fillNativeItemCard === "function"
  ) {
    const entry = window.SQBTNativeItemCard.propsToEntry(props);
    const filled = window.SQBTNativeItemCard.fillNativeItemCard(existing, entry, {
      width: 420,
      lazy: false,
    });
    if (filled) {
      // Keep a fresh serial strip above the reused iframe card.
      const strip = _catalogSerialStrip(serial);
      const prev = host.querySelector(".sqbt-catalog-serial-strip");
      if (strip && prev) prev.replaceWith(strip);
      else if (strip && !prev) host.insertBefore(strip, host.firstChild);
      else if (!strip && prev) prev.remove();
      return filled;
    }
  }
  const card =
    buildInventoryStyleCardEl({
      ...props,
      preferNative: true,
      nativeOnly: true,
      width: 420,
      lazy: false,
    }) || _catalogPreviewStub(props);
  return mountCard(card);
}

async function paintCatalogNativePreview(host, props) {
  if (!host) return;
  if (!catalogShowItemCards()) {
    host.hidden = true;
    host.replaceChildren();
    return;
  }
  const serial = String(props?.serial || "").trim();
  setCatalogCardEnrichFocus(serial);
  const paintId = String(++catalogCardPaintSeq);
  host.dataset.paintReq = paintId;
  host.hidden = false;
  host.dataset.previewSerial = serial;
  const bakedSerialLevel = Number(props?.serial_level ?? props?.raw?.level);
  if (Number.isFinite(bakedSerialLevel) && bakedSerialLevel > 0) {
    host.dataset.previewSerialLevel = String(bakedSerialLevel);
  } else if (!host.dataset.previewSerialLevel && Number(props?.level) > 0) {
    // First paint may only have row.level before override remaps it.
    host.dataset.previewSerialLevel = String(Number(props.level));
  }
  const split = host.closest(".catalog-preview-split");
  if (split) split.classList.remove("cards-off");
  // Keep the prior card (or a stub) while enrich runs — do not start a thin native
  // fill that can race the enriched model into the reused iframe.
  if (!host.querySelector(".sqbt-native-card")) {
    host.replaceChildren(_catalogPreviewStub(props));
  }
  const sectionId =
    String(props?._catalogSectionId || host?.dataset?.catalogPreview || "").trim();
  const serialLevelHint = Number(
    props?.serial_level || host.dataset.previewSerialLevel || props?.raw?.level
  );
  const leveledBase = {
    ...props,
    _catalogSectionId: sectionId || props?._catalogSectionId || "",
    serial_level:
      Number.isFinite(serialLevelHint) && serialLevelHint > 0
        ? serialLevelHint
        : props?.serial_level,
    level: resolveNexusCardLevel(
      {
        ...props,
        _catalogSectionId: sectionId || props?._catalogSectionId,
        serial_level:
          Number.isFinite(serialLevelHint) && serialLevelHint > 0
            ? serialLevelHint
            : props?.serial_level,
      },
      sectionId
    ),
    _previewLevelLocked: true,
  };
  // Exact NCS serial matches already contain the full card and do not need the
  // slower in-game serial-label bridge. This also keeps rapid hover previews
  // responsive when the bridge is busy.
  const direct = await attachPartScaleStats(leveledBase);
  let enriched = direct;
  const typeBlob = `${direct.itemType || ""} ${direct.type_label || ""} ${leveledBase.itemType || ""} ${leveledBase.type_label || ""} ${(Array.isArray(leveledBase.part_names) ? leveledBase.part_names : []).join(" ")} ${(Array.isArray(direct.part_names) ? direct.part_names : []).join(" ")}`;
  const isClassmodPreview =
    /class\s*mod|classmod/i.test(typeBlob) ||
    (/passive_(?:blue|green|red)/i.test(typeBlob) &&
      !/\.(?:part_barrel|part_grip|part_mag)_/i.test(typeBlob));
  const classmodIconsMissing =
    isClassmodPreview &&
    !(
      Array.isArray(direct.native_equipment?.groups?.primary) &&
      direct.native_equipment.groups.primary.some((row) =>
        /^(?:coui:|data:|common:)/i.test(String(row?.image || "").trim())
      )
    );
  // Pearl classmods often resolve on NCS Lookup as TED_SG / Shotgun with Damage.
  // That used to skip enrich forever → gun card + @U title and no skill glyphs.
  const exactLooksGun =
    /pistol|shotgun|assault|smg|submachine|sniper|heavy/i.test(
      `${direct.itemType || ""} ${direct.type_label || ""} ${direct.raw?.item_type || ""}`
    );
  const nameLooksSerial = /^@U/i.test(
    String(direct.display_name || direct.title || leveledBase.display_name || leveledBase.title || "")
  );
  const maybeMisTypedClassmod =
    exactLooksGun &&
    String(leveledBase.serial || direct.serial || "").startsWith("@U") &&
    (nameLooksSerial ||
      classmodIconsMissing ||
      /passive_(?:blue|green|red)|classmod_/i.test(typeBlob) ||
      !/\.(?:part_barrel|part_grip|part_mag)_/i.test(typeBlob));
  // Exact NCS must not skip enrich for classmods — those cards often lack primary
  // skill icons, and bridge decode supplies perk_rows / part codes for backfill.
  if (
    (direct.stats_source !== "ncs_lookup_exact" ||
      classmodIconsMissing ||
      maybeMisTypedClassmod ||
      String(direct.stats_source || "").includes("level_mismatch") ||
      !(Number(direct.damage) > 0)) &&
    (catalogNeedsBridgeEnrich(leveledBase) ||
      classmodIconsMissing ||
      maybeMisTypedClassmod ||
      String(direct.stats_source || "").includes("level_mismatch") ||
      (!(Number(direct.damage) > 0) && catalogPartCodes(leveledBase).length < 8))
  ) {
    const enrichedRaw = await enrichCatalogCardProps({
      ...leveledBase,
      ...(classmodIconsMissing || maybeMisTypedClassmod || !(Number(direct.damage) > 0)
        ? { _forceBridgeEnrich: true }
        : {}),
    });
    enriched = await attachPartScaleStats({
      ...enrichedRaw,
      _catalogSectionId: sectionId || enrichedRaw._catalogSectionId || "",
      _previewLevelLocked: true,
      level: resolveNexusCardLevel(
        {
          ...enrichedRaw,
          _catalogSectionId: sectionId || enrichedRaw._catalogSectionId,
          _previewLevelLocked: true,
          level: leveledBase.level,
        },
        sectionId
      ),
    });
  }
  if (host.dataset.paintReq !== paintId) return;
  const rowName = String(props?.display_name || "").trim();
  const finalName = String(enriched.display_name || "").trim();
  if (rowName && !/^@U/i.test(rowName) && (!finalName || /^@U/i.test(finalName) || /^item$/i.test(finalName))) {
    enriched = { ...enriched, display_name: rowName, title: rowName };
  }
  enriched = withPinnedCardName(props, enriched);
  host.dataset.previewKey = [
    enriched.serial,
    enriched.title,
    enriched.rarity,
    enriched.itemType,
    enriched.level,
    (enriched.parts || []).length,
    (enriched.perk_rows || []).length,
    (enriched.stats || []).length,
    enriched.stats_source || "",
  ].join("|");
  paintCatalogCardHost(host, enriched);
}

function scheduleCatalogNativePreview(host, props) {
  if (!host || !catalogShowItemCards()) return;
  const serial = String(props?.serial || "").trim();
  setCatalogCardEnrichFocus(serial);
  catalogPreviewDebounceSerial = serial;
  if (catalogPreviewDebounceTimer) {
    clearTimeout(catalogPreviewDebounceTimer);
    catalogPreviewDebounceTimer = 0;
  }
  // Instant name stub only — defer native fill until enrich so thin models cannot
  // race into the reused iframe and blank Damage / classmod icons.
  if (!host.querySelector(".sqbt-native-card")) {
    host.replaceChildren(_catalogPreviewStub(props));
  }
  catalogPreviewDebounceTimer = window.setTimeout(() => {
    catalogPreviewDebounceTimer = 0;
    if (catalogPreviewDebounceSerial !== serial) return;
    paintCatalogNativePreview(host, props);
  }, 120);
}

function _catalogPreviewStub(props) {
  const stub = document.createElement("div");
  stub.className = "sqbt-native-card-fallback";
  const name = document.createElement("div");
  name.className = "sqbt-native-card-fallback-name";
  name.textContent = String(props?.title || props?.name || "Item");
  stub.appendChild(name);
  const note = document.createElement("div");
  note.className = "muted small";
  note.textContent = "Hover to load card details…";
  stub.appendChild(note);
  return stub;
}

function appendCatalogItemCardRow({
  listEl,
  wrap,
  label,
  row,
  title,
  extraBits,
  config,
  previewHost = null,
  sectionId = "",
  chipLabel = "",
}) {
  const useCards =
    catalogShowItemCards() &&
    (
      config.catalog === "gzo" ||
      config.catalog === "lootlemon" ||
      config.catalog === "serial_store" ||
      config.catalog === "curated_builds"
    );
  if (!useCards) {
    const text = document.createElement("span");
    const extra = (extraBits || []).filter((bit, idx, arr) => bit && arr.indexOf(bit) === idx).join(" · ");
    text.textContent = extra ? `${title} · ${extra}` : title;
    label.appendChild(text);
    wrap.appendChild(label);
    listEl.appendChild(wrap);
    return;
  }

  const sid =
    String(sectionId || previewHost?.dataset?.catalogPreview || "").trim();
  const props = catalogCardPropsFromRow(row, title, sid);
  // Shared Cohtml preview for GZO / Lootlemon / Item lists — never spawn per-row iframes
  // or mass-decode 2000 Legit rows on list paint.
  const wantNativePreview =
    Boolean(previewHost) &&
    (
      config.catalog === "gzo" ||
      config.catalog === "lootlemon" ||
      config.catalog === "serial_store" ||
      config.catalog === "curated_builds"
    );

  if (wantNativePreview) {
    label.classList.add("catalog-card-row", "catalog-native-pick");
    const chip = document.createElement("div");
    chip.className = `sqbt-catalog-pick ${rarityCardClass(props.rarity)}`;
    chip.style.setProperty("--sqbt-rarity", rarityAccentColor(props.rarity));
    const nameEl = document.createElement("div");
    nameEl.className = "sqbt-catalog-pick-name";
    // List chip = optional user nickname; never show raw @U as the item name.
    const rawChip =
      String(chipLabel || row.user_label || row.name || title || "Item").trim() || "Item";
    const chipText = /^@U/i.test(rawChip)
      ? String(props.display_name || props.title || props.itemType || props.type_label || "Item").trim() ||
        "Item"
      : rawChip;
    nameEl.textContent = chipText;
    const badge = serialSafetyBadgeEl(row);
    if (badge) nameEl.appendChild(badge);
    chip.appendChild(nameEl);
    if (row.broken) chip.classList.add("is-broken-code");
    const metaBits = row.broken
      ? ["Can't be sent — remove it from the list"]
      : [props.manufacturer, props.itemType, props.rarity]
          .map((x) => String(x || "").trim())
          .filter(Boolean);
    if (metaBits.length) {
      const meta = document.createElement("div");
      meta.className = "sqbt-catalog-pick-meta";
      meta.textContent = metaBits.join(" · ");
      chip.appendChild(meta);
    }
    const rowSerial = String(props.serial || row.serial || "").trim();
    if (rowSerial.startsWith("@U")) {
      const serialEl = document.createElement("code");
      serialEl.className = "sqbt-catalog-pick-serial";
      serialEl.textContent = rowSerial.length > 42 ? `${rowSerial.slice(0, 38)}…` : rowSerial;
      serialEl.title = `${rowSerial} (click to copy)`;
      serialEl.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        try {
          await navigator.clipboard.writeText(rowSerial);
          serialEl.classList.add("is-copied");
          window.setTimeout(() => serialEl.classList.remove("is-copied"), 900);
        } catch {
          /* ignore */
        }
      });
      chip.appendChild(serialEl);
    }
    label.appendChild(chip);
    // Rebuild on hover: Item list names land after first paint (row patched in place).
    const showPreview = () =>
      scheduleCatalogNativePreview(
        previewHost,
        catalogCardPropsFromRow(row, String(row.display_name || "").trim() || title, sid)
      );
    label.addEventListener("mouseenter", showPreview);
    label.addEventListener("focusin", showPreview);
    wrap.appendChild(label);
    listEl.appendChild(wrap);
    if (!previewHost.dataset.seeded) {
      previewHost.dataset.seeded = "1";
      scheduleCatalogNativePreview(previewHost, props);
    }
    return;
  }

  // Fallback CSS inventory tiles (no bridge enrich on paint).
  label.classList.add("catalog-card-row");
  const cardHost = document.createElement("div");
  cardHost.className = "sqbt-inv-card-host";
  const paintTile = (nextProps) => {
    cardHost.replaceChildren(
      buildInventoryStyleCardEl({
        ...nextProps,
        listing: row.listing || row.group || row.creator || "",
        preferNative: false,
      })
    );
  };
  paintTile(props);
  label.appendChild(cardHost);
  wrap.appendChild(label);
  listEl.appendChild(wrap);
  // Hover-only enrich for fallback tiles — never fan out on list render.
  if (props.serial && String(props.serial).startsWith("@U")) {
    label.addEventListener(
      "mouseenter",
      async () => {
        if (cardHost.dataset.enriched === "1") return;
        setCatalogCardEnrichFocus(String(props.serial));
        const direct = await attachPartScaleStats(props);
        let enriched = direct;
        const typeBlob = `${direct.itemType || ""} ${direct.type_label || ""} ${props.itemType || ""} ${props.type_label || ""} ${(Array.isArray(props.part_names) ? props.part_names : []).join(" ")} ${(Array.isArray(direct.part_names) ? direct.part_names : []).join(" ")}`;
        const isClassmodPreview =
          /class\s*mod|classmod/i.test(typeBlob) ||
          (/passive_(?:blue|green|red)/i.test(typeBlob) &&
            !/\.(?:part_barrel|part_grip|part_mag)_/i.test(typeBlob));
        const classmodIconsMissing =
          isClassmodPreview &&
          !(
            Array.isArray(direct.native_equipment?.groups?.primary) &&
            direct.native_equipment.groups.primary.some((row) =>
              /^(?:coui:|data:|common:)/i.test(String(row?.image || "").trim())
            )
          );
        const exactLooksGun = /pistol|shotgun|assault|smg|submachine|sniper|heavy/i.test(
          `${direct.itemType || ""} ${direct.type_label || ""}`
        );
        const nameLooksSerial = /^@U/i.test(
          String(direct.display_name || direct.title || props.display_name || props.title || "")
        );
        const maybeMisTypedClassmod =
          exactLooksGun &&
          String(props.serial || direct.serial || "").startsWith("@U") &&
          (nameLooksSerial ||
            classmodIconsMissing ||
            /passive_(?:blue|green|red)|classmod_/i.test(typeBlob) ||
            !/\.(?:part_barrel|part_grip|part_mag)_/i.test(typeBlob));
        if (
          (direct.stats_source !== "ncs_lookup_exact" ||
            classmodIconsMissing ||
            maybeMisTypedClassmod ||
            String(direct.stats_source || "").includes("level_mismatch") ||
            !(Number(direct.damage) > 0)) &&
          (catalogNeedsBridgeEnrich(props) ||
            classmodIconsMissing ||
            maybeMisTypedClassmod ||
            !(Number(direct.damage) > 0))
        ) {
          enriched = await attachPartScaleStats(
            await enrichCatalogCardProps({
              ...props,
              _previewLevelLocked: true,
              level: resolveNexusCardLevel({ ...props, _previewLevelLocked: true, level: 70 }),
              ...(classmodIconsMissing || maybeMisTypedClassmod || !(Number(direct.damage) > 0)
                ? { _forceBridgeEnrich: true }
                : {}),
            })
          );
        }
        if (!cardHost.isConnected) return;
        if (enriched._enriched || enriched.stats_source) {
            cardHost.dataset.enriched = "1";
        }
        paintTile(withPinnedCardName(props, enriched));
      },
      { once: false }
    );
  }
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
  for (const id of selected) {
    const row = rowById.get(id);
    let serial = row ? rowSerialValue(row, config) : "";
    if (!serial) serial = String(cache.get(String(id)) || "").trim();
    if (!isDeliverableSerial(serial)) continue;
    serials.push(serial);
    const title = String(
      (row && (row.title || row.name || row[config.labelKey || "title"])) || serial.slice(0, 48)
    ).trim();
    libraryRows.push({ serial, title, name: title });
  }
  // Keep row↔serial one-to-one for pack save / mail — do not filter against a re-sanitized set.
  const whole = sanitizeDeliverableSerials(serials);
  return {
    serials: whole,
    rows: libraryRows.length === whole.length ? libraryRows : whole.map((serial) => ({
      serial,
      title: serial.slice(0, 48),
      name: serial.slice(0, 48),
    })),
    selectedCount: selected.size,
  };
}

function bustSerialStoreCatalog() {
  for (const key of [...catalogCache.keys()]) {
    const name = String(key);
    if (
      name.startsWith("serial_store:") ||
      name.startsWith("serial_groups:") ||
      name === "serial_store" ||
      name === "serial_groups"
    ) {
      catalogCache.delete(key);
    }
  }
  // Auto Lobby drip pack dropdowns also cache serial_groups — rebuild them.
  for (const node of document.querySelectorAll("[data-field-key$=':item_drip_pack'], [data-field-key$=':pack'], [data-field-key$=':mail_pack']")) {
    const select = node.querySelector?.("select") || (node.tagName === "SELECT" ? node : null);
    if (!select) continue;
    const fieldJson = node.dataset?.catalogField || select.dataset?.catalogField;
    if (!fieldJson) continue;
    try {
      const field = JSON.parse(fieldJson);
      if (field?.catalog !== "serial_groups" && field?.catalog !== "serial_store") continue;
      const sectionId = node.dataset?.sectionId || select.dataset?.sectionId || "";
      const actionDef = { action: node.dataset?.actionName || select.dataset?.actionName || "catalog" };
      populateCatalogSelect(select, field, sectionId, actionDef, node);
    } catch {
      /* ignore */
    }
  }
}

function refreshAllSerialStoreSections() {
  bustSerialStoreCatalog();
  for (const box of document.querySelectorAll("[data-multiselect-section]")) {
    const sectionId = box.dataset.multiselectSection;
    if (!sectionId) continue;
    const config = getMultiselectConfig(sectionId);
    if (config?.catalog !== "serial_store" && config?.catalog !== "serial_groups") continue;
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

function configParamsPartyBay(sectionId) {
  const config = getMultiselectConfig(sectionId);
  return Boolean(config?.params?.party_bay);
}

function configParamsPackBay(sectionId) {
  const config = getMultiselectConfig(sectionId);
  return Boolean(config?.params?.pack_bay || config?.source === "save_yaml");
}

function isPartyBayContext(sectionId) {
  return activeTabId === "party_bay" || configParamsPartyBay(sectionId);
}

function hostPlayerIndex(players) {
  const list = Array.isArray(players) ? players : [];
  const host = list.find((row) => row.is_host || row.host);
  if (host && host.index != null && host.index !== "") return Number(host.index);
  return 0;
}

function playerOptionLabel(row) {
  const rawName = String(row?.name || row?.shift_name || "").trim();
  const base = rawName || (row?.is_host ? "Host" : `Player ${row?.index}`);
  const lvl = row?.level != null && row?.level !== "" ? Number(row.level) : NaN;
  const levelBit = Number.isFinite(lvl) && lvl > 0 ? ` · L${lvl}` : "";
  let label = `${base}${levelBit} (#${row?.index})`;
  if (label.length > 56) {
    label = `${label.slice(0, 53)}…`;
  }
  return label;
}

function paintKickExemptField(wrap, fieldKey) {
  if (!wrap) return;
  const chips = wrap.querySelector('[data-role="kick-exempt-chips"]');
  if (!chips) return;
  const list = Array.isArray(fieldValues[fieldKey]) ? fieldValues[fieldKey] : [];
  chips.innerHTML = "";
  if (!list.length) {
    const empty = document.createElement("span");
    empty.className = "muted small";
    empty.textContent = "None saved — add lobby guests above.";
    chips.appendChild(empty);
    return;
  }
  for (const name of list) {
    const chip = document.createElement("span");
    chip.className = "kick-exempt-chip";
    const label = document.createElement("span");
    label.textContent = String(name);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "kick-exempt-remove";
    remove.textContent = "×";
    remove.title = `Remove ${name}`;
    remove.addEventListener("click", () => {
      const next = (Array.isArray(fieldValues[fieldKey]) ? fieldValues[fieldKey] : []).filter(
        (n) => String(n) !== String(name)
      );
      fieldValues[fieldKey] = next;
      markAutoLobbyFieldTouched(fieldKey);
      markUserEditing();
      paintKickExemptField(wrap, fieldKey);
      const sectionId = String(fieldKey).split(":").slice(0, 2).join(":");
      persistKickExemptNames(sectionId, fieldKey);
    });
    chip.append(label, remove);
    chips.appendChild(chip);
  }
}

function refreshKickExemptAddSelect(select) {
  if (!select) return;
  const previous = select.value;
  const players = (latestStatus?.raw?.players || []).filter((row) => !row.is_host && !isPlaceholderPlayerRow(row));
  select.innerHTML = "";
  if (!players.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = actionsEnabled() ? "No guests in lobby" : "Connect in-game…";
    select.appendChild(opt);
    select.disabled = true;
    return;
  }
  select.disabled = !actionsEnabled();
  for (const row of players) {
    const opt = document.createElement("option");
    opt.value = String(row.index);
    opt.textContent = playerOptionLabel(row);
    select.appendChild(opt);
  }
  if (previous && [...select.options].some((o) => o.value === previous)) {
    select.value = previous;
  }
}

function refreshAllKickExemptFields() {
  for (const wrap of document.querySelectorAll('[data-role="kick-exempt"]')) {
    const key = wrap.dataset.fieldKey || "";
    const select = wrap.querySelector('select[data-role="kick-exempt-add"]');
    if (select) refreshKickExemptAddSelect(select);
    if (key) paintKickExemptField(wrap, key);
  }
}

async function persistKickExemptNames(sectionId, fieldKey) {
  if (!actionsEnabled()) return;
  const names = Array.isArray(fieldValues[fieldKey])
    ? fieldValues[fieldKey].map((n) => String(n || "").trim()).filter(Boolean)
    : [];
  try {
    const { data } = await window.sqbt.postAction("auto_lobby_set", {
      kick_exempt_names: names,
    });
    const cfg = data?.config || data?.auto_lobby?.config;
    if (cfg && Array.isArray(cfg.kick_exempt_names)) {
      fieldValues[fieldKey] = cfg.kick_exempt_names;
    }
    const wrap = document.querySelector(`[data-field-key="${CSS.escape(fieldKey)}"]`);
    if (wrap) paintKickExemptField(wrap, fieldKey);
    if (actionMessage) {
      actionMessage.textContent = `Never-kick list saved (${names.length}).`;
    }
  } catch (err) {
    if (actionMessage) {
      actionMessage.textContent = `Could not save never-kick list: ${err?.message || err}`;
    }
  }
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
  // Stamp the EXE boost-target index for player-scoped boosts when the action
  // did not already choose a specific index (e.g. typed kick field).
  const BOOST_TARGET_ACTIONS = new Set([
    "map_fog_unlock",
    "give_everything",
    "character_flag",
    "god_mode",
    "infinite_ammo",
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
    "spawn_item_pool",
    "spawn_item_pool_all",
    "spawn_mix",
    "devperk_activate",
    "weapons_restricted",
    "ammo_regen",
    "vehicle_actions_locked",
    "mobility_force_fly",
    "mobility_infinite_jump",
    "backpack_scan_status",
    "backpack_relevel_selected",
    "backpack_export_txt",
    "backpack_refresh_view",
    "faafo_drop_backpack",
    "faafo_launch",
    "faafo_invert_look",
    "faafo_lock_look",
    "faafo_lock_move",
    "faafo_lock_both",
    "faafo_empty_backpack",
    "faafo_ffyl",
    "faafo_kill",
  ]);
  // These actions need a single concrete player — never stamp "All players" (-1).
  // uvhm_start accepts All and routes to all-lobby on the bridge.
  const BOOST_TARGET_NO_ALL = new Set([
    "party_kick",
    "teleport_party",
    "backpack_scan_status",
    "backpack_relevel_selected",
    "backpack_export_txt",
    "backpack_refresh_view",
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
  if (WORLD_SPAWN_ACTIONS.has(action)) {
    const players = latestStatus?.raw?.players || [];
    const hostIdx = hostPlayerIndex(players);
    // Always prefer sticky Boost target over stale per-field / "From me" defaults —
    // selecting a guest then Drop Shinies was flicking spawn back to host feet.
    const boostIdx = Number(preferredDeliveryPlayerIndex(players));
    if (Number.isFinite(boostIdx) && boostIdx >= 0) {
      next.player_index = boostIdx;
      if (boostIdx !== Number(hostIdx)) {
        next.spawn_anchor = "party";
      } else if (!next.spawn_anchor && spawnAnchorSelect?.value) {
        next.spawn_anchor = spawnAnchorSelect.value;
      }
    } else if (!next.spawn_anchor && spawnAnchorSelect?.value) {
      next.spawn_anchor = spawnAnchorSelect.value;
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
  const countRaw = fieldValues[`${sectionId}:count`];
  if (countRaw !== undefined && countRaw !== "") {
    const c = Number(countRaw);
    if (Number.isFinite(c) && c >= 1) {
      payload.count = Math.min(99, Math.max(1, Math.round(c)));
    }
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
  if (actionDef.action === "auto_lobby_start" || actionDef.action === "auto_lobby_set") {
    // Choosing a DROP list always means ground pile comes from that Item list.
    if (String(payload.item_drip_pack || "").trim()) {
      payload.item_drip_mode = "pack";
    }
  }
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
    for (const field of actionDef.fields || []) {
      const key = actionFieldKey(sectionId, actionDef, field);
      let value = fieldValues[key];
      if (value === undefined || value === "") value = field.default ?? "";
      if (field.type === "number") {
        if (value === "" || value == null) continue;
        value = Number(value);
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
        payload.open_rewards = String(value).toLowerCase() === "yes" || value === true;
        continue;
      }
      if (field.key === "level_override") {
        payload.level_override = String(value).toLowerCase() === "yes" || value === true;
        continue;
      }
      payload[field.key] = value;
    }
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

  if (actionDef.action === "backpack_relevel_selected") {
    // Dig Boost-target backpack; mail recipient comes from this action's Send to field.
    const players = latestStatus?.raw?.players || [];
    const boostIdx = preferredDeliveryPlayerIndex(players);
    if (boostIdx != null && boostIdx !== "" && Number(boostIdx) >= 0) {
      payload.source_player_index = Number(boostIdx);
    }
    payload._selected_count = Array.isArray(payload.slots) ? payload.slots.length : 0;
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
    for (const field of actionDef.fields || []) {
      const key = actionFieldKey(sectionId, actionDef, field);
      let value = fieldValues[key];
      if (value === undefined || value === "") value = field.default ?? "";
      if (field.type === "number") {
        if (value === "" || value == null) continue;
        value = Number(value);
      }
      payload[field.key] = value;
    }
    return applyDeliveryRecipient(payload, sectionId);
  }

  if (actionDef.addSelectedToLibrary) {
    const config = getMultiselectConfig(sectionId);
    const picked = collectSelectedSerials(sectionId, config);
    payload.rows = picked.rows;
    payload.serials = picked.serials;
    payload.titles = picked.rows.map((row) => row.title || row.name || "");
    // Pack name is prompted in runAction — do not hardcode Live/Save Pack.
    payload._selected_count = picked.selectedCount;
    payload._suggest_group = (() => {
      const cat = String(config?.catalog || "").toLowerCase();
      if (config?.params?.party_bay) return "Live Pack";
      if (config?.params?.pack_bay || config?.source === "save_yaml") return "Save Pack";
      if (cat === "lootlemon") return "Lootlemon";
      if (cat === "gzo") return "GZO";
      return "Imported";
    })();
    // Live / Save Pack: keep duplicate @U (same shiny twice in one backpack).
    if (config?.params?.party_bay || config?.params?.pack_bay || config?.source === "save_yaml") {
      payload.allow_duplicate_serials = true;
    }
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
      if (
        actionDef.action === "deliver_serials" ||
        actionDef.action === "backpack_relevel_selected"
      ) {
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
    } else if (!["nonhost", "non_host", "each_nonhost", "all_non_host"].includes(String(payload.mode || "").toLowerCase())) {
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

function beginGiveEverythingProgress() {
  lastGiveEverythingStatus = {
    active: true, running: true, phase: "starting", workflow_phase: "preparing",
    progress_percent: 0, phase_number: 0, phase_total: 4,
    message: "Preparing Give everything and checking Boost target…",
    _optimisticUntil: Date.now() + 45000,
  };
  lastProgressHtml = "";
  renderProgressPanel(null, null, null);
  startProgressPoll();
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
  if (action === "backpack_relevel_selected" && !prompt) {
    const n = Array.isArray(payload?.slots) ? payload.slots.length : Number(payload?._selected_count || 0);
    const lvl = Number(payload?.level || 70);
    prompt = `Mail ${n || "selected"} releveled @U serial(s) at level ${lvl} (Reward Center — does not rewrite live backpack)?`;
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
      kicker: "Builds",
      title: "New build",
      detail: "Name the build, paste @U codes, then save it. Import only adds — it never wipes.",
      label: "Build name",
      defaultValue: "New build",
      okLabel: "Create",
    });
    if (next == null) return;
    const cleaned = String(next).trim();
    if (!cleaned) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = "List name is required.";
      return;
    }
    payload.group = cleaned;
    payload.name = cleaned;
  }
  if (action === "serial_store_add_selected") {
    const count = Array.isArray(payload.serials) ? payload.serials.length : Number(payload._selected_count || 0);
    if (!count) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = "Tick at least one @U row first.";
      return;
    }
    const suggested = String(payload.group || payload._suggest_group || "Imported").trim() || "Imported";
    const next = await promptPackPickDialog({
      kicker: "Builds",
      title: count === 1 ? "Add to which build?" : `Add ${count} items to a build`,
      detail: "Choose an existing build or create a new named build.",
      packs: allKnownSerialStorePackNames(),
      suggested,
      okLabel: "Add to build",
    });
    if (next == null) {
      actionMessage.className = "action-message muted";
      actionMessage.textContent = "Add to Builds cancelled.";
      return;
    }
    const cleaned = String(next).trim();
    if (!cleaned) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = "Enter a list name.";
      return;
    }
    payload.group = cleaned;
    delete payload._suggest_group;
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
      actionMessage.textContent = "Pick a list name first (not All).";
      return;
    }
    if (!window.confirm(`Delete entire list "${pack}" and all of its serials?`)) {
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
    finalPayload.serials = sanitizeDeliverableSerials(finalPayload.serials);
    if (!finalPayload.serials.length) {
      actionMessage.className = "action-message error";
      actionMessage.textContent =
        "No whole @U serials left after integrity check (cut-off / split fragments were dropped).";
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
    // Match in-game chunking (fat @U split further by char budget).
    const perPkg = 16;
    const packages = Math.max(1, Math.ceil(nSerials / perPkg));
    const selectedHintCount = selectedHint || nSerials;
    if (nSerials >= 25) {
      let confirmText = `Deliver ${nSerials} serial(s) in ~${packages} mail package(s)?`;
      if (nSerials >= 400) {
        confirmText =
          `${confirmText}\n\nLarge pack: paced mail (~1s+ between packages). Stay in-world until delivery finishes.`;
      }
      if (selectedHintCount > nSerials) {
        confirmText = `Deliver ${nSerials} serial(s) (${selectedHintCount} row(s) selected) in ~${packages} mail package(s)?`;
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
    const digIdx = Number(finalPayload.source_player_index);
    if (!Number.isFinite(digIdx) || digIdx < 0) {
      actionMessage.className = "action-message error";
      actionMessage.textContent =
        "Pick one player in Boost target (not All players) before mailing releveled Live Pack gear.";
      actionBusy = false;
      refreshActionButtons();
      return;
    }
    if (!Array.isArray(finalPayload.slots) || !finalPayload.slots.length) {
      actionMessage.className = "action-message error";
      actionMessage.textContent =
        "Tick at least one backpack item in the list above, pick a new level, then Send releveled.";
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
    if (lastChallengeStatus?.running || lastChallengeStatus?.queued) {
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
      const perPkg = 8;
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
    if (["give_everything", "map_fog_unlock"].includes(resolvedAction)) beginGiveEverythingProgress();
    let { httpStatus, data } = await window.sqbt.postAction(resolvedAction, finalPayload, timeout);
    if (["give_everything", "map_fog_unlock"].includes(resolvedAction)) {
      lastGiveEverythingStatus = data?.ok === false ? null
        : data?.give_everything || { ...lastGiveEverythingStatus, _optimisticUntil: Date.now() + 45000 };
      lastProgressHtml = "";
      renderProgressPanel(null, null, null);
      if (lastGiveEverythingStatus) startProgressPoll();
    }
    if ((resolvedAction === "camera_third_person" || resolvedAction === "camera_view_reset") && data?.camera) {
      stickyToggleGraceUntil.third_person = Date.now() + 2500;
      syncMobilityToggleButtons("third_person", Boolean(data.camera.active));
    }
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
      actionMessage.textContent = shortenStatusLine(
        friendlyActionError(data?.message || JSON.stringify(data))
      );
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
      actionMessage.textContent = shortenStatusLine(data?.message || "Done.");
      if (action === "rewards_open_everyone" && data?.ok) {
        suppressOpenAllAfterChallenge = false;
      }
      if (action === "runtime_log" && Array.isArray(data?.lines)) {
        showRuntimeLogPanel(data.lines, data?.path || "");
        actionMessage.textContent =
          activeTabId === "log"
            ? `Log updated (${data.lines.length} line(s)).`
            : `Log: ${data.lines.length} line(s) — open the Log tab.`;
      }
      if (action === "party_player_info" && data?.ok) {
        showPartyStatsPanel(data);
        const n = Array.isArray(data.players) ? data.players.length : 0;
        const who = data.players?.[0]?.name || "player";
        actionMessage.textContent =
          n > 1 ? `Player stats updated (${n}).` : `Player stats: ${who}`;
      }
      if (["appearance_apply_selected", "appearance_apply_looked_at", "appearance_preview_selected"].includes(action) && data?.ok) {
        const code = Array.isArray(finalPayload.codes)
          ? String(finalPayload.codes[0] || "") : String(finalPayload.code || "");
        pollAppearanceApply(code, data.appearance?.operation_id, action === "appearance_preview_selected" ? "preview" : "applied");
      }
      if (["appearance_restore", "appearance_clear_previews"].includes(action) && data?.ok) {
        appearancePollToken++;
      }
      if (action === "serial_convert" && data?.ok) {
        renderSerialConvertResult(data);
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
        syncMobilityToggleButtons("force_fly_all",
          data?.force_fly_scope === "all" && Boolean(data?.force_fly_on));
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
    if (action === "hud_hide" && data?.ok !== false) {
      syncMobilityToggleButtons("hud_hidden", Boolean(data?.hidden));
    }
    if (action === "fps_display" && data?.ok !== false) {
      syncMobilityToggleButtons("fps_shown", Boolean(data?.shown));
    }
    if (action === "low_power" && data?.ok !== false) {
      syncMobilityToggleButtons("low_power", Boolean(data?.enabled));
    }
    if (action === "photo_preset" && data?.ok !== false) {
      for (const key of ["clean", "freecam", "wide"]) {
        syncMobilityToggleButtons(`photo_${key}`, data?.photo === key);
      }
    }
    if (action === "hold_session" && data?.ok !== false) {
      syncMobilityToggleButtons("hold_session", Boolean(data?.enabled));
    }
    if (action === "shift_friend_autoaccept") {
      if (data?.ok !== false && httpStatus !== 202) {
        const on = Object.prototype.hasOwnProperty.call(data || {}, "shift_friend_autoaccept")
          ? Boolean(data.shift_friend_autoaccept)
          : Boolean(finalPayload.enabled);
        stickyToggleGraceUntil.shift_friend_autoaccept = Date.now() + 2500;
        syncMobilityToggleButtons("shift_friend_autoaccept", on);
      } else {
        stickyToggleGraceUntil.shift_friend_autoaccept = Date.now() + 2500;
        syncMobilityToggleButtons("shift_friend_autoaccept", !Boolean(finalPayload.enabled));
      }
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
    if (resolvedAction === "mission_start" && data?.ok !== false && data?.running) {
      lastMissionStatus = {
        running: true,
        index: Number(data.index || 0),
        total: Number(data.total || 0),
        message: data.message || "Missions queued…",
      };
      lastProgressHtml = "";
      startProgressPoll();
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
            challengeCompleteDismissed = false;
            challengeFinishFlashUntil = 0;
            challengeSawLive = true;
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
              phase: "queued",
              progress_index: 0,
              progress_total: 7,
              message: "Starting…",
            };
            uvhmCompleteDismissed = false;
            uvhmErrorShownUntil = 0;
            uvhmBusyGraceUntil = 0;
            uvhmFinishFlashUntil = 0;
            uvhmSawLive = true;
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
        // Challenges first; UVHM is armed as a follow-up when both checkboxes are on.
        if (data?.challenges_queued) {
          const queuedN = Math.max(
            0,
            Number(data?.queued_count || data?.progress_total || data?.challenge?.progress_total || 0)
          );
          const uvhmNext = Boolean(data?.uvhm_queued);
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
            followup_uvhm: uvhmNext,
            message:
              queuedN > 0
                ? `MAX ALL · queued ${queuedN} challenges${uvhmNext ? " · UVHM after" : ""} — starting…`
                : `MAX ALL · challenges queued${uvhmNext ? " · UVHM after" : ""} — starting…`,
            _optimistic: true,
          });
          challengeOptimisticUntil = Date.now() + 45000;
          challengeCompleteShownUntil = 0;
          challengeCompleteDismissed = false;
          challengeFinishFlashUntil = 0;
          challengeSawLive = true;
          challengeProgressStartedAt = Date.now();
          challengeProgressTotalHint = queuedN;
          challengeDisplayMilestone = 0;
          suppressOpenAllAfterChallenge = true;
          lastProgressHtml = "";
          renderProgressPanel(null, null, null);
          startProgressPoll();
        } else if (data?.uvhm_queued) {
          lastUvhmStatus = {
            active: true,
            queued: true,
            running: true,
            phase: "queued",
            progress_index: 0,
            progress_total: 7,
            message: "UVHM queued from MAX ALL…",
          };
          uvhmCompleteDismissed = false;
          uvhmErrorShownUntil = 0;
          uvhmBusyGraceUntil = 0;
          uvhmFinishFlashUntil = 0;
          uvhmSawLive = true;
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
        // Keep paste-send textarea as-is so the same batch can be resent / tweaked.
        const nSerials = Array.isArray(finalPayload.serials) ? finalPayload.serials.length : 0;
        const perPkg = 8;
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
      const addedN = Math.max(
        1,
        Number(data?.added || 0) ||
          (Array.isArray(data?.entries) ? data.entries.length : 0) ||
          1
      );
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
      if (!serialStoreExpanded.has(context.sectionId)) {
        serialStoreExpanded.set(context.sectionId, new Set());
      }
      serialStoreExpanded.get(context.sectionId).add(savedGroup);
      renderSerialStoreForm(context.sectionId);
      // Must bust catalogCache — otherwise Save looks like a no-op (same bug as Delete pack).
      refreshAllSerialStoreSections();
      window.setTimeout(() => revealSerialStorePack(context.sectionId, savedGroup), 80);
      actionMessage.className = "action-message ok";
      actionMessage.textContent =
        data?.message ||
        (addedN > 1
          ? `Saved ${addedN} serial(s) to list “${savedGroup}”.`
          : `Saved to list “${savedGroup}”. Open that list below to see it.`);
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
      rememberSerialStorePackNames(context.sectionId, [
        ...serialStoreKnownPackNames(context.sectionId),
        group,
      ]);
      fieldValues[`${context.sectionId}:group`] = group;
      if (!serialStoreExpanded.has(context.sectionId)) {
        serialStoreExpanded.set(context.sectionId, new Set());
      }
      serialStoreExpanded.get(context.sectionId).add(group);
      renderSerialStoreForm(context.sectionId);
      refreshAllSerialStoreSections();
      window.setTimeout(() => revealSerialStorePack(context.sectionId, group), 80);
      actionMessage.className = "action-message ok";
        actionMessage.textContent = `Build “${group}” ready — paste codes, then save the build.`;
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
      // Must bust catalogCache — otherwise Delete pack looks like a no-op (stale GZO pack returns).
      refreshAllSerialStoreSections();
    }
    if (
      (action === "serial_store_add_selected" ||
        action === "serial_store_import_text" ||
        action === "serial_store_import_serials" ||
        action === "serial_store_import_merge") &&
      data?.ok
    ) {
      const savedGroup = String(
        data?.entry?.group ||
          data?.group ||
          payload?.group ||
          context?.payload?.group ||
          ""
      ).trim();
      // Expand destination list + filter so new rows show immediately (no EXE reload).
      for (const box of document.querySelectorAll("[data-multiselect-section]")) {
        const sid = box.dataset.multiselectSection;
        if (!sid) continue;
        const config = getMultiselectConfig(sid);
        if (config?.catalog !== "serial_store") continue;
        if (savedGroup) {
          if (!serialStoreExpanded.has(sid)) serialStoreExpanded.set(sid, new Set());
          serialStoreExpanded.get(sid).add(savedGroup);
          fieldValues[`${sid}:group`] = savedGroup;
          rememberSerialStorePackNames(sid, [
            ...serialStoreKnownPackNames(sid),
            savedGroup,
          ]);
          try {
            renderSerialStoreForm(sid);
          } catch {
            /* ignore */
          }
        }
      }
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
    if (action === "challenge_bulk_cancel") {
      const ch = normalizeChallengeStatus(
        data?.challenge && typeof data.challenge === "object"
          ? data.challenge
          : {
              active: false,
              running: false,
              queued: false,
              phase: data?.ok === false ? "idle" : "cancelled",
              message: data?.message || "Cancelled.",
              index: Number(lastChallengeStatus?.index || 0),
              total: Number(lastChallengeStatus?.total || 0),
              ok: Number(lastChallengeStatus?.ok || 0),
              failed: Number(lastChallengeStatus?.failed || 0),
              skipped: Number(lastChallengeStatus?.skipped || 0),
            }
      );
      if (ch) {
        lastChallengeStatus = {
          ...ch,
          active: false,
          running: false,
          queued: false,
          phase: data?.ok === false && !ch.running && ch.phase !== "cancelled" ? "idle" : "cancelled",
        };
      } else {
        lastChallengeStatus = null;
      }
      challengeOptimisticUntil = 0;
      challengeBusyGraceUntil = 0;
      challengeCancelHoldUntil = Date.now() + 2500;
      challengeCompleteShownUntil = Date.now() + 1500;
      challengeCompleteDismissed = false;
      challengeDisplayMilestone = 0;
      lastProgressHtml = "";
      renderProgressPanel(null, null, null);
      // Keep a short poll so the cancel flash can expire and the panel re-hides.
      startProgressPoll();
    }
    if (action === "uvhm_status") {
      renderProgressPanel(null, data?.uvhm, null);
    }
    if (action === "uvhm_cancel") {
      const uv = data?.uvhm && typeof data.uvhm === "object" ? data.uvhm : null;
      lastUvhmStatus = uv
        ? { ...uv, active: false, running: false, queued: false, phase: "cancelled" }
        : {
            active: false,
            running: false,
            queued: false,
            phase: "cancelled",
            message: data?.message || "UVHM cancelled.",
          };
      uvhmCompleteDismissed = false;
      uvhmCancelHoldUntil = Date.now() + 2500;
      uvhmErrorShownUntil = Date.now() + 1500;
      uvhmBusyGraceUntil = 0;
      lastProgressHtml = "";
      renderProgressPanel(null, null, null);
      startProgressPoll();
    }
    if (action === "spawn_item_pool_status" || action === "spawn_item_pool_cancel") {
      renderProgressPanel(null, null, data?.spawn_all);
    }
    return data || { ok: false, message: "No action result received." };
  } catch (error) {
    if (["give_everything", "map_fog_unlock"].includes(resolvedAction)) {
      lastGiveEverythingStatus = null;
      lastProgressHtml = "";
      renderProgressPanel(null, null, null);
    }
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
    return { ok: false, message: text };
  } finally {
    actionBusy = false;
    refreshActionButtons();
  }
}

function applyFieldValues(values) {
  if (!values || typeof values !== "object") return;
  if (isUserEditingTools()) return;
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
      // Must re-render so Complete flash actually hides (timer alone left the box up).
      lastProgressHtml = "";
      renderProgressPanel(null, null, null);
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

function challengeIsCancelled(st) {
  const phase = String(st?.phase || "").toLowerCase();
  return phase === "cancelled" || /^cancelled/i.test(String(st?.message || ""));
}

function uvhmIsCancelled(st) {
  const phase = String(st?.phase || "").toLowerCase();
  return phase === "cancelled" || phase === "error";
}

/** When live work ends, force a Complete snapshot so the bar always shows Finished. */
function applyChallengeFinishEdge(next) {
  const live = Boolean(next && (next.queued || next.running));
  const phase = String(next?.phase || "").toLowerCase();
  if (live) {
    challengeSawLive = true;
    challengeCompleteDismissed = false;
    challengeFinishFlashUntil = 0;
    return next;
  }
  if (challengeIsCancelled(next) || Date.now() < challengeCancelHoldUntil) {
    challengeSawLive = false;
    challengeFinishFlashUntil = 0;
    return next;
  }
  const modComplete = phase === "complete" || /^complete:/i.test(String(next?.message || ""));
  if ((challengeSawLive || modComplete) && !challengeCompleteDismissed) {
    challengeSawLive = false;
    if (!challengeFinishFlashUntil || Date.now() >= challengeFinishFlashUntil) {
      challengeFinishFlashUntil = Date.now() + 2500;
    }
    challengeCompleteShownUntil = challengeFinishFlashUntil;
    const total = Math.max(
      1,
      Number(next?.total || next?.progress_total || lastChallengeStatus?.total || challengeProgressTotalHint || 1)
    );
    const ok = Number(next?.ok ?? lastChallengeStatus?.ok ?? 0);
    const failed = Number(next?.failed ?? lastChallengeStatus?.failed ?? 0);
    const skipped = Number(next?.skipped ?? lastChallengeStatus?.skipped ?? 0);
    return {
      ...(lastChallengeStatus && typeof lastChallengeStatus === "object" ? lastChallengeStatus : {}),
      ...(next && typeof next === "object" ? next : {}),
      active: true,
      running: false,
      queued: false,
      phase: "complete",
      index: total,
      progress_index: total,
      total,
      progress_total: total,
      ok,
      failed,
      skipped,
      message:
        /^complete:/i.test(String(next?.message || ""))
          ? String(next.message)
          : `Complete: ${ok} accepted, ${failed} failed${skipped ? `, ${skipped} skipped` : ""}.`,
      _finishFlash: true,
      _optimistic: false,
    };
  }
  if (Date.now() < challengeFinishFlashUntil && lastChallengeStatus?._finishFlash) {
    return lastChallengeStatus;
  }
  return next;
}

function applyUvhmFinishEdge(next) {
  const live = Boolean(next && (next.queued || next.running));
  const phase = String(next?.phase || "").toLowerCase();
  if (live) {
    uvhmSawLive = true;
    uvhmCompleteDismissed = false;
    uvhmFinishFlashUntil = 0;
    return next;
  }
  if (uvhmIsCancelled(next) || Date.now() < uvhmCancelHoldUntil) {
    uvhmSawLive = false;
    uvhmFinishFlashUntil = 0;
    return next;
  }
  const modComplete = phase === "complete";
  if ((uvhmSawLive || modComplete) && !uvhmCompleteDismissed) {
    uvhmSawLive = false;
    if (!uvhmFinishFlashUntil || Date.now() >= uvhmFinishFlashUntil) {
      uvhmFinishFlashUntil = Date.now() + 2500;
    }
    uvhmErrorShownUntil = uvhmFinishFlashUntil;
    const total = Math.max(
      1,
      Number(next?.progress_total || next?.total || lastUvhmStatus?.progress_total || 7)
    );
    const msg = String(next?.message || lastUvhmStatus?.message || "UVHM complete.");
    return {
      ...(lastUvhmStatus && typeof lastUvhmStatus === "object" ? lastUvhmStatus : {}),
      ...(next && typeof next === "object" ? next : {}),
      active: true,
      running: false,
      queued: false,
      phase: "complete",
      progress_index: total,
      progress_total: total,
      progress_percent: 100,
      message: /complete/i.test(msg) ? msg : "UVHM complete.",
      _finishFlash: true,
    };
  }
  if (Date.now() < uvhmFinishFlashUntil && lastUvhmStatus?._finishFlash) {
    return lastUvhmStatus;
  }
  return next;
}

function isChallengeBusy(challenge) {
  if (!challenge) {
    challengeBusyGraceUntil = 0;
    return false;
  }
  if (Date.now() < challengeFinishFlashUntil && (challenge._finishFlash || String(challenge.phase || "").toLowerCase() === "complete")) {
    return true;
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
    challengeCompleteDismissed = false;
    return true;
  }
  // Trust running/queued for live work. Sticky active alone is Complete/Cancel flash.
  const workLive = Boolean(challenge.queued || challenge.running);

  // Cancel: short flash then hide (unless another job is still running elsewhere).
  if (phase === "cancelled" || /^cancelled/i.test(msg)) {
    if (workLive) {
      challengeCompleteDismissed = false;
      return true;
    }
    if (challengeCompleteDismissed) return false;
    challengeBusyGraceUntil = 0;
    challengeOptimisticUntil = 0;
    if (!challengeCompleteShownUntil) challengeCompleteShownUntil = Date.now() + 1200;
    if (Date.now() >= challengeCompleteShownUntil) {
      challengeCompleteDismissed = true;
      challengeFinishFlashUntil = 0;
      return false;
    }
    return true;
  }
  // Complete: show Finished, then dismiss once (no sticky re-open).
  if (phase === "complete" || /^complete:/i.test(msg) || challenge._finishFlash) {
    if (workLive) {
      challengeCompleteDismissed = false;
      return true;
    }
    if (challengeCompleteDismissed) return false;
    challengeBusyGraceUntil = 0;
    challengeOptimisticUntil = 0;
    if (!challengeCompleteShownUntil) challengeCompleteShownUntil = Date.now() + 2500;
    if (!challengeFinishFlashUntil) challengeFinishFlashUntil = challengeCompleteShownUntil;
    if (Date.now() >= challengeCompleteShownUntil && Date.now() >= challengeFinishFlashUntil) {
      challengeCompleteDismissed = true;
      challengeFinishFlashUntil = 0;
      return false;
    }
    return true;
  }
  if (!workLive && !challenge.active) {
    challengeCompleteShownUntil = 0;
    challengeBusyGraceUntil = 0;
    challengeOptimisticUntil = 0;
    return false;
  }
  if (!workLive) {
    challengeCompleteShownUntil = 0;
    challengeBusyGraceUntil = 0;
    challengeOptimisticUntil = 0;
    return false;
  }
  challengeCompleteDismissed = false;
  challengeCompleteShownUntil = 0;
  challengeBusyGraceUntil = Date.now() + 3500;
  challengeOptimisticUntil = 0;
  return true;
}

function isUvhmBusy(uvhm) {
  if (!uvhm) {
    uvhmBusyGraceUntil = 0;
    return false;
  }
  if (Date.now() < uvhmFinishFlashUntil && (uvhm._finishFlash || String(uvhm.phase || "").toLowerCase() === "complete")) {
    return true;
  }
  const phase = String(uvhm.phase || "").toLowerCase();
  const workLive = Boolean(uvhm.queued || uvhm.running);
  if (phase === "error" || phase === "cancelled") {
    uvhmBusyGraceUntil = 0;
    if (!workLive && !uvhm.active) {
      if (uvhmCompleteDismissed) return false;
      if (!uvhmErrorShownUntil) uvhmErrorShownUntil = Date.now() + 1200;
      if (Date.now() >= uvhmErrorShownUntil) {
        uvhmCompleteDismissed = true;
        uvhmFinishFlashUntil = 0;
        return false;
      }
      return true;
    }
    if (workLive) uvhmCompleteDismissed = false;
    if (!uvhmErrorShownUntil) uvhmErrorShownUntil = Date.now() + 1500;
    if (Date.now() >= uvhmErrorShownUntil) {
      uvhmCompleteDismissed = true;
      uvhmFinishFlashUntil = 0;
      return false;
    }
    return true;
  }
  if ((phase === "complete" || uvhm._finishFlash) && !workLive) {
    if (uvhmCompleteDismissed) return false;
    if (!uvhmErrorShownUntil) uvhmErrorShownUntil = Date.now() + 2500;
    if (!uvhmFinishFlashUntil) uvhmFinishFlashUntil = uvhmErrorShownUntil;
    uvhmBusyGraceUntil = 0;
    if (Date.now() >= uvhmErrorShownUntil && Date.now() >= uvhmFinishFlashUntil) {
      uvhmCompleteDismissed = true;
      uvhmFinishFlashUntil = 0;
      return false;
    }
    return true;
  }
  // Idle with no live work — hide. Do NOT mark dismissed here if a finish flash
  // still needs to paint (falling-edge Complete is handled above).
  if ((phase === "idle" || phase === "") && !workLive) {
    uvhmErrorShownUntil = 0;
    uvhmBusyGraceUntil = 0;
    if (!uvhmSawLive && Date.now() >= uvhmFinishFlashUntil) {
      uvhmCompleteDismissed = true;
    }
    return false;
  }
  uvhmCompleteDismissed = false;
  uvhmErrorShownUntil = 0;
  const live = Boolean(
    workLive &&
      phase !== "complete" &&
      phase !== "cancelled" &&
      phase !== "error"
  );
  if (live) {
    uvhmBusyGraceUntil = Date.now() + 2200;
    return true;
  }
  if (uvhm.active && !workLive) {
    return false;
  }
  if (Date.now() < uvhmBusyGraceUntil) {
    if (phase === "complete" || phase === "idle" || phase === "cancelled" || !phase) {
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
function isMissionBusy(mission) {
  return Boolean(mission && mission.running);
}
function isGiveEverythingBusy(job) {
  return Boolean(job && (job.running || job.active));
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

function challengeBarFillPercent(index, total) {
  const totalI = Math.max(0, Number(total) || 0);
  const indexI = Math.max(0, Number(index) || 0);
  if (totalI <= 0) return indexI > 0 ? 8 : 0;
  const raw = Math.min(100, (Math.min(indexI, totalI) / totalI) * 100);
  if (indexI > 0 && indexI < totalI) return Math.max(0.35, raw);
  return raw;
}

function applyBridgeChallengeSnapshot(raw) {
  const give = raw?.give_everything;
  if (give && typeof give === "object") {
    if (give.running || give.active) {
      lastGiveEverythingStatus = give;
      lastProgressHtml = "";
      renderProgressPanel(null, null, null);
      if (!progressPollTimer) startProgressPoll();
    } else if (lastGiveEverythingStatus && Date.now() >= Number(lastGiveEverythingStatus._optimisticUntil || 0)) {
      lastGiveEverythingStatus = null;
      lastProgressHtml = "";
      renderProgressPanel(null, null, null);
    }
  }
  const bulk = raw?.challenge_bulk;
  if (!bulk || typeof bulk !== "object") return;
  const next = normalizeChallengeStatus(bulk);
  if (!next) return;
  const workLive = Boolean(next.queued || next.running);
  const phase = String(next.phase || "").toLowerCase();
  const terminal = phase === "complete" || phase === "cancelled";
  // After Complete/Cancel flash ends, ignore leftover sticky active snapshots.
  if (!workLive && terminal && challengeCompleteDismissed) return;
  const live = Boolean(next.active || workLive);
  if (!live) return;
  if (
    Date.now() < challengeCancelHoldUntil &&
    workLive &&
    phase !== "cancelled"
  ) {
    return;
  }
  const prev = lastChallengeStatus;
  const prevIndex = Math.max(
    0,
    Number(prev?.raw_index || 0),
    Number(prev?.progress_index || prev?.index || 0)
  );
  const nextIndex = Math.max(
    0,
    Number(next.raw_index || 0),
    Number(next.progress_index || next.index || 0)
  );
  if (prev?._optimistic || !prev || nextIndex > prevIndex || terminal) {
    lastChallengeStatus = next;
    challengeOptimisticUntil = 0;
    lastProgressHtml = "";
    renderProgressPanel(null, null, null);
    if (isChallengeBusy(lastChallengeStatus) && !progressPollTimer) startProgressPoll();
  }
}

/** Prefer raw_index / accepted counts so the bar tracks live work. */
function challengeDisplayIndex(challengeState) {
  const total = Math.max(
    0,
    Number(challengeState?.total || challengeState?.progress_total || challengeProgressTotalHint || 0)
  );
  const phase = String(challengeState?.phase || "").toLowerCase();
  if (phase === "complete") {
    challengeDisplayMilestone = total;
    return total;
  }
  const rawDone = Math.max(
    0,
    Number(challengeState?.raw_index || 0),
    Number(challengeState?.progress_index ?? challengeState?.index ?? 0),
    Number(challengeState?.ok || 0) +
      Number(challengeState?.failed || 0) +
      Number(challengeState?.skipped || 0)
  );
  const next = Math.max(challengeDisplayMilestone, Math.min(total || rawDone, rawDone));
  challengeDisplayMilestone = next;
  return next;
}

function normalizeChallengeStatus(raw) {
  if (!raw || typeof raw !== "object") return null;
  const total = Math.max(0, Number(raw.total || raw.progress_total || 0));
  const accepted = Number(raw.ok || raw.accepted || 0);
  const failed = Number(raw.failed || 0);
  const skipped = Number(raw.skipped || 0);
  const rawIndex = Math.max(
    0,
    Number(raw.raw_index || 0),
    Number(raw.progress_index ?? raw.index ?? 0),
    accepted + failed + skipped
  );
  const index = total > 0 ? Math.min(rawIndex, total) : rawIndex;
  const msg = String(raw.message || "");
  const phaseRaw = String(raw.phase || "").toLowerCase();
  const queued = Boolean(raw.queued);
  // Never invent running from sticky active — that kept Cancel looking "live".
  const running = Boolean(raw.running);
  const terminal = phaseRaw === "complete" || phaseRaw === "cancelled" || phaseRaw === "error";
  const phase =
    phaseRaw ||
    (queued ? "queued" : running ? "running" : terminal ? phaseRaw : raw.active && !terminal ? "running" : "idle");
  return {
    ...raw,
    active: Boolean(raw.active || queued || running),
    queued,
    running,
    phase: phase || "idle",
    total,
    progress_total: total,
    index,
    progress_index: index,
    raw_index: rawIndex,
    ok: accepted,
    failed,
    skipped,
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
  const guestRuns = Array.isArray(raw.guest_runs)
    ? raw.guest_runs
        .filter((row) => row && typeof row === "object")
        .map((row) => ({
          name: String(row.name || "?"),
          index: Number(row.index || 0),
          done: Number(row.done || 0),
          total: Number(row.total || 0),
          complete: Boolean(row.complete),
        }))
    : [];
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
    guest_runs: guestRuns,
    guest_count: Number(raw.guest_count || guestRuns.length || 0),
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
  const giveEverythingState = lastGiveEverythingStatus;

  const clampPct = (value, total) => {
    const safeTotal = Math.max(1, Number(total || 0));
    const safeValue = Math.max(0, Number(value || 0));
    return Math.min(100, Math.max(0, Math.round((safeValue / safeTotal) * 100)));
  };

  const giveEverythingBusy = isGiveEverythingBusy(giveEverythingState);
  const challengeBusy = isChallengeBusy(challengeState) && !giveEverythingBusy;
  const uvhmBusy = isUvhmBusy(uvhmState) && !giveEverythingBusy;
  const spawnBusy = isSpawnAllBusy(spawnState);
  const serialBusy = isSerialDeliveryBusy(serialState);
  const autoLobbyArmed = isAutoLobbyArmed(autoLobbyState);
  const autoLobbyBusy = isAutoLobbyBusy(autoLobbyState);
  const shapeState = lastShapeStatus;
  const shapeBusy = isShapeBusy(shapeState);
  const vacuumBusy = isVacuumBusy(vacuumState);
  const missionState = lastMissionStatus;
  const missionBusy = isMissionBusy(missionState) && !giveEverythingBusy;
  // Floating bar: live jobs only. Auto Lobby "armed / waiting" still paints when armed,
  // but idle armed must not keep the panel stuck after other jobs finish without status.
  const busy =
    giveEverythingBusy ||
    challengeBusy ||
    uvhmBusy ||
    spawnBusy ||
    serialBusy ||
    autoLobbyBusy ||
    autoLobbyArmed ||
    shapeBusy ||
    vacuumBusy ||
    missionBusy;

  let html = "";
  if (giveEverythingBusy) {
    const pct = Math.min(100, Math.max(0, Number(giveEverythingState.progress_percent || 0)));
    const state = String(giveEverythingState.phase || "running").toLowerCase();
    const stage = String(giveEverythingState.workflow_phase || "").toLowerCase();
    const stageNames = { missions: "Missions", challenges: "Challenges", uvhm: "UVHM ranks", grassroots: "Grassroots side mission", discovery: "Map / safehouses / terrain" };
    const finished = state === "complete";
    const workflowLabel = giveEverythingState.discovery_only ? "Map discovery" : "Give everything";
    const title = state === "partial" ? `${workflowLabel} — Finished; check details` : finished ? `${workflowLabel} — Complete` : state === "stopped" ? `${workflowLabel} — Stopped` : workflowLabel;
    const step = Number(giveEverythingState.phase_number || 0);
    const stepTotal = Number(giveEverythingState.phase_total || 4);
    const childIndex = Number(giveEverythingState.child_index || 0);
    const childTotal = Number(giveEverythingState.child_total || 0);
    const count = childTotal > 0 ? ` · ${Math.min(childIndex, childTotal)}/${childTotal}` : "";
    const detail = String(giveEverythingState.child_message || giveEverythingState.message || stageNames[stage] || "Working…");
    html += `<div data-progress-job="give-everything"><h4>${title}</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${pct.toFixed(0)}% · step ${Math.min(step, stepTotal)}/${stepTotal} · ${stageNames[stage] || stage || "Starting"}${count}</p>
      <p class="progress-meta muted">${escapeHtml(detail)}</p>
      ${giveEverythingState.running ? '<button type="button" class="progress-stop-btn" data-give-everything-stop="1">Stop</button>' : ""}</div>`;
  }
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
    const guestRuns = Array.isArray(autoLobbyState.guest_runs) ? autoLobbyState.guest_runs : [];
    const guestLine = guestRuns.length
      ? guestRuns
          .slice(0, 4)
          .map((g) =>
            g.complete
              ? `${g.name} ✓`
              : `${g.name} ${Math.max(0, Number(g.done) || 0)}/${Math.max(0, Number(g.total) || 0)}`
          )
          .join(" · ") + (guestRuns.length > 4 ? "…" : "")
      : "";
    const dripCountdown =
      autoLobbyState.drip_phase === "wait_mail" && autoLobbyState.drip_drop_in > 0
        ? `ITEMS DROP IN ${Math.ceil(autoLobbyState.drip_drop_in)}s — stand clear`
        : "";
    html += `<div data-progress-job="auto-lobby"><h4>Auto Lobby</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${countLine}</p>
      ${guestLine ? `<p class="progress-meta muted">${guestLine}</p>` : ""}
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
    const fill = waitingTick ? 8 : challengeBarFillPercent(Math.min(index, total), total);
    const detail =
      challengeProgressDetail(challengeState.message) ||
      (waitingTick ? "Queued — waiting for world tick…" : `Working · ${index}/${total}`);
    const tokenRaw = String(challengeState.token || "");
    const token =
      tokenRaw.length > 28 ? ` · ${tokenRaw.slice(0, 25)}…` : tokenRaw ? ` · ${tokenRaw}` : "";
    const skipBit =
      Number(challengeState.skipped || 0) > 0 ? ` · skip ${challengeState.skipped}` : "";
    const seatTotal = Math.max(0, Number(challengeState.target_total || 0));
    const seatIdx = Math.max(0, Number(challengeState.target_index || 0));
    const seatName = String(challengeState.current_target || challengeState.target || "").trim();
    const seatBit =
      seatTotal > 1 &&
      String(challengeState.phase || "").toLowerCase() !== "complete" &&
      !/^complete:/i.test(String(challengeState.message || ""))
        ? ` · seat ${Math.min(seatIdx + 1, seatTotal)}/${seatTotal}${
            seatName ? ` (${seatName})` : ""
          }`
        : seatTotal > 1 &&
            (String(challengeState.phase || "").toLowerCase() === "complete" ||
              /^complete:/i.test(String(challengeState.message || "")))
          ? ` · ${seatTotal}/${seatTotal} seats done`
          : "";
    const countLine = waitingTick
      ? rawTotal > 0
        ? `Starting ${rawTotal}…`
        : "Starting…"
      : `${Math.min(index, total)}/${total} · OK ${challengeState.ok || 0} · fail ${challengeState.failed || 0}${skipBit}${seatBit}${token}`;
    const challengeDone =
      String(challengeState.phase || "").toLowerCase() === "complete" ||
      Boolean(challengeState._finishFlash) ||
      /^complete:/i.test(String(challengeState.message || ""));
    html += `<div data-progress-job="challenge"><h4>${
      challengeDone ? "Challenge bulk — Complete ✓" : "Challenge bulk"
    }</h4>
      <div class="progress-bar"><span data-fill="${Number(fill).toFixed(2)}" style="width:${Number(fill).toFixed(2)}%"></span></div>
      <p class="progress-meta muted">${countLine}</p>
      <p class="progress-meta muted">${detail}</p>
      ${
        challengeDone
          ? ""
          : '<button type="button" class="progress-stop-btn" data-challenge-stop="1">Stop challenges</button>'
      }</div>`;
  }
  if (uvhmBusy) {
    const total = Math.max(1, Number(uvhmState.progress_total || uvhmState.total || uvhmState.steps_total || 7));
    const index = Math.max(0, Number(uvhmState.progress_index || uvhmState.index || uvhmState.step || 0));
    const uvhmDone =
      String(uvhmState.phase || "").toLowerCase() === "complete" || Boolean(uvhmState._finishFlash);
    // Prefer mod progress_percent (settle polls). Never Math.round — that froze the last rank.
    let pct;
    if (uvhmDone) {
      pct = 100;
    } else if (Number.isFinite(Number(uvhmState.progress_percent))) {
      pct = Math.min(100, Math.max(0, Number(uvhmState.progress_percent)));
    } else {
      pct = Math.min(100, Math.max(0, (index / total) * 100));
    }
    const pctLabel = pct >= 99.95 ? "100" : pct.toFixed(pct < 10 ? 1 : 0);
    let detail = String(uvhmState.message || `Step ${index}/${total}`);
    detail = detail.replace(/Allowing .+ to settle \(\d+\/\d+\)\.?/i, "Settling rank…");
    detail = detail.replace(/Waiting for .+ to settle\.{0,3}/i, "Settling rank…");
    if (uvhmDone && !/complete/i.test(detail)) detail = "Complete.";
    if (detail.length > 120) detail = `${detail.slice(0, 117)}…`;
    const target = uvhmState.target_name ? `${uvhmState.target_name} · ` : "";
    const seatBit =
      Number(uvhmState.target_count || 0) > 1 && Number(uvhmState.target_number || 0) > 0
        ? `player ${uvhmState.target_number}/${uvhmState.target_count} · `
        : "";
    const rankBit =
      uvhmState.rank != null && uvhmState.rank !== ""
        ? `rank ${uvhmState.rank}${uvhmState.max_rank ? `/${uvhmState.max_rank}` : ""} · `
        : "";
    const autoBit =
      autoLobbyArmed || autoLobbyBusy
        ? ' <span class="progress-auto-tag" title="Auto Lobby">Auto</span>'
        : "";
    const uvhmLive = Boolean(uvhmState.queued || uvhmState.running);
    const indexLabel = Number.isInteger(index) ? String(index) : index.toFixed(1);
    html += `<div data-progress-job="uvhm"><h4>${
      uvhmDone ? "UVHM progression — Complete ✓" : "UVHM progression"
    }${autoBit}</h4>
      <div class="progress-bar"><span data-fill="${Number(pct).toFixed(2)}" style="width:${Number(pct).toFixed(2)}%"></span></div>
      <p class="progress-meta muted">${pctLabel}% · ${indexLabel}/${total} · ${seatBit}${target}${rankBit}${detail}</p>
      ${
        uvhmLive && !uvhmDone
          ? '<button type="button" class="progress-stop-btn" data-uvhm-stop="1">Stop UVHM</button>'
          : ""
      }</div>`;
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
  if (missionBusy) {
    const total = Math.max(1, Number(missionState.total || 1));
    const index = Math.max(0, Number(missionState.index || 0));
    const pct = clampPct(index, total);
    const results = Array.isArray(missionState.results) ? missionState.results : [];
    const recentResults = results.slice(-6).reverse();
    const outcomeLabel = (row) =>
      String(row?.outcome || "unknown").replaceAll("_", " ");
    const evidenceHtml = recentResults.length
      ? `<details class="progress-evidence"><summary>Observed mission results (${results.length})</summary>
          ${recentResults
            .map(
              (row) =>
                `<p class="progress-meta muted"><strong>${escapeHtml(row?.title || row?.name || "Mission")}</strong> · ` +
                `${escapeHtml(outcomeLabel(row))}${row?.uncertain ? " · uncertain write" : ""}` +
                `${row?.after ? ` · observed ${escapeHtml(String(row.after))}` : ""}<br>` +
                `${escapeHtml(row?.reason || "")}</p>`
            )
            .join("")}</details>`
      : "";
    const issueBits = [
      Number(missionState.locked || 0) ? `locked ${Number(missionState.locked)}` : "",
      Number(missionState.unsupported || 0)
        ? `unsupported ${Number(missionState.unsupported)}`
        : "",
      Number(missionState.blocked_count || 0)
        ? `blocked ${Number(missionState.blocked_count)}`
        : "",
      Number(missionState.failed || 0) ? `failed ${Number(missionState.failed)}` : "",
    ].filter(Boolean);
    html += `<div data-progress-job="missions"><h4>Missions</h4>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-meta muted">${Math.min(index, total)}/${total} · verified ${missionState.completed || 0} · already completed ${missionState.already || 0}${issueBits.length ? ` · ${issueBits.join(" · ")}` : ""}</p>
      <p class="progress-meta muted">${escapeHtml(missionState.message || "")}</p>
      ${evidenceHtml}
      <button type="button" class="progress-stop-btn" data-mission-stop="1">Stop missions</button></div>`;
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
    // Drop terminal caches so the next status poll cannot revive Complete.
    if (lastChallengeStatus && !isChallengeBusy(lastChallengeStatus)) {
      lastChallengeStatus = null;
      challengeOptimisticUntil = 0;
      challengeProgressStartedAt = 0;
      challengeProgressTotalHint = 0;
      challengeDisplayMilestone = 0;
    }
    if (lastUvhmStatus && !isUvhmBusy(lastUvhmStatus)) {
      lastUvhmStatus = null;
    }
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
      const fillAttr = freshSpan?.getAttribute("data-fill");
      if (span && fillAttr) {
        span.setAttribute("data-fill", fillAttr);
        span.style.width = `${fillAttr}%`;
      } else if (span && freshSpan && freshSpan.style.width) {
        span.style.width = freshSpan.style.width;
      }
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
      const fillAttr = freshSpan?.getAttribute("data-fill");
      if (span && fillAttr) {
        span.setAttribute("data-fill", fillAttr);
        span.style.width = `${fillAttr}%`;
      } else if (span && freshSpan && freshSpan.style.width) {
        span.style.width = freshSpan.style.width;
      }
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
    // Auto Lobby drip / mail / kick must NOT also spam challenge+UVHM+spawn
    // status — that froze the EXE when flipping tabs mid-run.
    // Skip heavy bridge polls while mail/vacuum/auto are loud — but NEVER skip
    // challenge_bulk_status while challenges are live (that froze the bar mid-job).
    const lightBridge =
      !heavyProgress &&
      !spawnBusy &&
      !shapeBusy &&
      (serialBusy || autoBusy || vacuumBusy);

    const jobs = [
      challengeBusy || !lightBridge
        ? window.sqbt.postAction("challenge_bulk_status", {}, 3)
        : Promise.resolve({ data: lastChallengeStatus ? { challenge: lastChallengeStatus } : null }),
      // Always poll UVHM during heavy rounds — skipping while challenges flash
      // Complete used to miss UVHM finish entirely on MAX ALL.
      lightBridge
        ? Promise.resolve({ data: lastUvhmStatus ? { uvhm: lastUvhmStatus } : null })
        : window.sqbt.postAction("uvhm_status", {}),
      lightBridge || heavyProgress
        ? Promise.resolve({ data: null })
        : window.sqbt.postAction("spawn_item_pool_status", {}),
      serialBusy
        ? window.sqbt.postAction("serial_delivery_status", {}, 8)
        : Promise.resolve({
            data: lastSerialDeliveryStatus ? { status: lastSerialDeliveryStatus } : null,
          }),
      autoBusy && !heavyProgress
        ? window.sqbt.postAction("auto_lobby_get", {})
        : Promise.resolve({ data: null }),
      shapeBusy && !lightBridge
        ? window.sqbt.postAction("loot_shape_status", {})
        : Promise.resolve({ data: null }),
      vacuumBusy && !heavyProgress
        ? window.sqbt.postAction("loot_vacuum_status", {})
        : Promise.resolve({ data: null }),
      isMissionBusy(lastMissionStatus)
        ? window.sqbt.postAction("mission_status", {})
        : Promise.resolve({ data: null }),
    ];
    jobs.push(isGiveEverythingBusy(lastGiveEverythingStatus)
      ? window.sqbt.postAction("give_everything_status", {}, 3)
      : Promise.resolve({ data: null }));
    const [challengeRes, uvhmRes, spawnRes, serialRes, autoLobbyRes, shapeRes, vacuumRes, missionRes, giveRes] =
      await Promise.all(jobs.map((job) => Promise.resolve(job).catch(() => ({ data: null }))));
    if (giveRes?.data?.give_everything) applyBridgeChallengeSnapshot(giveRes.data);
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
      const chPhase = String(challenge.phase || "").toLowerCase();
      const chWork = Boolean(challenge.queued || challenge.running);
      // Local Stop wins over a stale in-flight poll that still says running.
      if (
        Date.now() < challengeCancelHoldUntil &&
        chWork &&
        chPhase !== "cancelled" &&
        chPhase !== "complete"
      ) {
        /* keep cancelled snapshot */
      } else {
        lastChallengeStatus = applyChallengeFinishEdge(challenge);
        if (!challenge._optimistic) challengeOptimisticUntil = 0;
        if (chPhase === "cancelled" || chPhase === "complete" || !chWork) {
          challengeCancelHoldUntil = 0;
        }
      }
    } else if (challengeSawLive && !challengeCompleteDismissed) {
      lastChallengeStatus = applyChallengeFinishEdge({
        active: false,
        running: false,
        queued: false,
        phase: "idle",
        message: "Idle.",
      });
    }
    if (uvhm) {
      const uvPhase = String(uvhm.phase || "").toLowerCase();
      const uvWork = Boolean(uvhm.queued || uvhm.running);
      if (
        Date.now() < uvhmCancelHoldUntil &&
        uvWork &&
        uvPhase !== "cancelled" &&
        uvPhase !== "complete" &&
        uvPhase !== "idle"
      ) {
        /* keep cancelled snapshot */
      } else {
        lastUvhmStatus = applyUvhmFinishEdge(uvhm);
        if (uvPhase === "cancelled" || uvPhase === "complete" || uvPhase === "idle" || !uvWork) {
          uvhmCancelHoldUntil = 0;
        }
      }
    } else if (uvhmSawLive && !uvhmCompleteDismissed) {
      lastUvhmStatus = applyUvhmFinishEdge({
        active: false,
        running: false,
        queued: false,
        phase: "idle",
        message: "Idle.",
      });
    }
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
      const chPhase = String(lastChallengeStatus.phase || "").toLowerCase();
      if (
        chPhase === "complete" ||
        chPhase === "cancelled" ||
        /^complete:/i.test(String(lastChallengeStatus.message || ""))
      ) {
        challengeCompleteDismissed = true;
      }
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
        if (phase === "complete" || phase === "error" || phase === "cancelled") {
          uvhmCompleteDismissed = true;
        }
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
    const mission = missionRes.data?.mission;
    if (mission && typeof mission === "object") {
      lastMissionStatus = mission;
      if (!isMissionBusy(mission) && mission.message && actionMessage) {
        actionMessage.className = `action-message ${mission.phase === "complete" ? "ok" : "attention"}`;
        actionMessage.textContent = shortenStatusLine(String(mission.message));
      }
    }
    if (lastMissionStatus && !isMissionBusy(lastMissionStatus)) {
      lastMissionStatus = null;
    }
    renderProgressPanel(null, null, null);
    const busy =
      isChallengeBusy(lastChallengeStatus) ||
      isUvhmBusy(lastUvhmStatus) ||
      isSpawnAllBusy(lastSpawnAllStatus) ||
      isSerialDeliveryBusy(lastSerialDeliveryStatus) ||
      isAutoLobbyBusy(lastAutoLobbyStatus) ||
      isShapeBusy(lastShapeStatus) ||
      isVacuumBusy(lastVacuumStatus) ||
      isMissionBusy(lastMissionStatus) ||
      isGiveEverythingBusy(lastGiveEverythingStatus);
    if (busy) {
      // Challenges finish in seconds — poll fast or the bar stays on 0/N queued.
      // Auto Lobby drip / serial-only: slow + light bridge (was freezing tab switches).
      const lightOnly =
        !challengeBusy &&
        !uvhmBusy &&
        !spawnBusy &&
        !isShapeBusy(lastShapeStatus) &&
        (isSerialDeliveryBusy(lastSerialDeliveryStatus) ||
          isAutoLobbyBusy(lastAutoLobbyStatus) ||
          isVacuumBusy(lastVacuumStatus));
      const pollMs = challengeBusy
        ? 350
        : uvhmBusy
          ? 500
          : heavyProgress
            ? 800
            : lightOnly
              ? 2000
              : 1000;
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
    // Restart for challenge OR UVHM complete flash — UVHM-only used to stop polling
    // and leave the box on screen after a failed/skipped status round.
    if (
      !progressPollTimer &&
      (isGiveEverythingBusy(lastGiveEverythingStatus) || isChallengeBusy(lastChallengeStatus) || isUvhmBusy(lastUvhmStatus))
    ) {
      progressPollMs = 400;
      progressPollTimer = setInterval(() => {
        pollProgressOnce();
      }, progressPollMs);
    }
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
  if (isUserEditingTools()) return;
  refreshGlobalTargetSelect();
  refreshAllKickExemptFields();
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
    // Boost sticky wins over stale fieldValues (host 0) so pool/shiny dropdowns
    // do not flick back to the host after selecting a guest.
    if (stickyTargetInRoster(players) && stickyTargetIndex != null) {
      const sticky = String(stickyTargetIndex);
      if (includeAll || sticky !== "-1") {
        current = sticky;
      }
    } else if (globalIdx !== "" && (current === undefined || current === "")) {
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
      // Roster churn (Auto Lobby joins) must not rebuild Item lists / GZO /
      // Lootlemon — that fought <details> expand and collapsed packs mid-click.
      if (
        config.catalog === "serial_store" ||
        config.catalog === "gzo" ||
        config.catalog === "lootlemon"
      ) {
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
    if (isUserEditingTools()) return;
    const { data } = await window.sqbt.postAction("auto_lobby_get", {});
    if (gen !== autoLobbyPrefillGen) return;
    if (isUserEditingTools()) return;
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
    if (editing || isUserEditingTools()) return;
    // Refresh visible inputs if the tab is open — never clobber an active edit.
    for (const wrap of document.querySelectorAll(`[data-section-id="${sectionId}"] [data-field-key]`)) {
      const key = wrap.getAttribute("data-field-key");
      if (!key || fieldValues[key] === undefined) continue;
      if (autoLobbyTouchedKeys.has(key)) continue;
      if (wrap.dataset.role === "kick-exempt") {
        paintKickExemptField(wrap, key);
        continue;
      }
      const input = wrap.querySelector("input, select, textarea");
      if (!input || document.activeElement === input) continue;
      if (input.type === "checkbox") input.checked = Boolean(fieldValues[key]);
      else input.value = String(fieldValues[key]);
    }
    syncSectionFieldVisibility(sectionId);
    refreshAllKickExemptFields();
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

function showPartyStatsPanel(data) {
  const players = Array.isArray(data?.players) ? data.players : [];
  let panel = document.getElementById("party-stats-panel");
  if (!panel) {
    panel = document.createElement("div");
    panel.id = "party-stats-panel";
    panel.className = "result-panel party-stats-panel";
  }
  // Live Pack: list under Whose pack / Refresh player stats (not a toast line).
  const liveSection =
    tabContent?.querySelector('[data-tab-id="party_bay"]') ||
    tabContent?.querySelector('[data-section-id*="party"]') ||
    tabContent;
  const actionCard = liveSection?.querySelector('button[data-run-action="party_player_info"]')?.closest(
    ".action-card"
  );
  const whoseField =
    actionCard?.querySelector('[data-field-key$=":player_index"]') ||
    liveSection?.querySelector('[data-field-key$=":player_index"]');
  const anchor = whoseField || actionCard || liveSection?.querySelector(".action-grid") || liveSection;
  if (anchor) {
    const parent = anchor.parentElement || liveSection;
    if (panel.parentElement !== parent || panel.previousElementSibling !== anchor) {
      if (anchor.nextSibling) parent.insertBefore(panel, anchor.nextSibling);
      else parent.appendChild(panel);
    }
  } else if (!panel.parentElement && tabContent) {
    tabContent.appendChild(panel);
  }
  panel.replaceChildren();
  if (!players.length) {
    const empty = document.createElement("p");
    empty.className = "muted small";
    empty.textContent = String(data?.message || "No player stats.");
    panel.appendChild(empty);
    return;
  }
  for (const row of players) {
    const card = document.createElement("div");
    card.className = "party-stats-card";
    const title = document.createElement("h4");
    title.textContent = String(row?.name || `Player ${row?.index ?? "?"}`);
    if (row?.is_host) title.textContent += " (host)";
    card.appendChild(title);
    if (!row?.ok) {
      const err = document.createElement("p");
      err.className = "muted small";
      err.textContent = String(row?.error || "Failed to read.");
      card.appendChild(err);
      panel.appendChild(card);
      continue;
    }
    const dl = document.createElement("dl");
    dl.className = "party-stats-dl";
    const pairs = [];
    if (row.level != null) pairs.push(["Character level", row.level]);
    if (row.experience_points != null) pairs.push(["Character XP", Number(row.experience_points).toLocaleString()]);
    if (row.spec_level != null) pairs.push(["Specialization level", row.spec_level]);
    if (row.spec_experience_points != null) {
      pairs.push(["Specialization XP", Number(row.spec_experience_points).toLocaleString()]);
    }
    if (row.vault_hunter_level != null) pairs.push(["Vault Hunter points", row.vault_hunter_level]);
    const curs = Array.isArray(row.currencies) ? row.currencies : [];
    if (curs.length) {
      for (const cur of curs) {
        pairs.push([String(cur.name || "Currency"), Number(cur.amount || 0).toLocaleString()]);
      }
    } else {
      if (row.cash != null) pairs.push(["Cash", Number(row.cash).toLocaleString()]);
      if (row.eridium != null) pairs.push(["Eridium", Number(row.eridium).toLocaleString()]);
    }
    for (const [label, value] of pairs) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = String(value);
      dl.append(dt, dd);
    }
    card.appendChild(dl);
    panel.appendChild(card);
  }
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
  // Whole contiguous @U with no whitespace = one serial. Base85 may contain
  // = : , ( [ etc. — those must never count as a second @Ug start.
  if (!/\s/.test(t)) return true;
  const re = /(?:^|\s)@Ug/gi;
  let count = 0;
  let m;
  while ((m = re.exec(t)) !== null) {
    count += 1;
  }
  if (count === 0 && t.startsWith("@U")) return true;
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
  // Only whitespace / start — never punctuation (Base85 includes =:,([]{).
  // YAML serial: '…' is handled by extractYamlSerialFields.
  const re = /(?:^|\s)@Ug/gi;
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
    // Matching outer quotes only — never strip Base85 alphabet from the tail.
    if (
      (part.startsWith('"') && part.endsWith('"')) ||
      (part.startsWith("'") && part.endsWith("'"))
    ) {
      part = part.slice(1, -1).trim();
    }
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
    // Never rstrip Base85 alphabet — quotes already peeled above when matched.
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
      // Browse always fills the paste box — never the optional queue or Builds.
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
  libraryBtn.textContent = "Save to Builds";
  libraryBtn.title = "Save the paste box into a named item build.";
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
      const name = await promptPackPickDialog({
        kicker: "Builds",
        title: serials.length === 1 ? "Save item to which build?" : "Save items to which build?",
        detail:
          serials.length === 1
            ? "Pick an existing build or create a new named build."
            : `${serials.length} items will share the build you pick.`,
        packs: allKnownSerialStorePackNames(),
        suggested: "",
        okLabel: "Save to build",
      });
      if (name == null) {
        actionMessage.className = "action-message muted";
        actionMessage.textContent = "Build save cancelled.";
        return;
      }
      const cleanName = String(name).trim();
      if (!cleanName) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = "Enter a build name.";
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
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error || "Could not save the build.");
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
    if (field.includeBlank) {
      placeholder.textContent = String(field.blankLabel || "Select…");
    } else {
      placeholder.textContent = rows.length ? "Select…" : hint || "No entries";
    }
    selectEl.appendChild(placeholder);
    const valueKey = field.valueKey || "id";
    const labelKey = field.labelKey || valueKey;
    for (const row of rows) {
      const opt = document.createElement("option");
      opt.value = String(row[valueKey] || "");
      if (!opt.value && !field.includeBlank) continue;
      const label = String(row[labelKey] || opt.value);
      const extra = row.category || row.rarity || row.world || row.group || "";
      const favMark = isListFavorite(bucket, opt.value) ? "★ " : "";
      opt.textContent = favMark + (extra ? `${label} · ${extra}` : label);
      selectEl.appendChild(opt);
    }
    const key = fieldStorageKey(sectionId, actionDef, field);
    catalogRowCache.set(key, rows);
    const current = fieldValues[key] ?? field.default ?? "";
    if (current !== undefined && current !== null && String(current) !== "") {
      selectEl.value = String(current);
      if (selectEl.value !== String(current) && field.includeBlank) {
        // Kept value missing from list — still show it so Save does not wipe.
        const orphan = document.createElement("option");
        orphan.value = String(current);
        orphan.textContent = String(current);
        selectEl.appendChild(orphan);
        selectEl.value = String(current);
      }
      applyCatalogSelection(sectionId, actionDef, field, selectEl, key);
    } else if (field.includeBlank) {
      selectEl.value = "";
      fieldValues[key] = "";
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

function resolveVisibleWhenValue(sectionId, depKey) {
  const key = String(depKey || "").trim();
  if (!sectionId || !key) return undefined;
  const candidates = [
    `${sectionId}:__section__:${key}`,
    `${sectionId}:${key}`,
  ];
  for (const storageKey of candidates) {
    if (Object.prototype.hasOwnProperty.call(fieldValues, storageKey)) {
      return fieldValues[storageKey];
    }
  }
  // Action-scoped fields (rare): any key for this section ending with :depKey.
  const suffix = `:${key}`;
  const prefix = `${sectionId}:`;
  for (const [storageKey, value] of Object.entries(fieldValues)) {
    if (storageKey.startsWith(prefix) && storageKey.endsWith(suffix)) return value;
  }
  return undefined;
}

function fieldVisibleWhenRuleMet(rule, cur) {
  if (!rule || typeof rule !== "object") return true;
  if (Array.isArray(rule.any_of)) {
    return rule.any_of.some((sub) => fieldVisibleWhenRuleMet(sub, cur));
  }
  if (Array.isArray(rule.all_of)) {
    return rule.all_of.every((sub) => fieldVisibleWhenRuleMet(sub, cur));
  }
  const curStr = String(cur ?? "");
  if (Array.isArray(rule.in)) {
    return rule.in.map((v) => String(v)).includes(curStr);
  }
  if (rule.equals === undefined) return true;
  return curStr === String(rule.equals);
}

function fieldVisibleWhenMet(sectionId, field) {
  const rule = field?.visible_when;
  if (!rule || typeof rule !== "object") return true;
  // Compound rules may nest different dependency keys — evaluate each leaf against its key.
  if (Array.isArray(rule.any_of) || Array.isArray(rule.all_of)) {
    const evalNode = (node) => {
      if (!node || typeof node !== "object") return true;
      if (Array.isArray(node.any_of)) return node.any_of.some(evalNode);
      if (Array.isArray(node.all_of)) return node.all_of.every(evalNode);
      const depKey = String(node.key || rule.key || "").trim();
      const cur = depKey ? resolveVisibleWhenValue(sectionId, depKey) : undefined;
      return fieldVisibleWhenRuleMet(node, cur);
    };
    return evalNode(rule);
  }
  const depKey = String(rule.key || "").trim();
  if (!depKey) return true;
  const cur = resolveVisibleWhenValue(sectionId, depKey);
  return fieldVisibleWhenRuleMet(rule, cur);
}

function syncSectionFieldVisibility(sectionId) {
  if (!tabContent || !sectionId) return;
  const root =
    tabContent.querySelector(`[data-section-id="${CSS.escape(sectionId)}"]`) || tabContent;
  for (const wrap of root.querySelectorAll("[data-field-key][data-visible-when]")) {
    let rule = null;
    try {
      rule = JSON.parse(wrap.dataset.visibleWhen || "null");
    } catch {
      rule = null;
    }
    if (!rule) continue;
    const show = fieldVisibleWhenMet(sectionId, { visible_when: rule });
    wrap.classList.toggle("is-hidden", !show);
    wrap.style.display = show ? "" : "none";
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
  if (field.visible_when && typeof field.visible_when === "object") {
    wrap.dataset.visibleWhen = JSON.stringify(field.visible_when);
    if (!fieldVisibleWhenMet(sectionId, field)) {
      wrap.classList.add("is-hidden");
      wrap.style.display = "none";
    }
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
      markUserEditing();
      syncSectionFieldVisibility(sectionId);
    });
    wrap.appendChild(input);
    wrap.dataset.fieldKey = key;
    if (field.note) {
      const box = document.createElement("div");
      box.className = "field-note-wrap";
      const note = document.createElement("small");
      note.className = "field-note";
      note.textContent = field.note;
      box.append(wrap, note);
      return box;
    }
    return wrap;
  }

  if (field.type === "kick_exempt") {
    wrap.classList.add("field-wide", "field-kick-exempt");
    wrap.dataset.role = "kick-exempt";
    wrap.dataset.fieldKey = key;
    if (!Array.isArray(fieldValues[key])) {
      fieldValues[key] = Array.isArray(field.default) ? [...field.default] : [];
    }
    const row = document.createElement("div");
    row.className = "kick-exempt-row";
    const select = document.createElement("select");
    select.dataset.role = "kick-exempt-add";
    select.title = "Lobby guest to add";
    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "btn btn-secondary kick-exempt-add-btn";
    addBtn.textContent = "Add";
    row.append(select, addBtn);
    const chips = document.createElement("div");
    chips.className = "kick-exempt-chips";
    chips.dataset.role = "kick-exempt-chips";
    wrap.append(row, chips);
    const paint = () => paintKickExemptField(wrap, key);
    addBtn.addEventListener("click", () => {
      const idx = Number(select.value);
      if (!Number.isFinite(idx) || idx < 0) return;
      const players = latestStatus?.raw?.players || [];
      const rowPlayer = players.find((p) => Number(p.index) === idx);
      if (!rowPlayer || rowPlayer.is_host) return;
      const name = String(rowPlayer.shift_name || rowPlayer.name || "").trim();
      if (!name) return;
      const list = Array.isArray(fieldValues[key]) ? [...fieldValues[key]] : [];
      const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
      if (list.some((n) => norm(n) === norm(name))) {
        paint();
        return;
      }
      list.push(name);
      fieldValues[key] = list;
      markAutoLobbyFieldTouched(key);
      markUserEditing();
      paint();
      persistKickExemptNames(sectionId, key);
    });
    paint();
    refreshKickExemptAddSelect(select);
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
      markAutoLobbyFieldTouched(key);
      markUserEditing();
      syncSectionFieldVisibility(sectionId);
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
      markUserEditing();
      syncSectionFieldVisibility(sectionId);
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
    const drivesCatalog =
      Boolean(field.catalogParam) ||
      (allFields || []).some(
        (sibling) =>
          sibling.type === "catalog_select" &&
          ((sibling.catalogParamsFrom || []).includes(field.key) || sibling.catalogParam === field.key)
      );
    if (!drivesCatalog) return;
    catalogCache.clear();
    for (const sibling of allFields || []) {
      if (sibling.type !== "catalog_select") continue;
      const usesField =
        (sibling.catalogParamsFrom || []).includes(field.key) || sibling.catalogParam === field.key;
      if (!usesField) continue;
      const siblingWrap = sectionEl.querySelector(
        `[data-field-key="${actionFieldKey(sectionId, actionDef, sibling)}"]`
      );
      const siblingSelect = siblingWrap?.querySelector("select[data-role='catalog-select']");
      if (siblingSelect) populateCatalogSelect(siblingSelect, sibling, sectionId, actionDef, siblingWrap);
    }
  };
  let catalogRefreshTimer = 0;
  const scheduleCatalogRefresh = () => {
    window.clearTimeout(catalogRefreshTimer);
    catalogRefreshTimer = window.setTimeout(refreshCatalogSiblings, 280);
  };
  input.addEventListener("input", () => {
    fieldValues[key] = input.value;
    markAutoLobbyFieldTouched(key);
    markUserEditing();
    scheduleCatalogRefresh();
  });
  input.addEventListener("focus", () => markUserEditing(4000));
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
    markUserEditing();
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
    // Live catalog categories (e.g. Raid) — keep dropdown in sync with the mod.
    if (Array.isArray(data.categories) && data.categories.length) {
      const categorySelect = box.querySelector(".pool-browser-toolbar select");
      if (categorySelect) {
        const current = fieldValues[`${sectionId}:category`] || "All";
        categorySelect.innerHTML = "";
        for (const option of data.categories) {
          const opt = document.createElement("option");
          opt.value = option;
          opt.textContent = option;
          categorySelect.appendChild(opt);
        }
        categorySelect.value = data.categories.includes(current) ? current : "All";
        fieldValues[`${sectionId}:category`] = categorySelect.value;
      }
    }
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

function renderSerialStorePackList(
  sectionId,
  config,
  listEl,
  rows,
  selected,
  countEl,
  bucket,
  groups,
  groupCounts,
  groupMeta = null,
  previewHost = null
) {
  const readOnly = Boolean(config?.readOnly);
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
  for (const raw of groups || []) {
    const g = String(raw || "").trim();
    if (!g || g.toLowerCase() === "all") continue;
    if (!byGroup.has(g)) byGroup.set(g, []);
  }
  const counts =
    groupCounts && typeof groupCounts === "object" && !Array.isArray(groupCounts)
      ? groupCounts
      : null;
  const packNames = [...byGroup.keys()].sort((a, b) => a.localeCompare(b));
  // Auto-expand when filtering a single pack, or when only one pack exists.
  if (packNames.length === 1) expanded.add(packNames[0]);
  const filterGroup = String(fieldValues[`${sectionId}:group`] || "All");
  if (filterGroup && filterGroup !== "All") expanded.add(filterGroup);

  for (const packName of packNames) {
    const members = byGroup.get(packName) || [];
    // Prefer true pack sizes from the bridge so filtered List views don't paint sibling packs as (0).
    let packCount =
      counts && Object.prototype.hasOwnProperty.call(counts, packName)
        ? Number(counts[packName]) || 0
        : members.length;
    const details = document.createElement("details");
    details.className = "serial-store-pack";
    details.open = expanded.has(packName);
    details.addEventListener("toggle", () => {
      if (details.open) expanded.add(packName);
      else expanded.delete(packName);
    });
    const summary = document.createElement("summary");
    summary.className = "serial-store-pack-summary";
    // Clicks on action buttons already stopPropagation; ignore those here so a
    // mid-refresh rebuild cannot swallow the title click used to expand packs.
    summary.addEventListener("click", (event) => {
      if (event.target.closest(".serial-store-pack-actions")) {
        event.preventDefault();
      }
    });
    const title = document.createElement("span");
    title.className = "serial-store-pack-title";
    title.textContent = `${packName} (${packCount})`;
    const actions = document.createElement("span");
    actions.className = "serial-store-pack-actions";
    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.textContent = "Rename";
    renameBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const next = await promptTextDialog({
        kicker: "Builds",
        title: "Rename build",
        detail: `Current build: ${packName}`,
        label: "New build name",
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
      for (const row of members) {
        const rowId = multiselectRowId(row, config);
        next.add(rowId);
        const serial = rowSerialValue(row, config);
        if (serial) rememberMultiselectSerial(sectionId, rowId, serial);
        const consoleHeld = serialConsoleSafety.enabled && row.safety_tier === "heavy";
        if (!row.broken && !consoleHeld && isDeliverableSerial(serial)) {
          serials.push(serial);
        }
      }
      multiselectState.set(sectionId, next);
      // One row → one mail item (no silent dedupe; that was 150→148).
      return sanitizeDeliverableSerials(serials);
    };
    const sendPackBtn = document.createElement("button");
    sendPackBtn.type = "button";
    sendPackBtn.textContent = readOnly ? "Give loadout" : "Send pack";
    sendPackBtn.title =
      "Give every exact @U in this loadout (uses Override level above when set to yes)";
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
        applyDeliveryRecipient({
          serials,
          mode: "player",
          _selected_count: serials.length,
          ...levelFields,
        }, sectionId),
        `Mail all ${serials.length} serial(s) from pack “${packName}”${levelNote}?${serialConsoleSendNote(members)}`,
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
        applyDeliveryRecipient({
          serials,
          mode: "player",
          _selected_count: serials.length,
          ...levelFields,
        }, sectionId),
        `Mail all ${serials.length} serial(s) from pack “${packName}” releveled to ${levelFields.level}?${serialConsoleSendNote(members)}`,
        { sectionId, config, deliverStore: true }
      );
    });
    const saveCopyBtn = document.createElement("button");
    saveCopyBtn.type = "button";
    saveCopyBtn.textContent = "Save to My builds";
    saveCopyBtn.title = "Copy this exact loadout into an editable personal build";
    saveCopyBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const serialRows = members.filter((row) => isDeliverableSerial(row.serial));
      if (!serialRows.length) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = `Loadout “${packName}” has no deliverable @U serials.`;
        return;
      }
      await runAction(
        "serial_store_add_selected",
        {
          group: packName,
          rows: serialRows,
          serials: serialRows.map((row) => row.serial),
          titles: serialRows.map((row) => row.title || row.name || "Item"),
          _selected_count: serialRows.length,
          allow_duplicate_serials: true,
        },
        "",
        { sectionId, config }
      );
    });
    const addPackBtn = document.createElement("button");
    addPackBtn.type = "button";
    addPackBtn.textContent = "Add";
    addPackBtn.title = "Select this pack in Add to list, then paste codes and Save entry";
    addPackBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      focusSerialStoreAddToPack(sectionId, packName);
    });
    const exportBtn = document.createElement("button");
    exportBtn.type = "button";
    exportBtn.textContent = "Share .txt";
    exportBtn.title = "Download this list as a shareable .txt (works right away — no restart)";
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
    if (readOnly) {
      actions.append(selectPackBtn, sendPackBtn, sendPackLvlBtn, saveCopyBtn);
    } else {
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
    }
    summary.append(title, actions);
    details.appendChild(summary);

    const body = document.createElement("div");
    body.className = "serial-store-pack-body";
    const meta = groupMeta && typeof groupMeta === "object" ? groupMeta[packName] : null;
    if (meta && typeof meta === "object") {
      const intro = document.createElement("div");
      intro.className = "curated-build-meta";
      const lead = [meta.character, meta.playstyle].filter(Boolean).join(" · ");
      const notes = String(meta.notes || "").trim();
      const heading = document.createElement("strong");
      heading.textContent = lead || packName;
      intro.appendChild(heading);
      if (notes) {
        const note = document.createElement("span");
        note.textContent = notes;
        intro.appendChild(note);
      }
      const skills = String(meta.skills || "").trim();
      if (skills) {
        const skillLine = document.createElement("span");
        skillLine.className = "curated-build-skills";
        skillLine.textContent = `Skills: ${skills}`;
        intro.appendChild(skillLine);
      }
      const sources = Array.isArray(meta.sources) ? meta.sources : [];
      if (sources.length) {
        const refs = document.createElement("span");
        refs.className = "curated-build-sources";
        refs.append("References: ");
        sources.forEach((source, index) => {
          const url = String(source?.url || "").trim();
          if (!url.startsWith("https://")) return;
          if (index > 0) refs.append(" · ");
          const link = document.createElement("a");
          link.href = url;
          link.textContent = String(source?.label || "Build guide");
          link.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            window.sqbt.openExternal(url);
          });
          refs.appendChild(link);
        });
        if (refs.querySelector("a")) intro.appendChild(refs);
      }
      body.appendChild(intro);
    }
    const packListEl = document.createElement("div");
    packListEl.className = "serial-store-pack-list";
    body.appendChild(packListEl);
    for (const row of members) {
      const rowId = multiselectRowId(row, config);
      const wrap = document.createElement("div");
      wrap.className = "list-row-with-fav serial-store-line";
      if (bucket) {
        wrap.appendChild(
          makeFavoriteButton(bucket, rowId, () => refreshMultiselectSection(sectionId, config))
        );
      }
      const label = document.createElement("label");
      label.className = "multiselect-row serial-store-line-row";
      if (isListFavorite(bucket, rowId)) label.classList.add("is-favorite");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = selected.has(rowId);
      const userLabel = serialStoreListName(row);
      const cardTitle = String(
        row.full_name || row.display_name || row.title || userLabel || rowId
      ).trim();
      const chipTitle = userLabel || cardTitle;
      const serial = String(row.serial || rowSerialValue(row, config) || "").trim();
      cb.addEventListener("change", () => {
        if (cb.checked) selected.add(rowId);
        else selected.delete(rowId);
        if (cb.checked && serial) rememberMultiselectSerial(sectionId, rowId, serial);
        if (cb.checked && previewHost && catalogShowItemCards()) {
          paintCatalogNativePreview(
            previewHost,
            catalogCardPropsFromRow(row, String(row.display_name || "").trim() || cardTitle, sectionId)
          );
        }
        if (countEl) countEl.textContent = formatMultiselectSelectedLabel(sectionId, config);
      });
      label.appendChild(cb);

      const loadIntoForm = (event) => {
        if (event) event.preventDefault();
        serialStoreEdit.set(sectionId, {
          id: row.id,
          name: row.name || row.title,
          group: row.group || "Default",
          serial: row.serial || serial || "",
        });
        renderSerialStoreForm(sectionId);
        actionMessage.className = "action-message muted";
        actionMessage.textContent = `Editing “${chipTitle}” — Save to update.`;
      };

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "serial-store-entry-link catalog-card-edit";
      editBtn.textContent = "Edit";
      editBtn.title = "Click to edit in the form above";
      editBtn.addEventListener("click", loadIntoForm);

      wrap.dataset.serialRowId = String(row.id || "");
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "serial-store-row-remove";
      removeBtn.textContent = "×";
      removeBtn.title = "Remove this code from the list";
      removeBtn.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        const entryId = String(row.id || "").trim();
        if (!entryId) return;
        const shownName = String(chipTitle || "this item").replace(/^@U.*/i, "this item");
        if (!window.confirm(`Remove “${shownName}” from “${packName}”?`)) return;
        removeBtn.disabled = true;
        try {
          const { data } = await window.sqbt.postAction("serial_store_delete", { ids: [entryId] });
          if (data?.ok === false || !Number(data?.deleted || 0)) {
            removeBtn.disabled = false;
            actionMessage.className = "action-message error";
            actionMessage.textContent = data?.message || "Could not remove that code.";
            return;
          }
          selected.delete(rowId);
          const cachedRows = multiselectRows.get(sectionId);
          if (Array.isArray(cachedRows)) {
            multiselectRows.set(
              sectionId,
              cachedRows.filter((r) => String(r?.id || "") !== entryId)
            );
          }
          const memberIdx = members.indexOf(row);
          if (memberIdx >= 0) members.splice(memberIdx, 1);
          packCount = Math.max(0, packCount - 1);
          title.textContent = `${packName} (${packCount})`;
          wrap.remove();
          bustSerialStoreCatalog();
          if (countEl) countEl.textContent = formatMultiselectSelectedLabel(sectionId, config);
          actionMessage.className = "action-message ok";
          actionMessage.textContent = `Removed “${shownName}” from “${packName}”.`;
        } catch (error) {
          removeBtn.disabled = false;
          actionMessage.className = "action-message error";
          actionMessage.textContent = String(error?.message || error);
        }
      });

      if (catalogShowItemCards() && previewHost) {
        appendCatalogItemCardRow({
          listEl: packListEl,
          wrap,
          label,
          row,
          title: cardTitle,
          extraBits: row.roll ? [`God roll: ${row.roll}`] : [],
          config,
          previewHost,
          sectionId,
          chipLabel: chipTitle,
        });
        if (!readOnly) {
          wrap.appendChild(editBtn);
          wrap.appendChild(removeBtn);
        }
      } else {
        const nameBtn = document.createElement("button");
        nameBtn.type = "button";
        nameBtn.className = "serial-store-entry-link serial-store-line-name";
        nameBtn.textContent = chipTitle || "Item";
        const lineBadge = serialSafetyBadgeEl(row);
        if (lineBadge) nameBtn.appendChild(lineBadge);
        nameBtn.title = readOnly ? "Exact catalog-backed item" : "Click to edit in the form above";
        if (!readOnly) nameBtn.addEventListener("click", loadIntoForm);
        label.appendChild(nameBtn);
        if (row.roll) {
          const roll = document.createElement("span");
          roll.className = "serial-store-line-roll muted small";
          roll.textContent = `God roll: ${row.roll}`;
          label.appendChild(roll);
        }
        const serialBox = document.createElement("code");
        serialBox.className = "serial-store-line-serial";
        serialBox.textContent = serial || "(no @U)";
        serialBox.title = serial || "";
        label.appendChild(serialBox);
        if (!readOnly) label.appendChild(editBtn);
        wrap.appendChild(label);
        if (!readOnly) wrap.appendChild(removeBtn);
        packListEl.appendChild(wrap);
      }
    }
    details.appendChild(body);
    listEl.appendChild(details);
  }
}

/** Console mode settings mirrored from the mod (Item lists catalog / console_safety_*). */
let serialConsoleSafety = { enabled: false, max_length: 2500, max_repeat: 300, total_warn: 60000 };

const SERIAL_SAFETY_LABELS = {
  clean: ["Clean", "Legit-shaped code — fine everywhere."],
  modded: ["Modded", "Modded code within Console mode limits — still sends with Console mode on."],
  heavy: ["Heavy", ""],
  broken: ["Broken", "The game can't read this code — it is never sent."],
};

function serialSafetyBadgeEl(row) {
  const tier = String(row?.safety_tier || "").trim();
  const spec = SERIAL_SAFETY_LABELS[tier];
  if (!spec) return null;
  const badge = document.createElement("span");
  badge.className = `serial-safety-badge serial-safety-${tier}`;
  badge.textContent = spec[0];
  const len = Number(row.code_len || String(row.serial || "").length || 0);
  const rep = Number(row.max_repeat || 0);
  const sizeNote = len ? ` (${len} chars${rep > 1 ? `, worst part ×${rep}` : ""})` : "";
  badge.title =
    tier === "heavy"
      ? `Extra-heavy${sizeNote} — over Console mode limits (${serialConsoleSafety.max_length} chars / part ×${serialConsoleSafety.max_repeat}). Held back only while Console mode is on.`
      : `${spec[1]}${sizeNote}`;
  return badge;
}

/** Console-mode note for a send confirm (held-back count + big-total warning). */
function serialConsoleSendNote(rows) {
  if (!serialConsoleSafety.enabled) return "";
  let held = 0;
  let total = 0;
  for (const row of rows || []) {
    if (!row || row.broken) continue;
    if (row.safety_tier === "heavy") {
      held += 1;
      continue;
    }
    total += Number(row.code_len || String(row.serial || "").length || 0);
  }
  const bits = [];
  if (held) bits.push(`Console mode holds back ${held} extra-heavy code(s).`);
  if (total > Number(serialConsoleSafety.total_warn || 60000)) {
    bits.push(
      `This send is ${total.toLocaleString()} characters of item codes — very large modded sends are the usual cause of blank console inventories.`
    );
  }
  return bits.length ? `\n\n${bits.join("\n")}` : "";
}

function renderSerialConsoleBar(boxEl, sectionId, config) {
  if (!boxEl) return;
  let bar = boxEl.querySelector(".serial-console-bar");
  if (!bar) {
    bar = document.createElement("div");
    bar.className = "serial-console-bar";
    const anchor = boxEl.querySelector(".catalog-preview-split") || boxEl.querySelector(".multiselect-list");
    if (anchor) anchor.before(bar);
    else boxEl.appendChild(bar);
  }
  bar.replaceChildren();
  const toggle = document.createElement("label");
  toggle.className = "serial-console-toggle";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = Boolean(serialConsoleSafety.enabled);
  toggle.append(cb, document.createTextNode(" Console mode"));
  const note = document.createElement("span");
  note.className = "serial-console-note muted";
  note.textContent = serialConsoleSafety.enabled
    ? `On — modded codes still send; only extra-heavy ones (over ${serialConsoleSafety.max_length} chars or one part ×${serialConsoleSafety.max_repeat}) are held back.`
    : "Off — every readable code sends. Turn on when a console player is in the lobby.";
  const limits = document.createElement("details");
  limits.className = "serial-console-limits";
  const sum = document.createElement("summary");
  sum.textContent = "Limits";
  limits.appendChild(sum);
  const mkNum = (labelText, key, min, max) => {
    const wrap = document.createElement("label");
    wrap.textContent = `${labelText} `;
    const input = document.createElement("input");
    input.type = "number";
    input.min = String(min);
    input.max = String(max);
    input.value = String(serialConsoleSafety[key] ?? "");
    input.dataset.key = key;
    wrap.appendChild(input);
    return wrap;
  };
  const lenField = mkNum("Max code length", "max_length", 200, 20000);
  const repField = mkNum("Max repeats of one part", "max_repeat", 2, 5000);
  const totalField = mkNum("Warn above total chars", "total_warn", 5000, 2000000);
  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.textContent = "Save limits";
  limits.append(lenField, repField, totalField, saveBtn);
  bar.append(toggle, note, limits);

  const push = async (payload) => {
    try {
      const { data } = await window.sqbt.postAction("console_safety_set", payload);
      if (data?.settings) serialConsoleSafety = { ...serialConsoleSafety, ...data.settings };
      actionMessage.className = data?.ok === false ? "action-message error" : "action-message ok";
      actionMessage.textContent = data?.message || "Saved.";
    } catch (error) {
      actionMessage.className = "action-message error";
      actionMessage.textContent = String(error?.message || error);
    }
    refreshAllSerialStoreSections();
  };
  cb.addEventListener("change", () => push({ enabled: cb.checked }));
  saveBtn.addEventListener("click", () => {
    const payload = {};
    for (const input of limits.querySelectorAll("input[data-key]")) {
      if (input.value !== "") payload[input.dataset.key] = Number(input.value);
    }
    push(payload);
  });
}

/** Item lists: end the scroll box at the window bottom (measured, not a guessed offset). */
function fitSerialStoreListHeight(listEl) {
  if (!listEl || !listEl.isConnected) return;
  window.requestAnimationFrame(() => {
    if (!listEl.isConnected || listEl.offsetParent === null) return;
    const top = listEl.getBoundingClientRect().top;
    const room = Math.floor(window.innerHeight - top - 16);
    // Scrolled past the top: fill most of the window instead of collapsing.
    const height = room >= 320 ? room : Math.max(320, window.innerHeight - 120);
    listEl.style.maxHeight = `${height}px`;
    listEl.style.minHeight = `${Math.min(height, 320)}px`;
  });
}

let serialStoreFitTimer = 0;
window.addEventListener("resize", () => {
  window.clearTimeout(serialStoreFitTimer);
  serialStoreFitTimer = window.setTimeout(() => {
    for (const el of document.querySelectorAll(".multiselect-list.serial-store-list")) {
      fitSerialStoreListHeight(el);
    }
  }, 120);
});

/** @type {Map<string, number>} */
const serialStoreNamePatchTimers = new Map();

/** List name: computed full in-game name unless the row has a real custom nickname. */
function serialStoreListName(row) {
  const userLabel = String(row?.user_label || row?.name || "").trim();
  const full = String(row?.full_name || "").trim();
  if (!full) return userLabel;
  if (!userLabel) return full;
  const tag = (userLabel.match(/^\[(?:legit|modded)\]/i) || [""])[0];
  const bare = userLabel.slice(tag.length).trim().toLowerCase();
  const decoded = String(row?.display_name || "").trim().toLowerCase();
  if (!bare || bare === decoded || full.toLowerCase().includes(bare)) {
    return tag ? `${tag} ${full}` : full;
  }
  return userLabel;
}

function patchSerialStoreRowLabel(wrap, row) {
  const userLabel = serialStoreListName(row);
  const text = userLabel || String(row.display_name || row.title || "").trim();
  if (!text || /^@U/i.test(text)) return;
  const nameEl = wrap.querySelector(".sqbt-catalog-pick-name, .serial-store-line-name");
  if (nameEl) {
    nameEl.textContent = text;
    const badge = serialSafetyBadgeEl(row);
    if (badge) nameEl.appendChild(badge);
  }
  const chip = wrap.querySelector(".sqbt-catalog-pick");
  if (!chip) return;
  chip.classList.toggle("is-broken-code", Boolean(row.broken));
  if (row.rarity) {
    for (const cls of [...chip.classList]) {
      if (cls.startsWith("rarity-")) chip.classList.remove(cls);
    }
    chip.classList.add(rarityCardClass(row.rarity));
    chip.style.setProperty("--sqbt-rarity", rarityAccentColor(row.rarity));
  }
  const metaText = row.broken
    ? "Can't be sent — remove it from the list"
    : [row.manufacturer, row.item_type || row.type, row.rarity]
        .map((x) => String(x || "").trim())
        .filter(Boolean)
        .join(" · ");
  if (!metaText) return;
  let meta = chip.querySelector(".sqbt-catalog-pick-meta");
  if (!meta) {
    meta = document.createElement("div");
    meta.className = "sqbt-catalog-pick-meta";
    nameEl?.after(meta);
  }
  meta.textContent = metaText;
}

/** Big packs get names over a few bridge passes; patch rows in place (no rebuild / scroll jump). */
function scheduleSerialStoreNamePatch(sectionId, config, attempt = 0) {
  if (attempt > 60) return;
  window.clearTimeout(serialStoreNamePatchTimers.get(sectionId));
  serialStoreNamePatchTimers.set(
    sectionId,
    window.setTimeout(async () => {
      serialStoreNamePatchTimers.delete(sectionId);
      const box = tabContent.querySelector(`[data-multiselect-section="${sectionId}"]`);
      if (!box || box.closest(".hidden") || !actionsEnabled()) return;
      const params = multiselectParams(sectionId, config);
      let data;
      try {
        const result = await window.sqbt.getCatalog("serial_store", params);
        if (!result?.ok) return;
        data = result.data;
      } catch {
        return;
      }
      catalogCache.set(catalogCacheKey("serial_store", params), data);
      const rows = Array.isArray(data?.rows) ? data.rows : [];
      const byId = new Map(rows.map((r) => [String(r?.id || ""), r]));
      const cached = multiselectRows.get(sectionId);
      if (Array.isArray(cached)) {
        for (const r of cached) {
          const hit = byId.get(String(r?.id || ""));
          if (hit) Object.assign(r, hit);
        }
      }
      for (const wrap of box.querySelectorAll("[data-serial-row-id]")) {
        const row = byId.get(wrap.dataset.serialRowId || "");
        if (row) patchSerialStoreRowLabel(wrap, row);
      }
      if (Number(data?.names_pending || 0) > 0) {
        scheduleSerialStoreNamePatch(sectionId, config, attempt + 1);
      }
    }, 1200)
  );
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

  if (!actionsEnabled() && config.catalog !== "native_appearances") {
    listEl.innerHTML = `<p class="muted">Connect in-game first.</p>`;
    if (statusEl) statusEl.textContent = "";
    return;
  }

  listEl.innerHTML = `<p class="muted">Loading…</p>`;
  try {
  const params = multiselectParams(sectionId, config);
  let data;
  if (config.catalog === "native_appearances" && !actionsEnabled()) {
    const terms = String(params.search || "").toLowerCase().split(/\s+/).filter(Boolean);
    const group = String(params.group || "All");
    const rows = (config.staticRows || []).filter(row =>
      (group === "All" || row.group === group) && terms.every(term =>
        `${row.display_name} ${row.code} ${row.group}`.toLowerCase().includes(term)));
    data = {rows, total: rows.length, message: "Native BL4 catalog. Connect in-game to preview or apply a character."};
  } else if (config.catalog === "backpack" && (config.params?.pack_bay || config.source === "save_yaml")) {
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
    // Name + level via the same decode Party Bay uses (bridge / in-game mod).
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
                parts: hit.parts || row.parts,
                perk_rows: hit.perk_rows || row.perk_rows,
                perk_lines: hit.perk_lines || row.perk_lines,
                stats: hit.stats || row.stats,
                element: hit.element || row.element,
                damage_type: hit.damage_type || row.damage_type,
                part_names: hit.part_names || row.part_names,
                red_text: hit.red_text || row.red_text,
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
    if (config.catalog === "serial_store" && Array.isArray(data.groups)) {
      rememberSerialStorePackNames(sectionId, data.groups);
    }
    if (!multiselectState.has(sectionId)) {
      multiselectState.set(sectionId, new Set());
    }
    const selected = multiselectState.get(sectionId);
    listEl.innerHTML = "";
    const groupedBuilds = config.catalog === "serial_store" || Boolean(config.groupedBuilds);
    const storeGroups = groupedBuilds && Array.isArray(data.groups) ? data.groups : [];
    const namedPacks = storeGroups.filter((name) => {
      const g = String(name || "").trim();
      return g && g.toLowerCase() !== "all";
    });
    if (!rows.length && !namedPacks.length) {
      listEl.innerHTML = catalogEmptyHtml(config.catalog, config);
      if (data.message && statusEl) statusEl.textContent = data.message;
    } else if (groupedBuilds) {
      const boxEl = listEl.closest(".multiselect-box");
      let previewHost =
        (boxEl && boxEl.querySelector(`[data-catalog-preview="${sectionId}"]`)) || null;
      if (catalogShowItemCards()) {
        if (!previewHost) {
          const split = document.createElement("div");
          split.className = "catalog-preview-split";
          listEl.replaceWith(split);
          split.appendChild(listEl);
          previewHost = document.createElement("div");
          previewHost.className = "sqbt-catalog-native-preview";
          previewHost.dataset.catalogPreview = sectionId;
          previewHost.setAttribute("aria-label", "Item card preview");
          split.appendChild(previewHost);
        }
        previewHost.hidden = !rows.length;
        delete previewHost.dataset.seeded;
        delete previewHost.dataset.previewKey;
        previewHost.replaceChildren();
        const splitOn = previewHost.closest(".catalog-preview-split");
        if (splitOn) splitOn.classList.remove("cards-off");
      } else if (previewHost) {
        previewHost.hidden = true;
        previewHost.replaceChildren();
        const splitOff = previewHost.closest(".catalog-preview-split");
        if (splitOff) splitOff.classList.add("cards-off");
      }
      renderSerialStorePackList(
        sectionId,
        config,
        listEl,
        rows,
        selected,
        countEl,
        bucket,
        storeGroups,
        data.group_counts || null,
        data.group_meta || null,
        catalogShowItemCards() ? previewHost : null
      );
      if (data.console_safety && typeof data.console_safety === "object") {
        serialConsoleSafety = { ...serialConsoleSafety, ...data.console_safety };
      }
      if (config.catalog === "serial_store") {
        renderSerialConsoleBar(listEl.closest(".multiselect-box"), sectionId, config);
      }
      fitSerialStoreListHeight(listEl);
      if (Number(data.names_pending || 0) > 0) {
        scheduleSerialStoreNamePatch(sectionId, config);
      }
    } else {
      const box = listEl.closest(".multiselect-box");
      let previewHost =
        (box && box.querySelector(`[data-catalog-preview="${sectionId}"]`)) || null;
      if (
        catalogShowItemCards() &&
        (config.catalog === "gzo" || config.catalog === "lootlemon")
      ) {
        if (!previewHost) {
          // Older layout fallback — keep preview out of the scrolling list.
          const split = document.createElement("div");
          split.className = "catalog-preview-split";
          listEl.replaceWith(split);
          split.appendChild(listEl);
          previewHost = document.createElement("div");
          previewHost.className = "sqbt-catalog-native-preview";
          previewHost.dataset.catalogPreview = sectionId;
          previewHost.setAttribute("aria-label", "Item card preview");
          split.appendChild(previewHost);
        }
        previewHost.hidden = !rows.length;
        delete previewHost.dataset.seeded;
        delete previewHost.dataset.previewKey;
        previewHost.replaceChildren();
        const splitOn = previewHost.closest(".catalog-preview-split");
        if (splitOn) splitOn.classList.remove("cards-off");
      } else if (previewHost) {
        previewHost.hidden = true;
        previewHost.replaceChildren();
        const splitOff = previewHost.closest(".catalog-preview-split");
        if (splitOff) splitOff.classList.add("cards-off");
      }
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
        const unavailable = config.selectableKey && row[config.selectableKey] !== true;
        if (unavailable) selected.delete(rowId);
        cb.disabled = Boolean(unavailable);
        cb.checked = selected.has(rowId);
        if (unavailable) {
          label.classList.add("muted");
          label.title = row.status_label || "This character is not playable in BL4 yet.";
        }
        cb.addEventListener("change", () => {
          if (cb.checked && config.singleSelect) {
            selected.clear();
            for (const other of listEl.querySelectorAll("input[type='checkbox']")) {
              if (other !== cb) other.checked = false;
            }
          }
          if (cb.checked) selected.add(rowId);
          else selected.delete(rowId);
          if (cb.checked) {
            const serial = rowSerialValue(row, config);
            if (serial) rememberMultiselectSerial(sectionId, rowId, serial);
            if (previewHost) {
              paintCatalogNativePreview(
                previewHost,
                catalogCardPropsFromRow(
                  row,
                  String(row[config.labelKey || "title"] || row.name || rowId),
                  sectionId
                )
              );
            }
          }
          if (countEl) countEl.textContent = formatMultiselectSelectedLabel(sectionId, config);
        });
        const title = String(row[config.labelKey || "title"] || row.name || rowId);
        const extraBits = [row.type, row.manufacturer, row.creator, row.group || row.listing || row.category];
        if (config.kind === "backpack" || config.catalog === "backpack") {
          if (row.level != null && row.level !== "") extraBits.unshift(`L${row.level}`);
          const serial = String(row.serial || "");
          if (serial.startsWith("@U")) {
            // Display snip only — full serial stays in row.serial / cache for deliver.
            extraBits.push(serial.length > 40 ? `${serial.slice(0, 36)}…` : serial);
          } else {
            extraBits.push("no @U — cannot relevel");
          }
        }
        label.append(cb);
        appendCatalogItemCardRow({
          listEl,
          wrap,
          label,
          row,
          title,
          extraBits,
          config,
          previewHost,
          sectionId,
        });
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
      character: data.characters,
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
    if (
      config.catalog !== "serial_store" &&
      config.catalog !== "gzo" &&
      config.catalog !== "lootlemon" &&
      config.catalog !== "curated_builds"
    ) {
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
  newOpt.textContent = "＋ New build…";
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

function revealSerialStorePack(sectionId, packName) {
  const cleaned = String(packName || "").trim();
  if (!sectionId || !cleaned) return;
  if (!serialStoreExpanded.has(sectionId)) serialStoreExpanded.set(sectionId, new Set());
  serialStoreExpanded.get(sectionId).add(cleaned);
  fieldValues[`${sectionId}:group`] = cleaned;
  const sectionEl = serialStoreSectionEl(sectionId);
  const pack = [...(sectionEl?.querySelectorAll(".serial-store-pack") || [])].find((node) => {
    const title = node.querySelector(".serial-store-pack-title")?.textContent || "";
    return title.startsWith(`${cleaned} (`) || title === cleaned;
  });
  if (pack) {
    pack.open = true;
    try {
      pack.scrollIntoView({ block: "nearest", behavior: "smooth" });
    } catch {
      /* ignore */
    }
  }
  const filterSelect = sectionEl?.querySelector(`[data-field-key="${sectionId}:group"] select`);
  if (filterSelect) {
    const has = [...filterSelect.options].some((opt) => opt.value === cleaned);
    if (!has) {
      const opt = document.createElement("option");
      opt.value = cleaned;
      opt.textContent = cleaned;
      filterSelect.appendChild(opt);
    }
    filterSelect.value = cleaned;
  }
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
      // List-only refresh. Do not move the caret — a saved selectionStart
      // is already behind if another letter landed during the load.
      refreshMultiselectSection(sectionId, config);
    }, 220);
  });
  toolbar.appendChild(search);

  if (config.catalog === "gzo" || config.catalog === "lootlemon" || config.catalog === "serial_store") {
    const cardToggle = document.createElement("label");
    cardToggle.className = "multiselect-card-toggle";
    const cardCheck = document.createElement("input");
    cardCheck.type = "checkbox";
    cardCheck.checked = catalogShowItemCards();
    cardCheck.addEventListener("change", () => {
      setCatalogShowItemCards(cardCheck.checked);
      refreshMultiselectSection(sectionId, config);
    });
    cardToggle.appendChild(cardCheck);
    cardToggle.appendChild(
      document.createTextNode(
        config.catalog === "lootlemon"
          ? " Item cards (Lootlemon)"
          : config.catalog === "gzo"
            ? " Item cards (GZO)"
            : " Item cards"
      )
    );
    cardToggle.title = "Show in-game Cohtml inventory cards (same as Editor)";
    toolbar.appendChild(cardToggle);
  }

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
  // Always show every filter (Category / Type / Manufacturer) — no "More filters" fold.
  if (advancedFilters.length) {
    for (const filter of advancedFilters) appendFilterControl(filter, toolbar);
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

    const countKey = `${sectionId}:count`;
    if (fieldValues[countKey] === undefined || fieldValues[countKey] === "") {
      fieldValues[countKey] = "1";
    }
    const countWrap = document.createElement("label");
    countWrap.className = "multiselect-filter";
    countWrap.innerHTML = "<span>Copies each</span>";
    const countInput = document.createElement("input");
    countInput.type = "number";
    countInput.min = "1";
    countInput.max = "99";
    countInput.step = "1";
    countInput.value = String(fieldValues[countKey] || "1");
    countInput.title = "How many copies of each ticked serial to mail";
    countInput.addEventListener("change", () => {
      const n = Number(countInput.value);
      const clamped = Number.isFinite(n) && n >= 1 ? Math.min(99, Math.round(n)) : 1;
      countInput.value = String(clamped);
      fieldValues[countKey] = String(clamped);
    });
    countWrap.appendChild(countInput);
    toolbar.appendChild(countWrap);

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
    if (fieldValues[levelOverrideKey] === undefined) fieldValues[levelOverrideKey] = "yes";
    if (fieldValues[levelKey] === undefined) fieldValues[levelKey] = "70";
    const levelWrap = document.createElement("label");
    levelWrap.className = "multiselect-filter";
    const levelToggle = document.createElement("select");
    for (const option of ["yes", "no"]) {
      const opt = document.createElement("option");
      opt.value = option;
      opt.textContent = option === "yes" ? "Override level" : "Use serial level";
      levelToggle.appendChild(opt);
    }
    levelToggle.value = fieldValues[levelOverrideKey];
    levelToggle.addEventListener("change", () => {
      fieldValues[levelOverrideKey] = levelToggle.value;
      refreshCatalogCardsForSectionLevel(sectionId);
    });
    const levelInput = document.createElement("input");
    levelInput.type = "number";
    levelInput.min = "1";
    levelInput.max = "70";
    levelInput.value = fieldValues[levelKey];
    levelInput.addEventListener("input", () => {
      fieldValues[levelKey] = levelInput.value;
      refreshCatalogCardsForSectionLevel(sectionId);
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
  selectAllBtn.hidden = Boolean(config.singleSelect);
  selectAllBtn.title =
    "Add every row matching the current filters to the selection (keeps ticks from other categories). Use Clear to wipe.";
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
      // Item lists: Pack=All must not select every pack — only expanded packs
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
      // Union into existing ticks — clearing wiped other categories when
      // building a mixed GZO/Lootlemon pack (Weapons then Shields, etc.).
      const before = selected.size;
      cacheMultiselectRows(sectionId, rows, config);
      let added = 0;
      for (const row of rows) {
        const rowId = multiselectRowId(row, config);
        if (!selected.has(rowId)) added += 1;
        selected.add(rowId);
      }
      multiselectState.set(sectionId, selected);
      if (countEl) countEl.textContent = formatMultiselectSelectedLabel(sectionId, config);
      const total = Number(data.total || rows.length || 0);
      if (statusEl) {
        const kept = Math.max(0, before);
        const note =
          added || kept
            ? `Added ${added} filtered (${selected.size} total${kept ? `, kept ${kept} prior` : ""})`
            : `Selected ${selected.size} filtered row(s)`;
        statusEl.textContent =
          total > rows.length
            ? `${note} — loaded ${rows.length} of ${total}`
            : note;
      }
    } catch (error) {
      const rows = multiselectRows.get(sectionId) || [];
      // Visible-only fallback: still union, never wipe other categories.
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
  if (config.catalog === "serial_store") listEl.classList.add("serial-store-list");
  if (config.catalog === "gzo" || config.catalog === "lootlemon" || config.catalog === "serial_store") {
    const split = document.createElement("div");
    split.className = "catalog-preview-split";
    const previewHost = document.createElement("div");
    previewHost.className = "sqbt-catalog-native-preview";
    previewHost.dataset.catalogPreview = sectionId;
    previewHost.setAttribute("aria-label", "Item card preview");
    previewHost.hidden = true;
    split.append(listEl, previewHost);
    box.appendChild(split);
  } else {
    box.appendChild(listEl);
  }
  sectionEl.appendChild(box);

  if (!multiselectState.has(sectionId)) {
    multiselectState.set(sectionId, new Set());
  }
  const onDesk = tabContent?.dataset?.activeTab === "lobby";
  const localFast =
    Boolean(config?.localOnly) || String(config?.catalog || "") === "serial_send_list";
  if (onDesk && !localFast) {
    box.dataset.lazyCatalog = "1";
    const statusEl = box.querySelector(".multiselect-status");
    if (statusEl) {
      statusEl.textContent = "Scroll here or Jump to load this list…";
    }
    const listEl = box.querySelector(".multiselect-list");
    if (listEl && !listEl.childElementCount) {
      listEl.innerHTML = `<p class="muted">Waiting to load…</p>`;
    }
  } else {
    refreshMultiselectSection(sectionId, config);
  }
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
  nameWrap.innerHTML =
    "<span>Your label <span class='muted'>(optional — card shows the real item name)</span></span>";
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.dataset.storeName = "1";
  nameInput.placeholder = "Nickname for this list only";
  nameInput.addEventListener("input", () => {
    const edit = serialStoreEdit.get(sectionId) || {};
    edit.name = nameInput.value;
    serialStoreEdit.set(sectionId, edit);
  });
  nameWrap.appendChild(nameInput);

  const groupWrap = document.createElement("label");
  groupWrap.className = "field serial-store-pack-dest";
  groupWrap.innerHTML = "<span>Build name</span>";
  const packSelect = document.createElement("select");
  packSelect.dataset.storePackSelect = "1";
  packSelect.title = "Pick an existing build, or create a new build.";
  const groupInput = document.createElement("input");
  groupInput.type = "text";
  groupInput.dataset.storeGroup = "1";
  groupInput.placeholder = "Type a new list name…";
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
    const prev = serialStoreEdit.get(sectionId) || {};
    const keepGroup = String(prev.group || "Default").trim() || "Default";
    serialStoreEdit.set(sectionId, {
      id: "",
      name: "",
      group: keepGroup.toLowerCase() === "all" ? "Default" : keepGroup,
      serial: "",
    });
    renderSerialStoreForm(sectionId);
    actionMessage.className = "action-message muted";
    actionMessage.textContent = `New — paste codes into list “${keepGroup}”, then Save.`;
  });
  const convertBtn = document.createElement("button");
  convertBtn.type = "button";
  convertBtn.className = "secondary";
  convertBtn.textContent = "Convert";
  convertBtn.title = "Toggle human ↔ @U in this box";
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
      const fromAtU = raw.trimStart().startsWith("@U") || Boolean(data?.human && data?.serial);
      let next = "";
      if (results.length > 1) {
        // Multi-line: keep @U codes (ready to Save).
        next = results.map((row) => row.serial || row.human || "").filter(Boolean).join("\n");
      } else if (raw.trimStart().startsWith("@U") && data?.human) {
        // @U → human (readable). Click Convert again for @U.
        next = String(data.human);
      } else if (data?.serial) {
        next = String(data.serial);
      } else if (data?.human) {
        next = String(data.human);
      } else {
        next = String(data?.message || raw);
      }
      serialInput.value = next;
      const edit = serialStoreEdit.get(sectionId) || {};
      edit.serial = next;
      serialStoreEdit.set(sectionId, edit);
      actionMessage.className = "action-message ok";
      actionMessage.textContent = fromAtU && raw.trimStart().startsWith("@U")
        ? "Converted to human form — Convert again for @U, or save to Builds."
        : data?.message || "Converted.";
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

  // Primary actions (Save / Send / Import / Export) land here — under the codes
  // box, above the saved lists — so they stay visible without scrolling past packs.
  const primarySlot = document.createElement("div");
  primarySlot.className = "serial-store-primary-actions";
  primarySlot.dataset.serialStorePrimary = sectionId;
  sectionEl.appendChild(primarySlot);

  const shareBar = document.createElement("div");
  shareBar.className = "serial-store-share-bar";
  shareBar.innerHTML =
    "<span class='muted small'><b>Easy steps:</b> 1) Pick or create a build → 2) Paste @U codes → 3) <b>Save build</b> (buttons above). " +
    "Your build opens below right away. Use <b>Export .txt</b> to share (no restart needed).</span>";
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
        label: "Show list",
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
      if (button.dataset.toggleBusy === "1") return;
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
        beginStickyToggleChange(actionDef.syncKey, nextOn);
      }
      if (actionDef.sticky) writeStickyToggle(toggleStickyKey(sectionId, actionDef), nextOn);
      button.dataset.toggleBusy = "1";
      const busyMs = actionDef.action === "shift_friend_autoaccept" ? 1800 : 500;
      Promise.resolve(runAction(actionDef.action, payload, actionDef.confirm || "", context))
        .then((result) => reconcileFailedToggle(button, actionDef, sectionId, currentlyOn, result))
        .catch(() => reconcileFailedToggle(button, actionDef, sectionId, currentlyOn, null))
        .finally(() => {
          finishStickyToggleChange(actionDef.syncKey);
          window.setTimeout(() => {
            button.dataset.toggleBusy = "0";
          }, busyMs);
        });
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
    ControlLeft: "LeftControl",
    ControlRight: "RightControl",
    ShiftLeft: "LeftShift",
    ShiftRight: "RightShift",
    AltLeft: "LeftAlt",
    AltRight: "RightAlt",
    NumpadAdd: "Add",
    NumpadSubtract: "Subtract",
    NumpadMultiply: "Multiply",
    NumpadDivide: "Divide",
    NumpadDecimal: "Decimal",
    NumpadEnter: "Enter",
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

async function saveKeybindSlot(host, slot, actionId, key) {
  actionMessage.className = "action-message muted";
  actionMessage.textContent = "Saving keybind…";
  try {
    const { data: result } = await window.sqbt.postAction(
      "keybinds_set",
      {
        slot: Number(slot),
        action_id: actionId || "",
        key: key || "",
      },
      12
    );
    actionMessage.className = result?.ok === false ? "action-message error" : "action-message ok";
    actionMessage.textContent = result?.message || "Saved.";
    if (result?.ok !== false) await refreshKeybindsEditor(host);
  } catch (error) {
    actionMessage.className = "action-message error";
    actionMessage.textContent = String(error?.message || error);
  }
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
      emptyOpt.textContent = "Choose action";
      actionSelect.appendChild(emptyOpt);
      for (const action of actions) {
        const opt = document.createElement("option");
        opt.value = action.id;
        opt.textContent = action.label;
        if (action.id === slot.action_id) opt.selected = true;
        actionSelect.appendChild(opt);
      }

      const keyBtn = document.createElement("button");
      keyBtn.type = "button";
      keyBtn.className = "keybind-key-btn";
      const paintKey = () => {
        const key = keyBtn.dataset.key || "";
        keyBtn.textContent = key || "Click, then press a key";
        keyBtn.classList.toggle("is-empty", !key);
      };
      keyBtn.dataset.key = slot.key || "";
      paintKey();
      keyBtn.addEventListener("keydown", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (event.key === "Escape") {
          keyBtn.blur();
          return;
        }
        if (event.key === "Backspace") {
          keyBtn.dataset.key = "";
          paintKey();
          saveKeybindSlot(host, slot.slot, actionSelect.value, "");
          return;
        }
        const unreal = keyEventToUnrealKey(event);
        if (!unreal) return;
        keyBtn.dataset.key = unreal;
        paintKey();
        saveKeybindSlot(host, slot.slot, actionSelect.value, unreal);
      });
      actionSelect.addEventListener("change", () => {
        saveKeybindSlot(host, slot.slot, actionSelect.value, keyBtn.dataset.key || "");
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

      if (slot.bound) row.classList.add("is-bound");
      const controls = document.createElement("div");
      controls.className = "keybind-controls";
      controls.append(actionSelect, keyBtn, clearBtn);
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
  ["no_death_penalty", "No death penalty"],
  ["map_fog", "Hide map fog"],
  ["hud_hidden", "Hide HUD"],
  ["fps_shown", "Show FPS"],
  ["low_power", "Low power host mode"],
  ["hold_session", "No main menu"],
  ["shift_friend_autoaccept", "SHiFT autoaccept"],
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
  no_death_penalty: {
    action: "character_flag",
    payloadOn: { flag: "no_death_penalty", enabled: true },
    payloadOff: { flag: "no_death_penalty", enabled: false },
  },
  map_fog: {
    action: "map_fog_hide",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  hud_hidden: {
    action: "hud_hide",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  fps_shown: {
    action: "fps_display",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  low_power: {
    action: "low_power",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  hold_session: {
    action: "hold_session",
    payloadOn: { enabled: true },
    payloadOff: { enabled: false },
  },
  shift_friend_autoaccept: {
    action: "shift_friend_autoaccept",
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
  const now = Date.now();
  for (const [key, label] of TOGGLE_BOARD_ROWS) {
    let on = Boolean(sticky[key]);
    if (stickyToggleGraceUntil[key] && now < stickyToggleGraceUntil[key]) {
      const btn = document.querySelector(`button[data-sync-key="${key}"]`);
      if (btn) on = btn.dataset.toggleOn === "1";
    }
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
  beginStickyToggleChange(key, wantOn);
  fillTogglesBoard();
  actionMessage.className = "action-message muted";
  actionMessage.textContent = `${wantOn ? "Enabling" : "Disabling"} ${label}…`;
  try {
    const payload = wantOn ? { ...spec.payloadOn } : { ...spec.payloadOff };
    const result = await runAction(spec.action, payload, "", {});
    if (!result || result.ok === false) {
      delete stickyToggleGraceUntil[key];
      patchStickyToggleLocal(key, !wantOn);
      syncMobilityToggleButtons(key, !wantOn);
      fillTogglesBoard();
      return;
    }
    patchStickyToggleLocal(key, wantOn);
    syncMobilityToggleButtons(key, wantOn);
    fillTogglesBoard();
  } catch (error) {
    delete stickyToggleGraceUntil[key];
    patchStickyToggleLocal(key, !wantOn);
    syncMobilityToggleButtons(key, !wantOn);
    fillTogglesBoard();
    actionMessage.className = "action-message error";
    actionMessage.textContent = String(error?.message || error);
  } finally {
    finishStickyToggleChange(key);
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

const SECTION_COLLAPSED_STORAGE = "sqbt.sectionCollapsed";

function readSectionCollapsed(sectionId) {
  try {
    const map = JSON.parse(localStorage.getItem(SECTION_COLLAPSED_STORAGE) || "{}");
    return Boolean(map && typeof map === "object" && map[sectionId]);
  } catch {
    return false;
  }
}

function writeSectionCollapsed(sectionId, collapsed) {
  try {
    const raw = localStorage.getItem(SECTION_COLLAPSED_STORAGE);
    const map = raw ? JSON.parse(raw) : {};
    if (!map || typeof map !== "object") return;
    if (collapsed) map[sectionId] = true;
    else delete map[sectionId];
    localStorage.setItem(SECTION_COLLAPSED_STORAGE, JSON.stringify(map));
  } catch {
    /* ignore quota / private mode */
  }
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
  const deskBand = String(
    section.lobby_band || section.desk_band || section.compact_band || ""
  )
    .trim()
    .toLowerCase();
  if (deskBand) {
    sectionEl.dataset.deskBand = deskBand;
    sectionEl.classList.add("panel-section-desk-band");
    sectionEl.id = `sqbt-desk-${deskBand}`;
    if (
      section.lobby_band_header ||
      section.desk_band_header ||
      section.compact_band_header
    ) {
      sectionEl.classList.add("panel-section-desk-divider");
    }
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
  if (section.collapsible) {
    heading.classList.add("section-collapse-trigger");
    heading.tabIndex = 0;
    heading.setAttribute("role", "button");
    const applyCollapsed = (collapsed) => {
      sectionEl.classList.toggle("is-collapsed", collapsed);
      heading.setAttribute("aria-expanded", collapsed ? "false" : "true");
      heading.title = collapsed ? "Click to expand" : "Click to collapse";
    };
    applyCollapsed(readSectionCollapsed(sectionId));
    const flip = () => {
      const next = !sectionEl.classList.contains("is-collapsed");
      applyCollapsed(next);
      writeSectionCollapsed(sectionId, next);
    };
    heading.addEventListener("click", flip);
    heading.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        flip();
      }
    });
  }
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

  if (section.liveLog) {
    const wrap = document.createElement("div");
    wrap.className = "live-log-wrap";
    const pathLine = document.createElement("p");
    pathLine.className = "muted small";
    pathLine.id = "sqbt-live-log-path";
    pathLine.textContent = "sqbt_runtime.log";
    const body = document.createElement("pre");
    body.className = "live-log-body";
    body.id = "sqbt-live-log-body";
    body.textContent = "Connect in-game, then this fills with shiny / mail / shape activity…";
    wrap.append(pathLine, body);
    sectionEl.appendChild(wrap);
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
        if (navMode === "compact" || navMode === "lobby") {
          navMode = "tabs";
          try {
            localStorage.setItem(NAV_MODE_KEY, "tabs");
          } catch {
            /* ignore */
          }
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
    shared.className = "section-shared-fields fields-grid";
    let activeGroup = null;
    let activeGroupGrid = null;
    for (const field of section.fields) {
      const groupName = String(field.field_group || "").trim();
      let target = shared;
      if (groupName) {
        if (!activeGroup || activeGroup.dataset.fieldGroup !== groupName) {
          activeGroup = document.createElement("div");
          activeGroup.className = "section-field-group";
          activeGroup.dataset.fieldGroup = groupName;
          const heading = document.createElement("h4");
          heading.className = "section-field-group-title";
          heading.textContent = groupName;
          activeGroupGrid = document.createElement("div");
          activeGroupGrid.className = "fields-grid section-field-group-grid";
          activeGroup.append(heading, activeGroupGrid);
          shared.appendChild(activeGroup);
        }
        target = activeGroupGrid;
      } else {
        activeGroup = null;
        activeGroupGrid = null;
      }
      const node = renderField(sectionId, { action: "__section__" }, field);
      if (node) {
        if (field.key === "max_all" && groupName === "Boost jobs") {
          node.classList.add("field-nudge-right");
        }
        target.appendChild(node);
      }
    }
    sectionEl.appendChild(shared);
    syncSectionFieldVisibility(sectionId);
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
  const subgroupHosts = new Map();
  const subgroupsWrap = featured && !fieldsSidebar ? document.createElement("div") : null;
  if (subgroupsWrap) subgroupsWrap.className = "action-subgroups";
  const subgroupHostFor = (actionDef) => {
    const label = String(actionDef.subgroup || "").trim();
    if (!label || !subgroupsWrap) return null;
    let inner = subgroupHosts.get(label);
    if (!inner) {
      const group = document.createElement("div");
      group.className = "action-subgroup";
      const heading = document.createElement("p");
      heading.className = "action-subgroup-label";
      heading.textContent = label;
      inner = document.createElement("div");
      inner.className = "action-grid action-grid-featured";
      group.append(heading, inner);
      subgroupsWrap.appendChild(group);
      subgroupHosts.set(label, inner);
    }
    return inner;
  };
  const hostFor = (actionDef) => {
    const fold = String(actionDef.fold || "").trim();
    if (!fold) return subgroupHostFor(actionDef) || actionsWrap;
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
    if ((section.multiselect || section.serialStore || section.serialSendList) &&
        String(actionDef.type || "").toLowerCase() !== "toggle") {
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
          const tip = document.createElement("p");
          tip.className = "muted small";
          tip.textContent =
            "Tick rows above, choose Send to. Open rewards defaults to Yes so mail appears; set No if you want it to stay pending.";
          card.appendChild(tip);
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
        }
        if (actionDef.backpackMultiselect && actionDef.action === "backpack_relevel_selected") {
          const tip = document.createElement("p");
          tip.className = "muted small";
          tip.textContent =
            "Tick rows above, set New item level + Send to, then mail releveled @U (does not rewrite live slots).";
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
          const bayName = configParamsPartyBay(sectionId)
            ? "Live Pack"
            : activeTabId === "pack_bay"
              ? "Save Pack"
              : activeTabId === "party_bay"
                ? "Live Pack"
                : "bay";
          tip.textContent = `Tick ${bayName} rows above, then add their @U codes into Item lists.`;
          card.appendChild(tip);
        }
        if (actionDef.packBayCopy && actionDef.action === "deliver_serials") {
          const tip = document.createElement("p");
          tip.className = "muted small";
          const mailSelf =
            Boolean(actionDef.payload?.mail_to_self) ||
            activeTabId === "pack_bay" ||
            configParamsPackBay(sectionId);
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
        if (actionDef.deliverMultiselect || actionDef.deliverStore) {
          const tip = document.createElement("p");
          tip.className = "muted small";
          tip.textContent = actionDef.deliverStore
            ? "Tick list rows below, choose Send to. Open rewards defaults to Yes so mail appears; set No if you want it to stay pending."
            : "Tick rows above, choose Send to. Open rewards defaults to Yes so mail appears; set No if you want it to stay pending.";
          card.appendChild(tip);
        }
        // Party Bay: keep Send releveled beside Send selected (same row).
        if (
          isPartyBayContext(sectionId) &&
          actionDef.packBayCopy &&
          actionDef.action === "deliver_serials"
        ) {
          partyBaySendRow = document.createElement("div");
          partyBaySendRow.className = "bay-pair-row";
          partyBaySendRow.appendChild(card);
          actionHost.appendChild(partyBaySendRow);
        } else if (
          isPartyBayContext(sectionId) &&
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
        if (button.dataset.toggleBusy === "1") return;
        const currentlyOn = button.dataset.toggleOn === "1";
        const nextOn = !currentlyOn;
        const base = collectPayload(sectionId, actionDef);
        const flip = nextOn
          ? { ...(actionDef.payloadOn || { enabled: true }) }
          : { ...(actionDef.payloadOff || { enabled: false }) };
        paintToggleButton(button, actionDef, nextOn);
        if (actionDef.syncKey) {
          beginStickyToggleChange(actionDef.syncKey, nextOn);
        }
        if (actionDef.sticky) writeStickyToggle(toggleStickyKey(sectionId, actionDef), nextOn);
        button.dataset.toggleBusy = "1";
        Promise.resolve(
          runAction(actionDef.action, { ...base, ...flip }, actionDef.confirm || "", { sectionId })
        )
          .then((result) => reconcileFailedToggle(button, actionDef, sectionId, currentlyOn, result))
          .catch(() => reconcileFailedToggle(button, actionDef, sectionId, currentlyOn, null))
          .finally(() => {
            finishStickyToggleChange(actionDef.syncKey);
            window.setTimeout(() => {
              button.dataset.toggleBusy = "0";
            }, 500);
          });
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
    const storeSlot = section.serialStore
      ? sectionEl.querySelector(
          `.serial-store-primary-actions[data-serial-store-primary="${sectionId}"]`
        )
      : null;
    if (storeSlot) storeSlot.appendChild(actionsWrap);
    else sectionEl.appendChild(actionsWrap);
  }
  if (subgroupsWrap) {
    for (const inner of subgroupHosts.values()) {
      if (inner.childElementCount === 0) inner.parentElement?.remove();
    }
    if (subgroupsWrap.childElementCount > 0) sectionEl.appendChild(subgroupsWrap);
  }
  for (const rec of foldOrder) {
    sectionEl.appendChild(rec.details);
  }
  if (fieldActionsWrap && fieldActionsWrap.childElementCount > 0) {
    sectionEl.appendChild(fieldActionsWrap);
  }

  return sectionEl;
}

function editorShowItemCard() {
  try {
    const v = localStorage.getItem(EDITOR_CARD_KEY);
    if (v === null || v === "") return true;
    return v === "1";
  } catch {
    return true;
  }
}

function setEditorShowItemCard(on) {
  try {
    localStorage.setItem(EDITOR_CARD_KEY, on ? "1" : "0");
  } catch {
    /* ignore */
  }
  if (!on && editorPreviewTimer) {
    clearTimeout(editorPreviewTimer);
    editorPreviewTimer = 0;
  }
}

function rarityAccentColor(rarity) {
  const r = String(rarity || "").toLowerCase();
  if (r.includes("pearl") || r.includes("pearlescent")) return "#b4e6ff";
  if (r.includes("legend") || r.includes("unique") || r.includes("orange")) return "#ff9a2e";
  if (r.includes("epic") || r.includes("purple")) return "#b070ff";
  if (r.includes("rare") || r.includes("blue")) return "#4f96ff";
  if (r.includes("uncommon") || r.includes("green")) return "#50c878";
  if (r.includes("common") || r.includes("white")) return "#d7d7d7";
  return "#ff9a2e";
}

/** Game Cohtml item card (Editor + GZO/Lootlemon). CSS tiles only as last-resort fallback. */
function buildInventoryStyleCardEl({
  title,
  rarity = "",
  level = "",
  manufacturer = "",
  itemType = "",
  type_label = "",
  listing = "",
  parts = [],
  perk_rows = [],
  part_names = [],
  native_equipment = null,
  native_secondary = null,
  stats = [],
  element = "",
  serial = "",
  red_text = [],
  stats_source = "",
  stats_note = "",
  element_text = "",
  set = "",
  value = undefined,
  preferNative = false,
  nativeOnly = false,
  width = 546,
  lazy = false,
  ...cardExtra
}) {
  const props = {
    ...cardExtra,
    title,
    rarity,
    level,
    manufacturer,
    itemType,
    type_label,
    listing,
    parts,
    perk_rows,
    part_names,
    native_equipment,
    native_secondary,
    stats,
    element,
    serial,
    red_text,
    stats_source,
    stats_note,
    element_text,
    set,
    value,
  };
  if (preferNative) {
    try {
      const native =
        window.SQBTNativeItemCard &&
        window.SQBTNativeItemCard.buildNativeItemCardEl(props, {
          width: Math.max(280, Number(width) || 546),
          lazy: Boolean(lazy),
          force: true,
        });
      // Blank iframe hosts still look "successful" — keep CSS fallback unless nativeOnly.
      if (native && !native.dataset.nativeFailed) {
        if (nativeOnly) return native;
        const frame = native.querySelector(".sqbt-native-card-frame");
        if (frame) {
          const armFallback = () => {
            if (!native.isConnected || native.dataset.nativeFailed) return;
            const rendered = frame.dataset.rendered === "true";
            const h = parseFloat(frame.style.height) || frame.getBoundingClientRect().height || 0;
            if (rendered && h >= 80) return;
            native.dataset.nativeFailed = "1";
            const css = buildInventoryStyleCardEl({
              ...props,
              preferNative: false,
              nativeOnly: false,
              width,
              lazy: false,
            });
            if (css && native.parentElement) native.replaceWith(css);
          };
          frame.addEventListener("load", () => setTimeout(armFallback, 600), { once: true });
          setTimeout(armFallback, 1200);
        }
        return native;
      }
    } catch {
      /* fall through */
    }
    if (nativeOnly) {
      const stub = document.createElement("div");
      stub.className = "sqbt-native-card-fallback";
      const name = document.createElement("div");
      name.className = "sqbt-native-card-fallback-name";
      name.textContent = title || "Item";
      stub.appendChild(name);
      const meta = [manufacturer, itemType || type_label, rarity]
        .map((x) => String(x || "").trim())
        .filter(Boolean)
        .join(" · ");
      if (meta) {
        const m = document.createElement("div");
        m.className = "muted small";
        m.textContent = meta;
        stub.appendChild(m);
      }
      return stub;
    }
  }

  const card = document.createElement("div");
  const rClass = rarityCardClass(rarity);
  card.className = `sqbt-inv-card ${rClass}`;
  const accent = rarityAccentColor(rarity);
  card.style.setProperty("--sqbt-rarity", accent);

  const head = document.createElement("div");
  head.className = "sqbt-inv-card-head";
  const nameEl = document.createElement("div");
  nameEl.className = "sqbt-inv-card-name";
  nameEl.textContent = title || "Item";
  head.appendChild(nameEl);
  const lvl = String(level ?? "").trim();
  if (lvl !== "") {
    const levelEl = document.createElement("div");
    levelEl.className = "sqbt-inv-card-level";
    levelEl.textContent = /^l(vl|evel)?\s*/i.test(lvl) ? lvl : `Lvl ${lvl}`;
    head.appendChild(levelEl);
  }
  card.appendChild(head);

  const sub = document.createElement("div");
  sub.className = "sqbt-inv-card-sub";
  const typeBits = [manufacturer, itemType || type_label, rarity, listing]
    .map((x) => String(x || "").trim())
    .filter(Boolean);
  const typeEl = document.createElement("span");
  typeEl.className = "sqbt-inv-card-type";
  typeEl.textContent = typeBits.join(" · ") || "Gear";
  sub.appendChild(typeEl);
  const badge = document.createElement("span");
  badge.className = "sqbt-inv-card-badge";
  badge.textContent = (itemType || type_label || "ITEM").toString().slice(0, 12).toUpperCase();
  sub.appendChild(badge);
  card.appendChild(sub);

  if (Array.isArray(stats) && stats.length) {
    const grid = document.createElement("div");
    grid.className = "sqbt-inv-card-stats";
    for (const row of stats.slice(0, 6)) {
      const cell = document.createElement("div");
      cell.className = "sqbt-inv-card-stat";
      const lab = document.createElement("span");
      lab.className = "sqbt-inv-card-stat-label";
      lab.textContent = String(row?.label || "Stat");
      const val = document.createElement("span");
      val.className = "sqbt-inv-card-stat-value";
      val.textContent = String(row?.value || "").trim() || "—";
      cell.append(lab, val);
      grid.appendChild(cell);
    }
    card.appendChild(grid);
    const note = String(stats_note || "").trim();
    if (note || String(stats_source || "").startsWith("sqbt_")) {
      const src = document.createElement("div");
      src.className = "sqbt-inv-card-stats-note muted small";
      src.textContent = note || "Fallback estimate";
      card.appendChild(src);
    }
  }

  const elem = String(element || "").trim();
  if (elem) {
    const bar = document.createElement("div");
    bar.className = "sqbt-inv-card-element";
    bar.textContent = elem;
    card.appendChild(bar);
  }

  const redLines = Array.isArray(red_text) ? red_text.map((x) => String(x || "").trim()).filter(Boolean) : [];
  if (redLines.length) {
    const red = document.createElement("div");
    red.className = "sqbt-inv-card-redtext";
    red.textContent = redLines[0];
    card.appendChild(red);
  }

  if (Array.isArray(parts) && parts.length) {
    const list = document.createElement("ul");
    list.className = "sqbt-inv-card-parts";
    for (const part of parts.slice(0, 8)) {
      const line = String(part || "").trim();
      if (!line || /^(\{[\d:\s\[\],]+\}|\d+:\d+)/.test(line)) continue;
      const li = document.createElement("li");
      li.textContent = line;
      list.appendChild(li);
    }
    if (list.childElementCount) card.appendChild(list);
  }

  const ser = String(serial || "").trim();
  if (ser.startsWith("@U")) {
    const snip = document.createElement("div");
    snip.className = "sqbt-inv-card-serial";
    snip.textContent = ser.length > 48 ? `${ser.slice(0, 44)}…` : ser;
    snip.title = ser;
    card.appendChild(snip);
  }

  return card;
}

function renderEditorValidation() {
  const host = document.getElementById("sqbt-builder-validation");
  if (!host) return;
  host.replaceChildren();
  const analysis = editorLatest.analysis;
  const inspection = editorLatest.inspection;
  if (!analysis) {
    host.textContent = "Paste or build an item to decode and validate its exact serial.";
    host.className = "muted small";
    return;
  }
  const identity = String(analysis.identity?.payload_sha256 || "").slice(0, 16);
  const changed =
    Boolean(editorLatest.sourceSerial) &&
    String(editorLatest.sourceSerial) !== String(analysis.serial || "");
  const validRules = Boolean(inspection?.validation?.ok);
  const editable = Boolean(inspection?.editable);
  const line = document.createElement("p");
  line.className = inspection
    ? validRules
      ? "ok small"
      : editable
        ? "attention small"
        : "muted small"
    : "ok small";
  line.textContent =
    `${changed ? "Edited" : "Unchanged"} · exact payload ${identity || "decoded"} · ` +
    `${analysis.part_names?.length || 0} decoded parts · ` +
    (inspection
      ? validRules
        ? "legitimate-item rules pass"
        : editable
          ? "rule review required"
          : "root is not supported by the legitimate builder"
      : "serial decode verified");
  host.appendChild(line);
  const unknowns = Array.isArray(analysis.unknowns) ? analysis.unknowns : [];
  const conflicts = Array.isArray(analysis.conflicts) ? analysis.conflicts : [];
  const errors = Array.isArray(inspection?.errors) ? inspection.errors : [];
  if (unknowns.length || conflicts.length || errors.length) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `Review ${unknowns.length + conflicts.length + errors.length} uncertainty / rule item(s)`;
    const list = document.createElement("ul");
    for (const text of [
      ...unknowns.map((name) => `Unknown property: ${name}`),
      ...conflicts.map((row) => `Conflicting ${row.field} data`),
      ...errors,
    ].slice(0, 20)) {
      const li = document.createElement("li");
      li.textContent = String(text);
      list.appendChild(li);
    }
    details.append(summary, list);
    host.appendChild(details);
  }
}

async function editorValidateExactSerial(serial, { loadPreview = true } = {}) {
  const code = String(serial || "").trim();
  const analysis = await window.sqbt.analyzeItem(code, {});
  if (!analysis?.ok || !analysis?.exact) {
    editorLatest.analysis = null;
    editorLatest.inspection = null;
    renderEditorValidation();
    throw new Error(analysis?.error || "Serial decode validation failed.");
  }
  editorLatest.serial = analysis.serial;
  editorLatest.analysis = analysis;
  if (loadPreview) {
    editorLatest.preview = {
      ...(analysis.card_props || {}),
      serial: analysis.serial,
      title: analysis.display_name || analysis.card_props?.display_name || "Item",
    };
  }
  try {
    const { data } = await window.sqbt.postAction(
      "editor_analyze_serial",
      { serial: analysis.serial },
      12
    );
    editorLatest.inspection = data?.inspection || null;
  } catch {
    editorLatest.inspection = null;
  }
  editorLatest.ready = true;
  renderEditorValidation();
  refreshEditorDeliveryButtons();
  if (loadPreview && editorShowItemCard()) await paintEditorItemCard(editorLatest.preview);
  return analysis;
}

function scheduleEditorValidation() {
  if (editorValidationTimer) clearTimeout(editorValidationTimer);
  editorValidationTimer = window.setTimeout(() => {
    editorValidationTimer = 0;
    const serial = String(editorLatest.serial || "").trim();
    if (!serial.startsWith("@U")) {
      editorLatest.analysis = null;
      editorLatest.inspection = null;
      renderEditorValidation();
      return;
    }
    editorValidateExactSerial(serial, { loadPreview: false }).catch(() => {});
  }, 650);
}

function ensureEditorMessageListener() {
  if (editorMessageBound) return;
  editorMessageBound = true;
  window.addEventListener("message", (event) => {
    const data = event?.data;
    if (!data || data.source !== "sqbt-editor") return;
    if (data.type === "sqbt-editor-serial") {
      const incomingSerial = String(data.serial || "").trim();
      const preserveImported =
        Boolean(editorLatest.sourceSerial) &&
        Date.now() < Number(editorLatest.importingSourceUntil || 0) &&
        incomingSerial.startsWith("@U");
      if (!preserveImported) {
        editorLatest.serial = incomingSerial;
        if (
          editorLatest.sourceSerial &&
          incomingSerial &&
          incomingSerial !== editorLatest.sourceSerial
        ) {
          editorLatest.importingSourceUntil = 0;
        }
      }
      editorLatest.deser = String(data.deser || "").trim();
      editorLatest.ready = Boolean(data.ready) || Boolean(editorLatest.serial) || editorLatest.deser.includes("||");
      scheduleEditorValidation();
      refreshEditorDeliveryButtons();
      const pictureSerial = document.getElementById("sqbt-picture-final-serial");
      if (pictureSerial) pictureSerial.value = editorLatest.serial || "";
    } else if (data.type === "sqbt-editor-preview") {
      // Builder UI defaults to L60; after Picture "Final item level" relevel the
      // shell already verified @U at that level — never let preview wipe it.
      const incoming = data.preview && typeof data.preview === "object" ? { ...data.preview } : null;
      const forcedLevel = resolvePictureFinalLevel();
      if (incoming && forcedLevel) incoming.level = forcedLevel;
      editorLatest.preview = incoming;
      if (editorShowItemCard() || document.getElementById("sqbt-picture-card")) {
        scheduleEditorCardPaint();
      }
    } else if (data.type === "sqbt-editor-ready") {
      refreshEditorDeliveryButtons();
    } else if (data.type === "sqbt-editor-imported") {
      if (data.request_id) editorPictureLastImport = data;
      const status = document.getElementById("sqbt-editor-status");
      if (status) {
        status.textContent = String(data.message || (data.ok ? "Item loaded." : "Import failed."));
        status.className = data.ok ? "ok small" : "error small";
      }
    }
  });
}

/** Picture to Item Final level — wins over builder L60 default on card paint. */
function resolvePictureFinalLevel() {
  if (Number.isFinite(Number(editorPictureTargetLevel)) && Number(editorPictureTargetLevel) >= 1) {
    return Math.trunc(Number(editorPictureTargetLevel));
  }
  const el = document.getElementById("sqbt-picture-level");
  if (el) {
    const n = Number(el.value);
    if (Number.isFinite(n) && n >= 1) return Math.trunc(n);
  }
  return null;
}

function scheduleEditorCardPaint() {
  if (editorPreviewTimer) clearTimeout(editorPreviewTimer);
  editorPreviewTimer = setTimeout(() => {
    editorPreviewTimer = 0;
    paintEditorItemCard(
      editorLatest.preview,
      activeTabId === "picture_item" ? "sqbt-picture-card" : "sqbt-editor-card"
    );
  }, 280);
}

async function paintEditorItemCard(preview, hostId = "sqbt-editor-card") {
  const host = document.getElementById(hostId);
  if (!host) return;
  if (hostId === "sqbt-editor-card" && !editorShowItemCard()) {
    host.hidden = true;
    host.innerHTML = "";
    host.dataset.previewKey = "";
    return;
  }
  host.hidden = false;
  const p = preview && typeof preview === "object" ? preview : {};
  const title = String(p.title || "Item").trim() || "Item";
  const rarity = String(p.rarity || "").trim();
  const parts = Array.isArray(p.parts) ? p.parts.slice(0, 8) : [];
  const partNames = Array.isArray(p.part_names) ? p.part_names : [];
  const redText = Array.isArray(p.red_text) ? p.red_text.slice(0, 3) : [];
  const typeLabel = String(p.type_label || "").trim();
  const itemTypeRaw = String(p.itemType || "").trim();
  const weaponType = String(p.weaponType || "").trim();
  const itemType =
    typeLabel ||
    (/class/i.test(itemTypeRaw) ? itemTypeRaw : "") ||
    (partNames.some((x) => /classmod_/i.test(String(x || ""))) ? "Class Mod" : "") ||
    itemTypeRaw ||
    weaponType ||
    "";
  const forcedPictureLevel =
    hostId === "sqbt-picture-card" ? resolvePictureFinalLevel() : null;
  const cardLevel =
    forcedPictureLevel != null
      ? forcedPictureLevel
      : p.level != null && p.level !== ""
        ? p.level
        : "";
  const previewKey = [
    p.serial || editorLatest.serial || "",
    p.element || "",
    JSON.stringify(p.stats || []),
    title,
    rarity,
    itemType,
    cardLevel,
    partNames.join(","),
    (p.perk_rows || []).map((r) => r && (r.code || r.name)).filter(Boolean).join(","),
    redText.join("|"),
  ].join("::");
  if (host.dataset.previewKey === previewKey && host.querySelector(".sqbt-native-card-frame")) {
    return;
  }
  // Claim this key immediately so overlapping ticks don't stack paints.
  const paintId = String(++catalogCardPaintSeq);
  host.dataset.paintReq = paintId;
  host.dataset.previewKey = previewKey;

  if (!parts.length && !partNames.length && !(p.stats || []).length && !rarity && !p.manufacturer && !redText.length) {
    host.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "muted small";
    empty.textContent = "Pick parts to preview this item.";
    host.appendChild(empty);
    return;
  }
  const enriched = await attachPartScaleStats({
    title,
    display_name: title,
    rarity,
    level: cardLevel,
    serial_level: cardLevel,
    _fromEditor: true,
    _previewLevelLocked: true,
    manufacturer: p.manufacturer || "",
    itemType,
    type_label: typeLabel || itemType,
    parts,
    perk_rows: Array.isArray(p.perk_rows) ? p.perk_rows : [],
    stats: Array.isArray(p.stats) ? p.stats : [],
    element: p.element || "",
    serial: p.serial || editorLatest.serial || "",
    red_text: redText,
    part_names: partNames,
    name_parts: Array.isArray(p.name_parts) ? p.name_parts : [],
    set: p.set || "",
  });
  if (host.dataset.paintReq !== paintId) return;

  const existing = host.querySelector(".sqbt-native-card");
  if (existing && window.SQBTNativeItemCard?.fillNativeItemCard) {
    const entry = window.SQBTNativeItemCard.propsToEntry({
      ...enriched,
      title: enriched.title || title,
    });
    window.SQBTNativeItemCard.fillNativeItemCard(existing, entry, { width: 546, lazy: false });
    return;
  }

  const card = buildInventoryStyleCardEl({
    ...enriched,
    preferNative: true,
    nativeOnly: true,
    width: 546,
    lazy: false,
  });
  host.replaceChildren();
  if (card) host.appendChild(card);
}

function refreshEditorDeliveryButtons() {
  const ready = Boolean(editorLatest.ready);
  for (const id of ["sqbt-editor-mail", "sqbt-editor-copy", "sqbt-editor-library"]) {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = !ready || !actionsEnabled();
  }
  const status = document.getElementById("sqbt-editor-status");
  if (status && !status.dataset.sticky) {
    status.textContent = ready
      ? editorLatest.serial
        ? "Ready — @U packed"
        : "Ready — will pack on send"
      : "Build an item to enable Send code/item";
    status.className = "muted small";
  }
}

function ensureEditorPark() {
  if (editorParkEl && editorParkEl.isConnected) return editorParkEl;
  editorParkEl = document.createElement("div");
  editorParkEl.id = "sqbt-editor-park";
  editorParkEl.hidden = true;
  editorParkEl.setAttribute("aria-hidden", "true");
  document.body.appendChild(editorParkEl);
  return editorParkEl;
}

function ensureEditorFrameElement() {
  let frame =
    editorPersistedFrame && editorPersistedFrame.isConnected ? editorPersistedFrame : null;
  if (!frame) frame = document.getElementById("sqbt-editor-frame");
  if (!frame) {
    frame = document.createElement("iframe");
    frame.id = "sqbt-editor-frame";
    frame.className = "sqbt-editor-frame";
    frame.title = "Item Builder";
    frame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms");
    frame.src = "editor/index.html";
    editorFrameLoaded = true;
    ensureEditorPark().appendChild(frame);
  } else if (!frame.getAttribute("src")) {
    frame.src = "editor/index.html";
    editorFrameLoaded = true;
  }
  editorPersistedFrame = frame;
  return frame;
}

function parkEditorFrameIfNeeded() {
  const frame =
    editorPersistedFrame && editorPersistedFrame.isConnected
      ? editorPersistedFrame
      : document.getElementById("sqbt-editor-frame");
  if (!frame) return;
  const park = ensureEditorPark();
  if (frame.parentElement !== park) park.appendChild(frame);
  editorPersistedFrame = frame;
}

async function editorEnsureSerial() {
  let serial = String(editorLatest.serial || "").trim();
  if (serial.startsWith("@U")) {
    const analysis = await editorValidateExactSerial(serial, { loadPreview: true });
    return analysis.serial;
  }
  const deser = String(editorLatest.deser || "").trim();
  if (!deser) throw new Error("Build an item first.");
  if (deser.startsWith("@U")) return deser;
  const { data } = await window.sqbt.postAction("editor_pack_serial", { deser });
  if (data?.ok === false) throw new Error(data?.message || "Pack failed.");
  serial = String(data?.serial || data?.base85 || "").trim();
  if (!serial.startsWith("@U")) throw new Error("Pack did not return @U.");
  editorLatest.serial = serial;
  editorLatest.inspection = data?.inspection || null;
  const analysis = await editorValidateExactSerial(serial, { loadPreview: true });
  return analysis.serial;
}

async function serialWithExactLevel(serial, level) {
  const code = String(serial || "").trim();
  const levelNumber = Math.max(1, Math.min(100, Math.trunc(Number(level) || 70)));
  const { data } = await window.sqbt.postAction("serial_convert", {
    input: code,
    level_override: true,
    level: levelNumber,
  });
  const converted = String(data?.serial || "").trim();
  if (data?.ok === false || !converted.startsWith("@U")) {
    throw new Error(data?.message || `Could not serialize this item at level ${levelNumber}.`);
  }
  const analysis = await window.sqbt.analyzeItem(converted, {});
  if (!analysis?.ok || !analysis?.exact || Number(analysis?.card_props?.level) !== levelNumber) {
    throw new Error(`The final serial did not verify at level ${levelNumber}.`);
  }
  return { serial: analysis.serial, analysis, level: levelNumber };
}

function decodedSerialHasPartId(decodedHuman, partId) {
  const decoded = String(decodedHuman || "");
  const wanted = String(partId || "").trim();
  if (!decoded || !wanted) return false;
  if (decoded.includes(wanted)) return true;
  const match = wanted.match(/^(\d+):(\d+)$/);
  if (!match) return false;
  const setId = match[1];
  const partIndex = match[2];
  const decodedSet = decoded.match(/^\s*(\d+)\s*,/);
  if (!decodedSet || decodedSet[1] !== setId) return false;
  return new RegExp(`\\{\\s*${partIndex}\\s*\\}`).test(decoded);
}

async function finalizePictureSerialAtLevel(serial, level, { syncBuilder = false } = {}) {
  const leveled = await serialWithExactLevel(serial, level);
  editorPictureTargetLevel = leveled.level;
  editorLatest.serial = leveled.serial;
  editorLatest.analysis = leveled.analysis;
  editorLatest.preview = {
    ...(leveled.analysis.card_props || {}),
    serial: leveled.serial,
    title:
      editorLatest.preview?.title ||
      leveled.analysis.display_name ||
      "Pictured item",
  };
  editorPicturePreview = editorLatest.preview;
  editorLatest.sourceSerial = leveled.serial;
  editorLatest.importingSourceUntil = Date.now() + 3000;
  editorLatest.ready = true;
  const finalField = document.getElementById("sqbt-picture-final-serial");
  if (finalField) finalField.value = leveled.serial;
  renderEditorValidation();
  await paintEditorItemCard(editorLatest.preview, "sqbt-picture-card");
  if (syncBuilder) {
    const frame = ensureEditorFrameElement();
    frame?.contentWindow?.postMessage(
      {
        source: "sqbt-shell",
        type: "sqbt-load-serial",
        serial: leveled.serial,
        level: leveled.level,
      },
      "*"
    );
  }
  return leveled.serial;
}

async function editorUseAnalyzedSerial(serial, { pictureCandidate = false } = {}) {
  const finalizeGen = ++editorPictureFinalizeGen;
  if (pictureCandidate) editorPictureSelectedSource = String(serial || "").trim();
  const pictureRequestId = pictureCandidate
    ? `picture-${Date.now()}-${finalizeGen}`
    : "";
  if (pictureCandidate) editorPictureLastImport = null;
  let code = String(serial || "").trim();
  const imageExtracted = pictureCandidate && editorImageResult?.extracted
    ? editorImageResult.extracted
    : null;
  const picturedLevel = Number(imageExtracted?.level);
  editorPictureTargetLevel = pictureCandidate
    ? (Number.isFinite(picturedLevel) && picturedLevel >= 1 ? Math.trunc(picturedLevel) : 70)
    : null;
  if (pictureCandidate && Number.isFinite(picturedLevel) && picturedLevel >= 1) {
    code = (await serialWithExactLevel(code, picturedLevel)).serial;
  }
  const analysis = await editorValidateExactSerial(code, { loadPreview: true });
  editorPictureUncertain = Boolean(pictureCandidate);
  editorLatest.sourceSerial = analysis.serial;
  editorLatest.importingSourceUntil = pictureCandidate
    ? 0
    : Date.now() + (analysis.serial.length > 2200 ? 4000 : 1800);
  editorLatest.deser = analysis.decoded_human || "";
  editorLatest.ready = true;
  editorLatest.preview.picture_candidate_confirmed = Boolean(pictureCandidate);
  renderEditorValidation();
  const frame = ensureEditorFrameElement();
  frame?.contentWindow?.postMessage(
    {
      source: "sqbt-shell",
      type: "sqbt-load-serial",
      serial: analysis.serial,
      imageExtracted,
      requestId: pictureRequestId,
      level: editorPictureTargetLevel || undefined,
    },
    "*"
  );
  if (pictureCandidate && editorPictureTargetLevel) {
    const deadline = Date.now() + 8000;
    while (
      finalizeGen === editorPictureFinalizeGen &&
      Date.now() < deadline &&
      String(editorPictureLastImport?.request_id || "") !== pictureRequestId
    ) {
      await sleepMs(100);
    }
    if (finalizeGen !== editorPictureFinalizeGen) return analysis;
    if (String(editorPictureLastImport?.request_id || "") !== pictureRequestId) {
      throw new Error("Item Builder did not finish merging the pictured parts.");
    }
    if (editorPictureLastImport?.ok === false) {
      throw new Error(editorPictureLastImport?.message || "Item Builder could not merge the pictured parts.");
    }
    const current = String(editorLatest.serial || "").trim();
    if (!current.startsWith("@U")) {
      throw new Error("Item Builder did not produce the merged picture serial.");
    }
    const merged = await window.sqbt.analyzeItem(current, {});
    const decoded = String(merged?.decoded_human || "");
    const requiredPartIds = Array.isArray(editorPictureLastImport?.resolved_part_ids)
      ? editorPictureLastImport.resolved_part_ids.map((value) => String(value || "").trim()).filter(Boolean)
      : [];
    const missing = requiredPartIds.filter((partId) => !decodedSerialHasPartId(decoded, partId));
    if (missing.length) {
      throw new Error(`Final serial is missing pictured part${missing.length === 1 ? "" : "s"}: ${missing.join(", ")}.`);
    }
    await finalizePictureSerialAtLevel(current, editorPictureTargetLevel, {
      syncBuilder: true,
    });
  }
  refreshEditorDeliveryButtons();
  if (editorShowItemCard()) await paintEditorItemCard(editorLatest.preview);
  const status = document.getElementById("sqbt-editor-status");
  if (status) {
    status.textContent = pictureCandidate
      ? "Picture candidate confirmed — catalog identity and hidden rolls kept; pictured level and uniquely resolved visible parts merged."
      : "Exact serial validated and loaded.";
    status.className = pictureCandidate ? "attention small" : "ok small";
  }
  return analysis;
}

function editorImageCandidateKey(row) {
  return String(row?.serial || row?.id || `${row?.name || ""}:${row?.score || 0}`);
}

async function augmentEditorImageCandidates(result) {
  if (!result?.extracted || result?.exact_items?.length) return result;
  const searches = [
    ...(result.extracted.title_candidates || []),
    ...(result.extracted.perks || []),
  ]
    .map((value) =>
      String(value || "")
        .replace(/[^\w' -]+/g, " ")
        .replace(/\b(?:licensed|fires|critical hits?|projectiles?|secondary fire)\b/gi, " ")
        .replace(/\s+/g, " ")
        .trim()
        .split(/\s+/)
        .slice(0, 6)
        .join(" ")
    )
    .filter((value, index, all) => value.length >= 4 && all.indexOf(value) === index)
    .slice(0, 4);
  if (!searches.length || typeof window.sqbt?.getCatalog !== "function") return result;
  try {
    const replies = await Promise.all(
      searches.flatMap((search) =>
        ["gzo", "lootlemon", "serial_store"].map((name) =>
          window.sqbt.getCatalog(name, { search, limit: 250 }).catch(() => null)
        )
      )
    );
    const rows = replies.flatMap((reply) =>
      Array.isArray(reply?.data?.rows) ? reply.data.rows : []
    );
    if (!rows.length) return result;
    const ranked = await window.sqbt.rankItemImage(result.extracted, rows);
    const merged = [...(result.candidates || []), ...(ranked?.rows || [])];
    const seen = new Set();
    result.candidates = merged
      .sort((a, b) => Number(b?.score || 0) - Number(a?.score || 0))
      .filter((row) => {
        const key = editorImageCandidateKey(row);
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 16);
  } catch {
    /* Bundled known-item candidates remain available without a live bridge. */
  }
  return result;
}

async function previewTopPictureCandidate(result) {
  editorPicturePreview = null;
  if (!result?.ok || result?.exact) return;
  const top = Array.isArray(result.candidates) ? result.candidates[0] : null;
  const serial = String(top?.serial || "").trim();
  if (!serial.startsWith("@U")) return;
  // Selecting a result runs the same merge/validation path as clicking it.
  await editorUseAnalyzedSerial(serial, { pictureCandidate: true });
  editorPicturePreview = editorLatest.preview;
  renderEditorImageResult();
}

function renderEditorImageResult() {
  const host = document.getElementById("sqbt-image-results");
  if (!host) return;
  host.replaceChildren();
  const result = editorImageResult;
  if (!result) return;
  if (!result.ok) {
    const error = document.createElement("p");
    error.className = "error small";
    error.textContent = result.message || result.error || "Picture analysis failed.";
    host.appendChild(error);
    return;
  }
  const summary = document.createElement("p");
  summary.className = result.exact ? "ok small" : "attention small";
  summary.textContent = `${result.message || ""} OCR ${Math.round(Number(result.ocr?.confidence || 0))}%`;
  host.appendChild(summary);

  const attrs = result.extracted || {};
  const facts = [
    attrs.title_candidates?.[0] ? `Visible name: ${attrs.title_candidates[0]}` : "",
    attrs.manufacturer ? `Manufacturer: ${attrs.manufacturer}` : "",
    !attrs.manufacturer && attrs.manufacturers?.length
      ? `Visible brands/parts: ${attrs.manufacturers.join(", ")}`
      : "",
    attrs.item_type ? `Type: ${attrs.item_type}` : "",
    attrs.rarity ? `Rarity: ${attrs.rarity}` : "",
    Number.isFinite(Number(attrs.level)) ? `Level: ${attrs.level}` : "",
  ].filter(Boolean);
  if (facts.length) {
    const fact = document.createElement("p");
    fact.className = "muted small";
    fact.textContent = facts.join(" · ");
    host.appendChild(fact);
  }
  if (!result.exact && (attrs.item_type || attrs.title_candidates?.length || attrs.perks?.length)) {
    const loadObserved = document.createElement("button");
    loadObserved.type = "button";
    loadObserved.className = "primary";
    loadObserved.textContent = "Load observed parts into Build";
    loadObserved.title =
      "Starts a reconstruction from card evidence. Hidden parts and rolls remain for you to review.";
    loadObserved.addEventListener("click", () => {
      const confirmed = window.confirm(
        "This will start a reconstruction from visible card evidence. Hidden body, grip, sight, rolls, and any unreadable parts may differ. Continue?"
      );
      if (!confirmed) return;
      editorPictureUncertain = true;
      editorPictureTargetLevel =
        Number.isFinite(Number(attrs.level)) && Number(attrs.level) >= 1
          ? Math.trunc(Number(attrs.level))
          : 70;
      const frame = ensureEditorFrameElement();
      frame?.contentWindow?.postMessage(
        { source: "sqbt-shell", type: "sqbt-load-image-recipe", extracted: attrs },
        "*"
      );
      const editorStatus = document.getElementById("sqbt-editor-status");
      if (editorStatus) {
        editorStatus.textContent = "Loading observed card facts into Build…";
        editorStatus.className = "muted small";
      }
      if (activeTabId === "picture_item") {
        const pictureStatus = document.getElementById("sqbt-image-status");
        if (pictureStatus) pictureStatus.textContent = "Loading observed parts; the reconstructed card will appear below.";
      }
    });
    host.appendChild(loadObserved);
  }
  const visibleRecipe = [
    ...(attrs.title_candidates || []).slice(1, 6),
    ...(attrs.perks || []),
    ...(attrs.stats || []).map((row) => `${row.label}: ${row.value}`),
    ...(attrs.flavor_lines || []),
  ]
    .map((value) => String(value || "").trim())
    .filter((value, index, all) => value && all.indexOf(value) === index)
    .slice(0, 24);
  if (visibleRecipe.length) {
    const recipe = document.createElement("details");
    recipe.className = "sqbt-image-visible-recipe";
    const recipeSummary = document.createElement("summary");
    recipeSummary.textContent = `Observed card text (${visibleRecipe.length})`;
    const recipeList = document.createElement("ul");
    for (const value of visibleRecipe) {
      const li = document.createElement("li");
      li.textContent = value;
      recipeList.appendChild(li);
    }
    recipe.append(recipeSummary, recipeList);
    host.appendChild(recipe);
  }

  for (const item of result.exact_items || []) {
    const row = document.createElement("div");
    row.className = "sqbt-image-candidate is-exact";
    const copy = document.createElement("div");
    copy.innerHTML = `<strong>${escapeHtml(item.display_name || "Validated serial")}</strong><br>` +
      `<span class="muted small">Exact @U · ${escapeHtml(item.item_type || "item")} · ` +
      `${escapeHtml(String(item.identity?.payload_sha256 || "").slice(0, 12))}</span>`;
    const use = document.createElement("button");
    use.type = "button";
    use.className = "primary";
    use.textContent = "Use exact item";
    use.addEventListener("click", async () => {
      try {
        await editorUseAnalyzedSerial(item.serial);
      } catch (error) {
        if (actionMessage) {
          actionMessage.className = "action-message error";
          actionMessage.textContent = String(error?.message || error);
        }
      }
    });
    row.append(copy, use);
    host.appendChild(row);
  }

  const candidates = Array.isArray(result.candidates) ? result.candidates : [];
  if (!result.exact && candidates.length) {
    const warning = document.createElement("p");
    warning.className = "muted small";
    warning.textContent =
      "Suggestions match visible text only. A picture cannot prove hidden parts or rolls.";
    host.appendChild(warning);
    for (const [candidateIndex, item] of candidates.slice(0, 10).entries()) {
      const row = document.createElement("div");
      row.className = "sqbt-image-candidate";
      row.dataset.selected = String(editorPictureSelectedSource === item.serial);
      const copy = document.createElement("div");
      const evidence = Array.isArray(item.evidence) ? item.evidence.join(", ") : "";
      copy.innerHTML = `<strong>${candidateIndex === 0 ? "Top match · " : ""}${escapeHtml(item.name || "Candidate")}</strong><br>` +
        `<span class="muted small">match score ${Number(item.score || 0)}${evidence ? ` · ${escapeHtml(evidence)}` : ""}</span>`;
      const use = document.createElement("button");
      use.type = "button";
      use.className = "ghost";
      use.textContent = editorPictureSelectedSource === item.serial ? "Selected" : "Use this item";
      use.disabled = !String(item.serial || "").startsWith("@U");
      use.addEventListener("click", async () => {
        try {
          await editorUseAnalyzedSerial(item.serial, { pictureCandidate: true });
          renderEditorImageResult();
        } catch (error) {
          if (actionMessage) {
            actionMessage.className = "action-message error";
            actionMessage.textContent = String(error?.message || error);
          }
        }
      });
      row.append(copy, use);
      host.appendChild(row);
    }
  } else if (!result.exact) {
    const none = document.createElement("p");
    none.className = "muted small";
    none.textContent =
      "No strong known-item serial match. Load the observed facts into Build to reconstruct it; hidden parts and rolls cannot be recovered from this picture.";
    host.appendChild(none);
  }

  const details = document.createElement("details");
  const detailsSummary = document.createElement("summary");
  detailsSummary.textContent = "OCR text";
  const pre = document.createElement("pre");
  pre.className = "sqbt-image-ocr-text";
  pre.textContent = [result.ocr?.header_text, result.ocr?.text].filter(Boolean).join("\n\n") || "No text found.";
  details.append(detailsSummary, pre);
  host.appendChild(details);
}

async function runEditorImageIdentification(payload, previewUrl = "") {
  const status = document.getElementById("sqbt-image-status");
  if (status) {
    status.textContent = "Reading picture locally…";
    status.className = "muted small";
  }
  if (previewUrl) editorImagePreviewUrl = previewUrl;
  let result;
  if (payload?.picker) result = await window.sqbt.pickItemImage();
  else result = await window.sqbt.identifyItemImage(payload || {});
  if (result?.cancelled) {
    if (status) status.textContent = "No picture selected.";
    return;
  }
  editorImageResult = await augmentEditorImageCandidates(result || { ok: false });
  const pictureLevel = document.getElementById("sqbt-picture-level");
  const detectedLevel = Number(editorImageResult?.extracted?.level);
  if (
    pictureLevel &&
    pictureLevel.dataset.userChanged !== "1" &&
    Number.isFinite(detectedLevel) &&
    detectedLevel >= 1
  ) {
    pictureLevel.value = String(Math.trunc(detectedLevel));
  }
  if (status) {
    status.textContent = editorImageResult?.ok
      ? editorImageResult.message || "Picture read."
      : editorImageResult?.message || "Picture analysis failed.";
    status.className = editorImageResult?.ok ? "muted small" : "error small";
  }
  const preview = document.getElementById("sqbt-image-preview");
  if (preview && editorImagePreviewUrl) {
    preview.src = editorImagePreviewUrl;
    preview.hidden = false;
  }
  renderEditorImageResult();
  try {
    await previewTopPictureCandidate(editorImageResult);
  } catch (error) {
    editorPicturePreview = null;
    if (status) {
      status.textContent = `${editorImageResult?.message || "Picture read."} Top-match card preview failed: ${String(error?.message || error)}`;
      status.className = "attention small";
    }
  }
}

function fileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("Could not read image."));
    reader.readAsDataURL(file);
  });
}

function renderEditorImagePanel() {
  const panel = document.createElement("section");
  panel.className = "sqbt-image-identify";
  const title = document.createElement("h4");
  title.textContent = "Identify from picture";
  const hint = document.createElement("p");
  hint.className = "muted small";
  hint.textContent =
    "Drop, paste, or choose an item picture. OCR stays on this PC. Exact @U codes are validated; otherwise SQBT only suggests known items.";
  const drop = document.createElement("div");
  drop.className = "sqbt-image-drop";
  drop.tabIndex = 0;
  drop.textContent = "Drop or paste PNG / JPEG / WebP";
  const choose = document.createElement("button");
  choose.type = "button";
  choose.className = "ghost";
  choose.textContent = "Choose picture";
  choose.addEventListener("click", () =>
    runEditorImageIdentification({ picker: true }).catch((error) => {
      editorImageResult = { ok: false, message: String(error?.message || error) };
      renderEditorImageResult();
    })
  );
  const preview = document.createElement("img");
  preview.id = "sqbt-image-preview";
  preview.className = "sqbt-image-preview";
  preview.alt = "Selected item picture";
  preview.hidden = !editorImagePreviewUrl;
  if (editorImagePreviewUrl) preview.src = editorImagePreviewUrl;
  const status = document.createElement("p");
  status.id = "sqbt-image-status";
  status.className = "muted small";
  status.textContent = "No picture selected.";
  const results = document.createElement("div");
  results.id = "sqbt-image-results";
  const useFile = async (file) => {
    if (!file || !/^image\/(?:png|jpeg|webp)$/i.test(String(file.type || ""))) {
      throw new Error("Use a PNG, JPEG, or WebP image.");
    }
    if (file.size > 12 * 1024 * 1024) throw new Error("Image is larger than 12 MB.");
    const dataUrl = await fileAsDataUrl(file);
    await runEditorImageIdentification(
      { base64: dataUrl, mime: file.type, name: file.name || "" },
      dataUrl
    );
  };
  drop.addEventListener("dragover", (event) => {
    event.preventDefault();
    drop.classList.add("is-over");
  });
  drop.addEventListener("dragleave", () => drop.classList.remove("is-over"));
  drop.addEventListener("drop", (event) => {
    event.preventDefault();
    drop.classList.remove("is-over");
    useFile(event.dataTransfer?.files?.[0]).catch((error) => {
      editorImageResult = { ok: false, message: String(error?.message || error) };
      renderEditorImageResult();
    });
  });
  drop.addEventListener("paste", (event) => {
    const file = [...(event.clipboardData?.files || [])][0];
    if (!file) return;
    event.preventDefault();
    useFile(file).catch((error) => {
      editorImageResult = { ok: false, message: String(error?.message || error) };
      renderEditorImageResult();
    });
  });
  panel.append(title, hint, drop, choose, preview, status, results);
  queueMicrotask(renderEditorImageResult);
  return panel;
}

function renderEditorStartPanel() {
  const panel = document.createElement("section");
  panel.className = "sqbt-builder-start";
  const title = document.createElement("h4");
  title.textContent = "Start from an item";
  const hint = document.createElement("p");
  hint.className = "muted small";
  hint.textContent =
    "Paste an exact @U to load its decoded parts into Build. SQBT preserves that serial until an edit produces a newly validated serial.";
  const row = document.createElement("div");
  row.className = "sqbt-builder-start-row";
  const input = document.createElement("input");
  input.type = "text";
  input.id = "sqbt-builder-serial-input";
  input.placeholder = "Paste @U serial";
  input.autocomplete = "off";
  const load = document.createElement("button");
  load.type = "button";
  load.className = "primary";
  load.textContent = "Decode & load";
  load.addEventListener("click", async () => {
    try {
      load.disabled = true;
      await editorUseAnalyzedSerial(input.value);
      input.value = editorLatest.serial;
    } catch (error) {
      if (actionMessage) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = String(error?.message || error);
      }
    } finally {
      load.disabled = false;
    }
  });
  const validate = document.createElement("button");
  validate.type = "button";
  validate.className = "ghost";
  validate.textContent = "Validate current build";
  validate.addEventListener("click", async () => {
    try {
      validate.disabled = true;
      const serial = await editorEnsureSerial();
      const analysis = editorLatest.analysis;
      if (actionMessage) {
        actionMessage.className = "action-message ok";
        actionMessage.textContent =
          `Validated exact item ${String(analysis?.identity?.payload_sha256 || "").slice(0, 16)} · ${serial.length} chars.`;
      }
    } catch (error) {
      if (actionMessage) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = String(error?.message || error);
      }
    } finally {
      validate.disabled = false;
    }
  });
  row.append(input, load, validate);
  const status = document.createElement("div");
  status.id = "sqbt-builder-validation";
  status.className = "muted small";
  panel.append(title, hint, row, status);
  queueMicrotask(renderEditorValidation);
  return panel;
}

function renderEditorShell(tab) {
  ensureEditorMessageListener();
  const section = (tab.sections || []).find((s) => s.editorEmbed) || (tab.sections || [])[0] || {};
  const shell = document.createElement("section");
  shell.className = "panel-section sqbt-editor-shell";
  shell.dataset.editorShell = "1";

  const credit = document.createElement("div");
  credit.className = "sqbt-editor-credit";
  credit.innerHTML =
    `<div class="sqbt-editor-credit-text">` +
    `<div class="sqbt-editor-credit-brand">Scooter's Toolbox</div>` +
    `<div class="sqbt-editor-credit-title">Simple Builder</div>` +
    `<p class="muted small">Craft UI from scooterstoolbox.com — Send code/item below stays SQBT.</p>` +
    `</div>`;
  const fullLink = document.createElement("button");
  fullLink.type = "button";
  fullLink.className = "ghost sqbt-editor-full-link";
  fullLink.textContent = "Open full save editor";
  fullLink.title = "Opens scooterstoolbox.com in your browser";
  fullLink.addEventListener("click", () => {
    if (typeof window.sqbt?.openExternal === "function") {
      window.sqbt.openExternal("https://scooterstoolbox.com/");
    }
  });
  credit.appendChild(fullLink);
  shell.appendChild(credit);

  const title = document.createElement("h3");
  title.textContent = section.title || "Build & deliver";
  shell.appendChild(title);
  if (section.hint) {
    const hint = document.createElement("p");
    hint.className = "muted small";
    hint.textContent = section.hint;
    shell.appendChild(hint);
  }
  shell.appendChild(renderEditorStartPanel());

  const bar = document.createElement("div");
  bar.className = "sqbt-editor-bar";

  const recipientKey = "editor:deliver_player_index";
  const recipientLabel = document.createElement("label");
  recipientLabel.className = "sqbt-editor-field";
  recipientLabel.dataset.fieldKey = recipientKey;
  recipientLabel.innerHTML = `<span>Give to</span>`;
  const recipientSelect = document.createElement("select");
  recipientSelect.id = "sqbt-editor-recipient";
  recipientSelect.dataset.role = "player-select";
  recipientSelect.dataset.includeAll = "1";
  recipientSelect.addEventListener("change", () => {
    fieldValues[recipientKey] = recipientSelect.value;
    syncBoostTargetFromSendTo(recipientSelect.value);
  });
  recipientLabel.appendChild(recipientSelect);
  bar.appendChild(recipientLabel);

  const countLabel = document.createElement("label");
  countLabel.className = "sqbt-editor-field";
  countLabel.innerHTML = `<span>Copies</span>`;
  const countInput = document.createElement("input");
  countInput.type = "number";
  countInput.min = "1";
  countInput.max = "20";
  countInput.value = "1";
  countInput.id = "sqbt-editor-count";
  countLabel.appendChild(countInput);
  bar.appendChild(countLabel);

  const cardToggle = document.createElement("label");
  cardToggle.className = "sqbt-editor-toggle";
  const cardCheck = document.createElement("input");
  cardCheck.type = "checkbox";
  cardCheck.id = "sqbt-editor-card-toggle";
  cardCheck.checked = editorShowItemCard();
  cardCheck.addEventListener("change", () => {
    setEditorShowItemCard(cardCheck.checked);
    if (cardCheck.checked) scheduleEditorCardPaint();
    else paintEditorItemCard(null);
  });
  cardToggle.appendChild(cardCheck);
  cardToggle.appendChild(document.createTextNode(" Show item card"));
  bar.appendChild(cardToggle);

  const mailBtn = document.createElement("button");
  mailBtn.type = "button";
  mailBtn.id = "sqbt-editor-mail";
  mailBtn.className = "primary";
  mailBtn.textContent = "Give built item";
  mailBtn.title = "Mail the validated built item to the selected player(s)";
  mailBtn.addEventListener("click", async () => {
    const status = document.getElementById("sqbt-editor-status");
    try {
      mailBtn.disabled = true;
      const serial = await editorEnsureSerial();
      const count = Math.max(1, Math.min(20, Number(countInput.value) || 1));
      const players = latestStatus?.raw?.players || [];
      const selectedRecipient = Number(recipientSelect.value);
      const playerIndex = Number.isFinite(selectedRecipient)
        ? selectedRecipient
        : preferredDeliveryPlayerIndex(players);
      if (status) {
        status.dataset.sticky = "1";
        status.textContent = "Sending…";
        status.className = "muted small";
      }
      const payload = {
        serials: [serial],
        count,
        mode: playerIndex === -1 ? "all" : "player",
        player_index: playerIndex,
        open_rewards: true,
      };
      const { data } = await window.sqbt.postAction("deliver_serials", payload);
      if (actionMessage) {
        actionMessage.className = data?.ok === false ? "action-message error" : "action-message ok";
        actionMessage.textContent = data?.message || (data?.ok === false ? "Send failed." : "Sent.");
      }
      if (status) {
        status.textContent = data?.message || (data?.ok === false ? "Send failed" : "Built item sent");
        status.className = data?.ok === false ? "error small" : "ok small";
        delete status.dataset.sticky;
      }
    } catch (error) {
      if (actionMessage) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = String(error?.message || error || "Send failed.");
      }
      if (status) {
        status.textContent = String(error?.message || error || "Send failed");
        status.className = "error small";
        delete status.dataset.sticky;
      }
    } finally {
      refreshEditorDeliveryButtons();
    }
  });
  bar.appendChild(mailBtn);

  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.id = "sqbt-editor-copy";
  copyBtn.className = "ghost";
  copyBtn.textContent = "Copy @U";
  copyBtn.addEventListener("click", async () => {
    try {
      const serial = await editorEnsureSerial();
      await navigator.clipboard.writeText(serial);
      if (actionMessage) {
        actionMessage.className = "action-message ok";
        actionMessage.textContent = "Copied @U to clipboard.";
      }
    } catch (error) {
      if (actionMessage) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = String(error?.message || error || "Copy failed.");
      }
    } finally {
      refreshEditorDeliveryButtons();
    }
  });
  bar.appendChild(copyBtn);

  const libBtn = document.createElement("button");
  libBtn.type = "button";
  libBtn.id = "sqbt-editor-library";
  libBtn.className = "ghost";
  libBtn.textContent = "Add to Builds";
  libBtn.addEventListener("click", async () => {
    try {
      const serial = await editorEnsureSerial();
      const preview = editorLatest.preview || {};
      const name =
        String(preview.title || "").trim() ||
        `Editor ${new Date().toISOString().slice(0, 19).replace("T", " ")}`;
      const { data } = await window.sqbt.postAction("serial_store_import_serials", {
        name,
        group: "Editor",
        serials: [serial],
      });
      if (actionMessage) {
        actionMessage.className = data?.ok === false ? "action-message error" : "action-message ok";
        actionMessage.textContent = data?.message || (data?.ok === false ? "Build save failed." : "Saved to Builds.");
      }
      if (data?.ok !== false) {
        const pack = String(data?.group || "Editor").trim() || "Editor";
        for (const box of document.querySelectorAll("[data-multiselect-section]")) {
          const sid = box.dataset.multiselectSection;
          if (!sid) continue;
          const config = getMultiselectConfig(sid);
          if (config?.catalog !== "serial_store") continue;
          if (!serialStoreExpanded.has(sid)) serialStoreExpanded.set(sid, new Set());
          serialStoreExpanded.get(sid).add(pack);
          rememberSerialStorePackNames(sid, [...serialStoreKnownPackNames(sid), pack]);
        }
        refreshAllSerialStoreSections();
      }
    } catch (error) {
      if (actionMessage) {
        actionMessage.className = "action-message error";
        actionMessage.textContent = String(error?.message || error || "Build save failed.");
      }
    } finally {
      refreshEditorDeliveryButtons();
    }
  });
  bar.appendChild(libBtn);

  shell.appendChild(bar);

  const status = document.createElement("p");
  status.id = "sqbt-editor-status";
  status.className = "muted small";
  status.textContent = editorFrameLoaded ? "Editor ready — craft kept across tabs." : "Loading editor…";
  shell.appendChild(status);

  const workspace = document.createElement("div");
  workspace.className = "sqbt-editor-workspace";

  const frame = ensureEditorFrameElement();
  frame.className = "sqbt-editor-frame";
  workspace.appendChild(frame);

  const cardHost = document.createElement("div");
  cardHost.id = "sqbt-editor-card";
  cardHost.className = "sqbt-editor-card-host";
  cardHost.hidden = !editorShowItemCard();
  workspace.appendChild(cardHost);
  shell.appendChild(workspace);

  tabContent.appendChild(shell);
  refreshEditorDeliveryButtons();
  refreshPlayerSelects();
  if (editorShowItemCard()) paintEditorItemCard(editorLatest.preview);
}

function renderPictureItemShell(tab) {
  ensureEditorMessageListener();
  ensureEditorFrameElement();
  const section = (tab.sections || [])[0] || {};
  const shell = document.createElement("section");
  shell.className = "panel-section sqbt-picture-shell";
  const heading = document.createElement("h3");
  heading.textContent = section.title || "Picture to item";
  shell.appendChild(heading);
  if (section.hint) {
    const hint = document.createElement("p");
    hint.className = "muted small";
    hint.textContent = section.hint;
    shell.appendChild(hint);
  }
  shell.appendChild(renderEditorImagePanel());

  const serialTools = document.createElement("section");
  serialTools.className = "sqbt-picture-output";
  const serialHeading = document.createElement("h4");
  serialHeading.textContent = "Confirmed result";
  const serialHint = document.createElement("p");
  serialHint.className = "muted small";
  serialHint.textContent =
    "After choosing a suggestion, SQBT keeps its hidden catalog parts, applies uniquely visible picture evidence, and builds one validated serial. The top match is selected automatically; choose another result to replace it.";
  const serialField = document.createElement("textarea");
  serialField.id = "sqbt-picture-final-serial";
  serialField.rows = 3;
  serialField.readOnly = true;
  serialField.placeholder = "Choose a candidate or load observed parts, then generate the final @U";
  serialField.value = editorLatest.serial || "";

  const outputBar = document.createElement("div");
  outputBar.className = "sqbt-editor-bar";
  const levelLabel = document.createElement("label");
  levelLabel.className = "sqbt-editor-field";
  levelLabel.innerHTML = "<span>Final item level</span>";
  const levelInput = document.createElement("input");
  levelInput.id = "sqbt-picture-level";
  levelInput.type = "number";
  levelInput.min = "1";
  levelInput.max = "100";
  levelInput.value = String(
    editorPictureTargetLevel ||
    (Number.isFinite(Number(editorImageResult?.extracted?.level))
      ? Math.trunc(Number(editorImageResult.extracted.level))
      : 70)
  );
  levelInput.addEventListener("input", () => {
    levelInput.dataset.userChanged = "1";
    editorPictureTargetLevel = Math.max(
      1,
      Math.min(100, Math.trunc(Number(levelInput.value) || 70))
    );
  });
  levelLabel.appendChild(levelInput);
  const generate = document.createElement("button");
  generate.type = "button";
  generate.className = "primary";
  generate.textContent = "Generate / refresh @U";
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "ghost";
  copy.textContent = "Copy @U";

  const recipientKey = "picture_item:deliver_player_index";
  const recipientLabel = document.createElement("label");
  recipientLabel.className = "sqbt-editor-field";
  recipientLabel.dataset.fieldKey = recipientKey;
  recipientLabel.innerHTML = "<span>Give to</span>";
  const recipient = document.createElement("select");
  recipient.dataset.role = "player-select";
  recipient.dataset.includeAll = "1";
  recipient.addEventListener("change", () => {
    fieldValues[recipientKey] = recipient.value;
    syncBoostTargetFromSendTo(recipient.value);
  });
  recipientLabel.appendChild(recipient);

  const countLabel = document.createElement("label");
  countLabel.className = "sqbt-editor-field";
  countLabel.innerHTML = "<span>Copies</span>";
  const count = document.createElement("input");
  count.type = "number";
  count.min = "1";
  count.max = "20";
  count.value = "1";
  countLabel.appendChild(count);

  const give = document.createElement("button");
  give.type = "button";
  give.className = "primary";
  give.textContent = "Give pictured item";
  const deliveryStatus = document.createElement("p");
  deliveryStatus.id = "sqbt-picture-delivery-status";
  deliveryStatus.className = "muted small";
  deliveryStatus.textContent = editorLatest.serial
    ? "A validated result is ready."
    : "No generated item yet.";

  const refreshFinalSerial = async () => {
    let serial = await editorEnsureSerial();
    if (editorPictureUncertain || levelInput.dataset.userChanged === "1") {
      serial = await finalizePictureSerialAtLevel(serial, levelInput.value, {
        syncBuilder: true,
      });
    }
    serialField.value = serial;
    deliveryStatus.textContent = editorPictureUncertain
      ? "Validated serial generated from your confirmed suggestion; hidden rolls may differ from the picture."
      : "Exact validated serial ready.";
    deliveryStatus.className = editorPictureUncertain ? "attention small" : "ok small";
    return serial;
  };
  generate.addEventListener("click", async () => {
    try {
      generate.disabled = true;
      await refreshFinalSerial();
    } catch (error) {
      deliveryStatus.textContent = String(error?.message || error || "Serial generation failed.");
      deliveryStatus.className = "error small";
    } finally {
      generate.disabled = false;
    }
  });
  copy.addEventListener("click", async () => {
    try {
      const serial = await refreshFinalSerial();
      await navigator.clipboard.writeText(serial);
      deliveryStatus.textContent = "Copied final @U.";
      deliveryStatus.className = "ok small";
    } catch (error) {
      deliveryStatus.textContent = String(error?.message || error || "Copy failed.");
      deliveryStatus.className = "error small";
    }
  });
  give.addEventListener("click", async () => {
    if (
      editorPictureUncertain &&
      !window.confirm(
        "This item is based on a picture suggestion. Visible evidence was applied, but hidden parts and rolls may differ. Give this validated result?"
      )
    ) {
      return;
    }
    try {
      give.disabled = true;
      const serial = await refreshFinalSerial();
      const players = latestStatus?.raw?.players || [];
      const selectedRecipient = Number(recipient.value);
      const playerIndex = Number.isFinite(selectedRecipient)
        ? selectedRecipient
        : preferredDeliveryPlayerIndex(players);
      const { data } = await window.sqbt.postAction("deliver_serials", {
        serials: [serial],
        count: Math.max(1, Math.min(20, Number(count.value) || 1)),
        mode: playerIndex === -1 ? "all" : "player",
        player_index: playerIndex,
        open_rewards: true,
      });
      deliveryStatus.textContent =
        data?.message || (data?.ok === false ? "Give failed." : "Item queued.");
      deliveryStatus.className = data?.ok === false ? "error small" : "ok small";
    } catch (error) {
      deliveryStatus.textContent = String(error?.message || error || "Give failed.");
      deliveryStatus.className = "error small";
    } finally {
      give.disabled = false;
    }
  });
  outputBar.append(levelLabel, generate, copy, recipientLabel, countLabel, give);
  serialTools.append(serialHeading, serialHint, serialField, outputBar, deliveryStatus);
  shell.appendChild(serialTools);

  const openBuilder = document.createElement("button");
  openBuilder.type = "button";
  openBuilder.className = "ghost";
  openBuilder.textContent = "Open Item Builder";
  openBuilder.addEventListener("click", () => {
    activeTabId = "editor";
    renderTabs();
    const builderTab = manifest.tabs.find((row) => row.id === "editor");
    if (builderTab) renderTab(builderTab);
  });
  shell.appendChild(openBuilder);

  const cardHeading = document.createElement("h4");
  cardHeading.textContent = "Reconstructed item card";
  const cardHint = document.createElement("p");
  cardHint.className = "muted small";
  cardHint.textContent =
    "Appears after a confirmed catalog serial or observed parts are loaded into Item Builder. Unknown hidden parts remain unknown.";
  const cardHost = document.createElement("div");
  cardHost.id = "sqbt-picture-card";
  cardHost.className = "sqbt-editor-card-host sqbt-picture-card-host";
  shell.append(cardHeading, cardHint, cardHost);
  tabContent.appendChild(shell);
  refreshPlayerSelects();
  if (editorPicturePreview || editorLatest.preview) {
    paintEditorItemCard(editorPicturePreview || editorLatest.preview, "sqbt-picture-card");
  }
}

function renderTab(tab) {
  if (tab.id !== "editor") parkEditorFrameIfNeeded();
  tabContent.innerHTML = "";
  tabContent.dataset.activeTab = tab.id;
  catalogCache.clear();
  lastRosterSignature = "";
  stopLiveLogPolling();
  disconnectDeskCatalogObserver();
  if (tab.id === "editor") {
    renderEditorShell(tab);
    refreshActionButtons();
    return;
  }
  if (tab.id === "picture_item") {
    renderPictureItemShell(tab);
    refreshActionButtons();
    return;
  }
  for (const section of tab.sections || []) {
    // Hide Home "Start here" only when actions unlock (main menu Online is not enough).
    if (String(section.title || "") === "Start here" && actionsEnabled()) {
      continue;
    }
    const sectionEl = renderSection(section, tab.id);
    if (sectionEl) tabContent.appendChild(sectionEl);
  }
  if (tab.id === "log") {
    startLiveLogPolling();
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
    // Only kick a status round when something is actually working — not on every
    // Loot/Serials visit while Auto Lobby idles (that froze the EXE mid-browse).
    if (progressBusy) {
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
  const lobbyBtn = document.getElementById("nav-mode-lobby");
  const burger = document.getElementById("nav-burger-btn");
  if (tabsBtn && !tabsBtn.dataset.bound) {
    tabsBtn.dataset.bound = "1";
    tabsBtn.addEventListener("click", () => setNavMode("tabs"));
  }
  if (menuBtn && !menuBtn.dataset.bound) {
    menuBtn.dataset.bound = "1";
    menuBtn.addEventListener("click", () => setNavMode("menu"));
  }
  if (lobbyBtn && !lobbyBtn.dataset.bound) {
    lobbyBtn.dataset.bound = "1";
  lobbyBtn.addEventListener("click", () => setNavMode("compact"));
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
  document.body.classList.toggle("nav-mode-tabs", navMode === "tabs");
  document.body.classList.toggle("nav-mode-lobby", navMode === "compact");
  document.body.classList.toggle("nav-mode-compact", navMode === "compact");
  const chrome = document.querySelector(".nav-chrome");
  if (chrome) {
    chrome.classList.toggle("nav-mode-menu", navMode === "menu");
    chrome.classList.toggle("nav-mode-tabs", navMode === "tabs");
    chrome.classList.toggle("nav-mode-lobby", navMode === "compact");
    chrome.classList.toggle("nav-mode-compact", navMode === "compact");
  }
  const tabsBtn = document.getElementById("nav-mode-tabs");
  const menuBtn = document.getElementById("nav-mode-menu");
  const lobbyBtn = document.getElementById("nav-mode-lobby");
  const burger = document.getElementById("nav-burger-btn");
  const drawer = document.getElementById("nav-drawer");
  if (tabsBtn) tabsBtn.classList.toggle("active", navMode === "tabs");
  if (menuBtn) menuBtn.classList.toggle("active", navMode === "menu");
  if (lobbyBtn) lobbyBtn.classList.toggle("active", navMode === "compact");
  if (tabBar) {
    const hideTabs = navMode === "menu" || navMode === "compact";
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
  const raw = String(mode || "tabs").trim().toLowerCase();
  const next =
    raw === "menu" ? "menu" : raw === "lobby" || raw === "desk" || raw === "compact" ? "compact" : "tabs";
  const prev = navMode;
  navMode = next;
  try {
    localStorage.setItem(NAV_MODE_KEY, navMode);
  } catch (_) {
    /* ignore */
  }
  navDrawerOpen = navMode === "menu";
  applyNavMode();
  if (navMode === "compact") {
    renderLobbyView();
    return;
  }
  if (prev === "compact" || navMode !== prev) {
    renderTabs();
  } else {
    applyNavMode();
  }
}

function renderTabs() {
  initNavModeControls();
  if (navMode === "compact") {
    applyNavMode();
    renderLobbyView();
    return;
  }
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

  // Compact mode: open the matching accordion band, then flash the control.
  if (navMode === "compact") {
    if (tabContent?.dataset.activeTab !== "lobby") {
      renderLobbyView();
    }
    const bandId = resolveLobbyBandForSearchHit(row);
    if (bandId) expandDeskBand(bandId, { scroll: true });
    if (row.tabId === "serials") {
      const needle = `${row.sectionTitle || ""} ${row.label || ""}`.toLowerCase();
      if (row.segment && SERIALS_SEGMENTS.some((s) => s.id === String(row.segment))) {
        writeSerialsSegment(String(row.segment));
      } else if (/gzo|lootlemon|browse/.test(needle)) writeSerialsSegment("codes");
      else if (/library|my packs|item list/.test(needle)) writeSerialsSegment("library");
      else if (/mail|pending|reward|shiny mail/.test(needle)) writeSerialsSegment("mail");
    }
    window.setTimeout(() => flashToolSearchTarget(row), 80);
    return;
  }

  activeTabId = row.tabId;
  if (row.tabId === "serials") {
    const needle = `${row.sectionTitle || ""} ${row.label || ""}`.toLowerCase();
    if (row.segment && SERIALS_SEGMENTS.some((s) => s.id === String(row.segment))) {
      writeSerialsSegment(String(row.segment));
    } else if (/gzo|lootlemon|browse/.test(needle)) writeSerialsSegment("codes");
    else if (/library|my packs|item list/.test(needle)) writeSerialsSegment("library");
    else if (/mail|pending|reward|shiny mail/.test(needle)) writeSerialsSegment("mail");
  }
  renderTabs();
  window.setTimeout(() => flashToolSearchTarget(row), 40);
}

function resolveLobbyBandForSearchHit(row) {
  const tabId = String(row?.tabId || "").trim().toLowerCase();
  const sectionTitle = String(row?.sectionTitle || "").trim();
  const layoutSections = manifest?.lobby?.sections || [];
  let currentBand = "";
  for (const section of layoutSections) {
    if (!section || typeof section !== "object") continue;
    if (isDeskBandHeader(section)) {
      currentBand = deskBandKey(section);
      continue;
    }
    if (!currentBand) continue;
    if (sectionTitle && String(section.title || "").trim() === sectionTitle) {
      return currentBand;
    }
  }
  // Fall back to tab id when it matches a Compact jump band (loot, serials, …).
  if (tabId && deskBandCache.has(tabId)) return tabId;
  if (tabId && DESK_JUMP_LABELS[tabId]) return tabId;
  return currentBand || tabId || "";
}

function flashToolSearchTarget(row) {
  if (!tabContent || !row) return;
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
  const flashHost = target.closest(".action-card") || target.closest(".desk-band-wrap") || target;
  flashHost.classList.add("tool-search-flash");
  window.setTimeout(() => flashHost.classList.remove("tool-search-flash"), 1600);
}

async function loadManifest(options = {}) {
  const allowOffline = Boolean(options.allowOffline) || uiPreviewOnline;
  const gen = ++manifestLoadGen;
  let result = await window.sqbt.getManifest();
  if (gen !== manifestLoadGen) return;
  if (!result.ok && allowOffline && typeof window.sqbt.getOfflineManifest === "function") {
    result = await window.sqbt.getOfflineManifest();
  }
  if (!result.ok && allowOffline) {
    try {
      const cached = JSON.parse(String(localStorage.getItem("sqbt.lastManifest") || ""));
      if (cached && Array.isArray(cached.tabs) && cached.tabs.length) {
        result = { ok: true, manifest: cached, source: "localStorage" };
      }
    } catch {
      /* ignore */
    }
  }
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
  // Do not paint the full tools UI until the bridge is Online in-game (unless UI preview).
  if (!bridgeConnectedHeld() && !allowOffline) {
    clearToolsToWaiting(t("waiting.manifestUnavailable"));
    return;
  }
  const focused = document.activeElement;
  const editing =
    focused &&
    tabContent?.contains(focused) &&
    (focused.matches?.("input, textarea, select") || focused.isContentEditable);
  manifest = lockManifestToFirstRelease(result.manifest);
  applyDevUnlockTabs();
  try {
    if (manifest?.tabs?.length) {
      localStorage.setItem("sqbt.lastManifest", JSON.stringify(manifest));
    }
  } catch {
    /* ignore */
  }
  if (activeTabId && manifest?.tabs?.length && !manifest.tabs.some((row) => row.id === activeTabId)) {
    activeTabId = "home";
  }
  // Never wipe the open tab mid-keystroke — that is the “can't edit fields” bug.
  if (editing || isUserEditingTools()) {
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
      sdkStatusLine.textContent = baseSdk?.gameRoot
        ? `${t("sdk.notFound")} ${baseSdk.pythonMessage || ""} ${baseSdk.missing?.length ? `Missing: ${baseSdk.missing.join(", ")}.` : ""}`
        : "Choose the Borderlands 4 game folder, not the folder containing this tool.";
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
      if (baseSdk.pythonMessage) sdkStatusLine.textContent += ` ${baseSdk.pythonMessage}`;
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
    setModSyncBanner("ok", {
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
  applyDevUnlockTabs();
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
        await autoInstallMissingSdk(prompted);
      }
    } catch {
      /* user can still use Set install folder */
    }
  }
  await autoInstallMissingSdk(setup);
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

function applyDevUnlockTabs() {
  if (!manifest?.tabs?.length) return;
  for (const tab of manifest.tabs) {
    if (tab.dev_unlock) {
      tab.hidden = !hiddenShapesUnlocked;
    }
  }
}

/** First-release EXE: drop any live/private tabs not on the bundled allowlist. */
function lockManifestToFirstRelease(raw) {
  return window.SQBT_RESTRICT_MANIFEST(raw, window.SQBT_RELEASE_UI_SCHEMA);
}

async function finishHiddenShapeUnlock() {
  hiddenShapesUnlocked = true;
  try {
    await window.sqbt.unlockHiddenShapes();
  } catch {
    /* still show the options in this session */
  }
  injectHiddenShapeOptions();
  applyDevUnlockTabs();
  renderTabs();
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
  // When the game is not Online: toggle UI-preview Online so tabs/Editor work without loading BL4.
  const gameConnected =
    Boolean(latestStatus?.connected) && String(latestStatus?.raw?.session || "") !== "UI preview";
  if (!gameConnected) {
    setUiPreviewOnline(!uiPreviewOnline);
    unlockDevSmokePanel();
    return;
  }
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
    const startedSetup = await autoInstallMissingSdk(result);
    if (!startedSetup && !(result.modSync?.updated && result.modSync?.ok) && setupMessage) {
      setupMessage.className = "setup-message";
      setupMessage.textContent = result.baseSdk?.installed
        ? "Install folder saved. Squ1ggs mod auto-syncs on EXE launch."
        : "Install folder saved. Base SDK missing — press Install SDK + Squ1ggs mod once.";
    }
  }
});

async function autoInstallMissingSdk(setup) {
  const root = String(setup?.baseSdk?.gameRoot || "").trim();
  if (!root || setup.baseSdk.installed || sdkInstallInProgress) return false;
  const key = root.toLowerCase();
  if (automaticSdkSetupAttempts.has(key)) return false;
  automaticSdkSetupAttempts.add(key);
  showSetupCard();
  if (setup.modSync?.gameRunning) {
    setupMessage.className = "setup-message attention";
    setupMessage.textContent = "BL4 SDK setup is incomplete. Close Borderlands 4, then press Install SDK + Squ1ggs mod to finish setup.";
    return true;
  }
  await runInstall({includeBaseSdk: true});
  return true;
}

async function runInstall({ forceBaseSdk = false, includeBaseSdk = false } = {}) {
  if (sdkInstallInProgress) return;
  sdkInstallInProgress = true;
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
    sdkInstallInProgress = false;
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
  const giveEverythingStop = event.target?.closest?.("[data-give-everything-stop]");
  if (giveEverythingStop) {
    event.preventDefault();
    event.stopPropagation();
    if (!actionsEnabled()) return;
    lastGiveEverythingStatus = { ...(lastGiveEverythingStatus || {}), active: true, running: false, phase: "cancelled", message: "Stopping Give everything…" };
    lastProgressHtml = "";
    renderProgressPanel(null, null, null);
    window.sqbt?.postAction?.("give_everything_cancel", {}, 8)?.then((res) => {
      lastGiveEverythingStatus = res?.data?.give_everything || null;
      lastProgressHtml = "";
      renderProgressPanel(null, null, null);
    }).catch(() => { startProgressPoll(); });
    return;
  }
  const challengeStop = event.target?.closest?.("[data-challenge-stop]");
  if (challengeStop) {
    event.preventDefault();
    event.stopPropagation();
    if (!actionsEnabled()) return;
    // Stop must work even while another action/poll holds actionBusy.
    // Optimistic stop so the bar leaves "live" immediately; cancel handler finishes hide.
    const idx = Number(lastChallengeStatus?.index || lastChallengeStatus?.progress_index || 0);
    const tot = Number(lastChallengeStatus?.total || lastChallengeStatus?.progress_total || 0);
    lastChallengeStatus = {
      ...(lastChallengeStatus || {}),
      active: false,
      running: false,
      queued: false,
      phase: "cancelled",
      message:
        tot > 0
          ? `Cancelled after ${idx}/${tot} challenges — remaining were not applied.`
          : "Cancelled.",
      _optimistic: false,
    };
    challengeOptimisticUntil = 0;
    challengeCancelHoldUntil = Date.now() + 8000;
    challengeCompleteShownUntil = Date.now() + 1500;
    challengeDisplayMilestone = 0;
    lastProgressHtml = "";
    renderProgressPanel(null, null, null);
    // Fire cancel even if runAction is busy — dedicated bridge call.
    if (actionBusy) {
      window.sqbt
        ?.postAction?.("challenge_bulk_cancel", {}, 8)
        ?.then((res) => {
          const ch = normalizeChallengeStatus(res?.data?.challenge);
          if (ch) {
            lastChallengeStatus = {
              ...ch,
              active: false,
              running: false,
              queued: false,
              phase: "cancelled",
            };
          }
          challengeCancelHoldUntil = Date.now() + 2000;
          lastProgressHtml = "";
          renderProgressPanel(null, null, null);
          startProgressPoll();
        })
        ?.catch(() => {
          startProgressPoll();
        });
      return;
    }
    runAction("challenge_bulk_cancel", {}, "", {
      sectionId: "progression:challenges",
      actionDef: { action: "challenge_bulk_cancel", label: "Stop challenges" },
    });
    return;
  }
  const uvhmStop = event.target?.closest?.("[data-uvhm-stop]");
  if (uvhmStop) {
    event.preventDefault();
    event.stopPropagation();
    if (!actionsEnabled()) return;
    lastUvhmStatus = {
      ...(lastUvhmStatus || {}),
      active: false,
      running: false,
      queued: false,
      phase: "cancelled",
      message: "UVHM cancelled.",
    };
    uvhmCompleteDismissed = false;
    uvhmCancelHoldUntil = Date.now() + 8000;
    uvhmErrorShownUntil = Date.now() + 1500;
    uvhmBusyGraceUntil = 0;
    lastProgressHtml = "";
    renderProgressPanel(null, null, null);
    if (actionBusy) {
      window.sqbt
        ?.postAction?.("uvhm_cancel", {}, 8)
        ?.then((res) => {
          const uv = res?.data?.uvhm;
          if (uv && typeof uv === "object") {
            lastUvhmStatus = {
              ...uv,
              active: false,
              running: false,
              queued: false,
              phase: "cancelled",
            };
          }
          uvhmCancelHoldUntil = Date.now() + 2000;
          lastProgressHtml = "";
          renderProgressPanel(null, null, null);
          startProgressPoll();
        })
        ?.catch(() => {
          startProgressPoll();
        });
      return;
    }
    runAction("uvhm_cancel", {}, "", {
      sectionId: "progression:uvhm",
      actionDef: { action: "uvhm_cancel", label: "Stop UVHM" },
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
  const missionStop = event.target?.closest?.("[data-mission-stop]");
  if (missionStop) {
    event.preventDefault();
    event.stopPropagation();
    if (!actionsEnabled() || actionBusy) return;
    lastMissionStatus = null;
    runAction("mission_cancel", {}, "", {
      sectionId: "progression:Missions",
      actionDef: { action: "mission_cancel", label: "Cancel missions" },
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
if (tabContent) {
  const armEdit = (event) => {
    const t = event.target;
    if (t?.matches?.("input, textarea, select") || t?.isContentEditable) markUserEditing(6000);
  };
  tabContent.addEventListener("focusin", armEdit, true);
  tabContent.addEventListener("keydown", armEdit, true);
  // mousedown fires before focus — block remounts that steal the click.
  tabContent.addEventListener("mousedown", armEdit, true);
}
document.addEventListener(
  "mousedown",
  (event) => {
    const t = event.target;
    if (t?.matches?.("input, textarea, select") || t?.isContentEditable) markUserEditing(6000);
  },
  true
);
loadSetup();
window.sqbt.getStatus().then(async (status) => {
  setStatusUi(status);
  // Do not auto-enter offline browse on startup — Ctrl+Alt+Shift+F9 only.
});
loadManifest({ allowOffline: false });
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
