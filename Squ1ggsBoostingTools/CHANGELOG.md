# Changelog

## 3.8.143 / EXE 1.1.137
Public cut after sqbt-v1.1.136. Fun stuff first:

- **Drop All Shinies** + **loot shapes** (house/boat/etc) with co-op Use/grab
- **No main menu** — cancel guest leave-pull; blocks host map FT while ON
- **MAX ALL** checkboxes including optional **cosmetics + hover** and **All UVHM 1–7**
- **Serials:** GZO / Lootlemon + **My packs**; safer guest mail / open-rewards path
- **Drop backpack** on Home Most used
- **Auto Lobby (WIP)** timed boosts (options honor UI; no sticky crash-resume; quieter EXE polls)
- UVHM Boost-target fix (name + pending click win over stale index 0)
- Challenge bulk “waiting for game tick” / Start-cancels leftover queues

## 3.8.217 / EXE 1.1.195 (local line before public align)
- **MAX ALL options:** Cosmetics + hover and All UVHM 1–7 (default off).
- **Most used:** Drop backpack bottom pink button.
- **Auto Lobby marked WIP.**

## 3.8.216 / EXE 1.1.194
- **Auto Lobby options honor the UI:** Start/Save reads live checkboxes + number fields (off stays off). Prefill no longer overwrites while you type.
- **Crash / disconnect fix:** EXE stopped flooding `auto_lobby_get` every ~0.5s while Auto was only waiting; progress polls no longer overlap. Sticky `enabled=true` after a crash no longer auto-resumes — press Start again.
- **Safer defaults:** 90s cycle (min 30s), 1.5s step gaps, GZO mail drip defaults to OFF / 3 items / 120s; drip capped at 10.
- **GZO drip:** mails lobby Reward Center when **Mail GZO / pack codes** is ON (Refresh GZO first). World drop still needs **Drop All Shinies**.

## 3.8.215 / EXE 1.1.193
- **No main menu + map FT:** already PRE-blocked host LocalTravel; now also pins `bDisallowLocalTravel` while ON and clears it on OFF (menu-pull scrub path unchanged). Guests' own map travel on their PCs is still not host-controlled.
- **Serials visibility:** segment tabs renamed/emphasized — **My packs** and **GZO / Lootlemon** sit at the top of Serials (sticky nav). They were never under Send.

## 3.8.214 / EXE 1.1.192
- **UVHM was unlocking the host (Squ1ggs / index 0) when a guest was highlighted.** Boost-target dropdown could stay on 0 after a roster click. Pending click + target name now win; UVHM verifies the Boost-target name and retargets if the index drifted. Confirm dialog warns if the name is you/host.

## 3.8.213 / EXE 1.1.191
- **UVHM for guests restored:** reverted the identity-queue experiment back to the proven Boost-target index path. Starting UVHM now cancels leftover challenge-bulk queues (that was hard-blocking guest UVHM — people had to use Challenge Ticker). Settle pacing back to the last known-good timings.

## 3.8.212 / EXE 1.1.190
- **Challenge bulk stuck on 0/N “waiting for game tick”:** activate on queue (not only BP_TickWidget), always pump the challenge tick (self-pauses during UVHM / inventory), and log starts to `sqbt_runtime.log`. Progress polls no longer flood `auto_lobby_get` during challenge/UVHM.
- **UVHM wrong-target / bad fail text:** snapshot the Boost-target identity at queue (index can reshuffle), confirm dialog shows the live name, and blocked starts return the real reason instead of a stale “completed for every target” banner. Slightly slower settle pacing to reduce FinalChallenge AVs.
- **My packs / library:** Serials segment nav hint so My packs is obvious (second tab — it is not under Send).

## 3.8.211 / EXE 1.1.189
- **Shaped loot: normal grab for guests again.** Co-op no longer leaves pins frozen forever (Use/swap only). After publish, slots unlock dump physics + usable so Attract works; guest Use also drops pin tracking; flat shapes are not forced into permanent hold.

## 3.8.210 / EXE 1.1.188
- **Late-join shape grab:** held house/boat was left frozen with "no join teleports" after a guest entered — soft-republish + join mirrors again so friends can Use slots. Also stamp loose (non-pin) world pickups on join so ground piles stay grabable after a shape session.
- **EXE connect:** status poll every 1s while Offline (was 5s) so Online appears without needing a click.

## 3.8.209 / EXE 1.1.187
- **Open rewards on send works for guests again (safely):** when On, paced open runs for delivery targets (host + guests). Guests get a longer first delay. Only packages that already have SerialNumbers are opened — empty loyalty shells stay closed (that was the backpack wipe). Never rewrite guest backpack size.
- **Open pending rewards** opens the lobby the same way (still blocked/warned after Complete ALL non-UVHM).
- **Pack sync:** EXE `sync_sdkmod` prefers the live Steam `sdk_mods` tree so local packs stop shipping a stale Documents mirror (connect failures).

