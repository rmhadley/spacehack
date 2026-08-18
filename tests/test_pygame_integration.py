"""Headless integration coverage for the real Pygame runtime."""

from __future__ import annotations

import pygame
import pytest

from src.spacehack import engine, pygame_engine, pygame_runtime, world
from src.spacehack.data.planets import load_planet
from src.spacehack.framebuffer import FrameBuffer


@pytest.fixture
def _pygame_headless(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.quit()
    yield
    pygame.quit()


def test_real_tileset_loads_the_native_glyph_cells(_pygame_headless):
    pygame.init()
    try:
        tileset = engine.load_tileset()

        assert (tileset.tile_width, tileset.tile_height) == (16, 16)
        assert tileset[ord("@")].get_size() == (16, 16)
        assert tileset[ord("#")].get_size() == (16, 16)
    finally:
        pygame.quit()


def test_real_runtime_presents_a_framebuffer_through_dummy_video(_pygame_headless):
    pygame.init()
    tileset = engine.load_tileset()
    runtime = pygame_runtime.PygameRuntime(tileset)

    try:
        context = runtime.__enter__()
        frame = FrameBuffer(4, 2, background=(8, 12, 20))
        frame.print(x=0, y=0, string="@OK", fg=(255, 255, 255))
        context.present(frame)

        assert runtime.engine is not None
        assert runtime.engine.window.get_size() == (1600, 960)
        assert runtime.engine.logical_surface.get_size() == (1600, 960)
        assert runtime.engine.viewport == pygame_engine.Viewport(0, 0, 1600, 960)
    finally:
        runtime.close()
        pygame.quit()


def test_ac_ii_landing_pad_reaches_real_logical_surface(_pygame_headless):
    pygame.init()
    tileset = engine.load_tileset()
    runtime = pygame_runtime.PygameRuntime(tileset)
    game_map = load_planet("ac_planet_2")
    hangar_ship = world.Entity(
        "t", (180, 200, 220), world.Position(7, 14), owned=True,
    )
    game_map.entities.append(hangar_ship)
    frame = FrameBuffer(100, 60)
    world.render_world(
        frame,
        game_map,
        region_x=0,
        region_y=0,
        region_w=80,
        region_h=54,
    )
    pad = game_map.tiles[hangar_ship.pos.y][hangar_ship.pos.x]
    screen_x = (20 + hangar_ship.pos.x) * 16
    screen_y = (15 + hangar_ship.pos.y) * 16
    pad_x = (20 + 4) * 16
    pad_y = (15 + 11) * 16

    try:
        runtime.__enter__()
        runtime.present(frame)
        surface = runtime.engine.logical_surface

        assert pad.kind == "landing_pad"
        assert pad.char == "▓"
        assert surface.get_at((screen_x, screen_y))[:3] == (178, 198, 215)
        assert all(
            surface.get_at((screen_x + x, screen_y + y))[:3] != (0, 0, 0)
            for x in range(16)
            for y in range(16)
        )
        assert surface.get_at((pad_x, pad_y))[:3] == pad.bg
        assert all(
            surface.get_at((pad_x + x, pad_y + y))[:3] != (0, 0, 0)
            for x in range(16)
            for y in range(16)
        )
    finally:
        runtime.close()
        pygame.quit()


def test_real_pygame_event_translates_into_project_input(_pygame_headless):
    pygame.init()
    try:
        event = pygame.event.Event(
            pygame.KEYDOWN,
            {"key": pygame.K_RETURN, "mod": pygame.KMOD_SHIFT, "repeat": False, "unicode": ""},
        )

        translated = pygame_engine.translate_event(pygame, event)

        assert translated == pygame_engine.PygameInputEvent(
            kind="keydown",
            key_name="enter",
            modifiers=pygame.KMOD_SHIFT,
            shift=True,
            repeat=False,
        )
    finally:
        pygame.quit()
