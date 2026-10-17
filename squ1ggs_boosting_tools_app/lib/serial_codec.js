"use strict";

/**
 * Small, deterministic BL4 @U decoder for the desktop app.
 *
 * This mirrors SQBT's own serial_converter token format so exact identity and
 * catalog-backed part metadata remain available when system Python is absent.
 * It deliberately does not synthesize stats or hidden rolls.
 */

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const ALPHABET =
  "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{/}~";
const REVERSE = new Map([...ALPHABET].map((char, index) => [char, index]));
const TOK_SEP1 = 0;
const TOK_SEP2 = 1;
const TOK_VARINT = 2;
const TOK_VARBIT = 3;
const TOK_PART = 4;
const TOK_STRING = 5;

const MAKERS = {
  DAD: "Daedalus",
  JAK: "Jakobs",
  ORD: "Order",
  TED: "Tediore",
  TOR: "Torgue",
  VLA: "Vladof",
  MAL: "Maliwan",
  BOR: "Ripper",
  RIP: "Ripper",
  COV: "CoV",
  ATL: "Atlas",
  HYP: "Hyperion",
  C4SH: "C4SH",
};
const TYPES = {
  PS: "Pistol",
  SG: "Shotgun",
  AR: "Assault Rifle",
  SMG: "SMG",
  SM: "SMG",
  SR: "Sniper",
  HW: "Heavy Weapon",
  HEAVY: "Heavy Weapon",
  SHIELD: "Shield",
  ARMOR_SHIELD: "Shield",
  ENERGY_SHIELD: "Shield",
  GADGET: "Ordnance",
  GRENADE_GADGET: "Ordnance",
  TURRET_GADGET: "Ordnance",
  HEAVY_WEAPON_GADGET: "Ordnance",
  TERMINAL_GADGET: "Ordnance",
  TERMINAL_BARRIER: "Ordnance",
  BARRIER: "Ordnance",
  ORDNANCE: "Ordnance",
  ENHANCEMENT: "Enhancement",
  REPAIR_KIT: "Repkit",
  REPKIT: "Repkit",
  CLASS_MOD: "Classmod",
  CLASSMOD: "Classmod",
};
const CLASSES = {
  siren: "Siren",
  dark_siren: "Siren",
  forgeknight: "Paladin",
  paladin: "Paladin",
  exo_soldier: "Exo Soldier",
  gravitar: "Gravitar",
  ai: "AI",
  c4sh: "C4SH",
  robodealer: "C4SH",
  corpohacker: "Loveless",
  corpo_hacker: "Loveless",
  hacker: "Loveless",
  loveless: "Loveless",
};

let catalogCache;

function mirror(value, width) {
  let output = 0;
  for (let index = 0; index < width; index += 1) {
    output = output * 2 + (Math.floor(value / 2 ** index) % 2);
  }
  return output;
}

function decodeBase85(serial) {
  const code = String(serial || "").trim();
  if (!code.startsWith("@U")) throw new Error("serial must start with @U");
  const body = code.slice(2).replace(/\|/g, "/");
  if (!body) throw new Error("serial payload is empty");
  const output = [];
  for (let at = 0; at < body.length; ) {
    let value = 0;
    let count = 0;
    while (at < body.length && count < 5) {
      const char = body[at];
      at += 1;
      if (!REVERSE.has(char)) {
        throw new Error(`invalid Base85 character at index ${at - 1}`);
      }
      value = value * 85 + REVERSE.get(char);
      count += 1;
    }
    for (let pad = count; pad < 5; pad += 1) value = value * 85 + 84;
    const byteCount = count === 5 ? 4 : count - 1;
    for (const shift of [24, 16, 8, 0].slice(0, byteCount)) {
      output.push(mirror(Math.floor(value / 2 ** shift) % 256, 8));
    }
  }
  return Buffer.from(output);
}

function encodeBase85(input) {
  const data = Buffer.from(input || []);
  let output = "";
  for (let at = 0; at < data.length; at += 4) {
    const count = Math.min(4, data.length - at);
    let value = 0;
    for (let index = 0; index < 4; index += 1) {
      value = value * 256 + (index < count ? mirror(data[at + index], 8) : 0);
    }
    const chars = [];
    for (const divisor of [85 ** 4, 85 ** 3, 85 ** 2, 85, 1]) {
      const digit = Math.floor(value / divisor);
      value %= divisor;
      chars.push(ALPHABET[digit]);
    }
    output += chars.slice(0, count + 1).join("");
  }
  return `@U${output}`;
}

