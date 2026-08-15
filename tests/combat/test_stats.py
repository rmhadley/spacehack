"""Tests for combat/_stats.py — pure formula functions.

All functions here are deterministic given their inputs. The module
docstring explicitly states "suitable for testing in isolation."
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

# Make src/ importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack.combat._stats import (
    calc_hit_chance,
    _calc_dodge_bonus,
    _calc_ap,
    _calc_ap_tenths,
    _roll_ap,
    _calc_hull,
    _calc_max_hull,
    _calc_hull_for_enemy,
    _calc_power_gen,
    _calc_max_shields,
    _distance,
    init_combat_state,
    _player_free_regen,
)
from src.spacehack.data.pilot_skills import PilotSkills
from src.spacehack.world import Position


# ---------------------------------------------------------------------------
# calc_hit_chance
# ---------------------------------------------------------------------------

class TestCalcHitChance:
    """Hit chance: accuracy + gunnery/2 + close bonus - dist penalty
    - min penalty - dodge + hit bonus, clamped 5-95."""

    def test_basic_hit(self):
        """medium_laser: accuracy=72, gunnery=20 → +10, dist=3 → no bonus,
        no dodge → 82."""
        chance = calc_hit_chance("medium_laser", 20, 3.0, 0)
        # 72 + 10 + 0 - 0 - 0 - 0 = 82
        assert chance == 82

    def test_close_bonus(self):
        """Within half-range (5//2=2): +5 close bonus."""
        chance = calc_hit_chance("medium_laser", 20, 2.0, 0)
        # 72 + 10 + 5 = 87
        assert chance == 87

    def test_distance_penalty(self):
        """Beyond max_range (5): -10 per overshoot cell. dist=7 → ceil(7)=7,
        penalty = (7-5)*10 = 20."""
        chance = calc_hit_chance("medium_laser", 20, 7.0, 0)
        # 72 + 10 + 0 - 20 = 62
        assert chance == 62

    def test_min_range_penalty(self):
        """medium_laser min_range=1. dist=0 → ceil(0)=0, penalty = (1-0)*5 = 5."""
        chance = calc_hit_chance("medium_laser", 20, 0.0, 0)
        # 72 + 10 + 5(close!) - 0 - 5 = 82
        # Wait: distance 0 ≤ half_range (2) so close_bonus fires.
        # min_penalty = max(0, 1-0)*5 = 5.
        # chance = 72 + 10 + 5 - 0 - 5 = 82
        assert chance == 82

    def test_dodge_bonus(self):
        """Target dodge reduces hit."""
        chance = calc_hit_chance("medium_laser", 20, 3.0, 15)
        # 72 + 10 - 15 = 67
        assert chance == 67

    def test_hit_bonus(self):
        """Sharpshooter-style +10% permanent bonus."""
        chance = calc_hit_chance("medium_laser", 20, 3.0, 0, hit_bonus=10)
        # 72 + 10 + 10 = 92
        assert chance == 92

    def test_clamped_low(self):
        """Never below 5%."""
        chance = calc_hit_chance("medium_laser", 0, 100.0, 90)
        # 72 + 0 + 0 - (95)*10 - 90 = -968 → clamp to 5
        assert chance == 5

    def test_clamped_high(self):
        """Never above 95%."""
        chance = calc_hit_chance("medium_laser", 200, 1.0, 0, hit_bonus=50)
        # 72 + 100 + 5 + 50 = 227 → clamp to 95
        assert chance == 95

    def test_fractional_distance_penalty(self):
        """ceil(distance) means 5.1u counts as 6u for dist penalty."""
        chance = calc_hit_chance("medium_laser", 20, 5.1, 0)
        # ceil(5.1)=6, penalty=(6-5)*10=10
        # 72 + 10 - 10 = 72
        assert chance == 72


# ---------------------------------------------------------------------------
# _calc_dodge_bonus
# ---------------------------------------------------------------------------

class TestCalcDodgeBonus:
    def test_no_movement(self):
        assert _calc_dodge_bonus(0, 0) == 0

    def test_movement_only(self):
        """3 cells → 15%."""
        assert _calc_dodge_bonus(3, 0) == 15

    def test_movement_cap(self):
        """7 cells → 30 (capped, not 35)."""
        assert _calc_dodge_bonus(7, 0) == 30

    def test_piloting_bonus(self):
        """3 cells + 30 piloting → min(15+30, 60) = 45."""
        assert _calc_dodge_bonus(3, 30) == 45

    def test_total_cap(self):
        """7 cells + 50 piloting → min(30+50, 60) = 60."""
        assert _calc_dodge_bonus(7, 50) == 60


# ---------------------------------------------------------------------------
# _calc_ap / _calc_ap_tenths / _roll_ap (fractional AP with carry)
# ---------------------------------------------------------------------------

class TestCalcAp:
    def test_baseline(self):
        """piloting=0 → 3 AP in the first round."""
        assert _calc_ap(0) == 3

    def test_piloting_breakpoint(self):
        """piloting=20 → 3 + 2 = 5 AP (integer part of a 5.0 gain)."""
        assert _calc_ap(20) == 5

    def test_piloting_breakpoint_40(self):
        """piloting=40 → 3 + 4 = 7 AP."""
        assert _calc_ap(40) == 7

    def test_piloting_15_floors_to_4(self):
        """piloting=15 → first round 4 AP (gain 4.5, the .5 carries)."""
        assert _calc_ap(15) == 4

    def test_ap_bonus(self):
        """Ace Pilot trait: +1."""
        assert _calc_ap(20, ap_bonus=1) == 6

    def test_min_1(self):
        """Negative piloting still gives at least 1 AP."""
        assert _calc_ap(-1000) == 1


class TestCalcApTenths:
    def test_gain_in_tenths(self):
        """piloting=15 → 4.5 AP per round = 45 tenths."""
        assert _calc_ap_tenths(15) == 45

    def test_baseline(self):
        """piloting=0 → 30 tenths (3.0 AP)."""
        assert _calc_ap_tenths(0) == 30

    def test_bonus_scales_by_ten(self):
        """Ace Pilot +1 AP = +10 tenths."""
        assert _calc_ap_tenths(20, ap_bonus=1) == 60

    def test_min_gain(self):
        """Negative piloting floors the gain at 1.0 AP."""
        assert _calc_ap_tenths(-1000) == 10


class TestRollAp:
    def test_integer_gain_no_carry(self):
        """A whole 5.0 gain spends 5 and carries nothing."""
        assert _roll_ap(0, 50) == (5, 0)

    def test_fractional_gain_carries(self):
        """4.5 gain spends 4 and banks 5 tenths."""
        assert _roll_ap(0, 45) == (4, 5)

    def test_carry_pays_out_next_round(self):
        """Banked 5 tenths + 4.5 gain → a 5-AP round."""
        assert _roll_ap(5, 45) == (5, 0)

    def test_carry_accumulates(self):
        """3 tenths banked + 4.4 gain → 4.7 spends 4, banks 7."""
        assert _roll_ap(3, 44) == (4, 7)

    def test_carry_cycle_averages_gain(self):
        """A 4.5 gain cycles 4,5,4,5 — averaging exactly 4.5 AP/round."""
        avail = []
        carry = 0
        for _ in range(8):
            _avail, carry = _roll_ap(carry, 45)
            avail.append(_avail)
        assert avail == [4, 5, 4, 5, 4, 5, 4, 5]

    def test_every_5_piloting_points_visible(self):
        """15 vs 10 piloting: 4.5 vs 4.0 average — one extra action per 2 rounds."""
        def _avg(piloting: int, rounds: int = 20) -> float:
            carry = 0
            total = 0
            for _ in range(rounds):
                _avail, carry = _roll_ap(carry, _calc_ap_tenths(piloting))
                total += _avail
            return total / rounds
        assert abs(_avg(15) - 4.5) < 0.001
        assert abs(_avg(10) - 4.0) < 0.001


class TestStartPlayerTurnCarry:
    def test_round_reset_rolls_carry(self):
        """start_player_turn rolls 4,5,4,5... for a 15-piloting pilot."""
        from src.spacehack.combat._actions import start_player_turn

        ps = {
            "piloting": 15,
            "ap_gain_tenths": 45,
            "ap_carry_tenths": 0,
            "ap_total": 4,
            "ap_remaining": 4,
            "power_pool": 10,
            "max_power": 10,
            "power_gen": 1,
            "max_shields": 0,
            "shields": 0,
            "engineering": 10,
            "shield_regen_rate": 0,
            "shield_recharge_bonus": 0,
        }
        avail = []
        for _ in range(6):
            start_player_turn(ps)
            avail.append(ps["ap_remaining"])
        assert avail == [4, 5, 4, 5, 4, 5]
        assert ps["ap_carry_tenths"] == 0

    def test_initial_state_matches_first_round(self):
        """init sets ap_total/ap_remaining to the same floor start_player_turn produces."""
        from src.spacehack.combat._actions import start_player_turn

        ps = {
            "piloting": 15,
            "ap_gain_tenths": 45,
            "ap_carry_tenths": 0,
            "ap_total": _calc_ap(15),
            "ap_remaining": _calc_ap(15),
            "power_pool": 10,
            "max_power": 10,
            "power_gen": 1,
            "max_shields": 0,
            "shields": 0,
            "engineering": 10,
            "shield_regen_rate": 0,
            "shield_recharge_bonus": 0,
        }
        start_player_turn(ps)
        assert ps["ap_remaining"] == 4
        assert ps["ap_total"] == 4
        assert ps["ap_carry_tenths"] == 5


# ---------------------------------------------------------------------------
# _calc_hull, _calc_max_hull, _calc_hull_for_enemy,
# _calc_power_gen, _calc_max_shields
# ---------------------------------------------------------------------------

_MOD_MOCK = SimpleNamespace(max_hull_bonus=5, power_gen_bonus=-1, max_shield_bonus=20,
                            gunnery_bonus=0, piloting_bonus=0, engineering_bonus=0,
                            shield_recharge_bonus=0)


class TestCalcHull:
    def test_full_hull(self):
        """0% damage → 100% of max."""
        cat = SimpleNamespace(base_hull=100)
        owned = SimpleNamespace(modules=(), hull_damage_pct=0)
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_hull(cat, owned) == 100

    def test_damaged(self):
        """50% damage → half hull."""
        cat = SimpleNamespace(base_hull=100)
        owned = SimpleNamespace(modules=(), hull_damage_pct=50)
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_hull(cat, owned) == 50

    def test_damaged_rounding(self):
        """33% damage: 100 * 67 // 100 = 67."""
        cat = SimpleNamespace(base_hull=100)
        owned = SimpleNamespace(modules=(), hull_damage_pct=33)
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_hull(cat, owned) == 67

    def test_min_1(self):
        """99% damage still leaves at least 1 HP."""
        cat = SimpleNamespace(base_hull=100)
        owned = SimpleNamespace(modules=(), hull_damage_pct=99)
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_hull(cat, owned) == 1

    def test_with_module_bonuses(self):
        """Module with max_hull_bonus=5 increases max hull."""
        cat = SimpleNamespace(base_hull=100)
        owned = SimpleNamespace(modules=("armor_plating",), hull_damage_pct=0)
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_hull(cat, owned) == 105


class TestCalcMaxHull:
    def test_base_only(self):
        cat = SimpleNamespace(base_hull=100)
        owned = SimpleNamespace(modules=())
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_max_hull(cat, owned) == 100

    def test_with_modules(self):
        cat = SimpleNamespace(base_hull=100)
        owned = SimpleNamespace(modules=("armor_plating",))
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_max_hull(cat, owned) == 105

    def test_default_fallback(self):
        """Uses 100 when catalog has no base_hull."""
        cat = SimpleNamespace()  # no base_hull attr
        owned = SimpleNamespace(modules=())
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_max_hull(cat, owned) == 100


class TestCalcHullForEnemy:
    def test_from_spec(self):
        """Enemy spec with ship_id pointing to a ship with base_hull=80."""
        enemy_spec = SimpleNamespace(ship_id="scout_a", modules=())
        with mock.patch(
            "src.spacehack.combat._stats._ship_mod.find_ship",
            return_value=SimpleNamespace(base_hull=80),
        ), mock.patch(
            "src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK,
        ):
            assert _calc_hull_for_enemy(enemy_spec) == 80

    def test_with_modules(self):
        enemy_spec = SimpleNamespace(ship_id="scout_a", modules=("armor_plating",))
        with mock.patch(
            "src.spacehack.combat._stats._ship_mod.find_ship",
            return_value=SimpleNamespace(base_hull=80),
        ), mock.patch(
            "src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK,
        ):
            assert _calc_hull_for_enemy(enemy_spec) == 85

    def test_missing_ship_fallback(self):
        """Unknown ship_id falls back to 100 base hull."""
        enemy_spec = SimpleNamespace(ship_id="nonexistent", modules=())
        with mock.patch(
            "src.spacehack.combat._stats._ship_mod.find_ship",
            side_effect=KeyError,
        ), mock.patch(
            "src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK,
        ):
            assert _calc_hull_for_enemy(enemy_spec) == 100


class TestCalcPowerGen:
    def test_base_only(self):
        cat = SimpleNamespace(base_power_gen=3)
        owned = SimpleNamespace(modules=())
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_power_gen(cat, owned) == 3

    def test_with_modules(self):
        """armor_plating has power_gen_bonus=-1."""
        cat = SimpleNamespace(base_power_gen=5)
        owned = SimpleNamespace(modules=("armor_plating",))
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_power_gen(cat, owned) == 4

    def test_negative_floor(self):
        """Power gen can't go below 0."""
        cat = SimpleNamespace(base_power_gen=0)
        owned = SimpleNamespace(modules=("armor_plating",))
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_power_gen(cat, owned) == 0


class TestCalcMaxShields:
    def test_no_shields(self):
        cat = SimpleNamespace(base_shield_max=0)
        owned = SimpleNamespace(modules=())
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_max_shields(cat, owned) == 0

    def test_with_modules(self):
        cat = SimpleNamespace(base_shield_max=10)
        owned = SimpleNamespace(modules=("shield_mk1",))
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_MOD_MOCK):
            assert _calc_max_shields(cat, owned) == 30