## 3.8.208 / EXE 1.1.186
- **Challenge bulk stuck on "Building list":** status was overwriting the real queued message, and consume waited behind `session_safe` (inventory/menu flicker). List is built on queue now with a real total; activate still waits for listen-host world.
- **Static challenge library:** cache OakChallengeBlueprintLibrary CDO + IncrementChallengeForPlayer (clear on teardown) instead of find_class every apply — same stability/speed idea as ChallengeTicker.

## 3.8.207 / EXE 1.1.185
- **Backpack wipe root cause (confirmed in log):** 3.8.205/206 restored openable GZO mail, but also let the host `Server_OpenPackage` guest mailboxes again — that is what puts ghost items in backpacks (visible, unselectable, gone after leave).
- **Fix:** keep the GitHub serial write so packages open. Auto-open / Open pending only touch the **host** mailbox. Guests open Reward Center themselves. Never rewrite guest backpack size. Skip empty loyalty shells.

## 3.8.206 / EXE 1.1.184
- **Catalog hitch fix:** `read_data_json` / bridge `_load_json_path` now memoize parsed JSON (mtime-checked on disk). Stops re-parsing challenge/actor catalogs on every search/poll — that was stacking with game-thread dump work and forcing long EXE timeouts.
- **Version lockstep:** `pyproject.toml` project + sdkmod versions match `_mod_version.py` again (same drift class as the old hardcoded bridge mod_version bug).
- **Tick polish:** mobility UMG tick caches submodule callables after first resolve instead of string-looking them up every frame.

## 3.8.205 / EXE 1.1.183
- **GZO open restored:** Open rewards on send actually opens the mailed packages again (same GitHub GiveReward + contents[0] SerialNumbers write). 3.8.204 rewrote slots so Reward Center could not open them, and then skipped the auto-open.
- Default Open rewards on send is **Yes**. Stay in-world until status says Rewards opened.

## 3.8.204 / EXE 1.1.182
- **Serial mail (no more ghost wipes):** same GiveReward send as GitHub, but packages keep their loyalty slots (no popping rows, 5 codes per mail instead of 25 jammed on slot 0). That was cutting serials so guests saw items they could not select, then lost them after leave.
- Failed patch retries reuse the empty loyalty shell instead of creating another unopenable package.
- Never rewrite a guest backpack size on send. Host still never opens guest Reward Center.

## 3.8.203 / EXE 1.1.181
- **Ghost backpack fix (serials / open rewards):** Host no longer runs `Server_OpenPackage` on guest mailboxes. Opening rewards for others was putting visible-but-unselectable items in backpacks that vanished after leave/rejoin.
- **Open rewards on send** defaults to **No**; Yes only auto-opens the host's mail. Guests open Reward Center themselves.
- **Open pending rewards** is host-only (button/label: you). Cap remote backpack auto-expand; skip empty loyalty shells.

## 3.8.202 / EXE 1.1.180
- **Guest loot after leave:** No main menu no longer blocks `ClientEndOnlineSession` / kick paths, and only intercepts the host PC — guests can leave and keep dump loot in their backpack.

## 3.8.201 / EXE 1.1.179
- **Serials:** Browse codes (GZO / Lootlemon) segment clearer; Home Jump-to opens the right Serials segment.
- **Auto Lobby:** Drop All Shinies / phosphenes runs first; optional Block menu pull; mail item drip (random GZO or My packs) on its own timer; fair per-guest kick timers after cycle (leavers skipped); UVHM now runs entire lobby 1–7.
- **No main menu:** host Esc/self-leave releases hold instead of fighting the menu (crash fix).

## 3.8.200 / EXE 1.1.178
- **Auto Lobby smoothness:** keep **No main menu** armed for the whole Auto Lobby run when Challenges/UVHM are on (no OFF gap between those jobs that let guests yank the lobby).
- **Hold grace:** 3s delay before No main menu actually turns OFF after a job ends, so the next heavy job can re-arm cleanly.
- **Lighter progress polls** during UVHM/challenges (fewer parallel bridge actions, slower interval) to reduce disconnect / hitch risk.

## 3.8.199 / EXE 1.1.177
- **Auto Lobby Stop:** fixed the false “out of date” crash (`message` double-pass in status handlers). Stop works while Online.
- **Shape status poll:** same `message` clash fixed so the floating progress panel stays healthy.
- **Button sweep:** colour-aura accents keep the infinite seamless gradient loop.

## 3.8.198 / EXE 1.1.176
- **Restore Most used** full daily set (sprint flags, fog, freecam, tidy, mail, chests, BM).
- **Button aura animation:** colour accents keep the infinite sweep (gold/coral/amber/slate/mint were missing it).
- **Auto Lobby Stop:** hardened handlers so Stop cannot throw a false “EXE out of date” TypeError; real errors show the actual message.
- GZO / Lootlemon live under Serials → **Browse codes** (Jump-to label clarified).

