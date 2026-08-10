"use strict";

const UPDATE_REPOSITORY = "Squ1ggs/Bl4SDKmods";
const UPDATE_API_URL = `https://api.github.com/repos/${UPDATE_REPOSITORY}/releases/latest`;
const UPDATE_PAGE_URL = `https://github.com/${UPDATE_REPOSITORY}/releases/latest`;

function versionParts(value) {
  const text = String(value || "").trim();
  if (!text) return null;
  // Accept plain tags (1.0.65 / v1.0.65) and prefixed release tags (sqbt-v1.0.65).
  const match =
    text.match(/^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$/i) ||
    text.match(/(?:^|[^0-9])v?(\d+)\.(\d+)\.(\d+)\b/i);
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function normalizeVersion(value) {
  const parts = versionParts(value);
  return parts ? parts.join(".") : "";
}

function compareVersions(left, right) {
  const a = versionParts(left);
  const b = versionParts(right);
  if (!a || !b) return 0;
  for (let index = 0; index < 3; index += 1) {
    if (a[index] > b[index]) return 1;
    if (a[index] < b[index]) return -1;
  }
  return 0;
}

function trustedReleaseUrl(value) {
  const candidate = String(value || "");
  const prefix = `https://github.com/${UPDATE_REPOSITORY}/`;
  return candidate.startsWith(prefix) ? candidate : UPDATE_PAGE_URL;
}

function parseLatestModVersion(releaseBody) {
  const text = String(releaseBody || "");
  // Release notes use shapes like: "mod **3.6.47**" / "mod 3.6.47+".
  const match = text.match(/\bmod\s+\*{0,2}v?(\d+\.\d+\.\d+)\*{0,2}/i);
  return match ? match[1] : "";
}

async function checkForUpdates({
  currentVersion,
  currentModVersion = "",
  fetchImpl = globalThis.fetch,
  timeoutMs = 8000,
} = {}) {
  if (typeof fetchImpl !== "function") {
    throw new Error("Update checks are unavailable on this system.");
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(UPDATE_API_URL, {
      headers: {
        Accept: "application/vnd.github+json",
        "User-Agent": "Squ1ggs-Boosting-Tools",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      redirect: "follow",
      signal: controller.signal,
    });

    if (response.status === 404) {
      return {
        ok: true,
        updateAvailable: false,
        currentVersion,
        currentModVersion: normalizeVersion(currentModVersion) || "",
        latestVersion: "",
        latestModVersion: "",
        noRelease: true,
        repository: UPDATE_REPOSITORY,
      };
    }
    if (!response.ok) {
      throw new Error(`GitHub returned HTTP ${response.status}.`);
    }

    const release = await response.json();
    const latestVersion =
      normalizeVersion(release?.tag_name) || normalizeVersion(release?.name);
    if (!latestVersion) {
      throw new Error("The latest GitHub release does not have a standard version tag.");
    }

    const latestModVersion = parseLatestModVersion(release?.body);
    const installedApp = normalizeVersion(currentVersion) || String(currentVersion || "");
    const installedMod = normalizeVersion(currentModVersion) || "";
    const appUpdateAvailable = compareVersions(latestVersion, installedApp) > 0;
    const modUpdateAvailable =
      Boolean(installedMod && latestModVersion) &&
      compareVersions(latestModVersion, installedMod) > 0;

    return {
      ok: true,
      updateAvailable: appUpdateAvailable || modUpdateAvailable,
      appUpdateAvailable,
      modUpdateAvailable,
      currentVersion: installedApp,
      currentModVersion: installedMod,
      latestVersion,
      latestModVersion,
      releaseName: String(release?.name || "").trim(),
      releaseUrl: trustedReleaseUrl(release?.html_url),
      publishedAt: String(release?.published_at || ""),
      repository: UPDATE_REPOSITORY,
    };
  } finally {
    clearTimeout(timer);
  }
}

module.exports = {
  UPDATE_PAGE_URL,
  UPDATE_REPOSITORY,
  checkForUpdates,
  compareVersions,
  normalizeVersion,
  parseLatestModVersion,
};
