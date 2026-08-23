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

- [ ] Add data-defined Earth transit nodes and a free station-to-station route.
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
- Transit remains outstanding and is the next Phase 2 slice.

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

- [ ] Add data-defined ambient city NPC templates and Earth populations.
- [ ] Implement deterministic route/destination movement, collision avoidance,
      and one-step-per-city-tick updates.
- [ ] Add NPC talk/trade dispatch using existing catalogs and modals.
- [ ] Add faction-aware direct-contact hostile encounters using existing ground
      combat and faction attitude rules.
- [ ] Ensure named service NPCs stay anchored unless explicitly configured to
      move, and prevent combat movement code from running twice.
- [ ] Persist city NPC positions/routes and add deterministic save/load tests.

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

- [ ] Complete the Earth core district decoration pass and public landmark.
- [ ] Tune glyph contrast/backgrounds for all districts and interiors.
- [ ] Add compact city playtest/debug tooling for inspecting camera, transit,
      building ids, NPC routes, and map coordinates.
- [ ] Add regression tests for resize/asset loading failures and unreachable
      city destinations.
- [ ] Update the in-game guide, README, and design playtest record.
- [ ] Run the full project gate and review the final user-facing flow.

**PLAYTEST**

1. Visit every district using walking and transit.
2. Check that all decorative glyphs remain crisp at the configured window size.
3. Verify no building, transit stop, NPC, or landmark is unreachable.
4. Exercise all five core services after a save/continue cycle.
5. Run `make check` and the city-specific test suite.

## Acceptance criteria

- Earth is a 160x100 city that scrolls smoothly in the existing cell renderer.
- The current Earth services and named NPC functionality remain available.
- Districts and decoration make outdoor navigation readable and planet-themed.
- Transit is physical, named, free, and usable to move between core districts.
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
