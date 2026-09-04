"""Delve site mechanics: authored camp landmarks + quest cache placement.

Split from _act0 (module-size ratchet): everything that stamps a step's
delve_layout_id/variants and places the quest cache + its guardian.
"""

from __future__ import annotations

from collections import Counter, deque

from .. import dungeon
from .. import landmark
from .. import world
from ..data.main_quest import find_main_quest_step
from ._core import _active_objective_step


def _farthest_walkable(game_map: world.GameMap, spawn: world.Position) -> world.Position:
    """Walkable cell farthest from ``spawn`` (BFS over walkable tiles)."""
    _start = (spawn.x, spawn.y)
    if not game_map.tiles[_start[1]][_start[0]].walkable:
        for _yy in range(game_map.height):
            for _xx in range(game_map.width):
                if game_map.tiles[_yy][_xx].walkable:
                    _start = (_xx, _yy)
                    break
            if game_map.tiles[_start[1]][_start[0]].walkable:
                break
    _dist: dict[tuple[int, int], int] = {_start: 0}
    _queue: deque[tuple[int, int]] = deque([_start])
    _far = _start
    while _queue:
        _x, _y = _queue.popleft()
        _d = _dist[(_x, _y)]
        if _d > _dist[_far]:
            _far = (_x, _y)
        for _nx, _ny in ((_x + 1, _y), (_x - 1, _y), (_x, _y + 1), (_x, _y - 1)):
            if not (0 <= _nx < game_map.width and 0 <= _ny < game_map.height):
                continue
            if (_nx, _ny) in _dist:
                continue
            if game_map.tiles[_ny][_nx].walkable:
                _dist[(_nx, _ny)] = _d + 1
                _queue.append((_nx, _ny))
    return world.Position(_far[0], _far[1])

def _door_room_cells(game_map: world.GameMap, door_pos: world.Position, *, cap: int = 40) -> list[world.Position]:
    """BFS through walkable cells from the door — the door's room.

    Walls and doors stop expansion; cells are returned nearest-first,
    so the first entries surround the door itself.
    """
    _queue: deque[tuple[int, int]] = deque([(door_pos.x, door_pos.y)])
    _seen: set[tuple[int, int]] = {(door_pos.x, door_pos.y)}
    _cells: list[world.Position] = []
    while _queue and len(_cells) < cap:
        _x, _y = _queue.popleft()
        _cells.append(world.Position(_x, _y))
        for _nx, _ny in ((_x + 1, _y), (_x - 1, _y), (_x, _y + 1), (_x, _y - 1)):
            if not (0 <= _nx < game_map.width and 0 <= _ny < game_map.height):
                continue
            if (_nx, _ny) in _seen:
                continue
            _tile = game_map.tiles[_ny][_nx]
            if not _tile.walkable or _tile.kind in ("dungeon_door", "breach"):
                continue
            _seen.add((_nx, _ny))
            _queue.append((_nx, _ny))
    return _cells




def _spawn_squad_near(
    game_map: world.GameMap,
    near_pos: world.Position,
    *,
    enemy_id: str,
    count: int,
    label: str,
    room_cap: int = 40,
) -> int:
    """Scatter ``count`` copies of ``enemy_id`` in the room around ``near_pos``.

    Shared by the Mars door ambush and the quest-cache guardians: a
    nearest-first BFS from ``near_pos`` (``room_cap`` cells), occupied
    cells excluded, all members sharing one ``squad_id`` so the group
    joins a single ground-combat encounter. Spawns on the given map —
    cached interiors keep the squad across save/load and re-entry.
    Returns how many were placed.
    """
    from ..data.npc_chars import find_npc_char as _fnc
    try:
        _spec = _fnc(enemy_id)
    except KeyError:
        return 0
    _room = _door_room_cells(game_map, near_pos, cap=room_cap)
    if not _room:
        return 0
    from ..engine import RNG as _RNG
    _occupied = {(e.pos.x, e.pos.y) for e in game_map.entities}
    _squad_id = f"{label}_{_RNG.randint(10000, 99999)}"
    return dungeon._scatter_squad(
        game_map.entities,
        _occupied,
        enemy_id=enemy_id,
        cells=[(_cell.x, _cell.y) for _cell in _room],
        count=count,
        squad_id=_squad_id,
        char=_spec.char,
        fg=_spec.fg,
    )

def _spawn_cache_guardian(
    game_map: world.GameMap,
    near_pos: world.Position,
    planet_id: str,
) -> int:
    """Spawn the planet's quest-cache guardian squad near ``near_pos``.

    Reads the guardian pool + count from the planet's ``dungeon_params``
    (empty pool = no guardian). Called at generation time, so the
    guardian persists via the interior cache (save/load safe).
    """
    from ..data.planets import find_planet_spec as _fps
    try:
        _pspec = _fps(planet_id)
    except KeyError:
        return 0
    _params = getattr(_pspec, "dungeon_params", None)
    _pool = tuple(getattr(_params, "cache_guardian_pool", ()) or ())
    if not _pool:
        return 0
    from ..engine import RNG as _RNG
    _eid = _RNG.choice(_pool)
    _count = getattr(_params, "cache_guardian_count", 1)
    # The 10 cells nearest the cache keep the squad in the cache room
    # (a wide BFS can leak it far down a corridor, away from what it
    # is guarding).
    return _spawn_squad_near(
        game_map, near_pos,
        enemy_id=_eid, count=_count, label="cache_guardian",
        room_cap=10,
    )

