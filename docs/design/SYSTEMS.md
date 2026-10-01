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
  merchant 0, consortium −100 (hidden); species NEVER adjusts (doc 49
  SETTLED 3-B — `_SPECIES_REP` empty); class tables on the ±30
  envelope (doc 49 SETTLED 5/6/7: pirate −70/−10/30 effective,
  merchant −100/30/50, BH −100/10/70); clamped [−100, 100]
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
  level-60 capstone; species beyond the five-roster
  (human/martian/cygnian/sirian/lalandan), classes beyond
  pirate/merchant/bounty_hunter; level-up HP gains.

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
- **Flee (comms, pre-combat)** — 0.40 +2%/speed >10 +0.5%/piloting
  >30, clamp 0.15–0.90; failure forces combat + unprovoked rep
  (`_calc_flee_chance`; `comms._attempt_flee`).
- **Flee through the world's exits (doc 54.1)** — mid-fight, a move
  onto a planet/station/jump gate runs the SAME exit prompt from the
  combat loop (the meta seam: `_handle_meta_action` probes
  `_rules_space.attempt_flee`); cancels/refusals are full no-ops, a
  committing choice eats the REACTION VOLLEY — every hostile with
  LOS + a weapon in range fires once, no movement, CAN KILL
  (DEFEAT at the threshold: doc-53 tombstone, no transition) —
  (`_rules_space.reaction_volley`; the explicit reach filter
  `_ai._reaction_pick` — the hit formula's 5% floor scores
  out-of-range guns, so `_volley_picks` alone is not the gate).
  Survivors end FLED carrying the `CombatResult.flee_exit` FleeExit
  payload — the CALLER executes the transition
  (`space_flee.begin_flee_transition` + the four game_loop
  adoptions; the drift/detection guards exclude FLED like BOARDED).
  The wall resolvers split probe/commit/apply in
  `game_interactions` (`_space_exit_target` / `_space_exit_commit`
  / `_apply_exit_commit`) with every refusal probed BEFORE the
  volley fires.
- **Space combat init** — encounter wrapper builds player state +
  one EnemyInstance per spec, dedupes overlapping spawns
  (`combat/_encounter._handle_combat_encounter`). The enemy build is
  the PARITY MIRROR (doc 48.7): hull-catalog shields/recharge/power
  via `_stats._enemy_hull` (unknown hulls contribute nothing), module
  skill bonuses + the per-spec dials folded onto band-derived skills
  (`_enemy_skills` — targeting/gyro count), flown weapons AND
  modules as quality-rolled `StoredEquipment`, ammo keyed by weapon
  slot; `pilot_*`/`min_power_gen` retired from the spec
  (TypeError-pinned). Doc 56 phase 2: upkeep authoring lowered power
  pools for specs flying upkept modules (probe-refereed,
  player-favor). Doc 56 phase 5 (NPC grid parity, LANDED): every
  spec's kit must PACK its hull grid and rest at net >= 0 at base
  quality (two permanent lints, `tests/test_space_scale.py`);
  `pirate_warlord` re-authored without the smuggler hold to fit
  (23/30, SETTLED 22). Enemies still fly no placements in combat —
  parity is lint-level; magnitudes were deliberately untouched
  (phase 4 calibrates against the probe).
- **Combat math** — fractional AP in twentieths with banked carry
  (both sides); hit = accuracy + gunnery/2 + close bonus − range
  penalties − dodge, clamp 5–95; dodge +5%/cell moved (cap 30) —
  kiting is the core defense; damage × quality × 0.8–1.2 variance,
  hull-then-shields (`combat/_stats.py`, `_actions.resolve_damage` —
  the roll carries the SHOOTER's weapon quality: both sides at
  their flown tier, doc 48.7 — the player's `OwnedShip.weapons`
  instances thread through `SpaceCombatState.weapon_qualities`).
  Weapon quality scales BOTH terms (doc 47 SETTLED 2; the space
  accuracy half landed 2026-09-28 after shipping damage-only —
  `calc_hit_chance(weapon_quality=…)` and
  `quality.effective_ship_weapon_spec`, and the enemy ranker scores
  at the flown tier so tiered weapons rank as they fight).
  Doc 49 riders in the same math: Momentum +5 hit (the ONE
  `_player_hit_bonus` assembly), Longshot +1 range
  (`_space_focus.max_range`), the Pirate opener (+hit via the
  assembly, ×1.25 via `_player_damage_mult`), BH +5 evade at
  `_resolve_enemy_shot` only (AI-belief reads stay bare).
