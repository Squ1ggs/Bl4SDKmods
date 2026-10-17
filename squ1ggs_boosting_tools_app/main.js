"use strict";

const path = require("path");
const { app, BrowserWindow, dialog, ipcMain, shell, screen, protocol } = require("electron");
const { registerNativeCardSchemes, installNativeCardProtocol } = require("./native_card_protocol");
const { getBridgeStatus, postAction, fetchManifest, fetchCatalog, getBridgeBase } = require("./lib/bridge");
const {
  loadFavorites,
  toggleFavorite,
  bucketForCatalog,
} = require("./lib/list_favorites");
const { defaultGameRootHint, defaultInstallCandidates, normalizeGameRoot, resolveGameRoot } = require("./lib/game_paths");
const { ensureModSynced, getModSyncStatus, installSdkmod, isBorderlandsRunning } = require("./lib/sdkmod_install");
const { checkBaseSdkUpdate, detectBaseSdk, installBaseSdk } = require("./lib/oak2_sdk");
const { loadSettings, saveSettings, normalizeTheme, normalizeLocale, readHiddenShapesUnlocked } = require("./lib/app_settings");
const { checkForUpdates, compareVersions, normalizeVersion } = require("./lib/update_check");
const { applyGithubUpdate } = require("./lib/github_update");
const { readSerialSource } = require("./lib/serial_sources");
const { scanLatestSave, listCandidateSaves, saveGamesRoot } = require("./lib/bl4_save_bay");

// Privileged Cohtml card schemes must be registered before app ready.
registerNativeCardSchemes(protocol);

let mainWindow = null;
let refreshTimer = null;
let lastBridgeConnected = false;
const STATUS_POLL_CONNECTED_MS = 5000;
const STATUS_POLL_DISCONNECTED_MS = 1000;
let storedGameRoot = null;
let storedTheme = "default";
let storedLocale = "en";
let storedHiddenShapes = false;
let storedGhostOpacity = 1;
let settingsMode = "appdata";
let settingsPath = null;
let updateCache = null;
let updateCheckedAt = 0;
let quittingAfterRestore = false;
let lastModSync = null;
const UPDATE_CACHE_MS = 15 * 60 * 1000;

function runAutoModSync(options = {}) {
  try {
    lastModSync = ensureModSynced({
      gameRoot: options.gameRoot !== undefined ? options.gameRoot : storedGameRoot || undefined,
      force: Boolean(options.force),
    });
    if (lastModSync?.ok && lastModSync.gameRoot) {
      storedGameRoot = lastModSync.gameRoot;
      persistStoredSettings();
    }
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("sqbt:mod-sync", lastModSync);
    }
    return lastModSync;
  } catch (error) {
    lastModSync = {
      ok: false,
      skipped: false,
      updated: false,
      message: `Auto mod sync failed: ${String(error?.message || error)}`,
    };
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("sqbt:mod-sync", lastModSync);
    }
    return lastModSync;
  }
}

function normalizeGhostOpacity(value, fallback = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  // Keep usable: too clear and clicks become confusing.
  return Math.max(0.55, Math.min(1, n));
}

function applyStoredSettings(state) {
  storedGameRoot = state?.gameRoot || null;
  storedTheme = normalizeTheme(state?.theme);
  storedLocale = normalizeLocale(state?.locale);
  storedHiddenShapes = Boolean(state?.hiddenShapes) || readHiddenShapesUnlocked();
  storedGhostOpacity = normalizeGhostOpacity(state?.ghostOpacity, 1);
  settingsMode = state?.settingsMode || "appdata";
  settingsPath = state?.settingsPath || null;
}

function loadStoredSettings() {
  applyStoredSettings(loadSettings(app));
}

function persistStoredSettings(extra = {}) {
  const saved = saveSettings(app, {
    gameRoot: storedGameRoot,
    theme: storedTheme,
    locale: storedLocale,
    hiddenShapes: storedHiddenShapes,
    ghostOpacity: storedGhostOpacity,
    ...extra,
  });
  settingsMode = saved.mode;
  settingsPath = saved.path;
  if (extra.theme !== undefined) {
    storedTheme = normalizeTheme(extra.theme);
  }
  if (extra.locale !== undefined) {
    storedLocale = normalizeLocale(extra.locale);
  }
  if (extra.hiddenShapes !== undefined) {
    storedHiddenShapes = Boolean(extra.hiddenShapes);
  }
  if (extra.ghostOpacity !== undefined) {
    storedGhostOpacity = normalizeGhostOpacity(extra.ghostOpacity, storedGhostOpacity);
  }
}

function applyWindowGhostOpacity(opacity) {
  storedGhostOpacity = normalizeGhostOpacity(opacity, storedGhostOpacity);
  if (mainWindow && !mainWindow.isDestroyed()) {
    try {
      mainWindow.setOpacity(storedGhostOpacity);
    } catch {
      /* Linux no-op */
    }
  }
  return storedGhostOpacity;
}

function createWindow() {
  const iconPath = path.join(__dirname, "build", "icon.png");
  const windowOptions = {
    width: 1280,
    height: 900,
    minWidth: 640,
    minHeight: 480,
    resizable: true,
    maximizable: true,
    title: "Squ1ggs Boosting Tools",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  };
  try {
    const fs = require("fs");
    if (fs.existsSync(iconPath)) {
      windowOptions.icon = iconPath;
    }
  } catch {
    /* optional branding asset */
  }

  mainWindow = new BrowserWindow(windowOptions);
  try {
    mainWindow.setOpacity(normalizeGhostOpacity(storedGhostOpacity, 1));
  } catch {
    /* optional */
  }

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
}

function pushStatus(payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("bridge-status", payload);
  }
}

