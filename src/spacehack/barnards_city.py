"""Barnard's Star b — "The Ember Deep", an underground mine colony.

A ring-and-spoke mining settlement carved into solid rock.  Three
concentric tunnel rings radiate from a central landing shaft, with
drifts connecting them like spokes.  Buildings are excavated chambers
cut directly into the rock face — no surface structures.  Ore-vein
accents, work lights, and barrel fires mark the junctions.

Layout (120×80):
  * Central shaft — landing pad on the elevator deck.
  * Outer ring (r≈45) — spaceport and shuttle bay chambers, miner shacks.
  * Mid ring (r≈30) — main thoroughfare, The Ember cantina, depot.
  * Inner ring (r≈15) — tight passage around the shaft, storage alcoves.
  * 6 radial haulage drifts connecting the three rings.
  * Solid rock mass (#) between rings — irregular edges, natural pillars.
  * Ore vein accents (▒, orange-red) at key junctions.
  * Work lights (*) and barrel fires (○) throughout.
"""

from __future__ import annotations

import math

from . import world
from .city_layout import (
    building_records,
    paint_roof_labels,
    stamp_city_assets,
    stamp_metadata,
)
from .data.planets import _readable_city_theme
from .data.planets.themes import DESERT


CITY_WIDTH = 120
CITY_HEIGHT = 80
_CENTER_X = 60
_CENTER_Y = 40

# Ring radii (in cells, roughly circular with small irregular perturbation).
_RING_INNER_R = 12
_RING_MID_R = 26
_RING_OUTER_R = 42

# Tunnel width.
_RING_WIDTH = 4
_DRIFT_WIDTH = 2

# ---------------------------------------------------------------------------
# Custom tiles — CP437-safe
# All entity-bearing tiles must have bg luma >= 60 (readability gate).
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
    fg=(240, 150, 60), bg=(38, 24, 14),
)
_WORK_LIGHT = world.Tile(
    kind="neon", char="*", walkable=True,
    fg=(200, 220, 255), bg=(30, 36, 46),
)
_LANDING_PAD = world.Tile(
    kind="floor", char=".", walkable=True,
    fg=(170, 165, 155), bg=(66, 60, 52),
)

# Spoke drift angles (radians from centre).  6 spokes at 60-degree intervals.
_DRIFT_ANGLES = tuple(math.radians(a) for a in (0, 60, 120, 180, 240, 300))

# ---------------------------------------------------------------------------
# Building origins
# ---------------------------------------------------------------------------

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "barnards_spaceport": world.Position(14, 24),
    "barnards_bar":       world.Position(64, 10),
    "barnards_depot":     world.Position(100, 48),
}

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _dist(x: int, y: int) -> float:
    return math.sqrt((x - _CENTER_X) ** 2 + (y - _CENTER_Y) ** 2)


def _in_ring(r: float, target_r: float, half_width: float) -> bool:
    return abs(r - target_r) <= half_width


def _on_drift(x: int, y: int, half_width: float) -> bool:
    """Check if (x,y) lies on any of the 6 radial drifts."""
    if _dist(x, y) > _RING_OUTER_R + 2:
        return False
    angle = math.atan2(y - _CENTER_Y, x - _CENTER_X)
    # Normalize to [0, 2π).
    if angle < 0:
        angle += 2 * math.pi
    # Perpendicular distance to each drift line.
    for a in _DRIFT_ANGLES:
        da = abs(angle - a)
        if da > math.pi:
            da = 2 * math.pi - da
        # At radius r, the chord distance = r * da.
        chord_dist = _dist(x, y) * da
        if chord_dist <= half_width:
            return True
    return False


# ---------------------------------------------------------------------------
# Painters
# ---------------------------------------------------------------------------

