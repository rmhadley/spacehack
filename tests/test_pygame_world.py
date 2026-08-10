"""Tests for the opt-in Pygame world-frame migration seam."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import pygame_world, world


def _map(*, seen=None, visible=None, entities=None) -> world.GameMap:
    tile = world.Tile("floor", ".", True, (200, 210, 220), (10, 20, 30))
    return world.GameMap(
        width=4,
        height=3,
        tiles=[[tile for _ in range(4)] for _ in range(3)],
        entities=list(entities or []),
        seen=seen,
        visible=visible,
    )


def test_world_commands_center_small_map_and_preserve_tile_backgrounds():
    player = world.Entity("@", (255, 255, 255), world.Position(1, 1))
    game_map = _map(entities=[player])

    commands = world.world_draw_commands(
        game_map,
        region_x=2,
        region_y=3,
        region_w=8,
        region_h=6,
        centered=True,
    )

    assert commands[0] == world.WorldDrawCommand(
        4, 4, ".", (200, 210, 220), (10, 20, 30),
    )
    assert commands[-1] == world.WorldDrawCommand(
        5, 5, "@", (255, 255, 255), None,
    )


def test_world_commands_skip_unseen_cells_and_dim_remembered_cells():
    seen = [[False, True, False, False] for _ in range(3)]
    visible = [[False, False, False, False] for _ in range(3)]
    static = world.Entity("!", (255, 200, 100), world.Position(1, 0))
    moving = world.Entity("m", (255, 100, 100), world.Position(2, 0), npc_id="npc")
    game_map = _map(seen=seen, visible=visible, entities=[static, moving])

    commands = world.world_draw_commands(
        game_map,
        region_x=0,
        region_y=0,
        region_w=4,
        region_h=3,
    )

    tile_commands = [command for command in commands if command.char == "."]
    assert {(command.x, command.y) for command in tile_commands} == {
        (1, 0), (1, 1), (1, 2),
    }
    assert any(command.char == "!" and command.fg == (89, 70, 35) for command in commands)
    assert not any(command.char == "m" for command in commands)
    assert not any(command.x != 1 for command in commands)


def test_world_commands_clamp_out_of_range_camera_coordinates():
    game_map = _map()

    commands = world.world_draw_commands(
        game_map,
        region_x=0,
        region_y=0,
        region_w=2,
        region_h=2,
        camera_x=99,
        camera_y=99,
    )

    assert commands[0].char == "."
    assert (commands[0].x, commands[0].y) == (0, 0)


def test_world_commands_cull_footprints_and_sort_loot_only_for_scrollable_view():
    loot = world.Entity("%", (255, 215, 0), world.Position(1, 1), loot_data={"goods": []})
    ship = world.Entity("S", (100, 220, 255), world.Position(1, 1))
    offscreen = world.Entity("X", (255, 0, 0), world.Position(0, 0))
    game_map = _map(entities=[ship, loot, offscreen])
    game_map.width = 8
    game_map.height = 8
    game_map.tiles = [game_map.tiles[0] * 2 for _ in range(8)]

    commands = world.world_draw_commands(
        game_map,
        region_x=0,
        region_y=0,
        region_w=2,
        region_h=2,
        camera_x=1,
        camera_y=1,
        sort_entities=True,
    )

    entity_commands = [command for command in commands if command.char in "%SX"]
    assert [command.char for command in entity_commands] == ["%", "S"]
    assert not any(command.char == "X" for command in entity_commands)
    assert game_map.entities == [ship, loot, offscreen]


def test_world_frame_payload_round_trips_commands_and_size():
    frame = pygame_world.WorldFrame(
        logical_size=(1280, 768),
        commands=(world.WorldDrawCommand(1, 2, "@", (255, 255, 255), None),),
    )

    restored = pygame_world._frame_from_payload(frame.payload())

    assert restored == frame
    assert restored.logical_size == (1280, 768)


def test_world_preview_is_disabled_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_WORLD", raising=False)

    assert pygame_world.start_if_enabled() is None


def test_dead_world_preview_rejects_new_frames_without_writing():
    class DeadProcess:
        stdin = None

        @staticmethod
        def poll():
            return 1

        @staticmethod
        def wait(timeout):
            return 1

    preview = pygame_world.PygameWorldPreview(DeadProcess())
    frame = pygame_world.WorldFrame((1600, 960), ())

    assert not preview.alive
    assert not preview.send(frame)
    preview.close()