async function refreshStatus() {
  const status = await getBridgeStatus();
  const connected = Boolean(status?.connected);
  if (connected !== lastBridgeConnected) {
    lastBridgeConnected = connected;
    // Re-arm interval: probe every 1s until Online, then back off to 5s.
    startAutoRefresh();
  }
  pushStatus(status);
  return status;
}

async function getUpdateStatus(force = false, currentModVersion = "") {
  const now = Date.now();
  const liveMod = normalizeVersion(currentModVersion) || String(currentModVersion || "").trim();
  // Disk / bundled versions win over a stale live bridge reading — otherwise Install
  // finishes, then the banner immediately says outdated until Borderlands restarts.
  let sync = null;
  try {
    sync = getModSyncStatus(storedGameRoot);
  } catch {
    sync = null;
  }
  const diskMod = normalizeVersion(sync?.installedVersion) || "";
  const bundledMod = normalizeVersion(sync?.bundledVersion) || "";
  let effectiveMod = liveMod;
  for (const candidate of [diskMod, bundledMod]) {
    if (!candidate) continue;
    if (!effectiveMod || compareVersions(candidate, effectiveMod) > 0) {
      effectiveMod = candidate;
    }
  }
  const modKey = effectiveMod;
  if (
    !force &&
    updateCache &&
    now - updateCheckedAt < UPDATE_CACHE_MS &&
    String(updateCache.checkedModVersion || "") === modKey &&
    String(updateCache.liveModVersion || "") === liveMod
  ) {
    return updateCache;
  }
  try {
    updateCache = await checkForUpdates({
      currentVersion: app.getVersion(),
      currentModVersion: modKey,
    });
    updateCache.checkedModVersion = modKey;
    updateCache.liveModVersion = liveMod;
    updateCache.diskModVersion = diskMod;
    updateCache.bundledModVersion = bundledMod;
    updateCache.needsGameRestartForMod = Boolean(
      liveMod && diskMod && compareVersions(diskMod, liveMod) > 0
    );
  } catch (error) {
    updateCache = {
      ok: false,
      updateAvailable: false,
      currentVersion: app.getVersion(),
      currentModVersion: modKey,
      checkedModVersion: modKey,
      liveModVersion: liveMod,
      diskModVersion: diskMod,
      bundledModVersion: bundledMod,
      needsGameRestartForMod: false,
      message: String(error?.message || error),
    };
  }
  updateCheckedAt = now;
  return updateCache;
}

function startAutoRefresh() {
  stopAutoRefresh();
  const gap = lastBridgeConnected ? STATUS_POLL_CONNECTED_MS : STATUS_POLL_DISCONNECTED_MS;
  refreshTimer = setInterval(() => {
    refreshStatus().catch(() => {});
  }, gap);
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

function resolveNativeCardUiRoot() {
  const fs = require("fs");
  const candidates = [
    path.join(__dirname, "native_card_ui"),
    path.join(process.resourcesPath || "", "native_card_ui"),
  ];
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(path.join(candidate, "manifest.json"))) {
      return candidate;
    }
  }
  return candidates[0];
}

app.whenReady().then(() => {
  installNativeCardProtocol(protocol, resolveNativeCardUiRoot());
  loadStoredSettings();
  runAutoModSync();
  createWindow();
  startAutoRefresh();
  refreshStatus().catch(() => {});

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
      refreshStatus().catch(() => {});
    }
  });
});

app.on("window-all-closed", () => {
  stopAutoRefresh();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", (event) => {
  if (quittingAfterRestore) {
    return;
  }
  event.preventDefault();
  stopAutoRefresh();
  postAction("desktop_session_end", {}, 4)
    .catch(() => {})
    .finally(() => {
      quittingAfterRestore = true;
      app.quit();
    });
});

