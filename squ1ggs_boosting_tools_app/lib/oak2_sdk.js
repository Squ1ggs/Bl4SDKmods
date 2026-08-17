"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");
const { existsDir, normalizeGameRoot, resolveGameRoot, resolveSdkModsDir } = require("./game_paths");

const OAK2_REPO = "bl-sdk/oak2-mod-manager";
const OAK2_API_LATEST = `https://api.github.com/repos/${OAK2_REPO}/releases/latest`;
const OAK2_RELEASES_PAGE = `https://github.com/${OAK2_REPO}/releases/latest`;
const OAK2_VERSION_MARKER = ".sqbt_oak2_sdk_version";
const MIN_OAK2_VERSION = "0.3";
const USER_AGENT = "Squ1ggs-Boosting-Tools";

function win64Dir(gameRoot) {
  return path.join(gameRoot, "OakGame", "Binaries", "Win64");
}

function pluginsDir(gameRoot) {
  return path.join(win64Dir(gameRoot), "Plugins");
}

function trustedOak2DownloadUrl(value) {
  const candidate = String(value || "");
  const prefixes = [
    `https://github.com/${OAK2_REPO}/releases/download/`,
    `https://github.com/${OAK2_REPO}/releases/latest/download/`,
  ];
  return prefixes.some((prefix) => candidate.startsWith(prefix)) ? candidate : "";
}

function readInstalledVersion(gameRoot) {
  const marker = path.join(resolveSdkModsDir(gameRoot), OAK2_VERSION_MARKER);
  try {
    if (fs.existsSync(marker)) {
      return String(fs.readFileSync(marker, "utf8") || "").trim();
    }
  } catch {
    /* ignore */
  }
  return "";
}

function writeInstalledVersion(gameRoot, version) {
  const modsDir = resolveSdkModsDir(gameRoot);
  fs.mkdirSync(modsDir, { recursive: true });
  fs.writeFileSync(path.join(modsDir, OAK2_VERSION_MARKER), `${String(version || "").trim()}\n`, "utf8");
}

function detectBaseSdk(gameRootInput) {
  const gameRoot = normalizeGameRoot(gameRootInput) || resolveGameRoot(gameRootInput);
  if (!gameRoot) {
    return {
      ok: false,
      installed: false,
      gameRoot: null,
      message: "Borderlands 4 folder not set.",
    };
  }
  const dsound = path.join(win64Dir(gameRoot), "dsound.dll");
  const unrealsdk = path.join(pluginsDir(gameRoot), "unrealsdk.dll");
  const modsDir = resolveSdkModsDir(gameRoot);
  const modsBase = path.join(modsDir, "mods_base.sdkmod");
  const mainPy = path.join(modsDir, "__main__.py");
  const hasProxy = fs.existsSync(dsound);
  const hasPlugin = fs.existsSync(unrealsdk);
  const hasModsCore = fs.existsSync(modsBase) || fs.existsSync(mainPy);
  const installed = hasProxy && hasPlugin && hasModsCore;
  const missing = [];
  if (!hasProxy) missing.push("OakGame\\Binaries\\Win64\\dsound.dll");
  if (!hasPlugin) missing.push("OakGame\\Binaries\\Win64\\Plugins\\unrealsdk.dll");
  if (!hasModsCore) missing.push("sdk_mods (mods_base / __main__.py)");
  const version = readInstalledVersion(gameRoot);
  const belowMin =
    Boolean(installed) && (!version || compareVersions(MIN_OAK2_VERSION, version) > 0);
  return {
    ok: true,
    installed,
    gameRoot,
    version,
    minVersion: MIN_OAK2_VERSION,
    belowMin,
    needsOak2_03: belowMin,
    hasProxy,
    hasPlugin,
    hasModsDir: existsDir(modsDir),
    missing,
    releasesPage: OAK2_RELEASES_PAGE,
  };
}

function compareVersions(left, right) {
  const parse = (value) => {
    const match = String(value || "")
      .trim()
      .match(/v?(\d+)\.(\d+)(?:\.(\d+))?/i);
    if (!match) return null;
    return [Number(match[1]), Number(match[2]), Number(match[3] || 0)];
  };
  const a = parse(left);
  const b = parse(right);
  if (!a || !b) return 0;
  for (let i = 0; i < 3; i += 1) {
    if (a[i] > b[i]) return 1;
    if (a[i] < b[i]) return -1;
  }
  return 0;
}