# ---------------------------------------------------------------------------
# _distance
# ---------------------------------------------------------------------------

class TestDistance:
    def test_same_point(self):
        assert _distance(Position(0, 0), Position(0, 0)) == 0.0

    def test_cardinal(self):
        assert _distance(Position(0, 0), Position(3, 0)) == 3.0

    def test_diagonal(self):
        dist = _distance(Position(0, 0), Position(3, 4))
        assert math.isclose(dist, 5.0)


# ---------------------------------------------------------------------------
# _player_free_regen, init_combat_state
# ---------------------------------------------------------------------------

_REGEN_MOD = SimpleNamespace(
    max_hull_bonus=0, power_gen_bonus=0, max_shield_bonus=0,
    gunnery_bonus=0, piloting_bonus=0, engineering_bonus=0,
    shield_recharge_bonus=3,
)


class TestPlayerFreeRegen:
    def test_ship_base_only(self):
        """Ship model's base_shield_recharge is free regen (no modules)."""
        cat = SimpleNamespace(base_shield_recharge=5)
        owned = SimpleNamespace(modules=())
        assert _player_free_regen(cat, owned) == 5

    def test_base_plus_module_bonus(self):
        """Base 5 + Shield Recharger +3 = 8 free regen."""
        cat = SimpleNamespace(base_shield_recharge=5)
        owned = SimpleNamespace(modules=("shield_recharger",))
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_REGEN_MOD):
            assert _player_free_regen(cat, owned) == 8

    def test_no_base_fallback(self):
        """Catalog without the field contributes 0."""
        cat = SimpleNamespace()
        owned = SimpleNamespace(modules=())
        assert _player_free_regen(cat, owned) == 0


