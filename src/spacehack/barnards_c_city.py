"""Barnard c — the Skimmer Deck, an atmospheric helium-3 mining platform.

Barnard c is a cold gas giant: it has no surface. Its settlement is an
industrial deck hung in the upper cloud bands, siphoning helium-3 and
rare volatiles for the frontier routes. The deck plate is the whole
walkable floor; every edge ends in a storm-void band fronted by a
painted hazard toe-line, the way a real platform ends at a yellow line
you can stand on but not past.

Layout (110x72):

  * One east-west service spine (road + sidewalk shoulders) crosses
    mid-deck; two north-south road connectors tie the west landing
    apron and the eastern bar frontage to the spine.
  * The deck is sheared, not rectangular: the southwest corner has
    been cut away in three steps down to the storm, rim-plated at the
    new edge. The west connector dies at the shear the way a real
    service stub would.
  * Landing operations (west): quiet blank apron around the hangar
    berth; the spaceport hull sits north of the apron, door south.
  * Bar district (east): The Deep Freeze, door south onto a sidewalk
    spur meeting the spine.
  * Industrial character instead of townscape filler: an eleven-tank
    He-3 farm in three staggered rows (southeast deck), a painted He-3
    pipeline header and cross-deck run with valve manifolds, two
    skimmer cradles flanking the siphon inlet, gantry trusses braced
    along the north void edge, and a cloud inlet cut into the southern
    rim.
"""

from __future__ import annotations

from dataclasses import replace

from . import world
from .city_kit import (
    TERMINAL_PALETTE_CLASSIC,
    add_service_terminals,
    add_showroom_ships,
    in_bounds,
    paint_door_forecourts,
    paint_transit_bays,
    set_city_metadata,
)
from .city_layout import paint_roof_labels, stamp_city_assets
from .data.planets import _readable_city_theme


CITY_WIDTH = 110
CITY_HEIGHT = 72

# Fixed asset origins. Footprints leave every public lane visible and
# each door opens onto its planned forecourt.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "barnards_c_spaceport": world.Position(22, 27),
    "barnards_c_bar": world.Position(86, 12),
}

# ---------------------------------------------------------------------
# Terrain zones
# ---------------------------------------------------------------------

_VOID_BAND = 2          # non-walkable storm-void cells along every edge
_TOE_ROWS = (2, CITY_HEIGHT - 3)
_TOE_COLS = (2, CITY_WIDTH - 3)

_SPINE_Y_LO, _SPINE_Y_HI = 37, 39       # sidewalk / road / sidewalk
_NS_CONNECTORS = ((6, 8), (94, 96))     # sidewalk / road / sidewalk, per lane

_APRON_X_LO, _APRON_X_HI = 10, 25
_APRON_Y_LO, _APRON_Y_HI = 41, 54

_FORECOURT_SPURS = (
    # Spaceport forecourt: door -> down to the spine.
    ((31, 33), (35, 36)),
    # Deep Freeze spur: door -> down to the spine.
    ((94, 96), (20, 36)),
)

# Southwest deck shear: stepped cut-away where storm took the corner.
# Each step is (y_lo, y_hi, x_max) -- every deck cell with x <= x_max in
# the row band is gone, leaving a staircase rim of bare plating.
_SHEAR_STEPS: tuple[tuple[int, int, int], ...] = (
    (55, 60, 30),
    (61, 65, 40),
    (66, CITY_HEIGHT - 1, 50),
)

# North-edge pipe gantry: beams with posts between, braced against the sky.
_GANTRY_Y_LO, _GANTRY_Y_HI = 7, 9
_GANTRY_POST_PERIOD = 6

# Southeast helium-3 tank farm: three staggered rows of frost-caked
# cylinder clusters.
_TANK_CLUSTER_SITES = (
    (70, 41), (76, 41), (82, 41), (88, 41),
    (70, 48), (76, 48), (82, 48), (88, 48),
    (73, 54), (79, 54), (85, 54),
)
_TANK_WIDTH, _TANK_HEIGHT = 4, 5

