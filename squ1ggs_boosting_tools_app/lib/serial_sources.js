"use strict";

const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

const TEXT_EXTS = new Set([".txt", ".csv", ".md", ".json", ".log", ".yaml", ".yml"]);
const DOCX_EXTS = new Set([".docx"]);
const ALLOWED_EXTS = new Set([...TEXT_EXTS, ...DOCX_EXTS]);

const PATH_LINE_RE =
  /^\s*(?:"([^"\r\n]+)"|'([^'\r\n]+)'|((?:[A-Za-z]:\\|\\\\)[^\r\n]+))\s*$/;
const ATU_RE = /@U\S+/g;
const HUMAN_SERIAL_RE = /^\s*\d+\s*,\s*\d+/;

function stripQuotes(raw) {
  let s = String(raw || "").trim();
  if (
    (s.startsWith('"') && s.endsWith('"')) ||
    (s.startsWith("'") && s.endsWith("'"))
  ) {
    s = s.slice(1, -1).trim();
  }
  return s;
}

function looksLikeSerialFilePath(raw) {
  const cleaned = stripQuotes(raw);
  if (!cleaned) return false;
  const ext = path.extname(cleaned).toLowerCase();
  if (!ALLOWED_EXTS.has(ext)) return false;
  if (/^[A-Za-z]:[\\/]/.test(cleaned) || cleaned.startsWith("\\\\")) return true;
  // Relative paths with separators (user dropped a local file name with folder).
  return /[\\/]/.test(cleaned);
}

function decodeHtmlEntities(text) {
  return String(text || "")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&apos;/gi, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCharCode(parseInt(h, 16)));
}

function readUInt32LE(buf, offset) {
  return buf.readUInt32LE(offset);
}

function readUInt16LE(buf, offset) {
  return buf.readUInt16LE(offset);
}

