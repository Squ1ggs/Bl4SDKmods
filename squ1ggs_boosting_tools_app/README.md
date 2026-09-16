# Squ1ggs Boosting Tools — desktop app

**v1.2.2** · Borderlands 4 player tools by **[Squ1ggs](https://github.com/Squ1ggs)**
Pairs with SDK mod **3.9.2**.

**Download:** [Releases on Bl4SDKmods](https://github.com/Squ1ggs/Bl4SDKmods/releases)
Grab the **portable zip**, unzip, run **`Squ1ggsBoostingTools.exe`**.

---

## Install (players)

1. Run **Squ1ggsBoostingTools.exe**.
2. Set your Borderlands 4 path if asked — the EXE installs the Oak2 SDK + Squ1ggs mod automatically.
3. **Fully restart** Borderlands 4 and load a character.
4. Click **Refresh status** — you want **Online** and mod **3.9.2+**.

That’s it. Keep the EXE open while you boost; leave the game unpaused for actions to land.

---

## What’s in the app

- **Auto Lobby guest mode** — skip the host for Challenges/UVHM, wait for guests, then boost each new arrival once
- **Save Pack / Live Pack** — read `@U` from autosave or a one-shot live Boost-target snap; copy, relevel or send
- **Loot shapes + shinies** — floor drops, shaped piles and quick pull-to-feet tools for the lobby
- **GZO drip** — build a host backpack pile for guests, with a red countdown before it spills
- **MAX ALL + progression HUD** — Challenge/UVHM progress in a draggable window
- **Mob & IO / Movement / Travel** — spawn enemies and machines, fly, jump, bookmark and warp

Host-only tools need you to be the session host.

**Complete ALL safety:** non-UVHM completion sends rewards but does not open a huge queue in multiplayer. Console/cross-play players should leave the lobby, open rewards in solo, sell junk, then rejoin.

---

## After an update

Close the old EXE → run the new portable build → fully restart BL4 once → Refresh status.

---

## Versioning

EXE uses **1.2.1 … 1.2.9**, then **1.3.1** (no triple-digit patches). Mod mirrors as **3.9.x**.

---

## Build (developers)

```powershell
npm run check
npm run dist:portable
```

Output:

- `../dist_squ1ggs_boosting_tools/win-unpacked/Squ1ggsBoostingTools.exe`
- `../dist_squ1ggs_boosting_tools/Squ1ggsBoostingTools-Portable-v1.2.2.zip`

`prepack` syncs the live `Squ1ggsBoostingTools` mod folder into `resources/` for the bundle.

---

## Changelog

See the mod **[CHANGELOG.md](resources/Squ1ggsBoostingTools/CHANGELOG.md)** (shared release notes for EXE + mod).