async function fetchLatestOak2Release() {
  const response = await fetch(OAK2_API_LATEST, {
    headers: {
      Accept: "application/vnd.github+json",
      "User-Agent": USER_AGENT,
    },
  });
  if (!response.ok) {
    throw new Error(`Could not check oak2-mod-manager releases (HTTP ${response.status}).`);
  }
  const data = await response.json();
  const tag = String(data.tag_name || data.name || "").trim();
  const assets = Array.isArray(data.assets) ? data.assets : [];
  const zip =
    assets.find((a) => String(a.name || "").toLowerCase() === "oak2-sdk.zip") ||
    assets.find((a) => String(a.name || "").toLowerCase().endsWith(".zip"));
  const url = trustedOak2DownloadUrl(zip?.browser_download_url || "");
  if (!url) {
    throw new Error("oak2-sdk.zip not found on the latest oak2-mod-manager release.");
  }
  return {
    tag,
    version: tag.replace(/^v/i, ""),
    zipUrl: url,
    zipName: String(zip.name || "oak2-sdk.zip"),
    htmlUrl: String(data.html_url || OAK2_RELEASES_PAGE),
  };
}

async function checkBaseSdkUpdate(gameRootInput) {
  const detected = detectBaseSdk(gameRootInput);
  if (!detected.gameRoot) {
    return { ...detected, updateAvailable: false };
  }
  try {
    const latest = await fetchLatestOak2Release();
    const belowMin =
      Boolean(detected.installed) &&
      (!detected.version || compareVersions(MIN_OAK2_VERSION, detected.version) > 0);
    const updateAvailable =
      !detected.installed ||
      belowMin ||
      (Boolean(detected.version) && compareVersions(latest.version, detected.version) > 0);
    return {
      ...detected,
      belowMin,
      needsOak2_03: belowMin,
      minVersion: MIN_OAK2_VERSION,
      updateAvailable,
      latestVersion: latest.version,
      latestTag: latest.tag,
      zipUrl: latest.zipUrl,
      htmlUrl: latest.htmlUrl,
      current: detected.version || (detected.installed ? "unknown" : ""),
      message: belowMin
        ? `Oak2 SDK ${MIN_OAK2_VERSION}+ required (tracked ${detected.version || "unknown"}). Update base SDK.`
        : undefined,
    };
  } catch (error) {
    return {
      ...detected,
      updateAvailable: !detected.installed,
      checkError: String(error?.message || error),
    };
  }
}

function extractArchive(archivePath, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  const tar = spawnSync("tar", ["-xf", archivePath, "-C", destDir], {
    windowsHide: true,
    encoding: "utf8",
  });
  if (Number(tar.status) === 0) return;
  const src = archivePath.replace(/'/g, "''");
  const dst = destDir.replace(/'/g, "''");
  const ps = spawnSync(
    "powershell.exe",
    [
      "-NoProfile",
      "-NonInteractive",
      "-Command",
      `Expand-Archive -LiteralPath '${src}' -DestinationPath '${dst}' -Force`,
    ],
    { windowsHide: true, encoding: "utf8" }
  );
  if (Number(ps.status) !== 0) {
    throw new Error(
      String(ps.stderr || tar.stderr || "Could not extract oak2-sdk.zip.").trim() ||
        "Could not extract oak2-sdk.zip."
    );
  }
}

async function downloadFile(url, destPath, onProgress) {
  const trusted = trustedOak2DownloadUrl(url);
  if (!trusted) {
    throw new Error("Refusing untrusted oak2 download URL.");
  }
  const response = await fetch(trusted, {
    headers: {
      Accept: "application/octet-stream",
      "User-Agent": USER_AGENT,
    },
    redirect: "follow",
  });
  if (!response.ok) {
    throw new Error(`oak2 SDK download failed (HTTP ${response.status}).`);
  }
  const total = Number(response.headers.get("content-length") || 0);
  const chunks = [];
  let received = 0;
  const reader = response.body?.getReader?.();
  if (!reader) {
    fs.writeFileSync(destPath, Buffer.from(await response.arrayBuffer()));
    return destPath;
  }
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(Buffer.from(value));
    received += value.length;
    if (total > 0 && typeof onProgress === "function") {
      const pct = Math.max(1, Math.min(99, Math.round((received / total) * 100)));
      onProgress({ stage: "download", message: `Downloading oak2 SDK… ${pct}%` });
    }
  }
  fs.writeFileSync(destPath, Buffer.concat(chunks));
  return destPath;
}

function copyFile(src, dest) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

function mergeTree(source, destination) {
  if (!existsDir(source)) return;
  fs.mkdirSync(destination, { recursive: true });
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const from = path.join(source, entry.name);
    const to = path.join(destination, entry.name);
    if (entry.isDirectory()) {
      mergeTree(from, to);
    } else if (entry.isFile()) {
      copyFile(from, to);
    }
  }
}

