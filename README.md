# Bl4SDKmods

These is my Borderlands 4 player movement **Python SDK** mod for the game’s **`sdk_mods`** folder (Oak2 / `mods_base`). Each mod ships as an **`.sdkmod`** file (Oak2 package format—a zip with exactly one top-level folder whose name matches the file stem). If something breaks after a patch, open an issue and say **which mod** and **which game build** you’re on.


---

## Mods in this repo

Each package shows up separately under **`mods`** in the console.

| `.sdkmod` / package | What it does |
|--------|----------------|
| **bl4_player_movement** | On-foot movement tuning (player_move_* in console). |
| **vehicle_movement** | Vehicle tuning + spawn (ehicle_move_*). BLImGui panel optional � **Open Vehicle Movement tab** (Ctrl+Alt+F8). |


---

## Release staging (local testing)

Use **`release_staging/`** to drop rebuilt **`*.sdkmod`** files, install them into the game’s **`sdk_mods`** for manual testing, then copy the same files into this repo’s mod subfolders when you are ready to commit or push. See **`release_staging/README.md`**. Staged **`.sdkmod`** / **`.zip`** files are **`.gitignore`d`** so they are not committed by accident.

---

## Install (`.sdkmod` — recommended)

1. From this repo, take **`bl4_player_movement/bl4_player_movement.sdkmod **ehicle_movement/vehicle_movement.sdkmod**`** (and any other mods you want—the same pattern for each name).
2. Copy those **`.sdkmod`** files into your game’s **`sdk_mods`** directory (next to `__main__.py`)
3. Launch BL4, open the **console** (tilde), run **`mods`**, enable the mods you added.

Do **not** unzip `.sdkmod` files by hand for normal play—the manager loads them as mod packages. Each archive must contain **only** one top-level folder, and that folder’s name must match the file stem (e.g. `bl4_player_movement.sdkmod` → `bl4_player_movement/...`).

---

## License

MIT — see **`LICENSE`** in the repo root; per-mod **`LICENSE`** files where included.
