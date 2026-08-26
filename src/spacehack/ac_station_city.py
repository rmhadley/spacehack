"""Alpha Centauri's authored orbital ring station layout.

The station is a hollow annulus with a central zero-g void, four structural
spokes, a transfer dock, and research/public sectors around the ring. The
ring is static in the simulation; its geometry communicates a station built
to spin for gravity without requiring an animation system.
"""

from __future__ import annotations

from dataclasses import replace

from . import world
from .city_kit import add_service_terminals, add_showroom_ships
from .city_layout import (
    building_records,
    paint_roof_labels,
    stamp_city_assets,
    stamp_metadata,
)
from .data.planets import _readable_city_theme
from .data.planets.themes import RING_STATION


RING_WIDTH = 120
RING_HEIGHT = 80
_RING_CENTER = (60, 40)
_OUTER_RADIUS = (50, 31)
_INNER_RADIUS = (25, 14)

_RING_HULL = world.Tile(
    kind="ring_hull", char="#", walkable=False,
    fg=(135, 175, 195), bg=(22, 34, 48),
    blocked_message="The station hull blocks your path.",
)
_RING_VOID = world.Tile(
    kind="ring_void", char=" ", walkable=False,
    fg=(5, 10, 18), bg=(2, 5, 10),
    blocked_message="The open station core is not pressurized.",
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "ac_ring_spaceport": world.Position(52, 10),
    "ac_ring_archive": world.Position(73, 15),
    "ac_ring_lab": world.Position(73, 53),
    "ac_ring_commons": world.Position(92, 35),
    "ac_ring_observation": world.Position(16, 35),
}


def _ellipse_value(x: int, y: int, radii: tuple[int, int]) -> float:
    """Return normalized squared distance from the station center."""
    dx = (x - _RING_CENTER[0]) / radii[0]
    dy = (y - _RING_CENTER[1]) / radii[1]
    return dx * dx + dy * dy


def _in_ring(x: int, y: int) -> bool:
    """Whether a cell lies in the pressurized annulus."""
    return (
        _ellipse_value(x, y, _OUTER_RADIUS) <= 1.0
        and _ellipse_value(x, y, _INNER_RADIUS) > 1.0
    )


def _base_tiles(theme):
    """Create a void field and paint the station's pressurized annulus."""
    deck = world.Tile(
        kind="ring_deck", char=".", walkable=True,
        fg=theme.floor.fg, bg=theme.floor.bg,
    )
    tiles = [
        [world.Tile(
            kind="ring_void", char=" ", walkable=False,
            fg=_RING_VOID.fg, bg=_RING_VOID.bg,
            blocked_message=_RING_VOID.blocked_message,
        ) for _ in range(RING_WIDTH)]
        for _ in range(RING_HEIGHT)
    ]
    ring_cells: set[tuple[int, int]] = set()
    for y in range(RING_HEIGHT):
        for x in range(RING_WIDTH):
            if _in_ring(x, y):
                tiles[y][x] = deck
                ring_cells.add((x, y))

    # The inner and outer pressure boundaries read as structural hull bands.
    for x, y in tuple(ring_cells):
        if any(
            (nx, ny) not in ring_cells
            for nx, ny in (
                (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1),
            )
            if 0 <= nx < RING_WIDTH and 0 <= ny < RING_HEIGHT
        ):
            tiles[y][x] = _RING_HULL
    return tiles, ring_cells


def _paint_path_cell(tiles, x: int, y: int, tile, ring_cells) -> None:
    """Paint a ring route without erasing an authored boundary."""
    if (x, y) in ring_cells and tiles[y][x].kind == "ring_deck":
        tiles[y][x] = tile


