"""Procyon b — The Crossroads: a scorched rocky waypoint on the deep lanes.

Procyon is the crossroads of the deep-space chain — gates to Epsilon
Eridani, Tau Ceti, and Vega all in reach — and Procyon b is the
sun-blasted truck stop at its heart. Every pilot between the gates
sets down here for fuel and a drink before pushing on.

Layout (120x80), authored as `proc_b_crossroads`:

  * One main strip (the Crossroads strip) runs east-west through the
    town; the west end opens onto the wide landing apron.
  * The spaceport stands north of the apron, door south onto it.
  * South of the strip, the Crossroads cantina and the fuel depot
    face a small crossroads plaza carrying the nav beacon.
  * A dry arroyo cuts the south-west corner (with one bridge), and
    scorched boulders, scrub, and a few shanty shacks texture the
    hardpan beyond the circulation.
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


CITY_WIDTH = 120
CITY_HEIGHT = 80

# Bleached, sun-scorched variant of the desert palette: pale hardpan,
# wind-scoured rock, amber accents from the white F-type star.
PROC_B_SCORCHED = derive_theme(
    floor=(178, 142, 104),
    grass=(128, 92, 58),
    accent=(255, 196, 110),
)

# Fixed asset origins. Footprints leave every public lane visible and
# each door opens onto its planned deck.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "proc_b_spaceport": world.Position(8, 18),
    "proc_b_bar":       world.Position(60, 46),
    "proc_b_depot":     world.Position(92, 46),
}

# ---------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------

# The main strip: 3-wide east-west road through the town.
_STRIP_Y = (38, 39, 40)
_STRIP_X_LO, _STRIP_X_HI = 4, 116

# Landing apron west of the strip's start.
_APRON = (4, 26, 28, 44)

# Spaceport north of the apron, door south (bottom row of the asset).
_SPACEPORT = (8, 28, 18, 25)
_SPACEPORT_DOOR_X = 18

# Bar and depot south of the strip, doors north (top row of the asset).
_BAR = (60, 78, 46, 53)
_BAR_DOOR_X = 69
_DEPOT = (92, 110, 46, 53)
_DEPOT_DOOR_X = 101

# Crossroads plaza between bar and depot, south of the strip.
_PLAZA = (79, 91, 42, 44)
_BEACON = (85, 43)
_NEON_SPOTS = ((80, 42), (90, 42), (80, 44), (90, 44))

# Dry arroyo across the south-west corner, plus one bridge crossing.
_ARROYO_FROM = (4, 64)
_ARROYO_TO = (34, 79)
_BRIDGE = (18, 20, 70, 70)

# Shanty shacks north of the strip, clear of roads and the apron.
_SHACKS: tuple[tuple[int, int, int, int], ...] = (
    (34, 28, 5, 4), (46, 30, 4, 3), (58, 28, 5, 4),
    (70, 30, 4, 3), (82, 28, 5, 4), (94, 30, 4, 3),
)

# Scattered boulders on the hardpan (kept off circulation).
_BOULDERS: tuple[tuple[int, int], ...] = (
    (30, 20), (52, 18), (78, 20), (104, 22), (116, 28),
    (30, 60), (44, 62), (52, 66), (66, 60), (76, 66),
    (90, 60), (104, 62), (112, 66), (40, 12), (60, 12),
)


# ---------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------


def _tile(kind, char, fg, bg, walkable=True, message=None) -> world.Tile:
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


ARROYO = _tile(
    "arroyo", "░", (128, 104, 76), (52, 42, 30), walkable=False,
    message="A dry arroyo - the wash is too loose to cross.",
)
BOULDER = _tile(
    "boulder", "o", (150, 126, 96), (58, 48, 36), walkable=False,
    message="A sun-blasted boulder blocks your path.",
)
SHACK_WALL = _tile(
    "city_building_wall", "#", (128, 106, 82), (44, 36, 28), walkable=False,
    message="The shack wall blocks your path.",
)
SHACK_ROOF = _tile(
    "city_building_wall", '"', (104, 86, 66), (38, 31, 24), walkable=False,
    message="The corrugated roof blocks your path.",
)
BEACON = _tile(
    "beacon", "!", (255, 215, 100), (44, 38, 22), walkable=False,
    message="The crossroads beacon marks the waypoint for inbound ships.",
)
BAY = _tile(
    "transit_bay", "=", (140, 240, 255), (42, 74, 88),
    message="A transit boarding bay.",
)


# ---------------------------------------------------------------------
# Terrain painters
# ---------------------------------------------------------------------


def _paint_scrub(tiles, theme) -> None:
    """Add sparse scorched scrub to the hardpan."""
    from .engine import seeded_rng

    rng = seeded_rng(7, "proc_b_scrub")
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and rng.random() < 0.05:
                tiles[y][x] = theme.grass_accent


def _paint_strip(tiles, theme) -> None:
    """Paint the 3-wide Crossroads strip with a centre lane marker."""
    surface, lane = theme.road_surface, theme.road_ew
    for x in range(_STRIP_X_LO, _STRIP_X_HI + 1):
        for y in _STRIP_Y:
            tiles[y][x] = lane if y == _STRIP_Y[1] else surface


def _paint_apron(tiles, theme) -> None:
    """Reserve the quiet blank landing apron at the west end."""
    pad = world.Tile(
        kind="landing_pad", char=" ", walkable=True,
        fg=(150, 175, 205), bg=(52, 66, 86),
    )
    x_lo, x_hi, y_lo, y_hi = _APRON
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = pad


def _paint_plaza(tiles, theme) -> None:
    """Paint the crossroads plaza with the nav beacon and neon lamps."""
    x_lo, x_hi, y_lo, y_hi = _PLAZA
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = theme.plaza
    bx, by = _BEACON
    tiles[by][bx] = BEACON
    for x, y in _NEON_SPOTS:
        tiles[y][x] = theme.neon


def _paint_arroyo(tiles) -> None:
    """Carve a dry arroyo across the south-west corner with one bridge."""
    x0, y0 = _ARROYO_FROM
    x1, y1 = _ARROYO_TO
    for step in range(0, 40):
        t = step / 39.0
        cx = int(round(x0 + (x1 - x0) * t))
        cy = int(round(y0 + (y1 - y0) * t))
        for dx in (-1, 0, 1):
            x, y = cx + dx, cy
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
                if tiles[y][x].kind == "floor":
                    tiles[y][x] = ARROYO
    for y in range(_BRIDGE[2], _BRIDGE[3] + 1):
        for x in range(_BRIDGE[0], _BRIDGE[1] + 1):
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
                tiles[y][x] = CITY_BRIDGE


def _paint_boulders(tiles) -> None:
    """Scatter sun-blasted boulders on the hardpan."""
    for x, y in _BOULDERS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = BOULDER


def _paint_one_shack(tiles, x, y, w, h) -> None:
    if not all(
        0 <= by < CITY_HEIGHT and 0 <= bx < CITY_WIDTH
        and tiles[by][bx].kind == "floor"
        for by in range(y, y + h) for bx in range(x, x + w)
    ):
        return
    for by in range(y, y + h):
        for bx in range(x, x + w):
            edge = by in (y, y + h - 1) or bx in (x, x + w - 1)
            tiles[by][bx] = SHACK_WALL if edge else SHACK_ROOF


def _paint_shacks(tiles) -> None:
    for x, y, w, h in _SHACKS:
        _paint_one_shack(tiles, x, y, w, h)


# ---------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------


def _paint_terrain(tiles, theme) -> None:
    """Lay down The Crossroads' scrub, strip, plaza, and shack furniture."""
    _paint_scrub(tiles, theme)
    _paint_strip(tiles, theme)
    _paint_apron(tiles, theme)
    _paint_plaza(tiles, theme)
    _paint_arroyo(tiles)
    _paint_boulders(tiles)
    _paint_shacks(tiles)


def build_proc_b_layout(spec, resolve_ship) -> world.GameMap:
    """Build The Crossroads' 120x80 scorched waypoint from data + assets."""
    theme = _readable_city_theme(PROC_B_SCORCHED)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _paint_terrain(tiles, theme)
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
        overwrite_kinds=frozenset({
            "floor", "grass", "grass_accent", "plaza", "city_plaza",
            "sidewalk", "landing_pad",
        }),
        force_center=True,
    )
    paint_roof_labels(game_map, stamps, "proc_b_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="proc_b_", default_layout_id="proc_b_crossroads",
    )
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-5, -2, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


__all__ = ["build_proc_b_layout", "LANDMARK_ORIGINS", "PROC_B_SCORCHED"]