# Design: Living Planetary Cities

## Overview

Expand planetary landing cities from small, mostly static service maps into
large, authored, camera-scrolled places that feel like another form of
navigation in the game. Earth is the first test city and becomes a 160x100
ASCII environment with districts, public transit, moving NPCs, building
interiors, and the existing services preserved.

The city layer should feel active without becoming a full civilian simulation.
NPCs use deterministic movement and faction-aware interaction rules. Named
service NPCs remain important mission and dialogue actors; ambient NPCs make
the streets feel inhabited and can become traders, allies, or threats as the
content catalog grows.

The first implementation is intentionally vertical and conservative:

- Earth is the content proving ground.
- Existing Earth buildings and functionality remain available.
- Hostile city encounters begin on direct contact in the first slice.
- NPC-on-NPC battles, broad crowd simulation, and complex daily schedules are
  follow-up work.
- All maps and decoration remain data-first and authorable with the existing
  layout editor.

## Decisions

| Topic | Decision |
|---|---|
| First city | Earth only; other planets keep their current layouts until migrated. |
| City size | 160x100 cells, larger than the current viewport and camera-scrolled. |
| Visual style | Crisp ASCII/bitmap glyphs, integer camera coordinates, and nearest-neighbor presentation. |
| City timing | Every player action advances one city simulation tick. |
| Transit | A physical, named transit network; public transit is free in the first slice. |
| NPC behavior | Space-NPC-inspired movement with deterministic goals and faction identity. |
| Hostility | First slice starts combat on bump/contact; detection-range combat can follow. |
| Interiors | Separate authored maps, cached per planet/building, with exact exterior return positions. |
| Earth content | Preserve the spaceport, bar, bounty guild, merchant guild, militia, trade, missions, ship buying, mechanic, armory, and existing named NPC roles. |
| First content pass | Core districts, transit hub, one central plaza feature, a river-to-coast waterway, and five functional building interiors. |
| Save/load | Persist the active city/interior state and return locations without breaking old saves. |

## Philosophy alignment

| Project rule | Application |
|---|---|
| Data-first | City districts, buildings, transit nodes, NPC templates, routes, and interiors are catalog data rather than dispatcher conditionals. |
| `ctx`-first design | City simulation, current interior identity, transit state, and interaction state live on `GameContext` or explicit map metadata; helpers receive `ctx` first. |
| Reuse before duplication | Reuse `world.GameMap`, camera math, `find_path`, `Entity`, faction attitude, ground combat, NPC dialogue, trade, mission boards, and the layout loader/editor. |
| Save/load contract | City and interior maps are stable cache entries keyed by `planet_id:building_id`; dynamic entity positions and relevant building state are serialized. |
| Crisp presentation | Use the existing logical cell renderer and bundled monospace font. Do not introduce smoothing, fractional camera positions, or raster-art dependencies. |
| Pure computation is tested | District generation, transit routing, NPC target selection, tick advancement, entrance/exit resolution, and hostility decisions receive focused tests. |
| Player-facing changes are documented | Update the in-game guide and README with city movement, transit, entrances, and encounter controls. |
| Atomic changes | Land the foundation, transit/interiors, NPC activity, and content/polish as independently testable phases. |

## User experience

### Outdoor city

The player lands in a 160x100 Earth map. The viewport follows the player while
keeping map coordinates integer-aligned. Earth is intentionally re-authored;
its existing building arrangement and palette do not constrain the new city.
The city is organized into readable areas rather than a uniform field:

- spaceport and landing apron
- central transit hub and civic plaza
- market/merchant district
- nightlife/bar district
- militia/security district
- bounty and industrial edge
- parks, residential street blocks, service alleys, a central plaza feature,
  and a major Earth water feature such as a river, lakefront, or beach

Roads, sidewalks, plaza surfaces, building walls, signs, vegetation, lights,
and district markers use distinct glyph and color treatments. Decoration must
support navigation: the player should be able to infer where they are from the
map, not just see a larger field of random symbols.

### Building entry

A building is represented by an exterior entrance entity or tile with metadata:

- stable `building_id`
- display name and district
- interior layout id
- interaction/service id, if any
- return position outside the door
- optional interior NPC and decor population rules

Bumping the entrance loads or creates the building's interior map. The player
walks through the same movement/combat/interaction model used elsewhere. A
return marker or exit sends the player back to the saved exterior position.

The first five interiors are functional, lightly themed maps:

- bar: counter, tables, a small customer population, and the existing barkeep dialogue
- ship store: showroom ship markers and sales interaction
- merchant hall: trade fixtures and mission-giver setting
- militia center: armory/mechanic/security presentation as appropriate
- bounty guild: mission-board setting and bounty NPC

The first pass does not require a fully simulated crowd or a finished art pass
inside every room. Detailed decoration, richer customer populations, and
additional landmark interiors are Phase 4 content work.

Exterior and interior layouts are authored using the existing landmark `.layout`
format and can be previewed/edited with `python -m tools.layout_editor`. The
city loader should resolve asset ids from data, so replacing a facade or room
changes a layout asset or catalog entry rather than game-flow code.

### Transit

Transit nodes are visible, walkable-to objects in the outdoor city. A transit
node offers a list of named reachable stations from the data-defined network.
The player selects a destination, sees a short themed departure/arrival
transition, and arrives at the destination station. Transit is free and does
not require fuel. It does advance the city simulation according to the normal
one-action tick contract.

The first Earth network should include the central hub plus stops near each
core district. A future planet can replace the implementation with a tram,
maglev, elevator, shuttle, or other theme without changing the interaction
contract.

### City NPCs

City NPCs use a shared data model with:

- stable catalog id and display glyph
- faction id and attitude behavior
- role (`civilian`, `merchant`, `guard`, `wanderer`, or named service role)
- movement route or destination set
- contact behavior (`talk`, `trade`, `mission`, `fight`, or a combination)
- optional interior destination

