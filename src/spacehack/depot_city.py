"""Depot — Waypoint 7: a deep-space refueling nexus and truck stop.

Every long-hauler between Epsilon Eridani and Tau Ceti stops at Waypoint
7 — the refueling depot that sits at the midpoint of the deep-space run.
It's a utilitarian industrial deck: a landing bay, a fuel depot, a
mechanic's yard, and cargo stacks. The deck's identity comes from the
amber sodium-vapor work lights that line the freight corridors, the fuel
pipe runs that crisscross the deck, and the cargo container stacks that
give the place its stacked, industrial texture.

Layout (100x70), authored as `depot_waypoint7`:

  * Station deck — pressure hull perimeter, no terrain.
  * Landing bay NW — smooth pad, showroom ships, service terminals.
  * The Freightway — main east-west corridor.
  * Spaceport NW, door south.
  * Depot east end, door north onto the freight plaza.
  * Cargo container stacks texture the south deck.
  * Fuel pipe runs crisscross the freight corridors.
  * Amber sodium-vapor work lights line the Freightway.
"""
from __future__ import annotations

from collections import deque
from dataclasses import replace

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
from .lighting import collect_light_sources, propagate_light


CITY_WIDTH = 100
CITY_HEIGHT = 70

# Industrial truck-stop variant: warm steel deck, amber sodium-vapor
# work lights, worn-metal walls, and amber accents.
DEPOT_WAYPOINT = override_theme(
    derive_theme(
        floor=(100, 95, 80),
        grass=(70, 65, 52),
        accent=(255, 190, 80),
        road_surface=T("road", ".", (120, 110, 90), (45, 40, 30)),
        road_ns=T("road", ":", (255, 190, 80), (35, 30, 20)),
        road_ew=T("road", "-", (255, 190, 80), (35, 30, 20)),
        sidewalk=T("sidewalk", "▒", (135, 125, 100), (55, 48, 38)),
        plaza=T("plaza", "░", (180, 165, 130), (75, 65, 48)),
        landing_pad=T("landing_pad", "▓", (190, 175, 130), (72, 60, 42)),
        neon=T("neon", "*", (255, 190, 80), (55, 38, 12)),
    ),
    floor=T("floor", ".", (110, 100, 82), (48, 42, 32)),
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "depot_spaceport": world.Position(6, 4),
    "depot_depot":      world.Position(66, 52),
}

# ---------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------

# The Freightway: 3-wide east-west corridor.
_FREIGHT_Y = (33, 34, 35)
_FREIGHT_X_LO, _FREIGHT_X_HI = 4, 96

# Landing apron NW.
_APRON = (4, 22, 18, 28)

# Freight plaza mid-Freightway with the depot beacon.
_PLAZA = (45, 55, 33, 35)
_BEACON = (50, 34)

# Cargo container stacks (decorative) south of the Freightway.
_CONTAINERS: tuple[tuple[int, int, int, int], ...] = (
    (15, 45, 5, 4), (25, 45, 4, 3), (35, 45, 5, 4),
    (55, 45, 4, 3), (65, 45, 5, 4), (75, 45, 4, 3),
    (85, 45, 5, 4),
)

# Fuel pipe runs crossing the deck.
_PIPES: tuple[tuple[int, int, str], ...] = (
    (10, 40, "─"), (20, 40, "─"), (30, 40, "─"),
    (40, 40, "─"), (50, 40, "─"), (60, 40, "─"),
    (70, 40, "─"), (80, 40, "─"), (90, 40, "─"),
    (10, 42, "─"), (20, 42, "─"), (30, 42, "─"),
    (40, 42, "─"), (50, 42, "─"), (60, 42, "─"),
    (70, 42, "─"), (80, 42, "─"), (90, 42, "─"),
)

