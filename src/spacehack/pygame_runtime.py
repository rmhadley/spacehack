"""Shared Pygame-owned runtime for the complete game flow.

The game uses project-owned framebuffers during the Phase 2 migration.
Input is fully project-owned in this phase: the runtime
polls Pygame and returns :class:`pygame_engine.PygameInputEvent` values without
patching a foreign event queue.
"""
from __future__ import annotations

from typing import Any

from . import pygame_engine
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_HEIGHT, TILE_WIDTH
from .framebuffer import FrameBuffer


def is_shared_context(context: Any) -> bool:
    """Return whether ``context`` belongs to the active shared runtime."""
    runtime = getattr(context, "_runtime", None)
    return getattr(runtime, "engine", None) is not None


class PygameContext:
    """Project-owned presentation context backed by the shared Pygame runtime."""

    def __init__(self, runtime: "PygameRuntime"):
        self._runtime = runtime

    def present(self, console: FrameBuffer, *, overlay: Any | None = None) -> None:
        """Paint one console and optional native text overlay into Pygame."""
        if overlay is None:
            self._runtime.present(console)
        else:
            self._runtime.present(console, overlay=overlay)

    def events(self) -> tuple[pygame_engine.PygameInputEvent, ...]:
        """Poll all currently queued project-owned input events."""
        return self._runtime.events()

    def wait_events(self) -> tuple[pygame_engine.PygameInputEvent, ...]:
        """Block until the next relevant input event is available."""
        return self._runtime.wait_events()

    def convert_event(self, event: Any) -> Any:
        """Retain the old adapter method for non-input compatibility callers."""
        return event


class PygameRuntime:
    """Own one Pygame engine and its explicit input queue."""

    def __init__(self, tileset: Any):
        self.tileset = tileset
        self.engine: pygame_engine.PygameEngine | None = None
        self.game_context: Any | None = None
        self.context = PygameContext(self)

    def __enter__(self) -> PygameContext:
        """Open the shared window without modifying global event functions."""
        pygame = pygame_engine._load_pygame()
        try:
            self.engine = pygame_engine.PygameEngine(
                pygame,
                pygame_engine.PygameEngineConfig(
                    logical_width=SCREEN_WIDTH * TILE_WIDTH,
                    logical_height=SCREEN_HEIGHT * TILE_HEIGHT,
                    window_width=SCREEN_WIDTH * TILE_WIDTH,
                    window_height=SCREEN_HEIGHT * TILE_HEIGHT,
                ),
                tileset=self.tileset,
            )
            self.engine.open()
        except Exception:
            self.close()
            raise
        return self.context

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Close the shared window."""
        self.close()

    def events(self) -> tuple[pygame_engine.PygameInputEvent, ...]:
        """Poll Pygame once and return project-owned input events."""
        if self.engine is None:
            return ()
        return self.engine.events()

    def wait_events(self) -> tuple[pygame_engine.PygameInputEvent, ...]:
        """Block until one relevant event, preserving the old tuple contract."""
        if self.engine is None:
            return ()
        pygame = self.engine.pygame
        while True:
            event = pygame.event.wait()
            translated = pygame_engine.translate_event(pygame, event)
            if translated.kind != "other":
                return (translated,)

    def present(self, console: FrameBuffer, *, overlay: Any | None = None) -> None:
        """Render a console, then an optional native Pygame overlay."""
        if self.engine is None or self.engine.logical_surface is None or self.engine.glyphs is None:
            raise RuntimeError("Pygame runtime is not open")
        self.engine.clear(console.default_background() or (0, 0, 0))
        for command in console.to_commands():
            self.engine.glyphs.blit(
                self.engine.logical_surface,
                command.char,
                int(command.x) * self.engine.glyphs.tile_width,
                int(command.y) * self.engine.glyphs.tile_height,
                fg=tuple(command.fg),
                bg=None if command.bg is None else tuple(command.bg),
            )
        if overlay is not None:
            from . import pygame_overlay
            pygame_overlay.draw(
                self.engine.pygame,
                self.engine.logical_surface,
                overlay,
                logical_width=self.engine.config.logical_width,
                logical_height=self.engine.config.logical_height,
            )
        self.engine.present()

    def close(self) -> None:
        """Release Pygame resources idempotently."""
        if self.engine is not None:
            self.engine.close()
            self.engine = None


class GameRuntime:
    """Own the mandatory shared Pygame runtime for the complete game."""

    def __init__(self, tileset: Any):
        self.tileset = tileset
        self._pygame: PygameRuntime | None = None

    def __enter__(self) -> Any:
        """Open the mandatory Pygame runtime."""
        self._pygame = PygameRuntime(self.tileset)
        return self._pygame.__enter__()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Close whichever renderer was selected."""
        if self._pygame is not None:
            self._pygame.__exit__(exc_type, exc_value, traceback)
            self._pygame = None


def open_runtime(tileset: Any) -> GameRuntime:
    """Return the mandatory full-game Pygame runtime."""
    return GameRuntime(tileset)
