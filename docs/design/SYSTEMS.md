# SYSTEMS INVENTORY — what exists in spacehack

The shared memory. One entry per shipped system/mechanic, with its
code anchor. THE CONTRACT:

1. **Consult BEFORE designing anything** — "is this already solved?"
   is the first question of every riff/refine session. An entry here
   means the mechanic exists, works, and is load-bearing.
2. **Update at every phase close** — a phase isn't closed until its
   entries exist here. New mechanic → new entry; changed behavior →
   amended entry.
3. **Entries are claims about code.** Before ruling from one, verify
   the anchor (file + symbol) still says what the entry claims.
   Never argue memory against memory — read the line.

v2 (2026-09-07): full codebase audit — 7 domain sweeps, every entry
below anchored in code read during the sweep. Drifts found and
fixed in place. "Absent:" lines record verified non-existence so
nobody designs against a ghost.

## Identity & reputation (doc 40)

- **Broadcast states** — live/dark/spoofed from `broadcast_dark`
  master switch + `broadcast_identity` worn ID; dark suppresses
  everything even with a face worn; D is gated — dark requires the
  one-time `transponder_cutout` install, refused with a pinned log
  line otherwise (`identity.py`: `broadcast_mode`,
  `resolved_identity`, `toggle_dark`).
- **Transponder cut-out** — dark's price of entry: one-time install
  by the `ember_tech` NPC ("Transponder Tech", seated always-on in
  Ember's depot interior), 2,500cr, never consumed, rides the
  player across lawful purchases; the talk row shows only while
  uninstalled (`identity.py`: `CUTOUT_BROKERS`,
  `buy_transponder_cutout`; `npc.py`: `_cutout_offer`). LOAD
  INVARIANT: a save without a cut-out never loads dark — a legacy
  dark save restores live with a log line
  (`saveload.py`: `_restore_identity_layer`). Storefront split
  is deliberate: scrub at Deadfall's broker only, cut-out at
  Ember's tech only.
- **The one read resolver** — every reader pulls the broadcasting
  sheet through `identity.effective_reputation(ctx)` (pure, fresh
  dict): dark → {} (all readers neutral), spoofed → the worn
  library entry's `rep`, live → copy of `ctx.faction_reputation`.
- **Rep write routing** — writes follow the broadcast
  (`faction.modify_rep`): live moves ID 1, spoofed moves the worn
  entry's sheet via `identity.apply_worn_delta` (library entry is
  source of truth; `broadcast_identity` is a display copy that
  diverges on save/load — never read/write rep through it), dark
  silently discards (crime under dark is unsolved).
- **Soft cap** — positive gains landing above +50 are halved;
  negatives uncapped (`faction.py`: `_soft_cap_delta`).
- **Attitude zones** — enemy ≤ −76, disliked ≤ −26, neutral ≤ +25,
  liked ≤ +75, allied ≥ +76 (`faction.get_attitude`).
- **Starting rep** — four axes (doc 48 phase 2): `_DEFAULT_REP`
  pirate −100 (enemy — why early pirates attack), militia +50,
  merchant 0, consortium −100 (hidden); species adj (martian:
  militia +10, pirate −10) + class tables; clamped [−100, 100]
  (`faction.py`: `starting_reputation`, `_SPECIES_REP`,
  `_CLASS_REP`). Civilian is RETIRED as an axis (doc 48 SETTLED 8 —
  rep requires an organization); the bystander's `civilian` tag
  survives only as a kill-delta accounting key.
