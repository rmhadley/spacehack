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

Audience is both of us: agent sessions and the player-designer.
Terse by design — this is a lookup surface, not documentation.

## Identity & reputation (doc 40)

- **Broadcast states** live / dark / spoofed — `identity.py`
  (`broadcast_mode`, `resolved_identity`); hub is the F screen
  (`pygame_faction.py`, D toggles, TAB cycles the library). Dark
  suppresses auto-hail and gates docks/challenges.
- **Rep sheets per ID** — an ID maps to a `{faction: int}` sheet.
  ID 1 = `ctx.faction_reputation` (only sheet behavior changes).
  Collected IDs carry their own `rep` in the `collected_ids` entry.
  Reads: `identity.effective_reputation(ctx)` — THE one resolver.
  Writes: `faction.modify_rep` follows the broadcast (live → ID 1,
  spoofed → worn sheet, **dark discards**). Scrubs = literal zeros,
  materialized at purchase. Time decay always ages ID 1 only.
- **Attitude zones** — `faction.get_attitude`: enemy ≤ −76, disliked
  ≤ −26, neutral ≤ +25, liked ≤ +75, allied ≥ +76. Starting rep
  (`_DEFAULT_REP`): pirate −100 (enemy — why early pirates attack),
  militia +50, merchant/civilian 0. Species/class adjust.
- **Challenge hail** — dark hull spotted by militia: identify /
  attack, two options, no run (`comms._handle_challenge`); the
  answered ID's sheet decides (value read, no faction special
  cases); one-shot per patrol via `ctx.militia_scanned`.
- **Dark dock gate** — only `dark_berth=True` ports berth a dark
  hull (data opt-in on PlanetSpec: Deadfall, Whisper, Ember,
  Wolf 359 b); scrubbed docks anywhere.
- **ID acquisition (v1)** — one vector: the Registry Broker at
  Deadfall, 6,000cr scrub (`identity.SCRUB_BROKERS`). Clones =
  live-ship boarding capture, rolled sheets (doc 40 phase 6,
  not built).

## Space flight, spawns & combat

- **Spawn readers, one gate** — bounty (`_trigger_bounty_spawns`),
  procedural (`_trigger_procedural_spawns`), static
  (`_trigger_static_spawns`) in `navigation_combat.py`; all engage
  only on RESOLVED disliked/enemy (`_gate_engages`); charged-cell
  heat (Act 0, militia in Sol) bypasses the mask — heat, not
  identity. Statics used to always engage; uniform since phase 4
  (the Luyten blockade stands down to militia-liked hulls).
- **Militia cargo scans** — chance by militia attitude
  (`_militia_scan_chance`: allied 0% … disliked/enemy 80%; bar-heat
  floor 60%); heat persists while hot quest cargo is held.
- **Space AI** — one hunter loop per squad, `ai_preferred_range`
  scalar; planets block LOS. (Kiter/brawler/artillery verbs
  proposed, not built — doc 34 seed.)
- **Boarding is SOLVED for wrecks** — any wreck/dead hull is
  bump-boardable into a dungeon interior
  (`game_interactions._resolve_npc_ship_blocker` + persisting
  interiors cache; crew/layouts from ship layout data). Live-ship
  boarding (cripple → board → fight to a console) is an EXTENSION
  of this pipeline, not a new system (doc 40 phase 6's planned
  shape).
- **Transit** — city transit bays/stops (`city_transit.py`);
  arrival pulse blooms the stop's colour at the player's cell.

## Ground: cities, dungeons, delves

- **Cities** — `*_city.py` modules build on `city_kit.py` (base
  tiles, terminals, showroom ships, transit, forecourts); NPC
  hostility per city tick reads the broadcasting sheet
  (`city_npcs.is_hostile` → `faction.spec_is_hostile`).
- **Dungeons/landmarks** — BSP + authored layouts
  (`dungeon_layout.py`, `dungeon_bsp.py`); explicit landmark
  entrance tile (glyph `e`) is the single link point; interiors
  unlimited doors. Player spawn glyph `P`.
- **Ground NPCs** — squads share leader paths (`ground_npcs.py`);
  hostility: `spec_is_hostile` (monsters `always_hostile` ignore
  rep; killing monsters never touches rep).
- **Ground consumables/equipment** — `ground_consumables.py`,
  `ground_equipment.py`, `data/ground_*` catalogs.

## Quests & content authoring

- **Quest mechanics are step data** — cache sites via the
  QUEST_CACHE `%` marker (≤1, floor-normalized), guardians as
  `ENEMY:` markers inside layouts, weighted `delve_layout_variants`
  (pick-then-fallback); machinery in `main_quest/` + delve paths.
- **Quest cargo is mission cargo** — named quest goods or virtual
  ids; never sellable; mission hold separate from market hold.
- **Quest perks** — story-earned via `rewards_trait`; free, outside
  level-up choices; perk-gated boards force-refresh on grant.
- **Decision points** — pure-data primitive on quest steps
  (option_gating, one-shot starters); doc 33.
- **Prose standard** — knowledge.md "Quest prose standard" (the 14
  tells); user wording is used verbatim.

## Economy & trade

- **Pricing** — `trade.trade_price` (pure); buy/sell modifiers by
  merchant attitude; market intel gated on non-negative merchant
  standing (`trade_market.py`).
- **Economy drift** — `trade.tick_economy` mutates planet stock
  toward target stocks; per-planet `economy_state`.
- **Salvage/loot** — loot budget in credits; wreck loot persists in
  the interiors cache; `loot.py` / `loot_selection.py`.

## Ships & equipment

- **Ship ops** — `ship.py` (weapon/module install/remove with slot
  re-indexing, ammo seeding, effective speed/cargo).
- **Layouts** — ship layouts authored per grammar (silhouette
  first, `{###}` hull, void tiles, BFS-validated; `layout_format.py`
  + editor twins in `tools/`).
- **Catalogs** — every content type is a frozen dataclass +
  `find_*(id)` under `data/` (weapons, modules, ships, npc_ships,
  npc_chars, planets, solar_systems, species, classes, traits,
  pilot_skills, missions, trade_goods, city_npcs, landmarks).

## Meta systems

- **Save/load** — single autosave, full-state serialization
  (`saveload.py`); every mutable state change must round-trip
  (knowledge.md contract); engine RNG state persisted.
- **Guide** — `?` opens `data/guide/` sections; every player-facing
  behavior ships with a guide entry (knowledge.md contract).
- **Time & decay** — gate-day clock (`time.py`); monthly faction
  decay toward neutral, sign-safe (`faction.apply_monthly_decay`,
  always ID 1's sheet).
- **Seeds** — SPACEHACK_SEED pins runs; per-new-game `_fresh_seed`
  (hook there to pin); Shift+S mid-session reroll; engine.RNG
  rebinds on seed.
- **Dev mode** — `dev_mode.py` (dev shortcuts for playtests).

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
