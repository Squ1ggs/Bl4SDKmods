# BL4 Vehicle Movement

Vehicle and Chaos movement tuning for **Borderlands 4** via the official Python SDK (`mods_base` / Oak2 mod manager).

**Author:** Squ1ggs · **License:** [MIT](LICENSE)

## Install

**Recommended — `.sdkmod`:** copy **`bl4_vehicle_movement.sdkmod`** into **`sdk_mods`** or **`sdk_mods/sdkmod_dist`**. Oak2 expects a zip with **exactly one** top-level folder named **`bl4_vehicle_movement`**. Leave it as `.sdkmod`; the manager loads it—no manual unzip for normal play.

**Optional — folder:** copy the whole **`bl4_vehicle_movement`** directory into **`sdk_mods`** instead if you use loose packages. Don’t duplicate the same mod as both zip and folder under `sdk_mods`.

Requires a normal BL4 SDK install (the game loads `sdk_mods/__main__.py` and `mods_base`). **Ultra Local Menu is not required.**

## Usage

Open the console, run **`mods`**, enable **BL4 Vehicle Movement**, then use **Mods → BL4 Vehicle Movement** for sliders, presets, and target scope (**Apply tuning to**: local / all / others).

**Enter a vehicle first** for per-target tuning. Values are **session-oriented** and may reset on travel or reconnect.

### Default keybinds

| Key | Action |
|-----|--------|
| Ctrl+Shift+F7 | Reset vehicle movement to defaults |
| Ctrl+Shift+F8 | Log current values (`vehicle_move_show`) |

Rebind under **Mods → BL4 Vehicle Movement → Keybinds** if needed.

### Console commands

Run **`vehicle_move_help`** for the full list. Short reference:

| Command | Purpose |
|---------|---------|
| `vehicle_move_target` | `local` \| `all` \| `others` (matches Mods spinner) |
| `vehicle_move_show` | Log current floats |
| `vehicle_move_reset` | Reset to bundled defaults |
| `vehicle_move_preset` | Named preset: `boost`, `crawl`, `floaty`, `orbit`, `heavy`, `drift` |
| `vehicle_move_set` | Set one float, e.g. `vehicle_move_set MaxWalkSpeed 1200` |
| `vehicle_move_scan_floats` | Discovery: list float fields on the movement component |
| `vehicle_move_vault_show` | Log vault power cost fields on scoped pawn(s) |
| `vehicle_move_vault_zero` | Zero vault power costs on scoped pawn(s) |
| `vehicle_move_vault_set` | Set all vault power `.Value` fields to one number (≥ 0) |

## Settings

Persisted options are stored next to other SDK mods, typically:

`sdk_mods/settings/bl4_vehicle_movement.json`

## Co-op / fairness

Registered with **`CoopSupport.ClientSide`**. Tuning is intended for your client; respect session rules and other players when using **all** / **others** scopes.

## Development tools (optional mention)

Using **BL4 Live Editor** or similar tools to **inspect** Unreal objects while you write a mod is normal. These mods do **not** bundle or require **blimgui** at runtime.

Under the **MIT** license you are **not** obligated to list every editor you used. Saying something like “field names were cross-checked with Live Editor dumps” in a Credits section is **optional** but helps other modders; it is not a substitute for following **third-party licenses** if you ever **copy** someone else’s source into this repo.
