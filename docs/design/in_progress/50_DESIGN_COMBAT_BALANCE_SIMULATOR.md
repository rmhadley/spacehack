# DESIGN: Headless Combat Balance Simulator

**Status: DESIGN IN PROGRESS — moved from `future/` 2026-09-24;
questions settled + Phase 1 brief proposed same day (SETTLED 1-3).**
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
    thresholds: Thresholds | None   # win_rate_floor, rounds_ceiling,
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

1. What are the target feel benchmarks, per matchup class? (win rate,
   round count, resource cost — needs the user's numbers, not guesses.
   Goal 1's "pretty easily beat" needs a number when it becomes a
   test — e.g. win rate floor + round ceiling. SETTLED 2 moves this
   INTO the scenario row: each scenario states its own goal.)
   **REMAINS OPEN, narrowed by SETTLED 3:** Goal 1's floor/ceiling
   get RULED at the Phase-1 checkpoint from the measured report —
   nothing to settle ahead of it.
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

## Phases (cut 2026-09-24 — SETTLED 1/2/3)

- [ ] 1. **The harness + Goal 1 (measure, then rule)** — the scenario
  table, the sheet/grid builders, the seeded sim runner driving the
  real space-combat loop through real action dispatch, the aggregate
  report, and Goal 1 as its first row in report-only mode; the
  checkpoint rules Goal 1's thresholds from the measured numbers and
  the assert lands with them (SETTLED 3). Brief below (PROPOSED).
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
