"""Ross c — Cinder, the Scrap Ring: a salvage bazaar domed over a blast crater.

Ross 154 c is a shattered moon. A dead navy fleet mined and fortified it;
when the fleet died, salvage crews domed the worst blast crater, rigged
the old docks to the decommissioned hulls around it, and turned the whole
graveyard into a bazaar. Everything here is "recovered."

Layout (100x70):

  * The walkable floor is the crater bowl. The map boundary is the
    crater rim itself — an irregular ring of impassable rubble whose
    radius wobbles and bulges inward in three rubble tongues. Badlands
    fill the map corners beyond it. The rim carries the dome's anchor
    pylons; no drawn rectangle wall anywhere.
  * The west rim is breached where the old fortification wall failed:
    the airlock aperture, flanked by gate pylons, opens onto the landing
    apron. The spaceport hull stands north of the apron, door south.
  * A dock street runs east from the apron to the bazaar ring — the ring
    road that circles the sealed impact-slag mound at the crater's
    offset heart. Stalls and crate stacks crowd the ring's outer edge.
  * Spokes tie the ring and street to each building forecourt: The Long
    Burn bar north-east, the salvage brokers hall south-west, the depot
    south-east.
  * The ship-breaker yard fills the east floor: three half-stripped navy
    hulls (frames with blast gaps and torn plating) around a berthing
    lane where the showroom craft wait beside scrap piles.
  * Blast scarring remembers the impact: radial gouges, slag-rimmed
    pock craters, and a frozen melt pool, all kept clear of circulation.
"""

from __future__ import annotations

import math
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


CITY_WIDTH = 100
CITY_HEIGHT = 70

# Fixed asset origins. Footprints leave every public lane visible and
# each door opens onto its planned forecourt.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "ross_c_spaceport": world.Position(24, 24),
    "ross_c_bar":       world.Position(56, 18),
    "ross_c_merchants": world.Position(26, 42),
    "ross_c_depot":     world.Position(64, 44),
}

# ---------------------------------------------------------------------
# Terrain zones
# ---------------------------------------------------------------------

# Crater ellipse: the rim ring is the dome foundation, badlands beyond.
_CRATER_CX, _CRATER_CY = 54, 36
_CRATER_RX, _CRATER_RY = 36.0, 25.0
_RIM_INNER = 0.945       # v below this is walkable crater floor
_BADLANDS_V = 1.05       # v at/above this is open badlands
# Per-sector radius wobble (percent), 16 sectors of 22.5deg starting east
# and running clockwise through south/west/north. Negative sectors are
# the rubble tongues sliding in from the rim.
_RIM_WOBBLE = (
    3, -2, 4, -5, -3, 5, -4, -6,   # east .. south-west
    2, 2, 4, -2, -1, -5, -2, 2,    # west .. north-east
)

# West rim breach: the airlock aperture where the old wall failed.
_BREACH_Y_LO, _BREACH_Y_HI = 33, 43
_BREACH_X_MAX = 20
_BREACH_V_MAX = 1.10     # rim/badlands up to this depth become aperture pad
_GATE_PYLON_ROWS = (_BREACH_Y_LO - 1, _BREACH_Y_HI + 1)

# Landing apron just inside the breach.
_APRON_X_LO, _APRON_X_HI = 20, 32
_APRON_Y_LO, _APRON_Y_HI = 32, 44

# Sealed impact core and the bazaar ring around it.
_MOUND_CX, _MOUND_CY = 62, 38
_MOUND_RADIUS = 5.0
_RING_INNER, _RING_OUTER = 7.5, 10.5
# Stall sites on the ring's outer edge (compass degrees, screen-y down).
_STALL_ANGLES = (0, 45, 90, 135, 180, 225, 270)
_STALL_RING_R = 12.4
_CRATE_CLUSTERS = ((58, 50), (48, 44), (66, 33))

# Dock street from the apron's east edge to the ring's west lobe.
_STREET_ROWS = (35, 36, 37)
_STREET_X_LO, _STREET_X_HI = 33, 53

# Sidewalk spokes: bar forecourt -> ring; merchants forecourt -> street;
# depot forecourt -> ring via an L-bend.
_BAR_SPOKE = ((64, 66), (26, 28))
_MERCHANTS_SPOKE = ((34, 36), (38, 40))
_DEPOT_SPOKE_ROW = ((70, 74), (40, 40))
_DEPOT_SPOKE_COL = ((71, 73), (41, 42))

