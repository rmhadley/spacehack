"""Procedural BSP dungeon generation."""

from __future__ import annotations

from . import world
from .dungeon_params import DungeonParams


def generate_dungeon(
    params: DungeonParams,
) -> tuple[world.GameMap, world.Position]:
    """Generate a seeded room-and-corridor dungeon."""
    from .engine import RNG

    width, height = params.width, params.height
    tiles = [[params.tile_wall for _ in range(width)] for _ in range(height)]
    center = _bsp_split(tiles, 0, 0, width, height, RNG, params)
    spawn = _find_walkable_near(tiles, center[0], center[1])
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    game_map.sight_radius = params.sight_radius
    return game_map, spawn


def _choose_split(w: int, h: int, params: DungeonParams, rng) -> tuple[bool, int]:
    """Choose a valid split direction and position for one BSP region."""
    leaf_min = int(params.max_room_size / params.room_fill_pct) + 2
    can_horizontal = w >= leaf_min
    can_vertical = h >= leaf_min
    if not can_horizontal and not can_vertical:
        return False, 0
    horizontal = w > h if can_horizontal and can_vertical else can_horizontal
    half_min = int(params.max_room_size / params.room_fill_pct) // 2 + 1
    lower = max(params.min_room_size + 1, half_min)
    size = w if horizontal else h
    return horizontal, rng.randint(lower, size - lower)


def _bsp_split(
    tiles: list[list[world.Tile]],
    x: int,
    y: int,
    w: int,
    h: int,
    rng,
    params: DungeonParams,
) -> tuple[int, int]:
    """Recursively carve rooms and connect sibling regions."""
    horizontal, split = _choose_split(w, h, params, rng)
    if split == 0:
        return _carve_room(tiles, x, y, w, h, rng, params)
    if horizontal:
        first = _bsp_split(tiles, x, y, split, h, rng, params)
        second = _bsp_split(tiles, x + split, y, w - split, h, rng, params)
    else:
        first = _bsp_split(tiles, x, y, w, split, rng, params)
        second = _bsp_split(tiles, x, y + split, w, h - split, rng, params)
    return _carve_corridor(tiles, first, second, rng, params)


