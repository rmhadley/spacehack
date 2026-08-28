"""Vega b — The Mirror Fields, a floating solar-reflector station."""

from __future__ import annotations

from dataclasses import replace

from . import world
from .city_kit import (
    TERMINAL_PALETTE_CLASSIC,
    add_service_terminals,
    add_showroom_ships,
    in_bounds,
    paint_door_forecourts,
    set_city_metadata,
)
from .city_layout import paint_roof_labels, stamp_city_assets
from .data.planets import _readable_city_theme


CITY_WIDTH = 140
CITY_HEIGHT = 90

LANDMARK_ORIGINS = {
    "vega_b_spaceport": world.Position(10, 18),
    "vega_b_bar": world.Position(94, 18),
    "vega_b_merchants": world.Position(94, 62),
}

_MIRROR_ROWS = (8, 14, 27, 34, 47, 54, 67, 74)
_MIRROR_X_LO, _MIRROR_X_HI = 4, 135
_SPINE_Y = (43, 44, 45)
_COOLING_PLAZA = (67, 44)


def _tile(kind, char, fg, bg, walkable=True, message=None):
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


MIRROR = _tile(
    "solar_mirror", "=", (222, 232, 244), (54, 70, 88),
    walkable=False, message="A locked reflector array catches the station's glare.",
)
MIRROR_FRAME = _tile(
    "mirror_frame", "|", (166, 188, 208), (58, 68, 80),
    walkable=False, message="A reflector support frame blocks the maintenance lane.",
)
SHADE = _tile("shade_canopy", "#", (96, 126, 150), (48, 60, 74), walkable=False)
PYLON = _tile("reflector_pylon", "!", (255, 194, 78), (72, 54, 28), walkable=False)
COOLING = _tile("cooling_works", "*", (110, 238, 248), (30, 76, 88))


def _paint_spine(tiles, theme):
    for y in _SPINE_Y:
        for x in range(3, CITY_WIDTH - 3):
            tiles[y][x] = theme.road_surface if y == _SPINE_Y[1] else theme.sidewalk
    for x in (32, 66, 104):
        for y in range(3, CITY_HEIGHT - 3):
            if tiles[y][x].kind == "floor":
                tiles[y][x] = theme.sidewalk


def _paint_mirror_fields(tiles):
    for row in _MIRROR_ROWS:
        for x in range(_MIRROR_X_LO, _MIRROR_X_HI + 1):
            if tiles[row][x].kind != "floor":
                continue
            tiles[row][x] = MIRROR_FRAME if x % 11 == 0 else MIRROR
        for x in (_MIRROR_X_LO + 4, _MIRROR_X_HI - 4):
            if tiles[row][x].kind == "solar_mirror":
                tiles[row][x] = PYLON


def _paint_cooling_plaza(tiles, theme):
    cx, cy = _COOLING_PLAZA
    for y in range(cy - 5, cy + 6):
        for x in range(cx - 8, cx + 9):
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
                tiles[y][x] = theme.plaza
    for x, y in ((cx, cy), (cx - 4, cy), (cx + 4, cy)):
        tiles[y][x] = COOLING


def _paint_shade_corridors(tiles):
    for x in range(12, 130, 17):
        for y in range(37, 52):
            if tiles[y][x].kind == "floor":
                tiles[y][x] = SHADE


def _paint_landing_apron(tiles, theme):
    apron = replace(theme.landing_pad, char=" ")
    for y in range(23, 40):
        for x in range(4, 31):
            if tiles[y][x].kind == "floor":
                tiles[y][x] = apron


def _paint_edges(tiles, theme):
    for x in range(CITY_WIDTH):
        tiles[0][x] = theme.sidewalk
        tiles[CITY_HEIGHT - 1][x] = theme.sidewalk
    for y in range(CITY_HEIGHT):
        tiles[y][0] = theme.sidewalk
        tiles[y][CITY_WIDTH - 1] = theme.sidewalk


def build_vega_b_layout(spec, resolve_ship):
    """Build Vega b's 140x90 floating Mirror Fields station."""
    theme = _readable_city_theme(spec.theme or world.EARTH_THEME)
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    _paint_edges(tiles, theme)
    _paint_spine(tiles, theme)
    _paint_mirror_fields(tiles)
    _paint_cooling_plaza(tiles, theme)
    _paint_shade_corridors(tiles)
    _paint_landing_apron(tiles, theme)
    game_map = world.GameMap(CITY_WIDTH, CITY_HEIGHT, tiles, [])
    stamps = stamp_city_assets(game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk)
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk"}),
    )
    paint_roof_labels(game_map, stamps, "vega_b_")
    set_city_metadata(game_map, spec, stamps, prefix="vega_b_", default_layout_id="vega_mirror_fields")
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(game_map, spec, dy=3, dxs=(-5, -2, 1), palette=TERMINAL_PALETTE_CLASSIC)
    return game_map


__all__ = ["build_vega_b_layout", "LANDMARK_ORIGINS"]
