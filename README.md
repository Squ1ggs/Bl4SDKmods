# Bl4SDKmods

These are my Borderlands 4 **Python SDK** mods for the game’s **`sdk_mods`** folder (Oak2 / `mods_base`). If something breaks after a patch, open an issue and say **which mod** and **which game build** you’re on.

---

## blimgui (third-party — I didn’t make it)

**I didn’t create [blimgui](https://github.com/juso40/blimgui).** It’s someone else’s mod: it loads the ImGui stack and owns the **BL4 mod menu window** (tabs, docking, input, rendering, etc.). For problems with that shell, use **blimgui’s** license, credits, and issue tracker—not mine.

**blimgui installs like any other Oak2 SDK mod** — add a **`blimgui`** folder or a valid **`blimgui.sdkmod`** to your game’s **`sdk_mods`** directory, then enable **blimgui** in **`mods`**. I **don’t ship** blimgui’s sources or a prebuilt zip in this repo; grab it from **[blimgui upstream](https://github.com/juso40/blimgui)** or the **[Oak2 mod database](https://bl-sdk.github.io/oak2-mod-db/)** so you stay on the current release and the original authors’ packaging. You can still drop **`blimgui.sdkmod`** next to your other `.sdkmod` files (for example under **`sdk_mods/sdkmod_dist`**) if that’s how you organize installs.

**What I built** is **Tuning GUI**: a small mod that **registers one extra tab** inside blimgui’s menu (the tab is also labeled **Tuning GUI**) and draws the controls that talk to my three gameplay mods. On disk Oak2 expects the package folder name **`squ1ggs_blimgui`** — that’s only the import/install path, not the product name. It’s **UI inside blimgui’s menu**, not a replacement for blimgui and not the ImGui framework itself.

**Install order:** enable **blimgui** first, then enable **Tuning GUI** (from the **`squ1ggs_blimgui`** folder or zip) if you want that tab.

---

## Mods in this repo

Each package shows up separately under **`mods`** in the console.

| Folder | What it does |
|--------|----------------|
| **bl4_player_movement** | On-foot movement tuning (`player_move_*` in console). |
| **bl4_vehicle_movement** | Vehicle movement tuning (`vehicle_move_*`). |
| **bl4_damage_and_more** | Local damage / healing tweaks (`bdam_*`). |
| **Tuning GUI** (`squ1ggs_blimgui` on disk) | Optional **blimgui** tab that drives the three mods above. Needs **blimgui** and at least one of those mods; it has **no sliders by itself**. |

**Dependency:** **blimgui** is also an Oak2 SDK mod (folder or `.sdkmod` in **`sdk_mods`**), but I **don’t include** it in this repo — install it from **[juso40/blimgui](https://github.com/juso40/blimgui)** or the **[Oak2 mod database](https://bl-sdk.github.io/oak2-mod-db/)**.

**User-facing details** (keybinds, commands, behaviour): see each folder’s **`README.md`**.

---

## Install (copy mod folders)

1. Copy the **folder(s)** you want into the game’s **`sdk_mods`** directory (alongside `__main__.py`).
2. Launch BL4, open the **console** (tilde), run **`mods`**, enable what you installed.
3. For the hub tab: install and enable **blimgui**, then enable **Tuning GUI** (enable the mod from the **`squ1ggs_blimgui`** folder, or drop **`squ1ggs_blimgui.sdkmod`** into **`sdk_mods`** / **`sdk_mods/sdkmod_dist`**).

If the mod list errors when saving options, create an empty **`sdk_mods/settings`** folder (if missing) and ensure **`sdk_mods`** is not read-only.

---

## Optional: `.sdkmod` zips

The mod manager can load **`.sdkmod`** files. Each zip must contain **exactly one** top-level directory, and that directory’s name must match the file stem (for example `bl4_player_movement.sdkmod` → only `bl4_player_movement/...` inside).

**Inside each mod folder** here there is a matching **`<folder>.sdkmod`** built to that layout. I keep those on purpose: you can copy **just the zip** into **`sdk_mods`** (or **`sdk_mods/sdkmod_dist`**) if you prefer that over copying the whole folder—they are not stray or duplicate mistakes.

You can still install using the **folder** only and ignore the zip if you want.

---

## License

MIT — see **`LICENSE`** in the repo root; per-mod **`LICENSE`** files where included.
