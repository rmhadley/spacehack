# DESIGN: Spaceport showrooms move indoors

**Status: REFINEMENT — all rulings settled 2026-09-11; briefs in progress.**

## The problem (user, 2026-09-11)

Spaceports put their showrooms on the landing pad, cluttering it —
ship-buying predates building interiors. Every city now has an
authored spaceport interior; the for-sale ships belong there.

**Ruled at review (user, 2026-09-11): the player's OWNED ship stays
parked on the outdoor pad.** Launch stays exactly as it is (bump
your ship outside). Buying inside spawns the new ship parked
outside; trade-in removes the old one from the pad. The pad keeps:
your ship + the terminal trio.

**Added at review (user, 2026-09-11): the ship buy screen itself.**
"Frankly it: 1. looks bad, 2. has no details, 3. is hard to
understand — we have a lot of screen real estate here and we're
using none of it. Just confusing the player and they have to guess
what a ship's stats are." Today the modal shows the description
sentence and one BUY row; the Ship spec carries speed, hull,
shields, power, weapon/module slots, cargo, fuel, and a starting
loadout — none of it displayed
(`menus/_ship_buy.py`; `data/ships`).

## Survey (verified 2026-09-11, all 27 cities)

Every planet with a spaceport building already has a
`<city>_spaceport_interior` layout with a `P` spawn and an exit:

- Sizes 13×7 (blockade_south) to 24×12 (six cities); most 20–24
  wide.
- Showroom manifests are 1–3 ships (mercury, barnards_c: 1;
  backwaters 2; core worlds 3).
- Ships are 1×1-footprint entities (`data/ships`: "collision only")
  — every interior fits its full manifest with room to walk.

## The P/exit placement audit (user requirement)

Having a `P` and an exit is not enough — they must sit where a
building's door logically is. **The placement rule** (the shared
gate every interior must pass):

1. Exactly one exit tile.
2. The exit sits on the SOUTH perimeter — the wall row itself
   (in-wall doorway, the blockade_south pattern) or the walkable
   row just inside it (the standard pattern).
3. `P` is orthogonally adjacent to the exit — you appear just
   inside the door you came through.

**Audit result: 11 of 93 interiors violate** (scan script, same
day) — clustered in the Ross/Indi/Tc authoring family:

- Mid-room exits (7): `ross_spaceport`, `ross_bar`, `ross_depot`,
  `ross_bounties`, `indi_spaceport`, `indi_militia`,
  `tc_spaceport` — the exit floats in the middle of the floor.
- Wrong-side exits (2): `ross_c_depot`, `ross_c_merchants` —
  exit on the TOP wall.
- Spawn detached (2): `indi_merchants`, `tc_merchants` — `P` five
  tiles from its exit along the bottom row.

Three of the 27 spaceports are in the violating set. All 11 get
fixed (exit to the south door position, `P` just inside), and the
rule becomes a shared load-time gate so it cannot regress.

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

## SETTLED (2026-09-11, refinement session)

- **Sold-showroom persistence — ownership-filtered displays.**
  "the player can only have one ship owned. so if the player owns a
  frigate, then frigates shouldn't show in any show rooms" (user,
  verbatim). The showroom is a model catalogue read against current
  ownership: the kit seating helper skips the manifest entry whose
  ship_id equals the player's owned ship_id, at interior build, on
  every entry (re-seated idempotently, the service-NPC pattern —
  ownership can change between entries). The filtered berth seats
  nothing — plain floor. Buying is always a trade-in (one-ship
  invariant); trading away restores the display in every city.
  Nothing about showrooms serializes — no sold-set, no entry/load
  twins. Known consequence, accepted: a 1-ship city (mercury,
  barnards_c) shows an empty room while you own its only model.
- **Terminal trio stays on the outdoor pad** (user confirmed). The
  pad keeps: your ship + the three service terminals — the clutter
  complaint was the showrooms.
- **Audit home confirmed** as written in Domain changes: the
  placement rule is a load-time gate in `load_city_interior` plus
  repo data tests for berths/reachability/outdoor absence;
  `tools/city_audit.py` is not extended.

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

0. **One shared helper — binding (user requirement).** Every city
   gets showroom placement from the SAME code path; no city module
   may place ships itself, ever. Concretely: `city_kit` owns the
   seating helper (kit function reading the spec manifest onto
   `S` markers), the interior loader invokes it, and the P/exit
   placement rule is enforced once on the shared path
   (`city_landmarks.load_city_interior` raises on violation — the
   same loud-fail family as its missing-spawn/missing-exit checks,
   with the layout editor validator mirroring the rule). Cities
   contribute DATA only: the layout file and the ship manifest.
1. **Placement gate.** The P/exit rule above lands in
   `load_city_interior` in the same change as the 11 layout fixes
   (the gate is loud, so the fixes must ride with it).
2. **Loader.** On interior build, each `S` marker becomes a
   showroom ship entity (`Ship: <name>`, ship_id set) using the
   spec's manifest in reading order. Seated at cache build (like
   the building NPC) by the kit helper.
