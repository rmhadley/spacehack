# DESIGN: Spaceport showrooms move indoors

**Status: READY — rulings settled and phases 1–3 briefed (2026-09-11); nothing implemented.**

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
- The coupling that must change: `_build_owned_ship` (game_flow.py)
  RE-USES the bumped entity — retargets its pos to
  `hangar_anchor(current_city_id)` and flips `owned=True`. Fine
  outdoors (that IS park-outside), but indoors the blocker is a
  DISPLAY on the interior map: re-anchoring pins a parent-map
  position on an interior entity. Under the ruling, an indoor buy
  appends a FRESH owned entity to the PARENT map at the anchor and
  strips the displays. `_relocate_old_ship` already targets the
  right map: `state.city_game_map` is the parent even indoors.
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

## Pre-implementation audit (2026-09-11, phase 1 session)

**Verified independently before coding:** the 11-violation audit
reproduces exactly (fresh scan over all 93 `*_interior.layout` files
against the rule as written — exactly one exit, exit row in
`{height-1, height-2}`, `P` orthogonally adjacent).

**1. Existing code to extend or reuse.**
- `city_kit.add_showroom_ships` (city_kit.py:67) — the retiring
  outdoor placer; `seat_showroom_ships` replaces it in the same
  module and reuses its Entity construction shape
  (`name=f"Ship: {name}"`, `ship_id`, catalog char/fg, 1×1).
- `city_interiors._interior_for_record` (city_interiors.py:102) —
  the every-entry hook; seating sits beside `_seat_service_npcs`
  (city_interiors.py:63), which IS the idempotent strip+re-seat
  pattern to mirror (cache hit or miss). SimpleNamespace ctx fakes
  for its tests exist in `tests/test_city_interiors.py`.
- `city_landmarks.load_city_interior` (city_landmarks.py:30) —
  already the loud-fail point (no-P / no-exit ValueErrors); the
  placement gate extends it. NOTE: the brief's parenthetical
  `_validate_city_asset` is an anchor slip — that helper validates
  EXTERIOR stamp fit and never sees interiors; Domain changes 0/1
  (binding) name `load_city_interior` as the gate's home.
- `layout_format` TILE directives + `world._TILE_BY_NAME` — a new
  `SHOWROOM_BERTH` tile in world.py is instantly authorable via
  `TILE: S = SHOWROOM_BERTH` (the QUEST_CACHE/LANDMARK_ENTRANCE
  precedent: explicit kind-marked tile, found by kind at runtime).
