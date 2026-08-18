"""Tests for the Pygame-owned engine foundation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import get_type_hints

import pytest

from src.spacehack import game_context, pygame_engine, pygame_runtime, pygame_ui, saveload


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
        KMOD_SHIFT = 3
        key = SimpleNamespace(name=lambda key: {10: "Return"}[key])

    event = SimpleNamespace(
        type=FakePygame.KEYDOWN, key=10, mod=3, text="", repeat=True,
    )

    translated = pygame_engine.translate_event(FakePygame, event)

    assert translated.kind == "keydown"
    assert translated.key_name == "enter"
    assert translated.modifiers == 3
    assert translated.shift is True
    assert translated.repeat is True
    assert not hasattr(translated, "raw")


def test_project_input_predicates_cover_quit_escape_shift_and_guide():
    keydown = pygame_engine.PygameInputEvent(
        kind="keydown", key_name="slash", modifiers=3, shift=True, text="?",
    )
    escape = pygame_engine.PygameInputEvent(kind="keydown", key_name="escape")
    quit_event = pygame_engine.PygameInputEvent(kind="quit")
    keyup = pygame_engine.PygameInputEvent(kind="keyup", key_name="j")

    assert pygame_engine.is_keydown(keydown)
    assert pygame_engine.has_shift(keydown)
    assert pygame_engine.guide_key(keydown)
    assert pygame_engine.is_escape(escape)
    assert pygame_engine.is_quit(quit_event)
    assert pygame_engine.quit_or_escape(escape)
    assert pygame_engine.quit_or_escape(quit_event)
    assert not pygame_engine.quit_or_escape(keyup)


def test_translate_event_defaults_repeat_to_false():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        KEYUP = 3
        MOUSEMOTION = 4
        MOUSEBUTTONDOWN = 5
        MOUSEBUTTONUP = 6
        KMOD_SHIFT = 3
        key = SimpleNamespace(name=lambda _key: "j")

    event = SimpleNamespace(type=FakePygame.KEYDOWN, key=10, mod=0)

    assert pygame_engine.translate_event(FakePygame, event).repeat is False


def test_shared_runtime_exposes_explicit_project_event_polling(monkeypatch):
    events = (
        pygame_engine.PygameInputEvent(kind="keydown", key_name="j"),
    )

    class FakeEngine:
        pygame = SimpleNamespace()
        def events(self):
            return events

    runtime = pygame_runtime.PygameRuntime(object())
    runtime.engine = FakeEngine()

    assert runtime.events() == events
    assert runtime.context.events() == events


def test_shared_runtime_wait_events_skips_irrelevant_events_and_returns_one():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        KEYUP = 3
        MOUSEMOTION = 4
        MOUSEBUTTONDOWN = 5
        MOUSEBUTTONUP = 6
        KMOD_SHIFT = 3
        key = SimpleNamespace(name=lambda _key: "j")

    waits = iter((
        SimpleNamespace(type=99),
        SimpleNamespace(type=FakePygame.KEYDOWN, key=10, mod=0, repeat=False),
    ))
    fake_pygame = SimpleNamespace(
        QUIT=FakePygame.QUIT,
        KEYDOWN=FakePygame.KEYDOWN,
        KEYUP=FakePygame.KEYUP,
        MOUSEMOTION=FakePygame.MOUSEMOTION,
        MOUSEBUTTONDOWN=FakePygame.MOUSEBUTTONDOWN,
        MOUSEBUTTONUP=FakePygame.MOUSEBUTTONUP,
        KMOD_SHIFT=FakePygame.KMOD_SHIFT,
        key=FakePygame.key,
        event=SimpleNamespace(wait=lambda: next(waits)),
    )
    runtime = pygame_runtime.PygameRuntime(object())
    runtime.engine = SimpleNamespace(pygame=fake_pygame)

    assert runtime.wait_events() == (
        pygame_engine.PygameInputEvent(kind="keydown", key_name="j"),
    )


def test_shared_runtime_wait_events_is_empty_when_closed():
    runtime = pygame_runtime.PygameRuntime(object())

    assert runtime.wait_events() == ()


def test_shared_runtime_does_not_patch_third_party_event_queue():
    runtime = pygame_runtime.PygameRuntime(object())
    assert not hasattr(runtime, "_old_wait")
    assert not hasattr(runtime, "_old_get")


def test_phase4_uses_project_owned_context_contracts():
    assert get_type_hints(game_context.GameContext)["context"] is pygame_runtime.PygameContext
    assert get_type_hints(saveload.load_game)["context"] is pygame_runtime.PygameContext
    assert get_type_hints(pygame_ui._context_game_context)["context"] is pygame_runtime.PygameContext
    assert get_type_hints(pygame_ui._context_game_context)["return"] == game_context.GameContext | None
    assert "convert_event" not in pygame_runtime.PygameContext.__dict__


def test_shared_runtime_context_is_renderer_compatible():
    runtime = SimpleNamespace(present=lambda console: None)
    context = pygame_runtime.PygameContext(runtime)
    marker = object()

    assert context.present(marker) is None


def test_pygame_runtime_present_uses_framebuffer_default_background():
    from src.spacehack.framebuffer import FrameBuffer

    fills = []
    blits = []
    presents = []

    class FakeSurface:
        def fill(self, color):
            fills.append(color)

    class FakeGlyphs:
        tile_width = 16
        tile_height = 16

        def blit(self, *_args, **kwargs):
            blits.append(kwargs)

    fake_engine = SimpleNamespace(
        logical_surface=FakeSurface(),
        glyphs=FakeGlyphs(),
        pygame=SimpleNamespace(),
        config=pygame_engine.PygameEngineConfig(),
        clear=lambda color: fills.append((*color, 255)),
        present=lambda: presents.append(True),
    )
    runtime = pygame_runtime.PygameRuntime(object())
    runtime.engine = fake_engine
    frame = FrameBuffer(2, 1, background=(7, 8, 9))
    frame.print(string="A")

    runtime.present(frame)

    assert fills == [(7, 8, 9, 255)]
    assert blits[0]["bg"] is None
    assert presents == [True]


def test_pygame_engine_uses_injected_tileset(monkeypatch):
    calls = []
    repeat_calls = []

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

    class FakeKey:
        @staticmethod
        def set_repeat(*args):
            repeat_calls.append(args)

    class FakePygame:
        RESIZABLE = 1
        SRCALPHA = 2
        font = FakeFont()
        key = FakeKey()
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
    assert repeat_calls == [(400, 55)]

    engine.close()
    assert repeat_calls[-1] == (0,)


def test_engine_applies_fullscreen_without_rebuilding_logical_surface(monkeypatch):
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
        def set_mode(self, size, flags, **_kwargs):
            calls.append((size, flags))
            return SimpleNamespace(get_size=lambda: size)

        def set_caption(self, *_args):
            pass

        def quit(self):
            pass

    class FakeKey:
        @staticmethod
        def set_repeat(*_args):
            pass

    class FakePygame:
        RESIZABLE = 1
        FULLSCREEN = 2
        SRCALPHA = 4
        font = FakeFont()
        key = FakeKey()
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
        def from_processed_tileset(cls, _pygame, _tileset):
            return object()

    monkeypatch.setattr(pygame_engine, "GlyphAtlas", FakeAtlas)
    engine = pygame_engine.PygameEngine(
        FakePygame,
        pygame_engine.PygameEngineConfig(vsync=False),
        tileset=object(),
    )
    engine.open()
    logical_surface = engine.logical_surface

    engine.apply_display_config(
        pygame_engine.DisplayConfig(fullscreen=True, window_width=1280, window_height=768),
    )

    assert calls == [((1600, 960), 1), ((0, 0), 2)]
    assert engine.config.fullscreen is True
    assert engine.logical_surface is logical_surface


def test_game_runtime_always_uses_shared_pygame(monkeypatch):
    class FakePygameRuntime:
        def __init__(self, tileset):
            self.context = object()

        def __enter__(self):
            return self.context

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(pygame_runtime, "PygameRuntime", FakePygameRuntime)
    runtime = pygame_runtime.GameRuntime(object())

    assert runtime.__enter__() is runtime._pygame.context
    runtime.__exit__(None, None, None)


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
