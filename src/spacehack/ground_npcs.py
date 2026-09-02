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
direction. Stragglers more than 4 cells from the squad centre that
could not take a patrol step this tick get a one-cell pull toward it
(slipping around obstacles), so a squad member never teleports back
to the pack — and the pull never undoes a member's own patrol
progress.
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
_LAST_SEEN_TICKS: int = 5
_PURSUIT_BEHAVIORS: frozenset[str] = frozenset(("hunter",))


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
        if game_map.is_walkable(_x, _y) and game_map.blocking_entity_at(_x, _y) is None:
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
        if game_map.is_walkable(_nx, _ny) and game_map.blocking_entity_at(_nx, _ny, exclude=entity) is None:
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
            and game_map.blocking_entity_at(_nx, _ny, exclude=entity) is None):
        entity.pos = world.Position(_nx, _ny)
        return True
    return False


def _cached_path_is_usable(
    cached, leader: world.Entity, game_map: world.GameMap,
) -> bool:
    """Whether a cached ``(tx, ty, path)`` entry can still be walked."""
    if cached is None:
        return False
    _tx, _ty, path = cached
    if not path:
        return False
    nx, ny = path[0]
    return (game_map.is_walkable(nx, ny)
            and game_map.blocking_entity_at(nx, ny, exclude=leader) is None)


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
    if _cached_path_is_usable(_cached, leader, game_map):
        return _cached[2]

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


def _last_seen_goal(entity: world.Entity) -> tuple[int, int] | None:
    """Return an active remembered player cell for a pursuit-capable NPC."""
    _pos = getattr(entity, "last_seen_pos", None)
    if getattr(entity, "last_seen_ticks", 0) <= 0 or _pos is None:
        return None
    return (_pos.x, _pos.y)


def _clear_last_seen(entity: world.Entity) -> None:
    """Discard an NPC's expired or reached last-seen player cell."""
    entity.last_seen_pos = None
    entity.last_seen_ticks = 0


def _is_pursuit_capable(entity: world.Entity) -> bool:
    """Return whether a known NPC catalog entry can pursue memory."""
    _eid = getattr(entity, "npc_char_id", "")
    if not _eid:
        return False
    try:
        return _find_nc(_eid).behavior in _PURSUIT_BEHAVIORS
    except KeyError:
        return False


def remember_last_seen(
    entities: list[world.Entity], player_pos: world.Position,
) -> int:
    """Stamp a bounded pursuit memory onto hunter entities.

    Guards and ambushers intentionally do not receive memory: guards defend
    their post and ambushers remain a stationary surprise. Returns the number
    of entities stamped.
    """
    _stamped = 0
    for _entity in entities:
        if getattr(_entity, "npc_char_id", "") == "":
            continue
        if not _is_pursuit_capable(_entity):
            continue
        _entity.last_seen_pos = world.Position(player_pos.x, player_pos.y)
        _entity.last_seen_ticks = _LAST_SEEN_TICKS
        _stamped += 1
    return _stamped


def _pursuit_path(
    entity: world.Entity,
    game_map: world.GameMap,
    goal: tuple[int, int],
) -> list[tuple[int, int]]:
    """Find a path from an NPC to a remembered player cell."""
    return world.find_path(
        (entity.pos.x, entity.pos.y), {goal}, game_map,
        exclude_entity=entity,
    ) or []


def _move_toward_last_seen(entity: world.Entity, game_map: world.GameMap) -> bool:
    """Take one pursuit step; return whether the memory remains active."""
    _goal = _last_seen_goal(entity)
    if _goal is None:
        return False
    if (entity.pos.x, entity.pos.y) == _goal:
        _clear_last_seen(entity)
        return False
    _path = _pursuit_path(entity, game_map, _goal)
    if not _path:
        _clear_last_seen(entity)
        return False
    _nx, _ny = _path[0]
    _try_move_entity(entity, _nx - entity.pos.x, _ny - entity.pos.y, game_map)
    entity.last_seen_ticks -= 1
    if entity.last_seen_ticks <= 0 or (entity.pos.x, entity.pos.y) == _goal:
        _clear_last_seen(entity)
    return True


def _rejoin_stragglers(
    members: list[world.Entity],
    start_positions: dict,
    game_map: world.GameMap,
) -> None:
    """Step wedged squad members ONE cell toward the squad centre.

    Only members that could not take a patrol step this tick — yanking
    back a member that just moved fights the patrol and freezes the
    pack. Slipping around obstacles keeps the unstick purpose: a member
    wedged against a wall can still rejoin the pack.
    """
    if len(members) < 2:
        return
    _cx = sum(m.pos.x for m in members) // len(members)
    _cy = sum(m.pos.y for m in members) // len(members)
    for _m in members:
        if (_m.pos == start_positions[id(_m)]
                and max(abs(_m.pos.x - _cx), abs(_m.pos.y - _cy)) > 4):
            _dx = 1 if _m.pos.x < _cx else -1 if _m.pos.x > _cx else 0
            _dy = 1 if _m.pos.y < _cy else -1 if _m.pos.y > _cy else 0
            world.try_step_with_slip(_m, game_map, _dx, _dy)


