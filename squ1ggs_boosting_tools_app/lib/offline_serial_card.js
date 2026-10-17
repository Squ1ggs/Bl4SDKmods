"use strict";

/**
 * Offline @U → card fields via the bundled Squ1ggsBoostingTools item_labels
 * (no live game bridge). Used so classmod cards still get part_names / skills
 * when NCS Lookup returns secondary-only chrome.
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { decodeSerialCard } = require("./serial_codec");

const cache = new Map();
const CACHE_MAX = 128;

function sdkmodRoot() {
  const candidates = [
    process.resourcesPath
      ? path.join(process.resourcesPath, "sdkmod", "Squ1ggsBoostingTools")
      : "",
    path.join(__dirname, "..", "resources", "Squ1ggsBoostingTools"),
    path.join(
      "C:",
      "Program Files (x86)",
      "Steam",
      "steamapps",
      "common",
      "Borderlands 4",
      "sdk_mods",
      "Squ1ggsBoostingTools"
    ),
  ].filter(Boolean);
  for (const root of candidates) {
    if (fs.existsSync(path.join(root, "item_labels.py"))) return root;
  }
  return "";
}

function cacheGet(serial) {
  if (!cache.has(serial)) return undefined;
  const hit = cache.get(serial);
  cache.delete(serial);
  cache.set(serial, hit);
  return hit;
}

function cacheSet(serial, value) {
  cache.delete(serial);
  cache.set(serial, value);
  while (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value);
}

function labelSerialOffline(serial) {
  const key = String(serial || "").trim();
  if (!key.startsWith("@U")) return null;
  if (cache.has(key)) return cacheGet(key);
  const root = sdkmodRoot();
  if (!root) return null;
  const deterministicFallback = () => {
    try {
      return decodeSerialCard(key, root);
    } catch {
      return null;
    }
  };
  const script = [
    "import hashlib, importlib.util, json, sys, types",
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
    "sc = load('serial_converter')",
    "il = load('item_labels')",
    "card = il.card_fields_from_serial(serial)",
    "try:",
    "    raw = sc.base85_decode(serial)",
    "    human = sc.serial_to_human(serial)",
    "    rebuilt = sc.human_to_serial(human)",
    "    card['serial'] = serial",
    "    card['decoded_human'] = human",
    "    card['identity'] = {",
    "        'serial_sha256': hashlib.sha256(serial.encode('utf-8')).hexdigest(),",
    "        'payload_sha256': hashlib.sha256(raw).hexdigest(),",
    "        'round_trip_exact': rebuilt == serial,",
    "        'readable': True,",
    "    }",
    "except Exception as exc:",
    "    card['identity'] = {",
    "        'serial_sha256': hashlib.sha256(serial.encode('utf-8')).hexdigest(),",
    "        'payload_sha256': '',",
    "        'round_trip_exact': False,",
    "        'readable': False,",
    "        'error': str(exc),",
    "    }",
    "print(json.dumps(card))",
  ].join("\n");
  try {
    if (process.env.SQBT_DISABLE_PYTHON_SERIAL === "1") {
      const fallback = deterministicFallback();
      cacheSet(key, fallback);
      return fallback;
    }
    const result = spawnSync("python", ["-c", script, root, key], {
      encoding: "utf8",
      maxBuffer: 8 * 1024 * 1024,
      windowsHide: true,
      timeout: 8000,
    });
    if (result.status !== 0) {
      const fallback = deterministicFallback();
      cacheSet(key, fallback);
      return fallback;
    }
    const parsed = JSON.parse(String(result.stdout || "").trim() || "null");
    if (!parsed || typeof parsed !== "object") {
      const fallback = deterministicFallback();
      cacheSet(key, fallback);
      return fallback;
    }
    cacheSet(key, parsed);
    return parsed;
  } catch {
    const fallback = deterministicFallback();
    cacheSet(key, fallback);
    return fallback;
  }
}

module.exports = { labelSerialOffline, sdkmodRoot };
