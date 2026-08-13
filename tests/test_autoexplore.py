"""Tests for dungeon auto-explore (the ``O`` key).

Covers the pure decision helpers (``next_explore_step``,
``interesting_at``, ``newly_interesting_positions``) and the
``run_auto_explore`` loop outcomes (complete, cancel, combat,
defeat, interesting stop, standing stop, no-fog) with injected
present/tick stubs — no Pygame required.
"""
from types import SimpleNamespace

from src.spacehack import world
from src.spacehack.autoexplore import (
    interesting_at,
    newly_interesting_positions,
    next_explore_step,
    run_auto_explore,
)
from src.spacehack.message_log import MessageLog


# ---------------------------------------------------------------------------
# Map builders
# ---------------------------------------------------------------------------


def _dungeon(width=12, height=8):
    """Open room with walled borders — generic dungeon test bed."""
    tiles = []
    for y in range(height):
        row = []
        for x in range(width):
            if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                row.append(world.DUNGEON_WALL)
            else:
                row.append(world.DUNGEON_FLOOR)
        tiles.append(row)
    return world.GameMap(
        width=width, height=height, tiles=tiles, entities=[],
        seen=[[False] * width for _ in range(height)],
        visible=[[False] * width for _ in range(height)],
        sight_radius=8,
    )


def _corridor():
    """8x3 corridor: floor only on row ``y=1`` — deterministic BFS."""
    tiles = []
    for y in range(3):
        row = []
        for x in range(8):
            row.append(world.DUNGEON_FLOOR if y == 1 else world.DUNGEON_WALL)
        tiles.append(row)
    return world.GameMap(
        width=8, height=3, tiles=tiles, entities=[],
        seen=[[False] * 8 for _ in range(3)],
        visible=[[False] * 8 for _ in range(3)],
        sight_radius=8,
    )


def _stairs(x, y, kind="stairs_down"):
    return world.Tile(kind=kind, char=">", walkable=True,
                      fg=(0, 255, 0), bg=(0, 0, 0))


def _player(x, y):
    return world.Entity(char="@", fg=(255, 255, 255),
                        pos=world.Position(x, y))


def _reveal_frame(game_map, cx, cy, radius):
    """Mark a Chebyshev disc as both seen and visible — the
    ``reveal_around`` simulation used by test ticks.
    """
    for y in range(max(0, cy - radius), min(game_map.height, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(game_map.width, cx + radius + 1)):
            game_map.seen[y][x] = True
            game_map.visible[y][x] = True


class _Events:
    def __init__(self, *events):
        self._events = list(events)

    def events(self):
        return tuple(self._events)


def _seed_start(gm, player):
    """Mark the starting cell and the one behind it as seen so the
    corridor's only unseen direction is forward.
    """
    gm.seen[player.pos.y][player.pos.x] = True
    gm.seen[player.pos.y][max(0, player.pos.x - 1)] = True


def _run(gm, player, *, events=None, tick=None):
    """Run auto-explore headless with stub present/tick hooks."""
    ctx = SimpleNamespace(log=MessageLog(20), context=_Events(*(events or ())))
    tick = tick or (lambda ctx, console, game_map: None)
    result = run_auto_explore(
        ctx, console=None, game_map=gm, player=player,
        post_step_tick=tick, map_w=8, map_h=3,
        present_frame=lambda *a, **k: None,
    )
    return ctx, result


# ---------------------------------------------------------------------------
# next_explore_step — BFS step planning
# ---------------------------------------------------------------------------


def test_next_explore_step_heads_toward_unseen():
    gm = _corridor()
    gm.seen[1][0] = gm.seen[1][1] = gm.seen[1][2] = gm.seen[1][3] = True
    assert next_explore_step(gm, world.Position(2, 1)) == (1, 0)
    assert next_explore_step(gm, world.Position(3, 1)) == (1, 0)


def test_next_explore_step_none_when_all_seen():
    gm = _corridor()
    for y in range(3):
        for x in range(8):
            gm.seen[y][x] = True
    assert next_explore_step(gm, world.Position(1, 1)) is None


def test_next_explore_step_none_without_fog():
    gm = _corridor()
    gm.seen = None
    assert next_explore_step(gm, world.Position(1, 1)) is None


def test_next_explore_step_stops_beside_stairs():
    gm = _corridor()
    gm.tiles[1][5] = _stairs(5, 1)
    gm.seen[1][0] = gm.seen[1][1] = gm.seen[1][2] = gm.seen[1][3] = True
    assert next_explore_step(gm, world.Position(2, 1)) == (1, 0)
    assert next_explore_step(gm, world.Position(3, 1)) == (1, 0)
    # Adjacent to the stairs with nothing beyond: no step onto them.
    assert next_explore_step(gm, world.Position(4, 1)) is None


def test_next_explore_step_blocked_by_solid_entity():
    gm = _corridor()
    gm.entities.append(world.Entity(char="S", fg=(255, 0, 0),
                                    pos=world.Position(4, 1)))
    gm.seen[1][0] = gm.seen[1][1] = gm.seen[1][2] = gm.seen[1][3] = True
    assert next_explore_step(gm, world.Position(2, 1)) is None


def test_next_explore_step_walks_over_loot():
    gm = _corridor()
    gm.entities.append(world.Entity(char="$", fg=(255, 255, 0),
                                    pos=world.Position(4, 1),
                                    loot_data={"good_id": "x", "quantity": 1}))
    gm.seen[1][0] = gm.seen[1][1] = gm.seen[1][2] = gm.seen[1][3] = True
    assert next_explore_step(gm, world.Position(2, 1)) == (1, 0)


# ---------------------------------------------------------------------------
# interesting_at / newly_interesting_positions
# ---------------------------------------------------------------------------


def test_interesting_at_labels_transitions_and_entities():
    gm = _dungeon()
    gm.tiles[3][3] = _stairs(3, 3)
    gm.tiles[6][3] = world.Tile(kind="exit", char=">", walkable=True,
                                fg=(255, 255, 0), bg=(0, 0, 0))  # y=6, x=3
    gm.entities.append(world.Entity(char="$", fg=(0, 255, 0),
                                    pos=world.Position(5, 5),
                                    loot_data={"good_id": "medkit", "quantity": 1}))
    gm.entities.append(world.Entity(char="C", fg=(0, 200, 255),
                                    pos=world.Position(6, 5),
                                    computer_terminal=True))
    gm.entities.append(world.Entity(char="N", fg=(0, 255, 0),
                                    pos=world.Position(4, 4), npc_id="smuggler"))
    gm.entities.append(world.Entity(char="D", fg=(255, 0, 0),
                                    pos=world.Position(5, 6),
                                    main_quest_door=True))
    assert interesting_at(gm, 3, 3) == "a stairway down"
    assert interesting_at(gm, 3, 6) == "the exit"
    assert interesting_at(gm, 5, 5) == "a cache of supplies"
    assert interesting_at(gm, 6, 5) == "a ship computer"
    assert interesting_at(gm, 4, 4) == "someone"
    assert interesting_at(gm, 5, 6) == "a sealed door"
    assert interesting_at(gm, 7, 5) is None
    assert interesting_at(gm, -1, 0) is None  # out of bounds


def test_newly_interesting_positions_reports_only_fresh_visible():
    gm = _dungeon()
    gm.tiles[3][3] = _stairs(3, 3)
    gm.visible[3][3] = True
    gm.visible[2][2] = True  # plain floor — visible but not interesting
    fresh = newly_interesting_positions(gm, set())
    assert fresh == {(3, 3)}
    assert newly_interesting_positions(gm, {(3, 3)}) == set()


def test_newly_interesting_positions_empty_without_fog():
    gm = _dungeon()
    gm.visible = None
    assert newly_interesting_positions(gm, set()) == set()


# ---------------------------------------------------------------------------
# run_auto_explore — the loop
# ---------------------------------------------------------------------------


def test_run_auto_explore_walks_whole_dungeon():
    gm = _corridor()
    player = _player(1, 1)
    _seed_start(gm, player)
    ticks = []

    def tick(ctx, console, game_map):
        # Radius 0 keeps the seen frontier exactly one cell ahead, so
        # the walk is monotonic cell-by-cell to the far end.
        ticks.append((player.pos.x, player.pos.y))
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=0)
        return None

    ctx, result = _run(gm, player, tick=tick)
    assert result == "DONE"
    assert player.pos == world.Position(7, 1)  # far end of the corridor
    assert len(ticks) >= 5
    assert "explored every reachable area" in ctx.log.recent(1)[0].text