Each city tick, eligible ambient NPCs take at most one movement step toward an
assigned destination or route waypoint. Movement uses the existing map
pathfinding and collision rules. Goals and route choices are deterministic
from the run seed, city id, NPC id, and current city tick so save/load and
re-entry do not cause arbitrary reshuffles.

Named NPCs retain their authored building positions and current dialogue,
mission, and faction behavior. Ambient NPCs are the first expansion surface.
The first combat slice supports direct-contact hostile encounters and does not
start fights merely because an enemy is nearby. NPC-on-NPC combat is deferred.

### ASCII presentation

The city and interiors use the same renderer-neutral cell commands as existing
maps. Requirements:

- one logical cell maps to one glyph draw operation
- camera movement is integer cell movement
- no anti-aliased or filtered scaling
- tile backgrounds remain explicit and readable under glyphs
- entities use high-contrast colors against their tile underlay
- decorative glyphs are selected from the supported project font set
- overlays do not replace the map with a raster screenshot

## Data model

### Planet city specification

Extend the existing planet data without making the game loop know individual
planet layouts:

```python
PlanetSpec(
    city_width=160,
    city_height=100,
    districts=(...),
    buildings=(...),
    transit_network=..., 
    ambient_npcs=(...),
    public_landmarks=(...),
)
```

The exact field names may follow the existing `PlanetSpec` conventions after
the pre-implementation audit. Existing `width`/`height` fields remain
compatible for planets not yet migrated.

### District data

A district defines its id, bounds, theme/palette, street pattern, decoration
rules, and building ids. District generation must be deterministic and must
leave walkable paths between the transit network and every core building.

Earth's major water feature is a deterministic river that enters from the
northwest, crosses the city through a managed floodplain, and widens into a
coastal edge/harbor along the eastern boundary. Bridges are authored or placed
at named crossing points so the river creates meaningful routes without
splitting the city into unreachable regions. Water is non-walkable; shore,
bridge, pier, and park tiles remain walkable and visually distinct.

### Landmark-authored city architecture

Reuse the current landmark system as the authoring boundary for city
architecture:

- `landmark.load_landmark()` remains the shared loader for `.layout` assets.
- The existing shared parser, tile mappings, color directives, and editor
  validation remain the source of truth for authored cells.
- Add a city-safe stamp operation that copies an authored footprint at a fixed
  city origin and returns its footprint, entrance, and interaction anchors.
  It must not assume a dungeon spawn or carve a dungeon route.
- Keep the existing dungeon-oriented `stamp_landmark()` behavior unchanged for
  Mars and prison landmarks; city stamping is a separate mode/helper because
  city maps have roads and fixed origins rather than generated dungeon rooms.
- City landmark assets may define facade, wall, door, sign, water-edge, pier,
  and decorative cells. Service terminals and named NPC slots remain catalog
  metadata attached to the landmark, so functional behavior is not encoded in
  glyph guesses.
- Persist the asset id, origin, footprint, and anchor metadata on the city map
  so save/load and debugging can identify exactly which authored asset is in
  use.

The Phase 1 Earth map should use this path for the five functional building
exteriors and the central plaza feature. The river/coast terrain is generated
from deterministic city terrain data because it is a large continuous feature,
while small riverfront structures can be landmark assets.

### Building data

A building definition extends the existing `CityBuilding` contract with stable
identity and authored asset metadata:

- `building_id`
- `exterior_layout_id`
- `interior_layout_id` (used in Phase 2)
- fixed origin or placement anchor
- entrance/return anchor
- service interaction id
- existing `label`, coordinates, door position, orientation, and NPC slot
  behavior where still useful

Existing service flags must continue to resolve through their current
interaction functions. Changing `exterior_layout_id` or `interior_layout_id`
should be sufficient to swap the authored presentation.

### Interior cache

Use the existing `ctx.interiors` cache with a namespaced key such as:

```text
city:earth:bar
city:earth:ship_store
```

The cached `GameMap` stores its layout identity, entry/exit metadata, entity
positions, and any interaction state needed to make visits consistent. Static
interiors may be rebuilt from authored layouts while dynamic interior state is
restored from the cache/save payload.

### City simulation state

Add only the state required by the first slice:

- current city simulation tick
- active city map/interior identity
- outdoor return position and building id when inside
- per-city NPC positions and route progress, if not stored directly on the map
- transit destination/arrival state only while a transition is active

Avoid adding a second global time system. The existing game clock remains the
long-range world clock; city ticks are local action ticks used to animate
nearby activity and resolve deterministic movement.

### NPC interaction contract

A city entity should be able to dispatch through the existing interaction
surface:

- named `npc_id` -> current dialogue, mission delivery, and mission board flow
- merchant role -> NPC trade modal using the existing trade data and economy
- hostile role/faction -> ground combat on direct contact
- neutral/allied role -> talk or trade, with no combat unless a future rule says otherwise
- service role -> building-specific existing service interaction

The implementation should add a small table-driven city interaction resolver
rather than expanding a chain of building-specific checks in the main loop.

## Domain changes

### Shared map/runtime

- Extend camera-backed city rendering to support all migrated city sizes.
- Keep `world.render_world_view` as the map presentation path for outdoor and
  interior maps.
- Reuse the landmark loader/parser/editor for authored city footprints.
- Add a city-specific landmark stamp helper rather than changing dungeon
  landmark route-carving semantics.
- Add map metadata for city/interior identity, landmark asset ids, origins,
  footprints, entrances, exits, and transit nodes without making generic
  `GameMap` behavior city-specific where avoidable.

### Game flow

- Preserve city -> space launch and planet landing transitions.
- Use camera-backed rendering during landing/launch animations; centered rendering
  is invalid for a city larger than the viewport.
- Add city -> interior and interior -> city transitions.
- Ensure launching always returns to the correct outdoor city map and hangar.
- Advance city simulation once per accepted city action, including movement,
  waiting, transit, and building entry/exit.
- Keep dungeon combat and space combat behavior unchanged outside the new city
  entry points.

### Persistence

- Extend save/load to retain the active city or interior identity, exterior
  return position, and dynamic city map/entity state where required.
