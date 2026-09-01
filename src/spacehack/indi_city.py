"""Indi b -- patchwork farmland town under a warm amber sun.

The breadbasket of the North Arm: orderly crop plots in a patchwork
grid, hedgerow windbreaks as living fences, grain silos beside the
harvest road, and a crossroads market where the four institutions of
farm-town life converge. The calmest, wealthiest place on the arm --
grain goes out to Cygni's shipyards and credits come back.

Layout (160x100):

  * Landing apron -- west end; the spaceport sits just north of it.
  * Harvest road -- full-width spine carrying grain from the fields
    past the silos to the port.
  * Crossroads market -- central square where the lanes meet.
  * The Harvest tavern -- north edge, via a short south lane.
  * Merchants guild -- south edge (silos beside it), door on its
    NORTH side facing the harvest road.
  * Militia station -- east end, door on its NORTH side facing the
    patrol lane; the arm's quiet lawful presence.
  * Crop plots -- fallow / young / mature patches rotated across the
    east and south-west fields, separated by hedgerow windbreaks.
"""

from __future__ import annotations

from . import world
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
from .data.planets.themes import T, derive_theme


CITY_WIDTH = 160
CITY_HEIGHT = 100

# Golden-harvest variant of LUSH: warm tan ground, wheat-gold mature
# crops, soft green-gold hedges, deep amber accents echoing the K-type sun.
INDI_GOLD = derive_theme(
    floor=(200, 175, 120),
    grass=(168, 128, 64),
    accent=(255, 185, 95),
    tree=T("tree", "♣", (120, 170, 80), (52, 74, 40)),
    neon=T("neon", "*", (255, 200, 110), (66, 46, 18)),
)

# ---------------------------------------------------------------------------
# Building positions (footprints match the indi_*.layout assets)
# ---------------------------------------------------------------------------

_SPACEPORT_ORIGIN = (10, 30)    # 24x9 -> x 10..33,   y 30..38
_BAR_ORIGIN = (70, 16)          # 21x8 -> x 70..90,   y 16..23
_MERCHANTS_ORIGIN = (66, 66)    # 24x9 -> x 66..89,   y 66..74
_MILITIA_ORIGIN = (116, 62)     # 22x8 -> x 116..137, y 62..69

_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 12, _SPACEPORT_ORIGIN[1] + 8)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 7)
_MERCHANTS_DOOR = (_MERCHANTS_ORIGIN[0] + 12, _MERCHANTS_ORIGIN[1])  # north side
_MILITIA_DOOR = (_MILITIA_ORIGIN[0] + 10, _MILITIA_ORIGIN[1])  # north side

_PAD_X_LO, _PAD_X_HI = 12, 38
_PAD_Y_LO, _PAD_Y_HI = 44, 60

# Road bands: harvest-road spine plus the three door lanes.
_SPINE_YBAND = (48, 50)
_SPINE_XRANGE = (8, 140)
_BAR_LANE = (79, 81, 24, 47)      # x_lo, x_hi, y_lo, y_hi
_GUILD_LANE = (77, 79, 51, 64)
_PATROL_LANE = (125, 127, 51, 60)

_MARKET_X_LO, _MARKET_X_HI = 66, 92
_MARKET_Y_LO, _MARKET_Y_HI = 42, 56

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "indi_spaceport": world.Position(*_SPACEPORT_ORIGIN),
    "indi_bar": world.Position(*_BAR_ORIGIN),
    "indi_merchants": world.Position(*_MERCHANTS_ORIGIN),
    "indi_militia": world.Position(*_MILITIA_ORIGIN),
}

# ---------------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------------

_SILO = world.Tile(
    kind="city_building_wall", char="O", walkable=False,
    fg=(214, 186, 128), bg=(78, 62, 34),
    blocked_message="A grain silo blocks your path.",
)

# Grain silo clusters beside the harvest road and the guild hall.
_SILO_SPOTS: tuple[tuple[int, int], ...] = (
    (44, 45), (45, 45), (44, 46),
    (94, 53), (95, 53),
    (96, 78), (97, 78), (96, 79),
)

# Patchwork field canvas (x_lo, y_lo, x_hi, y_hi). Crops paint FIRST,
# so every man-made feature (roads, market, pad, buildings, bays)
# overwrites them -- the fields simply fill whatever ground is left.
_FIELD_REGION: tuple[int, int, int, int] = (3, 3, 156, 96)


def _in_bounds(x: int, y: int) -> bool:
    return 0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT


# ---------------------------------------------------------------------------
# Painters
# ---------------------------------------------------------------------------

