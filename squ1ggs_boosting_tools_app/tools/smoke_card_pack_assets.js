"use strict";
/**
 * Pack gate: refuse to ship an EXE that would paint white-square item cards.
 * Checks package.json extraResources + source trees, and optionally the packed
 * win-unpacked/resources tree (--packed / SQBT_PACK_OUT).
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const pkgPath = path.join(ROOT, "package.json");

const REQUIRED_SOURCE = [
  "native_card_ui/uiresources/item_card/item_card.html",
  "native_card_ui/uiresources/item_card/css/item_card.css",
  "native_card_ui/uiresources/_shared/css/oakgame.css",
  "native_card_ui/uiresources/_shared/css/gbx.css",
  "resources/LegitItems/Nexus-Data-inv.json",
];

const REQUIRED_PACKED = [
  "native_card_ui/uiresources/item_card/item_card.html",
  "native_card_ui/uiresources/item_card/css/item_card.css",
  "native_card_ui/uiresources/_shared/css/oakgame.css",
  "LegitItems/Nexus-Data-inv.json",
];

function fail(msg) {
  console.error(`[smoke:card-assets] FAIL: ${msg}`);
  process.exitCode = 1;
}

function ok(msg) {
  console.log(`[smoke:card-assets] OK: ${msg}`);
}

function mustFile(file, label) {
  if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {
    fail(`${label} missing: ${file}`);
    return false;
  }
  const size = fs.statSync(file).size;
  if (size < 64) {
    fail(`${label} too small (${size}b): ${file}`);
    return false;
  }
  return true;
}

function mustDir(dir, label) {
  if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) {
    fail(`${label} missing dir: ${dir}`);
    return false;
  }
  return true;
}

function parseArgs(argv) {
  let packed = null;
  let sourceOnly = false;
  for (const a of argv) {
    if (a === "--source-only") sourceOnly = true;
    else if (a === "--packed") packed = true;
    else if (a.startsWith("--packed=")) packed = a.slice("--packed=".length).trim();
  }
  if (packed === true || packed === null) {
    const env = String(process.env.SQBT_PACK_OUT || "").trim();
    if (env) packed = env;
  }
  return { packed, sourceOnly };
}

function checkPackageJson() {
  const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  const extras = pkg?.build?.extraResources;
  if (!Array.isArray(extras) || !extras.length) {
    fail("package.json build.extraResources is missing/empty (white-square pack risk)");
    return pkg;
  }
  const blob = JSON.stringify(extras).toLowerCase();
  if (!/"to"\s*:\s*"native_card_ui"/i.test(JSON.stringify(extras)) && !blob.includes("native_card_ui")) {
    fail('package.json extraResources must include native_card_ui → "native_card_ui"');
  } else {
    ok("package.json lists native_card_ui extraResource");
  }
  if (!blob.includes("legititems")) {
    fail('package.json extraResources must include LegitItems → "LegitItems"');
  } else {
    ok("package.json lists LegitItems extraResource");
  }
  return pkg;
}

function checkSource() {
  for (const rel of REQUIRED_SOURCE) {
    mustFile(path.join(ROOT, rel), "source");
  }
  const legit = path.join(ROOT, "resources", "LegitItems");
  if (mustDir(legit, "source")) {
    const nexus = fs.readdirSync(legit).filter((n) => /^Nexus-Data/i.test(n));
    if (nexus.length < 20) {
      fail(`LegitItems looks thin (${nexus.length} Nexus-Data* files; need >= 20)`);
    } else {
      ok(`source LegitItems has ${nexus.length} Nexus-Data* files`);
    }
  }
  const ui = path.join(ROOT, "native_card_ui", "uiresources");
  if (mustDir(ui, "source")) ok("source native_card_ui/uiresources present");
}

function resolvePackedRoot(pkg, packedArg) {
  if (typeof packedArg === "string" && packedArg) {
    const p = path.resolve(packedArg);
    if (fs.existsSync(path.join(p, "resources"))) return p;
    if (path.basename(p).toLowerCase() === "resources") return path.dirname(p);
    if (fs.existsSync(path.join(p, "win-unpacked", "resources"))) {
      return path.join(p, "win-unpacked");
    }
    return p;
  }
  const outRel = pkg?.build?.directories?.output || "../dist_squ1ggs_boosting_tools";
  const outAbs = path.resolve(ROOT, outRel);
  const candidates = [
    path.join(outAbs, "win-unpacked"),
    outAbs,
    path.join(ROOT, "..", "dist_squ1ggs_boosting_tools", "win-unpacked"),
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, "resources", "native_card_ui"))) return c;
  }
  return candidates[0];
}

function checkPacked(pkg, packedArg) {
  const unpacked = resolvePackedRoot(pkg, packedArg);
  const res = path.join(unpacked, "resources");
  if (!mustDir(res, "packed")) {
    fail(
      `packed resources not found under ${unpacked} — pass --packed=PATH or set SQBT_PACK_OUT`
    );
    return;
  }
  for (const rel of REQUIRED_PACKED) {
    mustFile(path.join(res, rel), "packed");
  }
  const legit = path.join(res, "LegitItems");
  if (mustDir(legit, "packed")) {
    const nexus = fs.readdirSync(legit).filter((n) => /^Nexus-Data/i.test(n));
    if (nexus.length < 20) {
      fail(`packed LegitItems thin (${nexus.length} Nexus-Data* files)`);
    } else {
      ok(`packed LegitItems has ${nexus.length} Nexus-Data* files`);
    }
  }
  ok(`packed card assets OK → ${res}`);
}

function main() {
  const { packed, sourceOnly } = parseArgs(process.argv.slice(2));
  const pkg = checkPackageJson();
  checkSource();
  if (!sourceOnly && packed !== null && packed !== false) {
    checkPacked(pkg, typeof packed === "string" ? packed : "");
  } else if (!sourceOnly && process.argv.includes("--packed")) {
    checkPacked(pkg, "");
  }
  if (process.exitCode) {
    console.error(
      "[smoke:card-assets] Refusing pack: missing card UI / Nexus assets would ship white-square item cards."
    );
    process.exit(process.exitCode);
  }
  ok("all card pack asset checks passed");
}

main();
