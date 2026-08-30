"""Venus — Cloudbreak City: a packed neon downtown floating in the clouds.

Venus's floating port grew into a dense vertical megacity: a deck hung
in the upper atmosphere, packed tower-blocks in a neon canyon around a
cross of wide avenues. The signature is the city's own density — the
shared skyline filler packs every free block with varied towers, and a
neon-signage pass lines their street-facing facades with hot pink and
cyan signs, so the avenues read as Tokyo-in-2200 canyons.

Layout (140x100), authored as `venus_cloudbreak`:

  * North rim — Landing Deck: the spaceport NW with the smooth apron
    (berth, showroom, terminals) and the pad crew.
  * The Promenade — the east-west main avenue off the apron spur.
  * The Cross — central plaza where the north-south spine meets the
    Promenade, carrying the city beacon and the transit hub.
  * The Cross Street — a second east-west avenue south of the plaza.
  * The Cloudbreak (bar) on the west deck — hot-pink lounge over the
    cloud rim, on its own spur off the Cross Street.
  * Merchants hall (east district) and the deck stores depot (south),
    each docked onto the network by a lane.
  * Cloud bands rim every edge (irregular silhouette, non-walkable);
    maintenance gaps in the deck plate where floor would be sealed off.
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
from .city_layout import paint_roof_labels, paint_skyline, stamp_city_assets
from .data.planets import _readable_city_theme
from .data.planets.themes import T, derive_theme, override_theme


CITY_WIDTH = 140
CITY_HEIGHT = 100

# Cyberpunk-neon variant: Tokyo-in-2200 night palette.
#
# The default derive_theme pipeline darkens the grass anchor into
# road/sidewalk tones, but with a grass this dark every derived surface
# converges to the same lifted gray after `_readable_city_theme`
# processing — making road, sidewalk, and terrain indistinguishable.
# Hand-tuned overrides keep each surface visually distinct AND on-hue:
# backgrounds are pre-lifted above the readability luma floor so the
# indigo/purple cast survives processing instead of flattening to gray.
#   floor      = deep indigo deck plate with brighter blue specks
#   road       = purple-gray wet asphalt
#   road_ns/ew = electric cyan lane markers on deep blue
#   sidewalk   = light violet-tinted concrete curbs
#   plaza      = mauve stone washed in pink neon glow
#   neon       = hot pink signs (alternated with cyan in the signage pass)
VENUS_NEON = override_theme(
    derive_theme(
        floor=(55, 68, 105),
        grass=(55, 45, 85),
        accent=(255, 45, 150),
        road_surface=T("road", ".", (105, 112, 135), (62, 58, 76)),
        road_ns=T("road", ":", (0, 229, 255), (30, 42, 66)),
        road_ew=T("road", "-", (0, 229, 255), (30, 42, 66)),
        sidewalk=T("sidewalk", "▒", (155, 160, 185), (74, 78, 95)),
        plaza=T("plaza", "░", (200, 165, 210), (80, 62, 96)),
        landing_pad=T("landing_pad", "▓", (130, 185, 225), (55, 78, 105)),
        neon=T("neon", "*", (255, 45, 150), (58, 22, 48)),
    ),
    # Pinned directly so the readability lift keeps the indigo hue
    # instead of flattening the deck to neutral gray.
    floor=T("floor", ".", (85, 100, 140), (50, 62, 95)),
)

# Fixed asset origins (match the spec footprints).
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "venus_spaceport": world.Position(6, 6),
    "venus_bar":       world.Position(16, 70),
    "venus_merchants": world.Position(96, 70),
    "venus_depot":     world.Position(92, 84),
}

# ---------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------

# Planned circulation — a cross of avenues plus docked lanes.
_PROMENADE_Y = (32, 33, 34)          # the main east-west avenue
_PROMENADE_X = (30, 128)
_APRON_SPUR = (29, 31, 26, 34)       # apron -> Promenade (NS)
_SPINE = (80, 82, 34, 66)            # Promenade -> Cross Street (NS)
_CROSS_STREET_Y = (64, 65, 66)       # second avenue, south of the plaza
_CROSS_STREET_X = (30, 128)
_BAR_SPUR = (27, 29, 64, 68)         # Cross Street -> Cloudbreak curb (stops before forecourt)
_MERCHANTS_SPUR = (106, 108, 64, 68) # Cross Street -> exchange curb (stops before forecourt)
_DEPOT_SPUR = (89, 91, 66, 82)       # Cross Street -> depot service road
_DEPOT_WALKWAY_X = (89, 104)         # sidewalk walkway along the depot wall
_DEPOT_WALKWAY_Y = 83

# Landing apron south of the spaceport (drawn pad surface).
_APRON = (4, 30, 18, 26)

# The Cross — the central plaza at the avenue crossing.
_CROSS = (74, 88, 36, 46)
_BEACON = (83, 41)
_LAMP_SPOTS = ((75, 37), (87, 37), (75, 45), (87, 45))

# Single-cell gaps between perpendicular lane markers, bridged so the
# center line visibly turns (the Cross Street marker starts at x=30
# while the Cloudbreak spur marker sits at x=28).
_MARKER_BRIDGES = ((29, 65),)

# Skyline tuning: dense towers, every free block packed.
_SKYLINE_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((110, 160, 255), (16, 28, 52), (150, 195, 255), (24, 40, 70)),  # electric blue
    ((80, 230, 255), (12, 40, 50), (130, 240, 255), (18, 52, 62)),   # neon cyan
    ((255, 80, 180), (46, 12, 36), (255, 130, 200), (56, 18, 44)),   # hot pink
    ((175, 120, 255), (32, 20, 56), (205, 165, 255), (40, 26, 66)),  # violet
    ((255, 185, 85), (50, 34, 12), (255, 215, 130), (60, 42, 18)),   # amber gold
    ((185, 195, 215), (38, 42, 52), (215, 225, 240), (48, 53, 64)),  # steel silver
)


# ---------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------


def _tile(kind, char, fg, bg, walkable=True, message=None) -> world.Tile:
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


CLOUD_A = _tile(
    "cloud_deck", "░", (140, 70, 200), (38, 16, 62), walkable=False,
    message="The cloud deck below the city is not solid ground.",
)
CLOUD_B = _tile(
    "cloud_deck", "·", (180, 100, 230), (46, 20, 72), walkable=False,
    message="The cloud deck below the city is not solid ground.",
)
DECK_GAP = _tile(
    "deck_gap", "░", (15, 10, 30), (8, 5, 16), walkable=False,
    message="A maintenance gap in the deck plating - no way across.",
)
BEACON = _tile(
    "beacon", "!", (255, 225, 120), (44, 30, 60), walkable=False,
    message="The Cross beacon guides crews in from the landing deck.",
)
BAY = _tile(
    "transit_bay", "=", (0, 229, 255), (30, 68, 92),
    message="A transit boarding bay.",
)
# Second sign colour for the signage pass: electric cyan alternates
# with the theme's hot pink so facades read as mixed Tokyo neon.
NEON_CYAN = _tile("neon", "*", (0, 229, 255), (32, 66, 88))
# Junction marker where an EW lane line crosses an NS lane line.
# kind stays "road" so the crossing counts as part of the network.
ROAD_CROSS = _tile("road", "+", (0, 229, 255), (30, 42, 66))


# ---------------------------------------------------------------------
# Terrain painters
# ---------------------------------------------------------------------


def _paint_cloud_rim(tiles) -> None:
    """Irregular cloud bands on every deck edge (the city's silhouette)."""
    from .engine import seeded_rng

    rng = seeded_rng(13, "venus_cloud_rim")
    north, west, east, south = [], [], [], []
    for x in range(2, CITY_WIDTH - 2):
        for y in range(1, 1 + 1 + int(rng.random() * 3)):
            north.append((x, y))
    for y in range(6, CITY_HEIGHT - 6):
        for x in range(1, 1 + 1 + int(rng.random() * 2)):
            west.append((x, y))
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(CITY_WIDTH - 1 - (1 + int(rng.random() * 2)), CITY_WIDTH - 1):
            east.append((x, y))
    for x in range(30, CITY_WIDTH - 2):
        for y in range(CITY_HEIGHT - 1 - (1 + int(rng.random() * 2)), CITY_HEIGHT - 1):
            south.append((x, y))
    for band in (north, west, east, south):
        for x, y in band:
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
                tiles[y][x].kind == "floor"
            ):
                tiles[y][x] = CLOUD_A if (x + y) % 3 else CLOUD_B


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