3. **Purchases.** `_resolve_ship_blocker`'s buy branch: when the
   bumped ship lives on an interior map, the purchased owned ship
   spawns on a free cell at the city pad's parking berth
   (`hangar_anchor`, `_first_walkable`), NOT at the blocker.
   Trade-in keeps targeting the pad (already correct). Credits,
   equipment transfer, affordability: untouched.
4. **Launch.** Untouched — the owned ship never moves indoors.
5. **Outdoor pad.** Builders stop adding showroom entities; pad
   keeps terminals, owned-ship berth, transit bays.
6. **Audit tests.** Repo data tests (always run): the P/exit rule
   over every `*_interior.layout`; every city's manifest count
   equals its `S` marker count; every `S` walkable-adjacent and
   reachable from `P`; no outdoor showroom entities in any built
   city map.

## Phases

### Phase 1 — Berths, loader, clean pads, correct doors
- [ ] `S` marker tile in the layout grammar + kit seating helper
      (the ONE shared path, ownership filter included per SETTLED);
      `showroom_ships` field converted
- [ ] P/exit placement gate in `load_city_interior` (+ editor
      validator mirror); the 11 violating layouts fixed
- [ ] All 27 interiors authored with berths; outdoor
      `add_showroom_ships` retired
- [ ] Audit tests: P/exit rule over every interior, manifest↔
      markers, reachability from `P`, no outdoor showroom
      entities in any built city
- [ ] Playtest checkpoint

### Phase 2 — Buy indoors, park outside
- [ ] Interior buy path places the purchased ship on the outdoor
      pad berth; trade-in verified from indoors; the room re-filters
      per the SETTLED ownership rule (re-seat on next entry; strip
      display entities immediately on purchase so no stale display
      of the newly-owned model remains)
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

### Phase 3 — The ship buy screen: a spec sheet, not a riddle

- [ ] Stats ledger in the modal body — for the OFFERED ship, one
      line each: Speed (moves/day), Hull, Shields (max + regen, `—`
      when none), Power/turn, Weapon slots, Module slots, Cargo,
      Fuel tank; `Includes:` lines for `start_weapons`/
      `start_modules` — data straight off the Ship spec, no prose
- [ ] Comparison column — since the player always owns a ship,
      each stat line carries "yours: N" from the current
      `player_owned_ship`'s base spec, so the trade-in decision is
      visible at a glance; single column when shipless
- [ ] Price block stays the single source of money truth: price,
      trade-in value, credits, shortfall (existing `pygame_ui`
      helpers); one selectable row: `BUY the <name> - <effective>`
- [ ] No flow changes — `ShipBuyOutcome` contract, affordability
      path, GUIDE hook, and callers untouched (presentation only)
- [ ] Tests pin the ledger: every spec stat line present, compare
      lines match the owned spec, included-loadout lines, outcome
      mapping unchanged
- [ ] Playtest checkpoint

**PLAYTEST (phase 3)** — bump a showroom ship: every stat readable
at a glance, your current ship's numbers beside them, includes
lines accurate, price/trade-in/credits correct; check one shielded
hull and one `—`-shield hull; ESC never buys; the unaffordable path
still names the shortfall.

Design notes: the body ledger uses the idle ScreenFrame real estate
(the screen is 100×60; the modal currently draws ~4 lines). Numbers
state themselves — no explanations, per the UI-text-economy rule.
All glyphs CP437-safe; comparison lines are plain `yours: N` text in
the detail column.

## Acceptance criteria

- Every `*_interior.layout` passes the P/exit placement rule
  (gate-enforced at load, audit-enforced in the suite); the 11
  named violations are fixed.
- No showroom entities exist on any outdoor city map (audit-
  enforced).
- Every spaceport interior displays its manifest on `S` berths,
  reachable from the interior spawn, exit unblocked.
- Buy/trade-in from inside works; the purchased ship parks
  outside; launch is byte-for-byte today's behavior.
- Save/load shows no showroom drift: interiors rebuild from layout
  with ownership-filtered seating — nothing about showrooms
  serializes.
- The owned model never stands in any showroom while owned
  (audit-enforced over the seating helper and built interiors).
- The buy modal shows every Ship spec stat plus the player's
  current-ship comparison; no flow or outcome changes.

## Open questions

None — all settled 2026-09-11 (see SETTLED).

## Philosophy alignment

| Principle | How this holds |
|-----------|----------------|
| Data-first | Ship manifests stay on the planet spec; berth furniture authored in layouts |
| No special cases | One loader rule + one purchase-placement rule for all 27 cities; no per-city flags |
| City kit | The kit's showroom duty moves indoors rather than being re-implemented per city |
| Parallel paths | The audit test pins the built city AND the rebuilt interior, both paths |
| Save/load contract | Interiors stay non-serialized; seating re-derives from ownership at build, so nothing serializes |
