# BL4 Character Swapper 0.1.3

Standalone native Borderlands 4 character swapping by RDPSqu1ggs.

0.1.3 preserves native single-spawn defaults, gives spawning a fresh timeout
after package loading, and reports the failing stage and native actor counts.
Moxxi preview and attachment passed live testing. Known issue: Vex failed to
spawn in the tested session.

- Search native BL4 hunters, NPCs, enemies and bosses.
- Preview, apply and restore from the strongly recommended BLImGui F10 picker.
- Select local or lobby targets from the picker.
- Use `asw_*` SDK console controls without BLImGui.
- Supports official BLImGui's window API and compatible customised tab menus.
- Runs without Squ1ggs Boosting Tools.

Character swapping is already included in Squ1ggs Boosting Tools' Appearance
tab. Desktop users do not need this separate package or BLImGui.

The catalog is metadata, not proof that every entry renders correctly. Host
authority is required for previews and selected-player changes. Live
preview/apply/restore, respawn/travel cleanup and multiplayer visibility remain
release-candidate checks; no broader compatibility claim is made.

There are a lot of characters and bosses, so not all have been fully tested. Further testing and regular updates are planned. Characters retain their own animations, which may stay in idle while you move.

The unsuccessful movement-animation experiment was reverted and is not included.
