"""Hand-authored landmark loading and placement for procedural dungeons.

Landmarks are small ``.layout`` assets that are stamped into a generated
surface map.  The stamp owns both the visual footprint and the connection
back to the generated dungeon, so a landmark is reachable before the map is
cached in ``GameContext.interiors``.
"""

from __future__ import annotations

import copy
import heapq
from collections import deque
import pathlib
import sys
from dataclasses import dataclass

from . import dungeon
from . import world


if getattr(sys, "frozen", False):
    _LANDMARK_DIR = pathlib.Path(sys._MEIPASS) / "spacehack" / "data" / "landmarks"
else:
    _LANDMARK_DIR = pathlib.Path(__file__).parent / "data" / "landmarks"


@dataclass(frozen=True)
class LandmarkStamp:
    """Coordinates of a landmark after it has been stamped into a map."""

    origin: world.Position
    entrance: world.Position
    console: world.Position | None
    stairs: world.Position | None
    footprint: frozenset[tuple[int, int]]
    arrival: world.Position | None = None


def choose_weighted_variant(variants, roll: float) -> str:
    """Choose a landmark layout ID from weighted variant data."""
    _positive = tuple(
        _variant for _variant in variants
        if getattr(_variant, "weight", 0) > 0
    )
    if not _positive:
        raise ValueError("Landmark variants must contain a positive weight")
    _total = sum(_variant.weight for _variant in _positive)
    _target = min(max(roll, 0.0), 0.999999999) * _total
    for _variant in _positive:
        if _target < _variant.weight:
            return _variant.layout_id
        _target -= _variant.weight
    return _positive[-1].layout_id


def load_landmark(layout_id: str) -> world.GameMap:
    """Load a hand-authored landmark layout without requiring a player spawn."""
    game_map, _spawn = dungeon.load_layout(
        layout_id,
        layout_dir=_LANDMARK_DIR,
        require_spawn=False,
    )
    return game_map


