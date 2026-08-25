"""Tau Cet b -- canopy-clearing colony in an iridescent alien rainforest.

The colonists hacked a town out of a riotous biosphere and have been
losing ground gracefully ever since: survey gardens hybridized with the
native flora, and now vivid purple canopy presses in on every side of
the clearing. The town survives because the routes survive -- three
rough avenues and a perimeter path, all cut through the groves.

Layout (160x100):

  * Landing apron -- west side of the clearing; the spaceport sits
    just north of it.
  * Spine avenue -- east-west band from the apron to the east leg.
  * The Waypoint bar -- north edge, reached by a short south spur.
  * Merchants hall -- south-east, its door opening onto the southern
    perimeter path.
  * Perimeter path -- east leg + southern leg close the loop around
    the clearing so no route dead-ends.
  * Purple canopy walls ring the clearing and jut into it as lobes;
    glowing spore patches and walkable saplings texture the fern
    meadow between routes.
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
from .data.planets.themes import T, derive_theme


CITY_WIDTH = 160
CITY_HEIGHT = 100

# Full-riot alien palette: teal-green fern carpet, purple-violet canopy
# masses, hot magenta trees, cyan bioluminescent spore-light.
TC_CANOPY = derive_theme(
    floor=(112, 152, 128),
    grass=(148, 84, 198),
    accent=(255, 120, 220),
    tree=T("tree", "♣", (224, 120, 255), (56, 34, 88)),
    neon=T("neon", "*", (150, 255, 190), (28, 74, 52)),
)

# ---------------------------------------------------------------------------
# Building positions (footprints match the tc_*.layout assets)
# ---------------------------------------------------------------------------

_SPACEPORT_ORIGIN = (10, 28)    # 24x9 -> x 10..33,  y 28..36
_BAR_ORIGIN = (98, 20)          # 21x8 -> x 98..118, y 20..27
_MERCHANTS_ORIGIN = (94, 64)    # 24x9 -> x 94..117, y 64..72

_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 12, _SPACEPORT_ORIGIN[1] + 8)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 7)
_MERCHANTS_DOOR = (_MERCHANTS_ORIGIN[0] + 12, _MERCHANTS_ORIGIN[1] + 8)

_PAD_X_LO, _PAD_X_HI = 12, 38
_PAD_Y_LO, _PAD_Y_HI = 42, 58

# Route bands: spine avenue, bar spur, perimeter legs, west connector.
_ROAD_BANDS: tuple[tuple[str, int, int], ...] = (
    ("ew", 47, 49),   # spine, x 14..128
    ("ns", 107, 109), # bar spur, y 29..46
    ("ns", 126, 128), # east leg, y 50..73
    ("ew", 73, 75),   # south leg, x 96..127
    ("ns", 20, 22),   # spaceport forecourt connector, y 37..46
)
_SPINE_XRANGE = (14, 128)
_BAR_SPUR_YRANGE = (29, 46)
_EAST_LEG_YRANGE = (50, 73)
_SOUTH_LEG_XRANGE = (96, 127)
_WEST_CONN_YRANGE = (37, 46)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "tc_spaceport": world.Position(*_SPACEPORT_ORIGIN),
    "tc_bar": world.Position(*_BAR_ORIGIN),
    "tc_merchants": world.Position(*_MERCHANTS_ORIGIN),
}

# ---------------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------------

_CANOPY = world.Tile(
    kind="city_building_wall", char="♣", walkable=False,
    fg=(224, 120, 255), bg=(52, 30, 84),
    blocked_message="Dense alien canopy blocks your path.",
)

# Canopy groves: filled rects that only ever paint onto plain floor or
# fern texture, so roads, pad, sidewalks, bays, footprints, and door
# approaches can never be overwritten.
_GROVE_RECTS: tuple[tuple[int, int, int, int], ...] = (
    (2, 2, 156, 9),      # northern wall of canopy
    (2, 12, 4, 72),      # western wall (spaceport/pad keep their ground)
    (150, 14, 7, 70),    # eastern wall above/below the perimeter leg
    (2, 84, 156, 13),    # southern wall
    (44, 15, 28, 7),     # lobe between spaceport and bar approaches
    (130, 32, 16, 12),   # lobe pinching the spine's east end
    (40, 62, 24, 15),    # lobe between pad and merchants hall
    (12, 64, 22, 14),    # lobe south-west of the pad
    (58, 32, 16, 8),     # centre island north of the spine
    (60, 54, 16, 8),     # centre island south of the spine
    (86, 78, 8, 5),      # pocket grove by the merchants approach
)

# Glowing spore patches in the fern meadow (fixed, off-route cells).
_SPORE_SPOTS: tuple[tuple[int, int], ...] = (
    (40, 28), (50, 22), (92, 17), (134, 47), (142, 62),
    (44, 82), (72, 80), (122, 80), (88, 58), (58, 68),
)


# ---------------------------------------------------------------------------
# Painters
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


def _paint_scrub(tiles, theme) -> None:
    """Fern-carpet texture across open meadow -- sparse enough to read."""
    from .engine import seeded_rng

    rng = seeded_rng(11, "tc_fern")
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and rng.random() < 0.08:
                tiles[y][x] = theme.grass_accent


def _paint_roads(tiles, theme) -> None:
    """Spine, spur, and perimeter legs -- one connected route network."""
    surface = theme.road_surface
    for kind, lo, hi in _ROAD_BANDS:
        lane = theme.road_ew if kind == "ew" else theme.road_ns
        mid = (lo + hi) // 2
        if kind == "ew":
            x_lo, x_hi = (
                _SPINE_XRANGE if hi == 49 else _SOUTH_LEG_XRANGE
            )
            for x in range(x_lo, x_hi + 1):
                tiles[mid][x] = lane
                tiles[lo][x] = surface
                tiles[hi][x] = surface
        else:
            y_lo, y_hi = {
                108: _BAR_SPUR_YRANGE,
                127: _EAST_LEG_YRANGE,
                21: _WEST_CONN_YRANGE,
            }[mid]
            for y in range(y_lo, y_hi + 1):
                tiles[y][mid] = lane
                tiles[y][lo] = surface
                tiles[y][hi] = surface


def _paint_pad(tiles, theme) -> None:
    """Smooth landing apron under ships and terminals -- no dot noise."""
    pad_tile = world.Tile(
        kind="landing_pad", char=" ", walkable=True,
        fg=(170, 210, 190), bg=(40, 72, 64),
    )
    for y in range(_PAD_Y_LO, _PAD_Y_HI + 1):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = pad_tile


def _in_bounds(x: int, y: int) -> bool:
    return 0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT


def _paint_one_grove(tiles, x, y, w, h) -> None:
    for by in range(y, y + h):
        for bx in range(x, x + w):
            if not _in_bounds(bx, by):
                continue
            if tiles[by][bx].kind not in {"floor", "grass_accent"}:
                continue
            tiles[by][bx] = _CANOPY


def _paint_groves(tiles) -> None:
    for x, y, w, h in _GROVE_RECTS:
        _paint_one_grove(tiles, x, y, w, h)


def _paint_spores(tiles, theme) -> None:
    for x, y in _SPORE_SPOTS:
        if _in_bounds(x, y) and tiles[y][x].kind == "floor":
            tiles[y][x] = theme.neon


def _paint_saplings(tiles, theme) -> None:
    """Walkable young trees scattered through the meadow -- the jungle's
    next advance."""
    from .engine import seeded_rng

    rng = seeded_rng(23, "tc_sapling")
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and rng.random() < 0.03:
                tiles[y][x] = theme.tree


def _paint_forecourts(tiles, theme, spec) -> None:
    """Give each door a three-cell sidewalk forecourt on its exit side."""
    for building in spec.buildings:
        y = building.y_hi + 1
        for x in range(building.door_x - 1, building.door_x + 2):
            if _in_bounds(x, y):
                t = tiles[y][x]
                if t.kind == "floor":
                    tiles[y][x] = theme.sidewalk


def _paint_transit_bays(tiles, spec) -> None:
    """Paint a smooth floor bay under and around each transit stop."""
    bay = world.Tile(
        kind="floor", char=" ", walkable=True,
        fg=(150, 190, 168), bg=(52, 78, 66),
    )
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if _in_bounds(nx, ny) and tiles[ny][nx].kind in {"floor", "grass_accent"}:
                    tiles[ny][nx] = bay


# ---------------------------------------------------------------------------
# Metadata + service entities
# ---------------------------------------------------------------------------

def _set_metadata(game_map, spec, stamps) -> None:
    game_map.city_layout_id = spec.city_layout_id or "tc_canopy_clearing"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "tc_")


def _add_service_entities(game_map, spec, resolve_ship) -> None:
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
        ("=", "Trade Terminal", -6, "trade_terminal", (140, 230, 255)),
        ("%", "Mechanic Terminal", -2, "mech_terminal", (210, 220, 130)),
        ("A", "Armory Terminal", 2, "armory_terminal", (255, 175, 105)),
    )
    for char, name, dx, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg,
            pos=world.Position(berth.x + dx, berth.y + 3),
            name=name, **{flag: True},
        ))


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_tc_layout(spec, resolve_ship) -> world.GameMap:
    theme = _readable_city_theme(TC_CANOPY)
    tiles = _base_tiles(theme)
    _paint_scrub(tiles, theme)
    _paint_roads(tiles, theme)
    _paint_pad(tiles, theme)
    _paint_forecourts(tiles, theme, spec)
    _paint_transit_bays(tiles, spec)
    _paint_groves(tiles)
    _paint_spores(tiles, theme)
    _paint_saplings(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk)
    paint_roof_labels(game_map, stamps, "tc_")
    _set_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


__all__ = ["build_tc_layout", "LANDMARK_ORIGINS", "TC_CANOPY"]