# Painted He-3 lines: a header dropping from the spine to the siphon
# rim, plus a cross-deck run tying the tank farm to the west cradles
# and the east service road.
_PIPE_HEADER_X = 69
_PIPE_HEADER_Y_LO, _PIPE_HEADER_Y_HI = 40, 59
_PIPE_RUN_Y = 59
_PIPE_RUN_X_LO, _PIPE_RUN_X_HI = 47, 93

# Valve manifolds bleeding pressure between the lines (2x2 each).
_MANIFOLD_SITES = ((74, 43), (86, 50))
_MANIFOLD_SIZE = 2

# Skimmer cradles flanking the siphon inlet mouth: 5x4 frames with an
# open berth bed and a deck-side gate. Origins are top-left corners,
# one row above the shear rim so no frame hangs over the void.
_CRADLES: tuple[tuple[int, int, int], ...] = (
    (47, 61, "west"),   # gate on the west wall, away from the inlet
    (84, 61, "east"),   # gate on the east wall, away from the inlet
)
_CRADLE_WIDTH, _CRADLE_HEIGHT = 5, 4

# Southern cloud inlet: siphon head reaching into the abyss (scenery).
_INLET_X_LO, _INLET_X_HI = 58, 83
_INLET_RIM_Y = 61

# ---------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------


def _tile(kind, char, fg, bg, walkable=True, message=None) -> world.Tile:
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


STORM_VOID = _tile(
    "storm_void", " ", (70, 92, 120), (26, 36, 56), walkable=False,
    message="The storm void drops away into endless cloud.",
)
VOID_RIM = _tile(
    "storm_rim", "^", (120, 148, 180), (30, 42, 62), walkable=False,
    message="Rim plating braces the deck against the wind.",
)
TANK_WALL = _tile(
    "he3_tank", "O", (168, 190, 214), (48, 60, 84), walkable=False,
    message="A frost-caked helium-3 tank holds supercritical pressure.",
)
TANK_CAP = _tile(
    "he3_tank", "o", (200, 220, 240), (48, 60, 84), walkable=False,
    message="A frosted tank dome gleams under the warning lamps.",
)
GANTRY_BEAM = _tile(
    "gantry_truss", "#", (138, 152, 170), (38, 46, 64), walkable=False,
    message="A braced truss carries the siphon lines overhead.",
)
MANIFOLD = _tile(
    "he3_manifold", "%", (130, 205, 190), (40, 50, 70), walkable=False,
    message="A valve manifold bleeds pressure between the He-3 lines.",
)
CRADLE_BED = _tile(
    "skimmer_cradle", ",", (150, 170, 195), (44, 54, 74),
    message="An empty skimmer cradle awaits its next gas-run.",
)

# Painted hazard toe-line: a real platform's edge line you can stand on.
HAZARD_TOE_FG = (255, 198, 74)
# Painted He-3 feed line: walkable deck marking, copper against the plate.
HE3_PIPE_FG = (196, 146, 92)


def _hazard_toe(bg: tuple[int, int, int]) -> world.Tile:
    """Build the toe-line tile preserving the surface colour beneath."""
    return _tile("hazard_toe", "=", HAZARD_TOE_FG, bg)


def _he3_pipe(bg: tuple[int, int, int]) -> world.Tile:
    """Build the pipeline tile preserving the surface colour beneath."""
    return _tile("he3_pipe", "~", HE3_PIPE_FG, bg)


# ---------------------------------------------------------------------
# Painters
# ---------------------------------------------------------------------


def _paint_void_band(tiles) -> None:
    """Ring the whole map with non-walkable gas-top abyss."""
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            edge_x = x < _VOID_BAND or x >= CITY_WIDTH - _VOID_BAND
            edge_y = y < _VOID_BAND or y >= CITY_HEIGHT - _VOID_BAND
            if edge_x or edge_y:
                tiles[y][x] = STORM_VOID


def _paint_apron(tiles, theme) -> None:
    """Reserve the quiet blank landing apron around the berth."""
    apron = replace(theme.landing_pad, char=" ")
    for y in range(_APRON_Y_LO, _APRON_Y_HI + 1):
        for x in range(_APRON_X_LO, _APRON_X_HI + 1):
            tiles[y][x] = apron


