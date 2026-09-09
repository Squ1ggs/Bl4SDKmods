# Changelog

## 3.8.139 / EXE 1.1.133
- **Spawn shapes (new/restored on this drop):** diamond (3D), blocks, cube, torus, crown, UFO, rocket, gear — if you stayed on the last public release, grab this build so these shapes are actually on disk.
- **Send serials Browse / YAML:** loads into the paste box (blank line between codes) — not the optional queue and not My Library.
- **Add to library…** next to Send items: saves the paste box into My Library under a name you choose.
- **Open rewards:** still opens one package at a time (safe path); no bulk open.
- **Loot text / Spell a word:** restored 3-line shinies/pool lettering where relevant.
- **Co-op shapes:** silhouette drip / settle fixes so guests can grab without floor piles or mid-dump snaps.

## 3.8.243 / EXE 1.1.224
- **Send serials Browse / YAML:** loads into the paste box (blank line between codes) — not the optional queue and not My Library.
- **Add to library…** next to Send items: saves the paste box into My Library under a name you choose (reuse later).

## 3.8.242 / EXE 1.1.223
- **Loot text / Spell a word restored:** 3-line shinies/pool lettering (MODS / ARE / FREE style) back on Loot + Loot Shapes, with full glyph font, spawn_text_shape, and shape_text wiring through shinies/pools.

## 3.8.241 / EXE 1.1.222
- **Restored missing 3D shapes** from the pre-standalone tree: UFO, rocket, gear, diamond (3D), blocks, cube, torus, crown (were left behind when dist folders moved to Documents).
- **Forbidden** shapes stay unlock-only / hidden again (not the “missing” list).
- **Car:** fat sedan / driver-seat cabin back (was slim batmobile).
- **Co-op drop method:** guests get sparse mid-flight samples of rain/slow/medium again (not shoot-high-then-snap). Grab collision kept on frozen silhouette pins.

## 3.8.240 / EXE 1.1.221
- **Co-op shapes restore:** removed owner-only dump suppress + settle hide-debris + full re-push of already-synced pins (that broke guest grabs and left floor piles/dupes). Back to host local pin + throttled guest slot drip (~2/s) + settle pending-only repin.
- **Shapes:** `the forbidden one` / `the forbidden pair` back in the normal 3D list (were unlock-only / missing from panel).

## 3.8.239 / EXE 1.1.220
- **Co-op shapes (the ask):** friends watch the silhouette build live with the host. ULM dump ballistics are suppressed for guests; each host pin drips the frozen slot pose (~2 every 0.42s). Settle still full-pushes + clears floor leftovers. Grabable; avoids mid-dump ForceNetUpdate storms.

## 3.8.238 / EXE 1.1.219
- **Co-op ULM dump + shape:** removed mid-dump guest drip (that looked like sky→floor→snap). Host pins stay owner-only until settle, then one full silhouette push; leftover floor spit is hidden after settle.

## 3.8.237 / EXE 1.1.218
- **Serials UI:** one Optional queue fold (list + Deliver queued) — removed the duplicate second fold.
- **EXE scroll thrash:** status polls no longer reload GZO/catalogs every tick (was flipping pages / scrolling).
- **UVHM:** clearer target-one errors (needs a single Boost target); progress bar keeps a short grace so it does not blink off between ranks.
- **Co-op 3D shapes:** join guest net starts sooner (less floor-drop on join); mid-lobby Spawn All drips a few frozen pins to guests so they do not watch a floor pile until settle.

## 3.8.236 / EXE 1.1.217
- **Reward opens (GZO / serials):** one package at a time with a **3–5s** gap; always opens the live newest mail (no stale indices). Removed `Server_OpenAllPackages` bulk path that could AV / blank backpacks in MP.
- **Browse YAML / STBX:** still extracts `serial: '@U…'` (from 3.8.235).

## 3.8.235 / EXE 1.1.216
- **Browse YAML / STBX saves:** extract `serial: '@U…'` fields (quoted save-editor YAML). Empty browse now shows a clear error; optional queue opens when serials are added.

## 3.8.234 / EXE 1.1.215
- **Boost target stickiness:** EXE remembers your selected player (localStorage + in-session sticky). Status polls and roster refreshes no longer snap back to host; backend re-syncs if it drifts. Backpack list refreshes when you change target.
- **Backpack guard:** relevel/scan blocked when Boost target is All players — pick one player first.

## 3.8.233 / EXE 1.1.214
- **Safety UX:** red banner under tabs + Home “Before you boost” — always check Boost target, use tools in good humour (not griefing), and spread huge loot across bank/mules.
- **Rewards / inventory:** Serials tab warning — Open rewards on send defaults to Yes (opens one package at a time); console players avoid bulk-open in MP; ~250–300+ carried items can look invisible in MP until fixed solo.
- **Backpack tab:** scan boost target's backpack (@U serials), tick rows, bulk relevel to a chosen level (on demand only).

## 3.8.232 / EXE 1.1.213
- **Mobility (all):** infinite jump + force fly party-wide modes persist, auto-add joiners, and skip join scrub that was resetting remotes. Force fly (all) applies to every live player; remotes use CheatManager fly (not host kinematic drive that locked them in place).
- **Serial deliver:** one pasted `@U` line stays one item — rejoins lines broken mid-serial (e.g. backtick/newline) and never re-splits resolved serial arrays on punctuation inside Base85.

## 3.8.231 / EXE 1.1.212
- **Player bank spawn:** world duplicate no longer runs `find_all` template scans (froze/crashed with large held shapes). Uses find_object + session spawn, offline preset, then activate-only fallback.
- **Open rewards on send:** default back to **yes** (still togglable to no).

## 3.8.230 / EXE 1.1.211
- **Join + large held shape crash:** party grow with 180+ frozen pins stacked refresh + guest push repin on the same tick (pyunrealsdk AV). Held shapes now defer quiet-end repin to one throttled guest push, skip layout mirror entries, and scale join heartbeat batches by pin count.

## 3.8.226 / EXE 1.1.207
- **Home “What’s new”:** moved out of “Start here” (that section hides when Online) into its own always-visible Home card.

## 3.8.225 / EXE 1.1.206
- **Menu/travel crash:** main menu cleared pins but kept 1000+ layout entries — rejoin + party grow then tried join serial respawn (duplicate spawns → pyunrealsdk AV). Abandon now clears layout/join state; serial mirror requires live pins.
- **Orphan shape loot after menu:** frozen world items left in the level are marked unmanaged so the mod does not re-catch/re-pin stale wrappers on reload.

## 3.8.224 / EXE 1.1.205
- **Join + held 3D shape:** single find_all rebind (not per-pin — was AV/crash with stacked shapes). Batched host repin + phased guest net after 2s quiet.
- **Golden chest:** fast open path when many shape pins are frozen (skips world LootableObject scan hitch).
- **Stacked shapes:** round-robin hold repin cursor + longer pickup-scan cache when 400+ held pins.

## 3.8.223 / EXE 1.1.204
- **Join + held 3D shape:** rebind pins by serial before join quiet, skip addr-map wipe, host-only batch repin during quiet (no guest net push that woke physics). Longer quiet window for large houses.
- **Force fly (party):** remotes use CheatManager fly + speed stamp instead of host kinematic gravity-off (was freezing them in place).

## 3.8.222 / EXE 1.1.203
- **Keep prior shapes:** arming a new house/globe no longer clears frozen pins from the last spawn — old silhouettes stay put.
- **Join hold:** held shapes keep guest_ok during join quiet; faster heartbeat + host repin so half the house does not fall when someone joins.
- **Settle polish:** snap/slow/stagger pin on-slot with hold when Stay in air is on (3D); toned stagger wave; car cabin widened.
- **Infinite jump:** always refresh JumpMaxCount on party pawns; mid-air reset when double-jumped even if IsFalling is stale on remotes.
- **EXE Home:** short “What’s new” bullet box; button sweep animation pauses during window resize.

## 3.8.221 / EXE 1.1.202
- **Drip + stay in air:** no longer peels house/globe to the ground — pins on silhouette instead. Peel drip only when stay-in-air is off.
- **Drop judder:** faster motion tick while items are animating, higher per-frame budget, catch-up teleports if a frame is skipped.
- **Drip scatter:** extra velocity zero + physics off on animated drops; lower drip stagger.

## 3.8.220 / EXE 1.1.201
- **Drop-from-above on 3D shapes:** rain/slow/fast/snap/etc. no longer forced to instant pin — items spawn at overhead start pose and animate into slots. Settle **none** = direct on-slot (no feet spit animation).
- **Co-op guest sync crash:** stopped infinite retry on 5 stubborn ghost pins (was resetting fail counter forever → AV). Unsyncable / non-gear pins abandoned after max failures.
- **Spawn All:** registers pool per land slot for gear-only filtering.

## 3.8.219 / EXE 1.1.200
- **Co-op shaped Spawn All crash (globe / bulk):** guest net heartbeat no longer runs mid-dump (was touching stale pickup wrappers while 600+ slots filled → pyunrealsdk AV). Guest sync waits for settle; teleport/physics paths hardened; serial memory reads deferred until dump finishes.

## 3.8.218 / EXE 1.1.199
- **Remote moon-jump (joiners):** stopped periodic remote mobility writes (were re-applying jump/gravity every 0.18s). Remote scrub now only clears SQBT poison (fly/low-grav/JumpMaxCount 999 / bad jump flags) — never rewrites full JumpGoal presets. Join scrub runs for 18s after party grow; stale guest infinite-jump indices pruned on enable/join.
- **Mobility reset:** reset defaults is host-only again (`local_only=True`).

## 3.8.217 / EXE 1.1.198
- **Lobby crash (AV):** join quiet no longer hammers 24 teleports every 100ms (`_tick_join_hold_freeze` disabled) or bulk-repins 180+ pickups in one frame. Removed `GetStaticMesh` probes on pickup components (freed UObject AV during party join/GC).
- **Safer pin resolve:** repin uses cached addr + `_live()` before `K2_TeleportTo`; decor purge checks component name without deep mesh walks.

## 3.8.216 / EXE 1.1.197
- **String lights on car:** `SM_Pile_StringLights` / placeable pile pickups are no longer caught or pinned into shapes (were stealing a slot and colliding on join). Existing decor pins are purged on join quiet.
- **Join held shape:** late join is heartbeat-only again — no mass repin / followup blast that was knocking frozen pins down after 3.8.213.
- **Remote moon-jump:** scrub resets JumpMaxCount/JumpZ/gravity/fly without re-applying mod JumpGoalDef presets; `StopJumping` on party join.

## 3.8.215 / EXE 1.1.196
- **Join shape collapse (regression):** disabled join mirror respawn when a held shape already has pins — duplicate pool spawns at the same XYZ were knocking the host house down (log showed `Join serial batch N/190`). Late join now uses **net push only** on existing frozen pins.
- **Car roof lights:** removed decorative rim-ring wheel slots (read as a random round light cluster on the roof).
- **Remote moon-jump:** remote scrub no longer re-applies full JumpGoalDef mobility presets (`bClearGravityScaleAtApex=False` caused float-up). Restores vanilla jump flags + gravity/fly only when poison is detected.

## 3.8.214 / EXE 1.1.195
- **Join shape collapse:** late-join mirror no longer swaps or hides host pins (was deleting the shape batch-by-batch). Spawns guest-only replicas at slot XYZ while host pins stay frozen.
- **Mobility on join:** remote scrub no longer calls full reset-all (was logging "2 player pawn(s)" and touching the host). Party-index filtering uses `live_party_contexts` + `_is_local_party_index`, not `get_pc()` identity.
- **Car shape:** catch no longer XY-snaps dump items onto roof slots; overflow tucks under the chassis instead of scattering to roof Z.

## 3.8.213 / EXE 1.1.194
- **Remote moon-jump (joiners):** remotes now get a full vanilla JumpGoal/gravity/jump-count rewrite (Oak JumpGoalDef path, not just JumpZVelocity). Scrub runs on party join from loot_shapes + mobility tick every ~0.18s while 2+ players. Infinite-jump hook no longer touches pawns outside the enabled index set.

## 3.8.212 / EXE 1.1.193
- **Late join shape (fix regression):** layout tracking is **per pin** again (was deduping by @U serial — 385 house slots collapsed to ~102 and the join path hid host pins). Join now mirrors **every** held slot via native itempool respawn at stored XYZ, swaps the pin only after the new pickup is frozen + net-pushed, then retires the stale actor.
- **Remote moon-jump:** Mobility **Apply** is **host/local pawn only** — remotes no longer inherit gravity/jump writes from auto-apply or slider presets. Party join resets remote movement to vanilla defaults.

## 3.8.211 / EXE 1.1.192
- **Late join + held shape:** shiny pool names now map to curated @U serials per pin slot; guest join runs net pin push **and** chunked serial respawn at stored XYZ (replaces stale pinned actors so joiners see a fresh replicated layout). Log should show `N serial(s)` and `serial respawn(s) queued`, not `0 serial(s)`.
- **Remote moon-jump:** party join scrub restores gravity / JumpZ / jump count on remotes; walk restore runs more often and logs at lower thresholds.

## 3.8.210 / EXE 1.1.191
- **Co-op join + held shape:** join quiet no longer wipes the pickup addr map on scan failure; host re-freezes pins immediately and every 0.1s during quiet; guest heartbeat 48 pins/0.08s; full guest repin starts right when quiet ends (was +1.5s late).
- **Remote moon-jump:** periodic walk/gravity/jump restore on party remotes when fly / infinite jump / fall-through are off (ghost low-grav from old host ticks or Apply-all presets).

## 3.8.209 / EXE 1.1.190
- **Co-op remote jump float:** party join + periodic scrub restores walk/gravity on remote pawns when fly was never toggled but low-grav / fly-mode fields lingered (was “moon jump” with fly OFF).
- **House shape:** guns lie flat on walls/floor/roof strokes; only corner posts stand vertical (no slope-pitch porcupine).

## 3.8.208 / EXE 1.1.189
- **Co-op held shapes (join):** join quiet no longer kills guest net for 8s — held house/car pins keep a throttled guest heartbeat so the silhouette does not drop to the floor when someone joins. Preserves pinned addr map; ongoing maintenance after sync completes.

## 3.8.207 / EXE 1.1.188
- **Loot tab:** restored **Drop backpack → shape** (full land/shape fields) under Shiny drops — spill inventory to ground, catch into silhouette. Home quick drop still spills at feet; shape options live here and on F.A.A.F.O.

## 3.8.206 / EXE 1.1.187
- **Drop All Shinies:** live NCS pool first (~100ms); dump/@U only on miss (was ~280ms per shiny).
- **Spawn All Filtered (shiny rows):** skip per-row `prepare_shiny` / phosphene during mass bulk — save cosmetics decide look.
- **Force fly:** scrub orphan gravity-off latches on all party pawns when the EXE toggle is OFF; stale target expiry restores walk before dropping dict entries. UObject guards on fly tick (fixes `0xffffffffffffffff` AV).
- **Co-op shaped spawn:** slightly longer cache-first pin gap during bulk hold so guests still see pins without extra find_all hitch.

## 3.8.205 / EXE 1.1.186
- **Spawn list:** removed Slippy (`ItemPool_FishGrenade_Slippy`) — native pool crashes; fish ordnance still spawns via Fishing Uniquedrop / Fishcollector rows.
- **FAAFO Fall through map:** capsule + actor collision off, `bAlwaysCheckFloor` off, MOVE_Falling with gravity. HUD tick no longer skips re-apply after Force fly off; force-fly disable re-applies fall-through when active.

## 3.8.204 / EXE 1.1.185
- **Spawn All Filtered (dump list):** named L5 rows were taking ~2.3s each because bulk mode skipped live pools and ran the full dump/@U chain on every gun. Mass batches now pool-first (~100ms), NCS twin fallback only, no inline/@U per row.
- **Spawn All Filtered:** removed periodic feet `find_all` during flat mass runs — scan cost was growing with pile size (main hitch after ~100 items). Shaped runs still pin via loot_shapes.

## 3.8.203 / EXE 1.1.184
- **Spawn All Filtered:** progress bar stays up through finish/settle (was dropping when the queue drained). Mass batches no longer run a full feet `find_all` on every named L5 row — sampled verify only, same as other pools.
- **Spawn All Filtered:** removed duplicate shape motion tick on the spawn queue (HUD tick already runs it). Deferred tick keeps going until summary is written.
- **EXE:** spawn-only progress polls at 1.2s instead of hammering the bridge every 800ms.

## 3.8.194 / EXE 1.1.177
- **Force fly:** Cruise ~750 (walk/jog). WASD follows look **yaw only** — Jump/Crouch for up/down (look pitch no longer rockets you up). Floor liftoff is a small cooldown nudge, not every tick.
- **Car shape:** thicker cabin midsection + wheels tucked under the body (was a slim batmobile with wide stance).
- **Spawn All + shape (dump):** cache-first pin; fresh ``find_all`` ~1s during bulk hold instead of ~0.22s (that made the car take minutes).

## 3.8.193 / EXE 1.1.176
- **Force fly Cruise:** slowed to a real tour pace (1,600; was 4,000). Fast / Blur / Nuke ladder retuned. Tick no longer floors dt to 1/45 (that made every preset feel too fast).
- **EXE layout:** fly speed / Apply fly speed stay on **Mobility → Movement toggles**. Player → Local cheats is on/off only. Home → Most used Force fly toggle unchanged.
- **Loot shapes (join):** 3D silhouettes (globe / pyramid_3d / …) are the join-reapply path — not flat 2D rings/hearts.

## 3.8.192 / EXE 1.1.175
- **Echo4 / py:** register console ``py`` so Discord injects like Max All / shinies work when unrealsdk did not ship ``py``.
- **Inject agent:** serves the newest ULM party snapshot from Steam ``sdk_mods\\echo4bot_*\\data`` (was stuck on a stale ``D:\\echo4bot_windows`` copy → wrong host/guest linking).

## 3.8.191 / EXE 1.1.174
- **Force fly:** continuous WASD again — brief input gaps no longer kill motion; safe-fly lifts off the floor before sweeping so it doesn't hop once and stop. Force fly toggle added to Home → Most used.
- **Echo4 `/startup`:** no longer blocked by “Join Echo4mods's game first” when a saved shiftname doesn't match — panel opens so you can **Set Shiftname**. Solo mismatch copy tells you to fix the name instead of join.

## 3.8.190 / EXE 1.1.173
- **GZO / open rewards:** with Open rewards ON, each mail package opens before the next one sends (100-item package opens, then delivery continues).
- **Boost target:** EXE player roster / global target no longer snaps back on status polls; pending selection is held longer.

## 3.8.189 / EXE 1.1.172
- **World text crash guard:** MODS ARE FREE / barrel-logo spawns pause or slow down while co-op held-shape guest sync is active (was AV with 180+ electisafe clones + net push). Pin maintenance validates live actors and is throttled. Bridge rejects spawn when guest sync is still pending.

## 3.8.188 / EXE 1.1.171
- **GZO / deliver:** status polling now continues through the reward-open queue (not just mail send). Bridge `warning` text shows in the app action line. Deliver confirm distinguishes selected rows vs unique serials.
- **Open pending rewards (everyone):** confirm dialog; ETA uses the same paced gap as auto-open; progress polling after queue.
- **Force fly toggles:** Force fly vs Force fly (all) sync independently by scope; co-op tooltip on “all”. Map fog toggle is sticky and syncs from session status.
- **Co-op shapes:** guest sync retries longer on held silhouettes (higher fail budget + follow-up waves instead of stopping at 8 misses). Join refreshes tracked layout serials before re-push.

## 3.8.187 / EXE 1.1.170
- **Force fly speed (fix):** movement always reads the committed speed global; Apply logs `ACTIVE fly speed: N` with mod version. Noclip uses full-offset per tick; safe fly + velocity assist. **Restart BL4 after updating** so Python reloads.

## 3.8.186 / EXE 1.1.169
- **Force fly presets:** wider spread above Cruise — Fast 14k, Blur 55k, Nuke 160k (Cruise stays 4k). Noclip gets a small high-speed boost; safe fly still sweeps floors.

## 3.8.185 / EXE 1.1.168
- **Force fly speed:** toggling fly ON/OFF no longer resets speed to the Fast preset. Apply fly speed is what commits preset/custom values. Movement distance per tick now scales linearly with speed (Cruise → Nuke → custom 50k+ should feel clearly different).

## 3.8.184 / EXE 1.1.167
- **GZO / open rewards:** warns when auto-opening 250+ items (lag risk in multiplayer; solo lobby often best). Confirm dialog in the app, hint on Open rewards field, and bridge status note.

## 3.8.183 / EXE 1.1.166
- **GZO / open rewards:** auto-open is back to **one mail package per tick** (~0.5–0.8s apart) — opening ~100 items in one burst still hitches BL4. Going to menu **pauses** the queue (no more opens); it **resumes automatically** when you load back in.

## 3.8.182 / EXE 1.1.165
- **GZO / open rewards:** auto-open now runs in background waves of ~100 items (4 mail packages), pauses briefly, then continues — no 48-package cap and no manual Reward Center batching for big sends.

## 3.8.169 / EXE 1.1.152
- **Co-op shapes (the actual guest bug):** ULM dump `at_location` is host-only. Guests saw a floor square / items falling all over the ground because 3.8.168 froze slots locally and logged `no restamp`. Lobby pins now freeze first, then stamp `ReplicatedMovement` + one ForceNetUpdate per item (~2/s during dump). Settle queues a chunked freeze-first guest push (no physics-on).
- **Join:** still 8s quiet on old wrappers. Guest sync ticks also run from the dump HUD path so the delayed push actually happens.

## 3.8.168 / EXE 1.1.151
- **Shapes (GitHub pin path):** freeze physics first, then teleport. Host pins stay local (`replicate=False`). Dump still lands at the slot (ULM `at_location`) so guests already in the lobby see the silhouette, not a pile at the host's feet.
- **Join:** 8s quiet only drops stale wrappers and skips guest restamps. It no longer blocks host pin teleports or delete the held house after a few missed lookups. After quiet, `find_all` rebinds pins and restamps drift.
- **Removed** the GroundLootHelpers physics-on-then-teleport move, hold-refresh restamps, and settle/join ForceNetUpdate storms (those flattened houses and spat the car in front of the host).

## 3.8.167 / EXE 1.1.150
- **Join crash (console/PC):** party grow no longer teleports cached pickups. 8s join quiet — no `K2_TeleportTo` / physics / guest sync until the world finishes streaming. Pins drop stored UObject wrappers. Guest sync starts after quiet from a fresh `find_all`.
- Fixes AV `reading address 0x…` in pyunrealsdk when a console character joins a held silhouette.

## 3.8.166 / EXE 1.1.149
- **Co-op shapes:** pin moves match GroundLootHelpers — physics on, then `K2_TeleportTo`. Co-op never skips the teleport (on-slot skip was host-only; guests kept the feet pile). Freeze after the move, not before.
- **GZO / Lootlemon / Serials:** already-selected `@U` rows are delivered as-is. Mid-payload `@Ug` no longer splits one code into two. 235 selected → 235 queued.
- **Player tab:** Takedown mayhem lives here (removed from World). Dropped the duplicate Dev loot spawn button. Serials shiny section is mail-only; world shiny drop stays under Loot.

## 3.8.165 / EXE 1.1.148
- **GZO / Lootlemon deliver:** list respects `limit` up to 5000 and reports `total` filtered count. **Select all filtered** now loads the full filtered catalog (not just visible rows) and caches serials so Deliver sends every ticked row — fixes “238 selected → 104 queued”.
- **Deliver feedback:** bridge returns `selected_count` / `skipped` when rows lack usable serials or were off-screen.
- **Co-op shapes:** stamp `ReplicatedMovement` on on-slot spawns; `K2_SetActorLocation` teleport fallback; hold refresh re-pushes ~28 pins every 5.5s for lobby guests; delayed `bAlwaysRelevant` relax while silhouette is held.

## 3.8.164 / EXE 1.1.147
- **Crash fix:** guest sync no longer teleports stale/dead pickup wrappers (AV `0xffffffffffffffff`). Removed `dir(inv)` serial scan + gift `_hide_pickup` (both pyunrealsdk crash paths).
- **Co-op (dump showed `0 serial(s) tracked`):** safer serial read via UObject attrs first; guest sync uses `bAlwaysRelevant` net push @ 48/tick after settle.
- **World text:** seed wait 6s→20s, logo tick also runs from shape poll (not only mobility), canonical actor detect for letter clones.

## 3.8.163 / EXE 1.1.146
- **Lag (root cause from dump):** `after_dump_spawn(1)` per shiny + `find_all` every spawn = stutter every second. Now **one catch per tick batch** + fresh scan throttled to 0.45s on hold shapes.
- **Co-op lag:** removed mid-dump pin-tail ForceNetUpdate bursts entirely.
- **Gifts:** excluded from shape fill pools; gift/currency pickups are hidden instead of stealing wall slots.
- **Co-op visibility:** serial+XYZ tracked per pin; chunked guest sync at settle/join + **5 follow-up waves** (joiners stream late). SetNetDormancy Never on net push. Shaped spawns skip teleport when already on-slot (keeps replicated spawn pose).
- **Place Fully:** records serials for co-op instead of "tracking off".

## 3.8.162 / EXE 1.1.145
- **Co-op regression fix:** 3.8.161 was ForceNetUpdating every pin in lobby — host lag + guests saw feet-spit. Host pins locally again; guests get batched repin at settle + join.
- **Mid-dump:** no pin maintenance tick, no deferred find_all on hold shapes (after_dump_spawn only).
- **Settle/join:** `_repin_all_for_guests` pushes up to 72 pins immediately, then chunked sync for the rest.
- **Removed** present/floor-decor slot routing (was adding work per spawn).
- **Teleport replicate:** dropped `bAlwaysRelevant`/1000Hz spam from `_teleport_pickup`.

## 3.8.161 / EXE 1.1.144
- **Co-op shapes:** pins net-replicate immediately (guests see slot Z, not feet drops); removed duplicate tail sync + double catch scan hitch.
- **Catch Z fix:** near-slot pickups always use planned height — stops wall/roof guns landing on the floor.
- **Presents / gifts:** currency and gift pickups route to the **floor ring** inside house/boat/car shapes.
- **Shape height:** silhouettes sit lower (less head-height floating).
- **Loot visibility:** pinned items no longer hog `bAlwaysRelevant` — other ground loot stays visible after a shape.
- **Spawn All (solo shaped):** 2/tick @ 0.06s gap when no co-op lobby; co-op stays 1/tick for stability.
- **Black market:** clearer wait message + second spawn pass on failure.

## 3.8.160 / EXE 1.1.143
- **Co-op shapes:** each host pin now throttled net-pushes to lobby guests (not only at settle); late join / party grow starts chunked guest sync instead of a no-op or one-frame storm.
- **Co-op lag:** guest sync spreads over ticks with lighter pickup refresh (no full find_all every 0.22s).
- **Safe fly:** smaller swept steps at Blur/Nuke speeds, blocks digging into floor when grounded, remembers last safe height and recovers if you tunnel under terrain (without noclip).

## 3.8.159 / EXE 1.1.142
- **Force fly floor fix:** movement sweeps collision again when noclip / fall-through are off — no more clipping under the map at Blur/Nuke speeds (small steps, max 2/tick).

## 3.8.158 / EXE 1.1.141
- **Fly speed made idiot-proof:** Preset vs Custom mode — custom number actually applies (was always losing to preset). Big **Apply fly speed** button + live status line shows active speed. Step-by-step hint on Mobility tab.

