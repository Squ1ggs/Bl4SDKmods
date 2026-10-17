"use strict";

/**
 * Phase B — offline weapon card stats from mined Nexus data only.
 *
 * Game paths mirrored (do not invent):
 * - BalanceFormulaValueResolver: Multiplier * (Level ^ Power) * Scalar + Offset
 *   (Gbx ValueFormula; field wiring from Nexus attribute defs)
 * - PropertyValueResolver leaves from assembled part behaviors (FireRate, Damage, …)
 * - inv_aspect attributeeffecttemplate expansion (Resident column→attribute maps)
 * - GbxExpressionValueResolver / GbxConditionalAttributeValueResolver from attribute JSON
 * - weapon_dps_estimate expression from Nexus-Data-attribute0.json
 *
 * Leaves null when a required mined resolver/input cannot be evaluated.
 */

const fs = require("fs");
const path = require("path");

const GUN_TYPES = new Set([
  "Pistol",
  "Shotgun",
  "Assault Rifle",
  "SMG",
  "Sniper",
  "Heavy Weapon",
  "Heavy Gun Ordnance"
]);

function readJson(filePath) {
  try {
    if (!filePath || !fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

function attrKey(ref) {
  if (ref == null) return "";
  const s = String(ref);
  const m = s.match(/attribute'([^']+)'/i) || s.match(/^'?([^']+)'?$/);
  return String(m ? m[1] : s).trim().toLowerCase();
}

function aspectKey(ref) {
  if (ref == null) return "";
  const s = String(ref);
  const m = s.match(/inv_aspect'([^']+)'/i);
  return String(m ? m[1] : s).trim().toLowerCase();
}

function normalizeDatatableName(ref) {
  if (!ref || typeof ref !== "string") return "";
  return ref.replace(/^gbx_ue_data_table'/i, "").replace(/'$/, "").trim();
}

function parseNum(x) {
  if (x == null || x === "") return NaN;
  if (typeof x === "number" && Number.isFinite(x)) return x;
  const n = parseFloat(String(x));
  return Number.isFinite(n) ? n : NaN;
}

function unwrapNexus(value) {
  if (Array.isArray(value)) return value.map(unwrapNexus);
  if (!value || typeof value !== "object") return value;
  if (Object.prototype.hasOwnProperty.call(value, "__typeFlags") && Object.prototype.hasOwnProperty.call(value, "value")) {
    return unwrapNexus(value.value);
  }
  const out = {};
  for (const [k, v] of Object.entries(value)) out[k] = unwrapNexus(v);
  return out;
}

function loadKeyedRecords(legitItems, filePrefix, rootKey) {
  const map = new Map();
  if (!legitItems || !fs.existsSync(legitItems)) return map;
  for (const name of fs.readdirSync(legitItems)) {
    if (!name.startsWith(filePrefix) || !name.endsWith(".json")) continue;
    const payload = readJson(path.join(legitItems, name));
    if (!payload) continue;
    const roots = rootKey ? [rootKey] : Object.keys(payload);
    for (const rk of roots) {
      const block = payload[rk];
      if (!block || !Array.isArray(block.records)) continue;
      for (const rec of block.records) {
        for (const ent of rec.entries || []) {
          if (!ent || typeof ent !== "object") continue;
          for (const [k, v] of Object.entries(ent)) {
            if (k.startsWith("__") || v == null) continue;
            // DLC reference-only records must not erase a concrete base row.
            if (typeof v !== "object" || Array.isArray(v)) continue;
            const fields = Object.keys(v).filter(field => !field.startsWith("__") && field !== rk);
            if (!fields.length && map.has(String(k).toLowerCase())) continue;
            map.set(String(k).toLowerCase(), v);
          }
        }
      }
    }
  }
  return map;
}

/** Firmware shards are typed wrappers; unwrap for name / tier lookups. */
function loadFirmwareRecords(legitItems) {
  const raw = loadKeyedRecords(legitItems, "Nexus-Data-Firmware", "firmware");
  const map = new Map();
  for (const [key, row] of raw) {
    map.set(key, unwrapNexus(row));
  }
  return map;
}

function localizedFirmwareName(value) {
  const text = String(value || "");
  const parts = text.split(",");
  if (parts.length >= 3 && /^\s*[0-9A-Fa-f]{32}\s*$/.test(parts[1] || "")) {
    return parts.slice(2).join(",").trim();
  }
  return text.replace(/^[^,]*,\s*[a-f0-9]{16,32},\s*/i, "").trim();
}

function firmwareMetaFromTable(firmwareMap, fwId) {
  if (!firmwareMap || !fwId) return null;
  const row = firmwareMap.get(String(fwId).toLowerCase());
  if (!row || typeof row !== "object") return null;
  const name = localizedFirmwareName(row.name) || "";
  const tiers = Array.isArray(row.bonusaugmentdefs) ? row.bonusaugmentdefs.length : 0;
  const uiKeys = [];
  for (const tier of row.bonusaugmentdefs || []) {
    const ref = String(tier?.uistat || "").match(/^ui_stat'([^']+)'$/i);
    if (ref) uiKeys.push(ref[1].toLowerCase());
  }
  return {name, tierCount: Math.max(1, Math.min(3, tiers || 1)), uiKeys, id: String(fwId).toLowerCase()};
}

function loadDatatables(legitItems, rowDefaultsPath) {
  /** @type {Map<string, Map<string, Record<string, number>>>} */
  const tables = new Map();
  const rowDefaults = readJson(rowDefaultsPath || path.join(legitItems, "native_table_row_defaults.json"))?.definitions || {};
  const raw = loadKeyedRecords(legitItems, "Nexus-Data-gbx_ue_data_table", "gbx_ue_data_table");
  for (const [tableName, entry] of raw) {
    const rows = new Map();
    const rowStruct = rowDefaults[String(entry.row_struct || "").toLowerCase()] || {};
    const floatColumns = new Set((rowStruct.properties || [])
      .filter(property => property.Type === "FloatProperty")
      .map(property => normalizeDatatableColumnKey(property.Name) || String(property.Name).toLowerCase()));
    for (const row of entry.data || []) {
      if (!row || row.row_name == null) continue;
      // Cooked Nexus rows omit cells equal to their Unreal row-struct default.
      // Populate only defaults actually extracted from that exact struct.
      // Track which keys came from the sparse row so ModifierValue Constant can
      // win when a column was omitted (see resolveValueNode).
      const cells = {};
      const explicit = new Set();
      const defaults = rowStruct.defaults || {};
      for (const [ck, cv] of Object.entries(defaults)) {
        if (typeof cv === "number" && Number.isFinite(cv)) cells[normalizeDatatableColumnKey(ck) || String(ck).toLowerCase()] = cv;
      }
      const rv = row.row_value || {};
      for (const [ck, cv] of Object.entries(rv)) {
        const n = parseNum(cv);
        if (!Number.isNaN(n)) {
          const key = normalizeDatatableColumnKey(ck) || String(ck).toLowerCase();
          cells[key] = n;
          explicit.add(key);
        }
      }
      for (const key of floatColumns) if (Object.hasOwn(cells, key)) cells[key] = Math.fround(cells[key]);
      cells.__explicit = explicit;
      rows.set(String(row.row_name).toLowerCase(), cells);
    }
    tables.set(tableName.toLowerCase(), rows);
  }
  return tables;
}

function loadInvRoots(legitItems) {
  /** @type {Map<string, { root: object, parts: Map<string, object> }>} */
  const bySet = new Map();
  if (!legitItems || !fs.existsSync(legitItems)) return bySet;

  const ensure = (rootKey) => {
    const key = String(rootKey || "").toLowerCase();
    if (!key) return null;
    if (!bySet.has(key)) bySet.set(key, { root: null, parts: new Map() });
    return bySet.get(key);
  };

  const ingestDeps = (bucket, entry) => {
    if (!bucket) return;
    for (const dep of entry.__dep_entries || []) {
      if (!dep || typeof dep !== "object") continue;
      for (const [pk, part] of Object.entries(dep)) {
        if (
          pk.startsWith("__")
          || pk === "depTableName"
          || pk === "depTableId"
          || pk === "depIndex"
        ) {
          continue;
        }
        if (!part || typeof part !== "object") continue;
        const partKey = String(pk).toLowerCase();
        if (!bucket.parts.has(partKey)) bucket.parts.set(partKey, part);
      }
    }
  };

  for (const name of fs.readdirSync(legitItems)) {
    if (!name.startsWith("Nexus-Data-inv") || !name.endsWith(".json")) continue;
    if (name.includes("inv_name") || name.includes("inv_stat") || name.includes("inv_custom")) continue;
    const payload = readJson(path.join(legitItems, name));
    const records = (((payload || {}).inv || {}).records) || [];
    for (const rec of records) {
      for (const entry of rec.entries || []) {
        if (!entry || typeof entry !== "object") continue;
        // Live root body (ord_ps: { ... }) and null wrappers (ord_ps: null + __dep_entries)
        // both carry part aspects; uniques like Roulette live on the null wrappers.
        for (const [k, v] of Object.entries(entry)) {
          if (k.startsWith("__")) continue;
          const bucket = ensure(k);
          if (!bucket) continue;
          if (v && typeof v === "object") bucket.root = bucket.root || v;
          ingestDeps(bucket, entry);
          if (v && typeof v === "object") ingestDeps(bucket, v);
        }
      }
    }
  }
  return bySet;
}

/**
 * Nexus dumps store friendly cell keys (firerate_value). Inv behavior graphs often
 * still reference the cooked UE export name (FireRate_Value_36_<32-hex GUID>).
 * Strip that suffix so PropertyValueResolver datatable leaves resolve.
 */
function normalizeDatatableColumnKey(columnName) {
  const raw = String(columnName || "").trim().toLowerCase();
  if (!raw || raw === "none") return "";
  const stripped = raw.replace(/_\d+_[0-9a-f]{32}$/i, "");
  return stripped || raw;
}

function findDatatableRow(tables, tableRef, rowName) {
  const tableName = normalizeDatatableName(tableRef).toLowerCase();
  if (!tableName || tableName === "none") return null;
  const table = tables.get(tableName);
  if (!table) return null;
  const wantRow = String(rowName || "").toLowerCase();
  let row = table.get(wantRow);
  if (!row && wantRow) {
    for (const [rk, rv] of table) {
      if (rk.toLowerCase() === wantRow) {
        row = rv;
        break;
      }
    }
  }
  return row || null;
}

function lookupRowCell(row, columnName, {explicitOnly = false} = {}) {
  if (!row) return null;
  const ck = String(columnName || "").toLowerCase();
  if (!ck || ck === "none") {
    const vals = Object.entries(row)
      .filter(([k]) => k !== "__explicit")
      .map(([, v]) => v);
    return vals.length === 1 ? vals[0] : null;
  }
  const explicit = row.__explicit instanceof Set ? row.__explicit : null;
  const allow = (key) => !explicitOnly || !explicit || explicit.has(key);
  if (Object.prototype.hasOwnProperty.call(row, ck) && ck !== "__explicit" && allow(ck)) return row[ck];
  const friendly = normalizeDatatableColumnKey(ck);
  if (friendly && Object.prototype.hasOwnProperty.call(row, friendly) && allow(friendly)) return row[friendly];
  for (const [k, v] of Object.entries(row)) {
    if (k === "__explicit") continue;
    const lk = k.toLowerCase();
    if ((lk === ck || (friendly && lk === friendly)) && allow(k)) return v;
    if ((lk.startsWith(`${ck}_`) || (friendly && lk.startsWith(`${friendly}_`))) && allow(k)) return v;
  }
  return null;
}

function getDatatableCell(tables, tableRef, rowName, columnName, options) {
  return lookupRowCell(findDatatableRow(tables, tableRef, rowName), columnName, options);
}

function cloneEffect(effect, templateDt) {
  const out = JSON.parse(JSON.stringify(effect));
  const patchValue = (node) => {
    if (!node || typeof node !== "object") return;
    if (node.datatablevalue && typeof node.datatablevalue === "object") {
      if (templateDt.datatable) node.datatablevalue.datatable = templateDt.datatable;
      if (templateDt.rowname) node.datatablevalue.rowname = templateDt.rowname;
    }
    for (const v of Object.values(node)) {
      if (v && typeof v === "object") patchValue(v);
    }
  };
  patchValue(out.modifiervalue);
  return out;
}

function expandTemplateEffects(aspectDef, templateModValue) {
  const dt = (((templateModValue || {}).datatablevalue) || {});
  if (!dt.datatable && !dt.rowname) return [];
  const effects = [];
  for (const block of aspectDef.usemodeattributeeffects || []) {
    for (const eff of block.attributeeffects || []) {
      effects.push(cloneEffect(eff, dt));
    }
  }
  for (const eff of aspectDef.attributeeffects || []) {
    effects.push(cloneEffect(eff, dt));
  }
  return effects;
}

function collectEffectsFromAspect(aspect, invAspects, sink) {
  if (!aspect || typeof aspect !== "object") return;
  if (String(aspect.battributeeffecttemplateset || "").toLowerCase() === "true") {
    const parent = aspectKey(aspect.parent);
    const def = invAspects.get(parent);
    const templateVal = (aspect.attributeeffecttemplate || {}).modifiervalue;
    if (def && templateVal) {
      for (const eff of expandTemplateEffects(def, templateVal)) sink.push(eff);
    }
  }
  for (const block of aspect.usemodeattributeeffects || []) {
    for (const eff of block.attributeeffects || []) sink.push(eff);
  }
  for (const eff of aspect.attributeeffects || []) sink.push(eff);
}

function walkBehaviorBindings(aspect, sink) {
  const behavior = aspect && aspect.behavior;
  if (!behavior || typeof behavior !== "object") return;
  const map = {
    firerate: "weapon_fire_rate",
    damage: "weapon_damage",
    reloadtime: "weapon_reload_time",
    maxloadedammo: "weapon_max_loaded_ammo",
    projectilespershot: "weapon_projectile_per_shot",
    chargetime: "weapon_charge_time",
    shotammocost: "weapon_shot_cost"
  };
  for (const [prop, attr] of Object.entries(map)) {
    if (behavior[prop] != null) {
      sink.push({
        attr,
        value: behavior[prop],
        postscale: parseNum(behavior[prop].postscale)
      });
    }
  }
}

function emptyMods() {
  return { override: null, preAdd: [], scales: [], postAdd: [], scaleSimple: [], ordered: [] };
}

function addModifier(bag, attr, modType, value) {
  if (!attr || value == null || Number.isNaN(value)) return;
  const key = attrKey(attr);
  if (!key) return;
  if (!bag.has(key)) bag.set(key, emptyMods());
  const slot = bag.get(key);
  const t = String(modType || "").toLowerCase();
  let kind = "scaleSimple";
  if (t === "overridebasevalue" || t === "override") kind = "override";
  else if (t === "preadd") kind = "preAdd";
  else if (t === "postadd") kind = "postAdd";
  else if (t === "scaleadd" || t === "scalesimple" || !t) kind = "scaleSimple";
  else if (t === "scalemultiply" || t === "scale" || t === "premultiply") kind = "scales";
  slot.ordered.push({ kind, value });
  // Keep bag fields for naming_factors / diagnostics (last override wins).
  if (kind === "override") slot.override = value;
  else if (kind === "preAdd") slot.preAdd.push(value);
  else if (kind === "postAdd") slot.postAdd.push(value);
  else if (kind === "scaleSimple") slot.scaleSimple.push(value);
  else if (kind === "scales") slot.scales.push(value);
}

function applyMods(base, mods) {
  const f32 = (value) => (Number.isFinite(value) ? Math.fround(value) : value);
  if (!mods) return f32(base);
  const ordered = Array.isArray(mods.ordered) && mods.ordered.length ? mods.ordered : null;
  // Ordered path: OverrideBaseValue mid-stream replaces the running value and
  // clears prior scale/pre channels (GBX: override resets the base; later parts
  // like magazine init must not be zeroed by an earlier ScaleAdd -1).
  if (ordered) {
    let v = f32(base);
    let preAdd = [];
    let scales = [];
    let scaleSimple = [];
    let postAdd = [];
    const flush = () => {
      if (v == null || Number.isNaN(v)) return;
      for (const a of preAdd) v = f32(v + f32(a));
      for (const s of scales) v = f32(v * f32(s));
      const simple = scaleSimple.reduce((sum, value) => f32(sum + f32(value)), 0);
      v = f32(v * f32(1 + simple));
      for (const a of postAdd) v = f32(v + f32(a));
      preAdd = [];
      scales = [];
      scaleSimple = [];
      postAdd = [];
    };
    for (const step of ordered) {
      if (step.kind === "override") {
        // OverrideBaseValue replaces the running base. Drop PostAdds aimed at the
        // pre-override base, and drop full ScaleAdd -1 dumps (Abyss/charge barrels
        // zero the mag before PostAdd+2 — that must not wipe a later mag Override).
        // Fractional ScaleAdds (e.g. reload -0.5) still apply on the new base.
        postAdd = [];
        scaleSimple = scaleSimple.filter((s) => Number(s) > -1 + 1e-6);
        v = f32(step.value);
        continue;
      }
      if (step.kind === "preAdd") preAdd.push(step.value);
      else if (step.kind === "postAdd") postAdd.push(step.value);
      else if (step.kind === "scaleSimple") scaleSimple.push(step.value);
      else if (step.kind === "scales") scales.push(step.value);
    }
    flush();
    return v == null || Number.isNaN(v) ? null : v;
  }
  let v = f32(base);
  if (mods.override != null && !Number.isNaN(mods.override)) v = f32(mods.override);
  if (v == null || Number.isNaN(v)) return null;
  for (const a of mods.preAdd) v = f32(v + f32(a));
  for (const s of mods.scales) v = f32(v * f32(s));
  const simpleScale = mods.scaleSimple.reduce((sum, value) => f32(sum + f32(value)), 0);
  v = f32(v * f32(1 + simpleScale));
  for (const a of mods.postAdd) v = f32(v + f32(a));
  return v;
}

function resolveValueNode(node, ctx, depth = 0) {
  if (node == null || depth > 24) return null;
  if (typeof node === "number") return node;
  if (typeof node === "string") {
    const n = parseNum(node);
    return Number.isNaN(n) ? null : n;
  }
  if (typeof node !== "object") return null;

  if (
    node.constant != null
    && (node.datatablevalue == null || normalizeDatatableName(node.datatablevalue.datatable) === "none")
  ) {
    const c = parseNum(node.constant);
    if (!Number.isNaN(c)) {
      const ps = parseNum(node.postscale);
      return Number.isNaN(ps) ? c : c * ps;
    }
  }
  if (node.datatablevalue && typeof node.datatablevalue === "object") {
    const dt = node.datatablevalue;
    const withPost = (value) => {
      const ps = parseNum(node.postscale);
      return Number.isNaN(ps) ? value : value * ps;
    };
    // Prefer cells actually present on the sparse Nexus row. Omitted columns are
    // Unreal-default; ModifierValue.Constant is the authored fallback (e.g. Acc
    // Uistat SwayMax stays at struct default 1 in the table dump but the SMG
    // weight aspect still carries Constant 15 — matching live/ncs-lookup cards).
    const explicit = getDatatableCell(ctx.tables, dt.datatable, dt.rowname, dt.columnname, {
      explicitOnly: true
    });
    if (explicit != null) return withPost(explicit);
    if (node.constant != null && normalizeDatatableName(dt.datatable) !== "none") {
      const c = parseNum(node.constant);
      if (!Number.isNaN(c)) return withPost(c);
    }
    const cell = getDatatableCell(ctx.tables, dt.datatable, dt.rowname, dt.columnname);
    if (cell != null) return withPost(cell);
  }
  if (node.attribute) {
    const v = resolveAttribute(attrKey(node.attribute), ctx, depth + 1);
    if (v != null) {
      const ps = parseNum(node.postscale);
      return Number.isNaN(ps) ? v : v * ps;
    }
  }
  return null;
}

function evalBalanceFormula(valueDef, ctx, depth) {
  if (!valueDef || typeof valueDef !== "object") return null;
  const mult = resolveValueNode(valueDef.multiplier, ctx, depth + 1);
  const level = resolveValueNode(valueDef.level, ctx, depth + 1);
  const power = resolveValueNode(valueDef.power, ctx, depth + 1);
  const scalar = valueDef.scalar != null ? resolveValueNode(valueDef.scalar, ctx, depth + 1) : 1;
  const offset = valueDef.offset != null ? resolveValueNode(valueDef.offset, ctx, depth + 1) : 0;
  if (mult == null || level == null || power == null) return null;
  const s = scalar == null || Number.isNaN(scalar) ? 1 : scalar;
  const o = offset == null || Number.isNaN(offset) ? 0 : offset;
  return mult * (level ** power) * s + o;
}

function evalExpression(expr, ctx, depth) {
  if (expr == null) return null;
  if (typeof expr === "string") {
    const replaced = expr.replace(/attr\(([^)]+)\)/gi, (_, name) => {
      const v = resolveAttribute(attrKey(name), ctx, depth + 1);
      return v == null ? "NaN" : String(v);
    });
    if (/NaN/.test(replaced)) return null;
    if (!/^[\d\s.+\-*/()<>=!&|]+$/.test(replaced)) return null;
    try {
      // eslint-disable-next-line no-new-func
      const v = Function(`"use strict"; return (${replaced});`)();
      return typeof v === "boolean" ? Number(v) : Number.isFinite(v) ? v : null;
    } catch {
      return null;
    }
  }
  if (typeof expr === "object" && expr.formula) {
    const vars = {};
    const pairs = ((((expr.variables || {}).variablevalues || {}).pairs) || {});
    for (const pair of Object.values(pairs)) {
      if (!pair || !pair.key) continue;
      const raw = pair.value && pair.value.value ? pair.value.value : pair.value;
      let v = null;
      if (raw && raw.type === "Attribute") {
        v = resolveAttribute(attrKey(raw.value), ctx, depth + 1);
      } else {
        v = resolveValueNode(raw, ctx, depth + 1);
      }
      if (v == null) return null;
      vars[pair.key] = v;
    }
    let formula = String(expr.formula).replace(/attr\(([^)]+)\)/gi, (_, name) => {
      const value = resolveAttribute(attrKey(name), ctx, depth + 1);
      return value == null ? "NaN" : String(value);
    });
    for (const [k, v] of Object.entries(vars)) {
      formula = formula.replace(new RegExp(`\\b${k}\\b`, "g"), String(v));
    }
    if (!/^[\d\s.+\-*/()<>=!&|]+$/.test(formula)) return null;
    try {
      // eslint-disable-next-line no-new-func
      const v = Function(`"use strict"; return (${formula});`)();
      if (typeof v === "boolean") return v ? 1 : 0;
      return Number.isFinite(v) ? v : null;
    } catch {
      return null;
    }
  }
  return null;
}

