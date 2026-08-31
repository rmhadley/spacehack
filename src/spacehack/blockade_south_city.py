"""Blockade South — The Quarantine Cordon station-deck builder."""
from __future__ import annotations

from dataclasses import replace

from . import world
from .city_kit import (
    TERMINAL_PALETTE_CLASSIC,
    add_service_terminals,
    add_showroom_ships,
    base_tiles,
    paint_door_forecourts,
    paint_transit_bays,
    set_city_metadata,
)
from .city_layout import paint_roof_labels, stamp_city_assets
from .data.planets import _readable_city_theme
from .data.planets.themes import T, derive_theme, override_theme
from .lighting import collect_light_sources, propagate_light


WIDTH, HEIGHT = 140, 90
THEME = override_theme(
    derive_theme(
        floor=(72, 82, 102), grass=(42, 50, 68), accent=(255, 72, 72),
        road_surface=T("road", "▓", (190, 210, 225), (18, 24, 34)),
        road_ns=T("road", ":", (90, 220, 240), (24, 42, 58)),
        road_ew=T("road", "-", (90, 220, 240), (24, 42, 58)),
        sidewalk=T("sidewalk", "▒", (155, 170, 182), (54, 64, 78)),
        plaza=T("plaza", "░", (190, 205, 210), (72, 84, 96)),
        landing_pad=T("landing_pad", "▓", (170, 205, 220), (42, 58, 72)),
        neon=T("neon", "*", (255, 72, 72), (64, 18, 22)),
    ),
    floor=T("floor", ".", (95, 110, 130), (52, 62, 80)),
)

ORIGINS = {
    "blockade_south_spaceport": world.Position(7, 5),
    "blockade_south_bounties": world.Position(12, 67),
    "blockade_south_militia": world.Position(104, 67),
}

DECK = T("station_deck", ".", (100, 112, 128), (52, 62, 80))
BULKHEAD = world.Tile("station_bulkhead", "#", False, (150, 170, 185), (34, 42, 54))
QUARANTINE = world.Tile("quarantine", "+", True, (220, 170, 90), (95, 90, 100))
WARNING = world.Tile("neon", "!", False, (255, 72, 72), (70, 14, 18))
BEACON = world.Tile("beacon", "!", False, (255, 225, 125), (50, 42, 35))
BAY = T("transit_bay", "=", (100, 230, 245), (38, 72, 88))

# Planned circulation as (x_lo, x_hi, y_lo, y_hi, orientation) bands.
# Bands overlap at junctions so the painted network is one component.
_ARTERIAL = (2, 137, 42, 44, "ew")        # main deck crossing, full width
_WEST_SPINE = (44, 46, 2, 87, "ns")       # top edge down to the south street
_APRON_SPUR = (19, 21, 26, 41, "ns")      # apron south edge down to the arterial
_SOUTH_STREET = (2, 137, 79, 81, "ew")    # fronts the claims and watch stops
_COLLECTOR_WEST = (33, 35, 44, 81, "ns")  # arterial down to the south street
_COLLECTOR_EAST = (131, 133, 44, 81, "ns")

# Roads only replace open deck; pads, plaza, yards, walls, and lights survive.
_ROAD_HOST_KINDS = frozenset({"station_deck", "floor"})


def _paint_hull(tiles):
    for y in range(1, HEIGHT - 1):
        for x in range(1, WIDTH - 1):
            tiles[y][x] = DECK
    for x in range(WIDTH):
        tiles[1][x] = BULKHEAD
        tiles[HEIGHT - 2][x] = BULKHEAD
    for y in range(1, HEIGHT - 1):
        tiles[y][1] = BULKHEAD
        tiles[y][WIDTH - 2] = BULKHEAD


def _paint_apron_and_hall(tiles, theme) -> None:
    for y in range(15, 26):
        for x in range(4, 40):
            tiles[y][x] = replace(theme.landing_pad, char=".")
    for y in range(25, 39):
        for x in range(48, 93):
            tiles[y][x] = theme.plaza
    for x in range(52, 90, 7):
        tiles[27][x] = theme.neon
        tiles[37][x] = theme.neon
    tiles[32][70] = BEACON
    tiles[48][70] = BEACON


