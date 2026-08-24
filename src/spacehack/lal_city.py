"""Lalande 21185 b — Deadfall, the blacked-out squatter colony.

The Requiem's hull is embedded in the ice crust at an angle — the
settlement is built into the frozen wreck.  Spaceport and depot sit
in the upper decks near the surface; the bar glows amber through
frosted viewports deep in the ice.  The docking ring marks the crew's
grave, lit by reclamation lanterns.  Salvage gantries and scrap piles
ring the hull.  No charter, no law but the cold.

Layout (140×100):
  * The Requiem's spine — diagonal rusted hull, half-buried.
  * spaceport and depot in the upper deck section.
  * bar — The Deep Freeze — deep in the ice on the lower deck.
  * bounty office — weather-sealed shack, north edge.
  * docking ring — circle in the terrain, south of the hull.
  * salvage yard — gantries, scrap, reclamation fires.
  * reclamation lanterns — warm fire amid dark ice.
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
from .data.planets.themes import ICE


CITY_WIDTH = 140
CITY_HEIGHT = 100

# ---------------------------------------------------------------------------
# Placement constants
# ---------------------------------------------------------------------------

_SPACEPORT_X_LO, _SPACEPORT_X_HI = 8, 31
_SPACEPORT_Y_LO, _SPACEPORT_Y_HI = 8, 18

_DEPOT_X_LO, _DEPOT_X_HI = 90, 109
_DEPOT_Y_LO, _DEPOT_Y_HI = 10, 18

_BAR_X_LO, _BAR_X_HI = 56, 76
_BAR_Y_LO, _BAR_Y_HI = 56, 65

_BOUNTIES_X_LO, _BOUNTIES_X_HI = 8, 23
_BOUNTIES_Y_LO, _BOUNTIES_Y_HI = 72, 82

_PAD_X_LO, _PAD_X_HI = 34, 49
_PAD_Y_LO, _PAD_Y_HI = 8, 16

# ---------------------------------------------------------------------------
# Custom tiles — CP437-safe glyphs
# ---------------------------------------------------------------------------

# The Requiem's hull — dark rusted plating.
_HULL_WALL = world.Tile(
    kind="city_building_wall", char="▓", walkable=False,
    fg=(140, 110, 90), bg=(38, 26, 20),
    blocked_message="The Requiem's hull plates block your path.",
)
# Hull interior deck — stripped, iced-over.
_HULL_FLOOR = world.Tile(
    kind="floor", char="▒", walkable=True,
    fg=(100, 120, 140), bg=(55, 62, 74),
)
# Frost crust — lighter ice patches.
_FROST_CRUST = world.Tile(
    kind="floor", char="░", walkable=True,
    fg=(180, 210, 230), bg=(60, 80, 100),
)
# Docking ring segment — circle of ice-crusted metal.
_DOCK_RING = world.Tile(
    kind="floor", char="●", walkable=True,
    fg=(120, 145, 170), bg=(52, 66, 80),
)
_DOCK_GRAVE = world.Tile(
    kind="floor", char="○", walkable=True,
    fg=(80, 100, 125), bg=(55, 62, 74),
)
# Salvage gantry — dark frame structure.
_GANTRY = world.Tile(
    kind="city_building_wall", char="|", walkable=False,
    fg=(110, 116, 128), bg=(28, 34, 42),
    blocked_message="The salvage gantry blocks your path.",
)
# Scrap pile — salvage debris.
_SCRAP_HEAP = world.Tile(
    kind="plaza", char="░", walkable=True,
    fg=(130, 110, 90), bg=(70, 60, 52),
)
# Reclamation fire — warm orange glow amid the ice.
_RECLAMATION_FIRE = world.Tile(
    kind="plaza", char="○", walkable=True,
    fg=(235, 145, 65), bg=(34, 22, 14),
)
_WORK_LIGHT = world.Tile(
    kind="neon", char="*", walkable=True,
    fg=(200, 220, 255), bg=(28, 38, 52),
)
# Tool shed — scavenger lean-to.
_TOOL_ROOF = world.Tile(
    kind="city_building_wall", char="~", walkable=False,
    fg=(120, 140, 160), bg=(34, 44, 56),
    blocked_message="The tool shed wall blocks your path.",
)

# ---------------------------------------------------------------------------
# Hull geometry — the Requiem's spine, diagonal across the map
# ---------------------------------------------------------------------------

# Each segment: (x_lo, x_hi, y_lo, y_hi)
_HULL_SEGMENTS: tuple[tuple[int, int, int, int], ...] = (
    # Bow section — crushed, exposed, upper-left.
    (20, 40, 4, 16),
    # Upper-fore deck — spaceport sits in/around this.
    (30, 50, 16, 26),
    # Mid-fore — stripped, iced-over.
    (40, 58, 26, 38),
    # Mid section — the bar is built into this segment.
    (50, 70, 38, 52),
    # Mid-aft — deeper in the ice.
    (55, 75, 52, 64),
    # Lower-aft — the bar's lower deck.
    (60, 90, 64, 74),
    # Aft section — crushed, buried.
    (80, 110, 74, 84),
    # Exposed stern plates.
    (95, 125, 84, 92),
)

# Salvage yard — open ground around the hull.
_YARD_PATCHES: tuple[tuple[int, int, int, int], ...] = (
    (4, 20, 4, 20),        # NW corner
    (50, 80, 4, 20),        # north of bow
    (90, 135, 22, 40),      # NE salvage yard
    (4, 32, 44, 56),        # west flank
    (80, 135, 50, 68),      # east flank
    (4, 48, 70, 84),        # south-west
    (80, 135, 74, 90),      # south-east
)

# Docking ring — circle of ice-crusted metal, crew grave.
# Approximate a circle with discrete cells.
_DOCKING_CENTRE = (100, 55)
_DOCKING_OUTER_R = 12
_DOCKING_INNER_R = 10

# Reclamation fires and work lights.
_FIRES: tuple[tuple[int, int], ...] = (
    (14, 28), (22, 32), (36, 40), (48, 44),
    (52, 48), (60, 58), (68, 62), (74, 66),
    (84, 72), (92, 78), (104, 82), (110, 86),
    (6, 46), (10, 60), (78, 32), (96, 34),
    (118, 46), (128, 58), (134, 68), (130, 80),
)

# Tool sheds — scavenger lean-tos.
_SHEDS: tuple[tuple[int, int, int, int], ...] = (
    (8, 34, 3, 3), (16, 36, 3, 3), (40, 52, 3, 3),
    (72, 46, 3, 3), (84, 38, 3, 3), (98, 46, 3, 3),
    (108, 56, 3, 3), (126, 62, 3, 3),
)

# Gantry verticals — skeletal salvage frames.
_GANTRIES: tuple[tuple[int, int, int], ...] = (
    (44, 48, 3), (48, 44, 4), (78, 42, 3),
    (86, 50, 4), (102, 54, 3), (114, 60, 4),
    (128, 68, 3),
)

# ---------------------------------------------------------------------------

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "lal_spaceport": world.Position(_SPACEPORT_X_LO, _SPACEPORT_Y_LO),
    "lal_depot": world.Position(_DEPOT_X_LO, _DEPOT_Y_LO),
    "lal_bar": world.Position(_BAR_X_LO, _BAR_Y_LO),
    "lal_bounties": world.Position(_BOUNTIES_X_LO, _BOUNTIES_Y_LO),
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


# ---------------------------------------------------------------------------
# Painter functions
# ---------------------------------------------------------------------------

def _paint_hull(tiles):
    """Paint the Requiem's diagonal hull segments — walls and interior."""
    for x_lo, x_hi, y_lo, y_hi in _HULL_SEGMENTS:
        # Hull walls.
        for y in range(y_lo, y_hi + 1):
            tiles[y][x_lo] = _HULL_WALL
            tiles[y][x_hi] = _HULL_WALL
        for x in range(x_lo + 1, x_hi):
            tiles[y_lo][x] = _HULL_WALL
            tiles[y_hi][x] = _HULL_WALL
        # Interior floor — stripped deck plates.
        for y in range(y_lo + 1, y_hi):
            for x in range(x_lo + 1, x_hi):
                tiles[y][x] = _HULL_FLOOR
    # Frost crust patches — blown ice over the hull gaps.
    _crusts = (
        (32, 50, 18, 24), (42, 56, 26, 28),
        (52, 68, 52, 54), (62, 78, 64, 66),
    )
    for x_lo, x_hi, y_lo, y_hi in _crusts:
        for y in range(y_lo, y_hi + 1):
            for x in range(x_lo, x_hi + 1):
                if tiles[y][x].kind == "floor":
                    tiles[y][x] = _FROST_CRUST


