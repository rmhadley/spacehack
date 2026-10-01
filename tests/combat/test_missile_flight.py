"""Missile flight (doc 57 phase 1) — the crossing-entity domain.

Pins the ruled rows (SETTLED 3/7), the advance math (SETTLED 1: hop,
re-vector, fuel, arrival/overshoot), the guidance roll at arrival
(SETTLED 5), the hard floor (SETTLED 2), interception through the
merged targeting space (SETTLED 6), the bookkeeping split (intercept
records NOTHING; arrival runs the full kill chain), the non-blocking
entity pin, and the every-end-path cleanup sweep.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.support.asyncutil import run

from src.spacehack import world
from src.spacehack.combat import _actions, _loop, _missile_flight, _rules_space
from src.spacehack.combat._missile_flight import (
    InFlightMissile,
    advance_step,
    guidance_hit_chance,
)
from src.spacehack.combat._types import CombatResult, EnemyInstance
from src.spacehack.data.quality import effective_ship_weapon_spec
from src.spacehack.data.weapons import find_weapon


# --- fixtures -----------------------------------------------------------------


class _Log:
    """Collecting log: every line lands in ``lines`` for asserts."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, message: str, **_kwargs) -> None:
        self.lines.append(message)

    def add_colored(self, message: str, _color, **_kwargs) -> None:
        self.lines.append(message)


def _fake_rng(*, roll: int = 1, spread: float = 1.0) -> SimpleNamespace:
    """A pinned RNG: every d100 rolls ``roll``, every variance draw is
    ``spread`` — hits land when the chance clears the roll."""
    return SimpleNamespace(
        randint=lambda _a, _b: roll, uniform=lambda _a, _b: spread,
    )


def _pin_rng(monkeypatch, *, roll: int = 1, spread: float = 1.0) -> None:
    """Pin every RNG read the arrival/intercept paths make — the
    call-time ``engine.RNG`` import and the module-bound copies
    (``_actions`` resolves damage; ``_loop`` rolls the hit)."""
    import src.spacehack.engine as _engine

    fake = _fake_rng(roll=roll, spread=spread)
    monkeypatch.setattr(_engine, "RNG", fake)
    monkeypatch.setattr(_actions, "RNG", fake)
    monkeypatch.setattr(_loop, "RNG", fake)


def _player_state(weapons: tuple[str, ...]) -> dict:
    return {
        "pos": world.Position(0, 0), "gunnery": 10, "piloting": 0,
        "ap_remaining": 8, "ap_total": 8,
        "ap_gain_twentieths": 60, "ap_carry_twentieths": 0,
        "power_pool": 20, "max_power": 20, "power_gen": 3,
        "plasma_ap_discount": 0,
        "hull": 100, "max_hull": 100, "shields": 0, "max_shields": 0,
        "shield_regen_rate": 0, "shield_recharge_bonus": 0,
        "cells_moved_this_turn": 0,
        "weapons": tuple(weapons),
        "weapon_ammo": {i: 4 for i in range(len(weapons))},
    }


def _flight_fixture(
    *, weapons: tuple[str, ...] = ("heavy_missile",),
    enemy_at: tuple[int, int] = (6, 0), enemy_hull: int = 40,
    traits: tuple[str, ...] = (),
):
    """A minimal live space-combat state: player at (0,0), one enemy,
    open floor."""
    _log = _Log()
    _ctx = SimpleNamespace(
        player_traits=list(traits),
        player_counters=SimpleNamespace(
            laser_shots=0, missile_shots=0, plasma_shots=0, focused_shots=0,
            total_kills=0, total_damage_taken=0, explosive_hits=0,
        ),
        player=world.Entity("@", (255, 255, 255), world.Position(0, 0), "Player"),
        log=_log, player_owned_ship=None,
    )
    _tiles = [[world.DUNGEON_FLOOR for _ in range(15)] for _ in range(11)]
    _map = world.GameMap(15, 11, _tiles, [])
    _enemy = EnemyInstance(
        spec_id="pirate_scout", name="Pirate Scout", char="P",
        fg=(255, 100, 100), pos=world.Position(*enemy_at),
        hull=enemy_hull, max_hull=enemy_hull, shields=0, max_shields=0,
        pilot_piloting=0, cells_moved_this_turn=0,
    )
    _state = _rules_space.SpaceCombatState(
        ctx=_ctx, console=None, game_map=_map, log=_log,
        player_state=_player_state(weapons),
        enemy_insts=[_enemy], enemy_specs=[], enemy_ents={},
        weapons_list=list(weapons), active_weapons=[True] * len(weapons),
        weapon_qualities=[0] * len(weapons),
        cr=CombatResult(),
    )
    _old = _rules_space._state
    _rules_space._state = _state
    return _ctx, _state, _old


