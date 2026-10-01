"""Doc 41 phase 3: the 30-floor tuning harness (pure closed form).

Doc 39's contract, made checkable — RE-PINNED 2026-09-24 for doc 48
phase 7 (SETTLED 39): the picket carries band 2, pilot skills derive
from the band budget, the cruiser hull's own shields and recharge are
honored, and the volley walks real weapon AP. Everything derives from
the REAL catalogs and the REAL combat formulas (``combat/_stats.py``);
the fits are the canonical min-maxed archetypes at their level.

EXTENDED 2026-09-24 for doc 48 phase 8 (SETTLED 40 addition, treatment
a — INTERIM by design; ``future/50_DESIGN_COMBAT_BALANCE_SIMULATOR.md``
supersedes closed-form pinning when it lands): the volley carries the
aggressiveness factor (agg 70 -> ~30% of decision points reposition
instead of firing) and regen gains the threshold-gated paid divert
(authored rate 2 below half shields, power-sustained).

RE-DERIVED 2026-09-30 for doc 56 phase 5 (SETTLED 24, enemy volley
parity): one fire action now fires every affordable weapon at
max-AP-once — the picket's two light lasers both ride each 1-AP
action, exactly DOUBLING its output per AP. Both live verdicts
FLIPPED: the super sheet's brute-force skip is gone (dies ~7.8
rounds into the ~15.2 it needs) and the thin watch no longer loses
to the mid-20s timing fit (~5.3 vs ~7.7). The envelope moves are the
phase-4 calibration headline, surfaced at the phase-5 playtest —
this harness pins the moved numbers, never tunes them. Calibration
caveats: the flat x0.70 is the open-floor expectation — a DENSE
watch crowds the player's ring until pickets have no legal
reposition cell, and the loop then fires unthinned; power drawdown
is unmodeled (the picket's pool 14 at gen 2/turn (armor watt-free
since SETTLED 31) funds only a few rounds of full volley before thinning) — so
the model reads softer than reality when the watch is dense, and
hotter than reality the longer the race runs.

THE MOVED BRACKET (build-discovered, called out for the playtest):
the parity numbers made the picket ~70% hotter than the doc-41 tuning
(band-2 gunnery + the targeting computer; cruiser hull shields; 4 AP;
free regen 3/turn) — under the survive-vs-clear reading the old
level-30 knife-edge fit now loses the full watch ~5x over (dies in
~4 rounds needing ~22). Per the ruling ("I want it to be extremely
hard... it's a brute force skip the run around shortcut for a super
powered player"), the costly win belongs to the SUPER-POWERED
endgame sheet; the frigate-hull re-author is the user's named
escalation lever (harder only — if the watch reads too hard in play,
that is a user ruling, not a lever).

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
    _calc_ap, _calc_hull_for_enemy, _calc_max_shields, _enemy_hull,
    _enemy_skills, _free_shield_regen, calc_hit_chance,
)
from src.spacehack.data.npc_ships import find_npc_ship
from src.spacehack.data.weapons import find_weapon
from src.spacehack.ship import base_module_entries

BEST_ROLL = 0.8     # the enemy's minimum damage roll


def _picket_build():
    """The picket's build-mirror: the REAL fold (_enemy_skills, the
    same function _build_enemy calls) over base-quality modules —
    the player's best-case bound."""
    _spec = find_npc_ship("militia_blockade")
    _modules = base_module_entries(_spec.modules)
    return _spec, _modules, _enemy_skills(_spec, _modules)


def _picket_volley(dodge: int) -> float:
    """One picket's damage per round against a player at ``dodge``
    (best-case-for-player rolls), from the REAL spec + formulas.
    VOLLEY PARITY (doc 56 SETTLED 24): one fire action fires every
    affordable weapon with AP = max(ap_cost) paid once — both light
    lasers ride each 1-AP action, exactly doubling the single-fire
    shots-per-AP. The Tier-1 aggro factor (doc 48 SETTLED 40): the
    dial (70) converts ~30% of decision points to reposition steps,
    thinning the full-AP volley by the fire fraction."""
    _spec, _modules, (_g, _p, _e) = _picket_build()
    _actions = _calc_ap(_p) // max(
        find_weapon(_w).ap_cost for _w in _spec.weapons
    )
    _per_action = 0.0
    for _w in _spec.weapons:
        _ws = find_weapon(_w)
        _hit = calc_hit_chance(_w, _g, 3.0, dodge)
        _per_action += (_hit / 100.0) * _ws.damage * BEST_ROLL
    return _per_action * _actions * (_spec.ai_aggressiveness / 100.0)


def _picket_ehp() -> int:
    _spec, _modules, _skills = _picket_build()
    return _calc_hull_for_enemy(_spec, _modules) + _calc_max_shields(
        _enemy_hull(_spec), _modules,
    )


