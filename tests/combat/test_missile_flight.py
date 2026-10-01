"""Missile flight (doc 57, SETTLED 11 flight model v2) — the
crossing-entity domain.

Pins the ruled rows (SETTLED 3/7), the v2 deploy-stagger-mini-turn
cycle: spawn near the shooter (never on it), the launch half-move,
the shooter's mini-turn one missile at a time, same-shooter avoidance,
contact detonation on any ship (full damage on contact — ruling),
harmless terrain detonation, the guidance roll (SETTLED 5), the hard
floor (SETTLED 2), interception through the merged targeting space
(SETTLED 6), the bookkeeping split (flak kills ordnance never touches
on_kill; any SHIP kill runs the full chain), the non-blocking entity
pin, and the every-end-path cleanup sweep.
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
    """Pin every RNG read the contact paths make — the call-time
    ``engine.RNG`` import and the module-bound copies (``_actions``
    resolves damage; ``_loop`` rolls the flak hit)."""
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


def _manual_missile(
    state, at: tuple[int, int], target, *, weapon_id: str = "heavy_missile",
    fuel: int | None = None, speed: int | None = None, side: str = "player",
) -> InFlightMissile:
    """Mount a missile by hand (movement-rule tests): no launch line,
    no spawn logic — the rules under test start at the first move."""
    _ws = find_weapon(weapon_id)
    _missile = InFlightMissile(
        weapon_id=weapon_id, pos=world.Position(*at), target=target,
        side=side, hull=_ws.missile_hp, max_hull=_ws.missile_hp,
        fuel=_ws.max_range if fuel is None else fuel,
        flight_speed=_ws.flight_speed if speed is None else speed,
        name=_ws.name,
        char=_missile_flight._GLYPH_BY_WEAPON.get(weapon_id, "*"),
        fg=_missile_flight.PLAYER_FG if side == "player" else _missile_flight.HOSTILE_FG,
    )
    _missile.ent = world.Entity(
        _missile.char, _missile.fg, _missile.pos, non_blocking=True,
    )
    state.game_map.entities.append(_missile.ent)
    state.in_flight.append(_missile)
    return _missile


def _patch_flights(monkeypatch) -> list:
    """No-op the render/explosion/death beats; record kill-chain calls."""
    calls: list = []

    async def _no_render(*_a, **_kw):
        pass

    async def _no_explosion(*_a, **_kw):
        pass

    async def _record_kill(state, game_map, enemy, ctx):
        calls.append((state, game_map, enemy, ctx))

    async def _no_death(*_a, **_kw):
        pass

    import src.spacehack.combat._ai as _ai_mod
    import src.spacehack.combat._space_kills as _kills

    monkeypatch.setattr(_missile_flight, "_render_hop_frame", _no_render)
    monkeypatch.setattr(_kills, "_animate_kill_explosion", _no_explosion)
    monkeypatch.setattr(_kills, "on_kill", _record_kill)
    monkeypatch.setattr(_ai_mod, "_present_ship_destruction", _no_death)
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
        # Distance never enters: the roll is identical at any standoff
        # (range was paid at launch).
        import inspect
        assert "dist" not in inspect.signature(guidance_hit_chance).parameters

    def test_quality_scales_the_accuracy_term(self):
        _base = effective_ship_weapon_spec("heavy_missile", 0).accuracy
        _tier = effective_ship_weapon_spec("heavy_missile", 3).accuracy
        expected = max(5, min(95, _tier + 5))
        assert guidance_hit_chance("heavy_missile", 10, 0, weapon_quality=3) == expected
        assert _tier >= _base  # tier never degrades the launcher


# --- deploy: spawn near the shooter + the launch half-move (11.2-5) --------------


class TestDeploy:
    def test_appears_near_you_but_not_on_you_then_half_moves(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()  # enemy at (6,0)
        try:
            _missile = run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            assert _missile.ent in _state.game_map.entities
            assert _missile.ent.non_blocking is True
            assert (_missile.pos.x, _missile.pos.y) == (2, 0)  # spawn (1,0) + half 1
            assert _missile.ent.pos == _missile.pos
            assert (_missile.hull, _missile.max_hull, _missile.fuel) == (6, 6, 12)
            assert _ctx.log.lines == ["Heavy missile away."]
        finally:
            _rules_space._state = _old

    def test_light_deploys_half_of_four(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(
            weapons=("light_missile",),
        )
        try:
            _missile = run(_missile_flight.spawn_flight_missile(
                _state, "light_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            assert (_missile.pos.x, _missile.pos.y) == (3, 0)  # (1,0) + half 2
            assert _missile.ent.char == "*"  # family by shape (SETTLED 10)
            assert _missile.fuel == 7
            assert _ctx.log.lines == ["Light missile away."]
        finally:
            _rules_space._state = _old

    def test_volley_members_stagger_and_never_stack(self, monkeypatch):
        # SETTLED 11.1-6: two heavies deploy one after the other; the
        # second sees the first's rest position on its track and
        # sidesteps — distinct cells, both alive.
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            _a = run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            _b = run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            assert (_a.pos.x, _a.pos.y) == (2, 0)
            assert (_b.pos.x, _b.pos.y) == (2, 1)  # avoided A's cell
            assert _a is not _b and _a.alive and _b.alive
        finally:
            _rules_space._state = _old

    def test_launch_half_move_clips_an_adjacent_enemy(self, monkeypatch):
        # Enemy within half-move reach of the shooter: the deploy
        # stagger can't clear it — contact at launch (full damage on
        # contact, SETTLED 11.7).
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(2, 0), enemy_hull=100)
        try:
            _pin_rng(monkeypatch, roll=50, spread=1.0)
            _missile = run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            assert _missile not in _state.in_flight   # warhead spent at launch
            assert _state.enemy_insts[0].hull == 36   # 100 - 64 on contact
        finally:
            _rules_space._state = _old

    def test_targetables_orders_ships_then_missiles(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
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
            _missile = run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
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
            run(_missile_flight.spawn_flight_missile(
                _state, "light_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            _pin_rng(monkeypatch, roll=50)  # 50 <= 85%: the flak shot lands

            async def _no_anim(*_a, **_kw):
                pass

            monkeypatch.setattr(_rules_space, "animate_fire", _no_anim)
            run(_loop._handle_fire(None, _ctx, _state.game_map, _rules_space, 1))
            assert "Missile destroyed." in _ctx.log.lines
            assert _state.in_flight == []
            assert _calls == []
            assert _state.player_state["ap_remaining"] == 7  # 1 AP flak shot
        finally:
            _rules_space._state = _old


# --- the shooter's mini-turn + contact rules (SETTLED 11.6-9) --------------------


class TestMiniTurn:
    def test_full_move_at_the_start_of_the_shooters_turn(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()  # enemy at (6,0)
        try:
            _missile = run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            assert (_missile.pos.x, _missile.pos.y) == (2, 0)  # launch half-move
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert (_missile.pos.x, _missile.pos.y) == (4, 0)  # full speed 2
            assert _missile.fuel == 10
        finally:
            _rules_space._state = _old

    def test_contact_with_the_target_arrives_through_guidance(
        self, monkeypatch,
    ):
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(3, 0), enemy_hull=100)
        try:
            run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            _pin_rng(monkeypatch, roll=50, spread=1.0)  # mult 1.0: full 64
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            _enemy = _state.enemy_insts[0]
            assert _enemy.hull == 100 - 64  # the doubled base through quality
            assert _enemy.alive is True and _calls == []
            assert _state.in_flight == []   # the warhead is spent
        finally:
            _rules_space._state = _old

    def test_contact_miss_is_a_harmless_detonation(self, monkeypatch):
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(3, 0))
        try:
            run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            _pin_rng(monkeypatch, roll=99)  # 99 > 77%: guidance misses
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert "Missile detonates short." in _ctx.log.lines
            assert _state.enemy_insts[0].hull == 40  # zero damage
            assert _state.in_flight == []
            assert _calls == []
        finally:
            _rules_space._state = _old

    def test_contact_kill_runs_the_full_kill_chain(self, monkeypatch):
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(3, 0), enemy_hull=40)
        try:
            run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            _pin_rng(monkeypatch, roll=50, spread=1.0)
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            _enemy = _state.enemy_insts[0]
            assert _enemy.alive is False
            assert "Pirate Scout destroyed!" in _ctx.log.lines
            assert len(_calls) == 1 and _calls[0][2] is _enemy  # on_kill
        finally:
            _rules_space._state = _old

    def test_contact_with_a_non_target_deals_full_damage(self, monkeypatch):
        # SETTLED 11.7, ruling: full damage on contact, target or not.
        # An escort stands on the track; the target stands beyond it.
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(8, 0), enemy_hull=90)
        try:
            _escort = EnemyInstance(
                spec_id="escort", name="Escort", char="E",
                fg=(255, 100, 100), pos=world.Position(2, 0),
                hull=50, max_hull=50, shields=0, max_shields=0,
                pilot_piloting=0, cells_moved_this_turn=0,
            )
            _state.enemy_insts.append(_escort)
            _pin_rng(monkeypatch, roll=50, spread=1.0)
            _missile = run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            assert _missile not in _state.in_flight   # spent on the escort
            assert _escort.alive is False  # the escort ate the warhead
            assert len(_calls) == 1 and _calls[0][2] is _escort  # full chain
            assert _state.enemy_insts[0].hull == 90  # the target untouched
        finally:
            _rules_space._state = _old

    def test_self_splash_damages_and_can_defeat_the_player(self, monkeypatch):
        # The player's own hull is a ship (SETTLED 11.7): a track that
        # clips it detonates on it — DEFEAT included.
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(2, 0))
        try:
            _state.player_state["pos"] = world.Position(4, 0)
            _state.player_state["hull"] = 10
            _missile = _manual_missile(_state, (6, 0), _state.enemy_insts[0])
            _pin_rng(monkeypatch, roll=50, spread=1.0)
            _outcome = run(_missile_flight.advance_flights(
                _state, _ctx, _state.game_map,
            ))
            assert _outcome == "DEFEAT"
            assert _state.player_state["hull"] <= 0
            assert _state.last_attacker == "Your own Heavy Missile"
            assert "detonates on your own hull" in " ".join(_ctx.log.lines)
            assert _missile not in _state.in_flight
        finally:
            _rules_space._state = _old

    def test_terrain_collision_detonates_harmlessly(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(5, 0))
        try:
            _state.game_map.tiles[0][2] = world.WALL  # planet hull on the track
            _missile = _manual_missile(_state, (1, 0), _state.enemy_insts[0])
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert "Missile detonates short." in _ctx.log.lines
            assert _missile not in _state.in_flight
            assert _missile.ent not in _state.game_map.entities
            assert (_missile.pos.x, _missile.pos.y) == (1, 0)  # never entered
            assert _state.enemy_insts[0].alive is True
        finally:
            _rules_space._state = _old

    def test_same_shooter_missiles_are_actively_avoided(self, monkeypatch):
        # SETTLED 11.6: A rests (dry tank) on B's track; B sidesteps to
        # the best progress-preserving free neighbor — never A's cell.
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(6, 0))
        try:
            _a = _manual_missile(
                _state, (3, 0), _state.enemy_insts[0], fuel=0,
            )  # dry: immobile blocker
            _b = _manual_missile(_state, (1, 0), _state.enemy_insts[0])
            run(_missile_flight._travel(
                _state, _ctx, _state.game_map, _b, _b.flight_speed,
            ))
            assert (_a.pos.x, _a.pos.y) == (3, 0)   # A never moved
            assert (_b.pos.x, _b.pos.y) == (3, 1)   # B sidestepped around A
            assert _a.alive and _b.alive
        finally:
            _rules_space._state = _old

    def test_boxed_missile_holds_station_without_burning_fuel(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(6, 0))
        try:
            _a = _manual_missile(
                _state, (2, 0), _state.enemy_insts[0], fuel=0,
            )  # dry: immobile blocker
            _b = _manual_missile(_state, (1, 0), _state.enemy_insts[0])
            # Box B in: wall off every other neighbor of (1,0).
            for _x, _y in ((0, 0), (0, 1), (1, 1), (2, 1)):
                _state.game_map.tiles[_y][_x] = world.WALL
            run(_missile_flight._travel(
                _state, _ctx, _state.game_map, _b, _b.flight_speed,
            ))
            assert (_b.pos.x, _b.pos.y) == (1, 0)   # held
            assert _b.fuel == 13                     # no station-keeping burn
            assert _b.alive and _a.alive
        finally:
            _rules_space._state = _old

    def test_missiles_never_detonate_on_missiles(self, monkeypatch):
        # SETTLED 11.6: a rack fired at a crossing MISSILE is a legal
        # dud — the missile avoids it, never detonates on it.
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(8, 0))
        try:
            _a = _manual_missile(
                _state, (4, 0), _state.enemy_insts[0], fuel=0,
            )  # dry: immobile blocker
            _b = _manual_missile(_state, (1, 0), _a)  # targeting ordnance
            run(_missile_flight._travel(
                _state, _ctx, _state.game_map, _b, _b.flight_speed,
            ))
            assert _a.alive is True
            assert _b.alive is True
            assert (_b.pos.x, _b.pos.y) != (_a.pos.x, _a.pos.y)
            assert "Missile destroyed." not in _ctx.log.lines
        finally:
            _rules_space._state = _old

    def test_ship_parking_on_a_resting_missile_detonates_it(
        self, monkeypatch,
    ):
        # Contact reads on entry — except a ship that parks ON a
        # resting missile (they are non-blocking): the next mini-turn
        # reads that as contact (SETTLED 11.7).
        _calls = _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(5, 0))
        try:
            _a = _manual_missile(
                _state, (3, 0), _state.enemy_insts[0], fuel=0,
            )  # dry: immobile, resting in the open
            _pin_rng(monkeypatch, roll=50, spread=1.0)
            _state.enemy_insts[0].pos = world.Position(3, 0)  # the ship parks
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert _a not in _state.in_flight   # detonated under the hull
            assert _a.ent not in _state.game_map.entities
            assert len(_calls) == 1             # full kill chain ran
        finally:
            _rules_space._state = _old

    def test_player_parked_on_a_missile_eats_the_self_splash(self, monkeypatch):
        # The player's own hull parking on a resting missile is the
        # same contact — the self-splash branch, DEFEAT when lethal.
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture(enemy_at=(8, 0))
        try:
            _a = _manual_missile(
                _state, (1, 0), _state.enemy_insts[0], fuel=0,
            )
            _state.player_state["pos"] = world.Position(1, 0)  # the player parks
            _pin_rng(monkeypatch, roll=50, spread=1.0)
            _outcome = run(_missile_flight.advance_flights(
                _state, _ctx, _state.game_map,
            ))
            assert _outcome is None              # hull 100 survives a 64 hit
            assert _state.player_state["hull"] < 100
            assert _state.last_attacker == "Your own Heavy Missile"
            assert _a not in _state.in_flight
        finally:
            _rules_space._state = _old

    def test_dead_target_dissipates_the_missile_silently(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
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
            _missile = _manual_missile(
                _state, (1, 0), _state.enemy_insts[0],
                weapon_id="light_missile", fuel=3,
            )
            run(_missile_flight.advance_flights(_state, _ctx, _state.game_map))
            assert "Missile exhausts its fuel." in _ctx.log.lines
            assert _missile not in _state.in_flight
            assert (_missile.pos.x, _missile.pos.y) == (4, 0)  # ran dry mid-track
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
            assert (_state.in_flight[0].pos.x, _state.in_flight[0].pos.y) == (2, 0)
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
    def test_d_on_a_missile_target_denies(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            _state.target_idx = 1  # the missile
            assert _rules_space.try_board(_ctx, _state.game_map, 1) is False
            assert "Nothing to board." in _ctx.log.lines
        finally:
            _rules_space._state = _old

    def test_end_check_ignores_live_missiles(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
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
    def test_sync_state_sweeps_flights_and_entities(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
            _rules_space.sync_state(_ctx)
            assert _state.in_flight == []
            assert _missile.ent not in _state.game_map.entities
            assert _state.active is False
        finally:
            _rules_space._state = _old

    def test_activate_combat_state_sweeps_a_leftover_fight(self, monkeypatch):
        _patch_flights(monkeypatch)
        _ctx, _state, _old = _flight_fixture()
        try:
            _missile = run(_missile_flight.spawn_flight_missile(
                _state, "heavy_missile", _state.enemy_insts[0],
                side="player", quality=0,
                launch_pos=_state.player_state["pos"],
            ))
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