def _patch_flights(monkeypatch) -> list:
    """No-op the render/explosion beats; record kill-chain calls."""
    calls: list = []

    async def _no_render(*_a, **_kw):
        pass

    async def _no_explosion(*_a, **_kw):
        pass

    async def _record_kill(state, game_map, enemy, ctx):
        calls.append((state, game_map, enemy, ctx))

    import src.spacehack.combat._space_kills as _kills

    monkeypatch.setattr(_missile_flight, "_render_hop_frame", _no_render)
    monkeypatch.setattr(_kills, "_animate_kill_explosion", _no_explosion)
    monkeypatch.setattr(_kills, "on_kill", _record_kill)
    return calls


# --- spec pins (SETTLED 3/7) ---------------------------------------------------


class TestSpecPins:
    def test_light_missile_ruled_row(self):
        ws = find_weapon("light_missile")
        assert (ws.damage, ws.min_range, ws.max_range) == (28, 4, 9)
        assert (ws.missile_hp, ws.flight_speed) == (2, 4)

    def test_heavy_missile_ruled_row(self):
        ws = find_weapon("heavy_missile")
        assert (ws.damage, ws.min_range, ws.max_range) == (64, 5, 13)
        assert (ws.missile_hp, ws.flight_speed) == (6, 2)

    def test_emp_stays_instant_and_uninterceptible(self):
        ws = find_weapon("emp_missile")
        assert ws.flight_speed == 0 and ws.missile_hp == 0
        assert ws.shield_strip_pct == 100 and ws.damage == 0
        assert ws.ammo_capacity == 2  # hard-capped (doc 56 SETTLED 35)

    def test_is_flight_weapon_branches_on_flight_speed_alone(self):
        assert _missile_flight.is_flight_weapon("light_missile") is True
        assert _missile_flight.is_flight_weapon("heavy_missile") is True
        assert _missile_flight.is_flight_weapon("emp_missile") is False
        assert _missile_flight.is_flight_weapon("light_laser") is False
        assert _missile_flight.is_flight_weapon("nope") is False


# --- advance-step math (SETTLED 1: pure) ---------------------------------------


class TestAdvanceStep:
    def test_hop_moves_speed_cells_toward_target(self):
        step = advance_step(
            world.Position(0, 0), world.Position(6, 0), speed=2, fuel=13,
        )
        assert step.path == ((1, 0), (2, 0))
        assert step.arrived is False and step.fuel_exhausted is False

    def test_revector_bends_toward_the_live_position(self):
        # The round's track is computed to where the target sits NOW —
        # a target that slipped north bends the hop north.
        step = advance_step(
            world.Position(0, 0), world.Position(4, 4), speed=2, fuel=13,
        )
        assert step.path == ((1, 1), (2, 2))

    def test_fuel_caps_the_hop_short_of_the_target(self):
        step = advance_step(
            world.Position(0, 0), world.Position(6, 0), speed=4, fuel=2,
        )
        assert step.path == ((1, 0), (2, 0))
        assert step.arrived is False and step.fuel_exhausted is True

    def test_arrival_detection(self):
        step = advance_step(
            world.Position(0, 0), world.Position(3, 0), speed=4, fuel=13,
        )
        assert step.path == ((1, 0), (2, 0), (3, 0))
        assert step.arrived is True and step.fuel_exhausted is False

    def test_overshoot_never_passes_the_target(self):
        step = advance_step(
            world.Position(0, 0), world.Position(3, 0), speed=10, fuel=99,
        )
        assert step.path[-1] == (3, 0) and step.arrived is True

    def test_on_the_target_is_arrival(self):
        step = advance_step(
            world.Position(3, 0), world.Position(3, 0), speed=2, fuel=5,
        )
        assert step.path == () and step.arrived is True

    def test_dry_tank_short_of_the_target_is_exhaustion(self):
        step = advance_step(
            world.Position(0, 0), world.Position(6, 0), speed=4, fuel=0,
        )
        assert step.path == () and step.fuel_exhausted is True