def _paint_ring_routes(tiles, theme, ring_cells) -> None:
    """Paint an orbital boulevard, sidewalks, and four spoke crossings."""
    for y in range(RING_HEIGHT):
        for x in range(RING_WIDTH):
            if (x, y) not in ring_cells:
                continue
            radius = _ellipse_value(x, y, _OUTER_RADIUS) ** 0.5
            if 0.72 <= radius <= 0.82:
                _paint_path_cell(tiles, x, y, theme.road_surface, ring_cells)
            elif 0.64 <= radius < 0.72 or 0.82 < radius <= 0.90:
                _paint_path_cell(tiles, x, y, theme.sidewalk, ring_cells)

    # Four structural crossways connect opposite sectors through the void.
    for y in range(9, 72):
        for x in (59, 60, 61):
            if 0 <= y < RING_HEIGHT:
                tiles[y][x] = theme.road_surface
    for x in range(10, 111):
        for y in (39, 40, 41):
            if 0 <= x < RING_WIDTH:
                tiles[y][x] = theme.road_surface

    # A small central transfer hub makes the spokes legible as infrastructure.
    for y in range(38, 43):
        for x in range(58, 63):
            tiles[y][x] = theme.plaza
    for x, y in ((60, 36), (60, 44), (56, 40), (64, 40)):
        tiles[y][x] = theme.neon


def _paint_dock_apron(tiles, theme, spec) -> None:
    """Reserve the top-sector dock apron around the player berth."""
    berth = spec.hangar_anchor
    for y in range(19, 26):
        for x in range(53, 68):
            if 0 <= x < RING_WIDTH and 0 <= y < RING_HEIGHT:
                tiles[y][x] = theme.landing_pad
    tiles[berth.y][berth.x] = theme.plaza
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x, y = berth.x + dx, berth.y + dy
        if 0 <= x < RING_WIDTH and 0 <= y < RING_HEIGHT:
            tiles[y][x] = theme.neon


def _paint_station_details(tiles, theme, ring_cells) -> None:
    """Add sparse ring lights and sector markers without cluttering routes."""
    details = (
        (31, 18), (41, 12), (79, 27), (97, 28),
        (96, 53), (78, 65), (40, 68), (22, 53),
        (23, 28), (42, 55),
    )
    for x, y in details:
        if (x, y) in ring_cells and tiles[y][x].walkable:
            tiles[y][x] = theme.neon


def _add_service_entities(game_map, spec, resolve_ship) -> None:
    """Place showroom ships and a readable service cluster in the dock."""
    add_showroom_ships(
        game_map, spec, resolve_ship,
        origin=world.Position(54, 20),
    )
    add_service_terminals(
        game_map, spec,
        dy=3, dxs=(-4, 0, 4),
        palette=((100, 220, 255), (200, 220, 100), (255, 160, 80)),
    )


def _set_metadata(game_map, spec, stamps, ring_cells) -> None:
    """Attach ring geometry and shared city metadata."""
    game_map.city_layout_id = spec.city_layout_id or "ac_ring_station"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "ac_ring_")
    game_map.ring_geometry = {
        "center": _RING_CENTER,
        "outer_radius": _OUTER_RADIUS,
        "inner_radius": _INNER_RADIUS,
        "ring_cells": ring_cells,
    }
    game_map.ring_void_cells = {
        (x, y)
        for y in range(RING_HEIGHT)
        for x in range(RING_WIDTH)
        if game_map.tiles[y][x].kind == "ring_void"
    }


def build_ac_ring_layout(spec, resolve_ship) -> world.GameMap:
    """Build Alpha Centauri's 120x80 orbital ring station."""
    theme = _readable_city_theme(RING_STATION)
    theme = replace(
        theme,
        landing_pad=replace(theme.landing_pad, char=" "),
    )
    tiles, ring_cells = _base_tiles(theme)
    _paint_ring_routes(tiles, theme, ring_cells)
    _paint_dock_apron(tiles, theme, spec)
    _paint_station_details(tiles, theme, ring_cells)
    game_map = world.GameMap(
        width=RING_WIDTH, height=RING_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    if any(
        (x, y) not in ring_cells
        for stamp in stamps.values()
        for x, y in stamp.footprint
    ):
        raise ValueError("Alpha Centauri landmark footprint leaves the station ring")
    paint_roof_labels(game_map, stamps, "ac_ring_")
    _set_metadata(game_map, spec, stamps, ring_cells)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


__all__ = ["build_ac_ring_layout", "LANDMARK_ORIGINS"]
