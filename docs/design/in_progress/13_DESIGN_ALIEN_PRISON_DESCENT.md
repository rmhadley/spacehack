# DESIGN: Themed Procedural Dungeon Extensions — Alien Prison First

> **Current content pack:** the Mars alien prison. The framework described here
> is intentionally dungeon-generic so future caves, ruins, stations, bunkers,
> and other themed sites can reuse it.

## Overview

Act 0's opened Mars door leads into an ancient alien prison: a high-tech facility
buried beneath the surface, more advanced than human engineering and long
abandoned. The prison is not a conventional dungeon full of prisoners. Every
cell is empty. Security systems still function intermittently, pests have
colonized the facility, and the deepest evidence suggests that at least one
massive unknown thing escaped.

The descent is a persistent five-floor dungeon extension attached to the Mars
surface dungeon. The player may backtrack freely between visited floors and
return to the Mars surface. Each floor keeps its map, fog, defeated enemies,
collected loot, opened doors, and objective state across floor changes and
save/load. "Alien prison" supplies the first theme, content definitions, and
story objectives; the floor cache, transition, generation, encounter, and
serialization machinery must not depend on prison-specific names.

Floor order:

1. **Main floor / entrance / staging area** — the opened Mars stairs arrive in
   an intake and security staging area. This teaches the prison's visual
   language and introduces low-level pests and dormant security.
2. **Low-risk prisoner quarters** — small empty cells, observation windows,
   security posts, and routine records. Security is present but degraded.
3. **Defensive floor** — the separation layer between ordinary and high-risk
   containment. Chokepoints, automated defenses, lockdown architecture, and a
   difficulty spike establish that the lower prison was built for something
   dangerous.
4. **High-risk prisoner quarters** — larger empty cells, more advanced
   security, and the prison engineering room. A deep elevator is present but
   unpowered. The player must find the engineering room and restore prison
   power before the elevator can operate.
5. **Deep cell** — the elevator arrives inside a giant empty cell. Its doors
   have been torn out by something massive and unknown. Terminals are scattered
   around the cell; only one still powers up. Extracting its incomprehensible
   data completes the Mars prison objective and begins Act 1's research trail.

## Design decisions (locked)

| Decision | Choice |
|----------|--------|
| **Generation strategy** | Procedural-first: generate each floor from reusable dungeon parameters, then reserve stable structural anchors for objectives and future landmark stamping. |
| **Authored content** | No required hand-authored floor map in the first vertical slice. Handcrafted landmarks remain a later extension point, not a prerequisite for the framework. |
| **Floor travel** | Backtrack freely between visited floors; preserve each floor as a persistent interior. |
| **Floor 5 outcome** | Extracting the data starts Act 1 research by unlocking the existing Alpha Centauri research step. |
| **Prison population** | Cells remain empty. Security defenses and random pests provide danger without populating prisoners. |
| **Narrative tone** | The facility is ancient, technologically superior, and ambiguous. The deep cell shows evidence of an unknown escape, not a direct monster reveal. |

## Philosophy alignment

| Principle | Application |
|----------|-------------|
| **Data-first** | Dungeon-extension definitions, floor themes, enemy pools, activation cues, objective markers, and terminal text live in data modules/layout assets rather than the game loop. |
| **Reusable extension** | A generic themed-dungeon definition owns floor generation and anchors; the alien prison is one content definition passed into that machinery. |
| **ctx-first** | The active prison run and its progress live on `GameContext`; no new scattered module globals. |
| **Persistent state** | Floor maps are cached under one prison-run key and serialized with their current floor and connections. |
| **Pure computation** | Floor selection, marker lookup, and transition validation remain pure helpers where possible; interaction handlers only mutate state and log outcomes. |
| **Domain ownership** | Prison setup/transition/objective logic belongs in a dedicated main-quest/prison module, not a larger `__main__.py` branch. |
| **Performance** | Generate floors on first visit, cache them, cap population, and avoid regenerating or duplicating entities on re-entry. |
| **Save/load safety** | Active floor, all visited floors, power state, elevator state, extraction state, fog, entities, and player return position survive Continue. |

## Data model

### Themed dungeon extension definition

A reusable dungeon extension is identified by a stable key, for example
`mars_alien_prison`, and contains:

- floor definitions and generation parameters
- per-floor themes, encounter pools, and activation cues
- stable objective anchors selected by the generator
- transition rules and return connection metadata
- extension-specific progress flags (power, elevator, extraction, etc.)

