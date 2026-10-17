"use strict";

/**
 * Deterministic item analysis keyed by the exact @U code.
 *
 * OCR, catalog labels, and user nicknames may suggest an item, but only this
 * path is allowed to describe the serial that Build/card/delivery will use.
 */

const { labelSerialOffline } = require("./offline_serial_card");
const { lookupExactNcsCard } = require("./ncs_lookup_card");
const { evaluateNexusCardStats, nexusStatus } = require("./nexus_card_stats");

const cache = new Map();
const CACHE_MAX = 96;

function clean(value) {
  return String(value == null ? "" : value).trim();
}

function norm(value) {
  return clean(value).toLocaleLowerCase("en-US").replace(/\s+/g, " ");
}

function setCache(key, value) {
  cache.delete(key);
  cache.set(key, value);
  while (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value);
}

function exactField(exact, ...keys) {
  for (const key of keys) {
    const value = exact?.[key] ?? exact?.raw?.[key] ?? exact?.native_equipment?.[key];
    if (value != null && clean(value)) return value;
  }
  return "";
}

function conflict(field, left, right, leftSource, rightSource) {
  if (!clean(left) || !clean(right) || norm(left) === norm(right)) return null;
  return {
    field,
    values: [
      { value: left, source: leftSource },
      { value: right, source: rightSource },
    ],
  };
}

async function analyzeItem(serial, hints = {}) {
  const code = clean(serial);
  if (!code.startsWith("@U")) {
    return {
      ok: false,
      exact: false,
      serial: code,
      error: "A complete @U serial is required.",
      unknowns: ["serial"],
      conflicts: [],
    };
  }
  if (code.length > 200000) {
    return {
      ok: false,
      exact: false,
      serial: "",
      error: "Serial is too large to analyze safely.",
      unknowns: ["serial"],
      conflicts: [],
    };
  }

  const levelHint = Number(hints?.level);
  const cacheKey = `${code}\n${Number.isFinite(levelHint) ? levelHint : ""}`;
  if (cache.has(cacheKey)) {
    const hit = cache.get(cacheKey);
    cache.delete(cacheKey);
    cache.set(cacheKey, hit);
    return hit;
  }

  const decoded = labelSerialOffline(code);
  if (!decoded?.identity?.readable || !decoded?.meta_ok) {
    const failed = {
      ok: false,
      exact: false,
      serial: code,
      identity: decoded?.identity || null,
      error: decoded?.identity?.error || "Serial could not be decoded.",
      unknowns: ["decoded_item"],
      conflicts: [],
    };
    setCache(cacheKey, failed);
    return failed;
  }

  let exactCard = null;
  try {
    exactCard = await lookupExactNcsCard(code);
  } catch {
    exactCard = null;
  }

  const cardInput = {
    ...decoded,
    part_names: decoded.name_parts?.length ? decoded.name_parts : decoded.part_names,
    serial: code,
    level: Number.isFinite(levelHint) && levelHint > 0 ? levelHint : decoded.level,
    itemType: decoded.item_type || decoded.type,
    type_label: decoded.item_type || decoded.type,
  };
  const calculated = nexusStatus().ok ? evaluateNexusCardStats(cardInput) : null;

  const exactName = exactField(exactCard, "full_name", "display_name", "title");
  const calculatedName = clean(calculated?.full_name || calculated?.display_name);
  const decodedName = clean(decoded.display_name || decoded.unique_name);
  const displayName = calculatedName || exactName || decodedName;
  const itemType =
    clean(decoded.item_type || decoded.type) ||
    clean(exactField(exactCard, "item_type", "type_label"));
  const manufacturer =
    clean(decoded.manufacturer) || clean(exactField(exactCard, "manufacturer"));
  const rarity = clean(decoded.rarity) || clean(exactField(exactCard, "rarity"));
  const level = Number.isFinite(Number(decoded.level)) ? Number(decoded.level) : null;
  const stats =
    Array.isArray(exactCard?.stats) && exactCard.stats.length
      ? exactCard.stats
      : Array.isArray(calculated?.stats)
        ? calculated.stats
        : [];
  const partNames = Array.isArray(decoded.name_parts) && decoded.name_parts.length
    ? decoded.name_parts : Array.isArray(decoded.part_names) ? decoded.part_names : [];
  const perkRows = Array.isArray(decoded.perk_rows) ? decoded.perk_rows : [];

  const conflicts = [
    conflict("name", exactName, calculatedName, "exact_catalog", "offline_game_data"),
    conflict(
      "item_type",
      decoded.item_type,
      exactField(exactCard, "item_type", "type_label"),
      "serial_decode",
      "exact_catalog"
    ),
    conflict(
      "rarity",
      decoded.rarity,
      exactField(exactCard, "rarity"),
      "serial_decode",
      "exact_catalog"
    ),
  ].filter(Boolean);

  const unknowns = [];
  if (!displayName) unknowns.push("name");
  if (!itemType) unknowns.push("item_type");
  if (!manufacturer) unknowns.push("manufacturer");
  if (!rarity) unknowns.push("rarity");
  if (!Number.isFinite(level)) unknowns.push("level");
  if (!partNames.length) unknowns.push("parts");
  if (!stats.length) unknowns.push("stats");

  const result = {
    ok: true,
    exact: true,
    serial: code,
    identity: {
      ...decoded.identity,
      exact_serial_preserved: true,
    },
    decoded_human: clean(decoded.decoded_human),
    display_name: displayName,
    full_name: calculatedName || exactName || "",
    item_type: itemType,
    manufacturer,
    rarity,
    level,
    set: clean(decoded.set),
    element: clean(decoded.element || decoded.damage_type),
    part_names: partNames,
    perk_rows: perkRows,
    stats,
    unknowns,
    conflicts,
    provenance: {
      identity: "serial_decode",
      level: "serial_decode",
      parts: "serial_decode",
      name: calculatedName
        ? "offline_game_data"
        : exactName
          ? "exact_catalog"
          : decodedName
            ? "serial_decode"
            : "unknown",
      stats:
        Array.isArray(exactCard?.stats) && exactCard.stats.length
          ? "exact_catalog"
          : calculated?.ok
            ? "offline_game_data"
            : "unknown",
    },
    sources: {
      exact_catalog: Boolean(exactCard),
      offline_game_data: Boolean(calculated?.ok),
      serial_decode: true,
    },
    card_props: {
      ...decoded,
      serial: code,
      display_name: displayName,
      full_name: calculatedName || exactName || "",
      item_type: itemType,
      type: itemType,
      type_label: itemType,
      itemType,
      manufacturer,
      rarity,
      level,
      set: clean(decoded.set),
      element: clean(decoded.element || decoded.damage_type),
      stats,
      part_names: partNames,
      perk_rows: perkRows,
      identity: decoded.identity,
      provenance: {
        name: calculatedName
          ? "offline_game_data"
          : exactName
            ? "exact_catalog"
            : "serial_decode",
        stats:
          Array.isArray(exactCard?.stats) && exactCard.stats.length
            ? "exact_catalog"
            : calculated?.ok
              ? "offline_game_data"
              : "unknown",
      },
      unknowns,
      conflicts,
    },
  };
  setCache(cacheKey, result);
  return result;
}

module.exports = { analyzeItem };