ipcMain.handle("sqbt:get-status", async () => refreshStatus());
ipcMain.handle("sqbt:analyze-item", async (_event, serial, hints) => {
  try {
    const { analyzeItem } = require("./lib/item_analysis");
    return await analyzeItem(serial, hints || {});
  } catch (error) {
    return {
      ok: false,
      exact: false,
      serial: "",
      error: String(error && error.message ? error.message : error),
      unknowns: ["analysis"],
      conflicts: [],
    };
  }
});
ipcMain.handle("sqbt:nexus-card-stats", async (_event, props) => {
  try {
    const { evaluateNexusCardStats, nexusStatus } = require("./lib/nexus_card_stats");
    const { prepareClassmodCardModel, inlineSqbtAssetUrls } = require("./native_card_protocol");
    const { lookupExactNcsCard } = require("./lib/ncs_lookup_card");
    const { labelSerialOffline } = require("./lib/offline_serial_card");
    const incoming = props && typeof props === "object" ? { ...props } : {};
    // NCS Lookup often returns classmod chrome with +% secondary and no skill
    // glyphs. Decode @U → part_names offline (no game bridge) so Nexus can paint
    // ClassModPassivesAspect skills even when bay_label_serials is unavailable.
    const serialKey = String(incoming.serial || "").trim();
    const hadParts = Array.isArray(incoming.part_names) && incoming.part_names.length >= 4;
    if (serialKey.startsWith("@U") && !hadParts) {
      const labeled = labelSerialOffline(serialKey);
      if (labeled && typeof labeled === "object") {
        if (Array.isArray(labeled.part_names) && labeled.part_names.length) {
          incoming.part_names = labeled.part_names;
        }
        if (Array.isArray(labeled.perk_rows) && labeled.perk_rows.length && !incoming.perk_rows?.length) {
          incoming.perk_rows = labeled.perk_rows;
        }
        if (!incoming.itemType && !incoming.type_label && labeled.item_type) {
          incoming.itemType = labeled.item_type;
          incoming.type_label = labeled.item_type;
        }
        if (!incoming.set && labeled.set) incoming.set = labeled.set;
        if (!incoming.display_name && labeled.display_name) {
          incoming.display_name = labeled.display_name;
        }
        if (!incoming.rarity && labeled.rarity) incoming.rarity = labeled.rarity;
      }
    }
    const exact = await lookupExactNcsCard(serialKey);
    const status = nexusStatus();
    if (!status.ok && !exact) {
      return { ok: false, stats: [], source: "none", error: status.error || "nexus_unavailable" };
    }
    const offline = status.ok ? evaluateNexusCardStats(incoming) : null;
    const uiLevel = Number(incoming.level);
    const ncsLevel = Number(exact?.raw?.level);
    const levelMismatch =
      Number.isFinite(uiLevel) &&
      uiLevel > 0 &&
      Number.isFinite(ncsLevel) &&
      Math.abs(uiLevel - ncsLevel) >= 1;
    const typeBlob = [
      incoming.itemType,
      incoming.type_label,
      incoming.type,
      exact?.raw?.item_type,
      offline?.raw?.item_type,
      ...(Array.isArray(incoming.part_names) ? incoming.part_names : []),
    ]
      .map((v) => String(v || ""))
      .join(" ");
    const isClassmod =
      /class\s*mod|classmod/i.test(typeBlob) ||
      (/classmod_/i.test(typeBlob) && !/\.(?:part_barrel|part_grip|part_mag)_/i.test(typeBlob)) ||
      (/passive_(?:blue|green|red)/i.test(typeBlob) &&
        !/\.(?:part_barrel|part_grip|part_mag)_/i.test(typeBlob));
    // Editor equipment + pearl weapon dual ({21:90} etc.) must not paint as a gun.
    const isNonGunEquipment =
      isClassmod ||
      /enhancement|shield|repkit|repair\s*kit|ordnance|grenade|gadget/i.test(typeBlob);
    // Pearl rarity hooks ({7:54} TED_SG / {21:90} Juliet) can make NCS/exact resolve as a gun.
    // Never paint a shotgun/SMG card when the serial/parts are equipment.
    const exactLooksGun = /pistol|shotgun|assault|smg|submachine|sniper|heavy/i.test(
      String(exact?.raw?.item_type || exact?.native_equipment?.type_label || "")
    );
    const primaryIconCount = (card) => {
      const rows = card?.native_equipment?.groups?.primary;
      if (!Array.isArray(rows)) return 0;
      return rows.filter((row) => String(row?.image || "").trim()).length;
    };
    const offlineDamage = Number(offline?.raw?.damage);
    const offlineHasDamage = Number.isFinite(offlineDamage) && offlineDamage > 0;
    const exactDamage = Number(exact?.raw?.damage);
    const exactHasDamage = Number.isFinite(exactDamage) && exactDamage > 0;
    // Exact NCS cards are baked to the serial's stored level, and classmod cards
    // often ship with no primary skill icons (text/secondary only). Prefer offline
    // Nexus only when the preview level disagrees or exact under-paints — never
    // discard a level-matched exact card (Ammo / Fire Rate / Reload match in-game).
    const exactClassmodWeak = isClassmod && primaryIconCount(exact) < 1;
    const offlineClassmodStrong = isClassmod && primaryIconCount(offline) > primaryIconCount(exact);
    const preferOffline =
      offline &&
      (offline.ok || (Array.isArray(offline.stats) && offline.stats.length) || offlineHasDamage) &&
      (!exact ||
        levelMismatch ||
        exactClassmodWeak ||
        offlineClassmodStrong ||
        (isNonGunEquipment && exactLooksGun) ||
        (offlineHasDamage && !exactHasDamage));
    let result = exact || offline;
    // Pearl rarity hooks can make exact NCS look like a gun — prefer offline
    // equipment chrome when it actually painted (icons / ok / stats), never empty.
    if (
      isNonGunEquipment &&
      exactLooksGun &&
      offline &&
      (offline.ok ||
        primaryIconCount(offline) > 0 ||
        (Array.isArray(offline.stats) && offline.stats.length))
    ) {
      result = offline;
    } else if (preferOffline) {
      result = offline;
      // Keep exact chrome (red text / flavor) when offline is thin.
      if (exact) {
        if (!(result.red_text || []).length && (exact.red_text || []).length) {
          result = { ...result, red_text: exact.red_text };
        }
        if (!(result.native_text || []).length && (exact.native_text || []).length) {
          result = { ...result, native_text: exact.native_text };
        }
          // Keep NCS +% / universal rows under offline skill glyphs.
          const exactSec = exact.native_equipment?.groups?.secondary;
          if (
            isClassmod &&
            Array.isArray(exactSec) &&
            exactSec.length &&
            result.native_equipment?.groups
          ) {
            const groups = { ...result.native_equipment.groups };
            const ownSec = Array.isArray(groups.secondary) ? groups.secondary : [];
            const mergedSec = [...ownSec, ...exactSec];
            groups.secondary = mergedSec;
            const mergedNativeSec = [
              ...(Array.isArray(result.native_secondary) ? result.native_secondary : []),
              ...(Array.isArray(exact.native_secondary) ? exact.native_secondary : []),
            ];
            result = {
              ...result,
              native_equipment: { ...result.native_equipment, groups },
              native_secondary: mergedNativeSec,
            };
          }
        if (result.raw && exact.raw) {
          result = {
            ...result,
            raw: {
              ...result.raw,
              red_text: result.red_text || result.raw.red_text,
              native_text: result.native_text || result.raw.native_text,
              native_equipment: result.native_equipment,
            },
          };
        }
      }
    } else if (exact && offlineHasDamage) {
      // Level-matched exact keeps Ammo / Fire Rate / Reload. Damage + DPS come
      // from offline Nexus so WeaponType_Init Damage_Scale is not double-counted
      // the way NCS Lookup currently overshoots live cards.
      const offlineGroups = offline.native_groups || offline.raw?.native_groups || {};
      const exactGroups =
        exact.native_groups && typeof exact.native_groups === "object"
          ? { ...exact.native_groups }
          : {};
      const isDamageRow = (row) =>
        /^(damage|dps)$/i.test(String(row?.label || row?.loc_text || "").trim()) ||
        /damage/i.test(String(row?.ident || ""));
      if (Array.isArray(exactGroups.primary) && Array.isArray(offlineGroups.primary)) {
        const offlineDamageRows = offlineGroups.primary.filter(isDamageRow);
        if (offlineDamageRows.length) {
          exactGroups.primary = [
            ...offlineDamageRows,
            ...exactGroups.primary.filter((row) => !isDamageRow(row)),
          ];
        }
      }
      if (Array.isArray(offlineGroups.headline) && offlineGroups.headline.length) {
        exactGroups.headline = offlineGroups.headline;
      }
      const offlineDps = Number(offline.raw?.dps);
      const offlineDmg = Number(offline.raw?.damage);
      result = {
        ...exact,
        source: exact.source || "ncs_lookup_exact",
        native_groups: exactGroups,
        stats: Array.isArray(exact.stats)
          ? exact.stats.map((row) => {
              if (/^damage$/i.test(String(row?.label || "").trim()) && Number.isFinite(offlineDmg) && offlineDmg > 0) {
                return { ...row, value: String(Math.round(offlineDmg)) };
              }
              if (/^dps$/i.test(String(row?.label || "").trim()) && Number.isFinite(offlineDps) && offlineDps > 0) {
                return { ...row, value: String(Math.round(offlineDps)) };
              }
              return row;
            })
          : exact.stats,
        raw: {
          ...(exact.raw || {}),
          damage: Number.isFinite(offlineDmg) && offlineDmg > 0 ? offlineDmg : exact.raw?.damage,
          dps: Number.isFinite(offlineDps) && offlineDps > 0 ? offlineDps : exact.raw?.dps,
          damage_per_projectile:
            offline.raw?.damage_per_projectile ?? exact.raw?.damage_per_projectile,
          native_groups: exactGroups,
        },
      };
    } else if (exact && levelMismatch) {
      // Never paint baked L1–30 Damage under a different preview level when
      // offline could not resolve yet — strip numeric Damage so the renderer
      // can estimate / enrich at the UI level.
      const stripDamageRows = (rows) =>
        (Array.isArray(rows) ? rows : []).filter(
          (row) => !/^(damage|dps)$/i.test(String(row?.label || row?.loc_text || "").trim())
        );
      const groups = exact.native_groups && typeof exact.native_groups === "object" ? { ...exact.native_groups } : {};
      if (groups.primary) groups.primary = stripDamageRows(groups.primary);
      result = {
        ...exact,
        source: "ncs_lookup_exact_level_mismatch",
        stats: stripDamageRows(exact.stats),
        native_groups: groups,
        raw: {
          ...(exact.raw || {}),
          damage: null,
          dps: null,
          level: Number.isFinite(uiLevel) ? uiLevel : exact.raw?.level,
          native_groups: groups,
        },
      };
    }
    // Exact NCS cards hardcode empty firmware. When we keep exact for Ammo/FR/Reload
    // (Damage already patched above), restore offline firmware widget + rows.
    if (result && offline && result !== offline) {
      const exactHasFirmware =
        !!(result.firmware_block && result.firmware_block.firmwareident) ||
        (Array.isArray(result.native_firmware) && result.native_firmware.length > 0) ||
        (Array.isArray(result.native_equipment?.groups?.firmware) &&
          result.native_equipment.groups.firmware.length > 0);
      if (!exactHasFirmware) {
        const offlineFwBlock =
          offline.firmware_block || offline.raw?.firmware_block || null;
        const offlineFwRows =
          (Array.isArray(offline.native_firmware) && offline.native_firmware.length
            ? offline.native_firmware
            : null) ||
          (Array.isArray(offline.raw?.native_firmware) && offline.raw.native_firmware.length
            ? offline.raw.native_firmware
            : null) ||
          (Array.isArray(offline.native_equipment?.groups?.firmware)
            ? offline.native_equipment.groups.firmware
            : null);
        if (offlineFwBlock?.firmwareident || (offlineFwRows && offlineFwRows.length)) {
          result = {
            ...result,
            firmware_block: offlineFwBlock?.firmwareident
              ? offlineFwBlock
              : result.firmware_block,
            native_firmware: offlineFwRows || result.native_firmware,
          };
          if (
            result.native_equipment?.groups &&
            Array.isArray(offline.native_equipment?.groups?.firmware) &&
            offline.native_equipment.groups.firmware.length
          ) {
            result = {
              ...result,
              native_equipment: {
                ...result.native_equipment,
                groups: {
                  ...result.native_equipment.groups,
                  firmware: offline.native_equipment.groups.firmware,
                },
              },
            };
          }
          if (result.raw && typeof result.raw === "object") {
            result = {
              ...result,
              raw: {
                ...result.raw,
                firmware_block: result.firmware_block,
                native_firmware: result.native_firmware,
                native_equipment: result.native_equipment || result.raw.native_equipment,
              },
            };
          }
        }
      }
    }
    if (result && result.native_equipment) {
      result.native_equipment = inlineSqbtAssetUrls(result.native_equipment);
      const painted = prepareClassmodCardModel({
        primary_stat_entries: result.native_equipment.groups?.primary || [],
      });
      if (result.native_equipment.groups && painted.primary_stat_entries) {
        result.native_equipment.groups.primary = painted.primary_stat_entries;
      }
    }
    if (result && result.raw && result.raw.native_equipment) {
      result.raw.native_equipment = result.native_equipment;
    }
    // Exact NCS name wins for normal cards. Pearl-hooked equipment can resolve as a
    // gun named Juliet/Firewerks/Eigenburst — keep the offline equipment title then.
    const exactName = String(exact?.display_name || exact?.raw?.display_name || "").trim();
    const offlineName = String(
      incoming.display_name ||
        incoming.title ||
        result?.display_name ||
        result?.raw?.display_name ||
        ""
    ).trim();
    const keepOfflineEquipmentName =
      isNonGunEquipment &&
      exactLooksGun &&
      offlineName &&
      !/^@U/i.test(offlineName) &&
      !/get\s*throwin|action\s*fist|goojfc|high\s*caliber/i.test(offlineName);
    if (result && exactName && !/^@U/i.test(exactName)) {
      if (!keepOfflineEquipmentName) {
        result = { ...result, display_name: exactName };
        if (result.raw && typeof result.raw === "object") {
          result = {
            ...result,
            raw: { ...result.raw, display_name: exactName },
          };
        }
      } else {
        result = { ...result, display_name: offlineName };
        if (result.raw && typeof result.raw === "object") {
          result = {
            ...result,
            raw: { ...result.raw, display_name: offlineName },
          };
        }
      }
    } else if (result && !result.display_name && offlineName) {
      result = { ...result, display_name: offlineName };
    }
    // Full in-game name (prefixes + title) from the offline naming rules beats bare titles.
    const fullName = String(itemFullNameCache.get(serialKey) || offline?.full_name || "").trim();
    if (result && fullName) {
      result = {
        ...result,
        display_name: fullName,
        full_name: fullName,
        raw: result.raw && typeof result.raw === "object"
          ? { ...result.raw, display_name: fullName, full_name: fullName }
          : result.raw,
      };
    }
    // Force Editor equipment type when pearl dual made NCS/exact report a gun.
    if (result && isNonGunEquipment && exactLooksGun) {
      const forcedType = String(
        incoming.type_label ||
          incoming.itemType ||
          offline?.raw?.item_type ||
          (isClassmod ? "Classmod" : "")
      ).trim();
      if (
        forcedType &&
        !/pistol|shotgun|assault|smg|submachine|sniper|heavy/i.test(forcedType)
      ) {
        const rawType = /class/i.test(forcedType) ? "Classmod" : forcedType;
        const forcedLabel =
          rawType === "Classmod" || /class/i.test(forcedType) ? "Class Mod" : forcedType;
        result = {
          ...result,
          raw: {
            ...(result.raw || {}),
            item_type: rawType,
            display_name: result.display_name || result.raw?.display_name,
          },
        };
        if (result.native_equipment && typeof result.native_equipment === "object") {
          result = {
            ...result,
            native_equipment: {
              ...result.native_equipment,
              type_label: forcedLabel,
            },
          };
        }
      }
    }
    return result;
  } catch (error) {
    return {
      ok: false,
      stats: [],
      source: "none",
      error: String(error && error.message ? error.message : error),
    };
  }
});
ipcMain.handle("sqbt:inline-card-assets", async (_event, model) => {
  try {
    const { prepareClassmodCardModel } = require("./native_card_protocol");
    return { ok: true, model: prepareClassmodCardModel(model || {}) };
  } catch (error) {
    return {
      ok: false,
      model: model || {},
      error: String(error && error.message ? error.message : error),
    };
  }
});
ipcMain.handle("sqbt:get-list-favorites", async () => ({
  ok: true,
  favorites: loadFavorites(),
}));
ipcMain.handle("sqbt:toggle-list-favorite", async (_event, bucket, id) => {
  const favorites = toggleFavorite(bucket, id);
  return { ok: true, favorites, bucket: bucketForCatalog(bucket) || bucket };
});
ipcMain.handle("sqbt:check-for-updates", async (_event, force, currentModVersion) =>
  getUpdateStatus(Boolean(force), currentModVersion || "")
);
const releaseActions = new Set(require("./lib/release_actions.json"));
const releaseSchema = require("./renderer/release_ui_schema.js");
const restrictReleaseManifest = require("./renderer/release_manifest_guard.js");
ipcMain.handle("sqbt:post-action", async (_event, action, payload, timeout) => {
  if (!releaseActions.has(String(action || ""))) return { data: { ok: false, message: "This action is unavailable in this build." } };
  try {
    const result = await postAction(action, payload || {}, timeout ?? 12);
    const name = String(action || "");
    // Status-only polls must not rebuild the whole UI (dropdown flicker during UVHM).
    const skipStatusRefresh =
      name === "uvhm_status" ||
      name === "challenge_bulk_status" ||
      name === "spawn_item_pool_status" ||
      name === "loot_vacuum_status";
    if (!skipStatusRefresh) {
      await refreshStatus().catch(() => {});
    }
    return result;
  } catch (error) {
    return {
      httpStatus: 0,
      data: {
        ok: false,
        message: String(error?.message || error),
      },
    };
  }
});
ipcMain.handle("sqbt:get-manifest", async () => {
  try {
    return { ok: true, manifest: restrictReleaseManifest(await fetchManifest(), releaseSchema) };
  } catch (error) {
    return { ok: false, message: String(error) };
  }
});
ipcMain.handle("sqbt:get-offline-manifest", async () => {
  try {
    const fs = require("fs");
    const candidates = [
      path.join(__dirname, "renderer", "offline_manifest.json"),
      path.join(app.getAppPath(), "renderer", "offline_manifest.json"),
    ];
    for (const file of candidates) {
      if (!fs.existsSync(file)) continue;
      const manifest = JSON.parse(fs.readFileSync(file, "utf8"));
      if (manifest && Array.isArray(manifest.tabs) && manifest.tabs.length) {
        return { ok: true, manifest, source: file };
      }
    }
    return { ok: false, message: "No offline_manifest.json (run npm run sync:sdkmod)." };
  } catch (error) {
    return { ok: false, message: String(error?.message || error) };
  }
});
/** @type {Map<string, string>} serial → full in-game name ("" when no title resolves). */
const itemFullNameCache = new Map();

