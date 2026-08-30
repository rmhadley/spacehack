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
streets feel inhabited and can become traders, allies, or threats as content
expands.

> The historical implementation record, domain model, phase checklists, and
> authoring invariants below remain the contract for the completed city work.

## Current implementation status

The generic city pipeline is complete for the authored cities listed in Phase 6.
Ross 154 c (Cinder), Vega b (**The Beacon**), Procyon c (**Ice Campus**),
and Venus (**Cloudbreak City**) are complete and approved. The next backlog
cities are Procyon planets 1/2, AC planets 1/2/3, Sirius Station, Depot, and
Blockade.

Ross c now has:

- an irregular crater rim with badlands beyond it and dome anchor pylons;
- a west airlock breach with a smooth landing apron and spaceport;
- a dock street, ring road, offset impact-slag mound, and connected building
  spokes;
- three partial navy hulls, scrap piles, bazaar stalls, cargo crates, blast
  gouges, pock craters, and a frozen melt pool;
- four data-defined transit stops and ten ambient NPCs;
- four authored exterior/interior landmark pairs for the spaceport, bar,
  merchants hall, and depot;
- the existing showroom ships, trade/mechanic/armory terminals, service NPC
  overrides, interiors, save/load rebuilding, and deterministic city-NPC
  placement through the shared systems.

During final verification, the Ross c crate marker was changed from the
unmapped `▄` glyph to CP437-safe `#`, and the landing-apron regression matrix
was updated to recognize Ross c's intentionally blank `landing_pad` surface.

## Design decisions

| Topic | Decision |
|---|---|
| City pipeline | All landable cities route through `city_builder.build_city`; layout geometry is selected by data `city_layout_id`. |
| City authoring | Authored exterior/interior `.layout` assets are stamped through the shared city landmark helpers. |
| City identity | Each city gets its own terrain plan and theme while sharing transit, interiors, terminals, NPC, and persistence behavior. |
| Landing aprons | Operational pads use deliberate low-noise surfaces; smooth blank pads are valid when ships and terminals are present. |
| Glyphs | Live map content must use the supported CP437 charmap; new decoration cannot silently render as empty cells. |

## Ross c scrap-ring plan and build record

Ross c is **Cinder, the Scrap Ring**: a salvage bazaar domed over a blast crater
on a shattered moon. Crater geography is the signature; hulls and stalls are
secondary dressing.

Civil-engineering plan:

- The crater floor is the walkable bowl. An irregular rubble rim and badlands
  form the edge without a rectangular wall.
- A west rim breach provides the airlock and smooth landing apron.
- A dock street connects the apron to a ring road around an offset sealed slag
  mound; spokes connect the ring to every functional building.
- The bar, brokers hall, and depot occupy staggered forecourts, while the east
  floor becomes a breaker yard with partial navy hulls and showroom craft.
- Blast scars remain outside planned circulation routes and building footprints.
- Four transit stops and ten NPC anchors reinforce the same route hierarchy.

Implementation notes:

- `src/spacehack/ross_c_city.py` owns only Ross c's distinct crater, yard,
  bazaar, and scarring painters and delegates shared stamping/metadata,
  forecourts, ships, terminals, and labels to `city_kit` and `city_layout`.
- `src/spacehack/data/planets/ross_c.py` supplies the layout id, theme, buildings,
  transit, interiors, showroom ships, NPC overrides, and economy data.
- `src/spacehack/data/planets/themes.py` supplies the `SCRAP_RING` palette.
- `src/spacehack/data/landmarks/ross_c_*.layout` supplies swappable authored
  exteriors and interiors.

Verification record:

- Ross c builds through `load_planet` → `city_builder.build_city` with no new
  dispatch fork.
- The crate glyph is CP437-mapped and therefore covered by the live-glyph
  regression sweep.
- The smooth apron is covered by the city landing-pad readability regression.
- The full project gate passes: smoke, main-quest validation, architecture,
  Ruff, and the complete pytest suite.

## Historical design and implementation record

