# Squ1ggs Boosting Tools

Borderlands 4 boosting toolkit — **desktop app (.exe)** + **SDK mod**.  
Author: **[Squ1ggs](https://github.com/Squ1ggs)** · Bridge: `http://127.0.0.1:49775` · **GPL-3.0**

**Repo:** [github.com/Squ1ggs/Bl4SDKmods](https://github.com/Squ1ggs/Bl4SDKmods)

**Distribution:** [GitHub / this repo only](https://github.com/Squ1ggs/Bl4SDKmods) — **not** on the [BL Oak2 Mod DB](https://bl-sdk.github.io/oak2-mod-db/).

---

## Interface

Use the **desktop app** for the full interface. The SDK mod supplies the localhost bridge and lightweight console commands; it does not register an additional pause-menu or BLImGui panel.

---

## Quick start (MSBT-style)

1. Run **Squ1ggs Boosting Tools** (desktop app) → browse to Borderlands 4 if needed → **Install SDK + Squ1ggs mod** (pulls official [oak2-mod-manager](https://github.com/bl-sdk/oak2-mod-manager/releases) when the base SDK is missing).
2. **Fully restart Borderlands 4**.
3. Refresh status in the app — mod version should match (**3.7.0**).

Same idea as Matt's SDK Boosting Tools: exe installs the mod, restart game, control from outside.

**Thanks:** GZO catalog/site by **Ynot**, catalog API by **Mattmab** — SQBT only reads that API. Thank you to **Tobgun** for feedback, ideas, testing, and bug reports.

---

## Desktop app tabs

| Tab | Highlights |
|-----|------------|
| **Home** | MAX ALL, currency/XP/SDU, serial delivery, golden chest, party kick |
| **Player** | Dev perks, gravity, force fly, ammo regen, freecam, party teleports |
| **Challenges** | UVHM workflow start/cancel/resume and challenge bulk actions |
| **Loot** | **Loot Pool Spawner** + **Legit Item Forge** (validate/build/give) |
| **Serials** | GZO + Lootlemon catalog delivery, serial convert |
| **Mobility** | Presets, movement sliders, noclip, time dilation, slot teleports |
| **Vehicle** | Vehicle handling + personal vehicle spawn (embedded bl4_vehicle_movement) |
| **Damage & More** | Combat damage sliders (embedded) |
| **Kits & Shields** | Repair kits, shields, ammo regen, cooldowns (embedded) |
| **World** | Map/station travel and world utilities |
| **Mob and IO Spawner** | Spawn mixes, NPCs, AI, bosses, IO objects and encounter presets |
| **Loot Shapes** | Arrange ground loot (circle, vault, firehawk, grid, rarity lanes, and more); Place Fully for co-op joiners |
| **Keybinds** | Custom in-game action keybinds |
| **Support** | Discord invite/QR code, Ko-fi link and release information |

**GZO Codes:** catalog from [Borderlands 4 Items on save-editor.be](https://save-editor.be/GZO/Borderlands4/Codes.html) (site/catalog by **Ynot**). Catalog API by **Mattmab** — SQBT only reads that API to cache and deliver serials. Thank you to **Tobgun** for feedback, ideas, testing, and bug reports.

Searchable catalog dropdowns are provided directly by the desktop app.

---

## Install (folder build)

Requires [Oak2 Mod Manager v0.3+](https://github.com/bl-sdk/oak2-mod-manager/releases/tag/v0.3).

1. Copy the `Squ1ggsBoostingTools` folder into `sdk_mods` (do not nest a second `Squ1ggsBoostingTools` folder inside it).
2. Enable **Squ1ggs's Boosting Tools** in the mods menu.

**Tuning:** Player / Vehicle / Damage / Kits & Shields tabs work standalone or alongside the separate tuning mods — if a standalone mod is enabled, SQBT uses it automatically with shared settings.

---

## Notes

- Host-only actions (travel, BMS spawns, UVHM bulk) require session host in-world.
- After any mod update, **fully restart BL4** — partial reload can leave an old bridge running.
- The desktop app does not require the SDK console. If `~` loses focus in exclusive
  fullscreen, click back into the game and press it twice, or use borderless
  fullscreen; the SDK log should report `Console key is already set to Tilde`.
- In-game diagnostics: console `sqbt_bridge status`.

Desktop app build/docs: [`../squ1ggs_boosting_tools_app/README.md`](../squ1ggs_boosting_tools_app/README.md)