- Old saves with only `current_city_id` and city coordinates must load through
  the migrated Earth layout with a valid fallback position.
- Round-trip tests must cover outdoor Earth, each first-wave interior, transit
  arrival, and an active city NPC position.

### Guide/content

Update the in-game guide and README with:

- city camera scrolling and districts
- building entry/exit
- transit controls and station interaction
- city NPC interaction and hostile-contact behavior
- the distinction between city ticks and long-range world time

## Pre-implementation audit

This audit was completed after design approval and before implementation.
It inspected the exact current contracts for:

- `PlanetSpec` and all planet loaders
- `GameMap` camera/render metadata and map serialization
- `GameContext.interiors` and save/load rebuild paths
- city movement and blocker resolution in `game_loop.py` / `game_interactions.py`
- existing ground combat entry and faction hostility helpers
- `npc_ships.py` movement/path caching patterns
- layout editor format/validation support for city interior assets
- in-game guide data and README workflow

Audit findings:

- `world.camera_for_view()` and `world.render_world_view()` already support
  maps larger than the viewport with integer cell cameras. City mode must call
  those functions instead of `world.render_world()` once Earth is 160x100.
- `city._animate_ship_to_y()` currently uses centered rendering and must use the
  same camera-backed path for the expanded Earth landing/launch animation.
- `PlanetSpec` owns dimensions, buildings, themes, and showroom data. Earth can
  be re-authored as a dedicated `PlanetSpec` layout while non-Earth specs retain
  their current dimensions and layout behavior.
- `load_planet()` currently calls `world._layout_outside()`, whose detailed
  road/plaza pass is hard-coded to 60x40. Phase 1 will add an Earth-specific
  160x100 builder and leave the compact-city path intact for other planets.
- City saves rebuild through `saveload_maps._rebuild_city()` and store city id,
  mode, and player coordinates. No old saves need migration; new Earth saves
  must simply use valid generated coordinates.
- Existing interaction resolution keys off `Entity` flags (`ship_id`, `npc_id`,
  and terminal flags), so Phase 1 must preserve those entities even if their
  coordinates and surrounding architecture change.
- The working tree contains only the new untracked design document; no user
  changes were found in the Phase 1 implementation files.

The audit changes the implementation order: first add a pure Earth city layout
builder and tests, then switch city rendering and landing animation to the
existing camera path, and finally run the full gate before beginning Phase 2.

## Phased implementation plan

### Phase 1 - Scrolling Earth foundation

- [x] Migrate Earth to a deterministic 160x100 outdoor map.
- [x] Add camera-follow rendering and map-edge handling for city mode and
      landing/launch animations.
- [x] Re-author Earth freely with a central plaza feature and a river-to-coast
      water feature; preserve all current Earth buildings, service terminals,
      named NPC slots, and hangar behavior.
- [x] Add the city-safe landmark stamping path and author swappable exterior
      assets for the five functional Earth buildings plus the plaza feature.
- [x] Add pure tests for dimensions, walkability, water boundaries, landmark
      footprints/anchors, district markers, and reachability from the landing
      pad to every core building.
- [x] No old-save migration is required for this project phase.

**PLAYTEST**

1. Start a new Earth run and walk far north, south, east, and west.
2. Confirm the camera scrolls without stretching or blurring glyphs.
3. Reach each current Earth building from the landing pad and cross the river
   at each named bridge.
4. Inspect the central plaza feature and confirm the river reaches the coast.
5. Launch from the hangar and return to Earth; verify the outdoor map and
   player position remain coherent.
6. Launch into space and land back on Earth; confirm the expanded map and
   landing animation remain camera-aligned.
7. Swap one authored exterior asset id in Earth data, rebuild the city, and
   verify the replacement changes the facade without changing interaction code.

**Phase 1 verification record**

- Automated Earth, camera, landmark, reachability, Pygame, and ship-anchor
  coverage passes.
- The headless landmark validator accepts all shipped assets.
- `make check` passes with the full test suite.
- Manual checklist items 1-7 remain useful for an interactive run with Pygame;
  the current environment has no display/browser session for visual inspection.

### Phase 2 - Transit and building interiors

- [x] Add data-defined Earth transit nodes and a free station-to-station route.
- [x] Add stable building entrance metadata and interior transition helpers.
- [x] Resolve interiors through the same landmark asset-id/catalog path used by
      Phase 1 exteriors.
- [x] Author and validate five functional, lightly themed Earth interior layouts.
- [x] Cache interiors by `planet_id:building_id` and return to the exact exterior
      door position.
- [x] Preserve current service NPC interactions inside the authored interiors.
- [x] Add save/load metadata for active city interiors and exterior return doors.

**PLAYTEST**

1. Walk from the landing pad to the central transit hub.
2. Travel to each core district stop and verify arrival glyphs/theme.
3. Enter the bar, ship store, merchant hall, militia center, and bounty guild.
4. Confirm each interior has a distinct basic ASCII theme and its existing
   service/NPC function still works.
5. Leave and re-enter an interior; verify its map and dynamic entities persist.
6. Save inside an interior, continue, and verify the player returns to the same
   interior and exterior return metadata remains intact.

**Phase 2 verification record**

- Five Earth interior assets load through the shared landmark parser/editor.
- Entry, exact-door exit, cache reuse, service-NPC transfer, and save metadata
  have focused regression coverage.
- A data-defined Earth transit network is live: six ``TransitStation`` nodes
  (Spaceport, Central Hub, Bar District, Bounty Guild, Merchant Hall, Militia
  Center) placed on walkable cells with a fully connected route table, a
  bump-to-menu bump interaction that rides to the chosen destination, and
  a deterministic ``game_map.city_transit`` lookup. Stations are rebuilt with
  the Earth map on save/load, so no new persistence payload is required.
- ``tests/test_city_transit.py`` covers placement on walkable cells, route
  integrity, travel motion, cancel, empty-route fallback, and menu dispatch.
  Full suite, lint, and architecture gate pass.

