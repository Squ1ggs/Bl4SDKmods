"use strict";

const fs = require("fs");
const path = require("path");
const { PNG } = require("pngjs");
const { analyzeItem } = require("./item_analysis");
const { sdkmodRoot } = require("./offline_serial_card");

const MAX_BYTES = 12 * 1024 * 1024;
const MAX_PIXELS = 40 * 1000 * 1000;
const ALLOWED_MIME = new Set(["image/png", "image/jpeg", "image/webp"]);
let offlineCandidates;

function clean(value) {
  return String(value == null ? "" : value).trim();
}

function pngSize(buf) {
  if (buf.length < 24 || buf.toString("hex", 0, 8) !== "89504e470d0a1a0a") return null;
  return { mime: "image/png", width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

function jpegSize(buf) {
  if (buf.length < 4 || buf[0] !== 0xff || buf[1] !== 0xd8) return null;
  let at = 2;
  while (at + 9 < buf.length) {
    if (buf[at] !== 0xff) {
      at += 1;
      continue;
    }
    const marker = buf[at + 1];
    at += 2;
    if (marker === 0xd8 || marker === 0xd9) continue;
    if (at + 2 > buf.length) break;
    const length = buf.readUInt16BE(at);
    if (length < 2 || at + length > buf.length) break;
    if (
      (marker >= 0xc0 && marker <= 0xc3) ||
      (marker >= 0xc5 && marker <= 0xc7) ||
      (marker >= 0xc9 && marker <= 0xcb) ||
      (marker >= 0xcd && marker <= 0xcf)
    ) {
      return {
        mime: "image/jpeg",
        width: buf.readUInt16BE(at + 5),
        height: buf.readUInt16BE(at + 3),
      };
    }
    at += length;
  }
  return null;
}

function webpSize(buf) {
  if (
    buf.length < 30 ||
    buf.toString("ascii", 0, 4) !== "RIFF" ||
    buf.toString("ascii", 8, 12) !== "WEBP"
  ) {
    return null;
  }
  const kind = buf.toString("ascii", 12, 16);
  if (kind === "VP8X") {
    return {
      mime: "image/webp",
      width: 1 + buf.readUIntLE(24, 3),
      height: 1 + buf.readUIntLE(27, 3),
    };
  }
  if (kind === "VP8L" && buf.length >= 25 && buf[20] === 0x2f) {
    const bits = buf.readUInt32LE(21);
    return {
      mime: "image/webp",
      width: 1 + (bits & 0x3fff),
      height: 1 + ((bits >>> 14) & 0x3fff),
    };
  }
  if (kind === "VP8 " && buf.length >= 30) {
    return {
      mime: "image/webp",
      width: buf.readUInt16LE(26) & 0x3fff,
      height: buf.readUInt16LE(28) & 0x3fff,
    };
  }
  return null;
}

function inspectImageBuffer(buffer, declaredMime = "") {
  if (!Buffer.isBuffer(buffer) || !buffer.length) throw new Error("Image is empty.");
  if (buffer.length > MAX_BYTES) throw new Error("Image is larger than 12 MB.");
  const info = pngSize(buffer) || jpegSize(buffer) || webpSize(buffer);
  if (!info || !ALLOWED_MIME.has(info.mime)) {
    throw new Error("Use a valid PNG, JPEG, or WebP image.");
  }
  const claimed = clean(declaredMime).toLowerCase();
  if (claimed && ALLOWED_MIME.has(claimed) && claimed !== info.mime) {
    throw new Error("Image contents do not match the declared file type.");
  }
  if (
    !Number.isInteger(info.width) ||
    !Number.isInteger(info.height) ||
    info.width < 16 ||
    info.height < 16 ||
    info.width * info.height > MAX_PIXELS
  ) {
    throw new Error("Image dimensions are invalid or exceed 40 megapixels.");
  }
  return { ...info, bytes: buffer.length };
}

function tokens(value) {
  return clean(value)
    .toLocaleLowerCase("en-US")
    .replace(/[^a-z0-9+%]+/g, " ")
    .split(/\s+/)
    .filter((token) => token.length >= 2);
}

const MATCH_STOP_WORDS = new Set([
  "the",
  "and",
  "for",
  "with",
  "from",
  "item",
  "weapon",
  "damage",
  "level",
  "legendary",
  "licensed",
  "part",
  "fires",
]);
const GENERIC_IDENTITY_WORDS = new Set([
  "atlas",
  "daedalus",
  "hyperion",
  "jakobs",
  "maliwan",
  "order",
  "ripper",
  "tediore",
  "torgue",
  "vladof",
  "sniper",
  "rifle",
  "pistol",
  "shotgun",
  "shield",
  "grenade",
  "ordnance",
  "repkit",
  "enhancement",
  "class",
  "mod",
  "heavy",
  "smg",
]);

function distinctiveTokens(value) {
  return tokens(value).filter((token) => token.length >= 3 && !MATCH_STOP_WORDS.has(token));
}

function decodePng(buffer) {
  try {
    const png = PNG.sync.read(buffer);
    return png && png.width > 0 && png.height > 0 ? png : null;
  } catch {
    return null;
  }
}

function makeHeaderOcrBuffer(png) {
  if (!png) return null;
  const sourceHeight = Math.max(1, Math.min(png.height, Math.round(png.height * 0.24), 150));
  const scale = 3;
  const out = new PNG({ width: png.width * scale, height: sourceHeight * scale });
  for (let y = 0; y < sourceHeight; y += 1) {
    for (let x = 0; x < png.width; x += 1) {
      const src = (y * png.width + x) * 4;
      const luminance =
        (png.data[src] * 0.3) + (png.data[src + 1] * 0.59) + (png.data[src + 2] * 0.11);
      const ink = png.data[src + 3] > 32 && luminance >= 100;
      for (let oy = 0; oy < scale; oy += 1) {
        for (let ox = 0; ox < scale; ox += 1) {
          const dest = (((y * scale) + oy) * out.width + (x * scale) + ox) * 4;
          out.data[dest] = ink ? 0 : 255;
          out.data[dest + 1] = ink ? 0 : 255;
          out.data[dest + 2] = ink ? 0 : 255;
          out.data[dest + 3] = 255;
        }
      }
    }
  }
  return PNG.sync.write(out);
}

function inferRarityFromCardColor(png) {
  if (!png) return null;
  const top = Math.max(1, Math.min(png.height, Math.round(png.height * 0.45)));
  const counts = {
    Legendary: 0,
    Pearlescent: 0,
    Epic: 0,
    Rare: 0,
    Uncommon: 0,
  };
  let opaque = 0;
  for (let y = 0; y < top; y += 1) {
    for (let x = 0; x < png.width; x += 1) {
      const offset = (y * png.width + x) * 4;
      const r = png.data[offset];
      const g = png.data[offset + 1];
      const b = png.data[offset + 2];
      if (png.data[offset + 3] < 64) continue;
      opaque += 1;
      const max = Math.max(r, g, b);
      const min = Math.min(r, g, b);
      if ((max - min) < 55 || max < 105) continue;
      if (r >= 175 && g >= 115 && b <= 90 && r >= (b * 1.8) && g >= (b * 1.45)) {
        counts.Legendary += 1;
      } else if (r >= 105 && b >= 115 && g >= 70 && Math.abs(r - b) <= 85) {
        counts.Pearlescent += 1;
      } else if (r >= 105 && b >= 120 && g <= 125) {
        counts.Epic += 1;
      } else if (b >= 125 && b >= (r * 1.25) && b >= (g * 1.12)) {
        counts.Rare += 1;
      } else if (g >= 115 && g >= (r * 1.2) && g >= (b * 1.1)) {
        counts.Uncommon += 1;
      }
    }
  }
  const ranked = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const [value, evidencePixels] = ranked[0];
  const runnerUp = ranked[1]?.[1] || 0;
  const minimum = Math.max(45, Math.round(opaque * 0.00035));
  if (evidencePixels < minimum || evidencePixels < runnerUp * 1.35) return null;
  return {
    value,
    source: "card_color",
    confidence: Math.min(0.99, 0.72 + Math.min(0.25, (evidencePixels / Math.max(1, opaque)) * 18)),
    evidence_pixels: evidencePixels,
  };
}

function headerItemType(headerText) {
  const lower = clean(headerText).toLowerCase();
  const types = [
    ["Assault Rifle", /\bassault\s+rifle\b/],
    ["Sniper Rifle", /\bsniper(?:\s+rifle)?\b/],
    ["Submachine Gun", /\b(?:submachine\s+gun|smg)\b/],
    ["Heavy Gun Ordnance", /\bheavy\s+gun\s+ordnance\b/],
    ["Heavy Weapon", /\b(?:heavy\s+weapon|launcher)\b/],
    ["Ordnance", /\bordnance\b/],
    ["Class Mod", /\bclass\s+mod\b/],
    ["Enhancement", /\benhancement\b/],
    ["Grenade", /\bgrenade\b/],
    ["Repkit", /\b(?:repkit|repair\s+kit)\b/],
    ["Shield", /\bshield\b/],
    ["Shotgun", /\bshotgun\b/],
    ["Pistol", /\bpistol\b/],
  ];
  return types.find(([, pattern]) => pattern.test(lower))?.[0] || "";
}

function headerTitle(headerText, itemType) {
  const excluded =
    /^(?:lvl|level|lv[il1])\b|(?:sniper|assault)\s+rifle|\b(?:shotgun|pistol|launcher|shield|grenade|ordnance|heavy\s+gun\s+ordnance|repkit|enhancement|class\s+mod|smg)\b|\bdps\b/i;
  const lines = clean(headerText)
    .split(/\r?\n/)
    .map((line) => line.replace(/[|[\]{}<>«»]+/g, " ").replace(/\s+/g, " ").trim())
    .filter((line) => line.length >= 4 && !excluded.test(line) && !/^\d[\d,\s.]*$/.test(line));
  const title = clean(lines[0])
    .replace(/^[^A-Za-z0-9]+/, "")
    .replace(/[^A-Za-z0-9)'’\- ]+$/, "");
  return title && !title.toLowerCase().includes(clean(itemType).toLowerCase()) ? title : "";
}

function visibleLicensedParts(text, { manufacturer = "", itemType = "" } = {}) {
  const flat = clean(text).toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ");
  const parts = [];
  const jakobsSniper =
    clean(manufacturer).toLowerCase() === "jakobs" &&
    /sniper/i.test(clean(itemType));
  const ammoKinds = [
    ["assault rifle", "Assault Rifle"],
    ["pistol", "Pistol"],
    ["shotgun", "Shotgun"],
    ["smg", "SMG"],
    ["sniper rifle", "Sniper Rifle"],
  ];
  if (flat.includes("daedalus licensed multi loader")) {
    const ammo = ammoKinds.find(([needle]) =>
      flat.includes(`secondary fire consumes ${needle} ammo`) ||
      flat.includes(`${needle} ammo`)
    );
    if (ammo) {
      parts.push({
        label: `Daedalus-Licensed Multi-Loader · ${ammo[1]} Ammo`,
        id_raw: jakobsSniper && ammo[0] === "shotgun" ? "24:70" : "",
        match_words: ["daedalus", ammo[0], "ammo"],
        source: "visible_card_text",
      });
    }
  }
  if (
    flat.includes("torgue licensed impact magazine") &&
    (flat.includes("gyrojet") || flat.includes("gyrojets"))
  ) {
    parts.push({
      label: "Torgue-Licensed Impact Magazine · Gyrojets",
      id_raw: jakobsSniper ? "24:18" : "",
      match_words: ["torgue", "impact", "gyrojet"],
      source: "visible_card_text",
    });
  }
  return parts;
}

function extractVisibleAttributes(text, options = {}) {
  const headerText = clean(options.headerText);
  const colorRarity = options.colorRarity || null;
  const raw = clean(text);
  const lines = raw
    .split(/\r?\n/)
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .slice(0, 160);
  const lower = raw.toLocaleLowerCase("en-US");
  const manufacturers = [
    "Atlas",
    "Daedalus",
    "Hyperion",
    "Jakobs",
    "Maliwan",
    "Order",
    "Ripper",
    "Tediore",
    "Torgue",
    "Vladof",
  ];
  const itemTypes = [
    "Assault Rifle",
    "Class Mod",
    "Enhancement",
    "Grenade",
    "Heavy Weapon",
    "Ordnance",
    "Pistol",
    "Repkit",
    "Repair Kit",
    "Shield",
    "Shotgun",
    "SMG",
    "Sniper",
  ];
  const rarities = ["Pearlescent", "Legendary", "Epic", "Rare", "Uncommon", "Common"];
  const firstMatch = (list) => list.find((value) => lower.includes(value.toLowerCase())) || "";
  const manufacturerHits = manufacturers.filter((value) => lower.includes(value.toLowerCase()));
  const nativeManufacturerHits = manufacturers.filter((value) =>
    lines.some((line) => {
      const index = line.toLowerCase().indexOf(value.toLowerCase());
      if (index < 0) return false;
      const before = line.slice(Math.max(0, index - 16), index).toLowerCase();
      const after = line.slice(index + value.length, index + value.length + 12).toLowerCase();
      return !before.includes("licensed") && !after.includes("licensed");
    })
  );
  const standaloneManufacturer = [...lines]
    .reverse()
    .map((line) =>
      manufacturers.find((value) => {
        const normalized = line.toLowerCase().replace(/[^a-z]+/g, " ").trim();
        return normalized === value.toLowerCase();
      })
    )
    .find(Boolean);
  const manufacturer =
    standaloneManufacturer ||
    (nativeManufacturerHits.length === 1 ? nativeManufacturerHits[0] : "") ||
    (manufacturerHits.length === 1 ? manufacturerHits[0] : "");
  const levelMatch = `${headerText}\n${raw}`.match(
    /\b(?:item\s*)?(?:lvl|level|lv[il1])\s*[:.]?\s*(\d{1,3})\b/i
  );
  const statMatches = [];
  const statRe =
    /\b(damage|dps|accuracy|handling|reload|fire\s*rate|magazine|capacity|radius|cooldown)\s*[:.]?\s*([+\-]?\d[\d,.]*%?)/gi;
  for (const match of raw.matchAll(statRe)) {
    statMatches.push({ label: match[1].replace(/\s+/g, " "), value: match[2] });
    if (statMatches.length >= 24) break;
  }
  const titleCandidates = lines
    .filter(
      (line) =>
        line.length >= 3 &&
        line.length <= 80 &&
        !/\b(?:damage|dps|accuracy|handling|reload|fire rate|magazine|level|lvl|licensed|critical hits?|ammo|projectiles?)\b/i.test(line) &&
        !/^@U/i.test(line)
    )
    .slice(0, 8);
  const perkLines = lines
    .filter((line) =>
      /\b(?:licensed|critical hits?|ricochet|projectiles?|ammo|magazine|secondary fire|firmware|class mod|passive|skill|perk)\b/i.test(
        line
      )
    )
    .slice(0, 20);
  const flavorLines = lines
    .filter(
      (line) =>
        line.length >= 12 &&
        !titleCandidates.includes(line) &&
        !perkLines.includes(line) &&
        !/\b(?:damage|dps|accuracy|handling|reload|fire rate|magazine|level|lvl)\b/i.test(line)
    )
    .slice(0, 8);
  const topCardText = lines
    .slice(0, 8)
    .filter((line) => !/\b(?:licensed|ammo|critical hits?|projectiles?|secondary fire)\b/i.test(line))
    .join("\n");
  const reliableItemType = headerItemType(headerText) || headerItemType(topCardText);
  const visibleRarity = firstMatch(rarities);
  return {
    text: raw,
    header_text: headerText,
    lines,
    title_candidates: [
      headerTitle(headerText, reliableItemType),
      ...titleCandidates,
    ].filter(Boolean),
    manufacturer,
    manufacturers: manufacturerHits,
    item_type: reliableItemType || firstMatch(itemTypes),
    item_type_source: headerItemType(headerText)
      ? "card_header"
      : (reliableItemType ? "top_card_text" : "visible_text"),
    rarity: visibleRarity || colorRarity?.value || "",
    rarity_source: visibleRarity ? "visible_text" : (colorRarity?.source || ""),
    rarity_confidence: visibleRarity ? 0.98 : (colorRarity?.confidence || null),
    rarity_evidence_pixels: colorRarity?.evidence_pixels || 0,
    level: levelMatch ? Number(levelMatch[1]) : null,
    stats: statMatches,
    perks: perkLines,
    flavor_lines: flavorLines,
    element: lines.map((line) => line.match(/^(?:[\d,.]+\s+)?(Radiation|Shock|Cryo|Corrosive|Fire|Incendiary)(?:\s+Damage)?(?:\s+[\d,.]+(?:\/s)?)?$/i))
      .find(Boolean)?.[1] || "",
    visible_parts: visibleLicensedParts(raw, {
      manufacturer,
      itemType: reliableItemType || firstMatch(itemTypes),
    }),
  };
}

function extractSerialStrings(text) {
  const out = [];
  const seen = new Set();
  const regex = /@U[^\s"<>]{8,200000}/g;
  for (const match of clean(text).matchAll(regex)) {
    const value = String(match[0] || "").replace(/[.;]+$/, "");
    if (!seen.has(value)) {
      seen.add(value);
      out.push(value);
    }
    if (out.length >= 8) break;
  }
  return out;
}

async function recognizeImage(buffer) {
  const { createWorker, OEM, PSM } = require("tesseract.js");
  const lang = require("@tesseract.js-data/eng");
  const png = decodePng(buffer);
  const worker = await createWorker("eng", OEM.LSTM_ONLY, {
    langPath: lang.langPath,
    gzip: lang.gzip,
    cacheMethod: "none",
    logger: () => {},
  });
  try {
    await worker.setParameters({
      tessedit_pageseg_mode: PSM.AUTO,
      preserve_interword_spaces: "1",
    });
    const result = await worker.recognize(buffer, { rotateAuto: true });
    let headerText = "";
    let headerConfidence = 0;
    const headerBuffer = makeHeaderOcrBuffer(png);
    if (headerBuffer) {
      await worker.setParameters({
        tessedit_pageseg_mode: PSM.SPARSE_TEXT,
        preserve_interword_spaces: "1",
      });
      const header = await worker.recognize(headerBuffer);
      headerText = clean(header?.data?.text);
      headerConfidence = Number(header?.data?.confidence || 0);
    }
    return {
      text: clean(result?.data?.text),
      confidence: Number(result?.data?.confidence || 0),
      header_text: headerText,
      header_confidence: headerConfidence,
      card_color_rarity: inferRarityFromCardColor(png),
    };
  } finally {
    await worker.terminate();
  }
}

async function identifyImageBuffer(buffer, declaredMime = "") {
  const image = inspectImageBuffer(buffer, declaredMime);
  const ocr = await recognizeImage(buffer);
  const combinedText = [ocr.header_text, ocr.text].filter(Boolean).join("\n");
  const extracted = extractVisibleAttributes(combinedText, {
    headerText: ocr.header_text,
    colorRarity: ocr.card_color_rarity,
  });
  const exactItems = [];
  for (const serial of extractSerialStrings(ocr.text)) {
    const analysis = await analyzeItem(serial);
    if (analysis.ok) exactItems.push(analysis);
  }
  const candidates = exactItems.length ? [] : rankCandidates(extracted, loadOfflineCandidates());
  const visibleIdentity = [
    extracted.title_candidates?.[0],
    extracted.rarity,
    extracted.manufacturer,
    extracted.item_type,
  ].filter(Boolean).join(" · ");
  return {
    ok: true,
    image,
    ocr,
    extracted,
    exact_items: exactItems,
    candidates,
    exact: exactItems.length > 0,
    message: exactItems.length
      ? `Found ${exactItems.length} exact, validated serial${exactItems.length === 1 ? "" : "s"}.`
      : visibleIdentity
        ? `Read visible card: ${visibleIdentity}. Hidden parts still need confirmation.`
        : "No exact serial or reliable card identity was visible.",
  };
}

function loadOfflineCandidates() {
  if (offlineCandidates) return offlineCandidates;
  offlineCandidates = [];
  const root = sdkmodRoot();
  if (!root) return offlineCandidates;
  const sources = [
    {
      path: path.join(root, "squ1ggs_lootlemon_codes.json"),
      rows: (data) => data?.entries,
      source: "known_item_catalog",
    },
  ];
  for (const source of sources) {
    try {
      const data = JSON.parse(fs.readFileSync(source.path, "utf8"));
      const rows = source.rows(data);
      if (!Array.isArray(rows)) continue;
      for (const row of rows) {
        if (!row || typeof row !== "object") continue;
        offlineCandidates.push({
          ...row,
          item_type: row.item_type || row.category || "",
          _source: source.source,
        });
      }
    } catch {
      /* Optional catalog absent: OCR still returns visible attributes. */
    }
  }
  return offlineCandidates;
}

async function identifyImageFile(filePath) {
  const target = path.resolve(clean(filePath));
  const buffer = fs.readFileSync(target);
  return identifyImageBuffer(buffer, "");
}

function fieldValue(row, ...keys) {
  for (const key of keys) {
    const value = row?.[key] ?? row?.card?.[key] ?? row?.raw?.[key];
    if (value != null && clean(value)) return clean(value);
  }
  return "";
}

function fieldText(row, ...keys) {
  const values = [];
  for (const key of keys) {
    const value = row?.[key] ?? row?.card?.[key] ?? row?.raw?.[key];
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item && typeof item === "object") {
          values.push(item.name, item.label, item.effect, item.code);
        } else {
          values.push(item);
        }
      }
    } else if (value && typeof value === "object") {
      values.push(value.name, value.label, value.effect, value.code);
    } else {
      values.push(value);
    }
  }
  return values.map(clean).filter(Boolean).join(" ");
}

function rankCandidates(extracted, inputRows) {
  const attrs = extracted && typeof extracted === "object" ? extracted : {};
  const rows = Array.isArray(inputRows) ? inputRows.slice(0, 5000) : [];
  const titleTokens = new Set(
    distinctiveTokens((attrs.title_candidates || []).join(" ")).filter(
      (token) => !GENERIC_IDENTITY_WORDS.has(token)
    )
  );
  const allTokens = new Set(distinctiveTokens(attrs.text));
  const results = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const name = fieldValue(row, "full_name", "display_name", "title", "name", "label");
    const serial = fieldValue(row, "serial", "code", "base85");
    if (!name && !serial) continue;
    const evidence = [];
    let score = 0;
    const nameTokens = distinctiveTokens(name).filter(
      (token) => !GENERIC_IDENTITY_WORDS.has(token)
    );
    const titleHits = nameTokens.filter((token) => titleTokens.has(token));
    const textHits = nameTokens.filter((token) => allTokens.has(token));
    const exactName = Boolean(
      name &&
        (attrs.title_candidates || []).some(
          (title) => clean(title).toLowerCase() === name.toLowerCase()
        )
    );
    if (exactName) {
      score += 70;
      evidence.push("visible name matches");
    } else {
      score += titleHits.length * 12 + textHits.length * 3;
      if (titleHits.length) evidence.push(`${titleHits.length} name word${titleHits.length === 1 ? "" : "s"} match`);
    }
    const detailText = fieldText(
      row,
      "red_text",
      "flavor_text",
      "parts",
      "part_names",
      "perk_rows",
      "perks",
      "effects",
      "description"
    );
    const detailHits = [...new Set(distinctiveTokens(detailText).filter((token) => allTokens.has(token)))];
    if (detailHits.length) {
      score += Math.min(36, detailHits.length * 6);
      evidence.push(`${detailHits.length} visible perk/part word${detailHits.length === 1 ? "" : "s"} match`);
    }
    for (const [key, keys, weight] of [
      ["manufacturer", ["manufacturer", "mfr"], 12],
      ["item_type", ["item_type", "type", "type_label", "category"], 14],
      ["rarity", ["rarity"], 10],
    ]) {
      const wanted = clean(attrs[key]);
      const actual = fieldValue(row, ...keys);
      if (wanted && actual && normContains(actual, wanted)) {
        score += weight;
        evidence.push(`${key.replace("_", " ")} matches`);
      }
    }
    const wantedLevel = Number(attrs.level);
    const actualLevel = Number(row.level ?? row.card?.level);
    if (Number.isFinite(wantedLevel) && Number.isFinite(actualLevel)) {
      if (wantedLevel === actualLevel) {
        score += 8;
        evidence.push("level matches");
      } else {
        score -= Math.min(12, Math.abs(wantedLevel - actualLevel));
      }
    }
    if (score <= 0) continue;
    const strongIdentityEvidence =
      exactName || titleHits.length >= 1 || detailHits.length >= 2 || score >= 50;
    if (score < 24 || !strongIdentityEvidence) continue;
    results.push({
      id: fieldValue(row, "id", "key") || serial || name,
      name: name || "Unknown item",
      serial,
      manufacturer: fieldValue(row, "manufacturer", "mfr"),
      item_type: fieldValue(row, "item_type", "type", "type_label", "category"),
      rarity: fieldValue(row, "rarity"),
      level: Number.isFinite(actualLevel) ? actualLevel : null,
      score: Math.max(0, Math.round(score)),
      exact: false,
      evidence,
      visible_matches: {
        name_words: titleHits,
        detail_words: detailHits,
      },
      source: fieldValue(row, "_source", "source", "catalog") || "catalog",
    });
  }
  results.sort((a, b) => b.score - a.score || a.name.localeCompare(b.name));
  return results.slice(0, 16);
}

function normContains(left, right) {
  const a = tokens(left).join(" ");
  const b = tokens(right).join(" ");
  return Boolean(a && b && (a.includes(b) || b.includes(a)));
}

module.exports = {
  MAX_BYTES,
  extractSerialStrings,
  extractVisibleAttributes,
  identifyImageBuffer,
  identifyImageFile,
  inspectImageBuffer,
  rankCandidates,
  visibleLicensedParts,
};