def _paint_quarantine_yards(tiles) -> None:
    for y in range(52, 66):
        for x in range(82, 126):
            if (x + y) % 4 == 0:
                tiles[y][x] = QUARANTINE
    for x in range(84, 124, 8):
        tiles[52][x] = BULKHEAD
        tiles[65][x] = BULKHEAD
    for y in range(53, 65, 4):
        tiles[y][83] = BULKHEAD
        tiles[y][125] = BULKHEAD
    for x in range(124, 133):
        tiles[27][x] = BULKHEAD
        tiles[28][x] = WARNING
    tiles[28][132] = WARNING


def _paint_lights(tiles) -> None:
    tiles[47][70] = BEACON
    for x in range(25, 121, 12):
        if tiles[47][x].walkable:
            tiles[47][x] = T("neon", "*", (80, 220, 240), (25, 55, 68))
    for x in range(86, 126, 10):
        tiles[60][x] = T("neon", "*", (255, 180, 70), (68, 40, 18))
    for x, y in ((7, 18), (36, 18), (48, 32), (92, 32), (21, 47), (116, 47)):
        tiles[y][x] = WARNING


def _paint_road_band(tiles, theme, x_lo, x_hi, y_lo, y_hi, orientation) -> None:
    """Paint one three-wide right-of-way with a lane marker down its center."""
    mid_y = (y_lo + y_hi) // 2
    mid_x = (x_lo + x_hi) // 2
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            if tiles[y][x].kind not in _ROAD_HOST_KINDS:
                continue
            if orientation == "ns" and x == mid_x:
                tiles[y][x] = theme.road_ns
            elif orientation == "ew" and y == mid_y:
                tiles[y][x] = theme.road_ew
            else:
                tiles[y][x] = theme.road_surface


def _paint_road_network(tiles, theme) -> None:
    """Paint the planned station circulation over open deck only."""
    for x_lo, x_hi, y_lo, y_hi, orientation in (
        _ARTERIAL, _WEST_SPINE, _APRON_SPUR,
        _SOUTH_STREET, _COLLECTOR_WEST, _COLLECTOR_EAST,
    ):
        _paint_road_band(tiles, theme, x_lo, x_hi, y_lo, y_hi, orientation)


def _paint_deck(game_map, spec, theme, stamps) -> None:
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=WIDTH, height=HEIGHT,
        overwrite_kinds=frozenset({"station_deck", "floor"}),
    )
    paint_transit_bays(
        game_map.tiles, spec, BAY, width=WIDTH, height=HEIGHT,
        overwrite_kinds=frozenset({"station_deck", "plaza", "sidewalk"}),
        force_center=True,
    )
    paint_roof_labels(game_map, stamps, "blockade_south_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="blockade_south_", default_layout_id="blockade_south_quarantine",
    )
    sources = collect_light_sources(game_map)
    game_map.light_sources = sources
    game_map.light_grid = propagate_light(
        WIDTH, HEIGHT, sources,
        occluder=lambda x, y: not game_map.tiles[y][x].walkable,
    )


def build_blockade_south_layout(spec, resolve_ship) -> world.GameMap:
    """Build Blockade South's 140x90 quarantine station deck."""
    theme = _readable_city_theme(THEME)
    tiles = base_tiles(WIDTH, HEIGHT, theme.floor)
    _paint_hull(tiles)
    _paint_apron_and_hall(tiles, theme)
    tiles[76][21] = theme.plaza
    tiles[76][117] = theme.plaza
    for x in range(18, 21):
        tiles[14][x] = theme.landing_pad
    _paint_quarantine_yards(tiles)
    _paint_lights(tiles)
    _paint_road_network(tiles, theme)
    game_map = world.GameMap(WIDTH, HEIGHT, tiles=tiles, entities=[])
    stamps = stamp_city_assets(game_map, ORIGINS, sidewalk=theme.sidewalk)
    _paint_deck(game_map, spec, theme, stamps)
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(game_map, spec, dy=5, dxs=(-5, -2, 3), palette=TERMINAL_PALETTE_CLASSIC)
    return game_map


__all__ = ["build_blockade_south_layout"]
