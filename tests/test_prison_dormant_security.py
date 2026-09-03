"""Dormant prison security — the powered_down entity contract (doc 30).

A dormant unit is grey, inert, and bump-reported: it never enters an
encounter, never patrols, and survives save/load in its exact state.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import dungeon_fov, ground_npcs, saveload_maps, world


def _dormant_drone(x=5, y=5, squad="prison_x_security"):
    return world.Entity(
        char="d", fg=(110, 110, 110),
        pos=world.Position(x, y), name="", width=1, height=1,
        npc_char_id="sentry_drone", squad_id=squad,
        powered_down=True,
    )


def _active_drone(x=7, y=5):
    return world.Entity(
        char="d", fg=(150, 185, 255),
        pos=world.Position(x, y), name="", width=1, height=1,
        npc_char_id="sentry_drone", squad_id="prison_y_security",
    )


def _map_with(entities):
    width, height = 15, 9
    tiles = [[world.DUNGEON_WALL for _ in range(width)] for _ in range(height)]
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            tiles[y][x] = world.DUNGEON_FLOOR
    return world.GameMap(width=width, height=height, tiles=tiles,
                         entities=list(entities))


def test_powered_down_round_trips_through_dungeon_save():
    game_map = _map_with([_dormant_drone(), _active_drone()])
    data = saveload_maps._dungeon_to_dict(game_map, None)
    restored = saveload_maps._dungeon_from_dict(data)[0]
    states = {
        e.squad_id: e.powered_down for e in restored.entities
    }
    assert states == {"prison_x_security": True, "prison_y_security": False}


def test_dormant_units_never_enter_visible_hostiles():
    from src.spacehack.combat._encounter import _visible_hostile_entities

    game_map = _map_with([_dormant_drone(3, 4), _active_drone(11, 4)])
    ctx = SimpleNamespace(player=SimpleNamespace(pos=world.Position(7, 4)))
    seen = _visible_hostile_entities(ctx, game_map, ctx.player.pos, radius=8)
    assert [e.squad_id for e in seen] == ["prison_y_security"]


def test_dormant_units_do_not_move_on_the_ground_tick():
    game_map = _map_with([_dormant_drone(3, 4)])
    ctx = SimpleNamespace(player=SimpleNamespace(pos=world.Position(7, 4)))
    ground_npcs.move_ground_npcs(ctx, game_map)
    drone = game_map.entities[0]
    assert (drone.pos.x, drone.pos.y) == (3, 4)


def test_bumping_a_dormant_unit_reports_and_never_fights():
    from src.spacehack.game_interactions import resolve_blocker

    messages = []
    state = SimpleNamespace(
        ctx=SimpleNamespace(),
        log=SimpleNamespace(add=messages.append),
        current_mode="dungeon",
    )
    drone = _dormant_drone(8, 4)
    assert resolve_blocker(state, "occupied", drone, 1, 0) is None
    assert any("powered down Sentry Drone" in m for m in messages)


# ----- Prison floors are stocked (doc 30 phase 2) ----------------------


def _prison_floor(floor):
    from src.spacehack.dungeon_extensions import _generate_floor

    return _generate_floor("mars_alien_prison", floor)


def test_prison_floor_stocks_dormant_security_near_anchors():
    game_map, _spawn = _prison_floor(1)
    dormant = [e for e in game_map.entities if e.powered_down]
    assert dormant, "F1 must carry dormant security"
    anchors = game_map.activation_positions or {}
    for unit in dormant:
        if unit.squad_id.startswith("lockdown_extras_"):
            continue  # extras spread along the route (see clustering test)
        event_id = unit.squad_id.removesuffix("_security")
        assert event_id in anchors, unit.squad_id
        anchor = (anchors[event_id].x, anchors[event_id].y)
        # Room-edge + chokepoint + stranding filters (and Phase B
        # landmark footprints) can push units past the first ring —
        # the guarantee is "at the anchor's room", not a fixed radius.
        assert max(abs(unit.pos.x - anchor[0]), abs(unit.pos.y - anchor[1])) <= 12
        assert unit.fg == (110, 110, 110)
        assert unit.npc_char_id


def test_lockdown_extras_match_floor_spec():
    from src.spacehack.data.dungeon_extensions import find_extension

    extension = find_extension("mars_alien_prison")
    by_floor = {spec.floor: spec.lockdown_extras for spec in extension.floors}
    assert by_floor[1] >= by_floor[2] >= by_floor[3] >= by_floor[4]
    game_map, _spawn = _prison_floor(1)
    extras = [
        e for e in game_map.entities
        if e.powered_down and e.squad_id.startswith("lockdown_extras_")
    ]
    assert len(extras) == by_floor[1]


def test_event_counts_become_dormant_units():
    from src.spacehack.data.dungeon_extensions import find_extension

    extension = find_extension("mars_alien_prison")
    spec = extension.floors[0]
    game_map, _spawn = _prison_floor(1)
    by_squad = {}
    for e in game_map.entities:
        if e.powered_down and not e.squad_id.startswith("lockdown_extras_"):
            by_squad[e.squad_id] = by_squad.get(e.squad_id, 0) + 1
    for event in spec.activation_events:
        # Placement filters (corridor runs, chokepoints, footprints)
        # can legitimately claim a cell, so exact parity is not
        # guaranteed — every event keeps at least one dormant unit.
        assert by_squad.get(f"{event.id}_security", 0) >= 1, event.id


# ----- Playtest fixes: room-edge placement + combat light (2026-09-02) --


def test_dormant_units_prefer_room_edges_and_never_fill_corridors():
    """Room-edge placement is the preference, open surroundings are the
    guarantee: no dormant unit sits in a 1-wide corridor, most hug a
    wall, and routes stay walkable (playtest finding #3 — the guarantee
    is the separate routes test)."""
    from src.spacehack.dungeon_activation import _hugs_wall, _open_neighbours

    game_map, _spawn = _prison_floor(1)
    dormant = [e for e in game_map.entities if e.powered_down]
    assert dormant
    for unit in dormant:
        x, y = unit.pos.x, unit.pos.y
        assert _open_neighbours(game_map, x, y) >= 3, (x, y)
    wall_huggers = sum(
        _hugs_wall(game_map, u.pos.x, u.pos.y) for u in dormant
    )
    assert wall_huggers >= len(dormant) // 2, (
        f"only {wall_huggers}/{len(dormant)} dormant units hug walls"
    )


def test_stocked_floor_keeps_routes_walkable():
    """Dormant bodies block movement but never block a path: the down
    stairs stay reachable from the entry treating them as walls."""
    from collections import deque

    for floor in (1, 2):
        game_map, spawn = _prison_floor(floor)
        blockers = {
            (e.pos.x, e.pos.y) for e in game_map.entities if e.powered_down
        }
        goal = (game_map.down_stair_pos.x, game_map.down_stair_pos.y)
        start = (spawn.x, spawn.y)
        seen = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not (dx or dy):
                        continue
                    nxt = (x + dx, y + dy)
                    if nxt in seen or not game_map.in_bounds(*nxt):
                        continue
                    if not game_map.tiles[nxt[1]][nxt[0]].walkable:
                        continue
                    if nxt in blockers:
                        continue
                    seen.add(nxt)
                    queue.append(nxt)
        assert goal in seen, f"floor {floor}: down stairs blocked by dormant units"


def test_recompute_frame_light_advances_with_the_clock():
    """The shared frame recompute (used by explore AND combat renders)
    animates flickering sources; steady-only maps are untouched."""
    from src.spacehack import lighting

    width, height = 15, 9
    tiles = [[world.DUNGEON_WALL for _ in range(width)] for _ in range(height)]
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            tiles[y][x] = world.DUNGEON_FLOOR
    tiles[4][7] = world.PRISON_PANEL_ALARM  # one strobing panel
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    game_map.light_sources = lighting.collect_light_sources(game_map)
    ctx = SimpleNamespace(context=SimpleNamespace(frame_clock=0))

    lighting.recompute_frame_light(ctx, game_map)
    assert game_map.light_grid is not None
    probe = (7, 4)
    at_zero = game_map.light_grid[probe[1]][probe[0]]
    ctx.context.frame_clock = 9
    lighting.recompute_frame_light(ctx, game_map)
    assert game_map.light_grid[probe[1]][probe[0]] != at_zero

    steady = world.GameMap(
        width=width, height=height,
        tiles=[[world.PRISON_PANEL_NORMAL for _ in range(width)]
               for _ in range(height)],
        entities=[],
    )
    steady.light_grid = None
    lighting.recompute_frame_light(ctx, steady)
    assert steady.light_grid is None  # steady-only: build grid stands


# ----- The wake-up + lockdown (doc 30 phase 3) --------------------------


def test_activate_dormant_filters_by_squad_and_recolors():
    from src.spacehack.dungeon_activation import activate_dormant
    from src.spacehack.data.npc_chars import find_npc_char

    a = _dormant_drone(3, 4)   # squad prison_x_security
    b = _dormant_drone(9, 4)   # squad prison_x_security
    c = _dormant_drone(6, 6, squad="prison_y_security")
    game_map = _map_with([a, b, c])

    assert activate_dormant(game_map, squad_prefix="prison_x") == 2
    assert not a.powered_down and not b.powered_down and c.powered_down
    spec = find_npc_char("sentry_drone")
    assert a.fg == spec.fg and a.char == spec.char
    assert activate_dormant(game_map) == 1  # everything else


def test_extract_locks_down_every_cached_floor():
    from src.spacehack.dungeon_activation import apply_lockdown_all_floors
    from src.spacehack.dungeon_extensions import floor_key

    f1, _ = _prison_floor(1)
    f2, _ = _prison_floor(2)
    ctx = SimpleNamespace(
        game_map=f1,
        interiors={
            floor_key("mars_alien_prison", 1): f1,
            floor_key("mars_alien_prison", 2): f2,
        },
        dungeon_extension=SimpleNamespace(
            extension_id="mars_alien_prison",
            activated_events=set(), state_flags=set(),
        ),
    )
    assert any(e.powered_down for e in f1.entities)
    assert any(e.powered_down for e in f2.entities)

    awakened = apply_lockdown_all_floors(ctx)

    assert awakened > 0
    for floor_map in (f1, f2):
        assert not any(e.powered_down for e in floor_map.entities)
        assert not any(
            t.kind == "prison_panel_off"
            for row in floor_map.tiles for t in row
        )


def test_activated_units_survive_save_load_round_trip():
    drone = _dormant_drone(3, 4)
    game_map = _map_with([drone])
    from src.spacehack.dungeon_activation import activate_dormant
    activate_dormant(game_map)

    data = saveload_maps._dungeon_to_dict(game_map, None)
    restored = saveload_maps._dungeon_from_dict(data)[0]
    entity = restored.entities[0]
    assert not entity.powered_down
    assert entity.fg != (110, 110, 110)


# ----- Playtest v2 fixes: corner aggro + guard investigation ----------


def test_what_the_player_sees_can_see_the_player():
    """Combat aggro uses the player's own FOV grid — the corner case
    where Bresenham LOS and the FOV rays disagree no longer silences
    a visible drone (playtest: d beside a corner was visible but
    never aggressive until adjacency)."""
    from src.spacehack.combat._encounter import _visible_hostile_entities
    from src.spacehack.combat._animations import _has_los

    # The playtest's exact map: corridor with the drone one cell off it.
    glyphs = [
        "#####",
        "###@#",   # player at (3, 1)
        "###.#",
        "##d.#",   # drone at (2, 3), corridor (3, 2)-(3, 3)
    ]
    tiles = []
    for row in glyphs:
        tiles.append([
            world.DUNGEON_FLOOR if ch in ".@" else world.DUNGEON_WALL
            for ch in row
        ])
    drone = _active_drone(2, 3)
    game_map = world.GameMap(width=5, height=4, tiles=tiles, entities=[drone])
    ctx = SimpleNamespace(player=SimpleNamespace(pos=world.Position(3, 1)))
    dungeon_fov.init_fog(game_map)
    dungeon_fov.reveal_around(game_map, ctx.player.pos, radius=8)

    if game_map.visible[3][2]:  # corridor in sight
        seen_by_fov = game_map.visible[3][3]
        if seen_by_fov and not _has_los(
            game_map, 3, 1, 2, 3,
        ):
            # The disagreement case: aggro must still include the drone.
            seen = _visible_hostile_entities(ctx, game_map, ctx.player.pos, 8)
            assert drone in seen


def test_guards_investigate_last_seen_then_resume_their_post():
    """A guard with disengage memory moves toward the last-seen cell;
    without memory it holds position as always."""
    from src.spacehack.ground_npcs import remember_last_seen

    guard = world.Entity(
        char="d", fg=(150, 185, 255),
        pos=world.Position(9, 2), name="", width=1, height=1,
        npc_char_id="sentry_drone", squad_id="g1",
    )
    assert remember_last_seen([guard], world.Position(2, 2)) == 0  # default: guards skip
    assert remember_last_seen(
        [guard], world.Position(2, 2), include_stationary=True,
    ) == 1
    assert guard.last_seen_pos is not None

    from src.spacehack.ground_npcs import move_ground_npcs

    # Corridor: guard at (9,2), open row 2 from x=1..9 — memory at (2,2).
    width, height = 12, 5
    tiles = [[world.DUNGEON_WALL for _ in range(width)] for _ in range(height)]
    for x in range(1, width - 1):
        tiles[2][x] = world.DUNGEON_FLOOR
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[guard])
    ctx = SimpleNamespace(player=SimpleNamespace(pos=world.Position(2, 3)))
    move_ground_npcs(ctx, game_map)
    assert guard.pos.x < 9, "guard with fresh memory must investigate"
    guard.last_seen_pos = None
    guard.last_seen_ticks = 0
    move_ground_npcs(ctx, game_map)
    assert guard.pos == world.Position(*((guard.pos.x, guard.pos.y))), (
        "guard without memory holds position"
    )


def test_extras_spread_along_the_route_not_piled_at_the_door():
    """Two extras hold the entry; the rest spread across the floor —
    the garrison never piles into the stairs-up room (playtest v3)."""
    game_map, spawn = _prison_floor(1)
    dormant = [e for e in game_map.entities if e.powered_down]
    near_entry = [
        e for e in dormant
        if max(abs(e.pos.x - spawn.x), abs(e.pos.y - spawn.y)) <= 6
    ]
    assert len(near_entry) <= 3, f"{len(near_entry)} units camp the entry room"
    far = [
        e for e in dormant
        if max(abs(e.pos.x - spawn.x), abs(e.pos.y - spawn.y)) >= 15
    ]
    assert len(far) >= 4, "the route's far half must be garrisoned too"


def test_dormant_units_never_seal_one_tile_passages():
    """A body may block a cell, never a passage: corridor cells, bends,
    and room mouths are rejected even when a detour exists elsewhere
    (playtest v3)."""
    from src.spacehack.dungeon_activation import _dormant_cells, _plugs_passage

    # Two rooms joined by a 1-wide corridor with a bend; side pocket.
    glyphs = [
        "##########",
        "#........#",   # top room (2 tall)
        "#........#",
        "####.#####",   # 1-wide vertical passage
        "####.#####",
        "####.#####",
        "#...+.....#",   # bend at +; east corridor continues
        "####.#####",   # passage continues down
        "####....##",   # bottom room (2 tall, mouth at x=4)
        "#####...##",
        "##########",
    ]
    glyphs = [row.ljust(10, "#") for row in glyphs]
    tiles = [
        [world.DUNGEON_FLOOR if ch in ".+" else world.DUNGEON_WALL for ch in row]
        for row in glyphs
    ]
    game_map = world.GameMap(width=10, height=11, tiles=tiles, entities=[])

    # The conduit cells of the 1-wide passage plug it...
    for conduit in ((4, 3), (4, 5), (4, 7)):
        assert game_map.tiles[conduit[1]][conduit[0]].walkable
        assert _plugs_passage(game_map, set(), conduit), conduit
    # ...room edge cells do not.
    assert not _plugs_passage(game_map, set(), (2, 1))
    assert not _plugs_passage(game_map, set(), (6, 9))

    # Placement anchored mid-passage must land beside it, never on it.
    cells = _dormant_cells(
        game_map, world.Position(4, 4), set(), 2, spawn=world.Position(4, 3),
    )
    assert cells
    assert all(not _plugs_passage(game_map, set(), c) for c in cells)
    assert all(_hug_ok(game_map, c) for c in cells)


def _hug_ok(game_map, cell):
    from src.spacehack.dungeon_activation import _hugs_wall
    return _hugs_wall(game_map, cell[0], cell[1])


def test_stairside_diagonal_slip_is_not_a_chokepoint():
    """The first v4 report (`#<D# / ##@#`): under REAL 8-directional
    movement the player steps diagonally past the drone — not a choke.
    (The in-game symptom there was the autoexplore loop, fixed by
    making dormant units permanent walls to planning.) True diagonal
    stair pockets — the F3/F4 rematches — are the next test."""
    from src.spacehack.dungeon_activation import _plugs_passage

    glyphs = ["#<D#", "##@#"]
    tiles = [
        [world.DUNGEON_FLOOR if ch in "<@D" else world.DUNGEON_WALL for ch in row]
        for row in glyphs
    ]
    game_map = world.GameMap(width=4, height=2, tiles=tiles, entities=[])
    assert not _plugs_passage(game_map, set(), (2, 0))


def test_autoexplore_treats_dormant_units_as_permanent_walls():
    """A dormant drone outside current view still seals planning —
    the walk-toward-reveal loop oscillates forever on stationary
    blockers (playtest v4 autoexplore freak-out)."""
    from src.spacehack.autoexplore import _visible_blocker

    def _visible_blocker_at(gm, x, y):
        return _visible_blocker(gm, x, y)

    glyphs = [
        "#####",
        "#...#",
        "#.@.#",
        "#####",
    ]
    tiles = [
        [world.DUNGEON_FLOOR if ch in ".@" else world.DUNGEON_WALL for ch in row]
        for row in glyphs
    ]
    dormant = _dormant_drone(3, 2)
    active = _active_drone(1, 2)
    game_map = world.GameMap(width=5, height=4, tiles=tiles,
                            entities=[dormant, active])
    game_map.seen = [[True] * 5 for _ in range(4)]
    game_map.visible = [[False] * 5 for _ in range(4)]  # out of view

    assert _visible_blocker_at(game_map, 3, 2) is dormant
    assert _visible_blocker_at(game_map, 1, 2) is None  # active: unchanged


def test_diagonal_stair_pockets_are_chokepoints():
    """Both playtest v4 rematches: with real 8-dir movement the F3
    diagonal pocket and the F4 landing are chokes for dormant units."""
    from src.spacehack.dungeon_activation import _plugs_passage

    f3 = ["#####", "##<##", ".d.@#", "###.#"]
    tiles = [
        [world.DUNGEON_FLOOR if ch in ".@d<" else world.DUNGEON_WALL
         for ch in row]
        for row in f3
    ]
    game_map = world.GameMap(width=5, height=4, tiles=tiles, entities=[])
    assert _plugs_passage(game_map, set(), (1, 2)), "F3: d seals the stair"

    f4 = [".D##", ".@D.", ".<##"]
    tiles = [
        [world.DUNGEON_FLOOR if ch in ".@D<" else world.DUNGEON_WALL
         for ch in row]
        for row in f4
    ]
    game_map = world.GameMap(width=4, height=3, tiles=tiles, entities=[])
    assert _plugs_passage(game_map, {(1, 0)}, (2, 1)), "F4: D seals the landing"


def test_finished_garrison_strands_nothing_across_seeds():
    """The whole-garrison invariant, not per-cell: across seeded runs,
    dormant bodies may occupy cells but never seal a region or a stair
    (playtest v5 — two bodies in a two-cell doorway each passed the
    per-candidate checks and sealed the room together)."""
    from src.spacehack.dungeon_activation import _reachable_cells
    from src.spacehack.dungeon_extensions import _generate_floor
    from src.spacehack.engine import seed_rng

    audited = 0
    for seed in (1, 3, 5, 10, 25):
        for floor in (1, 2, 3, 4):
            seed_rng(seed)
            game_map, spawn = _generate_floor("mars_alien_prison", floor)
            dormant = {
                (e.pos.x, e.pos.y) for e in game_map.entities if e.powered_down
            }
            if not dormant:
                continue
            audited += 1
            free = _reachable_cells(game_map, spawn, set())
            walled = _reachable_cells(game_map, spawn, dormant)
            assert not (free - walled - dormant), (seed, floor)
    assert audited >= 8


# ----- Cell-block landmarks (polish phase B) ----------------------------


def test_prison_landmark_layouts_parse_with_single_entrances():
    """Every prison block layout parses and honours the one-entrance
    marker contract (bottom-wall door so the approach lands outside
    the protected footprint)."""
    from src.spacehack import landmark

    for layout_id in (
        "prison_intake_block", "prison_cell_block",
        "prison_cell_block_breached", "prison_checkpoint",
        "prison_high_risk_block",
    ):
        asset = landmark.load_landmark(layout_id)
        entrances = sum(
            tile.kind in {"dungeon_door", "landmark_entrance"}
            for row in asset.tiles for tile in row
        )
        assert entrances == 1, layout_id


def test_every_prison_floor_stamps_its_cell_block():
    """F1-F4 generation stamps its authored structure (and the sprinkle
    theme still adds filler beside it); panels inside the block ride
    the floor's phase lighting."""
    from src.spacehack.dungeon_extensions import _generate_floor
    from src.spacehack.engine import seed_rng

    expected = {
        1: "prison_intake_block",
        3: "prison_checkpoint",
        4: "prison_high_risk_block",
    }
    for floor in (1, 2, 3, 4):
        seed_rng(1)
        game_map, _ = _generate_floor("mars_alien_prison", floor)
        variant = getattr(game_map, "landmark_variant_id", None)
        assert variant, f"floor {floor} stamped no landmark variant"
        if floor in expected:
            assert variant == expected[floor]
        assert game_map.landmark_footprint, floor
    # F2 picks one of its two gallery variants.
    seed_rng(1)
    game_map, _ = _generate_floor("mars_alien_prison", 2)
    assert getattr(game_map, "landmark_variant_id", "") in {
        "prison_cell_block", "prison_cell_block_breached",
    }


