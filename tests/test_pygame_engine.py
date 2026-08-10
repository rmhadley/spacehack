"""Tests for the Pygame-owned engine foundation."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import pygame_engine


def test_default_config_matches_the_existing_logical_grid():
    config = pygame_engine.PygameEngineConfig()

    assert pygame_engine.logical_size(config) == (1600, 960)
    assert (config.window_width, config.window_height) == (1600, 960)


def test_fit_viewport_preserves_aspect_ratio_and_centers_letterbox():
    assert pygame_engine.fit_viewport(1920, 1080, 1600, 960) == pygame_engine.Viewport(
        60, 0, 1800, 1080,
    )
    assert pygame_engine.fit_viewport(1000, 1000, 1600, 960) == pygame_engine.Viewport(
        0, 200, 1000, 600,
    )


def test_fit_viewport_handles_invalid_dimensions_without_division_errors():
    assert pygame_engine.fit_viewport(0, 800, 1600, 960) == pygame_engine.Viewport(
        0, 0, 1, 1,
    )


def test_logical_position_rejects_letterbox_and_maps_inside_viewport():
    viewport = pygame_engine.Viewport(60, 0, 1800, 1080)

    assert pygame_engine.logical_position((20, 100), viewport, 1600, 960) is None
    assert pygame_engine.logical_position((60, 0), viewport, 1600, 960) == (0, 0)
    assert pygame_engine.logical_position((960, 540), viewport, 1600, 960) == (800, 480)


def test_key_normalization_preserves_game_friendly_names():
    assert pygame_engine.normalize_key_name("Return") == "enter"
    assert pygame_engine.normalize_key_name("KP 8") == "kp_8"
    assert pygame_engine.normalize_key_name("J") == "j"
    assert pygame_engine.normalize_key_name("unknown") == "unknown"


def test_pygame_event_translation_is_renderer_neutral():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        KEYUP = 3
        MOUSEMOTION = 4
        MOUSEBUTTONDOWN = 5
        MOUSEBUTTONUP = 6
        key = SimpleNamespace(name=lambda key: {10: "Return"}[key])

    event = SimpleNamespace(type=FakePygame.KEYDOWN, key=10, mod=4, text="")

    translated = pygame_engine._event_from_pygame(FakePygame, event)

    assert translated.kind == "keydown"
    assert translated.key_name == "enter"
    assert translated.modifiers == 4
    assert translated.raw is event
