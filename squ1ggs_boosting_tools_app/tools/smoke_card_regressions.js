"use strict";

const path = require("node:path");
const fs = require("node:fs");

global.window = global;
global.addEventListener = () => {};

require("../native_item_card");

const { evaluateNexusCardStats } = require("../lib/nexus_card_stats");
const { loadStatData } = require("../lib/nexus/serial_card_stats");
const { inlineSqbtAssetUrls } = require("../native_card_protocol");

function assert(condition, message) {
  if (!condition) throw new Error(message);
  console.log(`[smoke:card-regressions] OK: ${message}`);
}

const legitItemsPath = path.join(__dirname, "..", "resources", "LegitItems");
const data = loadStatData({ legitItemsPath });

function partKeys(set, pattern, limit) {
  const parts = data.invRoots.get(set)?.parts;
  if (!parts) return [];
  return [...parts.keys()].filter((key) => pattern.test(key)).slice(0, limit);
}

function refs(set, keys) {
  return keys.map((key) => `${set}.${key}`);
}

// Heavy C4SH: this exercises Cowbell tooltip-name lookup, named local glyph
// fallback, the six-icon render cap, and skill-first classmod assembly.
const classmodSet = "classmod_corpohacker";
const classmodParts = [
  ...refs(classmodSet, partKeys(classmodSet, /^body_/, 1)),
  ...refs(classmodSet, partKeys(classmodSet, /passive_/i, 80)),
  ...refs(classmodSet, partKeys(classmodSet, /part_(?:unv|sec|stat)|firmware/i, 20)),
];
const classmod = evaluateNexusCardStats({
  itemType: "Class Mod",
  type_label: "Class Mod",
  set: classmodSet,
  part_names: classmodParts,
  level: 70,
});
const classmodEquipment = inlineSqbtAssetUrls(classmod.native_equipment);
const classmodEntry = global.SQBTNativeItemCard.propsToEntry({
  display_name: "C4SH Class Mod",
  itemType: "Classmod",
  type_label: "Class Mod",
  part_names: classmodParts,
  native_equipment: classmodEquipment,
  raw: classmod.raw,
  level: 70,
});
const skillRows = classmodEntry.native_equipment?.groups?.primary || [];
const secondaryRows = classmodEntry.native_equipment?.groups?.secondary || [];
assert(classmod.raw?.item_type === "Classmod", "heavy classmod remains Classmod");
assert(skillRows.length > 6, "heavy classmod paints all skill glyphs (no icon cap)");
assert(
  skillRows.every((row) => /^(?:data:|coui:|common:)/i.test(String(row.image || ""))),
  "heavy classmod skill glyphs resolve to packaged assets"
);
assert(
  skillRows.every((row) => !/^(?:trunk|branch)\s*-/i.test(String(row.name || ""))),
  "C4SH skill glyphs use character perk names"
);
const skillTextSpill = secondaryRows.filter((row) => {
  const plain = String(row?.value || "")
    .replace(/\[[^\]]+\]/g, "")
    .trim();
  // Named character skills — not Nexus +N% / +N flat stat lines.
  return plain && !/^[+\-−]?\d/.test(plain);
});
assert(
  skillTextSpill.length >= 6,
  "heavy classmod lists character perks under the glyph row above other parts"
);
assert(
  (classmod.native_equipment?.groups?.primary || []).length > 6,
  "heavy classmod Nexus payload has more than six skills"
);
assert(skillRows.length > 6, "painted classmod glyphs stay uncapped for real character perks");

