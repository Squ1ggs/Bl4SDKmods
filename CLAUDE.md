# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo overview

Borderlands 4 **Python SDK** mods for the game's `sdk_mods` folder (Oak2 Mod Manager / `mods_base` / `unrealsdk` — the PythonSDK framework itself lives outside this repo, inside the game install).

Two kinds of shippable output live side by side:

- **Standalone mods** (`bl4_player_movement`, `vehicle_movement`, `challenge_ticker`, `damage_and_more`, `resources_and_cooldowns`, `mob_spawner`, `p2p_teleporter`, `world_travel`) — small, single-purpose, MIT-licensed, distributed as `.sdkmod` files and listed on the BL Oak2 Mod DB.
- **Squ1ggs Boosting Tools (SQBT)** — an all-in-one boosting toolkit split across two halves that must be treated together:
  - `Squ1ggsBoostingTools/` — the GPL-3.0 SDK mod (a superset that embeds the tuning logic of the standalone mods above).
  - `squ1ggs_boosting_tools_app/` — an Electron desktop app that is the actual UI; it drives the mod over a localhost HTTP bridge. Distributed only via GitHub Releases, never the Mod DB.

## Commands

There is no lint/test runner in this repo (no ruff/pytest/mypy config anywhere). Correctness is checked by loading mods in-game and, for SQBT, via the in-game dev smoke panel (`Squ1ggsBoostingTools/dev_smoke.py`, opened with Ctrl+Alt+Shift+F9).

**Packaging a standalone mod as `.sdkmod`:** a `.sdkmod` is literally a zip of the mod's folder with one top-level directory matching the zip's basename (e.g. `bl4_player_movement.sdkmod` → `bl4_player_movement/__init__.py`, `pyproject.toml`, `README.md`, `LICENSE`). There's no packaging script — after editing a mod's source, re-zip that folder to refresh the committed `.sdkmod` before it will pick up changes in-game.

**Desktop app** (`squ1ggs_boosting_tools_app/`, run npm scripts from that directory):
```powershell
npm run check          # node --check syntax pass over main/preload/lib/renderer JS
npm run sync:sdkmod    # copy ../Squ1ggsBoostingTools -> resources/Squ1ggsBoostingTools (runs automatically as `prepack`)
npm run dist:portable  # pack + pack:zip -> ../dist_squ1ggs_boosting_tools/*.zip
npm run dist:win       # nsis installer build
```
`sync_sdkmod.py` excludes `__pycache__`, `.pytest_cache`, `logs`, `tools`, and stray `*.pyc/*.sdkmod/*.log/*.jsonl`/`spawn_batch_*`/`spawn_test_*` files when syncing — the packaged app always ships a fresh copy of the live mod source, not the checked-in `.sdkmod`.

## Version bookkeeping

Every mod's version is declared **twice** in `pyproject.toml` and must match:
```toml
[project]
version = "X.Y.Z"
[tool.sdkmod]
version = "X.Y.Z"
```
SQBT additionally hardcodes the version a **third** time in `Squ1ggsBoostingTools/_mod_version.py` (`__version__`/`__version_info__`), imported first thing in `__init__.py` specifically so it's safe to read before any other submodule loads. A comment in SQBT's `pyproject.toml` calls out that drift between it and `_mod_version.py` has shipped a stale `mod_version` before — bump all three together. The desktop app's `package.json` version is tracked separately (its own EXE version) but is referenced in the shared `Squ1ggsBoostingTools/CHANGELOG.md` as `<mod version> / EXE <exe version>`.

## Standalone mod architecture

