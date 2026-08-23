"""Shared machinery for authored city layouts (Earth, Mercury, ...).

A *layout* in the generic city pipeline owns its terrain and authored
assets; the pieces below are common to every authored layout:

* :func:`stamp_city_assets` — copy authored exterior landmarks at their
  fixed origins and connect each door to the nearest road with sidewalk.
* :func:`paint_roof_labels` — carve each enterable building's name into
  its roof as readable text.
* :func:`paint_skyline` — fill free blocks with decorative (non-enterable)
  buildings, seeded per layout so each city keeps a deterministic look.
* :func:`building_records` — the data-driven exterior/interior records
  that make interiors work on any planet.
* :func:`stamp_metadata` — the persisted ``landmark_stamps`` shape.

Earth's river-coast terrain (``earth_city.build_earth_layout``) and
Mercury's station deck (``mercury_city.build_mercury_layout``) are thin
layouts over this shared machinery — same pipeline, different data.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from . import city_landmarks, world
from .engine import seeded_rng


_SKYLINE_SEED: int = 1
_SKYLINE_AVOID_KINDS: frozenset[str] = frozenset({
    "road", "city_water", "city_shore", "city_bridge", "landing_pad",
    "sidewalk", "city_plaza", "city_fountain", "city_ornament",
})
# Roof-label characters: bright, crisp, readable on every roof band.
_ROOF_LABEL_FG: tuple[int, int, int] = (244, 246, 240)


def stamp_city_assets(game_map: world.GameMap, origins) -> dict[str, city_landmarks.CityLandmarkStamp]:
    """Stamp all authored exteriors and return their placement data.

    ``origins`` maps each ``layout_id`` to its fixed ``Position``.
    After stamping, every door gets a sidewalk route to the nearest
    public route (road / bridge / landing pad).
    """
    stamps = {
        layout_id: city_landmarks.stamp_city_landmark(
            game_map, layout_id, origin,
        )
        for layout_id, origin in origins.items()
    }
    for stamp in stamps.values():
        if stamp.entrance is None:
            continue
        route = _sidewalk_route(
            game_map, (stamp.entrance.x, stamp.entrance.y + 1),
        )
        for x, y in route:
            if game_map.tiles[y][x].kind in {"road", "city_bridge", "landing_pad"}:
                continue
            game_map.tiles[y][x] = world.SIDEWALK
    return stamps


def _sidewalk_route(
    game_map: world.GameMap,
    start: tuple[int, int],
) -> list[tuple[int, int]]:
    """Find a walkable route from a door to the nearest public route."""
    route_kinds = {"road", "city_bridge", "landing_pad"}
    blocked_kinds = {
        "city_building_floor", "city_building_door", "city_building_wall",
    }
    queue = deque([start])
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while queue:
        point = queue.popleft()
        if game_map.tiles[point[1]][point[0]].kind in route_kinds:
            path: list[tuple[int, int]] = []
            while point is not None:
                path.append(point)
                point = previous[point]
            return list(reversed(path))
        for dx, dy in ((0, 1), (-1, 0), (1, 0), (0, -1)):
            next_point = (point[0] + dx, point[1] + dy)
            if next_point in previous or not game_map.in_bounds(*next_point):
                continue
            tile = game_map.tiles[next_point[1]][next_point[0]]
            if not tile.walkable or tile.kind in blocked_kinds:
                continue
            previous[next_point] = point
            queue.append(next_point)
    return []


def paint_roof_labels(game_map: world.GameMap, stamps, prefix: str) -> None:
    """Carve each enterable building's name into its roof as readable text.

    Bright letters replace the roof cells on a single centered band, so
    the building reads as a rooftop sign while staying fully non-walkable.
    ``prefix`` is stripped from each layout id to recover the building
    label (e.g. ``\"earth_city_\"`` or ``\"mercury_\"``).
    """
    for layout_id, stamp in stamps.items():
        label = layout_id.removeprefix(prefix).upper()
        if label in {"PLAZA", "COMMONS"}:
            continue
        xs = [x for x, _ in stamp.footprint]
        ys = [y for _, y in stamp.footprint]
        x_lo, x_hi = min(xs), max(xs)
        y_lo, y_hi = min(ys), max(ys)
        row = (y_lo + y_hi) // 2
        start = (x_lo + x_hi) // 2 - len(label) // 2
        for index, ch in enumerate(label):
            x = start + index
            if not (x_lo < x < x_hi):
                continue
            bg = game_map.tiles[row][x].bg
            game_map.tiles[row][x] = world.Tile(
                kind="city_building_wall", char=ch, walkable=False,
                fg=_ROOF_LABEL_FG, bg=bg,
                blocked_message="The building wall blocks your path.",
            )


def building_records(spec, stamps, prefix: str) -> dict:
    """Build data-driven exterior/interior records for spec buildings.

    One record per stamped building keyed by label, with the interior
    layout id from ``spec.interior_layouts`` and the entrance taken from
    the stamped asset's door cell.
    """
    layout_by_label = {
        layout_id.removeprefix(prefix): stamp
        for layout_id, stamp in stamps.items()
        if layout_id.removeprefix(prefix) != "plaza"
    }
    return {
        building.label: {
            "label": building.label,
            "display_name": building.label.replace("_", " "),
            "npc_id": building.npc_id,
            "interior_layout_id": dict(spec.interior_layouts).get(building.label, ""),
            "entrance": (
                (stamp.entrance.x, stamp.entrance.y)
                if (stamp := layout_by_label[building.label]).entrance is not None
                else None
            ),
            "cache_key": f"city:{spec.id}:{building.label}",
        }
        for building in spec.buildings
        if building.label in layout_by_label
    }


def stamp_metadata(stamps) -> dict:
    """Serialize stamped landmarks to the persisted metadata shape."""
    return {
        layout_id: {
            "origin": (stamp.origin.x, stamp.origin.y),
            "footprint": set(stamp.footprint),
            "entrance": (
                (stamp.entrance.x, stamp.entrance.y)
                if stamp.entrance is not None else None
            ),
        }
        for layout_id, stamp in stamps.items()
    }


# ---------------------------------------------------------------------------
# Procedural skyline — decorative buildings filling free city blocks
# ---------------------------------------------------------------------------


def _skyline_tile(
    char: str,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
) -> world.Tile:
    """Build one non-walkable skyline roof/wall tile."""
    return world.Tile(
        kind="city_building_wall", char=char, walkable=False,
        fg=fg, bg=bg,
        blocked_message="The building wall blocks your path.",
    )


def _building_site_free(
    tiles: list[list[world.Tile]],
    x: int, y: int, w: int, h: int,
    site_kinds: frozenset[str],
    avoid_kinds: frozenset[str],
) -> bool:
    """Whether a ``w x h`` footprint at ``(x, y)`` is a clear site.

    Every footprint cell must be one of ``site_kinds`` (park grass on
    Earth, bare deck on Mercury) and the site must not sit orthogonally
    against ``avoid_kinds`` (roads, water, pads, plazas...). Earth keeps
    a strict buffer so buildings never touch the circulation network;
    a compact station may relax it so utility domes can line its roads.
    """
    for by in range(y, y + h):
        for bx in range(x, x + w):
            if tiles[by][bx].kind not in site_kinds:
                return False
    for by in range(y, y + h):
        for bx in range(x, x + w):
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                if tiles[by + dy][bx + dx].kind in avoid_kinds:
                    return False
    return True


def _paint_one_skyline_building(
    tiles: list[list[world.Tile]],
    x: int, y: int, w: int, h: int,
    rng,
    schemes,
    roof_char: str,
) -> None:
    """Paint one solid decorative building: a calm roof block."""
    wall_fg, wall_bg, roof_fg, roof_bg = rng.choice(schemes)
    wall = _skyline_tile("#", wall_fg, wall_bg)
    roof = _skyline_tile(roof_char, roof_fg, roof_bg)
    for by in range(y, y + h):
        for bx in range(x, x + w):
            if by in (y, y + h - 1) or bx in (x, x + w - 1):
                tiles[by][bx] = wall
            else:
                tiles[by][bx] = roof


def _fit_skyline_building(
    tiles: list[list[world.Tile]],
    x: int, y: int, bw: int, bh: int,
    site_kinds: frozenset[str],
    avoid_kinds: frozenset[str],
) -> tuple[int, int] | None:
    """Return a slightly smaller size that fits, or ``None``."""
    for nbw, nbh in (
        (bw - 1, bh), (bw, bh - 1),
        (bw - 1, bh - 1), (bw - 2, bh - 1),
    ):
        if nbw >= 5 and nbh >= 4 and _building_site_free(
            tiles, x, y, nbw, nbh, site_kinds, avoid_kinds,
        ):
            return nbw, nbh
    return None


@dataclass(frozen=True)
class _SkylineParams:
    """Tuning knobs for one layout's procedural skyline."""

    site_kinds: frozenset[str]
    avoid_kinds: frozenset[str]
    schemes: tuple
    roof_char: str
    width_range: tuple[int, int]
    height_range: tuple[int, int]
    min_size: tuple[int, int]


def _fit_or_skip(
    tiles, rng, params, x, y,
) -> tuple[int, int, bool]:
    """Return ``(bw, bh, placed)`` for one candidate site at ``(x, y)``.

    Picks a random size, fits it down when the site is blocked, and
    paints the building in place. ``placed=False`` means the scan should
    advance one column and retry.
    """
    bw = min(rng.randint(*params.width_range), len(tiles[0]) - 2 - x)
    bh = min(rng.randint(*params.height_range), len(tiles) - 2 - y)
    if bw < params.min_size[0] or bh < params.min_size[1]:
        return 0, 0, False
    if not _building_site_free(
        tiles, x, y, bw, bh, params.site_kinds, params.avoid_kinds,
    ):
        fitted = _fit_skyline_building(
            tiles, x, y, bw, bh, params.site_kinds, params.avoid_kinds,
        )
        if fitted is None:
            return 0, 0, False
        bw, bh = fitted
    _paint_one_skyline_building(
        tiles, x, y, bw, bh, rng, params.schemes, params.roof_char,
    )
    return bw, bh, True


def _fill_skyline_row(game_map, rng, params, y, placements) -> None:
    """Scan one skyline row, painting buildings on every free site."""
    tiles = game_map.tiles
    x = 2
    while x < game_map.width - 2:
        if tiles[y][x].kind not in params.site_kinds:
            x += 1
            continue
        bw, bh, placed = _fit_or_skip(tiles, rng, params, x, y)
        if not placed:
            x += 1
            continue
        placements.append((x, y, bw, bh))
        x += bw + 2


def paint_skyline(
    game_map: world.GameMap,
    *,
    seed_key: tuple[str, str],
    schemes,
    site_kinds: frozenset[str] = frozenset({"grass"}),
    avoid_kinds: frozenset[str] = _SKYLINE_AVOID_KINDS,
    roof_char: str = ".",
    width_range: tuple[int, int] = (6, 12),
    height_range: tuple[int, int] = (5, 9),
    min_size: tuple[int, int] = (5, 4),
    row_stride: int = 1,
) -> None:
    """Fill every free city block with varied decorative buildings.

    Buildings are solid, non-walkable roof blocks in a range of sizes
    and muted colour schemes. The fixed seed key keeps the skyline
    identical across runs and save/load rebuilds. ``site_kinds`` names
    the tile kinds buildings may sit on (park grass, or bare deck on a
    station), ``avoid_kinds`` the tiles buildings must not touch (Earth
    keeps a strict buffer; a compact station may relax it so domes can
    line its roads), and ``row_stride`` > 1 scans fewer rows for a
    sparser fill.
    """
    params = _SkylineParams(
        site_kinds=site_kinds, avoid_kinds=avoid_kinds, schemes=schemes,
        roof_char=roof_char, width_range=width_range,
        height_range=height_range, min_size=min_size,
    )
    rng = seeded_rng(_SKYLINE_SEED, *seed_key)
    placements: list[tuple[int, int, int, int]] = []
    for y in range(2, game_map.height - 2, row_stride):
        _fill_skyline_row(game_map, rng, params, y, placements)
    game_map.skyline_placements = placements


__all__ = [
    "stamp_city_assets", "paint_roof_labels", "building_records",
    "stamp_metadata", "paint_skyline",
]