// Legendary unique shields must keep Shield_Rarity_Init from the base comp and
// resolve Capacity/Amp augment values (InventoryAugmentAttributeValueResolver).
const cindershelly = evaluateNexusCardStats({
  itemType: "Shield",
  type_label: "Energy Shield",
  set: "ord_shield",
  part_names: [
    "ord_shield.comp_05_legendary_cindershelly",
    "ord_shield.part_body_energy",
    "ord_shield.part_unique_cindershelly",
    "shield.part_unv_capacity_secondary",
    "energy_shield.part_eng_amp_primary",
    "shield.part_firmware_trickshot",
  ],
  level: 70,
});
const cinderPrimary = cindershelly.native_equipment?.groups?.primary || [];
const cinderSecondary = cindershelly.native_equipment?.groups?.secondary || [];
const cinderCap = Number(
  String(cinderPrimary[0]?.value || "").replace(/,/g, "").replace(/[^\d.]/g, "")
);
const cinderRate = Number(
  String(cinderPrimary[1]?.value || "").replace(/,/g, "").replace(/[^\d.]/g, "")
);
assert(
  cinderCap > 120000 && cinderCap < 128000,
  "Cindershelly Capacity tracks in-game (~124k), not bare ~70k"
);
assert(
  cinderRate > 9800 && cinderRate < 10100,
  "Cindershelly recharge tracks in-game (~9939/s)"
);
assert(
  cinderSecondary.some((row) => /\+25%\s*Shield Capacity/i.test(String(row.value || ""))),
  "Cindershelly Capacity augment paints +25%"
);
assert(
  cinderSecondary.some((row) => /\+100%\s*Gun Damage/i.test(String(row.value || ""))),
  "Cindershelly Amp augment paints +100% Gun Damage"
);
assert(
  cinderSecondary.some((row) => /drain[\s\S]*28%/i.test(String(row.value || ""))),
  "Cindershelly Amp drain paints whole percent (28%)"
);

// FirmwareAspect must inject Firmware UI rows (widget + group) from Nexus.
const shieldFw = evaluateNexusCardStats({
  itemType: "Shield",
  type_label: "Shield",
  set: "shield",
  part_names: ["shield.comp_05_legendary", "shield.part_firmware_jacked"],
  level: 70,
});
assert(
  String(shieldFw.firmware_block?.firmwareident || "") === "fw_jacked",
  "shield with Jacked firmware paints firmware_block.fw_jacked"
);
assert(
  Array.isArray(shieldFw.native_equipment?.groups?.firmware) &&
    shieldFw.native_equipment.groups.firmware.length > 0,
  "shield firmware group is present on native_equipment"
);
assert(
  Array.isArray(shieldFw.native_firmware) && shieldFw.native_firmware.length > 0,
  "shield native_firmware rows come from FirmwareAspect UI inject"
);

const ordnanceFw = evaluateNexusCardStats({
  itemType: "Ordnance",
  type_label: "Ordnance",
  set: "grenade_gadget",
  part_names: ["grenade_gadget.comp_05_legendary", "grenade_gadget.part_firmware_airstrike"],
  level: 70,
});
assert(
  String(ordnanceFw.firmware_block?.firmwareident || "") === "fw_airstrike",
  "ordnance Airstrike paints firmware widget ident"
);

const enhanceFw = evaluateNexusCardStats({
  itemType: "Enhancement",
  type_label: "Enhancement",
  set: "enhancement",
  part_names: ["enhancement.part_body_01_common", "enhancement.part_firmware_get_throwin"],
  level: 70,
});
assert(
  String(enhanceFw.firmware_block?.firmwareident || "") === "fw_get_throwin",
  "enhancement Get Throwin paints firmware widget ident"
);

// Pearl weapon dual must not retype Editor Enhancement cards as SMG/Shotgun.
const pearlEnhEntry = global.SQBTNativeItemCard.propsToEntry({
  display_name: "Functional Human",
  title: "Functional Human",
  itemType: "SMG",
  type_label: "Enhancement",
  part_names: ["enhancement.part_body_01_common", "enhancement.part_firmware_get_throwin"],
  raw: { item_type: "SMG", display_name: "Juliet" },
});
assert(pearlEnhEntry.item_type === "Enhancement", "pearl SMG leak keeps Enhancement type");
assert(
  !/juliet|smg|submachine/i.test(String(pearlEnhEntry.display_name || "")),
  "pearl SMG name does not overwrite Enhancement title"
);
assert(
  /enhancement/i.test(String(pearlEnhEntry.type_label || "")),
  "pearl SMG leak keeps Enhancement type_label"
);

