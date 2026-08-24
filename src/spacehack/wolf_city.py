"""Wolf 359 b — a pirate-run listening post built into a cold dark rock.

The settlement grew piecemeal: a landing clearing scraped flat, a bar dug
into the rock, cargo containers stacked into a depot, antenna masts on the
ridge, and scrap-lean-to shacks wherever pirates could squeeze them. No
roads, no plan, no questions asked.

Layout (120×80):
  * spaceport on the west side, depot on the east.
  * landing pad scraped flat in the gap between them.
  * showcase ships parked on the apron above the pad, terminals below.
  * bar — The Salty Grave — dug into the southern rock shelf.
  * smuggler's row — a contraband market south of the bar.
  * antenna forest on the northern ridge (non-enterable).
  * cave entrance (delve site) in the south-eastern wall.
  * scattered homestead shacks, barrel fires, and scrap heaps.
"""

from __future__ import annotations

from dataclasses import replace

from . import world
from .city_layout import (
    building_records,
    paint_roof_labels,
    stamp_city_assets,
    stamp_metadata,
)
from .data.planets import _readable_city_theme
from .data.planets.themes import PIRATE_OUTPOST


CITY_WIDTH = 120
CITY_HEIGHT = 80

# ---------------------------------------------------------------------------
# Placement constants
# ---------------------------------------------------------------------------

_SPACEPORT_X_LO, _SPACEPORT_X_HI = 10, 37
_SPACEPORT_Y_LO, _SPACEPORT_Y_HI = 12, 22
_DEPOT_X_LO, _DEPOT_X_HI = 48, 67
_DEPOT_Y_LO, _DEPOT_Y_HI = 14, 22
_BAR_X_LO, _BAR_X_HI = 14, 34
_BAR_Y_LO, _BAR_Y_HI = 50, 59
_ANTENNA_X_LO, _ANTENNA_X_HI = 74, 106
_ANTENNA_Y_LO, _ANTENNA_Y_HI = 4, 22
_CAVE_X_LO, _CAVE_X_HI = 62, 79
_CAVE_Y_LO, _CAVE_Y_HI = 66, 73

# The landing pad — scraped-flat clearing in the gap between spaceport and depot.
_PAD_X_LO, _PAD_X_HI = 34, 47
_PAD_Y_LO, _PAD_Y_HI = 12, 20

# Smuggler's Row — contraband market south of the bar.
_MARKET_X_LO, _MARKET_X_HI = 6, 38
_MARKET_Y_LO, _MARKET_Y_HI = 61, 69

# Scrap-barrel fire colours — dim orange/red salvage lighting.
_SCRAP_FIRE = world.Tile(
    kind="plaza", char="♦", walkable=True,
    fg=(235, 145, 65), bg=(52, 30, 16),
)
_WARNING_LIGHT = world.Tile(
    kind="neon", char="*", walkable=True,
    fg=(230, 100, 60), bg=(28, 12, 8),
)

# ---------- Non-enterable structures ----------

# Antenna masts — two-cell-wide metal towers.
_ANTENNA_MAST = world.Tile(
    kind="city_building_wall", char="▓", walkable=False,
    fg=(140, 152, 170), bg=(46, 52, 62),
    blocked_message="The antenna mast blocks your path.",
)

# Salvaged-metal cabin — dark corrugated walls with a flat roof.
_SHACK_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    # Rusted steel, corrugated iron, scavenged plate.
    ((132, 118, 100), (50, 42, 36), (160, 148, 130), (62, 52, 44)),
    ((108, 114, 122), (42, 44, 50), (140, 146, 154), (50, 52, 58)),
    ((96, 88, 82), (38, 34, 32), (130, 122, 116), (48, 42, 38)),
    ((120, 110, 96), (44, 40, 34), (152, 142, 128), (56, 48, 40)),
)

# Each entry: (x, y, width, height, scheme_index).  Placement skips
# the whole footprint unless every cell is open floor or grass.
_SHACKS: tuple[tuple[int, int, int, int, int], ...] = (
    # West side — near the landing clearing.
    (8, 38, 6, 5, 0), (24, 40, 5, 4, 1), (42, 35, 6, 5, 2),
    (55, 38, 7, 5, 3), (58, 50, 5, 4, 0), (12, 64, 6, 5, 1),
    # East side — around the cave approach.
    (82, 50, 6, 5, 2), (90, 56, 5, 4, 3), (72, 60, 7, 5, 0),
    (96, 38, 6, 5, 1), (102, 44, 5, 4, 2),
    # North-east — near the antenna ridge.
    (70, 24, 6, 5, 3), (86, 30, 5, 4, 0), (100, 28, 6, 5, 1),
    (48, 6, 5, 4, 2), (62, 10, 6, 5, 3),
    # Far east flank.
    (106, 62, 5, 4, 0), (110, 70, 6, 5, 1),
)

