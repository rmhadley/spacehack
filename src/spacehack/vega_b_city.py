"""Vega b — The Beacon: a floating power-and-observation station.

Vega b is a massive gas giant; the player "lands" on a platform
suspended in its upper atmosphere. The station's reason to exist is
power: a fan of reflector panels concentrates Vega's light onto a
collector tower, and the waste heat bleeds off the east rim through
cooling fins. Around that industrial core the inhabited deck grew —
landing deck north, Freight Exchange south, and The Veil observation
lounge west, hanging over the cloud bands. Vega is the sector's
navigation hub, and the station is its beacon: every route threads
through Vega, and ships set course by its light.

Layout (140x90), authored as `vega_beacon_station`:

  * The whole map outside the platform is open atmosphere: horizontal
    cloud bands with sparse wisps. The platform silhouette — a cross
    of four arms over the cloud deck — is the walkable deck.
  * The Focus, the 21x21 central hub where the arms overlap, carries
    the station's navigation beacon and a neon ring.
  * North arm — Landing Deck: the spaceport at the arm's tip, the
    smooth landing apron (berth + showroom + terminals), and the
    corridor down to the hub.
  * East arm — Reflector Field: a wedge widening toward the map edge,
    filled by seven mirror rays fanning from the collector tower; the
    walkable lanes between the rays are the maintenance access. A
    service shack sits north of the tower; cooling fins and radiators
    bleed heat off the tip into the clouds.
  * South arm — Freight Exchange: the merchants hall and the depot
    flanking a central corridor that opens onto the exchange plaza
    with freight crates along its rim.
  * West arm — The Veil: the bar and, beyond it, the rounded
    observation deck with safety railings hanging over the clouds.
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


CITY_WIDTH = 140
CITY_HEIGHT = 90

# Fixed asset origins. Footprints leave every public lane visible and
# each door opens onto its planned deck.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "vega_b_spaceport": world.Position(58, 4),
    "vega_b_bar":       world.Position(26, 38),
    "vega_b_merchants": world.Position(56, 62),
    "vega_b_depot":     world.Position(72, 62),
}

# ---------------------------------------------------------------------
# Platform geometry
# ---------------------------------------------------------------------

# Four arms over the cloud deck; the hub is their 21x21 overlap.
_NORTH_ARM = (52, 88, 8, 45)      # x_lo, x_hi, y_lo, y_hi
_SOUTH_ARM = (54, 86, 45, 82)
_WEST_ARM = (8, 60, 35, 55)
_WEDGE_X_LO, _WEDGE_X_HI = 70, 132
_WEDGE_HALF_AT_HUB = 10.0
_WEDGE_SPREAD = 0.15             # half-height grows 0.15 per cell east
_HUB = (60, 80, 35, 55)

_APRON = (52, 88, 9, 17)
_EXCHANGE_PLAZA = (54, 86, 70, 76)
_OBSERVE_CX, _OBSERVE_CY = 17, 45
_OBSERVE_RX, _OBSERVE_RY = 9, 10

# Reflector field: the tower anchors seven rays fanning into the wedge.
_TOWER = (82, 86, 43, 47)        # x_lo, x_hi, y_lo, y_hi
_TOWER_CX, _TOWER_CY = 84, 45
_FAN = (
    (-60, 14), (-40, 22), (-20, 40), (0, 44),
    (20, 40), (40, 22), (60, 14),
)
_RAY_START = 3
_SHACK = (88, 91, 34, 36)
_FIN_X_LO, _FIN_X_HI = 133, 138
_FIN_ROWS = (30, 37, 44, 51, 58)
_COOLING_X = 128

# Hub beacon and its neon ring.
_BEACON = (70, 45)
_NEON_RING = ((70, 42), (70, 48), (66, 45), (74, 45))
# A field marker near the collector tower so the reflector stop reads as
# a destination, not a bare lane.
_FIELD_NEON = (95, 44)

# Freight crates on the exchange plaza rim (clear of doors and stops).
_CRATES = (
    (57, 72), (58, 75), (63, 73), (66, 75),
    (74, 75), (77, 73), (81, 71), (85, 75),
)


# ---------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------


def _tile(kind, char, fg, bg, walkable=True, message=None) -> world.Tile:
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


CLOUD_A = _tile(
    "cloud_deck", "░", (108, 128, 152), (48, 62, 82), walkable=False,
    message="The cloud deck below the station is not solid ground.",
)
CLOUD_B = _tile(
    "cloud_deck", "░", (96, 116, 140), (44, 58, 76), walkable=False,
    message="The cloud deck below the station is not solid ground.",
)
CLOUD_WISP = _tile(
    "cloud_deck", "·", (150, 180, 205), (44, 58, 76), walkable=False,
    message="The cloud deck below the station is not solid ground.",
)
RAILING = _tile(
    "railing", "│", (170, 200, 220), (55, 70, 85), walkable=False,
    message="A safety railing overlooks the cloud deck.",
)
MIRROR = _tile(
    "solar_mirror", "=", (215, 235, 255), (58, 78, 98),
    message="A reflector panel catches the station's light.",
)
MIRROR_UP = _tile(
    "solar_mirror", "/", (215, 235, 255), (58, 78, 98),
    message="A reflector panel catches the station's light.",
)
MIRROR_DOWN = _tile(
    "solar_mirror", "\\", (215, 235, 255), (58, 78, 98),
    message="A reflector panel catches the station's light.",
)
TOWER = _tile(
    "collector_tower", "█", (95, 125, 155), (40, 55, 70), walkable=False,
    message="The collector tower concentrates the reflected light.",
)
TOWER_CORE = _tile(
    "collector_tower", "!", (255, 210, 90), (58, 48, 28), walkable=False,
    message="The collector's focus glows with concentrated light.",
)
SHACK = _tile(
    "service_shack", "#", (140, 160, 180), (46, 60, 76), walkable=False,
    message="A sealed service shack for the reflector field.",
)
COOLING = _tile(
    "cooling_works", "*", (110, 238, 248), (30, 76, 88), walkable=False,
    message="A waste-heat radiator bleeds the station's heat into the clouds.",
)
FIN = _tile(
    "cooling_fin", "─", (150, 200, 215), (40, 52, 68), walkable=False,
    message="A cooling fin hangs over the cloud deck.",
)
CRATE = _tile(
    "cargo_crate", "#", (146, 104, 60), (72, 62, 54), walkable=False,
    message="Freight crates waiting on a berth.",
)
BEACON = _tile(
    "beacon", "!", (255, 215, 100), (44, 38, 22), walkable=False,
    message="The station's navigation beacon sweeps the cloud deck.",
)
BAY = _tile(
    "transit_bay", "=", (140, 240, 255), (42, 74, 88),
    message="A transit boarding bay.",
)


# ---------------------------------------------------------------------
# Terrain painters
# ---------------------------------------------------------------------


def _paint_cloud_deck(tiles) -> None:
    """Fill the map with horizontal cloud bands and sparse wisps."""
    for y in range(CITY_HEIGHT):
        band = CLOUD_A if y % 2 == 0 else CLOUD_B
        for x in range(CITY_WIDTH):
            tiles[y][x] = band
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if (x * 7 + y * 11) % 97 == 0:
                tiles[y][x] = CLOUD_WISP


def _paint_arm(tiles, theme, arm) -> None:
    """Paint one rectangular arm as pedestrian deck."""
    x_lo, x_hi, y_lo, y_hi = arm
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = theme.sidewalk


def _in_wedge(x: int, y: int) -> bool:
    """Whether a cell lies on the widening reflector-field arm."""
    if not (_WEDGE_X_LO <= x <= _WEDGE_X_HI):
        return False
    half = _WEDGE_HALF_AT_HUB + (x - _WEDGE_X_LO) * _WEDGE_SPREAD
    return abs(y - _TOWER_CY) <= half


def _paint_platform(tiles, theme) -> None:
    """Paint the cross silhouette: three arms plus the widening wedge."""
    for arm in (_NORTH_ARM, _SOUTH_ARM, _WEST_ARM):
        _paint_arm(tiles, theme, arm)
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if _in_wedge(x, y):
                tiles[y][x] = theme.sidewalk


def _paint_rect(tiles, tile, rect) -> None:
    """Paint a rectangular region with one tile."""
    x_lo, x_hi, y_lo, y_hi = rect
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = tile


def _in_observation_deck(x: int, y: int) -> bool:
    """Whether a cell lies on the rounded observation deck."""
    dx = (x - _OBSERVE_CX) / _OBSERVE_RX
    dy = (y - _OBSERVE_CY) / _OBSERVE_RY
    return dx * dx + dy * dy <= 1.0


def _paint_hub_and_plazas(tiles, theme) -> None:
    """Paint the Focus hub, the exchange plaza, and the observation deck."""
    _paint_rect(tiles, theme.plaza, _HUB)
    _paint_rect(tiles, theme.plaza, _EXCHANGE_PLAZA)
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if _in_observation_deck(x, y):
                tiles[y][x] = theme.plaza


def _paint_apron(tiles, theme) -> None:
    """Reserve the quiet blank landing apron around the berth."""
    apron = replace(theme.landing_pad, char=" ")
    _paint_rect(tiles, apron, _APRON)


def _paint_ray(tiles, angle_deg: int, length: int) -> None:
    """Paint one mirror ray from the tower into the wedge.

    The ray char follows its slope: ``=`` for the shallow center ray,
    ``/`` for rays climbing east, ``\\`` for rays diving east. Rays
    are walkable — they read as a fan of panels laid flat on the deck,
    and the lanes between them stay open as the field's maintenance
    access (the collector tower and service shack are the only
    blockers).
    """
    if abs(angle_deg) < 10:
        tile = MIRROR
    elif angle_deg < 0:
        tile = MIRROR_UP
    else:
        tile = MIRROR_DOWN
    ux = math.cos(math.radians(angle_deg))
    uy = math.sin(math.radians(angle_deg))
    for step in range(_RAY_START, length + 1):
        x = int(round(_TOWER_CX + ux * step))
        y = int(round(_TOWER_CY + uy * step))
        if not in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
            continue
        if tiles[y][x].kind not in {"sidewalk", "plaza"}:
            continue
        tiles[y][x] = tile


def _paint_fan(tiles) -> None:
    """Paint the collector tower, its mirror fan, shack, and cooling."""
    _paint_rect(tiles, TOWER, _TOWER)
    tiles[_TOWER_CY][_TOWER_CX] = TOWER_CORE
    for angle_deg, length in _FAN:
        _paint_ray(tiles, angle_deg, length)
    _paint_rect(tiles, SHACK, _SHACK)
    for y in _FIN_ROWS:
        for x in range(_FIN_X_LO, _FIN_X_HI + 1):
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT):
                tiles[y][x] = FIN
        if in_bounds(_COOLING_X, y, CITY_WIDTH, CITY_HEIGHT):
            tiles[y][x] = COOLING


def _paint_railings(tiles) -> None:
    """Ring the observation deck with railings where it meets open air."""
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if not _in_observation_deck(x, y):
                continue
            if any(
                not in_bounds(x + dx, y + dy, CITY_WIDTH, CITY_HEIGHT)
                or not tiles[y + dy][x + dx].walkable
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
            ):
                tiles[y][x] = RAILING


def _paint_beacon_and_crates(tiles, theme) -> None:
    """Place the navigation beacon, its neon ring, and freight crates."""
    bx, by = _BEACON
    tiles[by][bx] = BEACON
    for x, y in _NEON_RING:
        if tiles[y][x].walkable:
            tiles[y][x] = theme.neon
    fx, fy = _FIELD_NEON
    if tiles[fy][fx].walkable:
        tiles[fy][fx] = theme.neon
    for x, y in _CRATES:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and tiles[y][x].walkable:
            tiles[y][x] = CRATE


# ---------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------


def build_vega_b_layout(spec, resolve_ship) -> world.GameMap:
    """Build The Beacon's 140x90 floating station from data + assets."""
    theme = _readable_city_theme(spec.theme or world.EARTH_THEME)
    tiles = [[CLOUD_A for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    _paint_cloud_deck(tiles)
    _paint_platform(tiles, theme)
    _paint_hub_and_plazas(tiles, theme)
    _paint_apron(tiles, theme)
    _paint_fan(tiles)
    _paint_railings(tiles)
    _paint_beacon_and_crates(tiles, theme)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk"}),
    )
    paint_transit_bays(
        game_map.tiles, spec, BAY, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk", "plaza"}),
    )
    paint_roof_labels(game_map, stamps, "vega_b_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="vega_b_", default_layout_id="vega_beacon_station",
    )
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-5, -2, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


__all__ = ["build_vega_b_layout", "LANDMARK_ORIGINS"]