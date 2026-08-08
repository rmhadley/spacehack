"""Regression tests for the reusable themed dungeon extension runtime."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import dungeon_extensions
from src.spacehack import dungeon
from src.spacehack import message_log
from src.spacehack import world
from src.spacehack.data.dungeon_extensions import find_extension
from src.spacehack.game_context import DungeonExtensionState
from src.spacehack.engine import seed_rng
from src.spacehack.saveload import _dungeon_from_dict, _dungeon_to_dict


def _ctx(parent_map: world.GameMap, parent_player: world.Entity):
    return SimpleNamespace(
        interiors={"surface:mars": parent_map},
        dungeon_extension=None,
        game_map=parent_map,
        player=parent_player,
        current_city_id="mars",
        log=message_log.MessageLog(capacity=6),
    )


def _parent_map() -> tuple[world.GameMap, world.Entity]:
    tiles = [[world.DUNGEON_FLOOR for _ in range(12)] for _ in range(12)]
    game_map = world.GameMap(12, 12, tiles, [])
    player = world.Entity("@", (255, 255, 255), world.Position(4, 5), "Player")
    game_map.entities.append(player)
    return game_map, player


def test_floor_generation_has_up_stairs_and_stable_activation_anchors():
    seed_rng(7)
    game_map, spawn = dungeon_extensions._generate_floor("mars_alien_prison", 1)

    assert game_map.tiles[spawn.y][spawn.x] is world.STAIRS_UP
    assert set(game_map.activation_positions) == {
        "prison_floor1_security_alpha",
        "prison_floor1_security_beta",
    }
    assert all(game_map.is_walkable(pos.x, pos.y)
               for pos in game_map.activation_positions.values())


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
    event_pos = dungeon_extensions._event_position(ctx, event_id)
    assert event_pos is not None
    extension_player.pos = event_pos

    assert dungeon_extensions.tick_activation(ctx)
    assert event_id in ctx.dungeon_extension.activated_events
    assert shown == [("ALIEN SECURITY", "SECURITY POWER RISING")]
    entity_count = len(extension_map.entities)

    assert not dungeon_extensions.tick_activation(ctx)
    assert len(extension_map.entities) == entity_count


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
    assert restored.tiles[game_map.entry_spawn.y][game_map.entry_spawn.x].kind == "stairs_up"
