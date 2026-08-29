"""Tests for the Pygame capture console and renderer-neutral world commands."""

from __future__ import annotations

from src.spacehack import pygame_world, world
from src.spacehack.data.planets import hangar_anchor
from src.spacehack.framebuffer import FrameBuffer


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


def test_registered_city_themes_lift_near_black_surface_backgrounds():
    from src.spacehack.data.planets import (
        _CITY_THEME_FIELDS,
        _CITY_BG_MIN_CHANNEL,
        _CITY_BG_MIN_LUMA,
        _city_bg_luma,
        _readable_city_theme,
        list_planet_specs,
    )

    for spec in list_planet_specs():
        theme = _readable_city_theme(spec.theme or world.EARTH_THEME)
        for field in _CITY_THEME_FIELDS:
            tile = getattr(theme, field)
            assert min(tile.bg) >= _CITY_BG_MIN_CHANNEL
            assert _city_bg_luma(tile.bg) >= _CITY_BG_MIN_LUMA
            if field in {"floor", "landing_pad"}:
                assert tile.char == "."


def test_compact_city_floor_is_sparse_and_entities_inherit_its_background():
    from src.spacehack.data.planets import list_planet_specs, load_planet

    for spec in list_planet_specs():
        if spec.width >= 60:
            continue
        game_map = load_planet(spec.id)
        floor_tiles = [
            tile
            for row in game_map.tiles
            for tile in row
            if tile.kind == "floor"
        ]
        assert floor_tiles
        assert all(tile.char == "." for tile in floor_tiles)

        for entity in game_map.entities:
            tile = game_map.tiles[entity.pos.y][entity.pos.x]
            if tile.kind != "floor":
                continue
            console = FrameBuffer(game_map.width, game_map.height)
            world.render_world(
                console,
                game_map,
                region_x=0,
                region_y=0,
                region_w=game_map.width,
                region_h=game_map.height,
            )
            assert console.cell(entity.pos.x, entity.pos.y).bg == tile.bg


def test_all_landable_city_pads_use_readable_entity_backgrounds():
    from src.spacehack.data.planets import (
        _CITY_BG_MIN_CHANNEL,
        _CITY_BG_MIN_LUMA,
        _city_bg_luma,
        list_planet_specs,
        load_planet,
    )

    for spec in list_planet_specs():
        game_map = load_planet(spec.id)
        pad_tiles = [
            tile
            for row in game_map.tiles
            for tile in row
            if tile.kind == "landing_pad"
        ]
        if pad_tiles:
            smooth_apron_cities = {"earth", "ac_station", "eri_b", "wolf_b", "cygni_b", "lal_b", "lal_c", "groom_b", "tc_b", "indi_b", "barnards_c", "ross_c", "vega_b"}
            expected_char = " " if spec.id in smooth_apron_cities else "."
            assert pad_tiles[0].char == expected_char
            assert min(pad_tiles[0].bg) >= _CITY_BG_MIN_CHANNEL
            assert _city_bg_luma(pad_tiles[0].bg) >= _CITY_BG_MIN_LUMA
        for entity in game_map.entities:
            tile = game_map.tiles[entity.pos.y][entity.pos.x]
            assert min(tile.bg) >= _CITY_BG_MIN_CHANNEL
            assert _city_bg_luma(tile.bg) >= _CITY_BG_MIN_LUMA


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
        5, 5, "@", (255, 255, 255), None, True,
        ".", (200, 210, 220), (10, 20, 30),
    )


def test_render_world_preserves_tile_background_behind_entity_glyphs():
    player = world.Entity("@", (255, 255, 255), world.Position(1, 1))
    game_map = _map(entities=[player])
    console = FrameBuffer(4, 3)

    world.render_world(
        console,
        game_map,
        region_x=0,
        region_y=0,
        region_w=4,
        region_h=3,
    )

    assert console.cell(1, 1).bg == (10, 20, 30)
    assert console.cell(1, 1).preserve_underlay is True


def test_ac_ii_hangar_entity_preserves_ice_landing_pad_background():
    from src.spacehack.data.planets import load_planet

    game_map = load_planet("ac_planet_2")
    hangar_ship = world.Entity(
        "t", (180, 200, 220), world.Position(7, 14), owned=True,
    )
    game_map.entities.append(hangar_ship)
    tile = game_map.tiles[hangar_ship.pos.y][hangar_ship.pos.x]
    console = FrameBuffer(80, 54)

    world.render_world(
        console,
        game_map,
        region_x=0,
        region_y=0,
        region_w=80,
        region_h=54,
    )

    assert tile.kind == "landing_pad"
    assert tile.char == "."
    assert console.cell(20 + hangar_ship.pos.x, 15 + hangar_ship.pos.y).bg == tile.bg


def test_earth_hangar_entity_preserves_landing_pad_background():
    from src.spacehack.data.planets import load_planet

    game_map = load_planet("earth")
    hangar_ship = world.Entity(
        "t", (180, 200, 220), hangar_anchor("earth"), owned=True,
    )
    game_map.entities.append(hangar_ship)
    tile = game_map.tiles[hangar_ship.pos.y][hangar_ship.pos.x]
    console = FrameBuffer(game_map.width, game_map.height)

    world.render_world(
        console,
        game_map,
        region_x=0,
        region_y=0,
        region_w=game_map.width,
        region_h=game_map.height,
    )

    assert tile.kind == "landing_pad"
    assert tile.char == " "
    from src.spacehack.data.planets import _readable_city_bg

    assert tile.bg == _readable_city_bg(world.LANDING_PAD.bg)
    assert console.cell(hangar_ship.pos.x, hangar_ship.pos.y).bg == tile.bg


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
