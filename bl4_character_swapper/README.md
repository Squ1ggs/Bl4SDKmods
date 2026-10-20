# BL4 Character Swapper

By **RDPSqu1ggs** | [Source code](https://github.com/Squ1ggs/Bl4SDKmods)

Swap your appearance to a BL4 NPC, enemy, boss or Vault Hunter. Preview a character,
apply it to yourself, or restore your original appearance. Hosts can also select
a lobby player.

Version **0.2.8** requires the BL4 Python SDK and runs without Squ1ggs Boosting
Tools. This download is for BL4 characters. Vehicle controls are not included.

## Install

1. Install the [BL4 Python SDK](https://bl-sdk.github.io/oak2-mod-db/).
2. Put `bl4_character_swapper.sdkmod` directly in `sdk_mods`. Keep its filename
   and remove any duplicate loose copy of the mod.
3. Restart BL4, load into a map and enable **BL4 Character Swapper**.

Character swapping is already included in SQBT's Appearance tab, so you only need
one of them. If both are installed, disable one and restart.

## Use the SDK Mods menu

BLImGui isn't required. Open the SDK console, type `mods`, select **BL4 Character
Swapper**, and open its options.

- Choose **Refresh characters and players**.
- Set **Change appearance for** to yourself or a lobby player.
- Open **Browse characters**, then a category, page and character.
- Choose **Preview this character** or **Apply this character**.

Wait for a preview to finish before applying. Restore, remove previews and check
status from the same menu. Refresh the player list if someone joins or leaves.

## Console shortcuts

```text
bl4cs_list moxxi
bl4cs_preview 1
bl4cs 1
bl4cs_status
bl4cs_restore
```

You can also type `bl4cs Moxxi` directly. If several characters match, the mod
shows numbered choices. Numbers refer to your most recent search results.

For more results, repeat your search with `--page`, for example
`bl4cs_list boss --page 2`. Use `bl4cs_players` to list lobby targets, then
`bl4cs 1 --player 1` to apply your selected character to that player.
`bl4cs_clear` removes previews; `bl4cs_help` lists all commands. Older `asw`
commands remain available as aliases.

## Optional BLImGui picker

BLImGui is strongly recommended if you prefer a searchable F10 window.
The SDK Mods menu and console commands work without it.

- [BLImGui installation and downloads](https://bl-sdk.github.io/oak2-mod-db/mods/blimgui/)
- [Pinned BLImGui 1.1 download](https://github.com/juso40/blimgui/raw/ff5be35f41d69f28056befdd1bfb8caddae5892b/blimgui.zip)

Extract it so `sdk_mods/blimgui/__init__.py` and its `dist64` folder exist.
Keep the bundled dependencies together, restart BL4 and press **F10**. If another
mod is using the BLImGui window, close that window first.

## Known limits

Not every character or boss has been tested. Some entries need DLC or may fail
to spawn; Vex failed in an earlier test. Moxxi preview and attachment worked in
that test, but this does not establish that the whole catalog works.

Characters use their own animations, which may stay idle while you move.
Gun holding, aiming, custom first-person arms and vehicle seating are unfinished.
Multiplayer visibility, respawn and map travel need more testing. Creating
previews and changing another player's appearance require the host.

Separate character packs are optional and are not included in this download.

## Optional character packs

Separately installed character packs appear in the picker. Packs marked
**preview only** cannot be applied. The standalone download contains code and
catalog data, not character meshes, textures or game archives.

Pack manifests go in `sdk_mods/appearance_packs/<id>/pack.json`. Restart BL4 after
adding or removing a pack. Pack authors can use `Model`, `register_model` and
`unregister_model` to register their own characters. See the source for the API.

## Licence

Code by **RDPSqu1ggs**, licensed under **GPL-3.0-or-later**. See `LICENSE`, `COPYING`
and `provenance.json`. BL4 assets belong to their respective owners. The SDK and
BLImGui retain their own licences.
