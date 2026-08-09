"""Tests for combat/_rules_ground.py — pure formula functions.

Ground combat accuracy, damage, and movement dodge — same
invisible-regression risk as space combat math.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from types import SimpleNamespace

from src.spacehack import world
from src.spacehack.combat import _loop, _rules_ground
from src.spacehack.combat._rules_ground import (
    _ground_hit_chance_raw,
    _ground_damage_raw,
    _calc_ground_move_dodge,
    _ground_point_blank_penalty,
)


# ---------------------------------------------------------------------------
# _ground_hit_chance_raw
# ---------------------------------------------------------------------------

class TestGroundHitChanceRaw:
    """accuracy + att_reflexes//2 - tgt_reflexes//2 - dodge + hit_bonus,
    clamped 5-95."""

    def test_basic(self):
        """fists: accuracy=90, reflexes 20 vs 10,
        no dodge → 90 + 10 - 5 = 95."""
        chance = _ground_hit_chance_raw("fists", 20, 10, 0, 0)
        assert chance == 95

    def test_attacker_advantage(self):
        """High reflexes attacker."""
        chance = _ground_hit_chance_raw("fists", 40, 10, 0, 0)
        # 85 + 20 - 5 = 100 → clamped 95
        assert chance == 95

    def test_target_dodge(self):
        """Movement dodge reduces hit chance."""
        chance = _ground_hit_chance_raw("fists", 20, 10, 20, 0)
        # 90 + 10 - 5 - 20 = 75
        assert chance == 75

    def test_hit_bonus(self):
        """Sharpshooter +10%."""
        chance = _ground_hit_chance_raw("fists", 20, 10, 0, hit_bonus=10)
        # 85 + 10 - 5 + 10 = 100 → 95
        assert chance == 95

    def test_clamped_low(self):
        chance = _ground_hit_chance_raw("fists", 0, 100, 200, 0)
        assert chance == 5

    def test_point_blank_penalty_can_be_applied(self):
        chance = _ground_hit_chance_raw(
            "kinetic_rifle", 20, 10, range_penalty=35,
        )
        assert chance == 38


# ---------------------------------------------------------------------------
# _ground_damage_raw
# ---------------------------------------------------------------------------

class TestGroundDamageRaw:
    """Base damage + str//10 (melee only) - armor, min 1."""

    def test_basic(self):
        """fists: damage=1 (melee), str=20 → +2, armor=0 → 3."""
        dmg = _ground_damage_raw("fists", 20, 0)
        assert dmg == 3  # 1 + 2 - 0

    def test_armor_mitigation(self):
        """armor=3 reduces damage by 3."""
        dmg = _ground_damage_raw("fists", 20, 3)
        assert dmg == 1  # 2 + 2 - 3 = 1

    def test_no_strength_bonus_ranged(self):
        """Ranged weapons don't get the str//10 bonus."""
        # laser_pistol: damage=4, energy type (no str bonus)
        dmg = _ground_damage_raw("laser_pistol", 50, 0)
        assert dmg == 4  # 4 + 0 - 0

    def test_min_1(self):
        """Never below 1 damage."""
        dmg = _ground_damage_raw("fists", 0, 100)
        assert dmg == 1


# ---------------------------------------------------------------------------
# _calc_ground_move_dodge
# ---------------------------------------------------------------------------

class TestGroundPointBlankPenalty:
    def test_no_penalty_at_or_beyond_min_range(self):
        assert _ground_point_blank_penalty("kinetic_rifle", 2) == 0
        assert _ground_point_blank_penalty("kinetic_rifle", 4) == 0

    def test_penalty_scales_inside_min_range(self):
        assert _ground_point_blank_penalty("kinetic_rifle", 1) == 35
        assert _ground_point_blank_penalty("kinetic_rifle", 0) == 70


class TestGroundCanFire:
    def test_min_range_weapon_has_emergency_point_blank_action(self):
        _tiles = [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(5)]
        _game_map = world.GameMap(5, 5, _tiles, [])
        _player = world.Entity(
            "@", (255, 255, 255), world.Position(2, 2), "Player",
        )
        _enemy = world.Entity(
            "D", (255, 100, 100), world.Position(2, 3), "Assault Drone",
            npc_char_id="assault_drone",
        )
        _game_map.entities.extend((_player, _enemy))
        _ctx = SimpleNamespace(
            player=_player,
            ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
            ground_hp=23,
            ground_max_hp=23,
            equipped_ground_weapons=["kinetic_rifle"],
            equipped_ground_armor={},
            player_traits=[],
            log=SimpleNamespace(
                add=lambda _message: None,
                add_colored=lambda _message, _color: None,
            ),
        )

        _rules_ground.init(_ctx, [_enemy], _game_map)

        _ok, _reason = _rules_ground.can_fire(0, _ctx)

        assert _ok
        assert "Emergency point-blank shot" in _reason