## 3.8.157 / EXE 1.1.140
- **Serial paste fix:** Base85 codes no longer split at `@Uw` inside the payload — only `@Ug` starts a new serial (fixes truncated gear sets).
- **Send serials UX:** Send serials is first on the Serials tab; **Deliver pasted serials** skips the queue; queue is optional.
- **Boost UX:** MAX ALL tooltip lists cash/eridium/SDU/vault/level/spec; Jump to puts Serials first; Force fly removed from Home/FAAFO (Mobility tab only).
- **My Library:** Deliver selected first; Save/Duplicate/Delete under Library tools fold.
- **Movement presets:** lower Fast/Moon/Wall walk and fly Cruise/Fast/Blur/Nuke defaults.

## 3.8.156 / EXE 1.1.139
- **Host shaping fix:** pin/freeze runs immediately after each shiny spawn (not once per 2-item tick batch) so roof/wall slots stop falling to the floor.
- Hold catch: double-pass scan + `_lock_unseen_dump` fallback; pin failure queues float job instead of skipping the gun.

## 3.8.155 / EXE 1.1.138
- **Co-op shapes restored (3.8.149 path):** each catch batch tail-syncs new pins to guests; settle + late join run a full guest repin (was only queuing chunked sync and never restamping).
- **Host shaping:** pin path unchanged (`replicate=False` on host freeze); catch scan budget back to 1.1.94 `max(budget, 12)`; spawn-at-slot dump path kept.

## 3.8.154 / EXE 1.1.137
- **Co-op shape:** lobby guests get incremental pin net push as each dump batch lands (tail sync, max 3/tick — not a 200-pin storm).
- Late join / settle: guest sync refreshes the pickup map, restarts on party grow, and runs faster when the dump is idle (18 pins / 0.28s).

## 3.8.153 / EXE 1.1.136
- **Co-op fix:** removed 3.8.152 repin storms (4× full shape + double ForceNetUpdate) that lagged and dropped Shift.
- Late join / settle: guest sync is now **10 pins per 0.45s tick** in the background — no host freeze.

## 3.8.152 / EXE 1.1.135
- **Shaped shiny dump:** spawn on the silhouette slot first (inline / catalog / NCS at `at_location`) — no feet spit then teleport.
- **Co-op late join:** staggered guest repin waves (full XYZ + double net push) after settle and when someone joins a held shape.

## 3.8.151 / EXE 1.1.134
- **Shaping restored:** pin path back to always teleport+freeze (1.1.94); hold dumps run pin maintenance again so guns stop raining.
- Hold catch: fallback `_lock_unseen_dump` when a batch misses; stragglers retry pin before float queue.
- Co-op guest repin still only at settle/late join (shaping first).

## 3.8.150 / EXE 1.1.133
- **Shaping fix:** hold silhouettes always snap to the planned slot (feet-spit was frozen on the ground when XY was near a wall/roof slot).
- **Stragglers:** feet-spit on hold shapes pins immediately instead of queuing float jobs.
- **Co-op:** no mid-dump net teleports (they lagged and fought pins); guest repin still runs at settle + late join.

## 3.8.149 / EXE 1.1.132
- Co-op shape sync fixed: guests get full K2_TeleportTo net push as each batch pins (not stamp-only / 24-cap burst).
- Late joiner after house: repin runs even while landing is still armed; full silhouette Z, not a flat floor pile.
- Settle: repin all held slots for lobby guests instead of a partial burst.

## 3.8.148 / EXE 1.1.131
- Shaped dump/spawn: back to pre-3.8.143 smooth catch (one find_all per batch, freeze-on-slot, no mid-dump pin tick).
- Co-op unchanged: no ForceNetUpdate mid-dump, settle burst + join guard still sync guests without the old crash.

## 3.8.147 / EXE 1.1.130
- Shaped dump pins back to the working slot path (guns land on the silhouette, not the ground).
- Most used / featured buttons: same width and height in a row.

## 3.8.146
- House dump: guns pin to their slots again (no roof stack / ground drop from late freeze).

## 3.8.145
- Smoother shaped dump: freeze guns already on slots (no extra teleport); lighter world scan.

## 3.8.144
- Shaped Drop All / Spawn All: pin as items spawn (house forms again); world scan ~1/s instead of every spawn.

## 3.8.143
- Shaped Drop All / Spawn All: much less mid-dump hitch; players in lobby still see the held shape when it finishes (no crash).
- House silhouette proportions restored.
- Favourites on GZO / Lootlemon (app + in-game).
- Loot shapes visible to guests already in the lobby.

## 3.8.142
- House proportions restored; catch slot logic back to normal.

## 3.8.141
- Shape catch fix (no wrong-slot snap).

## 3.8.140
- Dump catch / pin timing tweaks.

## 3.8.139
- Dump stick + quieter offline status text.

## 3.8.138
- Faster shape arm (no double silhouette bake on Drop All).

## 3.8.137
- Spawn-all land fields always visible; dump hitch after ~10 reduced.

## 3.8.136 / EXE 1.1.129
- Guests see held shapes after late join; lighter mid-dump net work.

## 3.8.135 / EXE 1.1.128
- Favourites on GZO and Lootlemon catalogs.

## 3.8.134 / EXE 1.1.128
- Loot shapes visible to guests already in lobby.

## 3.8.133 / EXE 1.1.127 - Missing/fail spawn hint → Spawn All Filtered / type pools
- Loot Pool Spawner (EXE + in-game): if a named row is missing or fails, try Spawn all filtered or the type pool (AR / SG / SM / PS / SR 05 Legendary; Pearl type pools).
- Same tip on silent-empty / named legendary miss messages.

## 3.8.132 / EXE 1.1.126 - Named L5 dump miss → NCS twin (no phosphene apply)
- Loot-tab named legendaries (Lumberjack, Goalkeeper, Laser Disker, …) still try dump ItemPoolList / inline / @U first.
- If dump misses: spawn the registered ``*_shiny`` NCS twin **without** prepare_shiny / phosphene apply. Save cosmetics decide look; gun still lands on the ground.
- Never mail. Selected/bulk trust ``ncs_named_twin`` delivery. Explicit dump inv handles for common named L5s.

## 3.8.113 / EXE 1.1.110 - Base comp only, never deliver shiny pool
- Root cause of "only shiny": preload/fallback rolled live ``*_shiny`` NCS pools; when dump failed the shiny pickup stayed on the ground.
- Named legendary rows now spawn ``inv'ROOT.comp_05_legendary_*'`` from NCS (same comp as shiny row) with **no customizationlist** — inline merge, then @U, then ItemPoolList. **Never** roll ``*_shiny`` pools for non-shiny UI rows.
- Handles come from ``ncs_shiny_pools.json`` inv_handle + ``ncs_live_catalog.json`` (correct Early Excess / Laser Disker casing).

## 3.8.112 / EXE 1.1.109 - Legendary rows stop rolling shiny pools
- Root cause: ItemPoolList tried live ``*_shiny`` ItemPoolDefs first for non-shiny rows — guns landed with phosphene / wrong names (Early Excess → Overconsumption is the shiny-pool path).
- Non-shiny rows now: inline inv dump → inv handle → filtered ItemPoolList (shiny pools stripped). Named ``itempool_*_shiny`` rolls only when ``_spawn_shiny=1``.
- Spawn Selected / Spawn All now stamp ``_spawn_shiny=0/1`` from category (Pistol tab vs Shiny tab) so intent is never guessed from pool name alone.
- Pool catalog merges any missing NCS native pools; shiny rows still auto-get a base legendary twin under the weapon tab.

## 3.8.111 / EXE 1.1.108 - Named legendaries spawn again (no phosphene)
- 3.8.110 reverted to live-first bulk on synthetic base pool names — NCS silent-OK with zero loot, so Laser Disker / Bugbear stopped dropping.
- Named legendary rows (not Shiny tab) now: verified ItemPoolList / inline inv dump → warm inv via registered ``*_shiny`` preload (destroy preload pickup) → retry dump. Same path for Spawn Selected and Spawn All Filtered.
- Never trust bare ``pool_spawn`` on named uniques without verified ground loot. Mixed pools unchanged.

## 3.8.110 / EXE 1.1.107 - Spawn Selected = Spawn All Filtered again
- Reverted the shiny-preload + dump-companion detour (3.8.108–109) that lagged Selected and still dropped phosphene on legendary rows.
- Spawn Selected now uses the same live-first bulk drain + delivery trust as Spawn All Filtered (3.8.93 path). No separate VERIFY_DEFER gate for singles.
- Named uniques rejoin the bulk NCS path, then dump/@U like Spawn All — not a special shiny-twin preload.
- While Squ1ggs is enabled, extra interfering SDK mods (live editor, loot presentation, Azzy booster, etc.) auto-pause; **ULM stays on**.

## 3.8.109 / EXE 1.1.106 - Named legendary = base inv, verified dump
- 3.8.108 still dropped phosphene on legendary rows: companion dump used ``skip_verify=True`` and address tracking that never saw new pickups, so logs showed ``*_shiny`` fallback.
- NCS: normal legendary is the same ``inv'ROOT.comp_05_legendary_*`` without shiny ``customizationlist``; base rows live in ItemPoolList (Ordonte / dedicated drops). Shiny pool only preloads the comp.
- Named legendary rows (Selected + Spawn All Filtered, not Shiny tab) now: preload live ``*_shiny`` → verified ItemPoolList / inline inv dump → destroy shiny pickup by loot key. Shiny rows and mixed pools unchanged.

## 3.8.108 / EXE 1.1.105 - Named Selected = legendary, not phosphene
- 3.8.107 finally dropped named guns, but used the live ``*_shiny`` row so they came out with the phosphene / shiny prefix.
- Legendary is the same unique without that prefix. Selected now loads the unique via the live row, dumps the base inv-comp (no phosphene), and removes the shiny pickup. Shiny list rows still spawn phosphene. Mixed pools unchanged.

## 3.8.107 / EXE 1.1.104 - Named uniques use the live *_shiny Nexus row
- Dump on 3.8.106: Laser Disker / Bubbles / Bugbear / Buzzymuzz / Chuck honestly failed — ``SpawnLootFromData`` and ground @U never dropped a gun.
- Those uniques have no base Nexus pool. The registered ``*_shiny`` twin is the dedicated unique row (same path Drop All Shinies already uses). Spawn Selected now rolls that live pool at your feet. Look follows this save's cosmetics (normal legendary if shinies are locked).
- Mixed pools (Enhancements / rare / Shields 05) unchanged.

## 3.8.106 / EXE 1.1.103 - Named uniques skip silent NCS; original Drop
- Dump on 3.8.105: Laser Disker / Buzzymuzz / Chuck VERIFY_DEFER in ~30ms as ``pool_spawn``, then silent-empty after ~4s. Dump never ran.
- Spawn Selected sets bulk-drain, and live Nexus still accepted the synthetic named-pool id (``or name``). That RPC returns OK with no loot; the extra lag was the verify wait.
- Named uniques now skip unregistered Nexus entirely, drop via original ``SpawnLootFromData`` (Rotator then Quat), and fail immediately if nothing lands. Mixed pools (Enhancements / rare / Shields 05) stay on live Nexus.

## 3.8.105 / EXE 1.1.102 - Named uniques dump-only; Toggles tab
- Dump on 3.8.104: mixed pools (Shields 05, Enhancements 05, AR 03 Rare) dropped; named guns logged ``pool_spawn``/loot true from leftover mixed loot and live Nexus on synthetic names.
- Named unique rows (catalog ``*_comp_05_legendary_*``) now spawn only via inv-comp ``SpawnLootFromData`` (the original Item Spawner path). Live Nexus is skipped. Selected no longer treats leftover mixed-pool pickups as success.
- New **Toggles** tab next to Support shows sticky boosts on/off (fly, jump, noclip, shoot/zoom, fog).

## 3.8.104 / EXE 1.1.101 - Named Selected uses original dump/inline, not silent NCS
- Dump on 3.8.103: Laser Disker hit live store ``s1`` and still silent-empty; only mixed ``AR 05 Legendary`` dropped. Later named rows logged ``pool_spawn``/loot true with nothing on the ground.
- Named uniques (Laser Disker, Bloody Lumberjack, …) are not live Nexus pools — only mixed ``*_05_legendary`` and ``*_shiny`` rows are. Calling ``SpawnInventoryFromItemPool`` on the synthetic name always returns OK with no loot.
- Selected named uniques now use the original Item Spawner / Nexus Discovery path: inline inv-comp + ``SpawnLootFromData`` with a Rotator transform. Unregistered names no longer fall through to silent NCS. Mixed 05 pools stay on live NCS.

## 3.8.103 / EXE 1.1.100 - Selected starts on the discovered live Nexus store
- Dump on 3.8.102: only the broad ``AR 05 Legendary`` mixed pool produced world loot. Direct named pools were accepted but resolved on no layer and were falsely recorded as returned.
- Root cause: named Selected used the legacy multi-store iterator, which starts at the Nexus CDO and stops on the first non-exception RPC. The CDO resolves mixed pools but silently misses direct named pools stored in live config layers.
- Selected now starts on the discovered live/default Nexus store and tags that store in the verify job. Deferred retries probe remaining live layers before the CDO. Spawn All and pearl/Midnight routing remain unchanged.

## 3.8.102 / EXE 1.1.99 - Restore original Nexus FTransform ABI
- Dump 20:49-20:51 on 3.8.101 falsely reported non-shiny singulars as ``pool_spawn``/loot observed while no world loot appeared.
- Root cause: the Nexus spawn call had drifted from GitHub 3.8.0 and wrote a ``Rotator`` into ``FTransform.Rotation``. The original working call writes an ``FQuat``; the wrong struct type can return without an exception but spawn nothing.
- Restored the original Quat conversion for direct Nexus and dump transforms while retaining multi-store Nexus discovery, generic 05 pools, Spawn All shaping, pearls, and the Midnight/CrowdSourced exceptions.

## 3.8.101 / EXE 1.1.98 - Selected named = dump at feet (GitHub path)
- Dump 20:34 on 3.8.100: Class Mods 05 Selected OK; named Laser Disker / Screenwriter VERIFY_DEFER → silent_empty (live named RPC silent; dump never trusted).
- Named Selected uses GitHub-style dump/@U at feet first and trusts dump delivery. Generic pools (PS/AR/Class Mods 05) keep live + brief verify. Spawn All Filtered unchanged.

## 3.8.100 / EXE 1.1.97 - Selected = Spawn All live path + deferred verify
- Dump 20:23 on 3.8.99: every Selected ERROR'd ``live silent-empty; dump/@U missed`` while Spawn All live bulk RETURNED the same pools.
- 3.8.99 dump-first + skip bulk NCS for Selected was wrong. Selected again uses the Spawn All live NCS path for one row, waits for feet loot (deferred verify), then dump-escalates only if still empty.
- Spawn All Filtered unchanged.

## 3.8.99 / EXE 1.1.96 - Selected dump-first + feet verify (no false OK)
- Dump 20:00-20:01: Selected Laser Disker / Bonnie and Clyde / Rowan's Charge logged ``pool_spawn`` RETURNED + loot_observed with nothing on the ground (global pickup-delta false OK after Spawn All leftovers; live singles silent).
- Spawn Selected named rows are dump/@U-first (not Spawn All live mass-trust). OK only when new loot appears near feet (1400uu), else silent_empty after dump rescue.
- Clear stuck verify-only leftovers before queue so Selected is not blocked as already queued. Spawn All Filtered unchanged.

## 3.8.98 / EXE 1.1.95 - Spawn this one item = Spawn All path; roof before walls; fly-off cleanup
- Dump: Selected Bugbear/Laser-Cutter/King's Gambit/etc failed ``silent_empty`` after ``pool_spawn`` while Spawn All Filtered returned the same live pools.
- **Spawn this one item** (was Spawn selected pool) now uses the Spawn All Filtered live trust path for one row, yanks the drop in front, and no longer deferred-verify / dump-rescues into silent_empty.
- House fill order is wireframe → roof panels → walls → floor so incomplete batches keep a roof.
- Force Fly OFF double-Walks, clears noclip if left on, and restores the same movement fields Force Fly ON wrote.

## 3.8.97 / EXE 1.1.94 - Frame-first shapes; deterministic Black Market setup
- Spawn All Filtered shaped runs now default to **Continue until shape complete**; older clients that omit the field also pad shaped bulk runs.
- House layout reserves its foundation, corners, eaves, ridge, roof edges, gables, and door first, then fills floor/wall/roof panels.
- Black Market Spawn no longer queues two complete 23-step setup sequences. One sequence already contains retries; duplicate clicks and respawns are blocked while it is pending.
- Verified the live mod, app resource copy, and packed resource were all 3.8.96 before this change; the reported behavior was a current-code race, not an old bundled build.

## 3.8.96 / EXE 1.1.93 - Deferred Selected verify; no duplicate rescue
- Dump 18:34–18:37: 12/12 Selected attempts were silent-empty; immediate live check then dump rescue also produced duplicate items because the live pickup is asynchronous.
- Spawn Selected now snapshots before the live call, waits on later game ticks, accepts one observed pickup, and only dump/@U-escalates after about one second.
- Removed Selected native re-rolls during verification; the fallback dump is also verified asynchronously. Spawn All Filtered remains unchanged.

## 3.8.95 / EXE 1.1.92 - Selected legendaries: stop lying OK, dump-rescue
- Dump 18:23: Selected Whiskey Foxtrot / Star Helix logged ``pool_spawn`` + ``loot_observed`` with nothing on the ground (mass-trust silent RPC).
- Spawn Selected no longer mass-trusts live pools. If no new pickup after live spawn, dump inv / proven / @U rescue. Spawn All Filtered unchanged.

## 3.8.94 / EXE 1.1.91 - Spawn Selected normalizes like Spawn All
- Preflight: Selected queued raw UI rows (often ``*_comp_05_*`` / wrong casing) so live-first was skipped; Spawn All always ran ``_normalize_spawn_all_entry`` first.
- Spawn Selected now normalizes before queue — same live pool ids as Spawn All Filtered.

## 3.8.93 / EXE 1.1.90 - Spawn Selected = Spawn All Filtered path
- Dump: Selected Bubbles/Bugbear/etc failed ``Spawn Selected dump/@U missed`` while Spawn All Filtered spawned the same rows via live ``pool_spawn`` (~618 OK).
- Spawn Selected now uses the same live-first drain path + delivery trust as Spawn All Filtered. No separate dump-only Selected gate.

## 3.8.92 / EXE 1.1.89 - Restore 3.8.24 Spawn Selected ISP path
- Dump: Bubbles / First Impression ``pool_spawn`` silent_empty — Selected was forced through feet-verify/find_all again (exactly what 3.8.24 removed) then fell through to empty live pools.
- Spawn Selected named L5s back to ISP: dump/@U first, **no sync find_all**, never silent ``pool_spawn`` fallthrough. Spawn All Filtered unchanged.

## 3.8.91 / EXE 1.1.88 - Spawn Selected dump-first again; Midnight base
- Dump: Selected Midnight base rewrote to ``CrowdSourced_shiny`` only; Lumberjack/Bugbear etc. logged ``pool_spawn`` OK with ``loot_observed`` via Spawn All mass-trust while nothing landed.
- Spawn Selected named L5s use dump-first lean + feet verify again (not Spawn All live trust).
- Midnight non-shiny dumps ``VLA_SR.comp_05_legendary_CrowdSourced``; shiny still uses live ``*_shiny``.

## 3.8.90 / EXE 1.1.87 - Midnight Defiance singular live NCS again
- Dump: singular Midnight failed with ``serial/ItemPoolList/merge/dump all missed`` after 3.8.89 put it in dump-only; live ``CrowdSourced_shiny`` never ran because proven raised before fallbacks.
- Fix: Midnight is live-first (same-family shiny pool), not dump-only like Roil. Dump-only path now catches proven raises so @U / native shiny can still run.

## 3.8.89 / EXE 1.1.86 - Steady Spawn All; filter toggles; car scale; Midnight Defiance
- Spawn All: one continuous queue (no 80-item wave bursts), default 1/tick @ 0.10s.
- Loot list: coloured **No cash** / **No AI guns** toggles (default on) hide currency + oversized NPC/mech guns from list + Spawn all.
- Car silhouette: larger human-scale radius/spacing, default drop height 8 (feel inside it).
- Midnight Defiance singular: dump ``VLA_SR.comp_05_legendary_CrowdSourced`` / shiny pool / @U (no synthetic ``*_comp_*`` pool).

## 3.8.88 / EXE 1.1.85 - Roil / Rainmaker dump-inv (correct parts)
- Dump **656 ok / 3 fail**: Slippy (quarantine), Rainmaker base, Roil Shiny.
- Cause: only ``mal_sg *_shiny`` NCS exists; Spawn All stripped ``_shiny`` into ghost pools and skipped ``BOR_SM`` / ``bor_sr`` invs (wrong manufacturer/part locks).
- Fix: dump-only catalogs dump correct inv first, never synthesize stripped mal_sg bases; @U fallback. Live-first for everything else unchanged.

## 3.8.87 / EXE 1.1.84 - Spawn All Filtered queues the FULL list again
- Dump showed **305/306** because All Spawn All was wrongly shrunk to named L5 + shiny + pearl (~450 type/ammo/manufacturer pools never queued).
- Restored GitHub 3.8.0 behavior: Spawn All Filtered spawns every row in the current filter (≈760 on All), live-first — no curated cut.

## 3.8.86 / EXE 1.1.83 - Slippy crash-safe dump (keep live-first Spawn All)
- Latest 3.8.85 dump: **305 ok / 1 fail** — only Slippy (FishGrenade GameThread overflow + weak dump/@U).
- Crash-safe path now uses proven dump routes (Pascal inv, StealthPredator preferred list, @U) with ``allow_native=False`` — never calls FishGrenade; live-first path for the other 305 unchanged.

## 3.8.85 / EXE 1.1.82 - Restore GitHub 3.8.0 live-first Spawn All
- **Root cause:** recent dump/@U-first experiments made every named L5 take ~1–2s and produce no ground loot.
- **Restored release path:** Spawn All uses live NCS ``SpawnInventoryFromItemPool`` first (same as sqbt-v1.1.1 / mod 3.8.0).
- Shiny rows still prepare cosmetics; wrong-family Burrow blocked; curated All still legen+shiny+pearl (no ammo filler).

## 3.8.84 / EXE 1.1.81 - Spawn summary shows THIS session fails only
- Dump for 3.8.83 was **290 ok / 5 fail** — the summary's "Recent failures" still listed the old 291 silent_empty run, which looked like "many fails".
- Summary now lists **This session failures** only; Spawn All resets the session marker each run.
- Named legen: @U serial then stronger inv-handle dump (inline fallback) before live NCS.

