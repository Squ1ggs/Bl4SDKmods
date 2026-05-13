# BL4 Player Movement

On-foot **CharacterMovement** tuning for **Borderlands 4** via the official Python SDK (`mods_base` / Oak2 mod manager).

**Author:** Squ1ggs · **License:** [MIT](LICENSE)

## Install

**Recommended — `.sdkmod`:** place **`bl4_player_movement.sdkmod`** in **`sdk_mods`** (next to `__main__.py`) or **`sdk_mods/sdkmod_dist`**. Oak2 package zip: single top-level folder **`bl4_player_movement`**, matching the filename stem. Do not unzip for normal play—the mod manager loads it as a package.

**Optional — loose folder:** copy the **`bl4_player_movement`** directory into **`sdk_mods`** and enable under **`mods`**. Either the zip **or** the folder, not both.

Requires a normal BL4 SDK install. **Ultra Local Menu is not required.**

## Usage

Console → **`mods`** → enable **BL4 Player Movement** → **Mods → BL4 Player Movement** for sliders, presets, and **Apply tuning to** (local / all / others).

Requires an in-world pawn (not main menu only). Values are **session-oriented** and may reset on travel.

### Default keybinds

| Key | Action |
|-----|--------|
| Ctrl+Shift+F5 | Reset on-foot movement to defaults |
| Ctrl+Shift+F6 | Log current values (`player_move_show`) |

Rebind: **Mods → BL4 Player Movement → Keybinds**.

### Console commands

Run **`player_move_help`** for the full list. Short reference:

| Command | Purpose |
|---------|---------|
| `player_move_target` | `local` \| `all` \| `others` |
| `player_move_show` | Log current movement floats |
| `player_move_reset` | Reset to bundled defaults |
| `player_move_preset` | `fast`, `slow`, `moon`, `tank`, `ice` |
| `player_move_set` | e.g. `player_move_set MaxWalkSpeed 900` |
| `player_move_scan_floats` | List float fields on the movement component |
| `player_move_vault_show` | Log vault / traversal cost fields |
| `player_move_vault_zero` | Zero vault power costs (dash, jump, glide, grapple, slam, forgiveness) |
| `player_move_vault_set` | Set all vault power `.Value` fields to one number (≥ 0) |

## Settings

`sdk_mods/settings/bl4_player_movement.json`

## Co-op / fairness

**`CoopSupport.ClientSide`**. Be careful with **all** / **others** in multiplayer.

## Oak2 mod database

**`pyproject.toml`:** metadata for [BL4 SDK Mod Database](https://bl-sdk.github.io/oak2-mod-db/) / [Adding to the Mod DB](https://bl-sdk.github.io/developing/#adding-to-the-mod-db). **`[tool.sdkmod].download`** must match the URL of **`bl4_player_movement.sdkmod`**.

## Development tools (optional)

**Live Editor** / console are typical for SDK mod work. No **blimgui** runtime dependency.
