"""Shared target-card geometry: map positions → anchored :class:`TargetCard`.

Ground and space combat build the same floating info card; only the stat
rows differ. This module holds the camera/viewport math so each domain's
presentation module supplies just its row formatting.
"""

from __future__ import annotations

from .. import world
from ..pygame_target_card import TargetCard


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
    )
