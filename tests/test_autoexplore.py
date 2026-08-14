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
    GotoTarget,
    blocking_way_entity,
    goto_targets,
    interesting_at,
    newly_interesting_positions,
    next_explore_step,
    next_goto_step,
    run_auto_explore,
    run_goto,
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
    """Mark a Chebyshev disc (walls included) as both seen and visible —
    the ``reveal_around`` simulation used by test ticks.
    """
    for y in range(max(0, cy - radius), min(game_map.height, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(game_map.width, cx + radius + 1)):
            game_map.seen[y][x] = True
            game_map.visible[y][x] = True


def _explored_corridor(gm, upto):
    """Mark corridor cells x=0..``upto`` (floor AND walls) as seen — the
    explored stretch a player would have revealed walking it.
    """
    for x in range(upto + 1):
        for y in range(3):
            gm.seen[y][x] = True


def _seed_start(gm, player):
    """Reveal a small disc around the start (walls included), like the
    player's entry reveal — the corridor then only has unseen cells
    ahead.
    """
    _reveal_frame(gm, player.pos.x, player.pos.y, radius=1)


class _Events:
    def __init__(self, *events):
        self._events = list(events)

    def events(self):
        return tuple(self._events)


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


def _run_goto(gm, player, target, *, events=None, tick=None):
    """Run go-to headless with stub present/tick hooks."""
    ctx = SimpleNamespace(log=MessageLog(20), context=_Events(*(events or ())))
    tick = tick or (lambda ctx, console, game_map: None)
    result = run_goto(
        ctx, console=None, game_map=gm, player=player, target=target,
        post_step_tick=tick, map_w=8, map_h=3,
        present_frame=lambda *a, **k: None,
    )
    return ctx, result


# ---------------------------------------------------------------------------
# next_explore_step — BFS step planning
# ---------------------------------------------------------------------------


def test_next_explore_step_heads_toward_unseen():
    gm = _corridor()
    _explored_corridor(gm, 3)
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
    _explored_corridor(gm, 4)
    # Walks toward the unseen stairs (so they get spotted)...
    assert next_explore_step(gm, world.Position(2, 1)) == (1, 0)
    assert next_explore_step(gm, world.Position(3, 1)) == (1, 0)
    # ...but never steps onto them: nothing beyond, so no further step.
    assert next_explore_step(gm, world.Position(4, 1)) is None


def test_next_explore_step_visible_solid_entity_blocks():
    gm = _corridor()
    gm.entities.append(world.Entity(char="S", fg=(255, 0, 0),
                                    pos=world.Position(4, 1)))
    gm.visible[1][4] = True  # the player can see it on screen
    _explored_corridor(gm, 4)
    # A visible solid entity seals the corridor — no step onto or past it.
    assert next_explore_step(gm, world.Position(2, 1)) is None


def test_next_explore_step_unseen_solid_entity_does_not_block():
    """Regression (new save): a monster camped in the only doorway
    beyond LOS must NOT seal the route — the player cannot see it, so
    auto-explore walks toward it and reveals it.
    """
    gm = _corridor()
    gm.entities.append(world.Entity(char="s", fg=(205, 170, 120),
                                    npc_char_id="rock_scavenger",
                                    pos=world.Position(4, 1)))
    _explored_corridor(gm, 3)
    # Invisible (outside the LOS frame) — passable: the walk heads for
    # the unseen floor beyond it.
    assert next_explore_step(gm, world.Position(2, 1)) == (1, 0)
    # Once it comes into view it seals the route again.
    gm.visible[1][4] = True
    assert next_explore_step(gm, world.Position(3, 1)) is None


def test_next_explore_step_walks_over_loot():
    gm = _corridor()
    gm.entities.append(world.Entity(char="$", fg=(255, 255, 0),
                                    pos=world.Position(4, 1),
                                    loot_data={"good_id": "x", "quantity": 1}))
    _explored_corridor(gm, 3)
    assert next_explore_step(gm, world.Position(2, 1)) == (1, 0)


def test_next_explore_step_walks_toward_unseen_walls():
    """Regression: the fog boundary is made of unseen wall cells just
    beyond LOS — the BFS must walk toward them so the run reaches and
    reveals them instead of declaring everything explored.
    """
    gm = _corridor()
    _explored_corridor(gm, 3)
    gm.seen[1][4] = True  # floor ahead is seen, but its wall at (4,0) is not
    assert next_explore_step(gm, world.Position(2, 1)) == (1, 0)


def test_next_explore_step_walk_progresses_through_walls():
    """Walking toward the fog edge reveals the boundary walls and keeps
    going: revealing wall (4,0) exposes the next target at (5,0).
    """
    gm = _corridor()
    _explored_corridor(gm, 3)
    gm.seen[1][4] = gm.seen[1][5] = True
    assert next_explore_step(gm, world.Position(2, 1)) == (1, 0)
    # Reveal the first fog wall (as reveal_around would when adjacent).
    gm.seen[0][4] = gm.seen[2][4] = True
    assert next_explore_step(gm, world.Position(3, 1)) == (1, 0)


def test_next_explore_step_none_when_walls_revealed():
    """Once the corridor and its walls are fully revealed, nothing left."""
    gm = _corridor()
    _explored_corridor(gm, 7)
    assert next_explore_step(gm, world.Position(4, 1)) is None


def test_next_explore_step_walks_through_breach_tiles():
    """Derelict entry shafts are made of walkable ``breach`` tiles —
    the player spawns on them and must walk through them. Regression:
    they were excluded as transitions, cornering the player at spawn
    with the whole ship still dark.
    """
    gm = _corridor()
    gm.tiles[1][5] = world.Tile(kind="breach", char="X", walkable=True,
                                fg=(255, 120, 50), bg=(80, 30, 10))
    _explored_corridor(gm, 4)
    # Step onto the breach tile itself...
    assert next_explore_step(gm, world.Position(4, 1)) == (1, 0)
    # ...and through it to the unseen floor beyond.
    gm.seen[1][5] = True
    assert next_explore_step(gm, world.Position(5, 1)) == (1, 0)


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


def test_interesting_at_does_not_flag_breach_tiles():
    """Breach tiles are ordinary passable floor, not a leave-tile —
    auto-explore must walk through them, not stop.
    """
    gm = _corridor()
    gm.tiles[1][5] = world.Tile(kind="breach", char="X", walkable=True,
                                fg=(255, 120, 50), bg=(80, 30, 10))
    assert interesting_at(gm, 5, 1) is None


# ---------------------------------------------------------------------------
# blocking_way_entity — the visible-only-way-out detector
# ---------------------------------------------------------------------------


def _sealed_room():
    """Fully-seen 12x3 room with one 1-wide door in the east wall at
    (7,1): a small unseen pocket at x=8..11 lies just beyond it, so a
    monster standing on the door cell is the only obstruction."""
    gm = world.GameMap(
        width=12, height=3,
        tiles=[[(world.DUNGEON_FLOOR if y == 1 else world.DUNGEON_WALL)
                for x in range(12)] for y in range(3)],
        entities=[],
        seen=[[True] * 12 for _ in range(3)],
        visible=[[False] * 12 for _ in range(3)],
        sight_radius=8,
    )
    # Unseen pocket east of the door at (8,1).
    gm.seen[1][8] = gm.seen[1][9] = gm.seen[1][10] = gm.seen[1][11] = False
    return gm


def test_blocking_way_entity_reports_visible_monster_in_door():
    gm = _sealed_room()
    gm.entities.append(world.Entity(char="s", fg=(205, 170, 120),
                                    npc_char_id="rock_scavenger",
                                    pos=world.Position(7, 1)))
    gm.visible[1][7] = True  # the player sees it in the doorway
    blocker = blocking_way_entity(gm, world.Position(3, 1))
    assert blocker is not None
    assert blocker.pos == world.Position(7, 1)


def test_blocking_way_entity_none_for_invisible_monster_in_door():
    gm = _sealed_room()
    gm.entities.append(world.Entity(char="s", fg=(205, 170, 120),
                                    pos=world.Position(7, 1)))
    # Not in the LOS frame — the player does not know it is there, so
    # it is walked through, never reported.
    assert blocking_way_entity(gm, world.Position(3, 1)) is None


def test_blocking_way_entity_none_for_incidental_visible_terminal():
    """A visible terminal inside a wall-sealed room is not the way
    out: removing it opens no unseen territory, so no message."""
    gm = _sealed_room()
    for x in range(8, 12):
        gm.seen[1][x] = True  # fully seal it — no unseen anywhere
    gm.entities.append(world.Entity(char="C", fg=(0, 200, 255),
                                    pos=world.Position(4, 1),
                                    computer_terminal=True))
    gm.visible[1][4] = True
    assert blocking_way_entity(gm, world.Position(3, 1)) is None


def test_blocking_way_entity_none_when_unseen_reachable():
    """If the BFS finds unseen territory it returns a step, and the
    way-out detector reports nothing."""
    gm = _corridor()
    _explored_corridor(gm, 3)
    assert blocking_way_entity(gm, world.Position(2, 1)) is None


# ---------------------------------------------------------------------------
# run_auto_explore — the loop
# ---------------------------------------------------------------------------


def test_run_auto_explore_walks_whole_dungeon():
    gm = _corridor()
    player = _player(1, 1)
    _seed_start(gm, player)
    ticks = []

    def tick(ctx, console, game_map):
        # Radius 1 keeps the seen frontier one cell ahead (walls
        # included), so the walk is monotonic to the far end.
        ticks.append((player.pos.x, player.pos.y))
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=1)
        return None

    ctx, result = _run(gm, player, tick=tick)
    assert result == "DONE"
    assert len(ticks) >= 5
    # The walk reveals the entire corridor (walls included); it stops
    # one step short of the far end because the last cell is already
    # revealed when adjacent.
    assert all(gm.seen[y][x] for x in range(8) for y in range(3))
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
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=1)
        return None

    ctx, result = _run(gm, player, tick=tick)
    assert result == "DONE"
    # Walked past the already-spotted loot and revealed the whole
    # corridor (walls included) without stopping on the loot again.
    assert player.pos.x >= 5
    assert all(gm.seen[y][x] for x in range(8) for y in range(3))
    assert (3, 1) in gm.autoexplore_ignored


