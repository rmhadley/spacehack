# DESIGN: Headless Combat Balance Simulator

**Status: DESIGN IN PROGRESS — moved from `future/` 2026-09-24.** The
seed's blocker is lifted: doc 48's phases 7-8 landed space combat's
Tier-0 parity (hull/module stats, honest costs) and Tier-1 decision
loop (the volley scorer, the aggressiveness dial, the divert) — combat
is now in the purposefully-designed state this doc was waiting for,
and doc 48 SETTLED 40 already named this tool the successor to
closed-form Line pinning (`tests/test_line_tuning.py` carries the
INTERIM note). Goal 1 is set (below); the open questions still need
settling before build phases are cut.

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

## Open questions (settle before expanding this into a full design)

1. What are the target feel benchmarks, per matchup class? (win rate,
   round count, resource cost — needs the user's numbers, not guesses.
   Goal 1's "pretty easily beat" needs a number when it becomes a
   test — e.g. win rate floor + round ceiling. SETTLED 2 moves this
   INTO the scenario row: each scenario states its own goal.)
2. Which axis is being tuned first — ship combat, ground combat, or both
   in parallel? (SETTLED 2's ground-equipment clause implies BOTH
   theaters are in scope from the start — a scenario names its
   theater; confirm at refine.)
3. ~~One-off CLI vs `make check` regression gate?~~ ANSWERED — the
   suite is the home (SETTLED 1); a CLI front is optional.
4. ~~How is enemy/gear variation parameterized — sweep every stat block
   in `data/`, or a curated matchup list?~~ ANSWERED by SETTLED 2 —
   the curated scenario table; every side of every matchup is
   declared per row. (A full-catalog sweep may still exist as a
   REPORT, not a gate.)
5. AI behavior: use the real combat AI (`combat/_ai.py`,
   `_ai_ground.py`) as-is, or does simulation need simplified/seeded
   AI to get statistically clean, reproducible results across N runs?
   (The suite-home ruling leans real-AI: a benchmark pinned against
   simplified AI would lie the moment the loop changes. SETTLED 2's
   "average outcome" implies seeded-RNG batches for reproducibility —
   how to seed N runs cleanly is refine-time.)
6. Player-side AI: the scenario declares the player SHEET but not (yet)
   the player's TACTICS — does the sim fly the player with a fixed
   script (e.g. "fire both lasers every turn, S-dial at 2"), a
   heuristic, or the enemy AI mirrored? The goal thresholds are only
   honest relative to a declared player policy. (Refine-time; the
   user's word "average outcome" presumes something flies the ship.)