/** Item lists: full names (prefixes + title) from each row's decoded parts, spread over polls. */
function attachSerialStoreFullNames(data) {
  const rows = Array.isArray(data?.rows) ? data.rows : null;
  if (!rows) return data;
  let evaluate;
  const started = Date.now();
  let pending = 0;
  for (const row of rows) {
    const serial = String(row?.serial || "").trim();
    const parts = Array.isArray(row?.name_parts) ? row.name_parts : null;
    delete row.name_parts;
    if (!serial || row.broken) continue;
    if (itemFullNameCache.has(serial)) {
      const hit = itemFullNameCache.get(serial);
      if (hit) row.full_name = hit;
      continue;
    }
    if (!parts || !parts.length || !row.set) continue;
    if (evaluate === undefined) {
      try {
        const mod = require("./lib/nexus_card_stats");
        evaluate = mod.nexusStatus().ok ? mod.evaluateNexusCardStats : null;
      } catch {
        evaluate = null;
      }
    }
    if (!evaluate) continue;
    if (Date.now() - started > 400) {
      pending += 1;
      continue;
    }
    let name = "";
    try {
      const res = evaluate({
        part_names: parts,
        itemType: row.item_type || row.type || "",
        set: row.set,
        rarity: row.rarity || "",
        level: Number(row.level) || 50,
        display_name: row.display_name || "",
      });
      name = String(res?.full_name || "").trim();
    } catch {
      name = "";
    }
    itemFullNameCache.set(serial, name);
    if (name) row.full_name = name;
  }
  if (itemFullNameCache.size > 20000) itemFullNameCache.clear();
  if (pending) data.names_pending = Number(data.names_pending || 0) + pending;
  return data;
}