def test_run_auto_explore_remembers_left_loot_on_return_to_floor():
    """Once auto-explore presents a cache, leaving it on purpose must not
    make the next auto-explore run stop on the same cached-floor object."""
    gm = _corridor()
    gm.entities.append(world.Entity(char="$", fg=(255, 255, 0),
                                    pos=world.Position(4, 1),
                                    loot_data={"good_id": "x", "quantity": 1}))
    player = _player(1, 1)
    _seed_start(gm, player)

    def tick(ctx, console, game_map):
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=2)
        return None

    first_ctx, first_result = _run(gm, player, tick=tick)
    assert first_result == "DONE"
    assert player.pos == world.Position(2, 1)
    assert (4, 1) in gm.autoexplore_ignored
    assert "cache of supplies" in first_ctx.log.recent(1)[0].text

    second_ctx, second_result = _run(gm, player, tick=tick)
    assert second_result == "DONE"
    assert player.pos.x >= 5
    assert "cache of supplies" not in " ".join(
        entry.text for entry in second_ctx.log.history()
    )


def test_autoexplore_memory_round_trips_with_cached_floor():
    """The ignored-cell memory survives the same map serialization used by
    cached dungeon floors and autosaves."""
    from src.spacehack.saveload_maps import _dungeon_from_dict, _dungeon_to_dict

    gm = _corridor()
    gm.autoexplore_ignored = {(2, 1), (6, 1)}
    restored, _ = _dungeon_from_dict(_dungeon_to_dict(gm, None))
    assert restored.autoexplore_ignored == {(2, 1), (6, 1)}


