# BL4 Character Swapper

Created by **RDPSqu1ggs** Â· [original repository](https://github.com/Squ1ggs/Bl4SDKmods).

Version **0.1.3** supports **Borderlands 4 only**. This is a standalone SDK mod: neither the Squ1ggs Boosting Tools EXE nor its SDK mod is required.

**BLImGui is strongly recommended** for the searchable F10 character picker, character groups, target selection and preview/apply/restore controls. Console-only use remains supported.

**Already using Squ1ggs Boosting Tools?** Character swapping is included in the tool's **Appearance** tab. You do not need this separate mod or BLImGui for the desktop interface. Matching releases share the same appearance core when installed together.

## Recommended BLImGui download

Use the official **juso / smugg BLImGui 1.1** package:

- [Fixed official BLImGui 1.1 download](https://github.com/juso40/blimgui/raw/ff5be35f41d69f28056befdd1bfb8caddae5892b/blimgui.zip)
- [Official BL4 SDK database page and installation instructions](https://bl-sdk.github.io/oak2-mod-db/mods/blimgui/)

The linked archive was inspected on 2026-10-17: it explicitly supports BL4 (`Game.Oak2`) and contains the Python 3.14 x64 ImGui Bundle and pydantic-core binaries used by the current SDK. The swapper supports its window API and compatible custom BLImGui tab APIs. This compatibility inspection is not proof of an in-game character swap.

Extract the archive so **`sdk_mods/blimgui/__init__.py`** exists, with its `dist64` folder beside it. Keep the supplied dependencies together; there is no separate pip/Python installation step. Restart BL4, enable the swapper and press **F10**. Do not nest it as `sdk_mods/blimgui/blimgui`.

If another window is already using official BLImGui, close it before opening Appearance. The swapper does not take over or close another mod's window. If an SDK update changes Python versions, use the official database page to check for a matching updated BLImGui build.

Inspected download SHA-256: `20f85a7386bf057fee2c6084e910daee8bfb09df8cb22af4627a0bc7a4bc18b4`.

## Controls

With official BLImGui, **F10** opens the Appearance window. With a compatible custom tab menu, it opens the **Appearance** tab. Without BLImGui, the mod still enables and can be controlled from the BL4 SDK console:

- `asw_help` â€” show the full command list.
- `asw_list [search]` â€” search the full native BL4 character catalog.
- `asw_players` â€” list yourself and lobby players by target index.
- `asw_preview <name or code>` â€” spawn a preview beside you (host authority required).
- `asw_apply <name or code>` â€” apply a model to yourself.
- `asw_apply <name or code> --player INDEX` â€” host applies it to one lobby player.
- `asw_restore [--player INDEX]`, `asw_restore_all`, and `asw_clear` â€” restore appearances or remove unworn previews.

The picker contains 1,649 native definitions, including Vex, Rafa, Amon, Harlowe, C4SH and Loveless. Models load on demand; entries may fail if their content is unavailable or their definition cannot produce a usable appearance. Catalog inclusion does not mean every model has passed an in-game test. `asw_players` refreshes as the lobby changes, so check indexes before targeting another player.

## Installation

Install the [BL4 Python SDK](https://bl-sdk.github.io/oak2-mod-db/), then place **`bl4_character_swapper.sdkmod`** in `sdk_mods` and enable **BL4 Character Swapper**. Keep that filename: the SDK requires it to match the package inside. BLImGui is optional but strongly recommended. The matching SQBT release shares this appearance controller. Mismatched runtime versions require a game restart; older SQBT appearance controllers must be restored before use. Install only one copy of the standalone package; remove earlier development archives or duplicate loose copies before restarting. Do not install a separate system Python or use `pip` for BLImGui; retain the dependencies supplied inside its `dist64` folder.

The mod queues game changes onto BL4's game-thread tick. The UI reads cached choices and queues actions; the console commands use the same controller.

## Current limits

Host authority is required to create previews and change another lobby player's appearance. Selected-player replication, map travel, respawn restoration and disabled-mod cleanup still need live multiplayer validation. Different skeletons keep the source character's existing animation; weapon/aim retargeting is unfinished. Vehicle swaps and foreign-game characters are outside this release. This standalone package contains code and catalogue metadata, no ripped meshes, textures, PAKs or boosting functions.

## Authorship and licence

Appearance code and integration: **RDPSqu1ggs**, GPL-3.0-or-later. See `LICENSE`, `COPYING` and `provenance.json` for source notices. BL4 assets belong to Gearbox / 2K. SDK and optional BLImGui dependencies retain their authors' licences.

## Optional character packs

An add-on imports `Model`, `register_model` and `unregister_model` from `bl4_character_swapper`, then registers a unique `pack:` key, display name, source-game group, author, game-thread spawn callback, and optional game-thread tick callback. Add-ons must provide their own models, materials, animation and lifecycle handling; no foreign-game pack is bundled here.

## Current validation

There are a lot of characters and bosses, so not all have been fully tested. Further testing and regular updates are planned. Characters retain their own animations, which may stay in idle while you move.

Moxxi preview and attachment are confirmed in-game. See RELEASE_NOTES.md for known issues.