ipcMain.handle("sqbt:get-catalog", async (_event, name, payload) => {
  try {
    const data = await fetchCatalog(name, payload || {});
    return { ok: true, data: name === "serial_store" ? attachSerialStoreFullNames(data) : data };
  } catch (error) {
    return { ok: false, message: String(error) };
  }
});
ipcMain.handle("sqbt:get-setup", async () => {
  const candidates = defaultInstallCandidates();
  const gameRoot = resolveGameRoot(storedGameRoot);
  const pathSource = storedGameRoot ? "stored" : gameRoot ? "detected" : "none";
  let baseSdk = detectBaseSdk(gameRoot);
  try {
    baseSdk = await checkBaseSdkUpdate(gameRoot);
  } catch {
    /* keep local detect */
  }
  return {
    bridgeUrl: getBridgeBase(),
    gameRoot,
    defaultGameRoot: defaultGameRootHint(),
    candidates,
    storedGameRoot,
    pathSource,
    setupDismissed: Boolean(loadSettings(app).setupDismissed),
    theme: storedTheme,
    locale: storedLocale,
    hiddenShapes: storedHiddenShapes,
    ghostOpacity: storedGhostOpacity,
    settingsMode,
    settingsPath,
    isPackaged: app.isPackaged,
    baseSdk,
    modSync: lastModSync || getModSyncStatus(gameRoot || storedGameRoot),
  };
});
ipcMain.handle("sqbt:dismiss-setup", async () => {
  persistStoredSettings({ setupDismissed: true });
  return { ok: true };
});
ipcMain.handle("sqbt:set-theme", async (_event, theme) => {
  storedTheme = normalizeTheme(theme);
  persistStoredSettings({ theme: storedTheme });
  return { ok: true, theme: storedTheme };
});
ipcMain.handle("sqbt:set-ghost-opacity", async (_event, opacity) => {
  const next = applyWindowGhostOpacity(opacity);
  persistStoredSettings({ ghostOpacity: next });
  return { ok: true, ghostOpacity: next };
});
ipcMain.handle("sqbt:get-ghost-opacity", async () => ({
  ok: true,
  ghostOpacity: storedGhostOpacity,
}));
ipcMain.handle("sqbt:pack-bay-scan", async (_event, payload = {}) => {
  try {
    return scanLatestSave(payload || {});
  } catch (error) {
    return {
      ok: false,
      message: String(error?.message || error),
      rows: [],
      saveRoot: saveGamesRoot(),
    };
  }
});
ipcMain.handle("sqbt:pack-bay-list-saves", async () => {
  try {
    const rows = listCandidateSaves().slice(0, 24);
    return { ok: true, rows, saveRoot: saveGamesRoot() };
  } catch (error) {
    return { ok: false, message: String(error?.message || error), rows: [], saveRoot: saveGamesRoot() };
  }
});
ipcMain.handle("sqbt:set-locale", async (_event, locale) => {
  storedLocale = normalizeLocale(locale);
  persistStoredSettings({ locale: storedLocale });
  return { ok: true, locale: storedLocale };
});
ipcMain.handle("sqbt:unlock-hidden-shapes", async () => {
  storedHiddenShapes = true;
  persistStoredSettings({ hiddenShapes: true });
  return { ok: true, hiddenShapes: true };
});
ipcMain.handle("sqbt:read-serial-source", async (_event, rawPath) => readSerialSource(rawPath));
ipcMain.handle("sqbt:pick-serial-file", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select a serial list (.txt / .yaml / .json / .docx)",
    properties: ["openFile"],
    filters: [
      { name: "Serial lists", extensions: ["txt", "yaml", "yml", "json", "docx", "csv", "md", "log"] },
      { name: "All files", extensions: ["*"] },
    ],
  });
  if (result.canceled || !result.filePaths?.length) {
    return { ok: false, cancelled: true };
  }
  return readSerialSource(result.filePaths[0]);
});
ipcMain.handle("sqbt:pick-item-image", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Choose an item picture",
    properties: ["openFile"],
    filters: [{ name: "Item pictures", extensions: ["png", "jpg", "jpeg", "webp"] }],
  });
  if (result.canceled || !result.filePaths?.length) return { ok: false, cancelled: true };
  try {
    const { identifyImageFile } = require("./lib/image_item_match");
    return await identifyImageFile(result.filePaths[0]);
  } catch (error) {
    return { ok: false, message: String(error?.message || error) };
  }
});
ipcMain.handle("sqbt:identify-item-image", async (_event, payload = {}) => {
  try {
    const base64 = String(payload?.base64 || "").replace(/^data:[^,]*,/, "");
    if (!base64 || base64.length > 18 * 1024 * 1024) {
      return { ok: false, message: "Image payload is empty or too large." };
    }
    const buffer = Buffer.from(base64, "base64");
    const { identifyImageBuffer } = require("./lib/image_item_match");
    return await identifyImageBuffer(buffer, String(payload?.mime || ""));
  } catch (error) {
    return { ok: false, message: String(error?.message || error) };
  }
});
ipcMain.handle("sqbt:rank-item-image", async (_event, extracted, rows) => {
  try {
    const { rankCandidates } = require("./lib/image_item_match");
    return { ok: true, rows: rankCandidates(extracted || {}, rows || []) };
  } catch (error) {
    return { ok: false, message: String(error?.message || error), rows: [] };
  }
});