# Blast scarring: frozen melt pool, pock craters, radial gouges.
_POOL_CX, _POOL_CY = 44, 56
_POOL_RX, _POOL_RY = 4.0, 2.5
_POCKS = ((47, 19, 2.0), (50, 49, 2.5), (56, 27, 1.5))
# Gouges radiate from the mound: (angle_deg, char, length, step)
_GOUGES = (
    (135, "\\", 12.5, 16.5),
    (100, "/", 11.0, 16.0),
    (160, "/", 11.0, 16.0),
)

# Ship-breaker yard: half-stripped navy hulls. Each is (x_lo, y_lo,
# x_hi, y_hi, gaps, plates): outline cells minus gap cells, plus torn
# plating patches inside.
_HULLS = (
    (
        76, 25, 85, 31,
        ((79, 31), (80, 31), (76, 27), (76, 28)),
        ((77, 26, 78, 27), (82, 26, 84, 28), (79, 29, 81, 30)),
    ),
    (
        78, 34, 88, 41,
        ((83, 34), (84, 34), (88, 37), (88, 38)),
        ((80, 35, 82, 37), (84, 36, 86, 38), (80, 39, 83, 40)),
    ),
    (
        68, 26, 75, 31,
        ((75, 28), (75, 29)),
        ((70, 27, 72, 29),),
    ),
)
_SCRAP_PILES = (
    (75, 28), (74, 38), (77, 33), (85, 32), (89, 37), (76, 24),
    (72, 33), (90, 40),
)


# ---------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------


def _tile(kind, char, fg, bg, walkable=True, message=None) -> world.Tile:
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


BADLANDS = _tile(
    "moon_badlands", "▒", (120, 104, 92), (72, 64, 58), walkable=False,
    message="Churned blast rubble - too loose to climb.",
)
RIM_RIDGE = _tile(
    "crater_rim", "^", (172, 150, 128), (72, 64, 58), walkable=False,
    message="The crater rim carries the dome's anchor foundations.",
)
DOME_PYLON = _tile(
    "dome_pylon", "║", (200, 210, 225), (72, 64, 58), walkable=False,
    message="A dome anchor pylon rooted deep in the crater rim.",
)
GATE_PYLON = _tile(
    "airlock_gate", "║", (230, 238, 248), (72, 64, 58), walkable=False,
    message="The airlock gate's pylons brace the aperture against vacuum.",
)
SLAG = _tile(
    "impact_slag", "▓", (128, 104, 138), (54, 46, 62), walkable=False,
    message="Vitrified impact slag, fused smooth by the blast.",
)
GOUGE_A = _tile("blast_gouge", "/", (188, 160, 120), (54, 47, 42))
GOUGE_B = _tile("blast_gouge", "\\", (188, 160, 120), (54, 47, 42))
HULL_FRAME = _tile(
    "navy_hull", "#", (150, 158, 168), (68, 74, 84), walkable=False,
    message="A decommissioned navy hull, half-stripped to the frame.",
)
HULL_PLATE = _tile(
    "navy_hull", "▓", (112, 122, 136), (64, 70, 80), walkable=False,
    message="Torn hull plating, scorched by whatever killed the fleet.",
)
SCRAP_PILE = _tile(
    "scrap_pile", "%", (188, 130, 78), (72, 62, 54),
    message="A pile of recovered parts, sorted and priced.",
)
STALL_A = _tile(
    "bazaar_stall", "▓", (196, 120, 70), (76, 58, 42), walkable=False,
    message="A salvage stall hung with recovered panels and wiring.",
)
STALL_B = _tile(
    "bazaar_stall", "▓", (90, 160, 150), (58, 76, 74), walkable=False,
    message="A broker's stall of boxed components and scorched data cores.",
)
CRATE = _tile(
    "cargo_crate", "#", (146, 104, 60), (72, 62, 54), walkable=False,
    message="Crates of recovered stock, waiting on a buyer.",
)


# ---------------------------------------------------------------------
# Rim geometry helpers
# ---------------------------------------------------------------------