def _carve_small_room(
    tiles: list[list[world.Tile]],
    x: int,
    y: int,
    w: int,
    h: int,
    tile_floor: world.Tile,
) -> tuple[int, int]:
    """Carve the largest centered floor possible in a small region."""
    floor_w = max(1, w - 2)
    floor_h = max(1, h - 2)
    floor_x = x + max(0, (w - floor_w) // 2)
    floor_y = y + max(0, (h - floor_h) // 2)
    for row in range(floor_y, floor_y + floor_h):
        for col in range(floor_x, floor_x + floor_w):
            tiles[row][col] = tile_floor
    return floor_x + floor_w // 2, floor_y + floor_h // 2


def _carve_room(
    tiles: list[list[world.Tile]],
    x: int,
    y: int,
    w: int,
    h: int,
    rng,
    params: DungeonParams,
) -> tuple[int, int]:
    """Carve one randomly sized room inside a BSP leaf."""
    if w < params.min_room_size + 2 or h < params.min_room_size + 2:
        return _carve_small_room(tiles, x, y, w, h, params.tile_floor)
    available_w = min(
        params.max_room_size,
        max(params.min_room_size, int((w - 2) * params.room_fill_pct)),
    )
    available_h = min(
        params.max_room_size,
        max(params.min_room_size, int((h - 2) * params.room_fill_pct)),
    )
    room_w = rng.randint(params.min_room_size, available_w)
    room_h = rng.randint(params.min_room_size, available_h)
    room_x = x + rng.randint(1, max(1, w - room_w - 1))
    room_y = y + rng.randint(1, max(1, h - room_h - 1))
    for row in range(room_y, room_y + room_h):
        for col in range(room_x, room_x + room_w):
            tiles[row][col] = params.tile_floor
    _scatter_fungus(tiles, room_x, room_y, room_w, room_h, rng)
    return room_x + room_w // 2, room_y + room_h // 2


def _scatter_fungus(
    tiles: list[list[world.Tile]],
    room_x: int, room_y: int, room_w: int, room_h: int, rng,
) -> None:
    """Scatter 0-2 bioluminescent fungus patches on a carved room floor.

    Sparse so the dungeon reads as dark with occasional green glows; the
    fungus extends the player's sight nearby (see :mod:`dungeon_fov`).
    """
    patches = rng.randint(0, 2)
    for _ in range(patches):
        fx = room_x + rng.randint(0, room_w - 1)
        fy = room_y + rng.randint(0, room_h - 1)
        if tiles[fy][fx].kind == "dungeon_floor":
            tiles[fy][fx] = world.GLOW_FUNGUS


def _carve_horizontal_first(
    tiles: list[list[world.Tile]],
    first: tuple[int, int],
    second: tuple[int, int],
    floor: world.Tile,
) -> tuple[int, int]:
    """Carve horizontal then vertical corridor legs."""
    x1, y1 = first
    x2, y2 = second
    height, width = len(tiles), len(tiles[0]) if tiles else 0
    for x in range(min(x1, x2), max(x1, x2) + 1):
        if 0 <= y1 < height and 0 <= x < width and tiles[y1][x].kind == "dungeon_wall":
            tiles[y1][x] = floor
    for y in range(min(y1, y2), max(y1, y2) + 1):
        if 0 <= y < height and 0 <= x2 < width and tiles[y][x2].kind == "dungeon_wall":
            tiles[y][x2] = floor
    return x2, y1


def _carve_vertical_first(
    tiles: list[list[world.Tile]],
    first: tuple[int, int],
    second: tuple[int, int],
    floor: world.Tile,
) -> tuple[int, int]:
    """Carve vertical then horizontal corridor legs."""
    x1, y1 = first
    x2, y2 = second
    height, width = len(tiles), len(tiles[0]) if tiles else 0
    for y in range(min(y1, y2), max(y1, y2) + 1):
        if 0 <= y < height and 0 <= x1 < width and tiles[y][x1].kind == "dungeon_wall":
            tiles[y][x1] = floor
    for x in range(min(x1, x2), max(x1, x2) + 1):
        if 0 <= y2 < height and 0 <= x < width and tiles[y2][x].kind == "dungeon_wall":
            tiles[y2][x] = floor
    return x1, y2


def _carve_corridor(
    tiles: list[list[world.Tile]],
    first: tuple[int, int],
    second: tuple[int, int],
    rng,
    params: DungeonParams,
) -> tuple[int, int]:
    """Carve an L-shaped corridor and return its guaranteed corner."""
    if rng.random() < 0.5:
        return _carve_horizontal_first(tiles, first, second, params.tile_floor)
    return _carve_vertical_first(tiles, first, second, params.tile_floor)


def _has_floor_neighbour(
    tiles: list[list[world.Tile]],
    x: int,
    y: int,
) -> bool:
    """Return whether a coordinate has an in-bounds walkable neighbor."""
    height = len(tiles)
    width = len(tiles[0]) if height else 0
    return any(
        0 <= x + dx < width
        and 0 <= y + dy < height
        and tiles[y + dy][x + dx].walkable
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
    )


def _find_walkable_near(
    tiles: list[list[world.Tile]],
    cx: int,
    cy: int,
) -> world.Position:
    """Place an exit in a wall cell adjacent to floor near a center."""
    height = len(tiles)
    width = len(tiles[0]) if height else 0
    for radius in range(max(width, height)):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                x, y = cx + dx, cy + dy
                if 0 <= x < width and 0 <= y < height:
                    if not tiles[y][x].walkable and _has_floor_neighbour(tiles, x, y):
                        tiles[y][x] = world.EXIT
                        return world.Position(x, y)
    for y in range(height):
        for x in range(width):
            if not tiles[y][x].walkable and _has_floor_neighbour(tiles, x, y):
                tiles[y][x] = world.EXIT
                return world.Position(x, y)
    for y in range(height):
        for x in range(width):
            if tiles[y][x].walkable:
                tiles[y][x] = world.EXIT
                return world.Position(x, y)
    return world.Position(cx, cy)