def test_run_auto_explore_stops_at_visible_monster_in_the_way():
    """A visible monster camping the only exit of the explored room:
    auto-explore stops with an honest message instead of 'explored
    every reachable area' (the unseen corridor beyond the monster is
    exactly what the player could not have explored past it).
    """
    gm = _corridor()
    gm.entities.append(world.Entity(char="s", fg=(205, 170, 120),
                                    npc_char_id="rock_scavenger",
                                    pos=world.Position(4, 1)))
    gm.visible[1][4] = True
    player = _player(1, 1)
    # The room is explored up to the doorway the monster camps: its
    # cell and the flanking walls are seen; only the corridor beyond
    # is dark.
    _explored_corridor(gm, 4)
    ctx, result = _run(gm, player)
    assert result == "DONE"
    assert player.pos == world.Position(1, 1)  # never moved
    assert "rock scavenger blocks the only way forward" in ctx.log.recent(1)[0].text


def test_run_auto_explore_walks_to_and_reveals_unseen_monster():
    """Regression (new save): a monster in the only doorway beyond LOS
    does not stop auto-explore — the walker advances, the monster
    comes into view, and the run stops beside it with the way-forward
    message (in the real game the LOS tick starts combat instead).
    """
    gm = _corridor()
    gm.entities.append(world.Entity(char="s", fg=(205, 170, 120),
                                    npc_char_id="rock_scavenger",
                                    pos=world.Position(5, 1)))
    player = _player(1, 1)
    _explored_corridor(gm, 3)

    def tick(ctx, console, game_map):
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=1)
        return None

    ctx, result = _run(gm, player, tick=tick)
    assert result == "DONE"
    # The walker advanced through the dark corridor and stopped one
    # cell short of the now-visible monster.
    assert player.pos == world.Position(4, 1)
    assert gm.visible[1][5]
    assert "rock scavenger blocks the only way forward" in ctx.log.recent(1)[0].text


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


