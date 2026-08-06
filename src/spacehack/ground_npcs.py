"""Ground NPC movement outside of combat — patrol and wander patterns.

Mirrors :mod:`npc_ships` for space NPCs. Called from ``__main__.py``
after the player moves in dungeon mode, before combat detection.

Patterns by faction attitude:
  * **Hostile** (enemy/disliked): patrol between rooms — squad leader
    picks a random walkable cell on the map, A* path there, all
    members follow the same direction. New target on arrival.
  * **Neutral / allied**: idle wander within the current room —
    random adjacent walkable cell.

Squad cohesion: entities sharing the same ``squad_id`` move as a
group. The leader's A* path is shared; followers trail in the same
direction.  Stragglers more than 4 cells from the squad centre are
pulled back toward it.
"""

from __future__ import annotations

from . import world
from .engine import RNG
from .data.npc_chars import find_npc_char as _find_nc
from .faction import spec_is_hostile as _spec_is_hostile


# Per-squad path cache: {squad_id: (target_x, target_y, path_list)}
_paths: dict[str, tuple[int, int, list[tuple[int, int]]]] = {}

# How often NPCs attempt to move (per tick).
_MOVE_CHANCE: float = 0.8


def _spec_behavior(ctx, entity: world.Entity) -> str:
    """Out-of-combat behavior for this NPC ("hunter" when unknown)."""
    _eid = getattr(entity, 'npc_char_id', '')
    if not _eid:
        return "hunter"
    try:
        return _find_nc(_eid).behavior
    except KeyError:
        return "hunter"


def _is_hostile(ctx, entity: world.Entity) -> bool:
    """True if this NPC's faction is hostile toward the player.

    Monsters (``always_hostile``) are always hostile; everyone else
    follows faction reputation. Shares logic with
    ``combat._encounter.detect_ground_combat``.
    """
    _eid = getattr(entity, 'npc_char_id', '')
    if not _eid:
        return False
    try:
        _spec = _find_nc(_eid)
    except KeyError:
        return False
    return _spec_is_hostile(ctx, _spec)


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


def _try_move_entity(
    entity: world.Entity,
    dx: int, dy: int,
    game_map: world.GameMap,
) -> bool:
    """Try to move *entity* by (dx, dy).  Returns True on success."""
    _nx = entity.pos.x + dx
    _ny = entity.pos.y + dy
    if (game_map.is_walkable(_nx, _ny)
            and game_map.entity_at(_nx, _ny, exclude=entity) is None):
        entity.pos = world.Position(_nx, _ny)
        return True
    return False


def _patrol_path(
    squad_id: str,
    leader: world.Entity,
    game_map: world.GameMap,
    *,
    cache: dict | None = None,
) -> list[tuple[int, int]]:
    """Get or compute the A* patrol path for *squad_id*.

    Uses *cache* (defaults to module-level ``_paths``) for path
    persistence across ticks.  Pass an empty dict for solos so their
    paths aren't cached.
    """
    if cache is None:
        cache = _paths

    _cached = cache.get(squad_id)
    _need_new = True
    if _cached is not None:
        _tx, _ty, _path = _cached
        if _path:
            _nx, _ny = _path[0]
            if (game_map.is_walkable(_nx, _ny)
                    and game_map.entity_at(_nx, _ny, exclude=leader) is None):
                _need_new = False

    if _need_new:
        _target = _random_walkable(game_map)
        if _target is None:
            cache.pop(squad_id, None)
            return []
        _path = world.find_path(
            (leader.pos.x, leader.pos.y), {_target}, game_map,
            exclude_entity=leader,
        )
        if not _path:
            cache.pop(squad_id, None)
            return []
        cache[squad_id] = (_target[0], _target[1], _path)
        return _path

    return _cached[2]


