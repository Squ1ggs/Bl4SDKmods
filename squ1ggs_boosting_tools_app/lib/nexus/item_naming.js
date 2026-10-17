"use strict";

/**
 * Full in-game item names (prefixes + title) from mined Nexus naming data.
 *
 * Mirrors the game's naming strategies:
 * - OakWeaponNamingStrategy: licensed mag/barrel prefix (or Tediore payload) +
 *   stat prefix from naming-attribute thresholds + barrel/unique title.
 * - OakHeavyWeaponNamingStrategy: body-mod prefix table + title.
 * - OakShieldNamingStrategy: ShieldNameTable primary / secondary / both.
 * - ClassModNamingStrategy: highest-points passive display name + body title.
 * - OakEnhancementNamingStrategy: stat combination + single stat + core title.
 * - No strategy (repkits, grenades, …): prefixpartlist names + title.
 */

const fs = require("fs");
const path = require("path");

const RARITY_ORDER = ["01_common", "02_uncommon", "03_rare", "04_epic", "05_legendary"];

function readJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

function nexusText(value) {
  const s = String(value || "");
  const parts = s.split(",");
  return parts.length >= 3 ? parts.slice(2).join(",").trim() : s.trim();
}

function refKey(ref, kind) {
  const s = String(ref || "");
  const m = s.match(new RegExp(`${kind}'([^']+)'`, "i"));
  return String(m ? m[1] : s).trim().toLowerCase();
}

function columnKey(name) {
  return String(name || "")
    .trim()
    .toLowerCase()
    .replace(/_\d+_[0-9a-f]{32}$/i, "");
}

function tagNames(list) {
  const out = [];
  for (const entry of list || []) {
    if (entry && typeof entry === "object") out.push(...Object.keys(entry).map((k) => k.toLowerCase()));
    else if (entry) out.push(String(entry).toLowerCase());
  }
  return out;
}

function eachRecordEntry(payload, rootKey, fn) {
  for (const rec of payload?.[rootKey]?.records || []) {
    for (const ent of rec.entries || []) {
      if (!ent || typeof ent !== "object") continue;
      for (const [k, v] of Object.entries(ent)) {
        if (!k.startsWith("__")) fn(k, v);
      }
    }
  }
}

function loadNamingData(legitItems) {
  const nameParts = new Map();
  const strategies = new Map();
  const tables = new Map();
  if (!legitItems || !fs.existsSync(legitItems)) return { nameParts, strategies, tables };
  const files = fs.readdirSync(legitItems);
  for (const name of files) {
    if (!/^Nexus-Data-inv_name_part\d*\.json$/.test(name)) continue;
    eachRecordEntry(readJson(path.join(legitItems, name)), "inv_name_part", (k, v) => {
      if (!v || typeof v !== "object") return;
      nameParts.set(k.toLowerCase(), {
        text: nexusText(v.partname),
        priority: Number(v.priority) || 0,
        minRarity: refKey(v.minrarity, "rarity"),
        maxRarity: refKey(v.maxrarity, "rarity"),
        manufacturer: refKey(v.requiredmanufacturer, "manufacturer"),
        requiredTags: tagNames(v.requiredbasetags),
        excludedTags: tagNames(v.excludedbasetags),
      });
    });
  }
  const refs = new Map();
  for (const name of files) {
    if (!/^Nexus-Data-inv_name_strategy\d*\.json$/.test(name)) continue;
    eachRecordEntry(readJson(path.join(legitItems, name)), "inv_name_strategy", (k, v) => {
      if (!v || typeof v !== "object") return;
      if (v.namingstrategy) strategies.set(k.toLowerCase(), v.namingstrategy);
      else if (v.ref) refs.set(k.toLowerCase(), String(v.ref).toLowerCase());
    });
  }
  for (const [k, target] of refs) {
    if (!strategies.has(k) && strategies.has(target)) strategies.set(k, strategies.get(target));
  }
  for (const name of files) {
    if (!/^Nexus-Data-gbx_ue_data_table\d*\.json$/.test(name)) continue;
    eachRecordEntry(readJson(path.join(legitItems, name)), "gbx_ue_data_table", (k, v) => {
      if (!v || typeof v !== "object" || !Array.isArray(v.data)) return;
      const rows = new Map();
      for (const row of v.data) {
        if (!row || !row.row_name || !row.row_value || typeof row.row_value !== "object") continue;
        const cells = {};
        for (const [ck, cv] of Object.entries(row.row_value)) cells[columnKey(ck)] = cv;
        rows.set(String(row.row_name).toLowerCase(), cells);
      }
      tables.set(String(v.gbx_ue_data_table || k).toLowerCase(), rows);
    });
  }
  return { nameParts, strategies, tables };
}

