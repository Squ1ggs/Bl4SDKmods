"use strict";

/**
 * Offline weapon/equipment card stats via Nexus data (closest to live BaseValues).
 * Uses mined LegitItems tables — not the coarse SQBT part-table estimate.
 */

const fs = require("fs");
const path = require("path");

let _data = null;
let _dataError = "";
let _legitItemsPath = "";

function resolveLegitItemsPath() {
  const candidates = [
    process.env.SQBT_LEGIT_ITEMS,
    path.join(__dirname, "..", "resources", "LegitItems"),
    path.join(process.resourcesPath || "", "LegitItems"),
    path.join(process.resourcesPath || "", "app", "resources", "LegitItems"),
    path.join(__dirname, "resources", "LegitItems"),
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      if (candidate && fs.existsSync(candidate) && fs.existsSync(path.join(candidate, "Nexus-Data-attribute0.json"))) {
        return candidate;
      }
    } catch {
      /* ignore */
    }
  }
  return "";
}

function ensureStatData() {
  if (_data) return _data;
  if (_dataError) return null;
  const { loadStatData } = require("./nexus/serial_card_stats");
  _legitItemsPath = resolveLegitItemsPath();
  if (!_legitItemsPath) {
    _dataError = "LegitItems / Nexus data not found";
    return null;
  }
  try {
    _data = loadStatData({ legitItemsPath: _legitItemsPath });
    return _data;
  } catch (error) {
    _dataError = String(error && error.message ? error.message : error);
    return null;
  }
}

function splitPartRef(raw, fallbackSet) {
  const s = String(raw || "")
    .trim()
    .toLowerCase()
    .replace(/^"+|"+$/g, "");
  if (!s) return null;
  const leaf = s.includes(".") ? s.slice(s.lastIndexOf(".") + 1) : s;
  let root = s.includes(".") ? s.slice(0, s.lastIndexOf(".")) : String(fallbackSet || "").toLowerCase();
  // Keep real inv roots (mal_sm, weapon.part_cryo, classmod_*, shields…).
  // Manufacturer labels like "jakobs.part_barrel_01" are NOT roots — fall back to set.
  const isRealInvRoot =
    /_(ps|sg|sm|smg|ar|sr|hw)$/i.test(root) ||
    /_(?:shield|repair_kit|grenade_gadget)$/i.test(root) ||
    /^(?:weapon|shield|energy_shield|armor_shield|repair_kit|grenade_gadget|gadget)$/i.test(root) ||
    /^classmod/i.test(root);
  if (root && !isRealInvRoot && fallbackSet) {
    root = String(fallbackSet).toLowerCase();
  }
  if (!leaf) return null;
  return { root: root || String(fallbackSet || "").toLowerCase(), key: leaf.replace(/^part_/, "part_") };
}

function inferClassmodSet(partNames) {
  for (const raw of partNames || []) {
    const s = String(raw || "")
      .trim()
      .replace(/^"+|"+$/g, "");
    if (!s) continue;
    const root = s.includes(".") ? s.slice(0, s.lastIndexOf(".")) : s;
    const low = root.toLowerCase();
    if (low.startsWith("classmod_") || low === "classmod") return low;
    // CLASSMOD_CORPOHACKER → classmod_corpohacker
    if (/^classmod_/i.test(root)) return low;
  }
  return "";
}

