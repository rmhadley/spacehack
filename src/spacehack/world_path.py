"""A* pathfinding over a :class:`world.GameMap`.

Split out of :mod:`spacehack.world` so the shared game-world module stays
within the project architecture budget; importing :mod:`spacehack.world`
re-exports :func:`find_path`.
"""

from __future__ import annotations

import heapq

from . import world


_DIRS_8 = (
    (0, -1), (-1, 0), (1, 0), (0, 1),
    (-1, -1), (1, -1), (-1, 1), (1, 1),
)


def _heuristic(a, b) -> int:
    """Chebyshev distance — the cheapest 8-directional move is a diagonal."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _expand_node(
    game_map: world.GameMap,
    curr: tuple[int, int],
    end_candidates: set[tuple[int, int]],
    exclude_entity,
) -> list[tuple[int, int]]:
    """Return the passable neighbours of ``curr`` reachable in one step."""
    cx, cy = curr
    neighbours: list[tuple[int, int]] = []
    for dx, dy in _DIRS_8:
        npos = (cx + dx, cy + dy)
        if not game_map.in_bounds(*npos):
            continue
        if npos not in end_candidates:
            if not game_map.is_walkable(*npos):
                continue
            if game_map.blocking_entity_at(*npos, exclude=exclude_entity) is not None:
                continue
        neighbours.append(npos)
    return neighbours


def _reconstruct_path(
    came_from: dict, target: tuple[int, int],
) -> list[tuple[int, int]]:
    """Rebuild start->target (excluding the start cell) from the A* tree."""
    path: list[tuple[int, int]] = []
    cur = target
    while cur is not None:
        path.append(cur)
        cur = came_from.get(cur)
    path.reverse()
    return path[1:]


def find_path(
    start: tuple[int, int],
    end_candidates: set[tuple[int, int]],
    game_map: world.GameMap,
    *,
    exclude_entity=None,
    max_steps: int = 50000,
) -> list[tuple[int, int]] | None:
    """A* shortest path from ``start`` to any cell in ``end_candidates``."""
    best_target = min(end_candidates, key=lambda tc: _heuristic(start, tc))
    counter = 0
    open_set = [(0, counter, start)]
    came_from: dict = {start: None}
    g_score: dict = {start: 0}
    visited: set = set()
    target = None

    while open_set and target is None:
        _, _, curr = heapq.heappop(open_set)
        if curr in visited:
            continue
        visited.add(curr)
        if len(visited) > max_steps or curr in end_candidates:
            target = curr
            break
        for npos in _expand_node(game_map, curr, end_candidates, exclude_entity):
            tentative = g_score.get(curr, 0) + 1
            if tentative < g_score.get(npos, 999999):
                came_from[npos] = curr
                g_score[npos] = tentative
                f = tentative + _heuristic(npos, best_target)
                counter += 1
                heapq.heappush(open_set, (f, counter, npos))

    if target is None or target not in end_candidates:
        return None
    return _reconstruct_path(came_from, target)


__all__ = ["find_path"]