class BitReader {
  constructor(data) {
    this.data = Buffer.from(data);
    this.position = 0;
  }

  read() {
    if (this.position >= this.data.length * 8) throw new Error("unexpected end of bitstream");
    const byteIndex = Math.floor(this.position / 8);
    const bitIndex = 7 - (this.position % 8);
    this.position += 1;
    return (this.data[byteIndex] >> bitIndex) & 1;
  }

  readN(count) {
    if (count <= 0 || count > 32 || this.position + count > this.data.length * 8) {
      throw new Error("unexpected end of bitstream");
    }
    let value = 0;
    for (let index = 0; index < count; index += 1) value = value * 2 + this.read();
    return value;
  }
}

function readToken(reader, allowEof = false) {
  if (allowEof && reader.position >= reader.data.length * 8) return null;
  // A final zero bit is byte padding, not an incomplete two-bit token.
  if (allowEof && reader.position === reader.data.length * 8 - 1 &&
      (reader.data[reader.data.length - 1] & 1) === 0) return null;
  const first = reader.read();
  const second = reader.read();
  const short = first * 2 + second;
  if (short === 0) return TOK_SEP1;
  if (short === 1) return TOK_SEP2;
  const full = short * 2 + reader.read();
  if (full === 4) return TOK_VARINT;
  if (full === 6) return TOK_VARBIT;
  if (full === 5) return TOK_PART;
  if (full === 7) return TOK_STRING;
  throw new Error("invalid token");
}

function readVarint(reader) {
  let output = 0;
  let bits = 0;
  for (let block = 0; block < 4; block += 1) {
    output += mirror(reader.readN(4), 4) * 2 ** bits;
    bits += 4;
    if (reader.read() === 0) break;
  }
  return output;
}

function readVarbit(reader) {
  const length = mirror(reader.readN(5), 5);
  let value = 0;
  for (let index = 0; index < length; index += 1) value += reader.read() * 2 ** index;
  return value;
}

function readPart(reader) {
  const index = readVarint(reader);
  if (reader.read() === 1) {
    const value = readVarint(reader);
    if (reader.read() || reader.read() || reader.read()) {
      throw new Error("bad part integer terminator");
    }
    return { index, subtype: "int", value };
  }
  const flags = reader.readN(2);
  if (flags === 2) return { index, subtype: "none" };
  if (flags !== 1 || readToken(reader) !== TOK_SEP2) {
    throw new Error("invalid part encoding");
  }
  const values = [];
  while (true) {
    const token = readToken(reader);
    if (token === TOK_SEP1) break;
    if (token === TOK_VARINT) values.push(readVarint(reader));
    else if (token === TOK_VARBIT) values.push(readVarbit(reader));
    else throw new Error("unexpected token in part list");
  }
  return { index, subtype: "list", values };
}

function readString(reader) {
  const length = readVarint(reader);
  let output = "";
  for (let index = 0; index < length; index += 1) {
    output += String.fromCharCode(mirror(reader.readN(7), 7));
  }
  return output;
}

function parseSerialBytes(data) {
  const reader = new BitReader(data);
  for (const expected of [0, 0, 1, 0, 0, 0, 0]) {
    if (reader.read() !== expected) throw new Error("bad serial header");
  }
  const blocks = [];
  let trailingTerms = 0;
  while (reader.position < reader.data.length * 8) {
    const token = readToken(reader, true);
    if (token == null) break;
    const block = { token };
    trailingTerms = token === TOK_SEP1 ? trailingTerms + 1 : 0;
    if (token === TOK_VARINT) block.value = readVarint(reader);
    else if (token === TOK_VARBIT) block.value = readVarbit(reader);
    else if (token === TOK_PART) block.part = readPart(reader);
    else if (token === TOK_STRING) block.value = readString(reader);
    blocks.push(block);
  }
  if (trailingTerms > 1) blocks.splice(blocks.length - trailingTerms + 1);
  return blocks;
}