- `tools/layout_editor/validation.py::_validate_markers` — the
  editor mirror lives there, CITY-mode gated (city interiors infer
  CITY mode via their CITY_* tiles; dungeon landmarks don't).
- `city_builder._grid_port_entities` (city_builder.py:104) — the
  grid path's ship placement to retire (terminals stay). All 27
  registered planets use authored layouts today; the grid path is
  the "any future planet" guarantee.
- Ownership data: `ctx.player_owned_ship.ship_id`
  (ship.py `OwnedShip.ship_id`).

**2. Duplication hotspots and DRY strategy.**
- *The placement rule written three times* (load gate, editor
  validator, repo audit test see different shapes: GameMap /
  EditorDocument / files). DRY: one pure predicate
  `door_placement_error(exits, spawn, height) -> str | None` in
  `city_landmarks`; all three consumers derive their exits/spawn and
  call it. The editor already imports `src.spacehack` modules.
- *Entity-construction copy-paste* between the retired helper and
  the new one. DRY: the new helper owns one
  `_showroom_entity(ship_obj, pos)` builder; the old function is
  deleted, not left as a twin.
- *Berth discovery / reading order* re-derived by tests. DRY: tests
  count `kind == "showroom_berth"` tiles from `load_layout` output
  (the loader's row-major iteration IS reading order — no second
  ordering implementation).
- *Parallel paths* (authored vs grid builders; entry vs load
  interior paths): the audit test pins BOTH builders' outdoor maps
  and BOTH interior paths (`_interior_for_record` fresh + cached).

**3. Surprises the scan found (binding for the build).**
- The brief's authored-caller list was a sample: **25** city modules
  call `add_showroom_ships` (grep-verified), not 6 — all retire in
  the same commit so the kit function can be deleted.
- `S` is ALREADY a marker glyph (`dungeon_layout._parse_cell` set
  `{"P","C","E","T","r","R","S"}`; editor `_FIXED_MARKERS`) that
  resolves to the `.` underlay with no entity — and two lab
  interiors (ac2, sirius) carry `TILE: S = CITY_ORNAMENT`
  directives that are DEAD today. Build: `S` leaves the marker set
  in both places and becomes a pure TILE-directive glyph; the two
  dead directives activate (CITY_ORNAMENT is walkable — visual-only
  change, authored intent restored).
- Reviewer pass 1 (same day): the marker set is enumerated in a
  THIRD place — the editor palette's `_RESERVED_MARKERS`
  (tools/layout_editor/palette.py); S drops there too, pinned by a
  palette regression test. One more dead-directive activation the
  scan missed: `mercury_supply.layout` maps `S` to
  CITY_BUILDING_WALL with no `TILE: .`, so its roof bands were
  walkable DUNGEON_FLOOR underlay before and become solid wall —
  matching the file's authored intent ("Solid roof... nothing
  inside is visible from the deck"); accepted, named here and in
  the commit. The placement predicate tightened per review: P must
  be adjacent AND off the south wall row (no spawning inside the
  wall), and the editor mirror rejects multiple P markers.
- `world_layout._showroom_ships` + `make_space_port` are a SECOND
  outdoor placer (hardcoded scout/hauler/cruiser trio, stale 2×2
  cruiser footprint) with zero live callers (only world.py
  re-exports) — dead code; deleted with the retirement, re-exports
  updated.
- Per-city outdoor-showroom tests exist across
  test_ac1/ac2/ac3/blockade_north/blockade_south/city_builder —
  they flip to no-outdoor-showroom assertions in build (2).
- `enter_city_interior` catches ValueError from the interior loader
  (soft "not available" log) — the gate stays ValueError (brief
  ruling); its loudness is author-facing via the repo audit test,
  which makes violations unshippable.

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
- [x] `S` marker tile in the layout grammar + kit seating helper
      (the ONE shared path, ownership filter included per SETTLED);
      `showroom_ships` field converted
- [x] P/exit placement gate in `load_city_interior` (+ editor
      validator mirror); the 11 violating layouts fixed
- [x] All 27 interiors authored with berths; outdoor
      `add_showroom_ships` retired
- [x] Audit tests: P/exit rule over every interior, manifest↔
      markers, reachability from `P`, no outdoor showroom
      entities in any built city
- [x] Playtest checkpoint

#### Phase 1 result (2026-09-11): LANDED + PLAYTEST PASSED

All nine checkpoint items passed on the first SPACEHACK_DEV run
(berths, filter, no-buy modal check, clean pads, both save/load
resumes, Ross/Indi/Tc doors, 1-ship backwater, guide unchanged).
Commits: e459e29 (gate+grammar+doors), e00f7b2 (indoor move),
f5c4c1c (resolve_ship refactor), 1f731b7 (corpus audits).

#### Implementation brief — Phase 1 (2026-09-11) — APPROVED

**Scope.**
- `world.py` — `SHOWROOM_BERTH` tile beside `LANDMARK_ENTRANCE`
  (world.py:195): kind `showroom_berth`, char `S`, walkable, builds
  to plain floor.
- `city_landmarks.py` — P/exit placement gate in the interior
  validation path (`_validate_city_asset`): exactly one exit, on
  the SOUTH perimeter (wall row or the walkable row just inside),
  `P` orthogonally adjacent; raise ValueError in the existing
  loud-fail family.
- `tools/layout_editor/validation.py` — editor mirror of the same
  rule (layout files validate standalone).
- `data/landmarks/*.layout` — the 11 violating interiors fixed per
  the audit list; all 27 `*_spaceport_interior.layout` authored
  with `S` berths. These land directly in `data/landmarks/` — a
  gate-enforced install pass, not layout_drafts iteration.
- `data/planets/__init__.py` — `showroom_ships: tuple[str, ...]`
  (docstring at the field updated); every planet spec converted.
- `city_kit.py` — the ONE helper `seat_showroom_ships(game_map,
  spec, owned_ship_id)`: PURE (ownership passed as `str | None`,
  never ctx); strips unowned ship entities, seats the manifest on
  `S` markers in reading order (rows top-to-bottom, columns
  left-to-right), skipping `owned_ship_id`; zip-strict — manifest/
  marker count mismatch raises (repo tests make it unreachable);
  1×1 `Ship: <name>` entities, `ship_id` set, `owned=False`.
- `city_interiors.py` — `_interior_for_record` seats on EVERY entry
  (cache hit or miss — the service-NPC slot, idempotent strip +
  re-seat), passing the owned ship_id from `ctx.player_owned_ship`.
- Outdoor retirement — authored callers (`earth_city.py`,
  `ac1_city.py`, `epsilon_eridani_city.py`, `groom_city.py`,
  `barnards_c_city.py`, `ross_c_city.py`) AND the grid path
  (`city_builder._grid_port_entities`); then delete
  `city_kit.add_showroom_ships` (no callers left).

**Build order.** (1) `S` grammar + P/exit gate + editor mirror +
the 11 fixes — ONE change, the gate is loud so the fixes ride with
it. (2) manifest conversion + kit helper + interior seating +
outdoor retirement. (3) audit tests pinning the end state.

**Binding rulings.** Shared helper only — no per-city showroom
code, ever. Ownership filter inside the helper. Terminal trio stays
on the pad. Re-seat every entry. Layout fixes land in
`data/landmarks/` directly.

**Required tests.** P/exit rule over every `*_interior.layout` in
`data/landmarks/` (all 93); manifest count == `S` count per city;
every `S` walkable-adjacent and BFS-reachable from `P`; no unowned
ship entities on any built exterior city map (authored AND grid
paths); helper unit tests — reading order, owned-model skip,
idempotent re-seat, shipless seats all.

**Stop point.** No purchase-path changes (`_complete_ship_purchase`
family, `_relocate_old_ship`, `_resolve_ship_blocker` untouched —
Phase 2); no buy-modal changes (Phase 3). Until Phase 2 lands,
buying indoors still re-anchors the display entity — the playtest
must NOT buy.

**Playtest checkpoint** (SPACEHACK_DEV run):
1. New game at Earth: before first launch, enter the spaceport —
   ships stand on berths inside; floor between them walkable.
2. Your starting model does NOT stand in the room (filter live).
3. Bump a display — buy modal opens; ESC walks away. Do NOT buy.
4. Step outside: pad shows only your ship + the terminal trio — no
   for-sale ships anywhere outside.
5. Save → quit → Continue indoors: room rebuilds identically.
6. Save → quit → Continue outdoors: pad unchanged.
7. Visit a Ross/Indi/Tc city (was violating): enter/exit the
   spaceport — you appear just inside the south door, `P` beside.
8. A 1-ship backwater room: single display, berth reachable.
9. Guide: no edits this phase (guide carries no showroom
   references) — `?` Ships section confirmed unchanged.

### Phase 2 — Buy indoors, park outside
- [ ] Interior buy path places the purchased ship on the outdoor
      pad berth; trade-in verified from indoors; the room re-filters
      per the SETTLED ownership rule (re-seat on next entry; strip
      display entities immediately on purchase so no stale display
      of the newly-owned model remains)
- [ ] Regression: outdoor launch, owned-ship menu, affordability
      modal, landing places your ship on the pad (entry/load twin)
- [ ] Playtest checkpoint

#### Implementation brief — Phase 2 (2026-09-11) — APPROVED

**Scope.**
- `game_flow.py` — `_complete_ship_purchase` (game_flow.py:570)
  gains the interior branch: when the buy happens on an interior
  map, do NOT mutate the display entity; append a FRESH owned
  entity to the PARENT map (`city_game_map` — already the parent
  indoors via `state.city_game_map`) at
  `hangar_anchor(ctx.current_city_id)`, `_first_walkable`-near-
  anchor fallback if occupied; strip unowned display entities from
  the interior map (the SETTLED re-filter, applied immediately).
  The outdoor path stays byte-identical. `_relocate_old_ship`
  (game_flow.py:496) is verify-only — it already removes the old
  owned entity from the parent.
- Signature threading — `_resolve_ship_blocker`
  (game_interactions.py:301) → `_apply_ship_buy_result`
  (game_flow.py:466) → `_complete_ship_purchase`: the interior map
  must reach the purchase (pass the blocker's home map or an
  is-interior flag); update the `__main__.py` compat alias
  (`_flow_complete_ship_purchase`) in the same commit — twin rule,
  both call paths tested.
- `_build_owned_ship` (game_flow.py:536): the re-anchor mutation
  becomes outdoor-only; the interior branch builds its entity with
  the same constructor shape (audit both for drift).

**Binding rulings.** Buy is always a trade-in once you own a ship;
the purchased ship always parks at the city pad anchor; displays
re-filter immediately on purchase and on every entry; launch,
credits math, equipment transfer untouched.

**Required tests.** Indoor buy: new owned entity on the parent at
the anchor, interior displays stripped, credits/equipment transfer
unchanged. Indoor trade-in: old hull leaves the parent pad. Outdoor
buy: existing tests stay green, path unchanged. Twin coverage:
landing entry AND `restore_city_interior_parent` resume both park
exactly one owned entity. `TOO_EXPENSIVE` names the shortfall,
unchanged.

**Stop point.** No buy-modal changes (Phase 3); no seating changes
(Phase 1 landed them).

**Playtest checkpoint** (SPACEHACK_DEV run):
1. Enter a core-city spaceport; bump a display; buy WITH trade-in.
2. On purchase the bought display vanishes from the room
   immediately; your OLD model is gone from the room too.
3. Walk out: the new ship stands at the pad anchor; the old ship is
   gone from the pad.
4. Re-enter the showroom: the NEW model does not display; the OLD
   model is back (filter follows ownership).
5. Bump an unaffordable ship: shortfall named; no credits move.
6. Launch from the pad — unchanged flow.
7. Save → quit → Continue indoors: room filtered correctly, your
   ship parked outside (resume re-park twin).
8. Save → quit → Continue outdoors: pad has exactly your ship.
9. Guide: no edits expected (buy flow and controls unchanged) —
   `?` Ships section reviewed, recorded as unchanged.

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

#### Implementation brief — Phase 3 (2026-09-11) — APPROVED

**Scope.** `menus/_ship_buy.py` only.
- `_ship_buy_body` (menus/_ship_buy.py:13) grows the ledger — one
  line each, data straight off the `Ship` spec, no prose: Speed
  (moves/day), Hull, Shields (`<max> + <regen>/turn`, `—` when
  `base_shield_max == 0`), Power/turn, Weapon slots, Module slots,
  Cargo, Fuel tank; `Includes:` line(s) for `start_weapons`/
  `start_modules`. Each stat line appends `yours: N` from
  `find_ship(ctx.player_owned_ship.ship_id)`'s BASE spec when the
  player owns a ship (installed mods don't count — base vs base);
  shipless → no `yours:` text.
- `_ship_buy_frame` (menus/_ship_buy.py:30): same ScreenFrame
  shape; exactly ONE selectable row — `BUY the <name> - <price>`.
  Price/credits/shortfall keep routing through the `pygame_ui`
  helpers. All glyphs CP437-safe.
- `ShipBuyOutcome`, `_run_pygame_ship_buy` flow, GUIDE hook,
  callers: untouched. Presentation only.

**Binding rulings.** Numbers state themselves — no mechanic
explanations (UI-text-economy); comparison is always base-spec vs
base-spec; ESC never buys; the unaffordable path keeps naming the
shortfall.

**Required tests.** Every spec stat line present for a probe ship;
compare values match the owned spec's base stats; includes lines
render; `—` on a shieldless hull; outcome mapping unchanged
(BUY/TOO_EXPENSIVE/BACK/QUIT); ledger sweep over the full catalog
(every ship, with and without an owned comparison).

**Stop point.** Nothing else — no flow, no purchase math, no guide
changes unless the review demands (expected: none — the screen
teaches itself).

**Playtest checkpoint** (SPACEHACK_DEV run):
1. Bump a showroom ship: every stat readable at a glance, labeled,
   no prose.
2. Your current ship's numbers sit beside each line.
3. `Includes:` matches what the purchase actually grants.
4. Check one shielded hull AND one `—`-shield hull.
5. Price / trade-in value / credits / shortfall all correct.
6. ENTER on an unaffordable ship never buys; ESC never buys.
7. Guide: reviewed; expected no change — recorded.

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