// Pearl rarity ids must paint pearl chrome — not fall through to grey common.
const { toNativeCardModel } = require("../native_card_model");
for (const [label, note] of [
  ["Pearlescent", "title case Pearlescent"],
  ["06_pearlescent", "Nexus 06_pearlescent id"],
  ["pearl", "lowercase pearl"],
  ["6", "numeric pearl tier"],
]) {
  const model = toNativeCardModel({
    display_name: "Looming Constable",
    rarity: label,
    manufacturer: "Jakobs",
    item_type: "Shotgun",
    level: 70,
  });
  assert(model.rarityident === "pearl", `${note} must map to pearl rarityident`);
}
assert(
  toNativeCardModel({
    display_name: "Looming Constable",
    rarity: "",
    part_names: ["JAK_SG.comp_06_pearl_Constable"],
    manufacturer: "Jakobs",
    item_type: "Shotgun",
    level: 70,
  }).rarityident === "pearl",
  "comp_06_pearl parts must force pearl chrome when rarity label is blank"
);

// DLC firmware CSS classes must exist (Skillcraft / Active Fire).
const firmwareCss = fs.readFileSync(
  path.join(__dirname, "..", "native_card_ui", "uiresources", "components", "firmware", "css", "firmware.css"),
  "utf8"
);
assert(/\.icon_bkg\.fw_raid1_skillcraft\b/.test(firmwareCss), "firmware.css includes Skillcraft icon");
assert(/\.icon_bkg\.fw_raid2_activefire\b/.test(firmwareCss), "firmware.css includes Active Fire icon");
const skillcraftBig = path.join(
  __dirname,
  "..",
  "native_card_ui",
  "uiresources",
  "_shared",
  "assets",
  "ico_ui_art_firmwares",
  "item_card_size",
  "ico_firmware_skillcraft_big.png"
);
assert(fs.existsSync(skillcraftBig), "Skillcraft big firmware PNG is packaged");

// Modded guns can contain foreign shield/gadget parts. The serial-header weapon
// type must win so renderer fallback Damage remains enabled.
const gunSet =
  [...data.invRoots.keys()].find(
    (set) =>
      /_ps$/i.test(set) &&
      partKeys(set, /barrel/i, 1).length &&
      partKeys(set, /body/i, 1).length
  ) || "";
const foreignSet =
  [...data.invRoots.keys()].find(
    (set) => /shield/i.test(set) && data.invRoots.get(set)?.parts?.size
  ) || "";
assert(Boolean(gunSet && foreignSet), "Nexus test data contains gun and foreign equipment sets");
const gunParts = [
  ...refs(gunSet, partKeys(gunSet, /body/i, 1)),
  ...refs(gunSet, partKeys(gunSet, /barrel/i, 1)),
  ...refs(gunSet, partKeys(gunSet, /mag/i, 1)),
  ...refs(foreignSet, partKeys(foreignSet, /.*/, 2)),
];
const moddedGun = evaluateNexusCardStats({
  itemType: "Pistol",
  type_label: "Pistol",
  set: gunSet,
  part_names: gunParts,
  level: 70,
});
assert(moddedGun.raw?.item_type === "Pistol", "foreign equipment parts do not retype a gun");

