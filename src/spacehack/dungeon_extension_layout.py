"""Room-region helpers for procedural dungeon extensions."""

from __future__ import annotations

from collections import deque
from typing import Callable

from . import world


def _room_core_components(
    game_map: world.GameMap,
) -> list[set[tuple[int, int]]]:
    """Return connected components of wide, room-like floor cells."""
    _core = {
        (_x, _y)
        for _y in range(game_map.height)
        for _x in range(game_map.width)
        if game_map.tiles[_y][_x].walkable
        and sum(
            game_map.is_walkable(_x + _dx, _y + _dy)
            for _dx, _dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
        ) >= 3
    }
    _components: list[set[tuple[int, int]]] = []
    while _core:
        _start = _core.pop()
        _component = {_start}
        _queue = deque([_start])
        while _queue:
            _x, _y = _queue.popleft()
            for _nx, _ny in (
                (_x + 1, _y), (_x - 1, _y),
                (_x, _y + 1), (_x, _y - 1),
            ):
                if (_nx, _ny) in _core:
                    _core.remove((_nx, _ny))
                    _component.add((_nx, _ny))
                    _queue.append((_nx, _ny))
        _components.append(_component)
    return _components


def _separate_room_cells(
    game_map: world.GameMap,
    anchor: world.Position,
    distance_fn: Callable,
) -> list[tuple[int, int]]:
    """Return cells in a room core different from the anchor's room."""
    _components = _room_core_components(game_map)
    if len(_components) < 2:
        return []
    _distances = distance_fn(game_map, anchor)
    _anchor_component = min(
        _components,
        key=lambda _component: min(
            _distances.get(_cell, float("inf")) for _cell in _component
        ),
    )
    _cells = [
        _cell
        for _component in _components
        if _component is not _anchor_component
        for _cell in _component
    ]
    return sorted(
        _cells,
        key=lambda _cell: (-_distances.get(_cell, -1), _cell[1], _cell[0]),
    )


def _preferred_interaction_cells(
    game_map: world.GameMap,
    cells: list[tuple[int, int]],
    anchor: world.Position | None,
    distance_fn: Callable,
) -> list[tuple[int, int]]:
    """Prefer a different room core, retaining all cells as fallback."""
    if anchor is None:
        return cells
    return _separate_room_cells(game_map, anchor, distance_fn) or cells
