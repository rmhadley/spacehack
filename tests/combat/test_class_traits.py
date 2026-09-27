"""Tests for the doc 49 phase-2 class-trait combat hooks — Pirate.

Pirate: +10 smuggler's hold on every ship; the opener (+hit, +damage
on the player's first attack of an encounter while no enemy has
fired) in BOTH theaters, spent by the attack, closed by any enemy
shot. The Merchant and Bounty Hunter hooks pin in their own sections
as they land.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.combat import _ai, _ai_ground, _loop, _rules_ground, _rules_space
from src.spacehack.ship import OwnedShip, StoredEquipment, smuggler_hold_capacity
from src.spacehack.xp import (
    PIRATE_OPENER_DAMAGE_PCT,
    PIRATE_OPENER_HIT_BONUS,
    pirate_opener_armed,
)
from tests.support.asyncutil import run


def _ctx(traits=(), **extra):
    ns = SimpleNamespace(player_traits=list(traits))
    for key, value in extra.items():
        setattr(ns, key, value)
    return ns


# ---------------------------------------------------------------------------
# Smuggler's hold — the +10 flat term
# ---------------------------------------------------------------------------

def test_smuggler_hold_pirate_flat_ten_on_every_ship():
    bare = OwnedShip(ship_id="starter")
    assert smuggler_hold_capacity(bare, _ctx([])) == 0
    assert smuggler_hold_capacity(bare, _ctx(["pirate"])) == 10


def test_smuggler_hold_pirate_stacks_module_and_perk_terms():
    held = OwnedShip(
        ship_id="starter",
        modules=(StoredEquipment("module", "smuggler_hold_mk1"),),
    )
    module_term = smuggler_hold_capacity(held, None)
    perk_term = smuggler_hold_capacity(
        OwnedShip(ship_id="starter"), _ctx(["smugglers_instinct"]),
    )
    assert module_term == 10
    assert perk_term >= 1
    assert smuggler_hold_capacity(held, _ctx(["pirate", "smugglers_instinct"])) == (
        module_term + perk_term + 10
    )


# ---------------------------------------------------------------------------
# The opener predicate (xp layer)
# ---------------------------------------------------------------------------

def test_pirate_opener_armed_truth_table():
    _pirate = _ctx(["pirate"])
    _plain = _ctx([])
    assert pirate_opener_armed(
        _pirate, enemy_fired=False, opener_spent=False,
    ) is True
    # No trait: never armed.
    assert pirate_opener_armed(
        _plain, enemy_fired=False, opener_spent=False,
    ) is False
    # Any enemy shot closes the window...
    assert pirate_opener_armed(
        _pirate, enemy_fired=True, opener_spent=False,
    ) is False
    # ...and the first attack spends it even if none ever fired.
    assert pirate_opener_armed(
        _pirate, enemy_fired=False, opener_spent=True,
    ) is False


# ---------------------------------------------------------------------------
# Ground opener — hit and damage reads
# ---------------------------------------------------------------------------

def _ground_enemy(armor=0, reflexes=30):
    return _rules_ground.GroundEnemyInstance(
        entity=SimpleNamespace(pos=world.Position(1, 0)),
        spec=SimpleNamespace(armor=armor),
        stats=SimpleNamespace(reflexes=reflexes),
        hp=100,
    )


def _ground_ctx(traits):
    return SimpleNamespace(
        player_traits=list(traits),
        player=SimpleNamespace(pos=world.Position(0, 0)),
        ground_stats=SimpleNamespace(reflexes=10, strength=20, stamina=10),
        equipped_ground_armor={},
    )


def _install_ground_state(**flags):
    _old = _rules_ground._state
    _rules_ground._state = SimpleNamespace(**flags)
    return _old


def test_ground_opener_hit_bonus_first_attack_only():
    # fists (acc 90) at reflexes 10 vs reflexes 30: 90 + 5 - 15 = 80.
    _old = _install_ground_state(enemy_fired=False, opener_spent=False)
    try:
        plain = _rules_ground.hit_chance("fists", _ground_enemy(), _ground_ctx([]))
        armed = _rules_ground.hit_chance(
            "fists", _ground_enemy(), _ground_ctx(["pirate"]),
        )
        assert plain == 80
        assert armed == plain + PIRATE_OPENER_HIT_BONUS
    finally:
        _rules_ground._state = _old
    _old = _install_ground_state(enemy_fired=True, opener_spent=False)
    try:
        after_shot = _rules_ground.hit_chance(
            "fists", _ground_enemy(), _ground_ctx(["pirate"]),
        )
        assert after_shot == plain
    finally:
        _rules_ground._state = _old
    _old = _install_ground_state(enemy_fired=False, opener_spent=True)
    try:
        after_attack = _rules_ground.hit_chance(
            "fists", _ground_enemy(), _ground_ctx(["pirate"]),
        )
        assert after_attack == plain
    finally:
        _rules_ground._state = _old


def test_ground_opener_damage_pct_first_attack_only():
    # fists vs armor 3 at strength 20: 1 + 4 - 3 = 2 base.
    _old = _install_ground_state(enemy_fired=False, opener_spent=False)
    try:
        _plain_dmg, _ = _rules_ground.damage("fists", _ground_enemy(3), _ground_ctx([]))
        _armed_dmg, _ = _rules_ground.damage(
            "fists", _ground_enemy(3), _ground_ctx(["pirate"]),
        )
        assert _plain_dmg == 2
        assert _armed_dmg == _plain_dmg * PIRATE_OPENER_DAMAGE_PCT // 100
    finally:
        _rules_ground._state = _old


def test_explosive_opener_scales_primary_and_splash_shares():
    """The blast's enemy shares ride the opener (doc 49 SETTLED 5):
    primary fully, splash off the scaled full damage."""
    from src.spacehack.combat import _ground_blast

    def _blast(opener_pct):
        _primary = _ground_enemy(0)
        _primary.pos = world.Position(0, 0)
        _splash = _ground_enemy(0)
        _splash.pos = world.Position(1, 0)
        _hits = {}
        for _label, _enemy in (("primary", _primary), ("splash", _splash)):
            _hit = _ground_blast.apply_explosive_enemy_hit(
                "grenade_launcher", _enemy, _primary, _ground_ctx([]),
                primary_hit=(_label == "primary"), opener_pct=opener_pct,
            )
            _hits[_label] = _hit[1]
        return _hits

    _plain = _blast(100)
    _armed = _blast(PIRATE_OPENER_DAMAGE_PCT)
    assert _armed["primary"] == _plain["primary"] * 125 // 100
    assert _armed["splash"] == _plain["splash"] * 125 // 100


def test_explosive_opener_never_reaches_the_self_splash():
    """The player's own splash share stays opener-free: the self-splash
    resolver takes no opener input at all (the signature is the
    tripwire — threading the pct in means the trait starts boosting
    the blast's friendly fire)."""
    import inspect

    from src.spacehack.combat import _ground_blast

    _params = inspect.signature(_ground_blast._apply_self_splash).parameters
    assert not any("opener" in name for name in _params)


# ---------------------------------------------------------------------------
# Space opener — hit and damage reads
# ---------------------------------------------------------------------------

def _install_space_state(traits, *, enemy_fired, opener_spent):
    _old = _rules_space._state
    _rules_space._state = _rules_space.SpaceCombatState(
        ctx=_ctx(traits), console=None,
        game_map=world.GameMap(3, 3, [[world.DUNGEON_FLOOR] * 3 for _ in range(3)], []),
        log=None,
        player_state={"pos": world.Position(0, 0)},
        enemy_fired=enemy_fired, opener_spent=opener_spent,
    )
    return _old


def test_space_opener_hit_bonus_first_attack_only():
    _old = _install_space_state(["pirate"], enemy_fired=False, opener_spent=False)
    try:
        assert _rules_space._player_hit_bonus(_ctx(["pirate"]), "light_laser") == (
            PIRATE_OPENER_HIT_BONUS
        )
    finally:
        _rules_space._state = _old
    for _flags in ({"enemy_fired": True, "opener_spent": False},
                   {"enemy_fired": False, "opener_spent": True}):
        _old = _install_space_state(["pirate"], **_flags)
        try:
            assert _rules_space._player_hit_bonus(
                _ctx(["pirate"]), "light_laser",
            ) == 0
        finally:
            _rules_space._state = _old


def test_space_opener_damage_mult_first_attack_only():
    from src.spacehack.combat._rules_space import _player_damage_mult

    _old = _install_space_state(["pirate"], enemy_fired=False, opener_spent=False)
    try:
        _armed = _player_damage_mult("light_laser", _ctx(["pirate"]), 4.0)
        _plain = _player_damage_mult("light_laser", _ctx([]), 4.0)
        assert _armed == _plain * (PIRATE_OPENER_DAMAGE_PCT / 100)
    finally:
        _rules_space._state = _old
    _old = _install_space_state(["pirate"], enemy_fired=True, opener_spent=False)
    try:
        assert _player_damage_mult("light_laser", _ctx(["pirate"]), 4.0) == \
            _player_damage_mult("light_laser", _ctx([]), 4.0)
    finally:
        _rules_space._state = _old


# ---------------------------------------------------------------------------
# The funnels — enemy shots close the window; attacks spend it
# ---------------------------------------------------------------------------

def test_space_enemy_attack_stamps_enemy_fired_before_resolution():
    """Every _enemy_attack call closes the window FIRST — the stamp
    lands before the weapon is even read, so misses count too."""
    _state = SimpleNamespace(enemy_fired=False)
    _ei = SimpleNamespace(weapons=())  # slot access raises post-stamp
    with pytest.raises(IndexError):
        run(_ai._enemy_attack(
            _state, _ei, 0, hit_chances={}, evade_bonus=0,
            calc_cam=lambda: (0, 0), ctx=None,
        ))
    assert _state.enemy_fired is True


def test_ground_enemy_burst_stamps_enemy_fired():
    _old = _install_ground_state(enemy_fired=False, opener_spent=False)
    try:
        # shots=0: nothing resolves, only the funnel stamp runs.
        _total = run(_ai_ground._fire_enemy_burst(
            None, None, None, None, None, None, "fists", None,
            None, 0, 0, 0, shots=0,
        ))
        assert _total == 0
        assert _rules_ground._state.enemy_fired is True
    finally:
        _rules_ground._state = _old


def test_mark_opener_spent_hook_resolves_for_both_rules_modules():
    assert callable(getattr(_rules_space, "mark_opener_spent", None))
    assert callable(getattr(_rules_ground, "mark_opener_spent", None))
    assert _loop._rules_hook(_rules_space, "mark_opener_spent") is \
        _rules_space.mark_opener_spent
    assert _loop._rules_hook(_rules_ground, "mark_opener_spent") is \
        _rules_ground.mark_opener_spent


def test_the_first_volley_spends_the_opener(monkeypatch):
    """The real fire loop consumes the opener on the player's first
    attack action — hit or miss (the fixture stubs the roll to hit)."""
    from tests.combat.test_origin_traits import _drive_fire

    _ctx_fired, _state = _drive_fire(monkeypatch, ["pirate"], hull=100)
    assert _state.opener_spent is True
    assert _state.enemy_fired is False  # the enemy never fired — spent anyway
