"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { analyzeItem } = require("../lib/item_analysis");
const { decodeBase85, decodeSerialCard, encodeBase85 } = require("../lib/serial_codec");
const {
  extractSerialStrings,
  extractVisibleAttributes,
  identifyImageFile,
  inspectImageBuffer,
  rankCandidates,
} = require("../lib/image_item_match");

const SERIAL = "@Ugxp/&35E/M%(VsDhbmN}7L^ZG6ZI0+64j/Xs9UIVsDXx$%mD";
const TRUCK_SERIAL = "@Ugy3L+35E/MOymv9i7M2g8g&yj4^<C!5A~@ss5_`qs8gs~sBoy32m";

async function main() {
  const analysis = await analyzeItem(SERIAL);
  assert.equal(analysis.ok, true);
  assert.equal(analysis.exact, true);
  assert.equal(analysis.serial, SERIAL);
  assert.equal(analysis.identity.round_trip_exact, true);
  assert.match(analysis.identity.payload_sha256, /^[0-9a-f]{64}$/);
  assert.ok(Array.isArray(analysis.part_names) && analysis.part_names.length > 0);
  const truck = await analyzeItem(TRUCK_SERIAL);
  assert.ok(
    truck.perk_rows.some((row) => /Daedalus Multi-Loader.*Shotgun Ammo/i.test(row.name)),
    JSON.stringify(truck.perk_rows)
  );

  const payload = decodeBase85(SERIAL);
  assert.equal(encodeBase85(payload), SERIAL);
  const deterministic = decodeSerialCard(
    SERIAL,
    path.join(__dirname, "..", "resources", "Squ1ggsBoostingTools")
  );
  assert.equal(deterministic.identity.readable, true);
  assert.equal(deterministic.identity.round_trip_exact, true);
  assert.equal(deterministic.level, 60);
  assert.ok(deterministic.part_names.length > 0);

  const noPythonProbe = spawnSync(
    process.execPath,
    [
      "-e",
      "require('./lib/item_analysis').analyzeItem(process.argv[1]).then(x=>{console.log(JSON.stringify(x));process.exit(x.ok&&x.identity?.round_trip_exact?0:2)}).catch(()=>process.exit(3))",
      SERIAL,
    ],
    {
      cwd: path.join(__dirname, ".."),
      encoding: "utf8",
      env: { ...process.env, SQBT_DISABLE_PYTHON_SERIAL: "1" },
      windowsHide: true,
    }
  );
  assert.equal(noPythonProbe.status, 0, noPythonProbe.stderr || noPythonProbe.stdout);

  assert.deepEqual(extractSerialStrings(`code:\n${SERIAL}\n`), [SERIAL]);
  const extracted = extractVisibleAttributes(
    "HELLWALKER\nJAKOBS LEGENDARY SHOTGUN\nLEVEL 60\nDAMAGE 1200"
  );
  const rows = [
    {
      name: "Hellwalker",
      manufacturer: "Jakobs",
      category: "Shotguns",
      rarity: "Legendary",
      level: 60,
      serial: SERIAL,
    },
    {
      name: "Other Gun",
      manufacturer: "Maliwan",
      category: "Pistols",
      rarity: "Rare",
      level: 20,
    },
  ];
  const ranked = rankCandidates(extracted, rows);
  assert.equal(ranked[0].name, "Hellwalker");
  assert.equal(ranked[0].exact, false);
  assert.ok(ranked[0].score >= 100);

  const ambiguous = rankCandidates(
    extractVisibleAttributes("LEGENDARY WEAPON"),
    [
      { name: "One", rarity: "Legendary" },
      { name: "Two", rarity: "Legendary" },
    ]
  );
  assert.deepEqual(ambiguous, []);
  assert.deepEqual(rankCandidates(extractVisibleAttributes("nothing useful"), rows), []);

  const customCard = extractVisibleAttributes(
    [
      "Sudden Looming Truck",
      "Lvl 70 Sniper Rifle",
      "Fixer-Upper",
      "Torgue-Licensed Impact Magazine - Fires gyrojet projectiles",
      "Daedalus-Licensed Multi-Loader - Secondary fire consumes Shotgun Ammo",
      "Jakobs - Critical Hits will Ricochet Projectiles",
      "JAKOBS",
    ].join("\n")
  );
  assert.equal(customCard.manufacturer, "Jakobs");
  assert.equal(customCard.item_type, "Sniper Rifle");
  assert.ok(customCard.perks.length >= 3);
  const customRanked = rankCandidates(customCard, [
    {
      name: "Fixer-Upper",
      manufacturer: "Jakobs",
      item_type: "Sniper Rifle",
      perks: [
        "Torgue-Licensed Impact Magazine",
        "Daedalus-Licensed Multi-Loader",
        "Jakobs Ricochet",
      ],
      serial: SERIAL,
    },
    {
      name: "Unrelated Jakobs Sniper",
      manufacturer: "Jakobs",
      item_type: "Sniper Rifle",
      serial: SERIAL,
    },
  ]);
  assert.equal(customRanked[0].name, "Fixer-Upper");
  assert.ok(customRanked[0].visible_matches.detail_words.length >= 2);
  assert.equal(customRanked.some((row) => row.name === "Unrelated Jakobs Sniper"), false);

  const png = Buffer.alloc(24);
  Buffer.from("89504e470d0a1a0a", "hex").copy(png, 0);
  png.writeUInt32BE(16, 16);
  png.writeUInt32BE(16, 20);
  const image = inspectImageBuffer(png, "image/png");
  assert.deepEqual({ width: image.width, height: image.height }, { width: 16, height: 16 });

  const lang = require("@tesseract.js-data/eng");
  assert.equal(typeof require("tesseract.js").createWorker, "function");
  assert.ok(fs.existsSync(`${lang.langPath}/eng.traineddata.gz`));

  const realScreenshot = "C:\\Users\\picto\\Pictures\\Screenshots\\test.png";
  if (fs.existsSync(realScreenshot)) {
    const pictured = await identifyImageFile(realScreenshot);
    assert.equal(pictured.extracted.title_candidates[0], "Sudden Looming Truck");
    assert.equal(pictured.extracted.item_type, "Sniper Rifle");
    assert.equal(pictured.extracted.manufacturer, "Jakobs");
    assert.equal(pictured.extracted.rarity, "Legendary");
    assert.equal(pictured.extracted.rarity_source, "card_color");
    assert.equal(pictured.extracted.level, 70);
    assert.ok(
      pictured.extracted.perks.concat(pictured.extracted.flavor_lines).some((line) => /Fixer-Upper/i.test(line))
    );
    assert.ok(pictured.extracted.perks.some((line) => /Torgue-Licensed Impact/i.test(line)));
    assert.ok(pictured.candidates.some((row) => /Truck/i.test(row.name)));
  }
  console.log("ALL OK");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
