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
_BAR_Y_LO, _BAR_Y_HI = 64, 73

_BOUNTIES_X_LO, _BOUNTIES_X_HI = 8, 23
_BOUNTIES_Y_LO, _BOUNTIES_Y_HI = 72, 82

_PAD_X_LO, _PAD_X_HI = 34, 49
_PAD_Y_LO, _PAD_Y_HI = 8, 16

# ---------------------------------------------------------------------------
# Custom tiles — CP437-safe glyphs
# ---------------------------------------------------------------------------

# The Requiem's hull — cold metallic wreck plating, black-backed.
_HULL_WALL = world.Tile(
    kind="city_building_wall", char="#", walkable=False,
    fg=(100, 145, 170), bg=(24, 38, 52),
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

# The Requiem's spine is a narrow, broken corridor of hull floor (▒)
# ringed by fragmented hull walls (▓) with deliberate breaches.
# Players walk through the wreck freely — walls are scattered debris,
# not contiguous barriers.
#
# Each entry: (x_start, x_end, y_start, y_end) — a walkable hull-deck patch.
# Walls are painted *around* some edges, but with gaps.
_HULL_DECK_PATCHES: tuple[tuple[int, int, int, int], ...] = (
    # Bow deck — crushed and exposed.
    (18, 30, 6, 14),
    # Upper-fore deck.
    (30, 42, 16, 24),
    # Mid-fore — stripped interior.
    (42, 54, 28, 38),
    # Mid section — bar is alongside this.
    (54, 66, 42, 52),
    # Mid-aft.
    (60, 74, 56, 64),
    # Lower-aft.
    (72, 86, 68, 76),
    # Aft section.
    (84, 98, 78, 86),
    # Exposed stern plates.
    (100, 114, 86, 92),
)

# Hull wall fragments: (x, y, length, orientation).
# "h" = horizontal span to the right; "v" = vertical span downward.
# These are the broken ribs of the Requiem — never a solid line.
_HULL_WALL_FRAGS: tuple[tuple[int, int, int, str], ...] = (
    # Bow walls —  broken into chunks.
    (18, 6, 3, "h"), (26, 14, 3, "h"),
    (18, 6, 4, "v"), (30, 10, 4, "v"),
    # Upper-fore.
    (30, 16, 4, "h"), (36, 24, 3, "h"),
    (30, 16, 4, "v"), (42, 20, 4, "v"),
    # Mid-fore.
    (42, 28, 4, "h"), (48, 38, 4, "h"),
    (42, 28, 4, "v"), (54, 34, 3, "v"),
    # Mid section.
    (54, 42, 4, "h"), (60, 52, 3, "h"),
    (54, 42, 4, "v"), (66, 48, 3, "v"),
    # Mid-aft.
    (60, 56, 4, "h"), (68, 64, 3, "h"),
    (60, 56, 4, "v"), (74, 60, 3, "v"),
    # Lower-aft.
    (72, 68, 4, "h"), (80, 76, 4, "h"),
    (72, 68, 4, "v"), (86, 72, 3, "v"),
    # Aft.
    (84, 78, 4, "h"), (92, 86, 3, "h"),
    (84, 78, 4, "v"), (98, 82, 3, "v"),
    # Stern.
    (100, 86, 4, "h"), (108, 92, 4, "h"),
    (100, 86, 3, "v"), (114, 88, 3, "v"),
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
# Painter functions
# ---------------------------------------------------------------------------

def _paint_hull(tiles):
    """Paint the Requiem's skeletal spine — walkable deck with broken wall ribs."""
    # 1. Paint walkable hull deck first.
    for x_lo, x_hi, y_lo, y_hi in _HULL_DECK_PATCHES:
        for y in range(y_lo, y_hi + 1):
            for x in range(x_lo, x_hi + 1):
                if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                    tiles[y][x] = _HULL_FLOOR
    # 2. Paint broken wall fragments — never a solid line.
    for wx, wy, length, orient in _HULL_WALL_FRAGS:
        for i in range(length):
            if orient == "h":
                x, y = wx + i, wy
            else:
                x, y = wx, wy + i
            if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
                tiles[y][x] = _HULL_WALL
    # 3. Frost crust on the gaps between deck patches.
    _crusts = (
        (30, 42, 14, 16), (42, 54, 24, 28),
        (54, 60, 38, 42), (66, 72, 52, 56),
        (74, 84, 64, 68), (86, 100, 76, 78),
    )
    for x_lo, x_hi, y_lo, y_hi in _crusts:
        for y in range(y_lo, y_hi + 1):
            for x in range(x_lo, x_hi + 1):
                if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
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


_BAY_TILE = world.Tile(
    kind="transit_bay", char="=", walkable=True,
    fg=(0, 229, 255), bg=(30, 68, 92),
)


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_lal_layout(spec, resolve_ship):
    """Build Deadfall's 140×100 wreck colony."""
    theme = _readable_city_theme(ICE)
    tiles = base_tiles(CITY_WIDTH, CITY_HEIGHT, theme.floor)
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
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
    )
    paint_transit_bays(
        game_map.tiles, spec, _BAY_TILE,
        width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({
            "floor", "grass", "grass_accent", "plaza", "city_plaza",
            "sidewalk", "landing_pad",
        }),
        force_center=True,
    )
    paint_roof_labels(game_map, stamps, "lal_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="lal_", default_layout_id="lal_wreck_colony",
    )
    add_showroom_ships(game_map, spec, resolve_ship)
    add_service_terminals(game_map, spec, dy=2)
    return game_map



__all__ = ["build_lal_layout", "LANDMARK_ORIGINS"]