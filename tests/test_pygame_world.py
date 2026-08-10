"""Tests for the Pygame exploration-frame presentation seam."""

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


def test_earth_grass_accent_uses_field_background_and_unique_comma_color():
    assert world.GRASS_ACCENT.char == ","
    assert world.GRASS_ACCENT.bg == world.GRASS.bg
    assert world.GRASS_ACCENT.fg == (57, 100, 47)
    assert world.GRASS_ACCENT.fg != world.GRASS.fg


def test_derived_grass_accent_uses_derived_field_background():
    from src.spacehack.data.planets.themes import derive_theme

    theme = derive_theme(grass=(100, 180, 80))

    assert theme.grass_accent.bg == theme.grass.bg
    assert theme.grass_accent.fg != theme.grass.fg


def test_all_named_planet_themes_keep_grass_accents_on_field_background():
    from src.spacehack.data.planets import themes

    named_themes = (
        themes.EARTH,
        themes.MARS,
        themes.DESERT,
        themes.LUSH,
        themes.CLOUD_CITY,
        themes.ICE,
        themes.WARM_EARTH,
        themes.STATION,
    )

    assert all(theme.grass_accent.bg == theme.grass.bg for theme in named_themes)


def test_capture_console_clips_text_and_preserves_colors_and_backgrounds():
    capture = pygame_world.CaptureConsole(4, 2)

    capture.print(
        x=2,
        y=1,
        string="hello",
        fg=(1, 2, 3),
        bg=(4, 5, 6),
    )

    assert capture.commands == [
        world.WorldDrawCommand(2, 1, "h", (1, 2, 3), (4, 5, 6)),
        world.WorldDrawCommand(3, 1, "e", (1, 2, 3), (4, 5, 6)),
    ]


def test_capture_console_handles_newlines_and_vertical_clipping():
    capture = pygame_world.CaptureConsole(4, 2)

    capture.print(x=0, y=0, string="a" + "\n" + "bc", fg=(1, 2, 3))

    assert capture.commands == [
        world.WorldDrawCommand(0, 0, "a", (1, 2, 3), None),
        world.WorldDrawCommand(0, 1, "b", (1, 2, 3), None),
        world.WorldDrawCommand(1, 1, "c", (1, 2, 3), None),
    ]


def test_capture_console_clear_removes_previous_commands():
    capture = pygame_world.CaptureConsole(4, 2)
    capture.print(string="old")

    capture.clear()

    assert capture.commands == []


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


def test_exploration_frame_uses_custom_logical_dimensions(monkeypatch):
    ctx = SimpleNamespace(
        log=SimpleNamespace(capacity=2, recent=lambda _n=None: []),
        character_info={"species_name": "human", "class_name": "merchant"},
        stats=SimpleNamespace(gunnery=1, piloting=2, engineering=3, credits=100),
        player_owned_ship=None,
        player_xp=0,
        player_level=1,
        player_skill_points=0,
        ground_stats=SimpleNamespace(reflexes=1, strength=2, stamina=3),
        ground_hp=23,
        ground_max_hp=23,
        time_day=1,
        time_month=1,
        time_year=2200,
    )

    frame = pygame_world.make_exploration_frame(
        ctx,
        _map(),
        mode="city",
        location="Earth",
        region_x=0,
        region_y=0,
        region_w=4,
        region_h=3,
        centered=True,
        logical_size=(1280, 768),
    )

    assert any(command.x == 60 for command in frame.commands)
    assert all(command.x < 80 for command in frame.commands)
    assert all(command.y < 48 for command in frame.commands)


def test_exploration_frame_appends_hud_and_log_after_map(monkeypatch):
    class FakeLog:
        capacity = 6

        def __init__(self):
            self.entries = []

        def recent(self, _n=None):
            return self.entries

    ctx = SimpleNamespace(
        log=FakeLog(),
        character_info={"species_name": "human", "class_name": "merchant"},
        stats=SimpleNamespace(
            gunnery=1, piloting=2, engineering=3, credits=100,
        ),
        player_owned_ship=None,
        player_xp=0,
        player_level=1,
        player_skill_points=0,
        ground_stats=SimpleNamespace(reflexes=1, strength=2, stamina=3),
        ground_hp=23,
        ground_max_hp=23,
        time_day=1,
        time_month=1,
        time_year=2200,
    )
    monkeypatch.setattr(
        ctx.log,
        "recent",
        lambda _n=None: [SimpleNamespace(text="Hello", fg=(9, 8, 7))],
    )

    frame = pygame_world.make_exploration_frame(
        ctx,
        _map(),
        mode="city",
        location="Earth",
        region_x=0,
        region_y=0,
        region_w=4,
        region_h=3,
        centered=True,
    )

    assert any(command.char == "S" for command in frame.commands)
    assert any(command.char == ">" and command.fg == (9, 8, 7) for command in frame.commands)
    assert any(command.char == "Spacehack"[0] for command in frame.commands)
    assert frame.commands.index(next(command for command in frame.commands if command.char == "S")) < frame.commands.index(next(command for command in frame.commands if command.char == "H"))


def test_world_preview_starts_when_requested(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        pygame_world.PygameWorldPreview,
        "start",
        staticmethod(lambda: sentinel),
    )

    assert pygame_world.start_if_enabled() is sentinel


def test_world_preview_starts_without_environment_flags(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        pygame_world.PygameWorldPreview,
        "start",
        staticmethod(lambda: sentinel),
    )

    assert pygame_world.start_if_enabled() is sentinel


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