function evalConditional(valueDef, ctx, depth) {
  for (const row of valueDef.conditionalvalues || []) {
    const cond = row.condition || {};
    let ok = false;
    if (cond.externalattribute) {
      const v = resolveAttribute(attrKey(cond.externalattribute), ctx, depth + 1);
      ok = Boolean(v);
    } else if (cond.type === "ValueResolver" && cond.inlinestruct) {
      const v = evalExpression(cond.inlinestruct.expression, ctx, depth + 1);
      ok = Boolean(v);
    }
    if (ok) return resolveValueNode(row.value, ctx, depth + 1);
  }
  if (valueDef.defaultvalue) return resolveValueNode(valueDef.defaultvalue, ctx, depth + 1);
  return 0;
}

/** Wear/dirt/rust/sun live in InventoryStatsContainer; offline cards treat unset as 0 (new item). */
const WEAR_CONTAINER_DEFAULTS = {
  weapon_wear: 0,
  weapon_rust: 0,
  weapon_dirt: 0,
  weapon_sun_damage: 0
};

function priceAttrForItemType(itemType) {
  switch (String(itemType || "")) {
    case "Pistol":
      return "attr_calc_price_gun_pistol";
    case "Shotgun":
      return "attr_calc_price_gun_shotgun";
    case "Assault Rifle":
      return "attr_calc_price_gun_assault";
    case "SMG":
      return "attr_calc_price_gun_smg";
    case "Sniper":
      return "attr_calc_price_gun_sniper";
    case "Heavy Weapon":
    case "Heavy Gun Ordnance":
      return "attr_calc_price_heavy_weapon";
    default:
      return "";
  }
}

