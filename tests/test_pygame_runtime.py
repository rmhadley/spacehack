"""Renderer-neutral tests for the PygameRuntime facade.

The engine derives its ``display_config`` from the live window only, so
these tests pin the stitching that keeps ``animation_speed`` round-tripping
through Apply and re-reading — plus the animation_timing sync — and the
``wait_events`` backlog contract: one event per call, with a released
key's queued repeat keydowns dropped at its keyup.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.spacehack import animation_timing, pygame_runtime
from src.spacehack.display_config import DisplayConfig
from tests.support.asyncutil import run


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


_KEY_NAMES = {40: "j", 41: "k"}


def _raw_event(kind: str, key: int, repeat: bool = False):
    return SimpleNamespace(
        type={"down": 2, "up": 3}[kind], key=key, mod=0, text="", repeat=repeat,
    )


def _input_runtime(batches: list[list[SimpleNamespace]]):
    """A PygameRuntime whose fake SDL queue serves one batch per poll."""
    fake_pygame = SimpleNamespace(
        QUIT=1, KEYDOWN=2, KEYUP=3,
        MOUSEMOTION=4, MOUSEBUTTONDOWN=5, MOUSEBUTTONUP=6,
        KMOD_SHIFT=3,
        key=SimpleNamespace(name=_KEY_NAMES.get),
        event=SimpleNamespace(get=lambda: batches.pop(0) if batches else []),
    )
    runtime = pygame_runtime.PygameRuntime(tileset=None, display_config=DisplayConfig())
    runtime.engine = SimpleNamespace(pygame=fake_pygame)
    return runtime


def test_released_key_drops_queued_repeat_keydowns():
    batches = [
        [_raw_event("down", 40)],
        [_raw_event("down", 40, repeat=True), _raw_event("down", 40, repeat=True)],
        [_raw_event("down", 40, repeat=True), _raw_event("up", 40)],
    ]
    runtime = _input_runtime(batches)

    delivered = [run(runtime.wait_events())[0] for _ in range(3)]

    assert [(e.kind, e.repeat) for e in delivered] == [
        ("keydown", False), ("keydown", True), ("keyup", False),
    ]
    assert runtime._event_backlog == []


def test_release_purge_keeps_other_keys_repeats():
    batches = [
        [_raw_event("down", 40), _raw_event("down", 41)],
        [_raw_event("down", 41, repeat=True), _raw_event("up", 40)],
    ]
    runtime = _input_runtime(batches)

    run(runtime.wait_events())
    run(runtime.wait_events())
    final = run(runtime.wait_events())[0]

    assert final.kind == "keydown"
    assert final.key_name == "k"
    assert final.repeat is True
    assert [e.kind for e in runtime._event_backlog] == ["keyup"]


def test_same_batch_tap_still_delivers_its_press():
    runtime = _input_runtime([[_raw_event("down", 40), _raw_event("up", 40)]])

    delivered = run(runtime.wait_events())[0]

    assert (delivered.kind, delivered.repeat) == ("keydown", False)
    assert [e.kind for e in runtime._event_backlog] == ["keyup"]


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
