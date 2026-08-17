"use strict";

const fs = require("fs");
const path = require("path");
const {
  existsDir,
  modSettingsPath,
  normalizeGameRoot,
  resolveGameRoot,
  resolveSdkModsDir,
  settingsDir,
} = require("./game_paths");

const { compareVersions } = require("./update_check");

const MOD_FOLDER_NAME = "Squ1ggsBoostingTools";
const LEGACY_SDKMOD_NAME = `${MOD_FOLDER_NAME}.sdkmod`;
const PRESERVED_RUNTIME_DIRS = new Set(["logs"]);
const BL4_PROCESS_NAMES = ["Borderlands4.exe", "Borderlands 4.exe"];

function validModFolder(folder) {
  return existsDir(folder) && fs.existsSync(path.join(folder, "__init__.py"));
}

function readVersionFromPy(filePath) {
  try {
    const text = fs.readFileSync(filePath, "utf8");
    const match = text.match(/__version__(?:\s*:\s*\w+)?\s*=\s*["']([^"']+)["']/);
    return match ? String(match[1]).trim() : "";
  } catch {
    return "";
  }
}

function readModVersion(folder) {
  if (!validModFolder(folder)) return "";
  // Prefer _mod_version.py (avoids circular imports in the live mod).
  return (
    readVersionFromPy(path.join(folder, "_mod_version.py")) ||
    readVersionFromPy(path.join(folder, "__init__.py"))
  );
}

function installedModFolder(gameRoot) {
  const root = normalizeGameRoot(gameRoot) || resolveGameRoot(gameRoot);
  if (!root) return null;
  const folder = path.join(resolveSdkModsDir(root), MOD_FOLDER_NAME);
  return validModFolder(folder) ? folder : null;
}

function isBorderlandsRunning() {
  const { spawnSync } = require("child_process");
  for (const name of BL4_PROCESS_NAMES) {
    try {
      const result = spawnSync(
        "tasklist",
        ["/FI", `IMAGENAME eq ${name}`, "/FO", "CSV", "/NH"],
        { windowsHide: true, encoding: "utf8" }
      );
      const out = String(result.stdout || "");
      if (out.toLowerCase().includes(name.toLowerCase())) {
        return true;
      }
    } catch {
      /* ignore */
    }
  }
  return false;
}

function getModSyncStatus(gameRootInput) {
  const gameRoot = normalizeGameRoot(gameRootInput) || resolveGameRoot(gameRootInput);
  const source = resolveSourceModFolder();
  const bundledVersion = readModVersion(source);
  const installed = gameRoot ? installedModFolder(gameRoot) : null;
  const installedVersion = readModVersion(installed);
  // Only push when bundled is newer. Never wipe a newer on-disk fix with an older EXE bundle.
  const needsUpdate =
    Boolean(gameRoot) &&
    Boolean(source) &&
    Boolean(bundledVersion) &&
    (!installed ||
      !installedVersion ||
      compareVersions(bundledVersion, installedVersion) > 0);
  return {
    gameRoot,
    bundledVersion,
    installedVersion,
    installedPath: installed,
    sourcePath: source,
    needsUpdate,
    gameRunning: isBorderlandsRunning(),
  };
}

function bundledModFolderPath() {
  if (process.resourcesPath) {
    const packaged = path.join(process.resourcesPath, "sdkmod", MOD_FOLDER_NAME);
    if (validModFolder(packaged)) {
      return packaged;
    }
  }
  return path.join(__dirname, "..", "resources", MOD_FOLDER_NAME);
}

function devModFolderPath(repoRoot) {
  return path.join(repoRoot, MOD_FOLDER_NAME);
}

function resolveSourceModFolder(explicitSource) {
  if (explicitSource && validModFolder(explicitSource)) {
    return explicitSource;
  }
  const bundled = bundledModFolderPath();
  if (validModFolder(bundled)) {
    return bundled;
  }
  const repoRoot = path.resolve(__dirname, "..", "..");
  const dev = devModFolderPath(repoRoot);
  return validModFolder(dev) ? dev : null;
}

function syncFolder(source, destination, relative = "") {
  fs.mkdirSync(destination, { recursive: true });
  const sourceEntries = fs
    .readdirSync(source, { withFileTypes: true })
    .filter((entry) => entry.name !== "__pycache__" && entry.name !== "logs");
  const sourceNames = new Set(sourceEntries.map((entry) => entry.name));
  for (const destEntry of fs.readdirSync(destination, { withFileTypes: true })) {
    if (sourceNames.has(destEntry.name)) continue;
    if (!relative && PRESERVED_RUNTIME_DIRS.has(destEntry.name)) continue;
    fs.rmSync(path.join(destination, destEntry.name), { recursive: true, force: true });
  }
  for (const sourceEntry of sourceEntries) {
    const sourcePath = path.join(source, sourceEntry.name);
    const destPath = path.join(destination, sourceEntry.name);
    const nextRelative = path.join(relative, sourceEntry.name);
    if (sourceEntry.isDirectory()) {
      syncFolder(sourcePath, destPath, nextRelative);
    } else if (sourceEntry.isFile()) {
      fs.copyFileSync(sourcePath, destPath);
    }
  }
}