## 3.8.83 / EXE 1.1.80 - Spawn All shaped: stop rejecting real loot
- Dump showed **4 ok / 291 fail** after 3.8.82: shaped Spawn All rejected every live/shiny success as "no new ground loot" while dump retries lagged.
- **Trust shaped delivery again** (feet can't verify when catch yanks into slots).
- **Named legen:** inv-handle dump companion first (same path that works after shinies); no bulk live short-circuit before dump.
- **Shinies:** live *_shiny pool first (Drop All Shinies path).

## 3.8.82 / EXE 1.1.79 - Spawn All dump-first again; Drop Shinies on Loot
- **Spawn All shaped:** stopped counting silent live `pool_spawn` as success (that left mostly shinies/pearls on the silhouette while named L5s "OK'd" with no loot). Named legen + shiny go dump/@U first.
- **Faster bulk:** skip ItemPoolList miss scans during Spawn All; shaped drain allows 2/tick.
- **Loot tab:** Drop all shinies (world loot) lives here too (still on Home).
- **Curated All:** named L5 + shiny + pearl only (no bare type-parent filler).

## 3.8.81 / EXE 1.1.78 - Spawn All crash fix; serials stop rewriting backpack
- **Spawn all filtered:** fixed NameError (`shaping` undefined) that aborted the queue so nothing spawned.
- **Serial codes / deliver:** no longer forces backpack to serial_count+100 every send. Only expands when MaxSize is readable and too small for used+new items; skips rewrite when size can't be read.

## 3.8.80 / EXE 1.1.77 - Spawn All keeps loot; live pool first; shiny+legen both
- **No cleanup wipe:** Spawn All no longer deletes loot every 16 drops (that left only a couple on the ground and caused stop/start lag).
- **Faster:** live itempool first for named L5 / shiny during bulk — skip dump ItemPoolList misses.
- **List:** legendaries and shinies both keep (same catalog no longer dedupes away the shiny twin). All Spawn All = named legen + shiny + pearl (not ammo/common filler).

## 3.8.79 / EXE 1.1.76 - Legendaries vs Shiny split; faster Spawn All
- **Loot list:** ``*_shiny`` pools are only under **Shiny**; each gets a normal legendary twin on its weapon tab so the two no longer fight.
- **Spawn all filtered:** tries the live item pool before dump/ItemPoolList (those misses were the lag + scary fail spam). Use **Shiny** when you want shinies.

## 3.8.78 / EXE 1.1.75 - Spawn All normals; plain BM hints

- **Spawn all filtered:** All / weapon tabs no longer rewrite named L5s onto *_shiny pools (that made the pile look shiny-only and hitchier). Use the Shiny category when you want shinies.

- **Hints:** Black market / golden chest / launch text no longer expose internal API names.



## 3.8.77 / EXE 1.1.74 - Most used restored; Loot spawn under list


- **Most used:** fly, jump, sprint flags, fog, freecam, golden chest, BM spawn, shiny drop/mail, drop backpack, legendary loot back on Home (gold frame).


- **Loot:** Spawn selected + Stop sit full-width under the pool list; Spawn all filtered (land/shape) is collapsed so the spawn button stays visible.





## 3.8.76 / EXE 1.1.73 - Most used gold frame; Economy gap fix



- **Home:** Essentials renamed back to **Most used** with a gold border/glow.



- **Economy / Party:** featured packing - one-tap buttons in a dense row; field cards below so tall Give currency no longer leaves empty holes.







## 3.8.75 / EXE 1.1.72 - Home jump links + restore golden chest



- **Audit:** golden chest spawn/open/close had left Home without a new home  restored under World ? Golden chest.



- **Home:** Jump to shortcuts into Progress / Mobility / Serials / Loot / World / FAAFO / Player / Mob & IO.



## 3.8.74 / EXE 1.1.71 - Leaner Home, tool search, no false Offline flash




- **Home:** Essentials only (MAX ALL / cosmetics / rewards / god / kill). Fly, shinies, challenges, chests, fog, serial paste moved to their real tabs. Takedown mayhem â World.




- **Find a tool:** search above the tabs jumps to the matching tab/section and highlights the control.




- **Connection:** brief Offline / manifest blips no longer wipe the tools UI or show "Start Borderlands 4" while you were already Online.









## 3.8.73 / EXE 1.1.70 - Remove dead Loot feed; tighten FAAFO layout




- **Loot:** removed the no-op Loot feed section (EXE + in-game card).




- **F.A.A.F.O.:** split into compact featured rows + Launch/locks + Drop backpack so tall land fields no longer leave empty button holes.




- **UI:** land/shape action cards span full width; slightly tighter section gaps without packing controls together.









## 3.8.72 / EXE 1.1.69 - Shiny house fill, spawn lag, Selected = All, no Patch labels




- **Dump:** runtime log no longer re-appends the whole ring on every flush (status polls were rewriting history and hitching I/O). Status polls stay out of the flight log.




- **Drop All Shinies:** "Continue until shape complete" defaults to **yes** (house â 420). End settle pulls up to 96 leftovers so silhouettes aren't a few slots short.




- **Spawn/shape lag:** one catch pass per shiny tick batch; shaped drains use the same find_all throttle as Spawn All; 1 dump/tick default.




- **Spawn Selected:** same drain trust as Spawn All Filtered (no sync feet-verify on dump-first lean).




- **Lists:** Verce / Loiter / Hydrowerks / BloodIron / Kaos / PRISM â no more "Patch - â¦" in display names.









## 3.8.71 / EXE 1.1.68 - Accurate smoke + crash flight log (dev-only UI)




- **Dev smoke:** fixed false greens (shinies checked real APIs; loot `item_pools.json` count; host check no longer soft-passes on error; zoom flags are INFO not pass; deferred no longer re-registers hooks; travel requires `travel_to_preset`; mobility/fly suite added).




- **Flight log:** `Squ1ggsBoostingTools/logs/sqbt_runtime.log` â ring buffer in memory, flush on enable/disable / bridge actions / exceptions (â¥8s dirty flush). No per-tick disk I/O.




- **EXE:** Show/Flush/Open log buttons only on the hidden Dev smoke panel (`Ctrl+Alt+Shift+F9`).









## 3.8.70 / EXE 1.1.67 - Force fly WASD (not look-only)




- **Force fly** uses dump `ControlInputVector` / `Action_Move` (W/S along look, A/D strafe). Any-key-goes-forward is gone.









## 3.8.69 / EXE 1.1.66 - Force fly speed (dump MaxFlySpeed=600)




- **Force fly** no longer drives CMC velocity. Live dumps cap `MaxFlySpeed` / `MaxWalkSpeed` at **600**, `MaxAcceleration` at **2048**, and `MaxSimulationIterations` at **8** â that was the slow crawl plus hitch.




- Look + WASD now **kinematic position steps** (Cruise/Fast/Blur/Nuke actually differ). Hold WASD; jump up / crouch down; release to hover.




- Per-tick `SetMovementMode` / `ClientCheatFly` / `find_all` / floor teleports removed. Mode + `MaxFlyAltitude` stamp every 0.4s / 8s.









## 3.8.43 / EXE 1.1.40 - Spawn dead ahead (no left/behind jitter)




- Spawn location is straight in front of look direction (`ControlRotation`), not body yaw + left/right pile jitter.




- Pile / singular offsets: side = 0. No post-spawn yank on singular test.









## 3.8.42 / EXE 1.1.39 - Stop yank teleports eating singular drops




- Singular test no longer repositions loot after spawn (yank/settle/catch). That was making guns appear then vanish (under world / out of feet verify).




- Removed the `loot_verified` yank that had no before-snapshot (it teleported the whole nearby pile).




- Yank for normal Spawn selected still only runs with a before_keys snapshot, and only for native pool spit â not dump/@U.









## 3.8.41 / EXE 1.1.38 - Fix silent-empty legendaries / pearls on singular path




- Singular / Spawn Selected no longer uses the Spawn All silent-native shortcut (that was marking Gomie, P6 pearls, heavies, etc. as spawned with no ground loot).




- Synthetic `itempool_*_comp_05_*` UI ids rewrite to live `itempool_*_05_legendary_*` (and P6 `*_06_pearl_*`).




- Patch-inline pearls (Gomie, Abyss, Temper, PRISM/Burrow, â¦): dump/@U before live pool.




- Verify escalates dump/serial sooner for dump-first / pearl catalogs instead of only retrying the empty pool.









## 3.8.40 / EXE 1.1.37 - Test Singular Filtered




- **Test Singular Filtered** (Loot Pool / EXE / `sqbt_spawn_singular_test`): runs every matching named row one-by-one on the same Spawn Selected path (feet verify, front pile). Not Spawn All mass mode. Defaults to named only (catalog / `>`). Stop spawn list cancels. World loot only â never mail.









## 3.8.39 / EXE 1.1.36 - Conflux back on pearl path + front drops




- **Conflux**: was wrongly forced to [L5] so it skipped the live `*_pearl` pool path that works for Handcannon/Soul Survivor. Restored as Pearl (NCS rarity 06_pearlescent).




- Pearl roster aligned with known list: Conflux, PRISM (Burrow), Pachonk added; Soul Survivor remains the only pearl with a shiny/Phosphene pool entry.




- **Behind you**: never fall back to `upandforward`; after a singular spawn, yank new pickups to a pile in front of the pawn.









## 3.8.38 / EXE 1.1.35 - Logs, front drops, keep the list




- **Console log**: Spawn selected / Spawn All finish no longer dumps the all-time "Successes by category" wall (Ammo 273, AR 2503, â¦). One short done line only. Full summary stays in `spawn_test_summary.txt`; `sqbt_spawn_dump` still prints it on demand.




- **Singular drops in front**: Stopped using the game's `upandforward` spit (it was throwing loot behind after we already placed the transform). Ring offsets stay in the front hemisphere. Leftover shape slots from a prior Spawn All are cleared before a plain Spawn selected.




- **Names**: Stopped preferring the NCS dump label when it points at a different gun (Disc JockeyâBoomslang, BarrelâCooper Duper). Curated / np_names titles again.




- **List**: Dead-shiny filter no longer hides rows from the UI. Cosmetics still stay out. Ammo/currency and the rest remain.









## 3.8.37 / EXE 1.1.34 - Reverted the 3.8.36 spawn gating




- 3.8.36 treated the converted NCS dump as proof of what exists. It is not: `itempool_jak_ar_05_legendary_gomie` and `itempool_bor_sm_05_legendary_jailbroken` both roll live from the game's pool service but appear nowhere in the dump files. Absence from the dump means "not exported", not "not in the game".




- Removed the row filtering and the "pool is dead â skip to dump" routing that were built on that assumption. Spawn behaviour is back to 3.8.35.




- **Kept** the display names, which the dump does prove: `inv_name_part` is the game's own label table.









## 3.8.36 / EXE 1.1.33 - Rebuilt against the live NCS




- New `ncs_live_catalog.json`, generated from the converted base + patch Nexus config store. It is now the source of truth for which pools exist, what each one drops, and the real item names.




- **Names fixed.** Display names come from the game's `inv_name_part` labels instead of pool ids, so rows read *PRISM* (not Burrow), *ARC-TAN* (not Arctic), *Cooper Duper* (not Barrel), *Plasma Coil*, *Bloody Lumberjack*, *Whiskey Foxtrot*. Only pools that drop exactly one item take that item's name, so shared pools like `itempool_ar_05_legendary` stay generic.




- `ItemPool_BlackMarket_Comp_BOR_HW_DiscJockey` actually contains **Boomslang**; the row is labelled by contents, not by the pool's name.




- **Phantom rows removed.** 67 catalog rows and 28 synthesized dump rows pointed at pools *and* comps that no longer exist in the shipped game (Draupner, Ichor, Hard Dark, Heimdahl, the `*_06_pearl` type pools, Dahlmech/Mandolin/Tuba enemy pools). They could never drop anything and now stay out of the list.




- Rows still reachable by a curated @U serial (Abyss, Solar Temper, Reminisce, Fearstalker, Gomie, Juliet, Herald â¦) are kept.




- A pool the NCS no longer defines goes straight to the item's comp/serial instead of calling into a dead pool and reporting a silent success.









## 3.8.27 / EXE 1.1.24 - Loot feed + Solar Temper dump




- **Loot feed** renamed (not "toasts"); Appear* now passes WorldContext + widget def (was bare `fn()` â errors).




- **Solar Temper** / pearl-world: patch dump â merge â @U serial before NCS pool.









## 3.8.26 / EXE 1.1.23 - Catalog hotfix (syntax)




- Fixed broken `_TITLE_ALIASES` dict in `legendary_dump_manifest.py` that crashed pool catalog loads (false "Connect in-game first" in dropdown).




- EXE: clearer catalog timeout message when already connected.









## 3.8.25 / EXE 1.1.22 - Conflux L5 + Solar Temper dump spawn




- **Conflux** reclassified from Pearl â **[L5] Legendary** (ULM dump: `comp_05_legendary_conflux`, not pearlescent).




- **Solar Temper** (and other ItemPoolList inline defs): patch inv dump first â NCS pool absent from ULM dump.




- Pearl tab no longer lists Conflux; Sniper legendary row shows as **Conflux**.









## 3.8.24 / EXE 1.1.21 - Singular named legendaries (no freeze)




- Spawn Selected named L5s use an ISP-style lean path: base pool â dump inv (2 handles) â @U â **no sync find_all**.




- Removed forced singular feet-verify that froze the game twice and reported no spawn.




- Raid3 / dump-first rows no longer expand every casing variant before drop.









## 3.8.20 / EXE 1.1.17 - Mayhem Rank bypasses first clear




- Unlock writes **Mayhem Rank** (`HighestUnlockedMayhemLevel`): **1+** = Mayhem mode without a normal clear, **5+** = Hardcore.




- Floor unlock at rank 1 so a zeroed save still gets Mayhem mode; default 10 unlocks both.




- Note/labels updated so this is not confused with session HUD mayhem.









## 3.8.19 / EXE 1.1.16 - Takedown mayhem UI simplified




- EXE: one **Unlock takedown mayhem** action (level field, default 10) â removed Session HUD, quick 10/99, and status buttons.




- ULM Player tab: removed Session Mayhem slider; one **Takedown mayhem unlock cap** field + reload hint.









## 3.8.18 / EXE 1.1.15 - Mayhem unlock cap (takedown)




- **Mayhem (takedown unlock cap)** in EXE under Boost â Black market area: set `HighestUnlockedMayhemLevel`, quick 10/99, session HUD mayhem, status.




- Writes PlayerState + progression mirrors, then nudges UI collectors / nearby takedown IO (best-effort live refresh).




- Note in EXE: **reload save** or re-open kiosk if Hardcore tiers stay locked after write.









## 3.8.12 / EXE 1.1.9 - Crow/Midnight dump serial-first (no NCS required)




- **You do not need fresh NCS** for Crow-Sourced Pearl or Midnight Defiance â bundled FModel merge + Lootlemon @U serials spawn without live pools.




- Removed dead **L5 Crow-Sourced** pool row (itempool8 deleted it); one **Crow-Sourced Pearl** row with `*_pearl` pool.




- **Spawn Selected** tries curated @U first, then merge inline; accepts dump-first RPC when feet scan misses.




- **Spawn All** no longer auto-OKs silent native/dump that dropped non-shiny legendaries (Midnight fix).




- Re-enabled verify-queue @U / merge / dump inv retries (were stubbed out).









## 3.8.11 / EXE 1.1.8 - Crow / Midnight singular dump-first




- **L5 Crow-Sourced:** `catalog_key` + `dump_named_legendary` on the pool row; infer catalog from `itempool_*_05_legendary_*` when missing. Deleted base pool skips silent NCS and dump-firsts like Spawn All.




- **Crow-Sourced Pearl (Spawn Selected):** uses verified pearl dump path (merge inline before @U serial).




- **Midnight Defiance Shiny:** fixed shiny @U lookup (`crowdsourced` â `midnight_defiance` serial). Singular shiny no longer misses the curated serial before native pool.









## 3.8.10 / EXE 1.1.7 - Fly collision + FAAFO fall-through + Crow merge-first




- **Force fly:** fixed 60Hz steps (presets stay consistent) and **sweep collision** so you stop on floors/walls unless Noclip / Fall through map is on.




- **Noclip:** auto-enables local Force fly so collision-off does not freefall.




- **FAAFO â Fall through map:** collision off + gravity on + Force fly off (separate from Mobility Noclip).




- **Crow-Sourced Pearl:** dump merge payload first; richer `live_inv:missing` / merge failure detail. Dump/FModel data is present â failures usually mean the inv def is not loaded live (itempool8 deleted the base pool).









## 3.8.9 / EXE 1.1.6 - Kinematic force fly




- **Force fly** no longer uses ClientCheatFly / MaxFlySpeed (Oak ignored those â every preset felt the same).




- Moves you with look + WASD **position steps** so Cruise / Fast / Blur / Nuke actually differ. Hold WASD; release to hover.




- Preset wins over the stale number field the EXE always sends with the toggle.









## 3.8.8 / EXE 1.1.5 - Hyper-V-safe bridge + overlapping mods




- **Hyper-V / WinNAT:** skip Windows excluded TCP ranges, then bind an OS-assigned localhost port if needed. The EXE reads `bridge_port.json` so it always finds the live port.




- **Other copies of bundled tools** (movement, spawners, item spawner, live clones): paused while Squ1ggs is on; no "disable it yourself" warning unless pause actually failed.




- **sdk_mods cleanup:** duplicate `.sdkmod` zips (folder already wins), `.sdkmod.patched` leftovers, and invalid `_pre_*` backup folders moved to `.archived_sdkmods/` so oak2 stops loading them.









## 3.8.7 / EXE 1.1.4 - Bridge ports (Hyper-V 10013)




- **EXE not connecting:** Windows Hyper-V reserved TCP **49718â49817**, so the old 49775â49784 bind failed (`PermissionError 10013`). Bridge now prefers **50675** (then 55175, then the old range). Fully restart the game after this EXE auto-copies.









## 3.8.6 / EXE 1.1.3 - Fly presets + Crow / Midnight dump gates




- **Force fly:** Cruise / Fast / Blur / Nuke presets + look/WASD directed velocity (old 12Ã crawl cap removed). Raise the number only to override a preset; Update fly speed while airborne.




- **Crow-Sourced Pearl:** dump inv first, then curated @U before silent NCS pools; no fuzzy non-shiny companion dumps.




- **Midnight Defiance / Crowd-Sourced:** catalog_key on the shiny row; companion gate covers crow* and crowd* so a "crow" filter cannot twin the wrong gun.




- After install: fully restart Borderlands 4 and relaunch the **1.1.3** EXE so it auto-copies **3.8.6**. Download from GitHub only if the update card says a newer app is there.









## 3.8.5 / EXE 1.1.2 - Fly cap, Crow-Sourced Pearl solo, Midnight Defiance rename




- **Force fly:** speed cap raised to **500000** (UI + clamp).




- **Crow-Sourced Pearl:** Spawn Selected uses dump inv + ground @U before trusting the silent pearl pool; Spawn All no longer false-OKs native-first for pearl rows.




- **Midnight Defiance:** VLA CrowdSourced shiny is labeled Midnight Defiance (not Crow-Sourced). Auto non-shiny companion is skipped for that gun so a crow filter does not drop two of them.




- After install: fully restart Borderlands 4 and confirm the log shows **3.8.5**.














## 3.8.4 / EXE 1.1.2 - Cold Shoulder solo + shiny dump companion + fly speed




- **Spawn Selected Cold Shoulder:** shiny @U/merge no longer reports success with zero ground loot (that skipped the live *_shiny pool Spawn All used). Feet loot is required before OK.




- **Spawn All Filtered shinies:** also dumps the matching non-shiny legendary from catalog inv (the dump twin is hidden when a shiny pool row exists).




- **Force fly:** stronger velocity assist + faster tick so the speed slider is not a crawl/judder.




- After install: fully restart Borderlands 4 and confirm the log shows **3.8.4**. EXE **1.1.2** is fine (mod-only).














## 3.8.3 / EXE 1.1.2 - Solo shiny dump + smooth force fly




- **Cold Shoulder (and peer shinies):** solo dump spawn no longer skips the shiny dump / catalog fallback that Spawn All used. Curated @U first, then dump, then catalog inv; Spawn All also prefers shiny dump before bulk native.




- **Force fly:** tick only restamps speeds (Gbx-aware writes + soft velocity assist). No per-tick SetMovementMode / ClientCheatFly â that was the stop-start judder. Fly speed slider should stick; use Update fly speed after changing the number.




- After install: fully restart Borderlands 4 and confirm the log shows **3.8.3**. EXE **1.1.2** is fine (mod-only fix).









## 3.8.2 / EXE 1.1.2 - Rarity layout + client force fly




- **Rarity drop weights:** fields stay left; Legendary / Pearlescent / Reset stack on the right when the window is snapped half-width (no more 2Ã2 card scramble).




- **Force fly:** mobility path for clients (no ClientCheatFly). Tick re-applies mode/gravity on remotes; **Force fly (all)** added; Boost target **All** expands correctly.




- After install: fully restart Borderlands 4 and confirm the log shows **3.8.2**. Use EXE **1.1.2**.









## 3.8.1 / EXE 1.1.1 - Host polish




- **Vault card tokens:** absolute set can lower below current (slot write; no fake "already at" success).




- **Loot feed toasts:** standalone Squ1ggs path (no external editor module required).




- After install: fully restart Borderlands 4 and confirm the log shows **3.8.1**.




- **Rarity weights:** Pearlescent-only (and presets) return live % so EXE fields update; pearl aliases accepted.




- **Cold Shoulder shiny:** prefer curated shiny serial before legendary dump handles (was landing non-shiny).




- **Challenges:** **World** category added.




- **Target player:** top Boost dropdown syncs Send to / Target player fields (including All).









## 3.8.0 / EXE 1.1.1 - Shapes, backpack drop, sprint fire/ADS




- **Smoother Spawn All / land-in-shape (dump):** less finish hitch (settle + log rewrite spread across ticks), leftover catch kept alive during shaped runs, pin miss grace so silhouette guns stick better.




- **Drop backpack â shape:** SpillOut still dumps world loot at your feet, then catch/settle pulls into the selected silhouette (same ground path as Drop All â never mail).




- **Shoot while sprinting** and **Zoom / ADS while sprinting** on Player + Mobility (session toggles).




- After install: fully restart Borderlands 4 and confirm the log shows **3.8.0**. Use EXE **1.1.1** with this mod.









## 3.7.29 - Broader Dev smoke suites for support




- Ctrl+Alt+Shift+F9 Dev panel: vault, world, currency, challenges, rewards, deferred, travel, peers.




- Run all dedupes SDK/host; tips call out FGbxDefPtr / host / mission-role failures.









## 3.7.28 - Dev smoke panel (Ctrl+Alt+Shift+F9)




- EXE: unlock **Dev smoke tests** card with per-suite buttons (SDK, host, bridge, catalog, mission cast, mission live, zoom).




- Results print in the panel and unrealsdk.log as `[DevSmoke]`. Surfaces FGbxDefPtr / host failures that block mission Start.









## 3.7.27 - Mission start cast fix + remove Lab tab




- Mission Start/Track: try string / FGbxDefPtr / UFunction WrappedStruct first (bare FGameDataHandle could not cast on this SDK).




- Desktop + in-mod panel: remove Lab tab (worldsettings errors). Zoom while downed lives on Player + Mobility.









## 3.7.26 - Claptrap silhouette + fill until the shape is complete




- **Claptrap** is a real CL4P-TP now: box head, one eye, antenna, trapezoid body, unicycle, two arms. Extra guns fill those parts together instead of stacking a tapered crate.




- Dump has **626** itempools (115 cosmetics hidden). Spawn All Filtered already queues the rest (~530). Empty Other / crashy Slippy still cannot invent loot.




- **Continue until shape complete** (Loot Pool + desktop land fields): after the selected rows, keep world-dumping SMG / shotgun / rifle from that selection (or dump `itempool_sm/sg/ar_05_legendary` and `*_all` type pools) until the silhouette has enough guns. Claptrap wants ~240. Off by default. Still ground loot, no mail.









## 3.7.25 - Shiny dump is one gun, not a live ItemPoolList




- Spawn All Filtered shinies were dump-first through **every loaded ItemPoolList** (and empty `*_shiny` pointers). After a bulk dump the world is full of lists, so that call counted as success with **no loot** â fewer items, no phosphene in the pile.




- Drop All Shinies then rolled those fat lists (extra guns) and the end-of-dump catch could still yank leftovers from the previous Spawn All that were sitting in the same volume.




- Shiny / exact inv now **SpawnLootFromDef only** (one dump handle). ItemPoolList stays Gomie / Jail-Broken only. Catch takes 1â2 new actors per dump, not 12â80.




- If a shiny still looks like a normal legendary, cosmetics are not unlocked on this save. Still world loot, no mail.









## 3.7.24 - Non-pearl dump-first (shinies, Slippy, BloodIron)




- **Shinies:** Catalog `*_shiny` rows now dump the inv handle first. They used to go through empty NCS and never hit dump, so Spawn All logged "no new ground loot". If a shiny lands as a normal legendary, unlock the phosphene cosmetic on this save (UVHM / save editor) â still world loot, no mail.




- **Slippy:** Native `ItemPool_FishGrenade_Slippy` stays quarantined (GameThread stack overflow). Spawn uses dump `tor_grenade_gadget.comp_05_legendary_slippy` on the ground instead of the crashy pool.




- **Patch BloodIron:** `itempool_patch_inline_*` pools with an empty catalog now map to the dump inv (`vla_repair_kit.comp_05_legendary_BloodIron`).




- Named dump-only L5s dump inv after an NCS miss. Empty Other pools (side missions, NPC weapons) still fail â the dump has no item to invent.




- Spawn All / land-in-shape still skip find_all verify on dump. No mail.









## 3.7.23 - Pearl dump-first spawn, no pile-scan hitch




- Named pearls (Gomie, Abyss, Solar Temper, Jail-Broken, P6, *_pearl) now dump inv / ItemPoolList **first**. Empty NCS "success" was skipping dump and leaving holes in Spawn All.




- Spawn All / land-in-shape no longer find_all-verifies or scans nearby phosphene while hundreds of guns are already on the ground. That was the hitch when the catalog reached pearls.




- ItemPoolList is only used for Gomie / Jail-Broken (the dump rows that live there). Other pearls skip that world scan.




- Still world loot on the ground. No mail.









## 3.7.22 - Pyramid fill, claptrap size, ground height, pearl hitch, leftover shapes




- **Pyramid 3D:** After the outer wire, fill all four faces together. Spawn All was drawing the base/edges then packing only the player-facing side.




- **Claptrap:** No more 148-unit cap. Bulk dumps use a taller/wider body so ~500 items are not crammed into a tiny box.




- **Ground height:** On Loot Pool (Spawn All Filtered) and the desktop land fields, next to Drop height. This lifts the whole silhouette (`z_bias`). Drop height is still fall-from-above.




- **Pearl hitch:** Named pearls during Spawn All / land-in-shape use one live pool call then one dump inv, with no ItemPoolDef loop or find_all verify.




- **Forbidden pair:** Slightly narrower globes.




- **Psycho / Firehawk out of last shape:** Leftover guns from a previous dump are no longer adopted into the new logo. Firehawk is a multi-stroke bird (beak, eye, feathers, three-flame tail) and both logos sit further forward.









## 3.7.21 - Stop dump pin-restamp crash




- Same native crash as 3.7.19 (`EXCEPTION_ACCESS_VIOLATION reading 0xffffffffffffffff` in pyunrealsdk). Spawn All was doing fine, then died mid-wave (~320/530) because `tick_drop_motion` restamped stored pickup wrappers after every pool spawn. Python `try` cannot catch that native AV.




- **Fix:** Do not restamp pins while a land dump is armed â freeze once on catch. After dump, restamp only uses a live address-map wrapper, never the stored `inv`.




- **Fix:** Deferred leftover-catch waits until the dump has settled, so it does not `find_all` + pin on the same tick as each spawn.









## 3.7.20 - Stop bulk shape spray on every land shape




- **Root cause:** Dump already spawns each gun on a silhouette slot, then the catcher nearest-snapped it onto a neighbor (72u slack). At Spawn All density every item is within 72 of an occupied slot, so later guns got yanked onto earlier ones and physics sprayed the rest onto the floor. Same path hit every 2D and 3D shape.




- **Fix:** If a new pickup is already on the silhouette, freeze it there. Only teleport from the player / feet onto the next planned slot.




- **Fix:** Catch up to 12 unseen items per dump tick (was 1â3), so extras from a pool call cannot sit unfrozen while `_drop_next` falls behind `_spawn_cursor`.




- **Fix:** Pin restamp no longer drops a live row when the wrapper probe fails for one tick (that was releasing already-placed guns).




- **Fix:** 2D land pins stay held while the dump is armed, same as 3D.









## 3.7.19 - Fix 3D shape spray + crash on large bulk spawn




- **Root cause (spray):** `after_dump_spawn` used a stale pickup cache when items spawned faster than the 280 ms refresh window. For `forbidden_pair` and other 3D hold shapes, newly spawned items were invisible to the catcher, fell under gravity for up to 450 ms, and scattered.




- **Fix:** 3D hold shapes now always force a fresh scan in `after_dump_spawn`, the same as 2D shapes.




- **Fix:** `_tick_pins` restamp budget scales with the number of pinned items (capped at 64 per cycle) and runs every 3rd motion tick when >32 items are held (~0.66 s full coverage for 530 items vs ~130 s before).




- **Fix:** Deferred catch runs faster (150 ms / 6 items) for 3D hold shapes so stragglers that miss the initial catch are pinned within one more tick.




- **Crash fix:** `_tick_pins` now wraps the stale-wrapper check (`_uobject_addr`) and the teleport in try/except to avoid native access-violation when the engine GC's old pickup actors mid-frame.




- **Fix:** `forbidden_one` balls now interleave left/right (same fix as `forbidden_pair`) so both fill together instead of left-then-right.




- **Fix:** Both forbidden shapes lift their lowest points to at least 56 units above origin â items near the floor got swept by the engine before the catcher could pin them.









## 3.7.18 - Forbidden pair: both sides stay in shape




- Spawn slots now **interleave left/right** (was fill-left-then-right, so the second globe got dump-spit). Right globe is a **mirror** of the left. Guns orient from each globe's center so they do not spear through the cleavage.




- Removed `_lift_above_ground` from inside the offset function â it shifted z in local offset space before `_push_shape_in_front`, causing drop-start height to collapse and items to fall straight to the floor.









## 3.7.17 - Unique item piles + forbidden shape fix




- **Unique item piles** â new land shape: one pile per exact item (serial / balance / pool). Works on **Spawn all filtered** and **Drop backpack** (with land fields). **Type piles** still groups by weapon type (AR, SMG, shield, â¦).




- **Forbidden one / forbidden pair** â restored 3D silhouette at bulk scale: radial gun orientation (no roof-flatten), larger layout bases, capped shaft density, partial torso on the pair.









## 3.7.16 - BM refresh actually removes the shop at your feet




- Copies are named `OakVendingMachine_*` so the old "blackmarket in name" filter never found them. Refresh now destroys those copies, and **hides + teleports** the PersistentLevel weekly shop (Destroy does nothing on that actor).




- Clear purchase cooldown / Reroll: remove nearby shop, then **one** spawn queue (a second pass was immediately duplicating the new shop).









## 3.7.15 - BM reroll/clear both destroy + respawn




- **Clear purchase cooldown** and **Reroll BM stock** both delete the nearby shop actor (`K2_DestroyActor`) then queue a fresh spawn (same path). Removed separate Remove / Pin-on-map buttons.









## 3.7.14 - BM reroll, stock read, map pin (NCS-backed)




- **Reroll BM stock** â `ServerRerollBlackMarketParts` (matches ULM + NCS `InventoryShop_VendingMachine_BlackMarket` 8-slot pool).




- **Status / stock** â reads live `StoredVendorInventories[0].Serials` (@U list) from nearest loaded shop.




- **Pin BM on map** â `DiscoverTrackerObject` + tracker on world `IO_VendingMachine_BlackMarket` only (NCS `DiscoveryLocation_MenuIO_BlackMarketVendor`).




- **Remove nearby BM** â destroy spawned shop at your feet without respawn.









## 3.7.13 - BM one-click spawn + clear removes old shop




- **Fix:** Spawn queues **oak_dual twice** in one click (same as clicking Spawn twice manually).




- **Fix:** Clear purchase cooldown **destroys nearby black market machines** first, then respawns a fresh shop.









## 3.7.12 - Fix black market spawn NameError




- **Fix:** Spawn black market machine crashed immediately with `NameError: name 'spawned' is not defined` â the spawn call was accidentally dropped in 3.7.11, so the queue never ran.









## 3.7.11 - Black market: load packages + dump dual path




- **Fix:** 3.7.10 removed the package-load step, so nothing spawned when the PersistentLevel template was not in memory. Spawn again runs **load packages â oak_spawnai Ã2 â world Ã3 â wake Ã3** in one deferred queue (dump path). One click, wait ~15s for the queue to finish.









## 3.7.10 - Restore dump oak_dual black market spawn




- Reverted the experimental single-pass spawn. Black market uses the dump-proven queue again: **oak_spawnai Ã2 â PersistentLevel relocate Ã3 â wake Ã3**, and the bridge queues **oak_dual twice** per click (same as 3.6.165 / working portable build). Clear purchase cooldown still clears timer then runs that same respawn path.









## 3.7.9 - Clear BM cooldown always respawns




- **Fix:** Clear purchase cooldown / ULM **Black market ready** only woke a nearby shop and reported success without respawning. Reset now always writes timer ready **and** runs the same respawn queue as Spawn (wait a few seconds for the deferred place).









## 3.7.8 - Black market spawn works again (one shop)




- **Fix:** Spawn did nothing after 3.7.7 removed the package-load step. Black market loads packages, moves the live shop once, and only falls back to a single oak_spawnai shell if the world template is not ready yet.









## 3.7.7 - One black market shop, no cooldown crash




- Spawn places **one** shop (the live machine is moved to you). The old dual queue spawned two, then a third.




- Clear purchase cooldown wakes that shop and writes the timer. It does not poke every vending actor (that null-read crashed BL4) and does not drop extra machines.









## 3.7.6 - Black market clear timer actually unlocks the shop




- **Clear purchase cooldown** now refreshes the shop the same way a new spawn does (writing 0/1 on the timer field does not unlock an already-placed machine). Button text is unchanged.









## 3.7.5 - Black market / extended table NameError




- **Fix:** `Unknown action 'black_market'` with `NameError: name 'world_personal_vehicle' is not defined`. Building the EXE action table referenced a function that was never a real top-level name, so **the whole extended table failed to load** â spawn, travel, loot, Lab, the lot. Personal vehicles is its own function now, and the table binds by name so one missing symbol cannot wipe the rest.




- Spawn black market machine is also registered in core so it cannot vanish if extended load hiccups.









## 3.7.4 - Travel unknown-action + shorter shapes




- **Fix:** `Unknown action 'travel_station'` (and the same class of EXE errors). Loading extended actions at import time circular-imported `backend_actions` and silently dropped the whole action table. Travel / loot / Lab now load lazily; travel is also registered in core so it cannot vanish.




- Loot Shapes blurb is one line: pick a shape, Place Fully.




- Lab: cycle tracked mission, replay, end replay, play trait mission (dump leftovers).









## 3.7.3 - Pull Missions tab




- Removed the Missions tab. Live dumps have Activate / Track / Abandon RPCs but **no CompleteMission**. Start/track/abandon also did not stick. Same class as fog: progress is on the save, not a live stamp.




- Challenges â **Story challenge flags** still ticks Completemainstory / Completesidemissions **challenge tokens**. That is not finishing story in the mission log.









## 3.7.2 - Mission actions always registered




- **Fix:** `mission_start` / `mission_track` / `mission_abandon` / `mission_query` live in `backend_actions` now, not only `EXTENDED_ACTIONS`. EXE no longer shows Unknown action when extended import hiccups.




- Mission RPCs try more payload shapes and report host/listen + per-RPC detail when start fails.




- UI copy: no complete-mission button (dumps had no CompleteMission RPC).









## 3.7.1 - Missions tab




- **Missions** tab: search 518 NCS missions, **Start selected**, **Track selected**, **Abandon selected**, **Start nearby**, **Refresh tasks**. Skip the giver â does not complete story.




- EXE **Missions** tab matches BLImGui. Fully restart Borderlands 4 after updating Python.









## 3.7.0 / EXE 1.1.0 - Public snapshot




- Round-number ship of the 3.6.2xx work. GitHub last had EXE 1.0.75 / mod 3.6.185.




- **Loot shapes** land as world loot: car, Claptrap, house, boat, DNA, pyramid, globe/dome, plus 2D star / heart / circle / psycho / firehawk / smiley / vault. Dump-first when NCS is empty; still in the selected shape. No mail path.




- **Force fly** is the stamp-only tick (MaxFlySpeed / accel / zero brake). One fly-speed box + Force fly + Update fly speed. No WASD hop.




- Pasting one `@U` Base85 serial (backticks / extra `@` / quotes inside) delivers that one item. Split only at a new `@U`.




- Vehicle Movement logs use `[Vehicle Movement]`. EXE sticky toggles stay highlighted while on and start off on a new install. Offline status is "Launch Borderlands 4".




- After install: fully restart Borderlands 4 and confirm the log shows **3.7.0**.









## 3.6.234 / EXE 1.0.125 - Put force fly back




- The 3.6.233 velocity push made fly hop a tiny bit on each WASD tap. Force fly is the 3.6.232 tick again: stamp MaxFlySpeed / accel / zero brake only, no velocity injection, no MinAnalogWalkSpeed overwrite.




- One fly-speed box, serial paste, Vehicle Movement logs, and EXE sticky toggles stay.




- Today's dump log is 530/530 START/RETURNED with no FAIL. Shapes unchanged. Still world loot. No mail.









## 3.6.233 / EXE 1.0.124 - Faster fly, one speed box, whole serials




- Force fly speed actually goes faster: Oak was ignoring a raw MaxFlySpeed write, so the slider felt stuck. It now writes the Gbx speed fields and keeps live velocity at the number you set. Still no ClientCheatFly every tick.




- Mobility has one fly speed, plus Force fly toggle and Update fly speed. The extra fly box on on-foot tuning is gone.




- Pasting one `@U` serial with backticks / extra `@` / quotes inside Base85 delivers that one item, not four broken pieces. Split only at a new `@U`.




- Vehicle Movement logs no longer say `[BVM]` or dump hook paths on install. EXE toggles stay highlighted while they are on and start off on a new install.




- Shapes unchanged. Still world loot. No mail.









## 3.6.232 / EXE 1.0.123 - Force fly actually uses the speed slider




- Stop-start crawl was the tick thinking the pawn changed every frame (Python wrapper ids) and re-firing ClientCheatFly, plus walk speed capped at 6000. Tick now only restamps MaxFlySpeed / accel / zero brake at the slider value.




- Shapes unchanged. Still world loot. No mail.









## 3.6.231 / EXE 1.0.122 - 2D dump pins; guns follow the stroke




- 2D dump (psycho / firehawk / smiley / vault) pins onto the drawing. Catch-pause was skipping the scan so items fell in a pile at your feet.




- Guns lie along each stroke so long rifles cover the line instead of punching a hole in the bottom-left of a face.




- Firehawk path is unchanged; it was the orientation + dump pile that made it look like a hollow box.




- Removed BL logo. Force fly no longer re-calls ClientCheatFly every tick (that was the judder). Dump logs stay in the trace file instead of repeating OK lines in the console.




- Still world loot. No mail.









## 3.6.230 / EXE 1.0.121 - Drop 3D psycho mask; 2D face + vault V




- Removed the 3D psycho mask. Psycho is the 2D ground mask: outer face, eyes, mouth grill, small vault V above the eyes.




- Dump after a previous 3D spawn fills sequential 2D slots instead of piling on the old origin.




- Vault Hunter logo stays a circle with an inverted V whose peak almost touches the top of the ring.




- Still world loot. No mail.









## 3.6.229 / EXE 1.0.120 - Simple psycho mask; shorter offline hint




- **Psycho mask**: outer face, two eyes, one mouth. Every gun lies the same way along the face â no mixed horizontals/verticals, no vault, no back ring.




- Offline status text is just "Launch Borderlands 4".




- Still world loot. No mail.









## 3.6.228 / EXE 1.0.119 - Psycho mask is a face drawing, not stacked rings




- **Restored mask looked like floating discs**: multiple `_ring_3d` slices + a back-of-head ring + a V from the mouth to the crown, and guns laying flat on each ring. It is one YZ drawing now (same idea as the house): oval outline, small empty eye holes, vault V only above the eyes, small mouth grill. Guns follow those strokes. No second oval behind the head.




- Still world loot. No mail.









## 3.6.227 / EXE 1.0.118 - Psycho mask restored




- **Psycho mask experiments were a mess**: the 3D mask is back to yesterday's oval skull, eye sockets, vault chevron, and circular mouth grill. House / pyramid / Claptrap / car are unchanged.




- Still world loot. No mail.









## 3.6.226 / EXE 1.0.117 - Psycho mask has eyes and a mouth




- **Dump was a tiny oval with no face**: outline ate the items, the mask was too narrow, and eyes/mouth were specks. Eyes, circular grill, and vault V are reserved first (house-sized). The oval comes after, wider, with a real chin taper.




- Still world loot. No mail.









## 3.6.225 / EXE 1.0.116 - Psycho mask matches the BL4 face




- **Psycho dump was a wide jaw-bowl**: width beat height, the crown got almost no guns, and teeth filled the mouth. It is a tall oval now (from the reference sheet): vault Î from the crown to the eyes, two round eye holes, circular mouth grill with spokes. Chin tapers; slight depth (grill forward, brow back). No interior fill.




- House, pyramid, Claptrap, and car are unchanged. Still world loot. No mail.









## 3.6.224 / EXE 1.0.115 - Outline house/pyramid; psycho mask face




- **House had no door**: the doorway was on the far wall and leftover loot. It faces you now, with jambs standing and a lintel along the top.




- **Pyramid was all barrels up**: dump items stood on the rising edges so it never finished. Base square is horizontals first; slopes follow the edge; a few front stripes fill after the outline.




- **Psycho mask was a wall of lights**: every gun stood, so there was no vault V, no eyes, no grin. It is a hockey-mask outline now â pointed chin, round eyes, upside-down V above the eyes, wide mouth with a few teeth â guns along each stroke.




- Claptrap and car are unchanged. Still world loot. No mail.









## 3.6.223 / EXE 1.0.114 - Shiny house, boat, helix, Claptrap, mask




- **House had no floor**: shiny dumps stood wall guns like a curtain. It is a cottage wireframe now (floor rectangle, wall edges, roof lines). Only the four corner posts stand.




- **Boat looked like a blob**: it is a small side-profile hull (pointed bow, cabin, short mast), guns along the boat like the car.




- **Helix top went horizontal**: the roof-lie rule was flattening strand guns at the cap. Strands follow the twist; rungs stay rungs.




- **Claptrap was oversized / off**: smaller body, filled front face, shorter arms.




- **Psycho mask lost the face**: the giant vault V is gone. Pointed-chin skull, slash eyes, small upside-down V above the eyes, wide grin with teeth.




- Car is unchanged. Still world loot. No mail.









## 3.6.222 / EXE 1.0.113 - Car tires and no side spikes




- **Rifles stuck out the doors**: every third gun was yawed 90Â°. Body guns now lie along the chassis only.




- **No wheels**: the body fill covered the wells, and long guns took the tire slots. Wheel arches are cut out; shiny pistols and SMGs go on the rims.




- Still world loot. No mail.









## 3.6.221 / EXE 1.0.112 - Longer car; shiny dumps draw 3D walls




- **Car looked like a 206**: short hatch with a tall cabin. It is a longer sedan now, and the ~133 shinies fill one dense side profile instead of three thin copies.




- **House dump looked unfinished**: roof guns stood on the barrel (pillars) and walls were a thin outline. Roof guns lie down; walls are taller and filled on the front; standing guns stay on the walls so a shiny dump still has height. Spawn All Filtered (hundreds) is unchanged. Car guns still lie flat.




- Still world loot. No mail.









## 3.6.220 / EXE 1.0.111 - Car has a cabin; 2D guns lie flat




- **Car was a long plank**: fill sat on the hood/roof, so from the side it was one thin layer. It is a sedan side-profile now (hood, raised cabin, tires), slightly taller, guns still flat.




- **2D shapes stood guns**: vault / psycho / firehawk were getting every-third barrel upright. 2D lies flat. House, globe, Claptrap, mask, DNA, dome, pyramid still mix standing guns for height. Boat hull is a bit taller so it is not a plank.




- Still world loot. No mail.









## 3.6.219 / EXE 1.0.110 - Car is long and low; guns lie flat




- **Car was a glowing fence**: 3D shapes stand one in three guns on the barrel, so the car became a tall wall. Every gun on the car now lies flat. The silhouette is a long parked car (hood, cabin, small tires) â not a cube, not a floor stamp.




- Still world loot. No mail.









## 3.6.218 / EXE 1.0.109 - Parked 3D car; Drop All includes every dump shiny




- **Car was a pile on the floor**: "horizontal only" flattened it to a 2D ground stamp and paused catch, so leftovers sat at your feet. Car is a parked 3D silhouette again (chassis, cabin, vertical wheels), same path for Drop All Shinies and Spawn All Filtered.




- **Missing shinies**: Drop All skipped 7 dump-registered pools (PlumbBob, Cormano, Light Gun, Silver Sliver, Fishward, Rhythm, Early Excess) and the dump-proven pearl shinies. End-of-dump catch was capped at 12 leftovers, so extras never left your feet. Those pools are in the dump list, leftover catch can pull up to 80 onto the silhouette.




- Still world loot. No mail.









## 3.6.217 / EXE 1.0.108 - House reads as a house; car is top-down; dome no longer starts UVHM




- **Picking dome started UVHM**: the long Land-in-shape dropdown sits above Start UVHM. Windows sends the mouse-up to that button. Ghost clicks after a `<select>` are ignored, and Start UVHM asks to confirm.




- **House dump looked empty / not a house**: the last pass was a thin wireframe, so ~100 shinies looked missing. Roof faces are filled again (walls + door + chimney, no floor pile).




- **Car looked dumb**: it is top-down on the ground now (horizontal guns only), same for Drop All Shinies and Spawn All Filtered. Dome no longer auto-peels unless you pick drip.









## 3.6.216 / EXE 1.0.107 - EXE icon; Spawn All shapes dump-sized




- **EXE showed Electron's icon**: `icon.png` was a JPEG, and portable builds skipped resource editing. Real PNG + `icon.ico` are stamped onto the EXE (still unsigned).




- **Spawn All Filtered too big**: bulk house was radius 520 and Claptrap 400 (then another 1.35Ã). 3D silhouettes now sit near Drop All Shinies size; extra items densify the wireframe instead of growing a mansion.




- **House dump looked like a pile**: filled roof/floor quads. House is a standing wireframe (ridge, eaves, door, chimney) lifted off the ground.









## 3.6.215 / EXE 1.0.106 - Live version + restart vs GitHub EXE




- **Stale âgame still has v3.6.210â after restart**: the live bridge reported a hardcoded version instead of `_mod_version.py`. Status / panel / pyproject now import that file, so a full game restart shows the version actually on disk.




- **EXE copy**: restart Borderlands 4 = files already synced, game process is old. Download from GitHub = this EXE is behind a release. Restarting the game is not a substitute for a new EXE.









## 3.6.214 / EXE 1.0.105 - Force fly actually flies




- **Judder then stop**: fly brake was 24â280 (vanilla is 0) and accel was `speed Ã 3.5`. A speed of 2e12 overflows CharacterMovement, so it felt identical to 20000. Speed is clamped to 800â120000, fly brake is 0, accel is capped, world MaxFlyAltitude is raised, and CheatManager.Fly is used so it stays in fly instead of snapping back to walk.









## 3.6.213 / EXE 1.0.104 - Dump catch shapes again




- **Not shaping**: dump `at_location` is only a hint â items still spit at your feet. 3.6.212 skipped the catch that teleports them onto slots (and skipped the 2D end-settle), so Drop All sat in a pile. Catch is back: light per-dump pull + leftover sweep, 2D included.




- **2D psycho** silhouette from 3.6.212 is unchanged. Feet-spit uses the next empty slot (not a wide nearest-snap that piled everything on the chin).




- Still world loot. No mail.









## 3.6.212 / EXE 1.0.103 - 2D psycho is a psycho; dump no longer hitch-reshuffles




- **2D psycho** was an oval with two circle eyes (a dumb face). It is now a pointed-chin skull, tall mohawk, slash eyes, vault V, and teeth â features reserved so a shiny dump cannot drop them.




- **Lag while dumping**: Drop All was `find_all`-scanning after every pool call, then moving items onto the next unused slot. That hitch is gone. Dump already lands on the planned slots; 2D stays put. 3D still pins stragglers to the nearest slot, not a reshuffle.




- Still world loot. No mail.









## 3.6.211 / EXE 1.0.102 - Per-shape sizing; less spawn lag; globe stop overflow




- **Drop All Shinies** defaults smaller (house radius 200 / spacing 72). Each shape has its own base size; globe/pyramid stay compact so ~80â130 shinies fill the wireframe instead of leaving gaps.




- **EXE**: changing Land in shape updates radius/spacing to that shape's defaults (Drop All vs Spawn All use separate profiles).




- **Globe shooting**: extra dump items no longer get pushed outward when slots are full â overflow catch stops instead of stacking physics on the same points.




- **Lag**: per-dump catch budget trimmed again (2 items/pass, deferred catch 2). Still pin-once world spawn.









## 3.6.210 / EXE 1.0.101 - Shape spawn back to pin-once (no freeze)




- **Freeze**: after the smoother-spawn / catch-every-tick work, every dump was find_all-scanning, double-teleporting, and restamping pins on a timer. That locked the session on globe, pyramid, and large dumps.




- Spawn is **pin once, freeze physics, stop**. No per-tick restamp, no settle loop over the whole plan, no nested motion tick.




- Drop All Shinies still defaults house / radius 300 / spacing 90. Spawn All Filtered still house / 520 / 70 / 2 per tick. Still world loot.









## 3.6.209 / EXE 1.0.100 - Globe and pyramid stay house-sized




- **Globe / pyramid freeze**: the last globe fix grew the ball with item count (up to huge spans). Pyramid did the same â 2D rows with no cap, 3D filled faces. Those oversized clouds locked physics.




- Globe, 3D pyramid, and dome now stay about house-sized. Extra dump items reuse existing slots instead of rebuilding the whole silhouette each time.









## 3.6.208 / EXE 1.0.99 - Globe no longer freezes the game




- **Globe**: was drawing a filled shell *and* latitude *and* longitude on the same sphere, so hundreds of pickups stacked in the same spots and physics locked up. It is a single spaced lat/lon wireframe now, and radius grows with count.









## 3.6.207 / EXE 1.0.98 - HUD toast options removed




- **HUD confirmations** toggle, Test HUD toast, and the in-game toast overlay are gone (Home, Mobility, World Spawn). Status still shows in the SDK menu / EXE.




- Gearbox logo stays removed. Drop All Shinies vs Spawn All Filtered layout defaults and dump-first world spawn are unchanged.









## 3.6.206 / EXE 1.0.97 - UMG HUD toast; Gearbox logo removed; dump vs Spawn All layouts




- **HUD toast**: uses native UMG (UserWidget + TextBlock + AddToViewport), the same on-screen path as UI SLOP. Yellow banner at the top of the game for 8 seconds.




- **Gearbox logo** shape option removed.




- **Drop All Shinies** defaults to house, radius 300, stay in air. **Spawn All Filtered** defaults to a larger house (radius 520) for hundreds of items. Radius auto-grows with count so the silhouette is not missing a wall/roof.




- **Smoother spawn**: shaped Spawn All no longer find_all-scans between pearls; 2 items/tick default. Still world loot, no skipped rows.









## 3.6.205 / EXE 1.0.96 - HUD overlay actually draws; dump extras stay on the house




- **HUD Test / boost toasts**: PrintString never appears on BL4. Toasts are now drawn on the game HUD (`OakHUD:ReceiveDrawHUD`, same path as ULM) at the top of the screen for a few seconds. Reload the SDK mod, then Test HUD toast while in a session.




- **Co-op behind the shape**: dump extras were frozen at the host's feet (behind the house). Overflow actors are pinned onto remaining silhouette slots, stragglers are swept, and `upandforward` spit is not used while a shape is armed. Player 2 should see the house without a floor pile behind it.









## 3.6.204 / EXE 1.0.95 - First dump no longer cancels the shape; HUD text




- **First dump + shape**: the mod compared Python `id(World)` wrappers. That id changes every fetch, so attempt one thought you left the map and wiped the silhouette. Landing now stays armed; a missed pawn tick skips the frame instead of cancelling.




- **Crash**: removed same-frame 5Ã find_all, 256-pin net bursts, and dump-time pickup refresh (those AVs).




- **HUD Test**: uses Kismet `PrintString` / on-screen debug first so the message actually appears. EXE shows the real result text.









## 3.6.203 / EXE 1.0.94 - Dump into the slot, do not wipe the first shape




- **Dump + 3D shape**: dump now uses the silhouette slot transform (it was spawning at your feet and hoping catch would teleport). Stay in air keeps catch/pin restamps running.




- First batch no longer cancels the armed shape: a failed pawn lookup during dump used to `abandon_world_loot()`, so attempt one fell and attempt two worked.




- New dump actors at 0,0,0 are still catchable. Pin restamp keeps running while the queue drains so clients see the hold.









## 3.6.202 / EXE 1.0.93 - Hard pin dump shapes, co-op replicate burst




- **Dump + 3D shape**: `_pin_pickup_to_slot` freezes, double-teleports, and pins immediately (no 350ms wait). Five catch passes per dump; lock path teleports feet spits straight onto slots.




- **Co-op**: net burst restamps all held slots after each catch batch + at settle; pins tick 48/tick every 50ms; NetUpdateFrequency cranked during landing.




- **Psycho mask**: slightly slimmer cheeks (narrower oval, tighter eye spacing).









## 3.6.201 / EXE 1.0.92 - Gearbox 3D logo, co-op shape sync




- **Gearbox logo** is now a **3D** standing logo (in the air in front of you): wider icon, gear + gearbox / SOFTWARE wordmark. Was flat on the ground as a 2D square.




- **Co-op dump shapes**: 3D pins stay held for the whole spawn, restamp round-robin (28/tick, every 120ms) with double net-update so clients see the silhouette instead of feet drops.









## 3.6.200 / EXE 1.0.91 - Gearbox logo, globe, HUD toasts, dump MP sync




- **Gearbox logo** (2D): square gear icon + gearbox / SOFTWARE wordmark. **Globe** (3D): sphere with latitude/longitude grid.




- **HUD boost confirmations** on Home tab (toggle + test). MAX ALL / level / eridium / SDU / currency from the EXE now trigger in-game slide-out toasts when enabled.




- **Dump + shape**: always replicate pin teleports (fixes clients seeing items on the ground), double-pass catch on each dump, deferred retry armed before spawn. First pool tick runs motion catch immediately.




- **EXE waiting screen**: "Start Borderlands 4" instead of misleading Install SDK steps when the game is simply not running (`fetch failed`).









## 3.6.199 / EXE 1.0.90 - First dump catch sticks, vault V bolder




- **Dump + shape**: first item no longer falls through on attempt one. Deferred catch now retries on the HUD tick even while the spawn queue is draining, shape pins stick during that drain, and the retry window is longer.




- **Psycho mask**: vault chevron uses more slots, wider arms, and two clear legs so the V reads from a distance.









## 3.6.198 / EXE 1.0.89 - Psycho mask v1 back, dump first-catch fixed




- **Psycho mask** restored to the oval + eye sockets + vault chevron + circular mouth grill silhouette (matches the reference art again; drops the zigzag grin / mohawk simplification from 3.6.197).




- **Dump + shape**: first item no longer spits at your feet when a silhouette is armed. Post-dump lock/catch now busts the pickup scan cache and honors `fresh=True`, with a longer deferred retry if the actor isn't visible on tick zero.









## 3.6.197 / EXE 1.0.88 - Vehicle jump in EXE, psycho mask silhouette




- **Vehicle** tab: **Unlimited vehicle jumps** toggle + repeat cooldown + **Test jump now**. **Apply vehicle tuning** also exposes unlimited boost and jump height/gravity sliders.




- **Psycho mask** 3D shape rebuilt as a standing oval skull (eyes + zigzag grin + mohawk) so short dump counts still read as a mask.









## 3.6.196 / EXE 1.0.87 - Shape drop no longer AVs after peel or in lobby




- After **Drop after** finishes, dump actors are released. The old restamp kept teleporting them and crashed (access violation in the SDK) once you picked them up or returned to the lobby.









## 3.6.195 / EXE 1.0.86 - Dump Drop-after actually peels




- Drop All Shinies 3D silhouettes now fall after **Then drop to ground after (sec)**. Dump was skipping the hold list while catch was paused, so the timer often fired with nothing to drop. The clock now starts after the dump finishes.









## 3.6.194 / EXE 1.0.85 - Dome rim closed, peel no longer dumps every item in one tick




- **Dome** is a closed hemisphere: full equator ring, ribs, even shell fill, cap. The old pole-biased cloud left a hole in the rim.




- **Drop after** peels Spawn All / dump silhouettes in small batches and only teleports live pickups. Starting every item at once was crashing the game (access violation in the SDK).









## 3.6.193 / EXE 1.0.84 - Language picker




- EXE header adds a **Language** menu next to Theme. English, French, German, Spanish, Portuguese, Italian, Polish, Russian, Japanese, Korean, and Simplified Chinese. Choice is saved with your other app settings. Tab names and the EXE chrome translate; in-game action labels from the live mod stay English.









## 3.6.193 / EXE 1.0.83 - Portable keeps stock Electron host




- Portable EXE is no longer resource-edited (icon/version stamp). That rewrite made a new unsigned hash and Smart App Control started blocking it. The host is the same official Electron binary as `npm start`.









## 3.6.193 / EXE 1.0.82 - Psycho mask off the dirt, dump peel timer




- **Psycho mask** sits fully above the ground (chin was below your feet, so it looked half-buried).




- **Drop after (sec)** now peels a dump silhouette when the time elapses. The timer starts after the dump finishes landing, and a set number of seconds is enough even if Stay in air is still yes.









## 3.6.192 / EXE 1.0.81 - Theme buttons, 3D silhouette polish, mixed gun pose




- Every theme now has Scooters-style sweeping action buttons in that palette (Default, Tina, Claptrap, Moxxi, Crimson, Psycho, Maliwan).




- 3D **pyramid** fills all four sides plus the square base (the last face was getting dropped).




- **Claptrap** matches the reference: facing eye, antenna, tapered box, jointed arms, one wheel.




- **Psycho mask** matches the BL4 mask: sockets, mouth grill, vault chevron, head depth (no mohawk).




- Hidden pair silhouette uses larger teardrop globes with more forward range.




- Weapons mix **standing and lying** on spawn and pin, so a shiny dump (and pool dumps) can draw height instead of one flat pancake.









## 3.6.191 / EXE 1.0.80 - Extra palettes




- Theme menu adds **Claptrap**, **Moxxi**, **Crimson** (red/black), **Psycho**, and **Maliwan**.









## 3.6.190 / EXE 1.0.79 - Get Online steps, 3D shapes up top, Tina theme




- Get Online is four steps: load EXE, load game, set a non-default install folder in **Setup** (link), then load/reload.




- 3D shapes sit at the **top** of the dropdown. New **Claptrap**, **pyramid**, and **psycho mask**. Car keeps a readable body with a short shiny dump (wheels are vertical disks).




- **Stay in air** holds a 3D silhouette; turn it off and set **Drop after** to peel to the ground.




- Theme menu: Default / Scooters / **Tina**. Kits tab uses a shield icon.









## 3.6.189 / EXE 1.0.78 - All-in-one, no extra copies




- Squ1ggs Boosting Tools always runs its **bundled** movement / kits / damage / spawners.




- Extra standalone copies of those same tools are paused while Squ1ggs is on (they come back if you turn Squ1ggs off).









## 3.6.188 / EXE 1.0.78 - Stay in control with other live-tool mods




- While Squ1ggs is enabled, overlapping extra SDK mods that copied the live desktop bridge / loot catcher are paused so fly, shapes, and the EXE do not fight. They come back if you disable Squ1ggs.




- EXE only talks to a Squ1ggs bridge (`product_id`), and will look on nearby ports if 49775 is already taken.




- PlayerTick hooks are re-claimed while the desktop app is connected.









## 3.6.187 / EXE 1.0.77 - Connected status, kits icon, shape polish




- Connected status is just **Connected! / lets mod** (Oak2 hint stays in Setup, not the live line).




- Kits tab uses a shield + kit icon instead of the eridium gem.




- Smiley keeps a mouth and nose. House roof / dome cap spawn first so short dumps still fill them. Car wheels are reserved and prefer classmods.









## 3.6.186 / EXE 1.0.76 - Drop backpack, fly speed, 3D shapes, girly Scooters




- **Drop backpack** keeps spilling until the pack is empty (the old spawn pattern only spat one item).




- **Force fly** restamps MaxFlySpeed while you are already flying, so the slider actually changes speed.




- Loot shapes: 3D **house / boat / car / dome / DNA helix** at the bottom of the shape list. **Dome** + slow/drip peels loot down to the ground. New **drip** drop mode.




- Desktop: third theme **Girly Scooters** (same Scooters look, pink / lavender). Theme button cycles default â Scooters â Girly Scooters. Local only â not published.









## 3.6.185 / EXE 1.0.75 - Oak2 0.3 gate + GiveCurrency fix




- EXE treats oak2 below **0.3** (or untracked) as must-update.




- Status shows when the live game mod is older than the EXE bundle (e.g. still on 3.6.180).




- GiveCurrency rebuilds a real `FGbxDefPtr` instead of passing `WrappedStruct`; wallet set prefers slot write (same path as MAX ALL).




- Clearer errors pointing at Update base SDK when the cast fails.









## 3.6.184 / EXE 1.0.74 - Kits & Shields rename + Offline fix ship




- Renamed the **Resources** tab to **Kits & Shields** (repair kits / shields / recovery tuning).




- Ships the Offline / circular-import fix (bridge version literals + auto-sync only upgrades).




- Hidden app updater (no CMD/FIND flash).




- MAX ALL already maxes vault cards **1â4** (tokens + XP).









## 3.6.183 / EXE 1.0.73 - Stop Offline spam




- Bridge/status no longer import package `__version__` (circular import flooded the SDK log and killed Online).




- EXE auto-sync only upgrades when bundled mod is newer â it will not wipe a newer on-disk fix.









## 3.6.181 / EXE 1.0.71 - Real mod version + Vault Card 4 give









- Bridge was hardcoding `mod_version` **3.6.49**, so the EXE kept saying ârestart BL4â forever after update.




- Status now reports `__version__` (3.6.181+).




- Give currency (delta) for vault cards uses the same absolute wallet path as MAX ALL.




- Vault Card 4 slot resolve / error text from the prior local fix included.









## 3.6.180 / EXE 1.0.70 - Update banner no longer stuck outdated









- After Install update, the checker uses on-disk / bundled mod version (not only the live game reading).




- If files are current but BL4 is still on an old mod, show restart-game â not another install.




- Install update always applies the portable EXE when a zip is present.









## 3.6.179 / EXE 1.0.69 - GitHub release









- Verified Vault Card 4 currency/XP against live dump (`VaultCard04_Tokens` / ExperienceState[5]).




- Ships the pending desktop build as **EXE 1.0.69** (next after GitHub **1.0.68**).




- Report issue button; Most used expansions; wave packs / IO cleanup; black market spawn + purchase CD; golden chest spawn/open-all; loot shapes; auto mod sync.









## 3.6.178 / EXE 1.0.167 - Report issue button









- Topbar + footer **Report issue**: opens a small chooser â GitHub issue (pre-filled EXE/mod/game connection) or Discord.




- Issue prefill uses **Game connection**, not internal âbridgeâ wording.




- Open/Close golden chest now targets every scripted chest in range (AI copies, logos, nearby map), not just the newest + seed.




- Discovery uses find_all(False), script Outers, remembered spawns, `_SPAWNED`, and nearby OakSpawner alive actors (log showed older AI copies dropping out of find_all).




- World IO spawns: removed Aggro mode (props are not combatants); IO detect skips aggro queue.




- EXE **1.0.167**.









## 3.6.177 - Golden chest: stop dual-world freeze









- `goldenchest` was on the dual-world spawn list, so `Lootable_GoldenChest` matched by substring and queued a PersistentLevel `oak_spawn` of the map chest â that freezes.




- Removed from dual list. Most used now calls the same `spawn_ios` path as IO spawner (single `oak_spawnai Lootable_GoldenChest`).




- EXE **1.0.164**.









## 3.6.176 - Fix Spawn golden chest crash









- Most used **Spawn golden chest** now uses the same catalog cmd as IO spawner: `oak_spawnai Lootable_GoldenChest`.




- Bare alias `goldenchest` was not an IO code, so it fell through to `run_oak_line` and could hard-crash. Alias remap added in `spawn_io`.




- EXE **1.0.163**.









## 3.6.175 - Serials order + action card fill









- Serials tab: **GZO** and **Lootlemon** sit directly under **Serial tools**.




- Action-card frames around compact buttons use cyan/violet fills instead of dull empty borders.




- EXE **1.0.162**.









## 3.6.174 - UI polish + spawn golden chest









- Home **Start here** hides as soon as Connected (not only when actions unlock). Desktop Start here card also force-hides.




- Most used: **Spawn golden chest** (near Open/Close).




- Compact action buttons (no more stretched âReset vehicle movementâ / pool spawn giants). Serial paste box spans full width.




- Mob **Group waves** renamed to clearer **Wave packs** with step hint + friendlier button labels.




- EXE **1.0.161**.









## 3.6.173 - Black market release cleanup









- Black market is spawn + purchase cooldown (+ status) only. Removed parked stock/serial, use-timer unlock, map-seen, probe, shuffle, and legacy relocate spawn code from `black_market.py`.




- EXE/panel and blimgui match: Spawn, Clear purchase cooldown, Status. Bridge rejects other BM actions.




- Versions aligned to **3.6.173** (`__version__` / `__version_info__` / panel / pyproject). EXE **1.0.157** auto-copies Squ1ggsBoostingTools into `sdk_mods` on launch when the folder version differs (prompts to restart BL4 if the game is open). First-use oak2 base SDK still uses a confirm dialog (**1.0.156**+).









## 3.6.172 - Reset stopped re-arming lock; stock writes host row









- Live log after Reset: `WaitForCooldownEnd=off` + `CooldownEnd`, then `ClientCallBlackMarketCooldownEvent` â that re-armed the look-without-buy lock. Snapshot also showed `cooldown=None` because ready dump value is on the pawn, not only PlayerState.




- Reset writes `BlackMarketCooldownTimestamp=1` on pawn + PlayerState + PC, unlocks nearest feet copy first, sets `bIgnoreBMVMSchedule`, clears `StructuredInteractableUserState`, and never calls `ClientCallBlackMarketCooldownEvent`.




- Serial Apply prefers nearest machine + host `OakPC` vendor row, whole-array Serials write, then CooldownEnd so the write does not leave the shop locked.









## 3.6.171 - Use unlock all copies + stock writes dump shop









- Live log: Reset only cleared the world shop while spawnai copies at your feet still held WaitForCooldownEnd; stock wrote `machine=nearest` (often a shell) so the dump shop UI never changed.




- Reset now ends use/view lock on every live BM actor (CooldownEnd + InUse off + primary use). Serial Apply writes PersistentLevel `IO_VendingMachine_BlackMarket` first, then every machine with vendor rows, and mutes view-cooldown after write.









## 3.6.170 - Use/view cooldown + multi Spawn









- Buy cooldown is `BlackMarketCooldownTimestamp`. Use/view lock after looking without buying is dump `WaitForCooldownEnd` / `CooldownEnd_ScriptEvent`. Reset now calls CooldownEnd on the already-placed shop only (never during Spawn).




- Second Spawn no longer only relocates the same PersistentLevel shop: if it is already at your feet, oak_spawn duplicates another copy.









## 3.6.169 - Reset cooldown clears the on-screen timer









- Dump timer is player `BlackMarketCooldownTimestamp`, vendor `OverrideRemainingTime`, and script `WaitForCooldownEnd` (`bCooldownOnView`). Writing timestamp with `reps=False` left the ~30m UI stuck.




- Reset / Re-enable now write those fields, call `OnRep_BlackMarketCooldownTimestamp`, and ping `ClientCallBlackMarketCooldownEvent` / `ClientSyncVendingMachineTimer`. Still no `CooldownEnd_ScriptEvent` (that froze spawn). Spawn stays oak_dual-only.









## 3.6.168 - Spawn no longer fires cooldown script events









- Spawn froze because Re-enable's `CooldownEnd_ScriptEvent` / `WaitForCooldownEnd` ran on the shop during oak_dual (and Spawn was still marking visited). Spawn is oak_dual twice again with player timestamp only.




- Re-enable / Reset cooldown write timestamps only. We are not firing dump `CooldownEnd_ScriptEvent` â it froze BL4. Serial Apply stays its own button and is not part of Spawn.









## 3.6.167 - Re-enable ends view-without-buy cooldown









- Dump lock after looking without buying is script `WaitForCooldownEnd` plus `BlackMarketCooldownTimestamp` (player dump value is `1`) and vendor `OverrideRemainingTime`. Repair was rewriting usability/collision and hid the use buttons.




- Re-enable / Reset cooldown now end that dump cooldown only: timestamps, `WaitForCooldownEnd=off`, `CooldownEnd_ScriptEvent`. No poke, no Anim_*.









## 3.6.166 - Re-enable shop use restores dump flags









- Dump `UsabilityConfigInfo` is `bRequireTrace=true`, 135Â° cone, both use slots on. Repair was turning trace/cone off and poking collision/mesh, which kills overlap `Anim_InProximity` and left the spawned kiosk unusable.




- Re-enable now writes those dump flags on PersistentLevel `IO_VendingMachine_BlackMarket` and does not poke or force Anim_*.









## 3.6.165 - 1.0.140 Maurice spawn (two oak_dual passes)









- Dump shop `IO_VendingMachine_BlackMarket` is packed (`Seq_VendingMachine_BlackMarketPlayer` `bReversePlayback=true`). The version that actually showed the kiosk queued `oak_dual` twice: load, relocate PersistentLevel shop, wake vending Active/Usable (including the spawnai copy). One Spawn click now does both passes.




- Removed later Play/destroy and collision-only activate skips that left a red outline.









## 3.6.164 - Unfold dump shop, kill red-outline copies









- Red outline was the packed dump sequence (`bReversePlayback=true`) plus leftover `OakVendingMachine_*` spawnai shells. Wake was keeping the copy (`mesh-miss`) instead of the PersistentLevel shop.




- Spawn still uses oak_spawnai so the weekly shop exists, then teleports `IO_VendingMachine_BlackMarket` to you at z=0, Plays `Seq_VendingMachine_BlackMarketPlayer` forward, unhides `BaseSkelMesh`, and destroys copies. Serial Load/Apply and map pin are unchanged.









## 3.6.163 - Restore pre-today black market spawn









- EXE Spawn is the working 1.0.140 oak_dual path again: oak_spawnai (loads the shop), relocate PersistentLevel `IO_VendingMachine_BlackMarket` to you, then wake/activate. Today's copy/teleport-only paths no-op'd when find_all=0.




- Wake uses vending Active/Usable states again (empty blackmarket preset had blocked that).









## 3.6.162 - Spawn moves the dump shop (copies were half-spawns)









- Live log: duplicate `OakVendingMachine_*` is `mesh-miss` (dump mesh is `BaseSkelMesh` on PersistentLevel `IO_VendingMachine_BlackMarket`). Play on the copy does not drive dump `Seq_VendingMachine_BlackMarketPlayer`.




- Spawn now teleports that dump actor to you, Plays its sequence forward (packed pose is `bReversePlayback=true`), unhides `BaseSkelMesh`, sets `bIgnoreBMVMSchedule`. No `oak_spawnai`. Leftover copies are destroyed.




- Map seen still DiscoverTrackerObject on that dump shop; saved true coords go into `ActivationCenter`.









## 3.6.161 - Black market spawn + true map pin









- EXE Spawn no longer runs `oak_dual`/`oak_spawnai` first (that queued shells and never Played). It duplicates PersistentLevel `IO_VendingMachine_BlackMarket` at your feet, copies the mesh, Plays `Seq_VendingMachine_BlackMarketPlayer` on the copy, then holds. World shop stays put.




- **Black market seen on map** calls dump `DiscoverTrackerObject` / `TrackerOn` / `ToggleTrackingEnabled` on the weekly world shop only (not spawned copies).




- Reset cooldown and 8-slot serial Load/Apply are unchanged (nearest copy). Spawn does not mark-visited.









## 3.6.160 - Spawn Play and hold (red line was reverse-pack)









- 3.6.159 `reverse+GoToEndAndStop` is the dump's packed pose â you only got the spawn red line. The working click was **Play** the 21-frame sequence and leave it.




- One Spawn: spawnai â duplicate â Play (not reversed), pause after 0.8s. No GoToEndAndStop.









## 3.6.159 - Spawn parks like the dump (no Play-then-vanish)









- Dump `Seq_VendingMachine_BlackMarketPlayer`: `bReversePlayback=true`, stopped, 21 frames. Spawn was `Play` then `GoToEndAndStop` â that is the animation in front of you, then it packs away.




- Spawn now duplicates once and parks reverse+GoToEndAndStop like the live world shop. No Play, no RestoreState, no 2ÃAI/3Ãcopy storm.









## 3.6.158 - Spawn is oak_dual again









- Home Spawn uses the original `oak_dual` place path (spawnai â duplicate in this cell â sequence Play + Anim_Idle). It no longer teleports PersistentLevel (ghost) and no longer no-ops as "already at your feet".




- Still does not force `Anim_InProximity` on every copy.









## 3.6.157 - Duplicate shop in this cell; Kill all enemies on Most used









- Relocating PersistentLevel left a transparent LOD (`show Play,UpdateAnimState` still ghost). Spawn now **duplicates** the dump template in your cell, then Play + `GoToEndAndStop` + `Anim_Idle` (not InProximity).




- Home **Most used** includes Kill all enemies.









## 3.6.156 - Spawn second step plays the dump sequence









- Move alone left a transparent shop (`moved â¦ dist_after=350`). Dump `Seq_VendingMachine_BlackMarketPlayer` had `bReversePlayback=true` and `Play` / `UpdateAnimState`.




- Spawn now: move, wait one tick, then Play the sequence (not reversed) + `UpdateAnimState`. Does not force `Anim_InProximity`.









## 3.6.155 - Spawn always teleports the world shop









- Probe: `spawn target â¦ PersistentLevel.IO_VendingMachine_BlackMarket scripts=3 dist=350` then `already at your feet`. 350 is the spawn offset, so the skip never moved it.




- Spawn always `K2_SetActorLocation`s that dump shop in front of you (z=0, unhide/collision poke). No skip.









## 3.6.154 - Spawn moves the dump PersistentLevel shop









- Dump log: `find_all=0` then `Queued â¦ (1 live)` then `already at your feet` â a dead spawnai shell sat on the player so we never moved `/Game/Maps/WorldLevels/World_P.World_P:PersistentLevel.IO_VendingMachine_BlackMarket`.




- Spawn now always targets that dump world shop (scripts>0). Ghost copies are ignored.









## 3.6.153 - Spawn moves the live shop (no oak_dual)









- Spawn no longer uses the oak_dual lobby queue (that was returning "queued" and never placing). It finds a live `IO_VendingMachine_BlackMarket` and teleports it in front of you on PlayerTick. No anim wake.









## 3.6.152 - Spawn places the shop again









- 3.6.151 skipped spawn if any live black market existed (including the world one) and blocked relocating PersistentLevel, so the button queued and nothing appeared.




- Spawn again relocates the live shop in front of you with **no anim/script-state wake**. Second click is skipped only if it is already at your feet.









## 3.6.151 - Stop poking black market use/anim









- Spawn no longer relocates the world shop, no longer forces `Anim_InProximity` / generic Idle-Active, and the dual queue is one place + one duplicate (not 2Ã AI, 3Ã world, 3Ã wake).




- Second Spawn no longer runs Re-enable. Shuffle/visited/Apply/Reset no longer write script anim states or all 8 copies.




- Re-enable is collision + primary use only (no Anim_*).









## 3.6.150 - Load stock is a read; Reset is timers only









- Load stock no longer writes `bCooldownOnView` / shuffle flags on the live machine before copying serials. Status/Reset no longer read shop stock at all (that is what filled the EXE boxes as a side effect).




- Apply after a serial write no longer forces `Anim_InProximity`. Featured **Run** still writes the shop â only use it if you changed a serial.




- Reset cooldown writes timestamps on you + the nearest machine only. It does not restore/anim-poke every copy.









## 3.6.148 - Use prompt is Anim_InProximity; no second spawn









- Dump `vendinganim`: Idle / **InProximity** / Using. Re-enable was forcing Anim_Idle and disabling Anim_Using on every copy â that hides ammo/use icons. Repair now only the nearest machine, overlap on, InProximity on, no CooldownEnd BP.




- Second Spawn while a machine is already nearby skipped (relocating the PersistentLevel shop with the UI open froze BL4).









## 3.6.147 - Apply stock only nearest machine (8 slots)









- Probe log: `stock serials=7/7 machines=8` â Run wrote every spawned copy then `_restore_usable` (Anim_Idle/Active). Dump shop is **8** serials/costs.




- Apply/Load now hit the **nearest** machine only, skip Anim state storms after a serial write, and spawn is one dual queue (not two full queues).









## 3.6.146 - Black market spawn no longer freezes









- Spawn no longer calls `Anim_Idle__OnStateEnabled` / `Active__OnStateEnabled` (dummy state-key BP hung the game thread).




- Spawn click no longer restore-pokes every live machine, then again immediately, then every 0.35s for 10s. Follow-up is 2s and skips map-pin / snapshot.









## 3.6.145 - Black market idle from dump; denser Most used









- Dump: `vendinganim` defaults to **Anim_Inactive**, `Anim_Idle__OnStateEnabled` takes a state key, live shop has `bRequireTrace` + a 135Â° use cone. Spawn/repair now enable Anim_Idle that way, skip WaitForCooldownEnd OnStateEnabled, and relax trace/angle so spawned copies get a use prompt.




- IO wake matches **blackmarket** instead of generic **vending** (that substring was winning first).




- Desktop **1.0.142**: Most used / featured action buttons pack more per row again; field cards stay full width.









## 3.6.144 - Black market load/apply no longer locks use









- Load stock and Apply stock turn off view/buy cooldown around the serial read/write, then re-enable primary use. Dump showed `bCooldownOnView` on the machine script â touching Serials looked like opening the shop.




- Apply no longer replaces the 8-slot Serials array with a shorter list, and no longer fires cooldown OnRep after a stock write.









## 3.6.143 - Group waves fold; black market probe









- Mob spawner stays the same page: spawn actions first, **Group waves** collapsed at the bottom (same Char_* ticks). No second catalog.




- Home **Probe black market** dumps live machine / player discovery and pin fields to unrealsdk.log.




- Desktop **1.0.141**: restore release section/button sizes; Scooters theme toggle text sits above the sweep.









## 3.6.142 - Sweep loop; slimmer BMS groups









- Scooter button sweep no longer restarts every status poll (that looked like a jump every ~5s). Gradient loops as three copies.




- BMS group spawner: fewer fields (options once, then Start/Stop/Next). Compact action cards.









## 3.6.141 - BMS group spawner (desktop + in-game)









- **BMS group spawner** on Mob and IO Spawner: tick Char_*, add groups, start/stop/next, on-clear / timed / loop. Same runner in-game (World â BMS groups). Uses SQBT's bundled mob spawner, not mailbox.









## 3.6.140 - Encounter Builder (in-game only)









- In-game World â **Encounter**: Ripper Drill Site style Char_* waves (on-clear / timed / manual, loop, save). Desktop EXE is unchanged until this is finished vs Funkâs Hoard Builder.









## 3.6.139 - GZO item category / type filters









- GZO catalog (desktop + in-game) can filter by item category (Weapons, Shields, Class Mods, â¦) and item type (Pistol, SMG, â¦). Rows show type and manufacturer. Type list narrows when a category is selected.









## 3.6.138 - Seamless sweep; re-enable black market use









- Scooter colours slide on a duplicated strip so the loop never jumps.




- Reset no longer one-arg toggles `WaitForCooldownEnd` (that could lock the shop). **Re-enable shop use** turns primary use / collision back on.









## 3.6.137 - Scooter ping-pong; live BM stock; view cooldown









- Scooter button colours sweep back and forth instead of jumping when the loop restarts.




- Black market stock: Load from machine fills 7 live serial slots; Apply writes them back; one lobby cost hits every slot. Reset also turns off buy and close-menu (view) cooldowns so shuffle/check and multi-buy work. Map seen notifies OakPC `ClientDiscoveryNotifyLocationDiscoveredStateChanged` with the live machine.









## 3.6.136 - Compact Most used; BM machine script; Scooter sweep









- Most used buttons are shorter (tighter padding, smaller icons, wider grid). Featured toggles sit in the same compact grid instead of tall cards.




- Scooter's theme sweeps aqua / blue / pink across action buttons again (tabs stay dark).




- Removed **Black market ready**. Reset cooldown / mark seen poke `IO_VendingMachine_BlackMarket` (`CooldownEnd_ScriptEvent`, `OverrideRemainingTime`, `DiscoverTrackerObject`, script states). Spawn runs the place path twice. Stock + shuffle use dump Serials/Costs (8 slots).




- World: disallow local travel, cancel travel countdown, allow personal vehicle on OakWorldSettings. ULM lab catalog gets the matching OakPC bools/floats. ResurrectStation stays a handle (live editor).









## 3.6.135 - Fog first click; black market spawn + machine timer









- Temp hide map fog retries immediately for a few seconds (first click used to skip the tick, so a second click could turn it off).




- Clear cooldown also pings dump `ClientSyncVendingMachineTimer` and writes live `OakVendingMachine` copies, then keeps applying for 10s after spawn so the placed shop is not still on cooldown.




- One Spawn black market machine click preloads the dump IO packages and retries place/wake; added to Most used and the Black market Home block.









## 3.6.134 - Black market on Home; dump fog hide; Scooter aqua/pink









- Home **Black market** sits under Most used (ready, visited, cooldown, reroll, status) so the EXE shows it without scrolling past serials.




- Most used keeps every previous button. Order is MAX ALL, Unlock all cosmetics, then the rest, plus spawn legendary/epic loot and Black market ready.




- Temp hide map fog uses dump `OakMapViewerFog` actor + FogMesh/FogRoot (`SetVisibility` / `SetHiddenInGame` / `SetActorHiddenInGame`) and re-applies on PlayerTick even when loot-shape world checks skip.




- Scooter's theme buttons are aqua/blue and pink (no purple fills).









## 3.6.133 - Hide dump-missing named pearls; use type pools









- Pearl list only shows named guns that have a dump itempool. Gomie, Abyss Ripper, and Solar Temper are omitted.




- Note above Loot Pool Spawner / Pearl: if a named item is missing, use the related AR / SR / SM / SG / PS Pearl Pool.









## 3.6.132 - Named pearls always try live NCS; P6 silent-empty









- Constable / Herald / Juliet / Parasite / Screwstonian / Sharkbait use their dedicated `*_06_pearl_*` pools. Selected spawn now treats a pool call with no loot as a miss and tries every loot-pool store plus the live ItemPoolDef.




- Gomie / Abyss / Solar Temper still have no dump itempool row; live NCS is tried anyway, then the type-pool walk / ItemPoolList / inv-comp. PearlDrop FModel assets are projectile scripts, not loot defs.









## 3.6.131 - Named Gomie / Abyss / Temper from live type pearl pools









- Those three can roll from live `itempool_ar_06_pearl` / `itempool_sr_06_pearl` even though the FModel JSON never listed them. Named spawn now walks that live parent for the matching inv-comp (not a random type roll, not serial).









## 3.6.130 - Gomie from dump ItemPoolList; Abyss / Temper live inv









- Dump: Gomie is an inline ItemPoolDef on `ItemPoolList_Raid2_Thol` / `_True`, not a named itempool. Spawn that live list row on the ground.




- Abyss Ripper and Solar Temper still have no ItemPoolList/itempool row in the NCS dump; resolve the dump inv-comp from loaded inventory defs.









## 3.6.129 - Gomie / Abyss / Temper dump inv; less pearl scan lag









- Dump: Gomie, Abyss Ripper, and Solar Temper have no standalone itempool â they are ItemPoolList inv-comps. Spawn those from `inv'â¦'` on the ground (not serial, not a fake pool name).




- Pearl spawns no longer scan every world pickup around the pool call (that was the remaining hitch).









## 3.6.128 - Spawn selected logs are not Spawn All









- One selected pool logs `Spawn selected: â¦ x1` plus that item's OK/FAIL. It no longer prints Spawn All queue/cleanup/batch lines or the all-time summary dump.









## 3.6.127 - One Soul Survivor roll; single spawn is not Spawn All









- Dump: Spawn selected Soul Survivor was 1/1, not Spawn All. The summary still said "spawn all done".




- Freeze + two guns: the pearl path called the same pool on every loot-pool service layer, then scanned the world after each call. One selected spawn is now one pool roll.









## 3.6.126 - Pearls are NCS pool rolls only









- Loot Pool Spawner named pearls no longer fall through to @U serial or dump inv. Serial is not a pool roll.




- Uses the dump NCS names (Herald, Juliet, Locust, Gomie, Abyss, Temper, Jail-Broken, Raiden, â¦) even when older game_data.json omitted them. Each spawn is SpawnInventoryFromItemPool.









## 3.6.125 - Pearl queue hitch; dump NCS first









- Progress bar does not hitch the game (it only reads counters). Pearls lagged Spawn All because each one walked every NCS store, dump-inv, then FromSerial.




- Spawn All named pearls: one dump NCS call, then dump inv if needed. No serial. Crazed Earl uses the dump pearl pool, not the Maliwan SG shiny.









## 3.6.124 - Spawn All pearls: world pickup, not feet









- Last Spawn All marked Herald / Constable / Juliet / every named pearl as serial-fail. Dump NCS did run; loot was checked at feet during a shaped dump, then a serial error was recorded without looking at world pickups.




- Named pearls now count OK when a new ground pickup appears anywhere (shape slots included). If the pearl path raises, Spawn All still counts OK when loot is already there.









## 3.6.123 - Dump NCS pools for Jail-Broken / Raiden









- Jail-Broken Gatling and Raiden use the Nexus-Data-itempool names that wrap their dump inv-comps (`itempool_bor_sm_05_legendary_jailbroken`, `itempool_dad_sm_05_legendary_raiden`). Those were skipped because they are missing from the older game_data.json item_pools list.




- All five dump-inv pearls (Abyss, Gomie, Jail-Broken, Raiden, Solar Temper) spawn from dump-exact `inv'â¦'` handles first, then verified NCS, then merge/serial. NCS success still requires loot on the ground.









## 3.6.122 - Spawn All reports real loot; pool UI cleanup









- Loot Pool Spawner: shape / height / spawn-then-shape only on Spawn all filtered. Spawn selected is level, count, and drop-near.




- Drop backpack is on Most used (still on F.A.A.F.O.).




- Spawn All Filtered counts OK only when a new ground pickup appears. Silent empties are FAIL (`loot_observed: false`), including named pearls that previously returned unverified OK.




- Dump check: Abyss Ripper, Solar Temper, Gomie, Jail-Broken Gatling, and Raiden are inv-comps only (no live dump itempool). Ground spawn still fails honestly when the live def is not loaded.









## 3.6.121 - Missing dump legendaries; Jail-Broken no longer the wrong gun









- Dump check: pearls are complete vs game_data + Lootlemon. Hard fails were Abyss, Solar Temper, and Raiden (no live dump pool). Jail-Broken was âokâ via Maliwan SG shiny â that path is locked to the same gunâs dump pool now.




- Added singular L5 dump comps that had no itempool row (Draupner, Jet Set, First Impression, Hard Dark, Loarmaster, Screenwriter, Bottled Lightning, Gamma Void, Ichor, Firework, Dahl Father, Javelin, Ravenfire, Sidewinder, Unstable Kor, Atling Gun, Flak, Splatoon). Commons/epics stay type-pool rolls.




- Named pearls try the dump inv-comp after NCS before merge/serial.









## 3.6.120 - Named pearls actually dump









- Spawn All Filtered named pearls were counting as OK after a silent merge call and never hitting their live dump NCS pools. Herald / Constable / Juliet / etc. now dump via the same SpawnInventoryFromItemPool path as the type pools. Merge inv only runs after that, and only counts if loot actually appears.




- Jail-Broken / Raiden no longer take the dead supplement-only route. Jail-Broken retries the Lootlemon `@U` serial. Raiden still inv-only (no dump pool, no serial) â fail on the ground, no mail.









## 3.6.119 - Named pearlescents back in the pool spawner









- Pearl tab lists the five type pools again, plus every singular dump-NCS pearlescent (Herald, Constable, Juliet, Gomie, Abyss, â¦) as `>` rows you can spawn one at a time. Spawn All Filtered still dedupes type-pool expansion against those named rows.









## 3.6.118 - Firehawk is outline only









- Firehawk is the Lilith bird outline again (beak left, jagged wings, three-flame tail). Interior fill is gone.









## 3.6.117 - Drop methods animate; spawn-then-shape in front; pearl hitch; repeat-spawn crash









- Rain / fountain / spiral were freezing in the air for the whole dump then snapping onto slots because motion clocks expired during drain. They tick during dump again, and clocks restart when the batch finishes.




- Spawn all, then shape now dumps a few feet in front of you (small visible pile), not inside the pawn.




- Repeat Spawn All after a few runs was AVing on stale pickup wrappers. Each new landing drops old wrappers without touching Unreal.




- Pearl rows in Spawn All were hitching the whole queue: loot-verify find_all + cache reset + blocking the next dump. Bulk pearl dump skips that verify/block. Still dump-first world loot.









## 3.6.116 - Spawn All no longer sprays; spawn-then-shape toggle









- Spawn All Filtered dump was shooting guns out because catch only looked at the last 48 pickups and never froze dump launch. Catch is full-world address scan again, freeze-before-catch is back, and the end sweep drains every remaining dump actor into the silhouette.




- New toggle: **Spawn all, then shape**. Off = place one-by-one as they dump (default). On = dump+freeze everything first, then move the pile into the shape so you can compare hitch. Still dump-first world loot. Main-menu teardown from 3.6.115 stays.









## 3.6.115 - Main-menu crash after dump spawn; cheaper dump catch









- Returning to the main menu after a shaped dump no longer AVs. Pickup wrappers are dropped without touching Unreal as soon as the pawn/world goes away, and PreLoadMap / return-to-menu hooks abandon landing before teardown.




- Dump catch no longer double-scans (lock then catch) or walks every pickup in the world. Each dump item catches at most a couple of newest actors; height motion and delayed pins wait until the dump drain finishes.




- Per-item dump teleports skip net replication until after the batch. Shape + freeze stay dump-first world loot.









## 3.6.114 - Slider limits; 0 line length no longer freezes









- Line length 0 stacked every gun on one point and froze physics. Line now keeps a minimum gap, and the slider cannot go below 200.




- Drop height, radius, spacing, per-ring, ground height, and stack height all have min/max in the UI and in the spawn path. Drop height tops out at 800.




- Dump spawn/place hitch is expected: each item is still spawned then locked into the silhouette. That is dump-first world loot, not a mail fallback.









## 3.6.113 - Stop dump collision spray; Firehawk is a filled bird









- Dump still launches items with pitch and physics. One gun standing on its barrel was knocking every neighbour out of the silhouette. Freeze now also switches pickup collision to query-only (still pickupable) and flattens pitch/roll immediately after each dump, before the catcher runs.




- Stragglers that already had a slot are sent to the next silhouette slot instead of the nearest front-edge point, which is what collapsed a working shape into a blob in front of you.




- Firehawk is no longer a sparse outline scribble. It is a filled Lilith-style bird (beak left, jagged wings, three-flame tail) sampled on both the outline and the interior, and scaled up so it actually reads.









## 3.6.112 - Spawns no longer pile on one slot; scan cost stops growing









- Spawn positions now advance on their own instead of waiting for the catcher. Previously a single missed catch aimed every later spawn at that same slot, so items stacked on one point and shoved each other across the floor, and it never recovered. That is the "works for a while then sprays everywhere" behaviour.




- Pickup scans reject already-known items by address before reading any actor property. Each scan used to probe the world location of hundreds of already-placed items, so spawning got progressively slower the further a run went.




- The pre-run pickup snapshot is no longer capped, so loot that was already on the ground is not mistaken for a fresh drop and dragged into the new layout.




- The final sweep now sizes its pickup radius from the silhouette instead of a fixed 560 units, which was smaller than the shape itself on wide layouts and left drifted items behind.









## 3.6.111 - Catch every dump pickup class









- Shaped dump scans now reserve capacity for both InventoryPickup and OakInventoryPickup actors. A full first class can no longer hide newly spawned actors from the second class and leave their native forward launch velocity active.




- End-of-run straggler collection checks both pickup classes instead of returning as soon as the first class reaches its sample limit.




- The combined result remains cached briefly, preserving the lower scan rate from 3.6.110.









## 3.6.110 - Pool overflow stays shaped; lower-cost height motion









- Pool calls which emit more actors than estimated now reuse slots inside the silhouette. They can no longer exhaust the plan and fall back to the normal forward-facing launch.




- Final cleanup now freezes actors which spawned near their intended slot instead of marking them complete while physics remained active. Two bounded settle passes cover late physics initialization on heavier sniper pickups.




- Height animation uses plain intermediate teleports and performs physics/network finalization only at landing. Catch scans share a short cache and intermediate motion is capped at three items per tick to reduce placement hitching.









## 3.6.109 - Spiral settles once; live clients receive movement snapshots









- Ground-level spiral and other direct layouts get one delayed freeze/settle pass, then release every pickup wrapper. This catches the engine re-enabling physics without restoring the stale permanent pin loop.




- Corrective teleports now enable actor movement replication, stamp the server movement snapshot, wake dormancy, and force a net update for clients already in the lobby.




- Delayed settling is capped at six pickups per tick to avoid another placement hitch.









## 3.6.108 - Mix/match shape + height completes without stale pin crashes









- Dump actors missed by the immediate catch get a short deferred retry, for both Drop All Shinies and Spawn All Filtered. Random-spit off still means no intentional spray; native dump launch velocity is caught and zeroed.




- Rain/fountain/stagger use a bounded 10-item cascade instead of delaying item 200 for up to a minute. Height motion runs at a safer budget and stale flight jobs expire.




- Removed the permanent pin loop and stopped snapping old wrappers when starting/stopping another layout. Pickups are frozen once; this addresses the latest GameThread `0xffffffffffffffff` pyunrealsdk crash.









## 3.6.107 - Revert failed pickup hook; safe Shapes reset









- Removed the BeginPlay pickup-hook experiment that missed dump guns and sent Shinies / Spawn All back to spit. Restored the proven 3.6.103 per-dump catch for both paths.




- Shapes now cancels old flight/pin tracking before a manual layout, de-duplicates pickups by Unreal address, and never reads raw serial memory. This addresses the new GameThread pyunrealsdk `0x0` / `0xffffffffffffffff` crashes.









## 3.6.106 - Spawn All Filtered lands in shape; Place Fully no longer AVs









- Spawn All Filtered + a shape now catches after every pool (it only did that on shiny dump before). Test cleanup stays off while a silhouette is armed.




- Place Fully / Quick Arrange: skip dead pickups and never read serials from a null pointer (that was the `EXCEPTION_ACCESS_VIOLATION 0x0` after sorting dump loot).









## 3.6.105 - Shape catch after every dump again (no spray)









- Dump still sprays; we pin after every spawn again (3.6.104 skipped that and most guns hit the floor). New pickups are grabbed from BeginPlay when possible so the world find_all is only a fallback.









## 3.6.104 - Dump shapes without the hitch









- Drop All / Spawn All no longer find_all after every dump (that was the lag). Dump advances to the next slot itself; catch runs every 8 items and once at the end. Rain/fountain still animate from that light catch.









## 3.6.103 - Height drops no longer leave dump spit behind the silhouette









- Drop-from-above: rain/spiral/fountain stay over the shape (not behind it at your feet). Leftover dump spit around the player is pinned onto remaining slots (also the last 2â5% on ground shapes).









## 3.6.102 - Every land-in-shape works after dump (grid / â / 8 / wave / pyramid / poisson)









- Catch no longer fills up with leftover guns from the last shape (that is why grid/â/8/wave started spitting mid-run). New dump actors are pinned even when the ground is already busy.




- Star / â / figure-8 sit fully in front of you (they were half behind your feet). Wave/pyramid/grid/poisson silhouettes are tighter and readable. Poisson = filled scatter patch, not dump spit.









## 3.6.101 - Shape selected = every dump gun goes on the silhouette









- Dump still sprays; we catch after every drop again (the 3.6.98 path that actually placed). Spit only when land-in-shape is none. Verify scans stay off so it is not the old hitch loop.









## 3.6.100 - Shape pin is back (cheap, after every dump)









- 3.6.99 skipped pinning and dump spat again. After each dump we now snap the newest gun onto the current slot (newest-only scan, not a world find_all). Already-on-silhouette guns are left alone.









## 3.6.99 - Shaped dump no longer hitches on the few spitters









- Drop All Shinies + shape: no per-item find_all verify/catch (that was the lag). Dump onto the next slot, advance the index, and only pin leftover feet-spit every 12 / at the end.




- Reuse the at-transform dump winner instead of retrying scatter candidates each gun.









## 3.6.98 - Shape / drop mode never leave dump spit on the ground









- Dump was using `spawnpattern_default_loot` / `upandforward` (random spray). With a shape or drop-from-above selected it now uses an at-transform pattern, then immediately pins any leftover spit onto the silhouette (square, rows, rain, fountain, â¦).




- Catch also sees `InventoryPickup` dump actors. Drop-from-above still starts above the slot and lands in the same shape.









## 3.6.97 - Rows / ground shapes spawn on the slots (lobby can see them)









- Dump was stuffing a Rotator into FTransform.Rotation, so NCS ignored XY and spat at feet. Now uses a Quat + land pose so rows/circle/â¦ appear on the silhouette.




- Drop-from-above none skips the hitchy catch/find_all (spawn at the slot). Teleport/Place Fully marks pickups always-relevant + ForceNetUpdate so party clients can see the layout.









## 3.6.96 - Dump spit no longer fights the shape









- Catch dump actors out to 6000uu (they were flying past 1600 and looking like random spit). Flight jobs stay alive when wrappers go stale instead of freezing mid-air.




- Second Drop All Shinies snaps in-flight guns onto their slots first; already-placed silhouette pins stay (no yeet). Catch after each dump spawn. Less hitchy scans (no Name probes, 30 Hz motion).









## 3.6.95 - Shape drops actually fly into the slots









- Rain / fountain / spiral / stagger / slow / fast / snap now script into the selected shape (heart, square, â¦) instead of hanging then gravity-scattering.




- Fountain arcs from your feet out to each slot. Rain jitters then converges. Dead pickup wrappers are skipped (no 0xffffffffffffffff TeleportTo).




- Dump catch scans OakInventoryPickup / OakPickup again. Motion ticks on the proven UMG hook.









## 3.6.94 - F.A.A.F.O. tab (party chaos + locks)









- New **F.A.A.F.O.** tab: StreamerChaos-style launch / backpack drop-delete / FFYL / kill / invert look / lock look-move, aimed at boost targets (not NumPad-local-only).




- Weapon restricted, vehicle lock, ammo regen, no-target, force fly, and kill-all are mirrored there; Player tab buttons stay.




- Do not install standalone StreamerChaos beside SQBT.









## 3.6.93 - NCS FModel export ingested (Harp travel + loot merge)









- Parsed the FModel `_NCS` + `_NCS patch` export (514+9 files) with NcsParser `--deps`.




- Loot merge rebuilt from inv/itempool/name_part shards 0/4/6 plus itempool8 and patch overlays. Pool spawner still has 511 rows (cosmetics skipped; dump-find shinies kept).




- Fast travel catalog merged from Map0/4/6: 684 â 820 stations, including Harp_P DLC. Existing Cowbell/Tuba rows kept where this export had no map table.




- IO catalog gained `IO_VendingMachine_Legend_A`. Mob Char_* aliases in NCS already pointed at catalog actors.









## 3.6.92 - Spawn All Filtered lands in shape; ground height 30









- Spawn All Filtered uses the same pin-into-shape path, at the Drop-near player (party), 1 item per tick so it hitch less.




- Ground height default is 30 (was -40). Result text says ground_drop / shape, not "used dump".




- Party player field is labeled Party player.









## 3.6.91 - Dump spit is zeroed and pinned onto shape slots









- Dump still has to spawn in front, then the next tick uses the same TeleportTo + physics pin as Loot Shapes Arrange so they stay in the square/heart instead of flying off.




- Drop All Shinies note: finished the story â start a new game in UVHM and spawning should work. Mail/rewards are not a spawn fallback.




- Setup / update banners are cyan-violet instead of yellow.









## 3.6.90 - Dump catch is nearby-newest only; no PlayerTick scan









- Drop All Shinies / Spawn All Filtered no longer find_all the whole world every PlayerTick (that was the spawn-run hitch).




- Dump still spits in front ("used dump"); next shiny tick teleports the newest nearby actors onto the selected shape / drop-from-above silhouette.




- Line length is Arrange-only again. Setup collapses once when Online (Setup button to reopen).









## 3.6.88 - Dump shinies land in the shape again









- Dump spawn still ignores transform (spit in front/above). Catch now teleports *new* OakInventoryPickup / OakPickup actors onto silhouette slots next tick, then gravity.




- Spawn All / Drop All Shinies no longer run Place Fully's GetMaterial gather every tick (that was the hitch). One light find_all per spawn tick; empty scans do not re-arm forever.









## 3.6.87 - Spawn catch uses Place Fully's pickup list









- Dump shiny/filtered loot is OakInventoryPickup. Shape catch only scanned InventoryPickup, so Place Fully worked on already-dropped items but spawn never shaped.




- Catch now uses the same Gear gather as the Shapes page. Per-dump find_all removed (that was the Spawn All hitch).









## 3.6.86 - Shape + drop combos; dump OakPickup; random spit off









- Dump loot is OakPickup, so shape catch never saw it. Catch now scans OakPickup + InventoryPickup.




- Shape and drop work alone or together: both = silhouette in the sky, then fall onto the slots.




- Random spit defaults off (it was throwing dump loot out of the shape). Spawn All no longer find_all-scans after every dump.









## 3.6.85 - Dump spawns honor shape and drop









- Dump-fill (inv handle / serial) was spawning at feet and skipping Land in shape / Drop from above. After dump, new pickups are caught onto the selected shape and drop mode.




- Pickup scan cache no longer hides items spawned on the same tick.









## 3.6.84 - Snap falls from height into the shape









- Snap + Drop height now spawns above each shape slot (heart/circle/etc) and lets gravity drop. none stays on the ground.




- Each spawn consumes the next slot so items are not stacked on point 0 (that is why heart looked like a pile).









## 3.6.83 - No tick-teleport after overhead spawn









- UE crash `EXCEPTION_ACCESS_VIOLATION 0xffffffffffffffff` was pyunrealsdk TeleportTo on stale InventoryPickup wrappers after Spawn All (Python `id()` reset every find_all, so every pickup got teleported every tick).




- Drop-from-above now places once at the mode start (rain/fountain/spiral hang in the sky, then gravity drops). No per-tick move/pin of held UObjects.









## 3.6.82 - Shape drop AV + enable line









- Drop animation no longer calls SetActorLocation* with SweepHitResult=None (that native AV). Teleport-only, and physics only on the pickup primitive.




- Enable log is the real first-use line again (not the old "no BLImGui hook" leftover).









## 3.6.81 - Spawn All less hitchy; dump shinies that NCS skipped









- Spawn All / Drop All Shinies no longer find_all every item. Catch runs once per tick; in-air teleports are budgeted so rain/fountain still play without melting the frame.




- *_shiny pools use the NCS dump inv_handle (or dump @U serial) instead of treating a silent-empty NCS RPC as a spawn.









## 3.6.80 - Drop modes actually differ; pin slots









- Rain / fountain / spiral / stagger freeze the pickup on the first catch frame and fly their own paths (no gravity yank that made every mode look like snap).




- Items stay pinned in the silhouette after landing so they don't bounce out of the shape.









## 3.6.79 - Loot tab shape + drop modes









- Loot Pool Spawner (Spawn selected / Spawn all filtered) has the same Land in shape and Drop from above options as Shinies and Shapes.




- Shape on disables random spit so items land on the silhouette; rain/fountain/spiral/stagger animate in. none stays feet/spit.









## 3.6.78 - Restore Spawn All fallbacks; hide Start here when ready









- Spawn All Filtered uses the full chain again (NCS â native â BL4 â serial â merge). 3.6.77 wrongly treated an NCS RPC as done and skipped the rest. Bulk still skips the hitchy find_all scan between items.




- Start here / first-use card only shows when the game is not Online yet.









## 3.6.77 - First-run copy, live drop modes, toggles, Spawn All









- Start here is setup-only (install â restart â load character â Online). Points at GitHub and scooterstoolbox.com â no GZO.




- Shape drop modes keep physics frozen in the air so rain / fountain / spiral / stagger actually play instead of snapping into the slots.




- Keybinds: one Toggle each for force fly, infinite jump, no-target, freecam (old ON/OFF ids still map).




- Spawn All Filtered: dump bulk NCS, no per-item find_all scan (that was the hitch). Empty pools still stay empty.









## 3.6.76 - Visible first-run Start here









- Home tab opens with a **Start here** block (numbered steps) instead of a tiny GZO hint.




- In-game Home dashboard lead-in is the same: pick target, be in-world, then Most used.




- EXE (needs rebuild for this part): Setup no longer hides just because Steam was auto-detected; a yellow **Start here** card stays up until the game is Online.









## 3.6.75 - Firehawk / vault shapes + line length









- Vault shape is the real symbol: ring + inverted rounded V (feet at 4 and 8 o'clock). Firehawk is Lilith's phoenix silhouette (beak left, jagged wings up, three-point tail down).




- Line / S / lightning / wave no longer grow with item count. **Line length** (default 900, 120â4000) caps how far they stretch.




- Drop modes: rain jitters XY and wobbles on the way down; fountain arcs from your feet; stagger still one-by-one. none/snap stay instant on the slots.




- Panel + in-game Shapes tab expose Line length. Live SDK â no EXE rebuild.









## 3.6.74 - Shapes parity + temp map fog hide









- Loot Shapes in-game tab now has drop-from-above, drop height, ground height, pile stack, and Stop drop (snap remaining items onto slots).




- Place Fully records @U serials again and keeps settle/drop height on Re-apply (was defaulting to slow with empty serials).




- Most Used / SDU card: **Temp hide map fog** â session FogMesh hide only. Not an unlock; fog returns after reload.









## 3.6.73 - Remove map fog / FT unlock UI









- In-session fog unlock is not possible: FOD grids live in ``profile.sav`` (``gbx_discovery_pc.foddatas``) and the live FOD manager has no reflected fields. Fast-travel map icons need the same save/PoA graph.




- Removed Reveal/Unlock map buttons (panel, BLImGui, ULM Map tab), ``map_reveal.py``, and related console commands. Travel-to-map / stations stay.









## 3.6.72 - DiscoveredKey is AsLiveActor + AsMetaLocation









- Probe after 3.6.71: ``GbxDiscoveryDiscoveredKey`` members are ``AsMetaLocation`` and ``AsLiveActor``. Previous fill stuffed station names into the meta slot and left the live actor empty, so 3900 RPC writes still did nothing. Unlock now sets ``AsLiveActor`` to the station/location object and ``AsMetaLocation`` to the DLMD/FT id.









## 3.6.71 - DiscoveredKey struct + station discovery config









- ``sqbt_probe_discovery`` was missing from the mod command list (``ulm probe discovery`` worked).




- Probe types: ``InLocation`` is ``GbxDiscoveryDiscoveredKey``, ``InProximity`` is an enum, discovering player is ``GbxPlayerState``, PoA ident is an FName. Unlock now builds that struct, stamps ``OakDiscoveryLocationConfig`` territories ``bEverywhere`` (live station dump), and calls ``MakeActorDiscoverable(InActor, InLocationType, InComponentType)``.









## 3.6.70 - Discovery RPCs use real param names









- 3.6.69 logged the signatures: ``InLocation, InProximity`` / ``InDiscoveringPlayer`` / ``LocationMetadataIdent, DiscoverState``. Calls now pass those kwargs (proximity True, PoA state 2) plus ``MakeActorDiscoverable`` on the function library. Vault ``roles[]`` scanned for Discovery*.




- FOD manager live object has **no reflected fog fields** â fog bytes are native. Console ``sqbt_probe_discovery`` / ``ulm probe discovery`` lists instances to dump (not the class).









## 3.6.69 - Call native FOD functions + log RPC signatures









- Last reveal: **10 FOD objects / 0 setattr writes** â fog bytes are not reflected UProperties. Now walks Class.Children and calls fod/reveal/unfog functions (including FunctionLibrary CDO), and invokes discovery RPCs via UFunction param block.




- Status line includes live FOD function names + ``ServerDiscovery*`` param names so the next dump is useful. Queue capped (no 1699 dupes).









## 3.6.68 - FOD save grids + PoA fast travel (no mesh hide)









- Reveal no longer hides FogMesh. Fog is ``gbx_discovery_pc.foddatas`` (128x128 0xFF) on live ``GbxDiscoverySaveGameData`` / FOD manager / discovery progress roles.




- Fast travel queues safehouse/silo **PoA** ids (``DLMD_World_P_PoAActor_*``) plus live ``PoAActor`` / ``ServerReportDiscoveredPoAState``. Station lock writes ``2`` (Unlocked), not ``1``.




- Console: ``sqbt_probe_discovery`` / ``ulm probe discovery`` â dump live FOD/PoA field names. Stay in-world until the queue finishes, then reopen the map.









## 3.6.67 - Catalog FT handles + discovery bits









- Last run queued 877 FOD/location objects and **0 bit writes** â that only hid fog. Unlock now queues packaged ``World_P.FT_*`` catalog ids as ``FGameDataHandle(24576, â¦)`` (same ids as ``gbx.servertraveltostation``) and fills ``DiscoveryReplicatedBitArray.BitField`` in place (challenge-style). GameState comes from ``GameViewport.World``.




- ULM (console only): ``ulm probe character`` / ``ulm probe vehicle``.









## 3.6.66 - Real map/FT unlock queue









- Reveal/Unlock now tick-drain live ``TravelStationObject`` / ``FastTravelStationObject`` / ``OakDiscoveryLocation`` objects with ``ServerDiscoveryMakeNonAuthoritativeDiscovery`` + ``ClientDiscoveryNotifyLocationDiscoveredStateChanged`` (dump PC RPCs). Not mesh-hide-only.




- 6 objects per PlayerTick so it does not freeze. Stay in-game until the queue finishes, then reopen the map.









## 3.6.65 - Sticky fog hide + stagger vs snap









- Map fog: Reveal keeps hiding FogMesh for the **whole session** (map close/open respawns the actor; tick hides the new one). Stopped destroying fog (that forced a fresh FogTexture). Also probes ``GbxDiscoveryFOD*`` / ``GbxDiscoverySaveGameData`` / discovery function libraries. Reload still uses save fog.




- **snap** = instant on slots. **stagger** = one-by-one from above (~0.28s apart). Rain/slow no longer share that delay.









## 3.6.64 - Shape none + settle crash + fog ticks









- Shapes tab: ``settle`` was assigned only inside the ``stack_height`` except block (``UnboundLocalError``). Place Fully / Quick Arrange work again.




- Drop All Shinies **Land in shape** now includes **none** (pile at feet, no silhouette). Drop-from-above **none** still means no overhead float.




- Map fog: Reveal arms an 18s PlayerTick loop that keeps ``SetHiddenInGame`` on live ``OakMapViewerFog`` (mesh only exists with the map open). Dump ``UnfogData`` / ``GbxFogDensityMultiplier`` stamped. Do not destroy ``OakMapViewer``.




- Fast travel still stamps station defs + lock status; open the map while Reveal/Unlock is ticking.




- Desktop portable **1.0.82** (SDK-only; EXE rebuild optional â panel comes from the game).









## 3.6.63 - Fog CDO + spawn at shape slots









- Map fog: also stamp ``Default__OakMapViewerFog`` (dump CDO) and scale FogMesh to 0. Open the map, then Reveal â live fog only exists while the map is open.




- Drop All Shinies now NCS-spawns on the shape slot XY (was always index 0 / one pile). Pickup catch also scans OakInventoryPickup.









## 3.6.62 - No shiny unlock, map fog from dump, fly icon









- Drop All Shinies no longer tries to unlock cosmetics. Use an edited save; legendaries without phosphene means the save is not gated-open.




- Map fog: hide live ``OakMapViewerFog`` FogMesh/FogRoot (dump 2026-08-11). Do not dump-all that *class* (CDO crash).




- EXE Force fly / Infinite jump toggles use the mobility icon (were broken ``<img src="â">``).




- Desktop portable **1.0.81**.









## 3.6.61 - Paced shiny unlock (no freeze)









- Unlock-all no longer brute-forces ``ClientUnlockUnlockable`` for every token on one frame (that froze the game, especially after a dump).




- ``sqbt_probe_shiny`` / Map **Unlock shiny** queues 2 cosmetics per tick. No ``find_all``.




- Drop All Shinies skips world phosphene scans (dump ``find_all`` hitch) and does not burst-unlock 80 tokens first.




- ``sqbt_probe_shiny`` is registered in ``build_mod(commands=â¦)``.









## 3.6.60 - Shiny unlock bypass, ULM Map tab









- Drop All Shinies now unlocks ``Unlockable_Weapons.Shiny_*`` first (story-complete gate bypass), then phosphene-stamps nearby drops, then serial-ground if the pool was empty.




- ULM F4 **Map** tab: fog / fast travel / safehouses (same experimental writers as SQBT).




- ``sqbt_probe_shiny`` / ``sqbt_discover_safehouses`` console probes.




- Desktop portable **1.0.80** (local only).









## 3.6.59 - Max All no fly, spawn-all bar, normal drops









- MAX ALL no longer turns on Force Fly / infinite jump.




- Spawn All Filtered uses the same sticky progress bar as challenges (ok/fail counts).




- Drop-from-above adds **none** / **normal** (land in the shape with no animation).




- Spawn transform writes a Quat for Rotation (ULM/dump) so NCS is less likely to ignore XY.




- Desktop portable **1.0.79** (local only).









## 3.6.58 - Shape + drop combos, crash-hardened ticks









- Land-in-shape (where) and drop-from-above (how) now share one path: every combo (circle/spiral/type piles/â¦ Ã slow/fast/fountain/rain/â¦) ends on the shape slot.




- Type piles / rarity lanes classify live shiny drops into those groups instead of a generic ring.




- Crash harden: no SweepHitResult=None teleports, one PlayerTick hook, deferred lifts, thinner pickup scans.




- Desktop portable **1.0.78** (local only).









## 3.6.57 - Drop styles, grounded type piles, lighter spawn-all









- Drop options: slow / medium / fast / spiral / rain / fountain / stagger / snap. Fast now holds in the slot instead of bouncing out. Shapes Arrange uses the same drop-from-above list.




- Type piles stay on the ground (stack height default 0). Raise stack height only if you want a tower.




- Spawn All hitch: skip dump-scan verify on anonymous pools; fewer loot find_all classes.




- Map/FT: stamp GbxLevelStationDef lock fields from dump + discovery-location notify (still no PoA).




- Desktop portable **1.0.77** (local only).









## 3.6.56 - Matching icons, landing drops, type piles, map probe









- Action/tab icons no longer use Vault Hunter portraits (Harlowe etc.) on random buttons â those stay in the top VH strip; buttons use function SVGs/PNGs.




- Shiny overhead drop actually lerps down into the shape (tick was missing so they froze in the air). Drop height is a field.




- Type piles: one stack per gear class in a row; Ground height + Pile stack height sliders.




- Map fog/FT: dump-backed DiscoveryReplicatedBitArray fill + region RPCs + current-world station unlocks (still no PoA mission RPCs).




- Spawn All Filtered no longer pauses the whole queue on every pearl verify.




- Desktop portable **1.0.76** (local only).









## 3.6.55 - PNG icons, overhead shiny drop, spawn-all serials









- EXE tab/action icons use the original `assets/bl4/*.png` set from Portable v1.0.69 (not emoji).




- Drop-all-shiny: spawn overhead, then lerp down into the selected shape (slow / fast / spiral). NCS zigzag is teleported into slots.




- Spawn All Filtered: dump `@U` serial fallback runs during bulk (was skipped), wider loot scan, more NCS-store retries.




- Map reveal no longer stamps discovery/PoA or runs `gbx.DiscoverAll` (that was retargeting the first-mission marker).




- Desktop portable **1.0.75** (local only).









## 3.6.54 - Spawn cancel, tight spit, fly, shiny shapes









- Spawn All random spit stays in a small ring (was a huge growing circle). Bulk non-pearls no longer false-FAIL from feet-verify.




- **Stop spawn list** cancels the running queue (EXE + BLImGui + `sqbt_spawn_cancel`).




- Map reveal now probes GbxDiscovery / PoA / GameState from the ULM dump (still experimental).




- Force Fly no longer re-applies cheat-fly every tick (that was the judder). Most used + MAX ALL turn on infinite jump + fly.




- EXE icons restored to custom SVG (not emoji placeholders).




- Drop all shinies can land in a loot shape: instant, float, or spiral.




- Desktop portable **1.0.74** (local only).









## 3.6.53 - Map fog / fast travel on the EXE









- World â Fast travel: Reveal map fog, Unlock fast travel, Reveal map + unlock travel (experimental).




- EXE-installed SDK still has no BLImGui panel â use the app buttons or console `sqbt_reveal_map`.




- Desktop portable **1.0.73** (local only).









## 3.6.52 - Spawn pace, map unlock, setup pin, loot sort









- EXE **Install / update** no longer flicks back to Home (setup stays open until you dismiss it).




- Spawn All Filtered: delay, items-per-tick, and **spit random directions** (yes/no; no = feet pile).




- Map fog + fast travel: BLImGui buttons and `sqbt_reveal_map` / `sqbt_unlock_fast_travel` / `sqbt_unlock_map` (not in EXE yet).




- EXE tab/action icons are emoji (broken PNG paths removed).




- Include ammo/cash piles is a yes/no select (not a truthy `"false"` checkbox).




- Type piles / rarity lanes classify from balance ids (`jak_ar`, `comp_05`, â¦); per-shape radius/spacing tuning kept.




- Desktop portable **1.0.72** (local only).









## 3.6.51 - Full loot-shape set + portable build script









- Added shapes: circle, double ring, filled star, Firehawk, square, rows/inventory wall, arc, fan, X, infinity, figure-8, wave, lightning, Vault logo, Psycho mask, BL initials, pyramid, hexagon, honeycomb, random scatter, Poisson scatter, rarity lanes.




- Portable build script (`build_squ1ggs_boosting_tools_app.ps1`) closes a running EXE, stages the mod with robocopy, skips code-signing discovery, and writes both `win-unpacked` and the zip.




- Desktop portable **1.0.71** (local only).









## 3.6.50 - Loot shape polish + toggle UX + spawn reliability









- Letter **S** is a continuous sine stroke (no more two disconnected halves).




- **Type piles** classify from name/path/materials/serial (AR/SMG/shotgun/sniper/pistol/heavy/shield/grenade/classmod/repkit).




- Extra shapes: spiral, cross, diamond, circle, arrow, smiley.




- NPC spawn-anchor `find_all` cached (~1.3s) to cut hitching when dropping near NPCs.




- Drop-all-filtered: more verify attempts + stronger ULM dump/@U / BL4 fallbacks.




- Force Fly OFF restores walk gravity in one click (no poisoned GravityScale snapshot).




- EXE/BLImGui: paired ON/OFF actions collapsed into single color/icon toggle buttons.




- Desktop portable **1.0.70** (local only; no GitHub push).









## 3.6.49 - Loot Shapes tab + late-joiner placement









- New **Loot Shapes** tab (EXE + in-game): rings, star, letter S, heart, line, grid, type piles.




- **Place Fully** (default) tries @U respawn at shaped spots so late joiners can see the layout; **Quick Arrange** teleports only.




- Soft clear + re-apply last layout; party-join watch re-applies tracked serials after a short delay.




- No GitHub publish in this drop (local portable only).









## 3.6.48 - All-players targeting + Tobgun thanks









- EXE Boost target dropdown is the source of truth when stamping `player_index`




  (MAX ALL / cash / XP / SDU and related boosts honor **All players**).




- All-players expands via live roster indices (PlayerArray fallback); `player_index`




  accepts `"all"`; shinies mail / god-mode style actions loop every lobby member.




- Spawn BMS no longer clamps All (â1) to party seat 0.




- Desktop default install path prefers




  `C:\Program Files (x86)\Steam\steamapps\common\Borderlands 4` (unless the user




  saved a different folder).




- Thanks line updated; thank you to **Tobgun** for




  feedback, ideas, testing, and bug reports.




- Mod / package versions aligned for the next GitHub desktop release (**1.0.66**).









## 3.6.43 - Vault Card 4 in currency / XP dropdowns









- EXE Resources / experience dropdowns include `vaultcard_4` and `vaultcard_xp_4`




  (Desert Dreams / VaultCard04_Tokens + ExperienceState[5]).




- Currency aliases, max-all vault fallbacks, and vault-card catalog defaults cover




  card 4 alongside 1â3.









## 3.6.42 - Roster cleanup + Keybinds tab + faster GZO load









- Party roster drops empty / placeholder `Player N` PlayerArray stubs so solo




  hosts no longer see fake Player 1â3 rows; rows now include `is_host`.




- New EXE **Keybinds** tab: 12 custom slots (action dropdown + key capture/edit),




  persisted and registered as in-game `SQBT Custom 1â12` binds.




- GZO catalog keeps an in-memory parse cache; dump writes compact JSON to reduce




  hitch when Refresh GZO finishes.









## 3.6.41 - EXE boost-target ship hardening









- Live `get_target_player_index()` getter (fixes stale import-by-value of the




  boost target int in extended bridge actions).




- Home âReward shinies â targetâ now mails the selected boost target(s), not




  always PlayerArray[0].




- EXE only stamps `player_index` when the action did not already set one; never




  stamps All (â1) onto kick / teleport / UVHM start.




- Kick / teleport / UVHM start reject All-players; inventory All expands to




  whole lobby; empty-string `player_index` parsed safely.









## 3.6.40 - Home boost target + MAX ALL level 60









- EXE stamps the selected boost-target `player_index` on Home cash / eridium /




  MAX ALL / level / SDU (and other player-scoped boosts) so a pending roster




  click is not lost to a stale host default.




- MAX ALL applies player 60 / spec 701 **after** vault writes, with BP




  readback retries so character level does not settle short (e.g. 50).




- Home Max cash / Max eridium use full int32 wallet max (`2147483647`).









## 3.6.37 - Visible first-use install / restart notices (EXE)









- Desktop app Setup callout + post-install message use high-visibility colours so




  **Install / update mod folder** and **fully restart Borderlands 4** are hard to miss.




- README thanks kept for GZO catalog.









## 3.6.36 - One Maurice's Black Market list row









- Dump shows the working vendor is ``IO_VendingMachine_BlackMarket``; Legend /




  Maurice was a confusing duplicate of the same machine.




- EXE/World Props now show a single **Maurice's Black Market Machine** entry




  (Legend_Legendary hidden; aliases still resolve to Black Market).









## 3.6.35 - Blank Maurice / Black Market first-try wake









- unrealsdk log showed dual retry using actor-def cache â blank OakSpawner shells;




  IO / PersistentLevel spawns skip that cache now.




- After settle, prefer relocating the live ``PersistentLevel.IO_*`` once it has




  scripts, plus delayed wake passes (same effect as spawning another IO nearby).




- EXE World IO section notes the blank-machine workaround if settle is slow.









## 3.6.34 - IO spawn hitch / Maurice freeze fix









- Maurice / Black Market dual no longer blocks PlayerTick: async ``oak_spawnai``




  + settle ticks + ``find_object`` world pass (no ``find_all(OakInteractiveObject)``).




- World IO template lookup prefers exact PersistentLevel ``find_object``; skips




  broad interactive/Actor scans that froze the game.




- Catalog no longer forces every vending row onto the heavy world-path spawn.









## 3.6.33 - Black Market / Maurice via SQBT oak dual (no ASD)









- EXE/SQBT no longer call ActorScriptDeployer. Black Market and Maurice use




  embedded Oak Spawner only: ``oak_spawnai`` â settle â




  ``oak_spawn PersistentLevel.IO_*`` via ``OakInteractiveObject`` (same




  two-step shape as the working console flow).




- Still one dropdown row each for Black Market and Maurice.









## 3.6.32 - EXE Black Market / Maurice via proven ASD dual









- EXE/World Props show exactly one **Black Market Machine** and one




  **Maurice's Vending Machine** row (Legend A hidden).




- Both run the working console flow automatically:




  ``asd_spawnai`` â settle â ``ASD_spawn PersistentLevel.IO_*``.




- Requires ActorScriptDeployer enabled (same mod as your manual commands).









## 3.6.31 - Maurice / vending live relocate path









- There are no separate thin-air packages/files for Maurice or Black Market â




  they only exist as world-placed ``OakVendingMachine`` actors in map chunks.




- Maurice dropdown rows now use ``oak_spawn`` (live template), same as Black Market.




- If a deferred duplicate lands with ``scripts=0``, SQBT relocates the live




  world machine in front of you so it is actually usable.









## 3.6.30 - Black Market live OakVendingMachine spawn









- WhatAmILookingAt dump: real machines are ``OakVendingMachine`` in a




  ``World_P/_Generated_/â¦`` PersistentLevel (UAID), not a thin-air actor-def.




- Black Market dropdown now uses ``oak_spawn`` template duplication (same idea as




  bank/lost loot), not ``oak_spawnai``.




- Added ``OakVendingMachine`` to the class scan / Black Market aliases.









## 3.6.29 - Black Market one-click dual spawn









- World Props dropdown shows a single **Black Market Machine** row that runs




  ``oak_spawnai`` then a PersistentLevel ``oak_spawn`` unlock pass automatically




  (same two-step flow as the old ASD console commands).




- Dual machines no longer use async-fire for step 1 (that skipped package loads




  and left no live template for the world pass).




- Added Black Market oak aliases, package loads, offline preset, and template




  caching from the just-spawned actor.









## 3.6.28 - Vault of the Damned catalog + console rewards notice









- Merged missing Vault of the Damned / Cowbell challenge tokens from the NCS




  dump into ``challenge_catalog.json`` so All non-UVHM covers DLC achievements,




  spooky stories, kickdowns, and related rows.




- Added a dedicated **Vault of the Damned** category and expanded Combat /




  Enemies / Character filters to include Cowbell-prefixed challenges.




- Challenges menu shows a short notice: console players opening 600+ rewards in




  multiplayer can crash â open rewards in single player instead.









## 3.6.27 - Remote challenge UI path (COS)









- Challenge bulk for lobby guests now writes ``PlayerState.ChallengeObjectiveStates``




  (what the Challenges UI actually reads), not only numeric library/RPC calls that




  often false-OK on remote/console clients.




- Refuses to apply when the resolved PlayerController does not match the selected




  lobby identity (prevents silently boosting the host).




- Desktop EXE always sends the boost-target ``player_index`` with challenge/UVHM




  start so a stale host default cannot override the dropdown.




- Challenge apply logs the resolved player name/controller into unrealsdk.log.









## 3.6.26 - Challenge target + boost dropdown fixes









- Challenge unlocks for a selected non-host player no longer fall back onto the




  host. Uses the proven ``IncrementChallengeForPlayer(TargetPC, TargetPC, Handle, Amount)``




  path and never substitutes the local controller when another target was chosen.




- All-players bulk completion falls through to per-player increments when the




  lobby-wide library call is missing or fails, instead of only bumping the host.




- Desktop boost-target dropdown keeps the chosen player through status polls




  (optimistic selection + no mid-click option rebuild).









## 3.6.24 - Maurice vending crash-safe dual spawn









- Maurice's legendary vending (and similar locked machines) now run




  ``oak_spawnai`` first, wait a couple of ticks, then the PersistentLevel




  ``oak_spawn`` world pass second â automatically from one catalog pick.




- Users only see a single machine row; the follow-up command is hidden.




- IO activation and world template spawns are crash-guarded: failures return a




  status message instead of hard-crashing Borderlands 4.




- Catalog labels Maurice's machine clearly.









## 3.6.23 - Serial delivery and mob budget hotfix









- Fixed desktop serial delivery being blocked when an optional level rewrite




  encountered a newer item serial layout.




- Level overrides now run only when explicitly enabled. Unsupported layouts




  keep and deliver the original valid serial with a visible warning.




- Reapply and verify the active map's disabled AI spawn budget before each mob




  request, preventing valid spawns from stopping around 20 live actors.




- Aligned catalog and backend mob-count handling with the UI's 999 maximum.









## 3.6.22 - Periodic stutter cleanup









- Cached inventory settings in memory and reduced automatic capacity checks to




  once every five seconds instead of rereading JSON from disk every second.




- Reduced bridge status snapshots to once every five seconds and removed




  repeated `find_all` scans while freecam is inactive.




- Prefer the live local controller directly for debug-camera status, reserving




  global controller scans for an explicitly requested freecam fallback.




- Local test setup: disabled the unrelated `bot_suite` session timer, whose four




  tick hooks and 2â3 second diagnostic cadence matched the reported hitch.









## 3.6.21 - Release cleanup and runtime stability









- Removed the bridge's redundant controller/viewport hooks and reused SQBT's




  single proven mobility runtime tick, eliminating up to eight duplicate bridge




  callbacks per frame.




- Consolidated serial delivery, UVHM, challenges, shiny delivery, bridge work,




  and deferred actions onto that same UMG dispatcher instead of stacking




  additional always-on UMG/PlayerTick hooks.




- Restored single ownership of Loot Pool Spawn All queue draining; the bridge no




  longer advances the queue in parallel with its deferred worker.




- Made Spawn All use SQBT's bundled deferred queue, removing the undeclared




  `bl4_world_tools` runtime dependency.




- Reduced idle status refresh and inventory auto-apply polling frequency to keep




  the desktop bridge responsive without constant game-thread work.




- Limited desktop bursts to two game-thread actions per frame, throttled force




  fly maintenance to 10 Hz, and reduced repeated loot/sticky-combat scans.




- Fixed the embedded Mob Spawner catalog picker to use its bundled catalog,




  added friendly labels for all NCS-discovered actor rows, and cleaned malformed




  actor labels.




- Added guarded freecam inspect, damage, and DestroyTarget actions without




  exposing destructive DestroyAll operations.




- Added local player/pawn fallbacks for embedded BMS aggro and spawn anchoring




  when `gbx_actor_deploy` is not installed.









Release note: SQBT does not install a pause-menu or BLImGui tab. Disable separate




Mob/Oak/Item Spawner mods when using SQBT to avoid duplicate Mod Menu tabs and




runtime hooks.









## 3.6.19 - Bridge drain on proven existing runtime tick









- Reused SQBT's already-installed mobility/runtime UMG tick to refresh desktop status and drain actions; the dump proves this callback runs because it successfully applied inventory settings after the character loaded.




- This adds no BLImGui window, keybind, or additional pause-menu hook; it only shares the existing runtime callback.









## 3.6.18 - Dump-confirmed live bridge tick









- Switched the bridge drain to the `ReceiveTick` and GbxGame viewport paths that ULM's live hook probe reports as supported on this BL4 build; the previously selected PlayerTick paths existed but did not dispatch.




- Added bridge tick heartbeat diagnostics and a safe manual refresh when `sqbt_bridge` is run from the console.




- Removed a duplicated `sqbt_bridge` command registration.









## 3.6.17 - Reliable desktop connection status









- Register all viable gameplay controller and viewport ticks so the bridge cannot select an existing-but-inactive controller class and remain stuck on âenter a saveâ.




- Coalesce overlapping tick callbacks within the same frame, keeping actions and bulk loot work single-drained without restoring the pause-menu UI hook.




- Added visible GZO catalog attribution.









## 3.6.16 - Desktop-only UI and honest Shiny eligibility









- Removed the optional SQBT BLImGui panel/keybind and the bridge's pause-menu UI tick; the EXE and lightweight SDK commands remain.




- Removed duplicate Mob/IO queue draining from the bridge because the embedded spawner already owns a lazy PlayerTick hook.




- Shiny batch results now report completed pool calls instead of claiming the resulting items are Shiny; final rarity is save/character unlock-gated.




- Added visible Shiny unlock guidance with a clickable Scooter's Toolbox link, renamed the mail controls to Reward all shinies, and labeled the Discord community ScootersGarage.









## 3.6.15 - Visible standalone pending-rewards action









- Promoted **Open pending rewards (everyone)** to the first button in Most Used with a clear gift icon and tooltip.




- The action discovers reward managers directly from Squ1ggs Boosting Tools' live party controllers, with a UObject-scan fallback; it does not import, call, or require Ultra Local Menu.




- Added a package-by-package fallback when the direct open-all reward RPC is unavailable.









## 3.6.14 - Exact Gomie route and delay-free verified batches









- Gomie and the other patch-only inline inventory definitions now bypass the broad Pearl route and use their exact exported definitions first.




- Loot-pool results are only accepted when a physical pickup is observed; silent backend returns continue through fast tick-based fallbacks and are logged as failures when nothing appears.




- Removed the fixed spawn gap, two-second batch breathers, and Pearl unverified burst mode while retaining one-at-a-time attribution on the shared game tick.




- Spawn All clearly reports one verification drop per filtered pool instead of echoing the selected quantity.









## 3.6.13 - Smooth desktop queue drain and clean folder release









- The desktop bridge now retains its request-facing UI hook and also installs a continuous gameplay PlayerTick drain, removing multi-second gaps between queued loot, mob, AI, boss, and IO actions.




- Selected loot-pool requests reject a duplicate while the same pool is already queued or being verified; different pools can still be queued deliberately.




- Ground-loot verification scans newest `OakPickup` objects first, preventing busy worlds from exhausting the scan cap on old inventory objects and falsely logging visible drops as silent-empty failures.




- Appended selected-pool rows now update the batch total correctly in trace checkpoints.




- Removed a stale nested v3.6.7 folder copy and generated runtime artifacts from the folder distribution.









## 3.5.88 - Verify named Pearl pools across loaded config layers









- Exact Pearl supplements no longer inherit the fast batch's unverified-success shortcut.




- Missing itempool8/DLC names probe every distinct loaded item-pool config layer, with two short observation ticks per layer, and stop on the first observed ground pickup.




- Existing nearby loot is included in the before-snapshot so an earlier Pearl cannot falsely verify the next named spawn.




- Raiden's exported inline inventory comp now falls back to reflected/wrapped runtime script structs when this SDK build cannot resolve selection structs by short name.




- Decoded the current patch `_NCS` records: Handcannon, Eigenburst, Conflux, Jail-Broken, and Gomie are inline `ItemPoolList` inventory definitions, not standalone pools in the patch itempool store. Exact comp spawning now also uses `SpawnLootFromDef_Drop` to bypass that missing registration.




- Added Pool Spawner rows and exact inline definitions for six patch-only items missing from the previous catalog: Burrow, BloodIron, Kaos, Verce, Loiter, and Hydrowerks.




- Ground-only inline and serial routes remain last resorts; Reward Center delivery is not used.









## 3.5.87 - Exact fallback for Pearls omitted by type pools









- Type-pool requests keep the working native random rolls and reserve results for the eight names those pools omit.




- Missing names now fall back to a verified exact Reward Center package when no ground route exists; logs label this as inbox delivery and never claim a ground pickup was observed.




- Exact fallback packages wait for replication, open only their newly created package, and confirm an occupied backpack slot changed before logging delivery; unrelated reward mail is left untouched.




- Removed Unverified/Fail health labels and the failure filter from the Item Pool GUI; full results remain in the spawn logs.




- Fixed the Item Pool panel draw loop referencing removed `health` variables, which caused a repeated `NameError` every frame.




- Spawn JSONL now distinguishes ground and backpack delivery and records the asynchronous exact-package result instead of treating a returned open call as success.




- Restored the fresh itempool8 ground pools for Handcannon, Crazed Earl, Soul Survivor, Crow-Sourced, Eigenburst, and Conflux; Jail-Broken uses its registered shiny pool and Raiden uses its exported inventory comp.




- Pearl Pool spawning no longer substitutes Reward Center delivery when a physical ground route fails.




- Added a Hotfix-9 Raiden serial and stopped treating accepted-but-unregistered console commands as successful spawns.









## 3.5.86 - Type pools spawn all 15 user pearlescents via dump









- PS/SG/SM/SR/AR Pearl Pool rows list every weapon in that pool (Herald, Constable, Abyss, â¦).




- Count â¥ pool size spawns **one of each** pearlescent for that weapon type (e.g. count 3 on SR = Abyss + Conflux + Solar Temper).




- Per-weapon dump path: merge inline â @U serial â verified named NCS pools â full fallbacks.









## 3.5.85 - Generic pearl pools (PS/SG/SM/SR/AR) dump expansion









- **SG/PS/SM/SR/AR Pearl Pool** buttons use BL4 dump expansion into named pearl pools (no raw generic NCS â that path silent-empties or freezes).




- Local fallback: verified roll on each child's live `itempool_*_06_pearl_*` pool, then merge/BL4 per weapon.




- Count > 1 cycles through all pearls for that weapon type (same as dump catalog).




- Removed Spawn All batch delay (back to 0.25s tick).









## 3.5.84 - Spawn All spread + weapon-only verify









- Pearl batch spawns spread in a ring around you (no more 17 guns stacking in one spot / despawning).




- Feet verify scans **weapons/pickups only** â stops false OK from random OakActor noise.




- Dump order: merge inline â verified NCS â shiny â BL4 (deferred verify) â serial.




- Spawn All pace slowed to ~1.45s per pearl so each drop can land before the next.









## 3.5.83 - Pearls: dump-first spawn, honest feet-loot verify









- Named pearls use **BL4 Item Spawner â verified NCS â merge inline â shiny â serial** (dump order).




- **No more false OKs**: pearl rows only log OK when loot appears at your feet (serial/NCS RPC success is not enough).




- Verify queue retries BL4 + merge inline when a path silent-empties.




- Generic pearl pools also defer to feet verify instead of trusting NCS RPC.









## 3.5.82 - DLC/Raid2 pearls: serial-first + shiny unlock









- comp_06 (Herald, Constable, Juliet, â¦) and pearl_world (Abyss, Gomie, Solar Temper, â¦) now spawn via **@U bookmark serial first** â full Raid2/DLC builds instead of bare NCS pool rolls.




- Pre-unlocks shiny/phosphene cosmetics before Spawn All pearl batches and each DLC pearl spawn.




- After NCS fallback, applies phosphene customization on nearby loot (Sharkbait and other no-serial comp_06 try verified shiny pool next).









## 3.5.57 - Pearl merge-first + NCS data; freecam live-edit options









- Named pearls: merge inline before NCS (bl4 order); legacy NCS for all dump pools; pearl_world pools allowed.




- Added missing pearl shiny index rows (Locust/CrazedEarl/Jailbroken) for inline fallback.




- Freecam: cycle mode, distance, copy location, EXE status bar â from live-edit OakPlayerController dump.









## 3.5.56 - Pearl spawn: stop fake *_shiny OK, honest routing









- Fixed false OK: no longer tries unregistered `{pool}_shiny` guesses (herald_shiny etc.).




- Only dump-proven shiny NCS pools skip feet-loot verify (Earl/Parasite/Soul/Jailbroken).




- Named pearls use simplified router: bl4 delegate â registered NCS â merge â @U.









## 3.5.55 - Pearl spawn: trust shiny NCS, dedupe rows, merge direct









- `*_shiny` NCS pools use legacy trust (same as generic type pools) â fixes false FAIL + double spawn.




- Shiny-primary catalogs (Earl/Parasite/Soul/Jailbroken) only try shiny pool, not pearl+shiny twice.




- Spawn All dedupes by `catalog_key` (Soul Survivor no longer drops x2).




- Merge inline trusts RPC success; extra inv handle casing; legacy NCS for all named pool tries.




- comp_06 (Herald, Constable, â¦) tries merge inline before NCS.









## 3.5.54 - Pearl spawn: shiny-first NCS + merge inline + ground @U fallback









- Named pearls try **shiny/alias NCS pools first** (Earl/Parasite/Soul Survivor pattern).




- Added shiny inline merge from `ncs_shiny_pools.json` when live pool silent-empties.




- Merge attach-before-drop; extended loot verify for merge/serial paths.




- **Ground @U serial** last resort (feet drop only) for world pearls and comp_06 when NCS+merge fail.




- Jailbroken alias â `mal_sg Jailbroken_shiny`; Soul Survivor alias â shiny pool first.









## 3.5.53 - Pearl OK/FAIL: loot-verified only (fixes false OK on silent-empty)









- Named Pearl rows log **OK only when loot appears at feet** (reverts 3.5.52 NCS-trust bypass).




- NCS named pools use `require_loot_verify` â silent-empty NCS calls are FAIL, not OK.




- Single Spawn queues off ImGui (same paced tick path as Spawn All) so loot scan is safe.




- Merge inline: selection-struct build order matches BL4 Item Spawner (fgbx ptr first).




- pool_health prefers `catalog_key`; bulk queue no longer duplicates pearl failure rows.









## 3.5.52 - Pearl named spawn: trust NCS like type pools + world-pearl fallbacks









- Removed feet-loot gate on named NCS pools (same trust as PS/SM/SG/SR/AR Pearl Pool buttons).




- World pearls (Abyss, Temper, Gomie, Raiden, Jailbroken): merge first, then BL4 inline,




  then ground @U serial last.




- comp_05/comp_06 named: NCS chain â merge â BL4 â ground @U.









## 3.5.51 - Pearl NCS try-order: comp_05 *_shiny fallbacks before merge









- Named pearls now test an **ordered pool chain** from game_data.json: dump alias,




  manifest pool, then comp_05 `*_shiny` / comp_06 `*_shiny` siblings (e.g. Soul Survivor




  pearl + shiny, Parasite Locust + Locust_shiny). One spawn attempt each, then merge drop.









## 3.5.50 - Pearl tab: pool drop only (no serial/mail/backpack)









- Named Pearl rows use **ground pool drop only**: NCS `SpawnInventoryFromItemPool`, then




  merge inline world drop. Removed @U serial / backpack / mail paths from pearl spawner.




- NCS pool pick trusts **game_data.json** registration (comp_06 named pools included).









## 3.5.49 - Named pearls: exact item only (no type-pool roulette)









- **Wrong item fix:** Removed type-pool fallback from named Pearl tab clicks (was rolling




  random SR/PS pearls â Solar Temper â Abyss, Soul Survivor â Herald).




- **Multi-spawn fix:** One NCS pool attempt per click (Crazed Earl no longer fires 4 pools).




- **Spawn order:** Backpack @U â merge inline â one dump NCS pool â ground @U.




- **False FAIL fix:** Disabled feet-only loot verify on Pearl tab (backpack/merge paths).




- **Dump merge:** Added Abyss, Solar Temper, Gomie, Raiden, Jailbroken to pearl_merge_pools.json.









## 3.5.48 - Exe parity + pearl spawn fixes (comp_05 pearls, Herald, fly off)









- **Pearls:** comp_05 legendary pearls (Handcannon, Conflux, Crow-Sourced, Soul Survivor,




  Eigenburst) route through serial-first `_spawn_catalog_named` instead of broken comp_06




  merge inline. `item_pools.json` `catalog_key` preserved. Herald/comp_06: native NCS first,




  backpack @U before merge inline. Soul Survivor native alias fixed (`*_pearl` not `*_shiny`).




- **Exe manifest:** Most used adds Drop all shinies + freecam toggle/OFF. UVHM rank picker




  is one shared field (no duplicate). Freecam toggle wired (`freecam_toggle`).




- **Force fly OFF:** always calls ClientCheatWalk + clears cheat fly/gravity even without




  a saved snapshot; still disables when target wasn't tracked.









## 3.5.47 - Pearl tab shows all tier/mixed pearl pools (category mismatch fix)









- **Root cause:** `PS/SG/SM/SR 06 Pearl` and the legendary pearl variants (Crazed Earl,




  Soul Survivor, Conflux, Crow-Sourced, Handcannon, Eigenburst) carry **weapon** categories




  in `item_pools.json` â the Pearl tab filter (`category == "Pearl"`) never matched them.




- **Fix:** Pearl tab now matches any pearl-tagged row (generic tiers, 06-pearl catalogs,




  `*_pearl` legendaries). Searching "pearl" in All shows the tier pools too.




- **Spawning:** Legendary pearl variants route through the pearl pipeline (serials accepted




  for non-06 catalogs); the row's own registered pool is now a loot-verified native candidate




  (fixes Crazed Earl-style rows). Tier pools spawn by expanding to named children.









## 3.5.46 - Pearls: bypass BL4 delegate, backpack @U last resort, tier pools visible









- **Your dump showed:** all 12 pearl rows OK via BL4 `native_store_api` but only Parasite




  dropped (both Locust-alias rows) â `native_store_api` never loot-verifies, and only the




  Locust pool actually rolls on plain native.




- **Fix:** Pearl rows (catalog / category / `*_06_pearl*` pool) never touch the BL4 delegate




  or plain native. They go straight to SQBT's pearl pipeline: ground @U serial â loot-verified




  generic type pool â loot-verified live native (Locust works here) â merge comp inline â




  **NEW: backpack @U serial last resort** (ground FromSerial is dead on this build).




- **Generic tiers:** `PS/SG/SM/SR 06 Pearl` parent rows show again under the Pearl tab (and




  spawn by expanding to their named children). Failures now log honestly instead of false OK.









## 3.5.45 - Pearls back on catalog pipeline; named classmod rows removed









- **Pearls:** 3.5.44's native-first fast path intercepted named pearl rows and logged false




  OKs (registered pearl pools silent-empty on plain native). Pearl rows (pool/catalog/category)




  are excluded from native-first everywhere and use the proven catalog/serial pipeline again.




- **Named classmods removed:** `> Artificer`, `> Bombastic`, `> Grim Sister`, `> Plasmaphile`,




  `> Prestidigitator` rows hidden from browse and Spawn All â no spawn path works for




  single-comp classmod synthetics on this build (`no selection struct`). Use the broad pools




  (`Class Mods 05 Legendary <VH>`, `Classmods Raid2`, â¦) which all spawn now.









## 3.5.44 - Registered NCS pools spawn native-first (restore classmods/pearls/mixed)









- **Root cause:** Every pool spawn â including `spawn_item_pool` itself â delegated to the




  BL4 Item Spawner pipeline first, which mis-routed classmod/mixed pools into inline merge




  (`no selection struct`) and reported false OKs (`ncs_synthetic` with nothing dropped).




- **Fix:** Pools present in `ncs_native_itempools.json` (504 live registered pools â all 27




  classmod pools, named pearls, zone/commander pools, weapons) now call




  `SpawnInventoryFromItemPool` **directly first**; BL4 pipeline is fallback only.




- **Guards kept:** Generic pearl criteria pools (`itempool_ps/sg/sm/sr/ar_06_pearl`) never




  hit native (freeze); generic `*_05_legendary` weapon pools keep the F1 expansion path.




- **Dedicated classmods** (Artificer, Bombastic, `*_05_legendary_01-06`): BL4 (loot-verified)




  â inline merge â loot-verified native â backpack @U serial. No more false OKs from the




  synthetic pool path.









## 3.5.43 - Class mod spawn: dedicated inline vs native roll split









- **Regression (3.5.42):** All classmod pools were forced through inline merge â broad pools




  (`itempool_class_mods_05_legendary_*`, commander zones, GoldSilver Raid2) failed with




  `no selection struct` / `no inv handle`.




- **Fix:** Only **dedicated** single-comp pools (`itempool_classmod_*_05_legendary_01-06`, â¦)




  use BL4 â inline merge â native â backpack serial. **Mixed/criteria** classmod pools use




  live NCS `SpawnInventoryFromItemPool` (random roll) â never inline merge.




- **Rebuild:** `classmod_merge_pools.json` filtered to dedicated synthetic pools only.









## 3.5.42 - Class mod legendary spawn: bundled merge inline (78 pools)









- **Root cause:** `@U` FromSerial ground path fails on this BL4 build; pool API silent-empty




  logged OK without dropping Artificer/Bombastic/etc.




- **Fix:** Extracted **78** classmod merge payloads â `classmod_merge_pools.json`; new




  `classmod_comp_spawn.py` uses Attach+Drop inline (same as pearls / Item Spawner merge).




- **Order:** Inline merge â @U ground â backpack serial for named Subjugator rows.




- **Broad pools** (`itempool_class_mods_05_legendary_*` without inline handles) still use




  live NCS pool API (random roll â by design).









## 3.5.41 - SQBT pool spawner: classmods + Spawn All filtered









- **Spawn All:** No longer hard-blocked at 20 â queues up to 80 filtered pools on paced UI




  ticks (Class Mod category cap 80). Truncates with a warning if the filter matches more.




- **Class mods:** Subjugator rows (Artificer, Bombastic, â¦) use bundled `@U` ground serial




  first â pool API rolls random pearl gear on `*_comp_05_legendary_06`.




- **Verify:** If Item Spawner reports OK but no loot at feet for class mod rows, falls through




  to bundled merge/native/serial paths (same stack as F3 Item Spawner).




- **Bulk queue:** Failed paced spawns now write FAIL rows to `spawn_test.jsonl`.









## 3.5.40 - Pearl @U ground fallback: multi-serial, no mail









- **Ground only:** Pearl serial fallback tries every bundled `@U` at your feet â never loyalty mail




  or backpack unless `BL4_IS_ALLOW_SERIAL_BACKUP=1` (Item Spawner opt-in only).




- **Multi-serial:** Primary + DLC alternates for Parasite/Locust, Crazed Earl, Soul Survivor;




  Lootlemon + NCS shiny rows auto-merge when names match.




- **Logging:** Success methods include `pearl_serial_ground_alt2` etc. when a backup serial works.









## 3.5.39 - Pool spawner: pearls less prominent in All browse









- **All tab:** Pearl-category rows and generic pearl tiers (SM/PS/SG/SR 06 Pearl) are hidden




  until you open the **Pearl** category or search "pearl".




- **Sort:** Any remaining pearl-tagged rows sink to the bottom of **All** instead of pinning




  under child `>` headers at the top.




- **Spawn logging:** Every pool spawn writes **OK/FAIL** to `Squ1ggsBoostingTools/logs/spawn_test.jsonl`




  with a live `spawn_test_summary.txt`. After **Spawn All**, run console **`sqbt_spawn_dump`**




  (or share the three files under `logs/`). **`sqbt_spawn_log_clear`** resets before a new test run.









## 3.5.38 - Pearl verify + Locust pool fix









- **False FAIL:** Loot verify marked spawns failed when items actually dropped at your feet




  (Parasite, Herald, comp_05 pearls). Native_store / generic pearl / `*_05_legendary_*_pearl`




  pools skip verify now; silent-empty retries merge inline Attach+Drop.




- **Locust/Parasite:** `native_pool` wrongly pointed at `*_Locust_shiny` â every Locust spawn




  tried the shiny pool (one UI row failed, other looked like wrong item). Fixed to live




  `itempool_vla_sm_06_pearl_Locust`. Shiny row hidden unless you search "shiny".




- **Note:** Locust and Parasite are the **same gun** (marketing names).









## 3.5.37 - Restore pearl ground spawn (native pool at feet, no mail)









- **Regression:** Named pearl rows (Herald, Constable, â¦) were routed through




  `_spawn_pearl_catalog_row` (serial â broken inline) instead of live NCS




  `SpawnInventoryFromItemPool` â your 00:21 log showed `native_store_api` working.




- **Fix:** Named pearl UI rows use the normal pool spawn path again. Generic pearl




  pools still expand to one random named child (never native on criteria pools).




- **No mail:** Pearl delivery never uses loyalty rewards; ground-only serial if any.




- **Inline:** Attach+Drop before Drop-only; sdkmain-style FGbxDefPtr selection struct.




- **Native inject:** `__native_store` merges into synthetic rows (keeps inv handles).









## 3.5.36 - Pearl mail fallback + generic native freeze fix









- **Your dump showed:** every pearl logged `serial: ground @U failed` and `inline: no selection struct`.




  Ground FromSerial RPCs are not available on this BL4 build; inline comp structs also fail.




- **Fix:** `deliver_pearl_serial_resilient` â ground @U â backpack @U â **loyalty mail** (SQBT




  path, always on for pearls, no env flag).




- **Bug fix:** `spawn_native_pool` had inverted logic that still called native API on generic pearl




  pools when `should_skip_native` was true â that caused freezes on PS/SG/SM/SR pool rows.




- **Named pearl native pools** (`itempool_tor_ps_06_pearl_herald`, etc.) allowed again as fallback




  after serial; only **generic** `itempool_*_06_pearl` blocked.









## 3.5.35 - Pearl spawn: @U serial first, block native pool API (fix freeze)









- **Root cause:** Generic pearl pools (`itempool_ps/sg/sm/sr_06_pearl`) are criteria-roll pools in




  NexusConfigStore. Calling `SpawnInventoryFromItemPool` on them **hard-freezes** the game. Named




  pearl pools mostly silent-empty on native. Only Crazed Earl appeared to work because it hit inline




  merge or a registered native pool first â comp_06 pearls were failing inline then trying native.




- **Fix:** ALL pearl-tier pools now skip native API entirely (`spawn_risk.is_pearl_tier_itempool`).




  Spawn order is **@U ground serial first** (Lootlemon codes), then merge `inv'â¦'` inline.




- **Serials added:** Crazed Earl, Soul Survivor, Conflux, Crow-Sourced, Eigenburst, Handcannon




  (comp_06 pearls Herald/Juliet/Constable/Screwstonian/Parasite were already present).




- **Data:** `pearl_merge_pools.json` copied into `bl4_item_spawner/data/reference/` (was SQBT-only).




- **NCS dump:** Run `bl4_item_spawner/tools/refresh_from_ncs.bat` â now also patches pearl inv




  handles from `NexusConfigStore_Dumps_v1.9.1` if that folder exists in Downloads.









## 3.5.34 - F3 keybind conflict + stale def-ptr cache retry









- **Root cause #1:** `bl4_player_movement` and `bl4_coop_session_tools` both also bind their




  panel toggle to plain `F3`, same as BL4 Item Spawner. All three fire on one keypress,




  which is why F3 needed pressing twice to reliably land on the Item Spawner tab.




- **Fix:** Rebound `bpm_open_menu` to `F9` and `bcst_open_menu` to `Ctrl+F9`. F3 is now




  BL4 Item Spawner only (Home still opens Nexus Discovery).




- **Root cause #2:** Named pearl inline spawns (`_build_selection_data_for_inv_handle`)




  cache a `ScriptStruct` ref for the item-def type once per session. The same handle




  (`vla_sm_comp_06_pearl_locust` / Parasite) spawned fine earlier in a session then




  failed later with "no selection struct" for no code-visible reason â consistent with




  that cached ref going stale (e.g. across a level transition) rather than the handle




  itself being wrong.




- **Fix:** On total failure to build a selection struct, drop the cached ref and retry




  once with a fresh lookup before giving up.




- **Freeze investigation:** Confirmed via a fresh `unrealsdk.log` that no spawn attempt in




  that session actually hung â both attempts logged completed with real errors, no




  native `SpawnInventoryFromItemPool` call is issued for generic PS/SG/SM/SR pearl pools




  (already inline-only since 3.5.33), and their merge rows have zero nested itempool




  references â so the cycle-detection graph walk isn't the freeze source either. Added a




  hard node-visit cap to that graph walk anyway as a defensive backstop, but the actual




  freeze this round could not be reproduced from logs; if it recurs, note the *exact* row




  clicked â the log cut off mid-session with no trailing spawn entry to pin it down.




- **Also confirmed not a bug:** the "Found multiple versions of mod 'Squ1ggsBoostingTools'"




  warning (and the same warning for 7 other mods) is expected â the loose dev folder




  always wins over the packaged `.sdkmod`, and the log confirms SQBT did load and




  register (`[17] Squ1ggs's Boosting Tools` in the mod list) this session.









## 3.5.25 - Generic pearl pools spawn every named pearl









- **Root cause:** Generic pools (`itempool_sg_06_pearl`, etc.) called live NCS once and always dropped the same pearl (Herald, Constable, â¦). Child fallbacks only tried the first named pearl.




- **Fix:** Generic pearl pool spawn expands to **every named pearl** in that weapon type when count=1 (SG â Constable + Sharkbait, SM â all three). count>1 cycles through children.




- **Item Spawner UI:** Generic pearl pools now list individual rows (`> Herald`, `> Sharkbait`, â¦) instead of one misleading parent row.




- **SQBT:** Same expand-all behavior; added missing Sharkbait (`ted_sg`) to standalone pearl child map.









## 3.5.24 - Generic pearl pool NCS fix (SG/PS/SM/SR)









- **Root cause:** NCS merge rows for `itempool_sg_06_pearl` etc. use criteria rolls; `should_skip_native_itempool_api` was blocking the live `SpawnInventoryFromItemPool` path that actually works.




- **Fix:** Generic pearl pools (`itempool_ps/sg/sm/sr_06_pearl`) always use native NCS API â never skipped as criteria/event pools.




- **Item Spawner:** Generic pearl spawn uses registered pool API first (`allow_blocked_native`), then named-pearl @U fallbacks.




- **SQBT exe:** Generic pearl pools call legacy NCS spawn directly when BL4 Item Spawner is not loaded.









## 3.5.23 - Named pearl false-success fix + mail fallback









- **Item Spawner / Discovery:** Named `comp_06_pearl_*` rows no longer report spawn OK when NCS silently empties â synthetic pearl pools are not loot-verified as trusted.




- **Pearls:** `deliver_catalog_serial_resilient` tries ground @U â backpack â **loyalty mail** (always, no env flag) for Herald, Screwstonian, Juliet, Constable, Parasite, etc.




- **Discovery / ULM dump:** Named pearl rows try @U serial before synthetic pool ids; pool spawns require nearby loot when verify is available.









## 3.5.22 - Gomie / Raid 2 serial-first fix









- **Raid 2 items (Gomie, Abyss, Lockjaw, â¦):** @U ground serial runs **before** broken merge inline and silent-empty synthetic NCS pools â in both BL4 Item Spawner and SQBT exe.




- **BL4 synthetic rows:** `__synthetic` itempools no longer try inline before catalog @U serial.




- **SQBT:** `_spawn_catalog_named` tries bundled @U serial first for all `RAID2_CATALOG_KEYS`; serial delivery tries ground â backpack â mail.









## 3.5.21 - Pearl spawn order fix (serial-first, no silent NCS)









- **Pearls (SQBT + BL4):** Named pearl rows now try **@U ground serial first**, then **generic type NCS pools** (`itempool_ps_06_pearl`, etc.) for part rolls, then merge inline. Synthetic named pool ids (`itempool_*_06_pearl_herald`, etc.) no longer hit silent-empty `SpawnInventoryFromItemPool` before working paths.




- **Bundled fallback:** Pearl world spawn uses loot-verified NCS (not legacy no-verify). `@U serial` runs before NCS when BL4 Item Spawner is not loaded.




- **spawn_risk:** Block native API on synthetic named pearl pools unless row is `__native_store`.









## 3.5.20 - Pearl pool fix + NCS refresh









- **Pearls:** SQBT Item Pools delegate to BL4 Item Spawner again when loaded (fixes Herald/Constable/Juliet and generic PS/SG/SM pearl pools failing via bundled-only path).




- **Standalone:** Generic pearl pools no longer skip native NCS spawn; named pearl expansion + merge inline casing preserved.




- **Catalog:** Rebuilt from latest NCS dump (1025 itempools); added **Sharkbait** (`itempool_ted_sg_06_pearl_sharkbait`) with `catalog_key` on all named pearl rows.




- **Diagnostics:** Pearl @U serial failures log attempted delivery path.









## 3.5.19 - Serial-first Raid2 + no double-spawn









- **Gomie / Herald / Constable / Artificer:** @U ground serial runs before broken merge inline or silent-empty synthetic pools.




- **BL4 Item Spawner:** `SpawnInventoryFromItemPool` trusts API OK (no verify retry loop â fixes double Crazed Earl / random pearl floods).




- **Raid 2 bridge:** Serial â NCS legacy pool â inline last; removed recursive `_run_pool_spawn_tracked` that caused duplicate drops.




- **Spawn All Filtered:** Queues batches >5 pools to avoid game-thread jank.









## 3.5.18 - Clean pool spawns (pool spawn + pearl fix)









- **All pools:** Plain `SpawnInventoryFromItemPool` uses legacy no-verify path (matches original Downloads item spawner). BL4 Item Spawner mod used when installed for merge/NCS/shiny rows.




- **Pearls:** Named pearl rows skip broken BL4 inline-first path; bundled order is live NCS â @U ground serial â merge inline.




- **BL4 Item Spawner:** Pearl spawn order fixed (NCS â ground serial always â inline last); `try_spawn_catalog_via_serial` now ground-first like Boosting Tools.









## 3.5.17 - Pearl @U ground serial fallback









- **Pearls:** After live NCS pool (Parasite/Locust shiny), non-native pearls (Herald, Constable, Juliet, Screwstonian) spawn via bundled **@U ground serial** (`SpawnItemFromSerial` / console) â same path Item Spawner uses when merge inline has no selection struct. No mail/inbox.




- **pearl_serial_spawn.py:** Synced ground-first comprehensive FromSerial delivery from Item Spawner.









## 3.5.16 - Pearl spawn fix (syntax + NCS-native path)









- **Critical:** Fixed syntax error in `comp_loot_drop.py` that prevented merge inline pearl spawns from loading.




- **Pearls:** Live NCS pools only via legacy `SpawnInventoryFromItemPool` (Locust shiny); all other named pearls use merge inline `drop_only` â no silent-empty synthetic pool retries (fixes double spawns).




- **Catalog:** Pool rows resolve `catalog_key` before pearl routing so Constable/Herald hit merge payloads.









## 3.5.15 - Pearl world spawn (dump-backed merge inline)









- **Pearls:** Named rows (Herald, Constable, Juliet, Screwstonian, Parasite) world-drop via bundled `pearl_merge_pools.json` merge payloads â Item Spawner parity (`handle_variants`, comp casing, `LootFunctionLibrary` inline).




- **Spawn order:** Merge inline comp path runs before silent-empty synthetic itempool names; live NCS pools (Locust) still used as fallback.




- **Catalog:** Pearl rows in `item_pools.json` now carry `catalog_key` so the EXE routes to the correct comp row.









## 3.5.6 - BMS spawn speed + unlimited thin-air spawns









- **Mob Spawner performance:** Async spawns use a prewarmed OakSpawner template + per-click duplicate (~10 ms) instead of multi-second `load_package` / world scans on the game thread.




- **Unlimited stacking:** Fast spawner overdrive + world AI spawn budget disabled on every BMS fire (no ~5â6 mob cap); deploy count UI raised to 999.




- **Reliability:** Deferred lean package warm on PlayerTick; session cache + `find_object` resolve when packages are already loaded; known NPC paths (e.g. Claptrap).




- **BLImGui:** SQBT opens its own window (`acquire_imgui_host`) â not mixed into the shared F1 âBL4 Mod Menuâ tab bar.




- **Startup warning** if standalone `bl4_mob_spawner` / `bl4_oak_spawner` are also enabled (duplicate tabs + slow console path).









## 3.5.5 - Cheat parity (SDK + desktop app)









- **Quick Mods (SDK):** Kill All, Infinite Ammo, Dev Loot, vehicle lock ON/OFF alongside existing god mode, movement, and weapon locks.




- **Desktop app Home:** Reordered for daily workflow â MAX ALL, cosmetics, all challenges, shiny drops/mail, modded serial + legit forge delivery up top.




- **Desktop Player tab:** Full combat cheat set, movement cheats, weapon/vehicle locks.




- **Bridge:** `kill_all_enemies`, `shiny_mail_all`, `vehicle_actions_locked`.









## 3.5.4 - Fix BLImGui panel crash on open









- **Panel open crash:** Switched from a private ImGui host (`acquire_imgui_host`) to the shared BL4 Mod Menu tab system. Opening the panel while ULM or another mod held ImGui could trigger `ACCESS_VIOLATION` during host tear-down.




- **Duplicate mod:** Renamed stale `Squ1ggsBoostingTools.sdkmod` (v3.3.6) so only the loose folder (3.5.4) loads.









## 3.5.3 - TubaBoss spawn prerequisite + clearer DLC boss errors









- Char_TubaBoss fails in open world until Tuba DLC boss packages stream in â BMS now surfaces this instead of silent no-aggro.




- Auto `oak_cache` attempt before DLC boss spawns; explicit error when no live actor exists.




- `oak_cache_status` workflow documented in catalog notes.









## 3.5.2 - BMS territory + aggro fixes (live-editor dumps)









- **GbxTerritoryComponent poke**: set `settings.bAlwaysAwareInThreatArea` and expand Threat/Combat/Patrol territory (`bEverywhere`, large radius) on spawned mobs â fixes large bosses that ignore the player outside arena volumes.




- **Arena poke**: also fires `SetEncounterEnabled(True)` on nearby `OakSpawnEncounter` / `GbxGameSpawnEncounter` actors.




- **Free-for-all**: full pairwise hostility (attack each other) instead of one target per mob.




- **IO spawns**: desktop manifest now passes aggro/anchor fields like mob spawns.









## 3.5.1 - Release polish (desktop 1.0.0)









- Bridge status exposes `bridge_features` for stale-mod detection after updates.




- Home tab: party host tools (refresh roster, kick player â blank index uses roster target).









## 3.5.0 - Legit Item Forge browser (desktop)









- Loot tab: type â manufacturer â root dropdowns, part catalog, validate/build/give, max passives.




- Bridge catalogs: `legit_manufacturers`, `legit_roots`, `legit_parts`.




- Bridge actions: `legit_forge_validate`, `legit_forge_build`, `legit_forge_give`, `legit_forge_max_passives`, `legit_forge_append_part`.









## 3.4.0 - Mobility sliders + utilities (desktop)









- Mobility tab: full movement tuning sliders, apply/save/load preset, time dilation, noclip, party slot teleports.




- Bridge: `mobility_apply`, `mobility_status`, `mobility_zero_vault`, `mobility_noclip`, `mobility_time`, slot teleports, and more.









## 3.3.9 - BMS mob spawner browser (desktop)









- World tab: mob actor catalog (1493 Char_* entries), IO spawns, encounter presets.




- Bridge actions: `spawn_mob`, `spawn_io`, `spawn_encounter`, `bms_reaggro`, `bms_clear`, `bms_activate_io`.




- Restored full catalog dropdowns for loot, travel, serials, mixes.









## 3.3.8 - Desktop dropdown catalogs + RDPSqu1ggs branding









- Author set to **RDPSqu1ggs** in `pyproject.toml`.




- Removes BOOSTDECK naming; unified **Squ1ggs Boosting Tools** branding.




- Desktop app: searchable catalog dropdowns (item pools, travel, mixes, GZO, Lootlemon).




- Bridge: `travel_stations` catalog, improved GZO cache reads, higher list limits.









## 3.3.7 - Expanded bridge actions + desktop tabs









- Full 8-tab manifest, 40+ bridge actions, catalog endpoints.









## 3.3.6 - Local HTTP bridge + desktop app + freecam hardening









- Adds a localhost-only HTTP bridge (`127.0.0.1:49775`) for the Squ1ggs Boosting Tools desktop app and scripts.




- Exposes `/status` and POST `/action` (party roster, currency/XP, max-all, freecam controls).




- Adds `squ1ggs_boosting_tools_app/` Electron app: setup, install/update SDK mod, connection status, quick actions.




- Console command: `sqbt_bridge` (start/stop/status).




- Freecam: enable/disable/flip, stuck-cam recovery, safer co-op player resolution.









## 3.3.5 - Fully bundled spawn stack









- Embeds item spawn (raid/pearl/native pools + @U serial fallbacks), Oak deploy, and Borderlands Mob Spawner inside Squ1ggs Boosting Tools.




- Removes runtime dependencies on BL4 Item Spawner, BMS, Oak Spawner, and Ultra Local Menu for core features.




- World â Mob Spawner and Mix Groups now use the bundled engines only.









## 3.3.4 - Single-click map travel









- Removes the second confirmation click for map and station travel.




- Keeps safe deferred travel (panel closes before the world transition).









## 3.2.5 - Reliable, paced item-pool spawning









- Moves item-pool UObject calls out of the BLImGui draw callback.




- Paces Spawn All through a safe game-tick queue instead of sleeping on the game thread.









## 3.0.0 - Squ1ggs Boosting Tools host console









- Initial host boosting console release.




