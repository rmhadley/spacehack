"""Mars's authored colony city layout generator.

Phase 6: Mars is a third *layout* in the generic city pipeline
(:mod:`spacehack.city_builder` dispatches on ``city_layout_id ==
"mars_colony"``).  It reads as a sleek, modern terraformed city —
same machinery Earth and Mercury use (authored exterior stamps,
roof labels, skyline, roads) but themed for a red/rust palette:
clean grid roads, a central market-square plaza, and geometric
skyline buildings instead of organic shapes.

The shared authored-layout machinery lives in
:mod:`spacehack.city_layout`; the shared city tail (transit
stations + ambient NPCs) runs in ``city_builder.build_city`` for
every planet, Mars included.
"""

from __future__ import annotations

from . import world
from .city_layout import (
    building_records,
    paint_roof_labels,
    paint_skyline,
    stamp_city_assets,
    stamp_metadata,
)
from .data.planets import _readable_city_theme
from .data.planets.themes import MARS


MARS_CITY_WIDTH = 160
MARS_CITY_HEIGHT = 100

# Fixed authored origins — one per spec building.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "mars_spaceport":  world.Position(4, 3),
    "mars_bar":        world.Position(120, 8),
    "mars_merchants":  world.Position(4, 70),
    "mars_militia":    world.Position(120, 70),
    "mars_bounties":   world.Position(60, 45),
}

# Three east-west boulevards, each 3 tiles wide.
_NORTH_BOULEVARD_Y = (16, 17, 18)
_CENTRAL_BOULEVARD_Y = (48, 49, 50)
_SOUTH_BOULEVARD_Y = (83, 84, 85)

# Three north-south avenues, each 3 tiles wide.
_WEST_AVENUE_X = (30, 31, 32)
_CENTRAL_AVENUE_X = (79, 80, 81)
_EAST_AVENUE_X = (108, 109, 110)

# Short feeder roads connecting building doors to the nearest avenue.
_FEEDERS: tuple[tuple[int, int, int], ...] = (
    # (x_lo, x_hi, y) — horizontal segments
    (24, 29, 12),   # spaceport door → west avenue
    (110, 119, 12), # bar door → east avenue
    (24, 29, 70),   # merchants door → west avenue
    (110, 119, 70), # militia door → east avenue
    (33, 59, 57),   # bounties door → central avenue (west leg)
    (78, 59, 57),   # bounties door → central avenue (east leg — redundant, kept for symmetry)
)

# Market square plaza — a wide central feature below the bounties building.
_PLAZA_X_LO, _PLAZA_X_HI = 70, 90
_PLAZA_Y_LO, _PLAZA_Y_HI = 59, 67

# Neon accent positions — near building entrances and plaza edges.
_NEON_POSITIONS: tuple[tuple[int, int], ...] = (
    (10, 30), (18, 30),       # spaceport entrance row
    (124, 17), (132, 17),     # bar entrance row
    (10, 70), (18, 70),       # merchants entrance
    (124, 70), (140, 70),     # militia entrance
    (64, 57), (72, 57),       # bounties entrance
    # Plaza edge accents
    (70, 59), (90, 59), (70, 67), (90, 67),
    # Street lamps along boulevards
    (40, 17), (60, 17), (100, 17), (140, 17),
    (40, 49), (60, 49), (100, 49), (140, 49),
    (40, 84), (60, 84), (100, 84), (140, 84),
)

# Ornament positions — near building doors and plaza perimeter.
_ORNAMENT_POSITIONS: tuple[tuple[int, int], ...] = (
    (6, 15), (22, 15),       # spaceport door markers
    (122, 15), (136, 15),    # bar door markers
    (6, 68), (22, 68),       # merchants door markers
    (122, 68), (154, 68),    # militia door markers
    (62, 57), (76, 57),      # bounties door markers
    # Plaza perimeter
    (70, 58), (90, 58), (70, 68), (90, 68),
)

# Procedural skyline: clean geometric buildings fill city blocks.
# Mars buildings are modern — sharp angles, no organic shapes.
_SKYLINE_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((180, 90, 60), (55, 28, 15), (200, 110, 75), (62, 32, 18)),   # rust
    ((160, 100, 80), (48, 30, 20), (185, 120, 95), (55, 35, 22)),  # sandstone
    ((140, 80, 55), (42, 22, 12), (165, 100, 70), (50, 28, 15)),   # dark rust
    ((170, 120, 90), (52, 36, 24), (195, 140, 105), (58, 40, 28)), # terracotta
    ((130, 75, 50), (38, 20, 10), (155, 95, 65), (45, 25, 13)),    # deep ochre
    ((155, 110, 85), (48, 34, 22), (180, 130, 100), (55, 38, 26)), # warm stone
)


def _colony_theme():
    """Mars's red/rust theme, readability-adjusted."""
    return _readable_city_theme(MARS)


def _paint_road_cell(tiles, x, y, tile) -> None:
    """Paint one road cell — only on floor or grass."""
    kind = tiles[y][x].kind
    if kind in {"floor", "grass"}:
        tiles[y][x] = tile


