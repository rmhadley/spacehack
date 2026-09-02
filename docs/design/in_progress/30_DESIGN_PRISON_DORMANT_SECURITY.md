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

## Phased implementation

### Phase 1 — dormancy exists
- [ ] `powered_down` Entity field + serialization row
- [ ] grey render (fg override when dormant)
- [ ] enemy-turn skip + bump message branch
- [ ] tests: field round-trips through save/load; dormant unit does
      not act; bumping logs and starts no combat

PLAYTEST: none (nothing places them yet); `make check`.

### Phase 2 — prison floors are stocked
- [ ] dormant-security scatter pass (event data + `lockdown_extras`)
- [ ] `lockdown_extras` field on `ExtensionFloorSpec`
- [ ] tests: every prison floor carries dormant squads near anchors;
      non-prison dungeons unchanged; counts match data

PLAYTEST: descend F1 — grey `d`s stand along the route; bump one.

### Phase 3 — the wake-up
- [ ] `activate_dormant` mutator; events rewired (no more spawn)
- [ ] data-extract activates all floors + cached maps
- [ ] phase-gated generation (late floors spawn active)
- [ ] tests: alpha/beta/ascent events convert only their squads;
      extract converts everything everywhere; post-download generated
      floor spawns active; save/load preserves each unit's state

PLAYTEST: full run — grey on the way down, colored and hostile after
each popup; download → the whole map lights up red (doc 29) and every
grey wakes; climb the stocked gauntlet.

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