def _base_tiles(theme):
    """Fill the map with solid rock."""
    tiles = [[_SOLID_ROCK for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    return tiles


_PAD_X_LO, _PAD_X_HI = 52, 68
_PAD_Y_LO, _PAD_Y_HI = 35, 45


def _paint_tunnels(tiles, theme):
    """Carve ring tunnels and radial drifts from solid rock."""
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            r = _dist(x, y)
            # Three ring tunnels.
            if _in_ring(r, _RING_INNER_R, _RING_WIDTH / 2):
                tiles[y][x] = _ROCK_FLOOR
            elif _in_ring(r, _RING_MID_R, _RING_WIDTH / 2):
                tiles[y][x] = _ROCK_FLOOR
            elif _in_ring(r, _RING_OUTER_R, _RING_WIDTH / 2):
                tiles[y][x] = _ROCK_FLOOR
            # Radial drifts.
            if _on_drift(x, y, _DRIFT_WIDTH / 2):
                if tiles[y][x].kind == "city_building_wall":
                    tiles[y][x] = _ROCK_FLOOR

    # Carve the landing pad shaft (rectangular void in centre).
    for y in range(_PAD_Y_LO, _PAD_Y_HI + 1):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = _LANDING_PAD

    # Carve building chambers — wide excavated cavities in the rock.
    _carve_chamber(tiles, 10, 20, 14, 14)   # spaceport
    _carve_chamber(tiles, 60, 6,  16, 12)   # The Ember cantina
    _carve_chamber(tiles, 96, 44, 18, 14)   # salvage depot


def _carve_chamber(tiles, x_lo, y_lo, w, h):
    """Carve a rectangular excavated chamber for a building."""
    for y in range(y_lo, y_lo + h):
        for x in range(x_lo, x_lo + w):
            if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                tiles[y][x] = _ROCK_FLOOR


def _paint_ore_veins(tiles):
    """Ore vein patches at key tunnel junctions."""
    _vein_positions = (
        (20, 22), (20, 58), (98, 22), (98, 58),
        (40, 6), (40, 74), (80, 6), (80, 74),
        (38, 16), (38, 64), (82, 16), (82, 64),
        (60, 14), (60, 66),
        (50, 30), (50, 50), (70, 30), (70, 50),
    )
    for x, y in _vein_positions:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= ny < CITY_HEIGHT and 0 <= nx < CITY_WIDTH:
                    if tiles[ny][nx].kind == "floor":
                        tiles[ny][nx] = _ORE_VEIN


def _paint_barrel_fires(tiles):
    """Barrel fires at drift-ring junctions."""
    _fire_positions = (
        (72, 8), (96, 28), (96, 52), (72, 72),
        (48, 72), (24, 52), (24, 28), (48, 8),
        (72, 20), (90, 38), (72, 56), (48, 56),
        (30, 38), (48, 20),
        (68, 14), (68, 20),
        (104, 52), (100, 56),
    )
    for x, y in _fire_positions:
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            if tiles[y][x].kind == "floor":
                tiles[y][x] = _BARREL_FIRE


def _paint_accents(tiles, theme):
    """Ore veins, barrel fires, work lights, and pad marker."""
    _paint_ore_veins(tiles)
    _paint_barrel_fires(tiles)
    _light_positions = (
        (60, 25), (60, 55), (34, 40), (86, 40),
        (44, 14), (76, 14), (44, 66), (76, 66),
        (20, 40), (100, 40), (60, 8), (60, 72),
        (60, 36), (60, 44),
    )
    for x, y in _light_positions:
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            if tiles[y][x].kind == "floor" and tiles[y][x].char != "○":
                tiles[y][x] = _WORK_LIGHT
    tiles[_CENTER_Y][_CENTER_X] = theme.neon


def _paint_building_forecourts(tiles, theme, spec):
    """Cleared forecourt outside each door."""
    for building in spec.buildings:
        dy = building.y_hi + 1 if not getattr(building, 'door_north', False) else building.y_lo - 1
        for x in range(building.door_x - 1, building.door_x + 2):
            if 0 <= x < CITY_WIDTH and 0 <= dy < CITY_HEIGHT:
                if tiles[dy][x].kind == "city_building_wall":
                    tiles[dy][x] = _ROCK_FLOOR


def _paint_transit_bays(tiles, spec):
    """Transit landing zones — cleared rock floor."""
    bay_tile = world.Tile(
        kind="floor", char=".", walkable=True,
        fg=(140, 160, 180), bg=(67, 59, 53),
    )
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            tiles[y][x] = bay_tile


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_barnards_layout(spec, resolve_ship):
    """Build the Ember Deep's 120×80 underground mine colony."""
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
    paint_roof_labels(game_map, stamps, "barnards_")
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