def _paint_deck_shear(tiles) -> None:
    """Cut the southwest corner away in steps and rim the new edge."""
    carved = {
        (x, y)
        for y_lo, y_hi, x_max in _SHEAR_STEPS
        for y in range(y_lo, y_hi + 1)
        for x in range(0, x_max + 1)
    }
    for x, y in carved:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
            tiles[y][x] = STORM_VOID
    # Rim plating where surviving deck meets the shear.
    for x, y in carved:
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = x + dx, y + dy
            if not in_bounds(nx, ny, CITY_WIDTH, CITY_HEIGHT):
                continue
            neighbour = tiles[ny][nx]
            if neighbour.kind in {"storm_void", "storm_rim"}:
                continue
            if (nx, ny) in carved:
                continue
            tiles[ny][nx] = VOID_RIM


def _paint_gantry(tiles) -> None:
    """Brace pipe-truss beams along the northern void edge."""
    for y in range(_GANTRY_Y_LO, _GANTRY_Y_HI + 1):
        beam_row = y != _GANTRY_Y_LO + 1
        for x in range(2, CITY_WIDTH - 2):
            if beam_row or (x - 2) % _GANTRY_POST_PERIOD == 0:
                tiles[y][x] = GANTRY_BEAM


def _paint_tank_farm(tiles) -> None:
    """Paint frosted helium-3 cylinder clusters on free deck pockets."""
    for x_lo, y_lo in _TANK_CLUSTER_SITES:
        for y in range(y_lo, min(y_lo + _TANK_HEIGHT, _INLET_RIM_Y)):
            for x in range(x_lo, x_lo + _TANK_WIDTH):
                if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
                    cap_row = y == y_lo
                    tiles[y][x] = TANK_CAP if cap_row else TANK_WALL


def _paint_pipes(tiles) -> None:
    """Paint the He-3 feed lines onto the open deck plates."""
    for y in range(_PIPE_HEADER_Y_LO, _PIPE_HEADER_Y_HI + 1):
        x = _PIPE_HEADER_X
        if tiles[y][x].walkable:
            tiles[y][x] = _he3_pipe(tiles[y][x].bg)
    for x in range(_PIPE_RUN_X_LO, _PIPE_RUN_X_HI + 1):
        y = _PIPE_RUN_Y
        if tiles[y][x].walkable:
            tiles[y][x] = _he3_pipe(tiles[y][x].bg)


def _paint_manifolds(tiles) -> None:
    """Set 2x2 valve manifolds into the gaps between tank clusters."""
    for x_lo, y_lo in _MANIFOLD_SITES:
        for y in range(y_lo, y_lo + _MANIFOLD_SIZE):
            for x in range(x_lo, x_lo + _MANIFOLD_SIZE):
                if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
                    tiles[y][x] = MANIFOLD


def _paint_skimmer_cradles(tiles, theme) -> None:
    """Frame two skimmer cradles flanking the inlet, gates to the deck."""
    for cx, cy, gate_side in _CRADLES:
        x_hi, y_hi = cx + _CRADLE_WIDTH - 1, cy + _CRADLE_HEIGHT - 1
        gate_x = cx if gate_side == "west" else x_hi
        gate_y = cy + 1
        for y in range(cy, y_hi + 1):
            for x in range(cx, x_hi + 1):
                on_frame = x in (cx, x_hi) or y in (cy, y_hi)
                if (x, y) == (gate_x, gate_y):
                    tiles[y][x] = theme.floor
                elif on_frame:
                    tiles[y][x] = GANTRY_BEAM
                else:
                    tiles[y][x] = CRADLE_BED


def _paint_cloud_inlet(tiles) -> None:
    """Cut the southern rim open where the siphon head dips into the storm."""
    for y in range(_INLET_RIM_Y, CITY_HEIGHT):
        for x in range(_INLET_X_LO, _INLET_X_HI + 1):
            tiles[y][x] = STORM_VOID
    for x in range(_INLET_X_LO, _INLET_X_HI + 1):
        tiles[_INLET_RIM_Y - 1][x] = VOID_RIM
    # Siphon-head struts rising out of the inlet.
    for x, y in ((63, 63), (63, 65), (78, 63), (78, 65)):
        tiles[y][x] = GANTRY_BEAM