def _paint_docking_ring(tiles):
    """The crew's grave — ice-crusted metal ring in the terrain."""
    cx, cy = _DOCKING_CENTRE
    for y in range(cy - _DOCKING_OUTER_R, cy + _DOCKING_OUTER_R + 1):
        for x in range(cx - _DOCKING_OUTER_R, cx + _DOCKING_OUTER_R + 1):
            if not (0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT):
                continue
            r = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if _DOCKING_INNER_R <= r <= _DOCKING_OUTER_R:
                if tiles[y][x].kind == "floor":
                    tiles[y][x] = _DOCK_RING
    # Grave markers inside the ring.
    for dy in (-2, 0, 2):
        for dx in (-2, 0, 2):
            x, y = cx + dx, cy + dy
            if 0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT:
                tiles[y][x] = _DOCK_GRAVE
    # Reclamation lantern at the ring centre.
    tiles[cy][cx] = _RECLAMATION_FIRE


def _paint_salvage_yard(tiles):
    """Scraped salvage yard around the hull."""
    for x_lo, x_hi, y_lo, y_hi in _YARD_PATCHES:
        for y in range(y_lo, y_hi + 1):
            for x in range(x_lo, x_hi + 1):
                if tiles[y][x].kind == "floor":
                    tiles[y][x] = _SCRAP_HEAP
    # Fires.
    for x, y in _FIRES:
        if tiles[y][x].kind in {"floor", "plaza"}:
            tiles[y][x] = _RECLAMATION_FIRE
    # Tool sheds.
    for sx, sy, sw, sh in _SHEDS:
        for yy in range(sy, sy + sh):
            for xx in range(sx, sx + sw):
                if yy in (sy, sy + sh - 1) or xx in (sx, sx + sw - 1):
                    tiles[yy][xx] = _HULL_WALL
                else:
                    tiles[yy][xx] = _TOOL_ROOF
    # Gantry frames.
    for gx, gy, gh in _GANTRIES:
        for dy in range(gh):
            ty = gy + dy
            if ty < CITY_HEIGHT - 1:
                tiles[ty][gx] = _GANTRY
        tiles[gy + gh][gx] = _WORK_LIGHT


