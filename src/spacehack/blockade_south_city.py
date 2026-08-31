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
        road_surface=T("road", "▓", (185, 205, 220), (18, 24, 34)),
        road_ns=T("road", "║", (120, 240, 255), (12, 32, 46)),
        road_ew=T("road", "═", (120, 240, 255), (12, 32, 46)),
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


def _paint_road(tiles, theme, x_lo, x_hi, y_lo, y_hi, horizontal):
    """Paint an exact three-cell road corridor with a center lane mark."""
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            if tiles[y][x].kind == "station_deck":
                tiles[y][x] = theme.road_surface
    if horizontal:
        y = (y_lo + y_hi) // 2
        for x in range(x_lo, x_hi + 1):
            if tiles[y][x].kind == "road":
                tiles[y][x] = theme.road_ew
    else:
        x = (x_lo + x_hi) // 2
        for y in range(y_lo, y_hi + 1):
            if tiles[y][x].kind == "road":
                tiles[y][x] = theme.road_ns


def _paint_sidewalk_line(tiles, theme, points):
    for x, y in points:
        if tiles[y][x].kind in {"station_deck", "sidewalk"}:
            tiles[y][x] = theme.sidewalk


def _paint_station_base(tiles, theme) -> None:
    """Paint a compact three-lane collector network and one-cell walks."""
    _paint_hull(tiles)
    _paint_road(tiles, theme, 35, 105, 47, 49, True)
    _paint_road(tiles, theme, 68, 72, 36, 49, False)
    _paint_road(tiles, theme, 19, 21, 25, 49, False)
    _paint_road(tiles, theme, 20, 22, 66, 68, False)
    _paint_road(tiles, theme, 114, 116, 66, 68, False)
    _paint_road(tiles, theme, 20, 116, 66, 68, True)
    for points in (
        [(x, 46) for x in range(35, 106)],
        [(x, 50) for x in range(35, 106)],
        [(67, y) for y in range(36, 50)],
        [(73, y) for y in range(36, 50)],
        [(18, y) for y in range(25, 50)],
        [(22, y) for y in range(66, 69)],
        [(117, y) for y in range(66, 69)],
        [(x, 69) for x in range(20, 117)],
        [(x, 25) for x in range(17, 23)],
        [(x, 66) for x in range(18, 24)],
        [(x, 66) for x in range(113, 119)],
        [(x, 37) for x in range(67, 74)],
        [(x, 38) for x in range(67, 74)],
    ):
        _paint_sidewalk_line(tiles, theme, points)


def _paint_apron_and_hall(tiles, theme) -> None:
    """Paint the docking apron and brightly marked inspection hall."""
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
    """Paint fenced cargo holding yards and the sealed frontier airlock."""
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
    """Place atmospheric cyan, amber, and red station lights."""
    tiles[47][70] = BEACON
    for x in range(25, 121, 12):
        if tiles[47][x].walkable:
            tiles[47][x] = T("neon", "*", (80, 220, 240), (25, 55, 68))
    for x in range(86, 126, 10):
        tiles[60][x] = T("neon", "*", (255, 180, 70), (68, 40, 18))
    for x, y in ((7, 18), (36, 18), (48, 32), (92, 32), (21, 47), (116, 47)):
        tiles[y][x] = WARNING


def _paint_deck(game_map, spec, theme, stamps) -> None:
    """Finish station routes, bays, labels, and lighting state."""
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=WIDTH, height=HEIGHT,
        overwrite_kinds=frozenset({"station_deck", "sidewalk"}),
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
    _paint_station_base(tiles, theme)
    _paint_apron_and_hall(tiles, theme)
    _paint_quarantine_yards(tiles)
    _paint_lights(tiles)
    game_map = world.GameMap(WIDTH, HEIGHT, tiles=tiles, entities=[])
    stamps = stamp_city_assets(game_map, ORIGINS, sidewalk=theme.sidewalk)
    _paint_deck(game_map, spec, theme, stamps)
    showroom_origin = spec.hangar_anchor
    add_showroom_ships(game_map, spec, resolve_ship, origin=showroom_origin)
    add_service_terminals(game_map, spec, dy=5, dxs=(-5, -2, 3), palette=TERMINAL_PALETTE_CLASSIC)
    return game_map


__all__ = ["build_blockade_south_layout"]