/** Prefer explicit inv roots from part codes (jak_shield.part_*, mal_repair_kit.*, …). */
function isUsableInvSet(set) {
  const s = String(set || "")
    .trim()
    .toLowerCase();
  if (!s || s === "none" || s === "weapon" || s === "item" || s === "unknown") return false;
  // Manufacturer display names are not inv roots (jakobs ≠ jak_ps).
  if (
    /^(jakobs|maliwan|tediore|torgue|vladof|daedalus|atlas|hyperion|order|ripper|borg|cov)$/.test(
      s
    )
  ) {
    return false;
  }
  if (/^(jak|mal|ted|tor|vla|ord|dad|bor|borg|cov|hyp|atl)_/.test(s)) return true;
  if (/^classmod_/.test(s)) return true;
  if (
    /^(shield|energy_shield|armor_shield|repair_kit|grenade_gadget|gadget|heavy_weapon_gadget|turret_gadget|terminal_gadget)$/.test(
      s
    )
  ) {
    return true;
  }
  // Other set-like tokens (shared pools, DLC roots) — require an underscore, not part_/comp_.
  if (/_/.test(s) && !/^(part_|comp_)/.test(s)) return true;
  return false;
}

function inferSetFromParts(partNames) {
  const roots = [];
  for (const raw of partNames || []) {
    const s = String(raw || "")
      .trim()
      .replace(/^"+|"+$/g, "");
    if (!s || !s.includes(".")) continue;
    const root = s.slice(0, s.lastIndexOf(".")).toLowerCase();
    if (!isUsableInvSet(root)) continue;
    roots.push(root);
  }
  if (!roots.length) return "";
  // Prefer manufacturer-prefixed sets over shared pools (shield / grenade_gadget).
  const ranked = [...roots].sort((a, b) => {
    const score = (r) => {
      if (/^(jak|mal|ted|tor|vla|ord|dad|bor|borg|cov|hyp|atl)_/.test(r)) return 0;
      if (/^classmod_/.test(r)) return 1;
      return 2;
    };
    return score(a) - score(b) || a.length - b.length;
  });
  return ranked[0] || "";
}

function inferItemTypeFromParts(partNames) {
  const blob = (partNames || []).join(" ").toLowerCase();
  if (!blob.trim()) return "";
  if (/classmod_|class_mod|class\s*mod/.test(blob)) return "Classmod";
  if (/repair_kit|repkit/.test(blob)) return "Repkit";
  if (/enhancement/.test(blob)) return "Enhancement";
  // Manufacturer gun sets win over shared shield/gadget tokens that can co-exist in thin lists.
  if (/(?:^|[._])(?:ps|sg|sm|ar|sr|hw)(?:[._]|$)/.test(blob) && !/grenade_gadget|repair_kit|classmod_/.test(blob)) {
    if (/(?:^|[._])hw(?:[._]|$)/.test(blob)) return "Heavy Weapon";
    if (/(?:^|[._])sg(?:[._]|$)/.test(blob)) return "Shotgun";
    if (/(?:^|[._])sm(?:[._]|$)/.test(blob)) return "SMG";
    if (/(?:^|[._])ar(?:[._]|$)/.test(blob)) return "Assault Rifle";
    if (/(?:^|[._])ps(?:[._]|$)/.test(blob)) return "Pistol";
    if (/(?:^|[._])sr(?:[._]|$)/.test(blob)) return "Sniper";
  }
  if (/grenade_gadget|turret_gadget|terminal_gadget|heavy_weapon_gadget/.test(blob)) return "Ordnance";
  if (/energy_shield|armor_shield|[._]shield(?:[._]|$)|shield\./.test(blob)) return "Shield";
  if (/weapon_meathead|meathead_/.test(blob)) return "Heavy Gun Ordnance";
  if (/(?:^|[._])hw(?:[._]|$)/.test(blob)) return "Heavy Weapon";
  if (/(?:^|[._])sg(?:[._]|$)/.test(blob)) return "Shotgun";
  if (/(?:^|[._])sm(?:[._]|$)/.test(blob)) return "SMG";
  if (/(?:^|[._])ar(?:[._]|$)/.test(blob)) return "Assault Rifle";
  if (/(?:^|[._])ps(?:[._]|$)/.test(blob)) return "Pistol";
  if (/(?:^|[._])sr(?:[._]|$)/.test(blob)) return "Sniper";
  return "";
}

