"""Renderer-neutral tests for the PygameRuntime preference facade.

The engine derives its ``display_config`` from the live window only, so
these tests pin the stitching that keeps ``animation_speed`` round-tripping
through Apply and re-reading — plus the animation_timing sync.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.spacehack import animation_timing, pygame_runtime
from src.spacehack.display_config import DisplayConfig


@pytest.fixture(autouse=True)
def _restore_speed_scale():
    yield
    animation_timing.set_speed_scale(1.0)


def _runtime_with_fake_engine(config: DisplayConfig) -> pygame_runtime.PygameRuntime:
    runtime = pygame_runtime.PygameRuntime(tileset=None, display_config=config)
    runtime.engine = SimpleNamespace(
        display_config=config.normalized(),
        apply_display_config=lambda _config: None,
    )
    return runtime


def test_display_config_property_stitches_animation_speed_onto_engine_state():
    runtime = _runtime_with_fake_engine(DisplayConfig(animation_speed=2.0))
    runtime.engine.display_config = DisplayConfig(fullscreen=True)

    assert runtime.display_config.fullscreen is True
    assert runtime.display_config.animation_speed == 2.0


def test_apply_display_config_keeps_animation_speed_and_syncs_timing():
    runtime = _runtime_with_fake_engine(DisplayConfig())

    runtime.apply_display_config(DisplayConfig(animation_speed=4.0))

    assert runtime.display_config.animation_speed == 4.0
    assert animation_timing.speed_scale() == 4.0
