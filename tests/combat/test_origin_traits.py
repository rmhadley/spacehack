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
from src.spacehack.data.ground_weapons import find_ground_weapon
from src.spacehack.combat import _ground_charger


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
