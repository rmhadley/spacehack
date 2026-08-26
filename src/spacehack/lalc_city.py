"""Lalande 21185 c — Whisper's tight shipping-container maze.

Whisper is not a town laid out around a square. It is a smuggler depot
that kept adding containers until only narrow public lanes remained:
three stacked container belts divide the vault, while a central pair of
crossings ties the landing apron to the Hush, the Ledger, and the bounty
clerks. The empty cells are deliberate circulation space, not unfinished
terrain.
"""

from __future__ import annotations

from dataclasses import replace

from . import world
from .city_kit import (
    TERMINAL_PALETTE_CLASSIC,
    add_service_terminals,
    add_showroom_ships,
    base_tiles,
    paint_door_forecourts,
    paint_transit_stops,
    set_city_metadata,
)
from .city_layout import paint_roof_labels, stamp_city_assets
from .data.planets import _readable_city_theme


CITY_WIDTH = 100
CITY_HEIGHT = 70

# Fixed asset origins. The building footprints leave the public lanes
# visible on all four sides, while the lower pair shares the south loop.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "lalc_spaceport": world.Position(5, 4),
    "lalc_bar": world.Position(72, 5),
    "lalc_merchants": world.Position(5, 53),
    "lalc_bounties": world.Position(73, 52),
}

# The three narrow lower-level transit lanes and their two vertical
# crossings make a connected maze without opening the whole map into a
# featureless floor.
_HORIZONTAL_LANES = ((25, 27), (46, 48), (64, 66))
_VERTICAL_LANES = ((32, 34), (68, 70))

_CONTAINER_WALL = world.Tile(
    kind="city_building_wall", char="#", walkable=False,
    fg=(92, 96, 118), bg=(34, 36, 54),
    blocked_message="A sealed shipping container blocks the lane.",
)
_CONTAINER_ROOF = world.Tile(
    kind="city_building_wall", char="=", walkable=False,
    fg=(128, 132, 158), bg=(42, 44, 66),
    blocked_message="A stacked container blocks the lane.",
)
_BAY_TILE = world.Tile(
    kind="floor", char=" ", walkable=True,
    fg=(184, 170, 224), bg=(68, 60, 92),
)

_STORAGE_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((238, 100, 112), (92, 38, 54), (255, 140, 132), (108, 48, 58)),
    ((92, 190, 238), (32, 62, 104), (126, 220, 255), (42, 76, 118)),
    ((230, 190, 72), (94, 70, 24), (255, 220, 108), (112, 82, 30)),
    ((142, 224, 136), (38, 82, 48), (180, 245, 160), (48, 100, 56)),
    ((202, 126, 236), (72, 38, 96), (232, 166, 255), (84, 46, 112)),
)
_STORAGE_SITES: tuple[tuple[int, int, int, int], ...] = (
    # Upper logistics yard, between the apron and the first container belt.
    (37, 5, 5, 7), (45, 5, 5, 7), (55, 5, 5, 7), (63, 5, 5, 5),
    # Middle transfer yard, split by the two crossing lanes.
    (4, 29, 6, 4), (12, 29, 5, 4), (20, 29, 6, 4),
    (40, 29, 6, 4), (49, 29, 6, 4), (57, 29, 6, 4),
    (76, 29, 5, 4), (86, 29, 6, 4), (93, 29, 5, 4),
    # Lower transfer yard, outside the service buildings and south loop.
    (28, 51, 6, 4), (38, 51, 6, 4), (48, 51, 6, 4),
    (58, 51, 6, 4), (66, 51, 5, 4), (91, 51, 5, 4),
    # South freight lane: intentionally sparse to keep the loop readable.
    (28, 61, 6, 3), (38, 61, 6, 3), (48, 61, 6, 3),
    (58, 61, 6, 3), (68, 61, 5, 3), (90, 61, 6, 3),
)

# Container stacks are intentionally long and close together. Lane paint
# below cuts the planned public corridors back through the stacks.
_CONTAINER_BLOCKS: tuple[tuple[int, int, int, int], ...] = (
    (3, 16, 16, 4), (20, 31, 16, 4), (37, 48, 16, 4),
    (54, 66, 16, 4), (74, 96, 16, 4),
    (3, 14, 30, 5), (18, 29, 30, 5), (37, 51, 30, 5),
    (56, 67, 30, 5), (73, 84, 30, 5), (88, 97, 30, 5),
    (3, 18, 37, 5), (22, 36, 37, 5), (40, 53, 37, 5),
    (58, 71, 37, 5), (76, 93, 37, 5),
    (28, 43, 50, 4), (48, 61, 50, 4), (64, 71, 50, 4),
    (89, 97, 50, 4),
    (3, 18, 67, 3), (24, 37, 67, 3), (43, 57, 67, 3),
    (63, 76, 67, 3), (82, 96, 67, 3),
)


def _paint_container_block(tiles, x_lo, x_hi, y_lo, y_hi) -> None:
    """Paint one solid, non-enterable stack of shipping containers."""
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            edge = y in (y_lo, y_hi) or x in (x_lo, x_hi)
            tiles[y][x] = _CONTAINER_WALL if edge else _CONTAINER_ROOF


def _paint_containers(tiles) -> None:
    """Fill the vault with close-set container stacks."""
    for block in _CONTAINER_BLOCKS:
        _paint_container_block(tiles, *block)