- **Volley + Focus** — F fires all active weapons (max single AP
  cost); Focus trait (one weapon): 2× AP/power cost, doubled
  ranges, 2× damage beyond normal max — the kiting payoff
  (`combat/_loop.py`; `combat/_space_focus.py`).
- **Resources** — hull/ammo sync to the owned ship at fight end;
  power pool regen/turn; S = paid shield regen 0–10
  (`combat/_rules_space.sync_state`, `handle_defense`). Enemies
  regenerate shields FREE at hull base + module bonus per turn
  (folded at build into `EnemyInstance.shield_recharge_bonus`,
  `start_enemy_turn`; the paid divert stays unset — Tier 1, doc
  48.7).
- **Combat AI** — per-ENEMY AP loop: advance when beyond own
  `ai_preferred_range` or no LOS, else the aggressiveness-gated
  engagement decision (fire vs reposition; fights to the death)
  (`combat/_ai.py`). VOLLEY FIRE (doc 56 SETTLED 24, the player's
  burst-fire mirror): the fire action fires EVERY affordable weapon
  once in slot order — per-weapon power/ammo paid by each member, AP
  = max(ap_cost) paid once; a volley with nothing affordable never
  stamps the Pirate opener. HONEST FIRE (doc 48.7): every shot pays
  real costs through the shared `weapon_costs` table (misses
  included; the player's `can_afford_action` reads the same table);
  the score-ranked pickers govern the band/dance and the flee
  reaction only — volley INCLUSION is affordability alone (a
  score-zero strip weapon rides the volley when another affordable
  weapon passes the engagement gate; an ALL-zero affordable set never
  volleys — it repositions per SETTLED 40);
  out-of-range members fire at the penalized floor, exactly as the
  player's own volley does; LOS stays a firing precondition (a
  blocked no-LOS step breaks the turn — never fires through cover).
  Doc 54's flee reaction keeps its single-shot consumer
  (`_enemy_attack`, one top-scoring reach weapon, opener stamped per
  attack). `ai_flee_threshold` RETIRED in doc 48 phase 3 (field
  deleted, TypeError-pinned; fleeing ruled out of space combat,
  SETTLED 20 — doc 34 folded there).
