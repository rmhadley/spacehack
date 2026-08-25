"""Ross 154 b -- "Ashfall", a pirate town on a volcanic flare-star world.

The ground glows.  Lava channels carve through obsidian flats, forcing
navigation around molten rock.  Pirates built their town on whatever
basalt shelf didn't move, stacking containers and corrugated shelters
wherever the heat would let them.

Layout (120x80):
  * Two lava channels running NE to SW, dividing the map into three zones.
  * Cooled-crust bridges crossing the channels at three points.
  * Spaceport on the NW basalt shelf.
  * The Flare Line bar carved into a dormant vent on the NE shelf.
  * Bounty office on the SW shelf.
  * Depot on the SE shelf.
  * Landing pad on a raised basalt platform in the NW zone.
  * Pirate shacks, barrel fires, and scorch marks throughout.
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
# Placement constants
# ---------------------------------------------------------------------------

_SPACEPORT_X_LO, _SPACEPORT_X_HI = 8, 32
_SPACEPORT_Y_LO, _SPACEPORT_Y_HI = 10, 22
_BAR_X_LO, _BAR_X_HI = 88, 112
_BAR_Y_LO, _BAR_Y_HI = 8, 18
_BOUNTIES_X_LO, _BOUNTIES_X_HI = 8, 26
_BOUNTIES_Y_LO, _BOUNTIES_Y_HI = 55, 68
_DEPOT_X_LO, _DEPOT_X_HI = 88, 112
_DEPOT_Y_LO, _DEPOT_Y_HI = 55, 68

# Landing pad -- raised basalt platform in the NW zone.
_PAD_X_LO, _PAD_X_HI = 38, 55
_PAD_Y_LO, _PAD_Y_HI = 14, 26

# ---------------------------------------------------------------------------
# Lava channel geometry
# ---------------------------------------------------------------------------
# Channel 1: runs from upper-left to lower-right (NE to SW direction).
# Channel 2: runs parallel, further east.
# Both are impassable molten rock.

def _in_lava_channel_1(x: int, y: int) -> bool:
    """First lava channel: y roughly = 0.75*x - 5, width ~3."""
    expected_y = 0.75 * x - 5
    return abs(y - expected_y) <= 1.5

def _in_lava_channel_2(x: int, y: int) -> bool:
    """Second lava channel: y roughly = 0.75*x - 45, width ~3."""
    expected_y = 0.75 * x - 45
    return abs(y - expected_y) <= 1.5

# Bridge crossings -- cooled crust over each channel at specific rows.
# (channel, y_row, x_lo, x_hi)
_BRIDGES = (
    (1, 20, 30, 38),   # Channel 1 bridge near spaceport
    (1, 52, 68, 76),   # Channel 1 bridge mid-map
    (2, 30, 62, 70),   # Channel 2 bridge near bar
    (2, 60, 100, 108), # Channel 2 bridge near depot
)

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
_OBSIDIAN = world.Tile(
    kind="floor", char=".", walkable=True,
    fg=(48, 38, 52), bg=(70, 58, 64),
)
_BASALT = world.Tile(
    kind="floor", char=".", walkable=True,
    fg=(60, 50, 55), bg=(70, 58, 64),
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
_SCORCH = world.Tile(
    kind="floor", char=".", walkable=True,
    fg=(55, 42, 50), bg=(70, 58, 64),
)

# Non-enterable structures
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

# Pirate shack placements: (x, y, width, height)
_SHACKS: tuple[tuple[int, int, int, int], ...] = (
    # NW zone -- near spaceport.
    (12, 28, 5, 4), (28, 30, 4, 3), (44, 30, 5, 4),
    # NE zone -- between channels.
    (50, 8, 4, 3), (66, 12, 5, 4), (80, 6, 4, 3),
    # SW zone -- near bounties.
    (32, 56, 5, 4), (48, 60, 4, 3), (20, 70, 5, 4),
    # SE zone -- near depot.
    (72, 58, 5, 4), (88, 72, 4, 3), (104, 52, 5, 4),
    # Along channel edges.
    (36, 36, 4, 3), (78, 42, 5, 4), (56, 68, 4, 3),
)

# Barrel fires and scorch marks: (x, y, is_fire)
_SCRAPS: tuple[tuple[int, int, bool], ...] = (
    (22, 24, True), (50, 10, True), (74, 16, True),
    (100, 12, True), (40, 40, True), (80, 50, True),
    (16, 48, True), (60, 36, True), (92, 64, True),
    (34, 66, True), (110, 44, True), (58, 22, True),
    (26, 14, False), (68, 28, False), (86, 38, False),
    (46, 54, False), (104, 28, False), (18, 40, False),
    (72, 70, False), (42, 46, False),
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "ross_spaceport": world.Position(_SPACEPORT_X_LO, _SPACEPORT_Y_LO),
    "ross_bar": world.Position(_BAR_X_LO, _BAR_Y_LO),
    "ross_bounties": world.Position(_BOUNTIES_X_LO, _BOUNTIES_Y_LO),
    "ross_depot": world.Position(_DEPOT_X_LO, _DEPOT_Y_LO),
}


# ---------------------------------------------------------------------------
# Tile helpers
# ---------------------------------------------------------------------------

def _base_tiles(theme):
    """Dark obsidian floor with perimeter walls."""
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    for x in range(CITY_WIDTH):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(CITY_HEIGHT):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL
    return tiles


def _paint_cell(tiles, x, y, tile):
    """Paint on open ground only."""
    if tiles[y][x].kind in {"floor", "grass"}:
        tiles[y][x] = tile


# ---------------------------------------------------------------------------
# Painter functions
# ---------------------------------------------------------------------------

def _paint_lava_channels(tiles):
    """Carve two diagonal lava channels across the obsidian field."""
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if _in_lava_channel_1(x, y) or _in_lava_channel_2(x, y):
                # Core of the channel -- bright lava.
                if abs(y - (0.75 * x - (5 if _in_lava_channel_1(x, y) else 45))) <= 0.8:
                    tiles[y][x] = _LAVA_GLOW
                else:
                    tiles[y][x] = _LAVA


def _paint_bridges(tiles):
    """Place cooled-crust bridges over the lava channels."""
    for ch, y_row, x_lo, x_hi in _BRIDGES:
        for x in range(x_lo, x_hi + 1):
            if 0 <= y_row < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                tiles[y_row][x] = _COOLED_CRUST
                # Widen bridge to 2 cells for walkability.
                if y_row + 1 < CITY_HEIGHT:
                    tiles[y_row + 1][x] = _COOLED_CRUST


def _paint_landing_pad(tiles, theme):
    """Raised basalt landing platform."""
    pad_tile = world.Tile(
        kind="floor", char=".", walkable=True,
        fg=(60, 80, 120), bg=(50, 62, 85),
    )
    for y in range(_PAD_Y_LO, _PAD_Y_HI + 1):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = pad_tile
    # Sidewalk border around the pad.
    for y in range(_PAD_Y_LO - 1, _PAD_Y_HI + 2):
        for x in range(_PAD_X_LO - 1, _PAD_X_HI + 2):
            if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                if tiles[y][x].kind in {"floor", "grass"}:
                    if y in (_PAD_Y_LO - 1, _PAD_Y_HI + 1) or x in (_PAD_X_LO - 1, _PAD_X_HI + 1):
                        tiles[y][x] = theme.sidewalk


def _paint_paths(tiles, theme):
    """Worn footpaths linking the pad to each building zone."""
    # Pad -> spaceport (west).
    _paint_worn_path(tiles, theme, _PAD_X_LO, _PAD_Y_LO + 6, _SPACEPORT_X_HI, _SPACEPORT_Y_LO + 6)
    # Pad -> bar (east across channel 1 bridge).
    _paint_worn_path(tiles, theme, _PAD_X_HI, _PAD_Y_LO + 4, 62, 22)
    _paint_worn_path(tiles, theme, 62, 22, _BAR_X_LO, _BAR_Y_HI)
    # Pad -> bounties (south).
    _paint_worn_path(tiles, theme, _PAD_X_LO + 4, _PAD_Y_HI, _PAD_X_LO + 4, 42)
    _paint_worn_path(tiles, theme, _PAD_X_LO + 4, 42, 18, _BOUNTIES_Y_LO)
    # Pad -> depot (south-east).
    _paint_worn_path(tiles, theme, _PAD_X_HI, _PAD_Y_HI, 70, 54)
    _paint_worn_path(tiles, theme, 70, 54, _DEPOT_X_LO, _DEPOT_Y_LO + 6)


def _paint_worn_path(tiles, theme, x0, y0, x1, y1):
    """Dither a worn trail between two points."""
    dx = x1 - x0
    dy = y1 - y0
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        return
    for i in range(steps + 1):
        t = i / steps
        cx = round(x0 + dx * t)
        cy = round(y0 + dy * t)
        _paint_cell(tiles, cx, cy, theme.sidewalk)
        if i % 4 == 1 and abs(dx) > abs(dy):
            _paint_cell(tiles, cx, cy - 1, theme.sidewalk)
        if i % 7 == 3 and abs(dy) > abs(dx):
            _paint_cell(tiles, cx - 1, cy, theme.sidewalk)


def _paint_obsidian_variety(tiles):
    """Scatter scorch marks and cooled patches for texture."""
    import random
    rng = random.Random(42)
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and tiles[y][x].char == ".":
                if rng.random() < 0.04:
                    tiles[y][x] = _SCORCH
                elif rng.random() < 0.03:
                    tiles[y][x] = _BASALT


def _paint_shack(tiles, x, y, w, h):
    """Paint one non-enterable pirate shack on open ground."""
    if not all(
        tiles[by][bx].kind in {"floor", "grass"}
        for by in range(y, y + h)
        for bx in range(x, x + w)
        if 0 <= by < CITY_HEIGHT and 0 <= bx < CITY_WIDTH
    ):
        return
    for by in range(y, y + h):
        for bx in range(x, x + w):
            if not (0 <= by < CITY_HEIGHT and 0 <= bx < CITY_WIDTH):
                continue
            if by in (y, y + h - 1) or bx in (x, x + w - 1):
                tiles[by][bx] = _SHACK_WALL
            else:
                tiles[by][bx] = _SHACK_ROOF


def _paint_shacks(tiles):
    """Scatter pirate lean-tos across the zones."""
    for x, y, w, h in _SHACKS:
        _paint_shack(tiles, x, y, w, h)


def _paint_scraps(tiles):
    """Scatter barrel fires and scorch debris."""
    scrap_heap = world.Tile(
        kind="plaza", char="░", walkable=True,
        fg=(65, 50, 42), bg=(25, 18, 14),
    )
    for x, y, is_fire in _SCRAPS:
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            if tiles[y][x].kind in {"floor", "grass"}:
                tiles[y][x] = _SCRAP_FIRE if is_fire else scrap_heap


def _paint_heat_glow(tiles):
    """Add heat shimmer markers near lava edges."""
    import random
    rng = random.Random(99)
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind in {"floor", "grass"} and tiles[y][x].char == ".":
                # Check if any neighbor is lava.
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if 0 <= ny < CITY_HEIGHT and 0 <= nx < CITY_WIDTH:
                            if tiles[ny][nx].char == "~" and tiles[ny][nx].fg[0] > 200:
                                if rng.random() < 0.15:
                                    tiles[y][x] = _HEAT_MARKER
                                break


def _paint_building_forecourts(tiles, theme, spec):
    """Small cleared forecourt south of each door."""
    for building in spec.buildings:
        y = building.y_hi + 1
        for x in range(building.door_x - 1, building.door_x + 2):
            if 0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT:
                if tiles[y][x].kind in {"floor", "grass"}:
                    tiles[y][x] = theme.sidewalk


def _paint_transit_bays(tiles, spec):
    """Dedicated transit landing zones."""
    bay_tile = world.Tile(
        kind="floor", char=" ", walkable=True,
        fg=(80, 60, 55), bg=(72, 58, 62),
    )
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            tiles[y][x] = bay_tile
        # Widen the bay so transit doesn't block the path.
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= ny < CITY_HEIGHT and 0 <= nx < CITY_WIDTH:
                    if tiles[ny][nx].kind in {"floor", "grass"}:
                        tiles[ny][nx] = bay_tile


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_ross_layout(spec, resolve_ship):
    """Build Ashfall's 120x80 volcanic pirate settlement."""
    theme = _readable_city_theme(VOLCANIC)
    tiles = _base_tiles(theme)
    _paint_lava_channels(tiles)
    _paint_bridges(tiles)
    _paint_obsidian_variety(tiles)
    _paint_landing_pad(tiles, theme)
    _paint_paths(tiles, theme)
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
    _paint_building_forecourts(game_map.tiles, theme, spec)
    _paint_transit_bays(game_map.tiles, spec)
    paint_roof_labels(game_map, stamps, "ross_")
    _set_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


def _set_metadata(game_map, spec, stamps):
    """Attach landmark and layout metadata."""
    game_map.city_layout_id = spec.city_layout_id or "ross_volcanic_settlement"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "ross_")


def _add_service_entities(game_map, spec, resolve_ship):
    """Place showroom ships and service terminals on the landing pad."""
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