def test_run_auto_explore_cancels_on_keypress():
    gm = _corridor()
    player = _player(1, 1)
    key = SimpleNamespace(kind="keydown", key_name="h")
    ctx, result = _run(gm, player, events=[key])
    assert result == "CANCELLED"
    assert player.pos == world.Position(1, 1)  # never moved


def test_run_auto_explore_stops_when_combat_starts():
    gm = _corridor()
    player = _player(1, 1)
    _seed_start(gm, player)

    def tick(ctx, console, game_map):
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=0)
        return "COMBAT"

    ctx, result = _run(gm, player, tick=tick)
    assert result == "COMBAT"
    assert player.pos == world.Position(2, 1)  # one step taken


def test_run_auto_explore_stops_on_defeat():
    gm = _corridor()
    player = _player(1, 1)

    def tick(ctx, console, game_map):
        return "DEFEAT"

    ctx, result = _run(gm, player, tick=tick)
    assert result == "DEFEAT"


def test_run_auto_explore_stops_at_newly_visible_loot():
    gm = _corridor()
    gm.entities.append(world.Entity(char="$", fg=(255, 255, 0),
                                    pos=world.Position(4, 1),
                                    loot_data={"good_id": "medkit", "quantity": 1}))
    player = _player(1, 1)
    _seed_start(gm, player)

    def tick(ctx, console, game_map):
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=2)
        return None

    ctx, result = _run(gm, player, tick=tick)
    assert result == "DONE"
    assert player.pos == world.Position(2, 1)  # stopped short of the loot
    assert "cache of supplies" in ctx.log.recent(1)[0].text


def test_run_auto_explore_ignores_already_visible_interesting():
    gm = _corridor()
    gm.entities.append(world.Entity(char="$", fg=(255, 255, 0),
                                    pos=world.Position(3, 1),
                                    loot_data={"good_id": "x", "quantity": 1}))
    gm.visible[1][3] = True  # loot already on screen when O is pressed
    player = _player(1, 1)
    _seed_start(gm, player)

    def tick(ctx, console, game_map):
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=0)
        return None

    ctx, result = _run(gm, player, tick=tick)
    assert result == "DONE"
    assert player.pos == world.Position(7, 1)  # walked past it to the end


def test_run_auto_explore_stops_when_standing_on_interesting():
    gm = _corridor()
    gm.tiles[1][1] = _stairs(1, 1, kind="stairs_up")
    player = _player(1, 1)
    ctx, result = _run(gm, player)
    assert result == "DONE"
    assert player.pos == world.Position(1, 1)
    assert "standing at a stairway up" in ctx.log.recent(1)[0].text


def test_run_auto_explore_requires_dungeon_fog():
    gm = _dungeon()
    gm.seen = None
    gm.visible = None
    player = _player(2, 2)
    ctx, result = _run(gm, player)
    assert result == "DONE"
    assert "inside dungeons" in ctx.log.recent(1)[0].text