function tableFor(naming, ref) {
  return naming.tables.get(refKey(ref, "gbx_ue_data_table")) || null;
}

function rarityFromKeys(keys) {
  for (const key of keys) {
    const m = String(key).match(/comp_0([1-5])_/);
    if (m) return RARITY_ORDER[Number(m[1]) - 1];
  }
  return "";
}

/** Assemble part defs, tags and naming aspects for one item. */
function assembleParts(statData, set, partRefs) {
  const roots = statData.invRoots;
  const host = roots.get(set) || null;
  const parts = [];
  const tags = new Set();
  for (const ref of partRefs) {
    const root = String(ref.root || set).toLowerCase();
    const key = String(ref.key || "").toLowerCase();
    if (!key) continue;
    const def = roots.get(root)?.parts.get(key) || host?.parts.get(key) || null;
    if (!def) continue;
    parts.push({ root, key, def });
    for (const t of tagNames(def.addtags)) tags.add(t);
    for (const t of tagNames(def.basetags)) tags.add(t);
  }
  const manufacturer = refKey(host?.root?.manufacturer, "manufacturer");
  const rarity = rarityFromKeys(parts.map((p) => p.key));
  return { set, host, parts, tags, manufacturer, rarity };
}

function namePartAllowed(np, ctx) {
  if (!np || !np.text) return false;
  if (np.manufacturer && ctx.manufacturer && np.manufacturer !== ctx.manufacturer) return false;
  if ((np.minRarity || np.maxRarity) && ctx.rarity) {
    const r = RARITY_ORDER.indexOf(ctx.rarity);
    if (np.minRarity && r < RARITY_ORDER.indexOf(np.minRarity)) return false;
    if (np.maxRarity && RARITY_ORDER.indexOf(np.maxRarity) >= 0 && r > RARITY_ORDER.indexOf(np.maxRarity)) return false;
  }
  if (np.requiredTags.length && !np.requiredTags.every((t) => ctx.tags.has(t))) return false;
  if (np.excludedTags.some((t) => ctx.tags.has(t))) return false;
  return true;
}

function collectNameParts(naming, ctx) {
  const titles = [];
  const prefixes = [];
  const rows = [];
  for (const part of ctx.parts) {
    for (const aspect of part.def.aspects || []) {
      if (!/InventoryNamingAspect/i.test(String(aspect?.structtype || ""))) continue;
      if (aspect.datatablerowname) rows.push({ row: String(aspect.datatablerowname).toLowerCase(), part });
      for (const [list, sink] of [
        [aspect.titlepartlist, titles],
        [aspect.prefixpartlist, prefixes],
      ]) {
        for (const ref of list || []) {
          const np = naming.nameParts.get(refKey(ref, "inv_name_part"));
          if (namePartAllowed(np, ctx)) sink.push({ ...np, part });
        }
      }
    }
  }
  return { titles, prefixes, rows };
}

function bestTitle(titles) {
  let best = null;
  for (const t of titles) if (!best || t.priority > best.priority) best = t;
  return best ? best.text : "";
}

function joinName(words) {
  let out = "";
  for (const raw of words) {
    const w = String(raw || "").trim();
    if (!w) continue;
    out = w.startsWith("-") && out ? `${out}${w}` : out ? `${out} ${w.replace(/^-/, "")}` : w.replace(/^-/, "");
  }
  return out.replace(/\s+/g, " ").trim();
}

// --- Weapons ---------------------------------------------------------------

function attributeLevel(factor, threshold) {
  const first = Math.fround(Number(threshold.firstthreshold));
  const second = Math.fround(Number(threshold.secondthreshold));
  if (!Number.isFinite(factor) || !Number.isFinite(first)) return 0;
  const value = Math.fround(factor);
  // Spread / reload / zoom time: lower is better (thresholds below 1).
  // Strict compare: 1.5 × 0.8 elemental = exactly 1.2 does not earn Damage.
  const lowerBetter = first < 1;
  const passes = (limit) => (lowerBetter ? value < limit : value > limit);
  if (Number.isFinite(second) && passes(second)) return 2;
  return passes(first) ? 1 : 0;
}