def test_run_auto_explore_real_derelict_escapes_spawn_shaft():
    """End-to-end on a real derelict layout (scout_a): the BFS must
    escape the breach-tile entry shaft instead of reporting everything
    explored, and the loop must make progress.
    """
    from src.spacehack.dungeon import load_layout, init_fog, reveal_around

    gm, spawn = load_layout("scout_a")
    assert spawn is not None
    init_fog(gm)
    # Strip scatter-RNG-dependent enemies so no entity can seal the
    # shaft (loot placement is layout-fixed and stays for the
    # interesting-stop).
    gm.entities = [e for e in gm.entities if not e.npc_char_id]
    player = world.Entity(char="@", fg=(255, 255, 255), pos=spawn)
    reveal_around(gm, player.pos, radius=gm.sight_radius)

    # The BFS must escape the shaft immediately (regression core).
    assert next_explore_step(gm, player.pos) is not None

    # The full loop must make progress and stop for a real reason
    # (a cache sighting), never the cornered 'explored everything'.
    def tick(ctx, console, game_map):
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=2)
        return None

    ctx, result = _run(gm, player, tick=tick)
    assert result == "DONE"
    assert player.pos != spawn
    assert "explored every reachable area" not in ctx.log.recent(1)[0].text


# ---------------------------------------------------------------------------
# goto_targets — discovered destinations for the G picker
# ---------------------------------------------------------------------------