def _paint_fields(tiles, theme) -> None:
    """Patchwork crop plots: fallow / young / mature rotation with
    hedgerow windbreaks on plot boundaries. Edge plots clip to the
    region so the fields run to the map frame."""
    rotation = (None, theme.grass_accent, theme.grass)
    plot_w, plot_h, gap = 15, 10, 2
    rx_lo, ry_lo, rx_hi, ry_hi = _FIELD_REGION
    for iy, py in enumerate(range(ry_lo, ry_hi, plot_h + gap)):
        for ix, px in enumerate(range(rx_lo, rx_hi, plot_w + gap)):
            crop = rotation[(ix + iy) % len(rotation)]
            for y in range(py, min(py + plot_h, ry_hi + 1)):
                for x in range(px, min(px + plot_w, rx_hi + 1)):
                    if tiles[y][x].kind == "floor" and crop is not None:
                        tiles[y][x] = crop
            # Windbreak on the plot's right edge.
            hedge_x = px + plot_w
            for y in range(py, min(py + plot_h, ry_hi + 1)):
                if _in_bounds(hedge_x, y) and tiles[y][hedge_x].kind == "floor":
                    tiles[y][hedge_x] = theme.tree


def _paint_road_cell(tiles, theme, x, y, mid_lane: bool) -> None:
    if not _in_bounds(x, y):
        return
    tiles[y][x] = theme.road_ew if mid_lane else theme.road_surface


def _paint_roads(tiles, theme) -> None:
    """Harvest-road spine plus one lane to each far building."""
    y_mid = (_SPINE_YBAND[0] + _SPINE_YBAND[1]) // 2
    for x in range(_SPINE_XRANGE[0], _SPINE_XRANGE[1] + 1):
        _paint_road_cell(tiles, theme, x, _SPINE_YBAND[0], False)
        _paint_road_cell(tiles, theme, x, y_mid, True)
        _paint_road_cell(tiles, theme, x, _SPINE_YBAND[1], False)
    for x_lo, x_hi, y_lo, y_hi in (_BAR_LANE, _GUILD_LANE, _PATROL_LANE):
        x_mid = (x_lo + x_hi) // 2
        for y in range(y_lo, y_hi + 1):
            _paint_road_cell(tiles, theme, x_lo, y, False)
            _paint_road_cell(tiles, theme, x_mid, y, True)
            _paint_road_cell(tiles, theme, x_hi, y, False)


def _paint_market_square(tiles, theme) -> None:
    """Open plaza at the crossroads -- the town's gathering point."""
    for y in range(_MARKET_Y_LO, _MARKET_Y_HI + 1):
        for x in range(_MARKET_X_LO, _MARKET_X_HI + 1):
            if _in_bounds(x, y) and tiles[y][x].kind != "road":
                tiles[y][x] = theme.plaza
    # Amber lanterns framing the square.
    for x, y in (
        (_MARKET_X_LO + 2, _MARKET_Y_LO + 1),
        (_MARKET_X_HI - 2, _MARKET_Y_LO + 1),
        (_MARKET_X_LO + 2, _MARKET_Y_HI - 1),
        (_MARKET_X_HI - 2, _MARKET_Y_HI - 1),
    ):
        if tiles[y][x].kind == "plaza":
            tiles[y][x] = theme.neon


def _paint_pad(tiles, theme) -> None:
    """Smooth landing apron under ships and terminals."""
    pad_tile = world.Tile(
        kind="landing_pad", char=" ", walkable=True,
        fg=(190, 205, 170), bg=(58, 70, 48),
    )
    for y in range(_PAD_Y_LO, _PAD_Y_HI + 1):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = pad_tile


def _paint_silos(tiles) -> None:
    """Silos may stand in open ground OR amid crops -- never on roads,
    pads, plazas, or approaches."""
    for x, y in _SILO_SPOTS:
        if _in_bounds(x, y) and tiles[y][x].kind in {"floor", "grass"}:
            tiles[y][x] = _SILO


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

_BAY_TILE = world.Tile(
    kind="transit_bay", char="=", walkable=True,
    fg=(0, 229, 255), bg=(30, 68, 92),
)


def build_indi_layout(spec, resolve_ship) -> world.GameMap:
    theme = _readable_city_theme(INDI_GOLD)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
    _paint_fields(tiles, theme)
    _paint_roads(tiles, theme)
    _paint_market_square(tiles, theme)
    _paint_pad(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk)
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
    )
    paint_transit_bays(
        game_map.tiles, spec, _BAY_TILE, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({
            "floor", "grass", "grass_accent", "plaza", "city_plaza",
            "sidewalk", "landing_pad",
        }),
        force_center=True,
    )
    _paint_silos(game_map.tiles)
    paint_roof_labels(game_map, stamps, "indi_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="indi_", default_layout_id="indi_farmland_grid",
    )
    add_showroom_ships(game_map, spec, resolve_ship)
    add_service_terminals(game_map, spec)
    return game_map


__all__ = ["build_indi_layout", "INDI_GOLD", "LANDMARK_ORIGINS"]
