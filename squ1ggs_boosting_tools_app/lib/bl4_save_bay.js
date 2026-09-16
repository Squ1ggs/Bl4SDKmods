"use strict";

/**
 * Pack Bay save sheet — decrypt the active character .sav to YAML and pull @U
 * serials. Runs in the EXE (not the game thread) so big packs do not hitch BL4.
 *
 * Crypto matches public BL4 save tools (AES-256-ECB + zlib; SteamID-derived key).
 * Local test only — no write-back yet.
 */

const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const crypto = require("crypto");
const os = require("os");

const BASE_KEY = Buffer.from([
  0x35, 0xec, 0x33, 0x77, 0xf3, 0x5d, 0xb0, 0xea, 0xbe, 0x6b, 0x83, 0x11, 0x54, 0x03, 0xeb, 0xfb, 0x27, 0x25, 0x64, 0x2e,
  0xd5, 0x49, 0x06, 0x29, 0x05, 0x78, 0xbd, 0x60, 0xba, 0x4a, 0xa7, 0x87,
]);

const DEFAULT_ROW_CAP = 200;

function saveGamesRoot() {
  const docs = path.join(os.homedir(), "Documents", "My Games", "Borderlands 4", "Saved", "SaveGames");
  return docs;
}

function deriveKey(steamid) {
  const digits = String(steamid || "").replace(/\D/g, "");
  if (!digits) {
    throw new Error("Missing Steam ID for save decrypt.");
  }
  const sid = BigInt(digits);
  const sidLe = Buffer.alloc(8);
  let n = sid;
  for (let i = 0; i < 8; i += 1) {
    sidLe[i] = Number(n & 0xffn);
    n >>= 8n;
  }
  const key = Buffer.from(BASE_KEY);
  for (let i = 0; i < 8; i += 1) {
    key[i] ^= sidLe[i];
  }
  return key;
}

function decryptSavToYamlText(savPath, steamid) {
  const ciph = fs.readFileSync(savPath);
  if (ciph.length % 16 !== 0) {
    throw new Error(`Save size ${ciph.length} is not a multiple of 16 — wrong file or corrupt.`);
  }
  const key = deriveKey(steamid);
  const decipher = crypto.createDecipheriv("aes-256-ecb", key, null);
  decipher.setAutoPadding(true);
  let padded;
  try {
    padded = Buffer.concat([decipher.update(ciph), decipher.final()]);
  } catch (error) {
    throw new Error(`Decrypt failed (wrong Steam ID?): ${error.message || error}`);
  }
  let yamlBuf;
  try {
    yamlBuf = zlib.inflateSync(padded);
  } catch {
    // Some toolchains leave trailing length/adler; try stripping 8 trailer bytes.
    try {
      yamlBuf = zlib.inflateSync(padded.subarray(0, Math.max(0, padded.length - 8)));
    } catch (error) {
      throw new Error(`Decompress failed: ${error.message || error}`);
    }
  }
  return yamlBuf.toString("utf8");
}

function listCandidateSaves() {
  const root = saveGamesRoot();
  if (!fs.existsSync(root)) {
    return [];
  }
  const out = [];
  for (const steamDir of fs.readdirSync(root, { withFileTypes: true })) {
    if (!steamDir.isDirectory()) continue;
    const steamid = steamDir.name;
    if (!/^\d{5,}$/.test(steamid) && !/^[0-9a-fA-F]{16,}$/.test(steamid)) continue;
    const accountRoot = path.join(root, steamid);
    const walk = (dir) => {
      let entries = [];
      try {
        entries = fs.readdirSync(dir, { withFileTypes: true });
      } catch {
        return;
      }
      for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(full);
          continue;
        }
        if (!entry.isFile()) continue;
        const lower = entry.name.toLowerCase();
        if (!lower.endsWith(".sav")) continue;
        if (lower === "profile.sav") continue;
        // Prefer plain character slots (1.sav, 21.sav). Skip stamped backups.
        if (/_20\d{6}_/.test(lower) || /_updated_/.test(lower) || /backup/.test(lower)) {
          continue;
        }
        let st;
        try {
          st = fs.statSync(full);
        } catch {
          continue;
        }
        out.push({
          path: full,
          steamid,
          mtimeMs: st.mtimeMs,
          size: st.size,
          name: entry.name,
        });
      }
    };
    walk(accountRoot);
  }
  out.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return out;
}

