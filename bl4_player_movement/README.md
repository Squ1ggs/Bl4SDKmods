# BL4 Player Movement

On-foot **CharacterMovement** tuning for **Borderlands 4** via the official Python SDK (`mods_base` / Oak2 mod manager).

**Author:** Squ1ggs · **License:** [MIT](LICENSE)

## Install

**Recommended — `.sdkmod`:** copy **`bl4_player_movement.sdkmod`** into your game’s **`sdk_mods`** (next to `__main__.py`) or into **`sdk_mods/sdkmod_dist`**. It is an Oak2 package zip: **one** top-level folder named **`bl4_player_movement`** inside the archive, matching the filename stem. Do not unzip it yourself for normal use—the mod manager loads it as a package.

**Optional — folder:** if you prefer a loose package instead of the zip, copy the whole **`bl4_player_movement`** directory into **`sdk_mods`** and enable the mod under **`mods`**. (In this repo the same `.sdkmod` is also bundled inside the folder for convenience—use **either** the zip **or** the folder in `sdk_mods`, not both.)

Requires a normal BL4 SDK install. **Ultra Local Menu is not required.**

## Usage

Console → **`mods`** → enable **BL4 Player Movement** → **Mods → BL4 Player Movement** for sliders, presets, and **Apply tuning to** (local / all / others).

Use **in open gameplay** (not only main menu) so your pawn exists. Values are **session-oriented** and may reset on travel.

### Default keybinds

| Key | Action |
|-----|--------|
| Ctrl+Shift+F5 | Reset on-foot movement to defaults |
| Ctrl+Shift+F6 | Log current values (`player_move_show`) |

Rebind under **Mods → BL4 Player Movement → Keybinds** if needed.

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

## Development tools (optional mention)

Inspecting the game with **Live Editor** or the console is common while building SDK mods. This package does **not** depend on **blimgui** at runtime.

**MIT** does not require you to credit tools you only used for research. A short “thanks / data from Live Editor” line is **optional** transparency for other authors, not a legal requirement for this project unless you redistribute someone else’s code under stricter terms.