def _paint_cross(tiles, theme) -> None:
    """Paint The Cross plaza with the beacon and corner lamps."""
    x_lo, x_hi, y_lo, y_hi = _CROSS
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = theme.plaza
    bx, by = _BEACON
    tiles[by][bx] = BEACON
    for x, y in _LAMP_SPOTS:
        tiles[y][x] = theme.neon


def _paint_asphalt(tiles, theme, bands) -> None:
    """Lay bare asphalt for every road band (no lane markers yet)."""
    for x_lo, x_hi, y_lo, y_hi, _orientation in bands:
        for y in range(y_lo, y_hi + 1):
            for x in range(x_lo, x_hi + 1):
                tiles[y][x] = theme.road_surface


def _paint_lane_markers(tiles, theme, bands) -> None:
    """Draw continuous lane markers so dashes turn through junctions.

    NS markers first, then EW markers — so dashes run through
    junctions instead of breaking where bands overlap. Cells where an
    EW marker crosses an NS marker get a '+' crossing tile, and
    single-cell gaps between perpendicular markers are bridged so the
    center line visibly turns at every corner.
    """
    # North-south markers, full length.
    for x_lo, x_hi, y_lo, y_hi, orientation in bands:
        if orientation != "ns":
            continue
        mid_x = (x_lo + x_hi) // 2
        for y in range(y_lo, y_hi + 1):
            tiles[y][mid_x] = theme.road_ns
    # East-west markers, turning through north-south markers at
    # junctions.
    for x_lo, x_hi, y_lo, y_hi, orientation in bands:
        if orientation != "ew":
            continue
        mid_y = (y_lo + y_hi) // 2
        for x in range(x_lo, x_hi + 1):
            tiles[mid_y][x] = (
                ROAD_CROSS
                if tiles[mid_y][x].kind == "road_ns"
                else theme.road_ew
            )
    # Bridge single-cell gaps so perpendicular dashes connect.
    for x, y in _MARKER_BRIDGES:
        tiles[y][x] = theme.road_ew


