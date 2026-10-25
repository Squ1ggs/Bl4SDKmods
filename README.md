# Bl4SDKmods

Borderlands 4 **Python SDK** mods for the game's **`sdk_mods`** folder (Oak2 / `mods_base`).

**Looking for the boosting desktop app?** → **[Squ1ggs Boosting Tools 1.3.57](https://github.com/Squ1ggs/Bl4SDKmods/releases/tag/sqbt-v1.3.57)** (portable EXE **1.3.57** + mod **3.10.57**).

**Car looks without the app?** → **[BL4 Vehicle Swapper 0.1.2](https://github.com/Squ1ggs/Bl4SDKmods/releases/tag/bl4-vehicle-swapper-v0.1.2)**. The folder is [bl4_vehicle_swapper](bl4_vehicle_swapper). No cars are included. Car packs are on the [original packs release](https://github.com/Squ1ggs/Bl4SDKmods/releases/tag/bl4-original-model-packs-v0.1).

Each smaller mod ships as an **`.sdkmod`** file — a zip with one top-level folder matching the file name.

---

## Mods in this repo

| Folder | What it does |
|--------|----------------|
| **bl4_player_movement** | On-foot movement tuning (`player_move_*` in console). |
| **vehicle_movement** | Vehicle tuning + spawn (`vehicle_move_*`). Optional **BLImGui** panel — **Open Vehicle Movement tab** (Ctrl+Alt+F8). |
| **challenge_ticker** | UVHM ranks + challenge completion (`bl4cu_*`). Optional panel if you already have BL4 BLImGui. MIT. |
| **damage_and_more** | Combat tuning (`bdam_*`). Optional **BLImGui** tab — **Open Damage & More tab** (Ctrl+Shift+F11). |
| **resources_and_cooldowns** | Recovery sliders (`brc_*`). Optional **BLImGui** tab — **Open Resources & Cooldowns tab** (Ctrl+Shift+F12). |
| **mob_spawner** | Mob/IO spawn catalog. **BLImGui** tabs (Ctrl+F6 / F1 BMS). Console: `bms_*`. |
| **p2p_teleporter** | Co-op roster + teleports (`bcst_*`). Optional **BLImGui** tab. |
| **world_travel** | Location bookmarks + travel catalog (`bwt_*`). Optional **BLImGui** tab. |
| **bl4_character_swapper** | Character looks. Download [0.2.13](https://github.com/Squ1ggs/Bl4SDKmods/releases/tag/bl4-character-swapper-v0.2.13). Skills and weapons stay yours. |
| These above are also on the [BL Oak2 Mod DB](https://bl-sdk.github.io/oak2-mod-db/). |
| **bl4_vehicle_swapper** | Car looks. Driving stays the car you are using. No cars are included. Download [0.1.2](https://github.com/Squ1ggs/Bl4SDKmods/releases/tag/bl4-vehicle-swapper-v0.1.2). Not on Mod DB. |
| **Squ1ggsBoostingTools** | All-in-one boosting **desktop app + mod** (**3.10.57 / EXE 1.3.57**), including character looks on Appearance and car looks on Vehicle. Download the portable EXE from [Releases](https://github.com/Squ1ggs/Bl4SDKmods/releases/tag/sqbt-v1.3.57) — not on Mod DB. |

Mods menu + console work without BLImGui. Optional panels need a BL4-capable BLImGui already installed.

---

## Install (`.sdkmod`)

1. Take the `.sdkmod` from the mod folder (e.g. `vehicle_movement/vehicle_movement.sdkmod`).
2. Copy into your game's **`sdk_mods`** directory (next to `__main__.py`).
3. Launch BL4, open the **console** (tilde), run **`mods`**, enable what you added.

Do **not** unzip `.sdkmod` files for normal play.

---

## License

MIT by default - see **`LICENSE`** in the repo root. Squ1ggs Boosting Tools,
BL4 Character Swapper, and BL4 Vehicle Swapper retain their module-specific
GPL-3.0-or-later licences. Car and character packs keep their own licences.
