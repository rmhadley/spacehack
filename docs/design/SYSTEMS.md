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
  everything even with a face worn (`identity.py`: `broadcast_mode`,
  `resolved_identity`, `toggle_dark`).
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
- **Starting rep** — `_DEFAULT_REP` pirate −100 (enemy — why early
  pirates attack), militia +50, merchant/civilian 0; species adj
  (martian: militia +10, pirate −10) + class tables; clamped
  [−100, 100] (`faction.py`: `starting_reputation`, `_SPECIES_REP`,
  `_CLASS_REP`).
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
- **ID library** — collected IDs ride the player across lawful ship
  purchases; dedup by hull number; cycle none → first → … → none
  (`identity.py`: `collect_id`, `cycle_identity`,
  `library_position`).
- **Scrub (only acquisition vector)** — `deadfall_scrubber` NPC,
  6,000cr; a scrub materializes literal 0s for every faction
  (`identity.py`: `SCRUB_BROKERS`, `buy_scrubbed_id`).
- **Registration** — 2 letters + 4 digits, generated once per run,
  migrated into old saves on load (`generate_registration`,
  `ensure_registration`).
- **NPC broadcasts** — every NPC ship broadcasts; hull number minted
  on first read, kept for the entity's life (`npc_identity`).
- **F screen hub** — renders the broadcasting sheet literally + the
  identity line `[pos/total] label [MODE]`; D toggles (logged,
  naming the worn ID), TAB cycles (`pygame_faction.py`: `frame_for`,
  `_log_transponder_toggle`).
- **Challenge hail** — militia-only physical spot of a dark hull
  inside `detect_radius` (eyes, not comms range): Identify/Attack,
  no run; silence = refuse = fire; the answered ID's sheet decides;
  one-shot per patrol via persisted `ctx.militia_scanned`
  (`navigation_combat._dark_spot_challenge`; `comms._handle_challenge`,
  `_judge_identification`).
- **Dark dock gate** — only `dark_berth=True` PlanetSpec opt-ins
  berth a dark hull (lal_b Deadfall, lal_c Whisper, ross_b Ember,
  wolf_b Wolf 359 b), checked before the system switch commits
  (`game_interactions._dark_dock_refusal`).
- **Absent:** cloned/fabricated IDs (labels exist, no grant path —
  doc 40 phase 6); level-60 capstone; species beyond human/martian,
  classes beyond pirate/merchant/bounty_hunter; level-up HP gains.

## Space flight, spawns & combat

- **System maps** — big walkable grids (Sol 200×140); planets/
  gates/stations are multi-cell unwalkable footprints driving bump
  detection (`solar_system.py`: `planet_id_at`, `jump_point_at`).
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
  RESOLVED sheet reads disliked/enemy (`_gate_engages`); statics
  gate uniformly since doc 40 phase 4 (the Luyten blockade stands
  down to militia-liked hulls — user-ruled, no exceptions).