## 3.8.197 / EXE 1.1.175
- **Auto Lobby Stop fix:** hard off clears the queue and persists; floating panel has a Stop button; Stop no longer re-merges settings that could leave the loop armed.

## 3.8.196 / EXE 1.1.174
- **First-timer polish:** Start here stays until buttons unlock (main menu Online is not enough). Stronger load-character steps.
- **Co-op shape progress** in the floating panel (placing / publish / ready + join-rejoin hint).
- **Home Most used trimmed** to daily boosts; Open pending removed from Home (Serials only). Jump-to adds Auto Lobby + Loot.
- **Auto Lobby:** one shared settings block, Host-only banner, settings prefill; Status button removed (live panel covers it).
- Sticky Boost target label shows **Editing: name**.

## 3.8.195 / EXE 1.1.174
- **Auto Lobby status box:** floating progress panel shows current job / queue / next cycle while the loop is on (same place as UVHM & challenges).
- **Most used:** similar tools grouped together with colour auras (gold boost, violet progression, coral combat, cyan mobility, amber host lock, pink loot, mint mail). **No main menu** has a 🚫 emoji.

## 3.8.194 / EXE 1.1.174
- **Crash fix (DE983863):** settled co-op held shapes no longer run pin heartbeat (no wrapper resolve / K2_GetActorLocation while friends grab). Host Use matches RPC addr only. Deferred grab unlock disabled.
- **Challenge progress bar:** no more stuck 0/1 while the list builds; selected-challenge runs open the panel too; apply logging throttled so the EXE can poll.

## 3.8.193 / EXE 1.1.174
- **Removed Float up on grab** (option + runtime) — never reliable enough for production.
- **Crash fix (A2F2D77E):** grabbing shaped loot null-AVd through pyunrealsdk. Guest Use no longer resolves aim/pins. Host Use only untracks the pin in the PRE hook (no ForceNet/restore mid-Use); light gravity unlock is deferred one tick.

## 3.8.192 / EXE 1.1.174
- **Crash fix (C87FB5F6):** null AV through pyunrealsdk after guest joined a held boat/house twice then Used. Held shapes no longer rebind/repin/ForceNet on join; join push is cooldown-gated; in-world join waits ~1s to settle; Use no longer probes BodyInstance/net props on guest grabs.

## 3.8.191 / EXE 1.1.174
- **Character-select join lag:** shape join work waits until the guest has a real pawn — no more 197-pin heartbeat while they sit on player select.
- **Place Fully / reshape:** co-op pin cap 180→240 (shiny dumps ~220), prefer loot near the dump, pile leftovers at feet so reshape does not leave a ring. Lighter join prep teleports.
- **Float up on grab:** arms on host Use immediately (was easy to miss), keeps the setting across Place Fully when the field is omitted, small guest samples so friends see the gag.

## 3.8.190 / EXE 1.1.174
- **Auto Lobby tab:** pick MAX ALL, cosmetics + hover drives, challenges, UVHM, backpack/bank size, and Drop All Shinies (no shape). Timer minimum 15s. Jobs run one at a time on the host. Settings save under Documents. Heavy jobs run once per Start unless Repeat heavy jobs is on.
- **MAX ALL snappier:** skips the slow vault wallet/XP double-pass and skips level writes when already at cap — less host freeze / kick risk.
- **Co-op drop visibility:** more pickups stamped live for rain/slow so guests see the flight without ForceNet storms.
- Co-op grab note unchanged: shape first then join, or rejoin once if already in lobby.

## 3.8.189 / EXE 1.1.174
- **Co-op shape note (clearer):** shape first, then friends join — or rejoin once if they were already in the lobby. Host grabs either way. Same note on Drop All / Loot / Shapes / pool spawn.
- **Stay in air defaults to yes** on Drop All Shinies land options so 3D silhouettes hold instead of peeling to the floor.
- Clean-respawn remains off so shaping stays stable.

## 3.8.188 / EXE 1.1.174
- **Co-op shaped grab (release note):** guests who watched the dump still cannot native-collect shaped slots (Use reaches host, collect refuses). Proven path: finish the shape, then have them join — or anyone already in lobby rejoin once. Host grabs either way. UI notes on Loot / Shapes / pool spawn.
- **Stopped the broken clean-respawn path** that dropped guns mid-shape and still failed guest grab. Shapes hold again; no mass slot replace.

## 3.8.187 / EXE 1.1.174
- **Crash before / during co-op shape:** GameThread AV through pyunrealsdk (`0x…6e006f0089`). Clean lobby copies were being armed as soon as float jobs emptied — still mid-dump — then each slot did `find_all(InventoryPickup)` + destroy. Copies now wait until settle, use the cached pickup scan instead of raw `find_all`, pin the new actor before destroying the old one, and never re-arm themselves in a loop.

