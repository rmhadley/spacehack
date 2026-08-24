"""Epsilon Eridani b's authored terraced canyon settlement."""

from __future__ import annotations

from dataclasses import replace

from . import world
from .city_layout import (
    building_records,
    paint_roof_labels,
    stamp_city_assets,
    stamp_metadata,
)
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
    "bar": ((75, 56),),
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

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "eri_spaceport": world.Position(20, 18),
    "eri_bar": world.Position(67, 48),
    "eri_merchants": world.Position(116, 70),
    "eri_militia": world.Position(151, 105),
}


def _base_tiles(theme):
    """Create dusty terrain with a dry canyon and perimeter walls."""
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    for x in range(CITY_WIDTH):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(CITY_HEIGHT):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(_CANYON_X_LO, _CANYON_X_HI + 1):
            tiles[y][x] = _CANYON_FLOOR
        tiles[y][_CANYON_X_LO - 1] = _CANYON_WALL
        tiles[y][_CANYON_X_HI + 1] = _CANYON_WALL
    return tiles


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
        for x in range(3, _CANYON_X_LO):
            _paint_cell(tiles, x, y_mid, theme.road_ew)
        for x in range(_CANYON_X_HI + 1, CITY_WIDTH - 2):
            _paint_cell(tiles, x, y_mid, theme.road_ew)


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


def _paint_building_forecourts(tiles, theme, spec):
    """Give every south-facing door a three-cell sidewalk forecourt."""
    for building in spec.buildings:
        y = building.y_lo - 1 if building.door_north else building.y_hi + 1
        for x in range(building.door_x - 1, building.door_x + 2):
            if 0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT:
                tiles[y][x] = theme.sidewalk


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


def _add_service_entities(game_map, spec, resolve_ship):
    """Place showroom ships and service terminals on the landing plateau."""
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        game_map.entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(24 + off_x, 32 + off_y),
            name=f"Ship: {ship_obj.name}", ship_id=ship_obj.id,
            width=ship_obj.width, height=ship_obj.height,
        ))
    berth = spec.hangar_anchor
    terminal_data = (
        ("=", "Trade Terminal", -6, "trade_terminal", (100, 220, 255)),
        ("%", "Mechanic Terminal", -2, "mech_terminal", (210, 220, 110)),
        ("A", "Armory Terminal", 2, "armory_terminal", (255, 165, 85)),
    )
    for char, name, dx, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg,
            pos=world.Position(berth.x + dx, berth.y + 3),
            name=name, **{flag: True},
        ))


def _set_metadata(game_map, spec, stamps):
    """Attach authored landmark and canyon metadata."""
    game_map.city_layout_id = spec.city_layout_id or "eri_canyon_settlement"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.canyon_cells = {
        (x, y)
        for y in range(2, CITY_HEIGHT - 2)
        for x in range(_CANYON_X_LO, _CANYON_X_HI + 1)
    }
    game_map.bridge_crossings = _BRIDGE_ROWS
    game_map.city_buildings = building_records(spec, stamps, "eri_")


def build_epsilon_eridani_layout(spec, resolve_ship):
    """Build Epsilon Eridani b's 200x140 terraced canyon settlement."""
    theme = _readable_city_theme(CANYON_SETTLEMENT)
    tiles = _base_tiles(theme)
    _paint_dust(tiles, theme)
    _paint_roads(tiles, theme)
    _paint_sidewalks(tiles, theme)
    _paint_plaza(tiles, theme)
    _paint_apron(tiles, theme, spec)
    _paint_settlement_details(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    _paint_building_forecourts(game_map.tiles, theme, spec)
    _paint_transit_bays(game_map.tiles, theme, spec)
    paint_roof_labels(game_map, stamps, "eri_")
    _set_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


__all__ = ["build_epsilon_eridani_layout", "LANDMARK_ORIGINS"]
