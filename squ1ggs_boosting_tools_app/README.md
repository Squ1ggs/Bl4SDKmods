# Squ1ggs Boosting Tools

**EXE 1.3.41 / mod 3.10.41** · Borderlands 4 player tools by [Squ1ggs](https://github.com/Squ1ggs).

## What's new

- **Connection fix:** corrected a startup failure in the earlier public bundle that prevented fresh installations connecting. Appearance startup errors are isolated so the rest of the tool can still connect.
- **Automatic SDK setup:** after detecting or selecting your game folder, the app starts the official SDK installer when files are missing. The install button remains available for retrying. Close BL4 before installation, accept the SDK prompt, then restart the game.
- **Sending items:** a named recipient takes priority over a stale All players mode. Missing recipients fail clearly, and guest delivery rejects host-controller or host-mailbox mismatches.
- **Faster boosting:** shorter waits for unverified guest UVHM objective reads and faster verified mission steps. Rank-up settle waits and guest save/reload confirmation remain in place.
- **Setup:** accepts BL4's inner Win64 folder and checks the actual game location. It now detects the SDK's Python plugin and embedded runtime; **Install SDK + Squ1ggs mod** installs them. No separate system Python installation is needed.
- **Appearance:** the BL4 character swapper is back, with native hunters, NPCs, enemies and bosses. Search or filter the list, select one character, preview it, then apply or restore your appearance.
- **Picture to Item:** load an item-card picture, read the visible details, review the closest known match, then take it into the builder. Check the result before sending it; a picture may not show every hidden part.
- **Builds:** browse and manage saved item lists, inspect parts, validate an item, preview its card, and send the finished item to yourself or the lobby. Existing saved lists appear automatically.
- **Better item cards:** improved item names, prefixes, parts, elements, firmware and rarity display, including pearlescent items, with closer in-game stat previews.
- **Map unlocking:** one **Clear map fog** action discovers location markers and runs the main Kairos reveal route for your Boost target. Players visit twelve stops, spend eight seconds at each, then return to where they started. Allow a few minutes and keep everyone connected. Some safehouse claims still need a visit.
- **Missions:** dedicated mission controls and progress reporting, with mission options in MAX ALL and Auto Lobby. Give everything runs missions before challenges and UVHM, then completes a supported side mission to help register the challenge progress.
- **Better UVHM passes:** improved guest handling, rank 1–7 sequencing and objective verification. Failed or incomplete work is reported instead of being presented as a successful pass.
- **Better loot shapes and 3D pinning:** improved placement and holding for 3D loot shapes, with automatic air holding, optional drop timing and co-op placement controls. **I should have done this when I first released the 3D shapes.**
- **Give everything:** one selected-target workflow for MAX ALL options, missions, challenges, UVHM and map discovery, with progress and a Stop control. Map clearing uses the same route as the standalone button; you do not need to run it twice.
- **Home shortcuts and world tools:** Clear map fog, Auto revive and Low power are easier to reach. Black Market spawning can create a missing native machine and checks that placement finishes.
- **Co-op item delivery:** larger guest lists use paced reward packages. Save Pack and Live Pack let you copy, relevel, save and send item serials.

## Get started

1. Keep this whole folder together and run **Squ1ggsBoostingTools.exe**.
2. Use Setup to choose the Borderlands 4 install folder and install the SDK and bundled Squ1ggs mod if needed.
3. Fully quit and restart Borderlands 4, load a character, then wait for **Online** in the app.
4. Check **Boost target** before starting an action. Pick a player or **All players** where supported.

After an update, close the old app, run the new build, install the bundled mod and fully restart Borderlands 4. Keep the game unpaused while actions run.

## Using the new controls

**Trying Appearance?** Open **Appearance**, pick one BL4 character, and use **Preview selected character** before **Apply selected model to me**. Turn on third person to inspect the model. **Restore my appearance** returns your original body; **Remove unworn previews** clears previews. Content must be installed to load. This local test build still needs live checks for rendering, animation, respawn, travel and visibility to other players. Keep the experimental lobby hiding option off while testing.

**Just want the map cleared?** Use **Clear map fog** on Home or World. It is the same action wherever it appears. The older host-sweep and guest-assist controls have been replaced in the menus.

**Doing a full boost?** Use **Give everything** and let its progress finish. It already includes map discovery and the reveal route. The Stop control cancels the active workflow.

Mission gates and blocked travel stops can leave a partial result; check the reported outcome. Save and reload the guest's own character to confirm progression and map results.

Non-UVHM challenge completion does not automatically open a large reward queue in multiplayer. For large queues, console and cross-play players should leave the lobby, open rewards in solo, sell unwanted items, then rejoin.

## Downloads and support

- [Official releases](https://github.com/Squ1ggs/Bl4SDKmods/releases)
- [Source and issue tracker](https://github.com/Squ1ggs/Bl4SDKmods)
- [ScootersGarage Discord](https://discord.gg/DqetrAK2sJ)
- [Support Squ1ggs](https://ko-fi.com/rdpsqu1ggs)

## Credits and thanks

- **Azalea Asvail:** [GitHub](https://github.com/AzaleaAsvailAMW) · [Azzy UVH Booster](https://github.com/AzaleaAsvailAMW/amw-Uvhbooster). Her SHiFT UI management and friend auto-accepter are used through SQBT's SHiFT integration; that work remains hers. [Mods page](https://save-editor.be/GZO/Mods.html#/borderlands-4) · [direct download](https://save-editor.be/GZO/mods/api.php?action=download&id=92c8f31dd95c34f0).
- **BL SDK contributors:** the SDK and mod-loading ecosystem that make these tools possible.
- **GZO / save-editor.be** and **Lootlemon:** item catalogs and reference data.
- **Scooter's Toolbox:** Simple Builder editor integration.
- **Tobgun** and everyone testing, sharing feedback and reporting bugs.

See the bundled **CREDITS.md** for additional attribution. The bundled mod is licensed under GPL-3.0.