The sections below preserve the original approved design, phased plan,
acceptance criteria, and previous city correction records. They remain useful
for future city migrations and playtests.

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

## Phased implementation plan

### Phase 1 - Scrolling Earth foundation

- [x] Migrate Earth to a deterministic 160x100 outdoor map.
- [x] Add camera-follow rendering and map-edge handling for city mode and landing/launch animations.
- [x] Re-author Earth with a central plaza, river-to-coast water feature, preserved services, and authored landmarks.
- [x] Add city-safe landmark stamping and focused reachability/geometry tests.

### Phase 2 - Transit and building interiors

- [x] Add data-defined transit nodes, stable entrances, authored interiors, exact-door returns, caching, and save metadata.

### Phase 3 - City NPC activity and direct-contact encounters

- [x] Add data-defined populations, deterministic one-step movement, talk/trade/hostility dispatch, anchored named NPCs, and persisted positions.

### Phase 4 - Content, crispness, and workflow polish

- [x] Complete district decoration, contrast tuning, debug tooling, regression tests, and guide/README updates.

### Phase 5 - Data-driven city pipeline for every landable city

- [x] Route every city through `build_city` and data-selected layout builders.
- [x] Parameterize themes and preserve shared systems.
- [x] Expand and author Mercury as the proof city.
- [x] Add shared-pipeline tests and pass the full gate.

### Phase 6 - Author every landable city

- [x] Earth, Mercury, Mars, Epsilon Eridani b, Wolf 359 b, Cygni b,
  Barnard's Star b/c, Ross b/c, Tau Ceti b, Lalande b/c, Groombridge b,
  Indi b, and AC station are authored and migrated.
- [x] Vega b — redesigned as **The Beacon** and approved (see build record below).
- [x] Venus — redesigned as **Cloudbreak City** and approved (see build record below).
- [ ] Procyon planets 1/2, AC planets 1/2/3, Sirius Station, Depot, and Blockade remain the next migration backlog.

## Acceptance criteria

- Authored cities have coherent terrain-specific circulation, complete
  buildings and entrances, usable transit, clean landing operations, readable
  roofs, deterministic NPC activity, functional interiors, and crisp CP437
  rendering.
- `make check` passes with focused regression coverage.
- Remaining unchecked Phase 6 cities are explicit backlog rather than silently
  falling through as finished content.

## Vega b build record — The Beacon (approved)

The rejected Mirror Fields pass is preserved only as a technical reference.
This section is the new contract for the replacement.

### Concept

Vega b is a massive gas giant; the player "lands" on a floating platform in its
upper atmosphere. The station's reason to exist is power: a fan of reflector
panels concentrates Vega's light onto a collector tower, and the waste heat
bleeds off the east rim through cooling fins. Around that industrial core the
inhabited deck grew — landing deck north, Freight Exchange south, and The Veil
observation lounge west, hanging over the cloud bands. The station is the
sector's beacon: every route threads through Vega, and ships set course by its
light.

The layout must read immediately as a purposeful floating station: a cross of
four arms over the cloud deck, each arm one function, with the reflector fan
as the signature silhouette. Intentional empty space is the cloud deck itself.

### Civil-engineering plan (140x90, `vega_beacon_station`)

