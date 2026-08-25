"""Ross 154 b -- "Ashfall", a pirate town on a volcanic flare-star world.

Two lava channels cut diagonally across obsidian flats.  Pirates built
their town on basalt shelves, crossing the channels on cooled-crust
bridges.  Roads follow the same 3-cell corridor convention as Earth.

Layout (120x80):
  * Channel 1 (west): y = 0.75*x - 5, NW to SE.
  * Channel 2 (east): y = 0.75*x - 45, NE quadrant.
  * Cooled-crust bridges cross each channel at key points.
  * Spaceport on the NW shelf, landing pad below it.
  * Bar on the NE shelf, bounty office SW, depot SE.
  * 3-cell-wide roads with sidewalks connecting everything.
"""

from __future__ import annotations

from . import city_tiles, world
from .city_layout import (
    building_records,
    paint_roof_labels,
    stamp_city_assets,
    stamp_metadata,
)
from .data.planets import _readable_city_theme
from .data.planets.themes import VOLCANIC


CITY_WIDTH = 120
CITY_HEIGHT = 80

# ---------------------------------------------------------------------------
# Lava channel geometry
# ---------------------------------------------------------------------------

def _ch1_x(y: int) -> float:
    return (y + 5) / 0.75

def _ch2_x(y: int) -> float:
    return (y + 45) / 0.75

def _in_channel(x: int, y: int, ch_x_fn) -> bool:
    return abs(x - ch_x_fn(y)) <= 1.8

# ---------------------------------------------------------------------------
# Building positions (origin = top-left of the layout stamp)
# ---------------------------------------------------------------------------
# Layout sizes: spaceport 24x9, bar 21x9, bounties 19x8, depot 24x9.

_SPACEPORT_ORIGIN = (4, 1)
_BAR_ORIGIN = (90, 1)
_BOUNTIES_ORIGIN = (8, 56)
_DEPOT_ORIGIN = (90, 56)

_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 11, _SPACEPORT_ORIGIN[1] + 8)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 8)
_BOUNTIES_DOOR = (_BOUNTIES_ORIGIN[0] + 9, _BOUNTIES_ORIGIN[1] + 7)
_DEPOT_DOOR = (_DEPOT_ORIGIN[0] + 11, _DEPOT_ORIGIN[1] + 8)

# Landing pad -- below spaceport, above channel 1.
_PAD_X_LO, _PAD_X_HI = 8, 22
_PAD_Y_LO, _PAD_Y_HI = 14, 22

# Bridge crossings: (y_row, x_lo, x_hi, channel_fn)
_BRIDGES = (
    (14, 20, 28, _ch1_x),
    (40, 54, 64, _ch1_x),
    (55, 74, 84, _ch1_x),
    (16, 82, 90, _ch2_x),
    (28, 94, 106, _ch2_x),
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "ross_spaceport": world.Position(*_SPACEPORT_ORIGIN),
    "ross_bar": world.Position(*_BAR_ORIGIN),
    "ross_bounties": world.Position(*_BOUNTIES_ORIGIN),
    "ross_depot": world.Position(*_DEPOT_ORIGIN),
}

# ---------------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------------

_LAVA = world.Tile(
    kind="city_building_wall", char="~", walkable=False,
    fg=(255, 100, 20), bg=(180, 40, 10),
    blocked_message="Molten lava -- you'd be incinerated.",
)
_LAVA_GLOW = world.Tile(
    kind="neon", char="~", walkable=False,
    fg=(255, 180, 60), bg=(200, 80, 20),
    blocked_message="The lava glows white-hot.",
)
_SCRAP_FIRE = world.Tile(
    kind="neon", char="○", walkable=True,
    fg=(240, 130, 50), bg=(72, 48, 40),
)
_HEAT_MARKER = world.Tile(
    kind="neon", char="*", walkable=True,
    fg=(255, 80, 30), bg=(86, 60, 52),
)
_SHACK_WALL = world.Tile(
    kind="city_building_wall", char="#", walkable=False,
    fg=(90, 75, 65), bg=(35, 28, 22),
    blocked_message="The shack wall blocks your path.",
)
_SHACK_ROOF = world.Tile(
    kind="city_building_wall", char="~", walkable=False,
    fg=(70, 58, 50), bg=(28, 22, 18),
    blocked_message="The corrugated roof blocks your path.",
)

