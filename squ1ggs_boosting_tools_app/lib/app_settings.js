"use strict";

const fs = require("fs");
const path = require("path");

const SETTINGS_FILENAME = "squ1ggs-boosting-tools-settings.json";

function appDataSettingsPath(app) {
  return path.join(app.getPath("userData"), SETTINGS_FILENAME);
}

function portableSettingsPath(app) {
  if (!app.isPackaged) {
    return null;
  }
  return path.join(path.dirname(process.execPath), SETTINGS_FILENAME);
}

function directoryWritable(dir) {
  try {
    fs.accessSync(dir, fs.constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

function resolveWritableSettingsTarget(app) {
  // Always prefer AppData for packaged builds so unzipping a newer portable
  // folder does not wipe game path / setup (old builds wrote beside the EXE).
  const appDataPath = appDataSettingsPath(app);
  try {
    fs.mkdirSync(path.dirname(appDataPath), { recursive: true });
    if (directoryWritable(path.dirname(appDataPath))) {
      return { path: appDataPath, mode: "appdata" };
    }
  } catch {
    /* fall through */
  }
  const portablePath = portableSettingsPath(app);
  if (portablePath && directoryWritable(path.dirname(portablePath))) {
    return { path: portablePath, mode: "portable" };
  }
  return { path: appDataPath, mode: "appdata" };
}

function readJsonFile(filePath) {
  const raw = fs.readFileSync(filePath, "utf8");
  const data = JSON.parse(raw);
  return data && typeof data === "object" ? data : {};
}

function normalizeTheme(value) {
  const theme = String(value || "").trim().toLowerCase();
  return theme === "scooters" ? "scooters" : "default";
}

function settingsScore(data) {
  if (!data || typeof data !== "object") return 0;
  let score = 0;
  if (data.gameRoot) score += 2;
  if (data.setupDismissed) score += 1;
  if (data.theme) score += 1;
  return score;
}

function loadSettings(app) {
  const writeTarget = resolveWritableSettingsTarget(app);
  const portablePath = portableSettingsPath(app);
  const appDataPath = appDataSettingsPath(app);
  const readCandidates = [];
  // Prefer AppData first so a leftover empty/stale file beside a new EXE
  // cannot override the durable profile settings.
  if (appDataPath) {
    readCandidates.push(appDataPath);
  }
  if (portablePath && portablePath !== appDataPath) {
    readCandidates.push(portablePath);
  }

  let best = null;
  let bestFrom = null;
  let bestScore = -1;
  for (const candidate of readCandidates) {
    try {
      if (!fs.existsSync(candidate)) continue;
      const loaded = readJsonFile(candidate);
      const score = settingsScore(loaded);
      if (score > bestScore) {
        best = loaded;
        bestFrom = candidate;
        bestScore = score;
      }
    } catch {
      /* try next location */
    }
  }

  if (best && bestFrom && bestFrom !== writeTarget.path) {
    try {
      saveSettings(app, {
        gameRoot: best.gameRoot || null,
        setupDismissed: Boolean(best.setupDismissed),
        theme: normalizeTheme(best.theme),
      });
    } catch {
      /* keep loaded values even if migration fails */
    }
  }

  return {
    gameRoot: best?.gameRoot || null,
    setupDismissed: Boolean(best?.setupDismissed),
    theme: normalizeTheme(best?.theme),
    settingsPath: writeTarget.path,
    settingsMode: writeTarget.mode,
  };
}

function saveSettings(app, data) {
  const target = resolveWritableSettingsTarget(app);
  let existing = {};
  try {
    if (fs.existsSync(target.path)) {
      existing = readJsonFile(target.path);
    }
  } catch {
    existing = {};
  }
  const payload = {
    gameRoot: data?.gameRoot !== undefined ? data.gameRoot || null : existing.gameRoot || null,
    setupDismissed:
      data?.setupDismissed !== undefined
        ? Boolean(data.setupDismissed)
        : Boolean(existing.setupDismissed),
    theme: normalizeTheme(data?.theme !== undefined ? data.theme : existing.theme),
  };
  fs.mkdirSync(path.dirname(target.path), { recursive: true });
  fs.writeFileSync(target.path, JSON.stringify(payload, null, 2) + "\n", "utf8");
  return target;
}

module.exports = {
  SETTINGS_FILENAME,
  appDataSettingsPath,
  loadSettings,
  normalizeTheme,
  portableSettingsPath,
  resolveWritableSettingsTarget,
  saveSettings,
};