def _paint_horizontal_lane(tiles, theme, y_lo, y_hi) -> None:
    """Cut one three-cell east-west lane through the container field."""
    middle = (y_lo + y_hi) // 2
    for y in range(y_lo, y_hi + 1):
        tile = theme.road_ew if y == middle else theme.sidewalk
        for x in range(2, CITY_WIDTH - 2):
            tiles[y][x] = tile


def _paint_vertical_lane(tiles, theme, x_lo, x_hi) -> None:
    """Cut one three-cell north-south crossing through the maze."""
    middle = (x_lo + x_hi) // 2
    for x in range(x_lo, x_hi + 1):
        tile = theme.road_ns if x == middle else theme.sidewalk
        for y in range(2, CITY_HEIGHT - 2):
            tiles[y][x] = tile


def _paint_lanes(tiles, theme) -> None:
    """Build the connected public lane grid before adding door approaches."""
    for y_lo, y_hi in _HORIZONTAL_LANES:
        _paint_horizontal_lane(tiles, theme, y_lo, y_hi)
    for x_lo, x_hi in _VERTICAL_LANES:
        _paint_vertical_lane(tiles, theme, x_lo, x_hi)


def _paint_landing_apron(tiles, theme) -> None:
    """Reserve a quiet apron below the unlisted landing hall."""
    apron = replace(theme.landing_pad, char=" ")
    for y in range(14, 24):
        for x in range(8, 30):
            tiles[y][x] = apron
    # A short public approach leaves the apron and joins the first lane.
    for y in range(23, 26):
        for x in range(28, 35):
            tiles[y][x] = theme.sidewalk if y < 25 else theme.road_ew


def _paint_door_approaches(tiles, theme) -> None:
    """Connect each functional door to the nearest planned public lane."""
    # Spaceport door -> landing apron.
    for y in range(13, 15):
        for x in range(16, 19):
            tiles[y][x] = theme.sidewalk
    # The Hush door -> a short spur ending beside the upper lane.
    for y in range(13, 24):
        for x in range(80, 83):
            tiles[y][x] = theme.sidewalk
    # The Ledger and bounty office both open onto the south loop.
    for y in range(61, 65):
        for x in range(14, 17):
            tiles[y][x] = theme.sidewalk
    for y in range(62, 65):
        for x in range(79, 82):
            tiles[y][x] = theme.sidewalk


def _storage_tile(char: str, fg, bg) -> world.Tile:
    """Build a vivid non-walkable storage-container tile."""
    return world.Tile(
        kind="storage_container", char=char, walkable=False,
        fg=fg, bg=bg,
        blocked_message="A colorful storage container blocks the lane.",
    )


def _paint_storage_unit(tiles, x, y, width, height, scheme) -> bool:
    """Paint one colorful storage unit only on an unclaimed floor pocket."""
    if not all(
        tiles[yy][xx].kind == "floor"
        for yy in range(y, y + height)
        for xx in range(x, x + width)
    ):
        return False
    wall_fg, wall_bg, roof_fg, roof_bg = scheme
    for yy in range(y, y + height):
        for xx in range(x, x + width):
            edge = yy in (y, y + height - 1) or xx in (x, x + width - 1)
            tiles[yy][xx] = _storage_tile(
                "#" if edge else "=",
                wall_fg if edge else roof_fg,
                wall_bg if edge else roof_bg,
            )
    return True


def _paint_storage_containers(tiles) -> None:
    """Fill selected freight-yard pockets with varied container colors."""
    for index, (x, y, width, height) in enumerate(_STORAGE_SITES):
        _paint_storage_unit(
            tiles, x, y, width, height,
            _STORAGE_SCHEMES[index % len(_STORAGE_SCHEMES)],
        )


def _paint_vault_details(tiles, theme) -> None:
    """Add restrained lights and container-end markers without blocking lanes."""
    light = replace(theme.neon, char="*")
    marker = replace(theme.decor, char="+")
    for x, y in (
        (6, 24), (25, 24), (44, 24), (60, 24), (92, 24),
        (84, 25),
        (6, 49), (25, 49), (44, 49), (60, 49), (92, 49),
        (24, 63), (43, 63), (62, 63), (91, 63),
    ):
        if tiles[y][x].walkable:
            tiles[y][x] = light
    for x, y in ((35, 28), (35, 52), (71, 28), (71, 52)):
        if tiles[y][x].walkable:
            tiles[y][x] = marker


def build_lalc_layout(spec, resolve_ship) -> world.GameMap:
    """Build Whisper's 100x70 shipping-container maze."""
    theme = _readable_city_theme(spec.theme or world.EARTH_THEME)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _paint_containers(tiles)
    _paint_lanes(tiles, theme)
    _paint_landing_apron(tiles, theme)
    _paint_door_approaches(tiles, theme)
    _paint_storage_containers(tiles)
    _paint_vault_details(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor"}),
    )
    paint_transit_stops(game_map.tiles, spec, _BAY_TILE)
    paint_roof_labels(game_map, stamps, "lalc_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="lalc_", default_layout_id="lalc_container_maze",
    )
    add_showroom_ships(game_map, spec, resolve_ship)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-6, -2, 2),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


__all__ = ["build_lalc_layout", "LANDMARK_ORIGINS"]
