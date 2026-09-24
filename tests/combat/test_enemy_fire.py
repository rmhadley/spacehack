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


# --- loop-level behavior (the turn itself) -----------------------------------


def _turn_state(enemy, *, los: bool, enemy_at=(8, 4)):
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
    enemy.pos = _world.Position(*enemy_at)
    return SimpleNamespace(
        ctx=None, console=None, game_map=game_map, log=[],
        player_state={"pos": player_pos, "hull": 50, "shields": 0},
        enemy_insts=[enemy], enemy_ents={}, player_ent=None,
        weapons_list=[], active_weapons=[], target_idx=0,
        view_w=80, view_h=54,
    )


def test_power_dry_ship_dodges_leftover_ap(monkeypatch):
    """The restated termination (SETTLED 40): with nothing affordable
    to fire, remaining AP goes to reposition steps while a legal
    in-band step exists — a power-dry ship dodges while it recharges;
    it never sits, never spins."""
    enemy = _enemy(("heavy_laser",), ap=4, power=0)  # 2 power/shot, none left
    _run_turn(enemy, monkeypatch=monkeypatch)
    assert enemy.ap_remaining == 0
    assert enemy.cells_moved_this_turn == 4
    assert enemy.power_pool == 0


def test_weaponless_spec_breaks_at_once(monkeypatch):
    """A weaponless ship (derelicts, the hauler) has no decision
    point in position — nothing to fire, no band to dance in."""
    enemy = _enemy((), ap=4, power=10)
    _run_turn(enemy, monkeypatch=monkeypatch)
    assert enemy.ap_remaining == 4      # breaks immediately, nothing spent


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


def _run_turn(enemy, *, los=True, pref=6, agg=100, enemy_at=(8, 4),
              rng_pin=None, monkeypatch=None):
    """Run one enemy turn under the fake state. ``agg`` is the spec's
    dial; ``rng_pin`` fixes the aggressiveness roll (1 always fires,
    100 always repositions) so volley sequences pin deterministically.
    Rendering is stubbed out — these pin decisions, not frames."""
    from tests.support.asyncutil import run
    from src.spacehack.combat import _ai

    async def _no_render(*_a, **_kw):
        pass

    monkeypatch.setattr(_ai, "_render_step_frame", _no_render)
    if rng_pin is not None:
        monkeypatch.setattr(
            _ai, "RNG", SimpleNamespace(randint=lambda _a, _b: rng_pin),
        )
    state = _turn_state(enemy, los=los, enemy_at=enemy_at)
    spec = SimpleNamespace(ai_preferred_range=pref, ai_aggressiveness=agg)
    run(_ai._take_enemy_turn(
        state, enemy, 0, spec,
        hit_chances={}, evade_bonus=0,
        calc_cam=lambda: (0, 0), ctx=None,
    ))
    return state


def _dist_to_player(state, enemy) -> float:
    _p = state.player_state["pos"]
    return ((_p.x - enemy.pos.x) ** 2 + (_p.y - enemy.pos.y) ** 2) ** 0.5


def test_volley_opens_with_missiles_then_settles_into_beams(monkeypatch):
    """Conservation is emergent (SETTLED 40): the finite magazine wins
    the scoring while tubes last, then the beam duel takes over."""
    shots = _record_shots(monkeypatch)
    enemy = _enemy(
        ("heavy_missile", "heavy_laser"), ap=4, power=6,
        ammo={0: 1, 1: -1},
    )
    _run_turn(enemy, rng_pin=1, monkeypatch=monkeypatch)
    assert shots == ["heavy_missile", "heavy_laser", "heavy_laser"]
    assert enemy.ap_remaining == 0
    assert enemy.weapon_ammo[0] == 0


def test_thin_power_pool_reads_as_the_low_draw_volley(monkeypatch):
    """The volley composes under the shared budget: with power for one
    heavy shot the ship dumps it, then steps down to the light set —
    a fat pool dumps the rack, a thin one reads low-draw."""
    shots = _record_shots(monkeypatch)
    enemy = _enemy(("heavy_laser", "light_laser"), ap=4, power=3)
    _run_turn(enemy, rng_pin=1, monkeypatch=monkeypatch)
    assert shots == ["heavy_laser", "light_laser"]
    assert enemy.power_pool == 0
    assert enemy.ap_remaining == 0      # power dry: leftover AP went to dodging
    assert enemy.cells_moved_this_turn == 2


# --- the aggressiveness dial (SETTLED 23/40) -----------------------------------


def test_aggressive_spec_fires_every_affordable_ap(monkeypatch):
    """The fire extreme: agg 100 fires ~every decision point — a
    brute-force ship sits and shoots, eating return fire."""
    shots = _record_shots(monkeypatch)
    enemy = _enemy(("light_laser",), ap=4, power=10)
    _run_turn(enemy, agg=100, rng_pin=1, monkeypatch=monkeypatch)
    assert shots == ["light_laser"] * 4
    assert enemy.cells_moved_this_turn == 0


def test_passive_spec_dodge_stacks_instead_of_shooting(monkeypatch):
    """The reposition extreme: agg 0 never wins the roll — the ship
    dodge-stacks through the movement economy, every step landing
    inside the active weapon's [min..max] band (the merchant read,
    SETTLED 23/40)."""
    from src.spacehack.combat._stats import _calc_dodge_bonus

    shots = _record_shots(monkeypatch)
    enemy = _enemy(("light_laser",), ap=4, power=10)
    state = _run_turn(enemy, agg=0, monkeypatch=monkeypatch)
    assert shots == []
    assert enemy.cells_moved_this_turn == 4
    assert 1 <= _dist_to_player(state, enemy) <= 5   # never left the band
    assert _calc_dodge_bonus(enemy.cells_moved_this_turn, 0) == 20  # 4 cells