Each standalone mod is a single-file (or near single-file) `mods_base` package:
- One `__init__.py` calling `mods_base.build_mod(...)` at import time, registering `commands=[...]` (via `@command("name", ...)` + `.add_argument`), `keybinds=[...]` (via `mods_base.keybind`), and `options=[...]` (`SliderOption`/`BoolOption`/`SpinnerOption`/`ButtonOption`/`GroupedOption`) that show up in the in-game Mods menu.
- Console commands share a per-mod prefix: `player_move_*` (bl4_player_movement), `vehicle_move_*` (vehicle_movement), `bdam_*` (damage_and_more), `brc_*` (resources_and_cooldowns), `bms_*` (mob_spawner), `bcst_*` (p2p_teleporter), `bwt_*` (world_travel), `bl4cu_*` (challenge_ticker).
- A BLImGui tab is optional and only registers if [BLImGui](https://github.com/juso40/blimgui) is present; console commands and the plain Mods-menu options always work without it.
- Values are applied by resolving live `unrealsdk` objects at call time (e.g. walking `OakPlayerController` → pawn → `OakCharacterMovement`/movement component and `setattr`-ing float fields) rather than editing static game assets — most tuning is session-only and gets re-applied on keybind/slider/"sticky re-apply" rather than persisted into the save.
- Mods declare `coop_support` (`ClientSide` for pawn-local tuning vs `Unknown`/host-gated for actions that touch other players or the world), and many expose an **"Apply tuning to" (local / all / others)** scope spinner that mirrors a `*_target` console command.

## Squ1ggs Boosting Tools (SQBT) architecture

`Squ1ggsBoostingTools/__init__.py` is the composition root: it imports version info first, then wires ~15+ feature submodules' commands/keybinds into one `build_mod(...)`, with most real setup happening in `_on_enable()`/`_on_disable()` (not at import time) so failures in one subsystem (bridge, hooks, companion pak, session guards) are caught and logged independently rather than blocking mod load.

Key subsystems, each its own module:
- **`external_bridge.py`** — a `ThreadingHTTPServer` on `127.0.0.1:50675` (falls back through a candidate list, or port 0, if the preferred port is taken — see `_PORT_CANDIDATES`) that the desktop app polls/drives via `do_GET`/`do_POST`; `bridge_catalog.py` and `backend_actions.py` implement the actual actions dispatched through it. Console: `sqbt_bridge status`.
- **`embedded_bdam/`, `embedded_brc/`, `embedded_bpm/`, `embedded_bvm/`** — each mirrors a standalone mod's tuning engine (`engine.py`) plus a `sqbt_coop.py`, so SQBT can offer Damage & More / Resources & Cooldowns / Player Movement / Vehicle Movement tuning inline. `tuning_embed.py` decides at `_on_enable()` time whether to drive these or defer to a separately-enabled standalone mod, sharing the same settings file either way — **don't edit tuning logic in only one place**; check whether the standalone mod and its `embedded_*` counterpart both need the change.
- **`companion_pak.py`** — installs a bundled `.pak` (`pakchunk991-SQBT-PearlPools-Windows_991_P.pak`, sha256-verified) into the game's paks directory before certain loot features work; requires a restart if freshly installed.
- **`item_spawn/`, `world_spawn*.py`, `mob_spawner_ui.py`, `encounter_builder.py`** — spawning/loot subsystems, backed by JSON catalogs (`item_pools.json`, `squ1ggs_world_spawn_catalog.json`, `travelmaps_flat.json`, `gzo_parts_map.json`, `shiny_serials.json`, etc.) rather than hardcoded tables.
- **`peer_session.py`** — on enable, pauses/tracks any of the standalone mods listed above if they're also enabled (to avoid duplicate hooks/handlers), and restores them on disable.
- **`runtime_log.py`** — structured session logging (`sqbt_runtime.log`) used throughout for diagnostics beyond the normal `unrealsdk.log`.

`squ1ggs_boosting_tools_app/` (Electron) is the UI for SQBT: `main.js`/`preload.js` + `lib/*.js` (bridge client, game path discovery, SDK/mod install, settings, update checks) form the backend/main process; `renderer/app.js` + `renderer/index.html` form the UI. `lib/bridge.js` holds the client-side view of the same port/candidate list as `external_bridge.py` — keep both in sync if the port scheme changes.

## Cross-mod conventions

- Distribution split: everything MIT-licensed is on the BL Oak2 Mod DB; SQBT (GPL-3.0) is GitHub-only, per each README and the repo root README's mod table.
- "Sticky re-apply" (damage_and_more, resources_and_cooldowns) and "Apply tuning to" scope exist because BL4 can silently reset tuned fields on respawn/travel — mods re-push values rather than assuming a one-time `setattr` sticks.
- Host-authority actions (world travel, BMS spawns, UVHM/challenge bulk actions, some P2P teleports) are called out explicitly in READMEs/docstrings because they only work reliably for the session host — preserve those caveats when touching that code or its docs.
