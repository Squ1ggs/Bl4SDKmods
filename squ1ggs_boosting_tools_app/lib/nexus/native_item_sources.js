"use strict";

// Native definition traversal shared by the offline calculator and diagnostics.
// This collects source data; it does not infer native selection/stacking rules.
function reference(value, table) {
  const match = String(value || "").match(new RegExp(`^${table}'([^']+)'$`, "i"));
  return match ? match[1].toLowerCase() : "";
}

function mergeDefinition(parent, child) {
  if (!parent || typeof parent !== "object" || Array.isArray(parent)) return structuredClone(child);
  const result = structuredClone(parent);
  for (const [key, value] of Object.entries(child || {})) {
    if (value && typeof value === "object" && !Array.isArray(value) && result[key] && typeof result[key] === "object" && !Array.isArray(result[key]))
      result[key] = mergeDefinition(result[key], value);
    else result[key] = structuredClone(value);
  }
  return result;
}

function resolveAspect(aspect, definitions, trail = []) {
  if (!aspect || typeof aspect !== "object") throw new Error("Missing aspect definition");
  const parent = reference(aspect.parent, "inv_aspect");
  if (!parent) return structuredClone(aspect);
  if (trail.includes(parent)) throw new Error(`Aspect inheritance cycle: ${[...trail, parent].join(" -> ")}`);
  if (!definitions.has(parent)) throw new Error(`Missing inherited aspect: ${parent}`);
  return mergeDefinition(resolveAspect(definitions.get(parent), definitions, [...trail, parent]), aspect);
}

function collectItemSources(data, {set, partKeys, partRoots}) {
  const sources = [], errors = [];
  const host = String(set || "").toLowerCase();
  function inheritedPart(definition, trail = []) {
    const base = reference(definition.basecomposition, "inv");
    if (!base) return definition;
    if (trail.includes(base)) throw new Error(`Composition inheritance cycle: ${[...trail, base].join(" -> ")}`);
    const split = base.indexOf(".");
    const parent = data.invRoots.get(base.slice(0, split))?.parts.get(base.slice(split + 1));
    if (!parent) throw new Error(`Missing base composition: ${base}`);
    const parentMerged = inheritedPart(parent, [...trail, base]);
    const merged = mergeDefinition(parentMerged, definition);
    // Composition stacks aspects. mergeDefinition replaces arrays, which drops
    // legendary Shield_Rarity_Init (and similar) when a unique comp only adds
    // Material/wear aspects on top of energy_shield.comp_05_legendary.
    const parentAspects = Array.isArray(parentMerged.aspects) ? parentMerged.aspects : [];
    const childAspects = Array.isArray(definition.aspects) ? definition.aspects : [];
    if (parentAspects.length || childAspects.length) {
      merged.aspects = [
        ...parentAspects.map((row) => structuredClone(row)),
        ...childAspects.map((row) => structuredClone(row)),
      ];
    }
    return merged;
  }
  function rootChain(key, trail = []) {
    if (trail.includes(key)) {errors.push(`Item inheritance cycle: ${[...trail, key].join(" -> ")}`); return;}
    const row = data.invRoots.get(key)?.root;
    if (!row) {errors.push(`Missing item definition: ${key}`); return;}
    const base = reference(row.basetype, "inv");
    if (base) rootChain(base, [...trail, key]);
    sources.push({kind: "item", id: key, definition: row});
  }
  rootChain(host);
  // Each typed part retains its own definition scope. Foreign parts do not
  // turn the host into an additional weapon/manufacturer. Never use a Set here.
  for (let index = 0; index < (partKeys || []).length; index++) {
    const root = String(partRoots?.[index] || host).toLowerCase();
    const key = String(partKeys[index] || "").toLowerCase();
    const definition = data.invRoots.get(root)?.parts.get(key);
    if (!definition) {errors.push(`Missing part definition: ${root}.${key} (serial position ${index})`); continue;}
    try { sources.push({kind: "part", id: `${root}.${key}`, index, root, key, definition: inheritedPart(definition)}); }
    catch (error) { errors.push(error.message); }
  }
  return {sources, errors};
}

function resolveStatDefinition(key, definitions, trail = []) {
  key = String(key).toLowerCase();
  if (trail.includes(key)) throw new Error(`Stat inheritance cycle: ${[...trail, key].join(" -> ")}`);
  const row = definitions.get(key);
  if (!row) throw new Error(`Missing stat definition: ${key}`);
  const parent = reference(row.parent, "inv_stat");
  const base = parent ? resolveStatDefinition(parent, definitions, [...trail, key]) : {attributes: new Map(), categories: new Map(), lineage: []};
  // Nexus subtable records are keyed patches: Order's base multiplier augments
  // Weapon's damage definition, rather than replacing that entire definition.
  for (const [field, inner] of [["attributes", "attribute"], ["categories", "category"]]) {
    for (const wrapper of row[field]?.[inner] || []) {
      for (const [name, value] of Object.entries(wrapper)) {
        const id = name.toLowerCase();
        base[field].set(id, mergeDefinition(base[field].get(id), value));
      }
    }
  }
  base.lineage.push(key);
  return base;
}

/**
 * FirmwareAspect rows carry firmware'fw_*' but no uistatstoinclude. Live cards
 * still paint the Firmware widget from matching ui_stat comparison ids — inject
 * those keys so offline equipment/guns get the same firmware group.
 */