def test_goto_targets_lists_discovered_transitions_and_interactables():
    gm = _dungeon()
    gm.tiles[3][3] = _stairs(3, 3)
    gm.seen[3][3] = True
    gm.tiles[3][8] = _stairs(8, 3, kind="stairs_up")
    gm.seen[3][8] = True
    gm.tiles[3][10] = _stairs(10, 3)  # unseen — not discovered, excluded
    gm.entities.append(world.Entity(char="C", fg=(0, 200, 255),
                                    pos=world.Position(5, 5),
                                    computer_terminal=True))
    gm.seen[5][5] = True
    gm.entities.append(world.Entity(char="D", fg=(255, 0, 0),
                                    pos=world.Position(9, 2),
                                    main_quest_door=True))
    gm.seen[2][9] = True
    # A seen loot cache is NOT a goto destination (O handles pickup).
    gm.entities.append(world.Entity(char="$", fg=(255, 255, 0),
                                    pos=world.Position(7, 5),
                                    loot_data={"good_id": "x", "quantity": 1}))
    gm.seen[7][5] = True

    targets = goto_targets(gm, world.Position(2, 2))
    # Nearest first (Chebyshev from the player): stairs(1), computer(3),
    # stairs up(6), sealed door(7).
    assert [(t.title, t.x, t.y) for t in targets] == [
        ("Stairs down", 3, 3),
        ("Ship computer", 5, 5),
        ("Stairs up", 8, 3),
        ("Sealed door", 9, 2),
    ]
    assert targets[0].label == "a stairway down"
    assert targets[1].label == "a ship computer"


def test_goto_targets_npc_and_interaction_labels():
    """NPC and dungeon-interaction entities are targets; interaction
    entities have no prose label in ``interesting_at``, so the title is
    the fallback."""
    gm = _dungeon()
    gm.entities.append(world.Entity(char="N", fg=(0, 255, 0),
                                    pos=world.Position(4, 4), npc_id="smuggler"))
    gm.seen[4][4] = True
    gm.entities.append(world.Entity(char="D", fg=(255, 255, 0),
                                    pos=world.Position(6, 6),
                                    dungeon_interaction="signal_door"))
    gm.seen[6][6] = True
    targets = goto_targets(gm, world.Position(2, 2))
    assert [(t.title, t.label) for t in targets] == [
        ("NPC", "someone"),
        ("Interactable", "Interactable"),
    ]


def test_goto_targets_entity_on_transition_keeps_tile_title():
    gm = _dungeon()
    gm.tiles[3][3] = _stairs(3, 3)
    gm.seen[3][3] = True
    # A terminal standing on the stairs cell dedupes into one target;
    # the tile title wins over the entity title.
    gm.entities.append(world.Entity(char="C", fg=(0, 200, 255),
                                    pos=world.Position(3, 3),
                                    computer_terminal=True))
    targets = goto_targets(gm, world.Position(2, 2))
    assert [(t.title, t.x, t.y) for t in targets] == [("Stairs down", 3, 3)]


def test_goto_targets_empty_without_fog():
    gm = _dungeon()
    gm.seen = None
    assert goto_targets(gm, world.Position(2, 2)) == []


# ---------------------------------------------------------------------------
# next_goto_step — goal-mode BFS
# ---------------------------------------------------------------------------


def test_next_goto_step_walks_toward_target_and_stops_adjacent():
    gm = _corridor()
    gm.tiles[1][6] = _stairs(6, 1)
    assert next_goto_step(gm, world.Position(2, 1), 6, 1) == (1, 0)
    assert next_goto_step(gm, world.Position(4, 1), 6, 1) == (1, 0)
    # Adjacent to the stairs — arrival, no step (caller announces).
    assert next_goto_step(gm, world.Position(5, 1), 6, 1) is None
    assert next_goto_step(gm, world.Position(5, 0), 6, 1) is None


def test_next_goto_step_visible_entity_blocks():
    gm = _corridor()
    gm.entities.append(world.Entity(char="S", fg=(255, 0, 0),
                                    pos=world.Position(4, 1)))
    gm.visible[1][4] = True
    gm.tiles[1][6] = _stairs(6, 1)
    # The visible monster seals the 1-wide corridor — no path.
    assert next_goto_step(gm, world.Position(2, 1), 6, 1) is None


def test_next_goto_step_unseen_entity_does_not_block():
    gm = _corridor()
    gm.entities.append(world.Entity(char="s", fg=(205, 170, 120),
                                    pos=world.Position(4, 1)))
    gm.tiles[1][6] = _stairs(6, 1)
    # Invisible — walked through and revealed, same as auto-explore.
    assert next_goto_step(gm, world.Position(2, 1), 6, 1) == (1, 0)