## 3.8.186 / EXE 1.1.174
- **Pyramid is 3D again.** The dropdown labeled both the 3D pyramid and a flat triangle as "pyramid". Spawn/shape logged `Land in pyramid` and built the 2D triangle (every Z=0). `pyramid` now maps to the standing 3D pyramid; the flat one is `triangle`.
- **Guest grab: stop leaving frozen copies for native Use.** 3.8.185 marked serial-at-feet then teleport as "clean"; guests Used those slots and native collect still refused (`STILL on the ground`, `grav=0 sleep=1`). Replacements now spawn from the item pool *at the slot* (same path as unshaped loot). Guest Use on a replaced slot wakes it into dump-usable world loot, same as the host, then native collect runs.
- **No pickup-safe ForceNet on held co-op shapes.** The 121-pin publish started while the dump was still running and fought the clean-copy respawn. Held shapes only queue the in-place copies.

## 3.8.185 / EXE 1.1.174
- **Guests already in the lobby can grab shaped loot.** Dump-then-teleport copies stay poisoned for those clients (rejoin worked because they got a fresh replica). After the drop lands, each slot is replaced one-at-a-time with a new world actor spawned while they are connected — same guns, same silhouette, no SetReplicates storm, no mail, no rejoin. Wait for `Co-op clean copies done`. Using a slot that is still the old copy jumps that slot to the front of the queue.
- **Drop method plays while items spawn.** Spawn All / dump catch was waiting ~1.3–2s between scans, then snapping leftover guns onto the house after the dump finished. Rain/fountain/spiral now catch as they appear and fly into slots during the dump. Instant pin is only for drop method `none`.
- **Removed the 3.8.184 channel refresh.** Toggling SetReplicates False→True on a 175-slot house lagged the host and never made grabs work.

## 3.8.184 / EXE 1.1.174
- **Guest grab: stop dropping the shape.** The Use trace on 3.8.183 proved native collect refused every guest Use after we woke gravity (`STILL on the ground`). The house only became grabable after they rejoined — same actors, fresh client copies. Guest Use now leaves the gun in the silhouette (host still releases as before). Pin restamp after settle is off so Attract is not yanked back to the slot.
- **Join-quality refresh after the shape lands.** Each slot briefly closes then reopens its net channel (a few at a time) so guests who watched the drop get the same clean copy a rejoin would. That is why a 220-item house fountain kicked the lobby: too much live net at once. Flight net is slower on big shapes (8–12Hz, smaller teleport batches).
- **Drop method `none` has no flight.** Guests will see items appear then snap into the circle. Use rain/fountain/spiral if you want them to see the drop.
- **My packs cannot lose codes on update.** The library now merges every known save file (Documents + sdk_mods + mod folder) by serial, writes back to the richest file, and refuses to overwrite a populated file with an empty list. Import still only adds.

## 3.8.183 / EXE 1.1.173
- **Guests standing back from the shape now release the slot they are looking at.** When a Use RPC carries no resolvable object, the old fallback released the pin nearest the player's *feet* within 320uu. A host stood inside their own shape always matched; a guest a few metres back matched nothing, which is why the log filled with `no shaped slot matched` and their items stayed frozen. Resolution order is now the exact RPC object, then an aim ray from the player's eye (replicated control rotation, 900uu, ~12° cone, tightest angle wins so a gun behind another cannot steal the pick), then the old nearest-feet check as a last resort.
- **Release lines are trustworthy again.** The Use trace used one global 0.45s gate, so any two Uses inside half a second dropped a line and made it look like the wrong slot was released. It is now throttled per slot address, and each line says whether the slot came from the RPC (`rpc`) or the aim ray (`aim`).
- **New: the log says whether the game actually took the item.** 1.5s after a release the slot is re-checked and logs either `collected` or `STILL on the ground — native collect refused`, which separates "we handed back the wrong item" from "native pickup rejects it".

## 3.8.182 / EXE 1.1.173
- **Fixed loot stuck in mid-air (host and guests).** 3.8.180 killed gravity on every physics body to stop shaped guns dropping when Used, but nothing ever switched it back on, so any item that passed a freeze path hung wherever it happened to be. Gravity is now set in both directions across all bodies (`_set_gravity_all_bodies`), and only genuinely held shape slots keep it off.
- **Released slots become ordinary world loot again.** The Use trace proved a released gun kept `grav=0` and stayed frozen-but-asleep, so nobody could collect it — the guest in the log Used the same gun twice, twelve seconds apart, and it was still lying there. Release now restores gravity, wakes the rigid bodies instead of sleeping them, and clears `bSimulatedPhysicSleep` so the fall replicates. That is the same state as the unshaped SQBT loot guests can already pick up.
- **Use trace reads real physics state:** `IsSimulatingPhysics` is not a reflected function and always logged `sim=?`. The snapshot now reads `BodyInstance.bSimulatePhysics` and also reports the collision profile.