- **Charged-cell heat** — Act-0 heat in Sol: militia engage
  regardless of identity, detect radius floored at 30 — a heat
  response, not an identity read (`_charged_cell_aggro`).
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
- **Squad movement** — shared leader A*, 80%/tick step, straggler
  regroup >4 cells; aggro chase retargets whole squads
  (`_move_one_squad`, `_squad_aggro`).
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
  (`combat/_ai.py`). **Dead data:** `ai_aggressiveness`,
  `ai_flee_threshold` unread anywhere — no kiter/brawler/artillery
  verbs (doc-34 seed open).
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
- **Boarding is SOLVED for wrecks** — dead hulls are bump-boardable
  into cached dungeon interiors with breach animation
  (`game_interactions._resolve_npc_ship_blocker`,
  `_enter_boarding_dungeon`; `dungeon_animation.animate_breach`).
  Live-ship boarding (cripple → board → console) is an EXTENSION of
  this pipeline (doc 40 phase 6's planned shape), not a new system.
- **Absent:** no ship-vs-ship real-time movement, ramming, tractor,
  mines-as-entities; no salvage drones; no player-called allies; no
  flee-from-space-combat; `NpcShipSpec.comms_range` documented
  "future use", unread (viewport visibility rules instead).

## Ground combat

- **Trigger** — pure LOS aggro: visible hostiles within
  `sight_radius` (8); `noise_hostiles` is a wired, EMPTY seam
  (`combat/_encounter.detect_ground_combat`).
- **End states** — all dead = VICTORY; survivors out of sight =
  DISENGAGED (they keep wounds — HP syncs to `entity.hp`, so
  re-engaging never heals them) (`combat/_rules_ground.py`).
- **Guard leash** — guard NPCs abandon chase beyond distance 8 and
  return to post; a 5-tick last-seen memory bounds investigation
  (`combat/_ai_ground.py`; `ground_npcs.py`: `remember_last_seen`).
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
- **Player kit** — HP 20 + stamina/3 + armor + traits; AP 4 +
  bonuses; reload costs AP in combat (free at dungeon screen);
  consumables with timed effects; equipment swaps cost 1 AP
  (`combat/_rules_ground.py`; `ground_reload_ui.py`,
  `ground_consumables.py`).

## Cities & ground life

- **Kit vs module** — `city_kit.py` owns the shared skeleton (base
  tiles, terminal trio, showroom ships, transit bay/stop painters,
  forecourts, metadata); `*_city.py` modules author only terrain +
  landmarks. 27 `city_layout_id` dispatch entries; unknown ids fall
  through to a grid city built from PlanetSpec buildings
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
- **PlanetSpec drives everything** — buildings, showroom ships,
  `city_layout_id`, `interior_layouts`, transit stations, NPC
  population, theme, produces/demands, mech/armory stock, tech
  level, mission tier, `explorable_site_name`+`dungeon_params`,
  `dark_berth`; modules auto-register by exporting `SPEC`
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
- **Showroom ships** — bump unowned = buy with trade-in; bump
  owned = ship menu + launch (`_resolve_ship_blocker`).
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
  per planet `quest_npc_spots` while their step is live; resume
  always re-enters at the entry spawn (`city_interiors.py`).
- **Landing flow** — Land → dark dock gate → cargo scan → city map
  build with ship glide; ground HP fully restores on landing;
  `militia_scanned` clears (`game_interactions._resolve_planet_land`,
  `_enter_city_landing`).
- **Launch** — bump your docked ship: hangar menu; the same entity
  animates offscreen and returns, keeping identity; launch spawns
  space with a spawn-exclusion ring (`city.py`: `_launch_to_space`).
- **Ground gear** — strength-capped expedition pack (4 + 1/5 STR
  over 10), 2 weapon slots, five armor slots; per-weapon magazines +
  ammo types (6), reload picks among weapons sharing the ammo
  (`ground_equipment.py`: `expedition_capacity`; `data/ground_items/
  ammo.py`: `AMMO`).
- **Consumables** — exactly two (med_pack heal+regen, stim +1 AP),
  AP-costed in combat, stack decrements only after the effect
  validates (`ground_consumables.use_consumable`).
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
  (`autoexplore.py`: `run_auto_explore`).
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
- **Absent:** generic multi-level stair dungeons (extensions only);
  per-save dungeon regen (interiors cache is permanent); mobile
  dormant AI; extension content beyond the prison.

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
  _breadcrumb.py`).
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
- **Mission-reserved space** — deliveries reserve on accept,
  released on complete/abort/fail; heist pickup reserves its
  volume; mission cargo never enters the sellable hold
  (`mission/_lifecycle.release_mission_cargo`; `loot.
  _secure_heist_cargo`).
- **Contraband** — `category="contraband"` goods sell only where
  listed in produces/demands (`trade._can_sell_here`).
- **Smuggler's hold** — hidden volume from smuggler modules
  (Mk1 10 / Mk2 25 / Mk3 50) + Smuggler's Instinct perk (+10% hull,
  min 1) (`ship.smuggler_hold_capacity`).
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
  check) (`dungeon_layout.py`: `_scatter_loot`; `loot.py`;
  `loot_selection.py`).
- **Quest loot security** — quest-cache pickup completes the step in
  the same action; goods NEVER enter the sellable hold (enforced
  structurally via reservations + `secure_quest_loot`, not at the
  sell counter) (`main_quest/_objectives.py`).
- **Absent:** `TradeGood.rarity` is a dead field (zero consumers);
  no tariffs beyond the confiscation fine; no equipment selling at
  terminals; no persistent NPC-trader stock.

## Progression

- **XP/levels** — curve 40 + next-level×25, hard cap 60 (XP accrues
  past cap); 5 skill points/level across six 0–100 skills
  (`xp.py`: `add_xp`, `_apply_skill_point`, `MAX_PLAYER_LEVEL`).
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
  pilot_skills, missions, trade_goods, city_npcs, landmarks).

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
  rebound to `surface:<city>` (`saveload.py`, `saveload_maps.py`).
- **Map rebuild on Continue** — mode dispatch rebuilds space
  (tombstones skipped) / dungeon (+hidden return pair) / city
  (authored rebuild + saved NPC positions) (`saveload_maps.py`).
- **Dev quicksave** — F6 writes `quicksave.json` (never deleted);
  F9 restores in place (`dev_mode.py`; `game_loop._dev_quickload`).
- **Time** — single choke-point `advance_time` (30-day months);
  month rollover refreshes boards + applies decay + ticks economy;
  the clock advances via `tick_move` at the ship's
  `effective_speed` moves/day (10 is only the fallback) (`time.py`).
- **Seeds** — `SPACEHACK_SEED` pins New Games in a session; Shift+S
  reroll is DEV-GATED (SPACEHACK_DEV) and ignores the pin; `RNG`
  rebinds on seed; `INIT_SEED` persists for deterministic helpers
  (`engine.py`: `new_game_seed`, `reroll_run_seed`; `title_flow.
  _fresh_seed`).
- **Dev mode** — `SPACEHACK_DEV`: super-frigate, 999,999cr, best
  gear; shortcuts: F3 debug overlay, F5 text hot-reload, F6/F9
  quicksave/load, Shift+X +200 XP, Shift+T teleport-to-port picker,
  Shift+S seed reroll, Shift+R reveal fog, Shift+D +30 days,
  Shift+O Act-0 faction picker (`dev_mode.py`; `game_loop.
  _handle_dev_event`).
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
- **Animations** — pure frame generators + present loops (descent
  elevator, breach sparks, transit arrival pulse); one pacing-
  constants module (`descent_animation.py`, `dungeon_animation.py`,
  `animation_timing.py`).
- **Presentation shell** — every screen is a pure frame through a
  `run_for_context` loop returning `(outcome, action, selected)`;
  three live modes (city/space/dungeon) with hidden return pairs;
  one main loop with an event dispatch chain; 50ms poll only when
  flickering lights animate (`pygame_menu.py`, `pygame_screen.py`;
  `game_loop.py`: `_run_gameplay`).
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
  `~/.spacehack/config.toml` (`display_config.py`).
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
