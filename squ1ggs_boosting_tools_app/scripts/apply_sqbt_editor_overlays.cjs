/**
 * Re-apply SQBT-only Simple Builder patches after sync_editor.mjs copies D:\new edit.
 */
const fs = require("fs");
const path = require("path");

const corePath = path.join(__dirname, "..", "renderer", "editor", "js", "stx-simple-builder-core.js");

function mustReplace(src, oldStr, newStr, label) {
  if (!src.includes(oldStr)) {
    console.error("MISSING patch anchor:", label);
    process.exitCode = 1;
    return src;
  }
  return src.replace(oldStr, newStr);
}

let s = fs.readFileSync(corePath, "utf8");

// Firmware slot order (3.10.3): additional parts before firmware on weapons.
s = mustReplace(
  s,
  `    {key:'legendary', label:'Legendary Perks', partType:'Legendary Perks', multi:true},
    {key:'firmware', label:'Firmware', partType:'Firmware'},
    {key:'additionalParts', label:'Additional (other parts)', partType:'', multi:true, customType:'weaponAdditionalParts'},`,
  `    {key:'legendary', label:'Legendary Perks', partType:'Legendary Perks', multi:true},
    {key:'additionalParts', label:'Additional (other parts)', partType:'', multi:true, customType:'weaponAdditionalParts'},
    {key:'firmware', label:'Firmware', partType:'Firmware'},`,
  "weapon-firmware-order"
);

// Enhancement: firmware before stats (NCS emit order).
s = mustReplace(
  s,
  `    Enhancement: [
      {key:'core', label:'Core', partType:'Core'},
      {key:'stats', label:'Stat Group 1', partType:'Stats', multi:true},
      {key:'firmware', label:'Firmware', partType:'Firmware', multi:true},`,
  `    Enhancement: [
      {key:'core', label:'Core', partType:'Core'},
      {key:'firmware', label:'Firmware', partType:'Firmware', multi:true},
      {key:'stats', label:'Stat Group 1', partType:'Stats', multi:true},`,
  "enhancement-firmware-order"
);

// Manufacturer repkit family inference (jak_repair_kit etc.).
const repkitBlock = `
  /**
   * Manufacturer repair-kit TypeIDs (from rarity comps). Body rows often ship with bare
   * \`idRaw: "2"\` and no family — packing \`{2}\` makes the kit show as a naked "Stim"/etc.
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
    const m = c.match(/^([a-z0-9]+)_repair_kit\\./);
    if (!m) return NaN;
    const fam = STX_REPKIT_MFR_FAMILY[m[1]];
    return Number.isFinite(fam) ? Number(fam) : NaN;
  }

`;

s = mustReplace(s, "  /** Emit `{fam:id}` / `{id}` style token when dataset metadata allows; else ''. */\n  function numericTokenFromPart(p){", repkitBlock + "  /** Emit `{fam:id}` / `{id}` style token when dataset metadata allows; else ''. */\n  function numericTokenFromPart(p){", "repkit-family-block");

s = mustReplace(
  s,
  `          if (c.indexOf('repair_kit.') === 0) {
            return \`{243:\${raw}}\`;
          }
          if (c.indexOf('heavy_weapon_gadget.') === 0) {`,
  `          if (c.indexOf('repair_kit.') === 0) {
            return \`{243:\${raw}}\`;
          }
          const rkFam = stxRepkitManufacturerFamilyFromCode(c);
          if (Number.isFinite(rkFam)) {
            return \`{\${rkFam}:\${raw}}\`;
          }
          if (c.indexOf('heavy_weapon_gadget.') === 0) {`,
  "numericToken-repkit"
);

s = mustReplace(
  s,
  `      if (c.indexOf('repair_kit.') === 0) return 243;
      if (c.indexOf('heavy_weapon_gadget.') === 0) return 244;`,
  `      if (c.indexOf('repair_kit.') === 0) return 243;
      const rkFam0 = stxRepkitManufacturerFamilyFromCode(c);
      if (Number.isFinite(rkFam0)) return rkFam0;
      if (c.indexOf('heavy_weapon_gadget.') === 0) return 244;`,
  "inferredFamily-repkit"
);

