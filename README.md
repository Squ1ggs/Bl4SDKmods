# Bl4SDKmods

Borderlands 4 **Python SDK** mods for the game's **`sdk_mods`** folder (Oak2 / `mods_base`). Each mod ships as an **`.sdkmod`** file - a zip with one top-level folder matching the file name. If something breaks after a patch, open an issue and say **which mod** and **which game build** you're on.

---

## Mods in this repo

| Folder | What it does |
|--------|----------------|
| **bl4_player_movement** | On-foot movement tuning (`player_move_*` in console). |
| **vehicle_movement** | Vehicle tuning + spawn (`vehicle_move_*`). Optional **BLImGui** panel - **Open Vehicle Movement tab** (Ctrl+Alt+F8). |
| **challenge_ticker** | UVHM ranks + challenge completion. **BLImGui** tab (Ctrl+F7). GPL-3.0. |
| **damage_and_more** | Combat tuning (`bdam_*`). Optional **BLImGui** tab - **Open Damage & More tab** (Ctrl+Shift+F11). |
| **resources_and_cooldowns** | Recovery sliders (`brc_*`). Optional **BLImGui** tab - **Open Resources & Cooldowns tab** (Ctrl+Shift+F12). |

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