def _picket_regen() -> int:
    """Sustained regen per picket per round: the free tier (hull base
    + modules) plus the threshold-gated paid divert (doc 48 SETTLED
    40) — the race's decisive stretch runs below half shields, where
    the blockade's authored rate 2 diverts (power: the flown build's
    net gen sits at 2 (armor watt-free, SETTLED 31; it was 1 through phase-2 upkeep) — pool 14 funds the
    divert + volley for a few rounds before drying; drawdown stays
    unmodeled here, see the module docstring)."""
    _spec, _modules, _skills = _picket_build()
    _free = _free_shield_regen(_enemy_hull(_spec), _modules)
    return _free + _spec.shield_regen_rate


# The canonical fits (skill points = 5/level; a min-maxed combat
# build spends them on gunnery/piloting/engineering, with the
# level's credits buying the next gear tier).
# dps provenance: sustained weapon cycles at 95% hit x 1.0 avg roll.
FIT_25 = dict(hull=73, shields=105, regen=11, dps=85, dodge=40)    # mid-20s: cruiser + mk2 shield stack, piloting 55
FIT_29 = dict(hull=113, shields=120, regen=15, dps=100, dodge=50)  # the ceiling below the floor: frigate + piloting 80 with gyro mk2
FIT_SUPER = dict(hull=100, shields=338, regen=19, dps=132, dodge=60)  # the max sheet: gunnery/piloting 100, twin shield_mk4 at prototype, 8 heavy-laser AP

FULL_WATCH = 10
THIN_WATCH = 4


def _player_wins(fit: dict, n_pickets: int) -> bool:
    """The closed-form race: the fit clears the watch before its
    effective pool empties (regen included, on both sides)."""
    _incoming = n_pickets * _picket_volley(fit["dodge"]) - fit["regen"]
    _net_dps = fit["dps"] - n_pickets * _picket_regen()
    if _net_dps <= 0:
        return False  # the pickets out-regen the damage output
    _rounds_to_clear = (n_pickets * _picket_ehp()) / _net_dps
    _rounds_to_die = (fit["hull"] + fit["shields"]) / max(_incoming, 1)
    return _rounds_to_die > _rounds_to_clear


def test_full_watch_unwinnable_below_30():
    """Even under best-case play, the 29 ceiling cannot clear ten
    pickets — under volley fire it melts in ~3.0 rounds against the
    ~25.0 it needs (doc 56 SETTLED 24 doubled the picket's output
    per AP)."""
    assert not _player_wins(FIT_29, FULL_WATCH), (
        "doc 39's floor: below 30 the full watch is a death"
    )


def test_full_watch_now_unwinnable_even_for_the_super_sheet():
    """FLIPPED under volley parity (doc 56 SETTLED 24; surfaced at
    the phase-5 playtest as phase-4's headline input): the doubled
    picket volley kills the brute-force skip — the super sheet dies
    in ~7.8 rounds against the ~15.2 it needs. Restoring the skip is
    phase-4 calibration's call (divert/magnitude dials), never this
    harness's."""
    assert not _player_wins(FIT_SUPER, FULL_WATCH), (
        "volley parity moved the envelope: the skip is gone at "
        "current magnitudes — phase 4 calibrates"
    )


def test_thin_watch_no_longer_loses_to_the_mid_20s_fit():
    """FLIPPED under volley parity (surfaced at the phase-5
    playtest): the maintenance month's four pickets now out-race the
    mid-20s fit (~5.3 rounds to die vs ~7.7 to clear) — the timing
    play the dark run used is gone at current magnitudes. The pin
    records the moved envelope; phase 4 calibrates."""
    assert not _player_wins(FIT_25, THIN_WATCH), (
        "volley parity moved the envelope: the thin watch is no "
        "longer the early timing play — phase 4 calibrates"
    )


def test_picket_parity_numbers_pinned():
    """The re-pin's premise, pinned: band-2 derivation + hull parity
    make the picket LVL 10 with 4 AP, hull shields, and free regen —
    the doc-41 comment's 'light cutter' scaled to its band. The
    phase-8 extension pins the two Tier-1 terms: the volley carries
    the 0.70 fire fraction and regen gains the below-half divert."""
    _spec, _modules, (_g, _p, _e) = _picket_build()
    assert (_g, _p, _e) == (44, 32, 22)
    assert _calc_ap(_p) == 4
    assert _picket_ehp() == 125
    assert _picket_regen() == 3 + 2   # free tier + the authored divert
    _spec_agg = _spec.ai_aggressiveness
    assert _spec_agg == 70
    assert _spec.shield_regen_threshold == 0.5   # the "below half" gate
    # The factor: the volley is the full-AP action walk scaled by
    # agg/100 — and doc 56 SETTLED 24 puts BOTH lasers on every
    # action (4 actions x 2 lasers; AP = max paid once), exactly
    # double the single-fire walk's 4 shots.
    _full = _picket_volley(40) / (_spec_agg / 100.0)
    assert _full > _picket_volley(40)          # the thinning is live
    assert abs(_picket_volley(40) - _full * 0.70) < 1e-9
    _laser_ev = (
        calc_hit_chance("light_laser", _g, 3.0, 40) / 100.0
        * find_weapon("light_laser").damage * BEST_ROLL
    )
    assert abs(_full - 8 * _laser_ev) < 1e-9   # 4 actions x both lasers