function findZipEntry(buf, name) {
  // Prefer central directory (local headers often omit sizes / use data descriptors).
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0; i -= 1) {
    if (readUInt32LE(buf, i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd >= 0) {
    const cdOffset = readUInt32LE(buf, eocd + 16);
    let offset = cdOffset;
    while (offset < buf.length - 46 && readUInt32LE(buf, offset) === 0x02014b50) {
      const compression = readUInt16LE(buf, offset + 10);
      const compressedSize = readUInt32LE(buf, offset + 20);
      const nameLen = readUInt16LE(buf, offset + 28);
      const extraLen = readUInt16LE(buf, offset + 30);
      const commentLen = readUInt16LE(buf, offset + 32);
      const localHeader = readUInt32LE(buf, offset + 42);
      const entryName = buf.slice(offset + 46, offset + 46 + nameLen).toString("utf8").replace(/\\/g, "/");
      if (entryName === name) {
        if (readUInt32LE(buf, localHeader) !== 0x04034b50) {
          throw new Error(`Invalid local header for ${name}`);
        }
        const localNameLen = readUInt16LE(buf, localHeader + 26);
        const localExtraLen = readUInt16LE(buf, localHeader + 28);
        const dataStart = localHeader + 30 + localNameLen + localExtraLen;
        const data = buf.slice(dataStart, dataStart + compressedSize);
        if (compression === 0) return data;
        if (compression === 8) return zlib.inflateRawSync(data);
        throw new Error(`Unsupported zip compression (${compression}) in ${name}`);
      }
      offset += 46 + nameLen + extraLen + commentLen;
    }
  }

  // Fallback: scan local file headers.
  let offset = 0;
  while (offset < buf.length - 30) {
    if (readUInt32LE(buf, offset) !== 0x04034b50) {
      offset += 1;
      continue;
    }
    const compression = readUInt16LE(buf, offset + 8);
    const compressedSize = readUInt32LE(buf, offset + 18);
    const nameLen = readUInt16LE(buf, offset + 26);
    const extraLen = readUInt16LE(buf, offset + 28);
    const nameStart = offset + 30;
    const entryName = buf.slice(nameStart, nameStart + nameLen).toString("utf8").replace(/\\/g, "/");
    const dataStart = nameStart + nameLen + extraLen;
    if (entryName === name && compressedSize > 0) {
      const data = buf.slice(dataStart, dataStart + compressedSize);
      if (compression === 0) return data;
      if (compression === 8) return zlib.inflateRawSync(data);
      throw new Error(`Unsupported zip compression (${compression}) in ${name}`);
    }
    offset = compressedSize > 0 ? dataStart + compressedSize : dataStart + 1;
  }
  return null;
}

function readDocxText(filePath) {
  const buf = fs.readFileSync(filePath);
  const xmlBuf = findZipEntry(buf, "word/document.xml");
  if (!xmlBuf) {
    throw new Error("DOCX missing word/document.xml");
  }
  const xml = xmlBuf.toString("utf8");
  const withBreaks = xml
    .replace(/<\/w:p[^>]*>/gi, "\n")
    .replace(/<w:br\b[^/]*\/>/gi, "\n")
    .replace(/<w:tab\b[^/]*\/>/gi, "\t");
  const plain = withBreaks.replace(/<[^>]+>/g, "");
  return decodeHtmlEntities(plain);
}

function readSourceText(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (DOCX_EXTS.has(ext)) {
    return readDocxText(filePath);
  }
  if (TEXT_EXTS.has(ext)) {
    return fs.readFileSync(filePath, "utf8");
  }
  throw new Error(`Unsupported file type: ${ext || "(none)"}`);
}

function extractSerialsFromText(rawText) {
  const text = decodeHtmlEntities(String(rawText || ""));
  const found = [];
  const seen = new Set();

  const push = (serial) => {
    let cleaned = String(serial || "").trim();
    if (
      (cleaned.startsWith('"') && cleaned.endsWith('"')) ||
      (cleaned.startsWith("'") && cleaned.endsWith("'"))
    ) {
      cleaned = cleaned.slice(1, -1).trim();
    }
    // Markdown fence around the whole token only — never strip backticks inside Base85.
    if (cleaned.startsWith("`") && cleaned.endsWith("`") && cleaned.indexOf("`") === 0) {
      const inner = cleaned.slice(1, -1);
      if (!inner.includes("`")) {
        cleaned = inner.trim();
      }
    }
    if (!cleaned) return;
    if (!(cleaned.startsWith("@U") || (cleaned.includes(",") && /\d/.test(cleaned)))) {
      return;
    }
    if (seen.has(cleaned)) return;
    seen.add(cleaned);
    found.push(cleaned);
  };

  const pushAtUParts = (blob) => {
    const text = String(blob || "");
    const idx = text.indexOf("@U");
    if (idx < 0) return;
    for (const part of text.slice(idx).split(/(?=@U)/)) {
      const token = part.trim();
      if (token.startsWith("@U")) push(token);
    }
  };

  // Prefer explicit @U tokens anywhere in the blob (fenced markdown, prose, etc.).
  // Split only at a new @U prefix so ` ' @ inside one Base85 serial stay intact.
  const atMatches = text.match(ATU_RE) || [];
  for (const match of atMatches) {
    pushAtUParts(match);
  }

  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed.includes("@U")) {
      pushAtUParts(trimmed);
      continue;
    }
    if (HUMAN_SERIAL_RE.test(trimmed)) {
      push(trimmed);
    }
  }
  return found;
}

function readSerialSource(rawPath) {
  const cleaned = stripQuotes(rawPath);
  if (!cleaned) {
    return { ok: false, message: "Empty path." };
  }
  if (!looksLikeSerialFilePath(cleaned)) {
    return {
      ok: false,
      message: "Path must be a .txt / .docx / .csv / .md / .json file.",
    };
  }
  const resolved = path.resolve(cleaned);
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) {
    return { ok: false, message: `File not found: ${resolved}` };
  }
  try {
    const text = readSourceText(resolved);
    const serials = extractSerialsFromText(text);
    return {
      ok: true,
      path: resolved,
      serials,
      count: serials.length,
      message:
        serials.length > 0
          ? `Loaded ${serials.length} serial(s) from ${path.basename(resolved)}`
          : `No @U / human serials found in ${path.basename(resolved)}`,
    };
  } catch (error) {
    return {
      ok: false,
      message: `Could not read ${path.basename(resolved)}: ${String(error?.message || error)}`,
    };
  }
}

module.exports = {
  ALLOWED_EXTS,
  extractSerialsFromText,
  looksLikeSerialFilePath,
  readSerialSource,
  stripQuotes,
};
