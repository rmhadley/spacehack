"""Tests for dungeon.py — LOS raycasting and fog-of-war.

These are the pure computation functions under the rendering layer.
The stale-LOS bug (da75376) and hull-wall propagation were in this
file — both now have regression tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.world import (
    GameMap, Tile, Position,
    DUNGEON_WALL, DUNGEON_FLOOR, HULL_WALL, VOID, DUNGEON_DOOR,
)
from src.spacehack.dungeon import (
    init_fog,
    _cast_ray,
    reveal_around,
    _propagate_flags,
)


def _make_map(width: int, height: int) -> GameMap:
    """Build a map filled with floor tiles."""
    tiles = [[DUNGEON_FLOOR for _ in range(width)] for _ in range(height)]
    return GameMap(width=width, height=height, tiles=tiles, entities=[])


def _wall_at(gm: GameMap, x: int, y: int) -> None:
    gm.tiles[y][x] = DUNGEON_WALL


def _hull_at(gm: GameMap, x: int, y: int) -> None:
    gm.tiles[y][x] = HULL_WALL


# ---------------------------------------------------------------------------
# init_fog
# ---------------------------------------------------------------------------

class TestInitFog:
    def test_creates_grids(self):
        gm = _make_map(5, 5)
        init_fog(gm)
        assert gm.seen is not None
        assert gm.visible is not None
        assert len(gm.seen) == 5
        assert len(gm.seen[0]) == 5

    def test_all_unseen(self):
        gm = _make_map(3, 3)
        init_fog(gm)
        for y in range(3):
            for x in range(3):
                assert gm.seen[y][x] is False
                assert gm.visible[y][x] is False

    def test_sets_sight_radius(self):
        gm = _make_map(3, 3)
        init_fog(gm)
        assert gm.sight_radius == 8  # DUNGEON_SIGHT_RADIUS


# ---------------------------------------------------------------------------
# _cast_ray
# ---------------------------------------------------------------------------

class TestCastRay:
    """Ray from origin to dx/dy — reveals cells, stops at walls."""

    def test_reveals_along_ray(self):
        gm = _make_map(5, 5)
        init_fog(gm)
        # Cast ray from (0,0) to east: dx=4, dy=0
        _cast_ray(gm, 0, 0, 4, 0)
        # Cells (1,0) through (4,0) should be seen + visible.
        for x in range(1, 5):
            assert gm.seen[0][x] is True, f"cell ({x},0) not seen"
            assert gm.visible[0][x] is True

    def test_stops_at_wall(self):
        gm = _make_map(5, 5)
        _wall_at(gm, 3, 0)
        init_fog(gm)
        _cast_ray(gm, 0, 0, 4, 0)
        # Wall at (3,0) is revealed, but nothing beyond.
        assert gm.seen[0][3] is True  # wall itself is seen
        assert gm.seen[0][4] is False  # beyond wall stays hidden

    def test_passes_through_hull_wall(self):
        gm = _make_map(5, 5)
        _hull_at(gm, 3, 0)  # hull_wall is transparent to FOV
        init_fog(gm)
        _cast_ray(gm, 0, 0, 4, 0)
        assert gm.seen[0][3] is True
        assert gm.seen[0][4] is True  # ray continues through hull_wall

    def test_stops_at_door(self):
        gm = _make_map(5, 5)
        gm.tiles[0][3] = DUNGEON_DOOR
        init_fog(gm)
        _cast_ray(gm, 0, 0, 4, 0)
        assert gm.seen[0][3] is True  # door is seen
        assert gm.seen[0][4] is False  # beyond door stays hidden

    def test_zero_length_ray_noop(self):
        gm = _make_map(3, 3)
        init_fog(gm)
        _cast_ray(gm, 0, 0, 0, 0)
        # Nothing revealed beyond origin.
        assert gm.seen[0][1] is False
        assert gm.seen[1][0] is False


# ---------------------------------------------------------------------------
# reveal_around
# ---------------------------------------------------------------------------

class TestRevealAround:
    def test_origin_revealed(self):
        gm = _make_map(5, 5)
        init_fog(gm)
        reveal_around(gm, Position(2, 2), radius=2)
        assert gm.seen[2][2] is True
        assert gm.visible[2][2] is True

    def test_visible_reset_between_calls(self):
        """visible is recomputed each call — old visible cells are cleared."""
        gm = _make_map(5, 5)
        init_fog(gm)
        reveal_around(gm, Position(2, 2), radius=2)
        # Now move to a different position.
        reveal_around(gm, Position(0, 0), radius=1)
        # (2,2) should no longer be visible (but still seen).
        assert gm.seen[2][2] is True   # permanent memory
        assert gm.visible[2][2] is False  # no longer in LOS

    def test_seen_is_cumulative(self):
        gm = _make_map(5, 5)
        init_fog(gm)
        reveal_around(gm, Position(0, 0), radius=1)
        reveal_around(gm, Position(4, 4), radius=1)
        assert gm.seen[0][1] is True
        assert gm.seen[4][3] is True

    def test_wall_blocks_los(self):
        gm = _make_map(5, 5)
        _wall_at(gm, 2, 0)  # wall between origin and target
        init_fog(gm)
        reveal_around(gm, Position(0, 0), radius=4)
        # Wall at (2,0) is seen, but (3,0) and (4,0) are hidden.
        assert gm.seen[0][2] is True
        assert gm.seen[0][3] is False
        assert gm.seen[0][4] is False

    def test_diagonal_ray(self):
        gm = _make_map(5, 5)
        init_fog(gm)
        reveal_around(gm, Position(0, 0), radius=2)
        assert gm.seen[2][2] is True  # diagonal within radius

    def test_noop_no_fog(self):
        gm = _make_map(5, 5)
        # No init_fog — seen is None.
        reveal_around(gm, Position(2, 2))
        assert gm.seen is None  # unchanged


# ---------------------------------------------------------------------------
# _propagate_flags
# ---------------------------------------------------------------------------

class TestPropagateFlags:
    def test_hull_group_propagates(self):
        """Two adjacent hull_wall cells: if one is flagged, both become flagged."""
        gm = _make_map(4, 4)
        _hull_at(gm, 1, 1)
        _hull_at(gm, 2, 1)
        flags = [
            [False, False, False, False],
            [False, True,  False, False],  # only (1,1) is flagged
            [False, False, False, False],
            [False, False, False, False],
        ]
        _propagate_flags(gm, flags)
        assert flags[1][1] is True
        assert flags[1][2] is True  # propagated to adjacent hull_wall

    def test_non_hull_unaffected(self):
        gm = _make_map(4, 4)
        # (1,1) is floor, (2,1) is floor — no propagation.
        flags = [
            [False, False, False, False],
            [False, True,  False, False],
            [False, False, False, False],
            [False, False, False, False],
        ]
        _propagate_flags(gm, flags)
        assert flags[1][2] is False  # not propagated
