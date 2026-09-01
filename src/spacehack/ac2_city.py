"""AC-II — Frostlab: a research campus carved into a glacial ice sheet.

The outer rim of the Alpha Centauri binary is dark and cold — the
perfect vantage for long-baseline stellar interferometry. Frostlab
grew from a single observation dome into a small campus: four buildings
sunk into a sheltered trench of the ice sheet, a frozen meltwater
channel running past the quad, and the mouth of a frozen lake on the
south edge. The lab's cyan-lit interior glow spills out onto the snow
at night, and the meltwater channel shimmers with a faint pulse.

Layout (100x70), authored as `ac2_frostlab`:

  * The walkable ground is a glacial ice sheet. Crevasse bands
    (irregular, non-walkable) rim the map edges instead of a wall.
  * A frozen meltwater channel (deep ice, non-walkable) bisects the
    campus diagonally from NW to SE; one bridge carries the main route.
  * Sastrugi ridges (wind-carved ice, non-walkable) texture the open
    sheet. A core drill rig hums near the lab.
  * The Quad — central snow-packed plaza with the campus beacon.
  * Landing apron NW — smooth pad on packed snow.
  * Spaceport NW, door south.
  * Lab east-central, door north onto the quad terrace.
  * Planned campus road network: a landing strip (EW), an NS spine
    from strip to quad, a bridge crossing the channel, and spurs to
    each door and transit stop.
  * Cyan lab lamps and the campus beacon provide cold light.
"""
from __future__ import annotations

from collections import deque

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
from .city_tiles import CITY_BRIDGE
from .data.planets import _readable_city_theme
from .data.planets.themes import T, derive_theme, override_theme
from .lighting import collect_light_sources, propagate_light


CITY_WIDTH = 100
CITY_HEIGHT = 70

# Glacial variant: pale blue-white ice, deep-ice accents, cyan science
# lamps, and cold lab-lamp glow.
AC2_GLACIAL = override_theme(
    derive_theme(
        floor=(214, 232, 248),
        grass=(236, 246, 255),
        accent=(140, 200, 255),
        road_surface=T("road", ".", (110, 140, 175), (40, 60, 85)),
        road_ns=T("road", ":", (100, 200, 230), (35, 55, 80)),
        road_ew=T("road", "-", (100, 200, 230), (35, 55, 80)),
        sidewalk=T("sidewalk", "▒", (160, 190, 215), (65, 85, 110)),
        plaza=T("plaza", "░", (215, 235, 250), (130, 160, 185)),
        landing_pad=T("landing_pad", "▓", (220, 240, 255), (70, 90, 115)),
        neon=T("neon", "*", (150, 230, 255), (30, 55, 80)),
    ),
    floor=T("floor", "░", (200, 222, 245), (60, 80, 105)),
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "ac2_spaceport": world.Position(6, 4),
    "ac2_lab":       world.Position(60, 28),
}

# ---------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------

# Frozen meltwater channel — a winding non-walkable path NW to SE.
_CHANNEL_FROM = (4, 50)
_CHANNEL_TO = (96, 64)
_BRIDGE = (44, 46, 56, 56)  # x_lo, x_hi, y_lo, y_hi

# Campus quad between the spine and the lab.
_QUAD = (47, 58, 22, 27)
_BEACON = (52, 25)

# Landing apron NW.
_APRON = (4, 22, 18, 28)

# Drill rig near the lab terrace.
_RIG = ((56, 20), (56, 21))

# Sastrugi ridges — scattered wind-carved ice (non-walkable).
_SASTRUGI: tuple[tuple[int, int], ...] = (
    (28, 14), (40, 16), (52, 14), (64, 16), (76, 14), (88, 10),
    (30, 58), (42, 62), (54, 66), (66, 60), (78, 64), (90, 58),
    (10, 30), (12, 40), (88, 30), (92, 40),
    (30, 40), (80, 40), (85, 45),
)

# Cargo crates staged near the lab.
_CRATES = ((58, 22), (59, 22), (58, 23))

# ---------------------------------------------------------------------
# Planned circulation — campus road network (not one strip)
# ---------------------------------------------------------------------

# Landing strip (EW) off the apron's east edge.
_STRIP_Y = (24, 25, 26)
_STRIP_X_LO, _STRIP_X_HI = 22, 96

# NS spine from strip to quad, then bridge crossing.
_SPINE_X = (47, 48, 49)
_SPINE_Y_LO, _SPINE_Y_HI = 26, 56

# Lab spur from strip east to lab door.
_LAB_SPUR = (56, 58, 26, 27)

# South cross road after the bridge.
_SOUTH_EW_Y = (56, 57, 58)
_SOUTH_EW_X_LO, _SOUTH_EW_X_HI = 44, 80

# Route lamps along the planned paths.
_ROUTE_LAMPS = (
    (28, 25), (40, 25), (60, 25), (75, 25), (88, 25),
    (48, 30), (48, 40), (48, 50),
    (55, 57), (65, 57), (75, 57),
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
BEACON = _tile(
    "beacon", "!", (150, 230, 255), (30, 55, 80), walkable=False,
    message="The campus beacon orients arrivals to the lab terrace.",
)
LAMP = _tile(
    "neon", "i", (150, 230, 255), (30, 55, 80), walkable=False,
    message="A cyan lab lamp casts a cold pool of light on the snow.",
)
BAY = _tile(
    "transit_bay", "=", (150, 230, 255), (60, 82, 105),
    message="A transit boarding bay.",
)


# ---------------------------------------------------------------------
# Terrain painters
# ---------------------------------------------------------------------


def _paint_crevasse_perimeter(tiles) -> None:
    """Irregular crevasse bands rim the map edges instead of a wall."""
    from .engine import seeded_rng

    rng = seeded_rng(22, "ac2_crevasse")
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
    for x in range(30, CITY_WIDTH - 2):
        for y in range(CITY_HEIGHT - 1 - (2 + int(rng.random() * 3)), CITY_HEIGHT - 1):
            south.append((x, y))
    for band in (north, west, east, south):
        for x, y in band:
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
                tiles[y][x].kind == "floor"
            ):
                tiles[y][x] = CREVASSE