The alien prison is the first definition. A future cave, ruin, station, or
bunker should be able to use the same runtime with different data.

### Extension run state

A run state contains:

- `extension_id`: stable content-definition key
- `current_floor`: integer while inside the extension
- `visited_floors`: generated/cached floor maps keyed by floor number
- `floor_links`: exact up/down/elevator connection positions per floor
- `progress`: extension-specific flags, such as power restored or data extracted
- `surface_return_position`: the parent dungeon position used when entering

The implementation should prefer a serializable extension-run container over
adding many unrelated fields to `GameContext`. The container itself becomes a
single `GameContext` field and is represented by JSON-safe save/load helpers.

### Floor definitions

Each generic floor definition supplies:

- stable floor number and location name
- procedural generation parameters
- destination theme
- entry/return connection requirements
- optional objective anchor requirements
- encounter pool, capped density, and activation schedule
- extension-specific objective metadata and interaction text

Generation is procedural-first. Required rooms, connection points, and
objective anchors are selected deterministically from the generated map. A
future landmark pass may stamp hand-authored rooms or set pieces into those
anchors without changing the extension runtime.

### Security activation model

Floor 1 begins with a small number of dormant security entities or security
anchors. They do not all activate immediately. As the player explores or
crosses a small number of generated progression thresholds, a limited batch
powers up and becomes hostile. Each activation should:

- be a persistent mutation of the floor map
- present a main-quest modal popup with flavor explaining that deeper systems
  are waking, followed by an optional concise log entry
- stay capped so the opening floor remains a warning, not an ambush gauntlet
- use the existing ground-combat entity model and save/load fields

The activation schedule is generic (`activation_events` / thresholds); the
alien-prison data supplies the warning text and security enemy IDs. Player-facing
activation flavor uses the existing main-quest modal popup pattern, such as
`show_gate_popup`, rather than introducing a second notification system. The
ordinary message log may still receive a concise follow-up state update.

## Domain changes

### Dungeon/world

- Add reusable up-stair and dungeon-extension connection markers as needed.
- Add generic extension interaction metadata for objective terminals,
  elevators, and locked connections rather than overloading ship-computer or
  Act 0-specific behavior.
- Add procedural anchor selection and a future landmark-stamping hook.
- Add a small, persistent activation-event mechanism for dormant encounters.
- Route activation flavor through the existing main-quest modal popup helpers;
  do not create a parallel dungeon notification/modal system.
- Reuse existing fog-of-war, ground-combat, loot, entity, and layout parser
  paths.

### Main quest

- Keep Act 0's Mars door opening as the entrance trigger.
- Replace the current story-only Mars `>` endpoint with entry into prison Floor 1.
- Add prison objectives for reaching the engineering room, restoring power,
  reaching the deep cell, and extracting the data.
- On successful Floor 5 extraction, mark the prison objective complete and unlock
  the existing Act 1 `research_alpha` step (or its registered equivalent).
- Preserve the empty-cell ambiguity and do not reveal the escaped entity yet.

### Game loop / transitions

- Move prison floor traversal into a dedicated helper/module.
- A normal floor connection changes the active map while retaining the prior
  floor in the prison cache.
- Floor 4's elevator rejects interaction until power is restored, with a clear
  log message and guide text.
- Returning to Floor 1 and stepping out through the Mars entrance returns the
  player to the surface at the saved position.
- Re-entry uses the same prison run rather than generating a second facility.

### Save/load

- Serialize the prison-run container and every visited floor map.
- Preserve map tiles, entities, loot, fog memory, current floor, objective
  flags, power state, data extraction, and the surface return position.
- Loading inside the prison must rebuild the active floor and the outer Mars
  map/return context without duplicating the player entity.

### Guide/UI

- Add a guide section covering prison floors, free backtracking, the powered
  elevator requirement, and the Floor 5 data terminal.
- Keep interaction labels explicit: engineering console, elevator, and data
  terminal must not look like generic loot or a normal ship computer.

## Pre-implementation audit

### Scope correction from review

The first draft overfit the runtime model to a single prison. This revision
makes the reusable unit a **themed procedural dungeon extension**. The alien
prison remains the first content pack and supplies the five-floor story, but
its state keys, generation hooks, connection markers, activation events, and
serialization wrapper must be generic. The first vertical slice will prove
that generic runtime with prison-themed data and a small dormant-security
activation sequence.

### Existing classes/modules to extend or reuse

