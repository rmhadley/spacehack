# DESIGN: Headless Combat Balance Simulator

**Status: IN IMPLEMENTATION (phase 1, 2026-09-24) — moved from
`future/` 2026-09-24; questions settled + Phase 1 brief proposed same
day (SETTLED 1-3); brief approved via `/implement-phase 50.1`.**
The seed's blocker is lifted: doc 48's phases 7-8 landed space
combat's Tier-0 parity (hull/module stats, honest costs) and Tier-1
decision loop (the volley scorer, the aggressiveness dial, the
divert) — combat is now in the purposefully-designed state this doc
was waiting for, and doc 48 SETTLED 40 already named this tool the
successor to closed-form Line pinning (`tests/test_line_tuning.py`
carries the INTERIM note). Goal 1 is set (below); the Phase 1 brief
awaits approval, then `/implement-phase 50.1`.

## Goal 1 (user, 2026-09-24)

The first target feel benchmark is exactly what the user just tested
manually in the phase-8 playtest: **confirm that a starter ship with
2 lasers and a Shield Mk. 1 can pretty easily beat the forced
tutorial Crimson Jack fight.**

Anchors (the real fight, code-verified):
- The tutorial bounty `bhguild_sol_scout` ("Wanted: Crimson Jack",
  `data/missions/bounty.py:18`) targets spec **`pirate_scout`** —
  band 1, `ai_aggressiveness=60`, one light_laser on a scout hull.
- The starter loadout is the tutorial's own `_has_loadout` predicate
  (`tutorial.py`): 2+ energy weapons (two Light Lasers) + a shield
  module (Shield Mk. 1).
- Calibration datum from the manual test (2026-09-24, user): making
  Jack more aggressive **made the fight EASIER** — "I was worried it
  was going to make it harder." Mechanism read: the dial went LIVE in
  phase 8 (agg 60 was dead data before — the Tier-0 loop always
  fired); ~40% of Jack's decision points are now reposition steps, so
  his outgoing fire thins while the fight stays lively. A stationary
  aggressor eats return fire; a dancing one shoots less — both
  directions soften the fight for the starter. The simulator exists
  to make reads like this measured, not felt.

## The problem

Combat is mid-polish/refactor right now, with enemies, NPCs, gear, and ships
being purposefully (re)designed. Once that settles, tuning numbers by feel
and manual playtest alone won't scale — a bad matchup (an enemy type
unwinnable at a given level, a weapon that trivializes everything) is easy
to ship without noticing until a playtester hits it.

## The idea

