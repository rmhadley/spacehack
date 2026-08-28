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
The latest slice is Ross 154 c (Cinder), an authored 100x70 crater-bowl salvage
bazaar selected by `ross_c_scrap_ring`. Its implementation uses the shared city
kit and landmark pipeline rather than a planet-specific loader fork.

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
- [x] Vega b — authored 140x90 Mirror Fields floating station: solar-reflector fields, shaded service spine, Cooling Works plaza, west landing apron, 3 buildings, 4 transit stops, 6 crew, and authored exteriors/interiors.
- [ ] Procyon planets 1/2, AC planets 1/2/3, Sirius Station, Venus, Depot, and Blockade remain the next migration backlog.

## Acceptance criteria

- Authored cities have coherent terrain-specific circulation, complete
  buildings and entrances, usable transit, clean landing operations, readable
  roofs, deterministic NPC activity, functional interiors, and crisp CP437
  rendering.
- `make check` passes with focused regression coverage.
- Remaining unchecked Phase 6 cities are explicit backlog rather than silently
  falling through as finished content.

## Vega b build record

- Replaced the 60x40 generic floating deck with a 140x90 authored station whose
  identity comes from long solar-reflector rows, maintenance pylons, shaded
  corridors, and a central Cooling Works plaza.
- Added a broad west landing apron, a connected service spine, four named free
  transit stops, six station crew NPCs, and three authored exterior/interior
  landmark pairs while preserving the Cloud Host and Freight Broker overrides.
- Added focused tests for mirror-field density, circulation reachability,
  transit placement, NPC safety, smooth landing operations, showroom placement,
  and interior spawn/exit completeness.
- Full project verification passes: 1,464 tests, smoke, architecture, Ruff,
  and main-quest validation.

## Future work

Continue Phase 6 with the remaining unchecked settlements, following the same
civil-engineering-first plan and adding focused geometry, reachability,
transit, interior, NPC, landing-apron, glyph, and persistence tests for each.
