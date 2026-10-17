"use strict";

/**
 * Private gold harness — offline SQBT cards vs in-game-first fixture JSON.
 * Pack gate: npm run smoke:card-gold
 * Optional: --crosscheck-ncs (local debug only; not in prepack)
 */

const fs = require("node:fs");
const path = require("node:path");

const { evaluateNexusCardStats } = require("../lib/nexus_card_stats");

const ROOT = path.join(__dirname, "..");
const FIXTURE_DIR = path.join(__dirname, "fixtures", "card_gold");
const CROSSCHECK = process.argv.includes("--crosscheck-ncs");

function plain(text) {
  return String(text || "")
    .replace(/<[^>]+>/g, "")
    .replace(/\[[^\]]+\]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function parseNumber(text) {
  const s = String(text || "").replace(/,/g, "").trim();
  if (!s || s === "—") return null;
  const multi = s.match(
    /^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*x\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))/i
  );
  if (multi) return Number(multi[1]);
  const n = Number(s.replace(/[^\d.+-]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function groupRows(card, group) {
  return (card.native_equipment?.groups?.[group] || []).map((row) => ({
    value: plain(row.value || row.loc_text || ""),
    number: parseNumber(row.value || row.loc_text || ""),
  }));
}

function summarize(card) {
  const headline = groupRows(card, "headline");
  const primary = groupRows(card, "primary");
  const secondary = groupRows(card, "secondary");
  const element = groupRows(card, "element");
  const firmware = groupRows(card, "firmware");
  const stats = Array.isArray(card.stats) ? card.stats : [];
  const statNum = (label) => {
    const row = stats.find((s) => String(s.label || "").toLowerCase() === label.toLowerCase());
    return row ? parseNumber(row.value) : null;
  };
  const damage =
    card.raw?.damage ??
    card.damage ??
    statNum("Damage");
  const dps = card.raw?.dps ?? card.dps ?? statNum("DPS");
  const fwBlock = card.firmware_block || card.raw?.firmware_block;
  return {
    item_type: card.raw?.item_type || card.itemType || "",
    headline: headline[0]?.number ?? null,
    primary: primary.map((r) => r.value),
    primary_numbers: primary.map((r) => r.number).filter((n) => n != null && n !== 0).length
      ? primary.map((r) => r.number)
      : primary.map((r) => r.number),
    secondary_includes: secondary.map((r) => r.value).filter(Boolean),
    element: element.map((r) => r.value),
    firmware_count:
      firmware.length ||
      (fwBlock && fwBlock.firmwareident ? 1 : 0) ||
      (Array.isArray(card.native_firmware) ? card.native_firmware.length : 0),
    damage,
    dps,
    price: card.native_equipment?.price ?? card.raw?.price ?? null,
    stats_source: card.source || card.raw?.stats_source || "",
  };
}

function within(actual, expected, tol) {
  if (expected == null) return true;
  if (actual == null) return false;
  const a = Number(actual);
  const e = Number(expected);
  if (!Number.isFinite(a) || !Number.isFinite(e)) return false;
  if (tol == null) return a === e;
  if (tol.mode === "abs") return Math.abs(a - e) <= Number(tol.value || 0);
  if (tol.mode === "pct") return Math.abs(a - e) <= Math.abs(e) * Number(tol.value || 0);
  return a === e;
}

function checkFixture(fixture, actual) {
  const errors = [];
  const expect = fixture.expect || {};
  const tol = fixture.tolerance || {};

  if (expect.item_type && String(actual.item_type) !== String(expect.item_type)) {
    errors.push(`item_type: got ${actual.item_type}, want ${expect.item_type}`);
  }

  if (Array.isArray(expect.primary_numbers)) {
    expect.primary_numbers.forEach((want, i) => {
      if (want == null) return;
      const got = actual.primary_numbers[i];
      const t = tol.primary_numbers?.[i] || tol.primary || { mode: "pct", value: 0.02 };
      if (!within(got, want, t)) {
        errors.push(`primary[${i}]: got ${got}, want ~${want}`);
      }
    });
  }

  if (Array.isArray(expect.secondary_includes)) {
    for (const needle of expect.secondary_includes) {
      const ok = (actual.secondary_includes || []).some((row) =>
        new RegExp(needle, "i").test(row)
      );
      if (!ok) errors.push(`secondary missing /${needle}/`);
    }
  }

  if (Array.isArray(expect.element_includes)) {
    for (const needle of expect.element_includes) {
      const ok = (actual.element || []).some((row) => new RegExp(needle, "i").test(row));
      if (!ok) errors.push(`element missing /${needle}/`);
    }
  }

  if (expect.headline != null) {
    const t = tol.headline || { mode: "pct", value: 0.02 };
    if (!within(actual.headline, expect.headline, t)) {
      errors.push(`headline: got ${actual.headline}, want ~${expect.headline}`);
    }
  }

  if (expect.firmware_min != null && actual.firmware_count < expect.firmware_min) {
    errors.push(`firmware_count: got ${actual.firmware_count}, want >= ${expect.firmware_min}`);
  }

  if (expect.damage != null) {
    const t = tol.damage || { mode: "pct", value: 0.03 };
    if (!within(actual.damage, expect.damage, t)) {
      errors.push(`damage: got ${actual.damage}, want ~${expect.damage}`);
    }
  }

  if (expect.dps != null) {
    const t = tol.dps || { mode: "pct", value: 0.05 };
    if (!within(actual.dps, expect.dps, t)) {
      errors.push(`dps: got ${actual.dps}, want ~${expect.dps}`);
    }
  }

  if (expect.price != null) {
    const t = tol.price || { mode: "pct", value: 0.05 };
    if (!within(actual.price, expect.price, t)) {
      errors.push(`price: got ${actual.price}, want ~${expect.price}`);
    }
  }

  if (expect.primary_min_count != null && (actual.primary || []).length < expect.primary_min_count) {
    errors.push(
      `primary count: got ${(actual.primary || []).length}, want >= ${expect.primary_min_count}`
    );
  }

  return errors;
}

async function maybeCrosscheck(serial) {
  if (!CROSSCHECK || !serial) return null;
  try {
    const { lookupExactNcsCard } = require("../lib/ncs_lookup_card");
    return await lookupExactNcsCard(serial);
  } catch (error) {
    return { error: String(error && error.message ? error.message : error) };
  }
}

function loadFixtures() {
  if (!fs.existsSync(FIXTURE_DIR)) return [];
  return fs
    .readdirSync(FIXTURE_DIR)
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => {
      const file = path.join(FIXTURE_DIR, name);
      return { name, fixture: JSON.parse(fs.readFileSync(file, "utf8")) };
    });
}

async function main() {
  const rows = loadFixtures();
  if (!rows.length) {
    console.error(`[smoke:card-gold] no fixtures in ${FIXTURE_DIR}`);
    process.exit(1);
  }

  let failed = 0;
  for (const { name, fixture } of rows) {
    const card = evaluateNexusCardStats(fixture.input || {});
    const actual = summarize(card);
    const errors = checkFixture(fixture, actual);
    if (CROSSCHECK && fixture.serial) {
      const cross = await maybeCrosscheck(fixture.serial);
      if (cross?.error) {
        console.log(`[smoke:card-gold] ${name} crosscheck skip: ${cross.error}`);
      } else if (cross) {
        console.log(
          `[smoke:card-gold] ${name} crosscheck source=${cross.source || "ok"} (private)`
        );
      }
    }
    if (errors.length) {
      failed += 1;
      console.error(`[smoke:card-gold] FAIL ${name}`);
      for (const err of errors) console.error(`  - ${err}`);
      if (process.argv.includes("--dump")) {
        console.error("  actual:", JSON.stringify(actual, null, 2));
      }
    } else {
      console.log(`[smoke:card-gold] OK: ${fixture.id || name}`);
    }
  }

  if (failed) {
    console.error(`[smoke:card-gold] ${failed}/${rows.length} fixture(s) failed`);
    process.exit(1);
  }
  console.log(`[smoke:card-gold] all ${rows.length} fixtures passed`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
