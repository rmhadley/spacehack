"""AC-III — Ring Refinery: a floating refinery platform in a gas giant's ring plane.

Alpha Centauri III is a ringed gas giant, and the refinery deck floats
in the ring plane — the binary's fuel and machine stop. The platform's
identity comes from what's below it: ring particle bands of dust and
ice visible through the open atmosphere on every edge. The deck itself
is an irregular silhouette — not a rectangle — shaped like an
industrial platform with a collector tower at its core, a fuel tank
farm on the south deck, and pipe runs crossing between the tanks and
the refinery. Flickering amber neon warning signs line the concourse,
and the collector tower's core glows with concentrated light.

Layout (100x70), authored as `ac3_ring_refinery`:

  * Everything outside the platform is open atmosphere: horizontal ring
    particle bands (two tones of dust/ice, non-walkable) with sparse
    wisp accents. The platform silhouette — an irregular shape — is
    the walkable deck. No drawn rectangle wall.
  * The Concourse — main east-west avenue across the platform.
  * Landing apron NW — smooth pad, showroom ships, terminals.
  * Spaceport NW of the apron, door south.
  * "The Ring Band" bar east end, door south.
  * Collector tower at the platform's industrial core — a 5x5 block
    with a glowing focus at its center.
  * Fuel tank farm south of the concourse — six storage tanks with
    pipe runs connecting them to the refinery.
  * The concourse plaza carries the refinery beacon mid-deck.
  * Flickering amber/red neon warning signs line the concourse.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import replace

from . import world
from .city_kit import (
    TERMINAL_PALETTE_CLASSIC,
    add_service_terminals,
    add_showroom_ships,
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

# Gas-giant ring-plane palette: deep amber-brown deck over ring dust,
# industrial steel, amber/red warning neon.
AC3_REFINERY = override_theme(
    derive_theme(
        floor=(95, 75, 50),
        grass=(60, 45, 30),
        accent=(255, 180, 70),
        road_surface=T("road", ".", (110, 95, 70), (45, 38, 25)),
        road_ns=T("road", ":", (100, 180, 80), (35, 45, 25)),
        road_ew=T("road", "-", (100, 180, 80), (35, 45, 25)),
        sidewalk=T("sidewalk", "▒", (130, 115, 85), (55, 48, 35)),
        plaza=T("plaza", "░", (180, 150, 90), (80, 65, 38)),
        landing_pad=T("landing_pad", "▓", (200, 170, 100), (75, 60, 42)),
        neon=T("neon", "*", (255, 180, 70), (60, 35, 12)),
    ),
    floor=T("floor", "░", (95, 75, 50), (42, 35, 22)),
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "ac3_spaceport": world.Position(10, 6),
    "ac3_bar":       world.Position(66, 52),
}

# ---------------------------------------------------------------------
# Platform silhouette geometry
# ---------------------------------------------------------------------

# The platform is an irregular rounded shape — not a rectangle.
# Defined by an ellipse with per-sector wobble, like Ross c's crater.
_PLATFORM_CX, _PLATFORM_CY = 50, 38
_PLATFORM_RX, _PLATFORM_RY = 52.0, 34.0
_PLATFORM_WOBBLE = (
    3, -2, 4, -5, -3, 5, -4, -6,
    2, 2, 4, -2, -1, -5, -2, 2,
)

# Concourse: main east-west avenue.
_CONC_Y = (33, 34, 35)
_CONC_X_LO, _CONC_X_HI = 8, 92

# Landing apron NW.
_APRON = (10, 28, 20, 28)

# Concourse plaza with the refinery beacon.
_PLAZA = (44, 56, 33, 35)
_BEACON = (50, 34)

# Collector tower at the industrial core (south of concourse).
_TOWER = (46, 54, 40, 46)
_TOWER_CX, _TOWER_CY = 50, 43
_TOWER_CORE = (50, 43)

# Fuel tank farm south of the concourse (east side).
_TANKS: tuple[tuple[int, int, int, int], ...] = (
    (60, 48, 5, 5), (68, 48, 4, 4), (76, 48, 5, 5),
    (84, 48, 4, 4),
)

# Pipe runs connecting tanks to the refinery core.
_PIPES: tuple[tuple[int, int, str], ...] = (
    (55, 47, "─"), (60, 47, "─"), (65, 47, "─"),
    (70, 47, "─"), (75, 47, "─"), (80, 47, "─"),
    (85, 47, "─"), (90, 47, "─"),
    (62, 44, "│"), (72, 44, "│"), (82, 44, "│"),
)

# Flickering amber/red neon warning signs along the concourse.
_WARNING_SIGNS = tuple(
    (x, 32) for x in range(20, 90, 10)
) + tuple(
    (x, 36) for x in range(25, 85, 10)
)

# Cooling fins on the platform's east edge.
_COOLING_FINS = (
    (93, 28), (93, 32), (93, 36), (93, 40),
)


# ---------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------


def _tile(kind, char, fg, bg, walkable=True, message=None) -> world.Tile:
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


RING_DUST_A = _tile(
    "ring_dust", "░", (180, 150, 100), (50, 40, 25), walkable=False,
    message="Ring particle bands drift past the platform edge - no deck here.",
)
RING_DUST_B = _tile(
    "ring_dust", "·", (200, 170, 110), (55, 42, 28), walkable=False,
    message="Ring particle bands drift past the platform edge - no deck here.",
)
PLATFORM_EDGE = _tile(
    "platform_edge", "▓", (130, 100, 65), (50, 38, 22), walkable=False,
    message="The platform edge drops away into the ring plane.",
)
TANK_WALL = _tile(
    "city_building_wall", "#", (130, 110, 80), (45, 38, 25), walkable=False,
    message="A fuel storage tank blocks your path.",
)
TANK_ROOF = _tile(
    "city_building_wall", "o", (160, 135, 90), (50, 42, 28), walkable=False,
    message="A fuel storage tank blocks your path.",
)
PIPE = _tile(
    "pipe", "─", (100, 85, 60), (35, 30, 20), walkable=False,
    message="A fuel pipe runs across the deck.",
)
TOWER = _tile(
    "collector_tower", "█", (95, 125, 155), (40, 55, 70), walkable=False,
    message="The collector tower concentrates the refinery's output.",
)
TOWER_CORE = _tile(
    "beacon", "!", (255, 200, 80), (58, 42, 18), walkable=False,
    message="The collector's focus glows with concentrated energy.",
)
COOLING_FIN = _tile(
    "cooling_fin", "─", (150, 200, 215), (40, 52, 68), walkable=False,
    message="A cooling fin hangs over the ring plane.",
)
WARNING = _tile(
    "neon", "!", (255, 100, 50), (60, 25, 10), walkable=False,
    message="A flickering neon warning sign reads: FUEL ZONE - NO OPEN FLAME.",
)
BAY = _tile(
    "transit_bay", "=", (255, 180, 70), (82, 62, 44),
    message="A transit boarding bay.",
)
DECK_GAP = _tile(
    "deck_gap", "░", (15, 10, 5), (8, 5, 3), walkable=False,
    message="A maintenance gap in the deck plating - no way across.",
)


# ---------------------------------------------------------------------
# Terrain painters
# ---------------------------------------------------------------------


def _platform_scale(x: int, y: int) -> tuple[float, float]:
    """Wobbled ellipse scales for the cell's compass sector."""
    angle = math.degrees(math.atan2(y - _PLATFORM_CY, x - _PLATFORM_CX))
    sector = int(((angle + 360.0) % 360.0) // 22.5) % 16
    wobble = 1.0 + _PLATFORM_WOBBLE[sector] / 100.0
    return _PLATFORM_RX * wobble, _PLATFORM_RY * wobble


def _platform_value(x: int, y: int) -> float:
    """Normalized ellipse value: <1 on the platform, >=1 off the edge."""
    rx, ry = _platform_scale(x, y)
    dx = (x - _PLATFORM_CX) / rx
    dy = (y - _PLATFORM_CY) / ry
    return dx * dx + dy * dy


def _paint_ring_deck(tiles, theme) -> None:
    """Fill the map with ring particle bands, then paint the platform."""
    # Ring particle bands: two tones, alternating by row, with sparse wisps.
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            tiles[y][x] = RING_DUST_A if y % 2 == 0 else RING_DUST_B
    # Sparse wisp accents.
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if (x * 7 + y * 11) % 97 == 0:
                tiles[y][x] = RING_DUST_B
    # Paint the platform deck — the walkable silhouette.
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if _platform_value(x, y) <= 1.0:
                tiles[y][x] = theme.floor
    # Paint the platform edge — the boundary cells.
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if _platform_value(x, y) <= 1.0:
                if any(
                    _platform_value(x + dx, y + dy) > 1.0
                    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                    if 0 <= x + dx < CITY_WIDTH and 0 <= y + dy < CITY_HEIGHT
                ):
                    tiles[y][x] = PLATFORM_EDGE


def _paint_concourse(tiles, theme) -> None:
    """Paint the 3-wide Concourse with a centre lane marker."""
    surface, lane = theme.road_surface, theme.road_ew
    for x in range(_CONC_X_LO, _CONC_X_HI + 1):
        for y in _CONC_Y:
            if tiles[y][x].kind in ("floor", "sidewalk"):
                tiles[y][x] = lane if y == _CONC_Y[1] else surface


def _paint_apron(tiles, theme) -> None:
    """Reserve the quiet blank landing apron at the NW end."""
    pad = world.Tile(
        kind="landing_pad", char=" ", walkable=True,
        fg=(165, 140, 90), bg=(75, 60, 42),
    )
    x_lo, x_hi, y_lo, y_hi = _APRON
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            if tiles[y][x].kind in ("floor", "platform_edge"):
                tiles[y][x] = pad


def _paint_plaza(tiles, theme) -> None:
    """Paint the concourse plaza with the refinery beacon."""
    x_lo, x_hi, y_lo, y_hi = _PLAZA
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            if tiles[y][x].kind in ("floor", "road", "sidewalk"):
                tiles[y][x] = theme.plaza
    bx, by = _BEACON
    tiles[by][bx] = _tile(
        "beacon", "!", (255, 200, 80), (50, 38, 15), walkable=False,
        message="The refinery beacon guides ships to the fuel docks.",
    )


def _paint_tower(tiles) -> None:
    """Paint the collector tower with its glowing core."""
    x_lo, x_hi, y_lo, y_hi = _TOWER
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            if tiles[y][x].kind in ("floor", "sidewalk", "plaza"):
                tiles[y][x] = TOWER
    cx, cy = _TOWER_CORE
    tiles[cy][cx] = TOWER_CORE


def _paint_tanks(tiles) -> None:
    """Paint the fuel tank farm on the south deck."""
    for x, y, w, h in _TANKS:
        for by in range(y, y + h):
            for bx in range(x, x + w):
                if in_bounds(bx, by, CITY_WIDTH, CITY_HEIGHT) and (
                    tiles[by][bx].kind == "floor"
                ):
                    edge = by in (y, y + h - 1) or bx in (x, x + w - 1)
                    tiles[by][bx] = TANK_WALL if edge else TANK_ROOF


def _paint_pipes(tiles) -> None:
    """Paint fuel pipe runs connecting tanks to the refinery."""
    for x, y, ch in _PIPES:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = replace(PIPE, char=ch)


def _paint_cooling_fins(tiles) -> None:
    """Paint cooling fins on the platform's east edge."""
    for x, y in _COOLING_FINS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind in ("floor", "platform_edge")
        ):
            tiles[y][x] = COOLING_FIN


