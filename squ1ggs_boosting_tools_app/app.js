"use strict";

const path = require("path");
const { app, BrowserWindow, dialog, ipcMain, shell, screen } = require("electron");
const { getBridgeStatus, postAction, fetchManifest, fetchCatalog, BRIDGE_BASE } = require("./lib/bridge");
const { defaultGameRootHint, defaultInstallCandidates, normalizeGameRoot, resolveGameRoot } = require("./lib/game_paths");
const { installSdkmod } = require("./lib/sdkmod_install");
const { loadSettings, saveSettings, normalizeTheme } = require("./lib/app_settings");
const { checkForUpdates, compareVersions, normalizeVersion } = require("./lib/update_check");
const { applyGithubUpdate } = require("./lib/github_update");
const { getModSyncStatus } = require("./lib/sdkmod_install");
const { readSerialSource } = require("./lib/serial_sources");

let mainWindow = null;
let refreshTimer = null;
let storedGameRoot = null;
let storedTheme = "default";
let settingsMode = "appdata";
let settingsPath = null;
let updateCache = null;
let updateCheckedAt = 0;
let quittingAfterRestore = false;
const UPDATE_CACHE_MS = 15 * 60 * 1000;

function applyStoredSettings(state) {
  storedGameRoot = state?.gameRoot || null;
  storedTheme = normalizeTheme(state?.theme);
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
    ...extra,
  });
  settingsMode = saved.mode;
  settingsPath = saved.path;
  if (extra.theme !== undefined) {
    storedTheme = normalizeTheme(extra.theme);
  }
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

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
}

function pushStatus(payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("bridge-status", payload);
  }
}

async function refreshStatus() {
  const status = await getBridgeStatus();
  pushStatus(status);
  return status;
}

async function getUpdateStatus(force = false, currentModVersion = "") {
  const now = Date.now();
  const liveMod = normalizeVersion(currentModVersion) || String(currentModVersion || "").trim();
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
  refreshTimer = setInterval(() => {
    refreshStatus().catch(() => {});
  }, 5000);
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

app.whenReady().then(() => {
  loadStoredSettings();
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
ipcMain.handle("sqbt:check-for-updates", async (_event, force, currentModVersion) =>
  getUpdateStatus(Boolean(force), currentModVersion || "")
);
ipcMain.handle("sqbt:post-action", async (_event, action, payload, timeout) => {
  try {
    const result = await postAction(action, payload || {}, timeout ?? 12);
    await refreshStatus().catch(() => {});
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
    return { ok: true, manifest: await fetchManifest() };
  } catch (error) {
    return { ok: false, message: String(error) };
  }
});
ipcMain.handle("sqbt:get-catalog", async (_event, name, payload) => {
  try {
    return { ok: true, data: await fetchCatalog(name, payload || {}) };
  } catch (error) {
    return { ok: false, message: String(error) };
  }
});
ipcMain.handle("sqbt:get-setup", async () => ({
  bridgeUrl: BRIDGE_BASE,
  gameRoot: resolveGameRoot(storedGameRoot),
  defaultGameRoot: defaultGameRootHint(),
  candidates: defaultInstallCandidates(),
  storedGameRoot,
  setupDismissed: Boolean(loadSettings(app).setupDismissed),
  theme: storedTheme,
  settingsMode,
  settingsPath,
  isPackaged: app.isPackaged,
}));
ipcMain.handle("sqbt:dismiss-setup", async () => {
  persistStoredSettings({ setupDismissed: true });
  return { ok: true };
});
ipcMain.handle("sqbt:set-theme", async (_event, theme) => {
  storedTheme = normalizeTheme(theme);
  persistStoredSettings({ theme: storedTheme });
  return { ok: true, theme: storedTheme };
});
ipcMain.handle("sqbt:read-serial-source", async (_event, rawPath) => readSerialSource(rawPath));
ipcMain.handle("sqbt:pick-serial-file", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select a serial list (.txt or .docx)",
    properties: ["openFile"],
    filters: [
      { name: "Serial lists", extensions: ["txt", "docx", "csv", "md", "json", "log"] },
      { name: "All files", extensions: ["*"] },
    ],
  });
  if (result.canceled || !result.filePaths?.length) {
    return { ok: false, cancelled: true };
  }
  return readSerialSource(result.filePaths[0]);
});
ipcMain.handle("sqbt:pick-game-folder", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select Borderlands 4 game folder (not sdk_mods)",
    properties: ["openDirectory"],
  });
  if (result.canceled || !result.filePaths?.length) {
    return { ok: false, cancelled: true };
  }
  storedGameRoot = normalizeGameRoot(result.filePaths[0]) || result.filePaths[0];
  persistStoredSettings();
  return { ok: true, gameRoot: storedGameRoot, settingsMode, settingsPath };
});
ipcMain.handle("sqbt:install-sdkmod", async () => {
  try {
    const outcome = installSdkmod({ gameRoot: storedGameRoot || undefined });
    if (outcome.ok && outcome.gameRoot) {
      storedGameRoot = outcome.gameRoot;
      persistStoredSettings();
    }
    return outcome;
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
      applyApp: Boolean(status.zipUrl),
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
