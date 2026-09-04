"""Ross 154 b -- "Ashfall", a pirate town on a volcanic flare-star world.

Simple road system: roads go where they need to go.  If a road crosses
lava, a bridge is placed at that crossing point.
"""

from __future__ import annotations

from . import city_tiles, world
from .city_kit import (
    add_service_terminals,
    add_showroom_ships,
    base_tiles,
    paint_door_forecourts,
    paint_transit_bays,
    set_city_metadata,
)
from .city_layout import paint_roof_labels, stamp_city_assets
from .data.planets import _readable_city_theme
from .data.planets.themes import VOLCANIC


CITY_WIDTH = 120
CITY_HEIGHT = 80

# ---------------------------------------------------------------------------
# Lava
# ---------------------------------------------------------------------------

def _ch1_x(y: int) -> float:
    return (y + 5) / 0.75

def _ch2_x(y: int) -> float:
    return (y + 45) / 0.75

def _is_lava(x: int, y: int) -> bool:
    return abs(x - _ch1_x(y)) <= 1.8 or abs(x - _ch2_x(y)) <= 1.8

# ---------------------------------------------------------------------------
# Building positions
# ---------------------------------------------------------------------------
_SPACEPORT_ORIGIN = (4, 1)
_BAR_ORIGIN = (90, 1)
_BOUNTIES_ORIGIN = (8, 56)
_DEPOT_ORIGIN = (94, 56)

_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 11, _SPACEPORT_ORIGIN[1] + 8)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 8)
_BOUNTIES_DOOR = (_BOUNTIES_ORIGIN[0] + 9, _BOUNTIES_ORIGIN[1] + 7)
_DEPOT_DOOR = (_DEPOT_ORIGIN[0] + 10, _DEPOT_ORIGIN[1])

_PAD_X_LO, _PAD_X_HI = 8, 22
_PAD_Y_LO, _PAD_Y_HI = 14, 22

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
    kind="lava_glow", char="~", walkable=False,
    fg=(255, 180, 60), bg=(200, 80, 20),
    blocked_message="The lava glows white-hot.",
)
_SCRAP_FIRE = world.Tile(
    kind="neon", char="○", walkable=True,
    fg=(240, 130, 50), bg=(72, 48, 40),
)
# Street texture, not light: 300+ markers city-wide, and every neon
# cell collects as a radius-4 source — as neon the whole town burned
# (playtest v15). Unlit kind keeps the warm paint.
_HEAT_MARKER = world.Tile(
    kind="heat_marker", char="*", walkable=True,
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

def _paint_road_cell(tiles, x, y, tile):
    if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
        t = tiles[y][x]
        if t.kind != "city_building_wall" and not (
            _PAD_X_LO <= x <= _PAD_X_HI and _PAD_Y_LO <= y <= _PAD_Y_HI
        ):
            tiles[y][x] = tile


def _paint_line(tiles, x0, y0, x1, y1, theme):
    """Paint a 3-cell road from (x0,y0) to (x1,y1). Adds bridges where it crosses lava."""
    dx = x1 - x0
    dy = y1 - y0
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        return
    road, lane = theme.road_surface, (theme.road_ns if dy != 0 else theme.road_ew)
    for i in range(steps + 1):
        t = i / steps
        cx = round(x0 + dx * t)
        cy = round(y0 + dy * t)
        # Paint 3-cell road perpendicular to direction.
        if dy != 0:  # Vertical segment.
            for ox in (-1, 0, 1):
                nx = cx + ox
                tile = lane if ox == 0 else road
                if _is_lava(nx, cy):
                    # Place bridge.
                    if 0 <= cy < CITY_HEIGHT and 0 <= nx < CITY_WIDTH:
                        tiles[cy][nx] = city_tiles.CITY_BRIDGE
                else:
                    _paint_road_cell(tiles, nx, cy, tile)
        else:  # Horizontal segment.
            for oy in (-1, 0, 1):
                ny = cy + oy
                tile = lane if oy == 0 else road
                if _is_lava(cx, ny):
                    if 0 <= ny < CITY_HEIGHT and 0 <= cx < CITY_WIDTH:
                        tiles[ny][cx] = city_tiles.CITY_BRIDGE
                else:
                    _paint_road_cell(tiles, cx, ny, tile)


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
    """Roads go where they need to go. Bridges where they cross lava."""
    # Pad right edge → central area → south to bounties road.
    _paint_line(tiles, 23, 18, 40, 18, theme)
    _paint_line(tiles, 40, 18, 40, 60, theme)
    # Bounties road east-west, turns north to cross lava.
    _paint_line(tiles, 40, 62, 80, 62, theme)
    _paint_road_cell(tiles, 81, 62, theme.road_surface)
    _paint_line(tiles, 80, 61, 80, 52, theme)
    # Bounties door.
    _paint_line(tiles, 40, 62, _BOUNTIES_DOOR[0], 62, theme)
    # Junction: connect y=17 road up to y=14 road.
    _paint_line(tiles, 40, 17, 40, 14, theme)
    # East junction → east across second lava, then south to depot road.
    _paint_line(tiles, 40, 14, 101, 14, theme)
    _paint_line(tiles, 101, 14, 101, 28, theme)
    # Depot road.
    _paint_line(tiles, 101, 28, 101, 52, theme)
    # West connector to bounties road.
    _paint_line(tiles, 101, 52, 80, 52, theme)
    # Sidewalk from road to depot door (horizontal then south).
    for x in range(101, _DEPOT_DOOR[0] + 1):
        t = tiles[52][x]
        if t.kind in {"floor", "grass"}:
            tiles[52][x] = theme.sidewalk
    for y in range(52, _DEPOT_DOOR[1]):
        t = tiles[y][_DEPOT_DOOR[0]]
        if t.kind in {"floor", "grass"}:
            tiles[y][_DEPOT_DOOR[0]] = theme.sidewalk



def _paint_pad(tiles, theme):
    pad_tile = world.Tile(
        kind="landing_pad", char=".", walkable=True,
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


_BAY_TILE = world.Tile(
    kind="transit_bay", char="=", walkable=True,
    fg=(0, 229, 255), bg=(30, 68, 92),
)
_BAY_KINDS = frozenset({
    "floor", "grass", "grass_accent", "plaza", "city_plaza",
    "sidewalk", "landing_pad",
})


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_ross_layout(spec, resolve_ship):
    theme = _readable_city_theme(VOLCANIC)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _paint_lava(tiles)
    _paint_variety(tiles)
    _paint_pad(tiles, theme)
    _paint_roads(tiles, theme)
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
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=_BAY_KINDS,
    )
    paint_transit_bays(
        game_map.tiles, spec, _BAY_TILE, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=_BAY_KINDS, force_center=True,
    )
    paint_roof_labels(game_map, stamps, "ross_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="ross_", default_layout_id="ross_volcanic_settlement",
    )
    add_showroom_ships(game_map, spec, resolve_ship)
    add_service_terminals(game_map, spec)
    return game_map


__all__ = ["build_ross_layout", "LANDMARK_ORIGINS"]
