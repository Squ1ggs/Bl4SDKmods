"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn, spawnSync } = require("child_process");
const { installSdkmod, MOD_FOLDER_NAME } = require("./sdkmod_install");
const { trustedDownloadUrl } = require("./update_check");

function emit(onProgress, stage, message) {
  if (typeof onProgress === "function") {
    onProgress({ stage, message });
  }
}

function walkFind(root, matcher, maxDepth = 6, depth = 0) {
  if (!root || depth > maxDepth) return null;
  let entries = [];
  try {
    entries = fs.readdirSync(root, { withFileTypes: true });
  } catch {
    return null;
  }
  for (const entry of entries) {
    const full = path.join(root, entry.name);
    if (matcher(full, entry)) return full;
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const hit = walkFind(path.join(root, entry.name), matcher, maxDepth, depth + 1);
    if (hit) return hit;
  }
  return null;
}

function findModFolder(extractRoot) {
  return walkFind(
    extractRoot,
    (full, entry) =>
      entry.isDirectory() &&
      entry.name === MOD_FOLDER_NAME &&
      fs.existsSync(path.join(full, "__init__.py"))
  );
}

function findAppRoot(extractRoot) {
  const exe = walkFind(
    extractRoot,
    (_full, entry) =>
      entry.isFile() && entry.name.toLowerCase() === "squ1ggsboostingtools.exe",
    4
  );
  return exe ? path.dirname(exe) : null;
}

async function downloadFile(url, destPath, onProgress) {
  const trusted = trustedDownloadUrl(url);
  if (!trusted) {
    throw new Error("Refusing untrusted download URL.");
  }
  const response = await fetch(trusted, {
    headers: {
      Accept: "application/octet-stream",
      "User-Agent": "Squ1ggs-Boosting-Tools",
    },
    redirect: "follow",
  });
  if (!response.ok) {
    throw new Error(`Download failed (HTTP ${response.status}).`);
  }
  const total = Number(response.headers.get("content-length") || 0);
  const chunks = [];
  let received = 0;
  const reader = response.body?.getReader?.();
  if (!reader) {
    const buffer = Buffer.from(await response.arrayBuffer());
    fs.writeFileSync(destPath, buffer);
    return destPath;
  }
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(Buffer.from(value));
    received += value.length;
    if (total > 0) {
      const pct = Math.max(1, Math.min(99, Math.round((received / total) * 100)));
      emit(onProgress, "download", `Downloading update… ${pct}%`);
    }
  }
  fs.writeFileSync(destPath, Buffer.concat(chunks));
  return destPath;
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
      String(ps.stderr || tar.stderr || "Could not extract the update archive.").trim() ||
        "Could not extract the update archive."
    );
  }
}

function scheduleAppReplace(extractedAppRoot, destRoot, pid) {
  const batPath = path.join(os.tmpdir(), `sqbt-apply-app-${Date.now()}.bat`);
  const script = [
    "@echo off",
    "setlocal",
    "set \"SRC=%~1\"",
    "set \"DST=%~2\"",
    "set \"PID=%~3\"",
    ":wait",
    "tasklist /FI \"PID eq %PID%\" | find \"%PID%\" >nul",
    "if not errorlevel 1 (",
    "  timeout /t 1 /nobreak >nul",
    "  goto wait",
    ")",
    "robocopy \"%SRC%\" \"%DST%\" /E /NFL /NDL /NJH /NJS /nc /ns /np",
    "start \"\" \"%DST%\\Squ1ggsBoostingTools.exe\"",
    "del \"%~f0\"",
  ].join("\r\n");
  fs.writeFileSync(batPath, script, "utf8");
  const child = spawn("cmd.exe", ["/c", batPath, extractedAppRoot, destRoot, String(pid)], {
    detached: true,
    stdio: "ignore",
    windowsHide: true,
  });
  child.unref();
}

async function applyGithubUpdate({
  zipUrl = "",
  sdkmodUrl = "",
  zipName = "",
  gameRoot,
  applyApp = false,
  packaged = false,
  execPath = "",
  pid = process.pid,
  onProgress,
} = {}) {
  const url =
    (!applyApp && trustedDownloadUrl(sdkmodUrl)) ||
    trustedDownloadUrl(zipUrl) ||
    trustedDownloadUrl(sdkmodUrl);
  if (!url) {
    return {
      ok: false,
      message: "This GitHub release has no downloadable zip/.sdkmod yet. Open the release page instead.",
    };
  }

  const work = fs.mkdtempSync(path.join(os.tmpdir(), "sqbt-update-"));
  const archiveName = String(zipName || path.basename(url) || "update.zip").replace(/[^\w.\-]+/g, "_");
  const archivePath = path.join(work, archiveName || "update.zip");
  const extractDir = path.join(work, "extracted");
  let keepWork = false;

  try {
    emit(onProgress, "download", "Downloading update from GitHub…");
    await downloadFile(url, archivePath, onProgress);
    emit(onProgress, "extract", "Extracting update…");
    extractArchive(archivePath, extractDir);

    const modFolder = findModFolder(extractDir);
    let installed = null;
    if (modFolder) {
      emit(onProgress, "mod", "Updating sdk_mods folder…");
      installed = installSdkmod({ gameRoot, sourcePath: modFolder });
      if (!installed?.ok) {
        return installed;
      }
    }

    const appRoot = findAppRoot(extractDir);
    const canReplaceApp =
      Boolean(applyApp && packaged && appRoot && execPath) &&
      path.basename(String(execPath)).toLowerCase().includes("squ1ggs");
    if (canReplaceApp) {
      emit(onProgress, "app", "App update staged. The window will restart.");
      scheduleAppReplace(appRoot, path.dirname(execPath), pid);
      keepWork = true;
      return {
        ok: true,
        restartApp: true,
        needsGameRestart: true,
        message:
          (installed?.message ? `${installed.message} ` : "") +
          "App files will replace after this window closes, then Squ1ggs Boosting Tools will reopen. Fully restart Borderlands 4.",
        gameRoot: installed?.gameRoot,
      };
    }

    if (!installed) {
      return {
        ok: false,
        message: "Downloaded the release, but it did not contain Squ1ggsBoostingTools. Open the GitHub zip and install manually.",
      };
    }
    return {
      ...installed,
      message:
        installed.message +
        (applyApp && !canReplaceApp
          ? " App EXE was left as-is (dev build or missing portable EXE in the zip)."
          : ""),
    };
  } finally {
    if (!keepWork) {
      try {
        fs.rmSync(work, { recursive: true, force: true });
      } catch {
        /* temp cleanup is best-effort */
      }
    }
  }
}

module.exports = {
  applyGithubUpdate,
  findAppRoot,
  findModFolder,
};
