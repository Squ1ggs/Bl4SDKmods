"use strict";

const path = require("path");
const { app, BrowserWindow, dialog, ipcMain, shell, screen } = require("electron");
const { getBridgeStatus, postAction, fetchManifest, fetchCatalog, BRIDGE_BASE } = require("./lib/bridge");
const { defaultGameRootHint, defaultInstallCandidates, normalizeGameRoot, resolveGameRoot } = require("./lib/game_paths");
const { installSdkmod } = require("./lib/sdkmod_install");
const { loadSettings, saveSettings } = require("./lib/app_settings");
const { checkForUpdates } = require("./lib/update_check");

let mainWindow = null;
let refreshTimer = null;
let storedGameRoot = null;
let settingsMode = "appdata";
let settingsPath = null;
let updateCache = null;
let updateCheckedAt = 0;
const UPDATE_CACHE_MS = 15 * 60 * 1000;

function applyStoredSettings(state) {
  storedGameRoot = state?.gameRoot || null;
  settingsMode = state?.settingsMode || "appdata";
  settingsPath = state?.settingsPath || null;
}

function loadStoredSettings() {
  applyStoredSettings(loadSettings(app));
}

function persistStoredSettings(extra = {}) {
  const saved = saveSettings(app, { gameRoot: storedGameRoot, ...extra });
  settingsMode = saved.mode;
  settingsPath = saved.path;
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
  const modKey = String(currentModVersion || "").trim();
  if (
    !force &&
    updateCache &&
    now - updateCheckedAt < UPDATE_CACHE_MS &&
    String(updateCache.checkedModVersion || "") === modKey
  ) {
    return updateCache;
  }
  try {
    updateCache = await checkForUpdates({
      currentVersion: app.getVersion(),
      currentModVersion: modKey,
    });
    updateCache.checkedModVersion = modKey;
  } catch (error) {
    updateCache = {
      ok: false,
      updateAvailable: false,
      currentVersion: app.getVersion(),
      currentModVersion: modKey,
      checkedModVersion: modKey,
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
  settingsMode,
  settingsPath,
  isPackaged: app.isPackaged,
}));
ipcMain.handle("sqbt:dismiss-setup", async () => {
  saveSettings(app, { gameRoot: storedGameRoot, setupDismissed: true });
  return { ok: true };
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
