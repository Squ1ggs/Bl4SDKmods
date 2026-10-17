(function(){
  'use strict';
  var patch = [
  {
    "manufacturer": "Tediore",
    "itemType": "Pistol",
    "itemTypeString": "TED_PS.comp_05_legendary_shammy",
    "familyId": 5,
    "itemId": 89,
    "legendaryName": "Shammy Kablammy",
    "source": "Raid 2"
  },
  {
    "manufacturer": "Torgue",
    "itemType": "Assault Rifle",
    "itemTypeString": "TOR_AR.comp_05_legendary_lockjaw",
    "familyId": 17,
    "itemId": 85,
    "legendaryName": "Lockjaw",
    "source": "Raid 2"
  },
  {
    "manufacturer": "Ripper",
    "itemType": "SMG",
    "itemTypeString": "BOR_SM.comp_05_legendary_jailbroken",
    "familyId": 19,
    "itemId": 61,
    "legendaryName": "Jail-Broken Gatling",
    "source": "Raid 2"
  },
  {
    "manufacturer": "Vladof",
    "itemType": "Heavy Weapon",
    "itemTypeString": "VLA_HW.comp_05_legendary_flak",
    "familyId": 282,
    "itemId": 31,
    "legendaryName": "Flak Cannon",
    "source": "Raid 2"
  },
  {
    "manufacturer": "Order",
    "itemType": "Shield",
    "itemTypeString": "ord_shield.comp_05_legendary_collector",
    "familyId": 293,
    "itemId": 12,
    "legendaryName": "Collector",
    "source": "Raid 2"
  }
];
  if (!Array.isArray(window.STX_RARITIES)) window.STX_RARITIES = [];
  var seen = {};
  for (var i = 0; i < window.STX_RARITIES.length; i++) {
    var r = window.STX_RARITIES[i];
    if (r && Number.isFinite(r.familyId) && Number.isFinite(r.itemId)) seen[r.familyId + ':' + r.itemId] = true;
  }
  for (var j = 0; j < patch.length; j++) {
    var p = patch[j];
    var k = p.familyId + ':' + p.itemId;
    if (seen[k]) continue;
    window.STX_RARITIES.push(p);
    seen[k] = true;
  }
})();