# --- the guidance roll (SETTLED 5: pure) ---------------------------------------


class TestGuidanceRoll:
    def test_formula_is_accuracy_gunnery_minus_dodge_clamped(self):
        # 72 (quality-scaled launcher accuracy) + 10//2 - 0 = 77
        assert guidance_hit_chance("heavy_missile", 10, 0) == 77

    def test_dodge_at_arrival_subtracts(self):
        assert guidance_hit_chance("heavy_missile", 10, 30) == 47

    def test_hit_bonus_folds_in(self):
        assert guidance_hit_chance("heavy_missile", 10, 0, 10) == 87

    def test_clamped_both_ends(self):
        assert guidance_hit_chance("heavy_missile", 200, 0) == 95
        assert guidance_hit_chance("emp_missile", 0, 100) == 5

    def test_no_range_terms(self):
        # Distance never enters: the roll is identical point-blank and
        # at max range (range was paid at launch).
        assert (
            guidance_hit_chance("heavy_missile", 10, 0)
            == guidance_hit_chance("heavy_missile", 10, 0)
        )
        import inspect
        assert "dist" not in inspect.signature(guidance_hit_chance).parameters

    def test_quality_scales_the_accuracy_term(self):
        _base = effective_ship_weapon_spec("heavy_missile", 0).accuracy
        _tier = effective_ship_weapon_spec("heavy_missile", 3).accuracy
        expected = max(5, min(95, _tier + 5))
        assert guidance_hit_chance("heavy_missile", 10, 0, weapon_quality=3) == expected
        assert _tier >= _base  # tier never degrades the launcher


# --- spawn + merged targeting (SETTLED 6) --------------------------------------


class TestSpawnAndMergedSpace:
    def test_launch_mounts_a_non_blocking_entity_and_lines(self):
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            assert _state.in_flight == [_missile]
            assert _missile.ent in _state.game_map.entities
            assert _missile.ent.non_blocking is True
            assert _missile.ent.char == "♦"   # family by shape (SETTLED 10)
            assert _missile.ent.fg == _missile_flight.PLAYER_FG
            assert (_missile.hull, _missile.max_hull, _missile.fuel) == (6, 6, 13)
            assert _ctx.log.lines == ["Heavy missile away."]
        finally:
            _rules_space._state = _old

    def test_light_missile_glyph_is_the_star(self):
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "light_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            assert _missile.ent.char == "*"
            assert _ctx.log.lines == ["Light missile away."]
        finally:
            _rules_space._state = _old

    def test_targetables_orders_ships_then_missiles(self):
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            merged = _rules_space.targetables(None)
            assert len(merged) == 2
            assert merged[0] is _state.enemy_insts[0]
            assert merged[1] is _state.in_flight[0]
            # Every other index-space reader stays ships-only.
            assert _rules_space.get_enemies(None) == [_state.enemy_insts[0]]
        finally:
            _rules_space._state = _old


# --- the hard floor (SETTLED 2) -------------------------------------------------