### Phase 1.5 - Earth circulation and presentation correction

- [x] Stop road paint at the river so bridges remain the only crossings.
- [x] Route each functional building entrance to a real road, bridge, or landing pad.
- [x] Preserve exact tile backgrounds behind the player glyph on dense terrain.
- [x] Add regression coverage for road/water boundaries, entrance routes, and
      player underlay colors.

This pass keeps the map's existing macro arrangement but repairs the most
visible foundation defects: roads no longer disappear into water, sidewalks
terminate at meaningful public routes, and the player glyph no longer inherits
bright blended color from dense terrain glyphs.

### Phase 3 - City NPC activity and direct-contact encounters

Pre-implementation audit (completed before code changes):

- City mode currently runs **no NPC simulation** — after a city action the
  loop does not advance ambient entities. Phase 3 adds exactly one
  ``move_city_npcs`` call per accepted city action (movement and wait),
  mirroring how ``ground_npcs.move_ground_npcs`` ticks dungeon ground NPCs
  after the player moves.
- Movement/combat reuse: ``ground_npcs`` already implements one-cell
  deterministic steps, faction-aware patrol/wander, ``squad_id`` cohesion,
  ``combat_locked`` freezing, and ``world.find_path`` A*. Phase 3 reuses
  these patterns; it does **not** duplicate a movement engine.
- Hostility already flows through ``faction.spec_is_hostile`` (faction
  reputation + ``always_hostile``). City ambient NPCs reuse that predicate
  via an ``npc_char_id`` that resolves to a ground :class:`NpcCharSpec`.
- Direct-contact combat reuses ``combat._rules_ground.init(...)`` with a
  list of hostile ``world.Entity`` (the bump target), the same entry the
  dungeon LOS-aggro path uses. Phase 3 is bump-triggered only per the
  hostile-on-direct-contact decision.
- Talk/trade reuse: the occupied-blocker dispatch in
  ``game_interactions._resolve_occupied`` keys off ``npc_id``. Ambient
  city NPCs get a new ``city_npc_id`` Entity field routed through that
  same dispatch to dialog/trade/fight without expanding main-loop checks.
- Determinism: ambient placement and route choice use
  ``engine.seeded_rng(INIT_SEED, city_id, npc_id, ...)`` so save/load and
  re-entry don't reshuffle routes (matches the Earth skyline pattern).
- Persistence: the city map rebuilds deterministically on load, so ambient
  NPC *identity and seed* persist for free; their **current positions** must
  be saved like other dynamic entity state. Store a
  ``ctx.city_npc_positions`` dict and reapply after rebuild.

- [x] Add data-defined ambient city NPC templates and Earth populations.
- [x] Implement deterministic route/destination movement, collision avoidance,
      and one-step-per-city-tick updates.
- [x] Add NPC talk/trade dispatch using existing catalogs and modals.
- [x] Add faction-aware direct-contact hostile encounters using existing ground
      combat and faction attitude rules.
- [x] Ensure named service NPCs stay anchored unless explicitly configured to
      move, and prevent combat movement code from running twice.
- [x] Persist city NPC positions/routes and add deterministic save/load tests.

**PLAYTEST**

1. Walk and wait in the city; verify ambient NPCs move one cell per city tick.
2. Leave and return to the city; verify seeded NPC routes are stable.
3. Talk to a named Earth NPC and confirm current dialogue/mission behavior.
4. Contact a neutral or allied NPC and verify no combat starts.
5. Contact a hostile NPC and verify ground combat starts through the existing
   combat flow.
6. Save during active city activity, continue, and verify NPC positions and
   hostility behavior remain coherent.

### Phase 4 - Content, crispness, and workflow polish

- [x] Complete the Earth core district decoration pass and public landmark.
      Added 34 trees, 19 neon signs, 14 ornaments, and a public monument
      (cyan `♦` diamond + ornament posts) south of the central plaza.
- [x] Tune glyph contrast/backgrounds for all districts and interiors.
      Created high-contrast MONUMENT tile (10.0:1 ratio). Verified all city
      decorative tiles meet WCAG AA contrast thresholds.
- [x] Add compact city playtest/debug tooling for inspecting camera, transit,
      building ids, NPC routes, and map coordinates.
      F3 toggle (SPACEHACK_DEV) overlays camera coords, player tile,
      district name, transit stops, building count, and NPC count.
- [x] Add regression tests for resize/asset loading failures and unreachable
      city destinations. 6 new tests in test_city_builder.py covering
      Earth reachability, transit placement, NPC spawns, missing interiors,
      and tiny-map edge cases.
- [x] Update the in-game guide, README, and design playtest record.
      Guide updated with transit and ambient NPC info; README updated
      to mention Mercury and the new city features.
- [ ] Run the full project gate and review the final user-facing flow.

**PLAYTEST**

1. Visit every district using walking and transit.
2. Check that all decorative glyphs remain crisp at the configured window size.
3. Verify no building, transit stop, NPC, or landmark is unreachable.
4. Exercise all five core services after a save/continue cycle.
5. Run `make check` and the city-specific test suite.

### Phase 5 - Data-driven city pipeline for every landable city

Pre-implementation audit (completed before code changes):

- Every landable planet already authors a `PlanetSpec` with data-driven
  knobs: `theme` (8 presets + `derive_theme`/`override_theme`), `buildings`,
  `transit_stations`, `interior_layouts`, `city_npc_population`,
  `showroom_ships`, `mech/armory` inventories, and `mission_tier`. The
  Earth-special machinery (transit, interiors, ambient NPCs) is already
  generic — it reads those spec fields, not Earth constants.
- The **only** structural special case is the loader fork:
  ``load_planet`` routes `city_layout_id == "earth_river_coast"` to
  ``build_earth_city`` (160x100 authored river/coast/road/skyline layout)
  and every other planet falls through to the legacy compact builder
  (bare floor grid + building blocks, no roads, no transit, no interiors,
  no NPCs). Nothing else in the game depends on that fork; Earth's own
  transit/interiors/NPCs run through generic spec-driven code.
