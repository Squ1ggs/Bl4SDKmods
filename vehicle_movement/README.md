# Vehicle Movement

Tune how your vehicle handles — speed, boost, jump, durability, vault costs — and spawn personal vehicles from a built-in catalog.

Works through the **mods menu** and **console** (`vehicle_move_help`). For a proper in-game panel, install **[BLImGui](https://github.com/juso40/blimgui)** separately, enable it, then under **Mods → Keybinds** bind **Open Vehicle Movement tab** (default **Ctrl+Alt+F8**). That opens a BLImGui tab with all the sliders, presets, and the vehicle spawn picker. No BLImGui? You still get the full mods menu and `vehicle_move_*` commands.

## Install

Requires [Oak2 Mod Manager v0.3+](https://github.com/bl-sdk/oak2-mod-manager/releases/tag/v0.3).

1. Drop `vehicle_movement.sdkmod` into your game's `sdk_mods` folder.
2. Restart, run `mods`, enable **Vehicle Movement**.
3. Optional: install **BLImGui**, restart again, assign the keybind above.

## Tips

Get **in a vehicle** before changing vehicle sliders. After fast travel or reconnect, run `vehicle_move_apply` if your build feels off.

Presets: `vehicle_move_preset boost` (also crawl, floaty, orbit, heavy, drift — see `vehicle_move_help`).

**Apply tuning to** (local / all / others) is in the mods menu and BLImGui panel. Client-side co-op — don't grief strangers with **all** / **others**.

Plays nice with **Squ1ggs Boosting Tools** if you run that too — same settings file, SQBT takes over the BLImGui tab when both are enabled.

MIT license.
