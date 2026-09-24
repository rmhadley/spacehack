"""Honest enemy fire (doc 48 phase 7, SETTLED 39).

The Tier-0 walk pays real AP/power/ammo per shot, skips unaffordable
weapons, and ends the turn when nothing fires; weapon quality
multiplies enemy damage (the player path stays bit-identical at 0).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack.combat._actions import resolve_damage
from src.spacehack.combat._ai import _first_affordable_weapon, _pay_fire_costs
from src.spacehack.combat._types import EnemyInstance
from src.spacehack.data.weapons import find_weapon
from src.spacehack.engine import RNG
from src.spacehack.ship import StoredEquipment


def _enemy(weapons, *, ap=4, power=10, ammo=None):
    entries = tuple(StoredEquipment("weapon", w) for w in weapons)
    return EnemyInstance(
        spec_id="x", name="X", char="X", fg=(1, 2, 3),
        weapons=entries,
        ap_remaining=ap, ap_total=ap,
        power_pool=power, max_power=power,
        weapon_ammo=ammo if ammo is not None else {
            slot: (find_weapon(w).ammo_capacity if find_weapon(w).ammo_capacity > 0 else -1)
            for slot, w in enumerate(weapons)
        },
    )


# --- the walk ---------------------------------------------------------------


def test_walk_fires_the_first_affordable_weapon():
    enemy = _enemy(("light_laser", "heavy_missile"))
    assert _first_affordable_weapon(enemy) == 0


def test_walk_steps_past_a_dry_missile_to_the_next_weapon():
    """A missile-led ship with an empty magazine fires its laser —
    never inert, never infinite (the playtest's item 3)."""
    enemy = _enemy(("heavy_missile", "light_laser"), ammo={0: 0, 1: -1})
    assert _first_affordable_weapon(enemy) == 1


def test_walk_skips_a_two_ap_missile_at_one_ap():
    enemy = _enemy(("light_missile", "light_laser"), ap=1, ammo={0: 4, 1: -1})
    assert _first_affordable_weapon(enemy) == 1


def test_walk_skips_an_unaffordable_power_weapon():
    enemy = _enemy(("heavy_laser", "light_laser"), power=1)
    assert _first_affordable_weapon(enemy) == 1


def test_walk_returns_none_when_nothing_is_affordable():
    """The termination rule: no affordable weapon -> the turn's break."""
    enemy = _enemy(("heavy_laser",), power=0)
    assert _first_affordable_weapon(enemy) is None
    enemy = _enemy(("light_missile",), ammo={0: 0})
    assert _first_affordable_weapon(enemy) is None


# --- the costs ---------------------------------------------------------------


def test_fire_costs_pay_real_ap_power_and_ammo():
    enemy = _enemy(("heavy_missile",), ap=4, power=5, ammo={0: 3})
    _pay_fire_costs(enemy, 0, find_weapon("heavy_missile"))
    assert enemy.ap_remaining == 2          # missiles cost 2 AP
    assert enemy.power_pool == 5             # missiles cost no power
    assert enemy.weapon_ammo[0] == 2

    laser = _enemy(("heavy_laser",), ap=4, power=5)
    _pay_fire_costs(laser, 0, find_weapon("heavy_laser"))
    assert laser.ap_remaining == 3
    assert laser.power_pool == 3             # heavy laser drains 2


def test_missile_costs_floor_at_zero():
    enemy = _enemy(("light_missile",), ammo={0: 1})
    _pay_fire_costs(enemy, 0, find_weapon("light_missile"))
    assert enemy.weapon_ammo[0] == 0


# --- weapon-quality damage ----------------------------------------------------


def test_player_path_is_bit_identical_at_quality_zero():
    """quality 0 is the default: same seed, same damage as ever."""
    RNG.seed(42)
    base = resolve_damage("medium_laser", 100, 0)
    RNG.seed(42)
    explicit = resolve_damage("medium_laser", 100, 0, weapon_quality=0)
    assert base == explicit


def test_enemy_quality_scales_damage():
    """A prototype-tier weapon rolls inside the scaled band: quality 3
    multiplies by 1.45, so the same seed lands strictly harder."""
    RNG.seed(99)
    _, _, fh0, _ = resolve_damage("medium_laser", 100, 0)
    RNG.seed(99)
    _, _, fh3, _ = resolve_damage("medium_laser", 100, 0, weapon_quality=3)
    assert (100 - fh3) > (100 - fh0)  # the scaled roll is strictly bigger


# --- loop-level termination (the turn itself) --------------------------------


def _turn_state(enemy, *, los: bool):
    """A minimal SpaceCombatState-shaped fake: open floor when LOS
    should hold, a wall between the pair when it should not."""
    from types import SimpleNamespace
    from src.spacehack import world as _world

    width, height = 12, 8
    tiles = [[_world.DUNGEON_FLOOR] * width for _ in range(height)]
    if not los:
        for y in range(height):
            tiles[y][6] = _world.WALL
    game_map = _world.GameMap(width, height, tiles, [])
    player_pos = _world.Position(2, 4)
    enemy.pos = _world.Position(8, 4)
    return SimpleNamespace(
        ctx=None, console=None, game_map=game_map, log=[],
        player_state={"pos": player_pos, "hull": 50, "shields": 0},
        enemy_insts=[enemy], enemy_ents={}, player_ent=None,
        weapons_list=[], active_weapons=[], target_idx=0,
        view_w=80, view_h=54,
    )


def test_turn_breaks_when_nothing_is_affordable_in_band():
    """In range with LOS but an unaffordable loadout: the turn ends
    without firing — never a spin (the termination rule)."""
    from tests.support.asyncutil import run
    from src.spacehack.combat import _ai

    enemy = _enemy(("heavy_laser",), ap=4, power=0)  # 2 power/shot, none left
    state = _turn_state(enemy, los=True)
    spec = SimpleNamespace(ai_preferred_range=6)
    result = run(_ai._take_enemy_turn(
        state, enemy, 0, spec,
        hit_chances={}, evade_bonus=0,
        calc_cam=lambda: (0, 0), ctx=None,
    ))
    assert result is None
    assert enemy.ap_remaining == 4      # nothing spent, nothing fired


def test_blocked_enemy_without_los_never_fires():
    """A blocked step with no LOS breaks the turn instead of firing
    through cover (the dropped-gate regression the reviewer caught)."""
    from tests.support.asyncutil import run
    from src.spacehack.combat import _ai
    from src.spacehack import world as _world

    enemy = _enemy(("light_laser",), ap=4, power=10)
    state = _turn_state(enemy, los=False)
    # Wall the enemy in completely: no path, no move.
    for y in range(8):
        for x in (7, 9):
            state.game_map.tiles[y][x] = _world.WALL
    spec = SimpleNamespace(ai_preferred_range=6)
    result = run(_ai._take_enemy_turn(
        state, enemy, 0, spec,
        hit_chances={}, evade_bonus=0,
        calc_cam=lambda: (0, 0), ctx=None,
    ))
    assert result is None
    assert enemy.ap_remaining == 4      # affordable laser, but no LOS: no shot
    assert enemy.power_pool == 10
