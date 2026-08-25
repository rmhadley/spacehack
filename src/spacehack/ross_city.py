"""Ross 154 b -- "Ashfall", a pirate town on a volcanic flare-star world.

The ground glows.  Two lava channels cut diagonally across obsidian
flats, forcing navigation around molten rock.  Pirates built their town
on whatever basalt shelf didn't move, stacking containers and corrugated
shelters wherever the heat would let them.

Layout (120x80):
  * Channel 1 (west): runs NW to SE through the map centre.
  * Channel 2 (east): runs NE to SE in the upper-east quadrant.
  * Cooled-crust bridges cross each channel at key crossing points.
  * Spaceport + landing pad on the NW basalt shelf (safe zone).
  * The Flare Line bar on the NE shelf, behind channel 2.
  * Bounty office on the SW shelf.
  * Depot on the SE shelf.
  * Roads link the bridges to every building.
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

_SPACEPORT_X_LO, _SPACEPORT_X_HI = 8, 34
_SPACEPORT_Y_LO, _SPACEPORT_Y_HI = 10, 22
_BAR_X_LO, _BAR_X_HI = 90, 112
_BAR_Y_LO, _BAR_Y_HI = 8, 18
_BOUNTIES_X_LO, _BOUNTIES_X_HI = 8, 26
_BOUNTIES_Y_LO, _BOUNTIES_Y_HI = 55, 68
_DEPOT_X_LO, _DEPOT_X_HI = 90, 112
_DEPOT_Y_LO, _DEPOT_Y_HI = 55, 68

# Landing pad -- NW shelf, safely away from both channels.
_PAD_X_LO, _PAD_X_HI = 14, 28
_PAD_Y_LO, _PAD_Y_HI = 14, 22

# ---------------------------------------------------------------------------
# Lava channel geometry
# ---------------------------------------------------------------------------
# Channel 1: y = 0.75*x - 5  (runs NW to SE across the whole map)
# Channel 2: y = 0.75*x - 45 (runs NE to SE, only in upper-east)

def _ch1_x(y: int) -> float:
    """Channel 1 centre x at a given y."""
    return (y + 5) / 0.75

def _ch2_x(y: int) -> float:
    """Channel 2 centre x at a given y."""
    return (y + 45) / 0.75

def _in_channel(x: int, y: int, ch_x_fn) -> bool:
    cx = ch_x_fn(y)
    return abs(x - cx) <= 1.8

# ---------------------------------------------------------------------------
# Bridge crossings -- cooled crust at points where channels are narrow.
# (y_row, x_lo, x_hi, channel_fn)
# ---------------------------------------------------------------------------
_BRIDGES = (
    # Channel 1 -- three crossings along its length.
    (20, 28, 36, _ch1_x),    # NW bridge near spaceport
    (40, 54, 64, _ch1_x),    # Central bridge
    (55, 74, 84, _ch1_x),    # SE bridge near depot approach
    # Channel 2 -- two crossings in the NE.
    (18, 80, 90, _ch2_x),    # NE bridge near bar
    (30, 94, 106, _ch2_x),   # East bridge near depot
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
    (8, 28, 5, 4), (24, 28, 4, 3),
    # NE zone -- between channels.
    (50, 8, 4, 3), (66, 10, 5, 4), (74, 6, 4, 3),
    # SW zone -- near bounties.
    (32, 56, 5, 4), (44, 62, 4, 3), (16, 70, 5, 4),
    # SE zone -- near depot.
    (72, 58, 5, 4), (88, 68, 4, 3), (104, 52, 5, 4),
    # Along channel edges.
    (40, 34, 4, 3), (62, 44, 5, 4),
)

# Barrel fires and scrap: (x, y, is_fire)
_SCRAPS: tuple[tuple[int, int, bool], ...] = (
    (22, 24, True), (50, 12, True), (74, 16, True),
    (100, 12, True), (40, 42, True), (80, 50, True),
    (16, 48, True), (60, 36, True), (92, 64, True),
    (34, 66, True), (110, 44, True), (58, 24, True),
    (26, 14, False), (68, 28, False), (86, 38, False),
    (46, 54, False), (104, 28, False), (18, 40, False),
    (72, 70, False),
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
    """Paint on plain floor only -- never overwrite lava, bridges, or special tiles."""
    if tiles[y][x].kind == "floor" and tiles[y][x].char in {".", "░"}:
        tiles[y][x] = tile


# ---------------------------------------------------------------------------
# Painter functions
# ---------------------------------------------------------------------------

def _paint_lava_channels(tiles):
    """Carve two diagonal lava channels across the obsidian field."""
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            ch1 = _in_channel(x, y, _ch1_x)
            ch2 = _in_channel(x, y, _ch2_x)
            if ch1 or ch2:
                cx = _ch1_x(y) if ch1 else _ch2_x(y)
                if abs(x - cx) <= 0.9:
                    tiles[y][x] = _LAVA_GLOW
                else:
                    tiles[y][x] = _LAVA


def _paint_bridges(tiles):
    """Place cooled-crust bridges where they actually cross the lava."""
    for y_row, x_lo, x_hi, ch_x_fn in _BRIDGES:
        for x in range(x_lo, x_hi + 1):
            if 0 <= y_row < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                tiles[y_row][x] = _COOLED_CRUST
                if y_row + 1 < CITY_HEIGHT:
                    tiles[y_row + 1][x] = _COOLED_CRUST


def _paint_landing_pad(tiles, theme):
    """Raised basalt landing platform on the NW shelf."""
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


def _h_road(tiles, x0, x1, y, tile):
    """Horizontal road segment."""
    for x in range(min(x0, x1), max(x0, x1) + 1):
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            _paint_cell(tiles, x, y, tile)


def _v_road(tiles, x, y0, y1, tile):
    """Vertical road segment."""
    for y in range(min(y0, y1), max(y0, y1) + 1):
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            _paint_cell(tiles, x, y, tile)


def _paint_north_roads(tiles, theme):
    """Roads in the northern half: collectors, bridge approaches, pad."""
    ew, ns = theme.road_ew, theme.road_ns
    # Main east-west collector below pad.
    _h_road(tiles, 8, 54, 28, ew)
    _h_road(tiles, 64, 112, 28, ew)
    # Pad to bridge at y=20.
    _v_road(tiles, 32, 22, 28, ns)
    _v_road(tiles, 33, 22, 28, ns)
    _v_road(tiles, 21, 22, 28, ns)
    _v_road(tiles, 22, 22, 28, ns)
    # Central bridge approach y=28 to y=40.
    _v_road(tiles, 58, 28, 40, ns)
    _v_road(tiles, 59, 28, 40, ns)
    # NE bridge approach y=18 to y=28.
    _v_road(tiles, 84, 18, 28, ns)
    _v_road(tiles, 85, 18, 28, ns)
    # East bridge approach y=28 to y=34.
    _v_road(tiles, 100, 28, 34, ns)
    _v_road(tiles, 101, 28, 34, ns)
    # NE approach to bar.
    _v_road(tiles, 100, 18, 28, ns)
    _v_road(tiles, 101, 18, 28, ns)


def _paint_south_roads(tiles, theme):
    """Roads in the southern half: collectors, bridge approaches."""
    ew, ns = theme.road_ew, theme.road_ns
    # South collector below channel 1.
    _h_road(tiles, 8, 48, 52, ew)
    _h_road(tiles, 84, 112, 52, ew)
    # SE bridge approach y=40 to y=55.
    _v_road(tiles, 78, 40, 55, ns)
    _v_road(tiles, 79, 40, 55, ns)
    # SW approach to bounties.
    _v_road(tiles, 17, 52, 55, ns)
    _v_road(tiles, 18, 52, 55, ns)
    # SE approach to depot.
    _v_road(tiles, 100, 52, 55, ns)
    _v_road(tiles, 101, 52, 55, ns)


def _paint_roads(tiles, theme):
    """Wide roads connecting buildings to bridges and to each other."""
    _paint_north_roads(tiles, theme)
    _paint_south_roads(tiles, theme)


def _paint_obsidian_variety(tiles):
    """Scatter scorch marks and cooled patches for texture."""
    import random
    rng = random.Random(42)
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and tiles[y][x].char == ".":
                if rng.random() < 0.04:
                    tiles[y][x] = _HEAT_MARKER


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
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if 0 <= ny < CITY_HEIGHT and 0 <= nx < CITY_WIDTH:
                            if tiles[ny][nx].char == "~" and tiles[ny][nx].fg[0] > 200:
                                if rng.random() < 0.12:
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