_SHACKS: tuple[tuple[int, int, int, int], ...] = (
    (30, 30, 5, 4), (44, 34, 4, 3), (56, 44, 5, 4),
    (68, 26, 4, 3), (38, 50, 4, 3), (72, 52, 5, 4),
    (108, 30, 4, 3), (108, 50, 4, 3), (40, 66, 4, 3),
)
_SCRAPS: tuple[tuple[int, int, bool], ...] = (
    (30, 12, True), (50, 26, True), (70, 18, True),
    (90, 28, True), (42, 42, True), (80, 48, True),
    (16, 44, True), (62, 36, True), (94, 62, True),
    (34, 64, True), (110, 42, True), (58, 22, True),
    (26, 16, False), (68, 30, False), (86, 36, False),
    (46, 52, False), (104, 26, False), (18, 38, False),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_tiles(theme):
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    for x in range(CITY_WIDTH):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(CITY_HEIGHT):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL
    return tiles


def _paint_road_cell(tiles, x, y, tile):
    """Paint a road cell only on non-lava, non-bridge ground."""
    if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
        t = tiles[y][x]
        if t.kind not in {"city_building_wall", "neon"} and t.char != "~":
            tiles[y][x] = tile


# ---------------------------------------------------------------------------
# Painters
# ---------------------------------------------------------------------------

def _paint_lava(tiles):
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            ch1 = _in_channel(x, y, _ch1_x)
            ch2 = _in_channel(x, y, _ch2_x)
            if ch1 or ch2:
                cx = _ch1_x(y) if ch1 else _ch2_x(y)
                tiles[y][x] = _LAVA_GLOW if abs(x - cx) <= 0.9 else _LAVA


def _paint_bridges(tiles):
    """Cooled-crust bridges crossing the lava channels."""
    for y_row, x_lo, x_hi, _ in _BRIDGES:
        for x in range(x_lo, x_hi + 1):
            if 0 <= y_row < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                tiles[y_row][x] = city_tiles.CITY_BRIDGE
                if y_row + 1 < CITY_HEIGHT:
                    tiles[y_row + 1][x] = city_tiles.CITY_BRIDGE


def _paint_pad(tiles, theme):
    pad_tile = world.Tile(
        kind="floor", char=".", walkable=True,
        fg=(60, 80, 120), bg=(50, 62, 85),
    )
    for y in range(_PAD_Y_LO, _PAD_Y_HI + 1):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = pad_tile
    for y in range(_PAD_Y_LO - 1, _PAD_Y_HI + 2):
        for x in range(_PAD_X_LO - 1, _PAD_X_HI + 2):
            if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                t = tiles[y][x]
                if t.kind == "floor" and t.char == ".":
                    if y in (_PAD_Y_LO - 1, _PAD_Y_HI + 1) or \
                       x in (_PAD_X_LO - 1, _PAD_X_HI + 1):
                        tiles[y][x] = theme.sidewalk


def _paint_roads(tiles, theme):
    """3-cell-wide road corridors connecting bridges to buildings."""
    road, lane_ns, lane_ew = theme.road_surface, theme.road_ns, theme.road_ew
    # Main east-west collector at y=26 (below pad, above channel 1).
    for y in (25, 26, 27):
        for x in range(8, 112):
            _paint_road_cell(tiles, x, y, lane_ew if y == 26 else road)
    # South collector at y=54.
    for y in (53, 54, 55):
        for x in range(8, 112):
            _paint_road_cell(tiles, x, y, lane_ew if y == 54 else road)
    # North-south: pad to collector (x=15,16,17).
    for x in (14, 15, 16):
        for y in range(_PAD_Y_HI + 1, 25):
            _paint_road_cell(tiles, x, y, lane_ns if x == 15 else road)
    # N-S: spaceport door to collector (x=15,16,17).
    for x in (14, 15, 16):
        for y in range(_SPACEPORT_DOOR[1] + 1, 25):
            _paint_road_cell(tiles, x, y, lane_ns if x == 15 else road)
    # N-S: central bridge approach (x=58,59,60).
    for x in (58, 59, 60):
        for y in range(27, 40):
            _paint_road_cell(tiles, x, y, lane_ns if x == 59 else road)
    # N-S: SE bridge approach (x=78,79,80).
    for x in (78, 79, 80):
        for y in range(40, 53):
            _paint_road_cell(tiles, x, y, lane_ns if x == 79 else road)
    # N-S: NE bridge to bar (x=86,87,88).
    for x in (86, 87, 88):
        for y in range(11, 25):
            _paint_road_cell(tiles, x, y, lane_ns if x == 87 else road)
    # N-S: east bridge to depot (x=100,101,102).
    for x in (100, 101, 102):
        for y in range(28, 53):
            _paint_road_cell(tiles, x, y, lane_ns if x == 101 else road)


def _paint_sidewalks(tiles, theme):
    """2-cell sidewalks alongside every road corridor."""
    sw = theme.sidewalk
    # Along E-W collectors.
    for y in (23, 24, 28, 29, 51, 52, 56, 57):
        for x in range(8, 112):
            _paint_road_cell(tiles, x, y, sw)
    # Along N-S corridors.
    for x_off in (-2, -1, 2, 3):
        for corridor_x in (15, 59, 79, 87, 101):
            x = corridor_x + x_off
            if x_off < 0:
                y_range = range(11, 25) if corridor_x in (15, 87) else range(25, 53)
            else:
                y_range = range(11, 25) if corridor_x in (15, 87) else range(25, 53)
            for y in y_range:
                _paint_road_cell(tiles, x, y, sw)


def _paint_variety(tiles):
    import random
    rng = random.Random(42)
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and tiles[y][x].char == ".":
                if rng.random() < 0.04:
                    tiles[y][x] = _HEAT_MARKER


def _paint_shack(tiles, x, y, w, h):
    if not all(
        0 <= by < CITY_HEIGHT and 0 <= bx < CITY_WIDTH
        and tiles[by][bx].kind == "floor" and tiles[by][bx].char == "."
        for by in range(y, y + h) for bx in range(x, x + w)
    ):
        return
    for by in range(y, y + h):
        for bx in range(x, x + w):
            edge = by in (y, y + h - 1) or bx in (x, x + w - 1)
            tiles[by][bx] = _SHACK_WALL if edge else _SHACK_ROOF


def _paint_shacks(tiles):
    for x, y, w, h in _SHACKS:
        _paint_shack(tiles, x, y, w, h)


def _paint_scraps(tiles):
    heap = world.Tile(
        kind="plaza", char="░", walkable=True,
        fg=(65, 50, 42), bg=(25, 18, 14),
    )
    for x, y, is_fire in _SCRAPS:
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            if tiles[y][x].kind == "floor" and tiles[y][x].char == ".":
                tiles[y][x] = _SCRAP_FIRE if is_fire else heap


def _paint_heat_glow(tiles):
    import random
    rng = random.Random(99)
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            t = tiles[y][x]
            if t.kind == "floor" and t.char == ".":
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if 0 <= ny < CITY_HEIGHT and 0 <= nx < CITY_WIDTH:
                            nt = tiles[ny][nx]
                            if nt.char == "~" and nt.fg[0] > 200:
                                if rng.random() < 0.12:
                                    tiles[y][x] = _HEAT_MARKER
                                break


def _paint_forecourts(tiles, theme, spec):
    for building in spec.buildings:
        y = building.y_hi + 1
        for x in range(building.door_x - 1, building.door_x + 2):
            if 0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT:
                t = tiles[y][x]
                if t.kind == "floor" and t.char == ".":
                    tiles[y][x] = theme.sidewalk


def _paint_transit_bays(tiles, spec):
    bay = world.Tile(
        kind="floor", char=" ", walkable=True,
        fg=(80, 60, 55), bg=(72, 58, 62),
    )
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            tiles[y][x] = bay
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= ny < CITY_HEIGHT and 0 <= nx < CITY_WIDTH:
                    t = tiles[ny][nx]
                    if t.kind == "floor" and t.char == ".":
                        tiles[ny][nx] = bay


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_ross_layout(spec, resolve_ship):
    theme = _readable_city_theme(VOLCANIC)
    tiles = _base_tiles(theme)
    _paint_lava(tiles)
    _paint_bridges(tiles)
    _paint_variety(tiles)
    _paint_pad(tiles, theme)
    _paint_roads(tiles, theme)
    _paint_sidewalks(tiles, theme)
    _paint_shacks(tiles)
    _paint_scraps(tiles)
    _paint_heat_glow(tiles)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    _paint_forecourts(game_map.tiles, theme, spec)
    _paint_transit_bays(game_map.tiles, spec)
    paint_roof_labels(game_map, stamps, "ross_")
    _set_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


def _set_metadata(game_map, spec, stamps):
    game_map.city_layout_id = spec.city_layout_id or "ross_volcanic_settlement"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "ross_")


def _add_service_entities(game_map, spec, resolve_ship):
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


__all__ = ["build_ross_layout", "LANDMARK_ORIGINS"]
