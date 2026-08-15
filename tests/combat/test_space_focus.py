"""Tests for the Focus trait — single-weapon space combat.

Focus is live while exactly one weapon is enabled: that weapon's AP,
power, and range double, and it deals double damage beyond half its
(doubled) range. The player controls the gate with the 1-9 weapon
toggles, so the trait is a per-round commitment like Charger/Deadshot.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.combat import _loop, _rules_space, _space_focus, _actions
from src.spacehack.combat._types import EnemyInstance


def _focus_fixture(*, traits=("focus",), active=(True,), weapons=("light_laser",)):
    """A minimal live space-combat state with the player at (0,0)."""
    _ctx = SimpleNamespace(
        player_traits=list(traits),
        player_counters=SimpleNamespace(
            laser_shots=0, missile_shots=0, plasma_shots=0, focused_shots=0,
        ),
        player=world.Entity("@", (255, 255, 255), world.Position(0, 0), "Player"),
        log=SimpleNamespace(
            add=lambda _message: None,
            add_colored=lambda _message, _color: None,
        ),
    )
    _tiles = [[world.DUNGEON_FLOOR for _ in range(11)] for _ in range(11)]
    _state = _rules_space.SpaceCombatState(
        ctx=_ctx,
        console=None,
        game_map=world.GameMap(11, 11, _tiles, []),
        log=None,
        player_state={
            "pos": world.Position(0, 0),
            "gunnery": 10,
            "ap_remaining": 8,
            "ap_total": 8,
            "power_pool": 20,
            "max_power": 20,
            "plasma_ap_discount": 0,
            "weapons": tuple(weapons),
            "weapon_ammo": {i: 4 for i in range(len(weapons))},
        },
        enemy_insts=[],
        weapons_list=list(weapons),
        active_weapons=list(active),
    )
    _old = _rules_space._state
    _rules_space._state = _state
    return _ctx, _state, _old


def _enemy(x: int = 6, *, hull: int = 100) -> EnemyInstance:
    return EnemyInstance(
        spec_id="pirate_scout", name="Pirate Scout", char="P",
        fg=(255, 100, 100), pos=world.Position(x, 0),
        hull=hull, max_hull=hull, shields=0, max_shields=0,
        pilot_piloting=0, cells_moved_this_turn=0,
    )


class TestIsFocusActive:
    def test_live_with_single_enabled_weapon(self):
        _ctx, _state, _old = _focus_fixture()
        try:
            assert _space_focus.is_focus_active(_ctx) is True
        finally:
            _rules_space._state = _old

    def test_off_with_two_weapons_enabled(self):
        _ctx, _state, _old = _focus_fixture(
            active=(True, True), weapons=("light_laser", "heavy_laser"),
        )
        try:
            assert _space_focus.is_focus_active(_ctx) is False
        finally:
            _rules_space._state = _old

    def test_off_with_all_weapons_disabled(self):
        _ctx, _state, _old = _focus_fixture(active=(False,))
        try:
            assert _space_focus.is_focus_active(_ctx) is False
        finally:
            _rules_space._state = _old

    def test_off_without_trait(self):
        _ctx, _state, _old = _focus_fixture(traits=())
        try:
            assert _space_focus.is_focus_active(_ctx) is False
        finally:
            _rules_space._state = _old

    def test_off_outside_combat(self):
        _old = _rules_space._state
        _rules_space._state = None
        try:
            assert _space_focus.is_focus_active(
                SimpleNamespace(player_traits=["focus"]),
            ) is False
        finally:
            _rules_space._state = _old


class TestCosts:
    def test_ap_cost_doubles_under_focus(self):
        _ctx, _state, _old = _focus_fixture()
        try:
            assert _space_focus.ap_cost("light_laser", _ctx) == 2
        finally:
            _rules_space._state = _old

    def test_ap_cost_base_without_focus(self):
        _ctx, _state, _old = _focus_fixture(traits=())
        try:
            assert _space_focus.ap_cost("light_laser", _ctx) == 1
        finally:
            _rules_space._state = _old

    def test_plasma_discount_applies_before_doubling(self):
        _ctx, _state, _old = _focus_fixture(
            traits=("focus", "plasma_savant"), weapons=("plasma_cannon",),
        )
        try:
            # plasma cannon AP 2 - Plasma Savant 1 = 1, doubled = 2.
            assert _space_focus.ap_cost("plasma_cannon", _ctx) == 2
        finally:
            _rules_space._state = _old

    def test_power_cost_doubles_energy_but_not_missiles(self):
        _ctx, _state, _old = _focus_fixture(weapons=("heavy_laser",))
        try:
            assert _space_focus.power_cost("heavy_laser", _ctx) == 4
        finally:
            _rules_space._state = _old
        _ctx2, _state2, _old2 = _focus_fixture(weapons=("heavy_missile",))
        try:
            assert _space_focus.power_cost("heavy_missile", _ctx2) == 0
        finally:
            _rules_space._state = _old2

    def test_range_profile_doubles_under_focus(self):
        _ctx, _state, _old = _focus_fixture()
        try:
            assert _space_focus.max_range("light_laser", _ctx) == 10
            assert _space_focus.min_range("light_laser", _ctx) == 2
        finally:
            _rules_space._state = _old

    def test_damage_band_starts_at_original_max_range(self):
        _ctx, _state, _old = _focus_fixture()
        try:
            # Half the doubled range is the original max range (5).
            assert _space_focus.damage_mult("light_laser", _ctx, 5) == 2.0
            assert _space_focus.damage_mult("light_laser", _ctx, 4.9) == 1.0
        finally:
            _rules_space._state = _old

    def test_missiles_share_the_damage_band(self):
        _ctx, _state, _old = _focus_fixture(weapons=("heavy_missile",))
        try:
            # Heavy missile: max 13, doubled 26, band starts at 13.
            assert _space_focus.damage_mult("heavy_missile", _ctx, 13) == 2.0
            assert _space_focus.damage_mult("heavy_missile", _ctx, 12) == 1.0
        finally:
            _rules_space._state = _old

    def test_no_doubling_for_unfocused_weapon(self):
        _ctx, _state, _old = _focus_fixture(
            active=(True, False), weapons=("light_laser", "heavy_laser"),
        )
        try:
            assert _space_focus.ap_cost("heavy_laser", _ctx) == 1
            assert _space_focus.power_cost("heavy_laser", _ctx) == 2
            assert _space_focus.max_range("heavy_laser", _ctx) == 5
        finally:
            _rules_space._state = _old


class TestRulesIntegration:
    def test_weapon_ap_cost_doubled(self):
        _ctx, _state, _old = _focus_fixture()
        try:
            assert _rules_space.weapon_ap_cost("light_laser", _ctx) == 2
        finally:
            _rules_space._state = _old

    def test_consume_shot_drains_double_power_and_counts_focused(self):
        _ctx, _state, _old = _focus_fixture()
        try:
            _rules_space.consume_shot(0, _ctx)
            assert _state.player_state["power_pool"] == 18
            assert _ctx.player_counters.focused_shots == 1
            assert _ctx.player_counters.laser_shots == 1
        finally:
            _rules_space._state = _old

    def test_consume_shot_normal_without_focus(self):
        _ctx, _state, _old = _focus_fixture(traits=())
        try:
            _rules_space.consume_shot(0, _ctx)
            assert _state.player_state["power_pool"] == 19
            assert _ctx.player_counters.focused_shots == 0
        finally:
            _rules_space._state = _old

    def test_can_fire_gates_on_doubled_costs(self):
        _ctx, _state, _old = _focus_fixture()
        try:
            _state.player_state["ap_remaining"] = 1
            _ok, _reason = _rules_space.can_fire(0, _ctx)
            assert (_ok, _reason) == (False, "Need 2 AP (have 1)")

            _state.player_state["ap_remaining"] = 2
            _state.player_state["power_pool"] = 1
            _ok, _reason = _rules_space.can_fire(0, _ctx)
            assert (_ok, _reason) == (False, "Need 2 power (have 1)")

            _state.player_state["power_pool"] = 2
            _ok, _reason = _rules_space.can_fire(0, _ctx)
            assert _ok is True
        finally:
            _rules_space._state = _old

    def test_damage_doubles_beyond_half_range(self, monkeypatch):
        _ctx, _state, _old = _focus_fixture(weapons=("heavy_laser",))
        monkeypatch.setattr(
            _actions, "RNG",
            SimpleNamespace(randint=lambda *_a: 50, uniform=lambda *_a: 1.0),
        )
        try:
            _enemy_far = _enemy(x=6)
            _dmg, _ = _rules_space.damage("heavy_laser", _enemy_far, _ctx)
            assert _dmg == 24  # 12 base, doubled at range 6

            _enemy_close = _enemy(x=4)
            _dmg, _ = _rules_space.damage("heavy_laser", _enemy_close, _ctx)
            assert _dmg == 12  # base damage inside the band
        finally:
            _rules_space._state = _old

    def test_hit_chance_uses_doubled_range(self, monkeypatch):
        _ctx, _state, _old = _focus_fixture()
        try:
            _enemy_far = _enemy(x=6)
            _hit_focus = _rules_space.hit_chance("light_laser", _enemy_far, _ctx)
            # Distance 6 is past light_laser's normal max (5), which would
            # take a -10% overshoot penalty without Focus.
            from src.spacehack.combat._stats import calc_hit_chance as _chc
            _hit_normal = _chc("light_laser", 10, 6.0, 0)
            assert _hit_focus == _hit_normal + 10  # no overshoot penalty
        finally:
            _rules_space._state = _old

    def test_full_fire_path_spends_doubled_ap_and_power(self, monkeypatch):
        _ctx, _state, _old = _focus_fixture()
        _state.enemy_insts.append(_enemy(x=6))
        monkeypatch.setattr(
            _actions, "RNG",
            SimpleNamespace(randint=lambda *_a: 1, uniform=lambda *_a: 1.0),
        )
        monkeypatch.setattr(_rules_space, "animate_fire", lambda *a, **k: None)
        try:
            _loop._handle_fire(None, _ctx, _state.game_map, _rules_space, target_idx=0)

            assert _rules_space.player_ap(_ctx) == 6  # 8 - 2 focused AP
            assert _state.player_state["power_pool"] == 18  # 20 - 2 focused power
            assert _ctx.player_counters.focused_shots == 1
            assert _ctx.player_counters.laser_shots == 1
        finally:
            _rules_space._state = _old

    def test_toggling_a_second_weapon_on_disables_focus(self):
        _ctx, _state, _old = _focus_fixture(
            active=(True, False), weapons=("light_laser", "heavy_laser"),
        )
        try:
            assert _space_focus.is_focus_active(_ctx) is True
            _state.active_weapons = [True, True]
            assert _space_focus.is_focus_active(_ctx) is False
        finally:
            _rules_space._state = _old