function extractSerialRows(yamlText, { preferBackpack = true, limit = DEFAULT_ROW_CAP } = {}) {
  const text = String(yamlText || "");
  const rows = [];
  const seen = new Set();
  const cap = Math.max(24, Math.min(Number(limit) || DEFAULT_ROW_CAP, 400));

  // Line-oriented: remember recent key context so we can bias backpack/inventory.
  const contextWindow = [];
  const lines = text.split(/\r?\n/);
  const serialRe = /\bserial\s*:\s*(?:'([^']+)'|"([^"]+)"|(@U\S+))/i;

  for (const line of lines) {
    const keyMatch = line.match(/^\s*([A-Za-z0-9_]+)\s*:/);
    if (keyMatch) {
      contextWindow.push(String(keyMatch[1] || "").toLowerCase());
      if (contextWindow.length > 12) contextWindow.shift();
    }
    const m = line.match(serialRe);
    if (!m) continue;
    const serial = String(m[1] || m[2] || m[3] || "").trim();
    if (!serial.startsWith("@U") || serial.length < 12 || seen.has(serial)) continue;
    const blob = contextWindow.join(" ");
    const backpackish = /backpack|inventory|equipped|itemlist|items/.test(blob);
    if (preferBackpack && !backpackish && rows.length > 0) {
      // Keep scanning; we'll accept non-backpack only if we found nothing later.
      continue;
    }
    seen.add(serial);
    const snip = serial.length > 40 ? `${serial.slice(0, 36)}…` : serial;
    rows.push({
      id: String(rows.length),
      slot: rows.length,
      serial,
      human: "",
      title: `#${rows.length} — ${snip}`,
      source: backpackish ? "backpack" : "save",
    });
    if (rows.length >= cap) break;
  }

  if (!rows.length && preferBackpack) {
    return extractSerialRows(yamlText, { preferBackpack: false, limit });
  }
  return rows;
}

function scanLatestSave(options = {}) {
  const limit = options.limit != null ? Number(options.limit) : DEFAULT_ROW_CAP;
  const forcedPath = String(options.path || "").trim();
  const forcedId = String(options.steamid || "").trim();
  let chosen = null;
  if (forcedPath) {
    chosen = {
      path: forcedPath,
      steamid: forcedId || guessSteamIdFromPath(forcedPath),
      mtimeMs: fs.existsSync(forcedPath) ? fs.statSync(forcedPath).mtimeMs : 0,
      name: path.basename(forcedPath),
    };
  } else {
    const list = listCandidateSaves();
    chosen = list[0] || null;
  }
  if (!chosen || !chosen.path) {
    return {
      ok: false,
      message: `No character .sav found under ${saveGamesRoot()}.`,
      rows: [],
    };
  }
  if (!chosen.steamid) {
    return {
      ok: false,
      message: `Could not infer Steam ID for ${chosen.path}.`,
      rows: [],
      save: chosen,
    };
  }
  try {
    const yamlText = decryptSavToYamlText(chosen.path, chosen.steamid);
    const rows = extractSerialRows(yamlText, { preferBackpack: true, limit });
    const when = new Date(chosen.mtimeMs || Date.now()).toLocaleString();
    return {
      ok: true,
      message: `${rows.length} @U from ${chosen.name} (autosave ${when}). Sheet is save-YAML — not a live UObject scan.`,
      rows,
      save: {
        path: chosen.path,
        name: chosen.name,
        steamid: chosen.steamid,
        mtimeMs: chosen.mtimeMs,
      },
      capped: rows.length >= limit,
      limit,
    };
  } catch (error) {
    return {
      ok: false,
      message: String(error?.message || error),
      rows: [],
      save: chosen,
    };
  }
}

function guessSteamIdFromPath(filePath) {
  const parts = String(filePath || "").split(/[/\\]/);
  for (const part of parts) {
    if (/^7656119\d+$/.test(part)) return part;
    if (/^\d{16,}$/.test(part)) return part;
  }
  return "";
}

module.exports = {
  DEFAULT_ROW_CAP,
  saveGamesRoot,
  listCandidateSaves,
  decryptSavToYamlText,
  extractSerialRows,
  scanLatestSave,
};
