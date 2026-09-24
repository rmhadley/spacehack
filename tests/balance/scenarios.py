"""Balance scenario table (doc 50, SETTLED 2 + 3).

The unit of balance protection: one frozen row per situation the user
does not want drifting. Composition is pinned BY ID (spec ids, never
copied stats) so catalog rebalances flow into scenarios while the
matchup stays declared. Data-first SHAPE, dev-only HOME (tests/, not
``data/``) — balance scenarios are test fixtures, not game content.

Geometry pins for Goal 1 come from the live fight, code-verified in
doc 50's pre-implementation audit: Jack spawns at Mercury's landmark
(80, 52); ``pirate_scout.detect_radius=8`` triggers the fight with the
player due east (the Earth->Mercury approach) at (88, 52); the grid
is Sol's own 200x140 map (bodies derived from the catalog at build
time), so the end-turn reinforcement path (ambient traffic +
re-detect) behaves exactly as in the live fight.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    """A scenario's ruled pass bars, asserted by the parameterized gate.

    Every field is optional at the data-shape level but a thresholds-
    bearing row must state at least one; ``None`` overall means
    report-only (SETTLED 3: Goal 1 rules its numbers at the phase-1
    checkpoint from the measured report). The win-rate bars form a
    BAND: the floor keeps the goal honest, the ceiling keeps the
    fight honest — a matchup that can never be lost is as broken as
    one that can't be won.
    """

    win_rate_floor: float | None = None      # fraction of runs won, 0..1
    win_rate_ceiling: float | None = None    # never a sure thing, 0..1
    rounds_ceiling: float | None = None      # mean turns per run
    damage_taken_ceiling: float | None = None  # mean hull damage per run


@dataclass(frozen=True)
class PlayerSheet:
    """The complete player side (SETTLED 2: 'all the things').

    Level-1 sheets derive skills through ``starting_pilot_skills``;
    higher levels will carry declared skill spends when a scenario
    needs them (the harness raises on level != 1 until then).
    ``ground_*`` fields exist for the phase-3 ground theater; space
    runs ignore them.
    """

    species_id: str
    class_id: str
    hull_id: str
    weapon_ids: tuple[str, ...]
    module_ids: tuple[str, ...]
    trait_ids: tuple[str, ...] = ()
    level: int = 1
    # Declared level-up spends, (("gunnery", 5), ...) — 5 points per
    # level past 1, applied by the harness onto the starting skills
    # (the same +1-per-point fold ``xp._apply_skill_point`` does).
    skill_spends: tuple[tuple[str, int], ...] = ()
    ground_weapon_ids: tuple[str, ...] = ()
    ground_armor_id: str = ""


@dataclass(frozen=True)
class EnemySide:
    """One enemy combatant: spec id + start cell (x, y)."""

    spec_id: str
    pos: tuple[int, int]


@dataclass(frozen=True)
class GridSpec:
    """The declared map grid.

    A ``system_id`` grid IS that system's map (the live fight's
    geometry): the harness asserts the declared size against the
    catalog and derives the blocking body footprints from it at build
    time — composition by id, so a body move in the system spec flows
    into scenarios instead of fighting on a stale copy. A
    system-less grid is synthetic geometry: size + unwalkable rect
    blocks (x, y, w, h), stamped as-is.
    """

    width: int
    height: int
    blocks: tuple[tuple[int, int, int, int], ...] = ()
    system_id: str = ""


@dataclass(frozen=True)
class BalanceScenario:
    """One protected situation: both sides, the grid, the stance, N runs."""

    id: str
    theater: str                  # "space" (ground rows join phase 3)
    goal: str                     # the stated feel goal, verbatim
    player: PlayerSheet
    player_start: tuple[int, int]  # the live fight's first-trigger cell
    enemies: tuple[EnemySide, ...]
    grid: GridSpec
    stance: str                   # STANCES vocabulary key (harness)
    runs: int                     # N per batch
    seed: int                     # base; run i rebinds RNG to base+i
    thresholds: Thresholds | None  # None = report-only


SCENARIOS: tuple["BalanceScenario", ...] = (
    BalanceScenario(
        id="goal_1_starter_vs_jack",
        theater="space",
        goal=(
            "A starter ship with 2 lasers and a Shield Mk. 1 can "
            "pretty easily beat the forced tutorial Crimson Jack fight."
        ),
        player=PlayerSheet(
            # The tutorial's own forced combo (title_flow.py:74 runs
            # new games as human merchant — character creation is
            # skipped). Corrected 2026-09-24: the first cut wrongly
            # pinned human bounty_hunter, a better pilot than the
            # tutorial actually flies (gunnery 16 vs 12).
            species_id="human",
            class_id="merchant",
            hull_id="starter",
            weapon_ids=("light_laser", "light_laser"),
            module_ids=("shield_mk1",),
        ),
        player_start=(88, 52),
        enemies=(EnemySide(spec_id="pirate_scout", pos=(80, 52)),),
        grid=GridSpec(width=200, height=140, system_id="sol"),
        stance="stand_and_trade",
        runs=100,
        seed=20260924,
        # Ruled at the phase-1 checkpoint (2026-09-24): win the fight
        # easily but never a sure thing (<=0.99 — at least one upset
        # survives the declared batch). Floor eased 0.95 -> 0.94
        # (user ruling: measured 0.950 sat exactly on the bar; a hair
        # of room keeps the pin from tripping on the first whisper of
        # drift).
        thresholds=Thresholds(
            win_rate_floor=0.94,
            win_rate_ceiling=0.99,
        ),
    ),
)

_BY_ID = {row.id: row for row in SCENARIOS}


def find_scenario(id: str) -> "BalanceScenario":
    """Raise ``KeyError`` for an unknown scenario id (catalog idiom)."""
    return _BY_ID[id]
