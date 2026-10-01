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
from src.spacehack.combat._actions import (resolve_damage, set_combat_locks,
                                              start_enemy_turn)


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
        """The EMP boss-key (SETTLED 34): strips ALL current shields,
        zero hull damage — however fat the pool. On bare shields it
        connects for nothing (the scorer reads the same zero)."""
        _seed(42)
        hull_dmg, shield_dmg, final_hull, glancing = resolve_damage(
            "emp_missile", target_hull=100, target_shields=50,
        )
        assert shield_dmg == 50        # the whole pool, not a flat number
        assert hull_dmg == 0
        assert final_hull == 100
        assert glancing is False
        hull_dmg, shield_dmg, final_hull, _ = resolve_damage(
            "emp_missile", target_hull=100, target_shields=190,
        )
        assert shield_dmg == 190       # anti-stack: the bigger, the more
        hull_dmg, shield_dmg, _, _ = resolve_damage(
            "emp_missile", target_hull=100, target_shields=0,
        )
        assert (hull_dmg, shield_dmg) == (0, 0)   # bare: dead shot

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
        '''The generic damage multiplier halves damage (3 vs 6).'''
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
        '''Damage floor of 1 even with piloting=100 + mult=0.01.'''
        _seed(12345)
        hull_dmg, shield_dmg, final_hull, glancing = resolve_damage(
            "light_laser", target_hull=100, target_shields=0,
            target_pilot_piloting=100, damage_taken_mult=0.01,
        )
        assert hull_dmg == 1
        assert shield_dmg == 0
        assert final_hull == 99
        assert glancing is False


class TestStartEnemyTurn:
    """Doc 48 SETTLED 39/40: the free-regen tier reads the build-time
    hull+module fold (`shield_recharge_bonus`); the paid divert fires
    only below the spec's threshold of max (default half) while power
    lasts."""

    def _enemy(self, **overrides):
        from src.spacehack.combat._types import EnemyInstance
        base = dict(
            shields=10, max_shields=30, shield_recharge_bonus=5,
            power_pool=3, max_power=20, power_gen=4,
            ap_gain_twentieths=80,
        )
        base.update(overrides)
        return EnemyInstance(
            spec_id="x", name="X", char="X", fg=(1, 2, 3), **base,
        )

    def test_free_regen_includes_the_folded_term(self):
        enemy = self._enemy()
        start_enemy_turn(enemy)
        assert enemy.shields == 15      # min(5, room 20) — no power spent
        assert enemy.power_pool == 7    # 3 + gen 4; the free tier is free
        assert enemy.shield_regen_rate == 0  # no divert authored

    def test_free_regen_capped_by_room(self):
        enemy = self._enemy(shields=28, max_shields=30)
        start_enemy_turn(enemy)
        assert enemy.shields == 30      # capped at max

    def test_paid_tier_is_dormant_at_zero_rate(self):
        enemy = self._enemy()
        start_enemy_turn(enemy)
        assert enemy.ap_remaining == 4  # 80 twentieths gain
        assert enemy.cells_moved_this_turn == 0

    def test_divert_fires_below_threshold_with_power_spend(self):
        """Below half of 30 (gate 15): shields 10 divert — rate 2 for
        2 power (engineering 10 buys no discount yet), on top of the
        free tier."""
        enemy = self._enemy(shield_regen_rate=2)
        start_enemy_turn(enemy)
        assert enemy.shields == 17      # +2 paid, +5 free
        assert enemy.power_pool == 5    # 3 + gen 4 - 2 spent

    def test_divert_holds_at_or_above_threshold(self):
        """Shields 15 of 30 sit AT the default gate — the paid tier
        holds; the free tier is unconditional."""
        enemy = self._enemy(shields=15, shield_regen_rate=2)
        start_enemy_turn(enemy)
        assert enemy.shields == 20      # free tier only
        assert enemy.power_pool == 7

    def test_divert_threshold_is_per_spec(self):
        """A tuned 0.3 gate diverts later in the drain (shields 10 of
        30 still above a gate of 9)."""
        enemy = self._enemy(
            shields=10, shield_regen_rate=2, shield_regen_threshold=0.3,
        )
        start_enemy_turn(enemy)
        assert enemy.shields == 15      # free tier only
        low = self._enemy(
            shields=8, shield_regen_rate=2, shield_regen_threshold=0.3,
        )
        start_enemy_turn(low)
        assert low.shields == 8 + 2 + 5  # below the 9 gate: divert fires

    def test_divert_power_bounded_and_engineering_discounted(self):
        """Engineering 40 halves the rate-2 cost to 1 power; an empty
        pool diverts nothing."""
        enemy = self._enemy(
            shield_regen_rate=2, pilot_engineering=40,
        )
        start_enemy_turn(enemy)
        assert enemy.shields == 17
        assert enemy.power_pool == 6    # 3 + 4 - 1 (discounted)
        # Gen lands BEFORE the divert decision (the player twin's
        # order): an empty pool with generation still diverts.
        refilled = self._enemy(
            shield_regen_rate=2, power_pool=0,
        )
        start_enemy_turn(refilled)
        assert refilled.power_pool == 2  # 0 + 4 - 2
        dry = self._enemy(
            shield_regen_rate=2, power_pool=0, power_gen=0,
        )
        start_enemy_turn(dry)
        assert dry.shields == 15        # free tier only — no power to divert