- Reusability goal: **one city builder for every landable city.** The
  layout (river/coast vs. grid vs. station) becomes a data-selected
  generator keyed by `city_layout_id`; all planets flow through the same
  pipeline. A desolate moon base and a research station then operate
  identically to Earth while reading as clearly different worlds.
- Proof city: **Mercury** (Sol-adjacent, already a compact research
  station with a lab + `research_officer` + `act0_lab` main-quest chain
  + militia cave delve). Mercury needs more buildings to exercise the
  pipeline meaningfully: a **bar** (a base with no bar is unthinkable)
  and a **supply depot**, plus authored interiors, a transit network,
  and an ambient population.

- [x] Promote `build_earth_city` to a generic `build_city(spec, ...)`
      where the river/road/plaza geometry is a layout generator selected
      by `city_layout_id` from data.
- [x] Delete the `earth_river_coast` special-case fork in `load_planet`
      so every planet flows through the same builder path.
- [x] Theme-parameterize the layout painters so non-Earth planets get
      their theme's roads/plaza/pad instead of Earth's palette (the
      generic grid builder uses each spec's readability-adjusted theme;
      compact stations with no roads get the whole walkable floor as
      their traffic lanes).
- [x] Expand Mercury: add a bar and a supply depot to its `PlanetSpec`,
      sized to a compact research station.
- [x] Author Mercury interiors + transit stations + ambient NPC
      population (data only).
- [x] Add tests asserting Earth and Mercury run through the identical
      builder path and both produce walkable, reachable, serviceable
      cities.
- [x] Run the full gate with both cities exercised.

**PLAYTEST**

1. Land on Mercury; verify its layout reads as a compact scorched
   research station, not a recolored Earth.
2. Walk between the port, lab, bar, and supply depot; confirm each is
   reachable and its interior works.
3. Ride Mercury's transit and bump its ambient NPCs; confirm the same
   interactions as Earth.
4. Land on Earth again; confirm nothing about the Earth city changed.

**Phase 5 verification record**

- `city_builder.build_city(spec, ...)` is the single entry point;
  `load_planet` has no per-planet fork. Earth keeps its authored
  river-coast layout (`earth_city.build_earth_layout`, selected by
  `city_layout_id == "earth_river_coast"`); every other planet flows
  through the generic grid builder (the former legacy path plus the
  Phase 2/3 systems).
- The generic grid builder places buildings, showroom ships, terminals,
  landing pad, per-planet interior building records, transit stations,
  and ambient NPCs — all from spec data. Earth's transit/NPC placement
  now runs through that same shared tail.
- Mercury is the proof city: port + lab + new bar + new supply depot,
  a fully-connected 5-stop transit network (port, commons hub, lab,
  cantina, supply), four authored interiors (`mercury_*_interior`), and
  a station-crew ambient population — all data-only.
- Mercury now uses the **authored layout treatment** like Earth instead
  of the legacy building boxes: four stamped exterior roof assets
  (`mercury_*.layout`) with roof labels, a service-road strip, a
  commons plaza, a landing apron, sparse scorched scrub, deck beacons,
  and a small procedural skyline of utility domes — all through the
  shared `city_layout` machinery (stamping, roof labels, skyline,
  records), so Earth and Mercury run the identical authored pipeline.
- Movement generalization: cities whose traffic lanes don't span the
  map (compact stations with just a pad) fall back to the whole
  walkable floor as their landmark pool, so citizens cross the base
  instead of pacing the pad. Mercury's landmark pool spans the map.
- The authored-layout machinery was extracted from `earth_city.py` into
  `city_layout.py` (shared by Earth + Mercury); Earth's build output is
  byte-identical after the extraction (same seeds, same RNG order).
- Layout-editor asset mode is now content-driven (`CITY_*` tiles =>
  city asset) instead of the `earth_city_` name prefix, so Mercury's
  interiors validate the same way Earth's do.
- Focused tests (`tests/test_city_builder.py`) cover the shared
  pipeline, Mercury reachability, station/door placement, interiors,
  and the floor-as-lanes fallback.
- Full suite (1378 tests), lint, architecture, smoke, and main-quest
  gates pass; Earth's city is byte-identical in layout to before.

## Acceptance criteria

- Earth is a 160x100 city that scrolls smoothly in the existing cell renderer.
- The current Earth services and named NPC functionality remain available.
- Districts and decoration make outdoor navigation readable and planet-themed.
- Every city layout has a coherent civil-engineering plan: districts have
  readable purposes, roads and sidewalks form intentional connected routes,
  crossings are placed where routes need them, and terrain/empty space support
  the settlement's stated identity rather than looking procedurally scattered.
- Buildings never overwrite or block roads, sidewalks, bridge approaches,
  transit approach cells, or building doors.
- Every enterable building has a real exterior entrance, a valid interior
  spawn, and an exit that returns to the corresponding exterior door area.
- Transit is physical, named, free, and usable to move between core districts.
  Each station is adjacent to, but not on, the sidewalk; does not block the
  sidewalk or building door; and is on the same building side as the door it
  serves.
- Shipyard/spaceport landing aprons use a deliberate, low-noise floor under
  ships and terminals. Generic `.` texture is omitted where it makes the pad
  visually cluttered, while pad readability, collision, and landing anchors
  remain intact.
- Building roofs are complete, fit their footprints, and use restrained
  readable labels or decoration. Decorative letters must not create accidental
  words or visual noise, and no roof label may clip its first or last character.
- Cities feel believable and remain immersive: infrastructure, buildings,
  traffic, empty space, and NPC activity reinforce the settlement's theme and
  scale instead of reading as arbitrary decoration.
- Five core buildings load distinct cached interior maps with basic themed decoration.
- Building exteriors and the plaza feature are supplied by swappable landmark
  assets with persisted ids and anchors.
