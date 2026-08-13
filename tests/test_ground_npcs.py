"""Tests for selective last-seen pursuit by ground NPCs."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import ground_npcs, saveload, world
from src.spacehack.combat import _loop, _rules_ground
from src.spacehack.combat._types import CombatResult


def _floor_map(*entities: world.Entity) -> world.GameMap:
    tiles = [
        [world.DUNGEON_FLOOR for _ in range(10)]
        for _ in range(5)
    ]
    return world.GameMap(10, 5, tiles, list(entities))


def _squad_map(*entities: world.Entity) -> world.GameMap:
    """20x20 open floor so a far-flung squad has room to patrol."""
    tiles = [
        [world.DUNGEON_FLOOR for _ in range(20)]
        for _ in range(20)
    ]
    return world.GameMap(20, 20, tiles, list(entities))


def test_hunter_pursues_remembered_player_cell(monkeypatch):
    player = world.Entity("@", (255, 255, 255), world.Position(7, 2))
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    game_map = _floor_map(player, hunter)
    ctx = SimpleNamespace(player=player, faction_reputation={})

    assert ground_npcs.remember_last_seen([hunter], player.pos) == 1
    monkeypatch.setattr(ground_npcs, "_MOVE_CHANCE", 1.0)
    monkeypatch.setattr(ground_npcs.RNG, "random", lambda: 0.0)

    ground_npcs.move_ground_npcs(ctx, game_map)

    assert hunter.pos.x > 2
    assert hunter.last_seen_ticks == 4


def test_move_ground_npcs_skips_combat_locked_entities(monkeypatch):
    """Engaged enemies (combat_locked) are frozen; others still move."""
    player = world.Entity("@", (255, 255, 255), world.Position(7, 2))
    locked = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    locked.combat_locked = True
    free = world.Entity(
        "p", (255, 100, 100), world.Position(5, 2),
        npc_char_id="dust_prowler",
    )
    game_map = _floor_map(player, locked, free)
    ctx = SimpleNamespace(player=player, faction_reputation={})
    monkeypatch.setattr(ground_npcs, "_MOVE_CHANCE", 1.0)
    monkeypatch.setattr(ground_npcs.RNG, "random", lambda: 0.0)

    ground_npcs.move_ground_npcs(ctx, game_map)

    assert locked.pos == world.Position(2, 2)  # frozen mid-combat
    assert free.pos != world.Position(5, 2)    # patrolled/wandered normally


def test_active_pursuit_bypasses_normal_move_roll(monkeypatch):
    player = world.Entity("@", (255, 255, 255), world.Position(7, 2))
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    game_map = _floor_map(player, hunter)
    ctx = SimpleNamespace(player=player, faction_reputation={})
    ground_npcs.remember_last_seen([hunter], player.pos)
    monkeypatch.setattr(ground_npcs, "_MOVE_CHANCE", 0.0)
    monkeypatch.setattr(ground_npcs.RNG, "random", lambda: 1.0)

    ground_npcs.move_ground_npcs(ctx, game_map)

    assert hunter.pos.x > 2
    assert hunter.last_seen_ticks == 4


def test_unknown_npcs_do_not_receive_unconsumed_memory():
    unknown = world.Entity(
        "?", (255, 255, 255), world.Position(2, 2),
        npc_char_id="missing_npc",
    )

    assert ground_npcs.remember_last_seen(
        [unknown], world.Position(7, 2),
    ) == 0
    assert unknown.last_seen_pos is None
    assert unknown.last_seen_ticks == 0


def test_only_hunters_receive_last_seen_memory():
    player_pos = world.Position(7, 2)
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    guard = world.Entity(
        "d", (150, 185, 255), world.Position(3, 2),
        npc_char_id="sentry_drone",
    )
    ambusher = world.Entity(
        "w", (185, 220, 245), world.Position(4, 2),
        npc_char_id="ice_worm",
    )

    assert ground_npcs.remember_last_seen(
        [hunter, guard, ambusher], player_pos,
    ) == 1
    assert hunter.last_seen_pos == player_pos
    assert hunter.last_seen_ticks == 5
    assert guard.last_seen_pos is None
    assert guard.last_seen_ticks == 0
    assert ambusher.last_seen_pos is None
    assert ambusher.last_seen_ticks == 0


def test_blocked_pursuit_still_expires():
    game_map = _floor_map()
    for _x, _y in (
        (1, 1), (2, 1), (3, 1),
        (1, 2), (3, 2),
        (1, 3), (2, 3), (3, 3),
    ):
        game_map.tiles[_y][_x] = world.DUNGEON_WALL
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    hunter.last_seen_pos = world.Position(7, 2)
    hunter.last_seen_ticks = 1
    game_map.entities.append(hunter)

    ground_npcs._move_toward_last_seen(hunter, game_map)

    assert hunter.pos == world.Position(2, 2)
    assert hunter.last_seen_pos is None
    assert hunter.last_seen_ticks == 0


def test_pursuit_memory_clears_when_expired_or_reached():
    game_map = _floor_map()
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    hunter.last_seen_pos = world.Position(7, 2)
    hunter.last_seen_ticks = 1

    assert ground_npcs._move_toward_last_seen(hunter, game_map)
    assert hunter.last_seen_pos is None
    assert hunter.last_seen_ticks == 0

    hunter.last_seen_pos = world.Position(hunter.pos.x, hunter.pos.y)
    hunter.last_seen_ticks = 3
    assert not ground_npcs._move_toward_last_seen(hunter, game_map)
    assert hunter.last_seen_pos is None
    assert hunter.last_seen_ticks == 0


def test_disengagement_stamps_surviving_hunter():
    player = world.Entity("@", (255, 255, 255), world.Position(7, 2))
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    game_map = _floor_map(player, hunter)
    _rules_ground._state = SimpleNamespace(
        enemies=[SimpleNamespace(entity=hunter, alive=True)],
    )
    ctx = SimpleNamespace(player=player)

    _rules_ground.on_disengage(ctx, game_map)

    assert hunter.last_seen_pos == player.pos
    assert hunter.last_seen_ticks == 5


def test_unified_loop_stamps_only_on_disengagement():
    callbacks = []
    enemy = SimpleNamespace()
    rules = SimpleNamespace(
        get_enemies=lambda _ctx: [enemy],
        enemy_name=lambda _enemy: "Hunter",
        refresh_engaged=lambda _ctx, _map: None,
        combat_should_end=lambda _ctx, _map, _enemies: True,
        on_disengage=lambda _ctx, _map: callbacks.append("disengaged"),
        sync_state=lambda _ctx: None,
        get_combat_result=lambda: CombatResult(),
    )
    ctx = SimpleNamespace(
        log=SimpleNamespace(add_colored=lambda *_args: None),
        _pygame_combat_presenter=None,
    )
    result = _loop._run_combat_impl(None, ctx, object(), rules)

    assert result.outcome == "DISENGAGED"
    assert callbacks == ["disengaged"]


def test_unified_loop_does_not_stamp_memory_for_victory(monkeypatch):
    callbacks = []
    rules = SimpleNamespace(
        get_enemies=lambda _ctx: [],
        refresh_engaged=lambda *_args: None,
        combat_should_end=lambda *_args: True,
        on_disengage=lambda *_args: callbacks.append("disengaged"),
        sync_state=lambda *_args: None,
        get_combat_result=lambda: CombatResult(),
    )
    ctx = SimpleNamespace(
        log=SimpleNamespace(add_colored=lambda *_args: None),
        _pygame_combat_presenter=None,
    )
    result = _loop._run_combat_impl(None, ctx, object(), rules)

    assert result.outcome == "VICTORY"
    assert callbacks == []


def test_squad_cohesion_steps_one_cell_toward_centre(monkeypatch):
    """The cohesion pull moves a straggler ONE cell per tick — no
    multi-cell snap back to the squad centre."""
    player = world.Entity("@", (255, 255, 255), world.Position(17, 2))
    members = [
        world.Entity("S", (220, 120, 80), world.Position(5, 18),
                     npc_char_id="pirate_raider", squad_id="squad"),
        world.Entity("S", (220, 120, 80), world.Position(14, 8),
                     npc_char_id="pirate_raider", squad_id="squad"),
        world.Entity("S", (220, 120, 80), world.Position(16, 9),
                     npc_char_id="pirate_raider", squad_id="squad"),
    ]
    game_map = _squad_map(player, *members)
    # Leader (the straggler) patrols one cell west; cohesion then runs.
    monkeypatch.setattr(ground_npcs, "_patrol_path", lambda *a, **k: [(4, 18)])

    ground_npcs._move_squad(members, game_map, is_hostile=True, squad_id="squad")

    straggler = members[0]
    # After the patrol step the straggler is at (4, 18); the pull may
    # move it at most one cell from there (no (11, 10) snap).
    assert max(abs(straggler.pos.x - 4), abs(straggler.pos.y - 18)) == 1


def test_squad_cohesion_slips_around_blocked_direct_cell(monkeypatch):
    """A straggler whose direct centre step is blocked slips one cell
    perpendicular — the old unstick behaviour, without teleporting."""
    player = world.Entity("@", (255, 255, 255), world.Position(17, 2))
    members = [
        world.Entity("S", (220, 120, 80), world.Position(5, 18),
                     npc_char_id="pirate_raider", squad_id="squad"),
        world.Entity("S", (220, 120, 80), world.Position(14, 8),
                     npc_char_id="pirate_raider", squad_id="squad"),
        world.Entity("S", (220, 120, 80), world.Position(16, 9),
                     npc_char_id="pirate_raider", squad_id="squad"),
    ]
    game_map = _squad_map(player, *members)
    # Wall the direct pull cell (5, 17) AND the first slip candidate
    # (5, 18) so the pull must take the second slip (4, 17).
    game_map.tiles[17][5] = world.DUNGEON_WALL
    game_map.tiles[18][5] = world.DUNGEON_WALL
    monkeypatch.setattr(ground_npcs, "_patrol_path", lambda *a, **k: [(4, 18)])

    ground_npcs._move_squad(members, game_map, is_hostile=True, squad_id="squad")

    straggler = members[0]
    # Patrol: (5,18) -> (4,18). Pull: direct (5,17) and slip (5,18)
    # blocked, so it takes the second slip -> (4,17) — exactly one cell.
    assert straggler.pos == world.Position(4, 17)


def test_invalid_pursuit_memory_is_ignored_on_dungeon_load():
    game_map = _floor_map()
    saved = saveload._dungeon_to_dict(game_map, None)
    saved["entities"] = [{
        "char": "p",
        "fg_r": 255,
        "fg_g": 100,
        "fg_b": 100,
        "x": 2,
        "y": 2,
        "npc_char_id": "dust_prowler",
        "last_seen_pos": ["bad", 2],
        "last_seen_ticks": "bad",
    }]

    restored, _ = saveload._dungeon_from_dict(saved)
    loaded = restored.entities[0]

    assert loaded.last_seen_pos is None
    assert loaded.last_seen_ticks == 0


def test_last_seen_memory_survives_dungeon_map_round_trip():
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    hunter.last_seen_pos = world.Position(7, 2)
    hunter.last_seen_ticks = 3
    game_map = _floor_map(hunter)

    saved = saveload._dungeon_to_dict(game_map, None)
    restored, _ = saveload._dungeon_from_dict(saved)
    loaded = restored.entities[0]

    assert loaded.last_seen_pos == world.Position(7, 2)
    assert loaded.last_seen_ticks == 3
