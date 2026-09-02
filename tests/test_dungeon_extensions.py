"""Regression tests for the reusable themed dungeon extension runtime."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import dungeon_extension_layout
from src.spacehack import dungeon_extensions
from src.spacehack import message_log
from src.spacehack import world
from src.spacehack.game_context import DungeonExtensionState
from src.spacehack.engine import seed_rng
from src.spacehack.saveload import _dungeon_from_dict, _dungeon_to_dict


def _ctx(parent_map: world.GameMap, parent_player: world.Entity):
    return SimpleNamespace(
        context=None,
        interiors={"surface:mars": parent_map},
        dungeon_extension=None,
        game_map=parent_map,
        player=parent_player,
        current_city_id="mars",
        log=message_log.MessageLog(capacity=6),
        main_quest_progress={},
        main_quest_unlocked_items=set(),
        player_xp=0,
        player_level=1,
        player_skill_points=0,
        player_traits=[],
        player_counters=SimpleNamespace(
            laser_shots=0, missile_shots=0, plasma_shots=0,
            merchant_kills=0, total_kills=0, bounties_completed=0,
            deliveries_completed=0, total_damage_taken=0, melee_kills=0,
        ),
        faction_reputation={},
        main_quest_gate={},
        main_quest_chain="",
        main_quest_disclosure="",
        post_prison_orbit_seen=False,
    )


def _parent_map() -> tuple[world.GameMap, world.Entity]:
    tiles = [[world.DUNGEON_FLOOR for _ in range(12)] for _ in range(12)]
    game_map = world.GameMap(12, 12, tiles, [])
    player = world.Entity("@", (255, 255, 255), world.Position(4, 5), "Player")
    game_map.entities.append(player)
    return game_map, player


def _position_between_security_thresholds(game_map: world.GameMap) -> world.Position:
    """Find a reachable cell after alpha but before beta progress."""
    _entry = game_map.up_stair_pos
    _down = game_map.down_stair_pos
    _distances = dungeon_extensions._walkable_distances(game_map, _down)
    _total = _distances[(_entry.x, _entry.y)]
    _alpha = _total * (1.0 - 0.42)
    _beta = _total * (1.0 - 0.76)
    _cells = [
        _cell for _cell, _remaining in _distances.items()
        if _beta < _remaining <= _alpha
    ]
    assert _cells
    return world.Position(*_cells[0])


def test_activation_cells_collect_multiple_rings_without_stairs():
    _tiles = [[world.DUNGEON_FLOOR for _ in range(7)] for _ in range(7)]
    _tiles[3][2] = world.STAIRS_DOWN
    _game_map = world.GameMap(7, 7, _tiles, [])
    _position = world.Position(3, 3)
    _occupied = {
        (x, y)
        for y in range(7)
        for x in range(7)
        if max(abs(x - 3), abs(y - 3)) <= 1
    }
    _occupied.remove((2, 3))

    _cells = dungeon_extensions._activation_cells(
        _game_map, _position, _occupied, needed_count=3,
    )

    assert len(_cells) == 3
    assert (2, 3) not in _cells
    assert all(max(abs(x - 3), abs(y - 3)) >= 2 for x, y in _cells)


def test_activation_cells_return_empty_when_only_stair_is_free():
    _tiles = [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(5)]
    _tiles[2][1] = world.STAIRS_UP
    _game_map = world.GameMap(5, 5, _tiles, [])
    _position = world.Position(2, 2)
    _occupied = {
        (x, y)
        for y in range(5)
        for x in range(5)
        if (x, y) != (1, 2)
    }

    assert dungeon_extensions._activation_cells(
        _game_map, _position, _occupied, needed_count=1,
    ) == []


def test_activation_threshold_resolves_when_no_deployment_cell_exists(monkeypatch):
    seed_rng(15)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    extension_map, extension_player = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda *args, **kwargs: None,
    )
    extension_player.pos = _position_between_security_thresholds(extension_map)

    assert dungeon_extensions.tick_activation(ctx)
    assert "prison_floor1_security_alpha" in ctx.dungeon_extension.activated_events
    assert not dungeon_extensions.tick_activation(ctx)
    # The event woke its pre-placed dormant squad (doc 30 phase 3):
    # alpha's units are active and hostile now.
    squad = [
        e for e in extension_map.entities
        if e.squad_id == "prison_floor1_security_alpha_security"
    ]
    assert squad and all(not e.powered_down for e in squad)


def test_floor_generation_has_up_stairs_and_stable_activation_anchors():
    seed_rng(7)
    game_map, spawn = dungeon_extensions._generate_floor("mars_alien_prison", 1)

    assert game_map.tiles[spawn.y][spawn.x] is world.STAIRS_UP
    assert game_map.location_name == "Alien Prison F1"
    assert set(game_map.activation_positions) == {
        "prison_floor1_security_alpha",
        "prison_floor1_security_beta",
        "prison_ascent_f1_sentries",
        "prison_ascent_f1_final_lockdown",
    }
    assert all(game_map.is_walkable(pos.x, pos.y)
               for pos in game_map.activation_positions.values())


def test_enter_extension_rejects_invalid_parent_key_without_activation():
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)

    try:
        dungeon_extensions.enter_extension(
            ctx,
            parent_map,
            parent_player,
            extension_id="mars_alien_prison",
            parent_map_key="surface:missing",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid parent key should fail")

    assert ctx.dungeon_extension is None


def test_first_entry_flavor_shows_once_on_reentry(monkeypatch):
    seed_rng(81)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    ctx.context = object()
    shown: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda _ctx, faction, message, *, title: shown.append(
            (faction, title, message),
        ),
    )

    extension_map, extension_player = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )

    assert len(shown) == 1
    assert shown[0][0:2] == ("ALIEN FACILITY", "THE PRISON BELOW")
    assert "technology humanity never reached" in shown[0][2]
    assert "__entry_flavor__:floor:1" in ctx.dungeon_extension.activated_events
    assert ctx.dungeon_extension.activated_events == {"__entry_flavor__:floor:1"}

    dungeon_extensions.leave_extension(ctx, extension_map)
    dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )

    assert len(shown) == 1


def test_floor_without_entry_flavor_does_not_mark_state(monkeypatch):
    ctx = _ctx(*_parent_map())
    ctx.context = object()
    state = DungeonExtensionState(extension_id="future_extension")
    shown = []
    monkeypatch.setattr(
        "src.spacehack.dungeon_extensions._floor_spec",
        lambda _extension_id, _floor: SimpleNamespace(entry_flavor=None),
    )
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda *args, **kwargs: shown.append((args, kwargs)),
    )

    dungeon_extensions._show_first_entry_flavor(ctx, state, 1)

    assert not shown
    assert not any(
        marker.startswith("__entry_flavor__")
        for marker in state.activated_events
    )


def test_extension_entry_and_leave_preserve_parent_position():
    seed_rng(8)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)

    extension_map, extension_player = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )

    assert ctx.dungeon_extension.active
    assert ctx.dungeon_extension.parent_position == world.Position(4, 5)
    assert extension_map is ctx.game_map
    assert extension_player is ctx.player
    assert extension_map.tiles[extension_player.pos.y][extension_player.pos.x] is world.STAIRS_UP

    returned_map, returned_player = dungeon_extensions.leave_extension(ctx, extension_map)

    assert returned_map is parent_map
    assert returned_player.pos == world.Position(4, 5)
    assert not ctx.dungeon_extension.active
    assert sum(entity.char == "@" for entity in parent_map.entities) == 1


def test_prison_exit_does_not_consume_orbit_disclosure_state():
    """Returning to Mars leaves the orbit disclosure queued for launch."""
    seed_rng(8)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    ctx.main_quest_progress["act1_prison"] = "completed"
    ctx.dungeon_extension = DungeonExtensionState(
        extension_id="mars_alien_prison",
        current_floor=1,
        active=True,
        parent_map_key="surface:mars",
        parent_position=parent_player.pos,
        state_flags={"prison_data_extracted"},
    )
    extension_map, _ = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )

    dungeon_extensions.leave_extension(ctx, extension_map)

    assert not ctx.post_prison_orbit_seen
    assert ctx.main_quest_disclosure == ""
    assert "prison_data_extracted" in ctx.dungeon_extension.state_flags


def test_activation_fires_once_and_persists_event_id(monkeypatch):
    seed_rng(9)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    extension_map, extension_player = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )

    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda _ctx, faction, message, *, title: shown.append((faction, title)),
    )
    event_id = "prison_floor1_security_alpha"
    extension_player.pos = _position_between_security_thresholds(extension_map)

    assert dungeon_extensions.tick_activation(ctx)
    assert event_id in ctx.dungeon_extension.activated_events
    assert "prison_floor1_security_beta" not in ctx.dungeon_extension.activated_events
    assert any(
        entity.npc_char_id == "sentry_drone"
        and entity.squad_id == f"{event_id}_security"
        and not entity.powered_down
        for entity in extension_map.entities
    )
    assert shown == [("ALIEN SECURITY", "SECURITY POWER RISING")]
    entity_count = len(extension_map.entities)

    assert not dungeon_extensions.tick_activation(ctx)
    assert len(extension_map.entities) == entity_count


def test_second_activation_spawns_assault_drone_near_deeper_anchor(monkeypatch):
    seed_rng(12)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    extension_map, extension_player = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda *args, **kwargs: None,
    )
    event_id = "prison_floor1_security_beta"
    ctx.dungeon_extension.activated_events.add(
        "prison_floor1_security_alpha",
    )
    extension_player.pos = extension_map.down_stair_pos

    assert dungeon_extensions.tick_activation(ctx)
    assert event_id in ctx.dungeon_extension.activated_events
    assert any(
        entity.npc_char_id == "assault_drone"
        and entity.squad_id == f"{event_id}_security"
        and not entity.powered_down
        for entity in extension_map.entities
    )


def test_progress_trigger_fires_when_anchor_is_skipped(monkeypatch):
    seed_rng(13)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    extension_map, extension_player = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda *args, **kwargs: None,
    )
    extension_player.pos = extension_map.down_stair_pos

    assert dungeon_extensions.tick_activation(ctx)
    assert {
        "prison_floor1_security_alpha",
        "prison_floor1_security_beta",
    } <= ctx.dungeon_extension.activated_events
    assert sum(
        entity.npc_char_id in {"sentry_drone", "assault_drone"}
        and not entity.powered_down
        for entity in extension_map.entities
    ) == 2


def test_cached_floor_repairs_pre_phase_two_missing_down_stairs():
    seed_rng(14)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    floor_one, _ = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    _down = floor_one.down_stair_pos
    floor_one.tiles[_down.y][_down.x] = world.DUNGEON_FLOOR
    del floor_one.down_stair_pos
    dungeon_extensions.leave_extension(ctx, floor_one)

    repaired, _ = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )

    assert repaired.down_stair_pos is not None
    assert repaired.tiles[
        repaired.down_stair_pos.y
    ][repaired.down_stair_pos.x].kind == "stairs_down"


def test_cached_floor_repairs_invalid_stair_metadata():
    seed_rng(13)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    floor_two, _ = dungeon_extensions.transition_floor(ctx, 1)
    floor_two.up_stair_pos = world.Position(999, 999)
    floor_two.down_stair_pos = world.Position(-1, -1)

    returned_one, _ = dungeon_extensions.transition_floor(ctx, -1)
    assert returned_one.extension_floor == 1
    restored_two, _ = dungeon_extensions.transition_floor(ctx, 1)
    assert restored_two.up_stair_pos is not None
    assert restored_two.down_stair_pos is not None
    assert restored_two.tiles[
        restored_two.down_stair_pos.y
    ][restored_two.down_stair_pos.x].kind == "stairs_down"


def test_cached_floor_repairs_missing_activation_positions():
    seed_rng(11)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    extension_map, _ = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    ctx.dungeon_extension.event_positions.clear()

    dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )

    assert set(ctx.dungeon_extension.event_positions) == set(
        extension_map.activation_positions,
    )


def test_extension_map_metadata_round_trips():
    seed_rng(10)
    game_map, _ = dungeon_extensions._generate_floor("mars_alien_prison", 1)
    payload = _dungeon_to_dict(game_map, None)

    restored, _ = _dungeon_from_dict(payload)

    assert restored.extension_id == "mars_alien_prison"
    assert restored.extension_floor == 1
    assert restored.activation_positions == game_map.activation_positions
    assert restored.extension_entry_id == getattr(game_map, "extension_entry_id", "")
    assert getattr(restored, "feature_theme", "") == getattr(
        game_map, "feature_theme", "",
    )
    assert restored.up_stair_pos == game_map.up_stair_pos
    assert restored.down_stair_pos == game_map.down_stair_pos
    assert restored.tiles[game_map.entry_spawn.y][game_map.entry_spawn.x].kind == "stairs_up"


def test_phase_two_floors_have_expected_stair_connections_and_population():
    for floor in (2, 3):
        seed_rng(100 + floor)
        game_map, spawn = dungeon_extensions._generate_floor(
            "mars_alien_prison", floor,
        )

        assert game_map.extension_floor == floor
        assert game_map.location_name == f"Alien Prison F{floor}"
        assert game_map.up_stair_pos == spawn
        assert game_map.tiles[spawn.y][spawn.x] is world.STAIRS_UP
        if floor == 2:
            assert game_map.feature_theme == "prisoner_quarters"
            assert sum(
                tile.kind == "prison_cell_door"
                for row in game_map.tiles for tile in row
            ) >= 1
            assert sum(
                tile.kind == "security_post"
                for row in game_map.tiles for tile in row
            ) >= 1
            assert game_map.down_stair_pos is not None
            assert game_map.tiles[
                game_map.down_stair_pos.y
            ][game_map.down_stair_pos.x] is world.STAIRS_DOWN
        else:
            assert game_map.feature_theme == "defensive_layer"
            assert sum(
                tile.kind == "defense_barrier"
                for row in game_map.tiles for tile in row
            ) >= 1
            assert sum(
                tile.kind == "security_node"
                for row in game_map.tiles for tile in row
            ) >= 1
            assert game_map.down_stair_pos is not None
            assert game_map.tiles[
                game_map.down_stair_pos.y
            ][game_map.down_stair_pos.x] is world.STAIRS_DOWN
        assert any(entity.npc_char_id for entity in game_map.entities)


def test_phase_three_floor_four_has_engineering_and_elevator_anchors():
    for seed in (304, 307, 308, 309, 310):
        seed_rng(seed)
        game_map, _ = dungeon_extensions._generate_floor("mars_alien_prison", 4)

        _assert_floor_four_interactions_are_separate(game_map)


def _assert_floor_four_interactions_are_separate(game_map):

    assert game_map.location_name == "Alien Prison F4"
    assert game_map.feature_theme == "high_risk_quarters"
    assert sum(
        tile.kind == "engineering_floor"
        for row in game_map.tiles for tile in row
    ) >= 1
    assert sum(
        tile.kind == "high_risk_cell_door"
        for row in game_map.tiles for tile in row
    ) >= 1
    _interactions = {
        entity.dungeon_interaction for entity in game_map.entities
    }
    assert {"engineering_console", "deep_elevator"} <= _interactions
    assert game_map.down_stair_pos is not None
    _console = next(
        entity for entity in game_map.entities
        if entity.dungeon_interaction == "engineering_console"
    )
    _elevator = next(
        entity for entity in game_map.entities
        if entity.dungeon_interaction == "deep_elevator"
    )
    _distance = dungeon_extensions._walkable_distances(
        game_map, _elevator.pos,
    ).get((_console.pos.x, _console.pos.y), -1)
    assert _distance >= 8
    _rooms = dungeon_extension_layout._room_core_components(game_map)
    _distances = dungeon_extensions._walkable_distances(
        game_map, _elevator.pos,
    )
    _elevator_room = min(
        _rooms,
        key=lambda room: min(
            _distances.get(cell, float("inf")) for cell in room
        ),
    )
    assert not any(
        (_console.pos.x, _console.pos.y) in room
        for room in _rooms
        if room is _elevator_room
    )


def test_phase_three_elevator_requires_power_then_reaches_floor_five():
    seed_rng(305)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    dungeon_extensions.transition_floor(ctx, 1)
    dungeon_extensions.transition_floor(ctx, 1)
    floor_four, _ = dungeon_extensions.transition_floor(ctx, 1)

    assert ctx.dungeon_extension.current_floor == 4
    assert not dungeon_extensions.elevator_is_powered(ctx)
    try:
        dungeon_extensions.transition_floor(ctx, 1)
    except ValueError as exc:
        assert "unpowered" in str(exc)
    else:
        raise AssertionError("unpowered elevator should block Floor 5")

    assert dungeon_extensions.restore_power(ctx)
    assert ctx.dungeon_extension.power_restored
    assert dungeon_extensions.elevator_is_powered(ctx)
    floor_five, _ = dungeon_extensions.transition_floor(ctx, 1)
    assert floor_five.extension_floor == 5
    assert floor_five.location_name == "Alien Prison F5"


def test_phase_three_power_state_round_trips_in_extension_state():
    state = DungeonExtensionState(
        extension_id="mars_alien_prison",
        current_floor=4,
        active=True,
        power_restored=True,
    )
    assert dungeon_extensions.elevator_is_powered(
        SimpleNamespace(dungeon_extension=state),
    )


def test_unrelated_state_flag_does_not_power_elevator():
    state = DungeonExtensionState(
        extension_id="mars_alien_prison",
        current_floor=4,
        active=True,
        state_flags={"unrelated_system"},
    )
    assert not dungeon_extensions.elevator_is_powered(
        SimpleNamespace(dungeon_extension=state),
    )


def test_floor_four_repair_reanchors_existing_elevator_to_repaired_stairs():
    seed_rng(306)
    game_map, _ = dungeon_extensions._generate_floor("mars_alien_prison", 4)
    _elevator = next(
        entity for entity in game_map.entities
        if entity.dungeon_interaction == "deep_elevator"
    )
    _console = next(
        entity for entity in game_map.entities
        if entity.dungeon_interaction == "engineering_console"
    )
    _old_down = game_map.down_stair_pos
    _stale_console_pos = world.Position(1, 1)
    game_map.tiles[_old_down.y][_old_down.x] = world.DUNGEON_FLOOR
    game_map.down_stair_pos = world.Position(1, 1)
    game_map.tiles[1][1] = world.DUNGEON_FLOOR
    _console.pos = _stale_console_pos

    dungeon_extensions._ensure_floor_connections(
        game_map, "mars_alien_prison", 4,
    )

    assert game_map.down_stair_pos is not None
    assert _elevator.pos == game_map.down_stair_pos
    assert game_map.tiles[
        game_map.down_stair_pos.y
    ][game_map.down_stair_pos.x].kind == "stairs_down"
    assert _console.pos != _stale_console_pos
    _distance = dungeon_extensions._walkable_distances(
        game_map, _elevator.pos,
    ).get((_console.pos.x, _console.pos.y), -1)
    assert _distance >= 8
    assert game_map.tiles[
        _console.pos.y
    ][_console.pos.x].kind == "engineering_floor"


def test_interaction_placement_has_unrestricted_fallback(monkeypatch):
    seed_rng(307)
    game_map, _ = dungeon_extensions._generate_floor("mars_alien_prison", 4)
    spec = dungeon_extensions._floor_spec("mars_alien_prison", 4)
    console = next(
        interaction for interaction in spec.interactions
        if interaction.id == "engineering_console"
    )
    game_map.entities[:] = [
        entity for entity in game_map.entities
        if entity.dungeon_interaction != "engineering_console"
    ]
    calls = []

    def _fallback(game_map, cells, **kwargs):
        calls.append(kwargs.get("forbidden_positions", ()))
        if kwargs.get("forbidden_positions"):
            return None
        return world.Position(2, 2)

    monkeypatch.setattr(
        "src.spacehack.dungeon_extensions._free_interaction_position",
        _fallback,
    )
    dungeon_extensions._stamp_interactions(
        game_map, spec, game_map.entry_spawn, interactions=(console,),
    )

    assert calls[-1] == ()
    _consoles = [
        entity for entity in game_map.entities
        if entity.dungeon_interaction == "engineering_console"
    ]
    assert len(_consoles) == 1
    assert _consoles[0].pos == world.Position(2, 2)


def test_phase_four_deep_cell_has_epic_bridge_and_terminal_landing():
    """F5 arrival is an exposed bridge over void into a terminal landing."""
    seed_rng(401)
    game_map, _spawn = dungeon_extensions._generate_floor(
        "mars_alien_prison", 5,
    )

    assert game_map.landmark_variant_id == "alien_prison_deep_cell"
    assert game_map.tiles[game_map.entry_spawn.y][game_map.entry_spawn.x] is world.STAIRS_UP
    assert sum(
        tile.kind == "stairs_up"
        for row in game_map.tiles for tile in row
    ) == 1
    assert world.VOID.walkable is False
    assert world.BRIDGE.walkable is True
    assert world.TERMINAL_LANDING.walkable is True
    assert sum(tile.kind == "void" for row in game_map.tiles for tile in row) >= 1
    assert sum(tile.kind == "bridge" for row in game_map.tiles for tile in row) >= 20
    assert sum(
        tile.kind == "terminal_landing"
        for row in game_map.tiles for tile in row
    ) >= 20
    _landing_terminals = [
        entity for entity in game_map.entities
        if entity.name == "Landmark Terminal"
    ]
    assert len(_landing_terminals) >= 3
    assert all(
        (entity.pos.x, entity.pos.y) in game_map.landmark_footprint
        for entity in _landing_terminals
    )


def test_phase_four_deep_cell_floor_has_landmark_set_dressing_and_live_terminal():
    for seed in (401, 402, 403):
        seed_rng(seed)
        game_map, _ = dungeon_extensions._generate_floor("mars_alien_prison", 5)

        assert game_map.location_name == "Alien Prison F5"
        assert game_map.feature_theme == "deep_cell"
        assert getattr(game_map, "landmark_footprint", set())
        assert sum(
            tile.kind == "deep_cell_floor"
            for row in game_map.tiles for tile in row
        ) >= 1
        assert sum(
            tile.kind == "torn_door"
            for row in game_map.tiles for tile in row
        ) >= 1
        assert sum(
            tile.kind == "claw_scar"
            for row in game_map.tiles for tile in row
        ) >= 20
        assert sum(
            tile.kind == "landmark_entrance"
            for row in game_map.tiles for tile in row
        ) == 1
        assert not any(
            entity.npc_char_id
            and (entity.pos.x, entity.pos.y) in game_map.landmark_footprint
            for entity in game_map.entities
        )
        _terminal = next(
            entity for entity in game_map.entities
            if entity.dungeon_interaction == "deep_cell_data_terminal"
        )
        assert (
            _terminal.pos.x, _terminal.pos.y
        ) in game_map.landmark_footprint
        _dead = [
            entity for entity in game_map.entities
            if entity.interaction_flavor
        ]
        assert len(_dead) >= 3
        _live = [
            entity for entity in game_map.entities
            if entity.dungeon_interaction == "deep_cell_data_terminal"
        ]
        assert len(_live) == 1


def test_phase_four_deep_cell_keeps_up_stair_after_theme_stamp():
    for seed in (407, 408):
        seed_rng(seed)
        game_map, spawn = dungeon_extensions._generate_floor(
            "mars_alien_prison", 5,
        )

        # The deep-cell theme pass converts walkable tiles to alien
        # flooring but must never clobber the connection markers — a
        # clobbered up-stair would relocate F5's exit to an arbitrary
        # cell on re-entry (elevator continuity break).
        assert game_map.tiles[spawn.y][spawn.x] is world.STAIRS_UP
        assert game_map.up_stair_pos == spawn
        assert sum(
            tile.kind == "deep_cell_floor"
            for row in game_map.tiles for tile in row
        ) >= 1


def test_ascent_events_are_gated_until_data_extraction(monkeypatch):
    seed_rng(409)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    extension_map, extension_player = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda *args, **kwargs: None,
    )
    extension_player.pos = extension_map.up_stair_pos

    assert not dungeon_extensions.tick_activation(ctx)
    assert not any(
        event_id.startswith("prison_ascent_")
        for event_id in ctx.dungeon_extension.activated_events
    )

    ctx.dungeon_extension.state_flags.add("prison_data_extracted")
    extension_player.pos = extension_map.down_stair_pos
    assert not dungeon_extensions.tick_activation(ctx)
    assert not ctx.dungeon_extension.activated_events


def test_ascent_progress_targets_upper_stairs_and_escalates(monkeypatch):
    seed_rng(410)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda *args, **kwargs: None,
    )
    floor_two, _ = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    dungeon_extensions.transition_floor(ctx, 1)
    floor_two = ctx.game_map
    ctx.dungeon_extension.state_flags.add("prison_data_extracted")
    ctx.player.pos = floor_two.up_stair_pos

    assert dungeon_extensions.tick_activation(ctx)
    assert len(ctx.dungeon_extension.activated_events) == 1
    assert ctx.dungeon_extension.activated_events == {
        "prison_ascent_f2_assault",
    }
    assert sum(
        entity.npc_char_id == "assault_drone"
        and not entity.powered_down
        for entity in floor_two.entities
    ) == 2

    assert dungeon_extensions.tick_activation(ctx)
    assert ctx.dungeon_extension.activated_events == {
        "prison_ascent_f2_assault",
        "prison_ascent_f2_sentries",
    }
    assert sum(
        entity.npc_char_id == "sentry_drone"
        and not entity.powered_down
        for entity in floor_two.entities
    ) == 2
    assert not dungeon_extensions.tick_activation(ctx)


def test_descent_events_are_suppressed_after_extraction(monkeypatch):
    seed_rng(411)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    extension_map, extension_player = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda *args, **kwargs: None,
    )
    ctx.dungeon_extension.state_flags.add("prison_data_extracted")
    extension_player.pos = extension_map.down_stair_pos

    assert not dungeon_extensions.tick_activation(ctx)
    assert not any(
        event_id.startswith("prison_floor1_security_")
        for event_id in ctx.dungeon_extension.activated_events
    )


def test_phase_four_extraction_completes_prison_objective(monkeypatch):
    seed_rng(404)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    ctx.context = object()
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda *args, **kwargs: None,
    )
    from src.spacehack.main_quest import start_step

    ctx.main_quest_progress["act1_prison"] = "available"
    start_step(ctx, "act1_prison")
    dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    dungeon_extensions.transition_floor(ctx, 1)
    dungeon_extensions.transition_floor(ctx, 1)
    _floor_four, _ = dungeon_extensions.transition_floor(ctx, 1)
    assert ctx.dungeon_extension.current_floor == 4
    assert dungeon_extensions.restore_power(ctx)
    assert dungeon_extensions.elevator_is_powered(ctx)
    _floor_five, _ = dungeon_extensions.transition_floor(ctx, 1)

    assert ctx.main_quest_progress.get("act1_prison") == "active"
    assert dungeon_extensions.activate_interaction_state(
        ctx, "deep_cell_data_terminal",
    )
    assert "prison_data_extracted" in ctx.dungeon_extension.state_flags
    assert ctx.main_quest_progress.get("act1_prison") == "completed"
    assert ctx.player_xp >= 120

    assert not dungeon_extensions.activate_interaction_state(
        ctx, "deep_cell_data_terminal",
    )


def test_phase_four_entry_activates_prison_objective(monkeypatch):
    seed_rng(405)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)
    ctx.context = object()
    monkeypatch.setattr(
        "src.spacehack.main_quest.show_gate_popup",
        lambda *args, **kwargs: None,
    )
    ctx.main_quest_progress["act1_prison"] = "available"

    dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )

    assert ctx.main_quest_progress.get("act1_prison") == "active"


def test_phase_four_deep_cell_floor_round_trips():
    seed_rng(406)
    game_map, _ = dungeon_extensions._generate_floor("mars_alien_prison", 5)
    payload = _dungeon_to_dict(game_map, None)

    restored, _ = _dungeon_from_dict(payload)

    assert restored.extension_floor == 5
    assert restored.landmark_variant_id == game_map.landmark_variant_id
    assert getattr(restored, "landmark_footprint", set())
    assert restored.landmark_interaction_cells == {
        (_cell.x, _cell.y)
        for _cell in game_map.landmark_interaction_cells
    }
    assert sum(
        tile.kind == "deep_cell_floor"
        for row in restored.tiles for tile in row
    ) >= 1
    assert sum(
        tile.kind == "torn_door"
        for row in restored.tiles for tile in row
    ) >= 1
    _restored_live = [
        entity for entity in restored.entities
        if entity.dungeon_interaction == "deep_cell_data_terminal"
    ]
    assert len(_restored_live) == 1
    _terminal_position = (_restored_live[0].pos.x, _restored_live[0].pos.y)
    assert _terminal_position in restored.landmark_footprint
    assert _terminal_position in restored.landmark_interaction_cells
    assert any(entity.interaction_flavor for entity in restored.entities)

    dungeon_extensions._ensure_floor_connections(
        restored, "mars_alien_prison", 5,
    )

    _repaired_live = next(
        entity for entity in restored.entities
        if entity.dungeon_interaction == "deep_cell_data_terminal"
    )
    assert (_repaired_live.pos.x, _repaired_live.pos.y) == _terminal_position
    assert (_repaired_live.pos.x, _repaired_live.pos.y) in restored.landmark_footprint


def test_landmark_interaction_metadata_ignores_malformed_coordinates():
    seed_rng(407)
    game_map, _ = dungeon_extensions._generate_floor("mars_alien_prison", 5)
    game_map.landmark_interaction_cells = [
        world.Position(1, 2),
        (3, 4),
        ("bad", 6),
        (7,),
        None,
    ]

    payload = _dungeon_to_dict(game_map, None)

    assert payload["landmark_interaction_cells"] == [[1, 2], [3, 4]]
    restored, _ = _dungeon_from_dict({
        **payload,
        "landmark_interaction_cells": [[1, 2], ["bad", 6], [8]],
    })

    assert restored.landmark_interaction_cells == {(1, 2)}


def test_old_dungeon_payload_without_landmark_interaction_metadata_loads():
    seed_rng(408)
    game_map, _ = dungeon_extensions._generate_floor("mars_alien_prison", 1)
    payload = _dungeon_to_dict(game_map, None)
    payload.pop("landmark_interaction_cells")

    restored, _ = _dungeon_from_dict(payload)

    assert not hasattr(restored, "landmark_interaction_cells")
    assert restored.extension_floor == 1


def test_phase_two_transition_caches_maps_and_backtracks_to_stairs():
    seed_rng(202)
    parent_map, parent_player = _parent_map()
    ctx = _ctx(parent_map, parent_player)

    floor_one, _ = dungeon_extensions.enter_extension(
        ctx,
        parent_map,
        parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    floor_one_marker = world.Entity(
        "!", (255, 255, 255), floor_one.entry_spawn, "Test marker",
    )
    floor_one.entities.append(floor_one_marker)
    floor_two, floor_two_player = dungeon_extensions.transition_floor(ctx, 1)

    assert ctx.dungeon_extension.current_floor == 2
    assert floor_two.location_name == "Alien Prison F2"
    assert floor_two.tiles[
        floor_two.up_stair_pos.y
    ][floor_two.up_stair_pos.x] is world.STAIRS_UP
    assert floor_two.down_stair_pos is not None

    floor_three, _ = dungeon_extensions.transition_floor(ctx, 1)
    assert ctx.dungeon_extension.current_floor == 3
    assert floor_three.location_name == "Alien Prison F3"
    assert floor_three.down_stair_pos is not None

    floor_four, _ = dungeon_extensions.transition_floor(ctx, 1)
    assert ctx.dungeon_extension.current_floor == 4
    assert floor_four.location_name == "Alien Prison F4"

    returned_three, returned_player = dungeon_extensions.transition_floor(ctx, -1)
    assert returned_three is floor_three
    assert returned_player.pos == floor_three.down_stair_pos
    assert ctx.dungeon_extension.current_floor == 3

    returned_two, _ = dungeon_extensions.transition_floor(ctx, -1)
    assert returned_two is floor_two
    assert ctx.dungeon_extension.current_floor == 2

    returned_one, _ = dungeon_extensions.transition_floor(ctx, -1)
    assert returned_one is floor_one
    assert returned_one.entity_at(
        floor_one_marker.pos.x, floor_one_marker.pos.y,
    ) is floor_one_marker
    assert ctx.dungeon_extension.current_floor == 1

    surface_map, _ = dungeon_extensions.leave_extension(ctx, returned_one)
    assert surface_map is parent_map
    assert not ctx.dungeon_extension.active