function disableLegacySdkmod(modsDir) {
  const legacy = path.join(modsDir, LEGACY_SDKMOD_NAME);
  if (!fs.existsSync(legacy)) return null;
  const disabled = `${legacy}.folder-build-disabled`;
  if (fs.existsSync(disabled)) {
    fs.rmSync(legacy, { force: true });
  } else {
    fs.renameSync(legacy, disabled);
  }
  return disabled;
}

function ensureModEnabled(gameRoot) {
  const settingsPath = modSettingsPath(gameRoot);
  let settings = {};
  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
    } catch {
      settings = {};
    }
  }
  settings.enabled = true;
  if (!settings.keybinds || typeof settings.keybinds !== "object") {
    settings.keybinds = {};
  }
  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 4) + "\n", "utf8");
}

function installSdkmod(options = {}) {
  const rawRoot = options.gameRoot;
  const gameRoot = normalizeGameRoot(rawRoot) || resolveGameRoot(rawRoot);
  if (!gameRoot) {
    return {
      ok: false,
      message: "Could not find Borderlands 4. Browse to the game folder (the Borderlands 4 folder, not sdk_mods).",
    };
  }

  const source = resolveSourceModFolder(options.sourcePath);
  if (!source) {
    return {
      ok: false,
      message: `Missing bundled ${MOD_FOLDER_NAME} folder. Rebuild the portable app folder.`,
    };
  }

  const modsDir = resolveSdkModsDir(gameRoot);
  const settings = settingsDir(gameRoot);
  fs.mkdirSync(modsDir, { recursive: true });
  fs.mkdirSync(settings, { recursive: true });

  const destination = path.join(modsDir, MOD_FOLDER_NAME);
  try {
    syncFolder(source, destination);
    ensureModEnabled(gameRoot);
  } catch (error) {
    return {
      ok: false,
      message:
        `Could not update ${destination}: ${String(error?.message || error)}. ` +
        `Close Borderlands 4 and retry.`,
      gameRoot,
    };
  }
  let disabledSdkmod = null;
  let legacyWarning = "";
  try {
    disabledSdkmod = disableLegacySdkmod(modsDir);
  } catch (error) {
    legacyWarning =
      `Could not disable the older ${LEGACY_SDKMOD_NAME} (${String(error?.message || error)}). ` +
      `Close the game and remove or rename it to avoid a duplicate-version warning. `;
  }

  return {
    ok: true,
    message:
      `Updated the ${MOD_FOLDER_NAME} folder and set enabled=true in settings. ` +
      (disabledSdkmod ? `Disabled the older duplicate ${LEGACY_SDKMOD_NAME}. ` : "") +
      legacyWarning +
      `Fully restart Borderlands 4 if it was already running.`,
    needsGameRestart: true,
    gameRoot,
    modFolderPath: destination,
    disabledSdkmod,
    settingsPath: modSettingsPath(gameRoot),
    sourcePath: source,
    bundledVersion: readModVersion(source),
    installedVersion: readModVersion(destination),
    usesDevFolder: true,
  };
}

/**
 * On EXE launch: copy bundled Squ1ggsBoostingTools into sdk_mods when versions differ.
 * Does not install the oak2 base SDK (that still needs user confirm).
 */
function ensureModSynced(options = {}) {
  const status = getModSyncStatus(options.gameRoot);
  if (!status.gameRoot) {
    return {
      ok: false,
      skipped: true,
      reason: "no-game-root",
      message: "No Borderlands 4 folder yet — browse in Setup first.",
      ...status,
    };
  }
  if (!status.sourcePath) {
    return {
      ok: false,
      skipped: true,
      reason: "no-bundled-mod",
      message: "Bundled Squ1ggsBoostingTools folder missing from this EXE build.",
      ...status,
    };
  }
  if (!status.needsUpdate && !options.force) {
    return {
      ok: true,
      skipped: true,
      updated: false,
      reason: "already-current",
      message: `Squ1ggsBoostingTools already matches this EXE (v${status.bundledVersion || "unknown"}).`,
      needsGameRestart: false,
      gameRunning: status.gameRunning,
      ...status,
    };
  }
  const installed = installSdkmod({ gameRoot: status.gameRoot, sourcePath: status.sourcePath });
  if (!installed.ok) {
    return { ...status, ...installed, updated: false, skipped: false };
  }
  const gameRunning = isBorderlandsRunning();
  const restartNote = gameRunning
    ? " Borderlands 4 is open — fully quit to desktop and relaunch so the new mod loads."
    : " Launch Borderlands 4 (or fully restart it) so the updated mod loads.";
  return {
    ...installed,
    skipped: false,
    updated: true,
    bundledVersion: status.bundledVersion,
    installedVersion: installed.installedVersion || status.bundledVersion,
    gameRunning,
    needsGameRestart: true,
    message:
      `Auto-updated Squ1ggsBoostingTools to v${status.bundledVersion || "bundled"}` +
      (status.installedVersion ? ` (was v${status.installedVersion})` : " (fresh install)") +
      `.${restartNote}`,
  };
}

module.exports = {
  LEGACY_SDKMOD_NAME,
  MOD_FOLDER_NAME,
  bundledModFolderPath,
  devModFolderPath,
  ensureModSynced,
  getModSyncStatus,
  installSdkmod,
  isBorderlandsRunning,
  readModVersion,
  resolveSourceModFolder,
  syncFolder,
};