- **Reinforcements** — per-round re-detection joins newly triggered
  squads mid-fight (`combat/_rules_space.check_reinforcements`);
  joiners build from their OWN spec through the one enemy
  construction path (`_build_reinforcement_enemy` → `_build_enemy`
  — the old player-hull reads + spurious None dropped, doc 48.7).
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
  interior seeds the flown-equipment strip at engine-room markers —
  modules AND quality-bearing weapons (`cr.boarded_weapons` beside
  the modules, `ship_weapon` payloads; doc 47.3 + 48.7); heist
  cargo rides
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
- **Missile flight (doc 57 SETTLED 11, phases 1-2 playtest-passed
  2026-10-01)** — light/heavy missiles are physical crossing
  projectiles (`combat/_missile_flight.py`), BOTH sides: deploy into a
  free 8-neighbor of the shooter (never on it, nearest the target),
  launch half-move (`max(1, speed//2)`), then per-SHOOTER mini-turns
  at the start of the shooter's turn — one missile at a time, launch
  order, full `flight_speed`; dead shooters' missiles fly at the
  start of the enemy phase (the orphan sweep — death never recalls).
  Collision: any ship contact (anchor cells, on
  entry, plus a parking pre-check) = the same guidance roll vs that
  ship's dodge-at-contact, FULL spec damage, full kill chain on any
  kill; self-splash live (DEFEAT propagates); enemy-on-enemy clips
  are fratricide (identical physics, no player credit); terrain
  detonates harmlessly; missiles never detonate on missiles
  (same-shooter actively avoided via sidestep/hold-no-burn — keyed on
  shooter IDENTITY; launch stagger keeps volleys unstacked; a rack
  fired at a missile is a legal fuel dud).
  Fuel = `max_range` cells of entered cells; beyond-max launch is a
  fuel dud (user ruling). Hard floor = catalog `min_range`, flight
  missiles only (ONE read: `catalog_floor` — gate, range line, HUD
  distance, card HIT color, WEAPONS row; Focus never widens it);
  enemy racks take the same gate (supersedes doc 56 SETTLED 24's
  fire-at-penalized-floor for missile members), and the enemy dance
  band reads the WISH-list top so a benched rack still governs range
  (rack carriers' `ai_preferred_range` clears floor + sqrt(2),
  pinned catalog-wide). Enemy launches are wordless (the attack line
  lands at arrival through `_apply_enemy_hit`); enemy guidance rolls
  the launch-time gunnery snapshot, never player perks.
  Interception: merged `targetables` (ships then missiles) feeds
  TAB/card/range reads/fire ONLY — end-check, reaction volley, board
  stay ships-only; flak = normal volley damage onto `missile_hp`,
  the intercept kill never reaches `on_kill` (no XP/loot/rep for
  ordnance); arrival kills run the full chain minus the Momentum
  refund. Enemy flak: per-action score(inbound) vs score(shooter)
  (`score_flak` = chance x hull-coverage x threat / AP), fired inside
  the fire branch; flak volleys exclude racks and strip weapons.
  Reaction fire is guns-only (racks cannot chase a fleeing ship; the
  instant EMP stays). EMP stays an instant pulse (`flight_speed=0`).
  Glyphs: heavy `♦` / light `*`, hostile hot red / player cyan. All
  flight state is combat-transient (swept on every end path + at
  `_activate_combat_state`); `world.Entity.non_blocking` makes
  crossings zero-footprint (blocking/A*/patrol/reinforcement-matcher
  all skip them). Calibration owns the magnitudes.
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
- **Ship band scaling (doc 48 phase 7)** — `space_scale.py`, the
  ground resolver's space twin (imports `ground_scale`'s band
  machinery; the largest-remainder allocator is ONE shared helper).
  A ship's band is SPEC-AUTHORED (`NpcShipSpec.band` + three-slot
  `skill_weights`; nothing stamps a band at spawn): pirate
  1/2/2/3/3/4, militia weight ladder 1/2/3 (blockade 2 — the Line),
  merchant wealth 1/2/3 piloting-light, derelicts 0. Pilot skills =
  base 11 (the ships dial: band-1 total 43) + the band budget split
  by weights; the LVL line rides the ground card's exact title
  format on the space target card. Fly-time quality rolls are
  band-indexed for weapons AND modules (band 1 == KILL ladder)
  through `roll_flown_equipment` — `_roll_flown_modules` retired.
  The Line's closed-form harness re-pinned for parity numbers: the
  costly full-watch win belongs to the super-powered sheet (the
  MOVED BRACKET, `tests/test_line_tuning.py`). Themed loadouts
  (doc 48.7): pirate flagships fly the EXISTING smuggler-hold
  family (mk3/mk4, mk = band — no new module id, playtest ruling
  2026-09-24); merchant wealth scales cargo+shield suites; the map
  shield read credits hull base shields for ships under way only —
  hulls pinned `base_speed=0` (derelicts) show no bubble.
- **End states** — all dead = VICTORY; survivors out of sight =
  DISENGAGED (they keep wounds — HP syncs to `entity.hp`, so
  re-engaging never heals them) (`combat/_rules_ground.py`). The
  doc-54 stair-dance synthesizes DISENGAGED directly (see Stair
  dancing below) — `_combat_end_check` is not the only producer.
