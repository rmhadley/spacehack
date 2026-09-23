"""Ground combat enemy AI — movement + fire logic for on-foot enemies.

Mirrors :mod:`combat._ai` which handles ship enemy behavior. The
universal loop manages RANGE (doc 48 SETTLED 26): fire when inside the
rolled weapon's band with LOS (one shot per turn), close beyond max,
back off inside min, reposition with leftover AP after the shot —
melee never repositions (no knife-dancers). Guards leash to their post
at the rolled weapon's ``max_range + 2`` (SETTLED 18/37).
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

_STEP_DIRS: tuple[tuple[int, int], ...] = (
    (-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1),
)


async def run_ground_enemy_turn(
    ctx,
    *,
    enemy_weapon_id: str,
    enemy_weapon_quality: int = 0,
    enemy_spec,
    enemy_stats,
    enemy_ap: int,
    player_pos: world.Position,
    enemy_entity: world.Entity,
    game_map: world.GameMap,
    armor_defense: int,
    console=None,
    render_callback=None,
    player_dodge: int = 0,
) -> tuple[int, int, bool]:
    """One enemy ground turn: manage range and fire per AP (SETTLED 26
    — the weapon's band decides close / hold / back off / dance).

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

    return await _spend_ground_ap(
        ctx, console, render_callback, game_map,
        enemy_entity, player_pos, enemy_weapon_id, _ews,
        enemy_spec, enemy_stats, armor_defense, player_dodge, enemy_ap,
        enemy_weapon_quality,
    )


async def _attempt_fire(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_weapon_id, _ews, enemy_spec, enemy_stats, armor_defense,
    player_dodge, enemy_weapon_quality, _dist, _los,
):
    """Fire when in band with LOS; the shot tuple, else None. The gate
    duplicates :func:`_try_ground_fire`'s internal check deliberately —
    pre-computing skips the await when the shot is not legal."""
    if not (_ews.min_range <= _dist <= _ews.max_range and _los):
        return None
    return await _try_ground_fire(
        ctx, console, render_callback, game_map,
        enemy_entity, player_pos, enemy_weapon_id, _ews,
        enemy_spec, enemy_stats, armor_defense, player_dodge,
        enemy_weapon_quality,
    )


async def _spend_ground_ap(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_weapon_id, _ews, enemy_spec, enemy_stats, armor_defense,
    player_dodge, enemy_ap, enemy_weapon_quality=0,
):
    """Run the enemy's AP loop (SETTLED 26) — one shot per turn in the
    weapon's band with LOS; otherwise manage range (see module header)."""
    _result_ap, _damage_dealt, _fired = enemy_ap, 0, False
    _cached_path: list[tuple[int, int]] | None = None
    _path_goal: tuple[int, int] | None = None

    while _result_ap > 0:
        _dist = _dist_to(enemy_entity.pos.x, enemy_entity.pos.y, player_pos)
        _los = _has_los(game_map, enemy_entity.pos.x, enemy_entity.pos.y,
                        player_pos.x, player_pos.y)
        _shot = None if _fired else await _attempt_fire(
            ctx, console, render_callback, game_map, enemy_entity,
            player_pos, enemy_weapon_id, _ews, enemy_spec, enemy_stats,
            armor_defense, player_dodge, enemy_weapon_quality, _dist, _los,
        )
        if _shot is not None:
            _damage_dealt, _ap_cost = _shot
            _result_ap -= _ap_cost
            _fired = True
            continue
        _stepped, _cached_path, _path_goal, _halt = await _range_step(
            ctx, console, render_callback, game_map, enemy_entity,
            player_pos, _ews, _dist, _los, _fired,
            _cached_path, _path_goal,
        )
        if _halt or not _stepped:
            break
        _result_ap -= 1

    if not _fired:
        ctx.log.add_colored(
            f"{enemy_spec.name} moves into position.", _ml.COLOR_ENEMY_ACTION,
        )
    return (_result_ap, _damage_dealt, _fired)


async def _range_step(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    _ews, _dist, _los, _fired, _cached_path, _path_goal,
):
    """One movement decision by range (SETTLED 26), as the uniform
    ``(stepped, cached_path, path_goal, halt)`` quad: back off inside
    min, close beyond max or without LOS, else the post-shot
    reposition dance (ranged only — melee holds, no knife-dancers).
    The off-path arms drop the cached A* path (the entity now stands
    beside it) so a later advance recomputes instead of teleporting."""
    if _dist < _ews.min_range:
        return (
            await _back_off_step(
                ctx, console, render_callback, game_map, enemy_entity,
                player_pos, _ews,
            ), None, _path_goal, False,
        )
    if _dist > _ews.max_range or not _los:
        return await _ground_advance(
            ctx, console, render_callback, game_map, enemy_entity,
            player_pos, _cached_path, _path_goal,
        )
    if _fired and _ews.max_range > 1:
        return (
            await _reposition_step(
                ctx, console, render_callback, game_map, enemy_entity,
                player_pos, _ews,
            ), None, _path_goal, False,
        )
    return (False, _cached_path, _path_goal, False)


def _free_cell(game_map, enemy_entity, x: int, y: int) -> bool:
    """A walkable cell no body stands on."""
    return game_map.is_walkable(x, y) and game_map.blocking_entity_at(
        x, y, exclude=enemy_entity,
    ) is None


async def _step_to(
    ctx, console, render_callback, game_map, enemy_entity, x, y,
) -> bool:
    """Move one cell and present the step (combat animates every move)."""
    enemy_entity.pos = world.Position(x, y)
    if render_callback is not None and console is not None:
        render_callback(console, ctx, game_map)
        _present(ctx, console)
        await _responsive_sleep(animation_timing.GROUND_STEP, ctx.context)
    return True


def _dist_to(x: int, y: int, player_pos) -> float:
    from ._stats import _distance

    return _distance(world.Position(x, y), player_pos)


async def _back_off_step(
    ctx, console, render_callback, game_map, enemy_entity, player_pos, _ews,
):
    """One step toward restoring ``>= min_range`` — restoring steps
    first, LOS-keeping preferred, then any step that strictly widens
    the gap (SETTLED 26). Pinned with no qualifying cell: inert, by
    design — cornering a ranged face is the counter-play."""
    def _rank(cell):
        _x, _y = cell
        _d = _dist_to(_x, _y, player_pos)
        return (
            _d >= _ews.min_range,
            _has_los(game_map, _x, _y, player_pos.x, player_pos.y),
            _d,
        )

    _cur = _dist_to(
        enemy_entity.pos.x, enemy_entity.pos.y, player_pos,
    )
    _pool = [
        (enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy)
        for _dx, _dy in _STEP_DIRS
        if _free_cell(
            game_map, enemy_entity,
            enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy,
        )
        and (
            _dist_to(enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy,
                     player_pos) >= _ews.min_range
            or _dist_to(enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy,
                        player_pos) > _cur
        )
    ]
    if not _pool:
        return False
    _x, _y = max(_pool, key=_rank)
    return await _step_to(
        ctx, console, render_callback, game_map, enemy_entity, _x, _y,
    )


async def _reposition_step(
    ctx, console, render_callback, game_map, enemy_entity, player_pos, _ews,
):
    """One random in-band LOS-keeping step — the skirmisher dance that
    leftover AP buys after the one-shot cap (SETTLED 26). No such cell:
    hold position."""
    _pool = [
        (enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy)
        for _dx, _dy in _STEP_DIRS
        if _free_cell(
            game_map, enemy_entity,
            enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy,
        )
        and _ews.min_range <= _dist_to(
            enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy, player_pos,
        ) <= _ews.max_range
        and _has_los(
            game_map, enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy,
            player_pos.x, player_pos.y,
        )
    ]
    if not _pool:
        return False
    _x, _y = RNG.choice(_pool)
    return await _step_to(
        ctx, console, render_callback, game_map, enemy_entity, _x, _y,
    )


async def _try_ground_fire(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_weapon_id, _ews, enemy_spec, enemy_stats, armor_defense,
    player_dodge, enemy_weapon_quality=0,
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
    from .. import noise

    # Firing report at the shooter (SETTLED 22, symmetric): third
    # parties converge on the fight — enemy fire never logs the
    # player-facing reaction line.
    noise.emit(
        ctx, game_map, enemy_entity.pos, enemy_weapon_id, by_player=False,
    )
    _hit, _damage, _popup = _roll_ground_shot(
        ctx, enemy_weapon_id, enemy_stats, armor_defense, player_dodge,
        enemy_weapon_quality,
    )
    await _present_enemy_shot(
        ctx, console, render_callback, game_map,
        enemy_entity, player_pos, enemy_weapon_id, enemy_weapon_quality,
        enemy_spec, _hit, _damage, _popup,
    )
    return _damage, (_ews.ap_cost if _ews else 1)


async def _present_enemy_shot(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_weapon_id, enemy_weapon_quality, enemy_spec, hit, damage, popup,
) -> None:
    """Log and animate one enemy shot at the wielded variant's label."""
    from ..ground_equipment import display_name

    _line = _enemy_attack_line(
        enemy_spec.name, enemy_weapon_id,
        display_name("weapon", enemy_weapon_id, enemy_weapon_quality),
        hit=hit, hull_dmg=damage,
    )
    ctx.log.add_colored(_line, _ml.COLOR_ENEMY_ACTION)
    if console is not None and render_callback is not None:
        await _animate_ground_shot(
            console, ctx, game_map,
            enemy_entity.pos, player_pos,
            enemy_weapon_id, is_hit=hit,
            damage=popup,
            render_callback=render_callback,
        )


def _roll_ground_shot(
    ctx, enemy_weapon_id, enemy_stats, armor_defense, player_dodge,
    enemy_weapon_quality=0,
):
    """(hit, damage, popup) for one ground shot — miss damage is 0.

    ``enemy_stats`` is the instance's band-derived block (doc 48
    SETTLED 35). The wielded weapon fights at its equip-time rolled
    quality (SETTLED 13): what was firing at you is what drops.
    """
    from ._ground_math import ground_damage_raw, ground_hit_chance_raw

    _hit = RNG.randint(1, 100) <= ground_hit_chance_raw(
        enemy_weapon_id, enemy_stats.reflexes, ctx.ground_stats.reflexes,
        target_dodge_bonus=player_dodge, quality=enemy_weapon_quality,
    )
    if not _hit:
        return False, 0, None
    _damage = ground_damage_raw(
        enemy_weapon_id, enemy_stats.strength, armor_defense,
        quality=enemy_weapon_quality,
    )
    return True, _damage, _damage_popup_for(_damage, 0, False)


def _chase_goal(
    player_pos, guard_post, enemy_entity, game_map=None,
) -> tuple[int, int]:
    """The chase goal: the player, or the guard post beyond the leash
    — the entity's rolled weapon ``max_range + 2`` (doc 48 SETTLED
    18/37; the hardcoded radius 8 retired with it)."""
    from ._stats import _distance

    if guard_post is not None:
        from .. import noise

        if _distance(player_pos, guard_post) > noise.guard_leash(
            enemy_entity, game_map,
        ):
            return (guard_post.x, guard_post.y)
    return (player_pos.x, player_pos.y)


async def _ground_advance(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    _cached_path, _path_goal,
):
    """One step toward the chase goal.

    Returns ``(stepped, cached_path, path_goal, halt)``: the path is
    computed once per goal and recomputed when a step is blocked;
    ``halt`` ends the enemy's turn (no path, or at the player).
    """
    _goal = _chase_goal(
        player_pos, getattr(enemy_entity, 'guard_post', None),
        enemy_entity, game_map,
    )

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
    if not _free_cell(game_map, enemy_entity, _nx, _ny):
        return False, None, _path_goal, False  # blocked — recompute path
    await _step_to(
        ctx, console, render_callback, game_map, enemy_entity, _nx, _ny,
    )
    return True, _cached_path, _path_goal, False
