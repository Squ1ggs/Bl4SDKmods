# Nexus Mods — paste notes (Borderlands 4)

There is **no separate “Nexus readme”** shipped by default—this file is **for you**: copy sections into the Nexus **Description**, **Requirements**, and **Files** UI when you create the mod page(s). Keep **[GitHub](https://github.com/Squ1ggs/Bl4SDKmods)** as the canonical place for full docs and issues.

---

## Does blimgui come with the SDK?

**Usually no.** A typical Oak2 / BL4 **Python SDK** install gives you things like **`sdk_mods/__main__.py`**, **`mods_base`**, and the **`mods`** console workflow. **blimgui** is normally a **separate** SDK mod (its own **`.sdkmod`** or folder) that adds the **ImGui mod menu**. If your `sdk_mods` folder **does not** contain **`blimgui`** (or `blimgui.sdkmod`), you still need to install it from **upstream** (see root `README.md` links).

When in doubt: open the game, run **`mods`** in the console—if **blimgui** is not listed, it isn’t installed.

---

## Suggested Nexus layout (recommended)

| Nexus page | Main file(s) | Notes |
|------------|----------------|------|
| **One “bundle” mod** *or* **four separate mods** | Each **`.sdkmod`** from GitHub (`bl4_*`, `squ1ggs_blimgui`) | Do **not** upload **blimgui** unless you fully comply with **its** license and clearly credit upstream; easier to list **blimgui** as an **off-site requirement** with a link. |
| **Optional:** separate page for **Tuning GUI** only | `squ1ggs_blimgui.sdkmod` | Avoids duplicating the hub file as an “optional download” on every other mod. |

---

## Block: “About this mod” (Description) — bundle example

Copy and edit bracketed bits:

```text
Oak2 / Python SDK mods for Borderlands 4 (.sdkmod packages).

WHAT’S INCLUDED
- BL4 Player Movement — on-foot movement tuning
- BL4 Vehicle Movement — vehicle movement tuning  
- BL4 Damage & More — local damage / healing tweaks
- Tuning GUI — extra tab inside blimgui’s menu to drive the three mods above (optional; needs blimgui + at least one of the others)

INSTALL (QUICK)
1) Install the official BL4 Python SDK / Oak2 setup so you have sdk_mods and the `mods` console command.
2) Copy the .sdkmod file(s) you want into:
   …\Borderlands 4\sdk_mods\
   or …\Borderlands 4\sdk_mods\sdkmod_dist\
3) Launch the game, open the console (~), run: mods
4) Enable the mods you added.

Do not unzip .sdkmod files for normal play — the manager loads them as packages.

TUNING GUI + BLIMGUI
I did not make blimgui. Install blimgui separately (see Requirements), enable it first, then enable Tuning GUI.

SOURCE + ISSUES
https://github.com/Squ1ggs/Bl4SDKmods
```

---

## Block: Requirements (Nexus)

Add as **off-site requirements** (use real URLs you support):

- **blimgui** — required **only** if you use **Tuning GUI**; link upstream / Oak2 mod DB.  
- **BL4 Python SDK (Oak2)** — link the install guide you follow (e.g. Oak2 mod database install page).

---

## Block: Files tab

Upload the same **`.sdkmod`** files as on GitHub (one row per file, or one zip of all four with a note: “extract the four .sdkmod files into sdk_mods or sdk_mods/sdkmod_dist”).  
Short **changelog** on each update helps a lot.

---

## Permissions / credits (Nexus)

- Your mods: **MIT** (match repo `LICENSE`).  
- **blimgui:** do **not** claim you made it; if you **mirror** it (not recommended vs linking), include **their** license and copyright.
