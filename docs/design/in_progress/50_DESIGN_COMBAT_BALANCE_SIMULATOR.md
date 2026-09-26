# DESIGN: Headless Combat Balance Simulator

**Status: PHASES 1-2 CLOSED (2026-09-25) — the standard is live:
five pinned rows (space win band + the four-ground-row cost board,
SETTLED 6) assert green in `make check`; goal_2's measured 1.00 win
rate is parked as the standard's first tuning target. Remaining
phases are cut-when-needed (3 = optional CLI front, 4 = Line
migration); adding a protected matchup is a ROW, not a phase.**
Moved from `future/` 2026-09-24; settled + built in three sessions
(SETTLED 1-3 space harness + Goal 1; SETTLED 4-5 ground theater + the
R-key fix; SETTLED 6 the standard).

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
  checkpoint fights, delve guardians are the candidates — both
  superseded by SETTLED 4: the Line fight is space-side, and the
  first ground scenario is the tutorial Mars fight).
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

## SETTLED 4 (2026-09-24, user) — the ground theater rulings (phase 2)

- **The first ground scenario is the tutorial Mars fight** — the
  ground twin of Goal 1: the same forced tutorial sheet (human
  merchant), the loadout the tutorial itself teaches (two Kinetic
  Pistols + a stack of Pistol Rounds — `tutorial.py`
  "earth_armory"; doc 52.6 note 2026-09-25: the stack-buy phrasing
  is gone — the beat now says "restock your Pistol Rounds" — but
  the taught LOADOUT is unchanged: two pistols + pistol rounds in
  reserve), against the Mars signal delve's first-sight group
  (`monster_pool` rock_scavenger / dust_prowler / sentry_drone,
  band 1; `data/planets/mars.py`). Doc 48's ground rework (phases
  4-7 re-derived every ground enemy's stats, bands, and gear) is the
  live trigger: the tutorial's ground fight has zero measured
  protection. CORRECTION to the phase-2 cut note: the "Line
  checkpoint fight" candidate is a SPACE fight (picket squads at
  the blockade) — protecting it later is a space ROW under the
  phase-1 harness, not ground machinery.
- **Ground grids are planet-pinned generated delves.** `GridSpec`
  gains a planet mode — the idiom of `system_id`: the harness runs
  the REAL delve generator on the planet's own `DungeonParams`
  (dims asserted against the catalog) with the row's declared grid
  seed, keeps the tiles, discards the generated entity scatter, and
  seeds the declared combatants. Real rooms/walls, reproducible, a
  planet param change flows in. Synthetic blocks stay available for
  hand-built geometry. (Pipeline named precisely by SETTLED 5 after
  the review pass: the live Mars map is generate →
  `prepare_mars_surface` tile mutations → `populate_dungeon`
  scatter — the skipped step.)