- **Cloud deck** — everything outside the platform is open atmosphere: two
  horizontal cloud-band tiles (the gas giant's striping) plus sparse wisp
  accents. Non-walkable; the platform silhouette is the walkable deck.
- **The Focus (hub)** — the 21x21 center square (x 60-80, y 35-55) where the
  four arms overlap, painted plaza, with the station's navigation beacon at
  its center and a neon ring.
- **North arm — Landing Deck** (x 52-88, y 8-45): the spaceport at the arm's
  tip (x 58-82, y 4-8, door south), the smooth landing apron flaring to
  x 52-88 y 9-17 (berth at 70,13; showroom ships and terminals on the pad),
  and the arm corridor down to the hub.
- **East arm — Reflector Field**: a wedge widening from the hub (x 70,
  y 35-55) to the tip (x 132, y 26-64). The collector tower (5x5,
  x 82-86 y 43-47) anchors seven mirror rays fanning to the wedge's outer
  edge (lengths 14-44 by angle); the walkable deck between the rays IS the
  reflector-field maintenance access. A service shack (non-enterable,
  x 88-91 y 34-36) sits north of the tower; cooling fins and radiator works
  bleed heat off the tip into the clouds.
- **South arm — Freight Exchange** (x 58-82, y 45-82): merchants hall
  (x 58-70, y 62-69, door south) and depot (x 70-82, y 62-69, door south)
  flanking the arm, opening onto the exchange plaza (x 58-82, y 70-76) with
  freight crates along its rim.
- **West arm — The Veil** (x 8-60, y 35-55): the bar (x 26-44, y 38-46,
  door south onto the arm) and, beyond it, the rounded observation deck
  (ellipse x 8-26, y 35-55) with safety railings and deck lights hanging
  over the clouds.
- **Transit** — five stops, all-to-all: `spaceport` (70,19), `focus` (70,52),
  `exchange` (70,73), `veil` (35,49), `reflectors` (100,47). Each stop gets a
  painted bay.
- **Population** — ten ambient NPCs re-anchored to the new districts (pad
  crew, reflector techs, freight handlers, bar regulars, security, station
  hand).
- **Services preserved** — spaceport/bar/merchants plus a new depot
  (`depot_attendant` override), showroom ships, service terminals, four
  authored interiors, and the named NPC overrides (Cloud Host, Freight
  Broker, plus a new depot persona).

### Pre-implementation audit

1. **Reuse.** `city_kit` (`set_city_metadata`, `add_showroom_ships`,
   `add_service_terminals`, `paint_door_forecourts`, `paint_transit_bays`,
   `in_bounds`), `city_layout` (`stamp_city_assets`, `paint_roof_labels`),
   the `city_builder` registry (one new dispatch row),
   the `CLOUD_CITY` theme, `city_landmarks` authored layouts,
   `data/city_npcs.py` population tuples, and the existing
   `depot_attendant` guild NPC.
2. **Duplication hotspots.** (a) The fan-ray painter would copy Ross c's
   gouge loop — parameterize one `_paint_ray` helper by angle/length/char
   instead. (b) The cloud-deck/platform painters must not re-implement
   `base_tiles` — the cloud deck replaces the walled perimeter, so the
   silhouette painters stay local. (c) Building records/entrances come
   free from `set_city_metadata` — no hand-rolled records.
3. **DRY strategy.** One `_paint_ray` for all seven rays; one
   `_paint_cloud_deck` for the atmosphere; all custom tiles as module
   constants; the platform painted as four arm shapes + hub/plaza
   overlays, with glyphs kept inside `CP437_CHARMAP`.

### Implementation checklist

- [x] New builder `vega_b_city.py` (cloud deck, platform silhouette,
      reflector fan, building placement, transit bays).
- [x] New data `data/planets/vega_b.py` (layout id, buildings incl.
      depot, transit, interiors, showroom, overrides).
- [x] Authored exteriors/interiors: spaceport, bar, merchants, depot.
- [x] New NPC population anchors in `data/city_npcs.py`.
- [x] Regression tests replacing `tests/test_vega_b_city.py`.
- [ ] Full gate (`make check`) and city playtest.

### Verification record

The Beacon replacement landed and the full gate passes: smoke,
architecture, Ruff, and the complete pytest suite (1475 tests).

Design notes from the implementation pass:

- The reflector fan's mirror rays are **walkable** — they read as
  panels laid flat on the deck, and the lanes between them stay open
  as the field's maintenance access. The collector tower and service
  shack are the only blockers. (A first pass painted the rays
  impassable, which segmented the wedge into isolated pockets and
  stranded the reflector transit stop.)
- The Freight Exchange arm is 32 wide so the merchants hall and depot
  flank a central corridor instead of walling off the exchange plaza.
- The reflector transit stop sits at the wedge's west edge beside a
  neon field marker, satisfying the "stop near something interesting"
  invariant without burying the stop in the field.
- The transit bay tile and the mirror glyphs are CP437-safe; the
  city-wide glyph sweep and the smooth-apron regression both pass.

The four building interiors were also reworked to the shared
authored-room conventions: `CITY_BUILDING_WALL`/`CITY_BUILDING_FLOOR`,
furniture tiles (`TABLE`, `BAR_BODY`, `DRINK`, `CITY_ORNAMENT`) with
colour directives, and spawn/exit adjacent at the door side. The old
merchants hall trapped the Freight Broker inside a sealed wall box;
the replacement exchange floor seats her on open floor, and the depot
gives the loadmaster a U-shaped cage open at the bottom. A regression
test now asserts spawn/exit adjacency, furniture presence, and that
every service NPC seats on a walkable, spawn-reachable cell.

The replacement received explicit user approval ("great job") after the
interior rework; the Vega b checkbox is now marked done.

## Procyon build record — The Crossroads and the Ice Campus (in progress)

Next backlog pair, approved scope: author both Procyon cities one at a time
(Procyon b first), and each may **add service buildings** beyond today's set.

### Procyon b — The Crossroads (120x80, `proc_b_crossroads`)

A scorched rocky waypoint on the inner edge of the crossroads system — the
deep-space pivot. Reads as a sun-blasted truck stop: a wide landing apron
west, one main strip, the Crossroads cantina and a new fuel depot facing a
small crossroads plaza with the nav beacon, and a dry arroyo on one edge.

- Buildings: spaceport (north of apron, door south), bar (south of strip,
  door north), **new depot** (south-east, door north).
- Transit: 3 stops (spaceport / crossroads / depot), all-to-all.
- Population: ~8 (pad crew, pilots, mechanic, one shady pirate, one
  security patrol, depot hand).
- Interiors: spaceport, bar, depot (authored conventions).
- Overrides: Waypoint Host (bar) kept, new Fuel Factor (depot).

### Procyon c — Ice Campus (140x100, `proc_c_ice_campus`)

A research outpost carved into the ice, campus-style: landing bay, lab,
**new mess hall (bar)** and **new supply depot**, with frozen channels and
crevasses as terrain. The lab chain and the ice-cave delve
(`lab_q3_reference`, `research_officer`) must survive unchanged.

- Buildings: spaceport, lab, bar, depot.
- Transit: 4 stops, all-to-all.
- Population: ~9 (researchers, drill crew, security).
- Interiors: spaceport, lab, bar, depot.
- **Signature feature (user-approved): the cave entrance.** The ice-cave
  delve's surface entrance is promoted from an implicit menu option to a
  large, authored landmark on the campus's east edge: a carved portal
  (framed mouth, scree apron, warning lamps, drill-rig approach road)
  that reads as THE way down into the ice. The EXPLORE "caves" menu
  option is the data contract and stays as-is; the entrance art gives
  the delve a visible, diegetic front door on the city map.

### Pre-implementation audit (shared)

1. **Reuse.** `city_kit` (set_city_metadata, add_showroom_ships,
   add_service_terminals, paint_door_forecourts, paint_transit_bays),
   `city_layout` (stamp_city_assets, paint_roof_labels), the
   `city_builder` registry (two new dispatch rows), `depot_attendant`
   guild NPC, and the authored-interior conventions from the Vega b fix.
2. **Duplication hotspots.** (a) Hand-placed shacks/sheds would duplicate
   Groom's — both cities get their own small shack painter or the shared
   `paint_skyline`. (b) The desert-scorch and ice-terrain painters must
   not re-implement `derive_theme` — define per-city theme variants in
   the planet data module like Groom's `GROOM_DUSK`. (c) Building
   records/entrances come free from `set_city_metadata`.
3. **DRY strategy.** One `_paint_shacks` helper per city; per-city theme
   via `derive_theme`; all custom tiles as module constants; glyphs kept
   inside `CP437_CHARMAP`.

### Implementation checklist

- [x] Procyon b: builder, data, exteriors/interiors, NPCs, tests, gate.
- [x] Procyon c: builder, data, exteriors/interiors, NPCs, tests, gate,
      delve-site preservation.

### Verification record

Procyon b — The Crossroads landed:

- Builds through `load_planet` → `city_builder.build_city` via the
  `proc_b_crossroads` dispatch row; no new dispatch fork.
- Transit was initially missing from the planet data (the builder painted
  transit bays over an empty station list, leaving `city_transit` empty);
  fixed by adding three all-to-all `TransitStation` entries (spaceport /
  crossroads / depot) to the planet data.
- The full gate passes: smoke, main-quest validation, architecture, Ruff,
  and the complete pytest suite (1481 tests).

Procyon c — Ice Campus landed:

- `proc_c_city.py` builds the 140x100 glacial campus (`proc_c_ice_campus`
  dispatch row): pale blue-white `PROC_C_GLACIAL` theme via `derive_theme`,
  frozen meltwater channel (walkable ice) with one `CITY_BRIDGE` crossing,
  snow-packed quad with the campus beacon, sastrugi ridges as non-walkable
  texture, and the signature **cave mouth** at the east edge — a dark ice
  ring (radius 7) with a walkable mouth floor, a west approach gap, and a
  `cave_marker` signpost standing in the mouth.
- `procyon_c.py` rewritten as the campus spec: 4 buildings (spaceport,
  lab, mess hall, supply depot), 5 all-to-all transit stops, 4 interior
  layout pairs,
  `PROC_C_POPULATION` (9 ambient staff incl. the cave-mouth scout),
  Campus Cook + Stores Keeper overrides. The lab-chain delve data
  (`explorable_site_name="caves"`, DungeonParams, monster pools) is
  preserved byte-identical.
- Regression coverage (`tests/test_proc_c_city.py`, 5 tests): authored
  size/stamps/channel/bridge/beacon/sastrugi, cave-mouth geometry,
  BFS reachability of every entrance/stop/NPC from the hangar, delve
  preservation, and the shared interior conventions (exit directly below
  spawn, furnished, NPC seat reachable).
- Fixups found by execution: spaceport asset door added, interior exits
  moved to the spawn-column convention, caves stop moved within the
  shared transit-reach gate (12 of the lab door).
- The full gate passes: 1486 tests (smoke, main-quest validation,
  architecture, Ruff, pytest).

Playtest corrections (same checklist item, re-verified):

- The **caves transit stop was removed** — the cave mouth is a
  five-second walk from the lab terrace, so a dedicated stop was
  useless; the spaceport/lab destination lists dropped it too.
- The four **exterior layouts' door rows were ragged** (24 of 25
  chars), so the layout parser padded the missing corner with a `void`
  tile — a black gap in the building wall. All four door rows are now
  full width. (The same ragged-door-row defect was found and fixed in
  `indi_militia.layout` and `ross_bounties.layout`.)