def _paint_road_network(tiles, theme) -> None:
    """Paint the planned circulation: the avenue cross and docked lanes."""
    bands = (
        (_PROMENADE_X[0], _PROMENADE_X[1], _PROMENADE_Y[0], _PROMENADE_Y[2], "ew"),
        (_APRON_SPUR[0], _APRON_SPUR[1], _APRON_SPUR[2], _APRON_SPUR[3], "ns"),
        (_SPINE[0], _SPINE[1], _SPINE[2], _SPINE[3], "ns"),
        (_CROSS_STREET_X[0], _CROSS_STREET_X[1], _CROSS_STREET_Y[0], _CROSS_STREET_Y[2], "ew"),
        (_BAR_SPUR[0], _BAR_SPUR[1], _BAR_SPUR[2], _BAR_SPUR[3], "ns"),
        (_MERCHANTS_SPUR[0], _MERCHANTS_SPUR[1], _MERCHANTS_SPUR[2], _MERCHANTS_SPUR[3], "ns"),
        (_DEPOT_SPUR[0], _DEPOT_SPUR[1], _DEPOT_SPUR[2], _DEPOT_SPUR[3], "ns"),
    )
    _paint_asphalt(tiles, theme, bands)
    _paint_lane_markers(tiles, theme, bands)


