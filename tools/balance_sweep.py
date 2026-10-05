"""Doc 56.4 dial sweeps (SETTLED 30 upkeep scaling + SETTLED 29 clamp).

Ad-hoc instrument, tools/ scope (outside lint by design): imports the
doc-50 harness batch runner + the cal4 scenario rows and re-runs them
under patched dial settings, printing one table per setting. Report-
only — sweep values NEVER land in catalog data or src/; a dial becomes
a real authored edit at the checkpoint ruling or not at all.

Two sweeps:

upkeep   Swaps dataclasses.replace copies into data/modules/_BY_ID
         (the registry behind find_module; forced built first, and
         each assignment is the COMPLETE dict so unswept ids never
         KeyError). Two families per the brief: uniform magnitude
         (x2/x3 over every authored upkept value) and steepness
         (mk-indexed curves, mk1 pinned at -1, singles kept authored
         — SETTLED 30 asks whether drain scales FASTER up the
         ladders, which uniform xk alone never measures).

clamp    Swaps a parametric twin of clamp_hit_chance into BOTH live
         space-side bindings — combat._stats.clamp_hit_chance (read
         by calc_hit_chance as a module global) AND the from-import
         binding combat._missile_flight.clamp_hit_chance (the missile
         guidance rolls; patch only the first and marauder/warlord
         tables silently misattribute). Space-side only: ground's
         own literal (_ground_math) is a separate twin the checkpoint
         rules on deliberately.

A row whose swept sheet becomes power-refused or unpackable under an
extreme setting (build_owned_ship's loud assert) prints REFUSED for
that setting — the table bounds the ladder where the gate binds
instead of crashing. The authored baseline (x1 / cap 95) prints once
per invocation as the comparison anchor.

Usage:
    python3 tools/balance_sweep.py                # both sweeps, all cal4 rows
    python3 tools/balance_sweep.py upkeep
    python3 tools/balance_sweep.py clamp
    python3 tools/balance_sweep.py --only raider  # substring row filter
    python3 tools/balance_sweep.py --runs 20      # trim runs per row
"""

from __future__ import annotations

import argparse
import dataclasses
import sys

sys.path.insert(0, ".")

from src.spacehack.combat import _missile_flight, _stats
from src.spacehack.data import modules as modules_pkg
from src.spacehack.data.modules import list_modules
from tests.balance.harness import aggregate, run_batch
from tests.balance.scenarios import SCENARIOS

CAL4_ROWS = tuple(r for r in SCENARIOS if r.id.startswith("probe_cal4"))

# Dial surfaces (brief item 2): magnitudes x2/x3 over authored, the
# steepness example curve verbatim, ceilings 90/98 around authored 95.
MAGNITUDE_KS = (2, 3)
STEEPNESS_CURVES = ((1, 3, 6, 10),)
CLAMP_CEILINGS = (90, 98)

# Module ids whose chain head is the mk1 without a _mkN suffix
# (the MK_CHAINS naming split: targeting_computer, gyro_stabilizer).
_IMPLICIT_MK1 = frozenset({"targeting_computer", "gyro_stabilizer"})

# The pre-patch authored curve, captured once (see _authored_upkeep).
_AUTHORED_CACHE: dict[str, int] | None = None


def _mk_of(module_id: str) -> int | None:
    """The mk rung 1..4 of an upkept id, or None for singles."""
    if module_id in _IMPLICIT_MK1:
        return 1
    if "_mk" in module_id:
        tail = module_id.rsplit("_mk", 1)[1]
        if tail.isdigit():
            return int(tail)
    return None


def _authored_upkeep() -> dict[str, int]:
    """Every module that draws watts today (negative bonus).

    Cached on first read — the sweep patches the live registry, so a
    later setting computed from a re-read would scale the ALREADY
    SCALED values (x3 reading the x2-patched registry = x6 in
    disguise). First read always happens pre-patch.
    """
    global _AUTHORED_CACHE
    if _AUTHORED_CACHE is None:
        _AUTHORED_CACHE = {
            m.id: m.power_gen_bonus
            for m in list_modules()
            if m.power_gen_bonus < 0
        }
    return _AUTHORED_CACHE


def _magnitude_setting(k: float) -> dict[str, int]:
    """Uniform xk over every upkept value (ints; xk of -1 rounds to -k)."""
    return {mid: -int(round(k * -v)) for mid, v in _authored_upkeep().items()}