def _paint_snowdrifts(tiles, theme) -> None:
    """Add sparse snowdrift texture to the ice sheet."""
    from .engine import seeded_rng

    rng = seeded_rng(33, "ac2_snow")
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and rng.random() < 0.06:
                tiles[y][x] = theme.grass_accent


def _paint_channel(tiles) -> None:
    """Carve the frozen meltwater channel border-to-border."""
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


def _paint_bridge(tiles) -> None:
    """Paint the bridge crossing over the channel."""
    for y in range(_BRIDGE[2], _BRIDGE[3] + 1):
        for x in range(_BRIDGE[0], _BRIDGE[1] + 1):
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
                tiles[y][x] = CITY_BRIDGE


def _paint_apron(tiles, theme) -> None:
    """Reserve the quiet blank landing apron at the NW end."""
    pad = world.Tile(
        kind="landing_pad", char=" ", walkable=True,
        fg=(190, 210, 240), bg=(70, 90, 115),
    )
    x_lo, x_hi, y_lo, y_hi = _APRON
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = pad


def _paint_quad(tiles, theme) -> None:
    """Paint the campus quad with the beacon."""
    x_lo, x_hi, y_lo, y_hi = _QUAD
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = theme.plaza
    bx, by = _BEACON
    tiles[by][bx] = BEACON


def _paint_sastrugi(tiles) -> None:
    """Scatter wind-carved ridges on open ice, clear of circulation."""
    for x, y in _SASTRUGI:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = SASTRUGI


def _paint_details(tiles) -> None:
    """Drill rig and cargo crates."""
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


def _paint_road_band(tiles, theme, x_lo, x_hi, y_lo, y_hi, orientation) -> None:
    """Paint a road band with a centered lane marker."""
    mid_y = (y_lo + y_hi) // 2
    mid_x = (x_lo + x_hi) // 2
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            if tiles[y][x].kind not in ("floor", "sidewalk"):
                continue
            if orientation == "ns" and x == mid_x:
                tiles[y][x] = theme.road_ns
            elif orientation == "ew" and y == mid_y:
                tiles[y][x] = theme.road_ew
            else:
                tiles[y][x] = theme.road_surface


def _paint_road_network(tiles, theme) -> None:
    """Paint the planned campus circulation: strip, spine, spurs, bridge."""
    _paint_road_band(tiles, theme, _STRIP_X_LO, _STRIP_X_HI, _STRIP_Y[0], _STRIP_Y[2], "ew")
    _paint_road_band(tiles, theme, _SPINE_X[0], _SPINE_X[2], _SPINE_Y_LO, _SPINE_Y_HI, "ns")
    _paint_road_band(tiles, theme, _LAB_SPUR[0], _LAB_SPUR[1], _LAB_SPUR[2], _LAB_SPUR[3], "ew")
    _paint_road_band(tiles, theme, _SOUTH_EW_X_LO, _SOUTH_EW_X_HI, _SOUTH_EW_Y[0], _SOUTH_EW_Y[2], "ew")


def _paint_lamps(tiles) -> None:
    """Place cyan lab lamps along the campus routes."""
    for x, y in _ROUTE_LAMPS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind in ("floor", "road", "plaza")
        ):
            tiles[y][x] = LAMP


def _seal_dead_ice(tiles, anchor) -> None:
    """Turn walkable cells cut off from the hangar into crevasse."""
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
                tiles[y][x] = CREVASSE


# ---------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------


def _finish_ac2(spec, resolve_ship, tiles, theme):
    """Stamp assets, paint transit/lamps, seed lighting for AC-II."""
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk", "plaza"}),
    )
    paint_transit_bays(
        game_map.tiles, spec, BAY, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({
            "floor", "grass", "grass_accent", "plaza", "city_plaza",
            "sidewalk", "landing_pad",
        }),
        force_center=True,
    )
    _paint_lamps(game_map.tiles)
    _seal_dead_ice(game_map.tiles, spec.hangar_anchor)
    paint_roof_labels(game_map, stamps, "ac2_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="ac2_", default_layout_id="ac2_frostlab",
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


def build_ac2_layout(spec, resolve_ship) -> world.GameMap:
    """Build Frostlab's 100x70 glacial research campus from data + assets."""
    theme = _readable_city_theme(AC2_GLACIAL)
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    _paint_snowdrifts(tiles, theme)
    _paint_crevasse_perimeter(tiles)
    _paint_channel(tiles)
    _paint_quad(tiles, theme)
    _paint_apron(tiles, theme)
    _paint_sastrugi(tiles)
    _paint_details(tiles)
    _paint_road_network(tiles, theme)
    _paint_bridge(tiles)
    return _finish_ac2(spec, resolve_ship, tiles, theme)


__all__ = ["build_ac2_layout", "LANDMARK_ORIGINS", "AC2_GLACIAL"]
