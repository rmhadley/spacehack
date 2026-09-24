"""Balance gate (doc 50, SETTLED 1) — the benchmarks' pytest home.

Every scenario row in ``tests/balance/scenarios.py`` runs its batch
through the real combat resolution here; rows with ruled thresholds
assert them. Pure harness math (seed derivation, aggregate, threshold
bars) is pinned directly.
"""

from __future__ import annotations

import dataclasses

import pytest
from src.spacehack.combat import _loop
from tests.support.asyncutil import run as _async_run

from tests.balance import harness
from tests.balance.harness import (
    BatchReport,
    RunResult,
    aggregate,
    begin_run,
    derived_seed,
    meets_thresholds,
    run_batch,
    run_once,
)
from tests.balance.scenarios import SCENARIOS, Thresholds, find_scenario

_RESOLVED = frozenset({"VICTORY", "DEFEAT", "TIMEOUT"})


def test_seed_derivation_is_base_plus_run_index() -> None:
    """The house derived-seed pattern: distinct streams per run."""
    assert derived_seed(100, 0) == 100
    assert [derived_seed(100, i) for i in range(3)] == [100, 101, 102]
    assert len({derived_seed(50, i) for i in range(10)}) == 10


def test_aggregate_math_on_a_mixed_batch() -> None:
    """win_rate over all runs; rounds/damage means over WON runs only."""
    results = [
        RunResult("VICTORY", 3, 0),
        RunResult("VICTORY", 5, 10),
        RunResult("DEFEAT", 2, 15),
        RunResult("TIMEOUT", harness.TURN_CAP, 7),
    ]
    report = aggregate(results)
    assert report.runs == 4
    assert report.wins == 2
    assert report.defeats == 1
    assert report.timeouts == 1
    assert report.win_rate == 0.5
    assert report.mean_turns == 4.0          # (3 + 5) / 2 won runs
    assert report.mean_hull_damage_taken == 5.0  # (0 + 10) / 2
    assert report.max_turns == harness.TURN_CAP


def test_aggregate_on_an_empty_batch() -> None:
    report = aggregate([])
    assert report.win_rate == 0.0
    assert report.mean_turns == 0.0
    assert report.mean_hull_damage_taken == 0.0


def test_meets_thresholds_checks_every_stated_bar() -> None:
    report = BatchReport(
        runs=10, wins=8, defeats=2, timeouts=0, win_rate=0.8,
        mean_turns=4.0, max_turns=7, mean_hull_damage_taken=2.5,
    )
    assert meets_thresholds(report, Thresholds(win_rate_floor=0.7))
    assert not meets_thresholds(report, Thresholds(win_rate_floor=0.9))
    # The ceiling bar bites on both sides: a 0.8 batch passes under
    # 0.99, a sure-thing 1.0 batch fails it ("never a sure thing").
    assert meets_thresholds(report, Thresholds(win_rate_ceiling=0.99))
    assert not meets_thresholds(report, Thresholds(win_rate_ceiling=0.79))
    sure_thing = dataclasses.replace(report, win_rate=1.0)
    assert not meets_thresholds(sure_thing, Thresholds(win_rate_ceiling=0.99))
    assert meets_thresholds(report, Thresholds(rounds_ceiling=4.0))
    assert not meets_thresholds(report, Thresholds(rounds_ceiling=3.9))
    assert meets_thresholds(
        report, Thresholds(damage_taken_ceiling=2.5),
    )
    assert not meets_thresholds(
        report, Thresholds(damage_taken_ceiling=2.4),
    )
    # Bars left unstated never fail the batch.
    assert meets_thresholds(report, Thresholds())


def test_stand_and_trade_fires_while_affordable_then_waits() -> None:
    """The stance reads affordability through the REAL rules: FIRE
    while power/AP hold (one burst covers every active slot), WAIT
    the moment nothing can fire — never a move."""
    row = find_scenario("goal_1_starter_vs_jack")
    with harness._inert_presentation(), harness._sandboxed_home():
        rules = harness._rules_space
        try:
            ctx, game_map, console, rules = begin_run(row, 0)
            assert rules.player_ap(ctx) > 0
            assert _async_run(
                harness.STANCES[row.stance](ctx, rules),
            ) == "FIRE"
            # A real FIRE dispatch: both lasers fire (power -2), AP -1.
            power_before = rules._state.player_state["power_pool"]
            ap_before = rules.player_ap(ctx)
            _async_run(_loop._dispatch_combat_action(
                console, ctx, game_map, rules, "FIRE", 0,
            ))
            assert rules._state.player_state["power_pool"] == power_before - 2
            assert rules.player_ap(ctx) == ap_before - 1
            # Power dry -> nothing affordable -> the stance ends the turn.
            rules._state.player_state["power_pool"] = 0
            assert _async_run(
                harness.STANCES[row.stance](ctx, rules),
            ) == "WAIT"
        finally:
            harness.end_run(rules)


# One batch per row per pytest process — the resolve test and the
# thresholds gate share it (a second 50s batch per thresholds-bearing
# row in make check is exactly the cost the checkpoint told us to
# weigh; reviewer issue 10). Keyed on row.id: feed it the AUTHORED
# row, never a dataclasses.replace variant (a short variant would
# poison the cache and fail the len assert).
_BATCH_CACHE: dict = {}


def batch_for(row) -> list:
    if row.id not in _BATCH_CACHE:
        _BATCH_CACHE[row.id] = run_batch(row)
    return _BATCH_CACHE[row.id]


@pytest.mark.parametrize("row", SCENARIOS, ids=[r.id for r in SCENARIOS])
def test_scenario_batch_resolves_every_run(row) -> None:
    """The batch runs to completion under the real resolution: every
    run lands a named outcome — no hangs, no crashes (SETTLED 2)."""
    results = batch_for(row)
    assert len(results) == row.runs
    assert all(r.outcome in _RESOLVED for r in results)


@pytest.mark.parametrize("row", SCENARIOS, ids=[r.id for r in SCENARIOS])
def test_scenario_thresholds(row) -> None:
    """Rows with ruled thresholds assert their goal; report-only rows
    (SETTLED 3, measure-then-rule) skip until the numbers land."""
    if row.thresholds is None:
        pytest.skip("report-only until thresholds are ruled")
    assert any(bar is not None for bar in (
        row.thresholds.win_rate_floor,
        row.thresholds.win_rate_ceiling,
        row.thresholds.rounds_ceiling,
        row.thresholds.damage_taken_ceiling,
    )), "a thresholds row must state at least one bar"
    report = aggregate(batch_for(row))
    assert meets_thresholds(report, row.thresholds), report


def test_goal_1_run_level_determinism() -> None:
    """Same row + run index -> identical fight, end to end through the
    seeded runner (the batch-level determinism contract follows from
    per-run determinism, so the pin needs only a few indices)."""
    row = find_scenario("goal_1_starter_vs_jack")
    first = [run_once(row, i) for i in (0, 1, 2)]
    second = [run_once(row, i) for i in (0, 1, 2)]
    assert first == second


def test_goal_1_batch_aggregate_determinism() -> None:
    """A whole (small) batch re-run folds to the identical aggregate."""
    row = dataclasses.replace(
        find_scenario("goal_1_starter_vs_jack"), runs=3,
    )
    assert aggregate(run_batch(row)) == aggregate(run_batch(row))
