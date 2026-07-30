"""Ground combat loop — turn-based on-foot combat reusing the ship combat engine.

Mirrors :mod:`combat._loop` but adapted for ground:
  - AP per turn = 4 (brisker pace)
  - No shields, no power pool — armor provides flat DR
  - Hit chance uses REFLEXES, damage uses STRENGTH for melee
  - Enemy death → loot drop at position (no explosion)
  - Player death → ctx.player_dead = True
"""

from __future__ import annotations

from typing import Any

import tcod.console
import tcod.event

from .. import ui
from .. import world
from .. import message_log as _ml
from ..engine import RNG, SCREEN_WIDTH, SCREEN_HEIGHT, make_console
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..data.ground_enemies import find_ground_enemy as _find_ge
from ..data.ground_armor import find_ground_armor as _find_ga
from ..data.trade_goods import find_trade_good as _find_good
from ._actions import _remove_dead_entity as _rde
from ._stats import _distance


# ---------------------------------------------------------------------------
# Formulas
# ---------------------------------------------------------------------------

def _ground_hp_from_stamina(stamina: int) -> int:
    """Player max HP derived from stamina."""
    return 20 + stamina * 2


def _total_armor_defense(ctx) -> int:
    """Sum defense from all equipped armor pieces."""
    _total = 0
    for _slot, _aid in ctx.equipped_ground_armor.items():
        if _aid:
            try:
                _armor = _find_ga(_aid)
                _total += _armor.defense
            except KeyError:
                pass
    return _total


def _ground_hit_chance(
    weapon_id: str,
    attacker_reflexes: int,
    target_reflexes: int,
) -> int:
    """Hit chance for ground combat.

    Clamped 5-95.  Each point of reflexes adds 3% accuracy and
    2% dodge (subtracted from incoming).
    """
    _ws = _find_gw(weapon_id)
    _dodge = target_reflexes * 2
    _chance = _ws.accuracy + attacker_reflexes * 3 - _dodge
    return max(5, min(95, _chance))


def _ground_damage(
    weapon_id: str,
    strength: int,
    armor_defense: int,
) -> int:
    """Damage after armor reduction. STR bonus applies to melee only."""
    _ws = _find_gw(weapon_id)
    _str_bonus = strength // 4 if _ws.damage_type == 'melee' else 0
    _raw = _ws.damage + _str_bonus
    return max(1, _raw - armor_defense)


# ---------------------------------------------------------------------------
# Ground combat HUD
# ---------------------------------------------------------------------------

_COLOR_GROUND_TITLE: tuple[int, int, int] = (255, 200, 100)    # gold
_COLOR_GROUND_PLAYER: tuple[int, int, int] = (100, 220, 255)   # cyan
_COLOR_GROUND_ENEMY: tuple[int, int, int] = (255, 100, 100)    # red
_COLOR_GROUND_WEAPON: tuple[int, int, int] = (255, 200, 100)   # gold
_COLOR_GROUND_ACTION: tuple[int, int, int] = (180, 220, 255)   # light blue


def _render_ground_combat_hud(
    console: tcod.console.Console,
    *,
    player_hp: int,
    player_max_hp: int,
    enemy_name: str,
    enemy_hp: int,
    enemy_max_hp: int,
    weapon_name: str,
    ap_remaining: int,
    ap_total: int,
    distance: int,
) -> None:
    """Paint the ground combat HUD on the right panel."""
    _hud_x = SCREEN_WIDTH - 25
    y = 0

    console.print(x=_hud_x, y=y, string="> GROUND COMBAT <", fg=_COLOR_GROUND_TITLE)
    y += 2

    # Player block
    console.print(x=_hud_x, y=y, string="PLAYER", fg=_COLOR_GROUND_PLAYER)
    y += 1
    _hp_bar = _bar_str(player_hp, player_max_hp, width=8)
    _hp_pct = player_hp * 100 // max(player_max_hp, 1)
    console.print(x=_hud_x, y=y, string=f"HP  {_hp_bar} {_hp_pct}%", fg=_COLOR_GROUND_PLAYER)
    y += 1
    console.print(x=_hud_x, y=y, string=f"AP: {ap_remaining}/{ap_total}", fg=_COLOR_GROUND_ACTION)
    y += 1
    console.print(x=_hud_x, y=y, string=f"Wpn: {weapon_name}", fg=_COLOR_GROUND_WEAPON)
    y += 2

    # Enemy block
    console.print(x=_hud_x, y=y, string=f"ENEMY: {enemy_name}", fg=_COLOR_GROUND_ENEMY)
    y += 1
    _e_bar = _bar_str(enemy_hp, enemy_max_hp, width=8)
    _e_pct = enemy_hp * 100 // max(enemy_max_hp, 1)
    console.print(x=_hud_x, y=y, string=f"HP  {_e_bar} {_e_pct}%", fg=_COLOR_GROUND_ENEMY)
    y += 1
    console.print(x=_hud_x, y=y, string=f"Dist: {distance}", fg=_COLOR_GROUND_ENEMY)
    y += 2

    # Actions
    console.print(x=_hud_x, y=y, string="ACTIONS", fg=_COLOR_GROUND_TITLE)
    y += 1
    _actions = [
        ("[m]", "Move"),
        ("[f]", "Fire"),
        ("[w]", "Wait"),
        ("[ESC]", "Flee"),
    ]
    for key, desc in _actions:
        console.print(x=_hud_x, y=y, string=f"{key} {desc}", fg=_COLOR_GROUND_ACTION)
        y += 1