- Interior exits return to the correct outdoor location.
- City NPCs move deterministically one step per city tick.
- Named NPCs support existing talk/mission behavior.
- Neutral/allied NPCs can be approached without forced combat.
- Hostile NPCs start existing ground combat on direct contact.
- Save/load preserves active city/interior state and does not break old saves.
- All authored maps use crisp ASCII-style rendering through the existing font
  and renderer.
- The in-game guide documents the new city interactions.
- `make check` passes with focused regression coverage.

## City authoring invariants

These rules apply to every landable city, station, moon base, and other
walkable planetary settlement. They are design constraints, not optional polish
and not assumptions to be recovered from a screenshot after implementation.

### 1. Plan the circulation before placing the buildings

Each city must have an intentional human-readable plan before assets are
stamped:

- Define the city's districts, primary destinations, service routes, public
  spaces, terrain constraints, and settlement edges.
- Lay out the primary roads, sidewalks, bridges, ramps, and other circulation
  routes first. They must connect the landing area, transit network, and every
  enterable building without arbitrary dead ends or accidental chokepoints.
- Place buildings inside the planned blocks or terraces afterward. A building
  footprint must fit its assigned area and may not consume a road, sidewalk,
  bridge approach, entrance tile, or required pedestrian clearance cell.
- Leave intentional empty space for yards, plazas, landing safety zones,
  wilderness, industrial separation, or sight lines. Empty space is part of the
  plan, not evidence that the map needs more decoration.
- Use the city's terrain and infrastructure to explain its shape. A canyon,
  ring, river, crater, station deck, or coast must affect routes and zoning in
  a way that is legible to a player.

A city is not complete if its buildings are individually attractive but the
routes between them do not make sense as a connected public layout.

### 2. Building and entrance clearance

For every enterable building:

- The exterior roof/wall footprint must be complete and occupy only its
  assigned building cells.
- The building must expose a visible, walkable entrance.
- The entrance must connect to a sidewalk, road, bridge, plaza, landing apron,
  or other deliberately planned public route.
- The building footprint and its entrance clearance must not overwrite or
  block roads, sidewalks, transit stations, doors, bridge approaches, or the
  only route to another destination.
- The interior must place the player at a valid entry point and return the
  player to the same exterior entrance area, not to an arbitrary offset.

### 3. Transit placement

Transit placement follows a strict relationship to the destination building:

- A station must be on the same side of the building as the destination door.
  "Near" is insufficient if the station requires the player to walk around the
  building or approach from the opposite facade.
- A station must be next to the sidewalk, but never occupy the sidewalk itself.
- A station must not occupy the building door, its approach cell, or the
  clearance needed to enter/exit the building.
- Transit stops must not block roads, bridges, landing pads, or other required
  circulation routes.
- The station's name, id, destination, and rendered position must agree. A
  spaceport stop is named `Spaceport`; city-specific names must be clear to a
  player and stable in data.

These relationships must be represented in city data and checked by tests;
they must not depend on a visual convention or an agent remembering a prior
city's placement.

### 4. Landing-pad and shipyard clarity

Shipyard landing aprons must reserve clear operational space around the
player-owned ship, terminals, and visiting ships:

- Do not texture the operational floor with repeated `.` glyphs when they
  compete with ships, terminals, or player navigation.
- Keep ships and terminals separated enough that the player ship is obvious,
  the spaceport entrance is not blocked, and landing/launch anchors remain
  usable.
- Use themed floor tiles, blank floor, or restrained structural markings
  instead of visual filler. Any markings must communicate a real function.

### 5. Roof and facade quality

Roofs and facades are authored architecture, not debug output:

- Fill the entire declared footprint; no missing roof/wall tiles.
- Keep roof labels crisp, centered or intentionally aligned, and fully inside
  the roof footprint. Never clip the first or last character.
- Use alphabetic glyphs only for intentional readable labels. Decorative
  patterns must not form accidental words or repeated letter noise.
- Keep labels and facade decoration restrained enough that the building reads
  as a building before it reads as a sign.

### 6. Immersion and plausibility review

Before marking a city complete, review it as a place rather than as a set of
passing coordinates:

- Does the city communicate what it is, who built it, and why it occupies this
  terrain?
- Do building scale, district spacing, road hierarchy, transit placement,
  landing operations, and NPC routes agree with one another?
- Are important services easy to find without making every building or route
  identical?
- Does the map have enough activity to feel inhabited, with enough quiet space
  to preserve readability and believable scale?
- Would a human civil engineer accept the circulation plan and clearances?

A city that passes reachability tests but fails this review is not done. Record
any playtest correction in the city's Phase 6 entry before moving on.

## Open questions

All product questions discussed so far are resolved:

1. City size: **160x100**.
2. Transit: **physical transit network**, free in the first version.
3. City timing: **every player action advances one city tick**.
4. NPC behavior: **space-NPC-inspired movement and faction identity**, with
   broader talk/trade/combat behavior added incrementally.
5. Initial hostility: **direct contact/bump-to-fight**, not detection range.
6. Initial content: **Earth core districts and five functional interiors**,
   with the full city pass deferred.
7. Water feature: **a river that reaches the coast**, with named bridges.
8. Authored architecture: **reuse the landmark loader/editor and add a
   city-safe stamping mode** so exterior and interior assets are easy to swap.

Implementation-specific choices will be settled in the pre-implementation audit
and recorded before code changes begin.

### Phase 6 — Author every landable city

Every landable planet currently runs through the generic grid builder with
no transit, no interiors, and no ambient NPCs. Phase 6 gives each city the
same full treatment Earth and Mercury already have: themed layout, transit
network, authored interiors, and a living population.

**Per-city checklist** (repeat for each planet):

1. Choose a layout id and size appropriate to the planet's theme and role.
2. Write down the civil-engineering plan first: districts, terrain constraints,
   road hierarchy, sidewalks, crossings, public spaces, building blocks,
   landing operations, transit relationships, and intentional quiet areas.
3. Paint the terrain and primary circulation routes before stamping buildings.
   Roads, sidewalks, bridges, ramps, and plazas must connect the landing area,
   transit network, and every enterable building without arbitrary chokepoints.
