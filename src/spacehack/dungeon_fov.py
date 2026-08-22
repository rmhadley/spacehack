"""Fog-of-war and line-of-sight behavior for dungeon maps."""

from __future__ import annotations

from collections import deque

from . import world


DUNGEON_SIGHT_RADIUS: int = 8


def init_fog(game_map: world.GameMap) -> None:
    """Initialize fog-of-war on a map before player control."""
    game_map.seen = [
        [False for _ in range(game_map.width)]
        for _ in range(game_map.height)
    ]
    game_map.visible = [
        [False for _ in range(game_map.width)]
        for _ in range(game_map.height)
    ]
    game_map.sight_radius = DUNGEON_SIGHT_RADIUS


def _cast_ray(game_map: world.GameMap, ox: int, oy: int, dx: int, dy: int) -> None:
    """Reveal one ray, stopping at solid walls and closed doors."""
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        return
    for step in range(1, steps + 1):
        fraction = step / steps
        sx = round(ox + dx * fraction)
        sy = round(oy + dy * fraction)
        if not game_map.in_bounds(sx, sy):
            return
        game_map.seen[sy][sx] = True
        if game_map.visible is not None:
            game_map.visible[sy][sx] = True
        tile = game_map.tiles[sy][sx]
        if not tile.walkable and tile.kind != "hull_wall":
            return
        if tile.kind == "dungeon_door":
            return


def _propagate_flags(game_map: world.GameMap, flags: list[list[bool]]) -> None:
    """Propagate a visibility flag through connected hull-wall groups."""
    width, height = game_map.width, game_map.height
    seeds = [
        (x, y)
        for y in range(height)
        for x in range(width)
        if game_map.tiles[y][x].kind == "hull_wall" and flags[y][x]
    ]
    visited: set[tuple[int, int]] = set()
    for seed in seeds:
        if seed in visited:
            continue
        group: list[tuple[int, int]] = []
        queue = deque([seed])
        visited.add(seed)
        while queue:
            current = queue.popleft()
            group.append(current)
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                neighbor = (current[0] + dx, current[1] + dy)
                if not (0 <= neighbor[0] < width and 0 <= neighbor[1] < height):
                    continue
                if neighbor in visited:
                    continue
                if game_map.tiles[neighbor[1]][neighbor[0]].kind != "hull_wall":
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
        if any(flags[y][x] for x, y in group):
            for x, y in group:
                flags[y][x] = True


def _propagate_hull_groups(game_map: world.GameMap) -> None:
    """Apply hull-group visibility to remembered and current-LOS grids."""
    if game_map.seen is None:
        return
    _propagate_flags(game_map, game_map.seen)
    if game_map.visible is not None:
        _propagate_flags(game_map, game_map.visible)


def _clear_visible(game_map: world.GameMap) -> None:
    """Reset or create the current line-of-sight grid."""
    if game_map.visible is None:
        game_map.visible = [
            [False for _ in range(game_map.width)]
            for _ in range(game_map.height)
        ]
        return
    for row in game_map.visible:
        for index in range(len(row)):
            row[index] = False


def _cast_visible_rays(
    game_map: world.GameMap,
    pos: world.Position,
    radius: int,
) -> None:
    """Cast all rays within the requested Chebyshev radius."""
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if max(abs(dx), abs(dy)) <= radius and (dx or dy):
                _cast_ray(game_map, pos.x, pos.y, dx, dy)


def reveal_around(
    game_map: world.GameMap,
    pos: world.Position,
    radius: int = DUNGEON_SIGHT_RADIUS,
) -> None:
    """Recompute current LOS and grow permanent visibility around ``pos``."""
    if game_map.seen is None:
        return
    _clear_visible(game_map)
    if game_map.in_bounds(pos.x, pos.y):
        game_map.seen[pos.y][pos.x] = True
        game_map.visible[pos.y][pos.x] = True
    _cast_visible_rays(game_map, pos, radius)
    _propagate_hull_groups(game_map)