function weaponStatPrefix(strategy, factors) {
  if (!factors) return "";
  const levels = new Map();
  for (const t of strategy.namingattributethresholds || []) {
    const name = String(t.attributename || "");
    levels.set(name, attributeLevel(Number(factors[name]), t));
  }
  let best = null;
  const offer = (entry) => {
    const np = entry?.namepart;
    if (!np) return;
    const priority = Number(np.priority) || 0;
    if (!best || priority > best.priority) best = { priority, text: nexusText(np.partname) };
  };
  for (const e of strategy.combinationnames || []) {
    if ((levels.get(e.firstattributename) || 0) >= 1 && (levels.get(e.secondattributename) || 0) >= 1) offer(e);
  }
  for (const e of strategy.doublenames || []) {
    if ((levels.get(e.firstattributename) || 0) >= 2) offer(e);
  }
  for (const e of strategy.singlenames || []) {
    if ((levels.get(e.firstattributename) || 0) >= 1) offer(e);
  }
  return best ? best.text : "";
}

function pickRow(table, tags, fallback = "default") {
  if (!table) return null;
  for (const [row, cells] of table) {
    if (row !== fallback && tags.has(row)) return cells;
  }
  return table.get(fallback) || null;
}

function pickCell(cells, tags, columns) {
  if (!cells) return "";
  for (const col of columns) {
    if (tags.has(col) && cells[col]) return nexusText(cells[col]);
  }
  return cells.default ? nexusText(cells.default) : "";
}

function payloadPrefix(naming, strategy, tags) {
  const table = tableFor(naming, strategy.payloaddeliverydatatable);
  if (!table) return "";
  const kinds = ["ted_shooting", "ted_mirv", "ted_combo", "ted_replicator"].filter((t) => tags.has(t));
  let cells = null;
  if (kinds.length >= 2) cells = table.get(`${kinds[0]}+${kinds[1]}`) || table.get(`${kinds[1]}+${kinds[0]}`);
  if (!cells && kinds.length) cells = table.get(kinds[0]);
  if (!cells) cells = table.get("default");
  return pickCell(cells, tags, ["ted_javelin", "ted_homing", "ted_legs"]);
}

function weaponLicensedPrefix(naming, strategy, tags) {
  const table = tableFor(naming, strategy.magbarreldatatable);
  const cells = pickRow(table, tags);
  if (!cells) return "";
  const mag = pickCell(cells, tags, ["borg_mag", "cov_mag", "tor_mag"]);
  if (String(cells.use_payload_prefix || "").toLowerCase() === "true") {
    const payload = payloadPrefix(naming, strategy, tags);
    return payload ? joinName([payload, mag]) : mag;
  }
  return mag;
}

function nameWeapon(naming, strategy, ctx, collected, factors) {
  return joinName([
    weaponLicensedPrefix(naming, strategy, ctx.tags),
    weaponStatPrefix(strategy, factors),
    bestTitle(collected.titles),
  ]);
}

function nameHeavyWeapon(naming, strategy, ctx, collected) {
  const mods = [...ctx.tags].filter((t) => /^body_mod_[a-z]$/.test(t)).sort();
  let prefix = "";
  const table = tableFor(naming, strategy.bodyprefixmodnamedatatable);
  if (table && mods.length) {
    const rowKey = mods.length >= 3 ? `${mods[0]}.${mods[1]}` : mods[0];
    const extra = mods.length >= 2 ? mods[mods.length - 1].slice(-1) : "";
    const cells = table.get(rowKey);
    if (cells) prefix = nexusText(extra ? cells[`mod${extra}`] : cells.singleornomod);
  }
  ctx.resolvedTitle = heavyBarrelTitle(naming, strategy, ctx, collected);
  return joinName([prefix, ctx.resolvedTitle]);
}

function heavyBarrelTitle(naming, strategy, ctx, collected) {
  const unique = collected.titles.filter((t) => t.priority > 0);
  if (unique.length) return bestTitle(unique);
  const barrel = ctx.tags.has("barrel_02") ? 2 : ctx.tags.has("barrel_01") ? 1 : 0;
  const table = tableFor(naming, barrel === 2 ? strategy.barreltwomodnamedatatable : strategy.barrelonemodnamedatatable);
  if (!barrel || !table) return bestTitle(collected.titles);
  const mods = new Set();
  for (const t of ctx.tags) {
    const m = t.match(/^barrel_mod_([a-d])$/);
    if (m) mods.add(m[1]);
  }
  for (const part of ctx.parts) {
    const m = part.key.match(/^part_barrel_0\d_([a-d])x?([a-d])$/);
    if (m) mods.add(m[1]).add(m[2]);
  }
  const sorted = [...mods].sort();
  let text = "";
  if (!sorted.length) text = nexusText(table.get("no_mod")?.singleornomod);
  else {
    const cells = table.get(`barrel_mod_${sorted[0]}`);
    text = nexusText(sorted.length >= 2 ? cells?.[`mod${sorted[sorted.length - 1]}`] : cells?.singleornomod);
  }
  return text || bestTitle(collected.titles);
}

