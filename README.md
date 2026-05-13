# Bl4SDKmods

Borderlands 4 **Python SDK** mods for the game’s **`sdk_mods`** folder (Oak2 / `mods_base`). If something breaks after a patch, open an issue and say **which mod** and **which game build** you are on.

---

## blimgui (third-party — not by Squ1ggs)

**Squ1ggs did not create [blimgui](https://github.com/juso40/blimgui).**  
**blimgui** is its own mod: it loads the ImGui stack and owns the **BL4 mod menu window** (tabs, docking, input, rendering, etc.). Use **blimgui’s** license, credits, and issue tracker for anything wrong with that shell.

**blimgui is installed like any other Oak2 SDK mod** — add a **`blimgui`** folder or a valid **`blimgui.sdkmod`** to your game’s **`sdk_mods`** directory, then enable **blimgui** in **`mods`**. This repository **does not include** blimgui’s sources or a prebuilt zip; get it from **[blimgui upstream](https://github.com/juso40/blimgui)** or the **[Oak2 mod database](https://bl-sdk.github.io/oak2-mod-db/)** so you use the current release and the original authors’ packaging. You can still drop **`blimgui.sdkmod`** next to your other `.sdkmod` files (for example under **`sdk_mods/sdkmod_dist`**) if that is how you organize installs.

**What Squ1ggs did build** is only the **`squ1ggs_blimgui`** package in this repo: it **registers one extra tab** inside blimgui’s menu (**“Squ1ggs · Tuning”**) and draws the controls that talk to the three gameplay mods. That is **menu content inside blimgui**, not a replacement for blimgui and not the ImGui framework itself.

**Install order:** enable **blimgui** first, then enable **Squ1ggs · Tuning** (`squ1ggs_blimgui`) if you want that tab.

---

## Mods in this repo

Each package shows up separately under **`mods`** in the console.

| Folder | What it does |
|--------|----------------|
| **bl4_player_movement** | On-foot movement tuning (`player_move_*` in console). |
| **bl4_vehicle_movement** | Vehicle movement tuning (`vehicle_move_*`). |
| **bl4_damage_and_more** | Local damage / healing tweaks (`bdam_*`). |
| **squ1ggs_blimgui** | Optional **blimgui** tab that drives the three mods above. Needs **blimgui** and at least one of those mods; it has **no sliders by itself**. |

**Dependency:** **blimgui** is also an Oak2 SDK mod (folder or `.sdkmod` in **`sdk_mods`**), but it is **not packaged in this repository** — install it from **[juso40/blimgui](https://github.com/juso40/blimgui)** or the **[Oak2 mod database](https://bl-sdk.github.io/oak2-mod-db/)**.

**User-facing details** (keybinds, commands, behaviour): see each folder’s **`README.md`**.

---

## Install (copy mod folders)

1. Copy the **folder(s)** you want into the game’s **`sdk_mods`** directory (alongside `__main__.py`).
2. Launch BL4, open the **console** (tilde), run **`mods`**, enable what you installed.
3. For the hub tab: install and enable **blimgui**, then enable **squ1ggs_blimgui** (listed as **Squ1ggs · Tuning**).

If the mod list errors when saving options, create an empty **`sdk_mods/settings`** folder (if missing) and ensure **`sdk_mods`** is not read-only.

---

## Optional: `.sdkmod` zips

The mod manager can load **`.sdkmod`** files. Each zip must contain **exactly one** top-level directory, and that directory’s name must match the file stem (for example `bl4_player_movement.sdkmod` → only `bl4_player_movement/...` inside). You can zip a folder yourself with that layout, or install the folders without zipping.

---

## License

MIT — see **`LICENSE`** in the repo root; per-mod **`LICENSE`** files where included.
