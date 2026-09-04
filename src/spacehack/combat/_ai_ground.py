"""Ground combat enemy AI — movement + fire logic for on-foot enemies.

Mirrors :mod:`combat._ai` which handles ship enemy behavior. Enemies
move toward the player when out of weapon range, fire when in range,
and spend AP on each action (1 per move, weapon's ap_cost per shot).
"""

from __future__ import annotations

from .. import world
from .. import message_log as _ml
from ..engine import RNG
from .. import animation_timing
from ._animations import (
    _damage_popup_for,
    _has_los,
    _responsive_sleep,
    _present,
)
from ._messages import enemy_attack_line as _enemy_attack_line
from ._shot_animations import _animate_ground_shot

# Guards defend a post: beyond this euclidean distance from their
# spawn position they disengage and return instead of chasing.
_GUARD_LEASH_RADIUS: int = 8


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
    console=None,
    render_callback=None,
    player_dodge: int = 0,
) -> tuple[int, int, bool]:
    """One enemy ground turn: fire when in range and LOS, else advance.

    Mutates ``enemy_entity.pos`` in place; the caller applies the
    returned damage. Returns ``(remaining_ap, damage_dealt, fired)``.
    """

    if not enemy_weapon_id or enemy_ap <= 0:
        return (enemy_ap, 0, False)
    from ..data.ground_weapons import find_ground_weapon as _find_gw
    try:
        _ews = _find_gw(enemy_weapon_id)
    except KeyError:
        return (enemy_ap, 0, False)

    return _spend_ground_ap(
        ctx, console, render_callback, game_map,
        enemy_entity, player_pos, enemy_weapon_id, _ews,
        enemy_spec, armor_defense, player_dodge, enemy_ap,
    )


def _spend_ground_ap(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_weapon_id, _ews, enemy_spec, armor_defense, player_dodge, enemy_ap,
):
    """Run the enemy's AP loop: fire when able, else advance per AP.

    One shot per turn (matching the player's single [f] action);
    guards fall back to their post when the player leaves the leash.
    """
    _result_ap, _damage_dealt, _fired = enemy_ap, 0, False
    _cached_path: list[tuple[int, int]] | None = None
    _path_goal: tuple[int, int] | None = None
    _post = getattr(enemy_entity, 'guard_post', None)

    while _result_ap > 0:
        _shot = _try_ground_fire(
            ctx, console, render_callback, game_map,
            enemy_entity, player_pos, enemy_weapon_id, _ews,
            enemy_spec, armor_defense, player_dodge,
        )
        if _shot is not None:
            _damage_dealt, _ap_cost = _shot
            _result_ap -= _ap_cost
            _fired = True
            break
        _stepped, _cached_path, _path_goal, _halt = _ground_advance(
            ctx, console, render_callback, game_map,
            enemy_entity, player_pos, _post, _cached_path, _path_goal,
        )
        if _stepped:
            _result_ap -= 1
        if _halt:
            break

    if not _fired:
        ctx.log.add_colored(
            f"{enemy_spec.name} moves into position.",
            _ml.COLOR_ENEMY_ACTION,
        )
    return (_result_ap, _damage_dealt, _fired)


def _try_ground_fire(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_weapon_id, _ews, enemy_spec, armor_defense, player_dodge,
):
    """One shot when in range with LOS: ``(damage, ap_cost)``, else None.

    Logs the attack line and animates with a weapon-family effect and
    a floating hit/MISS number on the player.
    """
    from ._stats import _distance

    _dist = _distance(enemy_entity.pos, player_pos)
    if not (_ews and _ews.min_range <= _dist <= _ews.max_range):
        return None
    if not _has_los(
        game_map,
        enemy_entity.pos.x, enemy_entity.pos.y,
        player_pos.x, player_pos.y,
    ):
        return None  # can't shoot through walls — caller moves instead

    _hit, _damage, _popup = _roll_ground_shot(
        ctx, enemy_weapon_id, enemy_spec, armor_defense, player_dodge,
    )
    _line = _enemy_attack_line(
        enemy_spec.name, enemy_weapon_id, _ews.name,
        hit=_hit, hull_dmg=_damage,
    )
    ctx.log.add_colored(_line, _ml.COLOR_ENEMY_ACTION)
    if console is not None and render_callback is not None:
        _animate_ground_shot(
            console, ctx, game_map,
            enemy_entity.pos, player_pos,
            enemy_weapon_id, is_hit=_hit,
            damage=_popup,
            render_callback=render_callback,
        )
    return _damage, (_ews.ap_cost if _ews else 1)


def _roll_ground_shot(ctx, enemy_weapon_id, enemy_spec, armor_defense, player_dodge):
    """(hit, damage, popup) for one ground shot — miss damage is 0."""
    from ._rules_ground import _ground_hit_chance_raw, _ground_damage_raw

    _hit = RNG.randint(1, 100) <= _ground_hit_chance_raw(
        enemy_weapon_id, enemy_spec.reflexes, ctx.ground_stats.reflexes,
        target_dodge_bonus=player_dodge,
    )
    if not _hit:
        return False, 0, None
    _damage = _ground_damage_raw(
        enemy_weapon_id, enemy_spec.strength, armor_defense,
    )
    return True, _damage, _damage_popup_for(_damage, 0, False)


def _ground_advance(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    _post, _cached_path, _path_goal,
):
    """One step toward the chase goal.

    Returns ``(stepped, cached_path, path_goal, halt)``: the path is
    computed once per goal (guards head back to their post once the
    player leaves the leash radius) and recomputed when a step is
    blocked; ``halt`` ends the enemy's turn (no path, or at the player).
    """
    from ._stats import _distance

    _goal = (player_pos.x, player_pos.y)
    if _post is not None and _distance(player_pos, _post) > _GUARD_LEASH_RADIUS:
        _goal = (_post.x, _post.y)

    if _cached_path is None or _path_goal != _goal:
        _cached_path = world.find_path(
            (enemy_entity.pos.x, enemy_entity.pos.y),
            {_goal},
            game_map,
            exclude_entity=enemy_entity,
        )
        _path_goal = _goal
    if not _cached_path:
        return False, _cached_path, _path_goal, True  # no path to goal

    _nx, _ny = _cached_path.pop(0)
    if (_nx, _ny) == (player_pos.x, player_pos.y):
        return False, _cached_path, _path_goal, True  # don't move into player
    if not (game_map.is_walkable(_nx, _ny) and game_map.blocking_entity_at(
            _nx, _ny, exclude=enemy_entity) is None):
        return False, None, _path_goal, False  # blocked — recompute path
    enemy_entity.pos = world.Position(_nx, _ny)
    if render_callback is not None and console is not None:
        render_callback(console, ctx, game_map)
        _present(ctx, console)
        _responsive_sleep(animation_timing.GROUND_STEP)
    return True, _cached_path, _path_goal, False
