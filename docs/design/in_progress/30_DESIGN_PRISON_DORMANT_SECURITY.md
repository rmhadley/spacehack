# DESIGN: Prison Dormant Security

## Overview

Replace event-time enemy spawning with **pre-placed dormant security**.
Dormant units stand on the map from floor generation — same glyph as
their unit (`d` for drones) but grey. Bumping one reports it ("It is a
powered down Sentry Drone."); it does not fight and cannot be fought.
When a power event triggers, its allotted dormant units ACTIVATE —
recolored, hostile, and fighting. The data download activates EVERY
remaining dormant unit on EVERY floor at once: the exit gauntlet.

Companion to `29_DESIGN_PRISON_LIGHTING.md` — same events, same
derived phase, one facility truth:

- Descent events (alpha/beta, ascent events) activate their own
  dormant squads (near their route anchors).
- `prison_data_extracted` → all dormant units, all floors, instantly —
  the moment the prison "flares white".
- Upper floors carry EXTRA dormant units precisely so the lockdown
  gauntlet is stocked (user ruling 2026-09-02).

## Philosophy alignment

| Repo principle | How this applies |
|---|---|
| Data-first | Dormant counts come from the existing ActivationEvent data (+ one `lockdown_extras` per floor); no magic numbers in logic |
| ctx-first / declared fields | `powered_down` is a declared `world.Entity` field — never runtime-attached |
| Save/load sacred | The flag serializes with entities (saveload_maps flag-row pattern); phase-derived generation keeps unvisited floors consistent |
| Table over conditionals | squad_id ↔ event mapping by convention (`{event.id}_security` already exists) |
| Pure/mutation split | activation flip is one mutator; generation-time dormancy is a pure function of the phase (doc 29's `_facility_phase`) |

## Mechanics

### The dormancy flag

`world.Entity.powered_down: bool = False`. Dormant units:

- render grey — fg `(110, 110, 110)`, same char as the unit spec;
- are SKIPPED by the ground enemy turn (no movement, no aggro, no
  detect-radius pulls);
- resolve bumps with a log line — `It is a powered down Sentry Drone.`
  — NOT combat: no free kills before the wake-up;
- serialize the flag (add the bool row to the dungeon entity
  encoder/decoder, `main_quest_door` pattern).

### Activation

`activate_dormant(game_map, *, squad_prefix: str = "") -> int`:
one mutator — flips `powered_down`, restores the spec `fg`, returns
the count activated (for the log). Called from:

1. `_fire_activation_event` — replace `_spawn_activation_group` with
   `activate_dormant(game_map, squad_prefix=event.id)`. The event's
   popup/log text is unchanged; only the origin of the bodies changes
   (pre-placed instead of materializing).
2. the data-extract hook — `activate_dormant(floor_map)` for the
   current map AND every cached prison floor, plus set the phase so
   floors generated later spawn security already-active (see below).

### Generation placement

Prison floor population gains a dormant-security pass beside the
monster scatter (reuse `_scatter_squad`):

- per activation event on the floor: place `event.count` dormant units
  of `event.enemy_id` near the event's route anchor
  (`_event_position`), squad_id `{event.id}_security` — the existing
  convention, now assigned at generation;
- plus `lockdown_extras: int = 0` per `ExtensionFloorSpec` — reserve
  gauntlet stock, largest on F1/ascent floors;
- **phase gate**: if `_facility_phase(state)` is already `lockdown`
  when a floor generates (player saved post-download, floor unvisited),
  security spawns ACTIVE, not dormant — same derived-phase rule as the
  panel table in doc 29.

### Balance shape (data, tunable in playtest)

| Floor | Descent events | lockdown_extras |
|---|---|---|
| F1 | alpha (2 sentries), beta-region, ascent events | high |
| F2 | descent + ascent events | medium |
| F3/F4 | descent events | low |

Total activation on download ≈ the old spawn counts PLUS the extras —
the gauntlet the user asked for.

## Pre-implementation audit

**Reuse:**
- `_scatter_squad` (`dungeon_population.py`) — placement, unchanged.
- `NpcCharSpec` (`data/npc_chars/monsters.py`) — char/fg source of
  truth; grey is the only dormant-specific value.
- `_fire_activation_event` + `squad_id` convention — the single event
  dispatch point (already the lighting hook in doc 29).
- `_facility_phase` (doc 29) — drives generation-time dormancy.
- saveload_maps per-flag entity rows — serialization pattern.
- bump dispatch (`game_interactions` blocker chain) — new branch
  before the enemy branch.

**Duplication hotspots:**
1. Re-implementing squad placement instead of calling
   `_scatter_squad`.
2. Activation logic leaking into each event handler instead of one
   `activate_dormant` mutator.
3. A second "is hostile/active" concept drifting from the single
   `powered_down` flag (combat code must consult the SAME flag the
   renderer does).

**DRY strategy:** one flag, one mutator, one phase function (shared
with doc 29); counts live in data.

## Playtest v2 findings (2026-09-02) — fixed same day

- Gauntlet too sparse on ascent → extras raised to F1=8, F2=7, F3=6,
  F4=5, F5=3 (deep cell now stocked for the extract moment).
- Corner-LOS asymmetry (user-reported with ASCII repro): combat aggro
  used Bresenham while the player FOV uses rounded ray sampling — a
  drone beside a corner was visible but never aggressive. Aggro now
  reads the player's own `visible` grid: what you see can see you,
  by construction.
- Disengaged guards never investigated: `remember_last_seen` excluded
  guards by design, so a fight broken at a corner just froze. Combat
  disengage now stamps ALL survivors (`include_stationary=True`) and
  guards with a fresh memory investigate the last-seen cell before
  resuming their post.
- Dormant placement now also excludes landmark footprints (F5 extras
  had landed inside the deep-cell landmark).

## Phased implementation

### Phase 1 — dormancy exists — COMPLETE 2026-09-02
- [x] `powered_down` Entity field + serialization row
- [x] grey render (grey fg placed at stocking time; spec fg restored
      at activation — renderer needs no change)
- [x] inert at all three chokepoints: encounter scan
      (`_visible_hostile_entities`), patrol pass (`move_ground_npcs`),
      bump dispatch (reports "It is a powered down X.")
- [x] tests: field round-trips through save/load; dormant unit does
      not act; bumping logs and starts no combat
- [x] ratchet debt paid: ground_npcs.py split (patrol/squad/straggler
      helpers extracted)

PLAYTEST: none (nothing places them yet); `make check`.

### Phase 2 — prison floors are stocked — COMPLETE 2026-09-02
- [x] `_stock_dormant_security`: per-event dormant units at route
      anchors (ring-scan cells, ZERO RNG draws — seeded descents
      stable) + extras at the floor entry (F1=4, F2=3, F3=2, F4=1)
- [x] `lockdown_extras` field on `ExtensionFloorSpec`
- [x] size-limit split: anchor/dormant block extracted to
      `dungeon_activation.py` (re-exported)
- [x] tests: anchors/proximity/grey/counts; three legacy enemy-count
      pins updated to exclude `powered_down` (their intent: spawned
      security)
- [x] PLAYTEST FIX (#3, 2026-09-02): room-edge placement — ring scan
      prefers wall-hugging open cells, never 1-wide corridors, plus a
      strands-nothing reachability guarantee (a body may block a cell,
      never a route; BFS-per-candidate at generation, zero RNG).
      Tests: edge preference, routes-walkable BFS on F1+F2

PLAYTEST: descend F1 — grey `d`s stand along the route; bump one.

### Phase 3 — the wake-up — COMPLETE 2026-09-02
- [x] `activate_dormant` mutator (recolor + flag flip, squad-filtered);
      events rewired — `_spawn_activation_group` deleted; zero spawns
      log the existing "no deployable unit" line
- [x] data-extract hook in `activate_interaction_state` →
      `apply_lockdown_all_floors` (current + cached floors)
- [x] phase-gated generation (post-lockdown floors spawn active)
- [x] tests: squad filtering + recolor; extract lockdown across cached
      floors; activated state round-trips; three legacy spawn-proximity
      tests rewritten to activation semantics

PLAYTEST: pending user (session checklist v2).

### Phase 4 — feel + docs
- [ ] tune counts/extras from playtest
- [ ] guide: dormant security entry (player-visible behavior —
      "powered-down units block nothing until the facility wakes")
- [ ] corpus audit + `make check`
- [ ] Ask user: move doc to complete?

## Acceptance criteria

- No enemy materializes at event time anywhere in the prison —
  activation only converts pre-placed dormant units.
- Dormant: grey, inert, bump-safe (message, no combat, no damage).
- Download: every dormant unit on every floor activates at once.
- Unvisited floors generated post-download spawn active security.
- Save/load preserves every unit's dormant/active/dead state exactly.
- Guide documents the behavior; `make check` green throughout.

## Open questions

- Should dormant units block movement (physical obstacle) or allow
  walk-through? Default: block (they're bodies in the way) — but the
  gauntlet route must stay passable, anchors placed off the main path.
- Do dormant units grant XP/loot at all if never activated? Default:
  no — they are scenery until the facility wakes them.
