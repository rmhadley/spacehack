"""Shared target-card geometry: map positions → anchored :class:`TargetCard`.

Ground and space combat build the same floating info card; only the stat
rows differ. This module holds the camera/viewport math so each domain's
presentation module supplies just its row formatting.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from .. import world
from ..hud import range_band_color
from ..pygame_target_card import TargetCard


def hit_color_for_weapon(
    weapon_id: str | None,
    target_pos: world.Position,
    player_pos: world.Position,
    find_weapon: Callable[[str], Any],
    *,
    distance_round: Callable[[float], float] | None = None,
    weapon_range: tuple[int, int] | None = None,
) -> tuple[int, int, int] | None:
    """Range-band color for a weapon's HIT % on the target card, or None.

    Resolves ``weapon_id`` through ``find_weapon`` and colors by the
    targeting-line range bands between ``player_pos`` and ``target_pos``.
    ``distance_round`` normalizes the raw Euclidean distance to the
    domain's fire-gate math (ground passes ``int``); ``weapon_range``
    overrides the catalog profile with the wielder's effective
    ``(min, max)`` — trait riders like Longshot/Focus move the real
    envelope. ``None`` for unarmed/unknown weapons so the card falls
    back to its default text color.
    """
    if weapon_id is None:
        return None
    try:
        _ws = find_weapon(weapon_id)
    except KeyError:
        return None
    dist = math.hypot(player_pos.x - target_pos.x, player_pos.y - target_pos.y)
    if distance_round is not None:
        dist = distance_round(dist)
    _min, _max = (
        weapon_range if weapon_range is not None
        else (_ws.min_range, _ws.max_range)
    )
    from ._missile_flight import catalog_floor
    _floor = catalog_floor(_ws)
    if _floor > 0:
        _min = _floor  # the refusal band reads the catalog floor (doc 57)
    return range_band_color(dist, _max, _min, hard_floor=_floor > 0)


def viewport_cells(
    positions: tuple[world.Position, ...],
    *,
    cam_x: int,
    cam_y: int,
    rx: int,
    ry: int,
    region_w: int,
    region_h: int,
) -> tuple[tuple[int, int], ...]:
    """Map map positions to viewport cells, dropping any off-screen."""
    cells: list[tuple[int, int]] = []
    for _p in positions:
        _x, _y = rx + _p.x - cam_x, ry + _p.y - cam_y
        if 0 <= _x < region_w and 0 <= _y < region_h:
            cells.append((_x, _y))
    return tuple(cells)


def build_card(
    enemy_pos: world.Position,
    rows,
    *,
    game_map: world.GameMap,
    player_pos: world.Position,
    region_w: int,
    region_h: int,
    avoid_positions: tuple[world.Position, ...] = (),
    quick_rows=(),
) -> TargetCard | None:
    """Anchor pre-formatted ``rows`` near ``enemy_pos``, or None when off-view."""
    cam_x, cam_y, rx, ry = world.camera_for_view(
        game_map, player_pos, region_w=region_w, region_h=region_h,
    )
    sx, sy = rx + enemy_pos.x - cam_x, ry + enemy_pos.y - cam_y
    if not (0 <= sx < region_w and 0 <= sy < region_h):
        return None
    return TargetCard(
        rows=rows,
        x=sx,
        y=sy,
        avoid_cells=viewport_cells(
            avoid_positions,
            cam_x=cam_x, cam_y=cam_y, rx=rx, ry=ry,
            region_w=region_w, region_h=region_h,
        ),
        # Player is always in view; its cell drives away-from-player placement.
        player_cell=(rx + player_pos.x - cam_x, ry + player_pos.y - cam_y),
        quick_rows=tuple(quick_rows),
    )