# Antenna tower placements: (x, y, height) — vertical 2-wide masts.
_ANTENNAS: tuple[tuple[int, int, int], ...] = (
    (76, 6, 10), (84, 4, 12), (92, 5, 11),
    (100, 6, 10), (106, 7, 9),
    (84, 24, 7), (94, 26, 6),
)

# Scrap heaps and barrel fires — (x, y, is_fire).
_SCRAPS: tuple[tuple[int, int, bool], ...] = (
    (44, 32, True), (47, 48, False), (56, 52, True),
    (68, 42, False), (78, 48, True), (88, 60, False),
    (95, 46, True), (104, 52, False), (14, 44, True),
    (26, 68, False), (40, 62, True), (60, 64, False),
    (84, 68, True), (50, 4, False), (64, 16, True),
    (112, 54, False), (36, 72, True),
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "wolf_spaceport": world.Position(_SPACEPORT_X_LO, _SPACEPORT_Y_LO),
    "wolf_depot": world.Position(_DEPOT_X_LO, _DEPOT_Y_LO),
    "wolf_bar": world.Position(_BAR_X_LO, _BAR_Y_LO),
}


# ---------------------------------------------------------------------------
# Tile helpers
# ---------------------------------------------------------------------------

def _base_tiles(theme):
    """Dark ice-rock floor with perimeter walls."""
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    for x in range(CITY_WIDTH):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(CITY_HEIGHT):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL
    return tiles


def _paint_cell(tiles, x, y, tile):
    """Paint on open ground only — never overwrite walls or buildings."""
    if tiles[y][x].kind in {"floor", "grass"}:
        tiles[y][x] = tile


def _paint_path(tiles, theme, x0, y0, x1, y1):
    """Paint a worn trail (sidewalk) from (x0,y0) to (x1,y1).

    Dithers the line so it reads as an improvised footpath, not a
    paved sidewalk.  The path meanders slightly.
    """
    dx = x1 - x0
    dy = y1 - y0
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        return
    for i in range(steps + 1):
        t = i / steps
        cx = round(x0 + dx * t)
        cy = round(y0 + dy * t)
        # Widen to 2 cells every few steps for a worn look.
        _paint_cell(tiles, cx, cy, theme.sidewalk)
        if i % 4 == 1:
            if abs(dx) > abs(dy):
                _paint_cell(tiles, cx, cy - 1, theme.sidewalk)
            else:
                _paint_cell(tiles, cx - 1, cy, theme.sidewalk)
        if i % 7 == 3:
            if abs(dx) > abs(dy):
                _paint_cell(tiles, cx, cy + 1, theme.sidewalk)
            else:
                _paint_cell(tiles, cx + 1, cy, theme.sidewalk)


def _paint_crater_floor(tiles, theme):
    """Patches of darker crust and scraped-flat ground for variety."""
    import random
    rng = random.Random(42)
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and rng.random() < 0.06:
                tiles[y][x] = theme.grass


# ---------------------------------------------------------------------------
# Painter functions
# ---------------------------------------------------------------------------

def _paint_landing_pad(tiles, theme):
    """Scraped-flat landing pad in the gap between spaceport and depot."""
    # Use a lighter scraped-rock bg so the pad reads clearly against
    # the dark crater floor, but keep char=" " for entity readability.
    pad_tile = replace(theme.landing_pad, char=" ", bg=(70, 78, 90))
    for y in range(_PAD_Y_LO, _PAD_Y_HI + 1):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = pad_tile
    # Two rows of sidewalk north of the pad for the showcase apron.
    for y in range(_PAD_Y_LO - 2, _PAD_Y_LO):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = theme.sidewalk