function resolveAttribute(name, ctx, depth = 0) {
  const key = attrKey(name);
  if (!key || depth > 32) return null;
  if (ctx.cache.has(key)) return ctx.cache.get(key);
  if (ctx.resolving.has(key)) return null;
  ctx.resolving.add(key);

  let base = null;
  if (Object.prototype.hasOwnProperty.call(ctx.injected, key)) {
    base = ctx.injected[key];
  } else if (ctx.propertyBases.has(key)) {
    base = ctx.propertyBases.get(key);
  } else {
    const def = ctx.attributes.get(key);
    const valueDef = def && def.value;
    const st = String((valueDef && valueDef.structtype) || "");
    if (valueDef) {
      if (/BalanceFormulaValueResolver/i.test(st)) {
        base = evalBalanceFormula(valueDef, ctx, depth);
      } else if (/GbxExpressionValueResolver/i.test(st)) {
        base = evalExpression(valueDef.expression, ctx, depth);
      } else if (/GbxConditionalAttributeValueResolver/i.test(st)) {
        base = evalConditional(valueDef, ctx, depth);
      } else if (/OakStatusEffectApplicationDefaultsValueResolver/i.test(st)) {
        // These table cells are structured status-application records, not
        // ordinary numeric columns. Only the resolved primary element is known.
        if (!Number(valueDef.index || 0) && ctx.element) {
          const row = ctx.statusDefaults?.data?.find(row => String(row.row_name).toLowerCase() === ctx.element);
          const field = row?.row_value?.[String(valueDef.property || "").toLowerCase()];
          const value = parseNum(field?.value);
          if (Number.isFinite(value)) base = Math.fround(value);
        }
      } else if (/GbxConstantAttributeValueResolver/i.test(st)) {
        base = resolveValueNode(valueDef.attributeinit || valueDef, ctx, depth);
      } else if (/PropertyValueResolver/i.test(st)) {
        base = ctx.propertyBases.has(key) ? ctx.propertyBases.get(key) : null;
      } else if (/BalanceStateValueResolver/i.test(st)) {
        if (
          /ExperienceLevel/i.test(String(valueDef.valuetoresolve || ""))
          && ctx.injected.weapon_level != null
        ) {
          base = ctx.injected.weapon_level;
        }
      } else if (/InventoryStatsContainerValueResolver/i.test(st)) {
        // Accuracy / sway weights with no mods stay null (need live containers).
        // Wear attrs are injected as 0. Compounding-style PreAdd-only attrs
        // (grenade_spring_compound_*_pct) start at 0 offline so mods apply.
        if (Object.prototype.hasOwnProperty.call(ctx.injected, key)) {
          base = ctx.injected[key];
        } else {
          const pending = ctx.modifiers.get(key);
          const hasMods = Boolean(
            pending &&
              (pending.override != null ||
                (pending.preAdd && pending.preAdd.length) ||
                (pending.scales && pending.scales.length) ||
                (pending.scaleSimple && pending.scaleSimple.length) ||
                (pending.postAdd && pending.postAdd.length) ||
                (pending.ordered && pending.ordered.length))
          );
          base = hasMods ? 0 : null;
        }
      } else if (valueDef.constant != null || valueDef.datatablevalue || valueDef.attribute) {
        base = resolveValueNode(valueDef, ctx, depth);
      }
    }
  }

  const mods = ctx.modifiers.get(key) || emptyMods();
  const final = applyMods(base, mods);
  ctx.cache.set(key, final);
  ctx.resolving.delete(key);
  return final;
}

