/**
 * cc-build-stats-rebuild.js
 * Build Stats (Core Snapshot) for Scooter's Toolbox Rebuild.
 * Provides accumulateFromSelected() to compute estimated multipliers from resolved part stats.
 *
 * Alternative: all_parts_stats_vd49.xlsx has structured stats (part_code, bucket, stat_value, combine, invert).
 * Run scripts/build_parts_stats_from_excel.py to export to assets/data/parts_stats.json.
 * Integration would need a part_code mapping (Excel uses "bor_hw.part_barrel_01", we use idRaw "254:10").
 */
(function () {
  'use strict';
  if (window.__ccBuildStatsRebuildV1) return;
  window.__ccBuildStatsRebuildV1 = true;

  function byId(id) { try { return document.getElementById(id); } catch (_) { return null; } }
  function q(s) { return String(s == null ? '' : s).trim(); }

  /**
   * Text fields for slug hints only (never yaml/library paste — those inflate Core Snapshot).
   * Omit outCodeB85 / raw Base85: false `\\d+:\\d+` matches inflate part lists.
   */
  var BUILD_STATS_SLUG_SOURCE_IDS = [
    'guidedOutputDeserialized', 'outCode', 'deserialized-code-output',
    'deserialized-code-output-yaml', 'deserialized-result', 'output-code-live', 'output-code', 'importBox'
  ];

  function resolveStatsSourceMode() {
    try {
      var last = String(window.__CC_LAST_CODE_TARGET || '').trim().toLowerCase();
      if (last === 'guided' || last === 'simple') return last;
    } catch (_) {}
    try {
      if (document.documentElement.classList.contains('stx-builder-mode-guided')) return 'guided';
    } catch (_) {}
    return 'simple';
  }

  function fieldText(el) {
    if (!el) return '';
    return String(el.value != null ? el.value : el.textContent || '');
  }

  /** Prefer deserialized / toolbox codes; skip pure @U Base85 blobs. */
  function looksLikeDeserializedBuildText(text) {
    var s = String(text || '').trim();
    if (!s) return false;
    if (/^@U/i.test(s) && s.indexOf('||') < 0 && !/\b\d+:\d+\b/.test(s)) return false;
    return /\b\d+:\d+\b/.test(s) || /\|\|/.test(s) || /^\d+\s*,/.test(s) || /\{/.test(s);
  }

  function inferBaseFamilyFromSerialText(text) {
    var s = String(text || '').trim();
    var dbl = s.indexOf('||');
    var prefix = dbl >= 0 ? s.slice(0, dbl).trim() : s;
    var m = prefix.match(/^\s*(\d+)\s*,\s*0\s*,\s*1\s*,\s*\d+\s*\|/) || prefix.match(/^\s*(\d+)\s*[,\|]/);
    return m ? Number(m[1]) : null;
  }

  /** Push one ref key onto refList (array). Preserves duplicates for stacked preset parts. */
  function pushRef(refList, ref) {
    var r = q(ref);
    if (r) refList.push(r);
  }

  function addRefsFromToken(tok, refList, opts) {
    var t = q(tok);
    if (!t) return;
    var o = opts || {};
    var baseFam = o.baseFamilyId;
    var dm = t.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
    if (dm) { pushRef(refList, dm[1] + ':' + dm[2]); return; }
    var bm = t.match(/^\{\s*(\d+)\s*\}$/);
    if (bm) {
      if (baseFam != null && Number.isFinite(Number(baseFam))) pushRef(refList, String(baseFam) + ':' + bm[1]);
      else pushRef(refList, bm[1]);
      return;
    }
    if (/^\d+:\d+$/.test(t)) { pushRef(refList, t); return; }
    if (/^\d+$/.test(t)) {
      if (baseFam != null && Number.isFinite(Number(baseFam))) pushRef(refList, String(baseFam) + ':' + t);
      else pushRef(refList, t);
      return;
    }
    pushRef(refList, t.replace(/^"+|"+$/g, ''));
  }

  function addRefsFromText(text, refList, opts) {
    if (!refList || typeof refList.push !== 'function') return;
    var s = String(text || '');
    var o = opts || {};
    var baseFam = o.baseFamilyId != null ? o.baseFamilyId : inferBaseFamilyFromSerialText(s);
    /*
     * This expression already captures both plain `family:id` refs and refs
     * inside `{family:id}`. Do not scan brace pairs a second time: doing so
     * counted every normal dual-ID part twice while still looking like an
     * intentional stacked duplicate.
     */
    var ms = s.match(/\b\d{1,6}:\d{1,6}\b/g);
    if (ms) ms.forEach(function (r) { pushRef(refList, r); });
    var bareMs = s.match(/\{\s*(\d{1,6})\s*\}/g);
    if (bareMs) bareMs.forEach(function (b) {
      var m = b.match(/\{\s*(\d+)\s*\}/);
      if (!m) return;
      if (baseFam != null && Number.isFinite(Number(baseFam))) pushRef(refList, String(baseFam) + ':' + m[1]);
      else pushRef(refList, m[1]);
    });
    try {
      var reQuoted = /"([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)"/g;
      var m;
      while ((m = reQuoted.exec(s)) !== null) {
        var tok = q(m[1]);
        if (tok) pushRef(refList, tok);
      }
    } catch (_) {}
    var reList = /\{(\d{1,6})\s*:\s*\[\s*([0-9,\s]+)\s*\]\s*\}/g;
    var m2;
    while ((m2 = reList.exec(s)) !== null) {
      var fam = m2[1];
      var list = String(m2[2] || '').replace(/,/g, ' ').trim().split(/\s+/).filter(Boolean);
      for (var i = 0; i < list.length; i++) {
        if (/^\d{1,6}$/.test(list[i])) pushRef(refList, fam + ':' + list[i]);
      }
    }
  }

  function stripQuotes(s) { return q(s).replace(/^"+|"+$/g, ''); }

  var _partLookupMap = null;
  function getPartLookupMap() {
    if (_partLookupMap) return _partLookupMap;
    var all = (window.STX_DATASET && window.STX_DATASET.ALL_PARTS) ? window.STX_DATASET.ALL_PARTS : [];
    if (!all.length) return null;
    var map = new Map();
    var norm = function (x) { return String(x || '').replace(/^"+|"+$/g, '').trim(); };
    for (var i = 0; i < all.length; i++) {
      var p = all[i];
      if (!p) continue;
      var idRaw = norm(p.idRaw || p.idraw || '');
      if (idRaw) { if (!map.has(idRaw)) map.set(idRaw, p); }
      if (p.family != null && p.id != null) {
        var famId = String(p.family) + ':' + String(p.id);
        if (!map.has(famId)) map.set(famId, p);
      }
      var c = norm(p.code);
      if (c) { if (!map.has(c)) map.set(c, p); }
      if (p.id != null && /^\d+$/.test(String(p.id))) {
        var sid = String(p.id);
        if (!map.has(sid)) map.set(sid, p);
      }
    }
    _partLookupMap = map;
    return map;
  }

  function resolvePart(ref) {
    if (!ref) return null;
    var code = typeof ref === 'string' ? stripQuotes(ref) : (ref.idRaw || ref.code || ref.spawnCode || '');
    if (!code) return null;
    try {
      if (typeof window.__lookupPartByImportCode === 'function') {
        var p = window.__lookupPartByImportCode(code);
        if (p) return p;
      }
    } catch (_) {}
    
    var norm = function (x) { return String(x || '').replace(/^"+|"+$/g, '').trim(); };
    var t = norm(code);
    
    var map = getPartLookupMap();
    if (map && map.has(t)) return map.get(t);

    // Fallback if map not ready or missed something
    var all = (window.STX_DATASET && window.STX_DATASET.ALL_PARTS) ? window.STX_DATASET.ALL_PARTS : [];
    for (var i = 0; i < all.length; i++) {
      var p = all[i];
      if (!p) continue;
      if (norm(p.idRaw || p.idraw || '') === t) return p;
      if (/^\d+$/.test(t) && Number(p.id) === Number(t)) return p;
      if (norm(p.code) === norm(t)) return p;
      var m = t.match(/^\s*(\d+)\s*:\s*(\d+)\s*$/);
      if (m && p.family != null && p.id != null && Number(m[1]) === Number(p.family) && Number(m[2]) === Number(p.id)) return p;
    }
    return null;
  }

  function displayStatsFor(part) {
    try {
      var p = (typeof resolvePart === 'function' ? resolvePart(part) : part) || part;
      if (p && typeof p.stats === 'string' && p.stats.trim()) return String(p.stats).trim();
      if (p && typeof p.statText === 'string' && p.statText.trim()) return String(p.statText).trim();
      var code = (p && (p.code || p.spawnCode || p.importCode || ''));
      code = String(code || '').replace(/^"+|"+$/g, '').trim();
      if (code) {
        var zip = window.__CC_ZIP_WEAPON_PARTS || window.ZIP_WEAPON_PARTS;
        if (zip && typeof zip === 'object' && zip[code] && zip[code].stats) return String(zip[code].stats).trim();
      }
    } catch (_) {}
    return '';
  }

  function getPartCodes(part) {
    var codes = [];
    var p = (typeof resolvePart === 'function' ? resolvePart(part) : part) || part;
    if (!p) return codes;
    var code = String(p.code || p.spawnCode || p.importCode || '').replace(/^"+|"+$/g, '').trim();
    if (code) codes.push(code);
    var idRaw = String(p.idRaw || p.idraw || '').trim();
    if (idRaw) codes.push(idRaw);
    if (p.family != null && p.id != null) codes.push(p.family + ':' + p.id);
    return codes;
  }

  function getExcelStatsForPart(part) {
    var data = window.PARTS_STATS_DATA;
    if (!data) return null;
    var codes = getPartCodes(part);
    for (var i = 0; i < codes.length; i++) {
      var c = String(codes[i] || '').trim();
      if (!c) continue;
      if (data.by_id_raw && data.by_id_raw[c]) return data.by_id_raw[c];
      if (data.by_part_code && data.by_part_code[c]) return data.by_part_code[c];
    }
    /*
     * Do not fall back to the global first match in by_code_suffix. Generic
     * suffixes (part_barrel_01, comp_05_legendary, etc.) collide across
     * manufacturers and weapon classes and can borrow unrelated stat rows.
     */
    return null;
  }

  function dedupeExcelStatRows(stats) {
    if (!stats || !stats.length) return stats;
    var seen = new Set();
    var out = [];
    for (var di = 0; di < stats.length; di++) {
      var s = stats[di];
      if (!s || typeof s !== 'object') continue;
      var k = String(s.bucket || '') + '\t' + String(s.stat_field || '') + '\t' + String(s.stat_value) + '\t' + String(s.combine || '');
      if (seen.has(k)) continue;
      seen.add(k);
      out.push(s);
    }
    return out.length ? out : stats;
  }

  /** Preserve raw damage scales; magnitude alone cannot identify add-vs-multiply semantics. */
  function partsStatsDamageScaleMulToDisplayMult(statField, combine, val) {
    var field = String(statField || '').toLowerCase();
    if (field !== 'damage_scale') return null;
    if (String(combine || '').trim().toLowerCase() !== 'mul') return null;
    var v = Number(val);
    return Number.isFinite(v) ? v : null;
  }

  /** Effective multiplier for human-readable % next to a raw ×scale value. */
  function scaleRowDisplayMultiplier(s) {
    if (!s || typeof s !== 'object') return null;
    if (String(s.combine || '').trim().toLowerCase() !== 'mul') return null;
    var sf = String(s.stat_field || '').toLowerCase();
    if (!isScaleStatField(sf)) return null;
    var val = Number(s.stat_value);
    if (!Number.isFinite(val)) return null;
    var dmgFix = partsStatsDamageScaleMulToDisplayMult(s.stat_field, s.combine, val);
    if (dmgFix != null && sf === 'damage_scale') return dmgFix;
    if (WSTAT_KEYS_INVERT_SCALE_FOR_BENEFIT[sf] && val !== 0) return 1 / val;
    return val;
  }

  function applyExcelStatsToBuckets(stats, buckets, record, partLabel) {
    if (!stats || !Array.isArray(stats)) return;
    stats = dedupeExcelStatRows(stats);
    var pl = partLabel || '';
    var grouped = Object.create(null);
    for (var gi = 0; gi < stats.length; gi++) {
      var gs = stats[gi];
      if (!gs || typeof gs !== 'object') continue;
      var gb = String(gs.bucket || '').trim();
      var gf = String(gs.stat_field || gb).trim().toLowerCase();
      var gc = String(gs.combine || 'add').trim().toLowerCase();
      if (!gb || !buckets[gb]) continue;
      var gk = gb + '\0' + gf + '\0' + gc;
      if (!grouped[gk]) grouped[gk] = [];
      grouped[gk].push(gs);
    }
    var groupKeys = Object.keys(grouped);
    for (var gidx = 0; gidx < groupKeys.length; gidx++) {
      var group = grouped[groupKeys[gidx]];
      var distinct = [];
      var seenValues = Object.create(null);
      for (var gv = 0; gv < group.length; gv++) {
        var gn = Number(group[gv].stat_value);
        if (!Number.isFinite(gn)) continue;
        var gnKey = String(gn);
        if (seenValues[gnKey]) continue;
        seenValues[gnKey] = true;
        distinct.push(gn);
      }
      var s = group[0];
      var bucket = s && s.bucket ? String(s.bucket).trim() : '';
      var comb = String(s.combine || 'add').trim().toLowerCase();
      var statField = String(s.stat_field || bucket);
      var sfLow = statField.toLowerCase();
      if (distinct.length > 1) {
        distinct.sort(function (a, b) { return a - b; });
        record(bucket, '', null, {
          part: pl,
          source: 'PARTS_STATS_DATA',
          detail: statField + ': alternate context values ' + distinct.join(', '),
          combine: 'alternative',
          statField: statField,
          alternatives: distinct,
          invertedBenefit: !!WSTAT_KEYS_INVERT_SCALE_FOR_BENEFIT[sfLow]
        });
        continue;
      }
      var val = Number(s.stat_value);
      if (!Number.isFinite(val)) continue;
      var mult = 1;
      if (comb === 'mul') {
        if (val <= 0) {
          record(bucket, '', null, {
            part: pl,
            source: 'PARTS_STATS_DATA',
            detail: statField + ': invalid/unsupported scale ' + val,
            combine: 'invalid',
            statField: statField,
            invalidValue: val
          });
          continue;
        }
        mult = val;
        var dmgFix = partsStatsDamageScaleMulToDisplayMult(s.stat_field, comb, val);
        if (dmgFix != null) mult = dmgFix;
        if ((s.invert || WSTAT_KEYS_INVERT_SCALE_FOR_BENEFIT[sfLow]) && mult !== 0) mult = 1 / mult;
      } else if (comb === 'add') {
        mult = 1 + val;
      } else if (comb === 'value') {
        mult = null;
      } else {
        continue;
      }
      var detail = formatExcelStatRow(s);
      record(bucket, '', mult, {
        part: pl,
        source: 'PARTS_STATS_DATA',
        detail: detail,
        combine: comb,
        statField: statField,
        rawValue: val,
        multApplied: mult,
        invertedBenefit: !!WSTAT_KEYS_INVERT_SCALE_FOR_BENEFIT[sfLow]
      });
    }
  }

  /** Rough map from weapon init / stat_field names to core snapshot buckets (same coarse groups as text parser). */
  var FIELD_TO_BUCKET = {
    damage_scale: 'damage',
    critdamage_add: 'crit',
    statuschance_scale: 'elemental',
    statusdamage_scale: 'elemental',
    elementaldamage_scale: 'elemental',
    elementalchance_scale: 'elemental',
    accuracy_scale: 'accuracy',
    maxaccuracy_scale: 'accuracy',
    spread_scale: 'accuracy',
    zoomtime_scale: 'ads',
    /** Init tables use zoomduration_scale (e.g. Dad_UB); treat like zoom time → ADS. */
    zoomduration_scale: 'ads',
    sway_scale: 'ads',
    recoil_scale: 'ads',
    accimpulse_scale: 'ads',
    equiptime_scale: 'ads',
    putdowntime_scale: 'ads',
    firerate_scale: 'firerate',
    projpershot_scale: 'projectiles',
    reloadtime_scale: 'reload_time',
    reloadtime_value: 'reload_time',
    thrownreloadtime_value: 'reload_time'
  };

  /**
   * weapon_stats_data uses:
   * - _scale: direct multiplier (e.g. damage_scale 0.95)
   * - _add: additive (e.g. critdamage_add 0.35 = +35% crit damage -> mult 1.35)
   * - _value: additive offset to base stat, NOT a multiplier — exclude from mult display
   *
   * For core cards, combined mult is meant to track “direction of benefit” (higher ≈ better).
   * Scales that worsen handling when the raw number goes up use benefitMult = 1/val (same idea
   * as spread_scale). Not inverted: damage, firerate, projpershot, elemental, crit add,
   * reloadtime (reload card uses speed/time explicitly).
   */
  var WSTAT_KEYS_INVERT_SCALE_FOR_BENEFIT = {
    spread_scale: 1,
    maxaccuracy_scale: 1,
    accuracy_scale: 1,
    recoil_scale: 1,
    accimpulse_scale: 1,
    sway_scale: 1,
    equiptime_scale: 1,
    putdowntime_scale: 1,
    zoomtime_scale: 1,
    zoomduration_scale: 1
  };

  function wstatRawScaleToBenefitMult(key, val) {
    if (val === 0 || !Number.isFinite(val)) return null;
    if (WSTAT_KEYS_INVERT_SCALE_FOR_BENEFIT[key]) return 1 / val;
    return val;
  }

  function applyWstatsObjectToBuckets(obj, buckets, record, partLabel) {
    if (!obj || typeof obj !== 'object') return;
    var pl = partLabel || '';
    var keys = Object.keys(obj);
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      var bucket = FIELD_TO_BUCKET[k];
      if (!bucket || !buckets[bucket]) continue;
      var val = Number(obj[k]);
      if (!Number.isFinite(val)) continue;
      var mult;
      var combine;
      if (k.indexOf('_add') !== -1) {
        mult = 1 + val;
        combine = 'add';
      } else if (k.indexOf('_value') !== -1) {
        mult = null;
        combine = 'value';
      } else {
        if (val <= 0) {
          record(bucket, k, null, {
            part: pl,
            source: 'WEAPON_STATS_DATA',
            detail: k + ': invalid/unsupported scale ' + obj[k],
            combine: 'invalid',
            statField: k,
            invalidValue: val
          });
          continue;
        }
        mult = wstatRawScaleToBenefitMult(k, val);
        if (mult == null) continue;
        combine = 'mul';
      }
      record(bucket, k, mult, {
        part: pl,
        source: 'WEAPON_STATS_DATA',
        detail: k + ': ' + obj[k],
        combine: combine,
        statField: k,
        rawValue: val,
        multApplied: mult,
        invertedBenefit: !!WSTAT_KEYS_INVERT_SCALE_FOR_BENEFIT[k]
      });
    }
  }

  function getWstatsGlobal() {
    try {
      if (typeof WEAPON_STATS_DATA !== 'undefined' && WEAPON_STATS_DATA) return WEAPON_STATS_DATA;
    } catch (_) {}
    return null;
  }

  var WEAPON_TYPE_MAP = { pistol: 'PS', shotgun: 'SG', ar: 'AR', smg: 'SM', sniper: 'SR', heavy_weapon: 'HW' };
  var MFR_BARREL_PREFIX = { Daedalus: 'DAD', Jakobs: 'JAK', Tediore: 'TED', Torgue: 'TOR', Order: 'ORD', Vladof: 'VLA', Borg: 'BOR', Maliwan: 'MAL' };

  function getWeaponTypeCode(slug) {
    if (!slug) return null;
    var parts = String(slug).split('_');
    var type = parts.slice(1).join('_');
    return WEAPON_TYPE_MAP[type] || null;
  }

  function getMfrFromSlug(slug) {
    if (!slug) return null;
    var parts = String(slug).split('_');
    var map = { daedalus: 'Daedalus', jakobs: 'Jakobs', tediore: 'Tediore', torgue: 'Torgue', order: 'Order', vladof: 'Vladof', ripper: 'Borg', maliwan: 'Maliwan', atlas: 'Atlas', cov: 'COV', hyperion: 'Hyperion' };
    return map[parts[0]] || null;
  }

  function lookupBarrelStats(slug, partName) {
    var WSTATS = getWstatsGlobal();
    if (!WSTATS || !slug || !partName) return null;
    var typeCode = getWeaponTypeCode(slug);
    if (!typeCode) return null;
    var tableKey = 'Weapon_' + typeCode + '_Barrel_Init';
    var table = WSTATS[tableKey];
    if (!table || !table.rows) return null;
    var mfr = getMfrFromSlug(slug);
    var prefix = mfr ? MFR_BARREL_PREFIX[mfr] : '';
    var bestMatch = null;
    var keys = Object.keys(table.rows);
    for (var i = 0; i < keys.length; i++) {
      var rowName = keys[i];
      if (partName && rowName.toLowerCase().indexOf(String(partName).replace(/^part_/i, '').toLowerCase()) !== -1) {
        bestMatch = table.rows[rowName];
        break;
      }
      if (prefix && rowName.indexOf(prefix) === 0) {
        var partIdx = partName ? String(partName).match(/(\d+)/) : null;
        var rowIdx = rowName.match(/(\d+)/);
        if (partIdx && rowIdx && partIdx[1] === rowIdx[1]) {
          bestMatch = table.rows[rowName];
          break;
        }
      }
    }
    return bestMatch;
  }

  function lookupMagStats(slug, partName) {
    var WSTATS = getWstatsGlobal();
    if (!WSTATS || !slug || !partName) return null;
    var typeCode = getWeaponTypeCode(slug);
    if (!typeCode) return null;
    var table = WSTATS['Weapon_' + typeCode + '_Magazine_Init'];
    if (!table || !table.rows) return null;
    var mfr = getMfrFromSlug(slug);
    var prefix = mfr ? MFR_BARREL_PREFIX[mfr] : '';
    var keys = Object.keys(table.rows);
    for (var i = 0; i < keys.length; i++) {
      var rowName = keys[i];
      if (partName && rowName.toLowerCase().indexOf(String(partName).replace(/^part_/i, '').toLowerCase()) !== -1) return table.rows[rowName];
      if (prefix && rowName.indexOf(prefix) === 0) {
        var pIdx = partName ? String(partName).match(/(\d+)/) : null;
        var rIdx = rowName.match(/(\d+)/);
        if (pIdx && rIdx && pIdx[1] === rIdx[1]) return table.rows[rowName];
      }
    }
    return null;
  }

  function lookupMfrStats(slug) {
    var WSTATS = getWstatsGlobal();
    if (!WSTATS || !WSTATS.WeaponManufacturer_Init) return null;
    var mfr = getMfrFromSlug(slug);
    if (!mfr) return null;
    return WSTATS.WeaponManufacturer_Init.rows[mfr] || null;
  }

  /** Best-effort item slug for weapon init tables (Legit Builder passes slug explicitly). */
  function inferSlugHint() {
    try {
      if (typeof window.__STX_ITEM_SLUG === 'string' && window.__STX_ITEM_SLUG.trim()) return window.__STX_ITEM_SLUG.trim();
    } catch (_) {}
    try {
      var sd = window.selectedData;
      if (sd && typeof sd === 'object') {
        if (sd.itemSlug) return String(sd.itemSlug);
        if (sd.slug) return String(sd.slug);
        if (sd.item && sd.item.slug) return String(sd.item.slug);
      }
    } catch (_) {}
    for (var si = 0; si < BUILD_STATS_SLUG_SOURCE_IDS.length; si++) {
      var el = byId(BUILD_STATS_SLUG_SOURCE_IDS[si]);
      if (!el) continue;
      var t = fieldText(el).slice(0, 120000);
      var m = t.match(/\b([a-z]+_(?:pistol|shotgun|ar|smg|sniper|heavy_weapon)(?:_[a-z0-9]+)*)\b/i);
      if (m) return m[1].toLowerCase();
      var m2 = t.match(/(?:^|[\s"'{,])(slug|itemtype|item_type)\s*[:=]\s*['\"]?([a-z][a-z0-9_]*(?:_(?:pistol|shotgun|ar|smg|sniper|heavy_weapon)|_[a-z0-9_]+)*)/i);
      if (m2 && m2[2]) return m2[2].toLowerCase();
    }
    return '';
  }

  function wstatsObjectToLines(obj) {
    if (!obj || typeof obj !== 'object') return [];
    var keys = Object.keys(obj);
    var lines = [];
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      lines.push(k + ': ' + obj[k]);
    }
    return lines;
  }

  function tryBarrelMagWstats(part, slug) {
    if (!slug || !part || typeof part !== 'object') return null;
    var name = String(part.name || '').toLowerCase();
    var code = String(part.code || '').toLowerCase();
    if (name.indexOf('barrel') >= 0 || code.indexOf('barrel') >= 0) return lookupBarrelStats(slug, part.name || code);
    if (name.indexOf('mag') >= 0 || name.indexOf('magazine') >= 0 || code.indexOf('mag') >= 0) return lookupMagStats(slug, part.name || code);
    return null;
  }

  function parseNumericEffect(text) {
    var s = String(text || '').replace(/[xX\u00D7]/g, 'x').replace(/<[^>]*>/g, ' ').replace(/(\d),(\d)/g, '$1.$2');
    var m = s.match(/x\s*([0-9]*\.?[0-9]+)/i) || s.match(/([0-9]*\.?[0-9]+)\s*x\b/i);
    if (m) {
      var v = parseFloat(m[1]);
      return Number.isFinite(v) ? v : null;
    }
    var rePct = /([+-]?\s*\d+(?:\.\d+)?)\s*%/g;
    var best = null;
    var bestIdx = -1;
    var m2;
    while ((m2 = rePct.exec(s)) !== null) {
      var pct = parseFloat(String(m2[1]).replace(/\s+/g, ''));
      if (Number.isFinite(pct)) {
        var left = s.slice(Math.max(0, m2.index - 18), m2.index).toLowerCase();
        var right = s.slice(m2.index, Math.min(s.length, m2.index + 26)).toLowerCase();
        if (!/(chance|proc)/.test(left) && !/(chance|proc)/.test(right)) {
          if (m2.index > bestIdx) {
            bestIdx = m2.index;
            best = 1 + (pct / 100);
          }
        }
      }
    }
    if (best != null) return best;
    var mh = s.match(/([+-])\s*(\d+(?:\.\d+)?)/);
    if (mh) {
      var sign = mh[1] === '-' ? -1 : 1;
      var v = parseFloat(mh[2]);
      if (Number.isFinite(v)) return 1 + (sign * v / 100);
    }
    return null;
  }

  function classifyLine(line) {
    var l = String(line || '').toLowerCase();
    return {
      damage: /(damage|weapon damage|gun damage)/.test(l) && !/(crit|critical)/.test(l) && !/(element|status|dot|incendiary|\bfire\b(?!\s*rate)|burn|shock|corros|cryo|radiat)/.test(l),
      crit: /(crit|critical)/.test(l),
      elemental: /(element|status|dot|incendiary|\bfire\b(?!\s*rate)|burn|shock|corros|cryo|radiat|slag|poison)/.test(l),
      accuracy: /(accuracy|spread|precision|bloom)/.test(l),
      ads: /(ads|aim\s*down\s*sights|\baim\b|handling|recoil|stability|sway)/.test(l),
      firerate: /(fire\s*rate|rate\s*of\s*fire|\brof\b)/.test(l),
      reload_time: /(reload\s*time|time\s*to\s*reload|reload\b)/.test(l) && !/(reload\s*speed)/.test(l),
      reload_speed: /(reload\s*speed)/.test(l),
      ammo_mag: /(mag(azine)?(\s*(size|capacity))?|ammo\s*(capacity)?|clip\s*size)/.test(l),
      projectiles: /(projectile|projectiles|pellet|pellets)/.test(l)
    };
  }

  function walkSelectedDataRefs(sd, refList, baseFam) {
    if (!sd || typeof sd !== 'object') return;
    var seenWalk = new Set();
    function walk(v) {
      if (v == null) return;
      if (typeof v === 'string') { addRefsFromText(v, refList, { baseFamilyId: baseFam }); return; }
      if (typeof v !== 'object') return;
      if (seenWalk.has(v)) return;
      seenWalk.add(v);
      if (v.idRaw) addRefsFromToken(String(v.idRaw), refList, { baseFamilyId: baseFam });
      if (v.code) addRefsFromToken(String(v.code), refList, { baseFamilyId: baseFam });
      if (v.spawnCode) addRefsFromToken(String(v.spawnCode), refList, { baseFamilyId: baseFam });
      if (Array.isArray(v)) { for (var k = 0; k < v.length; k++) walk(v[k]); return; }
      var keys = Object.keys(v);
      for (var kk = 0; kk < keys.length; kk++) {
        if (keys[kk] === 'yaml' || keys[kk] === 'yamlText' || keys[kk] === 'raw' || keys[kk] === 'rawText') continue;
        walk(v[keys[kk]]);
      }
    }
    walk(sd);
  }

  function appendSimpleExtrasRefs(refList, baseFam) {
    try {
      var st = window.state || window.__STX_SIMPLE_STATE;
      if (!st || !Array.isArray(st.extras)) return;
      for (var ei = 0; ei < st.extras.length; ei++) {
        var ex = st.extras[ei];
        var tok = ex && typeof ex === 'object' ? String(ex.tok || '').trim() : String(ex || '').trim();
        if (tok) addRefsFromToken(tok, refList, { baseFamilyId: baseFam });
      }
    } catch (_) {}
  }

  /**
   * Collect part refs for stat accumulation — one active builder source only.
   * Keeps duplicate/stacked tokens within that serial; does not scan YAML/library paste.
   */
  function collectRefsListForStats() {
    var refList = [];
    var mode = resolveStatsSourceMode();
    var outEl = byId('outCode');
    var usedPrimaryText = false;

    if (mode === 'guided') {
      var guidedDeser = byId('guidedOutputDeserialized');
      var gTxt = fieldText(guidedDeser).slice(0, 200000);
      if (looksLikeDeserializedBuildText(gTxt)) {
        addRefsFromText(gTxt, refList, { baseFamilyId: inferBaseFamilyFromSerialText(gTxt) });
        usedPrimaryText = true;
      } else {
        var guidedSer = byId('guidedOutputSerial');
        var gSer = fieldText(guidedSer).slice(0, 200000);
        if (looksLikeDeserializedBuildText(gSer)) {
          addRefsFromText(gSer, refList, { baseFamilyId: inferBaseFamilyFromSerialText(gSer) });
          usedPrimaryText = true;
        }
      }
    }

    if (!usedPrimaryText) {
      var txtOut = fieldText(outEl).slice(0, 200000);
      if (looksLikeDeserializedBuildText(txtOut) || (txtOut && typeof window.stxOutCodeHasItemHeader === 'function' && window.stxOutCodeHasItemHeader())) {
        var baseFam = inferBaseFamilyFromSerialText(txtOut);
        addRefsFromText(txtOut, refList, { baseFamilyId: baseFam });
        appendSimpleExtrasRefs(refList, baseFam);
        usedPrimaryText = true;
      } else {
        var deserOut = byId('deserialized-code-output');
        var dTxt = fieldText(deserOut).slice(0, 200000);
        if (looksLikeDeserializedBuildText(dTxt)) {
          addRefsFromText(dTxt, refList, { baseFamilyId: inferBaseFamilyFromSerialText(dTxt) });
          appendSimpleExtrasRefs(refList, inferBaseFamilyFromSerialText(dTxt));
          usedPrimaryText = true;
        }
      }
    }

    /* Only walk selectedData when primary text did not already supply the build (avoids double-count). */
    if (!usedPrimaryText || !refList.length) {
      try {
        var sd = window.selectedData || null;
        if (sd && typeof sd === 'object') {
          var bfSd = outEl ? inferBaseFamilyFromSerialText(fieldText(outEl)) : null;
          walkSelectedDataRefs(sd, refList, bfSd);
        }
      } catch (_) {}
      if (!refList.length && mode === 'simple') {
        appendSimpleExtrasRefs(refList, null);
      }
    }

    if (!refList.length) return null;
    var resolved = [];
    for (var r = 0; r < refList.length; r++) {
      try {
        var p = resolvePart(refList[r]);
        resolved.push(p || refList[r]);
      } catch (_) {
        resolved.push(refList[r]);
      }
    }
    return { refList: refList, parts: resolved };
  }

  function dedupePartsList(parts) {
    var seen = new Set();
    var deduped = [];
    for (var d = 0; d < parts.length; d++) {
      var p = parts[d];
      var k;
      if (p && typeof p === 'object') {
        k = String((p.idRaw || p.idraw || p.partRef || p.code || '') || '').trim();
        if (!k && p.family != null && p.id != null) k = String(p.family) + ':' + String(p.id);
        if (!k) k = String(p.partRef || p.id || p.name || '');
      } else {
        k = String(p);
      }
      if (seen.has(k)) continue;
      seen.add(k);
      deduped.push(p);
    }
    return deduped;
  }

  /** Unique parts for full-stats panel display (stacked duplicates collapsed). */
  function collectRefsAndDedupedParts() {
    var col = collectRefsListForStats();
    if (!col) return null;
    return { refList: col.refList, deduped: dedupePartsList(col.parts) };
  }

  function partDisplayName(part) {
    if (!part || typeof part !== 'object') return String(part);
    return String(part.name || part.code || part.idRaw || part.spawnCode || part.partRef || '').trim() || 'Part';
  }

  var STAT_DISPLAY_BUCKET_LABELS = {
    damage: 'Damage', crit: 'Crit', elemental: 'Elemental', accuracy: 'Accuracy',
    ads: 'ADS/Handling', firerate: 'Fire Rate', reload_time: 'Reload Time',
    reload_speed: 'Reload Speed', ammo_mag: 'Ammo/Mag', projectiles: 'Projectiles', misc: 'Misc'
  };

  function isScaleStatField(field) {
    return /_scale$/i.test(String(field || ''));
  }

  /** User-facing cheat sheet — standard game scale multipliers. */
  var SCALE_MULT_LEGEND_SHORT =
    '×1.0000 = normal · ×1.1000 = +10% · ×1.2500 = +25% · ×1.5000 = +50% · ×2.0000 = +100%. ' +
    'Shown % = (× − 1) × 100 vs a neutral (×1) part.';

  function scalePctVsNormal(effectiveMult) {
    if (!Number.isFinite(effectiveMult)) return null;
    return (effectiveMult - 1) * 100;
  }

  function formatScalePctSuffix(pct, opts) {
    opts = opts || {};
    if (!Number.isFinite(pct) || Math.abs(pct) > 500) return '';
    var sign = pct >= 0 ? '+' : '';
    var core = sign + pct.toFixed(1) + '%';
    if (opts.invertedBenefit) return core + ' better (lower × is better for this stat)';
    if (opts.fractionalDamageLayer) return core + ' vs normal (fractional damage layer; effective ×' + opts.effectiveMult.toFixed(4) + ')';
    return core + ' vs normal';
  }

  /** Display multiplier for one PARTS_STATS_DATA row (matches bucket accumulation rules). */
  function statRowToDisplayMult(s) {
    if (!s || typeof s !== 'object') return null;
    var comb = String(s.combine || '').trim().toLowerCase();
    if (comb === 'value') return null;
    var val = Number(s.stat_value);
    if (!Number.isFinite(val)) return null;
    var mult = 1;
    if (comb === 'mul') {
      mult = val;
      var dmgFix = partsStatsDamageScaleMulToDisplayMult(s.stat_field, comb, val);
      if (dmgFix != null) mult = dmgFix;
    } else if (comb === 'add' || !comb) {
      mult = 1 + val;
    } else {
      return null;
    }
    if (s.invert && mult !== 0) mult = 1 / mult;
    return mult;
  }

  /**
   * Human-readable stat line: scale fields as ×1.0500, bonuses as +20% Damage.
   * Raw engine offsets (combine value) show as offsets, not bogus percentages.
   */
  function formatPartStatRowForDisplay(s) {
    if (!s || typeof s !== 'object') return '';
    if (s.description && String(s.description).trim()) {
      return String(s.description).trim();
    }
    var sf = s.stat_field != null ? String(s.stat_field) : '';
    var bucket = s.bucket != null ? String(s.bucket) : '';
    var comb = String(s.combine || '').trim().toLowerCase();
    var val = Number(s.stat_value);
    var lbl = STAT_DISPLAY_BUCKET_LABELS[bucket] || bucket || sf;

    if (!Number.isFinite(val)) {
      return sf ? (sf + ': ' + s.stat_value) : String(s.stat_value);
    }

    if (comb === 'value') {
      if (isScaleStatField(sf)) {
        return lbl + ': ×' + val.toFixed(4) + ' scale';
      }
      return sf + ': ' + val + ' (engine offset)';
    }

    if (comb === 'mul' && isScaleStatField(sf)) {
      var dispMult = scaleRowDisplayMultiplier(s);
      var sfLow = sf.toLowerCase();
      var invertedBenefit = !!WSTAT_KEYS_INVERT_SCALE_FOR_BENEFIT[sfLow];
      var fractionalDmg = sfLow === 'damage_scale' && val > 0 && val < 0.5;
      var line = lbl + ': ×' + val.toFixed(4);
      if (!fractionalDmg) line += ' scale';
      if (dispMult != null) {
        var pctS = scalePctVsNormal(dispMult);
        var suffix = formatScalePctSuffix(pctS, {
          invertedBenefit: invertedBenefit && !fractionalDmg,
          fractionalDamageLayer: fractionalDmg,
          effectiveMult: dispMult
        });
        if (suffix) line += ' (' + suffix + ')';
      }
      return line;
    }

    var mult = statRowToDisplayMult(s);
    if (mult == null) return sf ? (sf + ': ' + val) : String(val);
    var pct = (mult - 1) * 100;
    if (Math.abs(pct) > 500) {
      return lbl + ': ×' + mult.toFixed(4) + ' scale';
    }
    return (pct >= 0 ? '+' : '') + pct.toFixed(1) + '% ' + lbl;
  }

  function formatExcelStatRow(s) {
    return formatPartStatRowForDisplay(s);
  }

  var SUMMARY_BUCKET_ORDER = ['damage', 'crit', 'firerate', 'ammo_mag', 'reload_speed', 'reload_time', 'accuracy', 'splash', 'elemental', 'ads', 'projectiles'];

  /** Compact stats for inspector rows / tooltips (meaningful buckets only). */
  function formatPartStatsSummary(part, maxLines) {
    maxLines = maxLines == null ? 3 : Math.max(1, maxLines);
    var excelStats = null;
    try { excelStats = getExcelStatsForPart(part); } catch (_) {}
    if (!excelStats || !excelStats.length) return '';
    excelStats = dedupeExcelStatRows(excelStats);
    var picked = [];
    var used = new Set();
    function tryPick(bucket) {
      for (var i = 0; i < excelStats.length; i++) {
        var s = excelStats[i];
        if (!s || used.has(i)) continue;
        if (String(s.bucket || '') !== bucket) continue;
        if (String(s.combine || '').toLowerCase() === 'value' && !isScaleStatField(s.stat_field)) continue;
        var line = formatPartStatRowForDisplay(s);
        if (!line) continue;
        used.add(i);
        picked.push(line);
        return true;
      }
      return false;
    }
    for (var bi = 0; bi < SUMMARY_BUCKET_ORDER.length && picked.length < maxLines; bi++) {
      tryPick(SUMMARY_BUCKET_ORDER[bi]);
    }
    for (var j = 0; j < excelStats.length && picked.length < maxLines; j++) {
      if (used.has(j)) continue;
      var s2 = excelStats[j];
      if (String(s2.combine || '').toLowerCase() === 'value' && !isScaleStatField(s2.stat_field)) continue;
      var line2 = formatPartStatRowForDisplay(s2);
      if (line2) picked.push(line2);
    }
    return picked.slice(0, maxLines).join(', ');
  }

  /**
   * Same resolution order as the full-stats panel: PARTS_STATS_DATA → barrel/mag init → embedded text.
   * @returns {{ source: string, lines: string[], excelRows: Array|null }}
   */
  function computeFullStatLinesForPart(part, slug) {
    var excelStats = null;
    try {
      excelStats = getExcelStatsForPart(part);
    } catch (_) {}
    var source = 'embedded stat text';
    var lines = [];
    var excelRows = null;
    if (excelStats && excelStats.length) {
      source = 'PARTS_STATS_DATA';
      excelRows = excelStats;
      for (var j = 0; j < excelStats.length; j++) {
        lines.push(formatExcelStatRow(excelStats[j]));
      }
    } else if (slug) {
      var wRow = tryBarrelMagWstats(part, slug);
      if (wRow) {
        source = 'WEAPON_STATS_DATA (barrel/mag init)';
        lines = wstatsObjectToLines(wRow);
      }
    }
    if (!lines.length) {
      var raw = '';
      try {
        raw = displayStatsFor(part) || '';
      } catch (_) {}
      if (raw) {
        lines = raw.split(/(?:\r?\n|\r|;|\u2022|\u25AA|\u25CF)+/).map(function (t) { return t.trim(); }).filter(Boolean);
        if (source === 'embedded stat text' && lines.length) source = 'Item stats';
      }
    }
    return { source: source, lines: lines, excelRows: excelRows };
  }

  function excelRowImpactScore(s) {
    if (!s || typeof s !== 'object') return 0;
    var comb = String(s.combine || '').trim();
    if (comb === 'value') return -1;
    var val = Number(s.stat_value);
    if (!Number.isFinite(val)) return 0;
    if (comb === 'mul') {
      if (val === 0) return 0;
      return Math.abs(Math.log(Math.max(1e-9, Math.abs(val))));
    }
    return Math.abs(val);
  }

  function wstatLineImpactScore(line) {
    var m = String(line || '').match(/^([^:]+):\s*(.+)$/);
    if (!m) return textLineImpactScore(line);
    var key = m[1].trim();
    if (/_value$/i.test(key)) return -1;
    var v = parseFloat(String(m[2]).trim().replace(/,/g, ''));
    if (!Number.isFinite(v) || v === 0) return 0;
    if (/_add$/i.test(key)) return Math.abs(v);
    if (/_scale$/i.test(key)) {
      if (WSTAT_KEYS_INVERT_SCALE_FOR_BENEFIT[key]) {
        if (v === 0) return 0;
        return Math.abs(Math.log(Math.max(1e-9, 1 / Math.abs(v))));
      }
      return Math.abs(Math.log(Math.max(1e-9, Math.abs(v))));
    }
    return Math.abs(v);
  }

  function textLineImpactScore(line) {
    var mult = parseNumericEffect(line);
    if (mult != null && Number.isFinite(mult) && mult > 0) {
      return Math.abs(Math.log(Math.max(1e-9, mult)));
    }
    var s = String(line || '');
    var best = 0;
    var re = /([+-]?\d+(?:\.\d+)?)\s*%/g;
    var mm;
    while ((mm = re.exec(s)) !== null) {
      var left = s.slice(Math.max(0, mm.index - 18), mm.index).toLowerCase();
      var right = s.slice(mm.index, Math.min(s.length, mm.index + 26)).toLowerCase();
      if (/(chance|proc)/.test(left) || /(chance|proc)/.test(right)) continue;
      var x = Math.abs(parseFloat(String(mm[1]).replace(/\s+/g, '')));
      if (Number.isFinite(x) && x > best) best = x;
    }
    return best;
  }

  /** Largest / most multiplicative changes first; stable tie-break on original index. */
  function sortFullStatLinesByImpact(lines, source, excelRows) {
    if (!lines || lines.length <= 1) return lines.slice();
    var decorated = [];
    for (var i = 0; i < lines.length; i++) {
      var sc;
      if (excelRows && excelRows[i]) {
        sc = excelRowImpactScore(excelRows[i]);
      } else if (String(source || '').indexOf('WEAPON_STATS') >= 0) {
        sc = wstatLineImpactScore(lines[i]);
      } else {
        sc = textLineImpactScore(lines[i]);
      }
      decorated.push({ line: lines[i], score: sc, idx: i });
    }
    decorated.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.idx - b.idx;
    });
    return decorated.map(function (d) { return d.line; });
  }

  /**
   * One entry for Guided slot previews / tooling. slugHint may be '' to use inferSlugHint().
   * @returns {{ name: string, source: string, lines: string[] }}
   */
  function getFullStatLinesForPart(part, slugHint) {
    var slug = (slugHint != null && String(slugHint).trim() !== '') ? String(slugHint).trim() : inferSlugHint();
    var name = partDisplayName(part);
    var pack = computeFullStatLinesForPart(part, slug);
    var lines = sortFullStatLinesByImpact(pack.lines, pack.source, pack.excelRows);
    return { name: name, source: pack.source, lines: lines };
  }

  /** Per-part lines for the full-stats panel (PARTS_STATS_DATA → weapon init tables → embedded text). Matches Legit Builder priority where possible. */
  function getFullStatsBreakdown() {
    var col = collectRefsAndDedupedParts();
    if (!col || !col.deduped.length) {
      return { entries: [], message: 'No part refs found. Import code, use Guided Builder, or paste serials to see full stat lines.' };
    }
    var slug = inferSlugHint();
    var entries = [];
    for (var i = 0; i < col.deduped.length; i++) {
      var part = col.deduped[i];
      var name = partDisplayName(part);
      var pack = computeFullStatLinesForPart(part, slug);
      var lines = sortFullStatLinesByImpact(pack.lines, pack.source, pack.excelRows) || [];
      lines = lines.filter(function (ln) { return ln != null && String(ln).trim() !== ''; }).map(function (ln) { return String(ln); });
      if (!lines.length) {
        var raw = '';
        try { raw = String(displayStatsFor(part) || '').trim(); } catch (_) {}
        if (raw) lines = [raw];
        else {
          var tok = '';
          try { tok = String((part && (part.idRaw || part.idraw || part.code || part.spawnCode)) || '').trim(); } catch (_) {}
          lines = [tok ? ('No parsed stat lines (' + tok + ')') : 'No parsed stat lines'];
        }
      }
      entries.push({ name: name, source: pack.source, lines: lines });
    }
    if (slug) {
      var mfr = lookupMfrStats(slug);
      if (mfr && Object.keys(mfr).length) {
        var mlines = wstatsObjectToLines(mfr) || [];
        mlines = mlines.filter(function (ln) { return ln != null && String(ln).trim() !== ''; }).map(function (ln) { return String(ln); });
        if (!mlines.length) mlines = ['No parsed manufacturer stat lines'];
        mlines = sortFullStatLinesByImpact(mlines, 'WEAPON_STATS_DATA (manufacturer init)', null);
        entries.unshift({
          name: 'Manufacturer (' + (getMfrFromSlug(slug) || slug) + ')',
          source: 'WEAPON_STATS_DATA (manufacturer init)',
          lines: mlines
        });
      }
    }
    return { entries: entries, slugHint: slug || null };
  }

  function applyBuildStatContribution(bucket, mult, contrib) {
    if (!bucket) return bucket;
    var c = contrib || {};
    if (!bucket.fields) bucket.fields = Object.create(null);
    if (!Array.isArray(bucket.values)) bucket.values = [];
    if (!Array.isArray(bucket.contributions)) bucket.contributions = [];
    if (!Number.isFinite(Number(bucket.mult))) bucket.mult = 1;
    if (!Number.isFinite(Number(bucket.add))) bucket.add = 0;
    bucket.hits = Number(bucket.hits || 0) + 1;
    bucket.nonNumeric = Number(bucket.nonNumeric || 0);
    var combine = String(c.combine || 'mul').toLowerCase();
    var fieldKey = String(c.statField || 'effect').toLowerCase();
    var f = bucket.fields[fieldKey];
    if (!f) {
      f = bucket.fields[fieldKey] = {
        field: fieldKey,
        mul: 1,
        add: 0,
        offsets: [],
        alternatives: [],
        invalidValues: [],
        mulHits: 0,
        addHits: 0,
        valueHits: 0,
        ambiguousHits: 0,
        invalidHits: 0,
        hits: 0,
        invertedBenefit: false
      };
    }
    f.hits++;
    if (c.invertedBenefit) f.invertedBenefit = true;
    if (combine === 'alternative') {
      var alternatives = Array.isArray(c.alternatives) ? c.alternatives : [];
      for (var ai = 0; ai < alternatives.length; ai++) {
        var av = Number(alternatives[ai]);
        if (Number.isFinite(av) && f.alternatives.indexOf(av) < 0) f.alternatives.push(av);
      }
      f.ambiguousHits++;
    } else if (combine === 'invalid') {
      var invalidValue = Number(c.invalidValue);
      if (Number.isFinite(invalidValue)) f.invalidValues.push(invalidValue);
      f.invalidHits++;
    } else if (combine === 'value') {
      var rawOffset = Number(c.rawValue);
      if (Number.isFinite(rawOffset)) {
        bucket.values.push(rawOffset);
        f.offsets.push(rawOffset);
        f.valueHits++;
      } else {
        bucket.nonNumeric++;
      }
    } else if (combine === 'add') {
      var rawAdd = Number(c.rawValue);
      if (Number.isFinite(rawAdd)) {
        bucket.add += rawAdd;
        f.add += rawAdd;
        f.addHits++;
      } else {
        bucket.nonNumeric++;
      }
    } else if (Number.isFinite(Number(mult)) && Number(mult) !== 0) {
      bucket.mult *= Number(mult);
      f.mul *= Number(mult);
      f.mulHits++;
    } else {
      bucket.nonNumeric++;
    }
    bucket.contributions.push(c);
    return bucket;
  }

  /**
   * Convert one operation-aware bucket into stable per-field effects.
   * Additive rows are summed, multiplicative rows are multiplied, and raw
   * engine value rows remain offsets. Different stat fields are never folded
   * into one pretend final number.
   */
  function summarizeBuildStatBucket(bucket) {
    if (!bucket || !bucket.fields) return [];
    var out = [];
    var keys = Object.keys(bucket.fields);
    for (var i = 0; i < keys.length; i++) {
      var f = bucket.fields[keys[i]];
      if (!f) continue;
      var offsets = Array.isArray(f.offsets) ? f.offsets.slice() : [];
      var alternatives = Array.isArray(f.alternatives) ? f.alternatives.slice().sort(function (a, b) { return a - b; }) : [];
      var invalidValues = Array.isArray(f.invalidValues) ? f.invalidValues.slice() : [];
      var offsetTotal = 0;
      for (var oi = 0; oi < offsets.length; oi++) {
        var ov = Number(offsets[oi]);
        if (Number.isFinite(ov)) offsetTotal += ov;
      }
      out.push({
        field: f.field,
        mul: Number.isFinite(f.mul) ? f.mul : 1,
        add: Number.isFinite(f.add) ? f.add : 0,
        offsetTotal: offsetTotal,
        offsetCount: offsets.length,
        alternatives: alternatives,
        invalidValues: invalidValues,
        mulHits: Number(f.mulHits || 0),
        addHits: Number(f.addHits || 0),
        valueHits: Number(f.valueHits || 0),
        ambiguousHits: Number(f.ambiguousHits || 0),
        invalidHits: Number(f.invalidHits || 0),
        hits: Number(f.hits || 0),
        invertedBenefit: !!f.invertedBenefit
      });
    }
    out.sort(function (a, b) {
      if (b.hits !== a.hits) return b.hits - a.hits;
      return String(a.field).localeCompare(String(b.field));
    });
    return out;
  }

  function accumulateFromSelected() {
    var col = collectRefsListForStats();
    if (!col || !col.parts.length) return null;
    var deduped = col.parts;
    var slug = inferSlugHint();
    var pname = function (part) { return partDisplayName(part); };

    var buckets = {
      damage: { mult: 1, add: 0, values: [], fields: Object.create(null), hits: 0, nonNumeric: 0, contributions: [] },
      crit: { mult: 1, add: 0, values: [], fields: Object.create(null), hits: 0, nonNumeric: 0, contributions: [] },
      elemental: { mult: 1, add: 0, values: [], fields: Object.create(null), hits: 0, nonNumeric: 0, contributions: [] },
      accuracy: { mult: 1, add: 0, values: [], fields: Object.create(null), hits: 0, nonNumeric: 0, contributions: [] },
      ads: { mult: 1, add: 0, values: [], fields: Object.create(null), hits: 0, nonNumeric: 0, contributions: [] },
      firerate: { mult: 1, add: 0, values: [], fields: Object.create(null), hits: 0, nonNumeric: 0, contributions: [] },
      reload_time: { mult: 1, add: 0, values: [], fields: Object.create(null), hits: 0, nonNumeric: 0, contributions: [] },
      reload_speed: { mult: 1, add: 0, values: [], fields: Object.create(null), hits: 0, nonNumeric: 0, contributions: [] },
      ammo_mag: { mult: 1, add: 0, values: [], fields: Object.create(null), hits: 0, nonNumeric: 0, contributions: [] },
      projectiles: { mult: 1, add: 0, values: [], fields: Object.create(null), hits: 0, nonNumeric: 0, contributions: [] }
    };

    function record(key, line, mult, contrib) {
      var b = buckets[key];
      if (!b) return;
      var c = contrib || {};
      if (!c.statField) c.statField = key || 'effect';
      applyBuildStatContribution(b, mult, c);
    }

    for (var idx = 0; idx < deduped.length; idx++) {
      var part = deduped[idx];
      var pl = pname(part);
      var excelStats = null;
      try {
        excelStats = getExcelStatsForPart(part);
      } catch (_) {}
      if (excelStats && excelStats.length) {
        applyExcelStatsToBuckets(excelStats, buckets, record, pl);
        continue;
      }
      var wRow = slug ? tryBarrelMagWstats(part, slug) : null;
      if (wRow) {
        applyWstatsObjectToBuckets(wRow, buckets, record, pl);
        continue;
      }
      var raw = '';
      try {
        raw = displayStatsFor(part) || '';
      } catch (_) {}
      if (!raw) continue;

      var lines = raw.split(/(?:\r?\n|\r|;|\u2022|\u25AA|\u25CF)+/).map(function (t) { return t.trim(); }).filter(Boolean);
      for (var li = 0; li < lines.length; li++) {
        var line = lines[li];
        var c = classifyLine(line);
        var mult = parseNumericEffect(line);
        var cb = { part: pl, source: 'parsed text', detail: line, combine: 'mul', statField: 'text_effect', multApplied: mult };
        if (c.damage) record('damage', line, mult, cb);
        if (c.crit) record('crit', line, mult, cb);
        if (c.elemental) record('elemental', line, mult, cb);
        if (c.accuracy) record('accuracy', line, mult, cb);
        if (c.ads) record('ads', line, mult, cb);
        if (c.firerate) record('firerate', line, mult, cb);
        if (c.reload_time) record('reload_time', line, mult, cb);
        if (c.reload_speed) record('reload_speed', line, mult, cb);
        if (c.ammo_mag) record('ammo_mag', line, mult, cb);
        if (c.projectiles) record('projectiles', line, mult, cb);
      }
    }

    if (slug) {
      var mfr = lookupMfrStats(slug);
      if (mfr) applyWstatsObjectToBuckets(mfr, buckets, record, 'Manufacturer');
    }

    var detected = 0;
    var keys = Object.keys(buckets);
    for (var ki = 0; ki < keys.length; ki++) {
      var bk = buckets[keys[ki]];
      if (bk && bk.hits) {
        detected += Number(bk.hits) || 0;
        bk.effects = summarizeBuildStatBucket(bk);
      }
    }
    buckets.detectedParts = detected;

    return buckets;
  }

  function getBuildStatsDebugInfo() {
    var col = collectRefsListForStats();
    var arr = col && col.refList ? col.refList.slice() : [];
    var resolved = [];
    var withStats = [];
    var withoutStats = [];
    for (var r = 0; r < arr.length; r++) {
      try {
        var p = resolvePart(arr[r]);
        var part = p || arr[r];
        resolved.push({ ref: arr[r], part: part });
        var raw = displayStatsFor(part) || '';
        if (raw && raw.trim()) {
          withStats.push({ ref: arr[r], part: part, stats: raw });
        } else {
          withoutStats.push({ ref: arr[r], part: part });
        }
      } catch (_) {
        resolved.push({ ref: arr[r], part: arr[r] });
        withoutStats.push({ ref: arr[r], part: arr[r] });
      }
    }
    return { refs: arr, resolved: resolved, withStats: withStats, withoutStats: withoutStats };
  }

  window.accumulateFromSelected = accumulateFromSelected;
  window.displayStatsFor = displayStatsFor;
  window.getBuildStatsDebugInfo = getBuildStatsDebugInfo;
  window.getFullStatsBreakdown = getFullStatsBreakdown;
  window.applyBuildStatContribution = applyBuildStatContribution;
  window.summarizeBuildStatBucket = summarizeBuildStatBucket;
  window.getFullStatLinesForPart = getFullStatLinesForPart;
  window.sortFullStatLinesByImpact = sortFullStatLinesByImpact;
  window.statRowToDisplayMult = statRowToDisplayMult;
  window.formatPartStatRowForDisplay = formatPartStatRowForDisplay;
  window.formatPartStatsSummary = formatPartStatsSummary;
  window.SCALE_MULT_LEGEND_SHORT = SCALE_MULT_LEGEND_SHORT;

  var __ccStatsTriggerTimer = 0;
  function isBuildStatsActive() {
    var sec = document.getElementById('rebuildBuildStatsSection');
    if (sec && sec.open) return true;
    var guided = document.getElementById('ccGuidedFullStatsPreview');
    if (guided && guided.checked) return true;
    var gr = document.getElementById('godrollShowFullStatsToggle');
    if (gr && gr.checked) return true;
    return false;
  }
  function triggerRefresh() {
    if (!isBuildStatsActive()) return;
    if (__ccStatsTriggerTimer) clearTimeout(__ccStatsTriggerTimer);
    __ccStatsTriggerTimer = setTimeout(function () {
      __ccStatsTriggerTimer = 0;
      var run = function () {
        try {
          if (typeof window.refreshBuildStatsCore === 'function') window.refreshBuildStatsCore();
        } catch (_) {}
      };
      if (typeof window.__ccEnsureBuildStatsData === 'function' && (!window.PARTS_STATS_DATA || typeof window.WEAPON_STATS_DATA === 'undefined')) {
        window.__ccEnsureBuildStatsData().then(run);
      } else if (typeof window.__ccEnsurePartsStatsData === 'function' && !window.PARTS_STATS_DATA) {
        window.__ccEnsurePartsStatsData().then(run);
      } else {
        run();
      }
    }, 300);
  }

  try { window.__ccRefreshBuildStatsAfterStatsLoad = triggerRefresh; } catch (_) {}

  function scheduleInitialBuildStatsRefresh() {
    var run = function () {
      if (typeof window.stxScheduleIdle === 'function') {
        window.stxScheduleIdle(triggerRefresh, 1200);
      } else {
        setTimeout(triggerRefresh, 700);
      }
    };
    if (typeof window.stxWhenSplashDismissed === 'function') {
      window.stxWhenSplashDismissed(run);
    } else {
      run();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleInitialBuildStatsRefresh);
  } else {
    scheduleInitialBuildStatsRefresh();
  }

  document.addEventListener('change', function (ev) {
    var t = ev && ev.target;
    if (t && t.tagName === 'SELECT') setTimeout(triggerRefresh, 80);
  }, true);

  setTimeout(function () {
    try {
      if (typeof window.refreshOutputs === 'function') {
        var orig = window.refreshOutputs;
        if (orig && !orig.__buildStatsWrapped) {
          window.refreshOutputs = function () {
            var r = orig.apply(this, arguments);
            setTimeout(triggerRefresh, 50);
            return r;
          };
          window.refreshOutputs.__buildStatsWrapped = true;
        }
      }
      if (typeof window.refreshGuidedOutput === 'function') {
        var origGuided = window.refreshGuidedOutput;
        if (origGuided && !origGuided.__buildStatsWrapped) {
          window.refreshGuidedOutput = function () {
            var r = origGuided.apply(this, arguments);
            setTimeout(triggerRefresh, 50);
            return r;
          };
          window.refreshGuidedOutput.__buildStatsWrapped = true;
        }
      }
      var bindIds = BUILD_STATS_SLUG_SOURCE_IDS;
      for (var bi = 0; bi < bindIds.length; bi++) {
        var elB = byId(bindIds[bi]);
        if (elB && !elB.__buildStatsInputBound) {
          elB.addEventListener('input', function () { setTimeout(triggerRefresh, 80); });
          elB.addEventListener('change', function () { setTimeout(triggerRefresh, 80); });
          elB.__buildStatsInputBound = true;
        }
      }
    } catch (_) {}
  }, 500);
})();