def _steepness_setting(curve: tuple[int, ...]) -> dict[str, int]:
    """mk n (n >= 2) draws -curve[n-1]; mk1 and singles stay authored
    (the SETTLED-29/30 shape: mk1 is NPC-load-bearing and untouched)."""
    out = {}
    for mid, authored in _authored_upkeep().items():
        mk = _mk_of(mid)
        if mk is not None and 1 < mk <= len(curve):
            out[mid] = -curve[mk - 1]
        else:
            out[mid] = authored
    return out


def _apply_upkeep(setting: dict[str, int]) -> None:
    """Swap replace() copies into the COMPLETE registry dict."""
    modules_pkg._registry()  # force the lazy build (it starts None)
    modules_pkg._BY_ID = {
        mid: (
            dataclasses.replace(spec, power_gen_bonus=setting[mid])
            if mid in setting else spec
        )
        for mid, spec in modules_pkg._BY_ID.items()
    }


def _make_clamp_twin(ceiling: int):
    def _clamp(chance: int) -> int:
        return max(5, min(ceiling, chance))

    _clamp.__name__ = f"clamp_hit_chance_cap{ceiling}"
    return _clamp


def _print_table(title: str, setting_note: str, rows, runs: int) -> None:
    print(f"== {title} ==")
    print(setting_note)
    for row in rows:
        effective = runs or row.runs
        target = row if effective == row.runs else dataclasses.replace(
            row, runs=effective,
        )
        try:
            report = aggregate(run_batch(target))
        except AssertionError as exc:
            print(f"{row.id:42s} REFUSED ({str(exc).splitlines()[-1]})")
            continue
        arrival = report.missile_resolved_arrival_rate.get("player")
        print(
            f"{row.id:42s} win {report.win_rate:.3f}"
            f"  dmg {report.mean_hull_damage_taken:.2f}"
            f"  turns {report.mean_turns:.2f}"
            f"  def {report.defeats}"
            + (f"  p-arrival {arrival:.0%}" if arrival is not None else "")
        )
    print()


def _baseline(rows, runs: int) -> None:
    _print_table(
        "baseline (authored curve, clamp 95)",
        "shield/targeting/gyro ladders -1/-2/-3/-4; singles -1",
        rows, runs,
    )


def run_upkeep_sweep(rows, runs: int) -> None:
    originals = dict(modules_pkg._registry())
    try:
        for k in MAGNITUDE_KS:
            setting = _magnitude_setting(k)
            note = f"uniform x{k}: every upkept value x{k}"
            _apply_upkeep(setting)
            _print_table(f"upkeep magnitude x{k}", note, rows, runs)
        for curve in STEEPNESS_CURVES:
            setting = _steepness_setting(curve)
            note = (
                f"steepness {'/'.join(f'-{n}' for n in curve)} by mk"
                " (mk1 and singles authored)"
            )
            _apply_upkeep(setting)
            _print_table(f"upkeep steepness {'/'.join(map(str, curve))}", note, rows, runs)
    finally:
        modules_pkg._BY_ID = dict(originals)


def run_clamp_sweep(rows, runs: int) -> None:
    saved = (_stats.clamp_hit_chance, _missile_flight.clamp_hit_chance)
    try:
        for ceiling in CLAMP_CEILINGS:
            twin = _make_clamp_twin(ceiling)
            _stats.clamp_hit_chance = twin
            _missile_flight.clamp_hit_chance = twin
            _print_table(
                f"clamp ceiling {ceiling}",
                f"space-side hit-chance clamp 5-{ceiling} (both live"
                " bindings; ground untouched)",
                rows, runs,
            )
    finally:
        _stats.clamp_hit_chance, _missile_flight.clamp_hit_chance = saved


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="tools/balance_sweep.py",
        description="Doc 56.4 dial sweeps over the cal4 scenario rows.",
    )
    parser.add_argument(
        "sweep", nargs="?", default="all", choices=("all", "upkeep", "clamp"),
        help="which sweep to run (default: both)",
    )
    parser.add_argument(
        "--only", action="append", default=None,
        help="substring filter on row ids (repeatable; default: all cal4 rows)",
    )
    parser.add_argument(
        "--runs", type=int, default=None,
        help="override runs per row (default: each row's declared 50)",
    )
    args = parser.parse_args(argv)

    rows = CAL4_ROWS
    if args.only:
        rows = tuple(
            r for r in rows if any(pat in r.id for pat in args.only)
        )
    runs = args.runs if args.runs else 0

    _baseline(rows, runs)
    if args.sweep in ("all", "upkeep"):
        run_upkeep_sweep(rows, runs)
    if args.sweep in ("all", "clamp"):
        run_clamp_sweep(rows, runs)


if __name__ == "__main__":
    main()