# Amber sodium-vapor work lights along the Freightway.
_WORK_LIGHTS = tuple(
    (x, 32) for x in range(15, 95, 10)
) + tuple(
    (x, 36) for x in range(20, 90, 10)
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
    "station_hull", "#", (120, 110, 90), (35, 30, 22), walkable=False,
    message="The station pressure hull blocks your path.",
)
CONTAINER_WALL = _tile(
    "city_building_wall", "#", (130, 115, 85), (45, 38, 25), walkable=False,
    message="A cargo container stack blocks your path.",
)
CONTAINER_ROOF = _tile(
    "city_building_wall", "=", (155, 135, 95), (50, 42, 28), walkable=False,
    message="A cargo container stack blocks your path.",
)
PIPE = _tile(
    "pipe", "─", (100, 90, 70), (35, 30, 22), walkable=False,
    message="A fuel pipe runs across the deck.",
)
BEACON = _tile(
    "beacon", "!", (255, 190, 80), (50, 38, 12), walkable=False,
    message="The depot beacon marks the fuel dock for inbound haulers.",
)
WORK_LIGHT = _tile(
    "neon", "i", (255, 190, 80), (55, 38, 12), walkable=False,
    message="A sodium-vapor work light casts an amber pool on the deck.",
)
BAY = _tile(
    "transit_bay", "=", (255, 190, 80), (76, 60, 42),
    message="A transit boarding bay.",
)
DECK_GAP = _tile(
    "deck_gap", "░", (12, 10, 8), (6, 5, 4), walkable=False,
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


def _paint_freightway(tiles, theme) -> None:
    """Paint the 3-wide Freightway with a centre lane marker."""
    surface, lane = theme.road_surface, theme.road_ew
    for x in range(_FREIGHT_X_LO, _FREIGHT_X_HI + 1):
        for y in _FREIGHT_Y:
            tiles[y][x] = lane if y == _FREIGHT_Y[1] else surface


def _paint_apron(tiles, theme) -> None:
    """Reserve the quiet blank landing apron at the NW end."""
    pad = world.Tile(
        kind="landing_pad", char=" ", walkable=True,
        fg=(160, 145, 115), bg=(72, 60, 42),
    )
    x_lo, x_hi, y_lo, y_hi = _APRON
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = pad


def _paint_plaza(tiles, theme) -> None:
    """Paint the freight plaza with the depot beacon."""
    x_lo, x_hi, y_lo, y_hi = _PLAZA
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = theme.plaza
    bx, by = _BEACON
    tiles[by][bx] = BEACON


def _paint_containers(tiles) -> None:
    """Paint cargo container stacks south of the Freightway."""
    for x, y, w, h in _CONTAINERS:
        if not all(
            0 <= by < CITY_HEIGHT and 0 <= bx < CITY_WIDTH
            and tiles[by][bx].kind == "floor"
            for by in range(y, y + h) for bx in range(x, x + w)
        ):
            continue
        for by in range(y, y + h):
            for bx in range(x, x + w):
                edge = by in (y, y + h - 1) or bx in (x, x + w - 1)
                tiles[by][bx] = CONTAINER_WALL if edge else CONTAINER_ROOF


def _paint_pipes(tiles) -> None:
    """Paint fuel pipe runs across the deck."""
    for x, y, ch in _PIPES:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = replace(PIPE, char=ch)


def _paint_work_lights(tiles) -> None:
    """Line the Freightway with amber sodium-vapor work lights."""
    for x, y in _WORK_LIGHTS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = WORK_LIGHT


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


def _finish_depot(spec, resolve_ship, tiles, theme):
    """Stamp assets, paint transit, seed lighting for Depot."""
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
    paint_roof_labels(game_map, stamps, "depot_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="depot_", default_layout_id="depot_waypoint7",
    )
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-5, -2, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    sources = collect_light_sources(game_map)
    game_map.light_sources = sources
    game_map.light_grid = propagate_light(
        CITY_WIDTH, CITY_HEIGHT, sources,
        occluder=lambda x, y: not game_map.tiles[y][x].walkable,
    )
    return game_map


def build_depot_layout(spec, resolve_ship) -> world.GameMap:
    """Build Waypoint 7's 100x70 truck stop from data + assets."""
    theme = _readable_city_theme(DEPOT_WAYPOINT)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _paint_hull_perimeter(tiles)
    _paint_freightway(tiles, theme)
    _paint_apron(tiles, theme)
    _paint_plaza(tiles, theme)
    _paint_containers(tiles)
    _paint_pipes(tiles)
    _paint_work_lights(tiles)
    return _finish_depot(spec, resolve_ship, tiles, theme)


__all__ = ["build_depot_layout", "LANDMARK_ORIGINS", "DEPOT_WAYPOINT"]