- A **dead-ice sealing pass** (`_seal_dead_ice`) now converts any
  walkable cell unreachable from the hangar into crevasse — the cave
  ring's east pockets, the north strip behind the spaceport's wall,
  and the south band had walkable-looking floor sealed off from every
  route. Regression tests now assert zero `void` tiles and zero
  unreachable walkable cells city-wide.
- **Interior walls were also ragged** — `proc_c_lab_interior` and
  `proc_c_spaceport_interior` had short rows the layout parser padded
  with `void`, producing black gaps in the perimeter wall. The same
  defect existed in 16 other city interiors (AC ring ×4, Cygni ×4,
  Eri ×3, Lal ×3, Mars bar, Ross c bar). All are now clean rectangles
  (every `MAP` row full width), and a new regression
  (`test_no_city_interior_has_void_perimeter_walls`) asserts no `void`
  lands on any interior perimeter ring.
- **Planned circulation (civil-engineering pass)** — the Ice Campus had
  no charted road network: open ice between buildings, the bridge
  sitting off-route at (58-62, 79-82), and sidewalk routes L-walking
  around roofs. The builder now paints one connected campus road
  network (`_paint_road_network`, lane-marker bands like Proc b / Indi
  / Groom): a landing strip (EW y32-34, apron to the cave side), an NS
  spine (x80-82, strip → quad east edge → the channel bend), the
  **primary bridge** at the channel's thin point (x79-83, y71-75,
  sealing the crossing), a mess spur + door promenade + east connector,
  a south-campus cross road (y73 x57-104) linking bridge → mess-side
  → depot, a depot NS lane docking the depot stop and door, and lab /
  cave spurs off the strip. The lab transit stop moved onto its spur
  (108,26); the depot stop now stands on its lane instead of a sealed
  crevasse. Every door and stop sits on a charted surface, and the
  dead-ice seal no longer eats the far bank. New regression
  (`test_proc_c_circulation_is_planned`) asserts the road network is
  one connected component, the bridge leaves no channel on the spine
  corridor, and every transit stop stands on road/plaza/pad/bay.