# --- back-off (SETTLED 40) ------------------------------------------------------


def test_back_off_restores_min_range_then_resumes_fire(monkeypatch):
    """Hugged inside a min-3 missile's floor at dist 1, the ship
    backs off greedily until restoration (never past the band), then
    resumes fire."""
    shots = _record_shots(monkeypatch)
    enemy = _enemy(("heavy_missile",), ap=4, power=10, ammo={0: 3})
    state = _run_turn(
        enemy, pref=4, rng_pin=1, enemy_at=(3, 4), monkeypatch=monkeypatch,
    )
    assert _dist_to_player(state, enemy) >= 3.0   # restored to the floor
    assert shots == ["heavy_missile"]
    assert enemy.cells_moved_this_turn == 2


def test_cornered_missile_ship_fires_through_the_min_penalty(monkeypatch):
    """Walled in with no distance-gaining step: fall through and shoot
    through the min-range penalty — today's blocked-advance read."""
    from tests.support.asyncutil import run
    from src.spacehack.combat import _ai
    from src.spacehack import world as _world

    shots = _record_shots(monkeypatch)
    enemy = _enemy(("heavy_missile",), ap=4, power=10, ammo={0: 3})
    state = _turn_state(enemy, los=True, enemy_at=(3, 4))
    for _x, _y in ((2, 3), (2, 5), (3, 3), (3, 5), (4, 3), (4, 4), (4, 5)):
        state.game_map.tiles[_y][_x] = _world.WALL
    monkeypatch.setattr(
        _ai, "RNG", SimpleNamespace(randint=lambda _a, _b: 1),
    )
    spec = SimpleNamespace(ai_preferred_range=4, ai_aggressiveness=100)
    run(_ai._take_enemy_turn(
        state, enemy, 0, spec,
        hit_chances={}, evade_bonus=0,
        calc_cam=lambda: (0, 0), ctx=None,
    ))
    assert shots == ["heavy_missile", "heavy_missile"]  # 2 AP each
    assert enemy.cells_moved_this_turn == 0
    assert _dist_to_player(state, enemy) == 1.0         # never escaped the hug


def test_min_1_loadouts_never_back_off(monkeypatch):
    """Adjacency is in-band for a min-1 weapon (all lasers, merchants
    included): the back-off verb can never fire."""
    shots = _record_shots(monkeypatch)
    enemy = _enemy(("light_laser",), ap=4, power=10)
    _run_turn(
        enemy, pref=4, rng_pin=1, enemy_at=(3, 4), monkeypatch=monkeypatch,
    )
    assert enemy.cells_moved_this_turn == 0
    assert shots == ["light_laser"] * 4


def test_player_dodge_pins_the_shared_read():
    """The one dodge read both the shot and the scorer resolve with:
    4 cells (+20) and half-rate piloting 10 (+5)."""
    from src.spacehack.combat._ai import _player_dodge

    assert _player_dodge({"cells_moved_this_turn": 4, "piloting": 10}) == 25
    assert _player_dodge({}) == 0


def test_mixed_turn_never_teleports_off_a_stale_path(monkeypatch):
    """Advance and the in-position verbs interleave: back-off and
    reposition relocate the ship off its cached route, and the next
    advance must recompute (the stale-path teleport regression — a
    passive pref-3 missile ship closes to its floor, backs off the
    diagonal, then advances again; every hop stays 8-adjacent)."""
    from tests.support.asyncutil import run
    from src.spacehack.combat import _ai
    from src.spacehack import world as _world

    enemy = _enemy(("heavy_missile",), ap=7, power=10, ammo={0: 3})
    width, height = 16, 12
    game_map = _world.GameMap(
        width, height,
        [[_world.DUNGEON_FLOOR] * width for _ in range(height)], [],
    )
    enemy.pos = _world.Position(9, 9)
    state = SimpleNamespace(
        ctx=None, console=None, game_map=game_map, log=[],
        player_state={"pos": _world.Position(2, 2), "hull": 50, "shields": 0},
        enemy_insts=[enemy], enemy_ents={}, player_ent=None,
        weapons_list=[], active_weapons=[], target_idx=0,
        view_w=80, view_h=54,
    )
    hops: list[tuple[tuple[int, int], tuple[int, int]]] = []
    real_apply = _ai._apply_step

    async def _record_apply(_state, _ei, _e_idx, nx, ny, **_kw):
        hops.append(((_ei.pos.x, _ei.pos.y), (nx, ny)))
        await real_apply(_state, _ei, _e_idx, nx, ny, **_kw)

    async def _no_render(*_a, **_kw):
        pass

    monkeypatch.setattr(_ai, "_apply_step", _record_apply)
    monkeypatch.setattr(_ai, "_render_step_frame", _no_render)
    spec = SimpleNamespace(ai_preferred_range=3, ai_aggressiveness=0)
    run(_ai._take_enemy_turn(
        state, enemy, 0, spec,
        hit_chances={}, evade_bonus=0,
        calc_cam=lambda: (0, 0), ctx=None,
    ))
    assert enemy.ap_remaining == 0            # a full dance, never broke
    assert len(hops) == 7                     # every AP spent on a step
    for (fx, fy), (tx, ty) in hops:
        assert max(abs(tx - fx), abs(ty - fy)) == 1   # 8-adjacent, no teleports
