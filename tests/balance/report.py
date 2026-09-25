"""``python3 -m tests.balance.report`` — the balance report front.

SETTLED 1: the suite is the benchmarks' home; this CLI is the
exploration/reporting FRONT over the same scenario rows — bulk runs
and a richer read than an assert. The phase-1 checkpoint's ruling
input prints here.

Usage:
    python3 -m tests.balance.report                  # every scenario
    python3 -m tests.balance.report --scenario id    # one scenario
"""

from __future__ import annotations

from tests.balance.harness import (
    aggregate,
    run_batch,
    threshold_checks,
)
from tests.balance.scenarios import SCENARIOS, find_scenario


def _print_row(row) -> None:
    results = run_batch(row)
    report = aggregate(results)
    print(f"== {row.id} ({row.theater}) ==")
    print(f"goal: {row.goal}")
    print(
        f"stance={row.stance}  runs={row.runs}  base_seed={row.seed} "
        f"(run i seeds base+i)"
        + (
            f"  grid_seed={row.grid.grid_seed} (planet {row.grid.planet_id})"
            if row.grid.planet_id else ""
        )
    )
    print(
        f"win_rate={report.win_rate:.3f}  "
        f"wins={report.wins}  defeats={report.defeats}  "
        f"timeouts={report.timeouts}  disengaged={report.disengagements}"
    )
    print(
        f"turns (won runs): mean={report.mean_turns:.2f}  "
        f"max (all runs)={report.max_turns}"
    )
    print(
        f"damage taken, hull/HP (won runs): "
        f"mean={report.mean_hull_damage_taken:.2f}"
    )
    if row.thresholds is None:
        print("thresholds: none yet — report-only (measure, then rule)")
    else:
        checks = threshold_checks(report, row.thresholds)
        for name, value, bar, sign, passed in checks:
            print(
                f"threshold {name}: {value:.3f} {sign} {bar} "
                f"{'PASS' if passed else 'FAIL'}"
            )
        verdict = "PASS" if all(c[4] for c in checks) else "FAIL"
        print(f"thresholds verdict: {verdict}")
    print()


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="tests.balance.report",
        description="Run balance scenarios and print their aggregates.",
    )
    parser.add_argument(
        "--scenario", action="append", default=None,
        help="scenario id to run (repeatable; default: every row)",
    )
    args = parser.parse_args(argv)
    rows = (
        [find_scenario(sid) for sid in args.scenario]
        if args.scenario else list(SCENARIOS)
    )
    for row in rows:
        _print_row(row)


if __name__ == "__main__":
    main()
