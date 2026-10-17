(() => {
  'use strict';

  const $ = (id)=>document.getElementById((id==='itemType')?'stx_itemType':(id==='manufacturer')?'stx_manufacturer':id);

  /** Collapse legacy **Heavy Weapon** / **Gadget** labels into one Simple item type: **Heavy**. */
  function stxNormalizeSimpleBuilderItemTypeUi(v){
    const s = String(v || '').trim();
    if (s === 'Heavy Weapon' || s === 'Gadget') return 'Heavy';
    return s;
  }
  /** Heavy guns: item type **Heavy** / **Heavy Weapon** / legacy **Gadget** only. */
  function stxSimpleBuilderItemTypeIsHeavyUi(catUi, wtOverride){
    const raw = String(catUi || '').trim();
    if (/^(Heavy Weapon|Heavy|Gadget)$/i.test(raw)) return true;
    return stxNormalizeSimpleBuilderItemTypeUi(raw) === 'Heavy';
  }

  function stxWeaponTypeIsHeavyLabel(wt){
    const w = String(wt || '').trim();
    return /^heavy(?:\s*weapon)?$/i.test(w) || /heavy\s*weapon/i.test(w);
  }

  function stxStripLegendaryRarityDisplayPrefix(s){
    const t = String(s || '').trim();
    if (!t) return '';
    const m = t.match(/^legendary\s*[-–—]\s*(.+)$/i);
    if (m) return m[1].trim();
    if (/^legendary$/i.test(t)) return '';
    return t;
  }

  /** Dataset often names rarity comps "Doeshot Skin" / "Ballista Skin" — drop the cosmetic "Skin" suffix in UI. */
  function stxStripRarityIdSkinDisplaySuffix(s){
    const t = String(s || '').trim();
    if (!t) return '';
    return t.replace(/\s+skins?\s*$/i, '').trim() || t;
  }
  try { window.stxStripRarityIdSkinDisplaySuffix = stxStripRarityIdSkinDisplaySuffix; } catch (_e) {}

  function stxNormalizeNewItemCodeKey(raw){
    return String(raw || '')
      .toLowerCase()
      .replace(/["']/g, '')
      .replace(/^inv['"]?/i, '')
      .trim();
  }

  function stxCollectNewItemCodeCandidates(partOrCode){
    const out = [];
    const push = (v)=>{
      const n = stxNormalizeNewItemCodeKey(v);
      if (n) out.push(n);
    };
    if (partOrCode == null) return out;
    if (typeof partOrCode === 'string' || typeof partOrCode === 'number') {
      push(partOrCode);
      return out;
    }
    if (typeof partOrCode !== 'object') return out;
    push(partOrCode.code);
    push(partOrCode.spawnCode);
    push(partOrCode.importCode);
    push(partOrCode.itemTypeString);
    push(partOrCode.matchCode);
    push(partOrCode.value);
    try {
      if (typeof normCode === 'function') {
        push(normCode(partOrCode.code || partOrCode.spawnCode || partOrCode.importCode || ''));
      }
    } catch (_e) {}
    return out;
  }

  function stxIsNewEditorItem(partOrCode){
    const set = (typeof window !== 'undefined') ? window.STX_NEW_EDITOR_ITEM_CODES : null;
    if (!set || typeof set.has !== 'function') return false;
    const cands = stxCollectNewItemCodeCandidates(partOrCode);
    for (let i = 0; i < cands.length; i++){
      if (set.has(cands[i])) return true;
    }
    return false;
  }

  function stxMarkNewDropdownLabel(label, partOrCode){
    const L = String(label == null ? '' : label);
    if (!L || !stxIsNewEditorItem(partOrCode)) return L;
    if (/^🆕/.test(L) || L.indexOf('🆕') !== -1) return L;
    return `🆕 ${L}`;
  }

  try {
    window.stxIsNewEditorItem = stxIsNewEditorItem;
    window.stxMarkNewDropdownLabel = stxMarkNewDropdownLabel;
  } catch (_e) {}

  
  // Bridge parent datasets into this srcdoc iframe (host page keeps canonical copies).
  try{
    if (!window.STX_DATASET && window.parent && window.parent.STX_DATASET) window.STX_DATASET = window.parent.STX_DATASET;
    if (!window.STX_RARITIES && window.parent && window.parent.STX_RARITIES) window.STX_RARITIES = window.parent.STX_RARITIES;
  }catch(_e){}

  const state = {
    __seedEnabled: false,
    itemType: '',
    manufacturer: '',
    weaponType: '',
    level: 70,
    rarity: '',
    idMode: true,
    allParts: false,
    swapBodyLegendary: false,
    forceTypeIdTokens: false,

    detectedCategory: null,
    mainPart: null, // part object
    // slot selections: key -> part object
    slots: {},
    // elements
    primaryElement: '',
    elementStack: [],
    /** Maliwan dual element switch: insert `Weapon.part_secondary_elem_*_*_mal` before preset element tokens when needed. */
    dualElementUseMaliwanSwitch: false,
    // extras from import
    extras: []
  };

  const byId = (id) => document.getElementById(id);

  /** True when Simple or Guided “Pearl override” is on — drives DLC pearl pip icons in dropdowns. */
  function stxIsPearlOverrideUiActive(){
    try{
      const a = document.getElementById('stxPearlOverride');
      const b = document.getElementById('ccGuidedPearlOverride');
      return !!((a && a.checked) || (b && b.checked));
    }catch(_e){ return false; }
  }

  /** Swap gold legendary augment icons for matching `dlc_rarity_pips` pearl pips when override is active. */
  function stxPearlPipUrlInsteadOfLegendaryAug(u){
    const s = String(u || '').trim();
    // Safety: do not rewrite icon URLs to DLC pearl pips unless your build actually ships those assets.
    // Pearl override still affects *code output* elsewhere; this is icon-only.
    return s;
  }

  try{
    // Keep STX/simple state isolated; do not clobber an existing main-page `window.state`.
    window.__STX_SIMPLE_STATE = state;
    window.__BL4_EDITOR_STATE = state;
    if (!window.state || window.state === window.__STX_SIMPLE_STATE || window.state === window.__BL4_EDITOR_STATE){
      window.state = state;
    }
  }catch(_e){}

  const ELEMENTS = [
    {key:'None', label:'No Element', code:''},
    {key:'Corrosive', label:'Corrosive', code:'{1:10}'},
    {key:'Cryo', label:'Cryo', code:'{1:11}'},
    {key:'Fire', label:'Fire', code:'{1:12}'},
    {key:'Radiation', label:'Radiation', code:'{1:13}'},
    {key:'Shock', label:'Shock', code:'{1:14}'}
  ];

  /** Repkit element pool uses family 243 (`repair_kit.part_element_*`), not weapon TypeID `{1:n}` — weapon tokens break spawns. */
  const REPKIT_ELEMENT_SYNTH = [
    { key:'Corrosive', label:'Corrosive', idRaw:'243:100', id:100, spawnCode:'repair_kit.part_element_corrosive' },
    { key:'Cryo', label:'Cryo', idRaw:'243:102', id:102, spawnCode:'repair_kit.part_element_cryo' },
    { key:'Fire', label:'Fire', idRaw:'243:98', id:98, spawnCode:'repair_kit.part_element_fire' },
    { key:'Radiation', label:'Radiation', idRaw:'243:99', id:99, spawnCode:'repair_kit.part_element_radiation' },
    { key:'Shock', label:'Shock', idRaw:'243:101', id:101, spawnCode:'repair_kit.part_element_shock' }
  ];

  function stxMaliwanElementKeyToSlug(key){
    const k = String(key || '').trim();
    const map = { Corrosive:'corrosive', Cryo:'cryo', Fire:'fire', Radiation:'radiation', Shock:'shock' };
    return map[k] || '';
  }

  function stxFindMaliwanDualSwitchPart(primaryKey, stackKey){
    const a = stxMaliwanElementKeyToSlug(primaryKey);
    const b = stxMaliwanElementKeyToSlug(stackKey);
    if (!a || !b) return null;
    const needles = [
      ('part_secondary_elem_' + a + '_' + b + '_mal').toLowerCase(),
      ('part_secondary_elem_' + b + '_' + a + '_mal').toLowerCase()
    ];
    try{
      const all = getAllParts();
      for (let n = 0; n < needles.length; n++){
        const needle = needles[n];
        for (let i = 0; i < all.length; i++){
          const p = all[i];
          if (!p) continue;
          const c = String(normCode(p.code || '') || '').toLowerCase();
          if (c.includes(needle)) return p;
        }
      }
    }catch(_e){}
    return {
      category: 'Weapon',
      manufacturer: 'Maliwan',
      partType: 'Element Switch',
      name: `Dual element switch (${primaryKey} / ${stackKey})`,
      code: '"Weapon.part_secondary_elem_' + a + '_' + b + '_mal"'
    };
  }

  /** Distinct preset element keys (primary + stack) for dual-element Maliwan switch detection. */
  function stxDistinctElementKeysForDualSwitch(){
    const out = new Set();
    const prim = state.primaryElement || 'None';
    if (prim && prim !== 'None') out.add(prim);
    const stack = Array.isArray(state.elementStack) ? state.elementStack : [];
    for (const e of stack){
      if (e && e !== 'None') out.add(e);
    }
    return out;
  }

  /** When two different elements are selected, auto-enable the Maliwan dual-element switch part. */
  function stxSyncDualElementMaliwanSwitch(){
    const distinct = stxDistinctElementKeysForDualSwitch();
    if (distinct.size < 2){
      state.dualElementUseMaliwanSwitch = false;
      if (state.slots && state.slots.secondaryEle && state.slots.secondaryEle.__autoDualElement){
        delete state.slots.secondaryEle;
      }
      return;
    }
    const keys = Array.from(distinct);
    const sw = stxFindMaliwanDualSwitchPart(keys[0], keys[1]);
    if (!sw) return;
    state.dualElementUseMaliwanSwitch = true;
    if (!state.slots) state.slots = {};
    state.slots.secondaryEle = Object.assign({}, sw, { __autoDualElement: true });
  }

  /** Legendary-perk pools scoped to the weapon class being built (not manufacturer). */
  function stxPartMatchesLegendaryPoolWeaponType(p, weaponType){
    const wt = String(weaponType || '').trim();
    if (!wt) return true;
    const wtN = wt.toLowerCase();
    const pwt = String((p && (p.weaponType || p.itemType)) || '').trim().toLowerCase();
    if (!pwt || pwt === 'weapon' || pwt === 'prefix' || pwt === 'rarity' || pwt === 'gadget' || pwt === 'enhancement') return true;
    if (pwt === wtN) return true;
    if ((pwt === 'sniper' && wtN === 'sniper rifle') || (pwt === 'sniper rifle' && wtN === 'sniper')) return true;
    if ((pwt === 'smg' && wtN === 'submachine gun') || (pwt === 'submachine gun' && wtN === 'smg')) return true;
    if ((wtN === 'heavy weapon' || wtN === 'heavy') && (pwt.indexOf('heavy') >= 0)) return true;
    const code = String(normCode(p && p.code || '') || '').toLowerCase();
    if ((wtN === 'heavy weapon' || wtN === 'heavy') && (/_hw[._]|heavy_weapon_gadget/i.test(code))) return true;
    const spawnWtMap = {
      'assault rifle': /[._]ar[._]/,
      'shotgun': /[._]sg[._]/,
      'smg': /[._]sm[._]/,
      'pistol': /[._]ps[._]/,
      'sniper rifle': /[._]sr[._]/,
      'sniper': /[._]sr[._]/
    };
    const re = spawnWtMap[wtN];
    if (re && re.test(code)) return true;
    return false;
  }

  /** One stable key per logical part for dropdown dedupe (handles `105` vs `243:105`, duplicate dataset rows). */
  function stxStableDropdownDedupeKey(p){
    if (!p) return '';
    let ir = String((p.idRaw != null ? p.idRaw : (p.idraw != null ? p.idraw : ''))).trim().replace(/^"+|"+$/g, '');
    const mFull = ir.match(/^(\d+)\s*:\s*(\d+)$/);
    if (mFull){
      return 'fid:' + Number(mFull[1]) + ':' + Number(mFull[2]);
    }
    const fam = Number(p.family != null ? p.family : p.familyId);
    const idn = Number(p.id != null ? p.id : p.itemId);
    if (Number.isFinite(fam) && Number.isFinite(idn)){
      return 'fid:' + fam + ':' + idn;
    }
    if (/^\d+$/.test(ir)){
      const idOnly = Number(ir);
      if (Number.isFinite(fam) && Number.isFinite(idOnly)) return 'fid:' + fam + ':' + idOnly;
      const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
      if (c.indexOf('repair_kit.') === 0 && Number.isFinite(idOnly)) return 'fid:243:' + idOnly;
      if (/heavy_weapon_gadget\./.test(c) && Number.isFinite(idOnly)) return 'fid:244:' + idOnly;
      const enhFam = stxEnhancementTypeFamilyIdFromSpawnCode(c);
      if (enhFam != null && Number.isFinite(idOnly)) return 'fid:' + enhFam + ':' + idOnly;
    }
    return 'code:' + normCode(p.code || '');
  }

  function stxPartDropdownRichnessScore(p){
    if (!p || typeof p !== 'object') return 0;
    let s = 0;
    const ir = String(p.idRaw ?? p.idraw ?? '').trim();
    if (/^\d+\s*:\s*\d+$/.test(ir)) s += 8;
    else if (ir) s += 2;
    if (Number.isFinite(partFamilyIdOf(p)) && Number.isFinite(partItemIdOf(p))) s += 4;
    if (String(p.name || '').trim()) s += 1;
    if (String(normCode(p.code || '') || '').trim()) s += 1;
    return s;
  }

  /**
   * Collapse duplicate dataset rows in dropdowns: same `fid:family:item`, same numeric token, or same spawn code,
   * even when each row has a different `idx:N` option value or idRaw omits the family.
   */
  function stxSelectLogicalDedupeKey(o){
    if (!o || typeof o !== 'object') return '';
    const kNum = stxNumericTokenDedupeKey(o);
    if (kNum && kNum.indexOf('fid:') === 0) return kNum;
    const k = stxStableDropdownDedupeKey(o);
    if (k && k.indexOf('fid:') === 0) return k;
    if (kNum && kNum.indexOf('bareid:') === 0) return kNum;
    if (k && k.length > 5 && k.indexOf('code:') === 0 && k !== 'code:') return k;
    return '';
  }

  function stxPresetElementDropdownLabel(e){
    if (!e) return '-';
    const label = e.label != null ? String(e.label) : String(e.key || '');
    const code = e.code != null ? String(e.code).trim() : '';
    if (!code) return label;
    return label + ' (' + code + ')';
  }

  const CLASSMOD_ELEMENT_OVERRIDES = [
    {key:'Kinetic Override', label:'Kinetic Override', code:'{1:55}'},
    {key:'Shock Override', label:'Shock Override', code:'{1:56}'},
    {key:'Radiation Override', label:'Radiation Override', code:'{1:57}'},
    {key:'Corrosive Override', label:'Corrosive Override', code:'{1:58}'},
    {key:'Cryo Override', label:'Cryo Override', code:'{1:59}'},
    {key:'Incendiary Override', label:'Incendiary Override', code:'{1:60}'}
  ];

  const PEARL_FALLBACK_ROWS = [
    {itemId:51, itemTypeString:'pearl_damage', legendaryName:'Pearlescent - Damage'},
    {itemId:52, itemTypeString:'pearl_reload', legendaryName:'Pearlescent - Reload'},
    {itemId:53, itemTypeString:'pearl_firerate', legendaryName:'Pearlescent - Fire Rate'},
    {itemId:54, itemTypeString:'pearl_handling', legendaryName:'Pearlescent - Handling'},
    {itemId:55, itemTypeString:'pearl_normal', legendaryName:'Pearlescent - Kinetic Override'},
    {itemId:56, itemTypeString:'pearl_shock', legendaryName:'Pearlescent - Shock Override'},
    {itemId:57, itemTypeString:'pearl_radiation', legendaryName:'Pearlescent - Radiation Override'},
    {itemId:58, itemTypeString:'pearl_corrosive', legendaryName:'Pearlescent - Corrosive Override'},
    {itemId:59, itemTypeString:'pearl_cryo', legendaryName:'Pearlescent - Cryo Override'},
    {itemId:60, itemTypeString:'pearl_fire', legendaryName:'Pearlescent - Incendiary Override'}
  ];
  // Known pearlescent weapon-item barrel entries from the 2026-02-27 update list.
  const PEARL_WEAPON_MAINPART_ID_SET = new Set([
    '11:81','11:82','14:78','13:82','18:99','23:22','6:77','6:78','4:84','12:78','25:81','25:82','21:80','9:100','16:69','2:80','7:54','17:82','22:91','3:82','7:55'
  ]);
  const PEARL_WEAPON_MAINPART_HINTS = [
    'eigenburst','laserdisc','mercredi','bubbles','tankbuster','handcannon','roulette',
    'arctic','conflux','songbird','doeshot','fleabag','mercury','mercurious','shalashaska','demo',
    'crowsourced','soulsurvivor','crazedearl','jailbroken','jailbrokengatling',
    'hairtrigger','herald','gomie','abyss','loomingconstable','looming','constable',
    'firestorm','firework','screwstonian','screwed','parasite','solartemper'
  ];

  const CORE_PARTTYPE_BY_CATEGORY = {
    Weapon: 'Rarity',
    Shield: 'Rarity',
    // Main / prefix row is the rarity-id slot (like Shield). Manufacturer bases use the Base slot.
    Repkit: 'Rarity',
    // Grenades use the inv_comp rarity component as the core prefix row.
    Grenade: 'Rarity',
    /* Same heavy / turret pools as `Weapon` + Heavy (`*_HW.comp_*`); not grenade `Base` rows. */
    Gadget: 'Rarity',
    Enhancement: 'Rarity',
    Character: 'Body',
    'Class Mod': 'Body',
    Other: 'Base'
  };

  /** Preset full-item serials for AI / vehicle / turret-style gear (same pool as advanced search "AI Car Guns"). */
  const STX_SIMPLE_AICAR_DEFAULTS = [
    { name: 'GIANT ROOCKET LAUNCHER', code: '383, 0, 1, 50| 2, 420|| {287:7} {2}|' },
    { name: 'Maliwan Car part', code: '390, 0, 1, 50| 2, 420|| {287:7} {2}|' },
    { name: 'Minigun', code: '239, 0, 1, 50| 2, 3765|| {273:34}|' },
    { name: 'RPG', code: '240, 0, 1, 50| 2, 3765|| {8:1}|' },
    { name: 'Flamethrower', code: '391, 0, 1, 50| 2, 420|| {287:7} {2}|' }
  ];

  function getAicarSimpleBuilderParts(){
    const src = (Array.isArray(window.AI_CAR_GUNS) && window.AI_CAR_GUNS.length)
      ? window.AI_CAR_GUNS
      : STX_SIMPLE_AICAR_DEFAULTS;
    const out = [];
    for (let i = 0; i < src.length; i++){
      const g = src[i];
      const full = String((g && g.code) || '').replace(/^"+|"+$/g, '').trim();
      if (!full) continue;
      const name = String((g && g.name) || '').trim() || `Preset ${i + 1}`;
      out.push({
        name,
        __fullDeserialized: full,
        code: `"${full}"`,
        category: 'Other',
        itemType: 'Other',
        manufacturer: 'AI Car Guns',
        partType: 'AI Car Guns',
        weaponType: '',
        idRaw: '',
        id: null,
        __isAicarFullItem: true
      });
    }
    return out;
  }

  /** Fallback when slug missing from `NCS_SLOT_MAP` (e.g. offline). */
  const WEAPON_SLOT_SCHEMA = [
    {key:'body', label:'Body', partType:'Body'},
    {key:'bodyEle', label:'Body Element', partType:'Body Element', ncsSlot:'body_ele'},
    {key:'bodyAcc', label:'Body Accessory', partType:'Body Accessory'},
    {key:'barrel', label:'Barrel', partType:'Barrel'},
    {key:'barrelAcc', label:'Barrel Accessory', partType:'Barrel Accessory'},
    {key:'mag', label:'Magazine', partType:'Magazine', ncsSlot:'magazine'},
    {key:'magazineAcc', label:'Magazine Accessory', partType:'Magazine', ncsSlot:'magazine_acc'},
    {key:'magazineBorg', label:'Borg Magazine', partType:'Magazine', ncsSlot:'magazine_borg'},
    {key:'pearlElem', label:'Pearl Element', partType:'', ncsSlot:'pearl_elem'},
    {key:'pearlStat', label:'Pearl Stat', partType:'', ncsSlot:'pearl_stat'},
    {key:'scope', label:'Scope', partType:'Scope'},
    {key:'scopeAcc', label:'Scope Accessory', partType:'Scope Accessory', ncsSlot:'scope_acc'},
    {key:'grip', label:'Grip', partType:'Grip'},
    {key:'foregrip', label:'Foregrip', partType:'Foregrip'},
    {key:'underbarrel', label:'Underbarrel', partType:'Underbarrel'},
    {key:'underbarrelAcc', label:'Underbarrel Accessory', partType:'Underbarrel', ncsSlot:'underbarrel_acc'},
    {key:'licensed', label:'Licensed Manufacturer Part', partType:'Manufacturer Part'},
    {key:'secondaryAmmo', label:'Secondary Ammo Type', partType:'Manufacturer Part', ncsSlot:'secondary_ammo'},
    {key:'hyperionSecondaryAcc', label:'Hyperion Amp Shield', partType:'Manufacturer Part', ncsSlot:'hyperion_secondary_acc'},
    {key:'statMod', label:'Stat Modifier', partType:'Stat Modifier'},
    {key:'secondaryEle', label:'Secondary Element (Maliwan Switch)', partType:'Element Switch', ncsSlot:'secondary_ele'},
    {key:'legendary', label:'Legendary Perks', partType:'Legendary Perks', multi:true},
    {key:'additionalParts', label:'Additional (other parts)', partType:'', multi:true, customType:'weaponAdditionalParts'},
    {key:'firmware', label:'Firmware', partType:'Firmware'},
  ];

  /** Inject body/barrel when NCS omits them (e.g. legacy \"Body\" casing) — Body must precede Body Accessory. */
  function ensureSimpleWeaponCoreSlots(schema){
    let out = Array.isArray(schema) ? schema.slice() : [];
    if (!out.length) return out;
    /*
     * Heavy uses the weapon schema internally, but the dataset contains no
     * Heavy/HW underbarrel rows. Hide those empty controls instead of leaking
     * unrelated AR/SMG parts into Heavy.
     */
    if (stxSimpleBuilderItemTypeIsHeavyUi(state && state.itemType, state && state.weaponType)) {
      out = out.filter(s => !stxWeaponSlotIsUnderbarrelFamily(s && s.key));
    }
    const seen = Object.create(null);
    for (let i = 0; i < out.length; i++) {
      const k = String(out[i] && out[i].key || '');
      if (k) seen[k] = true;
    }
    if (!seen.body) {
      const bodyRow = { key: 'body', label: 'Body', partType: 'Body', ncsSlot: 'body' };
      let at = 0;
      for (let j = 0; j < out.length; j++) {
        const k = String(out[j] && out[j].key || '');
        if (k === 'bodyAcc' || k === 'bodyEle' || k === 'bodyMag') { at = j; break; }
      }
      out.splice(at, 0, bodyRow);
      seen.body = true;
    }
    if (!seen.barrel) {
      const barrelRow = { key: 'barrel', label: 'Barrel', partType: 'Barrel', ncsSlot: 'barrel' };
      let at = out.length;
      for (let j = 0; j < out.length; j++) {
        const k = String(out[j] && out[j].key || '');
        if (k === 'bodyAcc' || k === 'bodyEle' || k === 'bodyMag' || k === 'barrelAcc') at = j + 1;
        if (k === 'mag' || k === 'magazine') { at = j; break; }
      }
      out.splice(at, 0, barrelRow);
      seen.barrel = true;
    }
    if (!stxSimpleBuilderItemTypeIsHeavyUi(state && state.itemType, state && state.weaponType) && !seen.underbarrel) {
      const ubRow = { key: 'underbarrel', label: 'Underbarrel', partType: 'Underbarrel', ncsSlot: 'underbarrel' };
      let at = out.length;
      for (let j = 0; j < out.length; j++) {
        const k = String(out[j] && out[j].key || '');
        if (k === 'scope' || k === 'scopeAcc' || k === 'grip' || k === 'stock') at = j + 1;
      }
      out.splice(at, 0, ubRow);
      seen.underbarrel = true;
    }
    if (!seen.magazineAcc) {
      const magAccRow = { key: 'magazineAcc', label: 'Magazine Accessory', partType: 'Magazine', ncsSlot: 'magazine_acc' };
      let at = out.length;
      for (let j = 0; j < out.length; j++) {
        const k = String(out[j] && out[j].key || '');
        if (k === 'mag' || k === 'magazine' || k === 'magazineBorg') at = j + 1;
      }
      out.splice(at, 0, magAccRow);
      seen.magazineAcc = true;
    }
    /*
     * Accessory and visual-accessory rows are not universal weapon slots. Keep
     * them only when the active NCS schema declares them (or when the fallback
     * WEAPON_SLOT_SCHEMA is in use); otherwise an unrelated gun gets an empty
     * control with no valid serialized position.
     */
    return out;
  }

  function getActiveWeaponSlotSchema(){
    try{
      const slug = typeof window.computeSimpleBuilderItemSlug === 'function' ? window.computeSimpleBuilderItemSlug(state) : '';
      const built = typeof window.buildWeaponSlotSchemaFromNcs === 'function' ? window.buildWeaponSlotSchemaFromNcs(slug) : null;
      if (built && built.length){
        return ensureSimpleWeaponCoreSlots(filterSimpleWeaponSchemaSlots(built));
      }
    }catch(_e){}
    return ensureSimpleWeaponCoreSlots(filterSimpleWeaponSchemaSlots(WEAPON_SLOT_SCHEMA));
  }

  /** Core gun identity — users must pick these. */
  function stxWeaponSlotIsCoreRequired(slotKey){
    const k = String(slotKey || '');
    return k === 'body' || k === 'barrel';
  }

  function stxWeaponSlotIsUnderbarrelFamily(slotKey){
    const k = String(slotKey || '');
    return k === 'underbarrel' || k === 'underbarrelAcc' || k === 'underbarrelAccVis';
  }

  const STX_UNDERBARREL_SLOT_HINT = 'Usually Vladof ARs, SMGs, and snipers in legit data. Other guns rarely show a pool here — use Additional parts for modded underbarrels.';
  const STX_UNDERBARREL_VISUAL_HINT = 'Cosmetic companion part used by a small number of underbarrels. It does not add a separate gameplay stat.';

  /**
   * Hide empty optional / specialty slots (Body Mag, Borg Mag, Mag Acc, pearl, etc.) so the UI
   * only shows pools that exist for this manufacturer + weapon type.
   * Always keep Body / Barrel / Magazine and the main Underbarrel control visible.
   * Accessory/visual underbarrel controls only help when their filtered pool exists.
   */
  function stxWeaponSlotHideWhenEmpty(slotKey){
    const k = String(slotKey || '');
    if (k === 'body' || k === 'barrel' || k === 'mag' || k === 'magazine') return false;
    if (k === 'underbarrel') return false;
    return true;
  }

  function stxSimpleSlotPlaceholder(schemaItem, useQtyAddSlot){
    if (useQtyAddSlot) return 'Select a part to add...';
    if (schemaItem && schemaItem.multi) return '(add one or more...)';
    if (stxWeaponSlotIsCoreRequired(schemaItem && schemaItem.key)) return '-- Required — pick one --';
    return '(optional)';
  }

  /**
   * Simple Builder already picks rarity via left-panel #mainPart ("Rarity ID Part").
   * NCS maps still list a leading `rarity` slot — drop it so Body is first in the grid.
   * Guided Builder keeps its own rarity dropdown and is unaffected.
   */
  function filterSimpleWeaponSchemaSlots(schema){
    const isHeavy = stxSimpleBuilderItemTypeIsHeavyUi(state.itemType);
    return (schema || []).filter(s => {
      if (!s) return false;
      const k = String(s.key || '');
      const ns = String(s.ncsSlot || '');
      const pt = String(s.partType || '').trim().toLowerCase();
      if (k === 'rarity' || ns === 'rarity' || pt === 'rarity') return false;
      if (isHeavy && (k === 'secondaryEle' || ns === 'secondary_ele')) return false;
      return true;
    });
  }

  function weaponPearlElemPartMatch(p){
    if (!p) return false;
    const codeNorm = String(normCode(p.code || '') || '').toLowerCase();
    const pf = partFamilyIdOf(p);
    const pi = partItemIdOf(p);
    if (/part_pearl_elem/i.test(codeNorm)) return true;
    if (pf === 1 && Number.isFinite(pi) && pi >= 55 && pi <= 60 && /weapon\.part_override_/.test(codeNorm)) return true;
    return false;
  }

  function weaponPearlStatPartMatch(p){
    if (!p) return false;
    if (weaponPearlElemPartMatch(p)) return false;
    const codeNorm = String(normCode(p.code || '') || '').toLowerCase();
    const pf = partFamilyIdOf(p);
    const pi = partItemIdOf(p);
    if (/weapon\.part_pearl_/.test(codeNorm)) return true;
    if (pf === 1 && Number.isFinite(pi) && pi >= 51 && pi <= 54 && /weapon\.part_pearl_/.test(codeNorm)) return true;
    return false;
  }

  function mergeUniquePartOpts(base, extra){
    const seen = new Set();
    const out = [];
    const push = (p)=>{
      if (!p) return;
      const k = stxStableDropdownDedupeKey(p);
      if (!k || seen.has(k)) return;
      seen.add(k);
      out.push(p);
    };
    for (const p of base || []) push(p);
    for (const p of extra || []) push(p);
    return out;
  }

  /** Shared firmware chips — same idea as guidedCollectFirmwareParts (prefer 247/234/246). */
  function stxSimpleCollectFirmwareParts(){
    const byStem = Object.create(null);
    const all = getAllParts();
    for (let i = 0; i < all.length; i++){
      const p = all[i];
      if (!p) continue;
      const code = String(normCode(p.code || p.spawnCode || '') || '').toLowerCase();
      const pt = String(p.partType || '').trim().toLowerCase();
      if (!(pt === 'firmware' || /part_firmware|\.part_firmware/.test(code))) continue;
      const stemM = code.match(/part_firmware_([a-z0-9_]+)/);
      const stem = stemM ? stemM[1] : code;
      if (!stem) continue;
      const fam = p.family != null ? Number(p.family) : (p.familyId != null ? Number(p.familyId) : NaN);
      let score = 0;
      if (fam === 247) score = 100;
      else if (fam === 234) score = 90;
      else if (fam === 246) score = 80;
      else if (pt === 'firmware') score += 5;
      const idRaw = String(p.idRaw || p.idraw || '').trim();
      if (/^\d+\s*:\s*\d+$/.test(idRaw.replace(/\s+/g, ' '))) score += 3;
      const prev = byStem[stem];
      if (!prev || score > prev.score) byStem[stem] = { p: p, score: score };
    }
    const out = [];
    for (const k in byStem){
      if (Object.prototype.hasOwnProperty.call(byStem, k) && byStem[k]) out.push(byStem[k].p);
    }
    return out;
  }

  /** Stat Modifier options = Tools preset boost tokens (damage/accuracy/…), resolved from ALL_PARTS. */
  function stxSimpleCollectPresetBoostPartsForStatMod(){
    const pools = (typeof getSimplePresetBoostPools === 'function')
      ? getSimplePresetBoostPools()
      : (window.PRESET_BOOST_POOLS || {});
    const weaponCats = ['damage', 'accuracy', 'reload', 'firerate', 'ammo', 'splash', 'crit'];
    const idRawSet = Object.create(null);
    for (let ci = 0; ci < weaponCats.length; ci++){
      const pool = pools[weaponCats[ci]];
      if (!Array.isArray(pool)) continue;
      for (let i = 0; i < pool.length; i++){
        const e = pool[i];
        if (!e) continue;
        const k = e.key != null ? e.key : e.k;
        const v = e.value != null ? e.value : e.v;
        if (k == null || v == null) continue;
        idRawSet[String(k) + ':' + String(v)] = true;
      }
    }
    const parts = getAllParts();
    const out = [];
    const seen = new Set();
    for (let j = 0; j < parts.length; j++){
      const p = parts[j];
      if (!p) continue;
      const idRaw = String(p.idRaw || p.idraw || '').trim();
      if (!idRaw || !idRawSet[idRaw]) continue;
      const dk = stxStableDropdownDedupeKey(p);
      if (!dk || seen.has(dk)) continue;
      seen.add(dk);
      out.push(p);
    }
    // Synthetic rows when dataset has no matching idRaw (still selectable as `{fam:id}`).
    for (const idRaw of Object.keys(idRawSet)){
      if (seen.has('synth:' + idRaw)) continue;
      const already = out.some(p => String(p.idRaw || p.idraw || '').trim() === idRaw);
      if (already) continue;
      const bits = idRaw.split(':');
      const fam = Number(bits[0]);
      const id = Number(bits[1]);
      if (!Number.isFinite(fam) || !Number.isFinite(id)) continue;
      seen.add('synth:' + idRaw);
      out.push({
        category: 'Weapon',
        manufacturer: '',
        itemType: 'Weapon',
        partType: 'Stat Modifier',
        name: `{${fam}:${id}}`,
        code: `{${fam}:${id}}`,
        idRaw: idRaw,
        family: fam,
        id: id,
        itemId: id
      });
    }
    return out;
  }

  function applyWeaponNcsSlotOptionFilter(ncsSlot, rawOpts){
    if (!ncsSlot || !Array.isArray(rawOpts)) return rawOpts;
    const lower = (p)=> String(normCode(p && p.code)||'').toLowerCase();
    const filt = (pred)=>{ return rawOpts.filter(pred); };
    switch (ncsSlot){
      case 'hyperion_secondary_acc': return filt(p => lower(p).includes('part_shield'));
      case 'body':
        return rawOpts.filter(p => {
          const lo = lower(p);
          return !lo.includes('part_body_bolt') && !lo.includes('part_body_flap') && !lo.includes('part_body_ele');
        });
      case 'body_ele':
        return rawOpts.filter(p => lower(p).includes('part_body_ele'));
      case 'magazine':
      case 'mag': {
        const o = rawOpts.filter(p => {
          if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('mag', p);
          const lo = lower(p);
          if (typeof window.magazineAccessoryCodeMatchLo === 'function' && window.magazineAccessoryCodeMatchLo(lo)) return false;
          if (/mag_05_borg|mag_.*_borg/i.test(lo)) return false;
          return true;
        });
        /* Never fall back to every Magazine partType row (that re-includes accessories/borg). */
        return o;
      }
      case 'magazine_ted_thrown': {
        const o = rawOpts.filter(p => lower(p).includes('mag_ted_thrown'));
        return o;
      }
      case 'magazine_borg': {
        const isBorg = (p) => {
          if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('magazineBorg', p);
          return /mag_05_borg|mag_.*_borg/i.test(lower(p));
        };
        let o = rawOpts.filter(isBorg);
        if (!o.length) {
          o = getAllParts().filter((p) => {
            if (!p) return false;
            const cat = String(p.category || '').trim();
            if (cat && cat !== 'Weapon' && cat !== 'Prefix' && cat !== 'Rarity') return false;
            return isBorg(p);
          });
        }
        return o;
      }
      case 'magazine_acc': {
        const isMagAcc = (p) => {
          if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('magazineAcc', p);
          const lo = lower(p);
          if (typeof window.magazineAccessoryCodeMatchLo === 'function') return window.magazineAccessoryCodeMatchLo(lo);
          return /mag_acc|magazine_acc|part_mag_acc/i.test(lo)
            || /part_mag[^.\s]*_acc(?:_|$|\.)/.test(lo);
        };
        let o = rawOpts.filter(isMagAcc);
        // Never fall back to the full Magazine pool — that dumps normal mags into this slot.
        if (!o.length) {
          o = getAllParts().filter((p) => {
            if (!p) return false;
            const cat = String(p.category || '').trim();
            if (cat && cat !== 'Weapon' && cat !== 'Prefix' && cat !== 'Rarity') return false;
            return isMagAcc(p);
          });
        }
        return o;
      }
      case 'barrel': {
        const isMain = (p) => {
          if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('barrel', p);
          const lo = lower(p);
          const pt = String((p && p.partType) || '').trim().toLowerCase();
          if (pt === 'barrel accessory') return false;
          if (typeof window.barrelAccessoryCodeMatchLo === 'function' && window.barrelAccessoryCodeMatchLo(lo)) return false;
          if (pt === 'barrel') return true;
          if (typeof window.barrelMainCodeMatchLo === 'function') return window.barrelMainCodeMatchLo(lo);
          return /part_barrel/i.test(lo);
        };
        const o = rawOpts.filter(isMain);
        return o;
      }
      case 'barrel_acc': {
        const isAcc = (p) => {
          if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('barrelAcc', p);
          const lo = lower(p);
          const pt = String((p && p.partType) || '').trim().toLowerCase();
          if (pt === 'barrel accessory') return true;
          if (typeof window.barrelAccessoryCodeMatchLo === 'function') return window.barrelAccessoryCodeMatchLo(lo);
          return /part_barrel_\d+_[a-d](?:$|x)/i.test(lo) || /barrel_acc|part_barrel_acc/i.test(lo);
        };
        let o = rawOpts.filter(isAcc);
        // Never fall back to the full Barrel pool — that dumps main barrels into this slot.
        if (!o.length) {
          o = getAllParts().filter((p) => {
            if (!p || String(p.category || '').trim() !== 'Weapon') return false;
            return isAcc(p);
          });
        }
        return o;
      }
      case 'scope': {
        const o = rawOpts.filter(p => {
          if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('scope', p);
          const lo = lower(p);
          const pt = String((p && p.partType) || '').trim().toLowerCase();
          if (pt === 'scope accessory') return false;
          if (typeof window.scopeAccessoryCodeMatchLo === 'function' && window.scopeAccessoryCodeMatchLo(lo)) return false;
          return pt === 'scope' || /part_scope/.test(lo);
        });
        return o;
      }
      case 'scope_acc': {
        const isAcc = (p) => {
          if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('scopeAcc', p);
          const lo = lower(p);
          const pt = String((p && p.partType) || '').trim().toLowerCase();
          return pt === 'scope accessory' || (typeof window.scopeAccessoryCodeMatchLo === 'function' && window.scopeAccessoryCodeMatchLo(lo));
        };
        let o = rawOpts.filter(isAcc);
        if (!o.length) {
          o = getAllParts().filter((p) => p && String(p.category || '').trim() === 'Weapon' && isAcc(p));
        }
        return o;
      }
      case 'underbarrel': {
        const o = rawOpts.filter(p => {
          if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('underbarrel', p);
          const lo = lower(p);
          return /underbarrel/.test(lo) && !/underbarrel.*_acc/.test(lo);
        });
        return o;
      }
      case 'secondary_ammo': return filt(p => lower(p).includes('part_secondary_ammo'));
      case 'barrel_licensed': return filt(p => lower(p).includes('barrel_licensed'));
      case 'body_mag': return filt(p => lower(p).includes('part_body_mag'));
      case 'underbarrel_acc': {
        const isAcc = (p) => {
          if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('underbarrelAcc', p);
          return /underbarrel_.*_acc/i.test(lower(p)) && !/acc_vis/i.test(lower(p));
        };
        let o = rawOpts.filter(isAcc);
        // Never fall back to the full Underbarrel pool.
        if (!o.length) {
          o = getAllParts().filter((p) => p && String(p.category || '').trim() === 'Weapon' && isAcc(p));
        }
        return o;
      }
      case 'underbarrel_acc_vis': {
        const isVisualAcc = (p) => {
          if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('underbarrelAccVis', p);
          return /underbarrel_.*acc_vis/i.test(lower(p)) || /^"?vla_ar\.part_underbarrel_07_b"?$/i.test(String(normCode(p && p.code) || ''));
        };
        let o = rawOpts.filter(isVisualAcc);
        /* Strict Underbarrel filtering intentionally removes accessory rows; recover only NCS visual members. */
        if (!o.length) {
          o = getAllParts().filter((p) =>
            p &&
            String(p.category || '').trim() === 'Weapon' &&
            isVisualAcc(p)
          );
        }
        return o;
      }
      case 'body_bolt': return filt(p => lower(p).includes('part_body_bolt') || lower(p).includes('part_body_flap'));
      case 'tediore_acc': return filt(p => /TED_.*part_.*(multi|mirv|homing|jav|legs)/i.test(lower(p)) || /barrel_licensed_multi/i.test(lower(p)));
      case 'tediore_secondary_acc': return filt(p => /TED_.*part_.*secondary/i.test(lower(p)));
      case 'pearl_elem': return filt(p => weaponPearlElemPartMatch(p));
      case 'pearl_stat': return filt(p => weaponPearlStatPartMatch(p));
      default:
        return rawOpts;
    }
  }

  function weaponPartMatchesNcsSlot(p, ncsSlot){
    if (!p || !ncsSlot) return true;
    const lo = String(normCode(p.code)||'').toLowerCase();
    switch (ncsSlot){
      case 'hyperion_secondary_acc': return lo.includes('part_shield');
      case 'magazine_ted_thrown': return lo.includes('mag_ted_thrown');
      case 'magazine_borg':
        if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('magazineBorg', p);
        return /mag_05_borg|mag_.*_borg/i.test(lo);
      case 'magazine_acc':
        if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('magazineAcc', p);
        if (typeof window.magazineAccessoryCodeMatchLo === 'function') return window.magazineAccessoryCodeMatchLo(lo);
        return /mag_acc|magazine_acc|part_mag_acc/i.test(lo)
          || /part_mag[^.\s]*_acc(?:_|$|\.)/.test(lo);
      case 'barrel':
        if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('barrel', p);
        if (typeof window.barrelAccessoryCodeMatchLo === 'function' && window.barrelAccessoryCodeMatchLo(lo)) return false;
        if (typeof window.barrelMainCodeMatchLo === 'function') return window.barrelMainCodeMatchLo(lo);
        return /part_barrel/i.test(lo) && !/part_barrel_\d+_[a-d](?:$|x)/i.test(lo);
      case 'barrel_acc':
        if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('barrelAcc', p);
        if (typeof window.barrelAccessoryCodeMatchLo === 'function') return window.barrelAccessoryCodeMatchLo(lo);
        return /part_barrel_\d+_[a-d](?:$|x)/i.test(lo) || /barrel_acc|part_barrel_acc/i.test(lo);
      case 'scope':
        if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('scope', p);
        return /part_scope/i.test(lo) && !/scope_acc|part_scope_acc/i.test(lo);
      case 'scope_acc':
        if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('scopeAcc', p);
        return /part_scope_acc|scope_acc/i.test(lo);
      case 'underbarrel':
        if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('underbarrel', p);
        return /underbarrel/i.test(lo) && !/underbarrel.*_acc/i.test(lo);
      case 'secondary_ammo': return lo.includes('part_secondary_ammo');
      case 'barrel_licensed': return lo.includes('barrel_licensed');
      case 'body_mag': return lo.includes('part_body_mag');
      case 'underbarrel_acc':
        if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('underbarrelAcc', p);
        return /underbarrel_.*_acc/i.test(lo) && !/acc_vis/i.test(lo);
      case 'underbarrel_acc_vis':
        if (typeof window.stxWeaponSlotPartMatch === 'function') return window.stxWeaponSlotPartMatch('underbarrelAccVis', p);
        return /underbarrel_.*acc_vis/i.test(lo) || /^vla_ar\.part_underbarrel_07_b$/i.test(lo);
      case 'body':
        if (lo.includes('part_body_bolt') || lo.includes('part_body_flap')) return false;
        if (lo.includes('part_body_ele')) return false;
        return true;
      case 'body_ele':
        return lo.includes('part_body_ele');
      case 'body_acc':
        return true;
      case 'body_bolt':
        return lo.includes('part_body_bolt') || lo.includes('part_body_flap');
      case 'secondary_ele': return lo.includes('part_secondary_elem') && lo.includes('_mal');
      case 'pearl_elem': return weaponPearlElemPartMatch(p);
      case 'pearl_stat': return weaponPearlStatPartMatch(p);
      case 'tediore_acc': return /TED_.*part_.*(multi|mirv|homing|jav|legs)/i.test(lo) || /barrel_licensed_multi/i.test(lo);
      case 'tediore_secondary_acc': return /TED_.*part_.*secondary/i.test(lo);
      default: return true;
    }
  }
  try { window.weaponPartMatchesNcsSlot = weaponPartMatchesNcsSlot; } catch (_e) {}

  const SIMPLE_SCHEMA_BY_CATEGORY = {
    /* Shield: first identity slot is Base (not weapon Body). Keys stay `body` for slot state. */
    Shield: [
      {key:'body', label:'Base', partType:'Body'},
      {key:'elementType1', label:'Element / resist (Shield 246)', partType:'TypeID1Element', customType:'type1Element'},
      {key:'resistance', label:'Resistance', partType:''},
      {key:'primary246', label:'Primary Perks 246', partType:'Perk'},
      {key:'secondary246', label:'Secondary Perks 246', partType:'Perk'},
      {key:'pearlElem246', label:'Pearl element (Shield 246)', partType:'Perk'},
      {key:'pearlStat246', label:'Pearl stat (Shield 246)', partType:'Perk'},
      {key:'armor237', label:'Armor 237 (Tediore / armor shield body)', partType:''},
      {key:'energy248', label:'Energy 248 (default for most shields)', partType:''},
      {key:'bodyLegendary', label:'Unique / Legendary', partType:'', multi:true, hideWhenEmpty:true},
      {key:'otherParts', label:'Other parts (stack)', partType:'', multi:true, customType:'otherParts'},
      {key:'firmware246', label:'Firmware 246', partType:'Firmware'}
    ],
    /* Repkit: manufacturer identity Body, then optional Variant (unique) pool. */
    Repkit: [
      {key:'body', label:'Body', partType:'Base'},
      {key:'base', label:'Variant', partType:'', customType:'repkitBase', hideWhenEmpty:true},
      {key:'payload', label:'Payload (Size)', partType:'Payload'},
      {key:'element', label:'Element', partType:'Element'},
      {key:'augment', label:'Augment', partType:'Augment', multi:true},
      {key:'perk', label:'Perk', partType:'Perk', multi:true},
      {key:'perkResist', label:'Element resist add-ons', partType:''},
      {key:'perkImmunity', label:'Element immunity add-ons', partType:''},
      {key:'perkNova', label:'Nova add-ons', partType:''},
      {key:'perkSplat', label:'Splat add-ons', partType:''},
      {key:'legendary', label:'Legendary Perks', partType:'Legendary Perks', multi:true},
      {key:'otherParts', label:'Other parts (stack)', partType:'', multi:true, customType:'otherParts'},
      {key:'firmware', label:'Firmware', partType:'Firmware'}
    ],
    /* Grenade: NCS/Legit order — body → element → payload → payload_augment →
       stat_augment → firmware → endgame → pearl_*. Keep slot keys stable for import/emit. */
    Grenade: [
      {key:'body', label:'Body', partType:'Base', multi:true, ncsSlot:'body'},
      {key:'element', label:'Element', partType:'Element', ncsSlot:'element'},
      {key:'payload', label:'Payload', partType:'Payload', multi:true, ncsSlot:'payload'},
      {key:'augment', label:'Payload Augment', partType:'Augment', multi:true, ncsSlot:'payload_augment'},
      {key:'grenadeKitStats', label:'Stat Augment', partType:'', customType:'grenadeKitStats', ncsSlot:'stat_augment'},
      {key:'special', label:'Endgame / Unique', partType:'', ncsSlot:'endgame'},
      {key:'pearlElem', label:'Pearl Element', partType:'', customType:'grenadePearlElem', ncsSlot:'pearl_elem', hideWhenEmpty:true},
      {key:'pearlStat', label:'Pearl Stat', partType:'', customType:'grenadePearlStat', ncsSlot:'pearl_stat', hideWhenEmpty:true},
      {key:'otherParts', label:'Other parts (stack)', partType:'', multi:true, customType:'otherParts'},
      {key:'firmware', label:'Firmware', partType:'Firmware', ncsSlot:'firmware'}
    ],
    /* Gadget item type = heavy weapons / turrets only (`*_HW`, `heavy_weapon_gadget`). Grenade NCS rows also use dataset category `Gadget` — filter them out in `filterParts`. */
    Gadget: [
      {key:'body', label:'Body', partType:'Body'},
      {key:'bodyAcc', label:'Body Accessory', partType:'Body Accessory'},
      {key:'barrel', label:'Barrel', partType:'Barrel'},
      {key:'barrelAcc', label:'Barrel Accessory', partType:'Barrel Accessory'},
      {key:'payload', label:'Payload', partType:'Payload', multi:true},
      {key:'augment', label:'Augment', partType:'Augment', multi:true},
      {key:'legendary', label:'Legendary Perks', partType:'Legendary Perks', multi:true},
      {key:'special', label:'Special / Unique', partType:''},
      {key:'otherParts', label:'Other parts (stack)', partType:'', multi:true, customType:'otherParts'},
      {key:'firmware', label:'Firmware', partType:'Firmware'}
    ],
    /* Enhancement: UI picks Core → Stats → Other → Firmware last; serial emit stays core → firmware → stats. */
    Enhancement: [
      {key:'core', label:'Core', partType:'Core'},
      {key:'stats', label:'Stat Group 1', partType:'Stats', multi:true},
      {key:'otherParts', label:'Other parts (stack)', partType:'', multi:true, customType:'otherParts'},
      {key:'firmware', label:'Firmware', partType:'Firmware', multi:true}
    ],
    Character: [
      {key:'perk', label:'Perk', partType:'Perk', multi:true},
      {key:'special', label:'Special / Unique', partType:''},
      {key:'otherParts', label:'Other parts (stack)', partType:'', multi:true, customType:'otherParts'},
      {key:'firmware', label:'Firmware', partType:'Firmware'}
    ]
,
'Class Mod': [
  {key:'perk', label:'Perks', partType:'Skill', multi:true},
  {key:'universal', label:'Universal Parts', partType:'Universal', multi:true},
  {key:'secondary', label:'Secondary Parts', partType:'Secondary', multi:true},
  {key:'element', label:'Element Override', partType:'Element', customType:'classModElement'},
  {key:'enhancementGunStats', label:'Enhancement stats (modded)', partType:'', multi:true, customType:'enhancementGunStats'},
  {key:'otherParts', label:'Other parts (stack)', partType:'', multi:true, customType:'otherParts'},
  {key:'firmware', label:'Firmware', partType:'Firmware'}
]
  };
  /* Heavy / Heavy Weapon share the Gadget (turret / HW) slot schema. */
  SIMPLE_SCHEMA_BY_CATEGORY.Heavy = SIMPLE_SCHEMA_BY_CATEGORY.Gadget;
  SIMPLE_SCHEMA_BY_CATEGORY['Heavy Weapon'] = SIMPLE_SCHEMA_BY_CATEGORY.Gadget;

  function normCode(code){
    if (code == null) return '';
    const s = String(code).trim();
    // dataset stores code with quotes (e.g. "DAD_AR.part_x")
    if (s.startsWith('"') && s.endsWith('"')) return s.slice(1,-1);
    return s;
  }

  /** Spawn-code family prefix for shield rows (`ted_shield`, `bor_shield`, …) — aligns with guided builder pools. */
  function stxShieldSpawnPrefixForUiManufacturer(man){
    const m = String(man || '').trim().toLowerCase();
    const map = {
      tediore: 'ted_shield',
      ripper: 'bor_shield',
      jakobs: 'jak_shield',
      maliwan: 'mal_shield',
      order: 'ord_shield',
      daedalus: 'dad_shield',
      torgue: 'tor_shield',
      vladof: 'vla_shield',
      hyperion: 'hyp_shield'
    };
    return map[m] || '';
  }

  /**
   * Rows with manufacturer `gadgets` were previously treated as universal for all shields, which leaked
   * every mfr's `*_shield.comp_*` into the rarity/body dropdowns. Shared gadget pools use `Shield.` / `Armor_Shield.` / `energy_shield.`.
   */
  function stxShieldGadgetRowMatchesSelectedManufacturer(codeNormLo, wantMan){
    const pref = stxShieldSpawnPrefixForUiManufacturer(wantMan);
    if (!pref) return true;
    const c = String(codeNormLo || '').toLowerCase();
    if (/^shield\.part_/.test(c) || /^armor_shield\./.test(c) || /^energy_shield\./.test(c)) return true;
    const PREFIXES = ['ted_shield', 'bor_shield', 'jak_shield', 'mal_shield', 'ord_shield', 'dad_shield', 'tor_shield', 'vla_shield', 'hyp_shield'];
    let hit = '';
    for (let i = 0; i < PREFIXES.length; i++){
      const px = PREFIXES[i];
      if (c.indexOf(px + '.') === 0) { hit = px; break; }
    }
    if (!hit) return true;
    return hit === pref;
  }

  /**
   * Shield NCS dep tables. Base uses `body` only.
   * Maliwan/Order/Torgue `unique` parts are not bodies (Daedalus Supersoldier is a body).
   */
  const STX_SHIELD_NCS_BODY_TAILS = {
    bor_shield: ['part_body_energy', 'part_body_energy_firewall', 'part_body_energy_lightning', 'part_body_energy_watts4dinner', 'part_body_energy_overswarm'],
    dad_shield: ['part_body_energy', 'part_body_angel', 'part_unique_supersoldier', 'part_body_honeybadger'],
    jak_shield: ['part_body_armor', 'part_body_armor_onionlayeredguard', 'part_body_barrelaged', 'part_body_armor_exfoliatrix'],
    mal_shield: ['part_body_energy'],
    ord_shield: ['part_body_energy', 'part_body_energy_proteancell', 'part_body_energy_collector'],
    ted_shield: ['part_body_armor', 'part_body_shieldboi', 'part_body_timekeeper', 'part_body_hopscotch', 'part_body_pocketbuddies'],
    tor_shield: ['part_body_armor', 'part_body_armor_compleat'],
    vla_shield: ['part_body_armor', 'part_body_armor_heavyweight', 'part_body_armor_hoarder', 'part_body_armor_undershield']
  };
  const STX_SHIELD_NCS_UNIQUE_TAILS = {
    mal_shield: ['part_unique_supernova', 'part_unique_momento', 'part_unique_elpisstar'],
    ord_shield: ['part_unique_cindershelly'],
    tor_shield: ['part_unique_firewerks', 'part_unique_hydrowerks']
  };

  function stxShieldInvTail(normLo){
    const c = String(normLo || '').toLowerCase();
    const m = c.match(/^([a-z0-9]+_shield)\.([a-z0-9_]+)$/);
    if (!m) return null;
    return { inv: m[1], tail: m[2] };
  }
  function stxIsShieldBodyPoolRowCode(normLo){
    const hit = stxShieldInvTail(normLo);
    if (!hit) return false;
    const tails = STX_SHIELD_NCS_BODY_TAILS[hit.inv];
    return !!(tails && tails.indexOf(hit.tail) !== -1);
  }
  function stxIsShieldUniquePoolRowCode(normLo){
    const hit = stxShieldInvTail(normLo);
    if (!hit) return false;
    const tails = STX_SHIELD_NCS_UNIQUE_TAILS[hit.inv];
    return !!(tails && tails.indexOf(hit.tail) !== -1);
  }

  /** Shield Base row to pin for the selected rarity (`part_body_timekeeper` for Timekeeper). */
  function stxShieldRarityPinnedBodyCode(parts, rarityPart, wantMan){
    const suffix = stxGrenadeRarityBodySuffixFromPart(rarityPart);
    const pref = stxShieldSpawnPrefixForUiManufacturer(wantMan);
    const list = Array.isArray(parts) ? parts : [];
    if (suffix && pref) {
      for (let i = 0; i < list.length; i++) {
        const c = String(normCode(list[i] && list[i].code || '') || '').toLowerCase();
        if (c.indexOf(pref + '.') !== 0) continue;
        if (!stxIsShieldBodyPoolRowCode(c)) continue;
        if (stxGrenadeBodyCodeMatchesRaritySuffix(c, suffix)) return c;
      }
    }
    if (pref) {
      const energy = pref + '.part_body_energy';
      const armor = pref + '.part_body_armor';
      for (let j = 0; j < list.length; j++) {
        const c2 = String(normCode(list[j] && list[j].code || '') || '').toLowerCase();
        if (c2 === energy || c2 === armor) return c2;
      }
    }
    return '';
  }
  try { window.stxShieldRarityPinnedBodyCode = stxShieldRarityPinnedBodyCode; } catch (_eShPin) {}

  /** `wantMan` is normalized lowercase (e.g. from `String(man).trim().toLowerCase()`). */
  function stxGrenadeSpawnPrefixForUiManufacturer(wantMan){
    const m = String(wantMan || '').trim().toLowerCase();
    const map = {
      tediore: 'ted_grenade_gadget',
      jakobs: 'jak_grenade_gadget',
      maliwan: 'mal_grenade_gadget',
      order: 'ord_grenade_gadget',
      daedalus: 'dad_grenade_gadget',
      torgue: 'tor_grenade_gadget',
      vladof: 'vla_grenade_gadget',
      cov: 'cov_grenade_gadget',
      ripper: 'borg_grenade_gadget',
      borg: 'borg_grenade_gadget'
    };
    return map[m] || '';
  }

  /** Manufacturer `*_repair_kit` spawn prefix for Simple Builder repkit slots (e.g. `jak_repair_kit`). */
  function stxRepkitSpawnPrefixForUiManufacturer(wantMan){
    const m = String(wantMan || '').trim().toLowerCase();
    const prefix =
      (m === 'tediore') ? 'ted' :
      (m === 'torgue') ? 'tor' :
      (m === 'jakobs') ? 'jak' :
      (m === 'maliwan') ? 'mal' :
      (m === 'vladof') ? 'vla' :
      (m === 'daedalus') ? 'dad' :
      (m === 'order') ? 'ord' :
      (m === 'ripper' || m === 'borg') ? 'bor' :
      '';
    return prefix ? prefix + '_repair_kit' : '';
  }

  /**
   * Same idea as shields: shared `grenade_gadget.*` stays cross-manufacturer; `jak_grenade_gadget.*` etc.
   * must match the selected UI manufacturer (Ripper → `borg_grenade_gadget`, not `bor_*`).
   */
  function stxGrenadeGadgetRowMatchesSelectedManufacturer(codeNormLo, wantMan){
    const pref = stxGrenadeSpawnPrefixForUiManufacturer(wantMan);
    const c = String(codeNormLo || '').toLowerCase();
    if (c.indexOf('grenade_gadget.') === 0) return true;
    const PREFIXES = ['ted_grenade_gadget', 'borg_grenade_gadget', 'cov_grenade_gadget', 'jak_grenade_gadget', 'mal_grenade_gadget', 'ord_grenade_gadget', 'dad_grenade_gadget', 'tor_grenade_gadget', 'vla_grenade_gadget'];
    let hit = '';
    for (let i = 0; i < PREFIXES.length; i++){
      const px = PREFIXES[i];
      if (c.indexOf(px + '.') === 0){ hit = px; break; }
    }
    if (!hit) return true;
    if (!pref) return false;
    return hit === pref;
  }

  /** Identity grenade row: `mal_grenade_gadget.part_mal` / `borg_grenade_gadget.part_borg`, etc. */
  function stxIsGrenadeManufacturerIdentityBodyCode(normLo){
    const c = String(normLo || '').toLowerCase();
    return /(^|[^a-z0-9])(?:borg|bor|cov|dad|jak|mal|ord|ted|tor|vla)_grenade_gadget\.part_(?:borg|dad|jak|mal|ord|ted|tor|vla|cov)($|[^a-z0-9])/.test(c);
  }

  /**
   * Skin-only "rarity" rows (`ORD.part_rarity` / "UAV Skin") — not real inv_comp rarity ids.
   * Must never drive header family or sit first after `||` (breaks grenade spawns).
   */
  function stxIsGrenadeSkinRarityPart(p){
    if (!p) return false;
    const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
    if (!c) return false;
    if (c === 'ord.part_rarity' || /(^|[._])part_rarity$/.test(c)) return true;
    if (/\.comp_0[1-6]_/.test(c)) return false;
    const blob = String((p.stats || '') + ' ' + (p.dataNote || '') + ' ' + (p.name || '') + ' ' + (p.effects || '')).toLowerCase();
    if (blob.indexOf('can be used for skin') !== -1) return true;
    if (/\bskin\b/.test(blob) && String(p.partType || '').trim().toLowerCase() === 'rarity') return true;
    return false;
  }
  try { window.stxIsGrenadeSkinRarityPart = stxIsGrenadeSkinRarityPart; } catch (_e) {}

  /** Legendary/epic/pearl suffix from rarity-id spawn (`comp_05_legendary_PredatorDrone` → `predatordrone`). */
  function stxGrenadeRarityBodySuffixFromPart(p){
    const c = String(normCode(p && (p.code || p.spawnCode || p.importCode) || '') || '').toLowerCase();
    if (!c) return '';
    let m = c.match(/\.comp_05_legendary_([a-z0-9_]+)/);
    if (m) return m[1];
    m = c.match(/\.comp_06_pearlescent_([a-z0-9_]+)/);
    if (m) return m[1];
    m = c.match(/\.comp_04_epic_([a-z0-9_]+)/);
    if (m) return m[1];
    return '';
  }
  try { window.stxGrenadeRarityBodySuffixFromPart = stxGrenadeRarityBodySuffixFromPart; } catch (_e) {}

  function stxGrenadeBodyCodeMatchesRaritySuffix(codeNormLo, suffix){
    const suf = String(suffix || '').trim().toLowerCase();
    if (!suf) return false;
    const c = String(codeNormLo || '').toLowerCase();
    if (c.indexOf('.part_' + suf) !== -1) return true;
    const tail = c.split('.').pop() || '';
    return tail === suf || tail === ('part_' + suf) || tail.slice(-(suf.length + 1)) === ('_' + suf);
  }
  try { window.stxGrenadeBodyCodeMatchesRaritySuffix = stxGrenadeBodyCodeMatchesRaritySuffix; } catch (_e) {}

  /**
   * Body to pin/highlight for the selected rarity: named body (`part_tor_slippy` for Slippy)
   * when one exists, otherwise this manufacturer's identity body.
   */
  function stxGrenadeRarityPinnedBodyCode(parts, rarityPart, wantMan){
    const suffix = stxGrenadeRarityBodySuffixFromPart(rarityPart);
    const man = String(wantMan || '').trim().toLowerCase();
    const spawn = stxGrenadeSpawnPrefixForUiManufacturer(man);
    let identity = '';
    if (spawn) {
      const sm = spawn.match(/^([a-z0-9]+)_grenade_gadget$/);
      if (sm) identity = (spawn + '.part_' + sm[1]).toLowerCase();
    }
    const list = Array.isArray(parts) ? parts : [];
    if (suffix) {
      for (let i = 0; i < list.length; i++) {
        const c = String(normCode(list[i] && list[i].code || '') || '').toLowerCase();
        if (!stxGrenadeBodyCodeMatchesRaritySuffix(c, suffix)) continue;
        if (man && !stxGrenadeGadgetRowMatchesSelectedManufacturer(c, man)) continue;
        return c;
      }
    }
    return identity;
  }
  try { window.stxGrenadeRarityPinnedBodyCode = stxGrenadeRarityPinnedBodyCode; } catch (_ePin) {}

  /**
   * Sort grenade Body dropdown: rarity-matched variant first, then manufacturer identity,
   * then other selected-mfr bodies, then remaining (all manufacturers still listed).
   */
  function stxSortGrenadeBodyOptionsForRarity(parts, rarityPart, wantMan){
    const arr = Array.isArray(parts) ? parts.slice() : [];
    if (!arr.length) return arr;
    const pinned = stxGrenadeRarityPinnedBodyCode(arr, rarityPart, wantMan);
    const suffix = stxGrenadeRarityBodySuffixFromPart(rarityPart);
    const man = String(wantMan || '').trim().toLowerCase();
    const spawn = stxGrenadeSpawnPrefixForUiManufacturer(man);
    let identity = '';
    if (spawn) {
      const sm = spawn.match(/^([a-z0-9]+)_grenade_gadget$/);
      if (sm) identity = (spawn + '.part_' + sm[1]).toLowerCase();
    }
    const rank = (p)=>{
      const c = String(normCode(p && p.code || '') || '').toLowerCase();
      if (pinned && c === pinned) return 0;
      if (suffix && stxGrenadeBodyCodeMatchesRaritySuffix(c, suffix)) return 1;
      if (identity && c === identity) return 2;
      if (man && stxGrenadeGadgetRowMatchesSelectedManufacturer(c, man)) {
        return stxIsGrenadeManufacturerIdentityBodyCode(c) ? 3 : 4;
      }
      return 5;
    };
    arr.sort((a, b)=>{
      const d = rank(a) - rank(b);
      if (d) return d;
      return displayForPart(a).localeCompare(displayForPart(b), undefined, { numeric: true, sensitivity: 'base' });
    });
    return arr;
  }
  try { window.stxSortGrenadeBodyOptionsForRarity = stxSortGrenadeBodyOptionsForRarity; } catch (_e) {}

  /** Named rarity suffix for weapon barrels (`comp_05_legendary_Eigenburst` → `eigenburst`). */
  function stxRarityBarrelSuffixFromPart(rarityPart){
    const fromGrenadeHelper = stxGrenadeRarityBodySuffixFromPart(rarityPart);
    if (fromGrenadeHelper) return fromGrenadeHelper;
    const tok = stxBarrelPearlLegendTokenFromPart(rarityPart);
    return tok ? String(tok).toLowerCase() : '';
  }
  try { window.stxRarityBarrelSuffixFromPart = stxRarityBarrelSuffixFromPart; } catch (_e) {}

  function stxCumulativeUnderscorePrefixes(fam){
    const parts = String(fam || '').toLowerCase().split('_').filter(Boolean);
    const out = [];
    for (let i = 1; i <= parts.length; i++) out.push(parts.slice(0, i).join('_'));
    return out;
  }

  /** True when `part_barrel_##_<tail>` (or unnumbered / unique HW barrels) belongs to `comp_05_legendary_<fam>`. */
  function stxWeaponBarrelCodeMatchesRaritySuffix(codeNormLo, suffix){
    const suf = String(suffix || '').trim().toLowerCase().replace(/[^a-z0-9_]/g, '');
    if (!suf) return false;
    const c = String(codeNormLo || '').toLowerCase();
    let tail = '';
    const mb = c.match(/part_barrel_\d+_([a-z0-9_]+)$/);
    if (mb) tail = String(mb[1] || '').toLowerCase().replace(/[^a-z0-9_]/g, '');
    if (!tail){
      const uniq = c.match(/part_unique_barrel_\d+_([a-z0-9_]+)$/);
      if (uniq) tail = String(uniq[1] || '').toLowerCase().replace(/[^a-z0-9_]/g, '');
    }
    if (!tail){
      /* Heavy legendaries like Heimdahl: `tor_hw.part_barrel_dahlfather` (no digit index). */
      const bare = c.match(/\.part_barrel_([a-z][a-z0-9_]{2,})$/);
      if (bare) tail = String(bare[1] || '').toLowerCase().replace(/[^a-z0-9_]/g, '');
    }
    if (!tail) return false;
    if (tail === suf) return true;
    const allowed = stxCumulativeUnderscorePrefixes(suf);
    if (allowed.indexOf(tail) >= 0) return true;
    /* Also allow barrel tails that start with the rarity fam token. */
    if (tail.indexOf(suf) === 0 && (tail.length === suf.length || tail.charAt(suf.length) === '_')) return true;
    /* Rarity slug `dahlfather` ↔ display Heimdahl still uses that spawn tail. */
    if (suf.indexOf(tail) === 0 && (suf.length === tail.length || suf.charAt(tail.length) === '_')) return true;
    return false;
  }
  try { window.stxWeaponBarrelCodeMatchesRaritySuffix = stxWeaponBarrelCodeMatchesRaritySuffix; } catch (_e) {}

  function stxWeaponRarityPinnedBarrelCode(parts, rarityPart){
    const suffix = stxRarityBarrelSuffixFromPart(rarityPart);
    if (!suffix) return '';
    const list = Array.isArray(parts) ? parts : [];
    for (let i = 0; i < list.length; i++) {
      const c = String(normCode(list[i] && list[i].code || '') || '').toLowerCase();
      if (stxWeaponBarrelCodeMatchesRaritySuffix(c, suffix)) return c;
    }
    return '';
  }
  try { window.stxWeaponRarityPinnedBarrelCode = stxWeaponRarityPinnedBarrelCode; } catch (_e) {}

  /** Sort weapon Barrel dropdown: rarity-matched named barrel first, then remaining. */
  function stxSortWeaponBarrelOptionsForRarity(parts, rarityPart){
    const arr = Array.isArray(parts) ? parts.slice() : [];
    if (!arr.length) return arr;
    const pinned = stxWeaponRarityPinnedBarrelCode(arr, rarityPart);
    const suffix = stxRarityBarrelSuffixFromPart(rarityPart);
    if (!suffix && !pinned) return arr;
    const rank = (p)=>{
      const c = String(normCode(p && p.code || '') || '').toLowerCase();
      if (pinned && c === pinned) return 0;
      if (suffix && stxWeaponBarrelCodeMatchesRaritySuffix(c, suffix)) return 1;
      return 2;
    };
    arr.sort((a, b)=>{
      const d = rank(a) - rank(b);
      if (d) return d;
      return displayForPart(a).localeCompare(displayForPart(b), undefined, { numeric: true, sensitivity: 'base' });
    });
    return arr;
  }
  try { window.stxSortWeaponBarrelOptionsForRarity = stxSortWeaponBarrelOptionsForRarity; } catch (_e) {}

  /** Collect NCS grenade body-slot rows (all manufacturers) for Body dropdowns. */
  function stxCollectAllGrenadeBodyParts(){
    const all = getAllParts();
    const out = [];
    const seen = Object.create(null);
    for (let i = 0; i < all.length; i++){
      const p = all[i];
      if (!p) continue;
      const c = String(normCode(p.code || '') || '').toLowerCase();
      if (!stxIsGrenadeBodyPoolRowCode(c)) continue;
      if (stxIsGrenadeSkinRarityPart(p)) continue;
      const key = String((p.idRaw != null ? p.idRaw : '') || c);
      if (seen[key]) continue;
      seen[key] = 1;
      out.push(p);
    }
    return out;
  }
  try { window.stxCollectAllGrenadeBodyParts = stxCollectAllGrenadeBodyParts; } catch (_e) {}

  /**
   * Grenade part tails by NCS dep table (`Nexus-Data-inv*.json` on each `*_grenade_gadget`).
   * Body is only that table — divider/seeker/repeater and named uniques are payload or payload_augment.
   */
  const STX_GRENADE_NCS_SLOT_TAILS = {
    body: {
      borg_grenade_gadget: ['part_borg'],
      dad_grenade_gadget: ['part_dad'],
      jak_grenade_gadget: ['part_jak', 'part_jak_bismuth'],
      mal_grenade_gadget: ['part_mal'],
      ord_grenade_gadget: ['part_ord', 'part_ord_alignment'],
      ted_grenade_gadget: ['part_ted'],
      tor_grenade_gadget: ['part_tor', 'part_tor_slippy', 'body_flare'],
      vla_grenade_gadget: ['part_vla', 'part_vla_waterfall']
    },
    payload: {
      borg_grenade_gadget: ['part_02_divider_borg', 'part_payload_unique_rubber', 'part_payload_unique_transmission', 'part_payload_unique_pellet', 'part_payload_unique_buoy'],
      dad_grenade_gadget: ['part_payload_axe', 'part_payload_fuse', 'part_payload_pressurecooker'],
      grenade_gadget: ['part_01_mirv', 'part_02_divider', 'part_03_spring', 'part_04_artillery', 'part_05_singularity', 'part_06_lingering_corrosive', 'part_06_lingering_cryo', 'part_06_lingering_fire', 'part_06_lingering_radiation', 'part_06_lingering_shock', 'part_07_damage_amp', 'part_01_mirv_brudder'],
      jak_grenade_gadget: ['part_02_divider_jak', 'part_shokunai', 'part_bismuth_corrosive', 'part_bismuth_cryo', 'part_bismuth_fire', 'part_bismuth_radiation', 'part_bismuth_shock', 'part_spinning_blade'],
      mal_grenade_gadget: ['part_02_divider_maliwan', 'part_disco_disc', 'part_recursive', 'part_brudder'],
      ord_grenade_gadget: ['part_aggrovator', 'part_alignment', 'part_skully'],
      ted_grenade_gadget: ['part_faultydetonator', 'part_predatordrone', 'part_ordinance', 'part_urchin'],
      tor_grenade_gadget: ['payload_firepot', 'part_payload_firepot'],
      vla_grenade_gadget: ['part_blockbuster', 'part_barb']
    },
    payload_augment: {
      borg_grenade_gadget: ['part_02_divider_02_seeker_borg', 'part_02_divider_04_repeater_borg'],
      grenade_gadget: ['part_01_mirv_01_children', 'part_01_mirv_02_bouncer', 'part_01_mirv_03_micro_mirv', 'part_01_mirv_04_spring', 'part_02_divider_01_children', 'part_02_divider_02_seeker', 'part_02_divider_03_singularity', 'part_02_divider_04_repeater', 'part_02_divider_05_spring', 'part_03_spring_01_additional_bounce', 'part_03_spring_02_apex', 'part_03_spring_03_compound', 'part_03_spring_04_bouncer', 'part_03_spring_05_spawning', 'part_04_artillery_01_duration', 'part_04_artillery_02_ricochet', 'part_04_artillery_03_micro_missiles', 'part_04_artillery_04_maglock', 'part_04_artillery_05_mortar_strike', 'part_05_singularity_01_duration', 'part_05_singularity_02_lingering', 'part_05_singularity_03_collapsing', 'part_05_singularity_04_repulsor', 'part_06_lingering_01_duration_bursts', 'part_06_lingering_01_duration_bursts_cryo', 'part_06_lingering_02_pulse', 'part_06_lingering_03_splat_pack', 'part_06_lingering_04_fracture', 'part_06_lingering_05_alchemic', 'part_07_damage_amp_01_bouncing', 'part_07_damage_amp_02_suppressor', 'part_07_damage_amp_03_penetrator'],
      jak_grenade_gadget: ['part_02_divider_02_seeker_jak', 'part_02_divider_04_repeater_jak'],
      mal_grenade_gadget: ['part_02_divider_02_seeker_mal', 'part_02_divider_04_repeater_mal'],
      ord_grenade_gadget: ['part_01_mirv_05_swarm']
    }
  };

  function stxGrenadeCodeMatchesNcsSlot(normLo, slotName){
    const c = String(normLo || '').toLowerCase();
    const m = c.match(/^([a-z0-9]+_grenade_gadget|grenade_gadget)\.([a-z0-9_]+)$/);
    if (!m) return false;
    const tails = STX_GRENADE_NCS_SLOT_TAILS[slotName] && STX_GRENADE_NCS_SLOT_TAILS[slotName][m[1]];
    if (!tails) return false;
    return tails.indexOf(m[2]) !== -1;
  }

  /** NCS `body` dep table only (identity + the few body variants). */
  function stxIsGrenadeBodyPoolRowCode(normLo){
    return stxGrenadeCodeMatchesNcsSlot(normLo, 'body');
  }

  function stxIsGrenadePayloadPoolRowCode(normLo){
    return stxGrenadeCodeMatchesNcsSlot(normLo, 'payload');
  }

  function stxIsGrenadePayloadAugmentPoolRowCode(normLo){
    return stxGrenadeCodeMatchesNcsSlot(normLo, 'payload_augment');
  }

  function stxSortGrenadeBodySelections(parts){
    const arr = (Array.isArray(parts) ? parts.slice() : (parts ? [parts] : [])).filter(Boolean);
    const rank = (p)=>{
      const c = String(normCode(p && p.code || '') || '').toLowerCase();
      return stxIsGrenadeManufacturerIdentityBodyCode(c) ? 0 : 1;
    };
    arr.sort((a,b)=>{
      const d = rank(a) - rank(b);
      if (d) return d;
      return displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'});
    });
    return arr;
  }

  function stxGrenadeBodyVariantKey(p){
    const c = String(normCode((p && (p.code || p.spawnCode || p.importCode)) || '') || '').toLowerCase();
    const m = c.match(/grenade_gadget\.part_([a-z0-9_]+)/);
    return m ? m[1] : '';
  }

  /** Same grenade body even when one row is a spawn code and the other is `{family:id}`. */
  function stxGrenadeBodiesMatch(a, b){
    if (!a || !b) return false;
    if (a === b) return true;
    const codeOf = (p)=> String(normCode(p.code || p.spawnCode || p.importCode || '') || '').trim().toLowerCase();
    const ca = codeOf(a);
    const cb = codeOf(b);
    if (ca && cb && ca === cb) return true;
    const ka = stxGrenadeBodyVariantKey(a);
    const kb = stxGrenadeBodyVariantKey(b);
    if (ka && kb && ka === kb) return true;
    try {
      const na = numericTokenFromPart(a);
      const nb = numericTokenFromPart(b);
      if (na && nb && String(na) === String(nb)) return true;
    } catch (_eGrenSame) {}
    const ta = String(tokenForPart(a) || '').trim().toLowerCase();
    const tb = String(tokenForPart(b) || '').trim().toLowerCase();
    return !!(ta && tb && ta === tb);
  }

  /** 3-letter enhancement prefix (`atl`, `jak`, …) for `*_enhancement.` spawn paths. */
  function stxEnhancementCodePrefixForUiManufacturer(wantMan){
    const m = String(wantMan || '').trim().toLowerCase();
    const map = {
      atlas: 'atl',
      cov: 'cov',
      daedalus: 'dad',
      hyperion: 'hyp',
      jakobs: 'jak',
      maliwan: 'mal',
      order: 'ord',
      ripper: 'bor',
      borg: 'bor',
      tediore: 'ted',
      torgue: 'tor',
      vladof: 'vla'
    };
    return map[m] || '';
  }

  /** Shared `enhancement.*` (family 247) vs manufacturer `ATL_Enhancement.*` pools. */
  function stxEnhancementGadgetRowMatchesSelectedManufacturer(codeNormLo, wantMan){
    const pref3 = stxEnhancementCodePrefixForUiManufacturer(wantMan);
    const c = String(codeNormLo || '').toLowerCase();
    if (c.indexOf('enhancement.') === 0) return true;
    const em = c.match(/^([a-z]{3})_enhancement\./);
    if (!em) return true;
    if (!pref3) return false;
    return em[1] === pref3;
  }

  /** TypeID (family) for `ted_enhancement.*` / `mal_enhancement.*` when the part row omits `family` / `idRaw` — used for dropdown dedupe and tier gates. */
  function stxEnhancementTypeFamilyIdFromSpawnCode(codeNormLo){
    const c = String(codeNormLo || '').toLowerCase();
    const em = c.match(/^([a-z]{3})_enhancement\./);
    if (!em || !em[1]) return null;
    const m3 = em[1];
    const mfr =
      (m3 === 'atl') ? 'Atlas' :
      (m3 === 'cov') ? 'COV' :
      (m3 === 'dad') ? 'Daedalus' :
      (m3 === 'hyp') ? 'Hyperion' :
      (m3 === 'jak') ? 'Jakobs' :
      (m3 === 'mal') ? 'Maliwan' :
      (m3 === 'ord') ? 'Order' :
      (m3 === 'bor') ? 'Ripper' :
      (m3 === 'ted') ? 'Tediore' :
      (m3 === 'tor') ? 'Torgue' :
      (m3 === 'vla') ? 'Vladof' :
      '';
    if (!mfr) return null;
    try{
      const rr = (Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : (typeof STX_RARITIES !== 'undefined' ? STX_RARITIES : [])) || [];
      const row = rr.find(r => String(r && r.itemType || '').trim() === 'Enhancement' && String(r && r.manufacturer || '').trim() === mfr);
      const fam = row ? Number(row.familyId) : NaN;
      return Number.isFinite(fam) ? fam : null;
    }catch(_e){ return null; }
  }

  /** Heavy / Gadget pool: `MAL_HW`, `BOR_HW`, … vs shared `heavy_weapon_gadget`. */
  function stxGadgetHwSpawnPrefixForUiManufacturer(wantMan){
    const m = String(wantMan || '').trim().toLowerCase();
    const map = {
      maliwan: 'mal_hw',
      ripper: 'bor_hw',
      borg: 'bor_hw',
      torgue: 'tor_hw',
      vladof: 'vla_hw'
    };
    return map[m] || '';
  }

  function stxGadgetHeavyRowMatchesSelectedManufacturer(codeNormLo, wantMan){
    const pref = stxGadgetHwSpawnPrefixForUiManufacturer(wantMan);
    const c = String(codeNormLo || '').toLowerCase();
    if (c.indexOf('heavy_weapon_gadget.') === 0) return true;
    const hm = c.match(/^([a-z]{3})_hw\./);
    if (!hm) return true;
    const hit = hm[1] + '_hw';
    if (!pref) return false;
    return hit === pref;
  }

  function stxWeaponTypeSuffixForUiWeaponType(wt){
    const w = String(wt || '').trim().toLowerCase();
    if (w === 'assault rifle' || w === 'assault' || w === 'ar') return '_ar';
    if (w === 'smg' || w === 'submachine gun' || w === 'submachinegun') return '_sm';
    if (w === 'shotgun' || w === 'sg') return '_sg';
    if (w === 'pistol' || w === 'ps') return '_ps';
    if (w === 'sniper rifle' || w === 'sniper' || w === 'sr') return '_sr';
    if (w === 'heavy weapon' || w === 'heavy' || w === 'hw') return '_hw';
    return '';
  }

  function stxWeaponCodePrefixForUiManufacturer(wantMan){
    const m = String(wantMan || '').trim().toLowerCase();
    const map = {
      atlas: 'atl',
      cov: 'cov',
      daedalus: 'dad',
      hyperion: 'hyp',
      jakobs: 'jak',
      maliwan: 'mal',
      order: 'ord',
      ripper: 'bor',
      borg: 'bor',
      tediore: 'ted',
      torgue: 'tor',
      vladof: 'vla'
    };
    return map[m] || '';
  }

  /** e.g. `dad_ar` for Daedalus Assault Rifle — used to keep body dropdowns item-scoped. */
  function stxWeaponSpawnPrefixForUiManufacturer(wantMan, weaponType){
    const pref3 = stxWeaponCodePrefixForUiManufacturer(wantMan);
    const suf = stxWeaponTypeSuffixForUiWeaponType(weaponType);
    if (!pref3 || !suf) return '';
    return pref3 + suf;
  }

  /** True when spawn path prefix matches the selected manufacturer + weapon type (e.g. `jak_sg.`). */
  function stxWeaponSpawnPrefixMatchesCode(codeNormLo, pref){
    const c = String(codeNormLo || '').toLowerCase();
    const p = String(pref || '').toLowerCase();
    if (!p) return true;
    if (p.endsWith('_hw')) {
      const hm = c.match(/^([a-z]{3})_hw\./);
      return !!(hm && (hm[1] + '_hw') === p);
    }
    const wm = c.match(/^([a-z]{3})_(ar|sm|sg|ps|sr|hw)\./);
    if (!wm) return false;
    return (wm[1] + '_' + wm[2]) === p;
  }

  function stxWeaponRowMatchesSelectedManufacturer(codeNormLo, wantMan, weaponType){
    const pref = stxWeaponSpawnPrefixForUiManufacturer(wantMan, weaponType);
    return stxWeaponSpawnPrefixMatchesCode(codeNormLo, pref);
  }

  /** Manufacturer + weapon-type body rows that can legitimately spawn on the item (not bolt/ele/comp pools). */
  function stxIsWeaponNaturalBodyPoolRowCode(normLo, wantMan, weaponType){
    const c = String(normLo || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!c || !/part_body/i.test(c)) return false;
    if (c.includes('part_body_bolt') || c.includes('part_body_flap') || c.includes('part_body_ele') || c.includes('part_body_mag')) return false;
    /* Letter body accessories belong in Body Accessory, not the main Body slot. */
    if (/\.part_body_[a-z](?:_|$)/.test(c)) return false;
    if (c.includes('.comp_') || /(?:^|[._])comp_0[1-6]_/.test(c) || /(?:^|[._])pearl_/.test(c)) return false;
    const pref = stxWeaponSpawnPrefixForUiManufacturer(wantMan, weaponType);
    if (!pref) return false;
    if (!stxWeaponSpawnPrefixMatchesCode(c, pref)) return false;
    return /\.part_body(?:$|_\d)/.test(c);
  }

  /**
   * Fallback Body pool when the strict natural body (`mfr_wt.part_body`) is missing from the dataset:
   * letter accessories / other Body-typed rows for the same spawn prefix (still excludes bolt/ele/mag).
   */
  function stxIsWeaponBodySlotFallbackRowCode(normLo, wantMan, weaponType){
    const c = String(normLo || '').toLowerCase().replace(/^["']|["']$/g, '');
    if (!c || !/part_body/i.test(c)) return false;
    if (c.includes('part_body_bolt') || c.includes('part_body_flap') || c.includes('part_body_ele') || c.includes('part_body_mag')) return false;
    if (c.includes('.comp_') || /(?:^|[._])comp_0[1-6]_/.test(c) || /(?:^|[._])pearl_/.test(c)) return false;
    const pref = stxWeaponSpawnPrefixForUiManufacturer(wantMan, weaponType);
    if (!pref) return false;
    if (!stxWeaponSpawnPrefixMatchesCode(c, pref)) return false;
    return /\.part_body(?:$|_[a-z0-9])/.test(c);
  }

  /** Drop cached part pools after deferred supplements mutate ALL_PARTS. */
  function stxInvalidateSimpleBuilderPartCaches(){
    try { __filterPartsCache.clear(); } catch (_e) {}
    try { window.__stxPartCategoryIndex = null; } catch (_e) {}
    try { window.__stxAllPartsIndexed = false; } catch (_e) {}
    try { __allPartsIdxStamp = -1; } catch (_e) {}
  }

  /** Body / main-body slots must stay tied to the item under construction (even when “all manufacturers” is on). */
  function stxSlotRequiresItemManufacturer(schemaItem, category){
    const slotKey = String(schemaItem && schemaItem.key || '');
    if (category === 'Weapon') return slotKey === 'body' || slotKey === 'bodyAcc';
    if (category === 'Shield') return slotKey === 'mainBody' || slotKey === 'body';
    if (category === 'Grenade') return slotKey === 'body';
    if (category === 'Enhancement') return slotKey === 'core';
    if (category === 'Repkit') return slotKey === 'body' || String(schemaItem && schemaItem.customType || '') === 'repkitBase';
    return false;
  }

  /** Spawn path token for Repkit element rows (shared pool, any manufacturer UI selection). */
  function stxIsDatasetRepkitElementCode(normLo){
    const c = String(normLo || '').toLowerCase();
    return /^part_element_/.test(c) || /\.part_element_/.test(c);
  }

  /** Grenade element/status pool: dataset often uses empty partType + grenade_gadget.part_{element}. */
  function stxIsDatasetGrenadeElementCode(normLo){
    const c = String(normLo || '').toLowerCase();
    return /(?:^|[._])grenade_gadget\.part_(corrosive|cryo|fire|radiation|shock)\b/.test(c)
      || /[a-z0-9]+_grenade_gadget\.part_(corrosive|cryo|fire|radiation|shock)\b/.test(c)
      || /^part_element_/.test(c);
  }

  /** Grenade NCS spawn paths (`grenade_gadget.*` / `*_grenade_gadget.*`) — dataset `category` is often `Gadget`. */
  function stxIsDatasetGrenadeGadgetSpawnCode(normLo){
    const c = String(normLo || '').toLowerCase();
    if (c.indexOf('grenade_gadget.') === 0) return true;
    if (c.indexOf('_grenade_gadget.') !== -1) return true;
    return false;
  }

  /** Dataset part row that belongs to grenade kits — never show in Heavy / weapon heavy pools. */
  function stxPartIsGrenadeKitDatasetPart(p){
    if (!p) return false;
    if (String(p.category || '').trim() === 'Grenade') return true;
    if (String(p.itemType || '').trim() === 'Grenade') return true;
    const c = String(normCode(p.code || '') || '').toLowerCase();
    if (c.includes('grenade_gadget')) return true;
    return !!stxIsDatasetGrenadeGadgetSpawnCode(c);
  }

  /**
   * Curated pearlescent rarity-id names (normalized: lowercase, alphanumeric only).
   * Pearl pip / aug art in rarity and related dropdowns is limited to these rows.
   */
  window.STX_PEARL_RARITY_ID_ALLOWLIST_NORM = {
    iigenburst: true,
    eagenburst: true,
    eigenburst: true,
    handcannon: true,
    handconnon: true,
    vestigialconflux: true,
    conflux: true,
    soulsurvivor: true,
    crazedearl: true,
    crowsourced: true,
    // Do NOT treat Vladof CrowdSourced / Midnight Defiance as pearlescent (that is a phosphene sniper).
    doeshot: true,
    doshot: true,
    shalashaska: true,
    jailbroken: true,
    jailbrokengatling: true,
    jailbrokenkatling: true,
    mercurious: true,
    mercury: true,
    fleabag: true,
    hairtrigger: true,
    herald: true,
    gomie: true,
    loomingconstable: true,
    looming: true,
    firestorm: true,
    firework: true,
    abyss: true,
    constable: true,
    screwstonian: true,
    screwed: true,
    screwstonian: true,
    parasite: true,
    solartemper: true,
    // Pearl main-barrel / curated list hints (same set as PEARL_WEAPON_MAINPART_HINTS, normalized).
    laserdisc: true,
    mercredi: true,
    bubbles: true,
    tankbuster: true,
    roulette: true,
    arctic: true,
    songbird: true,
    demo: true
  };

  /** Curated in-game titles for pearlescent rarity-id rows (keys = stxNormPearlAllowKey). */
  window.STX_PEARL_RARITY_DISPLAY_BY_NORM = {
    soulsurvivor: 'Soul Survivor',
    conflux: 'Conflux',
    crowsourced: 'Crow-Sourced',
    // Midnight Defiance is phosphene-only (not in pearl allowlist); keep display for rarity-id lookups.
    midnightdefiance: 'Midnight Defiance',
    crowdsourced: 'Midnight Defiance',
    crazedearl: 'Crazed Earl',
    eigenburst: 'Eigenburst',
    iigenburst: 'Eigenburst',
    eagenburst: 'Eigenburst',
    handcannon: 'Handcannon',
    handconnon: 'Handcannon',
    jailbroken: 'Jail-Broken Gatling',
    jailbrokengatling: 'Jail-Broken Gatling',
    jailbrokenkatling: 'Jail-Broken Gatling',
    mercurious: 'Mercurious',
    mercury: 'Mercurious',
    fleabag: 'Fleabag',
    hairtrigger: 'Hair Trigger',
    shalashaska: 'Shalashaska',
    gomie: 'Gomie',
    herald: 'Herald',
    loomingconstable: 'Constable',
    looming: 'Constable',
    firestorm: "Juliet's Sparkle",
    firework: "Juliet's Sparkle",
    juliet: "Juliet's Sparkle",
    vestigialconflux: 'Conflux',
    doeshot: 'Doeshot',
    doshot: 'Doeshot',
    laserdisc: 'Laserdisc',
    mercredi: 'Mercredi',
    bubbles: 'Bubbles',
    tankbuster: 'Tankbuster',
    roulette: 'Roulette',
    arctic: 'Arctic',
    songbird: 'Songbird',
    demo: 'Demo',
    ohmigot: 'Ohm I Got',
    abyss: 'Abyss',
    constable: 'Constable',
    screwstonian: 'Screwstonian',
    screwed: 'Screwstonian',
    parasite: 'Parasite',
    solartemper: 'Solar Temper',
    temper: 'Solar Temper'
  };

  function stxNormPearlAllowKey(s){
    return String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  function stxHumanizeLegendToken(tok){
    const t = String(tok || '').trim();
    if (!t) return '';
    if (/^0?\d{1,2}$/.test(t)) return '';
    const spaced = t.replace(/_/g, ' ').replace(/([a-z0-9])([A-Z])/g, '$1 $2');
    return spaced.replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function stxRarityIdHumanTitleForPart(p){
    if (!p) return '';
    /* Class-mod: prefer mapped DLC/raid names; never surface Raid3/Harmonica stubs. */
    try {
      const code0 = String(normCode(p.code || '') || '').toLowerCase();
      const isCm = /classmod_/.test(code0)
        || /class\s*mod/i.test(String(p.category || ''))
        || /class\s*mod/i.test(String(p.itemType || ''));
      if (isCm) {
        if (typeof stxIsClassModUnnamedLegendaryStub === 'function' && stxIsClassModUnnamedLegendaryStub(p)) return '';
        const mapped = typeof stxResolveClassModPartDisplayName === 'function'
          ? String(stxResolveClassModPartDisplayName(p) || '').trim()
          : '';
        if (mapped) return mapped;
      }
    } catch (_e) {}
    const map = window.STX_PEARL_RARITY_DISPLAY_BY_NORM;
    const eff0 = String(p.effects || p.effect || '').split(/\s*-\s*/)[0].trim();
    if (eff0 && eff0.length <= 64 && !/^(use |\+|reload|damage|\d)/i.test(eff0)){
      const ek = stxNormPearlAllowKey(eff0);
      if (map && map[ek]) return stxStripRarityIdSkinDisplaySuffix(map[ek]);
      if (/^(raid\s*[34]|raid[34]|harmonica)$/i.test(eff0.replace(/[\s_-]+/g, ' ').trim())) {
        /* fall through — do not use stub effect text as title */
      } else if (eff0.length <= 40) {
        return stxStripRarityIdSkinDisplaySuffix(eff0);
      }
    }
    const nameHead = stxStripLegendaryRarityDisplayPrefix(String(p.name || '').split(/\s*-\s*/)[0]);
    const tryKeys = [
      stxRarityLegendTokenFromPart(p),
      stxNormPearlAllowKey(eff0),
      stxNormPearlAllowKey(nameHead)
    ];
    for (let i = 0; i < tryKeys.length; i++){
      const k = tryKeys[i];
      if (k && map && map[k]) return stxStripRarityIdSkinDisplaySuffix(map[k]);
    }
    if (nameHead && !/^comp_0[56]_/i.test(nameHead) && nameHead.length <= 72) {
      if (/^(raid\s*[34]|raid[34]|harmonica)$/i.test(nameHead.replace(/[\s_-]+/g, ' ').trim())) return '';
      return stxStripRarityIdSkinDisplaySuffix(nameHead);
    }
    const hum = stxHumanizeLegendToken(stxRarityLegendTokenFromPart(p));
    if (hum && !/^(raid\s*[34]|harmonica)$/i.test(hum)) return stxStripRarityIdSkinDisplaySuffix(hum);
    const spawnFallback = spawnSegmentFromNormCode(normCode(p.code || '')) || '';
    if (/raid\s*[34]|harmonica/i.test(spawnFallback)) return '';
    return stxStripRarityIdSkinDisplaySuffix(spawnFallback);
  }
  try { window.stxRarityIdHumanTitleForPart = stxRarityIdHumanTitleForPart; } catch (_e) {}

  function stxApplyPearlGearCatalogLookups(){
    const cat = window.STX_PEARL_GEAR_CATALOG;
    if (!cat || !cat.byNorm) return;
    const allow = window.STX_PEARL_RARITY_ID_ALLOWLIST_NORM;
    const disp = window.STX_PEARL_RARITY_DISPLAY_BY_NORM;
    for (const [k, row] of Object.entries(cat.byNorm)){
      if (!row || !row.isPearlescent) continue;
      if (allow) allow[k] = true;
      if (row.name && disp) disp[k] = row.name;
      const tokens = row.spawnTokens || [];
      for (let i = 0; i < tokens.length; i++){
        const tk = stxNormPearlAllowKey(tokens[i]);
        if (!tk) continue;
        if (allow) allow[tk] = true;
        if (row.name && disp) disp[tk] = row.name;
      }
    }
  }

  function stxLegendTailTokenFromDisplayName(nm) {
    const s = String(nm || '').trim();
    if (!s) return '';
    const m = s.match(/(?:^|\s)([A-Za-z][A-Za-z0-9_'-]*)\s*$/);
    if (!m) return '';
    if (/^(barrel|body|part|legendary|comp|magazine|scope|grip|stock|accessory)$/i.test(m[1])) return '';
    return stxNormPearlAllowKey(m[1]);
  }

  function stxPearlGearCatalogRowForPart(p){
    if (!p) return null;
    const cat = window.STX_PEARL_GEAR_CATALOG && window.STX_PEARL_GEAR_CATALOG.byNorm;
    if (!cat) return null;
    const keys = [
      stxRarityLegendTokenFromPart(p),
      stxNormPearlAllowKey(String(p.effects || p.effect || '').split(/\s*-\s*/)[0]),
      stxNormPearlAllowKey(stxStripLegendaryRarityDisplayPrefix(String(p.name || '').split(/\s*-\s*/)[0]))
    ];
    const barrelTok = typeof stxBarrelPearlLegendTokenFromPart === 'function' ? stxBarrelPearlLegendTokenFromPart(p) : '';
    if (barrelTok) keys.push(barrelTok);
    const nameTail = stxLegendTailTokenFromDisplayName(p.name || p.legendaryName);
    if (nameTail) keys.push(nameTail);
    for (let i = 0; i < keys.length; i++){
      const k = keys[i];
      if (k && cat[k]) return cat[k];
    }
    return null;
  }

  /** Red text / ability / drop source from gear database (pearls + documented raid rows). */
  function stxCatalogFlavorLineForPart(p){
    const row = stxPearlGearCatalogRowForPart(p);
    if (!row) return '';
    const bits = [];
    if (row.redText) bits.push(`"${row.redText}"`);
    if (row.ability) bits.push(row.ability);
    if (row.source && !String(row.ability || '').includes(row.source)) bits.push(`Source: ${row.source}`);
    return bits.join(' — ');
  }
  try { window.stxCatalogFlavorLineForPart = stxCatalogFlavorLineForPart; } catch (_e) {}

  function stxRarityLegendTokenFromPart(p){
    if (!p) return '';
    const code = normCode(p.code || p.spawnCode || p.importCode || '').toLowerCase();
    const i = code.indexOf('comp_05_legendary_');
    if (i !== -1) return stxNormPearlAllowKey(code.slice(i + 'comp_05_legendary_'.length));
    return '';
  }

  function stxPartIsExplicitPearlescentComp(p){
    if (!p) return false;
    const code = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
    const its = String(p.itemTypeString || '').toLowerCase();
    const pt = String(p.partType || '').trim().toLowerCase();
    if (/(?:^|[._])comp_06_pearlescent|comp_06_pearl_/.test(code)) return true;
    /* itemTypeString "pearlescent" only counts on rarity/comp rows — not barrels/mags that mention pearls. */
    if (/\bpearlescent\b/.test(its) && (pt === 'rarity' || /comp_0[1-6]_/.test(code) || /comp_06_/.test(its))) return true;
    if (/\bpearl_(?:damage|reload|firerate|handling|normal|shock|radiation|corrosive|cryo|fire|sonic)\b/.test(its)) return true;
    // Pearl rarity numeric ids 51–60 only on rarity/comp rows (not classmod Name+Skin like Windrider).
    const item = Number((p.itemId != null) ? p.itemId : p.id);
    if (Number.isFinite(item) && item >= 51 && item <= 60) {
      if (pt === 'rarity' || /comp_0[1-6]_/.test(code) || /part_pearl/.test(code) || /\bpearl_/.test(its)) return true;
    }
    return false;
  }

  /** True for pearl element parts (`part_pearl_elem_*`). */
  function stxPartIsPearlElementPart(p){
    if (!p) return false;
    if (typeof weaponPearlElemPartMatch === 'function' && weaponPearlElemPartMatch(p)) return true;
    const code = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
    return /part_pearl_elem/i.test(code);
  }
  try { window.stxPartIsPearlElementPart = stxPartIsPearlElementPart; } catch (_e) {}

  /** Pearl rarity-ID picker rows only (not barrels, mags, classmod names, etc.). */
  function stxPartIsPearlRarityIdPart(p){
    if (!p) return false;
    if (stxPartIsPearlElementPart(p)) return false;
    if (stxPartIsExplicitPearlescentComp(p)) return true;
    if (!isStxRarityIdCompIconPart(p)) return false;
    const code = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
    if (/part_pearl/i.test(code) && !/comp_/.test(code)) return false;
    if (/comp_06_pearlescent|comp_06_pearl_/.test(code)) return true;
    if (/comp_05_legendary/.test(code) && typeof stxPartMatchesPearlRarityIdAllowlist === 'function' && stxPartMatchesPearlRarityIdAllowlist(p)) return true;
    return false;
  }
  try { window.stxPartIsPearlRarityIdPart = stxPartIsPearlRarityIdPart; } catch (_e) {}

  /** Barrel/body code suffix token (e.g. `part_barrel_02_eigenburst` → `eigenburst`). */
  function stxBarrelPearlLegendTokenFromPart(p){
    if (!p) return '';
    const fromComp = stxRarityLegendTokenFromPart(p);
    if (fromComp) return fromComp;
    const code = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
    let m = code.match(/part_(?:barrel|body)_\d+_([a-z0-9_]+)$/);
    if (m) return stxNormPearlAllowKey(m[1]);
    m = code.match(/part_(?:barrel|body)_(?:\d+[a-z]_)([a-z0-9_]+)$/);
    if (m) return stxNormPearlAllowKey(m[1]);
    return '';
  }
  try { window.stxBarrelPearlLegendTokenFromPart = stxBarrelPearlLegendTokenFromPart; } catch (_e) {}

  /**
   * Pearlescent rarity-id rows: `comp_06_*`, pearl item ids 51–60, or curated `comp_05_legendary_<token>`.
   * Does not treat every part whose display name says "Legendary" as pearl.
   */
  function stxPartMatchesPearlRarityIdAllowlist(p){
    const allow = window.STX_PEARL_RARITY_ID_ALLOWLIST_NORM;
    if (!p || !allow) return false;
    if (stxPartIsExplicitPearlescentComp(p)) return true;

    const code = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
    const compTok = stxRarityLegendTokenFromPart(p);
    if (compTok && allow[compTok] && /comp_05_legendary/.test(code)) return true;

    const barrelTok = stxBarrelPearlLegendTokenFromPart(p);
    if (barrelTok && allow[barrelTok] && /\.part_(?:barrel|body)_/.test(code)) return true;

    if (isStxRarityIdCompIconPart(p)) {
      const eff0 = String(p.effects || p.effect || '').split(/\s*-\s*/)[0];
      if (eff0 && allow[stxNormPearlAllowKey(eff0)]) return true;
      if (/comp_05_legendary/.test(code)) {
        const n0 = String(p.name || '').split(/\s*-\s*/)[0];
        if (n0 && allow[stxNormPearlAllowKey(n0)]) return true;
      }
    }
    return false;
  }
  try { window.stxPartMatchesPearlRarityIdAllowlist = stxPartMatchesPearlRarityIdAllowlist; } catch (_e) {}

  try { stxApplyPearlGearCatalogLookups(); } catch (_e) {}

  function stxPearlSlotIconUrlForPart(p, schemaItem){
    try{
      const ctx = stxCompIconContext();
      const pfn = stxPearlSlotIconFilenameFromContext(ctx);
      if (pfn) return STX_CC_PEARL_ITEMTYPE_BASE + pfn;
    }catch(_e){}
    return STX_CC_PEARL_ITEMTYPE_BASE + 'ico_misc_pearl.png';
  }

  /** Pearl pip only on pearl rarity-ID rows and pearl element parts — never barrels/mags/classmod names. */
  function stxPartUsesPearlRarityBarrelIcon(p, schemaItem){
    if (!p) return false;
    if (stxPartIsPearlElementPart(p)) return true;
    if (stxPartIsPearlRarityIdPart(p)) return true;
    return false;
  }
  try { window.stxPartUsesPearlRarityBarrelIcon = stxPartUsesPearlRarityBarrelIcon; } catch (_e) {}

  /** `(Pearl)` suffix only on pearl rarity-ID parts and pearl element parts. */
  function stxPartQualifiesForPearlUiLabel(p){
    if (!p) return false;
    if (stxPartIsPearlElementPart(p)) return true;
    if (stxPartIsPearlRarityIdPart(p)) return true;
    return false;
  }
  try { window.stxPartQualifiesForPearlUiLabel = stxPartQualifiesForPearlUiLabel; } catch (_e) {}


  /**
   * Manufacturer repair-kit TypeIDs (from rarity comps). Body rows often ship with bare
   * `idRaw: "2"` and no family — packing `{2}` makes the kit show as a naked "Stim"/etc.
   */
  const STX_REPKIT_MFR_FAMILY = {
    bor: 274,
    dad: 277,
    jak: 265,
    mal: 266,
    ord: 285,
    ted: 290,
    tor: 261,
    vla: 269,
  };

  function stxRepkitManufacturerFamilyFromCode(codeNormLo){
    const c = String(codeNormLo || '').toLowerCase();
    const m = c.match(/^([a-z0-9]+)_repair_kit\./);
    if (!m) return NaN;
    const fam = STX_REPKIT_MFR_FAMILY[m[1]];
    return Number.isFinite(fam) ? Number(fam) : NaN;
  }

  /** Emit `{fam:id}` / `{id}` style token when dataset metadata allows; else ''. */
  function numericTokenFromPart(p){
    if (!p) return '';
    var raw = String((p.idRaw ?? p.id ?? '') || '').trim();
    if (/^\d+\s*:\s*\d+$/.test(raw)){
      var parts = raw.split(':');
      var fam = String(parts[0]).trim();
      var idn = String(parts[1]).trim();
      return `{${fam}:${idn}}`;
    }
    if (/^\d+$/.test(raw)) {
      // If a part only has a bare numeric id (no family in idRaw), infer the family from the part object.
      // Critical for Repkit-style packed pools (e.g. family 243 arrays) where a part may otherwise serialize as `{73}`
      // instead of `{243:73}`, causing the item to fail to load in-game.
      try{
        const baseFam = stxBaseFamilyIdForCompactIds();
        const partFam = Number(p.family != null ? p.family : (p.familyId != null ? p.familyId : NaN));
        if (Number.isFinite(baseFam) && Number.isFinite(partFam) && partFam !== baseFam) {
          return `{${partFam}:${raw}}`;
        }
        // If the part doesn't expose family metadata, infer from known shared-pool code prefixes.
        // Repkits frequently source most tail parts from the shared `repair_kit.*` pool (family 243).
        if (!Number.isFinite(partFam)) {
          const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
          const cmVFam = stxClassModSpawnCodeVaultFamilyId(c);
          if (Number.isFinite(cmVFam)) {
            return `{${cmVFam}:${raw}}`;
          }
          // Shared numeric pools (dataset rows often omit `family` — qualify by spawn-code prefix).
          // Keep `repair_kit.` at string index 0 only: manufacturer kits use `jak_repair_kit.` etc.
          if (c.indexOf('repair_kit.') === 0) {
            return `{243:${raw}}`;
          }
          const rkFam = stxRepkitManufacturerFamilyFromCode(c);
          if (Number.isFinite(rkFam)) {
            return `{${rkFam}:${raw}}`;
          }
          if (c.indexOf('heavy_weapon_gadget.') === 0) {
            return `{244:${raw}}`;
          }
          if (c.startsWith('classmod.')) {
            return `{234:${raw}}`;
          }
          // Universal Enhancement rows (body tiers, stats, firmware dupes) live under family 247.
          if (c.startsWith('enhancement.')) {
            return `{247:${raw}}`;
          }
          if (c.startsWith('armor_shield.')) {
            return `{237:${raw}}`;
          }
          if (c.startsWith('energy_shield.')) {
            return `{248:${raw}}`;
          }
          if (c.startsWith('shield.part_')) {
            return `{246:${raw}}`;
          }
          // Weapon element / Maliwan secondary pools use TypeID 1 in the dataset.
          if (c.startsWith('weapon.part_')) {
            return `{1:${raw}}`;
          }
          // Grenade shared pools (stats/augments/elements) live under `grenade_gadget.*` and belong to family 245.
          if (c.indexOf('grenade_gadget.') === 0) {
            return `{245:${raw}}`;
          }
          // Enhancement manufacturer cores are split by prefix, but some rows are missing family metadata.
          // Infer TypeID from STX_RARITIES based on prefix (atl_enhancement, cov_enhancement, etc.).
          const enhM = c.match(/^([a-z]{3})_enhancement\./);
          if (enhM && enhM[1]) {
            const m3 = enhM[1];
            const mfr =
              (m3 === 'atl') ? 'Atlas' :
              (m3 === 'cov') ? 'COV' :
              (m3 === 'dad') ? 'Daedalus' :
              (m3 === 'hyp') ? 'Hyperion' :
              (m3 === 'jak') ? 'Jakobs' :
              (m3 === 'mal') ? 'Maliwan' :
              (m3 === 'ord') ? 'Order' :
              (m3 === 'bor') ? 'Ripper' :
              (m3 === 'ted') ? 'Tediore' :
              (m3 === 'tor') ? 'Torgue' :
              (m3 === 'vla') ? 'Vladof' :
              '';
            if (mfr) {
              try{
                const rr = (Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : (typeof STX_RARITIES !== 'undefined' ? STX_RARITIES : [])) || [];
                const row = rr.find(r => String(r && r.itemType || '').trim() === 'Enhancement' && String(r && r.manufacturer || '').trim() === mfr);
                const famInf = row ? Number(r && row.familyId) : NaN;
                if (Number.isFinite(famInf)) return `{${famInf}:${raw}}`;
              }catch(_e){}
            }
          }
          // Manufacturer-scoped tails: qualify with the selected item's base family when metadata is missing.
          if (Number.isFinite(baseFam)) {
            if (/[a-z0-9]+_repair_kit\./.test(c)) {
              return `{${baseFam}:${raw}}`;
            }
            if (/[a-z0-9]+_shield\./.test(c)) {
              return `{${baseFam}:${raw}}`;
            }
            if (c.indexOf('_grenade_gadget.') !== -1) {
              return `{${baseFam}:${raw}}`;
            }
            // Weapons / shields / generic manufacturer gear: `TED_PS.part_*`, `MAL_HW.part_*`, `dad_shield.part_*`, etc.
            if (/^[a-z]{3}_[a-z0-9]+\.part_/i.test(c)) {
              return `{${baseFam}:${raw}}`;
            }
          }
        }
      }catch(_e){}
      return `{${raw}}`;
    }
    if (/^\d+\s*:\s*\[[^\]]+\]$/.test(raw)) return `{${raw.replace(/\s+/g, ' ').trim()}}`;
    if (/^\{.*\}$/.test(raw)) return raw;
    var fam2 = p.family != null ? String(p.family) : (p.familyId != null ? String(p.familyId) : '');
    var id2 = p.id != null ? String(p.id) : (p.itemId != null ? String(p.itemId) : '');
    if (/^\d+$/.test(fam2) && /^\d+$/.test(id2)) return `{${fam2}:${id2}}`;
    if (/^\d+$/.test(id2)) {
      if (!String(fam2).trim()) return `{${id2}}`;
      // If family is non-numeric but id is numeric, we might still want to return just {id}
      // if it's considered a "top-level" part without a defined family.
      return `{${id2}}`;
    }
    return '';
  }

  /**
   * Family TypeID for rows whose idRaw is a bare number — matches `numericTokenFromPart` pool rules
   * (repair_kit → 243, weapon.part_ → 1, manufacturer parts + baseFam, etc.).
   */
  function stxInferredFamilyNumberForPackedPoolPart(p){
    if (!p) return NaN;
    try{
      const partFam = Number(p.family != null ? p.family : (p.familyId != null ? p.familyId : NaN));
      if (Number.isFinite(partFam)) return partFam;
      const baseFam = stxBaseFamilyIdForCompactIds();
      const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
      if (c.indexOf('repair_kit.') === 0) return 243;
      const rkFam0 = stxRepkitManufacturerFamilyFromCode(c);
      if (Number.isFinite(rkFam0)) return rkFam0;
      if (c.indexOf('heavy_weapon_gadget.') === 0) return 244;
      const cmInf = stxClassModSpawnCodeVaultFamilyId(c);
      if (Number.isFinite(cmInf)) return cmInf;
      if (c.startsWith('classmod.')) return 234;
      if (c.startsWith('enhancement.')) return 247;
      if (c.startsWith('armor_shield.')) return 237;
      if (c.startsWith('energy_shield.')) return 248;
      if (c.startsWith('shield.part_')) return 246;
      if (c.startsWith('weapon.part_')) return 1;
      if (c.indexOf('grenade_gadget.') === 0) return 245;
      const enhM = c.match(/^([a-z]{3})_enhancement\./);
      if (enhM && enhM[1]){
        const m3 = enhM[1];
        const mfr =
          (m3 === 'atl') ? 'Atlas' :
          (m3 === 'cov') ? 'COV' :
          (m3 === 'dad') ? 'Daedalus' :
          (m3 === 'hyp') ? 'Hyperion' :
          (m3 === 'jak') ? 'Jakobs' :
          (m3 === 'mal') ? 'Maliwan' :
          (m3 === 'ord') ? 'Order' :
          (m3 === 'bor') ? 'Ripper' :
          (m3 === 'ted') ? 'Tediore' :
          (m3 === 'tor') ? 'Torgue' :
          (m3 === 'vla') ? 'Vladof' :
          '';
        if (mfr){
          try{
            const rr = (Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : (typeof STX_RARITIES !== 'undefined' ? STX_RARITIES : [])) || [];
            const row = rr.find(r => String(r && r.itemType || '').trim() === 'Enhancement' && String(r && r.manufacturer || '').trim() === mfr);
            const famInf = row ? Number(row && row.familyId) : NaN;
            if (Number.isFinite(famInf)) return famInf;
          }catch(_e){}
        }
      }
      if (Number.isFinite(baseFam)){
        if (/[a-z0-9]+_repair_kit\./.test(c)) return baseFam;
        if (/[a-z0-9]+_shield\./.test(c)) return baseFam;
        if (c.indexOf('_grenade_gadget.') !== -1) return baseFam;
        if (/^[a-z]{3}_[a-z0-9]+\.part_/i.test(c)) return baseFam;
      }
    }catch(_e){}
    return NaN;
  }

  /**
   * Vault-hunter TypeID from class-mod spawn code. `classmod_paladin.*` must not match the blanket `classmod.` → 234
   * shared-pool rule (that was emitting cross-VH rows as `{234:n}` then bare `{n}`).
   */
  function stxClassModSpawnCodeVaultFamilyId(code){
    try{
      const c = String(normCode(code || '') || '').toLowerCase();
      if (!c) return NaN;
      const m1 = c.match(/^([a-z0-9]+)_classmod\./i);
      if (m1 && m1[1]){
        const k = String(m1[1] || '').replace(/[\s-]+/g, '').toLowerCase();
        const byPrefix = {
          vex:254, siren:254,
          amon:255, paladin:255,
          rafa:256, exosoldier:256, exo:256,
          harlowe:259, gravitar:259,
          c4sh:404, robodealer:404,
          loveless:402, corpohacker:402, hacker:402
        };
        const fam1 = Number(byPrefix[k]);
        if (Number.isFinite(fam1)) return fam1;
      }
      const m2 = c.match(/^classmod_([a-z0-9]+)\./i);
      if (m2 && m2[1]){
        const low = String(m2[1] || '').toLowerCase();
        if (low === 'universal' || low === 'firmware') return 234;
        const fam2 = classModFamilyIdForCharacter(String(m2[1]).replace(/_/g, ' '));
        if (Number.isFinite(fam2)) return fam2;
      }
      return NaN;
    }catch(_e){
      return NaN;
    }
  }

  /**
   * Dropdown dedupe key aligned with numeric serialization: merges `{8}` with `{284:8}` when the same pool applies.
   */
  function stxNumericTokenDedupeKey(p){
    if (!p || typeof p !== 'object') return '';
    try{
      const t = numericTokenFromPart(p);
      const m = String(t || '').match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
      if (m) return 'fid:' + Number(m[1]) + ':' + Number(m[2]);
      const m2 = String(t || '').match(/^\{\s*(\d+)\s*\}$/);
      if (m2){
        const id = Number(m2[1]);
        const fam = stxInferredFamilyNumberForPackedPoolPart(p);
        if (Number.isFinite(fam) && Number.isFinite(id)) return 'fid:' + fam + ':' + id;
        return 'bareid:' + id;
      }
      const id2 = Number(p.id != null ? p.id : (p.itemId != null ? p.itemId : NaN));
      const fam2 = Number(p.family != null ? p.family : (p.familyId != null ? p.familyId : NaN));
      if (Number.isFinite(fam2) && Number.isFinite(id2)) return 'fid:' + fam2 + ':' + id2;
      if (Number.isFinite(id2)){
        const famI = stxInferredFamilyNumberForPackedPoolPart(p);
        if (Number.isFinite(famI)) return 'fid:' + famI + ':' + id2;
        return 'bareid:' + id2;
      }
    }catch(_e){}
    return '';
  }

  function spawnTokenFromPart(p){
    if (!p) return '';
    const c = normCode(p.code || p.spawnCode || '');
    return c || '';
  }

  /** Default numeric `{fam:id}`; unchecked (spawn mode) uses spawn strings. Mutual fallback when one form is missing. */
  function tokenForPart(p){
    if (!p) return '';
    // IMPORTANT: Check for __importedToken FIRST.
    // If it's explicitly set to an empty string, it means this part should be skipped
    // (e.g., it was part of a bracketed group where another part took the bracket token).
    if (p.__importedToken != null) {
      const rawTok = String(p.__importedToken);
      if (rawTok === '') return '';
      if (state.idMode && state.detectedCategory === 'Shield'){
        const mImp = rawTok.match(/^\{\s*1\s*:\s*(\d+)\s*\}$/);
        const t1 = { 10: 22, 11: 23, 12: 24, 13: 25, 14: 26 };
        if (mImp && Number.isFinite(t1[Number(mImp[1])])){
          return `{246:${t1[Number(mImp[1])]}}`;
        }
      }
      return rawTok;
    }

    /* Class Mod: rarity + name/leg-effect rows must always serialize as `{TypeID:itemId}` so tails normalize to
     * truncated bare `{id}` after the header family; spawn-mode spawn strings here omit the name in output. */
    try {
      const itUi = String(state && state.itemType || '').trim();
      if (itUi === 'Class Mod' && p) {
        const ptLo = String(p.partType || '').trim().toLowerCase();
        if (ptLo === 'name+skin' || ptLo === 'rarity') {
          const numTok = numericTokenFromPart(p);
          if (numTok) return numTok;
        }
      }
    } catch (_eCmTok) {}

    // Use current builder mode (Numeric or Spawn)
    // If the part was NOT imported (manually added), we strictly follow idMode.
    let result = '';
    if (state.idMode){
      const n = numericTokenFromPart(p);
      // Strictly return numeric if it exists.
      if (n) result = String(n);
      // ONLY fallback to spawn if numeric is absolutely missing.
      else result = String(spawnTokenFromPart(p));
    } else {
      const s = spawnTokenFromPart(p);
      // Strictly return spawn if it exists.
      if (s) result = String(s);
      // ONLY fallback to numeric if spawn is absolutely missing.
      else result = String(numericTokenFromPart(p));
    }

    // Shields must use the Shield gadget pool (246) for elemental resist rows — not weapon TypeID `{1:n}`.
    try {
      if (state.idMode && state.detectedCategory === 'Shield' && p) {
        const cLo = String(normCode(p.code || p.spawnCode || '') || '').toLowerCase();
        const weaponElemTo246 = (
          cLo === 'weapon.part_corrosive' ? 22 :
          cLo === 'weapon.part_cryo' ? 23 :
          cLo === 'weapon.part_fire' ? 24 :
          cLo === 'weapon.part_radiation' ? 25 :
          cLo === 'weapon.part_shock' ? 26 : NaN
        );
        const type1To246 = { 10: 22, 11: 23, 12: 24, 13: 25, 14: 26 };
        let id246 = Number.isFinite(weaponElemTo246) ? weaponElemTo246 : NaN;
        if (!Number.isFinite(id246)){
          const mm = String(result || '').match(/^\{\s*1\s*:\s*(\d+)\s*\}$/);
          if (mm) id246 = type1To246[Number(mm[1])];
        }
        if (Number.isFinite(id246)){
          result = `{246:${id246}}`;
        }
      }
    } catch (_e) {}

    // Critical safety: never emit bare "{id}" for parts that are NOT from the base family.
    // Also: Firmware should always be emitted as "{TypeID:ID}" when possible.
    try {
      if (/^\{\s*\d+\s*\}$/.test(String(result || ''))) {
        const ptLo = String(p.partType || '').trim().toLowerCase();
        const isFirmware = ptLo === 'firmware' || /part_firmware/i.test(String(p.code || p.spawnCode || ''));

        const base = typeof getSelectedBaseItem === 'function' ? getSelectedBaseItem() : null;
        const baseFam = Number(base && base.familyId);
        const partFam = Number(p.family != null ? p.family : (p.familyId != null ? p.familyId : NaN));
        const idNum = Number(String(result).replace(/[^\d]/g, ''));

        const needExplicitFamily = isFirmware || (Number.isFinite(baseFam) && Number.isFinite(partFam) && partFam !== baseFam);
        if (needExplicitFamily && Number.isFinite(partFam) && Number.isFinite(idNum)) {
          result = `{${partFam}:${idNum}}`;
        }
      }
    } catch (_e) {}

    return (result === '[object Object]') ? '' : result;
  }

  function parseIdToken(tok){
    const s = String(tok || '').trim();
    if (!s) return null;

    let m = s.match(/^\{\s*(\d+)\s*\}$/);
    if (m){
      return { kind:'id', id: Number(m[1]) };
    }

    m = s.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
    if (m){
      return { kind:'family', family: Number(m[1]), ids: [Number(m[2])] };
    }

    m = s.match(/^\{\s*(\d+)\s*:\s*\[([^\]]+)\]\s*\}$/);
    if (m){
      const idsStr = String(m[2] || '');
      // Match all numbers separated by spaces or commas
      const ids = idsStr.match(/\d+/g);
      const list = (ids || []).map(n => Number(n)).filter(n => Number.isFinite(n));
      if (!list.length) return null;
      // Also return the raw bracketed string to allow preserving it
      return { kind:'family', family: Number(m[1]), ids: list, rawIds: m[2] };
    }

    return null;
  }

  function normalizeIdTokensForBaseFamily(tokens, baseFamily, opts){
    const src = Array.isArray(tokens) ? tokens : [];
    const out = [];
    const bf = Number(baseFamily);
    const hasBase = Number.isFinite(bf);
    const compactSame = !(opts && opts.compactSameFamily === false);

    for (const tok of src) {
        const parsed = parseIdToken(tok);
        if (parsed && parsed.kind === 'family' && parsed.rawIds) {
            // Check if it's foreign or if we are forced to keep bracketed form
            // The user wants NO shortening, and specifically mentioned {7:[4 4 4 4 64]} should show.
            out.push(tok);
            continue;
        }
        
        // Use existing expansion logic for others
        if (!parsed) {
            out.push(tok);
            continue;
        }
        
        if (parsed.kind === 'id') {
            if (compactSame && hasBase) out.push(`{${parsed.id}}`);
            else if (hasBase) out.push(`{${bf}:${parsed.id}}`);
            else out.push(`{${parsed.id}}`);
            continue;
        }

        const fam = Number(parsed.family);
        const ids = Array.isArray(parsed.ids) ? parsed.ids : [];
        if (hasBase && fam === bf && compactSame) {
            for (const id of ids) out.push(`{${id}}`);
        } else {
            for (const id of ids) out.push(`{${fam}:${id}}`);
        }
    }
    return out;
  }

  function normalizeIdTokensForBaseFamilyWithPrefs(tokens, baseFamily){
    /* Same TypeID as the item → bare `{id}` after `||`; different TypeID → `{fam:id}`. Applies to all categories (not gated on idMode). */
    const compactSame = !isForceTypeIdTokensEnabled();
    return normalizeIdTokensForBaseFamily(tokens, baseFamily, {
      compactSameFamily: compactSame
    });
  }

  // OLD VERSION kept for reference or removed if certain
  /*
  function normalizeIdTokensForBaseFamily_OLD(tokens, baseFamily, opts){
    const src = Array.isArray(tokens) ? tokens : [];
    const out = [];
    const bf = Number(baseFamily);
    const hasBase = Number.isFinite(bf);
    const compactSame = !(opts && opts.compactSameFamily === false);

    let pendingFamily = null;
    let pendingIds = [];

    const flushPending = () => {
      if (!Number.isFinite(pendingFamily) || !pendingIds.length) return;
      for (const pid of pendingIds){
        if (hasBase && pendingFamily === bf && compactSame) out.push(`{${pid}}`);
        else out.push(`{${pendingFamily}:${pid}}`);
      }
      pendingFamily = null;
      pendingIds = [];
    };

    for (const tok of src){
      const parsed = parseIdToken(tok);
      if (!parsed){
        flushPending();
        out.push(tok);
        continue;
      }

      if (parsed.kind === 'id'){
        flushPending();
        if (compactSame && hasBase){
          out.push(`{${parsed.id}}`);
        } else if (hasBase){
          out.push(`{${bf}:${parsed.id}}`);
        } else {
          out.push(`{${parsed.id}}`);
        }
        continue;
      }

      const fam = Number(parsed.family);
      const ids = Array.isArray(parsed.ids) ? parsed.ids.filter(n => Number.isFinite(Number(n))).map(n => Number(n)) : [];
      if (!Number.isFinite(fam) || !ids.length){
        flushPending();
        out.push(tok);
        continue;
      }

      // If it has rawIds (bracketed), and it's a foreign family, we can preserve the bracketed form if it's already one
      if (parsed.rawIds && fam !== bf) {
          flushPending();
          out.push(tok);
          continue;
      }

      if (hasBase && fam === bf){
        flushPending();
        if (compactSame){
          for (const id of ids) out.push(`{${id}}`);
        } else {
          for (const id of ids) out.push(`{${bf}:${id}}`);
        }
        continue;
      }

      // Foreign-family ids stay family-qualified; merge consecutive same-family tokens.
      if (Number.isFinite(pendingFamily) && pendingFamily === fam){
        pendingIds.push(...ids);
      } else {
        flushPending();
        pendingFamily = fam;
        pendingIds = ids.slice();
      }
    }
    flushPending();
    return out;
  }
  */

  function displayForPart(p){
    if (!p) return '-';

    // Prefer the same labels the main page uses (names + stat summaries) only for Weapon/Character/Class Mod.
    const __allowParentLabels = (state.itemType === 'Weapon' || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType));
    const pl = __allowParentLabels ? parentLabelForPart(p) : null;
    let out;
    if (pl){
      out = pl;
    } else {
      const base = (p.name && String(p.name).trim()) ? String(p.name).trim() : normCode(p.code);
      out = base;
    }

    // Always surface numeric IDs in labels so users can see the full TypeID/ID even when inserting spawn codes.
    const id = String(p.idRaw ?? p.id ?? '').trim();
    const fullTok = (()=>{
      const fam = partFamilyIdOf(p);
      const item = partItemIdOf(p);
      if (Number.isFinite(fam) && Number.isFinite(item)) return `{${Number(fam)}:${Number(item)}}`;
      const baseFam = stxBaseFamilyIdForCompactIds();
      if (Number.isFinite(baseFam) && Number.isFinite(item)) return `{${Number(baseFam)}:${Number(item)}}`;
      return '';
    })();
    const want = fullTok || id;
    if (want && !String(out).includes(want)) out = `${out}  (id: ${want})`;

    // Repkit placeholder rows: make them meaningful instead of showing "PLACEHOLDER".
    try{
      const cat = String(p.category || '').trim().toLowerCase();
      const nmU = String(p.name || '').trim().toUpperCase();
      const codeN = String(normCode(p.code) || '').trim();
      if (cat === 'repkit' && nmU === 'PLACEHOLDER' && !codeN){
        const ef = String(p.effects ?? p.effect ?? '').toLowerCase();
        const suffix = ef.includes('primary perk') ? 'Primary perk' : (ef.includes('secondary perk') ? 'Secondary perk' : 'Perk');
        out = out.replace(/PLACEHOLDER/i, `None (${suffix})`);
      }
    }catch(_e){}

    if (stxPartQualifiesForPearlUiLabel(p) && out.indexOf('(Pearl)') === -1) out = out + ' (Pearl)';
    const ef = String(p.effects ?? p.effect ?? '').trim();
    const catFlavor = stxCatalogFlavorLineForPart(p);
    if (catFlavor && (stxPartQualifiesForPearlUiLabel(p) || isStxRarityIdCompIconPart(p))) {
      out = out + ' — ' + (catFlavor.length > 120 ? catFlavor.slice(0, 119) + '…' : catFlavor);
    } else if (ef) out = out + ' — ' + (ef.length > 50 ? ef.slice(0, 49) + '…' : ef);
    return out;
  }

  // Verbose labels for dropdowns: show in-game name, id, spawn code, stats, and effects (red text).
  function dropdownLabelForPart(p){
    if (!p) return '-';
    const rawCode = normCode(p.code);
    let name = (p.name && String(p.name).trim()) ? String(p.name).trim() : rawCode;
    const id = String(p.idRaw ?? p.id ?? '').trim();
    const statsRaw = (p.stats != null) ? String(p.stats) : '';
    const stats = statsRaw.replace(/\s+/g,' ').trim();
    const ef = String(p.effects ?? p.effect ?? '').trim();
    if (ef) name = name + ' — ' + (ef.length > 45 ? ef.slice(0, 44) + '…' : ef);

    const chunks = [];
    if (id) chunks.push(`ID: ${id}`);
    if (rawCode) chunks.push(`Code: ${rawCode}`);
    if (stats) chunks.push(`Stats: ${stats}`);

    return chunks.length ? `${name} - ${chunks.join(' - ')}` : name;
  }

  /** Last segment of spawn path for readable part names in long dropdowns. */
  function spawnSegmentFromNormCode(rawCode){
    const c = String(rawCode || '').replace(/^["']|["']$/g, '').trim();
    if (!c) return '';
    const seg = c.indexOf('.') >= 0 ? c.slice(c.lastIndexOf('.') + 1) : c;
    return String(seg).replace(/^["']|["']$/g, '').trim();
  }

  /** Rarity-ID comp rows (#mainPart): human weapon title + id, not raw `comp_05_legendary_*` segment. */
  function dropdownLabelRarityIdCompPart(p){
    if (!p) return '-';
    let line = stxRarityIdHumanTitleForPart(p) || '-';
    const id = String(p.idRaw ?? p.idraw ?? p.id ?? '').trim();
    const fam = partFamilyIdOf(p);
    const item = partItemIdOf(p);
    let tok = '';
    if (Number.isFinite(fam) && Number.isFinite(item)) tok = `{${Number(fam)}:${Number(item)}}`;
    else {
      const baseFam = stxBaseFamilyIdForCompactIds();
      if (Number.isFinite(baseFam) && Number.isFinite(item)) tok = `{${Number(baseFam)}:${Number(item)}}`;
    }
    if (!tok && id){
      const idM = id.match(/^(\d+)\s*:\s*(\d+)\s*$/);
      if (idM) tok = `{${Number(idM[1])}:${Number(idM[2])}}`;
    }
    if (stxPartQualifiesForPearlUiLabel(p) && line.indexOf('(Pearl)') === -1) line += ' (Pearl)';
    if (tok && !line.includes(tok)) line = `${line} ${tok}`;
    else if (id && !line.includes(id)) line = `${line} ${id}`;
    if (line.length > 140) line = line.slice(0, 137) + '…';
    return line;
  }

  function dropdownLabelForMainPartList(p){
    return isStxRarityIdCompIconPart(p) ? dropdownLabelRarityIdCompPart(p) : dropdownLabelCompactForPart(p);
  }

  /** Short list label: single line; stats/long text live in tooltip + part preview. */
  function dropdownLabelCompactForPart(p){
    if (!p) return '-';
    if (typeof window.ccRichPartDropdownLabel === 'function'){
      try{
        const rich = String(window.ccRichPartDropdownLabel(p, 180) || '').trim();
        if (rich && rich !== '-') return rich;
      }catch(_e){}
    }
    const rawCode = normCode(p.code);
    const spawnSeg = spawnSegmentFromNormCode(rawCode);
    let datasetName = (p.name && String(p.name).trim()) ? String(p.name).trim() : '';
    let isCm = false;
    try {
      const catLo = String(p.category || p.itemType || '').toLowerCase();
      isCm = /class\s*mod/.test(catLo) || /classmod_/.test(String(rawCode || '').toLowerCase());
      if (isCm) {
        if (stxIsClassModUnnamedLegendaryStub(p)) return '-';
        const resolved = String(stxResolveClassModPartDisplayName(p) || '').trim();
        if (resolved) datasetName = resolved;
        else datasetName = '';
      }
    } catch (_e) {}

    // Repkit placeholder rows: make them meaningful instead of showing "PLACEHOLDER".
    try{
      const cat = String(p.category || '').trim().toLowerCase();
      const nmU = String(datasetName || '').trim().toUpperCase();
      const codeN = String(rawCode || '').trim();
      if (cat === 'repkit' && nmU === 'PLACEHOLDER' && !codeN){
        const ef = String(p.effects ?? p.effect ?? '').toLowerCase();
        const suffix = ef.includes('primary perk') ? 'Primary perk' : (ef.includes('secondary perk') ? 'Secondary perk' : 'Perk');
        datasetName = `None (${suffix})`;
      }
    }catch(_e){}

    const id = String(p.idRaw ?? p.idraw ?? p.id ?? '').trim();
    const fam = partFamilyIdOf(p);
    const item = partItemIdOf(p);
    let tok = '';
    if (Number.isFinite(fam) && Number.isFinite(item)) tok = `{${Number(fam)}:${Number(item)}}`;
    else {
      const baseFam = stxBaseFamilyIdForCompactIds();
      if (Number.isFinite(baseFam) && Number.isFinite(item)) tok = `{${Number(baseFam)}:${Number(item)}}`;
    }
    if (!tok && id){
      const idM = id.match(/^(\d+)\s*:\s*(\d+)\s*$/);
      if (idM) tok = `{${Number(idM[1])}:${Number(idM[2])}}`;
    }

    /* Class Mod: in-game name + numeric id only (never spawn-derived "Raid 3"). */
    if (isCm) {
      let line = datasetName || '';
      const tail = tok || (id && line.indexOf(id) === -1 ? id : '');
      if (tail && line.indexOf(tail) === -1) line = line ? `${line} · ${tail}` : tail;
      if (!line) line = tok || id || '-';
      if (line.length > 140) line = line.slice(0, 137) + '…';
      return line;
    }

    let primary = spawnSeg || (rawCode ? (rawCode.length <= 80 ? rawCode : rawCode.slice(0, 77) + '…') : '');
    if (!primary && datasetName) primary = datasetName.length > 80 ? datasetName.slice(0, 77) + '…' : datasetName;
    if (!primary) primary = id || '-';

    /* Bare `part_body` codes often ship with empty/useless names — surface a readable Body label. */
    if ((/^part_body$/i.test(spawnSeg) || /^part_body$/i.test(String(datasetName || '').trim())) && (!datasetName || /^part_body$/i.test(datasetName) || !String(datasetName).trim())) {
      const manHint = String(p.manufacturer || '').trim();
      const typeHint = String(p.itemType || p.weaponType || '').trim();
      primary = [manHint, typeHint, 'Body'].filter(Boolean).join(' ') || 'Body';
      datasetName = '';
    }

    const nameLc = datasetName.toLowerCase().replace(/[^a-z0-9]/g, '');
    const primLc = primary.toLowerCase().replace(/[^a-z0-9]/g, '');
    let line = primary;
    if (datasetName && nameLc !== primLc && !primLc.includes(nameLc) && datasetName.length <= 48){
      line = `${primary} — ${datasetName}`;
    }

    const tail = tok || (id && !line.includes(id) ? id : '');
    if (tail && !line.includes(tail)) line = `${line} ${tail}`;

    if (stxPartQualifiesForPearlUiLabel(p) && line.indexOf('(Pearl)') === -1) line += ' (Pearl)';

    if (line.length > 140) line = line.slice(0, 137) + '…';
    return line || rawCode || '-';
  }

  function barrelFamilyDropdownLabelCompact(p){
    // One line in list; flavor stays in getTitle / preview.
    return dropdownLabelCompactForPart(p);
  }

  function barrelFamilyOptionTitle(p){
    let base = '';
    try{
      if (typeof window.partTooltipText === 'function') base = String(window.partTooltipText(p) || '').trim();
    }catch(_){}
    const ef = String(p.effects ?? p.effect ?? p.effects_text ?? '').trim();
    if (ef && !base.includes(ef)) return base ? (base + ' | ' + ef) : ef;
    return base;
  }

  // ---- Parent dropdown label bridge (re-uses the same part lists/labels as the main page) ----
  const __PARENT_LABEL_CACHE = new Map();
  let __PARENT_LABEL_CACHE_AT = 0;

  function __normKey(s){
    if (s == null) return '';
    return String(s).trim();
  }

  function __cacheKeyVariants(raw){
    const out = [];
    const s = __normKey(raw);
    if (!s) return out;
    out.push(s);

    // Strip surrounding quotes
    if (s.startsWith('"') && s.endsWith('"') && s.length > 1) out.push(s.slice(1,-1));

    // Strip braces
    const unbraced = s.replace(/^\{\s*/, '').replace(/\s*\}$/, '');
    if (unbraced !== s){
      out.push(unbraced);
      out.push(`{${unbraced}}`);
    }

    return Array.from(new Set(out));
  }

  function rebuildParentLabelCache(){
    __PARENT_LABEL_CACHE.clear();
    __PARENT_LABEL_CACHE_AT = Date.now();

    try{
      const pd = (window.parent && window.parent.document) ? window.parent.document : null;
      if (!pd) return;

      const selects = pd.querySelectorAll('select');
      for (const sel of Array.from(selects)){
        for (const opt of Array.from(sel.options || [])){
          const v = __normKey(opt.value);
          const t = __normKey(opt.textContent);
          if (!v || !t) continue;

          for (const k of __cacheKeyVariants(v)){
            if (!__PARENT_LABEL_CACHE.has(k)) __PARENT_LABEL_CACHE.set(k, t);
          }

          // Also index labels by ids embedded in the text: "(id: X)".
          const m = t.match(/\(id:\s*([^\)]+)\)/i);
          if (m && m[1]){
            const id = __normKey(m[1]);
            for (const k of __cacheKeyVariants(id)){
              if (!__PARENT_LABEL_CACHE.has(k)) __PARENT_LABEL_CACHE.set(k, t);
            }
          }
        }
      }
    }catch(_e){}
  }

  function parentLabelForPart(p){
    try{
      if (state && state.itemType === 'Class Mod') return '';
      // Refresh occasionally in case the parent dropdowns were re-populated.
      if (!__PARENT_LABEL_CACHE.size || (Date.now() - __PARENT_LABEL_CACHE_AT) > 1500){
        rebuildParentLabelCache();
      }

      const keys = [];

      const id = __normKey(p.idRaw ?? p.id ?? '');
      if (id) keys.push(...__cacheKeyVariants(id));

      const codeRaw = __normKey(p.code ?? '');
      if (codeRaw) keys.push(...__cacheKeyVariants(codeRaw));
      const code = __normKey(normCode(codeRaw));
      if (code && code !== codeRaw) keys.push(...__cacheKeyVariants(code));

      for (const k of keys){
        if (__PARENT_LABEL_CACHE.has(k)) return __PARENT_LABEL_CACHE.get(k);
      }
    }catch(_e){}
    return '';
  }

  // Keep cache warm after load
  try{ setTimeout(rebuildParentLabelCache, 250); }catch(_e){}
function getAllParts(){
    return (window.STX_DATASET && Array.isArray(window.STX_DATASET.ALL_PARTS)) ? window.STX_DATASET.ALL_PARTS : [];
  }

  function unique(list){
    return Array.from(new Set(list.filter(Boolean)));
  }

  /**
   * Canonical vault-hunter manufacturer key for Class Mod rows.
   * Nexus/extract sometimes ships "Dark Siren" while the live editor uses "Siren" (UI: Vex).
   */
  function stxCanonicalClassModManufacturerKey(m){
    const lo = String(m || '').trim().toLowerCase().replace(/[\s_-]+/g, ' ');
    if (!lo) return '';
    if (lo === 'vex' || lo === 'siren' || lo === 'dark siren' || lo === 'darksiren') return 'siren';
    if (lo === 'amon' || lo === 'paladin' || lo === 'forge knight') return 'paladin';
    if (lo === 'rafa' || lo === 'exo soldier' || lo === 'exo-soldier' || lo === 'exosoldier') return 'exo soldier';
    if (lo === 'harlowe' || lo === 'gravitar') return 'gravitar';
    if (lo === 'c4sh' || lo === 'robodealer' || lo === 'robo dealer') return 'robodealer';
    if (lo === 'loveless' || lo === 'corpohacker' || lo === 'corpo hacker' || lo === 'hacker' || lo === 'the hacker') return 'corpohacker';
    if (lo === 'universal') return 'universal';
    return lo;
  }

  /** Collapse rarity-sheet / parts-list duplicates (e.g. COV vs Cov, bor→Ripper). */
  function stxCanonicalizeManufacturerDisplayName(m){
    const s = String(m || '').trim();
    if (!s) return s;
    const lo = s.toLowerCase();
    if (/^cov$/i.test(s) || /^children\s+of\s+the\s+vault$/i.test(s)) return 'COV';
    // Spawn-code prefixes that slipped into STX_RARITIES supplement rows.
    if (lo === 'bor' || lo === 'borg' || lo === 'rip') return 'Ripper';
    if (lo === 'dad' || lo === 'dae') return 'Daedalus';
    if (lo === 'jak') return 'Jakobs';
    if (lo === 'mal') return 'Maliwan';
    if (lo === 'ord') return 'Order';
    if (lo === 'ted') return 'Tediore';
    if (lo === 'tor') return 'Torgue';
    if (lo === 'vla') return 'Vladof';
    if (lo === 'atl') return 'Atlas';
    if (lo === 'hyp') return 'Hyperion';
    if (lo === 'classmod' || lo === 'class mod') return '';
    // Class Mod character aliases → stable internal family names (UI maps Siren→Vex, etc.).
    const cmKey = stxCanonicalClassModManufacturerKey(s);
    if (cmKey === 'siren') return 'Siren';
    if (cmKey === 'paladin') return 'Paladin';
    if (cmKey === 'exo soldier') return 'Exo Soldier';
    if (cmKey === 'gravitar') return 'Gravitar';
    if (cmKey === 'robodealer') return 'Robodealer';
    if (cmKey === 'corpohacker') return 'Corpohacker';
    if (cmKey === 'universal') return 'Universal';
    return s;
  }

  function isAllPartsEnabled(){
    return !!(state && state.allParts);
  }

  function stxSyncAllPartsToggleUi(checked){
    state.allParts = !!checked;
    try{
      const a = document.getElementById('allPartsToggle');
      const b = document.getElementById('ccGuidedAllManufacturers');
      if (a) a.checked = !!checked;
      if (b) b.checked = !!checked;
    }catch(_e){}
  }

  function isForceTypeIdTokensEnabled(){
    return !!(state && state.forceTypeIdTokens);
  }

  /** Lowercased join of fields used to infer comp tier (itemTypeString alone often omits `comp_*` from `code`). */
  function stxRarityTierBlobFromRow(row){
    if (!row || typeof row !== 'object') return '';
    return [
      row.itemTypeString,
      row.code,
      row.spawnCode,
      row.importCode,
      row.name,
      row.legendaryName,
      row.effects,
      row.effect
    ].map(x => String(x || '').trim()).filter(Boolean).join(' ').toLowerCase();
  }

  function rarityTierFromItemTypeString(s, rowHint){
    const row = (s && typeof s === 'object') ? s : rowHint;
    let t = '';
    if (s && typeof s === 'object'){
      t = stxRarityTierBlobFromRow(s);
    } else {
      const parts = [String(s || '')];
      if (rowHint && typeof rowHint === 'object'){
        const b = stxRarityTierBlobFromRow(rowHint);
        if (b) parts.push(b);
      }
      t = parts.join(' ');
    }
    t = String(t || '').toLowerCase();

    const item = Number(row && ((row.itemId != null) ? row.itemId : row.id));
    if (t.includes('comp_01_common')) return 0;
    if (t.includes('comp_02_uncommon')) return 1;
    if (t.includes('comp_03_rare')) return 2;
    if (t.includes('comp_04_epic')) return 3;
    if (/(?:^|[._])comp_06_pearlescent/.test(t) || /\bpearlescent\b/.test(t)) return 5;
    if (t.includes('comp_05_legendary') && row && typeof stxPartMatchesPearlRarityIdAllowlist === 'function' && stxPartMatchesPearlRarityIdAllowlist(row)) return 5;
    if (t.includes('comp_05_legendary')) return 4;
    if (t.includes('part_pearl')) return 5;
    if (/\bpearl_(?:normal|shock|radiation|corrosive|cryo|fire|sonic|damage|reload|firerate|handling)\b/.test(t)) return 5;

    // Pearl rarity IDs 51–60 only — never treat classmod Name+Skin rows (e.g. Windrider id 51) as pearl.
    if (Number.isFinite(item) && item >= 51 && item <= 60) {
      const pt = String((row && row.partType) || '').trim().toLowerCase();
      const code = String((row && (row.code || row.spawnCode)) || '').toLowerCase();
      const rarityLike =
        pt === 'rarity' ||
        /comp_0[1-6]_/.test(t) ||
        /comp_0[1-6]_/.test(code) ||
        /\bpearl_/.test(t) ||
        /part_pearl/.test(code);
      if (rarityLike) return 5;
    }
    return null;
  }

  function rarityTierLabel(t){
    switch (Number(t)){
      case 0: return 'Common';
      case 1: return 'Uncommon';
      case 2: return 'Rare';
      case 3: return 'Epic';
      case 4: return 'Legendary';
      case 5: return 'Pearlescent';
      default: return 'Unknown';
    }
  }

  function stxRarityTierFromPartForGrouping(p, manufacturerHint){
    if (!p) return null;
    const code = String(normCode(p && p.code || '') || '').toLowerCase();
    const fromCode = rarityTierFromItemTypeString(code, p);
    if (Number.isFinite(fromCode)) return fromCode;
    const item = partItemIdOf(p);
    if (Number.isFinite(item) && item >= 51 && item <= 60) return 5;
    const fam = partFamilyIdOf(p);
    if (!Number.isFinite(fam) || !Number.isFinite(item)) return null;
    const manL = String(manufacturerHint != null ? manufacturerHint : ((p && p.manufacturer) || '')).trim().toLowerCase();
    const table = Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : [];
    const tryRows = (requireMan)=>{
      for (let i = 0; i < table.length; i++){
        const r = table[i];
        if (typeof stxIsGrenKitStxRarityRow === 'function' && stxIsGrenKitStxRarityRow(r)) continue;
        if (Number(r.familyId) !== fam || Number(r.itemId) !== item) continue;
        if (requireMan && manL){
          const rm = String(r.manufacturer || '').trim().toLowerCase();
          if (rm && rm !== manL) continue;
        }
        const t = rarityTierFromItemTypeString(r.itemTypeString, r);
        if (Number.isFinite(t)) return t;
      }
      return null;
    };
    if (manL){
      const t0 = tryRows(true);
      if (Number.isFinite(t0)) return t0;
    }
    return tryRows(false);
  }

  function stxRarityOptgroupLabelFromPart(p, manufacturerHint){
    const t = stxRarityTierFromPartForGrouping(p, manufacturerHint);
    return Number.isFinite(t) ? rarityTierLabel(t) : 'Unknown';
  }

  function rarityTierFromValue(v){
    const s = String(v || '').trim().toLowerCase();
    if (!s) return null;
    if (/^\d+$/.test(s)){
      const n = Number(s);
      return (n >= 0 && n <= 5) ? n : null;
    }
    if (s === 'common') return 0;
    if (s === 'uncommon') return 1;
    if (s === 'rare') return 2;
    if (s === 'epic') return 3;
    if (s === 'legendary') return 4;
    if (s === 'pearlescent' || s === 'pearl') return 5;
    return null;
  }

  function parseRarityValue(v){
    const s = String(v || '').trim();
    if (!s) return null;

    // Preferred tier-only values used by STX/simple rarity dropdown.
    const tier = rarityTierFromValue(s);
    if (Number.isFinite(tier)) return { tier };

    // Backward compatibility for old "family|item" values.
    if (s.indexOf('|') !== -1){
      const [a,b] = s.split('|');
      const familyId = Number(String(a || '').trim());
      const itemId = Number(String(b || '').trim());
      if (!Number.isFinite(familyId) || !Number.isFinite(itemId)) return null;
      const row = (Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : [])
        .find(r => Number(r && r.familyId) === familyId && Number(r && r.itemId) === itemId);
      const rt = row ? rarityTierFromItemTypeString(row.itemTypeString, row) : null;
      return { tier: Number.isFinite(rt) ? rt : null, familyId, itemId };
    }
    return null;
  }

  function getSelectedRarityTier(){
    const parsed = parseRarityValue(
      (state && state.rarity) || (($('rarity') && $('rarity').value) ? $('rarity').value : '')
    );
    return (parsed && Number.isFinite(parsed.tier)) ? Number(parsed.tier) : null;
  }

  function categoryUsesRarityTierFilter(category){
    const c = String(category || '').trim().toLowerCase();
    return c === 'class mod' || c === 'classmod' || c === 'character';
  }

  function rarityTierFilterActiveForCurrentContext(){
    const catUi = stxNormalizeSimpleBuilderItemTypeUi(String(
      (state && state.itemType) ||
      (($('itemType') && $('itemType').value) ? $('itemType').value : '')
    ).trim());
    const cat = stxSimpleBuilderItemTypeIsHeavyUi(catUi) ? 'Weapon' : catUi;
    return categoryUsesRarityTierFilter(cat);
  }

  function refreshRarityUiState(){
    const sel = $('rarity');
    if (!sel) return;
    const active = rarityTierFilterActiveForCurrentContext();
    /* Hide only the rarity tier control, not sibling item level (#stxRarityTierWrap on index; else parent of #rarity e.g. embed column). */
    const rarityWrap = document.getElementById('stxRarityTierWrap') || sel.parentElement || null;
    const rarityLabel = document.querySelector('label[for="rarity"]');
    if (rarityLabel){
      rarityLabel.textContent = active ? 'Rarity Filter' : 'Rarity (auto from rarity ID)';
    }
    if (rarityWrap){
      rarityWrap.style.display = active ? '' : 'none';
    }
    sel.disabled = !active;
  }

  function getGuidedContext(){
    const gi = document.getElementById('ccGuidedItemType');
    const gm = document.getElementById('ccGuidedManufacturer');
    const gw = document.getElementById('ccGuidedWeaponType');
    const gl = document.getElementById('ccGuidedLevel');
    const getVal = (el)=>{
      if (!el || el.tagName !== 'SELECT') return (el && el.value || '').trim();
      return (el.value || '').trim() || (el.options[el.selectedIndex] && (el.options[el.selectedIndex].value || '').trim()) || '';
    };
    const itemType = getVal(gi);
    if (!itemType) return null;
    return {
      itemType,
      manufacturer: getVal(gm),
      weaponType: getVal(gw),
      level: Number(gl && gl.value || 60) || 60
    };
  }

  /** Guided-dropdown art (same paths as cc-guided-builder-rebuild.js). */
  const STX_CC_WEAPON_TYPE_DIR = './assets/img/guided-dropdowns/weapon-type/';
  const STX_CC_LEGENDARY_AUG_BASE = './assets/img/guided-dropdowns/legendary-augments/';
  const STX_CC_PEARL_ITEMTYPE_BASE = './assets/img/dlc_rarity_pips/';
  const STX_CC_ELEMENT_ICON_BASE = './assets/img/elements/';
  /** BL UI stats icons for class mod Universal / stat rows (see `universal-perk-icons/`). */
  const STX_UNIVERSAL_PERK_ICON_BASE = './assets/img/universal-perk-icons/';
  const STX_WEAPON_TYPE_ICON_FILES = {
    'assault rifle': 'ico_ui_art_assault_small.png',
    pistol: 'ico_ui_art_pistol_small.png',
    shotgun: 'ico_ui_art_shotgun_small.png',
    smg: 'ico_ui_art_smg_small.png',
    'sniper rifle': 'ico_ui_art_sniper_small.png',
    sniper: 'ico_ui_art_sniper_small.png',
    'heavy weapon': 'ico_ui_art_heavy_small.png',
    heavy: 'ico_ui_art_heavy_small.png'
  };
  const STX_GUIDED_DROPDOWN_BASE = './assets/img/guided-dropdowns/';
  /** Recolor white-on-dark weapon silhouettes (common→epic). Applied on `.custom-select-icon-filter-wrap`, not on `<img>`, for reliable Chromium/Electron compositing. */
  const STX_COMP_TIER_WEAPON_ICON_FILTERS = [
    'brightness(0) saturate(100%) invert(68%) sepia(9%) saturate(214%) hue-rotate(126deg) brightness(94%) contrast(88%)',
    'brightness(0) saturate(100%) invert(56%) sepia(58%) saturate(488%) hue-rotate(90deg) brightness(96%) contrast(91%)',
    'brightness(0) saturate(100%) invert(55%) sepia(72%) saturate(1466%) hue-rotate(176deg) brightness(96%) contrast(92%)',
    'brightness(0) saturate(100%) invert(51%) sepia(71%) saturate(2347%) hue-rotate(238deg) brightness(95%) contrast(92%)'
  ];
  /** Legendary (gold) tint for flat class-mod body / vault-hunter silhouettes. */
  const STX_CLASSMOD_LEGENDARY_BODY_ICON_FILTER =
    'brightness(0) saturate(100%) invert(78%) sepia(64%) saturate(1200%) hue-rotate(2deg) brightness(1.05) contrast(1.05)';

  function stxClassModBodyLooksLegendary(p){
    if (!p) return false;
    const c = String(normCode(p.code || p.spawnCode || '') || '').toLowerCase();
    if (/leg_body_/.test(c)) return true;
    const nm = String((p.name || p.legendaryName || p.displayName) || '').toLowerCase();
    if (/\blegendary\b/.test(nm)) return true;
    const pt = String(p.partType || '').toLowerCase();
    if (pt.indexOf('legendary') !== -1) return true;
    return false;
  }

  function stxApplyClassModBodyLegendaryIconFilter(opt, p){
    if (!opt || !p) return;
    if (!stxClassModBodyLooksLegendary(p)) return;
    try {
      if (document.documentElement.classList.contains('stx-lite-ui')) return;
    } catch (_) {}
    const icon = String(opt.getAttribute('data-cc-icon') || '');
    /* Vault-hunter portraits have face detail; brightness(0) gold fill turns them into solid yellow blobs. */
    if (/vault-hunters\//i.test(icon)) {
      if (!opt.getAttribute('data-cc-primary-tone')) opt.setAttribute('data-cc-primary-tone', 'legendary');
      return;
    }
    opt.setAttribute('data-cc-icon-filter', STX_CLASSMOD_LEGENDARY_BODY_ICON_FILTER);
  }
  /**
   * Gentle tints for full-color `legendary-augments/*.png` on rarity-ID rows (common→epic).
   * Separate from STX_COMP_TIER_WEAPON_ICON_FILTERS: those pipelines target flat weapon silhouettes and crush aug detail.
   * Legendary (comp_05) stays unfiltered so gold reads clearly.
   */
  const STX_COMP_TIER_GEAR_LEGENDARY_AUG_FILTERS = [
    'saturate(0.48) brightness(0.84) contrast(1.09)',
    'hue-rotate(78deg) saturate(0.82) brightness(0.86) contrast(1.06)',
    'hue-rotate(168deg) saturate(0.88) brightness(0.87) contrast(1.07)',
    'hue-rotate(228deg) saturate(0.9) brightness(0.86) contrast(1.08)'
  ];
  /** Simple Builder top row: same art as Guided / index.html static options. */
  const STX_ITEM_TYPE_ICONS = {
    Weapon: STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_gun_assault.png',
    Heavy: STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_heavy.png',
    'Heavy Weapon': STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_heavy.png',
    Shield: STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_shield.png',
    Repkit: STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_repkit.png',
    Grenade: STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_grenade.png',
    Gadget: STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_heavy.png',
    Enhancement: STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_classmod.png',
    'Class Mod': STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_classmod.png',
    Other: STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_gun_assault.png'
  };

  function stxItemTypeIconUrl(cat){
    const c = String(cat || '').trim();
    if (!c) return '';
    let u = '';
    if (STX_ITEM_TYPE_ICONS[c]) u = STX_ITEM_TYPE_ICONS[c];
    else {
      const low = c.toLowerCase().replace(/\s+/g, ' ');
      if (low === 'character' || low === 'classmod' || low === 'class mod') u = STX_ITEM_TYPE_ICONS['Class Mod'];
      else if (low === 'heavy') u = STX_ITEM_TYPE_ICONS['Heavy Weapon'];
    }
    return u ? stxPearlPipUrlInsteadOfLegendaryAug(u) : '';
  }

  function stxManufacturerIconUrl(rawMfr, itemTypeCat){
    const it = String(itemTypeCat || '').trim();
    if (/class\s*mod/i.test(it)){
      const key = stxCanonicalClassModManufacturerKey(rawMfr);
      const base = './assets/img/vault-hunters/';
      if (key === 'siren') return base + 'player_class_dark_siren.png';
      if (key === 'paladin') return base + 'player_class_paladin.png';
      if (key === 'exo soldier') return base + 'player_class_exo_soldier.png';
      if (key === 'gravitar') return base + 'player_class_gravitar.png';
      if (key === 'robodealer') return base + 'player_robodealer.png';
      if (key === 'corpohacker') return base + 'player_corpohacker.png';
      return '';
    }
    const m = String(rawMfr || '').trim().toLowerCase();
    const map = {
      atlas: 'manufacturer/ui_art_manu_logomark_atlas_small.png',
      cov: 'manufacturer/ui_art_manu_logomark_cov_small.png',
      daedalus: 'manufacturer/ui_art_manu_logomark_daedalus_small.png',
      hyperion: 'manufacturer/ui_art_manu_logomark_hyperion_small.png',
      jakobs: 'manufacturer/ui_art_manu_logomark_jakobs_small.png',
      maliwan: 'manufacturer/ui_art_manu_logomark_maliwan_small.png',
      order: 'manufacturer/ui_art_manu_logomark_order_small.png',
      ripper: 'manufacturer/ui_art_manu_logomark_ripper_small.png',
      tediore: 'manufacturer/ui_art_manu_logomark_tediore_small.png',
      torgue: 'manufacturer/ui_art_manu_logomark_torgue_small.png',
      vladof: 'manufacturer/ui_art_manu_logomark_vladof_small.png',
      borg: 'manufacturer/ui_art_manu_logomark_ripper_small.png'
    };
    const rel = map[m];
    return rel ? STX_GUIDED_DROPDOWN_BASE + rel : '';
  }

  function stxSyncCustomSelectIfWrapped(sel){
    if (!sel) return;
    if (typeof sel.__customSelectSync === 'function') {
      try { sel.__customSelectSync(); } catch (_) {}
    }
    if (typeof sel.__customSelectPrebuild === 'function') {
      try { sel.__customSelectPrebuild(); } catch (_) {}
    }
  }

  function stxRebuildCustomSelectIfWrapped(sel){
    if (!sel) return;
    stxSyncCustomSelectIfWrapped(sel);
    if (typeof sel.__customSelectForceRebuild === 'function') {
      try { sel.__customSelectForceRebuild(); } catch (_) {}
    }
  }

  function stxNormWeaponKeyFromUi(wtRaw){
    let wt = String(wtRaw || '').trim().toLowerCase();
    if (wt === 'submachine gun') wt = 'smg';
    if (wt === 'heavy') wt = 'heavy weapon';
    if (wt === 'sniper') wt = 'sniper rifle';
    return wt;
  }

  function stxWeaponTypeIconUrl(wtRaw){
    const k = stxNormWeaponKeyFromUi(wtRaw);
    const fn = STX_WEAPON_TYPE_ICON_FILES[k];
    return fn ? STX_CC_WEAPON_TYPE_DIR + fn : '';
  }

  /**
   * Icons for plain-text "universal" class mod rows (normalized perk keys) + Rafa Broken shields.
   * Uses element chips for Broken * (Maliwan-style color read) and item-stat art for numeric bonuses.
   */
  function stxResolveUniversalClassmodPerkIconUrl(pkNorm){
    const b = String(pkNorm || '').toLowerCase();
    if (!b) return null;
    const u = STX_UNIVERSAL_PERK_ICON_BASE;
    const el = STX_CC_ELEMENT_ICON_BASE;

    if (b.includes('brokenblue')) return el + 'pearl_elemental_shock.png';
    if (b.includes('brokengreen')) return el + 'pearl_elemental_corrosive.png';
    if (b.includes('brokenred')) return el + 'pearl_elemental_fire.png';
    if (b.includes('brokenwhite')) return el + 'pearl_elemental_kinetic.png';

    if (b.includes('cryo') && b.includes('damage')) return el + 'pearl_elemental_cryo.png';
    if ((b.includes('fire') || b.includes('incendiary')) && b.includes('damage')) return el + 'pearl_elemental_fire.png';
    if (b.includes('shock') && b.includes('damage')) return el + 'pearl_elemental_shock.png';
    if (b.includes('corrosive') && b.includes('damage')) return el + 'pearl_elemental_corrosive.png';
    if (b.includes('radiation') && b.includes('damage')) return el + 'pearl_elemental_radiation.png';
    if (b.includes('sonic') && b.includes('damage')) return el + 'pearl_elemental_sonic.png';

    if (b.includes('damagereduction')) return u + 'perk_damage_reduction.png';
    if (b.includes('energyshield') || (b.includes('shield') && b.includes('energy'))) return u + 'perk_shield_capacity.png';

    if (b.includes('critical') || b.includes('crit')) return u + 'perk_crit_damage.png';
    if (b.includes('firerate')) return u + 'perk_fire_rate.png';
    if (b.includes('reload')) return u + 'perk_reload.png';
    if (b.includes('magazine') || b.includes('magsize')) return u + 'perk_mag_size.png';
    if (b.includes('accuracy') || b.includes('handling')) return u + 'perk_accuracy.png';
    if (b.includes('duration')) return u + 'perk_duration.png';
    if (b.includes('cooldown') || b === 'actionskill' || b.startsWith('actionskill')) return u + 'perk_cooldown.png';

    if (b.includes('grenade') && b.includes('damage')) return u + 'perk_explosive_damage.png';

    if ((b.includes('assault') && b.includes('rifle')) || b === 'assaultrifle') return stxWeaponTypeIconUrl('Assault Rifle') || null;
    if (b.includes('submachine') || b === 'smg' || b === 'submachinegun') return stxWeaponTypeIconUrl('SMG') || null;
    if (b.includes('shotgun')) return stxWeaponTypeIconUrl('Shotgun') || null;
    if (b.includes('sniper')) return stxWeaponTypeIconUrl('Sniper Rifle') || null;
    if (b.includes('pistol')) return stxWeaponTypeIconUrl('Pistol') || null;
    if (b.includes('heavyweapon') || b === 'heavy' || (b.includes('heavy') && b.includes('weapon'))) return stxWeaponTypeIconUrl('Heavy Weapon') || null;

    if (b.includes('damage') && !b.includes('reduction')) return u + 'perk_weapon_damage.png';

    return null;
  }

  /** Strip combining marks so "Corazón" → "Corazon" before the ASCII-only slug step. */
  function stxFoldDiacriticsForPerkIconKey(raw){
    try{
      return String(raw || '').normalize('NFD').replace(/\p{M}+/gu, '');
    }catch(_e){
      return String(raw || '');
    }
  }

  /** On-disk stems under `assets/img/classmod-firmware/` (no .png). */
  const STX_FIRMWARE_ICON_STEMS = {
    actionfist: 1, activefire: 1, airstrike: 1, atlasex: 1, atlasinfinium: 1, baker: 1,
    bulletstospare: 1, daedyo: 1, deadeye: 1, gadgetahoy: 1, getthrowd: 1, godkiller: 1,
    goojfc: 1, heatingup: 1, highcaliber: 1, jacked: 1, lifeblood: 1, oscarmike: 1,
    reelbigfist: 1, riskyboots: 1, rubberbandman: 1, skillcraft: 1, trickshot: 1
  };
  const STX_FIRMWARE_ICON_FALLBACK = './assets/img/classmod-firmware/jacked.png';
  const STX_FIRMWARE_ICON_BASE = './assets/img/classmod-firmware/';
  const STX_DLC_FIRMWARE_ICON_BASE = './assets/img/dlc-firmware/';

  /** Map dataset / label stems → on-disk firmware icon stem. */
  function stxNormalizeFirmwareIconStem(raw){
    let fw = stxFoldDiacriticsForPerkIconKey(String(raw || ''))
      .toLowerCase()
      .replace(/&/g, 'and')
      .replace(/['’]/g, '')
      .replace(/[^a-z0-9_]+/g, '_')
      .replace(/_+/g, '_')
      .replace(/^_|_$/g, '');
    if (!fw) return '';
    /* Drop noise prefixes/suffixes from labels like "Firmware Active Fire" / "Active Fire Firmware". */
    fw = fw.replace(/^(part_)?firmware_?/g, '').replace(/_?firmware$/g, '').replace(/_?passive_?/g, '');
    fw = fw.replace(/_/g, '');
    if (!fw) return '';
    if (fw === 'atlasinfinum' || fw === 'atlasinfiniumm' || fw === 'atlasinfimum') fw = 'atlasinfinium';
    if (fw === 'daeddyo' || fw === 'deaddyo' || fw === 'daeddy') fw = 'daedyo';
    if (fw === 'bulletspare' || fw === 'bulletstospare') fw = 'bulletstospare';
    if (fw === 'getthrowin' || fw === 'getthrowing' || fw === 'getthrowd') fw = 'getthrowd';
    if (fw === 'godkillers') fw = 'godkiller';
    if (fw === 'gadgetahoy') fw = 'gadgetahoy';
    if (fw === 'reelbigfists') fw = 'reelbigfist';
    if (fw === 'rubberband') fw = 'rubberbandman';
    if (fw === 'oscarmikes') fw = 'oscarmike';
    if (fw === 'highcalibre' || fw === 'highcalibur') fw = 'highcaliber';
    if (fw === 'heating') fw = 'heatingup';
    if (fw === 'actionfists') fw = 'actionfist';
    return fw;
  }

  /**
   * Resolve a firmware chip icon from spawn code and/or display name.
   * Newer rows often have empty names or "Firmware …" labels — always prefer `part_firmware_*` stem.
   */
  function stxResolveFirmwareIconUrl(p){
    const code = String((p && (p.code || p.spawnCode || p.importCode)) || '').toLowerCase();
    const nameBlob = String((p && (p.name || p.legendaryName || p.effects || p.effect || p.label)) || '');
    const candidates = [];
    const codeStem = code.match(/part_firmware_([a-z0-9_]+)/i);
    if (codeStem && codeStem[1]) candidates.push(codeStem[1]);
    if (nameBlob) candidates.push(nameBlob);
    /* Also try raw code slug without path. */
    const bare = code.replace(/^.*\./, '').replace(/^part_firmware_?/i, '');
    if (bare && bare !== code) candidates.push(bare);

    for (let i = 0; i < candidates.length; i++) {
      const stem = stxNormalizeFirmwareIconStem(candidates[i]);
      if (!stem) continue;
      if (STX_FIRMWARE_ICON_STEMS[stem]) return STX_FIRMWARE_ICON_BASE + stem + '.png';
      /* DLC alternate art when present (active fire / skillcraft). */
      if (stem === 'activefire') return STX_FIRMWARE_ICON_BASE + 'activefire.png';
      if (stem === 'skillcraft') return STX_FIRMWARE_ICON_BASE + 'skillcraft.png';
    }
    /* Known newer firmwares without dedicated art yet — still show a chip, not a blank. */
    return STX_FIRMWARE_ICON_FALLBACK;
  }
  try { window.stxResolveFirmwareIconUrl = stxResolveFirmwareIconUrl; } catch (_e) {}
  try { window.stxNormalizeFirmwareIconStem = stxNormalizeFirmwareIconStem; } catch (_e) {}

  /**
   * Perk art files omit the "Vex - " / "Harlowe - " prefix; `vexchanneling` → `channeling`.
   * Longest prefixes first so `c4sh` wins over substring collisions.
   */
  function stxStripVaultHunterPrefixFromClassmodPerkStem(pk){
    const x = String(pk || '').toLowerCase().trim();
    if (!x) return x;
    const prefs = ['corpohacker', 'loveless', 'robodealer', 'exosoldier', 'harlowe', 'gravitar', 'c4sh', 'paladin', 'siren', 'amon', 'rafa', 'vex'];
    for (let pi = 0; pi < prefs.length; pi++){
      const pref = prefs[pi];
      /* Keep short stems like c4shgame intact (stripping would leave "game"). */
      if (!x.startsWith(pref) || x.length < pref.length + 5) continue;
      let rest = x.slice(pref.length);
      /* Normalized possessives: harlowescertaintyprinciple → certaintyprinciple */
      if (rest.charAt(0) === 's' && /[a-z]/.test(rest.charAt(1))) rest = rest.slice(1);
      return rest || x;
    }
    return x;
  }

  /**
   * Map normalized perk-name keys to existing `assets/img/classmod-perks/*.png` stems
   * (typos, UK spellings, and long autogenerated stat keys with no dedicated art).
   */
  function stxRemapClassmodPerkArtStem(raw){
    const x = String(raw || '').toLowerCase().trim();
    if (!x) return x;
    const map = {
      harbringer: 'harbinger',
      judgement: 'judgment',
      thebestdefence: 'thebestdefense',
      statuseffectapplicationchance: 'practicalapplications',
      devilstinered: 'devilstinesred',
      devilstineblue: 'devilstinesblue',
      devilstinegreen: 'devilstinesgreen',
      fromgloamtoglow: 'fromgloamtillglow',
      luckbearobot: 'luckless',
      precisionengineering: 'mechanicalbrilliance',
      lifesteal: 'essenceleech',
      phaseclonehealthlossovertime: 'phasepocket',
      redtreestrikemedownbroken: 'strikemedown',
      legerdamain: 'legerdemain',
      toothofnail: 'toothandnail',
      chainreaction: 'chainreactor',
      scertaintyprinciple: 'harlowescertaintyprinciple',
      certaintyprinciple: 'harlowescertaintyprinciple',
      /* Nexus Gravitar stub — no dedicated art; closest Harlowe Grave skill stem. */
      gravasmskilltest: 'gravepower',
      gravasmskill: 'gravepower',
    };
    if (map[x]) return map[x];
    if (/defence$/i.test(x)) return x.replace(/defence$/i, 'defense');
    return x;
  }

  try {
    window.stxResolveUniversalClassmodPerkIconUrl = stxResolveUniversalClassmodPerkIconUrl;
    window.stxFoldDiacriticsForPerkIconKey = stxFoldDiacriticsForPerkIconKey;
    window.stxStripVaultHunterPrefixFromClassmodPerkStem = stxStripVaultHunterPrefixFromClassmodPerkStem;
    window.stxRemapClassmodPerkArtStem = stxRemapClassmodPerkArtStem;
  } catch (_e) {}

  /** Match cc-guided-builder `ccNormalizedWeaponTypeKey` so barrel icons align with Guided. */
  function stxNormalizedWeaponTypeKeyFromPart(p){
    if (!p) return '';
    let wt = String(p.weaponType || p.itemType || '').trim().toLowerCase().replace(/\s+/g, ' ');
    if (wt === 'submachine gun') wt = 'smg';
    if (STX_WEAPON_TYPE_ICON_FILES[wt]) return wt;

    const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toUpperCase();
    if (!c) return '';
    if (/_HW\.|\bMAL_HW\b|\bTOR_HW\b|\bBOR_HW\b|\bVLA_HW\b|\bJAK_HW\b|\bTED_HW\b/i.test(c)) return 'heavy weapon';
    if (/_AR\.|\bDAD_AR\b|\bJAK_AR\b|\bATL_AR\b|\bVLA_AR\b|\bMAL_AR\b|\bTED_AR\b|\bHYP_AR\b/i.test(c)) return 'assault rifle';
    if (/_SM\.|\bDAD_SM\b|\bJAK_SM\b|\bMAL_SM\b|\bVLA_SM\b|\bTED_SM\b|\bHYP_SM\b/i.test(c)) return 'smg';
    if (/_SG\.|\bDAD_SG\b|\bJAK_SG\b|\bMAL_SG\b|\bVLA_SG\b|\bTED_SG\b|\bHYP_SG\b/i.test(c)) return 'shotgun';
    if (/_PS\.|\bDAD_PS\b|\bJAK_PS\b|\bMAL_PS\b|\bVLA_PS\b|\bTED_PS\b|\bHYP_PS\b/i.test(c)) return 'pistol';
    if (/_SR\.|\bDAD_SR\b|\bJAK_SR\b|\bMAL_SR\b|\bVLA_SR\b|\bTED_SR\b|\bHYP_SR\b/i.test(c)) return 'sniper rifle';
    return '';
  }

  function stxSpawnCodeLooksLikeWeaponFamily(p){
    if (!p) return false;
    const c = normCode(p.code || p.spawnCode || p.importCode || '').toLowerCase();
    return /\.(ar|ps|sg|sm|sr|hw)\./.test(c);
  }

  function stxWeaponFamilyPearlFilename(p){
    let kw = stxNormalizedWeaponTypeKeyFromPart(p);
    if (kw === 'submachine gun') kw = 'smg';
    const map = {
      'assault rifle': 'ico_pearl_aug_gun_assault.png',
      pistol: 'ico_pearl_aug_gun_pistol.png',
      shotgun: 'ico_pearl_aug_gun_shotgun.png',
      smg: 'ico_pearl_aug_gun_smg.png',
      'sniper rifle': 'ico_pearl_aug_gun_sniper.png',
      sniper: 'ico_pearl_aug_gun_sniper.png',
      'heavy weapon': 'ico_pearl_aug_gun_heavy.png',
      heavy: 'ico_pearl_aug_gun_heavy.png'
    };
    return map[kw] || 'ico_pearl_aug_gun_assault.png';
  }

  function stxPartLooksLegendaryBarrel(p){
    if (!p) return false;
    if (String(p.legendaryName || '').trim()) return true;
    if (/legendary/i.test(String(p.partType || ''))) return true;
    const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
    if (c.indexOf('comp_05_legendary') !== -1) return true;
    if (c.indexOf('part_unique_barrel') !== -1) return true;
    /* Heavy / named legendaries sometimes use `part_barrel_<slug>` (no digit index). */
    const unnumbered = c.match(/\.part_barrel_([a-z][a-z0-9_]{3,})$/);
    if (unnumbered && !/^[abcd]$/.test(unnumbered[1])) return true;
    const numbered = c.match(/part_barrel_\d+_([a-z0-9_]+)$/);
    if (numbered){
      const suf = String(numbered[1] || '');
      if (suf.length >= 4 && !/^[abcd]$/.test(suf)) return true;
    }
    return false;
  }

  /** Barrels whose dataset row carries the item-card legendary effect line (unique barrels, etc.), not only abstract Legendary Perks rows. */
  function stxPartCarriesLegendaryEffectWeaponFamilyBarrel(p){
    if (!p) return false;
    const cat = String(p.category || '').trim();
    if (cat !== 'Weapon' && cat !== 'Gadget' && cat !== 'Heavy Weapon') return false;
    const pt = String(p.partType || '').trim().toLowerCase();
    if (pt !== 'barrel') return false;
    const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
    if (c.indexOf('part_unique_barrel') !== -1) return true;
    if (String(p.legendaryName || '').trim()) return true;
    if (c.indexOf('comp_05_legendary') !== -1) return true;
    /* `tor_hw.part_barrel_dahlfather` / `part_barrel_javelin` — no digit between barrel_ and slug. */
    const unnumbered = c.match(/\.part_barrel_([a-z][a-z0-9_]{3,})$/);
    if (unnumbered && !/^[abcd]$/.test(unnumbered[1])) return true;
    const namedLeg = c.match(/part_barrel_\d+_([a-z0-9_]+)$/);
    if (namedLeg){
      const suf = String(namedLeg[1] || '');
      if (suf.length >= 4 && !/^[abcd]$/.test(suf)) return true;
    }
    return false;
  }

  function stxLegendaryAugFilenameFromWeaponKey(key){
    const wt = stxNormWeaponKeyFromUi(key);
    const map = {
      'assault rifle': 'ico_legendary_aug_gun_assault.png',
      pistol: 'ico_legendary_aug_gun_pistol.png',
      shotgun: 'ico_legendary_aug_gun_shotgun.png',
      smg: 'ico_legendary_aug_gun_smg.png',
      'sniper rifle': 'ico_legendary_aug_gun_sniper.png',
      sniper: 'ico_legendary_aug_gun_sniper.png',
      'heavy weapon': 'ico_legendary_aug_heavy.png',
      heavy: 'ico_legendary_aug_heavy.png'
    };
    return map[wt] || map['assault rifle'] || '';
  }

  /** Full URL for pearl slot art from part category + spawn code (like ccPearlSlotAugFullUrl). */
  function stxPearlAugFullUrlFromPart(p){
    if (!p) return '';
    if (stxSpawnCodeLooksLikeWeaponFamily(p)) {
      return STX_CC_PEARL_ITEMTYPE_BASE + stxWeaponFamilyPearlFilename(p);
    }
    let cat = String(p.category || '').trim().toLowerCase();
    if (cat === 'character') cat = 'class mod';
    let fn = '';
    if (cat === 'class mod') fn = 'ico_pearl_aug_gun_classmod.png';
    else if (cat === 'grenade') fn = 'ico_pearl_aug_gun_grenade.png';
    else if (cat === 'repkit') fn = 'ico_pearl_aug_gun_repkit.png';
    else if (cat === 'shield') fn = 'ico_pearl_aug_gun_shield.png';
    else if (cat === 'heavy weapon' || cat === 'gadget'){
      fn = 'ico_pearl_aug_gun_heavy.png';
    } else if (cat === 'weapon'){
      fn = stxWeaponFamilyPearlFilename(p);
      if (fn === 'ico_pearl_aug_gun_assault.png' && !stxNormalizedWeaponTypeKeyFromPart(p)) fn = '';
    }
    return fn ? STX_CC_PEARL_ITEMTYPE_BASE + fn : '';
  }

  function stxCompIconContext(){
    const guided = getGuidedContext();
    const simpleItem = stxNormalizeSimpleBuilderItemTypeUi(state.itemType || '');
    const guidedItem = guided ? stxNormalizeSimpleBuilderItemTypeUi(String(guided.itemType || '').trim()) : '';
    const useGuided = !!(guidedItem && (!simpleItem || guidedItem === simpleItem ||
      (stxSimpleBuilderItemTypeIsHeavyUi(guidedItem) && stxSimpleBuilderItemTypeIsHeavyUi(simpleItem))));
    if (useGuided && guided && guided.itemType){
      const catUi = guided.itemType;
      const cat = stxSimpleBuilderItemTypeIsHeavyUi(catUi, guided.weaponType) ? 'Weapon' : catUi;
      let wtr = (cat === 'Weapon' && stxSimpleBuilderItemTypeIsHeavyUi(catUi, guided.weaponType)) ? 'Heavy Weapon' : (guided.weaponType || (cat === 'Weapon' ? 'Assault Rifle' : ''));
      if (String(wtr) === 'Heavy') wtr = 'Heavy Weapon';
      return { cat, catUi, weaponType: String(wtr || '') };
    }
    const catUi = simpleItem;
    const cat = stxSimpleBuilderItemTypeIsHeavyUi(catUi) ? 'Weapon' : catUi;
    let wtr = (cat === 'Weapon' && stxSimpleBuilderItemTypeIsHeavyUi(catUi)) ? 'Heavy Weapon'
      : (($('weaponType') && $('weaponType').value) || state.weaponType || '');
    if (String(wtr) === 'Heavy') wtr = 'Heavy Weapon';
    return { cat, catUi, weaponType: String(wtr || '') };
  }

  function stxResolveGearCategoryForCompIcons(ctx){
    let cat = String(ctx && ctx.cat || '').trim().toLowerCase();
    if (cat === 'enhancement' && state.mainPart){
      const mc = String(state.mainPart.category || state.detectedCategory || '').trim().toLowerCase();
      if (mc === 'weapon') cat = 'weapon';
      else if (mc === 'shield') cat = 'shield';
      else if (mc === 'grenade') cat = 'grenade';
      else if (mc === 'repkit') cat = 'repkit';
      else if (mc === 'character' || mc === 'class mod') cat = 'class mod';
      else if (mc === 'gadget' || mc === 'heavy weapon') cat = 'gadget';
    }
    return cat;
  }

  function stxPearlSlotIconFilenameFromContext(ctx){
    if (!ctx) return '';
    let cat = stxResolveGearCategoryForCompIcons(ctx);
    if (cat === 'character') cat = 'class mod';
    const wt = stxNormWeaponKeyFromUi(ctx.weaponType);
    if (cat === 'class mod' || cat === 'classmod') return 'ico_pearl_aug_gun_classmod.png';
    if (cat === 'grenade') return 'ico_pearl_aug_gun_grenade.png';
    if (cat === 'repkit') return 'ico_pearl_aug_gun_repkit.png';
    if (cat === 'shield') return 'ico_pearl_aug_gun_shield.png';
    if (cat === 'heavy weapon' || cat === 'gadget') return 'ico_pearl_aug_gun_heavy.png';
    if (cat === 'weapon'){
      const map = {
        'assault rifle': 'ico_pearl_aug_gun_assault.png',
        pistol: 'ico_pearl_aug_gun_pistol.png',
        shotgun: 'ico_pearl_aug_gun_shotgun.png',
        smg: 'ico_pearl_aug_gun_smg.png',
        'sniper rifle': 'ico_pearl_aug_gun_sniper.png',
        sniper: 'ico_pearl_aug_gun_sniper.png',
        'heavy weapon': 'ico_pearl_aug_gun_heavy.png',
        heavy: 'ico_pearl_aug_gun_heavy.png'
      };
      return map[wt] || map['assault rifle'];
    }
    return '';
  }

  /** Legendary aug file by resolved UI gear category + weapon class (rarity comp tier + slots). */
  function stxLegendaryAugFilenameFromCategoryWeapon(catRaw, weaponTypeStr, normWeaponKey, partHint){
    if (partHint && stxSpawnCodeLooksLikeWeaponFamily(partHint)) {
      const wk = normWeaponKey || stxNormalizedWeaponTypeKeyFromPart(partHint);
      return stxLegendaryAugFilenameFromWeaponKey(wk || weaponTypeStr || 'Assault Rifle');
    }
    const c0 = String(catRaw || '').trim().toLowerCase();
    const c = (c0 === 'character' || c0 === 'classmod') ? 'class mod' : c0;
    const byCat = {
      shield: 'ico_legendary_aug_shield.png',
      repkit: 'ico_legendary_aug_repkit.png',
      grenade: 'ico_legendary_aug_grenade.png',
      'class mod': 'ico_legendary_aug_classmod.png',
      enhancement: 'ico_legendary_aug_classmod.png'
    };
    if (byCat[c]) return byCat[c];
    const wk = normWeaponKey || stxNormalizedWeaponTypeKeyFromPart({ weaponType: weaponTypeStr, itemType: weaponTypeStr });
    return stxLegendaryAugFilenameFromWeaponKey(wk || weaponTypeStr || 'Assault Rifle');
  }

  function stxGuessPearlElementIconFilename(p){
    const its = String(p && p.itemTypeString || '').toLowerCase();
    const code = String(p && p.code || '').toLowerCase();
    const nm = String((p && (p.legendaryName || p.name)) || '').toLowerCase();
    const blob = its + ' ' + code + ' ' + nm;
    if (/\bpearl_(damage|reload|firerate|handling)\b/.test(blob)) return 'ico_misc_pearl.png';
    const pe = its.match(/\bpearl_(normal|shock|radiation|corrosive|cryo|fire|sonic)\b/);
    if (pe) return pe[1] === 'normal' ? 'pearl_elemental_kinetic.png' : 'pearl_elemental_' + pe[1] + '.png';
    if (blob.includes('corrosive')) return 'pearl_elemental_corrosive.png';
    if (blob.includes('cryo')) return 'pearl_elemental_cryo.png';
    if (blob.includes('radiation') || blob.includes('_rad_')) return 'pearl_elemental_radiation.png';
    if (blob.includes('sonic') || blob.includes('barrier_elemental_field_sonic')) return 'pearl_elemental_sonic.png';
    if (blob.includes('shock')) return 'pearl_elemental_shock.png';
    if ((/\bring\b/.test(blob) && (blob.includes('element') || blob.includes('ele_'))) || blob.includes('element_ring')) return 'pearl_elemental_ring.png';
    if (blob.includes('kinetic')) return 'pearl_elemental_kinetic.png';
    if (blob.includes('incendiary') || /\bfire\b/.test(blob)) return 'pearl_elemental_fire.png';
    return '';
  }

  /** Pearl elemental art for pearl_elem / part_pearl / curated pearl comp_05 rows; otherwise `ico_elemental_*` UI chip. */
  function stxIsPearlWeaponElementIconContext(p, schemaItem, category){
    const catRaw = String(category || '').trim();
    const catOk = catRaw === 'Weapon' || stxSimpleBuilderItemTypeIsHeavyUi(catRaw) || stxNormalizeSimpleBuilderItemTypeUi(catRaw) === 'Heavy';
    if (!catOk) return false;
    const ns = schemaItem && schemaItem.ncsSlot;
    if (ns === 'pearl_elem' || ns === 'pearl_stat') return true;
    const sk = schemaItem && String(schemaItem.key || '').toLowerCase();
    if (sk === 'pearlelem' || sk === 'pearlstat') return true;
    const lo = String(normCode(p && p.code) || '').toLowerCase();
    if (/part_pearl|comp_06_pearlescent/.test(lo)) return true;
    return false;
  }

  function stxElementChipFilenameFromBlob(blob, pearlStyle){
    const b = String(blob || '').toLowerCase();
    // Repo only contains `pearl_elemental_*` assets (no `ico_elemental_*` set),
    // so always map element chips to the existing filenames.
    const pref = 'pearl_elemental_';
    // Spawn-code shorthands (e.g. JAK_SG.part_body_ele_*_cor_cryo_fire) plus full names
    if (b.includes('corrosive') || b.includes('_cor_')) return pref + 'corrosive.png';
    if (b.includes('_cryo_') || /\bcryo\b/.test(b)) return pref + 'cryo.png';
    if (b.includes('radiation') || b.includes('_rad_')) return pref + 'radiation.png';
    if (b.includes('sonic') || b.includes('barrier_elemental_field_sonic')) return pref + 'sonic.png';
    if (b.includes('shock') || b.includes('_shock_')) return pref + 'shock.png';
    if ((/\bring\b/.test(b) && (b.includes('element') || b.includes('ele_'))) || b.includes('element_ring'))
      return 'pearl_elemental_ring.png';
    if (b.includes('kinetic')) return pref + 'kinetic.png';
    if (b.includes('incendiary') || b.includes('_fire_') || /\bfire\b/.test(b)) return pref + 'fire.png';
    return '';
  }

  /** True only for rarity *component* rows (comp_01…comp_06 / pearl ids), not every partType:Rarity barrel/etc. */
  function isStxCompRarityComponentPart(p){
    if (!p) return false;
    const code = String(normCode(p.code) || '').toLowerCase();
    const its = String(p.itemTypeString || '').toLowerCase();
    const blob = its + ' ' + code;
    const item = Number((p.itemId != null) ? p.itemId : p.id);
    if (Number.isFinite(item) && item >= 51 && item <= 60) return true;
    if (/(^|[._])(comp_0[1-6]_|pearl_)/.test(code)) return true;
    if (/\bpearl_[a-z0-9]+\b/.test(its)) return true;
    if (code.includes('.comp_') || code.includes('enhancement.comp_')) return true;
    if (/(?:^|[._])comp_06_pearlescent/.test(code) || /(?:^|[._])comp_06_pearlescent/.test(its)) return true;
    if (/\bcomp_0[1-6]_/.test(blob) || /\bpearl_/.test(blob)) return true;
    return false;
  }

  /** Rarity ID dropdown (#mainPart): comp rows + any remaining dataset row tagged partType Rarity. */
  function isStxRarityIdCompIconPart(p){
    if (!p) return false;
    if (isStxCompRarityComponentPart(p)) return true;
    return String(p.partType || '').trim().toLowerCase() === 'rarity';
  }

  function stxCodeBlobForCompTier(p){
    if (!p) return '';
    const its = String(p.itemTypeString || '').toLowerCase();
    const c = normCode(p.code).toLowerCase();
    const sp = normCode(p.spawnCode).toLowerCase();
    const nm = String((p.legendaryName || p.name || '')).toLowerCase();
    return `${its} ${c} ${sp} ${nm}`;
  }

  function stxCompTierFromCodeBlob(blob){
    const t = String(blob || '').toLowerCase();
    const m = t.match(/comp_0([1-6])_/);
    if (!m) return null;
    const n = Number(m[1]);
    if (n >= 1 && n <= 6) return n - 1;
    return null;
  }

  function stxInferCompTier(p){
    if (!p) return null;
    const codeEarly = String(normCode(p.code || '') || '').toLowerCase();
    const itsEarly = String(p.itemTypeString || '').toLowerCase();
    const ptEarly = String(p.partType || '').trim().toLowerCase();
    /* Pearl tier only for explicit pearlescent comps / allowlisted pearl rarity ids — not every "pearlescent" substring. */
    if (typeof stxPartIsPearlRarityIdPart === 'function' && stxPartIsPearlRarityIdPart(p)) return 5;
    if (/comp_06_pearlescent|comp_06_pearl_/.test(codeEarly)) return 5;
    if (/comp_05_legendary/.test(codeEarly) || /comp_05_legendary/.test(itsEarly)) {
      if (typeof stxPartMatchesPearlRarityIdAllowlist === 'function' && stxPartMatchesPearlRarityIdAllowlist(p)) return 5;
      return 4;
    }
    if (ptEarly === 'legendary perks' || ptEarly === 'legendary perk') return 4;

    let t = rarityTierFromItemTypeString(p.itemTypeString, p);
    if (Number.isFinite(t)) return t;
    const blob = stxCodeBlobForCompTier(p);
    t = rarityTierFromItemTypeString(blob, p);
    if (Number.isFinite(t)) return t;
    t = stxCompTierFromCodeBlob(blob);
    if (Number.isFinite(t)) return t;
    /* part_rarity / Skin rows often lack comp_05 in code — resolve via STX_RARITIES fam:id (same as optgroups). */
    t = stxRarityTierFromPartForGrouping(p, (state && state.manufacturer) || p.manufacturer || '');
    if (Number.isFinite(t)) return t;
    return null;
  }

  function stxApplyCompPartOptionDecoration(opt, p){
    if (!opt || !p || !isStxRarityIdCompIconPart(p)) return;
    let tier = stxInferCompTier(p);
    opt.removeAttribute('data-cc-icon');
    opt.removeAttribute('data-cc-icon-filter');

    if (!Number.isFinite(tier)){
      const u = stxResolvePartIconUrl(p, { partType: 'Rarity', key: 'rarity' }, state.itemType || '');
      if (u) stxSetOptionDataCcIconFromUrl(opt, u);
      return;
    }

    const ctx = stxCompIconContext();
    const wtFallback = ctx.weaponType || 'Assault Rifle';

    if (tier === 5){
      if ((typeof stxPartIsPearlRarityIdPart === 'function' && stxPartIsPearlRarityIdPart(p)) ||
          (typeof stxPartIsPearlElementPart === 'function' && stxPartIsPearlElementPart(p))) {
        opt.setAttribute('data-cc-icon', stxPearlSlotIconUrlForPart(p, { key: 'rarity', partType: 'Rarity' }));
        return;
      }
      const catLow = stxResolveGearCategoryForCompIcons(ctx);
      const legFn = stxLegendaryAugFilenameFromCategoryWeapon(catLow, ctx.weaponType || wtFallback, stxNormalizedWeaponTypeKeyFromPart(p), p);
      if (legFn) opt.setAttribute('data-cc-icon', STX_CC_LEGENDARY_AUG_BASE + legFn);
      else {
        const u = stxResolvePartIconUrl(p, { partType: 'Rarity', key: 'rarity' }, state.itemType || '');
        if (u) stxSetOptionDataCcIconFromUrl(opt, u);
      }
      return;
    }

    if (tier === 4){
      if (typeof stxPartIsPearlRarityIdPart === 'function' && stxPartIsPearlRarityIdPart(p)) {
        opt.setAttribute('data-cc-icon', stxPearlSlotIconUrlForPart(p, { key: 'rarity', partType: 'Rarity' }));
        return;
      }
      const catLow = stxResolveGearCategoryForCompIcons(ctx);
      const legFn = stxLegendaryAugFilenameFromCategoryWeapon(catLow, ctx.weaponType || wtFallback, stxNormalizedWeaponTypeKeyFromPart(p), p);
      if (legFn){
        opt.setAttribute('data-cc-icon', STX_CC_LEGENDARY_AUG_BASE + legFn);
        return;
      }
      opt.setAttribute('data-cc-icon', STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_gun_assault.png');
      return;
    }

    if (tier >= 0 && tier <= 3){
      const ftier = STX_COMP_TIER_WEAPON_ICON_FILTERS[tier] || '';
      const catLow = stxResolveGearCategoryForCompIcons(ctx);
      if (catLow === 'weapon' || catLow === 'heavy weapon' || catLow === 'heavy' || catLow === 'gadget'){
        const wurl = stxWeaponTypeIconUrl(wtFallback);
        if (wurl){
          opt.setAttribute('data-cc-icon', wurl);
          if (ftier) opt.setAttribute('data-cc-icon-filter', ftier);
          return;
        }
      }
      const gearUsesLegAug = (
        catLow === 'shield'
        || catLow === 'repkit'
        || catLow === 'grenade'
        || catLow === 'class mod'
        || catLow === 'classmod'
        || catLow === 'enhancement'
      );
      if (gearUsesLegAug){
        const legFn = stxLegendaryAugFilenameFromCategoryWeapon(catLow, ctx.weaponType || wtFallback, stxNormalizedWeaponTypeKeyFromPart(p), p);
        if (legFn){
          const fGear = STX_COMP_TIER_GEAR_LEGENDARY_AUG_FILTERS[tier] || '';
          opt.setAttribute('data-cc-icon', stxPearlPipUrlInsteadOfLegendaryAug(STX_CC_LEGENDARY_AUG_BASE + legFn));
          if (fGear) opt.setAttribute('data-cc-icon-filter', fGear);
          return;
        }
      }
      const pfn = stxPearlSlotIconFilenameFromContext(ctx);
      if (pfn){
        opt.setAttribute('data-cc-icon', STX_CC_PEARL_ITEMTYPE_BASE + pfn);
        return;
      }
      const wurl = stxWeaponTypeIconUrl(wtFallback);
      if (wurl){
        opt.setAttribute('data-cc-icon', wurl);
        if (ftier) opt.setAttribute('data-cc-icon-filter', ftier);
        return;
      }
      const u = stxResolvePartIconUrl(p, { partType: 'Rarity', key: 'rarity' }, state.itemType || '');
      if (u) stxSetOptionDataCcIconFromUrl(opt, u);
    }
    if (!opt.getAttribute('data-cc-icon')){
      const u = stxResolvePartIconUrl(p, { partType: 'Rarity', key: 'rarity' }, state.itemType || '');
      if (u) stxSetOptionDataCcIconFromUrl(opt, u);
    }
  }

  /** Simple Builder: class-mod skill / universal / secondary slots (partType "Skill" must still get perk icons). */
  function stxSchemaIsClassmodPerkishSlot(schemaItem, category){
    if (String(category || '').trim() !== 'Class Mod') return false;
    if (!schemaItem) return false;
    const key = String(schemaItem.key || '');
    if (key === 'perk' || key === 'secondary' || key === 'universal') return true;
    const ppt = String(schemaItem.partType || '').toLowerCase();
    return ppt === 'skill' || ppt === 'perk' || ppt === 'universal' || ppt === 'secondary';
  }

  function stxDatasetSuggestsClassmodPerkRow(p, category){
    if (!p) return false;
    const cat = String(category || '').trim();
    const pt = String(p.partType || '').toLowerCase();
    const its = String(p.itemTypeString || p.itemType || '').toLowerCase();
    const blobPs = pt + ' ' + its;
    if (pt.indexOf('perk') !== -1 || pt.indexOf('skill') !== -1 || pt.indexOf('universal') !== -1 || pt.indexOf('modifier') !== -1) return true;
    if (its.indexOf('perk') !== -1 || its.indexOf('skill') !== -1) return true;
    if ((cat === 'Class Mod' || cat === 'Character') && pt.indexOf('secondary') !== -1){
      if (/secondary_ammo|secondary\s*ammo|secondary\s*ele|secondary_ammo|hyperion_secondary|part_secondary_ammo/i.test(blobPs)) return false;
      return true;
    }
    return false;
  }

  function stxResolvePartIconUrl(p, schemaItem, category){
    if (!p) return null;
    const catRaw = String(category || '').trim();
    const cat = (stxSimpleBuilderItemTypeIsHeavyUi(catRaw) || stxNormalizeSimpleBuilderItemTypeUi(catRaw) === 'Heavy') ? 'Weapon' : catRaw;
    const its = String(p.itemTypeString || p.itemType || '').toLowerCase();
    const code = String(p.code || '').toLowerCase();
    const nm = String((p.legendaryName || p.name || '')).toLowerCase();
    const pt = String(p.partType || '').toLowerCase();
    let blob = its + ' ' + code + ' ' + nm;
    const codeNormLo = String(normCode(p.code) || '').toLowerCase();
    const nsSlot = schemaItem && String(schemaItem.ncsSlot || '').toLowerCase();
    const skSlot = schemaItem && String(schemaItem.key || '').toLowerCase();
    if (/part_pearl/i.test(codeNormLo) || nsSlot === 'pearl_elem' || nsSlot === 'pearl_stat' || skSlot === 'pearlelem' || skSlot === 'pearlstat'){
      const elFn = stxGuessPearlElementIconFilename(p);
      if (elFn) return STX_CC_ELEMENT_ICON_BASE + elFn;
      try{
        const pu = stxPearlAugFullUrlFromPart(p);
        if (pu) return pu;
      }catch(_e){}
      try{
        const ctx = stxCompIconContext();
        const pfn = stxPearlSlotIconFilenameFromContext(ctx);
        if (pfn) return STX_CC_PEARL_ITEMTYPE_BASE + pfn;
      }catch(_e){}
      return STX_CC_PEARL_ITEMTYPE_BASE + 'ico_misc_pearl.png';
    }
    if (codeNormLo.includes('part_body_ele')){
      blob += ' ' + codeNormLo.replace(/_cor_/g, ' corrosive ').replace(/_cryo_/g, ' cryo ').replace(/_fire_/g, ' fire ')
        .replace(/_shock_/g, ' shock ').replace(/_rad_/g, ' radiation ').replace(/_sonic_/g, ' sonic ');
    }
    if (codeNormLo){
      const pem = codeNormLo.match(/\.part_element_([a-z0-9_]+)/);
      if (pem && pem[1]){
        blob += ' ' + pem[1].replace(/_/g, ' ');
        if (pem[1] === 'fire') blob += ' incendiary';
      }
      const gge = codeNormLo.match(/grenade_gadget\.part_(corrosive|cryo|fire|radiation|shock)\b/);
      if (gge && gge[1]) blob += ' ' + (gge[1] === 'fire' ? 'fire incendiary' : gge[1]);
    }
    const perkishSchema = stxSchemaIsClassmodPerkishSlot(schemaItem, cat);
    const perkishDataset = stxDatasetSuggestsClassmodPerkRow(p, cat);

    /* Avoid showing fire-element chips for "fire rate" stat rows (name/code contains `fire` as a substring). */
    const blobElemProbe = String(blob || '')
      .replace(/\bfire\s*rate\b/gi, ' __firerate_stat__ ')
      .replace(/\bfirerate\b/gi, '__firerate_stat__')
      .replace(/(^|[^a-z])fire\s*rate([^a-z]|$)/gi, '$1__firerate_stat__$2')
      .replace(/weapon_firerate|[_]firerate\b|wt_[a-z]{2}_firerate/gi, '__firerate_stat__');

    // 0. Element chips: standard `ico_elemental_*` for normal weapon pools; pearl art for pearl slots / curated pearl guns.
    if (/\bcorrosive\b|\bcryo\b|\bshock\b|\bradiation\b|\bfire\b|\bkinetic\b|\bsonic\b|\bincendiary\b/.test(blobElemProbe) || ((/\bring\b/.test(blobElemProbe) && (blobElemProbe.includes('element') || blobElemProbe.includes('ele_'))) || blobElemProbe.includes('element_ring')) || /(?:^|\.)(?:repair_kit\.)?part_element_/.test(codeNormLo) || /^part_element_/.test(codeNormLo)){
      const usePearl = stxIsPearlWeaponElementIconContext(p, schemaItem, cat);
      const el = stxElementChipFilenameFromBlob(blobElemProbe, usePearl);
      if (el) return STX_CC_ELEMENT_ICON_BASE + el;
    }

    // 1. Curated pearl guns: pearl pip only on rarity-ID and barrel rows (not mag/grip/body on the same gun).
    if (stxPartUsesPearlRarityBarrelIcon(p, schemaItem)){
      return stxPearlSlotIconUrlForPart(p, schemaItem);
    }

    // Legendary Perks rows: item-type chip even when name/effects are empty (synthetic / placeholder dataset rows).
    if (String(pt).trim().toLowerCase() === 'legendary perks'){
      const rowCat = String(p.category || '').trim();
      const chipCat = (rowCat === 'Gadget' && stxIsDatasetGrenadeGadgetSpawnCode(codeNormLo)) ? 'Grenade' : rowCat;
      const chip =
        (chipCat === 'Repkit') ? stxItemTypeIconUrl('Repkit')
          : (chipCat === 'Gadget') ? stxItemTypeIconUrl('Gadget')
            : (chipCat === 'Grenade') ? stxItemTypeIconUrl('Grenade')
              : (chipCat === 'Weapon') ? stxItemTypeIconUrl('Weapon')
                : (chipCat === 'Enhancement') ? stxItemTypeIconUrl('Enhancement')
                  : (chipCat === 'Shield') ? stxItemTypeIconUrl('Shield')
                    : (chipCat === 'Character' || chipCat === 'Class Mod') ? stxItemTypeIconUrl('Class Mod')
                      : null;
      if (chip) return chip;
    }

    const schemaKeyLo = schemaItem && String(schemaItem.key || '').trim().toLowerCase();
    if (schemaKeyLo === 'licensed' || /barrel_licensed/i.test(codeNormLo)){
      try{
        const ctx = stxCompIconContext();
        const wt = (ctx && ctx.weaponType) || state.weaponType || 'Assault Rifle';
        const legFn = stxLegendaryAugFilenameFromCategoryWeapon(cat, wt, stxNormalizedWeaponTypeKeyFromPart(p), p);
        if (legFn) return STX_CC_LEGENDARY_AUG_BASE + legFn;
        const wurl = stxWeaponTypeIconUrl(wt);
        if (wurl) return wurl;
      }catch(_e){}
      const u0 = stxItemTypeIconUrl('Weapon');
      if (u0) return u0;
    }

    const s = stxFoldDiacriticsForPerkIconKey(String(p.name || p.legendaryName || p.effects || p.effect || ''))
      .toLowerCase()
      .replace(/&/g, 'and')
      .replace(/[^a-z0-9]+/g, '')
      .trim();

    /* Firmware before empty-name bail-out — many newer firmware rows have blank/odd names. */
    const looksFirmware = (pt.indexOf('firmware') !== -1 || code.indexOf('firmware') !== -1
      || /part_firmware|\.part_firmware/i.test(codeNormLo)
      || schemaKeyLo === 'firmware' || schemaKeyLo === 'firmware246'
      || nsSlot === 'firmware');
    if (looksFirmware) {
      return stxResolveFirmwareIconUrl(p);
    }

    if (!s){
      if (String(cat || catRaw || '').trim() === 'Enhancement' && schemaKeyLo){
        const augChip = ()=> stxPearlPipUrlInsteadOfLegendaryAug(STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_classmod.png');
        if (schemaKeyLo === 'legendary'){
          const ptL = String(pt||'').trim().toLowerCase();
          if (ptL === 'core' || codeNormLo.includes('part_core_')) return augChip();
          const u = stxItemTypeIconUrl('Enhancement');
          if (u) return u;
          return augChip();
        }
        if (schemaKeyLo === 'stats' || schemaKeyLo === 'special' || schemaKeyLo === 'element'){
          const u = stxItemTypeIconUrl('Enhancement');
          if (u) return u;
        }
      }
      if (perkishSchema || perkishDataset){
        if (cat === 'Class Mod') return STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_classmod.png';
      }
      return null;
    }

    // Firmware icons are resolved earlier (before empty-name bail-out).

    // 3. Perk / skill / universal / secondary (all class-mod pickers + Character/Repkit perks)
    if (perkishSchema || perkishDataset || pt.indexOf('perk') !== -1 || pt.indexOf('modifier') !== -1 || its.indexOf('perk') !== -1){
      // Repkits often have perk-ish rows without a corresponding icon file in our perk folders.
      // Prefer a stable item-type chip over a broken-image red cross in dropdowns.
      if (cat === 'Repkit') {
        const u = stxItemTypeIconUrl('Repkit');
        if (u) return u;
      }
      // Shield gadget perks (`Shield.part_unv_*`) do not use class-mod perk artwork — avoid broken-image placeholders.
      if (cat === 'Shield'){
        const u = stxItemTypeIconUrl('Shield');
        if (u) return u;
      }
      const thumbMap = window.__PERK_THUMB_URL_BY_KEY || {};
      if (thumbMap[s]) return thumbMap[s];
      
      // Known skill icon stem aliases
      let pk = s;
      if (pk === 'alcentrorafa') pk = 'alcentro';
      if (pk === 'abajorafa') pk = 'abajo';
      if (pk === 'arribarafa') pk = 'arriba';
      if (pk === 'propreitaryincendiary') pk = 'proprietaryincendiary';
      if (pk === 'thethrill') pk = 'thethrillamon';
      /* Stat stems from data often lack 1:1 perk art files — map to nearby icons to avoid 404 spam. */
      if (pk === 'healthregenpersecond') pk = 'gravevitality';
      if (pk === 'maximumhealthcapacity') pk = 'vitalorgans';
      if (pk === 'maximumshieldcapacity') pk = 'shieldbarriest';
      if (pk === 'movementspeed') pk = 'fasthands';

      /* Prefer full key (e.g. harlowescertaintyprinciple / c4shgame) before VH-prefix strip. */
      if (thumbMap[pk]) return thumbMap[pk];
      const remappedFull = stxRemapClassmodPerkArtStem(pk);
      if (remappedFull && remappedFull !== pk && thumbMap[remappedFull]) return thumbMap[remappedFull];

      pk = stxStripVaultHunterPrefixFromClassmodPerkStem(pk);
      pk = stxRemapClassmodPerkArtStem(pk);
      if (thumbMap[pk]) return thumbMap[pk];

      const universalUrl = stxResolveUniversalClassmodPerkIconUrl(pk) || stxResolveUniversalClassmodPerkIconUrl(s);
      if (universalUrl) return universalUrl;

      if (pk.length > 3) return './assets/img/classmod-perks/' + pk + '.png';
    }

    // 4. Class Mod Body / Character Body (not skill/universal rows — those use section 3)
    if ((cat === 'Class Mod' || cat === 'Character' || its.indexOf('classmod') !== -1 || its.indexOf('character') !== -1) && !perkishSchema && !perkishDataset){
      const mfrKey = stxCanonicalClassModManufacturerKey(p.manufacturer);
      // Character portraits (Dark Siren ≡ Siren / Vex)
      if (mfrKey === 'siren') return './assets/img/vault-hunters/player_class_dark_siren.png';
      if (mfrKey === 'paladin') return './assets/img/vault-hunters/player_class_paladin.png';
      if (mfrKey === 'exo soldier') return './assets/img/vault-hunters/player_class_exo_soldier.png';
      if (mfrKey === 'gravitar') return './assets/img/vault-hunters/player_class_gravitar.png';
      if (mfrKey === 'robodealer') return './assets/img/vault-hunters/player_robodealer.png';
      if (mfrKey === 'corpohacker') return './assets/img/vault-hunters/player_corpohacker.png';
    }

    // 5. Legendary Augments (true legendaries only — not pearlescent comp_05 allowlist rows)
    const looksLegendary = (
      (stxPartLooksLegendaryBarrel(p) && !stxPartUsesPearlRarityBarrelIcon(p, schemaItem))
      || (/comp_05_legendary/.test(blob) && !stxPartMatchesPearlRarityIdAllowlist(p))
      || (nm.indexOf('legendary') !== -1 && !stxPartMatchesPearlRarityIdAllowlist(p))
    );
    if (looksLegendary){
      const uiCat = String(category || '').trim().toLowerCase();
      if (uiCat === 'enhancement'){
        return stxPearlPipUrlInsteadOfLegendaryAug(STX_CC_LEGENDARY_AUG_BASE + 'ico_legendary_aug_classmod.png');
      }
      const catPart = String(p.category || '').trim().toLowerCase();
      const legFn = stxLegendaryAugFilenameFromCategoryWeapon(
        catPart,
        p.weaponType || p.itemType,
        stxNormalizedWeaponTypeKeyFromPart(p),
        p
      );
      if (legFn) return stxPearlPipUrlInsteadOfLegendaryAug(STX_CC_LEGENDARY_AUG_BASE + legFn);
    }

    // 6. Default: Weapon/Gadget chip
    const kw = stxNormalizedWeaponTypeKeyFromPart(p);
    if (kw){
      const fn = STX_WEAPON_TYPE_ICON_FILES[kw];
      if (fn) return STX_CC_WEAPON_TYPE_DIR + fn;
    }

    // 7. Dataset category chip (shield / grenade / repkit / gadget / enhancement bodies, payloads, etc.)
    const dataCat = String(p.category || '').trim();
    if (dataCat === 'Shield' || dataCat === 'Grenade' || dataCat === 'Repkit' || dataCat === 'Gadget' || dataCat === 'Enhancement'){
      const chipCat = (dataCat === 'Gadget' && stxIsDatasetGrenadeGadgetSpawnCode(codeNormLo)) ? 'Grenade' : dataCat;
      const u = stxItemTypeIconUrl(chipCat);
      if (u) return u;
    }

    return null;
  }
  try { window.stxResolvePartIconUrl = stxResolvePartIconUrl; } catch (_e) {}

  function stxSetOptionDataCcIconFromUrl(opt, iconUrl){
    if (!opt || !iconUrl) return;
    opt.setAttribute('data-cc-icon', iconUrl);
    opt.removeAttribute('data-cc-icon-alt');
    if (typeof iconUrl === 'string' && iconUrl.indexOf('./assets/img/classmod-perks/') === 0){
      opt.setAttribute('data-cc-icon-alt', iconUrl.replace('/classmod-perks/', '/classmod-passive/'));
    } else if (typeof iconUrl === 'string' && iconUrl.indexOf('./assets/img/classmod-firmware/') === 0){
      /* If a newer firmware stem 404s, fall back to a known chip instead of a blank. */
      opt.setAttribute('data-cc-icon-alt', STX_FIRMWARE_ICON_FALLBACK);
    } else if (typeof iconUrl === 'string' && iconUrl.indexOf('./assets/img/dlc-firmware/') === 0){
      opt.setAttribute('data-cc-icon-alt', STX_FIRMWARE_ICON_FALLBACK);
    }
  }

  /** Simple Builder tick lists are plain labels (not `<select>`); attach a small preview icon when resolvable. */
  function stxAttachTickRowPartIcon(row, part, schemaItem, category){
    if (!row || !part || !schemaItem) return;
    const iconUrl = stxResolvePartIconUrl(part, schemaItem, category);
    if (!iconUrl) return;
    const im = document.createElement('img');
    im.alt = '';
    im.loading = 'lazy';
    im.decoding = 'async';
    im.className = 'stx-tick-row-part-icon';
    im.src = iconUrl;
    const passiveAlt = (typeof iconUrl === 'string' && iconUrl.indexOf('./assets/img/classmod-perks/') === 0)
      ? iconUrl.replace('/classmod-perks/', '/classmod-passive/')
      : '';
    im.addEventListener('error', function onImgErr(){
      if (!im.__stxTickTriedPassive && passiveAlt && String(im.src || '').indexOf(passiveAlt) === -1){
        im.__stxTickTriedPassive = true;
        im.src = passiveAlt;
        return;
      }
      if (!im.__stxTickTriedMiss){
        im.__stxTickTriedMiss = true;
        try {
          im.style.visibility = 'hidden';
          im.style.opacity = '0';
          im.removeAttribute('src');
        } catch (_) {}
        return;
      }
      im.removeEventListener('error', onImgErr);
    });
    row.appendChild(im);
  }

  function stxEnhancementCoreEffectText(p){
    try{
      if (!p || !window.__ENHANCEMENT_PAYLOAD || !window.__ENHANCEMENT_PAYLOAD.manufacturers) return '';
      const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
      if (!/enhancement\./.test(c) || !/part_core_|core_augment/.test(c)) return '';
      const rowName = stxFoldDiacriticsForPerkIconKey(String(p.name || p.legendaryName || ''))
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '');
      if (!rowName) return '';
      const mfgs = window.__ENHANCEMENT_PAYLOAD.manufacturers || {};
      for (const key of Object.keys(mfgs)){
        const perks = (mfgs[key] && Array.isArray(mfgs[key].perks)) ? mfgs[key].perks : [];
        for (const rec of perks){
          const full = String(rec && rec.name || '').trim();
          if (!full) continue;
          const m = full.match(/^(.+?)\s*[-–]\s*(.+)$/);
          const title = stxFoldDiacriticsForPerkIconKey(m ? m[1] : full)
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '');
          if (title && title === rowName) return (m ? m[2] : full).trim();
        }
      }
    }catch(_e){}
    return '';
  }
  try {
    window.stxPearlGearCatalogRowForPart = stxPearlGearCatalogRowForPart;
    window.stxEnhancementCoreEffectText = stxEnhancementCoreEffectText;
  } catch (_e) {}

  /** In-game / card “red text” (flavor quote) — catalog only; see partEffectDescForDropdown for abilities. */
  function stxPartRedTextSubForDropdown(p){
    if (typeof window.partRedTextForDropdown === 'function') {
      try { return String(window.partRedTextForDropdown(p) || '').trim(); } catch (_e) {}
    }
    const row = stxPearlGearCatalogRowForPart(p);
    const red = row && row.redText ? String(row.redText).trim() : '';
    return red.length > 240 ? red.slice(0, 237) + '…' : red;
  }

  function stxBarrelSlotLegendaryPrimaryTone(p, schemaItem, category){
    if (!p || !schemaItem) return false;
    if (!isBarrelFamilySchemaSlot(schemaItem, category)) return false;
    if (stxPartLooksLegendaryBarrel(p) || stxPartCarriesLegendaryEffectWeaponFamilyBarrel(p)) return true;
    return false;
  }

  function stxApplySlotPartOptionDecoration(opt, p, schemaItem, category){
    if (!opt || !p || !schemaItem) return;
    opt.removeAttribute('data-cc-icon');
    opt.removeAttribute('data-cc-icon-filter');
    opt.removeAttribute('data-cc-icon-alt');
    opt.removeAttribute('data-cc-grenade-rarity-match');
    const iconUrl = stxResolvePartIconUrl(p, schemaItem, category);
    if (iconUrl) stxSetOptionDataCcIconFromUrl(opt, iconUrl);
    if (typeof window.stxApplyPartDropdownMeta === 'function') {
      try {
        window.stxApplyPartDropdownMeta(opt, p, {
          isBarrelSlot: isBarrelFamilySchemaSlot(schemaItem, category),
          allowLegendaryTone: true
        });
      } catch (_e) {}
    } else {
      const redSub = stxPartRedTextSubForDropdown(p);
      if (redSub) opt.setAttribute('data-cc-barrel-sub', redSub);
      else opt.removeAttribute('data-cc-barrel-sub');
      if (stxBarrelSlotLegendaryPrimaryTone(p, schemaItem, category)) opt.setAttribute('data-cc-primary-tone', 'legendary');
      else opt.removeAttribute('data-cc-primary-tone');
    }
    /* After meta: Class Mod legendary bodies — gold-fill flat icons, or legendary text tone for portraits. */
    if (String(category || '').trim() === 'Class Mod' && (
      String(schemaItem.key || '') === 'body' ||
      String(schemaItem.key || '') === 'mainBody' ||
      String(schemaItem.partType || '').toLowerCase() === 'body' ||
      stxIsClassModBodyPoolCode(p.code || p.spawnCode || '')
    )) {
      stxApplyClassModBodyLegendaryIconFilter(opt, p);
    }
    /* Grenade Body: highlight the variant that matches the selected rarity id. */
    if (String(category || '').trim() === 'Grenade' && String(schemaItem.key || '') === 'body') {
      try {
        const rp0 = state.mainPart && String(state.mainPart.partType || '').trim().toLowerCase() === 'rarity'
          ? state.mainPart
          : (state.slots && state.slots.rarity);
        const rp = Array.isArray(rp0) ? rp0[0] : rp0;
        const suf = stxGrenadeRarityBodySuffixFromPart(rp);
        const c = String(normCode(p.code || '') || '').toLowerCase();
        if (suf && stxGrenadeBodyCodeMatchesRaritySuffix(c, suf)) {
          opt.setAttribute('data-cc-grenade-rarity-match', '1');
          opt.setAttribute('data-cc-primary-tone', 'legendary');
          const base = String(opt.textContent || opt.label || '').trim();
          if (base && base.indexOf('★') !== 0) {
            opt.textContent = '★ ' + base;
            try { opt.setAttribute('data-base-label', '★ ' + base); } catch (_e) {}
          }
        }
      } catch (_e) {}
    }
  }

  let __rarityRowsCacheKey = '';
  let __rarityRowsCacheVal = null;

  function getRarityRowsForCurrentContext(){
    const table = (typeof STX_RARITIES !== 'undefined' && Array.isArray(STX_RARITIES)) ? STX_RARITIES : (Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : []);
    const guided = getGuidedContext();
    const simpleItem = stxNormalizeSimpleBuilderItemTypeUi(String(
      (state && state.itemType) ||
      (($('itemType') && $('itemType').value) ? $('itemType').value : '')
    ).trim());
    const guidedItem = guided ? stxNormalizeSimpleBuilderItemTypeUi(String(guided.itemType || '').trim()) : '';
    /* Only borrow Guided context when it matches the active Simple item type.
       Otherwise Guided Weapon/etc. steals rarity rows and empties Class Mod / gear dropdowns. */
    const useGuided = !!(guidedItem && (!simpleItem || guidedItem === simpleItem ||
      (stxSimpleBuilderItemTypeIsHeavyUi(guidedItem) && stxSimpleBuilderItemTypeIsHeavyUi(simpleItem))));
    const man = useGuided ? guided.manufacturer : (($('manufacturer') && $('manufacturer').value) || (state && state.manufacturer) || '');
    if (!useGuided && state) state.manufacturer = man;
    const allMansEl = useGuided ? document.getElementById('ccGuidedAllManufacturers') : null;
    const useAllMfr = useGuided ? !!(allMansEl && allMansEl.checked) : (typeof isAllPartsEnabled === 'function' ? isAllPartsEnabled() : false);
    const catUi = stxNormalizeSimpleBuilderItemTypeUi(useGuided ? guidedItem : simpleItem);
    const gWt = useGuided && guided ? guided.weaponType : undefined;
    const cat   = stxSimpleBuilderItemTypeIsHeavyUi(catUi, gWt) ? 'Weapon' : catUi;

    const wtypeRaw = useGuided
      ? ((cat === 'Weapon' && stxSimpleBuilderItemTypeIsHeavyUi(catUi, guided.weaponType)) ? 'Heavy Weapon' : (guided.weaponType || (cat === 'Weapon' ? 'Assault Rifle' : '')))
      : ((cat === 'Weapon' && stxSimpleBuilderItemTypeIsHeavyUi(catUi)) ? 'Heavy Weapon' :
      ((cat === 'Weapon' && $('weaponType')) ? ($('weaponType').value || (state && state.weaponType) || '') : ((state && state.weaponType) || '')));

    const wtypeNorm = (String(wtypeRaw) === 'Heavy') ? 'Heavy Weapon' : String(wtypeRaw || '');
    if (cat === 'Weapon' && !useGuided && state) state.weaponType = wtypeNorm;

    const itemType = (cat === 'Weapon') ? wtypeNorm : cat;
    let wantType = String(itemType || '').trim();
    if (cat === 'Weapon' && !wantType) {
      if (guided && guided.itemType) wantType = 'Assault Rifle';
    }
    const __cacheKey = [useGuided ? '1' : '0', man, useAllMfr ? '1' : '0', catUi, wtypeNorm, wantType].join('|');
    if (__cacheKey === __rarityRowsCacheKey && __rarityRowsCacheVal) return __rarityRowsCacheVal;
    const manL = String(man || '').trim().toLowerCase();
    const itemTypeMatches = (rowTypeRaw)=>{
      const rt = String(rowTypeRaw || '').trim();
      if (!rt || !wantType) return false;
      if (wantType === 'Heavy Weapon'){
        return (rt === 'Heavy Weapon' || rt === 'Heavy' || rt === 'HeavyWeapon');
      }
      return rt === wantType;
    };

    const isPearlRow = (r)=>{
      const item = Number(r && ((r.itemId != null) ? r.itemId : r.id));
      const code = String((r && (r.itemTypeString || r.code)) || '').toLowerCase();
      if (Number.isFinite(item) && item >= 51 && item <= 60) return true;
      return code.includes('pearl_') || /(?:^|[._])comp_06_pearlescent/.test(code);
    };

    const isClassModCtx = /class\s*mod/i.test(String(cat || '')) || /class\s*mod/i.test(String(wantType || ''));
    const manCmKey = isClassModCtx ? stxCanonicalClassModManufacturerKey(man) : '';
    let rows = table.filter(r => {
      if (wantType === 'Heavy Weapon' && stxIsGrenKitStxRarityRow(r)) return false;
      if (!itemTypeMatches(r && r.itemType)) return false;
      if (useAllMfr) return true;
      const rm = String(r && r.manufacturer || '').trim().toLowerCase();
      if (rm === manL) return true;
      // Class Mod: treat Dark Siren ≡ Siren ≡ Vex (and peers) so extract + live sheet rows both match.
      if (isClassModCtx && manCmKey) {
        return stxCanonicalClassModManufacturerKey(rm) === manCmKey;
      }
      /* Nexus grenade rarity rows often ship manufacturer "Weapon"; match via spawn prefix instead. */
      if ((wantType === 'Grenade' || catUi === 'Grenade' || cat === 'Grenade') && manL) {
        const blob = String((r && (r.itemTypeString || r.code)) || '').toLowerCase();
        if (blob && stxGrenadeGadgetRowMatchesSelectedManufacturer(blob, manL)) return true;
      }
      return false;
    });

    // Fallback when manufacturer-specific rows are missing.
    if (!rows.length){
      rows = table.filter(r => {
        if (wantType === 'Heavy Weapon' && stxIsGrenKitStxRarityRow(r)) return false;
        return itemTypeMatches(r && r.itemType);
      });
    }
    
    // Absolute fallback: if still empty, find anything that matches category or name
    if (!rows.length && cat) {
       rows = table.filter(r => {
         if (wantType === 'Heavy Weapon' && stxIsGrenKitStxRarityRow(r)) return false;
         return String(r && r.itemType || '').includes(cat);
       });
    }

    // Older rarity tables may not include pearlescent rows yet.
    // Keep pearlescent tier usable by injecting a stable fallback set.
    if (cat === 'Weapon'){
      const hasPearlRows = rows.some(isPearlRow);
      if (!hasPearlRows){
        const synthMan = String(man || '').trim();
        const synthType = String(wantType || 'Weapon').trim();
        const synth = PEARL_FALLBACK_ROWS.map(pr => ({
          manufacturer: synthMan,
          itemType: synthType,
          itemTypeString: pr.itemTypeString,
          familyId: 1,
          itemId: Number(pr.itemId),
          legendaryName: String(pr.legendaryName || ''),
          source: 'stx-simple-fallback'
        }));
        rows = rows.concat(synth);
      }
    }
    __rarityRowsCacheKey = __cacheKey;
    __rarityRowsCacheVal = rows;
    return rows;
  }

  /**
   * Community pearlescent rarity dual-brace ids (`fam:item`) from save-editor / community_pearlescent.
   * Pearl override prepends one after `||` for every category (guns, classmods, enhancements, …).
   * Weapons prefer a pearl from the same weapon type when available; everything else uses the base-game pool.
   * Never use DLC families (245/254/282/…) or nameless pearl_handling ids 51–60 — those fail on enhancements.
   */
  const STX_PEARL_OVERRIDE_BY_WEAPON_TYPE = {
    'Sniper Rifle': ['23:61', '24:83', '25:82', '26:84'],
    Shotgun: ['12:86', '9:101', '7:85', '11:82', '11:90'],
    'Assault Rifle': ['15:77', '27:81', '13:91', '15:79'],
    Pistol: ['6:78', '6:85', '2:80'],
    SMG: ['19:61', '21:90', '22:101', '20:70'],
    'Heavy Weapon': ['11:90', '21:90', '19:61'],
    Heavy: ['11:90', '21:90', '19:61']
  };
  /** True for base-game community pearl duals usable as Pearl override prepend (not DLC, not 51–60). */
  function stxIsBaseGameCommunityPearlKey(key){
    const m = String(key || '').trim().match(/^(\d+)\s*:\s*(\d+)$/);
    if (!m) return false;
    const fam = Number(m[1]);
    const id = Number(m[2]);
    if (!Number.isFinite(fam) || !Number.isFinite(id)) return false;
    /* Nameless pearl_handling / elemental pearl hooks — fail on enhancements (`{254:51}`). */
    if (id >= 51 && id <= 60) return false;
    /* DLC / high TypeIDs (grenade 245, DLC pearl host 254, heavy DLC 282, …). */
    if (fam >= 200) return false;
    return true;
  }
  const STX_PEARL_OVERRIDE_ID_POOL = (function () {
    const out = [];
    const seen = Object.create(null);
    const groups = STX_PEARL_OVERRIDE_BY_WEAPON_TYPE;
    for (const k in groups) {
      if (!Object.prototype.hasOwnProperty.call(groups, k)) continue;
      const arr = groups[k] || [];
      for (let i = 0; i < arr.length; i++) {
        const id = String(arr[i] || '').trim();
        if (!id || seen[id] || !stxIsBaseGameCommunityPearlKey(id)) continue;
        seen[id] = true;
        out.push(id);
      }
    }
    return out.length ? out : ['21:90', '19:61', '11:90'];
  })();
  /** Fallback — Juliet (base-game weapon pearl). Never bare `{54}` / DLC `{254:51}` (mail won't open). */
  const STX_PEARL_OVERRIDE_FIXED_NON_WEAPON = '{21:90}';
  const STX_PEARL_OVERRIDE_FIXED_WEAPON = '{21:90}';

  function stxIsPearlTierStxRarityRow(r){
    const item = Number(r && ((r.itemId != null) ? r.itemId : r.id));
    const code = String((r && (r.itemTypeString || r.code)) || '').toLowerCase();
    if (Number.isFinite(item) && item >= 51 && item <= 60) return true;
    return code.includes('pearl_') || /(?:^|[._])comp_06_pearlescent/.test(code);
  }

  function stxPearlOverrideRowScore(r){
    const code = String((r && (r.itemTypeString || r.code)) || '').toLowerCase();
    let s = 0;
    if (!String(r && r.legendaryName || '').trim()) s += 4;
    if (/(?:^|[._])comp_06_pearlescent/.test(code)) s += 3;
    if (code.includes('comp_06')) s += 1;
    return s;
  }

  function stxPearlRaritiesTable(){
    return (typeof STX_RARITIES !== 'undefined' && Array.isArray(STX_RARITIES))
      ? STX_RARITIES
      : (Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : []);
  }

  /**
   * Same itemId as the pearl row we want, but a family different from the header — avoids `{9:51}` compacting to `{51}`
   * and colliding with the rarity slot when the item family is also 9.
   */
  function stxPearlForeignFamilyForPearlItemId(pearlItemId, baseFamilyId){
    const pid = Number(pearlItemId);
    const bf = Number(baseFamilyId);
    if (!Number.isFinite(pid) || pid < 51 || pid > 60) return null;
    if (!Number.isFinite(bf)) return null;
    const table = stxPearlRaritiesTable();
    const cands = table.filter(r =>
      Number(r && r.familyId) !== bf &&
      stxIsPearlTierStxRarityRow(r) &&
      Number((r.itemId != null) ? r.itemId : r.id) === pid
    );
    if (!cands.length) return null;
    cands.sort((a, b) => Number(a.familyId) - Number(b.familyId));
    return Number(cands[0].familyId);
  }

  /** Any base-game community pearl brace from a non-header family (fallback — never nameless 51–60 / DLC). */
  function stxPearlForeignBraceTokenFromTable(baseFamilyId){
    const bf = Number(baseFamilyId);
    const pool = STX_PEARL_OVERRIDE_ID_POOL.filter((k) => {
      if (!stxIsBaseGameCommunityPearlKey(k)) return false;
      if (!Number.isFinite(bf)) return true;
      const fam = Number(String(k).split(':')[0]);
      return fam !== bf;
    });
    if (pool.length) {
      const pick = pool[Math.floor(Math.random() * pool.length)] || '21:90';
      return `{${String(pick).replace(/\s+/g, '')}}`;
    }
    return STX_PEARL_OVERRIDE_FIXED_NON_WEAPON;
  }

  /**
   * If `{fam:itemId}` uses the same family as the serialized header, rewrite to a foreign-family pearl token
   * (keep itemId when another family has that pearlescent row; otherwise pick another foreign pearl row).
   */
  function stxRewritePearlOverrideIfSameFamilyAsHeader(dualBraceTok, baseFamilyId){
    const m = String(dualBraceTok || '').trim().match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
    if (!m) return dualBraceTok;
    const fam = Number(m[1]);
    const id = Number(m[2]);
    const bf = Number(baseFamilyId);
    if (!Number.isFinite(fam) || !Number.isFinite(id) || !Number.isFinite(bf)) return dualBraceTok;
    if (fam !== bf) return dualBraceTok;
    /* Never rewrite onto nameless 51–60 / DLC hosts — pick another base-game community pearl. */
    return stxPearlForeignBraceTokenFromTable(bf);
  }

  /** Pick a random base-game community pearl rarity id and format as `{fam:item}`. */
  function stxRandomPearlOverrideBraceRaw(preferWeaponType){
    const full = STX_PEARL_OVERRIDE_ID_POOL;
    let pool = full;
    const wt = String(preferWeaponType || '').trim();
    if (wt) {
      const map = STX_PEARL_OVERRIDE_BY_WEAPON_TYPE;
      let typed = map[wt];
      if (!typed || !typed.length) {
        const lo = wt.toLowerCase();
        if (lo === 'sniper' || lo === 'sniper rifle') typed = map['Sniper Rifle'];
        else if (lo === 'submachine gun' || lo === 'smg') typed = map.SMG;
        else if (lo === 'assault rifle' || lo === 'ar') typed = map['Assault Rifle'];
        else if (lo === 'heavy' || lo === 'heavy weapon') typed = map['Heavy Weapon'];
        else if (lo === 'shotgun') typed = map.Shotgun;
        else if (lo === 'pistol') typed = map.Pistol;
      }
      if (typed && typed.length) {
        const filtered = typed.filter(stxIsBaseGameCommunityPearlKey);
        if (filtered.length) pool = filtered;
      }
    }
    if (!pool || !pool.length) pool = full;
    if (!pool || !pool.length) return STX_PEARL_OVERRIDE_FIXED_NON_WEAPON;
    const pick = pool[Math.floor(Math.random() * pool.length)] || '21:90';
    return `{${String(pick).replace(/\s+/g, '')}}`;
  }

  /**
   * Pearl override for every category: prepend a base-game **weapon** community pearl dual-brace
   * (e.g. `{21:90}` Juliet). Never bare `{54}` / nameless 51–60 / DLC TypeIDs — those fail to open in mail.
   * Weapons may prefer same weapon-type pool; enhancements/classmods/shields use the full base-game pool.
   */
  function stxPickPearlOverrideBraceToken(baseFamilyId, isWeapon, category, weaponType){
    const bf = Number(baseFamilyId);
    const cat = String(category || '').trim();
    const weaponish =
      isWeapon || cat === 'Weapon' || cat === 'Heavy' || cat === 'Heavy Weapon';
    const preferWt = weaponish
      ? (weaponType || (typeof state !== 'undefined' && state && state.weaponType) || '')
      : '';
    const raw = stxRandomPearlOverrideBraceRaw(preferWt);
    if (!Number.isFinite(bf)) return raw;
    return stxRewritePearlOverrideIfSameFamilyAsHeader(raw, bf);
  }

  /** Weapon rarity families — never use these as Class Mod pearl hooks (card decodes as that gun type). */
  function stxPearlFamilyLooksLikeGun(familyId){
    const fam = Number(familyId);
    if (!Number.isFinite(fam)) return false;
    const table = stxPearlRaritiesTable();
    const rows = table.filter(r => Number(r && r.familyId) === fam);
    if (!rows.length) return false;
    return rows.some(r => {
      const it = String(r && r.itemType || '').trim();
      const code = String((r && (r.itemTypeString || r.code)) || '').toLowerCase();
      if (/^(Assault Rifle|Pistol|Shotgun|SMG|Sniper|Heavy|Submachine Gun|Sniper Rifle|Heavy Weapon)$/i.test(it)) return true;
      return /(?:^|[._])(?:ps|sg|sm|ar|sr|hw)(?:[._]|$)/.test(code) || /\bTED_SG\b|\bDAD_SG\b|\bJAK_SG\b/i.test(code);
    });
  }

  function stxPickClassModPearlOverrideBraceToken(baseFamilyId){
    /* Same base-game weapon community pearl prepend as enhancements. */
    return stxPickPearlOverrideBraceToken(baseFamilyId, false, 'Class Mod', '');
  }

  function stxLooksLikePearlOverrideLeadTok(tok){
    const s = String(tok || '').replace(/\s+/g, '');
    const bare = s.match(/^\{\s*(\d+)\s*\}$/);
    if (bare) {
      const id = Number(bare[1]);
      return Number.isFinite(id) && id >= 51 && id <= 60;
    }
    const dual = s.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
    if (!dual) return false;
    const key = `${dual[1]}:${dual[2]}`;
    if (STX_PEARL_OVERRIDE_ID_POOL.indexOf(key) >= 0) return true;
    const id = Number(dual[2]);
    return Number.isFinite(id) && id >= 51 && id <= 60;
  }

  /**
   * Pearl override = prepend a base-game weapon community pearl dual after `||`. No replace.
   * Enhancement: `|| {4} …` → `|| {21:90} {4} …`. Never bare `{54}` (mail won't open).
   */
  function stxApplyPearlRarityOnlyToTailSeq(parts, pearlRaw, baseFamilyId, _category){
    const p = String(pearlRaw || '').trim() || stxRandomPearlOverrideBraceRaw('');
    return stxPrependPearlOverrideToTailSeq(parts, p, baseFamilyId);
  }

  /** Replace leading rarity brace (legacy helper — pearl-override checkbox uses prepend). */
  function stxReplacePearlOverrideOnTailSeq(parts, pearlRaw, baseFamilyId){
    const p = String(pearlRaw || '').trim() || stxPearlOverrideNormalized(pearlRaw, baseFamilyId);
    if (!p) return parts;
    const arr = Array.isArray(parts) ? parts.slice() : [];
    if (arr.length) {
      const first = String(arr[0] || '').replace(/\s+/g, '');
      if (/^\{\d+(?::\d+)?\}$/.test(first)) arr.shift();
    }
    if (arr.length && stxPearlTokensDuplicateForOverride(arr[0], p, baseFamilyId)) return arr;
    return [p].concat(arr);
  }


  function isStxSimplePearlOverrideChecked(){
    return stxIsPearlOverrideUiActive();
  }

  /**
   * Pearl override tokens must stay explicitly `{family:itemId}` in output — never bare `{id}` from same-family compaction.
   * When the pearl family equals the header family (e.g. `{9:51}` → `{51}`), rewrite to a foreign-family pearl token.
   */
  function stxPearlOverrideNormalized(tok, baseFamilyId){
    const t = String(tok || '').trim();
    if (!t) return '';
    const dualIn = t.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
    if (dualIn){
      const fam = Number(dualIn[1]);
      const id = Number(dualIn[2]);
      if (Number.isFinite(fam) && Number.isFinite(id)){
        /* Never emit nameless 51–60 (bare or dual) — those break mail open. */
        if (id >= 51 && id <= 60) return stxPearlForeignBraceTokenFromTable(baseFamilyId);
        if (fam >= 200) return stxPearlForeignBraceTokenFromTable(baseFamilyId);
        return stxRewritePearlOverrideIfSameFamilyAsHeader(`{${fam}:${id}}`, baseFamilyId);
      }
    }
    const bareIn = t.replace(/\s+/g, '').match(/^\{(5[1-9]|60)\}$/);
    if (bareIn) return stxPearlForeignBraceTokenFromTable(baseFamilyId);
    const bf = Number(baseFamilyId);
    const norm = normalizeIdTokensForBaseFamilyWithPrefs([t], bf);
    let out = (norm && norm.length) ? String(norm[0]).trim() : t;
    const bareOut = out.match(/^\{\s*(\d+)\s*\}$/);
    if (bareOut && Number.isFinite(bf)){
      const bid = Number(bareOut[1]);
      if (bid >= 51 && bid <= 60) return stxPearlForeignBraceTokenFromTable(baseFamilyId);
      return stxRewritePearlOverrideIfSameFamilyAsHeader(`{${bf}:${bid}}`, baseFamilyId);
    }
    return out;
  }

  function stxPearlTokensDuplicateForOverride(a, b, baseFamilyId){
    const na = stxPearlOverrideNormalized(a, baseFamilyId);
    const nb = stxPearlOverrideNormalized(b, baseFamilyId);
    if (!na || !nb) return false;
    return na.replace(/\s+/g, '') === nb.replace(/\s+/g, '');
  }

  function stxPrependPearlOverrideToTailSeq(parts, pearlRaw, baseFamilyId){
    /* Always a base-game weapon community dual — never leave bare `{54}` in the serial. */
    const raw = String(pearlRaw || '').trim().replace(/\s+/g, '');
    let p = raw;
    if (/^\{\d+:\d+\}$/.test(raw)) {
      const m = raw.match(/^\{(\d+):(\d+)\}$/);
      const fam = m ? Number(m[1]) : NaN;
      const id = m ? Number(m[2]) : NaN;
      if ((Number.isFinite(id) && id >= 51 && id <= 60) || (Number.isFinite(fam) && fam >= 200)) {
        p = stxPearlForeignBraceTokenFromTable(baseFamilyId);
      } else {
        p = stxRewritePearlOverrideIfSameFamilyAsHeader(raw, baseFamilyId);
      }
    } else if (/^\{(5[1-9]|60)\}$/.test(raw)) {
      p = stxPearlForeignBraceTokenFromTable(baseFamilyId);
    } else {
      p = stxPearlOverrideNormalized(pearlRaw, baseFamilyId) || STX_PEARL_OVERRIDE_FIXED_NON_WEAPON;
    }
    if (!p || !/^\{\d+:\d+\}$/.test(String(p).replace(/\s+/g, ''))) {
      p = STX_PEARL_OVERRIDE_FIXED_NON_WEAPON;
    }
    if (!p) return parts;
    const arr = Array.isArray(parts) ? parts.slice() : [];
    const first = arr.length ? String(arr[0] || '').replace(/\s+/g, '') : '';
    if (first && first === p.replace(/\s+/g, '')) return arr;
    if (first && stxPearlTokensDuplicateForOverride(first, p, baseFamilyId)) return arr;
    return [p].concat(arr);
  }

  function computeGuidedPrefix(){
    if (window.state) window.state.__seedEnabled = true;
    const guided = getGuidedContext();
    if (!guided || !guided.itemType) return '';

    // If we have an existing serial with a valid numeric prefix, try to preserve its familyId.
    // This prevents resets to 21 or 1 when UI dropdowns aren't perfectly matched yet.
    let preservedFamilyId = null;
    try {
      const deserEl = document.getElementById('guidedOutputDeserialized');
      const cur = String((deserEl && deserEl.value) || '').trim();
      if (cur) {
        const dbl = cur.indexOf('||');
        const prefixStr = dbl >= 0 ? cur.slice(0, dbl).trim() : cur.trim();
        const m = prefixStr.match(/^\s*(\d+)\s*[,\|]/) || prefixStr.match(/^\s*(\d+)/);
        if (m) preservedFamilyId = Number(m[1]);
      }
    } catch (_) {}

    /* Prefer the Guided Rarity ID dropdown (same role as Simple #mainPart) so grenade/repkit
       headers match the selected rarity family instead of an arbitrary STX_RARITIES row. */
    let selectedRarityPart = null;
    try {
      if (typeof window.__ccGetSelectedGuidedRarityPart === 'function') {
        selectedRarityPart = window.__ccGetSelectedGuidedRarityPart();
      }
    } catch (_) {}

    const rows = getRarityRowsForCurrentContext();
    const pick = rows.find(r => !String(r && r.legendaryName || '').trim()) || rows[0] || null;
    
    const level = Number(guided.level) || 60;
    const firmwareLockEl = document.getElementById('ccGuidedFirmwareLockFlag');
    const buybackEl = document.getElementById('ccGuidedBuybackFlag');
    const firmwareLock = !!(
      (window.state && window.state.lockFirmware) ||
      (document.getElementById('firmwareLock') && document.getElementById('firmwareLock').checked) ||
      (firmwareLockEl && firmwareLockEl.checked)
    );
    const buyback = !!(
      (window.state && window.state.buybackFlag) ||
      (document.getElementById('buybackFlag') && document.getElementById('buybackFlag').checked) ||
      (buybackEl && buybackEl.checked)
    );
    
    const selFam = selectedRarityPart ? partFamilyIdOf(selectedRarityPart) : null;
    const selItem = selectedRarityPart ? partItemIdOf(selectedRarityPart) : null;

    // Prioritize preserved familyId if it belongs to the current manufacturer/type context.
    // (We check if it exists in 'rows' to be safe, but allow it if rows are somehow broken).
    let familyId = Number.isFinite(selFam) ? Number(selFam)
      : ((pick && Number.isFinite(Number(pick.familyId))) ? Number(pick.familyId) : 1);
    if (!Number.isFinite(selFam) && preservedFamilyId != null) {
       // If the preserved ID matches ANY row in the current context, definitely use it.
       if (rows.some(r => Number(r.familyId || r.family) === preservedFamilyId)) {
          familyId = preservedFamilyId;
       } else if (!rows.length || (pick && familyId === 1 && preservedFamilyId !== 1)) {
          // If rows is empty or we fell back to 1, trust the preserved ID more.
          familyId = preservedFamilyId;
       }
    }

    const itemId = Number.isFinite(selItem) ? Number(selItem)
      : ((pick && Number.isFinite(Number(pick.itemId))) ? Number(pick.itemId) : 0);
    const seedBase = { familyId: familyId, itemId: itemId };
    
    let header = `${familyId}, 0, 1, ${level}|`;
    header += (typeof stxBuildSerialHeaderSuffix === 'function')
      ? stxBuildSerialHeaderSuffix(getSeed(seedBase), firmwareLock, buyback)
      : (`${firmwareLock ? ' 9, 1|' : ''}${buyback ? ' 10, 1|' : ''} 2, ${getSeed(seedBase)}||`);
    return header;
  }

  function partFamilyIdOf(p){
    if (!p) return null;
    if (p.familyId != null && Number.isFinite(Number(p.familyId))) return Number(p.familyId);
    if (p.family != null && Number.isFinite(Number(p.family))) return Number(p.family);
    const idRaw = String((p.idRaw ?? p.idraw ?? '') || '').trim();
    const m = idRaw.match(/^(\d+)\s*:/);
    if (m) return Number(m[1]);
    const enhFam = stxEnhancementTypeFamilyIdFromSpawnCode(String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase());
    return enhFam != null ? enhFam : null;
  }

  function partItemIdOf(p){
    if (!p) return null;
    if (p.id != null && Number.isFinite(Number(p.id))) return Number(p.id);
    if (p.itemId != null && Number.isFinite(Number(p.itemId))) return Number(p.itemId);
    const idRaw = String((p.idRaw ?? p.idraw ?? '') || '').trim();
    const m = idRaw.match(/^\d+\s*:\s*(\d+)\s*$/);
    if (m) return Number(m[1]);
    const bare = idRaw.match(/^(\d+)$/);
    if (bare && (p.id == null || !Number.isFinite(Number(p.id))) && (p.itemId == null || !Number.isFinite(Number(p.itemId)))) {
      return Number(bare[1]);
    }
    return null;
  }

  /** Keys `familyId:itemId` from STX_RARITIES-style rows. Tier gates must use pairs, not separate fam + item sets (IDs collide across families). */
  function stxRarityPairKeyFromRow(r){
    const f = Number(r && r.familyId);
    const i = Number(r && r.itemId);
    if (!Number.isFinite(f) || !Number.isFinite(i)) return '';
    return `${f}:${i}`;
  }

  function stxRarityPairSetFromRows(rows){
    const set = new Set();
    if (!Array.isArray(rows)) return set;
    for (let i = 0; i < rows.length; i++){
      const k = stxRarityPairKeyFromRow(rows[i]);
      if (k) set.add(k);
    }
    return set;
  }

  function stxPartMatchesRarityPairSet(p, pairSet){
    if (!pairSet || !pairSet.size) return true;
    const f = partFamilyIdOf(p);
    const i = partItemIdOf(p);
    if (!Number.isFinite(f) || !Number.isFinite(i)) return false;
    return pairSet.has(`${f}:${i}`);
  }

  /** True if this STX_RARITIES row is grenade-kit (must never drive Heavy Weapon tier gates). */
  function stxIsGrenKitStxRarityRow(r){
    if (!r) return false;
    if (String(r.itemType || '').trim() === 'Grenade') return true;
    const blob = String((r.itemTypeString || r.code) || '').toLowerCase();
    if (blob.includes('grenade_gadget')) return true;
    return !!stxIsDatasetGrenadeGadgetSpawnCode(blob);
  }

  function stxBaseFamilyIdForCompactIds(){
    try{
      const main = state && state.mainPart ? state.mainPart : null;
      const fam = partFamilyIdOf(main);
      if (Number.isFinite(fam)) return Number(fam);
    }catch(_e){}
    return null;
  }

  function isPearlWeaponMainPart(p){
    if (!p) return false;
    const fam = partFamilyIdOf(p);
    const item = partItemIdOf(p);
    const key = (Number.isFinite(fam) && Number.isFinite(item)) ? `${Number(fam)}:${Number(item)}` : '';
    if (key && PEARL_WEAPON_MAINPART_ID_SET.has(key)) return true;
    const code = String(normCode(p && p.code || '') || '').toLowerCase();
    const name = String((p && p.name) || '').toLowerCase();
    for (let i=0; i<PEARL_WEAPON_MAINPART_HINTS.length; i++){
      const h = PEARL_WEAPON_MAINPART_HINTS[i];
      if (!h) continue;
      if (code.includes(h) || name.includes(h)) return true;
    }
    return false;
  }

  function setSelectOptions(sel, options, {placeholder='Select...', getLabel=(x)=>x, getValue=(x)=>x, groupBy=null, getTitle=null, decorateOption=null, appendIdRawToLabel=true, onComplete=null, chunked=null}={}){
    if (!sel) { if (typeof onComplete === 'function') onComplete(); return; }
    const baseGetLabel = getLabel;
    const baseDecorate = decorateOption;
    getLabel = (o) => stxMarkNewDropdownLabel(baseGetLabel(o), o);
    decorateOption = (opt, o) => {
      try {
        if (stxIsNewEditorItem(o)) {
          opt.setAttribute('data-stx-new', '1');
          const tip = String(opt.title || '').trim();
          if (!/\bnew\b/i.test(tip)) opt.title = tip ? `${tip} · New this update` : 'New this update';
        }
      } catch (_e) {}
      if (typeof baseDecorate === 'function') {
        try { baseDecorate(opt, o); } catch (_e2) {}
      }
    };
    sel.innerHTML = '';
    const ph = document.createElement('option');
    ph.value = '';
    ph.textContent = placeholder;
    sel.appendChild(ph);

    if (!options || !options.length) {
      if (typeof onComplete === 'function') onComplete();
      return;
    }

    const useChunked = chunked !== false && options.length > (stxPerfLiteUi() ? 60 : 120);
    if (useChunked) {
      setSelectOptionsChunked(sel, options, { getLabel, getValue, groupBy, getTitle, decorateOption, appendIdRawToLabel, onComplete });
      return;
    }

    const __ccSeen = new Set();
    const __logicalSeen = new Set();

    if (groupBy){
      const groups = new Map();
      for (const o of options){
        const __v = String(getValue(o));
        if (__ccSeen.has(__v)) continue;
        const lk = stxSelectLogicalDedupeKey(o);
        if (lk && __logicalSeen.has(lk)) continue;
        if (lk) __logicalSeen.add(lk);
        __ccSeen.add(__v);
        const g = groupBy(o) || 'Other';
        if (!groups.has(g)) groups.set(g, []);
        groups.get(g).push(o);
      }
      const __tierRank = (label)=>{
        const m = { 'Common':0, 'Uncommon':1, 'Rare':2, 'Epic':3, 'Legendary':4, 'Pearlescent':5, 'Unknown':6, 'Other':7 };
        const L = String(label || '');
        return Object.prototype.hasOwnProperty.call(m, L) ? m[L] : 50;
      };
      const entries = [...groups.entries()].sort((a, b) => (__tierRank(a[0]) - __tierRank(b[0])) || String(a[0]).localeCompare(String(b[0]), undefined, { numeric:true, sensitivity:'base' }));
      const flat = [];
      for (const [, arr] of entries){
        arr.sort((a, b) => String(getLabel(a)).localeCompare(String(getLabel(b)), undefined, { numeric:true, sensitivity:'base' }));
        for (const o of arr) flat.push(o);
      }
      for (const o of flat){
        const opt = document.createElement('option');
        opt.value = getValue(o);
        opt.textContent = getLabel(o);
        let tip = '';
        if (typeof getTitle === 'function') { try{ tip = String(getTitle(o) || '').trim(); }catch(_e){} }
        if (!tip && typeof window.partTooltipText === 'function') { try{ tip = String(window.partTooltipText(o) || '').trim(); }catch(_e){} }
        try{
          const __idRaw = (o && (o.idRaw ?? o.idraw ?? o.id_raw));
          if (__idRaw !== undefined && __idRaw !== null && String(__idRaw).trim()){
            const idS = String(__idRaw).trim();
            if (appendIdRawToLabel && !String(opt.textContent).includes(idS)){
              opt.textContent = `${opt.textContent} [${idS}]`;
            } else if (!appendIdRawToLabel && !tip.includes(idS)){
              tip = tip ? `${tip} | id: ${idS}` : `id: ${idS}`;
            }
          }
        }catch(_e){}
        if (tip) opt.title = tip;
        if (typeof decorateOption === 'function') { try{ decorateOption(opt, o); }catch(_e){} }
        sel.appendChild(opt);
      }
      if (typeof onComplete === 'function') onComplete();
      return;
    }

    for (const o of options){
      const __v = String(getValue(o));
      if (__ccSeen.has(__v)) continue;
      const lk = stxSelectLogicalDedupeKey(o);
      if (lk && __logicalSeen.has(lk)) continue;
      if (lk) __logicalSeen.add(lk);
      __ccSeen.add(__v);
      const opt = document.createElement('option');
      opt.value = getValue(o);
      opt.textContent = getLabel(o);
      let tip = '';
      if (typeof getTitle === 'function') { try{ tip = String(getTitle(o) || '').trim(); }catch(_e){} }
      if (!tip && typeof window.partTooltipText === 'function') { try{ tip = String(window.partTooltipText(o) || '').trim(); }catch(_e){} }
      try{
        const __idRaw = (o && (o.idRaw ?? o.idraw ?? o.id_raw));
        if (__idRaw !== undefined && __idRaw !== null && String(__idRaw).trim()){
          const idS = String(__idRaw).trim();
          if (appendIdRawToLabel && !String(opt.textContent).includes(idS)){
            opt.textContent = `${opt.textContent} [${idS}]`;
          } else if (!appendIdRawToLabel && !tip.includes(idS)){
            tip = tip ? `${tip} | id: ${idS}` : `id: ${idS}`;
          }
        }
      }catch(_e){}
      if (tip) opt.title = tip;
      if (typeof decorateOption === 'function') { try{ decorateOption(opt, o); }catch(_e){} }
      sel.appendChild(opt);
    }
    if (typeof onComplete === 'function') onComplete();
  }

  function setSelectOptionsChunked(sel, options, { getLabel, getValue, groupBy, getTitle, decorateOption, appendIdRawToLabel, onComplete }) {
    const __ccSeen = new Set();
    const __logicalSeen = new Set();
    let flat = options;
    if (groupBy) {
      const groups = new Map();
      for (const o of options) {
        const __v = String(getValue(o));
        if (__ccSeen.has(__v)) continue;
        const lk = stxSelectLogicalDedupeKey(o);
        if (lk && __logicalSeen.has(lk)) continue;
        if (lk) __logicalSeen.add(lk);
        __ccSeen.add(__v);
        const g = groupBy(o) || 'Other';
        if (!groups.has(g)) groups.set(g, []);
        groups.get(g).push(o);
      }
      flat = [];
      const entries = [...groups.entries()].sort((a, b) => String(a[0]).localeCompare(String(b[0]), undefined, { numeric: true, sensitivity: 'base' }));
      for (const [, arr] of entries) {
        arr.sort((a, b) => String(getLabel(a)).localeCompare(String(getLabel(b)), undefined, { numeric: true, sensitivity: 'base' }));
        for (const o of arr) flat.push(o);
      }
    }
    let idx = 0;
    const step = stxPerfLiteUi() ? 35 : 70;
    function appendOne(o) {
      const opt = document.createElement('option');
      opt.value = getValue(o);
      opt.textContent = getLabel(o);
      if (typeof getTitle === 'function') {
        try {
          const tip = String(getTitle(o) || '').trim();
          if (tip) opt.title = tip;
        } catch (_e) {}
      }
      if (typeof decorateOption === 'function') {
        try { decorateOption(opt, o); } catch (_e) {}
      }
      return opt;
    }
    function pump() {
      const end = Math.min(idx + step, flat.length);
      const fragment = document.createDocumentFragment();
      for (; idx < end; idx++) fragment.appendChild(appendOne(flat[idx]));
      sel.appendChild(fragment);
      if (idx < flat.length) {
        setTimeout(pump, stxPerfLiteUi() ? 16 : 0);
      } else if (typeof onComplete === 'function') {
        onComplete();
      }
    }
    pump();
  }

  let __legacyClassModMerged = false;

  function mergeLegacyClassModPartsIntoAllParts(opts){
    const force = !!(opts && opts.force);
    if (__legacyClassModMerged && !force) return;
    try{
      const src = (window.parent && window.parent.__LEGACY_CLASSMOD_PARTS_BY_KEY) ? window.parent.__LEGACY_CLASSMOD_PARTS_BY_KEY
                : (window.__LEGACY_CLASSMOD_PARTS_BY_KEY ? window.__LEGACY_CLASSMOD_PARTS_BY_KEY : null);
      if (!src) return;
      const all = getAllParts();
      if (!Array.isArray(all) || !all.length) return;

      // Track existing Character-category idRaw tokens so we don't duplicate the rows this merger owns.
      // (Classmod rows may already exist in ALL_PARTS with the same idRaw but under "Classmod".)
      const existing = new Set(
        all
          .filter(p => String((p && p.category) || '').trim() === 'Character')
          .map(p => String(p && p.idRaw ? p.idRaw : ''))
      );

      // Derive a family id per character key by matching the first Name+Skin row against the base dataset,
      // falling back to STX_RARITIES mapping when needed.
      const famByKey = {};
      for (const [key, list] of Object.entries(src)){
        if (!Array.isArray(list) || !list.length) continue;
        const first = list.find(r => Array.isArray(r) && r.length >= 2) || list[0];
        const pid = Number(first[0]);
        const pname = String(first[1] || '').trim();

        let fam = null;
        const hit = all.find(p => Number(p && p.id) === pid && String(p && p.name || '').trim() === pname && p.family != null);
        if (hit) fam = Number(hit.family);

        if (!fam){
          const cap = key ? (key.charAt(0).toUpperCase() + key.slice(1)) : '';
          const fallback = classModFamilyIdForCharacter(cap);
          if (fallback) fam = Number(fallback);
        }

        if (fam) famByKey[key] = fam;
      }

      // Materialize legacy rows as normal part objects so the builder can treat them like any other pool.
      for (const [key, list] of Object.entries(src)){
        if (!Array.isArray(list) || !list.length) continue;
        const fam = famByKey[key];
        if (!fam) continue;

        for (const row of list){
          if (!Array.isArray(row) || row.length < 2) continue;
          const id = Number(row[0]);
          const name = String(row[1] || '').trim();
          const kind = String(row[2] || '').trim(); // e.g., Skill, Perk, Rarity, Name+Skin
          const idRaw = `${fam}:${id}`;
          if (existing.has(idRaw)) continue;
          existing.add(idRaw);

          all.push({
            category: 'Character',
            manufacturer: 'characters',
            itemType: '',
            weaponType: '',
            partType: kind,
            // Use brace token for "code mode" compatibility; idRaw is used in numeric mode.
            code: `""{${fam}:${id}}""`,
            name,
            idRaw,
            family: fam,
            id
          });
        }
      }
      __legacyClassModMerged = true;
      __cachedItemTypeCategories = null;
      __cachedItemTypeCategoriesLen = 0;
    }catch(_e){}
  }

  try {
    window.__ccClassmodSkillsReady = function () {
      __legacyClassModMerged = false;
      try { mergeLegacyClassModPartsIntoAllParts({ force: true }); } catch (_e) {}
      try {
        if (typeof refreshTopSelectors === 'function') refreshTopSelectors({ deferHeavy: true });
      } catch (_e2) {}
      try {
        if (typeof refreshBuilder === 'function') refreshBuilder();
      } catch (_e3) {}
      try {
        if (typeof window.__ccClassmodChecklistRender === 'function') window.__ccClassmodChecklistRender();
      } catch (_e4) {}
    };
  } catch (_e) {}

  function classModFamilyIdForCharacter(charName){
    try{
      const rows = Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : [];
      const raw = String(charName || '').trim();
      if (!raw) return null;

      // Accept either internal family names (Siren/Paladin/Exo Soldier/Gravitar/Robodealer)
      // or displayed BL4 character names (Vex/Amon/Rafa/Harlowe) / Nexus "Dark Siren".
      const aliasByLower = { 'vex':'Siren', 'siren':'Siren', 'dark siren':'Siren', 'darksiren':'Siren', 'amon':'Paladin', 'paladin':'Paladin', 'rafa':'Exo Soldier', 'exo soldier':'Exo Soldier', 'harlowe':'Gravitar', 'gravitar':'Gravitar', 'c4sh':'Robodealer', 'robodealer':'Robodealer', 'loveless':'Corpohacker', 'corpohacker':'Corpohacker', 'corpo hacker':'Corpohacker', 'hacker':'Corpohacker', 'the hacker':'Corpohacker' };
      const lc = raw.toLowerCase();
      const name = aliasByLower[lc] || stxCanonicalizeManufacturerDisplayName(raw) || raw;
      const wantCmKey = stxCanonicalClassModManufacturerKey(name);

      // Primary: manufacturer match for Class Mod rows (alias-aware: Dark Siren ≡ Siren)
      let row = rows.find(r =>
        String(r && r.itemType || '') === 'Class Mod' &&
        (String(r && r.manufacturer || '').trim() === name ||
          (wantCmKey && stxCanonicalClassModManufacturerKey(r && r.manufacturer) === wantCmKey))
      );
      if (row && row.familyId != null) return row.familyId;

      // Fallback: match by itemTypeString slug (e.g., classmod_paladin...)
      // Siren family spawn codes use classmod_dark_siren.*, not classmod_siren.*.
      const slug = name.toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'');
      const slugAlts = (slug === 'siren') ? ['siren', 'dark_siren', 'darksiren'] : [slug];
      row = rows.find(r => {
        const it = String(r && r.itemType || '');
        const its = String(r && r.itemTypeString || '').toLowerCase();
        if (it !== 'Class Mod' && !/class\s*mod|classmod/i.test(its)) return false;
        return slugAlts.some(function (s) { return its.includes('classmod_' + s); });
      });
      if (row && row.familyId != null) return row.familyId;

      // Stable fallback when STX_RARITIES does not expose Class Mod rows.
      const famFallbackByLower = {
        vex: 254, siren: 254, 'dark siren': 254, darksiren: 254,
        amon: 255, paladin: 255,
        rafa: 256, 'exo soldier': 256, 'exo-soldier': 256, exosoldier: 256,
        harlowe: 259, gravitar: 259,
        c4sh: 404, robodealer: 404,
        loveless: 402, corpohacker: 402, 'corpo hacker': 402, hacker: 402, 'the hacker': 402
      };
      const fam = famFallbackByLower[lc] ?? famFallbackByLower[String(name || '').toLowerCase()];
      return Number.isFinite(Number(fam)) ? Number(fam) : null;
    }catch(_e){ return null; }
  }

  /**
   * Vault-hunter TypeID from class-mod spawn code when `family` is missing on the part row.
   * `classmod_paladin.*` must NOT hit the generic `classmod.*` → 234 pool rule (that caused `{234:n}` → bare `{n}` on wrong-family mods).
   */
  function stxClassModSpawnCodeVaultFamilyId(code){
    try{
      const c = String(normCode(code || '') || '').toLowerCase();
      if (!c) return NaN;
      const m1 = c.match(/^([a-z0-9_]+)_classmod\./);
      if (m1 && m1[1]){
        const k = String(m1[1]).replace(/[\s-]+/g, '');
        const byPrefix = {
          vex: 254, siren: 254,
          amon: 255, paladin: 255,
          rafa: 256, exosoldier: 256, exo: 256,
          harlowe: 259, gravitar: 259,
          c4sh: 404, robodealer: 404,
          loveless: 402, corpohacker: 402, hacker: 402
        };
        const fam = Number(byPrefix[k]);
        if (Number.isFinite(fam)) return fam;
      }
      const m2 = c.match(/^classmod_([a-z0-9_]+)\./i);
      if (m2 && m2[1]){
        const slug = String(m2[1]).replace(/_/g, ' ').trim();
        const low = slug.toLowerCase();
        if (low === 'universal' || low === 'firmware') return 234;
        const fam = classModFamilyIdForCharacter(slug);
        if (Number.isFinite(fam)) return fam;
      }
      return NaN;
    }catch(_e){ return NaN; }
  }

  function classModKeyForCharacter(charName){
    const raw = String(charName || '').trim().toLowerCase();
    if (!raw) return null;
    const byLower = {
      vex: 'vex', siren: 'vex', 'dark siren': 'vex', darksiren: 'vex',
      amon: 'amon', paladin: 'amon',
      rafa: 'rafa', 'exo soldier': 'rafa', 'exo-soldier': 'rafa', exosoldier: 'rafa',
      harlowe: 'harlowe', gravitar: 'harlowe',
      c4sh: 'c4sh', robodealer: 'c4sh',
      loveless: 'loveless', corpohacker: 'loveless', 'corpo hacker': 'loveless', hacker: 'loveless', 'the hacker': 'loveless'
    };
    return byLower[raw] || null;
  }

  /**
   * Dataset / legacy placeholder class-mod rows (Broken Red/Green/Blue/White, Broken??, etc.).
   * Also excludes Nexus supplement skill stubs like "Passive Blue 1 5 Tier 3" / passive_blue_* codes
   * that replaced real perk names and break classmod perk icon lookups.
   * Excluded from dropdowns, checklists, and search — not valid selectable perks/skills.
   */
  function stxIsBrokenClassmodDatasetPlaceholderPart(p){
    if (!p) return false;
    const nm = String((p.name || p.legendaryName || p.displayName) || '').trim();
    const code = String(normCode(p.code || '') || '').toLowerCase();
    const ef = String((p.effects || p.effect || p.effects_text || '') || '');
    const blob = (nm + ' ' + code + ' ' + ef).toLowerCase();
    if (/\bbroken\s*[-_]?\s*(red|green|blue|white)\b/i.test(blob)) return true;
    if (/\bbroken[\s_]*\?{2,}/i.test(blob) || /\bbroken\?{2,}/i.test(blob.replace(/\s+/g, ''))) return true;
    const nn = nm.toLowerCase().replace(/\s+/g, '');
    if (/broken(red|green|blue|white)/.test(nn)) return true;
    if (/^broken\?+$/.test(nn) || /^broken\?{3,}$/i.test(nn.replace(/\s+/g, ''))) return true;
    /* Nexus class-mod skill stubs (no real display names / icon stems). */
    if (/^passive\s+(blue|green|red|white|purple)\b/i.test(nm)) return true;
    if (/^action\s+skill\b/i.test(nm) && /\btier\s*\d+/i.test(nm)) return true;
    if (/^capstone\b/i.test(nm) && /\btier\s*\d+/i.test(nm)) return true;
    if (/(^|[._])passive_(blue|green|red|white|purple)(_|\d)/i.test(code)) return true;
    if (/(^|[._])action_skill_.*tier_/i.test(code)) return true;
    if (/(^|[._])capstone_.*tier_/i.test(code)) return true;
    if (/\bskill\s*test\b/i.test(nm) || /_skill_test\b/i.test(code) || /skilltest\b/i.test(nn)) return true;
    /* Unreleased / unnamed legendary stubs (no inv_name_part marketing name). */
    if (stxIsClassModUnnamedLegendaryStub(p)) return true;
    return false;
  }

  /**
   * Legendary class-mod rows that only have internal codenames (Raid3/Raid4/Harmonica)
   * and no player-facing name yet — hide from builders so lists show real names only.
   */
  function stxIsClassModUnnamedLegendaryStub(p){
    if (!p) return false;
    const code = String(normCode(p.code || p.spawnCode || '') || '').toLowerCase();
    if (/classmod_/.test(code) && /\.(?:leg_body_|comp_05_legendary_)(raid3|raid4|harmonica)(?:["']|$)/.test(code)) return true;
    const nm = String((p.name || p.legendaryName || p.displayName || p.effects || p.effect || '') || '')
      .trim()
      .toLowerCase()
      .replace(/[\s_-]+/g, '');
    /* Only unreleased stubs — raid1 has real names (Misericorde / Overdriver / …). */
    if (!/^(raid3|raid4|harmonica)$/.test(nm)) return false;
    /* Name-only stubs: hide when spawn is missing/token-only or also unnamed. */
    if (!code || /\{/.test(code)) return true;
    if (/(raid3|raid4|harmonica)/.test(code)) return true;
    /* Class-mod category with stub label and no mapped spawn → hide. */
    try {
      const catLo = String(p.category || p.itemType || '').toLowerCase().replace(/\s+/g, '');
      if (catLo === 'classmod' || catLo === 'character') return true;
    } catch (_e) {}
    return false;
  }
  try { window.stxIsClassModUnnamedLegendaryStub = stxIsClassModUnnamedLegendaryStub; } catch (_) {}

  /** Known DLC / raid legendary class-mod display names (spawn → in-game name). */
  const STX_CLASSMOD_DLC_DISPLAY_BY_SPAWN = {
    'classmod_dark_siren.leg_body_cowbell': 'Configuration',
    'classmod_dark_siren.comp_05_legendary_cowbell': 'Configuration',
    'classmod_dark_siren.leg_body_raid1': 'Misericorde',
    'classmod_dark_siren.comp_05_legendary_raid1': 'Misericorde',
    'classmod_dark_siren.leg_body_raid2': 'Grim Sister',
    'classmod_dark_siren.comp_05_legendary_raid2': 'Grim Sister',
    'classmod_dark_siren.leg_body_tuba': 'Living Weapon',
    'classmod_dark_siren.comp_05_legendary_tuba': 'Living Weapon',
    'classmod_exo_soldier.leg_body_cowbell': 'Reaparición',
    'classmod_exo_soldier.comp_05_legendary_cowbell': 'Reaparición',
    'classmod_exo_soldier.leg_body_raid1': 'Overdriver',
    'classmod_exo_soldier.comp_05_legendary_raid1': 'Overdriver',
    'classmod_exo_soldier.leg_body_raid2': 'Bombastic',
    'classmod_exo_soldier.comp_05_legendary_raid2': 'Bombastic',
    'classmod_exo_soldier.leg_body_tuba': 'Power-Puncher',
    'classmod_exo_soldier.comp_05_legendary_tuba': 'Power-Puncher',
    'classmod_gravitar.leg_body_cowbell': 'Phlebotomist',
    'classmod_gravitar.comp_05_legendary_cowbell': 'Phlebotomist',
    'classmod_gravitar.leg_body_raid1': 'Trooper',
    'classmod_gravitar.comp_05_legendary_raid1': 'Trooper',
    'classmod_gravitar.leg_body_raid2': 'Plasmaphile',
    'classmod_gravitar.comp_05_legendary_raid2': 'Plasmaphile',
    'classmod_gravitar.leg_body_tuba': 'Chirurgeon',
    'classmod_gravitar.comp_05_legendary_tuba': 'Chirurgeon',
    'classmod_paladin.leg_body_cowbell': 'Tempest',
    'classmod_paladin.comp_05_legendary_cowbell': 'Tempest',
    'classmod_paladin.leg_body_raid1': 'Lamplighter',
    'classmod_paladin.comp_05_legendary_raid1': 'Lamplighter',
    'classmod_paladin.leg_body_raid2': 'Artificer',
    'classmod_paladin.comp_05_legendary_raid2': 'Artificer',
    'classmod_paladin.leg_body_tuba': 'Damned',
    'classmod_paladin.comp_05_legendary_tuba': 'Damned',
    'classmod_robodealer.leg_body_raid1': 'Hooligan',
    'classmod_robodealer.comp_05_legendary_raid1': 'Hooligan',
    'classmod_robodealer.leg_body_raid2': 'Prestidigitator',
    'classmod_robodealer.comp_05_legendary_raid2': 'Prestidigitator',
    'classmod_robodealer.leg_body_tuba': 'Trainer',
    'classmod_robodealer.comp_05_legendary_tuba': 'Trainer',
    'classmod_corpohacker.leg_body_01': 'Devourer',
    'classmod_corpohacker.comp_05_legendary_01': 'Devourer',
    'classmod_corpohacker.leg_body_02': 'Virophile',
    'classmod_corpohacker.comp_05_legendary_02': 'Virophile',
    'classmod_corpohacker.leg_body_03': 'Montage Maker',
    'classmod_corpohacker.comp_05_legendary_03': 'Montage Maker',
    'classmod_corpohacker.leg_body_04': 'Memory Hoarder',
    'classmod_corpohacker.comp_05_legendary_04': 'Memory Hoarder',
    'classmod_corpohacker.leg_body_05': 'Trackstar',
    'classmod_corpohacker.comp_05_legendary_05': 'Trackstar',
    'classmod_corpohacker.leg_body_06': 'Functional Human',
    'classmod_corpohacker.comp_05_legendary_06': 'Functional Human',
    'classmod_corpohacker.leg_body_dlc1': 'Martyr',
    'classmod_corpohacker.comp_05_legendary_dlc1': 'Martyr',
    'classmod_corpohacker.leg_body_cowbell': 'Martyr',
    'classmod_corpohacker.comp_05_legendary_cowbell': 'Martyr',
    'classmod_corpohacker.leg_body_dlc2': 'Programmer',
    'classmod_corpohacker.comp_05_legendary_dlc2': 'Programmer',
    'classmod_corpohacker.leg_body_harmonica': 'Programmer',
    'classmod_corpohacker.comp_05_legendary_harmonica': 'Programmer',
    'classmod_corpohacker.leg_body_raid1': 'Boomer',
    'classmod_corpohacker.comp_05_legendary_raid1': 'Boomer',
    'classmod_corpohacker.leg_body_raid2': 'Plague Engineer',
    'classmod_corpohacker.comp_05_legendary_raid2': 'Plague Engineer',
    'classmod_corpohacker.leg_body_tuba': 'Puppetmaster',
    'classmod_corpohacker.comp_05_legendary_tuba': 'Puppetmaster'
  };

  /** Resolve player-facing class-mod part name (never Raid3 / Harmonica stubs). */
  function stxResolveClassModPartDisplayName(p){
    if (!p) return '';
    const code = String(normCode(p.code || p.spawnCode || '') || '').toLowerCase();
    if (STX_CLASSMOD_DLC_DISPLAY_BY_SPAWN[code]) return STX_CLASSMOD_DLC_DISPLAY_BY_SPAWN[code];
    let nm = String((p.name || p.legendaryName || p.displayName || '') || '').trim();
    nm = nm.replace(/^part_|^comp_/i, '').replace(/_/g, ' ').trim();
    const nmKey = nm.toLowerCase().replace(/[\s_-]+/g, '');
    if (/^(raid\d+|harmonica|cowbell|tuba|dlc\d+)$/i.test(nmKey) || /^raid\s*\d+$/i.test(nm) || /^leg\s*body\s*\d+$/i.test(nm)) {
      /* Mapped spawn already checked; leave blank rather than show internal slug. */
      return '';
    }
    return nm;
  }
  try { window.stxResolveClassModPartDisplayName = stxResolveClassModPartDisplayName; } catch (_) {}

  /** Class-mod body rows (`classmod_paladin.body_01`, `leg_body_*`) often ship with empty `partType` in the dataset. */
  function stxIsClassModBodyPoolCode(code){
    const c = String(normCode(code || '') || '').toLowerCase();
    if (!c) return false;
    if (/\.comp_/.test(c) || /comp_0[1-6]_/.test(c)) return false;
    if (/leg_body_/.test(c)) return true;
    if (/\.body_\d+/.test(c)) return true;
    return false;
  }

  /** Class-mod rarity comp rows (`classmod_paladin.comp_04_epic`, etc.) also use empty `partType`. */
  function stxIsClassModRarityCompCode(code){
    const c = String(normCode(code || '') || '').toLowerCase();
    if (!c) return false;
    return /\.comp_0[1-6]_/.test(c) || /\.comp_05_legendary/.test(c) || /\.comp_06_pearlescent/.test(c);
  }

  /**
   * Non-legendary class-mod bodies: `body_01`..`body_10` map to name/skin item ids 1..10.
   * Dataset quirks:
   *  - many rows are off-by-one (`body_02`→id 1 … `body_10`→id 9)
   *  - stray `body_01` rows reuse rarity-comp ids (e.g. 221) and must be rejected
   */
  function stxIsValidClassModNonLegendaryBodyPart(p){
    if (!p) return false;
    const codeLo = String(normCode(p && p.code || '') || '').toLowerCase();
    if (/leg_body_/.test(codeLo)) return false;
    if (!/(?:^|[._])body_\d+/.test(codeLo)) return false;
    const bm = codeLo.match(/body_(\d+)/);
    if (!bm) return false;
    const bodyNum = Number(bm[1]);
    if (!Number.isFinite(bodyNum) || bodyNum < 1 || bodyNum > 10) return false;
    const itemId = partItemIdOf(p);
    if (!Number.isFinite(itemId) || itemId < 1 || itemId > 10) return false;
    /* Prefer exact / off-by-one numbering; still accept any 1–10 id on a real body_0N row. */
    return true;
  }
  try { window.stxIsValidClassModNonLegendaryBodyPart = stxIsValidClassModNonLegendaryBodyPart; } catch (_e) {}

  function getLegacyClassModPartsByKind(charName, kindMatcher){
    try{
      const src = (window.parent && window.parent.__LEGACY_CLASSMOD_PARTS_BY_KEY) ? window.parent.__LEGACY_CLASSMOD_PARTS_BY_KEY
                : (window.__LEGACY_CLASSMOD_PARTS_BY_KEY ? window.__LEGACY_CLASSMOD_PARTS_BY_KEY : null);
      if (!src) return [];
      const key = classModKeyForCharacter(charName);
      if (!key || !Array.isArray(src[key])) return [];
      const fam = classModFamilyIdForCharacter(charName);
      if (!Number.isFinite(Number(fam))) return [];
      const out = [];
      for (const row of src[key]){
        if (!Array.isArray(row) || row.length < 2) continue;
        const id = Number(row[0]);
        const name = String(row[1] || '').trim();
        const kind = String(row[2] || '').trim();
        if (!Number.isFinite(id) || !name) continue;
        const k = kind.toLowerCase();
        const keep = (typeof kindMatcher === 'function')
          ? !!kindMatcher(k, kind)
          : (String(kindMatcher || '').toLowerCase() === k);
        if (!keep) continue;
        let normalizedPartType = kind || 'Perk';
        if (k === 'skill') normalizedPartType = 'Skill';
        else if (k === 'perk') normalizedPartType = 'Perk';
        else if (k === 'firmware') normalizedPartType = 'Firmware';
        else if (k === 'item card') normalizedPartType = 'Rarity';
        const synth = {
          category: 'Character',
          manufacturer: 'characters',
          itemType: '',
          weaponType: '',
          partType: normalizedPartType,
          code: `""{${Number(fam)}:${id}}""`,
          name,
          idRaw: `${Number(fam)}:${id}`,
          family: Number(fam),
          id
        };
        if (stxIsBrokenClassmodDatasetPlaceholderPart(synth)) continue;
        out.push(synth);
      }
      return out;
    }catch(_e){ return []; }
  }

  function getLegacyClassModNameParts(charName){
    return getLegacyClassModPartsByKind(charName, (k)=>k.startsWith('name+skin'));
  }

  function getLegacyClassModSkillParts(charName){
    return getLegacyClassModPartsByKind(charName, (k)=>k === 'skill');
  }

  function verifyC4shLegacyClassModSkillParts(){
    const parts = getLegacyClassModSkillParts('c4sh');
    if (!Array.isArray(parts) || parts.length === 0){
      throw new Error('C4sh legacy classmod skill parts missing (count=' + (parts && parts.length) + ')');
    }
    const hasSplash = parts.some(p => String(p.name || '').trim().toLowerCase() === 'splash the pot');
    if (!hasSplash){
      throw new Error('C4sh legacy classmod skill part "Splash the pot" missing');
    }
    return {ok:true,count:parts.length};
  }

  function scheduleC4shLegacyClassModSkillVerify(){
    let warned = false;
    const attempt = () => {
      try {
        return verifyC4shLegacyClassModSkillParts();
      } catch (_e) {
        return null;
      }
    };
    if (attempt()) return;
    const retry = () => {
      if (attempt()) return;
      if (warned) return;
      warned = true;
      try {
        console.warn('[STX] C4sh classmod skill parts not loaded yet — class mod skill dropdowns may be incomplete until legacy data arrives.');
      } catch (_) {}
    };
    if (typeof window === 'undefined') return;
    window.addEventListener('stx:builder-scripts-ready', retry, { once: true });
    window.addEventListener('stx:deferred-core-ready', retry, { once: true });
  }

  if (typeof window !== 'undefined'){
    window.verifyC4shLegacyClassModSkillParts = verifyC4shLegacyClassModSkillParts;
    scheduleC4shLegacyClassModSkillVerify();
  }

  function buildPartCategoryIndex(){
    if (window.__stxPartCategoryIndex) return window.__stxPartCategoryIndex;
    const all = getAllParts();
    const byCat = new Map();
    const byMfr = new Map();
    const weaponish = [];
    const gadgetHeavy = [];
    const character = [];
    for (let i = 0; i < all.length; i++){
      const p = all[i];
      const pc = String(p.category || '').trim();
      const pcNorm = pc.toLowerCase().replace(/\s+/g, '');
      if (pcNorm === 'character' || pcNorm === 'classmod') character.push(p);
      if (pc === 'Weapon' || pc === 'Prefix' || pc === 'Rarity' || pc === 'Enhancement') weaponish.push(p);
      if (pc === 'Gadget' || pc === 'Heavy Weapon' || pc === 'Heavy') gadgetHeavy.push(p);
      if (!byCat.has(pcNorm)) byCat.set(pcNorm, []);
      byCat.get(pcNorm).push(p);
      const mfr = String(p.manufacturer || '').trim().toLowerCase();
      if (mfr) {
        if (!byMfr.has(mfr)) byMfr.set(mfr, []);
        byMfr.get(mfr).push(p);
      }
    }
    window.__stxPartCategoryIndex = { byCat, byMfr, weaponish, gadgetHeavy, character };
    return window.__stxPartCategoryIndex;
  }

  function intersectPartPools(a, b){
    if (!a || !a.length) return b || [];
    if (!b || !b.length) return a || [];
    const smaller = a.length <= b.length ? a : b;
    const larger = a.length <= b.length ? b : a;
    const set = new Set(smaller);
    const out = [];
    for (let i = 0; i < larger.length; i++) {
      if (set.has(larger[i])) out.push(larger[i]);
    }
    return out.length ? out : a;
  }

  function partPoolForFilter(category, isClassMod, isHeavyWeapon, manufacturer){
    const idx = buildPartCategoryIndex();
    let pool = null;
    if (isClassMod) pool = idx.character.length ? idx.character : null;
    else {
      const cat = String(category || '').trim();
      if (cat === 'Weapon'){
        if (isHeavyWeapon && idx.gadgetHeavy.length) pool = idx.gadgetHeavy;
        else if (idx.weaponish.length) pool = idx.weaponish;
      } else {
        const key = cat.toLowerCase().replace(/\s+/g, '');
        if (key && idx.byCat.has(key)) pool = idx.byCat.get(key);
      }
    }
    const manL = String(manufacturer || '').trim().toLowerCase();
    /* Class Mod / Enhancement / gadget gear: real-mfr names only index a thin byMfr slice
       (bodies or cores). Shared skills/stats/payloads/augs live under "gadgets" /
       other manufacturer keys — do not narrow or those slots empty. */
    const catSkipMfr = String(category || '').trim();
    const skipMfrNarrow =
      isClassMod ||
      catSkipMfr === 'Enhancement' ||
      catSkipMfr === 'Repkit' ||
      catSkipMfr === 'Grenade' ||
      catSkipMfr === 'Shield';
    if (manL && !skipMfrNarrow && !isAllPartsEnabled() && idx.byMfr && idx.byMfr.has(manL)) {
      const narrowed = intersectPartPools(pool, idx.byMfr.get(manL));
      if (narrowed.length) pool = narrowed;
    }
    return pool;
  }

  function stxPerfLiteUi(){
    try {
      if (typeof window.stxIsLiteUi === 'function' && window.stxIsLiteUi()) return true;
      if (typeof window.stxIsTouchUi === 'function' && window.stxIsTouchUi()) return true;
    } catch (_) {}
    return document.documentElement.classList.contains('stx-lite-ui') ||
      document.documentElement.classList.contains('stx-touch-ui');
  }

  function stxMainPartOptionCap(){
    if (!stxPerfLiteUi()) return 0;
    try {
      if (typeof window.stxIsTouchUi === 'function' && window.stxIsTouchUi()) return 140;
    } catch (_) {}
    return 180;
  }

  const __filterPartsCache = new Map();

  function filterParts({category, manufacturer, weaponType, partType, relaxShieldGadgetMfr, forceItemManufacturer, ignoreWeaponType}){
    const __filterCacheKey = JSON.stringify({
      category: category || '',
      manufacturer: manufacturer || '',
      weaponType: weaponType || '',
      partType: partType || '',
      relaxShieldGadgetMfr: !!relaxShieldGadgetMfr,
      forceItemManufacturer: !!forceItemManufacturer,
      ignoreWeaponType: !!ignoreWeaponType,
      allMfr: isAllPartsEnabled(),
      n: getAllParts().length
    });
    if (__filterPartsCache.has(__filterCacheKey)) return __filterPartsCache.get(__filterCacheKey);

    const isClassMod = (String(category||'') === 'Class Mod');
    let datasetCategory = isClassMod ? 'Character' : String(category||'');
    // Some slots (Stat Modifier / Endgame) intentionally disable the weaponType gate to prevent empty dropdowns.
    // But we still need Heavy-mode category allowances (Gadget/Prefix/Rarity pools), so infer Heavy from state too.
    let __wt = String(weaponType||'').trim();
    if (!__wt && !ignoreWeaponType && !isClassMod && String(category||'') === 'Weapon') {
      try {
        __wt = String((state && state.weaponType) || '').trim();
        if (!__wt && typeof $ === 'function'){
          const wEl = $('weaponType');
          if (wEl) __wt = String(wEl.value || '').trim();
        }
      } catch (_e) {}
    }
    /* Item type Weapon must never inherit a leftover Heavy weaponType into the heavy-pool gate (empties Body). */
    if (String(category||'') === 'Weapon' && !stxSimpleBuilderItemTypeIsHeavyUi(state && state.itemType) && /^heavy(?:\s*weapon)?$/i.test(__wt)) {
      __wt = '';
    }
    const __isHeavyWeapon = (!ignoreWeaponType && !isClassMod && String(category||'') === 'Weapon' && (__wt === 'Heavy Weapon' || __wt === 'Heavy' || /heavy\s*weapon/i.test(__wt)));
    const pool = partPoolForFilter(category, isClassMod, __isHeavyWeapon, manufacturer);
    const all = pool || getAllParts();

    const filtered = all.filter(p => {
      const code = String((p && p.code) ? p.code : '').trim();
      const pt   = String((p && p.partType) ? p.partType : '').trim();

      if (isClassMod && stxIsBrokenClassmodDatasetPlaceholderPart(p)) return false;

      // Exclude skins/cosmetics from the parts universe (skins are handled via the dedicated Skin dropdown)
      if (/^\{\s*27\s*:\s*\d+\s*\}$/.test(code)) return false; // weapon skin token
      if (/skin/i.test(pt) && !/^Name\+Skin/i.test(pt)) return false; // defensive: true Skin/Cosmetic parts (allow Class Mod Name+Skin)

      // Category filter (Class Mod uses the Character dataset category)
      // Weapons are split across multiple internal categories in some datasets (e.g. Prefix/Rarity pools).
      // For Heavy Weapons, do NOT force a category swap; instead, allow the relevant sub-pools.
      if (datasetCategory){
        const pc = String(p.category||'');
        if (isClassMod){
          const pcNorm = pc.trim().toLowerCase().replace(/\s+/g, '');
          if (!(pcNorm === 'character' || pcNorm === 'classmod')) return false;
        } else if (__isHeavyWeapon){
          const allow = (pc === datasetCategory || pc === 'Heavy Weapon' || pc === 'Heavy' || pc === 'Prefix' || pc === 'Rarity' || pc === 'Gadget' || pc === 'Enhancement');
          if (!allow) return false;
          // Grenade kits share dataset category "Gadget" (and sometimes "Rarity"/others).
          // Heavy weapons should never include `*_grenade_gadget.*` pools.
          const cGr = String(normCode(code) || '').toLowerCase();
          if (stxIsDatasetGrenadeGadgetSpawnCode(cGr)) return false;
        } else if (String(category||'') === 'Weapon'){
          const wantFirmwareSlot = String(partType||'').trim().toLowerCase() === 'firmware';
          const codeNorm0 = String(normCode(code) || '').toLowerCase();
          const isFirmwareRow = /part_firmware|\.part_firmware/i.test(codeNorm0);
          if (wantFirmwareSlot && isFirmwareRow){
            if (!(pc === 'Weapon' || pc === 'Prefix' || pc === 'Rarity' || pc === 'Character' || pc === 'Gadget' || pc === 'Enhancement')) return false;
          } else if (!(pc === datasetCategory || pc === 'Prefix' || pc === 'Rarity')) return false;
        } else {
          if (pc !== datasetCategory) {
            // Repkits: some manufacturer identity/unique rows are incorrectly tagged as category "Other" in the dataset
            // (e.g. `mal_repair_kit.part_mal`, `*_repair_kit.part_augment_unique_*`). Allow those to show under Repkit.
            const dc = String(datasetCategory || '').trim().toLowerCase();
            if (dc === 'repkit') {
              const codeNorm0 = String(normCode(code) || '').toLowerCase();
              if (pc === 'Other' && (/^[a-z0-9]+_repair_kit\./.test(codeNorm0) || codeNorm0.indexOf('repair_kit.') === 0)) {
                // Keep only repkit-ish pools; other "Other" rows should not leak into Repkit.
              } else {
                return false;
              }
            } else if (dc === 'grenade') {
              const codeNorm0 = String(normCode(code) || '').toLowerCase();
              if (pc === 'Gadget' && stxIsDatasetGrenadeGadgetSpawnCode(codeNorm0)) {
                /* Shared + mfr grenade NCS pools are filed under dataset category `Gadget`. */
              } else {
                return false;
              }
            } else {
              return false;
            }
          }
        }
      }

      if (String(datasetCategory || '').trim().toLowerCase() === 'gadget' && String(category || '').trim() === 'Gadget'){
        const cg = String(normCode(code) || '').toLowerCase();
        if (stxIsDatasetGrenadeGadgetSpawnCode(cg)) return false;
      }

      // Manufacturer filter (do NOT apply for Class Mods; their dataset manufacturer is generic)
      // Can be disabled via the "All manufacturers parts" toggle.
      const weaponFirmwareUniversalPool = (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'firmware'
        && /part_firmware|\.part_firmware/i.test(String(normCode(code) || '').toLowerCase()));
      if (!weaponFirmwareUniversalPool && (!isAllPartsEnabled() || forceItemManufacturer) && !isClassMod && manufacturer && String(p.manufacturer||'').trim().toLowerCase() !== String(manufacturer||'').trim().toLowerCase()){
        // Repkits: dataset manufacturer is often "gadgets" even for manufacturer-specific parts.
        // When filtering by manufacturer, match by code prefix instead (e.g. ted_repair_kit.*, jak_repair_kit.*).
        const cm0 = String(datasetCategory || '').trim().toLowerCase();
        if (cm0 === 'repkit'){
          const wantM = String(manufacturer||'').trim().toLowerCase();
          const repkitPrefix =
            (wantM === 'tediore') ? 'ted' :
            (wantM === 'torgue') ? 'tor' :
            (wantM === 'jakobs') ? 'jak' :
            (wantM === 'maliwan') ? 'mal' :
            (wantM === 'vladof') ? 'vla' :
            (wantM === 'daedalus') ? 'dad' :
            (wantM === 'order') ? 'ord' :
            (wantM === 'ripper') ? 'bor' :
            '';
          const codeNorm0 = String(normCode(code) || '').toLowerCase();
          const isUniversalRepkitPool = /^repair_kit\./.test(codeNorm0) || stxIsDatasetRepkitElementCode(codeNorm0);
          const isSelectedRepkitPool = !!(repkitPrefix && codeNorm0.includes(repkitPrefix + '_repair_kit.'));
          // This is only the manufacturer gate. Do not accept the row here, or
          // the later slot filters (Body/Augment/Rarity/etc.) get bypassed.
          if (!isUniversalRepkitPool && !isSelectedRepkitPool) return false;
        } else {
          // Many non-weapon pools are stored under a generic/blank manufacturer.
          // Treat those as universal so selecting a real manufacturer (Daedalus/Jakobs/etc.) still shows parts.
          const pm = String(p.manufacturer || '').trim().toLowerCase();
          const cm = String(datasetCategory || '').trim().toLowerCase();
          let allowGeneric = (pm === '' || pm === 'gadgets' || pm === 'generic' || pm === 'all' || pm === 'universal');
          /* Grenade/Repkit shared pools often use the slot name as manufacturer in Nexus dumps. */
          if (!allowGeneric && (cm === 'grenade' || cm === 'repkit') &&
            (pm === 'payload' || pm === 'augment' || pm === 'size' || pm === 'status' ||
             pm === 'element' || pm === 'elemental' || pm === 'perk' || pm === 'firmware' ||
             pm === 'base' || pm === 'body' || pm === 'other')) {
            allowGeneric = true;
          }
          /* Enhancement shared pools use pseudo-manufacturers in the dataset. */
          if (!allowGeneric && cm === 'enhancement' &&
            (pm === 'stats' || pm === 'firmware' || pm === 'main body' || pm === 'secondary rarity' || pm === 'status')) {
            allowGeneric = true;
          }
          const isNonWeapon = (cm !== 'weapon' && cm !== 'character' && cm !== 'prefix');
          const codeL = String(code || '').toLowerCase();
          const wantPt = String(partType || '').trim().toLowerCase();
          // Only allow generic pools when they are known shared pools for that category (prevents "everything" leaking in).
          let genericAllowedForCategory = false;
          if (isNonWeapon) {
            if (cm === 'shield') genericAllowedForCategory = true;
            else if (cm === 'grenade') genericAllowedForCategory = true;
            else if (cm === 'repkit') genericAllowedForCategory = true;
            else if (cm === 'gadget') genericAllowedForCategory = true;
            else if (cm === 'enhancement') genericAllowedForCategory = true;
          }
          // Heavy Weapon Firmware/Payload parts use manufacturer "gadgets" and heavy_weapon_gadget codes - allow them
          const isHeavyFirmwarePayload = (__isHeavyWeapon && allowGeneric && /heavy_weapon_gadget/i.test(codeL));
          const isHeavyGadgetLegPerks = (__isHeavyWeapon && pm === 'gadgets' && wantPt === 'legendary perks' && String(p.category||'').trim() === 'Gadget'
            && !stxIsDatasetGrenadeGadgetSpawnCode(String(normCode(code) || '').toLowerCase()));
          // Heavy legendary perk rows sometimes live under Weapon + partType Legendary Perks (still need manufacturer gate bypass).
          const isHeavyWeaponLegPerks = (__isHeavyWeapon && wantPt === 'legendary perks' && String(p.category||'').trim() === 'Weapon' && String(pt||'').trim().toLowerCase() === 'legendary perks');
          // Simple "Heavy" uses category Weapon internally (`datasetCategory === 'weapon'`), so `genericAllowedForCategory` is false.
          // Almost all `*_HW.*` / shared `heavy_weapon_gadget.*` rows still carry manufacturer "gadgets" — without this bypass,
          // every real Maliwan/Ripper/… selection filtered them out while itemType "Gadget" (datasetCategory gadget) still worked.
          const codeNormHeavyGate = String(normCode(code) || '').toLowerCase();
          const isHeavyGadgetHwPoolRow = (__isHeavyWeapon && allowGeneric && String(p.category||'').trim() === 'Gadget'
            && !stxIsDatasetGrenadeGadgetSpawnCode(codeNormHeavyGate)
            && (/_hw/i.test(code) || /heavy_weapon_gadget/i.test(codeL)));
          const isHeavyGadgetMfrBySpawnPrefix = !!(isHeavyGadgetHwPoolRow && manufacturer
            && stxGadgetHeavyRowMatchesSelectedManufacturer(codeNormHeavyGate, manufacturer));
          // Some heavy rows are tagged category Weapon (or other) but still use _HW / heavy_weapon_gadget pools and generic manufacturers.
          // Treat those as eligible heavy pools too, otherwise Heavy UI appears empty for licensed/stat/legendary/barrel pools.
          const isHeavyHwPoolRowAnyCat = (__isHeavyWeapon && allowGeneric
            && !stxIsDatasetGrenadeGadgetSpawnCode(codeNormHeavyGate)
            && (/_hw/i.test(code) || /heavy_weapon_gadget/i.test(codeL)));
          const isHeavyHwMfrBySpawnPrefixAnyCat = !!(isHeavyHwPoolRowAnyCat && manufacturer
            && stxGadgetHeavyRowMatchesSelectedManufacturer(codeNormHeavyGate, manufacturer));
          let mfrOk = (allowGeneric && genericAllowedForCategory) || isHeavyFirmwarePayload || isHeavyGadgetLegPerks || isHeavyWeaponLegPerks
            || isHeavyGadgetMfrBySpawnPrefix || isHeavyHwMfrBySpawnPrefixAnyCat || isHeavyHwPoolRowAnyCat;
          // Grenade element pool lives under manufacturer "Status" / similar — shared across grenade kits.
          if (!mfrOk && cm === 'grenade' && wantPt === 'element'){
            const cNorm = String(normCode(code) || '').toLowerCase();
            const sharedElemMfr = (pm === 'status' || pm === 'elemental' || pm === 'augment' || pm === 'gadgets' || pm === 'generic' || pm === 'all' || pm === 'universal' || pm === '');
            if (sharedElemMfr && stxIsDatasetGrenadeElementCode(cNorm)) mfrOk = true;
          }
          if (mfrOk && cm === 'shield' && manufacturer && (!isAllPartsEnabled() || forceItemManufacturer) && !relaxShieldGadgetMfr){
            const cN = String(normCode(code) || '').toLowerCase();
            if (!stxShieldGadgetRowMatchesSelectedManufacturer(cN, manufacturer)) mfrOk = false;
          }
          if (mfrOk && cm === 'grenade' && manufacturer && (!isAllPartsEnabled() || forceItemManufacturer)){
            const cN = String(normCode(code) || '').toLowerCase();
            if (!stxGrenadeGadgetRowMatchesSelectedManufacturer(cN, manufacturer)) mfrOk = false;
          }
          if (mfrOk && cm === 'enhancement' && manufacturer && (!isAllPartsEnabled() || forceItemManufacturer)){
            const cN = String(normCode(code) || '').toLowerCase();
            if (!stxEnhancementGadgetRowMatchesSelectedManufacturer(cN, manufacturer)) mfrOk = false;
          }
          /* Heavy: many `licensed` / stat / endgame rows use manufacturer `gadgets` (or other generics) while the
           * spawn prefix still encodes MAL_/BOR_/… — without this bypass the UI shows empty dropdowns. */
          if (!mfrOk && __isHeavyWeapon && manufacturer){
            const cHg = String(normCode(code) || '').toLowerCase();
            const ptLo = String(partType || '').trim().toLowerCase();
            const heavyAdjunct =
              /barrel_licensed|\.part_stat|part_stat|heavy_weapon_gadget|_hw\.|_hw\b/i.test(cHg)
              || ptLo === 'stat modifier'
              || (ptLo === 'manufacturer part' && /barrel_licensed/i.test(cHg));
            if (heavyAdjunct && stxGadgetHeavyRowMatchesSelectedManufacturer(cHg, manufacturer)) mfrOk = true;
          }
          /* Gadget: show full dataset Gadget pool (except grenade spawn paths). Do not narrow to *_HW / heavy_weapon_gadget only. */
          if (!mfrOk) return false;
        }
      }

      // Heavy Weapon parts are stored in the Gadget category with _HW codes (MAL_HW, BOR_HW, etc.).
      // Firmware and Payload use heavy_weapon_gadget prefix. Element uses Weapon.part_* (shared pool).
      // Element Switch (Maliwan) uses Weapon.part_secondary_elem_*_mal. Legendary Perks use Gadget + manufacturer gadgets.
      // Unique barrels (part_unique_barrel) have partType Barrel and appear in the Barrel dropdown.
      if (typeof __isHeavyWeapon !== 'undefined' && __isHeavyWeapon){
        const wantPt = String(partType || '').trim().toLowerCase();
        const wantPtEmpty = !wantPt;
        const codeNormHw = String(normCode(code) || '').toLowerCase();
        if (wantPt === 'firmware' && /part_firmware|\.part_firmware/i.test(codeNormHw)) {
          /* Heavy weapons still use the shared `part_firmware_*` universe for the firmware slot. */
        } else {
        const isFirmwareOrPayload = (wantPt === 'firmware' || wantPt === 'payload');
        const isElement = (wantPt === 'element');
        const isElementSwitch = (wantPt === 'element switch');
        const isLegendaryPerks = (wantPt === 'legendary perks');
        const hasHwCode = /_HW[\._]/i.test(code) || /_HW/i.test(code);
        const hasHeavyGadgetCode = /heavy_weapon_gadget/i.test(code);
        const hasWeaponElementCode = /weapon\.part_(corrosive|cryo|fire|radiation|shock|secondary_elem)/i.test(code);
        const hasElementSwitchCode = hasWeaponElementCode && /_mal/i.test(code);
        const ptLegendL = String(pt || '').trim().toLowerCase();
        const statsBlobHeavy = (String(p.stats || '') + ' ' + String(p.effects || '') + ' ' + String(p.name || '')).toLowerCase();
        const isHeavyLegendaryPerk = ((isLegendaryPerks || wantPtEmpty) && String(p.category||'').trim() === 'Gadget' && ptLegendL === 'legendary perks'
          && !stxIsDatasetGrenadeGadgetSpawnCode(codeNormHw));
        const isWeaponLegendaryPerk = ((isLegendaryPerks || wantPtEmpty) && String(p.category||'').trim() === 'Weapon' && ptLegendL === 'legendary perks');
        const isGadgetDatasetNonGrenade = String(p.category || '').trim() === 'Gadget' && !stxIsDatasetGrenadeGadgetSpawnCode(codeNormHw);
        // Do not let every Gadget row through the heavy gate (that poisons Licensed / Body / etc. pools).
        // Only gadget rows that are clearly in heavy_HW / heavy_weapon_gadget families may bypass via this path.
        const isGadgetHeavyPoolRow = isGadgetDatasetNonGrenade && (hasHwCode || hasHeavyGadgetCode || /_hw/i.test(code));
        // Stat Modifier / Endgame: explicit partType, spawn tokens, or stats text — not only `*_HW` rows.
        const isHeavyStatModifierCandidate = (wantPt === 'stat modifier') && (
          /part_stat|part_endgame|\.endgame/i.test(codeNormHw) ||
          ptLegendL === 'stat modifier' ||
          (String(p.category || '').trim() === 'Weapon' && ptLegendL === 'legendary perks' && /stat\s*modifier/.test(statsBlobHeavy)) ||
          (/stat\s*modifier/.test(statsBlobHeavy) && (hasHwCode || hasHeavyGadgetCode || isGadgetHeavyPoolRow))
        );
        // Licensed barrels are frequently `weapon.part_barrel_*` / shared pools without a `MAL_HW.` prefix.
        const isHeavyLicensedCandidate = (wantPt === 'manufacturer part') && /barrel_licensed/i.test(codeNormHw);
        // Loose legendary filter passes `partType: undefined` first — allow heavy-relevant Weapon legendary rows.
        const itLo = String(p.itemType || '').toLowerCase();
        const wtLo = String(p.weaponType || '').toLowerCase();
        const isHeavyLooseWeaponLegendary = wantPtEmpty && String(p.category || '').trim() === 'Weapon' && ptLegendL === 'legendary perks' && (
          hasHwCode || hasHeavyGadgetCode || /_hw/i.test(code) || itLo.includes('heavy') || wtLo.includes('heavy')
        );
        const isHeavyBodyEleRow = (wantPt === 'body element') && codeNormHw.includes('part_body_ele');
        const codeOk = hasHwCode || (isFirmwareOrPayload && hasHeavyGadgetCode) || (isElement && hasWeaponElementCode) ||
          (isElementSwitch && hasElementSwitchCode) || isHeavyLegendaryPerk || isWeaponLegendaryPerk || isGadgetHeavyPoolRow
          || isHeavyStatModifierCandidate || isHeavyLicensedCandidate || isHeavyLooseWeaponLegendary || isHeavyBodyEleRow;
        if (!codeOk) return false;
        }
      }

      // Weapon type filter (Gadget = dataset pool mixes itemType labels; grenade paths already excluded above)
      if (weaponType && !ignoreWeaponType && String(category||'') !== 'Gadget'){
        if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'firmware'
          && /part_firmware|\.part_firmware/i.test(String(normCode(code) || '').toLowerCase())){
          /* Firmware rows are shared across categories; don't require matching item weapon type. */
        } else {
        const pwt = p.weaponType || p.itemType || '';
        if (pwt && String(pwt) !== String(weaponType)){
          // Normalize Sniper <-> Sniper Rifle (dataset uses both)
          const pwtN = String(pwt).trim().toLowerCase();
          const wtN = String(weaponType).trim().toLowerCase();
          if ((pwtN === 'sniper' && wtN === 'sniper rifle') || (pwtN === 'sniper rifle' && wtN === 'sniper')) { /* match */ }
          else if ((pwtN === 'smg' && wtN === 'submachine gun') || (pwtN === 'submachine gun' && wtN === 'smg')) { /* match */ }
          else if (__isHeavyWeapon){
            // Heavy Weapon parts often live under Gadget/Prefix/Rarity pools; don't drop them due to a mismatched itemType.
            // Element Switch (Maliwan) and Legendary Perks use shared pools with different weaponType - allow them.
            const pwtL = String(pwt||'').trim().toLowerCase();
            const wantPt = String(partType || '').trim().toLowerCase();
            const isElementSwitch = (wantPt === 'element switch');
            const isLegendaryPerks = (wantPt === 'legendary perks');
            const hasElementSwitchCode = /weapon\.part_secondary_elem/i.test(code) && /_mal/i.test(code);
            const codeBw = String(normCode(code) || '').toLowerCase();
            const isHeavyBodyEle = (wantPt === 'body element' && codeBw.includes('part_body_ele'));
            const allowMismatch = (pwtL === 'gadget' || pwtL === 'weapon' || pwtL === 'prefix' || pwtL === 'rarity' || pwtL === '') ||
              (isElementSwitch && hasElementSwitchCode) || isLegendaryPerks || isHeavyBodyEle;
            if (!allowMismatch) return false;
          } else {
            const wantPtLo = String(partType || '').trim().toLowerCase();
            const codeBw = String(normCode(code) || '').toLowerCase();
            if (wantPtLo === 'body element' && codeBw.includes('part_body_ele')) { /* cross-type pool (modded-style breadth) */ }
            else if (wantPtLo === 'legendary perks') {
              const pwtL = String(pwt || '').trim().toLowerCase();
              if (!pwtL || pwtL === 'weapon' || pwtL === 'prefix' || pwtL === 'rarity' || pwtL === 'gadget' || pwtL === 'enhancement') { /* shared pool */ }
              else if (pwtL === wtN) { /* match */ }
              else if ((pwtL === 'sniper' && wtN === 'sniper rifle') || (pwtL === 'sniper rifle' && wtN === 'sniper')) { /* match */ }
              else if ((pwtL === 'smg' && wtN === 'submachine gun') || (pwtL === 'submachine gun' && wtN === 'smg')) { /* match */ }
              else return false;
            }
            else return false;
          }
        }
        }
      }
// Class Mod: scope character-specific pools by the selected character family.
      if (isClassMod && !isAllPartsEnabled()){
        const fam = classModFamilyIdForCharacter(manufacturer);
        if (fam != null){
          let pfam = (p && p.family != null) ? Number(p.family) : null;
          if (!Number.isFinite(pfam) && p && p.familyId != null) pfam = Number(p.familyId);
          if (!Number.isFinite(pfam)){
            const idRaw = String((p && (p.idRaw || p.idraw)) || '').trim();
            const m = idRaw.match(/^(\d+)\s*:/);
            if (m) pfam = Number(m[1]);
          }
          const want = String(partType || '');
          // Only scope class-specific pools. Perks (family 234) are universal and must not be filtered by class.
          // Legendary main/prefix uses partType '' (leg_body_*) — still class-scoped.
          const classScoped = (want === 'Body' || want === '' || want === 'Name+Skin' || want === 'Rarity' || want === 'Skill');
          if (classScoped && Number.isFinite(pfam) && pfam !== Number(fam)) return false;
          /* Reject cross-VH classmod spawn codes even when family is missing on the row. */
          if (classScoped) {
            const codeL = String(code || '').toLowerCase();
            if (/classmod_/.test(codeL)) {
              const cmKey = stxCanonicalClassModManufacturerKey(manufacturer);
              const slugByKey = {
                siren: 'classmod_dark_siren',
                paladin: 'classmod_paladin',
                'exo soldier': 'classmod_exo_soldier',
                gravitar: 'classmod_gravitar',
                robodealer: 'classmod_robodealer',
                corpohacker: 'classmod_corpohacker'
              };
              const wantSlug = slugByKey[cmKey] || '';
              if (wantSlug && !codeL.includes(wantSlug)) return false;
            }
          }
        }
      }

      // Part type filter (special-case Enhancement Core + Class Mod pools)
      const isEnhCore = (String(category||'') === 'Enhancement' && String(partType||'') === 'Core');
      const isCM = (String(category||'') === 'Class Mod');

      if (partType !== undefined && !isEnhCore){
        // Class Mod special cases:
        // - Legendary bodies often use an empty partType but codes like "leg_body_01".
        // - Name/Skin variants include "Name+Skin+Leg Effect" and should be matched by prefix.
        if (isCM){
          const want = String(partType||'').trim();
          const wantNorm = want.toLowerCase();
          const ptL = String(pt||'').trim();
          const ptNorm = ptL.toLowerCase();
          const codeL = String(code||'').toLowerCase();

          if (wantNorm === 'body' || wantNorm === ''){
            const isBody = (ptNorm === 'body');
            const isLegBody = codeL.includes('leg_body_');
            const isBodyCode = stxIsClassModBodyPoolCode(code);
            /* Legendary main/prefix pool uses partType '' — DLC/raid rows often ship as partType Body. */
            if (wantNorm === '') {
              if (!isLegBody) return false;
            } else if (!(isBody || isLegBody || isBodyCode)) {
              return false;
            }
          } else if (wantNorm === 'name+skin'){
            if (ptNorm.startsWith('name+skin')) { /* ok */ }
            else if (codeL.includes('leg_body_')) { /* DLC/raid legendary names tagged Body */ }
            else return false;
          } else if (wantNorm === 'skill'){
            if (ptNorm !== 'skill') return false;
          } else if (wantNorm === 'perk'){
            if (ptNorm !== 'perk') return false;
          } else if (wantNorm === 'universal'){
            if (ptNorm !== 'perk') return false;
            if (codeL.includes('statspecial')) return false;
            // Secondary bucket: any stat2-style perk variants.
            if (/(^|[._])stat2([._]|$)/.test(codeL)) return false;
          } else if (wantNorm === 'secondary'){
            if (ptNorm !== 'perk') return false;
            if (codeL.includes('statspecial')) return false;
            if (!/(^|[._])stat2([._]|$)/.test(codeL)) return false;
          } else if (wantNorm === 'firmware'){
            const isFirmware = (ptNorm === 'firmware' || /firmware/.test(codeL));
            const isCorrectClassModFirmware = isFirmware && codeL.includes('part_firmware');
            if (!isCorrectClassModFirmware) return false;
          } else if (wantNorm === 'rarity'){
            const isRarityPt = (ptNorm === 'rarity' || ptNorm === 'item card');
            if (!(isRarityPt || stxIsClassModRarityCompCode(code))) return false;
          } else {
            if (String(p.partType||'') !== String(partType||'')) return false;
          }
        } else if (String(partType||'').trim().toLowerCase() === 'element switch'){
          // Shared Maliwan dual-element switch chips — usable on any manufacturer gun.
          const codeL = String(normCode(code) || code || '').toLowerCase();
          const ptL = String(pt||'').trim().toLowerCase();
          if (codeL.includes('part_secondary_elem') && codeL.includes('_mal')) return true;
          if (ptL === 'element switch' && /secondary_elem/.test(codeL)) return true;
          return false;
        } else if (String(category||'') === 'Repkit' && (String(partType||'').trim().toLowerCase() === 'body' || String(partType||'').trim().toLowerCase() === 'base')) {
          // Repkit body/base parts are manufacturer identity parts like `bor_repair_kit.part_borg`.
          const codeL = String(normCode(code)||'').toLowerCase();
          if (!/(^|[^a-z0-9])(?:bor|dad|jak|mal|ord|ted|tor|vla)_repair_kit\.part_(?:borg|dad|jak|mal|ord|ted|tor|vla)($|[^a-z0-9])/.test(codeL)) return false;
        } else if (String(category||'') === 'Grenade' && (String(partType||'').trim().toLowerCase() === 'body' || String(partType||'').trim().toLowerCase() === 'base')) {
          const codeL = String(normCode(code)||'').toLowerCase();
          if (!stxIsGrenadeBodyPoolRowCode(codeL)) return false;
        } else if (String(category||'') === 'Grenade' && String(partType||'').trim().toLowerCase() === 'payload') {
          const codeL = String(normCode(code)||'').toLowerCase();
          const ptL = String(pt||'').trim().toLowerCase();
          if (!(ptL === 'payload' || stxIsGrenadePayloadPoolRowCode(codeL))) return false;
        } else if (String(category||'') === 'Grenade' && String(partType||'').trim().toLowerCase() === 'augment') {
          const codeL = String(normCode(code)||'').toLowerCase();
          const ptL = String(pt||'').trim().toLowerCase();
          if (!(ptL === 'augment' || stxIsGrenadePayloadAugmentPoolRowCode(codeL))) return false;
        } else if (String(category||'') === 'Grenade' && String(partType||'').trim().toLowerCase() === 'rarity') {
          /* Exclude ORD.part_rarity / "UAV Skin" rows — they are skins, not inv_comp rarity ids. */
          if (stxIsGrenadeSkinRarityPart(p)) return false;
          const codeL = String(normCode(code)||'').toLowerCase();
          const ptL = String(pt||'').trim().toLowerCase();
          const isComp = /\.comp_0[1-6]_/.test(codeL) || /(?:^|[._])comp_0[1-6]_/.test(codeL);
          if (!(isComp || ptL === 'rarity')) return false;
          if (!isComp) return false;
        } else if (String(category||'') === 'Repkit' && String(partType||'').trim().toLowerCase() === 'payload') {
          // Repkit payload size parts often ship with an empty `partType` in the dataset.
          // Match the known payload-size pool by code prefix.
          const codeL = String(code||'').toLowerCase();
          if (!/repair_kit\.part_payload_/.test(codeL)) return false;
        } else if (String(category||'') === 'Repkit' && String(partType||'').trim().toLowerCase() === 'augment') {
          const codeNorm = String(normCode(code) || '').toLowerCase();
          const ptL = String(pt||'').trim().toLowerCase();
          const isAugCode = /repair_kit\.part_aug_/.test(codeNorm);
          if (!(isAugCode || ptL === 'augment')) return false;
          /* Resist / immunity / nova / splat have their own slots. */
          if (/resist|immunity|nova|splat/.test(codeNorm)) return false;
        } else if (String(category||'') === 'Repkit' && String(partType||'').trim().toLowerCase() === 'element') {
          // Repkit element rows are inconsistently tagged (often empty partType, sometimes "Cryo").
          const codeNorm = String(normCode(code) || '').toLowerCase();
          const ptL = String(pt||'').trim().toLowerCase();
          const isElementCode = stxIsDatasetRepkitElementCode(codeNorm);
          const isElementTagged = (ptL === 'element' || ptL === 'cryo' || ptL === 'shock' || ptL === 'fire' || ptL === 'radiation' || ptL === 'corrosive');
          if (!(isElementCode || isElementTagged)) return false;
        } else if (String(category||'') === 'Grenade' && String(partType||'').trim().toLowerCase() === 'element') {
          const codeNorm = String(normCode(code) || '').toLowerCase();
          const ptL = String(pt||'').trim().toLowerCase();
          if (!((ptL === 'element') || stxIsDatasetGrenadeElementCode(codeNorm))) return false;
        } else if (String(category||'') === 'Shield' && String(partType||'').trim().toLowerCase() === 'body') {
          const codeL = String(normCode(code)||'').toLowerCase();
          if (!stxIsShieldBodyPoolRowCode(codeL)) return false;
        } else if (String(category||'') === 'Shield' && String(partType||'').trim().toLowerCase() === 'shieldunique') {
          const codeL = String(normCode(code)||'').toLowerCase();
          if (!stxIsShieldUniquePoolRowCode(codeL)) return false;
        } else if (String(category||'') === 'Shield' && String(partType||'').trim() === 'TypeID1Element'){
          const codeNorm = String(normCode(code) || '').toLowerCase();
          if (String(p.category || '').trim() !== 'Shield') return false;
          if (!/^shield\.part_(corrosive|cryo|fire|radiation|shock)$/.test(codeNorm)) return false;
        } else if (String(category||'') === 'Shield' && String(partType||'').trim().toLowerCase() === 'perk') {
          const ptL = String(pt||'').trim().toLowerCase();
          if (String(p.category||'').trim() !== 'Shield') return false;
          if (!(ptL === 'perk' || ptL === '')) return false;
          if (ptL === ''){
            const cn = String(normCode(code) || '').toLowerCase();
            if (!/^shield\.part_|^armor_shield\./i.test(cn)) return false;
          }
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'stat modifier') {
          const codeL = String(normCode(code) || '').toLowerCase();
          const ptL = String(pt||'').trim().toLowerCase();
          if (/part_stat/.test(codeL)) return true;
          if (ptL === 'stat modifier') return true;
          if (/\.endgame\b|part_endgame|stat_augment/.test(codeL)) return true;
          return false;
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'firmware') {
          const codeL = String(normCode(code) || '').toLowerCase();
          const ptL = String(pt||'').trim().toLowerCase();
          // Guided-style: any `part_firmware_*` row (partType often blank on shared chips).
          if (/part_firmware|\.part_firmware/i.test(codeL)) return true;
          if (ptL === 'firmware') return true;
          return false;
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'body element') {
          const codeL = String(normCode(code) || '').toLowerCase();
          const ptNorm = String(pt||'').trim().toLowerCase();
          if (!(ptNorm === 'body' || ptNorm === 'body element')) return false;
          if (!codeL.includes('part_body_ele')) return false;
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'body') {
          const codeL = String(normCode(code) || '').toLowerCase();
          if (String(pt||'').trim().toLowerCase() !== 'body') return false;
          if (codeL.includes('part_body_bolt') || codeL.includes('part_body_flap')) return false;
          if (codeL.includes('part_body_ele')) return false;
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'body accessory') {
          const codeL = String(code||'').toLowerCase();
          const ptNorm = String(pt||'').trim().toLowerCase();
          const isAcc = ptNorm === 'body accessory';
          const isBoltSlotMis = ptNorm === 'body' && (codeL.includes('part_body_bolt') || codeL.includes('part_body_flap'));
          if (!(isAcc || isBoltSlotMis)) return false;
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'barrel') {
          const codeL = String(normCode(code) || '').toLowerCase();
          const ptNorm = String(pt||'').trim().toLowerCase();
          if (ptNorm === 'barrel accessory') return false;
          if (typeof window.stxWeaponSlotPartMatch === 'function') {
            return window.stxWeaponSlotPartMatch('barrel', Object.assign({}, p, { code: codeL, partType: pt }));
          }
          if (typeof window.barrelAccessoryCodeMatchLo === 'function' && window.barrelAccessoryCodeMatchLo(codeL)) return false;
          if (ptNorm === 'barrel') return true;
          if (typeof window.barrelMainCodeMatchLo === 'function') return window.barrelMainCodeMatchLo(codeL);
          return /part_barrel/i.test(codeL);
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'barrel accessory') {
          const codeL = String(normCode(code) || '').toLowerCase();
          const ptNorm = String(pt||'').trim().toLowerCase();
          if (typeof window.stxWeaponSlotPartMatch === 'function') {
            return window.stxWeaponSlotPartMatch('barrelAcc', Object.assign({}, p, { code: codeL, partType: pt }));
          }
          if (ptNorm === 'barrel accessory') return true;
          if (typeof window.barrelAccessoryCodeMatchLo === 'function') return window.barrelAccessoryCodeMatchLo(codeL);
          return /part_barrel_\d+_[a-d](?:$|x)/i.test(codeL) || /barrel_acc|part_barrel_acc/i.test(codeL);
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'magazine') {
          const codeL = String(normCode(code) || '').toLowerCase();
          /* Default Magazine partType = main mag bodies only (accessories/borg filtered by ncsSlot post-pass). */
          if (typeof window.magazineAccessoryCodeMatchLo === 'function' && window.magazineAccessoryCodeMatchLo(codeL)) return false;
          if (typeof window.magazineBorgCodeMatchLo === 'function' && window.magazineBorgCodeMatchLo(codeL)) return false;
          if (String(pt||'').trim().toLowerCase() !== 'magazine') return false;
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'scope') {
          const codeL = String(normCode(code) || '').toLowerCase();
          const ptNorm = String(pt||'').trim().toLowerCase();
          if (ptNorm === 'scope accessory') return false;
          if (typeof window.scopeAccessoryCodeMatchLo === 'function' && window.scopeAccessoryCodeMatchLo(codeL)) return false;
          if (ptNorm !== 'scope') return false;
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'scope accessory') {
          const codeL = String(normCode(code) || '').toLowerCase();
          const ptNorm = String(pt||'').trim().toLowerCase();
          if (ptNorm === 'scope accessory') return true;
          if (typeof window.scopeAccessoryCodeMatchLo === 'function') return window.scopeAccessoryCodeMatchLo(codeL);
          return false;
        } else if (String(category||'') === 'Weapon' && String(partType||'').trim().toLowerCase() === 'underbarrel') {
          const codeL = String(normCode(code) || '').toLowerCase();
          /* Default Underbarrel partType = main only; acc slots use ncsSlot filters. */
          if (typeof window.underbarrelAccessoryCodeMatchLo === 'function') {
            if (window.underbarrelAccessoryCodeMatchLo(codeL, false) || window.underbarrelAccessoryCodeMatchLo(codeL, true)) return false;
          } else if (/underbarrel.*_acc/.test(codeL)) return false;
          if (String(pt||'').trim().toLowerCase() !== 'underbarrel') return false;
        } else if (String(partType||'').trim().toLowerCase() === 'firmware') {
          const codeL = String(normCode(code) || '').toLowerCase();
          const ptL = String(pt||'').trim().toLowerCase();
          if (!(ptL === 'firmware' || /part_firmware|\.part_firmware/i.test(codeL))) return false;
        } else if (String(category||'') === 'Grenade' && String(partType||'').trim() === '') {
          const codeL = String(normCode(code) || '').toLowerCase();
          if (stxIsGrenadeBodyPoolRowCode(codeL) || stxIsGrenadePayloadPoolRowCode(codeL) || stxIsGrenadePayloadAugmentPoolRowCode(codeL)) return false;
          if (String(p.partType||'').trim() !== '') return false;
        } else {
          if (String(p.partType||'').trim().toLowerCase() !== String(partType||'').trim().toLowerCase()) return false;
        }
      }

      // Enhancement: treat "Core" as manufacturer perk (part_core_*) rather than relying on partType fields.
      if (isEnhCore){
        const codeL = String(code||'').toLowerCase();
        const ptL   = String(pt||'').toLowerCase();
        if (!(ptL === 'core' || codeL.includes('part_core_') || codeL.includes('.part_core_'))) return false;
      }

      return true;
    });
    let __filterResult = filtered;
    if (typeof window.__ccDedupePartsByNumericId === 'function'){
      try { __filterResult = window.__ccDedupePartsByNumericId(filtered); } catch (_e) { /* ignore */ }
    }
    if (__filterPartsCache.size >= 96) {
      const __dropKey = __filterPartsCache.keys().next().value;
      if (__dropKey !== undefined) __filterPartsCache.delete(__dropKey);
    }
    __filterPartsCache.set(__filterCacheKey, __filterResult);
    return __filterResult;
  }

  function ensureAllPartIndices(){
    if (window.__stxAllPartsIndexed) return;
    const all = getAllParts();
    for (let i = 0; i < all.length; i++) all[i].__idx = i;
    window.__stxAllPartsIndexed = true;
  }

  let __mainPartLazyWired = false;
  let __mainPartHydrated = false;
  let __mainPartHydrateKey = '';
  let __mainPartRefreshPending = false;
  let __topSelectorsHydrated = false;
  let __topSelectorsLazyWired = false;
  let __mainPartAsyncGen = 0;

  function mainPartContextKey(){
    return [
      String(state.itemType || ''),
      String(state.manufacturer || ''),
      String(state.weaponType || ''),
      String(state.rarity || ''),
      String(($('itemType') && $('itemType').value) || ''),
      String(($('manufacturer') && $('manufacturer').value) || ''),
      String(($('weaponType') && $('weaponType').value) || ''),
      String(($('rarity') && $('rarity').value) || '')
    ].join('|');
  }

  function scheduleRefreshMainPart(force){
    const key = mainPartContextKey();
    if (!force && __mainPartHydrated && key === __mainPartHydrateKey) return;
    if (__mainPartRefreshPending) return;
    __mainPartRefreshPending = true;
    const run = () => {
      __mainPartRefreshPending = false;
      __mainPartHydrated = true;
      __mainPartHydrateKey = mainPartContextKey();
      try { hydrateTopSelectorsIfNeeded(); } catch (_e) {}
      try { refreshMainPart(); } catch (_e) {}
    };
    if (typeof window.stxScheduleIdle === 'function') {
      window.stxScheduleIdle(run, stxPerfLiteUi() ? 160 : 80);
    } else {
      setTimeout(run, 16);
    }
  }

  function invokeRefreshMainPart(forceImmediate){
    if (__mainPartLazyWired || stxPerfLiteUi()) {
      scheduleRefreshMainPart(!!forceImmediate);
      return;
    }
    refreshMainPart();
  }

  function hydrateTopSelectorsIfNeeded(){
    if (__topSelectorsHydrated) return;
    __topSelectorsHydrated = true;
    try { refreshManufacturer(); } catch (_e) {}
    try { refreshWeaponType(); } catch (_e) {}
    try { refreshRarity(); } catch (_e) {}
  }

  function wireLazyTopSelectorRefresh(){
    if (__topSelectorsLazyWired) return;
    __topSelectorsLazyWired = true;
    const deferHydrate = () => {
      if (typeof window.stxYieldToMain === 'function') {
        window.stxYieldToMain(() => {
          try { hydrateTopSelectorsIfNeeded(); } catch (_e) {}
        });
      } else {
        setTimeout(() => {
          try { hydrateTopSelectorsIfNeeded(); } catch (_e) {}
        }, 0);
      }
    };
    // Item type options are ready after refreshTopSelectors — do not hydrate sibling dropdowns on open (blocks first click).
    ['manufacturer', 'weaponType', 'rarity', 'mainPart'].forEach((id) => {
      const el = $(id);
      if (!el || el.__stxLazyTopBound) return;
      el.__stxLazyTopBound = true;
      el.addEventListener('focus', deferHydrate, { passive: true });
      el.addEventListener('pointerdown', deferHydrate, { passive: true });
    });
  }

  function wireLazyMainPartRefresh(){
    if (__mainPartLazyWired) return;
    __mainPartLazyWired = true;
    const mainSel = $('mainPart');
    if (mainSel && !mainSel.__stxLazyMainPartBound) {
      mainSel.__stxLazyMainPartBound = true;
      const deferMainPartHydrate = () => {
        const run = () => {
          hydrateTopSelectorsIfNeeded();
          scheduleRefreshMainPart(true);
        };
        if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(run);
        else setTimeout(run, 0);
      };
      mainSel.addEventListener('pointerdown', deferMainPartHydrate, { passive: true });
      mainSel.addEventListener('focus', deferMainPartHydrate, { passive: true });
    }
  }

  function primeLazyMainPartPlaceholder(){
    const mainSel = $('mainPart');
    if (!mainSel) return;
    try {
      mainSel.disabled = false;
      setSelectOptions(mainSel, [], { placeholder: 'Click here or change filters to load parts…' });
      stxSyncCustomSelectIfWrapped(mainSel);
    } catch (_e) {}
  }

  let __cachedItemTypeCategories = null;
  let __cachedItemTypeCategoriesLen = 0;

  const STX_LITE_ITEM_TYPE_CATEGORIES = Object.freeze([
    'Class Mod', 'Enhancement', 'Gadget', 'Grenade', 'Heavy', 'Other', 'Repkit', 'Shield', 'Weapon'
  ]);

  function itemTypeCategoriesFromParts(all){
    if (stxPerfLiteUi()) {
      if (!__cachedItemTypeCategories) {
        __cachedItemTypeCategories = STX_LITE_ITEM_TYPE_CATEGORIES.slice();
        __cachedItemTypeCategoriesLen = all.length;
      }
      return __cachedItemTypeCategories;
    }
    const n = all.length;
    if (__cachedItemTypeCategories && __cachedItemTypeCategoriesLen === n) {
      return __cachedItemTypeCategories;
    }
    const categories = unique(all.map(p=>{
      var c = String(p.category||'').trim();
      if (/^class\s*mod$/i.test(c) || /^classmod$/i.test(c)) return 'Class Mod';
      return c;
    })).sort((a,b)=>a.localeCompare(b, undefined, {numeric:true}));
    __cachedItemTypeCategories = categories;
    __cachedItemTypeCategoriesLen = n;
    return categories;
  }

  function refreshTopSelectors(opts){
    const itemUi = stxNormalizeSimpleBuilderItemTypeUi(String(state.itemType || ($('itemType') && $('itemType').value) || ''));
    if (/class\s*mod|classmod/i.test(itemUi)) {
      try { mergeLegacyClassModPartsIntoAllParts(); } catch (_e) {}
    }
    const all = getAllParts();
    $('dsStatus').textContent = all.length ? `loaded (${all.length} parts)` : 'not loaded';
    if (state.itemType) {
      const n = stxNormalizeSimpleBuilderItemTypeUi(state.itemType);
      if (n !== state.itemType) state.itemType = n;
    }
    if (stxSimpleBuilderItemTypeIsHeavyUi(state.itemType)) state.weaponType = 'Heavy Weapon';

    // Item Type options from known categories
    const categories = itemTypeCategoriesFromParts(all);

    // Surface "Class Mod" even though parts live under the Character category in ALL_PARTS
    const hasClassMod = (() => {
      if (stxPerfLiteUi()) return true;
      try{
        if (categories.includes('Class Mod')) return true;
        const rows = Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : [];
        if (rows.some(r => /class\s*mod|classmod/i.test(String((r && r.itemType) || '') + ' ' + String((r && r.itemTypeString) || '')))) return true;
      }catch(_e){}
      return all.some(p => /classmod/i.test(String((p && p.code) ? p.code : '')));
    })();

    const visibleCats = (hasClassMod ? categories.filter(c => c !== 'Character' && c !== 'Prefix') : categories.filter(c => c !== 'Prefix'))
      .filter(c =>
        c !== 'Firmware' &&
        c !== 'Heavy Weapon' &&
        c !== 'Heavy' &&
        c !== 'Gadget'
      );

    // Keep item types **alphabetical** (Heavy is a synthetic row not present as dataset category name).
    let ordered = visibleCats.slice();
    if (!ordered.includes('Heavy')) ordered.push('Heavy');
    if (hasClassMod && !ordered.includes('Class Mod')) ordered.push('Class Mod');
    ordered = [...new Set(ordered.map(String))].sort((a, b) => String(a).localeCompare(String(b), undefined, { numeric:true, sensitivity:'base' }));

    setSelectOptions($('itemType'), ordered, {
      placeholder: 'Select item type...',
      decorateOption(opt, cat){
        const url = stxItemTypeIconUrl(cat);
        if (url) opt.setAttribute('data-cc-icon', url);
        else opt.removeAttribute('data-cc-icon');
      }
    });
    if (state.itemType && !ordered.includes(state.itemType)) state.itemType = ordered[0] || '';
    $('itemType').value = state.itemType || '';
    stxSyncCustomSelectIfWrapped($('itemType'));
    try {
      if (typeof window.__ccBootPriorityBuilderSelects === 'function') window.__ccBootPriorityBuilderSelects();
    } catch (_e) {}

    const deferHeavy = !!(opts && opts.deferHeavy);
    const liteDefer = deferHeavy && stxPerfLiteUi();
    if (liteDefer) {
      wireLazyTopSelectorRefresh();
      wireLazyMainPartRefresh();
      primeLazyMainPartPlaceholder();
      try { updateModeLabel(); } catch (_e) {}
    } else {
      refreshManufacturer();
      refreshWeaponType();
      refreshRarity();
      if (deferHeavy) {
        wireLazyMainPartRefresh();
        primeLazyMainPartPlaceholder();
        try { updateModeLabel(); } catch (_e) {}
      } else {
        invokeRefreshMainPart(true);
        updateModeLabel();
      }
    }
  }

  /** Canonical weapon manufacturers from dataset/rarities - ensures none are ever missing from dropdowns. */
  const CANONICAL_WEAPON_MANS = ['Daedalus','Jakobs','Maliwan','Order','Ripper','Tediore','Torgue','Vladof'];
  const CANONICAL_HEAVY_MANS = ['Maliwan','Ripper','Torgue','Vladof'];

  /** Rarity-sheet row `itemType` values that are weapon families (not shields, class mods, etc.). */
  const STX_RARITY_WEAPON_ITEM_TYPES = new Set([
    'Assault Rifle','Pistol','Shotgun','SMG','Sniper','Heavy','Submachine Gun','Sniper Rifle','Heavy Weapon'
  ]);

  /** Normalize weapon-type UI labels to STX_RARITIES `itemType` values (may have synonyms). */
  function stxRarityItemTypesForWeaponTypeUi(wtUi){
    const w = String(wtUi || '').trim();
    if (!w) return [];
    const wl = w.toLowerCase();
    if (wl === 'smg' || wl === 'submachine gun') return ['SMG', 'Submachine Gun'];
    if (wl === 'sniper' || wl === 'sniper rifle') return ['Sniper', 'Sniper Rifle'];
    if (wl === 'heavy' || wl === 'heavy weapon') return ['Heavy', 'Heavy Weapon'];
    if (wl === 'assault rifle') return ['Assault Rifle'];
    if (wl === 'pistol') return ['Pistol'];
    if (wl === 'shotgun') return ['Shotgun'];
    // Default: accept exact string plus common-cased variant
    return [w];
  }

  /**
   * Rows from STX_RARITIES used to build the "allowed manufacturers" set for the final guard.
   * Must NOT mix in Class Mod / Character rows — that leaked Siren, Robodealer, etc. into Weapon.
   */
  function stxRarityRowsForManufacturerAllowlist(cat, wtNormForWeapon){
    const rows = Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : [];
    const catStr = String(cat || '').trim();
    if (catStr === 'Weapon'){
      const wn = String(wtNormForWeapon || '').trim();
      const wfixed = (wn === 'Heavy') ? 'Heavy Weapon' : wn;
      if (wfixed){
        const want = new Set(stxRarityItemTypesForWeaponTypeUi(wfixed).map(s => String(s).trim()));
        return rows.filter(function (r){
          return want.has(String(r && r.itemType || '').trim());
        });
      }
      return rows.filter(function (r){
        return STX_RARITY_WEAPON_ITEM_TYPES.has(String(r && r.itemType || '').trim());
      });
    }
    if (catStr === 'Gadget'){
      return rows.filter(function (r){
        const it = String(r && r.itemType || '').trim();
        return it === 'Heavy Weapon' || it === 'Heavy' || it === 'HeavyWeapon';
      });
    }
    const gear = { Shield: 1, Grenade: 1, Repkit: 1, Enhancement: 1 };
    if (gear[catStr]){
      return rows.filter(function (r){
        return String(r && r.itemType || '').trim() === catStr;
      });
    }
    if (catStr === 'Other') return [];
    return rows.filter(function (r){
      return String(r && r.itemType || '').trim() === catStr;
    });
  }

  /** Vault-hunter / class-mod family names — never show in non–Class Mod manufacturer lists. */
  const STX_CLASS_MOD_ONLY_MANUFACTURERS = new Set([
    'siren', 'dark siren', 'darksiren', 'vex',
    'paladin', 'amon', 'forge knight',
    'exo soldier', 'exosoldier', 'exo-soldier', 'rafa',
    'gravitar', 'harlowe',
    'robodealer', 'robo dealer', 'c4sh',
    'corpohacker', 'corpo hacker', 'loveless', 'hacker', 'the hacker',
    'universal', 'class mod', 'classmod', 'characters'
  ]);

  const __mfrHasPartsCache = new Map();

  /** True when this manufacturer has at least one usable identity/core part for the item type. */
  function manufacturerHasUsablePartsForCategory(catUi, manufacturer, weaponTypeForCat){
    const man = String(manufacturer || '').trim();
    if (!man) return false;
    const catUiNorm = (catUi === 'Heavy Weapon') ? 'Heavy' : catUi;
    if (/class\s*mod/i.test(String(catUiNorm || ''))) return true;
    if (String(catUiNorm || '').trim() === 'Other') return /^ai\s*car/i.test(man) || /car|gun/i.test(man);
    const cat = (catUiNorm === 'Heavy') ? 'Weapon' : catUiNorm;
    const wt = (cat === 'Weapon')
      ? (catUiNorm === 'Heavy' ? 'Heavy Weapon' : String(weaponTypeForCat != null ? weaponTypeForCat : '').trim())
      : ((cat === 'Gadget') ? 'Heavy Weapon' : '');
    const cacheKey = [String(catUiNorm || ''), man.toLowerCase(), wt, String(getAllParts().length)].join('|');
    if (__mfrHasPartsCache.has(cacheKey)) return __mfrHasPartsCache.get(cacheKey);

    let probePt = CORE_PARTTYPE_BY_CATEGORY[cat];
    if (cat === 'Weapon' || cat === 'Gadget') probePt = 'Body';
    else if (cat === 'Shield') probePt = 'Body';
    else if (cat === 'Repkit' || cat === 'Grenade') probePt = 'Base';
    else if (cat === 'Enhancement') probePt = 'Core';

    let ok = false;
    try {
      const forceBody = (cat === 'Weapon' || cat === 'Shield' || cat === 'Grenade' || cat === 'Repkit' || cat === 'Enhancement' || cat === 'Gadget');
      let parts = filterParts({
        category: cat,
        manufacturer: man,
        weaponType: wt || undefined,
        partType: probePt,
        forceItemManufacturer: !!forceBody
      });
      if (parts && parts.length) ok = true;
      if (!ok) {
        parts = filterParts({
          category: cat,
          manufacturer: man,
          weaponType: wt || undefined,
          partType: undefined,
          forceItemManufacturer: !!forceBody
        });
        ok = !!(parts && parts.length);
      }
    } catch (_e) { ok = false; }

    __mfrHasPartsCache.set(cacheKey, ok);
    return ok;
  }

  /** Returns {mans: string[], isClassMod: boolean} for a given category. Use from Guided Builder via window.getManufacturersForCategory. */
  function computeManufacturersForCategory(catUi, weaponTypeForCat){
    const catUiNorm = (catUi === 'Heavy Weapon') ? 'Heavy' : catUi;
    if (String(catUiNorm || catUi || '').trim() === 'Other'){
      return { mans: ['AI Car Guns'], isClassMod: false };
    }
    const cat = (catUiNorm === 'Heavy') ? 'Weapon' : catUiNorm;
    const isClassMod = /class\s*mod/i.test(String(catUiNorm||''));
    let mans = [];
    if (isClassMod){
      try{
        const rows = Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : [];
        mans = unique(
          rows
            .filter(r => String(r && r.itemType || '') === 'Class Mod' || /class\s*mod|classmod/i.test(String(r && r.itemTypeString || '')))
            .map(r => stxCanonicalizeManufacturerDisplayName(String(r && r.manufacturer || '').trim()))
            .filter(Boolean)
        ).map(m => (/^c4sh$/i.test(m) || /^robodealer$/i.test(m)) ? 'Robodealer' : (/^loveless$/i.test(m) || /^corpohacker$/i.test(m) || /^hacker$/i.test(m)) ? 'Corpohacker' : m);
        mans = unique(mans).sort((a,b)=>String(a).localeCompare(String(b), undefined, {numeric:true}));
      
      // Guard against mis-tagged / pseudo manufacturer values (characters, Class Mod, etc.)
      mans = mans.filter(x => {
        const lo = String(x || '').trim().toLowerCase();
        return lo && lo !== 'characters' && lo !== 'class mod' && lo !== 'classmod' && lo !== 'universal';
      });
      const __cmFallback = ['Siren','Paladin','Exo Soldier','Gravitar','Robodealer','Corpohacker'];
      // If the sheet/dataset ever fails to expose the classmod families, use the known set.
      if (!mans.length || !__cmFallback.some(v => mans.includes(v))) {
        mans = __cmFallback.slice();
      } else {
        // Ensure all vault hunters are always present even when extract only ships aliases.
        for (let i = 0; i < __cmFallback.length; i++) {
          if (!mans.includes(__cmFallback[i])) mans.push(__cmFallback[i]);
        }
        mans = unique(mans).sort((a,b)=>String(a).localeCompare(String(b), undefined, {numeric:true}));
      }
}catch(_e){ mans = []; }
    } else {
      // For non-weapon categories, ALL_PARTS often uses a generic manufacturer (e.g., "gadgets"),
      // while STX_RARITIES is keyed by the real manufacturer (Daedalus/Jakobs/etc.).
      // Build the manufacturer list from both sources, preferring real manufacturers.
      const wtForMans = (cat === 'Weapon')
        ? (catUiNorm === 'Heavy' ? 'Heavy Weapon' : (weaponTypeForCat != null ? String(weaponTypeForCat).trim() : String(($('weaponType') && $('weaponType').value) || state.weaponType || '').trim()))
        : ((cat === 'Gadget') ? 'Heavy Weapon' : '');
      const parts = filterParts({category: cat, weaponType: wtForMans || undefined});
      const mansFromParts = unique(parts.map(p=>p.manufacturer));
      let mansFromRarity = [];
      try{
        const rows = Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : [];
        if (cat === 'Weapon' || cat === 'Gadget'){
          const wnorm = (String(wtForMans)==='Heavy') ? 'Heavy Weapon' : String(wtForMans||'').trim();
          if (wnorm){
            const want = new Set(stxRarityItemTypesForWeaponTypeUi(wnorm).map(s => String(s).trim()));
            mansFromRarity = unique(
              rows
                .filter(r => want.has(String(r && r.itemType || '').trim()))
                .map(r => String(r && r.manufacturer || '').trim())
                .filter(Boolean)
            );
          } else {
            const nonWeapon = new Set(['Shield','Grenade','Repkit','Gadget','Enhancement','Class Mod','Character','characters']);
            mansFromRarity = unique(
              rows
                .filter(r => !nonWeapon.has(String(r && r.itemType || '').trim()))
                .map(r => String(r && r.manufacturer || '').trim())
                .filter(Boolean)
            );
          }
        } else {
          mansFromRarity = unique(
            rows
              .filter(r => String(r && r.itemType || '') === String(cat || ''))
              .map(r => String(r && r.manufacturer || '').trim())
              .filter(Boolean)
          );
        }
      }catch(_e){ mansFromRarity = []; }

      mans = unique(mansFromParts.concat(mansFromRarity).map(stxCanonicalizeManufacturerDisplayName))
        .filter(m => {
          const ml = String(m || '').trim().toLowerCase();
          const bad = new Set(['gadgets', 'generic', 'all', 'universal', 'firmware', 'weapon', 'heavy weapon', 'splat', 'nova', 'immunity', 'elemental', 'ground splat', 'splat pack', 'resist', 'resistance', 'elemental resist', 'capacity', 'duration', 'cooldown', 'stats', 'augment', 'perk', 'payload', 'size', 'part', 'main body', 'status', 'secondary rarity', 'class mod', 'grenade', 'repkit', 'shield']);
          return ml && !bad.has(ml);
        })
        .sort((a,b)=>String(a).localeCompare(String(b), undefined, {numeric:true}));

      // If we still have nothing (or the rarity sheet is missing), fall back to parts manufacturers.
      if (!mans.length){
        mans = unique(mansFromParts)
          .filter(Boolean)
          .filter(m => {
            const ml = String(m || '').trim().toLowerCase();
            const badFallback = new Set(['gadgets', 'generic', 'all', 'universal', 'firmware', 'characters', 'weapon', 'heavy weapon', 'splat', 'nova', 'immunity', 'elemental', 'ground splat', 'splat pack', 'resist', 'resistance', 'elemental resist', 'capacity', 'duration', 'cooldown', 'stats', 'augment', 'perk', 'payload', 'size', 'part', 'main body', 'status', 'secondary rarity', 'class mod', 'grenade', 'repkit', 'shield']);
            return ml && !badFallback.has(ml);
          })
          .sort((a,b)=>String(a).localeCompare(String(b), undefined, {numeric:true}));
      }
    
      // Heavy Weapons are stored under the Gadget category with _HW codes; ensure the supported manufacturers surface
      // even if the parts-based scan fails (e.g., during partial dataset loads).
      const wtSel = (cat === 'Weapon')
        ? (catUiNorm === 'Heavy' ? 'Heavy Weapon' : (weaponTypeForCat != null ? String(weaponTypeForCat).trim() : String(($('weaponType') && $('weaponType').value) || state.weaponType || '').trim()))
        : ((cat === 'Gadget') ? 'Heavy Weapon' : '');
      const wtNorm = (wtSel === 'Heavy') ? 'Heavy Weapon' : wtSel;
      if (wtNorm === 'Heavy Weapon' && !mans.length){
        try{
          const rows = Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : [];
          const hwMans = unique(rows.filter(r => String(r && r.itemType || '') === 'Heavy Weapon').map(r => String(r && r.manufacturer || '').trim()).filter(Boolean));
          mans = hwMans.length ? hwMans.sort((a,b)=>String(a).localeCompare(String(b), undefined, {numeric:true})) : ['Maliwan','Ripper','Torgue','Vladof'];
        }catch(_e){
          mans = ['Maliwan','Ripper','Torgue','Vladof'];
        }
      }

      // Final guard: allow only manufacturers that appear in STX_RARITIES for *this* category
      // (and weapon itemType when Weapon). A global allowlist previously pulled Class Mod names into Weapon.
      try{
        const scopedRows = stxRarityRowsForManufacturerAllowlist(cat, wtNorm);
        const allowed = unique(
          scopedRows
            .map(r => stxCanonicalizeManufacturerDisplayName(String(r && r.manufacturer || '').trim()))
            .filter(Boolean)
        );
        if (allowed.length){
          const allow = new Set(allowed.map(a => String(a).trim().toLowerCase()));
          mans = mans.filter(m => allow.has(String(m || '').trim().toLowerCase()));
          // Ensure canonical weapon manufacturers are never missing (Guided/Simple both use this)
          const canonical = (wtNorm === 'Heavy Weapon') ? CANONICAL_HEAVY_MANS : CANONICAL_WEAPON_MANS;
          for (const cm of canonical){
            const cml = String(cm || '').trim().toLowerCase();
            if (cml && allow.has(cml) && !mans.some(m => String(m || '').trim().toLowerCase() === cml)){
              mans.push(cm);
            }
          }
          mans.sort((a,b)=>String(a).localeCompare(String(b), undefined, {numeric:true}));
        }
      }catch(_e){}

      mans = mans
        .map(stxCanonicalizeManufacturerDisplayName)
        .filter(function (m){
          const ml = String(m || '').trim().toLowerCase();
          return ml && !STX_CLASS_MOD_ONLY_MANUFACTURERS.has(ml);
        });
      mans = unique(mans).sort((a,b)=>String(a).localeCompare(String(b), undefined, {numeric:true}));

      /* Drop manufacturers with no usable parts for this item type (keeps rarity-sheet ghosts out). */
      try {
        const wtProbe = (cat === 'Weapon')
          ? (catUiNorm === 'Heavy' ? 'Heavy Weapon' : (weaponTypeForCat != null ? String(weaponTypeForCat).trim() : String(($('weaponType') && $('weaponType').value) || state.weaponType || '').trim()))
          : ((cat === 'Gadget') ? 'Heavy Weapon' : '');
        const keepCur = String((state && state.manufacturer) || '').trim().toLowerCase();
        const filteredMans = mans.filter(function (m) {
          const ml = String(m || '').trim().toLowerCase();
          if (keepCur && ml === keepCur) return true;
          if (window.__CC_IMPORT_IN_PROGRESS && keepCur && ml === keepCur) return true;
          return manufacturerHasUsablePartsForCategory(catUiNorm || cat, m, wtProbe);
        });
        /* Only apply when we still have at least one option — avoid wiping the list on partial dataset load. */
        if (filteredMans.length) mans = filteredMans;
      } catch (_e) {}
}
    return { mans, isClassMod };
  }

  function refreshManufacturer(){
    const itEl = $('itemType');
    const rawPick = String((itEl && itEl.value) || state.itemType || '').trim();
    const legacyHeavyItem = /^(Heavy Weapon|Heavy|Gadget)$/i.test(rawPick);
    let catUi = stxNormalizeSimpleBuilderItemTypeUi(rawPick);
    state.itemType = catUi;
    if (legacyHeavyItem) state.weaponType = 'Heavy Weapon';
    if (itEl && String(itEl.value || '').trim() !== catUi){
      itEl.value = catUi;
      try { stxSyncCustomSelectIfWrapped(itEl); } catch (_e) {}
    }
    const cat = stxSimpleBuilderItemTypeIsHeavyUi(catUi) ? 'Weapon' : catUi;
    const { mans, isClassMod } = computeManufacturersForCategory(catUi);
    const importingManufacturer = window.__CC_IMPORT_IN_PROGRESS ? String(state.manufacturer || '').trim() : '';
    if (importingManufacturer && !mans.some(m => String(m || '').trim().toLowerCase() === importingManufacturer.toLowerCase())) {
      const badImportMfr = new Set(['firmware','gadgets','generic','all','universal','characters','weapon','heavy weapon','splat','nova','immunity','elemental','ground splat','splat pack','resist','resistance','elemental resist','capacity','duration','cooldown','stats','augment','perk','payload','size','part','main body','status','secondary rarity','class mod','grenade','repkit','shield']);
      if (!badImportMfr.has(importingManufacturer.toLowerCase())) mans.push(importingManufacturer);
    }

    if ($('manufacturerLabel')){
      if (isClassMod) $('manufacturerLabel').textContent = 'Character';
      else if (String(catUi).trim() === 'Other') $('manufacturerLabel').textContent = 'AI / Car / Guns';
      else $('manufacturerLabel').textContent = 'Manufacturer';
    }

    if (isClassMod){
      // Display BL4 character names while keeping internal STX mapping (familyId) intact.
      const DISP = {'Siren':'Vex','Dark Siren':'Vex','Paladin':'Amon','Exo Soldier':'Rafa','Gravitar':'Harlowe','Robodealer':'C4sh','C4sh':'C4sh','Corpohacker':'Loveless','Loveless':'Loveless'};
      // Normalize any leftover Dark Siren / display-name selection onto the canonical internal value.
      try {
        const canonMan = stxCanonicalizeManufacturerDisplayName(state.manufacturer);
        if (canonMan && mans.includes(canonMan)) state.manufacturer = canonMan;
      } catch (_e) {}
      const opts = mans.map(v=>({value:v, label:(DISP[v] || v)}));
      setSelectOptions($('manufacturer'), opts, {
        placeholder: 'Select character...',
        getLabel: (o)=>o.label,
        getValue: (o)=>o.value,
        decorateOption(opt, o){
          const url = stxManufacturerIconUrl(o.value, 'Class Mod');
          if (url) opt.setAttribute('data-cc-icon', url);
          else opt.removeAttribute('data-cc-icon');
        }
      });
    } else {
      setSelectOptions($('manufacturer'), mans, {
        placeholder: 'Select manufacturer...',
        decorateOption(opt, m){
          const url = stxManufacturerIconUrl(m, catUi);
          if (url) opt.setAttribute('data-cc-icon', url);
          else opt.removeAttribute('data-cc-icon');
        }
      });
    }
    // Safety: remove any disallowed pseudo-manufacturers that may slip in (e.g. Firmware, bor/dad codes)
    try{
      const bad = new Set(['firmware','gadgets','generic','all','universal','characters','weapon','heavy weapon','splat','nova','immunity','elemental','ground splat','splat pack','resist','resistance','elemental resist','capacity','duration','cooldown','stats','augment','perk','payload','size','part','main body','status','secondary rarity','class mod','grenade','repkit','shield','bor','borg','dad','jak','mal','ord','ted','tor','vla','atl','hyp','rip','dae','classmod']);
      const sel = $('manufacturer');
      if (sel && sel.options){
        Array.from(sel.options).forEach(opt=>{
          if (!opt) return;
          const v = String(opt.value||'').trim().toLowerCase();
          const t = String(opt.textContent||'').trim().toLowerCase();
          if ((v && bad.has(v)) || (t && bad.has(t))) opt.remove();
        });
        // If current selection is now invalid, choose first real option
        const cur = String(sel.value||'').trim().toLowerCase();
        if (bad.has(cur)){
          const first = Array.from(sel.options).find(o => o.value && !bad.has(String(o.value).trim().toLowerCase()));
          sel.value = first ? first.value : '';
        }
      }
    }catch(_e){}

    // attempt to keep previous (only fix when empty or absent from list); match case-insensitively (sheet vs UI casing)
    if (state.manufacturer && !window.__CC_IMPORT_IN_PROGRESS){
      const keep = mans.some(m => String(m || '').trim().toLowerCase() === String(state.manufacturer || '').trim().toLowerCase());
      if (!keep) state.manufacturer = mans[0] || '';
    }
    $('manufacturer').value = state.manufacturer || '';
    stxSyncCustomSelectIfWrapped($('manufacturer'));

    // Weapon row: level (and skin row elsewhere) for all guns; weapon-type picker only for non-Heavy weapons.
    const isWeapon = (cat === 'Weapon');
    const showWeaponTypePick = isWeapon && !stxSimpleBuilderItemTypeIsHeavyUi(catUi);
    $('weaponTypeRow').style.display = isWeapon ? '' : 'none';
    $('nonWeaponRow').style.display = isWeapon ? 'none' : '';
    refreshRarityUiState();
    try{
      const wtSel = $('weaponType');
      const wtRow = $('weaponTypeRow');
      const wtLab = document.querySelector('label[for="weaponType"]');
      if (wtLab) wtLab.style.display = showWeaponTypePick ? '' : 'none';
      if (wtSel && wtRow){
        if (wtSel.parentElement && wtSel.parentElement !== wtRow){
          wtSel.parentElement.style.display = showWeaponTypePick ? '' : 'none';
        } else {
          wtSel.style.display = showWeaponTypePick ? '' : 'none';
        }
      }
      if (wtSel) wtSel.disabled = !showWeaponTypePick;
      stxSyncCustomSelectIfWrapped($('weaponType'));
    }catch(_e){}
    try{
      // Keep a manually picked Maliwan switch when changing manufacturer — dual-element works on any gun.
      if (stxSimpleBuilderItemTypeIsHeavyUi(catUi) && state.slots && state.slots.secondaryEle && !state.slots.secondaryEle.__autoDualElement){
        delete state.slots.secondaryEle;
      }
    }catch(_e){}

    syncBuildStatsItemSlug();
  }

  function refreshWeaponType(){
    const wtEl = $('weaponType');
    const decUi = (s)=>String(s || '').trim();
    const heavyCtx = stxSimpleBuilderItemTypeIsHeavyUi(state.itemType);

    // Heavy (item type Heavy, or Weapon + Heavy Weapon): force one option so we never leak AR/SMG/etc. from a prior Weapon session.
    if (heavyCtx){
      state.weaponType = 'Heavy Weapon';
      if (state.weaponType === 'Heavy') state.weaponType = 'Heavy Weapon';
      setSelectOptions(wtEl, ['Heavy Weapon'], {
        placeholder: 'Select weapon type...',
        decorateOption(opt, wt){
          const url = stxWeaponTypeIconUrl(wt);
          if (url) opt.setAttribute('data-cc-icon', url);
          else opt.removeAttribute('data-cc-icon');
        }
      });
      wtEl.value = 'Heavy Weapon';
      stxSyncCustomSelectIfWrapped(wtEl);
      syncBuildStatsItemSlug();
      return;
    }

    // Not a gun category: clear weapon type so switching Weapon → Shield → Weapon does not keep stale labels/options.
    if (decUi(state.itemType) !== 'Weapon'){
      state.weaponType = '';
      setSelectOptions(wtEl, [], { placeholder: 'Select weapon type...' });
      wtEl.value = '';
      stxSyncCustomSelectIfWrapped(wtEl);
      syncBuildStatsItemSlug();
      return;
    }

    const mansel = $('manufacturer').value || '';
    state.manufacturer = mansel;

    const parts = filterParts({category:'Weapon', manufacturer: mansel});
    let wtypes = unique(parts.map(p=>p.weaponType || p.itemType).filter(Boolean));
    wtypes = wtypes.filter(w => String(w).trim().toLowerCase() !== 'weapon');
    // Heavy is its own item type — never offer Heavy Weapon in the Weapon weapon-type picker.
    wtypes = wtypes.filter(w => !stxWeaponTypeIsHeavyLabel(w));
    if (stxWeaponTypeIsHeavyLabel(state.weaponType)) state.weaponType = '';
    /* Dataset mixes "Sniper" vs "Sniper Rifle" (same gameplay row); one menu entry avoids duplicate picks. */
    const seenWt = new Set();
    wtypes = wtypes.map(w=>{
      const s = String(w || '').trim();
      const l = s.toLowerCase();
      if (l === 'sniper' || l === 'sniper rifle') return 'Sniper Rifle';
      if (l === 'submachine gun') return 'SMG';
      return s;
    }).filter(w=>{
      if (!w || seenWt.has(w)) return false;
      seenWt.add(w);
      return true;
    });
    wtypes = unique(wtypes).sort((a,b)=>a.localeCompare(b, undefined, {numeric:true}));
    setSelectOptions($('weaponType'), wtypes, {
      placeholder: 'Select weapon type...',
      decorateOption(opt, wt){
        const url = stxWeaponTypeIconUrl(wt);
        if (url) opt.setAttribute('data-cc-icon', url);
        else opt.removeAttribute('data-cc-icon');
      }
    });
    if (state.weaponType === 'Heavy') state.weaponType = 'Heavy Weapon';
    const wtNormSel = String(state.weaponType || '').trim();
    const wtLow = wtNormSel.toLowerCase();
    if ((wtLow === 'sniper' || wtLow === 'sniper rifle') && wtypes.includes('Sniper Rifle')) state.weaponType = 'Sniper Rifle';
    if ((wtLow === 'submachine gun') && wtypes.includes('SMG')) state.weaponType = 'SMG';
    if (state.weaponType && !wtypes.includes(state.weaponType)) state.weaponType = wtypes[0] || '';
    $('weaponType').value = state.weaponType || '';
    stxSyncCustomSelectIfWrapped($('weaponType'));
    syncBuildStatsItemSlug();
  }

  function refreshRarity(){
    const sel = $('rarity');
    if (!sel) return;
    const useTierFilter = rarityTierFilterActiveForCurrentContext();
    refreshRarityUiState();

    if (!useTierFilter){
      sel.innerHTML = '';
      const auto = document.createElement('option');
      auto.value = '';
      auto.textContent = '(auto from rarity ID)';
      sel.appendChild(auto);
      sel.value = '';
      try{ state.rarity = ''; }catch(_e){}
      try { stxSyncCustomSelectIfWrapped(sel); } catch (_e) {}
      return;
    }

    const cur = String(sel.value || state.rarity || '').trim();
    const isClassModTierFilter = String(state.itemType || '') === 'Class Mod';
    const order = isClassModTierFilter ? [0,1,2,3,4] : [0,1,2,3,4,5];
    // Always show the full tier list so Legendary/Pearlescent are consistently available in the main rarity dropdown.
    // Part availability is still enforced later when selecting the rarity-id part.
    const opts = order.map(t => ({ value: String(t), label: rarityTierLabel(t) }));

    sel.innerHTML = '';
    const ph = document.createElement('option');
    ph.value = '';
    ph.textContent = '(select rarity tier)';
    sel.appendChild(ph);
    for (const o of opts){
      const opt = document.createElement('option');
      opt.value = o.value;
      opt.textContent = o.label;
      sel.appendChild(opt);
    }

    // Keep current if valid; otherwise auto-select first available tier.
    if (cur && opts.some(o => o.value === cur)){
      sel.value = cur;
    } else if (!sel.value && opts.length){
      sel.value = opts[0].value;
    }
    try{ state.rarity = sel.value || ''; }catch(_e){}
    try { stxSyncCustomSelectIfWrapped(sel); } catch (_e) {}
  }

  function stxEnsureMainPartSelectOption(part){
    if (!part) return '';
    const sel = $('mainPart');
    let key = '';
    try { key = String(part.__mainOptKey || '').trim(); } catch (_) { key = ''; }
    if (!key && part.__idx != null && Number.isFinite(Number(part.__idx))) key = `idx:${Number(part.__idx)}`;
    if (!key) {
      const tok = tokenForPart(part) || normCode(part.code) || '';
      key = tok ? `import:${tok}` : 'import:main';
    }
    try { part.__mainOptKey = key; } catch (_) {}
    try {
      if (!state.__mainPartByOptionKey || typeof state.__mainPartByOptionKey.set !== 'function') {
        state.__mainPartByOptionKey = new Map();
      }
      state.__mainPartByOptionKey.set(key, part);
    } catch (_) {}
    if (sel) {
      let found = false;
      try {
        for (let i = 0; i < (sel.options || []).length; i++) {
          if (String(sel.options[i].value || '') === key) { found = true; break; }
        }
      } catch (_) {}
      if (!found) {
        let label = key;
        try { label = String(displayForPart(part) || dropdownLabelForPart(part) || key).trim() || key; } catch (_) {}
        try {
          const opt = new Option(label, key);
          try { opt.setAttribute('data-base-label', label); } catch (_) {}
          sel.appendChild(opt);
        } catch (_) {}
      }
      try { sel.value = key; } catch (_) {}
      try { stxSyncCustomSelectIfWrapped(sel); } catch (_) {}
    }
    return key;
  }

  function refreshMainPartSync(){
    const catUi = stxNormalizeSimpleBuilderItemTypeUi(state.itemType);
    if (state.itemType !== catUi) state.itemType = catUi;
    const cat   = stxSimpleBuilderItemTypeIsHeavyUi(catUi) ? 'Weapon' : catUi;
    const man = $('manufacturer').value || '';
    state.manufacturer = man;
    if (cat === 'Weapon'){
      // If UI itemType is Heavy, the weaponType row is hidden - force the correct weapon type anyway.
      state.weaponType = (stxSimpleBuilderItemTypeIsHeavyUi(catUi))
        ? 'Heavy Weapon'
        : ($('weaponType').value || '');

      if (state.weaponType === 'Heavy') state.weaponType = 'Heavy Weapon';
      state.level = Number($('level').value || 1);
    } else {
      state.level = Number(($('level2') && $('level2').value) ? $('level2').value : ($('level').value || 1));
    }
    const isHeavyWeaponSimple = cat === 'Weapon' && (
      /^heavy(?:\s*weapon)?$/i.test(String(state.weaponType || '').trim()) ||
      /heavy\s*weapon/i.test(String(state.weaponType || ''))
    );
    const useTierFilter = rarityTierFilterActiveForCurrentContext();
    state.rarity = useTierFilter ? ($('rarity').value || '') : '';
    const selectedRarity = parseRarityValue(state.rarity);
    let selectedTier = (selectedRarity && Number.isFinite(selectedRarity.tier)) ? Number(selectedRarity.tier) : null;
    const raritySelText = String((($('rarity') && $('rarity').selectedOptions && $('rarity').selectedOptions[0])
      ? $('rarity').selectedOptions[0].textContent
      : '') || '').trim().toLowerCase();
    const pearlTierSelected =
      (selectedTier === 5) ||
      /^6$/.test(String(state.rarity || '').trim()) ||
      /\bpearl/.test(String(state.rarity || '').trim().toLowerCase()) ||
      /\bpearl/.test(raritySelText);
    if (!Number.isFinite(selectedTier) && pearlTierSelected) selectedTier = 5;
    if (!useTierFilter) selectedTier = null;
    if (useTierFilter && !Number.isFinite(selectedTier)){
      const pendingLabel = (cat === 'Class Mod')
        ? 'Body - Classmod Name (select rarity tier first)'
        : 'Rarity ID Part (select rarity tier first)';
      $('mainPartLabel').textContent = pendingLabel;
      setSelectOptions($('mainPart'), [], {placeholder:'Select rarity tier first...'});
      try { stxSyncCustomSelectIfWrapped($('mainPart')); } catch (_e) {}
      $('mainPart').disabled = true;
      state.mainPart = null;
      refreshBuilder();
      syncMainPartPreview();
      return;
    }
    $('mainPart').disabled = false;

    if (cat === 'Other'){
      $('mainPartLabel').textContent = 'Select item (full serial)';
      const aicarList = getAicarSimpleBuilderParts();
      ensureAllPartIndices();
      const mainPartByOptionKey = new Map();
      for (let i = 0; i < aicarList.length; i++){
        const p = aicarList[i];
        const key = `aicar:${i}`;
        try{ p.__mainOptKey = key; }catch(_e){}
        mainPartByOptionKey.set(key, p);
      }
      state.__mainPartByOptionKey = mainPartByOptionKey;
      setSelectOptions($('mainPart'), aicarList, {
        placeholder: 'Select AI / car / guns preset...',
        getLabel: dropdownLabelForMainPartList,
        getValue: (p) => String((p && p.__mainOptKey) ? p.__mainOptKey : '')
      });
      if (state.mainPart){
        const prev = state.mainPart.__fullDeserialized ? String(state.mainPart.__fullDeserialized).trim() : '';
        const match = prev ? aicarList.find(p => String(p.__fullDeserialized || '').trim() === prev) : null;
        if (match && match.__mainOptKey) $('mainPart').value = String(match.__mainOptKey);
        else stxEnsureMainPartSelectOption(state.mainPart);
      } else {
        $('mainPart').value = '';
      }
      try { stxSyncCustomSelectIfWrapped($('mainPart')); } catch (_e) {}
      refreshBuilder();
      syncMainPartPreview();
      return;
    }

    // Determine core part type for the Main/Prefix selector.
    // Note: "Class Mod" bodies are split into two pools:
    //  - Non-legendary: the standard Body pool (body_0x)
    //  - Legendary: the unnamed leg_body_* pool (partType == '')
    let corePt = CORE_PARTTYPE_BY_CATEGORY[cat] ?? 'Base';

    if (cat === 'Class Mod'){
      const isLegendary = useTierFilter ? (selectedTier === 4) : false;
      corePt = isLegendary ? '' : 'Body';
    }
    if (cat === 'Class Mod'){
      $('mainPartLabel').textContent = (useTierFilter && Number.isFinite(selectedTier))
        ? `Body - Classmod Name (${rarityTierLabel(selectedTier)})`
        : 'Body - Classmod Name';
    } else {
      let lbl = (useTierFilter && Number.isFinite(selectedTier))
        ? `Rarity ID Part (${rarityTierLabel(selectedTier)})`
        : 'Rarity ID Part';
      if (cat === 'Weapon' && pearlTierSelected && isStxSimplePearlOverrideChecked()){
        lbl += ' — pearl override prepends a random pearl id (keeps rarity)';
      }
      $('mainPartLabel').textContent = lbl;
    }

    const wtForMainPart = (cat === 'Weapon') ? state.weaponType : '';
    let partsList = filterParts({category: cat, manufacturer: man, weaponType: wtForMainPart, partType: corePt});

    // Absolute guardrail: Heavy simple builder must never show grenade-kit rarity IDs in the main "Rarity ID Part" list,
    // even if the dataset/part metadata files them under weapon-ish pools.
    if (cat === 'Weapon'){
      try{
        const wtLo = String(state.weaponType || '').trim().toLowerCase();
        const heavyCtx = stxSimpleBuilderItemTypeIsHeavyUi(catUi) || wtLo === 'heavy' || wtLo === 'heavy weapon' || /heavy\s*weapon/i.test(wtLo);
        if (heavyCtx){
          partsList = partsList.filter(p => {
            const cN = String(normCode(p && p.code || '') || '').toLowerCase();
            if (stxIsDatasetGrenadeGadgetSpawnCode(cN)) return false;
            // extra: some rows may not normalize cleanly, so also reject explicit "grenade_gadget" tokens
            if (cN.includes('grenade_gadget')) return false;
            return true;
          });
        }
      }catch(_e){}
    }

    // Class Mod: keep the body selector aligned to the chosen rarity tier.
    if (cat === 'Class Mod'){
      const wantLegendary = (corePt === '');
      partsList = partsList.filter(p => {
        const c = String((p && p.code) ? p.code : '').toLowerCase();
        const isLeg = c.includes('leg_body_');
        return wantLegendary ? isLeg : !isLeg;
      });
      if (!wantLegendary) {
        partsList = partsList.filter(stxIsValidClassModNonLegendaryBodyPart);
        /* Rescue: Body partType filter can miss empty-partType body_0N rows after dataset quirks. */
        if (!partsList.length && man) {
          const fam = classModFamilyIdForCharacter(man);
          const rescued = getAllParts().filter(p => {
            if (!p) return false;
            const pc = String(p.category || '').trim().toLowerCase().replace(/\s+/g, '');
            if (!(pc === 'character' || pc === 'classmod')) return false;
            if (!stxIsValidClassModNonLegendaryBodyPart(p)) return false;
            if (Number.isFinite(Number(fam))) {
              const pf = partFamilyIdOf(p);
              if (Number.isFinite(pf) && pf !== Number(fam)) return false;
            }
            return true;
          });
          if (rescued.length) partsList = rescued;
        }
      }
      const seenMain = new Set();
      partsList = partsList.filter(p => {
        if (stxIsBrokenClassmodDatasetPlaceholderPart(p)) return false;
        const iid = Number(partItemIdOf(p));
        const key = [
          Number.isFinite(iid) ? String(iid) : '',
          String((p && p.idRaw) || '').trim().toLowerCase(),
          String((p && p.code) || '').trim().toLowerCase(),
          String((p && p.name) || '').trim().toLowerCase()
        ].join('|');
        if (!key || seenMain.has(key)) return false;
        seenMain.add(key);
        return true;
      });
    }

    // Fallback to empty partType is useful for several categories, but for Enhancements it causes the core selector to show every enhancement pool.
    // Also: do not fall back for Class Mods, or we'd re-introduce the legendary pool when a non-legendary tier is selected.
    // Repkit: never fall back to partType "" — that pool is mostly untyped perks/payload/element rows and pollutes "Rarity ID".
    if (!partsList.length && cat !== 'Enhancement' && cat !== 'Class Mod' && cat !== 'Shield' && cat !== 'Repkit' && cat !== 'Gadget'){
      partsList = filterParts({category: cat, manufacturer: man, weaponType: (cat==='Weapon'? state.weaponType : ''), partType: ''});
    }

    // Heavy Weapons live in the Gadget pool (_HW codes). If filters miss, re-scan Gadget directly.
    if (!partsList.length && (cat === 'Weapon' || cat === 'Gadget')
      && (cat === 'Gadget' || /^heavy(?:\s*weapon)?$/i.test(String(state.weaponType||'').trim()) || /heavy\s*weapon/i.test(String(state.weaponType||'')))) {
      try{
        const wantMan = isAllPartsEnabled() ? '' : String(man||'').trim().toLowerCase();
        const wantPt  = String(corePt||'').trim();
        partsList = getAllParts().filter(p=>{
          const pc = String(p.category||'').trim();
          if (pc !== 'Gadget') return false;
          const code = String((p && p.code) ? p.code : '');
          const cn = String(normCode(code) || '').toLowerCase();
          if (stxIsDatasetGrenadeGadgetSpawnCode(cn)) return false;
          if (!/_HW/i.test(code)) return false;
          const pm = String(p.manufacturer||'').trim().toLowerCase();
          if (wantMan && pm !== wantMan) return false;
          return String(p.partType||'').trim() === wantPt;
        });
      }catch(_e){ /* ignore */ }
    }

if (cat === 'Class Mod' && !isAllPartsEnabled()){
      const fam = classModFamilyIdForCharacter(man);
      let slugPrefix = '';
      try {
        const key = classModKeyForCharacter(man);
        if (key === 'vex') slugPrefix = 'classmod_dark_siren.';
        else if (key === 'amon') slugPrefix = 'classmod_paladin.';
        else if (key === 'rafa') slugPrefix = 'classmod_exo_soldier.';
        else if (key === 'harlowe') slugPrefix = 'classmod_gravitar.';
        else if (key === 'c4sh') slugPrefix = 'classmod_robodealer.';
        else if (key === 'loveless') slugPrefix = 'classmod_corpohacker.';
      } catch (_e) {}
      if (fam != null || slugPrefix){
        partsList = partsList.filter(p => {
          const pf = Number(p && (p.familyId ?? p.family));
          if (fam != null && Number.isFinite(pf) && pf === Number(fam)) return true;
          if (slugPrefix) {
            const c = String(normCode(p && p.code || '') || '').toLowerCase();
            if (c.indexOf(slugPrefix) === 0) return true;
          }
          /* Keep family-less DLC rows only when they clearly belong to this VH slug. */
          return false;
        });
      }
    }

    const rarityRowsForTier = useTierFilter && Number.isFinite(selectedTier)
      ? getRarityRowsForCurrentContext().filter(r => rarityTierFromItemTypeString(r && r.itemTypeString, r) === selectedTier)
      : getRarityRowsForCurrentContext();

    /* Class Mod / Character: #mainPart lists Body / name rows, not rarity comps.
       Empty rarity-tier rows must not wipe the body dropdown (epic/common/etc.). */
    if (useTierFilter && !rarityRowsForTier.length && !(cat === 'Weapon' && pearlTierSelected) && cat !== 'Class Mod' && cat !== 'Character'){
      setSelectOptions($('mainPart'), [], {placeholder:`No ${rarityTierLabel(selectedTier).toLowerCase()} parts available...`});
      try { stxSyncCustomSelectIfWrapped($('mainPart')); } catch (_e) {}
      $('mainPart').disabled = true;
      state.mainPart = null;
      refreshBuilder();
      syncMainPartPreview();
      return;
    }

    // Shield main parts: include any unique bodies that are stored with empty partType
    // (e.g., some legendary shields use partType "" but still have part_* codes).
    if (cat === 'Shield' && corePt !== 'Rarity'){
      const partFam = (p)=>{
        if (p && p.family != null && Number.isFinite(Number(p.family))) return Number(p.family);
        if (p && p.familyId != null && Number.isFinite(Number(p.familyId))) return Number(p.familyId);
        const idRaw = String(p && (p.idRaw || p.idraw) || '').trim();
        const m = idRaw.match(/^(\d+)\s*:/);
        return m ? Number(m[1]) : null;
      };
      const isShieldMainCandidate = (p)=>{
        const code = String(p && p.code || '').toLowerCase();
        const pt = String(p && p.partType || '').trim().toLowerCase();
        if (!code) return false;
        if (pt === 'rarity') return false;
        if (code.includes('.comp_') || code.includes('comp_')) return false;
        return (code.includes('.part_') || code.includes('part_') || pt === 'body' || pt === '');
      };
      // Prefer families available for the selected rarity tier.
      let fams = [];
      fams = rarityRowsForTier
        .map(r => Number(r && r.familyId))
        .filter(n => Number.isFinite(n));
      if (!fams.length && man && !isAllPartsEnabled()){
        try{
          const rows = Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : [];
          const manL = String(man||'').trim().toLowerCase();
          fams = rows
            .filter(r => String(r && r.itemType || '') === 'Shield' && String(r && r.manufacturer || '').trim().toLowerCase() === manL)
            .filter(r => rarityTierFromItemTypeString(r && r.itemTypeString, r) === selectedTier)
            .map(r => Number(r && r.familyId))
            .filter(n => Number.isFinite(n));
        }catch(_e){ fams = []; }
      }
      if (fams.length){
        const all = getAllParts();
        const famSet = new Set(fams);
        const existing = new Set(partsList.map(p => String(p.__idx ?? p.idRaw ?? p.code)));
        for (const p of all){
          if (!p || String(p.category||'') !== 'Shield') continue;
          const pf = partFam(p);
          if (pf == null || !famSet.has(pf)) continue;
          if (!isShieldMainCandidate(p)) continue;
          const key = String(p.__idx ?? p.idRaw ?? p.code);
          if (existing.has(key)) continue;
          partsList.push(p);
          existing.add(key);
        }
        // Now restrict to the current manufacturer family set to avoid cross-mfr bleed.
        partsList = partsList.filter(p => {
          const pf = partFam(p);
          return pf != null && famSet.has(pf);
        });
      }
    }

    // Non-weapon main parts: if any manufacturer-specific parts exist, hide generic pools.
    // This prevents Shield main parts from showing every manufacturer when a specific one is selected.
    // Enhancement: many `TED_Enhancement.*` / `MAL_Enhancement.*` cores ship with an empty `manufacturer` field;
    // strict string match would drop every core and leave an empty "Rarity ID" / Core dropdown (e.g. Hydrator = Banger + Digi-Divider).
    if (!isAllPartsEnabled() && cat !== 'Weapon' && cat !== 'Class Mod' && cat !== 'Gadget' && cat !== 'Enhancement' && man){
      const manL = String(man||'').trim().toLowerCase();
      const strict = partsList.filter(p => String(p.manufacturer||'').trim().toLowerCase() === manL);
      if (strict.length) partsList = strict;
    }

    // Weapon + Pearlescent: the Main/Prefix (barrel) dropdown should show only pearlescent item barrels.
    if (cat === 'Weapon' && pearlTierSelected && String(corePt || '').toLowerCase() === 'barrel'){
      const pearlBarrels = partsList.filter(isPearlWeaponMainPart);
      if (pearlBarrels.length){
        partsList = pearlBarrels;
      }
    }

    // Rarity-driven part selection:
    // Keep the main selector aligned with all families/items in the selected rarity tier.
    // Pearlescent used to skip this gate for all weapons — that let non-heavy rarity rows (e.g. grenade comps
    // sharing numeric IDs) stay in the list. Heavy always uses STX pair keys for the selected tier.
    // Class Mod / Character: #mainPart lists Body rows (names, not STX rarity comp tokens); pair gating clears the list.
    const skipRarityFamilyItemGate = !useTierFilter || (cat === 'Weapon' && pearlTierSelected && !isHeavyWeaponSimple) || cat === 'Class Mod' || cat === 'Character';
    if (!skipRarityFamilyItemGate){
      const pairSet = stxRarityPairSetFromRows(rarityRowsForTier);
      if (pairSet.size){
        if (stxPerfLiteUi() && partsList.length > 180) {
          const famOnly = new Set();
          for (const k of pairSet) {
            const bits = String(k).split(':');
            const f = Number(bits[0]);
            if (Number.isFinite(f)) famOnly.add(f);
          }
          if (famOnly.size) {
            const byFamPre = partsList.filter(p => famOnly.has(partFamilyIdOf(p)));
            if (byFamPre.length) partsList = byFamPre;
          }
        }
        const byPair = partsList.filter(p => stxPartMatchesRarityPairSet(p, pairSet));
        partsList = byPair.length ? byPair : [];
      } else {
        const famSet = new Set(
          rarityRowsForTier
            .map(r => Number(r && r.familyId))
            .filter(n => Number.isFinite(n))
        );
        const itemSet = new Set(
          rarityRowsForTier
            .map(r => Number(r && r.itemId))
            .filter(n => Number.isFinite(n))
        );
        const byFam = famSet.size ? partsList.filter(p => famSet.has(partFamilyIdOf(p))) : [];
        if (byFam.length) partsList = byFam;
        const byItem = itemSet.size ? partsList.filter(p => itemSet.has(partItemIdOf(p))) : [];
        if (byItem.length) partsList = byItem;
      }
    }

    if (man && typeof isAllPartsEnabled === 'function' && !isAllPartsEnabled()){
      const cpt = String(corePt || '').toLowerCase();
      const codeLo = (p) => String(normCode(p && p.code || '') || '').toLowerCase();
      if (cat === 'Shield' && cpt === 'rarity'){
        partsList = partsList.filter(p => stxShieldGadgetRowMatchesSelectedManufacturer(codeLo(p), man));
      } else if (cat === 'Grenade' && cpt === 'rarity'){
        partsList = partsList.filter(p => stxGrenadeGadgetRowMatchesSelectedManufacturer(codeLo(p), man));
      } else if (cat === 'Enhancement' && cpt === 'core'){
        partsList = partsList.filter(p => stxEnhancementGadgetRowMatchesSelectedManufacturer(codeLo(p), man));
      }
    }

    if (isHeavyWeaponSimple){
      partsList = partsList.filter(p => !stxPartIsGrenadeKitDatasetPart(p));
    }

    // We need stable retrieval: attach index to dataset parts and option keys for synthetic rows.
    ensureAllPartIndices();

    const useRarityTierGroups = String(corePt || '').trim().toLowerCase() === 'rarity';
    const cap = stxMainPartOptionCap();
    const liteUi = stxPerfLiteUi();
    if (liteUi && partsList.length > 80) {
      partsList.sort((a, b) => displayForPart(a).localeCompare(displayForPart(b), undefined, { numeric: true, sensitivity: 'base' }));
    } else {
      partsList.sort((a,b)=>{
        const rd = stxPartDropdownRichnessScore(b) - stxPartDropdownRichnessScore(a);
        if (rd) return rd;
        return displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'});
      });
    }

    (function stxDedupeMainPartListByLogicalKey(){
      const seen = new Set();
      const out = [];
      for (const p of partsList){
        const lk = stxSelectLogicalDedupeKey(p);
        if (lk){
          if (seen.has(lk)) continue;
          seen.add(lk);
        }
        out.push(p);
      }
      partsList = out;
    })();

    if (cap && partsList.length > cap) {
      partsList = partsList.slice(0, cap);
    }

    const mainPartByOptionKey = new Map();
    for (let i=0; i<partsList.length; i++){
      const p = partsList[i];
      let key = '';
      if (p && p.__idx != null && Number.isFinite(Number(p.__idx))){
        key = `idx:${Number(p.__idx)}`;
      } else {
        const fam = partFamilyIdOf(p);
        const item = partItemIdOf(p);
        if (Number.isFinite(fam) && Number.isFinite(item)) key = `synth:${fam}:${item}`;
        else key = `local:${i}`;
      }
      try{ p.__mainOptKey = key; }catch(_e){}
      mainPartByOptionKey.set(key, p);
    }
    state.__mainPartByOptionKey = mainPartByOptionKey;

    const lightMainPartOpts = partsList.length > (stxPerfLiteUi() ? 40 : 120);
    const mainPlaceholder = (useTierFilter && Number.isFinite(selectedTier))
      ? `Select rarity ID part (${rarityTierLabel(selectedTier)})...`
      : 'Select rarity ID part...';
    const finishMainPartSelect = () => {
      if (state.mainPart){
        const isGuidedClassMod = (() => {
          try {
            const gi = document.getElementById('ccGuidedItemType');
            return !!(gi && /class\s*mod|classmod/i.test(String(gi.value || '').trim()));
          } catch (_) { return false; }
        })();
        const checklistCompRarity = isGuidedClassMod && cat === 'Class Mod' && String(state.mainPart.partType || '').trim().toLowerCase() === 'rarity';
        if (checklistCompRarity) {
          try { stxSyncCustomSelectIfWrapped($('mainPart')); } catch (_e) {}
          refreshBuilder();
          syncMainPartPreview();
          return;
        }
        const prevTok = tokenForPart(state.mainPart);
        const match = partsList.find(p => {
          if (p && state.mainPart && p.__idx != null && state.mainPart.__idx != null && p.__idx === state.mainPart.__idx) return true;
          return tokenForPart(p) === prevTok;
        });
        if (match) $('mainPart').value = String((match && match.__mainOptKey) ? match.__mainOptKey : '');
        else {
          /* Never drop an imported/current body just because filters or the lite option-cap
             omitted it from the rebuilt list — that used to wipe Simple down to skin-only. */
          stxEnsureMainPartSelectOption(state.mainPart);
        }
      } else {
        $('mainPart').value = '';
      }

      try { stxSyncCustomSelectIfWrapped($('mainPart')); } catch (_e) {}

      try {
        var legCtx = 'other';
        var itUiLeg = String(state.itemType || '').trim();
        if (itUiLeg === 'Weapon' || stxSimpleBuilderItemTypeIsHeavyUi(itUiLeg)) legCtx = 'weapon';
        if (window.__ccSimpleLegPerkCtx !== legCtx) {
          window.__ccSimpleLegPerkCtx = legCtx;
          if (typeof window.populateLegendaryPerks === 'function') {
            var ls = document.getElementById('legendaryPerkSelect');
            if (ls) window.populateLegendaryPerks(ls);
          }
        }
      } catch (_) {}

      refreshBuilder();
      syncMainPartPreview();
    };

    setSelectOptions($('mainPart'), partsList, {
      placeholder: mainPlaceholder,
      groupBy: useRarityTierGroups ? ((p) => stxRarityOptgroupLabelFromPart(p, man)) : null,
      getLabel: dropdownLabelForMainPartList,
      getTitle: lightMainPartOpts ? null : ((p)=>{
        let tip = '';
        try { tip = String(dropdownLabelForPart(p) || '').trim(); } catch (_e) {}
        if (String(state.itemType || '').trim() === 'Class Mod'){
          try {
            const code = String(normCode(p && p.code) || '').trim();
            if (code && tip.indexOf(code) === -1) tip = tip ? (tip + ' | ' + code) : code;
          } catch (_e) {}
        }
        return tip;
      }),
      getValue: (p)=>String((p && p.__mainOptKey) ? p.__mainOptKey : ''),
      appendIdRawToLabel: !lightMainPartOpts,
      decorateOption(opt, p){
        if (lightMainPartOpts) {
          /* Rarity ID: no red flavor sublines. */
          opt.removeAttribute('data-cc-barrel-sub');
          opt.removeAttribute('data-cc-part-desc-sub');
          opt.removeAttribute('data-cc-primary-tone');
          return;
        }
        stxApplyCompPartOptionDecoration(opt, p);
        /* Rarity ID dropdown: icons only — skip red text / effect / legendary tone. */
        opt.removeAttribute('data-cc-barrel-sub');
        opt.removeAttribute('data-cc-part-desc-sub');
        opt.removeAttribute('data-cc-primary-tone');
        if (!opt.getAttribute('data-cc-icon')){
          const uR = stxResolvePartIconUrl(p, { partType: 'Rarity', key: 'rarity' }, state.itemType || '');
          if (uR) stxSetOptionDataCcIconFromUrl(opt, uR);
        }
        if (!opt.getAttribute('data-cc-icon') && String(state.itemType || '').trim() === 'Class Mod'){
          const u = stxResolvePartIconUrl(p, { key: 'mainBody', partType: String((p && p.partType) || 'Body') }, 'Class Mod');
          if (u) stxSetOptionDataCcIconFromUrl(opt, u);
          stxApplyClassModBodyLegendaryIconFilter(opt, p);
        } else if (String(state.itemType || '').trim() === 'Class Mod') {
          stxApplyClassModBodyLegendaryIconFilter(opt, p);
        }
      },
      onComplete: finishMainPartSelect
    });
  }

  function refreshMainPart(){
    if (stxPerfLiteUi()) {
      const gen = ++__mainPartAsyncGen;
      const run = () => {
        if (gen !== __mainPartAsyncGen) return;
        try { hydrateTopSelectorsIfNeeded(); } catch (_e) {}
        try { refreshMainPartSync(); } catch (_e) {}
      };
      if (typeof window.stxScheduleIdle === 'function') {
        window.stxScheduleIdle(run, 24);
      } else {
        setTimeout(run, 0);
      }
      return;
    }
    refreshMainPartSync();
  }

  function clearBuilderState(keepTop=false){
    state.detectedCategory = null;
    state.mainPart = keepTop ? state.mainPart : null;
    state.slots = {};
    state.primaryElement = 'None';
    state.elementStack = [];
    state.dualElementUseMaliwanSwitch = false;
    state.extras = [];
  }

  function detectCategoryFromMainPart(p){
    if (!p) return null;
    if (p.__isAicarFullItem || p.__fullDeserialized) return 'Other';
    // Class Mods are stored under the "Character" category in the dataset, but the STX builder
    // needs to treat them as "Class Mod" so the correct schema + ordering is used.
    if (String(state.itemType || '') === 'Class Mod') return 'Class Mod';
    // Keep Enhancement locked when selected in the left panel.
    if (String(state.itemType || '') === 'Enhancement') return 'Enhancement';

    const itemUi = stxNormalizeSimpleBuilderItemTypeUi(String(state.itemType || '').trim());
    const wtUi = String(state.weaponType || '').trim();
    const wantsWeaponHeavyUi = stxSimpleBuilderItemTypeIsHeavyUi(itemUi, wtUi);

    const pcat = String((p && p.category) || '').trim();
    if (pcat === 'Rarity' && itemUi){
      if (wantsWeaponHeavyUi) return 'Weapon';
      return itemUi;
    }
    const code = String((p && p.code) ? p.code : '');
    if (/classmod_/i.test(code)) return 'Class Mod';

    let out = p.category || null;
    const codeN = String(normCode(code) || '').toLowerCase();
    const isHeavySpawn = /_hw[\._]|_hw\b|heavy_weapon_gadget/i.test(codeN);
    // Heavy UI: dataset `Gadget` rows include grenade NCS paths — exclude those only.
    if (out === 'Gadget' && wantsWeaponHeavyUi){
      if (isHeavySpawn || !stxIsDatasetGrenadeGadgetSpawnCode(codeN)) return 'Weapon';
    }
    if ((out === 'Heavy' || out === 'Heavy Weapon') && wantsWeaponHeavyUi) return 'Weapon';
    // Stale shield (or other gear) main part after switching Item Type to Heavy / Heavy Weapon — use weapon slots, not Shield 237/246 pearl rows.
    if (wantsWeaponHeavyUi && out === 'Shield') return 'Weapon';
    return out;
  }

  function isBarrelFamilySchemaSlot(schemaItem, category){
    if (!schemaItem) return false;
    if (schemaItem.key !== 'barrel' && schemaItem.key !== 'barrelAcc') return false;
    return category === 'Weapon' || category === 'Gadget';
  }

  function splitEffectPerkBodyForPreview(ef){
    const s = String(ef || '').trim();
    if (!s) return { perk: '', body: '' };
    const idx = s.indexOf(' - ');
    if (idx >= 0){
      return { perk: s.slice(0, idx).trim(), body: s.slice(idx + 3).trim() };
    }
    if (s.length <= 52 && s.indexOf('.') === -1 && s.split(/\s+/).length <= 6){
      return { perk: s, body: '' };
    }
    return { perk: '', body: s };
  }

  function stripStatsHeadlineIfRedundantForPreview(statsRaw, title){
    const st = String(statsRaw || '').replace(/\s+/g, ' ').trim();
    const tl = String(title || '').replace(/\s+/g, ' ').trim();
    if (!st || !tl) return st;
    if (st.toLowerCase().indexOf(tl.toLowerCase()) !== 0) return st;
    const rest = st.slice(tl.length).replace(/^,\s*/, '').trim();
    return rest || st;
  }

  function barrelHeadlineTitleForPreview(p){
    if (!p) return '';
    const st = String(p.stats != null ? p.stats : (p.stats_text || '')).replace(/\s+/g, ' ').trim();
    if (st && st.indexOf(',') > 0){
      const head = st.slice(0, st.indexOf(',')).trim();
      if (head.length >= 3 && head.length <= 88) return head;
    }
    const nm = String((p.legendaryName || p.name || '')).trim();
    if (nm) return nm;
    return String(displayForPart(p) || '').trim();
  }

  /** Rich preview for barrel / barrel accessory slots: title from stats, perk line, then detail + meta. */
  function formatBarrelFamilyPartPreviewHtml(part){
    if (!part) return '';
    const lines = [];
    const title = barrelHeadlineTitleForPreview(part);
    if (title) lines.push('<div class="stx-part-preview__title">' + escapeHtml(title) + '</div>');
    const efRaw = String(part.effects != null ? part.effects : (part.effect ?? part.effects_text ?? '')).trim();
    const split = splitEffectPerkBodyForPreview(efRaw);
    if (split.perk) lines.push('<div class="stx-part-preview__barrel-perk">' + escapeHtml(split.perk) + '</div>');
    /* Card flavor quote only — never treat ability/effect body as red text. */
    const catalogRed = (typeof window.partRedTextForDropdown === 'function')
      ? String(window.partRedTextForDropdown(part) || '').trim()
      : stxPartRedTextSubForDropdown(part);
    if (catalogRed) {
      lines.push('<div class="stx-part-preview__barrel-redtext" style="color:#ff8f8f;font-size:12px;line-height:1.35;margin-top:2px;">' + escapeHtml(catalogRed.length > 420 ? catalogRed.slice(0, 419) + '…' : catalogRed) + '</div>');
    }
    const statsRaw = String(part.stats != null ? part.stats : (part.stats_text || '')).replace(/\s+/g, ' ').trim();
    const statsTail = statsRaw ? stripStatsHeadlineIfRedundantForPreview(statsRaw, title) : '';
    const descParts = [];
    const effectDesc = (typeof window.partEffectDescForDropdown === 'function')
      ? String(window.partEffectDescForDropdown(part) || '').trim()
      : '';
    function previewTextSame(a, b){
      const x = String(a || '').toLowerCase().replace(/\s+/g, ' ').trim();
      const y = String(b || '').toLowerCase().replace(/\s+/g, ' ').trim();
      if (!x || !y) return false;
      return x === y || (x.length > 12 && y.indexOf(x) >= 0) || (y.length > 12 && x.indexOf(y) >= 0);
    }
    if (effectDesc && !previewTextSame(effectDesc, catalogRed) && !previewTextSame(effectDesc, split.perk)) {
      descParts.push(effectDesc);
    } else if (split.body && !catalogRed && !previewTextSame(split.body, split.perk)) {
      descParts.push(split.body);
    }
    if (statsTail && !previewTextSame(statsTail, effectDesc) && !previewTextSame(statsTail, catalogRed)) {
      descParts.push(statsTail);
    }
    if (descParts.length){
      lines.push('<div class="stx-part-preview__barrel-desc">' + escapeHtml(descParts.join('\n\n')) + '</div>');
    }
    lines.push('<div class="stx-part-preview__barrel-meta">');
    try{
      const tok = tokenForPart(part);
      if (tok) lines.push('<div><span class="muted">Token</span> <code>' + escapeHtml(tok) + '</code></div>');
    }catch(_){}
    const id = String(part.idRaw ?? part.idraw ?? '').trim();
    if (id) lines.push('<div><span class="muted">ID</span> <code>' + escapeHtml(id) + '</code></div>');
    const code = normCode(part.code);
    if (code) lines.push('<div><span class="muted">Spawn</span> <code>' + escapeHtml(code) + '</code></div>');
    if (part.manufacturer) lines.push('<div><span class="muted">Mfr</span> ' + escapeHtml(String(part.manufacturer)) + '</div>');
    if (part.partType) lines.push('<div><span class="muted">Part type</span> ' + escapeHtml(String(part.partType)) + '</div>');
    lines.push('</div>');
    return lines.join('');
  }

  /** Rich preview HTML for the slot under the dropdown (IDs, codes, stats) — complements long option labels. */
  function formatPartPreviewHtml(part){
    if (!part) return '';
    const lines = [];
    const name = displayForPart(part);
    if (name) lines.push('<div class="stx-part-preview__title">' + escapeHtml(name) + '</div>');
    try{
      const tok = tokenForPart(part);
      if (tok) lines.push('<div><span class="muted">Token</span> <code>' + escapeHtml(tok) + '</code></div>');
    }catch(_){}
    const id = String(part.idRaw ?? part.idraw ?? '').trim();
    if (id) lines.push('<div><span class="muted">ID</span> <code>' + escapeHtml(id) + '</code></div>');
    const code = normCode(part.code);
    if (code) lines.push('<div><span class="muted">Spawn</span> <code>' + escapeHtml(code) + '</code></div>');
    if (part.manufacturer) lines.push('<div><span class="muted">Mfr</span> ' + escapeHtml(String(part.manufacturer)) + '</div>');
    if (part.partType) lines.push('<div><span class="muted">Part type</span> ' + escapeHtml(String(part.partType)) + '</div>');
    const statsRaw = part.stats != null ? String(part.stats) : '';
    const stats = statsRaw.replace(/\s+/g, ' ').trim();
    if (stats) lines.push('<div><span class="muted">Stats</span> ' + escapeHtml(stats.length > 520 ? stats.slice(0, 519) + '…' : stats) + '</div>');
    const ef = String(part.effects ?? part.effect ?? '').trim();
    const effectDesc = (typeof window.partEffectDescForDropdown === 'function')
      ? String(window.partEffectDescForDropdown(part) || '').trim()
      : '';
    if (effectDesc) lines.push('<div><span class="muted">Effect</span> ' + escapeHtml(effectDesc.length > 360 ? effectDesc.slice(0, 359) + '…' : effectDesc) + '</div>');
    else if (ef) lines.push('<div><span class="muted">Effect</span> ' + escapeHtml(ef.length > 360 ? ef.slice(0, 359) + '…' : ef) + '</div>');
    const catalogRed = (typeof window.partRedTextForDropdown === 'function')
      ? String(window.partRedTextForDropdown(part) || '').trim()
      : stxPartRedTextSubForDropdown(part);
    if (catalogRed) lines.push('<div class="stx-part-preview__barrel-redtext" style="color:#ff8f8f;font-size:12px;line-height:1.35;margin-top:4px;"><span class="muted">Red text</span> ' + escapeHtml(catalogRed) + '</div>');
    let tip = '';
    try{
      if (typeof window.partTooltipText === 'function'){
        tip = String(window.partTooltipText(part) || '').trim();
      }
    }catch(_){}
    if (tip && tip.length > 12){
      const clipped = tip.length > 520 ? tip.slice(0, 519) + '…' : tip;
      const n = String(name || '').trim();
      const tipRedundant = n && (clipped === n || (clipped.startsWith(n) && clipped.length < n.length + 25));
      if (!tipRedundant) lines.push('<div class="small muted" style="margin-top:6px;opacity:.92;">' + escapeHtml(clipped) + '</div>');
    }
    return lines.join('');
  }

  function stxMaxImportOrderInPartArray(arr){
    if (!Array.isArray(arr)) return 0;
    let max = 0;
    for (const p of arr){
      const io = Number(p && p.__importOrder);
      if (Number.isFinite(io) && io > max) max = io;
    }
    return max;
  }

  function stxNextImportOrders(existingArr, count){
    let base = stxMaxImportOrderInPartArray(existingArr);
    const out = [];
    for (let i = 0; i < count; i++) out.push(++base);
    return out;
  }

  function stxClonePartWithImportOrder(part, ord){
    if (!part || typeof part !== 'object') return part;
    const c = Object.assign({}, part);
    c.__importOrder = ord;
    return c;
  }

  function syncMainPartPreview(){
    const el = document.getElementById('stxMainPartPreview');
    if (!el) return;
    const sel = $('mainPart');
    if (!sel){
      el.innerHTML = '';
      return;
    }
    if (sel.disabled){
      const ph = (sel.options && sel.options[0]) ? String(sel.options[0].textContent || '').trim() : '';
      el.innerHTML = '<span class="muted">' + escapeHtml(ph || 'Complete the steps above first.') + '</span>';
      return;
    }
    const k = sel.value;
    const map = state.__mainPartByOptionKey;
    const p = (k && map && typeof map.get === 'function') ? map.get(k) : null;
    if (!k || !p){
      el.innerHTML = '<span class="muted">Select a main / prefix part to see token, IDs, spawn code, and stats.</span>';
      return;
    }
    if (p.__isAicarFullItem && p.__fullDeserialized){
      const fs = String(p.__fullDeserialized || '').trim();
      el.innerHTML = '<div class="stx-part-preview__title">' + escapeHtml(displayForPart(p)) + '</div>'
        + '<div class="small muted" style="margin-bottom:6px;">Full deserialized payload (trimmed)</div>'
        + '<code>' + escapeHtml(fs.length > 900 ? fs.slice(0, 899) + '…' : fs) + '</code>';
      return;
    }
    el.innerHTML = formatPartPreviewHtml(p);
  }

  function buildSlotControl(schemaItem, category){
    const slot = document.createElement('div');
    slot.className = 'slot';

    const top = document.createElement('div');
    top.className = 'top';

    const name = document.createElement('div');
    name.className = 'name';
    let slotLabel = schemaItem.label;
    if ((category === 'Weapon' || category === 'Gadget') && stxWeaponSlotIsCoreRequired(schemaItem.key)) {
      slotLabel += ' (required)';
    } else if ((category === 'Weapon' || category === 'Gadget') && stxWeaponSlotIsUnderbarrelFamily(schemaItem.key)) {
      slotLabel += ' (optional)';
    }
    name.textContent = slotLabel;
    if ((category === 'Weapon' || category === 'Gadget') && schemaItem.key === 'underbarrelAccVis') {
      name.title = STX_UNDERBARREL_VISUAL_HINT;
    }

    const btnClear = document.createElement('button');
    btnClear.type = 'button';
    btnClear.textContent = 'Clear';
    btnClear.className = 'danger';
    btnClear.style.padding = '7px 10px';
    btnClear.addEventListener('click', ()=>{
      clearImportedOutputLock();
      delete state.slots[schemaItem.key];
      if (state.__simpleSlotDropdownSelections) delete state.__simpleSlotDropdownSelections[schemaItem.key];
      refreshBuilder();
    });

    top.appendChild(name);
    top.appendChild(btnClear);

    // Stable retrieval: attach index to objects
    ensureAllPartsIndexed();

    let rawOpts = [];
    const isShieldType1ElementSlot = (category === 'Shield' && schemaItem && schemaItem.customType === 'type1Element');
    const isClassModElementSlot = (category === 'Class Mod' && schemaItem && schemaItem.customType === 'classModElement');
    const isShieldBodyLegendarySlot = (category === 'Shield' && schemaItem && schemaItem.key === 'bodyLegendary');
    const isShieldMainBodySlot = (category === 'Shield' && schemaItem && (schemaItem.key === 'mainBody' || schemaItem.key === 'body'));
    if (isShieldType1ElementSlot){
      const seenElem = new Set();
      const elemRows = [];
      for (const p of getAllParts()){
        if (!p || String(p.category || '').trim() !== 'Shield') continue;
        const cLo = String(normCode(p.code || p.spawnCode || '') || '').toLowerCase();
        if (!/^shield\.part_(corrosive|cryo|fire|radiation|shock)$/.test(cLo)) continue;
        if (seenElem.has(cLo)) continue;
        seenElem.add(cLo);
        elemRows.push(Object.assign({}, p));
      }
      elemRows.sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
      const noneElem = {
        category: 'Shield',
        manufacturer: '',
        partType: 'TypeID1Element',
        name: 'None',
        code: '',
        idRaw: '',
        family: null,
        id: null,
        __isShieldElementNone: true
      };
      rawOpts = [noneElem].concat(elemRows);
    } else if (isClassModElementSlot){
      rawOpts = CLASSMOD_ELEMENT_OVERRIDES
        .filter(e => e && e.code)
        .map(e => {
          const m = String(e.code || '').match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
          const fam = m ? Number(m[1]) : null;
          const id = m ? Number(m[2]) : null;
          return {
            category: 'Character',
            manufacturer: state.manufacturer || '',
            partType: 'Element',
            name: e.label,
            code: String(e.code || '').trim(),
            idRaw: (Number.isFinite(fam) && Number.isFinite(id)) ? `${fam}:${id}` : '',
            family: Number.isFinite(fam) ? fam : null,
            id: Number.isFinite(id) ? id : null
          };
        })
        .sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    } else if (schemaItem && schemaItem.customType === 'grenadeKitStats') {
      const man = String(state.manufacturer || '').trim().toLowerCase();
      rawOpts = getAllParts().filter(p=>{
        if (!p) return false;
        const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
        if (!/grenade_gadget\.part_stat_/.test(c)) return false;
        if (isAllPartsEnabled()) return true;
        return stxGrenadeGadgetRowMatchesSelectedManufacturer(c, man);
      }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    } else if (schemaItem && (schemaItem.customType === 'grenadePearlElem' || schemaItem.key === 'pearlElem') && category === 'Grenade') {
      rawOpts = getAllParts().filter(weaponPearlElemPartMatch)
        .sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    } else if (schemaItem && (schemaItem.customType === 'grenadePearlStat' || schemaItem.key === 'pearlStat') && category === 'Grenade') {
      rawOpts = getAllParts().filter(weaponPearlStatPartMatch)
        .sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    } else if (schemaItem && schemaItem.customType === 'repkitBase') {
      const man = String(state.manufacturer || '').trim().toLowerCase();
      const spawn = stxRepkitSpawnPrefixForUiManufacturer(man);
      const idBodyRe = /(^|[^a-z0-9])(?:bor|dad|jak|mal|ord|ted|tor|vla)_repair_kit\.part_(?:borg|dad|jak|mal|ord|ted|tor|vla)($|[^a-z0-9])/i;
      rawOpts = getAllParts().filter(p=>{
        if (!p || !spawn) return false;
        const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
        if (c.indexOf(spawn + '.part_') !== 0) return false;
        if (idBodyRe.test(c)) return false;
        if (c.indexOf(spawn + '.part_payload_') === 0) return false;
        if (c.indexOf(spawn + '.part_element_') === 0) return false;
        if (c.indexOf(spawn + '.part_firmware') === 0) return false;
        if (c.indexOf(spawn + '.part_aug_') === 0) return false;
        if (c.indexOf(spawn + '.comp_') === 0) return false;
        if (isAllPartsEnabled()) return true;
        return String(p.category || '').trim() === 'Repkit';
      }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    } else if (schemaItem && schemaItem.customType === 'enhancementGunStats') {
      // Enhancement secondary/universal-style stats for modded classmods (exclude firmware + rarity comps).
      rawOpts = getAllParts().filter(p=>{
        if (!p) return false;
        if (String(p.category || '').trim() !== 'Enhancement') return false;
        if (stxIsBrokenClassmodDatasetPlaceholderPart(p)) return false;
        const codeL = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
        const ptL = String((p.partType || p.kind || '') || '').toLowerCase();
        if (ptL === 'firmware' || codeL.indexOf('part_firmware') !== -1) return false;
        if (ptL === 'core' || codeL.indexOf('part_core') !== -1) return false;
        if (/\.comp_\d+_/.test(codeL) || ptL === 'rarity' || ptL === 'item card') return false;
        const isStats = ptL === 'stats' || ptL === 'stat' || /^stats?\s*[23]$/.test(ptL) || codeL.indexOf('part_stat') !== -1;
        if (!isStats) return false;
        const id = Number(p.id != null ? p.id : NaN);
        return Number.isFinite(id);
      }).map(p=>{
        const id = Number(p.id);
        const codeL = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
        let fam = Number(p.familyId != null ? p.familyId : p.family);
        if (!Number.isFinite(fam)) {
          if (codeL.indexOf('enhancement.') === 0) fam = 247;
          else {
            const inferred = stxEnhancementTypeFamilyIdFromSpawnCode(codeL);
            fam = Number.isFinite(inferred) ? inferred : 247;
          }
        }
        return Object.assign({}, p, { familyId: fam, family: fam, idRaw: fam + ':' + id, id });
      }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    } else if (schemaItem && schemaItem.customType === 'otherParts') {
      // Category-wide stackable pool. Firmware + rarity comps have their own pickers — keep them out of Other.
      rawOpts = filterParts({
        category,
        manufacturer: '',
        weaponType: '',
        partType: undefined,
        ignoreWeaponType: true
      }).filter(p=>{
        if (!p) return false;
        const c = String((p && p.code) ? p.code : '').trim();
        if (/^\{\s*27\s*:\s*\d+\s*\}$/.test(c)) return false;
        const pt = String((p.partType || p.kind || '') || '').trim().toLowerCase();
        const code = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
        /* Firmware always has its own slot — never dump into Other parts. */
        if (pt === 'firmware' || /part_firmware|\.part_firmware/.test(code)) return false;
        /* Rarity comps / item-card rarity ids belong to the left rarity picker, not Other. */
        if (
          pt === 'rarity' ||
          pt === 'secondary rarity' ||
          pt === 'rarity components' ||
          pt === 'item card' ||
          /\.comp_/.test(code) ||
          /(?:^|[._])comp_0[1-6]_/.test(code) ||
          /pearl_/.test(code)
        ) return false;
        return true;
      }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    } else if (category === 'Weapon' && schemaItem && schemaItem.customType === 'weaponAdditionalParts'){
      rawOpts = filterParts({
        category: 'Weapon',
        manufacturer: '',
        weaponType: '',
        partType: undefined,
        ignoreWeaponType: true
      }).filter(p => {
        if (!p) return false;
        const c = String((p && p.code) ? p.code : '').trim();
        if (/^\{\s*27\s*:\s*\d+\s*\}$/.test(c)) return false;
        return true;
      }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    } else if (category === 'Weapon' && schemaItem && (schemaItem.ncsSlot === 'pearl_elem' || schemaItem.key === 'pearlElem')){
      rawOpts = mergeUniquePartOpts(rawOpts, getAllParts().filter(weaponPearlElemPartMatch))
        .sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    } else if (category === 'Weapon' && schemaItem && (schemaItem.ncsSlot === 'pearl_stat' || schemaItem.key === 'pearlStat')){
      rawOpts = mergeUniquePartOpts(rawOpts, getAllParts().filter(weaponPearlStatPartMatch))
        .sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    } else {
      const isLooseFilter = (schemaItem.key === 'legendary');
      const slotKeySimple = schemaItem && schemaItem.key ? String(schemaItem.key) : '';
      /* Slots with schema `partType: ''` often need the whole category pool; dataset rows use mixed labels.
         Omit strict partType matching and let category-specific filters below narrow options. */
      const looseEmptyPartTypeSlot =
        (category === 'Shield' && ['resistance', 'armor237', 'energy248'].includes(slotKeySimple)) ||
        (category === 'Repkit' && ['perkResist', 'perkImmunity', 'perkNova', 'perkSplat'].includes(slotKeySimple)) ||
        ((category === 'Grenade' || category === 'Gadget' || category === 'Enhancement' || category === 'Character') && slotKeySimple === 'special');
      // Heavy Weapon pools frequently live under generic manufacturers ("gadgets") even when the user selects Maliwan/Ripper/etc.
      // Keep shared pools visible for the slots that behave universally (licensed/stat/firmware/secondary ele) and for loose/multi pools.
      const isSharedWeaponSlot = (category === 'Weapon' && (slotKeySimple === 'licensed' || slotKeySimple === 'statMod' || slotKeySimple === 'endgame' || slotKeySimple === 'firmware' || slotKeySimple === 'secondaryEle'));
      const relaxShieldGadgetMfr = (category === 'Shield' && ['armor237', 'energy248', 'primary246', 'secondary246', 'pearlElem246', 'pearlStat246', 'resistance', 'firmware246', 'elementType1'].includes(slotKeySimple));
      const isItemBodyFamilySlot = stxSlotRequiresItemManufacturer(schemaItem, category);
      /* Body element parts (e.g. Jakobs `part_body_ele_*`) are filed under normal Weapon rows; Heavy UI must still list them
       * for any selected heavy manufacturer (pools are shared like legendary/stat slots). */
      const manufacturerForSlot = isItemBodyFamilySlot
        ? state.manufacturer
        : ((isShieldBodyLegendarySlot || isLooseFilter || isSharedWeaponSlot
          || (category === 'Weapon' && slotKeySimple === 'bodyEle'))
          ? ''
          : state.manufacturer);
      const partTypeForSlot = ((category === 'Shield' && (isShieldBodyLegendarySlot || isShieldMainBodySlot)) || (isLooseFilter && category !== 'Weapon' && category !== 'Gadget') || looseEmptyPartTypeSlot)
        ? undefined
        : schemaItem.partType;
      
      const filterParams = {
        category,
        manufacturer: manufacturerForSlot,
        // Licensed / Stat / Endgame / Firmware / Secondary Element pools are often tagged with non–Heavy-Weapon itemType; keep them visible for Heavy.
        weaponType: (() => {
          if (isLooseFilter && category === 'Weapon') return state.weaponType || '';
          if (isLooseFilter && category === 'Gadget') return 'Heavy Weapon';
          if (category==='Weapon' && !isLooseFilter && slotKeySimple !== 'statMod' && slotKeySimple !== 'endgame' && slotKeySimple !== 'licensed' && slotKeySimple !== 'bodyEle' && slotKeySimple !== 'firmware' && slotKeySimple !== 'secondaryEle') return state.weaponType;
          return '';
        })(),
        partType: partTypeForSlot,
        relaxShieldGadgetMfr: !!relaxShieldGadgetMfr,
        forceItemManufacturer: !!isItemBodyFamilySlot,
        ignoreWeaponType: !!(schemaItem.customType === 'otherParts' || schemaItem.customType === 'weaponAdditionalParts' || slotKeySimple === 'secondaryEle')
      };

      rawOpts = filterParts(filterParams).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));

      if (isItemBodyFamilySlot && state.manufacturer){
        const manLo = String(state.manufacturer || '').trim().toLowerCase();
        const wtBody = String(state.weaponType || '').trim();
        rawOpts = rawOpts.filter((p)=>{
          const c = String(normCode(p && p.code || '') || '').toLowerCase();
          if (category === 'Weapon') {
            if (slotKeySimple === 'body') {
              /* Strict: only the body for this manufacturer + weapon type (e.g. jak_ar.part_body). */
              if (!wtBody) return false;
              return stxIsWeaponNaturalBodyPoolRowCode(c, manLo, wtBody);
            }
            return stxWeaponRowMatchesSelectedManufacturer(c, manLo, state.weaponType);
          }
          if (category === 'Shield') return stxShieldGadgetRowMatchesSelectedManufacturer(c, manLo);
          if (category === 'Grenade') {
            if (slotKeySimple === 'body') return stxIsGrenadeBodyPoolRowCode(c) && stxGrenadeGadgetRowMatchesSelectedManufacturer(c, manLo);
            return stxGrenadeGadgetRowMatchesSelectedManufacturer(c, manLo);
          }
          if (category === 'Enhancement') return stxEnhancementGadgetRowMatchesSelectedManufacturer(c, manLo);
          return true;
        });
        /* Body: partType filter can miss the natural body — rescue from full parts pool. */
        if (category === 'Weapon' && slotKeySimple === 'body' && (!rawOpts || !rawOpts.length) && wtBody) {
          const rescued = [];
          const seenTok = Object.create(null);
          const allP = (typeof getAllParts === 'function') ? getAllParts() : (Array.isArray(window.PARTS) ? window.PARTS : []);
          const pushRescue = (pred)=>{
            for (let ri = 0; ri < allP.length; ri++) {
              const rp = allP[ri];
              if (!rp) continue;
              const rc = String(normCode(rp.code || '') || '').toLowerCase();
              if (!pred(rc, rp)) continue;
              const tok = String((rp.idRaw != null ? rp.idRaw : rp.id) || rc);
              if (seenTok[tok]) continue;
              seenTok[tok] = true;
              rescued.push(rp);
            }
          };
          pushRescue((rc) => stxIsWeaponNaturalBodyPoolRowCode(rc, manLo, wtBody));
          /* Dataset gaps: some mfr/type combos lack `*.part_body` but still have letter Body rows. */
          if (!rescued.length) {
            pushRescue((rc, rp) => {
              if (stxIsWeaponBodySlotFallbackRowCode(rc, manLo, wtBody)) return true;
              const pt = String(rp.partType || '').trim().toLowerCase();
              return pt === 'body' && stxWeaponRowMatchesSelectedManufacturer(rc, manLo, wtBody)
                && !/part_body_(?:bolt|flap|ele|mag)/.test(rc);
            });
          }
          if (rescued.length) rawOpts = rescued.sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
        }
        if (category === 'Grenade' && slotKeySimple === 'body' && (!rawOpts || !rawOpts.length)) {
          const rescuedG = [];
          const seenG = Object.create(null);
          const allG = (typeof getAllParts === 'function') ? getAllParts() : [];
          for (let gi = 0; gi < allG.length; gi++) {
            const gp = allG[gi];
            if (!gp) continue;
            const gc = String(normCode(gp.code || '') || '').toLowerCase();
            if (!stxIsGrenadeBodyPoolRowCode(gc)) continue;
            if (!stxGrenadeGadgetRowMatchesSelectedManufacturer(gc, manLo)) continue;
            const tok = String((gp.idRaw != null ? gp.idRaw : gp.id) || gc);
            if (seenG[tok]) continue;
            seenG[tok] = true;
            rescuedG.push(gp);
          }
          if (rescuedG.length) rawOpts = rescuedG.sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
        }
      }

      // Licensed Manufacturer Part is a code-shape slot (`barrel_licensed`), not a general Manufacturer Part bucket.
      if (category === 'Weapon' && schemaItem && String(schemaItem.key || '') === 'licensed' && rawOpts && rawOpts.length){
        const lic = rawOpts.filter(p => String(normCode(p && p.code) || '').toLowerCase().includes('barrel_licensed'));
        if (lic.length) rawOpts = lic;
      }
      
      if (isLooseFilter && schemaItem.partType) {
        const targetPt = String(schemaItem.partType).trim().toLowerCase();
        const isRepkitLegendary = (category === 'Repkit' && targetPt === 'legendary perks');
        if (!isRepkitLegendary){
          rawOpts = rawOpts.filter(p => String(p.partType || '').trim().toLowerCase() === targetPt);
        }
        /* Repkit: merge Gadget legendary perks + loosely-tagged repkit rows (often `Perk` / empty partType). */
        if (targetPt === 'legendary perks' && category === 'Repkit'){
          if (isRepkitLegendary){
            rawOpts = rawOpts.filter(p => {
              if (String(p.category || '').trim() !== 'Repkit') return false;
              const pt = String(p.partType || '').trim().toLowerCase();
              const c = String(normCode(p.code || '') || '').toLowerCase();
              const n = String((p.name || '')).toUpperCase();
              if (!c || n === 'PLACEHOLDER') return false;
              if (/repair_kit\.part_payload_|repair_kit\.part_element_|repair_kit\.part_firmware|repair_kit\.part_aug_/.test(c)) return false;
              if (pt === 'legendary perks' || pt === 'legendary perk' || pt === 'legendary') return true;
              if (pt === 'perk' || pt === 'augment' || pt === ''){
                if (/unique|legendary/i.test(c + ' ' + String((p.name || '')).toLowerCase())) return true;
              }
              return false;
            });
          }
          const legGadget = filterParts({
            category:'Gadget',
            manufacturer:'',
            weaponType:'',
            partType: undefined
          }).filter(p => String(p.partType || '').trim().toLowerCase() === 'legendary perks'
            && !stxIsDatasetGrenadeGadgetSpawnCode(String(normCode(p.code || '') || '').toLowerCase()));
          rawOpts = rawOpts.concat(legGadget);
          const legSeen = new Set();
          rawOpts = rawOpts.filter(p=>{
            const k = stxStableDropdownDedupeKey(p);
            if (!k || legSeen.has(k)) return false;
            legSeen.add(k);
            return true;
          });
        }
        if (targetPt === 'legendary perks' && category === 'Weapon'){
          const wtLeg = String(state.weaponType || '').trim();
          const barrelLegendary = filterParts({
            category:'Weapon',
            manufacturer: '',
            weaponType: wtLeg,
            partType:'Barrel',
            ignoreWeaponType: false
          }).filter(p => stxPartCarriesLegendaryEffectWeaponFamilyBarrel(p)
            && stxPartMatchesLegendaryPoolWeaponType(p, wtLeg));
          rawOpts = rawOpts.concat(barrelLegendary);
          const heavyWt = String(state.weaponType || '').trim().toLowerCase();
          const isHeavyWeaponCtx = heavyWt === 'heavy weapon' || heavyWt === 'heavy' || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType);
          if (isHeavyWeaponCtx){
            const legGadget = filterParts({
              category:'Gadget',
              manufacturer:'',
              weaponType:'',
              partType: undefined
            }).filter(p => String(p.partType || '').trim().toLowerCase() === 'legendary perks'
              && !stxIsDatasetGrenadeGadgetSpawnCode(String(normCode(p.code || '') || '').toLowerCase()));
            /* Heavy builds: also surface HW unique / named barrels (Heimdahl, Sprezzatura, …).
               These often live under Gadget or Heavy Weapon with partType Barrel, not Legendary Perks. */
            const heavyGadgetBarrels = filterParts({
              category:'Gadget',
              manufacturer:'',
              weaponType:'',
              partType:'Barrel',
              ignoreWeaponType: true
            }).filter(p => stxPartCarriesLegendaryEffectWeaponFamilyBarrel(p));
            const heavyCatRows = filterParts({
              category:'Heavy Weapon',
              manufacturer:'',
              weaponType:'',
              partType: undefined,
              ignoreWeaponType: true
            }).filter(p => {
              const pt = String(p.partType || '').trim().toLowerCase();
              return pt === 'legendary perks' || pt === 'legendary perk' || stxPartCarriesLegendaryEffectWeaponFamilyBarrel(p);
            });
            const heavyWeaponBarrels = filterParts({
              category:'Weapon',
              manufacturer:'',
              weaponType:'Heavy Weapon',
              partType:'Barrel',
              ignoreWeaponType: true
            }).filter(p => stxPartCarriesLegendaryEffectWeaponFamilyBarrel(p)
              && stxPartMatchesLegendaryPoolWeaponType(p, 'Heavy Weapon'));
            rawOpts = rawOpts.concat(legGadget, heavyGadgetBarrels, heavyCatRows, heavyWeaponBarrels);
          } else {
            /* Regular gun builds: also surface heavy legendary barrels + heavy perk rows in the same dropdown. */
            const heavyBarrelPool = filterParts({
              category:'Weapon',
              manufacturer:'',
              weaponType:'',
              partType:'Barrel',
              ignoreWeaponType: true
            }).filter(p => stxPartCarriesLegendaryEffectWeaponFamilyBarrel(p)
              && stxPartMatchesLegendaryPoolWeaponType(p, 'Heavy Weapon'));
            const heavyGadgetBarrels = filterParts({
              category:'Gadget',
              manufacturer:'',
              weaponType:'',
              partType:'Barrel',
              ignoreWeaponType: true
            }).filter(p => stxPartCarriesLegendaryEffectWeaponFamilyBarrel(p));
            const heavyLegRows = filterParts({
              category:'Gadget',
              manufacturer:'',
              weaponType:'',
              partType: undefined,
              ignoreWeaponType: true
            }).filter(p => String(p.partType || '').trim().toLowerCase() === 'legendary perks'
              && !stxIsDatasetGrenadeGadgetSpawnCode(String(normCode(p.code || '') || '').toLowerCase()));
            const heavyCatRows = filterParts({
              category:'Heavy Weapon',
              manufacturer:'',
              weaponType:'',
              partType: undefined,
              ignoreWeaponType: true
            }).filter(p => {
              const pt = String(p.partType || '').trim().toLowerCase();
              return pt === 'legendary perks' || pt === 'legendary perk' || stxPartCarriesLegendaryEffectWeaponFamilyBarrel(p);
            });
            rawOpts = rawOpts.concat(heavyBarrelPool, heavyGadgetBarrels, heavyLegRows, heavyCatRows);
          }
          const legSeenW = new Set();
          rawOpts = rawOpts.filter(p=>{
            const k = stxStableDropdownDedupeKey(p);
            if (!k || legSeenW.has(k)) return false;
            legSeenW.add(k);
            return true;
          });
        }
        if (targetPt === 'legendary perks' && category === 'Gadget'){
          const barrelLegendary = filterParts({
            category:'Gadget',
            manufacturer: '',
            weaponType:'',
            partType:'Barrel'
          }).filter(p => stxPartCarriesLegendaryEffectWeaponFamilyBarrel(p));
          rawOpts = rawOpts.concat(barrelLegendary);
        }
        if (targetPt === 'legendary perks'){
          rawOpts = rawOpts.filter((p)=>{
            const pt = String(p.partType || '').trim().toLowerCase();
            if (pt === 'rarity') return false;
            const c = String(normCode(p.code || '') || '').toLowerCase();
            if (/(?:^|[._])comp_0[1-6]_/.test(c) || /pearl_/.test(c) || /\.comp_/.test(c)) return false;
            return true;
          });
          if (category === 'Weapon'){
            const wtLeg = String(state.weaponType || '').trim();
            if (wtLeg) rawOpts = rawOpts.filter(p => stxPartMatchesLegendaryPoolWeaponType(p, wtLeg));
          }
        }
        rawOpts = rawOpts.sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
      }

      if (category === 'Weapon' && schemaItem && schemaItem.ncsSlot){
        rawOpts = applyWeaponNcsSlotOptionFilter(schemaItem.ncsSlot, rawOpts);
      }
      if (category === 'Weapon' && schemaItem && schemaItem.key === 'bodyEle'){
        const broad = filterParts({
          category:'Weapon',
          manufacturer:'',
          weaponType:'',
          partType:'Body Element'
        });
        const seenK = new Set();
        for (const p of rawOpts){
          const k = stxStableDropdownDedupeKey(p);
          if (k) seenK.add(k);
        }
        for (const p of broad){
          const k = stxStableDropdownDedupeKey(p);
          if (k && seenK.has(k)) continue;
          if (k) seenK.add(k);
          rawOpts.push(p);
        }
        rawOpts = rawOpts.sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
        if (!rawOpts.length){
          rawOpts = getAllParts().filter(p=>{
            if (!p) return false;
            if (String(p.category || '').trim() !== 'Weapon') return false;
            const c = String(normCode(p.code || '') || '').toLowerCase();
            return c.includes('part_body_ele');
          }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
        }
      }
      if (category === 'Weapon' && schemaItem && (schemaItem.key === 'statMod' || schemaItem.key === 'endgame') && !rawOpts.length){
        rawOpts = filterParts({
          category:'Weapon',
          manufacturer:'',
          weaponType:'',
          partType:'Stat Modifier'
        }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
      }
      if (category === 'Weapon' && schemaItem && (schemaItem.key === 'statMod' || schemaItem.key === 'endgame')){
        rawOpts = rawOpts.filter((p)=>{
          const pt = String(p.partType || '').trim().toLowerCase();
          if (pt === 'legendary perks' || pt === 'rarity') return false;
          const c = String(normCode(p.code || '') || '').toLowerCase();
          if (/(?:^|[._])comp_0[1-6]_/.test(c) || /pearl_/.test(c) || /\.comp_/.test(c)) return false;
          if (/part_stat|\.endgame\b|part_endgame|stat_augment/.test(c)) return true;
          return pt === 'stat modifier';
        }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
        // Same boost tokens as Tools → Preset Parts (damage/accuracy/etc.).
        const boostParts = stxSimpleCollectPresetBoostPartsForStatMod();
        if (boostParts.length){
          rawOpts = mergeUniquePartOpts(boostParts, rawOpts)
            .sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
        }
      }
      if (category === 'Weapon' && schemaItem && schemaItem.key === 'firmware'){
        const fwParts = stxSimpleCollectFirmwareParts();
        if (fwParts.length){
          rawOpts = fwParts.sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
        } else if (!rawOpts.length){
          rawOpts = filterParts({
            category:'Weapon',
            manufacturer:'',
            weaponType:'',
            partType:'Firmware'
          }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
        }
      }
      if (isShieldMainBodySlot && !rawOpts.length){
        rawOpts = filterParts({
          category,
          manufacturer: '',
          weaponType: '',
          partType: ''
        }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
      }
      if (category === 'Class Mod' && schemaItem && schemaItem.partType === 'Name+Skin'){
        // Keep Prefix Part aligned with the main page classmod name list (legacy per-class pools).
        const legacyNameOpts = getLegacyClassModNameParts(state.manufacturer)
          .filter((p)=>!stxIsBrokenClassmodDatasetPlaceholderPart(p))
          .sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
        if (legacyNameOpts.length > rawOpts.length) rawOpts = legacyNameOpts;
        if (rawOpts.length <= 1){
          // In some builds legacy classmod pools load later; retry after merging them.
          try{ mergeLegacyClassModPartsIntoAllParts(); }catch(_e){}
          const retry = filterParts({
            category,
            manufacturer: state.manufacturer,
            weaponType: '',
            partType: schemaItem.partType
          }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
          if (retry.length > rawOpts.length) rawOpts = retry;
        }
        rawOpts = (rawOpts || []).filter((p)=>!stxIsBrokenClassmodDatasetPlaceholderPart(p));
      }
      if (category === 'Class Mod' && schemaItem && schemaItem.partType === 'Skill'){
        // Match main classmod builder: class-specific skill pool from the selected character.
        // Never keep Nexus "Passive Blue … Tier N" stubs — they break names + perk icons.
        try{
          if (typeof window.__ccEnsureClassmodSkillsData === 'function') {
            var skillsP = window.__ccEnsureClassmodSkillsData();
            var skillsReady = typeof window.__ccClassmodSkillsLoaded === 'function'
              ? !!window.__ccClassmodSkillsLoaded()
              : false;
            if (skillsP && typeof skillsP.then === 'function' && !skillsReady) {
              skillsP.then(function () {
                try {
                  if (typeof window.__ccClassmodSkillsReady === 'function') window.__ccClassmodSkillsReady();
                  else if (typeof refreshBuilder === 'function') refreshBuilder();
                } catch (_e) {}
              });
            }
          }
        }catch(_e){}
        try{ mergeLegacyClassModPartsIntoAllParts(); }catch(_e){}
        let legacySkillOpts = getLegacyClassModSkillParts(state.manufacturer)
          .filter((p)=>!stxIsBrokenClassmodDatasetPlaceholderPart(p))
          .sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
        if (!legacySkillOpts.length) {
          /* Manufacturer may be display name (Vex) or internal (Siren). */
          const aliases = [];
          try {
            const key = classModKeyForCharacter(state.manufacturer);
            if (key === 'vex') aliases.push('Siren', 'Vex', 'Dark Siren');
            else if (key === 'amon') aliases.push('Paladin', 'Amon');
            else if (key === 'rafa') aliases.push('Exo Soldier', 'Rafa');
            else if (key === 'harlowe') aliases.push('Gravitar', 'Harlowe');
            else if (key === 'c4sh') aliases.push('Robodealer', 'C4sh');
          } catch (_e) {}
          for (let ai = 0; ai < aliases.length && !legacySkillOpts.length; ai++) {
            legacySkillOpts = getLegacyClassModSkillParts(aliases[ai])
              .filter((p)=>!stxIsBrokenClassmodDatasetPlaceholderPart(p))
              .sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
          }
        }
        if (legacySkillOpts.length) rawOpts = legacySkillOpts;
        else {
          rawOpts = (rawOpts || []).filter((p)=>!stxIsBrokenClassmodDatasetPlaceholderPart(p));
        }
      }
      if (category === 'Grenade' && schemaItem && schemaItem.key === 'special'){
        rawOpts = rawOpts.filter((p)=>{
          const c = String(normCode(p && p.code || '') || '').toLowerCase();
          const pt = String((p && p.partType) || '').trim().toLowerCase();
          if (pt === 'firmware' || /part_firmware|\.part_firmware/.test(c)) return false;
          if (pt === 'payload' || /\.part_payload_/.test(c) || stxIsGrenadePayloadPoolRowCode(c)) return false;
          if (pt === 'augment' || stxIsGrenadePayloadAugmentPoolRowCode(c)) return false;
          if (stxIsGrenadeBodyPoolRowCode(c)) return false;
          if (/grenade_gadget\.part_stat_/.test(c)) return false;
          if (/(?:^|[._])comp_0[0-9]_/.test(c) || /\.comp_/.test(c)) return false;
          return true;
        }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
      }
      if (category === 'Grenade' && schemaItem && schemaItem.key === 'body'){
        /* Body slot: every grenade body part (all manufacturers). Rarity-matched body stays at the top. */
        const allBodies = stxCollectAllGrenadeBodyParts();
        if (allBodies.length) rawOpts = allBodies;
        const rarityPart = state.mainPart && String(state.mainPart.partType || '').trim().toLowerCase() === 'rarity'
          ? state.mainPart
          : (state.slots && state.slots.rarity) || null;
        const rp = Array.isArray(rarityPart) ? rarityPart[0] : rarityPart;
        rawOpts = stxSortGrenadeBodyOptionsForRarity(rawOpts || [], rp, state.manufacturer);
      }
      if ((category === 'Weapon' || category === 'Heavy' || category === 'Heavy Weapon') && schemaItem && schemaItem.key === 'barrel'){
        const rarityPartB = state.mainPart && String(state.mainPart.partType || '').trim().toLowerCase() === 'rarity'
          ? state.mainPart
          : (state.slots && state.slots.rarity) || null;
        const rpB = Array.isArray(rarityPartB) ? rarityPartB[0] : rarityPartB;
        rawOpts = stxSortWeaponBarrelOptionsForRarity(rawOpts || [], rpB);
      }
      if (category === 'Weapon' && schemaItem && String(schemaItem.key || '') === 'secondaryEle'){
        // Always keep Maliwan dual-element switches available (works on non-Maliwan guns too).
        const isSecEle = (p)=>{
          const c = String(normCode(p && p.code || '') || '').toLowerCase();
          return c.includes('part_secondary_elem') && c.includes('_mal');
        };
        let sec = (rawOpts || []).filter(isSecEle);
        if (!sec.length){
          sec = getAllParts().filter((p)=>{
            if (!p) return false;
            const cat = String(p.category || '').trim();
            if (cat && cat !== 'Weapon' && cat !== 'Prefix' && cat !== 'Rarity') return false;
            return isSecEle(p);
          });
        }
        rawOpts = sec.sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
      }
    }

    // Keep "Legendary ID" / Rarity slot aligned with the selected left-side rarity tier.
    if (schemaItem.partType === 'Rarity' && rarityTierFilterActiveForCurrentContext()){
      const selTier = getSelectedRarityTier();
      if (Number.isFinite(selTier)){
        const rr = getRarityRowsForCurrentContext()
          .filter(r => rarityTierFromItemTypeString(r && r.itemTypeString, r) === selTier);
        const pairSet = stxRarityPairSetFromRows(rr);
        rawOpts = rawOpts.filter(p => {
          try{
            const wtLo = String((state && state.weaponType) || '').trim().toLowerCase();
            const heavyCtx = (wtLo === 'heavy weapon' || wtLo === 'heavy' || stxSimpleBuilderItemTypeIsHeavyUi(state && state.itemType));
            if (heavyCtx){
              const cN = String(normCode(p && p.code || '') || '').toLowerCase();
              if (stxIsDatasetGrenadeGadgetSpawnCode(cN) || cN.includes('grenade_gadget')) return false;
              if (String((p && p.category) || '').trim() === 'Grenade') return false;
              if (String((p && p.itemType) || '').trim() === 'Grenade') return false;
            }
          }catch(_e){}
          if (pairSet.size) return stxPartMatchesRarityPairSet(p, pairSet);
          const famSet = new Set(rr.map(r => Number(r && r.familyId)).filter(n => Number.isFinite(n)));
          const itemSet = new Set(rr.map(r => Number(r && r.itemId)).filter(n => Number.isFinite(n)));
          const pf = partFamilyIdOf(p);
          const pi = partItemIdOf(p);
          const famOk = !famSet.size || famSet.has(pf);
          const itemOk = !itemSet.size || itemSet.has(pi);
          return famOk && itemOk;
        });

        // Weapon pearlescent override picker:
        // keep this slot strictly on pearl rarity IDs (51-60), and synthesize them if dataset rows are missing.
        if (category === 'Weapon' && Number(selTier) === 5){
          const isPearlRarityOpt = (p)=>{
            const code = String(normCode(p && p.code || '') || '').toLowerCase();
            const item = partItemIdOf(p);
            const pt = String((p && p.partType) || '').trim().toLowerCase();
            const catL = String((p && p.category) || '').trim().toLowerCase();
            const pearlCode = code.includes('pearl_') || /(?:^|[._])comp_06_pearlescent/.test(code);
            const pearlId = Number.isFinite(item) && item >= 51 && item <= 60;
            const rarityLike = (pt === 'rarity') || (catL === 'rarity');
            return pearlId || (rarityLike && pearlCode);
          };
          rawOpts = rawOpts.filter(isPearlRarityOpt);
          if (!rawOpts.length){
            const synthMan = String(state.manufacturer || '').trim();
            const synthType = String(state.weaponType || '').trim() || 'Weapon';
            rawOpts = PEARL_FALLBACK_ROWS.map(pr => ({
              category: 'Rarity',
              manufacturer: synthMan,
              itemType: synthType,
              weaponType: synthType,
              partType: 'Rarity',
              name: String(pr.legendaryName || pr.itemTypeString || `Pearlescent ${pr.itemId}`),
              code: `{1:${Number(pr.itemId)}}`,
              idRaw: `1:${Number(pr.itemId)}`,
              family: 1,
              id: Number(pr.itemId)
            }));
          }
        }
      }
    }

    // Shield slot filtering:
    // Keep options aligned to the selected family/manufacturer and enforce slot-specific
    // pools (body/246 perks/237 armor/248 energy/type1 element).
    if (category === 'Shield' && !isShieldType1ElementSlot){
      const parseFamFromRaritySel = (v)=>{
        const s = String(v || '').trim();
        if (!s || s.indexOf('|') === -1) return null;
        const fam = Number(s.split('|')[0]);
        return Number.isFinite(fam) ? fam : null;
      };
      const partFam = (p)=>{
        if (p && p.family != null && Number.isFinite(Number(p.family))) return Number(p.family);
        if (p && p.familyId != null && Number.isFinite(Number(p.familyId))) return Number(p.familyId);
        const idRaw = String((p && (p.idRaw || p.idraw)) || '').trim();
        const m = idRaw.match(/^(\d+)\s*:/);
        return m ? Number(m[1]) : null;
      };
      const selectedFam = (() => {
        const fromRarity = parseFamFromRaritySel(state.rarity || ($('rarity') && $('rarity').value) || '');
        if (fromRarity != null) return fromRarity;
        return partFam(state.mainPart || null);
      })();
      const manL = String(state.manufacturer || '').trim().toLowerCase();
      const useAllMfr = isAllPartsEnabled();
      const slotKey = String(schemaItem && schemaItem.key || '');
      const ignoreMfrForBodyLegendary = (slotKey === 'bodyLegendary' || slotKey === 'mainBody' || slotKey === 'body');
      const shieldUsesArmorBodyAcc = (() => {
        if (selectedFam === 287) return true;
        if (manL === 'tediore') return true;
        const body = state.slots && (state.slots.body || state.slots.mainBody);
        const bc = String(normCode(body && body.code || '') || '').toLowerCase();
        if (!bc) return false;
        if (bc.indexOf('ted_shield.') === 0 || bc.indexOf('armor_shield.') === 0) return true;
        if (bc.includes('part_body_armor')) return true;
        return false;
      })();

      rawOpts = rawOpts.filter((p)=>{
        const pm = String((p && p.manufacturer) || '').trim().toLowerCase();
        const pf = partFam(p);
        const isGenericMan = (pm === '' || pm === 'gadgets' || pm === 'generic' || pm === 'all' || pm === 'universal');
        if (!useAllMfr && !ignoreMfrForBodyLegendary && manL && pm && !isGenericMan && pm !== manL) return false;
        if (pf == null) return false;

        const pt = String((p && p.partType) || '').trim().toLowerCase();
        const codeRawLo = String((p && p.code) || '').trim().toLowerCase();
        const codeNorm = String(normCode(p.code || '') || '').toLowerCase();
        const nmLo = String((p && p.name) || '').toLowerCase();
        const isRarityPart = (pt === 'rarity') || /(^|[._])(comp_0[1-5]_|pearl_)/.test(codeRawLo) || codeRawLo.includes('.comp_');
        const isFirmware = (pt === 'firmware');
        const isExplicitPerk = (pt === 'perk');
        const isUntypedShieldPartRow = (pt === '' && /^shield\.part_|^armor_shield\./i.test(codeNorm));
        const is246Perkish = isExplicitPerk || isUntypedShieldPartRow;
        const isBaseElementResist246 = /^shield\.part_(corrosive|cryo|fire|radiation|shock)$/i.test(codeNorm);
        const isPearlElem = /part_pearl_elem|pearl_elem|pearlescent.*elem/i.test(codeNorm)
          || (/\bpearl\b/i.test(nmLo) && /\b(elem|element)\b/i.test(nmLo));
        const isPearlStatish = !isPearlElem && (
          /part_pearl/i.test(codeNorm) || /\bpearlescent\b/i.test(codeNorm) || /\bpearl\b/i.test(nmLo)
          || /\bpearl\b/i.test(String((p && p.effects) || '').toLowerCase())
        );
        const isPerk = isExplicitPerk;

        if (slotKey === 'mainBody' || slotKey === 'body'){
          if (pf === 246 || pf === 237 || pf === 248) return false;
          if (isRarityPart || isPerk || isFirmware) return false;
          if (Number.isFinite(selectedFam) && pf !== selectedFam) return false;
          return stxIsShieldBodyPoolRowCode(codeNorm);
        }

        if (slotKey === 'bodyLegendary'){
          if (!Number.isFinite(pf)) return false;
          if (pf === 246 || pf === 237 || pf === 248) return false;
          if (isRarityPart || isPerk || isFirmware) return false;
          if (Number.isFinite(selectedFam) && pf !== selectedFam) return false;
          return stxIsShieldUniquePoolRowCode(codeNorm);
        }

        if (slotKey === 'resistance'){
          if (pf !== 246) return false;
          if (isRarityPart || isFirmware) return false;
          if (isExplicitPerk) return false;
          if (isUntypedShieldPartRow && !isBaseElementResist246) return false;
          return true;
        }

        if (slotKey === 'primary246'){
          if (pf !== 246) return false;
          if (!is246Perkish) return false;
          if (isPearlElem || isPearlStatish) return false;
          return codeNorm.includes('_primary');
        }

        if (slotKey === 'secondary246'){
          if (pf !== 246) return false;
          if (!is246Perkish) return false;
          if (isPearlElem || isPearlStatish) return false;
          // Secondary bucket also catches generic perk rows that are not explicitly marked primary.
          return !codeNorm.includes('_primary');
        }

        if (slotKey === 'pearlElem246'){
          if (pf !== 246) return false;
          if (!is246Perkish) return false;
          return isPearlElem;
        }

        if (slotKey === 'pearlStat246'){
          if (pf !== 246) return false;
          if (!is246Perkish) return false;
          return isPearlStatish && !isPearlElem;
        }
        if (slotKey === 'armor237') return pf === 237 && /^armor_shield\./i.test(codeNorm);
        if (slotKey === 'energy248') return pf === 248 && /^energy_shield\./i.test(codeNorm);
        if (slotKey === 'firmware246') return pf === 246 && isFirmware;

        if (!useAllMfr && Number.isFinite(selectedFam)){
          if (pf === selectedFam) return true;
          if (pf === 237 || pf === 246 || pf === 248) return true;
          return false;
        }
        return true;
      });

      if ((schemaItem.key === 'body' || schemaItem.key === 'mainBody') && rawOpts && rawOpts.length) {
        const pinnedShield = stxShieldRarityPinnedBodyCode(rawOpts, state.mainPart, state.manufacturer);
        rawOpts = rawOpts.slice().sort((a, b)=>{
          const ca = String(normCode(a && a.code || '') || '').toLowerCase();
          const cb = String(normCode(b && b.code || '') || '').toLowerCase();
          const ra = pinnedShield && ca === pinnedShield ? 0 : 1;
          const rb = pinnedShield && cb === pinnedShield ? 0 : 1;
          if (ra !== rb) return ra - rb;
          return displayForPart(a).localeCompare(displayForPart(b), undefined, { numeric: true, sensitivity: 'base' });
        });
      }

      const slotKeyShieldExtras = String(schemaItem && schemaItem.key || '');
      if (slotKeyShieldExtras === 'pearlElem246'){
        const inject = getAllParts().filter(p=>{
          if (!p) return false;
          const pf = partFamilyIdOf(p);
          const pi = partItemIdOf(p);
          const c = String(normCode(p && p.code || '') || '').toLowerCase();
          return pf === 1 && Number.isFinite(pi) && pi >= 55 && pi <= 60 && /weapon\.part_override_/.test(c);
        });
        rawOpts = rawOpts.concat(inject);
      } else if (slotKeyShieldExtras === 'pearlStat246'){
        const inject = getAllParts().filter(p=>{
          if (!p) return false;
          const pf = partFamilyIdOf(p);
          const pi = partItemIdOf(p);
          const c = String(normCode(p && p.code || '') || '').toLowerCase();
          return pf === 1 && Number.isFinite(pi) && pi >= 51 && pi <= 54 && /weapon\.part_pearl_/.test(c);
        });
        rawOpts = rawOpts.concat(inject);
      }
      if (slotKeyShieldExtras === 'armor237' && !rawOpts.length){
        rawOpts = getAllParts().filter(p=>{
          if (!p || String(p.category || '').trim() !== 'Shield') return false;
          if (partFamilyIdOf(p) !== 237) return false;
          const c = String(normCode(p && p.code || '') || '').toLowerCase();
          return /^armor_shield\./i.test(c);
        }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
      }
    }

    // Enhancement compatibility:
    // Build robust slot pools because Enhancement datasets often mix partType labels.
    if (category === 'Enhancement'){
      const slotKey = String(schemaItem && schemaItem.key || '').trim().toLowerCase();
      const allEnhancement = () => filterParts({
        category,
        manufacturer: state.manufacturer,
        weaponType: '',
        partType: undefined
      });
      const allEnhancementAnyManufacturer = () => filterParts({
        category,
        manufacturer: '',
        weaponType: '',
        partType: undefined
      });
      const sortParts = (arr)=>arr.sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
      const isRarityish = (p)=>{
        const pt = String((p && p.partType) || '').trim().toLowerCase();
        const code = String((p && p.code) || '').trim().toLowerCase();
        return (
          pt === 'rarity' ||
          pt === 'secondary rarity' ||
          pt === 'rarity components' ||
          /(^|[._])(comp_0[1-5]_|pearl_)/.test(code) ||
          code.includes('.comp_') ||
          code.includes('enhancement.comp_')
        );
      };
      const isCoreLike = (p)=>{
        const pt = String((p && p.partType) || '').trim().toLowerCase();
        const code = String((p && p.code) || '').trim().toLowerCase();
        return pt === 'core' || code.includes('part_core_') || code.includes('.part_core_');
      };
      const isStatsLike = (p)=>{
        const pt = String((p && p.partType) || '').trim().toLowerCase();
        const code = String((p && p.code) || '').trim().toLowerCase();
        return pt === 'stats' || pt === 'stat' || /^stats?\s*[23]$/.test(pt) || code.includes('part_stat');
      };
      const isFirmwareLike = (p)=>{
        const pt = String((p && p.partType) || '').trim().toLowerCase();
        const code = String((p && p.code) || '').trim().toLowerCase();
        return pt === 'firmware' || code.includes('part_firmware');
      };
      const isElementLike = (p)=>{
        const pt = String((p && p.partType) || '').trim().toLowerCase();
        const code = String((p && p.code) || '').trim().toLowerCase();
        return (
          pt === 'status' ||
          pt === 'element' ||
          pt === 'elemental' ||
          /(?:^|[._])part_ele(?:[._]|$)/.test(code) ||
          /(?:^|[._])part_(fire|cryo|shock|corrosive|radiation)(?:[._]|$)/.test(code) ||
          /(?:^|[._])(element|ele)(?:[._]|$)/.test(code)
        );
      };
      /** Manufacturer core row (`part_core_*`, partType Core / augment) — NCS “core_augment” lane. */
      const isEnhancementCoreAugmentPool = (p)=>{
        if (isRarityish(p)) return false;
        if (isFirmwareLike(p) || isStatsLike(p) || isElementLike(p)) return false;
        const pt = String((p && p.partType) || '').trim().toLowerCase();
        const code = String(normCode(p && p.code || '') || '').toLowerCase();
        if (pt === 'core') return true;
        if (code.includes('part_core_') || code.includes('.part_core_')) return true;
        if (code.includes('core_augment')) return true;
        if (pt === 'augment' && (code.includes('part_core') || code.includes('core_augment'))) return true;
        return false;
      };
      /** Supplemental legendary rows. Enhancement's selectable legendary-effect slot itself uses the core_augment pool. */
      const isEnhancementLegendaryPerkPool = (p)=>{
        if (isRarityish(p)) return false;
        if (isEnhancementCoreAugmentPool(p)) return false;
        if (isFirmwareLike(p) || isStatsLike(p) || isElementLike(p)) return false;
        const pt = String((p && p.partType) || '').trim().toLowerCase();
        const code = String(normCode(p && p.code || '') || '').toLowerCase();
        const nm = String((p && (p.name || p.legendaryName)) || '').toLowerCase();
        if (pt === 'legendary perks' || pt === 'legendary perk') return true;
        if (pt === 'legendary') return true;
        if (code.includes('unique_core')) return true;
        if ((code.includes('legendary') || nm.includes('legendary')) && !code.includes('part_core_')) return true;
        return false;
      };
      const isBodyLike = (p)=>{
        const pt = String((p && p.partType) || '').trim().toLowerCase();
        const code = String((p && p.code) || '').trim().toLowerCase();
        if (pt === 'body' || pt === 'main body') return true;
        return code.includes('part_body_') || code.includes('.part_body_');
      };
      const isSpecialLike = (p)=>{
        const pt = String((p && p.partType) || '').trim().toLowerCase();
        const code = String((p && p.code) || '').trim().toLowerCase();
        if (isRarityish(p) || isCoreLike(p) || isStatsLike(p) || isFirmwareLike(p) || isEnhancementLegendaryPerkPool(p) || isEnhancementCoreAugmentPool(p) || isElementLike(p) || isBodyLike(p)) return false;
        if (pt === 'special' || pt === 'unique' || pt === '') return true;
        if (code.includes('part_unique') || code.includes('.part_unique_') || code.includes('unique_')) return true;
        return false;
      };

      if (slotKey === 'rarity'){
        rawOpts = sortParts(allEnhancement().filter((p)=>isRarityish(p)));
      } else if (slotKey === 'stats'){
        rawOpts = sortParts(allEnhancementAnyManufacturer().filter((p)=>isStatsLike(p) && !isRarityish(p)));
      } else if (slotKey === 'core'){
        rawOpts = sortParts(allEnhancementAnyManufacturer().filter((p)=>isEnhancementCoreAugmentPool(p)));
        rawOpts = rawOpts.filter((p)=>{
          const pt = String((p && p.partType) || '').trim().toLowerCase();
          if (pt === 'rarity') return false;
          const c = String(normCode(p && p.code || '') || '').toLowerCase();
          if (/(?:^|[._])comp_0[1-6]_/.test(c) || /pearl_/.test(c) || /\.comp_/.test(c)) return false;
          return true;
        });
        /* Prefer cores for the selected manufacturer, but never empty the list. */
        if (state.manufacturer) {
          const manLo = String(state.manufacturer || '').trim().toLowerCase();
          const scoped = rawOpts.filter((p) => stxEnhancementGadgetRowMatchesSelectedManufacturer(
            String(normCode(p && p.code || '') || '').toLowerCase(), manLo
          ));
          if (scoped.length) rawOpts = scoped;
        }
      } else if (slotKey === 'special'){
        rawOpts = sortParts(allEnhancementAnyManufacturer().filter((p)=>isSpecialLike(p)));
        const legGadgetEn = filterParts({
          category:'Gadget',
          manufacturer:'',
          weaponType:'',
          partType: undefined
        }).filter(p => {
          const pt = String(p.partType || '').trim().toLowerCase();
          const c = String(normCode(p.code || '') || '').toLowerCase();
          if (stxIsDatasetGrenadeGadgetSpawnCode(c)) return false;
          return pt === 'legendary perks' || pt === 'legendary perk' || pt === 'legendary';
        });
        rawOpts = sortParts(rawOpts.concat(legGadgetEn));
      } else if (slotKey === 'firmware'){
        /* Shared firmware chips (247/234/246) + Enhancement.part_firmware_* rows. */
        const sharedFw = stxSimpleCollectFirmwareParts();
        const enhFw = allEnhancementAnyManufacturer().filter((p)=>isFirmwareLike(p) && !isRarityish(p));
        rawOpts = sortParts(mergeUniquePartOpts(sharedFw, enhFw));
      } else if (slotKey === 'element'){
        rawOpts = sortParts(allEnhancementAnyManufacturer().filter((p)=>isElementLike(p) && !isRarityish(p)));
        if (!rawOpts.length){
          // Enhancement datasets often omit dedicated element rows; keep slot usable.
          rawOpts = ELEMENTS
            .filter(e => e && e.key !== 'None' && e.code)
            .map(e => {
              const m = String(e.code || '').match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
              const fam = m ? Number(m[1]) : null;
              const id = m ? Number(m[2]) : null;
              return {
                category: 'Enhancement',
                manufacturer: state.manufacturer || '',
                partType: 'Status',
                name: e.label,
                code: String(e.code || '').trim(),
                idRaw: (Number.isFinite(fam) && Number.isFinite(id)) ? `${fam}:${id}` : '',
                family: Number.isFinite(fam) ? fam : null,
                id: Number.isFinite(id) ? id : null
              };
            });
        }
      }
    }

    // Repkit: rows with an empty `partType` mix placeholders, augment-style perks, etc.
    // Split them across dedicated slots so one dropdown is not an unusably long mix.
    if (category === 'Repkit'){
      const slotKey = String(schemaItem && schemaItem.key || '').trim();
      if (slotKey === 'perkResist' || slotKey === 'perkImmunity' || slotKey === 'perkNova' || slotKey === 'perkSplat'){
        const codeL = (p)=> String(normCode(p && p.code) || '').toLowerCase();
        rawOpts = rawOpts.filter((p)=>{
          const c = codeL(p);
          const isAug = /repair_kit\.part_aug_/.test(c);
          if (slotKey === 'perkResist') return isAug && /resist/.test(c);
          if (slotKey === 'perkImmunity') return isAug && /immunity/.test(c);
          if (slotKey === 'perkNova') return isAug && /nova/.test(c);
          if (slotKey === 'perkSplat') return isAug && /splat/.test(c);
          return true;
        }).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
      }
    }
    // Element slots should not render totally empty if the dataset failed to load matching rows.
    if (!rawOpts.length && schemaItem && schemaItem.key === 'element' && category === 'Repkit'){
      rawOpts = REPKIT_ELEMENT_SYNTH.map(e => ({
        category: 'Repkit',
        manufacturer: 'gadgets',
        itemType: 'Repkit',
        partType: 'Element',
        name: e.label,
        code: `"${e.spawnCode}"`,
        spawnCode: e.spawnCode,
        idRaw: e.idRaw,
        family: 243,
        id: e.id
      }));
    } else if (!rawOpts.length && schemaItem && schemaItem.key === 'element' && category === 'Grenade'){
      rawOpts = ELEMENTS
        .filter(e => e && e.key !== 'None' && e.code)
        .map(e => {
          const m = String(e.code || '').match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
          const fam = m ? Number(m[1]) : null;
          const id = m ? Number(m[2]) : null;
          return {
            category: String(category || ''),
            manufacturer: state.manufacturer || '',
            partType: 'Element',
            name: e.label,
            code: String(e.code || '').trim(),
            idRaw: (Number.isFinite(fam) && Number.isFinite(id)) ? `${fam}:${id}` : '',
            family: Number.isFinite(fam) ? fam : null,
            id: Number.isFinite(id) ? id : null
          };
        });
    }
    // Dataset can contain duplicate rows for the same logical part.
    // Dedupe by normalized TypeID:ItemID (not raw idRaw vs bare id strings).
    rawOpts.sort((a,b)=>{
      const rd = stxPartDropdownRichnessScore(b) - stxPartDropdownRichnessScore(a);
      if (rd) return rd;
      return displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'});
    });
    const seenOptKeys = new Set();
    let opts = rawOpts.filter((p)=>{
      const lk = stxSelectLogicalDedupeKey(p);
      const key = lk || stxStableDropdownDedupeKey(p);
      if (!key) return true;
      if (seenOptKeys.has(key)) return false;
      seenOptKeys.add(key);
      return true;
    });
    if (category === 'Repkit' && schemaItem && schemaItem.key === 'body'){
      const byCode = new Map();
      const rank = (row)=>{
        let s = 0;
        if (String(row.category || '').trim() === 'Repkit') s += 4;
        if (String(row.idRaw || '').includes(':')) s += 2;
        if (stxResolvePartIconUrl(row, schemaItem, category)) s += 1;
        return s;
      };
      for (const p of opts){
        const c = String(normCode(p.code || '') || '').toLowerCase();
        const prev = byCode.get(c);
        if (!prev || rank(p) > rank(prev)) byCode.set(c, p);
      }
      opts = Array.from(byCode.values()).sort((a,b)=>displayForPart(a).localeCompare(displayForPart(b), undefined, {numeric:true, sensitivity:'base'}));
    }

    /* Hide optional near-duplicate slots (Repkit Variant, Shield Unique) when the pool is empty. */
    if (schemaItem && schemaItem.hideWhenEmpty && !opts.length) {
      const curKeep = state.slots && state.slots[schemaItem.key];
      const hasCur = schemaItem.multi
        ? (Array.isArray(curKeep) && curKeep.length > 0)
        : !!curKeep;
      if (!hasCur) return null;
    }

    const picked = document.createElement('div');
    picked.className = 'picked';

    function renderPicked(){
      if (!showInlinePicked) return;
      const cur = state.slots[schemaItem.key];
      const arr = Array.isArray(cur) ? cur : (cur ? [cur] : []);
      picked.innerHTML = arr.length
        ? `<div>${arr.map(p=>`* ${escapeHtml(displayForPart(p))}<br><code>${escapeHtml(tokenForPart(p))}</code>`).join('<br>')}</div>`
        : `<div class="muted small">Nothing selected.</div>`;
    }

    // Tickbox selectors (searchable) for large pools.
    const useTickPicker = (
      ((category === 'Class Mod') && (
        schemaItem.partType === 'Name+Skin' ||
        schemaItem.partType === 'Rarity' ||
        schemaItem.partType === 'Skill' ||
        schemaItem.partType === 'Universal' ||
        schemaItem.partType === 'Secondary' ||
        schemaItem.partType === 'Firmware' ||
        schemaItem.partType === 'Perk' ||
        schemaItem.customType === 'enhancementGunStats'
      )) ||
      ((category === 'Weapon') && schemaItem.customType === 'weaponAdditionalParts') ||
      (schemaItem.customType === 'otherParts' && category !== 'Class Mod') ||
      ((category === 'Enhancement') && (
        schemaItem.key === 'stats' ||
        schemaItem.key === 'core' ||
        schemaItem.key === 'firmware'
      ))
    );
    const showInlinePicked = !(category === 'Class Mod' && useTickPicker);

    slot.appendChild(top);
    if ((category === 'Weapon' || category === 'Gadget') && schemaItem.key === 'underbarrel') {
      const ubHint = document.createElement('div');
      ubHint.className = 'muted small';
      ubHint.style.margin = '-4px 0 8px';
      ubHint.style.lineHeight = '1.4';
      ubHint.textContent = STX_UNDERBARREL_SLOT_HINT;
      slot.appendChild(ubHint);
    } else if (category === 'Class Mod' && schemaItem.customType === 'enhancementGunStats') {
      const egHint = document.createElement('div');
      egHint.className = 'muted small';
      egHint.style.margin = '-4px 0 8px';
      egHint.style.lineHeight = '1.4';
      egHint.textContent = 'Enhancement Stat / Stat2 rows only (no firmware or cores). Modded cross-stuff for classmods.';
      slot.appendChild(egHint);
    } else if ((category === 'Weapon' || category === 'Gadget') && schemaItem.key === 'underbarrelAccVis') {
      const ubvHint = document.createElement('div');
      ubvHint.className = 'muted small';
      ubvHint.style.margin = '-4px 0 8px';
      ubvHint.style.lineHeight = '1.4';
      ubvHint.textContent = STX_UNDERBARREL_VISUAL_HINT;
      slot.appendChild(ubvHint);
    }

    if (useTickPicker){
      const wrap = document.createElement('div');
      wrap.style.marginTop = '6px';

      const search = document.createElement('input');
      search.type = 'text';
      search.id = 'stx-tick-search-' + (schemaItem.key || 'filter');
      search.name = search.id;
      search.setAttribute('aria-label', 'Filter parts');
      search.placeholder = 'Filter...';
      search.style.width = '100%';
      search.style.padding = '10px';
      search.style.borderRadius = '10px';
      search.style.border = '1px solid rgba(255,255,255,0.14)';
      search.style.background = '#0b0f18';
      search.style.color = '#d8ffff';
      search.style.marginBottom = '8px';

      const cmPerkPoolAddAll = (
        category === 'Class Mod' &&
        schemaItem.multi &&
        (schemaItem.partType === 'Skill' ||
          schemaItem.partType === 'Secondary' ||
          schemaItem.partType === 'Universal' ||
          schemaItem.partType === 'Perk' ||
          schemaItem.customType === 'enhancementGunStats')
      );

      const list = document.createElement('div');
      list.style.maxHeight = '168px';
      list.style.overflow = 'auto';
      list.style.border = '1px solid rgba(255,255,255,0.10)';
      list.style.borderRadius = '8px';
      list.style.padding = '3px';
      list.style.background = 'rgba(0,0,0,0.18)';

      const tickHoverPreview = document.createElement('div');
      tickHoverPreview.className = 'stx-part-preview small stx-tick-hover-preview';
      tickHoverPreview.setAttribute('role', 'status');
      tickHoverPreview.innerHTML = '<span class="muted">Hover a part to see token, IDs, spawn code, and stats.</span>';

      function tickRowTooltip(part){
        if (category === 'Enhancement' && schemaItem.key === 'core'){
          const core = stxEnhancementCoreEffectText(part);
          if (core) return core;
        }
        if (typeof window.partTooltipText === 'function'){
          try { return String(window.partTooltipText(part) || '').trim(); } catch (_e) {}
        }
        return '';
      }

      const perRowTickMultiQty = !!(schemaItem.multi && (
        schemaItem.customType === 'weaponAdditionalParts' ||
        schemaItem.customType === 'otherParts' ||
        (category === 'Enhancement' && ['stats','core'].includes(String(schemaItem.key || '')))
      ));
      const tickQtyInput = (schemaItem.multi && !perRowTickMultiQty) ? document.createElement('input') : null;
      if (tickQtyInput){
        tickQtyInput.type = 'number';
        tickQtyInput.id = 'stx-tick-qty-' + (schemaItem.key || 'multi');
        tickQtyInput.name = tickQtyInput.id;
        tickQtyInput.min = '1';
        tickQtyInput.step = '1';
        tickQtyInput.value = '1';
        tickQtyInput.inputMode = 'numeric';
        tickQtyInput.setAttribute('aria-label', 'Copies to add or remove when toggling a checkbox');
        tickQtyInput.style.width = '44px';
        tickQtyInput.style.padding = '3px 5px';
        tickQtyInput.style.borderRadius = '6px';
        tickQtyInput.style.border = '1px solid rgba(255,255,255,0.16)';
        tickQtyInput.style.background = '#0b0f18';
        tickQtyInput.style.color = '#d8ffff';
        tickQtyInput.style.fontWeight = '700';
        tickQtyInput.style.fontSize = '11px';
      }

      function isSelected(part){
        const cur = state.slots[schemaItem.key];
        const tok = tokenForPart(part);
        if (schemaItem.multi){
          const arr = Array.isArray(cur) ? cur : [];
          return arr.some(x => tokenForPart(x) === tok);
        }
        return cur && tokenForPart(cur) === tok;
      }

      function setSelected(part, checked, qtyOverride){
        if (schemaItem.multi){
          const cur = state.slots[schemaItem.key];
          const arr = Array.isArray(cur) ? cur.slice() : [];
          const tok = tokenForPart(part);
          const fromGlobal = tickQtyInput && tickQtyInput.value;
          const n = Math.max(1, Number(qtyOverride != null ? qtyOverride : fromGlobal || 1) || 1);
          if (checked){
            const orders = stxNextImportOrders(arr, n);
            for (let i = 0; i < n; i++) arr.push(stxClonePartWithImportOrder(part, orders[i]));
          } else {
            let rem = n;
            for (let i = arr.length - 1; i >= 0 && rem > 0; i--){
              if (tokenForPart(arr[i]) === tok){
                arr.splice(i, 1);
                rem--;
              }
            }
          }
          state.slots[schemaItem.key] = arr;
        } else {
          state.slots[schemaItem.key] = checked ? part : null;
          if (!checked) delete state.slots[schemaItem.key];
        }
      }

      function renderList(){
        const q = String(search.value || '').trim().toLowerCase();
        let listSrc = opts;
        if (q){
          listSrc = opts.filter(p=>{
            const label = String(displayForPart(p) || '').toLowerCase();
            const code  = String(p && p.code ? p.code : '').toLowerCase();
            return label.includes(q) || code.includes(q);
          });
        } else {
          listSrc = opts.slice(0, 500);
        }

        list.innerHTML = '';
        if (!listSrc.length){
          const empty = document.createElement('div');
          empty.className = 'muted small';
          empty.style.padding = '8px';
          empty.textContent = 'No matches.';
          list.appendChild(empty);
          return;
        }

        const groupName = `tick_${schemaItem.key}_${Math.random().toString(16).slice(2)}`;

        listSrc.forEach((part, idx) => {
          const row = document.createElement('label');
          row.className = 'stx-tick-row';
          row.style.display = 'flex';
          row.style.gap = '6px';
          row.style.alignItems = 'center';
          row.style.padding = '2px 4px';
          row.style.borderRadius = '5px';
          row.style.cursor = 'pointer';
          row.style.userSelect = 'none';
          row.style.pointerEvents = 'auto';
          row.style.fontSize = '12px';
          row.style.lineHeight = '1.25';

          const input = document.createElement('input');
          input.type = schemaItem.multi ? 'checkbox' : 'radio';
          input.id = 'tick-' + (schemaItem.key || 'part') + '-' + idx;
          input.name = schemaItem.multi ? input.id : groupName;
          input.style.margin = '0';
          input.style.width = '14px';
          input.style.height = '14px';
          input.checked = isSelected(part);
          input.style.pointerEvents = 'auto';

          const text = document.createElement('div');
          text.style.flex = '1';
          text.style.minWidth = '0';
          const line1 = document.createElement('div');
          line1.textContent = displayForPart(part);
          line1.style.overflow = 'hidden';
          line1.style.textOverflow = 'ellipsis';
          line1.style.whiteSpace = 'nowrap';
          const line2 = document.createElement('div');
          line2.className = 'muted small';
          line2.textContent = tokenForPart(part);
          line2.style.overflow = 'hidden';
          line2.style.textOverflow = 'ellipsis';
          line2.style.whiteSpace = 'nowrap';
          text.appendChild(line1);
          text.appendChild(line2);
          try {
            const effDesc = (typeof window.partEffectDescForDropdown === 'function')
              ? String(window.partEffectDescForDropdown(part) || '').trim()
              : '';
            if (effDesc) {
              const line3 = document.createElement('div');
              line3.className = 'small';
              line3.style.cssText = 'color:rgba(0,243,255,0.82);margin-top:2px;line-height:1.3;';
              line3.textContent = effDesc.length > 180 ? effDesc.slice(0, 177) + '…' : effDesc;
              text.appendChild(line3);
            }
            const redLine = (typeof window.partRedTextForDropdown === 'function')
              ? String(window.partRedTextForDropdown(part) || '').trim()
              : '';
            if (redLine) {
              const line4 = document.createElement('div');
              line4.className = 'small';
              line4.style.cssText = 'color:#ff7b7b;margin-top:2px;line-height:1.3;font-style:italic;';
              line4.textContent = '"' + (redLine.length > 160 ? redLine.slice(0, 157) + '…' : redLine) + '"';
              text.appendChild(line4);
            }
          } catch (_e) {}

          let rowQty = null;
          if (perRowTickMultiQty){
            rowQty = document.createElement('input');
            rowQty.type = 'number';
            rowQty.className = 'stx-tick-qty-row';
            rowQty.min = '1';
            rowQty.step = '1';
            rowQty.value = '1';
            rowQty.inputMode = 'numeric';
            const tokSafe = String(schemaItem.key || 'ap') + '-' + String(tokenForPart(part) || idx).replace(/[^a-z0-9_-]/gi, '_').slice(0, 48);
            rowQty.id = 'stx-tick-qty-row-' + tokSafe;
            rowQty.name = rowQty.id;
            rowQty.setAttribute('aria-label', 'Copies for this part (uncheck removes up to this many)');
            rowQty.title = 'Copies to add; uncheck removes up to this many';
            rowQty.style.width = '52px';
            rowQty.style.flexShrink = '0';
            rowQty.style.padding = '6px 8px';
            rowQty.style.borderRadius = '8px';
            rowQty.style.border = '1px solid rgba(255,255,255,0.16)';
            rowQty.style.background = '#0b0f18';
            rowQty.style.color = '#d8ffff';
            rowQty.addEventListener('click', (e)=>{ e.stopPropagation(); });
            const curForQty = state.slots[schemaItem.key];
            const arrForQty = Array.isArray(curForQty) ? curForQty : [];
            const tokForQty = tokenForPart(part);
            const stackCnt = arrForQty.filter(x => tokenForPart(x) === tokForQty).length;
            rowQty.value = String(stackCnt > 0 ? stackCnt : 1);
            rowQty.addEventListener('change', ()=>{
              if (!schemaItem.multi || !perRowTickMultiQty) return;
              if (!input.checked) return;
              const want = Math.max(1, Number(rowQty.value) || 1);
              const cur = state.slots[schemaItem.key];
              const arr = Array.isArray(cur) ? cur.slice() : [];
              const tok = tokenForPart(part);
              const cnt = arr.filter(x => tokenForPart(x) === tok).length;
              if (want === cnt) return;
              clearImportedOutputLock();
              if (want > cnt){
                const orders = stxNextImportOrders(arr, want - cnt);
                for (let i = 0; i < want - cnt; i++) arr.push(stxClonePartWithImportOrder(part, orders[i]));
              } else {
                let rem = cnt - want;
                for (let i = arr.length - 1; i >= 0 && rem > 0; i--){
                  if (tokenForPart(arr[i]) === tok){
                    arr.splice(i, 1);
                    rem--;
                  }
                }
              }
              state.slots[schemaItem.key] = arr;
              renderPicked();
              refreshOutputs();
            });
          }

          input.addEventListener('change', ()=>{
            clearImportedOutputLock();
            if (!schemaItem.multi){
              // Clear previous selection
              setSelected(part, true);
              // Ensure only one selected: rerender the list to update other radios
              renderPicked();
              refreshOutputs();
              renderList();
              return;
            }
            const qRow = perRowTickMultiQty && rowQty
              ? Math.max(1, Number(rowQty.value) || 1)
              : undefined;
            setSelected(part, input.checked, qRow);
            renderPicked();
            refreshOutputs();
          });

          const tip = tickRowTooltip(part);
          if (tip) row.title = tip;
          row.addEventListener('mouseenter', ()=>{
            tickHoverPreview.innerHTML = formatPartPreviewHtml(part);
          });

          row.appendChild(input);
          if (rowQty) row.appendChild(rowQty);
          try { stxAttachTickRowPartIcon(row, part, schemaItem, category); } catch (_e) {}
          row.appendChild(text);
          list.appendChild(row);
        });
      }

      search.addEventListener('input', ()=>window.requestAnimationFrame(renderList));

      wrap.appendChild(search);

      if (tickQtyInput){
        const qtyRow = document.createElement('div');
        qtyRow.style.display = 'flex';
        qtyRow.style.alignItems = 'center';
        qtyRow.style.flexWrap = 'wrap';
        qtyRow.style.gap = '8px';
        qtyRow.style.marginBottom = '8px';
        const ql = document.createElement('span');
        ql.className = 'small muted';
        ql.textContent = 'Per checkbox:';
        qtyRow.appendChild(ql);
        qtyRow.appendChild(tickQtyInput);
        const qh = document.createElement('span');
        qh.className = 'small muted';
        qh.textContent = 'copies (uncheck removes up to that many)';
        qtyRow.appendChild(qh);
        wrap.appendChild(qtyRow);
      } else if (perRowTickMultiQty){
        const hint = document.createElement('div');
        hint.className = 'small muted';
        hint.style.marginBottom = '8px';
        hint.textContent = 'Each row: set copies beside the checkbox (uncheck removes up to that many).';
        wrap.appendChild(hint);
      }

      if (cmPerkPoolAddAll){
        const btnRow = document.createElement('div');
        btnRow.style.display = 'flex';
        btnRow.style.flexWrap = 'wrap';
        btnRow.style.gap = '8px';
        btnRow.style.marginBottom = '8px';
        const btnAll = document.createElement('button');
        btnAll.type = 'button';
        btnAll.textContent = 'Add all';
        btnAll.className = 'primary';
        btnAll.style.padding = '7px 12px';
        btnAll.setAttribute('aria-label', `Add all ${schemaItem.label || 'parts'} from this list`);
        btnAll.addEventListener('click', ()=>{
          clearImportedOutputLock();
          const arr = [];
          const seen = new Set();
          for (const p of opts){
            const tok = tokenForPart(p);
            if (!tok || seen.has(tok)) continue;
            seen.add(tok);
            arr.push(p);
          }
          state.slots[schemaItem.key] = arr;
          renderPicked();
          refreshOutputs();
          renderList();
        });
        btnRow.appendChild(btnAll);
        wrap.appendChild(btnRow);
      }

      wrap.appendChild(list);
      wrap.appendChild(tickHoverPreview);
      slot.appendChild(wrap);

      renderList();
      if (showInlinePicked){
        renderPicked();
        slot.appendChild(picked);
      }
      return slot;
    }

    // Default dropdown-based selector for all other categories/slots.
    const sel = document.createElement('select');
    sel.id = 'stx-sel-' + (schemaItem.key || category || 'part');
    sel.name = sel.id;
    sel.setAttribute('aria-label', schemaItem.label || schemaItem.key || 'Select part');
    const useQtyAddSlot =
      (category === 'Shield') ||
      (category === 'Enhancement' && schemaItem.key === 'firmware');
    const partByOptionKey = new Map();
    for (let i=0; i<opts.length; i++){
      const p = opts[i];
      const key = (p && p.__idx != null && Number.isFinite(Number(p.__idx)))
        ? `idx:${Number(p.__idx)}`
        : `local:${i}`;
      partByOptionKey.set(key, p);
      try{ p.__slotOptKey = key; }catch(_e){}
    }
    const barrelSlot = isBarrelFamilySchemaSlot(schemaItem, category);
    const raritySlot = String(schemaItem.partType || '').trim().toLowerCase() === 'rarity';
    const baseLabelPick = barrelSlot ? barrelFamilyDropdownLabelCompact : dropdownLabelCompactForPart;
    const grenadePinnedBody = (category === 'Grenade' && schemaItem.key === 'body')
      ? stxGrenadeRarityPinnedBodyCode(opts, state.mainPart, state.manufacturer)
      : '';
    const shieldPinnedBody = (category === 'Shield' && (schemaItem.key === 'body' || schemaItem.key === 'mainBody'))
      ? stxShieldRarityPinnedBodyCode(opts, state.mainPart, state.manufacturer)
      : '';
    const weaponPinnedBarrel = ((category === 'Weapon' || category === 'Heavy' || category === 'Heavy Weapon') && schemaItem.key === 'barrel')
      ? stxWeaponRarityPinnedBarrelCode(opts, state.mainPart)
      : '';
    const pinnedBodyCode = grenadePinnedBody || shieldPinnedBody || weaponPinnedBarrel;
    const getLabelPick = (p)=>{
      let line = baseLabelPick(p);
      if (pinnedBodyCode) {
        const c = String(normCode(p && p.code || '') || '').toLowerCase();
        if (c === pinnedBodyCode && String(line).indexOf('★') !== 0) line = '★ ' + line;
      }
      return line;
    };
    function simpleSlotOptionTitle(p){
      if (barrelSlot) return barrelFamilyOptionTitle(p);
      if (category === 'Enhancement' && schemaItem.key === 'core'){
        const core = stxEnhancementCoreEffectText(p);
        if (core) return core;
      }
      let tip = '';
      /* Class Mod: prefer full part tooltip (name + numeric id + spawn + stats). */
      if (category === 'Class Mod' && typeof window.partTooltipText === 'function'){
        try{
          const t = String(window.partTooltipText(p) || '').trim();
          if (t) tip = t;
        }catch(_e){}
      }
      if (!tip && typeof window.partEffectDescForDropdown === 'function'){
        try{
          const d = String(window.partEffectDescForDropdown(p) || '').trim();
          if (d) tip = d;
        }catch(_e){}
      }
      if (!tip && typeof window.partTooltipText === 'function'){
        try{
          const t = String(window.partTooltipText(p) || '').trim();
          if (t) tip = t;
        }catch(_e){}
      }
      if (!tip) tip = dropdownLabelForPart(p);
      /* Class Mod: spawn is omitted from the compact label — keep it on hover. */
      if (category === 'Class Mod'){
        try{
          const code = String(normCode(p && p.code) || '').trim();
          if (code && tip.indexOf(code) === -1) tip = tip ? (tip + ' | ' + code) : code;
        }catch(_e){}
      }
      return tip;
    }
    setSelectOptions(sel, opts, {
      placeholder: stxSimpleSlotPlaceholder(schemaItem, useQtyAddSlot),
      getLabel: getLabelPick,
      getValue: (p)=>String((p && p.__slotOptKey) ? p.__slotOptKey : ''),
      getTitle: simpleSlotOptionTitle,
      groupBy: raritySlot ? ((p) => stxRarityOptgroupLabelFromPart(p, state.manufacturer)) : null,
      appendIdRawToLabel: true,
      decorateOption: (opt, p)=>{ stxApplySlotPartOptionDecoration(opt, p, schemaItem, category); }
    });
    state.__simpleSlotDropdownSelections = state.__simpleSlotDropdownSelections || {};
    const lastDropdownKey = state.__simpleSlotDropdownSelections[schemaItem.key];
    if (lastDropdownKey && partByOptionKey.has(lastDropdownKey)) sel.value = lastDropdownKey;
    else {
      // Restore dropdown selection from current slot state after import.
      // (Without this, the slot may be populated in the output/picked list, but the <select> stays on placeholder.)
      const cur = state.slots[schemaItem.key];
      let curPart = cur;
      if (Array.isArray(cur)) {
        if (cur.length) {
          const sorted = cur.slice().sort((a,b)=>(a.__importOrder ?? 0) - (b.__importOrder ?? 0));
          curPart = sorted[sorted.length - 1];
        } else {
          curPart = null;
        }
      }
      if (curPart){
        const curTok = tokenForPart(curPart) || '';
        const curNorm = normCode(curPart.code || '') || '';
        const curIdRaw = String(curPart && (curPart.idRaw ?? curPart.idraw ?? '') || '').trim();
        for (const [k, p] of partByOptionKey.entries()){
          const pTok = tokenForPart(p) || '';
          const pNorm = normCode(p && (p.code || '')) || '';
          const pIdRaw = String(p && (p.idRaw ?? p.idraw ?? '') || '').trim();
          if (curTok && pTok && String(pTok) === String(curTok)){
            sel.value = k;
            state.__simpleSlotDropdownSelections[schemaItem.key] = k;
            break;
          }
          if ((!curTok || !pTok) && curNorm && pNorm && String(pNorm) === String(curNorm)){
            sel.value = k;
            state.__simpleSlotDropdownSelections[schemaItem.key] = k;
            break;
          }
          if (curIdRaw && pIdRaw && curIdRaw === pIdRaw){
            sel.value = k;
            state.__simpleSlotDropdownSelections[schemaItem.key] = k;
            break;
          }
        }
      }
    }
    slot.appendChild(sel);

    const partPreview = document.createElement('div');
    partPreview.className = 'stx-part-preview small';
    partPreview.setAttribute('role', 'status');
    partPreview.setAttribute('aria-live', 'polite');
    function syncPartPreview(){
      const k = sel.value;
      const p = k ? partByOptionKey.get(k) : null;
      const barrelish = !!(p && isBarrelFamilySchemaSlot(schemaItem, category));
      partPreview.classList.toggle('stx-part-preview--barrel', barrelish);
      if (!p){
        partPreview.classList.remove('stx-part-preview--barrel');
        partPreview.innerHTML = '<span class="muted">Select a part above to see token, IDs, spawn code, and stats.</span>';
        return;
      }
      partPreview.innerHTML = barrelish ? formatBarrelFamilyPartPreviewHtml(p) : formatPartPreviewHtml(p);
    }
    sel.addEventListener('change', ()=>{
      syncPartPreview();
      if (window.__ccIsHydrating) return;
      const key = sel.value;
      if (!key) return;
      const part = partByOptionKey.get(key);
      if (!part) return;
      const existing = state.slots[schemaItem.key];
      const hasExisting = Array.isArray(existing) ? existing.length > 0 : !!existing;
      const isBodySlot = schemaItem.key === 'body' || schemaItem.key === 'mainBody' || schemaItem.key === 'base' || schemaItem.key === 'core';
      const isRaritySlot = schemaItem.key === 'rarity';
      /* First pick auto-applies. Later picks wait for Add (modders stack via Add). Body/core/rarity replace on select. */
      if (hasExisting && !isBodySlot && !isRaritySlot) return;
      clearImportedOutputLock(true);
      state.slots[schemaItem.key] = part;
      try {
        sel.__ccAutoAppliedTok = (typeof tokenForPart === 'function') ? String(tokenForPart(part) || '').trim() : '';
        sel.__ccAutoAppliedAt = Date.now();
      } catch (_) {}
      state.__simpleSlotDropdownSelections = state.__simpleSlotDropdownSelections || {};
      state.__simpleSlotDropdownSelections[schemaItem.key] = key;
      renderPicked();
      refreshOutputs(true);
      try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
    });
    syncPartPreview();
    slot.appendChild(partPreview);

    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.textContent = 'Add';
    addBtn.className = 'primary';
    addBtn.style.marginTop = useQtyAddSlot ? '0' : '8px';

    let qtyInput = null;
    /* Every Add row gets a Qty so stacking 3 / another 3 is obvious. */
    qtyInput = document.createElement('input');
    qtyInput.type = 'number';
    qtyInput.id = 'stx-qty-' + (schemaItem.key || 'part');
    qtyInput.name = `qty_${schemaItem.key}`;
    qtyInput.min = '1';
    qtyInput.max = '999';
    qtyInput.step = '1';
    qtyInput.value = '1';
    qtyInput.inputMode = 'numeric';
    qtyInput.setAttribute('aria-label', 'Quantity to add');
    qtyInput.title = 'How many copies to add';
    qtyInput.style.width = '64px';
    qtyInput.style.padding = '9px 10px';
    qtyInput.style.borderRadius = '10px';
    qtyInput.style.border = '1px solid rgba(255,255,255,0.16)';
    qtyInput.style.background = '#0b0f18';
    qtyInput.style.color = '#d8ffff';
    qtyInput.style.fontWeight = '700';
    let swapPerkInput = null;
    if (isShieldBodyLegendarySlot){
      swapPerkInput = document.createElement('input');
      swapPerkInput.type = 'checkbox';
      swapPerkInput.id = 'stxSwapBodyLegendary';
      swapPerkInput.name = 'stxSwapBodyLegendary';
      swapPerkInput.checked = !!state.swapBodyLegendary;
      swapPerkInput.style.margin = '0';
      swapPerkInput.style.width = '16px';
      swapPerkInput.style.height = '16px';
      swapPerkInput.addEventListener('change', ()=>{
        clearImportedOutputLock();
        state.swapBodyLegendary = !!swapPerkInput.checked;
        if (state.swapBodyLegendary){
          const cur = state.slots.bodyLegendary;
          if (Array.isArray(cur) && cur.length > 1){
            state.slots.bodyLegendary = [cur[cur.length - 1]];
            refreshBuilder();
            return;
          }
        }
        refreshOutputs(true);
      });
    }

    addBtn.addEventListener('click', ()=>{
      /* User Add must always win over import pins / in-progress flags. */
      clearImportedOutputLock(true);
      try { window.__LOCK_IMPORTED_OUTPUT = false; window.__LAST_IMPORTED_DESERIALIZED = null; } catch (_) {}
      const key = sel.value;
      if (!key) return;
      const part = partByOptionKey.get(key);
      if (!part) return;
      const count = Math.max(1, Math.min(999, Number(qtyInput && qtyInput.value || 1) || 1));
      const isRaritySlot = schemaItem.key === 'rarity';
      /* Rarity stays single-replace. Every other Add stacks — including Select+Add of the same part. */
      const stacksOnAdd = !isRaritySlot;

      if (stacksOnAdd){
        const swapBodyLegendary = (isShieldBodyLegendarySlot && !!state.swapBodyLegendary);
        const arr = Array.isArray(state.slots[schemaItem.key])
          ? state.slots[schemaItem.key].slice()
          : (state.slots[schemaItem.key] ? [state.slots[schemaItem.key]] : []);
        if (swapBodyLegendary){
          const orders = stxNextImportOrders(arr, 1);
          state.slots[schemaItem.key] = [stxClonePartWithImportOrder(part, orders[0])];
        } else {
          try { sel.__ccAutoAppliedTok = ''; sel.__ccAutoAppliedAt = 0; } catch (_) {}
          const orders = stxNextImportOrders(arr, count);
          for (let i = 0; i < count; i++) arr.push(stxClonePartWithImportOrder(part, orders[i]));
          state.slots[schemaItem.key] = arr;
        }
      } else {
        state.slots[schemaItem.key] = part;
      }
      state.__simpleSlotDropdownSelections = state.__simpleSlotDropdownSelections || {};
      state.__simpleSlotDropdownSelections[schemaItem.key] = key;
      try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_) {}
      renderPicked();
      refreshOutputs(true);
      try {
        /* Immediate sync — do not wait solely on rAF if lock previously pinned output. */
        const codeNow = (typeof computeFullDeserializedCode === 'function') ? String(computeFullDeserializedCode() || '').trim() : '';
        if (codeNow && codeNow.indexOf('||') >= 0 && typeof writeSharedItemCode === 'function') {
          writeSharedItemCode({ deser: codeNow, source: 'simple', force: true });
        }
      } catch (_) {}
      try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
    });

    {
      const actionRow = document.createElement('div');
      actionRow.className = 'row';
      actionRow.style.marginTop = '8px';
      actionRow.style.display = 'flex';
      actionRow.style.alignItems = 'center';
      actionRow.style.gap = '8px';
      actionRow.style.flexWrap = 'wrap';
      const ql = document.createElement('span');
      ql.className = 'small';
      ql.style.color = 'rgba(200,230,255,0.85)';
      ql.textContent = 'Qty';
      actionRow.appendChild(ql);
      actionRow.appendChild(qtyInput);
      actionRow.appendChild(addBtn);
      slot.appendChild(actionRow);
      if (swapPerkInput){
        const swapRow = document.createElement('label');
        swapRow.className = 'row';
        swapRow.style.display = 'inline-flex';
        swapRow.style.marginTop = '6px';
        swapRow.style.alignItems = 'center';
        swapRow.style.gap = '4px';
        swapRow.style.cursor = 'pointer';
        swapRow.style.pointerEvents = 'auto';
        swapPerkInput.style.pointerEvents = 'auto';
        swapRow.appendChild(swapPerkInput);
        const swapText = document.createElement('span');
        swapText.textContent = '- Swap perk';
        swapText.className = 'small';
        swapText.style.fontWeight = '700';
        swapText.style.color = '#9de8ff';
        swapText.style.pointerEvents = 'auto';
        swapRow.appendChild(swapText);
        slot.appendChild(swapRow);
      }
    }
    renderPicked();
    slot.appendChild(picked);
    /* Optional specialty slots with no parts for this gun (e.g. Body Mag on non-Daedalus) — hide. */
    if ((category === 'Weapon' || category === 'Gadget') && stxWeaponSlotHideWhenEmpty(schemaItem.key) && (!opts || !opts.length)) {
      const cur = state.slots[schemaItem.key];
      const hasSel = schemaItem.multi
        ? (Array.isArray(cur) && cur.length > 0)
        : !!cur;
      if (!hasSel) {
        slot.style.display = 'none';
        slot.dataset.stxHiddenEmpty = '1';
      }
    }
    return slot;
  }

  function escapeHtml(s){
    return String(s).replace(/[&<>"']/g, (c)=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  }

  function buildElementsControl(){
    const wrap = document.createElement('div');
    wrap.className = 'slot';

    const top = document.createElement('div');
    top.className='top';
    const name = document.createElement('div');
    name.className='name';
    name.textContent = 'Elements (stackable)';

    const clearBtn = document.createElement('button');
    clearBtn.type='button';
    clearBtn.className='danger';
    clearBtn.style.padding='7px 10px';
    clearBtn.textContent='Clear';
    clearBtn.addEventListener('click', ()=>{
      state.primaryElement = 'None';
      state.elementStack = [];
      state.dualElementUseMaliwanSwitch = false;
      if (state.__simpleSlotDropdownSelections) delete state.__simpleSlotDropdownSelections.__elementStack;
      refreshBuilder();
    });

    top.appendChild(name);
    top.appendChild(clearBtn);

    const primary = document.createElement('select');
    primary.id = 'stxPrimaryElement';
    primary.name = primary.id;
    primary.setAttribute('aria-label', 'Primary element');
    setSelectOptions(primary, ELEMENTS, {
      placeholder:'Primary element...',
      getLabel: stxPresetElementDropdownLabel,
      getValue:(e)=>e.key,
      getTitle: (e) => (e && e.code) ? ('Output token: ' + String(e.code)) : '',
      decorateOption(opt, e){
        const key = String(e && e.key || '').toLowerCase();
        const lbl = String(e && e.label || '').toLowerCase();
        const fn = stxElementChipFilenameFromBlob(key + ' ' + lbl, false);
        if (fn) stxSetOptionDataCcIconFromUrl(opt, STX_CC_ELEMENT_ICON_BASE + fn);
      }
    });
    primary.value = state.primaryElement || 'None';
    primary.addEventListener('change', ()=>{
      state.primaryElement = primary.value || 'None';
      stxSyncDualElementMaliwanSwitch();
      refreshOutputs();
    });

    const row = document.createElement('div');
    row.className='row';
    row.style.marginTop='10px';

    const addSel = document.createElement('select');
    addSel.id = 'stxAddElement';
    addSel.name = addSel.id;
    addSel.setAttribute('aria-label', 'Add element to stack');
    setSelectOptions(addSel, ELEMENTS.filter(e=>e.key!=='None'), {
      placeholder:'Add element...',
      getLabel: stxPresetElementDropdownLabel,
      getValue:e=>e.key,
      getTitle: (e) => (e && e.code) ? ('Output token: ' + String(e.code)) : '',
      decorateOption(opt, e){
        const key = String(e && e.key || '').toLowerCase();
        const lbl = String(e && e.label || '').toLowerCase();
        const fn = stxElementChipFilenameFromBlob(key + ' ' + lbl, false);
        if (fn) stxSetOptionDataCcIconFromUrl(opt, STX_CC_ELEMENT_ICON_BASE + fn);
      }
    });

    const addBtn = document.createElement('button');
    addBtn.type='button';
    addBtn.className='primary';
    addBtn.textContent='Add';
    addBtn.style.flex = '1';
    addBtn.style.minWidth = '72px';

    const elemQty = document.createElement('input');
    elemQty.type = 'number';
    elemQty.id = 'stx-qty-element-stack';
    elemQty.name = 'qty_element_stack';
    elemQty.min = '1';
    elemQty.max = '999';
    elemQty.step = '1';
    elemQty.value = '1';
    elemQty.inputMode = 'numeric';
    elemQty.setAttribute('aria-label', 'Element stack quantity');
    elemQty.title = 'How many copies to stack (packs as {1:[13 13]})';
    elemQty.style.width = '64px';
    elemQty.style.padding = '9px 10px';
    elemQty.style.borderRadius = '10px';
    elemQty.style.border = '1px solid rgba(255,255,255,0.16)';
    elemQty.style.background = '#0b0f18';
    elemQty.style.color = '#d8ffff';
    elemQty.style.fontWeight = '700';

    addBtn.addEventListener('click', ()=>{
      const v = addSel.value;
      if (!v) return;
      const count = Math.max(1, Math.min(999, Number(elemQty.value || 1) || 1));
      state.__simpleSlotDropdownSelections = state.__simpleSlotDropdownSelections || {};
      state.__simpleSlotDropdownSelections.__elementStack = v;
      if (!state.primaryElement || state.primaryElement === 'None') {
        state.primaryElement = v;
        for (let i = 1; i < count; i++) state.elementStack.push(v);
      } else {
        for (let i = 0; i < count; i++) state.elementStack.push(v);
      }
      stxSyncDualElementMaliwanSwitch();
      try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_) {}
      refreshBuilder();
      try {
        refreshOutputs(true);
        if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true);
      } catch (_) {}
    });
    if (state.__simpleSlotDropdownSelections && state.__simpleSlotDropdownSelections.__elementStack) {
      const lastElementAdd = state.__simpleSlotDropdownSelections.__elementStack;
      if (Array.from(addSel.options).some(o => o.value === lastElementAdd)) addSel.value = lastElementAdd;
    }

    const qtyLbl = document.createElement('span');
    qtyLbl.className = 'small';
    qtyLbl.style.color = 'rgba(200,230,255,0.85)';
    qtyLbl.textContent = 'Qty';
    row.appendChild(addSel);
    row.appendChild(qtyLbl);
    row.appendChild(elemQty);
    row.appendChild(addBtn);

    const picked = document.createElement('div');
    picked.className='picked';
    const primaryLine = `<div><span class="muted">Primary:</span> <b>${escapeHtml(state.primaryElement || 'None')}</b></div>`;
    const stackLine = state.elementStack.length
      ? `<div style="margin-top:6px"><span class="muted">Stack:</span><br>${state.elementStack.map((e,i)=>`* ${escapeHtml(e)} <button data-idx="${i}" style="margin-left:8px;padding:2px 8px;border-radius:10px">remove</button>`).join('<br>')}</div>`
      : `<div style="margin-top:6px" class="muted small">No stacked elements yet. Add the same element again to stack it.</div>`;
    picked.innerHTML = primaryLine + stackLine;

    picked.querySelectorAll('button[data-idx]').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const i = Number(btn.getAttribute('data-idx'));
        state.elementStack.splice(i,1);
        stxSyncDualElementMaliwanSwitch();
        refreshBuilder();
      });
    });

    wrap.appendChild(top);
    wrap.appendChild(primary);
    wrap.appendChild(row);
    wrap.appendChild(picked);

    const dualWrap = document.createElement('label');
    dualWrap.style.display = 'flex';
    dualWrap.style.alignItems = 'flex-start';
    dualWrap.style.gap = '8px';
    dualWrap.style.marginTop = '10px';
    dualWrap.style.cursor = 'pointer';
    const dualChk = document.createElement('input');
    dualChk.type = 'checkbox';
    dualChk.id = 'stxDualElementMaliwanSwitch';
    dualChk.name = 'stxDualElementMaliwanSwitch';
    dualChk.checked = !!state.dualElementUseMaliwanSwitch;
    dualChk.addEventListener('change', ()=>{
      state.dualElementUseMaliwanSwitch = !!dualChk.checked;
      if (!state.dualElementUseMaliwanSwitch && state.slots && state.slots.secondaryEle && state.slots.secondaryEle.__autoDualElement){
        delete state.slots.secondaryEle;
      } else if (state.dualElementUseMaliwanSwitch){
        stxSyncDualElementMaliwanSwitch();
      }
      refreshBuilder();
    });
    const dualTxt = document.createElement('span');
    dualTxt.className = 'small';
    dualTxt.textContent = 'Maliwan dual element switch (auto-enabled when two elements are selected)';
    dualWrap.appendChild(dualChk);
    dualWrap.appendChild(dualTxt);
    wrap.appendChild(dualWrap);

    const note = document.createElement('div');
    note.className='small muted';
    note.style.marginTop='8px';
    note.textContent = stxSimpleBuilderItemTypeIsHeavyUi(state.itemType)
      ? 'Preset element tokens are appended after gun parts in the serial. For Maliwan heavy weapons with two elements, enable the Maliwan dual-element switch above (or add both elements to the stack).'
      : 'Preset element tokens are appended after gun parts in the serial. Picking two different elements auto-adds the Maliwan dual-element switch; you can still toggle it off above.';
    wrap.appendChild(note);

    return wrap;
  }

  /** Map legacy Enhancement `body` / `legendary` slots into `core`. */
  function migrateEnhancementLegacySlots(){
    try{
      if (!state || !state.slots) return;
      if (Object.prototype.hasOwnProperty.call(state.slots, 'legendary') && !state.slots.core){
        state.slots.core = state.slots.legendary;
        delete state.slots.legendary;
      }
      if (!Object.prototype.hasOwnProperty.call(state.slots, 'body')) return;
      const raw = state.slots.body;
      delete state.slots.body;
      const parts = Array.isArray(raw) ? raw.filter(Boolean) : (raw ? [raw] : []);
      if (!parts.length) return;
      if (!state.slots.core){
        state.slots.core = parts.length === 1 ? parts[0] : parts;
        return;
      }
      const op0 = state.slots.otherParts;
      const base = Array.isArray(op0) ? op0.slice() : (op0 ? [op0] : []);
      for (const p of parts) if (p) base.push(p);
      state.slots.otherParts = base.length ? base : null;
    }catch(_e){}
  }

  /** Map legacy `slots.special` into the split Repkit buckets (schema v2). */
  function migrateRepkitLegacySpecialSlots(){
    try{
      if (state && state.slots && Object.prototype.hasOwnProperty.call(state.slots, 'specialPlaceholder')){
        const sp = state.slots.specialPlaceholder;
        delete state.slots.specialPlaceholder;
        if (sp){
          const pile = Array.isArray(sp) ? sp.filter(Boolean) : (sp ? [sp] : []);
          const op0 = state.slots.otherParts;
          const base = Array.isArray(op0) ? op0.slice() : (op0 ? [op0] : []);
          for (const p of pile) if (p) base.push(p);
          state.slots.otherParts = base.length ? base : null;
        }
      }
      if (!state || !state.slots || !Object.prototype.hasOwnProperty.call(state.slots, 'special')) return;
      const raw = state.slots.special;
      delete state.slots.special;
      const parts = Array.isArray(raw) ? raw.filter(Boolean) : (raw ? [raw] : []);
      if (!parts.length) return;
      state.extras = Array.isArray(state.extras) ? state.extras : [];
      const route = (p)=>{
        const c = String(normCode(p && p.code) || '').toLowerCase();
        const n = String((p && p.name) || '').trim().toUpperCase();
        const isPh = !c || n === 'PLACEHOLDER';
        const isPayload = /repair_kit\.part_payload_/.test(c);
        const isElem = stxIsDatasetRepkitElementCode(c);
        const isAug = /repair_kit\.part_aug_/.test(c);
        if (isPh) return 'otherParts';
        if (isPayload) return 'payload';
        if (isAug){
          if (/resist/.test(c)) return 'perkResist';
          if (/immunity/.test(c)) return 'perkImmunity';
          if (/nova/.test(c)) return 'perkNova';
          if (/splat/.test(c)) return 'perkSplat';
          return 'perkResist';
        }
        if (isElem) return 'element';
        return '';
      };
      for (const p of parts){
        const key = route(p);
        if (key === 'otherParts'){
          const arr = Array.isArray(state.slots.otherParts) ? state.slots.otherParts.slice() : (state.slots.otherParts ? [state.slots.otherParts] : []);
          arr.push(p);
          state.slots.otherParts = arr;
          continue;
        }
        if (key && !state.slots[key]){
          state.slots[key] = p;
          continue;
        }
        const tok = tokenForPart(p) || normCode(p.code);
        if (tok) state.extras.push({ tok: String(tok), order: p.__importOrder ?? Infinity, type: 'migrated' });
      }
    }catch(_e){}
  }

  let __refreshBuilderGen = 0;
  let __allPartsIdxStamp = 0;
  function ensureAllPartsIndexed(){
    const all = getAllParts();
    const n = all.length;
    if (n === __allPartsIdxStamp) return;
    for (let i = 0; i < n; i++) all[i].__idx = i;
    __allPartsIdxStamp = n;
  }

  function stxRefreshBuilderAfterDatasetGrowth(){
    try { stxInvalidateSimpleBuilderPartCaches(); } catch (_e) {}
    try { ensureAllPartsIndexed(); } catch (_e) {}
    try {
      if (typeof refreshTopSelectors === 'function') refreshTopSelectors();
    } catch (_e) {}
    try {
      if (typeof invokeRefreshMainPart === 'function') invokeRefreshMainPart(true);
      else if (typeof refreshMainPart === 'function') refreshMainPart();
    } catch (_e) {}
    try {
      if (state && state.mainPart && typeof refreshBuilder === 'function') refreshBuilder();
    } catch (_e) {}
  }
  function refreshBuilder(){
    const gen = ++__refreshBuilderGen;

    requestAnimationFrame(function() {
      if (gen !== __refreshBuilderGen) return;
      const builder = $('builder');
      builder.innerHTML = '';

      const finishBuilderRefresh = ()=>{
        if (gen !== __refreshBuilderGen) return;
        try {
          if (typeof window.__ccBootCustomSelectRebuild === 'function') window.__ccBootCustomSelectRebuild();
        } catch (_cs) {}
        refreshOutputs();
      };

      const mainKey = String($('mainPart').value || '').trim();
      if (!mainKey){
        const directMain = state.mainPart || null;
        const directType = String((directMain && directMain.partType) || '').trim().toLowerCase();
        const directCat = String(state.itemType || state.detectedCategory || '').trim();
        if (directMain && directType === 'rarity' && /class\s*mod|classmod/i.test(directCat)) {
          state.detectedCategory = 'Class Mod';
          $('detectedCat').textContent = state.detectedCategory;
          $('builderEmpty').style.display = '';
          refreshOutputs();
          return;
        }
        /* Keep a live imported/manual body even if the <select> value briefly blanked. */
        if (directMain) {
          try { stxEnsureMainPartSelectOption(directMain); } catch (_) {}
        } else {
          state.mainPart = null;
          state.detectedCategory = null;
          $('detectedCat').textContent = '-';
          $('builderEmpty').style.display = '';
          refreshOutputs();
          return;
        }
      }

      let main = null;
      const mainKey2 = String($('mainPart').value || '').trim() || mainKey;
      try{
        const map = state && state.__mainPartByOptionKey;
        if (map && typeof map.get === 'function') main = map.get(mainKey2) || null;
      }catch(_e){}
      if (!main && /^idx:\s*-?\d+$/i.test(mainKey2)){
        const idx = Number(mainKey2.replace(/^idx:\s*/i, ''));
        if (Number.isFinite(idx)) main = getAllParts()[idx] || null;
      }
      // Backward compatibility for old numeric-only values.
      if (!main && /^-?\d+$/.test(mainKey2)){
        const idx = Number(mainKey2);
        if (Number.isFinite(idx)) main = getAllParts()[idx] || null;
      }
      if (!main && state.mainPart) main = state.mainPart;
      if (!main){
        state.mainPart = null;
        state.detectedCategory = null;
        $('detectedCat').textContent = '-';
        $('builderEmpty').style.display = '';
        refreshOutputs();
        return;
      }
      let guidedClassModActive = false;
      try {
        const gi = document.getElementById('ccGuidedItemType');
        guidedClassModActive = !!(gi && /class\s*mod|classmod/i.test(String(gi.value || '').trim()) && String(state.itemType || '').trim() === 'Class Mod');
      } catch (_) {}
      const checklistCompRarity = guidedClassModActive && state.mainPart && String(state.mainPart.partType || '').trim().toLowerCase() === 'rarity';
      if (checklistCompRarity) {
        main = state.mainPart;
      } else {
        state.mainPart = main;
      }
      // Keep slots.rarity mirrored for serializers that still read it, without rendering a second Rarity UI.
      try {
        if (!state.slots) state.slots = {};
        if (String((main && main.partType) || '').trim().toLowerCase() === 'rarity' ||
            /(?:^|[._])comp_0[1-6]_/i.test(String((main && main.code) || ''))) {
          state.slots.rarity = main;
        }
      } catch (_e) {}
      state.detectedCategory = detectCategoryFromMainPart(main) || state.itemType;
      if (stxSimpleBuilderItemTypeIsHeavyUi(state.itemType) && String(state.detectedCategory || '').trim() === 'Gadget') {
        state.detectedCategory = 'Weapon';
      }
      $('detectedCat').textContent = state.detectedCategory || '-';
      $('builderEmpty').style.display = 'none';

      const cat = state.detectedCategory;
      if (cat === 'Repkit') migrateRepkitLegacySpecialSlots();
      if (cat === 'Enhancement') migrateEnhancementLegacySlots();

      // Main part card
      const mainSlot = document.createElement('div');
      mainSlot.className = 'slot';
      const top = document.createElement('div');
      top.className='top';
      const name = document.createElement('div');
      name.className='name';
      var mainLabel = 'Rarity ID Part';
      if (String(cat || '').trim() === 'Class Mod') mainLabel = 'Body - Classmod Name';
      name.textContent = main.__isAicarFullItem ? 'Full item' : mainLabel;
      const change = document.createElement('div');
      change.className='muted small';
      change.textContent = main.__isAicarFullItem ? 'Complete deserialized serial (AI / car / guns).' : 'Selected in the left panel.';
      top.appendChild(name);
      top.appendChild(change);
      top.style.willChange = 'transform';

      const picked = document.createElement('div');
      picked.className='picked';
      if (main.__isAicarFullItem && main.__fullDeserialized){
        picked.innerHTML = `<div>${escapeHtml(displayForPart(main))}<br><code>${escapeHtml(String(main.__fullDeserialized))}</code></div>`;
      } else {
        picked.innerHTML = `<div>${escapeHtml(displayForPart(main))}<br><code>${escapeHtml(tokenForPart(main))}</code></div>`;
      }
      mainSlot.appendChild(top);
      mainSlot.appendChild(picked);

      builder.appendChild(mainSlot);

      ensureAllPartsIndexed();
      const grid = document.createElement('div');
      grid.className = cat === 'Weapon' ? 'grid' : 'grid';
      builder.appendChild(grid);

      const slotJobs = [];
      if (cat === 'Weapon'){
        const schema = getActiveWeaponSlotSchema() || [];
        for (const s of schema){
          slotJobs.push(function () {
            const el = buildSlotControl(s, 'Weapon');
            if (el) grid.appendChild(el);
          });
        }
        slotJobs.push(function () { grid.appendChild(buildElementsControl()); });
      } else {
        const schema = SIMPLE_SCHEMA_BY_CATEGORY[cat] || [];
        for (const s of schema){
          slotJobs.push(function () {
            const el = buildSlotControl(s, cat);
            if (el) grid.appendChild(el);
          });
        }
      }

      if (!slotJobs.length) {
        finishBuilderRefresh();
        return;
      }

      let jobIdx = 0;
      const slotsPerSlice = (typeof stxPerfLiteUi === 'function' && stxPerfLiteUi()) ? 1 : 2;
      function runNextSlotSlice() {
        if (gen !== __refreshBuilderGen) return;
        let built = 0;
        while (jobIdx < slotJobs.length && built < slotsPerSlice) {
          try { slotJobs[jobIdx++](); } catch (_) { jobIdx++; }
          built++;
        }
        if (jobIdx < slotJobs.length) {
          if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(runNextSlotSlice);
          else setTimeout(runNextSlotSlice, 0);
        } else {
          finishBuilderRefresh();
        }
      }
      runNextSlotSlice();
    });
  }

  function computeOrderedParts(){
    const cat = state.detectedCategory;
    if (!cat || !state.mainPart) return [];
    if (state.mainPart.__fullDeserialized) return [];

    // Weapons: emit in stable weapon slot schema order (then elements/extras handled elsewhere).
    // For all other item types, emit in a stable slot order:
    // main part first, then schema slots in schema order, then any extra slots.
    if (cat === 'Weapon') {
      /* Soft-fill rarity-matched named barrel when barrel slot is empty (do not overwrite user pick). */
      (function stxSoftFillWeaponBarrelForRarity(){
        try {
          if (state.slots && state.slots.barrel) return;
          const rp = state.mainPart;
          if (!rp || String(rp.partType || '').trim().toLowerCase() !== 'rarity') return;
          const suffix = stxRarityBarrelSuffixFromPart(rp);
          if (!suffix) return;
          const all = getAllParts();
          const man = String(state.manufacturer || '').trim().toLowerCase();
          const wt = String(state.weaponType || '').trim().toLowerCase();
          let pick = null;
          for (let i = 0; i < all.length; i++) {
            const p = all[i];
            if (!p) continue;
            const pt = String(p.partType || '').trim().toLowerCase();
            if (pt && pt !== 'barrel') continue;
            const c = String(normCode(p.code || '') || '').toLowerCase();
            if (!stxWeaponBarrelCodeMatchesRaritySuffix(c, suffix)) continue;
            if (typeof window.stxWeaponSlotPartMatch === 'function' && !window.stxWeaponSlotPartMatch('barrel', p)) continue;
            if (man) {
              const pm = String(p.manufacturer || '').trim().toLowerCase();
              if (pm && pm !== man && pm.indexOf(man) < 0 && man.indexOf(pm) < 0) continue;
            }
            if (wt) {
              const pwt = String(p.weaponType || p.itemType || '').trim().toLowerCase();
              if (pwt && pwt !== wt && pwt !== 'weapon' && pwt.indexOf(wt) < 0) continue;
            }
            pick = p;
            break;
          }
          if (pick) {
            if (!state.slots || typeof state.slots !== 'object') state.slots = {};
            state.slots.barrel = pick;
          }
        } catch (_e) {}
      })();

      const schema = getActiveWeaponSlotSchema() || [];
      const schemaKeys = schema.map(s => String(s && s.key || '')).filter(Boolean);
      const seen = new Set();
      const out = [];
      out.push(state.mainPart);
      seen.add(state.mainPart);

      const pushVal = (val)=>{
        if (!val) return;
        if (Array.isArray(val)) {
          const arr = val.filter(Boolean).slice().sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
          for (const p of arr) if (p) out.push(p);
        } else {
          if (!seen.has(val)) { out.push(val); seen.add(val); }
        }
      };

      for (const k of schemaKeys) {
        if (k === 'secondaryEle'){
          const m = String(state.manufacturer || '').trim().toLowerCase();
          if (m !== 'maliwan') continue;
        }
        pushVal(state.slots[k]);
      }
      // Maliwan dual-element switch + `{1:n}` stack ordering is handled in `computeOutputTokens`
      // so the switch always appears immediately before stacked element TypeIDs in the tail.
      const restKeys = Object.keys(state.slots).filter(k => !schemaKeys.includes(k));
      for (const k of restKeys) pushVal(state.slots[k]);
      return out.filter(Boolean);
    }

    if (cat === 'Repkit'){
      const schema = SIMPLE_SCHEMA_BY_CATEGORY[cat] || [];
      const schemaKeys = schema.map(s => String(s && s.key || '')).filter(Boolean);
      const seen = new Set();
      const out = [];

      const pushVal = (val)=>{
        if (!val) return;
        if (Array.isArray(val)) {
          const arr = val.filter(Boolean).slice().sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
          for (const p of arr) if (p) out.push(p);
        } else {
          if (!seen.has(val)) { out.push(val); seen.add(val); }
        }
      };

      // Repkit expected tail ordering (post `||`):
      // rarity comp → body → base (variant) → payload(size) → element → primary aug → secondary aug → resist → immune → nova → splat → firmware → leftovers.
      // This matches how multiple linked editors (and in-repo godroll parses) resolve repair kits.
      const isSecondaryRepkitAugment = (p)=>{
        if (!p) return false;
        const c = String(p.code || '').toLowerCase();
        const n = String(p.name || '').toLowerCase();
        // Common naming: `..._sec` marks secondary augment.
        return /_sec\b/.test(c) || /_sec\b/.test(n) || /\bsecondary\b/.test(n);
      };
      const isRepkitManufacturerIdentityOrUnique = (p)=>{
        if (!p) return false;
        const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
        // Manufacturer identity body (e.g. `mal_repair_kit.part_mal`) and manufacturer-unique augment rows.
        return /^[a-z0-9]+_repair_kit\.part_[a-z0-9]+$/.test(c) || /_repair_kit\.part_augment_unique_/.test(c);
      };
      const pushAugmentsPrimaryThenSecondary = (val)=>{
        if (!val) return;
        const arr = Array.isArray(val) ? val.filter(Boolean).slice() : [val];
        const prim = [];
        const sec = [];
        for (const p of arr){
          if (!p) continue;
          (isSecondaryRepkitAugment(p) ? sec : prim).push(p);
        }
        prim.sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
        sec.sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
        for (const p of prim) out.push(p);
        for (const p of sec) out.push(p);
      };

      if (state.mainPart) pushVal(state.mainPart);      // comp rarity
      // Manufacturer base/body is required for a valid repkit. If the user didn't explicitly pick it
      // (common when datasets mis-tag it or users rely on “one of each” in other slots),
      // auto-pick the identity part matching the selected manufacturer and current base family.
      (function ensureRepkitBody(){
        if (state.slots && state.slots.body) return;
        const man = String(state.manufacturer || '').trim().toLowerCase();
        if (!man) return;
        const prefix =
          (man === 'tediore') ? 'ted' :
          (man === 'torgue') ? 'tor' :
          (man === 'jakobs') ? 'jak' :
          (man === 'maliwan') ? 'mal' :
          (man === 'vladof') ? 'vla' :
          (man === 'daedalus') ? 'dad' :
          (man === 'order') ? 'ord' :
          (man === 'ripper') ? 'bor' :
          '';
        if (!prefix) return;
        const baseFam = Number(state.mainPart && (state.mainPart.family ?? state.mainPart.familyId));
        const all = getAllParts();
        const wantCode = prefix + '_repair_kit.part_' + prefix;
        let pick = null;
        for (let i = 0; i < all.length; i++){
          const p = all[i];
          if (!p) continue;
          const code = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
          if (code !== wantCode) continue;
          if (Number.isFinite(baseFam)) {
            const pf = Number(p.family ?? p.familyId);
            if (Number.isFinite(pf) && pf !== baseFam) continue;
          }
          pick = p;
          break;
        }
        if (pick) {
          state.slots.body = pick;
        }
      })();

      (function ensureRepkitBaseVariant(){
        if (state.slots && state.slots.base) return;
        const mp = state.mainPart;
        if (!mp) return;
        const man = String(state.manufacturer || '').trim().toLowerCase();
        const spawn = stxRepkitSpawnPrefixForUiManufacturer(man);
        if (!spawn) return;
        const c = String(normCode(mp.code || mp.spawnCode || mp.importCode || '') || '').toLowerCase();
        let suffix = '';
        const m6 = c.match(/\.comp_06_pearlescent_([a-z0-9_]+)/);
        const m5 = c.match(/\.comp_05_legendary_([a-z0-9_]+)/);
        const m4 = c.match(/\.comp_04_epic_([a-z0-9_]+)/);
        const m3 = c.match(/\.comp_03_rare_([a-z0-9_]+)/);
        const m2 = c.match(/\.comp_02_uncommon_([a-z0-9_]+)/);
        const m1 = c.match(/\.comp_01_common_([a-z0-9_]+)/);
        if (m6) suffix = m6[1];
        else if (m5) suffix = m5[1];
        else if (m4) suffix = m4[1];
        else if (m3) suffix = m3[1];
        else if (m2) suffix = m2[1];
        else if (m1) suffix = m1[1];
        if (!suffix) return;
        const want = (spawn + '.part_' + suffix).toLowerCase();
        const baseFam = Number(mp.family ?? mp.familyId);
        const all = getAllParts();
        let pick = null;
        for (let i = 0; i < all.length; i++){
          const p = all[i];
          if (!p) continue;
          const pc = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
          if (pc !== want) continue;
          if (Number.isFinite(baseFam)) {
            const pf = Number(p.family ?? p.familyId);
            if (Number.isFinite(pf) && pf !== baseFam) continue;
          }
          pick = p;
          break;
        }
        if (pick) state.slots.base = pick;
      })();

      pushVal(state.slots.body);                        // manufacturer base/body
      pushVal(state.slots.base);                         // kit variant (e.g. `*_repair_kit.part_*` from comp suffix)
      // Some manufacturer-specific repkit rows are classified as untyped and land in the cross bucket;
      // but they must serialize early (before the shared 243 pool) to match known-good editors.
      (function pushRepkitMfrUniquesEarly(){
        const extract = (parts)=>{
          const arr = Array.isArray(parts) ? parts.filter(Boolean).slice() : (parts ? [parts] : []);
          const keep = [];
          for (const p of arr){
            if (isRepkitManufacturerIdentityOrUnique(p)) out.push(p);
            else keep.push(p);
          }
          return keep;
        };
        if (state.slots.otherParts){
          const k = extract(state.slots.otherParts);
          state.slots.otherParts = k.length ? k : null;
        }
        if (state.slots.legendary){
          const wasArr = Array.isArray(state.slots.legendary);
          const k = extract(state.slots.legendary);
          state.slots.legendary = wasArr ? k : (k[0] || null);
        }
      })();
      pushVal(state.slots.payload);                     // size
      pushVal(state.slots.element);                     // element
      pushAugmentsPrimaryThenSecondary(state.slots.augment); // primary aug then secondary aug
      pushVal(state.slots.perk);                        // perk list
      pushVal(state.slots.perkResist);
      pushVal(state.slots.perkImmunity);
      pushVal(state.slots.perkNova);
      pushVal(state.slots.perkSplat);
      pushVal(state.slots.firmware);
      // Keep other optional buckets after the core ordering.
      pushVal(state.slots.legendary);
      // Any remaining schema slots (future additions) + unknown legacy/custom keys at the end.
      for (const k of schemaKeys){
        if (k === 'body' || k === 'base' || k === 'payload' || k === 'element' || k === 'augment' || k === 'perk' ||
            k === 'perkResist' || k === 'perkImmunity' || k === 'perkNova' || k === 'perkSplat' ||
            k === 'firmware' || k === 'legendary') continue;
        pushVal(state.slots[k]);
      }
      const restKeys = Object.keys(state.slots).filter(k => !schemaKeys.includes(k));
      for (const k of restKeys) pushVal(state.slots[k]);
      return out.filter(Boolean);
    }

    if (cat === 'Grenade'){
      if (state.slots && state.slots.base){
        const ex = state.slots.base;
        delete state.slots.base;
        const tok = (p)=> (p && (tokenForPart(p) || normCode(p.code))) || '';
        if (!state.slots.body) state.slots.body = ex;
        else if (Array.isArray(state.slots.body)){
          if (!state.slots.body.some(y => tok(y) === tok(ex))) state.slots.body.push(ex);
          state.slots.body = stxSortGrenadeBodySelections(state.slots.body);
        } else {
          const b = state.slots.body;
          state.slots.body = (tok(b) === tok(ex)) ? b : stxSortGrenadeBodySelections([b, ex]);
        }
      }

      (function ensureGrenadeBodyStack(){
        const man = String(state.manufacturer || '').trim().toLowerCase();
        const spawn = stxGrenadeSpawnPrefixForUiManufacturer(man);
        if (!spawn) return;
        const sm = spawn.match(/^([a-z0-9]+)_grenade_gadget$/);
        if (!sm) return;
        const baseFam = Number(state.mainPart && (state.mainPart.family ?? state.mainPart.familyId));
        const all = getAllParts();
        const tokEq = (a, b)=>{
          if (!a || !b) return false;
          const ta = tokenForPart(a) || normCode(a.code);
          const tb = tokenForPart(b) || normCode(b.code);
          return ta && tb && ta === tb;
        };
        const curList = ()=>{
          const b = state.slots && state.slots.body;
          if (!b) return [];
          return Array.isArray(b) ? b.filter(Boolean) : [b];
        };
        let list = curList();
        const wantIdentity = (spawn + '.part_' + sm[1]).toLowerCase();
        let idPick = null;
        for (let i = 0; i < all.length; i++){
          const p = all[i];
          if (!p) continue;
          const code = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
          if (code !== wantIdentity) continue;
          if (Number.isFinite(baseFam)) {
            const pf = Number(p.family ?? p.familyId);
            if (Number.isFinite(pf) && pf !== baseFam) continue;
          }
          idPick = p;
          break;
        }
        const mp = state.mainPart;
        let varPick = null;
        if (mp){
          const c = String(normCode(mp.code || mp.spawnCode || mp.importCode || '') || '').toLowerCase();
          let suffix = '';
          const m5 = c.match(/\.comp_05_legendary_([a-z0-9_]+)/);
          const m6 = c.match(/\.comp_06_pearlescent_([a-z0-9_]+)/);
          const m4 = c.match(/\.comp_04_epic_([a-z0-9_]+)/);
          if (m5) suffix = m5[1];
          else if (m6) suffix = m6[1];
          else if (m4) suffix = m4[1];
          if (suffix){
            for (let i = 0; i < all.length; i++){
              const p = all[i];
              if (!p) continue;
              const pc = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
              if (pc.indexOf(spawn + '.') !== 0) continue;
              if (!stxIsGrenadeBodyPoolRowCode(pc)) continue;
              if (!stxGrenadeBodyCodeMatchesRaritySuffix(pc, suffix)) continue;
              if (Number.isFinite(baseFam)) {
                const pf = Number(p.family ?? p.familyId);
                if (Number.isFinite(pf) && pf !== baseFam) continue;
              }
              varPick = p;
              break;
            }
          }
        }
        const hasIdentity = list.some(p => stxIsGrenadeManufacturerIdentityBodyCode(String(normCode(p && p.code || '') || '').toLowerCase()));
        if (idPick && !hasIdentity && !list.some(p => stxGrenadeBodiesMatch(p, idPick))) list.push(idPick);
        if (varPick && !list.some(p => stxGrenadeBodiesMatch(p, varPick))) list.push(varPick);
        const uniq = [];
        for (const p of list){
          if (!uniq.some(u => stxGrenadeBodiesMatch(u, p))) uniq.push(p);
        }
        list = stxSortGrenadeBodySelections(uniq);
        if (list.length === 1) state.slots.body = list[0];
        else if (list.length > 1) state.slots.body = list;
      })();

      const schema = SIMPLE_SCHEMA_BY_CATEGORY[cat] || [];
      const schemaKeys = schema.map(s => String(s && s.key || '')).filter(Boolean);
      const seen = new Set();
      const out = [];
      out.push(state.mainPart);
      seen.add(state.mainPart);

      const pushVal = (val)=>{
        if (!val) return;
        const emitOne = (p)=>{
          if (!p) return;
          const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
          if (stxIsGrenadeBodyPoolRowCode(c) && out.some(prev => stxGrenadeBodiesMatch(prev, p))) return;
          if (seen.has(p)) return;
          out.push(p);
          seen.add(p);
        };
        if (Array.isArray(val)) {
          const arr = val.filter(Boolean).slice().sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
          for (const p of arr) emitOne(p);
        } else {
          emitOne(val);
        }
      };

      const gb = state.slots.body;
      if (gb){
        const sorted = stxSortGrenadeBodySelections(gb);
        for (const p of sorted){
          if (!p) continue;
          if (out.some(prev => stxGrenadeBodiesMatch(prev, p))) continue;
          if (!seen.has(p)) { out.push(p); seen.add(p); }
        }
      }
      const grenadeEmitOrder = ['element', 'payload', 'augment', 'grenadeKitStats', 'firmware', 'special', 'pearlElem', 'pearlStat', 'otherParts'];
      const gEmitted = new Set(['body']);
      for (const k of grenadeEmitOrder){
        gEmitted.add(k);
        pushVal(state.slots[k]);
      }
      for (const k of schemaKeys){
        if (gEmitted.has(k)) continue;
        pushVal(state.slots[k]);
      }
      const restKeys = Object.keys(state.slots).filter(k => !schemaKeys.includes(k));
      for (const k of restKeys) pushVal(state.slots[k]);
      return out.filter(Boolean);
    }

    if (cat === 'Shield'){
      (function ensureShieldBody(){
        if (state.slots && state.slots.body) return;
        const man = String(state.manufacturer || '').trim().toLowerCase();
        if (!man) return;
        const prefix =
          (man === 'tediore') ? 'ted' :
          (man === 'torgue') ? 'tor' :
          (man === 'jakobs') ? 'jak' :
          (man === 'maliwan') ? 'mal' :
          (man === 'vladof') ? 'vla' :
          (man === 'daedalus') ? 'dad' :
          (man === 'order') ? 'ord' :
          (man === 'ripper') ? 'bor' :
          '';
        if (!prefix) return;
        const baseFam = Number(state.mainPart && (state.mainPart.family ?? state.mainPart.familyId));
        const armorish = (man === 'jakobs' || man === 'tediore' || man === 'torgue' || man === 'vladof');
        const tail = armorish ? 'part_body_armor' : 'part_body_energy';
        const wantCode = (prefix + '_shield.' + tail).toLowerCase();
        const all = getAllParts();
        let pick = null;
        for (let i = 0; i < all.length; i++){
          const p = all[i];
          if (!p) continue;
          const pc = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
          if (pc !== wantCode) continue;
          if (Number.isFinite(baseFam)) {
            const pf = Number(p.family ?? p.familyId);
            if (Number.isFinite(pf) && pf !== baseFam) continue;
          }
          pick = p;
          break;
        }
        if (pick) state.slots.body = pick;
      })();

      const schema = SIMPLE_SCHEMA_BY_CATEGORY[cat] || [];
      const schemaKeys = schema.map(s => String(s && s.key || '')).filter(Boolean);
      const seen = new Set();
      const out = [];

      const pushVal = (val)=>{
        if (!val) return;
        if (Array.isArray(val)) {
          const arr = val.filter(Boolean).slice().sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
          for (const p of arr) if (p) out.push(p);
        } else {
          if (!seen.has(val)) { out.push(val); seen.add(val); }
        }
      };

      out.push(state.mainPart);
      seen.add(state.mainPart);
      pushVal(state.slots.body);
      /* Shield token order: element → resistance → perks → armor/energy → firmware → unique */
      const shieldEmitOrder = [
        'elementType1',
        'resistance',
        'primary246', 'secondary246',
        'pearlElem246', 'pearlStat246',
        'armor237', 'energy248',
        'firmware246',
        'bodyLegendary',
        'otherParts'
      ];
      const emitted = new Set(['body']);
      for (const k of shieldEmitOrder){
        emitted.add(k);
        pushVal(state.slots[k]);
      }
      for (const k of schemaKeys){
        if (emitted.has(k)) continue;
        pushVal(state.slots[k]);
      }
      const restKeys = Object.keys(state.slots).filter(k => !schemaKeys.includes(k));
      for (const k of restKeys) pushVal(state.slots[k]);
      /* Keep intentional stacks (qty Add) — do not collapse consecutive identical tokens. */
      return out.filter(Boolean);
    }

    if (cat === 'Gadget'){
      (function ensureGadgetHeavyWeaponBody(){
        if (state.slots && state.slots.body) return;
        const wt = String(state.weaponType || '').trim().toLowerCase();
        if (!wt || (!/^heavy(?:\s*weapon)?$/i.test(wt) && !/heavy\s*weapon/i.test(wt))) return;
        const man = String(state.manufacturer || '').trim().toLowerCase();
        const hw =
          (man === 'maliwan') ? 'MAL' :
          (man === 'ripper') ? 'BOR' :
          (man === 'torgue') ? 'TOR' :
          (man === 'vladof') ? 'VLA' :
          '';
        if (!hw) return;
        const wantCode = (hw + '_HW.part_body').toLowerCase();
        const baseFam = Number(state.mainPart && (state.mainPart.family ?? state.mainPart.familyId));
        const all = getAllParts();
        let pick = null;
        for (let i = 0; i < all.length; i++){
          const p = all[i];
          if (!p) continue;
          const pc = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
          if (pc !== wantCode) continue;
          if (Number.isFinite(baseFam)) {
            const pf = Number(p.family ?? p.familyId);
            if (Number.isFinite(pf) && pf !== baseFam) continue;
          }
          pick = p;
          break;
        }
        if (pick) state.slots.body = pick;
      })();

      const schema = SIMPLE_SCHEMA_BY_CATEGORY[cat] || [];
      const schemaKeys = schema.map(s => String(s && s.key || '')).filter(Boolean);
      const seen = new Set();
      const out = [];

      const pushVal = (val)=>{
        if (!val) return;
        if (Array.isArray(val)) {
          const arr = val.filter(Boolean).slice().sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
          for (const p of arr) if (p) out.push(p);
        } else {
          if (!seen.has(val)) { out.push(val); seen.add(val); }
        }
      };

      out.push(state.mainPart);
      seen.add(state.mainPart);
      pushVal(state.slots.body);
      const gadgetEmitOrder = [
        'bodyAcc', 'barrel', 'barrelAcc', 'rarity',
        'payload', 'augment', 'legendary', 'special', 'firmware', 'otherParts'
      ];
      const gaEmitted = new Set(['body']);
      for (const k of gadgetEmitOrder){
        gaEmitted.add(k);
        pushVal(state.slots[k]);
      }
      for (const k of schemaKeys){
        if (gaEmitted.has(k)) continue;
        pushVal(state.slots[k]);
      }
      const restKeys = Object.keys(state.slots).filter(k => !schemaKeys.includes(k));
      for (const k of restKeys) pushVal(state.slots[k]);
      return out.filter(Boolean);
    }

    if (cat === 'Enhancement'){
      const schema = SIMPLE_SCHEMA_BY_CATEGORY[cat] || [];
      const schemaKeys = schema.map(s => String(s && s.key || '')).filter(Boolean);
      const seen = new Set();
      const out = [];
      const pushVal = (val)=>{
        if (!val) return;
        if (Array.isArray(val)) {
          const arr = val.filter(Boolean).slice().sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
          for (const p of arr) if (p) out.push(p);
        } else {
          if (!seen.has(val)) { out.push(val); seen.add(val); }
        }
      };
      out.push(state.mainPart);
      seen.add(state.mainPart);
      const enhEmitOrder = ['core', 'firmware', 'stats', 'otherParts'];
      const enhEmitted = new Set();
      for (const k of enhEmitOrder){
        enhEmitted.add(k);
        pushVal(state.slots[k]);
      }
      for (const k of schemaKeys){
        if (enhEmitted.has(k)) continue;
        pushVal(state.slots[k]);
      }
      const restKeys = Object.keys(state.slots).filter(k => !schemaKeys.includes(k));
      for (const k of restKeys) pushVal(state.slots[k]);
      return out.filter(Boolean);
    }

    if (cat === 'Class Mod'){
      const schema = SIMPLE_SCHEMA_BY_CATEGORY[cat] || [];
      const schemaKeys = schema.map(s => String(s && s.key || '')).filter(Boolean);
      const seen = new Set();
      const out = [];
      const pushVal = (val)=>{
        if (!val) return;
        if (Array.isArray(val)) {
          const arr = val.filter(Boolean).slice().sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
          for (const p of arr) if (p) out.push(p);
        } else {
          if (!seen.has(val)) { out.push(val); seen.add(val); }
        }
      };
      out.push(state.mainPart);
      seen.add(state.mainPart);
      /* After rarity/name: Element → Universal → Secondary → Perks (skills) → Firmware.
         Keeping element before the 234-family perks lets firmware stay last but still pack with the other 234 tokens. */
      const cmEmitOrder = ['namePart', 'element', 'universal', 'secondary', 'perk', 'firmware', 'enhancementGunStats', 'otherParts'];
      const cmEmitted = new Set();
      for (const k of cmEmitOrder){
        cmEmitted.add(k);
        pushVal(state.slots[k]);
      }
      for (const k of schemaKeys){
        if (cmEmitted.has(k)) continue;
        pushVal(state.slots[k]);
      }
      const restKeys = Object.keys(state.slots).filter(k => !schemaKeys.includes(k) && !cmEmitted.has(k));
      for (const k of restKeys) pushVal(state.slots[k]);
      return out.filter(Boolean);
    }

    if (cat === 'Character'){
      const schema = SIMPLE_SCHEMA_BY_CATEGORY[cat] || [];
      const schemaKeys = schema.map(s => String(s && s.key || '')).filter(Boolean);
      const seen = new Set();
      const out = [];
      const pushVal = (val)=>{
        if (!val) return;
        if (Array.isArray(val)) {
          const arr = val.filter(Boolean).slice().sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
          for (const p of arr) if (p) out.push(p);
        } else {
          if (!seen.has(val)) { out.push(val); seen.add(val); }
        }
      };
      out.push(state.mainPart);
      seen.add(state.mainPart);
      const chEmitOrder = ['rarity', 'perk', 'special', 'firmware', 'otherParts'];
      const chEmitted = new Set();
      for (const k of chEmitOrder){
        chEmitted.add(k);
        pushVal(state.slots[k]);
      }
      for (const k of schemaKeys){
        if (chEmitted.has(k)) continue;
        pushVal(state.slots[k]);
      }
      const restKeys = Object.keys(state.slots).filter(k => !schemaKeys.includes(k));
      for (const k of restKeys) pushVal(state.slots[k]);
      return out.filter(Boolean);
    }

    const schema = SIMPLE_SCHEMA_BY_CATEGORY[cat] || [];
    const schemaKeys = schema.map(s => String(s && s.key || '')).filter(Boolean);
    const seen = new Set();
    const out = [];

    out.push(state.mainPart);
    seen.add(state.mainPart);

    const pushVal = (val)=>{
      if (!val) return;
      if (Array.isArray(val)) {
        const arr = val.filter(Boolean).slice().sort((a,b)=>(a.__importOrder ?? Infinity) - (b.__importOrder ?? Infinity));
        for (const p of arr) if (p) out.push(p);
      } else {
        if (!seen.has(val)) { out.push(val); seen.add(val); }
      }
    };

    // Schema slots, in order
    for (const k of schemaKeys) pushVal(state.slots[k]);

    // Any remaining slots (future/legacy/custom) at the end, preserving import-order where present.
    const restKeys = Object.keys(state.slots).filter(k => !schemaKeys.includes(k));
    for (const k of restKeys) pushVal(state.slots[k]);

    return out.filter(Boolean);
  }

  /** Harlowe + legendary: append `{27}` immediately after the name / leg-effect token (game format). */
  function stxClassModTokensWithHarlowe27(tokens, state, cat){
    const out = Array.isArray(tokens) ? tokens.slice() : [];
    if (String(cat) !== 'Class Mod' || !state || !out.length) return out;
    const manLo = String((state.classmodClass || state.manufacturer || '')).trim().toLowerCase();
    if (manLo !== 'harlowe' && manLo !== 'gravitar') return out;
    if (out.some(t => String(t || '').trim() === '{27}')) return out;
    const mainT = stxRarityTierFromPartForGrouping(state.mainPart, state.manufacturer);
    if (mainT !== 4) return out;
    const np = state.slots && state.slots.namePart;
    if (!np) return out;
    const nameTok = String(tokenForPart(np) || '').trim();
    if (!nameTok || nameTok === '[object Object]') return out;
    const ix = out.indexOf(nameTok);
    if (ix === -1) return out;
    out.splice(ix + 1, 0, '{27}');
    return out;
  }


  /**
   * Save-editor checklist class key for legendary rarity↔name pairing maps.
   */
  function stxClassModChecklistClassName(man){
    const k = stxCanonicalClassModManufacturerKey(man);
    if (k === 'siren') return 'Vex';
    if (k === 'paladin') return 'Amon';
    if (k === 'exo soldier') return 'Rafa';
    if (k === 'gravitar') return 'Harlowe';
    if (k === 'corpohacker') return 'Loveless';
    if (k === 'robodealer') return 'C4sh';
    return '';
  }

  const STX_CM_LEGENDARY_RARITY_BY_NAME = {
    Vex: { 10: 56, 11: 55, 12: 54, 13: 53, 14: 52, 15: 51 },
    Amon: { 10: 25, 11: 24, 12: 23, 13: 22, 14: 21, 15: 20 },
    Rafa: { 10: 26, 11: 25, 12: 24, 13: 23, 14: 22, 15: 21 },
    Harlowe: { 10: 26, 11: 25, 12: 24, 13: 23, 14: 22, 15: 21 },
    Loveless: { 6: 52, 5: 53, 4: 54, 3: 55, 2: 56, 1: 217 }
  };
  const STX_CM_LEGENDARY_DLC_NAME_TO_RARITY = {
    Vex: { 538: 539, 544: 545, 546: 547 },
    Amon: { 538: 539, 544: 545, 546: 547 },
    Rafa: { 540: 541, 542: 543, 546: 547, 548: 549 },
    Harlowe: { 540: 541, 542: 543, 546: 547, 548: 549 },
    Loveless: { 540: 544, 545: 546, 539: 543, 538: 542, 222: 541 }
  };

  function stxResolveClassModPairedRarityItemId(namePart, man){
    if (!namePart) return null;
    const cls = stxClassModChecklistClassName(man);
    const itemId = partItemIdOf(namePart);
    const spawn = String(normCode(namePart.code || namePart.spawnCode || '') || '').replace(/^"+|"+$/g, '').trim().toLowerCase();

    if (cls && Number.isFinite(itemId) && itemId >= 10 && itemId <= 15) {
      const byName = STX_CM_LEGENDARY_RARITY_BY_NAME[cls];
      if (byName && Number.isFinite(Number(byName[itemId]))) return Number(byName[itemId]);
    }
    if (cls === 'Loveless' && Number.isFinite(itemId) && itemId >= 1 && itemId <= 6) {
      const byName = STX_CM_LEGENDARY_RARITY_BY_NAME.Loveless;
      if (byName && Number.isFinite(Number(byName[itemId]))) return Number(byName[itemId]);
    }
    if (cls && Number.isFinite(itemId)) {
      const dlcMap = STX_CM_LEGENDARY_DLC_NAME_TO_RARITY[cls];
      if (dlcMap && Number.isFinite(Number(dlcMap[itemId]))) return Number(dlcMap[itemId]);
    }
    const bodyTail = (spawn.match(/leg_body_([a-z0-9_]+)/i) || [])[1] || '';
    if (bodyTail) {
      const want = 'comp_05_legendary_' + bodyTail.toLowerCase();
      const fam = partFamilyIdOf(namePart);
      const rows = Array.isArray(window.STX_RARITIES) ? window.STX_RARITIES : [];
      for (let i = 0; i < rows.length; i++) {
        const r = rows[i];
        if (!r) continue;
        if (Number.isFinite(fam) && Number(r.familyId) !== Number(fam)) continue;
        const its = String(r.itemTypeString || r.code || '').toLowerCase();
        if (its.indexOf(want) === -1) continue;
        const rid = Number(r.itemId);
        if (Number.isFinite(rid)) return rid;
      }
    }
    return null;
  }

  function computeOutputTokens(force){
    if (!force && typeof window.__ccIsScrollBusy === 'function' && window.__ccIsScrollBusy()) return { tokens: [], json: {} };
    const cat = state.detectedCategory;
    if (!cat || !state.mainPart) return {tokens:[], json:{}};
    if (state.mainPart.__fullDeserialized){
      const fs = String(state.mainPart.__fullDeserialized).trim();
      return {
        tokens: fs ? [String(fs)] : [],
        json: {
          category: 'Other',
          manufacturer: state.manufacturer || 'AI Car Guns',
          fullItemDeserialized: fs,
          mode: 'fullItem'
        }
      };
    }

    const orderedParts = computeOrderedParts();
    
    // Emit in schema slot order (not raw import token order).
    let finalItems = [];
    let seq = 0;

    for (const p of orderedParts) {
      const t = tokenForPart(p);
      if (t !== '' && t != null) {
        let sTok = String(t).trim();
        if (sTok === '[object Object]') continue;
        finalItems.push({
          tok: sTok,
          order: seq++
        });
      }
    }

    const extraBase = seq + 1000;
    let extraSeq = 0;
    if (Array.isArray(state.extras)) {
      for (const ex of state.extras) {
        if (ex && typeof ex === 'object' && ex.tok) {
          let sTok = String(ex.tok).trim();
          if (sTok === '[object Object]') continue;
          finalItems.push({
            tok: sTok,
            order: Number.isFinite(ex.order) ? (extraBase + ex.order) : (extraBase + extraSeq++)
          });
        } else if (ex) {
          let sTok = String(ex).trim();
          if (sTok === '[object Object]') continue;
          finalItems.push({
            tok: sTok,
            order: extraBase + extraSeq++
          });
        }
      }
    }

    const weaponLike = (cat === 'Weapon') || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType);
    if (weaponLike){
      let ord = seq;

      const prim = state.primaryElement || 'None';
      const primObj = ELEMENTS.find(x=>x.key===prim);
      const stack = Array.isArray(state.elementStack) ? state.elementStack.slice() : [];
      const mfrL = String(state.manufacturer || '').trim().toLowerCase();
      const manualSw = state.slots && state.slots.secondaryEle;
      const mc = manualSw ? String(normCode(manualSw.code || '') || '').toLowerCase() : '';
      const hasManualSwitch = mc.includes('part_secondary_elem') && mc.includes('_mal');

      const pushTok = (tok, o, allowDup)=>{
        const s = String(tok || '').trim();
        if (!s || s === '[object Object]') return;
        /* Element stacks must keep duplicate `{1:13}` copies — packing turns them into `{1:[13 13]}`. */
        if (!allowDup && finalItems.some(fi => String(fi.tok) === s)) return;
        finalItems.push({ tok: s, order: o });
      };

      if (primObj && primObj.code) pushTok(primObj.code, ord++, true);
      if (stack.length && state.dualElementUseMaliwanSwitch && prim !== 'None' && !hasManualSwitch){
        const sw = stxFindMaliwanDualSwitchPart(prim, stack[0]);
        if (sw){
          const st = tokenForPart(sw);
          if (st) pushTok(st, ord++, false);
        }
      }
      for (const e of stack){
        const eo = ELEMENTS.find(x=>x.key===e);
        if (eo && eo.code) pushTok(eo.code, ord++, true);
      }

      const sc = getSelectedWeaponSkinAndCamo();
      if (sc && sc.spawnToken) {
        const sSpawn = String(sc.spawnToken);
        if (!finalItems.some(fi => String(fi.tok) === sSpawn || unquoteWrappedValue(fi.tok) === unquoteWrappedValue(sSpawn))) {
          finalItems.push({ tok: sSpawn, order: extraBase + 90000 });
        }
      }
      if (sc && sc.camoToken) {
        const sCamo = String(sc.camoToken);
        if (!finalItems.some(fi => String(fi.tok) === sCamo)) {
          finalItems.push({ tok: sCamo, order: extraBase + 100000 });
        }
      }
    }

    finalItems.sort((a, b) => a.order - b.order);

    let tokens = finalItems.map(x => String(x.tok));
    const catPearlTier =
      cat === 'Class Mod' && Number.isFinite(getSelectedRarityTier()) && getSelectedRarityTier() === 5;
    if ((isStxSimplePearlOverrideChecked() || catPearlTier) && !(state.mainPart && state.mainPart.__fullDeserialized)){
      const b0 = getSelectedBaseItem();
      const bf = Number(b0 && b0.familyId);
      if (Number.isFinite(bf)){
        const isW = cat === 'Weapon' || (state && stxSimpleBuilderItemTypeIsHeavyUi(state.itemType));
        const wt = isW ? String((state && state.weaponType) || '').trim() : '';
        const pr = cat === 'Class Mod'
          ? stxPickClassModPearlOverrideBraceToken(bf)
          : stxPickPearlOverrideBraceToken(bf, isW, cat, wt);
        if (pr){
          /* Prepend random community pearl rarity id — all categories (keeps craft rarity/name). */
          tokens = stxApplyPearlRarityOnlyToTailSeq(tokens, pr, bf, cat);
        }
      }
    }
    if (cat === 'Class Mod') tokens = stxClassModTokensWithHarlowe27(tokens, state, cat);

    const jsonObj = {
      category: cat,
      manufacturer: state.manufacturer || '',
      weaponType: (cat==='Weapon') ? (state.weaponType || '') : '',
      level: Number(state.level || 1),
      main: state.mainPart ? {
        name: state.mainPart.name || '',
        code: normCode(state.mainPart.code),
        idRaw: String(state.mainPart.idRaw ?? ''),
        id: state.mainPart.id ?? null,
        partType: state.mainPart.partType || ''
      } : null,
      slots: {},
      elements: (cat === 'Weapon' || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType)) ? { primary: state.primaryElement || 'None', stack: state.elementStack.slice() } : undefined,
      extras: state.extras.map(ex => {
        if (ex && typeof ex === 'object' && ex.tok) return String(ex.tok);
        return String(ex || '');
      }),
      mode: state.idMode ? 'idRaw' : 'code'
    };

    const base = getSelectedBaseItem();
    if (base) jsonObj.seed = getSeed(base);
    const scJson = (cat === 'Weapon') ? getSelectedWeaponSkinAndCamo() : null;
    if (scJson){
      if (scJson.skinRaw) jsonObj.skin = scJson.skinRaw;
      if (scJson.spawnToken) jsonObj.skinSpawnToken = String(scJson.spawnToken || '').trim();
      if (Number.isFinite(scJson.rarityId)) jsonObj.skinRarityId = Number(scJson.rarityId);
      if (scJson.rarityToken) jsonObj.skinRarityToken = String(scJson.rarityToken || '').trim();
      if (scJson.camoToken) jsonObj.camo = scJson.camoToken;
    }

    // serialize slots
    const addSlot = (k, v)=>{
      if (!v) return;
      if (Array.isArray(v)){
        jsonObj.slots[k] = v.map(p=>({
          name: p.name || '',
          code: normCode(p.code),
          idRaw: String(p.idRaw ?? ''),
          id: p.id ?? null,
          partType: p.partType || ''
        }));
      } else {
        jsonObj.slots[k] = {
          name: v.name || '',
          code: normCode(v.code),
          idRaw: String(v.idRaw ?? ''),
          id: v.id ?? null,
          partType: v.partType || ''
        };
      }
    };
    for (const k of Object.keys(state.slots)){
      addSlot(k, state.slots[k]);
    }

    return {tokens, json: jsonObj};
  }

  function getSelectedBaseItem(){
    const tier = getSelectedRarityTier();
    const useTierFilter = rarityTierFilterActiveForCurrentContext();
    const rows = getRarityRowsForCurrentContext()
      .filter(r => !useTierFilter || !Number.isFinite(tier) || rarityTierFromItemTypeString(r && r.itemTypeString, r) === tier);
    const famFromMain = partFamilyIdOf(state.mainPart || null);
    const mainPartType = String((state.mainPart && state.mainPart.partType) || '').trim().toLowerCase();
    const mainPartItemId = partItemIdOf(state.mainPart || null);
    if (mainPartType === 'rarity' && Number.isFinite(famFromMain) && Number.isFinite(mainPartItemId)){
      return { familyId: Number(famFromMain), itemId: Number(mainPartItemId) };
    }
    const raritySlotPartRaw = state && state.slots ? state.slots.rarity : null;
    const raritySlotPart = Array.isArray(raritySlotPartRaw) ? (raritySlotPartRaw[0] || null) : raritySlotPartRaw;
    const raritySlotIsRarity = String((raritySlotPart && raritySlotPart.partType) || '').trim().toLowerCase() === 'rarity';
    const raritySlotItemId = raritySlotIsRarity ? partItemIdOf(raritySlotPart || null) : null;
    const raritySlotFamilyId = raritySlotIsRarity ? partFamilyIdOf(raritySlotPart || null) : null;

    let pool = rows;
    if (Number.isFinite(famFromMain)){
      const byFam = rows.filter(r => Number(r && r.familyId) === Number(famFromMain));
      if (byFam.length) pool = byFam;
    }

    // Prefer the explicitly selected shield rarity slot item (e.g. {8} vs {7}).
    if (Number.isFinite(raritySlotItemId)){
      const bySlot = pool.filter(r => Number(r && r.itemId) === Number(raritySlotItemId));
      if (bySlot.length){
        return { familyId: Number(bySlot[0].familyId), itemId: Number(bySlot[0].itemId) };
      }
      if (Number.isFinite(raritySlotFamilyId)){
        return { familyId: Number(raritySlotFamilyId), itemId: Number(raritySlotItemId) };
      }
      if (Number.isFinite(famFromMain)){
        return { familyId: Number(famFromMain), itemId: Number(raritySlotItemId) };
      }
    }

    const pick = pool.find(r => !String(r && r.legendaryName || '').trim()) || pool[0] || null;
    if (pick){
      // Do not invent a default base from the first rarity row until the user selects a main/rarity part
      // (or a rarity slot part for shield-style layouts).
      if (!state.mainPart && !raritySlotIsRarity){
        return null;
      }
      return { familyId: Number(pick.familyId), itemId: Number(pick.itemId) };
    }
    if (Number.isFinite(famFromMain)){
      return { familyId: Number(famFromMain), itemId: null };
    }
    return null;
  }

  function quoteIfGunPart(tok){
    const t = String(tok).trim();
    if (!t) return '';
    if (t.startsWith('{') && t.endsWith('}')) return t;
    if (/\.part_/.test(t) || /^[A-Z]{3}_[A-Z]{2}\./.test(t)) return `"${t}"`;
    return t;
  }

  
  /**
   * Compress consecutive foreign-family numeric-id tokens into bracket lists.
   * Example: `{243:106} {243:100}` → `{243:[106 100]}`.
   *
   * Important: this only compresses *consecutive* runs so we preserve order relative to other families
   * (matches examples like `{243:[106 100]} {6} {243:[75 ...]}`).
   */
  /**
   * Pack consecutive weapon TypeID-1 element tokens into `{1:[13 13]}` form.
   * Keeps non-element tokens (e.g. Maliwan switch spawn codes) in place as separators.
   */
  function stxPackWeaponElementTokens(tokens){
    const src = Array.isArray(tokens) ? tokens : [];
    const out = [];
    let pending = [];
    const flush = ()=>{
      if (!pending.length) return;
      if (pending.length === 1) out.push(`{1:${pending[0]}}`);
      else out.push(`{1:[${pending.join(' ')}]}`);
      pending = [];
    };
    for (let i = 0; i < src.length; i++) {
      const t = String(src[i] || '').trim();
      if (!t) continue;
      const m = t.match(/^\{\s*1\s*:\s*(\d+)\s*\}$/);
      if (m) {
        pending.push(Number(m[1]));
        continue;
      }
      const packed = t.match(/^\{\s*1\s*:\s*\[([^\]]+)\]\s*\}$/);
      if (packed) {
        const ids = String(packed[1] || '').match(/\d+/g) || [];
        for (let j = 0; j < ids.length; j++) pending.push(Number(ids[j]));
        continue;
      }
      flush();
      out.push(t);
    }
    flush();
    return out;
  }
  try { window.stxPackWeaponElementTokens = stxPackWeaponElementTokens; } catch (_) {}

  function compressConsecutiveFamilyRefs(tokens){
    const src = Array.isArray(tokens) ? tokens : [];
    const out = [];
    let pendingFam = null;
    let pendingIds = [];

    const flush = ()=>{
      if (!Number.isFinite(pendingFam) || !pendingIds.length) { pendingFam = null; pendingIds = []; return; }
      if (pendingIds.length === 1) out.push(`{${pendingFam}:${pendingIds[0]}}`);
      else out.push(`{${pendingFam}:[${pendingIds.join(' ')}]}`);
      pendingFam = null;
      pendingIds = [];
    };

    for (const tok0 of src){
      const tok = String(tok0 || '').trim();
      if (!tok) continue;

      // Bracket lists contribute ids to the same-family run (merge {24:[44 44]} {24:[44 44]} → one list).
      const packed = tok.match(/^\{\s*(\d+)\s*:\s*\[([^\]]+)\]\s*\}$/);
      if (packed) {
        const fam = Number(packed[1]);
        const ids = packed[2].trim().split(/\s+/).filter(Boolean).map((x) => Number(x));
        if (!Number.isFinite(fam) || !ids.length || ids.some((n) => !Number.isFinite(n))) {
          flush();
          out.push(tok);
          continue;
        }
        if (pendingFam == null || pendingFam === fam) {
          pendingFam = fam;
          pendingIds.push(...ids);
        } else {
          flush();
          pendingFam = fam;
          pendingIds = ids.slice();
        }
        continue;
      }

      const m = tok.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
      if (!m){
        flush();
        out.push(tok);
        continue;
      }

      const fam = Number(m[1]);
      const id = Number(m[2]);
      if (!Number.isFinite(fam) || !Number.isFinite(id)){
        flush();
        out.push(tok);
        continue;
      }

      if (pendingFam == null || pendingFam === fam){
        pendingFam = fam;
        pendingIds.push(id);
      } else {
        flush();
        pendingFam = fam;
        pendingIds = [id];
      }
    }
    flush();
    return out;
  }

  /** Legacy name: keep call sites stable. */
  function compressFamilyRefsAll(tokens){
    return compressConsecutiveFamilyRefs(tokens);
  }

function randSeed(){
    // Avoid 0 so the seed marker is always emitted for auto seeds.
    return Math.floor(Math.random() * 9999) + 1;
  }

  function getSeed(base){
    const seedEl = $('seedInput');
    const manual = String(seedEl && seedEl.value ? seedEl.value : '').trim();
    if (manual && /^-?\d+$/.test(manual)){
      state.__seedEnabled = true;
      state.seedAuto = null;
      state.seedKey = null;
      if (seedEl) seedEl.placeholder = 'manual';
      return Number(manual);
    }

    // Seed gating: do not auto-roll a random seed until the user begins building.
    if (!state.__seedEnabled){
      if (seedEl && !seedEl.value){
        seedEl.placeholder = 'random (enabled after selecting base / adding a part)';
      }
      return 0;
    }

    const key = base ? `${base.familyId}:${base.itemId}:${Number(state.level || 1)}` : 'none';
    if (typeof state.seedAuto !== 'number' || state.seedKey !== key){
      state.seedAuto = randSeed();
      state.seedKey = key;
    }
    if (seedEl) seedEl.placeholder = `random (${state.seedAuto})`;
    return state.seedAuto;
  }

  function isPhospheneLabel(label){
    return /(phosphene|shiny)/i.test(label || '');
  }

  function unquoteWrappedValue(v){
    let s = String(v || '').trim();
    // Some select values are serialized as quoted tokens; normalize once here.
    while (s.length >= 2 && ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'")))){
      s = s.slice(1, -1).trim();
    }
    return s;
  }

  function hasSpawnCode(label, value){
    const lbl = String(label || '').trim();
    const val = unquoteWrappedValue(value);
    if (!lbl && !val) return false;
    if (/^Cosmetics_Weapon_/i.test(val) || /^Cosmetics_Weapon_/i.test(lbl)) return true;
    if (/spawn[\s_-]*id/i.test(lbl)) return true;
    const m = lbl.match(/\(([^)]+)\)/);
    if (m && m[1]){
      const inside = String(m[1]).trim();
      if (/^Cosmetics_Weapon_/i.test(inside)) return true;
      if (/[A-Za-z_]/.test(inside) && !/^\d+\s*:\s*(?:\[\s*\d+(?:\s+\d+)*\s*\]|\d+)\s*$/.test(inside)) return true;
    }
    return false;
  }

  function isCamoTokenSyntax(value){
    const s = unquoteWrappedValue(value);
    return /^\|\s*["']?c["']?\s*,\s*\d+\s*\|$/i.test(s);
  }

  function isCamoLiteralSyntax(value){
    const s = unquoteWrappedValue(value);
    return /^\|?\s*["']?c["']?\s*,\s*\d+\s*\|?$/i.test(s);
  }

  function extractSkinNumericId(value, allowBareNumeric, allowGenericNumericBrace){
    const s = unquoteWrappedValue(value);
    if (!s) return null;
    let m = s.match(/^\{\s*27\s*:\s*(\d+)\s*\}$/);
    if (m) return Number(m[1]);
    m = s.match(/^\|\s*["']?c["']?\s*,\s*(\d+)\s*\|$/i);
    if (m) return Number(m[1]);
    m = s.match(/^["']?c["']?\s*,\s*(\d+)$/i);
    if (m) return Number(m[1]);
    if (allowGenericNumericBrace){
      m = s.match(/^\{\s*\d+\s*:\s*(\d+)\s*\}$/);
      if (m) return Number(m[1]);
    }
    if (allowBareNumeric){
      m = s.match(/^(\d+)$/);
      if (m) return Number(m[1]);
    }
    return null;
  }

  function canonicalSkinToken(value, allowBareNumeric, allowGenericNumericBrace){
    const s = unquoteWrappedValue(value);
    if (!s) return '';
    const id = extractSkinNumericId(s, !!allowBareNumeric, !!allowGenericNumericBrace);
    if (Number.isFinite(id)) return `{27:${id}}`;
    return s;
  }

  function canonicalCamoToken(value){
    const s = unquoteWrappedValue(value);
    if (!s) return '';
    const m = s.match(/^\|\s*["']?c["']?\s*,\s*(\d+)\s*\|$/i)
      || s.match(/^["']?c["']?\s*,\s*(\d+)$/i);
    if (!m) return '';
    const id = Number(m[1]);
    /* Camo id 0 is invalid junk (shows up as broken `):0`-like tails). */
    if (!Number.isFinite(id) || id <= 0) return '';
    return `|"c",${id}|`;
  }

  /**
   * Resolve a skin/camo dropdown value to a serial-safe token.
   * Returns '' if the value is junk/unresolved Cosmetics (caller should skip).
   * Returns null if the value is a normal part token (leave unchanged).
   */
  function stxResolveSkinOrCamoTokenForSerial(valueRaw, optionEl){
    const raw = String(valueRaw || '').trim();
    if (!raw) return '';
    const camo = canonicalCamoToken(raw);
    if (camo) return camo;
    if (isCamoLiteralSyntax(raw) || isCamoTokenSyntax(raw)) return '';
    const unq = unquoteWrappedValue(raw);
    /* Skin (optional) Cosmetics spawn names → Skin customization (`c`), not bare quoted names. */
    if (/^Cosmetics_Weapon_/i.test(unq)) {
      try {
        const r = (typeof resolveCosmeticWeaponSkinSerial === 'function')
          ? resolveCosmeticWeaponSkinSerial(unq)
          : null;
        if (r && r.camoToken) return r.camoToken;
        if (r && r.stringCamo) return r.stringCamo;
        if (r && r.skinCode) return r.skinCode;
      } catch (_) {}
      return '';
    }
    const skinTok = extractSkinRarityToken(raw, optionEl || null);
    if (skinTok) {
      /* Reject bare `{0}` / `{fam:0}` garbage. */
      if (/^\{\s*\d+\s*:\s*0\s*\}$/.test(skinTok) || /^\{\s*0\s*\}$/.test(skinTok)) return '';
      return skinTok;
    }
    /* Malformed fragments like `):0` / `,0|` after broken camo quoting. */
    if (/^[):,\s|]*0\|?$/.test(unq) || /^["']?c["']?\s*,\s*0\|?$/i.test(unq)) return '';
    if (/^\{\s*\d+\s*(?::\s*(?:\d+|\[[^\]]*\]))?\s*\}$/.test(unq)) return unq;
    return null;
  }
  try { window.stxResolveSkinOrCamoTokenForSerial = stxResolveSkinOrCamoTokenForSerial; } catch (_) {}

  function isSkinTokenCandidate(value){
    const s = String(value || '').trim();
    if (!s) return false;
    const unq = unquoteWrappedValue(s);
    if (/^Cosmetics_Weapon_/i.test(unq)) return true;
    // Stacked mixer braces `{fam:[id1 id2…]}` are always skins (not TypeID-1 elements).
    if (/^\{\s*\d+\s*:\s*\[/.test(unq) && !/^\{\s*1\s*:/.test(unq)) return true;
    return Number.isFinite(extractSkinNumericId(unq, false, false));
  }

  function extractNumericIdFromLabelText(text){
    const s = String(text || '').trim();
    if (!s) return null;
    let m = s.match(/\{\s*\d+\s*:\s*(\d+)\s*\}/);
    if (m) return Number(m[1]);
    m = s.match(/\(\s*\d+\s*:\s*(\d+)\s*\)/);
    if (m) return Number(m[1]);
    m = s.match(/\b\d+\s*:\s*(\d+)\b/);
    if (m) return Number(m[1]);
    m = s.match(/\|\s*["']?c["']?\s*,\s*(\d+)\s*\|/i);
    if (m) return Number(m[1]);
    return null;
  }

  function parseItemIdFromIdRawText(raw){
    const s = unquoteWrappedValue(raw);
    if (!s) return null;
    let m = s.match(/^\s*\d+\s*:\s*(\d+)\s*$/);
    if (m) return Number(m[1]);
    m = s.match(/^\s*(\d+)\s*$/);
    if (m) return Number(m[1]);
    return null;
  }

  function parseFamilyItemPair(raw){
    const s = unquoteWrappedValue(raw);
    if (!s) return null;
    let m = s.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/) || s.match(/^(\d+)\s*:\s*(\d+)$/);
    if (m) return { family: Number(m[1]), itemId: Number(m[2]) };
    m = s.match(/^\{\s*(\d+)\s*\}$/) || s.match(/^(\d+)$/);
    if (m) return { family: null, itemId: Number(m[1]) };
    return null;
  }

  /** `{fam:id}` or stacked `{fam:[id1 id2 …]}` skin braces — keep opaque through serialize. */
  function isStackedOrFamilySkinBrace(raw){
    const s = String(raw || '').trim().replace(/\s+/g, ' ');
    return /^\{\s*\d+\s*:\s*(?:\[\s*\d+(?:\s+\d+)*\s*\]|\d+)\s*\}$/.test(s);
  }

  function canonicalizeSkinBraceToken(raw){
    const s = String(raw || '').trim();
    if (!s) return '';
    const parsed = parseIdToken(s);
    if (parsed && parsed.kind === 'family' && parsed.rawIds != null){
      const ids = String(parsed.rawIds).trim().replace(/\s+/g, ' ');
      return `{${parsed.family}:[${ids}]}`;
    }
    if (parsed && parsed.kind === 'family' && Array.isArray(parsed.ids) && parsed.ids.length === 1){
      return `{${parsed.family}:${parsed.ids[0]}}`;
    }
    if (isStackedOrFamilySkinBrace(s)) return s.replace(/\s+/g, ' ');
    return '';
  }

  function tokenFromPair(pair, fallbackFamily){
    const p = pair || null;
    if (!p || !Number.isFinite(Number(p.itemId))) return '';
    const itemId = Number(p.itemId);
    const fam = Number.isFinite(Number(p.family)) ? Number(p.family)
      : (Number.isFinite(Number(fallbackFamily)) ? Number(fallbackFamily) : null);
    if (Number.isFinite(fam)) return `{${fam}:${itemId}}`;
    return `{${itemId}}`;
  }

  function resolveSpawnSkinRarityId(raw){
    const key = unquoteWrappedValue(raw);
    if (!key) return null;
    const cacheKey = `__spawnSkinRid__${key}`;
    try{
      if (Object.prototype.hasOwnProperty.call(window, cacheKey)){
        const hit = Number(window[cacheKey]);
        return Number.isFinite(hit) ? hit : null;
      }
    }catch(_){}

    let resolved = null;
    const isCosmetic = /^Cosmetics_Weapon_/i.test(key);

    try{
      let part = null;
      if (typeof window.__lookupPartByImportCode === 'function') part = window.__lookupPartByImportCode(key);
      if (!part && typeof window.lookupPart === 'function') part = window.lookupPart(key);
      const pid = part ? Number(part.itemId || part.id || part.partId) : NaN;
      if (Number.isFinite(pid)) resolved = Number(pid);
    }catch(_){}

    if (!Number.isFinite(resolved)){
      try{
        const map = window.__ccSpawnToIdRawMap;
        if (map && typeof map.get === 'function'){
          const unquoted = key.replace(/^"+|"+$/g, '');
          const idRaw = String(map.get(key) || map.get(unquoted) || map.get(`"${unquoted}"`) || '').trim();
          const rid = parseItemIdFromIdRawText(idRaw);
          if (Number.isFinite(rid)) resolved = Number(rid);
        }
      }catch(_){}
    }

    /* Alphabetic spawn skins: match SPAWN_SKINS / SKINS by value or display name → numeric id. */
    if (!Number.isFinite(resolved)){
      try{
        const lists = [];
        const spawn = (window.parent && window.parent.SPAWN_SKINS) ? window.parent.SPAWN_SKINS : (window.SPAWN_SKINS || []);
        if (Array.isArray(spawn)) lists.push(spawn);
        const skinsObj = (window.parent && window.parent.SKINS) ? window.parent.SKINS : (window.SKINS || {});
        if (skinsObj && typeof skinsObj === 'object') {
          for (const cat of Object.keys(skinsObj)) {
            if (Array.isArray(skinsObj[cat])) lists.push(skinsObj[cat]);
          }
        }
        const keyLo = key.toLowerCase();
        for (let li = 0; li < lists.length && !Number.isFinite(resolved); li++) {
          const arr = lists[li];
          for (let i = 0; i < arr.length; i++) {
            const s = arr[i];
            if (!s) continue;
            const v = String(s.value || s.code || (Array.isArray(s) ? s[0] : '') || '').trim();
            const n = String(s.label || s.name || (Array.isArray(s) ? s[1] : '') || '').trim();
            const vLo = v.toLowerCase();
            const nLo = n.toLowerCase();
            if (vLo !== keyLo && nLo !== keyLo && (!isCosmetic || vLo !== keyLo)) continue;
            const sid = Number(s.skinId || s.itemId || s.id || s.partId || s.rarityId);
            if (Number.isFinite(sid) && sid > 0) { resolved = sid; break; }
            const idRaw = String(s.idRaw || s.idraw || '').trim();
            const rid = parseItemIdFromIdRawText(idRaw);
            if (Number.isFinite(rid) && rid > 0) { resolved = rid; break; }
            const brace = String(v).match(/^\{\s*(?:\d+\s*:\s*)?(\d+)\s*\}$/);
            if (brace) { resolved = Number(brace[1]); break; }
            /* Never treat Mat## as a rarity/skin id — Cosmetics_Weapon_Mat* are spawn names, not {Mat#}. */
          }
        }
      }catch(_){}
    }

    if (!Number.isFinite(resolved) && !isCosmetic){
      try{
        const arr = Array.isArray(window.ALL_PARTS) ? window.ALL_PARTS
          : (window.STX_DATASET && Array.isArray(window.STX_DATASET.ALL_PARTS) ? window.STX_DATASET.ALL_PARTS : []);
        const lk = key.toLowerCase();
        for (const p of (arr || [])){
          if (!p) continue;
          const vals = [
            String(p.code || '').trim(),
            String(p.spawnCode || '').trim(),
            String(p.spawn_id || '').trim(),
            String(p.partString || '').trim(),
            String(p.partCode || '').trim(),
            String(p.name || '').trim()
          ];
          const match = vals.some(v => String(v || '').toLowerCase() === lk);
          if (!match) continue;
          const pid = Number(p.itemId || p.id || p.partId);
          if (Number.isFinite(pid)){ resolved = Number(pid); break; }
        }
      }catch(_){}
    }

    try{ window[cacheKey] = Number.isFinite(resolved) ? Number(resolved) : ''; }catch(_){}
    return Number.isFinite(resolved) ? Number(resolved) : null;
  }

  function extractSkinRarityId(valueRaw, optionEl){
    const raw = String(valueRaw || '').trim();
    if (!raw) return null;
    // Token-form camos are not rarity-id skins.
    if (isCamoLiteralSyntax(raw)) return null;

    // Stacked mixer brace `{fam:[id1 id2…]}` — use first id for rarity sync / mainPart hint.
    const stacked = String(raw).match(/^\{\s*\d+\s*:\s*\[\s*(\d+)/);
    if (stacked) return Number(stacked[1]);

    const direct = extractSkinNumericId(raw, true, true);
    if (Number.isFinite(direct)) return Number(direct);

    try{
      const ds = optionEl && optionEl.dataset ? optionEl.dataset : null;
      const idRaw = String((ds && (ds.idRaw || ds.idraw || ds.skinIdRaw || ds.skinidraw)) || '').trim();
      let m = idRaw.match(/^\s*\d+\s*:\s*(\d+)\s*$/);
      if (m) return Number(m[1]);
      m = idRaw.match(/^\s*(\d+)\s*$/);
      if (m) return Number(m[1]);
      const sid = String((ds && (ds.skinId || ds.skinid || ds.itemId || ds.itemid)) || '').trim();
      if (/^\d+$/.test(sid)) return Number(sid);
    }catch(_){}

    const text = String(optionEl && (optionEl.textContent || optionEl.label) || '').trim();
    const base = String(optionEl && optionEl.getAttribute && optionEl.getAttribute('data-base-label') || '').trim();
    const labelHit = extractNumericIdFromLabelText(text) ?? extractNumericIdFromLabelText(base);
    if (Number.isFinite(labelHit)) return Number(labelHit);

    const spawnHit = resolveSpawnSkinRarityId(raw);
    if (Number.isFinite(spawnHit)) return Number(spawnHit);

    /* Alphabetic dropdown labels (spawn-name skins) — resolve by display name too. */
    if (text) {
      const byLabel = resolveSpawnSkinRarityId(text);
      if (Number.isFinite(byLabel)) return Number(byLabel);
    }
    if (base) {
      const byBase = resolveSpawnSkinRarityId(base);
      if (Number.isFinite(byBase)) return Number(byBase);
    }

    return null;
  }

  function extractSkinRarityToken(valueRaw, optionEl){
    const raw = String(valueRaw || '').trim();
    if (!raw) return '';
    if (isCamoLiteralSyntax(raw)) return '';
    const spawnRaw = unquoteWrappedValue(raw);
    /* Cosmetics spawn names are Skin (optional) string tokens — not rarity braces and not camo `c`. */
    if (/^Cosmetics_Weapon_/i.test(spawnRaw)){
      try{
        const ds = optionEl && optionEl.dataset ? optionEl.dataset : null;
        const idRaw = String((ds && (ds.idRaw || ds.idraw || ds.skinIdRaw || ds.skinidraw)) || '').trim();
        const opaqueDs = canonicalizeSkinBraceToken(idRaw.indexOf('{') === 0 ? idRaw : (idRaw ? `{${idRaw}}` : ''));
        if (opaqueDs) return opaqueDs;
        const pairDs = parseFamilyItemPair(idRaw);
        if (pairDs) return tokenFromPair(pairDs, null);
        const famRaw = String((ds && (ds.family || ds.familyId || ds.ccFamily)) || '').trim();
        const sidRaw = String((ds && (ds.skinId || ds.skinid || ds.itemId || ds.itemid || ds.id || ds.partId)) || '').trim();
        if (/^\d+$/.test(famRaw) && /^\d+$/.test(sidRaw)) return `{${Number(famRaw)}:${Number(sidRaw)}}`;
        if (/^\d+$/.test(sidRaw)) return `{${Number(sidRaw)}}`;
      }catch(_){}
      return '';
    }

    // Mixer / numeric skins: keep `{fam:id}` and stacked `{fam:[id1 id2]}` intact.
    const opaque = canonicalizeSkinBraceToken(raw);
    if (opaque) return opaque;

    let pair = parseFamilyItemPair(raw);
    if (pair){
      return tokenFromPair(pair, null);
    }

    try{
      const ds = optionEl && optionEl.dataset ? optionEl.dataset : null;
      const idRaw = String((ds && (ds.idRaw || ds.idraw || ds.skinIdRaw || ds.skinidraw)) || '').trim();
      const opaqueDs = canonicalizeSkinBraceToken(idRaw.indexOf('{') === 0 ? idRaw : (idRaw ? `{${idRaw}}` : ''));
      if (opaqueDs) return opaqueDs;
      pair = parseFamilyItemPair(idRaw);
      if (pair) return tokenFromPair(pair, null);

      const famRaw = String((ds && (ds.family || ds.familyId || ds.ccFamily)) || '').trim();
      const sidRaw = String((ds && (ds.skinId || ds.skinid || ds.itemId || ds.itemid || ds.id || ds.partId)) || '').trim();
      if (/^\d+$/.test(famRaw) && /^\d+$/.test(sidRaw)){
        return `{${Number(famRaw)}:${Number(sidRaw)}}`;
      }
    }catch(_){}

    try{
      const text = String(optionEl && (optionEl.textContent || optionEl.label) || '').trim();
      const base = String(optionEl && optionEl.getAttribute && optionEl.getAttribute('data-base-label') || '').trim();
      let m = text.match(/\{\s*(\d+)\s*:\s*\[([^\]]+)\]\s*\}/);
      if (!m) m = base.match(/\{\s*(\d+)\s*:\s*\[([^\]]+)\]\s*\}/);
      if (m){
        const ids = String(m[2] || '').match(/\d+/g) || [];
        if (ids.length) return `{${Number(m[1])}:[${ids.join(' ')}]}`;
      }
      m = text.match(/\{\s*(\d+)\s*:\s*(\d+)\s*\}/) || text.match(/\(\s*(\d+)\s*:\s*(\d+)\s*\)/);
      if (!m) m = base.match(/\{\s*(\d+)\s*:\s*(\d+)\s*\}/) || base.match(/\(\s*(\d+)\s*:\s*(\d+)\s*\)/);
      if (m) return `{${Number(m[1])}:${Number(m[2])}}`;
    }catch(_){}

    const rid = extractSkinRarityId(raw, optionEl);
    if (Number.isFinite(rid) && Number(rid) > 0) return `{${Number(rid)}}`;
    /* Alphabetic spawn / display-name skins (not C-code camo): resolve via label / SPAWN_SKINS. */
    try {
      const text = String(optionEl && (optionEl.textContent || optionEl.label) || '').trim();
      if (text && !/^Cosmetics_Weapon_/i.test(spawnRaw)) {
        const byName = resolveSpawnSkinRarityId(text);
        if (Number.isFinite(byName) && byName > 0) return `{${Number(byName)}}`;
      }
    } catch (_) {}
    return '';
  }

  /**
   * Preserve valid Cosmetics string tokens (incl. `"c" "Cosmetics_*"` phosphene/mat tails).
   * Only strips orphan bare Cosmetics that sit where a part brace should be when paired with
   * a broken Mat→rarity rewrite — otherwise leave the serial intact for Base85 TOK_STRING.
   * Returns { serial, changed, unresolved[] }.
   */
  function stxSanitizeCosmeticSpawnTokensInSerial(fullSerial, fallbackFamily){
    const full = String(fullSerial || '').trim();
    if (!full) return { serial: '', changed: false, unresolved: [] };
    /* Do not rewrite Cosmetics — Skin (optional) / phosphene string tokens are valid TOK_STRING.
       Earlier Mat##→{n} conversion corrupted imports and blocked Base85. */
    void fallbackFamily;
    return { serial: full, changed: false, unresolved: [] };
  }
  try { window.stxSanitizeCosmeticSpawnTokensInSerial = stxSanitizeCosmeticSpawnTokensInSerial; } catch (_) {}

  function forceFamilyOnRarityToken(tokenRaw, fallbackFamily){
    const s = String(tokenRaw || '').trim();
    if (!s) return '';
    // Never rewrite stacked mixes or explicit fam:id skin braces.
    const opaque = canonicalizeSkinBraceToken(s);
    if (opaque) return opaque;
    const pair = parseFamilyItemPair(s);
    if (!pair) return s;
    return tokenFromPair(pair, fallbackFamily);
  }

  /**
   * Cosmetics_Weapon_* → serial skin/camo form used by BE "Skin customization (`c`)".
   * Mat skins are NOT rarity braces and NOT bare quoted spawn names after ||.
   * Returns { camoToken, stringCamo, skinCode } — prefer camoToken (|"c",N|) when set.
   */
  function resolveCosmeticWeaponSkinSerial(raw){
    const key = unquoteWrappedValue(raw);
    if (!key || !/^Cosmetics_Weapon_/i.test(key)) {
      return { camoToken: '', stringCamo: '', skinCode: '' };
    }
    let camoToken = '';
    let stringCamo = '';
    let skinCode = '';

    try {
      const map = (window.parent && window.parent.__CC_SPAWN_SKIN_CAMO_MAP)
        ? window.parent.__CC_SPAWN_SKIN_CAMO_MAP
        : (window.__CC_SPAWN_SKIN_CAMO_MAP || null);
      const hit = map && (map[key] || map[key.toLowerCase()]);
      if (hit) {
        const h = String(hit).trim();
        const c = canonicalCamoToken(h);
        if (c) camoToken = c;
        else if (/^["']?c["']?\s+"/i.test(h) || /^"c"\s+"/i.test(h)) stringCamo = h.replace(/^'+|'+$/g, '');
      }
    } catch (_) {}

    if (!camoToken && !stringCamo) {
      try {
        const data = (window.parent && window.parent.SKIN_LIST_DATA) ? window.parent.SKIN_LIST_DATA : window.SKIN_LIST_DATA;
        const skins = data && Array.isArray(data.skins) ? data.skins : [];
        const lk = key.toLowerCase();
        for (let i = 0; i < skins.length; i++) {
          const row = skins[i];
          if (!row) continue;
          const id = String(row.id || row.cosmetic || '').trim();
          if (id.toLowerCase() !== lk) continue;
          const ct = String(row.camo_token || '').trim();
          const sc = String(row.skin_code || '').trim();
          if (sc && isStackedOrFamilySkinBrace(sc)) skinCode = sc.replace(/\s+/g, ' ');
          if (ct) {
            const c = canonicalCamoToken(ct);
            if (c) camoToken = c;
            else if (/^["']?c["']?\s+"/i.test(ct) || /Cosmetics_Weapon_/i.test(ct)) {
              stringCamo = ct.replace(/^"+|"+$/g, '').indexOf('"') >= 0 ? ct : `"c" "${key}"`;
            }
          }
          break;
        }
      } catch (_) {}
    }

    if (!camoToken && !stringCamo) {
      try {
        const spawn = (window.parent && window.parent.SPAWN_SKINS) ? window.parent.SPAWN_SKINS : (window.SPAWN_SKINS || []);
        const camos = (window.parent && window.parent.CAMO_TOKENS) ? window.parent.CAMO_TOKENS : (window.CAMO_TOKENS || []);
        const lk = key.toLowerCase();
        let label = '';
        for (let i = 0; i < spawn.length; i++) {
          const s = spawn[i];
          if (!s) continue;
          const v = String(s.value || s.code || '').trim();
          if (v.toLowerCase() !== lk) continue;
          label = String(s.label || s.name || '').trim();
          break;
        }
        if (label) {
          const prefix = label.indexOf(' - ') > 0 ? label.slice(0, label.indexOf(' - ')).trim() : label;
          const pLo = prefix.toLowerCase();
          const lLo = label.toLowerCase();
          for (let j = 0; j < camos.length; j++) {
            const n = String((camos[j] && camos[j].name) || '').trim().toLowerCase();
            if (n && (n === pLo || n === lLo)) {
              camoToken = canonicalCamoToken(camos[j].code) || '';
              break;
            }
          }
        }
      } catch (_) {}
    }

    if (!camoToken && !stringCamo) {
      const mat = key.match(/Mat_?0*(\d+)/i);
      if (mat) {
        const n = Number(mat[1]);
        if (n >= 1 && n <= 39) camoToken = `|"c",${111 - n}|`;
        else if (n >= 40 && n <= 70) camoToken = `|"c",${76 + n}|`;
        else if (n >= 71) stringCamo = `"c" "${key}"`;
      } else if (/Shiny_/i.test(key)) {
        stringCamo = `"c" "${key}"`;
      }
    }

    return {
      camoToken: String(camoToken || '').trim(),
      stringCamo: String(stringCamo || '').trim(),
      skinCode: String(skinCode || '').trim()
    };
  }
  try { window.resolveCosmeticWeaponSkinSerial = resolveCosmeticWeaponSkinSerial; } catch (_) {}

  /**
   * Inject Skin brace / Camo (`c`) from the Simple dropdowns into an existing || serial.
   * Used when the live serial is frozen (__fullDeserialized) or rebuild would drop the selection.
   * Order after ||: [pearl?] rarity, Skin brace, …parts…, spawn, camo.
   */
  function stxOverlaySkinCamoOnDeserialized(fullSerial, scIn){
    const full = String(fullSerial || '').trim();
    const dbl = full.indexOf('||');
    if (dbl < 0) return full;
    const sc = scIn || getSelectedWeaponSkinAndCamo();
    if (!sc) return full;
    const skinBrace = String(sc.rarityToken || '').trim();
    const camoTok = String(sc.camoToken || '').trim();
    const spawnTok = String(sc.spawnToken || '').trim();
    if (!skinBrace && !camoTok && !spawnTok) return full;

    const head = full.slice(0, dbl + 2).replace(/\s+$/, '');
    const toks = (typeof parseImportTokenList === 'function')
      ? parseImportTokenList(full)
      : [];
    const skinNorm = skinBrace.replace(/\s+/g, '');
    const skinIsMix = !!(skinBrace && /^\{\s*\d+\s*:\s*\[/.test(skinBrace));
    const isSimpleBrace = (t)=>/^\{\s*\d+\s*:\s*\d+\s*\}$/.test(t) || /^\{\s*\d+\s*\}$/.test(t);
    const isElemBrace = (t)=>/^\{\s*1\s*:\s*\d+\s*\}$/.test(t);
    const out = [];
    for (let i = 0; i < toks.length; i++) {
      const t = String(toks[i] || '').trim();
      if (!t) continue;
      if (camoTok && canonicalCamoToken(t)) continue;
      if (spawnTok && (/^"c"\s+"/i.test(t) || /^Cosmetics_Weapon_/i.test(unquoteWrappedValue(t)))) continue;
      if (skinBrace && t.replace(/\s+/g, '') === skinNorm) continue;
      /* Drop prior skin-stack mixes when applying a new Skin brace / mix. */
      if (skinBrace && /^\{\s*\d+\s*:\s*\[/.test(t) && !/^\{\s*1\s*:/.test(t)) continue;
      out.push(t);
    }
    if (skinBrace) {
      if (skinIsMix) {
        /* Stacked mixes own the rarity slot — lead the tail (after an optional pearl). */
        let mixAt = 0;
        if (out.length && isSimpleBrace(out[0]) && !isElemBrace(out[0])) {
          const looksPearl = stxLooksLikePearlOverrideLeadTok(out[0]);
          if (looksPearl) mixAt = 1;
        }
        const replaceRarity = mixAt < out.length && isSimpleBrace(out[mixAt]) && !isElemBrace(out[mixAt]);
        out.splice(mixAt, replaceRarity ? 1 : 0, skinBrace);
      } else {
        /* Additive `{fam:id}`: insert after rarity, or after pearl+rarity when pearl leads. */
        let insertAt = 0;
        if (out.length && isSimpleBrace(out[0]) && !isElemBrace(out[0])) {
          const looksPearl = stxLooksLikePearlOverrideLeadTok(out[0]);
          if (looksPearl && out.length > 1 && isSimpleBrace(out[1]) && !isElemBrace(out[1])) {
            insertAt = 2; /* pearl, rarity, ← skin */
          } else {
            insertAt = 1; /* rarity, ← skin */
          }
        }
        out.splice(insertAt, 0, skinBrace);
      }
    }
    if (spawnTok) out.push(spawnTok);
    if (camoTok) out.push(camoTok);
    let tail = out.join(' ').trim();
    if (tail && !/\|\s*$/.test(tail)) tail += '|';
    return head + (tail ? ' ' + tail : '');
  }
  try { window.stxOverlaySkinCamoOnDeserialized = stxOverlaySkinCamoOnDeserialized; } catch (_) {}

  function getSelectedWeaponSkinAndCamo(){
    const skinSel = $('skinSelect');
    const camoSel = $('camoSelect');
    const skinRaw = String((skinSel && skinSel.value) || '').trim();
    const skinOpt = (skinSel && skinSel.selectedOptions && skinSel.selectedOptions[0]) ? skinSel.selectedOptions[0] : null;
    const camoRaw = String((camoSel && camoSel.value) || '').trim();

    const spawnKey = unquoteWrappedValue(skinRaw);
    let spawnToken = '';
    let cosmeticCamo = '';
    let cosmeticStringCamo = '';
    let cosmeticSkinCode = '';
    if (/^Cosmetics_Weapon_/i.test(spawnKey)) {
      const resolved = resolveCosmeticWeaponSkinSerial(spawnKey);
      cosmeticCamo = resolved.camoToken || '';
      cosmeticStringCamo = resolved.stringCamo || '';
      cosmeticSkinCode = resolved.skinCode || '';
      /* Only keep a quoted spawn if we could not map to `c` form (should be rare). */
      if (!cosmeticCamo && !cosmeticStringCamo) spawnToken = `"${spawnKey}"`;
    }
    const rarityId = (cosmeticCamo || cosmeticStringCamo || spawnToken)
      ? (cosmeticSkinCode ? extractSkinRarityId(cosmeticSkinCode, null) : null)
      : extractSkinRarityId(skinRaw, skinOpt);
    let rarityToken = (cosmeticCamo || cosmeticStringCamo || spawnToken)
      ? (cosmeticSkinCode || '')
      : extractSkinRarityToken(skinRaw, skinOpt);
    /* Skin (optional) Cosmetics win over Camo dropdown when they resolve to `c`. */
    let camoToken = cosmeticCamo || canonicalCamoToken(camoRaw);
    if (!camoToken && cosmeticStringCamo) {
      /* string form lives in spawnToken slot for tail assembly */
      spawnToken = cosmeticStringCamo;
    }
    return {
      skinRaw,
      camoRaw,
      spawnToken,
      rarityId: Number.isFinite(rarityId) ? Number(rarityId) : null,
      rarityToken: String(rarityToken || '').trim(),
      camoToken: String(camoToken || '').trim()
    };
  }

  function getSelectedMainPartFromUi(){
    const sel = $('mainPart');
    const key = String((sel && sel.value) || '').trim();
    if (!key) return null;
    try{
      const map = state && state.__mainPartByOptionKey;
      if (map && typeof map.get === 'function'){
        const hit = map.get(key);
        if (hit) return hit;
      }
    }catch(_){}
    if (/^idx:\s*-?\d+$/i.test(key)){
      const idx = Number(key.replace(/^idx:\s*/i, ''));
      if (Number.isFinite(idx)) return getAllParts()[idx] || null;
    }
    if (/^-?\d+$/.test(key)){
      const idx = Number(key);
      if (Number.isFinite(idx)) return getAllParts()[idx] || null;
    }
    return state.mainPart || null;
  }

  function findMainPartKeyForSkinRarityId(rarityId, preferredFamilyId){
    const rid = Number(rarityId);
    if (!Number.isFinite(rid)) return '';
    const map = state && state.__mainPartByOptionKey;
    if (!map || typeof map.entries !== 'function') return '';

    const famHint = Number(preferredFamilyId);
    let fallback = '';
    for (const [k, p] of map.entries()){
      if (!p) continue;
      if (String((p.partType || '')).trim().toLowerCase() !== 'rarity') continue;
      const pid = partItemIdOf(p);
      if (!Number.isFinite(pid) || Number(pid) !== rid) continue;

      if (Number.isFinite(famHint)){
        const pf = partFamilyIdOf(p);
        if (Number.isFinite(pf) && Number(pf) === famHint) return String(k);
      }
      if (!fallback) fallback = String(k);
    }
    return fallback;
  }

  function syncMainPartFromSkinSelection(){
    const it = String(state.itemType || '').trim();
    if (it !== 'Weapon' && !stxSimpleBuilderItemTypeIsHeavyUi(it)) return false;
    const mainSel = $('mainPart');
    if (!mainSel) return false;

    const skinSel = getSelectedWeaponSkinAndCamo();
    const skinTok = String((skinSel && skinSel.rarityToken) || '').trim();
    /* Single `{fam:id}` Skin brace is additive after rarity — never rewrite mainPart/rarity.
       Only stacked mixes `{fam:[id1 id2…]}` own the rarity slot. */
    if (!skinTok || !/^\{\s*\d+\s*:\s*\[/.test(skinTok)) return false;

    const rid = Number(skinSel && skinSel.rarityId);
    if (!Number.isFinite(rid)) return false;

    let mapReady = !!(state && state.__mainPartByOptionKey && typeof state.__mainPartByOptionKey.entries === 'function' && state.__mainPartByOptionKey.size);
    if (!mapReady){
      if (__mainPartLazyWired && !__mainPartHydrated) return false;
      invokeRefreshMainPart(true);
      mapReady = !!(state && state.__mainPartByOptionKey && typeof state.__mainPartByOptionKey.entries === 'function' && state.__mainPartByOptionKey.size);
    }
    if (!mapReady) return false;

    let famHint = null;
    const parsed = parseFamilyItemPair(skinTok);
    if (parsed && Number.isFinite(Number(parsed.family))) famHint = Number(parsed.family);
    if (!Number.isFinite(famHint)){
      const base = getSelectedBaseItem();
      if (base && Number.isFinite(Number(base.familyId))) famHint = Number(base.familyId);
    }

    const targetKey = findMainPartKeyForSkinRarityId(rid, famHint);
    if (!targetKey) return false;

    const currentMain = getSelectedMainPartFromUi();
    const currentRid = partItemIdOf(currentMain);
    const currentIsRarity = String((currentMain && currentMain.partType) || '').trim().toLowerCase() === 'rarity';
    const currentKey = String(mainSel.value || '').trim();
    if (currentIsRarity && Number.isFinite(currentRid) && Number(currentRid) === rid && currentKey === String(targetKey)){
      return false;
    }

    if (!Array.from(mainSel.options || []).some(o => String(o.value || '').trim() === String(targetKey))) return false;
    // Soft-apply stacked-mix rarity onto mainPart — do NOT dispatch `change` (that wipes slots/extras + imported serial).
    mainSel.value = String(targetKey);
    try {
      const map = state && state.__mainPartByOptionKey;
      const main = (map && typeof map.get === 'function') ? map.get(String(targetKey)) : null;
      if (main) {
        state.mainPart = main;
        if (!state.slots) state.slots = {};
        if (String(main.partType || '').trim().toLowerCase() === 'rarity' ||
            /(?:^|[._])comp_0[1-6]_/i.test(String(main.code || ''))) {
          state.slots.rarity = main;
        }
      }
    } catch (_e) {}
    try { clearImportedOutputLock(); } catch (_e2) {}
    try { syncMainPartPreview(); } catch (_e3) {}
    refreshOutputs(true);
    return true;
  }

  function syncCamoOptionsFromParent(opts){
    const skipTooltips = !!(opts && opts.skipTooltips);
    const skipSkinsCatalog = !!(opts && opts.skipSkinsCatalog);
    const sel = $('camoSelect');
    if (!sel) return;

    const parentDoc = (window.parent && window.parent.document)
      ? window.parent.document
      : document;
    const parentSel = parentDoc
      ? parentDoc.getElementById('skin')
      : null;
    const parentCamoSel = parentDoc ? parentDoc.getElementById('skinCamo') : null;

    const keep = [];
    const seen = new Set();
    const push = (tok, labelRaw)=>{
      const token = canonicalCamoToken(tok);
      if (!token) return;
      const key = token.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      let label = String(labelRaw || '').trim();
      label = label
        .replace(/<[^>]*>/g, ' ')
        .replace(/\{\s*\d+\s*:\s*\d+\s*\}/g, ' ')
        .replace(/\(\s*\d+\s*:\s*\d+\s*\)/g, ' ')
        .replace(/\|\s*["']?c["']?\s*,\s*\d+\s*\|/gi, ' ')
        .replace(/\[\s*token\s*\]/gi, ' ')
        .replace(/\s{2,}/g, ' ')
        .trim();
      if (!label){
        const m = token.match(/\|\s*["']?c["']?\s*,\s*(\d+)\s*\|/i);
        label = m ? `Camo ${m[1]}` : 'Camo';
      }
      if (label.indexOf(token) < 0) label = `${label} · ${token}`;
      keep.push({ value: token, label });
    };

    try{
      if (parentSel && parentSel.options){
        Array.from(parentSel.options || []).forEach(function(o){
          if (!o) return;
          const v = String(o.value || '').trim();
          const l = String(o.getAttribute('data-base-label') || o.textContent || o.label || '').trim();
          if (isCamoLiteralSyntax(v) || /\|\s*["']?c["']?\s*,\s*\d+\s*\|/i.test(l) || /\b["']?c["']?\s*,\s*\d+\b/i.test(l) || /\[token\]/i.test(l)){
            push(v, l);
          }
        });
      }
    }catch(_){}

    // If the host page has a dedicated camo dropdown, mirror it directly.
    try{
      if (parentCamoSel && parentCamoSel.options){
        Array.from(parentCamoSel.options || []).forEach(function(o){
          if (!o) return;
          const v = String(o.value || '').trim();
          const l = String(o.getAttribute('data-base-label') || o.textContent || o.label || '').trim();
          if (isCamoLiteralSyntax(v) || /\|\s*["']?c["']?\s*,\s*\d+\s*\|/i.test(l) || /\b["']?c["']?\s*,\s*\d+\b/i.test(l) || /\[token\]/i.test(l)){
            push(v, l);
          }
        });
      }
    }catch(_){}

    const skinsSource = (() => {
      try{
        return (window.parent && window.parent.SKINS) ? window.parent.SKINS : (window.SKINS || null);
      }catch(_){ return null; }
    })();
    try{
      if (skinsSource && typeof skinsSource === 'object' && !skipSkinsCatalog){
        for (const cat of Object.keys(skinsSource)){
          const arr = skinsSource[cat];
          if (!Array.isArray(arr)) continue;
          for (const sk of arr){
            if (!sk) continue;
            const v = String(sk.code || '').trim();
            const l = String(sk.name || sk.label || '').trim();
            if (isCamoLiteralSyntax(v) || /\|\s*["']?c["']?\s*,\s*\d+\s*\|/i.test(l) || /\b["']?c["']?\s*,\s*\d+\b/i.test(l) || /\[token\]/i.test(l)){
              push(v, l);
            }
          }
        }
      }
    }catch(_){}

    /* Named weapon mats from SPAWN→camo map (Snowfall, Afterburn, …). */
    try{
      const map = (window.parent && window.parent.__CC_SPAWN_SKIN_CAMO_MAP)
        ? window.parent.__CC_SPAWN_SKIN_CAMO_MAP
        : (window.__CC_SPAWN_SKIN_CAMO_MAP || {});
      const spawn = (window.parent && window.parent.SPAWN_SKINS) ? window.parent.SPAWN_SKINS : (window.SPAWN_SKINS || []);
      if (Array.isArray(spawn)) {
        for (const s of spawn) {
          if (!s) continue;
          const v = String(s.value || s.code || '').trim();
          if (!/^Cosmetics_Weapon_Mat/i.test(v)) continue;
          const tok = String(map[v] || map[v.toLowerCase()] || '').trim();
          if (!tok) continue;
          const lbl = String(s.label || s.name || '').trim();
          push(tok, lbl || tok);
        }
      }
      const camos = (window.parent && window.parent.CAMO_TOKENS) ? window.parent.CAMO_TOKENS : (window.CAMO_TOKENS || []);
      if (Array.isArray(camos)) {
        for (const nc of camos) {
          if (!nc || !nc.code) continue;
          push(nc.code, String(nc.name || '').trim() || nc.code);
        }
      }
    }catch(_){}

    // Fallback: if no literal token entries exist in this dataset, expose token aliases from numeric IDs.
    if (!keep.length){
      const pushAliasFromNumeric = (valueRaw, labelRaw)=>{
        const value = unquoteWrappedValue(valueRaw);
        if (!value || /^Cosmetics_Weapon_/i.test(value)) return;
        const label = String(labelRaw || '').trim();
        let id = extractSkinNumericId(value, true, true);
        if (!Number.isFinite(id)) id = extractNumericIdFromLabelText(label);
        if (!Number.isFinite(id)) return;
        push(`|"c",${Number(id)}|`, label || `Camo ${Number(id)}`);
      };
      try{
        if (parentSel && parentSel.options){
          Array.from(parentSel.options || []).forEach(function(o){
            if (!o) return;
            pushAliasFromNumeric(String(o.value || '').trim(), String(o.getAttribute('data-base-label') || o.textContent || o.label || '').trim());
          });
        }
      }catch(_){}
      try{
        if (skinsSource && typeof skinsSource === 'object' && !skipSkinsCatalog){
          for (const cat of Object.keys(skinsSource)){
            const arr = skinsSource[cat];
            if (!Array.isArray(arr)) continue;
            for (const sk of arr){
              if (!sk) continue;
              pushAliasFromNumeric(String(sk.code || '').trim(), String(sk.name || sk.label || '').trim());
            }
          }
        }
      }catch(_){}
      try{
        const extras = (window.parent && window.parent.__CC_EXTRA_NUMERIC_SKINS) ? window.parent.__CC_EXTRA_NUMERIC_SKINS : (window.__CC_EXTRA_NUMERIC_SKINS || []);
        if (Array.isArray(extras)){
          for (const ex of extras){
            if (!ex) continue;
            const code = Array.isArray(ex) ? ex[0] : ex.code;
            const name = Array.isArray(ex) ? ex[1] : (ex.name || ex.label);
            pushAliasFromNumeric(String(code || '').trim(), String(name || '').trim());
          }
        }
      }catch(_){}
    }

    const cur = String(sel.value || '').trim();
    sel.innerHTML = '<option value="">-- None --</option>';
    for (const row of keep){
      const o = document.createElement('option');
      o.value = row.value;
      o.textContent = row.label;
      if (typeof window.skinTooltipText === 'function' && !skipTooltips) { const t = window.skinTooltipText(row.value, row.label); if (t) o.title = t; }
      sel.appendChild(o);
    }
    if (cur && Array.from(sel.options || []).some(o => String(o.value || '').trim() === cur)){
      sel.value = cur;
    }
    try { stxSyncCustomSelectIfWrapped(sel); } catch (_) {}
  }

  function syncSkinOptionsFromParent(opts){
    const skipTooltips = !!(opts && opts.skipTooltips);
    const sel = $('skinSelect');
    if (!sel) {
      if (opts && typeof opts.onDone === 'function') opts.onDone();
      return;
    }

    const parentDoc = (window.parent && window.parent.document)
      ? window.parent.document
      : document;
    const parentSel = parentDoc ? parentDoc.getElementById('skin') : null;

    const seen = new Set();
    const grouped = {
      spawn: [],
      mixes: [],
      numeric: [],
      phosphene: []
    };
    const cleanSkinLabel = (labelRaw, valueRaw)=>{
      const value = String(valueRaw || '').trim();
      const id = extractSkinNumericId(value, true, true);
      let t = String(labelRaw || '').trim();
      t = t.replace(/<[^>]*>/g, ' ');
      t = t.replace(/\(\s*\{\s*\d+\s*:\s*(?:\[\s*\d+(?:\s+\d+)*\s*\]|\d+)\s*\}\s*\)/g, ' ');
      t = t.replace(/\{\s*\d+\s*:\s*(?:\[\s*\d+(?:\s+\d+)*\s*\]|\d+)\s*\}/g, ' ');
      t = t.replace(/\(\s*\d+\s*:\s*(?:\[\s*\d+(?:\s+\d+)*\s*\]|\d+)\s*\)/g, ' ');
      t = t.replace(/\|\s*["']?c["']?\s*,\s*\d+\s*\|/gi, '');
      t = t.replace(/\bid\s*[:#-]?\s*\d+\b/gi, '');
      t = t.replace(/\b\d+\s*:\s*\d+\b/g, '');
      t = t.replace(/\[\s*token\s*\]/gi, '');
      t = t.replace(/\(\s*\)/g, '');
      t = t.replace(/\s{2,}/g, ' ').trim();
      if (!t){
        if (isPhospheneLabel(labelRaw) || isPhospheneLabel(value)) t = 'Phosphene';
        else if (hasSpawnCode(labelRaw, value) || /^Cosmetics_Weapon_/i.test(value)) t = 'Spawn Skin';
        else t = Number.isFinite(id) ? `Skin ${id}` : 'Skin';
      }
      return t;
    };
    const classifyGroup = (valueRaw, labelRaw)=>{
      const value = String(valueRaw || '').trim();
      const label = String(labelRaw || '').trim();
      if (isPhospheneLabel(label) || isPhospheneLabel(value)) return 'phosphene';
      if (hasSpawnCode(label, value) || /^Cosmetics_Weapon_/i.test(value)) return 'spawn';
      if (/^\{\s*\d+\s*:\s*\[/.test(value) || /custom\s*mix|auto\s+\d+-way\s+mix/i.test(label)) return 'mixes';
      return 'numeric';
    };
    const pushEntry = (value, label, groupKey)=>{
      const v = String(value || '').trim();
      if (!v) return;
      const l = String(label || v).trim() || v;
      const key = v.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      let sid = extractSkinRarityId(v, null);
      if (!Number.isFinite(sid)) sid = resolveSpawnSkinRarityId(v);
      if (!Number.isFinite(sid) && l) sid = resolveSpawnSkinRarityId(l);
      const bucket = grouped[groupKey] || grouped.numeric;
      bucket.push({ value: v, label: l, skinId: Number.isFinite(sid) ? Number(sid) : null });
    };
    const addFromRaw = (valueRaw, labelRaw)=>{
      const raw = String(valueRaw || '').trim();
      if (!raw) return;
      if (isCamoLiteralSyntax(raw)) return; // camo tokens live in camoSelect only
      /* Cosmetics_Weapon_* are profile unlock IDs — not Skin (optional) item options. */
      if (/^Cosmetics_Weapon_/i.test(unquoteWrappedValue(raw))) return;
      const label = String(labelRaw || '').trim();
      if (hasSpawnCode(label, raw) && !/^\{\s*\d+\s*:/.test(raw)) return;
      const cleaned = cleanSkinLabel(label || raw, raw);
      const group = classifyGroup(raw, label || cleaned);
      if (group === 'spawn' || group === 'phosphene') return;
      pushEntry(raw, cleaned || raw, group);
    };

    try{
      if (parentSel && parentSel.options){
        for (const opt of Array.from(parentSel.options || [])){
          addFromRaw(opt.value, opt.textContent);
        }
      }
    }catch(_){}

    // Fallback: pull numeric skins from extra numeric registry.
    try{
      const extras = (window.parent && window.parent.__CC_EXTRA_NUMERIC_SKINS)
        ? window.parent.__CC_EXTRA_NUMERIC_SKINS
        : (window.__CC_EXTRA_NUMERIC_SKINS || []);
      if (Array.isArray(extras)){
        for (const ex of extras){
          if (!ex) continue;
          if (Array.isArray(ex)) addFromRaw(ex[0], ex[1] || '');
          else addFromRaw(ex.code, ex.name || ex.label || '');
        }
      }
    }catch(_){}

    /* Do not load SPAWN_SKINS into Skin (optional) — Mat/Shiny Cosmetics go on Camo as |"c",N|. */
    const skipSkinsCatalog = !!(opts && opts.skipSkinsCatalog);
    const curRaw = String(sel.value || '').trim();
    const cur = canonicalSkinToken(curRaw, true, true) || curRaw;
    const tokenTransfer = isCamoTokenSyntax(curRaw) ? canonicalCamoToken(curRaw) : '';

    function renderSkinDom() {
      sel.innerHTML = '<option value="">-- None --</option>';
      const sortRows = (rows)=>rows.sort((a,b)=>String(a.label || '').localeCompare(String(b.label || ''), undefined, { numeric:true, sensitivity:'base' }));
      sortRows(grouped.spawn);
      sortRows(grouped.mixes);
      sortRows(grouped.numeric);
      sortRows(grouped.phosphene);
      const appendGroup = (title, rows, done)=>{
        if (!Array.isArray(rows) || !rows.length) {
          if (typeof done === 'function') done();
          return;
        }
        const og = document.createElement('optgroup');
        og.label = title;
        sel.appendChild(og);
        const addOption = (row)=>{
          const o = document.createElement('option');
          o.value = row.value;
          o.textContent = row.label;
          try{
            if (Number.isFinite(row.skinId)) o.setAttribute('data-skin-id', String(row.skinId));
            o.setAttribute('data-base-label', String(row.label || '').trim());
          }catch(_){}
          if (typeof window.skinTooltipText === 'function' && !skipTooltips) { const t = window.skinTooltipText(row.value, row.label); if (t) o.title = t; }
          og.appendChild(o);
        };
        if (typeof window.stxRunInSlices === 'function' && rows.length > 64) {
          window.stxRunInSlices(rows, 48, function (start, end) {
            for (let ri = start; ri < end; ri++) addOption(rows[ri]);
          }, done);
        } else {
          for (const row of rows) addOption(row);
          if (typeof done === 'function') done();
        }
      };
      const finishSkinDom = ()=>{
        /* Drop leftover Cosmetics_Weapon_* selections — those are Camo options now. */
        let want = curRaw;
        if (/^Cosmetics_Weapon_/i.test(unquoteWrappedValue(want))) want = '';
        if (want && Array.from(sel.options).some(o=>o.value===want)) sel.value = want;
        else if (cur && !/^Cosmetics_Weapon_/i.test(unquoteWrappedValue(cur)) && Array.from(sel.options).some(o=>o.value===cur)) sel.value = cur;
        else sel.value = '';
        syncCamoOptionsFromParent({ skipTooltips: skipTooltips, skipSkinsCatalog: skipSkinsCatalog });
        if (tokenTransfer && $('camoSelect') && Array.from(($('camoSelect').options || [])).some(o => String(o.value || '').trim() === tokenTransfer)){
          $('camoSelect').value = tokenTransfer;
        }
        try {
          stxSyncCustomSelectIfWrapped(sel);
          const camoEl = $('camoSelect');
          if (camoEl) stxSyncCustomSelectIfWrapped(camoEl);
        } catch (_) {}
        if (opts && typeof opts.onDone === 'function') opts.onDone();
      };
      appendGroup('Custom Mixes', grouped.mixes, ()=>{
        appendGroup('Numeric ID Skins', grouped.numeric, finishSkinDom);
      });
    }

    function collectSkinsCatalogChunked(done) {
      if (skipSkinsCatalog) {
        if (typeof done === 'function') done();
        return;
      }
      let skinsSource = null;
      try{
        skinsSource = (window.parent && window.parent.SKINS) ? window.parent.SKINS : (window.SKINS || null);
      }catch(_){ skinsSource = null; }
      if (!skinsSource || typeof skinsSource !== 'object') {
        if (typeof done === 'function') done();
        return;
      }
      const cats = Object.keys(skinsSource);
      let catIdx = 0;
      let skIdx = 0;
      const SLICE = 180;
      function step() {
        let budget = SLICE;
        try {
          while (catIdx < cats.length && budget > 0) {
            const arr = skinsSource[cats[catIdx]];
            if (!Array.isArray(arr)) {
              catIdx++;
              skIdx = 0;
              continue;
            }
            while (skIdx < arr.length && budget > 0) {
              const sk = arr[skIdx++];
              if (sk) addFromRaw(sk.code, sk.name || sk.label || '');
              budget--;
            }
            if (skIdx >= arr.length) {
              catIdx++;
              skIdx = 0;
            }
          }
        } catch (_) {}
        if (catIdx < cats.length) {
          if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(step);
          else setTimeout(step, 0);
        } else if (typeof done === 'function') {
          if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(done);
          else done();
        }
      }
      step();
    }

    // Phase 1: render spawn/extras/parent options immediately so custom dropdowns aren't empty while SKINS catalog chunks in.
    renderSkinDom();
    if (!skipSkinsCatalog) {
      collectSkinsCatalogChunked(renderSkinDom);
    }
  }

  
function computeFullDeserializedCode(){
  if (state.mainPart && state.mainPart.__fullDeserialized){
    let frozen = String(state.mainPart.__fullDeserialized).trim();
    try {
      const scFrozen = getSelectedWeaponSkinAndCamo();
      if (scFrozen && (scFrozen.rarityToken || scFrozen.camoToken || scFrozen.spawnToken || scFrozen.skinRaw || scFrozen.camoRaw)) {
        frozen = stxOverlaySkinCamoOnDeserialized(frozen, scFrozen);
      }
    } catch (_) {}
    return frozen;
  }
  const guided = getGuidedContext();
  const useGuided = guided && guided.itemType;
  let base = getSelectedBaseItem();
  if (!base) {
    try {
      const existing = String(($('outCode') && $('outCode').value) || '').trim();
      const dblEx = existing.indexOf('||');
      if (dblEx >= 0) {
        const prefixEx = existing.slice(0, dblEx).trim();
        const mEx = prefixEx.match(/^\s*(\d+)\s*[,\|]/) || prefixEx.match(/^\s*(\d+)/);
        if (mEx) base = { familyId: Number(mEx[1]), itemId: null };
      }
    } catch (_) {}
  }
  if (!base) return '';
  const level = useGuided ? (Number(guided.level) || 60) : Number(state.level || 60);

  /* Prefer explicit Item Type for tail packing: imports can mis-set detectedCategory to Repkit when `repair_kit.*`
     perk rows appear on Enhancement builds — those still need `{243:[…]}` consecutive packing. */
  const outputCategory = String(state.itemType || state.detectedCategory || '').trim();
  const orderedPartObjects = computeOrderedParts();
  const orderedParts = orderedPartObjects.map(p => tokenForPart(p) || normCode(p.code)).filter(Boolean);
  const importedExtras = Array.isArray(state.extras)
    ? state.extras.map(x => {
        if (x && typeof x === 'object' && x.tok) return String(x.tok).trim();
        return String(x || '').trim();
      }).filter(Boolean)
    : [];
  // Preserve unresolved imported tokens (e.g. {7:[4 4 4 4 64]}) in final code output.
  const outputTokens = orderedParts.concat(importedExtras);

  // Rarity helpers (tier for filtering; emits rarity token after ||)
  const selectedTier = getSelectedRarityTier();
  const useTierFilter = rarityTierFilterActiveForCurrentContext();
  const baseFamilyId = Number(base && base.familyId);
  let rarityRows = getRarityRowsForCurrentContext();
  if (useTierFilter && Number.isFinite(selectedTier)){
    rarityRows = rarityRows.filter(r => rarityTierFromItemTypeString(r && r.itemTypeString, r) === selectedTier);
  }
  let rarityRow = null;
  if (Number.isFinite(baseFamilyId)){
    const byFam = rarityRows.filter(r => Number(r && r.familyId) === baseFamilyId);
    if (byFam.length){
      rarityRow = byFam.find(r => !String(r && r.legendaryName || '').trim()) || byFam[0];
    }
  }
  if (!rarityRow){
    rarityRow = rarityRows.find(r => !String(r && r.legendaryName || '').trim()) || rarityRows[0] || null;
  }

  const rarityTierId = Number.isFinite(selectedTier)
    ? selectedTier
    : (rarityRow ? rarityTierFromItemTypeString(rarityRow.itemTypeString, rarityRow) : null);
  let rarityItemId = rarityRow && Number.isFinite(Number(rarityRow.itemId))
    ? Number(rarityRow.itemId)
    : (base && Number.isFinite(Number(base.itemId)) ? Number(base.itemId) : null);
    const mainPartIsRarity = String((state.mainPart && state.mainPart.partType) || '').trim().toLowerCase() === 'rarity';
    const mainPartRarityItemId = mainPartIsRarity ? partItemIdOf(state.mainPart || null) : null;
    if (Number.isFinite(mainPartRarityItemId)){
      rarityItemId = Number(mainPartRarityItemId);
    }
    const raritySlotPartRaw = state && state.slots ? state.slots.rarity : null;
    const raritySlotPart = Array.isArray(raritySlotPartRaw) ? (raritySlotPartRaw[0] || null) : raritySlotPartRaw;
    const raritySlotIsRarity = String((raritySlotPart && raritySlotPart.partType) || '').trim().toLowerCase() === 'rarity';
    const raritySlotItemId = raritySlotIsRarity ? partItemIdOf(raritySlotPart || null) : null;
    if (Number.isFinite(raritySlotItemId)){
      rarityItemId = Number(raritySlotItemId);
    }
  if (String(outputCategory) === 'Class Mod') {
    try {
      const mainPt = String((state.mainPart && state.mainPart.partType) || '').trim().toLowerCase();
      const nameSrc = (mainPt === 'rarity')
        ? (state.slots && state.slots.namePart)
        : state.mainPart;
      const spawnLo = String(normCode((nameSrc && (nameSrc.code || nameSrc.spawnCode)) || '') || '').toLowerCase();
      const looksLegendaryBody = /leg_body_|comp_05_legendary_/.test(spawnLo);
      const tierNow = Number.isFinite(selectedTier) ? selectedTier : rarityTierId;
      if (nameSrc && (looksLegendaryBody || tierNow === 4)) {
        const paired = stxResolveClassModPairedRarityItemId(
          nameSrc,
          state.manufacturer || state.classmodClass || ''
        );
        if (Number.isFinite(paired)) rarityItemId = Number(paired);
      }
      /* Pearl override only prepends a random pearl rarity id — never rewrite rarityItemId (keeps Bio-Robot `{26}` etc.). */
      if (tierNow === 5
          && !isStxSimplePearlOverrideChecked()
          && !(Number.isFinite(rarityItemId) && rarityItemId >= 51 && rarityItemId <= 60)) {
        rarityItemId = 54;
      }
    } catch (_eCmPair) { /* keep prior rarityItemId */ }
  }
  const isWeapon = (state.itemType === 'Weapon') || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType) || (state.detectedCategory === 'Weapon');
  const weaponSkinSelection = isWeapon ? getSelectedWeaponSkinAndCamo() : null;
  /* Skin brace from dropdown — keep separate from rarity so selecting a skin ADDS it, not only replaces rarity. */
  let skinBraceTok = '';
  if (weaponSkinSelection && weaponSkinSelection.rarityToken) {
    skinBraceTok = String(forceFamilyOnRarityToken(weaponSkinSelection.rarityToken, baseFamilyId) || '').trim();
    if (!skinBraceTok) skinBraceTok = String(weaponSkinSelection.rarityToken || '').trim();
  }
  const skinIsStackedMix = !!(skinBraceTok && /^\{\s*\d+\s*:\s*\[/.test(skinBraceTok));
  /* Stacked mixes own the rarity slot; single {fam:id} skins append after rarity. */
  let skinRarityToken = '';
  if (skinIsStackedMix) {
    skinRarityToken = skinBraceTok;
    skinBraceTok = '';
  }
  if (weaponSkinSelection && Number.isFinite(weaponSkinSelection.rarityId) && Number(weaponSkinSelection.rarityId) > 0 && skinIsStackedMix){
    const skinRid = Number(weaponSkinSelection.rarityId);
    rarityItemId = skinRid;
    if (!String(skinRarityToken || '').trim()){
      skinRarityToken = tokenFromPair({ family: baseFamilyId, itemId: skinRid }, baseFamilyId);
    } else {
      skinRarityToken = forceFamilyOnRarityToken(skinRarityToken, baseFamilyId);
    }
  }
  const rarityItemIdStr = Number.isFinite(rarityItemId) ? String(rarityItemId) : '';
  function tokenIdOnlyForRarity(tok){
    const s = String(tok || '').trim();
    let m = s.match(/^\{\s*\d+\s*:\s*(\d+)\s*\}$/);
    if (m && m[1]) return String(m[1]);
    m = s.match(/^\{\s*(\d+)\s*\}$/);
    if (m && m[1]) return String(m[1]);
    return '';
  }
  const orderedHasRarity = !!(rarityItemIdStr && outputTokens.some(t => tokenIdOnlyForRarity(t) === rarityItemIdStr));
  const rarityTokRaw = String(skinRarityToken || '').trim()
    || (Number.isFinite(rarityItemId) ? `{${rarityItemId}}` : '');
  // Skin braces (incl. mixer stacks) must not compact to bare `{id}` — same TypeID as the gun
  // would turn `{3:79}` / `{3:[78 76]}` into `{79}` and break stacked mixes.
  let rarityTok = rarityTokRaw;
  if (rarityTokRaw && !canonicalizeSkinBraceToken(rarityTokRaw) && !/^\{\s*\d+\s*:\s*\[/.test(rarityTokRaw)){
    const rarityTokNorm = normalizeIdTokensForBaseFamilyWithPrefs([rarityTokRaw], baseFamilyId);
    rarityTok = Array.isArray(rarityTokNorm) && rarityTokNorm.length
      ? String(rarityTokNorm[0] || '').trim()
      : rarityTokRaw;
  } else if (canonicalizeSkinBraceToken(rarityTokRaw)){
    rarityTok = canonicalizeSkinBraceToken(rarityTokRaw);
  }
  if (skinBraceTok) {
    const opaqueSkin = canonicalizeSkinBraceToken(skinBraceTok) || skinBraceTok;
    skinBraceTok = opaqueSkin;
    /* Don't duplicate if skin brace is already the rarity token. */
    if (rarityTok && rarityTok.replace(/\s+/g, '') === skinBraceTok.replace(/\s+/g, '')) {
      skinBraceTok = '';
    }
  }
  const __rarityTokN = String(rarityTok || '').replace(/\s+/g,'').trim();
  const __rarityBeforePearlId = (() => {
    try {
      const n = Number(state && state.__stxRarityItemIdBeforePearl);
      return Number.isFinite(n) ? String(n) : '';
    } catch (_e) { return ''; }
  })();
  const isSameAsSelectedRarityToken = (tok)=>{
    if (!__rarityTokN && !__rarityBeforePearlId) return false;
    const t = String(tok || '').trim();
    if (!t) return false;
    if (__rarityTokN && t.replace(/\s+/g, '').trim() === __rarityTokN) return true;
    // Stacked mixes only match exact brace form.
    if (skinIsStackedMix) return false;
    const skinId = tokenIdOnlyForRarity(rarityTok) || rarityItemIdStr;
    const tokId = tokenIdOnlyForRarity(t);
    if (skinId && tokId && skinId === tokId) return true;
    // Pearl override rewrote rarityItemId — still drop the craft's previous rarity brace.
    if (__rarityBeforePearlId && tokId && tokId === __rarityBeforePearlId) return true;
    if (!__rarityTokN) return false;
    const one = normalizeIdTokensForBaseFamilyWithPrefs([t], baseFamilyId);
    if (!Array.isArray(one) || !one.length) return false;
    return String(one[0] || '').replace(/\s+/g,'').trim() === __rarityTokN;
  };
// Weapon detection should not depend on main-part selection.

  if (isWeapon){
    const isElement = (t)=>/^\{\s*1\s*:\s*\d+\s*\}$/.test(t);
    const isSkin = (t)=>isSkinTokenCandidate(t);
    const spawnTokEarly = (weaponSkinSelection && weaponSkinSelection.spawnToken)
      ? String(weaponSkinSelection.spawnToken || '').trim()
      : '';

    const bracketTokens = [];
    const gunTokens = [];
    const camoTokens = [];
    const elements = [];
    const preservedSpawn = [];

    for (const t of outputTokens){
      if (!t) continue;
      if (isSameAsSelectedRarityToken(t)) continue;
      
      const sT = String(t).trim();
      if (skinBraceTok && sT.replace(/\s+/g, '') === skinBraceTok.replace(/\s+/g, '')) continue;
      if (isSkin(sT)) {
        const ct = canonicalCamoToken(sT);
        if (ct) {
          camoTokens.push(ct);
          continue;
        }
        const unqSkin = unquoteWrappedValue(sT);
        if (/^Cosmetics_Weapon_/i.test(unqSkin)) {
          /* Map imported Cosmetics names to `c` form; do not keep bare spawn strings. */
          if (!spawnTokEarly) {
            try {
              const r = resolveCosmeticWeaponSkinSerial(unqSkin);
              if (r && r.camoToken) camoTokens.push(r.camoToken);
              else if (r && r.stringCamo) preservedSpawn.push(r.stringCamo);
            } catch (_) {}
          }
          continue;
        }
        // Drop legacy/extra skin rarity braces — active Skin dropdown is source of truth.
        continue;
      }
      if (isElement(sT)) { elements.push(sT); continue; }
      
      // If it's a bracketed group or a numeric token, it goes to partsSection
      if (sT.startsWith('{')) bracketTokens.push(sT);
      else gunTokens.push(sT);
    }

    // Optional Skin (optional) spawn string + Camo (optional) `|"c",N|` — separate controls.
    const spawnTok = spawnTokEarly || (preservedSpawn.length ? preservedSpawn[preservedSpawn.length - 1] : '');
    if (weaponSkinSelection && weaponSkinSelection.camoToken){
      camoTokens.push(String(weaponSkinSelection.camoToken || '').trim());
    }
    const skinTok = camoTokens.length ? String(camoTokens[camoTokens.length - 1] || '').trim() : '';

    // Elements from selection (same ordering intent as `computeOutputTokens`): primary → Maliwan switch → stack.
    const primObj = ELEMENTS.find(x=>x.key===(state.primaryElement||'None'));
    const primKey = state.primaryElement || 'None';
    const mfrL = String(state.manufacturer || '').trim().toLowerCase();
    const manualSw = state.slots && state.slots.secondaryEle;
    const mc = manualSw ? String(normCode(manualSw.code || '') || '').toLowerCase() : '';
    const hasManualSwitch = mc.includes('part_secondary_elem') && mc.includes('_mal');
    if (primObj && primObj.code) elements.unshift(primObj.code);
    if (Array.isArray(state.elementStack)){
      if (state.elementStack.length && state.dualElementUseMaliwanSwitch && primKey !== 'None' && !hasManualSwitch){
        const sw = stxFindMaliwanDualSwitchPart(primKey, state.elementStack[0]);
        if (sw){
          const st = tokenForPart(sw);
          if (st) elements.push(st);
        }
      }
      for (const e of state.elementStack){
        const eo = ELEMENTS.find(x=>x.key===e);
        if (eo && eo.code) elements.push(eo.code);
      }
    }

    const __bracketNorm = normalizeIdTokensForBaseFamilyWithPrefs(bracketTokens, baseFamilyId);
    const __bracket = compressConsecutiveFamilyRefs(__bracketNorm);

    // Order: Rarity, Skin brace, spawn/`c` string, Parts, Elements, Camo `|"c",N|`.
    const partsSection = [...__bracket, ...gunTokens.map(quoteIfGunPart)]
      .filter(Boolean)
      .join(' ')
      .trim();
    
    /* Pack stacked elements → `{1:[13 13]}` (never emit a lone `,{1:13}`). */
    const elementsPacked = stxPackWeaponElementTokens(elements.filter(Boolean));
    const elementsStr = elementsPacked.join(' ').trim();
    
    // Construct the tail parts in specific order
    let tailParts = [rarityTok, skinBraceTok, spawnTok, partsSection, elementsStr, skinTok].filter(Boolean);
    // Dedup rarity if already in partsSection (bracketed or gunTokens)
    if (rarityTok) {
       const cleanRarityTok = rarityTok.trim();
       if (partsSection.includes(cleanRarityTok)) {
          tailParts = [skinBraceTok, partsSection, elementsStr, skinTok].filter(Boolean);
       }
    }
    if (skinBraceTok) {
      const cleanSkin = skinBraceTok.trim();
      const withoutDupSkin = [];
      let skinOnce = false;
      for (let ti = 0; ti < tailParts.length; ti++) {
        const tp = String(tailParts[ti] || '').trim();
        if (tp === cleanSkin) {
          if (skinOnce) continue;
          skinOnce = true;
        }
        withoutDupSkin.push(tailParts[ti]);
      }
      tailParts = withoutDupSkin;
    }
    if (isStxSimplePearlOverrideChecked()){
      const wt = String((state && state.weaponType) || '').trim();
      const pr = stxPickPearlOverrideBraceToken(baseFamilyId, true, 'Weapon', wt);
      /* Prepend pearl rarity dual-brace only — keep crafted rarity. */
      tailParts = stxApplyPearlRarityOnlyToTailSeq(tailParts, pr, baseFamilyId, 'Weapon');
    }
    let tail = tailParts.join(' ').trim();
    
    // Ensure final tail ends with a single pipe (no space before it)
    if (tail) {
      tail = tail.trim();
      if (!/\|\s*$/.test(tail)) tail = tail + '|';
    }

    const seed = getSeed(base);
    const headerFlags = stxReadSerialModifierFlags();
    let out = `${base.familyId}, 0, 1, ${level}|`;
    out += stxBuildSerialHeaderSuffix(seed, headerFlags.lockFirmware, headerFlags.buybackFlag);
    if (tail){
      out += /\|\s*$/.test(tail) ? ` ${tail}` : ` ${tail}|`;
    }
    return String(out || '').replace(/\s+\|$/, '|');
  }

  const __partsArrRaw = outputTokens
    .filter(t => !isSameAsSelectedRarityToken(t))
    .map(quoteIfGunPart)
    .filter(Boolean);
  const __partsArr = normalizeIdTokensForBaseFamilyWithPrefs(__partsArrRaw, baseFamilyId);

  const catTail = outputCategory;
  // Shields mix gadget pool 246 (element/resist + perks + firmware) with base-family tokens.
  // Packing consecutive `{246:a} {246:b} …` into `{246:[a b …]}` often fails to spawn — emit separate tokens.
  // Repkits likewise use packed `{243:…}` pools; bracket compression after `||` often fails in-game (spawn rejects).
  const shieldSkipCompress = (catTail === 'Shield');
  const repkitSkipCompress = (catTail === 'Repkit');
  /* Class Mod: same-base tokens are already bare `{id}` after normalize; consecutive foreign `{fam:a} {fam:b}` pack for any fam. */
  const classModPackForeignRuns = (catTail === 'Class Mod');
  let partsSection;
  if (shieldSkipCompress || repkitSkipCompress) {
    partsSection = __partsArr.join(' ').trim();
  } else if (classModPackForeignRuns) {
    partsSection = compressConsecutiveFamilyRefs(__partsArr)
      .join(' ')
      .trim();
  } else {
    partsSection = (((state.idMode && window.__CC_ENABLE_FAMILY_REF_COMPRESS === true) ? compressFamilyRefsAll(__partsArr) : compressConsecutiveFamilyRefs(__partsArr))
      .join(' ')
      .trim());
  }
  const seed = getSeed(base);
  let tailPartsNw = [rarityTok, partsSection].filter(Boolean);
  const classModPearlTier =
    String(outputCategory) === 'Class Mod' &&
    Number.isFinite(selectedTier) &&
    Number(selectedTier) === 5;
  if (String(outputCategory) === 'Class Mod' && (isStxSimplePearlOverrideChecked() || classModPearlTier)){
    const pr = stxPickClassModPearlOverrideBraceToken(baseFamilyId);
    if (pr) {
      /* Strip any pearl already injected via token preview, then prepend once. */
      let flat = [];
      for (const chunk of tailPartsNw) {
        for (const t of String(chunk || '').split(/\s+/).filter(Boolean)) {
          if (!stxLooksLikePearlOverrideLeadTok(t)) flat.push(t);
        }
      }
      /* `|| {26} {548}|` → `|| {7:54} {26} {548}|` — prepend nameless pearl only. */
      tailPartsNw = stxApplyPearlRarityOnlyToTailSeq(flat, pr, baseFamilyId, 'Class Mod');
    }
  } else if (isStxSimplePearlOverrideChecked()){
    const pr = stxPickPearlOverrideBraceToken(baseFamilyId, false, outputCategory, '');
    let flat = [];
    for (const chunk of tailPartsNw) {
      for (const t of String(chunk || '').split(/\s+/).filter(Boolean)) {
        if (!stxLooksLikePearlOverrideLeadTok(t)) flat.push(t);
      }
    }
    /* Prepend nameless pearl (enhancement/shield/…) — never Eigenburst gun uniques. */
    tailPartsNw = stxApplyPearlRarityOnlyToTailSeq(flat, pr, baseFamilyId, outputCategory);
  }
  const tail = tailPartsNw.join(' ').trim();

  const headerFlagsNw = stxReadSerialModifierFlags();
  let out = `${base.familyId}, 0, 1, ${level}|`;
  out += stxBuildSerialHeaderSuffix(seed, headerFlagsNw.lockFirmware, headerFlagsNw.buybackFlag);
  if (tail){
    out += /\|\s*$/.test(tail) ? ` ${tail}` : ` ${tail}|`;
  }
  return String(out || '').replace(/\s+\|$/, '|');
}

  function stxNormalizePartExtraToken(rawTok){
    let t = String(rawTok || '').trim();
    if (!t) return '';
    if (/^\d+:\d+$/.test(t)) return `{${t}}`;
    if (/^\d+$/.test(t)) return `{${t}}`;
    if (/^\{\s*\d+\s*:\s*\[/.test(t)) return t;
    if (/^\{\s*\d+\s*:\s*\d+\s*\}$/.test(t)) return t;
    if (/^\{\s*\d+\s*\}$/.test(t)) return t;
    const bare = t.replace(/^"+|"+$/g, '').trim();
    if (!bare) return '';
    if (bare.includes('.')) return `"${bare}"`;
    return t;
  }

  /**
   * Append one part token into `state.extras` so `refreshOutputs()` keeps stacked tail parts.
   * Accepts `{fam:id}`, `{id}`, and quoted spawn codes (e.g. `"MAL_SG.part_barrel_foo"`).
   */
  function stxAppendPartTokenViaExtras(rawTok, opts){
    const o = opts || {};
    const t = stxNormalizePartExtraToken(rawTok);
    if (!t) return false;
    const isDual = /^\{\s*\d+\s*:\s*\d+\s*\}$/.test(t);
    const isBareId = /^\{\s*\d+\s*\}$/.test(t);
    const isBracketList = /^\{\s*\d+\s*:\s*\[/.test(t);
    const isQuotedSpawn = /^".+"$/.test(t);
    if (!isDual && !isBareId && !isBracketList && !isQuotedSpawn) return false;

    clearImportedOutputLock();
    try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_) {}

    state.extras = Array.isArray(state.extras) ? state.extras : [];
    let maxOrd = 0;
    for (const ex of state.extras){
      const ord = ex && typeof ex.order === 'number' ? ex.order : 0;
      if (ord > maxOrd) maxOrd = ord;
    }
    state.extras.push({
      tok: t,
      order: maxOrd + 1,
      type: String(o.type || 'stackedPart')
    });

    if (!o.skipRefresh){
      refreshOutputs(true);
      try { if (typeof window.refreshBuildStatsCore === 'function') window.refreshBuildStatsCore(); } catch (_) {}
      try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
    }
    return true;
  }
  try { window.stxAppendPartTokenViaExtras = stxAppendPartTokenViaExtras; } catch (_) {}

  /**
   * Quick-add `{family:itemId}` tokens must merge into `state.extras` — otherwise `refreshOutputs()`
   * regenerates `outCode` from slots alone and wipes textarea-only appends (floating panel goes stale too).
   */
  function stxAppendTailTokenViaExtras(rawTok){
    return stxAppendPartTokenViaExtras(rawTok, { type: 'quickPreset' });
  }
  try { window.stxAppendTailTokenViaExtras = stxAppendTailTokenViaExtras; } catch (_) {}

  /**
   * Tools / preset UI: append one or more normalized `{fam:id}` or `{id}` tokens into Simple Builder `state.extras`.
   * Plain `#outCode` edits are overwritten by `refreshOutputs()` — presets must use this path (or `stxAppendTailTokenViaExtras`).
   */
  function stxAppendQuickPresetNumericTokens(normalizedTokArr, opts){
    const arr = Array.isArray(normalizedTokArr) ? normalizedTokArr : [];
    const o = opts || {};
    const replaceBareQuickPresets = !!o.replaceBareQuickPresets;
    const filtered = arr.map(x => String(x || '').trim()).filter(Boolean);
    if (!filtered.length) return false;
    for (const t of filtered){
      const isDual = /^\{\s*\d+\s*:\s*\d+\s*\}$/.test(t);
      const isBare = /^\{\s*\d+\s*\}$/.test(t);
      if (!isDual && !isBare) return false;
    }

    clearImportedOutputLock();
    try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_) {}

    state.extras = Array.isArray(state.extras) ? state.extras : [];
    if (replaceBareQuickPresets){
      state.extras = state.extras.filter(ex => {
        if (!ex || typeof ex !== 'object') return true;
        if (String(ex.type || '') !== 'quickPreset') return true;
        const tk = String(ex.tok || '').trim();
        return !/^\{\s*\d+\s*\}$/.test(tk);
      });
    }
    let maxOrd = 0;
    for (const ex of state.extras){
      const ord = ex && typeof ex.order === 'number' ? ex.order : 0;
      if (ord > maxOrd) maxOrd = ord;
    }
    let ord = maxOrd;
    for (const t of filtered){
      ord += 1;
      state.extras.push({ tok: t, order: ord, type: 'quickPreset' });
    }

    refreshOutputs(true);
    try { if (typeof window.refreshBuildStatsCore === 'function') window.refreshBuildStatsCore(); } catch (_) {}
    try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
    return true;
  }
  try { window.stxAppendQuickPresetNumericTokens = stxAppendQuickPresetNumericTokens; } catch (_) {}

  /** True when #outCode already has a toolbox-style item header before `||`. */
  function stxOutCodeHasItemHeader(){
    try {
      const existing = String(($('outCode') && $('outCode').value) || '').trim();
      const dbl = existing.indexOf('||');
      if (dbl < 0) return false;
      const prefix = existing.slice(0, dbl).trim();
      return /^\d+\s*,\s*0\s*,\s*1\s*,\s*\d+\s*\|/.test(prefix) || /^\d+\s*,/.test(prefix);
    } catch (_) {
      return false;
    }
  }
  try { window.stxOutCodeHasItemHeader = stxOutCodeHasItemHeader; } catch (_) {}

  /** Simple Builder has a real item (slots/main part or a full serialized header in #outCode). */
  function stxSimpleBuilderHasActiveBuild(){
    if (state.mainPart) return true;
    if (stxOutCodeHasItemHeader()) return true;
    try {
      const slots = state.slots;
      if (slots && typeof slots === 'object'){
        for (const k of Object.keys(slots)){
          if (slots[k]) return true;
        }
      }
    } catch (_) {}
    return false;
  }
  try { window.stxSimpleBuilderHasActiveBuild = stxSimpleBuilderHasActiveBuild; } catch (_) {}

  /**
   * Infer the best Simple Builder weapon slot key for a resolved part row.
   * Prefer accessory/specialty matchers before main slots so parts land correctly.
   */
  function stxInferBestWeaponSlotKey(p){
    if (!p) return '';
    const pt = String(p.partType || '').trim().toLowerCase();
    const code = String(normCode(p.code || p.spawnCode || '') || '').toLowerCase();
    if (!code && !pt) return '';
    if (pt === 'rarity' || /(?:^|[._])comp_0[1-6]_/.test(code) || /(?:^|[._])pearl_/.test(code)) return '';
    if (isSkinTokenCandidate(tokenForPart(p) || code)) return '';

    const match = (typeof window.stxWeaponSlotPartMatch === 'function')
      ? (k) => window.stxWeaponSlotPartMatch(k, p)
      : null;

    const ordered = [
      'underbarrelAccVis', 'underbarrelAcc', 'underbarrel',
      'magazineAcc', 'magazineBorg', 'mag',
      'barrelAcc', 'barrel',
      'scopeAcc', 'scope',
      'bodyEle', 'bodyMag', 'bodyAcc', 'body',
      'grip', 'foregrip',
      'licensed', 'secondaryAmmo', 'hyperionSecondaryAcc', 'secondaryEle',
      'pearlElem', 'pearlStat', 'firmware', 'legendary', 'statMod'
    ];

    for (let i = 0; i < ordered.length; i++) {
      const key = ordered[i];
      if (match && (key === 'mag' || key === 'magazineAcc' || key === 'magazineBorg'
        || key === 'barrel' || key === 'barrelAcc'
        || key === 'scope' || key === 'scopeAcc'
        || key === 'underbarrel' || key === 'underbarrelAcc' || key === 'underbarrelAccVis')) {
        if (match(key)) return key;
        continue;
      }
      if (key === 'body') {
        if (pt === 'body' || /\.part_body(?:$|_\d)/.test(code)) {
          if (!/part_body_(?:bolt|flap|ele|mag)/.test(code) && !/\.part_body_[a-z](?:_|$)/.test(code)) return 'body';
        }
        continue;
      }
      if (key === 'bodyAcc') {
        if (pt === 'body accessory' || /part_body_bolt|part_body_flap|\.part_body_[a-z](?:_|$)/.test(code)) return 'bodyAcc';
        continue;
      }
      if (key === 'bodyEle') {
        if (pt === 'body element' || /part_body_ele/.test(code)) return 'bodyEle';
        continue;
      }
      if (key === 'bodyMag') {
        if (/part_body_mag/.test(code)) return 'bodyMag';
        continue;
      }
      if (key === 'grip' && (pt === 'grip' || /part_grip/.test(code))) return 'grip';
      if (key === 'foregrip' && (pt === 'foregrip' || /part_foregrip/.test(code))) return 'foregrip';
      if (key === 'licensed' && /barrel_licensed/.test(code)) return 'licensed';
      if (key === 'secondaryAmmo' && /part_secondary_ammo/.test(code)) return 'secondaryAmmo';
      if (key === 'hyperionSecondaryAcc' && (/part_shield/.test(code) || /amp/.test(code))) return 'hyperionSecondaryAcc';
      if (key === 'secondaryEle' && /part_secondary_elem/.test(code) && /_mal/.test(code)) return 'secondaryEle';
      if (key === 'pearlElem' && weaponPearlElemPartMatch(p)) return 'pearlElem';
      if (key === 'pearlStat' && weaponPearlStatPartMatch(p)) return 'pearlStat';
      if (key === 'firmware' && (pt === 'firmware' || /part_firmware/.test(code))) return 'firmware';
      if (key === 'legendary' && /legendary\s*perk/i.test(pt)) return 'legendary';
      if (key === 'statMod' && /stat\s*modifier/i.test(pt)) return 'statMod';
    }

    const ptMap = {
      body: 'body', 'body accessory': 'bodyAcc', 'body element': 'bodyEle',
      barrel: 'barrel', 'barrel accessory': 'barrelAcc',
      magazine: 'mag', 'magazine accessory': 'magazineAcc',
      scope: 'scope', 'scope accessory': 'scopeAcc',
      grip: 'grip', foregrip: 'foregrip', underbarrel: 'underbarrel',
      firmware: 'firmware', 'legendary perks': 'legendary', 'stat modifier': 'statMod',
      'element switch': 'secondaryEle', 'manufacturer part': ''
    };
    return ptMap[pt] || '';
  }

  /**
   * Place a resolved part into the best matching Simple Builder slot (replace single slots, stack multi).
   * Returns true when the part was slotted (caller should skip blind tail-append).
   */
  function stxTryPlacePartInBestSlot(part, opts){
    const o = opts || {};
    if (!part || !stxSimpleBuilderHasActiveBuild()) return false;
    const cat = String(state.detectedCategory || state.itemType || '').trim();
    const isWeaponish = cat === 'Weapon' || cat === 'Heavy' || cat === 'Heavy Weapon' || cat === 'Gadget';
    if (!isWeaponish) return false;

    let key = stxInferBestWeaponSlotKey(part);
    if (!key) return false;

    const schema = getActiveWeaponSlotSchema() || [];
    let schemaItem = schema.find(s => s && s.key === key) || null;
    if (!schemaItem && key === 'mag') schemaItem = schema.find(s => s && (s.key === 'mag' || s.key === 'magazine')) || null;
    if (!schemaItem) {
      const add = schema.find(s => s && (s.key === 'additionalParts' || s.customType === 'weaponAdditionalParts'));
      if (add) {
        key = add.key;
        schemaItem = add;
      } else {
        return false;
      }
    }

    clearImportedOutputLock();
    try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_) {}
    if (!state.slots || typeof state.slots !== 'object') state.slots = {};

    const multi = !!(schemaItem.multi || key === 'additionalParts' || key === 'legendary');
    const forceStack = !!(o.forceStack || o.stackDuplicates);
    if (multi || forceStack) {
      const arr = Array.isArray(state.slots[key]) ? state.slots[key].slice() : (state.slots[key] ? [state.slots[key]] : []);
      /* Always append on stack — same part qty 3 then another 3 must accumulate. */
      arr.push(stxClonePartWithImportOrder(part, (stxNextImportOrders(arr, 1)[0])));
      state.slots[key] = arr;
    } else {
      state.slots[key] = part;
    }

    if (!o.skipRefresh) {
      try { refreshBuilder(); } catch (_) {}
      try { refreshOutputs(true); } catch (_) {}
      try { if (typeof window.refreshBuildStatsCore === 'function') window.refreshBuildStatsCore(); } catch (_) {}
      try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
    }
    return true;
  }
  try { window.stxInferBestWeaponSlotKey = stxInferBestWeaponSlotKey; } catch (_) {}
  try { window.stxTryPlacePartInBestSlot = stxTryPlacePartInBestSlot; } catch (_) {}

  /**
   * Append preset / quick-add tokens into Simple `state.extras` when Simple already has a build.
   * Used by Guided preset UI and Tools so tail edits are not lost to `refreshOutputs()`.
   * Resolvable gun parts are placed into the best matching slot when possible.
   */
  function stxAppendPresetToActiveBuilder(rawCode, opts){
    const o = opts || {};
    try {
      if (typeof window.__ccGuidedHasLiveTailSerial === 'function' && window.__ccGuidedHasLiveTailSerial()) {
        return false;
      }
    } catch (_) {}
    if (!stxSimpleBuilderHasActiveBuild()) return false;
    let code = String(rawCode || '').trim();
    if (!code) return false;
    if (/^\d+:\d+$/.test(code)) code = `{${code}}`;
    if (/^\d+$/.test(code)) code = `{${code}}`;
    code = code.replace(/^"+|"+$/g, '');
    const n = Math.max(1, parseInt(o.quantity, 10) || 1);

    /* Stacked mixer braces `{fam:[id1 id2…]}` belong on the skin slot, not as loose extras.
       Plain `{fam:id}` skins are handled by the normal skin dropdown and should not be intercepted here. */
    if (/^\{\s*\d+\s*:\s*\[/.test(code) && !/^\{\s*1\s*:/.test(code)) {
      const skinSel = $('skinSelect');
      if (skinSel) {
        let found = false;
        for (let oi = 0; oi < (skinSel.options || []).length; oi++) {
          if (String(skinSel.options[oi].value || '').trim() === code) { found = true; break; }
        }
        if (!found) {
          const opt = new Option(code, code);
          try { opt.setAttribute('data-base-label', code); } catch (_) {}
          skinSel.appendChild(opt);
        }
        skinSel.value = code;
        try { stxSyncCustomSelectIfWrapped(skinSel); } catch (_) {}
        try { syncMainPartFromSkinSelection(); } catch (_) {}
        refreshOutputs(true);
        try { if (typeof window.refreshBuildStatsCore === 'function') window.refreshBuildStatsCore(); } catch (_) {}
        try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
        return true;
      }
    }

    const resolved = tryResolveToken(code);
    if (resolved) {
      let placed = 0;
      for (let qi = 0; qi < n; qi++) {
        if (stxTryPlacePartInBestSlot(resolved, { skipRefresh: qi < n - 1, forceStack: n > 1 })) placed++;
        else break;
      }
      if (placed === n) return true;
      if (placed > 0) {
        try { refreshBuilder(); } catch (_) {}
        try { refreshOutputs(true); } catch (_) {}
        return true;
      }
    }

    const serialSb = String(($('outCode') && $('outCode').value) || '').trim();
    let baseFamSb = null;
    try {
      const dblSb = serialSb.indexOf('||');
      const prefixSb = dblSb >= 0 ? serialSb.slice(0, dblSb).trim() : serialSb;
      const mSb = prefixSb.match(/^\s*(\d+)\s*[,\|]/) || prefixSb.match(/^\s*(\d+)/);
      baseFamSb = mSb ? Number(mSb[1]) : null;
    } catch (_) {}

    const piecesSb = [];
    for (let i = 0; i < n; i++) piecesSb.push(code);
    let normPiecesSb = piecesSb;
    if (typeof window.normalizeIdTokensForBaseFamily === 'function' && baseFamSb != null) {
      normPiecesSb = window.normalizeIdTokensForBaseFamily(piecesSb, baseFamSb, { compactSameFamily: false });
    }

    try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_) {}

    /* Stat presets stack — do not strip prior bare `{id}` quickPreset rows (legacy replace was for rarity-only picks). */
    if (stxAppendQuickPresetNumericTokens(normPiecesSb, { replaceBareQuickPresets: false })) {
      try { if (typeof window.refreshBuildStatsCore === 'function') window.refreshBuildStatsCore(); } catch (_) {}
      try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
      return true;
    }
    for (let ia = 0; ia < normPiecesSb.length; ia++) {
      const skipRefresh = ia < normPiecesSb.length - 1;
      if (!stxAppendPartTokenViaExtras(normPiecesSb[ia], { type: 'quickPreset', skipRefresh })) return false;
    }
    try { if (typeof window.refreshBuildStatsCore === 'function') window.refreshBuildStatsCore(); } catch (_) {}
    try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
    return true;
  }
  try { window.stxAppendPresetToActiveBuilder = stxAppendPresetToActiveBuilder; } catch (_) {}
  try { window.isSkinTokenCandidate = isSkinTokenCandidate; } catch (_) {}

  let __refreshOutputsPending = false;
  let __refreshOutputsForceQueued = false;
  let __refreshOutputsRescheduleQueued = false;
  function refreshOutputs(force){
    if (!force && typeof window.__ccIsScrollBusy === 'function' && window.__ccIsScrollBusy()) return;
    
    if (__refreshOutputsPending) {
      if (force) __refreshOutputsForceQueued = true;
      else __refreshOutputsRescheduleQueued = true;
      return;
    }
    __refreshOutputsPending = true;

    requestAnimationFrame(function() {
      __refreshOutputsPending = false;
      const runForce = !!force || __refreshOutputsForceQueued;
      __refreshOutputsForceQueued = false;
      const {tokens, json} = computeOutputTokens(runForce);
      const listBase = getSelectedBaseItem();
      const listFamily = Number(listBase && listBase.familyId);
      const listIsClassMod = String(state.itemType || '').trim() === 'Class Mod';
      let listTokensRaw;
      if (listIsClassMod) {
        listTokensRaw = compressConsecutiveFamilyRefs(tokens);
      } else if (state.idMode && window.__CC_ENABLE_FAMILY_REF_COMPRESS === true) {
        listTokensRaw = compressFamilyRefsAll(tokens);
      } else {
        listTokensRaw = tokens;
      }
      
      const listCompactSame = !isForceTypeIdTokensEnabled();
      const listTokens = normalizeIdTokensForBaseFamily(
        listTokensRaw,
        listFamily,
        { compactSameFamily: listCompactSame }
      );
      
      const lockedImportedCode = (window.__LOCK_IMPORTED_OUTPUT && window.__LAST_IMPORTED_DESERIALIZED)
        ? String(window.__LAST_IMPORTED_DESERIALIZED || '').trim()
        : '';
      const code = lockedImportedCode || computeFullDeserializedCode();
      let partsListValue = listTokens.map(t => String(t || '')).join(', ');
      
      if (code.includes('||')) {
        const partsPart = code.split('||')[1].trim();
        if (partsPart) {
          const actualParts = parseImportTokenList(partsPart)
            .map(t => String(t || '').trim())
            .filter(t => t && t !== '|' && t !== '||');
          partsListValue = actualParts.join(', ');
        }
      }
      
      $('outList').value = partsListValue;
      const lastTarget = String(window.__CC_LAST_CODE_TARGET || '').trim();
      const simpleActive = typeof stxSimpleBuilderHasActiveBuild === 'function' && stxSimpleBuilderHasActiveBuild();
      const writeSimpleOut = (
        simpleActive ||
        ((runForce || lastTarget === 'simple') && lastTarget !== 'guided')
      );
      if (writeSimpleOut) {
        writeSharedItemCode({
          deser: code,
          source: 'simple',
          force: !!runForce || !!window.__CC_BUILDER_HANDOFF
        });
        try {
          const outEl = $('outCode');
          if (outEl) outEl.dispatchEvent(new Event('input', { bubbles: true }));
        } catch (_) {}
      }
      if (!runForce && lastTarget !== 'guided') {
        try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_) {}
      }
      $('outJson').value = JSON.stringify(json, null, 2);
      try {
        if (typeof window.refreshImportedInspector === 'function' && !window.__CC_IMPORT_IN_PROGRESS) {
          window.refreshImportedInspector();
        }
      } catch(_){}
      try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch(_){}
      try { if (typeof window.__ccSyncCodeCharCounts === 'function') window.__ccSyncCodeCharCounts(); } catch (_) {}
      try {
        if (typeof window.__ccForceCustomSelectSync === 'function') {
          ['stx_itemType', 'weaponType', 'stx_manufacturer', 'mainPart', 'rarity', 'skinSelect', 'camoSelect',
            'ccGuidedItemType', 'ccGuidedWeaponType', 'ccGuidedManufacturer', 'ccGuidedLevel'].forEach(function (sid) {
            var node = document.getElementById(sid);
            if (node) window.__ccForceCustomSelectSync(node);
          });
        }
      } catch (_ccFs) {}
      if (__refreshOutputsForceQueued) {
        __refreshOutputsForceQueued = false;
        refreshOutputs(true);
      } else if (__refreshOutputsRescheduleQueued) {
        __refreshOutputsRescheduleQueued = false;
        refreshOutputs(false);
      }
    });
  }

  function updateModeLabel(){
    const el = $('modeLabel');
    if (el) el.textContent = state.idMode ? 'Numeric' : 'Spawn';
  }


  /** Clear import pin so rebuilds use live slots. Pass true on explicit user Add/select edits. */
  function clearImportedOutputLock(force){
    if (!force && window.__CC_IMPORT_IN_PROGRESS) return;
    try{
      window.__LOCK_IMPORTED_OUTPUT = false;
      window.__ccImportedValue = null;
      window.__LAST_IMPORTED_DESERIALIZED = null;
      window.__IMPORTED_HEADER_FULL = null;
      window.__IMPORTED_BASE_ITEM = null;
      window.__IMPORTED_BASE_FAMILY_ID = null;
    }catch(_){}
  }

  /**
   * Best live deserialized serial across Simple mirror + shared Generated Item Code panel.
   */
  function getSharedDeserialized(){
    let gv = '';
    let ov = '';
    let fv = '';
    try {
      const gDes = document.getElementById('guidedOutputDeserialized');
      gv = gDes ? String(gDes.value || '').trim() : '';
    } catch (_) {}
    try {
      const out = $('outCode');
      ov = out ? String(out.value || '').trim() : '';
    } catch (_) {}
    try {
      const fl = document.getElementById('floating-output-code');
      fv = fl ? String(fl.value || '').trim() : '';
    } catch (_) {}
    const gLive = gv.indexOf('||') >= 0;
    const oLive = ov.indexOf('||') >= 0;
    const fLive = fv.indexOf('||') >= 0;
    const last = String(window.__CC_LAST_CODE_TARGET || '').trim();
    const simpleActive = typeof stxSimpleBuilderHasActiveBuild === 'function' && stxSimpleBuilderHasActiveBuild();
    /* Prefer the longest live serial when floating was manually edited for import/handoff. */
    if (fLive && (!oLive || fv.length >= ov.length) && (!gLive || fv.length >= gv.length)) {
      if (last === 'floating' || (!simpleActive && last !== 'guided' && last !== 'simple')) return fv;
      if (fv.length > Math.max(ov.length, gv.length) + 5) return fv;
    }
    if (oLive && last !== 'guided' && (simpleActive || last === 'simple')) {
      if (!gLive || ov.length >= gv.length) return ov;
    }
    if (gLive && last === 'guided') return gv;
    if (gLive && (!oLive || gv.length >= ov.length)) return gv;
    if (oLive) return ov;
    if (fLive) return fv;
    return gv || ov || fv || '';
  }
  try { window.getSharedDeserialized = getSharedDeserialized; } catch (_) {}

  /**
   * Preflight before Base85 convert: hard-fail absurd stacks only.
   * Cosmetics_Weapon string tokens are valid TOK_STRING (Skin optional / phosphene) — do not block convert.
   * Soft-warn named-legendary rarity with wrong-family named barrel.
   */
  function stxPreflightDeserializedForConvert(deserRaw){
    const deser = String(deserRaw || '').trim();
    const hardFails = [];
    const warnings = [];
    if (!deser || deser.indexOf('||') < 0) {
      return { ok: false, hardFails: ['Missing deserialized || payload'], warnings: warnings };
    }
    if (/"\s*Cosmetics_Weapon_/i.test(deser) || /(?:^|[\s|])Cosmetics_Weapon_/i.test(deser)) {
      warnings.push('Cosmetics_Weapon string token present (Skin optional / phosphene) — convert allowed');
    }
    const dbl = deser.indexOf('||');
    const tail = deser.slice(dbl + 2);
    const toks = parseImportTokenList(tail);
    const famCounts = Object.create(null);
    let raritySuffix = '';
    try {
      if (state && state.mainPart) raritySuffix = stxRarityBarrelSuffixFromPart(state.mainPart) || '';
    } catch (_) {}
    let namedBarrelMismatch = false;
    for (let i = 0; i < toks.length; i++) {
      const t = String(toks[i] || '').trim();
      const unq = t.replace(/^"+|"+$/g, '');
      const packed = t.match(/^\{\s*(\d+)\s*:\s*\[([^\]]+)\]\s*\}$/);
      if (packed) {
        const fam = packed[1];
        const ids = String(packed[2] || '').match(/\d+/g) || [];
        famCounts[fam] = (famCounts[fam] || 0) + ids.length;
        continue;
      }
      const pair = t.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
      if (pair) {
        famCounts[pair[1]] = (famCounts[pair[1]] || 0) + 1;
      }
      if (raritySuffix) {
        try {
          const part = (typeof tryResolveToken === 'function') ? tryResolveToken(t) : null;
          const code = part ? String(normCode(part.code || '') || '').toLowerCase() : '';
          if (/part_barrel_\d+_[a-z0-9_]+$/.test(code) && !stxWeaponBarrelCodeMatchesRaritySuffix(code, raritySuffix)) {
            namedBarrelMismatch = true;
          }
        } catch (_) {}
      }
      void unq;
    }
    for (const fam in famCounts) {
      /* Modded class mods / packed stacks routinely exceed ~80 ids — only block truly absurd sizes. */
      if (famCounts[fam] >= 2500) {
        hardFails.push('Absurd part stack size for family ' + fam + ' (' + famCounts[fam] + ')');
      } else if (famCounts[fam] >= 400) {
        warnings.push('Large stack for family ' + fam + ' (' + famCounts[fam] + ') — convert still allowed');
      }
    }
    if (namedBarrelMismatch) {
      warnings.push('Named legendary rarity with a barrel that does not match that rarity family');
    }
    try {
      window.__ccLastSerialPreflight = { hardFails: hardFails.slice(), warnings: warnings.slice() };
    } catch (_) {}
    return { ok: hardFails.length === 0, hardFails: hardFails, warnings: warnings };
  }
  try { window.stxPreflightDeserializedForConvert = stxPreflightDeserializedForConvert; } catch (_) {}

  /**
   * Strip serial junk that breaks spawn (broken camo fragments, unresolved cosmetics leftovers).
   * Does NOT de-mod or force legit pools — spawn-safety only.
   */
  function stxStripSpawnUnsafeJunkTokens(fullSerial){
    const full = String(fullSerial || '').trim();
    const dbl = full.indexOf('||');
    if (dbl < 0) return { serial: full, changed: false };
    const head = full.slice(0, dbl + 2).replace(/\s+$/, '');
    let tail = full.slice(dbl + 2).trim();
    let changed = false;
    /* Remove duplicated header pasted into the tail (e.g. `279 1 70| 2 1259|| {12}…`). */
    const dupHead = tail.match(/^(\d[\d\s|,]*)\|\|\s*/);
    if (dupHead) {
      tail = tail.slice(dupHead[0].length).trim();
      changed = true;
    } else {
      /* Loose: `279 1 70| 2 1259` then braces (no second ||). */
      const looseHead = tail.match(/^(\d+(?:\s*[,\s]\s*\d+){1,8}\s*\|\s*\d+(?:\s*,\s*\d+)?)\s+/);
      if (looseHead && /\{/.test(tail.slice(looseHead[0].length))) {
        tail = tail.slice(looseHead[0].length).trim();
        changed = true;
      }
    }
    /* Tokenize ONLY the cleaned tail — never re-feed header digits into the part list. */
    const toks = (typeof parseImportTokenList === 'function')
      ? parseImportTokenList(head + (tail ? ' ' + tail : ''))
      : [];
    const kept = [];
    for (let i = 0; i < toks.length; i++) {
      const t = String(toks[i] || '').trim();
      if (!t) { changed = true; continue; }
      const unq = t.replace(/^"+|"+$/g, '');
      /* Keep Cosmetics_Weapon string tokens; only strip broken camo / zero junk. */
      if (/^[):,\s|]+0\|?$/.test(unq) || /^["']?c["']?\s*,\s*0\|?$/i.test(unq)) { changed = true; continue; }
      if (/^\|\s*["']?c["']?\s*,\s*0\s*\|$/i.test(t)) { changed = true; continue; }
      if (/^\{\s*\d+\s*:\s*0\s*\}$/.test(t) || /^\{\s*0\s*\}$/.test(t)) { changed = true; continue; }
      if (/^\):?\d+$/.test(unq) || /^,\d+\|$/.test(unq)) { changed = true; continue; }
      if (/^\d+\|$/.test(unq)) { changed = true; continue; }
      /* Bare header leftovers that are not brace / quoted parts. */
      if (/^\d+$/.test(unq) && !/^\{/.test(t)) { changed = true; continue; }
      kept.push(t);
    }
    if (!changed && kept.length === toks.length) return { serial: full, changed: false };
    return { serial: head + (kept.length ? ' ' + kept.join(' ') : ''), changed: true };
  }
  try { window.stxStripSpawnUnsafeJunkTokens = stxStripSpawnUnsafeJunkTokens; } catch (_) {}

  /**
   * Move the first rarity part token to the front of the || tail (spawn-order repair only).
   */
  function stxReorderRarityTokenFirstInSerial(fullSerial){
    const full = String(fullSerial || '').trim();
    const dbl = full.indexOf('||');
    if (dbl < 0) return { serial: full, changed: false };
    const head = full.slice(0, dbl + 2).replace(/\s+$/, '');
    const toks = (typeof parseImportTokenList === 'function') ? parseImportTokenList(full) : [];
    if (!toks.length) return { serial: full, changed: false };
    let rarityIdx = -1;
    for (let i = 0; i < toks.length; i++) {
      try {
        const part = (typeof tryResolveToken === 'function') ? tryResolveToken(toks[i]) : null;
        if (part && String(part.partType || '').trim().toLowerCase() === 'rarity') {
          rarityIdx = i;
          break;
        }
      } catch (_) {}
    }
    if (rarityIdx < 0 || rarityIdx === 0) return { serial: full, changed: false };
    const rarityTok = toks.splice(rarityIdx, 1)[0];
    toks.unshift(rarityTok);
    return { serial: head + ' ' + toks.join(' '), changed: true };
  }
  try { window.stxReorderRarityTokenFirstInSerial = stxReorderRarityTokenFirstInSerial; } catch (_) {}

  /**
   * Shared Ready / Modded / Needs fix chip on Generated Item Code + floating panel.
   * Modding-first: warnings still convert; hardFails block convert.
   */
  function stxUpdateSerialHealthUi(deserRaw){
    let deser = String(deserRaw != null ? deserRaw : '').trim();
    if (!deser) {
      try { deser = String((typeof getSharedDeserialized === 'function') ? getSharedDeserialized() : '').trim(); } catch (_) { deser = ''; }
    }
    const chipIds = ['ccSerialHealthChip', 'ccSerialHealthChipFloat'];
    const msgIds = ['ccSerialHealthMsg', 'ccSerialHealthMsgFloat'];
    const fixIds = ['ccFixItemSerialBtn', 'ccFixItemSerialBtnFloat'];
    const setAll = (chipText, chipMod, msg, showFix) => {
      for (let i = 0; i < chipIds.length; i++) {
        const chip = document.getElementById(chipIds[i]);
        if (!chip) continue;
        chip.textContent = chipText;
        chip.className = 'cc-serial-health__chip cc-serial-health__chip--' + chipMod;
      }
      for (let j = 0; j < msgIds.length; j++) {
        const msgEl = document.getElementById(msgIds[j]);
        if (msgEl) msgEl.textContent = msg;
      }
      for (let k = 0; k < fixIds.length; k++) {
        const btn = document.getElementById(fixIds[k]);
        if (btn) btn.hidden = !showFix;
      }
    };
    if (!deser || deser.indexOf('||') < 0) {
      setAll('No item', 'idle', 'Build or paste a serial to see convert health.', false);
      return { status: 'idle' };
    }
    const pre = stxPreflightDeserializedForConvert(deser);
    if (!pre.ok) {
      const detail = (pre.hardFails && pre.hardFails[0]) ? pre.hardFails[0] : 'Serial will not convert safely';
      setAll('Needs fix', 'blocked', detail, true);
      return { status: 'blocked', pre: pre };
    }
    if (pre.warnings && pre.warnings.length) {
      setAll('Modded', 'modded', pre.warnings[0] + ' — convert still allowed (Quick fix will not de-mod).', true);
      return { status: 'modded', pre: pre };
    }
    setAll('Ready', 'ok', 'Looks convert-safe. Modded parts are fine; Quick fix only repairs spawn junk.', false);
    return { status: 'ok', pre: pre };
  }
  try { window.stxUpdateSerialHealthUi = stxUpdateSerialHealthUi; } catch (_) {}

  /**
   * Quick fix: spawn-safe repair only — sanitize cosmetics, strip junk / duplicated headers, rarity-first, re-pack.
   * Does NOT pin barrels, strip stacks, or force legit pools.
   */
  function stxFixCurrentItemSerial(){
    let deser = '';
    try { deser = String((typeof getSharedDeserialized === 'function') ? getSharedDeserialized() : '').trim(); } catch (_) {}
    if (!deser || deser.indexOf('||') < 0) {
      try {
        const fl = document.getElementById('floating-output-code');
        const fv = fl ? String(fl.value || '').trim() : '';
        if (fv.indexOf('||') >= 0) deser = fv;
      } catch (_) {}
    }
    if (!deser || deser.indexOf('||') < 0) {
      stxUpdateSerialHealthUi('');
      return { ok: false, reason: 'no-serial' };
    }

    /* Prefer the longest valid || serial if panels diverged. */
    try {
      const candidates = [];
      const pushC = (v) => {
        const s = String(v || '').trim();
        if (s && s.indexOf('||') >= 0) candidates.push(s);
      };
      pushC(deser);
      try { pushC(document.getElementById('guidedOutputDeserialized') && document.getElementById('guidedOutputDeserialized').value); } catch (_) {}
      try { pushC($('outCode') && $('outCode').value); } catch (_) {}
      try { pushC(document.getElementById('floating-output-code') && document.getElementById('floating-output-code').value); } catch (_) {}
      candidates.sort((a, b) => b.length - a.length);
      if (candidates[0]) deser = candidates[0];
    } catch (_) {}

    let changed = false;
    try {
      const san = stxSanitizeCosmeticSpawnTokensInSerial(deser);
      if (san && san.changed && san.serial) {
        deser = String(san.serial).trim();
        changed = true;
        if (Array.isArray(san.unresolved) && san.unresolved.length) {
          try { window.__ccSkinUnresolvedCosmetic = san.unresolved[0]; } catch (_) {}
        }
      }
    } catch (_) {}

    try {
      const junk = stxStripSpawnUnsafeJunkTokens(deser);
      if (junk && junk.changed && junk.serial) {
        deser = String(junk.serial).trim();
        changed = true;
      }
    } catch (_) {}

    /* Only reorder when tail has braces — never rewrite a header-only / mangled serial. */
    try {
      const dbl = deser.indexOf('||');
      const tail = dbl >= 0 ? deser.slice(dbl + 2) : '';
      if (/\{/.test(tail)) {
        const ord = stxReorderRarityTokenFirstInSerial(deser);
        if (ord && ord.changed && ord.serial && ord.serial.indexOf('||') >= 0) {
          const ot = ord.serial.slice(ord.serial.indexOf('||') + 2);
          /* Guard: reordered result must not reintroduce a second || header blob. */
          if ((ot.match(/\|\|/g) || []).length === 0) {
            deser = String(ord.serial).trim();
            changed = true;
          }
        }
      }
    } catch (_) {}

    const source = (window.__CC_LAST_CODE_TARGET === 'guided') ? 'guided' : 'simple';
    try {
      writeSharedItemCode({ deser: deser, source: source, force: true });
    } catch (_) {}

    const health = stxUpdateSerialHealthUi(deser);
    try {
      const banner = document.getElementById('dsStatus');
      if (banner) {
        if (health && health.status === 'blocked') banner.textContent = 'Quick fix incomplete: ' + ((health.pre && health.pre.hardFails && health.pre.hardFails[0]) || 'still blocked');
        else if (changed) banner.textContent = 'Quick fix applied (spawn-safe only — modded stacks kept)';
        else banner.textContent = 'Nothing to quick-fix (or already clean)';
      }
    } catch (_) {}
    return { ok: !(health && health.status === 'blocked'), changed: changed, health: health };
  }
  try { window.stxFixCurrentItemSerial = stxFixCurrentItemSerial; } catch (_) {}

  function stxApplyValidBase85ToSerialFields(packed, outB85El, gSerEl, deserForPlausibility){
    const b85 = String(packed || '').trim();
    const valid = (typeof window.ccIsValidStoredBase85 === 'function')
      ? window.ccIsValidStoredBase85(b85)
      : !!(b85 && b85.indexOf('@U') === 0 && b85.indexOf(',') < 0 && b85.indexOf('||') < 0 && b85.length >= 10);
    if (!valid) return false;
    if (deserForPlausibility != null && String(deserForPlausibility).trim()
        && typeof window.ccBase85PlausibleForDeser === 'function'
        && !window.ccBase85PlausibleForDeser(b85, deserForPlausibility)) {
      return false;
    }
    try { if (outB85El) outB85El.value = b85; } catch (_) {}
    try {
      if (gSerEl) {
        gSerEl.value = b85;
        gSerEl.__ccImportedValue = b85;
      }
    } catch (_) {}
    try { if (typeof window.__ccSyncCodeCharCounts === 'function') window.__ccSyncCodeCharCounts(); } catch (_) {}
    return true;
  }

  function stxClearImplausibleSerialFields(deser, outB85El, gSerEl){
    const d = String(deser || '').trim();
    const outB85 = (outB85El != null) ? outB85El : $('outCodeB85');
    const gSer = (gSerEl != null) ? gSerEl : document.getElementById('guidedOutputSerial');
    const cur = String((gSer && gSer.value) || (outB85 && outB85.value) || '').trim();
    if (!cur) return false;
    if (typeof window.ccBase85PlausibleForDeser !== 'function') return false;
    if (window.ccBase85PlausibleForDeser(cur, d)) return false;
    try { if (outB85) outB85.value = ''; } catch (_) {}
    try {
      if (gSer) {
        gSer.value = '';
        /* Keep imported lock only for plausible packs. */
        if (gSer.__ccImportedValue && !window.ccBase85PlausibleForDeser(String(gSer.__ccImportedValue), d)) {
          gSer.__ccImportedValue = null;
        }
      }
    } catch (_) {}
    return true;
  }

  /**
   * Local packer used by auto-fill — same strength as Convert's localBest:
   * normalize → ensureBase85SerialForYamlSave → serializeToBase85 (raw + normalized).
   * Rejects alphabet-valid but truncated packs (header-only @U for huge deser).
   */
  function stxPackDeserializedToBase85Local(deserRaw){
    const deser = String(deserRaw || '').trim();
    if (!deser || deser.indexOf('||') < 0) return '';
    const isAcceptable = (b)=>{
      const t = String(b || '').trim();
      if (!t) return false;
      if (typeof window.ccIsValidStoredBase85 === 'function') {
        if (!window.ccIsValidStoredBase85(t)) return false;
      } else if (!(t.indexOf('@U') === 0 && t.indexOf(',') < 0 && t.indexOf('||') < 0 && t.length >= 10)) {
        return false;
      }
      if (typeof window.ccBase85PlausibleForDeser === 'function'
          && !window.ccBase85PlausibleForDeser(t, deser)) {
        return false;
      }
      return true;
    };
    let norm = deser;
    if (typeof window.__stxNormalizeDeserializedInput === 'function') {
      try {
        const n = window.__stxNormalizeDeserializedInput(deser);
        if (n) norm = String(n).trim();
      } catch (_) {}
    }
    if (typeof window.ensureBase85SerialForYamlSave === 'function') {
      try {
        let packed = window.ensureBase85SerialForYamlSave(deser);
        if (isAcceptable(packed)) return String(packed).trim();
        if (norm && norm !== deser) {
          packed = window.ensureBase85SerialForYamlSave(norm);
          if (isAcceptable(packed)) return String(packed).trim();
        }
      } catch (_) {}
    }
    if (typeof window.serializeToBase85 === 'function') {
      try {
        let packed = window.serializeToBase85(deser, undefined, true);
        if (isAcceptable(packed)) return String(packed).trim();
        if (norm && norm !== deser) {
          packed = window.serializeToBase85(norm, undefined, true);
          if (isAcceptable(packed)) return String(packed).trim();
        }
      } catch (_) {}
    }
    return '';
  }
  try { window.stxPackDeserializedToBase85Local = stxPackDeserializedToBase85Local; } catch (_) {}

  /**
   * Best-effort pack for auto-fill: local first, then shared Convert helper / remote.
   * Returns a Promise<string> of a valid+plausible @U or ''.
   */
  function stxPackDeserializedToBase85BestEffort(deserRaw){
    const deser = String(deserRaw || '').trim();
    if (!deser || deser.indexOf('||') < 0) return Promise.resolve('');
    try {
      const pre = (typeof stxPreflightDeserializedForConvert === 'function')
        ? stxPreflightDeserializedForConvert(deser)
        : { ok: true };
      if (pre && pre.ok === false) return Promise.resolve('');
    } catch (_) {}
    const accept = (packed)=>{
      const t = String(packed || '').trim();
      if (!t) return '';
      if (typeof window.ccIsValidStoredBase85 === 'function') {
        if (!window.ccIsValidStoredBase85(t)) return '';
      } else if (!(t.indexOf('@U') === 0 && t.length >= 10)) {
        return '';
      }
      if (typeof window.ccBase85PlausibleForDeser === 'function'
          && !window.ccBase85PlausibleForDeser(t, deser)) {
        return '';
      }
      return t;
    };
    const localHit = stxPackDeserializedToBase85Local(deser);
    if (localHit) return Promise.resolve(localHit);
    if (typeof window.serializeDeserializedToBase85BestEffort === 'function') {
      return Promise.resolve(window.serializeDeserializedToBase85BestEffort(deser)).then(function (packed) {
        return accept(packed);
      }).catch(function () { return ''; });
    }
    if (typeof window.ccSerializeDeserializedRemote === 'function') {
      return window.ccSerializeDeserializedRemote(deser, { timeoutMs: 900 }).then(function (remote) {
        return accept(remote);
      }).catch(function () { return ''; });
    }
    return Promise.resolve('');
  }
  try { window.stxPackDeserializedToBase85BestEffort = stxPackDeserializedToBase85BestEffort; } catch (_) {}

  /**
   * Auto-fill Serial (BL-base85) from deserialized. Used on import + shared writes.
   * Retries after deferred Base85 scripts load when packer is not ready yet.
   * Uses a generation token so a late header-only pack cannot overwrite a newer full pack.
   */
  function stxFillSerialBase85FromDeser(deserRaw, opts){
    opts = opts || {};
    const deser = String(deserRaw || '').trim();
    if (!deser || deser.indexOf('||') < 0) return false;
    const outB85 = (opts.outB85El != null) ? opts.outB85El : $('outCodeB85');
    const gSer = (opts.gSerEl != null) ? opts.gSerEl : document.getElementById('guidedOutputSerial');
    try { window.__stxB85PackGen = (Number(window.__stxB85PackGen) || 0) + 1; } catch (_) {}
    let packGen = 0;
    try { packGen = Number(window.__stxB85PackGen) || 0; } catch (_) { packGen = 0; }
    try { window.__stxPendingB85Deser = deser; } catch (_) {}
    stxClearImplausibleSerialFields(deser, outB85, gSer);

    const applyPacked = (packed)=>{
      try {
        if (packGen !== Number(window.__stxB85PackGen)) return false;
        const pending = String(window.__stxPendingB85Deser || '').trim();
        if (pending && pending !== deser) return false;
      } catch (_) {}
      if (!stxApplyValidBase85ToSerialFields(packed, outB85, gSer, deser)) return false;
      try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
      return true;
    };

    const tryPackNow = ()=>{
      if (typeof window.serializeToBase85 !== 'function'
          && typeof window.ensureBase85SerialForYamlSave !== 'function'
          && typeof window.serializeDeserializedToBase85BestEffort !== 'function') {
        return false;
      }
      try {
        const pre = (typeof stxPreflightDeserializedForConvert === 'function')
          ? stxPreflightDeserializedForConvert(deser)
          : { ok: true };
        if (pre && pre.ok === false) return true; /* don't keep retrying a blocked serial */
        const localHit = stxPackDeserializedToBase85Local(deser);
        if (localHit) return applyPacked(localHit);
        const weight = (typeof window.ccDeserializedPayloadWeight === 'function')
          ? window.ccDeserializedPayloadWeight(deser)
          : { heavy: deser.length > 12000 };
        /* Local miss — async best-effort (normalize / remote) same as floating Convert. */
        try { if (gSer) gSer.setAttribute('aria-busy', 'true'); } catch (_) {}
        const runBest = function () {
          stxPackDeserializedToBase85BestEffort(deser).then(function (packed) {
            try { if (gSer && packGen === Number(window.__stxB85PackGen)) gSer.removeAttribute('aria-busy'); } catch (_) {}
            applyPacked(packed);
          }).catch(function () {
            try { if (gSer && packGen === Number(window.__stxB85PackGen)) gSer.removeAttribute('aria-busy'); } catch (_) {}
          });
        };
        if (weight.heavy) setTimeout(runBest, 0);
        else runBest();
        return true;
      } catch (_) {
        return false;
      }
    };

    if (tryPackNow()) return true;

    const flushPending = ()=>{
      let pending = '';
      try { pending = String(window.__stxPendingB85Deser || '').trim(); } catch (_) {}
      if (!pending) pending = deser;
      if (!pending || pending.indexOf('||') < 0) return;
      if (typeof window.serializeToBase85 !== 'function'
          && typeof window.ensureBase85SerialForYamlSave !== 'function') return;
      try {
        if (packGen !== Number(window.__stxB85PackGen)) return;
      } catch (_) {}
      try {
        const pre = (typeof stxPreflightDeserializedForConvert === 'function')
          ? stxPreflightDeserializedForConvert(pending)
          : { ok: true };
        if (pre && pre.ok === false) {
          try { window.__stxPendingB85Deser = ''; } catch (_) {}
          return;
        }
        stxPackDeserializedToBase85BestEffort(pending).then(function (packed) {
          if (applyPacked(packed)) {
            try { window.__stxPendingB85Deser = ''; } catch (_) {}
          }
        }).catch(function () {});
      } catch (_) {}
    };

    try {
      if (typeof window.stxEnsureDeferredCore === 'function') {
        Promise.resolve(window.stxEnsureDeferredCore()).then(flushPending).catch(function () {});
      }
    } catch (_) {}
    try {
      if (typeof window.stxEnsureFullAppScripts === 'function') {
        Promise.resolve(window.stxEnsureFullAppScripts()).then(flushPending).catch(function () {});
      }
    } catch (_) {}
    try {
      window.addEventListener('stx:deferred-core-ready', flushPending, { once: true });
    } catch (_) {}
    try {
      window.addEventListener('stx:full-scripts-ready', flushPending, { once: true });
    } catch (_) {}
    /* Fallback poll — Base85 may land between events. */
    let polls = 0;
    const pollId = setInterval(function () {
      polls++;
      if (typeof window.serializeToBase85 === 'function'
          || typeof window.ensureBase85SerialForYamlSave === 'function') {
        clearInterval(pollId);
        flushPending();
      } else if (polls >= 40) {
        clearInterval(pollId);
      }
    }, 100);
    return false;
  }
  try { window.stxFillSerialBase85FromDeser = stxFillSerialBase85FromDeser; } catch (_) {}

  /**
   * Write deserialized (+ optional base85) to the shared panel and Simple mirror IDs.
   * opts: { deser, b85, source: 'simple'|'guided', skipB85, force, allowEmpty }
   */
  function writeSharedItemCode(opts){
    opts = opts || {};
    if (window.__ccIsHydrating && !opts.force) return false;
    if (window.__CC_IMPORT_IN_PROGRESS && !opts.force && !window.__CC_BUILDER_HANDOFF) return false;

    let deser = String(opts.deser != null ? opts.deser : '').trim();
    try {
      const san = stxSanitizeCosmeticSpawnTokensInSerial(deser);
      if (san && san.changed && san.serial) deser = String(san.serial).trim();
    } catch (_) {}
    const source = (opts.source === 'guided') ? 'guided' : 'simple';
    const outEl = $('outCode');
    const gDes = document.getElementById('guidedOutputDeserialized');
    const outB85 = $('outCodeB85');
    const gSer = document.getElementById('guidedOutputSerial');
    /* Never treat a header-only / truncated @U as a fallback once deser has a real part tail. */
    const prevValidB85 = (()=>{
      try {
        const cur = String((gSer && gSer.value) || (outB85 && outB85.value) || '').trim();
        if (typeof window.ccIsValidStoredBase85 === 'function' && !window.ccIsValidStoredBase85(cur)) return '';
        if (typeof window.ccIsValidStoredBase85 !== 'function'
            && !(cur && cur.indexOf('@U') === 0 && cur.length >= 10)) return '';
        if (deser && deser.indexOf('||') >= 0
            && typeof window.ccBase85PlausibleForDeser === 'function'
            && !window.ccBase85PlausibleForDeser(cur, deser)) {
          return '';
        }
        return cur;
      } catch (_) {}
      return '';
    })();
    try { stxClearImplausibleSerialFields(deser, outB85, gSer); } catch (_) {}

    if (gDes && !opts.force && deser) {
      const existing = String(gDes.value || '').trim();
      if (gDes.__ccUserTailEdit && existing.indexOf('||') >= 0 && existing.length > deser.length + 15) {
        if (outEl && existing) outEl.value = existing;
        try { window.__CC_LAST_CODE_TARGET = source; } catch (_) {}
        return false;
      }
      if (gDes.__ccImportedValue && existing === String(gDes.__ccImportedValue).trim()
          && existing.indexOf('||') >= 0 && existing.length > deser.length + 5) {
        if (outEl && existing) outEl.value = existing;
        try { window.__CC_LAST_CODE_TARGET = source; } catch (_) {}
        return false;
      }
    }

    if (deser || opts.allowEmpty) {
      if (outEl) outEl.value = deser;
      if (gDes) gDes.value = deser;
    }

    try { window.__CC_LAST_CODE_TARGET = source; } catch (_) {}

    const providedB85 = opts.b85 != null ? String(opts.b85).trim() : '';
    if (providedB85) {
      if (!stxApplyValidBase85ToSerialFields(providedB85, outB85, gSer, deser) && prevValidB85) {
        stxApplyValidBase85ToSerialFields(prevValidB85, outB85, gSer, deser);
      }
    } else if (!opts.skipB85 && deser && deser.indexOf('||') >= 0) {
      const packerReady = (typeof window.serializeToBase85 === 'function')
        || (typeof window.ensureBase85SerialForYamlSave === 'function')
        || (typeof window.serializeDeserializedToBase85BestEffort === 'function');
      if (packerReady) {
        const pre = stxPreflightDeserializedForConvert(deser);
        if (!pre.ok) {
          try {
            const banner = document.getElementById('ccSerialPreflightWarn') || document.getElementById('dsStatus');
            if (banner) banner.textContent = 'Convert blocked: ' + (pre.hardFails[0] || 'invalid serial');
          } catch (_) {}
          /* Do not re-apply a short sticky serial when convert is blocked for a large item. */
          if (prevValidB85) stxApplyValidBase85ToSerialFields(prevValidB85, outB85, gSer, deser);
          try { if (typeof window.__ccSyncCodeCharCounts === 'function') window.__ccSyncCodeCharCounts(); } catch (_) {}
          try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
          try { stxUpdateSerialHealthUi(deser); } catch (_) {}
          return true;
        }
        if (pre.warnings && pre.warnings.length) {
          try {
            const banner = document.getElementById('ccSerialPreflightWarn') || document.getElementById('dsStatus');
            if (banner) banner.textContent = pre.warnings[0];
          } catch (_) {}
        }
        const deserForB85 = deser;
        try { window.__stxB85PackGen = (Number(window.__stxB85PackGen) || 0) + 1; } catch (_) {}
        let packGen = 0;
        try { packGen = Number(window.__stxB85PackGen) || 0; } catch (_) { packGen = 0; }
        try { window.__stxPendingB85Deser = deserForB85; } catch (_) {}
        const applyB85 = function (packed) {
          try {
            if (gSer) {
              gSer.removeAttribute('aria-busy');
              if (gSer.placeholder === 'Packing…') gSer.placeholder = '—';
            }
            if (outB85 && outB85.placeholder === 'Packing…') outB85.placeholder = '—';
          } catch (_) {}
          try {
            if (packGen !== Number(window.__stxB85PackGen)) return;
            const pending = String(window.__stxPendingB85Deser || '').trim();
            if (pending && pending !== deserForB85) return;
          } catch (_) {}
          if (!stxApplyValidBase85ToSerialFields(packed, outB85, gSer, deserForB85)) {
            /* Prefer blank Serial over a truncated header-only @U for this deser. */
            if (prevValidB85) stxApplyValidBase85ToSerialFields(prevValidB85, outB85, gSer, deserForB85);
          }
        };
        const weight = (typeof window.ccDeserializedPayloadWeight === 'function')
          ? window.ccDeserializedPayloadWeight(deserForB85)
          : { heavy: deserForB85.length > 12000 };
        try {
          if (window.__stxB85RefreshTimer) clearTimeout(window.__stxB85RefreshTimer);
        } catch (_) {}
        const packDelay = opts.force ? 0 : (weight.heavy ? 0 : 80);
        window.__stxB85RefreshTimer = setTimeout(function () {
          window.__stxB85RefreshTimer = 0;
          try {
            if (packGen !== Number(window.__stxB85PackGen)) return;
          } catch (_) {}
          try {
            if (gSer) {
              gSer.setAttribute('aria-busy', 'true');
              if (!prevValidB85) gSer.placeholder = 'Packing…';
            }
            if (outB85 && !prevValidB85) outB85.placeholder = 'Packing…';
            /* Same path as floating Convert: local normalize/ensure, then best-effort/remote. */
            stxPackDeserializedToBase85BestEffort(deserForB85).then(function (packed) {
              applyB85(packed);
            }).catch(function () {
              applyB85('');
            });
          } catch (_) {
            applyB85('');
          }
        }, packDelay);
      } else {
        /* Packer not loaded yet (deferred) — queue fill so Serial is not left blank after import. */
        stxFillSerialBase85FromDeser(deser, { outB85El: outB85, gSerEl: gSer });
      }
    }

    try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
    try { if (typeof window.__ccSyncCodeCharCounts === 'function') window.__ccSyncCodeCharCounts(); } catch (_) {}
    try { stxUpdateSerialHealthUi(deser); } catch (_) {}
    return true;
  }
  try { window.writeSharedItemCode = writeSharedItemCode; } catch (_) {}

  /**
   * Continue the current item when switching Simple ↔ Guided.
   * fromMode/toMode: 'simple' | 'guided'. No-op when there is no live serial.
   */
  function __ccHandoffBuilderMode(fromMode, toMode){
    toMode = (toMode === 'guided') ? 'guided' : 'simple';
    if (window.__CC_IMPORT_IN_PROGRESS || window.__ccIsHydrating) return;
    const deser = getSharedDeserialized();
    if (!deser || deser.indexOf('||') < 0) {
      try { window.__CC_LAST_CODE_TARGET = toMode; } catch (_) {}
      return;
    }

    window.__CC_BUILDER_HANDOFF = true;
    try {
      writeSharedItemCode({ deser: deser, source: toMode, force: true });

      if (toMode === 'guided') {
        try { window.__CC_LAST_CODE_TARGET = 'guided'; } catch (_) {}
        try {
          const gDes = document.getElementById('guidedOutputDeserialized');
          if (gDes) {
            gDes.value = deser;
            gDes.__ccImportedValue = deser;
            gDes.__ccUserTailEdit = false;
          }
        } catch (_) {}
        try {
          if (stxSimpleBuilderHasActiveBuild() && typeof window.__ccHydrateGuidedSlotsFromSimpleState === 'function') {
            window.__ccHydrateGuidedSlotsFromSimpleState();
          } else if (typeof window.__ccHydrateGuidedSlotSelectsFromSerial === 'function') {
            window.__ccHydrateGuidedSlotSelectsFromSerial(deser);
          }
        } catch (_) {}
        try { if (typeof window.syncGuidedVisibility === 'function') window.syncGuidedVisibility(); } catch (_) {}
        try {
          if (typeof window.syncGuidedFloatingOutputFromDeser === 'function') {
            window.syncGuidedFloatingOutputFromDeser();
          }
        } catch (_) {}
      } else {
        try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_) {}
        try {
          if (typeof window.importTokens === 'function') {
            /* 'simple' keeps Guided fields; shared panel already mirrored. */
            window.importTokens(deser, 'simple');
          }
        } catch (_) {}
      }
    } finally {
      setTimeout(function () {
        try { window.__CC_BUILDER_HANDOFF = false; } catch (_) {}
      }, 280);
    }
  }
  try { window.__ccHandoffBuilderMode = __ccHandoffBuilderMode; } catch (_) {}

  /**
   * Clear every visible generated-code surface when starting a new item
   * (item type / manufacturer / weapon type). Simple used to only clear its
   * own boxes later via idle refreshOutputs, leaving Guided + floating stale.
   */
  function clearAllGeneratedCodeForNewItem(opts){
    opts = opts || {};
    if (window.__CC_IMPORT_IN_PROGRESS && !opts.force) return;
    try { clearImportedOutputLock(); } catch (_) {}
    try { if (typeof window.clearGuidedImportLock === 'function') window.clearGuidedImportLock(); } catch (_) {}

    try {
      if ($('outCode')) $('outCode').value = '';
      if ($('outCodeB85')) $('outCodeB85').value = '';
      if ($('outList')) $('outList').value = '';
      if ($('outJson')) $('outJson').value = '';
    } catch (_) {}
    try {
      if (window.__stxB85RefreshTimer) {
        clearTimeout(window.__stxB85RefreshTimer);
        window.__stxB85RefreshTimer = 0;
      }
    } catch (_) {}

    try {
      const guidedDeser = document.getElementById('guidedOutputDeserialized');
      const guidedSerial = document.getElementById('guidedOutputSerial');
      if (guidedDeser) {
        guidedDeser.__ccUserTailEdit = false;
        guidedDeser.__ccImportedValue = null;
        guidedDeser.value = '';
      }
      if (guidedSerial) {
        guidedSerial.__ccImportedValue = null;
        guidedSerial.value = '';
      }
    } catch (_) {}

    if (opts.clearImportBox) {
      try { if ($('importBox')) $('importBox').value = ''; } catch (_) {}
    }

    try {
      if (opts.source === 'simple') window.__CC_LAST_CODE_TARGET = 'simple';
      else if (opts.source === 'guided') window.__CC_LAST_CODE_TARGET = 'guided';
    } catch (_) {}

    try {
      if (typeof window.resetFloatingOutputMirror === 'function') {
        window.resetFloatingOutputMirror(true);
      } else if (typeof window.syncFloatingOutput === 'function') {
        window.syncFloatingOutput(true);
      }
    } catch (_) {}
    try { if (typeof window.__ccSyncCodeCharCounts === 'function') window.__ccSyncCodeCharCounts(); } catch (_) {}
  }
  try { window.clearAllGeneratedCodeForNewItem = clearAllGeneratedCodeForNewItem; } catch (_) {}

  /** Parse optional `9, 1|` / `10, 1|` header segments (before `||`, after level). */
  function stxParseHeaderModifierFlags(headStr) {
    const out = { lockFirmware: false, buybackFlag: false };
    const segments = String(headStr || '').trim().split('|').map(x => String(x || '').trim()).filter(Boolean);
    for (let si = 1; si < segments.length; si++) {
      const sm = segments[si].match(/^(\d+)\s*,\s*(\d+)\s*$/);
      if (!sm) continue;
      const sectionId = Number(sm[1]);
      const sectionValue = Number(sm[2]);
      if (sectionId === 9 && sectionValue === 1) out.lockFirmware = true;
      else if (sectionId === 10 && sectionValue === 1) out.buybackFlag = true;
    }
    return out;
  }

  function stxApplySerialModifierFlagsToUi(flags) {
    const lock = !!(flags && flags.lockFirmware);
    const buy = !!(flags && flags.buybackFlag);
    if (state) {
      state.lockFirmware = lock;
      state.buybackFlag = buy;
    }
    if ($('firmwareLock')) $('firmwareLock').checked = lock;
    if ($('buybackFlag')) $('buybackFlag').checked = buy;
    try {
      const gf = document.getElementById('ccGuidedFirmwareLockFlag');
      const gb = document.getElementById('ccGuidedBuybackFlag');
      if (gf) gf.checked = lock;
      if (gb) gb.checked = buy;
    } catch (_e) {}
  }

  /** Build header suffix after `{family}, 0, 1, {level}|` (optional lock/buyback, then seed `||`). */
  function stxBuildSerialHeaderSuffix(seed, lockFirmware, buybackFlag) {
    const sd = Number(seed);
    const hasSeed = Number.isFinite(sd) && sd !== 0;
    let out = '';
    if (lockFirmware) out += ' 9, 1|';
    if (buybackFlag) out += ' 10, 1|';
    if (hasSeed || (!lockFirmware && !buybackFlag)) {
      const seedVal = hasSeed ? sd : (Number.isFinite(sd) ? sd : 0);
      out += ` 2, ${seedVal}||`;
    } else {
      out += '|';
    }
    return out;
  }

  /** Remove modifier segments wrongly placed at the start of the parts tail (after `||`). */
  function stxStripMisplacedModifierSegmentsFromTail(tail) {
    let t = String(tail || '').replace(/^\s+/, '');
    let changed = true;
    while (changed) {
      changed = false;
      const m = t.match(/^(\d+)\s*,\s*(\d+)\s*\|\s*/);
      if (!m) break;
      const sectionId = Number(m[1]);
      const sectionValue = Number(m[2]);
      if ((sectionId === 9 && sectionValue === 1) || (sectionId === 10 && sectionValue === 1)) {
        t = t.slice(m[0].length).replace(/^\s+/, '');
        changed = true;
      }
    }
    return t;
  }

  function stxExtractSeedFromHeaderHead(headStr) {
    const segments = String(headStr || '').trim().split('|').map(x => String(x || '').trim()).filter(Boolean);
    for (let si = 1; si < segments.length; si++) {
      const sm = segments[si].match(/^2\s*,\s*(\d+)\s*$/);
      if (sm) {
        const sd = Number(sm[1]);
        if (Number.isFinite(sd)) return sd;
      }
    }
    return 0;
  }

  /** Insert/remove `9, 1|` / `10, 1|` in the header (before `||`), not in the parts tail. */
  function stxPatchSerialModifierFlags(code, lockFirmware, buybackFlag) {
    const raw = String(code || '').trim();
    if (!raw) return raw;
    const dbl = raw.indexOf('||');
    if (dbl < 0) return raw;
    const head = raw.slice(0, dbl);
    let tail = stxStripMisplacedModifierSegmentsFromTail(raw.slice(dbl + 2));
    const seed = stxExtractSeedFromHeaderHead(head);
    const levelMatch = head.match(/^(\s*\d+\s*,\s*0\s*,\s*1\s*,\s*\d+\s*\|)/);
    if (!levelMatch) return raw;
    const base = levelMatch[1].replace(/\s+/g, ' ').trim();
    const suffixBody = stxBuildSerialHeaderSuffix(seed, lockFirmware, buybackFlag).replace(/\|\|$/, '');
    const rebuilt = base + suffixBody + '||' + (tail ? (' ' + String(tail).replace(/^\s+/, '')) : '');
    return String(rebuilt || '').replace(/\s+\|$/, '|');
  }

  function stxReadSerialModifierFlags() {
    const lockFirmware = !!(
      (state && state.lockFirmware) ||
      ($('firmwareLock') && $('firmwareLock').checked) ||
      (document.getElementById('ccGuidedFirmwareLockFlag') && document.getElementById('ccGuidedFirmwareLockFlag').checked)
    );
    const buybackFlag = !!(
      (state && state.buybackFlag) ||
      ($('buybackFlag') && $('buybackFlag').checked) ||
      (document.getElementById('ccGuidedBuybackFlag') && document.getElementById('ccGuidedBuybackFlag').checked)
    );
    return { lockFirmware, buybackFlag };
  }

  function stxPatchSerialModifierFlagsIntoOutputs() {
    const flags = stxReadSerialModifierFlags();
    const ids = ['outCode', 'guidedOutputDeserialized'];
    for (let i = 0; i < ids.length; i++) {
      const el = document.getElementById(ids[i]);
      if (!el) continue;
      const cur = String(el.value || '').trim();
      if (!cur || cur.indexOf('||') < 0) continue;
      const next = stxPatchSerialModifierFlags(cur, flags.lockFirmware, flags.buybackFlag);
      if (next && next !== cur) el.value = next;
    }
  }
  try {
    window.stxPatchSerialModifierFlags = stxPatchSerialModifierFlags;
    window.stxPatchSerialModifierFlagsIntoOutputs = stxPatchSerialModifierFlagsIntoOutputs;
    window.stxBuildSerialHeaderSuffix = stxBuildSerialHeaderSuffix;
    window.stxParseHeaderModifierFlags = stxParseHeaderModifierFlags;
    window.stxApplySerialModifierFlagsToUi = stxApplySerialModifierFlagsToUi;
    window.stxReadSerialModifierFlags = stxReadSerialModifierFlags;
  } catch (_) {}

function resetAll(){
    clearImportedOutputLock();
    state.itemType = 'Weapon';
    state.manufacturer = '';
    state.weaponType = '';
    state.level = 60;
    state.rarity = '';
    state.swapBodyLegendary = false;
    state.__seedEnabled = false;
    state.buybackFlag = false;
    state.lockFirmware = false;
    if ($('buybackFlag')) $('buybackFlag').checked = false;
    if ($('firmwareLock')) $('firmwareLock').checked = false;
    try {
      const gf = document.getElementById('ccGuidedFirmwareLockFlag');
      const gb = document.getElementById('ccGuidedBuybackFlag');
      if (gf) gf.checked = false;
      if (gb) gb.checked = false;
    } catch (_e) {}
    stxSyncAllPartsToggleUi(false);
    state.seedAuto = null;
    state.seedKey = null;
    if ($('seedInput')) $('seedInput').value = '';
    if ($('skinSelect')) $('skinSelect').value = '';
    if ($('camoSelect')) $('camoSelect').value = '';
    state.mainPart = null;
    clearBuilderState();
    clearAllGeneratedCodeForNewItem({ source: 'simple', clearImportBox: true, force: true });
    refreshTopSelectors();
    $('builder').innerHTML = '';
    $('builderEmpty').style.display = '';
    $('detectedCat').textContent = '-';
    refreshOutputs(true);
  }

  function clearParts(){
    state.slots = {};
    state.primaryElement = 'None';
    state.elementStack = [];
    state.dualElementUseMaliwanSwitch = false;
    state.extras = [];
    refreshBuilder();
  }

  let __STX_PART_RESOLVER_CACHE = null;
  function __getStxPartResolverCache() {
    if (__STX_PART_RESOLVER_CACHE) return __STX_PART_RESOLVER_CACHE;
    const all = getAllParts();
    if (!all.length) return null;
    const cache = {
      famId: new Map(),
      idRaw: new Map(),
      singleId: new Map(),
      code: new Map()
    };
    const stripQ = (s)=> String(s ?? '').trim().replace(/^"+|"+$/g, '').trim();
    for (let i = 0; i < all.length; i++) {
      const p = all[i];
      if (!p) continue;
      const fam = Number(p.family != null ? p.family : p.familyId);
      const idn = Number(p.id != null ? p.id : p.itemId);
      if (Number.isFinite(fam) && Number.isFinite(idn)) {
        const key = fam + ':' + idn;
        if (!cache.famId.has(key)) cache.famId.set(key, p);
      }
      const ir = stripQ(p.idRaw ?? p.idraw ?? '');
      if (ir) {
        if (!cache.idRaw.has(ir)) cache.idRaw.set(ir, p);
        if (/^\d+\s*:\s*\d+$/.test(ir)) {
          const ps = ir.split(':');
          const key = Number(ps[0].trim()) + ':' + Number(ps[1].trim());
          if (!cache.famId.has(key)) cache.famId.set(key, p);
        }
      }
      if (p.id != null && /^\d+$/.test(String(p.id))) {
        const sid = String(Number(p.id));
        if (!cache.singleId.has(sid)) cache.singleId.set(sid, p);
      }
      const c = normCode(p.code);
      if (c && !cache.code.has(c)) cache.code.set(c, p);
      const sc = normCode(p.spawnCode || '');
      if (sc && !cache.code.has(sc)) cache.code.set(sc, p);
      const ic = normCode(p.importCode || '');
      if (ic && !cache.code.has(ic)) cache.code.set(ic, p);
    }
    __STX_PART_RESOLVER_CACHE = cache;
    return cache;
  }

  function tryResolveToken(tok){
    const t0 = String(tok).trim();
    if (!t0) return null;

    const cache = __getStxPartResolverCache();
    const stripQ = (s)=> String(s ?? '').trim().replace(/^"+|"+$/g, '').trim();
    const tBare = stripQ(t0);

    if (cache) {
      // {fam:id} or {fam : id}
      var mBrace = tBare.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
      if (mBrace) {
        const key = Number(mBrace[1]) + ':' + Number(mBrace[2]);
        if (cache.famId.has(key)) return cache.famId.get(key);
      }
      // Bare fam:id
      var mBare = tBare.match(/^(\d+)\s*:\s*(\d+)$/);
      if (mBare) {
        const key = Number(mBare[1]) + ':' + Number(mBare[2]);
        if (cache.famId.has(key)) return cache.famId.get(key);
      }
      // Verbatim idRaw
      if (cache.idRaw.has(tBare)) return cache.idRaw.get(tBare);
      // Single id
      if (/^\d+$/.test(tBare)) {
        const sid = String(Number(tBare));
        if (cache.singleId.has(sid)) return cache.singleId.get(sid);
      }
      // Code match
      const tNorm = normCode(tBare);
      if (cache.code.has(tNorm)) return cache.code.get(tNorm);
    }

    // Fallback if cache not ready or missed something
    const all = getAllParts();
    const normIdRawPair = (p)=>{
      var r = stripQ(p.idRaw ?? p.idraw ?? '');
      if (/^\d+\s*:\s*\d+$/.test(r)){
        var ps = r.split(':');
        return String(Number(ps[0].trim())) + ':' + String(Number(ps[1].trim()));
      }
      if (p && p.family != null && (p.id != null || p.itemId != null)){
        var fid = Number(p.family != null ? p.family : p.familyId);
        var iid = Number(p.id != null ? p.id : p.itemId);
        if (Number.isFinite(fid) && Number.isFinite(iid)) return fid + ':' + iid;
      }
      return '';
    };

    var mBraceF = tBare.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
    if (mBraceF){
      const fam = Number(mBraceF[1]);
      const idn = Number(mBraceF[2]);
      const needle = `${fam}:${idn}`;
      var hit = all.find(p => normIdRawPair(p) === needle);
      if (hit) return hit;
      hit = all.find(p => Number(p.family ?? p.familyId) === fam && Number(p.id ?? p.itemId) === idn);
      if (hit) return hit;
    }

    var bareF = tBare.match(/^(\d+)\s*:\s*(\d+)$/);
    if (bareF){
      const fam2 = Number(bareF[1]);
      const idn2 = Number(bareF[2]);
      const needle2 = `${fam2}:${idn2}`;
      let hit2 = all.find(p => normIdRawPair(p) === needle2);
      if (hit2) return hit2;
      hit2 = all.find(p => Number(p.family ?? p.familyId) === fam2 && Number(p.id ?? p.itemId) === idn2);
      if (hit2) return hit2;
    }

    const byIdRaw = all.find(p => stripQ(p.idRaw ?? p.idraw ?? '') === tBare);
    if (byIdRaw) return byIdRaw;

    if (/^\d+$/.test(tBare)){
      const n = Number(tBare);
      const byId = all.find(p => Number(p.id ?? -1) === n);
      if (byId) return byId;
    }

    const tNormF = normCode(tBare);
    const byCode = all.find(p => normCode(p.code) === tNormF || normCode(p.spawnCode || '') === tNormF || normCode(p.importCode || '') === tNormF);
    if (byCode) return byCode;

    return null;
  }

  /** After importTokens: mirror output into Guided, hydrate slot dropdowns, scroll to Guided. */
  function finalizeCcImportToBuilders(targetBuilder){
    try{
      var outEl = $('outCode');
      var outB85El = $('outCodeB85');
      var guidedDeserEl = document.getElementById('guidedOutputDeserialized');
      var guidedSerialEl = document.getElementById('guidedOutputSerial');
      
      var deser = '';
      try{ deser = String((outEl && outEl.value) || '').trim(); }catch(__){ deser = ''; }
      if (!deser){
        try{ deser = String(($('importBox') && $('importBox').value) || '').trim(); }catch(__2){ deser = ''; }
      }
      if (!deser || deser.indexOf('||') < 0) {
        try {
          var gExisting = guidedDeserEl ? String(guidedDeserEl.value || '').trim() : '';
          if (gExisting.indexOf('||') >= 0) deser = gExisting;
        } catch (_) {}
      }

      /* Shared Generated Item Code panel + both builder mirrors — force so import isn't blocked. */
      if (deser && deser.indexOf('||') >= 0) {
        try {
          var src = (targetBuilder === 'simple') ? 'simple' : 'guided';
          writeSharedItemCode({ deser: deser, source: src, force: true, skipB85: false });
        } catch (_) {}
        try {
          var impBoxShared = document.getElementById('importBox');
          if (impBoxShared && String(impBoxShared.value || '').trim() !== deser) impBoxShared.value = deser;
        } catch (_) {}
        try { if (typeof window.__ipiInvalidateSerialCache === 'function') window.__ipiInvalidateSerialCache(); } catch (_) {}
      }
      
  if ((targetBuilder === 'guided' || targetBuilder === 'both' || targetBuilder === 'simple') && guidedDeserEl && deser && deser.indexOf('||') >= 0) {
    if (targetBuilder === 'guided' || targetBuilder === 'both') {
      guidedDeserEl.value = deser;
      guidedDeserEl.__ccImportedValue = deser;
      guidedDeserEl.__ccUserTailEdit = false;
    }
    try {
      var impBox = document.getElementById('importBox');
      if (impBox && String(impBox.value || '').trim() !== deser) impBox.value = deser;
    } catch (_) {}
    try { if (typeof window.__ipiInvalidateSerialCache === 'function') window.__ipiInvalidateSerialCache(); } catch (_) {}
    /* Always auto-fill Serial (BL-base85) on import — wait for packer if still loading. */
    stxFillSerialBase85FromDeser(deser, { outB85El: outB85El, gSerEl: guidedSerialEl });
  }
  
  // Keep Simple #outCode/#outCodeB85 as hidden mirrors of the shared panel (do not blank on guided import).
  if ((targetBuilder === 'guided' || targetBuilder === 'both') && outEl && deser && deser.indexOf('||') >= 0) {
    outEl.value = deser;
  }

      var runHydrate = function(){
        try{
          if (typeof window.__ccHydrateGuidedSlotsFromSimpleState === 'function'){
            window.__ccHydrateGuidedSlotsFromSimpleState();
          }
        }catch(_e2){}
      };
      
      if (targetBuilder === 'guided' || targetBuilder === 'both') {
        if (!window.__CC_IMPORT_HEAVY) {
          runHydrate();
          setTimeout(function(){
            runHydrate();
            try { if (typeof window.syncGuidedVisibility === 'function') window.syncGuidedVisibility(); } catch (_) {}
            try { if (typeof window.refreshGuidedOutput === 'function') window.refreshGuidedOutput(); } catch (_) {}
            try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
          }, 150);
        } else {
          setTimeout(function () {
            try { if (typeof window.syncGuidedVisibility === 'function') window.syncGuidedVisibility(); } catch (_) {}
            try {
              var gDesHeavy = document.getElementById('guidedOutputDeserialized');
              var fullHeavy = gDesHeavy ? String(gDesHeavy.value || '').trim() : '';
              if (fullHeavy && typeof window.__ccHydrateGuidedSlotSelectsFromSerial === 'function') {
                window.__ccHydrateGuidedSlotSelectsFromSerial(fullHeavy);
              }
            } catch (_) {}
            try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
          }, 100);
        }
      }

      if (targetBuilder === 'guided') {
        window.__CC_LAST_CODE_TARGET = 'guided';
        /* Simple/Guided are mutually hidden — switch UI so Import to Guided is actually visible. */
        try {
          if (typeof window.__ccSetBuilderUiMode === 'function') {
            window.__ccSetBuilderUiMode('guided', { scroll: !window.__CC_IMPORT_HEAVY, handoff: false });
          }
        } catch (_modeG) {}
        var anchor = document.getElementById('rebuildGuidedBuilderSection');
        if (anchor && !window.__CC_IMPORT_HEAVY) anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
        try{
          var gi = document.getElementById('ccGuidedItemType');
          if (gi) {
            gi.focus();
            if (state.itemType && gi.value !== state.itemType) {
              gi.value = state.itemType;
              if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(gi);
            }
          }
        }catch(_e3){}
      } else if (targetBuilder === 'simple') {
        window.__CC_LAST_CODE_TARGET = 'simple';
        /* Simple/Guided are mutually hidden — switch UI so Import to Simple is actually visible. */
        try {
          if (typeof window.__ccSetBuilderUiMode === 'function') {
            window.__ccSetBuilderUiMode('simple', { scroll: !window.__CC_IMPORT_HEAVY, handoff: false });
          }
        } catch (_modeS) {}
        /* Mirror into Guided so mode-switch handoff / shared panel stay consistent. */
        if (guidedDeserEl && deser && deser.indexOf('||') >= 0) {
          guidedDeserEl.value = deser;
          guidedDeserEl.__ccImportedValue = deser;
          guidedDeserEl.__ccUserTailEdit = false;
        }
        refreshOutputs(true);
        try {
          if (typeof window.__ccHydrateGuidedSlotSelectsFromSerial === 'function') {
            window.__ccHydrateGuidedSlotSelectsFromSerial(deser);
          }
        } catch (_) {}
      } else if (targetBuilder === 'both') {
        window.__CC_LAST_CODE_TARGET = 'guided';
        refreshOutputs(true);
      }
      
      try{
        if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true);
      }catch(_e4){}
      try {
        if ((targetBuilder === 'guided' || targetBuilder === 'both') && typeof window.syncGuidedFloatingOutputFromDeser === 'function') {
          window.syncGuidedFloatingOutputFromDeser();
        }
      } catch (_) {}
    }catch(_){}
  }

  window.finalizeCcImportToBuilders = finalizeCcImportToBuilders;
  function applyImportedSerialHeaderToUi(full, importTarget){
    try{
      const s = String(full || '').trim();
      const dbl = s.indexOf('||');
      if (dbl < 0) return;
      const head = s.slice(0, dbl);
      const segments = head.split('|').map(x => String(x || '').trim()).filter(Boolean);
      const primary = segments[0] || '';
      const lm = primary.match(/^(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
    if (lm){
      const lvl = Number(lm[4]);
      if (Number.isFinite(lvl)){
        const cap = (typeof window.clampItemLevel === 'function')
          ? window.clampItemLevel(lvl)
          : Math.min(60, Math.max(1, lvl));
        state.level = cap;
        if (!importTarget || importTarget === 'simple' || importTarget === 'both') {
          const le = $('level') || $('level2');
          if (le) le.value = String(cap);
        }
        if (importTarget === 'guided' || importTarget === 'both') {
          const gl = document.getElementById('ccGuidedLevel');
          if (gl) {
             gl.value = String(cap);
             if (!window.__CC_IMPORT_HEAVY) gl.dispatchEvent(new Event('change', { bubbles: true }));
          }
        }
      }
    }
      for (let si = 1; si < segments.length; si++){
        const sm = segments[si].match(/^2\s*,\s*(\d+)\s*$/);
        if (sm){
          const sd = Number(sm[1]);
          if (Number.isFinite(sd)){
            state.__seedEnabled = true;
            state.seedAuto = null;
            const se = $('seedInput');
            if (se) se.value = String(sd);
          }
          break;
        }
      }
      try {
        const modFlags = stxParseHeaderModifierFlags(head);
        stxApplySerialModifierFlagsToUi(modFlags);
      } catch (_eFlags) {}
    }catch(_){}
  }

  /** Repair pasted tails where `{fam:[…]}` lost the opening `{` (e.g. `234:[28 27 … ]}`). Used by import + inspector. */
  function stxNormalizeTruncatedPackedBracketTail(tail){
    let s = String(tail || '');
    s = s.replace(/(^|[\s|])(\d+)\s*:\s*\[\s*([^\]]*?)\s*\]\s*\}/g, (_m, sep, fam, ids) => {
      const compact = String(ids || '').trim().replace(/\s+/g, ' ');
      return String(sep || '') + '{' + fam + ':[' + compact + ']}';
    });
    s = s.replace(/(^|[\s|])(\d+)\s*:\s*\[\s*([^\]]*?)\s*\](?!\s*\})/g, (_m, sep, fam, ids) => {
      const compact = String(ids || '').trim().replace(/\s+/g, ' ');
      return String(sep || '') + '{' + fam + ':[' + compact + ']}';
    });
    return s;
  }
  try { window.__ccNormalizeTruncatedTailBracketTokens = stxNormalizeTruncatedPackedBracketTail; } catch (_) {}

  function parseImportTokenList(raw){
    let s = String(raw || '').trim();
    try {
      const san = stxSanitizeCosmeticSpawnTokensInSerial(s);
      if (san && san.changed && san.serial) s = String(san.serial).trim();
      if (san && Array.isArray(san.unresolved) && san.unresolved.length) {
        try { window.__ccSkinUnresolvedCosmetic = san.unresolved[0]; } catch (_) {}
      }
    } catch (_) {}
    /* Only tokenize the || tail — never the header (`279, 0, 1, 70| 2, 1259`). */
    const di = s.indexOf('||');
    if (di >= 0) {
      s = stxNormalizeTruncatedPackedBracketTail(s.slice(di + 2));
    } else {
      s = stxNormalizeTruncatedPackedBracketTail(s);
    }
    const out = [];
    // Enhanced regex to handle {14:[1 1 1]} correctly even with internal spaces
    const rx = /\|\s*["']?c["']?\s*,\s*\d+\s*\||\{[^}]*(?:\[[^\]]*\])?[^}]*\}|"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|[^,\s]+/g;
    let m;
    while ((m = rx.exec(s))){
      const tok = String(m[0] || '').trim();
      if (!tok) continue;
      if (tok === '|' || tok === '||') continue;
      /* Keep Cosmetics_Weapon string tokens — Skin (optional) / phosphene TOK_STRING. */
      /* Header fragments that leaked into a bad paste (bare flags / seeds). */
      if (/^\d+\|$/.test(tok) || tok === '0') continue;
      out.push(tok);
    }
    return out;
  }
  try { window.parseImportTokenList = parseImportTokenList; } catch (_) {}

  function tokenIsElement(tok) {
    const s = String(tok || '').trim();
    if (/^\{\s*1\s*:\s*\d+\s*\}$/.test(s)) return true;
    const m = s.match(/^\{\s*246\s*:\s*(\d+)\s*\}$/);
    if (m){
      const id = Number(m[1]);
      return id === 22 || id === 23 || id === 24 || id === 25 || id === 26;
    }
    return false;
  }

  /** Header family already resolved to a concrete gear type — do not let stray `repair_kit.*` rows override it. */
  function stxImportHeaderTrustsItemType(itemTypeGuess) {
    const g = String(itemTypeGuess || '').trim();
    if (!g) return false;
    if (g === 'Weapon' || g === 'Heavy' || stxSimpleBuilderItemTypeIsHeavyUi(g)) return true;
    if (STX_RARITY_WEAPON_ITEM_TYPES.has(g)) return true;
    return g === 'Shield' || g === 'Grenade' || g === 'Class Mod' || g === 'Enhancement' || g === 'Repkit';
  }

  /** After import: map `{1:10}`… extras → primary/stack, detect pearl override tokens, sync Maliwan switch. */
  function stxHydrateImportExtrasMeta(cat){
    if (!state || !Array.isArray(state.extras)) return;
    const elemExtras = state.extras.filter(e => e && e.type === 'element');
    if ((cat === 'Weapon' || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType)) && elemExtras.length){
      const keys = [];
      for (const ex of elemExtras){
        const tok = String(ex.t || '').trim();
        const eo = ELEMENTS.find(x => x.code === tok);
        if (eo && eo.key && eo.key !== 'None') keys.push(eo.key);
      }
      if (keys.length){
        state.primaryElement = keys[0];
        state.elementStack = keys.slice(1);
        state.extras = state.extras.filter(e => !(e && e.type === 'element'));
        stxSyncDualElementMaliwanSwitch();
      }
    }
    const pearlTok = (tok)=>{
      const m = String(tok || '').trim().match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
      if (!m) return false;
      const id = Number(m[2]);
      return (id >= 51 && id <= 60) || id === 90;
    };
    const foundPearl = state.extras.some(e => e && pearlTok(e.tok || e.t));
    if (foundPearl){
      try{
        const a = document.getElementById('stxPearlOverride');
        const b = document.getElementById('ccGuidedPearlOverride');
        if (a) a.checked = true;
        if (b) b.checked = true;
      }catch(_e){}
    }
  }

  function stxSetImportBusy(on) {
    try {
      var fb = document.getElementById('importFeedback');
      if (fb) {
        fb.textContent = on ? 'Importing long serial…' : fb.textContent;
        fb.style.opacity = on ? '1' : fb.style.opacity;
        fb.style.transition = 'opacity 0.2s';
      }
      var mount = document.getElementById('ccAdvancedMount');
      var insp = document.getElementById('importedPartsInspector');
      var busyStyle = on ? '0.55' : '';
      if (mount) mount.style.opacity = busyStyle || '';
      if (insp) insp.style.opacity = busyStyle || '';
    } catch (_) {}
  }

  function stxApplyQuietHeaderFromSerial(raw, importTarget) {
    if (raw.indexOf('||') < 0) return;
    const dbl = raw.indexOf('||');
    const head = raw.slice(0, dbl).trim();
    const hm = head.match(/^\s*(\d+)/);
    if (!hm || !Number.isFinite(Number(hm[1]))) return;
    state.familyId = Number(hm[1]);
    const rRow = (window.STX_RARITIES || []).find(r => Number(r.familyId || r.family) === state.familyId);
    if (!rRow) return;
    let rawIt = rRow.itemType || rRow.category || '';
    if (STX_RARITY_WEAPON_ITEM_TYPES.has(rawIt)) {
      state.itemType = 'Weapon';
      if (rawIt === 'Sniper' || rawIt === 'Sniper Rifle') state.weaponType = 'Sniper Rifle';
      else if (rawIt === 'Submachine Gun') state.weaponType = 'SMG';
      else if (rawIt === 'Heavy' || rawIt === 'Heavy Weapon') state.weaponType = 'Heavy Weapon';
      else state.weaponType = rawIt;
    } else {
      state.itemType = rawIt;
    }
    state.manufacturer = rRow.manufacturer || state.manufacturer;
    state.itemType = stxNormalizeSimpleBuilderItemTypeUi(state.itemType);
    if (stxSimpleBuilderItemTypeIsHeavyUi(state.itemType) && !String(state.weaponType || '').trim()) state.weaponType = 'Heavy Weapon';

    const cgi = document.getElementById('ccGuidedItemType');
    if ((importTarget === 'guided' || importTarget === 'both') && cgi) {
      let wantCgi = state.itemType;
      if (wantCgi === 'Weapon' || STX_RARITY_WEAPON_ITEM_TYPES.has(wantCgi)) wantCgi = 'Weapon';
      if (wantCgi === 'Heavy' || wantCgi === 'Heavy Weapon' || wantCgi === 'Gadget') wantCgi = 'Heavy';
      cgi.value = wantCgi;
      if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgi);
    }
    const cgm = document.getElementById('ccGuidedManufacturer');
    if ((importTarget === 'guided' || importTarget === 'both') && cgm && state.manufacturer) {
      cgm.__ccPreferredManufacturer = String(state.manufacturer);
      cgm.value = state.manufacturer;
      if (cgm.value !== state.manufacturer) {
        cgm.appendChild(new Option(state.manufacturer, state.manufacturer));
        cgm.value = state.manufacturer;
      }
      if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgm);
    }
    const cgw = document.getElementById('ccGuidedWeaponType');
    if ((importTarget === 'guided' || importTarget === 'both') && cgw && (state.itemType === 'Weapon' || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType)) && state.weaponType) {
      cgw.value = state.weaponType;
      if (cgw.value !== state.weaponType) {
        cgw.appendChild(new Option(state.weaponType, state.weaponType));
        cgw.value = state.weaponType;
      }
      if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgw);
    }
    if (typeof window.syncGuidedVisibilityLayoutOnly === 'function') {
      window.syncGuidedVisibilityLayoutOnly();
    }
  }

  function stxSyncGuidedHeaderCustomSelects() {
    ['ccGuidedItemType', 'ccGuidedManufacturer', 'ccGuidedWeaponType', 'ccGuidedLevel'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el && typeof el.__customSelectSync === 'function') {
        try { el.__customSelectSync(); } catch (_) {}
      }
    });
  }

  function stxHydrateGuidedHeaderAfterImport() {
    try {
      const wantMan = String(state.manufacturer || '').trim();
      const wantWt = String(state.weaponType || '').trim();
      const cgi = document.getElementById('ccGuidedItemType');
      const cgm = document.getElementById('ccGuidedManufacturer');
      const cgw = document.getElementById('ccGuidedWeaponType');
      if (cgm && wantMan) cgm.__ccPreferredManufacturer = wantMan;

      if (typeof window.loadGuidedManufacturers === 'function') window.loadGuidedManufacturers();

      if (cgm && wantMan) {
        let hasMan = false;
        try {
          hasMan = Array.prototype.some.call(cgm.options || [], function (o) {
            return String(o && o.value || '').trim() === wantMan;
          });
        } catch (_) { hasMan = false; }
        if (!hasMan) cgm.appendChild(new Option(wantMan, wantMan));
        cgm.value = wantMan;
      }

      const itemType = (cgi && cgi.value) ? String(cgi.value).trim() : String(state.itemType || '').trim();
      if (itemType === 'Weapon' && typeof window.loadGuidedWeaponTypes === 'function') {
        window.loadGuidedWeaponTypes();
      }

      if (cgw && wantWt && (itemType === 'Weapon' || itemType === 'Heavy' || itemType === 'Heavy Weapon' || itemType === 'Gadget')) {
        let hasWt = false;
        try {
          hasWt = Array.prototype.some.call(cgw.options || [], function (o) {
            return String(o && o.value || '').trim() === wantWt;
          });
        } catch (_) { hasWt = false; }
        if (!hasWt) cgw.appendChild(new Option(wantWt, wantWt));
        cgw.value = wantWt;
      }

      stxSyncGuidedHeaderCustomSelects();
      try {
        if (typeof window.__ccForceCustomSelectSync === 'function') {
          ['ccGuidedItemType', 'ccGuidedManufacturer', 'ccGuidedWeaponType', 'ccGuidedLevel'].forEach(function (id) {
            const node = document.getElementById(id);
            if (node) window.__ccForceCustomSelectSync(node);
          });
        }
      } catch (_) {}
    } catch (_) {}
  }

  function stxCompleteGuidedLongImportUi(finishImportFn) {
    stxHydrateGuidedHeaderAfterImport();
    setTimeout(function () {
      try {
        var gDes = document.getElementById('guidedOutputDeserialized');
        var full = gDes ? String(gDes.value || '').trim() : '';
        if (full && typeof window.__ccHydrateGuidedSlotSelectsFromSerial === 'function') {
          window.__ccHydrateGuidedSlotSelectsFromSerial(full);
        }
        if (typeof window.syncGuidedFloatingOutputFromDeser === 'function') window.syncGuidedFloatingOutputFromDeser();
      } catch (_) {}
    }, 90);
    window.__CC_IMPORT_IN_PROGRESS = false;
    window.__ccDeferredGuidedVisibilityRefresh = false;
    window.__ccDeferredPartSectionsRefresh = false;
    try { if (window.__ccFlushDeferredGuidedVisibility) window.__ccFlushDeferredGuidedVisibility(); } catch (_) {}
    try { if (typeof window.syncGuidedVisibility === 'function') window.syncGuidedVisibility(); } catch (_) {}
    try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
    try { if (typeof window.refreshImportedInspector === 'function') window.refreshImportedInspector(); } catch (_) {}
    stxSetImportBusy(false);
    finishImportFn(true);
  }

  function stxAfterPaint(fn) {
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(function () { requestAnimationFrame(fn); });
    } else {
      setTimeout(fn, 16);
    }
  }

  function stxRunGuidedLongImportPipeline(ctx) {
    const rawIn = ctx.raw;
    const rawLooksPacked = ctx.rawLooksPacked;
    const importedB85Original = ctx.importedB85Original;
    const importTarget = ctx.importTarget;
    const ib = ctx.ib;
    const finishImportFn = ctx.finishImport;

    stxAfterPaint(function () {
      let full = rawIn;
      if (rawLooksPacked) {
        const applyDecoded = function (deser) {
          if (deser && typeof deser === 'string' && deser.trim().length) full = deser.trim();
          stxAfterPaint(function () {
            window.__CC_LAST_CODE_TARGET = 'guided';
            const guidedDeserEl = document.getElementById('guidedOutputDeserialized');
            const guidedSerialEl = document.getElementById('guidedOutputSerial');
            if (ib) ib.value = full;
            if (guidedDeserEl) {
              guidedDeserEl.value = full;
              guidedDeserEl.__ccImportedValue = full;
              guidedDeserEl.__ccUserTailEdit = false;
            }
            if (guidedSerialEl && importedB85Original) {
              guidedSerialEl.value = importedB85Original;
              guidedSerialEl.__ccImportedValue = importedB85Original;
            }
            applyImportedSerialHeaderToUi(full, importTarget);
            try { if (typeof window.__ccSyncCodeCharCounts === 'function') window.__ccSyncCodeCharCounts(); } catch (_) {}

            stxAfterPaint(function () {
              stxApplyQuietHeaderFromSerial(full, importTarget);

              setTimeout(function () {
                stxCompleteGuidedLongImportUi(finishImportFn);
              }, 50);
            });
          });
        };
        if (typeof window.ccDeserializeBase85Async === 'function') {
          window.ccDeserializeBase85Async(rawIn, applyDecoded);
          return;
        }
        if (typeof window.deserializeBase85 === 'function') {
          try {
            const deser = window.deserializeBase85(rawIn);
            applyDecoded(deser);
          } catch (_) {
            applyDecoded('');
          }
          return;
        }
      }

      stxAfterPaint(function () {
        window.__CC_LAST_CODE_TARGET = 'guided';
        const guidedDeserEl = document.getElementById('guidedOutputDeserialized');
        const guidedSerialEl = document.getElementById('guidedOutputSerial');
        if (ib) ib.value = full;
        if (guidedDeserEl) {
          guidedDeserEl.value = full;
          guidedDeserEl.__ccImportedValue = full;
          guidedDeserEl.__ccUserTailEdit = false;
        }
        if (guidedSerialEl && importedB85Original) {
          guidedSerialEl.value = importedB85Original;
          guidedSerialEl.__ccImportedValue = importedB85Original;
        }
        applyImportedSerialHeaderToUi(full, importTarget);
        try { if (typeof window.__ccSyncCodeCharCounts === 'function') window.__ccSyncCodeCharCounts(); } catch (_) {}

        stxAfterPaint(function () {
          stxApplyQuietHeaderFromSerial(full, importTarget);

          setTimeout(function () {
            stxCompleteGuidedLongImportUi(finishImportFn);
          }, 50);
        });
      });
    });
  }

  function stxFinishGuidedHeavyImport(full, b85Original, finishImportFn) {
    window.__CC_LAST_CODE_TARGET = 'guided';
    const ib = $('importBox');
    const guidedDeserEl = document.getElementById('guidedOutputDeserialized');
    const guidedSerialEl = document.getElementById('guidedOutputSerial');
    if (ib && full) ib.value = full;
    if (guidedDeserEl && full) {
      guidedDeserEl.value = full;
      guidedDeserEl.__ccImportedValue = full;
      guidedDeserEl.__ccUserTailEdit = false;
    }
    if (guidedSerialEl) {
      if (b85Original) {
        guidedSerialEl.value = b85Original;
        guidedSerialEl.__ccImportedValue = b85Original;
      } else {
        try { guidedSerialEl.setAttribute('aria-busy', 'true'); } catch (_) {}
        const fullCopy = full;
        const packHeavy = function () {
          try {
            if (typeof window.ccSerializeToBase85Async === 'function') {
              window.ccSerializeToBase85Async(fullCopy, function (b85) {
                try { guidedSerialEl.removeAttribute('aria-busy'); } catch (_) {}
                if (!guidedSerialEl || !b85) return;
                if (typeof window.ccIsValidStoredBase85 === 'function' && !window.ccIsValidStoredBase85(b85)) return;
                guidedSerialEl.value = String(b85).trim();
                guidedSerialEl.__ccImportedValue = String(b85).trim();
              });
            } else if (typeof window.serializeToBase85 === 'function') {
              const b85 = window.serializeToBase85(fullCopy, undefined, true);
              try { guidedSerialEl.removeAttribute('aria-busy'); } catch (_) {}
              if (b85) {
                if (typeof window.ccIsValidStoredBase85 === 'function' && !window.ccIsValidStoredBase85(b85)) return;
                guidedSerialEl.value = String(b85).trim();
                guidedSerialEl.__ccImportedValue = String(b85).trim();
              }
            }
          } catch (_) {
            try { guidedSerialEl.removeAttribute('aria-busy'); } catch (_e) {}
          }
        };
        setTimeout(packHeavy, 0);
      }
    }
    setTimeout(function () {
      stxHydrateGuidedHeaderAfterImport();
      try {
        var gDes = document.getElementById('guidedOutputDeserialized');
        var full = gDes ? String(gDes.value || '').trim() : '';
        if (full && typeof window.__ccHydrateGuidedSlotSelectsFromSerial === 'function') {
          window.__ccHydrateGuidedSlotSelectsFromSerial(full);
        }
        if (typeof window.syncGuidedFloatingOutputFromDeser === 'function') window.syncGuidedFloatingOutputFromDeser();
      } catch (_) {}
      window.__CC_IMPORT_IN_PROGRESS = false;
      window.__ccDeferredGuidedVisibilityRefresh = false;
      window.__ccDeferredPartSectionsRefresh = false;
      try { if (window.__ccFlushDeferredGuidedVisibility) window.__ccFlushDeferredGuidedVisibility(); } catch (_) {}
      try { if (typeof window.syncGuidedVisibility === 'function') window.syncGuidedVisibility(); } catch (_) {}
      try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
      try { if (typeof window.refreshImportedInspector === 'function') window.refreshImportedInspector(); } catch (_) {}
      stxSetImportBusy(false);
      finishImportFn(true);
    }, 40);
  }

  function importTokens(rawInput, targetBuilder){
    const modeArg = String(rawInput || '').trim().toLowerCase();
    if (!targetBuilder && (modeArg === 'guided' || modeArg === 'simple' || modeArg === 'both')){
      targetBuilder = modeArg;
      rawInput = '';
    }
    const importTarget = (targetBuilder === 'guided' || targetBuilder === 'simple' || targetBuilder === 'both')
      ? targetBuilder
      : 'both';
    const ib = $('importBox');
    if (!ib) return;
    let raw = String(rawInput || ib.value || '').trim();
    if (!raw) return;
    let importedFullOriginal = '';
    let baseFamilyFromHeader = null;
    let importHeavy = false;
    let importedB85Original = '';
    const rawLooksPacked = (raw.indexOf('@u') === 0 || raw.indexOf('@U') === 0 || (raw.indexOf('||') < 0 && raw.indexOf('{') < 0 && raw.length > 20));
    if (rawLooksPacked) importedB85Original = raw;
    window.__CC_IMPORT_IN_PROGRESS = true;
    try {
      if (typeof window.stxEnsureDeferredCore === 'function') window.stxEnsureDeferredCore();
    } catch (_) {}
    const finishImport = (heavy)=>{
      setTimeout(function () { window.__CC_IMPORT_IN_PROGRESS = false; }, heavy ? 650 : 220);
    };

    const isGuidedLongImport = importTarget === 'guided' && (raw.length > 2200 || rawLooksPacked);
    if (isGuidedLongImport) {
      window.__CC_IMPORT_HEAVY = true;
      stxSetImportBusy(true);
      stxRunGuidedLongImportPipeline({
        raw: raw,
        rawLooksPacked: rawLooksPacked,
        importedB85Original: importedB85Original,
        importTarget: importTarget,
        ib: ib,
        finishImport: finishImport
      });
      return;
    }

    const runProcessImport = function () {
    if (importHeavy && importTarget === 'guided') {
      stxApplyQuietHeaderFromSerial(raw, importTarget);
      stxFinishGuidedHeavyImport(importedFullOriginal, importedB85Original, finishImport);
      return;
    }
    // If no part tokens are found, try to detect item type/manufacturer from the header base family ID
    if (raw.indexOf('||') >= 0){
      const dbl = raw.indexOf('||');
      const head = raw.slice(0, dbl).trim();
      const hm = head.match(/^\s*(\d+)/);
      if (hm && Number.isFinite(Number(hm[1]))){
        baseFamilyFromHeader = Number(hm[1]);
        state.familyId = baseFamilyFromHeader;
        // Fallback: If no parts resolve, use header to set category
        const rarities = window.STX_RARITIES || [];
        const rRow = rarities.find(r => Number(r.familyId || r.family) === baseFamilyFromHeader);
        if (rRow) {
           let rawIt = rRow.itemType || rRow.category || '';
           if (STX_RARITY_WEAPON_ITEM_TYPES.has(rawIt)) {
             state.itemType = 'Weapon';
             if (rawIt === 'Sniper' || rawIt === 'Sniper Rifle') state.weaponType = 'Sniper Rifle';
             else if (rawIt === 'Submachine Gun') state.weaponType = 'SMG';
             else if (rawIt === 'Heavy' || rawIt === 'Heavy Weapon') state.weaponType = 'Heavy Weapon';
             else state.weaponType = rawIt;
           } else {
             state.itemType = rawIt;
           }
           state.manufacturer = rRow.manufacturer || state.manufacturer;
           state.itemType = stxNormalizeSimpleBuilderItemTypeUi(state.itemType);
           if (stxSimpleBuilderItemTypeIsHeavyUi(state.itemType) && !String(state.weaponType||'').trim()) state.weaponType = 'Heavy Weapon';

         if ((importTarget === 'simple' || importTarget === 'both') && $('itemType')) {
           $('itemType').value = state.itemType;
           stxSyncCustomSelectIfWrapped($('itemType'));
           if (!importHeavy) $('itemType').dispatchEvent(new Event('change', { bubbles: true }));
         }
        
         const cgi = document.getElementById('ccGuidedItemType');
         if ((importTarget === 'guided' || importTarget === 'both') && cgi) {
            let wantCgi = state.itemType;
            // Map canonical names to Guided dropdown values if they differ
            if (wantCgi === 'Weapon' || STX_RARITY_WEAPON_ITEM_TYPES.has(wantCgi)) wantCgi = 'Weapon';
            if (wantCgi === 'Heavy' || wantCgi === 'Heavy Weapon' || wantCgi === 'Gadget') wantCgi = 'Heavy';
            if (wantCgi === 'Sniper' || wantCgi === 'Sniper Rifle') wantCgi = 'Weapon';
          
            cgi.value = wantCgi;
            if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgi);
           
            // Check if it actually stuck
            if (cgi.value !== wantCgi && wantCgi) {
               var opt3 = new Option(wantCgi, wantCgi);
               cgi.appendChild(opt3);
               cgi.value = wantCgi;
               if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgi);
            }

            // Force visibility sync; defer noisy change handlers on long imports
            if (!importHeavy) cgi.dispatchEvent(new Event('change', { bubbles: true }));
            if (typeof window.syncGuidedVisibility === 'function') window.syncGuidedVisibility();
         }

         if (importTarget === 'simple' || importTarget === 'both') {
           refreshTopSelectors();
           if ($('manufacturer')) {
             $('manufacturer').value = state.manufacturer;
             stxSyncCustomSelectIfWrapped($('manufacturer'));
           }
         }
        
         if (importTarget === 'guided' || importTarget === 'both') {
           // Ensure Guided manufacturers are loaded for the selected item type
           if (typeof window.loadGuidedManufacturers === 'function') window.loadGuidedManufacturers();

           const cgm = document.getElementById('ccGuidedManufacturer');
           if (cgm) {
             cgm.value = state.manufacturer;
             // If not in list, add it
             if (cgm.value !== state.manufacturer && state.manufacturer) {
                var opt = new Option(state.manufacturer, state.manufacturer);
                cgm.appendChild(opt);
                cgm.value = state.manufacturer;
             }
             if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgm);
             if (!importHeavy) cgm.dispatchEvent(new Event('change', { bubbles: true }));
            
             // SECOND PASS RE-CHECK: Sometimes events clear it
             if (!importHeavy) setTimeout(function() {
                if (cgm.value !== state.manufacturer && state.manufacturer) {
                   cgm.value = state.manufacturer;
                   if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgm);
                   cgm.dispatchEvent(new Event('change', { bubbles: true }));
                }
             }, 100);
           }
         }

         if ((importTarget === 'simple' || importTarget === 'both') && (state.itemType === 'Weapon' || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType)) && $('weaponType')) {
           $('weaponType').value = state.weaponType;
           stxSyncCustomSelectIfWrapped($('weaponType'));
         }
        
         // Ensure Guided weapon types are loaded
         if ((importTarget === 'guided' || importTarget === 'both')) {
           if (typeof window.loadGuidedWeaponTypes === 'function') window.loadGuidedWeaponTypes();

           const cgw = document.getElementById('ccGuidedWeaponType');
           if (cgw && (state.itemType === 'Weapon' || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType))) {
             cgw.value = state.weaponType;
             if (cgw.value !== state.weaponType && state.weaponType) {
                var opt2 = new Option(state.weaponType, state.weaponType);
                cgw.appendChild(opt2);
                cgw.value = state.weaponType;
             }
             if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgw);
             if (!importHeavy) cgw.dispatchEvent(new Event('change', { bubbles: true }));
           }
         }
         // Final pass to ensure all dependent pools are correctly filtered
         if ((importTarget === 'simple' || importTarget === 'both') && !importHeavy) {
            invokeRefreshMainPart(true);
         }
        }
      }
      raw = raw.slice(dbl + 2).trim();
    }

    const tokensRaw = parseImportTokenList(raw);
    const tokens = [];
    const bracketedMap = new Map(); // Map original bracketed string to its expanded individual tokens
    const tokenToBracket = new Map(); // Map expanded individual token to its original bracketed string

    for (const t0 of tokensRaw){
      const t = String(t0 || '').trim();
      if (!t) continue;
      
      let m = t.match(/^\{\s*(\d+)\s*\}$/);
      if (m && Number.isFinite(baseFamilyFromHeader)){
        const exp = `{${baseFamilyFromHeader}:${Number(m[1])}}`;
        tokens.push(exp);
        continue;
      }
      m = t.match(/^\{\s*(\d+)\s*:\s*\[([^\]]+)\]\s*\}$/);
      if (m){
        const fam = m[1];
        const ids = String(m[2] || '').match(/\d+/g);
        if (ids && ids.length) {
          const expandCap = importHeavy ? 48 : 512;
          if (ids.length > expandCap) {
            tokens.push(t);
            continue;
          }
          const expandedForThisBracket = [];
          for (const id of ids) {
            const exp = `{${fam}:${id}}`;
            expandedForThisBracket.push(exp);
            tokens.push(exp);
            tokenToBracket.set(exp, t);
          }
          bracketedMap.set(t, expandedForThisBracket);
          continue;
        }
      }
      tokens.push(t);
    }
    
    // reset selections but keep top dropdowns
    state.slots = {};
    state.elementStack = [];
    state.dualElementUseMaliwanSwitch = false;
    state.extras = [];
    state.primaryElement = 'None';
    
    if (!tokens.length) {
      refreshOutputs(true);
      finishImport(false);
      return;
    }

    // Resolve parts
    const bracketUsed = new Set();
    let globalImportCounter = 0;
    const resolved = tokens.map(t => {
       const rawPart = tryResolveToken(t);
       let p = null;
       const originalIdx = globalImportCounter++;

       if (rawPart) {
         // Clone the part object to avoid polluting the shared dataset with __importedToken
         p = {...rawPart};
         p.__importOrder = originalIdx;
         
         const originalBracket = tokenToBracket.get(t);
         if (originalBracket) {
           if (!bracketUsed.has(originalBracket)) {
             // First part resolved from this bracket gets the bracketed token
             p.__importedToken = String(originalBracket);
             bracketUsed.add(originalBracket);
           } else {
             // Subsequent parts from the same bracket get NO token to avoid duplication
             p.__importedToken = '';
           }
         } else {
           p.__importedToken = String(t); 
         }
       }
       return {t, p, originalIdx};
    });

    state.extras = [];
    const actualPartTokens = [];
    const resolvedTokensSet = new Set();
    const partCounts = new Map();

      for (const res of resolved) {
        if (res.p) {
          const pt = tokenForPart(res.p);
          if (pt) {
            actualPartTokens.push(res);
            resolvedTokensSet.add(res.t);
            const pKey = res.p.__idx != null ? `idx:${res.p.__idx}` : (pt || normCode(res.p.code));
            partCounts.set(pKey, (partCounts.get(pKey) || 0) + 1);
          }
        } else {
          if (tokenIsElement(res.t)) {
            // Store elements as objects with order
            state.extras.push({ tok: String(res.t), order: res.originalIdx, type: 'element' });
          } else {
            if (!tokenToBracket.has(res.t)) {
              state.extras.push({ tok: String(res.t), order: res.originalIdx, type: 'extra' });
            }
          }
        }
      }

    // Handle bracketed groups: if NONE of the parts in a bracket resolved, add original bracket to extras
    for (const [bracket, expandedList] of bracketedMap.entries()) {
      const anyResolved = expandedList.some(et => resolvedTokensSet.has(et));
      if (!anyResolved) {
        // Find the index of the first token in the expanded list to approximate the bracket's position
        const firstTok = expandedList[0];
        const resObj = resolved.find(r => r.t === firstTok);
        state.extras.push({ tok: String(bracket), order: resObj ? resObj.order : (resObj ? resObj.originalIdx : 0), type: 'extra' });
      }
    }

    const partTokens = actualPartTokens;

    // Set main part: prefer the category's core part type (e.g. Barrel for weapons)
    if (partTokens.length){
      // Repkits can have the first resolved token be a non-repkit row,
      // which breaks category selection. Prioritize Repkit when repair_kit.* is present.
      const hasRepkit = partTokens.some(res => {
        const p = res && res.p;
        const cat = String(p && p.category || '').trim().toLowerCase();
        const c = String(normCode(p && p.code || '')).toLowerCase();
        return cat === 'repkit' || c.includes('repair_kit.part_');
      });

      let enhancementFromHeaderFamily = false;
      try {
        const fid = Number(baseFamilyFromHeader);
        if (Number.isFinite(fid)){
          const rr = (window.STX_RARITIES || []).find(r => Number(r.familyId || r.family) === fid);
          enhancementFromHeaderFamily = String(rr && rr.itemType || '').trim() === 'Enhancement';
        }
      } catch (_){ enhancementFromHeaderFamily = false; }

      // Use existing `state.itemType` (from header / prior dropdown) as the primary signal.
      // Dataset internal categories for weapons can be `Prefix`/`Rarity`/`Gadget`, which
      // would break CORE_PARTTYPE_BY_CATEGORY if we blindly used `partTokens[0].p.category`.
      const itemTypeRaw = state.itemType || (partTokens[0] && partTokens[0].p && partTokens[0].p.category) || '';
      const itemTypeKey = STX_RARITY_WEAPON_ITEM_TYPES.has(itemTypeRaw) ? 'Weapon' : itemTypeRaw;

      const itemTypeGuess = String(state.itemType || '').trim();
      const headerTrustsType = stxImportHeaderTrustsItemType(itemTypeGuess);
      const detectedCat0 = (hasRepkit && !headerTrustsType && !enhancementFromHeaderFamily)
        ? 'Repkit'
        : (itemTypeKey || state.itemType || partTokens[0].p.category);
      const corePt0 = CORE_PARTTYPE_BY_CATEGORY[detectedCat0] || 'Base';
      const main = partTokens.map(x=>x.p).find(p => (p.partType||'') === corePt0) || partTokens[0].p;
      
      // Update counts because main is handled separately
      const mKey = main.__idx != null ? `idx:${main.__idx}` : (tokenForPart(main) || normCode(main.code));
      if (partCounts.get(mKey) > 0) partCounts.set(mKey, partCounts.get(mKey) - 1);
      // set top dropdowns to match detected
      let rawDetectedCat = detectedCat0 || main.category || state.itemType;
      if (STX_RARITY_WEAPON_ITEM_TYPES.has(rawDetectedCat)) {
        state.itemType = 'Weapon';
        if (rawDetectedCat === 'Sniper' || rawDetectedCat === 'Sniper Rifle') state.weaponType = 'Sniper Rifle';
        else if (rawDetectedCat === 'Submachine Gun') state.weaponType = 'SMG';
        else if (rawDetectedCat === 'Heavy' || rawDetectedCat === 'Heavy Weapon') state.weaponType = 'Heavy Weapon';
        else state.weaponType = rawDetectedCat;
      } else {
        state.itemType = rawDetectedCat;
      }

      state.itemType = stxNormalizeSimpleBuilderItemTypeUi(state.itemType);
      if (stxSimpleBuilderItemTypeIsHeavyUi(state.itemType) && !String(state.weaponType||'').trim()) state.weaponType = 'Heavy Weapon';

      // Resolve Simple **Heavy** vs **Weapon** before populating dropdowns (normalize + heavy weapon type).
      if (state.itemType === 'Weapon' || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType)){
        if (stxSimpleBuilderItemTypeIsHeavyUi(state.itemType)){
          state.itemType = 'Heavy';
          state.weaponType = 'Heavy Weapon';
        } else {
          state.weaponType = main.weaponType || main.itemType || state.weaponType;
        }
      }

      // Ensure dropdowns are populated for the new category
      const doSimpleUI = (importTarget === 'simple' || importTarget === 'both');
      if (doSimpleUI && $('itemType')) {
        $('itemType').value = state.itemType;
        stxSyncCustomSelectIfWrapped($('itemType'));
      }
      const cgi_main = document.getElementById('ccGuidedItemType');
      if ((importTarget === 'guided' || importTarget === 'both') && cgi_main) {
        cgi_main.value = (state.itemType === 'Heavy' || state.itemType === 'Heavy Weapon' || state.itemType === 'Gadget') ? 'Heavy' : state.itemType;
        if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgi_main);
        if (typeof syncGuidedVisibility === 'function') syncGuidedVisibility();
      }

      if (doSimpleUI) refreshTopSelectors(stxPerfLiteUi() ? { deferHeavy: true } : undefined);
      
      state.manufacturer = main.manufacturer || '';
      if (doSimpleUI && $('manufacturer')) {
        $('manufacturer').value = state.manufacturer;
        stxSyncCustomSelectIfWrapped($('manufacturer'));
      }
      const cgm_main = document.getElementById('ccGuidedManufacturer');
      if ((importTarget === 'guided' || importTarget === 'both') && cgm_main) {
        cgm_main.value = state.manufacturer;
        if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgm_main);
      }

      if (state.itemType === 'Weapon' || state.itemType === 'Heavy'){
        if (doSimpleUI && $('weaponType')) {
          $('weaponType').value = state.weaponType;
          stxSyncCustomSelectIfWrapped($('weaponType'));
        }
        const cgw_main = document.getElementById('ccGuidedWeaponType');
        if ((importTarget === 'guided' || importTarget === 'both') && cgw_main) {
           cgw_main.value = state.weaponType;
           if (typeof syncGuidedCustomSelectIfWrapped === 'function') syncGuidedCustomSelectIfWrapped(cgw_main);
        }
      }
      if (doSimpleUI) invokeRefreshMainPart(true);

      // If category uses rarity filter, we MUST set the rarity tier dropdown first
      // so refreshMainPart can find the part in the resulting pool.
      if (categoryUsesRarityTierFilter(state.itemType)){
        const detectedTier = rarityTierFromItemTypeString(main.itemTypeString || main.code || main.itemType || '', main);
        if (Number.isFinite(detectedTier)){
          state.rarity = String(detectedTier);
          if (doSimpleUI && $('rarity')) {
            $('rarity').value = state.rarity;
            stxSyncCustomSelectIfWrapped($('rarity'));
          }
          // Re-refresh main part pool with the new tier
          if (doSimpleUI) invokeRefreshMainPart(true);
        }
      }

      let mainOptKey = '';
      try{
        const map = state && state.__mainPartByOptionKey;
        if (map && typeof map.entries === 'function'){
          const mainTok = tokenForPart(main);
          for (const [k,p] of map.entries()){
            if (p === main){ mainOptKey = k; break; }
            if (p && main && p.__idx != null && main.__idx != null && p.__idx === main.__idx){ mainOptKey = k; break; }
            if (tokenForPart(p) === mainTok){ mainOptKey = k; break; }
          }
        }
      }catch(_e){}
      if (doSimpleUI) {
        if (mainOptKey) $('mainPart').value = String(mainOptKey);
        else if (main && main.__idx != null && Number.isFinite(Number(main.__idx))) $('mainPart').value = `idx:${Number(main.__idx)}`;
        try { stxEnsureMainPartSelectOption(main); } catch (_) {}
      }
      state.mainPart = main;
      state.detectedCategory = detectedCat0 || main.category || state.itemType;
    
      // Explicitly set the rarity slot if we detected it
      const ptL = String(main.partType || '').toLowerCase();
      if (ptL === 'rarity') {
        state.slots.rarity = main;
        // Also update counts
        const rKey = main.__idx != null ? `idx:${main.__idx}` : (tokenForPart(main) || normCode(main.code));
        if (partCounts.get(rKey) > 0) partCounts.set(rKey, partCounts.get(rKey) - 1);
      }
    }

    // Fill slots best-effort by matching partType to first empty slot schema
    const cat = state.detectedCategory;
    const partsLeft = partTokens.slice().map(x=>x.p);
    // Remove mainPart from pool once (it was already accounted for in partCounts)
    if (state.mainPart) {
      const mainIdx = partsLeft.findIndex(p => p === state.mainPart);
      if (mainIdx >= 0) partsLeft.splice(mainIdx, 1);
    }

    if (cat === 'Weapon'){
      const schema = getActiveWeaponSlotSchema();
      let pool = partsLeft.slice();
      const takeIndex = (pred)=>{
        const idx = pool.findIndex(pred);
        if (idx < 0) return null;
        const p = pool[idx];
        pool.splice(idx, 1);
        return p;
      };
      for (const s of schema){
        if (s.multi && s.key === 'legendary'){
          for (let i = pool.length - 1; i >= 0; i--){
            const p = pool[i];
            if (String(p.partType||'').trim() !== 'Legendary Perks') continue;
            const statsBlob = (String(p.stats||'') + ' ' + String(p.effects||'') + ' ' + String(p.name||'')).toLowerCase();
            if (/stat\s*modifier/.test(statsBlob)) continue;
            const pKey = p.__idx != null ? `idx:${p.__idx}` : (tokenForPart(p) || normCode(p.code));
            if ((partCounts.get(pKey) || 0) <= 0) continue;
            const arr = Array.isArray(state.slots.legendary) ? state.slots.legendary.slice() : [];
            arr.push(p);
            state.slots.legendary = arr;
            partCounts.set(pKey, (partCounts.get(pKey) || 0) - 1);
            pool.splice(i, 1);
          }
          continue;
        }
        if (s.multi) continue;
        if (state.slots[s.key]) continue;
        const p = takeIndex(part => {
          const pt = String(part.partType||'').trim();
          const wantPt = String(s.partType||'').trim();
          if (wantPt !== pt){
            if (s.key === 'pearlElem' && weaponPearlElemPartMatch(part)) { /* ok */ }
            else if (s.key === 'pearlStat' && weaponPearlStatPartMatch(part)) { /* ok */ }
            else if (s.key === 'statMod' && wantPt === 'Stat Modifier') {
              const c = String(normCode(part.code || '') || '').toLowerCase();
              if (!(/part_stat|\.endgame\b|part_endgame|stat_augment/.test(c) || pt === 'Stat Modifier')) return false;
            } else if (wantPt === 'Body Accessory' && pt === 'Body') {
              const c = normCode(part.code).toLowerCase();
              if (!(c.includes('part_body_bolt') || c.includes('part_body_flap'))) return false;
            } else return false;
          }
          if (s.key === 'pearlElem' && !weaponPearlElemPartMatch(part)) return false;
          if (s.key === 'pearlStat' && !weaponPearlStatPartMatch(part)) return false;
          if (s.ncsSlot && !weaponPartMatchesNcsSlot(part, s.ncsSlot)) return false;
          return true;
        });
        if (p) {
          state.slots[s.key] = p;
          const pKey = p.__idx != null ? `idx:${p.__idx}` : (tokenForPart(p) || normCode(p.code));
          if (partCounts.get(pKey) > 0) partCounts.set(pKey, partCounts.get(pKey) - 1);
        }
      }
      const schemaHasAdditional = schema.some(s => s.key === 'additionalParts' && s.multi);
      if (schemaHasAdditional){
        const arr = Array.isArray(state.slots.additionalParts) ? state.slots.additionalParts.slice() : [];
        for (const p of pool){
          const pKey = p.__idx != null ? `idx:${p.__idx}` : (tokenForPart(p) || normCode(p.code));
          let left = partCounts.get(pKey) || 0;
          while (left > 0){
            arr.push(p);
            left--;
            partCounts.set(pKey, left);
          }
        }
        if (arr.length) state.slots.additionalParts = arr;
      } else {
      // Surplus parts go to extras to ensure they are NOT REMOVED
      for (const p of pool){
        const pKey = p.__idx != null ? `idx:${p.__idx}` : (tokenForPart(p) || normCode(p.code));
        if (partCounts.get(pKey) > 0) {
          state.extras.push({ tok: tokenForPart(p) || normCode(p.code), order: p.__importOrder ?? 0, type: 'extra' });
          partCounts.set(pKey, (partCounts.get(pKey) || 0) - 1);
        }
      }
      }
      // parse elements ({1:10}-{1:14}) into primary + stack
      stxHydrateImportExtrasMeta('Weapon');
    } else {
      const schema = SIMPLE_SCHEMA_BY_CATEGORY[cat] || [];
      const slotByKey = new Map(schema.map(s => [s.key, s]));
      const assignSlot = (s, p) => {
        if (!s || !p) return false;
        if (s.multi){
          const arr = Array.isArray(state.slots[s.key]) ? state.slots[s.key].slice() : (state.slots[s.key] ? [state.slots[s.key]] : []);
          arr.push(p);
          state.slots[s.key] = arr;
          return true;
        }
        if (!state.slots[s.key]){
          state.slots[s.key] = p;
          return true;
        }
        return false;
      };

      if (cat === 'Shield'){
        const elementTokens = state.extras.filter(e => e && e.type === 'element');
        const pickShieldSlot = (p) => {
          const pf = partFamilyIdOf(p);
          const pt = String((p && p.partType) || '').trim().toLowerCase();
          const code = String((p && p.code) || '').trim().toLowerCase();
          const codeNorm = String(normCode(p && p.code || '') || '').toLowerCase();
          const isRarityPart = (pt === 'rarity') || /(^|[._])(comp_0[1-5]_|pearl_)/.test(code) || code.includes('.comp_');

          if (isRarityPart) return null;
          if (pf === 237) return slotByKey.get('armor237') || null;
          if (pf === 248) return slotByKey.get('energy248') || null;

          // Weapon TypeID-1 element rows must land in the shield element slot (spawn expects `Shield.part_*` / 246).
          if (pf === 1 && /^weapon\.part_(corrosive|cryo|fire|radiation|shock)$/.test(codeNorm)){
            return slotByKey.get('elementType1') || null;
          }

          if (pf === 246){
            if (pt === 'firmware') return slotByKey.get('firmware246') || null;
            if (pt === 'perk'){
              const nmLo = String((p && p.name) || '').toLowerCase();
              const isPearlElem = /part_pearl_elem|pearl_elem/i.test(codeNorm);
              const isPearlStatish = !isPearlElem && (/part_pearl/i.test(codeNorm) || /\bpearlescent\b/i.test(codeNorm) || /\bpearl\b/.test(nmLo));
              if (isPearlElem) return slotByKey.get('pearlElem246') || null;
              if (isPearlStatish) return slotByKey.get('pearlStat246') || null;
              if (codeNorm.includes('_primary')){
                return !state.slots.primary246
                  ? (slotByKey.get('primary246') || null)
                  : (slotByKey.get('secondary246') || null);
              }
              return !state.slots.secondary246
                ? (slotByKey.get('secondary246') || null)
                : (slotByKey.get('primary246') || null);
            }
            const isShieldFiveElem = /^shield\.part_(corrosive|cryo|fire|radiation|shock)$/.test(codeNorm);
            if (isShieldFiveElem && !state.slots.elementType1) return slotByKey.get('elementType1') || null;
            return slotByKey.get('resistance') || null;
          }

          if (stxIsShieldUniquePoolRowCode(codeNorm)) return slotByKey.get('bodyLegendary') || null;
          if (stxIsShieldBodyPoolRowCode(codeNorm)) {
            if (!state.slots.body && !state.slots.mainBody) return slotByKey.get('body') || slotByKey.get('mainBody') || null;
            return null;
          }
          return null;
        };

        for (const p of partsLeft){
          const s = pickShieldSlot(p);
          if (!assignSlot(s, p)){
            state.extras.push({ tok: tokenForPart(p) || normCode(p.code), order: p.__importOrder ?? 0, type: 'extra' });
          }
        }

        if (elementTokens.length && slotByKey.has('elementType1') && !state.slots.elementType1){
          const tok = String(elementTokens[0].t || '').trim();
          const type1To246 = { 10: 22, 11: 23, 12: 24, 13: 25, 14: 26 };
          let picked = null;
          let m246 = tok.match(/^\{\s*246\s*:\s*(\d+)\s*\}$/);
          if (m246){
            const wantId = Number(m246[1]);
            picked = getAllParts().find(row => {
              if (!row || String(row.category || '').trim() !== 'Shield') return false;
              const cLo = String(normCode(row.code || '') || '').toLowerCase();
              if (!/^shield\.part_(corrosive|cryo|fire|radiation|shock)$/.test(cLo)) return false;
              return Number(row.id) === wantId && Number(row.family || row.familyId) === 246;
            }) || null;
          }
          if (!picked){
            const m1 = tok.match(/^\{\s*1\s*:\s*(\d+)\s*\}$/);
            if (m1){
              const id1 = Number(m1[1]);
              const id246 = type1To246[id1];
              if (Number.isFinite(id246)){
                picked = getAllParts().find(row => {
                  if (!row || String(row.category || '').trim() !== 'Shield') return false;
                  const cLo = String(normCode(row.code || '') || '').toLowerCase();
                  if (!/^shield\.part_(corrosive|cryo|fire|radiation|shock)$/.test(cLo)) return false;
                  return Number(row.id) === id246 && Number(row.family || row.familyId) === 246;
                }) || null;
              }
            }
          }
          if (picked){
            state.slots.elementType1 = Object.assign({}, picked);
            const dropTok = String(elementTokens[0].t || '').trim();
            state.extras = state.extras.filter(e => !(e && e.type === 'element' && String(e.t || '').trim() === dropTok));
          }
        }
      } else if (cat === 'Repkit'){
        const repkitIdBodyRe = /(^|[^a-z0-9])(?:bor|dad|jak|mal|ord|ted|tor|vla)_repair_kit\.part_(?:borg|dad|jak|mal|ord|ted|tor|vla)($|[^a-z0-9])/i;
        const isRepkitImportedBaseVariant = (p)=>{
          const man = String(state.manufacturer || '').trim().toLowerCase();
          const spawn = stxRepkitSpawnPrefixForUiManufacturer(man);
          if (!spawn || !p) return false;
          const c = String(normCode(p.code || p.spawnCode || p.importCode || '') || '').toLowerCase();
          if (c.indexOf(spawn + '.part_') !== 0) return false;
          if (repkitIdBodyRe.test(c)) return false;
          if (c.indexOf(spawn + '.part_payload_') === 0) return false;
          if (c.indexOf(spawn + '.part_element_') === 0) return false;
          if (c.indexOf(spawn + '.part_firmware') === 0) return false;
          if (c.indexOf(spawn + '.part_aug_') === 0) return false;
          if (c.indexOf(spawn + '.comp_') === 0) return false;
          return true;
        };
        const pickRepkitEmptyPartTypeSlot = (p) => {
          const c = String(normCode(p && p.code) || '').toLowerCase();
          const n = String((p && p.name) || '').trim().toUpperCase();
          const isPh = !c || n === 'PLACEHOLDER';
          const isPayload = /repair_kit\.part_payload_/.test(c);
          const isElem = stxIsDatasetRepkitElementCode(c);
          const isAug = /repair_kit\.part_aug_/.test(c);
          if (isPh) return slotByKey.get('otherParts') || null;
          if (isPayload) return slotByKey.get('payload') || null;
          if (isElem) return slotByKey.get('element') || null;
          if (isAug) {
            if (/resist/.test(c)) return slotByKey.get('perkResist') || null;
            if (/immunity/.test(c)) return slotByKey.get('perkImmunity') || null;
            if (/nova/.test(c)) return slotByKey.get('perkNova') || null;
            if (/splat/.test(c)) return slotByKey.get('perkSplat') || null;
          }
          return null;
        };
        for (const p of partsLeft){
          const pt = String((p && p.partType) || '').trim();
          let s = null;
          if (slotByKey.get('base') && isRepkitImportedBaseVariant(p) && !state.slots.base){
            s = slotByKey.get('base');
          }
          // Repkit elements are inconsistently tagged in the dataset (sometimes partType is "", sometimes
          // it's "Cryo"/"Fire"/etc). Route by code patterns first.
          if (!s) s = pickRepkitEmptyPartTypeSlot(p);

          if (!s && pt !== ''){
            const matches = schema.filter(sx => String(sx.partType || '') === pt);
            if (matches.length){
              s = matches.find(x => x.multi) || matches.find(x => !state.slots[x.key]) || matches[0];
            }
          }
          if (!assignSlot(s, p)){
            state.extras.push({ tok: tokenForPart(p) || normCode(p.code), order: p.__importOrder ?? Infinity, type: 'extra' });
          }
        }
        if (typeof bracketedExtras !== 'undefined' && bracketedExtras && bracketedExtras.length) {
          state.extras.push(...bracketedExtras);
        }
      } else if (cat === 'Grenade'){
        const pickGrenadeByCode = (p)=>{
          const c = String(normCode(p && p.code) || '').toLowerCase();
          if (/grenade_gadget\.part_stat_/.test(c)) return slotByKey.get('grenadeKitStats') || null;
          if (stxIsGrenadePayloadAugmentPoolRowCode(c)) return slotByKey.get('augment') || null;
          if (stxIsGrenadePayloadPoolRowCode(c)) return slotByKey.get('payload') || null;
          if (stxIsGrenadeBodyPoolRowCode(c)) return slotByKey.get('body') || null;
          if (weaponPearlElemPartMatch(p)) return slotByKey.get('pearlElem') || null;
          if (weaponPearlStatPartMatch(p)) return slotByKey.get('pearlStat') || null;
          return null;
        };
        for (const p of partsLeft){
          const pt = String((p && p.partType) || '').trim();
          let s = pickGrenadeByCode(p);
          if (!s && pt !== ''){
            const matches = schema.filter(sx => String(sx.partType || '') === pt);
            if (matches.length){
              s = matches.find(x => x.multi) || matches.find(x => !state.slots[x.key]) || matches[0];
            }
          }
          if (!assignSlot(s, p)){
            state.extras.push({ tok: tokenForPart(p) || normCode(p.code), order: p.__importOrder ?? Infinity, type: 'extra' });
          }
        }
        if (typeof bracketedExtras !== 'undefined' && bracketedExtras && bracketedExtras.length) {
          state.extras.push(...bracketedExtras);
        }
      } else {
        for (const p of partsLeft){
          if (cat === 'Enhancement'){
            const c = String(normCode(p && p.code) || '').toLowerCase();
            const pt = String((p && p.partType) || '').trim().toLowerCase();
            let sEnh = null;
            if (/part_core_|core_augment/.test(c) || pt === 'core' || /part_body_/.test(c) || pt === 'body') sEnh = slotByKey.get('core') || null;
            else if (/part_stat/.test(c) || pt === 'stats' || pt === 'stat') sEnh = slotByKey.get('stats') || null;
            else if (/part_firmware/.test(c) || pt === 'firmware') sEnh = slotByKey.get('firmware') || null;
            if (assignSlot(sEnh, p)) continue;
          }
          const matches = schema.filter(s => String(s.partType || '') === String((p && p.partType) || ''));
          let s = null;
          if (matches.length){
            s = matches.find(x => x.multi) || matches.find(x => !state.slots[x.key]) || matches[0];
          }
          if (!assignSlot(s, p)){
            state.extras.push({ tok: tokenForPart(p) || normCode(p.code), order: p.__importOrder ?? Infinity, type: 'extra' });
          }
        }
        if (typeof bracketedExtras !== 'undefined' && bracketedExtras && bracketedExtras.length) {
          state.extras.push(...bracketedExtras);
        }
      }
    }
    
    stxHydrateImportExtrasMeta(cat);

    function completeImportUi(){
      const skipSimpleBuilder = importHeavy && importTarget === 'guided';
      if (!skipSimpleBuilder) refreshBuilder();
      try{ finalizeCcImportToBuilders(importTarget); }catch(_){}
      const stagger = importHeavy ? 35 : 0;
      setTimeout(function () {
        if (skipSimpleBuilder) {
          stxHydrateGuidedHeaderAfterImport();
          window.__CC_IMPORT_IN_PROGRESS = false;
          window.__ccDeferredGuidedVisibilityRefresh = false;
          window.__ccDeferredPartSectionsRefresh = false;
        }
        try { if (window.__ccFlushDeferredGuidedVisibility) window.__ccFlushDeferredGuidedVisibility(); } catch (_) {}
        try { if (typeof window.syncGuidedVisibility === 'function') window.syncGuidedVisibility(); } catch (_) {}
        try { if (typeof window.refreshPartSections === 'function') window.refreshPartSections(true); } catch (_) {}
        setTimeout(function () {
          if (!skipSimpleBuilder) {
            window.__CC_IMPORT_IN_PROGRESS = false;
            try { clearImportedOutputLock(); } catch (_) {}
            if (importTarget === 'guided') {
              try { if (typeof window.syncGuidedFloatingOutputFromDeser === 'function') window.syncGuidedFloatingOutputFromDeser(); } catch (_) {}
            } else {
              try { refreshOutputs(true); } catch (_) {}
            }
          }
          try { if (typeof window.refreshImportedInspector === 'function') window.refreshImportedInspector(); } catch (_) {}
          stxSetImportBusy(false);
          finishImport(importHeavy);
        }, stagger);
      }, stagger);
    }
    if (importHeavy) {
      setTimeout(completeImportUi, 0);
    } else {
      completeImportUi();
    }
    };

    const continueImportAfterDecode = function () {
      try {
        importedFullOriginal = String(raw || '').trim();
        const importTail = raw.indexOf('||') >= 0 ? raw.slice(raw.indexOf('||') + 2) : raw;
        importHeavy = importedFullOriginal.length > 4000 || importTail.length > 1500 || rawLooksPacked;
        if (!importHeavy && importTail.length > 800) {
          try {
            const braceCount = (importTail.match(/\{/g) || []).length;
            if (braceCount > 40) importHeavy = true;
          } catch (_) {}
        }
        window.__CC_IMPORT_HEAVY = importHeavy;
        applyImportedSerialHeaderToUi(raw, importTarget);
        runProcessImport();
      } catch (_) {
        stxSetImportBusy(false);
        window.__CC_IMPORT_IN_PROGRESS = false;
      }
    };

    const runImportPipeline = function () {
      try {
        if (rawLooksPacked) {
          const applyPacked = function (deser) {
            try {
              if (deser && typeof deser === 'string' && deser.trim().length) {
                raw = deser.trim();
                ib.value = raw;
              }
            } catch (_) {}
            continueImportAfterDecode();
          };
          if (typeof window.ccDeserializeBase85Async === 'function') {
            window.ccDeserializeBase85Async(raw, applyPacked);
            return;
          }
          if (typeof window.deserializeBase85 === 'function') {
            try {
              applyPacked(window.deserializeBase85(raw));
            } catch (_) {
              applyPacked('');
            }
            return;
          }
        }
      } catch (_) {}
      continueImportAfterDecode();
    };

    if (raw.length > 2200 || rawLooksPacked) {
      stxSetImportBusy(true);
      setTimeout(runImportPipeline, 0);
    } else {
      runImportPipeline();
    }
  }

  async function copyToClipboard(text){
    try{
      await navigator.clipboard.writeText(text);
      return true;
    }catch(e){
      // fallback
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try{ document.execCommand('copy'); }catch(_){}
      document.body.removeChild(ta);
      return false;
    }
  }

  /** Legit-style item slug — logic in assets/js/cc-item-slug.js (computeSimpleBuilderItemSlug). */
  function computeEditorItemSlug() {
    try {
      if (typeof window.computeSimpleBuilderItemSlug === 'function') {
        return window.computeSimpleBuilderItemSlug(state) || '';
      }
    } catch (_e) {}
    return '';
  }

  function syncBuildStatsItemSlug() {
    try {
      const slug = computeEditorItemSlug();
      try { window.__STX_ITEM_SLUG = slug || ''; } catch (_e) {}
      try {
        if (!window.selectedData || typeof window.selectedData !== 'object') window.selectedData = {};
        window.selectedData.itemSlug = slug || '';
        window.selectedData.editorItemContext = 'stx_simple_builder';
      } catch (_e) {}
      try {
        if (typeof window.refreshBuildStatsCore === 'function') {
          setTimeout(() => { try { window.refreshBuildStatsCore(); } catch (_e) {} }, 0);
        }
      } catch (_e) {}
    } catch (_e) {}
  }

  function wireEvents(){
    $('itemType').addEventListener('change', ()=>{
      hydrateTopSelectorsIfNeeded();
      clearImportedOutputLock();
      const itPick = stxNormalizeSimpleBuilderItemTypeUi(String($('itemType').value || '').trim());
      if (itPick === 'Weapon' && stxWeaponTypeIsHeavyLabel(state.weaponType)) state.weaponType = '';
      clearBuilderState(false);
      clearAllGeneratedCodeForNewItem({ source: 'simple' });
      try { refreshOutputs(true); } catch (_e) {}
      refreshManufacturer();
      refreshWeaponType();
      refreshRarity();
      invokeRefreshMainPart(true);
    });

    $('manufacturer').addEventListener('change', ()=>{
      clearImportedOutputLock();
      state.manufacturer = $('manufacturer').value || '';
      clearBuilderState(false);
      clearAllGeneratedCodeForNewItem({ source: 'simple' });
      try { refreshOutputs(true); } catch (_e) {}
      try { stxSyncCustomSelectIfWrapped($('manufacturer')); } catch (_e) {}
      refreshWeaponType();
      refreshRarity();
      invokeRefreshMainPart(true);
      syncBuildStatsItemSlug();
    });

    $('weaponType').addEventListener('change', ()=>{
      clearImportedOutputLock();
      // Keep state in sync before downstream refresh (fixes Heavy Weapon rarity/main pools)
      state.weaponType = $('weaponType').value || '';
      if (state.weaponType === 'Heavy') state.weaponType = 'Heavy Weapon';
      clearBuilderState(true);
      clearAllGeneratedCodeForNewItem({ source: 'simple' });
      try { refreshOutputs(true); } catch (_e) {}
      // Weapon type does not change the manufacturer list; keep it stable to avoid empty/invalid states.
      refreshManufacturer();
      refreshRarity();
      invokeRefreshMainPart(true);
    });

    $('level').addEventListener('change', ()=>{
      clearImportedOutputLock();
      state.level = Number($('level').value||1);
      refreshOutputs();
    });
    $('level2').addEventListener('change', ()=>{
      clearImportedOutputLock();
      state.level = Number($('level2').value||1);
      refreshOutputs();
    });

    $('rarity').addEventListener('change', (e)=>{
  if (e && e.isTrusted) state.__seedEnabled = true;
  state.rarity = $('rarity').value||'';
  // Rarity affects the core pool for several categories (notably Class Mods and Enhancements),
  // so rebuild the rarity-id part selector and dependent slots when it changes.
  const runRarityRefresh = () => { try { invokeRefreshMainPart(true); } catch (_e) {} };
  if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(runRarityRefresh);
  else runRarityRefresh();
});

    if ($('skinSelect')){
      let skinCamoSyncTimer = 0;
      const skinSyncDebounceMs = stxPerfLiteUi() ? 320 : 140;
      const resyncSkinCamo = (opts)=>{
        const saveBusy = typeof window.stxSaveYamlUiBusy === 'function' && window.stxSaveYamlUiBusy();
        if (opts && opts.immediate) {
          if (saveBusy) {
            /* Large-save extract owns the main thread — retry after it settles. */
            if (skinCamoSyncTimer) clearTimeout(skinCamoSyncTimer);
            skinCamoSyncTimer = setTimeout(() => { skinCamoSyncTimer = 0; resyncSkinCamo(opts); }, 1200);
            return;
          }
          if (skinCamoSyncTimer) { clearTimeout(skinCamoSyncTimer); skinCamoSyncTimer = 0; }
          const runSync = ()=>{
            try{
              syncSkinOptionsFromParent({
                skipTooltips: !(opts && opts.withTooltips),
                onDone: () => {}
              });
            }catch(_){}
          };
          if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(runSync);
          else setTimeout(runSync, 0);
          return;
        }
        if (skinCamoSyncTimer) clearTimeout(skinCamoSyncTimer);
        const delay = saveBusy ? Math.max(skinSyncDebounceMs, 1800) : skinSyncDebounceMs;
        skinCamoSyncTimer = setTimeout(() => {
          skinCamoSyncTimer = 0;
          if (typeof window.stxSaveYamlUiBusy === 'function' && window.stxSaveYamlUiBusy()) {
            resyncSkinCamo(opts);
            return;
          }
          try{
            syncSkinOptionsFromParent({
              skipTooltips: !(opts && opts.withTooltips),
              onDone: () => {}
            });
          }catch(_){}
        }, delay);
      };
      const observeSourceSelect = (docObj, id)=>{
        try{
          const d = docObj || document;
          const src = d ? d.getElementById(id) : null;
          if (!src || src.__stxSkinSyncObsV1) return;
          const mo = new MutationObserver(()=>{
            if (!$('skinSelect').__stxSkinSyncArmedV1) return;
            resyncSkinCamo();
          });
          mo.observe(src, { childList:true, subtree:true });
          src.__stxSkinSyncObsV1 = mo;
        }catch(_){}
      };
      const observeSkinSources = ()=>{
        try{
          const pd = (window.parent && window.parent.document) ? window.parent.document : document;
          ['skin','skinCamo'].forEach((id)=>observeSourceSelect(pd, id));
        }catch(_){}
      };
      const armInitialSkinSync = (opts)=>{
        if (!$('skinSelect').__stxSkinSyncArmedV1) {
          $('skinSelect').__stxSkinSyncArmedV1 = true;
          observeSkinSources();
        }
        resyncSkinCamo(opts);
        if (!__mainPartLazyWired || __mainPartHydrated) syncMainPartFromSkinSelection();
      };
      try { window.__stxArmSkinCamoSync = armInitialSkinSync; } catch (_) {}

      $('skinSelect').addEventListener('change', ()=>{
        clearImportedOutputLock(true);
        try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_) {}
        try {
          const gDes = document.getElementById('guidedOutputDeserialized');
          if (gDes) {
            gDes.__ccUserTailEdit = false;
            /* Allow Skin brace to rewrite a longer imported mirror. */
            if (gDes.__ccImportedValue) gDes.__ccImportedValue = null;
          }
        } catch (_) {}
        /* Stacked mixes may soft-pin rarity; single `{fam:id}` skins never rewrite rarity. */
        syncMainPartFromSkinSelection();
        try {
          const sc = getSelectedWeaponSkinAndCamo();
          let codeNow = (typeof computeFullDeserializedCode === 'function') ? String(computeFullDeserializedCode() || '').trim() : '';
          const live = (typeof getSharedDeserialized === 'function') ? String(getSharedDeserialized() || '').trim() : '';
          const skinNorm = sc && sc.rarityToken ? String(sc.rarityToken).replace(/\s+/g, '') : '';
          const rebuildHasSkin = !!(skinNorm && codeNow.replace(/\s+/g, '').indexOf(skinNorm) >= 0);
          /* If rebuild dropped the brace (frozen/partial state), patch the longest live || serial. */
          if (sc && (sc.rarityToken || sc.camoToken || sc.spawnToken) && !rebuildHasSkin && live.indexOf('||') >= 0) {
            const patched = stxOverlaySkinCamoOnDeserialized(live, sc);
            if (patched && patched.indexOf('||') >= 0) codeNow = patched;
          }
          if (codeNow && codeNow.indexOf('||') >= 0 && typeof writeSharedItemCode === 'function') {
            writeSharedItemCode({ deser: codeNow, source: 'simple', force: true });
          }
        } catch (_) {}
        refreshOutputs(true);
        try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
      });
      if ($('camoSelect')) $('camoSelect').addEventListener('change', ()=>{
        clearImportedOutputLock(true);
        refreshOutputs(true);
        try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_) {}
      });

      const lazyArm = ()=>{ armInitialSkinSync(); };
      $('skinSelect').addEventListener('focus', lazyArm, { once: true, passive: true });
      $('skinSelect').addEventListener('pointerdown', lazyArm, { once: true, passive: true });
      if ($('camoSelect')) {
        $('camoSelect').addEventListener('focus', lazyArm, { once: true, passive: true });
        $('camoSelect').addEventListener('pointerdown', lazyArm, { once: true, passive: true });
      }
      function wireCustomSelectSkinArm(selId) {
        const sel = $(selId);
        if (!sel) return;
        const bindDisplay = ()=>{
          const wrap = sel.closest && sel.closest('.custom-select-wrapper');
          if (!wrap) return false;
          const display = wrap.querySelector('.custom-select-display');
          if (!display || display.__stxSkinLazyArmBound) return !!display;
          display.__stxSkinLazyArmBound = true;
          display.addEventListener('pointerdown', lazyArm, { passive: true });
          display.addEventListener('click', lazyArm, { passive: true });
          return true;
        };
        if (bindDisplay()) return;
        try {
          const obs = new MutationObserver(()=>{ if (bindDisplay()) obs.disconnect(); });
          const root = sel.parentNode || document.body;
          obs.observe(root, { childList: true, subtree: true });
          [400, 1200, 2500].forEach((ms)=> setTimeout(bindDisplay, ms));
        } catch (_) {}
      }
      wireCustomSelectSkinArm('skinSelect');
      wireCustomSelectSkinArm('camoSelect');

      function scheduleBackgroundSkinSync() {
        const run = ()=>{ armInitialSkinSync(); };
        if (typeof window.stxWhenSplashDismissed === 'function') {
          window.stxWhenSplashDismissed(function () {
            const delay = stxPerfLiteUi() ? 5200 : 3800;
            if (typeof window.stxQueueIdleWork === 'function') window.stxQueueIdleWork(run, delay);
            else if (typeof window.stxScheduleIdle === 'function') window.stxScheduleIdle(run, delay);
            else setTimeout(run, delay);
          });
        } else if (typeof window.stxQueueIdleWork === 'function') {
          window.stxQueueIdleWork(run, 2000);
        } else if (typeof window.stxScheduleIdle === 'function') {
          window.stxScheduleIdle(run, 1500);
        } else {
          setTimeout(run, 1200);
        }
      }
      scheduleBackgroundSkinSync();

      if (!window.__stxSkinSyncHooksV1){
        window.__stxSkinSyncHooksV1 = true;
        ['loadSkinOptions'].forEach((fnName)=>{
          const orig = window[fnName];
          if (typeof orig !== 'function' || orig.__stxSkinSyncWrappedV1) return;
          const wrapped = function(){
            const out = orig.apply(this, arguments);
            armInitialSkinSync();
            return out;
          };
          wrapped.__stxSkinSyncWrappedV1 = true;
          window[fnName] = wrapped;
        });
        window.addEventListener('load', ()=>{
          if (typeof window.stxQueueIdleWork === 'function') {
            window.stxQueueIdleWork(()=>{ armInitialSkinSync(); }, stxPerfLiteUi() ? 4500 : 2800);
          } else if (typeof window.stxScheduleIdle === 'function') {
            window.stxScheduleIdle(()=>{ armInitialSkinSync(); }, stxPerfLiteUi() ? 4500 : 2800);
          }
        });
      }
    }

    if ($('seedInput')){
      $('seedInput').addEventListener('input', (e)=>{
        if (e && e.isTrusted) state.__seedEnabled = true;
        const v = String($('seedInput').value || '').trim();
        if (!v){ state.seedAuto = null; state.seedKey = null; }
        refreshOutputs();
      });
    }

    $('mainPart').addEventListener('change', ()=>{
      clearImportedOutputLock();
      // selecting main part resets builder state (slots etc.)
      state.slots = {};
      state.primaryElement = 'None';
      state.elementStack = [];
      state.dualElementUseMaliwanSwitch = false;
      state.extras = [];
      refreshBuilder();
      syncMainPartPreview();
    });

    const idModeEl = $('idMode');
    if (idModeEl){
      idModeEl.addEventListener('change', ()=>{
        clearImportedOutputLock();
        state.idMode = !!idModeEl.checked;
        var ccPart = document.getElementById('ccPartEntryMode');
        if (ccPart) ccPart.checked = state.idMode;
        updateModeLabel();
        refreshTopSelectors(stxPerfLiteUi() ? { deferHeavy: true } : undefined);
        refreshBuilder();
        try { if (typeof window.syncGuidedVisibility === 'function') window.syncGuidedVisibility(); } catch (_) {}
        try { if (typeof window.refreshPartSections === 'function') window.refreshPartSections(); } catch (_) {}
      });
    }

    var ccPartMode = document.getElementById('ccPartEntryMode');
    if (ccPartMode){
      ccPartMode.addEventListener('change', ()=>{
        clearImportedOutputLock();
        state.idMode = !!ccPartMode.checked;
        if ($('idMode')) $('idMode').checked = state.idMode;
        updateModeLabel();
        refreshTopSelectors(stxPerfLiteUi() ? { deferHeavy: true } : undefined);
        refreshBuilder();
        try { if (typeof window.syncGuidedVisibility === 'function') window.syncGuidedVisibility(); } catch (_) {}
        try { if (typeof window.refreshPartSections === 'function') window.refreshPartSections(); } catch (_) {}
      });
    }

    var forceType = document.getElementById('ccForceTypeIdTokens');
    if (forceType){
      forceType.addEventListener('change', ()=>{
        clearImportedOutputLock();
        state.forceTypeIdTokens = !!forceType.checked;
        refreshOutputs();
      });
    }

    if ($('buybackFlag')) $('buybackFlag').addEventListener('change', ()=>{
      state.buybackFlag = !!$('buybackFlag').checked;
      try {
        const g = document.getElementById('ccGuidedBuybackFlag');
        if (g) g.checked = state.buybackFlag;
      } catch (_e) {}
      try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_e2) {}
      try { if (typeof window.syncChecklistClassModOutputs === 'function') window.syncChecklistClassModOutputs(); } catch (_eCm) {}
      try { if (typeof window.stxPatchSerialModifierFlagsIntoOutputs === 'function') window.stxPatchSerialModifierFlagsIntoOutputs(); } catch (_eP) {}
      refreshOutputs(true);
      try { if (typeof window.refreshGuidedOutput === 'function') window.refreshGuidedOutput(); } catch (_e3) {}
      try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_e4) {}
    });
    if ($('firmwareLock')) $('firmwareLock').addEventListener('change', ()=>{
      state.lockFirmware = !!$('firmwareLock').checked;
      try {
        const g = document.getElementById('ccGuidedFirmwareLockFlag');
        if (g) g.checked = state.lockFirmware;
      } catch (_e) {}
      try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_e2) {}
      try { if (typeof window.syncChecklistClassModOutputs === 'function') window.syncChecklistClassModOutputs(); } catch (_eCm) {}
      try { if (typeof window.stxPatchSerialModifierFlagsIntoOutputs === 'function') window.stxPatchSerialModifierFlagsIntoOutputs(); } catch (_eP) {}
      refreshOutputs(true);
      try { if (typeof window.refreshGuidedOutput === 'function') window.refreshGuidedOutput(); } catch (_e3) {}
      try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_e4) {}
    });
    var pearlOv = document.getElementById('stxPearlOverride');
    if (pearlOv) {
      pearlOv.addEventListener('change', ()=>{
        clearImportedOutputLock();
        try {
          const g = document.getElementById('ccGuidedPearlOverride');
          if (g) g.checked = !!pearlOv.checked;
        } catch (_e) {}
        refreshTopSelectors();
        refreshBuilder();
        try { if (typeof window.ensureStaticGuidedIcons === 'function') window.ensureStaticGuidedIcons(); } catch (_e) {}
        try { if (typeof window.refreshGuidedBuilderDropdowns === 'function') window.refreshGuidedBuilderDropdowns(); } catch (_e) {}
        try { if (typeof window.refreshPartSections === 'function') window.refreshPartSections(); } catch (_e) {}
        refreshOutputs(true);
        try { if (typeof window.syncFloatingOutput === 'function') window.syncFloatingOutput(true); } catch (_e) {}
      });
    }
    if ($('allPartsToggle')) $('allPartsToggle').addEventListener('change', ()=>{
      stxSyncAllPartsToggleUi(!!$('allPartsToggle').checked);
      refreshBuilder();
    });

    $('btnNew').addEventListener('click', ()=>resetAll());
    $('btnClear').addEventListener('click', ()=>clearParts());

    // Enable seed generation after the user interacts (prevents random seed on initial load).
    // Trusted events only (ignores programmatic changes).
    document.addEventListener('pointerdown', (e)=>{ if (e && e.isTrusted) state.__seedEnabled = true; }, true);
    document.addEventListener('keydown', (e)=>{ if (e && e.isTrusted) state.__seedEnabled = true; }, true);

    $('btnCopyList').addEventListener('click', async ()=>{
      await copyToClipboard($('outList').value||'');
    });
    $('btnCopyJson').addEventListener('click', async ()=>{
      await copyToClipboard($('outJson').value||'');
    });

    // Import buttons are wired in index.html (initImportToBuilder) with target-specific handlers.

    // Simple Builder Quick Presets (`{fam:id}` rows → state.extras so serialized code + floating panel stay in sync)
    const simplePresetSel = $('simpleBuilderPresetSelect');
    const simpleMorePresetSel = $('simpleBuilderMorePresetSelect');
    const simplePresetAddBtn = $('simpleBuilderPresetAddBtn');
    if (simplePresetSel && simpleMorePresetSel && typeof window.ensurePresetSelectMutex === 'function') {
      window.ensurePresetSelectMutex(simplePresetSel, simpleMorePresetSel);
    }
    if (simplePresetSel && simplePresetAddBtn) {
      simplePresetAddBtn.addEventListener('click', () => {
        const code = (typeof window.resolveActivePresetPartValue === 'function')
          ? window.resolveActivePresetPartValue(simplePresetSel, simpleMorePresetSel)
          : String((simplePresetSel && simplePresetSel.value) || (simpleMorePresetSel && simpleMorePresetSel.value) || '').trim();
        if (!code) return;
        try { window.__CC_LAST_CODE_TARGET = 'simple'; } catch (_) {}
        if (stxAppendTailTokenViaExtras(code)) return;
        if (typeof window.appendToOutCode === 'function') {
          window.appendToOutCode(code);
          return;
        }
        const out = $('outCode');
        if (!out) return;
        const serial = String(out.value || '').trim();
        const dbl = serial.indexOf('||');
        if (!dbl && !serial) {
          alert('Pick a rarity / main part in Simple Builder first so the item header exists before adding presets.');
          return;
        }
        const tail = dbl >= 0 ? serial.slice(dbl + 2).trim() : '';
        const nextTail = (tail ? tail + ' ' : '') + code;
        out.value = dbl >= 0 ? serial.slice(0, dbl + 2) + nextTail : (serial + ' || ' + nextTail);
        try { refreshOutputs(true); } catch (_) {}
        try { if (typeof window.refreshBuildStatsCore === 'function') window.refreshBuildStatsCore(); } catch (_) {}
      });
    }
  }

  const STX_SIMPLE_PRESET_BOOST_POOLS_FALLBACK = Object.freeze({
    damage: [{ key: 22, value: '72' }, { key: 9, value: '28' }, { key: 9, value: '32' }, { key: 9, value: '40' }, { key: 9, value: '55' }, { key: 9, value: '59' }, { key: 9, value: '62' }, { key: 9, value: '68' }],
    accuracy: [{ key: 13, value: '12' }, { key: 9, value: '48' }],
    reload: [{ key: 24, value: '44' }, { key: 9, value: '61' }],
    firerate: [{ key: 14, value: '1' }, { key: 27, value: '15' }],
    ammo: [{ key: 18, value: '14' }, { key: 27, value: '75' }],
    splash: [{ key: 6, value: '33' }, { key: 9, value: '89' }, { key: 24, value: '18' }, { key: 243, value: '32' }, { key: 243, value: '33' }, { key: 243, value: '34' }, { key: 243, value: '35' }, { key: 243, value: '36' }],
    crit: [{ key: 3, value: '6' }, { key: 24, value: '33' }, { key: 243, value: '37' }, { key: 243, value: '38' }, { key: 243, value: '39' }, { key: 243, value: '40' }, { key: 243, value: '41' }],
    splat: [{ key: 243, value: '32' }, { key: 243, value: '33' }, { key: 243, value: '34' }, { key: 243, value: '35' }, { key: 243, value: '36' }],
    nova: [{ key: 243, value: '37' }, { key: 243, value: '38' }, { key: 243, value: '39' }, { key: 243, value: '40' }, { key: 243, value: '41' }],
    immunity: [{ key: 243, value: '27' }, { key: 243, value: '28' }, { key: 243, value: '29' }, { key: 243, value: '31' }, { key: 243, value: '42' }, { key: 243, value: '43' }, { key: 243, value: '44' }, { key: 243, value: '46' }],
    resistance: [{ key: 243, value: '22' }, { key: 243, value: '23' }, { key: 243, value: '24' }, { key: 243, value: '26' }, { key: 243, value: '47' }, { key: 243, value: '49' }, { key: 243, value: '50' }, { key: 243, value: '51' }],
    elemental: [{ key: 243, value: '98' }, { key: 243, value: '99' }, { key: 243, value: '100' }, { key: 243, value: '101' }, { key: 243, value: '102' }]
  });

  function stxSimplePresetBoostPoolsReady(pools){
    if (!pools || typeof pools !== 'object') return false;
    return Object.keys(pools).some((k) => Array.isArray(pools[k]) && pools[k].length);
  }

  function getSimplePresetBoostPools(){
    const w = window.PRESET_BOOST_POOLS;
    if (stxSimplePresetBoostPoolsReady(w)) return w;
    return STX_SIMPLE_PRESET_BOOST_POOLS_FALLBACK;
  }

  function loadSimplePresets() {
    const sel = $('simpleBuilderPresetSelect');
    const moreSel = $('simpleBuilderMorePresetSelect');
    if (!sel) return;

    const cats = [
      ['damage', 'Damage'],
      ['accuracy', 'Accuracy'],
      ['reload', 'Reload Speed'],
      ['firerate', 'Fire Rate'],
      ['ammo', 'Ammo'],
      ['splash', 'Splash Damage'],
      ['crit', 'Crit Damage'],
      ['splat', 'Repkit — Splat'],
      ['nova', 'Repkit — Nova'],
      ['immunity', 'Repkit — Immunity'],
      ['resistance', 'Repkit — Resistance'],
      ['elemental', 'Repkit — Elemental']
    ];
    function tokenForPresetEntry(entry) {
      if (!entry) return '';
      if (entry.bareId) return '{' + String(entry.bareId) + '}';
      const k = entry.key != null ? entry.key : entry.k;
      const v = entry.value != null ? entry.value : entry.v;
      if (k == null || v == null) return '';
      return `{${String(k)}:${String(v)}}`;
    }
    function partNameForToken(tok) {
      const m = String(tok || '').match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
      if (!m) return '';
      const idRaw = `${Number(m[1])}:${Number(m[2])}`;
      const parts = (window.STX_DATASET && window.STX_DATASET.ALL_PARTS) ? window.STX_DATASET.ALL_PARTS : [];
      for (let i = 0; i < parts.length; i++) {
        const p = parts[i];
        if (!p) continue;
        if (String(p.idRaw || p.idraw || '').trim() !== idRaw) continue;
        return String(p.name || p.legendaryName || p.displayName || '').trim();
      }
      return '';
    }
    function partForToken(tok) {
      const m = String(tok || '').match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
      if (!m) return null;
      const idRaw = `${Number(m[1])}:${Number(m[2])}`;
      const parts = (window.STX_DATASET && window.STX_DATASET.ALL_PARTS) ? window.STX_DATASET.ALL_PARTS : [];
      for (let i = 0; i < parts.length; i++) {
        const p = parts[i];
        if (p && String(p.idRaw || p.idraw || '').trim() === idRaw) return p;
      }
      return null;
    }
    function quickPresetTitle(tok, catLabel, name) {
      const p = partForToken(tok);
      let tip = '';
      if (p && typeof window.partTooltipText === 'function') {
        try { tip = String(window.partTooltipText(p) || '').trim(); } catch (_) { tip = ''; }
      }
      if (tip) return tip;
      return name
        ? `${catLabel}: ${name}\nOther stats: hover data unavailable for this part.`
        : `${catLabel}: ${tok}\nOther stats: dataset name/stats unavailable, token still adds correctly.`;
    }
    const updateSimplePresets = () => {
      const currentVal = sel.value;
      const currentMore = moreSel ? moreSel.value : '';
      const pools = getSimplePresetBoostPools();
      const hasPools = stxSimplePresetBoostPoolsReady(pools);
      sel.innerHTML = hasPools
        ? '<option value="">-- Select preset part --</option>'
        : '<option value="">Loading preset parts…</option>';
      for (const [catKey, catLabel] of cats) {
        const pool = pools[catKey] || [];
        if (!Array.isArray(pool) || !pool.length) continue;
        const group = document.createElement('optgroup');
        group.label = catLabel;
        for (const entry of pool) {
          const tok = tokenForPresetEntry(entry);
          if (!tok) continue;
          const name = partNameForToken(tok);
          const opt = new Option(name ? `${tok} - ${name}` : `${tok} - Preset token`, tok);
          opt.title = quickPresetTitle(tok, catLabel, name);
          group.appendChild(opt);
        }
        if (group.children.length) sel.appendChild(group);
      }
      if (currentVal) sel.value = currentVal;
      try { stxRebuildCustomSelectIfWrapped(sel); } catch (_) {}
      if (moreSel && typeof window.populateFlatMorePresetParts === 'function') {
        window.populateFlatMorePresetParts(moreSel);
        if (currentMore) moreSel.value = currentMore;
        try { stxRebuildCustomSelectIfWrapped(moreSel); } catch (_) {}
      }
    };

    if (!sel.__simplePresetHooksBound) {
      sel.__simplePresetHooksBound = true;
      const itemTypeEl = $('itemType');
      if (itemTypeEl) {
        itemTypeEl.addEventListener('change', () => {
          try { updateSimplePresets(); } catch (_) {}
        });
      }
      const refreshAfterDeferred = () => {
        if (typeof window.stxSaveYamlUiBusy === 'function' && window.stxSaveYamlUiBusy()) {
          setTimeout(refreshAfterDeferred, 1500);
          return;
        }
        try { updateSimplePresets(); } catch (_) {}
        try { stxRefreshBuilderAfterDatasetGrowth(); } catch (_) {}
      };
      window.addEventListener('stx:deferred-core-ready', refreshAfterDeferred);
      window.addEventListener('stx:full-scripts-ready', refreshAfterDeferred);
    }

    try { window.refreshSimpleBuilderPresets = updateSimplePresets; } catch (_) {}

    updateSimplePresets();
    if (!sel.__simplePresetReloadTimer) {
      var tries = 0;
      sel.__simplePresetReloadTimer = setInterval(() => {
        tries++;
        updateSimplePresets();
        const parts = (window.STX_DATASET && window.STX_DATASET.ALL_PARTS) ? window.STX_DATASET.ALL_PARTS : [];
        const poolsReady = stxSimplePresetBoostPoolsReady(window.PRESET_BOOST_POOLS);
        const datasetReady = parts.length > 0;
        if ((poolsReady && datasetReady) || tries > 40) {
          clearInterval(sel.__simplePresetReloadTimer);
          sel.__simplePresetReloadTimer = null;
        }
      }, 500);
    }
  }

  function exposeBuilderApi(){
    try {
      window.getManufacturersForCategory = (catUi, weaponType) => {
        const r = computeManufacturersForCategory(catUi, weaponType);
        return r ? r.mans : [];
      };
      window.computeGuidedPrefix = computeGuidedPrefix;
      window.normalizeIdTokensForBaseFamily = normalizeIdTokensForBaseFamily;
      window.compressConsecutiveFamilyRefs = compressConsecutiveFamilyRefs;
      window.tokenForPart = tokenForPart;
      window.stxPickPearlOverrideBraceToken = stxPickPearlOverrideBraceToken;
      window.stxPickClassModPearlOverrideBraceToken = stxPickClassModPearlOverrideBraceToken;
      window.stxPrependPearlOverrideToTailSeq = stxPrependPearlOverrideToTailSeq;
      window.stxReplacePearlOverrideOnTailSeq = stxReplacePearlOverrideOnTailSeq;
      window.stxPearlTokensDuplicateForOverride = stxPearlTokensDuplicateForOverride;
      window.stxPearlOverrideNormalized = stxPearlOverrideNormalized;
      window.stxIsPearlOverrideUiActive = stxIsPearlOverrideUiActive;
      window.stxPearlPipUrlInsteadOfLegendaryAug = stxPearlPipUrlInsteadOfLegendaryAug;
      window.refreshTopSelectors = refreshTopSelectors;
      window.refreshBuilder = refreshBuilder;
      window.filterPartsForGuided = filterParts;
      window.stxSelectLogicalDedupeKey = stxSelectLogicalDedupeKey;
      window.stxStableDropdownDedupeKey = stxStableDropdownDedupeKey;
      window.stxPartCarriesLegendaryEffectWeaponFamilyBarrel = stxPartCarriesLegendaryEffectWeaponFamilyBarrel;
      window.stxPartMatchesLegendaryPoolWeaponType = stxPartMatchesLegendaryPoolWeaponType;
      window.stxSyncDualElementMaliwanSwitch = stxSyncDualElementMaliwanSwitch;
      window.stxSyncAllPartsToggleUi = stxSyncAllPartsToggleUi;
      window.weaponPearlElemPartMatch = weaponPearlElemPartMatch;
      window.weaponPearlStatPartMatch = weaponPearlStatPartMatch;
      window.stxPartDropdownRichnessScore = stxPartDropdownRichnessScore;
      window.stxRarityOptgroupLabelFromPart = stxRarityOptgroupLabelFromPart;
      window.stxRarityTierFromPartForGrouping = stxRarityTierFromPartForGrouping;
      window.stxGrenadeSpawnPrefixForUiManufacturer = stxGrenadeSpawnPrefixForUiManufacturer;
      window.stxGrenadeGadgetRowMatchesSelectedManufacturer = stxGrenadeGadgetRowMatchesSelectedManufacturer;
      window.stxWeaponRowMatchesSelectedManufacturer = stxWeaponRowMatchesSelectedManufacturer;
      window.stxIsWeaponNaturalBodyPoolRowCode = stxIsWeaponNaturalBodyPoolRowCode;
      window.stxIsWeaponBodySlotFallbackRowCode = stxIsWeaponBodySlotFallbackRowCode;
      window.stxSlotRequiresItemManufacturer = stxSlotRequiresItemManufacturer;
      window.classModFamilyIdForCharacter = classModFamilyIdForCharacter;
      window.stxIsBrokenClassmodDatasetPlaceholderPart = stxIsBrokenClassmodDatasetPlaceholderPart;
      window.getLegacyClassModNameParts = getLegacyClassModNameParts;
      window.getLegacyClassModSkillParts = getLegacyClassModSkillParts;
      window.stxInvalidateSimpleBuilderPartCaches = stxInvalidateSimpleBuilderPartCaches;
      window.stxRefreshBuilderAfterDatasetGrowth = stxRefreshBuilderAfterDatasetGrowth;
      window.importTokens = importTokens;
      window.refreshOutputs = refreshOutputs;
      window.isSkinTokenCandidate = isSkinTokenCandidate;
      window.stxPartRedTextSubForDropdown = stxPartRedTextSubForDropdown;
      window.stxPearlGearCatalogRowForPart = stxPearlGearCatalogRowForPart;
      window.stxEnhancementCoreEffectText = stxEnhancementCoreEffectText;
      window.__ccFinalizeImportToBuilders = finalizeCcImportToBuilders;
    } catch (_e) {}
  }

  function initDeferredWork(advLanding){
    if (!advLanding) {
      if (typeof window.loadGuidedManufacturers === 'function') window.loadGuidedManufacturers();
      if (typeof window.wireLazyGuidedDropdownRefresh === 'function') window.wireLazyGuidedDropdownRefresh();
    }
    loadSimplePresets();
    if (!stxPerfLiteUi()) {
      refreshOutputs();
    } else {
      var panel = document.getElementById('stxSimpleBuilderPanel');
      var liteOutputsWired = false;
      var armLiteOutputs = function () {
        if (liteOutputsWired) return;
        liteOutputsWired = true;
        try { refreshOutputs(); } catch (_e) {}
      };
      if (panel) {
        panel.addEventListener('pointerdown', armLiteOutputs, { once: true, passive: true });
        panel.addEventListener('focusin', armLiteOutputs, { once: true });
      }
      if (typeof window.stxWhenSplashDismissed === 'function') {
        window.stxWhenSplashDismissed(function () {
          if (typeof window.stxQueueIdleWork === 'function') {
            window.stxQueueIdleWork(armLiteOutputs, 12000);
          } else if (typeof window.stxScheduleIdle === 'function') {
            window.stxScheduleIdle(armLiteOutputs, 12000);
          }
        });
      }
    }
  }

  function init(){
    {
      const idEl = $('idMode');
      if (idEl && typeof idEl.checked === 'boolean'){
        state.idMode = !!idEl.checked;
      } else {
        state.idMode = true;
        if (idEl) idEl.checked = true;
      }
      const ccEl = document.getElementById('ccPartEntryMode');
      if (ccEl) ccEl.checked = state.idMode;
    }
    // Serial modifiers in header before || (firmware lock 9,1; buyback 10,1)
    state.buybackFlag = false;
    state.lockFirmware = false;
    if ($('buybackFlag')) $('buybackFlag').checked = false;
    if ($('firmwareLock')) $('firmwareLock').checked = false;
    try {
      const gf = document.getElementById('ccGuidedFirmwareLockFlag');
      const gb = document.getElementById('ccGuidedBuybackFlag');
      if (gf) gf.checked = false;
      if (gb) gb.checked = false;
    } catch (_e) {}
    // Part pool scope (manufacturer-only vs all manufacturers)
    stxSyncAllPartsToggleUi(false);
    state.forceTypeIdTokens = false;
    try{
      var forceTypeInit = document.getElementById('ccForceTypeIdTokens');
      if (forceTypeInit) forceTypeInit.checked = false;
    }catch(_){}
    updateModeLabel();

    var advLanding = typeof window.__ccIsAdvSearchDeepLinkV1 === 'function' && window.__ccIsAdvSearchDeepLinkV1();

    // Ensure level defaults are sane on first load (some browsers may ignore initial value in srcdoc).
    try{
      const lv = $('level');
      if (lv && (!String(lv.value||'').trim() || Number(lv.value) <= 1)) lv.value = '60';
      const lv2 = $('level2');
      if (lv2 && (!String(lv2.value||'').trim() || Number(lv2.value) <= 1)) lv2.value = '60';
      state.level = 60;
    }catch(_e){}

    if (!advLanding) {
      refreshTopSelectors({ deferHeavy: true });
    }
    wireEvents();
    exposeBuilderApi();
    try {
      if (!window.__stxSimpleDatasetGrowthHooked) {
        window.__stxSimpleDatasetGrowthHooked = true;
        const onDatasetGrowth = () => {
          if (typeof window.stxSaveYamlUiBusy === 'function' && window.stxSaveYamlUiBusy()) {
            setTimeout(onDatasetGrowth, 1500);
            return;
          }
          try { stxRefreshBuilderAfterDatasetGrowth(); } catch (_e) {}
        };
        window.addEventListener('stx:deferred-core-ready', onDatasetGrowth);
        window.addEventListener('stx:full-scripts-ready', onDatasetGrowth);
        window.addEventListener('stx:dataset-growth', onDatasetGrowth);
        /* Deferred may have finished before Simple finished booting — refresh once if parts already grew. */
        try {
          const n = (window.STX_DATASET && window.STX_DATASET.ALL_PARTS && window.STX_DATASET.ALL_PARTS.length) || 0;
          if (n && window.__stxDeferredCoreReady) onDatasetGrowth();
        } catch (_e) {}
      }
    } catch (_e) {}
    try {
      window.__stxBuilderInteractive = true;
      window.dispatchEvent(new CustomEvent('stx:builder-interactive'));
    } catch (_e) {}

    var deferWork = function () { initDeferredWork(advLanding); };
    if (stxPerfLiteUi()) {
      if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(deferWork);
      else setTimeout(deferWork, 0);
    } else {
      deferWork();
    }
  }

  // wait for dataset to load
  const wait = () => {
    if (window.STX_DATASET && Array.isArray(window.STX_DATASET.ALL_PARTS) && window.STX_DATASET.ALL_PARTS.length){
      const boot = () => {
        try { init(); } catch (bootErr) { console.error(bootErr); }
      };
      const scheduleBoot = () => {
        if (typeof window.stxWhenSplashDismissed === 'function') {
          window.stxWhenSplashDismissed(boot, { priority: true });
        } else {
          boot();
        }
      };
      scheduleBoot();
    } else {
      $('dsStatus').textContent = 'waiting for dataset...';
      setTimeout(wait, 50);
    }
  };
  wait();
})();
