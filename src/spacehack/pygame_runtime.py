"""Shared Pygame-owned runtime for the complete game flow.

The game uses project-owned framebuffers during the Phase 2 migration.
Input is fully project-owned in this phase: the runtime
polls Pygame and returns :class:`pygame_engine.PygameInputEvent` values without
patching a foreign event queue.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import pygame_engine
from .display_config import (
    DisplayConfig,
    load_display_config,
    save_display_config,
)
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_HEIGHT, TILE_WIDTH
from .framebuffer import FrameBuffer

if TYPE_CHECKING:
    from .game_context import GameContext


def is_shared_context(context: PygameContext) -> bool:
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

    @property
    def display_config(self) -> DisplayConfig:
        """Return the active user-facing display preferences."""
        return self._runtime.display_config

    def apply_display_config(self, config: DisplayConfig) -> None:
        """Apply display preferences through the active engine."""
        self._runtime.apply_display_config(config)

    def save_display_config(self) -> None:
        """Persist the active display preferences outside save-game state."""
        self._runtime.save_display_config()

class PygameRuntime:
    """Own one Pygame engine and its explicit input queue."""

    def __init__(
        self,
        tileset: Any,
        display_config: DisplayConfig | None = None,
        config_path: Path | None = None,
    ):
        self.tileset = tileset
        self._display_config = display_config or DisplayConfig()
        self.config_path = config_path
        self.engine: pygame_engine.PygameEngine | None = None
        self.game_context: "GameContext | None" = None
        self.context = PygameContext(self)

    @property
    def display_config(self) -> DisplayConfig:
        """Return the engine's current display preferences."""
        if self.engine is not None:
            return self.engine.display_config
        return self._display_config

    def apply_display_config(self, config: DisplayConfig) -> None:
        """Apply display preferences, retaining the logical framebuffer."""
        if self.engine is None:
            raise RuntimeError("PygameRuntime must be open before applying display config")
        self.engine.apply_display_config(config)
        self._display_config = self.engine.display_config

    def save_display_config(self) -> None:
        """Persist the current display preference to the user config."""
        save_display_config(self.display_config, self.config_path)

    def __enter__(self) -> PygameContext:
        """Open the shared window without modifying global event functions."""
        pygame = pygame_engine._load_pygame()
        try:
            self.engine = pygame_engine.PygameEngine(
                pygame,
                pygame_engine.PygameEngineConfig(
                    logical_width=SCREEN_WIDTH * TILE_WIDTH,
                    logical_height=SCREEN_HEIGHT * TILE_HEIGHT,
                    window_width=self._display_config.window_width,
                    window_height=self._display_config.window_height,
                    fullscreen=self._display_config.fullscreen,
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

    def __init__(
        self,
        tileset: Any,
        display_config: DisplayConfig | None = None,
        config_path: Path | None = None,
    ):
        self.tileset = tileset
        self.display_config = display_config
        self.config_path = config_path
        self._pygame: PygameRuntime | None = None

    def __enter__(self) -> PygameContext:
        """Open the mandatory Pygame runtime."""
        _kwargs: dict[str, Any] = {}
        if self.display_config is not None:
            _kwargs["display_config"] = self.display_config
        if self.config_path is not None:
            _kwargs["config_path"] = self.config_path
        self._pygame = PygameRuntime(self.tileset, **_kwargs)
        return self._pygame.__enter__()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Close whichever renderer was selected."""
        if self._pygame is not None:
            self._pygame.__exit__(exc_type, exc_value, traceback)
            self._pygame = None


def open_runtime(
    tileset: Any,
    *,
    display_config: DisplayConfig | None = None,
    config_path: Path | None = None,
) -> GameRuntime:
    """Return the mandatory full-game Pygame runtime."""
    return GameRuntime(
        tileset,
        display_config=display_config or load_display_config(config_path),
        config_path=config_path,
    )