class TestInitCombatState:
    """Combat state seeds the S-key rate at 0 and folds free regen in."""

    def _fixtures(self):
        cat = SimpleNamespace(
            base_hull=100, base_power_gen=3, base_shield_max=20,
            base_shield_recharge=5,
        )
        owned = SimpleNamespace(
            modules=("shield_recharger",), weapons=(), weapon_ammo={}, hull_damage_pct=0,
        )
        skills = PilotSkills(gunnery=10, piloting=10, engineering=10)
        enemy_spec = SimpleNamespace(
            id="e1", name="Pirate", char="P", fg=(255, 0, 0),
            ship_id="scout_a", faction="pirate", weapons=(), modules=(),
            min_power_gen=3, pilot_piloting=10, pilot_gunnery=10,
            pilot_engineering=10, ai_accuracy_bonus=0, ai_dodge_bonus=0,
        )
        return cat, owned, skills, enemy_spec

    def test_free_regen_folds_ship_base_and_module(self):
        """shield_recharge_bonus = ship base 5 + module 3; S rate starts 0."""
        cat, owned, skills, enemy_spec = self._fixtures()
        with mock.patch("src.spacehack.combat._stats.find_module_spec", return_value=_REGEN_MOD), mock.patch(
            "src.spacehack.combat._stats._ship_mod.find_ship",
            return_value=SimpleNamespace(base_hull=80),
        ):
            state, enemy = init_combat_state(
                cat, owned, Position(1, 2), skills, enemy_spec, Position(5, 5),
            )
        assert state["shield_recharge_bonus"] == 8
        assert state["shield_regen_rate"] == 0
        assert enemy.name == "Pirate"
