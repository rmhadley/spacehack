"""Earth's authored river-coast city layout generator.

Phase 5: this module is one *layout* in the generic city pipeline
(:mod:`spacehack.city_builder` dispatches on ``city_layout_id ==
\"earth_river_coast\"`). It owns Earth's terrain (river, coast, roads,
parks, pad) and its authored asset data (origins, skyline schemes).
The shared authored-layout machinery — asset stamping, roof labels,
skyline painting, building records — lives in
:mod:`spacehack.city_layout` and is reused verbatim by Mercury's
station layout, so every authored city runs the same pipeline.

The shared city tail (transit stations + ambient NPCs) runs in
``city_builder.build_city`` for every planet, Earth included.
"""

from __future__ import annotations

from . import city_tiles, world
from .city_layout import (
    building_records,
    paint_roof_labels,
    paint_skyline,
    stamp_city_assets,
    stamp_metadata,
)


EARTH_CITY_WIDTH = 160
EARTH_CITY_HEIGHT = 100

# Water runs diagonally from the west map edge to the eastern coast.
# Bridges are deliberately wide enough to remain readable and easy to find.
RIVER_CELLS: frozenset[tuple[int, int]] = frozenset(
    (x, y)
    for x in range(1, 143)
    for y in range(max(1, 42 - x // 8), min(98, 47 - x // 8) + 1)
)
COAST_CELLS: frozenset[tuple[int, int]] = frozenset(
    (x, y) for x in range(143, 159) for y in range(1, 99)
)
# Each crossing is ``(center_x, center_y, half_height)``. The river runs
# generally east-west, so bridges run north-south through the full water band.
BRIDGE_CROSSINGS: tuple[tuple[int, int, int], ...] = (
    (49, 39, 6),
    (86, 35, 6),
    (109, 31, 6),
)

# Fixed authored origins. The assets remain easy to replace without moving
# the surrounding city data or interaction logic. Origins are chosen so no
# building footprint overlaps the road grid or the river bank.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "earth_city_spaceport": world.Position(12, 12),
    "earth_city_bar": world.Position(112, 10),
    "earth_city_bounties": world.Position(120, 58),
    "earth_city_merchants": world.Position(12, 62),
    "earth_city_militia": world.Position(54, 70),
    "earth_city_plaza": world.Position(70, 52),
}

# Procedural skyline: decorative (non-enterable) buildings fill the city
# blocks between the road grid and the river. A fixed seed keeps the same
# city every run, matching the deterministic terrain generation.
# Each scheme is ``(wall_fg, wall_bg, roof_fg, roof_bg)`` for one building.
# Muted hues with low wall/roof contrast keep the skyline colorful but calm.
_SKYLINE_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((168, 196, 222), (58, 70, 86), (186, 208, 228), (66, 80, 96)),   # steel blue
    ((152, 200, 192), (54, 70, 68), (172, 212, 206), (62, 80, 78)),   # teal
    ((188, 176, 214), (66, 60, 80), (204, 194, 224), (74, 68, 88)),   # violet
    ((218, 190, 152), (74, 62, 46), (232, 208, 176), (82, 70, 54)),   # amber
    ((164, 200, 164), (56, 70, 56), (184, 214, 184), (64, 78, 64)),   # green
    ((196, 196, 208), (64, 64, 72), (212, 212, 220), (72, 72, 80)),   # slate
)


def _base_tiles() -> list[list[world.Tile]]:
    """Create the Earth terrain base with perimeter walls."""
    tiles = [
        [world.EARTH_THEME.floor for _ in range(EARTH_CITY_WIDTH)]
        for _ in range(EARTH_CITY_HEIGHT)
    ]
    for x in range(EARTH_CITY_WIDTH):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(EARTH_CITY_HEIGHT):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL
    return tiles


def _paint_water_and_shore(tiles: list[list[world.Tile]]) -> None:
    """Paint the river, shoreline, and a small northwest wetland."""
    water_cells = RIVER_CELLS | COAST_CELLS
    for x, y in water_cells:
        tiles[y][x] = city_tiles.CITY_WATER
    for x, y in water_cells:
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            shore_x, shore_y = x + dx, y + dy
            if not (0 <= shore_x < EARTH_CITY_WIDTH and 0 <= shore_y < EARTH_CITY_HEIGHT):
                continue
            if tiles[shore_y][shore_x].kind == "floor":
                tiles[shore_y][shore_x] = city_tiles.CITY_SHORE
    for x in range(8, 25):
        for y in range(30, 39):
            if (x + y) % 3:
                tiles[y][x] = city_tiles.CITY_SHORE


def _paint_bridges(tiles: list[list[world.Tile]]) -> None:
    """Paint north-south bridges with roads approaching both banks."""
    for center_x, _center_y, _half_height in BRIDGE_CROSSINGS:
        bridge_xs = range(center_x - 1, center_x + 2)
        river_rows = [
            y for y in range(1, EARTH_CITY_HEIGHT - 1)
            if any((x, y) in RIVER_CELLS for x in bridge_xs)
        ]
        if not river_rows:
            continue
        bridge_rows = range(min(river_rows) - 1, max(river_rows) + 2)
        for y in bridge_rows:
            for x in bridge_xs:
                tiles[y][x] = city_tiles.CITY_BRIDGE
        for y in range(4, EARTH_CITY_HEIGHT - 1):
            for x in bridge_xs:
                if tiles[y][x].kind in {
                    "city_water", "city_bridge", "city_building_wall",
                    "city_building_floor", "city_building_door",
                }:
                    continue
                tiles[y][x] = world.ROAD_SURFACE