def _paint_paths(tiles, theme):
    """Worn footpaths linking the landing clearing to the bar/depot/cave."""
    # Landing pad → bar (south).
    _paint_path(tiles, theme, 40, _PAD_Y_HI + 1, 34, 50)
    # Landing pad → depot (east).
    _paint_path(tiles, theme, _PAD_X_HI, _PAD_Y_LO + 4, _DEPOT_X_LO, _DEPOT_Y_LO + 4)
    # Landing pad → spaceport (west).
    _paint_path(tiles, theme, _PAD_X_LO, _PAD_Y_LO + 4, _SPACEPORT_X_HI, _PAD_Y_LO + 4)
    # Depot → antenna ridge (north-east).
    _paint_path(tiles, theme, 56, 23, 72, 16)
    # Bar → cave entrance (south-east).
    _paint_path(tiles, theme, 34, 55, 65, 68)
    # Cave → east flank.
    _paint_path(tiles, theme, 79, 70, 95, 70)
    # Landing → north edge (antenna access).
    _paint_path(tiles, theme, 28, 10, 62, 10)


def _paint_antennas(tiles):
    """Raise non-enterable antenna masts on the northern ridge."""
    for x, y, height in _ANTENNAS:
        for dy in range(height):
            ty = y + dy
            if ty >= CITY_HEIGHT - 1:
                break
            tiles[ty][x] = _ANTENNA_MAST
            if x + 1 < CITY_WIDTH - 1:
                tiles[ty][x + 1] = _ANTENNA_MAST
        # Red warning light on top.
        light_y = y + height
        if light_y < CITY_HEIGHT - 1:
            tiles[light_y][x] = _WARNING_LIGHT


def _paint_cave_entrance(tiles):
    """A dark, jagged mine entrance in the south-eastern rock wall."""
    cave_mouth = world.Tile(
        kind="mine_shaft", char=" ", walkable=False,
        fg=(30, 36, 44), bg=(10, 14, 18),
        blocked_message="The cave entrance drops into the dark. Too dangerous without equipment.",
    )
    cave_wall = world.Tile(
        kind="mine_rock", char="#", walkable=False,
        fg=(80, 90, 105), bg=(32, 36, 44),
        blocked_message="The cave wall blocks your path.",
    )
    for y in range(_CAVE_Y_LO, _CAVE_Y_HI + 1):
        for x in range(_CAVE_X_LO, _CAVE_X_HI + 1):
            if y in (_CAVE_Y_LO, _CAVE_Y_HI) or x in (_CAVE_X_LO, _CAVE_X_HI):
                tiles[y][x] = cave_wall
            else:
                tiles[y][x] = cave_mouth
    # Ore tailings and a warning light outside the cave.
    for ox, oy in ((_CAVE_X_LO - 3, _CAVE_Y_HI - 2), (_CAVE_X_HI + 3, _CAVE_Y_HI - 2)):
        if tiles[oy][ox].kind in {"floor", "grass"}:
            tiles[oy][ox] = _SCRAP_FIRE
    light_x = (_CAVE_X_LO + _CAVE_X_HI) // 2
    light_y = _CAVE_Y_HI + 2
    if light_y < CITY_HEIGHT - 1:
        tiles[light_y][light_x] = _WARNING_LIGHT


def _paint_scraps(tiles):
    """Scatter barrel fires, scrap heaps, and salvage debris."""
    scrap_heap = world.Tile(
        kind="plaza", char="░", walkable=True,
        fg=(100, 112, 128), bg=(38, 42, 50),
    )
    for x, y, is_fire in _SCRAPS:
        if tiles[y][x].kind in {"floor", "grass"}:
            tiles[y][x] = _SCRAP_FIRE if is_fire else scrap_heap
        # Occasionally add a second cell for a bigger heap.
        if not is_fire and x + 1 < CITY_WIDTH - 1 and tiles[y][x + 1].kind in {"floor", "grass"}:
            tiles[y][x + 1] = scrap_heap


def _paint_shed(tiles, x, y, w, h, scheme_index):
    """Paint one salvaged-metal shack only on open ground."""
    if not all(
        tiles[by][bx].kind in {"floor", "grass"}
        for by in range(y, y + h)
        for bx in range(x, x + w)
    ):
        return
    wall_fg, wall_bg, roof_fg, roof_bg = _SHACK_SCHEMES[scheme_index]
    wall = world.Tile(
        kind="city_building_wall", char="#", walkable=False,
        fg=wall_fg, bg=wall_bg,
        blocked_message="The shack wall blocks your path.",
    )
    roof = world.Tile(
        kind="city_building_wall", char="~", walkable=False,
        fg=roof_fg, bg=roof_bg,
        blocked_message="The shack wall blocks your path.",
    )
    for by in range(y, y + h):
        for bx in range(x, x + w):
            if by in (y, y + h - 1) or bx in (x, x + w - 1):
                tiles[by][bx] = wall
            else:
                tiles[by][bx] = roof