A headless tool that runs the game's real combat resolution
(`combat/_rules_space.py`, `combat/_rules_ground.py`, `combat/_stats.py`)
against synthetic matchups in bulk — N encounters per matchup, no
rendering, no UI — and reports outcomes: win rate, average rounds to
resolve, damage taken, ammo/resource consumption. The goal isn't just to
*measure* the current feel, it's to *enforce* a target feel the user has
already decided on (e.g. "a fresh pilot vs. a Pirate Scout should win
~70% of the time in 3-5 rounds") — a regression check for balance, not
just a balance report.

Likely builds on pieces that already exist: `tests/support/fake_pygame.py`
and combat's existing test fixtures show the resolution logic is already
exercised headlessly in the test suite; `tools/save_debug.py` shows the
project's pattern for a CLI tool that drives real game logic outside the
UI (though it explicitly stops at the combat boundary today).

## Settled rulings

**SETTLED 1 (2026-09-24, user): the simulator is part of the TEST
SUITES.** Battle-sim scenarios live as tests — every new scenario gets
tested as balance is tweaked across the game's life. Goal 1 is the
first such test (the starter-vs-Jack benchmark asserted in pytest,
riding `make check` like every other gate). A `tools/balance_sim.py`
CLI may still exist as the exploration/reporting FRONT for the same
scenario data (bulk runs, richer output than an assert), but the
benchmarks' home is the suite — answers open question 3. Precedent in
the tree: `tests/test_line_tuning.py` already pins a balance contract
(closed form); this generalizes the pattern to simulated matchups.

**SETTLED 2 (2026-09-24, user) — the scenario doctrine.** User,
verbatim:

> I imagine using this for various situations that I don't want the
> balance to change on. So I'd like it to be flexible enough to set
> up new scenarios easily. What the player is fighting. What the
> player's level/stats are. What the player is flying and which
> modules it has installed. What ground equipment the player has
> equipped. What traits the player has. All the things. The idea is
> that we set up a scenario on a specified map grid, and we sim the
> fight and take an average outcome to determine if the stated goal
> of the scenario passes/fails.

Rulings read from it:

- **Scenarios are the unit of balance protection** — each one pins a
  situation the user does not want drifting ("various situations that
  I don't want the balance to change on"). Adding protection = adding
  a scenario; that must be EASY (the flexibility requirement).
- **The scenario fully specifies BOTH sides**: the opposition (spec,
  squad, band), and the complete player sheet — level and stats,
  the flown hull with its installed modules, the equipped ground
  loadout, traits. "All the things" — a scenario never depends on
  ambient state; everything is declared.
- **The scenario declares its map grid** — fights sim on a specified
  grid, so geometry-sensitive reads (chokepoints, dense watches,
  kiting room) are reproducible.
- **Verdict = average outcome vs the scenario's stated goal**: N runs
  under the real resolution (+ real AI, per the Q5 lean), aggregate
  win rate / rounds / cost, pass/fail against thresholds the
  scenario states. With SETTLED 1: that verdict is a pytest.
- **Shape lean (refine-time to settle): scenarios are DATA, not test
  code** — the repo's data-first doctrine: a scenario table (frozen
  dataclass rows, like every `data/` catalog) + ONE parameterized
  pytest that loads every row and asserts its goal. Authoring a new
  protected situation = adding a row, zero new test code. Whether the
  table lives in `data/` or `tests/` is a refine-time call.

## SETTLED 3 (2026-09-24, user) — the session rulings (open questions 1/2/5/6)

Four rulings from the refine batch (all on the proposed options), plus
two mechanical rulings proposed alongside and not vetoed:

- **Player policy = stance scripts (answers Q6).** The scenario row
  names a stance from a small declared vocabulary; the stance flies
  the player ship. Goal 1's stance is the tutorial-honest
  **stand-and-trade**: fire every affordable weapon at the target
  each turn, never move — how a new player actually flies the Jack
  fight, so "pretty easily" stays honest. New stances (kite,
  focus-hold, flee) join the vocabulary only when a scenario needs
  one; a heuristic competent-pilot module may JOIN the vocabulary
  later the same way, but nothing ships one before a scenario asks.
- **Thresholds: measure, then rule (answers Q1's ordering).** Phase 1
  ships the harness + Goal 1 scenario as a measured report (win
  rate, rounds, damage taken over N seeded runs); its checkpoint
  hands the user the real numbers, the user rules the final
  win-rate floor + rounds ceiling, and the pytest assert lands with
  the ruled numbers in the same phase. The Goal-1 numbers themselves
  remain open until that checkpoint — every later scenario states
  its own goal in its row (SETTLED 2).
- **Space first (answers Q2).** The scenario shape carries a theater
  field from day one, but the first build flies space only — Goal 1
  is a space fight. The ground harness (`_rules_ground` +
  `_ai_ground`) lands with the first ground balance question (Line
  checkpoint fights, delve guardians are the candidates).
- **The scenario table lives in `tests/` (closes SETTLED 2's
  refine-time call).** Frozen dataclass rows — data-first SHAPE,
  dev-only HOME (e.g. `tests/balance/scenarios.py`): the
  parameterized pytest sits beside it, a `tools/` CLI front reads
  the same rows when it exists (SETTLED 1's optional front), and
  nothing ships in the game package. Balance scenarios are test
  fixtures, not game content.
- **Mechanical (a) — real AI + derived-seed batches (answers Q5).**
  The sim runs the real combat AI (`combat/_ai.py`) as-is. Each
  scenario row declares a base seed; run *i* of its batch rebinds
  `engine.RNG` to a derived seed (base+*i*, the house pattern), with
  every in-run roll — weapon-quality tiers, per-turn AP — inside
  the seeded run. Every batch is reproducible from its row.
- **Mechanical (b) — the stance acts through the real action
  dispatch.** The sim loop mirrors `_run_combat_impl` minus
  presentation: same `refresh_engaged` → end-check → retarget →
  `_dispatch_combat_action(action)` → `_end_player_turn` path the
  keyboard drives. End-turn costs, retargeting, and reinforcement
  paths are exercised; the gate never breaks on keymap rebinding,
  and the stance is not coupled to SDL events.

## The scenario data model (the row — SETTLED 2 + 3 shape)

Authoring a protected situation = adding one frozen row. Composition
is pinned BY ID (spec ids, not copied stats) so catalog rebalances
flow through while the matchup stays declared:

```python
@dataclass(frozen=True)
class BalanceScenario:
    id: str                    # "goal_1_starter_vs_jack"
    theater: str               # "space" (ground rows join phase 3)
    goal: str                  # the stated feel goal, verbatim
    player: PlayerSheet        # level/stats->skills, hull id,
                               #   weapon ids, module ids, traits
    enemies: tuple[EnemySide, ...]   # spec id + start cell each
    grid: GridSpec             # size + obstacle cells (space: open
                               #   grid; coords from the live fight)
    stance: str                # STANCES vocabulary key
    runs: int                  # N per batch
    seed: int                  # base; run i rebinds RNG to base+i
    thresholds: Thresholds | None   # win_rate_floor, win_rate_ceiling,
                                    #   rounds_ceiling,
                                    #   damage_taken_ceiling;
                                    #   None = report-only
```

`PlayerSheet` carries the full sheet SETTLED 2 demands — level and
stats (the skills the flown ship fights with), the hull id, weapon
ids, module ids, traits (ground loadout fields exist on the row
shape; space runs ignore them until phase 3). The harness builds
REAL objects from the ids — `OwnedShip` through the ship module's
own install helpers, `PilotSkills` from the declared level/stats —
never hand-built structs with copied numbers.

## Open questions (settle before expanding this into a full design)

1. ~~What are the target feel benchmarks, per matchup class?~~
   ANSWERED — SETTLED 2 moved each scenario's goal INTO its row, and
   Goal 1's numbers were ruled at the phase-1 checkpoint (win-rate
   band [0.94, 0.99] over the measured 0.950; rounds/damage ceilings
   left unstated — the fight's shape didn't need them).
2. ~~Which axis is being tuned first — ship combat, ground combat, or
   both in parallel?~~ ANSWERED — space first; ground lands with the
   first ground balance question (SETTLED 3).
3. ~~One-off CLI vs `make check` regression gate?~~ ANSWERED — the
   suite is the home (SETTLED 1); a CLI front is optional.
4. ~~How is enemy/gear variation parameterized — sweep every stat block
   in `data/`, or a curated matchup list?~~ ANSWERED by SETTLED 2 —
   the curated scenario table; every side of every matchup is
   declared per row. (A full-catalog sweep may still exist as a
   REPORT, not a gate.)
5. ~~AI behavior: use the real combat AI as-is, or simplified/seeded
   AI?~~ ANSWERED — real AI, derived-seed batches (SETTLED 3a).
6. ~~Player-side AI: fixed script, heuristic, or mirrored enemy AI?~~
   ANSWERED — stance scripts from a declared vocabulary (SETTLED 3).
7. **Is shield regen too expensive?** (user, 2026-09-24, deferred by
   ruling): in the tutorial sprint any divert is a race loss (rate 0
   → 0.95, best divert rate 2 → 0.91; power spent on shields is
   power not spent on guns) — but that says nothing about mid-game
   economies. Answerable by a scenario row once bigger ships have
   rows (Cruiser + shield_mk2 class, longer fights). NOTE the
   ship-independent half already measured: the rate ladder prices
   non-monotonically (one tap = 1 power/point; two taps = 1 power
   per 2 points at engineering 20-39) — the cautious single tap is
   the worst deal at ANY power level.

## Phases (cut 2026-09-24 — SETTLED 1/2/3)

- [x] 1. **The harness + Goal 1 (measure, then rule)** — the scenario
  table, the sheet/grid builders, the seeded sim runner driving the
  real space-combat loop through real action dispatch, the aggregate
  report, and Goal 1 as its first row in report-only mode; the
  checkpoint rules Goal 1's thresholds from the measured numbers and
  the assert lands with them (SETTLED 3). Brief below (PROPOSED).
  LANDED 2026-09-24: harness + gate green under two reviewer passes;
  tuning ruling (Skiff power gen 2→3, 33104dd7) measured in at 0.960;
  thresholds ruled as a win-rate BAND — floor 0.95, ceiling 0.99,
  "never a sure thing" (user ruling) — asserted green (cb159520).
- [ ] 2. **CLI reporting front (OPTIONAL)** — `tools/balance_sim.py`
  reading the same rows for bulk runs and richer output than an
  assert (SETTLED 1's optional front). Cut only when a tuning session
  actually wants it; adding scenarios needs none of this.
- [ ] 3. **Ground theater** — the ground harness (`_rules_ground` +
  `_ai_ground` through the same runner), the first ground scenario
  (Line checkpoint fight / delve guardian candidates). Cut when the
  first ground balance question exists.
- [ ] 4. **Line closed-form migration** — author the Line watch
  scenario on the Line grid and retire `tests/test_line_tuning.py`'s
  closed form per doc 48's INTERIM note. Needs its own brief-time
  refinement: the closed form's die/clear fit margins must translate
  to averaged-outcome thresholds honestly.

Adding a protected situation after Phase 1 is a ROW, not a phase —
the point of the doctrine. Phases 2-4 exist only for remaining
machinery. Each later phase gets its brief at its own refine time.

### Phase 1 PLAYTEST (checkpoint = the Goal-1 ruling)

**Checkpoint record (2026-09-24, measured through the harness,
N=100, seed base 20260924, stand_and_trade):**

| configuration | win rate | defeats | mean turns (won) | mean hull dmg (won) |
|---|---|---|---|---|
| as shipped (gen 2) | 0.86 | 14 | 3.93 | 1.53 |
| starter hull 15→20 | 0.89 | 11 | 3.99 | 2.00 |
| starter power_gen 2→3 | 0.96 | 4 | 3.46 | 0.76 |
| hull 20 + power_gen 3 | 0.97 | 3 | 3.48 | 0.93 |
| one-laser "fumbler" proxy (as shipped) | 0.82 | 18 | 5.17 | 3.26 |
| fumbler + hull 20 | 0.92 | 8 | 5.28 | 4.75 |
| fumbler + power_gen 3 | 0.82 | 18 | 5.17 | 3.26 |

Reads: the two-laser player's binding constraint is POWER (bursts
cost 2 and the Skiff regens 2/turn — the player goes dry mid-fight
and stands idle); the fumbler's constraint is HULL (half firepower
never runs dry, but attrition in a long race kills it).

**RULING (user, 2026-09-24): land `base_power_gen` 2→3** (content
commit 33104dd7), chosen over hull for the progression it buys:
tutorial (2 light lasers) → mid (2 medium lasers) → Scout, each stage
a real step. Post-landing measurements through the live spec:
Goal 1 (light pair) **0.960** / 3.46 turns / 0.76 dmg — the probe
number, reproduced exactly; the medium pair under gen 3 **1.00** /
2.84 turns / 0.00 dmg (0.97 / 0.44 under gen 2 — the buff helps both
pairs, as both cost 2 power per burst).

**THRESHOLDS RULED (user, 2026-09-24): a win-rate BAND** —
`win_rate_floor=0.95`, `win_rate_ceiling=0.99`. The ceiling is a new
bar (user ruling: "I don't want the tutorial to ever hit 100% win
rate") — a matchup that can never be lost is as broken as one that
can't be won, and the medium-pair probe's clean 1.00 shows how close
a careless buff sits to a sure thing. Asserted green (cb159520).

**SHEET CORRECTION (user catch, 2026-09-24):** the tutorial FORCES
human merchant (`title_flow.py:74`) — the scenario had wrongly pinned
human bounty_hunter. Under the true sheet (12/10/24; the merchant's
engineering quietly buys +1 max power) Goal 1 measures **0.950 —
exactly on the floor, zero margin** (merchant + hull 20 probes at
**0.98**). The row now pins the true combo and the band passes
deterministically; margin options (hull 20 buff vs lower floor) are
with the user.

1. `python3 -m tests.balance.report` — read Goal 1's measured table
   (win rate, mean/max rounds, mean hull damage taken, timeouts) and
   the batch parameters (N, base seed).
2. Sanity-check the read against the lived fight: you just flew the
   aggression-up Jack fight manually and it felt EASIER — if the
   measured number contradicts the feel, that is a finding (stance
   wrong, geometry wrong, or the feel wrong); say which.
3. RULE the numbers: state Goal 1's win-rate floor + rounds ceiling
   (a damage-taken ceiling is optional). They land as the row's
   `thresholds` + the parameterized assert, and the phase ticks.
4. Optional cross-check: re-fight the tutorial Jack fight once —
   the sim's verdict should match your sense of "pretty easily."
5. `make check` with the assert live: green, and the batch's suite
   cost stays reasonable.
6. Save/load: nothing to check — the sim is test-only surface; no
   runtime path changed. Guide diff: NONE (no player-facing change;
   no guide edit made).

### Phase 1 Implementation brief (PROPOSED 2026-09-24 — SETTLED 1/2/3;
### ready for /implement-phase 50.1 on approval)

**Scope (files / hook points):**

- **Scenario table** (`tests/balance/scenarios.py` — NEW): the
  `BalanceScenario`/`PlayerSheet`/`EnemySide`/`GridSpec`/
  `Thresholds` frozen dataclasses per the data model above, the
  `SCENARIOS` tuple, and Goal 1's row — the tutorial's own
  composition declared by id: starter hull, `light_laser` ×2,
  Shield Mk. 1 module, the tutorial starter's level-1 skills,
  `pirate_scout` as the enemy, start geometry pinned from the LIVE
  encounter (read what the real fight's detect-trigger distance and
  positions are during the pre-implementation audit — do not guess);
  `thresholds=None` (report-only) until the checkpoint rules them.
- **Harness** (`tests/balance/harness.py` — NEW):
  - Sheet builders: row → real objects. `OwnedShip` via the ship
    module's own install helpers (never hand-built structs);
    `PilotSkills` from the declared level/stats; minimal `GameContext`
    carrying exactly the fields the space rules touch (log,
    player_counters, player_traits, player, player_owned_ship —
    pin each with real values, no MagicMock defaults);
    `world.GameMap` from the grid spec with the player entity seeded.
  - Seeded batch: for run *i*, rebind `engine.RNG` to base+*i*, call
    the real `_rules_space.init(...)` (the `_encounter.py:225`
    argument shape), then the sim loop — a faithful mirror of
    `_run_combat_impl` minus presentation: `refresh_engaged` →
    `_combat_end_check` → `_retarget_if_dead` → stance action →
    `_dispatch_combat_action` → `_end_player_turn` (which runs the
    real enemy AI + reinforcements + `reset_turn`). Meta-action
    handling is skipped — the stance emits combat actions only.
    Presentation runs inert: absorbing console double (draw-command
    absorber, the `tests/support/fake_pygame.py` pattern extended)
    + fake `PygameContext` whose pump returns empty batches +
    INSTANT animation timing — no monkeypatched AI or rules
    internals.
  - Turn cap (e.g. 200 turns) → counted TIMEOUT outcome: a stuck
    fight is itself a balance finding, never a hung test.
  - Stance vocabulary: `STANCES` table, stance name → async
    generator yielding action strings given (ctx, rules, target).
    Phase 1 ships `STAND_AND_TRADE`: while AP remains and some
    weapon `can_fire`, FIRE at the current target; never move; then
    end turn.
  - Aggregate: per-run (outcome, turns, hull damage taken) →
    win rate, mean/max turns, mean damage, timeout count (pure
    function, tested).
- **Parameterized gate** (`tests/balance/test_balance.py` — NEW):
  one test loading every row; rows with `thresholds` assert them;
  Goal 1 starts threshold-less (runs + determinism pins only).
- **Report entry** (`tests/balance/report.py` — NEW):
  `python3 -m tests.balance.report` from the repo root prints every
  scenario's aggregate table + pass/fail vs thresholds; the
  checkpoint's ruling input.

**Build order:** scenario dataclasses + Goal 1 row (audit-pinned
geometry) → sheet/grid builders → seeded runner + absorbing doubles →
stance table + STAND_AND_TRADE → aggregate + report entry →
parameterized test (determinism pins; no assert for Goal 1 yet) →
full gate → PLAYTEST checkpoint (the ruling) → land the ruled
`thresholds` + assert as the phase's closing commit.

**Binding rulings:** SETTLED 1 (suite is the home — the assert is
the deliverable, the report is the front), SETTLED 2 (full both-side
sheets, declared grid, averaged verdict, rows-not-code), SETTLED 3
all six clauses. Specs load by id through the real catalogs — a
catalog rebalance flows into scenarios automatically; the row pins
COMPOSITION. Real AI, real dispatch, derived seeds, no runtime
changes of any kind (no `src/spacehack/` edits expected — if the
build reaches for one, stop: that is a design question, not a fix).

**Required tests:** determinism (same row twice → identical
aggregates, end to end through the seeded runner); seed derivation
(base, *i*) → distinct seeds (pure); the stance (unit-level: yields
FIRE for each affordable slot then turn-end, never a move, reads
`can_fire`/AP through the real rules on a built state); Goal 1 runs
to completion across N runs with every run resolving VICTORY /
DEFEAT / TIMEOUT (no hangs); aggregate math correctness (pure);
post-checkpoint — every thresholds-bearing row passes its own goal
in `make check`. Existing combat suites stay green.

**Stop point:** no CLI front (2), no ground rows or ground harness
(3), no Line migration (4), no new stances beyond STAND_AND_TRADE,
no balance CHANGES to any spec — phase 1 measures and pins; if the
measurement says the fight misses the goal, the fix is a separate
tuning decision with its own commits. No guide edits (nothing
player-facing changed).

**Playtest checkpoint:** the Phase 1 PLAYTEST list above — its
center is item 3, the threshold ruling; the phase ticks only with
the ruled numbers asserted green.

## Pre-implementation audit (Phase 1 — 2026-09-24, code-verified)

### 1. Existing modules / patterns to reuse

- **Loop mirror shares the real bodies.** The sim loop imports and
  calls `_loop`'s own helpers — `_log_combat_start`,
  `_combat_end_check`, `_retarget_if_dead`, `_dispatch_combat_action`,
  `_end_player_turn`, `_finish_combat` (`combat/_loop.py`) — replacing
  only render/present (dropped) and input (the stance). End-turn
  costs, retargeting, and reinforcements ride the real dispatch.
- **Real entry, NOT the encounter wrapper.** `init(ctx, console,
  ship_cat, owned, pos, skills, specs, positions, game_map, log)` at
  the `_encounter.py:225` shape. `_handle_combat_encounter` is
  avoided on purpose: it opens the tutorial-intro modal and the death
  screen (input-waiting presentation the sim must never open).
- **Sheet builders are the game's own.** `ship.
  install_stored_equipment` + `base_module_entries` build the
  OwnedShip through the real install path (slot caps enforced);
  `character.starting_pilot_skills(species, class)` folds the real
  base+bonuses.
- **Real FrameBuffer as the console** → AMENDED at build: the real
  FrameBuffer feeds a ~50ms/frame overlay build the sim doesn't need
  (measured); the shipped double is an ABSORBING console (the
  ``fake_pygame`` pattern extended — paints swallowed, frames report
  empty, frame counts and pacing awaits still real). Outcome-neutral
  by construction: combat logic never reads the console.
- **Fake PygameContext per the `tests/support/fake_pygame.py`
  pattern** — SimpleNamespace with `pump`/`wait_events` returning
  empty batches, absorbing `present`, a `note_drained` hook, and
  `_runtime.engine` set so `pygame_runtime.is_shared_context` passes
  (it is a duck-typed check, not an identity check).
- **Aggregate/report precedent:** `tests/test_line_tuning.py` (the
  closed-form interim this doc's phase 4 later retires).

### 2. Live-fight geometry pins (Goal 1) — read from code, not guessed

- **Jack's spawn**: `_pick_bounty_spawn_pos(sol)`
  (navigation_spawns.py:44) → first free landmark nearest the system
  centre = Mercury's `(pos.x+width+3, pos.y+height//2)` = **(80, 52)**
  (sol.py: mercury at (75,51), 2×2; game_interactions.py:842).
- **Trigger distance**: `_trigger_bounty_spawns` fires at
  `0 < dist <= detect_radius` and `pirate_scout.detect_radius=8`
  (npc_ships/core.py:99). The player flies Earth→Mercury due west, so
  the canonical first-trigger cell is 8.0 east of Jack: **player
  (88, 52)** — open space, LOS clear.
- **Grid = the live fight's map**: Sol 200×140, pinned BY ID —
  `system_id="sol"` (dims asserted against the catalog, body
  footprints derived from it at build time, reviewer-round amendment:
  a copied rect list would drift on a body move). The end-turn
  reinforcement path behaves exactly as live:
  `check_reinforcements` → `move_npcs` spawns ambient traffic at real
  Sol body goals (in-bounds, seeded) and `_detect_combat_encounter`
  re-detects honestly — joins can happen in the sim like they can in
  the fight.
- **Starter sheet** (all by id): hull `starter` (Skiff — base_hull
  15, 2 weapon slots, 1 module slot, base_power_gen 2→3 per the
  ruling below, base_shield_max 0, base_shield_recharge 0);
  `light_laser` ×2 (dmg 4, acc 80, band 1–5, 1 AP, 1 power); module
  `shield_mk1` (+20 max shields → max 20, free regen stays 0);
  **CORRECTED 2026-09-24: the tutorial's own forced combo
  (`title_flow.py:74` runs new games as human merchant — creation is
  skipped), gunnery 12 / piloting 10 / engineering 24 via
  `starting_pilot_skills`.** The first cut wrongly pinned human
  bounty_hunter (16/14/16 — a better pilot than the tutorial flies);
  user catch. Traits `[]` (a tutorial pilot has none).
- **Enemy** (`pirate_scout`, read live via `find_npc_ship`): band 1,
  `ai_aggressiveness` 60, `ai_preferred_range` 3, one `light_laser`,
  `compact_reactor`, `ai_accuracy_bonus` 5, `ai_dodge_bonus` 10;
  flown-equipment quality rolls (`roll_flown_equipment`) happen inside
  the seeded run.
- Map entities at init: player `Entity(owned=True)` at (88,52) and
  Jack's `npc_ship_id="pirate_scout"` entity named "Crimson Jack" at
  (80,52) — the `_match_enemy_entities` position match + name stamp
  need both.

### 3. Presentation-inert surface (what the doubles satisfy)

- `pygame_combat.present(ctx, console)` → `is_shared_context` passes
  on the fake's `_runtime.engine`; `_console_commands` reads the real
  FrameBuffer; overlay building is pure computation; the final
  `ctx.context.present(...)` is absorbed — nothing blits to a window.
- `_responsive_sleep` polls real `pygame.event.get()` unconditionally
  (only ModuleNotFoundError is caught; container-verified: it raises
  `pygame.error` until init). Harness: `pygame.init()` once headless
  (the `test_pygame_integration` pattern — initializing the real
  library is not monkeypatching) + INSTANT timing
  (`animation_timing.set_speed_scale(0.0)` — zero-length sleeps that
  still yield).
- `_message_segments` reads only `ctx.log` (real `MessageLog`).
- `_rules_space._state` is a module global: `init` re-creates it per
  run (clearing previous locks), and the runner nulls it + releases
  combat locks in a `finally` so runs cannot bleed.

### 4. RNG rebind hazard (the determinism contract)

`engine.seed_rng` REBINDS `engine.RNG`, but `_loop`, `_ai`, and
`_actions` hold import-time `from ..engine import RNG` references —
the hit/loot roll sites. Production is unaffected (saveload restores
in place via `setstate`; the stale instance is entropy-seeded and
never replayed). A sim that rebinds only `engine.RNG` would SPLIT its
rolls across two instances and lose per-run reproducibility. Harness
contract: per run *i*, one `random.Random(base+i)` instance assigned
to `engine.RNG` AND the touched modules' `RNG` attributes (loop, ai,
actions) — same instance, refreshed each run, test-side only.

### 5. Duplication hotspots + DRY strategy

1. **Sim loop vs `_run_combat_impl`** (highest drift risk): share the
   real helper bodies per §1; the mirror keeps only sequencing and
   cross-references `_run_combat_impl` step by step.
2. **Sim ctx vs `tests/support/quest_ctx.py`**: one pinned-field
   factory in the harness (SimpleNamespace, real `PlayerCounters`,
   real `MessageLog`, no MagicMock), fields enumerated from §2–§3
   reads — not a second ad-hoc namespace grown one failure at a time.
3. **Scenario rows vs `data/` catalogs**: frozen dataclasses in the
   house catalog idiom (`SCENARIOS` tuple + `find_scenario`), living
   in `tests/` per SETTLED 3; composition pinned by id everywhere.
   Seed derivation (`base+i`) is ONE helper shared by harness and
   tests — never two implementations.
