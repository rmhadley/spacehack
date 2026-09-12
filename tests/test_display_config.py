"""Tests for persistent fullscreen, window, and animation preferences."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.spacehack.display_config import (
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    DisplayConfig,
    load_display_config,
    parse_display_config,
    save_display_config,
    serialize_display_config,
)


def test_default_display_config_uses_the_logical_window_size():
    config = DisplayConfig()

    assert config.fullscreen is False
    assert (config.window_width, config.window_height) == (
        DEFAULT_WINDOW_WIDTH,
        DEFAULT_WINDOW_HEIGHT,
    )


def test_display_config_round_trips_the_owned_toml_shape():
    config = DisplayConfig(fullscreen=True, window_width=1280, window_height=768)

    assert parse_display_config(serialize_display_config(config)) == config


def test_display_config_ignores_unknown_sections_and_keys():
    contents = """
    [other]
    value = 42

    [display]
    fullscreen = true
    window_width = 1920
    window_height = 1152
    future_option = true
    """

    assert parse_display_config(contents) == DisplayConfig(
        fullscreen=True,
        window_width=1920,
        window_height=1152,
    )


def test_display_config_normalizes_unsafe_window_dimensions():
    assert DisplayConfig(window_width=1, window_height=1).normalized() == DisplayConfig(
        window_width=800,
        window_height=480,
    )


def test_load_display_config_falls_back_for_missing_or_malformed_files(tmp_path: Path):
    missing = tmp_path / "missing.toml"
    malformed = tmp_path / "malformed.toml"
    malformed.write_text("[display]\nfullscreen = maybe\n", encoding="utf-8")

    assert load_display_config(missing) == DisplayConfig()
    assert load_display_config(malformed) == DisplayConfig()


def test_save_display_config_creates_parent_and_persists_preferences(tmp_path: Path):
    path = tmp_path / "nested" / "config.toml"
    config = DisplayConfig(fullscreen=True, window_width=1280, window_height=768)

    save_display_config(config, path)

    assert path.exists()
    assert load_display_config(path) == config


def test_animation_speed_round_trips_every_supported_value(tmp_path: Path):
    path = tmp_path / "config.toml"
    for speed in (1.0, 2.0, 4.0, 0.0, 3.0):
        save_display_config(DisplayConfig(animation_speed=speed), path)

        assert load_display_config(path) == DisplayConfig(animation_speed=speed)


def test_animation_speed_defaults_to_normal_when_key_absent():
    contents = "[display]\nfullscreen = false\n"

    assert parse_display_config(contents).animation_speed == 1.0


def test_animation_speed_malformed_value_falls_back_to_defaults(tmp_path: Path):
    malformed = tmp_path / "malformed.toml"
    malformed.write_text("[display]\nanimation_speed = brisk\n", encoding="utf-8")

    with pytest.raises(ValueError):
        parse_display_config(malformed.read_text(encoding="utf-8"))
    assert load_display_config(malformed) == DisplayConfig()


def test_animation_speed_rejects_non_finite_values(tmp_path: Path):
    non_finite = tmp_path / "nonfinite.toml"
    non_finite.write_text("[display]\nanimation_speed = nan\n", encoding="utf-8")

    with pytest.raises(ValueError):
        parse_display_config(non_finite.read_text(encoding="utf-8"))
    assert load_display_config(non_finite) == DisplayConfig()


def test_animation_speed_normalizes_only_at_the_bounds():
    assert DisplayConfig(animation_speed=9.0).normalized().animation_speed == 4.0
    assert DisplayConfig(animation_speed=-1.0).normalized().animation_speed == 0.0
    assert DisplayConfig(animation_speed=3.0).normalized().animation_speed == 3.0
