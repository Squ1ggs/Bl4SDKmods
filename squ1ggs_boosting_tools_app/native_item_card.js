"use strict";
/**
 * Host for extracted BL4 Cohtml item cards.
 * Loads sqbt-card://inventory/card.html via privileged protocols registered in main.js.
 * Game UI assets under native_card_ui/ are Gearbox/2K — not MIT.
 */
(function (root) {
  const NATIVE_TYPES = new Set([
    "Assault Rifle",
    "Pistol",
    "Shotgun",
    "SMG",
    "Sniper",
    "Heavy Weapon",
    "Heavy Gun Ordnance",
    "Shield",
    "Ordnance",
    "Repkit",
    "Enhancement",
    "Classmod",
    "Class Mod",
  ]);

  const TYPE_ALIASES = {
    "assault rifle": "Assault Rifle",
    ar: "Assault Rifle",
    rifle: "Assault Rifle",
    pistol: "Pistol",
    shotgun: "Shotgun",
    smg: "SMG",
    "submachine gun": "SMG",
    sniper: "Sniper",
    "sniper rifle": "Sniper",
    heavy: "Heavy Weapon",
    "heavy weapon": "Heavy Weapon",
    "heavy gun": "Heavy Weapon",
    "heavy gun ordnance": "Heavy Gun Ordnance",
    weapon: "Assault Rifle",
    weapons: "Assault Rifle",
    shield: "Shield",
    shields: "Shield",
    energy: "Shield",
    armor: "Shield",
    grenade: "Ordnance",
    grenades: "Ordnance",
    ordnance: "Ordnance",
    gadget: "Ordnance",
    gadgets: "Ordnance",
    repkit: "Repkit",
    repkits: "Repkit",
    "rep kit": "Repkit",
    "repair kit": "Repkit",
    enhancement: "Enhancement",
    enhancements: "Enhancement",
    classmod: "Classmod",
    "class mod": "Class Mod",
    "class mods": "Class Mod",
    "class-mod": "Class Mod",
  };

  const TYPE_LABELS = {
    "Assault Rifle": "Assault Rifle",
    Pistol: "Pistol",
    Shotgun: "Shotgun",
    SMG: "Submachine Gun",
    Sniper: "Sniper Rifle",
    "Heavy Weapon": "Heavy Weapon",
    "Heavy Gun Ordnance": "Heavy Weapon",
    Shield: "Shield",
    Ordnance: "Ordnance",
    Repkit: "Repkit",
    Enhancement: "Enhancement",
    Classmod: "Class Mod",
    "Class Mod": "Class Mod",
  };

  const MFR_SLUGS = [
    "jakobs",
    "maliwan",
    "torgue",
    "vladof",
    "daedalus",
    "tediore",
    "order",
    "borg",
    "ripper",
    "atlas",
    "hyperion",
    "cov",
  ];

  const LICENSED_CODE_MFR = {
    jak: "jakobs",
    maliwan: "maliwan",
    mal: "maliwan",
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

  const ART = "coui://uiresources/_shared/assets/";
  const LEGEND_ICON = ART + "ico_ui_art_discovery/ico_misc_legendaries.png";
  const SECONDARY_KEYWORDS = [
    "critical hit damage",
    "critical hits",
    "critical hit",
    "status effect",
    "status effects",
    "magazine size",
    "fire rate",
    "reload speed",
    "damage radius",
    "splash damage",
    "gun damage",
    "weapon damage",
    "elemental damage",
    "shock damage",
    "fire damage",
    "cryo damage",
    "corrosive damage",
    "radiation damage",
    "kinetic damage",
    "pierce enemies",
    "pierce",
    "ricochet",
    "ricochets",
    "homing",
    "mirv",
    "chance",
    "ammo",
    "magazine",
    "damage",
    "accuracy",
    "reload",
  ];

  const RARITY_CANON = {
    pearl: "Pearlescent",
    pearlescent: "Pearlescent",
    "06_pearlescent": "Pearlescent",
    legendary: "Legendary",
    unique: "Legendary",
    orange: "Legendary",
    "05_legendary": "Legendary",
    epic: "Epic",
    purple: "Epic",
    "04_epic": "Epic",
    rare: "Rare",
    blue: "Rare",
    "03_rare": "Rare",
    uncommon: "Uncommon",
    green: "Uncommon",
    "02_uncommon": "Uncommon",
    common: "Common",
    white: "Common",
    "01_common": "Common",
  };

  const frames = new WeakMap();

  function canonRarity(raw) {
    const s = String(raw || "").trim();
    if (!s) return "Legendary";
    const lower = s.toLowerCase();
    if (/^(?:6|06)$/.test(lower) || /06_pearl|comp_06_pearl/.test(lower)) return "Pearlescent";
    if (/^(?:5|05)$/.test(lower) || /05_legend|comp_05_/.test(lower)) return "Legendary";
    for (const [key, val] of Object.entries(RARITY_CANON)) {
      if (lower === key || lower.includes(key)) return val;
    }
    return s;
  }

  function canonItemType(raw, fallback, partNames) {
    const s = String(raw || "").trim();
    const fb = String(fallback || "").trim();
    const partsBlob = Array.isArray(partNames)
      ? partNames.join(" ")
      : String(partNames || "");
    // Explicit Class Mod / equipment from Editor type_label must win over a gun
    // raw type leaked from pearl rarity family (TED_SG → Shotgun).
    if (
      /class\s*mod|classmod/i.test(fb) ||
      /class\s*mod|classmod/i.test(s) ||
      /classmod_/i.test(partsBlob)
    ) {
      return TYPE_ALIASES["class mod"] || "Class Mod";
    }
    // Pearl rarity id after || resolves as TED_SG / DAD_SG comps. Classmod body /
    // passive parts still mean Class Mod — do not paint a shotgun card.
    if (
      /(?:leg_body_|passive_(?:blue|green|red)|part_unv_|part_sec_|skilltree|progressgraph)/i.test(
        partsBlob
      ) &&
      (/comp_06_pearl|(?:^|[._])(?:ps|sg|sm|ar|sr|hw)(?:[._]|$)/i.test(partsBlob) ||
        /passive_(?:blue|green|red)/i.test(partsBlob)) &&
      !/\.(?:part_barrel|part_body|part_grip|part_mag|part_stock|part_sight)_/i.test(partsBlob)
    ) {
      return TYPE_ALIASES["class mod"] || "Class Mod";
    }
    // Editor Enhancement/Shield/Repkit/Ordnance must win over pearl gun dual typing.
    if (/enhancement/i.test(fb) || (/enhancement/i.test(s) && !/weapon/i.test(fb))) {
      return "Enhancement";
    }
    if (/repair\s*kit|rep\s*kit|repkit/i.test(fb) || /repair\s*kit|rep\s*kit|repkit/i.test(s)) {
      return "Repkit";
    }
    if (
      (/ordnance|grenade|gadget/i.test(fb) || /ordnance|grenade|gadget/i.test(s)) &&
      !/heavy/i.test(fb + s)
    ) {
      return "Ordnance";
    }
    if (/shield/i.test(fb) || (/shield/i.test(s) && !/class/i.test(fb))) {
      return "Shield";
    }
    if (NATIVE_TYPES.has(s)) return s;
    const key = s.toLowerCase();
    if (TYPE_ALIASES[key]) return TYPE_ALIASES[key];
    for (const [alias, typed] of Object.entries(TYPE_ALIASES)) {
      if (key.includes(alias)) return typed;
    }
    if (NATIVE_TYPES.has(fb)) return fb;
    const fbKey = fb.toLowerCase();
    if (TYPE_ALIASES[fbKey]) return TYPE_ALIASES[fbKey];
    // Weapons with unknown subtype still need a native type for the shell.
    if (/weapon|gun|legacy/i.test(s) || /weapon|gun/i.test(fb)) return "Assault Rifle";
    return s || "Assault Rifle";
  }

  function parseNumber(text) {
    if (text == null) return NaN;
    if (typeof text === "number") return Number.isFinite(text) ? text : NaN;
    let s = String(text).trim().replace(/,/g, "");
    if (!s || s === "—" || s === "-") return NaN;
    const mult = /([0-9.]+)\s*([kKmM])\b/.exec(s);
    if (mult) {
      const n = Number(mult[1]);
      if (!Number.isFinite(n)) return NaN;
      const u = mult[2].toUpperCase();
      return u === "M" ? n * 1e6 : n * 1e3;
    }
    const m = /[-+]?\d*\.?\d+/.exec(s);
    return m ? Number(m[0]) : NaN;
  }

  function isScaleStat(label, value) {
    const lab = String(label || "").toLowerCase();
    const val = String(value || "");
    return /scale|multiplier|mult\b/.test(lab) || /[×x]\s*[\d.]+/i.test(val) || /^[\d.]+x$/i.test(val.trim());
  }

  function applyStatRow(entry, label, value) {
    const lab = String(label || "").toLowerCase();
    const val = String(value || "");
    if (isScaleStat(lab, val)) {
      const pretty = `${String(label || "Stat").trim()} ${val}`.replace(/\s+/g, " ").trim();
      if (pretty && !(entry._scales || []).includes(pretty)) {
        entry._scales = entry._scales || [];
        entry._scales.push(pretty);
      }
      return;
    }
    const n = parseNumber(val);
    if (lab.includes("dps")) {
      if (Number.isFinite(n)) entry.dps = n;
      return;
    }
    if (lab.includes("damage") && !lab.includes("crit") && !lab.includes("splash") && !lab.includes("radius")) {
      const text = String(value || "").trim();
      const multi = text
        .replace(/,/g, "")
        .match(/^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*x\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*$/i);
      if (multi) {
        const per = Number(multi[1]);
        const proj = Number(multi[2]);
        if (Number.isFinite(per) && per >= 1) entry.damage = per;
        if (Number.isFinite(proj) && proj > 1) entry.projectile_count = proj;
        return;
      }
      if (Number.isFinite(n) && n >= 1) entry.damage = n;
      return;
    }
    if (lab.includes("accuracy") || lab.includes("acc")) {
      if (Number.isFinite(n)) entry.accuracy = n;
      return;
    }
    if (lab.includes("reload")) {
      if (Number.isFinite(n)) entry.reload = n;
      return;
    }
    if (lab.includes("fire") || lab.includes("firerate") || lab.includes("rate of fire") || lab.includes("rof")) {
      if (Number.isFinite(n)) entry.fire_rate = n;
      return;
    }
    if (lab.includes("mag")) {
      if (Number.isFinite(n)) entry.magazine = n;
      return;
    }
    if (lab.includes("crit")) {
      if (Number.isFinite(n)) entry.crit = n;
      return;
    }
    if (lab.includes("radius") || lab.includes("splash")) {
      if (Number.isFinite(n)) entry.damage_radius = n;
      return;
    }
    if (/shot.?cost|ammo.?per.?shot|per.?shot/.test(lab)) {
      if (Number.isFinite(n)) entry.shot_cost = n;
      return;
    }
    if (/projectile|pellet|projectiles.?per.?shot/.test(lab)) {
      if (Number.isFinite(n)) entry.projectile_count = n;
    }
  }

  function normalizeStats(stats) {
    const entry = {};
    if (!Array.isArray(stats)) return entry;
    for (const row of stats) {
      if (!row) continue;
      if (typeof row === "string") {
        const parts = row.split(/[:|·]/);
        if (parts.length >= 2) applyStatRow(entry, parts[0], parts.slice(1).join(":"));
        else applyStatRow(entry, row, row);
        continue;
      }
      applyStatRow(entry, row.label || row.key || "", row.value);
    }
    return entry;
  }

  function slugManufacturer(raw) {
    const s = String(raw || "").toLowerCase();
    for (const name of MFR_SLUGS) {
      if (s.includes(name)) return name === "borg" ? "ripper" : name;
    }
    return s.replace(/[^a-z0-9]+/g, "").slice(0, 24);
  }

  function mfrLogo(slug) {
    const key = slug === "borg" ? "ripper" : slug;
    if (!key || !MFR_SLUGS.includes(key) && key !== "ripper") return LEGEND_ICON;
    return ART + `ui_art_manufacturer_logos/ui_art_manu_logomark_${key}_small.png`;
  }

  function licensedSlugFromText(text) {
    const s = String(text || "").toLowerCase();
    const code = /barrel_licensed[_-]?([a-z]+)/i.exec(s);
    if (code && LICENSED_CODE_MFR[code[1].toLowerCase()]) {
      return LICENSED_CODE_MFR[code[1].toLowerCase()];
    }
    for (const name of MFR_SLUGS) {
      if (new RegExp(`${name}[- ]?licen`, "i").test(s) || new RegExp(`licen\\w*\\s+${name}`, "i").test(s)) {
        return name === "borg" ? "ripper" : name;
      }
    }
    return "";
  }

  function wrapSecondaryKeywords(text) {
    let out = String(text || "");
    if (!out) return "";
    const sorted = SECONDARY_KEYWORDS.slice().sort((a, b) => b.length - a.length);
    for (const word of sorted) {
      const re = new RegExp(`\\b(${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})\\b`, "gi");
      const src = out;
      out = src.replace(re, (match, _g1, offset) => {
        const head = src.slice(0, offset);
        const openPrimary = (head.match(/\[primary\]/gi) || []).length;
        const closePrimary = (head.match(/\[\/primary\]/gi) || []).length;
        const openSecondary = (head.match(/\[secondary\]/gi) || []).length;
        const closeSecondary = (head.match(/\[\/secondary\]/gi) || []).length;
        if (openPrimary > closePrimary || openSecondary > closeSecondary) return match;
        return `[secondary]${match}[/secondary]`;
      });
    }
    return out;
  }

  function formatPerkMarkup(name, effect, opts = {}) {
    const n = String(name || "").trim();
    const e = String(effect || "").trim();
    const licensed = String(opts.licensed || "").trim();
    if (licensed) {
      const pretty = licensed.charAt(0).toUpperCase() + licensed.slice(1);
      let body = e || n;
      // Strip duplicated "Jakobs-Licensed Barrel Licensed Jak" style noise.
      body = body
        .replace(new RegExp(`${pretty}[-\\s]*Licensed`, "ig"), "")
        .replace(new RegExp(`${licensed}[-\\s]*licen\\w*`, "ig"), "")
        .replace(/\bLicensed\b/gi, "")
        .replace(/\bBarrel\b/gi, "")
        .replace(/\bAccessory\b/gi, "")
        .replace(/\bJak\b/gi, "")
        .replace(/^[\s\-–—:|]+|[\s\-–—:|]+$/g, "")
        .replace(/\s+/g, " ")
        .trim();
      const marked = body ? wrapSecondaryKeywords(body) : "";
      return `[${licensed}_icon][primary]${pretty}-Licensed[/primary]${
        marked ? ` Accessory - ${marked}` : " Accessory"
      }`;
    }
    if (n && e) {
      return `[primary]${n}[/primary] - ${wrapSecondaryKeywords(e)}`;
    }
    if (n) return `[primary]${n}[/primary]`;
    if (e) return wrapSecondaryKeywords(e);
    return "";
  }

  const CLASSMOD_VH_PREFIXES = [
    "corpohacker",
    "loveless",
    "robodealer",
    "exosoldier",
    "harlowe",
    "gravitar",
    "c4sh",
    "paladin",
    "siren",
    "amon",
    "rafa",
    "vex",
  ];
  const CLASSMOD_STEM_REMAP = {
    harbringer: "harbinger",
    judgement: "judgment",
    thebestdefence: "thebestdefense",
    alcentrorafa: "alcentro",
    abajorafa: "abajo",
    arribarafa: "arriba",
  };

  function classmodPerkStem(code, name) {
    let s = String(code || name || "")
      .toLowerCase()
      .replace(/^.*\./, "")
      .replace(/[^a-z0-9]+/g, "");
    s = s.replace(
      /^(?:passivepoints|passive|skill|perk|partstat|partfirmware|firmware|partunv|unv|partsec|sec)+/,
      ""
    );
    for (const pref of CLASSMOD_VH_PREFIXES) {
      if (s.startsWith(pref) && s.length >= pref.length + 5) {
        let rest = s.slice(pref.length);
        if (rest.charAt(0) === "s" && /[a-z]/.test(rest.charAt(1))) rest = rest.slice(1);
        s = rest || s;
        break;
      }
    }
    if (CLASSMOD_STEM_REMAP[s]) s = CLASSMOD_STEM_REMAP[s];
    return s;
  }

  /** Tree-slot / tier stubs (Passive Blue 1 1 Tier 1) — no skill glyph; Nexus maps these. */
  function isClassmodTreeSlotStub(row) {
    const name = String(row?.name || "").trim();
    const code = String(row?.code || "").toLowerCase();
    // Humanized serial labels: "Passive Blue 1 1 Tier 1" / "Blue Mid 4 1" — not real perk names.
    if (
      /^(?:passive\s+)?(?:blue|green|red|white|purple)\b/i.test(name) &&
      (/\btier\b/i.test(name) || /\b(?:mid|left|right)\b/i.test(name) || /\d+\s+\d+/.test(name))
    ) {
      return true;
    }
    // Nexus progress-graph placeholders (not character perk titles).
    if (/^(?:trunk|branch)\s*-/i.test(name)) return true;
    if (/^(?:passive\s+skill)\s*-/i.test(name) && /corphacker|corpohacker|siren|exo|paladin|gravitar/i.test(name)) {
      return true;
    }
    if (/(^|[._])passive_(?:blue|green|red)_(?:mid|left|right)_/i.test(code)) return true;
    if (/(^|[._])passive_(?:blue|green|red|white|purple)(?:_|\d)/i.test(code) && /tier[_ ]?\d/i.test(code)) {
      return true;
    }
    // Stem after classmodPerkStem("passive_blue_1_1_tier_1") → blue11tier1
    const stem = classmodPerkStem(code, name);
    if (/^(?:blue|green|red|white|purple)\d/.test(stem) && /tier\d/.test(stem)) return true;
    return false;
  }

  function classmodIconUrl(row) {
    const kind = String(row?.kind || "").toLowerCase();
    if (isClassmodTreeSlotStub(row)) return "";
    const stem = classmodPerkStem(row?.code, row?.name);
    if (!stem || stem.length < 3) return LEGEND_ICON;
    if (kind === "firmware") {
      return `sqbt-asset:///img/classmod-firmware/${stem}.png`;
    }
    // Universal / secondary often lack dedicated art — keep legend pip + text.
    if (kind === "universal" || kind === "secondary" || kind === "stat") {
      return LEGEND_ICON;
    }
    // Prefer perks pack (880 stems, includes Rafa abajo/arriba); protocol falls back to passive.
    return `sqbt-asset:///img/classmod-perks/${stem}.png`;
  }

  /** White skill glyphs need .red/.blue/.green or they vanish on the cream card. */
  function classmodTreeColor(...parts) {
    const hay = parts.map((p) => String(p || "").toLowerCase()).join(" ");
    if (!hay.trim()) return "blue";
    if (/(?:^|[^a-z])red(?:[^a-z]|$)|passive_red|_red_/.test(hay)) return "red";
    if (/(?:^|[^a-z])green(?:[^a-z]|$)|passive_green|_green_/.test(hay)) return "green";
    if (/(?:^|[^a-z])blue(?:[^a-z]|$)|passive_blue|_blue_/.test(hay)) return "blue";
    return "blue";
  }

  function classmodTextKinds() {
    return new Set(["universal", "secondary", "stat", "firmware"]);
  }

  function pushClassmodTextRow(secondary, row) {
    if (!row) return;
    const kind = String(row.kind || "").toLowerCase();
    if (!classmodTextKinds().has(kind)) return;
    const count = Math.max(1, Math.min(5, Number(row.count) || 1));
    const name = classmodPerkPrettyName(row);
    if (!name && !row.code) return;
    // Skip noisy tree-slot / bare legendary comp labels.
    if (/^(?:passive\s+)?(?:blue|green|red)\s+(?:mid|left|right)/i.test(name)) return;
    if (/^\d+\s+legendary\s+\d+/i.test(name)) return;
    if (/^comp_0[1-6]_/i.test(name)) return;
    const effect = classmodPerkEffect(row);
    const licensed =
      slugManufacturer(row.licensed || "") ||
      licensedSlugFromText(row.code || row.name || "");
    const label =
      count > 1
        ? formatPerkMarkup(`${name} ×${count}`, effect, { licensed })
        : formatPerkMarkup(name, effect, { licensed }) || name;
    if (!label) return;
    secondary.push({
      image:
        kind === "firmware"
          ? classmodIconUrl({ ...row, kind: "firmware" })
          : kind === "licensed" && licensed
            ? mfrLogo(licensed)
            : LEGEND_ICON,
      value: label,
      comparison: "",
    });
  }

  function classifyClassmodPartLeaf(leaf) {
    const low = String(leaf || "")
      .toLowerCase()
      .replace(/^.*\./, "");
    if (!low) return "";
    if (/comp_0[1-4]_|comp_05_legendary$|comp_06_pearl|skin_|decal_|material_/.test(low)) return "";
    if (/part_firmware_|firmware/.test(low)) return "firmware";
    if (
      /universal|part_unv_|unv_|part_stat_unv|stat_mod_unv|part_stat_(?:gun|weapon|player|char)|stat_unv|unv_stat/.test(
        low
      )
    ) {
      return "universal";
    }
    if (/secondary|part_sec_|part_stat_sec|stat_sec|sec_stat/.test(low)) return "secondary";
    if (/passive_|skill|perk|progressgraph|skilltree/.test(low)) return "skill";
    if (/part_stat/.test(low)) return "universal";
    if (/comp_05_legendary_/.test(low)) return "legendary";
    return "";
  }

  /** Fill primary skill icons from perk_rows when Nexus left them blank.
   *  No glyph/text caps — heavily modded classmods must show every perk. */
  function pushClassmodSkillIcons(primary, props) {
    for (const row of Array.isArray(props.perk_rows) ? props.perk_rows : []) {
      if (!row) continue;
      const kind = String(row.kind || classifyClassmodPartLeaf(row.code || row.name) || "skill").toLowerCase();
      if (kind !== "skill") continue;
      if (isClassmodTreeSlotStub(row)) continue;
      const image = classmodIconUrl({ ...row, kind: "skill" });
      if (!image || image === LEGEND_ICON) continue;
      // Never push speculative sqbt-asset stems that 404 — blanks the whole glyph row.
      if (/^sqbt-asset:/i.test(image) && !/classmod-perks\/[a-z]{3,}/i.test(image)) continue;
      const count = Math.max(1, Math.min(5, Number(row.count) || 1));
      const name = classmodPerkPrettyName(row);
      primary.push({
        image,
        value: `+${count}`,
        name: name || "",
        comparison: classmodTreeColor(image, row.code, row.name, name),
      });
    }
  }

  function classmodSkillKey(row) {
    const stem = classmodPerkStem(row?.code, row?.name || row?.ident);
    if (stem) return stem;
    const name = String(row?.name || "").trim().toLowerCase();
    if (name && !/^[+×x]\d+$/i.test(name)) return name.replace(/[^a-z0-9]+/g, "");
    return "";
  }

  function classmodSkillSpillBody(row, fallbackName) {
    let count = Math.max(0, Math.min(5, Number(row?.count ?? row?.points) || 0));
    if (!count) {
      const m = String(row?.value || "").match(/^[+×x]\s*(\d+)/i);
      count = m ? Math.max(1, Math.min(5, Number(m[1]) || 1)) : 1;
    }
    const name =
      classmodPerkPrettyName(row) ||
      String(fallbackName || row?.name || "").trim() ||
      "Skill";
    if (!name || /^[+×x]\d+$/i.test(name)) return "";
    if (isClassmodTreeSlotStub({ ...row, name })) return "";
    const label = count > 1 ? `${name} ×${count}` : name;
    return formatPerkMarkup(label, classmodPerkEffect(row));
  }

  /** Keep every skill glyph; merge duplicate skills into one glyph with +N / spill ×N. */
  function capClassmodPrimaryIcons(primary, secondary, props) {
    // Prefer rows that actually have an image; empty image slots from missing
    // ProgressGraph icons must not consume the glyph budget.
    const withImage = [];
    const missingImage = [];
    for (const row of Array.isArray(primary) ? primary : []) {
      if (!row) continue;
      if (String(row.image || "").trim()) withImage.push(row);
      else missingImage.push(row);
    }
    // Prefer coui:// / data: (Nexus) over speculative sqbt-asset backfill.
    withImage.sort((a, b) => {
      const rank = (row) => {
        const img = String(row?.image || "");
        if (/^coui:/i.test(img) || /^data:/i.test(img) || /^common:/i.test(img)) return 0;
        return 1;
      };
      return rank(a) - rank(b);
    });

    const mergeBySkill = (rows) => {
      const map = new Map();
      const order = [];
      for (const row of rows) {
        if (!row) continue;
        const key =
          classmodSkillKey(row) ||
          classmodPerkStem(row.code, row.name) ||
          String(row.image || "").toLowerCase();
        if (!key) {
          order.push(row);
          continue;
        }
        let count = Math.max(1, Math.min(5, Number(row.count) || 0));
        if (!count) {
          const m = String(row.value || "").match(/^[+×x]\s*(\d+)/i);
          count = m ? Math.max(1, Math.min(5, Number(m[1]) || 1)) : 1;
        }
        const prev = map.get(key);
        if (!prev) {
          const next = { ...row, count, value: `+${count}` };
          map.set(key, next);
          order.push(next);
        } else {
          prev.count = Math.max(1, Math.min(5, (Number(prev.count) || 1) + count));
          prev.value = `+${prev.count}`;
          if (!prev.name && row.name) prev.name = row.name;
          if (!prev.image && row.image) prev.image = row.image;
        }
      }
      return order;
    };

    const keep = mergeBySkill(withImage);
    const sink = Array.isArray(secondary) ? secondary : null;
    if (!sink) return keep;

    const skillSpill = [];
    const seen = new Set();
    const pushSpill = (row, fallbackName) => {
      const key = classmodSkillKey(row) || classmodPerkStem("", fallbackName);
      let count = Math.max(0, Math.min(5, Number(row?.count ?? row?.points) || 0));
      if (!count) {
        const m = String(row?.value || "").match(/^[+×x]\s*(\d+)/i);
        count = m ? Math.max(1, Math.min(5, Number(m[1]) || 1)) : 1;
      }
      if (key && seen.has(key)) {
        const hit = skillSpill.find((s) => s.__key === key);
        if (hit) {
          const prev = Math.max(1, Number(hit.__count) || 1);
          const next = Math.max(1, Math.min(5, prev + count));
          hit.__count = next;
          const name =
            classmodPerkPrettyName(row) ||
            String(fallbackName || row?.name || "").trim() ||
            "Skill";
          hit.value = formatPerkMarkup(
            next > 1 ? `${name} ×${next}` : name,
            classmodPerkEffect(row)
          );
        }
        return;
      }
      const body = classmodSkillSpillBody({ ...row, count }, fallbackName);
      if (!body) return;
      if (key) seen.add(key);
      skillSpill.push({ image: LEGEND_ICON, value: body, comparison: "", __key: key, __count: count });
    };

    // Always list character skills under the glyph row (above other parts).
    for (const row of [...keep, ...mergeBySkill(missingImage)]) pushSpill(row, row?.name);
    for (const row of Array.isArray(props?.perk_rows) ? props.perk_rows : []) {
      const kind = String(
        row?.kind || classifyClassmodPartLeaf(row?.code || row?.name) || "skill"
      ).toLowerCase();
      if (kind !== "skill") continue;
      if (isClassmodTreeSlotStub(row)) continue;
      pushSpill(row, row?.name);
    }
    for (const raw of Array.isArray(props?.part_names) ? props.part_names : []) {
      const leaf = String(raw || "").trim();
      if (!leaf) continue;
      if (classifyClassmodPartLeaf(leaf) !== "skill") continue;
      if (isClassmodTreeSlotStub({ code: leaf, name: leaf })) continue;
      pushSpill({ code: leaf, name: humanizeClassmodPartLeaf(leaf, "skill"), kind: "skill", count: 1 }, leaf);
    }

    // Character skills first, then existing universal / secondary / firmware / Nexus stats.
    const prior = sink.slice();
    sink.length = 0;
    for (const row of skillSpill) {
      const { __key, __count, ...clean } = row;
      void __key;
      void __count;
      sink.push(clean);
    }
    for (const row of prior) sink.push(row);
    return keep;
  }

  function humanizeClassmodPartLeaf(leaf, kind) {
    let pretty = String(leaf || "")
      .replace(/^.*\./, "")
      .replace(/[_]+/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
      .trim();
    pretty = pretty.replace(/^(?:Part|Comp|Base Comp|Passive Points|Passive)\s+/i, "").trim();
    if (kind === "firmware" && pretty && !/^firmware/i.test(pretty)) {
      return `Firmware · ${pretty.replace(/^Firmware\s+/i, "")}`;
    }
    return pretty;
  }

  function appendClassmodTextFromPartNames(secondary, props) {
    const names = Array.isArray(props.part_names) ? props.part_names : [];
    if (!names.length) return;
    const seen = new Set(
      (Array.isArray(props.perk_rows) ? props.perk_rows : []).map((r) =>
        classmodPerkStem(r?.code, r?.name)
      )
    );
    for (const raw of names) {
      const leaf = String(raw || "").trim();
      if (!leaf) continue;
      const kind = classifyClassmodPartLeaf(leaf);
      if (!classmodTextKinds().has(kind)) continue;
      const stem = classmodPerkStem(leaf, "");
      if (stem && seen.has(stem)) continue;
      if (stem) seen.add(stem);
      pushClassmodTextRow(secondary, {
        kind,
        code: leaf,
        name: humanizeClassmodPartLeaf(leaf, kind),
        count: 1,
      });
    }
  }

  function augmentNexusClassmodEquipment(equipment, props) {
    const groups = equipment.groups && typeof equipment.groups === "object" ? { ...equipment.groups } : {};
    let primary = Array.isArray(groups.primary)
      ? groups.primary
          .map((row) => {
            const image = String(row?.image || "").trim();
            let value = String(row?.value || "").trim();
            if (row && Number.isFinite(Number(row.points)) && !/^[+×x]\d+/i.test(value)) {
              value = `+${Math.max(1, Math.min(5, Number(row.points) || 1))}`;
            }
            value = value.replace(/^×(\d+)$/i, "+$1");
            const comparison =
              String(row?.comparison || "").trim().toLowerCase() ||
              classmodTreeColor(image, row?.name, row?.ident, value);
            return { image, value, comparison: comparison || "blue", name: String(row?.name || "").trim() };
          })
          // Keep name-only rows so spill can list skills that lack a glyph.
          // Drop tree-slot stubs (Trunk/Branch/Passive Blue…) even when they have icons.
          .filter((row) => row && (row.image || row.name) && !isClassmodTreeSlotStub(row))
      : [];
    // NCS exact classmods often have text/secondary only (no primary icons). Nexus
    // can also return primary rows with empty images. Backfill from perk_rows only
    // when Nexus left the glyph row empty — never replace working coui:// / data:
    // skill icons with speculative sqbt-asset stems (that blanks the whole row).
    const filled = [];
    pushClassmodSkillIcons(filled, props);
    const nexusHasRealIcons = primary.some((row) =>
      /^(?:coui:|data:|common:)/i.test(String(row?.image || "").trim())
    );
    if (!primary.length && filled.length) {
      primary = filled;
    } else if (!nexusHasRealIcons && filled.length > primary.length) {
      primary = filled;
    }
    const secondary = Array.isArray(groups.secondary) ? [...groups.secondary] : [];
    // Icons cover skill ranks — list universal / secondary / firmware as text.
    // Skills spill into this list (above these rows) inside capClassmodPrimaryIcons.
    for (const row of Array.isArray(props.perk_rows) ? props.perk_rows : []) {
      const kind = String(row?.kind || classifyClassmodPartLeaf(row?.code || row?.name) || "").toLowerCase();
      if (kind === "skill") continue;
      pushClassmodTextRow(secondary, kind ? { ...row, kind } : row);
    }
    appendClassmodTextFromPartNames(secondary, props);
    primary = capClassmodPrimaryIcons(primary, secondary, props);
    return {
      ...equipment,
      type_label: String(equipment.type_label || props.type_label || "Class Mod").trim() || "Class Mod",
      groups: { ...groups, primary, secondary, tertiary: groups.tertiary || [], text: groups.text || [] },
    };
  }

  function classmodPerkMeta() {
    return root.__CLASSMOD_PERK_META || window.__CLASSMOD_PERK_META || null;
  }

  function classmodPerkEffect(row) {
    const direct = String(row?.effect || "").trim();
    if (direct) return direct;
    const meta = classmodPerkMeta();
    if (!meta) return "";
    const stem = classmodPerkStem(row?.code, row?.name);
    if (!stem) return "";
    const hit = meta[stem] || meta[stem.toLowerCase()];
    return hit && hit.description ? String(hit.description).trim() : "";
  }

  function classmodPerkPrettyName(row) {
    const direct = String(row?.name || "").trim();
    const meta = classmodPerkMeta();
    const stem = classmodPerkStem(row?.code, row?.name);
    if (meta && stem) {
      const hit = meta[stem] || meta[stem.toLowerCase()];
      if (hit && hit.name) return String(hit.name).trim();
    }
    return direct;
  }

  function buildClassmodNativeEquipment(props, description_lines) {
    if (props.native_equipment && typeof props.native_equipment === "object") {
      return augmentNexusClassmodEquipment(props.native_equipment, props);
    }
    const primary = [];
    const secondary = [];
    const text = [];
    const rows = Array.isArray(props.perk_rows) ? props.perk_rows : [];
    for (const row of rows) {
      if (!row) continue;
      const kind = String(
        row.kind || classifyClassmodPartLeaf(row.code || row.name) || "skill"
      ).toLowerCase();
      const count = Math.max(1, Math.min(5, Number(row.count) || 1));
      const name = classmodPerkPrettyName(row);
      if (!name && !row.code) continue;
      if (kind === "skill") {
        // Tree-slot stubs have no glyph — wait for Nexus native_equipment instead of blank squares.
        if (isClassmodTreeSlotStub(row)) continue;
        const image = classmodIconUrl({ ...row, kind: "skill" });
        const canIcon =
          image &&
          image !== LEGEND_ICON &&
          !(/^sqbt-asset:/i.test(image) && !/classmod-perks\/[a-z]{3,}/i.test(image));
        if (canIcon) {
          primary.push({
            image,
            value: `+${count}`,
            name: name || "",
            comparison: classmodTreeColor(image, row.code, row.name, name),
          });
        } else {
          // No glyph — keep the row so capClassmodPrimaryIcons lists it under the icons.
          primary.push({
            image: "",
            value: `+${count}`,
            name: name || "",
            comparison: "",
            count,
            code: row.code,
            effect: row.effect,
          });
        }
      } else if (classmodTextKinds().has(kind)) {
        pushClassmodTextRow(secondary, { ...row, kind });
      } else if (kind === "legendary" || kind === "unique" || kind === "licensed" || kind === "pearl") {
        // Legendary cores / uniques are usually the item name — skip raw comp labels.
        continue;
      }
    }
    if (!primary.length) pushClassmodSkillIcons(primary, props);
    appendClassmodTextFromPartNames(secondary, props);
    const cappedPrimary = capClassmodPrimaryIcons(primary, secondary, props);
    if (!cappedPrimary.length && !secondary.length) {
      for (const line of description_lines || []) {
        const body = String(line || "").trim();
        if (!body) continue;
        // Skip skill-like tree slot labels when we could not resolve icons.
        if (/^(?:passive\s+)?(?:blue|green|red)\s+(?:mid|left|right)/i.test(body)) continue;
        if (/^\d+\s+legendary\s+\d+/i.test(body)) continue;
        secondary.push({ image: LEGEND_ICON, value: wrapSecondaryKeywords(body), comparison: "" });
        if (secondary.length >= 8) break;
      }
    }
    // Optional Skill Damage / Kinetic Damage style lines from props.stats.
    if (Array.isArray(props.stats)) {
      for (const row of props.stats) {
        if (!row) continue;
        const label = String(row.label || row.key || "").trim();
        const value = String(row.value || "").trim();
        if (!label || !value) continue;
        if (!/damage|skill|kinetic|cooldown|fire|crit/i.test(label)) continue;
        text.push({
          value: `[primary]${label}[/primary] ${value}`,
          loc_text: `[primary]${label}[/primary] ${value}`,
          comparison: "",
        });
        if (text.length >= 4) break;
      }
    }
    if (!cappedPrimary.length && !secondary.length && !text.length) return null;
    return {
      type_label: String(props.type_label || "Class Mod").trim() || "Class Mod",
      groups: { primary: cappedPrimary, secondary, tertiary: [], text },
    };
  }

  function buildNativeSecondary(props, description_lines, scales) {
    if (Array.isArray(props.native_secondary) && props.native_secondary.length) {
      return props.native_secondary;
    }
    const rows = [];
    const structured = Array.isArray(props.perk_rows) ? props.perk_rows : [];
    for (const row of structured) {
      if (!row) continue;
      const count = Math.max(1, Math.min(5, Number(row.count) || 1));
      const baseName = String(row.name || "").trim();
      const name = count > 1 && baseName && !/×\d/.test(baseName) ? `${baseName} ×${count}` : baseName;
      const licensed =
        slugManufacturer(row.licensed || "") ||
        licensedSlugFromText(row.code || row.name || row.effect || "");
      const effect = String(row.effect || "").trim();
      const kind = String(row.kind || "").toLowerCase();
      const value =
        (row.value && kind !== "skill" ? row.value : "") ||
        formatPerkMarkup(name, effect, { licensed });
      if (!value) continue;
      const image =
        kind === "firmware"
          ? classmodIconUrl({ ...row, kind: "firmware" })
          : licensed
            ? mfrLogo(licensed)
            : LEGEND_ICON;
      rows.push({
        image,
        value: kind === "firmware" && !/^firmware/i.test(value) ? formatPerkMarkup("Firmware", value.replace(/^Firmware\s*[·\-–]\s*/i, "")) : value,
        comparison: "",
      });
      if (rows.length >= 10) break;
    }
    if (!rows.length) {
      for (const line of description_lines || []) {
        const text = String(line || "").trim();
        if (!text) continue;
        const licensed = licensedSlugFromText(text);
        let value = text;
        if (licensed && !/\[primary\]/i.test(text)) {
          value = formatPerkMarkup(
            "",
            text.replace(new RegExp(`${licensed}[- ]?licensed[:\\s-]*`, "i"), "").trim(),
            { licensed }
          );
        } else if (!/\[primary\]/i.test(text) && text.includes(" — ")) {
          const [head, ...rest] = text.split(" — ");
          value = formatPerkMarkup(head, rest.join(" — "));
        } else if (!/\[primary\]/i.test(text) && text.includes(" - ")) {
          const dash = text.indexOf(" - ");
          value = formatPerkMarkup(text.slice(0, dash), text.slice(dash + 3));
        } else if (!/\[(primary|secondary)\]/i.test(text)) {
          value = wrapSecondaryKeywords(text);
        }
        rows.push({ image: licensed ? mfrLogo(licensed) : LEGEND_ICON, value, comparison: "" });
        if (rows.length >= 10) break;
      }
    }
    for (const scale of scales || []) {
      if (rows.length >= 12) break;
      rows.push({
        image: ART + "ico_ui_art_item_stats/ico_ui_art_wpn_scndry_dmg_radius.png",
        value: wrapSecondaryKeywords(String(scale)),
        comparison: "",
      });
    }
    return rows;
  }

  /** Merge firmware into secondary only when the live firmware widget cannot paint. */
  function mergeFirmwareIntoSecondary(secondary, props) {
    const block = props?.firmware_block || props?.raw?.firmware_block;
    // Only suppress secondary firmware text when the widget has a real ident class.
    if (block && String(block.firmwareident || "").trim()) {
      return Array.isArray(secondary) ? [...secondary] : [];
    }
    const rows = Array.isArray(secondary) ? [...secondary] : [];
    const seen = new Set(
      rows.map((r) => String(r?.value || "").replace(/<[^>]+>/g, "").toLowerCase().trim()).filter(Boolean)
    );
    const nexusFw = Array.isArray(props?.native_firmware) ? props.native_firmware : [];
    for (const row of nexusFw) {
      if (!row) continue;
      const value = String(row.value || "").trim();
      if (!value) continue;
      const dedupe = value.replace(/<[^>]+>/g, "").toLowerCase().trim();
      if (seen.has(dedupe)) continue;
      seen.add(dedupe);
      rows.push({
        image: row.image || classmodIconUrl({ kind: "firmware", name: value, code: value }),
        value,
        comparison: "",
      });
    }
    // Perk-row stubs only when Nexus did not supply firmware UI lines.
    if (nexusFw.length) return rows;
    const perks = Array.isArray(props?.perk_rows) ? props.perk_rows : [];
    for (const row of perks) {
      if (!row) continue;
      const kind = String(row.kind || "").toLowerCase();
      const code = String(row.code || row.name || "").toLowerCase();
      if (kind !== "firmware" && !/part_firmware_|firmware/.test(code)) continue;
      const name = String(row.name || "").trim() || "Firmware";
      const effect = String(row.effect || "").trim();
      const value =
        (row.value && String(row.value).trim()) ||
        formatPerkMarkup(
          /^firmware/i.test(name) ? name : `Firmware · ${name}`,
          effect
        );
      if (!value) continue;
      const dedupe = value.replace(/<[^>]+>/g, "").toLowerCase().trim();
      if (seen.has(dedupe)) continue;
      seen.add(dedupe);
      rows.push({
        image: classmodIconUrl({ ...row, kind: "firmware" }),
        value,
        comparison: "",
      });
    }
    return rows;
  }

  function buildFirmwareBlock(props) {
    const block = props?.firmware_block || props?.raw?.firmware_block;
    if (block && block.firmwareident) return block;
    const rows = Array.isArray(props?.native_firmware) ? props.native_firmware : [];
    if (!rows.length) {
      // Last resort: perk_rows part_firmware_* stem → icon class.
      const perks = Array.isArray(props?.perk_rows) ? props.perk_rows : [];
      for (const row of perks) {
        const code = String(row?.code || row?.name || "");
        const m = code.match(/part_firmware_([a-z0-9_]+)/i);
        if (!m) continue;
        const stem = m[1].toLowerCase().replace(/_+/g, "_");
        const ident = stem.startsWith("fw_") ? stem : `fw_${stem}`;
        const name = String(row.name || "").replace(/^Firmware\s*[·\-–]\s*/i, "").trim() || stem.replace(/_/g, " ");
        return {
          firmwareident: ident,
          firmware: { loc_text: name.replace(/\b\w/g, (c) => c.toUpperCase()), comparison: "" },
          firmwarestring: "1/3",
          firmwarecount: 1,
          firmwaretransfered: false,
        };
      }
      return null;
    }
    const tiers = rows
      .map((row) => ({
        ...row,
        tier: Number(row.tier) || Number((String(row.ident || "").match(/_(\d+)$/) || [])[1]) || 1,
      }))
      .sort((a, b) => b.tier - a.tier);
    const best = tiers[0];
    const count = Math.max(1, Math.min(3, best.tier || tiers.length));
    let name = String(best.label || "").replace(/\s+\d+\s*$/, "").trim();
    if (!name) {
      const fromId = String(best.comparison_id || best.ident || "")
        .replace(/^fw_/, "")
        .replace(/_/g, " ")
        .trim();
      name = fromId.replace(/\b\w/g, (c) => c.toUpperCase()) || "Firmware";
    }
    let ident = String(best.comparison_id || "").trim();
    if (!ident) {
      const fromIdent = String(best.ident || "")
        .replace(/^uistat_firmware_/, "fw_")
        .replace(/_\d+$/, "")
        .trim();
      ident = fromIdent.startsWith("fw_") ? fromIdent : "";
    }
    if (!ident) return null;
    return {
      firmwareident: ident,
      firmware: { loc_text: name, comparison: "" },
      firmwarestring: `${count}/3`,
      firmwarecount: count,
      firmwaretransfered: false,
    };
  }

  function propsToEntry(props) {
    const p = props && typeof props === "object" ? props : {};
    const itemType = canonItemType(
      p.itemType || p.type_label || p.weaponType || p.type,
      p.type_label || p.itemType || p.category,
      p.part_names
    );
    const stats = normalizeStats(p.stats);
    const parts = Array.isArray(p.parts)
      ? p.parts
          .map((x) => String(x || "").trim())
          .filter((line) => line && !/^(\{[\d:\s\[\],]+\}|\d+:\d+)(\s|$)/.test(line))
      : [];
    const red = Array.isArray(p.red_text)
      ? p.red_text.map((x) => String(x || "").trim()).filter(Boolean)
      : [];
    const description_lines = parts.slice(0, 12);
    const listing = String(p.listing || "").trim();
    if (listing && !/^(legit|modded|gzo|lootlemon)$/i.test(listing)) {
      description_lines.unshift(listing);
    }
    const serialRaw = String(p.serial || "").trim();
    if (serialRaw.startsWith("@U")) {
      const snip =
        serialRaw.length > 56 ? `${serialRaw.slice(0, 52)}…` : serialRaw;
      if (!description_lines.some((line) => String(line).startsWith("@U"))) {
        description_lines.push(snip);
      }
    }
    const levelRaw = p.level;
    let level = null;
    if (levelRaw != null && String(levelRaw).trim() !== "") {
      const n = parseNumber(levelRaw);
      level = Number.isFinite(n) ? Math.round(n) : null;
    }
    const manufacturer = slugManufacturer(p.manufacturer) || String(p.manufacturer || "").trim();
    const isClassmod = itemType === "Classmod" || /class\s*mod/i.test(String(p.type_label || ""));
    // Fill empty classmod perk effects from skill-tree meta when Serials only has names.
    const perkProps = isClassmod && Array.isArray(p.perk_rows)
      ? {
          ...p,
          perk_rows: p.perk_rows.map((row) => {
            if (!row || String(row.effect || "").trim()) return row;
            const effect = classmodPerkEffect(row);
            const name = classmodPerkPrettyName(row) || row.name;
            return effect || name !== row.name ? { ...row, effect, name } : row;
          }),
        }
      : p;
    const native_equipment = isClassmod
      ? buildClassmodNativeEquipment(perkProps, description_lines)
      : p.native_equipment && typeof p.native_equipment === "object"
        ? p.native_equipment
        : null;
    // Prefer Nexus UI secondary (Trample / Alt Fire / licensed) when present,
    // then merge firmware perk rows only if the live firmware widget cannot paint.
    const firmware_block = buildFirmwareBlock(perkProps);
    const native_secondary = isClassmod
      ? []
      : mergeFirmwareIntoSecondary(
          Array.isArray(p.native_secondary) && p.native_secondary.length
            ? p.native_secondary
            : buildNativeSecondary(p, description_lines, stats._scales || []),
          { ...perkProps, firmware_block }
        );
    // Merge Nexus red text when @U decode left it empty.
    const redMerged = red.length
      ? red
      : Array.isArray(p.red_text)
        ? p.red_text.map((x) => String(x || "").trim()).filter(Boolean)
        : [];
    const element = String(p.element || p.damage_type || "").trim();
    let element2 = String(p.element2 || p.damage_type2 || p.second_element || "").trim();
    const elementText2 = String(p.element_text2 || p.raw?.element_text2 || "").trim();
    // Mode02 elemental DPS implies a second element bar even when label is thin.
    if (!element2 && elementText2) {
      const names = Array.isArray(p.part_names) ? p.part_names.join(" ") : "";
      const blob = `${names} ${element}`.toLowerCase();
      for (const el of ["shock", "fire", "incendiary", "cryo", "corrosive", "radiation"]) {
        if (blob.includes(el) && !element.toLowerCase().includes(el)) {
          element2 = el === "incendiary" ? "Fire" : el.charAt(0).toUpperCase() + el.slice(1);
          break;
        }
      }
      if (!element2) element2 = "Shock";
    }
    const rawDamage = parseNumber(p.damage != null ? p.damage : p.raw?.damage);
    const rawDps = parseNumber(p.dps != null ? p.dps : p.raw?.dps);
    const damage =
      Number.isFinite(rawDamage) && rawDamage > 0
        ? rawDamage
        : Number.isFinite(stats.damage) && stats.damage > 0
          ? stats.damage
          : undefined;
    const dps =
      Number.isFinite(rawDps) && rawDps > 0
        ? rawDps
        : Number.isFinite(stats.dps) && stats.dps > 0
          ? stats.dps
          : undefined;
    const equipPrice = parseNumber(p.native_equipment?.price ?? native_equipment?.price);
    const flavorFromNexus = Array.isArray(p.manufacturer_flavor)
      ? p.manufacturer_flavor
      : Array.isArray(p.native_text)
        ? p.native_text
        : Array.isArray(p.raw?.native_text)
          ? p.raw.native_text
          : undefined;
    return {
      display_name: (() => {
        const raw = String(p.display_name || p.title || p.name || "").trim();
        // Never paint a raw @U serial as the item name on the card.
        if (!raw || /^@U/i.test(raw)) {
          const equipLabel = String(
            native_equipment?.type_label || p.type_label || TYPE_LABELS[itemType] || itemType || ""
          ).trim();
          if (isClassmod) return equipLabel && !/^class\s*mod$/i.test(equipLabel) ? equipLabel : "Class Mod";
          return equipLabel || "Item";
        }
        return raw;
      })(),
      // Serial-backed pearl markers override stale dropdown/catalog rarity.
      rarity: [...(Array.isArray(p.name_parts) ? p.name_parts : []),
        ...(Array.isArray(p.part_names) ? p.part_names : [])]
        .some((part) => /(?:^|\.)(?:base_)?comp_06_pearl(?:escent)?(?:_|$)/i.test(String(part).replace(/"/g, "")))
        ? "Pearlescent" : canonRarity(p.rarity),
      manufacturer,
      item_type: itemType,
      type_label: String(p.type_label || TYPE_LABELS[itemType] || itemType).trim(),
      level,
      element,
      element2,
      element_text: String(p.element_text || "").trim(),
      element_text2: elementText2,
      description_lines,
      perk_lines: description_lines,
      native_secondary,
      native_firmware: Array.isArray(p.native_firmware) ? p.native_firmware : p.raw?.native_firmware,
      firmware_block,
      native_equipment: native_equipment || undefined,
      native_groups:
        p.native_groups && typeof p.native_groups === "object"
          ? p.native_groups
          : p.raw?.native_groups,
      manufacturer_flavor: flavorFromNexus,
      red_text: redMerged,
      dps,
      damage,
      accuracy: Number.isFinite(parseNumber(p.accuracy)) ? parseNumber(p.accuracy) : stats.accuracy,
      reload: Number.isFinite(parseNumber(p.reload)) ? parseNumber(p.reload) : stats.reload,
      fire_rate: Number.isFinite(parseNumber(p.fire_rate)) ? parseNumber(p.fire_rate) : stats.fire_rate,
      magazine: Number.isFinite(parseNumber(p.magazine)) ? parseNumber(p.magazine) : stats.magazine,
      crit: Number.isFinite(parseNumber(p.crit)) ? parseNumber(p.crit) : stats.crit,
      damage_radius: Number.isFinite(parseNumber(p.damage_radius))
        ? parseNumber(p.damage_radius)
        : stats.damage_radius,
      projectile_count: Number.isFinite(parseNumber(p.projectile_count))
        ? parseNumber(p.projectile_count)
        : stats.projectile_count,
      shot_cost: Number.isFinite(parseNumber(p.shot_cost))
        ? parseNumber(p.shot_cost)
        : stats.shot_cost,
      value: Number.isFinite(parseNumber(p.value))
        ? parseNumber(p.value)
        : Number.isFinite(equipPrice)
          ? equipPrice
          : undefined,
      name_status: p.name_status || "",
      stats_source: String(p.stats_source || "").trim(),
      stats_note: String(p.stats_note || "").trim(),
      damage_headline_estimate: !!p.damage_headline_estimate,
      set: String(p.set || "").trim(),
    };
  }

  function fitBoxFor(host) {
    return (
      host.closest(".sqbt-catalog-native-preview, .sqbt-editor-card-host") ||
      host.parentElement ||
      host
    );
  }

  function applyNativeCardFit(host, naturalHeight, opts = {}) {
    if (!host || !host.isConnected) return;
    const force = !!opts.force;
    const frame = host.querySelector(".sqbt-native-card-frame");
    const naturalW = Math.max(280, parseFloat(host.dataset.naturalWidth) || 546);
    let h = Number(naturalHeight);
    if (!Number.isFinite(h) || h <= 0) {
      h = parseFloat(host.dataset.naturalHeight) || (frame && parseFloat(frame.style.height)) || 360;
    }
    h = Math.ceil(h);
    const prevH = parseFloat(host.dataset.naturalHeight) || 0;
    if (!force && prevH > 0 && Math.abs(h - prevH) < 3) {
      // Tiny height jitter — keep zoom/layout stable (tall classmods with async perk icons).
      return;
    }
    host.dataset.naturalHeight = String(h);
    const box = fitBoxFor(host);
    // Leave a few px so border-image / zoom rounding does not clip the right edge.
    const availW = Math.max(120, (box.clientWidth || naturalW) - 8);
    // Width-only fit: tall classmods must stay readable and scroll in the preview
    // host — never shrink to a thin strip to fit viewport height (old min 0.08).
    const scale = Math.min(1, availW / naturalW);
    // Editor sidebar is ~200–280px — allow tighter zoom so the craft iframe stays large.
    const minZoom = host.closest?.(".sqbt-editor-card-host") ? 0.38 : 0.72;
    const next = Math.max(minZoom, scale);
    const prevZoom = parseFloat(host.style.zoom) || 0;
    // Chromium `zoom` scales paint + layout; skip micro updates that thrash with ResizeObserver.
    if (!force && prevZoom > 0 && Math.abs(next - prevZoom) < 0.01) return;
    host.style.zoom = String(next);
  }

  function scheduleNativeCardFit(host, naturalHeight, opts = {}) {
    if (!host) return;
    const h = Number(naturalHeight);
    if (Number.isFinite(h) && h > 0) host._sqbtPendingFitH = h;
    if (opts.force) host._sqbtFitForce = true;
    if (host._sqbtFitTimer) return;
    host._sqbtFitTimer = setTimeout(() => {
      host._sqbtFitTimer = 0;
      const force = !!host._sqbtFitForce;
      host._sqbtFitForce = false;
      const pending = host._sqbtPendingFitH;
      host._sqbtPendingFitH = undefined;
      applyNativeCardFit(host, pending, { force });
    }, 70);
  }

  function watchNativeCardFit(host) {
    if (!host || host._sqbtFitWatch) return;
    host._sqbtFitWatch = true;
    const refit = () => scheduleNativeCardFit(host);
    if (typeof ResizeObserver === "function") {
      const ro = new ResizeObserver(refit);
      ro.observe(fitBoxFor(host));
      host._sqbtFitRo = ro;
    }
    window.addEventListener("resize", refit);
    host._sqbtFitOnResize = refit;
  }

  function fillNativeItemCard(host, entry, options = {}) {
    const modelApi = root.SQBTNativeCard;
    if (!host || !entry || !modelApi || typeof modelApi.toNativeCardModel !== "function") {
      return null;
    }
    if (modelApi.enabled === false) return null;
    if (!NATIVE_TYPES.has(entry.item_type)) return null;

    const widthPx = Math.max(280, Number(options.width) || 546);
    host.classList.add("sqbt-native-card");
    host.style.width = `${widthPx}px`;
    host.style.maxWidth = "none";
    host.dataset.naturalWidth = String(widthPx);
    host.dataset.rarity = String(entry.rarity || "unknown").toLowerCase();
    // Keep prior zoom when reusing the iframe — clearing it causes shrink→grow shake
    // while tall classmods settle perk icons / height.
    const reusingFrame = !!host.querySelector("iframe.sqbt-native-card-frame");
    if (!reusingFrame) host.style.zoom = "";

    // Catalog paints thin then enriched into the same iframe. Without a generation
    // token, a slow thin prepare can finish last and wipe Damage / classmod icons.
    const paintGen = String((Number(host.dataset.nativePaintGen) || 0) + 1);
    host.dataset.nativePaintGen = paintGen;

    let model = modelApi.toNativeCardModel(entry);
    const api = root.sqbt;

    const deliver = (frame, m) => {
      if (!frame || !frame.contentWindow) return;
      if (host.dataset.nativePaintGen !== paintGen) return;
      frames.set(frame.contentWindow, { frame, model: m, host });
      try {
        frame.contentWindow.postMessage({ type: "sqbt-card-model", model: m }, "*");
      } catch {
        /* frame not ready */
      }
      watchNativeCardFit(host);
      // Do not force-fit before first settle size from the iframe (avoids empty→tall thrash).
      if (host.dataset.naturalHeight) scheduleNativeCardFit(host);
    };

    const prepare = (m) =>
      api && typeof api.inlineCardAssets === "function"
        ? Promise.resolve(api.inlineCardAssets(m))
            .then((res) => (res && res.model ? res.model : m))
            .catch(() => m)
        : Promise.resolve(m);

    // Reuse the iframe — destroying it on every tick is the flash / “adds another” glitch.
    const existing = host.querySelector("iframe.sqbt-native-card-frame");
    if (existing) {
      prepare(model).then((m) => deliver(existing, m));
      return host;
    }

    host.replaceChildren();
    const frame = document.createElement("iframe");
    frame.className = "sqbt-native-card-frame";
    frame.title = String(entry.display_name || "Item");
    frame.loading = "eager";
    frame.tabIndex = -1;
    frame.setAttribute("sandbox", "allow-scripts allow-same-origin");
    frame.setAttribute("scrolling", "no");
    frame.style.width = "100%";
    frame.style.minHeight = "200px";
    host.appendChild(frame);

    let posted = false;
    const register = () => {
      if (posted) return;
      posted = true;
      prepare(model).then((m) => {
        model = m;
        deliver(frame, m);
      });
    };
    frame.addEventListener("load", register, { once: true });
    frame.src = "sqbt-card://inventory/card.html?v=1623";
    return host;
  }

  function buildNativeItemCardEl(props, options = {}) {
    const entry = propsToEntry(props);
    const hasSignal =
      (entry.display_name && entry.display_name !== "Item") ||
      Number.isFinite(entry.dps) ||
      Number.isFinite(entry.damage) ||
      (Array.isArray(entry.description_lines) && entry.description_lines.length > 0) ||
      (Array.isArray(entry.red_text) && entry.red_text.length > 0) ||
      Boolean(entry.manufacturer) ||
      Boolean(props && props.rarity) ||
      (entry.native_equipment && entry.native_equipment.groups) ||
      (entry.native_groups &&
        ((entry.native_groups.primary || []).length ||
          (entry.native_groups.secondary || []).length));
    if (!hasSignal && !options.force) return null;

    // Prefer updating an existing host the caller already mounted.
    if (options.host && options.host.nodeType === 1) {
      const filled = fillNativeItemCard(options.host, entry, options);
      return filled || null;
    }

    const host = document.createElement("div");
    const filled = fillNativeItemCard(host, entry, options);
    if (!filled) return null;
    return host;
  }

  window.addEventListener("message", (event) => {
    const record = event.source && frames.get(event.source);
    if (!record || !record.frame.isConnected) return;
    const data = event.data;
    if (!data || typeof data !== "object") return;
    if (data.type === "sqbt-card-ready") {
      try {
        record.frame.contentWindow.postMessage({ type: "sqbt-card-model", model: record.model }, "*");
      } catch {
        /* ignore */
      }
    } else if (data.type === "sqbt-card-size") {
      const height = Number(data.height);
      if (Number.isFinite(height) && height > 0 && height < 20000) {
        const h = Math.ceil(height);
        const prev = parseFloat(record.frame.style.height) || 0;
        if (prev <= 0 || Math.abs(h - prev) >= 3) {
          record.frame.style.height = `${h}px`;
        }
        if (record.host) scheduleNativeCardFit(record.host, h);
      }
    } else if (data.type === "sqbt-card-rendered") {
      record.frame.dataset.rendered = "true";
      const height = Number(data.height);
      if (Number.isFinite(height) && height > 0 && height < 20000) {
        const h = Math.ceil(height) + 4;
        const prev = parseFloat(record.frame.style.height) || 0;
        if (prev <= 0 || Math.abs(h - prev) >= 3) {
          record.frame.style.height = `${h}px`;
        }
        // Prefer final rendered height; force once so settle wins over intermediate sizes.
        if (record.host) scheduleNativeCardFit(record.host, h, { force: true });
      }
      if (Array.isArray(data.errors) && data.errors.length) {
        record.frame.dataset.renderErrors = JSON.stringify(data.errors);
      }
    } else if (data.type === "sqbt-card-error") {
      record.frame.dataset.renderErrors = JSON.stringify([String(data.message || "Card failed")]);
    }
  });

  root.SQBTNativeItemCard = {
    propsToEntry,
    fillNativeItemCard,
    buildNativeItemCardEl,
    canonItemType,
    canonRarity,
  };
})(typeof window !== "undefined" ? window : globalThis);