- **Stair dancing / ground flee (doc 54.2)** — a MOVE that lands on
  a transition tile IS the flee commit (AP spent, no prompt): the
  refusal conditions are probed first over the handlers' own
  validators (dig bounds via seeded `site_depth`, sealed-elevator
  gates via `_transition_target_floor`, leave/attach preconditions
  — `combat/_ground_flee._stair_transition_refuses`, read-only) and
  a refusing stair REFUNDS the step (position + AP back, same
  turn). Otherwise every enemy in weapon band + LOS attacks once
  via the ground shot machinery (no movement, CAN KILL — death on
  the stairs = DEFEAT + tombstone, no transition) and the fight
  ends DISENGAGED carrying the tile-kind `flee_exit`
  (`GroundCombatState.flee_exit`), with `on_disengage` called
  directly so survivors hunt the stairs' last-seen. The CALLER runs
  the ordinary tile dispatch via the tick's distinct "COMBAT_EXIT"
  signal — move and wait paths share `_dispatch_dungeon_tile`;
  automation halts on the signal (commit dropped there: step
  off/back on, no second volley); interior fights exit through
  `exit_city_interior` with the real flow state
  (`city_npcs.run_city_fight` returns its result).
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
  min 1 (`combat/_rules_ground.py`, `_ground_math.py`). Doc 49
  riders in the same sums: Sturdy +2 armor/+2 melee, Nimble +1 AP,
  Longshot +1 ranged range (`weapon_range`), the Pirate opener
  (+hit in `hit_chance`, ×125% in `damage` and the blast's enemy
  shares); the player's dodge is ONE assembly
  (`_player_ground_dodge`: move + Evasive + BH) read by enemy
  aiming, the HUD line, and the flee reaction.
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
  bonuses; R is the only reload verb — the weapon's reload AP in
  combat, free at the dungeon screen (doc 51.3 removed the menu
  reloads); consumables with timed effects; EVERY equipment change
  through C costs 1 AP mid-combat, uniform across weapons, armor,
  and either set (doc 51.3) (`combat/_rules_ground.py`;
  `ground_reload_ui.py`; `character_screen._apply_equipment_select`;
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
  over 10), two class-keyed weapon sets (see Ground weapon sets),
  five armor slots under an `--- ARMOR ---` group (incl. the
  cybernetics subfamily — eyes/torso/arms/legs pieces whose
  `ap/hit/melee/hp_bonus` fields are the cyber identity,
  `data/ground_armor/vests.py`); per-weapon magazines +
  ammo types (6), reload picks among weapons sharing the ammo, and
  magazines ride stored entries through every store/displacement/
  install round-trip (legacy/absent = full seed; `StoredGroundEquipment.
  loaded_ammo`, doc 51.3) (`ground_equipment.py`:
  `expedition_capacity`, `stored_mag_suffix`; `data/ground_items/
  ammo.py`: `AMMO`).
