"""Enemy fire (doc 48 phases 7-8, SETTLED 39/40).

The volley scores every weapon (EV per AP through the same
``calc_hit_chance`` the shot resolves with), pays real AP/power/ammo
per shot, and ends the turn when nothing fires; weapon quality
multiplies enemy damage (the player path stays bit-identical at 0).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack.combat._actions import resolve_damage
from src.spacehack.combat._ai import (
    _pay_fire_costs, _select_fire_weapon, score_weapon,
)
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


# --- the scorer (SETTLED 40) --------------------------------------------------


def test_score_folds_range_bands_through_calc_hit_chance():
    """The EV uses the SAME hit chance the shot resolves with: beyond
    max and inside min both lose value through the penalties."""
    in_band = score_weapon(find_weapon("light_laser"), 4.0, 0, 20, 0)
    beyond_max = score_weapon(find_weapon("light_laser"), 7.0, 0, 20, 0)
    assert in_band > beyond_max
    in_min = score_weapon(find_weapon("heavy_missile"), 1.0, 0, 20, 0)
    in_window = score_weapon(find_weapon("heavy_missile"), 5.0, 0, 20, 0)
    assert in_window > in_min


def test_score_emp_zero_on_bare_shields_top_on_fat():
    """Shield-strip weapons score expected STRIP: an EMP never fires on
    bare shields, and outranks a damage weapon per AP on a fat shield."""
    assert score_weapon(find_weapon("emp_missile"), 5.0, 0, 20, 0) == 0.0
    emp = score_weapon(find_weapon("emp_missile"), 5.0, 100, 20, 0)
    laser = score_weapon(find_weapon("light_laser"), 5.0, 100, 20, 0)
    assert emp > laser > 0


# --- the volley pick ----------------------------------------------------------


def test_pick_takes_the_top_scorer_not_the_first_affordable():
    """A missile outranks the beam while tubes last (32 dmg / 2 AP vs
    4 / 1) — the volley opens with the salvo, list order is dead."""
    enemy = _enemy(("light_laser", "heavy_missile"))
    assert _select_fire_weapon(enemy, 4.0, {"shields": 0})[0] == 1


def test_pick_steps_past_a_dry_missile_to_the_beam():
    """A missile-led ship with an empty magazine fires its laser —
    never inert, never infinite (the playtest's item 3)."""
    enemy = _enemy(("heavy_missile", "light_laser"), ammo={0: 0, 1: -1})
    assert _select_fire_weapon(enemy, 4.0, {"shields": 0})[0] == 1


def test_pick_skips_a_two_ap_missile_at_one_ap():
    enemy = _enemy(("light_missile", "light_laser"), ap=1, ammo={0: 4, 1: -1})
    assert _select_fire_weapon(enemy, 4.0, {"shields": 0})[0] == 1


def test_pick_skips_an_unaffordable_power_weapon():
    enemy = _enemy(("heavy_laser", "light_laser"), power=1)
    assert _select_fire_weapon(enemy, 4.0, {"shields": 0})[0] == 1


def test_pick_returns_none_when_nothing_is_affordable():
    """The termination rule: no affordable weapon -> the turn's break."""
    enemy = _enemy(("heavy_laser",), power=0)
    assert _select_fire_weapon(enemy, 4.0, {"shields": 0}) is None
    enemy = _enemy(("light_missile",), ammo={0: 0})
    assert _select_fire_weapon(enemy, 4.0, {"shields": 0}) is None


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
    enemy = _enemy(("heavy_laser",), ap=4, power=0)  # 2 power/shot, none left
    _run_turn(enemy)
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


# --- volley composition (the greedy loop, SETTLED 40) --------------------------


def _record_shots(monkeypatch):
    """Stub the attack resolution, keep the real cost payment — the
    loop's selection walk is what's under test."""
    from src.spacehack.combat import _ai
    shots: list[str] = []

    async def _fake_attack(state, _ei, slot, **_kw):
        shots.append(_ei.weapons[slot].item_id)
        _pay_fire_costs(_ei, slot, find_weapon(_ei.weapons[slot].item_id))
        return None

    monkeypatch.setattr(_ai, "_enemy_attack", _fake_attack)
    return shots


def _run_turn(enemy, *, los=True, pref=6):
    from tests.support.asyncutil import run
    from src.spacehack.combat import _ai

    state = _turn_state(enemy, los=los)
    spec = SimpleNamespace(ai_preferred_range=pref)
    run(_ai._take_enemy_turn(
        state, enemy, 0, spec,
        hit_chances={}, evade_bonus=0,
        calc_cam=lambda: (0, 0), ctx=None,
    ))
    return state


def test_volley_opens_with_missiles_then_settles_into_beams(monkeypatch):
    """Conservation is emergent (SETTLED 40): the finite magazine wins
    the scoring while tubes last, then the beam duel takes over."""
    shots = _record_shots(monkeypatch)
    enemy = _enemy(
        ("heavy_missile", "heavy_laser"), ap=4, power=6,
        ammo={0: 1, 1: -1},
    )
    _run_turn(enemy)
    assert shots == ["heavy_missile", "heavy_laser", "heavy_laser"]
    assert enemy.ap_remaining == 0
    assert enemy.weapon_ammo[0] == 0


def test_thin_power_pool_reads_as_the_low_draw_volley(monkeypatch):
    """The volley composes under the shared budget: with power for one
    heavy shot the ship dumps it, then steps down to the light set —
    a fat pool dumps the rack, a thin one reads low-draw."""
    shots = _record_shots(monkeypatch)
    enemy = _enemy(("heavy_laser", "light_laser"), ap=4, power=3)
    _run_turn(enemy)
    assert shots == ["heavy_laser", "light_laser"]
    assert enemy.ap_remaining == 2      # power dry: AP left, nothing legal
    assert enemy.power_pool == 0
