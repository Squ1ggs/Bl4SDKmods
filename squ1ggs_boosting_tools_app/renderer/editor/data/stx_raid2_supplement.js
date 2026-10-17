(function(){
  'use strict';
  var add = [
  {
    "source": "nexus_inv_deps_verified",
    "effects": "Active Fire",
    "raid2Key": "firmware_active_fire_Enhancement",
    "category": "Enhancement",
    "manufacturer": "gadgets",
    "itemType": "Enhancement",
    "weaponType": "",
    "partType": "Firmware",
    "code": "\"enhancement.part_firmware_active_fire\"",
    "name": "Active Fire",
    "searchAlias": "Active Fire firmware",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Raid 2 overlay row; numeric IDs are verified, exact stat roll tables depend on future Nexus parser coverage."
  },
  {
    "source": "nexus_coverage_alias",
    "effects": "Radiation Nova",
    "raid2Key": "nexus_alias_repair_kit_part_aug_ele_nova_radiation",
    "category": "Repkit",
    "manufacturer": "",
    "itemType": "Repkit",
    "weaponType": "",
    "partType": "",
    "code": "\"repair_kit.part_aug_ele_nova_radiation\"",
    "name": "Radiation Nova",
    "searchAlias": "Radiation Nova",
    "dataNote": "Alias row for Nexus spawn repair_kit.part_aug_ele_nova_radiation (editor previously used repair_kit.part_aug_ele_nova_radiaion).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_alias",
    "effects": "Hopscotch",
    "raid2Key": "nexus_alias_ted_shield_part_body_hopscotch",
    "category": "Shield",
    "manufacturer": "Tediore",
    "itemType": "Shield",
    "weaponType": "",
    "partType": "Body",
    "code": "\"ted_shield.part_body_hopscotch\"",
    "name": "Hopscotch",
    "searchAlias": "Hopscotch",
    "dataNote": "Alias row for Nexus spawn ted_shield.part_body_hopscotch (editor previously used ted_shield.comp_05_legendary_hopscotch).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_alias",
    "effects": "Camera Drone Comp",
    "raid2Key": "nexus_alias_weapon_orderdrone_comp_camera",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "Rarity",
    "code": "\"weapon_orderdrone.comp_camera\"",
    "name": "Camera Drone Comp",
    "searchAlias": "Camera Drone Comp",
    "dataNote": "Alias row for Nexus spawn weapon_orderdrone.comp_camera (editor previously used weapon_orderdrone.part_body_camera).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_alias",
    "effects": "Legendary",
    "raid2Key": "nexus_alias_bor_hw_comp_05_legendary",
    "category": "Heavy Weapon",
    "manufacturer": "Ripper",
    "itemType": "Heavy Weapon",
    "weaponType": "Heavy Weapon",
    "partType": "Rarity",
    "code": "\"bor_hw.comp_05_legendary\"",
    "name": "Legendary",
    "idRaw": "275:30",
    "id": 30,
    "family": 275,
    "searchAlias": "Legendary",
    "dataNote": "Alias row for Nexus spawn bor_hw.comp_05_legendary (editor previously used bor_hw.comp_04_epic).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_alias",
    "effects": "Normal Element",
    "raid2Key": "nexus_alias_grenade_gadget_part_normal",
    "category": "Gadget",
    "manufacturer": "",
    "itemType": "Gadget",
    "weaponType": "",
    "partType": "",
    "code": "\"grenade_gadget.part_normal\"",
    "name": "Normal Element",
    "idRaw": "21",
    "id": 21,
    "searchAlias": "Normal Element",
    "dataNote": "Alias row for Nexus spawn grenade_gadget.part_normal (editor previously used grenade_gadget.part_radiation).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_auto",
    "effects": "Comp Badass",
    "raid2Key": "nexus_gap_weapon_orderdrone_comp_badass",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "Rarity",
    "code": "\"weapon_orderdrone.comp_badass\"",
    "name": "Comp Badass",
    "searchAlias": "Comp Badass",
    "dataNote": "Auto-filled from Nexus inv deps for coverage (no serialindex in export).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_auto",
    "effects": "Comp Default",
    "raid2Key": "nexus_gap_weapon_orderdrone_comp_default",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "Rarity",
    "code": "\"weapon_orderdrone.comp_default\"",
    "name": "Comp Default",
    "searchAlias": "Comp Default",
    "dataNote": "Auto-filled from Nexus inv deps for coverage (no serialindex in export).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_auto",
    "effects": "Comp Wideangle",
    "raid2Key": "nexus_gap_weapon_orderdrone_comp_wideangle",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "Rarity",
    "code": "\"weapon_orderdrone.comp_wideangle\"",
    "name": "Comp Wideangle",
    "searchAlias": "Comp Wideangle",
    "dataNote": "Auto-filled from Nexus inv deps for coverage (no serialindex in export).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_auto",
    "effects": "Comp Zanedrone",
    "raid2Key": "nexus_gap_weapon_orderdrone_comp_zanedrone",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "Rarity",
    "code": "\"weapon_orderdrone.comp_zanedrone\"",
    "name": "Comp Zanedrone",
    "searchAlias": "Comp Zanedrone",
    "dataNote": "Auto-filled from Nexus inv deps for coverage (no serialindex in export).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_auto",
    "effects": "Part Body",
    "raid2Key": "nexus_gap_weapon_orderdrone_part_body",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "",
    "code": "\"weapon_orderdrone.part_body\"",
    "name": "Part Body",
    "searchAlias": "Part Body",
    "dataNote": "Auto-filled from Nexus inv deps for coverage (no serialindex in export).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_auto",
    "effects": "Part Body Badass",
    "raid2Key": "nexus_gap_weapon_orderdrone_part_body_badass",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "",
    "code": "\"weapon_orderdrone.part_body_badass\"",
    "name": "Part Body Badass",
    "searchAlias": "Part Body Badass",
    "dataNote": "Auto-filled from Nexus inv deps for coverage (no serialindex in export).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_auto",
    "effects": "Part Body Camera",
    "raid2Key": "nexus_gap_weapon_orderdrone_part_body_camera",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "",
    "code": "\"weapon_orderdrone.part_body_camera\"",
    "name": "Part Body Camera",
    "searchAlias": "Part Body Camera",
    "dataNote": "Auto-filled from Nexus inv deps for coverage (no serialindex in export).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_auto",
    "effects": "Part Body Wideangle",
    "raid2Key": "nexus_gap_weapon_orderdrone_part_body_wideangle",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "",
    "code": "\"weapon_orderdrone.part_body_wideangle\"",
    "name": "Part Body Wideangle",
    "searchAlias": "Part Body Wideangle",
    "dataNote": "Auto-filled from Nexus inv deps for coverage (no serialindex in export).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_auto",
    "effects": "Comp Turret Chaingun",
    "raid2Key": "nexus_gap_weapon_turret_chaingun_comp_turret_chaingun",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "Rarity",
    "code": "\"weapon_turret_chaingun.comp_turret_chaingun\"",
    "name": "Comp Turret Chaingun",
    "searchAlias": "Comp Turret Chaingun",
    "dataNote": "Auto-filled from Nexus inv deps for coverage (no serialindex in export).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  },
  {
    "source": "nexus_coverage_auto",
    "effects": "Part Body",
    "raid2Key": "nexus_gap_weapon_turret_chaingun_part_body",
    "category": "Weapon",
    "manufacturer": "",
    "itemType": "Weapon",
    "weaponType": "",
    "partType": "",
    "code": "\"weapon_turret_chaingun.part_body\"",
    "name": "Part Body",
    "searchAlias": "Part Body",
    "dataNote": "Auto-filled from Nexus inv deps for coverage (no serialindex in export).",
    "stats": "",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards."
  }
];
  var patches = [
  {
    "matchCode": "\"ted_ps.comp_05_legendary_shammy\"",
    "raid2Key": "np_shammy",
    "idRaw": "5:89",
    "name": "Shammy Kablammy",
    "effects": "Raid Boss 2 unique effect: Douses enemies in hot Moonshine, then throws an explosive projectile when reloading that burns doused enemies with Incendiary damage, scaling with how many targets you lit ablaze.",
    "searchAlias": "Shammy Kablammy",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "matchCode": "\"tor_ar.comp_05_legendary_lockjaw\"",
    "raid2Key": "np_lockjaw",
    "idRaw": "17:85",
    "name": "Lockjaw",
    "effects": "Raid Boss 2 unique effect: Fires explosive projectiles that bounce between multiple targets.",
    "searchAlias": "Lockjaw",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "matchCode": "\"bor_sm.comp_05_legendary_jailbroken\"",
    "raid2Key": "np_jailbroken",
    "idRaw": "19:61",
    "name": "Jail-Broken Gatling",
    "effects": "Pearlescent Raid Boss 2 effect: For each hit on an enemy, gain a buff that increases fire rate, damage, weapon recoil, and the chance to fire additional projectiles.",
    "searchAlias": "Jail-Broken Gatling Jailbroken",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "matchCode": "\"vla_hw.comp_05_legendary_flak\"",
    "raid2Key": "np_flak",
    "idRaw": "282:31",
    "name": "Flak Cannon",
    "effects": "Raid Boss 2 unique effect: Shreds enemies with a hail of bullets.",
    "searchAlias": "Flak Cannon",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "matchCode": "\"ord_shield.comp_05_legendary_collector\"",
    "raid2Key": "np_collector",
    "idRaw": "293:12",
    "name": "Collector",
    "effects": "Raid Boss 2 unique effect: High-capacity Energy Shield with quick recharge rate, offset by a longer recharge delay.",
    "searchAlias": "Collector shield",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "matchCode": "\"classmod_dark_siren.leg_body_raid2\"",
    "raid2Key": "np_cm_ds_leg_raid2",
    "idRaw": "254:543",
    "name": "Grim Sister",
    "effects": "Raid Boss 2 unique Dark Siren class mod. Exact stat-roll table is not present in the current parsed Nexus export.",
    "searchAlias": "Grim Sister Raid 2 Dark Siren class mod",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "matchCode": "\"classmod_exo_soldier.leg_body_raid2\"",
    "raid2Key": "np_cm_exo_leg_raid2",
    "idRaw": "256:544",
    "name": "Bombastic",
    "effects": "Raid Boss 2 unique Exo Soldier class mod. Exact stat-roll table is not present in the current parsed Nexus export.",
    "searchAlias": "Bombastic Raid 2 Exo Soldier class mod",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "matchCode": "\"classmod_gravitar.leg_body_raid2\"",
    "raid2Key": "np_cm_grav_leg_raid2",
    "idRaw": "259:546",
    "name": "Plasmaphile",
    "effects": "Raid Boss 2 unique Gravitar class mod. Exact stat-roll table is not present in the current parsed Nexus export.",
    "searchAlias": "Plasmaphile Raid 2 Gravitar class mod",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "matchCode": "\"classmod_paladin.leg_body_raid2\"",
    "raid2Key": "np_cm_pld_leg_raid2",
    "idRaw": "255:544",
    "name": "Artificer",
    "effects": "Raid Boss 2 unique Paladin class mod. Exact stat-roll table is not present in the current parsed Nexus export.",
    "searchAlias": "Artificer Raid 2 Paladin class mod",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "matchCode": "\"classmod_robodealer.leg_body_raid2\"",
    "raid2Key": "np_cm_robo_leg_raid2",
    "idRaw": "404:543",
    "name": "Prestidigitator",
    "effects": "Raid Boss 2 unique Robodealer class mod. Exact stat-roll table is not present in the current parsed Nexus export.",
    "searchAlias": "Prestidigitator Raid 2 Robodealer class mod",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "matchCode": "\"grenade_gadget.part_firmware_active_fire\"",
    "raid2Key": "firmware_active_fire_grenade_gadget",
    "idRaw": "245:249",
    "name": "Active Fire",
    "effects": "Active Fire firmware: At Tier 3, unleashing a charge weapon's full-charge shot the moment it is available deals bonus damage.",
    "searchAlias": "Active Fire firmware",
    "dropHint": "Drops from Raid Boss 2: Subjugator and Thol the Invincible. Class mods require Silver-tier-or-better UVHM Raid Boss 2 rewards.",
    "dataNote": "Verified Raid 2 reference row — patches idRaw/display when gap catalog row lacks serialindex."
  },
  {
    "raid2Key": "np_screwed_pearl",
    "matchCode": "dad_sm.comp_06_pearl_screwed",
    "name": "Screwstonian",
    "legendaryName": "Screwstonian",
    "effects": "Screwstonian",
    "searchAlias": "Screwstonian Pearl Screwed",
    "itemTypeString": "DAD_SM.comp_06_pearl_screwed",
    "partType": "Rarity",
    "dropHint": "Community-discovered pearlescent (Raid 2).",
    "dataNote": "Pearlescent comp_06_pearl_screwed — idRaw 20:72 from Nexus supplement."
  }
];
  var insertIfMissing = [
  {
    "raid2Key": "np_screwed_pearl",
    "category": "Weapon",
    "manufacturer": "Daedalus",
    "itemType": "SMG",
    "weaponType": "SMG",
    "partType": "Rarity",
    "code": "\"DAD_SM.comp_06_pearl_screwed\"",
    "idRaw": "20:72",
    "id": 72,
    "family": 20,
    "name": "Screwstonian",
    "effects": "Screwstonian",
    "searchAlias": "Screwstonian",
    "source": "verified_pearl_reference"
  },
  {
    "raid2Key": "firmware_active_fire_grenade_gadget",
    "category": "Grenade",
    "manufacturer": "gadgets",
    "itemType": "Grenade",
    "weaponType": "",
    "partType": "Firmware",
    "code": "\"grenade_gadget.part_firmware_active_fire\"",
    "idRaw": "245:249",
    "name": "Active Fire",
    "searchAlias": "Active Fire firmware",
    "source": "verified_raid2_firmware",
    "effects": "Active Fire"
  }
];
  var tries = 0;
  function normCode(c){
    return String(c||'').replace(/^\\"|\\"$/g,'').replace(/^"|"$/g,'').trim().toLowerCase();
  }
  function applyPatch(p, patch){
    if (patch.raid2Key) p.raid2Key = patch.raid2Key;
    if (patch.name) p.name = patch.name;
    if (patch.legendaryName) p.legendaryName = patch.legendaryName;
    if (patch.effects) p.effects = patch.effects;
    if (patch.searchAlias) p.searchAlias = patch.searchAlias;
    if (patch.itemTypeString) p.itemTypeString = patch.itemTypeString;
    if (patch.partType) p.partType = patch.partType;
    if (patch.dropHint) p.dropHint = patch.dropHint;
    if (patch.dataNote) p.dataNote = patch.dataNote;
    if (patch.idRaw) p.idRaw = patch.idRaw;
    if (patch.id != null) p.id = patch.id;
    if (patch.family != null) p.family = patch.family;
    if (patch.stats) p.stats = patch.stats;
  }
  function merge(){ try{
    var ds = (window.STX_DATASET && Array.isArray(window.STX_DATASET.ALL_PARTS)) ? window.STX_DATASET.ALL_PARTS : null;
    if (!ds) { if (++tries < 80) setTimeout(merge, 25); return; }
    var haveCode = new Set();
    var haveRaid2Key = new Set();
    for (var i=0;i<ds.length;i++){
      var p = ds[i]; var c = normCode(p && p.code);
      if (c) haveCode.add(c);
      if (p && p.raid2Key) haveRaid2Key.add(String(p.raid2Key).toLowerCase());
    }
    var addedCount = 0;
    var patchedCount = 0;
    for (var j=0;j<add.length;j++){
      var r = add[j];
      var r2 = r && r.raid2Key ? String(r.raid2Key).toLowerCase() : '';
      if (r2 && haveRaid2Key.has(r2)) continue;
      var rc = normCode(r && r.code);
      if (!r2 && rc && haveCode.has(rc)) continue;
      ds.push(r); addedCount++; haveCode.add(rc); if (r2) haveRaid2Key.add(r2);
    }
    for (var ins=0; ins<insertIfMissing.length; ins++){
      var row = insertIfMissing[ins];
      var rc2 = normCode(row && row.code);
      var r2b = row && row.raid2Key ? String(row.raid2Key).toLowerCase() : '';
      if (!rc2) continue;
      if (haveCode.has(rc2) || (r2b && haveRaid2Key.has(r2b))) continue;
      ds.push(row); addedCount++; haveCode.add(rc2); if (r2b) haveRaid2Key.add(r2b);
    }
    for (var pi=0; pi<patches.length; pi++){
      var patch = patches[pi];
      var want = normCode(patch && patch.matchCode);
      if (!want) continue;
      for (var k=0;k<ds.length;k++){
        if (normCode(ds[k] && ds[k].code) !== want) continue;
        applyPatch(ds[k], patch);
        patchedCount++;
        break;
      }
    }
    if (addedCount || patchedCount){
      try{ window.GUN_PARTS = window.GRENADE_PARTS = window.SHIELD_PARTS = window.REPKIT_PARTS = window.ENHANCEMENT_PARTS = window.HEAVY_PARTS = window.CLASSMOD_PARTS = undefined; }catch(_e){}
      try{ if (typeof window.ensurePartPools === 'function') window.ensurePartPools(); }catch(_e){}
      try{ window.__ccStablePartRenderStateV1 = null; }catch(_e){}
      try{ if (typeof window.refreshPartSections === 'function') window.refreshPartSections(); }catch(_e){}
    }
  }catch(_e){} }
  merge();
})();
