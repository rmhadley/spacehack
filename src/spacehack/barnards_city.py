"""Barnard's Star b — "The Ember Deep", an underground mine colony.

A ring-and-spoke mining settlement carved into solid rock.  Three
concentric tunnel rings radiate from a central landing shaft.
Buildings are doors carved directly into the rock face with their
names inscribed horizontally above — no rectangle stamps.

Layout (120×100):
  * Central shaft — landing pad on the elevator deck (elevator).
  * Outer ring — spaceport door in the north wall.
  * Mid ring — The Ember cantina door, salvage depot door.
  * 6 radial haulage drifts connecting the three rings.
  * Ore vein accents (orange ░), barrel fires (○), work lights (*).
"""

from __future__ import annotations

import math

from . import world
from .city_layout import building_records, stamp_metadata
from .city_landmarks import CityLandmarkStamp
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
    fg=(160, 190, 220), bg=(50, 65, 85),
)
_ROCK_LABEL_FG = (235, 225, 200)
_ROCK_DOOR_FG = (180, 210, 255)

_DRIFT_ANGLES = tuple(math.radians(a) for a in (0, 60, 120, 180, 240, 300))

# ---------------------------------------------------------------------------
# Building door positions — carved directly into rock
# ---------------------------------------------------------------------------

# Each: (label_start_x, label_row_y, door_x, door_y, label_str)
_BUILDING_DEFS = (
    # Spaceport — above landing pad, south-facing door.
    (56, 38, 60, 40, "SPACEPORT"),
    # The Ember cantina — mid ring left, south-facing.
    (20, 45, 21, 47, "BAR"),
    # Salvage depot — outer ring right, south-facing.
    (98, 45, 100, 47, "DEPOT"),
)

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


def _paint_doors_in_rock(tiles):
    """Carve building doors directly into the rock wall and clear forecourts."""
    for start_x, label_y, door_x, door_y, _label_str in _BUILDING_DEFS:
        # Door tile — walkable, carved into rock wall.
        tiles[door_y][door_x] = world.Tile(
            kind="city_building_door", char="+", walkable=True,
            fg=_ROCK_DOOR_FG, bg=_SOLID_ROCK.bg,
        )
        # Clear a 3-wide corridor from the door south until we hit
        # walkable floor (the ring tunnel).  This connects the forecourt
        # to the nearest tunnel so the door is reachable.
        for fy in range(door_y + 1, CITY_HEIGHT):
            reached_open = False
            for fx in (door_x - 1, door_x, door_x + 1):
                if 0 <= fx < CITY_WIDTH:
                    t = tiles[fy][fx]
                    if t.walkable or t.kind != "city_building_wall":
                        reached_open = True
            for fx in (door_x - 1, door_x, door_x + 1):
                if 0 <= fx < CITY_WIDTH and 0 <= fy < CITY_HEIGHT:
                    t = tiles[fy][fx]
                    if t.kind == "city_building_wall":
                        tiles[fy][fx] = _ROCK_FLOOR
            if reached_open:
                break


def _paint_rock_inscriptions(tiles):
    """Carve each building's name horizontally into the rock above its door."""
    for start_x, label_y, door_x, door_y, label_str in _BUILDING_DEFS:
        for i, ch in enumerate(label_str):
            x = start_x + i
            if not (0 <= x < CITY_WIDTH and 0 <= label_y < CITY_HEIGHT):
                continue
            tile = tiles[label_y][x]
            if tile.kind == "city_building_wall":
                tiles[label_y][x] = world.Tile(
                    kind="city_building_wall", char=ch, walkable=False,
                    fg=_ROCK_LABEL_FG, bg=tile.bg,
                    blocked_message="Solid rock.",
                )


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


def _paint_acents(tiles, theme):
    _paint_ore_veins(tiles)
    _paint_barrel_fires(tiles)
    _paint_work_lights(tiles, theme)


def _paint_transit_bays(tiles, spec):
    """Place transit bay tiles and carve small alcoves so the station
    entity does not block the single-width ring tunnel."""
    bay_tile = world.Tile(
        kind="floor", char=".", walkable=True,
        fg=(140, 160, 180), bg=(70, 64, 58),
    )
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            tiles[y][x] = bay_tile
        # Carve a 3×3 alcove around the station so players can walk
        # past it even when the tunnel is only 1 cell tall.
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= ny < CITY_HEIGHT and 0 <= nx < CITY_WIDTH:
                    if tiles[ny][nx].kind == "city_building_wall":
                        tiles[ny][nx] = _ROCK_FLOOR


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_barnards_layout(spec, resolve_ship):
    """Build the Ember Deep's 120×100 underground mine colony."""
    theme = _readable_city_theme(DESERT)
    tiles = _base_tiles(theme)
    _paint_tunnels(tiles, theme)
    _paint_acents(tiles, theme)
    _paint_doors_in_rock(tiles)
    _paint_rock_inscriptions(tiles)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    _paint_transit_bays(game_map.tiles, spec)
    # Build fake stamps so building_records can find entrances.
    stamps = _make_door_stamps()
    _set_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


def _make_door_stamps():
    """Create CityLandmarkStamp entries for each building, keyed by its
    stamped-id so building_records() can cross-reference them."""
    stamps = {}
    for start_x, label_y, door_x, door_y, label_str in _BUILDING_DEFS:
        layout_id = "barnards_" + label_str.lower()
        origin = world.Position(start_x, label_y)
        stamp = CityLandmarkStamp(
            layout_id=layout_id,
            origin=origin,
            footprint=frozenset({(door_x, door_y)}),
            entrance=world.Position(door_x, door_y),
        )
        stamps[layout_id] = stamp
    return stamps


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


__all__ = ["build_barnards_layout"]