def _landmark_markers(
    landmark: world.GameMap,
) -> tuple[
    world.Position,
    world.Position | None,
    world.Position | None,
    world.Position | None,
]:
    """Return a landmark's entrance and optional connection markers."""
    _doors = [
        world.Position(x, y)
        for y, row in enumerate(landmark.tiles)
        for x, tile in enumerate(row)
        if tile.kind in {"dungeon_door", "landmark_entrance"}
    ]
    _consoles = [
        entity.pos
        for entity in landmark.entities
        if getattr(entity, "main_quest_console", False)
    ]
    _stairs = [
        world.Position(x, y)
        for y, row in enumerate(landmark.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "stairs_down"
    ]
    _arrivals = [
        world.Position(x, y)
        for y, row in enumerate(landmark.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "stairs_up"
    ]
    if (
        len(_doors) != 1
        or len(_consoles) > 1
        or len(_stairs) > 1
        or len(_arrivals) > 1
    ):
        raise ValueError(
            "Landmark must contain one entrance and at most one "
            "arrival/console/stairs marker"
        )
    return (
        _doors[0],
        _arrivals[0] if _arrivals else None,
        _consoles[0] if _consoles else None,
        _stairs[0] if _stairs else None,
    )


def _candidate_origins(
    game_map: world.GameMap,
    landmark: world.GameMap,
    spawn: world.Position,
) -> list[tuple[int, int, int]]:
    """Return valid origins ranked by entrance distance from ``spawn``."""
    _door, _arrival, _console, _stairs = _landmark_markers(landmark)
    _allow_spawn_overlap = _arrival is not None
    _max_x = game_map.width - landmark.width - 1
    _max_y = game_map.height - landmark.height - 2
    if _max_x < 1 or _max_y < 1:
        return []
    _candidates: list[tuple[int, int, int]] = []
    for _oy in range(1, max(1, _max_y) + 1):
        for _ox in range(1, max(1, _max_x) + 1):
            _entrance_x = _ox + _door.x
            _entrance_y = _oy + _door.y
            _approach_y = _entrance_y + 1
            if not game_map.in_bounds(_entrance_x, _approach_y):
                continue
            _footprint = {
                (_ox + _lx, _oy + _ly)
                for _ly in range(landmark.height)
                for _lx in range(landmark.width)
            }
            if (spawn.x, spawn.y) in _footprint and not _allow_spawn_overlap:
                continue
            if any(
                game_map.tiles[_py][_px].kind in {
                    "exit", "stairs_up", "stairs_down",
                }
                and not (
                    _allow_spawn_overlap
                    and (_px, _py) == (spawn.x, spawn.y)
                )
                for _px, _py in _footprint
            ):
                continue
            if game_map.tiles[_approach_y][_entrance_x].kind == "exit":
                continue
            _distance = max(
                abs(_entrance_x - spawn.x),
                abs(_entrance_y - spawn.y),
            )
            _candidates.append((_distance, _oy, _ox))
    return sorted(_candidates, reverse=True)


def _find_route(
    game_map: world.GameMap,
    start: world.Position,
    goal: world.Position,
    protected: set[tuple[int, int]],
) -> list[world.Position]:
    """Find a low-cost route that may carve existing walls, not landmarks."""
    _queue: list[tuple[int, int, int, tuple[int, int]]] = []
    _counter = 0
    _start = (start.x, start.y)
    _goal = (goal.x, goal.y)
    heapq.heappush(_queue, (0, _counter, 0, _start))
    _came_from: dict[tuple[int, int], tuple[int, int] | None] = {_start: None}
    _costs: dict[tuple[int, int], int] = {_start: 0}
    while _queue:
        _, _, _cost, _current = heapq.heappop(_queue)
        if _current == _goal:
            break
        _cx, _cy = _current
        for _dx, _dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            _next = (_cx + _dx, _cy + _dy)
            if not game_map.in_bounds(*_next):
                continue
            if _next in protected and _next != _goal:
                continue
            _tile = game_map.tiles[_next[1]][_next[0]]
            _step_cost = 1 if _tile.walkable else 5
            if _tile.kind == "void":
                _step_cost = 20
            _new_cost = _cost + _step_cost
            if _new_cost >= _costs.get(_next, 10**9):
                continue
            _costs[_next] = _new_cost
            _came_from[_next] = _current
            _counter += 1
            _heuristic = abs(_next[0] - goal.x) + abs(_next[1] - goal.y)
            heapq.heappush(
                _queue,
                (_new_cost + _heuristic, _counter, _new_cost, _next),
            )
    if _goal not in _came_from:
        raise ValueError("Landmark entrance cannot be connected to the dungeon")
    _route: list[world.Position] = []
    _current: tuple[int, int] | None = _goal
    while _current is not None:
        _route.append(world.Position(*_current))
        _current = _came_from[_current]
    return list(reversed(_route))


def _authored_boundary_targets(
    game_map: world.GameMap,
    landmark: world.GameMap,
    origin: world.Position,
    arrival: world.Position,
) -> list[world.Position]:
    """Find outside connection cells reachable from an authored arrival."""
    _start = (arrival.x, arrival.y)
    _visited = {_start}
    _queue = deque([_start])
    while _queue:
        _x, _y = _queue.popleft()
        for _dx, _dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            _next = (_x + _dx, _y + _dy)
            if not (0 <= _next[0] < landmark.width and 0 <= _next[1] < landmark.height):
                continue
            if _next in _visited or not landmark.tiles[_next[1]][_next[0]].walkable:
                continue
            _visited.add(_next)
            _queue.append(_next)
    _footprint = {
        (origin.x + _x, origin.y + _y)
        for _y in range(landmark.height)
        for _x in range(landmark.width)
    }
    _targets: list[world.Position] = []
    for _x, _y in _visited:
        _world = (origin.x + _x, origin.y + _y)
        if any(
            game_map.in_bounds(_world[0] + _dx, _world[1] + _dy)
            and (_world[0] + _dx, _world[1] + _dy) not in _footprint
            for _dx, _dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
        ):
            _targets.append(world.Position(*_world))
    return _targets


def _theme_tile(
    game_map: world.GameMap,
    kind: str,
    fallback: world.Tile,
) -> world.Tile:
    """Find the destination dungeon's themed tile for ``kind``."""
    return next(
        (
            _tile
            for _row in game_map.tiles
            for _tile in _row
            if _tile.kind == kind
        ),
        fallback,
    )


def _resolve_tile(
    tile: world.Tile,
    wall: world.Tile,
    floor: world.Tile,
) -> world.Tile:
    """Resolve generic dungeon tiles while preserving explicit colors."""
    _theme = {
        "dungeon_wall": wall,
        "dungeon_floor": floor,
    }.get(tile.kind)
    if _theme is None:
        return tile
    if tile is world.DUNGEON_WALL or tile is world.DUNGEON_FLOOR:
        return _theme
    return world.Tile(
        kind=_theme.kind,
        char=_theme.char,
        walkable=_theme.walkable,
        fg=tile.fg,
        bg=tile.bg if tile.bg_override else _theme.bg,
        bg_override=tile.bg_override,
    )


def _stamp_map_cells(
    game_map: world.GameMap,
    landmark: world.GameMap,
    origin: world.Position,
) -> set[tuple[int, int]]:
    """Copy landmark tiles/entities and return its protected footprint."""
    _wall = _theme_tile(game_map, "dungeon_wall", world.DUNGEON_WALL)
    _floor = _theme_tile(game_map, "dungeon_floor", world.DUNGEON_FLOOR)
    _protected: set[tuple[int, int]] = set()
    for _ly, _row in enumerate(landmark.tiles):
        for _lx, _tile in enumerate(_row):
            _x = origin.x + _lx
            _y = origin.y + _ly
            _protected.add((_x, _y))
            game_map.tiles[_y][_x] = _resolve_tile(_tile, _wall, _floor)
    for _entity in landmark.entities:
        _copy = copy.copy(_entity)
        _copy.pos = world.Position(
            origin.x + _entity.pos.x,
            origin.y + _entity.pos.y,
        )
        game_map.entities.append(_copy)
    return _protected


def _carve_route(
    game_map: world.GameMap,
    route: list[world.Position],
    entrance: world.Position,
) -> None:
    """Carve non-landmark route cells into the generated floor."""
    _floor = next(
        (
            _tile
            for _row in game_map.tiles
            for _tile in _row
            if _tile.kind == "dungeon_floor" and _tile.walkable
        ),
        world.DUNGEON_FLOOR,
    )
    for _position in route:
        if _position == entrance:
            continue
        if not game_map.tiles[_position.y][_position.x].walkable:
            game_map.tiles[_position.y][_position.x] = _floor


def stamp_landmark(
    game_map: world.GameMap,
    landmark: world.GameMap,
    spawn: world.Position,
) -> LandmarkStamp:
    """Stamp ``landmark`` into ``game_map`` and carve a route to its door."""
    _door, _arrival, _console, _stairs = _landmark_markers(landmark)
    _ranked = _candidate_origins(game_map, landmark, spawn)
    if not _ranked:
        raise ValueError("Landmark does not fit in the generated dungeon")
    _, _origin_y, _origin_x = _ranked[0]
    _origin = world.Position(_origin_x, _origin_y)
    _entrance = world.Position(_origin.x + _door.x, _origin.y + _door.y)
    _approach = world.Position(_entrance.x, _entrance.y + 1)
    _footprint = {
        (_origin.x + _lx, _origin.y + _ly)
        for _ly in range(landmark.height)
        for _lx in range(landmark.width)
    }
    if _arrival is not None:
        # The authored arrival selects the connected bridge component; the
        # generated route enters that component at its nearest outer edge.
        _targets = _authored_boundary_targets(
            game_map, landmark, _origin, _arrival,
        )
        if not _targets:
            raise ValueError("Landmark has no reachable outer connection")
        _route_goal = min(
            _targets,
            key=lambda _position: (
                abs(_position.x - spawn.x) + abs(_position.y - spawn.y),
                _position.y,
                _position.x,
            ),
        )
        _route = _find_route(game_map, spawn, _route_goal, _footprint)
        _carve_route(game_map, _route, _entrance)
        _protected = _stamp_map_cells(game_map, landmark, _origin)
    else:
        # Legacy landmarks (such as the Mars signal door) are stamped first;
        # their entrance/approach contract is defined relative to the stamped
        # footprint and remains compatible with existing Act 0 saves.
        _protected = _stamp_map_cells(game_map, landmark, _origin)
        _route = _find_route(game_map, spawn, _approach, _protected)
        _carve_route(game_map, _route, _entrance)
    return LandmarkStamp(
        origin=_origin,
        entrance=_entrance,
        arrival=(
            world.Position(_origin.x + _arrival.x, _origin.y + _arrival.y)
            if _arrival is not None else None
        ),
        console=(
            world.Position(_origin.x + _console.x, _origin.y + _console.y)
            if _console is not None else None
        ),
        stairs=(
            world.Position(_origin.x + _stairs.x, _origin.y + _stairs.y)
            if _stairs is not None else None
        ),
        footprint=frozenset(_protected),
    )
