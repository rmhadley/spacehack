"""Headless integration coverage for the real Pygame runtime."""

from __future__ import annotations

import pygame
import pytest

from src.spacehack import engine, pygame_engine, pygame_runtime
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
        assert tileset[ord("#")] .get_size() == (16, 16)
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
