"""Tests for the Deadshot trait — railgun full-pool shots + kill chains.

Deadshot spends the whole AP pool on a railgun shot (+5 hit / +4 damage
per AP beyond the base 2) and chains a kill into automatic follow-up
shots at the nearest target. Chain shots use base railgun stats, spend
one round each, and stop on a miss, a survivor, or an empty magazine.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.combat import _loop, _rules_ground, _ground_deadshot
from src.spacehack.ground_equipment import GroundWeaponInstance


def _deadshot_fixture(*, n_enemies: int = 3):
    """Open-floor map with the player holding a railgun at (2,5) and a
    line of scavengers to the east, plus an active ground combat state."""
    _tiles = [[world.DUNGEON_FLOOR for _ in range(11)] for _ in range(11)]
    _game_map = world.GameMap(11, 11, _tiles, [])
    _player = world.Entity("@", (255, 255, 255), world.Position(2, 5), "Player")
    _enemies = [
        world.Entity(
            "r", (255, 100, 100), world.Position(4 + 2 * _i, 5),
            f"Scavenger {_i}", npc_char_id="rock_scavenger",
        )
        for _i in range(n_enemies)
    ]
    _game_map.entities.extend([_player, *_enemies])
    _ctx = SimpleNamespace(
        player=_player,
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        ground_hp=23,
        ground_max_hp=23,
        equipped_ground_weapons=[GroundWeaponInstance("railgun", 12)],
        equipped_ground_armor={},
        player_traits=["deadshot"],
        player_counters=SimpleNamespace(total_kills=0, melee_kills=0, railgun_kills=0),
        player_xp=0,
        player_level=1,
        player_skill_points=0,
        log=SimpleNamespace(
            add=lambda _message: None,
            add_colored=lambda _message, _color: None,
        ),
    )
    _rules_ground.init(_ctx, _enemies, _game_map)
    return _ctx, _game_map, _enemies


def _force_hits(monkeypatch, chain_rolls):
    """Force every primary shot to hit and queue chain-shot rolls."""
    monkeypatch.setattr(_loop, "RNG", SimpleNamespace(randint=lambda *_a: 1))
    _rolls = iter(chain_rolls)
    monkeypatch.setattr(
        _ground_deadshot, "RNG",
        SimpleNamespace(randint=lambda *_a: next(_rolls)),
    )
    monkeypatch.setattr(
        _rules_ground, "animate_fire", lambda *a, **k: None,
    )


class TestIsDeadshot:
    def test_requires_trait_and_railgun(self):
        _ctx = SimpleNamespace(player_traits=["deadshot"])
        assert _ground_deadshot.is_deadshot(_ctx, "railgun")
        assert not _ground_deadshot.is_deadshot(_ctx, "battle_rifle")
        assert not _ground_deadshot.is_deadshot(
            SimpleNamespace(player_traits=[]), "railgun",
        )


class TestApPowerBonuses:
    def test_full_pool_powers_the_shot(self):
        _ctx, _game_map, _enemies = _deadshot_fixture()
        # ground base pool is 4 AP → 2 beyond the railgun's base 2.
        assert _rules_ground.player_ap(_ctx) == 4
        assert _ground_deadshot.ap_power_hit_bonus(_ctx, "railgun") == 10
        assert _ground_deadshot.ap_power_damage_bonus(_ctx, "railgun") == 8

    def test_no_bonus_below_base_cost(self):
        _ctx, _game_map, _enemies = _deadshot_fixture()
        _rules_ground.set_player_ap(_ctx, 1)
        assert _ground_deadshot.ap_power_hit_bonus(_ctx, "railgun") == 0
        assert _ground_deadshot.ap_power_damage_bonus(_ctx, "railgun") == 0

    def test_no_bonus_for_other_weapons(self):
        _ctx, _game_map, _enemies = _deadshot_fixture()
        assert _ground_deadshot.ap_power_hit_bonus(_ctx, "battle_rifle") == 0
        assert _ground_deadshot.ap_power_damage_bonus(_ctx, "battle_rifle") == 0


class TestDeadshotShotCost:
    def test_shot_spends_the_full_pool(self, monkeypatch):
        _ctx, _game_map, _enemies = _deadshot_fixture()
        for _inst in _rules_ground._state.enemies:
            _inst.hp = 5
        _force_hits(monkeypatch, chain_rolls=[1, 1])

        _loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0)

        assert _rules_ground.player_ap(_ctx) == 0


class TestChain:
    def test_kill_chains_through_nearest_targets(self, monkeypatch):
        _ctx, _game_map, _enemies = _deadshot_fixture()
        for _inst in _rules_ground._state.enemies:
            _inst.hp = 5
        _force_hits(monkeypatch, chain_rolls=[1, 1])

        _loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0)

        # Primary + two chain kills (nearest first), all dead.
        assert all(not _e.alive for _e in _rules_ground._state.enemies)
        assert _ctx.player_counters.railgun_kills == 3
        assert _ctx.player_counters.total_kills == 3
        # 1 primary round + 2 chain rounds spent.
        assert _ctx.equipped_ground_weapons[0].loaded_ammo == 9

    def test_chain_stops_when_a_target_survives(self, monkeypatch):
        _ctx, _game_map, _enemies = _deadshot_fixture()
        _rules_ground._state.enemies[0].hp = 5
        # e2/e3 are tankier than the base 22-damage chain shot — it
        # hits but fails to kill, so the chain stops there.
        _rules_ground._state.enemies[1].hp = 30
        _rules_ground._state.enemies[2].hp = 30
        _force_hits(monkeypatch, chain_rolls=[1])

        _loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0)

        assert not _rules_ground._state.enemies[0].alive
        assert _rules_ground._state.enemies[1].alive
        assert _rules_ground._state.enemies[2].alive
        assert _ctx.player_counters.railgun_kills == 1
        # Primary round + one fired chain round.
        assert _ctx.equipped_ground_weapons[0].loaded_ammo == 10

    def test_chain_stops_on_a_miss(self, monkeypatch):
        _ctx, _game_map, _enemies = _deadshot_fixture()
        for _inst in _rules_ground._state.enemies:
            _inst.hp = 5
        # First chain shot misses (roll 100 > hit chance).
        _force_hits(monkeypatch, chain_rolls=[100])

        _loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0)

        assert not _rules_ground._state.enemies[0].alive
        assert _rules_ground._state.enemies[1].alive
        assert _ctx.player_counters.railgun_kills == 1
        assert _ctx.equipped_ground_weapons[0].loaded_ammo == 10

    def test_no_chain_without_a_second_target(self, monkeypatch):
        _ctx, _game_map, _enemies = _deadshot_fixture(n_enemies=1)
        _rules_ground._state.enemies[0].hp = 5
        _force_hits(monkeypatch, chain_rolls=[])

        _loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0)

        assert not _rules_ground._state.enemies[0].alive
        assert _ctx.player_counters.railgun_kills == 1
        # Only the primary round was spent.
        assert _ctx.equipped_ground_weapons[0].loaded_ammo == 11

    def test_chain_respects_line_of_sight(self):
        _ctx, _game_map, _enemies = _deadshot_fixture()
        # A wall between e0 and e1 blocks the far enemies' sightlines
        # while leaving the adjacent scavenger a valid chain target.
        _game_map.tiles[5][5] = world.DUNGEON_WALL
        _target = _ground_deadshot._chain_target(_ctx, "railgun")
        assert _target is _rules_ground._state.enemies[0]
