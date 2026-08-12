"""Tests for dungeon.py — LOS raycasting and fog-of-war.

These are the pure computation functions under the rendering layer.
The stale-LOS bug (da75376) and hull-wall propagation were in this
file — both now have regression tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.world import (
    GameMap, Tile, Position,
    DUNGEON_WALL, DUNGEON_FLOOR, HULL_WALL, VOID, DUNGEON_DOOR,
    Entity, try_move, find_loot_near, find_path,
)
from src.spacehack.input_helpers import _is_p_press
from src.spacehack.pygame_engine import PygameInputEvent
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
# Soft loot movement
# ---------------------------------------------------------------------------

class TestSoftLoot:
    def test_p_predicate_accepts_both_key_aliases(self):
        """Pickup is bound to P without stealing G from navigation."""
        _event = PygameInputEvent(kind="keydown", key_name="p")

        assert _is_p_press(_event)
        assert not _is_p_press(
            PygameInputEvent(kind="keydown", key_name="g"),
        )

    def test_loot_does_not_block_world_movement(self):
        """A player can walk through a loot pile instead of being trapped."""
        gm = _make_map(3, 1)
        player = Entity(char="@", fg=(255, 255, 255), pos=Position(0, 0))
        loot = Entity(
            char="%", fg=(255, 215, 0), pos=Position(1, 0),
            loot_data={"good_id": "scrap_metal", "quantity": 1},
        )
        gm.entities.extend((player, loot))

        code, blocker = try_move(player, gm, 1, 0)

        assert code == "moved"
        assert blocker is None
        assert player.pos == Position(1, 0)
        assert gm.entity_at(1, 0) is player
        assert gm.loot_at(1, 0) is loot

    def test_find_loot_near_prefers_current_then_cardinal_cells(self):
        """P pickup can collect loot on the player or one step away."""
        gm = _make_map(5, 5)
        player_pos = Position(2, 2)
        adjacent = Entity(
            char="%", fg=(255, 215, 0), pos=Position(2, 1),
            loot_data={"good_id": "scrap_metal", "quantity": 1},
        )
        gm.entities.append(adjacent)

        assert find_loot_near(gm, player_pos) is adjacent

    def test_find_loot_near_finds_diagonal_cells(self):
        """P pickup also reaches loot on a diagonal neighbor."""
        gm = _make_map(5, 5)
        player_pos = Position(2, 2)
        diagonal = Entity(
            char="%", fg=(255, 215, 0), pos=Position(3, 3),
            loot_data={"good_id": "scrap_metal", "quantity": 1},
        )
        gm.entities.append(diagonal)

        assert find_loot_near(gm, player_pos) is diagonal

    def test_find_loot_near_returns_none_without_loot(self):
        gm = _make_map(3, 3)

        assert find_loot_near(gm, Position(1, 1)) is None

    def test_pathfinding_can_cross_loot(self):
        """A loot drop does not make a corridor unreachable."""
        gm = _make_map(3, 1)
        loot = Entity(
            char="%", fg=(255, 215, 0), pos=Position(1, 0),
            loot_data={"good_id": "scrap_metal", "quantity": 1},
        )
        gm.entities.append(loot)

        path = find_path((0, 0), {(2, 0)}, gm)

        assert path == [(1, 0), (2, 0)]

    def test_dungeon_p_pickup_routes_to_existing_loot_modal(self, monkeypatch):
        """The dungeon P action keeps mission-aware pickup centralized."""
        from src.spacehack import __main__ as game_main

        gm = _make_map(3, 3)
        loot = Entity(
            char="%", fg=(255, 215, 0), pos=Position(2, 1),
            loot_data={"good_id": "scrap_metal", "quantity": 1},
        )
        gm.entities.append(loot)
        ctx = SimpleNamespace(
            game_map=gm,
            player=Entity(char="@", fg=(255, 255, 255), pos=Position(1, 1)),
            log=MagicMock(),
        )
        opened = []
        monkeypatch.setattr(
            "src.spacehack.trade.open_loot_pickup",
            lambda _ctx, entity: opened.append(entity),
        )

        assert game_main._pickup_loot_near(ctx) is True
        assert opened == [loot]


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
