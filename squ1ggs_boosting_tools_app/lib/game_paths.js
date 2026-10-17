"use strict";

const fs = require("fs");
const path = require("path");

const STEAM_APP_ID = "1285190";

function defaultGameRootHint() {
  const programX86 = process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)";
  return path.join(programX86, "Steam", "steamapps", "common", "Borderlands 4");
}

function existsDir(candidate) {
  try {
    return fs.existsSync(candidate) && fs.statSync(candidate).isDirectory();
  } catch {
    return false;
  }
}

function readSteamLibraryFolders(steamRoot) {
  const vdfPath = path.join(steamRoot, "steamapps", "libraryfolders.vdf");
  if (!fs.existsSync(vdfPath)) {
    return [path.join(steamRoot, "steamapps")];
  }
  const text = fs.readFileSync(vdfPath, "utf8");
  const roots = [path.join(steamRoot, "steamapps")];
  for (const match of text.matchAll(/"path"\s+"([^"]+)"/g)) {
    const libraryRoot = match[1].replace(/\\\\/g, "\\");
    roots.push(path.join(libraryRoot, "steamapps"));
  }
  return roots;
}

function steamInstallCandidates() {
  const gameDirs = [];
  const steamRoots = [];
  const programX86 = process.env["ProgramFiles(x86)"];
  const programFiles = process.env.ProgramFiles;
  for (const root of [programX86, programFiles].filter(Boolean)) {
    steamRoots.push(path.join(root, "Steam"));
  }
  for (const steamRoot of steamRoots) {
    if (!existsDir(steamRoot)) continue;
    for (const apps of readSteamLibraryFolders(steamRoot)) {
      const manifest = path.join(apps, "appmanifest_" + STEAM_APP_ID + ".acf");
      if (!fs.existsSync(manifest)) continue;
      const text = fs.readFileSync(manifest, "utf8");
      const folderMatch = text.match(/"installdir"\s+"([^"]+)"/i);
      if (!folderMatch) continue;
      const gameDir = path.join(apps, "common", folderMatch[1]);
      if (existsDir(gameDir)) {
        gameDirs.push(gameDir);
      }
    }
  }
  return [...new Set(gameDirs.map((dir) => path.resolve(dir)))];
}

function epicInstallCandidates() {
  const candidates = [];
  const epicRoot = process.env.ProgramFiles
    ? path.join(process.env.ProgramFiles, "Epic Games", "Borderlands 4")
    : null;
  if (epicRoot && existsDir(epicRoot)) {
    candidates.push(path.resolve(epicRoot));
  }
  return candidates;
}

function defaultInstallCandidates() {
  const found = [];
  const manual = process.env.SQBT_BL4_ROOT;
  if (manual && existsDir(manual)) {
    found.push(path.resolve(manual));
  }
  const standard = defaultGameRootHint();
  if (existsDir(standard)) {
    found.push(path.resolve(standard));
  }
  for (const candidate of [...steamInstallCandidates(), ...epicInstallCandidates()]) {
    found.push(candidate);
  }
  return [...new Set(found)];
}

function normalizeGameRoot(candidate) {
  if (!candidate) return null;
  let root = path.resolve(candidate);
  try {
    if (fs.statSync(root).isFile()) root = path.dirname(root);
  } catch { return null; }
  // Accept the game EXE, Win64, OakGame or sdk_mods, then walk to the root.
  for (let depth = 0; depth < 5; depth++) {
    const binaries = path.join(root, "OakGame", "Binaries", "Win64");
    if ((existsDir(path.join(root, "OakGame")) && fs.existsSync(path.join(root, "Borderlands4.exe"))) ||
        fs.existsSync(path.join(binaries, "Borderlands4.exe")) ||
        fs.existsSync(path.join(binaries, "Borderlands4-Win64-Shipping.exe"))) return root;
    const parent = path.dirname(root);
    if (parent === root) break;
    root = parent;
  }
  return null;
}

function looksLikeSdkModsDir(candidate) {
  if (!candidate || !existsDir(candidate)) {
    return false;
  }
  const base = path.basename(path.resolve(candidate)).toLowerCase();
  if (base === "sdk_mods" || base === "sdkmods") {
    return true;
  }
  if (fs.existsSync(path.join(candidate, "settings"))) {
    return true;
  }
  try {
    return fs.readdirSync(candidate).some((name) => name.toLowerCase().endsWith(".sdkmod"));
  } catch {
    return false;
  }
}

function resolveSdkModsDir(gameRoot) {
  const normalized = normalizeGameRoot(gameRoot) || gameRoot;
  const nested = path.join(normalized, "sdk_mods");
  if (existsDir(nested)) {
    return nested;
  }
  if (looksLikeSdkModsDir(normalized)) {
    return path.resolve(normalized);
  }
  return nested;
}

function resolveGameRoot(preferred) {
  if (preferred) {
    const normalized = normalizeGameRoot(preferred);
    return normalized;
  }
  const candidates = defaultInstallCandidates();
  return candidates.map(normalizeGameRoot).find(Boolean) || null;
}

function sdkModsDir(gameRoot) {
  return resolveSdkModsDir(gameRoot);
}

function settingsDir(gameRoot) {
  return path.join(resolveSdkModsDir(gameRoot), "settings");
}

function modSettingsPath(gameRoot) {
  return path.join(settingsDir(gameRoot), "Squ1ggsBoostingTools.json");
}

module.exports = {
  defaultGameRootHint,
  defaultInstallCandidates,
  epicInstallCandidates,
  existsDir,
  looksLikeSdkModsDir,
  modSettingsPath,
  normalizeGameRoot,
  resolveGameRoot,
  resolveSdkModsDir,
  sdkModsDir,
  settingsDir,
  steamInstallCandidates,
};