## 3.8.181 / EXE 1.1.173
- **Use trace now logs the pickup's actual state, shaped or not.** Guests can collect unshaped SQBT loot but not shaped loot, so every Use RPC now logs one line per item (`Use (guest) [shaped|plain] 0x…: rep= repmov= relevant= rrole= dorm= freq= owner= repphys= sleep= lock= sim= coll= grav=`). Comparing a working plain grab against a failing shaped grab names the exact property shaping changes — no more guessing at the pickup path.
- Diagnostics only; no behaviour change to shaping, freezing, or collection.

## 3.8.180 / EXE 1.1.173
- **Backpack injection removed — it was never possible.** The live `OakPlayerController` dump has no `*FromSerial` function at all (only `ExecuteInventoryTransactionOnServer` / `ServerUseObject`), which is exactly why 3.8.178/179 logged `backpack RPC refused`. Use on a shaped slot now unpins that one item into natural pickable loot and lets the game's own collect finish.
- **Guns no longer fall out of the shape when Used:** `SetEnableGravity` only covers a skeletal pickup's root body, so released slots kept dropping. Gravity is now killed on every body (`SetEnableGravityOnAllBodiesBelow` / `SetEnableBodyGravity`).
- **Use trace is finer** (0.45s throttle, logs the slot address) so repeated guest attempts are all visible instead of being swallowed.

## 3.8.179 / EXE 1.1.173
- **Guests see the drop method, not just the finished shape:** live loot sits at `NetDormancy=3`, which is **DormantPartial**, not "Never" — a dormant actor ignores host teleports until something flushes it, so the lobby only ever got the settle burst ("it shapes after"). Shaped pickups are now stamped `DORM_Never` once when their flight starts, and ordinary replication carries rain/fountain/spiral at 15–30Hz. No per-sample ForceNetUpdate (that was the old host hitch / lobby kick path).
- **Same bug was starving guest pickup:** every `SetNetDormancy(3)` in the shape paths was commented "DORM_Never" but wrote DormantPartial, so guest copies of shaped slots went stale. All shape paths now write dormancy `0`.
- **Use trace:** one throttled log line per Use says whether a guest's RPC reached the host, whether a shaped slot matched, and whether the backpack RPC refused — so a failed grab points at the exact step.
- **Fallback:** if a slot has no `@U` serial, the pin releases (no gravity) and native Use runs for guests too, instead of host-only.

## 3.8.178 / EXE 1.1.173
- **Pick from the shape (no pile):** co-op shapes stay frozen + pinned so the lobby sees the silhouette. Guests (and host) Use an item → serial goes into that player's backpack and that world slot is destroyed. No floor drop, no mailbox, no separate pickable pile. Wait for `visible — Use to collect`.

## 3.8.177 / EXE 1.1.172
- **Guests saw no shape / could not pick (3.8.176):** vis ForceNet never ran — `tick_drop_motion` bailed with empty pins, so only the host had arranged XYZ. Now: no pin lock, dump-usable with gravity off (holds pose), RepMovement stamped, ForceNet every slot, log `visible + pickable N/N`. Wait for that line before guests grab.

## 3.8.176 / EXE 1.1.171
- **Why Ground Loot Helpers guests can pick and ours could not:** GLH is client-side teleport and never pin-freezes server actors. SQBT host pin/freeze/ServerUse was the block. Co-op 2D Arrange/Place/dump settle now leaves dump-natural pickable ground loot (no pin lock); sparse visibility ForceNet only. Stay/3D still uses the hold path.

## 3.8.175 / EXE 1.1.170
- **Guest click dropped guns to the floor and still could not pick them up:** proximity/Use was gravity-waking pins without completing remote collect. Guests now get the item via backpack `AddItemFromSerial` on ServerUse (world actor destroyed). No more proximity floor drops. Not mailbox.

## 3.8.174 / EXE 1.1.169
- **Guests: drop-on-click but still cannot pick:** dump LIVE_OK loot needs `bReplicates` + `RemoteRole=1` + `bRepPhysics` + NetDormancy Never pushed to clients. Host restore alone left guests on the non-replicating row. Per-item hand-off now dump-matches and ForceNet/Flushes once so others can Use the dropped gun.

## 3.8.173 / EXE 1.1.168
- **Lag + floor drop + still no guest pick (3.8.172):** mass `SetSimulatePhysics` on world unlock woke 120 guns (hitch + collapse) and cleared pins so ServerUse could not hand off — dump physics alone did not fix Use. Now: soft dump net/usable stamp only; pose stays frozen; pins kept; per-item restore on ServerUse / proximity / drift; stop sticky `ForceDisableSimulatePhysics`.

## 3.8.172 / EXE 1.1.167
- **Guests could see the shape but not pick it up:** not float-on-grab. Quick Arrange grid logged `held freeze` (Stay/physics lock) and never set settle-done, so hand-off never ran. Dump-backed fix: natural InventoryPickup needs `bRepPhysics=true` + sleep + NetFreq 40. 2D shapes world-unlock; 3D Stay gets dump-usable with gravity off; arrange marks settle done; ServerUse PRE releases the pin.

