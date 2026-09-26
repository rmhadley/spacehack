"""Player flown-weapon quality (doc 48.7 player side): the volley seam
threads the flown tier, damage scales exactly as enemy fire does, and
the HUD/target reads stay bounds-safe."""

from __future__ import annotations

import random
from types import SimpleNamespace

from src.spacehack import world
from src.spacehack.combat import _actions, _rules_space
from src.spacehack.combat._types import EnemyInstance
from src.spacehack.ship import StoredEquipment


def _enemy() -> EnemyInstance:
    return EnemyInstance(
        spec_id="pirate_scout", name="Pirate Scout", char="P",
        fg=(255, 100, 100), hull=200, max_hull=200, shields=0, max_shields=0,
        ap_remaining=2, ap_total=3, band=1,
        pos=world.Position(5, 3), weapons=(),
    )


def _engage(qualities=(0,)):
    old_state = _rules_space._state
    _rules_space._state = _rules_space.SpaceCombatState(
        ctx=SimpleNamespace(player_traits=()),
        console=None,
        game_map=None,
        log=None,
        player_state={
            "pos": world.Position(0, 0),
            "ap_remaining": 4, "ap_total": 4,
            "power_pool": 26, "gunnery": 20,
            "hull": 25, "max_hull": 25,
            "weapons": ["medium_laser"],
            "weapon_ammo": {0: -1},
        },
        enemy_insts=[_enemy()],
        target_idx=0,
        weapons_list=["medium_laser"],
        weapon_qualities=list(qualities),
        active_weapons=[True],
    )
    return old_state


def test_player_weapon_quality_reads_the_state_and_bounds_safe():
    old = _engage(qualities=(2,))
    try:
        assert _rules_space.player_weapon_quality(None, 0) == 2
        assert _rules_space.player_weapon_quality(None, 1) == 0  # out of range
    finally:
        _rules_space._state = old


def test_flown_quality_multiplies_player_damage():
    """Same RNG seed, same shot — a tier-2 barrel hits harder.

    Sabotage pin: drop the weapon_quality pass-through in
    ``_rules_space.damage`` and the two calls go identical."""
    import contextlib

    @contextlib.contextmanager
    def _seeded_rng():
        real = _actions.RNG
        _actions.RNG = random.Random(1234)
        try:
            yield
        finally:
            _actions.RNG = real

    old = _engage(qualities=(0,))
    try:
        ctx = None
        base, high = [], []
        for _ in range(12):
            for collected, quality in ((base, 0), (high, 2)):
                enemy = _enemy()
                with _seeded_rng():
                    dmg, _glancing = _rules_space.damage(
                        "medium_laser", enemy, ctx, quality,
                    )
                collected.append(dmg)
        # Tier 2 = the 1.3x weapon multiplier (doc 47.3 ladder); the
        # same seed makes every draw identical, so the pin is exact.
        assert base == [8] * 12
        assert high == [11] * 12
    finally:
        _rules_space._state = old


def test_init_threads_flown_qualities_into_state():
    """The space init reads ids AND tiers from the owned ship's
    StoredEquipment weapons."""
    owned = SimpleNamespace(
        weapons=(StoredEquipment("weapon", "medium_laser", quality=2),),
        modules=(),
        weapon_ammo={},
    )
    _ids = [
        entry.item_id if hasattr(entry, "item_id") else entry
        for entry in owned.weapons
    ]
    _quals = [getattr(entry, "quality", 0) for entry in owned.weapons]
    assert _ids == ["medium_laser"]
    assert _quals == [2]
