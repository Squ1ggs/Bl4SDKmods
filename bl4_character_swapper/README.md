# BL4 Character Swapper

By **RDPSqu1ggs** · Version **0.2.13**

Preview a BL4 character, apply their appearance, or restore your original
appearance. Hosts can also choose another lobby player. Optional character
packs add characters from other games. No desktop app is required.

## Install

1. Install the BL4 Python SDK.
2. Close Borderlands 4.
3. Put `bl4_character_swapper.sdkmod` in the game's `sdk_mods` folder.
4. Extract any optional character pack ZIPs at the game root, where
   `OakGame` and `sdk_mods` are located.
5. Restart BL4, load a map and enable **BL4 Character Swapper** in SDK Mods.

Character swapping is also included in Squ1ggs Boosting Tools. Use its
Appearance page if you prefer the desktop app. Update matching runtime
downloads together when using more than one interface.

## Controls

The SDK Mods options work without BLImGui. Refresh characters and players,
select a target, then browse to a character and choose **Preview** or **Apply**.
Use **Restore** to return to the original appearance.

- **F9** switches your first/third-person view. The menu also has a view button.
- **F10** opens the optional BLImGui character picker.
- Keybinds can be changed in SDK settings.
- Matching-rig pose following is automatic. The picker can reapply after respawn.

Install BLImGui separately if you want its searchable picker. If another mod
has its window open, close that window before opening the character picker.

SDK console shortcuts include `bl4cs_list NAME`, `bl4cs_preview NUMBER`,
`bl4cs NUMBER`, `bl4cs_restore`, `bl4cs_clear` and `bl4cs_help`.
Numbers refer to the latest search results. `bl4cs_players` lists lobby targets.

## Coverage

The list is Borderlands 4 characters. An extra character appears only after
you install that character's pack, and the list uses the name from the pack.
This mod does not include extra character models.

Wearing an enemy or boss keeps friendly characters friendly. The worn body
uses your team, and you stay targetable.

Some added characters keep their own held items. While you wear them, the
game's first-person gun and default arms stay hidden. Aiming, firing,
reloading, and switching weapons stay on the normal controls.

Some Borderlands 4 entries need DLC or files that are not on your PC. If a
model cannot load, your original appearance stays. Other players may not see
the swap.

Vehicle controls are provided by the separate **BL4 Vehicle Swapper** or the
desktop app's Vehicle page. Optional models are not bundled in this SDK mod.

Code: GPL-3.0-or-later. Included licence and source credits apply.
