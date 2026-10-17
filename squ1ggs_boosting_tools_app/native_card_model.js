"use strict";
(function(root) {
  const art = "coui://uiresources/_shared/assets/";
  const icons = {
    damage: "wpn_dmg",
    accuracy: "wpn_prmry_accuracy",
    reload: "wpn_prmry_reload_time",
    fire_rate: "wpn_prmry_fire_rate",
    magazine: "wpn_prmry_mag_size",
    damage_radius: "wpn_scndry_dmg_radius",
    shot_cost: "wpn_scndry_ammo_per_shot",
  };
  const types = {
    "Assault Rifle": "weap_assault",
    Pistol: "weap_pistol",
    Shotgun: "weap_shotgun",
    SMG: "weap_smg",
    "Submachine Gun": "weap_smg",
    Sniper: "weap_sniper",
    "Sniper Rifle": "weap_sniper",
    "Heavy Gun Ordnance": "heavy_weapon_torgue_rocket_launcher",
    "Heavy Weapon": "heavy_weapon_torgue_rocket_launcher",
    Shield: "energy_shield",
    Enhancement: "enhancement",
    Repkit: "rep_kit",
    Ordnance: "grenade_tediore",
    "Class Mod": "classmod",
    Classmod: "classmod",
  };
  const elements = {
    Shock: "electric",
    Electric: "electric",
    Fire: "fire",
    Cryo: "cryo",
    Corrosive: "corrosive",
    Radiation: "radiation",
    Incendiary: "fire",
    Kinetic: "",
    Impact: "impact",
  };
  // In-game manufacturer specials (weapon cards). Quotes only when confirmed from live cards.
  const MFR_WEAPON_FLAVOR = {
    jakobs: [
      "Jakobs weapons have a chance to ricochet on Critical Hits.",
      '"It ain\'t about being the best..." - Jakobs',
    ],
    maliwan: ["Maliwan weapons deal Bonus Elemental Damage."],
    torgue: ["Torgue weapons can toggle between Sticky and Impact modes."],
    vladof: ["Vladof weapons spin up, increasing Fire Rate while lowering Accuracy."],
    daedalus: ["Daedalus weapons have an alternate firing mode."],
    tediore: ["Tediore weapons are thrown like grenades on reload."],
    order: ["Order weapons charge before firing for Bonus Damage."],
    ripper: [
      "Ripper weapons charge before entering full-auto.",
      '"Rip and tear, until it is done." - Ripper',
    ],
    borg: [
      "Ripper weapons charge before entering full-auto.",
      '"Rip and tear, until it is done." - Ripper',
    ],
    atlas: ["Atlas weapons can lock onto targets."],
    hyperion: ["Hyperion weapons gain Accuracy while firing."],
    cov: ["CoV weapons never need to reload, but can overheat."],
  };
  const MFR_CLASSMOD_FLAVOR = {
    ripper: [
      "Ripper Class Mods increase Action Skill Cooldown Rate.",
      '"Rip and tear, until it is done." - Ripper',
    ],
    borg: [
      "Ripper Class Mods increase Action Skill Cooldown Rate.",
      '"Rip and tear, until it is done." - Ripper',
    ],
    jakobs: ["Jakobs Class Mods increase Critical Hit Damage."],
    maliwan: ["Maliwan Class Mods increase Status Effect Damage."],
    torgue: ["Torgue Class Mods increase Ordnance Damage."],
    vladof: ["Vladof Class Mods increase Fire Rate."],
    daedalus: ["Daedalus Class Mods increase Gun Damage."],
    tediore: ["Tediore Class Mods increase Reload Speed."],
    order: ["Order Class Mods increase Skill Damage."],
  };
  const mfrSlug = (raw) => {
    const s = String(raw || "").toLowerCase();
    for (const name of [
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
    ]) {
      if (s.includes(name)) return name === "borg" ? "ripper" : name;
    }
    return s.replace(/[^a-z0-9]+/g, "").slice(0, 24);
  };
  const number = (value) =>
    Number.isFinite(value)
      ? Number(value).toLocaleString("en-US", { maximumFractionDigits: 1 })
      : "—";
  function compact(value) {
    if (!Number.isFinite(value)) return "—";
    // Live cards keep full numbers until the millions (e.g. 13,191 Damage).
    if (Math.abs(value) >= 1e7) return number(Math.round(value / 1e6)) + "M";
    if (Math.abs(value) >= 1e6) return number(Math.round(value / 1e5) / 10) + "M";
    return number(value);
  }
  function typeIconKey(itemType) {
    if (types[itemType]) return types[itemType];
    const lower = String(itemType || "").toLowerCase();
    if (lower.includes("submachine") || lower === "smg") return "weap_smg";
    if (lower.includes("sniper")) return "weap_sniper";
    if (lower.includes("assault")) return "weap_assault";
    if (lower.includes("shotgun")) return "weap_shotgun";
    if (lower.includes("pistol")) return "weap_pistol";
    if (lower.includes("heavy")) return "heavy_weapon_torgue_rocket_launcher";
    if (lower.includes("shield")) return "energy_shield";
    if (lower.includes("rep")) return "rep_kit";
    if (lower.includes("grenade") || lower.includes("ordnance")) return "grenade_tediore";
    if (lower.includes("enhancement")) return "enhancement";
    if (lower.includes("class")) return null;
    return null;
  }
  function resolveElement(raw) {
    if (!raw) return "";
    const s = String(raw).trim();
    if (!s) return "";
    if (elements[s] != null) return elements[s];
    const lower = s.toLowerCase();
    for (const [key, val] of Object.entries(elements)) {
      if (key.toLowerCase() === lower || lower.includes(key.toLowerCase())) return val;
    }
    return lower.replace(/[^a-z]+/g, "");
  }
  function manufacturerFlavorLines(slug, itemType) {
    const isClassmod = itemType === "classmod" || itemType === "Classmod" || itemType === "Class Mod";
    const table = isClassmod ? MFR_CLASSMOD_FLAVOR : MFR_WEAPON_FLAVOR;
    const key = slug === "borg" ? "ripper" : slug;
    return table[key] || [];
  }
  function formatPrimaryStat(key, entry) {
    if (key === "magazine") return compact(entry.magazine);
    if (key === "fire_rate") {
      return Number(entry.fire_rate).toLocaleString("en-US", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      }) + "/s";
    }
    if (key === "accuracy") return number(entry.accuracy) + "%";
    if (key === "reload") return number(entry.reload) + "s";
    if (key === "damage") {
      // entry.damage is per-pellet weapon_damage (live primary).
      return formatShotDamage(entry.damage);
    }
    return number(entry[key]);
  }

  /** Parse "4,523", "4,523 x 7", or "4523x7" into per-pellet Damage for DPS fallback. */
  function parseDamageDisplay(raw) {
    const text = String(raw || "").trim();
    if (!text) return null;
    const cleaned = text.replace(/,/g, "");
    const multi = cleaned.match(/^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*x\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*$/i);
    if (multi) {
      const damage = Number(multi[1]);
      if (!Number.isFinite(damage) || damage <= 0) return null;
      // Keep per-pellet — live primary is "N x M", not the product.
      return { product: Math.round(damage), raw: text, multi: true };
    }
    const damage = Number(cleaned.replace(/[^\d.+-]/g, ""));
    if (!Number.isFinite(damage) || damage <= 0) return null;
    return { product: Math.round(damage), raw: text, multi: false };
  }

  /** Damage / DPS integers for the headline — never re-multiply pellets here. */
  function formatShotDamage(damage) {
    const dmg = Number(damage);
    if (!Number.isFinite(dmg) || dmg <= 0) return "";
    return compact(dmg);
  }

  function normalizeDamageRow(row) {
    // Preserve live "N x M" markup; only tidy single-number commas via compact
    // when the row is already a plain integer.
    if (!row || typeof row !== "object") return row;
    const text = String(row.value || "").trim();
    if (!text) return row;
    if (/\s*x\s*/i.test(text)) return row;
    const parsed = parseDamageDisplay(text);
    if (!parsed || parsed.multi) return row;
    return { ...row, value: compact(parsed.product) };
  }

  /** Map any rarity label / Nexus id onto Cohtml rarityident (never default pearl→common). */
  function rarityIdentFromEntry(entry) {
    const raw = String(entry?.rarity || "").trim();
    const lower = raw.toLowerCase();
    const blob = [
      raw,
      entry?.display_name,
      entry?.title,
      entry?.name,
      ...(Array.isArray(entry?.part_names) ? entry.part_names : []),
    ]
      .map((v) => String(v || ""))
      .join(" ")
      .toLowerCase();
    if (
      /pearl|pearlescent|06_pearl|comp_06_pearl/.test(lower) ||
      /comp_06_pearl|06_pearlescent/.test(blob) ||
      /^(?:6|06)$/.test(lower)
    ) {
      return "pearl";
    }
    if (/legend|unique|orange|05_legend|comp_05_/.test(lower) || /^(?:5|05)$/.test(lower)) {
      return "legendary";
    }
    if (/epic|purple|04_epic|comp_04_/.test(lower) || /^(?:4|04)$/.test(lower)) return "epic";
    if (/rare|blue|03_rare|comp_03_/.test(lower) || /^(?:3|03)$/.test(lower)) return "rare";
    if (/uncommon|green|02_uncommon|comp_02_/.test(lower) || /^(?:2|02)$/.test(lower)) {
      return "uncommon";
    }
    if (/common|white|01_common|comp_01_/.test(lower) || /^(?:1|01|0)$/.test(lower)) {
      return "common";
    }
    // Unknown blank → legendary chrome (better than grey common for named gear).
    if (!lower) return "legendary";
    return "common";
  }

  function toNativeCardModel(entry) {
    const rarity = rarityIdentFromEntry(entry);
    const nativeGroups =
      entry.native_groups && typeof entry.native_groups === "object" ? entry.native_groups : {};
    // Live cards define their own visible rows and icons. This is what distinguishes
    // Magazine from Shots to Overheat and prevents a synthetic Crit/headshot row.
    const nativePrimary = Array.isArray(nativeGroups.primary) ? nativeGroups.primary : [];
    const fallbackPrimaryKeys = ["damage", "accuracy", "reload", "fire_rate", "magazine"].filter(
      (key) => Number.isFinite(entry[key]) && entry[key] > 0
    );
    const primary = nativePrimary.length
      ? nativePrimary.map((row) =>
          /damage/i.test(String(row?.label || row?.loc_text || row?.ident || ""))
            ? normalizeDamageRow(row)
            : row
        )
      : fallbackPrimaryKeys.map((key) => ({
          ident: key,
          image: art + `ico_ui_art_item_stats/ico_ui_art_${icons[key]}.png`,
          comparison: "",
          value: formatPrimaryStat(key, entry),
        }));
    const nativeTertiary = Array.isArray(nativeGroups.tertiary) ? nativeGroups.tertiary : [];
    const tertiaryKeys = ["damage_radius", "shot_cost"].filter(
      (key) => Number.isFinite(entry[key]) && entry[key] > (key === "shot_cost" ? 1 : 0)
    );
    const tertiary = nativeTertiary.length
      ? nativeTertiary
      : tertiaryKeys.map((key) => ({
          image: art + `ico_ui_art_item_stats/ico_ui_art_${icons[key]}.png`,
          comparison: "",
          value:
            key === "damage_radius"
              ? number(entry.damage_radius) + "cm"
              : number(entry.shot_cost) + "/Shot",
        }));
    const red = Array.isArray(entry.red_text) ? entry.red_text : [];
    const descriptions = [
      ...new Set((entry.description_lines || entry.perk_lines || []).filter((line) => line && !red.includes(line))),
    ];
    const legendIcon = art + "ico_ui_art_discovery/ico_misc_legendaries.png";
    const secondary =
      (Array.isArray(entry.native_secondary) && entry.native_secondary.length
        ? entry.native_secondary
        : null) ||
      (Array.isArray(nativeGroups.secondary) && nativeGroups.secondary.length
        ? nativeGroups.secondary
        : null) ||
      descriptions.map((value) => ({ image: legendIcon, value, comparison: "" }));
    const element = resolveElement(entry.element || entry.damage_type);
    const element2 = resolveElement(entry.element2 || entry.damage_type2 || entry.second_element);
    const typeLabel = String(entry.type_label || entry.item_type || "").trim();
    const iconKey = typeIconKey(entry.item_type) || typeIconKey(typeLabel);
    const manufacturer = mfrSlug(entry.manufacturer);
    // Prefer native Damage primary (per-pellet or "N x M"). Fall back to entry.damage.
    const nativeDamage =
      primary.find((row) => /damage/i.test(String(row.label || row.loc_text || row.ident || ""))) ||
      null;
    const parsedNative = nativeDamage ? parseDamageDisplay(nativeDamage.value) : null;
    const shotDamage =
      (parsedNative && parsedNative.product) ||
      (Number.isFinite(entry.damage) && entry.damage > 0 ? entry.damage : null);
    const hasDamage = Number.isFinite(shotDamage) && shotDamage > 0;
    // Live cards: big DPS headline, then primary stats starting with Damage.
    // Painting Damage in both slots made DPS and Explosive/Damage look identical.
    let dpsValue = Number(entry.dps);
    if (!(Number.isFinite(dpsValue) && dpsValue > 0) && hasDamage) {
      const fr = Number(entry.fire_rate);
      // Fallback only — prefer weapon_dps_estimate. Use per-pellet × fire rate
      // (not pellet product) so we don't invent a fake total-shot DPS.
      if (Number.isFinite(fr) && fr > 0) dpsValue = Math.round(shotDamage * fr);
    }
    const hasDps = Number.isFinite(dpsValue) && dpsValue > 0;
    let headline = { value: "", loc_text: "", comparison: "" };
    let hasheadline = false;
    if (hasDps) {
      headline = { value: formatShotDamage(dpsValue), loc_text: "DPS", comparison: "" };
      hasheadline = true;
    } else if (hasDamage) {
      headline = {
        value: formatShotDamage(shotDamage),
        loc_text: String(nativeDamage?.label || nativeDamage?.loc_text || "Damage"),
        comparison: "",
      };
      hasheadline = true;
    }
    // Keep the primary Damage row — in-game shows DPS headline + Damage among the stats.
    const flavorProvided = Array.isArray(entry.manufacturer_flavor)
      ? entry.manufacturer_flavor
      : null;
    const secondaryBlob = (secondary || [])
      .map((r) => String(r?.value || ""))
      .join(" ")
      .toLowerCase();
    const hasLiveManuSecondary =
      /\[[a-z]+_icon\]|licensed|ricochet|spin up|sticky|impact|lock.?on|overheat|thrown like|charge before|alternate fir/i.test(
        secondaryBlob
      );
    // Prefer Nexus Text / live manu secondary; hardcoded quotes only as last resort.
    const flavor =
      flavorProvided && flavorProvided.length
        ? flavorProvided
        : hasLiveManuSecondary
          ? []
          : manufacturerFlavorLines(manufacturer, entry.item_type);
    const textStats = flavor
      .map((line) => String(line || "").trim())
      .filter(Boolean)
      .map((value) => ({ value, loc_text: value, comparison: "", image: "" }));
    const statsNote = String(entry.stats_note || "").trim();
    const src = String(entry.stats_source || "");
    // Only annotate when Damage/DPS themselves are coarse estimates — not Mag/Crit from Nexus.
    const showEstimateNote =
      !!entry.damage_headline_estimate ||
      (statsNote && !/partial nexus/i.test(statsNote)) ||
      (/^sqbt_/.test(src) && !src.includes("nexus"));
    if (showEstimateNote && (statsNote || src.startsWith("sqbt_"))) {
      textStats.push({
        value: statsNote || "Fallback estimate",
        loc_text: statsNote || "Fallback estimate",
        comparison: "",
        image: "",
      });
    }
    const model = {
      abbreviated: false,
      bannertype: "",
      bannertext: "",
      itemtype: "weapon",
      itembasetype: "weapon",
      rarityident: rarity,
      manufacturer,
      showlevel: entry.level != null,
      leveltoolow: false,
      level: entry.level == null ? "" : "Lvl. " + entry.level,
      thumbnailicon: iconKey ? art + `ico_ui_art_item_card_type/ico_art_item_card_${iconKey}.png` : "",
      name: String(entry.display_name || entry.card_name || entry.name || "Item"),
      showrarity: true,
      whiteheader: typeLabel || entry.item_type || "",
      headline,
      hasheadline,
      horizontalsplit: false,
      cardisflipped: false,
      primaryactive: !!primary.length,
      tertiaryactive: !!tertiary.length,
      secondaryactive: !!secondary.length,
      textstatsactive: !!textStats.length,
      firmwarevisible: false,
      firmwareident: "",
      firmware: { loc_text: "", comparison: "" },
      firmwarestring: "",
      firmwarecount: 0,
      firmwaretransfered: false,
      legendarystatvisible: false,
      // Offline host is not the in-game HUD tooltip — skip RecalculateLocation transforms
      // (undefined posx/posy/scale left a white strip and clipped secondary/perk rows).
      mousepositioned: true,
      posx: 0,
      posy: 0,
      scale: 1,
      positionunits: "px",
      compare: false,
      comparemode: false,
      showglyphs: false,
      glyphs: [],
      redtext: red.join("\n"),
      showprice: Number.isFinite(entry.value),
      price: number(entry.value),
      showelement1: !!element,
      showelement2: !!element2 && element2 !== element,
      damagetype1: element,
      damagetype2: element2 && element2 !== element ? element2 : "",
      elementtext: entry.element_text || "",
      secondelementtext: entry.element_text2 || entry.secondelementtext || "",
      elementswapdelay: 4,
      itemcardshowdelay: 0,
      text_stat_entries: textStats,
      primary_stat_entries: primary,
      tertiary_stat_entries: tertiary,
      secondary_stat_entries: secondary,
    };
    const fw = entry.firmware_block;
    if (fw && fw.firmwareident) {
      model.firmwarevisible = true;
      model.firmwareident = String(fw.firmwareident || "");
      model.firmware = fw.firmware || { loc_text: "", comparison: "" };
      model.firmwarestring = String(fw.firmwarestring || "");
      model.firmwarecount = Math.max(0, Math.min(3, Number(fw.firmwarecount) || 0));
      model.firmwaretransfered = !!fw.firmwaretransfered;
    }
    const itemType = {
      Shield: "shield",
      Ordnance: "gadget",
      Repkit: "repair_kit",
      Enhancement: "enhancement",
      Classmod: "classmod",
      "Class Mod": "classmod",
    }[entry.item_type];
    if (itemType) {
      model.itemtype = itemType;
      model.itembasetype = itemType;
      model.hasheadline = false;
      model.headline = { value: "", loc_text: "", comparison: "" };
      model.primary_stat_entries = [];
      model.tertiary_stat_entries = [];
      model.primaryactive = false;
      model.tertiaryactive = false;
      const equipment = entry.native_equipment;
      if (equipment) {
        const groups = equipment.groups || {};
        model.whiteheader = equipment.type_label || model.whiteheader;
        model.thumbnailicon = equipment.thumbnail || model.thumbnailicon;
        model.primary_stat_entries = (groups.primary || []).map((row) => {
          if (itemType !== "classmod") return row;
          // White skill glyphs vanish without a tree colour class on the wrapper.
          const comparison = String(row.comparison || "").trim();
          if (comparison) return row;
          return { ...row, comparison: "blue" };
        });
        const fwRows = Array.isArray(groups.firmware) ? groups.firmware : [];
        const legendary = Array.isArray(groups.legendary) ? groups.legendary : [];
        const baseSecondary = Array.isArray(groups.secondary) ? groups.secondary : [];
        // Prefer the live firmware widget when we can resolve an identity from equipment firmware rows.
        if (!model.firmwarevisible && fwRows.length) {
          const first = fwRows[0];
          const ident = String(first.ident || first.comparison_id || "")
            .replace(/^uistat_firmware_/, "fw_")
            .replace(/_\d+$/, "");
          const label = String(first.loc_text || first.label || first.value || "Firmware")
            .replace(/<[^>]+>/g, "")
            .replace(/\s+\d+\s*$/, "")
            .trim();
          if (ident.startsWith("fw_") || /firmware/i.test(String(first.ident || ""))) {
            model.firmwarevisible = true;
            model.firmwareident = ident.startsWith("fw_") ? ident : `fw_${ident.replace(/^fw_/, "")}`;
            model.firmware = { loc_text: label || "Firmware", comparison: "" };
            model.firmwarestring = `${Math.min(3, fwRows.length)}/3`;
            model.firmwarecount = Math.min(3, fwRows.length);
            model.firmwaretransfered = false;
          }
        }
        model.secondary_stat_entries = [
          ...baseSecondary,
          // Only dump firmware text into secondary when the widget could not light up.
          ...(model.firmwarevisible
            ? []
            : fwRows.map((row) => ({
                image: row.image || "",
                value: row.value || row.loc_text || "",
                comparison: row.comparison || "",
              }))),
          ...legendary.map((row) => ({
            image: row.image || "",
            value: row.value || row.loc_text || "",
            comparison: row.comparison || "",
          })),
        ];
        model.tertiary_stat_entries = groups.tertiary || [];
        const equipText = (groups.text || []).map((row) => ({ ...row, loc_text: row.value || row.loc_text }));
        // Manufacturer flavor first (in-game order), then equipment text stats.
        model.text_stat_entries = [...textStats, ...equipText];
        model.primaryactive = !!model.primary_stat_entries.length;
        model.secondaryactive = !!model.secondary_stat_entries.length;
        model.tertiaryactive = !!model.tertiary_stat_entries.length;
        model.textstatsactive = !!model.text_stat_entries.length;
        model.elementtext = (groups.element || []).map((row) => row.value).join(" | ") || model.elementtext;
        if (itemType === "classmod") model.extendedpassives = model.primary_stat_entries.length > 3;
        if (groups.headline?.length) {
          const h = groups.headline[0] || {};
          const hv = String(h.value || "").replace(/,/g, "").trim();
          const hn = Number(hv.replace(/[^\d.-]/g, ""));
          // Skip empty / "0" headlines so guns don't paint Damage 0 from a failed Nexus resolve.
          if (hv && hv !== "—" && !(Number.isFinite(hn) && hn <= 0)) {
            model.headline = h;
            model.hasheadline = true;
          }
        }
        model.redtext = red.length ? red.join("\n") : groups.redtext?.[0]?.value || "";
        if (!Number.isFinite(entry.value) && Number.isFinite(equipment.price)) {
          model.showprice = true;
          model.price = number(equipment.price);
        }
      } else if (secondary.length) {
        model.secondary_stat_entries = secondary;
        model.secondaryactive = true;
      }
    }
    return model;
  }
  if (typeof module !== "undefined" && module.exports) module.exports = { toNativeCardModel, compact };
  else root.SQBTNativeCard = { toNativeCardModel, compact };
})(typeof window !== "undefined" ? window : globalThis);
