# DESIGN: City Audit Conversion — all cities audit-clean

## Overview

Roll `tools/city_audit.py` (R0/R1/R2 + verified `--fix-plan`) across the
entire city corpus. 5 cities are clean (earth, mercury, mars, venus,
cygni_b); **22 remain**, all currently failing the R0 gate (no `serves`
tags). Goal: every city exits the audit `0`, in batches of one prompt
per batch, with zero back-and-forth per city except genuine author
decisions.

Companion doc: `27_DESIGN_CITY_AUDIT_TOOL.md` (the tool's own design).
This doc tracks the **campaign**: batch plan, per-city outcomes, and
any scope changes discovered along the way.

## Philosophy alignment

| Repo principle | How this campaign applies it |
|---|---|
| Tool is the contract | Apply `--fix-plan` ops literally; never hand-tune around the tool; loop-stop rule on bad recommendations |
| Data-first | All fixes land in `data/planets/<city>.py` (serves, pos) — no runtime logic changes |
| Gates beat playtests | `make check` + audit exit 0 per city before commit; playtest spot-checks per phase |
| Atomic commits | One commit per city conversion; separate commits for tool fixes or unrelated regressions surfaced mid-batch |
| First-pass autonomy | Batches are fire-and-forget; only clean redundant-stop patterns auto-resolve (standing policy), everything else escalates |

## Standing decisions (already made — do not re-litigate)

- **Duplicate `serves` (redundant stop):** keep the stop beside the
  target, delete the other, scrub it from every `destinations` tuple.
  Approved by the user on Mars and Venus; apply without asking. Any
  duplicate that is NOT the clean redundant-stop pattern → stop and ask.
- **Architecture ratchet:** touching a city module can trip the 40-line
  function / 1000-line module limits (cygni_b did). Pay the debt in the
  same commit (extract a cohesive helper); never route around the gate.
- **`--apply` mode:** shelved. Latency is secondary to first-pass
  correctness (user, 2026-09-01).
- **Tool modifications:** forbidden mid-batch (a batch validates cities
  with the tool). Tool fixes discovered by a batch land as their own
  commits after that batch's cities are clean.

## Domain changes

None to game logic. Per city, expected touch set:

| File | Change |
|---|---|
| `data/planets/<city>.py` | add `serves=` per station; apply op moves; delete redundant stations |
| `<city>_city.py` | only if op 5 fires: swap old pad method for `city_kit.paint_transit_bays` (exact args from the op) |
| `tests/` | update pins the tool's `tests_referencing_city` lists (stop counts, station sets, grandfather entries) |
| `data/city_npcs.py` | only if a move buries a fixed spawn (playbook pattern) |

## Pre-implementation audit

**Existing machinery to reuse:**
- `city_kit`: `paint_transit_bays` (+ every city already on kit bays —
  only builders still on `paint_transit_stops`/custom pads need wiring;
  from the Mars-era survey only a minority remain).
- Fix-plan contract: verified ops with exact `file`/`stage`,
  `tests_referencing_city`, duplicate flags, reserved pads.
- Playbook follow-ups (from the Mars/Mercury/Venus/cygni conversions):
  stop-count pins, `_STOP_DISTANCE_GRANDFATHER` entries, sidewalk
  paradigm assertions, NPC-spawn burial, ratchet hits.

**Duplication hotspots:**
1. Per-city `_TRANSIT_BAY_TILE` + `_paint_transit_bays` wrappers —
   already duplicated by design (each city's palette/dimensions); do
   NOT extract a shared wrapper beyond `city_kit` unless a third
   variant appears.
2. Scripted spec edits (insert `serves`, rewrite `pos`) — reuse the
   same one-shot python edit pattern per city rather than N Edit calls;
   it is batch-mechanical, not logic.
3. Per-city test rewrites — check whether an updated pin is
   city-specific (rewrite) or cross-city (one table edit).

**DRY strategy:** ops come from the tool (single source of truth);
edits apply them literally; anything recurring across ≥3 cities becomes
a playbook/memory entry, and recurring ≥3 cities is the trigger to
propose it as a new audit rule instead of more manual follow-up.

## Batch plan (phases)

Conversion order: small/simple first, odd vocabularies last (they are
the ones that may need tool attention — better discovered with a clean
corpus behind us). One prompt per phase; one commit per city.

### Phase 1 — small kit-bay cities (2–3 stops) — COMPLETE 2026-09-01
- [x] `barnards_c` (2) — 2 moves, kit bay wiring, `_paint_deck` extraction
- [x] `depot` (3) — 2 moves, overwrite set upgraded to op args
- [x] `ross_c` (3) — 3 moves, kit bay wiring, `_paint_terrain` extraction
- [x] `tc_b` (3) — 3 moves; exposed two tool/authoring gaps (see log)
- [x] `wolf_b` (3) — intent `serves` (mis-suggestion resolved by authored
      intent, no deletion), kit bay wiring, `_paint_terrain` extraction
- [x] `sirius_station` (3→2) — duplicate policy applied (see log),
      overwrite set upgraded

PLAYTEST: per city — audit exit 0 ✓ (all six); pinned tests ✓ (barnards_c
paradigm pin rewritten, sirius station-set pin 3→2); `make check` green at
every commit ✓. In-game: user validated all six cities via the dev
city teleport (Shift+T) 2026-09-01 ✓.

### Phase 2 — AC planets (3 stops each) — COMPLETE 2026-09-01
- [x] `ac_planet_1` — dropped redundant `crossroads` (intent keeper: `bar`)
- [x] `ac_planet_2` — dropped redundant `quad` (intent keeper: `lab`), 2 moves, full bay set
- [x] `ac_planet_3` — dropped redundant `concourse` (intent keeper: `bar`), 1 move
- [x] `proc_planet_1` — serves tags, 1 move, full bay set, `_paint_terrain` extraction

PLAYTEST: per-city gate ✓ (all four audit PASS; `make check` 1620 green).
In-game: user validated via Shift+T 2026-09-01 ✓ (caught the AC no-routes
destinations bug — fixed, integrity test added).

### Phase 3 — 4-stop cities — COMPLETE 2026-09-01
- [x] `blockade` — dropped redundant `plaza` (militia keeper by intent+door), 2 moves
- [x] `blockade_south` — dropped redundant `quarantine`; passed with zero ops after tags
- [x] `groom_b` — 4 moves, real transit_bay tile (was invisible `floor`-kind)
- [x] `indi_b` — 4 moves, real transit_bay tile
- [x] `lal_b` — 4 moves, full kit bay wiring (had `paint_transit_stops`)
- [x] `lal_c` — 4 moves, full kit bay wiring, `_paint_maze` extraction
- [x] `ross_b` — door-anchored positions became literals per verified ops, widened `_BAY_KINDS`, real bay tile

PLAYTEST: per-city gate ✓ (all seven audit PASS; `make check` green).
In-game: user validated 2026-09-01 ✓ — caught groom_b's bay-on-door-front
(raised to R1 check 5, 4 cities fixed) and ross_b/Ember follow-ups.

### Phase 4 — 5-stop cities — COMPLETE 2026-09-01
- [x] `eri_b` — dropped redundant `beacon` (interchange), 4 moves, custom
      floor-kind bay wrapper replaced with the kit call (+ dead
      `_TRANSIT_SIDEWALKS` table removed)
- [x] `proc_planet_2` — dropped redundant `quad` (mess keeper by intent), 3 moves
- [x] `vega_b` — dropped far-east `reflectors`; intent serves (`exchange`→
      merchants, `focus`→depot); `focus` moved door-side via the new
      R2-rescue planner fix

PLAYTEST: per-city gate ✓ (all three audit PASS; `make check` 1625 green).
In-game: pending user Shift+T validation (eri_b is the phase pick).

### Phase 5 — special vocabulary / most complex
- [ ] `barnards_b` (mine colony; no road vocabulary — expect tool
      friction; loop-stop rule applies)
- [ ] `ac_station` (6 stops, ring layout)

PLAYTEST: same per-city gate; phase playtest on both (ring transit
around `ac_station`, tunnel transit in `barnards_b`).

### Phase 6 — closeout
- [ ] Re-run audit across all 27 cities; all exit 0
- [ ] Shrink `_STOP_DISTANCE_GRANDFATHER` where conversions made stops
      door-side (each removal is its own commit)
- [ ] Propose next audit rules from the follow-up log (see below)
- [ ] Ask user: move this doc to `complete/`?

PLAYTEST: `for`-loop audit over the corpus, exit 0 everywhere; full
`make check`.

## Follow-up / scope-change log

Anything encountered that changes scope, with date and outcome. New
rules discovered here become the input for the next tool-design phase
(doc 27 or successor).

| Date | City | Finding | Scope impact |
|---|---|---|---|
| 2026-09-01 | (tool) | 27_DESIGN_CITY_AUDIT_TOOL.md lags the implemented tool (R0 gate, R1 check 4 shared pads, R2 duplicates + BFS reachability, fix-plan, summary default) | logged; refresh of 27 deferred — opt in if wanted |
| 2026-09-01 | cygni_b | architecture ratchet: `build_cygni_layout` 44 lines → extracted `_paint_terrain` same-commit | expected pattern, budgeted per city |
| 2026-09-01 | wolf_b | R0 duplicate flag was a suggestion artifact: Spaceport stop "suggested" for `wolf_depot` though authored intent (id/name) is the spaceport | precedent: check authored intent (station id/name) before applying the delete policy — suggestion is nearest-target, not intent |
| 2026-09-01 | sirius_station | true duplicate (2 targets, 3 stops): lab door_x=71 → kept `lab` stop, deleted `terrace` (standing policy) | first batch-application of the standing delete policy; no user pause needed |
| 2026-09-01 | tc_b | TOOL GAP: recommender validated pads by walkability, but `tree` tiles are walkable-yet-unpaintable → plan could not verify (tool refused, correctly) | tool fix (separate commit): candidate validity is now a whitelist of paintable kinds (`_PAINTABLE_PAD_KINDS`) — recommendations are carvable by construction |
| 2026-09-01 | tc_b | AUTHORING BUG: `tc_city._BAY_TILE` had `kind="floor"` — bays were painted invisibly with no bay semantics; every stop "passed" visually for years | conversion checklist: verify the bay tile's `kind` is `transit_bay`, not just that `paint_transit_bays` is called |
| 2026-09-01 | depot, sirius, tc_b | existing bay calls used narrow overwrite sets (e.g. `{"floor","plaza"}`) below the op's validated args | conversion step: upgrade existing calls to the op's overwrite set + `force_center=True` |
| 2026-09-01 | barnards_c, ross_c, wolf_b | ratchet: builders 44–49 lines → terrain-painter extractions same-commit | recurring; consider a shared kit pattern if a 4th identical extraction appears |
| 2026-09-01 | ac_planet_1/2/3 | all three AC planets had the same redundant-stop shape (3 stops, 2 targets); intent resolver (station id) picked the keeper each time, no user pause | the Phase-1 "intent before policy" rule held at scale; batched cleanly |
| 2026-09-01 | ac2/ac3/proc_b | bay calls ran `{"floor","sidewalk","plaza"}` without force_center — same narrow-set upgrade as Phase 1 (now 6 cities total) | near-certain pattern for remaining cities: check call args before assuming wiring is done |
| 2026-09-01 | proc_planet_1 | verified plan emitted a same-spot "move" (station stays, pad needs carving via op args) — position unchanged, bay-call upgrade was the real fix | a from==to move op is a signal to compare the builder's call args with the op's |
| 2026-09-01 | groom_b, indi_b, ross_b | THIRD occurrence of the invisible-bay bug (`_BAY_TILE` kind="floor") — 6 cities total now (tc, lal_b, lal_c, these 3) | per-conversion checklist item: ALWAYS check the bay tile's kind, not just the painter call. Candidate R3 rule: builder bay tile must be kind transit_bay |
| 2026-09-01 | blockade | militia stop's new bay fronts the building door; `test_authored_city_doors_front_a_route` failed because transit_bay wasn't in its route vocabulary | transit_bay added to `_ROUTE_KINDS` — a carved bay is a purposeful public surface; expect this vocabulary update to be permanent |
| 2026-09-01 | ross_b | spec authored positions as door-constant expressions; verified ops gave literals — replaced expressions with literal coords (comments kept) | expression-anchored specs need literal replacement when ops move stations |
| 2026-09-01 | groom_b | USER PLAYTEST: bar stop's bay covered the door-front sidewalk cell (57,23). User directed 1-west shift to (55,24); the tool's recommender wanted (56,24) (pure door-proximity ranking, NPC-blocked west) — user judgment is the "concrete reason" carve-out. Relocated `groom_bar_regular` (54,25)→(53,24) via the tool's nearest-clear-cell semantics; audit PASS | candidate rule refinement: pad zone should not consume the sidewalk cell directly fronting a door (R1 currently allows it); recommender could tie-break away from door-front cells |
| 2026-09-01 | ross_b, blockade, lal_b | USER PLAYTEST (Ember): 3 more door-approach pads. Implemented as R1 check 5 (pads never cover entrance-adjacent cells; recommender + fix-plan treat approaches as blocked). Corpus scan: 4 cities affected, all fixed same day | the groom_b scope-log candidate became a real rule mid-campaign with user sign-off |
| 2026-09-01 | vega_b | TOOL GAP: fix-plan only moved stations with failing PADS — an R2-unreachable station (clean pad, far from target) could never be rescued → refused plan with no path forward. Phase A now moves R2-failing stations door-side (commit 9ce5c3d, regression-tested) | second mid-campaign tool fix; eri_b's spaceport apron pad grandfathered at 14 in the POI invariant (tool-verified placement) |
| 2026-09-01 | ac1/2/3, sirius | AGENT BUG (user-reported): scripted destination scrub left `destinations=("bar")` — a string, not a 1-tuple — so bumping a stop said "no transit routes" (router iterated characters). Fixed all 8 stations; added a spec-integrity test (`test_every_transit_station_destinations_is_a_tuple_of_sibling_ids`) so the class is permanently guarded | scripted scrubs of tuple literals must re-verify tuple-ness; the integrity test now fails the gate |
| | | | |

## Acceptance criteria

- All 27 cities: `python3 tools/city_audit.py --city <id>` exits 0.
- Every conversion is one atomic commit; `make check` green at each.
- No game-logic changes beyond specs/builders/tests as listed above.
- All batch playtests recorded (pass/fail + notes) in this doc.
- Scope changes are logged above, not silently absorbed.

## Open questions

- Refresh doc 27 against the implemented tool now, after the campaign,
  or fold into a future rules doc? (default: after campaign)
- When (if ever) to build `--apply`? (default: shelved until the user
  asks; campaign does not depend on it)
- Do any Phase 5 oddities justify new tile-kind entries in the tool's
  `_FORBIDDEN_PAD_KINDS` / op overwrite sets? (decide from evidence)
