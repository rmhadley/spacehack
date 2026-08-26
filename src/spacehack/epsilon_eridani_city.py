"""Epsilon Eridani b's authored terraced canyon settlement."""

from __future__ import annotations

from dataclasses import replace

from . import world
from .city_kit import (
    add_service_terminals,
    add_showroom_ships,
    base_tiles,
    paint_door_forecourts,
    set_city_metadata,
)
from .city_layout import paint_roof_labels, stamp_city_assets
from .data.planets import _readable_city_theme
from .data.planets.themes import CANYON_SETTLEMENT


CITY_WIDTH = 200
CITY_HEIGHT = 140
_CANYON_X_LO, _CANYON_X_HI = 92, 107
_ROAD_ROWS = ((28, 29, 30), (58, 59, 60), (82, 83, 84), (118, 119, 120))
_BRIDGE_ROWS = ((34, 35, 36), (64, 65, 66), (92, 93, 94), (118, 119, 120))
_TRANSIT_SIDEWALKS = {
    "spaceport": ((34, 27),),
    "beacon": ((86, 47),),
    "bar": (
        (76, 76),
        *((76, y) for y in range(77, 82)),
    ),
    "merchants": ((128, 81),),
    "militia": ((166, 116),),
}

_CANYON_FLOOR = world.Tile(
    kind="canyon_floor", char=" ", walkable=False,
    fg=(112, 58, 42), bg=(42, 24, 22),
    blocked_message="The dry canyon drops away below the settlement.",
)
_CANYON_WALL = world.Tile(
    kind="canyon_wall", char="#", walkable=False,
    fg=(188, 105, 62), bg=(62, 32, 24),
    blocked_message="The canyon wall blocks your path.",
)
_MINE_ROCK = world.Tile(
    kind="mine_rock", char="#", walkable=False,
    fg=(150, 112, 82), bg=(46, 32, 24),
    blocked_message="The terraced rock face blocks your path.",
)
_MINE_SHAFT = world.Tile(
    kind="mine_shaft", char=" ", walkable=False,
    fg=(64, 46, 38), bg=(18, 14, 12),
    blocked_message="The mine shaft is sealed - too unstable to enter.",
)
_ORE_HEAP = world.Tile(
    kind="ore_heap", char="♦", walkable=True,
    fg=(214, 156, 78), bg=(66, 46, 28),
)

# A market square on the west bank fills the gap between the Beacon Spine
# plaza and the collectors with stalls; a sealed mine head sits on the
# north-eastern terrace as the settlement's reason for being.
_MARKET_X_LO, _MARKET_X_HI = 22, 50
_MARKET_Y_LO, _MARKET_Y_HI = 63, 79
_MINE_X_LO, _MINE_X_HI = 162, 183
_MINE_Y_LO, _MINE_Y_HI = 7, 19
_MINE_SHAFT_X_LO, _MINE_SHAFT_X_HI = 169, 176

# Frontier architecture: adobe, weathered steel, basalt, and oxidized
# copper, muted enough to read as sheds against the ochre canyon floor.
_HOMESTEAD_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((186, 136, 94), (64, 42, 28), (210, 168, 112), (74, 50, 32)),
    ((148, 156, 166), (44, 48, 58), (176, 184, 194), (52, 56, 66)),
    ((158, 124, 96), (56, 40, 30), (138, 178, 158), (40, 56, 46)),
    ((118, 108, 98), (40, 36, 32), (150, 140, 130), (46, 42, 38)),
    ((196, 158, 106), (68, 48, 32), (214, 182, 128), (78, 56, 36)),
)

# Non-enterable homestead sheds, one solar array, and a few ore/water
# stockpiles.  Each entry is ``(x, y, width, height, scheme_index)``;
# placement is skipped unless the whole footprint is open dust, so no
# shed can crowd a road, sidewalk, plaza, facade, or the canyon.
_HOMESTEADS: tuple[tuple[int, int, int, int, int], ...] = (
    # North terrace (west bank).
    (15, 6, 5, 4, 0), (40, 4, 6, 4, 1), (58, 8, 5, 5, 2),
    # Central terrace, west of the Beacon Spine (clear of the apron).
    (54, 37, 6, 5, 3), (54, 45, 5, 4, 4), (60, 40, 6, 5, 1),
    # South-west terraces.
    (18, 90, 7, 5, 0), (40, 100, 6, 4, 2), (60, 90, 5, 5, 3),
    (16, 125, 6, 5, 4), (38, 130, 7, 5, 0), (62, 125, 6, 4, 1),
    # East bank terraces.
    (118, 4, 5, 4, 2), (144, 6, 6, 5, 3),
    (118, 37, 6, 5, 4), (150, 44, 7, 5, 0), (170, 36, 5, 4, 1),
    (120, 88, 6, 5, 2), (146, 95, 5, 4, 3), (180, 94, 5, 4, 4),
    (120, 125, 6, 5, 0), (150, 130, 7, 5, 1), (180, 126, 5, 4, 2),
)
_SOLAR_ARRAY: tuple[int, int, int, int] = (123, 8, 8, 3)
_STOCKPILES: tuple[tuple[int, int], ...] = (
    (22, 88), (55, 103), (126, 96), (158, 130),
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "eri_spaceport": world.Position(20, 18),
    "eri_bar": world.Position(67, 68),
    "eri_merchants": world.Position(116, 70),
    "eri_militia": world.Position(151, 105),
}


