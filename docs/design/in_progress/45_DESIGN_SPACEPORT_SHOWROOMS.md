# DESIGN: Spaceport showrooms move indoors

**Status: DRAFT — for review. Nothing implemented until ruled.**

## The problem (user, 2026-09-11)

Spaceports put their showrooms on the landing pad, cluttering it —
ship-buying predates building interiors. Every city now has an
authored spaceport interior; the for-sale ships belong there.

**Ruled at review (user, 2026-09-11): the player's OWNED ship stays
parked on the outdoor pad.** Launch stays exactly as it is (bump
your ship outside). Buying inside spawns the new ship parked
outside; trade-in removes the old one from the pad. The pad keeps:
your ship + the terminal trio.

## Survey (verified 2026-09-11, all 27 cities)

Every planet with a spaceport building already has a
`<city>_spaceport_interior` layout with a `P` spawn and an exit:

- Sizes 13×7 (blockade_south) to 24×12 (six cities); most 20–24
  wide.
- Showroom manifests are 1–3 ships (mercury, barnards_c: 1;
  backwaters 2; core worlds 3).
- Ships are 1×1-footprint entities (`data/ships`: "collision only")
  — every interior fits its full manifest with room to walk.

## How it works today (code anchors)

- Outdoor placement: `city_kit.add_showroom_ships` berths
  `spec.showroom_ships` (ship id, dx, dy) at `spec.hangar_anchor`
  on the city map.
- Interaction is shared: `game_interactions.resolve_blocker` →
  `_resolve_ship_blocker` — bump unowned = buy with trade-in; bump
  owned = ship menu + launch. One game loop serves city AND
  interior modes, so an interior bump gets the buy modal for free.
- The coupling that must change: `_complete_ship_purchase` replaces
  the bumped entity in place, and `_relocate_old_ship` removes the
  traded-in entity from `city_game_map`. Under the ruling, a buy
  that happens INSIDE must place the new owned ship on the OUTDOOR
  pad berth — the interior blocker is a display, not the hull.
- Interiors are NOT serialized (they rebuild from layout on every
  entry, `saveload` excludes `city:` cache keys) — so anything
  mutated inside must be either re-derivable or kept off interior
  maps entirely.

## Data model

- `PlanetSpec.showroom_ships` — semantic change from
  `(ship_id, dx, dy)` triples to a bare ordered `(ship_id, ...)`
  manifest: the models this city displays, matched to berth markers
  in reading order.
- New interior layout marker tile `S` (`SHOWROOM_BERTH`) in the
  `.layout` TILE grammar — the LANDMARK_ENTRANCE precedent (explicit
  marker beats positional inference; the editor validator and
  inference mirror the rule).
- `city_kit.add_showroom_ships` retires from the outdoor builders;
  the seating logic moves to the interior build path
  (`city_interiors`/`city_landmarks`), reading the city's spec.

## Domain changes

1. **Loader.** On interior build, each `S` marker becomes a
   showroom ship entity (`Ship: <name>`, ship_id set) using the
   spec's manifest in reading order. Seated at cache build (like
   the building NPC).
2. **Purchases.** `_resolve_ship_blocker`'s buy branch: when the
   bumped ship lives on an interior map, the purchased owned ship
   spawns on a free cell at the city pad's parking berth
   (`hangar_anchor`, `_first_walkable`), NOT at the blocker.
   Trade-in keeps targeting the pad (already correct). Credits,
   equipment transfer, affordability: untouched.
3. **Launch.** Untouched — the owned ship never moves indoors.
4. **Outdoor pad.** Builders stop adding showroom entities; pad
   keeps terminals, owned-ship berth, transit bays.
5. **Survey/fix pass.** All 27 spaceport interiors get `S` berths;
   sizes, `P` and exit placements corrected where wrong. Tool-
   assisted: a showroom/reachability check (every `S` walkable-
   adjacent, reachable from `P`, exit unblocked) added to the
   audit test suite so the rule is enforced forever, plus a
   manifest↔marker count test per city.

## Known consequence to rule (open question 1)

**Sold-showroom persistence.** Interiors rebuild from layout on
every entry and are not serialized. Two coherent options:

- **(a) Persistent displays — recommended.** The showroom is a
  model catalogue, not a specific hull: buying never removes the
  indoor entity; you can buy the same model twice (both park
  outside). Zero new saved state, zero entry/load twins.
- (b) Consumed hulls, as outdoors today — the bought showroom must
  stay gone across save/load, which means a persisted sold-set on
  ctx and an entry/load twin to keep them agreeing.

## Phases

### Phase 1 — Berths, loader, clean pads
- [ ] `S` marker tile in the layout grammar + loader seating from
      the spec manifest; `showroom_ships` field converted
- [ ] All 27 interiors authored with berths; size/spawn/exit fixes
      from the survey; outdoor `add_showroom_ships` retired
- [ ] Audit tests: manifest↔markers, reachability from `P`, no
      outdoor showroom entities in any built city
- [ ] Playtest checkpoint

### Phase 2 — Buy indoors, park outside
- [ ] Interior buy path places the purchased ship on the outdoor
      pad berth; trade-in verified from indoors; persistent-
      display semantics per ruling on open question 1
- [ ] Regression: outdoor launch, owned-ship menu, affordability
      modal, landing places your ship on the pad (entry/load twin)
- [ ] Playtest checkpoint

**PLAYTEST (per phase)** — SPACEHACK_DEV run: land at a core city
(3-ship room) and a backwater (1-ship room); verify ships stand in
the showroom, walkable and bumpable; pad shows only your ship and
terminals; save → quit → Continue inside the interior and verify
the room rebuilds identically; buy with trade-in from inside; walk
out and launch; New Game at Earth shows the indoor showroom before
first launch.

## Acceptance criteria

- No showroom entities exist on any outdoor city map (audit-
  enforced).
- Every spaceport interior displays its manifest, reachable from
  the interior spawn, exit unblocked.
- Buy/trade-in from inside works; the purchased ship parks
  outside; launch is byte-for-byte today's behavior.
- Save/load shows no showroom drift (option-a ruling) or drifts
  never (option b).

## Open questions

1. Sold-showroom persistence: (a) persistent displays (rec) vs
   (b) consumed hulls + saved sold-set.
2. Terminal trio stays on the outdoor pad — confirm (assumed yes;
   not part of the clutter complaint).
3. Audit home: extend `tools/city_audit.py` (the trusted transit-
   pad diagnostic) with the showroom check, or a standalone survey
   script plus data tests. Recommendation: data tests in the repo
   suite (cheap, always run) + one city_audit rule only if it
   needs the built map.

## Philosophy alignment

| Principle | How this holds |
|-----------|----------------|
| Data-first | Ship manifests stay on the planet spec; berth furniture authored in layouts |
| No special cases | One loader rule + one purchase-placement rule for all 27 cities; no per-city flags |
| City kit | The kit's showroom duty moves indoors rather than being re-implemented per city |
| Parallel paths | The audit test pins the built city AND the rebuilt interior, both paths |
| Save/load contract | Interiors stay non-serialized; nothing mutated inside needs persisting (option a) |
