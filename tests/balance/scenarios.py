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
    higher levels carry declared skill spends (``skill_spends``). The
    ground fields declare the ground loadout (SETTLED 4); each theater
    ignores the other's fields.
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
    # Ground theater (doc 50 SETTLED 4): weapons install through the
    # equipment module's own path (magazines seed full); armor ids fill
    # their catalog slots; ground_ammo packs reserve stacks by catalog
    # id + rounds (``(("pistol_rounds", 40),)`` — the stack's
    # ammo_type links it to the weapon through the real matching
    # helpers). Each theater ignores the other's fields.
    ground_weapon_ids: tuple[str, ...] = ()
    ground_armor_ids: tuple[str, ...] = ()
    ground_ammo: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class EnemySide:
    """One enemy combatant: spec id + start cell (x, y).

    ``band`` stamps ``spawn_band`` — the ground band the instance
    resolves at through ``ground_scale.entity_band`` (doc 50 SETTLED 4;
    0 = site-derived, so ground rows DECLARE it). Space rows never
    touch it (SETTLED 5: the landed goal_1 row needed no edit).
    """

    spec_id: str
    pos: tuple[int, int]
    band: int = 0


@dataclass(frozen=True)
class GridSpec:
    """The declared map grid.

    A ``system_id`` grid IS that system's map (the live fight's
    geometry): the harness asserts the declared size against the
    catalog and derives the blocking body footprints from it at build
    time — composition by id, so a body move in the system spec flows
    into scenarios instead of fighting on a stale copy. A
    ``planet_id`` grid runs the planet's LIVE delve pipeline under the
    row's fixed ``grid_seed`` (dims asserted against the planet's
    ``DungeonParams``). A grid with neither is synthetic geometry:
    size + unwalkable rect blocks (x, y, w, h), stamped as-is.
    """

    width: int
    height: int
    blocks: tuple[tuple[int, int, int, int], ...] = ()
    system_id: str = ""
    planet_id: str = ""
    grid_seed: int = 0


@dataclass(frozen=True)
class BalanceScenario:
    """One protected situation: both sides, the grid, the stance, N runs."""

    id: str
    theater: str                  # "space" | "ground" (SETTLED 4)
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
    BalanceScenario(
        id="goal_2_starter_mars_delve",
        theater="ground",
        goal=(
            "A fresh pilot with two Kinetic Pistols can win the "
            "tutorial's Mars ground fight pretty easily."
        ),
        player=PlayerSheet(
            # The tutorial moment's full sheet: the space side as
            # goal_1 pins it (the player flew the starter + laser pair
            # + shield to Mars) and the taught ground side — two
            # Kinetic Pistols, exactly one 40-round Pistol Rounds
            # stack (the tutorial's own armory beat), no armor.
            species_id="human",
            class_id="merchant",
            hull_id="starter",
            weapon_ids=("light_laser", "light_laser"),
            module_ids=("shield_mk1",),
            ground_weapon_ids=("kinetic_pistol", "kinetic_pistol"),
            ground_ammo=(("pistol_rounds", 40),),
        ),
        # Audit-pinned (doc 50 phase-2 audit §3): grid_seed 115's
        # live Mars pipeline spawns at (100, 47) with one scavenger
        # squad's first three members visible at sight edge — the
        # canonical first-sight fight of the tutorial descent.
        player_start=(100, 47),
        enemies=(
            EnemySide(spec_id="rock_scavenger", pos=(106, 44), band=1),
            EnemySide(spec_id="rock_scavenger", pos=(107, 44), band=1),
            EnemySide(spec_id="rock_scavenger", pos=(108, 43), band=1),
        ),
        grid=GridSpec(width=120, height=90, planet_id="mars", grid_seed=115),
        stance="hold_range",
        runs=100,
        seed=20260925,
        thresholds=None,  # report-only until the checkpoint rules them
    ),
)

_BY_ID = {row.id: row for row in SCENARIOS}


def find_scenario(id: str) -> "BalanceScenario":
    """Raise ``KeyError`` for an unknown scenario id (catalog idiom)."""
    return _BY_ID[id]
