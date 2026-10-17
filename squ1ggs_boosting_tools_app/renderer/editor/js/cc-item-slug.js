/**
 * cc-item-slug.js — Shared item slug + spawn prefix mapping for Legit Builder and Scooter's Toolbox Rebuild.
 * Single source of truth: keep in sync with bl4_manifest item slugs / NCS where possible.
 */
(function () {
  'use strict';
  if (window.__ccItemSlugV1) return;
  window.__ccItemSlugV1 = true;

  var SLUG_TO_PREFIX = {
    shield: 'GEN_SH',
    enhancement: 'GEN_EN',
    daedalus_pistol: 'DAD_PS', daedalus_shotgun: 'DAD_SG', daedalus_ar: 'DAD_AR', daedalus_smg: 'DAD_SM',
    jakobs_pistol: 'JAK_PS', jakobs_shotgun: 'JAK_SG', jakobs_ar: 'JAK_AR', jakobs_sniper: 'JAK_SR',
    tediore_pistol: 'TED_PS', tediore_shotgun: 'TED_SG', tediore_ar: 'TED_AR', tediore_shield: 'TED_SH',
    torgue_pistol: 'TOR_PS', torgue_shotgun: 'TOR_SG', torgue_ar: 'TOR_AR', torgue_heavy_weapon: 'TOR_HW',
    order_pistol: 'ORD_PS', order_ar: 'ORD_AR', order_sniper: 'ORD_SR',
    vladof_ar: 'VLA_AR', vladof_smg: 'VLA_SM', vladof_sniper: 'VLA_SR', vladof_heavy_weapon: 'VLA_HW',
    ripper_shotgun: 'BOR_SG', ripper_smg: 'BOR_SM', ripper_sniper: 'BOR_SR', ripper_heavy_weapon: 'BOR_HW',
    maliwan_shotgun: 'MAL_SG', maliwan_smg: 'MAL_SM', maliwan_sniper: 'MAL_SR', maliwan_heavy_weapon: 'MAL_HW',
    jakobs_shield: 'JAK_SH', vladof_shield: 'VLA_SH', daedalus_shield: 'DAD_SH', torgue_shield: 'TOR_SH',
    ripper_shield: 'BOR_SH', maliwan_shield: 'MAL_SH', order_shield: 'ORD_SH',
    maliwan_grenade_gadget: 'MAL_GR', jakobs_grenade_gadget: 'JAK_GR', daedalus_grenade_gadget: 'DAD_GR',
    ripper_grenade_gadget: 'BOR_GR', order_grenade_gadget: 'ORD_GR', torgue_grenade_gadget: 'TOR_GR',
    vladof_grenade_gadget: 'VLA_GR', tediore_grenade_gadget: 'TED_GR',
    atlas_enhancement: 'ATL_EN', hyperion_enhancement: 'HYP_EN', jakobs_enhancement: 'JAK_EN',
    maliwan_enhancement: 'MAL_EN', order_enhancement: 'ORD_EN', cov_enhancement: 'COV_EN',
    tediore_enhancement: 'TED_EN', torgue_enhancement: 'TOR_EN', daedalus_enhancement: 'DAD_EN',
    ripper_enhancement: 'BOR_EN', vladof_enhancement: 'VLA_EN',
    torgue_repair_kit: 'TOR_RK', jakobs_repair_kit: 'JAK_RK', maliwan_repair_kit: 'MAL_RK',
    vladof_repair_kit: 'VLA_RK', daedalus_repair_kit: 'DAD_RK', ripper_repair_kit: 'BOR_RK',
    order_repair_kit: 'ORD_RK', tediore_repair_kit: 'TED_RK',
    vladof_turret_gadget: 'VLA_TG', tediore_turret_gadget: 'TED_TG', torgue_turret_gadget: 'TOR_TG',
    order_turret_gadget: 'ORD_TG',
    terminal_gadget_barrier: 'TB', terminal_gadget_combat: 'TC', terminal_gadget_healing: 'TH',
    ripper_terminal_barrier: 'BOR_TB', daedalus_terminal_combat: 'DAD_TC', jakobs_terminal_combat: 'JAK_TC',
    maliwan_terminal_healing: 'MAL_TH', order_terminal_healing: 'ORD_TH', tediore_terminal_barrier: 'TED_TB',
    torgue_terminal_combat: 'TOR_TC', vladof_terminal_barrier: 'VLA_TB',
    turret_weapon_basic: 'TWB', turret_weapon_beam: 'TWB', turret_weapon_chaingun: 'TWC',
    turret_weapon_longrifle: 'TWL', turret_weapon_rocketlauncher: 'TWR', turret_weapon_shotgun: 'TWS',
    weapon_turret_chaingun: 'WTC',
    turret_gadget: 'TUR_GA', terminal_gadget: 'TER_GA',
    classmod_dark_siren: 'CM_DS', classmod_exo_soldier: 'CM_EX', classmod_gravitar: 'CM_GR', classmod_paladin: 'CM_PA',
    classmod_robodealer: 'CM_RD'
  };

  function buildSlugPrefix(slug) {
    if (!slug) return '';
    if (SLUG_TO_PREFIX[slug]) return SLUG_TO_PREFIX[slug];
    var map = { daedalus: 'DAD', jakobs: 'JAK', tediore: 'TED', torgue: 'TOR', order: 'ORD', vladof: 'VLA', ripper: 'BOR', maliwan: 'MAL', atlas: 'ATL', cov: 'COV', hyperion: 'HYP' };
    var types = { pistol: 'PS', shotgun: 'SG', ar: 'AR', smg: 'SM', sniper: 'SR', heavy_weapon: 'HW', shield: 'SH', grenade_gadget: 'GR', repair_kit: 'RK', enhancement: 'EN', turret_gadget: 'TG', terminal_barrier: 'TB', terminal_combat: 'TC', terminal_healing: 'TH' };
    var parts = String(slug).split('_');
    var mfr = parts[0] || '';
    var type = parts.slice(1).join('_');
    if (!type && types[mfr]) return types[mfr];
    var left = (map[mfr] || (mfr ? mfr.substring(0, 3).toUpperCase() : ''));
    var right = (types[type] || (type ? type.substring(0, 2).toUpperCase() : ''));
    var pref = left + '_' + right;
    return /^[A-Z0-9]{3}_[A-Z0-9]{2}$/.test(pref) ? pref : '';
  }

  function normMfrSlugToken(m) {
    var s = String(m || '').trim().toLowerCase();
    var map = {
      maliwan: 'maliwan', jakobs: 'jakobs', daedalus: 'daedalus', torgue: 'torgue',
      tediore: 'tediore', order: 'order', vladof: 'vladof', borg: 'ripper', ripper: 'ripper',
      atlas: 'atlas', cov: 'cov', hyperion: 'hyperion'
    };
    return map[s] || s.replace(/\s+/g, '_');
  }

  function weaponTypeToSlugSuffix(wt) {
    var w = String(wt || '').trim().toLowerCase();
    var map = {
      pistol: 'pistol', shotgun: 'shotgun', 'assault rifle': 'ar', smg: 'smg',
      'sniper rifle': 'sniper', sniper: 'sniper', 'heavy weapon': 'heavy_weapon', heavy: 'heavy_weapon'
    };
    return map[w] || '';
  }

  /**
   * @param {{ itemType?: string, manufacturer?: string, weaponType?: string }} st — Simple Builder state shape
   * @returns {string} Legit-style slug or ''
   */
  function computeSimpleBuilderItemSlug(st) {
    if (!st || typeof st !== 'object') return '';
    var catUi = st.itemType || '';
    var man = normMfrSlugToken(st.manufacturer);
    if (!man) return '';
    /* Heavy / legacy Gadget → manufacturer_heavy_weapon slug (not leftover AR/SMG weaponType). */
    if (catUi === 'Heavy' || catUi === 'Heavy Weapon' || catUi === 'Gadget') {
      var hm = { maliwan: 1, ripper: 1, torgue: 1, vladof: 1 };
      if (hm[man]) return man + '_heavy_weapon';
      return '';
    }
    var cat = catUi;

    if (cat === 'Weapon') {
      var wt = weaponTypeToSlugSuffix(st.weaponType);
      if (!wt) return '';
      if (wt === 'heavy_weapon') return '';
      return man + '_' + wt;
    }
    if (cat === 'Shield') return man + '_shield';
    if (cat === 'Grenade') return man + '_grenade_gadget';
    if (cat === 'Enhancement') return man + '_enhancement';
    if (cat === 'Repkit') return man + '_repair_kit';
    if (cat === 'Class Mod') {
      var ch = String(st.manufacturer || '').trim().toLowerCase().replace(/\s+/g, '_');
      var cm = {
        siren: 'classmod_dark_siren',
        paladin: 'classmod_paladin',
        exo_soldier: 'classmod_exo_soldier',
        gravitar: 'classmod_gravitar',
        robodealer: 'classmod_robodealer'
      };
      return cm[ch] || ('classmod_' + ch);
    }
    return '';
  }

  /** NCS slot name → Simple Builder `state.slots` key (stable across UI). */
  function ncsNameToStateKey(ns) {
    var map = {
      rarity: 'rarity',
      body: 'body', body_acc: 'bodyAcc', body_ele: 'bodyEle', body_bolt: 'bodyBolt', body_mag: 'bodyMag',
      barrel: 'barrel', barrel_acc: 'barrelAcc', barrel_licensed: 'licensed',
      hyperion_secondary_acc: 'hyperionSecondaryAcc',
      magazine: 'mag', magazine_acc: 'magazineAcc', magazine_ted_thrown: 'magazineTedThrown', magazine_borg: 'magazineBorg',
      scope: 'scope', scope_acc: 'scopeAcc', grip: 'grip', foregrip: 'foregrip',
      underbarrel: 'underbarrel', underbarrel_acc: 'underbarrelAcc', underbarrel_acc_vis: 'underbarrelAccVis',
      secondary_ele: 'secondaryEle', secondary_ammo: 'secondaryAmmo', primary_ele: 'primaryEle',
      tediore_acc: 'tedioreAcc', tediore_secondary_acc: 'tedioreSecondaryAcc',
      pearl_elem: 'pearlElem', pearl_stat: 'pearlStat', firmware: 'firmware', endgame: 'endgame'
    };
    return map[ns] || '';
  }

  /** STX `partType` filter string (or '' for pearl rows — filtered in Simple Builder). */
  function ncsNameToPartType(ns) {
    var m = {
      rarity: 'Rarity',
      body: 'Body', body_acc: 'Body Accessory', body_ele: 'Body Element', body_bolt: 'Body Accessory', body_mag: 'Manufacturer Part',
      barrel: 'Barrel', barrel_acc: 'Barrel Accessory', barrel_licensed: 'Manufacturer Part',
      hyperion_secondary_acc: 'Manufacturer Part',
      magazine: 'Magazine', magazine_acc: 'Magazine', magazine_ted_thrown: 'Magazine', magazine_borg: 'Magazine',
      scope: 'Scope', scope_acc: 'Scope Accessory', grip: 'Grip', foregrip: 'Foregrip', underbarrel: 'Underbarrel',
      underbarrel_acc: 'Underbarrel', underbarrel_acc_vis: 'Underbarrel',
      secondary_ele: 'Element Switch', secondary_ammo: 'Manufacturer Part', primary_ele: 'Element',
      tediore_acc: 'Manufacturer Part', tediore_secondary_acc: 'Manufacturer Part',
      pearl_elem: '', pearl_stat: '', firmware: 'Firmware', endgame: 'Stat Modifier'
    };
    return Object.prototype.hasOwnProperty.call(m, ns) ? m[ns] : 'Body';
  }

  /**
   * Ordered weapon slot schema for a Legit-style slug, matching `NCS_SLOT_MAP.items[slug].ncs_slots`
   * plus trailing stat / legendary / additional / firmware rows. Requires `legacy/ncs_slot_map.js` on the page.
   * @param {string} slug
   * @returns {Array<{key:string,label:string,partType:string,ncsSlot?:string,multi?:boolean,customType?:string}>|null}
   */
  function buildWeaponSlotSchemaFromNcs(slug) {
    var sm = typeof NCS_SLOT_MAP !== 'undefined' && NCS_SLOT_MAP && NCS_SLOT_MAP.items;
    if (!slug || !sm || !sm[slug] || !Array.isArray(sm[slug].ncs_slots)) return null;
    var labels = NCS_SLOT_MAP.slot_labels || {};
    var slots = sm[slug].ncs_slots;
    var hasNcs = {};
    var i;
    for (i = 0; i < slots.length; i++) hasNcs[String(slots[i] || '').trim().toLowerCase()] = true;
    var rows = [];
    var seenKey = {};
    for (i = 0; i < slots.length; i++) {
      /* NCS source sometimes uses "Body" — normalize so body slot is never dropped. */
      var ns = String(slots[i] || '').trim().toLowerCase();
      /* Fold NCS `body_bolt` into Body Accessory UI (same parts; dataset lists bolt under Body). */
      if (ns === 'body_bolt') continue;
      /* Thrown Tediore mags belong in the main Magazine dropdown (not a separate slot). */
      if (ns === 'magazine_ted_thrown') continue;
      /* Firmware always renders as the final weapon slot (after legendary + additional parts). */
      if (ns === 'firmware') {
        hasNcs.firmware = true;
        continue;
      }
      var key = ncsNameToStateKey(ns);
      if (!key || seenKey[key]) continue;
      seenKey[key] = true;
      var partType = ncsNameToPartType(ns);
      var row = {
        key: key,
        label: labels[ns] || String(ns).replace(/_/g, ' '),
        partType: partType,
        ncsSlot: ns
      };
      rows.push(row);
    }
    if (!hasNcs.barrel_licensed) {
      rows.push({ key: 'licensed', label: 'Licensed Manufacturer Part', partType: 'Manufacturer Part', ncsSlot: '' });
    }
    rows.push({ key: 'statMod', label: 'Stat Modifier', partType: 'Stat Modifier', ncsSlot: '' });
    rows.push({ key: 'legendary', label: 'Legendary Perks', partType: 'Legendary Perks', multi: true, ncsSlot: '' });
    rows.push({ key: 'firmware', label: (labels && labels.firmware) ? labels.firmware : 'Firmware', partType: 'Firmware', ncsSlot: hasNcs.firmware ? 'firmware' : '' });
    rows.push({ key: 'additionalParts', label: 'Additional (other parts)', partType: '', multi: true, customType: 'weaponAdditionalParts', ncsSlot: '' });
    return rows;
  }

  /**
   * Lowercased part code — belongs in NCS `magazine_acc` only.
   * Explicit accessory stems (`mag_acc` / `part_mag*_acc*`) only.
   * Torgue gyrojets (`part_mag_torgue_normal` / `_sticky`) live in the main Magazine
   * slot per BL4_MANIFEST (`mag`) — not Mag Acc.
   */
  function magazineAccessoryCodeMatchLo(codeLc) {
    var x = String(codeLc || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!x) return false;
    if (x.indexOf('mag_ted_thrown') !== -1) return false;
    // Torgue gyrojets (incl. *_normal) are main Magazine options in the legit manifest.
    if (/part_mag_torgue|mag_torgue|mag_normal/i.test(x)) return false;
    // Plain Borg specialty mags + borg barrel-mags belong in main Mag / magazine_borg — not Mag Acc.
    if (/part_mag_(?:05_)?borg/i.test(x)) return false;
    if (/mag_acc|magazine_acc/i.test(x)) return true;
    // Explicit accessory stem only (avoid matching "accuracy" substrings).
    if (/part_mag[^.\s]*_acc(?:_|$|\.)/.test(x) || /part_mag_acc/.test(x)) return true;
    return false;
  }

  /** Plain Borg specialty magazine (`magazine_borg` slot) — not barrel-acc variants. */
  function magazineBorgCodeMatchLo(codeLc) {
    var x = String(codeLc || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!x) return false;
    if (magazineAccessoryCodeMatchLo(x)) return false;
    return /part_mag_(?:05_)?borg(?!_barrel|_acc)|mag_05_borg|mag_.*_borg/.test(x);
  }

  /** Main magazine bodies (excludes accessories, borg specialty). Ted thrown stays here. */
  function magazineMainCodeMatchLo(codeLc) {
    var x = String(codeLc || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!x || x.indexOf('part_mag') === -1) return false;
    if (magazineAccessoryCodeMatchLo(x)) return false;
    if (magazineBorgCodeMatchLo(x)) return false;
    return true;
  }

  /**
   * Lowercased spawn code — belongs in NCS `barrel_acc` only.
   * Letter accessories: `part_barrel_01_a` … `_d`, mix tags like `part_barrel_02_dXa` / `_aXD`.
   * Not main barrels (`part_barrel_01`), not legendary named barrels (`part_barrel_02_lumberjack`).
   */
  function barrelAccessoryCodeMatchLo(codeLc) {
    var x = String(codeLc || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!x || x.indexOf('part_barrel') === -1) return false;
    if (/barrel_licensed|part_barrel_unique/.test(x)) return false;
    if (/barrel_acc|part_barrel_acc/.test(x)) return true;
    var m = x.match(/part_barrel_(\d+)_(.+)$/);
    if (!m) return false;
    var suf = String(m[2] || '');
    // Single letter accessory (a–d).
    if (/^[a-d]$/.test(suf)) return true;
    // Heavy mix accessories: aXD / dXa / axd…
    if (/^[a-d]x[a-z0-9]*$/i.test(suf)) return true;
    return false;
  }

  /** Main barrel slot codes (excludes letter accessories + licensed). */
  function barrelMainCodeMatchLo(codeLc) {
    var x = String(codeLc || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!x || x.indexOf('part_barrel') === -1) return false;
    if (/barrel_licensed/.test(x)) return false;
    if (barrelAccessoryCodeMatchLo(x)) return false;
    return true;
  }

  /** Scope accessories: `part_scope_acc_*` (or partType Scope Accessory). */
  function scopeAccessoryCodeMatchLo(codeLc) {
    var x = String(codeLc || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!x || x.indexOf('part_scope') === -1) return false;
    if (/part_scope_acc|scope_acc/.test(x)) return true;
    if (/part_scope[^.\s]*_acc(?:_|$|\.)/.test(x)) return true;
    return false;
  }

  function scopeMainCodeMatchLo(codeLc) {
    var x = String(codeLc || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!x || x.indexOf('part_scope') === -1) return false;
    if (scopeAccessoryCodeMatchLo(x)) return false;
    return true;
  }

  /** Underbarrel accessories: `*_acc` / `*_acc_vis` (same dataset partType as main underbarrel). */
  function underbarrelAccessoryCodeMatchLo(codeLc, visOnly) {
    var x = String(codeLc || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!x || x.indexOf('underbarrel') === -1) return false;
    /* NCS puts both VLA AR dual-damage companion rows in underbarrel_acc_vis. */
    var isVisual = /underbarrel.*acc_vis/.test(x) || /^vla_ar\.part_underbarrel_07_b$/.test(x);
    if (visOnly) return isVisual;
    if (isVisual) return false;
    return /underbarrel.*_acc(?:_|$|\.)|underbarrel_.*acc/.test(x);
  }

  function underbarrelMainCodeMatchLo(codeLc) {
    var x = String(codeLc || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!x || x.indexOf('underbarrel') === -1) return false;
    if (underbarrelAccessoryCodeMatchLo(x, false) || underbarrelAccessoryCodeMatchLo(x, true)) return false;
    return true;
  }

  /**
   * Unified weapon-slot membership (Guided + Simple).
   * @param {string} slotKey  Guided/Simple state key (`mag`, `magazineAcc`, `barrel`, …)
   * @param {object} p        part row
   * @returns {boolean}
   */
  function stxWeaponSlotPartMatch(slotKey, p) {
    if (!p || !slotKey) return false;
    var key = String(slotKey);
    var x = String((p.code != null ? p.code : (p.spawnCode || '')) || '').toLowerCase().replace(/^["']|["']$/g, '');
    var pt = String(p.partType || '').trim().toLowerCase();
    switch (key) {
      case 'mag':
      case 'magazine':
        // Main magazine bodies (incl. Torgue gyrojets). Don't require partType === Magazine —
        // dataset often tags torgue mags as "Manufacturer Part".
        if (magazineAccessoryCodeMatchLo(x) || magazineBorgCodeMatchLo(x)) return false;
        if (magazineMainCodeMatchLo(x)) return true;
        return pt === 'magazine';
      case 'magazineAcc':
      case 'magazine_acc':
        if (magazineAccessoryCodeMatchLo(x)) return true;
        return pt === 'magazine accessory';
      case 'magazineBorg':
      case 'magazine_borg':
        return magazineBorgCodeMatchLo(x);
      case 'barrel':
        if (pt === 'barrel accessory') return false;
        if (barrelAccessoryCodeMatchLo(x)) return false;
        return pt === 'barrel' || barrelMainCodeMatchLo(x);
      case 'barrelAcc':
      case 'barrel_acc':
        if (pt === 'barrel accessory') return true;
        return barrelAccessoryCodeMatchLo(x);
      case 'scope':
        if (pt === 'scope accessory') return false;
        if (scopeAccessoryCodeMatchLo(x)) return false;
        return pt === 'scope' || scopeMainCodeMatchLo(x);
      case 'scopeAcc':
      case 'scope_acc':
        if (pt === 'scope accessory') return true;
        return scopeAccessoryCodeMatchLo(x);
      case 'underbarrel':
        if (underbarrelAccessoryCodeMatchLo(x, false) || underbarrelAccessoryCodeMatchLo(x, true)) return false;
        return pt === 'underbarrel' || underbarrelMainCodeMatchLo(x);
      case 'underbarrelAcc':
      case 'underbarrel_acc':
        return underbarrelAccessoryCodeMatchLo(x, false);
      case 'underbarrelAccVis':
      case 'underbarrel_acc_vis':
        return underbarrelAccessoryCodeMatchLo(x, true);
      default:
        return true;
    }
  }

  window.SLUG_TO_PREFIX = SLUG_TO_PREFIX;
  window.buildSlugPrefix = buildSlugPrefix;
  window.computeSimpleBuilderItemSlug = computeSimpleBuilderItemSlug;
  window.ncsNameToStateKey = ncsNameToStateKey;
  window.buildWeaponSlotSchemaFromNcs = buildWeaponSlotSchemaFromNcs;
  window.magazineAccessoryCodeMatchLo = magazineAccessoryCodeMatchLo;
  window.magazineBorgCodeMatchLo = magazineBorgCodeMatchLo;
  window.magazineMainCodeMatchLo = magazineMainCodeMatchLo;
  window.barrelAccessoryCodeMatchLo = barrelAccessoryCodeMatchLo;
  window.barrelMainCodeMatchLo = barrelMainCodeMatchLo;
  window.scopeAccessoryCodeMatchLo = scopeAccessoryCodeMatchLo;
  window.scopeMainCodeMatchLo = scopeMainCodeMatchLo;
  window.underbarrelAccessoryCodeMatchLo = underbarrelAccessoryCodeMatchLo;
  window.underbarrelMainCodeMatchLo = underbarrelMainCodeMatchLo;
  window.stxWeaponSlotPartMatch = stxWeaponSlotPartMatch;
})();