4. Expand the `PlanetSpec`: buildings, transit stations, interior layouts,
   and NPC population — all data.
5. Author exterior landmark assets (`*_spaceport.layout`, `*_bar.layout`, etc.)
   and interior assets (`*_interior.layout`) for every enterable building.
6. Verify every building has a complete, non-noisy roof, a visible entrance,
   a valid interior spawn, and an exit returning to the same exterior door area.
7. Verify no building footprint or entrance clearance blocks a road, sidewalk,
   bridge approach, transit station, door, landing anchor, or required route.
8. Verify every transit station is next to but not on the sidewalk, does not
   block the sidewalk or door, and is on the same side of its destination
   building as that building's entrance. Verify names and ids are player-clear.
9. Verify shipyard/landing aprons keep operational floor space visually clean:
   omit repeated `.` texture beneath ships and terminals when it adds noise,
   keep the player ship obvious, and keep the spaceport entrance unblocked.
10. Verify every NPC spawn is walkable and every required destination is
    reachable. Then perform an immersion review: the layout must read as a
    believable city shaped by its terrain, infrastructure, scale, and purpose.
11. Add focused regression coverage for the city's geometry and these
    authoring invariants, run the full gate, and commit.

**Cities** (26 total, 13 done):

- [x] Earth — authored river-coast layout (Phase 1–5)
- [x] Mercury — authored desert-station layout (Phase 5)
- [x] Mars — authored high-tech colony layout (Phase 6): 160x100,
      southern logistics port, civic boulevard/avenue plan, 5 buildings,
      6 transit stops, 10 NPCs, red-dust terrain, ceramic/glass skyline,
      civic beacon plaza, and authored high-tech interiors
- [x] Epsilon Eridani b (`eri_b`) — authored 200x140 terraced canyon settlement: four bridge crossings, Beacon Spine, western landing plateau, 4 buildings, 5 transit stops, 8 colonists, smooth landing apron, cleared circulation, and authored exteriors/interiors
- [x] Wolf 359 b (`wolf_b`) — authored crater pirate outpost: 120×80, 3 buildings, landing pad, antenna forest, cave entrance, Smuggler's Row market with vendors and shoppers, 12 NPCs, 3 transit stops, contraband trade, and authored exteriors/interiors
- [x] Cygni b (`cygni_b`) — authored 160x100 port-and-forge colony: haul road, three forge factories, dock market, 4 buildings, 9 NPCs, 4 transit stops
- [x] Barnard's Star b (`barnards_b`) — authored 120×100 underground mine colony: ring-and-spoke tunnels, 3 buildings carved into rock walls, metallic blue landing pad, 6 NPCs, 3 transit stops, ore veins and barrel fires
- [ ] Barnard's Star c (`barnards_c`) — 2 buildings (spaceport, bar)
- [x] Ross b (`ross_b`) — authored 120×80 volcanic pirate settlement: two lava channels with bridge crossings, obsidian ground, 4 buildings, 11 NPCs, 4 transit stops, Smuggler's Row market, contraband trade, and authored exteriors/interiors
- [ ] Ross c (`ross_c`) — 4 buildings (spaceport, bar, merchants, depot)
- [x] Tau Ceti b (`tc_b`) — authored 160×100 canopy clearing: full-riot
      purple/magenta alien rainforest pressing in on every side, west landing
      apron + spaceport, The Waypoint bar north, merchants hall south-east,
      spine avenue + perimeter loop, canopy groves and lobes, glowing spore
      patches and walkable saplings, 9 colonists/rangers, 3 transit stops,
      Act 0 salvage_specialist quest hook preserved, authored
      exteriors/interiors
- [ ] Vega b (`vega_b`) — 3 buildings (spaceport, bar, merchants)
- [x] Lalande b (`lal_b`) — authored 140×100 wreck colony: the Requiem's diagonal hull, docking ring grave, salvage yard, 4 buildings, 7 NPCs, 4 transit stops
- [ ] Lalande c (`lal_c`) — 4 buildings (spaceport, bar, merchants, bounties)
- [x] Groombridge b (`groom_b`) — authored 120×80 hardpan boomtown: cold-dusk
      red-dwarf palette, one full-width ore-haul road ring, 4 buildings
      (spaceport + apron west, The Last Gate mid-north, bounty office south,
      depot east), tailings mounds, shanty shacks, claim stakes, 10 NPCs with
      zero militia, 4 transit stops, and authored exteriors/interiors
- [x] Indi b (`indi_b`) — authored 160×100 patchwork farmland: golden-harvest
      palette, crop plots in fallow/young/mature rotation with hedgerow
      windbreaks, grain silos, crossroads market square, harvest-road spine,
      4 buildings (spaceport + apron west, The Harvest tavern north, guild
      hall south, militia station east with north door), 10 colonists, 4
      transit stops -- first kit-native city
- [ ] Procyon planet 1 (`proc_planet_1`) — 2 buildings (spaceport, bar)
- [ ] Procyon planet 2 (`proc_planet_2`) — 2 buildings (spaceport, lab)
- [ ] AC planet 1 (`ac_planet_1`) — 2 buildings (spaceport, bar)
- [ ] AC planet 2 (`ac_planet_2`) — 2 buildings (spaceport, lab)
- [ ] AC planet 3 (`ac_planet_3`) — 2 buildings (spaceport, bar)
- [x] AC station (`ac_station`) — authored rotating-ring science station: 120x80 annulus, central void, four spokes, 5 sectors, 6 transit stops, 6 station crew, and authored exteriors/interiors
- [ ] Sirius Station (`sirius_station`) — 2 buildings (spaceport, lab)
- [ ] Venus (`venus`) — 2 buildings (spaceport, bar)
- [ ] Depot (`depot`) — 2 buildings (spaceport, depot)
- [ ] Blockade (`blockade`) — 3 buildings (spaceport, militia, bounties)

**Prioritization** (recommended order):