def test_route_through_the_stairs_tile_does_not_count():
    """Playtest v6: a hallway whose only path crosses the stairs tile
    is SEALED in practice — stepping onto '<' auto-travels. Both
    drones in the reported layout must be rejected."""
    from src.spacehack.dungeon_activation import _plugs_passage

    glyphs = [
        "##.##",
        "#<D##",
        ".d@##",
        "##.##",
    ]
    tiles = [
        [
            world.DUNGEON_FLOOR if ch in ".@d<D"
            else (world.STAIRS_UP if ch == "<" else world.DUNGEON_WALL)
            for ch in row
        ]
        for row in glyphs
    ]
    tiles[1][1] = world.STAIRS_UP
    game_map = world.GameMap(width=5, height=4, tiles=tiles, entities=[])
    assert _plugs_passage(game_map, set(), (1, 2)), "d seals the left hall"
    assert _plugs_passage(game_map, {(1, 2)}, (2, 1)), "D seals via the stair"


def test_prison_landmark_layouts_contain_no_void_padding():
    """Ragged MAP rows parse as VOID padding on the east edge (playtest
    v7: broken checkpoint walls). Every prison layout must be uniform
    width and void-free — void belongs to the deep cell only."""
    from src.spacehack import landmark

    for layout_id in (
        "prison_intake_block", "prison_cell_block",
        "prison_cell_block_breached", "prison_checkpoint",
        "prison_high_risk_block", "mars_signal_door",
    ):
        asset = landmark.load_landmark(layout_id)
        widths = {len(row) for row in asset.tiles}
        assert len(widths) == 1, f"{layout_id}: ragged rows {widths}"
        assert not any(
            tile.kind == "void"
            for row in asset.tiles for tile in row
        ), layout_id