def _paint_spine(tiles, theme) -> None:
    """Paint the east-west service spine with sidewalk shoulders."""
    for y in range(_SPINE_Y_LO, _SPINE_Y_HI + 1):
        tile = (
            theme.sidewalk if y != _SPINE_Y_LO + 1 else theme.road_surface
        )
        for x in range(2, CITY_WIDTH - 2):
            tiles[y][x] = tile


def _paint_connectors(tiles, theme) -> None:
    """Run the north-south connectors, keeping road centre glyphs intact.

    Connectors stop dead at the shear rim instead of painting lane onto
    the storm void -- a service stub that simply ends where deck does.
    """
    for x_lo, x_hi in _NS_CONNECTORS:
        for x in range(x_lo, x_hi + 1):
            tile = (
                theme.sidewalk if x != x_lo + 1 else theme.road_ns
            )
            for y in range(3, CITY_HEIGHT - 3):
                if tiles[y][x].kind in {"road", "storm_void", "storm_rim"}:
                    continue
                tiles[y][x] = tile


def _paint_forecourts(tiles, theme) -> None:
    """Walk every door's planned approach down to the spine."""
    for (x_lo, x_hi), (y_lo, y_hi) in _FORECOURT_SPURS:
        for y in range(y_lo, y_hi + 1):
            for x in range(x_lo, x_hi + 1):
                tiles[y][x] = theme.sidewalk


def _paint_hazard_toelines(tiles, theme) -> None:
    """Stamp the walkable painted edge line across the deck rim,
    preserving each surface's background so routes read straight
    through. Void and rim cells are left alone: the painted line must
    never bridge the drop."""
    for y in _TOE_ROWS:
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].walkable:
                tiles[y][x] = _hazard_toe(tiles[y][x].bg)
    for x in _TOE_COLS:
        for y in range(2, CITY_HEIGHT - 2):
            if tiles[y][x].walkable:
                tiles[y][x] = _hazard_toe(tiles[y][x].bg)


# ---------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------


_TRANSIT_BAY_TILE = world.Tile(
    kind="transit_bay", char="=", walkable=True,
    fg=(0, 229, 255), bg=(30, 68, 92),
)


def _paint_deck(tiles, theme) -> None:
    """Lay down the Skimmer Deck's plate, plant, and circulation."""
    _paint_void_band(tiles)
    _paint_apron(tiles, theme)
    _paint_deck_shear(tiles)
    _paint_gantry(tiles)
    _paint_tank_farm(tiles)
    _paint_pipes(tiles)
    _paint_manifolds(tiles)
    _paint_skimmer_cradles(tiles, theme)
    _paint_cloud_inlet(tiles)
    _paint_spine(tiles, theme)
    _paint_connectors(tiles, theme)
    _paint_forecourts(tiles, theme)


def build_barnards_c_layout(spec, resolve_ship) -> world.GameMap:
    """Build the Skimmer Deck's 110x72 atmospheric mining platform."""
    theme = _readable_city_theme(spec.theme or world.EARTH_THEME)
    # No walled perimeter: the deck plate ends at storm void, not town wall.
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    _paint_deck(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor"}),
    )
    _paint_hazard_toelines(game_map.tiles, theme)
    paint_transit_bays(
        game_map.tiles, spec, _TRANSIT_BAY_TILE,
        width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({
            "floor", "grass", "grass_accent", "plaza", "city_plaza",
            "sidewalk", "landing_pad",
        }),
        force_center=True,
    )
    paint_roof_labels(game_map, stamps, "barnards_c_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="barnards_c_", default_layout_id="barnards_c_atmo_deck",
    )
    add_showroom_ships(game_map, spec, resolve_ship)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-7, -3, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


__all__ = ["build_barnards_c_layout", "LANDMARK_ORIGINS"]
