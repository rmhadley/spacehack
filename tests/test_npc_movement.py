"""The movement-credit kernel (doc 44 phase 2): NPCs move at their
own hull speed — credit accrues at map_speed/player_speed tiles per
player step, whole tiles spend cell-by-cell, fractions carry, the
clamp parks a mover on the encounter-trigger cell, and retained
credit never banks past one tile."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import npc_movement, world


def _corridor(width: int, height: int) -> world.GameMap:
    return world.GameMap(width, height, [
        [world.DUNGEON_FLOOR for _ in range(width)] for _ in range(height)
    ], [])


def _ctx(paths=None, credit=None) -> SimpleNamespace:
    return SimpleNamespace(npc_paths=paths or {}, npc_credit=credit or {})


def _mover(x: int, y: int) -> world.Entity:
    return world.Entity("M", (255, 255, 255), world.Position(x, y))


def test_credit_rate_is_own_speed_over_player_speed():
    assert npc_movement.credit_rate(14, 6) == pytest.approx(14 / 6)
    assert npc_movement.credit_rate(9, 10) == pytest.approx(0.9)
    assert npc_movement.credit_rate(6, 6) == 1.0


def test_enter_trigger_predicate():
    player = world.Position(10, 10)
    assert npc_movement.enter_trigger((11, 10), player, 5)   # dist 1
    assert npc_movement.enter_trigger((13, 10), player, 3)   # dist 3, boundary
    assert not npc_movement.enter_trigger((14, 10), player, 3)
    assert not npc_movement.enter_trigger((10, 10), player, 0), (
        "radius 0 (no trigger) never clamps"
    )


def test_settle_caps_retained_credit_at_one_tile():
    ctx = _ctx()
    npc_movement.settle(ctx, "k", 0.4)
    assert ctx.npc_credit["k"] == pytest.approx(0.4), "fractions carry"
    npc_movement.settle(ctx, "k", 2.5)
    assert ctx.npc_credit["k"] == 1.0, "bursts don't bank"


def test_spend_credit_carries_fractions_exactly():
    game_map = _corridor(12, 3)
    entity = _mover(4, 1)
    ctx = _ctx(paths={"k": [(5, 1), (6, 1), (7, 1)]})

    credit, outcome = npc_movement.spend_credit(
        ctx, game_map, entity=entity, key="k", credit=0.9,
        player_pos=world.Position(0, 0), radius=0,
    )
    assert outcome == "moving" and credit == pytest.approx(0.9)
    assert entity.pos == world.Position(4, 1), "0.9 tiles: no move yet"

    credit, outcome = npc_movement.spend_credit(
        ctx, game_map, entity=entity, key="k", credit=credit + 0.9,
        player_pos=world.Position(0, 0), radius=0,
    )
    assert outcome == "moving" and credit == pytest.approx(0.8)
    assert entity.pos == world.Position(5, 1), "1.8 tiles: one cell, 0.8 carried"


def test_spend_credit_arrives_when_the_path_exhausts():
    game_map = _corridor(12, 3)
    entity = _mover(4, 1)
    ctx = _ctx(paths={"k": [(5, 1), (6, 1)]})

    credit, outcome = npc_movement.spend_credit(
        ctx, game_map, entity=entity, key="k", credit=3.0,
        player_pos=world.Position(0, 0), radius=0,
    )
    assert outcome == "arrived" and credit == pytest.approx(1.0)
    assert entity.pos == world.Position(6, 1)
    assert ctx.npc_paths["k"] == []


def test_spend_credit_without_a_path():
    ctx = _ctx(paths={}, credit={})
    assert npc_movement.spend_credit(
        ctx, _corridor(3, 3), entity=_mover(1, 1), key="k", credit=1.5,
        player_pos=world.Position(0, 0), radius=0,
    ) == (1.5, "no-path")
    ctx = _ctx(paths={"k": []})
    assert npc_movement.spend_credit(
        ctx, _corridor(3, 3), entity=_mover(1, 1), key="k", credit=1.5,
        player_pos=world.Position(0, 0), radius=0,
    ) == (1.5, "arrived")


def test_spend_credit_blocked_cell_keeps_the_tile():
    # The direct cell AND every slip offset are blocked — a pure
    # head-on jam (slips try forward-diagonals first).
    _row = lambda wall_xs: [
        world.WALL if x in wall_xs else world.DUNGEON_FLOOR for x in range(8)
    ]
    game_map = world.GameMap(8, 3, [
        _row({4, 5}),
        [world.DUNGEON_FLOOR for _ in range(8)],
        _row({4, 5}),
    ], [_mover(5, 1)])  # the blocker occupies the next cell
    entity = _mover(4, 1)
    ctx = _ctx(paths={"k": [(5, 1), (6, 1)]})

    credit, outcome = npc_movement.spend_credit(
        ctx, game_map, entity=entity, key="k", credit=2.0,
        player_pos=world.Position(0, 0), radius=0,
    )
    assert outcome == "blocked"
    assert credit == pytest.approx(2.0), "the tile is retained for the retry"
    assert entity.pos == world.Position(4, 1), "no slip landed — fully jammed"
    assert ctx.npc_paths["k"] == [(5, 1), (6, 1)], "the path is kept"


def test_spend_credit_clamp_parks_on_the_trigger_cell():
    game_map = _corridor(12, 3)
    entity = _mover(4, 1)
    ctx = _ctx(paths={"k": [(5, 1), (6, 1), (7, 1)]})
    player = world.Position(5, 5)  # (5,1) is dist 4; (6,1) is dist 5.1

    credit, outcome = npc_movement.spend_credit(
        ctx, game_map, entity=entity, key="k", credit=3.0,
        player_pos=player, radius=4,
    )
    assert outcome == "clamped"
    assert entity.pos == world.Position(5, 1), "entered the trigger cell, parked"
    assert credit == pytest.approx(2.0), "spend stopped after the clamp cell"
    assert ctx.npc_paths["k"] == [(6, 1), (7, 1)], "the walk resumes next pass"


def test_pick_synced_credits_mirrors_the_path_population():
    synced = {"sol": ["m1", ""], "luyten_star": ["m2"]}
    credits = {"m1": 0.5, "watch:150:7:t3": 0.2}
    assert npc_movement.pick_synced_credits(credits, synced) == {"m1": 0.5}


def test_player_moves_per_day_reads_the_owned_ship():
    from src.spacehack.data.ships import find_ship
    assert npc_movement.player_moves_per_day(SimpleNamespace()) == 10
    assert npc_movement.player_moves_per_day(
        SimpleNamespace(player_owned_ship=None)
    ) == 10
    owned = SimpleNamespace(ship_id="scout", modules=())
    assert npc_movement.player_moves_per_day(
        SimpleNamespace(player_owned_ship=owned)
    ) == find_ship("scout").speed


def test_spend_credit_slipped_mover_reports_blocked_but_moved():
    """A blocked direct step that lands a perpendicular slip reports
    ``blocked`` WITH the entity moved one cell off the path — the
    tile is retained and the head kept (the kept-path idiom pulls
    the mover back next pass). Blocked never implies motionless."""
    game_map = _corridor(8, 3)
    game_map.entities.append(_mover(5, 1))  # the blocker: direct cell only
    entity = _mover(4, 1)
    ctx = _ctx(paths={"k": [(5, 1), (6, 1)]})

    credit, outcome = npc_movement.spend_credit(
        ctx, game_map, entity=entity, key="k", credit=2.0,
        player_pos=world.Position(0, 0), radius=0,
    )
    assert outcome == "blocked"
    assert (entity.pos.x, entity.pos.y) in {(5, 2), (5, 0), (4, 2), (4, 0)}, (
        "on a slip offset (forward-diagonals first)"
    )
    assert credit == pytest.approx(2.0), "the tile is retained"
    assert ctx.npc_paths["k"] == [(5, 1), (6, 1)], "the head is kept"


def test_rate_for_pays_a_whole_day_on_a_wait():
    assert npc_movement.rate_for(14, 6, day_pass=True) == 14.0
    assert npc_movement.rate_for(9, 10, day_pass=True) == 9.0
    assert npc_movement.rate_for(14, 6) == pytest.approx(14 / 6)
