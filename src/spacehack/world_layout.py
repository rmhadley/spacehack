"""City building factories and the compact planetary-city layout pass.

This module holds the authored-buildings helpers (:func:`make_building`,
:func:`make_space_port`), the compact 60x40 city dressing pass
(:func:`_layout_outside`), and the default building catalog
(:data:`CITY_BUILDINGS`). It is split out of :mod:`spacehack.world` so the
shared game-world module stays within the project architecture budget.

Importing :mod:`spacehack.world` re-exports every public name here, so existing
``world.make_building`` / ``world._layout_outside`` call sites are unchanged.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from . import world


# ---------------------------------------------------------------------------
# Labeled buildings (one factory, used by space port AND guild halls)
# ---------------------------------------------------------------------------


# ``spaceport`` is the default building label; guild halls pass their
# own label string (``bar``, ``merchants``, ``militia``, ``bounties``).
SPACEPORT_LABEL: str = "spaceport"
SPACEPORT_LABEL_FG: tuple[int, int, int] = (220, 220, 220)

# Per-building label colors so each guild reads as distinct at a
# glance. Looked up by :func:`make_building`; unknown labels fall
# back to ``SPACEPORT_LABEL_FG``.
BUILDING_LABEL_COLORS: dict[str, tuple[int, int, int]] = {
    "spaceport": (100, 220, 255),       # bright cyan - space commerce
    "bar":       (255, 200, 80),         # warm gold - tavern / nightlife
    "bounties":  (255, 130, 200),        # vivid magenta - danger / reward
    "merchants": (140, 240, 140),        # soft green - wealth / trade
    "militia":   (130, 230, 220),        # teal - order / defence
    "depot":     (200, 200, 160),        # warm grey - utility / refueling
    "lab":       (150, 220, 200),        # teal-cyan - research / science
}


def _validate_building(x_lo: int, x_hi: int, y_lo: int, y_hi: int, label: str) -> None:
    """Raise on a building rectangle that can't fit walls + label + door."""
    if x_hi - x_lo < 4 or y_hi - y_lo < 4:
        raise ValueError("building must be at least 5x5 to fit walls + interior")
    if len(label) > x_hi - x_lo + 1:
        raise ValueError(
            f"building label {label!r} ({len(label)} chars) "
            f"is wider than the wall ({x_hi - x_lo + 1} cells)"
        )


def _building_corners(
    x_lo: int, x_hi: int, y_lo: int, y_hi: int,
) -> list[tuple[world.Position, world.Tile]]:
    """Return the four box-drawing corner overwrites for a building."""
    return [
        (world.Position(x_lo, y_lo), world.WALL_TL),
        (world.Position(x_hi, y_lo), world.WALL_TR),
        (world.Position(x_lo, y_hi), world.WALL_BL),
        (world.Position(x_hi, y_hi), world.WALL_BR),
    ]


def _paint_door_wall(
    changes: list, x_lo: int, x_hi: int, y: int, door_x: int,
) -> None:
    """Paint one wall row with a single door at ``door_x``, walls elsewhere."""
    for x in range(x_lo + 1, x_hi):
        changes.append(
            (world.Position(x, y), world.DOOR if x == door_x else world.WALL_H)
        )


def _paint_label_wall(
    changes: list, label: str, x_lo: int, x_hi: int, y: int,
    label_x_start: int, label_fg: tuple[int, int, int],
) -> None:
    """Paint one wall row with the building's name carved into it."""
    for x in range(x_lo + 1, x_hi):
        if not (label_x_start <= x < label_x_start + len(label)):
            changes.append((world.Position(x, y), world.WALL_H))
    for index, ch in enumerate(label):
        changes.append((
            world.Position(label_x_start + index, y),
            world.Tile(
                kind="label", char=ch, walkable=False,
                fg=label_fg, bg=world.WALL_H.bg,
            ),
        ))


def _append_vertical_walls(tile_changes, x_lo: int, x_hi: int, y_lo: int, y_hi: int) -> None:
    """Append the left/right box-drawing walls between a building's corners."""
    for y in range(y_lo + 1, y_hi):
        tile_changes.append((world.Position(x_lo, y), world.WALL_V))
        tile_changes.append((world.Position(x_hi, y), world.WALL_V))