## 3.8.171 / EXE 1.1.166
- **Guests saw a partial circle / could not pick:** non-hold pins expired in 6s while co-op ForceNet was still running, so publish never finished (`visible + world unlock` never logged) and leftover guns stayed frozen. Co-op pins now live for the full publish; pin heartbeat pauses during pickup-safe; ground publish is faster; net-budget misses retry instead of skipping; unfinished runs force-unlock by 40s.

## 3.8.170 / EXE 1.1.165
- **Guest grab + crash:** Place Fully co-op was freezing *all* pins (including 2D circles), so guests could not Attract; unlock also ForceNet’d dead pickups and AV’d (`0xffffffffffffffff` in pyunrealsdk). Keep freeze only for Stay/peel; ground shapes world-unlock and clear pins; stamp without ForceNet; dead pins drop without restore; Stay hands off when a party pawn is next to a slot.

## 3.8.169 / EXE 1.1.164
- **Shapes stop falling after co-op publish:** logs showed every finish as `normal world pickup` (gravity on). Held/3D/Stay pins now stay frozen after the one-time guest publish; only individual grabs hand off.
- **Guest pickup (dump-backed):** unlock matches live InventoryPickup — `bAlwaysRelevant=true`, `NetUpdateFrequency=40` (held keeps 8). Prior AlwaysRelevant=false / NetFreq=10 left floor guns unusable for lobby mates.

## 3.8.168 / EXE 1.1.163
- **Stay in air kept:** co-op publish no longer enables gravity on held silhouettes. Ground shapes still get normal world pickup; Stay-in-air pins stay frozen with grab collision.
- **Lobby lag on Place Fully:** large held shapes publish slower (2–3 ForceNet/tick) and skip the 180-item gravity wake that was hitching guests.

## 3.8.167 / EXE 1.1.162
- **Challenge progress UI:** status no longer overwrites bridge `ok:true` with the accepted-count integer (that made polls look failed at 0/N and wiped the progress panel).
- **Complete ALL speed:** ULM-style batches — host-local 6/tick @ 0.04s, remote guest 2/tick @ 0.10s. Lobby size no longer forces the slow path when boosting yourself.

## 3.8.166 / EXE 1.1.161
- **Complete ALL for one guest:** a selected remote player now uses the co-op-safe challenge pace. Previously the job saw one target, misclassified the live lobby as solo, and sent 10 challenge updates/second until the interrupted game run.

## 3.8.165 / EXE 1.1.160
- **Remote pickup over rigid pins:** confirmed movement replication was not the blocker—guests cannot collect server physics-disabled pickups. After the bounded visibility publish, restore sleeping simulated world physics and remove every pin/tracking reference. This prioritizes usable sorted loot; 3D shapes may naturally settle.
- **Crash hardening:** stop all pin polling after hand-off and remove every `ReplicatedMovement` struct reassignment from shape paths.

## 3.8.164 / EXE 1.1.159
- **Guests see AND pick up the shape:** bounded two-phase co-op publish—ForceNet each settled slot once in batches of four, wait two game polls, then disable movement correction per slot so guest Attract can complete.
- **Bounded lag:** no indefinite retries; an unsyncable slot is skipped after four attempts. A clear `Co-op shape ready: X/Y visible + pickup-safe` line marks when guests should interact.

## 3.8.163 / EXE 1.1.158
- **Guest pickup without grab detection:** after a short normal-replication window, stop authoritative movement correction on settled co-op pickups. Guest Attract can now reach the player while the host keeps the shape frozen.
- **Shape lag:** remove the 100+ per-item ForceNet retry/follow-up storm and in-flight guest pushes. The failed `ServerUseObject` hook path from 3.8.162 is no longer installed.

## 3.8.162 / EXE 1.1.157
- **Guest pickup uses the real RPC:** hook host `OakPlayerController:ServerUseObject` / `ServerUseJunkObject` and release the referenced pinned pickup before native Use runs. Removed the 3.8.161 proximity-only release, which could unpin loot merely when someone stood nearby.
- **Pickup crash hardening:** no item-serial read or `ReplicatedMovement` reassignment during Use; settled `guest_ok` pins still receive no heartbeat restamp.