function firmwareIdFromAspect(definition) {
  if (!definition || typeof definition !== "object") return "";
  if (!/FirmwareAspect/i.test(String(definition.structtype || ""))) return "";
  const raw =
    reference(definition.firmware, "firmware") ||
    String(definition.firmware || "")
      .replace(/^firmware'/i, "")
      .replace(/'$/, "")
      .trim()
      .toLowerCase();
  if (!raw) return "";
  return raw.startsWith("fw_") ? raw : `fw_${raw}`;
}

function firmwareUiStatKeys(definition, data) {
  const fwId = firmwareIdFromAspect(definition);
  if (!fwId) return [];
  const keys = [];
  const seen = new Set();
  // Prefer explicit ui_stat refs from Nexus-Data-Firmware* tiers when bundled.
  const fwRow = data?.firmware?.get?.(fwId);
  if (fwRow && Array.isArray(fwRow.bonusaugmentdefs)) {
    for (const tier of fwRow.bonusaugmentdefs) {
      const ref = reference(tier?.uistat, "ui_stat") || String(tier?.uistat || "")
        .replace(/^ui_stat'/i, "")
        .replace(/'$/, "")
        .trim()
        .toLowerCase();
      if (ref && !seen.has(ref)) {
        seen.add(ref);
        keys.push(ref);
      }
    }
  }
  if (!data?.uiStats) return keys;
  for (const [key, stat] of data.uiStats) {
    if (String(stat?.comparisonidentifier || "").trim().toLowerCase() !== fwId) continue;
    if (seen.has(key)) continue;
    seen.add(key);
    keys.push(key);
  }
  return keys;
}

function assembleItemDefinitions(data, item) {
  const {sources, errors} = collectItemSources(data, item);
  const aspects = [], uiStats = [];
  let statKey = "", namingStrategy = "";
  for (const source of sources) {
    // Only the host's inheritance chain supplies item-level configuration.
    // Part definitions contribute their own aspects and UI stat references.
    if (source.kind === "item") {
      statKey = reference(source.definition.stats, "inv_stat") || statKey;
      namingStrategy = reference(source.definition.namingstrategydef, "inv_name_strategy") || namingStrategy;
    }
    for (const uiStat of source.definition.uistats || []) uiStats.push({source: source.id, reference: uiStat});
    for (const [index, aspect] of (source.definition.aspects || []).entries()) {
      try {
        const definition = resolveAspect(aspect, data.invAspects);
        // Expand templates after inheritance: a child can change just the row
        // while inheriting the table, columns and template-enabled flag.
        if (String(definition.battributeeffecttemplateset).toLowerCase() === "true") {
          const tablePatch = definition.attributeeffecttemplate?.modifiervalue?.datatablevalue;
          if (tablePatch) {
            // Nexus mis-wires some legendary uniques (Triple Bypass → Unique_AdrenalinePump
            // Healing_Scale 0.25). Prefer Unique_<stem> from part_augment_unique_<stem>
            // when that row exists on Table_RepKit_Uniques.
            const patched = { ...tablePatch };
            const srcId = String(source.id || "").toLowerCase();
            const m = srcId.match(/(?:^|\.)part_augment_unique_([a-z0-9_]+)$/);
            const tableName = String(patched.datatable || "").toLowerCase();
            if (m && /table_repkit_uniques/.test(tableName)) {
              const want = `unique_${m[1]}`;
              const table = data.tables && data.tables.get("table_repkit_uniques");
              const cur = String(patched.rowname || "").toLowerCase();
              if (table && table.has(want) && cur.startsWith("unique_") && cur !== want) {
                patched.rowname = want;
              }
            }
            const patch = (node) => {
              if (!node || typeof node !== "object") return;
              if (node.datatablevalue) node.datatablevalue = { ...node.datatablevalue, ...patched };
              for (const [key, child] of Object.entries(node)) {
                if (key !== "datatablevalue") patch(child);
              }
            };
            patch(definition.attributeeffects);
            patch(definition.usemodeattributeeffects);
          }
        }
        // FirmwareAspect has no uistatstoinclude in Nexus — synthesize the widget rows.
        const fwKeys = firmwareUiStatKeys(definition, data);
        if (fwKeys.length) {
          const existing = Array.isArray(definition.uistatstoinclude)
            ? definition.uistatstoinclude.map((ref) => reference(ref, "ui_stat") || String(ref || "").toLowerCase())
            : [];
          const seen = new Set(existing.filter(Boolean));
          const merged = Array.isArray(definition.uistatstoinclude)
            ? [...definition.uistatstoinclude]
            : [];
          for (const key of fwKeys) {
            if (seen.has(key)) continue;
            seen.add(key);
            merged.push(`ui_stat'${key}'`);
          }
          definition.uistatstoinclude = merged;
        }
        aspects.push({source: source.id, serialIndex: source.index ?? null, aspectIndex: index, definition});
      } catch (error) { errors.push(`${source.id}: ${error.message}`); }
    }
  }
  let stats = null;
  if (statKey) {
    try { stats = resolveStatDefinition(statKey, data.invStats); }
    catch (error) { errors.push(error.message); }
  } else errors.push("Missing item stat configuration");
  // All candidates remain present with their native selection priorities and
  // use-mode masks. This stage must not guess which conflicting behaviors win.
  return {sources, aspects, uiStats, statKey, stats, namingStrategy, errors};
}

module.exports = {
  reference,
  mergeDefinition,
  resolveAspect,
  collectItemSources,
  resolveStatDefinition,
  assembleItemDefinitions,
  firmwareIdFromAspect,
  firmwareUiStatKeys,
};