def test_next_goto_step_no_path():
    gm = _corridor()
    gm.tiles[1][4] = world.DUNGEON_WALL  # seal the corridor
    gm.tiles[1][6] = _stairs(6, 1)
    assert next_goto_step(gm, world.Position(2, 1), 6, 1) is None


# ---------------------------------------------------------------------------
# run_goto — the go-to loop
# ---------------------------------------------------------------------------


def test_run_goto_arrives_beside_stairs():
    gm = _corridor()
    gm.tiles[1][6] = _stairs(6, 1)
    target = GotoTarget(title="Stairs down", label="a stairway down", x=6, y=1)
    player = _player(1, 1)

    def tick(ctx, console, game_map):
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=1)
        return None

    ctx, result = _run_goto(gm, player, target, tick=tick)
    assert result == "DONE"
    assert player.pos == world.Position(5, 1)  # adjacent, never on top
    assert "arrive at a stairway down" in ctx.log.recent(1)[0].text


def test_run_goto_does_not_stop_at_own_target():
    """The chosen target is seeded into the known set — coming into
    view must not interrupt the approach."""
    gm = _corridor()
    gm.tiles[1][6] = _stairs(6, 1)
    target = GotoTarget(title="Stairs down", label="a stairway down", x=6, y=1)
    player = _player(1, 1)

    def tick(ctx, console, game_map):
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=2)
        return None

    ctx, result = _run_goto(gm, player, target, tick=tick)
    assert result == "DONE"
    assert player.pos == world.Position(5, 1)  # walked past the sighting
    assert "arrive at a stairway down" in ctx.log.recent(1)[0].text


def test_run_goto_stops_at_newly_visible_interesting():
    gm = _corridor()
    gm.entities.append(world.Entity(char="$", fg=(255, 255, 0),
                                    pos=world.Position(4, 1),
                                    loot_data={"good_id": "x", "quantity": 1}))
    gm.tiles[1][6] = _stairs(6, 1)
    target = GotoTarget(title="Stairs down", label="a stairway down", x=6, y=1)
    player = _player(1, 1)

    def tick(ctx, console, game_map):
        _reveal_frame(gm, player.pos.x, player.pos.y, radius=1)
        return None

    ctx, result = _run_goto(gm, player, target, tick=tick)
    assert result == "DONE"
    assert player.pos == world.Position(3, 1)  # stopped at the cache
    assert "cache of supplies" in ctx.log.recent(1)[0].text


def test_run_goto_cancels_on_keypress():
    gm = _corridor()
    gm.tiles[1][6] = _stairs(6, 1)
    target = GotoTarget(title="Stairs down", label="a stairway down", x=6, y=1)
    player = _player(1, 1)
    key = SimpleNamespace(kind="keydown", key_name="h")
    ctx, result = _run_goto(gm, player, target, events=[key])
    assert result == "CANCELLED"
    assert player.pos == world.Position(1, 1)  # never moved


def test_run_goto_stops_when_combat_starts():
    gm = _corridor()
    gm.tiles[1][6] = _stairs(6, 1)
    target = GotoTarget(title="Stairs down", label="a stairway down", x=6, y=1)
    player = _player(1, 1)

    def tick(ctx, console, game_map):
        return "COMBAT"

    ctx, result = _run_goto(gm, player, target, tick=tick)
    assert result == "COMBAT"
    assert player.pos == world.Position(2, 1)  # one step taken


def test_run_goto_cannot_reach_target():
    gm = _corridor()
    gm.tiles[1][4] = world.DUNGEON_WALL  # sealed corridor
    gm.tiles[1][6] = _stairs(6, 1)
    target = GotoTarget(title="Stairs down", label="a stairway down", x=6, y=1)
    player = _player(1, 1)
    ctx, result = _run_goto(gm, player, target)
    assert result == "DONE"
    assert player.pos == world.Position(1, 1)  # never moved
    assert "Cannot reach a stairway down" in ctx.log.recent(1)[0].text
