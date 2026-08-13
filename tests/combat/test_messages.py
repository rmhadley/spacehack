"""Tests for combat/_messages.py — roguelike combat log line builders.

These builders format every attack message in space and ground
combat, so their exact wording is a contract: players review the
scrollable history (\\ in combat) to understand what happened.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack.combat import _messages


# ---------------------------------------------------------------------------
# weapon_family
# ---------------------------------------------------------------------------

class TestWeaponFamily:
    def test_ship_missile(self):
        assert _messages.weapon_family("light_missile") == "missile"
        assert _messages.weapon_family("heavy_missile") == "missile"
        assert _messages.weapon_family("emp_missile") == "missile"

    def test_ship_energy_and_plasma_are_ranged(self):
        assert _messages.weapon_family("light_laser") == "ranged"
        assert _messages.weapon_family("plasma_cannon") == "ranged"

    def test_ground_melee(self):
        assert _messages.weapon_family("fists") == "melee"
        assert _messages.weapon_family("combat_knife") == "melee"
        assert _messages.weapon_family("monster_claws") == "melee"
        assert _messages.weapon_family("parasite_mandibles") == "melee"

    def test_ground_ranged(self):
        assert _messages.weapon_family("laser_rifle") == "ranged"
        assert _messages.weapon_family("kinetic_rifle") == "ranged"
        assert _messages.weapon_family("drone_laser") == "ranged"

    def test_unknown_defaults_to_ranged(self):
        assert _messages.weapon_family("no_such_weapon") == "ranged"


# ---------------------------------------------------------------------------
# player_attack_line
# ---------------------------------------------------------------------------

class TestPlayerAttackLine:
    def test_hit(self):
        line = _messages.player_attack_line(
            "laser_rifle", "Laser Rifle", "Assault Drone",
            hit=True, hull_dmg=7,
        )
        assert line == "You fire your Laser Rifle at Assault Drone. It hits for 7 damage!"

    def test_miss(self):
        line = _messages.player_attack_line(
            "laser_rifle", "Laser Rifle", "Assault Drone", hit=False,
        )
        assert line == "You fire your Laser Rifle at Assault Drone. It misses!"

    def test_melee_swing(self):
        line = _messages.player_attack_line(
            "combat_knife", "Combat Knife", "Ice Worm", hit=True, hull_dmg=4,
        )
        assert line == "You swing your Combat Knife at Ice Worm. It hits for 4 damage!"

    def test_missile_launch(self):
        line = _messages.player_attack_line(
            "heavy_missile", "Heavy Missile", "Pirate Raider",
            hit=True, hull_dmg=32,
        )
        assert line == "You launch a Heavy Missile at Pirate Raider. It hits for 32 damage!"

    def test_missile_an_article(self):
        line = _messages.player_attack_line(
            "emp_missile", "EMP Missile", "Pirate Raider",
            hit=True, hull_dmg=32,
        )
        assert line == "You launch an EMP Missile at Pirate Raider. It hits for 32 damage!"

    def test_glancing(self):
        line = _messages.player_attack_line(
            "light_laser", "Light Laser", "Pirate Raider",
            hit=True, hull_dmg=3, is_glancing=True,
        )
        assert line == "You fire your Light Laser at Pirate Raider. It glances for 3 damage!"

    def test_shield_split(self):
        line = _messages.player_attack_line(
            "light_laser", "Light Laser", "Pirate Raider",
            hit=True, hull_dmg=6, shield_dmg=2,
        )
        assert line == (
            "You fire your Light Laser at Pirate Raider. "
            "It hits for 8 damage (2 shields, 6 hull)!"
        )

    def test_shields_only_split(self):
        line = _messages.player_attack_line(
            "light_laser", "Light Laser", "Pirate Raider",
            hit=True, hull_dmg=0, shield_dmg=8,
        )
        assert line == (
            "You fire your Light Laser at Pirate Raider. "
            "It hits for 8 damage (8 shields)!"
        )

    def test_emp_strip(self):
        line = _messages.player_attack_line(
            "emp_missile", "EMP Missile", "Pirate Raider",
            hit=True, hull_dmg=0, shield_dmg=8, is_strip=True,
        )
        assert line == "You launch an EMP Missile at Pirate Raider. It strips 8 shields!"

    def test_glancing_with_shield_split(self):
        line = _messages.player_attack_line(
            "light_laser", "Light Laser", "Pirate Raider",
            hit=True, hull_dmg=2, shield_dmg=1, is_glancing=True,
        )
        assert line == (
            "You fire your Light Laser at Pirate Raider. "
            "It glances for 3 damage (1 shield, 2 hull)!"
        )


# ---------------------------------------------------------------------------
# enemy_attack_line
# ---------------------------------------------------------------------------

class TestEnemyAttackLine:
    def test_hit(self):
        line = _messages.enemy_attack_line(
            "Assault Drone", "drone_laser", "Drone Laser",
            hit=True, hull_dmg=4,
        )
        assert line == "Assault Drone fires its Drone Laser at you. It hits for 4 damage!"

    def test_miss(self):
        line = _messages.enemy_attack_line(
            "Assault Drone", "drone_laser", "Drone Laser", hit=False,
        )
        assert line == "Assault Drone fires its Drone Laser at you. It misses!"

    def test_melee(self):
        line = _messages.enemy_attack_line(
            "Ice Worm", "monster_claws", "Monster Claws",
            hit=True, hull_dmg=5,
        )
        assert line == "Ice Worm swings its Monster Claws at you. It hits for 5 damage!"

    def test_missile(self):
        line = _messages.enemy_attack_line(
            "Pirate Raider", "light_missile", "Light Missile",
            hit=True, hull_dmg=14,
        )
        assert line == "Pirate Raider launches a Light Missile at you. It hits for 14 damage!"

    def test_glancing(self):
        line = _messages.enemy_attack_line(
            "Pirate Raider", "light_laser", "Light Laser",
            hit=True, hull_dmg=3, is_glancing=True,
        )
        assert line == "Pirate Raider fires its Light Laser at you. It glances for 3 damage!"

    def test_shield_split(self):
        line = _messages.enemy_attack_line(
            "Pirate Raider", "light_laser", "Light Laser",
            hit=True, hull_dmg=6, shield_dmg=2,
        )
        assert line == (
            "Pirate Raider fires its Light Laser at you. "
            "It hits for 8 damage (2 shields, 6 hull)!"
        )

    def test_strip(self):
        line = _messages.enemy_attack_line(
            "Pirate Raider", "emp_missile", "EMP Missile",
            hit=True, hull_dmg=0, shield_dmg=6, is_strip=True,
        )
        assert line == "Pirate Raider launches an EMP Missile at you. It strips 6 shields!"

    def test_strip_singular(self):
        line = _messages.enemy_attack_line(
            "Pirate Raider", "emp_missile", "EMP Missile",
            hit=True, hull_dmg=0, shield_dmg=1, is_strip=True,
        )
        assert line == "Pirate Raider launches an EMP Missile at you. It strips 1 shield!"

    def test_shields_only_split(self):
        line = _messages.enemy_attack_line(
            "Pirate Raider", "light_laser", "Light Laser",
            hit=True, hull_dmg=0, shield_dmg=4,
        )
        assert line == (
            "Pirate Raider fires its Light Laser at you. "
            "It hits for 4 damage (4 shields)!"
        )
