# Squ1ggs Boosting Tools — desktop app

**v1.1.135** · Borderlands 4 player tools by **[Squ1ggs](https://github.com/Squ1ggs)**  
Pairs with SDK mod **3.8.140+**.

**Download:** [Releases on Bl4SDKmods](https://github.com/Squ1ggs/Bl4SDKmods/releases)  
Grab the **portable zip**, unzip, run **`Squ1ggsBoostingTools.exe`**.

---

## Install (players)

1. Run **Squ1ggsBoostingTools.exe**.
2. Set your Borderlands 4 path if asked — the EXE installs the Oak2 SDK + Squ1ggs mod automatically.
3. **Fully restart** Borderlands 4 and load a character.
4. Click **Refresh status** — you want **Online** and mod **3.8.137+**.

That’s it. Keep the EXE open while you boost; leave the game unpaused for actions to land.

---

## What’s in the app

- **Home** — boost target, MAX ALL, quick jumps, what’s new  
- **Loot** — pools, shinies, shapes (house / globe / …)  
- **Serials** — paste `@U` codes and **Send items**  
- **Mob & IO** — spawn enemies and machines (bank, vendors, beams, …)  
- **Movement / Travel / Challenges** — fly, jump, bookmarks, UVHM, and more  

Host-only tools need you to be the session host.

---

## After an update

Close the old EXE → run the new portable build → fully restart BL4 once → Refresh status.

---

## Build (developers)

```powershell
npm run check
npm run dist:portable
```

Output:

- `../dist_squ1ggs_boosting_tools/win-unpacked/Squ1ggsBoostingTools.exe`
- `../dist_squ1ggs_boosting_tools/Squ1ggsBoostingTools-Portable-v1.1.135.zip`

`prepack` syncs the live `Squ1ggsBoostingTools` mod folder into `resources/` for the bundle.

---

## Changelog

See the mod **[CHANGELOG.md](../Squ1ggsBoostingTools/CHANGELOG.md)** (shared release notes for EXE + mod).
