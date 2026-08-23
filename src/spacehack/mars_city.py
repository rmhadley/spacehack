"""Mars's authored colony city layout generator.

Phase 6: Mars is a third *layout* in the generic city pipeline
(:mod:`spacehack.city_builder` dispatches on ``city_layout_id ==
"mars_colony"``).  It reads as a sleek, modern terraformed city
with the spaceport at the heart, buildings radiating outward, and
hub-and-spoke roads connecting everything.  Red/rust palette with
orange neon accents and geometric skyline buildings.

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
# Layout: spaceport central-left, bar upper-right, merchants lower-left,
# militia lower-right, bounties center-right.  Buildings radiate outward
# from the spaceport hub.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "mars_spaceport":  world.Position(50, 28),
    "mars_bar":        world.Position(110, 12),
    "mars_merchants":  world.Position(12, 58),
    "mars_militia":    world.Position(120, 58),
    "mars_bounties":   world.Position(95, 40),
}

# Hub-and-spoke road network radiating from the spaceport pad area.
# Central hub (around the pad)
_HUB_ROAD_Y = (40, 41, 42)   # E-W through the pad
_HUB_ROAD_X = (62, 63, 64)   # N-S through the pad

# Spoke roads connecting the hub to each building district
_SPOKES: tuple[tuple[int, int, int, int], ...] = (
    # (x1, y1, x2, y2) — each spoke is a 3-wide corridor
    # NW spoke → bar district
    (63, 40, 115, 12),
    # SW spoke → merchants district
    (62, 41, 12, 65),
    # SE spoke → militia district
    (64, 42, 145, 65),
    # E spoke → bounties
    (64, 41, 110, 45),
)

# Feeder roads from building doors to the nearest spoke
_FEEDERS: tuple[tuple[int, int, int, int], ...] = (
    # (x_lo, x_hi, y) horizontal or (x, y_lo, y_hi) vertical
    # Spaceport pad area (below the building)
    (50, 70, 44),
    # Bar door → spoke
    (108, 118, 20),
    # Merchants door → spoke
    (14, 20, 65),
    # Militia door → spoke
    (118, 140, 65),
    # Bounties door → spoke
    (95, 108, 48),
)

# Market-square plaza — between the spaceport and the bounties district,
# the social heart of the colony.
_PLAZA_X_LO, _PLAZA_X_HI = 78, 96
_PLAZA_Y_LO, _PLAZA_Y_HI = 35, 48

# Neon accent positions — near building entrances, plaza edges, spoke
# intersections.  These read as modern lighting on a terraformed city.
_NEON_POSITIONS: tuple[tuple[int, int], ...] = (
    # Spaceport entrance area
    (55, 28), (65, 28),
    # Bar entrance
    (112, 12), (120, 12),
    # Merchants entrance
    (14, 58), (22, 58),
    # Militia entrance
    (122, 58), (140, 58),
    # Bounties entrance
    (97, 40), (105, 40),
    # Plaza edge accents
    (78, 35), (96, 35), (78, 48), (96, 48),
    # Hub spoke intersections
    (63, 30), (63, 50),
    (40, 41), (85, 41),
    # Along main boulevard
    (30, 41), (100, 41), (130, 41),
)

# Ornament positions — near doors and key landmarks.
_ORNAMENT_POSITIONS: tuple[tuple[int, int], ...] = (
    # Spaceport flanks
    (48, 28), (72, 28),
    # Bar flanks
    (108, 12), (124, 12),
    # Merchants flanks
    (12, 58), (26, 58),
    # Militia flanks
    (120, 58), (150, 58),
    # Bounties flanks
    (93, 40), (108, 40),
    # Plaza perimeter
    (78, 34), (96, 34), (78, 49), (96, 49),
)

# Procedural skyline: clean geometric buildings fill city blocks
# between the spokes.  Modern angles, no organic shapes.
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


def _paint_hub(tiles, theme) -> None:
    """Paint the central hub roads through the pad area."""
    road = theme.road_surface
    lane_h = theme.road_ew
    lane_v = theme.road_ns
    w, h = MARS_CITY_WIDTH, MARS_CITY_HEIGHT
    # E-W hub road
    for y_lo, y_mid, y_hi in ((_HUB_ROAD_Y[0], _HUB_ROAD_Y[1], _HUB_ROAD_Y[2]),):
        for x in range(3, w - 2):
            _paint_road_cell(tiles, x, y_lo, road)
            _paint_road_cell(tiles, x, y_mid, lane_h)
            _paint_road_cell(tiles, x, y_hi, road)
    # N-S hub road
    for x_lo, x_mid, x_hi in ((_HUB_ROAD_X[0], _HUB_ROAD_X[1], _HUB_ROAD_X[2]),):
        for y in range(3, h - 2):
            _paint_road_cell(tiles, x_lo, y, road)
            _paint_road_cell(tiles, x_mid, y, lane_v)
            _paint_road_cell(tiles, x_hi, y, road)


def _paint_spoke(tiles, theme, x1, y1, x2, y2) -> None:
    """Paint a diagonal spoke road from (x1,y1) to (x2,y2)."""
    road = theme.road_surface
    steps = max(abs(x2 - x1), abs(y2 - y1))
    if steps == 0:
        return
    for i in range(steps + 1):
        t = i / steps
        x = int(x1 + (x2 - x1) * t)
        y = int(y1 + (y2 - y1) * t)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= ny < MARS_CITY_HEIGHT and 0 <= nx < MARS_CITY_WIDTH:
                    _paint_road_cell(tiles, nx, ny, road)


def _paint_roads(tiles, theme) -> None:
    """Paint the hub-and-spoke road network."""
    _paint_hub(tiles, theme)
    for x1, y1, x2, y2 in _SPOKES:
        _paint_spoke(tiles, theme, x1, y1, x2, y2)
    # Feeder roads
    road = theme.road_surface
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
    """Paint the landing apron around the spaceport."""
    # Central pad area — the spaceport is the heart of the city
    anchor = spec.hangar_anchor
    port = spec.buildings[0]
    x_lo = max(1, anchor.x - 5)
    x_hi = min(MARS_CITY_WIDTH - 2, anchor.x + 5)
    y_lo = port.y_hi + 1
    y_hi = min(MARS_CITY_HEIGHT - 2, anchor.y + 2)
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
    pad_x_lo = max(1, anchor.x - 5)
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
        ("=", "Trade Terminal", (56, 46), "trade_terminal", (100, 220, 255)),
        ("%", "Mechanic Terminal", (52, 46), "mech_terminal", (200, 220, 100)),
        ("A", "Armory Terminal", (48, 46), "armory_terminal", (255, 160, 80)),
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
