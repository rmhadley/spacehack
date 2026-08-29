"""Procyon c — Ice Campus: a research campus carved into the ice sheet.

Procyon c hosts the chain's ice-research campus: four buildings sunk
into a sheltered trench of the ice sheet, a frozen meltwater channel
running past the quad, and — the signature — the mouth of the ice
caves opening at the city's east edge. The caves are the lab chain's
delve site (`explorable_site_name="caves"` on `proc_planet_2`); the
mouth here is the surface landmark that story stands behind.

Layout (140x100), authored as `proc_c_ice_campus`:

  * spaceport NW, door south onto the landing apron.
  * lab NE, door south onto the lab terrace — closest building to
    the cave mouth, as the research it serves is down there.
  * mess hall + supply depot south of the quad, doors north.
  * The Quad — central snow-packed plaza with the campus beacon.
  * A frozen channel (walkable ice) cuts diagonally past the quad;
    one bridge carries the main route across.
  * The CAVE MOUTH opens at the east edge: a dark ring of ice with
    the explore marker standing in it.
  * Sastrugi (wind-carved ridges) texture the open ice elsewhere.
"""

from __future__ import annotations

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
    "proc_c_mess":      world.Position(34, 72),
    "proc_c_depot":     world.Position(92, 72),
}

# ---------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------

# Frozen channel: diagonal spine, 3 wide, with one bridge.
_CHANNEL_FROM = (8, 96)
_CHANNEL_TO = (138, 58)
_BRIDGE = (58, 62, 79, 82)

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
)


# ---------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------


def _tile(kind, char, fg, bg, walkable=True, message=None) -> world.Tile:
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


ICE_CHANNEL = _tile(
    "ice_channel", "~", (170, 215, 250), (96, 140, 190),
    message=None,
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
    message="The ice caves open here - the lab chain's delve site lies below.",
)
SASTRUGI = _tile(
    "sastrugi", "^", (196, 220, 244), (150, 180, 212), walkable=False,
    message="Wind-carved ice ridges block the way.",
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


def _paint_channel(tiles, theme) -> None:
    """Carve the frozen meltwater channel with one bridge crossing."""
    x0, y0 = _CHANNEL_FROM
    x1, y1 = _CHANNEL_TO
    steps = 60
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


# ---------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------


def build_proc_c_layout(spec, resolve_ship) -> world.GameMap:
    """Build the Ice Campus 140x100 glacial research map from data + assets."""
    theme = _readable_city_theme(PROC_C_GLACIAL)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _paint_sastrugi(tiles)
    _paint_channel(tiles, theme)
    _paint_quad(tiles, theme)
    _paint_cave(tiles)
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
        overwrite_kinds=frozenset({"floor", "sidewalk", "plaza"}),
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