class TestGroundPointBlankFire:
    def test_two_adjacent_drones_do_not_softlock_min_range_rifles(self, monkeypatch):
        _tiles = [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(5)]
        _game_map = world.GameMap(5, 5, _tiles, [])
        _player = world.Entity(
            "@", (255, 255, 255), world.Position(2, 2), "Player",
        )
        _left = world.Entity(
            "D", (255, 100, 100), world.Position(2, 1), "Assault Drone",
            npc_char_id="assault_drone",
        )
        _right = world.Entity(
            "D", (255, 100, 100), world.Position(2, 3), "Assault Drone",
            npc_char_id="assault_drone",
        )
        _game_map.entities.extend((_player, _left, _right))
        _messages = []
        _ctx = SimpleNamespace(
            player=_player,
            ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
            ground_hp=23,
            ground_max_hp=23,
            equipped_ground_weapons=["kinetic_rifle", "kinetic_rifle"],
            equipped_ground_armor={},
            player_traits=[],
            log=SimpleNamespace(
                add=_messages.append,
                add_colored=lambda _message, _color: _messages.append(_message),
            ),
        )

        _rules_ground.init(_ctx, [_left, _right], _game_map)
        monkeypatch.setattr(_rules_ground, "animate_fire", lambda *args, **kwargs: None)
        monkeypatch.setattr(_loop, "RNG", SimpleNamespace(randint=lambda *_args: 1))

        _loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0)

        assert _rules_ground.player_ap(_ctx) == 2
        assert _left.hp < 39
        assert any("Emergency point-blank shot" in _message for _message in _messages)

    def test_point_blank_still_requires_clear_los(self, monkeypatch):
        _tiles = [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(5)]
        _tiles[3][2] = world.DUNGEON_WALL
        _game_map = world.GameMap(5, 5, _tiles, [])
        _player = world.Entity(
            "@", (255, 255, 255), world.Position(2, 2), "Player",
        )
        _enemy = world.Entity(
            "D", (255, 100, 100), world.Position(2, 4), "Assault Drone",
            npc_char_id="assault_drone",
        )
        _game_map.entities.extend((_player, _enemy))
        _ctx = SimpleNamespace(
            player=_player,
            ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
            ground_hp=23,
            ground_max_hp=23,
            equipped_ground_weapons=["kinetic_rifle"],
            equipped_ground_armor={},
            player_traits=[],
            log=SimpleNamespace(
                add=lambda _message: None,
                add_colored=lambda _message, _color: None,
            ),
        )

        _rules_ground.init(_ctx, [_enemy], _game_map)
        monkeypatch.setattr(
            _rules_ground,
            "_find_gw",
            lambda _weapon_id: SimpleNamespace(min_range=3, max_range=7, ap_cost=2),
        )

        _ok, _reason = _rules_ground.can_fire(0, _ctx)

        assert not _ok
        assert _reason == "Blocked by wall"

    def test_point_blank_still_requires_ap(self):
        _tiles = [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(5)]
        _game_map = world.GameMap(5, 5, _tiles, [])
        _player = world.Entity(
            "@", (255, 255, 255), world.Position(2, 2), "Player",
        )
        _enemy = world.Entity(
            "D", (255, 100, 100), world.Position(2, 3), "Assault Drone",
            npc_char_id="assault_drone",
        )
        _game_map.entities.extend((_player, _enemy))
        _ctx = SimpleNamespace(
            player=_player,
            ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
            ground_hp=23,
            ground_max_hp=23,
            equipped_ground_weapons=["kinetic_rifle"],
            equipped_ground_armor={},
            player_traits=[],
            log=SimpleNamespace(
                add=lambda _message: None,
                add_colored=lambda _message, _color: None,
            ),
        )

        _rules_ground.init(_ctx, [_enemy], _game_map)
        _rules_ground.set_player_ap(_ctx, 0)

        _ok, _reason = _rules_ground.can_fire(0, _ctx)

        assert not _ok
        assert "Need 2 AP" in _reason


class TestCalcGroundMoveDodge:
    def test_no_movement(self):
        assert _calc_ground_move_dodge(0) == 0

    def test_one_cell(self):
        assert _calc_ground_move_dodge(1) == 5

    def test_four_cells(self):
        assert _calc_ground_move_dodge(4) == 20

    def test_cap(self):
        """7 cells → 30 (capped, not 35)."""
        assert _calc_ground_move_dodge(7) == 30