def _interior_occupant(
    occupant: world.Entity | None, x_lo: int, x_hi: int, y_lo: int, y_hi: int,
) -> list[world.Entity]:
    """Return ``[occupant]`` re-anchored to the interior center, else empty."""
    if occupant is None:
        return []
    occupant.pos = world.Position((x_lo + x_hi) // 2, (y_lo + y_hi) // 2)
    return [occupant]


def make_building(
    label: str,
    x_lo: int, x_hi: int, y_lo: int, y_hi: int,
    *,
    door_x: int | None = None,
    occupant: world.Entity | None = None,
    door_north: bool = False,
) -> tuple[list[tuple[world.Position, world.Tile]], list[world.Entity]]:
    """Build a labeled rectangular building; returns ``(tile_changes, entities)``.

    ``door_north`` flips the door/label walls. Raises on an undersized or
    label-too-wide rectangle.
    """
    _validate_building(x_lo, x_hi, y_lo, y_hi, label)
    if door_x is None:
        door_x = (x_lo + x_hi) // 2
    label_x_start = x_lo + (x_hi - x_lo + 1 - len(label)) // 2
    label_fg = BUILDING_LABEL_COLORS.get(label, SPACEPORT_LABEL_FG)

    tile_changes = _building_corners(x_lo, x_hi, y_lo, y_hi)
    if door_north:
        _paint_door_wall(tile_changes, x_lo, x_hi, y_lo, door_x)
        _paint_label_wall(tile_changes, label, x_lo, x_hi, y_hi, label_x_start, label_fg)
    else:
        _paint_label_wall(tile_changes, label, x_lo, x_hi, y_lo, label_x_start, label_fg)
        _paint_door_wall(tile_changes, x_lo, x_hi, y_hi, door_x)
    _append_vertical_walls(tile_changes, x_lo, x_hi, y_lo, y_hi)
    return tile_changes, _interior_occupant(occupant, x_lo, x_hi, y_lo, y_hi)


def _showroom_ships(
    x_lo: int, y_lo: int,
) -> list[world.Entity]:
    """Return the three on-display showroom ships for the space port."""
    return [
        world.Entity(
            char="s", fg=(130, 220, 255),
            pos=world.Position(x=x_lo + 3, y=y_lo + 2),
            name="Ship: Scout", ship_id="scout", width=1, height=1,
        ),
        world.Entity(
            char="H", fg=(140, 210, 140),
            pos=world.Position(x=x_lo + 7, y=y_lo + 2),
            name="Ship: Hauler", ship_id="hauler", width=2, height=1,
        ),
        world.Entity(
            char="C", fg=(235, 130, 130),
            pos=world.Position(x=x_lo + 11, y=y_lo + 4),
            name="Ship: Cruiser", ship_id="cruiser", width=2, height=2,
        ),
    ]


def make_space_port(
    x_lo: int, x_hi: int, y_lo: int, y_hi: int,
    *,
    door_x: int | None = None,
    label: str = SPACEPORT_LABEL,
) -> tuple[list[tuple[world.Position, world.Tile]], list[world.Entity]]:
    """Build the space-port building: a labeled rectangular building
    (no NPC) plus the three ships on display inside.

    A thin composition over :func:`make_building` plus the fixed ship
    placements, kept for callers that use the ``(tile_changes, ships)`` shape.
    """
    tile_changes, _npcs = make_building(
        label, x_lo, x_hi, y_lo, y_hi, door_x=door_x,
    )
    return tile_changes, _showroom_ships(x_lo, y_lo)


# ---------------------------------------------------------------------------
# Building-interior decoration
# ---------------------------------------------------------------------------


def _decorate_interiors(
    tiles: list[list[world.Tile]],
    buildings: "tuple[CityBuilding, ...]",
) -> None:
    """Paint furniture + detail tiles into building interiors after
    step 7 has filled them with :data:`world.INTERIOR`."""
    _decorate_bar(tiles, buildings)


def _paint_bar_drinks(
    tiles: list[list[world.Tile]], bar, row_11_y: int,
) -> None:
    """Paint the bar's drinks + table row (left half of the interior)."""
    drink_positions: list[tuple[int, world.Tile]] = [
        (bar.x_lo + 1, world.DRINK),
        (bar.x_lo + 2, world.TABLE),
        (bar.x_lo + 3, world.DRINK),
        (bar.x_lo + 4, world.TABLE),
        (bar.x_lo + 5, world.INTERIOR),
    ]
    for ix, tile in drink_positions:
        tiles[row_11_y][ix] = tile


def _decorate_bar(
    tiles: list[list[world.Tile]],
    buildings: "tuple[CityBuilding, ...]",
) -> None:
    """Paint a bar counter with stools and a drinks table.

    The 8x6 bar (x=34..41, y=8..13) has a counter top row, a counter body
    row holding the barkeep, and a drinks/table row.
    """
    bar = next((b for b in buildings if b.label == "bar"), None)
    if bar is None:
        return
    npc_x = (bar.x_lo + bar.x_hi) // 2
    npc_y = (bar.y_lo + bar.y_hi) // 2

    for ix in range(bar.x_lo + 1, bar.x_hi):
        tiles[bar.y_lo + 1][ix] = world.BAR_COUNTER
    for ix in range(bar.x_lo + 1, bar.x_hi):
        if ix != npc_x:
            tiles[npc_y][ix] = world.BAR_BODY
    _paint_bar_drinks(tiles, bar, bar.y_lo + 3)


# Buildings the city spawns at make_city time. Coords are picked so
# that no two building rectangles overlap, the player can walk
# between them on the new roads, and the south-door of every
# building faces open city floor (no overlap with perimeter walls,
# perimeter city-exit doors, the wandering merchant NPC, or any
# other building).
@dataclass(frozen=True)
class CityBuilding:
    label: str
    x_lo: int
    x_hi: int
    y_lo: int
    y_hi: int
    door_x: int
    npc_id: str
    door_north: bool = False  # True: door on north wall, label on south wall


CITY_BUILDINGS: "tuple[CityBuilding, ...]" = (
    # Space port (commerce-heavy, NW): 20x10, door at midpoint.
    CityBuilding(label="spaceport", x_lo=4, x_hi=23, y_lo=3, y_hi=12, door_x=13, npc_id=""),
    # Bar (small tavern, NE): 8x6, north of the BH guild.
    CityBuilding(label="bar", x_lo=34, x_hi=41, y_lo=8, y_hi=13, door_x=37, npc_id="barkeep"),
    # Bounty hunter guild (medium, NE under the bar): 15x11.
    CityBuilding(label="bounties", x_lo=43, x_hi=57, y_lo=5, y_hi=15, door_x=50, npc_id="bounty_master"),
    # Merchant guild (big emporium, SW): 21x12.
    CityBuilding(label="merchants", x_lo=4, x_hi=24, y_lo=25, y_hi=36, door_x=14, npc_id="guild_master"),
    # Militia center (medium barracks, SE): 16x10.
    CityBuilding(label="militia", x_lo=40, x_hi=55, y_lo=26, y_hi=35, door_x=47, npc_id="militia_captain"),
)


# ---------------------------------------------------------------------------
# Compact 60x40 city layout
# ---------------------------------------------------------------------------


def _paint_main_roads(tiles, width: int, height: int, theme) -> None:
    """3-tile-wide N/S and E/W roads with centre-lane markings."""
    _rs, _ns, _ew = theme.road_surface, theme.road_ns, theme.road_ew
    for y in range(1, 17):
        tiles[y][29], tiles[y][30], tiles[y][31] = _rs, _ns, _rs
    for y in range(24, height - 1):
        tiles[y][29], tiles[y][30], tiles[y][31] = _rs, _ns, _rs
    for x in range(1, 27):
        tiles[19][x], tiles[20][x], tiles[21][x] = _rs, _ew, _rs
    for x in range(34, width - 1):
        tiles[19][x], tiles[20][x], tiles[21][x] = _rs, _ew, _rs


def _paint_plaza(tiles, width: int, height: int, theme) -> None:
    """9x9 central plaza with jewel fountain accents."""
    for y in range(16, 25):
        for x in range(26, 35):
            tiles[y][x] = theme.plaza
    for dx, dy in ((28, 18), (32, 18), (28, 22), (32, 22)):
        if 0 <= dx < width and 0 <= dy < height:
            tiles[dy][dx] = theme.decor


def _walk_one_direction(
    tiles, theme, path_x_lo: int, path_x_hi: int, sy: int, step: int, limit: int,
) -> None:
    """Paint a sidewalk strip from ``sy`` stepping ``step`` toward ``limit``."""
    while sy != limit:
        if any(tiles[sy][sx].kind == "road" for sx in range(path_x_lo, path_x_hi + 1)):
            break
        blocked = any(
            tiles[sy][sx].kind not in ("floor", "sidewalk", "plaza")
            for sx in range(path_x_lo, path_x_hi + 1)
        )
        if blocked:
            break
        for sx in range(path_x_lo, path_x_hi + 1):
            tiles[sy][sx] = theme.sidewalk
        sy += step


def _paint_walkways(tiles, height: int, buildings, theme) -> None:
    """Narrow 3-tile walkways from each building door to the nearest road."""
    for spec in buildings:
        door_x = spec.door_x
        path_x_lo = max(door_x - 1, spec.x_lo)
        path_x_hi = min(door_x + 1, spec.x_hi)
        if spec.door_north:
            _walk_one_direction(tiles, theme, path_x_lo, path_x_hi, spec.y_lo - 1, -1, 0)
        else:
            _walk_one_direction(tiles, theme, path_x_lo, path_x_hi, spec.y_hi + 1, 1, height - 1)


def _paint_port_pad_and_neon(tiles, width: int, height: int, buildings, theme) -> None:
    """Landing pad south of the spaceport plus neon signs."""
    spaceport = next((b for b in buildings if b.label == "spaceport"), None)
    if spaceport is not None:
        pad_centre = (spaceport.x_lo + spaceport.x_hi) // 2
        for py in range(spaceport.y_hi + 1, 18):
            for px in range(pad_centre - 5, pad_centre + 6):
                if 0 <= px < width and 0 <= py < height:
                    tiles[py][px] = theme.landing_pad
        door_col = spaceport.door_x
        neon_y = spaceport.y_hi + 1
        if 0 <= door_col - 1 < width:
            tiles[neon_y][door_col - 1] = theme.neon
        if 0 <= door_col + 1 < width:
            tiles[neon_y][door_col + 1] = theme.neon
    for n_x, n_y in ((30, 16), (30, 24), (26, 20), (34, 20)):
        if 0 <= n_x < width and 0 <= n_y < height:
            tiles[n_y][n_x] = theme.neon


def _grassify_floor(tiles, width: int, height: int, theme) -> None:
    """Convert every remaining bare FLOOR cell to GRASS."""
    for fy in range(1, height - 1):
        for fx in range(1, width - 1):
            if tiles[fy][fx].kind == "floor":
                tiles[fy][fx] = (
                    theme.grass_accent if random.random() < 0.15 else theme.grass
                )


def _restore_and_decorate_interiors(tiles, buildings) -> None:
    """Repaint building interiors back to INTERIOR floor and decorate them."""
    for spec in buildings:
        for iy in range(spec.y_lo + 1, spec.y_hi):
            for ix in range(spec.x_lo + 1, spec.x_hi):
                tiles[iy][ix] = world.INTERIOR
    _decorate_interiors(tiles, buildings)


def _paint_trees(tiles, height: int, theme) -> None:
    """Tree accents along the N/S road edge and inside parks."""
    for ry in range(1, height - 1):
        if tiles[ry][28].kind in ("grass", "road", "sidewalk") and ry % 4 == 0:
            tiles[ry][28] = theme.tree
        if tiles[ry][32].kind in ("grass", "road", "sidewalk") and ry % 4 == 2:
            tiles[ry][32] = theme.tree
    for tx, ty in ((6, 22), (10, 23), (18, 23), (22, 22)):
        if tiles[ty][tx].kind == "grass":
            tiles[ty][tx] = theme.tree
    for tx, ty in ((42, 23), (45, 25), (52, 24)):
        if tiles[ty][tx].kind == "grass":
            tiles[ty][tx] = theme.tree


def _layout_outside(
    tiles: list[list[world.Tile]],
    width: int,
    height: int,
    buildings: "tuple[CityBuilding, ...]",
    theme=world.EARTH_THEME,
) -> None:
    """Carve roads + plaza + purposeful green spaces into the compact city.

    Sized for the canonical 60x40 planetary city template; smaller planets
    early-return so they stay a bare interior. ``theme`` provides the
    per-planet tile colours (roads, plaza, landing pad, neon, etc.).
    """
    if width != 60 or height != 40:
        return
    _paint_main_roads(tiles, width, height, theme)
    _paint_plaza(tiles, width, height, theme)
    _paint_walkways(tiles, height, buildings, theme)
    _paint_port_pad_and_neon(tiles, width, height, buildings, theme)
    _grassify_floor(tiles, width, height, theme)
    _restore_and_decorate_interiors(tiles, buildings)
    _paint_trees(tiles, height, theme)


def make_city(width: int = 60, height: int = 40) -> world.GameMap:
    """Back-compat shim: build the Earth on-surface city from the planet loader."""
    from .data.planets import load_planet
    del width, height
    return load_planet("earth")


__all__ = [
    "SPACEPORT_LABEL", "SPACEPORT_LABEL_FG", "BUILDING_LABEL_COLORS",
    "CityBuilding", "CITY_BUILDINGS",
    "make_building", "make_space_port", "_decorate_interiors", "_decorate_bar",
    "_layout_outside", "make_city",
]
