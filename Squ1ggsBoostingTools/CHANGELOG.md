# Changelog

## 3.8.142 / EXE 1.1.136
- **Hold session (no menu kick):** sticky host toggle cancels travel-to-menu and blocks return-to-menu / session-end leave so guests cannot pull the lobby out. Auto-arms during All UVHM / Complete ALL challenges; turn OFF before you quit to the menu yourself.
- **Loot shapes co-op:** Place Fully / settle no longer ForceNetUpdates hundreds of pins in one frame (house AV). Host layout stays local; guest sync drips so grabs match the shape.
- **Soft clear (hide loot):** on Home -> Most used and Loot -> Shiny drops (same as Loot Shapes).
- **Party teleport:** Everyone -> me (plus Me -> selected / Selected -> me).
- **MAX ALL:** Vault cards labeled **1-5**; already-maxed levels treated as success.
- **My Library / Serials:** optional Save entry name; GZO / Lootlemon Add to library; Deliver converts human/deserialized codes to @U before mail.
- **Home -> Most used:** Complete ALL challenges + All UVHM (target) one-taps.
- **Nova:** 3D sphere pulse; Stay in air on/off landing behavior; pulse no longer stalls behind bulk pause.
- **Stability:** PlayerBank/IO freeze (no world find_all on every spawn); quit soft-clear; mobility scrub; Find a tool / catalog search click hardening.

## 3.8.141 / EXE 1.1.135
- **Loveless (Corpo Hacker Raid 2 class mod):** dedicated merge spawn (was silent NCS lag / no loot). Dedicated classmods run before bulk native.
- **Spawn All Filtered:** fixed `shape_text` TypeError (queues/shapes work again).
- **Infinite jump (all / others):** no longer clears friend targets / sticky all-mode on join blips.
- **Shiny shapes:** lower house fill cap + 1/tick when shaped (D3D12 crash mitigation).
- **Spawn this one item:** count accepts 1–999 (Spawn All Filtered still x1/pool).
- **UI/stability:** Backpack tab removed again; party teleport shows Boost names; Dev Testing Map travel no longer cancels on brief session blips; bridge clears sticky last_error after success.

## 3.8.140 / EXE 1.1.134
- **Character level 70:** MAX ALL, Player level, in-game LV button, and keybinds actually apply **70** (labels already said 70; wiring still used 60).
- **Gear defaults / overrides:** serial rewrite + catalog level fields track 70 for this cap bump.
- **Pre-update note:** item-pool / main-page catalog refresh for the new cap is coming soon — this drop is the level-70 boost prep.

## 3.8.139 / EXE 1.1.133
- **Spawn shapes (new/restored on this drop):** diamond (3D), blocks, cube, torus, crown, UFO, rocket, gear — if you stayed on the last public release, grab this build so these shapes are actually on disk.
- **Send serials Browse / YAML:** loads into the paste box (blank line between codes) — not the optional queue and not My Library.
- **Add to library…** next to Send items: saves the paste box into My Library under a name you choose.
- **Open rewards:** still opens one package at a time (safe path); no bulk open.
- **Loot text / Spell a word:** restored 3-line shinies/pool lettering where relevant.
- **Co-op shapes:** silhouette drip / settle fixes so guests can grab without floor piles or mid-dump snaps.