function buildStatContext(data, item) {
  return require("./native_stat_context").createNativeContext(data, item, {resolveValueNode, addModifier});
}

/**
 * weapon_projectile_per_shot defaults to 1. If the FireProjectile behavior's
 * ProjectilesPerShot failed to install into propertyBases (missing inheritance
 * match, datatable miss, etc.), scan assembled behaviors and take the best
 * resolved pellet count so multi-pellet cards don't paint bare per-pellet Damage.
 */
function recoverProjectilesPerShot(ctx) {
  let best = Number(ctx.propertyBases.get("weapon_projectile_per_shot"));
  if (!Number.isFinite(best) || best < 1) best = 1;
  const aspects = ctx.assembled?.aspects || [];
  for (const row of aspects) {
    const behavior = row?.definition?.behavior;
    if (!behavior || typeof behavior !== "object") continue;
    const node =
      behavior.projectilespershot ||
      behavior.ProjectilesPerShot ||
      behavior.projectilesPerShot;
    if (node == null) continue;
    const value = resolveValueNode(node, ctx);
    if (Number.isFinite(value) && value > best) best = value;
  }
  // Part attribute effects can ScaleAdd/PreAdd pellets onto the base.
  const fromAttr = resolveAttribute("weapon_projectile_per_shot", ctx, 0);
  if (Number.isFinite(fromAttr) && fromAttr > best) best = fromAttr;
  if (Number.isFinite(best) && best > 1) {
    ctx.propertyBases.set("weapon_projectile_per_shot", best);
    ctx.cache.delete("weapon_projectile_per_shot");
  }
  return best;
}

