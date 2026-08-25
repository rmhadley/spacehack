"""Ross 154 b -- "Ashfall", a pirate town on a volcanic flare-star world.

Two lava channels cut diagonally across obsidian flats.  Roads are
purpose-driven: each road takes you from one place to another, and
turns into a bridge when crossing lava.

Layout (120x80):
  * Channel 1: y = 0.75*x - 5, NW to SE.
  * Channel 2: y = 0.75*x - 45, NE quadrant.
  * Spaceport NW, bar NE, bounty office SW, depot SE.
  * Pad below spaceport, roads connect pad-bridges-buildings.
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

# ---------------------------------------------------------------------------
# Building positions
# ---------------------------------------------------------------------------
_SPACEPORT_ORIGIN = (4, 1)
_BAR_ORIGIN = (90, 1)
_BOUNTIES_ORIGIN = (8, 56)
_DEPOT_ORIGIN = (90, 56)

_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 11, _SPACEPORT_ORIGIN[1] + 8)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 8)
_BOUNTIES_DOOR = (_BOUNTIES_ORIGIN[0] + 9, _BOUNTIES_ORIGIN[1] + 7)
_DEPOT_DOOR = (_DEPOT_ORIGIN[0] + 11, _DEPOT_ORIGIN[1] + 8)

_PAD_X_LO, _PAD_X_HI = 8, 22
_PAD_Y_LO, _PAD_Y_HI = 14, 22
_PAD_CX = (_PAD_X_LO + _PAD_X_HI) // 2
_PAD_CY = (_PAD_Y_LO + _PAD_Y_HI) // 2

# Bridge positions: (y_row, x_lo, x_hi)
_BRIDGES = (
    (14, 20, 28),   # NW bridge over channel 1.
    (16, 82, 90),   # NE bridge over channel 2.
    (40, 54, 64),   # Central bridge over channel 1.
    (55, 74, 84),   # SE bridge over channel 1.
    (28, 94, 106),  # East bridge over channel 2.
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


def _paint_cell(tiles, x, y, tile):
    """Paint only on open ground -- never on lava, walls, or pads."""
    if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
        t = tiles[y][x]
        if t.kind in {"floor", "grass"} and t.char == ".":
            tiles[y][x] = tile


def _paint_road_h(tiles, x0, x1, y, theme):
    """Horizontal 3-cell road."""
    road, lane = theme.road_surface, theme.road_ew
    for x in range(min(x0, x1), max(x0, x1) + 1):
        _paint_cell(tiles, x, y - 1, road)
        _paint_cell(tiles, x, y, lane)
        _paint_cell(tiles, x, y + 1, road)


def _paint_road_v(tiles, x, y0, y1, theme):
    """Vertical 3-cell road."""
    road, lane = theme.road_surface, theme.road_ns
    for y in range(min(y0, y1), max(y0, y1) + 1):
        _paint_cell(tiles, x - 1, y, road)
        _paint_cell(tiles, x, y, lane)
        _paint_cell(tiles, x + 1, y, road)


# ---------------------------------------------------------------------------
# Painters
# ---------------------------------------------------------------------------

def _paint_lava(tiles):
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            ch1 = abs(x - _ch1_x(y)) <= 1.8
            ch2 = abs(x - _ch2_x(y)) <= 1.8
            if ch1 or ch2:
                cx = _ch1_x(y) if ch1 else _ch2_x(y)
                tiles[y][x] = _LAVA_GLOW if abs(x - cx) <= 0.9 else _LAVA


def _paint_roads(tiles, theme):
    """Purpose-driven roads painted BEFORE pad and bridges."""
    # Pad south edge down to NW bridge.
    _paint_road_v(tiles, _PAD_CX, _PAD_Y_HI + 1, 14, theme)
    # Pad right edge south, then east to central bridge.
    _paint_road_v(tiles, _PAD_X_HI + 1, _PAD_CY, 38, theme)
    _paint_road_h(tiles, _PAD_X_HI + 1, 59, 38, theme)
    _paint_road_v(tiles, 59, 38, 40, theme)
    # Central bridge south to SE bridge.
    _paint_road_v(tiles, 59, 42, 55, theme)
    # SE bridge south then west to bounties.
    _paint_road_v(tiles, 79, 57, 62, theme)
    _paint_road_h(tiles, 79, _BOUNTIES_DOOR[0], 62, theme)
    # NW bridge east to NE bridge.
    _paint_road_h(tiles, 28, 82, 16, theme)
    # NE bridge south then east to bar door.
    _paint_road_v(tiles, 86, 18, 11, theme)
    _paint_road_h(tiles, 86, _BAR_DOOR[0], 11, theme)
    # East bridge south then east to depot door.
    _paint_road_v(tiles, 100, 30, 52, theme)
    _paint_road_h(tiles, 100, _DEPOT_DOOR[0], 52, theme)
    # Spaceport door south to pad.
    _paint_road_v(tiles, _SPACEPORT_DOOR[0], _SPACEPORT_DOOR[1] + 1, _PAD_Y_LO - 1, theme)


def _paint_bridges(tiles):
    """Bridge crossings over lava (overwrite roads and lava)."""
    for y_row, x_lo, x_hi in _BRIDGES:
        for y in range(y_row, y_row + 2):
            for x in range(x_lo, x_hi + 1):
                if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                    tiles[y][x] = city_tiles.CITY_BRIDGE


def _paint_pad(tiles, theme):
    """Landing pad (overwrite roads underneath)."""
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
        and tiles[by][bx].kind in {"floor", "grass"}
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
            if tiles[y][x].kind in {"floor", "grass"}:
                tiles[y][x] = _SCRAP_FIRE if is_fire else heap


def _paint_heat_glow(tiles):
    import random
    rng = random.Random(99)
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            t = tiles[y][x]
            if t.kind in {"floor", "grass"}:
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
                if t.kind in {"floor", "grass"}:
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
                    if t.kind in {"floor", "grass"}:
                        tiles[ny][nx] = bay


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_ross_layout(spec, resolve_ship):
    theme = _readable_city_theme(VOLCANIC)
    tiles = _base_tiles(theme)
    _paint_lava(tiles)
    _paint_variety(tiles)
    # Roads first, then bridges overwrite where they cross lava,
    # then pad overwrites where it sits.
    _paint_roads(tiles, theme)
    _paint_bridges(tiles)
    _paint_pad(tiles, theme)
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