function partText(part) {
  if (part.subtype === "none") return `{${part.index}}`;
  if (part.subtype === "int") return `{${part.index}:${part.value}}`;
  return `{${part.index}:[${part.values.join(" ")}]}`;
}

function blocksToHuman(blocks) {
  const output = [];
  blocks.forEach((block, index) => {
    if (block.token === TOK_SEP1) output.push("|");
    else if (block.token === TOK_SEP2) output.push(",");
    else if (block.token === TOK_VARINT || block.token === TOK_VARBIT) {
      if (index > 0) output.push(" ");
      output.push(String(block.value));
    } else if (block.token === TOK_PART) {
      if (index > 0) output.push(" ");
      output.push(partText(block.part));
    } else if (block.token === TOK_STRING) {
      if (index > 0) output.push(" ");
      output.push(JSON.stringify(block.value));
    }
  });
  return output.join("");
}

function catalogPath(root) {
  return path.join(root || "", "gzo_parts_map.json");
}

function loadCatalog(root) {
  const target = catalogPath(root);
  if (catalogCache?.target === target) return catalogCache;
  const raw = JSON.parse(fs.readFileSync(target, "utf8"));
  const byId = new Map();
  for (const [key, table] of Object.entries(raw || {})) {
    const match = /^\s*(\d+)\s*\|\s*(.+?)\s*$/.exec(key);
    if (match && table && typeof table === "object") {
      byId.set(Number(match[1]), { label: match[2], table });
    }
  }
  catalogCache = { target, byId };
  return catalogCache;
}

function titleCase(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .trim()
    .split(/\s+/)
    .map((word) => (["smg", "ai", "cov"].includes(word.toLowerCase()) ? word.toUpperCase() : `${word[0]?.toUpperCase() || ""}${word.slice(1).toLowerCase()}`))
    .join(" ");
}

function typeInfo(label) {
  const raw = String(label || "").trim();
  const lower = raw.toLowerCase();
  const info = { set: raw, manufacturer: "", item_type: "", character_class: "" };
  if (lower.includes("classmod") || lower.includes("class_mod")) {
    info.item_type = "Classmod";
    const tail = lower.replace("classmod", "").replace("class_mod", "").replace(/^_+|_+$/g, "");
    info.character_class = CLASSES[tail] || titleCase(tail);
    return info;
  }
  const pieces = raw.split(/[_\s]+/).filter(Boolean);
  for (const piece of pieces) {
    const upper = piece.toUpperCase();
    if (!info.manufacturer && MAKERS[upper]) info.manufacturer = MAKERS[upper];
    else if (!info.manufacturer && upper.startsWith("BOR")) info.manufacturer = "Ripper";
  }
  for (let index = 1; index < pieces.length; index += 1) {
    const suffix = pieces.slice(index).join("_").toUpperCase();
    if (TYPES[suffix]) {
      info.item_type = TYPES[suffix];
      break;
    }
  }
  if (!info.item_type && TYPES[pieces[0]?.toUpperCase()]) {
    info.item_type = TYPES[pieces[0].toUpperCase()];
  }
  if (!info.item_type) {
    for (const [hint, itemType] of [
      ["classmod", "Classmod"],
      ["class_mod", "Classmod"],
      ["repair_kit", "Repkit"],
      ["repkit", "Repkit"],
      ["enhancement", "Enhancement"],
      ["gadget", "Ordnance"],
      ["shield", "Shield"],
    ]) {
      if (lower.includes(hint)) {
        info.item_type = itemType;
        break;
      }
    }
  }
  return info;
}

function categoryForType(itemType) {
  if (["Pistol", "Shotgun", "Assault Rifle", "SMG", "Sniper", "Heavy Weapon"].includes(itemType)) return "Guns";
  if (itemType === "Shield") return "Shields";
  if (itemType === "Ordnance") return "Ordnance";
  if (itemType === "Repkit") return "Repkits";
  if (itemType === "Enhancement") return "Enhancements";
  if (itemType === "Classmod") return "Class Mods";
  return "Other";
}