// Class Mod pearl override — avoid gun-family hooks (TED_SG card bug).
const classModPearlFns = `
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
      return /(?:^|[._])(?:ps|sg|sm|ar|sr|hw)(?:[._]|$)/.test(code) || /\\bTED_SG\\b|\\bDAD_SG\\b|\\bJAK_SG\\b/i.test(code);
    });
  }

  /**
   * Class Mod pearl override must stay off gun families. \`{7:54}\` TED_SG makes item cards
   * show Shotgun even when the craft is a classmod.
   */
  function stxClassModSafePearlBrace(tok, baseFamilyId){
    const bf = Number(baseFamilyId);
    const bare = '{54}';
    let t = String(tok || '').trim();
    if (!t) return bare;
    const dual = t.match(/^\\{\\s*(\\d+)\\s*:\\s*(\\d+)\\s*\\}$/);
    if (dual){
      const fam = Number(dual[1]);
      const id = Number(dual[2]);
      if (Number.isFinite(fam) && Number.isFinite(bf) && fam === bf) return bare;
      if (Number.isFinite(fam) && stxPearlFamilyLooksLikeGun(fam)) {
        const pid = Number.isFinite(id) && id >= 51 && id <= 60 ? id : 54;
        const altF = stxPearlForeignFamilyForPearlItemId(pid, bf);
        if (altF != null && Number.isFinite(altF) && !stxPearlFamilyLooksLikeGun(altF) && altF !== bf) {
          return \`{\${altF}:\${pid}}\`;
        }
        const table = stxPearlRaritiesTable();
        const cands = table.filter(r => {
          const rf = Number(r && r.familyId);
          if (!Number.isFinite(rf) || rf === bf) return false;
          if (stxPearlFamilyLooksLikeGun(rf)) return false;
          return stxIsPearlTierStxRarityRow(r) && Number((r.itemId != null) ? r.itemId : r.id) === pid;
        });
        if (cands.length) {
          cands.sort((a, b) => Number(a.familyId) - Number(b.familyId));
          return \`{\${Number(cands[0].familyId)}:\${pid}}\`;
        }
        return bare;
      }
      return t;
    }
    const single = t.match(/^\\{\\s*(\\d+)\\s*\\}$/);
    if (single) {
      const id = Number(single[1]);
      if (Number.isFinite(id) && id >= 51 && id <= 60) return \`{\${id}}\`;
    }
    return bare;
  }

  function stxPickClassModPearlOverrideBraceToken(baseFamilyId){
    const bf = Number(baseFamilyId);
    const raw = stxPickPearlOverrideBraceToken(bf, false);
    return stxClassModSafePearlBrace(raw, bf);
  }

`;

s = mustReplace(
  s,
  `  function stxPickPearlOverrideBraceToken(baseFamilyId, isWeapon){
    if (!isWeapon) return stxRewritePearlOverrideIfSameFamilyAsHeader(STX_PEARL_OVERRIDE_FIXED_NON_WEAPON, baseFamilyId);
    return stxPearlOverrideNormalized(STX_PEARL_OVERRIDE_FIXED_WEAPON, baseFamilyId);
  }

  function isStxSimplePearlOverrideChecked(){`,
  `  function stxPickPearlOverrideBraceToken(baseFamilyId, isWeapon){
    if (!isWeapon) return stxRewritePearlOverrideIfSameFamilyAsHeader(STX_PEARL_OVERRIDE_FIXED_NON_WEAPON, baseFamilyId);
    return stxPearlOverrideNormalized(STX_PEARL_OVERRIDE_FIXED_WEAPON, baseFamilyId);
  }
${classModPearlFns}
  function isStxSimplePearlOverrideChecked(){`,
  "classmod-pearl-fns"
);

const classModChecklist = `
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

`;

s = mustReplace(s, "  function computeOutputTokens(force){", classModChecklist + "  function computeOutputTokens(force){", "classmod-checklist");

s = mustReplace(
  s,
  `    if (Number.isFinite(raritySlotItemId)){
      rarityItemId = Number(raritySlotItemId);
    }
  const isWeapon = (state.itemType === 'Weapon') || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType) || (state.detectedCategory === 'Weapon');`,
  `    if (Number.isFinite(raritySlotItemId)){
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
      if (tierNow === 5 && !(Number.isFinite(rarityItemId) && rarityItemId >= 51 && rarityItemId <= 60)) {
        rarityItemId = 54;
      }
      if (isStxSimplePearlOverrideChecked()
          && !(Number.isFinite(rarityItemId) && rarityItemId >= 51 && rarityItemId <= 60)) {
        rarityItemId = 54;
      }
    } catch (_eCmPair) { /* keep prior rarityItemId */ }
  }
  const isWeapon = (state.itemType === 'Weapon') || stxSimpleBuilderItemTypeIsHeavyUi(state.itemType) || (state.detectedCategory === 'Weapon');`,
  "classmod-rarity-pairing"
);