function roundStat(value, mode) {
  if (value == null || Number.isNaN(value)) return null;
  if (mode === "int") return Math.round(value);
  if (mode === "1") return Math.round(value * 10) / 10;
  return value;
}

function evaluateWeaponCardStats(card, data) {
  const empty = {
    dps: null,
    damage: null,
    accuracy: null,
    reload: null,
    fire_rate: null,
    magazine: null,
    crit: null,
    value: null,
    stats_ok: false,
    stats_source: "none",
    stats_blocked: [],
    native_secondary: [],
    native_firmware: [],
    native_text: [],
    native_groups: {},
    red_text: [],
  };
  if (!card || !GUN_TYPES.has(card.item_type)) return empty;
  if (!data || !card.set || !Array.isArray(card.part_keys) || !card.part_keys.length) {
    return { ...empty, stats_blocked: ["missing_set_or_parts"] };
  }

  const levelMatch = String(card.human || "").match(/^\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*(\d+)/);
  const level = Number(card.level != null ? card.level : (levelMatch ? levelMatch[1] : NaN));
  if (!Number.isFinite(level) || level <= 0) {
    return { ...empty, stats_blocked: ["missing_level"] };
  }

  const ctx = buildStatContext(data, {
    set: card.set,
    partKeys: card.part_keys,
    partRoots: card.part_roots,
    element: card.element,
    level
  });
  // Install pellet count before Damage UI rows / need() so multi-pellet guns
  // select uistat_damage_and_projectile_count and paint total shot Damage.
  recoverProjectilesPerShot(ctx);

  const blocked = [...ctx.errors];
  const need = (name, label, { positive = false } = {}) => {
    const v = resolveAttribute(name, ctx, 0);
    if (v == null || Number.isNaN(v) || (positive && v <= 0)) {
      blocked.push(label || name);
      return null;
    }
    return v;
  };

  // Real guns never resolve to 0 Damage/DPS — treat non-positive as missing so UI can fall back.
  const damage = need("weapon_damage", "weapon_damage", { positive: true });
  // Burst-fire compare blanks when BurstFireDelay is missing; fall back to FireRate.
  let fireRate = resolveAttribute("weapon_compare_burst_fire_rate", ctx, 0);
  if (fireRate == null || Number.isNaN(fireRate) || fireRate <= 0) {
    fireRate = resolveAttribute("weapon_fire_rate", ctx, 0);
  }
  if (fireRate == null || Number.isNaN(fireRate) || fireRate <= 0) {
    blocked.push("fire_rate");
    fireRate = null;
  }
  const reload = need("weapon_compare_reload_time", "reload", { positive: true });
  const magazine = need("weapon_compare_shots_until_reload", "magazine", { positive: true });
  const dps = need("weapon_dps_estimate", "dps", { positive: true });
  const crit = resolveAttribute("weapon_damage_modifier_add_critical_hit", ctx, 0);
  const accuracy = resolveAttribute("weapon_accuracy_ui_compare", ctx, 0);
  const elementDps = resolveAttribute("weapon_ui_elemental_dps", ctx);
  const elementChance = resolveAttribute("weapon_damage_modifier_base_status_effect_chance", ctx);
  const elementDps2 = resolveAttribute("weapon_ui_elemental_dps_mode02", ctx);
  const namingFactors = {};
  const namingAttrs = data.globals?.get("def_globals_oak_inventory")?.inventorynamingattributes?.pairs || {};
  for (const row of Object.values(namingAttrs)) {
    const key = attrKey(row.value);
    const mods = (ctx.namingModifiers || ctx.modifiers).get(key) || emptyMods();
    // Naming uses the assembled modifier contribution, before the weapon's
    // base damage/level is applied. Base overrides are initialization values.
    namingFactors[row.key] = applyMods(1, {
      ...mods,
      override: null,
      ordered: (mods.ordered || []).filter((step) => step.kind !== "override"),
    });
    if (ctx.unresolved.some(error => attrKey(error.attribute) === key)) namingFactors[row.key] = null;
  }

  // Sell: inv.monetaryvalue → attr_calc_price_gun_* (BalanceFormula) × part monetaryvaluemodifier scales.
  let value = null;
  const priceAttr = ctx.assembled.sources.filter(source => source.kind === "item")
    .map(source => source.definition.monetaryvalue?.attribute).filter(Boolean).at(-1)
    || priceAttrForItemType(card.item_type);
  if (priceAttr) {
    let basePrice = resolveAttribute(priceAttr, ctx, 0);
    if (basePrice != null && !Number.isNaN(basePrice)) {
      for (const ref of ctx.priceModAttrs || []) {
        const modKey = attrKey(ref);
        if (!modKey) continue;
        const scale = resolveAttribute(modKey, ctx, 0);
        if (scale == null || Number.isNaN(scale)) {
          blocked.push(`price_mod:${modKey}`);
          basePrice = null;
          break;
        }
        basePrice *= scale;
      }
      if (basePrice != null && Number.isFinite(basePrice) && basePrice >= 0) {
        // The native card receives a float representation of the capped signed
        // integer price (INT_MAX consequently displays as 2,147,483,648).
        value = Math.fround(Math.min(2147483647,Math.round(basePrice)));
      }
    } else {
      blocked.push(priceAttr);
    }
  }

  if (accuracy == null) blocked.push("weapon_accuracy_ui_compare");

  const perPelletDamage = roundStat(damage, "int");
  const projectileCount = roundStat(resolveAttribute("weapon_projectile_per_shot", ctx), "int");
  // Live primary Damage is per-pellet (or "N x M"). DPS already uses
  // weapon_damage_per_shot (= damage × projectiles) inside weapon_dps_estimate.
  // Do not store the product as damage — that inflated the primary row / fallbacks.

  const out = {
    dps: roundStat(dps, "int"),
    damage: perPelletDamage,
    damage_per_projectile: perPelletDamage,
    accuracy: accuracy == null ? null : Math.ceil(accuracy * 100),
    reload: roundStat(reload, "1"),
    fire_rate: roundStat(fireRate, "1"),
    magazine: roundStat(magazine, "int"),
    crit: crit == null || Number.isNaN(crit) ? null : roundStat(crit * 100, "1"),
    value,
    stats_ok: false,
    stats_source: "none",
    stats_blocked: blocked,
    naming_factors: namingFactors,
    native_naming_ready: ctx.assembled.errors.length === 0 && Number.isFinite(ctx.statModifiers.rarityScale),
    damage_radius: roundStat(resolveAttribute("weapon_damage_radius", ctx), "int"),
    shot_cost: roundStat(resolveAttribute("weapon_shot_cost", ctx), "int"),
    projectile_count: projectileCount
  };
  out.element_dps = roundStat(elementDps,"int");
  out.element_chance = Number.isFinite(elementChance) ? Math.ceil(elementChance*100) : null;
  out.element_text = elementDps > 0 && out.element_chance != null
    ? `${out.element_dps.toLocaleString("en-US")} DMG/s | ${out.element_chance}% Chance` : "";
  out.element_dps2 = roundStat(elementDps2, "int");
  out.element_text2 =
    elementDps2 > 0 && out.element_chance != null
      ? `${out.element_dps2.toLocaleString("en-US")} DMG/s | ${out.element_chance}% Chance`
      : "";
  // When weapon_dps_estimate fails but Damage + Fire Rate resolved, paint a
  // shot-total DPS so shotguns/multi-pellet guns are not left blank.
  if (out.dps == null && out.damage != null && out.fire_rate != null && out.fire_rate > 0) {
    const pellets = Number(out.projectile_count) > 0 ? Number(out.projectile_count) : 1;
    const shot = out.damage * pellets;
    out.dps = roundStat(shot * out.fire_rate, "int");
  }
  if (
    out.dps != null
    || out.damage != null
    || out.fire_rate != null
    || out.reload != null
    || out.magazine != null
    || out.value != null
  ) {
    out.stats_ok = true;
    out.stats_source = out.dps != null ? "offline_nexus_stats" : "partial_nexus";
  }
  // Legendary perks / alt-fire / red text / firmware / manu text come from assembled UI stats.
  try {
    const ui = collectWeaponUiLines(card, data, ctx);
    out.native_secondary = ui.secondary;
    out.native_firmware = ui.firmware;
    out.native_text = ui.text;
    out.native_groups = ui.groups;
    out.red_text = ui.red_text;
  } catch {
    out.native_secondary = [];
    out.native_firmware = [];
    out.native_text = [];
    out.native_groups = {};
    out.red_text = [];
  }
  return out;
}

