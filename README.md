# Bl4SDKmods

Borderlands 4 **Python SDK** mods for the game's **`sdk_mods`** folder (Oak2 / `mods_base`). Each mod ships as an **`.sdkmod`** file - a zip with one top-level folder matching the file name. If something breaks after a patch, open an issue and say **which mod** and **which game build** you're on.

---

## Mods in this repo

| Folder | What it does |
|--------|----------------|
| **bl4_player_movement** | On-foot movement tuning (`player_move_*` in console). |
| **vehicle_movement** | Vehicle tuning + spawn (`vehicle_move_*`). Optional **BLImGui** panel - **Open Vehicle Movement tab** (Ctrl+Alt+F8). |
| **challenge_ticker** | UVHM ranks + challenge completion. **BLImGui** tab (Ctrl+F7). GPL-3.0. | full challenge unlocker for Bl4
| **damage_and_more** | Combat tuning (`bdam_*`). Optional **BLImGui** tab - **Open Damage & More tab** (Ctrl+Shift+F11). |
| **resources_and_cooldowns** | Recovery sliders (`brc_*`). Optional **BLImGui** tab - **Open Resources & Cooldowns tab** (Ctrl+Shift+F12). |
| **mob_spawner** | Mob/IO spawn catalog. **BLImGui** tabs (Ctrl+F6 / F1 BMS). Needs Oak Spawner. Console: `bms_*`. |
| **p2p_teleporter** | Co-op roster + teleports (`bcst_*`). Optional **BLImGui** tab - bind **Open P2P Teleporter tab**. |
| **world_travel** | Location bookmarks + travel catalog (`bwt_*`). Optional **BLImGui** tab - **Open World Travel tab**. |
| These above can also be found on the bl4 sdk mod database - https://bl-sdk.github.io/oak2-mod-db/

| **Squ1ggsBoostingTools** | Boosting toolkit + desktop EXE (**mod 3.8.0 / EXE 1.1.1**). GitHub [Releases](https://github.com/Squ1ggs/Bl4SDKmods/releases) — not on Mod DB. | includes all published sdk mods pretty much so it's an all in one boosting tool thats regularly updated, Supports multiple languages and has many features including sending modded items/legit items or spawning items via pools, movement/damage/teleports/fast travel/loot shapes like claptrap, car, house, pyramid or sort by type and more, also features the full challenge and uvhm unlocks and many other fun tools for playing around

Mods menu + console work without BLImGui on most packages. For in-game panels, install [BLImGui](https://github.com/juso40/blimgui) separately and set the keybind under **Mods -> Keybinds**.

---

## Install (`.sdkmod`)

1. Take the `.sdkmod` from the mod folder (e.g. `vehicle_movement/vehicle_movement.sdkmod`).
2. Copy into your game's **`sdk_mods`** directory (next to `__main__.py`).
3. Launch BL4, open the **console** (tilde), run **`mods`**, enable what you added.

Do **not** unzip `.sdkmod` files for normal play. Each archive needs **one** top-level folder whose name matches the file stem (`vehicle_movement.sdkmod` -> `vehicle_movement/...`).

---

## License

MIT by default - see **`LICENSE`** in the repo root. **Challenge Ticker** is GPL-3.0 (see its `pyproject.toml`).
