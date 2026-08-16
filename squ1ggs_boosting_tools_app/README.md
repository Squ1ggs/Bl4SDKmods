# Squ1ggs Boosting Tools — desktop app

**v1.0.80** · Player tools for **Borderlands 4** by **[Squ1ggs](https://github.com/Squ1ggs)**.

**Distribution:** GitHub only (mod + app) — not on the [BL Oak2 Mod DB](https://bl-sdk.github.io/oak2-mod-db/).  
**Repo:** [github.com/Squ1ggs/Bl4SDKmods](https://github.com/Squ1ggs/Bl4SDKmods)

## User flow (same idea as MSBT)

1. Run **Squ1ggs Boosting Tools** → browse to Borderlands 4 if needed → **Install SDK + Squ1ggs mod** (downloads official [oak2-mod-manager](https://github.com/bl-sdk/oak2-mod-manager/releases/tag/v0.3) when the base SDK is missing).
2. Launch **Borderlands 4**.
3. **Fully restart Borderlands 4**, then **Refresh status** — confirm the game is connected and mod v3.6.173+ is shown.
4. Click a party roster row to set the action target, then use any tab.

## Features

- One-click install of the official oak2 base SDK (when missing) plus Squ1ggsBoostingTools, with game path auto-detect
- Optional **Update base SDK** when a newer oak2-mod-manager release is available
- Live connection state, party roster, target player selection
- **12 manifest-driven tabs** synced with the SDK mod, including Loot, Mobility, Vehicle, Damage, Resources, World, and Mob/IO tools
- Searchable catalog dropdowns: item pools, travel maps/stations, spawn mixes, GZO, Lootlemon, BMS actors/IO, legit forge roots/parts
- **GZO serials:** [Borderlands 4 Items on save-editor.be](https://save-editor.be/GZO/Borderlands4/Codes.html) — catalog/site by **Ynot**, API by **Mattmab** (this app only reads that API). Thank you to **Tobgun** for feedback, ideas, testing, and bug reports.
- Result panels for mobility status and legit forge build output
- Stale-mod hint when bridge lacks manifest support (restart game after updates)
- Quiet GitHub release check with an in-app update notice only when a newer version is available

## Build

```powershell
# Dev (no installer)
.\build_squ1ggs_boosting_tools_app.ps1 -Dev

cd squ1ggs_boosting_tools_app
npm start

# Portable folder only (copy win-unpacked anywhere — settings live next to the EXE)
.\build_squ1ggs_boosting_tools_app.ps1
# → dist_squ1ggs_boosting_tools/win-unpacked/Squ1ggsBoostingTools.exe

# Windows NSIS installer → dist_squ1ggs_boosting_tools/
.\build_squ1ggs_boosting_tools_app.ps1 -Installer
```

### Portable vs installed

| Build | Use case | Where settings are saved |
|-------|----------|---------------------------|
| **`npm run pack`** (`win-unpacked`) | USB / portable folder | `squ1ggs-boosting-tools-settings.json` **next to the EXE** |
| **NSIS installer** to a writable folder | Same as portable if the install dir is writable | Next to EXE when possible |
| **NSIS installer** to `Program Files` | Normal install | `%APPDATA%` (auto fallback) |

Both builds are the same app — portable just keeps your game path with the folder you copied.

After mod changes: run the build script to restage the loose mod folder, then **fully restart Borderlands 4** before testing.