def _bar_str(value: int, max_value: int, width: int = 10) -> str:
    """CP437-safe bar string."""
    if max_value <= 0:
        return "." * width
    _full = max(0, min(width, value * width // max_value))
    return "#" * _full + "." * (width - _full)


# ---------------------------------------------------------------------------
# Ground combat loop
# ---------------------------------------------------------------------------

def _spawn_ground_loot(
    game_map: world.GameMap,
    pos: world.Position,
    enemy_id: str,
) -> None:
    """Drop loot at the enemy's death position (no explosion)."""
    try:
        _spec = _find_ge(enemy_id)
    except KeyError:
        return
    _pool = _spec.loot_pool
    if not _pool:
        return
    _min, _max = _spec.loot_count
    _count = RNG.randint(_min, _max)
    for _ in range(_count):
        _good_id = RNG.choice(_pool)
        _qty = RNG.randint(1, 2)
        game_map.entities.append(world.Entity(
            char="%",
            fg=(255, 215, 0),
            pos=pos,
            name="Loot", width=1, height=1,
            loot_data={"good_id": _good_id, "quantity": _qty},
        ))


def run_ground_combat(
    console: tcod.console.Console,
    ctx,
    enemy_entity: world.Entity,
    game_map: world.GameMap,
) -> tuple[str, str]:
    """Run a ground combat encounter against one enemy.

    Args:
        enemy_entity: the hostile Entity on the dungeon map.

    Returns:
        ``(outcome, defeated_enemy_id)`` where outcome is
        ``\"VICTORY\"``, ``\"DEFEAT\"``, or ``\"FLEE\"``.
    """
    try:
        _enemy_spec = _find_ge(enemy_entity.ground_enemy_id)
    except KeyError:
        ctx.log.add("Unknown ground enemy — cannot start combat.")
        return ("FLEE", "")

    # Determine enemy's weapon
    _enemy_weapon_id = ""
    if _enemy_spec.weapons:
        _enemy_weapon_id = _enemy_spec.weapons[0]
    elif _enemy_spec.weapon_pick:
        _enemy_weapon_id = RNG.choice(_enemy_spec.weapon_pick)

    # Compute stats
    _player_ap_total = 4
    _enemy_ap_total = 4

    _player_weapon_ids = list(ctx.equipped_ground_weapons)
    _player_weapon_id = _player_weapon_ids[0] if _player_weapon_ids else "fists"
    try:
        _player_ws = _find_gw(_player_weapon_id)
    except KeyError:
        _player_ws = _find_gw("fists")

    _player_max_hp = _ground_hp_from_stamina(ctx.ground_stats.stamina)
    _player_hp = min(ctx.ground_hp, _player_max_hp)
    _enemy_max_hp = _enemy_spec.hp + _enemy_spec.stamina * 2
    _enemy_hp = _enemy_max_hp

    _player_ap = _player_ap_total
    _enemy_ap = _enemy_ap_total

    _player_pos = ctx.player.pos
    _enemy_pos = enemy_entity.pos

    _armor_defense = _total_armor_defense(ctx)

    _outcome = "FLEE"
    _defeated_id = ""

    while True:
        _dist = _distance(_player_pos, _enemy_pos)

        # ---- Render ----
        console.clear()
        world.render_world(
            console, game_map,
            region_x=0, region_y=0,
            region_w=SCREEN_WIDTH - 25,
            region_h=SCREEN_HEIGHT - 6,
        )
        _render_ground_combat_hud(
            console,
            player_hp=_player_hp,
            player_max_hp=_player_max_hp,
            enemy_name=_enemy_spec.name,
            enemy_hp=_enemy_hp,
            enemy_max_hp=_enemy_max_hp,
            weapon_name=_player_ws.name,
            ap_remaining=_player_ap,
            ap_total=_player_ap_total,
            distance=_dist,
        )
        _ml.render_message_log(
            console, ctx.log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )
        ctx.context.present(console)

        # ---- Auto-end-turn when AP depleted ----
        if _player_ap <= 0:
            # Enemy turn
            if _enemy_weapon_id and _enemy_ap > 0:
                try:
                    _ews = _find_gw(_enemy_weapon_id)
                except KeyError:
                    _ews = None
                if _ews and _dist <= _ews.max_range and _dist >= _ews.min_range:
                    _hit = RNG.randint(1, 100) <= _ground_hit_chance(
                        _enemy_weapon_id, _enemy_spec.reflexes, ctx.ground_stats.reflexes,
                    )
                    if _hit:
                        _dmg = _ground_damage(_enemy_weapon_id, _enemy_spec.strength, _armor_defense)
                        _player_hp -= _dmg
                        ctx.log.add_colored(
                            f"{_enemy_spec.name} hits you for {_dmg}!",
                            _ml.COLOR_ENEMY_ACTION,
                        )
                        if _player_hp <= 0:
                            _outcome = "DEFEAT"
                            break
                    else:
                        ctx.log.add_colored(
                            f"{_enemy_spec.name} fires but misses!",
                            _ml.COLOR_ENEMY_ACTION,
                        )
                _enemy_ap -= _ews.ap_cost if _ews else 1
            _player_ap = _player_ap_total
            _enemy_ap = _enemy_ap_total
            continue

        # ---- Player input ----
        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                _outcome = "FLEE"
                break
            if not isinstance(event, tcod.event.KeyDown):
                continue
            _sym_name: str = getattr(event.sym, "name", "").lower()

            # Movement (vim keys)
            _vim_keys = {
                "h": (-1, 0), "j": (0, 1), "k": (0, -1), "l": (1, 0),
                "y": (-1, -1), "u": (1, -1), "b": (-1, 1), "n": (1, 1),
            }
            if _sym_name in _vim_keys and _player_ap > 0:
                _dx, _dy = _vim_keys[_sym_name]
                _nx = _player_pos.x + _dx
                _ny = _player_pos.y + _dy
                if game_map.is_walkable(_nx, _ny):
                    _blocker = game_map.entity_at(_nx, _ny, exclude=ctx.player)
                    if _blocker is None or _blocker is enemy_entity:
                        _player_pos = world.Position(_nx, _ny)
                        ctx.player.pos = _player_pos
                        _player_ap -= 1
                else:
                    ctx.log.add("A wall blocks your path.")
                break

            # [f] -> Fire weapon
            if _sym_name == "f":
                if _dist <= _player_ws.max_range and _dist >= _player_ws.min_range:
                    _hit = RNG.randint(1, 100) <= _ground_hit_chance(
                        _player_weapon_id, ctx.ground_stats.reflexes,
                        _enemy_spec.reflexes,
                    )
                    if _hit:
                        _dmg = _ground_damage(
                            _player_weapon_id, ctx.ground_stats.strength, 0,
                        )
                        _enemy_hp -= _dmg
                        ctx.log.add_colored(
                            f"You hit {_enemy_spec.name} for {_dmg}!",
                            _ml.COLOR_PLAYER_ACTION,
                        )
                        if _enemy_hp <= 0:
                            ctx.log.add_colored(
                                f"{_enemy_spec.name} collapses!",
                                _ml.COLOR_COMBAT_EVENT,
                            )
                            # Remove enemy entity, drop loot
                            _rde(game_map, {0: enemy_entity}, 0)
                            _spawn_ground_loot(game_map, _enemy_pos, enemy_entity.ground_enemy_id)
                            # XP reward
                            from ..xp import add_xp as _add_xp
                            _add_xp(ctx, _enemy_spec.xp_reward)
                            # Track kill counters
                            if hasattr(ctx, 'player_counters'):
                                ctx.player_counters.total_kills += 1
                            _outcome = "VICTORY"
                            _defeated_id = enemy_entity.ground_enemy_id
                            break
                    else:
                        ctx.log.add_colored(
                            f"Your shot misses {_enemy_spec.name}!",
                            _ml.COLOR_PLAYER_ACTION,
                        )
                    _player_ap -= _player_ws.ap_cost
                else:
                    ctx.log.add(f"Target out of range ({_dist}u, need {_player_ws.min_range}-{_player_ws.max_range}).")
                break

            # [w] -> Wait (end turn)
            if _sym_name == "w":
                _player_ap = 0
                break

            # ESC -> Flee
            if event.sym in ui._ESCAPE_SYMS:
                _flee_chance = 60  # flat 60% flee chance for ground
                if RNG.randint(1, 100) <= _flee_chance:
                    ctx.log.add("You break contact and retreat!")
                    _outcome = "FLEE"
                else:
                    ctx.log.add("Failed to flee!")
                    _player_ap = 0
                break

        if _outcome != "FLEE":
            break

    # Save HP back to ctx
    ctx.ground_hp = max(0, _player_hp)
    ctx.ground_max_hp = _player_max_hp

    if _outcome == "DEFEAT":
        ctx.player_dead = True
        ctx.log.add_colored("You collapse from your wounds...", _ml.COLOR_COMBAT_EVENT)

    return (_outcome, _defeated_id)