# ---------------------------------------------------------------------------
# Delve site preparation
# ---------------------------------------------------------------------------

def _delve_layout_candidates(layout_id: str, variants) -> list[str]:
    """Ordered stamp candidates for a delve camp: the weighted pick
    first, then the remaining variants in declared order; a bare
    ``delve_layout_id`` stands alone. Later candidates are fallbacks
    when an earlier one cannot route — the delve must never fail.
    """
    if not variants:
        return [layout_id] if layout_id else []
    from ..engine import RNG as _RNG
    from ..data.dungeon_extensions import LandmarkVariant as _LV
    _pick = landmark.choose_weighted_variant(
        tuple(_LV(_lid, _weight) for _lid, _weight in variants),
        _RNG.random(),
    )
    return [_pick] + [_lid for _lid, _ in variants if _lid != _pick]


def _camp_or_far_cache(
    game_map: world.GameMap, spawn: world.Position,
    layout_id: str, variants: tuple = (),
) -> world.Position:
    """The cache position: inside the step's authored camp landmark if
    one stamped cleanly, else the farthest walkable cell.

    An authored QUEST_CACHE marker in the layout owns the spot; without
    one, the camp's deepest interior cell (farthest from its door)
    holds the cache so the guardians end up holding the room around
    it. Layout candidates come from the step's ``delve_layout_variants``
    (weighted, one chosen per build) or its ``delve_layout_id`` — data,
    not a planet->layout dict.
    """
    for _candidate in _delve_layout_candidates(layout_id, variants):
        try:
            _asset = landmark.load_landmark(_candidate)
            _stamp = landmark.stamp_landmark(game_map, _asset, spawn)
        except ValueError:
            _stamp = None
        if _stamp is not None:
            game_map.landmark_footprint = (
                set(getattr(game_map, "landmark_footprint", ()) or ())
                | set(_stamp.footprint)
            )
            _marker = _cache_marker_cell(game_map, _stamp.footprint)
            if _marker is not None:
                return _marker
            _deepest = _deepest_interior_cell(
                game_map, _stamp.footprint, _stamp.entrance,
            )
            if _deepest is not None:
                return _deepest
    return _farthest_walkable(game_map, spawn)


def _deepest_interior_cell(game_map, footprint, door) -> world.Position | None:
    """The interior cell farthest from the entrance (marker-less camps),
    so the guardians end up holding the room around the cache."""
    _interior = [
        (x, y)
        for x, y in footprint
        if game_map.in_bounds(x, y)
        and game_map.tiles[y][x].walkable
    ]
    if not _interior:
        return None
    _cx, _cy = max(
        _interior,
        key=lambda c: (
            abs(c[0] - door.x) + abs(c[1] - door.y), c[1], c[0],
        ),
    )
    return world.Position(_cx, _cy)


def _cache_marker_cell(
    game_map: world.GameMap, footprint,
) -> world.Position | None:
    """The authored quest-cache marker inside a stamped landmark.

    Exactly one ``quest_cache`` tile may mark where the step's cache
    lands; the marker cell is normalized to the landmark's dominant
    floor so only the cache entity renders there (the marker tile
    must not linger once the cache is looted).
    """

    _cells = [
        (x, y) for x, y in footprint
        if game_map.in_bounds(x, y)
        and game_map.tiles[y][x].kind == "quest_cache"
    ]
    if len(_cells) != 1:
        return None
    _floors = Counter(
        game_map.tiles[y][x]
        for x, y in footprint
        if game_map.in_bounds(x, y)
        and game_map.tiles[y][x].walkable
        and game_map.tiles[y][x].kind != "quest_cache"
    )
    _x, _y = _cells[0]
    game_map.tiles[_y][_x] = (
        _floors.most_common(1)[0][0] if _floors else world.DUNGEON_FLOOR
    )
    return world.Position(_x, _y)


def prepare_delve_site(
    ctx,
    game_map: world.GameMap,
    spawn: world.Position,
    planet_id: str,
) -> bool:
    """Place the quest cache for planet_id's active delve step."""
    _step_id = _active_objective_step(ctx, "delve", planet_id=planet_id)
    if _step_id is None:
        return False
    _step = find_main_quest_step(_step_id)
    _cache_pos = _camp_or_far_cache(
        game_map, spawn, _step.delve_layout_id, _step.delve_layout_variants,
    )
    _cache = world.Entity(
        char="%",
        fg=(255, 215, 0),
        pos=_cache_pos,
        name="Quest Cache",
        width=1, height=1,
        loot_data={"goods": list(_step.delve_good_ids)},
    )
    _cache.main_quest_step_id = _step_id
    game_map.entities.append(_cache)
    # The planet's guardian holds the cache room — one squad, placed at
    # generation time so it persists via the interior cache.
    _spawn_cache_guardian(game_map, _cache_pos, planet_id)
    return True
