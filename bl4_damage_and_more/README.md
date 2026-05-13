# BL4 Damage & More

Tweaks **OakDamageState** and **OakDamageCauserData** on your **local pawn** (incoming damage/healing/resists, outgoing damage/crit/radius/healing, plus advanced scalars where the build exposes them).

**Author:** Squ1ggs · **License:** [MIT](LICENSE)

## Install

**Recommended — `.sdkmod`:** copy **`bl4_damage_and_more.sdkmod`** into **`sdk_mods`** or **`sdk_mods/sdkmod_dist`**. The archive must contain a **single** root folder **`bl4_damage_and_more`**. Use the file as-is (Oak2 loads `.sdkmod` packages directly).

**Optional — folder:** copy the **`bl4_damage_and_more`** folder into **`sdk_mods`** if you prefer not to use the zip. Use **either** the `.sdkmod` **or** the folder, not both with the same mod id.

Requires BL4 Python SDK / `mods_base`. **Ultra Local Menu is not required.**

## Usage

Enable in **`mods`**, then **Mods → BL4 Damage & More** for toggles, sliders, and **Sticky re-apply** (helps when the game overwrites structs).

Effects are **session-oriented**; re-apply after travel if needed.

### Default keybind

| Key | Action |
|-----|--------|
| Ctrl+Shift+F10 | Run `bdam_apply` |

### Console commands

| Command | Purpose |
|---------|---------|
| `bdam_help` | List commands |
| `bdam_apply` | Apply current sliders to local pawn |
| `bdam_reset` | Reset sliders to defaults and apply |
| `bdam_status` | Log master toggle, sticky hook, pawn resolution |
| `bdam_probe` | Log field presence on DamageState / DamageCauserData |

## Settings

`sdk_mods/settings/bl4_damage_and_more.json`

## Co-op / fairness

**`CoopSupport.ClientSide`**. This mod targets **your** local pawn; do not assume fairness or sync rules in online play beyond what the game already allows.

## Development tools (optional mention)

The in-code comments note that **property paths mirror BL4 Live Editor**-style dumps (`OakCharacter` → `DamageState` / `DamageCauserData`). That documents **how the mod was authored**, not a runtime dependency.

This mod does **not** ship or require **blimgui**.

You **do not have to** mention Live Editor or blimgui in your README for **MIT** compliance if you only used them as inspection tools. Mentioning Live Editor (or similar) is still useful for **other modders** who want to verify offsets/paths on new patches—entirely optional.
