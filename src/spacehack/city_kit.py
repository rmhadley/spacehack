"""Shared helpers for the sibling ``*_city.py`` layout builders.

Every authored city repeats the same skeleton: a floor-and-border tile
base, showroom ships plus service terminals on the landing apron,
landmark metadata, transit bays, and door forecourts. This module owns
those shared shapes so each city module only contains what makes it
*distinct* — its terrain painters and landmarks.

Behaviour notes:

* ``add_service_terminals`` places the trade/mechanic/armory terminal
  trio relative to the hangar berth; the offsets, row, and palette are
  parameters because cities legitimately differ in dock layout.
* ``paint_transit_bays`` carves a smooth bay under and around each
  transit stop without touching roads/pads/sidewalks (only the tile
  kinds listed in ``overwrite_kinds`` are replaced).
* ``paint_door_forecourts`` gives every door a three-cell sidewalk
  forecourt on its exit side; pass ``overwrite_kinds=None`` to write
  unconditionally, or a set of tile kinds to only replace those.
"""

from __future__ import annotations

from . import world
from .city_layout import building_records, stamp_metadata


# Terminal fg palettes observed across the sibling cities. New cities
# should default to CLASSIC; older modules keep their exact colours.
TERMINAL_PALETTE_CLASSIC = (
    (100, 220, 255),  # trade
    (210, 220, 110),  # mechanic
    (255, 165, 85),   # armory
)
TERMINAL_PALETTE_EMBER = (
    (140, 230, 255),
    (210, 220, 130),
    (255, 175, 105),
)

_TERMINAL_SPECS = (
    ("=", "Trade Terminal", "trade_terminal"),
    ("%", "Mechanic Terminal", "mech_terminal"),
    ("A", "Armory Terminal", "armory_terminal"),
)


def in_bounds(x: int, y: int, width: int, height: int) -> bool:
    """Return whether ``(x, y)`` lies inside a width×height grid."""
    return 0 <= x < width and 0 <= y < height


def base_tiles(
    width: int, height: int, floor_tile: world.Tile,
) -> list[list[world.Tile]]:
    """Floor fill with an impassable perimeter wall ring."""
    tiles = [[floor_tile for _ in range(width)] for _ in range(height)]
    for x in range(width):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(height):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL
    return tiles


def add_showroom_ships(
    game_map: world.GameMap,
    spec,
    resolve_ship,
    origin: world.Position | None = None,
) -> None:
    """Place the spec's showroom ships relative to ``origin``
    (default: the hangar anchor)."""
    berth = origin or spec.hangar_anchor
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        game_map.entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(berth.x + off_x, berth.y + off_y),
            name=f"Ship: {ship_obj.name}", ship_id=ship_obj.id,
            width=ship_obj.width, height=ship_obj.height,
        ))


def add_service_terminals(
    game_map: world.GameMap,
    spec,
    *,
    dy: int = 3,
    dxs: tuple[int, int, int] = (-6, -2, 2),
    palette: tuple[tuple[int, int, int], ...] = TERMINAL_PALETTE_CLASSIC,
) -> None:
    """Place the trade/mechanic/armory terminal trio near the berth."""
    berth = spec.hangar_anchor
    for (char, name, flag), dx, fg in zip(_TERMINAL_SPECS, dxs, palette):
        game_map.entities.append(world.Entity(
            char=char, fg=fg,
            pos=world.Position(berth.x + dx, berth.y + dy),
            name=name, **{flag: True},
        ))


def set_city_metadata(
    game_map: world.GameMap,
    spec,
    stamps,
    *,
    prefix: str,
    default_layout_id: str,
) -> None:
    """Attach layout id, landmark stamps, and building records."""
    game_map.city_layout_id = spec.city_layout_id or default_layout_id
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, prefix)


def paint_transit_bays(
    tiles: list[list[world.Tile]],
    spec,
    bay_tile: world.Tile,
    *,
    width: int,
    height: int,
    overwrite_kinds: frozenset[str] = frozenset({"floor"}),
    force_center: bool = False,
) -> None:
    """Carve a smooth bay under and around each transit stop.

    Only tile kinds in ``overwrite_kinds`` are replaced so roads,
    pads, sidewalks, and door approaches survive untouched.
    ``force_center`` additionally writes the bay onto the station cell
    itself regardless of kind.
    """
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        if force_center and in_bounds(x, y, width, height):
            tiles[y][x] = bay_tile
        for dyc in (-1, 0, 1):
            for dxc in (-1, 0, 1):
                nx, ny = x + dxc, y + dyc
                if not in_bounds(nx, ny, width, height):
                    continue
                if tiles[ny][nx].kind not in overwrite_kinds:
                    continue
                tiles[ny][nx] = bay_tile


def paint_transit_stops(
    tiles: list[list[world.Tile]],
    spec,
    bay_tile: world.Tile,
    *,
    skip_kinds: frozenset[str] = frozenset(),
) -> None:
    """Place a single-cell bay on each station cell unconditionally
    (except cells whose kind is listed in ``skip_kinds``)."""
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        if tiles[y][x].kind not in skip_kinds:
            tiles[y][x] = bay_tile


def paint_door_forecourts(
    tiles: list[list[world.Tile]],
    theme,
    spec,
    *,
    width: int,
    height: int,
    overwrite_kinds: frozenset[str] | None = None,
) -> None:
    """Give each door a three-cell sidewalk forecourt on its exit side.

    ``overwrite_kinds=None`` writes unconditionally; otherwise only the
    listed tile kinds are replaced. Buildings flagged ``door_north``
    get their forecourt on the north side instead.
    """
    for building in spec.buildings:
        y = (
            building.y_lo - 1 if getattr(building, "door_north", False)
            else building.y_hi + 1
        )
        for x in range(building.door_x - 1, building.door_x + 2):
            if not in_bounds(x, y, width, height):
                continue
            if overwrite_kinds is not None and tiles[y][x].kind not in overwrite_kinds:
                continue
            tiles[y][x] = theme.sidewalk


__all__ = [
    "TERMINAL_PALETTE_CLASSIC",
    "TERMINAL_PALETTE_EMBER",
    "add_service_terminals",
    "add_showroom_ships",
    "base_tiles",
    "in_bounds",
    "paint_door_forecourts",
    "paint_transit_bays",
    "paint_transit_stops",
    "set_city_metadata",
]