def _patrol_step(
    members: list[world.Entity],
    game_map: world.GameMap,
    squad_id: str,
) -> None:
    """March one hostile squad along its cached patrol path."""
    _leader = members[0]
    _path = _patrol_path(squad_id, _leader, game_map)
    if not _path:
        return
    _nx, _ny = _path[0]
    _dx = _nx - _leader.pos.x
    _dy = _ny - _leader.pos.y
    if abs(_dx) > 1 or abs(_dy) > 1:
        _paths.pop(squad_id, None)
        return

    # Try to move all members in the same direction (direct step with a
    # one-cell perpendicular slip when the cell is blocked).
    _start_positions = {id(_m): _m.pos for _m in members}
    _leader_moved = False
    for _m in members:
        _direct = world.try_step_with_slip(_m, game_map, _dx, _dy)
        if _m is _leader and _direct:
            _leader_moved = True
    if _leader_moved:
        _path.pop(0)
    _rejoin_stragglers(members, _start_positions, game_map)


def _move_squad(
    members: list[world.Entity],
    game_map: world.GameMap,
    is_hostile: bool,
    squad_id: str,
) -> None:
    """Move one squad: pursue last-seen cells, patrol, or wander."""
    if not members:
        return
    _leader = members[0]

    if not is_hostile:
        # Neutral squad: each member wanders independently.
        for _m in members:
            _wander_step(_m, game_map)
        return
    if _last_seen_goal(_leader) is not None:
        for _member in members:
            _move_toward_last_seen(_member, game_map)
        return
    _patrol_step(members, game_map, squad_id)


def _wander_step(entity: world.Entity, game_map: world.GameMap) -> None:
    """Move entity one cell randomly (neutral NPCs)."""
    _adj = _random_adjacent(entity, game_map)
    if _adj is not None:
        entity.pos = world.Position(*_adj)


def _prune_dead_squad_paths(game_map: world.GameMap) -> None:
    """Drop cached paths for squads no longer on the map."""
    _live_squads = {
        getattr(e, 'squad_id', '') for e in game_map.entities
        if getattr(e, 'squad_id', '')
    }
    for k in [k for k in _paths if k not in _live_squads]:
        del _paths[k]


def _is_movable_this_tick(ctx, entity: world.Entity) -> bool:
    """Whether the patrol pass should move ``entity`` this tick.

    Dormant prison security stands where placed; combat participants
    are driven by the combat AI; guards/ambushers hold position; and
    idle NPCs skip some ticks via the move-chance roll.
    """
    if getattr(entity, 'powered_down', False):
        return False  # dormant prison security (doc 30)
    if getattr(entity, 'combat_locked', False):
        return False
    if _spec_behavior(ctx, entity) in ("guard", "ambusher"):
        return False
    return _last_seen_goal(entity) is not None or RNG.random() < _MOVE_CHANCE


def _partition_movers(ctx, game_map) -> tuple[dict, list]:
    """Split this tick's movable NPCs into squads and solos."""
    _squad_map: dict[str, list[world.Entity]] = {}
    _solos: list[world.Entity] = []
    for _e in game_map.entities:
        if _e is ctx.player or not getattr(_e, 'npc_char_id', ''):
            continue
        if not _is_movable_this_tick(ctx, _e):
            continue
        _sid = getattr(_e, 'squad_id', '')
        if _sid:
            _squad_map.setdefault(_sid, []).append(_e)
        else:
            _solos.append(_e)
    return _squad_map, _solos


def _move_solo(_e: world.Entity, ctx, game_map: world.GameMap) -> None:
    """Move one squadless NPC: pursue, patrol (uncached), or wander."""
    if not _is_hostile(ctx, _e):
        _wander_step(_e, game_map)
        return
    if _last_seen_goal(_e) is not None:
        _move_toward_last_seen(_e, game_map)
        return
    # Solo-hostile: patrol without caching (A* per tick is fine for singles).
    _path = _patrol_path("", _e, game_map, cache={})
    if _path:
        _nx, _ny = _path[0]
        _dx = _nx - _e.pos.x
        _dy = _ny - _e.pos.y
        if abs(_dx) <= 1 and abs(_dy) <= 1:
            _try_move_entity(_e, _dx, _dy, game_map)


def move_ground_npcs(ctx, game_map: world.GameMap) -> None:
    """Move ground NPCs one tick — patrol for hostiles, wander for neutrals.

    Entities sharing a ``squad_id`` move as a group — the leader's
    A* path is shared, followers trail in the same direction.
    Called after the player moves in dungeon mode.
    """
    _prune_dead_squad_paths(game_map)
    _squad_map, _solos = _partition_movers(ctx, game_map)
    for _sid, _members in _squad_map.items():
        if _members:
            _move_squad(_members, game_map, _is_hostile(ctx, _members[0]), _sid)
    for _e in _solos:
        _move_solo(_e, ctx, game_map)