def _carve_canyon(tiles) -> None:
    """Cut the dry canyon between its flanking canyon walls."""
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(_CANYON_X_LO, _CANYON_X_HI + 1):
            tiles[y][x] = _CANYON_FLOOR
        tiles[y][_CANYON_X_LO - 1] = _CANYON_WALL
        tiles[y][_CANYON_X_HI + 1] = _CANYON_WALL


def _paint_dust(tiles, theme):
    """Add sparse dry-ground texture without filling the city with noise."""
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and (x * 11 + y * 7) % 17 == 0:
                tiles[y][x] = theme.grass_accent


def _paint_cell(tiles, x, y, tile):
    """Paint public infrastructure only on open settlement ground."""
    if tiles[y][x].kind in {"floor", "grass"}:
        tiles[y][x] = tile


def _paint_horizontal_road(tiles, theme, y_lo, y_mid, y_hi):
    """Paint one three-cell road tier on both canyon banks."""
    for x in range(3, CITY_WIDTH - 2):
        if _CANYON_X_LO <= x <= _CANYON_X_HI:
            continue
        _paint_cell(tiles, x, y_lo, theme.road_surface)
        _paint_cell(tiles, x, y_mid, theme.road_ew)
        _paint_cell(tiles, x, y_hi, theme.road_surface)


def _paint_roads(tiles, theme):
    """Paint collectors, bank avenues, and the four canyon crossings."""
    for road in _ROAD_ROWS:
        _paint_horizontal_road(tiles, theme, *road)
    for x in (8, 9, 10, 88, 89, 90, 109, 110, 111, 188, 189, 190):
        for y in range(3, CITY_HEIGHT - 2):
            _paint_cell(tiles, x, y, theme.road_ns)
    for y_lo, y_mid, y_hi in _BRIDGE_ROWS:
        for y in range(y_lo, y_hi + 1):
            for x in range(_CANYON_X_LO - 1, _CANYON_X_HI + 2):
                tiles[y][x] = world.BRIDGE


def _paint_sidewalks(tiles, theme):
    """Paint two-cell sidewalks along collectors and bank avenues."""
    for y_lo, _y_mid, y_hi in _ROAD_ROWS:
        for x in range(3, CITY_WIDTH - 2):
            for y in (y_lo - 2, y_lo - 1, y_hi + 1, y_hi + 2):
                if not (_CANYON_X_LO <= x <= _CANYON_X_HI):
                    _paint_cell(tiles, x, y, theme.sidewalk)
    for x in (6, 7, 11, 12, 86, 87, 112, 113, 186, 187, 191, 192):
        for y in range(3, CITY_HEIGHT - 2):
            _paint_cell(tiles, x, y, theme.sidewalk)


def _paint_plaza(tiles, theme):
    """Build the civic Beacon Spine and its public terraces."""
    for y in range(40, 55):
        for x in range(70, 88):
            if tiles[y][x].kind in {"floor", "grass", "sidewalk"}:
                tiles[y][x] = theme.plaza
    for x, y in ((78, 43), (78, 51), (73, 47), (83, 47)):
        tiles[y][x] = theme.neon
    tiles[47][78] = world.MONUMENT


def _paint_apron(tiles, theme, spec):
    """Reserve a smooth landing plateau west of the spaceport."""
    pad_tile = replace(theme.landing_pad, char=" ")
    for y in range(31, 50):
        for x in range(18, 52):
            tiles[y][x] = pad_tile
    berth = spec.hangar_anchor
    tiles[berth.y][berth.x] = theme.plaza
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        tiles[berth.y + dy][berth.x + dx] = theme.neon


def _paint_transit_bays(tiles, theme, spec):
    """Paint floor bays beside continuous sidewalks, never over them."""
    bay_tile = replace(theme.floor, char=" ")
    for station in spec.transit_stations:
        tiles[station.pos.y][station.pos.x] = bay_tile
        for x, y in _TRANSIT_SIDEWALKS.get(station.id, ()):
            tiles[y][x] = theme.sidewalk


def _paint_settlement_details(tiles, theme):
    """Place sparse beacon lights and edge infrastructure."""
    details = (
        (12, 20), (58, 25), (68, 35), (86, 61), (116, 59),
        (116, 94), (137, 94), (145, 124), (183, 124),
        (44, 105), (61, 119), (129, 132), (181, 92),
    )
    for x, y in details:
        if tiles[y][x].kind in {"floor", "grass"}:
            tiles[y][x] = theme.neon


