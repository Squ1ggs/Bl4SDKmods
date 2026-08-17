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

function psSingleQuote(value) {
  return String(value ?? "").replace(/'/g, "''");
}

function scheduleAppReplace(extractedAppRoot, destRoot, pid) {
  // Hidden PowerShell via wscript (window style 0) — no CMD / FIND flash.
  const stamp = Date.now();
  const ps1Path = path.join(os.tmpdir(), `sqbt-apply-app-${stamp}.ps1`);
  const vbsPath = path.join(os.tmpdir(), `sqbt-apply-app-${stamp}.vbs`);
  const waitPid = Math.max(0, Number(pid) || 0);
  const src = psSingleQuote(extractedAppRoot);
  const dst = psSingleQuote(destRoot);
  const ps1Self = psSingleQuote(ps1Path);
  const vbsSelf = psSingleQuote(vbsPath);
  const ps1 = [
    "$ErrorActionPreference = 'SilentlyContinue'",
    `$src = '${src}'`,
    `$dst = '${dst}'`,
    "$exe = Join-Path $dst 'Squ1ggsBoostingTools.exe'",
    `$waitPid = ${waitPid}`,
    "if ($waitPid -gt 0) {",
    "  Wait-Process -Id $waitPid -ErrorAction SilentlyContinue",
    "  Start-Sleep -Milliseconds 500",
    "}",
    "& robocopy $src $dst /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null",
    "if (Test-Path -LiteralPath $exe) { Start-Process -FilePath $exe }",
    `Remove-Item -LiteralPath '${ps1Self}' -Force -ErrorAction SilentlyContinue`,
    `Remove-Item -LiteralPath '${vbsSelf}' -Force -ErrorAction SilentlyContinue`,
    "",
  ].join("\r\n");
  const ps1ForVbs = ps1Path.replace(/"/g, '""');
  const vbs = [
    'Set sh = CreateObject("WScript.Shell")',
    `sh.Run "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""${ps1ForVbs}""", 0, False`,
    "",
  ].join("\r\n");
  fs.writeFileSync(ps1Path, ps1, "utf8");
  fs.writeFileSync(vbsPath, vbs, "utf8");
  const child = spawn("wscript.exe", ["//B", "//Nologo", vbsPath], {
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
          "Finishing in the background (no CMD window). This app will close and reopen once by itself — after that, the X button closes normally. Fully restart Borderlands 4.",
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