def _paint_road_cell(
    tiles: list[list[world.Tile]], x: int, y: int, tile: world.Tile,
) -> None:
    """Paint a road only on dry land; bridges own river crossings."""
    if tiles[y][x].kind not in {"city_water", "city_shore"}:
        tiles[y][x] = tile


def _paint_roads_and_districts(tiles: list[list[world.Tile]]) -> None:
    """Paint a readable road network around the water and districts."""
    road = world.ROAD_SURFACE
    lane_ns = world.ROAD_NS
    lane_ew = world.ROAD_EW
    for y in range(3, 97):
        for x in (48, 49, 50, 108, 109, 110):
            _paint_road_cell(tiles, x, y, lane_ns if x in {49, 109} else road)
    for x in range(3, 143):
        for y in (49, 50, 51, 78, 79, 80):
            _paint_road_cell(tiles, x, y, lane_ew if y in {50, 79} else road)
    # Short feeder roads toward the five core districts. Roads never run
    # east of the x=108 bridge road at these latitudes: the river's diagonal
    # bank would slice through the pavement, so the bridge road owns access
    # to the waterfront district.
    for x in range(24, 49):
        for y in (26, 27, 28):
            _paint_road_cell(tiles, x, y, lane_ew if y == 27 else road)
    for x in range(50, 93):
        for y in (64, 65, 66):
            _paint_road_cell(tiles, x, y, lane_ew if y == 65 else road)


def _paint_parks_and_details(tiles: list[list[world.Tile]]) -> None:
    """Add deterministic parks, trees, lamps, and district texture."""
    for x in range(4, 157):
        for y in range(3, 97):
            if tiles[y][x] is world.EARTH_THEME.floor:
                tiles[y][x] = world.GRASS_ACCENT if (x * 7 + y * 11) % 13 == 0 else world.GRASS
    for x, y in (
        (8, 8), (32, 16), (66, 20), (104, 18), (145, 12),
        (8, 55), (34, 88), (66, 87), (118, 88), (136, 70),
    ):
        if tiles[y][x].walkable:
            tiles[y][x] = world.TREE
    for x, y in ((56, 43), (64, 57), (116, 43), (134, 55), (74, 84)):
        if tiles[y][x].walkable:
            tiles[y][x] = world.NEON


def _paint_landing_pad(tiles: list[list[world.Tile]]) -> None:
    """Place the port landing apron below the spaceport."""
    _pad = world.Tile(
        kind="landing_pad", char=".", walkable=True,
        fg=(100, 210, 255), bg=(40, 64, 98),
    )
    for y in range(20, 30):
        for x in range(18, 38):
            if (x, y) not in RIVER_CELLS:
                tiles[y][x] = _pad


def _new_earth_map() -> world.GameMap:
    """Create and decorate the expanded outdoor terrain."""
    tiles = _base_tiles()
    _paint_water_and_shore(tiles)
    _paint_roads_and_districts(tiles)
    _paint_bridges(tiles)
    _paint_parks_and_details(tiles)
    _paint_landing_pad(tiles)
    return world.GameMap(
        width=EARTH_CITY_WIDTH, height=EARTH_CITY_HEIGHT,
        tiles=tiles, entities=[],
    )


def _set_city_metadata(game_map, spec, stamps) -> None:
    """Attach persistent city layout metadata to the map."""
    game_map.city_layout_id = spec.city_layout_id or "earth_river_coast"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.water_cells = {
        (x, y) for x, y in RIVER_CELLS | COAST_CELLS
        if game_map.tiles[y][x].kind == "city_water"
    }
    game_map.bridge_crossings = BRIDGE_CROSSINGS
    game_map.city_districts = {
        "spaceport": (4, 8, 52, 39), "plaza": (54, 35, 106, 61),
        "waterfront": (112, 1, 158, 98), "market": (4, 53, 56, 96),
        "civic": (58, 62, 110, 96),
    }
    game_map.city_buildings = building_records(spec, stamps, "earth_city_")


def _add_service_entities(game_map, spec, resolve_ship) -> None:
    """Add showroom ships and spaceport terminals to the street.

    Service NPCs live inside their authored interiors (seated when the
    room is first loaded), so nothing stands on the pavement outside.
    """
    # Showroom ships sit on the landing pad south of the solid hangar roof
    # (offsets are relative to the pad's top-left corner, x=18 / y=20).
    _pad_x, _pad_y = 18, 20
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        game_map.entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(_pad_x + off_x, _pad_y + off_y),
            name=f"Ship: {ship_obj.name}", ship_id=ship_obj.id,
            width=ship_obj.width, height=ship_obj.height,
        ))
    terminal_data = (
        ("=", "Trade Terminal", world.Position(34, 29), "trade_terminal", (100, 220, 255)),
        ("%", "Mechanic Terminal", world.Position(30, 29), "mech_terminal", (200, 220, 100)),
        ("A", "Armory Terminal", world.Position(25, 29), "armory_terminal", (255, 160, 80)),
    )
    for char, name, position, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg, pos=position, name=name, **{flag: True},
        ))


def build_earth_layout(spec, resolve_ship) -> world.GameMap:
    """Build Earth's 160x100 river-coast terrain + authored buildings.

    Transit stations and ambient NPCs are NOT placed here — the generic
    :func:`spacehack.city_builder.build_city` shared tail adds them for
    every planet, so Earth and Mercury run the identical city pipeline.
    """
    game_map = _new_earth_map()
    stamps = stamp_city_assets(game_map, LANDMARK_ORIGINS)
    paint_roof_labels(game_map, stamps, "earth_city_")
    paint_skyline(
        game_map,
        seed_key=("earth", "skyline"),
        schemes=_SKYLINE_SCHEMES,
    )
    _set_city_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map