def _rim_scale(x: int, y: int) -> tuple[float, float]:
    """Wobbled ellipse scales ``(rx, ry)`` for the cell's compass sector."""
    angle = math.degrees(math.atan2(y - _CRATER_CY, x - _CRATER_CX))
    sector = int(((angle + 360.0) % 360.0) // 22.5) % 16
    wobble = 1.0 + _RIM_WOBBLE[sector] / 100.0
    return _CRATER_RX * wobble, _CRATER_RY * wobble


def _rim_value(x: int, y: int) -> float:
    """Normalized ellipse value: <1 inside the crater, >=1 in the rim."""
    rx, ry = _rim_scale(x, y)
    dx = (x - _CRATER_CX) / rx
    dy = (y - _CRATER_CY) / ry
    return dx * dx + dy * dy


def _paint_crater_bowl(tiles) -> None:
    """Ring the floor with the wobbled rubble rim and badlands beyond."""
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            value = _rim_value(x, y)
            if value >= _BADLANDS_V:
                tiles[y][x] = BADLANDS
            elif value >= _RIM_INNER:
                tiles[y][x] = RIM_RIDGE


def _paint_apron(tiles, theme) -> None:
    """Reserve the quiet blank landing apron around the berth."""
    apron = replace(theme.landing_pad, char=" ")
    for y in range(_APRON_Y_LO, _APRON_Y_HI + 1):
        for x in range(_APRON_X_LO, _APRON_X_HI + 1):
            tiles[y][x] = apron


def _paint_breach(tiles, theme) -> None:
    """Open the west rim as the airlock aperture and flank it with gates.

    The aperture floor is landing pad: ships set down under the dome's
    one opening. Gate pylons brace the aperture's innermost shoulders:
    the first impassable cells north and south of the gap, wherever the
    wobbled rim puts them.
    """
    apron = replace(theme.landing_pad, char=" ")
    for y in range(_BREACH_Y_LO, _BREACH_Y_HI + 1):
        for x in range(0, _BREACH_X_MAX + 1):
            tile = tiles[y][x]
            if tile.kind in {"crater_rim", "moon_badlands"} and (
                _rim_value(x, y) <= _BREACH_V_MAX
            ):
                tiles[y][x] = apron
    for y in _GATE_PYLON_ROWS:
        shoulder = next(
            (
                x for x in range(_BREACH_X_MAX + 2, -1, -1)
                if not tiles[y][x].walkable
            ),
            None,
        )
        if shoulder is None:
            continue
        for x in (shoulder, shoulder - 1):
            if 0 <= x < CITY_WIDTH and not tiles[y][x].walkable:
                tiles[y][x] = GATE_PYLON


def _paint_mound_and_ring(tiles, theme) -> None:
    """Glaze the sealed impact core and pave the bazaar ring around it."""
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            radius = math.hypot(x - _MOUND_CX, y - _MOUND_CY)
            if radius <= _MOUND_RADIUS:
                tiles[y][x] = SLAG
            elif _RING_INNER <= radius <= _RING_OUTER:
                tiles[y][x] = theme.plaza


def _paint_street(tiles, theme) -> None:
    """Run the dock street from the apron edge into the bazaar ring."""
    for y in _STREET_ROWS:
        for x in range(_STREET_X_LO, _STREET_X_HI + 1):
            if tiles[y][x].kind != "floor":
                continue
            tiles[y][x] = (
                theme.road_surface if y == _STREET_ROWS[1] else theme.sidewalk
            )


def _paint_spokes(tiles, theme) -> None:
    """Tie each building forecourt into the street or the bazaar ring."""
    for (x_lo, x_hi), (y_lo, y_hi) in (
        _BAR_SPOKE, _MERCHANTS_SPOKE, _DEPOT_SPOKE_ROW, _DEPOT_SPOKE_COL,
    ):
        for y in range(y_lo, y_hi + 1):
            for x in range(x_lo, x_hi + 1):
                if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
                    tiles[y][x].kind == "floor"
                ):
                    tiles[y][x] = theme.sidewalk


def _paint_scarring(tiles) -> None:
    """Remember the impact: melt pool, pock craters, radial gouges."""
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if tiles[y][x].kind != "floor":
                continue
            dx = (x - _POOL_CX) / _POOL_RX
            dy = (y - _POOL_CY) / _POOL_RY
            if dx * dx + dy * dy <= 1.0:
                tiles[y][x] = SLAG
    for px, py, pr in _POCKS:
        for y in range(int(py - pr), int(py + pr) + 1):
            for x in range(int(px - pr), int(px + pr) + 1):
                if not in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
                    continue
                if math.hypot(x - px, y - py) <= pr and (
                    tiles[y][x].kind == "floor"
                ):
                    tiles[y][x] = SLAG
    for angle, char, r_lo, r_hi in _GOUGES:
        ux, uy = (
            math.cos(math.radians(angle)), -math.sin(math.radians(angle)),
        )
        step = r_lo
        while step <= r_hi:
            x = int(round(_MOUND_CX + ux * step))
            y = int(round(_MOUND_CY + uy * step))
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
                tiles[y][x].kind == "floor"
            ):
                tiles[y][x] = GOUGE_A if char == "/" else GOUGE_B
            step += 1.0