// --- Shields / class mods / enhancements -----------------------------------

function nameShield(naming, strategy, ctx, collected) {
  const table = tableFor(naming, strategy.namingcombinationdatatable);
  let primary = "";
  let secondary = "";
  for (const { row, part } of collected.rows) {
    const side = /_secondary$/.test(part.key) || part.def.secondary_augment ? "secondary" : "primary";
    if (side === "primary" && !primary) primary = row;
    if (side === "secondary" && !secondary) secondary = row;
  }
  const words = [];
  if (table && primary && primary === secondary) {
    words.push(nexusText(table.get(primary)?.both));
  } else if (table) {
    if (primary) words.push(nexusText(table.get(primary)?.primary));
    if (secondary) words.push(nexusText(table.get(secondary)?.secondary));
  }
  return joinName([...words, bestTitle(collected.titles)]);
}

function passiveKey(p) {
  return `${refKey(p?.progressgraph, "progress_graph")}|${String(p?.nodename || "").toLowerCase()}`;
}

/** Body title np for a ClassModPassiveAndDisplayName row (leg_body_06 -> Teen Witch). */
function classmodBodyTitle(naming, ctx, row) {
  const host = ctx.host;
  if (!host) return "";
  const titles = [];
  for (const def of host.parts.values()) {
    for (const aspect of def.aspects || []) {
      if (!/InventoryNamingAspect/i.test(String(aspect?.structtype || ""))) continue;
      if (String(aspect.datatablerowname || "").toLowerCase() !== row) continue;
      for (const ref of aspect.titlepartlist || []) {
        const np = naming.nameParts.get(refKey(ref, "inv_name_part"));
        if (np?.text) titles.push(np);
      }
    }
  }
  return bestTitle(titles);
}

function nameClassmod(naming, strategy, ctx, collected) {
  const table = tableFor(naming, strategy.passiveanddisplaynamedatatable);
  const points = new Map();
  const firstIndex = new Map();
  for (const part of ctx.parts) {
    const serialIndex = Number(part.def.serialindex?.index ?? 99999);
    for (const aspect of part.def.aspects || []) {
      if (!/ClassModPassivesAspect/i.test(String(aspect?.structtype || ""))) continue;
      const pts = Number(aspect.points) || 1;
      for (const p of aspect.passives || []) {
        const key = passiveKey(p);
        points.set(key, (points.get(key) || 0) + pts);
        firstIndex.set(key, Math.min(firstIndex.get(key) ?? 99999, serialIndex));
      }
    }
  }
  const hostSet = ctx.host ? ctx.set : "";
  const ownRows = collected.rows.filter((r) => !hostSet || r.part.root === hostSet);
  let bodyRow = ownRows[0]?.row || "";
  const ownTitles = collected.titles.filter((t) => !t.part || !hostSet || t.part.root === hostSet);
  let title = bestTitle(ownTitles.length ? ownTitles : collected.titles);
  if (table && (!bodyRow || !table.has(bodyRow))) {
    // Body-less legendary codes: the game names them from the body whose passives they carry.
    let bestScore = 0;
    for (const [row, rowCells] of table) {
      let score = 0;
      for (const slot of ["passive1", "passive2", "passive3", "passive4"]) {
        if (rowCells[slot]?.passive) score += points.get(passiveKey(rowCells[slot].passive)) || 0;
      }
      if (score > bestScore || (score && score === bestScore && /^leg_/.test(row) && !/^leg_/.test(bodyRow))) {
        bestScore = score;
        bodyRow = row;
      }
    }
    if (bestScore) title = classmodBodyTitle(naming, ctx, bodyRow) || title;
  }
  ctx.resolvedTitle = title;
  const cells = table?.get(bodyRow) || null;
  let prefix = "";
  if (cells) {
    let best = 0;
    let bestIndex = 99999;
    for (const slot of ["passive1", "passive2", "passive3", "passive4"]) {
      const entry = cells[slot];
      if (!entry?.passive) continue;
      const key = passiveKey(entry.passive);
      const pts = points.get(key) || 0;
      const idx = firstIndex.get(key) ?? 99999;
      if (pts > best || (pts && pts === best && idx < bestIndex)) {
        best = pts;
        bestIndex = idx;
        prefix = nexusText(entry.displayname);
      }
    }
  }
  return title ? joinName([prefix, title]) : "";
}

