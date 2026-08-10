"""Tests for the Pygame-owned engine foundation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.spacehack import pygame_engine, pygame_runtime


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


def test_shared_runtime_maps_pygame_keys_to_tcod_keysyms():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        KEYUP = 3
        key = SimpleNamespace(name=lambda key: {10: "Return", 11: "j"}[key])

    enter = pygame_runtime._tcod_event_from_pygame(
        FakePygame,
        SimpleNamespace(type=FakePygame.KEYDOWN, key=10, mod=0, unicode=""),
    )
    move = pygame_runtime._tcod_event_from_pygame(
        FakePygame,
        SimpleNamespace(type=FakePygame.KEYDOWN, key=11, mod=0, unicode="j"),
    )

    assert enter.sym.name == "RETURN"
    assert move.sym.name == "J"
    assert isinstance(
        pygame_runtime._tcod_event_from_pygame(
            FakePygame, SimpleNamespace(type=FakePygame.QUIT),
        ),
        __import__("tcod.event", fromlist=["Quit"]).Quit,
    )


def test_shared_runtime_context_is_renderer_compatible():
    runtime = SimpleNamespace(present=lambda console: None)
    context = pygame_runtime.PygameContext(runtime)
    marker = object()

    assert context.convert_event(marker) is marker
    assert context.present(marker) is None


def test_pygame_engine_uses_injected_tileset(monkeypatch):
    calls = []

    class FakeSurface:
        def __init__(self, *_args):
            pass

        def fill(self, *_args):
            pass

    class FakeFont:
        def init(self):
            pass

    class FakeDisplay:
        def set_mode(self, *_args, **_kwargs):
            return SimpleNamespace()

        def set_caption(self, *_args):
            pass

        def quit(self):
            pass

    class FakePygame:
        RESIZABLE = 1
        SRCALPHA = 2
        font = FakeFont()
        display = FakeDisplay()
        Surface = FakeSurface

        @staticmethod
        def init():
            pass

        @staticmethod
        def quit():
            pass

    class FakeAtlas:
        @classmethod
        def from_processed_tileset(cls, _pygame, tileset):
            calls.append(tileset)
            return object()

    monkeypatch.setattr(pygame_engine, "GlyphAtlas", FakeAtlas)
    supplied = object()
    engine = pygame_engine.PygameEngine(
        FakePygame,
        pygame_engine.PygameEngineConfig(vsync=False),
        tileset=supplied,
    )
    engine.open()

    assert calls == [supplied]


def test_game_runtime_prefers_shared_pygame_unless_tcod_rollback(monkeypatch):
    class FakePygameRuntime:
        def __init__(self, tileset):
            self.context = object()

        def __enter__(self):
            return self.context

        def __exit__(self, *_args):
            pass

    monkeypatch.delenv("SPACEHACK_TCOD_UI", raising=False)
    monkeypatch.setattr(pygame_runtime, "PygameRuntime", FakePygameRuntime)
    runtime = pygame_runtime.GameRuntime(object())

    assert runtime.__enter__() is runtime._pygame.context
    runtime.__exit__(None, None, None)

    monkeypatch.setenv("SPACEHACK_TCOD_UI", "1")
    sentinel = SimpleNamespace(__enter__=lambda self: self, __exit__=lambda *args: None)
    monkeypatch.setattr(
        "src.spacehack.engine.open_terminal",
        lambda _tileset: sentinel,
    )
    rollback = pygame_runtime.GameRuntime(object())

    assert rollback.__enter__() is sentinel
    rollback.__exit__(None, None, None)


def test_pygame_runtime_installs_and_restores_tcod_event_bridge(monkeypatch):
    original_wait = pygame_runtime.tcod.event.wait
    original_get = pygame_runtime.tcod.event.get

    class FakeEngine:
        pygame = SimpleNamespace()
        logical_surface = None
        glyphs = None

        def open(self):
            return self

        def close(self):
            pass

    monkeypatch.setattr(
        pygame_runtime.pygame_engine,
        "_load_pygame",
        lambda: object(),
    )
    monkeypatch.setattr(
        pygame_runtime.pygame_engine,
        "PygameEngine",
        lambda *args, **kwargs: FakeEngine(),
    )

    runtime = pygame_runtime.PygameRuntime(object())
    runtime.__enter__()
    assert pygame_runtime.tcod.event.wait != original_wait
    assert pygame_runtime.tcod.event.get != original_get

    runtime.close()

    assert pygame_runtime.tcod.event.wait is original_wait
    assert pygame_runtime.tcod.event.get is original_get


def test_real_pygame_runtime_opens_one_shared_engine_when_available(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame = pytest.importorskip("pygame")
    tileset = __import__("src.spacehack.engine", fromlist=["load_tileset"]).load_tileset()
    runtime = pygame_runtime.PygameRuntime(tileset)

    try:
        context = runtime.__enter__()
        assert context is runtime.context
        assert runtime.engine is not None
        assert runtime.engine.window is not None
        assert runtime.engine.glyphs is not None
    finally:
        runtime.close()
        pygame.quit()


def test_pygame_runtime_closes_partial_engine_after_open_failure(monkeypatch):
    closed = []

    class FakePygameEngine:
        def __init__(self, *args, **kwargs):
            pass

        def open(self):
            raise RuntimeError("broken")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(pygame_runtime.pygame_engine, "PygameEngine", FakePygameEngine)
    monkeypatch.setattr(pygame_runtime.pygame_engine, "_load_pygame", lambda: object())

    runtime = pygame_runtime.PygameRuntime(object())
    try:
        runtime.__enter__()
    except RuntimeError:
        pass
    else:
        raise AssertionError("broken engine must propagate during direct runtime setup")

    assert closed == [True]