- **Hidden axis (doc 48 phase 2)** — `HIDDEN_FACTIONS =
  {"consortium"}`: state that renders NOWHERE — no standings row
  (`pygame_faction._faction_rows` filters it) and no rep-delta log
  line (the write lands, `_apply_rep_delta` returns before the log
  build — every mover funnels there). Movers v1: killing
  consortium-tagged specs (kill row: consortium −3, pirate +1 — the
  pirate component still logs) and a −1 ripple per merchant-ship
  kill beside the `merchant_kills` counter, space path only (booked
  boardings included; ground merchant-crew kills are the direct
  mover's job). Gates nothing; decays uniformly with the monthly
  pass.
- **Civilian retirement blast radius (doc 48 phase 2)** — the
  bystander kill row is the honest-folk crime ledger
  `{"militia": −2}` (militia notices crime); the merchant kill row
  carries the same militia −2 (piracy is crime); guild pay re-keys
  civilian → merchant (`guild_to_faction` lab/depot/fallback);
  save migration drops civilian from BOTH rep stores and seeds an
  absent consortium at −100 on the true sheet only (worn sheets
  stay blank paper — absent keys read neutral; `saveload.py`:
  `_sanitize_rep_sheet`, `_migrate_worn_sheet`).
- **Rep delta sources** — per-mission-type, per-kill-by-victim-
  faction, and unprovoked-attack tables (`faction.py`:
  `_MISSION_REP_DELTAS`, `_COMBAT_KILL_DELTAS`,
  `_COMBAT_UNPROVOKED_DELTAS`).
- **Pay, not access** — standing scales rewards/prices, never gates
  access: board pay −15%…+20% (`adjust_reward_pct`), trade buy/sell
  liked −5%/+5%, allied −10%/+10% (`buy_price_modifier`,
  `sell_price_modifier`).
- **Monthly decay** — drift toward neutral by zone (+3/+2/−2/−3),
  sign-safe (only player actions flip sign); always ages ID 1 only
  (`faction.apply_monthly_decay`; ticked from `time.py`).
- **ID library** — six false IDs max (`LIBRARY_CAP`, enforced at
  `collect_id` so scrub AND capture refuse; shared full line
  "Your ID book is full."); entries ride the player across lawful
  ship purchases; dedup by hull number; cycle none → first → … →
  none; X deletes the shown ID on the F screen and removing the
  WORN entry auto-clears the broadcast to live (`identity.py`:
  `collect_id`, `library_full`, `remove_id`, `cycle_identity`;
  `pygame_faction.py`: `_delete_shown_id`).
- **ID buy-back** — the Wolf 359 b rig dealer (the only
  `ID_BUYERS` entry, behind his talk gate) pays sheet-derived
  prices: base 500 + 100 per positive point on the ENTRY's own
  sheet — a ground-up ID flips for more than a scrub costs
  (`identity.py`: `sell_value`; `npc.py`: `_handle_sell_ids`,
  sub-menu stays open until ESC).
- **Clone rig (identity purchase #3)** — one-time unlock at the
  Wolf 359 b dealer (priced above the cut-out), never consumed —
  the loop's recurring cost is the hunt itself; the dealer's talk
  gate refuses below resolved pirate liked with `Scram.` and no
  menu (`npc.py`: `_rig_offer`; `identity.py`: `transponder_rig`
  flag, rides the player like the library).
- **Clone roll** — at the capture interior's C console with the
  rig: one roll per source hull (physically enforced — the hull is
  consumed at boarding entry), persisted on the library entry;
  tier from the hull class's `base_hull` against bands (40, 80):
  the source faction rolls 0–60 / 10–80 / 25–100 by tier, every
  other faction −20…+20 (always neutral at birth — heat builds only
  by wearing it) (`identity.py`: `clone_tier`, `roll_clone_sheet`,
  `clone_transponder`; CLONE_TIER_BANDS re-cut 2026-09-09).
- **Scrub (identity purchase #1)** — `deadfall_scrubber` NPC,
  6,000cr; a scrub materializes literal 0s for every faction
  (`identity.py`: `SCRUB_BROKERS`, `buy_scrubbed_id`). The cut-out
  is the split storefront (see Transponder cut-out).
- **Registration** — 2 letters + 4 digits, generated once per run,
  migrated into old saves on load (`generate_registration`,
  `ensure_registration`).
- **NPC broadcasts** — every NPC ship broadcasts; hull number minted
  on first read, kept for the entity's life (`npc_identity`).
- **F screen hub** — renders the broadcasting sheet literally + the
  identity line `[pos/total] label [MODE]`; D toggles when the
  cut-out is installed (logged, naming the worn ID; otherwise the
  hint reads `D transponder (no cut-out)`), TAB cycles
  (`pygame_faction.py`: `frame_for`, `_log_transponder_toggle`).
- **Challenge hail** — militia-only physical spot of a dark hull
  inside `detect_radius` (eyes, not comms range): Identify/Attack,
  no run; silence = refuse = fire; the answered ID's sheet decides.
  POSITIONAL since doc 41: answered only while the hull stays in
  range, leaving re-arms the patrol (`dark:`-namespaced keys in
  `ctx.militia_scanned` — the scan/warning paths keep one-shot-
  per-visit). Doc 41 column scope: a picket spotter opens the
  Line's Comply/Defy checkpoint instead
  (`navigation_combat._dark_spot_challenge`; `comms._handle_challenge`,
  `_judge_identification`; `navigation_line.line_dark_hail`).
- **Dark dock gate** — only `dark_berth=True` PlanetSpec opt-ins
  berth a dark hull (lal_b Deadfall, lal_c Whisper, ross_b Ember,
  wolf_b Wolf 359 b), checked before the system switch commits
  (`game_interactions._dark_dock_refusal`).
- **Absent:** fabricated IDs (act-1 quest content owns the grant);
  level-60 capstone; species beyond human/martian,
  classes beyond pirate/merchant/bounty_hunter; level-up HP gains.

## Space flight, spawns & combat

- **System maps** — big walkable grids (Sol 200×140); planets/
  gates/stations are multi-cell unwalkable footprints driving bump
  detection (`solar_system.py`: `planet_id_at`, `jump_point_at`).
- **Enemy ship identity (doc 48 phase 3)** — glyph = the FLOWN
  HULL's own char, single-sourced in the hull catalog
  (`data/ships/core.py`: skiff `t`, scout `s`, hauler `h`, cruiser
  `C`, frigate `F`, freighter `H` — the h/H case pair is the cargo
  family); color = the faction's ONE family color (pirate red
  (220,60,60), militia blue (100,200,255), merchant green
  (100,220,140), derelicts amber/brass); class twins render
  identical by design — weight reads from the hull, faction from
  color. Elite/flagship bold: `NpcShipSpec.elite` (pirate captain +
  warlord) → `Entity.bold` at every spec-driven construction site →
  rides `WorldDrawCommand` → `FrameCell` → `GlyphAtlas.blit(bold=)`
  picking the +1-column widened atlas. Enforced by the identity
  lint (`tests/test_enemy_identity.py`: hull pin, one-fg-per-
  faction, ≥60 max-channel separation per theater, cross-registry
  glyph pin {s}).
- **Jump gates** — bump opens a fuel-vs-cost dialog; jump deducts 10
  fuel, rebuilds the map, re-stamps spawns (arrival exclusion
  radius 12), clears the old system's hail memory
  (`navigation_travel.py`: `_jump_to_system`; `ship.JUMP_FUEL_COST`).
- **GO TO auto-nav** — Bresenham-when-clear else A* to the target's
  nearest free cell; breaks instantly on comms warning or encounter
  (`navigation_travel.py`: `_run_goto`, `_goto_step_interrupt`).
- **A\* + slip** — 8-directional pathfinding to goal-cell sets;
  blocked steps try perpendicular slips (`world_path.find_path`;
  `world.try_step_with_slip`).
- **Encounter detection** — every step re-scans three spawn readers
  (static/bounty/procedural), one shared gate: engage only when the
  RESOLVED sheet reads disliked/enemy (`_gate_engages`), bypassed by
  `_aggro_override` (charged-cell heat OR the Line's interdiction
  flag — heat responses, not identity reads); statics gate uniformly
  since doc 40 phase 4 (the Luyten blockade stands down to
  militia-liked hulls — user-ruled, no exceptions).
- **Charged-cell heat** — Act-0 heat in Sol: militia engage
  regardless of identity, detect radius floored at 30 — a heat
  response, not an identity read (`_charged_cell_aggro`).
- **The Line (doc 41)** — the Luyten blockade as a checkpoint
  system: a data-specified broadcast-sweep column
  (`SensorColumn` on the system spec — x, squad, picket id,
  rank_rep 80, message templates). MANNED sweep: crossing fires on
  entering the column from either side (leaving free — no re-hail
  on a complying retreat) and the column goes dark when its picket
  squad is dead. One hail shape: comms modal addressed to the
  broadcast ID ("Unidentified hull" dark) — manifest trait waves;
  worn face at rank_rep waves ("sir"); service-run trait waves and
  is consumed (one crossing per contract, symmetric); everything
  else — allied included — is challenged (Comply turns back / Defy
  raises the LINE-scoped interdiction flag; ESC = Defy). Waves
  don't break GO TO. Identity-only reads, never cargo
  (`navigation_line.py`: `check_crossing`, `resolve_sweep`,
  `_run_checkpoint`; wired into `game_flow._run_combat_loop` +
  `_goto_step_interrupt`). Marker traits `blockade_manifest` /
  `blockade_service_run` in QUEST_PERKS — no grant path (the
  methods own acquisition); dev Shift+L / Shift+K grant them.
- **The convergence (doc 41 phase 3)** — the Line's teeth.
  Defiance PERSISTS: `GameContext.line_defiance_system` +
  `line_comply_latch` survive save/quit/Continue (the load path
  stamps the crossing tracker so a fresh process still converts);
  jumping out clears both (`reset_defiance` at the depart seam).
  The complying-runner LATCH: a challenge-Comply arms it (waves
  never do); the first step off the column's EAST edge converts
  the lie into Defy (its own branch, `prev_x == column.x`,
  manned-gated). A flagged hull is never hailed or waved — no
  checkpoint, no wave modals, no service consumption, no
  dark-spot Comply; the pursuit is the detection. Pursuit is
  system-wide MAP movement (`_squad_aggro` reads the flag — the
  patrols chase; the detect-30 floor keeps feeding engagements)
  until the pursuers die or the hull jumps; killing the line goes
  quiet until the next boundary's reliefs re-man and re-engage.
  Tuning (doc 39's 30-floor contract): pickets are light cutters
  (`light_laser` x2, gunnery 15 — one threatens a hauler, ten are
  the level-30 gate), proven closed-form by
  `tests/test_line_tuning.py` (full watch unwinnable below 30,
  costly win at 30+, thin watch winnable mid-20s — the
  maintenance month is the fight method's timing play).
- **Defeated statics tombstone** — a killed static spawn
  (`system.enemies` — the Line's pickets) is ledgered as
  `sys:enemy_id:x:y` (watch rotations: `sys:enemy_id:x:y:t<tenure>`
  — a kill holds for its tenure, the post re-mans at the next
  boundary) in `ctx.defeated_static_spawns` (key stamped
  on the entity at build — combat moves hulls) and never re-stamps
  at any map build; serialized
  (`_space_kills.mark_static_spawn_defeated`;
  `solar_system.static_spawn_key`; `make_solar_system`'s
  `skip_static_spawns`). Pre-watch saves migrate once at load
  (`navigation_line.migrate_legacy_tombstones` at the top of
  `load_game` — luyten picket keys only).
- **The watch (doc 41 phase 2, round-3 amendment)** — the Line's
  pickets rotate on 30-day shifts (a month on the line; 7-day
  shifts rotated too fast — every lead < shift, so one relief
  wave is airborne at most) from watchbill DATA on the `SensorColumn`
  (`shift_days`, `watch_cycle` full/full/full/thin, `full_watch` /
  `thin_watch` station rosters of `(y, lead_days, base_id)`). Every
  schedule decision derives purely from the day clock — tenure =
  `(total_days - epoch) // shift_days`, no schedule state anywhere.
  Map builds place the current-kind roster PARKED on station with
  tenure-suffixed keys and stamp overdue future reliefs AT THEIR
  BASES (`navigation_line.static_build_placements`;
  `make_solar_system(watch_day=…)` — required for watch systems, a
  build without it raises). The per-step pass
  (`navigation_line.step_watch`, beside `move_npcs` in both
  movement passes + the headless turn): reliefs launch silently at
  their bases a per-station lead before each boundary and fly in
  (deterministic hull-speed credit via doc 44, cached A*,
  `try_step_with_slip`); watch right-of-way (round 4): same-base
  reliefs launch pre-spaced down the corridor, landed pickets
  re-center onto their exact rows (the trigger pass reads rows),
  and a flight blocked by a parked hull re-routes (keeping its
  path if the corridor stays sealed); at a boundary
  every at-station picket of an ended tenure flies home and lands
  (despawned wordlessly); DISPLACED/lured pickets are never given a
  target — they serve until destroyed; murdered reliefs stay dead
  for their tenure (tombstoned launch keys skip); flights live in
  `ctx.npc_targets`/`npc_paths` keyed by spawn key and are dropped
  at save (session-scoped) — the watchbill rebuilds them. Watch
  traffic carries no squad id (invisible to the patrol machinery)
  and logs nothing (wordless — the schedule is observable by
  watching). The sweep counts every alive picket — parked, in
  flight, displaced (`_picket_payload` reads by picket id). Dev:
  Shift+J advances the clock ON the next shift boundary.
- **Bounty spawns** — placed at fixed offsets east of landmarks,
  leader-only carries `bounty_spawn_id`; defeated spawns tombstone
  (`defeated=True`) and never re-stamp (`navigation_spawns.py`:
  `_add_bounty_spawns_to_map`, `_remove_bounty_spawn`).
- **Procedural ecology** — per system entry: derelict roll, militia
  patrols sized by `patrol_density`, consortium squads under quest
  heat, weighted `npc_spawn_table` groups (50% squad-tagged,
  merchants given destinations); per-tick traffic at 5% of
  `npc_spawn_chance`, capped at density×3 (`npc_ships.py`:
  `spawn_npcs`, `_tick_spawn_npc`).
- **Merchant ecology** — body-to-body paths, flee pirates within 10
  cells, despawn on arrival (`_merchant_flees`, `_despawn_merchant`).
- **Squad movement** — shared leader A* with per-squad movement
  CREDIT at the mover's own hull speed (doc 44): `map_speed`
  derives from the spec's hull (explicit `base_speed` wins,
  derelicts 0), credit accrues map_speed/player_speed tiles per
  player step — deterministic, no throttle — and a space-wait pays
  a whole day (`rate_for`); the clamp parks a mover on a cell
  entering an encounter trigger (stop ≠ fire); retained credit
  banks at one tile; accumulators persist exactly the path-sync
  population. Straggler regroup >4 cells; aggro chase retargets
  whole squads (`npc_movement.py`: `spend_credit`;
  `_move_one_squad`, `_squad_aggro`, `navigation_line.
  _advance_flight`).
- **Danger knobs** — per-system `npc_spawn_chance`/`npc_spawn_table`/
  `npc_density`/`patrol_density`/`derelict_spawn_chance` (Sol none →
  Lalande 0.90/density 7) (`data/solar_systems/*.py`).
- **Comms panel (T)** — unowned ships in viewport, nearest first,
  `(hostile)` by resolved attitude; option matrix: militia Allow
  Scan/Flee/Attack; blockade/derelicts End Transmission only;
  others Attack/Scan Cargo + Open Trade at neutral+ (`comms.py`:
  `open_comms`, `_contact_options`).
- **Auto-hail** — three independent one-shot triggers per entity:
  spec `comms_warning_range`, per-entity `bounty_comms_range`,
  viewport entry for derelicts; all keyed via `militia_scanned`
  (`navigation_combat._auto_hail_entity`).
- **Militia scans** — chance by resolved militia attitude (allied
  0/liked 20/neutral 40/disliked+enemy 80%; bar-heat floor 60%);
  one roll per patrol per visit (`_militia_scan_chance`).
- **Flee (pre-combat only)** — 0.40 +2%/speed >10 +0.5%/piloting
  >30, clamp 0.15–0.90; failure forces combat + unprovoked rep
  (`_calc_flee_chance`; `comms._attempt_flee`). **Absent: no
  disengaging once a space fight starts** — fights run to VICTORY.
- **Space combat init** — encounter wrapper builds player state +
  one EnemyInstance per spec, dedupes overlapping spawns
  (`combat/_encounter._handle_combat_encounter`).
- **Combat math** — fractional AP in twentieths with banked carry
  (both sides); hit = accuracy + gunnery/2 + close bonus − range
  penalties − dodge, clamp 5–95; dodge +5%/cell moved (cap 30) —
  kiting is the core defense; damage × quality × 0.8–1.2 variance,
  hull-then-shields (`combat/_stats.py`, `_actions.resolve_damage`).
- **Volley + Focus** — F fires all active weapons (max single AP
  cost); Focus trait (one weapon): 2× AP/power cost, doubled
  ranges, 2× damage beyond normal max — the kiting payoff
  (`combat/_loop.py`; `combat/_space_focus.py`).
- **Resources** — hull/ammo sync to the owned ship at fight end;
  power pool regen/turn; S = paid shield regen 0–10
  (`combat/_rules_space.sync_state`, `handle_defense`).
- **Combat AI** — per-ENEMY AP loop: advance when beyond own
  `ai_preferred_range` or no LOS, else fire; fights to the death
  (`combat/_ai.py`). **Dead data:** `ai_aggressiveness` unread
  (doc 48 rules it the future fire-vs-reposition dial);
  `ai_flee_threshold` RETIRED in doc 48 phase 3 (field deleted,
  TypeError-pinned; fleeing ruled out of space combat, SETTLED 20 —
  doc 34 folded there).
- **Reinforcements** — per-round re-detection joins newly triggered
  squads mid-fight (`combat/_rules_space.check_reinforcements`).
- **Kill bookkeeping** — XP = hull×2; 1–2 loot drops; rep deltas by
  victim faction (+squad bonus); completes bounty missions;
  tombstones quest guards (`combat/_rules_space.on_kill`;
  `combat/_encounter._apply_kill_reputation`).
- **Death** — deletes the save immediately, writes nothing; combat
  never saves mid-fight (`combat/_loop._finish_combat`).
- **Persistence** — `bounty_spawns`, `procedural_spawns`,
  `npc_targets`, `npc_paths`, `militia_scanned` round-trip;
  `combat_locked` is transient (`saveload.py`).
- **Boarding** — wrecks: dead hulls bump-board into cached
  interiors (`game_interactions._resolve_npc_ship_blocker`,
  `_enter_boarding_dungeon`). LIVE capture (doc 40 6a): BOARD in
  combat under four conditions (shields down, 75% hull, solo duel,
  adjacent; `combat/_space_boarding.board_denial`), entry consumes
  the hull (one board/roll per ship), the crewed interior's C
  console clones the transponder (rig-gated, tier-banded roll —
  `identity.clone_transponder`). Every battle spec (13/13), static
  spawns, and quest-lifecycle ships board; the consume books the
  full kill pass minus exterior loot (XP, counters, rep through
  the broadcast gate, bounty completion, tombstone —
  `combat/_space_kills.record_kill_pass`,
  `game_interactions._consume_boarded_hull`); the capture
  interior seeds the flown-module strip at engine-room markers
  (doc 47.3); heist cargo rides
  the interior via the component seam (one-shot: exit without
  pickup strands the intercept — user-confirmed).
- **Crew roles (doc 48 phase 6)** — `data/npc_chars/crew_roles.py`:
  ENEMY markers name faction-neutral ROLE tokens
  (line/heavy/marksman/security_drone/stowaway); `load_layout`'s
  `crew_faction` resolves them through `CREW_ROLES` (raw spec ids
  pass through; an omitted role skips — militia boards no
  stowaways). One deck geometry serves every faction: pirate decks
  field raider/rifleman/brute crews, militia decks
  trooper/marine-strike/sniper (the sniper rides the heavy slot —
  SETTLED 10's heavy-hitting row), merchant decks field the light
  Merchant crew + droids (`heavy`=assault drone; the
  `security_drone` role scales by the boarded hull's
  `NpcShipSpec.security_drones` wealth dial — hauler 0.5 /
  freighter 1.0 / caravan 1.5; H decks guarantee their heavy pair).
  Marker COLOUR overrides are RETIRED — crew identity renders the
  resolved spec's family color (landmark drone decks included).
  Every capture/derelict interior is HOSTILE on entry regardless of
  rep (`GameMap.hostile_interior` through `spec_is_hostile`'s
  optional game_map param — the one uniform seam, serialized);
  kill deltas land by crew faction through the existing tables.
- **Absent:** no ship-vs-ship real-time movement, ramming, tractor,
  mines-as-entities; no salvage drones; no player-called allies; no
  flee-from-space-combat; `NpcShipSpec.comms_range` documented
  "future use", unread (viewport visibility rules instead).

## Ground combat

- **Trigger** — pure LOS aggro: visible hostiles within
  `sight_radius` (8) (`combat/_encounter.detect_ground_combat`).
  The doc-48 `noise_hostiles` OR-in seam is RETIRED (phase 5,
  SETTLED 36): heard entities investigate via the goal system and
  reach combat only through this LOS scan — heard is never
  combatant.
- **Ground noise (doc 48 phase 5)** — `noise.py`: every accepted
  shot emits at the shooter per the weapon's `noise` column
  (explosives 12, kinetic rifles 8, pistols/SMG 5-6, energy/plasma
  4, melee 1-2, organic 4-5; both sides symmetric, deadshot chain
  included via `consume_shot` / `_try_ground_fire` /
  `_fire_chain_link`), explosive impacts emit a SECOND event at the
  impact cell (`explosive_blast`). Hearing = flat Chebyshev radius
  (walls don't block), hostile-reading un-engaged combatants only —
  dormant deaf, engaged skip, non-hostiles ignore gunfire (SETTLED
  22). A hearer gains an investigation GOAL at the sound origin
  (latest wins); guards hear only within their leash of the sound
  (area guardians, SETTLED 37). Player feedback is ONE reaction
  line per fresh-hearer event — "Something to the {direction} heard
  that." — 8-way player-relative, never for quiet weapons (noise ≤2)
  or enemy fire; no guide entry (communicated in play, user ruling).
- **Ground movement modes (doc 48 phase 5)** —
  `ground_npcs.move_ground_npcs`: peace = the 1-tile stroll; while a
  ground fight is live (`_rules_ground.combat_active`), every
  un-engaged entity moves its spec AP in tiles — bystanders panic-
  scatter with no brake (SETTLED 36) — and hostile walkers STOP on
  the tile they enter the player's sight (never overshoot; join via
  the existing LOS scans; `_encounter.hostile_in_player_sight`).
  Investigation is GOAL-BASED (SETTLED 37): the walker holds its
  goal until it gains LOS on the goal cell (completes without
  walking when already visible), the goal is unreachable (gives
  up), or a newer event re-stamps — no tick countdown anywhere (the
  5-tick memory retired). Guards settle where the search ends (the
  post re-stamps — a new perch). Squads follow noise as a unit (any
  member's goal draws them; LOS aggro stays individual), patrol
  marches at the leader's AP. The goal + rolled weapon + carried
  stamp all round-trip save/load (`saveload_maps`).
- **Ground range management (doc 48 phase 5)** — the universal
  enemy loop (`combat/_ai_ground`): fire ONE shot per turn inside
  the rolled weapon's [min..max] with LOS; beyond max or without
  LOS, close one A* step per AP; inside min, back off
  (restoring-steps first, LOS preferred, progress allowed, PINNED =
  inert — cornering is the counter-play, SETTLED 26); leftover AP
  after the shot repositions inside the band for ranged only
  (melee holds — no knife-dancers). Guard leash = the entity's
  rolled weapon `max_range + 2` (`noise.guard_leash`), per instance
  — the hardcoded 8 retired (SETTLED 18/37).
- **Ground identity families (doc 48 phase 3)** —
  `CHAR_CLASS_FAMILIES` (`data/npc_chars/__init__.py`): one LETTER
  per family, members are case variants of it, ONE family color —
  pirate `r`/`R` rust (220,120,80), militia `m` blue, merchant `h`
  green (100,220,140) — the honest crew row (doc 48 phase 6, fixed
  pistol+knife, band-exempt), consortium
  `e`/`E` navy (90,120,200), civilian `c`, machines `d`/`D` bronze
  (200,180,110); fauna are not families (species glyphs, biome
  palettes). The (glyph, color) PAIR is the identity — a char may
  repeat across families when colors separate ≥60. Enforcer `E` /
  gunner `e`; `civillian_bystander` renamed with the `_ID_ALIASES`
  save-compat alias in `find_npc_char`; the uniqueness key is
  (char, fg, elite) — phase 4's faces: trooper `m`, marine `M`,
  sniper bold `M`, pirate brute bold `R` (elite flags exactly
  {brute, sniper}).
- **Ground band scaling (doc 48 phase 4)** — `ground_scale.py`
  owns every band question. `Entity.spawn_band` stamps the site's
  band at EVERY spawn (dig populate via its floor-climbed tier,
  authored layouts via `load_layout(spawn_band=)`, city ambient via
  planet tier, prison activation via band=floor, quest camps +
  guardians via planet tier, boarding wrecks via the city planet;
  0 = derive from context — dig cache keys re-climb, else band 1 —
  the legacy-save bridge). Stats: base 10 + 5×(level−1)
  (levels 3/10/18/30) split by the spec's six `stat_weights`
  (largest-remainder; space tail a flat 0.05×3; bystander ALL-zero =
  the exemption); combat math reads
  `GroundEnemyInstance.stats`/`.band`, never spec fields (authored
  stats + `weapon_pick` retired, grep-pinned). Weapons: specs name
  FAMILIES, bands roll the tier window (B1 {1}; B2 {1,2} 70/30;
  B3 {2,3} 30/70; B4 {3,4} 30/70; `pin_window_top` = the sniper's
  top tier; empty tiers snap up — explosives sit t3-t4). Equip- and
  drop-time quality ride the band ladder (B1 == KILL ladder). The
  target card title states `LVL <level> <name>`.
- **End states** — all dead = VICTORY; survivors out of sight =
  DISENGAGED (they keep wounds — HP syncs to `entity.hp`, so
  re-engaging never heals them) (`combat/_rules_ground.py`).
- **Guard leash** — guard NPCs abandon chase beyond their rolled
  weapon's `max_range + 2` and return to post; investigation is
  goal-based (see Ground movement modes) — no tick memory
  (`combat/_ai_ground._chase_goal`; `noise.guard_leash`).
- **Enemy consumables + AP (doc 48 phase 5)** — per-spec AP
  (`NpcCharSpec.ap`, default 4; predators 5-6, anchors 3) derives
  through `_ground_effects.enemy_ap_total` (the cybernetics
  `ap_bonus` seam — no wearers yet). Consumables are PRE-ROLLED
  once onto `Entity.carried_items` at first combat entry (same
  distribution as the death roll, consumable subset) — what they
  drop is what they carry: med pack at ≤50% HP (heal + regen),
  stim with LOS when not stimmed (+AP ×3 rounds), ANY carrier, use
  AP spent apart from the dodge ledger, approved log lines
  ("{name} uses a Med Pack." / "{name} injects a Combat Stim.");
  effect state is fight-scoped (never serialized; the dead never
  regenerate).
- **Math** — hit = accuracy + reflexes/2 − target reflexes/2 − move
  dodge − point-blank 35/cell inside min range; damage = base +
  str/5 melee − armor (plasma halves armor, `armor_bypass` ignores),
  min 1 (`combat/_rules_ground.py`, `_ground_math.py`).
- **Explosives with friendly fire** — miss splashes half damage on
  neighbors including the player (Demolitionist boosts)
  (`explosive_blast`).
- **Trait verbs** — Charger melee lunge (range = AP pool, +5 hit/+1
  dmg per tile); Deadshot railgun (+5 hit/+4 dmg per AP >2, kills
  chain auto-shots ≤12 links) (`combat/_ground_charger.py`,
  `_ground_deadshot.py`).
- **Kill drops** — authored pools (trade goods, tier-filtered
  equipment, field stacks) plus the diegetic kit: the enemy's
  resolved weapon always falls with one matching ammo stack
  (field sizing 1–5) AT its equip-time rolled quality — no
  re-roll (the weapon+quality stamp persists on the entity across
  engagements, doc 48 phase 5); extras roll quality at drop time —
  both ladders ride the spawn's band (band 1 == KILL ladder, doc 48
  phase 4); `GroundWeaponSpec.loot_droppable=False`
  keeps organic monster parts and fists off the floor; pools are
  beyond-the-weapon extras only; the pre-rolled carried stamp is
  the ONE resolution for consumable entries — unused charges drop
  at their remainder, used ones never do, ammo keeps the death
  roll (doc 48 phase 5); a very rare tinker-kit roll
  draws after the pad roll (doc 47.5); everything shares the
  silent 30-entity cap (`combat/_actions.spawn_kill_drops` /
  `_spawn_kit_drop`; pools authored in `data/npc_chars/`).
- **Player kit** — HP 20 + stamina/3 + armor + traits; AP 4 +
  bonuses; reload costs AP in combat (free at dungeon screen);
  consumables with timed effects; equipment swaps cost 1 AP
  (`combat/_rules_ground.py`; `ground_reload_ui.py`,
  `ground_consumables.py`).

## Cities & ground life

- **Kit vs module** — `city_kit.py` owns the shared skeleton (base
  tiles, terminal trio, indoor showroom seating, transit bay/stop
  painters, forecourts, metadata); `*_city.py` modules author only
  terrain + landmarks and NEVER place ships themselves. 27
  `city_layout_id` dispatch entries; unknown ids fall through to a
  grid city built from PlanetSpec buildings (terminal trio, no
  ships — grid cities have no authored showroom)
  (`city_builder.py`: `_LAYOUTS`, `_build_grid_city`).
- **Shared city tail** — every city (authored or grid) gets transit
  stations, ambient NPCs, and seeded light after build
  (`city_builder._finalize_city`).
- **Building stamping** — authored exteriors copy in at fixed
  origins; exactly one entrance; doors BFS-routed to nearest road/
  plaza with sidewalk; roof bands carry readable layout-id labels;
  deterministic seeded skyline fills free blocks (`city_layout.py`:
  `stamp_city_assets`, `paint_roof_labels`, `paint_skyline`).
- **Building records** — entrance cell ↔ interior layout id ↔
  resident npc_id, cache key `city:{planet}:{label}`
  (`city_layout.building_records`).
- **PlanetSpec drives everything** — buildings, showroom manifests
  (bare ordered ship-id tuples, seated onto the spaceport interior's
  `S` berths by the kit),
  `city_layout_id`, `interior_layouts`, transit stations, NPC
  population, theme, produces/demands, mech/armory stock, tech
  level, mission tier, `explorable_site_name`+`dungeon_params`,
  `dark_berth`, per-planet dig config (`dig_min_floors`/
  `dig_max_floors`, themed `dig_prefixes`/`dig_suffixes`,
  `dig_params` override); modules auto-register by exporting `SPEC`
  (`data/planets/__init__.py`: `PlanetSpec`, `load_planet`).
- **Port/militia/explorable predicates** — Land needs a `spaceport`
  building; landing scan needs a `militia` building; Explore needs
  `dungeon_params` (`has_landable_port`, `has_militia_presence`,
  `has_explorable_sites`).
- **Monthly shop stock** — mechanic/armory inventories are per-planet
  overrides or seeded tier-filtered samples, stable per calendar
  month; armory hides `shop_available=False` monster weapons
  (`resolve_mech_inventory`, `resolve_armory_inventory`).
- **Terminals** — trade (`=`) / mechanic (`%`) / armory (`A`) bump
  entities placed by the kit relative to the hangar; exterior props
  can carry `interaction_flavor` (`game_interactions.
  _resolve_terminal_blocker`).
- **Showroom ships** — displays stand on `S` (`SHOWROOM_BERTH`)
  markers inside the spaceport interior (the marker renders BLANK —
  tiles that host standing entities render blank so the world
  renderer's entity underlay never superimposes glyphs; an unseated
  berth is visually plain floor), seated from the city
  manifest in reading order by the ONE shared helper
  (`city_kit.seat_showroom_ships`), re-seated on every interior
  entry (idempotent strip + re-seat), with the player's owned model
  never displayed (its berth seats nothing; nothing serializes).
  Bump unowned = buy with trade-in — indoors the purchase parks a
  FRESH owned entity on the parent pad anchor
  (`game_flow._park_indoor_purchase`, nearest-free-cell fallback)
  and empties the room (`strip_showroom_ships`); outdoors the
  display itself is re-anchored. Bump owned = ship menu + launch
  (`game_interactions._resolve_ship_buy`, `_resolve_ship_blocker`).
- **Transit** — stations are authored data; rides are free, instant,
  one action, drop on a scanned clear cell beside the destination
  stop; arrival pulse blooms the stop's colour ~0.6s with the light
  grid snapshot-restored (`city_transit.py`: `resolve_transit_station`,
  `animate_transit_arrival`).
- **City NPC life** — one entity per catalog entry, per-NPC seeded
  RNG keyed INIT_SEED+city+id so routes never reshuffle; citizens
  pick far landmarks and A* one cell per tick, shoppers pause 3–8
  ticks; `wander_radius` 0 = hold (`data/city_npcs.py`;
  `city_npcs.py`: `place_city_npcs`, `move_city_npcs`).
- **City hostility** — bump reads the broadcasting sheet via
  `spec_is_hostile`; hostile = direct-contact fight reusing the
  shared combat runtime; friendly = bump line
  (`city_npcs.is_hostile`, `run_city_fight`).
- **Interiors** — bump a door with a record: cached authored room
  (must have `P` + exit tile), resident NPC seated, quest NPCs seat
  per planet `quest_npc_spots` while their step is live, and
  service NPCs seat unconditionally per planet
  `service_npc_spots` (doc 40 phase 5); showroom displays seat per
  current ownership (doc 45); NPC seaters never choose `exit` or
  `showroom_berth` cells; resume always re-enters at the entry
  spawn (`city_interiors.py`: `_interior_for_record`,
  `_first_interior_npc`). Every `*_interior.layout` passes the
  load-time P/exit placement gate — exactly one exit on the south
  perimeter, `P` adjacent and off the wall row — one shared pure
  predicate (`city_landmarks.door_placement_error`) also mirrored
  by the layout editor's CITY-mode validation.
- **Landing flow** — Land → dark dock gate → cargo scan → city map
  build with ship glide; ground HP fully restores on landing;
  `militia_scanned` clears (`game_interactions._resolve_planet_land`,
  `_enter_city_landing`).
- **Launch** — bump your docked ship: hangar menu; the same entity
  animates offscreen and returns, keeping identity; launch spawns
  space with a spawn-exclusion ring (`city.py`: `_launch_to_space`).
- **Ground gear** — strength-capped expedition pack (4 + 1/5 STR
  over 10), 2 weapon slots, five armor slots (incl. the cybernetics
  subfamily — eyes/torso/arms/legs pieces whose
  `ap/hit/melee/hp_bonus` fields are the cyber identity,
  `data/ground_armor/vests.py`); per-weapon magazines +
  ammo types (6), reload picks among weapons sharing the ammo
  (`ground_equipment.py`: `expedition_capacity`; `data/ground_items/
  ammo.py`: `AMMO`).
- **Consumables** — med_pack heal+regen, stim +1 AP, tinker kit
  quality-raise (loot-only, never sold — doc 47.5); AP-costed in
  combat, stack decrements only after the effect validates
  (`ground_consumables.use_consumable`; the kit intercepts
  earlier, at the manage modal — see Tinker kits).
- **Absent:** citizen day/night schedules; transit fares/fuel;
  shopping inside interiors (outdoor terminals only); crime/witness/
  city-guard systems; weather; survival needs.

## Dungeons, landmarks & extensions

- **BSP generation** — seeded recursive splits + L-corridors, EXIT
  in a wall near root center; `DungeonParams` per planet drives
  size/rooms/monster pools/cache guardians/panels/fungus
  (`dungeon_bsp.py`; `dungeon_params.py`).
- **Cave fungus** — 0–2 glow patches per room; the light hook that
  extends sight in dark dungeons (`dungeon_bsp._scatter_fungus`).
- **Population** — density × tier squads scattered ≥5 from spawn,
  never on stairs/footprints; panels scatter from an isolated
  seeded stream so generation sequences never shift
  (`dungeon_population.py`).
- **Layout grammar** — `MAP/ENDMAP` + directives `TILE:`/`COLOUR:`/
  `LOOT:` (room-typed pools)/`ENEMY: g = id@chance#min-max` (floods
  its connected room); markers: `P` spawn (exactly one), `C`
  console, `E` engine, `T` terminal; `{}` hull groups make walls
  LOS-transparent (`layout_format.py`; `dungeon_layout.py`).
- **Landmark entrance contract** — the single link point is an
  explicit `landmark_entrance` tile (glyph `e`, renders X); with
  it, interior `dungeon_door` tiles are unlimited; without, exactly
  one door serves; ≤1 arrival/console/stairs_down each, violations
  raise at stamp time (`landmark.py`: `_resolve_entrance_cell`,
  `_landmark_markers`).
- **Landmark stamping** — origins ranked farthest-from-spawn;
  route-before-stamp (failed attempt leaves the map untouched);
  weighted variants `LandmarkVariant(layout_id, weight)`
  (`landmark.py`: `stamp_landmark`, `choose_weighted_variant`).
- **FOV/fog** — Chebyshev rays stop at walls/closed doors; hull
  groups share visibility; seen is permanent; lit sources inside
  LOS extend sight (`dungeon_fov.py`: `reveal_around`).
- **Auto-explore (O)** — BFS to nearest unseen (boundary walls
  count); stops on newly-visible interesting content; only VISIBLE
  solid entities block (dormant units always block); single
  "blocks the only way forward" report for sealed exits
  (`autoexplore.py`: `run_auto_explore`). Blockers read from a
  per-plan occupancy snapshot and FOV hull-wall seeds from a
  per-map cache (doc 48 phase 6 perf pass — 4.5x on big decks).
- **Go-to (G)** — picker over discovered targets, shared stop
  semantics, stops 8-adjacent; interaction names override tile
  titles (`autoexplore.py`: `run_dungeon_goto`).
- **Dungeon extensions** — reusable themed multi-floor dungeons off
  a parent map; shipped: `mars_alien_prison` (5 floors, all content
  in code). Floor = BSP with EXIT→STAIRS_UP, themed features,
  farthest STAIRS_DOWN, event anchors, dormant stocking; cached
  under `extension:<id>:floor:<n>` (`dungeon_extensions.py`;
  `data/dungeon_extensions/__init__.py`).
- **Extension interactions** — data glyphs: state flags (engineering
  console, data terminal) + floor transitions gated on state; an
  interaction's `objective_type` completes the live quest step
  (`dungeon_extension_interactions.py`).
- **Route-progress events** — one-shot encounters at walkable-
  distance fractions along the stairs route; `route_direction: up`
  stages escape ambushes (`dungeon_extensions.tick_activation`).
- **Dormant security** — pre-placed `powered_down` units docked in
  carved one-opening wall alcoves (never adjacent, never near
  transit); events wake squads by prefix; lockdown spreads reserves
  (`dungeon_activation.py`: `_stock_dormant_security`,
  `activate_dormant`).
- **Facility phase** — derived, never stored: dormant→waking→rising
  →lockdown from activated events + the data-extract flag; the
  extract alarms the current map AND every cached floor
  (`dungeon_activation._facility_phase`, `apply_lockdown_all_floors`).
- **Deep cell** — authored bridge landmark becomes the new entry;
  dead flavor terminals scattered (`dungeon_extension_deep_cell.py`).
- **Surface dungeons & delves** — Explore builds/caches
  `surface:<pid>` from `dungeon_params`; the active delve step
  stamps a camp (weighted `delve_layout_variants` machinery exists —
  **no authored step uses it yet**, all three delves use bare
  `delve_layout_id`), places the Quest Cache at the authored `%`
  marker (exactly one honored; zero-or-many silently falls back to
  deepest interior) and spawns guardians at generation time
  (`game_interactions._build_surface_dungeon`; `main_quest/_delve.py`).
- **Dig sites (doc 42 phase 4)** — three RNG-rare discovery doors
  (humanoid ground kills 1-in-12, generic derelict interiors 1-in-8,
  a derelict C terminal's first power-restore 1-in-6; `data/digs`
  `DOOR_RATES`, `digs` helpers) reveal a site derived pure from
  INIT_SEED: `digs.reveal_site` picks planet/name/depth (depth is
  never stored) and records `{id, planet, name}` on
  `ctx.discovered_sites` (saved; New Game clears); readout via
  `rumor.present_hearing`, pointer lines in the RUMORS tab. The
  planet menu gains one "Explore <name>" row per discovered site
  (no quest gate). Floors are BSP-generated from
  `digs.derive_dig_params` (planet theme tiles + `data/digs`
  TIER_POOLS at `mission_tier`, four bands, densities
  1.0/1.4/1.8/2.2; the floor band climbs tier + floor − 1 capped 4;
  `spec.dig_params` overrides),
  persist per floor under `dig:<planet>:<id>:<floor>` — the cache
  key is the identity source, no dig attributes on maps; floor 1
  keeps the EXIT, deeper floors swap it for STAIRS_UP, non-bottom
  floors gain a farthest STAIRS_DOWN (footprint-aware); landmark
  rooms sprinkle seeded per site+floor (`landmark.stamp_landmark`);
  caches scatter planet `produces` goods or tier-banded gear
  through the pluggable `DigLootSpec` (doc 47.2: 1-in-4
  `equipment_rate` carries gear from monotone `tech<=band` pools,
  rolled at `quality_rates`; `digs.py`; `data/digs`).
- **Bump-to-swap (doc 42 SETTLED 39)** — ground population monsters
  are faction-checked as everywhere: bumping a NON-hostile one
  swaps places instead of blocking — one shared
  `ground_npcs.swap_step` across the player move, autoexplore/goto,
  and the headless debug executor; hostile guards block and fight;
  autoexplore plans through allies (`steps_aside_ids`) and the swap
  refuses transition tiles. Bump lines resolve nameless monsters
  through their spec (`ground_npcs.display_name`).
- **Absent:** per-save dungeon regen (interiors cache is permanent);
  mobile dormant AI; extension content beyond the prison.

## Quests, missions & story

- **Chain structure** — 36 steps as frozen catalog rows linked by
  `requires_step`; Act 0 prologue (5) + four faction chains
  (merchants/bar/militia/lab) + Act 1 prison + epilogue rewards
  (`data/main_quest/act0_*.py`, `act1_*.py`; `main_quest/_core.py`).
- **Time gates** — `wait_days` parks the next step with an absolute
  date; per-frame check flips it and queues the faction summon
  (`main_quest/_gates.py`: `check_quest_gates`).
- **Save migrations** — declared RENAMES/BACKFIELDS/FOLDS/RETIRED
  tables remap old progress onto the live catalog (`_gates.py`;
  `data/main_quest/migrations.py`).
- **Step rewards** — credits/xp/rep (broadcast-routed)/unlock item/
  quest perk/mission-hold goods (reserved, released by next step)
  (`_core.py`: `_apply_completion_rewards`).
- **Quest perks** — `smugglers_instinct`, `warrant_license`,
  `lab_credentials`: free trait grants outside ALL_TRAITS; perk
  grants force-refresh boards (`_grant_quest_perk`).
- **Objective handler registry** — 10 types (talk/payment/goods/
  smuggle/salvage/visit/bump/delve/bounty/prison) as frozen hook
  dataclasses; dispatch never branches on type
  (`main_quest/handlers.py`).
- **Decision point** — `prologue_seek_help` 4-way fork: one-way
  `locks_chain` on empty `main_quest_chain` + `backing_faction`
  recorded; one-shot behavior is EMERGENT (status transitions +
  empty-chain gate), not a data field
  (`main_quest/_dialogue._lock_in_chain`).
- **Smuggle crates** — story crates ride as `mission_reserved`
  reservations; hot-contraband loss re-offers via the giver;
  non-hot payloads auto-reload; next smuggle auto-triggers
  (`_core.py`: `_trigger_smuggle_crate`, `_maybe_auto_trigger_next_smuggle`).
- **Dispositions** — one-time Mars-orbit scene after the prison:
  delivered → chain-keyed epilogue reward step; kept → pending
  text, no step (`main_quest/_act1.py`).
- **Quest spawns** — bounty/salvage steps stamp leader + escorts +
  wreck on system entry; leader kill completes; guards tombstone;
  salvage securing pops the wreck + interior
  (`main_quest/_spawns.py`; `_objectives.secure_quest_loot`).
- **Faction heat** — data tags on steps: `militia_scan` (bar-heat
  scan floor), `militia_aggro` (charged-cell), `consortium`
  (pirate-heat squads); expire when the tagged step completes
  (`main_quest/_heat.py`).
- **Quest NPC presence** — per-step `npc_presence` ∩ planet
  `quest_npc_spots`: experts seat inside authored interiors while
  live, vanish on completion (`main_quest/_act0.py`).
- **Mars set-piece** — signal on first Sol jump-out; surface door
  landmark conceals stairs; bump animates the barrier split; prison
  starts on descent, completes via Floor-5 terminal
  (`_act0.py`: `maybe_trigger_signal`, `bump_mars_door`).
- **Quest log** — breadcrumb leads with the main quest; Q log lists
  ≤5 missions, abandon aborts cargo/returns missions to their exact
  board/removes spawns (`menus/_quest_log.py`; `main_quest/
  _breadcrumb.py`). Q opens LOGS with QUESTS/RUMORS tabs — the
  shared multi-pane tab treatment (`pygame_screen.draw_tab_bar`,
  origin y per host; TAB/SHIFT_TAB outcomes, host loop flips the
  sheet).
- **Rumors (lore)** — knowledge as currency (doc 42): frozen
  `RumorEntry` chains in `data/lore/` (the dark-ports chain — sources
  are planet-scoped `(npc, planet, faction, floor, trait)` candidates
  with authored `picks` width; trigger-delivered tiers carry
  `triggers` and no sources), prose single-sourced in
  `data/text/08_rumors.json` (`rumor.<id>.*`); keyring
  `ctx.known_rumors` saved in heard order; pure resolvers in
  `rumor.py` — `askable_topics(known, rep, traits, npc, PLANET,
  live=map)` is the ONE ask surface, scoped to the current planet and
  the run's live routing; source floors ride the talk_gate shape read
  off the resolved sheet (dark reads neutral); hearing records
  verbatim through `rumor.present_hearing` (the ONE readout path —
  hosts, triggers, pads); the RUMORS tab renders the ledger verbatim
  in heard order plus the dig-site pointer lines from
  `ctx.discovered_sites` (`digs.pointer_lines`) (`npc.py`:
  `_handle_ask_around`; `rumor.py`: `hear`).
  Seed routing (phase 3): pure INIT_SEED derivations in
  `rumor_routing.py`, nothing serialized — `live_routes` picks each
  entry's live candidate pairs (≥1 guaranteed; CONTINUE-stable,
  Shift+S reroll-legal), `live_holdings` picks the exclusive holder
  from `dealers.EXCLUSIVE_CANDIDATES`, `choose_dark_groups` marks
  max(1, groups//4) ambient pirate groups dark (the per-tick
  stragglers roll `flies_dark_coin` at the same rate). Discovery
  doors: landing at a `dark_berth` port logs "This port didn't
  verify any credentials." every landing and fires `dock_dark_port`
  once (`game_interactions._dark_port_landing_beat`); hailing a
  dark hull (no Broadcast line — `identity.npc_identity` returns
  None for `Entity.flies_dark`, round-tripped on
  `ProceduralSpawn.flies_dark`) fires `dark_hail`
  (`comms._run_interaction_modal`); kills drop teaching pads while
  unheard (`data/lore/finds.py`; `loot.maybe_spawn_pad` — knowledge
  is the item, nothing held).
  Favor exchange (phase 2): `DealerSpec` rows in
  `data/lore/dealers.py` key the books by ROLE id — `ctx.rumor_favor`
  `{favor, earned}` ledgers saved beside the keyring;
  `offerable_rumors` never buys an entry the dealer authors as a
  source (no selling back to the teller, playtest ruling);
  `exclusive_offers` hides priced rows until affordable and takes
  the live holdings as an explicit input; the ask sub-menu carries a
  live `Favor: N` line rebuilt per pass. The Whisper shady tech —
  ALWAYS on the city map by the containers (playtest ruling:
  knowledge gates the row, not the existence; plain population
  citizen) — sells the 2000cr cut-out through the passphrase row
  "The Hush sent me." (`npc._PASSPHRASE_ROWS`, keyring-gated;
  `identity.py`: `CUTOUT_BROKERS`). Dev: Shift+N logs the live
  routing (`dev_mode.log_rumor_routing`).
- **Mission boards** — keyed `(npc_id@planet)`; monthly refresh;
  slot fill from static catalog then faction generator; tier bands
  by planet `mission_tier` (+1 guild trait); militia/lab boards
  post nothing until their quest perk, then tier 3–4
  (`mission/_board.py`).
- **Faction generators** — merchants delivery, bhguild bounty, bar
  weighted intercept/smuggling/salvage, militia warrants
  (reflagged bounties), lab specimen runs; militia has NO static
  catalog; completed statics never repeat (no `repeatable` field)
  (`mission/_proc_*.py`; `data/missions/`).
- **Mission lifecycle** — 5-mission cap, cargo reservation on
  accept, early-delivery bonus %, late = half pay zero xp, rewards
  with tier-scaled rep + soft cap; abort releases cargo and removes
  spawned targets (`mission/_lifecycle.py`).
- **Tutorial** — forced Human Merchant Earth start, pre-seeded
  bounty board (Crimson Jack), ordered popups, guaranteed level-up
  before the finale lifts board suppression (`tutorial.py`).
- **Runtime text** — all quest prose in `data/text/*.json` keyed
  `step.*`/`npc.*`/`runtime.*`; code passes literal defaults; dev F5
  hot-reloads; lint checks coverage (`text.py`; `tools/quest_lint.py`).
- **Absent:** quest hooks in comms; repeatable missions; branches
  beyond the 4-faction fork + 2 dispositions.

## Economy & trade

- **Price curve (pure)** — stock/target ratio: shortage 2.0×→1.0×,
  surplus 1.0×→0.6×, floor 1cr (`trade.trade_price`).
- **Buy/sell** — buy = price × merchant-attitude modifier (the worn
  ID's sheet); sell = 75% of buy × modifier; shared by transaction
  and display (`trade.py`: `_unit_price`, `_sell_price`).
- **NPC ship trade** — ephemeral stock (3–8/good from the spec's
  `cargo_goods`), buy base×1.2 / sell base×0.5 × faction attitude;
  enemy/disliked refuse (`trade.py`: `open_npc_trade`).
- **Market intel** — merchant enemy/disliked: flat catalog; neutral:
  WANTS/SELLS CHEAP grouping + colours; liked: per-good headroom;
  allied: guild-network best-sell destination across visited
  planets (`trade.py`: `_market_intel_enabled`; `trade_market.py`).
- **Economy** — first visit seeds produced=target/demanded=0;
  drift ±1 toward target **once per game day** (via
  `time.advance_time` — not on jump/launch) (`trade.py`:
  `_seed_economy`, `tick_economy`).
- **Cargo model** — `cargo_used` = ammo + `mission_reserved` +
  inventory; capacity = hull + module bonus; full-screen hold modal
  with jettison (`ship.py`: `cargo_used`; `trade.open_cargo`).
  Every weapon-ammo mutator (install/remove/`buy_ammo`) recalcs
  `cargo_ammo` = the full-magazine reserve (`total_ammo_cargo`).
- **Mission-reserved space** — deliveries reserve on accept,
  released on complete/abort/fail; heist pickup reserves its
  volume; mission cargo never enters the sellable hold
  (`mission/_lifecycle.release_mission_cargo`; `loot.
  _secure_heist_cargo`).
- **Contraband** — `category="contraband"` goods sell only where
  listed in produces/demands (`trade._can_sell_here`).
- **Smuggler's hold** — hidden volume from smuggler modules
  (Mk1 10 / Mk2 25 / Mk3 50) + Smuggler's Instinct perk (+10% hull,
  min 1) (`ship.smuggler_hold_capacity`). The shared cargo body
  states hold capacity/free on all three cargo surfaces (modal,
  character CARGO tab, hangar CARGO tab; zero capacity stays
  silent) derived from the scan's own consumption so the display
  cannot drift from the scan; the Q-log's scan-risk label honors
  the perk like the scan does (doc 47.4 SETTLED 30)
  (`trade._cargo_body` → `navigation_scan.smuggler_hold_usage`).
- **Scan exposure (computed before the roll)** — smuggle missions
  claim `required_cargo_size` first (overflow auto-fails the
  mission), remaining capacity shields inventory contraband; exposed
  crates confiscate at fine = base_price×qty//2; landing scans =
  flat 40% on militia-presence planets, space scans ride the
  auto-hail without a second roll (`navigation_scan.py`:
  `_compute_scan_exposure`, `_run_cargo_scan`, `_run_space_cargo_scan`).
- **Loot** — wreck/delve interiors roll a credit budget from the
  ship spec's `loot_budget` across ≤4 passes from per-room pools;
  placed interiors persist in `ctx.interiors`; pickups route by
  type (equipment packs with drop-or-leave, stacks, cargo with hold
  check, modules → ship storage — doc 47.3); doc-42 pads
  (`{"teaches": id}` / `{"reveals_site": True}`)
  are consumed on pickup — knowledge never enters the hold
  (`dungeon_layout.py`: `_scatter_loot`; `loot.py`;
  `loot_selection.py`; `digs.reveal_site`).
- **Loot presentation & entity economy (doc 47.1)** — the `%`
  glyph's hue answers content at every constructor including the
  save/load restore path (equipment steel, field items amber,
  cargo gold, quest pads/caches violet, mission cargo cyan —
  `loot_common.loot_fg`; the equipment hue BRIGHTENS by quality
  tier, other categories ignore it — doc 47.2); ONE
  identity-based 30-entity cap on
  both kill paths evicts the oldest plain loot silently and never
  quest caches, pads, or heist cargo (`loot_common.enforce_loot_cap`);
  character-screen Discard drops the carried item at the player's
  feet, never destroys — space mode hides the verb, there being no
  floor (`character_screen._discard_pack_*` →
  `loot._drop_expedition_*_at`, `floor_available` threaded from
  the C-key's `current_mode`); leaving a one-shot derelict
  interior with floor loot confirms first (`GameMap.derelict_interior`
  — capture boardings + generic derelicts, save/load round-trip;
  "ABANDON THE DERELICT?" / Leave / Stay), while cached mission
  wrecks, digs, and city interiors are revisit-able and never
  prompt (`game_flow._derelict_loot_remains`).
- **Quest loot security** — quest-cache pickup completes the step in
  the same action; goods NEVER enter the sellable hold (enforced
  structurally via reservations + `secure_quest_loot`, not at the
  sell counter) (`main_quest/_objectives.py`).
- **Loot quality system (doc 47.2)** — stored gear carries a rolled
  tier above base (0): tokens Modded/Overclocked/Prototype
  (user-verbatim) title-cased at the one `display_name` label seam
  (`ground_equipment`); integer-hundredths multiplier rows scale
  weapon damage+accuracy and armor defense+4 bonus fields via
  `effective_*_spec` (`dataclasses.replace` copies; catalogs stay
  descriptive; the module family row + `effective_module_spec`
  landed doc 47.3); the legendary row (4) activates ONLY at
  RNG-delve bottoms (doc 47.4 randarts — no other source rolls
  it). All scaled stats ceiling-round in magnitude (SETTLED 18 —
  a tier never lands on its base value). Rates are authored
  1-in-N ladders checked rarest-first (KILL/WRECK/DIG in
  `data/quality.py`). Quality rides: `StoredGroundEquipment` +
  `GroundWeaponInstance` fields (every equip/store/swap/install/
  reload reconstruction preserves it), the equipped-armor dict
  (`dict[slot, StoredGroundEquipment]`, legacy bare-id saves
  migrate to base), NPC weapon rolls at EQUIP time gated on
  `loot_droppable` (what was firing at you is what drops),
  combat math end-to-end (one weapon, one stat set: enemy AI,
  player fire paths, explosive splash, deadshot chains, HUD
  readouts — `combat/_ground_math` owns the raw fns), and drop
  sources (kill extras, wreck room pools 1-in-3 per
  engine_room/personal_storage marker, dig caches 1-in-4).
  Economy: armory sell = exact `price//2` at base, integer-exact
  `(price*pct+100)//200` above, min 1; shops never variant.
  Save/load: `parse_quality` migrates all shapes; `loot_data`
  quality keys ride wholesale.
- **Ship module loot (doc 47.3)** — modules are a sixth loot
  payload: `item_type "module"` pickups append a quality-bearing
  `StoredEquipment` to global ship storage — no pack check, one
  log line, glyph reads the equipment hue + brightness
  (`loot._apply_module_loot`; `loot_common` maps module →
  EQUIPMENT_FG). Sources: INTACT CAPTURES strip the whole flown
  `modules` list at the quality it flew — per-module KILL-rate
  rolls at combat entry (`_stats._roll_flown_modules`; enemy
  hull/shields/skill sums scale through `effective_module_spec`)
  with the strip seeding engine-room markers from
  `cr.boarded_modules` (stamped at `_space_boarding`; no
  re-roll) — while DEAD hulls (wrecks, derelicts, mission
  salvage) never strip, room scatter only; wreck rooms host
  authored module pools (`dungeon_layout._ROOM_MODULE_POOLS`:
  engine_room → engine-slot, cargo_bay → system-slot, 1-in-4
  per marker — no "systems" room exists in any layout).
  `OwnedShip.modules` is `tuple[StoredEquipment, ...]` (legacy
  bare-id saves migrate via `ship.parse_module_entry`);
  `MODULE_MULTIPLIER_PCT (100,115,130,145,220)` scales all ten
  bonus fields in magnitude with ceiling rounding (SETTLED 18);
  sell = `(price*pct+100)//200` min 1 at the one `_sell_price`;
  shops and buy paths stay base. No module id is barred from
  payload/pool/strip paths (themed capture sources are doc 48's
  authoring).
- **Legendary randarts + credit containers (doc 47.4)** — the
  delve bottom is the ONLY quality-4 source: every RNG dig's
  bottom floor places one extra cache holding a module payload
  (base rolled uniformly from the catalog, quality 4, seeded;
  non-bottom floors and every other source never produce 4 —
  `DigLootSpec.legendary_bottom`, `digs._scatter_dig_loot`). A
  randart is its SEED: `roll_randart(module_id, seed)` derives
  the name + 2-4 distinct signed axes deterministically (same
  seed → same manifest all run; seeds draw ≥1 —
  `parse_randart_seed` migrates 0 to not-a-randart); the
  composed name IS the label, base identity lives in the detail
  row (`data/randarts.py`). Axis COUNT is band-weighted
  (`DigLootSpec.legendary_axes_weights`: T1 digs lean 2-stat,
  band-3 lean 4) with the seed the sole identity — no count
  threads any read path. Deltas apply on top of the
  ceiling-rounded scaled base (`effective_module_spec(…,
  randart_seed=…)`); engineering 3-10 is pure randart territory;
  axes never price (sell stays the phase-3 formula at the 220
  row). Pickup fires the LEGENDARY FIND modal (ScreenFrame
  body_runs) listing the COMPLETE effective sheet — the scaled
  base's own nonzero fields alongside the rolled axes, in
  axes-table order (SETTLED 27). Credit containers:
  `{"credits": N}` payload adds credits + log line, gold hue;
  chips scatter in wrecks and digs (40-120), the dig rare-cache
  lockbox (300-900, `lockbox_rate`) — the `wreck_scatter=True`
  kwarg gates every dead-ship-only scatter pass (chips and
  tinker kits alike) at exactly the three dead-ship
  `load_layout` callers. Dig caches can roll off-world goods the
  planet does not produce (`out_of_produce_rate`).
- **Tinker kits (doc 47.5)** — a stackable consumable that
  raises one owned item's quality one tier, capped at prototype.
  Very rare loot-only drops on the three ground paths (kill
  1-in-40 after the pad roll, wreck scatter 1-in-12, any dig
  floor 1-in-16 after the legendary placement — every roll draws
  after all pre-existing draws on its path; rates are authored
  `KIT_*_RATE` constants in `data/quality.py`, pinned by test);
  never shops (`GroundConsumableSpec.shop_available=False` gates
  the armory buy rows — the load-bearing default-True field),
  never exterior space kills, no delve-bottom guarantee. Use
  from the pack's consumable manage modal intercepts at
  `character_screen._manage_consumable_stack` →
  `tinker.try_manage_kit` (returns None for non-kits, falling
  through to `use_consumable`); one CHOOSE TARGET chooser over
  every eligible owned entry across SIX containers — equipped
  weapons, equipped armor, expedition pack, armory warehouse
  (`ground_armory_storage`), mechanic ship-storage modules
  (item_type "module" only — space weapons never variant),
  installed modules — rows preview `current -> next` token,
  title TINKER KIT, body the self-explaining effect_label (no
  guide entry, SETTLED 36). Eligibility is quality 0-2 with no
  randart seed (SETTLED 31 — prototype items and randarts never
  list), re-checked inside every apply; the bump is one
  `dataclasses.replace(entry, quality=q+1)` (all other fields —
  loaded ammo included — preserved; stats/labels/sell re-derive
  through the existing seams); a charge is consumed only on a
  completed bump (`ground_consumables.consume_kit_charge` via
  `_decrement_stack`); unsellable like every consumable. The
  row and the apply share ONE `_Target` walk per container
  (`tinker.eligible_targets`) so the chooser can never drift
  from what it bumps.
- **Absent:** `TradeGood.rarity` deleted (doc 47.2 — quest-cargo
  legality is now the explicit `QUEST_LEGAL_MARKET_GOODS` allowlist
  in `tools/quest_lint.py`); no module drops from exterior space
  kills or ordinary dig floors (modules come from raiding — doc
  47.3; the bottom-floor legendary cache is the sole dig-site
  module source — doc 47.4); tinker kits never sell and never
  appear in shops, exterior space kills, or delve-bottom
  guarantees (doc 47.5); no tariffs beyond the confiscation
  fine; no equipment selling at terminals; no persistent
  NPC-trader stock.

## Progression

- **XP/levels** — curve 40 + next-level×25, hard cap 60 (XP accrues
  past cap); 5 skill points/level across six 0–100 skills
  (`xp.py`: `add_xp`, `_apply_skill_point`, `MAX_PLAYER_LEVEL`).
  The C screen's Stats tab reads ship skills as base +
  installed-module bonuses with the delta annotated ("36 (+9)")
  through the SAME sum combat uses (`_stats._player_skill_bonuses`
  — doc 47.4 SETTLED 29); ground stats and bonus-less skills
  stay plain.
- **Milestone traits** — levels 40 and 50: mandatory modal from the
  shared pool filtered by counters/stats; defers if none qualify
  (`xp.py`: `_qualifying_traits`; `trait_screen.py`).
- **Trait catalog** — 17 traits (skill-followers, playstyle
  counters, career 20-mission traits); flat effect accessors on
  xp.py; Ironclad retro-applies max-HP including into live combat
  (`data/traits/core.py`; `xp.py`; `trait_screen._apply_ironclad_hp`).
- **`rep_required` is dormant** — implemented in the qualifier but
  every trait ships None; it reads the TRUE sheet, not the
  broadcast (`data/traits/core.py`; `xp.py:239`).
- **Career board refresh** — Hauler/Fixer/Hunter grants force-
  refresh all boards (`trait_screen._refresh_faction_boards`).
- **Character creation** — base 10 all stats; species/class add
  pilot/ground bonuses; class sets starting credits (25/50/75) and
  cosmetic ship `hp_base` (`character.py`).
- **Playstyle counters** — extendable `PlayerCounters` on ctx; all
  reset on death (`game_context.py`).

## Ships & equipment

- **Ship ops** — weapon/module install/remove with slot re-indexing
  and ammo seeding; effective speed/cargo math (`ship.py`).
- **Ship layouts** — authored grammar: silhouette-first `{###}`
  hull (LOS-transparent), void tiles, BFS-validated; exactly three
  ship interiors ship (`data/layouts/`: `freightliner_a`,
  `scout_a`, `survey_a`) (`layout_format.py`).
- **Catalogs** — every content type is a frozen dataclass +
  `find_*(id)` under `data/` (weapons, modules, ships, npc_ships,
  npc_chars, planets, solar_systems, species, classes, traits,
  pilot_skills, missions, trade_goods, city_npcs, landmarks, lore).

## Meta systems

- **Save model** — ONE autosave (`~/.spacehack/saves/autosave.json`)
  written only by ESC Save & Exit (no per-move/per-landing save;
  death writes nothing); deleted on successful Continue
  (`saveload.py`; `title_flow.py`).
- **Persisted payload** — full state incl. identity fields,
  collected-ID sheets, economy, boards, bounty/quest spawns, city
  NPC positions, interiors cache, RNG state; boarded wreck/planet
  interiors serialize INTO the save (city `city:*` rooms excluded
  so layout fixes reach old saves) (`saveload.py`:
  `_write_dungeon_and_interiors`).
- **Save-time spawn sync** — live entity positions re-match into
  `procedural_spawns` before writing; dead entities drop their
  spawn (`_sync_procedural_spawns`).
- **Load migrations** — heuristic/field-presence based (no schema
  version field): ammo reseed, storage renames, board re-keys,
  disposition backfill, registration re-mint, planet-surface saves
  rebound to `surface:<city>`, module lists migrated to
  quality-bearing instances (doc 47.3) (`saveload.py`,
  `saveload_maps.py`).
- **Map rebuild on Continue** — mode dispatch rebuilds space
  (tombstones skipped) / dungeon (+hidden return pair) / city
  (authored rebuild + saved NPC positions) (`saveload_maps.py`).
- **Dev quicksave** — F6 writes `quicksave.json` (never deleted);
  F9 restores in place (`dev_mode.py`; `game_loop._dev_quickload`).
- **Time** — single choke-point `advance_time` (30-day months);
  month rollover refreshes boards + applies decay + ticks economy;
  the clock advances via `tick_move` at the ship's
  `effective_speed` moves/day (10 is only the fallback); a
  SPACE-wait (`.`) passes a FULL day — the passes run on the old
  day, then the clock flips (`game_loop._handle_wait_event`;
  dungeon/city waits tick their NPCs but not the clock) (`time.py`).
- **Seeds** — `SPACEHACK_SEED` pins New Games in a session; Shift+S
  reroll is DEV-GATED (SPACEHACK_DEV) and ignores the pin; `RNG`
  rebinds on seed; `INIT_SEED` persists for deterministic helpers
  (`engine.py`: `new_game_seed`, `reroll_run_seed`; `title_flow.
  _fresh_seed`).
- **Dev mode** — `SPACEHACK_DEV`: super-frigate, 999,999cr, best
  gear; shortcuts: F3 debug overlay, F5 text hot-reload, F6/F9
  quicksave/load, Shift+X +200 XP, Shift+T teleport-to-port picker,
  Shift+S seed reroll, Shift+R reveal fog, Shift+D +30 days,
  Shift+O Act-0 faction picker, Shift+L blockade manifest,
  Shift+K service run, Shift+G warrant license, Shift+J advance to
  shift boundary, Shift+B toggle cut-out, Shift+N live rumor
  routing, Shift+M force-reveal a dig site, Shift+Y grant a
  tinker-kit stack (`dev_mode.py`;
  `game_loop._handle_dev_event`).
- **Headless save inspector** — `debug_session.py` runs scenario
  tokens (move/wait/reveal/goto/advance) against a copied save,
  read-only, no UI.
- **Guide** — `?` opens 15 sections; modals deep-link via
  `ctx._guide_topic`; content is a Python tuple (`help.py`;
  `data/guide/__init__.py`).
- **Lighting** — additive RGB grids, Chebyshev radius, Bresenham
  occlusion; flicker profiles (steady/buzz/flicker/pulse/alarm) as
  pure functions of the frame clock; dual luma caps (grid 200,
  blend 190); fog-masked; cities seed once; never serialized.
  Emission is a tile-kind table — adding a row is the whole
  extension (`lighting.py`; `data/lighting.py`: `STATIC_LIGHT_TABLE`).
  Static sources derive ONCE per map and cache on it (doc 48 phase
  6 perf pass); `GameMap.replace_tile` is the one runtime tile
  writer and drops the derived caches (light sources, hull-wall
  cells) so the next reveal re-derives.
- **Animations** — pure frame generators + present loops (descent
  elevator, breach sparks, transit arrival pulse); one pacing-
  constants module with a user speed multiplier (`Normal/Fast/
  Faster/Instant`) applied at the four delay choke points
  (`descent_animation.py`, `dungeon_animation.py`,
  `animation_timing.py`: `set_speed_scale`/`scaled`).
- **Presentation shell** — every screen is a pure frame through a
  `run_for_context` loop returning `(outcome, action, selected)`;
  three live modes (city/space/dungeon) with hidden return pairs;
  one main loop with an event dispatch chain; 50ms poll only when
  flickering lights animate (`pygame_menu.py`, `pygame_screen.py`;
  `game_loop.py`: `_run_gameplay`).
- **Spec-sheet buy modal** — the ship-buy body is a sectioned
  ledger (PERFORMANCE/COMBAT/CAPACITY) straight off the Ship spec:
  CP437-safe bar gauges scaled against the catalog's best per stat
  with the player's ship marked, and a base-vs-base `yours:` column
  coloured by trade verdict; exactly one selectable BUY row; flow,
  price block, and outcomes untouched (`menus/_ship_buy.py`).
- **Body colour runs** — `ScreenFrame.body_runs`: per-source-line
  `(text, colour)` segments, the paint-only sibling of
  `body_colors`; plain body text stays authoritative for
  measure/wrap, and run lines paint plain when they wrap or exceed
  the body width; `Palette` carries shared semantic accents
  (muted/positive/negative/accent) for data-bearing screens
  (`pygame_screen.py`: `_body_lines_with_colors`;
  `pygame_ui.draw_text_runs`).
- **Bump dispatch** — occupied tiles route by flag: owned ship →
  hangar/launch, unowned → ship-buy, transit, terminals, boardable
  wrecks (cached interior + breach on first board), NPCs (talk/
  deliver/missions), hostile citizens (fight), powered-down units
  (`game_interactions.py`: `resolve_blocker` family).
- **Action surface** — arrows/hjkl/numpad + yubn; `.` wait; space:
  G goto, M map, T comms, P pickup; dungeon: O explore, G goto, R
  reload, P pickup; everywhere: C character, F factions, Q quest
  log, `\` console, `?` guide, ESC save-and-exit
  (`input_helpers.py`; `game_loop.py`).
- **Engine essentials** — 100×60 grid, 16px CP437 bitmap (sole
  rendering asset) + procedural patches/widened text; shared `RNG`
  for game logic while map generation uses global random
  (`engine.py`).
- **Display prefs** — user config (not save) in
  `~/.spacehack/config.toml`: windowing + animation speed
  (`DisplayConfig.animation_speed`; runtime stitches it onto the
  engine-derived config on Apply, `display_config.py`,
  `pygame_runtime.py`).
- **Absent:** multiple save slots; player-facing seed entry UI;
  audio settings; save-schema versioning.

## Standing rulings that shape design

- **No special cases — uniform mechanisms.** Data opt-ins over id
  lists (dark_berth); one resolver; one gate; "how the game already
  works" is the design language.
- **Penalties/completions are modals**, never log lines; one modal
  per event.
- **Wordless atmosphere** — motion/light/animation beats, not prose
  popups; pure frame generators + present loops.
- **Environment as gate** — danger self-selects for prerequisites;
  verify numbers before claiming them.