async function pickAndSaveGameFolder() {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select Borderlands 4 install folder (contains Borderlands4.exe / OakGame)",
    defaultPath: defaultGameRootHint(),
    properties: ["openDirectory"],
  });
  if (result.canceled || !result.filePaths?.length) {
    return { ok: false, cancelled: true };
  }
  const selectedRoot = normalizeGameRoot(result.filePaths[0]);
  if (!selectedRoot) return {
    ok: false,
    message: "Choose the Borderlands 4 game folder, not the Squ1ggs tool folder. You can select the game's OakGame/Binaries/Win64 folder too. No files were installed.",
  };
  storedGameRoot = selectedRoot;
  persistStoredSettings();
  const modSync = runAutoModSync({ gameRoot: storedGameRoot });
  let baseSdk = detectBaseSdk(storedGameRoot);
  try {
    baseSdk = await checkBaseSdkUpdate(storedGameRoot);
  } catch {
    /* keep local detect */
  }
  return {
    ok: true,
    gameRoot: storedGameRoot,
    storedGameRoot,
    pathSource: "stored",
    candidates: defaultInstallCandidates(),
    settingsMode,
    settingsPath,
    baseSdk,
    modSync,
  };
}

ipcMain.handle("sqbt:pick-game-folder", async () => pickAndSaveGameFolder());

