"""Shared Pygame-owned runtime for the complete game flow.

The game still uses tcod consoles as renderer-neutral framebuffers and tcod
KeyDown objects as the domain input contract. This module owns the one default
SDL window, converts console cells to the existing Pygame glyph atlas, and
bridges Pygame events back to tcod events. Presentation is always owned by this Pygame runtime; tcod remains only
as the renderer-neutral console and event contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import tcod.event

from . import pygame_engine
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_HEIGHT, TILE_WIDTH


def is_shared_context(context: Any) -> bool:
    """Return whether ``context`` belongs to the active shared runtime."""
    runtime = getattr(context, "_runtime", None)
    return getattr(runtime, "engine", None) is not None


def _key_sym(name: str, text: str = "") -> Any | None:
    """Map a Pygame key name to the installed tcod ``KeySym`` enum."""
    if text == "?":
        name = "question"
    aliases = {
        "return": "RETURN",
        "kp enter": "KP_ENTER",
        "escape": "ESCAPE",
        "tab": "TAB",
        "up": "UP",
        "down": "DOWN",
        "left": "LEFT",
        "right": "RIGHT",
        "period": "PERIOD",
        ".": "PERIOD",
        "slash": "SLASH",
        "/": "SLASH",
        "question": "QUESTION",
        "?": "QUESTION",
        "space": "SPACE",
        "backspace": "BACKSPACE",
        "delete": "DELETE",
        "home": "HOME",
        "end": "END",
        "page up": "PAGEUP",
        "page down": "PAGEDOWN",
    }
    lowered = name.strip().lower()
    enum_name = aliases.get(lowered)
    if enum_name is None:
        if lowered.startswith("kp ") and lowered[3:].isdigit():
            enum_name = f"KP_{lowered[3:]}"
        elif lowered.isdigit():
            enum_name = f"N{lowered}"
        elif len(lowered) == 1 and lowered.isalpha():
            enum_name = lowered.upper()
        else:
            enum_name = lowered.upper().replace(" ", "_")
    return getattr(tcod.event.KeySym, enum_name, None)


def _tcod_event_from_pygame(pygame: Any, event: Any) -> Any | None:
    """Convert one Pygame event into the legacy tcod event contract."""
    if event.type == pygame.QUIT:
        return tcod.event.Quit()
    if event.type not in (pygame.KEYDOWN, pygame.KEYUP):
        return None
    key_name = pygame.key.name(event.key)
    sym = _key_sym(key_name, getattr(event, "unicode", ""))
    if sym is None:
        return None
    event_type = tcod.event.KeyDown if event.type == pygame.KEYDOWN else tcod.event.KeyUp
    return event_type(
        scancode=tcod.event.Scancode.UNKNOWN,
        sym=sym,
        mod=int(getattr(event, "mod", 0)),
    )


def _commands_from_console(console: Any) -> tuple[Any, ...]:
    """Extract renderer-neutral draw commands from a capture or tcod console."""
    commands = getattr(console, "commands", None)
    if commands is not None:
        return tuple(commands)
    chars = getattr(console, "ch", None)
    foreground = getattr(console, "fg", None)
    background = getattr(console, "bg", None)
    if chars is None or foreground is None or background is None:
        raise TypeError("console does not expose capture commands or cell planes")
    height, width = chars.shape
    if foreground.shape != (height, width, 3):
        raise ValueError("console foreground plane has an invalid shape")
    if background.shape != (height, width, 3):
        raise ValueError("console background plane has an invalid shape")
    return tuple(
        CaptureConsoleCommand(
            x=x,
            y=y,
            char=chr(int(chars[y, x])),
            fg=tuple(int(value) for value in foreground[y, x]),
            bg=tuple(int(value) for value in background[y, x]),
        )
        for y in range(height)
        for x in range(width)
    )


@dataclass(frozen=True)
class CaptureConsoleCommand:
    """Small command shape used when reading native tcod console planes."""

    x: int
    y: int
    char: str
    fg: tuple[int, int, int]
    bg: tuple[int, int, int] | None


class PygameContext:
    """Minimal tcod-context-compatible adapter backed by Pygame."""

    def __init__(self, runtime: "PygameRuntime"):
        self._runtime = runtime

    def present(self, console: Any, *, overlay: Any | None = None) -> None:
        """Paint one console and optional native text overlay into Pygame."""
        if overlay is None:
            self._runtime.present(console)
        else:
            self._runtime.present(console, overlay=overlay)

    def convert_event(self, event: Any) -> Any:
        """Keep the tcod-context API used by the jump menu compatibility path."""
        return event


class PygameRuntime:
    """Own one Pygame engine and bridge the legacy tcod event functions."""

    def __init__(self, tileset: Any):
        self.tileset = tileset
        self.engine: pygame_engine.PygameEngine | None = None
        self.game_context: Any | None = None
        self.context = PygameContext(self)
        self._old_wait: Callable[..., Any] | None = None
        self._old_get: Callable[..., Any] | None = None

    def __enter__(self) -> PygameContext:
        """Open the shared window and install the event bridge."""
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
            self._old_wait = tcod.event.wait
            self._old_get = tcod.event.get
            tcod.event.wait = self._wait
            tcod.event.get = self._get
        except Exception:
            self.close()
            raise
        return self.context

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Restore tcod event functions and close the shared window."""
        self.close()

    def _wait(self, *_args: Any, **_kwargs: Any) -> tuple[Any, ...]:
        """Block for Pygame input and return converted tcod events."""
        if self.engine is None:
            return ()
        pygame = self.engine.pygame
        while True:
            event = pygame.event.wait()
            converted = _tcod_event_from_pygame(pygame, event)
            if converted is not None:
                return (converted,)

    def _get(self, *_args: Any, **_kwargs: Any) -> tuple[Any, ...]:
        """Poll Pygame input and return converted tcod events."""
        if self.engine is None:
            return ()
        pygame = self.engine.pygame
        return tuple(
            converted
            for event in pygame.event.get()
            if (converted := _tcod_event_from_pygame(pygame, event)) is not None
        )

    def present(self, console: Any, *, overlay: Any | None = None) -> None:
        """Render a console, then an optional native Pygame overlay."""
        if self.engine is None or self.engine.logical_surface is None or self.engine.glyphs is None:
            raise RuntimeError("Pygame runtime is not open")
        self.engine.clear()
        for command in _commands_from_console(console):
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
        """Restore global bridges and release Pygame resources idempotently."""
        if self._old_wait is not None:
            tcod.event.wait = self._old_wait
            self._old_wait = None
        if self._old_get is not None:
            tcod.event.get = self._old_get
            self._old_get = None
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
