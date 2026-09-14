# Bl4SDKmods

Borderlands 4 **Python SDK** mods for the game's **`sdk_mods`** folder (Oak2 / `mods_base`).

**Looking for the boosting desktop app?** → **[Squ1ggs Boosting Tools releases](https://github.com/Squ1ggs/Bl4SDKmods/releases)** (portable EXE + mod, currently **1.1.130 / 3.8.136**).

Each smaller mod ships as an **`.sdkmod`** file — a zip with one top-level folder matching the file name.

---

## Mods in this repo

| Folder | What it does |
|--------|----------------|
| **bl4_player_movement** | On-foot movement tuning (`player_move_*` in console). |
| **vehicle_movement** | Vehicle tuning + spawn (`vehicle_move_*`). Optional **BLImGui** panel â€” **Open Vehicle Movement tab** (Ctrl+Alt+F8). |
| **challenge_ticker** | UVHM ranks + challenge completion (`bl4cu_*`). Optional panel if you already have BL4 BLImGui. MIT. |
| **damage_and_more** | Combat tuning (`bdam_*`). Optional **BLImGui** tab â€” **Open Damage & More tab** (Ctrl+Shift+F11). |
| **resources_and_cooldowns** | Recovery sliders (`brc_*`). Optional **BLImGui** tab â€” **Open Resources & Cooldowns tab** (Ctrl+Shift+F12). |
| **mob_spawner** | Mob/IO spawn catalog. **BLImGui** tabs (Ctrl+F6 / F1 BMS). Console: `bms_*`. |
| **p2p_teleporter** | Co-op roster + teleports (`bcst_*`). Optional **BLImGui** tab. |
| **world_travel** | Location bookmarks + travel catalog (`bwt_*`). Optional **BLImGui** tab. |
| These above are also on the [BL Oak2 Mod DB](https://bl-sdk.github.io/oak2-mod-db/). |
| **Squ1ggsBoostingTools** | All-in-one boosting **desktop app + mod** (**3.8.136 / EXE 1.1.130**). Download the portable EXE from [Releases](https://github.com/Squ1ggs/Bl4SDKmods/releases) — not on Mod DB. |

Mods menu + console work without BLImGui. Optional panels need a BL4-capable BLImGui already installed.

---

## Install (`.sdkmod`)

1. Take the `.sdkmod` from the mod folder (e.g. `vehicle_movement/vehicle_movement.sdkmod`).
2. Copy into your game's **`sdk_mods`** directory (next to `__main__.py`).
3. Launch BL4, open the **console** (tilde), run **`mods`**, enable what you added.

Do **not** unzip `.sdkmod` files for normal play.

---

## License

MIT by default - see **`LICENSE`** in the repo root and each mod's `pyproject.toml`.