/** Native card groups from Nexus ui_stat rows attached to the assembled gun. */
function collectWeaponUiLines(card, data, ctx) {
  const { reference } = require("./native_item_sources");
  const { localized, iconUrl } = require("./native_equipment_card");
  const { resolveStatModifierDisplayValue } = require("./stat_modifier_display");
  const truth = (value) => value === true || value === "true";
  const attr = (ref) => {
    const key = reference(ref, "attribute") || String(ref || "").toLowerCase();
    return resolveAttribute(key, ctx);
  };
  const format = (node) => {
    if (!node) return "";
    if (/NumericDisplayValue/.test(node.structtype || "")) {
      let value;
      if (truth(node.bshowstatmodifier)) {
        value = resolveStatModifierDisplayValue(node, ctx, reference);
        if (value == null) return "—";
      } else {
        value = attr(node.attributedef);
        if (value == null) return "—";
      }
      if (truth(node.bdisplayasoneminus)) value = 1 - value;
      if (truth(node.bcalculatewithreductionmath) && value > 0) value -= 1;
      if (node.signstyle === "OppositeSign") value *= -1;
      if (node.signstyle === "Positive") value = Math.abs(value);
      if (node.signstyle === "Negative") value = -Math.abs(value);
      if (truth(node.bdisplayaspercentage)) value *= 100;
      if (value === Infinity) return "infM";
      if (value === -Infinity) return "-infM";
      if (node.roundingmode === "RoundToInt") value = Math.round(value);
      if (node.roundingmode === "FloorToInt") value = Math.floor(value);
      if (node.roundingmode === "CeilToInt") value = Math.ceil(value);
      const explicitDecimals = Number(node.maximumfractionaldigits);
      const floatPrecision = Number(node.floatprecision);
      // Live cards usually paint whole percents (Amp drain 28%, not 27.5%).
      const decimals = Number.isFinite(explicitDecimals)
        ? explicitDecimals
        : Number.isFinite(floatPrecision)
          ? truth(node.bdisplayaspercentage)
            ? Math.max(0, floatPrecision - 1)
            : floatPrecision
          : truth(node.bdisplayaspercentage)
            ? 0
            : 1;
      let text = value.toLocaleString("en-US", {
        minimumFractionDigits:
          Number.isFinite(floatPrecision) && !truth(node.bdisplayaspercentage)
            ? Math.max(0, Math.min(decimals, 6))
            : 0,
        maximumFractionDigits: Math.max(0, Math.min(decimals, 6)),
      });
      if (truth(node.bdisplayplussign) && value > 0) text = "+" + text;
      if (truth(node.bdisplayaspercentage)) text += "%";
      return truth(node.buseformattext) && node.formattext
        ? localized(node.formattext).replaceAll("$VALUE$", text)
        : text;
    }
    if (!/StringDisplayValue/.test(node.structtype || "")) return "";
    let text = localized(node.formattext);
    const pairs = node.argsmap?.pairs || {};
    for (const row of Object.values(pairs)) {
      if (row?.key && text.includes("{" + row.key + "}")) {
        text = text.replaceAll("{" + row.key + "}", format(row.value));
      }
    }
    return text.replace(/\{[^{}]+\}/g, "—");
  };
  const condition = (cond) => {
    if (!cond?.attributedef) return true;
    const attrName = reference(cond.attributedef, "attribute") || attrKey(cond.attributedef);
    const value = attr(cond.attributedef);
    const compare = Number(cond.comparevalue || 0);
    if (value == null) {
      // Part-value resolvers are selection flags, not numeric stats. If a UI stat
      // was included by the selected aspect, an unavailable extracted flag must
      // not suppress that row (for example Torgue's sticky-mode description).
      const resolver = String(data.attributes.get(attrName)?.value?.structtype || "");
      return /WeaponPartValueResolver/.test(resolver);
    }
    switch (cond.comparetype || "Equal") {
      case "Equal":
      case "equal":
        return value === compare;
      case "NotEqual":
        return value !== compare;
      case "GreaterThan":
        return value > compare;
      case "GreaterOrEqual":
        return value >= compare;
      case "LessThan":
        return value < compare;
      case "LessOrEqual":
        return value <= compare;
      default:
        return false;
    }
  };
  const refs = [...(ctx.assembled.uiStats || []).map((row) => row.reference)];
  const excluded = new Set();
  for (const row of ctx.assembled.aspects || []) {
    refs.push(...(row.definition.uistatstoinclude || []));
    for (const ref of row.definition.uistatstoexclude || []) {
      excluded.add(reference(ref, "ui_stat"));
    }
  }
  const groups = {};
  const red_text = [];
  const seen = new Set();
  for (const key of new Set(refs.map((ref) => reference(ref, "ui_stat")).filter(Boolean))) {
    if (excluded.has(key)) continue;
    const stat = data.uiStats.get(key);
    if (!stat) continue;
    if (!condition(stat.displaycondition)) continue;
    const group = reference(stat.displaygroup, "ui_stat_group");
    let value = format(stat.statvalue);
    if (key === "uistat_accuracy") {
      const accuracy = resolveAttribute("weapon_accuracy_ui_compare", ctx);
      if (accuracy != null && !Number.isNaN(accuracy)) value = `${Math.ceil(accuracy * 100)}%`;
    }
    // Magazine / Ammo / shots-to-overheat are whole rounds on the live card.
    if (/^uistat_magazine_size|^uistat_shots_to_overheat|^uistat_ammo/i.test(key)) {
      const n = Number(String(value || "").replace(/,/g, ""));
      if (Number.isFinite(n) && n > 0) value = String(Math.round(n));
    }
    // Keep live "N x M" Damage format (per-pellet × pellets). Do not collapse to
    // the product — in-game primary shows the same multi form / first number.
    if (!value || value === "—") continue;
    const dedupe = `${group}:${value.toLowerCase()}`;
    if (seen.has(dedupe)) continue;
    seen.add(dedupe);
    const label = format(stat.statlabel);
    const row = {
      image: iconUrl(stat.staticon) || "",
      value,
      label: label || "",
      comparison: "",
      priority: Number(stat.sortingpriority || 0),
      ident: key,
      comparison_id: String(stat.comparisonidentifier || "").trim(),
      tier: Number((String(key).match(/_(\d+)$/) || [])[1]) || 0,
    };
    if (group === "redtext") {
      red_text.push(value.replace(/\[\/?(?:rarity_\w+|primary|secondary)\]/gi, "").trim());
    } else if (group) {
      (groups[group] ||= []).push(row);
    }
  }
  for (const rows of Object.values(groups)) rows.sort((a, b) => a.priority - b.priority);
  const legend =
    "coui://uiresources/_shared/assets/ico_ui_art_discovery/ico_misc_legendaries.png";
  const mapRow = (row) => {
    const { image, value, comparison, label, comparison_id, tier, ident, priority } = row;
    let painted = value;
    // Firmware tiers often resolve to bare bonus text — keep a Firmware title when label exists.
    if (label && !/firmware/i.test(value) && /firmware/i.test(label)) {
      painted = `[secondary]${label}[/secondary] — ${value}`;
    } else if (label && value && !value.includes(label) && /firmware/i.test(String(label))) {
      painted = `[secondary]${label}[/secondary] — ${value}`;
    }
    return {
      image: image || legend,
      value: painted,
      label: label || "",
      comparison: comparison || "",
      comparison_id: comparison_id || "",
      tier: Number(tier) || 0,
      ident: ident || "",
      priority: Number(priority) || 0,
    };
  };
  const secondaryRows = [
    ...(groups.secondary || []),
    ...(groups.augments || []),
    ...(groups.legendary || []),
  ].sort((a, b) => a.priority - b.priority);
  const mappedGroups = {};
  for (const [group, rows] of Object.entries(groups)) {
    mappedGroups[group] = rows.map(mapRow);
  }
  mappedGroups.secondary = secondaryRows.map(mapRow);
  return {
    groups: mappedGroups,
    secondary: mappedGroups.secondary || [],
    firmware: mappedGroups.firmware || [],
    text: (groups.text || []).map(({ value }) => String(value || "").trim()).filter(Boolean),
    red_text: red_text.filter(Boolean).slice(0, 3),
  };
}