def _paint_depot_walkway(tiles, theme) -> None:
    """Sidewalk walkway from the depot spur to the depot door forecourt."""
    x_lo, x_hi = _DEPOT_WALKWAY_X
    y = _DEPOT_WALKWAY_Y
    for x in range(x_lo, x_hi + 1):
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and tiles[y][x].kind == "floor":
            tiles[y][x] = theme.sidewalk


def _paint_neon_signage(game_map, theme) -> None:
    """Line each tower's street-facing facade with neon wall signs.

    Wide towers get a third centred sign, tall towers a rooftop sign,
    and colours alternate hot pink / electric cyan for variety.
    """
    for x, y, w, h in game_map.skyline_placements:
        if h < 2:
            continue
        facade_y = y + h - 1        # the block's south (street-facing) wall
        cols = [x + 2, x + w - 3]
        if w >= 8:
            cols.insert(1, x + (w - 1) // 2)
        for sx in cols:
            if sx >= x + w or sx <= x:
                continue
            game_map.tiles[facade_y][sx] = (
                theme.neon if (x + sx) % 2 else NEON_CYAN
            )
        if h >= 5:
            game_map.tiles[y][x + (w - 1) // 2] = (
                NEON_CYAN if (x + y) % 2 else theme.neon
            )


def _seal_dead_deck(tiles, anchor) -> None:
    """Turn walkable cells cut off from the hangar into deck gaps.

    Tower blocks and the cloud rim can leave sealed pockets of floor
    that look walkable but cannot be reached from the hangar. Sealing
    them as maintenance gaps keeps every walkable cell on a logical
    route while reading as un-plated deck, not terrain.
    """
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


def _paint_basemap(tiles, theme) -> None:
    """Paint the deck: cloud rim, apron, Cross plaza, and avenues."""
    _paint_cloud_rim(tiles)
    _paint_apron(tiles, theme)
    _paint_cross(tiles, theme)
    _paint_road_network(tiles, theme)
    _paint_depot_walkway(tiles, theme)


def _paint_bays(game_map, spec) -> None:
    """Carve curb-side transit bays without ever touching road asphalt."""
    paint_transit_bays(
        game_map.tiles, spec, BAY, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk", "plaza", "landing_pad"}),
        force_center=True,
    )


def _finalize_deck(game_map, spec, theme, stamps) -> None:
    """Dock doors, transit bays, skyline, neon signage, and seal gaps."""
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk"}),
    )
    _paint_bays(game_map, spec)
    paint_roof_labels(game_map, stamps, "venus_")
    paint_skyline(
        game_map,
        seed_key=("venus", "skyline"),
        schemes=_SKYLINE_SCHEMES,
        site_kinds=frozenset({"floor"}),
        # Towers keep a lane from the apron AND from every other tower,
        # so the floor between blocks stays one connected service web
        # instead of sealed pockets.
        avoid_kinds=frozenset({"landing_pad", "transit_bay", "city_building_wall"}),
        width_range=(5, 9),
        height_range=(4, 7),
        min_size=(5, 4),
    )
    _paint_neon_signage(game_map, theme)
    _seal_dead_deck(game_map.tiles, spec.hangar_anchor)
    set_city_metadata(
        game_map, spec, stamps,
        prefix="venus_", default_layout_id="venus_cloudbreak",
    )


def build_venus_layout(spec, resolve_ship) -> world.GameMap:
    """Build Cloudbreak City's 140x100 neon downtown from data + assets."""
    theme = _readable_city_theme(VENUS_NEON)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _paint_basemap(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    _finalize_deck(game_map, spec, theme, stamps)
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-5, -2, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


__all__ = ["build_venus_layout", "VENUS_NEON"]