def _move_squad(
    members: list[world.Entity],
    game_map: world.GameMap,
    is_hostile: bool,
    squad_id: str,
) -> None:
    """Move one squad: leader patrols, followers trail, stragglers pulled."""
    if not members:
        return
    _leader = members[0]
    _lx, _ly = _leader.pos.x, _leader.pos.y

    if is_hostile:
        _path = _patrol_path(squad_id, _leader, game_map)
        if not _path:
            return
        _nx, _ny = _path[0]
        _dx = _nx - _lx
        _dy = _ny - _ly
        if abs(_dx) > 1 or abs(_dy) > 1:
            _paths.pop(squad_id, None)
            return

        # Try to move all members in the same direction.
        _leader_moved = False
        for _m in members:
            if _try_move_entity(_m, _dx, _dy, game_map):
                if _m is _leader:
                    _leader_moved = True
            else:
                # Blocked — try perpendicular slip-around.
                if _dx != 0 and _dy != 0:
                    for _sdx, _sdy in [(_dx, 0), (0, _dy)]:
                        if _try_move_entity(_m, _sdx, _sdy, game_map):
                            break
                elif _dx != 0:
                    for _sdx, _sdy in [(_dx, 1), (_dx, -1)]:
                        if _try_move_entity(_m, _sdx, _sdy, game_map):
                            break
                else:  # _dy != 0
                    for _sdx, _sdy in [(1, _dy), (-1, _dy)]:
                        if _try_move_entity(_m, _sdx, _sdy, game_map):
                            break
        if _leader_moved:
            _path.pop(0)
    else:
        # Neutral squad: each member wanders independently.
        for _m in members:
            _wander_step(_m, game_map)
        return

    # Squad cohesion: pull stragglers toward centre.
    if len(members) > 1:
        _cx = sum(m.pos.x for m in members) // len(members)
        _cy = sum(m.pos.y for m in members) // len(members)
        for _m in members:
            if max(abs(_m.pos.x - _cx), abs(_m.pos.y - _cy)) > 4:
                _pull_x = _cx + (1 if _m.pos.x < _cx else -1 if _m.pos.x > _cx else 0)
                _pull_y = _cy + (1 if _m.pos.y < _cy else -1 if _m.pos.y > _cy else 0)
                _try_move_entity(_m, _pull_x - _m.pos.x, _pull_y - _m.pos.y, game_map)


def _wander_step(entity: world.Entity, game_map: world.GameMap) -> None:
    """Move entity one cell randomly (neutral NPCs)."""
    _adj = _random_adjacent(entity, game_map)
    if _adj is not None:
        entity.pos = world.Position(*_adj)


def move_ground_npcs(ctx, game_map: world.GameMap) -> None:
    """Move ground NPCs one tick — patrol for hostiles, wander for neutrals.

    Entities sharing a ``squad_id`` move as a group — the leader's
    A* path is shared, followers trail in the same direction.
    Called after the player moves in dungeon mode.
    """
    # Prune cached paths for squads no longer on the map.
    _live_squads = {
        getattr(e, 'squad_id', '') for e in game_map.entities
        if getattr(e, 'squad_id', '')
    }
    _dead = [k for k in _paths if k not in _live_squads]
    for k in _dead:
        del _paths[k]

    # ---- Build squad map ----
    _squad_map: dict[str, list[world.Entity]] = {}
    _solos: list[world.Entity] = []
    for _e in game_map.entities:
        if _e is ctx.player:
            continue
        if not getattr(_e, 'npc_char_id', ''):
            continue
        # Guards and ambushers hold their position out of combat —
        # only hunters patrol (and neutrals wander).
        if _spec_behavior(ctx, _e) in ("guard", "ambusher"):
            continue
        if RNG.random() >= _MOVE_CHANCE:
            continue
        _sid = getattr(_e, 'squad_id', '')
        if _sid:
            _squad_map.setdefault(_sid, []).append(_e)
        else:
            _solos.append(_e)

    # ---- Move squads ----
    for _sid, _members in _squad_map.items():
        if not _members:
            continue
        _hostile = _is_hostile(ctx, _members[0])
        _move_squad(_members, game_map, _hostile, _sid)

    # ---- Move solos ----
    for _e in _solos:
        if _is_hostile(ctx, _e):
            # Solo-hostile: patrol without caching (A* per tick is fine for singles).
            _path = _patrol_path("", _e, game_map, cache={})
            if _path:
                _nx, _ny = _path[0]
                _dx = _nx - _e.pos.x
                _dy = _ny - _e.pos.y
                if abs(_dx) <= 1 and abs(_dy) <= 1:
                    _try_move_entity(_e, _dx, _dy, game_map)
        else:
            _wander_step(_e, game_map)