def _paint_hull(tiles, hull) -> None:
    """Frame one half-stripped hull: outline minus gaps, plates inside."""
    x_lo, y_lo, x_hi, y_hi, gaps, plates = hull
    outline = {
        (x, y)
        for x in range(x_lo, x_hi + 1)
        for y in (y_lo, y_hi)
    } | {
        (x, y)
        for y in range(y_lo, y_hi + 1)
        for x in (x_lo, x_hi)
    }
    for x, y in outline - set(gaps):
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
            tiles[y][x] = HULL_FRAME
    for x, y in gaps:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
            tiles[y][x] = _tile(
                "hull_gap", ",", (120, 108, 96), (68, 60, 54),
                message="A work gap cut into the dead hull's frame.",
            )
    for px_lo, py_lo, px_hi, py_hi in plates:
        for y in range(py_lo, py_hi + 1):
            for x in range(px_lo, px_hi + 1):
                if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
                    (x, y) not in outline
                ):
                    tiles[y][x] = HULL_PLATE


def _paint_yard(tiles) -> None:
    """Build the ship-breaker yard: hulls and sorted scrap piles."""
    for hull in _HULLS:
        _paint_hull(tiles, hull)
    for x, y in _SCRAP_PILES:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = SCRAP_PILE


def _paint_bazaar(tiles) -> None:
    """Crowd the ring's outer edge with stalls and crate stacks."""
    for index, angle in enumerate(_STALL_ANGLES):
        x = int(round(_MOUND_CX + math.cos(math.radians(angle)) * _STALL_RING_R))
        y = int(round(_MOUND_CY - math.sin(math.radians(angle)) * _STALL_RING_R))
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = STALL_A if index % 2 else STALL_B
    for cx, cy in _CRATE_CLUSTERS:
        for x, y in ((cx, cy), (cx + 1, cy), (cx, cy + 1)):
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
                tiles[y][x].kind == "floor"
            ):
                tiles[y][x] = CRATE


def _paint_dome_pylons(tiles) -> None:
    """Set the dome's anchor pylons at the sixteen compass points."""
    for sector in range(16):
        angle = math.radians(sector * 22.5 + 11.25)
        wobble = 1.0 + _RIM_WOBBLE[sector] / 100.0
        x = int(round(_CRATER_CX + math.cos(angle) * _CRATER_RX * wobble * 0.98))
        y = int(round(_CRATER_CY + math.sin(angle) * _CRATER_RY * wobble * 0.98))
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "crater_rim"
        ):
            tiles[y][x] = DOME_PYLON


# ---------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------


_TRANSIT_BAY_TILE = world.Tile(
    kind="transit_bay", char="=", walkable=True,
    fg=(0, 229, 255), bg=(30, 68, 92),
)


def _paint_terrain(tiles, theme) -> None:
    """Lay down Cinder's crater bowl, streets, and salvage yards."""
    _paint_crater_bowl(tiles)
    _paint_apron(tiles, theme)
    _paint_breach(tiles, theme)
    _paint_mound_and_ring(tiles, theme)
    _paint_street(tiles, theme)
    _paint_spokes(tiles, theme)
    _paint_scarring(tiles)
    _paint_yard(tiles)
    _paint_bazaar(tiles)


def build_ross_c_layout(spec, resolve_ship) -> world.GameMap:
    """Build Cinder's 100x70 crater-bowl salvage bazaar."""
    theme = _readable_city_theme(spec.theme or world.EARTH_THEME)
    # No walled perimeter: badlands and the rubble rim bound the map.
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    _paint_terrain(tiles, theme)
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
    _paint_dome_pylons(game_map.tiles)
    paint_transit_bays(
        game_map.tiles, spec, _TRANSIT_BAY_TILE,
        width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({
            "floor", "grass", "grass_accent", "plaza", "city_plaza",
            "sidewalk", "landing_pad",
        }),
        force_center=True,
    )
    paint_roof_labels(game_map, stamps, "ross_c_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="ross_c_", default_layout_id="ross_c_scrap_ring",
    )
    add_showroom_ships(game_map, spec, resolve_ship)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-5, -2, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


__all__ = ["build_ross_c_layout", "LANDMARK_ORIGINS"]