def _paint_landing_pad(tiles, theme):
    """Landing pad between spaceport and the hull."""
    pad_tile = replace(theme.landing_pad, char=" ")
    for y in range(_PAD_Y_LO, _PAD_Y_HI + 1):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = pad_tile


def _paint_building_forecourts(tiles, theme, spec):
    """Cleared forecourt at each door."""
    for building in spec.buildings:
        y = building.y_hi + 1
        for x in range(building.door_x - 1, building.door_x + 2):
            if 0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT:
                tiles[y][x] = theme.sidewalk


def _paint_transit_bays(tiles, spec):
    """Dedicated transit landing zones."""
    bay_tile = world.Tile(
        kind="floor", char=" ", walkable=True,
        fg=(120, 170, 210), bg=(48, 62, 80),
    )
    for station in spec.transit_stations:
        tiles[station.pos.y][station.pos.x] = bay_tile


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_lal_layout(spec, resolve_ship):
    """Build Deadfall's 140×100 wreck colony."""
    theme = _readable_city_theme(ICE)
    tiles = _base_tiles(theme)
    _paint_hull(tiles)
    _paint_docking_ring(tiles)
    _paint_salvage_yard(tiles)
    _paint_landing_pad(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    _paint_building_forecourts(game_map.tiles, theme, spec)
    _paint_transit_bays(game_map.tiles, spec)
    paint_roof_labels(game_map, stamps, "lal_")
    _set_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


def _set_metadata(game_map, spec, stamps):
    game_map.city_layout_id = spec.city_layout_id or "lal_wreck_colony"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "lal_")


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


__all__ = ["build_lal_layout", "LANDMARK_ORIGINS"]