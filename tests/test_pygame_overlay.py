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


def test_overlay_segments_carry_background_and_split_runs_on_bg_change():
    # Mirrors the combat HUD shield line: the regen-rate cells share the
    # bar's foreground but paint a white background, so they must become
    # their own segment instead of merging into the unpainted run.
    commands = (
        world.WorldDrawCommand(5, 1, "#", (1, 2, 3), None),
        world.WorldDrawCommand(6, 1, "#", (1, 2, 3), (255, 255, 255)),
        world.WorldDrawCommand(7, 1, ".", (1, 2, 3), (255, 255, 255)),
        world.WorldDrawCommand(8, 1, ".", (1, 2, 3), None),
    )

    assert pygame_overlay._segments(
        commands, x_min=0, x_max=10, y_min=0, y_max=3,
    ) == (
        pygame_overlay.OverlaySegment(5, 1, "#", (1, 2, 3)),
        pygame_overlay.OverlaySegment(6, 1, "#.", (1, 2, 3), (255, 255, 255)),
        pygame_overlay.OverlaySegment(8, 1, ".", (1, 2, 3)),
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


def test_overlay_payload_round_trips_segments_and_layout():
    frame = pygame_overlay.OverlayFrame(
        hud=(pygame_overlay.OverlaySegment(80, 0, "HUD", (1, 2, 3)),),
        messages=(
            pygame_overlay.OverlaySegment(0, 54, "msg", (4, 5, 6), (255, 255, 255)),
        ),
        hud_x=80,
        hud_top=0,
        hud_height=54,
        message_top=54,
        message_height=6,
    )

    payload = pygame_overlay.payload(frame)

    assert payload["hud"][0] == {
        "x": 80, "y": 0, "text": "HUD", "color": (1, 2, 3), "bg": None,
    }
    assert payload["messages"][0]["text"] == "msg"
    assert payload["messages"][0]["bg"] == (255, 255, 255)
    assert payload["hud_height"] == 54
    restored = pygame_overlay.frame_from_payload(payload)
    assert restored == frame


def test_draw_segments_offsets_text_inside_panel_padding(monkeypatch):
    drawn = []

    class FakeScreen:
        def set_clip(self, _clip):
            pass

    class FakePygame:
        class Rect:
            def __init__(self, *args):
                self.args = args

    class FakeFont:
        def size(self, text):
            return (len(text) * 8, 12)

        def get_linesize(self):
            return 12

    monkeypatch.setattr(
        pygame_overlay.pygame_ui,
        "draw_text",
        lambda _pygame, _screen, _font, text, x, y, **_kwargs: drawn.append((text, x, y)),
    )

    pygame_overlay._draw_segments(
        FakePygame,
        FakeScreen(),
        FakeFont(),
        (pygame_overlay.OverlaySegment(80, 2, "HUD", (1, 2, 3)),),
        origin_x=1280,
        origin_y=0,
        width=320,
        height=864,
        origin_cell_x=80,
        origin_cell_y=0,
    )

    assert drawn == [("HUD", 1292, 36)]


def test_draw_segments_paints_background_highlight_before_text(monkeypatch):
    drawn = []
    filled = []

    class FakeScreen:
        def set_clip(self, _clip):
            pass

    class FakePygame:
        class Rect:
            def __init__(self, *args):
                self.args = args

        class draw:
            @staticmethod
            def rect(_screen, color, rect):
                filled.append((color, rect))

    class FakeFont:
        def size(self, text):
            return (len(text) * 8, 12)

        def get_linesize(self):
            return 12

    monkeypatch.setattr(
        pygame_overlay.pygame_ui,
        "draw_text",
        lambda _pygame, _screen, _font, text, x, y, **_kwargs: drawn.append((text, x, y)),
    )

    pygame_overlay._draw_segments(
        FakePygame,
        FakeScreen(),
        FakeFont(),
        (pygame_overlay.OverlaySegment(80, 2, "##", (1, 2, 3), (255, 255, 255)),),
        origin_x=1280,
        origin_y=0,
        width=320,
        height=864,
        origin_cell_x=80,
        origin_cell_y=0,
    )

    assert len(filled) == 1
    fill_color, fill_rect = filled[0]
    assert fill_color == (255, 255, 255)
    assert fill_rect.args == (1292, 36, 32, 16)
    assert drawn == [("##", 1292, 36)]


def test_present_exploration_uses_shared_overlay_and_tcod_fallback(monkeypatch):
    frame = object()
    shared_calls = []
    shared_ctx = SimpleNamespace(
        log=object(),
        context=SimpleNamespace(
            _runtime=object(),
            present=lambda console, **kwargs: shared_calls.append((console, kwargs)),
        ),
    )
    monkeypatch.setattr(pygame_overlay, "capture", lambda *_args, **_kwargs: frame)

    assert pygame_overlay.present_exploration(
        shared_ctx,
        "console",
        mode="city",
        location="Earth",
        screen_width=100,
        screen_height=60,
        hud_view_height=54,
    ) is True
    assert shared_calls == [("console", {"overlay": frame})]

    fallback_calls = []
    fallback_ctx = SimpleNamespace(
        log=object(),
        context=SimpleNamespace(
            present=lambda console: fallback_calls.append(("present", console)),
        ),
    )
    from src.spacehack import hud, message_log
    monkeypatch.setattr(hud, "render_hud", lambda *args, **kwargs: fallback_calls.append(("hud", args[0])))
    monkeypatch.setattr(message_log, "render_message_log", lambda *args, **kwargs: fallback_calls.append(("log", args[0])))

    assert pygame_overlay.present_exploration(
        fallback_ctx,
        "console",
        mode="city",
        location="Earth",
        screen_width=100,
        screen_height=60,
        hud_view_height=54,
    ) is False
    assert fallback_calls == [("hud", "console"), ("log", "console"), ("present", "console")]


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