## 3.8.161 / EXE 1.1.156
- **Guest shaped loot grab:** host can pick (local drift) but guests floated — host never saw their Attract, and settled ForceNet heartbeat kept freezing slots. Now release pins near any party pawn, stop restamping guest_ok pins after settle, and soft-restore physics (no ReplicatedMovement reassignment — that AV'd).

## 3.8.160 / EXE 1.1.155
- **Shaped loot pickup (real fix):** dumps were right about physics — prior build never called grab hand-off, so Attract lifted guns while freeze/guest ForceNet kept fighting. Drift/upward now restores sleeping world pickup (`bRepPhysics` + sleep) and drops the pin so guests can actually take the item. Float-on-grab option was never involved.

## 3.8.159 / EXE 1.1.154
- **Shaped loot float-up:** live dump showed SimulatePhysics + `bRepPhysics` launches guns — grab hand-off no longer enables physics; settled pins are left alone (no release-on-drift).
- **Nova / co-op lag:** slower pulse batches, no mid-pulse ForceNet to guests, leaner guest sync — was lagging lobby mates out.

## 3.8.158 / EXE 1.1.153
- **Shaped loot pickup:** grabbing a settled pin hands it back as normal world loot and blocks re-shape (fixes fly-up loop when guests tried to pick grid items).

## 3.8.157 / EXE 1.1.152
- **Shaped loot pickup (lobby):** after settle, host no longer re-freezes / yanks drifted pins — that made guest grabs float mid-air instead of picking up (grid + ULM).
- **2D freeze:** keep QueryAndPhysics so guests can grab grid slots.
- **Host lag mid-shape:** rarer find_all + ForceNet during ULM dump; no mid-dump flight net samples.

## 3.8.156 / EXE 1.1.151
- **Send serials copy:** paste one @U per line or space-separated — both work.
- **Serial mail + lobby join:** pause GiveReward / package opens ~12s when someone joins or leaves mid-send (crash at GZO package 18/23 during a join).

## 3.8.155 / EXE 1.1.150
- **Open pending rewards:** stays blocked after Complete ALL non-UVHM (often hundreds of packages) until you force-confirm; Serials Open rewards on send still defaults Yes.
- While challenge bulk is running, Send won’t auto-open mail.

## 3.8.154 / EXE 1.1.149
- **Loot shapes (lobby):** pin maintenance keeps grab collision so guests can pick up shaped guns; denser rain/settle mid-flight samples so friends see the drop, not a snap.
- **Float up on grab:** new Loot Shapes option — when someone yanks a gun from the silhouette, nearby shaped guns briefly float up (gag).
- **Complete ALL challenges:** solo gap 0.10s, co-op 0.18s (still one challenge×player per tick).

## 3.8.153 / EXE 1.1.148
- **Serial delivery HUD:** progress shows in the same floating window as UVHM/challenges (bar + package stage), not the bottom status line.

## 3.8.152 / EXE 1.1.147
- **Nav:** Tabs/Menu switch on its own row with a divider; Menu hides tabs and opens the drawer immediately.
- **Send:** Open rewards defaults to Yes again so mailed items show up for most players.

## 3.8.151 / EXE 1.1.146
- **PlayerBank spawn:** no dual world follow-up + broader bank-path detect — stops freezes when spawning bank with held loot shapes.
- **Nav:** Tabs / Menu switch (persisted) — hamburger drawer when Menu is on.
- **My Library:** New pack / Delete pack, Import .txt/.json, Export .txt + .json; pack headers Rename / Export / Delete.

## 3.8.150 / EXE 1.1.145
- **No main menu:** renamed from Keep lobby — same host toggle that stops guests pulling you to the title screen. Turn OFF before you quit yourself.

## 3.8.149 / EXE 1.1.144
- **Complete ALL challenges:** solo runs use a tighter safe gap (0.18s vs 0.30s) — still one challenge/player pair per tick, never the old co-op burst. Multi-target lobbies stay at 0.30s.

## 3.8.148 / EXE 1.1.143
- **Keep lobby:** cancel RPC now passes empty **SName** `CancelReason` (dump-proven type), not FText/`""`/`0` — that was why every interrupt logged `ok=False` while leave still completed. Logs now show real fail reasons + `sname_ok`.

## 3.8.147 / EXE 1.1.142
- **Serials UI:** GZO + Lootlemon are back on the same tab scroll (segment hiding removed); duplicate Advanced queue fold fixed.
- **Keep lobby:** View-button equivalent — spam `ServerInterruptTravelCountdown` + `ClientCancelPendingMapChange` while ON; treat TravelStatus status=1 as leave even when CountdownTime stays at 5.0; also PRE-block `LocalTravel`.

## 3.8.146 / EXE 1.1.141
- **Hold / Nova / Cleanup / Kick / Library (plan pack):** Keep lobby PRE-blocks travel/menu; Nova Stay defaults ground-unpinned pulse; Most used Cleanup loot; roster/Boost-target right-click kick (refuses self); My Library expandable packs + merge-only txt share.

## 3.8.145 / EXE 1.1.140
- **Serials / Library / Codes:** professional IA — Send | My Library | Browse codes | Mail tools segments; shorter copy; Open rewards defaults to No everywhere; in-app name dialogs (no `prompt()`); clearer empty states; GZO advanced filters tucked away; Send selected naming consistency.

## 3.8.144 / EXE 1.1.139
- **Keep lobby:** interrupt-only was not enough — guests could still travel the host out. Restored host-local leave cancel (pin TravelStatus + `ServerInterruptTravelCountdown`) plus PRE-blocks for travel/menu/session-end, with OnRep_TravelStatus scrub. No `find_all` / no `Initiator=None`.

## 3.8.143 / EXE 1.1.138
- **Progress HUD:** while Complete ALL challenges, UVHM, or Spawn All Filtered is running, the progress bar stays pinned top-right on every tab for the whole run.
- **UVHM restored:** fixed the rank-one `token_s` failure; safer final-challenge settle and persistent status/error reporting.
- **Network safety:** UVHM and bulk challenges cannot overlap; host-only bulk is paced one challenge/player pair at a time, shape guest replication waits for progression, and co-op held shapes cap at 180 pins.
- **Current challenge data:** 3,286 game-build challenge identifiers, including 55 FL4K/Providence (`Harmonica`) challenges and complete Loveless/Robo Dealer character filters.
- **Challenge safety:** Vault Card 5 dailies/weeklies stay excluded from Complete ALL; Tuba echo logs are categorized as collectibles.
- **Keep lobby:** now does exactly one host-local operation—`ServerInterruptTravelCountdown`; no travel/menu blocks, OnRep hooks, struct writes, or lobby-wide scans.
- **Co-op shapes:** hardened live-object/ForceNet handling, gear-only held silhouettes, safe pin limits, and paced guest sync.
- **Current loot:** added Loveless/Providence class-mod pools and the latest shiny equipment pools.
- **Most used:** restored full button wording and missing Shoot/Zoom while sprinting/downed actions; compact sizing is CSS-only.
- **My Library:** clearer import/create/edit flow, New entry, merge-only pack import, collision-safe persistent IDs, and refreshed Lootlemon caches now override the bundled seed.
- **Desktop cleanup:** closing the EXE clears pending desktop actions, cancels queued high-network/shape work, and releases Keep lobby.
- **General polish:** GZO/Lootlemon work without BLImGui, sticky combat toggles are restored, and PlayerBank/golden-chest/spawn spam paths are hardened.

## 3.8.142 / EXE 1.1.136
- **Hold session (no menu kick):** sticky host toggle cancels travel-to-menu and blocks return-to-menu / session-end leave so guests cannot pull the lobby out. Auto-arms during All UVHM / Complete ALL challenges; turn OFF before you quit to the menu yourself.
- **Loot shapes co-op:** Place Fully / settle no longer ForceNetUpdates hundreds of pins in one frame (house AV). Host layout stays local; guest sync drips so grabs match the shape.
- **Soft clear (hide loot):** on Home -> Most used and Loot -> Shiny drops (same as Loot Shapes).
- **Party teleport:** Everyone -> me (plus Me -> selected / Selected -> me).
- **MAX ALL:** Vault cards labeled **1-5**; already-maxed levels treated as success.
- **My Library / Serials:** optional Save entry name; GZO / Lootlemon Add to library; Deliver converts human/deserialized codes to @U before mail.
- **Home -> Most used:** Complete ALL challenges + All UVHM (target) one-taps.
- **Nova:** 3D sphere pulse; Stay in air on/off landing behavior; pulse no longer stalls behind bulk pause.
- **Stability:** PlayerBank/IO freeze (no world find_all on every spawn); quit soft-clear; mobility scrub; Find a tool / catalog search click hardening.

## 3.8.141 / EXE 1.1.135
- **Loveless (Corpo Hacker Raid 2 class mod):** dedicated merge spawn (was silent NCS lag / no loot). Dedicated classmods run before bulk native.
- **Spawn All Filtered:** fixed `shape_text` TypeError (queues/shapes work again).
- **Infinite jump (all / others):** no longer clears friend targets / sticky all-mode on join blips.
- **Shiny shapes:** lower house fill cap + 1/tick when shaped (D3D12 crash mitigation).
- **Spawn this one item:** count accepts 1–999 (Spawn All Filtered still x1/pool).
- **UI/stability:** Backpack tab removed again; party teleport shows Boost names; Dev Testing Map travel no longer cancels on brief session blips; bridge clears sticky last_error after success.

## 3.8.140 / EXE 1.1.134
- **Character level 70:** MAX ALL, Player level, in-game LV button, and keybinds actually apply **70** (labels already said 70; wiring still used 60).
- **Gear defaults / overrides:** serial rewrite + catalog level fields track 70 for this cap bump.
- **Pre-update note:** item-pool / main-page catalog refresh for the new cap is coming soon — this drop is the level-70 boost prep.

## 3.8.139 / EXE 1.1.133
- **Spawn shapes (new/restored on this drop):** diamond (3D), blocks, cube, torus, crown, UFO, rocket, gear — if you stayed on the last public release, grab this build so these shapes are actually on disk.
- **Send serials Browse / YAML:** loads into the paste box (blank line between codes) — not the optional queue and not My Library.
- **Add to library…** next to Send items: saves the paste box into My Library under a name you choose.
- **Open rewards:** still opens one package at a time (safe path); no bulk open.
- **Loot text / Spell a word:** restored 3-line shinies/pool lettering where relevant.
- **Co-op shapes:** silhouette drip / settle fixes so guests can grab without floor piles or mid-dump snaps.