function defaultLegitItems(sourceRoot) {
  return path.join(sourceRoot || process.cwd(), "resources", "LegitItems");
}

function loadStatData(options = {}) {
  const legitItems = options.legitItemsPath || defaultLegitItems(options.sourceRoot);
  return {
    legitItems,
    attributes: loadKeyedRecords(legitItems, "Nexus-Data-attribute", "attribute"),
    globals: loadKeyedRecords(legitItems, "Nexus-Data-Resident", "globals"),
    uiStats: loadKeyedRecords(legitItems, "Nexus-Data-ui_stat", "ui_stat"),
    tables: loadDatatables(legitItems, options.rowDefaultsPath),
    statusDefaults: loadKeyedRecords(legitItems,"Nexus-Data-gbx_ue_data_table","gbx_ue_data_table").get("status_application_defaults"),
    invAspects: loadKeyedRecords(legitItems, "Nexus-Data-Resident", "inv_aspect"),
    invStats: loadKeyedRecords(options.cardRulesPath || legitItems, "Nexus-Data-inv_stat", "inv_stat"),
    rarities: loadKeyedRecords(options.cardRulesPath || legitItems, "Nexus-Data-Rarity", "rarity"),
    behaviorRules: readJson(path.join(legitItems, "native_behavior_rules.json")),
    equipmentDefaults: readJson(path.join(legitItems, "native_equipment_defaults.json")),
    progressGraphs: loadKeyedRecords(legitItems,"Nexus-Data-progress_graph","progress_graph"),
    skillTrees: loadKeyedRecords(legitItems,"Nexus-Data-skilltrees_data","skilltrees_data"),
    uiTooltips: loadKeyedRecords(legitItems,"Nexus-Data-uitooltipdata","uitooltipdata"),
    firmware: loadFirmwareRecords(legitItems),
    invRoots: loadInvRoots(legitItems)
  };
}