class TestFloorGate:
    def test_heavy_refused_inside_five(self):
        _ctx, _state, _old = _flight_fixture(enemy_at=(4, 0))  # dist 4
        try:
            assert _rules_space.can_fire(0, _ctx) == (
                False, "Target inside minimum range.",
            )
        finally:
            _rules_space._state = _old

    def test_heavy_fires_at_the_floor(self):
        _ctx, _state, _old = _flight_fixture(enemy_at=(5, 0))  # dist 5
        try:
            assert _rules_space.can_fire(0, _ctx) == (True, "")
        finally:
            _rules_space._state = _old

    def test_light_refused_inside_four(self):
        _ctx, _state, _old = _flight_fixture(
            weapons=("light_missile",), enemy_at=(3, 0),  # dist 3
        )
        try:
            assert _rules_space.can_fire(0, _ctx) == (
                False, "Target inside minimum range.",
            )
        finally:
            _rules_space._state = _old

    def test_light_fires_at_the_floor(self):
        _ctx, _state, _old = _flight_fixture(
            weapons=("light_missile",), enemy_at=(4, 0),  # dist 4
        )
        try:
            assert _rules_space.can_fire(0, _ctx) == (True, "")
        finally:
            _rules_space._state = _old

    def test_non_flight_weapons_are_never_floor_refused(self):
        # The laser penalty path is untouched: no distance ever refuses
        # a non-flight rack (the EMP proxy pins it inside its own min).
        _ctx, _state, _old = _flight_fixture(
            weapons=("emp_missile", "light_laser"), enemy_at=(1, 0),
        )
        try:
            assert _rules_space.can_fire(0, _ctx) == (True, "")   # EMP, min 2
            assert _rules_space.can_fire(1, _ctx) == (True, "")   # laser
        finally:
            _rules_space._state = _old

    def test_emp_keeps_penalty_semantics_inside_its_min(self):
        # EMP is not a flight weapon: dist 1 sits inside its min 2 and
        # the rack still fires (the accuracy penalty, not a refusal).
        _ctx, _state, _old = _flight_fixture(
            weapons=("emp_missile",), enemy_at=(1, 0),
        )
        try:
            assert _rules_space.can_fire(0, _ctx) == (True, "")
        finally:
            _rules_space._state = _old

    def test_focus_never_widens_the_refusal_band(self):
        _ctx, _state, _old = _flight_fixture(
            weapons=("heavy_missile",), enemy_at=(6, 0), traits=("focus",),
        )
        try:
            from src.spacehack.combat import _space_focus
            assert _space_focus.min_range("heavy_missile", _ctx) == 10
            assert _rules_space.can_fire(0, _ctx) == (True, "")
        finally:
            _rules_space._state = _old


# --- interception (SETTLED 6/7 + the bookkeeping split) -------------------------


class TestInterception:
    def test_volley_damage_chips_missile_hp_and_kills(self):
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = InFlightMissile(
                weapon_id="heavy_missile", pos=world.Position(1, 0),
                hull=6, max_hull=6, name="Heavy Missile",
            )
            _dmg, _ = _rules_space.damage("light_laser", _missile, _ctx, 0)
            assert 0 < _dmg < 6 and _missile.alive is True
            _rules_space.damage("heavy_laser", _missile, _ctx, 0)
            assert _missile.hull <= 0 and _missile.alive is False
        finally:
            _rules_space._state = _old

    def test_strip_weapons_do_nothing_by_construction(self):
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = InFlightMissile(
                weapon_id="heavy_missile", pos=world.Position(1, 0),
                hull=6, max_hull=6, name="Heavy Missile",
            )
            _dmg, _ = _rules_space.damage("emp_missile", _missile, _ctx, 0)
            assert _dmg == 0
            assert (_missile.hull, _missile.shields) == (6, 0)
        finally:
            _rules_space._state = _old

    def test_intercept_kill_never_reaches_the_kill_chain(self, monkeypatch):
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            run(_missile_flight.finish_intercept(
                _state, _ctx, _state.game_map, _missile,
            ))
            assert "Missile destroyed." in _ctx.log.lines
            assert _missile not in _state.in_flight
            assert _missile.ent not in _state.game_map.entities
            assert _calls == []          # no XP, loot, or reputation
            assert _state.cr.defeated_names == []
        finally:
            _rules_space._state = _old

    def test_flak_volley_through_the_shared_loop(self, monkeypatch):
        # TAB onto the inbound, F: the volley applies member damage to
        # missile_hp, the killing shot takes the intercept branch.
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(weapons=("light_laser",))
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "light_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            _pin_rng(monkeypatch, roll=50)  # 50 <= 85%: the flak shot lands

            async def _no_anim(*_a, **_kw):
                pass

            monkeypatch.setattr(_rules_space, "animate_fire", _no_anim)
            _state.target_idx = 1  # the missile in the merged space
            run(_loop._handle_fire(None, _ctx, _state.game_map, _rules_space, 1))
            assert "Missile destroyed." in _ctx.log.lines
            assert _missile not in _state.in_flight
            assert _calls == []
            assert _state.player_state["ap_remaining"] == 7  # 1 AP flak shot
        finally:
            _rules_space._state = _old