ipcMain.handle("sqbt:prompt-missing-game-folder", async () => {
  const gameRoot = resolveGameRoot(storedGameRoot);
  if (gameRoot) {
    return {
      ok: true,
      skipped: true,
      gameRoot,
      storedGameRoot: storedGameRoot || gameRoot,
      pathSource: storedGameRoot ? "stored" : "detected",
      candidates: defaultInstallCandidates(),
    };
  }
  const hint = defaultGameRootHint();
  const choice = await dialog.showMessageBox(mainWindow, {
    type: "info",
    buttons: ["Choose Borderlands 4 folder…", "Not now"],
    defaultId: 0,
    cancelId: 1,
    title: "Borderlands 4 not found",
    message: "Could not find Borderlands 4 in the default install location.",
    detail:
      `Usually:\n${hint}\n\n` +
      "Choose the folder that contains Borderlands4.exe / OakGame " +
      "(Steam library folder named Borderlands 4 — not sdk_mods).",
  });
  if (choice.response !== 0) {
    return { ok: false, cancelled: true };
  }
  return pickAndSaveGameFolder();
});
ipcMain.handle("sqbt:install-sdkmod", async (_event, options = {}) => {
  try {
    const gameRoot = storedGameRoot || resolveGameRoot(undefined);
    const detectedPre = detectBaseSdk(gameRoot);
    const wantBase =
      Boolean(options?.includeBaseSdk) ||
      Boolean(options?.forceBaseSdk) ||
      !detectedPre.installed ||
      Boolean(detectedPre.belowMin);
    const forceBase = Boolean(options?.forceBaseSdk) || Boolean(detectedPre.belowMin);
    const notes = [];
    let baseOutcome = null;

    if (wantBase) {
      if (isBorderlandsRunning()) return {
        ok: false,
        message: "Close Borderlands 4 before installing the base SDK, then press Install SDK + Squ1ggs mod again.",
        gameRoot,
      };
      const detected = detectBaseSdk(gameRoot);
      const needsConfirm =
        !detected.installed || forceBase || Boolean(options?.includeBaseSdk) || Boolean(detected.belowMin);
      if (needsConfirm && !options?.confirmedBaseSdk) {
        const detail = detected.installed
          ? `Squ1ggs needs Oak2 SDK 0.3+ (FGbxDefPtr). Tracked version: ${detected.version || "unknown"}.\n\nUpdate from bl-sdk/oak2-mod-manager into:\n\n${gameRoot || "(unknown)"}\n\nExisting mods in sdk_mods are kept. Close Borderlands 4 first.`
          : `No oak2 SDK detected in:\n\n${gameRoot || "(unknown)"}\n\nDownload and install the official oak2-sdk.zip from bl-sdk/oak2-mod-manager (~14 MB), then install Squ1ggs Boosting Tools.\n\nClose Borderlands 4 first.`;
        const choice = await dialog.showMessageBox(mainWindow, {
          type: "question",
          buttons: ["Install SDK", "Cancel"],
          defaultId: 0,
          cancelId: 1,
          title: detected.belowMin ? "Update oak2 SDK to 0.3+?" : detected.installed ? "Update base SDK?" : "Install base SDK?",
          message: detected.belowMin
            ? "Oak2 SDK 0.3+ required"
            : detected.installed
              ? "Update oak2 base SDK?"
              : "Install oak2 base SDK?",
          detail,
        });
        if (choice.response !== 0) {
          return { ok: false, cancelled: true, message: "Base SDK install cancelled." };
        }
      }
      baseOutcome = await installBaseSdk({
        gameRoot,
        force: forceBase || Boolean(options?.includeBaseSdk) || Boolean(detected.belowMin),
        onProgress: (info) => {
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send("sqbt:update-progress", info);
          }
        },
      });
      if (!baseOutcome.ok) {
        return baseOutcome;
      }
      if (baseOutcome.message) notes.push(baseOutcome.message);
      if (baseOutcome.gameRoot) {
        storedGameRoot = baseOutcome.gameRoot;
        persistStoredSettings();
      }
    }

    const outcome = installSdkmod({ gameRoot: storedGameRoot || gameRoot || undefined });
    if (outcome.ok && outcome.gameRoot) {
      storedGameRoot = outcome.gameRoot;
      persistStoredSettings();
    }
    if (!outcome.ok) {
      return {
        ...outcome,
        baseSdk: baseOutcome,
        message: notes.length ? `${notes.join(" ")} ${outcome.message}` : outcome.message,
      };
    }
    return {
      ...outcome,
      baseSdk: baseOutcome,
      needsGameRestart: true,
      message: [...notes, outcome.message].filter(Boolean).join(" "),
    };
  } catch (error) {
    return { ok: false, message: `Mod folder update failed: ${String(error?.message || error)}` };
  }
});
ipcMain.handle("sqbt:apply-github-update", async (_event, currentModVersion) => {
  try {
    const status = await getUpdateStatus(true, currentModVersion || "");
    const outcome = await applyGithubUpdate({
      zipUrl: status.zipUrl,
      sdkmodUrl: status.sdkmodUrl,
      zipName: status.zipName || status.sdkmodName,
      gameRoot: storedGameRoot || undefined,
      // Prefer a small .sdkmod when only the mod moved — users keep their EXE.
      // Full portable zip replace only when the app version itself is newer.
      modOnly: Boolean(status.modUpdateAvailable) && !Boolean(status.appUpdateAvailable),
      applyApp: Boolean(status.zipUrl) && Boolean(status.appUpdateAvailable),
      packaged: app.isPackaged,
      execPath: process.execPath,
      pid: process.pid,
      onProgress: (info) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send("sqbt:update-progress", info);
        }
      },
    });
    if (outcome.ok && outcome.gameRoot) {
      storedGameRoot = outcome.gameRoot;
      persistStoredSettings();
    }
    updateCache = null;
    updateCheckedAt = 0;
    if (outcome.restartApp) {
      setTimeout(() => app.quit(), 900);
    }
    return outcome;
  } catch (error) {
    return { ok: false, message: `Update failed: ${String(error?.message || error)}` };
  }
});
ipcMain.handle("sqbt:open-external", async (_event, targetUrl) => {
  if (typeof targetUrl === "string" && targetUrl.startsWith("http")) {
    await shell.openExternal(targetUrl);
  }
});
ipcMain.handle("sqbt:open-path", async (_event, targetPath) => {
  const raw = String(targetPath || "").trim();
  if (!raw) {
    return { ok: false, message: "No path." };
  }
  try {
    const fs = require("fs");
    const path = require("path");
    let openTarget = raw;
    if (!fs.existsSync(openTarget)) {
      const parent = path.dirname(openTarget);
      if (fs.existsSync(parent)) {
        openTarget = parent;
      } else {
        return { ok: false, message: `Path not found: ${raw}` };
      }
    }
    const err = await shell.openPath(openTarget);
    if (err) {
      return { ok: false, message: String(err) };
    }
    return { ok: true, path: openTarget };
  } catch (error) {
    return { ok: false, message: String(error?.message || error) };
  }
});
ipcMain.handle("sqbt:snap-window", async (_event, edge = "right") => {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return { ok: false, message: "Window not ready." };
  }
  try {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    }
    const display = screen.getDisplayMatching(mainWindow.getBounds());
    const area = display.workArea;
    const half = Math.max(Math.floor(area.width / 2), 640);
    const width = Math.min(half, area.width);
    const x = edge === "left" ? area.x : area.x + area.width - width;
    mainWindow.setBounds({
      x,
      y: area.y,
      width,
      height: area.height,
    });
    return { ok: true, edge, width, height: area.height };
  } catch (error) {
    return { ok: false, message: String(error?.message || error) };
  }
});