function canonItemType(itemType, partNames) {
  const t = String(itemType || "").trim();
  const lower = t.toLowerCase();
  // Explicit Class Mod / equipment from the Editor UI must win — pearl rarity hooks
  // can inject foreign gun-family tokens ({7:54} TED_SG) that would otherwise
  // make inferItemTypeFromParts report Shotgun.
  if (/class\s*mod|classmod/.test(lower)) return "Classmod";
  if (/repair\s*kit|rep\s*kit|repkit/.test(lower)) return "Repkit";
  if (/enhancement/.test(lower)) return "Enhancement";
  if (/grenade|ordnance|gadget/.test(lower) && !/heavy/.test(lower)) return "Ordnance";
  if (/shield|energy|armor/.test(lower) && !/class/.test(lower)) return "Shield";
  // Part roots are the source of truth for GZO/Serials thin labels (Grenade vs Shield).
  const fromParts = inferItemTypeFromParts(partNames);
  if (fromParts) return fromParts;
  if (!lower) return "";
  if (lower.includes("assault") || lower === "ar") return "Assault Rifle";
  if (lower.includes("shotgun") || lower === "sg") return "Shotgun";
  if (lower.includes("submachine") || lower === "smg" || lower === "sm") return "SMG";
  if (lower.includes("sniper") || lower === "sr") return "Sniper";
  if (lower.includes("pistol") || lower === "ps") return "Pistol";
  if (/heavy\s*gun\s*ordnance/.test(lower)) return "Heavy Gun Ordnance";
  if (lower.includes("heavy") || lower === "hw") return "Heavy Weapon";
  if (t === "Shield" || t === "Ordnance" || t === "Repkit" || t === "Enhancement") return t;
  return t;
}

function inferSet(manufacturer, itemType, partNames) {
  const classmodHint = /class\s*mod|classmod/i.test(String(itemType || ""));
  const classmodSet = inferClassmodSet(partNames);
  // Class Mod crafts must not adopt a gun set from a foreign pearl hook (e.g. ted_sg).
  if (classmodHint && classmodSet) return classmodSet;
  const fromParts = inferSetFromParts(partNames);
  if (fromParts && !(classmodHint && /_(?:ps|sg|sm|ar|sr|hw)$/i.test(fromParts))) return fromParts;
  if (classmodSet && classmodHint) return classmodSet;
  if (classmodSet && !String(itemType || "").trim()) return classmodSet;
  const mfrMap = {
    jakobs: "jak",
    daedalus: "dad",
    tediore: "ted",
    torgue: "tor",
    order: "ord",
    vladof: "vla",
    maliwan: "mal",
    ripper: "bor",
    borg: "bor",
    atlas: "atl",
    hyperion: "hyp",
    cov: "cov",
  };
  // Gun short codes + equipment set suffixes (jak_shield, mal_repair_kit, …).
  const typeMap = {
    pistol: "ps",
    shotgun: "sg",
    smg: "sm",
    "submachine gun": "sm",
    "assault rifle": "ar",
    sniper: "sr",
    "sniper rifle": "sr",
    "heavy weapon": "hw",
    "heavy gun ordnance": "hw",
    heavy: "hw",
    shield: "shield",
    shields: "shield",
    energy: "shield",
    armor: "shield",
    repkit: "repair_kit",
    "rep kit": "repair_kit",
    "repair kit": "repair_kit",
    grenade: "grenade_gadget",
    grenades: "grenade_gadget",
    ordnance: "grenade_gadget",
    gadget: "grenade_gadget",
    gadgets: "grenade_gadget",
  };
  let pref = "";
  const m = String(manufacturer || "").toLowerCase();
  for (const [name, code] of Object.entries(mfrMap)) {
    if (m.includes(name)) {
      pref = code;
      break;
    }
  }
  let suf = "";
  const t = String(itemType || "").toLowerCase();
  for (const [name, code] of Object.entries(typeMap)) {
    if (t.includes(name) || t === code) {
      suf = code;
      break;
    }
  }
  if (!pref || !suf) {
    const blob = (partNames || []).join(" ").toLowerCase();
    for (const [name, code] of Object.entries(mfrMap)) {
      if (!pref && blob.includes(name)) pref = code;
    }
    // Short manufacturer prefixes in part codes (jak_ps / mal_shield).
    if (!pref) {
      const short = blob.match(
        /\b(jak|mal|ted|tor|vla|ord|dad|bor|borg|cov|hyp|atl)_(?:ps|sg|sm|ar|sr|hw|shield|repair_kit|grenade_gadget)\b/
      );
      if (short) pref = short[1] === "borg" ? "bor" : short[1];
    }
    if (/(?:^|[._])sg(?:[._]|$)|shotgun/.test(blob)) suf = suf || "sg";
    else if (/(?:^|[._])sm(?:[._]|$)|smg/.test(blob)) suf = suf || "sm";
    else if (/(?:^|[._])ar(?:[._]|$)|assault/.test(blob)) suf = suf || "ar";
    else if (/(?:^|[._])ps(?:[._]|$)|pistol/.test(blob)) suf = suf || "ps";
    else if (/(?:^|[._])sr(?:[._]|$)|sniper/.test(blob)) suf = suf || "sr";
    else if (/(?:^|[._])hw(?:[._]|$)|heavy/.test(blob)) suf = suf || "hw";
    else if (/_shield|shield\./.test(blob)) suf = suf || "shield";
    else if (/repair_kit|repkit/.test(blob)) suf = suf || "repair_kit";
    else if (/grenade_gadget|ordnance|grenade/.test(blob)) suf = suf || "grenade_gadget";
  }
  return pref && suf ? `${pref}_${suf}` : "";
}