function rarityFromParts(parts) {
  // Use the first composition in serial order, including foreign pearl hooks.
  for (const part of parts) {
    const match = String(part).match(/(?:^|\.)(?:base_)?comp_0([1-6])_/i);
    if (match) return ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Pearlescent"][Number(match[1]) - 1];
  }
  const joined = parts.join(" ").toLowerCase();
  for (const label of ["Pearlescent", "Legendary", "Epic", "Rare", "Uncommon", "Common"]) {
    if (new RegExp(`(?:^|[_.\\s])${label.toLowerCase()}(?:[_.\\s]|$)`).test(joined)) return label;
  }
  return "";
}

function damageTypeFromParts(parts) {
  const joined = parts.join(".").toLowerCase();
  for (const [pattern, label] of [
    [/(?:^|[_.])(?:incendiary|fire)(?:[_.]|$)/, "Fire"],
    [/(?:^|[_.])(?:shock|electric)(?:[_.]|$)/, "Shock"],
    [/(?:^|[_.])cryo(?:[_.]|$)/, "Cryo"],
    [/(?:^|[_.])corrosive(?:[_.]|$)/, "Corrosive"],
    [/(?:^|[_.])(?:radiation|rad)(?:[_.]|$)/, "Radiation"],
    [/(?:^|[_.])kinetic(?:[_.]|$)/, "Kinetic"],
  ]) {
    if (pattern.test(joined)) return label;
  }
  return "";
}

function decodeSerialCard(serial, root) {
  const code = String(serial || "").trim();
  const bytes = decodeBase85(code);
  const blocks = parseSerialBytes(bytes);
  const human = blocksToHuman(blocks);
  const header = /^\s*(\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(\d+)/.exec(human);
  if (!header) throw new Error("item header is incomplete");
  const typeId = Number(header[1]);
  const level = Number(header[4]);
  const { byId } = loadCatalog(root);
  const own = byId.get(typeId);
  if (!own) throw new Error(`unknown inventory root ${typeId}`);
  const info = typeInfo(own.label);
  const rootedParts = [];
  const flatParts = [];
  const addPart = (setId, partId, includeFlat = true) => {
    const set = byId.get(Number(setId));
    const name = set?.table?.[String(Number(partId))];
    if (!name) return;
    rootedParts.push(name.includes(".") || !set.label ? name : `${set.label}.${name}`);
    if (includeFlat) {
      flatParts.push(
        info.item_type === "Classmod" && set.label.toLowerCase().startsWith("classmod_") && !name.includes(".")
          ? `${set.label}.${name}`
          : name
      );
    }
  };
  for (const block of blocks) {
    const part = block.part;
    if (!part) continue;
    if (part.subtype === "none") addPart(typeId, part.index);
    else if (part.subtype === "int") addPart(part.index, part.value);
    else {
      const include = info.item_type === "Classmod" &&
        ([234, 247, typeId].includes(Number(part.index)));
      for (const value of part.values) addPart(part.index, value, include);
    }
  }
  const partNames = [...new Set(flatParts)].slice(0, 96);
  const fallbackName =
    info.item_type === "Classmod"
      ? [info.character_class, "Class Mod"].filter(Boolean).join(" ")
      : [info.manufacturer, info.item_type || info.character_class].filter(Boolean).join(" ");
  const canonical = encodeBase85(bytes);
  return {
    serial: code,
    decoded_human: human,
    type_id: String(typeId),
    set: info.set,
    manufacturer: info.manufacturer,
    item_type: info.item_type,
    type: info.item_type,
    character_class: info.character_class,
    category: categoryForType(info.item_type),
    rarity: rarityFromParts(rootedParts),
    damage_type: damageTypeFromParts(rootedParts),
    element: damageTypeFromParts(rootedParts),
    display_name: fallbackName || titleCase(info.set),
    unique_name: "",
    level,
    part_names: partNames,
    name_parts: rootedParts.slice(0, 400),
    perk_rows: [],
    stats: [],
    meta_ok: true,
    identity: {
      serial_sha256: crypto.createHash("sha256").update(code, "utf8").digest("hex"),
      payload_sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
      round_trip_exact: canonical === code,
      readable: true,
    },
  };
}

module.exports = {
  blocksToHuman,
  decodeBase85,
  decodeSerialCard,
  encodeBase85,
  parseSerialBytes,
};
