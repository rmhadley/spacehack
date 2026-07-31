"""Ground NPC movement outside of combat — patrol and wander patterns.

Mirrors :mod:`npc_ships` for space NPCs. Called from ``__main__.py``
after the player moves in dungeon mode, before combat detection.

Patterns by faction attitude:
  * **Hostile** (enemy/disliked): patrol between rooms — pick a
    random walkable cell on the map, A* path there, follow step by
    step. Pick new target on arrival.
  * **Neutral / allied**: idle wander within the current room —
    random adjacent walkable cell.
"""

from __future__ import annotations

from . import world
from .engine import RNG
from .data.npc_chars import find_npc_char as _find_nc
from .faction import get_attitude as _get_attitude


# Per-entity path cache: {id(entity): (target_x, target_y, path_list)}
_paths: dict[int, tuple[int, int, list[tuple[int, int]]]] = {}

# How often NPCs attempt to move (per tick).
_MOVE_CHANCE: float = 0.8


def _is_hostile(ctx, entity: world.Entity) -> bool:
    """True if this NPC's faction is hostile toward the player."""
    _eid = getattr(entity, 'npc_char_id', '')
    if not _eid:
        return False
    try:
        _spec = _find_nc(_eid)
    except KeyError:
        return False
    _rep = ctx.faction_reputation.get(_spec.faction, 0)
    return _get_attitude(_rep) in ('enemy', 'disliked')


def _random_walkable(game_map: world.GameMap) -> tuple[int, int] | None:
    """Return a random walkable cell on the entire map, or None."""
    _attempts = 50
    for _ in range(_attempts):
        _x = RNG.randint(0, game_map.width - 1)
        _y = RNG.randint(0, game_map.height - 1)
        if game_map.is_walkable(_x, _y) and game_map.entity_at(_x, _y) is None:
            return (_x, _y)
    return None


def _random_adjacent(
    entity: world.Entity, game_map: world.GameMap,
) -> tuple[int, int] | None:
    """Return a random adjacent walkable unoccupied cell, or None."""
    _dirs = [(-1, 0), (1, 0), (0, -1), (0, 1),
             (-1, -1), (1, -1), (-1, 1), (1, 1)]
    RNG.shuffle(_dirs)
    for _dx, _dy in _dirs:
        _nx = entity.pos.x + _dx
        _ny = entity.pos.y + _dy
        if game_map.is_walkable(_nx, _ny) and game_map.entity_at(_nx, _ny, exclude=entity) is None:
            return (_nx, _ny)
    return None


def _patrol_step(
    entity: world.Entity,
    game_map: world.GameMap,
) -> None:
    """Move entity one step along its patrol path (hostile NPCs).

    Picks a new random target + A* path when the current path is
    exhausted or blocked.
    """
    _eid = id(entity)
    _cached = _paths.get(_eid)

    # Check if we need a new target: no path, path empty, or path blocked.
    _need_new = True
    if _cached is not None:
        _tx, _ty, _path = _cached
        if _path:
            # Verify next step is still walkable.
            _nx, _ny = _path[0]
            if (game_map.is_walkable(_nx, _ny)
                    and game_map.entity_at(_nx, _ny, exclude=entity) is None):
                _need_new = False

    if _need_new:
        _target = _random_walkable(game_map)
        if _target is None:
            return
        _tx, _ty = _target
        _path = world.find_path(
            (entity.pos.x, entity.pos.y), {_target}, game_map,
            exclude_entity=entity,
        )
        if not _path:
            return
        _paths[_eid] = (_tx, _ty, _path)
        _cached = (_tx, _ty, _path)

    _tx, _ty, _path = _cached
    if not _path:
        return

    _nx, _ny = _path.pop(0)
    # Re-verify just in case.
    if (game_map.is_walkable(_nx, _ny)
            and game_map.entity_at(_nx, _ny, exclude=entity) is None):
        entity.pos = world.Position(_nx, _ny)        # If blocked, path will be recomputed next tick.
    # On collision, preserve the path so the NPC retries the same
    # step next tick — don't recompute A* just because a cell was
    # temporarily occupied.


def _wander_step(entity: world.Entity, game_map: world.GameMap) -> None:
    """Move entity one cell randomly (neutral NPCs)."""
    _adj = _random_adjacent(entity, game_map)
    if _adj is not None:
        entity.pos = world.Position(*_adj)


def move_ground_npcs(ctx, game_map: world.GameMap) -> None:
    """Move ground NPCs one tick — patrol for hostiles, wander for neutrals.

    Called after the player moves in dungeon mode. Skips NPCs
    without ``npc_char_id``.  80% move chance per NPC per tick
    (same throttle as space).
    """
    # Prune cached paths for entities no longer on the map.
    _live_ids = {id(e) for e in game_map.entities}
    _dead = [k for k in _paths if k not in _live_ids]
    for k in _dead:
        del _paths[k]

    for _e in game_map.entities:
        if _e is ctx.player:
            continue
        if not getattr(_e, 'npc_char_id', ''):
            continue
        if RNG.random() >= _MOVE_CHANCE:
            continue

        if _is_hostile(ctx, _e):
            _patrol_step(_e, game_map)
        else:
            _wander_step(_e, game_map)