/**
 * @param {object} props
 * @returns {{ ok: boolean, stats: Array<{label:string,value:string}>, raw: object, source: string, error?: string }}
 */
function evaluateNexusCardStats(props) {
  const base = props && typeof props === "object" ? props : {};
  const data = ensureStatData();
  if (!data) {
    return { ok: false, stats: [], raw: {}, source: "none", error: _dataError || "no_data" };
  }
  const rawType = String(base.itemType || base.item_type || base.type_label || base.type || "").trim();
  const partNames = Array.isArray(base.part_names) ? base.part_names : [];
  // Editor/Serials/GZO often leave itemType blank or as Grenade/Gadget — canon + parts.
  const itemType = canonItemType(rawType, partNames);
  const isClassmod = itemType === "Classmod" || /class\s*mod/i.test(itemType);
  let set = String(base.set || "").trim().toLowerCase();
  // Ignore garbage catalog sets ("weapon", "jakobs") — re-infer from parts / mfr+type.
  if (!isUsableInvSet(set)) set = "";
  if (!set) set = inferSet(base.manufacturer, isClassmod ? "Class Mod" : itemType, partNames);
  if (!set && isClassmod) set = inferClassmodSet(partNames);
  if (!set) set = inferSetFromParts(partNames);
  if (!set || !partNames.length) {
    return { ok: false, stats: [], raw: {}, source: "none", error: "missing_set_or_parts" };
  }
  const part_keys = [];
  const part_roots = [];
  for (const raw of partNames) {
    const split = splitPartRef(raw, set);
    if (!split || !split.key) continue;
    part_keys.push(split.key);
    // Keep true inv roots from the part ref (Weapon.part_cryo, classmod_*, mal_sm.*, shields).
    const rawRoot = String(raw || "")
      .trim()
      .replace(/^"+|"+$/g, "");
    const explicitRoot = rawRoot.includes(".")
      ? rawRoot.slice(0, rawRoot.lastIndexOf(".")).toLowerCase()
      : "";
    const keepRoot =
      explicitRoot &&
      (explicitRoot === "weapon" ||
        explicitRoot.startsWith("classmod") ||
        /_(?:shield|repair_kit|grenade_gadget|hw|ps|sg|sm|ar|sr)$/.test(explicitRoot) ||
        /^(?:shield|energy_shield|armor_shield|repair_kit|grenade_gadget|gadget)$/.test(
          explicitRoot
        ));
    part_roots.push(keepRoot ? explicitRoot : split.root || set);
  }
  if (!part_keys.length) {
    return { ok: false, stats: [], raw: {}, source: "none", error: "no_part_keys" };
  }
  let level = Number(base.level);
  if (!Number.isFinite(level) || level <= 0) level = 70;
  const element = String(base.element || base.damage_type || "").trim();
  const card = {
    item_type: itemType,
    set,
    part_keys,
    part_roots,
    level,
    element,
    human: "",
  };
  try {
    const { attachStatsToCard, GUN_TYPES } = require("./nexus/serial_card_stats");
    if (!GUN_TYPES.has(itemType)) {
      card.item_type = itemType === "Class Mod" ? "Classmod" : itemType;
    }
    attachStatsToCard(card, data);
  } catch (error) {
    return {
      ok: false,
      stats: [],
      raw: {},
      source: "none",
      error: String(error && error.message ? error.message : error),
    };
  }
  const stats = [];
  const push = (label, value, fmt) => {
    if (value == null || !Number.isFinite(Number(value))) return;
    const n = Number(value);
    let text;
    if (fmt === "pct") text = `${Math.round(n * 10) / 10}%`;
    else if (fmt === "rate") text = String(Math.round(n * 100) / 100);
    else if (fmt === "reload") text = `${Math.round(n * 100) / 100}s`;
    else text = String(Math.round(n));
    stats.push({ label, value: text });
  };
  // Live / GZO cards: Damage headline first; DPS only when Damage is missing.
  push("Damage", card.damage);
  if (card.damage == null || !Number.isFinite(Number(card.damage))) {
    push("DPS", card.dps);
  }
  push("Crit", card.crit, "pct");
  push("Magazine", card.magazine);
  push("Fire Rate", card.fire_rate, "rate");
  push("Accuracy", card.accuracy, "pct");
  push("Reload", card.reload, "reload");
  const equipment = card.native_equipment || null;
  const hasEquip = Boolean(
    equipment &&
      ((equipment.groups?.primary || []).length ||
        (equipment.groups?.secondary || []).length ||
        (equipment.groups?.headline || []).length ||
        (equipment.groups?.text || []).length)
  );
  const ok = (Boolean(card.stats_ok) && stats.length > 0) || hasEquip;
  return {
    ok,
    stats,
    native_equipment: equipment,
    native_secondary: Array.isArray(card.native_secondary) ? card.native_secondary : [],
    red_text: Array.isArray(card.red_text) ? card.red_text : [],
    raw: {
      damage: card.damage,
      dps: card.dps,
      crit: card.crit,
      magazine: card.magazine,
      fire_rate: card.fire_rate,
      accuracy: card.accuracy,
      reload: card.reload,
      element_text: card.element_text || "",
      element_dps: card.element_dps,
      element_chance: card.element_chance,
      value: card.value,
      stats_blocked: card.stats_blocked || [],
      native_equipment: equipment,
      native_secondary: Array.isArray(card.native_secondary) ? card.native_secondary : [],
      red_text: Array.isArray(card.red_text) ? card.red_text : [],
      set,
      item_type: card.item_type || itemType,
      level,
    },
    source: card.stats_source || (ok ? "offline_nexus" : "none"),
    error: ok ? "" : (card.stats_blocked || []).slice(0, 4).join(",") || "stats_incomplete",
  };
}

function nexusStatus() {
  const data = ensureStatData();
  return {
    ok: Boolean(data),
    path: _legitItemsPath || "",
    error: _dataError || "",
  };
}

module.exports = {
  evaluateNexusCardStats,
  nexusStatus,
  resolveLegitItemsPath,
  ensureStatData,
  inferSetFromParts,
  inferSet,
  isUsableInvSet,
  canonItemType,
};
