"""Tests for the native Pygame HUD/message-log overlay bridge."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import pygame_overlay, pygame_runtime, world


def test_overlay_segments_group_adjacent_cells_by_color_and_split_gaps():
    commands = (
        world.WorldDrawCommand(2, 1, "A", (1, 2, 3), None),
        world.WorldDrawCommand(3, 1, "B", (1, 2, 3), None),
        world.WorldDrawCommand(5, 1, "C", (1, 2, 3), None),
        world.WorldDrawCommand(6, 1, "D", (4, 5, 6), None),
    )

    assert pygame_overlay._segments(
        commands, x_min=0, x_max=10, y_min=0, y_max=3,
    ) == (
        pygame_overlay.OverlaySegment(2, 1, "AB", (1, 2, 3)),
        pygame_overlay.OverlaySegment(5, 1, "C", (1, 2, 3)),
        pygame_overlay.OverlaySegment(6, 1, "D", (4, 5, 6)),
    )


def test_overlay_capture_keeps_hud_and_log_regions_separate(monkeypatch):
    from src.spacehack import hud, message_log

    def fake_hud(console, _ctx, **_kwargs):
        console.print(x=80, y=2, string="HUD", fg=(10, 20, 30))
        console.print(x=1, y=2, string="not hud", fg=(99, 99, 99))

    def fake_log(console, _log, **_kwargs):
        console.print(x=0, y=54, string="old", fg=(40, 50, 60))
        console.print(x=0, y=55, string="> event", fg=(70, 80, 90))

    monkeypatch.setattr(hud, "render_hud", fake_hud)
    monkeypatch.setattr(message_log, "render_message_log", fake_log)

    frame = pygame_overlay.capture(
        SimpleNamespace(log=object()),
        mode="city",
        location="Earth",
        screen_width=100,
        screen_height=60,
        hud_view_height=54,
    )

    assert frame.hud == (
        pygame_overlay.OverlaySegment(80, 2, "HUD", (10, 20, 30)),
    )
    assert frame.messages == (
        pygame_overlay.OverlaySegment(0, 54, "old", (40, 50, 60)),
        pygame_overlay.OverlaySegment(0, 55, "> event", (70, 80, 90)),
    )
    assert frame.hud_x == 80
    assert frame.message_top == 54
    assert frame.message_height == 6


def test_overlay_payload_preserves_segments_and_layout():
    frame = pygame_overlay.OverlayFrame(
        hud=(pygame_overlay.OverlaySegment(80, 0, "HUD", (1, 2, 3)),),
        messages=(pygame_overlay.OverlaySegment(0, 54, "msg", (4, 5, 6)),),
        hud_x=80,
        hud_top=0,
        hud_height=54,
        message_top=54,
        message_height=6,
    )

    payload = pygame_overlay.payload(frame)

    assert payload["hud"][0] == {
        "x": 80, "y": 0, "text": "HUD", "color": (1, 2, 3),
    }
    assert payload["messages"][0]["text"] == "msg"
    assert payload["hud_height"] == 54


def test_shared_context_preserves_legacy_present_call_without_overlay():
    calls = []
    runtime = SimpleNamespace(
        present=lambda console, **kwargs: calls.append((console, kwargs)),
    )
    context = pygame_runtime.PygameContext(runtime)
    console = object()

    context.present(console)

    assert calls == [(console, {})]


def test_shared_context_forwards_optional_overlay_to_runtime():
    calls = []
    runtime = SimpleNamespace(
        present=lambda console, **kwargs: calls.append((console, kwargs)),
    )
    context = pygame_runtime.PygameContext(runtime)
    overlay = object()
    console = object()

    context.present(console, overlay=overlay)

    assert calls == [(console, {"overlay": overlay})]
