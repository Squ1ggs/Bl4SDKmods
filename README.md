# Bl4SDKmods

Borderlands 4 **Python SDK** mods for `sdk_mods`. If something breaks after a game patch, open an issue and say which mod and build you are on.

## blimgui

**blimgui** is a separate mod (ImGui menu). This repo’s **squ1ggs_blimgui** only registers a **“Squ1ggs · Tuning”** tab in that menu so you can drive the other mods from one window if you want. Problems with the ImGui shell itself belong with **blimgui**, not these mods.

## Mods

Each mod appears separately under **`mods`** in the console.

| Folder | What it does |
|--------|----------------|
| **bl4_player_movement** | On-foot movement (`player_move_*` in console). |
| **bl4_vehicle_movement** | Vehicle movement (`vehicle_move_*`). |
| **bl4_damage_and_more** | Local damage / healing tweaks (`bdam_*`). |
| **squ1ggs_blimgui** | Optional hub tab in blimgui. Needs **blimgui** plus at least one of the three mods above (no sliders by itself). |

## Install (folders)

1. Copy the mod **folder(s)** you want into the game’s **`sdk_mods`** directory (next to `__main__.py`).
2. Launch BL4, open the **console**, run **`mods`**, enable what you installed.
3. For the hub tab: install **blimgui**, enable it, then enable **squ1ggs_blimgui** (listed as **Squ1ggs · Tuning**).

If saving options errors, ensure **`sdk_mods/settings`** exists (empty folder is fine) and that `sdk_mods` is not read-only.

Each mod folder has its own **README** for keybinds and commands.

## Optional: `.sdkmod` zip files

The mod manager can load **`.sdkmod`** files. Each zip must contain **exactly one** top-level directory, and that directory’s name must match the file stem (example: `bl4_player_movement.sdkmod` contains only `bl4_player_movement/...`). You can build that with any zip tool, or copy the folders as-is without zipping.

## License

MIT — see **LICENSE** in the repo root; per-mod **LICENSE** files where included.
