"""Mars's authored high-tech colony city layout.

Mars is a planned terraformed settlement rather than a frontier camp.  The
red landscape remains visible between districts, while a legible boulevard
and avenue plan organizes civic, commercial, security, and logistics uses.
The shared city stamping/transit/NPC machinery remains data-driven.
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
from .data.planets.themes import MARS_CITY
from .city_tiles import CITY_ORNAMENT


MARS_CITY_WIDTH = 160
MARS_CITY_HEIGHT = 100

# A southern logistics port keeps heavy traffic at the edge of the civic
# fabric.  The other buildings sit in distinct, serviced urban blocks.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "mars_spaceport": world.Position(10, 79),
    "mars_bar": world.Position(101, 14),
    "mars_merchants": world.Position(18, 31),
    "mars_militia": world.Position(125, 64),
    "mars_bounties": world.Position(87, 31),
}

# Three-wide boulevards are the primary public circulation network.  The
# center tile carries a directional lane marker, matching Earth, while the
# outer lanes form a continuous paved corridor.
_BOULEVARDS_Y: tuple[tuple[int, int, int], ...] = (
    (24, 25, 26),   # north mixed-use boulevard
    (48, 49, 50),   # central civic boulevard
    (75, 76, 77),   # south residential/security boulevard
    (89, 90, 91),   # port logistics boulevard
)
_AVENUES_X: tuple[tuple[int, int, int], ...] = (
    (39, 40, 41),   # west market avenue
    (79, 80, 81),   # civic spine
    (121, 122, 123),  # east services avenue
)

# A small civic square is the social center of the colony.  Its solid
# surface prevents skyline filler from swallowing the public space.
_PLAZA_X_LO, _PLAZA_X_HI = 57, 76
_PLAZA_Y_LO, _PLAZA_Y_HI = 31, 45

# Transit platforms and civic fixtures are authored onto sidewalk/plaza cells
# before the skyline pass, which reserves those cells from procedural roofs.
_STATION_PADS: tuple[tuple[int, int], ...] = (
    (35, 87),   # spaceport pad, beside the logistics boulevard
    (76, 46),   # civic square, beside the central boulevard
    (111, 22),  # north entertainment district
    (43, 31),   # west merchant district
    (125, 72),  # east security district
    (83, 39),   # civic services / bounty hall
)

_NEON_POSITIONS: tuple[tuple[int, int], ...] = (
    (35, 87), (76, 46), (111, 22), (43, 31), (125, 72), (83, 39),
    (52, 24), (67, 24), (94, 24), (138, 24),
    (52, 48), (95, 48), (112, 48), (138, 48),
    (52, 75), (94, 75), (112, 75), (138, 75),
    (69, 32), (69, 44), (58, 38), (76, 38),
)
_ORNAMENT_POSITIONS: tuple[tuple[int, int], ...] = (
    (60, 33), (73, 33), (60, 43), (73, 43),
    (64, 37), (69, 41), (73, 37),
    (106, 23), (114, 23), (38, 32), (47, 32),
    (121, 72), (126, 72), (132, 73),
)

# High-tech architecture: white ceramic, glass cyan, graphite, and signal
# orange.  These colors contrast with the red dust without turning the city
# into a brown field of identical shelters.
_SKYLINE_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((218, 228, 236), (42, 52, 64), (150, 220, 238), (34, 68, 82)),
    ((172, 208, 224), (38, 55, 70), (225, 238, 242), (48, 76, 90)),
    ((194, 198, 208), (44, 48, 60), (110, 190, 220), (30, 62, 78)),
    ((230, 220, 198), (62, 54, 48), (255, 164, 88), (78, 48, 30)),
    ((134, 158, 178), (34, 42, 56), (190, 216, 228), (42, 68, 82)),
)


def _colony_theme():
    """Return the readable Mars palette for the outdoor city."""
    return _readable_city_theme(MARS_CITY)


def _paint_cell(tiles, x: int, y: int, tile: world.Tile) -> None:
    """Paint a public-surface tile without replacing authored terrain."""
    if tiles[y][x].kind in {"floor", "grass"}:
        tiles[y][x] = tile


def _paint_road_corridors(tiles, theme) -> None:
    """Paint Mars's four boulevards and three connecting avenues."""
    for y_lo, y_mid, y_hi in _BOULEVARDS_Y:
        for x in range(2, MARS_CITY_WIDTH - 2):
            _paint_cell(tiles, x, y_lo, theme.road_surface)
            _paint_cell(tiles, x, y_mid, theme.road_ew)
            _paint_cell(tiles, x, y_hi, theme.road_surface)
    for x_lo, x_mid, x_hi in _AVENUES_X:
        for y in range(2, MARS_CITY_HEIGHT - 2):
            _paint_cell(tiles, x_lo, y, theme.road_surface)
            _paint_cell(tiles, x_mid, y, theme.road_ns)
            _paint_cell(tiles, x_hi, y, theme.road_surface)


def _paint_sidewalks(tiles, theme) -> None:
    """Add one-cell pedestrian bands beside each major road."""
    for y_lo, _y_mid, y_hi in _BOULEVARDS_Y:
        for x in range(2, MARS_CITY_WIDTH - 2):
            for y in (y_lo - 1, y_hi + 1):
                if 0 <= y < MARS_CITY_HEIGHT:
                    _paint_cell(tiles, x, y, theme.sidewalk)
    for x_lo, _x_mid, x_hi in _AVENUES_X:
        for y in range(2, MARS_CITY_HEIGHT - 2):
            for x in (x_lo - 1, x_hi + 1):
                if 0 <= x < MARS_CITY_WIDTH:
                    _paint_cell(tiles, x, y, theme.sidewalk)


