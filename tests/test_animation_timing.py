"""Tests for the user-selectable animation speed scale.

Covers the pure ``scaled`` helper and the instant-speed cancellability
guarantee: at a zero scale the cancel-poll windows must still see a
queued keydown on their first poll (a zero-length window that never
polled would make auto-explore and auto-nav uncancellable).
"""

from types import SimpleNamespace

import pytest

from src.spacehack import animation_timing
from src.spacehack.autoexplore import _poll_cancel_window
from src.spacehack.navigation_travel import _goto_poll_cancel


@pytest.fixture(autouse=True)
def _restore_speed_scale():
    yield
    animation_timing.set_speed_scale(1.0)


def test_scaled_returns_authored_delay_by_default():
    assert animation_timing.speed_scale() == 1.0
    assert animation_timing.scaled(animation_timing.CITY_TRANSITION) == animation_timing.CITY_TRANSITION


def test_set_speed_scale_multiplies_delays():
    animation_timing.set_speed_scale(2.0)

    assert animation_timing.speed_scale() == 2.0
    assert animation_timing.scaled(0.05) == pytest.approx(0.1)


def test_set_speed_scale_clamps_negative_values_to_instant():
    animation_timing.set_speed_scale(-3.0)

    assert animation_timing.speed_scale() == 0.0
    assert animation_timing.scaled(0.05) == 0.0


def test_descent_pacing_constant_keeps_the_authored_value():
    assert animation_timing.DESCENT == 0.075


def test_goto_poll_cancel_sees_queued_keydown_at_instant_speed():
    animation_timing.set_speed_scale(0.0)
    key = SimpleNamespace(kind="keydown", key_name="h")
    context = SimpleNamespace(events=lambda: (key,))

    assert _goto_poll_cancel(context, animation_timing.AUTO_NAV) is True


def test_goto_poll_cancel_returns_promptly_when_idle_at_instant_speed():
    animation_timing.set_speed_scale(0.0)
    context = SimpleNamespace(events=lambda: ())

    assert _goto_poll_cancel(context, animation_timing.AUTO_NAV) is False


def test_explore_cancel_window_sees_queued_keydown_at_instant_speed():
    animation_timing.set_speed_scale(0.0)
    key = SimpleNamespace(kind="keydown", key_name="o")
    ctx = SimpleNamespace(context=SimpleNamespace(events=lambda: (key,)))

    assert _poll_cancel_window(ctx) is True


def test_explore_cancel_window_returns_promptly_when_idle_at_instant_speed():
    animation_timing.set_speed_scale(0.0)
    ctx = SimpleNamespace(context=SimpleNamespace(events=lambda: ()))

    assert _poll_cancel_window(ctx) is False