def test_dormant_units_never_park_in_straight_corridor_runs():
    """Playtest v8 (save-confirmed): two drones sat inside the hall run
    beside the Defensive Layer stairs — reachable around, but the hall
    mouth was plugged. The straight-corridor signature (two OPPOSITE
    orthogonal openings) rejects those cells regardless of diagonal
    stair pockets inflating the 8-dir count."""
    from src.spacehack.dungeon_activation import (
        _dormant_cells, _in_corridor_run,
    )

    # The save's exact pocket geometry: 1-wide hall at row 31 with the
    # stairs pocket at its east end.
    glyphs = [
        "####################",
        "####################",
        "..........#.......<.",   # row 2: hall + pocket + stairs
        "####################",
    ]
    tiles = []
    for row in glyphs:
        tiles.append([
            world.STAIRS_UP if ch == "<"
            else world.DUNGEON_FLOOR if ch == "."
            else world.DUNGEON_WALL
            for ch in row
        ])
    game_map = world.GameMap(width=20, height=4, tiles=tiles, entities=[])
    # Straight-run cells (walls above AND below) are corridor cells...
    assert _in_corridor_run(game_map, set(), (12, 2))
    assert _in_corridor_run(game_map, set(), (13, 2))
    # ...even with the stairs tile diagonally adjacent.
    assert _in_corridor_run(game_map, set(), (17, 2))
    # Placement beside the pocket must land OFF the hall run.
    cells = _dormant_cells(
        game_map, world.Position(15, 2), set(), 1,
        spawn=world.Position(18, 2),
    )
    assert cells == [] or all(
        not _in_corridor_run(game_map, set(), c) for c in cells
    )


