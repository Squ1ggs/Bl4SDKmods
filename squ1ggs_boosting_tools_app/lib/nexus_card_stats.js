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

let _namingData;

function ensureNamingData() {
  if (_namingData !== undefined) return _namingData;
  try {
    const { loadNamingData } = require("./nexus/item_naming");
    _namingData = loadNamingData(_legitItemsPath || resolveLegitItemsPath());
  } catch {
    _namingData = null;
  }
  return _namingData;
}

function sharedNamingRootsForSet(set) {
  const s = String(set || "").toLowerCase();
  if (/_shield$/.test(s)) return ["energy_shield", "armor_shield", "shield"];
  if (/_grenade_gadget$/.test(s)) return ["grenade_gadget"];
  if (/_repair_kit$/.test(s)) return ["repair_kit"];
  if (/_enhancement$/.test(s)) return ["enhancement"];
  if (/^classmod/.test(s)) return ["classmod"];
  if (/_hw$/.test(s)) return ["heavy_weapon_gadget", "weapon"];
  return ["weapon"];
}

const GENERIC_ITEM_NAME_RE =
  /^(?:@U|#|★)|^(?:[\w'-]+\s+)?(?:pistol|shotgun|assault\s*rifle|smg|submachine\s*gun|sniper(?:\s*rifle)?|heavy\s*weapon|shield|repkit|repair\s*kit|enhancement|class\s*mod|grenade|ordnance|gadget)$/i;

/** Full in-game name (licensed / stat / passive prefixes + title) from the complete part list. */
function computeFullItemName(data, set, partNames, namingFactors, decodedName) {
  const naming = ensureNamingData();
  if (!naming || !data?.invRoots || !set) return "";
  const partRefs = [];
  const hasPart = (root, key) => Boolean(data.invRoots.get(root)?.parts?.has(key));
  const kindRoots = sharedNamingRootsForSet(set);
  for (const raw of partNames || []) {
    const s = String(raw || "").trim().toLowerCase().replace(/^"+|"+$/g, "");
    if (!s) continue;
    const dot = s.lastIndexOf(".");
    const key = dot > 0 ? s.slice(dot + 1) : s;
    let root = dot > 0 ? s.slice(0, dot) : set;
    if (!hasPart(root, key)) root = hasPart(set, key) ? set : kindRoots.find((r) => hasPart(r, key)) || set;
    partRefs.push({ root, key });
  }
  const decoded = String(decodedName || "").replace(/^\[(?:legit|modded)\]\s*/i, "").trim();
  const fallbackTitle = decoded && !GENERIC_ITEM_NAME_RE.test(decoded) ? decoded : "";
  try {
    const { buildItemName } = require("./nexus/item_naming");
    const out = buildItemName(data, naming, { set, partRefs, namingFactors, fallbackTitle });
    return out.title && !GENERIC_ITEM_NAME_RE.test(out.title) ? out.name : "";
  } catch {
    return "";
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
    /^(shield|energy_shield|armor_shield|repair_kit|grenade_gadget|gadget|heavy_weapon_gadget|turret_gadget|terminal_gadget|enhancement|classmod)$/.test(
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
  // Classmod + foreign pearl hook ({7:54} → TED_SG.comp_06_pearl_*) must keep
  // the classmod root — manufacturer gun sets used to rank higher and paint a shotgun card.
  const hasClassmod = roots.some((r) => /^classmod_/.test(r));
  const ranked = [...roots].sort((a, b) => {
    const score = (r) => {
      if (/^classmod_/.test(r)) return 0;
      // Pearl-only gun family hooks are decoys when a classmod root is present.
      if (hasClassmod && /_(?:ps|sg|sm|ar|sr|hw)$/.test(r)) return 3;
      if (/^(jak|mal|ted|tor|vla|ord|dad|bor|borg|cov|hyp|atl)_/.test(r)) return 1;
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
  // Pearl rarity id after || often resolves as TED_SG / DAD_SG comps. If the
  // rest of the serial is classmod body / passives, keep Classmod — not Shotgun.
  if (
    /(?:leg_body_|passive_(?:blue|green|red)|part_unv_|part_sec_|skilltree|progressgraph)/.test(
      blob
    ) &&
    /comp_06_pearl|(?:^|[._])(?:ps|sg|sm|ar|sr|hw)(?:[._]|$)/.test(blob) &&
    !/\.(?:part_barrel|part_body|part_grip|part_mag|part_stock|part_sight)_/.test(blob)
  ) {
    return "Classmod";
  }
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
  const fromParts = inferItemTypeFromParts(partNames);
  const hasClassmodRoot = (partNames || []).some((part) =>
    /(?:^|["'])classmod_[a-z0-9_]+\./i.test(String(part || "").trim())
  );
  // Explicit Class Mod / equipment from the Editor UI must win — pearl rarity hooks
  // can inject foreign gun-family tokens ({7:54} TED_SG) that would otherwise
  // make inferItemTypeFromParts report Shotgun.
  if (/class\s*mod|classmod/.test(lower) || hasClassmodRoot) return "Classmod";
  // A decoded serial-header weapon type is authoritative for modded guns. Their
  // part lists can intentionally contain shield/gadget/classmod parts.
  if (lower.includes("assault") || lower === "ar") return "Assault Rifle";
  if (lower.includes("shotgun") || lower === "sg") return "Shotgun";
  if (lower.includes("submachine") || lower === "smg" || lower === "sm") return "SMG";
  if (lower.includes("sniper") || lower === "sr") return "Sniper";
  if (lower.includes("pistol") || lower === "ps") return "Pistol";
  if (/heavy\s*gun\s*ordnance/.test(lower)) return "Heavy Gun Ordnance";
  if (lower.includes("heavy") || lower === "hw") return "Heavy Weapon";
  // Part-rooted pearl classmod is only a fallback when no explicit type exists.
  if (fromParts === "Classmod") return "Classmod";
  if (/repair\s*kit|rep\s*kit|repkit/.test(lower)) return "Repkit";
  if (/enhancement/.test(lower)) return "Enhancement";
  if (/grenade|ordnance|gadget/.test(lower) && !/heavy/.test(lower)) return "Ordnance";
  if (/shield|energy|armor/.test(lower) && !/class/.test(lower)) return "Shield";
  // Part roots are the source of truth for GZO/Serials thin labels (Grenade vs Shield).
  if (fromParts) return fromParts;
  if (!lower) return "";
  if (t === "Shield" || t === "Ordnance" || t === "Repkit" || t === "Enhancement") return t;
  return t;
}

function inferSet(manufacturer, itemType, partNames) {
  const classmodHint = /class\s*mod|classmod/i.test(String(itemType || ""));
  const classmodSet = inferClassmodSet(partNames);
  // Class Mod crafts must not adopt a gun set from a foreign pearl hook (e.g. ted_sg).
  if (classmodHint && classmodSet) return classmodSet;
  if (classmodSet && (classmodHint || inferItemTypeFromParts(partNames) === "Classmod")) {
    return classmodSet;
  }
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
 * Manufacturer grenade sets keep Cooldown/Radius/Charges on part_<mfr>
 * (inherits grenade_attr_base_values + GrenadeMod_Manufacturer_Init row).
 */
function ensureGrenadeManufacturerPart(data, set, partNames) {
  const host = String(set || "").toLowerCase();
  const m = host.match(/^([a-z]+)_grenade_gadget$/i);
  if (!m) return partNames;
  const manu = m[1].toLowerCase();
  const key = `part_${manu}`;
  const bag = data?.invRoots?.get?.(host);
  if (!bag?.parts?.has?.(key)) return partNames;
  const already = (partNames || []).some((raw) => {
    const s = String(raw || "").toLowerCase();
    return s === key || s.endsWith(`.${key}`) || new RegExp(`(?:^|\\.)${key}$`, "i").test(s);
  });
  if (already) return partNames;
  return [...partNames, `${host}.${key}`];
}

function rarityCompForSet(data, set, rarityHint) {
  const hint = String(rarityHint || "")
    .trim()
    .toLowerCase();
  if (!hint || !set || !data?.invRoots?.get(set)) return "";
  const parts = data.invRoots.get(set).parts;
  const named = {
    common: "comp_01_common",
    white: "comp_01_common",
    uncommon: "comp_02_uncommon",
    green: "comp_02_uncommon",
    rare: "comp_03_rare",
    blue: "comp_03_rare",
    epic: "comp_04_epic",
    purple: "comp_04_epic",
    legendary: "comp_05_legendary",
    orange: "comp_05_legendary",
    pearlescent: "comp_06_pearl",
    pearl: "comp_06_pearl",
  };
  const preferred = named[hint];
  if (preferred && parts.has(preferred)) return preferred;
  // Pearl comps are often named comp_06_pearl_<gun>.
  if (/pearl/.test(hint)) {
    const pearl = [...parts.keys()].find((k) => /^comp_06_pearl/i.test(k));
    if (pearl) return pearl;
  }
  if (/legend/.test(hint) && parts.has("comp_05_legendary")) return "comp_05_legendary";
  if (/epic|purple/.test(hint) && parts.has("comp_04_epic")) return "comp_04_epic";
  if (/rare|blue/.test(hint) && parts.has("comp_03_rare")) return "comp_03_rare";
  if (/uncommon|green/.test(hint) && parts.has("comp_02_uncommon")) return "comp_02_uncommon";
  if (parts.has("comp_01_common")) return "comp_01_common";
  return "";
}

/** Prefer skill/passive parts so heavy classmods still paint glyphs when lists truncate. */
function prioritizeClassmodPartNames(partNames, hostSet) {
  const host = String(hostSet || "").toLowerCase();
  const scored = [];
  for (const raw of partNames || []) {
    const s = String(raw || "").trim();
    if (!s) continue;
    const low = s.toLowerCase();
    const root = low.includes(".") ? low.slice(0, low.lastIndexOf(".")) : "";
    const leaf = low.includes(".") ? low.slice(low.lastIndexOf(".") + 1) : low;
    let score = 5;
    if (/passive_|skilltree|progressgraph|skill/.test(leaf)) score = 1;
    else if (/^body_|^leg_body_/.test(leaf)) score = 0;
    else if (/part_unv_|part_sec_|part_stat_|firmware/.test(leaf)) score = 2;
    else if (/comp_05_|comp_06_pearl|pearl_/.test(leaf)) score = 0;
    // Foreign gun-family pearl hooks are decoys — keep last (or remap below).
    else if (root && /_(?:ps|sg|sm|ar|sr|hw)$/.test(root) && root !== host) score = 9;
    scored.push({ raw: s, score, root, leaf });
  }
  scored.sort((a, b) => a.score - b.score);
  // Cap assembly size; skill-first order keeps ClassModPassivesAspect fed.
  const out = [];
  const seen = new Set();
  for (const row of scored) {
    let ref = row.raw;
    // Remap foreign gun pearl leaves onto the classmod host set.
    if (
      host &&
      row.score >= 9 &&
      /comp_06_pearl|pearl_/.test(row.leaf)
    ) {
      ref = `${host}.${row.leaf}`;
    } else if (row.score >= 9) {
      // Drop non-pearl foreign gun parts entirely for classmod cards.
      continue;
    }
    const key = ref.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(ref);
    if (out.length >= 96) break;
  }
  return out;
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
  let partNames = Array.isArray(base.part_names) ? [...base.part_names] : [];
  // Editor/Serials/GZO often leave itemType blank or as Grenade/Gadget — canon + parts.
  const itemType = canonItemType(rawType, partNames);
  const isClassmod = itemType === "Classmod" || /class\s*mod/i.test(itemType);
  let set = String(base.set || "").trim().toLowerCase();
  // Ignore garbage catalog sets ("weapon", "jakobs") — re-infer from parts / mfr+type.
  if (!isUsableInvSet(set)) set = "";
  if (!set) set = inferSet(base.manufacturer, isClassmod ? "Class Mod" : itemType, partNames);
  if (!set && isClassmod) set = inferClassmodSet(partNames);
  // Never let a pearl rarity gun-family root (ted_sg / dad_sg) own a classmod card.
  if (isClassmod && set && /_(?:ps|sg|sm|ar|sr|hw)$/i.test(set)) {
    set = inferClassmodSet(partNames) || "";
  }
  if (!set && !isClassmod) set = inferSetFromParts(partNames);
  if (!set || !partNames.length) {
    return { ok: false, stats: [], raw: {}, source: "none", error: "missing_set_or_parts" };
  }
  // Guns need a rarity composition for inv_stat damage scales. Thin serials /
  // catalog rows often omit comp_0N — inject from the card rarity label.
  if (!isClassmod && !partNames.some((p) => /\.comp_0[1-6]_/i.test(String(p || "")))) {
    const comp = rarityCompForSet(data, set, base.rarity || base.raw?.rarity || "");
    if (comp) partNames = [...partNames, `${set}.${comp}`];
  }
  // Grenade manufacturer body (part_ord / part_dad / …) carries
  // GrenadeMod_Manufacturer_Init → Cooldown / Radius / Charges. Thin catalogs
  // and dump-only part lists often omit it and paint 0s / 0cm.
  if (!isClassmod) {
    partNames = ensureGrenadeManufacturerPart(data, set, partNames);
  }
  // Naming needs every part (classmod body + all passives), not the capped card list.
  const namingPartNames = [...partNames];
  if (isClassmod) {
    partNames = prioritizeClassmodPartNames(partNames, set);
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
    // Classmod cards must not assemble TED_SG / DAD_SG etc. as part roots.
    if (
      isClassmod &&
      explicitRoot &&
      /_(?:ps|sg|sm|ar|sr|hw)$/.test(explicitRoot) &&
      !explicitRoot.startsWith("classmod")
    ) {
      part_roots.push(set);
      continue;
    }
    const keepRoot =
      explicitRoot &&
      (explicitRoot === "weapon" ||
        explicitRoot === "enhancement" ||
        explicitRoot === "classmod" ||
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
    // Never publish Damage/DPS 0 — that paints "0" and blocks the estimate fallback.
    if ((label === "Damage" || label === "DPS") && n <= 0) return;
    let text;
    if (fmt === "pct") text = `${Math.round(n * 10) / 10}%`;
    else if (fmt === "rate") text = String(Math.round(n * 100) / 100);
    else if (fmt === "reload") text = `${Math.round(n * 100) / 100}s`;
    else text = String(Math.round(n));
    stats.push({ label, value: text });
  };
  // Match the live card's visible weapon rows. DPS remains available in raw for
  // comparisons but is not painted as a synthetic headline.
  push("Damage", card.damage);
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
  const fullName = computeFullItemName(
    data,
    set,
    namingPartNames,
    card.naming_factors || null,
    base.display_name || base.title || ""
  );
  return {
    ok,
    stats,
    full_name: fullName,
    native_equipment: equipment,
    native_secondary: Array.isArray(card.native_secondary) ? card.native_secondary : [],
    native_firmware: Array.isArray(card.native_firmware) ? card.native_firmware : [],
    native_text: Array.isArray(card.native_text) ? card.native_text : [],
    native_groups: card.native_groups && typeof card.native_groups === "object" ? card.native_groups : {},
    firmware_block: card.firmware_block || null,
    red_text: Array.isArray(card.red_text) ? card.red_text : [],
    raw: {
      damage: Number.isFinite(card.damage) && card.damage > 0 ? card.damage : null,
      damage_per_projectile:
        Number.isFinite(card.damage_per_projectile) && card.damage_per_projectile > 0
          ? card.damage_per_projectile
          : null,
      dps: Number.isFinite(card.dps) && card.dps > 0 ? card.dps : null,
      crit: card.crit,
      magazine: card.magazine,
      fire_rate: card.fire_rate,
      accuracy: card.accuracy,
      reload: card.reload,
      element_text: card.element_text || "",
      element_text2: card.element_text2 || "",
      element_dps: card.element_dps,
      element_dps2: card.element_dps2,
      element_chance: card.element_chance,
      value: card.value,
      damage_radius: card.damage_radius,
      projectile_count: card.projectile_count,
      shot_cost: card.shot_cost,
      stats_blocked: card.stats_blocked || [],
      naming_factors: card.naming_factors || null,
      full_name: fullName,
      native_equipment: equipment,
      native_secondary: Array.isArray(card.native_secondary) ? card.native_secondary : [],
      native_firmware: Array.isArray(card.native_firmware) ? card.native_firmware : [],
      native_text: Array.isArray(card.native_text) ? card.native_text : [],
      native_groups: card.native_groups && typeof card.native_groups === "object" ? card.native_groups : {},
      firmware_block: card.firmware_block || null,
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
