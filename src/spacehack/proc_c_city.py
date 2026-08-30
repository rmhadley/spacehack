"""Procyon c — Ice Campus: a research campus carved into the ice sheet.

Procyon c hosts the chain's ice-research campus: four buildings sunk
into a sheltered trench of the ice sheet, a frozen meltwater channel
running past the quad, and — the signature — the mouth of the ice
caves opening at the city's east edge. The caves are the site behind
the planet's EXPLORE option; the mouth here is its surface landmark.

Layout (140x100), authored as `proc_c_ice_campus`:

  * spaceport NW, door south onto the drawn landing apron.
  * lab NE, door south onto the lab terrace — closest building to
    the cave mouth, as the research it serves is down there.
  * mess hall + supply depot south of the quad, doors north; the
    depot stands on the far bank of the frozen channel.
  * The Quad — central snow-packed plaza with the campus beacon.
  * A frozen channel (deep ice, NOT walkable) bisects the map
    diagonally; one bridge carries the main route across.
  * The CAVE MOUTH opens at the east edge: a dark ring of ice with
    the explore marker standing in it.
  * Crevasses split the map edges (irregular silhouette), sastrugi
    texture the open ice, a drill rig hums by the lab, and cargo
    crates stage by the depot.
"""

from __future__ import annotations

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
from .city_tiles import CITY_BRIDGE
from .data.planets import _readable_city_theme
from .data.planets.themes import derive_theme


CITY_WIDTH = 140
CITY_HEIGHT = 100

# Glacial variant: pale blue-white ice floor, deep-ice accents.
PROC_C_GLACIAL = derive_theme(
    floor=(214, 232, 248),
    grass=(236, 246, 255),
    accent=(140, 200, 255),
)

# Fixed asset origins (match the spec footprints).
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "proc_c_spaceport": world.Position(6, 6),
    "proc_c_lab":       world.Position(98, 10),
    "proc_c_mess":      world.Position(34, 70),
    "proc_c_depot":     world.Position(92, 74),
}

# ---------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------

# Frozen channel: border-to-border diagonal, 3 wide, one bridge.
_CHANNEL_FROM = (0, 98)
_CHANNEL_TO = (139, 55)
_BRIDGE = (58, 62, 79, 82)

# Landing apron south of the spaceport (drawn pad surface).
_APRON = (4, 30, 18, 26)

# Campus quad between the buildings.
_QUAD = (62, 88, 44, 56)
_BEACON = (75, 50)
_LAMP_SPOTS = ((64, 45), (86, 45), (64, 55), (86, 55))

# Cave mouth at the east edge — the signature landmark.
_CAVE_CENTER = (128, 27)
_CAVE_RING = 7          # outer radius of the dark ice ring
_CAVE_MOUTH_R = 3       # walkable dark mouth inside the ring
_CAVE_MARK = (128, 27)  # explore marker cell (center of the mouth)

# Sastrugi: wind-carved ridges scattered on open ice (non-walkable).
_SASTRUGI: tuple[tuple[int, int], ...] = (
    (40, 16), (52, 26), (64, 20), (78, 14), (90, 24), (44, 34),
    (56, 40), (40, 52), (50, 62), (66, 66), (82, 62), (96, 40),
    (108, 34), (120, 44), (112, 58), (124, 52), (36, 44), (30, 60),
    (46, 78), (60, 90), (76, 92), (104, 90), (120, 84), (130, 70),
    (24, 40), (20, 56), (26, 76), (94, 16), (116, 20), (132, 40),
    (104, 46), (112, 50), (100, 54), (20, 30), (16, 40), (24, 50),
    (34, 58), (44, 64), (96, 56), (126, 64), (60, 30), (68, 26),
)

# Drill rig west of the lab terrace (mast cells).
_RIG: tuple[tuple[int, int], ...] = ((90, 21), (90, 22))

# Cargo crates staged by the depot and the bridge approach.
_CRATES: tuple[tuple[int, int], ...] = (
    (116, 74), (117, 74), (116, 75), (88, 76), (89, 76), (58, 76),
)

# Path lamps on the apron-quad-bridge route.
_ROUTE_LAMPS: tuple[tuple[int, int], ...] = ((40, 32), (54, 40), (62, 62))


# ---------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------


def _tile(kind, char, fg, bg, walkable=True, message=None) -> world.Tile:
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


ICE_CHANNEL = _tile(
    "ice_channel", "~", (170, 215, 250), (96, 140, 190), walkable=False,
    message="The frozen channel is deep and slick - cross at the bridge.",
)
CREVASSE = _tile(
    "crevasse", "▼", (40, 60, 90), (10, 18, 30), walkable=False,
    message="A deep crevasse splits the ice - go around.",
)
SASTRUGI = _tile(
    "sastrugi", "^", (196, 220, 244), (150, 180, 212), walkable=False,
    message="Wind-carved ice ridges block the way.",
)
RIG = _tile(
    "drill_rig", "║", (120, 150, 185), (30, 44, 66), walkable=False,
    message="The core drill rig hums as it bites through the ice.",
)
CRATE = _tile(
    "cargo_crate", "▓", (185, 205, 230), (48, 62, 84), walkable=False,
    message="Stacked supply crates wait for pickup.",
)
CAVE_WALL = _tile(
    "cave_ice_wall", "█", (168, 196, 226), (22, 34, 54), walkable=False,
    message="The cave wall is solid ice - the mouth is the way in.",
)
CAVE_MOUTH = _tile(
    "cave_mouth", " ", (120, 160, 205), (14, 22, 38),
    message=None,
)
CAVE_MARK = _tile(
    "cave_marker", "!", (255, 214, 110), (14, 22, 38), walkable=False,
    message="The ice caves open here - a drilled shaft descends into the dark.",
)
BEACON = _tile(
    "beacon", "!", (255, 215, 100), (60, 84, 112), walkable=False,
    message="The campus beacon guides crews in from the landing apron.",
)
BAY = _tile(
    "transit_bay", "=", (140, 240, 255), (42, 74, 88),
    message="A transit boarding bay.",
)


