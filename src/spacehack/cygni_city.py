"""Cygni b — a dry temperate shipyard colony on the North Arm.

The first stop out of Sol: hulls for the North Arm trade are forged here,
and the port never sleeps. A wide haul road splits the colony down the
middle — portside to the west, the forge complex to the east.

Layout (160×100):
  * spaceport, landing pad, and merchants on the port side (west).
  * dock market stalls along the haul road.
  * two massive hull-forge factories and a plate works on the east side.
  * The Anvil bar tucked between the forges.
  * militia outpost facing the haul road.
  * worker-row shacks south of the factories.
  * yard workers moving between forge entrances and the haul road.
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
from .data.planets.themes import DESERT


CITY_WIDTH = 160
CITY_HEIGHT = 100

# ---------------------------------------------------------------------------
# Placement constants — port side (west of haul road)
# ---------------------------------------------------------------------------

_SPACEPORT_X_LO, _SPACEPORT_X_HI = 6, 29
_SPACEPORT_Y_LO, _SPACEPORT_Y_HI = 10, 20

_PAD_X_LO, _PAD_X_HI = 32, 47
_PAD_Y_LO, _PAD_Y_HI = 10, 18

_MERCH_X_LO, _MERCH_X_HI = 6, 25
_MERCH_Y_LO, _MERCH_Y_HI = 48, 58

_DOCK_MARKET_X_LO, _DOCK_MARKET_X_HI = 30, 55
_DOCK_MARKET_Y_LO, _DOCK_MARKET_Y_HI = 48, 56

# ---------------------------------------------------------------------------
# Placement constants — forge district (east of haul road)
# ---------------------------------------------------------------------------

_HULL_BAY_X_LO, _HULL_BAY_X_HI = 66, 118
_HULL_BAY_Y_LO, _HULL_BAY_Y_HI = 6, 38

_FRAME_X_LO, _FRAME_X_HI = 66, 110
_FRAME_Y_LO, _FRAME_Y_HI = 48, 68

_PLATE_X_LO, _PLATE_X_HI = 120, 156
_PLATE_Y_LO, _PLATE_Y_HI = 14, 38

_BAR_X_LO, _BAR_X_HI = 112, 132
_BAR_Y_LO, _BAR_Y_HI = 48, 57

_MILITIA_X_LO, _MILITIA_X_HI = 122, 144
_MILITIA_Y_LO, _MILITIA_Y_HI = 74, 84

# ---------------------------------------------------------------------------
# Haul road
# ---------------------------------------------------------------------------

_HAUL_X_LO, _HAUL_X_HI = 58, 62
_HAUL_Y_LO, _HAUL_Y_HI = 4, 94

# ---------------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------------

_FORGE_FLOOR = world.Tile(
    kind="floor", char="▓", walkable=True,
    fg=(160, 90, 50), bg=(40, 22, 12),
)
_FORGE_STACK = world.Tile(
    kind="city_building_wall", char="●", walkable=False,
    fg=(200, 60, 30), bg=(40, 22, 12),
    blocked_message="The forge stack blocks your path.",
)
_FORGE_WALL = world.Tile(
    kind="city_building_wall", char="#", walkable=False,
    fg=(120, 70, 40), bg=(32, 16, 10),
    blocked_message="The foundry wall blocks your path.",
)
_FORGE_ROOF = world.Tile(
    kind="city_building_wall", char="=", walkable=False,
    fg=(170, 120, 60), bg=(48, 28, 14),
    blocked_message="The foundry wall blocks your path.",
)
_CARGO_PALLET = world.Tile(
    kind="plaza", char="○", walkable=True,
    fg=(140, 100, 60), bg=(100, 62, 38),
)
_WORK_LIGHT = world.Tile(
    kind="neon", char="*", walkable=True,
    fg=(255, 180, 60), bg=(40, 20, 8),
)
_BARREL_FIRE = world.Tile(
    kind="plaza", char="○", walkable=True,
    fg=(235, 145, 65), bg=(52, 30, 16),
)

# Shack colours — adobe and corrugated steel.
_SHACK_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((140, 100, 70), (50, 30, 18), (180, 140, 100), (60, 40, 25)),
    ((160, 110, 75), (55, 32, 20), (190, 150, 110), (65, 42, 28)),
    ((130, 90, 60), (45, 28, 16), (170, 130, 90), (55, 35, 22)),
)

_SHACKS: tuple[tuple[int, int, int, int, int], ...] = (
    # West side — port worker row.
    (4, 64, 6, 5, 0), (12, 66, 5, 4, 1), (20, 64, 6, 5, 2),
    (30, 62, 7, 5, 0), (42, 64, 5, 4, 1),
    # East side — forge worker row.
    (66, 72, 6, 5, 2), (74, 74, 5, 4, 0), (82, 72, 7, 5, 1),
    (94, 74, 6, 5, 2), (104, 72, 5, 4, 0), (112, 74, 7, 5, 1),
    (126, 86, 6, 5, 2), (136, 88, 5, 4, 0),
    # North-east corner.
    (146, 60, 6, 5, 1), (148, 50, 5, 4, 2),
)

# Yard details — pallets, lights, barrel fires.
_YARD_DETAILS: tuple[tuple[int, int, str], ...] = (
    # Hull Bay yard.
    (62, 8, "light"), (60, 20, "pallet"), (62, 30, "pallet"),
    (120, 10, "light"), (122, 24, "pallet"),
    # Frame Foundry yard.
    (62, 50, "light"), (62, 58, "pallet"), (62, 64, "pallet"),
    (112, 60, "light"),
    # Plate Works yard.
    (158, 22, "light"), (158, 30, "pallet"),
    # Port yard.
    (4, 22, "pallet"), (50, 22, "light"), (50, 24, "pallet"),
    # Dock market.
    (56, 50, "light"), (56, 54, "pallet"),
    # Southern edge.
    (4, 88, "light"), (20, 90, "pallet"), (60, 86, "light"),
    (150, 94, "pallet"),
)


LANDMARK_ORIGINS: dict[str, world.Position] = {
    "cygni_spaceport": world.Position(_SPACEPORT_X_LO, _SPACEPORT_Y_LO),
    "cygni_bar": world.Position(_BAR_X_LO, _BAR_Y_LO),
    "cygni_merchants": world.Position(_MERCH_X_LO, _MERCH_Y_LO),
    "cygni_militia": world.Position(_MILITIA_X_LO, _MILITIA_Y_LO),
}


# ---------------------------------------------------------------------------
# Tile helpers
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
    if tiles[y][x].kind in {"floor", "grass"}:
        tiles[y][x] = tile


def _paint_patch(tiles, theme, x0, y0, w, h, tile):
    """Paint a solid rectangle on open ground only."""
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            if tiles[y][x].kind in {"floor", "grass"}:
                tiles[y][x] = tile


# ---------------------------------------------------------------------------
# Painter functions
# ---------------------------------------------------------------------------

def _paint_haul_road(tiles, theme):
    """Wide road band splitting the colony portside from the forge district."""
    # Road surface band.
    for y in range(_HAUL_Y_LO, _HAUL_Y_HI + 1):
        for x in range(_HAUL_X_LO, _HAUL_X_HI + 1):
            tiles[y][x] = theme.road_surface
    # Centre dash line.
    for y in range(_HAUL_Y_LO, _HAUL_Y_HI + 1, 2):
        tiles[y][_HAUL_X_LO + 1] = theme.road_ew
        tiles[y][_HAUL_X_HI - 1] = theme.road_ew
    # Sidewalks flanking the road.
    for y in range(_HAUL_Y_LO, _HAUL_Y_HI + 1):
        tiles[y][_HAUL_X_LO - 1] = theme.sidewalk
        tiles[y][_HAUL_X_HI + 1] = theme.sidewalk
    # Cross roads — EW branches at key rows.
    for row in (13, 28, 48, 60, 80):
        for x in range(_HAUL_X_LO, _HAUL_X_HI + 1):
            tiles[row][x] = theme.road_ew


def _paint_landing_pad(tiles, theme):
    """Landing pad between spaceport and the haul road."""
    pad_tile = replace(theme.landing_pad, char=" ")
    for y in range(_PAD_Y_LO, _PAD_Y_HI + 1):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = pad_tile


def _paint_forge(tiles, x_lo, x_hi, y_lo, y_hi, name=""):
    """Paint one non-enterable forge factory: walls, roof, interior, stacks."""
    # Walls.
    for y in range(y_lo, y_hi + 1):
        tiles[y][x_lo] = _FORGE_WALL
        tiles[y][x_hi] = _FORGE_WALL
    for x in range(x_lo + 1, x_hi):
        tiles[y_lo][x] = _FORGE_WALL
        tiles[y_hi][x] = _FORGE_WALL
    # Interior forge floor with roof strips.
    for y in range(y_lo + 1, y_hi):
        for x in range(x_lo + 1, x_hi):
            if y % 4 in (0, 1):
                tiles[y][x] = _FORGE_ROOF
            else:
                tiles[y][x] = _FORGE_FLOOR
    # Stacks on the roof.
    for sx in range(x_lo + 4, x_hi - 2, 6):
        for sy in range(y_lo - 2, y_lo):
            tiles[sy][sx] = _FORGE_STACK
    # Roof label.
    if name and x_hi - x_lo >= 10:
        label_x = (x_lo + x_hi - len(name)) // 2
        label_y = y_lo + 1
        for i, ch in enumerate(name):
            cx = label_x + i
            if x_lo < cx < x_hi:
                tiles[label_y][cx] = _FORGE_STACK


def _paint_dock_market(tiles, theme):
    """Dock market — paved plaza with stalls along the haul road."""
    from dataclasses import replace
    # Paved ground.
    for y in range(_DOCK_MARKET_Y_LO, _DOCK_MARKET_Y_HI + 1):
        for x in range(_DOCK_MARKET_X_LO, _DOCK_MARKET_X_HI + 1):
            tiles[y][x] = theme.plaza
    # Stalls — darker blocks on the plaza floor.
    stall = replace(theme.decor, char="▒", bg=theme.plaza.bg)
    for x in range(_DOCK_MARKET_X_LO + 2, _DOCK_MARKET_X_HI - 1, 3):
        tiles[_DOCK_MARKET_Y_LO + 1][x] = stall
        tiles[_DOCK_MARKET_Y_HI - 1][x] = stall
    # Centre beacon.
    cx = (_DOCK_MARKET_X_LO + _DOCK_MARKET_X_HI) // 2
    cy = (_DOCK_MARKET_Y_LO + _DOCK_MARKET_Y_HI) // 2
    tiles[cy][cx] = _WORK_LIGHT


def _paint_yard_details(tiles):
    """Scatter cargo pallets, work lights, and barrel fires in the yards."""
    for x, y, kind in _YARD_DETAILS:
        if tiles[y][x].kind in {"floor", "grass"}:
            if kind == "light":
                tiles[y][x] = _WORK_LIGHT
            elif kind == "pallet":
                tiles[y][x] = _CARGO_PALLET


def _paint_worker_row(tiles):
    """Scatter adobe/steel worker shacks."""
    for x, y, w, h, scheme in _SHACKS:
        if not all(
            tiles[by][bx].kind in {"floor", "grass"}
            for by in range(y, y + h)
            for bx in range(x, x + w)
        ):
            continue
        wall_fg, wall_bg, roof_fg, roof_bg = _SHACK_SCHEMES[scheme]
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


def _paint_grass_patches(tiles, theme):
    """Sparse dry grass patches for variety on open floor."""
    import random
    rng = random.Random(12)
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and rng.random() < 0.04:
                tiles[y][x] = theme.grass


def _paint_building_forecourts(tiles, theme, spec):
    """Cleared forecourt south of each door."""
    for building in spec.buildings:
        y = building.y_hi + 1
        for x in range(building.door_x - 1, building.door_x + 2):
            if 0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT:
                tiles[y][x] = theme.sidewalk


def _paint_transit_bays(tiles, spec):
    """Dedicated transit landing zones."""
    bay_tile = world.Tile(
        kind="floor", char=" ", walkable=True,
        fg=(155, 120, 80), bg=(90, 55, 30),
    )
    for station in spec.transit_stations:
        tiles[station.pos.y][station.pos.x] = bay_tile


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_cygni_layout(spec, resolve_ship):
    """Build Cygni b's 160×100 port-and-forge shipyard colony."""
    theme = _readable_city_theme(DESERT)
    tiles = _base_tiles(theme)
    _paint_grass_patches(tiles, theme)
    _paint_haul_road(tiles, theme)
    _paint_landing_pad(tiles, theme)
    _paint_forge(tiles, _HULL_BAY_X_LO, _HULL_BAY_X_HI,
                _HULL_BAY_Y_LO, _HULL_BAY_Y_HI, name="HULL BAY ALPHA")
    _paint_forge(tiles, _FRAME_X_LO, _FRAME_X_HI,
                _FRAME_Y_LO, _FRAME_Y_HI, name="FRAME FOUNDRY")
    _paint_forge(tiles, _PLATE_X_LO, _PLATE_X_HI,
                _PLATE_Y_LO, _PLATE_Y_HI, name="PLATE WORKS")
    _paint_dock_market(tiles, theme)
    _paint_yard_details(tiles)
    _paint_worker_row(tiles)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    _paint_building_forecourts(game_map.tiles, theme, spec)
    _paint_transit_bays(game_map.tiles, spec)
    paint_roof_labels(game_map, stamps, "cygni_")
    _set_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


def _set_metadata(game_map, spec, stamps):
    game_map.city_layout_id = spec.city_layout_id or "cygni_shipyard_colony"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "cygni_")


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
        ("=", "Trade Terminal", -8, "trade_terminal", (100, 220, 255)),
        ("%", "Mechanic Terminal", -4, "mech_terminal", (210, 220, 110)),
        ("A", "Armory Terminal", 0, "armory_terminal", (255, 165, 85)),
    )
    for char, name, dx, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg,
            pos=world.Position(berth.x + dx, berth.y + 3),
            name=name, **{flag: True},
        ))


__all__ = ["build_cygni_layout", "LANDMARK_ORIGINS"]