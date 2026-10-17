/**
 * Bridge Simple Builder outputs → parent SQBT EXE (postMessage).
 * Posts @U when Base85 pack succeeds; otherwise posts deserialized for Python pack.
 * Preview prefers human part names / perk / red-text — never raw {7:54} token lists.
 */
(function () {
  "use strict";

  var TYPE = {
    SERIAL: "sqbt-editor-serial",
    PREVIEW: "sqbt-editor-preview",
    READY: "sqbt-editor-ready",
  };

  var lastSerial = "";
  var lastDeser = "";
  var previewTimer = 0;
  var serialTimer = 0;

  function trim(v) {
    return String(v == null ? "" : v).trim();
  }

  function readOut(id) {
    var el = document.getElementById(id);
    return el ? trim(el.value) : "";
  }

  function post(type, payload) {
    try {
      if (!window.parent || window.parent === window) return;
      window.parent.postMessage(Object.assign({ type: type, source: "sqbt-editor" }, payload || {}), "*");
    } catch (_) {}
  }

  function applyShellLevel(level) {
    var n = parseInt(level, 10);
    if (!Number.isFinite(n) || n < 1 || n > 100) return false;
    try {
      var state = window.__STX_SIMPLE_STATE || window.__BL4_EDITOR_STATE || window.state;
      if (state) state.level = n;
    } catch (_) {}
    ["level", "level2"].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      el.value = String(n);
      try {
        el.dispatchEvent(new Event("change", { bubbles: true }));
      } catch (_) {}
    });
    return true;
  }

  function loadSerialFromShell(data) {
    var serial = trim(data && data.serial);
    if (!serial || serial.indexOf("@U") !== 0) return;
    try {
      if (typeof window.importTokens !== "function") {
        post("sqbt-editor-imported", {
          ok: false,
          serial: serial,
          message: "Builder import is not ready yet.",
        });
        return;
      }
      window.importTokens(serial, "both");
      // importTokens often leaves the builder UI at L60; Picture relevel sends level.
      if (data && data.level != null) applyShellLevel(data.level);
      setTimeout(function () {
        if (data && data.level != null) applyShellLevel(data.level);
        if (data && data.imageExtracted) {
          loadImageRecipeFromShell({
            extracted: data.imageExtracted,
            merge: true,
            requestId: data.requestId,
          });
        } else {
          emitSerial();
          schedulePreview();
          post("sqbt-editor-imported", {
            ok: true,
            serial: serial,
            request_id: data && data.requestId,
            message: "Exact serial loaded into Build.",
          });
        }
      }, serial.length > 2200 ? 1100 : 420);
    } catch (error) {
      post("sqbt-editor-imported", {
        ok: false,
        serial: serial,
        message: String(error && error.message ? error.message : error),
      });
    }
  }

  function recipeNorm(value) {
    return trim(value)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function recipeIncludesWords(haystack, words) {
    var sourceWords = recipeNorm(haystack).split(" ").filter(Boolean);
    return words.every(function (word) {
      var wanted = recipeNorm(word);
      return sourceWords.some(function (actual) {
        if (actual === wanted) return true;
        if (wanted.length >= 5 && actual === wanted + "s") return true;
        if (actual.length >= 5 && wanted === actual + "s") return true;
        return false;
      });
    });
  }

  function loadImageRecipeFromShell(data) {
    var attrs = data && data.extracted && typeof data.extracted === "object"
      ? data.extracted
      : {};
    var merge = Boolean(data && data.merge);
    var state = window.__STX_SIMPLE_STATE || window.__BL4_EDITOR_STATE || window.state;
    var all = window.STX_DATASET && Array.isArray(window.STX_DATASET.ALL_PARTS)
      ? window.STX_DATASET.ALL_PARTS
      : [];
    if (!state || !all.length || typeof window.refreshTopSelectors !== "function") {
      post("sqbt-editor-imported", {
        ok: false,
        message: "Build data is not ready yet. Try Load observed parts again.",
      });
      return;
    }

    var itemType = trim(attrs.item_type);
    var weaponType = "";
    if (/\b(?:assault rifle|sniper rifle|sniper|shotgun|pistol|smg|submachine gun)\b/i.test(itemType)) {
      weaponType = /sniper/i.test(itemType) ? "Sniper Rifle"
        : /submachine|\bsmg\b/i.test(itemType) ? "SMG"
        : itemType;
      itemType = "Weapon";
    } else if (/heavy|launcher/i.test(itemType)) {
      itemType = "Heavy";
      weaponType = "Heavy Weapon";
    } else if (/class\s*mod/i.test(itemType)) {
      itemType = "Class Mod";
    } else if (/repair\s*kit|repkit/i.test(itemType)) {
      itemType = "Repkit";
    }

    state.itemType = itemType || state.itemType || "";
    state.weaponType = weaponType || state.weaponType || "";
    state.manufacturer = trim(attrs.manufacturer) || state.manufacturer || "";
    if (Number(attrs.level) >= 1 && Number(attrs.level) <= 100) state.level = Number(attrs.level);
    var rarity = recipeNorm(attrs.rarity);
    state.rarity = rarity === "pearl" ? "5"
      : rarity === "pearlescent" ? "5"
      : rarity === "legendary" ? "4"
      : rarity === "epic" ? "3"
      : rarity === "rare" ? "2"
      : rarity === "uncommon" ? "1"
      : rarity === "common" ? "0"
      : "";
    if (!merge) {
      state.mainPart = null;
      state.detectedCategory = state.itemType === "Heavy" ? "Weapon" : state.itemType;
      state.slots = {};
      state.extras = [];
    }

    try { window.refreshTopSelectors(); } catch (_) {}

    var evidenceLines = []
      .concat(attrs.text || [])
      .concat(attrs.title_candidates || [])
      .concat(attrs.perks || [])
      .concat(attrs.flavor_lines || [])
      .concat((attrs.stats || []).map(function (row) {
        return trim(row && row.label) + " " + trim(row && row.value);
      }))
      .filter(Boolean);
    var evidence = evidenceLines.join(" ");
    var scoped = all.filter(function (part) {
      if (!part || typeof part !== "object") return false;
      if (state.manufacturer && recipeNorm(part.manufacturer) !== recipeNorm(state.manufacturer)) return false;
      if (state.weaponType) {
        var partType = recipeNorm(part.weaponType || part.itemType);
        if (partType && partType !== recipeNorm(state.weaponType) && !(partType === "sniper" && state.weaponType === "Sniper Rifle")) {
          return false;
        }
      }
      return true;
    });

    var matched = [];
    function exactOne(predicate, evidenceLabel, pool) {
      var rows = (pool || scoped).filter(predicate).filter(function (row, index, entries) {
        return entries.findIndex(function (other) { return trim(other.idRaw) === trim(row.idRaw); }) === index;
      });
      if (rows.length !== 1) return null;
      var part = rows[0];
      if (!matched.some(function (entry) { return trim(entry.part.idRaw) === trim(part.idRaw); })) {
        matched.push({ part: part, evidence: evidenceLabel });
      }
      return part;
    }

    // Resolve only combinations whose visible words uniquely identify one
    // catalog row. Hidden body, grip, sight, and rolled parts stay unset.
    var title = (attrs.title_candidates || []).slice(0, 2).join(" ");
    var namedCandidates = scoped.filter(function (part) {
      var nameWords = recipeNorm(part.name).split(" ").filter(function (word) {
        return word.length >= 4 && !/^(legendary|perks)$/.test(word);
      });
      var effectWords = recipeNorm(part.effects).split(" ").filter(function (word) { return word.length >= 4; });
      return nameWords.length > 0 &&
        effectWords.length > 0 &&
        recipeIncludesWords(title + " " + evidence, nameWords) &&
        recipeIncludesWords(evidence, effectWords);
    });
    var namedPart = namedCandidates.length === 1
      ? exactOne(function (row) { return row === namedCandidates[0]; }, "visible item name/perk")
      : null;

    if (recipeIncludesWords(evidence, ["torgue", "impact", "gyrojet"])) {
      exactOne(function (part) {
        return recipeIncludesWords(
          [part.name, part.stats, part.effects, part.code].join(" "),
          ["torgue", "impact", "gyrojet"]
        );
      }, "Torgue impact Gyrojets");
    }
    if (recipeIncludesWords(evidence, ["daedalus", "shotgun", "ammo"])) {
      exactOne(function (part) {
        return recipeIncludesWords(
          [part.name, part.stats, part.effects, part.code].join(" "),
          ["daedalus", "shotgun", "ammo"]
        );
      }, "Daedalus Shotgun Ammo");
    }
    (Array.isArray(attrs.visible_parts) ? attrs.visible_parts : []).forEach(function (visiblePart) {
      var idRaw = trim(visiblePart && visiblePart.id_raw);
      var matchWords = Array.isArray(visiblePart && visiblePart.match_words)
        ? visiblePart.match_words.filter(Boolean)
        : [];
      if (idRaw) {
        exactOne(function (part) {
          return trim(part && part.idRaw) === idRaw;
        }, trim(visiblePart.label || idRaw));
      } else if (matchWords.length) {
        exactOne(function (part) {
          return recipeIncludesWords(
            [part.name, part.stats, part.effects, part.code].join(" "),
            matchWords
          );
        }, trim(visiblePart.label || matchWords.join(" ")));
      }
    });

    // Shared Weapon element parts are labelled Maliwan in STX, but apply to
    // every gun maker. Use their explicit shared-root code rather than maker scope.
    var observedElement = recipeNorm(attrs.element);
    if (observedElement === "incendiary") observedElement = "fire";
    if (observedElement && (state.itemType === "Weapon" || state.itemType === "Heavy")) {
      var selectedParts = [state.mainPart].concat(state.extras || []);
      Object.keys(state.slots || {}).forEach(function (key) {
        selectedParts = selectedParts.concat(state.slots[key] || []);
      });
      function sharedElementCode(part) {
        return trim(part && part.code).replace(/"/g, "").toLowerCase();
      }
      var pearlElement = selectedParts.some(function (part) {
        return /^weapon\.pearl_(?:fire|radiation|shock|cryo|corrosive|normal)$/.test(sharedElementCode(part));
      });
      var targetCode = "weapon." + (pearlElement ? "pearl_" : "part_") + observedElement;
      var elementPart = exactOne(function (part) {
        return sharedElementCode(part) === targetCode;
      }, "Visible " + observedElement + " element", all);
      if (elementPart) {
        function keepElement(part) {
          return !/^weapon\.(?:part_|pearl_)(?:fire|radiation|shock|cryo|corrosive|normal)$/.test(sharedElementCode(part)) || trim(part.idRaw) === trim(elementPart.idRaw);
        }
        state.extras = (state.extras || []).filter(keepElement);
        Object.keys(state.slots || {}).forEach(function (key) {
          var value = state.slots[key];
          if (Array.isArray(value)) state.slots[key] = value.filter(keepElement);
          else if (value && !keepElement(value)) delete state.slots[key];
        });
      }
    }

    if (namedPart && (!merge || !state.mainPart)) {
      state.mainPart = namedPart;
      state.detectedCategory = namedPart.category || state.detectedCategory || state.itemType;
    }
    function stateHasPart(part) {
      var wanted = trim(part && part.idRaw);
      if (!wanted) return false;
      var selected = [state.mainPart].concat(Array.isArray(state.extras) ? state.extras : []);
      Object.keys(state.slots || {}).forEach(function (key) {
        var value = state.slots[key];
        if (Array.isArray(value)) selected = selected.concat(value);
        else if (value) selected.push(value);
      });
      return selected.some(function (row) {
        return trim(row && row.idRaw) === wanted;
      });
    }
    matched.forEach(function (entry) {
      if (entry.part === namedPart || stateHasPart(entry.part)) return;
      var placed = false;
      try {
        if (typeof window.stxTryPlacePartInBestSlot === "function") {
          placed = window.stxTryPlacePartInBestSlot(entry.part, { skipRefresh: true });
        }
      } catch (_) {}
      if (!placed) {
        var key = /legendary\s*perk/i.test(trim(entry.part.partType)) ? "legendary" : "additionalParts";
        var current = Array.isArray(state.slots[key]) ? state.slots[key] : [];
        state.slots[key] = current.concat([entry.part]);
      }
    });

    try { window.refreshBuilder(); } catch (_) {}
    setTimeout(function () {
      try { window.refreshOutputs(true); } catch (_) {}
      try { if (typeof window.refreshBuildStatsCore === "function") window.refreshBuildStatsCore(); } catch (_) {}
      emitSerial();
      schedulePreview();
      var resolved = matched.map(function (entry) {
        return trim(entry.part.name || entry.part.stats || entry.part.code);
      });
      var unresolved = (attrs.perks || []).filter(function (line) {
        var lineNorm = recipeNorm(line);
        return !matched.some(function (entry) {
          var blob = recipeNorm([
            entry.part.name,
            entry.part.stats,
            entry.part.effects,
            entry.part.code,
          ].join(" "));
          var significant = lineNorm.split(" ").filter(function (word) {
            return word.length >= 5 && !/^(licensed|secondary|fires|critical|projectiles)$/.test(word);
          });
          return significant.some(function (word) { return blob.indexOf(word) >= 0; });
        });
      });
      post("sqbt-editor-imported", {
        ok: Boolean(matched.length || state.itemType),
        request_id: data && data.requestId,
        message: resolved.length
          ? "Loaded observed card facts and " + resolved.length + " resolved part" + (resolved.length === 1 ? "" : "s") +
            " into Build. Review hidden parts before using the reconstructed serial." +
            (unresolved.length ? " " + unresolved.length + " visible line" + (unresolved.length === 1 ? " remains" : "s remain") + " unresolved." : "")
          : "Loaded observed card facts into Build. No visible part was unique enough to add automatically.",
        resolved_parts: resolved,
        resolved_part_ids: matched.map(function (entry) {
          return trim(entry.part && entry.part.idRaw);
        }).filter(Boolean),
        unresolved_lines: unresolved,
      });
    }, 500);
  }

  function isRawTokenLine(s) {
    var t = trim(s);
    if (!t) return true;
    // Pure serial tokens / brace ids — not card copy.
    if (/^(\{[\d:\s\[\],]+\}|\d+:\d+)(\s+(\{[\d:\s\[\],]+\}|\d+:\d+))*$/.test(t)) return true;
    if (/^@U/.test(t)) return true;
    return false;
  }

  function stripTokenNoise(s) {
    return trim(s)
      .replace(/\s*\(id:\s*\{[^}]+\}\)\s*/gi, " ")
      .replace(/\s*\{[\d:\s\[\],]+\}/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function partHumanName(p) {
    if (!p || typeof p !== "object") return "";
    var n = trim(p.name || p.legendaryName || p.displayName || "");
    n = stripTokenNoise(n);
    if (n && !isRawTokenLine(n) && !/^placeholder$/i.test(n)) return n;
    var code = trim(p.code || p.spawnCode || p.importCode || "");
    if (code) {
      var seg = code.indexOf(".") >= 0 ? code.slice(code.lastIndexOf(".") + 1) : code;
      seg = stripTokenNoise(seg).replace(/_/g, " ");
      if (seg && !isRawTokenLine(seg)) return seg;
    }
    return "";
  }

  function partEffectLine(p) {
    if (!p || typeof p !== "object") return "";
    var line = "";
    try {
      if (typeof window.partEffectDescForDropdown === "function") {
        line = trim(window.partEffectDescForDropdown(p));
      }
    } catch (_) {}
    if (!line) line = trim(p.effects || p.effect || p.effects_text || "");
    // Prefer the ability body after "Name - body" when present.
    var dash = line.indexOf(" - ");
    if (dash > 0 && dash < 80) {
      var tail = trim(line.slice(dash + 3));
      if (tail.length > 12) line = tail;
    }
    line = stripTokenNoise(line);
    if (!line || isRawTokenLine(line)) return "";
    if (line.length > 220) line = line.slice(0, 217) + "…";
    return line;
  }

  function partRedText(p) {
    if (!p || typeof p !== "object") return "";
    var red = "";
    try {
      if (typeof window.partRedTextForDropdown === "function") {
        red = trim(window.partRedTextForDropdown(p));
      }
    } catch (_) {}
    if (!red) {
      try {
        if (typeof window.stxPearlGearCatalogRowForPart === "function") {
          var row = window.stxPearlGearCatalogRowForPart(p);
          if (row && row.redText) red = trim(row.redText);
        }
      } catch (_) {}
    }
    red = stripTokenNoise(red);
    if (!red || isRawTokenLine(red)) return "";
    if (red.length > 240) red = red.slice(0, 237) + "…";
    return red;
  }

  function pushUnique(arr, line, limit) {
    var t = trim(line);
    if (!t || isRawTokenLine(t)) return;
    var key = t.toLowerCase();
    for (var i = 0; i < arr.length; i++) {
      if (String(arr[i] || "").toLowerCase() === key) return;
    }
    if (arr.length >= (limit || 12)) return;
    arr.push(t);
  }

  function flattenSlotParts(slots) {
    var out = [];
    if (!slots || typeof slots !== "object") return out;
    Object.keys(slots).forEach(function (key) {
      var v = slots[key];
      if (!v) return;
      if (Array.isArray(v)) {
        for (var i = 0; i < v.length; i++) if (v[i] && typeof v[i] === "object") out.push(v[i]);
      } else if (typeof v === "object") {
        out.push(v);
      }
    });
    return out;
  }

  function collectSelectedPartObjects() {
    var list = [];
    var seen = {};
    function add(p) {
      if (!p || typeof p !== "object") return;
      var key =
        trim(p.idRaw || p.idraw || "") ||
        trim(p.code || p.spawnCode || "") ||
        trim(p.name || p.legendaryName || "") ||
        String(list.length);
      if (seen[key]) return;
      seen[key] = 1;
      list.push(p);
    }

    try {
      var st = window.state;
      if (st && st.mainPart) add(st.mainPart);
      if (st && st.slots) flattenSlotParts(st.slots).forEach(add);
    } catch (_) {}

    try {
      var map = window.state && window.state.__mainPartByOptionKey;
      var mainSel = document.getElementById("mainPart");
      var key = mainSel ? trim(mainSel.value) : "";
      if (map && key && typeof map.get === "function") add(map.get(key));
    } catch (_) {}

    // Fallback: resolve tokens from the live build via stats helper.
    try {
      if (typeof window.accumulateFromSelected === "function" && typeof window.getBuildStatsDebugInfo === "function") {
        var dbg = window.getBuildStatsDebugInfo();
        if (dbg && Array.isArray(dbg.resolved)) {
          dbg.resolved.forEach(function (row) {
            if (row && row.part && typeof row.part === "object") add(row.part);
          });
        }
      }
    } catch (_) {}

    return list;
  }

  function collectDropdownHumanLines() {
    var lines = [];
    var ids = [
      "mainPart",
      "rarity",
      "weaponType",
      "stx_manufacturer",
      "manufacturer",
    ];
    // Slot selects created by the builder.
    try {
      document.querySelectorAll("select[id], select[data-slot], select.stx-slot-select").forEach(function (sel) {
        if (sel && sel.id && ids.indexOf(sel.id) < 0) ids.push(sel.id);
      });
    } catch (_) {}
    ids.forEach(function (id) {
      var sel = document.getElementById(id);
      if (!sel || sel.selectedIndex < 0) return;
      var opt = sel.options[sel.selectedIndex];
      if (!opt || !opt.value) return;
      var text = stripTokenNoise(opt.textContent || opt.label || "");
      // Keep "Name — short effect" but drop empty / token-only.
      if (!text || isRawTokenLine(text) || /^(select|none|-|—)$/i.test(text)) return;
      // Skip manufacturer/rarity alone if already captured elsewhere — still useful as perk context for slots.
      if (id === "stx_manufacturer" || id === "manufacturer" || id === "rarity" || id === "weaponType") return;
      pushUnique(lines, text, 10);
    });
    return lines;
  }

  function collectStatsFromGrid() {
    var stats = [];
    try {
      if (typeof window.refreshBuildStatsCore === "function") {
        try { window.refreshBuildStatsCore(); } catch (_) {}
      }
      var grid = document.getElementById("buildStatsCoreGrid");
      if (!grid) return stats;
      grid.querySelectorAll(".cc-core-card").forEach(function (card) {
        var label = trim(
          (card.querySelector(".cc-core-card-title") || {}).textContent ||
            (card.querySelector(".cc-core-card-label, .label, .k") || {}).textContent ||
            ""
        );
        var value = trim(
          (card.querySelector(".cc-core-card-scale") || {}).textContent ||
            (card.querySelector(".cc-core-card-value, .value, .v") || {}).textContent ||
            ""
        );
        if (!label && !value) return;
        if (isRawTokenLine(label) || isRawTokenLine(value)) return;
        if (!value || value === "—" || value === "-" || /^no reliable/i.test(value)) return;
        stats.push({ label: label || "Stat", value: value });
      });
    } catch (_) {}
    return stats.slice(0, 8);
  }

  function licensedSlugFromPart(p) {
    var blob = trim((p && (p.code || p.spawnCode || p.name || p.legendaryName || "")) || "").toLowerCase();
    var m = /barrel_licensed[_-]?([a-z]+)/i.exec(blob);
    var map = {
      jak: "jakobs",
      mal: "maliwan",
      maliwan: "maliwan",
      ted: "tediore",
      tediore: "tediore",
      hyp: "hyperion",
      hyperion: "hyperion",
      tor: "torgue",
      torgue: "torgue",
      vla: "vladof",
      vladof: "vladof",
      dad: "daedalus",
      daedalus: "daedalus",
      bor: "ripper",
      borg: "ripper",
      rip: "ripper",
      ripper: "ripper",
      ord: "order",
      order: "order",
      atl: "atlas",
      atlas: "atlas",
      cov: "cov",
    };
    if (m && map[m[1].toLowerCase()]) return map[m[1].toLowerCase()];
    var names = ["jakobs", "maliwan", "torgue", "vladof", "daedalus", "tediore", "order", "ripper", "borg", "atlas", "hyperion", "cov"];
    for (var i = 0; i < names.length; i++) {
      if (blob.indexOf(names[i] + "-licen") >= 0 || blob.indexOf(names[i] + " licen") >= 0 || blob.indexOf("licensed_" + names[i].slice(0, 3)) >= 0) {
        return names[i] === "borg" ? "ripper" : names[i];
      }
    }
    return "";
  }

  function classifyPartKind(p) {
    var code = trim(p && (p.code || p.spawnCode || "")).toLowerCase();
    var pt = trim(p && (p.partType || "")).toLowerCase();
    var leaf = code.indexOf(".") >= 0 ? code.slice(code.lastIndexOf(".") + 1) : code;
    var hay = leaf + " " + pt;
    if (/firmware|augment/.test(hay)) return "firmware";
    if (/universal|part_unv_|unv_|part_stat_unv|stat_mod_unv|part_stat_(?:gun|weapon|player|char)|stat_unv/.test(hay)) {
      return "universal";
    }
    if (/secondary|part_sec_|part_stat_sec|stat_sec/.test(hay)) return "secondary";
    if (/passive_|skill|perk|progressgraph|skilltree|class\s*mod/.test(hay) || /passive|skill|perk/.test(pt)) {
      return "skill";
    }
    if (/part_stat/.test(hay)) return "universal";
    if (/comp_05_legendary|legendary|unique/.test(hay)) return "legendary";
    return "";
  }

  function partRankCount(p) {
    var n = Number(p && (p.count || p.points || p.rank || p.stacks));
    if (Number.isFinite(n) && n > 0) return Math.max(1, Math.min(5, Math.round(n)));
    return 1;
  }

  function collectPreview() {
    var itemType = readOut("stx_itemType") || (document.getElementById("stx_itemType") || {}).value || "";
    var mfrEl = document.getElementById("stx_manufacturer") || document.getElementById("manufacturer");
    var mainEl = document.getElementById("mainPart");
    var levelEl = document.getElementById("level");
    var level2El = document.getElementById("level2");
    var rarityEl = document.getElementById("rarity");
    var weaponTypeEl = document.getElementById("weaponType");
    var level = 70;
    try {
      var weaponRow = document.getElementById("weaponTypeRow");
      var useWeapon = weaponRow && weaponRow.style.display !== "none";
      level = parseInt((useWeapon ? levelEl && levelEl.value : level2El && level2El.value) || "70", 10) || 70;
    } catch (_) {}

    var mainLabel = "";
    try {
      if (mainEl && mainEl.selectedIndex >= 0) {
        mainLabel = stripTokenNoise(mainEl.options[mainEl.selectedIndex].text);
        if (isRawTokenLine(mainLabel)) mainLabel = "";
      }
    } catch (_) {}

    var mfr = "";
    try {
      if (mfrEl && mfrEl.selectedIndex >= 0) {
        mfr = stripTokenNoise(mfrEl.options[mfrEl.selectedIndex].text || mfrEl.value);
      }
    } catch (_) {}

    var rarity = "";
    try {
      if (rarityEl && rarityEl.selectedIndex >= 0) {
        var rv = trim(rarityEl.value);
        var rMap = {
          "0": "Common",
          "1": "Uncommon",
          "2": "Rare",
          "3": "Epic",
          "4": "Legendary",
          "5": "Pearlescent",
          common: "Common",
          uncommon: "Uncommon",
          rare: "Rare",
          epic: "Epic",
          legendary: "Legendary",
          pearlescent: "Pearlescent",
          pearl: "Pearlescent",
        };
        if (rv && rMap[rv.toLowerCase()]) rarity = rMap[rv.toLowerCase()];
        else rarity = stripTokenNoise(rarityEl.options[rarityEl.selectedIndex].text || rarityEl.value);
      }
    } catch (_) {}

    // Pearl override checkbox wins for card chrome.
    try {
      var pearlA = document.getElementById("stxPearlOverride");
      var pearlB = document.getElementById("ccGuidedPearlOverride");
      if ((pearlA && pearlA.checked) || (pearlB && pearlB.checked)) rarity = "Pearlescent";
    } catch (_) {}

    // Infer from selected main/rarity part when dropdown is empty.
    if (!rarity || rarity === "(select rarity tier)" || rarity === "(auto from rarity ID)") {
      try {
        var mainP = (window.state && window.state.mainPart) || null;
        if (mainP && typeof window.stxRarityTierFromPartForGrouping === "function") {
          var tierN = window.stxRarityTierFromPartForGrouping(mainP);
          if (Number.isFinite(tierN) && typeof window.rarityTierLabel === "function") {
            rarity = window.rarityTierLabel(tierN);
          } else {
            var labels = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Pearlescent"];
            if (Number.isFinite(tierN) && labels[tierN]) rarity = labels[tierN];
          }
        } else if (mainP) {
          var blob = String(mainP.itemTypeString || mainP.code || mainP.name || "").toLowerCase();
          if (/pearl|pearlescent/.test(blob)) rarity = "Pearlescent";
          else if (/legend/.test(blob)) rarity = "Legendary";
          else if (/epic/.test(blob)) rarity = "Epic";
          else if (/rare/.test(blob)) rarity = "Rare";
          else if (/uncommon/.test(blob)) rarity = "Uncommon";
          else if (/common/.test(blob)) rarity = "Common";
        }
      } catch (_) {}
    }

    var weaponType = "";
    try {
      if (weaponTypeEl) weaponType = trim(weaponTypeEl.value);
    } catch (_) {}

    var selected = collectSelectedPartObjects();
    var perkLines = [];
    var perkRows = [];
    var redText = [];
    var element = "";

    selected.forEach(function (p) {
      var name = partHumanName(p);
      var effect = partEffectLine(p);
      var red = partRedText(p);
      var pt = trim(p.partType || "").toLowerCase();
      var code = trim(p.code || p.spawnCode || "");
      var licensed = licensedSlugFromPart(p);
      var kind = classifyPartKind(p);
      var count = partRankCount(p);
      var legendaryish =
        kind === "legendary" ||
        /\blegend/i.test(String(p.legendaryName || "")) ||
        /\blegend/i.test(pt) ||
        /comp_05_legendary|part_unique_barrel/i.test(code);
      var classmodish =
        kind === "skill" ||
        kind === "universal" ||
        kind === "secondary" ||
        kind === "firmware" ||
        /firmware|augment|perk|skill|passive|universal|secondary/i.test(pt);

      if (red) pushUnique(redText, red, 4);

      var line = "";
      var pushRow = function (rowName, rowEffect, rowKind) {
        perkRows.push({
          name: rowName || name,
          effect: rowEffect || "",
          code: code,
          kind: rowKind || kind || (licensed ? "licensed" : legendaryish ? "legendary" : "skill"),
          count: count,
          licensed: licensed || "",
        });
      };
      if (licensed) {
        line = effect || name || "Licensed part";
        pushUnique(perkLines, line, 12);
        pushRow(name, effect || line, "licensed");
      } else if (legendaryish && name) {
        line = effect ? name + " — " + effect : name;
        pushUnique(perkLines, line, 12);
        pushRow(name, effect, "legendary");
      } else if (classmodish && (name || code)) {
        line = effect && name && effect.toLowerCase().indexOf(name.toLowerCase()) === -1
          ? name + " — " + effect
          : effect || name;
        if (line) pushUnique(perkLines, line, 14);
        pushRow(name, effect, kind || "skill");
      } else if (effect && name && effect.toLowerCase().indexOf(name.toLowerCase()) === -1) {
        line = name + " — " + effect;
        pushUnique(perkLines, line, 12);
        pushRow(name, effect, kind || "");
      } else if (effect) {
        pushUnique(perkLines, effect, 12);
        pushRow(name, effect, kind || "");
      } else if (name && (legendaryish || classmodish)) {
        pushUnique(perkLines, name, 12);
        pushRow(name, "", kind || (legendaryish ? "legendary" : "skill"));
      }

      var ele = trim(p.element || p.damage_type || p.damageType || "");
      if (!element && ele && !isRawTokenLine(ele)) element = ele;
    });

    // Dropdown labels as backup when slot state is thin.
    if (perkLines.length < 3) {
      collectDropdownHumanLines().forEach(function (ln) {
        var cut = ln.split(" — ")[0] || ln;
        if (cut.length > 8) {
          if (pushUnique(perkLines, ln.length <= 160 ? ln : cut, 12) !== false) {
            /* pushUnique returns undefined; just keep lines */
          }
          if (perkRows.length < 12) {
            var bits = ln.split(" — ");
            perkRows.push({ name: bits[0], effect: bits.slice(1).join(" — "), code: "" });
          }
        }
      });
    }

    var stats = collectStatsFromGrid();
    if (!perkLines.length) {
      selected.forEach(function (p) {
        var n = partHumanName(p);
        if (n) {
          pushUnique(perkLines, n, 8);
          perkRows.push({ name: n, effect: "", code: trim(p.code || "") });
        }
      });
    }

    var title = mainLabel || partHumanName(selected[0]) || itemType || "Item";
    title = stripTokenNoise(title);
    if (isRawTokenLine(title) || !title) title = itemType || "Item";

    var typeLabel = "";
    var wt = (weaponType || itemType || "").toLowerCase();
    var it = String(itemType || "").toLowerCase();
    if (/smg|submachine/.test(wt) && !/class/.test(it)) typeLabel = "Submachine Gun";
    else if (/sniper/.test(wt) && !/class/.test(it)) typeLabel = "Sniper Rifle";
    else if (/assault|ar\b/.test(wt) && !/class/.test(it)) typeLabel = "Assault Rifle";
    else if (/shotgun/.test(wt) && !/class/.test(it)) typeLabel = "Shotgun";
    else if (/pistol/.test(wt) && !/class/.test(it)) typeLabel = "Pistol";
    else if (/heavy/.test(wt) && !/class/.test(it)) typeLabel = "Heavy Weapon";
    else if (/shield/.test(wt) || /shield/.test(it)) typeLabel = "Shield";
    else if (/class/.test(wt) || /class/.test(it)) typeLabel = "Class Mod";
    else if (/rep/.test(wt) || /rep/.test(it)) typeLabel = "Repkit";
    else if (/ordnance|grenade|gadget/.test(wt) || /ordnance|grenade|gadget/.test(it)) typeLabel = "Ordnance";
    else if (/enhance/.test(wt) || /enhance/.test(it)) typeLabel = "Enhancement";

    // Classmod/shield/etc: never ship a leftover gun weaponType into the card host.
    var outWeaponType = typeLabel === "Class Mod" || typeLabel === "Shield" || typeLabel === "Repkit" || typeLabel === "Ordnance" || typeLabel === "Enhancement"
      ? ""
      : weaponType;

    return {
      title: title,
      itemType: itemType,
      type_label: typeLabel,
      manufacturer: mfr,
      weaponType: outWeaponType,
      rarity: rarity,
      level: level,
      _fromEditor: true,
      parts: perkLines.slice(0, 14),
      perk_rows: perkRows.slice(0, 16),
      part_names: selected
        .map(function (p) {
          return trim(p.code || p.spawnCode || "");
        })
        .filter(Boolean)
        .slice(0, 48),
      red_text: redText.slice(0, 3),
      stats: stats,
      element: element,
      deser: lastDeser,
      serial: lastSerial,
    };
  }

  function emitSerial() {
    var deser = readOut("outCode");
    var b85 = readOut("outCodeB85");
    if (b85 === "…" || b85 === "...") b85 = "";
    if (!b85 && typeof window.serializeToBase85 === "function" && deser.indexOf("||") >= 0) {
      try {
        b85 = trim(window.serializeToBase85(deser, undefined, true));
        var outB85 = document.getElementById("outCodeB85");
        if (outB85 && b85) outB85.value = b85;
      } catch (_) {}
    }
    lastDeser = deser;
    lastSerial = b85 && b85.indexOf("@U") === 0 ? b85 : "";
    post(TYPE.SERIAL, {
      serial: lastSerial,
      deser: lastDeser,
      ready: !!(lastSerial || (lastDeser && lastDeser.indexOf("||") >= 0)),
    });
  }

  function scheduleSerial() {
    if (serialTimer) clearTimeout(serialTimer);
    serialTimer = setTimeout(function () {
      serialTimer = 0;
      emitSerial();
    }, 120);
  }

  function schedulePreview() {
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(function () {
      previewTimer = 0;
      post(TYPE.PREVIEW, { preview: collectPreview() });
    }, 200);
  }

  function hookOutputs() {
    ["outCode", "outCodeB85", "outList", "outJson"].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      el.addEventListener("input", function () {
        scheduleSerial();
        schedulePreview();
      });
      try {
        var obs = new MutationObserver(function () {
          scheduleSerial();
          schedulePreview();
        });
        obs.observe(el, { attributes: true, characterData: true, subtree: true, childList: true });
      } catch (_) {}
    });
    document.addEventListener("change", function () {
      scheduleSerial();
      schedulePreview();
    });
    // Poll lightly while building — builder often sets .value without events.
    setInterval(function () {
      var deser = readOut("outCode");
      var b85 = readOut("outCodeB85");
      if (b85 === "…" || b85 === "...") b85 = "";
      if (deser !== lastDeser || b85 !== lastSerial) {
        scheduleSerial();
        schedulePreview();
      }
    }, 500);
  }

  function boot() {
    hookOutputs();
    post(TYPE.READY, {});
    scheduleSerial();
    schedulePreview();
  }

  window.addEventListener("message", function (event) {
    var data = event && event.data;
    if (!data || data.source !== "sqbt-shell") return;
    if (event.source && window.parent && event.source !== window.parent) return;
    if (data.type === "sqbt-load-serial") loadSerialFromShell(data);
    else if (data.type === "sqbt-load-image-recipe") loadImageRecipeFromShell(data);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