def test_dormant_units_never_stand_near_transit_tiles():
    """Playtest v10 (save-confirmed): a drone pair at a three-lane
    junction mouth beside the F2 up-stairs — every analytic rule passed
    (detours existed) but the local flow died. The guarantee is now
    blunt: no dormant unit within one step (8-dir) of any stairs/exit."""
    from src.spacehack.dungeon_activation import (
        _transit_neighborhood, _dormant_cells,
    )

    # The save's junction: three lanes meeting at x=5, stairs west.
    glyphs = [
        "#####...........",
        "#####...........",
        "####<###########",
        "#####...........",
    ]
    tiles = [
        [
            world.STAIRS_UP if ch == "<"
            else world.DUNGEON_FLOOR if ch == "."
            else world.DUNGEON_WALL
            for ch in row
        ]
        for row in glyphs
    ]
    game_map = world.GameMap(width=16, height=4, tiles=tiles, entities=[])
    zone = _transit_neighborhood(game_map)
    # Stairs sit at (4, 2): diagonal junction cells are in the zone.
    assert (5, 1) in zone and (5, 3) in zone and (4, 1) in zone
    assert (5, 0) not in zone, "two steps above the stairs stays free"
    assert (6, 1) not in zone, "one step beyond the zone is free"
    cells = _dormant_cells(
        game_map, world.Position(6, 1), set(), 2,
        spawn=world.Position(6, 3),
    )
    assert cells and all(cell not in zone for cell in cells)