## Venus build record — Cloudbreak City (approved)

Venus is the packed neon downtown: a deck hung in the upper atmosphere,
tower blocks crammed into a neon canyon around a cross of avenues, and
every edge dissolving into sulphuric cloud bands.

Civil-engineering plan (user-approved: **neon canyon skyline** as the
signature):

- The deck is ringed by irregular cloud bands (non-walkable) — the
  city's rim silhouette, never a box wall.
- A **landing apron** north (spaceport NW, berth + showroom + terminals)
  feeds the **Promenade**, the main east-west avenue off its spur.
- The **Spine** (NS) crosses the Promenade at **The Cross** — the central
  plaza with the city beacon and the transit hub.
- The **Cross Street** (second avenue) runs south of the plaza; the
  **Cloudbreak** bar (door north) sits on its west spur, the exchange
  hall (door north) on the east spur, and the deck-stores **depot**
  (door north) on its own lane behind the exchange via a back alley.
- Every free block between the avenues is packed with **skyline towers**
  (shared `paint_skyline`, neon schemes); towers keep a lane from the
  apron and from each other, so the floor between blocks stays one
  connected service web instead of sealed pockets. A neon-signage pass
  lines each tower's street-facing facade with hot pink/cyan signs.
- Five transit stops (spaceport / the Cross / Cloudbreak / exchange /
  depot, all-to-all) and nine ambient NPCs reinforce the same routes.

