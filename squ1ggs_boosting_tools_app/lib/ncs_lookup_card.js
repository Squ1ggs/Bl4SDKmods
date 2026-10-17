"use strict";

const API_ROOT = "https://api.ncs-lookup.io/v1";
const cache = new Map();
const CACHE_MAX = 256;
const ABSENT_TTL_MS = 5 * 60 * 1000;

function cacheSet(serial, value, ttl = 0) {
  cache.delete(serial);
  cache.set(serial, { value, expires: ttl ? Date.now() + ttl : 0 });
  while (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value);
}

function cacheGet(serial) {
  const hit = cache.get(serial);
  if (!hit) return undefined;
  if (hit.expires && hit.expires < Date.now()) {
    cache.delete(serial);
    return undefined;
  }
  cache.delete(serial);
  cache.set(serial, hit);
  return hit.value;
}

async function fetchJson(url, timeoutMs = 2500) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`NCS Lookup HTTP ${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

function iconUrl(asset) {
  const match = String(asset || "").match(/'\/Game\/(?:DLC\/[^'/]+\/)?(uiresources\/[^']+)'/i);
  return match ? `coui://${match[1].split(".")[0]}.png` : "";
}

function rowValue(row) {
  return String(row?.card_value_markup || row?.value_markup || "").trim();
}

function normalizeRow(row, index) {
  return {
    image: iconUrl(row?.icon_asset),
    value: rowValue(row),
    label: String(row?.label || "").trim(),
    loc_text: String(row?.label || "").trim(),
    comparison: "",
    comparison_id: "",
    ident: "",
    priority: index,
  };
}

function numericValue(value) {
  const text = String(value || "").replace(/,/g, "").trim();
  if (!text) return null;
  if (/^[+-]?infm?$/i.test(text)) return Infinity;
  // Live / NCS multi-pellet Damage is "4,523 x 7" — keep per-pellet (first number).
  // Product belongs in DPS via weapon_damage_per_shot, not the Damage primary.
  const multi = text.match(
    /^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*x\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*$/i
  );
  if (multi) {
    const damage = Number(multi[1]);
    if (!Number.isFinite(damage) || damage <= 0) return null;
    return Math.round(damage);
  }
  const number = Number(text.replace(/[^\d.+-]/g, ""));
  return Number.isFinite(number) ? number : null;
}

function buildFirmwareBlockFromNcs(rows) {
  if (!Array.isArray(rows) || !rows.length) return null;
  const best = rows[0];
  const value = String(best?.value || best?.label || "").replace(/<[^>]+>/g, "").trim();
  const label = String(best?.label || "").trim() || value.replace(/\s+\d+\s*$/, "").trim();
  let ident = String(best?.comparison_id || best?.ident || "").trim();
  if (!ident && value) {
    const stem = value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "");
    if (stem) ident = stem.startsWith("fw_") ? stem : `fw_${stem}`;
  }
  if (!ident) return null;
  return {
    firmwareident: ident,
    firmware: { loc_text: label || "Firmware", comparison: "" },
    firmwarestring: `${Math.min(3, rows.length)}/3`,
    firmwarecount: Math.min(3, rows.length),
    firmwaretransfered: false,
  };
}

function normalizeItemCard(itemCard) {
  if (!itemCard || typeof itemCard !== "object") return null;
  const groups = {};
  for (const [name, rows] of Object.entries(itemCard.stats || {})) {
    if (!Array.isArray(rows)) continue;
    groups[String(name).toLowerCase()] = rows
      .map(normalizeRow)
      .filter((row) => row.value);
  }
  const primary = groups.primary || [];
  const findPrimary = (label) =>
    primary.find((row) => String(row.label).toLowerCase() === label)?.value;
  const damage = numericValue(findPrimary("damage"));
  const accuracy = numericValue(findPrimary("accuracy"));
  const reload = numericValue(findPrimary("reload time"));
  const fireRate = numericValue(findPrimary("fire rate"));
  // Live Ripper / heat cards label magazine as "Ammo" (not "Magazine Size").
  const magazine =
    numericValue(findPrimary("magazine size")) ??
    numericValue(findPrimary("ammo")) ??
    numericValue(findPrimary("shots to overheat"));
  const stats = primary.map((row) => ({ label: row.label, value: row.value }));
  const redText = (groups.redtext || []).map((row) => row.value).filter(Boolean);
  const secondary = groups.secondary || [];
  const firmwareRows = groups.firmware || [];
  const firmwareBlock = buildFirmwareBlockFromNcs(firmwareRows);
  const elementText = (groups.element || []).map((row) => row.value).filter(Boolean).join(" | ");
  const isWeapon = /pistol|shotgun|assault|smg|submachine|sniper|heavy/i.test(
    String(itemCard.type || "")
  );
  const nativeEquipment = isWeapon
    ? null
    : {
        groups,
        values: {},
        price: Number.isFinite(Number(itemCard.sell_value)) ? Number(itemCard.sell_value) : null,
        type_label: String(itemCard.type || ""),
        thumbnail: iconUrl(itemCard.type_icon),
        missing: [],
      };
  return {
    ok: true,
    stats,
    source: "ncs_lookup_exact",
    display_name: String(itemCard.name || "").trim(),
    type_label: String(itemCard.type || "").trim(),
    native_groups: groups,
    native_secondary: secondary,
    native_firmware: firmwareRows,
    native_text: (groups.text || []).map((row) => row.value).filter(Boolean),
    firmware_block: firmwareBlock,
    red_text: redText,
    native_equipment: nativeEquipment,
    raw: {
      damage,
      dps: Number.isFinite(Number(itemCard.dps)) ? Number(itemCard.dps) : null,
      accuracy,
      reload,
      fire_rate: fireRate,
      magazine,
      crit: null,
      value: Number.isFinite(Number(itemCard.sell_value)) ? Number(itemCard.sell_value) : null,
      element_text: elementText,
      element_text2: "",
      native_groups: groups,
      native_secondary: secondary,
      native_firmware: firmwareRows,
      native_text: (groups.text || []).map((row) => row.value).filter(Boolean),
      firmware_block: firmwareBlock,
      red_text: redText,
      native_equipment: nativeEquipment,
      item_type: String(itemCard.type || ""),
      level: Number(itemCard.level) || null,
      display_name: String(itemCard.name || "").trim(),
    },
  };
}

async function lookupExactNcsCard(serial) {
  const key = String(serial || "").trim();
  if (!key.startsWith("@U")) return null;
  const cached = cacheGet(key);
  if (cached !== undefined) return cached;
  try {
    const search = await fetchJson(`${API_ROOT}/ncs/items?query=${encodeURIComponent(key)}`);
    const exact = search?.exactSerial;
    const itemKey =
      exact?.state === "existing"
        ? String(exact.itemKey || exact.item_key || exact.key || "")
        : "";
    if (!itemKey) {
      cacheSet(key, null, ABSENT_TTL_MS);
      return null;
    }
    const detail = await fetchJson(`${API_ROOT}/ncs/items/${encodeURIComponent(itemKey)}`);
    const normalized = normalizeItemCard(detail?.itemCard || detail?.item_card);
    if (normalized) cacheSet(key, normalized);
    return normalized;
  } catch {
    // Network and service failures remain retryable; offline Nexus data is the fallback.
    return null;
  }
}

module.exports = { lookupExactNcsCard, normalizeItemCard };