function findExtractedSdkRoot(extractDir) {
  if (existsDir(path.join(extractDir, "OakGame")) && existsDir(path.join(extractDir, "sdk_mods"))) {
    return extractDir;
  }
  for (const entry of fs.readdirSync(extractDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const nested = path.join(extractDir, entry.name);
    if (existsDir(path.join(nested, "OakGame")) && existsDir(path.join(nested, "sdk_mods"))) {
      return nested;
    }
  }
  return null;
}

function applyExtractedSdk(extractRoot, gameRoot) {
  const sdkRoot = findExtractedSdkRoot(extractRoot);
  if (!sdkRoot) {
    throw new Error("oak2-sdk.zip did not contain OakGame + sdk_mods.");
  }
  const srcWin64 = path.join(sdkRoot, "OakGame", "Binaries", "Win64");
  const destWin64 = win64Dir(gameRoot);
  fs.mkdirSync(destWin64, { recursive: true });
  const dsoundSrc = path.join(srcWin64, "dsound.dll");
  if (fs.existsSync(dsoundSrc)) {
    copyFile(dsoundSrc, path.join(destWin64, "dsound.dll"));
  }
  mergeTree(path.join(srcWin64, "Plugins"), pluginsDir(gameRoot));
  // Merge sdk_mods without deleting user mods (Squ1ggsBoostingTools, etc.).
  mergeTree(path.join(sdkRoot, "sdk_mods"), resolveSdkModsDir(gameRoot));
}

async function installBaseSdk({ gameRoot: gameRootInput, force = false, onProgress } = {}) {
  const emit = (stage, message) => {
    if (typeof onProgress === "function") onProgress({ stage, message });
  };
  const gameRoot = normalizeGameRoot(gameRootInput) || resolveGameRoot(gameRootInput);
  if (!gameRoot) {
    return {
      ok: false,
      message: "Could not find Borderlands 4. Browse to the game folder first.",
    };
  }
  if (!existsDir(path.join(gameRoot, "OakGame"))) {
    return {
      ok: false,
      message: `That folder does not look like Borderlands 4 (missing OakGame): ${gameRoot}`,
      gameRoot,
    };
  }

  const before = detectBaseSdk(gameRoot);
  let latest;
  try {
    emit("check", "Checking official oak2-mod-manager release…");
    latest = await fetchLatestOak2Release();
  } catch (error) {
    return { ok: false, message: String(error?.message || error), gameRoot };
  }

  if (
    before.installed &&
    before.version &&
    !before.belowMin &&
    compareVersions(latest.version, before.version) <= 0 &&
    !force
  ) {
    return {
      ok: true,
      skipped: true,
      message: `Base oak2 SDK already installed (v${before.version}).`,
      gameRoot,
      version: before.version,
      latestVersion: latest.version,
    };
  }

  const work = fs.mkdtempSync(path.join(os.tmpdir(), "sqbt-oak2-"));
  const archivePath = path.join(work, latest.zipName || "oak2-sdk.zip");
  const extractDir = path.join(work, "extracted");
  try {
    emit("download", `Downloading oak2 SDK ${latest.tag} (~14 MB)…`);
    await downloadFile(latest.zipUrl, archivePath, onProgress);
    emit("extract", "Extracting oak2 SDK…");
    extractArchive(archivePath, extractDir);
    emit("install", "Installing into Borderlands 4 folder…");
    applyExtractedSdk(extractDir, gameRoot);
    writeInstalledVersion(gameRoot, latest.version);
    const after = detectBaseSdk(gameRoot);
    if (!after.installed) {
      return {
        ok: false,
        message:
          `oak2 files were copied but detection still failed (missing: ${after.missing.join(", ") || "unknown"}). ` +
          `Close the game and retry, or install manually from ${OAK2_RELEASES_PAGE}.`,
        gameRoot,
      };
    }
    return {
      ok: true,
      message:
        `Installed official oak2 SDK ${latest.tag} into ${gameRoot}. ` +
        `Fully restart Borderlands 4 after finishing setup.`,
      gameRoot,
      version: latest.version,
      latestVersion: latest.version,
      needsGameRestart: true,
      htmlUrl: latest.htmlUrl,
    };
  } catch (error) {
    return {
      ok: false,
      message: `oak2 SDK install failed: ${String(error?.message || error)}`,
      gameRoot,
    };
  } finally {
    try {
      fs.rmSync(work, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  }
}

module.exports = {
  MIN_OAK2_VERSION,
  OAK2_RELEASES_PAGE,
  OAK2_REPO,
  checkBaseSdkUpdate,
  compareVersions,
  detectBaseSdk,
  fetchLatestOak2Release,
  installBaseSdk,
  trustedOak2DownloadUrl,
};