def _paint_warning_signs(tiles) -> None:
    """Line the concourse with flickering neon warning signs."""
    for x, y in _WARNING_SIGNS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind in ("floor", "road", "sidewalk", "plaza")
        ):
            tiles[y][x] = WARNING


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


def _finish_ac3(spec, resolve_ship, tiles, theme):
    """Stamp assets, paint transit/signs, seed lighting for AC-III."""
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk", "platform_edge"}),
    )
    paint_transit_bays(
        game_map.tiles, spec, BAY, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk", "plaza"}),
    )
    _paint_warning_signs(game_map.tiles)
    _seal_dead_deck(game_map.tiles, spec.hangar_anchor)
    paint_roof_labels(game_map, stamps, "ac3_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="ac3_", default_layout_id="ac3_ring_refinery",
    )
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-5, -2, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


def build_ac3_layout(spec, resolve_ship) -> world.GameMap:
    """Build Ring Refinery's 100x70 floating platform from data + assets."""
    theme = _readable_city_theme(AC3_REFINERY)
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    _paint_ring_deck(tiles, theme)
    _paint_concourse(tiles, theme)
    _paint_apron(tiles, theme)
    _paint_plaza(tiles, theme)
    _paint_tower(tiles)
    _paint_tanks(tiles)
    _paint_pipes(tiles)
    _paint_cooling_fins(tiles)
    return _finish_ac3(spec, resolve_ship, tiles, theme)


__all__ = ["build_ac3_layout", "LANDMARK_ORIGINS", "AC3_REFINERY"]
