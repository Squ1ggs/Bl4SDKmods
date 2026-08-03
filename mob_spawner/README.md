# Borderlands Mob Spawner (BMS)

Spawn **Char_*** enemies and **IO_*** world objects from a big catalog, with aggro modes, mix spawns, and favorites.

The UI lives in **BLImGui** — install **[BLImGui](https://github.com/juso40/blimgui)** and enable it. Open the **BMS** tabs via **F1 → BMS** or bind **BMS (Ctrl+F6)** under **Mods → Keybinds**. Console still works: `bms_spawn`, `bms_gui`, `bms_help`.

## Install

Requires [Oak2 Mod Manager v0.3+](https://github.com/bl-sdk/oak2-mod-manager/releases/tag/v0.3).

1. Drop `mob_spawner.sdkmod` into `sdk_mods`.
2. Also enable **Oak Spawner** — BMS calls into it for actual spawns.
3. Install **BLImGui**, restart, run `mods`, enable **Borderlands Mob Spawner (BMS)**.

**Disable world AI spawn budget** is on by default so you are not stuck at a handful of live spawns. Rows ending in `_SHARED` are templates, not spawnable mobs — BMS will tell you.

MIT license.
