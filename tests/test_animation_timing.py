from tests.support.asyncutil import run
"""Tests for the user-selectable animation speed scale.

Covers the pure ``scaled`` helper (a SPEED multiplier: delays divide by
it, 0.0 is instant), the instant-speed SDL pump guarantee (a zero-length
sleep still drains the event queue), and the instant-speed cancellability
guarantee (the cancel-poll windows must still see a queued keydown on
their first poll).
"""

import time
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


def test_set_speed_scale_divides_delays():
    animation_timing.set_speed_scale(2.0)

    assert animation_timing.speed_scale() == 2.0
    assert animation_timing.scaled(0.05) == pytest.approx(0.025)
    animation_timing.set_speed_scale(4.0)
    assert animation_timing.scaled(0.05) == pytest.approx(0.0125)


def test_set_speed_scale_clamps_negative_values_to_instant():
    animation_timing.set_speed_scale(-3.0)

    assert animation_timing.speed_scale() == 0.0
    assert animation_timing.scaled(0.05) == 0.0


def test_responsive_sleeps_pump_sdl_and_return_promptly_at_instant(monkeypatch):
    import pygame
    from src.spacehack.combat._animations import _responsive_sleep as combat_sleep
    from src.spacehack.navigation_travel import _responsive_sleep as nav_sleep

    pumped = []
    monkeypatch.setattr(pygame.event, "get", lambda *a, **k: pumped.append(1) or ())
    animation_timing.set_speed_scale(0.0)

    started = time.monotonic()
    run(nav_sleep(0.05))
    run(combat_sleep(0.05))
    elapsed = time.monotonic() - started

    assert len(pumped) == 2  # one drain per sleep, zero delay
    assert elapsed < 0.05


def test_descent_pacing_constant_keeps_the_authored_value():
    assert animation_timing.DESCENT == 0.075


def test_goto_poll_cancel_sees_queued_keydown_at_instant_speed():
    animation_timing.set_speed_scale(0.0)
    key = SimpleNamespace(kind="keydown", key_name="h")
    context = SimpleNamespace(events=lambda: (key,))

    assert run(_goto_poll_cancel(context, animation_timing.AUTO_NAV)) is True


def test_goto_poll_cancel_returns_promptly_when_idle_at_instant_speed():
    animation_timing.set_speed_scale(0.0)
    context = SimpleNamespace(events=lambda: ())

    assert run(_goto_poll_cancel(context, animation_timing.AUTO_NAV)) is False


def test_explore_cancel_window_sees_queued_keydown_at_instant_speed():
    animation_timing.set_speed_scale(0.0)
    key = SimpleNamespace(kind="keydown", key_name="o")
    ctx = SimpleNamespace(context=SimpleNamespace(events=lambda: (key,)))

    assert _poll_cancel_window(ctx) is True


def test_explore_cancel_window_returns_promptly_when_idle_at_instant_speed():
    animation_timing.set_speed_scale(0.0)
    ctx = SimpleNamespace(context=SimpleNamespace(events=lambda: ()))

    assert _poll_cancel_window(ctx) is False


def test_web_beacon_prints_only_on_emscripten(capsys, monkeypatch):
    monkeypatch.setattr(animation_timing.sys, "platform", "linux")
    animation_timing.web_beacon("b46:quiet")
    assert capsys.readouterr().out == ""

    monkeypatch.setattr(animation_timing.sys, "platform", "emscripten")
    animation_timing.web_beacon("b46:mark")
    assert capsys.readouterr().out == "b46:mark\n"


def test_goto_transit_beacons_and_interrupt_passthrough(capsys, monkeypatch):
    from src.spacehack import navigation_travel as nt

    monkeypatch.setattr(animation_timing.sys, "platform", "emscripten")

    async def fake_step(ctx, console, player_entity, sx, sy):
        return ("interrupted", None) if sy == 2 else None

    monkeypatch.setattr(nt, "_goto_step", fake_step)
    result = run(nt._goto_transit(None, None, None, [(0, 1), (0, 2), (0, 3)]))
    out = capsys.readouterr().out

    assert result == ("interrupted", None)
    assert "b46:goto-start steps=3" in out
    assert "b46:goto-end frames=2" in out  # the interrupting frame is counted
