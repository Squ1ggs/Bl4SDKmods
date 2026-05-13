# Tuning GUI (ImGui hub)

Adds a **Tuning GUI** tab inside **blimgui**’s menu so you can drive:

- `bl4_player_movement` — on-foot movement  
- `bl4_vehicle_movement` — vehicle movement (be in a vehicle)  
- `bl4_damage_and_more` — damage / elemental tuning  

The **mods** list shows **Squ1ggs** as author; **blimgui** is the separate mod that owns the ImGui window.

## Third-party: blimgui

**I didn’t create blimgui.** This package only **registers a tab** in the menu that **blimgui** provides. Use blimgui’s license, credits, and issue tracker for the shell itself.

## Install

**Recommended — `.sdkmod`:** copy **`tuning_blimgui.sdkmod`** into **`sdk_mods`** or **`sdk_mods/sdkmod_dist`**. It must be a valid Oak2 package (one top-level folder **`tuning_blimgui`** inside the zip). The manager loads `.sdkmod` files directly—don’t unzip them for normal use.

**Optional — folder:** copy the **`tuning_blimgui`** directory into **`sdk_mods`** instead if you use loose packages. Don’t install the same mod twice as both zip and folder.

If you upgraded from the old **`squ1ggs_blimgui`** package, remove that folder or `.sdkmod` after switching—settings are copied once from **`squ1ggs_blimgui.json`** (or **`squ1ggs_blimgui_tuning.json`**) into **`tuning_blimgui.json`** when the new mod first runs.

## Setup

1. Install **blimgui** (as **`.sdkmod`** or folder—see blimgui’s own docs) and enable it.  
2. Install **Tuning GUI** with **`tuning_blimgui.sdkmod`** (or folder) as above.  
3. In **`mods`**, enable **Tuning GUI** (package folder / zip stem is **`tuning_blimgui`**).

## Keys / console

- **Mods → Keybinds:** **Open BL4 Mod Menu (Tuning GUI)** (default **F1**; rebind if needed).  
- Console: `sqgui_open`

## Credit

**made by Squ1ggs**
