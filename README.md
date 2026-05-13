# Bl4SDKmods

These are my Borderlands 4 **Python SDK** mods for the game’s **`sdk_mods`** folder (Oak2 / `mods_base`). Each mod ships as an **`.sdkmod`** file (Oak2 package format—a zip with exactly one top-level folder whose name matches the file stem). If something breaks after a patch, open an issue and say **which mod** and **which game build** you’re on.

---

## blimgui (third-party — I didn’t make it)

**I didn’t create [blimgui](https://github.com/juso40/blimgui).** It’s someone else’s mod: it loads the ImGui stack and owns the **BL4 mod menu window** (tabs, docking, input, rendering, etc.). For problems with that shell, use **blimgui’s** license, credits, and issue tracker—not mine.

**blimgui installs like any other Oak2 SDK mod** — add **`blimgui.sdkmod`** (or the **`blimgui`** folder package from upstream) under **`sdk_mods`** or **`sdk_mods/sdkmod_dist`**, then enable **blimgui** in **`mods`**. I **don’t ship** blimgui in this repo; get it from **[blimgui upstream](https://github.com/juso40/blimgui)** or the **[Oak2 mod database](https://bl-sdk.github.io/oak2-mod-db/)**.

**What I built** is **Tuning GUI**: a small mod that **registers one extra tab** inside blimgui’s menu (the tab is also labeled **Tuning GUI**) and drives my three gameplay mods from there. The Oak2 package on disk is **`tuning_blimgui`** (`.sdkmod` / folder name); the mod list still shows **Squ1ggs** as author.

**Install order:** enable **blimgui** first, then enable **Tuning GUI** (install **`tuning_blimgui.sdkmod`** or the loose folder—see below).

---

## Mods in this repo

Each package shows up separately under **`mods`** in the console.

| `.sdkmod` / package | What it does |
|--------|----------------|
| **bl4_player_movement** | On-foot movement tuning (`player_move_*` in console). |
| **bl4_vehicle_movement** | Vehicle movement tuning (`vehicle_move_*`). |
| **bl4_damage_and_more** | Local damage / healing tweaks (`bdam_*`). |
| **Tuning GUI** (`tuning_blimgui`) | Optional **blimgui** tab that drives the three mods above. Needs **blimgui** and at least one of those mods; it has **no sliders by itself**. |

**Dependency:** **blimgui** is not included here — install it from **[juso40/blimgui](https://github.com/juso40/blimgui)** or the **[Oak2 mod database](https://bl-sdk.github.io/oak2-mod-db/)**.

**Per-mod details** (keybinds, console commands, behaviour): see each package’s **`README.md`**.

---

## Install (`.sdkmod` — recommended)

1. From this repo, take **`bl4_player_movement/bl4_player_movement.sdkmod`** (and any other mods you want—the same pattern for each name).
2. Copy those **`.sdkmod`** files into your game’s **`sdk_mods`** directory (next to `__main__.py`) **or** into **`sdk_mods/sdkmod_dist`** if you use that layout.
3. Launch BL4, open the **console** (tilde), run **`mods`**, enable the mods you added.
4. For **Tuning GUI**: install **`tuning_blimgui.sdkmod`** the same way, **after** **blimgui** is installed and enabled.

Do **not** unzip `.sdkmod` files by hand for normal play—the manager loads them as mod packages. Each archive must contain **only** one top-level folder, and that folder’s name must match the file stem (e.g. `bl4_player_movement.sdkmod` → `bl4_player_movement/...`).

---

## Install (folder package — optional)

If you maintain mods as **loose folders** instead of `.sdkmod` zips: copy the whole **`bl4_player_movement`** (etc.) directory into **`sdk_mods`**. Oak2 imports it as a Python package; you still enable it under **`mods`**. The **`.sdkmod`** sitting inside each folder in this repo is the same mod in archive form—use **either** the zip **or** the folder, not both copies of the same mod name in `sdk_mods`.

---

## License

MIT — see **`LICENSE`** in the repo root; per-mod **`LICENSE`** files where included.
