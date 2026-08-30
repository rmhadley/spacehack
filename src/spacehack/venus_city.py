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
from .data.planets.themes import derive_theme


CITY_WIDTH = 140
CITY_HEIGHT = 100

# Night-neon variant: deep blue-black deck, hot pink signage.
VENUS_NEON = derive_theme(
    floor=(26, 34, 50),
    grass=(18, 24, 36),
    accent=(255, 110, 200),
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
_BAR_SPUR = (27, 29, 64, 69)         # Cross Street -> Cloudbreak forecourt
_MERCHANTS_SPUR = (106, 108, 64, 69) # Cross Street -> exchange forecourt
_DEPOT_SPUR = (89, 91, 66, 83)       # Cross Street -> depot lane (west of exchange)
_DEPOT_LANE = (89, 104, 83, 83)      # EW back alley docking the depot forecourt

# Landing apron south of the spaceport (drawn pad surface).
_APRON = (4, 30, 18, 26)

# The Cross — the central plaza at the avenue crossing.
_CROSS = (74, 88, 36, 46)
_BEACON = (83, 41)
_LAMP_SPOTS = ((75, 37), (87, 37), (75, 45), (87, 45))

# Skyline tuning: dense towers, every free block packed.
_SKYLINE_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((96, 130, 185), (26, 38, 58), (120, 170, 215), (34, 48, 70)),   # steel blue
    ((70, 170, 200), (22, 40, 52), (100, 205, 230), (30, 50, 64)),   # neon cyan
    ((190, 90, 160), (46, 22, 42), (220, 130, 190), (56, 28, 52)),   # hot pink
    ((120, 110, 190), (32, 28, 52), (150, 140, 215), (40, 36, 62)),  # violet
    ((70, 150, 120), (22, 44, 36), (95, 185, 150), (30, 54, 44)),    # deck green
    ((150, 150, 165), (40, 40, 48), (175, 175, 190), (48, 48, 56)),  # slate
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
    "cloud_deck", "░", (60, 78, 108), (34, 44, 66), walkable=False,
    message="The cloud deck below the city is not solid ground.",
)
CLOUD_B = _tile(
    "cloud_deck", "·", (88, 110, 145), (34, 44, 66), walkable=False,
    message="The cloud deck below the city is not solid ground.",
)
DECK_GAP = _tile(
    "deck_gap", "░", (14, 18, 28), (8, 10, 16), walkable=False,
    message="A maintenance gap in the deck plating - no way across.",
)
BEACON = _tile(
    "beacon", "!", (255, 215, 100), (44, 30, 56), walkable=False,
    message="The Cross beacon guides crews in from the landing deck.",
)
BAY = _tile(
    "transit_bay", "=", (140, 240, 255), (42, 74, 88),
    message="A transit boarding bay.",
)


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


def _paint_road_band(tiles, theme, x_lo, x_hi, y_lo, y_hi, orientation) -> None:
    """Paint a road band from its bounding box (lane marker centered)."""
    mid_y = (y_lo + y_hi) // 2
    mid_x = (x_lo + x_hi) // 2
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            if orientation == "ns" and x == mid_x:
                tiles[y][x] = theme.road_ns
            elif orientation == "ew" and y == mid_y:
                tiles[y][x] = theme.road_ew
            else:
                tiles[y][x] = theme.road_surface


def _paint_road_network(tiles, theme) -> None:
    """Paint the planned circulation: the avenue cross and docked lanes."""
    _paint_road_band(tiles, theme, _PROMENADE_X[0], _PROMENADE_X[1],
                     _PROMENADE_Y[0], _PROMENADE_Y[2], "ew")
    _paint_road_band(tiles, theme, _APRON_SPUR[0], _APRON_SPUR[1],
                     _APRON_SPUR[2], _APRON_SPUR[3], "ns")
    _paint_road_band(tiles, theme, _SPINE[0], _SPINE[1], _SPINE[2], _SPINE[3], "ns")
    _paint_road_band(tiles, theme, _CROSS_STREET_X[0], _CROSS_STREET_X[1],
                     _CROSS_STREET_Y[0], _CROSS_STREET_Y[2], "ew")
    _paint_road_band(tiles, theme, _BAR_SPUR[0], _BAR_SPUR[1],
                     _BAR_SPUR[2], _BAR_SPUR[3], "ns")
    _paint_road_band(tiles, theme, _MERCHANTS_SPUR[0], _MERCHANTS_SPUR[1],
                     _MERCHANTS_SPUR[2], _MERCHANTS_SPUR[3], "ns")
    _paint_road_band(tiles, theme, _DEPOT_SPUR[0], _DEPOT_SPUR[1],
                     _DEPOT_SPUR[2], _DEPOT_SPUR[3], "ns")
    _paint_road_band(tiles, theme, _DEPOT_LANE[0], _DEPOT_LANE[1],
                     _DEPOT_LANE[2], _DEPOT_LANE[3], "ew")


def _paint_neon_signage(game_map, theme) -> None:
    """Line each tower's street-facing facade with neon wall signs."""
    for x, y, w, h in game_map.skyline_placements:
        if h < 2:
            continue
        facade_y = y + h - 1        # the block's south (street-facing) wall
        for sx in (x + 2, x + w - 3):
            if sx >= x + w or sx <= x:
                continue
            game_map.tiles[facade_y][sx] = theme.neon


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


def _finalize_deck(game_map, spec, theme, stamps) -> None:
    """Dock doors, transit bays, skyline, neon signage, and seal gaps."""
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk"}),
    )
    paint_transit_bays(
        game_map.tiles, spec, BAY, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk", "plaza", "landing_pad"}),
    )
    paint_roof_labels(game_map, stamps, "venus_")
    paint_skyline(
        game_map,
        seed_key=("venus", "skyline"),
        schemes=_SKYLINE_SCHEMES,
        site_kinds=frozenset({"floor"}),
        # Towers keep a lane from the apron AND from every other tower,
        # so the floor between blocks stays one connected service web
        # instead of sealed pockets.
        avoid_kinds=frozenset({"landing_pad", "city_building_wall"}),
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