- `src/spacehack/dungeon.py`: `DungeonParams`, `generate_dungeon`,
  `load_layout`, `init_fog`, `reveal_around`, `populate_dungeon`, and
  `_scatter_squad` provide procedural generation, layout loading, fog, capped
  enemy placement, and reusable entity scattering.
- `src/spacehack/landmark.py`: `LandmarkStamp`, `load_landmark`, marker
  validation, theme inheritance, and route carving provide the future
  hand-authored landmark-stamping hook; Phase 1 should not require a fixed
  landmark floor.
- `src/spacehack/world.py`: `GameMap`, `Tile`, `Entity`, `STAIRS_DOWN`,
  `try_move`, and render/camera helpers provide map state, markers, entities,
  collision, and presentation.
- `src/spacehack/main_quest/_act0.py`: Mars surface preparation, the signal-door
  animation, `mars_stairs_pos`, and Act 0 completion are the existing entrance
  seam and must remain compatible with old saves.
- `src/spacehack/__main__.py`: existing dungeon mode, cached `ctx.interiors`,
  `_prep_cached_dungeon`, dungeon combat tick, and exit handling show how to
  hand off an active map without duplicating the player.
- `src/spacehack/game_context.py`: the dataclass is the correct home for one
  prison-run state field and existing ground/player state.
- `src/spacehack/saveload.py`: `_dungeon_to_dict`, `_dungeon_from_dict`, and
  persistent `ctx.interiors` serialization can be reused for each prison floor.
- `src/spacehack/data/main_quest/`: the registered `MainQuestStep` data and
  `main_quest_progress`/gate helpers already support unlocking the Act 1
  research trail.
- `tests/test_dungeon.py` and `tests/test_saveload.py`: existing generation,
  mutation, and round-trip tests are the regression anchors.

### Three potential duplication hotspots

1. **Floor map caching and player handoff** could duplicate the existing
   planet-surface and derelict boarding paths.
   - **DRY strategy:** extract a generic dungeon-extension transition helper
     that follows the existing `_prep_cached_dungeon` contract and centralizes
     player removal, active-map assignment, fog reveal, and parent-return state.

2. **Security activation** could become a prison-only special case or a second
   monster-spawn path.
   - **DRY strategy:** define generic activation thresholds/events and reuse the
     existing `_scatter_squad`/ground-NPC entity model; prison data supplies only
     enemy IDs, caps, and warning text.