// Offline classmod titles: legendary body wins over firmware (Get Throwin).
const { spawnSync } = require("node:child_process");
const steamLabels = path.join(
  "C:",
  "Program Files (x86)",
  "Steam",
  "steamapps",
  "common",
  "Borderlands 4",
  "sdk_mods",
  "Squ1ggsBoostingTools"
);
const labelScript = [
  "import importlib.util, json, sys, types",
  "root = sys.argv[1]",
  "serial = sys.argv[2]",
  "pkg = types.ModuleType('Squ1ggsBoostingTools')",
  "pkg.__path__ = [root]",
  "sys.modules['Squ1ggsBoostingTools'] = pkg",
  "",
  "def load(name):",
  "    spec = importlib.util.spec_from_file_location(",
  "        'Squ1ggsBoostingTools.' + name,",
  "        root + '/' + name + '.py',",
  "        submodule_search_locations=[root],",
  "    )",
  "    mod = importlib.util.module_from_spec(spec)",
  "    sys.modules[spec.name] = mod",
  "    spec.loader.exec_module(mod)",
  "    return mod",
  "",
  "load('serial_converter')",
  "il = load('item_labels')",
  "print(json.dumps(il.meta_from_serial(serial)))",
].join("\n");
try {
  const savedPath = path.join(
    process.env.USERPROFILE || "",
    "Documents",
    "My Games",
    "Borderlands 4",
    "Saved",
    "Squ1ggsBoostingTools_saved_serials.json"
  );
  let probeSerial = "";
  if (fs.existsSync(savedPath)) {
    const saved = JSON.parse(fs.readFileSync(savedPath, "utf8"));
    const entries = saved.entries
      ? Array.isArray(saved.entries)
        ? saved.entries
        : Object.values(saved.entries)
      : [];
    const set1 = entries.find((row) => String(row?.name || "") === "set1");
    if (set1?.serial) probeSerial = String(set1.serial);
  }
  if (!probeSerial) {
    console.log("[smoke:card-regressions] skip set1 name check (no saved set1 serial)");
  } else {
    const labeled = spawnSync("python", ["-c", labelScript, steamLabels, probeSerial], {
      encoding: "utf8",
      windowsHide: true,
      timeout: 12000,
    });
    assert(labeled.status === 0, "set1 offline label decode runs");
    const meta = JSON.parse(String(labeled.stdout || "").trim() || "{}");
    assert(
      String(meta.display_name || "") === "Functional Human",
      "set1 / Hacker legendary titles Functional Human (not firmware Get Throwin)"
    );
    assert(
      !/firewerk/i.test(String(meta.display_name || "")),
      "set1 is not titled Firewerks"
    );
  }
} catch (error) {
  throw error;
}

// Gun bag-flood regression: legendary comps must survive truncation (not firmware titles).
try {
  const savedPath2 = path.join(
    process.env.USERPROFILE || "",
    "Documents",
    "My Games",
    "Borderlands 4",
    "Saved",
    "Squ1ggsBoostingTools_saved_serials.json"
  );
  if (fs.existsSync(savedPath2)) {
    const saved2 = JSON.parse(fs.readFileSync(savedPath2, "utf8"));
    const entries2 = saved2.entries
      ? Array.isArray(saved2.entries)
        ? saved2.entries
        : Object.values(saved2.entries)
      : [];
    const gun = entries2.find((row) => String(row?.name || "") === "Thugs moddes 500 #327");
    const cm = entries2.find(
      (row) =>
        String(row?.name || "").includes("Firewerks") &&
        /classmod/i.test(String(row?.name || ""))
    );
    if (gun?.serial) {
      const labeled = spawnSync("python", ["-c", labelScript, steamLabels, gun.serial], {
        encoding: "utf8",
        windowsHide: true,
        timeout: 12000,
      });
      assert(labeled.status === 0, "gun offline label decode runs");
      const meta = JSON.parse(String(labeled.stdout || "").trim() || "{}");
      assert(
        !/goojfc|get\s*throwin|action\s*fist/i.test(String(meta.display_name || "")),
        "modded AR is not titled from firmware"
      );
      assert(
        /soul\s*survivor/i.test(String(meta.display_name || meta.unique_name || "")),
        "modded AR keeps legendary Soulsurvivor title"
      );
    }
    if (cm?.serial) {
      const labeled = spawnSync("python", ["-c", labelScript, steamLabels, cm.serial], {
        encoding: "utf8",
        windowsHide: true,
        timeout: 12000,
      });
      if (labeled.status === 0) {
        const meta = JSON.parse(String(labeled.stdout || "").trim() || "{}");
        assert(
          !/firewerk/i.test(String(meta.display_name || "")),
          "classmod is not titled Firewerks from foreign pearl hook"
        );
      }
    }
  }
} catch (error) {
  throw error;
}

console.log("[smoke:card-regressions] all card regression checks passed");
