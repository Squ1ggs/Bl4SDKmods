"use strict";

const {assembleItemDefinitions} = require("./native_item_sources");
const {collectStatModifiers} = require("./native_stat_modifiers");

function className(ref) { return String(ref || "").split(".").pop().replace(/'$/, ""); }
function attrKey(ref) {
  if (ref == null) return "";
  const s = String(ref);
  const m = s.match(/attribute'([^']+)'/i) || s.match(/^'?([^']+)'?$/);
  return String(m ? m[1] : s).trim().toLowerCase();
}
function propertyValue(object, propertyPath) {
  let value = object;
  for (const part of String(propertyPath || "").split(".")) {
    if (!value || typeof value !== "object") return undefined;
    const key = Object.keys(value).find(key => key.toLowerCase() === part.toLowerCase());
    if (key == null) return undefined;
    value = value[key];
  }
  return value;
}

/** primary / secondary / both for each InventoryAugmentAspect tag on assembled parts. */
function collectAugmentModes(assembled) {
  const sideBySource = new Map();
  for (const source of assembled.sources || []) {
    if (source.kind !== "part") continue;
    const def = source.definition || {};
    let side = "";
    if (def.primary_augment || (def.addtags || []).some((row) => row && row.primary_augment != null)) {
      side = "primary";
    } else if (def.secondary_augment || (def.addtags || []).some((row) => row && row.secondary_augment != null)) {
      side = "secondary";
    } else if (/_primary$/i.test(String(source.key || ""))) {
      side = "primary";
    } else if (/_secondary$/i.test(String(source.key || ""))) {
      side = "secondary";
    }
    if (side) sideBySource.set(source.id, side);
  }
  const modes = new Map();
  for (const row of assembled.aspects || []) {
    const tag = String(row.definition?.augment?.tag || "").trim().toLowerCase();
    if (!tag) continue;
    const side = sideBySource.get(row.source);
    if (!side) continue;
    const prev = modes.get(tag);
    if (!prev) modes.set(tag, side);
    else if (prev !== side) modes.set(tag, "both");
  }
  return modes;
}

/** Install OverrideBaseValue mods from def_globals_shield.shieldaugmentpartdata. */
function installShieldAugmentValues(ctx, data, api) {
  const rows = data.globals?.get("def_globals_shield")?.shieldaugmentpartdata;
  if (!Array.isArray(rows) || !ctx.augmentModes?.size) return;
  for (const row of rows) {
    const tag = String(row?.tagname || "").trim().toLowerCase();
    const mode = ctx.augmentModes.get(tag);
    if (!mode) continue;
    const attr = attrKey(row.attributetomodify);
    if (!attr) continue;
    const node = mode === "both"
      ? row.bothpartsvalue
      : mode === "secondary"
        ? row.secondarypartvalue
        : row.primarypartvalue;
    const value = api.resolveValueNode(node, ctx);
    if (!Number.isFinite(value)) {
      ctx.unresolved.push({source: `augment:${tag}`, attribute: attr, reason: "augment_value"});
      continue;
    }
    api.addModifier(ctx.modifiers, row.attributetomodify, row.modifiertype || "OverrideBaseValue", value);
  }
  // Element Resist row reads InventoryStatsContainer offline as null. When a
  // Resistant augment is present, mirror its magnitude onto the compare attr so
  // the Element group paints (same number the Resistant secondary describes).
  if (ctx.augmentModes.has("unv_resistant")) {
    const resist = api.resolveValueNode({attribute: "attribute'shield_unv_resistant_value'"}, ctx);
    if (Number.isFinite(resist)) {
      api.addModifier(
        ctx.modifiers,
        "attribute'shield_elemental_damage_reduction'",
        "OverrideBaseValue",
        Math.abs(resist)
      );
    }
  }
  ctx.cache.clear();
}

function createNativeContext(data, item, api) {
  const assembled = assembleItemDefinitions(data, item);
  const hasRepairBehavior = assembled.aspects.some(row =>
    /WeaponBehavior_Repair/.test(String(row.definition?.behavior?.behaviorclass || ""))
  );
  const ctx = {
    tables:data.tables, attributes:data.attributes, statusDefaults:data.statusDefaults,
    globals:data.globals, element:String(item.element || "").toLowerCase(), cache:new Map(), resolving:new Set(),
    injected:{
      weapon_level:Number(item.level),
      weapon_wear:0,
      weapon_rust:0,
      weapon_dirt:0,
      weapon_sun_damage:0,
      // GbxCondition_WeaponPartValue Reload=4 selects the CoV repair/overheat
      // branch. The extracted condition is non-numeric, so derive it from the
      // selected native repair behavior.
      ...(hasRepairBehavior ? {weapon_reload_four:1} : {}),
    },
    // The additive critical property starts at zero in the captured native
    // DamageModifierData; item and stat modifiers then contribute separately.
    propertyBases:new Map([
      ["weapon_damage_modifier_add_critical_hit",0],
      ["weapon_shot_cost",1],
      ["weapon_projectile_per_shot",1],
      // BurstFireDelay is often absent on FireProjectile defs; null breaks
      // weapon_burst_fire_rate (= auto_burst_count / (... + delay)) and blanks
      // the Fire Rate row even when weapon_fire_rate resolves correctly.
      ["weapon_burst_fire_delay",0],
    ]),
    modifiers:new Map(), namingModifiers:new Map(), priceModAttrs:[], assembled, errors:[...assembled.errors], unresolved:[],
    augmentModes: collectAugmentModes(assembled),
  };
  // Shield Capacity/Amp/Resistant (etc.) ScaleMultiply refs resolve through
  // InventoryAugmentAttributeValueResolver — seed those OverrideBaseValues
  // before part attributeeffects are evaluated.
  installShieldAugmentValues(ctx, data, api);
  const priorities = Object.fromEntries(Object.entries(data.behaviorRules?.enums?.EInventoryAspectSelectionPriority || {})
    .map(([value,name]) => [name,Number(value)]));
  const priority = row => priorities[row.definition.selectionpriority || "Default"] ?? 0;
  const parents = data.behaviorRules?.behaviorParents || {};
  const itemClass = assembled.sources.filter(row=>row.kind==="item").map(row=>className(row.definition.class)).filter(Boolean).at(-1);
  const itemDefaults = data.equipmentDefaults?.classes?.[itemClass];
  if (itemDefaults) for (const [key,attribute] of data.attributes) {
    const resolver = className(attribute.context?.structtype);
    const relevant = resolver === "InventoryContextResolver" || resolver === "ShieldAttributeContextResolver" && itemClass === "Shield"
      || resolver === "RepairKitContextResolver" && itemClass === "RepairKit" || resolver === "EnhancementContextResolver" && itemClass === "Enhancement";
    const property = String(attribute.value?.property?.propertypath || "").toLowerCase();
    if(relevant && Number.isFinite(itemDefaults[property]))ctx.propertyBases.set(key,itemDefaults[property]);
  }
  function isA(child, parent) {
    const seen = new Set();
    while (child && !seen.has(child)) {
      if (child === parent) return true;
      seen.add(child); child = parents[child];
    }
    return false;
  }
  const aspects = assembled.aspects.filter(row => !Number(row.definition.usemodebitmask || 0) || Number(row.definition.usemodebitmask) & 1);
  const behaviorCandidates = aspects.filter(row => row.definition.behavior && row.definition.bremovefromusemodes !== "true")
    .sort((a,b) => priority(b)-priority(a));
  // Primary use modes select the first highest-priority behavior. Attribute
  // contexts resolve through its actual extracted class inheritance.
  for (const [key, attribute] of data.attributes) {
    if (!/PropertyValueResolver/.test(attribute.value?.structtype || "")) continue;
    const wanted = className(attribute.context?.behaviortypetofurtherresolveto);
    if (!wanted) continue;
    const matches = behaviorCandidates.filter(row => isA(className(row.definition.behavior.behaviorclass), wanted)
      && propertyValue(row.definition.behavior,attribute.value.property?.propertypath) !== undefined);
    if (!matches.length) continue;
    // Prefer the highest resolved property value across matching behaviors.
    // Taking only the first priority match left multi-pellet barrels stuck at 1
    // when a secondary fire / underbarrel also exposed ProjectilesPerShot.
    let best = null;
    let bestSource = null;
    for (const candidate of matches) {
      const node = propertyValue(candidate.definition.behavior,attribute.value.property.propertypath);
      const value = api.resolveValueNode(node,ctx);
      if (!Number.isFinite(value)) continue;
      if (best == null || value > best) {
        best = value;
        bestSource = candidate.source;
      }
    }
    if (best != null) ctx.propertyBases.set(key,best);
    else ctx.unresolved.push({source:bestSource || matches[0].source,attribute:key,reason:"behavior_value"});
    ctx.cache.clear();
  }
  // Attribute effects are applied in native aspect-priority order. Keep every
  // occurrence; later lower-priority override effects remain meaningful.
  const effects = [];
  for (const row of [...aspects].sort((a,b) => priority(b)-priority(a))) {
    for (const effect of row.definition.attributeeffects || []) effects.push({...effect,source:row.source});
    for (const mode of row.definition.usemodeattributeeffects || []) {
      if (mode.usemodebitmask != null && !(Number(mode.usemodebitmask) & 1)) continue;
      for (const effect of mode.attributeeffects || []) effects.push({...effect,source:row.source});
    }
  }
  // Resolve initialization values against the unmodified weapon, then install
  // the modifiers together. This avoids order-dependent cache contamination.
  //
  // Skip WeaponType_Init Damage_Scale → weapon_damage. That ScaleMultiply is
  // authored on the type root (Shotgun = 1.25, Sniper = 1.05, …) but live item
  // cards do not include it — applying it here overshoots in-game Damage/DPS
  // by exactly that factor (4523 vs 3618 on shotguns).
  const isTypeInitDamageScale = (effect) => {
    const dt = effect?.modifiervalue?.datatablevalue;
    if (!dt || typeof dt !== "object") return false;
    const table = String(dt.datatable || "").toLowerCase();
    const col = String(dt.columnname || "").toLowerCase();
    const attr = String(effect.attributetomodify || "").toLowerCase();
    return /weapontype_init/.test(table) && /^damage_scale/.test(col) && /weapon_damage'/.test(attr);
  };
  const resolved = effects.map(effect => ({...effect,value:api.resolveValueNode(effect.modifiervalue,ctx)}));
  for (const effect of resolved) {
    if (isTypeInitDamageScale(effect)) {
      // Item names still rate Damage against the type scale (Shotgun 1.25).
      if (Number.isFinite(effect.value)) api.addModifier(ctx.namingModifiers, effect.attributetomodify, effect.modifiertype, effect.value);
      continue;
    }
    if (Number.isFinite(effect.value)) {
      // Nexus dumps omit ModifierType on repair_kit_augment_attr_init.
      // Unique table scales are ScaleAdd (0 = no-op, 0.25 = +25%, 1.5 duration → 6→15s).
      let modType = effect.modifiertype;
      if (!modType) {
        const attr = String(effect.attributetomodify || "").toLowerCase();
        const table = String(effect.modifiervalue?.datatablevalue?.datatable || "").toLowerCase();
        if (
          /table_repkit_uniques|repkit_augmentdata/.test(table) &&
          /repair_kit_(?:health|duration|cooldown)'/.test(attr)
        ) {
          modType = "ScaleAdd";
        }
      }
      api.addModifier(ctx.modifiers, effect.attributetomodify, modType || effect.modifiertype, effect.value);
      api.addModifier(ctx.namingModifiers, effect.attributetomodify, modType || effect.modifiertype, effect.value);
    }
    else ctx.unresolved.push({source:effect.source,attribute:effect.attributetomodify,reason:"modifier_value"});
  }
  ctx.cache.clear();
  ctx.statModifiers = collectStatModifiers(assembled,data,node => api.resolveValueNode(node,ctx));
  for (const modifier of ctx.statModifiers.modifiers) {
    api.addModifier(ctx.modifiers,modifier.attributetomodify,modifier.modifiertype,modifier.modifiervalue.constant);
    api.addModifier(ctx.namingModifiers,modifier.attributetomodify,modifier.modifiertype,modifier.modifiervalue.constant);
  }
  ctx.errors.push(...ctx.statModifiers.errors);
  for (const source of assembled.sources) {
    const price = source.definition.monetaryvaluemodifier;
    if (price?.attribute) ctx.priceModAttrs.push(price.attribute);
  }
  ctx.cache.clear();
  return ctx;
}

module.exports = {createNativeContext,className,propertyValue};