def _paint_plaza(tiles, theme) -> None:
    """Paint the central civic square and its beacon."""
    for y in range(_PLAZA_Y_LO, _PLAZA_Y_HI + 1):
        for x in range(_PLAZA_X_LO, _PLAZA_X_HI + 1):
            if tiles[y][x].kind in {"floor", "grass", "sidewalk"}:
                tiles[y][x] = theme.plaza
    tiles[38][67] = world.MONUMENT
    for x, y in ((67, 36), (67, 40), (65, 38), (69, 38)):
        tiles[y][x] = CITY_ORNAMENT


def _paint_station_pads(tiles, theme) -> None:
    """Reserve one-cell pads beside sidewalks without consuming them."""
    for x, y in _STATION_PADS:
        if tiles[y][x].walkable and tiles[y][x].kind not in {"road", "landing_pad"}:
            tiles[y][x] = theme.plaza


def _restore_station_pads(game_map, theme) -> None:
    """Restore transit pads after door routes have painted sidewalks."""
    for x, y in _STATION_PADS:
        if game_map.tiles[y][x].walkable:
            game_map.tiles[y][x] = theme.plaza


def _paint_red_terrain(tiles, theme) -> None:
    """Turn open ground into varied red dust before city infrastructure."""
    for y in range(2, MARS_CITY_HEIGHT - 2):
        for x in range(2, MARS_CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor":
                tiles[y][x] = (
                    theme.grass_accent if (x * 7 + y * 11) % 13 == 0
                    else theme.grass
                )


def _paint_port_apron(tiles, theme, spec) -> None:
    """Paint a compact landing apron immediately below the port."""
    port = spec.buildings[0]
    for y in range(port.y_hi + 1, port.y_hi + 4):
        for x in range(port.x_lo + 5, port.x_hi - 4):
            _paint_cell(tiles, x, y, theme.landing_pad)


def _paint_decorations(tiles, theme) -> None:
    """Place restrained signal lights around public spaces and roads."""
    station_pads = set(_STATION_PADS)
    for x, y in _NEON_POSITIONS:
        if (x, y) in station_pads:
            continue
        if tiles[y][x].kind in {"sidewalk", "plaza", "landing_pad"}:
            tiles[y][x] = theme.neon
    for x, y in _ORNAMENT_POSITIONS:
        if tiles[y][x].kind in {"sidewalk", "plaza"}:
            tiles[y][x] = CITY_ORNAMENT


def _base_map(theme) -> list[list[world.Tile]]:
    """Create the red terrain grid with perimeter walls."""
    tiles = [
        [theme.floor for _ in range(MARS_CITY_WIDTH)]
        for _ in range(MARS_CITY_HEIGHT)
    ]
    for x in range(MARS_CITY_WIDTH):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(MARS_CITY_HEIGHT):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL
    return tiles


def _new_mars_map(spec) -> world.GameMap:
    """Build Mars's terrain, public realm, and logistics apron."""
    theme = _colony_theme()
    tiles = _base_map(theme)
    _paint_red_terrain(tiles, theme)
    _paint_road_corridors(tiles, theme)
    _paint_sidewalks(tiles, theme)
    _paint_plaza(tiles, theme)
    _paint_station_pads(tiles, theme)
    _paint_port_apron(tiles, theme, spec)
    _paint_decorations(tiles, theme)
    return world.GameMap(
        width=MARS_CITY_WIDTH, height=MARS_CITY_HEIGHT,
        tiles=tiles, entities=[],
    )


def _set_mars_metadata(game_map, spec, stamps) -> None:
    """Attach persistent Mars district and landmark metadata."""
    game_map.city_layout_id = spec.city_layout_id or "mars_colony"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_districts = {
        "spaceport": (3, 78, 38, 96),
        "merchant": (3, 27, 43, 47),
        "civic": (52, 27, 109, 47),
        "entertainment": (84, 3, 119, 27),
        "security": (124, 52, 157, 78),
        "residential": (43, 52, 120, 96),
    }
    game_map.city_buildings = building_records(spec, stamps, "mars_")


def _add_service_entities(game_map, spec, resolve_ship) -> None:
    """Place port ships and service consoles on the southern apron."""
    port = spec.buildings[0]
    pad_y = port.y_hi + 1
    pad_x = port.x_lo + 5
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        game_map.entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(pad_x + off_x, pad_y + off_y),
            name=f"Ship: {ship_obj.name}", ship_id=ship_obj.id,
            width=ship_obj.width, height=ship_obj.height,
        ))
    terminal_data = (
        ("=", "Trade Terminal", (17, 88), "trade_terminal", (100, 230, 255)),
        ("%", "Mechanic Terminal", (22, 88), "mech_terminal", (190, 240, 150)),
        ("A", "Armory Terminal", (27, 88), "armory_terminal", (255, 170, 90)),
    )
    for char, name, position, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg, pos=world.Position(*position),
            name=name, **{flag: True},
        ))


def build_mars_layout(spec, resolve_ship) -> world.GameMap:
    """Build Mars's 160x100 planned colony from data and authored assets."""
    game_map = _new_mars_map(spec)
    stamps = stamp_city_assets(game_map, LANDMARK_ORIGINS)
    _restore_station_pads(game_map, _colony_theme())
    paint_roof_labels(game_map, stamps, "mars_")
    paint_skyline(
        game_map,
        seed_key=("mars", "planned_colony"),
        schemes=_SKYLINE_SCHEMES,
        site_kinds=frozenset({"grass"}),
        roof_char="#",
        width_range=(5, 8),
        height_range=(4, 6),
        min_size=(5, 4),
        row_stride=2,
    )
    _set_mars_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


__all__ = ["build_mars_layout"]