Implementation notes:

- `src/spacehack/venus_city.py` owns Venus's distinct painters
  (cloud rim, apron, Cross plaza, avenue network, neon signage, dead-deck
  seal) and delegates stamping/metadata, forecourts, ships, terminals,
  and labels to `city_kit` and `city_layout`.
- `src/spacehack/data/planets/venus.py` supplies the layout id, buildings,
  transit, interiors, showroom ships, NPC overrides (Cloud Guide kept,
  new Deck Keeper), and economy (luxury goods + food, electronics /
  machine parts demand — preserved from the old outpost).
- `VENUS_NEON` is a night-neon `derive_theme` variant (deep blue-black
  deck, hot pink accent) over the `CLOUD_CITY` presets; `_readable_
  city_theme` guarantees readable backgrounds.
- `src/spacehack/data/landmarks/venus_*.layout` supplies the four
  authored exteriors and four interiors (all full-width rectangles).

Verification record:

- Venus builds through `load_planet` → `city_builder.build_city` via the
  new `venus_cloudbreak` dispatch row; no new dispatch fork beyond the
  registry row.
- The cloud-rim test asserts the west rim is an irregular silhouette, the
  north rim carries cloud, and cloud deck is never walkable.
- The planned-circulation regression (one connected road network + every
  stop on charted surface) and the no-void / no-dead-pockets regressions
  mirror the Procyon c playtest fixes.
- The city is in the smooth-apron matrix and the live-glyph sweep;
  full gate passes (1495 tests + smoke, architecture, Ruff).

## Future work

Continue Phase 6 with Procyon planets 1/2, AC planets 1/2/3, Sirius
Station, Depot, and Blockade, following the same civil-engineering-first
plan and adding focused geometry, reachability, transit, interior, NPC,
landing-apron, glyph, and persistence tests for each.