1. **Mars** — main-quest critical, surface dungeon tie-in, highest player traffic
2. **erib, wolf_b, cygni_b, lal_b** — main-quest delve/bounty/smuggle targets
3. **Full-service hubs** (eri_b, indi_b, ross_b, groom_b, lal_c, tc_b, vega_b)
4. **Stations** (sirius_station, ac_station) — compact, thematic
5. **Outposts** (barnards_b/c, ross_c, proc_planet_1/2, ac_planet_1/2/3, venus, depot, blockade)

**Epsilon Eridani b correction record**

- Replanned the settlement circulation so four road tiers and four canyon
  crossings remain continuous without passing through authored building
  footprints. The Beacon Spine utility avenue now has its own clear corridor.
- Normalized all four Epsilon exterior assets to rectangular, complete,
  restrained roofs with one clear entrance and readable labels.
- Moved transit stops into dedicated floor bays beside sidewalks and on the
  same entrance side as their buildings, without occupying sidewalks, doors,
  roads, or landing space.
- Replaced the repeated `.` landing-pad texture beneath ships and terminals
  with a smooth themed apron while preserving pad backgrounds and walkability.
- Added regression coverage for footprint clearance, door approaches, transit
  adjacency, roof completeness, NPC clearance, and landing-apron noise.

**Epsilon Eridani b circulation correction**

- Rebuilt the road plan around four three-cell collectors, four three-cell
  canyon crossings, and continuous bank-side collector routes instead of
  isolated one-cell strips.
- Added multi-cell sidewalk frontage and three-cell door forecourts so each
  building opens onto a legible pedestrian route.
- Moved every transit bay off roads, sidewalks, landing pads, and doors, with
  each bay on the entrance side of its destination and beside a sidewalk.
- Added a rendered-map connectivity regression covering the landing apron,
  sidewalks, plazas, roads, and bridges as one public circulation network.

**Mars redesign record**

- Replaced the hub-and-spoke outpost geometry with a rectilinear planned-city
  network: four 3-wide boulevards, three connecting avenues, sidewalks, a
  central civic square, and a southern logistics/spaceport district.
- Replaced the generic rust facade language with Mars colony architecture:
  ceramic frames, cyan glass bands, graphite circulation surfaces, and
  restrained orange signal lighting against red dust.
- Re-authored all five Mars exteriors and interiors. Interiors now use
  balanced rooms with direct entry exits, consoles, partitions, holo-displays,
  market/bar fixtures, and security/civic furnishings.
- Added Mars-specific regression coverage for public-grid structure, high-tech
  palette, road/building separation, station surfaces, and NPC separation.
- Verification: 1392 tests pass, smoke and architecture gates pass.

**Groombridge b build record**

- Linear boomtown plan: one 3-wide ore-haul road ring (two full-width
  east-west bands joined by connectors), sidewalk frontage on the mid-town
  band, and short forecourts to each door. No walls or gates — sprawl is
  the identity.
- Cold-dusk DESERT variant (`GROOM_DUSK` via `derive_theme`): dim slate
  hardpan, muted cold-red accents, pale ember neon for The Last Gate.
- Terrain furniture: tailings mounds (non-walkable relief shaping
  pedestrian routes), shanty shacks, claim stakes, sparse dry scrub — all
  hand-placed clear of roads, pads, transit bays, and door approaches.
- Population of 10 with zero patrol presence: prospectors on the haul
  road, pad crew, bounty hunters on the office steps, a pirate raider
  slouching outside The Last Gate. `bounty_master` guild override staffs
  the office; barkeep override keeps the bar voice.
- Exterior assets trimmed to documented geometry after the first stamp
  placed spaceport/depot doors one row low.
- Regression coverage: boomtown identity (tailings/shacks/stakes/no
  caves/smooth apron), reachability of every door/transit stop/NPC from
  the hangar anchor, interior spawn+exit completeness, and lawless
  population invariants.

**Tau Ceti b build record**

- Clearing-in-the-canopy plan: canopy wall rings the map on all four
  sides and juts inward as lobes that pinch the spine avenue; every
  grove rect paints only onto plain floor, so roads, apron, sidewalks,
  transit bays, footprints, and door approaches can never be buried.
- Full-riot palette (`TC_CANOPY`, derived from LUSH anchors): teal fern
  carpet, purple-violet canopy masses, hot magenta trees, cyan
  bioluminescent spore patches, walkable saplings scattered through the
  meadow as the jungle's next advance.
- Route network: spine avenue from the west apron to an east leg, bar
  spur north, southern perimeter leg serving the merchants hall door,
  spaceport forecourt connector closing the loop. No dead ends.
- Population of 9 with colonial rangers (militia) -- a lawful frontier
  in deliberate contrast to Groombridge's lawlessness.
- Act 0 hook preserved: `quest_npc_spots` keeps the merchants pairing;
  the hall interior keeps its centre column and centre-east cell
  walkable for the dynamic salvage_specialist spawn.
- Regression coverage: canopy identity (walls/saplings/spores/smooth
  apron/no caves), full reachability from the hangar anchor, interior
  spawn+exit completeness, quest-hook survival, lawful population
  invariants.

**PLAYTEST** (after each city):

1. Land and walk the primary routes from the landing area through each district.
   Confirm the road/sidewalk plan feels intentional and the terrain explains
   the city's shape.
2. Walk to every building and inspect each roof, facade, entrance, and door
   approach. Confirm no route, sidewalk, or building tile is blocked.
3. Enter and exit every interior; verify the return position is at the same
   exterior entrance area.
4. Ride transit between all stops. For each stop, approach the destination
   building from the station side and confirm the station is beside, not on,
   the sidewalk and does not block the door or route.
5. Inspect the shipyard landing apron with ships and terminals present. Confirm
   the player ship and spaceport entrance are obvious and the floor is not
   cluttered with repeated `.` glyphs.
6. Talk to ambient NPCs and observe their routes. Confirm activity feels
   inhabited without turning the city into visual noise.
7. Verify the city reads as thematically distinct, spatially plausible, and
   believable as a place built by people.
8. Run `make check`.