- **Ground weapon sets (doc 51, complete)** — loadout is
  two class-pure sets (membership table on `damage_type`: melee vs
  kinetic/energy/plasma/explosive); the ACTIVE set is still
  `ctx.equipped_ground_weapons` (combat reads it unchanged) and the
  other set lives on `ctx.holstered_ground_weapons` — equipment,
  never pack-counted. Pre-doc-51 saves partition on load (active =
  original slot 0's class). **X swaps the whole sets, any
  composition, magazines riding the instances**: in combat 1 AP
  mid-turn via the action table + `_run_rules_hook` →
  `_rules_ground.swap_weapon_sets` (flags reset all-True over the
  fists fallback — empty-active swaps to fists and still fires;
  0-AP refuses; silent, never turn-ending; space combat logs
  "unavailable"), FREE out of combat in every non-space mode
  (shift-excluded `_is_x_press`; 2-line branch in
  `game_loop._handle_menu_event`). The outcome line is
  single-sourced in `ground_weapon_sets.swap_sets_logged`. HUD:
  dim HOLSTER names row under the weapons panel (hidden when
  empty) + `[x] Swap` in the combat legend + `[X] Swap Sets` on
  the explore help block (the space list is pinned X-free). Dev:
  New-Game grant seats strongest-ranged active + strongest-melee
  holstered (`dev_mode._best_set_weapon`); Shift+W dumps both
  sets (`ground_weapon_sets.py`; `saveload_ground.py`:
  `_restore_weapon_sets`).
  **Phase 3 — sets are CLASS-KEYED homes (SETTLED 3)**: a weapon
  always equips into its class's set via the total founding rule
  (`resolve_weapon_home`: holding set wins, both → ACTIVE, unfounded
  → the empty set, both-empty → ACTIVE, degenerate no-home →
  refusal line); active/holstered are roles X flips. Both equipment
  screens render the two groups with role markers and BOTH slot
  rows (2H-founded sets mark slot 2 occupied); equipping into a
  full set opens the member chooser (1H pick displaces one, 2H the
  whole set — to the pack on the C path, pack-then-warehouse on the
  armory path; a 2H overflow aborts atomically); Store/Sell work on
  either set's members; tinker kits reach both sets
  (`KIT:WEAPON:{class}:{idx}`). All installs go through the atomic
  `install_set_weapon` (`ground_weapon_sets.py`; screens:
  `character_screen_weapons.py`, `menus/_armory.py`;
  `tinker._weapon_targets`).
- **Ground bandolier (doc 52, complete)** — ground ammo is a
  per-caliber tracked reserve (`ctx.bandolier`: ammo_type → rounds;
  caps from `GroundAmmoSpec.carry_cap` 160/240/250/130/18/10 through
  `bandolier.effective_cap` — the future armor `ammo_bonus` seam,
  phase 4 deferred), NEVER pack/armory cargo: reload draws it
  (`ground_weapon_ammo.reserve_ammo_count`/`apply_reload`), pickups
  (P + chooser) and armory RESTOCK refill it (`bandolier.refill`;
  over-cap ignored, at-cap logs the shared full line; restock priced
  per-round), and legacy pack/armory stack records migrate into it
  on load (overflow refunded as credits). Player-facing vocabulary
  is "Ammo"/"ammo storage" — never "bandolier" (52.3 playtest
  ruling). Surfaces (52.3): the combat weapons panel and the
  dungeon HUD's weapons block each end with one
  `PST/RFL/CEL/SHL/GRN/RKT cur/max` line per carried caliber
  (active+holstered union in catalog order; `bandolier.HUD_CODES`,
  `carried_ammo_types`, `hud.bandolier_hud_lines`; the dungeon
  block also shows active-set name+magazine rows and the dim
  HOLSTER names); the C screen's Equipment tab is a split frame —
  left equipment management, right a read-only six-caliber aligned
  readout (`pygame_split.run_for_screen`: TAB keeps cycling C tabs,
  flag-based selection; `character_screen._equipment_frame`).
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
  `RumorEntry` chains in `data/lore/` (two chains: dark-ports —
  sources are planet-scoped `(npc, planet, faction, floor, trait)`
  candidates with authored `picks` width; trigger-delivered tiers
  carry `triggers` and no sources. And the taking-ships opener
  (RUMORS.md) — a single ask-discovered entry teaching the four
  D-boarding conditions, value 0 (never sold), rarity by tier-weighted
  pool composition: rows per planet ∝ `mission_tier`, uniform sample
  = per-port odds), prose single-sourced in
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
  before the finale lifts board suppression; the armory beat buys
  two Kinetic Pistols + a Combat Knife (founding both weapon sets)
  and teaches restocking Pistol Rounds at the armory (52.6), and
  the ground-combat intro teaches the X set swap (doc 51.4)
  (`tutorial.py`).
- **Runtime text** — all quest prose in `data/text/*.json` keyed
  `step.*`/`npc.*`/`runtime.*`; code passes literal defaults; dev F5
  hot-reloads; lint checks coverage (`text.py`; `tools/quest_lint.py`).
- **Absent:** quest hooks in comms; repeatable missions; branches
  beyond the 4-faction fork + 2 dispositions.

## Economy & trade

- **Price curve (pure)** — stock/target ratio: shortage 2.0×→1.0×,
  surplus 1.0×→0.6×, floor 1cr (`trade.trade_price`).
- **Buy/sell** — buy = price × merchant-attitude modifier (the worn
  ID's sheet); sell = 75% of the CLASS-FREE buy core × modifier —
  the Merchant trait's −5%/+5% multiply the attitude chain at one
  site per surface and never compound (doc 49); shared by
  transaction and display (`trade.py`: `_terminal_buy_base`,
  `_unit_price`, `_sell_price`).
- **NPC ship trade** — ephemeral stock (3–8/good from the spec's
  `cargo_goods`), buy base×1.2 / sell base×0.5 × faction attitude ×
  the Merchant class mods (the NPC surface's one fold, doc 49);
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
  inventory; capacity = hull + module bonus + the Merchant trait's
  +10 (ctx-threaded at every decide/display reader — a merchant is
  never refused cargo their trade screen says fits, doc 49);
  full-screen hold modal with jettison (`ship.py`:
  `effective_max_cargo`; `trade.open_cargo`).
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
  min 1) + the Pirate class trait's flat +10 (doc 49)
  (`ship.smuggler_hold_capacity`). The shared cargo body
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
  tier, other categories ignore it — doc 47.2); loot is NEVER
  capped or evicted — the doc-47 30-entity cap was REMOVED 2026-09-23
  (the doc-48 perf pass removed the need, and the cap silently ate a
  floor-placed legendary when a guard squad's mass drops pushed the
  map over the limit); tiered
  NAMES colour their text everywhere they render — modded green,
  overclocked blue, prototype purple, legendary orange, base plain
  (`data/quality.QUALITY_COLORS` + `quality_mark`; inline runs:
  `MessageEntry.runs` through the log band/overlay/console history,
  `ScreenRow/MenuItem/SplitRow.runs`, combat `AttackLine`, the combat
  HUD weapon block — `message_log.with_runs`/`RunLine`, 2026-09-23);
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
- **Ship module loot (doc 47.3 + 48.7)** — modules are a loot
  payload: `item_type "module"` pickups append a quality-bearing
  `StoredEquipment` to global ship storage — no pack check, one
  log line, glyph reads the equipment hue + brightness
  (`loot._apply_module_loot`; `loot_common` maps module →
  EQUIPMENT_FG). WEAPONS are a seventh payload (doc 48.7):
  `item_type "ship_weapon"` (the bare "weapon" namespace is the
  ground catalog's) lands in storage at its flown quality through
  the module twin (`loot._apply_ship_weapon_loot`;
  `ship.weapon_display_name` is the label seam). Sources: INTACT
  CAPTURES strip the whole flown equipment list at the quality it
  flew — per-item BAND-INDEXED rolls at combat entry
  (`space_scale.roll_flown_equipment`; enemy hull/shields/skill
  sums scale through `effective_module_spec`)
  with the strip seeding engine-room markers from
  `cr.boarded_modules`/`boarded_weapons` (stamped at
  `_space_boarding`; no
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
  never exterior space kills, no delve-bottom guarantee. Targets
  cover BOTH weapon sets — class-keyed addresses that survive X
  flipping the roles (doc 51.3). Use
  from the pack's consumable manage modal intercepts at
  `character_screen._manage_consumable_stack` →
  `tinker.try_manage_kit` (returns None for non-kits, falling
  through to `use_consumable`); one CHOOSE TARGET chooser over
  every eligible owned entry across SEVEN containers — equipped
  weapons (both weapon sets, doc 51.3), equipped armor, expedition
  pack, armory warehouse
  (`ground_armory_storage`), mechanic ship-storage modules and
  ship weapons, installed modules, flown ship weapons (doc 48.7
  player side — `OwnedShip.weapons` holds quality-bearing
  `StoredEquipment`, legacy bare ids migrate on load) — rows preview `current -> next` token,
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
- **Creation traits (doc 49)** — one per species
  (`ORIGIN_TRAITS`: Fast Learner 6pts/level, Sturdy +2 armor/+2
  melee, Momentum +5% space hit + kill-refund, Longshot +1 ranged
  range, Nimble +1 ground AP) and one per class (`CLASS_TRAITS`,
  named the class) granted at creation — a fresh character holds
  exactly two; both registries sit outside `ALL_TRAITS` so
  milestones can never offer them; `trait_name` resolves all four
  registries (`data/traits/core.py`; `xp.py` bonus helpers;
  `game_loop._configure_new_context`).
- **Class-trait hooks (doc 49 phase 2)** — Pirate: +10 smuggler
  hold on every ship; the opener (+10 hit/+25% damage on the first
  attack while no enemy has fired, both theaters — `enemy_fired`
  stamps at the enemy-shot funnels, `opener_spent` at the fire
  loop). Merchant: +10 cargo at every decide/display reader;
  −5% buy/+5% sell goods prices folded at the class-free terminal
  core (no compounding; stacks with attitude; NPC surface folds
  both). Bounty Hunter: +5% evade both theaters (ground ONE
  assembly `_player_ground_dodge`; space resolution-only so AI
  beliefs misjudge); missile racks ×2 via
  `ship.effective_missile_capacity` at every capacity site incl
  the save/load `cargo_ammo` restore and the fresh-buy top-off.
- **Trait catalog** — 17 traits (skill-followers, playstyle
  counters, career 20-mission traits); flat effect accessors on
  xp.py; Ironclad retro-applies max-HP including into live combat
  (`data/traits/core.py`; `xp.py`; `trait_screen._apply_ironclad_hp`).
- **`rep_required` is dormant** — implemented in the qualifier but
  every trait ships None; it reads the TRUE sheet, not the
  broadcast (`data/traits/core.py`; `xp.py:239`).
- **Career board refresh** — Hauler/Fixer/Hunter grants force-
  refresh all boards (`trait_screen._refresh_faction_boards`).
- **Character creation** — base 10 all stats; species and class each
  add a +6-budget stat spread; class sets starting credits (25/50/75);
  hull HP is never a character stat (ship + modules own it, doc 49
  SETTLED 5 — `hp_base`/`HudStats.hp` deleted); each layer grants one
  creation trait (species' + class', never offered at milestones)
  (`character.py`; `data/classes/core.py`; `data/traits/core.py`
  `ORIGIN_TRAITS`/`CLASS_TRAITS`; `game_loop._configure_new_context`).
- **Creation pickers (doc 49)** — two split screens (`pygame_split`):
  species card (CHAR-NAME-HOME in the species color, six stat rows,
  Armor/HP, trait block) then class card (CHAR-SPECIES-CLASS in the
  species' color — classes carry none; six combined live-formula
  rows; Armor/HP/Cr vitals row; ONE effective-rep row; trait block;
  11-row viewport) via the shared `_run_split_picker` loop with a
  generic-menu fallback (`ui.py`; `input_helpers`).
- **Playstyle counters** — extendable `PlayerCounters` on ctx; all
  reset on death; career damage tallies are THEATER-SPLIT —
  `total_damage_taken` space-only (doc 2), `ground_damage_taken`
  ground-only (doc 53, incremented post-DR at both ground damage
  sites), both rebuilt on load (`game_context.py`;
  `saveload._parse_counters`).

## Ships & equipment

- **Ship ops** — weapon/module install/remove with slot re-indexing
  and ammo seeding; effective speed/cargo math; missile rack
  capacity resolves through ONE helper (`effective_missile_capacity`
  — the Missile Magazine's per-rack bonus first, then ×2 for the
  Bounty Hunter; EMP launchers HARD-CAPPED at authored 2, never
  expanded, never doubled, doc 56 SETTLED 34/35) at every capacity
  site: seeding,
  refill room, storage clamps, `cargo_ammo` booking + its save/load
  restore, HUD/loadout/mechanic displays, and the fresh-buy
  top-off (`ship.py`; `saveload_ship.py`). Doc 56 (player-side
  grid): every installed entry carries a `grid_x`/`grid_y` anchor,
  installs go through the fitting gate (geometry + resting power,
  symmetric on removal — D-store/X-sell/hand-drops at the mechanic
  editor; buys and storage installs HAND OFF into the editor's
  cursor), and loads normalize illegal grids by stripping offenders
  to storage (`ship_fitting.py`); the player-side slot guards and
  slot-count summaries are RETIRED, and doc 56 phase 5 deleted the
  `weapon_slots`/`module_slots` catalog fields outright
  (TypeError-pinned) — the fitting grid is the ONE capacity, and the
  NPC side reads it through the same packer/power lints the player's
  start loadouts do (`tests/test_space_scale.py`).
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
- **Death & share artifacts (doc 53)** — every DEFEAT writes a
  tombstone morgue file (header + CHAR + GEAR + the complete log;
  killer from per-fight `last_attacker` tracking on both combat
  states, self-splash pins "your own explosives"); the ESC pause
  menu's Dump Char row writes the living sibling (same sections,
  header minus death facts) to `chardumps/`; both live under
  `~/.spacehack/saves/` with timestamped names + -2/-3 collision
  suffixes, best-effort (a write failure never blocks its caller);
  the death screens APPEND the full-filename notice in all three
  theaters, city included (`tombstone.py`;
  `combat/_loop._finish_combat` — the write precedes autosave
  deletion; `game_flow._run_pygame_pause_menu`,
  `_show_char_dump_modal`; blast killer line in
  `combat/_ground_blast.py`).
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
  price block, and outcomes untouched (`menus/_ship_buy.py`). Doc 56 SETTLED 18: the Weapon/Module slot
  rows retired — the sheet reads Speed/Fuel tank, Hull/Shields/
  Power-per-turn, Cargo (grid fitness is the mechanic editor's
  question, not the sheet's).
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
  log, `\` console, `?` guide, ESC pause menu (Save & Exit /
  Dump Char) (`input_helpers.py`; `game_loop.py`).
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
