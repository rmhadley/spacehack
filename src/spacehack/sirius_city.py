"""Sirius Station — The Binary Eye: a solar observatory between two stars.

Perched in the gravity well between Sirius A and Sirius B, this station
studies the binary interaction — solar flares, gravitational tides, and
the exotic physics of a white dwarf orbiting a blue-white giant. The
station's signature is the Observation Dome: a great arc of transparent
plating facing the binary, lit gold by Sirius A's light. Solar collector
arrays line the south hull, and the lab's instruments pulse with a warm
golden glow that spills out onto the dark deck at night.

Layout (100x70), authored as `sirius_binary_eye`:

  * Station deck — pressure hull perimeter, no terrain.
  * Landing bay NW — smooth pad, showroom ships, service terminals.
  * The Solar Promenade — main east-west corridor.
  * Spaceport NW, door south.
  * Lab east-central, door north onto the observation terrace.
  * Solar collector arrays (decorative) line the south hull.
  * The Observation Dome — a curved transparent port facing the binary,
    lit gold by the stars.
  * Golden solar lamps and a station beacon provide warm light.
"""
from __future__ import annotations

from collections import deque

from . import world
from .city_kit import (
    TERMINAL_PALETTE_CLASSIC,
    add_service_terminals,
    add_showroom_ships,
    base_tiles,
    in_bounds,
    paint_door_forecourts,
    paint_transit_bays,
    set_city_metadata,
)
from .city_layout import paint_roof_labels, stamp_city_assets
from .data.planets import _readable_city_theme
from .data.planets.themes import T, derive_theme, override_theme


CITY_WIDTH = 100
CITY_HEIGHT = 70

# Solar-observatory variant: deep blue-black hull, golden solar light,
# warm amber accents from the binary's light through the observation dome.
SIRIUS_EYE = override_theme(
    derive_theme(
        floor=(80, 90, 120),
        grass=(50, 60, 85),
        accent=(255, 215, 120),
        road_surface=T("road", ".", (100, 110, 135), (35, 42, 58)),
        road_ns=T("road", ":", (255, 215, 120), (30, 38, 55)),
        road_ew=T("road", "-", (255, 215, 120), (30, 38, 55)),
        sidewalk=T("sidewalk", "▒", (130, 145, 165), (45, 55, 72)),
        plaza=T("plaza", "░", (200, 210, 230), (65, 75, 95)),
        landing_pad=T("landing_pad", "▓", (180, 200, 225), (50, 66, 82)),
        neon=T("neon", "*", (255, 215, 120), (50, 38, 15)),
    ),
    floor=T("floor", ".", (95, 108, 135), (45, 52, 70)),
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "sirius_spaceport": world.Position(6, 4),
    "sirius_lab":        world.Position(60, 28),
}

# ---------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------

# The Solar Promenade: 3-wide east-west corridor.
_PROM_Y = (33, 34, 35)
_PROM_X_LO, _PROM_X_HI = 4, 96

# Landing apron NW.
_APRON = (4, 22, 18, 28)

# Observation terrace (plaza) between the promenade and the lab.
_TERRACE = (47, 82, 22, 27)
_BEACON = (54, 25)

# Solar collector arrays (decorative) on the south hull.
_COLLECTORS: tuple[tuple[int, int, int, int], ...] = (
    (10, 52, 6, 3), (20, 52, 5, 3), (30, 52, 6, 3),
    (40, 52, 5, 3), (50, 52, 6, 3), (60, 52, 5, 3),
    (70, 52, 6, 3), (80, 52, 5, 3), (90, 52, 6, 3),
)

# Golden solar lamps along the promenade.
_LAMPS = tuple(
    (x, 32) for x in range(15, 95, 10)
) + tuple(
    (x, 36) for x in range(20, 90, 10)
)

# Observation dome arc (golden transparent port) on the north hull.
_DOME_ARC = (
    (40, 8), (45, 6), (50, 5), (55, 5), (60, 5), (65, 6), (70, 8),
)


# ---------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------


def _tile(kind, char, fg, bg, walkable=True, message=None) -> world.Tile:
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