- **The ground stance is a NEW vocabulary key: `hold_range`.** User,
  verbatim: "we need a new mode for ground. in ground fighting
  there's a clear ideal distance for most weapons. so the move
  should be move so that the closest target to you is within ideal
  range for your weapon." "Within ideal range" = inside the
  weapon's `[min_range, max_range]` band with LOS — the mirror of
  the enemy AI's own range rule (doc 48 SETTLED 26) from the player
  seat; inside the band ground accuracy is FLAT
  (`ground_point_blank_penalty` bites only inside min_range), so a
  scalar ideal distance would have no mechanical effect today.
  Policy order: FIRE while any active slot can fire (through the
  real `can_fire`) → RELOAD a dry slot when a reserve remains (the
  tutorial teaches the R key — a tutorial-honest pilot doesn't
  stand idle on a dry magazine) → MOVE one step per the band rule
  (approach when the closest target is beyond the reference
  weapon's max_range or has no LOS; back off when inside min_range)
  → WAIT. Reference weapon = the first active slot; reference
  TARGET = the closest alive enemy (SETTLED 5 — the stance cycles
  TARGET through the real dispatch to select it, and FIRE and the
  MOVE rule reference the same enemy).
  `stand_and_trade` stays the space policy, unchanged.
- **Row-shape amendments (approved as a batch):** `EnemySide` gains
  `band` (stamped `spawn_band` — `ground_scale.entity_band` reads
  it; a 0 stamp would derive from the site, so the row declares
  it); `PlayerSheet.ground_armor_id: str` → `ground_armor_ids:
  tuple[str, ...]` (armor is five slots — head/body/hands/legs/
  feet); new `PlayerSheet.ground_ammo: tuple[tuple[str, int], ...]`
  (pack stacks by catalog id + rounds, e.g. `(("pistol_rounds",
  40),)` — the stack's `ammo_type` links it to the weapon through
  the real matching helpers); the ground map seeds ONLY the
  declared combatants — the isolated first-sight fight (ambient
  wander-in is a later scenario's question).

## SETTLED 5 (2026-09-24, user) — the review-pass rulings (phase 2)

An ADVISE reviewer pass over the proposed phase-2 brief surfaced
one SHIPPED BUG and three design holes; the four load-bearing
claims were independently re-verified in code before ruling.

- **The ground R key is a shipped no-op — fix it and DROP the
  chooser.** The dispatch's RELOAD branch calls `_reload(ctx)`
  without await (`_loop.py`) and `_rules_ground.reload_weapon` is
  a coroutine — the live R key has never worked while the tutorial
  teaches it. Ruling: fix the await AND remove the multi-slot
  chooser; R always reloads the FIRST dry active slot with
  reserve. Uniform mechanism, zero sim/live seam, and the chooser
  has never actually run (the key was dead), so no live UX is
  lost. This is the ONE ruled `src/spacehack/` exception to phase
  2's stop rule — the fix lands as its own commit at the build's
  start. REVIEW-PASS NOTE (2026-09-25): "first dry slot" =
  `_reloadable_slots()[0]` — the first active slot with ROOM in its
  magazine (a partial magazine tops off), guide worded to match;
  `_reload_slot` vs `ground_reload_ui.reload_weapon_slot` remain
  parallel transactional reload bodies — recorded debt for a later
  pass (consolidating exceeds this phase's one-ruled-exception
  budget).
- **Reference target = closest everywhere.** The stance selects
  the closest alive enemy each turn (cycling TARGET through the
  real dispatch); FIRE and the MOVE band rule reference the same
  enemy. (The mismatch would otherwise idle the stance — no FIRE,
  no MOVE, AP forfeited — while a legal shot sat on a non-target
  squadmate, biasing Goal-2's measurement.)
- **DISENGAGED is its own outcome column.** Ground fights can end
  with all enemies transiently unseen and survivors alive
  (`combat_should_end` → "DISENGAGED"); it is UNRESOLVED like
  TIMEOUT — not a win, not a defeat. `win_rate` counts
  VICTORY/runs (the floor still bites); a nonzero DISENGAGED
  count is itself a stance/geometry finding named at the
  checkpoint.
- **`EnemySide.band` defaults to 0** (site-derived per
  `ground_scale.entity_band`; space rows untouched, the landed
  goal_1 row needs no edit).

Mechanical corrections from the same pass, folded into the brief:
the planet-mode grid runs the LIVE Mars pipeline and the
first-sight audit measurement comes from that same pipeline
(`generate_dungeon` carves tiles only; `populate_dungeon` is the
entity-scatter step that gets skipped); `init_fog` +
`reveal_around` run unconditionally on planet-mode grids (the fog
`visible` grid drives `refresh_engaged`/`combat_should_end` corner
semantics, and `reveal_around` no-ops without `init_fog`); the
ground RNG-rebind set extends beyond loop/ai/actions to
`_ai_ground`, `noise`, and `ground_npcs`; the back-off-inside-min
unit pin needs a synthetic min_range≥2 weapon/row (unreachable on
the tutorial sheet); verified audit numbers pre-pinned (new-game
ground HP **28** for the forced sheet — stamina 10+2 species +12
class = 24 → 20+24//3, and `_player_hp_state` only grows so the
GameContext default 23 must never leak into a ground ctx; the
taught loadout is exactly one 40-round stack; magazines seed full
at 12; level 1 is honest — the tutorial's level-up top-up fires
only after the fight and ground math reads `ground_stats` only).
BUILD-SESSION DEBT (2026-09-25 review pass, recorded for the next
trait-bearing ground row): `_ground_deadshot` holds an import-time
`engine.RNG` binding outside the rebind set — unreachable today
(no shipped row declares traits), but a deadshot-trait row must add
it to `_RNG_MODULES` or its rolls split across instances (the row's
determinism pin would catch it loudly).

## SETTLED 6 (2026-09-25, user) — the standard: how balance is judged

The checkpoint conversation (attrition reframe + the stance
exploration) produced the measurement doctrine; user, verbatim:
"**That shape works. it gives us a place to start tuning from.
Let's choose floors/ceilings from these scenarios we have now. Call
this the standard. Just so we have a starting point.**"

- **A reference pilot is a yardstick, not a player.** Stances are
  frozen measurement instruments; once landed, any drift in their
  measured numbers is drift in the GAME. A policy change to a stance
  is a benchmark revision: re-measure and re-rule its rows in the
  same commit.
- **The ground ladder has two rungs** (no third): `hold_range` =
  rung 0, the open-floor baseline (tutorial-honest, geometry-blind);
  `posted_hold` = rung 1, the geometry ceiling (posted in a 1-wide
  lane, bait, punish arrivals). The rung gap bounds the player
  population; mastery itself is not modeled.
- **Metrics by theater** (user rulings): space rows assert a
  win-rate band; ground rows assert COST — win rate stays as a
  coarse floor, the load-bearing bars are `damage_taken_ceiling`
  (health % of the sheet's max) and `ammo_spent_ceiling` (rounds).
  DISENGAGED is a reported smell column, never a verdict.
- **The board (the standard, bars = 2026-09-25 measurements + a hair
  of slack, deterministic batches so any bar movement is a swing):**

  | row | policy | measured (landed rows, 2026-09-25) | bars |
  |---|---|---|---|
  | goal_1_starter_vs_jack | space | 0.950 | band [0.94, 0.99] |
  | goal_2_starter_mars_delve | rung 0, pistols | 1.00 / 4.68 HP (17%) / 12.56 rds | floor 0.94, dmg ≤ 5.0, ammo ≤ 13.0 |
  | goal_2_mars_batons | rung 0, batons | 1.00 / 8.24 HP (29%) / 0 rds | floor 0.94, dmg ≤ 8.5 |
  | goal_2_lane | rung 1, full queue | 1.00 / 2.00 HP (7%) / 11.96 rds | floor 0.94, dmg ≤ 2.5, ammo ≤ 13.0 |
  | goal_2_lane_countered | rung 1 + sentry drone | 0.98 / 12.57 HP (45%) / 19.98 rds | floor 0.94, dmg ≤ 13.5, ammo ≤ 21.0 |

  (The board's baseline = the landed rows' own output — the standard's
  drift contract requires the record and the pinned batches to agree
  exactly; review issue 2 caught the first cut quoting the checkpoint's
  ad-hoc probe numbers instead.)

- **What each row protects**: goal_2 = the naive cost (the main
  tuning dial); lane = the geometry contract (melee rushers cannot
  answer a 1-wide lane — collision/LOS/AP-drain mechanics changes
  fail this row); lane_countered = the anti-degenerate guard (ranged
  enemies are the pool's answer to turtling — the drone makes posting
  cost 45% health where the uncountered lane costs 7%, rarely fatal:
  attrition, not execution).
- **Probe, then pin**: exploration = ad-hoc `dataclasses.replace`
  variants through the same harness (the checkpoint session's baton /
  bait / lane probes; no machinery); a row is pinned only when a
  number must not drift. Swing tracking = `make check` runs the
  board; a failing bar IS the swing, `python3 -m tests.balance.report`
  shows what moved.
- **Parked findings** (recorded, awaiting tuning): goal_2's measured
  1.00 win rate — a sure-thing tutorial fight, no ceiling until
  tuned; the taught 40-round reserve is never reached in the
  reference fight (the reload lesson is not load-bearing there);
  open-floor denial-without-geometry disengages (kiting away ends the
  fight — corridors are load-bearing for rung-1 play).
- **Deliberately not modeled**: map-scale attrition (sequential
  fights, re-engagement, the exit-heal valve, med-pack economy) —
  the deferred map-scale row class; a separate question from fight
  balance.

## SETTLED 7 (2026-09-26, user — the resumption: full-loadout sheets + re-ground)

> "Yes, let's wrap up these and re-ground. I want the sim harness to
> be able to fully simulate the players loadout."

- **The harness simulates the COMPLETE kit** — both weapon sets (doc
  51's install path already partitions `ground_weapon_ids` by class;
  no new sheet field needed), the bandolier (doc 52's store), armor,
  traits, space side. What was missing: a stance that EMITS the set
  swap and rows that exercise it.
- **goal_2 RE-GROUNDED to the taught kit** (doc 51.4 + 52.6 changed
  what the tutorial teaches): two Kinetic Pistols + Combat Knife
  (auto-partitioned sets), bandolier-restocked rounds, and the
  tutorial-honest stance is now toggle-capable. Expected and to be
  VERIFIED: the numbers do not move (the pistols' min range 1 means
  the knife never binds vs the scavenger pack — the sheet becomes
  honest, the bars stay).
- **New row: the doc-51 motivating matchup** — railgun + mono blade
  vs the Mars pack, the two-set loadout whose probe (100%/25%, full
  clear at every stat rung) motivated the whole weapon-sets build.
  Pins the toggle mechanic permanently.
- **The `toggle_sets` stance**: hold_range's ladder + the SWAP_SETS
  rung (real dispatch, 1 AP, band maintenance). Absorbs doc 51
  SETTLED 4's deferred re-rule scope.
- **Endurance pins land** (doc 52 SETTLED 6's deferred phase 5):
  kills-of-endurance per caliber (cap ÷ measured rounds-per-kill)
  as a caps-catalog regression test with the measured constants
  recorded.
- **Perf preamble (same resumption, 2026-09-26)**: the board runs the
  SIM TIER — `animation_timing.set_render_frames(False)`, a
  programmatic-only dial above INSTANT (INSTANT itself untouched BY
  USER RULING: "I like the speed of instant today. I don't want it
  to change") + a pristine-snapshot planet-grid cache. Board 232s →
  11s, byte-identical numbers (da92217e/afbfac40/ea5a3caf).

## SETTLED 8 (2026-09-26, user — the weapon-identity rulings)

> "let's do it. commit to: double 2h damage; rocket cap leave at
> 10! and I think enemies with rocket launchers should not roll with
> max ammo. keep it scarce. and also 2x rocket launcher firing at
> the player with max ammo would be a lot; SMG -- hmm. I like we're
> you're going with burst fire. But what if it fires twice per
> round. 2x damage, 2x ammo drain? 2x chances to land damage per AP
> cost."

- **DOUBLE EVERY TWO-HANDED WEAPON'S DAMAGE** — uniform across
  ranged AND melee (the hands-parity logic applies identically: 1H
  pairs get the volley economy, 2H pays double for single-slot).
  Ruled doctrine, probed end-to-end (both matchup tables).
- **Rocket cap STAYS 10.** Measured post-×2 via the two-set
  consumer (rocket + blade): 1.33 rds/kill → the cap delivers ~7.5
  kills (pin floor 7); the ruled ~10-boom target's remainder rides
  on cluster splash (one rocket into a bunched pack kills 2-3).
- **ENEMY SCARCITY (measured, reported):** explosive-ammo DROPS
  ceiling at 2 (authored `max_drop` — kit drops included, all three
  roll sites). AND the ×2 enemy-wielder danger is REAL: vs the
  standard 28-HP tutorial sheet, a band-3 grenade brute measures
  **25/25 DEFEATS (32.8 mean damage)** and a band-4 rocket brute
  **25/25 DEFEATS (51.6 mean, 69 max)** — every run fatal. Enemy
  fire budgets / enemy-side explosive taper = flagged follow-up
  ruling. (Also measured: single-set PLAYER explosives die to their
  own doubled splash when the pack closes — the launcher + blade
  toggle is the post-×2 play pattern, 25/25 at 7.4 damage.)
- **Guide outcome (the contract's checklist):** reviewed with the
  retune — no existing guide statement is false (the guide is
  qualitative on weapon stats). FOLLOW-UP: the SMG's double-fire is
  invisible at purchase (the armory detail has no fire-rate column)
  — a UI polish item, not a guide edit.
- **SMG double-fire**: a `shots_per_action` weapon property (default
  1; smg = 2) — one FIRE action rolls twice: 2x damage, 2x ammo
  drain, 2x hit chances, ONE AP cost. Player AND enemy fire paths
  (the family ladder lets enemies roll smgs). The reliability hose
  identity: anti-dodge, sustained pressure, deep mag — at double the
  ammo burn.

## The scenario data model (the row — SETTLED 2-5 shape)

Authoring a protected situation = adding one frozen row. Composition
is pinned BY ID (spec ids, not copied stats) so catalog rebalances
flow through while the matchup stays declared:

```python
@dataclass(frozen=True)
class BalanceScenario:
    id: str                    # "goal_1_starter_vs_jack"
    theater: str               # "space" | "ground"
    goal: str                  # the stated feel goal, verbatim
    player: PlayerSheet        # level/stats->skills, hull id,
                               #   weapon ids, module ids, traits;
                               #   ground rows add ground_weapon_ids,
                               #   ground_armor_ids, ground_ammo
    enemies: tuple[EnemySide, ...]   # spec id + start cell + band
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
ids, module ids, traits; ground rows additionally declare the ground
loadout (`ground_weapon_ids`, `ground_armor_ids` across the five
slots, `ground_ammo` pack stacks — SETTLED 4), and each theater
ignores the other's fields. The harness builds
REAL objects from the ids — `OwnedShip` through the ship module's
own install helpers, `PilotSkills` from the declared level/stats,
ground weapons/armor/ammo through the ground equipment module's own
install and stack helpers — never hand-built structs with copied
numbers.

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
  the assert lands with them (SETTLED 3). Brief below.
  LANDED 2026-09-24: harness + gate green under two reviewer passes;
  tuning ruling (Skiff power gen 2→3, 33104dd7) measured in at 0.960;
  thresholds ruled as a win-rate BAND — floor 0.95, ceiling 0.99,
  "never a sure thing" (user ruling) — asserted green (cb159520).
- [x] 2. **Ground theater** — the ground builders + the `hold_range`
  stance through the same runner; first row = the tutorial Mars
  fight on a planet-pinned delve grid (SETTLED 4 + the SETTLED 5
  review amendments, ruled 2026-09-24 — the Line candidate was
  space-side, see the correction there; the R-key fix rides this
  phase as its one ruled src exception).
  Swapped ahead of the CLI front (user, 2026-09-24): real machinery
  with a live trigger (doc 48's ground work) beats an optional
  front. Brief below (approved by the build session, 2026-09-25).
  BUILT + CLOSED 2026-09-25: R-key fix 603077a2 (reviewer
  REQUEST_CHANGES → all fixes applied), ground theater 0d9f7262
  (reviewer APPROVE, four minors applied/recorded). The checkpoint
  conversation reframed ground balance as ATTRITION (user: the map
  is the encounter — 20-40 enemies; win rate is the space lens),
  added the ammo metric, explored the skill ladder (stun batons
  31%, open-floor denial DISENGAGES, posted lanes ~7%), and landed
  THE STANDARD (SETTLED 6): four ground rows with ruled bars from
  their own landed batches, asserted green — goal_2 1.00/4.68 HP/
  12.56 rds (the 1.00 parked as the first tuning target), batons
  8.24 dmg ≤ 8.5, lane 2.00 dmg ≤ 2.5, countered 0.98 (1 defeat in
  50) / 12.57 dmg ≤ 13.5 — the drone counter prices posting at 45%
  health, rarely fatal. The standard's own review pass (REQUEST_
  CHANGES, both blockers fixed in-commit): posted_hold regained the
  RELOAD rung (its absence made 6 of 7 countered defeats dry-magazine
  suicides, an instrument artifact), and the board's baseline was
  re-measured from the landed rows (probe numbers had leaked into the
  record). Suite cost: balance board ~232s (gate ~5 min).
- [ ] 3. **CLI reporting front (OPTIONAL)** — `tools/balance_sim.py`
  reading the same rows for bulk runs and richer output than an
  assert (SETTLED 1's optional front). Cut only when a tuning session
  actually wants it; adding scenarios needs none of this.
- [ ] 4. **Line closed-form migration** — author the Line watch
  scenario on the Line grid and retire `tests/test_line_tuning.py`'s
  closed form per doc 48's INTERIM note. Needs its own brief-time
  refinement: the closed form's die/clear fit margins must translate
  to averaged-outcome thresholds honestly.

- [x] 5. **Full-loadout resumption (SETTLED 7)** — LANDED 2026-09-26:
  the toggle_sets stance through the real SWAP_SETS dispatch; goal_2
  re-grounded to the taught kit (pistols + knife + restocked
  bandolier) with numbers VERIFIED BYTE-IDENTICAL (4.68/12.56 — the
  knife doesn't bind vs the pack: the sheet became honest, the bars
  stood); goal_2_mars_railgun_blade pins the doc-51 motivating
  matchup (1.000 / 7.84 / 12.0 pre-SETTLED-8; re-ruled same-commit
  under the retune to 7.12 with bar 8.0 — the benchmark-revision
  clause; the 7.84 included a bounded dead-zone swap-churn turn,
  disclosed in the row comment); endurance pins per caliber at each
  MEASURED consumer (guns >= 35; explosives via two-set consumers:
  grenade 2.00 rds/kill, rocket 1.33 -> ~7.5 kills at cap 10). The
  x2 doctrine was subsequently RULED AND LANDED as SETTLED 8 (the
  tuning arc's proposal, executed); doc 52's deferred battle-x2
  consumer measurement remains deferred — battle rifle as the rifle
  caliber's better consumer. One pin caught the synthetic fixture
  inheriting
  the re-grounded stance — fixtures pin their instrument explicitly
  now.

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

**Stop point:** no ground rows or ground harness (2), no CLI
front (3), no Line migration (4), no new stances beyond STAND_AND_TRADE,
no balance CHANGES to any spec — phase 1 measures and pins; if the
measurement says the fight misses the goal, the fix is a separate
tuning decision with its own commits. No guide edits (nothing
player-facing changed).

**Playtest checkpoint:** the Phase 1 PLAYTEST list above — its
center is item 3, the threshold ruling; the phase ticks only with
the ruled numbers asserted green.

### Phase 2 PLAYTEST (checkpoint = the Goal-2 ruling)

**Checkpoint record (2026-09-25, measured through the harness, N=100,
seed base 20260925, grid seed 115, hold_range):**

| metric | measured |
|---|---|
| win rate | **1.00** (100 wins, 0 defeats) |
| mean turns (won runs) | 3.11 (max 4) |
| mean HP damage taken (won runs) | 4.68 |
| timeouts / disengagements | 0 / 0 |

Read: the tutorial's Mars fight is currently a SURE THING — the
starter with two pistols deletes a three-scavenger first-sight pack
in ~3 turns taking ~5 HP. The Goal-1 ceiling precedent ("never a
sure thing") flags this symmetrically: a first ground fight that
cannot be lost teaches nothing. Also of note: the 40-round reserve
is never reached (6 volleys × 2 rounds = 12 rounds < one magazine
pair), so the reload lesson the tutorial teaches is never
load-bearing in the reference fight.

**RULED (2026-09-25, across the checkpoint conversation — SETTLED
6):** ground balance is ATTRITION (user: "ground combat is about
attrition. on any ground combat map, you could fight 20-40 different
enemies. So 100% win rate isn't the thing to measure... The real
measure is how much % of your health did it cost you"), plus an
ammo-cost metric (user: "One more metric I'd like to see. Ammo
spent"), plus the reference-pilot doctrine after the stance
exploration ("I don't care to 100% mimic my 30 years of playing
roguelikes strategy. I just want to be able to properly judge
balance in these fight sims so we can tune and track unexpected
balance swings") — landed as the four-row cost board with bars from
the measured batches ("Call this the standard"). The 1.00 finding
stays parked (no ceiling until tuned).

1. `python3 -m tests.balance.report` — read the Mars row's measured
   table (win rate, mean/max turns, mean HP damage taken, timeouts,
   disengagements) and the batch parameters (N, base seed, grid
   seed).
2. Sanity-check the read against the lived fight: you fought Mars
   delves through doc 48's ground playtests — if the measured
   number contradicts the feel, that is a finding (stance wrong,
   reference delve unrepresentative, or the feel wrong); say which.
   A nonzero DISENGAGED count is its own finding (stance/geometry).
3. RULE the numbers: state the win-rate band (floor + ceiling per
   the Goal-1 precedent) and optionally turns/damage ceilings. They
   land as the row's `thresholds` + the parameterized assert, and
   the phase ticks.
4. Optional cross-check: play the tutorial Mars fight once (fresh
   new game or dev mode) — the sim's verdict should match your
   sense of "pretty easily."
5. The R-key fix live: in any ground fight, dry a magazine and
   press R — the first dry active slot reloads from reserve (no
   chooser, no freeze); the tutorial's "press R to reload" advice
   is finally true.
6. `make check` with the assert live: green, and the batch's suite
   cost stays reasonable.
7. Guide diff (the R-key fix is player-facing): the guide's reload
   coverage vs the now-working R key — before/after or none, per
   the checklist contract. Save/load: nothing to check — the sim
   is test-only surface and the fix touches no save state.

### Phase 2 Implementation brief (PROPOSED 2026-09-24 — SETTLED 1-5,
### amended after the ADVISE review pass; ready for
### /implement-phase 50.2 on approval)

**Scope (files / hook points):**

- **The R-key fix** (`src/spacehack/combat/_loop.py` +
  `_rules_ground.py` — the ONE ruled src exception, SETTLED 5):
  add the missing await on the dispatch's `_reload(ctx)` call AND
  drop `_choose_reload_slot` — R reloads the FIRST dry active slot
  with reserve, deterministically. Own commit at the build's
  start, with its own regression pin (sabotage-proven) and a guide
  review of the reload section (the guide may describe a working R
  key that never existed).
- **Row-shape amendments** (`tests/balance/scenarios.py`): the
  SETTLED 4 batch — `EnemySide.band: int = 0` (stamped
  `spawn_band`; 0 = site-derived, so ground rows declare it and
  space rows never touch it); `PlayerSheet.ground_armor_id` →
  `ground_armor_ids: tuple[str, ...] = ()`; new
  `PlayerSheet.ground_ammo: tuple[tuple[str, int], ...] = ()`;
  `GridSpec` gains `planet_id: str = ""` + `grid_seed: int = 0`
  (planet mode: dims asserted against the planet's
  `DungeonParams`).
- **Ground builders** (`tests/balance/harness.py`, extended):
  - Sheet: `starting_ground_stats(species, class)` (the real
    builder, the `starting_pilot_skills` idiom); ground weapons via
    the ground equipment module's own install path (slot occupancy
    enforced, magazines seeded as the real equip path seeds them);
    armor pieces into their catalog slots; `ground_ammo` as pack
    stacks through the real storage helpers. ctx carries the ground
    fields the rules touch (`ground_stats`, `ground_hp` /
    `ground_max_hp` seeded at **28** — verified in SETTLED 5:
    stamina 24 for the forced sheet → 20+24//3, and
    `_player_hp_state` only grows, so the GameContext default 23
    must never leak into a ground ctx — the equipped lists).
  - Grid: planet mode runs the LIVE delve pipeline with the row's
    grid seed (SETTLED 5) — `generate_dungeon` (tiles only, no
    entities) → `prepare_mars_surface` for Mars (the tile
    mutations the tutorial fight happens among: landmark stamp at
    the spawn, concealed stairs) → SKIP `populate_dungeon` (the
    entity-scatter step) — then seeds ONLY the declared
    combatants: player `Entity(owned=True)` + enemies stamped
    `npc_char_id` + `spawn_band` (SETTLED 4). `init_fog` +
    `reveal_around` at the player start run UNCONDITIONALLY: the
    fog `visible` grid drives `refresh_engaged` /
    `combat_should_end` corner semantics, and `reveal_around`
    no-ops without `init_fog`.
  - `begin_run` ground path: the real `_rules_ground.init(ctx,
    enemy_entities, game_map, console=absorbing)` — ground init is
    simpler than space's; enemy weapon/carried-consumable rolls
    (`noise.ensure_rolled_weapon`, `roll_carried_consumables`)
    happen inside the seeded run, the `roll_flown_equipment`
    doctrine.
- **`hold_range` stance** (`tests/balance/harness.py` STANCES): the
  SETTLED 4+5 policy — each turn, select the closest alive enemy
  as the reference target (cycling TARGET through the real
  dispatch), then FIRE while any active slot passes the real
  `can_fire` against it → RELOAD a dry slot with reserve (through
  the real dispatch's RELOAD — deterministic first-dry-slot after
  the SETTLED 5 fix) → MOVE one step per the band rule (approach
  when the reference target is beyond the reference weapon's
  max_range or has no LOS; back off inside min_range; the
  SETTLED-26 mirror; step choice via the real walkable checks /
  `find_path`) → WAIT. Reference weapon = first active slot.
  Emits keyboard action strings through `_dispatch_combat_action`
  only — never calls rules internals directly.
- **The Goal-2 row** (`tests/balance/scenarios.py`):
  `goal_2_starter_mars_delve` — theater "ground"; the tutorial
  moment's full sheet: human/merchant level 1, the space side as
  goal_1 pins it (the player flies the starter + 2 light lasers +
  shield_mk1 to Mars) AND the taught ground side (kinetic_pistol
  ×2, `(("pistol_rounds", 40),)` — exactly one full stack — no
  armor); enemies = the reference delve's first-sight group with
  band 1 (audit-pinned: run the LIVE Mars pipeline — SETTLED 5 —
  and measure the canonical first-sight engagement: which
  monster(s), what cells, at what sight radius; choose the
  reference grid seed from that measurement, never a guess);
  stance `hold_range`; runs/seed in the goal_1 idiom;
  `thresholds=None` until the checkpoint rules them. Proposed goal
  wording (settled at approval): "A fresh pilot with two Kinetic
  Pistols can win the tutorial's Mars ground fight pretty easily."
- **Outcome set + report**: `RunResult`/aggregate/report gain
  DISENGAGED as its own unresolved column (SETTLED 5; `win_rate` =
  VICTORY/runs); rides the existing `python3 -m tests.balance.report`
  (it loops every row) — ground rows' damage column is ground HP;
  relabel hull→HP in the header if trivial.

**Build order:** the R-key fix (own commit, sabotage-proven pin,
guide review) → row-shape amendments → ground sheet builder →
planet-mode grid builder + combatant seeding → `begin_run` ground
path → `hold_range` → the audit-pinned Goal-2 row → determinism
pins → full gate → PLAYTEST checkpoint (the ruling) → land the
ruled `thresholds` + assert as the phase's closing commit.

**Binding rulings:** SETTLED 1-5 in full. Measure-then-rule for the
Goal-2 numbers (SETTLED 3's precedent — report-only until the
checkpoint). Composition by id everywhere (specs, planet, ammo);
the row pins COMPOSITION, the catalog flows through. Real AI, real
dispatch, derived combat seeds, the fixed grid seed declared by the
row. The R-key fix is the ONE ruled `src/spacehack/` exception
(SETTLED 5); any other src edit — stop: that is a design question,
not a fix.

**Required tests:** ground determinism (same row twice → identical
aggregates end to end; the ground rebind set is loop / ai /
actions / `_ai_ground` / `noise` / `ground_npcs` — SETTLED 5);
`hold_range` unit pins (selects the closest alive enemy via TARGET
cycling; fires in-band through the real `can_fire`; reloads a dry
slot with reserve via the real reload path — the post-fix
first-dry-slot behavior; approaches when the reference target is
beyond max or unseen; backs off inside min — pinned on a synthetic
min_range≥2 weapon/row, unreachable on the tutorial sheet; WAITs
only when nothing else applies; never emits a fire out of band);
planet-grid pin (dims asserted vs `DungeonParams`; identical tiles
from the same `grid_seed`; fog grids present post-`init_fog`);
entity stamps (`npc_char_id` + `spawn_band` → the instance
resolves at the declared band through `ground_scale`); the R-key
fix's regression pin (sabotage-proven: unfix → test fails);
Goal 2 runs to completion across N runs with every run resolving
VICTORY / DEFEAT / TIMEOUT / DISENGAGED (no hangs); the phase-1
space row and existing combat suites stay green.

**Stop point:** no CLI front (3), no Line migration (4), no new
stances beyond `hold_range`, no scenarios beyond the Goal-2 row
(later rows are doctrine, not phase work), no balance changes to
any ground spec — phase 2 measures and pins; a miss against the
goal is a separate tuning decision with its own commits. The ONE
player-facing change is the R-key fix: the guide's reload coverage
is reviewed in the fix's commit and the diff rides the playtest
checklist.

**Playtest checkpoint:** the Phase 2 PLAYTEST list above — its
center is item 3, the threshold ruling; the phase ticks only with
the ruled numbers asserted green.

### Phase 5 Implementation brief (APPROVED 2026-09-26 — SETTLED 7,
### conversational ruling; executed in the resumption session)

**Scope:** `toggle_sets` stance (stances.py — hold_range's ladder
with the SWAP_SETS rung after FIRE; swap when the ACTIVE set's class
is wrong for the distance: ranged and inside its min, melee and
nothing in reach; 1-AP guard by the rules hook itself); goal_2's
sheet gains combat_knife (auto-partitioned) + stance toggle_sets,
comment re-pinned to the taught-kit verbatims; NEW row
goal_2_mars_railgun_blade (railgun + mono_blade sets, rifle_rounds
40, toggle_sets, thresholds from measurement + the standard's slack
idiom); endurance pins in test_balance.py (caps catalog vs ruled
floors at each caliber's WORST measured consumer: guns >= 35 kills,
explosives >= 8).

**Binding rulings:** SETTLED 7; goal_2's re-ground MUST verify
numbers-unchanged (the knife doesn't bind — that is the finding);
bars re-ruled only where they move (the benchmark-revision clause).

**Stop point:** no CLI front (3), no Line migration (4), no new
doctrines — rows and stances only.

## Pre-implementation audit (Phase 2 — 2026-09-25, code-verified)

### 1. Existing modules / patterns to reuse

- **The R-key bug, pinned to its lines.** `_loop._dispatch_combat_action`'s
  RELOAD branch calls `_reload(ctx)` with no await
  (`combat/_loop.py:557-562`); `_rules_ground.reload_weapon` is a
  coroutine (`_rules_ground.py:695`) whose multi-candidate path awaits
  `_choose_reload_slot` → `pygame_story.choose` — the never-run modal.
  The fix: await the call, drop `_choose_reload_slot` + `_reload_option`
  (combat-side only — `ground_reload_ui.py`'s exploration chooser is a
  SEPARATE flow and stays), reload `_reloadable_slots()[0][0]` always.
  `_reloadable_slots` already returns active+dry+reserve slots in slot
  order, so "first dry active slot with reserve" is `[0]`. Existing
  chooser pins to update: `tests/combat/test_rules_ground.py:1352-1403`
  (three modal tests become deterministic first-slot tests).
- **The live delve pipeline, exactly as the fight runs it.**
  `game_interactions._build_surface_dungeon` (game_interactions.py:131):
  `generate_dungeon(params)` (dungeon_bsp.py:9 — tiles only, reads
  `engine.RNG` at call time) → `prepare_mars_surface(ctx, map, spawn)`
  for Mars (main_quest/_act0.py:96 — landmark stamp + concealed stairs +
  one cache guardian via `_spawn_cache_guardian`, all reading
  `engine.RNG`/module state at call time) → `populate_dungeon(map,
  params, spawn, tier=mission_tier)` (dungeon_population.py:178 — the
  entity scatter; `_SPAWN_CLEAR_RADIUS=5` keeps squads ≥6 Chebyshev from
  spawn while `sight_radius=8`, so at-spawn first sight is reachable).
  Planet mode runs generate + prepare, skips populate, strips ALL map
  entities (the guardian included — it is generated scatter), seeds the
  declared combatants. Entry invariants from
  `_install_dungeon_player`: `init_fog` (dungeon_fov.py:16) then
  `reveal_around` at spawn — the fog `visible` grid is what
  `visible_hostiles`/`refresh_engaged`/`combat_should_end` read
  (`_encounter.py:261-277` uses the FOV grid when present).
- **Ground entry call shape**: `_run_ground_combat_tick`
  (game_flow.py:231) — detect (after `move_ground_npcs` + reveal) →
  `_rules_ground.init(ctx, hostiles, game_map, console=console)` → the
  unified `run_combat`. The harness mirrors init + the same
  `_mirror_loop` (rules-module polymorphic — ground slots straight in;
  `_end_player_turn` already branches on ground for the pre-turn death
  check, `_finish_combat` deletes the save only on DEFEAT — the
  sandboxed HOME covers it).
- **Ground sheet builders are the game's own.**
  `character.starting_ground_stats(species, class)` (character.py:90,
  the `starting_pilot_skills` idiom); weapons via `weapon_instance` +
  `install_weapon` (magazines seed FULL at capacity — 12 for the
  kinetic_pistol; ground_equipment.py:152, 549); armor via
  `install_armor` into catalog slots; ammo as
  `add_item_stack`/`add_item_quantity` pack stacks. ctx ground fields
  (GameContext defaults are the leak to avoid: `ground_hp=23`):
  `ground_stats`, `ground_hp=ground_max_hp=28`, `equipped_ground_weapons`
  (list), `equipped_ground_armor` (dict slot→entry),
  `ground_expedition_items` (stacks; `reserve_ammo_count` matches by
  `ammo_type`).
- **Enemy construction stamps**: `world.Entity(npc_char_id=..., spawn_band=...)`
  — `_build_enemy_instance` resolves spec through `npc_char_id`, band
  through `ground_scale.entity_band` (entity stamp wins; 0 derives from
  the site — with `interior_cache_key` unset, context_band returns 1),
  weapon via `noise.ensure_rolled_weapon` (inside the seeded run),
  carried consumables via `roll_carried_consumables`. `faction.
  spec_is_hostile` — Mars pool monsters are `always_hostile=True`, so an
  empty `faction_reputation` is honest.
- **`hold_range` reads**: `can_fire(slot, ctx)` is the real band gate
  (out-of-max, LOS, AP, ammo — `_rules_ground.py:525`); the band itself
  is `_ground_charger.weapon_range(wid, ctx, ap)` → (min, max);
  `find_path` (world) for step choice; TARGET cycles through
  `_dispatch_combat_action`. The tutorial sheet's pistols are
  min_range 1 — the back-off branch needs a synthetic min≥2 row (as
  SETTLED 5 says).
- **XP path is sim-safe**: `xp.add_xp` (on_kill awaits it) opens no
  modal below level 40 — level-ups log only.
- **Guide lines the R fix touches**: `data/guide/__init__.py:161`
  (Controls: "R: reload your active weapon (ground combat)" — stays
  true), `:292-297` (Ground Gear: describes the combat R opening "a
  chooser" — never-shipped behavior; must be re-worded to the
  deterministic first-dry-slot reload, keeping the exploration chooser
  sentence true), `:247` (combat body: "press R to reload" — finally
  true), `:515` (exploration tip — unchanged).

### 2. Duplication hotspots + DRY strategy

1. **Space vs ground paths inside the harness** (the drift risk):
   one `begin_run` dispatching on `row.theater` to two thin builders
   (`_begin_space_run` = today's body, `_begin_ground_run`), sharing
   the snapshot/rebind/teardown spine, the ctx factory, and the
   `_mirror_loop`. No second loop, no second aggregate.
2. **Grid builders**: `build_game_map` (system mode) gains a planet
   mode sibling `_build_planet_grid` — both return `world.GameMap`;
   the synthetic-blocks mode stays. Dims assert idiom shared (assert
   vs `DungeonParams.width/height`, assert generated spawn == the
   row's pinned `player_start` — loud on planet-spec drift, never
   silent).
3. **Stance step-choice vs enemy AI movement**: the stance's one-step
   band move must reuse `move_entity`/walkable checks + `find_path`,
   not re-implement walking. `hold_range` itself decomposes into
   module-level helpers (`_reference_target`, `_band_step_action`) so
   each policy phase is pin-testable in isolation.

### 3. The first-sight audit pin (measured 2026-09-25)

Live pipeline scan (generate → prepare → populate → entry invariants →
`detect_ground_combat` at spawn) over 129 grid seeds: at-spawn first
sight is the minority case (≈17% of seeds), single monsters dominate;
multi-monster groups are 5 seeds, all single-squad. **Reference grid
seed = 115**: spawn **(100, 47)**, first-sight group = THREE
`rock_scavenger` from one squad at **(106, 44), (107, 44), (108, 43)**
(distances 6/7/8 Chebyshev, LOS clear, all `spawn_band=1`) — the
swarm-pack fight the tutorial teaches into (scavenger squads run 3-5;
`hp=14`, `monster_claws`, hunter behavior). Alternatives measured:
seed 88 (2 scavengers @6), seed 39 (2 dust_prowlers @7), seed 8/91/118
(lone sentry_drone — the guard read, weaker as the tutorial's
representative swarm moment).

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
