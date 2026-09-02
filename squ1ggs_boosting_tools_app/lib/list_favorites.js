"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const FILENAME = "list_favorites.json";
const BUCKETS = Object.freeze([
  "itempools",
  "travel_maps",
  "travel_stations",
  "mobs",
  "ios",
  "serial_store",
  "gzo",
  "lootlemon",
]);

const CATALOG_BUCKET = Object.freeze({
  item_pools: "itempools",
  travel_maps: "travel_maps",
  travel_stations: "travel_stations",
  mob_actors: "mobs",
  io_spawns: "ios",
  serial_store: "serial_store",
  gzo: "gzo",
  lootlemon: "lootlemon",
});

function emptyStore() {
  const out = {};
  for (const key of BUCKETS) out[key] = [];
  return out;
}

function favoritesRoot() {
  const base =
    process.env.LOCALAPPDATA ||
    process.env.APPDATA ||
    path.join(os.homedir(), "AppData", "Local");
  return path.join(base, "Squ1ggsBoostingTools");
}

function favoritesPath() {
  return path.join(favoritesRoot(), FILENAME);
}

function inventorySettingsPath() {
  return path.join(
    os.homedir(),
    "Documents",
    "My Games",
    "Borderlands 4",
    "Saved",
    "Squ1ggsBoostingTools_settings.json"
  );
}

function bmsFavoritesPath() {
  // Live sdk_mods/settings — shared with in-game BMS favourites when present.
  const candidates = [
    path.join(
      process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)",
      "Steam",
      "steamapps",
      "common",
      "Borderlands 4",
      "sdk_mods",
      "settings",
      "squ1ggs_bms_favorites.json"
    ),
  ];
  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) return candidate;
    } catch {
      /* ignore */
    }
  }
  return path.join(favoritesRoot(), "squ1ggs_bms_favorites.json");
}

function readJson(filePath) {
  try {
    const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
    return data && typeof data === "object" ? data : {};
  } catch {
    return {};
  }
}

function normalizeIds(values) {
  const out = [];
  const seen = new Set();
  for (const raw of values || []) {
    const id = String(raw || "").trim();
    if (!id) continue;
    const key = id.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(id);
  }
  return out;
}

function mergeIds(...lists) {
  return normalizeIds(lists.flat());
}

function loadFavorites() {
  const store = emptyStore();
  const local = readJson(favoritesPath());
  for (const key of BUCKETS) {
    store[key] = normalizeIds(local[key]);
  }

  // Share pool / travel / GZO / Lootlemon favourites with the in-game BLImGui panel.
  const inv = readJson(inventorySettingsPath());
  store.itempools = mergeIds(store.itempools, inv.favorite_itempools);
  store.travel_maps = mergeIds(store.travel_maps, inv.favorite_travel_maps);
  store.travel_stations = mergeIds(store.travel_stations, inv.favorite_travel_stations);
  store.gzo = mergeIds(store.gzo, inv.favorite_gzo_serials);
  store.lootlemon = mergeIds(store.lootlemon, inv.favorite_lootlemon_serials);

  const bms = readJson(bmsFavoritesPath());
  store.mobs = mergeIds(store.mobs, bms.favorite_mobs);
  store.ios = mergeIds(store.ios, bms.favorite_encounters, bms.favorite_ios, bms.favorite_props);

  return store;
}

function writeLocal(store) {
  const payload = emptyStore();
  for (const key of BUCKETS) {
    payload[key] = normalizeIds(store[key]);
  }
  const filePath = favoritesPath();
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + "\n", "utf8");
  return payload;
}

function syncShared(store) {
  try {
    const invPath = inventorySettingsPath();
    const inv = readJson(invPath);
    inv.favorite_itempools = normalizeIds(store.itempools);
    inv.favorite_travel_maps = normalizeIds(store.travel_maps);
    inv.favorite_travel_stations = normalizeIds(store.travel_stations);
    inv.favorite_gzo_serials = normalizeIds(store.gzo);
    inv.favorite_lootlemon_serials = normalizeIds(store.lootlemon);
    fs.mkdirSync(path.dirname(invPath), { recursive: true });
    fs.writeFileSync(invPath, JSON.stringify(inv, null, 2) + "\n", "utf8");
  } catch {
    /* best-effort */
  }
  try {
    const bmsPath = bmsFavoritesPath();
    const bms = readJson(bmsPath);
    bms.favorite_mobs = normalizeIds(store.mobs);
    bms.favorite_ios = normalizeIds(store.ios);
    fs.mkdirSync(path.dirname(bmsPath), { recursive: true });
    fs.writeFileSync(bmsPath, JSON.stringify(bms, null, 2) + "\n", "utf8");
  } catch {
    /* best-effort */
  }
}

function bucketForCatalog(catalog) {
  const name = String(catalog || "").trim();
  return CATALOG_BUCKET[name] || "";
}

function isFavorite(store, bucket, id) {
  const needle = String(id || "").trim().toLowerCase();
  if (!needle || !store?.[bucket]) return false;
  return store[bucket].some((entry) => String(entry).toLowerCase() === needle);
}

function toggleFavorite(bucket, id) {
  const key = String(bucket || "").trim();
  const value = String(id || "").trim();
  if (!BUCKETS.includes(key) || !value) {
    return loadFavorites();
  }
  const store = loadFavorites();
  const low = value.toLowerCase();
  const existing = store[key].findIndex((entry) => String(entry).toLowerCase() === low);
  if (existing >= 0) store[key].splice(existing, 1);
  else store[key].unshift(value);
  const saved = writeLocal(store);
  syncShared(saved);
  return saved;
}

function sortFavoritesFirst(rows, idFn, bucket, store) {
  const list = Array.isArray(rows) ? rows.slice() : [];
  if (!list.length || !bucket) return list;
  const fav = new Set(
    (store?.[bucket] || []).map((entry) => String(entry).toLowerCase())
  );
  if (!fav.size) return list;
  return list.sort((a, b) => {
    const aFav = fav.has(String(idFn(a) || "").toLowerCase()) ? 0 : 1;
    const bFav = fav.has(String(idFn(b) || "").toLowerCase()) ? 0 : 1;
    if (aFav !== bFav) return aFav - bFav;
    return 0;
  });
}

module.exports = {
  BUCKETS,
  CATALOG_BUCKET,
  bucketForCatalog,
  loadFavorites,
  toggleFavorite,
  isFavorite,
  sortFavoritesFirst,
};
