"""Tests for xp.py — XP curve formulas.

xp_for_level and _xp_to_next produce 30 threshold values. A single
off-by-one in the loop body shifts every level from 2–30, which is
completely invisible to manual playtesting.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.xp import (
    _qualifying_traits,
    _xp_to_next,
    ground_damage_reduction,
    xp_for_level,
)


# Design doc table (docs/design/complete/02_DESIGN_XP_LEVELING.md).
# Cumulative XP to reach each level.
_CUMULATIVE_XP: dict[int, int] = {
    1: 0,
    2: 90,
    3: 200,
    4: 330,
    5: 480,
    6: 650,
    7: 840,
    8: 1050,
    9: 1280,
    10: 1530,
    11: 1800,
    12: 2090,
    13: 2400,
    14: 2730,
    15: 3080,
    16: 3450,
    17: 3840,
    18: 4250,
    19: 4680,
    20: 5130,
    21: 5600,
    22: 6090,
    23: 6600,
    24: 7130,
    25: 7680,
    26: 8250,
    27: 8840,
    28: 9450,
    29: 10080,
    30: 10730,
}


class TestXpForLevel:
    """Verify every threshold in the design doc table."""

    def test_all_levels(self):
        for level, expected in _CUMULATIVE_XP.items():
            assert xp_for_level(level) == expected, (
                f"Level {level}: expected {expected}, got {xp_for_level(level)}"
            )

    def test_level_1(self):
        """Level 1 is always 0 XP."""
        assert xp_for_level(1) == 0

    def test_monotonic(self):
        """Each level costs more than the last."""
        prev = 0
        for level in range(2, 31):
            cur = xp_for_level(level)
            assert cur > prev, f"Level {level}: {cur} <= {prev}"
            prev = cur


class TestTraitQualification:
    def _ctx(self, *, piloting=10, total_kills=0):
        return SimpleNamespace(
            stats=SimpleNamespace(
                gunnery=10, piloting=piloting, engineering=10,
            ),
            player_counters=SimpleNamespace(
                deliveries_completed=0,
                total_kills=total_kills,
                melee_kills=0,
            ),
            player_traits=[],
            faction_reputation={},
        )

    def test_ace_pilot_uses_piloting_not_flee_counter(self):
        _traits = _qualifying_traits(
            self._ctx(piloting=40),
        )

        assert "ace_pilot" in {trait.id for trait in _traits}

    def test_ace_pilot_does_not_use_old_flee_counter(self):
        _traits = _qualifying_traits(self._ctx(piloting=10))

        assert "ace_pilot" not in {trait.id for trait in _traits}

    def test_juggernaut_keeps_kill_requirement(self):
        _traits = _qualifying_traits(self._ctx(total_kills=30))

        assert "juggernaut" in {trait.id for trait in _traits}

    def test_charger_requires_40_melee_kills(self):
        _ctx = self._ctx(total_kills=40)
        _ctx.player_counters.melee_kills = 40

        _traits = _qualifying_traits(_ctx)

        assert "charger" in {trait.id for trait in _traits}

    def test_charger_does_not_use_total_kills(self):
        _traits = _qualifying_traits(self._ctx(total_kills=40))

        assert "charger" not in {trait.id for trait in _traits}

    def test_juggernaut_reduces_each_ground_hit(self):
        assert ground_damage_reduction(
            SimpleNamespace(player_traits=["juggernaut"]),
        ) == 1
        assert ground_damage_reduction(
            SimpleNamespace(player_traits=[]),
        ) == 0


class TestXpToNext:
    """Per-level cost: 50 + (level + 1) * 20."""

    def test_level_1_to_2(self):
        """50 + (1+1)*20 = 90."""
        assert _xp_to_next(1) == 90

    def test_level_5_to_6(self):
        """50 + (5+1)*20 = 170."""
        assert _xp_to_next(5) == 170

    def test_level_20_to_21(self):
        """50 + (20+1)*20 = 470."""
        assert _xp_to_next(20) == 470

    def test_level_29_to_30(self):
        """50 + (29+1)*20 = 650."""
        assert _xp_to_next(29) == 650

    def test_sum_matches_cumulative(self):
        """Sum of _xp_to_next(1) through _xp_to_next(n-1) equals xp_for_level(n)."""
        for level in range(2, 31):
            total = sum(_xp_to_next(l) for l in range(1, level))
            assert total == xp_for_level(level), (
                f"Level {level}: sum of costs = {total}, "
                f"xp_for_level = {xp_for_level(level)}"
            )