def _paint_roads(tiles, theme) -> None:
    """Paint the 3-wide road grid: three boulevards + three avenues + feeders."""
    road = theme.road_surface
    lane_h = theme.road_ew
    lane_v = theme.road_ns
    w, h = MARS_CITY_WIDTH, MARS_CITY_HEIGHT

    # East-west boulevards
    for y_lo, y_mid, y_hi in (
        _NORTH_BOULEVARD_Y, _CENTRAL_BOULEVARD_Y, _SOUTH_BOULEVARD_Y,
    ):
        for x in range(3, w - 2):
            _paint_road_cell(tiles, x, y_lo, road)
            _paint_road_cell(tiles, x, y_mid, lane_h)
            _paint_road_cell(tiles, x, y_hi, road)

    # North-south avenues
    for x_lo, x_mid, x_hi in (
        _WEST_AVENUE_X, _CENTRAL_AVENUE_X, _EAST_AVENUE_X,
    ):
        for y in range(3, h - 2):
            _paint_road_cell(tiles, x_lo, y, road)
            _paint_road_cell(tiles, x_mid, y, lane_v)
            _paint_road_cell(tiles, x_hi, y, road)

    # Feeder roads connecting building doors to avenues.
    for x_lo, x_hi, y in _FEEDERS:
        for x in range(x_lo, x_hi + 1):
            _paint_road_cell(tiles, x, y, road)


def _paint_market_square(tiles, theme) -> None:
    """Paint the central market-square plaza."""
    for y in range(_PLAZA_Y_LO, _PLAZA_Y_HI + 1):
        for x in range(_PLAZA_X_LO, _PLAZA_X_HI + 1):
            if tiles[y][x].kind in {"floor", "grass"}:
                tiles[y][x] = theme.plaza


def _paint_landing_pad(tiles, theme, spec) -> None:
    """Paint the landing apron below the spaceport."""
    anchor = spec.hangar_anchor
    port = spec.buildings[0]
    x_lo = max(1, anchor.x - 3)
    x_hi = min(MARS_CITY_WIDTH - 2, anchor.x + 3)
    y_lo = port.y_hi + 1
    y_hi = min(MARS_CITY_HEIGHT - 2, anchor.y + 1)
    for py in range(y_lo, y_hi + 1):
        for px in range(x_lo, x_hi + 1):
            tiles[py][px] = theme.landing_pad


def _paint_grass(tiles, theme) -> None:
    """Fill open floor with red Mars grass and sparse texture."""
    for y in range(3, MARS_CITY_HEIGHT - 3):
        for x in range(3, MARS_CITY_WIDTH - 3):
            if tiles[y][x].kind == "floor":
                tiles[y][x] = (
                    theme.grass_accent if (x * 7 + y * 11) % 13 == 0
                    else theme.grass
                )


def _paint_decorations(tiles, theme) -> None:
    """Add neon signs, ornaments, and lamp posts."""
    from .city_tiles import CITY_ORNAMENT
    h, w = len(tiles), len(tiles[0])
    for x, y in _NEON_POSITIONS:
        if 0 <= y < h and 0 <= x < w and tiles[y][x].walkable:
            tiles[y][x] = theme.neon
    for x, y in _ORNAMENT_POSITIONS:
        if 0 <= y < h and 0 <= x < w and tiles[y][x].walkable:
            tiles[y][x] = CITY_ORNAMENT


def _new_mars_map(spec) -> world.GameMap:
    """Create and decorate the Mars colony terrain."""
    theme = _colony_theme()
    tiles = [
        [theme.floor for _ in range(MARS_CITY_WIDTH)]
        for _ in range(MARS_CITY_HEIGHT)
    ]
    # Perimeter walls
    for x in range(MARS_CITY_WIDTH):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(MARS_CITY_HEIGHT):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL

    _paint_grass(tiles, theme)
    _paint_roads(tiles, theme)
    _paint_market_square(tiles, theme)
    _paint_landing_pad(tiles, theme, spec)
    _paint_decorations(tiles, theme)

    return world.GameMap(
        width=MARS_CITY_WIDTH, height=MARS_CITY_HEIGHT,
        tiles=tiles, entities=[],
    )


def _set_mars_metadata(game_map, spec, stamps) -> None:
    """Attach the metadata city systems need for Mars."""
    game_map.city_layout_id = spec.city_layout_id or "mars_colony"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "mars_")


def _add_service_entities(game_map, spec, resolve_ship) -> None:
    """Add showroom ships on the apron + terminals below the port door."""
    anchor = spec.hangar_anchor
    pad_x_lo = max(1, anchor.x - 3)
    pad_y_lo = spec.buildings[0].y_hi + 1
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        game_map.entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(pad_x_lo + off_x, pad_y_lo + off_y),
            name=f"Ship: {ship_obj.name}", ship_id=ship_obj.id,
            width=ship_obj.width, height=ship_obj.height,
        ))
    terminal_data = (
        ("=", "Trade Terminal", (10, 13), "trade_terminal", (100, 220, 255)),
        ("%", "Mechanic Terminal", (6, 13), "mech_terminal", (200, 220, 100)),
        ("A", "Armory Terminal", (3, 13), "armory_terminal", (255, 160, 80)),
    )
    for char, name, position, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg, pos=world.Position(*position),
            name=name, **{flag: True},
        ))


def build_mars_layout(spec, resolve_ship) -> world.GameMap:
    """Build Mars's 160x100 colony city from data + authored assets.

    Transit stations and ambient NPCs are NOT placed here — the generic
    :func:`spacehack.city_builder.build_city` shared tail adds them for
    every planet.
    """
    game_map = _new_mars_map(spec)
    stamps = stamp_city_assets(game_map, LANDMARK_ORIGINS)
    paint_roof_labels(game_map, stamps, "mars_")
    paint_skyline(
        game_map,
        seed_key=("mars", "skyline"),
        schemes=_SKYLINE_SCHEMES,
        # Modern geometric buildings on the red terrain.
        site_kinds=frozenset({"floor", "grass"}),
        roof_char="#",
        width_range=(5, 8),
        height_range=(4, 6),
        min_size=(5, 4),
        row_stride=3,
    )
    _set_mars_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map
