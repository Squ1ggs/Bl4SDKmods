# Tuning GUI (ImGui hub)

Adds a **Tuning GUI** tab to the **blimgui** menu for:

- `bl4_player_movement` — on-foot movement  
- `bl4_vehicle_movement` — vehicle movement (be in a vehicle)  
- `bl4_damage_and_more` — damage / elemental tuning  

The in-game **mods** list still shows the package author (**Squ1ggs**); **blimgui** is the separate library mod that provides the window.

## Third-party: blimgui

**I didn’t create blimgui.** This package only **registers a tab** in the menu that the **blimgui** mod provides. Install, enable, and follow **blimgui**’s own license and credits from its authors; any issues with the ImGui window itself belong with that project, not this hub.

## On-disk name

Install as folder **`squ1ggs_blimgui`**, or use a **`.sdkmod`** zip built in the Oak2 layout (the archive must contain a single top-level folder named `squ1ggs_blimgui`).  
If you still have the old **`squ1ggs_blimgui_tuning`** folder, remove it after copying settings if needed — this package was renamed.

## Setup

1. Install **blimgui** and enable it.  
2. Copy **`squ1ggs_blimgui`** into `sdk_mods` next to your tuning mods.  
3. Enable **Tuning GUI** in the mod list.

## Keys / console

- **Mods → Keybinds:** **Open BL4 Mod Menu (Tuning GUI)** (default **F1**, same as the usual blimgui menu key; rebind if you need a different key).  
- Console: `sqgui_open`

## Credit

**made by Squ1ggs**
