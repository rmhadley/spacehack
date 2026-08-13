"""Tests for combat/_actions.py — resolve_damage with seeded RNG.

resolve_damage uses RNG.randint(1, 100) for quality + RNG.uniform(0.8, 1.2)
for variance. Seeding the RNG before each test gives deterministic output.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.engine import RNG
from src.spacehack.combat._actions import resolve_damage, set_combat_locks


def _seed(n: int = 42) -> None:
    """Re-seed the global RNG for deterministic test output."""
    RNG.seed(n)


def _entity() -> world.Entity:
    return world.Entity("P", (255, 100, 100), world.Position(1, 1), "Pirate")


class TestSetCombatLocks:
    """Transient combat-lock flag: set on lock, removed on unlock."""

    def test_lock_marks_entities(self):
        a, b = _entity(), _entity()
        set_combat_locks(True, [a, b])
        assert a.combat_locked is True
        assert b.combat_locked is True

    def test_unlock_removes_flag(self):
        a = _entity()
        set_combat_locks(True, [a])
        set_combat_locks(False, [a])
        assert not hasattr(a, "combat_locked")

    def test_unlock_without_flag_is_noop(self):
        a = _entity()
        set_combat_locks(False, [a])  # must not raise
        assert not hasattr(a, "combat_locked")

    def test_none_entities_are_skipped(self):
        a = _entity()
        set_combat_locks(True, [None, a])
        assert a.combat_locked is True


class TestResolveDamage:
    """Damage resolution: quality roll → damage_mult + variance.

    Formula (non-EMP path):
      q = RNG.randint(1, 100)
      glancing_threshold = int(target_pilot_piloting * 0.5)
      if q <= glancing_threshold: damage_mult = 0.5
      else: damage_mult = 0.5 + (q - glancing_threshold) / max(1, 100 - glancing_threshold)
      raw_dmg = weapon.damage * damage_mult * RNG.uniform(0.8, 1.2)
      dmg = max(1, int(raw_dmg))
      shields absorb first, remainder hits hull.
    """

    # ---- EMP path ----

    def test_emp_strips_shields(self):
        """emp_missile has shield_strip=20, damage=0."""
        _seed(42)
        hull_dmg, shield_dmg, final_hull, glancing = resolve_damage(
            "emp_missile", target_hull=100, target_shields=50,
        )
        assert shield_dmg == 20
        assert hull_dmg == 0
        assert final_hull == 100
        assert glancing is False

    def test_emp_partial_strip(self):
        """EMP against a target with fewer shields than strip value."""
        _seed(42)
        hull_dmg, shield_dmg, final_hull, glancing = resolve_damage(
            "emp_missile", target_hull=100, target_shields=5,
        )
        assert shield_dmg == 5
        assert hull_dmg == 0
        assert final_hull == 100

    def test_emp_no_shields(self):
        """EMP against shieldless target: strips 0, no hull damage."""
        _seed(42)
        hull_dmg, shield_dmg, final_hull, glancing = resolve_damage(
            "emp_missile", target_hull=100, target_shields=0,
        )
        assert shield_dmg == 0
        assert hull_dmg == 0
        assert final_hull == 100

    # ---- Normal damage path ----

    def test_damage_against_no_shields(self):
        """medium_laser: damage=6, no shields. Seed 42 → hull_dmg=6."""
        _seed(42)
        hull_dmg, shield_dmg, final_hull, glancing = resolve_damage(
            "medium_laser", target_hull=100, target_shields=0,
        )
        assert shield_dmg == 0
        assert hull_dmg == 6
        assert final_hull == 94
        assert glancing is False

    def test_damage_against_shields(self):
        """Shields absorb damage first. Seed 42 → shield_dmg=3, hull_dmg=3."""
        _seed(42)
        hull_dmg, shield_dmg, final_hull, glancing = resolve_damage(
            "medium_laser", target_hull=100, target_shields=3,
        )
        assert shield_dmg == 3
        assert hull_dmg == 3
        assert final_hull == 97
        assert glancing is False

    def test_damage_with_piloting(self):
        """High piloting (80) → threshold=40. Seed 1 → glancing hit, hull_dmg=3."""
        _seed(1)
        hull_dmg, shield_dmg, final_hull, glancing = resolve_damage(
            "medium_laser", target_hull=100, target_shields=0,
            target_pilot_piloting=80,
        )
        assert hull_dmg == 3
        assert shield_dmg == 0
        assert final_hull == 97
        assert glancing is True

    def test_damage_taken_mult(self):
        """Juggernaut trait: damage_taken_mult=0.5 halves damage (3 vs 6)."""
        _seed(42)
        hull_dmg_mult, _, _, _ = resolve_damage(
            "medium_laser", target_hull=100, target_shields=0,
            damage_taken_mult=0.5,
        )
        _seed(42)
        hull_dmg_full, _, _, _ = resolve_damage(
            "medium_laser", target_hull=100, target_shields=0,
            damage_taken_mult=1.0,
        )
        assert hull_dmg_mult == 3
        assert hull_dmg_full == 6

    def test_min_1_damage(self):
        """Damage floor of 1 even with piloting=100 + mult=0.01."""
        _seed(12345)
        hull_dmg, shield_dmg, final_hull, glancing = resolve_damage(
            "light_laser", target_hull=100, target_shields=0,
            target_pilot_piloting=100, damage_taken_mult=0.01,
        )
        assert hull_dmg == 1
        assert shield_dmg == 0
        assert final_hull == 99
        assert glancing is False