3. **Terminal/elevator bump handling** could add another long conditional block
   to `__main__.py beside ship computers and the Act 0 console.
   - **DRY strategy:** use a table-driven extension interaction dispatch keyed by
     explicit metadata. Keep the main loop as a thin handoff.

4. **Serializing multiple floor maps** could copy the existing dungeon
   serializer and drift from ordinary interior save behavior.
   - **DRY strategy:** serialize a mapping of extension floor IDs through the
     existing `_dungeon_to_dict`/`_dungeon_from_dict` helpers, with a generic
     extension wrapper for progress and active-floor state.

## Phased implementation plan

### Phase 1 — Generic extension runtime and alien-prison Floor 1

- [x] Add a serializable themed-dungeon-extension run state container.
- [x] Add procedural floor generation parameters plus deterministic entry/return
  anchors; do not require a hand-authored floor layout.
- [x] Connect Mars `>` to the alien-prison extension's generated Floor 1.
- [x] Show a one-time first-entry flavor popup for the extension.
- [x] Add a small capped set of dormant alien security encounters and one or two
  persistent activation events that use main-quest modal popups to warn the
  player, with flavor as the systems power up.
- [x] Persist active floor, parent-dungeon return position, security activation
  progress, and the generated Floor 1 map.
- [x] Keep old Act 0 saves/load behavior compatible.

**PLAYTEST:** Open the Mars door, step onto `>`, confirm a procedural
`Alien Prison F1` loads and shows a one-time first-entry flavor popup;
explore until a main-quest modal popup warns
that security systems are powering up; verify that one nearby security unit
appears. Continue exploring until the second popup fires and the other nearby
security unit appears; either unit may come first because the route is
procedural. Quit and Continue inside Floor 1; return to Mars; re-enter without
generating a second facility; verify activated security stays activated and
does not show the popup again.

**Implementation checkpoint:** The generic extension runtime, procedural Floor 1,
Mars entry/return, persistent activation events, guide section, and save/load
coverage are implemented. Automated validation: `python3 tools/smoke.py` passes
and `python3 tools/test.py` passes with 227 tests. Manual playtest remains the
next checkpoint before Phase 2.

**Playtest result:** The Floor 1 HUD label remained readable as `Alien Prison F1`.
Both security activations fired and spawned nearby enemies; the deeper trigger
was reached first in this procedural run, spawning the assault drone before the
sentry drone. Save/Continue, return to Mars, and re-entry all worked. Encounter
order is intentionally route-dependent rather than tied to enemy type.

### Phase 2 — Floors 2-3 and free backtracking

- [x] Add low-risk quarters with empty cells and security posts.
- [x] Add the defensive floor with capped security/pest encounters.
- [x] Add up/down links and preserve each floor's mutations.

**PLAYTEST:** Descend through Floor 3, defeat or bypass a defense, backtrack to
Floor 1, verify defeated enemies/loot/fog remain changed, save on each floor,
and Continue from each floor.

**Implementation checkpoint:** Floors 2-3 now use the generic procedural
extension runtime. Floor 2 has low-risk quarters with procedural empty-cell
doors, security posts, alien pests, and a deeper `>` connection. Floor 3 has
procedural defensive barriers, security nodes, a defensive security/pest mix,
and no deeper connection yet. Each visited floor is cached under its stable
extension key, with `<`/`>` connection metadata and feature-theme metadata
serialized alongside the map. Automated validation: `python3 tools/smoke.py`
passes and `python3 tools/test.py` passes with 235 tests. Manual playtest is
the next checkpoint.### Phase 3 — Floor 4 engineering and powered elevator
- [x] Add high-risk quarters and larger empty cells.
- [x] Add engineering room and power-restoration interaction.
- [x] Gate the elevator until power is restored, then enable Floor 5 travel.

**PLAYTEST:** Attempt the elevator before engineering (blocked); restore power;
verify the elevator works after leaving/re-entering Floor 4 and after Continue.

**Implementation checkpoint:** Floor 4 is procedurally generated with reusable
high-risk cell/security markers, an engineering console, and a deep elevator.
The extension's power flag is persistent and the elevator now transitions to a
procedural Floor 5 staging map. Phase 4 will replace that staging map with the
hand-authored deep-cell/data-extraction content.


### Phase 4 — Floor 5 deep cell and data extraction

- [ ] Add the giant empty cell, torn doors, scattered terminals, and one live
  terminal.
- [ ] Add data extraction interaction and incomprehensible result.
- [ ] Complete the prison objective and unlock Act 1 `research_alpha`.

**PLAYTEST:** Reach Floor 5, inspect inactive terminals, extract from the one live
terminal, verify the objective completes and Alpha research becomes available;
save/Continue before and after extraction.

### Phase 5 — Tuning, landmarks, guide, and final regression pass

- [ ] Tune security/pest populations and encounter pacing.
- [ ] Add optional hand-authored landmarks stamped into generated anchors.
- [ ] Update the in-game guide and main-quest design references.
- [ ] Add generation, transition, activation, mutation, and save/load regression tests.
- [ ] Run smoke and the full test suite.

**PLAYTEST:** Complete the full five-floor run, return to Mars, visit Alpha
Centauri, and confirm the Act 1 research trail starts with the incomprehensible
data rather than a human-readable explanation.

## Acceptance criteria

- The opened Mars stairs enter one persistent themed dungeon extension, not a
  fresh random cave each time.
- The alien prison content definition supplies five distinct floors with the
  progression above.
- The runtime can accept a future themed dungeon definition without a new
  transition/save/load implementation.
- Floor generation is procedural-first and deterministic for the run.
- Dormant security activation is capped, visible through the main-quest modal
  popup pattern, and persistent.
- Cells are empty; danger comes from pests/security and environmental systems.
- Free backtracking works between visited floors and back to Mars.
- The Floor 4 elevator cannot be used before engineering power is restored.
- Floor 5 contains one usable data terminal and incomprehensible extracted data.
- Extraction unlocks the existing Act 1 research trail at Alpha Centauri.
- Every mutable prison/floor state survives save/load without duplication.
- The guide explains the new player-facing mechanics.
- Smoke and the full test suite pass.

## Open questions

- Exact prison enemy IDs and security mix should be selected during Phase 5
  tuning from the existing NPC catalog.
- The exact generic activation-event schema may be finalized during Phase 1,
  but it must support future themes without prison-specific branches.
- The final terminal's one-line immediate flavor text can be refined during
  implementation, but it must not decode the data or reveal the escaped entity.
