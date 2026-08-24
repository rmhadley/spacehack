"""Barnard's Star b — "The Ember Deep", an underground mine colony.

A ring-and-spoke mining settlement carved into solid rock.  Three
concentric tunnel rings radiate from a central landing shaft, with
haulag drifts connecting them like spokes.  Buildings are doors cut
directly into the rock face with their names inscribed vertically
above them — no rectangle buildings, no surface structures.

Layout (120×100):
  * Central shaft — landing pad on the elevator deck.
  * Outer ring — spaceport door carved into the north wall.
  * Mid ring — The Ember bar door, mid-ring left-side alcove.
  * Inner ring — tight passage around the shaft, storage alcoves.
  * 6 radial haulage drifts connecting the three rings.
  * Solid rock mass (#) between rings.
  * Ore vein accents (orange ░), barrel fires (○), work lights (*).
"""

from __future__ import annotations

import math

from . import world
from .city_layout import building_records, stamp_city_assets, stamp_metadata
from .data.planets import _readable_city_theme
from .data.planets.themes import DESERT


CITY_WIDTH = 120
CITY_HEIGHT = 100
_CENTER_X = 60
_CENTER_Y = 50

_RING_INNER_R = 16
_RING_MID_R = 32
_RING_OUTER_R = 48

_RING_WIDTH = 4
_DRIFT_WIDTH = 2

# ---------------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------------

_SOLID_ROCK = world.Tile(
    kind="city_building_wall", char="#", walkable=False,
    fg=(75, 68, 62), bg=(22, 20, 18),
    blocked_message="Solid rock -- you'd need a mining laser to get through.",
)
_ROCK_FLOOR = world.Tile(
    kind="floor", char=".", walkable=True,
    fg=(140, 125, 110), bg=(67, 60, 50),
)
_ORE_VEIN = world.Tile(
    kind="floor", char="░", walkable=True,
    fg=(210, 120, 55), bg=(68, 50, 38),
)
_BARREL_FIRE = world.Tile(
    kind="neon", char="○", walkable=True,
    fg=(240, 150, 60), bg=(42, 28, 18),
)
_WORK_LIGHT = world.Tile(
    kind="neon", char="*", walkable=True,
    fg=(200, 220, 255), bg=(30, 36, 46),
)
_LANDING_PAD = world.Tile(
    kind="floor", char=".", walkable=True,
    fg=(170, 165, 155), bg=(68, 62, 54),
)
_ROCK_LABEL_FG = (230, 220, 195)

_DRIFT_ANGLES = tuple(math.radians(a) for a in (0, 60, 120, 180, 240, 300))

# ---------------------------------------------------------------------------
# Building origins — door-niche positions in rock walls
# ---------------------------------------------------------------------------

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "barnards_spaceport": world.Position(42, 0),
    "barnards_bar":       world.Position(20, 47),
    "barnards_depot":     world.Position(99, 47),
}

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _dist(x: int, y: int) -> float:
    return math.sqrt((x - _CENTER_X) ** 2 + (y - _CENTER_Y) ** 2)


def _in_ring(r: float, target_r: float, half_width: float) -> bool:
    return abs(r - target_r) <= half_width


def _on_drift(x: int, y: int, half_width: float) -> bool:
    if _dist(x, y) > _RING_OUTER_R + 2:
        return False
    angle = math.atan2(y - _CENTER_Y, x - _CENTER_X)
    if angle < 0:
        angle += 2 * math.pi
    for a in _DRIFT_ANGLES:
        da = abs(angle - a)
        if da > math.pi:
            da = 2 * math.pi - da
        chord_dist = _dist(x, y) * da
        if chord_dist <= half_width:
            return True
    return False


# ---------------------------------------------------------------------------
# Painters
# ---------------------------------------------------------------------------

