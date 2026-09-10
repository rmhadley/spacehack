"""Doc 41 phase 3: the 30-floor tuning harness (pure closed form).

Doc 39's contract, made checkable: the FULL watch is provably
unwinnable below level 30 and a real costly win at 30+; the THIN
watch is the fight method's timing play — winnable by a skilled
mid-20s fit. Everything derives from the REAL catalogs and the
REAL combat formulas (``combat/_stats.py``); the fits are the
canonical min-maxed archetypes at their level.

Bound directions (the ADVISE ruling): payload positions are live
and arrivals stagger, so the aggregate race is the wrong verdict —
UNWINNABLE is proven when the player loses at the computed bound
(min enemy damage roll, quality 1.0, the fit's stated dodge,
hand-set dps); WINNABLE is proven under the ALL-SIMULTANEOUS
assumption (stagger only ever helps the player). The fits' dps
carry the 95%-hit x 1.2-roll provenance in their comments.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.combat._stats import (
    _calc_ap, _calc_hull_for_enemy, _calc_max_shields, calc_hit_chance,
)
from src.spacehack.data.npc_ships import find_npc_ship
from src.spacehack.data.weapons import find_weapon

BEST_ROLL = 0.8     # the enemy's minimum damage roll


def _picket_volley(dodge: int) -> float:
    """One picket's damage per round against a player at ``dodge``
    (best-case-for-player rolls), from the REAL spec + formulas."""
    _spec = find_npc_ship("militia_blockade")
    _ap = _calc_ap(_spec.pilot_piloting)
    _total, _shots = 0.0, []
    for _w in _spec.weapons:
        _ws = find_weapon(_w)
        _n = _ap // _ws.ap_cost
        _ap -= _n * _ws.ap_cost
        _shots += [_w] * _n
    for _w in _shots:
        _ws = find_weapon(_w)
        # Mirror the real build (_stats.py: the accuracy bonus folds
        # into gunnery, which hit chance reads at half rate).
        _hit = calc_hit_chance(
            _w, _spec.pilot_gunnery + _spec.ai_accuracy_bonus, 3.0, dodge,
        )
        _total += (_hit / 100.0) * _ws.damage * BEST_ROLL
    return _total


def _picket_ehp() -> int:
    _spec = find_npc_ship("militia_blockade")
    return _calc_hull_for_enemy(_spec) + _calc_max_shields(_spec, _spec)


# The canonical fits (skill points = 5/level; a min-maxed combat
# build spends them on gunnery/piloting/engineering, with the
# level's credits buying the next gear tier).
# dps provenance: sustained weapon cycles at 95% hit x 1.2 roll.
FIT_25 = dict(hull=80, shields=60, regen=10, dps=46, dodge=30)   # mid-20s
FIT_29 = dict(hull=90, shields=80, regen=10, dps=55, dodge=33)   # the ceiling below the floor
FIT_30 = dict(hull=100, shields=130, regen=30, dps=87, dodge=35)  # the AP-5 breakpoint + capacitor stack

FULL_WATCH = 10
THIN_WATCH = 4


def _player_wins(fit: dict, n_pickets: int) -> bool:
    """The closed-form race: the fit clears the watch before its
    effective pool empties (regen included)."""
    _incoming = n_pickets * _picket_volley(fit["dodge"]) - fit["regen"]
    _rounds_to_clear = (n_pickets * _picket_ehp()) / fit["dps"]
    _rounds_to_die = (fit["hull"] + fit["shields"]) / max(_incoming, 1)
    return _rounds_to_die > _rounds_to_clear


def test_full_watch_unwinnable_below_30():
    """Even under best-case play, the 29 ceiling cannot clear ten
    pickets before the sustained convergence melts it."""
    assert not _player_wins(FIT_29, FULL_WATCH), (
        "doc 39's floor: below 30 the full watch is a death"
    )


def test_full_watch_a_costly_win_at_30():
    """The level-30 endgame fit (the piloting-40 AP breakpoint +
    the capacitor stack + engineering sustain) clears the full
    watch — barely, which is what 'costly' means in closed form."""
    assert _player_wins(FIT_30, FULL_WATCH), (
        "at 30+ the fight must be winnable"
    )


def test_thin_watch_is_the_timing_play():
    """The maintenance month's four pickets lose to a mid-20s fit
    under the all-simultaneous bound — the same schedule hole the
    dark run uses."""
    assert _player_wins(FIT_25, THIN_WATCH), (
        "the thin watch is deliberately beatable earlier"
    )