function nameEnhancement(naming, strategy, ctx, collected) {
  const stats = [];
  let core = "";
  const cores = [];
  for (const { row, part } of collected.rows) {
    if (/^part_core_/.test(row)) cores.push(row);
    else if (/^part_stat/.test(row)) stats.push({ row, slot: Number((part.key.match(/^part_stat(\d)?_/) || [])[1] || 1) });
  }
  stats.sort((a, b) => a.slot - b.slot);
  const combo = naming.tables.get("enhancementnamingstatcombinationstable");
  const words = [];
  if (stats.length >= 2 && combo) {
    const [a, b] = stats;
    words.push(nexusText(combo.get(a.row)?.[b.row] || combo.get(b.row)?.[a.row]));
  }
  const single = stats.length >= 3 ? stats[2] : stats.length === 1 ? stats[0] : null;
  if (single) {
    const hit = (strategy.singlestatnames || []).find((e) => String(e.firstattributename || "").toLowerCase() === single.row);
    words.push(hit ? nexusText(hit.namepart?.partname) : nexusText(combo?.get(single.row)?.single));
  }
  const coreTable = naming.tables.get("enhancementnamingcorecombinationstable");
  if (cores.length && coreTable) {
    core = nexusText(
      cores.length >= 2
        ? coreTable.get(cores[0])?.[cores[1]] || coreTable.get(cores[1])?.[cores[0]]
        : coreTable.get(cores[0])?.single
    );
  }
  // Core table names the item (headringer = Pounder; bouncepass + sequencer = Hat Trick).
  const title = core || bestTitle(collected.titles);
  ctx.resolvedTitle = title;
  return joinName([...words, title]);
}

function nameGeneric(ctx, collected) {
  const prefixes = [...collected.prefixes].sort((a, b) => b.priority - a.priority);
  const seen = new Set();
  const words = [];
  for (const p of prefixes) {
    const k = p.text.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    words.push(p.text);
  }
  return joinName([...words, bestTitle(collected.titles)]);
}

/**
 * @param {object} statData   loadStatData() output (needs invRoots)
 * @param {object} naming     loadNamingData() output
 * @param {{set:string, partRefs:Array<{root:string,key:string}>, namingFactors?:object}} item
 * @returns {{ name: string, title: string, strategy: string }}
 */
function buildItemName(statData, naming, item) {
  const set = String(item?.set || "").toLowerCase();
  if (!statData?.invRoots || !naming || !set) return { name: "", title: "", strategy: "" };
  const ctx = assembleParts(statData, set, item.partRefs || []);
  const collected = collectNameParts(naming, ctx);
  const fallbackTitle = String(item.fallbackTitle || "").trim();
  if (!collected.titles.length && fallbackTitle) {
    collected.titles.push({ text: fallbackTitle, priority: 0 });
  }
  const title = bestTitle(collected.titles);
  // Manufacturer roots (ord_shield, tor_enhancement) inherit the shared root's strategy.
  let strategyRef = ctx.host?.root?.namingstrategydef;
  if (!strategyRef) {
    for (const part of ctx.parts) {
      strategyRef = statData.invRoots.get(part.root)?.root?.namingstrategydef;
      if (strategyRef) break;
    }
  }
  const strategyKey = refKey(strategyRef, "inv_name_strategy");
  const strategy = strategyKey ? naming.strategies.get(strategyKey) : null;
  const kind = String(strategy?.structtype || "");
  let name = "";
  if (/OakWeaponNamingStrategy/i.test(kind)) name = nameWeapon(naming, strategy, ctx, collected, item.namingFactors);
  else if (/HeavyWeaponNamingStrategy/i.test(kind)) name = nameHeavyWeapon(naming, strategy, ctx, collected);
  else if (/ShieldNamingStrategy/i.test(kind)) name = nameShield(naming, strategy, ctx, collected);
  else if (/ClassModNamingStrategy/i.test(kind)) name = nameClassmod(naming, strategy, ctx, collected);
  else if (/EnhancementNamingStrategy/i.test(kind)) name = nameEnhancement(naming, strategy, ctx, collected);
  else name = nameGeneric(ctx, collected);
  return { name, title: ctx.resolvedTitle ?? title, strategy: strategyKey };
}

module.exports = { loadNamingData, buildItemName };