def _base_tiles(theme):
    tiles = [[_SOLID_ROCK for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    return tiles


_PAD_X_LO, _PAD_X_HI = 51, 69
_PAD_Y_LO, _PAD_Y_HI = 41, 59


def _paint_tunnels(tiles, theme):
    """Carve ring tunnels, drifts, and the landing pad from solid rock."""
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            r = _dist(x, y)
            if _in_ring(r, _RING_INNER_R, _RING_WIDTH / 2):
                tiles[y][x] = _ROCK_FLOOR
            elif _in_ring(r, _RING_MID_R, _RING_WIDTH / 2):
                tiles[y][x] = _ROCK_FLOOR
            elif _in_ring(r, _RING_OUTER_R, _RING_WIDTH / 2):
                tiles[y][x] = _ROCK_FLOOR
            if _on_drift(x, y, _DRIFT_WIDTH / 2):
                if tiles[y][x].kind == "city_building_wall":
                    tiles[y][x] = _ROCK_FLOOR

    # Landing pad — the elevator deck at centre.
    for y in range(_PAD_Y_LO, _PAD_Y_HI + 1):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = _LANDING_PAD

    # Wide excavated plazas at key ring junctions.
    _carve_plaza(tiles, 78, 34)   # right-side mid-ring plaza (depot area)
    _carve_plaza(tiles, 26, 60)   # left-side lower plaza
    _carve_plaza(tiles, 60, 20)   # top mid-ring plaza (bar area)


def _carve_plaza(tiles, cx, cy):
    """Carve a 7×5 open area at a ring junction."""
    for y in range(cy - 2, cy + 3):
        for x in range(cx - 3, cx + 4):
            if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                if tiles[y][x].kind == "city_building_wall":
                    tiles[y][x] = _ROCK_FLOOR


def _paint_ore_veins(tiles):
    _vein_positions = (
        (20, 28), (20, 72), (98, 28), (98, 72),
        (40, 8), (40, 92), (80, 8), (80, 92),
        (38, 20), (38, 80), (82, 20), (82, 80),
        (60, 18), (60, 82),
        (50, 36), (50, 64), (70, 36), (70, 64),
        (34, 44), (86, 44), (34, 56), (86, 56),
    )
    for x, y in _vein_positions:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= ny < CITY_HEIGHT and 0 <= nx < CITY_WIDTH:
                    if tiles[ny][nx].kind == "floor":
                        tiles[ny][nx] = _ORE_VEIN


def _paint_barrel_fires(tiles):
    _fire_positions = (
        (72, 10), (98, 34), (98, 64), (72, 90),
        (48, 90), (24, 64), (24, 34), (48, 10),
        (72, 24), (92, 48), (72, 72), (48, 72),
        (28, 48), (48, 24),
        (74, 36), (80, 50), (30, 60), (36, 50),
    )
    for x, y in _fire_positions:
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            if tiles[y][x].kind == "floor":
                tiles[y][x] = _BARREL_FIRE


def _paint_work_lights(tiles, theme):
    _light_positions = (
        (60, 30), (60, 70), (34, 50), (86, 50),
        (44, 18), (76, 18), (44, 82), (76, 82),
        (20, 50), (100, 50), (60, 10), (60, 90),
        (60, 42), (60, 58),
    )
    for x, y in _light_positions:
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            if tiles[y][x].kind == "floor" and tiles[y][x].char != "○":
                tiles[y][x] = _WORK_LIGHT
    tiles[_CENTER_Y][_CENTER_X] = theme.neon


def _paint_accents(tiles, theme):
    _paint_ore_veins(tiles)
    _paint_barrel_fires(tiles)
    _paint_work_lights(tiles, theme)


def _paint_building_forecourts(tiles, theme, spec):
    """Clear 3 cells below each door so players can reach it."""
    for building in spec.buildings:
        dy = building.y_hi + 1
        for x in range(building.door_x - 1, building.door_x + 2):
            if 0 <= x < CITY_WIDTH and 0 <= dy < CITY_HEIGHT:
                if tiles[dy][x].kind == "city_building_wall":
                    tiles[dy][x] = _ROCK_FLOOR


def _paint_transit_bays(tiles, spec):
    bay_tile = world.Tile(
        kind="floor", char=".", walkable=True,
        fg=(140, 160, 180), bg=(70, 64, 58),
    )
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            tiles[y][x] = bay_tile


# ---------------------------------------------------------------------------
# Rock-wall labels (horizontal inscriptions in the rock above doors)
# ---------------------------------------------------------------------------

def _paint_rock_inscriptions(game_map, stamps, prefix):
    """Carve each building's name horizontally into the rock wall above its door.

    Works like paint_roof_labels but inscribes into solid rock (#) instead
    of roof tiles.  The label sits 2 rows above the door, centred.
    """
    for layout_id, stamp in stamps.items():
        label = layout_id.removeprefix(prefix).upper()
        if label == "PLAZA" or stamp.entrance is None:
            continue
        dx, dy = stamp.entrance.x, stamp.entrance.y
        row = dy - 3  # 2 rows of rock buffer above the door
        start_x = dx - len(label) // 2
        for i, ch in enumerate(label):
            x = start_x + i
            if not (0 <= x < CITY_WIDTH and 0 <= row < CITY_HEIGHT):
                continue
            tile = game_map.tiles[row][x]
            if tile.char == "#" and tile.kind == "city_building_wall":
                game_map.tiles[row][x] = world.Tile(
                    kind="city_building_wall", char=ch, walkable=False,
                    fg=_ROCK_LABEL_FG, bg=tile.bg,
                    blocked_message="Solid rock.",
                )


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_barnards_layout(spec, resolve_ship):
    """Build the Ember Deep's 120×100 underground mine colony."""
    theme = _readable_city_theme(DESERT)
    tiles = _base_tiles(theme)
    _paint_tunnels(tiles, theme)
    _paint_accents(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    _paint_building_forecourts(game_map.tiles, theme, spec)
    _paint_transit_bays(game_map.tiles, spec)
    _paint_rock_inscriptions(game_map, stamps, "barnards_")
    _set_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


def _set_metadata(game_map, spec, stamps):
    game_map.city_layout_id = spec.city_layout_id or "barnards_mine_colony"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "barnards_")


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
        ("=", "Trade Terminal", -7, "trade_terminal", (100, 220, 255)),
        ("%", "Mechanic Terminal", -3, "mech_terminal", (210, 220, 110)),
        ("A", "Armory Terminal", 1, "armory_terminal", (255, 165, 85)),
    )
    for char, name, dx, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg,
            pos=world.Position(berth.x + dx, berth.y + 2),
            name=name, **{flag: True},
        ))


__all__ = ["build_barnards_layout", "LANDMARK_ORIGINS"]