"""Tests for the doc 49 origin-trait space hooks — Momentum and Longshot.

Momentum: +5% hit chance always on; a space kill refunds the killing
volley's AP. Longshot: +1 max range on every player weapon (the space
rider; the ground +1 lives in _ground_charger.weapon_range, pinned in
tests/test_origin_traits.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.combat import _rules_space, _space_focus
from src.spacehack.combat._space_kills import refund_volley_ap
from src.spacehack.combat._types import CombatResult, EnemyInstance
from src.spacehack.data.ground_weapons import find_ground_weapon
from src.spacehack.combat import _ground_charger
from tests.support.asyncutil import as_async


def _ctx(traits=()):
    return SimpleNamespace(player_traits=list(traits))


# ---------------------------------------------------------------------------
# Momentum — hit bonus
# ---------------------------------------------------------------------------

def test_momentum_adds_five_space_hit():
    assert _rules_space._player_hit_bonus(_ctx(["momentum"]), "light_laser") == 5
    assert _rules_space._player_hit_bonus(_ctx([]), "light_laser") == 0


def test_momentum_stacks_with_sharpshooter_and_specialists():
    assert _rules_space._player_hit_bonus(
        _ctx(["momentum", "sharpshooter"]), "light_laser",
    ) == 15
    assert _rules_space._player_hit_bonus(
        _ctx(["momentum", "sharpshooter", "laser_specialist"]), "light_laser",
    ) == 25


# ---------------------------------------------------------------------------
# Momentum — kill refund
# ---------------------------------------------------------------------------

def _live_state(traits):
    """A minimal live space-combat session on the module global."""
    _state = _rules_space.SpaceCombatState(
        ctx=_ctx(traits), console=None,
        game_map=world.GameMap(3, 3, [[world.DUNGEON_FLOOR] * 3 for _ in range(3)], []),
        log=None,
        player_state={"pos": world.Position(0, 0), "ap_remaining": 3},
        enemy_insts=[], weapons_list=["light_laser"], active_weapons=[True],
    )
    _old = _rules_space._state
    _rules_space._state = _state
    return _state, _old


def test_refund_restores_the_volley_ap_with_momentum():
    _state, _old = _live_state(["momentum"])
    try:
        refund_volley_ap(_state, _state.ctx, 2)
        assert _state.player_state["ap_remaining"] == 5
    finally:
        _rules_space._state = _old


def test_refund_is_noop_without_momentum_or_amount():
    _state, _old = _live_state([])
    try:
        refund_volley_ap(_state, _state.ctx, 2)
        assert _state.player_state["ap_remaining"] == 3
        refund_volley_ap(_state, _state.ctx, 0)
        assert _state.player_state["ap_remaining"] == 3
    finally:
        _rules_space._state = _old


def test_rules_space_exposes_the_refund_hook_ground_does_not():
    """The shared fire loop resolves the refund by rules module: space
    implements it, ground stays silent (no ground AP refund)."""
    from src.spacehack.combat import _loop, _rules_ground
    assert callable(getattr(_rules_space, "refund_volley_ap", None))
    assert _loop._rules_hook(_rules_ground, "refund_volley_ap") is None


# ---------------------------------------------------------------------------
# Longshot — range riders
# ---------------------------------------------------------------------------

def test_longshot_space_max_range_plus_one_unfocused_and_focused():
    _ctx_l = _ctx(["longshot"])
    assert _space_focus.max_range("light_laser", _ctx_l) == 6
    assert _space_focus.max_range("light_laser", _ctx([])) == 5
    # The rider rides the doubled focused range too (5*2+1), min stays.
    assert _space_focus.min_range("light_laser", _ctx_l) == \
        _space_focus.min_range("light_laser", _ctx([]))


def test_longshot_ground_ranged_plus_one_melee_and_spec_untouched():
    _ctx_l = _ctx(["longshot"])
    _plain = _ctx([])
    # Ranged: +1 on the effective range; the catalog spec never moves.
    _ranged_max = find_ground_weapon("kinetic_pistol").max_range
    assert _ground_charger.weapon_range("kinetic_pistol", _ctx_l, 4) == (
        1, _ranged_max + 1,
    )
    assert _ground_charger.weapon_range("kinetic_pistol", _plain, 4) == (
        1, _ranged_max,
    )
    assert find_ground_weapon("kinetic_pistol").max_range == _ranged_max
    # Melee: untouched at max_range 1, trait or not.
    assert _ground_charger.weapon_range("stun_baton", _ctx_l, 4) == (1, 1)
    assert _ground_charger.weapon_range("fists", _ctx_l, 4) == (1, 1)


# ---------------------------------------------------------------------------
# Momentum — the fire-loop dispatch (kill detection + refund call)
# ---------------------------------------------------------------------------

class _FakeRules:
    """A rules double exposing only what _maybe_refund_volley_ap reads."""

    def __init__(self, alive):
        self._alive = alive
        self.refunded = 0

    def enemy_alive(self, enemy):
        return self._alive[enemy]

    def refund_volley_ap(self, ctx, amount):
        self.refunded = amount


def test_maybe_refund_dispatches_only_on_a_killing_volley():
    from src.spacehack.combat import _loop
    enemies = {0: True, 1: True}
    rules = _FakeRules(enemies)
    _loop._maybe_refund_volley_ap(None, rules, enemies, alive_before=2, max_ap_cost=3)
    assert rules.refunded == 0  # nothing died — no refund
    enemies[1] = False
    _loop._maybe_refund_volley_ap(None, rules, enemies, alive_before=2, max_ap_cost=3)
    assert rules.refunded == 3  # the volley killed — full cost back
    _loop._maybe_refund_volley_ap(None, rules, enemies, alive_before=2, max_ap_cost=0)
    assert rules.refunded == 3  # a kill from a free volley refunds nothing


def _fire_fixture(traits, hull):
    """A minimal live space session that can run the REAL _handle_fire."""
    _ctx = SimpleNamespace(
        player_traits=list(traits),
        player_counters=SimpleNamespace(
            laser_shots=0, missile_shots=0, plasma_shots=0, focused_shots=0,
            total_kills=0,
        ),
        player=world.Entity("@", (255, 255, 255), world.Position(0, 0), "Player"),
        log=SimpleNamespace(
            add=lambda *_a, **_k: None,
            add_colored=lambda *_a, **_k: None,
        ),
    )
    _tiles = [[world.DUNGEON_FLOOR for _ in range(11)] for _ in range(11)]
    _state = _rules_space.SpaceCombatState(
        ctx=_ctx, console=None,
        game_map=world.GameMap(11, 11, _tiles, []),
        log=None,
        player_state={
            "pos": world.Position(0, 0), "gunnery": 10,
            "ap_remaining": 8, "ap_total": 8,
            "power_pool": 20, "max_power": 20, "plasma_ap_discount": 0,
            "weapons": ("light_laser",), "weapon_ammo": {0: 4},
        },
        enemy_insts=[EnemyInstance(
            spec_id="pirate_scout", name="Pirate Scout", char="P",
            fg=(255, 100, 100), pos=world.Position(6, 0),
            hull=hull, max_hull=hull, shields=0, max_shields=0,
            pilot_piloting=0, cells_moved_this_turn=0,
        )],
        enemy_ents={},
        weapons_list=["light_laser"], active_weapons=[True],
        cr=CombatResult(),
    )
    _old = _rules_space._state
    _rules_space._state = _state
    return _ctx, _state, _old


def _drive_fire(monkeypatch, traits, hull):
    from src.spacehack.combat import _actions, _animations, _loop
    from tests.support.asyncutil import run
    _ctx, _state, _old = _fire_fixture(traits, hull)
    monkeypatch.setattr(
        _actions, "RNG",
        SimpleNamespace(randint=lambda *_a: 1, uniform=lambda *_a: 1.0),
    )
    monkeypatch.setattr(_loop, "RNG", _actions.RNG)
    monkeypatch.setattr(_rules_space, "animate_fire", as_async(lambda *a, **k: None))
    monkeypatch.setattr(
        _animations, "_animate_explosion", as_async(lambda *a, **k: None),
    )
    try:
        run(_loop._handle_fire(None, _ctx, _state.game_map, _rules_space, 0))
        return _ctx, _state
    finally:
        _rules_space._state = _old


def test_killing_volley_costs_no_ap_with_momentum(monkeypatch):
    # Assertions read the returned session state directly (the fixture's
    # finally restores the module global before these run).
    _ctx, _state = _drive_fire(monkeypatch, ["momentum"], hull=1)
    assert _state.enemy_insts[0].alive is False  # the target died
    assert _state.player_state["ap_remaining"] == 8  # 8 - 1 + 1 refunded


def test_surviving_volley_pays_full_ap_with_momentum(monkeypatch):
    _ctx, _state = _drive_fire(monkeypatch, ["momentum"], hull=100)
    assert _state.enemy_insts[0].alive is True
    assert _state.player_state["ap_remaining"] == 7  # 8 - 1, nothing died


def test_killing_volley_costs_ap_without_momentum(monkeypatch):
    _ctx, _state = _drive_fire(monkeypatch, [], hull=1)
    assert _state.enemy_insts[0].alive is False
    assert _state.player_state["ap_remaining"] == 7  # 8 - 1, no refund trait
