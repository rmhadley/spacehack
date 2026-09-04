"""Blockade North — The Picket: the primary militia garrison on the frontier.

Blockade North is the primary militia checkpoint on the Luyten frontier:
a sealed military station organized around a command deck, an armory, and
a bounty office for frontier claims. Its identity comes from pressure
bulkheads, docking infrastructure, and artificial lighting — teal
operational strips lead through public corridors, amber lights mark the
armory approach, and red warning lights identify restricted doors. A
central beacon orients arrivals from the landing bay.

Layout (100x70), authored as `blockade_north_picket`:

  * Station deck — pressure hull perimeter, no terrain.
  * Landing bay NW — smooth pad, showroom ships, service terminals.
  * The Corridor — main east-west military corridor.
  * Spaceport NW, door south.
  * Militia command SE, door north.
  * Bounty office SW, door north.
  * Pressure bulkheads and bulkhead doors texture the deck.
  * Teal operational lamps, amber armory lights, red warning lights,
    and a central beacon provide atmospheric lighting.
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

# Military garrison variant: dark steel deck, teal operational lighting,
# amber armory accents, and red warning lights.
BLOCKADE_NORTH = override_theme(
    derive_theme(
        floor=(72, 82, 102),
        grass=(42, 50, 68),
        accent=(90, 220, 240),
        road_surface=T("road", ".", (100, 112, 130), (35, 42, 55)),
        road_ns=T("road", ":", (90, 220, 240), (24, 42, 58)),
        road_ew=T("road", "-", (90, 220, 240), (24, 42, 58)),
        sidewalk=T("sidewalk", "▒", (130, 145, 160), (42, 52, 65)),
        plaza=T("plaza", "░", (170, 185, 200), (60, 72, 85)),
        landing_pad=T("landing_pad", "▓", (150, 185, 210), (55, 65, 80)),
        neon=T("neon", "*", (90, 220, 240), (22, 55, 68)),
    ),
    floor=T("floor", ".", (85, 100, 120), (42, 52, 68)),
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "blockade_north_spaceport": world.Position(6, 4),
    "blockade_north_militia":   world.Position(62, 52),
    "blockade_north_bounties":  world.Position(6, 52),
}

# ---------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------

# The Corridor: 3-wide east-west military corridor.
_CORR_Y = (33, 34, 35)
_CORR_X_LO, _CORR_X_HI = 4, 96

# Landing apron NW.
_APRON = (4, 22, 18, 28)

# Command plaza mid-corridor with the station beacon.
_PLAZA = (40, 58, 33, 35)
_BEACON = (49, 34)

# Pressure bulkhead segments (decorative).
_BULKHEADS: tuple[tuple[int, int, int, int], ...] = (
    (30, 24, 1, 8), (30, 38, 1, 8),
    (70, 24, 1, 8), (70, 38, 1, 8),
)

# Teal operational lamps along the corridor.
_TEAL_LAMPS = tuple(
    (x, 32) for x in range(15, 95, 8)
) + tuple(
    (x, 36) for x in range(20, 90, 8)
)

# Amber armory lights near the militia building approach.
_AMBER_LIGHTS = (
    (58, 50), (62, 50), (66, 50), (70, 50), (74, 50),
)

# Red warning lights at restricted zones.
_RED_WARNINGS = (
    (32, 24), (32, 45), (68, 24), (68, 45),
    (10, 50), (88, 50),
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
    "station_hull", "#", (110, 125, 145), (30, 38, 52), walkable=False,
    message="The station pressure hull blocks your path.",
)
BULKHEAD = _tile(
    "station_bulkhead", "#", (130, 145, 160), (35, 42, 55), walkable=False,
    message="A pressure bulkhead blocks your path.",
)
BEACON = _tile(
    "beacon", "!", (255, 225, 120), (50, 42, 35), walkable=False,
    message="The station beacon orients arrivals from the landing bay.",
)
TEAL_LAMP = _tile(
    "neon", "i", (90, 220, 240), (22, 55, 68), walkable=False,
    message="A teal operational lamp casts a cold pool of light on the deck.",
)
AMBER_LIGHT = _tile(
    "neon", "*", (255, 180, 70), (60, 40, 18), walkable=False,
    message="An amber armory light marks the militia approach.",
)
RED_WARNING = _tile(
    "neon", "!", (255, 72, 72), (64, 14, 18), walkable=False,
    message="A red warning light marks a restricted zone.",
)
BAY = _tile(
    "transit_bay", "=", (90, 220, 240), (58, 65, 80),
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


def _paint_corridor(tiles, theme) -> None:
    """Paint the 3-wide military Corridor with a centre lane marker."""
    surface, lane = theme.road_surface, theme.road_ew
    for x in range(_CORR_X_LO, _CORR_X_HI + 1):
        for y in _CORR_Y:
            tiles[y][x] = lane if y == _CORR_Y[1] else surface


def _paint_apron(tiles, theme) -> None:
    """Reserve the quiet blank landing apron at the NW end."""
    pad = world.Tile(
        kind="landing_pad", char=" ", walkable=True,
        fg=(140, 170, 195), bg=(55, 65, 80),
    )
    x_lo, x_hi, y_lo, y_hi = _APRON
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = pad


def _paint_plaza(tiles, theme) -> None:
    """Paint the command plaza with the station beacon."""
    x_lo, x_hi, y_lo, y_hi = _PLAZA
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = theme.plaza
    bx, by = _BEACON
    tiles[by][bx] = BEACON


def _paint_bulkheads(tiles) -> None:
    """Paint pressure bulkhead segments on the deck."""
    for x, y, w, h in _BULKHEADS:
        for by in range(y, y + h):
            for bx in range(x, x + w):
                if in_bounds(bx, by, CITY_WIDTH, CITY_HEIGHT) and (
                    tiles[by][bx].kind in ("floor", "wall")
                ):
                    tiles[by][bx] = BULKHEAD


def _paint_teal_lamps(tiles) -> None:
    """Line the corridor with teal operational lamps."""
    for x, y in _TEAL_LAMPS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = TEAL_LAMP


def _paint_amber_lights(tiles) -> None:
    """Place amber armory lights near the militia approach."""
    for x, y in _AMBER_LIGHTS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = AMBER_LIGHT


def _paint_red_warnings(tiles) -> None:
    """Place red warning lights at restricted zones."""
    for x, y in _RED_WARNINGS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = RED_WARNING


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


def _finish_blockade_north(spec, resolve_ship, tiles, theme):
    """Stamp assets, paint transit, seed lighting for Blockade North."""
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "station_hull"}),
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
    paint_roof_labels(game_map, stamps, "blockade_north_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="blockade_north_", default_layout_id="blockade_north_picket",
    )
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-5, -2, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


def build_blockade_north_layout(spec, resolve_ship) -> world.GameMap:
    """Build The Picket's 100x70 militia garrison from data + assets."""
    theme = _readable_city_theme(BLOCKADE_NORTH)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _paint_hull_perimeter(tiles)
    _paint_corridor(tiles, theme)
    _paint_apron(tiles, theme)
    _paint_plaza(tiles, theme)
    _paint_bulkheads(tiles)
    _paint_teal_lamps(tiles)
    _paint_amber_lights(tiles)
    _paint_red_warnings(tiles)
    return _finish_blockade_north(spec, resolve_ship, tiles, theme)


__all__ = ["build_blockade_north_layout", "LANDMARK_ORIGINS", "BLOCKADE_NORTH"]