# ---------------------------------------------------------------------
# Terrain painters
# ---------------------------------------------------------------------


def _paint_sastrugi(tiles) -> None:
    """Scatter wind-carved ridges on open ice, clear of circulation."""
    for x, y in _SASTRUGI:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = SASTRUGI


def _paint_channel(tiles) -> None:
    """Carve the frozen channel border-to-border with one bridge."""
    x0, y0 = _CHANNEL_FROM
    x1, y1 = _CHANNEL_TO
    steps = 80
    for step in range(steps + 1):
        t = step / steps
        cx = int(round(x0 + (x1 - x0) * t))
        cy = int(round(y0 + (y1 - y0) * t))
        for dx in (-1, 0, 1):
            x, y = cx + dx, cy
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
                tiles[y][x].kind == "floor"
            ):
                tiles[y][x] = ICE_CHANNEL
    for y in range(_BRIDGE[2], _BRIDGE[3] + 1):
        for x in range(_BRIDGE[0], _BRIDGE[1] + 1):
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
                tiles[y][x] = CITY_BRIDGE


def _paint_apron(tiles, theme) -> None:
    """Draw the landing apron: a smooth visible pad south of the port."""
    pad = replace(theme.landing_pad, char=" ")
    x_lo, x_hi, y_lo, y_hi = _APRON
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
                tiles[y][x].kind == "floor"
            ):
                tiles[y][x] = pad


def _paint_quad(tiles, theme) -> None:
    """Paint the campus quad with the beacon and path lamps."""
    x_lo, x_hi, y_lo, y_hi = _QUAD
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = theme.plaza
    bx, by = _BEACON
    tiles[by][bx] = BEACON
    for x, y in _LAMP_SPOTS:
        tiles[y][x] = theme.neon


def _crevasse_band(tiles, cells) -> None:
    """Stamp crevasses onto every open floor cell in ``cells``."""
    for x, y in cells:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = CREVASSE


def _paint_crevasse(tiles) -> None:
    """Jagged crevasse bands on the map edges + two short inland cracks,
    so the campus reads as a trench carved out of the ice sheet."""
    from .engine import seeded_rng

    rng = seeded_rng(11, "proc_c_crevasse")
    north, west, east, south = [], [], [], []
    for x in range(2, CITY_WIDTH - 2):
        for y in range(2, 2 + 2 + int(rng.random() * 4)):
            north.append((x, y))
    for y in range(8, CITY_HEIGHT - 8):
        for x in range(1, 1 + 1 + int(rng.random() * 3)):
            west.append((x, y))
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(CITY_WIDTH - 1 - (2 + int(rng.random() * 4)), CITY_WIDTH - 1):
            east.append((x, y))
    for x in range(60, CITY_WIDTH - 2):
        for y in range(CITY_HEIGHT - 1 - (2 + int(rng.random() * 3)), CITY_HEIGHT - 1):
            south.append((x, y))
    for band in (north, west, east, south):
        _crevasse_band(tiles, band)
    # Two short inland cracks: obstacles, not barriers.
    cracks = [
        (100 + i, 44 + (i * 2) // 5) for i in range(14)
    ] + [
        (14 + i, 62 - i // 3) for i in range(14)
    ]
    _crevasse_band(tiles, cracks)


def _paint_cave(tiles) -> None:
    """Open the cave mouth at the east edge: dark ring, mouth, marker."""
    cx, cy = _CAVE_CENTER
    for dy in range(-_CAVE_RING, _CAVE_RING + 1):
        for dx in range(-_CAVE_RING, _CAVE_RING + 1):
            x, y = cx + dx, cy + dy
            if not in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
                continue
            d2 = dx * dx + dy * dy
            if tiles[y][x].kind != "floor":
                continue
            if d2 <= _CAVE_MOUTH_R * _CAVE_MOUTH_R:
                tiles[y][x] = CAVE_MOUTH
            elif d2 <= _CAVE_RING * _CAVE_RING:
                # West gap: the approach corridor crews walk in through.
                if dx <= -4 and abs(dy) <= 1:
                    continue
                tiles[y][x] = CAVE_WALL
    mx, my = _CAVE_MARK
    if in_bounds(mx, my, CITY_WIDTH, CITY_HEIGHT):
        tiles[my][mx] = CAVE_MARK


def _paint_details(tiles, theme) -> None:
    """Drill rig, cargo crates, and route lamps."""
    for x, y in _RIG:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = RIG
    for x, y in _CRATES:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = CRATE
    for x, y in _ROUTE_LAMPS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = theme.neon


# ---------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------


def build_proc_c_layout(spec, resolve_ship) -> world.GameMap:
    """Build the Ice Campus 140x100 glacial research map from data + assets."""
    theme = _readable_city_theme(PROC_C_GLACIAL)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _paint_sastrugi(tiles)
    _paint_channel(tiles)
    _paint_quad(tiles, theme)
    _paint_apron(tiles, theme)
    _paint_crevasse(tiles)
    _paint_cave(tiles)
    _paint_details(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk"}),
    )
    paint_transit_bays(
        game_map.tiles, spec, BAY, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk", "plaza", "landing_pad"}),
    )
    paint_roof_labels(game_map, stamps, "proc_c_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="proc_c_", default_layout_id="proc_c_ice_campus",
    )
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-5, -2, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


__all__ = ["build_proc_c_layout", "PROC_C_GLACIAL"]