def _paint_shacks(tiles):
    """Scatter non-enterable salvaged-metal lean-tos."""
    for x, y, w, h, scheme_index in _SHACKS:
        _paint_shed(tiles, x, y, w, h, scheme_index)


def _paint_market_row(tiles, theme):
    """Smuggler's Row — a contraband market of jury-rigged stalls."""
    # Paved market ground.
    for y in range(_MARKET_Y_LO, _MARKET_Y_HI + 1):
        for x in range(_MARKET_X_LO, _MARKET_X_HI + 1):
            tiles[y][x] = theme.plaza
    # Stalls — two rows of awnings with a walking aisle between.
    # Top row of stalls (y = _MARKET_Y_LO + 1).
    stall_y_north = _MARKET_Y_LO + 1
    for x in range(_MARKET_X_LO + 2, _MARKET_X_HI - 1, 3):
        tiles[stall_y_north][x] = theme.decor
    # Bottom row of stalls (y = _MARKET_Y_HI - 1).
    stall_y_south = _MARKET_Y_HI - 1
    for x in range(_MARKET_X_LO + 2, _MARKET_X_HI - 1, 3):
        tiles[stall_y_south][x] = theme.decor
    # Centre beacon.
    centre_x = (_MARKET_X_LO + _MARKET_X_HI) // 2
    centre_y = (_MARKET_Y_LO + _MARKET_Y_HI) // 2
    tiles[centre_y][centre_x] = theme.neon
    # A barrel fire at the entrance.
    tiles[_MARKET_Y_HI][(_MARKET_X_LO + _MARKET_X_HI) // 2] = _SCRAP_FIRE


def _paint_building_forecourts(tiles, theme, spec):
    """Small cleared forecourt south of each door."""
    for building in spec.buildings:
        y = building.y_hi + 1
        for x in range(building.door_x - 1, building.door_x + 2):
            if 0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT:
                tiles[y][x] = theme.sidewalk


def _paint_transit_bays(tiles, spec):
    """Dedicated transit landing zones on open ground."""
    bay_tile = world.Tile(
        kind="floor", char=" ", walkable=True,
        fg=(155, 165, 180), bg=(62, 68, 78),
    )
    for station in spec.transit_stations:
        tiles[station.pos.y][station.pos.x] = bay_tile


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_wolf_layout(spec, resolve_ship):
    """Build Wolf 359 b's 120×80 crater pirate outpost."""
    theme = _readable_city_theme(PIRATE_OUTPOST)
    tiles = _base_tiles(theme)
    _paint_crater_floor(tiles, theme)
    _paint_landing_pad(tiles, theme)
    _paint_paths(tiles, theme)
    _paint_antennas(tiles)
    _paint_cave_entrance(tiles)
    _paint_market_row(tiles, theme)
    _paint_scraps(tiles)
    _paint_shacks(tiles)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    _paint_building_forecourts(game_map.tiles, theme, spec)
    _paint_transit_bays(game_map.tiles, spec)
    paint_roof_labels(game_map, stamps, "wolf_")
    _set_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


def _set_metadata(game_map, spec, stamps):
    """Attach landmark and cave metadata."""
    game_map.city_layout_id = spec.city_layout_id or "wolf_crater_settlement"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "wolf_")
    game_map.cave_cells = {
        (x, y)
        for y in range(_CAVE_Y_LO, _CAVE_Y_HI + 1)
        for x in range(_CAVE_X_LO, _CAVE_X_HI + 1)
    }


def _add_service_entities(game_map, spec, resolve_ship):
    """Place showroom ships and service terminals on the landing clearing."""
    berth = spec.hangar_anchor
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        game_map.entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(berth.x + off_x, berth.y + off_y),
            name=f"Ship: {ship_obj.name}", ship_id=ship_obj.id,
            width=ship_obj.width, height=ship_obj.height,
        ))
    terminal_data = (
        ("=", "Trade Terminal", -6, "trade_terminal", (100, 220, 255)),
        ("%", "Mechanic Terminal", -2, "mech_terminal", (210, 220, 110)),
        ("A", "Armory Terminal", 2, "armory_terminal", (255, 165, 85)),
    )
    for char, name, dx, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg,
            pos=world.Position(berth.x + dx, berth.y + 3),
            name=name, **{flag: True},
        ))


__all__ = ["build_wolf_layout", "LANDMARK_ORIGINS"]