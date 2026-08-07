"""Tests for combat/_rules_ground.py — pure formula functions.

Ground combat accuracy, damage, and movement dodge — same
invisible-regression risk as space combat math.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack.combat._rules_ground import (
    _ground_hit_chance_raw,
    _ground_damage_raw,
    _calc_ground_move_dodge,
)


# ---------------------------------------------------------------------------
# _ground_hit_chance_raw
# ---------------------------------------------------------------------------

class TestGroundHitChanceRaw:
    """accuracy + att_reflexes//2 - tgt_reflexes//2 - dodge + hit_bonus,
    clamped 5-95."""

    def test_basic(self):
        """fists: accuracy=90, reflexes 20 vs 10,
        no dodge → 90 + 10 - 5 = 95."""
        chance = _ground_hit_chance_raw("fists", 20, 10, 0, 0)
        assert chance == 95

    def test_attacker_advantage(self):
        """High reflexes attacker."""
        chance = _ground_hit_chance_raw("fists", 40, 10, 0, 0)
        # 85 + 20 - 5 = 100 → clamped 95
        assert chance == 95

    def test_target_dodge(self):
        """Movement dodge reduces hit chance."""
        chance = _ground_hit_chance_raw("fists", 20, 10, 20, 0)
        # 90 + 10 - 5 - 20 = 75
        assert chance == 75

    def test_hit_bonus(self):
        """Sharpshooter +10%."""
        chance = _ground_hit_chance_raw("fists", 20, 10, 0, hit_bonus=10)
        # 85 + 10 - 5 + 10 = 100 → 95
        assert chance == 95

    def test_clamped_low(self):
        chance = _ground_hit_chance_raw("fists", 0, 100, 200, 0)
        assert chance == 5


# ---------------------------------------------------------------------------
# _ground_damage_raw
# ---------------------------------------------------------------------------

class TestGroundDamageRaw:
    """Base damage + str//10 (melee only) - armor, min 1."""

    def test_basic(self):
        """fists: damage=1 (melee), str=20 → +2, armor=0 → 3."""
        dmg = _ground_damage_raw("fists", 20, 0)
        assert dmg == 3  # 1 + 2 - 0

    def test_armor_mitigation(self):
        """armor=3 reduces damage by 3."""
        dmg = _ground_damage_raw("fists", 20, 3)
        assert dmg == 1  # 2 + 2 - 3 = 1

    def test_no_strength_bonus_ranged(self):
        """Ranged weapons don't get the str//10 bonus."""
        # laser_pistol: damage=4, energy type (no str bonus)
        dmg = _ground_damage_raw("laser_pistol", 50, 0)
        assert dmg == 4  # 4 + 0 - 0

    def test_min_1(self):
        """Never below 1 damage."""
        dmg = _ground_damage_raw("fists", 0, 100)
        assert dmg == 1


# ---------------------------------------------------------------------------
# _calc_ground_move_dodge
# ---------------------------------------------------------------------------

class TestCalcGroundMoveDodge:
    def test_no_movement(self):
        assert _calc_ground_move_dodge(0) == 0

    def test_one_cell(self):
        assert _calc_ground_move_dodge(1) == 5

    def test_four_cells(self):
        assert _calc_ground_move_dodge(4) == 20

    def test_cap(self):
        """7 cells → 30 (capped, not 35)."""
        assert _calc_ground_move_dodge(7) == 30
