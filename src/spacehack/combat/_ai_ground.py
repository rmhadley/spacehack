"""Ground combat enemy AI — movement + fire logic for on-foot enemies.

Mirrors :mod:`combat._ai` which handles ship enemy behavior. Enemies
move toward the player when out of weapon range, fire when in range,
and spend AP on each action (1 per move, weapon's ap_cost per shot).
"""

from __future__ import annotations

from .. import world
from .. import message_log as _ml
from ..engine import RNG


def run_ground_enemy_turn(
    ctx,
    *,
    enemy_weapon_id: str,
    enemy_spec,
    enemy_ap: int,
    player_pos: world.Position,
    enemy_entity: world.Entity,
    game_map: world.GameMap,
    armor_defense: int,
) -> tuple[int, int]:
    """Execute one enemy turn during ground combat.

    While the enemy has AP remaining it either:
      1. Fires its weapon if the player is within weapon range.
      2. Moves toward the player (1 cell per AP) if out of range.

    Mutates ``enemy_entity.pos`` in-place as the enemy moves. The
    caller reads ``enemy_entity.pos`` after return for rendering.

    Returns ``(new_enemy_ap, damage_dealt)`` where ``damage_dealt`` is
    the amount of player HP reduced this turn (0 if miss or no weapon).
    The caller is responsible for applying ``damage_dealt`` to the
    player's HP pool and checking for defeat.
    """
    # Lazy import avoids circular import.
    from ._rules_ground import _ground_hit_chance_raw, _ground_damage_raw
    from ._stats import _distance

    if not enemy_weapon_id or enemy_ap <= 0:
        return (enemy_ap, 0, False)

    from ..data.ground_weapons import find_ground_weapon as _find_gw
    try:
        _ews = _find_gw(enemy_weapon_id)
    except KeyError:
        return (enemy_ap, 0, False)

    _result_ap = enemy_ap
    _damage_dealt = 0
    _fired = False

    while _result_ap > 0:
        _dist = _distance(enemy_entity.pos, player_pos)

        # If in weapon range -> fire
        if _ews and _dist <= _ews.max_range and _dist >= _ews.min_range:
            _hit = RNG.randint(1, 100) <= _ground_hit_chance_raw(
                enemy_weapon_id, enemy_spec.reflexes, ctx.ground_stats.reflexes,
            )
            if _hit:
                _damage_dealt = _ground_damage_raw(
                    enemy_weapon_id, enemy_spec.strength, armor_defense,
                )
                ctx.log.add_colored(
                    f"{enemy_spec.name} hits you for {_damage_dealt}!",
                    _ml.COLOR_ENEMY_ACTION,
                )
            else:
                ctx.log.add_colored(
                    f"{enemy_spec.name} fires but misses!",
                    _ml.COLOR_ENEMY_ACTION,
                )
            _result_ap -= _ews.ap_cost if _ews else 1
            _fired = True
            break  # one shot per enemy turn (matched to player's single [f] action)

        # Out of range — use A* pathfinding to navigate around walls/corners.
        _path = world.find_path(
            (enemy_entity.pos.x, enemy_entity.pos.y),
            {(player_pos.x, player_pos.y)},
            game_map,
            exclude_entity=enemy_entity,
            max_steps=2000,
        )
        if _path is None or len(_path) == 0:
            break  # no path to player

        _nx, _ny = _path[0]  # first step along A* path

        # Don't move into the player
        if (_nx, _ny) == (player_pos.x, player_pos.y):
            break

        if game_map.is_walkable(_nx, _ny) and game_map.entity_at(_nx, _ny, exclude=enemy_entity) is None:
            enemy_entity.pos = world.Position(_nx, _ny)
            _result_ap -= 1
        else:
            break  # blocked — can't move this turn

    if not _fired:
        ctx.log.add_colored(
            f"{enemy_spec.name} moves into position.",
            _ml.COLOR_ENEMY_ACTION,
        )

    return (_result_ap, _damage_dealt, _fired)