function buildFirmwareBlockFromRows(rows, firmwareMap) {
  if (!Array.isArray(rows) || !rows.length) return null;
  const tiers = rows
    .map((row) => ({
      ...row,
      tier:
        Number(row.tier) ||
        Number((String(row.ident || "").match(/_(\d+)$/) || [])[1]) ||
        1,
    }))
    .sort((a, b) => b.tier - a.tier);
  const best = tiers[0];
  const count = Math.max(1, Math.min(3, best.tier || tiers.length));
  let name = String(best.label || best.loc_text || "")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+\d+\s*$/, "")
    .trim();
  let ident = String(best.comparison_id || "").trim();
  if (!ident) {
    const fromIdent = String(best.ident || "")
      .replace(/^uistat_firmware_/, "fw_")
      .replace(/_\d+$/, "")
      .trim();
    ident = fromIdent.startsWith("fw_") ? fromIdent : "";
  }
  if (!ident) {
    const guess = String(best.comparison_id || best.ident || "")
      .replace(/^uistat_firmware_/, "fw_")
      .replace(/_\d+$/, "")
      .trim();
    if (guess.startsWith("fw_")) ident = guess;
  }
  const meta = firmwareMetaFromTable(firmwareMap, ident);
  if (meta?.name) name = meta.name;
  const finalCount = Math.max(1, Math.min(3, Math.max(count, meta?.tierCount || 0)));
  if (!name) {
    const fromId = String(ident || best.ident || "")
      .replace(/^uistat_firmware_/, "fw_")
      .replace(/^fw_/, "")
      .replace(/_\d+$/, "")
      .replace(/_/g, " ")
      .trim();
    name = fromId.replace(/\b\w/g, (c) => c.toUpperCase()) || "Firmware";
  }
  // Never invent fw_jacked — blank ident means secondary text should paint instead.
  if (!ident) return null;
  return {
    firmwareident: ident,
    firmware: { loc_text: name, comparison: "" },
    firmwarestring: `${finalCount}/3`,
    firmwarecount: finalCount,
    firmwaretransfered: false,
  };
}

function attachStatsToCard(card, data) {
  if (!card || typeof card !== "object") return card;
  const equipment = require("./native_equipment_card").buildEquipmentCard(card,data,{buildStatContext,resolveAttribute});
  if (equipment) {
    card.native_equipment = equipment;
    card.value = equipment.price;
    card.stats_ok = Object.keys(equipment.values).length > 0;
    card.stats_source = "offline_native_equipment";
    card.stats_blocked = equipment.missing;
    const fwRows = Array.isArray(equipment.groups?.firmware) ? equipment.groups.firmware : [];
    card.native_firmware = fwRows;
    card.firmware_block = buildFirmwareBlockFromRows(fwRows, data.firmware);
    return card;
  }
  const stats = evaluateWeaponCardStats(card, data);
  card.dps = stats.dps;
  card.damage = stats.damage;
  card.damage_per_projectile = stats.damage_per_projectile;
  card.accuracy = stats.accuracy;
  card.reload = stats.reload;
  card.fire_rate = stats.fire_rate;
  card.magazine = stats.magazine;
  card.crit = stats.crit;
  card.value = stats.value;
  card.stats_ok = stats.stats_ok;
  card.stats_source = stats.stats_source;
  card.stats_blocked = stats.stats_blocked;
  card.naming_factors = stats.naming_factors;
  card.native_naming_ready = stats.native_naming_ready;
  card.damage_radius = stats.damage_radius;
  card.shot_cost = stats.shot_cost;
  card.projectile_count = stats.projectile_count;
  card.element_dps = stats.element_dps;
  card.element_chance = stats.element_chance;
  card.element_text = stats.element_text;
  card.element_dps2 = stats.element_dps2;
  card.element_text2 = stats.element_text2;
  card.native_secondary = stats.native_secondary || [];
  card.native_firmware = stats.native_firmware || [];
  card.native_text = stats.native_text || [];
  card.native_groups = stats.native_groups || {};
  card.red_text = stats.red_text || [];
  // Compact live firmware widget fields (icon class + name + 1–3 pips).
  card.firmware_block = buildFirmwareBlockFromRows(card.native_firmware, data.firmware);
  return card;
}

module.exports = {
  loadStatData,
  evaluateWeaponCardStats,
  attachStatsToCard,
  buildFirmwareBlockFromRows,
  loadFirmwareRecords,
  firmwareMetaFromTable,
  getDatatableCell,
  evalBalanceFormula,
  GUN_TYPES,
  buildStatContext, resolveAttribute, resolveValueNode, addModifier, applyMods, emptyMods
};