s = mustReplace(
  s,
  `  let tailPartsNw = [rarityTok, partsSection].filter(Boolean);
  if (isStxSimplePearlOverrideChecked()){
    const pr = stxPickPearlOverrideBraceToken(baseFamilyId, false);
    tailPartsNw = stxPrependPearlOverrideToTailSeq(tailPartsNw, pr, baseFamilyId);
  }
  const tail = tailPartsNw.join(' ').trim();`,
  `  let tailPartsNw = [rarityTok, partsSection].filter(Boolean);
  const classModPearlTier =
    String(outputCategory) === 'Class Mod' &&
    Number.isFinite(selectedTier) &&
    Number(selectedTier) === 5;
  if (String(outputCategory) === 'Class Mod' && (isStxSimplePearlOverrideChecked() || classModPearlTier)){
    const pr = stxPickClassModPearlOverrideBraceToken(baseFamilyId);
    const barePearl = /^\\{\\s*(?:5[1-9]|60)\\s*\\}$/.test(String(pr || '').replace(/\\s+/g, ''));
    const rarityAlreadyPearl = (() => {
      const id = String(rarityTok || '').replace(/\\s+/g, '').match(/^\\{\\s*(?:\\d+\\s*:\\s*)?(5[1-9]|60)\\s*\\}$/);
      return !!id;
    })();
    if (pr && !(barePearl && rarityAlreadyPearl)) {
      tailPartsNw = stxPrependPearlOverrideToTailSeq(tailPartsNw, pr, baseFamilyId);
    }
  } else if (isStxSimplePearlOverrideChecked()){
    const pr = stxPickPearlOverrideBraceToken(baseFamilyId, false);
    tailPartsNw = stxPrependPearlOverrideToTailSeq(tailPartsNw, pr, baseFamilyId);
  }
  const tail = tailPartsNw.join(' ').trim();`,
  "classmod-pearl-tail"
);

s = mustReplace(
  s,
  `    let tokens = finalItems.map(x => String(x.tok));
    if (isStxSimplePearlOverrideChecked() && !(state.mainPart && state.mainPart.__fullDeserialized)){
      const b0 = getSelectedBaseItem();
      const bf = Number(b0 && b0.familyId);
      if (Number.isFinite(bf)){
        const isW = cat === 'Weapon' || (state && stxSimpleBuilderItemTypeIsHeavyUi(state.itemType));
        const pr = stxPickPearlOverrideBraceToken(bf, isW);
        if (pr){
          const pn = stxPearlOverrideNormalized(pr, bf);
          const first = tokens.length ? tokens[0] : '';
          if (!first || !stxPearlTokensDuplicateForOverride(first, pn, bf)) tokens.unshift(pn);
        }
      }
    }`,
  `    let tokens = finalItems.map(x => String(x.tok));
    const catPearlTier =
      cat === 'Class Mod' && Number.isFinite(getSelectedRarityTier()) && getSelectedRarityTier() === 5;
    if ((isStxSimplePearlOverrideChecked() || catPearlTier) && !(state.mainPart && state.mainPart.__fullDeserialized)){
      const b0 = getSelectedBaseItem();
      const bf = Number(b0 && b0.familyId);
      if (Number.isFinite(bf)){
        const isW = cat === 'Weapon' || (state && stxSimpleBuilderItemTypeIsHeavyUi(state.itemType));
        const pr = cat === 'Class Mod'
          ? stxPickClassModPearlOverrideBraceToken(bf)
          : stxPickPearlOverrideBraceToken(bf, isW);
        const barePearl = /^\\{\\s*(?:5[1-9]|60)\\s*\\}$/.test(String(pr || '').replace(/\\s+/g, ''));
        const rarityAlreadyPearl = tokens.some((t) => {
          const id = String(t || '').replace(/\\s+/g, '').match(/^\\{\\s*(?:\\d+\\s*:\\s*)?(5[1-9]|60)\\s*\\}$/);
          return !!id;
        });
        if (pr && !(cat === 'Class Mod' && barePearl && rarityAlreadyPearl)){
          const pn = cat === 'Class Mod' ? pr : stxPearlOverrideNormalized(pr, bf);
          const first = tokens.length ? tokens[0] : '';
          if (!first || !stxPearlTokensDuplicateForOverride(first, pn, bf)) tokens.unshift(pn);
        }
      }
    }`,
  "computeOutputTokens-pearl"
);

fs.writeFileSync(corePath, s, "utf8");
console.log("SQBT editor overlays applied →", corePath);
if (process.exitCode) process.exit(process.exitCode);