HULL = _tile(
    "station_hull", "#", (100, 115, 140), (30, 38, 55), walkable=False,
    message="The station pressure hull blocks your path.",
)
COLLECTOR = _tile(
    "solar_collector", "▲", (255, 215, 120), (50, 38, 15), walkable=False,
    message="A solar collector array faces the binary.",
)
DOME = _tile(
    "observation_dome", "♦", (255, 230, 150), (60, 50, 25), walkable=False,
    message="The observation dome's transparent plating faces the binary.",
)
BEACON = _tile(
    "beacon", "!", (255, 215, 120), (50, 38, 15), walkable=False,
    message="The station beacon orients arrivals to the lab.",
)
LAMP = _tile(
    "neon", "i", (255, 215, 120), (50, 38, 15), walkable=False,
    message="A golden solar lamp casts a warm pool of light on the deck.",
)
BAY = _tile(
    "transit_bay", "=", (255, 215, 120), (72, 60, 42),
    message="A transit boarding bay.",
)
DECK_GAP = _tile(
    "deck_gap", "░", (10, 12, 20), (5, 6, 12), walkable=False,
    message="A maintenance gap in the deck plating - no way across.",
)


# ---------------------------------------------------------------------
# Terrain painters
# ---------------------------------------------------------------------


def _paint_hull_perimeter(tiles) -> None:
    """Paint the station pressure hull perimeter."""
    for y in range(1, CITY_HEIGHT - 1):
        for x in range(1, CITY_WIDTH - 1):
            if tiles[y][x].kind == "wall":
                tiles[y][x] = HULL


def _paint_promenade(tiles, theme) -> None:
    """Paint the 3-wide Solar Promenade with a centre lane marker."""
    surface, lane = theme.road_surface, theme.road_ew
    for x in range(_PROM_X_LO, _PROM_X_HI + 1):
        for y in _PROM_Y:
            tiles[y][x] = lane if y == _PROM_Y[1] else surface


def _paint_apron(tiles, theme) -> None:
    """Reserve the quiet blank landing apron at the NW end."""
    pad = world.Tile(
        kind="landing_pad", char=" ", walkable=True,
        fg=(150, 175, 205), bg=(50, 66, 82),
    )
    x_lo, x_hi, y_lo, y_hi = _APRON
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = pad


def _paint_terrace(tiles, theme) -> None:
    """Paint the observation terrace with the station beacon."""
    x_lo, x_hi, y_lo, y_hi = _TERRACE
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = theme.plaza
    bx, by = _BEACON
    tiles[by][bx] = BEACON


def _paint_collectors(tiles) -> None:
    """Paint solar collector arrays on the south hull."""
    for x, y, w, h in _COLLECTORS:
        for by in range(y, y + h):
            for bx in range(x, x + w):
                if in_bounds(bx, by, CITY_WIDTH, CITY_HEIGHT) and (
                    tiles[by][bx].kind in ("floor", "wall")
                ):
                    tiles[by][bx] = COLLECTOR


def _paint_dome(tiles) -> None:
    """Paint the observation dome arc on the north hull."""
    for x, y in _DOME_ARC:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
            tiles[y][x] = DOME


def _paint_lamps(tiles) -> None:
    """Line the promenade with golden solar lamps."""
    for x, y in _LAMPS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = LAMP


def _seal_dead_deck(tiles, anchor) -> None:
    """Turn walkable cells cut off from the hangar into deck gaps."""
    start = (anchor.x, anchor.y)
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            point = (x + dx, y + dy)
            if point in seen or not in_bounds(point[0], point[1], CITY_WIDTH, CITY_HEIGHT):
                continue
            if tiles[point[1]][point[0]].walkable:
                seen.add(point)
                queue.append(point)
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if tiles[y][x].walkable and (x, y) not in seen:
                tiles[y][x] = DECK_GAP


# ---------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------


def _finish_sirius(spec, resolve_ship, tiles, theme):
    """Stamp assets, paint transit, seed lighting for Sirius Station."""
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "station_hull", "plaza"}),
    )
    paint_transit_bays(
        game_map.tiles, spec, BAY, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({
            "floor", "grass", "grass_accent", "plaza", "city_plaza",
            "sidewalk", "landing_pad",
        }),
        force_center=True,
    )
    _seal_dead_deck(game_map.tiles, spec.hangar_anchor)
    paint_roof_labels(game_map, stamps, "sirius_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="sirius_", default_layout_id="sirius_binary_eye",
    )
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-5, -2, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


def build_sirius_layout(spec, resolve_ship) -> world.GameMap:
    """Build The Binary Eye's 100x70 solar observatory from data + assets."""
    theme = _readable_city_theme(SIRIUS_EYE)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _paint_hull_perimeter(tiles)
    _paint_promenade(tiles, theme)
    _paint_apron(tiles, theme)
    _paint_terrace(tiles, theme)
    _paint_collectors(tiles)
    _paint_dome(tiles)
    _paint_lamps(tiles)
    return _finish_sirius(spec, resolve_ship, tiles, theme)


__all__ = ["build_sirius_layout", "LANDMARK_ORIGINS", "SIRIUS_EYE"]