def _paint_market_square(tiles, theme):
    """Paint a west-bank market square between the two collectors."""
    for y in range(_MARKET_Y_LO, _MARKET_Y_HI + 1):
        for x in range(_MARKET_X_LO, _MARKET_X_HI + 1):
            if tiles[y][x].kind in {"floor", "grass"}:
                tiles[y][x] = theme.plaza
    # Two stall rows read as awnings without letter noise; a lone beacon
    # marks the square's center.
    for y in (66, 69, 72, 75):
        for x in (26, 32, 38, 44):
            tiles[y][x] = theme.decor
    tiles[70][35] = theme.neon


def _paint_mine_site(tiles, theme):
    """Carve a sealed mine head into the north-eastern terrace."""
    for y in range(_MINE_Y_LO, _MINE_Y_HI + 1):
        for x in range(_MINE_X_LO, _MINE_X_HI + 1):
            tiles[y][x] = _MINE_ROCK
    # The dark, sealed shaft mouth opens onto the settlement's south side.
    for y in range(_MINE_Y_LO + 3, _MINE_Y_HI + 1):
        for x in range(_MINE_SHAFT_X_LO, _MINE_SHAFT_X_HI + 1):
            tiles[y][x] = _MINE_SHAFT
    # Ore heaps and a work light in the staging yard below the head.
    for x, y in ((_MINE_X_LO + 9, _MINE_Y_HI + 3), (_MINE_X_LO + 13, _MINE_Y_HI + 3)):
        tiles[y][x] = _ORE_HEAP
    tiles[_MINE_Y_HI + 3][_MINE_X_LO + 11] = theme.neon


def _paint_shed(tiles, x, y, w, h, scheme_index):
    """Paint one corrugated-metal shed only on clear settlement dust."""
    if not all(
        tiles[by][bx].kind in {"floor", "grass"}
        for by in range(y, y + h)
        for bx in range(x, x + w)
    ):
        return
    wall_fg, wall_bg, roof_fg, roof_bg = _HOMESTEAD_SCHEMES[scheme_index]
    wall = world.Tile(
        kind="city_building_wall", char="#", walkable=False,
        fg=wall_fg, bg=wall_bg,
        blocked_message="The shed wall blocks your path.",
    )
    roof = world.Tile(
        kind="city_building_wall", char="~", walkable=False,
        fg=roof_fg, bg=roof_bg,
        blocked_message="The shed wall blocks your path.",
    )
    for by in range(y, y + h):
        for bx in range(x, x + w):
            if by in (y, y + h - 1) or bx in (x, x + w - 1):
                tiles[by][bx] = wall
            else:
                tiles[by][bx] = roof


def _paint_solar_array(tiles, x, y, w, h):
    """Paint a flat photovoltaic field on open dust."""
    if not all(
        tiles[by][bx].kind in {"floor", "grass"}
        for by in range(y, y + h)
        for bx in range(x, x + w)
    ):
        return
    panel = world.Tile(
        kind="city_building_wall", char="▓", walkable=False,
        fg=(92, 148, 176), bg=(24, 40, 56),
        blocked_message="The solar array blocks your path.",
    )
    for by in range(y, y + h):
        for bx in range(x, x + w):
            tiles[by][bx] = panel


def _paint_homesteads(tiles, theme):
    """Scatter non-enterable sheds, a solar array, and ore stockpiles."""
    for x, y, w, h, scheme_index in _HOMESTEADS:
        _paint_shed(tiles, x, y, w, h, scheme_index)
    x, y, w, h = _SOLAR_ARRAY
    _paint_solar_array(tiles, x, y, w, h)
    for x, y in _STOCKPILES:
        if tiles[y][x].kind in {"floor", "grass"}:
            tiles[y][x] = _ORE_HEAP


_SHIPS_ORIGIN = world.Position(24, 32)  # landing plateau dock


def build_epsilon_eridani_layout(spec, resolve_ship):
    """Build Epsilon Eridani b's 200x140 terraced canyon settlement."""
    theme = _readable_city_theme(CANYON_SETTLEMENT)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _carve_canyon(tiles)
    _paint_dust(tiles, theme)
    _paint_roads(tiles, theme)
    _paint_sidewalks(tiles, theme)
    _paint_plaza(tiles, theme)
    _paint_apron(tiles, theme, spec)
    _paint_market_square(tiles, theme)
    _paint_mine_site(tiles, theme)
    _paint_settlement_details(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
    )
    _paint_transit_bays(game_map.tiles, theme, spec)
    paint_roof_labels(game_map, stamps, "eri_")
    _paint_homesteads(game_map.tiles, theme)
    set_city_metadata(
        game_map, spec, stamps,
        prefix="eri_", default_layout_id="eri_canyon_settlement",
    )
    game_map.canyon_cells = {
        (x, y)
        for y in range(2, CITY_HEIGHT - 2)
        for x in range(_CANYON_X_LO, _CANYON_X_HI + 1)
    }
    game_map.bridge_crossings = _BRIDGE_ROWS
    add_showroom_ships(game_map, spec, resolve_ship, origin=_SHIPS_ORIGIN)
    add_service_terminals(game_map, spec)
    return game_map


__all__ = ["build_epsilon_eridani_layout", "LANDMARK_ORIGINS"]
