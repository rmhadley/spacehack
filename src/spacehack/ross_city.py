"""Ross 154 b -- "Ashfall", a pirate town on a volcanic flare-star world.

Two lava channels cut diagonally across obsidian flats.  Pirates built
their town on basalt shelves on either side, crossing the channels on
cooled-crust bridges.

Layout (120x80):
  * Channel 1 (west): y = 0.75*x - 5, NW to SE across the whole map.
  * Channel 2 (east): y = 0.75*x - 45, NE quadrant only.
  * Cooled-crust bridges cross each channel.
  * Spaceport (24x9) on the NW shelf, above the pad.
  * Landing pad below the spaceport, clear of lava.
  * Bar (21x9) on the NE shelf, east of channel 2.
  * Bounty office (19x8) on the SW shelf.
  * Depot (24x9) on the SE shelf.
  * Roads connect bridges to buildings.
"""

from __future__ import annotations

from . import world
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
# Spaceport layout: 24x9, door at (11, 8) relative to origin.
# Bar layout: 21x9, door at (10, 8).
# Bounties layout: 19x8, door at (9, 7).
# Depot layout: 24x9, door at (11, 8).

_SPACEPORT_ORIGIN = (4, 1)     # covers x=4..27, y=1..9
_BAR_ORIGIN = (90, 1)          # covers x=90..110, y=1..9
_BOUNTIES_ORIGIN = (8, 56)     # covers x=8..26, y=56..63
_DEPOT_ORIGIN = (90, 56)       # covers x=90..113, y=56..63

# Absolute door positions (origin + layout-relative door).
_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 11, _SPACEPORT_ORIGIN[1] + 8)  # (15, 9)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 8)                    # (100, 9)
_BOUNTIES_DOOR = (_BOUNTIES_ORIGIN[0] + 9, _BOUNTIES_ORIGIN[1] + 7)     # (17, 63)
_DEPOT_DOOR = (_DEPOT_ORIGIN[0] + 11, _DEPOT_ORIGIN[1] + 8)             # (101, 64)

# Landing pad -- below spaceport, above channel 1.
_PAD_X_LO, _PAD_X_HI = 8, 22
_PAD_Y_LO, _PAD_Y_HI = 14, 22

# Bridge crossings: (y_row, x_lo, x_hi, channel_fn)
_BRIDGES = (
    (14, 20, 28, _ch1_x),    # NW bridge near pad
    (40, 54, 64, _ch1_x),    # Central bridge
    (55, 74, 84, _ch1_x),    # SE bridge
    (16, 82, 90, _ch2_x),    # NE bridge near bar
    (28, 94, 106, _ch2_x),   # East bridge near depot
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
_COOLED_CRUST = world.Tile(
    kind="floor", char="=", walkable=True,
    fg=(85, 60, 50), bg=(72, 55, 50),
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

# Pirate shacks: (x, y, w, h)
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


def _safe_paint(tiles, x, y, tile):
    """Paint only on plain '.' floor -- never overwrite lava, bridges, etc."""
    if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
        if tiles[y][x].kind == "floor" and tiles[y][x].char == ".":
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
    for y_row, x_lo, x_hi, _ in _BRIDGES:
        for x in range(x_lo, x_hi + 1):
            if 0 <= y_row < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                tiles[y_row][x] = _COOLED_CRUST
                if y_row + 1 < CITY_HEIGHT:
                    tiles[y_row + 1][x] = _COOLED_CRUST


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
    ew, ns = theme.road_ew, theme.road_ns
    # Spaceport door south to pad.
    for y in range(_SPACEPORT_DOOR[1] + 1, _PAD_Y_LO):
        _safe_paint(tiles, _SPACEPORT_DOOR[0], y, ns)
    # Pad south to bridge approach.
    for y in range(_PAD_Y_HI + 1, 26):
        _safe_paint(tiles, _PAD_X_HI, y, ns)
    # Horizontal collector at y=26.
    for x in range(8, 50):
        _safe_paint(tiles, x, 26, ew)
    # NW bridge approach down to y=26.
    for y in range(16, 26):
        _safe_paint(tiles, 24, y, ns)
    # Central bridge approach y=26 to y=40.
    for y in range(26, 42):
        _safe_paint(tiles, 58, y, ns)
        _safe_paint(tiles, 59, y, ns)
    # SE bridge approach y=40 to y=55.
    for y in range(40, 57):
        _safe_paint(tiles, 78, y, ns)
        _safe_paint(tiles, 79, y, ns)
    # NE bridge approach y=16 up to bar.
    for y in range(11, 18):
        _safe_paint(tiles, 86, y, ns)
        _safe_paint(tiles, 87, y, ns)
    # East bridge approach y=28 down to depot.
    for y in range(28, 56):
        _safe_paint(tiles, 100, y, ns)
        _safe_paint(tiles, 101, y, ns)
    # South collector at y=54 (west and east segments).
    for x in range(8, 40):
        _safe_paint(tiles, x, 54, ew)
    for x in range(86, 112):
        _safe_paint(tiles, x, 54, ew)
    # Building approaches (south collector to doors).
    for bx, y_hi in (_BOUNTIES_DOOR, _DEPOT_DOOR):
        for y in range(54, y_hi):
            _safe_paint(tiles, bx, y, ns)


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
    # 1. Lava and bridges first (impassable terrain).
    _paint_lava(tiles)
    _paint_bridges(tiles)
    # 2. Variety and heat markers on remaining floor.
    _paint_variety(tiles)
    # 3. Landing pad (on clear floor, no lava overlap).
    _paint_pad(tiles, theme)
    # 4. Roads (only on plain floor, never on lava/bridges/pad).
    _paint_roads(tiles, theme)
    # 5. Shacks and debris (on remaining floor).
    _paint_shacks(tiles)
    _paint_scraps(tiles)
    _paint_heat_glow(tiles)
    # 6. Build map, then stamp buildings (overwrites anything underneath).
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    # 7. Forecourts and transit bays (on remaining floor near doors).
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
