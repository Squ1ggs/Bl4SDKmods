/**
 * rebuild-presets-random.js - Presets, random build, tools, build stats
 */
(function(){
  "use strict";
  function byId(id){ return document.getElementById(id); }
  function loadPresetCategories(){
    var sel = byId("presetCategorySelect");
    if (!sel) return;
    if (typeof window.populatePresetCategories === 'function') window.populatePresetCategories(sel);
  }
  function loadPresetParts(){
    var catSel = byId("presetCategorySelect");
    var partSel = byId("presetPartSelect");
    var moreSel = byId("presetMorePartSelect");
    if (!catSel || !partSel) return;
    if (typeof window.populatePresetParts === 'function') window.populatePresetParts(catSel, partSel, null, moreSel);
  }
  /** Only bare {n} tokens participate in legacy "rarity slot" replacement — not full {fam:id} parts. */
  function isRarityTokenBootstrap(t) {
    return /^\{\s*\d+\s*\}$/.test(String(t || "").trim());
  }

  function getBaseFamilyIdFromSerial(serial) {
    try {
      var s = String(serial || "").trim();
      // Handle Base85
      if (s.indexOf('||') < 0 && s.indexOf('{') < 0 && s.length > 20 && typeof window.deserializeBase85 === 'function') {
        var deser = window.deserializeBase85(s);
        if (deser && typeof deser === 'string') s = deser.trim();
      }
      var dbl = s.indexOf("||");
      var prefix = dbl >= 0 ? s.slice(0, dbl).trim() : s.trim();
      var m = prefix.match(/^\s*(\d+)\s*[,\|]/);
      if (!m) m = prefix.match(/^\s*(\d+)/);
      return m ? Number(m[1]) : null;
    } catch (_) { return null; }
  }

  function normalizeBracedIdToken(token) {
    // Accept "22:72" / "95" too; always return something like "{22:72}" or "{95}".
    var t = String(token || "").trim();
    t = t.replace(/^"+|"+$/g, '');
    if (/^\d+:\d+$/.test(t)) return '{' + t + '}';
    if (/^\d+$/.test(t)) return '{' + t + '}';
    return t;
  }

  function normalizeIdTokenForBaseFamily(token, baseFamilyId) {
    var t = normalizeBracedIdToken(token);
    // Preserve stacked skin mixes `{fam:[id1 id2]}` — never collapse to bare `{id}`.
    if (/^\{\s*\d+\s*:\s*\[/.test(t)) return t;
    var m = t.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
    if (!m) return t; // already singular like "{95}" or non-matching
    var fam = Number(m[1]);
    var id = Number(m[2]);
    if (baseFamilyId != null && fam === baseFamilyId) {
      // Same family as the item header: allow singular "{95}" form.
      return '{' + id + '}';
    }
    return '{' + fam + ':' + id + '}';
  }

  function addPresetPart(){
    var partSel = byId("presetPartSelect");
    var moreSel = byId("presetMorePartSelect");
    var qty = byId("presetQuantity");
    var code = (typeof window.resolveActivePresetPartValue === 'function')
      ? window.resolveActivePresetPartValue(partSel, moreSel)
      : String((partSel && partSel.value) || (moreSel && moreSel.value) || "").trim();
    if (!code) return;
    if (typeof window.resolvePresetTokenForOutput === "function") {
      code = window.resolvePresetTokenForOutput(code) || code;
    }
    code = normalizeBracedIdToken(code);
    var n = Math.max(1, parseInt((qty && qty.value) || "1", 10) || 1);
    if (typeof window.stxAppendPresetToActiveBuilder === "function" && window.stxAppendPresetToActiveBuilder(code, { quantity: n })) {
      try { if (typeof window.refreshBuildStatsCore === "function") window.refreshBuildStatsCore(); } catch(_){}
      return;
    }
    var out = (typeof window.getCodeAppendOutputEl === "function") ? window.getCodeAppendOutputEl() : byId("outCode");
    if (!out) return;
    if (out.id === "guidedOutputDeserialized" && typeof window.appendToOutCodeGuided === "function") {
      for (var qi = 0; qi < n; qi++) window.appendToOutCodeGuided(code);
      try { window.__CC_LAST_CODE_TARGET = "guided"; } catch (_) {}
      return;
    }
    /* Simple Builder: merge presets into state.extras — textarea + refreshOutputs() drops tail-only edits. */
    if (out.id === "outCode" && typeof window.stxAppendQuickPresetNumericTokens === "function") {
      code = normalizeBracedIdToken(code);
      var serialSb = (out.value || "").trim();
      var baseFamSb = getBaseFamilyIdFromSerial(serialSb);
      var piecesSb = [];
      for (var isb = 0; isb < n; isb++) piecesSb.push(code);
      var normPiecesSb = piecesSb;
      if (typeof window.normalizeIdTokensForBaseFamily === "function" && baseFamSb != null) {
        normPiecesSb = window.normalizeIdTokensForBaseFamily(piecesSb, baseFamSb);
      } else {
        for (var jsb = 0; jsb < piecesSb.length; jsb++) {
          normPiecesSb[jsb] = normalizeIdTokenForBaseFamily(piecesSb[jsb], baseFamSb);
        }
      }
      try { window.__CC_LAST_CODE_TARGET = "simple"; } catch (_) {}
      if (window.stxAppendQuickPresetNumericTokens(normPiecesSb, { replaceBareQuickPresets: false })) {
        try { if (typeof window.refreshBuildStatsCore === 'function') window.refreshBuildStatsCore(); } catch(_){}
        return;
      }
    }
    var serial = (out.value || "").trim();
    var dbl = serial.indexOf("||");
    var tail = dbl >= 0 ? serial.slice(dbl + 2) : "";
    var baseFamilyId = getBaseFamilyIdFromSerial(serial);
    var tokens = (tail.match(/\{[^}]+\}|\"[^\"]+\"|\S+/g) || []);
    if (isRarityTokenBootstrap(code)) {
      tokens = tokens.filter(function(t){ return !isRarityTokenBootstrap(t); });
    }
    for (var i = 0; i < n; i++) tokens.push(code);
    if (typeof window.normalizeIdTokensForBaseFamily === "function" && baseFamilyId != null) {
      // Use compactSameFamily: true (default) so same-family parts use {id} and others use {fam:id}
      tokens = window.normalizeIdTokensForBaseFamily(tokens, baseFamilyId);
    } else {
      for (var j = 0; j < tokens.length; j++) {
        tokens[j] = normalizeIdTokenForBaseFamily(tokens[j], baseFamilyId);
      }
    }
    var newTail = tokens.join(" ");
    var newSerial = dbl >= 0 ? serial.slice(0, dbl + 2) + newTail : (serial ? serial + " || " + newTail : "|| " + newTail);
    out.value = newSerial;
    try { window.__CC_LAST_CODE_TARGET = (out.id === "outCode") ? "simple" : "guided"; } catch (_) {}
    try {
      if (out.id === "outCode") { if (window.refreshOutputs) window.refreshOutputs(); }
      else {
        if (window.refreshGuidedOutputPreview) window.refreshGuidedOutputPreview();
        if (window.syncFloatingOutput) window.syncFloatingOutput(true);
      }
    } catch (_) {}
  }
  function appendToOutCode(tok, forceTarget, replaceRarity) {
    if (!forceTarget && typeof window.stxAppendPresetToActiveBuilder === "function") {
      if (window.stxAppendPresetToActiveBuilder(tok, { quantity: 1 })) return;
    }
    var out = forceTarget || ((typeof window.getCodeAppendOutputEl === "function") ? window.getCodeAppendOutputEl() : byId("outCode"));
    if (!out) return;
    if (out.id === "guidedOutputDeserialized" && typeof window.appendToOutCodeGuided === "function") {
      window.appendToOutCodeGuided(tok, forceTarget, replaceRarity);
      return;
    }
    /* Simple Builder: tail tokens must hit state.extras — plain textarea append is overwritten by refreshOutputs(). */
    if (out.id === "outCode" && typeof window.stxAppendPartTokenViaExtras === "function") {
      var tNorm = normalizeBracedIdToken(tok);
      if (window.stxAppendPartTokenViaExtras(tNorm, { type: "quickPreset" })) return;
    }
    if (out.id === "outCode" && typeof window.stxAppendTailTokenViaExtras === "function") {
      var tNormLegacy = normalizeBracedIdToken(tok);
      if (window.stxAppendTailTokenViaExtras(tNormLegacy)) return;
    }
    var serial = (out.value || "").trim();
    var dbl = serial.indexOf("||");
    var tail = dbl >= 0 ? serial.slice(dbl + 2).trim() : "";
    var tokens = (tail.match(/\{[^}]+\}|\"[^\"]+\"|\S+/g) || []);
    var baseFamilyId = getBaseFamilyIdFromSerial(serial);
    var token = normalizeBracedIdToken(tok);
    if (isRarityTokenBootstrap(token)) {
      tokens = tokens.filter(function(t){ return !isRarityTokenBootstrap(t); });
    }
    tokens.push(token);
    if (typeof window.normalizeIdTokensForBaseFamily === "function" && baseFamilyId != null) {
      tokens = window.normalizeIdTokensForBaseFamily(tokens, baseFamilyId, { compactSameFamily: false });
    } else {
      tokens[tokens.length - 1] = normalizeIdTokenForBaseFamily(token, baseFamilyId);
    }
    var newTail = tokens.join(" ");
    var newSerial = dbl >= 0 ? serial.slice(0, dbl + 2) + newTail : (serial ? serial + " || " + newTail : "|| " + newTail);
    out.value = newSerial;
    try { window.__CC_LAST_CODE_TARGET = (out.id === "outCode") ? "simple" : "guided"; } catch (_) {}
    try {
      if (out.id === "outCode") { if (window.refreshOutputs) window.refreshOutputs(); }
      else {
        if (window.refreshGuidedOutputPreview) window.refreshGuidedOutputPreview();
        if (window.syncFloatingOutput) window.syncFloatingOutput(true);
      }
    } catch (_) {}
    try { if (typeof window.refreshBuildStatsCore === 'function') window.refreshBuildStatsCore(); } catch(_){}
  }
  function loadLegendaryPerks() {
    var sel = byId("legendaryPerkSelect");
    if (typeof window.populateLegendaryPerks === 'function') window.populateLegendaryPerks(sel);
  }
  function parseBrace(s) {
    s = String(s || "").trim();
    var bm = s.match(/^\{\s*(\d+)\s*:\s*\[([^\]]+)\]\s*\}$/);
    if (bm){
      var idsPacked = (bm[2].match(/\d+/g) || []).join(' ');
      return { a: Number(bm[1]), b: null, id: null, packed: true, bracketIds: idsPacked };
    }
    var m = s.match(/^\{\s*(\d+)\s*(?::\s*(\d+)\s*)?\}$/);
    if (!m) return null;
    var a = Number(m[1]);
    var b = m[2] != null ? Number(m[2]) : null;
    return { a: a, b: b, id: b != null ? b : a };
  }
  /** Expand packed bracket tokens like `{1:[51 51 53]}` into individual `{1:51}` rows for inspector. */
  function expandPackedInspectorTokens(tokens) {
    var out = [];
    for (var i = 0; i < tokens.length; i++) {
      var tok = String(tokens[i] || "").trim();
      if (!tok) continue;
      var brace = parseBrace(tok);
      if (brace && brace.packed && brace.bracketIds) {
        var ids = String(brace.bracketIds).trim().split(/\s+/);
        for (var j = 0; j < ids.length; j++) {
          var id = String(ids[j] || "").trim();
          if (id) out.push("{" + brace.a + ":" + id + "}");
        }
        continue;
      }
      out.push(tok);
    }
    return out;
  }
  var __resolvePartsIndex = null;
  var __resolvePartsStamp = "";
  function getResolvePartsIndex() {
    var stxLen = 0;
    var allLen = 0;
    var gunLen = 0;
    var grenLen = 0;
    var shieldLen = 0;
    try { if (window.STX_DATASET && Array.isArray(window.STX_DATASET.ALL_PARTS)) stxLen = window.STX_DATASET.ALL_PARTS.length; } catch(_){}
    try { if (Array.isArray(window.ALL_PARTS)) allLen = window.ALL_PARTS.length; } catch(_){}
    try { if (Array.isArray(window.GUN_PARTS)) gunLen = window.GUN_PARTS.length; } catch(_){}
    try { if (Array.isArray(window.GRENADE_PARTS)) grenLen = window.GRENADE_PARTS.length; } catch(_){}
    try { if (Array.isArray(window.SHIELD_PARTS)) shieldLen = window.SHIELD_PARTS.length; } catch(_){}
    var stamp = [stxLen, allLen, gunLen, grenLen, shieldLen].join("|");
    if (__resolvePartsIndex && __resolvePartsStamp === stamp) return __resolvePartsIndex;
    var all = [];
    try { if (window.STX_DATASET && Array.isArray(window.STX_DATASET.ALL_PARTS)) all = all.concat(window.STX_DATASET.ALL_PARTS); } catch(_){}
    try { if (Array.isArray(window.ALL_PARTS)) all = all.concat(window.ALL_PARTS); } catch(_){}
    try { if (Array.isArray(window.GUN_PARTS)) all = all.concat(window.GUN_PARTS); } catch(_){}
    try { if (Array.isArray(window.GRENADE_PARTS)) all = all.concat(window.GRENADE_PARTS); } catch(_){}
    try { if (Array.isArray(window.SHIELD_PARTS)) all = all.concat(window.SHIELD_PARTS); } catch(_){}
    var byIdRaw = Object.create(null);
    var byCode = Object.create(null);
    var byNumId = Object.create(null);
    var norm = function(s){ return String(s||"").replace(/^"+|"+$/g,"").trim(); };
    for (var i = 0; i < all.length; i++) {
      var p = all[i];
      if (!p) continue;
      var idRaw = String(p.idRaw || p.idraw || "").trim();
      if (idRaw && !byIdRaw[idRaw]) byIdRaw[idRaw] = p;
      if (p.id != null && Number.isFinite(Number(p.id))) {
        var nid = String(Number(p.id));
        if (!byNumId[nid]) byNumId[nid] = p;
      }
      var code = norm(p.code || p.spawnCode || "");
      if (code && !byCode[code]) byCode[code] = p;
    }
    __resolvePartsIndex = { all: all, byIdRaw: byIdRaw, byCode: byCode, byNumId: byNumId, norm: norm };
    __resolvePartsStamp = stamp;
    return __resolvePartsIndex;
  }
  function tryResolveToken(tok) {
    var t = String(tok || "").trim();
    if (!t) return null;
    var idx = getResolvePartsIndex();
    var tNorm = idx.norm(t);
    if (idx.byIdRaw[t]) return idx.byIdRaw[t];
    if (/^\d+$/.test(t) && idx.byNumId[t]) return idx.byNumId[t];
    if (tNorm && idx.byCode[tNorm]) return idx.byCode[tNorm];
    var brace = parseBrace(t);
    if (brace && brace.b != null) {
      var famIdKey = String(brace.a) + ":" + String(brace.b);
      if (idx.byIdRaw[famIdKey]) return idx.byIdRaw[famIdKey];
    }
    var all = idx.all;
    for (var i = 0; i < all.length; i++) {
      var p = all[i];
      if (!p) continue;
      if (brace && p.family != null && p.id != null && brace.b != null && brace.a === Number(p.family) && brace.b === Number(p.id)) return p;
    }
    return null;
  }
  function resolveTokenWithContext(tok, baseFamilyId) {
    var t = String(tok || "").trim();
    var p = tryResolveToken(t);
    if (p) return p;
    var brace = parseBrace(t);
    if (!brace) return null;
    var idx = getResolvePartsIndex();
    var all = idx.all;
    if (brace.b != null) {
      var famIdKey = String(brace.a) + ":" + String(brace.b);
      if (idx.byIdRaw[famIdKey]) return idx.byIdRaw[famIdKey];
      for (var i = 0; i < all.length; i++) {
        var row = all[i];
        if (!row) continue;
        if (row.family != null && row.id != null && Number(row.family) === Number(brace.a) && Number(row.id) === Number(brace.b)) return row;
      }
    }
    if (!Number.isFinite(baseFamilyId)) return null;
    var targetId = brace.b != null ? Number(brace.b) : Number(brace.id);
    if (!Number.isFinite(targetId)) return null;
    for (var j = 0; j < all.length; j++) {
      var row2 = all[j];
      if (!row2) continue;
      if (Number(row2.family) === Number(baseFamilyId) && Number(row2.id) === targetId) return row2;
      if (Number(row2.family) === Number(baseFamilyId) && row2.id == null && Number(row2.tokenId) === targetId) return row2;
    }
    return null;
  }
  function scanTailTokensFast(tail) {
    var out = [];
    var s = String(tail || "");
    var i = 0;
    while (i < s.length) {
      var c = s.charAt(i);
      if (c === " " || c === "\t" || c === "\n" || c === "\r" || c === ",") { i++; continue; }
      if (c === "{") {
        var close = s.indexOf("}", i + 1);
        if (close < 0) break;
        out.push(s.slice(i, close + 1));
        i = close + 1;
        continue;
      }
      if (c === '"') {
        var endQ = s.indexOf('"', i + 1);
        if (endQ < 0) break;
        out.push(s.slice(i, endQ + 1));
        i = endQ + 1;
        continue;
      }
      if (c === "|") {
        var mC = s.slice(i).match(/^\|\s*["']?c["']?\s*,\s*\d+\s*\|/);
        if (mC) {
          out.push(mC[0]);
          i += mC[0].length;
          continue;
        }
      }
      var start = i;
      while (i < s.length && /[A-Za-z0-9_.:-]/.test(s.charAt(i))) i++;
      if (i > start) out.push(s.slice(start, i));
      else i++;
    }
    return out;
  }

  function extractInspectorTokens(src) {
    var work = String(src || "").trim();
    if (!work) return [];
    if (work.indexOf("||") < 0 && (work.indexOf('@u') === 0 || work.indexOf('@U') === 0 || (work.indexOf("{") < 0 && work.length > 20)) && typeof window.deserializeBase85 === "function") {
      try {
        var deser = window.deserializeBase85(work);
        if (deser && typeof deser === "string" && deser.indexOf("||") >= 0) work = deser.trim();
      } catch (_) {}
    }
    var tail = "";
    var dbl = work.indexOf("||");
    if (dbl >= 0) {
      tail = work.slice(dbl + 2).trim();
    } else {
      var firstBrace = work.indexOf("{");
      tail = firstBrace >= 0 ? work.slice(firstBrace).trim() : work;
    }
    try {
      if (typeof window.__ccNormalizeTruncatedTailBracketTokens === "function") {
        tail = window.__ccNormalizeTruncatedTailBracketTokens(tail);
      }
    } catch (_) {}
    if (tail.length > 3000) {
      return scanTailTokensFast(tail).filter(function (tok) {
        tok = String(tok || "").trim();
        return tok && tok !== "|" && tok !== "||";
      });
    }
    if (typeof window.parseImportTokenList === "function") {
      return window.parseImportTokenList(tail).filter(function (tok) {
        tok = String(tok || "").trim();
        return tok && tok !== "|" && tok !== "||";
      });
    }
    var rawTokens = (tail.match(/\{[^}]+\}|\"[^\"]+\"|\|\s*["']?c["']?\s*,\s*\d+\s*\||[A-Za-z_][A-Za-z0-9_.:-]*/g) || []);
    var out = [];
    for (var i = 0; i < rawTokens.length; i++) {
      var tok = String(rawTokens[i] || "").trim();
      if (!tok) continue;
      if (/^\{\s*\d+\s*(?::\s*\d+\s*)?\}$/.test(tok)
        || /^\{\s*\d+\s*:\s*\[[^\]]+\]\s*\}$/.test(tok)
        || /^\"[^\"]+\"$/.test(tok)
        || /^\|\s*["']?c["']?\s*,\s*\d+\s*\|$/.test(tok)
        || /[A-Za-z_]/.test(tok)) {
        out.push(tok);
      }
    }
    return out;
  }
  window.__lookupPartByImportCode = function(code) {
    var c = String(code || "").replace(/^"+|"+$/g, "").trim();
    if (!c) return null;
    var p = tryResolveToken(c) || tryResolveToken('"' + c + '"');
    if (p) return p;
    if (typeof window.tryResolveToken === "function") return window.tryResolveToken(c) || window.tryResolveToken('"' + c + '"');
    return null;
  };
  function getFamilyForPart(part) {
    if (!part) return "";
    if (typeof part === "object") {
      if (part.family != null) return String(part.family);
      if (part.familyId != null) return String(part.familyId);
    }
    var code = String(typeof part === "string" ? part : (part.code || part.spawnCode || "")).trim();
    var brace = parseBrace(code);
    if (brace && brace.b != null) return String(brace.a);
    return "";
  }
  function isGenericInspectorPartText(s) {
    var t = String(s || "").trim();
    if (!t) return true;
    if (/^(barrel|magazine|scope|body|grip|stock|underbarrel|muzzle|sight|accessory|shield|grenade|firmware|core|stat)\s+part\s+for\s+/i.test(t)) return true;
    if (/^part\s+for\s+/i.test(t)) return true;
    if (/^part_/i.test(t)) return true;
    return false;
  }
  function titleCaseSlug(s) {
    return String(s || "").replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }
  function spawnNameFromPart(p) {
    if (!p) return "";
    var code = String(p.code || p.spawnCode || "").replace(/^"+|"+$/g, "").trim();
    if (!code) return "";
    var seg = code.indexOf(".") >= 0 ? code.slice(code.lastIndexOf(".") + 1) : code;
    seg = seg.replace(/^comp_\d+_(legendary|pearl|pearlescent)_/i, "").replace(/^part_/i, "");
    return seg ? titleCaseSlug(seg) : "";
  }
  function getInspectorPartName(p, fallbackTok) {
    if (!p) return String(fallbackTok || "—");
    try {
      if (typeof window.stxRarityIdHumanTitleForPart === "function") {
        var ht = String(window.stxRarityIdHumanTitleForPart(p) || "").trim();
        if (ht && ht !== "-") return ht;
      }
    } catch (_) {}
    var name = String(p.legendaryName || p.name || "").trim();
    if (name.indexOf("/") >= 0) {
      var slashParts = name.split("/").map(function (x) { return x.trim(); }).filter(Boolean);
      if (slashParts.length) name = slashParts[slashParts.length - 1];
    }
    if (name && !isGenericInspectorPartText(name)) {
      if (/^part_/i.test(name)) return titleCaseSlug(name.replace(/^part_/i, ""));
      return name;
    }
    var spawn = spawnNameFromPart(p);
    if (spawn) return spawn;
    return String(fallbackTok || name || "—");
  }
  function getInspectorPartDetails(p) {
    if (!p) return "";
    var bits = [];
    try {
      if (typeof window.stxGearCatalogRowForPart === "function") {
        var row = window.stxGearCatalogRowForPart(p);
        if (row && row.ability) bits.push(String(row.ability).trim());
      }
    } catch (_) {}
    var ef = String(p.effects != null ? p.effects : (p.effect || "")).trim();
    var red = getInspectorPartRedText(p);
    if (ef && !isGenericInspectorPartText(ef)) {
      if (!red || ef.toLowerCase() !== red.toLowerCase()) bits.push(ef);
    }
    var pt = String(p.partType || "").trim();
    if (pt && !isGenericInspectorPartText(pt)) {
      var blob = bits.join(" ").toLowerCase();
      if (blob.indexOf(pt.toLowerCase()) < 0) bits.push(pt);
    }
    var man = String(p.manufacturer || "").trim();
    if (man) {
      var blob2 = bits.join(" ").toLowerCase();
      if (blob2.indexOf(man.toLowerCase()) < 0) bits.push(man);
    }
    return bits.join(" · ");
  }
  function getInspectorPartRedText(p) {
    if (!p) return "";
    try {
      if (typeof window.partRedTextForDropdown === "function") {
        var red = String(window.partRedTextForDropdown(p) || "").trim();
        if (red) return red;
      }
    } catch (_) {}
    try {
      if (typeof window.stxGearCatalogRowForPart === "function") {
        var row = window.stxGearCatalogRowForPart(p);
        if (row && row.redText) return String(row.redText).trim();
      }
    } catch (_) {}
    var direct = String(p.redText || p.red_text || p.flavorText || "").trim();
    if (direct) return direct;
    return "";
  }
  function getStatsText(part) {
    try {
      if (typeof window.formatPartStatsSummary === "function") {
        var sum = window.formatPartStatsSummary(part, 4);
        if (sum) return sum;
      }
    } catch (_) {}
    try {
      if (typeof window.getFullStatLinesForPart === "function") {
        var full = window.getFullStatLinesForPart(part, null);
        if (full && full.lines && full.lines.length) {
          return full.lines.slice(0, 4).join(", ");
        }
      }
    } catch (_) {}
    try {
      var st = String(part && (part.stats || part.statText || "") || "").trim();
      if (st && !/^barrel part for/i.test(st) && !isGenericInspectorPartText(st)) return st;
    } catch (_) {}
    return "";
  }
  function esc(s) { return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
  var IPI_COL_COUNT = 9;

  /** Prefer explicit pasted inspector input; else active builder outputs. */
  function getInspectorSerialSource() {
    var qp = byId("ipiQuickPaste");
    var gi = byId("ccGuidedItemType");
    var guidedOn = gi && String(gi.value || "").trim();
    var g = byId("guidedOutputDeserialized");
    var o = byId("outCode");
    var imp = byId("importBox");
    var qv = qp && String(qp.value || "").trim();
    var gv = g && String(g.value || "").trim();
    var ov = o && String(o.value || "").trim();
    var iv = imp && String(imp.value || "").trim();
    if (qv) return qv;
    if (guidedOn) {
      if (gv) return gv;
      if (ov) return ov;
      if (iv) return iv;
      return "";
    }
    if (ov) return ov;
    if (gv) return gv;
    if (iv) return iv;
    return "";
  }

  function invalidateIpiSerialCache() {
    __ipiLastSrc = '';
  }
  window.__ipiInvalidateSerialCache = invalidateIpiSerialCache;
  window.__ipiGetInspectorSerialSource = getInspectorSerialSource;

  function normTailTokenKeyIpi(t) {
    var u = String(t || "").trim().replace(/^"+|"+$/g, "");
    var bk = u.match(/^\{\s*(\d+)\s*:\s*\[([^\]]+)\]\s*\}$/);
    if (bk) return bk[1] + ":[" + bk[2].trim().replace(/\s+/g, " ") + "]";
    var m = u.match(/^\{\s*(\d+)\s*:\s*(\d+)\s*\}$/);
    if (m) return m[1] + ":" + m[2];
    m = u.match(/^\{\s*(\d+)\s*\}$/);
    if (m) return "s:" + m[1];
    return u;
  }

  var __ipiRenderGen = 0;
  var __ipiRefreshTimer = 0;
  var __ipiLastSrc = '';

  function refreshImportedInspectorNow() {
    var tbody = byId("ipiBody");
    var badge = byId("ipiCount");
    var src = getInspectorSerialSource();
    if (!tbody || !badge) return;
    if (src === __ipiLastSrc && tbody.children && tbody.children.length) return;
    __ipiLastSrc = src;
    if (src && src.length > 7000) {
      badge.textContent = "Loading…";
      tbody.innerHTML = '<tr><td class="ipi-dim" colspan="' + IPI_COL_COUNT + '" style="color:rgba(255,255,255,0.62);padding:12px;">Parsing long serial…</td></tr>';
      var srcCopy = src;
      setTimeout(function () { refreshImportedInspectorCore(srcCopy); }, 50);
      return;
    }
    refreshImportedInspectorCore(src);
  }

  function refreshImportedInspector() {
    if (__ipiRefreshTimer) clearTimeout(__ipiRefreshTimer);
    __ipiRefreshTimer = setTimeout(function () {
      __ipiRefreshTimer = 0;
      refreshImportedInspectorNow();
    }, 280);
  }

  function refreshImportedInspectorCore(src) {
    var tbody = byId("ipiBody");
    var badge = byId("ipiCount");
    if (!tbody || !badge) return;
    var renderGen = ++__ipiRenderGen;

    // Support Base85 deserialization in inspector (skip when already deserialized)
    if (src && src.indexOf("||") < 0 && (src.indexOf('@u') === 0 || src.indexOf('@U') === 0 || (src.indexOf('{') < 0 && src.length > 20)) && typeof window.deserializeBase85 === 'function') {
      try {
        var deser = window.deserializeBase85(src);
        if (deser && typeof deser === 'string') src = deser.trim();
      } catch (_) {}
    }

    var baseFamilyId = getBaseFamilyIdFromSerial(src);
    var tokens = expandPackedInspectorTokens(extractInspectorTokens(src));
    
    var headerRows = [];

    // Resolve item header details (Type, Manufacturer, Rarity name)
    if (baseFamilyId != null) {
      var rarityRow = null;
      var rarities = window.STX_RARITIES || [];
      for (var ri = 0; ri < rarities.length; ri++) {
        if (Number(rarities[ri].familyId || rarities[ri].family) === baseFamilyId) {
          rarityRow = rarities[ri];
          break;
        }
      }
      if (rarityRow) {
        var rCat = String(rarityRow.itemType || rarityRow.category || "—").trim();
        var rMan = String(rarityRow.manufacturer || "—").trim();
        var rName = String(rarityRow.name || rarityRow.legendaryName || "Item Header").trim();
        headerRows.push(
          "<tr style=\"background:rgba(0,243,255,0.08);border-bottom:2px solid rgba(0,243,255,0.2);\">" +
          "<td style=\"color:rgba(0,243,255,1);font-weight:700;\">" + esc(rCat) + "</td>" +
          "<td style=\"color:rgba(255,255,255,0.95);\">" + esc(rName) + "</td>" +
          "<td class=\"ipi-dim\">—</td>" +
          "<td style=\"color:rgba(0,243,255,0.95);\">" + esc(rMan) + "</td>" +
          "<td>" + baseFamilyId + "</td>" +
          "<td style=\"text-align:center;\">—</td>" +
          "<td>—</td>" +
          "<td class=\"ipi-dim\">—</td>" +
          "<td class=\"ipi-dim\" style=\"color:rgba(0,243,255,0.7);font-size:0.85em;\">Item header</td></tr>"
        );
      }
    }

    if (!tokens.length) {
      badge.textContent = "0 added";
      if (!headerRows.length) {
        tbody.innerHTML = '<tr><td class="ipi-dim" colspan="' + IPI_COL_COUNT + '" style="color:rgba(255,255,255,0.62);">No part tokens after <code>||</code>. Paste or import a serial above, or build in Guided / Simple Builder.</td></tr>';
      } else {
        headerRows.push('<tr><td class="ipi-dim" colspan="' + IPI_COL_COUNT + '" style="color:rgba(255,255,255,0.4);padding:10px;text-align:center;">No parts found after <code>||</code></td></tr>');
        tbody.innerHTML = headerRows.join("");
      }
      return;
    }
    var order = [];
    var counts = {};
    var firstTok = {};
    for (var ti = 0; ti < tokens.length; ti++) {
      var tok = tokens[ti];
      var k = normTailTokenKeyIpi(tok);
      if (!counts[k]) {
        counts[k] = 0;
        firstTok[k] = tok;
        order.push(k);
      }
      counts[k]++;
    }
    badge.textContent = tokens.length + (tokens.length === 1 ? " token" : " tokens") + " (" + order.length + " unique)";

    var IPI_MAX_ROWS = 320;
    var displayOrder = order.length > IPI_MAX_ROWS ? order.slice(0, IPI_MAX_ROWS) : order;
    var hiddenUnique = order.length > IPI_MAX_ROWS ? (order.length - IPI_MAX_ROWS) : 0;

    var headerHtml = headerRows.join("");
    var RESOLVE_CHUNK = 40;
    var resolveIdx = 0;

    function resolveAndPaintChunk() {
      if (renderGen !== __ipiRenderGen) return;
      var end = Math.min(resolveIdx + RESOLVE_CHUNK, displayOrder.length);
      var chunkHtml = [];
      for (var oi = resolveIdx; oi < end; oi++) {
        var key = displayOrder[oi];
        var rep = firstTok[key];
        var p = resolveTokenWithContext(rep, baseFamilyId);
        var cat = p ? String(p.category || p.itemType || p.partType || "").trim() || "—" : "—";
        var name = getInspectorPartName(p, rep);
        var details = getInspectorPartDetails(p);
        var rawCode = String(rep).replace(/^"+|"+$/g, "");
        var brace = parseBrace(rawCode);
        var fam = p ? getFamilyForPart(p) : (brace && brace.b != null ? String(brace.a) : "");
        var familyOrSpawn = (brace && brace.b != null) ? String(brace.a)
          : ((brace && !brace.packed && brace.b == null && brace.id != null) ? String(baseFamilyId != null ? baseFamilyId : brace.a)
          : (fam || (brace && !brace.packed ? String(brace.a) : "") || "—"));
        var numericId = (brace && brace.b != null) ? String(brace.b)
          : ((brace && !brace.packed && brace.id != null) ? String(brace.id) : (p && p.id != null ? String(p.id) : "—"));
        var stats = p ? getStatsText(p) : "";
        var redText = p ? getInspectorPartRedText(p) : "";
        var cnt = counts[key];
        var encTok = encodeURIComponent(String(rep).trim());
        var statsShort = stats.length > 140 ? stats.slice(0, 137) + "…" : stats;
        var detailsShort = details.length > 140 ? details.slice(0, 137) + "…" : details;
        var redShort = redText.length > 120 ? redText.slice(0, 117) + "…" : redText;
        var redCell = redShort
          ? '<span style="color:#ff8f8f;">' + esc(redShort) + '</span>'
          : '<span class="ipi-dim">—</span>';
        chunkHtml.push(
          "<tr><td class=\"ipi-dim\" style=\"color:rgba(255,255,255,0.62);\">" + esc(cat) + "</td>" +
          "<td>" + esc(name) + "</td>" +
          "<td class=\"ipi-dim\" style=\"color:rgba(255,255,255,0.72);white-space:pre-line;font-size:0.88em;\">" + (detailsShort ? esc(detailsShort) : "—") + "</td>" +
          "<td style=\"color:rgba(0,243,255,0.95);\">" + esc(familyOrSpawn) + "</td><td>" + esc(numericId) + "</td>" +
          "<td style=\"text-align:center;font-weight:700;\">" + cnt + "</td>" +
          "<td style=\"white-space:nowrap;\"><button type=\"button\" class=\"btn ipi-qty\" style=\"padding:2px 8px;min-width:32px;\" data-ipi-delta=\"-1\" data-ipi-tok=\"" + encTok + "\" title=\"Remove one\">−</button> " +
          "<button type=\"button\" class=\"btn ipi-qty\" style=\"padding:2px 8px;min-width:32px;\" data-ipi-delta=\"1\" data-ipi-tok=\"" + encTok + "\" title=\"Add one\">+</button></td>" +
          "<td class=\"ipi-dim\" style=\"color:rgba(255,255,255,0.62);white-space:pre-line;font-size:0.88em;\">" + (statsShort ? esc(statsShort) : "—") + "</td>" +
          "<td style=\"white-space:pre-line;font-size:0.88em;\">" + redCell + "</td></tr>"
        );
      }
      if (resolveIdx === 0) tbody.innerHTML = headerHtml;
      if (chunkHtml.length) tbody.insertAdjacentHTML("beforeend", chunkHtml.join(""));
      resolveIdx = end;
      if (resolveIdx < displayOrder.length) {
        (window.requestAnimationFrame || function (fn) { setTimeout(fn, 0); })(resolveAndPaintChunk);
      } else if (hiddenUnique > 0) {
        tbody.insertAdjacentHTML("beforeend",
          '<tr><td class="ipi-dim" colspan="' + IPI_COL_COUNT + '" style="color:rgba(255,255,255,0.55);padding:10px;text-align:center;">+ ' + hiddenUnique + ' more unique part row(s) not shown — serial is fully imported.</td></tr>'
        );
      }
    }
    resolveAndPaintChunk();
  }

  function wireImportedInspectorQtyButtons() {
    var wrap = byId("importedPartsInspector");
    if (!wrap || wrap.__ipiQtyBound) return;
    wrap.__ipiQtyBound = true;
    wrap.addEventListener("click", function (ev) {
      var btn = ev.target && ev.target.closest ? ev.target.closest("[data-ipi-delta]") : null;
      if (!btn) return;
      var enc = btn.getAttribute("data-ipi-tok");
      if (!enc) return;
      function runMutate() {
        if (typeof window.__ccMutateSerialTailDelta !== "function") return false;
        try {
          var tok = decodeURIComponent(enc);
          var d = parseInt(btn.getAttribute("data-ipi-delta"), 10);
          if (Number.isFinite(d)) return window.__ccMutateSerialTailDelta(tok, d) !== false;
        } catch (_) {}
        return false;
      }
      if (runMutate()) return;
      if (typeof window.stxEnsureGuidedScripts === "function") {
        try { window.stxEnsureGuidedScripts(function () { runMutate(); }); } catch (_) {}
      }
    });
  }
  window.wireImportedInspectorQtyButtons = wireImportedInspectorQtyButtons;

  function getCombinedPasteForInspector() {
    var q = byId("ipiQuickPaste");
    var imp = byId("importBox");
    var a = q && String(q.value || "").trim();
    var b = imp && String(imp.value || "").trim();
    return a || b || "";
  }

  function applyInspectorPasteToGuided() {
    var importBox = byId("importBox");
    if (!importBox) {
      alert("Import box not found.");
      return;
    }
    var code = getCombinedPasteForInspector();
    if (!code) {
      alert("Paste a serial in the inspector box or in “Paste code to edit” first.");
      return;
    }
    if ((code.indexOf('@u') === 0 || code.indexOf('@U') === 0 || (code.indexOf("||") < 0 && code.indexOf("{") < 0 && code.length > 20)) && typeof window.deserializeBase85 === "function") {
      try {
        var deser = window.deserializeBase85(code);
        if (deser && typeof deser === "string" && deser.trim().length) code = deser.trim();
      } catch (_) {}
    }
    importBox.value = code;
    try {
      if (typeof window.importTokens === "function") {
        window.importTokens(code, 'guided');
      } else if (typeof window.refreshOutputs === "function") {
        window.refreshOutputs();
      }
    } catch (_) {}
    setTimeout(function () {
      try { if (typeof window.refreshGuidedOutputPreview === "function") window.refreshGuidedOutputPreview(); } catch (_) {}
      try { if (typeof window.syncFloatingOutput === "function") window.syncFloatingOutput(true); } catch (_) {}
      refreshImportedInspector();
      try { if (typeof window.refreshBuildStatsCore === "function") window.refreshBuildStatsCore(); } catch (_) {}
    }, 80);
  }

  function applyInspectorPasteToSimpleBuilder() {
    var importBox = byId("importBox");
    if (!importBox) {
      alert("Import box not found.");
      return;
    }
    var code = getCombinedPasteForInspector();
    if (!code) {
      alert("Paste a serial in the inspector box or in “Paste code to edit” first.");
      return;
    }
    importBox.value = code;
    if ((code.indexOf('@u') === 0 || code.indexOf('@U') === 0 || (code.indexOf("||") < 0 && code.indexOf("{") < 0 && code.length > 20)) && typeof window.deserializeBase85 === "function") {
      try {
        var deser = window.deserializeBase85(code);
        if (deser && typeof deser === "string" && deser.trim().length) importBox.value = deser.trim();
      } catch (_) {}
    }
    try {
      if (typeof window.importTokens === "function") {
        window.importTokens(code, 'simple');
      } else if (typeof window.refreshOutputs === "function") {
        window.refreshOutputs();
      }
    } catch (_) {}
    setTimeout(function () {
      try { if (typeof window.refreshGuidedOutputPreview === "function") window.refreshGuidedOutputPreview(); } catch (_) {}
      refreshImportedInspector();
      try { if (typeof window.refreshBuildStatsCore === "function") window.refreshBuildStatsCore(); } catch (_) {}
    }, 80);
  }
  function init(){
    loadPresetCategories();
    var catSel = byId("presetCategorySelect");
    var addBtn = byId("rebuildPresetAddBtn");
    if (catSel) catSel.addEventListener("change", loadPresetParts);
    if (addBtn) addBtn.addEventListener("click", addPresetPart);
    var randBtn = byId("rebuildRandomFullBuildBtn");
    if (randBtn && !randBtn.__moddedGenWired) {
      randBtn.__moddedGenWired = true;
      randBtn.onclick = function () {
        var repEl = byId("rebuildRandomRepeat");
        var n = repEl ? parseInt(String(repEl.value || "1"), 10) : 1;
        if (!Number.isFinite(n) || n < 1) n = 1;
        if (n > 100) n = 100;
        if (repEl) repEl.value = String(n);
        if (n > 1 && typeof window.randomFullBuildBatch === "function") {
          window.randomFullBuildBatch(n);
        } else if (typeof window.randomFullBuild === "function") {
          window.randomFullBuild();
        } else {
          alert("Random full build: loading… Try again in a moment.");
        }
      };
    }
    var liteUi = document.documentElement.classList.contains('stx-lite-ui') ||
      document.documentElement.classList.contains('stx-touch-ui');
    if (liteUi) {
      document.addEventListener('pointerdown', function () { loadLegendaryPerks(); }, { once: true, passive: true });
      if (typeof window.stxScheduleIdle === 'function') {
        window.stxScheduleIdle(loadLegendaryPerks, 12000);
      }
    } else {
      setTimeout(loadLegendaryPerks, 300);
    }
    function loadToolsSkinCamo() {
      var skinSel = byId("toolsSkinSelect");
      var camoSel = byId("toolsCamoSelect");
      if (typeof window.populateSkinCamo === 'function') window.populateSkinCamo(skinSel, camoSel);
    }
    loadToolsSkinCamo();
    window.loadToolsSkinCamo = loadToolsSkinCamo;
    var btnLeg = byId("btnAddLegendaryPart");
    var btnLegAll = byId("btnAddAllLegendaryParts");
    if (btnLeg) btnLeg.addEventListener("click", function(){ var s=byId("legendaryPerkSelect"); if(s&&s.value) appendToOutCode(s.value); });
    if (btnLegAll) btnLegAll.addEventListener("click", function(){
      var s=byId("legendaryPerkSelect"); if(!s) return;
      var all = (window.STX_DATASET && window.STX_DATASET.ALL_PARTS) ? window.STX_DATASET.ALL_PARTS : [];
      var leg = (typeof window.collectLegendaryPerkDropdownParts === "function")
        ? window.collectLegendaryPerkDropdownParts(all)
        : all.filter(function(p){ return p && /legendary\s*perk/i.test(String(p.partType || "")); });
      for (var i=0;i<leg.length;i++) {
        var p=leg[i];
        var raw=(p.idRaw||p.idraw||"").trim();
        var fam=p.family!=null?String(p.family):"";
        var id=p.id!=null?String(p.id):(p.itemId!=null?String(p.itemId):"");
        var tok=raw&&/^\d+:\d+$/.test(raw)?"{"+raw+"}":(fam&&id?"{"+fam+":"+id+"}":(p.code||"").trim());
        if(tok) appendToOutCode(tok);
      }
    });
    var btnElem = byId("btnAddElement");
    if (btnElem) btnElem.addEventListener("click", function(){ var s=byId("toolsElementSelect"); if(s&&s.value) appendToOutCode(s.value); });
    var btnDual = byId("btnAddDualElement");
    if (btnDual) btnDual.addEventListener("click", function(){ var s=byId("toolsDualElementSelect"); if(s&&s.value) appendToOutCode(s.value); });
    var btnPearl = byId("btnAddPearlElement");
    if (btnPearl) btnPearl.addEventListener("click", function(){ var s=byId("toolsPearlElementSelect"); if(s&&s.value) appendToOutCode(s.value); });
    setTimeout(function () {
      try { if (typeof window.refreshToolsStandaloneElementDropdowns === "function") window.refreshToolsStandaloneElementDropdowns(); } catch (_) {}
    }, 0);
    setTimeout(function () {
      try { if (typeof window.refreshToolsStandaloneElementDropdowns === "function") window.refreshToolsStandaloneElementDropdowns(); } catch (_) {}
    }, 700);
    var btnSkin = byId("btnAddSkinCamo");
    if (btnSkin) btnSkin.addEventListener("click", function(){
      var skin=byId("toolsSkinSelect"); var camo=byId("toolsCamoSelect");
      if (skin&&skin.value) appendToOutCode(skin.value);
      if (camo&&camo.value) appendToOutCode(camo.value);
    });
    var btnInsp = byId("btnRefreshInspector");
    if (btnInsp) btnInsp.addEventListener("click", function(){ refreshImportedInspector(); refreshBuildStatsCore(); });
    wireImportedInspectorQtyButtons();
    function wireIpiBtns() {
      var btnIpiG = byId("ipiBtnApplyGuided");
      var btnIpiS = byId("ipiBtnApplySimple");
      if (btnIpiG && !btnIpiG.__wired) {
        btnIpiG.__wired = true;
        btnIpiG.addEventListener("click", function () { applyInspectorPasteToGuided(); });
      }
      if (btnIpiS && !btnIpiS.__wired) {
        btnIpiS.__wired = true;
        btnIpiS.addEventListener("click", function () { applyInspectorPasteToSimpleBuilder(); });
      }
    }
    wireIpiBtns();
    setTimeout(wireIpiBtns, 800);
    window.__rebuildApplyInspectorPasteToGuided = applyInspectorPasteToGuided;
    window.__rebuildApplyInspectorPasteToSimple = applyInspectorPasteToSimpleBuilder;
    refreshImportedInspector();
    refreshBuildStatsCore();
    window.refreshImportedInspector = refreshImportedInspector;
    window.refreshBuildStatsCore = refreshBuildStatsCore;
    window.appendToOutCode = appendToOutCode;
  }
  var __ccRefreshBuildStatsRaf = 0;
  function refreshBuildStatsCoreFlush() {
    var grid = byId("buildStatsCoreGrid");
    var sub = byId("buildStatsCoreSubtitle");
    if (!grid || !sub) return;
    var core = null;
    var lastBuckets = null;
    try {
      if (typeof window.accumulateFromSelected === "function") {
        var b = window.accumulateFromSelected();
        lastBuckets = b || null;
        if (b && typeof b === "object") {
          function effectsOf(bucket) {
            if (!bucket) return [];
            if (Array.isArray(bucket.effects)) return bucket.effects.slice();
            return typeof window.summarizeBuildStatBucket === "function"
              ? window.summarizeBuildStatBucket(bucket)
              : [];
          }
          var items = [
            { label: "Damage", effects: effectsOf(b.damage), hits: (b.damage && b.damage.hits) || 0, nonNumeric: (b.damage && b.damage.nonNumeric) || 0 },
            { label: "Critical Damage", effects: effectsOf(b.crit), hits: (b.crit && b.crit.hits) || 0, nonNumeric: (b.crit && b.crit.nonNumeric) || 0 },
            { label: "Elemental", effects: effectsOf(b.elemental), hits: (b.elemental && b.elemental.hits) || 0, nonNumeric: (b.elemental && b.elemental.nonNumeric) || 0 },
            { label: "Accuracy", effects: effectsOf(b.accuracy), hits: (b.accuracy && b.accuracy.hits) || 0, nonNumeric: (b.accuracy && b.accuracy.nonNumeric) || 0 },
            { label: "ADS / Handling", effects: effectsOf(b.ads), hits: (b.ads && b.ads.hits) || 0, nonNumeric: (b.ads && b.ads.nonNumeric) || 0 },
            { label: "Fire Rate", effects: effectsOf(b.firerate), hits: (b.firerate && b.firerate.hits) || 0, nonNumeric: (b.firerate && b.firerate.nonNumeric) || 0 },
            { label: "Reload", effects: effectsOf(b.reload_time).concat(effectsOf(b.reload_speed)), hits: Number((b.reload_speed && b.reload_speed.hits) || 0) + Number((b.reload_time && b.reload_time.hits) || 0), nonNumeric: Number((b.reload_speed && b.reload_speed.nonNumeric) || 0) + Number((b.reload_time && b.reload_time.nonNumeric) || 0) },
            { label: "Ammo / Mag", effects: effectsOf(b.ammo_mag), hits: (b.ammo_mag && b.ammo_mag.hits) || 0, nonNumeric: (b.ammo_mag && b.ammo_mag.nonNumeric) || 0 },
            { label: "Projectiles", effects: effectsOf(b.projectiles), hits: (b.projectiles && b.projectiles.hits) || 0, nonNumeric: (b.projectiles && b.projectiles.nonNumeric) || 0 }
          ];
          var detected = 0;
          try { var r = Object.keys(b); for (var i = 0; i < r.length; i++) { var k = b[r[i]]; if (k && k.hits) detected += Number(k.hits) || 0; } } catch(_){}
          core = { detectedParts: detected, items: items };
        }
      }
    } catch(_){ lastBuckets = null; }
    var defaultItems = [
        { label: "Damage", effects: [], hits: 0, nonNumeric: 0 },
        { label: "Critical Damage", effects: [], hits: 0, nonNumeric: 0 },
        { label: "Elemental", effects: [], hits: 0, nonNumeric: 0 },
        { label: "Accuracy", effects: [], hits: 0, nonNumeric: 0 },
        { label: "ADS / Handling", effects: [], hits: 0, nonNumeric: 0 },
        { label: "Fire Rate", effects: [], hits: 0, nonNumeric: 0 },
        { label: "Reload", effects: [], hits: 0, nonNumeric: 0 },
        { label: "Ammo / Mag", effects: [], hits: 0, nonNumeric: 0 },
        { label: "Projectiles", effects: [], hits: 0, nonNumeric: 0 }
      ];
    if (!core || !core.items || !core.items.length) {
      sub.innerHTML = "Model estimate — coarse buckets, not in-game DPS. Import or select parts. Full lines and per-bucket contributions below.";
      core = { detectedParts: 0, items: defaultItems };
    }
    var debugBody = byId("buildStatsDebugBody");
    if (debugBody && (!core || core.detectedParts === 0)) {
      try {
        var dbg = typeof window.getBuildStatsDebugInfo === "function" ? window.getBuildStatsDebugInfo() : null;
        if (dbg && dbg.refs && dbg.refs.length) {
          var zipLoaded = !!(window.__CC_ZIP_WEAPON_PARTS || window.ZIP_WEAPON_PARTS);
          var lines = [];
          lines.push("Refs collected: " + (dbg.refs && dbg.refs.length) + " | With stats: " + (dbg.withStats && dbg.withStats.length) + " | Without stats: " + (dbg.withoutStats && dbg.withoutStats.length));
          if (!zipLoaded && (dbg.withoutStats && dbg.withoutStats.length)) lines.push("Note: ZIP_WEAPON_PARTS not loaded. Stats come from ALL_PARTS or ZIP_WEAPON_PARTS.");
          lines.push("Refs: " + (dbg.refs || []).join(", "));
          if (dbg.withoutStats && dbg.withoutStats.length) {
            lines.push("");
            lines.push("Parts without stats:");
            for (var j = 0; j < Math.min(dbg.withoutStats.length, 15); j++) {
              var u = dbg.withoutStats[j];
              var uname = String((u.part && (u.part.name || u.part.code || u.part.idRaw)) || u.ref || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
              lines.push("  " + uname);
            }
          }
          debugBody.innerHTML = lines.join("<br>");
        } else {
          debugBody.textContent = "No refs found. Add parts via Guided Builder or paste serial into output.";
        }
      } catch (e) { debugBody.textContent = "Debug: " + String(e && e.message); }
    }
    if (core && core.items && core.items.length) {
    sub.innerHTML = (core.detectedParts > 0)
      ? "<span>" + Number(core.detectedParts) + " contributing effect(s) from the selected parts.</span><span class=\"cc-stats-disclaimer\">Headline cards show reliable scales only: additive bonuses are summed, compatible scales are multiplied, and different stat fields stay separate. Raw offsets and alternate contexts are excluded from the scale and shown only in the detailed sections.</span>"
      : "<span>No stat effects detected yet.</span><span class=\"cc-stats-disclaimer\">Paste a serial or select parts to see source-aware modifiers.</span>";
    var pal = function(lbl) {
      var k = String(lbl||"").toLowerCase().replace(/\s+/g,"");
      if (k.indexOf("critical") >= 0) return { border: "rgba(255,179,71,0.42)", bgTop: "rgba(255,179,71,0.16)", bgBottom: "rgba(45,26,6,0.34)", title: "#ffd7a0", value: "#fff1d8", pos: "#ffc76a", neg: "#ff9a7a", meta: "rgba(255,236,210,0.9)" };
      if (k.indexOf("elemental") >= 0) return { border: "rgba(92,241,196,0.42)", bgTop: "rgba(92,241,196,0.14)", bgBottom: "rgba(5,38,34,0.34)", title: "#aaf8df", value: "#e8fff8", pos: "#7df0d2", neg: "#ff9aa8", meta: "rgba(222,255,245,0.9)" };
      if (k.indexOf("accuracy") >= 0) return { border: "rgba(88,198,255,0.42)", bgTop: "rgba(88,198,255,0.14)", bgBottom: "rgba(7,27,43,0.34)", title: "#a9e8ff", value: "#effaff", pos: "#6fd8ff", neg: "#ff9ca6", meta: "rgba(224,245,255,0.9)" };
      if (k.indexOf("ads") >= 0) return { border: "rgba(178,134,255,0.42)", bgTop: "rgba(178,134,255,0.14)", bgBottom: "rgba(29,18,47,0.34)", title: "#d9c1ff", value: "#f6efff", pos: "#caa2ff", neg: "#ff9dc9", meta: "rgba(239,228,255,0.9)" };
      if (k.indexOf("fire") >= 0) return { border: "rgba(255,107,107,0.42)", bgTop: "rgba(255,107,107,0.16)", bgBottom: "rgba(49,12,12,0.34)", title: "#ffc2c2", value: "#fff0f0", pos: "#ff9d78", neg: "#ff8f8f", meta: "rgba(255,228,228,0.9)" };
      if (k.indexOf("reload") >= 0) return { border: "rgba(54,225,179,0.42)", bgTop: "rgba(54,225,179,0.14)", bgBottom: "rgba(6,40,31,0.34)", title: "#98f4d6", value: "#eafff8", pos: "#67f0c1", neg: "#ff9da0", meta: "rgba(220,255,244,0.9)" };
      if (k.indexOf("ammo") >= 0) return { border: "rgba(156,230,86,0.42)", bgTop: "rgba(156,230,86,0.14)", bgBottom: "rgba(21,39,10,0.34)", title: "#cff7a7", value: "#f7ffeb", pos: "#b8f36e", neg: "#ffb08b", meta: "rgba(238,255,216,0.9)" };
      if (k.indexOf("projectile") >= 0) return { border: "rgba(255,122,186,0.42)", bgTop: "rgba(255,122,186,0.14)", bgBottom: "rgba(49,13,31,0.34)", title: "#ffc0df", value: "#fff0f8", pos: "#ff9ad1", neg: "#ff9f9f", meta: "rgba(255,228,241,0.9)" };
      return { border: "rgba(255,255,255,0.2)", bgTop: "rgba(255,255,255,0.08)", bgBottom: "rgba(255,255,255,0.02)", title: "#fff", value: "#fff", pos: "#7df", neg: "#f99", meta: "rgba(255,255,255,0.9)" };
    };
    var esc = function(s){ return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); };
    function readableNumber(value, maxDecimals) {
      var n = Number(value);
      if (!Number.isFinite(n)) return "\u2014";
      if (Math.abs(n) < 1e-12) n = 0;
      if (Math.abs(n) >= 1e12) return n.toExponential(3);
      return n.toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: maxDecimals == null ? 3 : maxDecimals
      });
    }
    function signedNumber(value, suffix, maxDecimals) {
      var n = Number(value);
      if (!Number.isFinite(n)) return "\u2014";
      return (n > 0 ? "+" : "") + readableNumber(n, maxDecimals) + (suffix || "");
    }
    function statFieldLabel(field) {
      var f = String(field || "").toLowerCase();
      var known = {
        damage_scale: "Damage", critdamage_add: "Critical damage",
        statuschance_scale: "Status chance", statusdamage_scale: "Status damage",
        elementaldamage_scale: "Elemental damage", elementalchance_scale: "Elemental chance",
        accuracy_scale: "Accuracy", maxaccuracy_scale: "Maximum accuracy", spread_scale: "Spread",
        recoil_scale: "Recoil", sway_scale: "Sway", accimpulse_scale: "Accuracy impulse",
        zoomtime_scale: "ADS time", zoomduration_scale: "ADS duration",
        equiptime_scale: "Equip time", putdowntime_scale: "Put-down time",
        firerate_scale: "Fire rate", firerate_value: "Fire-rate value",
        reloadtime_scale: "Reload time", reloadtime_value: "Reload-time value",
        thrownreloadtime_value: "Thrown reload-time value",
        maxloadedammo_value: "Loaded ammo", magazine_size: "Magazine size",
        projectilespershot_value: "Projectiles per shot", projpershot_scale: "Projectiles per shot",
        text_effect: "Parsed text effect"
      };
      if (known[f]) return known[f];
      return f.replace(/_+/g, " ").replace(/\b\w/g, function(ch) { return ch.toUpperCase(); });
    }
    function reliableScaleForEffect(effect) {
      var e = effect || {};
      var hasMul = Number(e.mulHits || 0) > 0;
      var hasAdd = Number(e.addHits || 0) > 0;
      if (!hasMul && !hasAdd) return null;
      var mul = hasMul ? Number(e.mul) : 1;
      var addLayer = hasAdd ? 1 + Number(e.add) : 1;
      var scale = mul * addLayer;
      return Number.isFinite(scale) && scale > 0 ? scale : null;
    }
    function reliableScaleSummary(effect) {
      var scale = reliableScaleForEffect(effect);
      if (scale == null) return "";
      var suffix = effect && effect.invertedBenefit ? " benefit" : "";
      return statFieldLabel(effect && effect.field) + ": \u00d7" + readableNumber(scale, 3) + suffix;
    }
    function impactStrength(deltaPct) {
      var amount = Math.abs(Number(deltaPct) || 0);
      if (amount < 1) return "Near neutral";
      if (amount < 5) return "Slight change";
      if (amount < 25) return "Noticeable change";
      if (amount < 100) return "Strong change";
      return "Major change";
    }
    function humanImpactForEffect(effect) {
      var scale = reliableScaleForEffect(effect);
      if (scale == null) return "\u2014";
      var delta = (scale - 1) * 100;
      if (Math.abs(delta) < 0.05) return "About the same as neutral";
      var amount = readableNumber(Math.abs(delta), 1) + "%";
      if (effect && effect.invertedBenefit) {
        return amount + (delta > 0 ? " better (lower raw scale)" : " worse (lower raw scale)");
      }
      return amount + (delta > 0 ? " above neutral" : " below neutral");
    }
    grid.innerHTML = core.items.map(function(it) {
      var effects = Array.isArray(it.effects) ? it.effects : [];
      var scaleEffects = effects.filter(function(e) { return reliableScaleForEffect(e) != null; });
      var nn = Number(it.nonNumeric || 0);
      var mainValue = scaleEffects.length === 1
        ? "\u00d7" + readableNumber(reliableScaleForEffect(scaleEffects[0]), 3)
        : (scaleEffects.length ? scaleEffects.length + " scales" : "\u2014");
      var detail = scaleEffects.length
        ? scaleEffects.slice(0, 2).map(reliableScaleSummary).join(" \u00b7 ") + (scaleEffects.length > 2 ? " \u00b7 +" + (scaleEffects.length - 2) + " more" : "")
        : "No reliable scale";
      var scaleHitCount = 0;
      var excludedCount = nn;
      for (var ei = 0; ei < effects.length; ei++) {
        scaleHitCount += Number(effects[ei].mulHits || 0) + Number(effects[ei].addHits || 0);
        excludedCount += Number(effects[ei].valueHits || 0) + Number(effects[ei].ambiguousHits || 0) + Number(effects[ei].invalidHits || 0);
      }
      var meta = scaleHitCount
        ? ("Scale effects: " + scaleHitCount + (excludedCount ? " | raw/context excluded: " + excludedCount : ""))
        : (excludedCount ? "Raw/context effects excluded: " + excludedCount : "\u2014");
      var p = pal(it.label);
      var titleRow = esc(it.label);
      return "<div class=\"cc-core-card\" style=\"border-color:" + p.border + ";background:linear-gradient(180deg," + p.bgTop + " 0%," + p.bgBottom + " 100%);\"><div class=\"cc-core-card-title\" style=\"color:" + p.title + "\">" + titleRow + "</div><div class=\"cc-core-card-scale-label\">Scale</div><div class=\"cc-core-card-scale\" style=\"color:" + p.value + "\" title=\"Reliable scale from compatible selected-part effects\">" + esc(mainValue) + "</div><div class=\"cc-core-card-pct\">" + esc(detail) + "</div><div class=\"cc-core-card-meta\" style=\"color:" + p.meta + "\">" + esc(meta) + "</div></div>";
    }).join("");
    var finalPanel = byId("buildStatsFinalEstimates");
    if (finalPanel) {
      try {
        var rows = [];
        for (var ci0 = 0; ci0 < core.items.length; ci0++) {
          var c0 = core.items[ci0];
          var cEffects = c0 && Array.isArray(c0.effects) ? c0.effects : [];
          for (var cei = 0; cei < cEffects.length; cei++) {
            var ce = cEffects[cei];
            var reliableScale = reliableScaleForEffect(ce);
            if (reliableScale == null) continue;
            var opNotes = [];
            if (Number(ce.mulHits || 0)) opNotes.push("scale product from " + Number(ce.mulHits) + " effect(s)");
            if (Number(ce.addHits || 0)) opNotes.push("summed additive bonus");
            var excludedForField = Number(ce.valueHits || 0) + Number(ce.ambiguousHits || 0) + Number(ce.invalidHits || 0);
            if (excludedForField) opNotes.push(excludedForField + " raw/context effect(s) excluded");
            opNotes.unshift(impactStrength((reliableScale - 1) * 100));
            rows.push({
              name: c0.label + " \u2014 " + statFieldLabel(ce.field),
              value: humanImpactForEffect(ce),
              note: opNotes.join("; ")
            });
          }
        }
        var bits = [];
        bits.push("<div class=\"cc-final-estimates-title\">Build Impact Overview</div>");
        bits.push("<div class=\"cc-final-estimates-grid\">");
        for (var rix = 0; rix < rows.length; rix++) {
          var rr = rows[rix];
          bits.push("<div class=\"cc-final-est-row\"><div class=\"cc-final-est-name\">" + esc(rr.name) + "</div><div class=\"cc-final-est-value\">" + esc(rr.value) + "</div><div class=\"cc-final-est-note\">" + esc(rr.note) + "</div></div>");
        }
        bits.push("</div>");
        bits.push("<div class=\"cc-final-est-note\" style=\"margin-top:8px;\">Plain-language comparison against a neutral 1.000 scale. Exact scales remain in the cards above; raw offsets and alternate table contexts remain in the detailed sections below.</div>");
        if (!rows.length) bits.push("<div class=\"cc-final-est-note\" style=\"margin-top:6px;\">There are no reliable scale effects to interpret for this build.</div>");
        finalPanel.innerHTML = bits.join("");
      } catch (e0) {
        finalPanel.innerHTML = "<div class=\"cc-final-estimates-title\">Build Impact Overview</div><p class=\"cc-full-stats-empty\">" + esc(String(e0 && e0.message)) + "</p>";
      }
    }
    var fullPanel = byId("buildStatsFullStats");
    if (fullPanel) {
      try {
        var br = typeof window.getFullStatsBreakdown === "function" ? window.getFullStatsBreakdown() : null;
        if (!br || !br.entries || !br.entries.length) {
          fullPanel.innerHTML = "<p class=\"cc-full-stats-empty\">" + esc(br && br.message ? br.message : "\u2014") + "</p>";
        } else {
          var chunks = ["<details class=\"cc-full-stats-details\"><summary class=\"cc-full-stats-heading\">Full stat lines (per resolved part)</summary><div class=\"cc-full-stats-details-body\">"];
          for (var fi = 0; fi < br.entries.length; fi++) {
            var en = br.entries[fi];
            chunks.push("<div class=\"cc-full-stats-part\"><div class=\"cc-full-stats-part-title\">" + esc(en.name) + "</div>");
            var safeLines = (en && en.lines && en.lines.length) ? en.lines.filter(function (ln) {
              return ln != null && String(ln).trim() !== '';
            }).map(function (ln) { return String(ln); }) : [];
            if (!safeLines.length) {
              chunks.push("<p class=\"cc-full-stats-empty cc-full-stats-none\">No stat lines for this part.</p>");
            } else {
              chunks.push("<ul class=\"cc-full-stats-lines\">");
              for (var li = 0; li < safeLines.length; li++) {
                chunks.push("<li>" + esc(safeLines[li]) + "</li>");
              }
              chunks.push("</ul>");
            }
            chunks.push("</div>");
          }
          chunks.push("</div></details>");
          fullPanel.innerHTML = chunks.join("");
        }
      } catch (e) {
        fullPanel.innerHTML = "<p class=\"cc-full-stats-empty\">" + esc(String(e && e.message)) + "</p>";
      }
    }
    var buckEl = byId("buildStatsBucketBreakdown");
    if (buckEl) {
      try {
        if (!lastBuckets) {
          buckEl.innerHTML = "";
        } else {
          var order = [
            ["damage", "Damage"], ["crit", "Critical Damage"], ["elemental", "Elemental"], ["accuracy", "Accuracy"],
            ["ads", "ADS / Handling"], ["firerate", "Fire Rate"], ["reload_time", "Reload (time)"], ["reload_speed", "Reload (speed)"],
            ["ammo_mag", "Ammo / Mag"], ["projectiles", "Projectiles"]
          ];
          var parts = ["<details class=\"cc-bucket-details\"><summary>How modifiers combine (per source effect)</summary>"];
          var any = false;
          for (var bi = 0; bi < order.length; bi++) {
            var bk = lastBuckets[order[bi][0]];
            if (!bk || !bk.contributions || !bk.contributions.length) continue;
            any = true;
            parts.push("<div class=\"cc-bucket-block\"><div class=\"cc-bucket-block-title\">" + esc(order[bi][1]) + "</div>");
            for (var ci = 0; ci < bk.contributions.length; ci++) {
              var c = bk.contributions[ci];
              var ma = "";
              if (String(c.combine || "").toLowerCase() === "add" && Number.isFinite(Number(c.rawValue))) {
                ma = " \u2192 additive " + signedNumber(Number(c.rawValue) * 100, "%", 1);
              } else if (String(c.combine || "").toLowerCase() === "value" && Number.isFinite(Number(c.rawValue))) {
                ma = " \u2192 engine offset " + signedNumber(c.rawValue, "", 3);
              } else if (c.multApplied != null && Number.isFinite(Number(c.multApplied))) {
                ma = " \u2192 scale \u00d7" + readableNumber(c.multApplied, 4);
              } else if (c.combine) {
                ma = " [" + esc(c.combine) + "]";
              }
              parts.push("<div class=\"cc-bucket-line\"><strong>" + esc(c.part || "") + "</strong> <span class=\"cc-bucket-src\">" + esc(c.source || "") + "</span><br>" + esc(c.detail || "") + ma + "</div>");
            }
            parts.push("</div>");
          }
          if (!any) parts.push("<p class=\"cc-full-stats-empty\">No contribution lines yet.</p>");
          parts.push("</details>");
          buckEl.innerHTML = parts.join("");
        }
      } catch (e2) {
        buckEl.innerHTML = "<p class=\"cc-full-stats-empty\">" + esc(String(e2 && e2.message)) + "</p>";
      }
    }
    var debugBody = byId("buildStatsDebugBody");
    var debugDetails = byId("buildStatsDebugDetails");
    if (debugBody && debugDetails) {
      try {
        var dbg = typeof window.getBuildStatsDebugInfo === "function" ? window.getBuildStatsDebugInfo() : null;
        if (dbg) {
          var zipLoaded = !!(window.__CC_ZIP_WEAPON_PARTS || window.ZIP_WEAPON_PARTS);
          var lines = [];
          lines.push("Refs collected: " + (dbg.refs && dbg.refs.length) + " | With stats: " + (dbg.withStats && dbg.withStats.length) + " | Without stats: " + (dbg.withoutStats && dbg.withoutStats.length));
          if (!zipLoaded && (dbg.withoutStats && dbg.withoutStats.length)) lines.push("Note: ZIP_WEAPON_PARTS not loaded. Stats come from ALL_PARTS or ZIP_WEAPON_PARTS.");
          if (dbg.refs && dbg.refs.length) {
            lines.push("");
            lines.push("Refs: " + dbg.refs.join(", "));
          }
          if (dbg.withStats && dbg.withStats.length) {
            lines.push("");
            lines.push("Parts with stats:");
            for (var i = 0; i < Math.min(dbg.withStats.length, 20); i++) {
              var w = dbg.withStats[i];
              var name = (w.part && (w.part.name || w.part.code || w.part.idRaw)) || w.ref;
              lines.push("  " + esc(String(name)) + " -> " + esc((w.stats || "").substring(0, 60)) + (w.stats && w.stats.length > 60 ? "..." : ""));
            }
            if (dbg.withStats.length > 20) lines.push("  ... and " + (dbg.withStats.length - 20) + " more");
          }
          if (dbg.withoutStats && dbg.withoutStats.length) {
            lines.push("");
            lines.push("Parts without stats:");
            for (var j = 0; j < Math.min(dbg.withoutStats.length, 15); j++) {
              var u = dbg.withoutStats[j];
              var uname = (u.part && (u.part.name || u.part.code || u.part.idRaw)) || u.ref;
              lines.push("  " + esc(String(uname)));
            }
            if (dbg.withoutStats.length > 15) lines.push("  ... and " + (dbg.withoutStats.length - 15) + " more");
          }
          debugBody.innerHTML = lines.join("<br>");
        } else {
          debugBody.textContent = "No debug info available.";
        }
      } catch (e) {
        debugBody.textContent = "Debug error: " + String(e && e.message);
      }
    }
    }
  }
  function refreshBuildStatsCore() {
    if (__ccRefreshBuildStatsRaf) return;
    __ccRefreshBuildStatsRaf = requestAnimationFrame(function () {
      __ccRefreshBuildStatsRaf = 0;
      refreshBuildStatsCoreFlush();
    });
  }
  window.tryResolveToken = tryResolveToken;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else setTimeout(init, 500);
})();