# --- arrival (SETTLED 1/5) -------------------------------------------------------


class TestArrival:
    def test_advance_hops_renders_and_burns_fuel(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert (_missile.pos.x, _missile.pos.y) == (2, 0)  # speed 2
            assert _missile.fuel == 11
            assert _missile.ent.pos == _missile.pos
        finally:
            _rules_space._state = _old

    def test_arrival_miss_is_a_harmless_detonation(self, monkeypatch):
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(1, 0))
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            _pin_rng(monkeypatch, roll=99)  # 99 > 77%: guidance misses
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert "Missile detonates short." in _ctx.log.lines
            assert _state.enemy_insts[0].hull == 40  # zero damage
            assert _missile not in _state.in_flight
            assert _calls == []
        finally:
            _rules_space._state = _old

    def test_arrival_hit_ride_the_resolve_path(self, monkeypatch):
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(1, 0), enemy_hull=100)
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            _pin_rng(monkeypatch, roll=50, spread=1.0)  # mult 1.0: full 64
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            _enemy = _state.enemy_insts[0]
            assert _enemy.hull == 100 - 64  # the doubled base through quality
            assert _enemy.alive is True and _calls == []
        finally:
            _rules_space._state = _old

    def test_arrival_kill_runs_the_full_kill_chain(self, monkeypatch):
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(1, 0), enemy_hull=40)
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            _pin_rng(monkeypatch, roll=50, spread=1.0)
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            _enemy = _state.enemy_insts[0]
            assert _enemy.alive is False
            assert "Pirate Scout destroyed!" in _ctx.log.lines
            assert len(_calls) == 1 and _calls[0][2] is _enemy  # on_kill
        finally:
            _rules_space._state = _old

    def test_arrival_at_a_missile_takes_the_intercept_branch(self, monkeypatch):
        # A flight rack fired at a crossing MISSILE (the merged fire
        # path allows it): arrival destroys ordnance through the
        # intercept bookkeeping — never the ship kill chain, no crash
        # on a spec_id that ordnance does not have.
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", None,  # target patched below
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            _target_missile = InFlightMissile(
                weapon_id="light_missile", pos=world.Position(2, 0),
                hull=2, max_hull=2, name="Light Missile",
            )
            _target_missile.ent = world.Entity(
                "*", _missile_flight.PLAYER_FG, world.Position(2, 0),
                non_blocking=True,
            )
            _state.game_map.entities.append(_target_missile.ent)
            _state.in_flight.append(_target_missile)  # after the attacker
            _missile.target = _target_missile
            _pin_rng(monkeypatch, roll=50, spread=1.0)  # guidance hits
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert "Missile destroyed." in _ctx.log.lines
            assert _target_missile not in _state.in_flight
            assert _target_missile.ent not in _state.game_map.entities
            assert _calls == []  # intercept bookkeeping only
            assert _missile not in _state.in_flight  # spent on impact
        finally:
            _rules_space._state = _old

    def test_dead_target_dissipates_the_missile_silently(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            _state.enemy_insts[0].alive = False
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert _missile not in _state.in_flight
            assert _missile.ent not in _state.game_map.entities
            assert _ctx.log.lines == ["Heavy missile away."]  # silent dissipate
        finally:
            _rules_space._state = _old

    def test_kiting_can_exhaust_the_fuel(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(10, 0))
        try:
            _missile = InFlightMissile(
                weapon_id="light_missile", pos=world.Position(0, 0),
                target=_state.enemy_insts[0],
                hull=2, max_hull=2, fuel=5, flight_speed=4,
                name="Light Missile",
            )
            _missile.ent = world.Entity(
                "*", _missile_flight.PLAYER_FG, world.Position(0, 0),
                non_blocking=True,
            )
            _state.game_map.entities.append(_missile.ent)
            _state.in_flight.append(_missile)
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert (_missile.pos.x, _missile.pos.y) == (4, 0) and _missile.fuel == 1
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert "Missile exhausts its fuel." in _ctx.log.lines
            assert _missile not in _state.in_flight  # short of the target at 10
        finally:
            _rules_space._state = _old


# --- launch through the shared fire path ------------------------------------------


class TestLaunchPath:
    def test_flight_member_launches_instead_of_resolving(self, monkeypatch):
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(6, 0))
        try:
            _hit, _ap = run(_loop._fire_weapon(
                None, _ctx, _state.game_map, _rules_space, 0,
                _state.enemy_insts[0], _state.player_state["pos"],
            ))
            assert _hit is False and _ap == 2   # volley costs paid at launch
            assert _ctx.log.lines == ["Heavy missile away."]
            assert _state.enemy_insts[0].hull == 40  # nothing resolved yet
            assert len(_state.in_flight) == 1
            assert _state.player_state["weapon_ammo"][0] == 3  # round spent
            assert _ctx.player_counters.missile_shots == 1
            assert _calls == []
        finally:
            _rules_space._state = _old

    def test_emp_rides_the_instant_path(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(weapons=("emp_missile",))
        try:
            _state.enemy_insts[0].shields = 20

            async def _no_anim(*_a, **_kw):
                pass

            monkeypatch.setattr(_rules_space, "animate_fire", _no_anim)
            _pin_rng(monkeypatch, roll=1)
            run(_loop._fire_weapon(
                None, _ctx, _state.game_map, _rules_space, 0,
                _state.enemy_insts[0], _state.player_state["pos"],
            ))
            assert _state.in_flight == []          # no entity ever spawns
            assert _state.enemy_insts[0].shields == 0  # instant strip
        finally:
            _rules_space._state = _old


# --- board denial + end check -------------------------------------------------------


class TestBoardAndEndCheck:
    def test_d_on_a_missile_target_denies(self):
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            _state.target_idx = 1  # the missile
            assert _rules_space.try_board(_ctx, _state.game_map, 1) is False
            assert "Nothing to board." in _ctx.log.lines
        finally:
            _rules_space._state = _old

    def test_end_check_ignores_live_missiles(self):
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            _state.enemy_insts[0].alive = False
            assert _rules_space.get_enemies(_ctx) == []
            assert _rules_space.combat_should_end(
                _ctx, _state.game_map, _rules_space.get_enemies(_ctx),
            ) is True  # VICTORY with the missile still crossing
        finally:
            _rules_space._state = _old


# --- the non-blocking entity pin ------------------------------------------------------


class TestNonBlocking:
    def _map_with_missile(self):
        _tiles = [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(3)]
        _map = world.GameMap(5, 3, _tiles, [])
        _map.entities.append(world.Entity(
            "♦", (255, 80, 80), world.Position(1, 0),
            non_blocking=True,
        ))
        return _map

    def test_blocking_entity_at_skips_missiles(self):
        assert self._map_with_missile().blocking_entity_at(1, 0) is None

    def test_movement_walks_through_a_missile_cell(self):
        _new, _ok = _actions.move_entity(
            world.Position(0, 0), 1, 0, self._map_with_missile(),
        )
        assert _ok is True and (_new.x, _new.y) == (1, 0)

    def test_pathfinding_routes_through_a_missile_cell(self):
        _path = world.find_path(
            (0, 0), {(3, 0)}, self._map_with_missile(),
        )
        assert _path is not None and (1, 0) in _path


# --- the cleanup sweep (every end path) ----------------------------------------------


class TestCleanupSweep:
    def test_sync_state_sweeps_flights_and_entities(self):
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            _rules_space.sync_state(_ctx)
            assert _state.in_flight == []
            assert _missile.ent not in _state.game_map.entities
            assert _state.active is False
        finally:
            _rules_space._state = _old

    def test_activate_combat_state_sweeps_a_leftover_fight(self):
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = _missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            )
            _map = _state.game_map
            _rules_space._activate_combat_state(
                _ctx, None, _map, _state.log,
                _player_state(("light_laser",)), [], [], {}, None,
                ["light_laser"], [True],
            )
            assert _missile.ent not in _map.entities
            assert _rules_space._state.in_flight == []
            assert _rules_space._state is not _state
        finally:
            _rules_space._state = _old
