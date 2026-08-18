"""Pygame-owned presentation foundation for the game renderer.

This module owns no gameplay state and imports Pygame lazily. The logical
canvas stays at the game's native 100x60 cells (1600x960 pixels), while the
physical window may be resized and letterboxed without changing map
coordinates. The presentation engine owns the input event shape and pump.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .display_config import DisplayConfig
from .engine import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_HEIGHT,
    TILE_WIDTH,
    WINDOW_TITLE,
    TILESHEET_COLUMNS,
    TILESHEET_ROWS,
    CP437_CHARMAP,
)


Color = tuple[int, int, int]

# Match the responsive held-key feel of the former terminal input while keeping
# the initial press distinct from the repeated movement ticks.
KEY_REPEAT_DELAY_MS: int = 400
KEY_REPEAT_INTERVAL_MS: int = 55


@dataclass(frozen=True)
class PygameEngineConfig:
    """Window and logical-canvas settings for the Pygame presentation."""

    logical_width: int = SCREEN_WIDTH * TILE_WIDTH
    logical_height: int = SCREEN_HEIGHT * TILE_HEIGHT
    window_width: int = SCREEN_WIDTH * TILE_WIDTH
    window_height: int = SCREEN_HEIGHT * TILE_HEIGHT
    title: str = WINDOW_TITLE
    resizable: bool = True
    vsync: bool = True
    fullscreen: bool = False


@dataclass(frozen=True)
class Viewport:
    """The fitted logical canvas rectangle inside the physical window."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class PygameInputEvent:
    """Project-owned input event produced by the Pygame event pump."""

    kind: str
    key_name: str = ""
    modifiers: int = 0
    shift: bool = False
    repeat: bool = False
    position: tuple[int, int] | None = None
    text: str = ""



def is_keydown(event: PygameInputEvent) -> bool:
    """Return whether an input event represents a pressed key."""
    return getattr(event, "kind", "") == "keydown"


def is_keyup(event: PygameInputEvent) -> bool:
    """Return whether an input event represents a released key."""
    return getattr(event, "kind", "") == "keyup"


def is_quit(event: PygameInputEvent) -> bool:
    """Return whether an input event requests application shutdown."""
    return getattr(event, "kind", "") == "quit"


def is_escape(event: PygameInputEvent) -> bool:
    """Return whether a keydown event is the Escape key."""
    return is_keydown(event) and event.key_name == "escape"


def has_shift(event: PygameInputEvent) -> bool:
    """Return whether a key event carries a Shift modifier."""
    return event.shift


def movement_key_name(event: PygameInputEvent) -> str:
    """Return the normalized key name used by movement/action tables."""
    return event.key_name


def guide_key(event: PygameInputEvent) -> bool:
    """Return whether a keydown event represents the question-mark key."""
    return is_keydown(event) and (
        event.key_name in {"question", "?"}
        or (event.key_name == "slash" and event.shift)
        or event.text == "?"
    )


def quit_or_escape(event: PygameInputEvent) -> bool:
    """Return whether an event is a window close or Escape press."""
    return is_quit(event) or is_escape(event)


_KEY_ALIASES: dict[str, str] = {
    "return": "enter",
    "kp enter": "enter",
    "escape": "escape",
    "left": "left",
    "right": "right",
    "up": "up",
    "down": "down",
    "kp 1": "kp_1",
    "kp 2": "kp_2",
    "kp 3": "kp_3",
    "kp 4": "kp_4",
    "kp 5": "kp_5",
    "kp 6": "kp_6",
    "kp 7": "kp_7",
    "kp 8": "kp_8",
    "kp 9": "kp_9",
    "\\": "backslash",
    "nonusbackslash": "backslash",
}


def logical_size(config: PygameEngineConfig) -> tuple[int, int]:
    """Return the fixed logical pixel size used for every game frame."""
    return config.logical_width, config.logical_height


def fit_viewport(
    window_width: int,
    window_height: int,
    logical_width: int,
    logical_height: int,
) -> Viewport:
    """Fit a logical canvas inside a window while preserving its aspect ratio."""
    if min(window_width, window_height, logical_width, logical_height) <= 0:
        return Viewport(0, 0, 1, 1)
    scale = min(window_width / logical_width, window_height / logical_height)
    width = max(1, int(logical_width * scale))
    height = max(1, int(logical_height * scale))
    return Viewport(
        (window_width - width) // 2,
        (window_height - height) // 2,
        width,
        height,
    )


def fit_cell_viewport(
    window_width: int,
    window_height: int,
    columns: int,
    rows: int,
) -> Viewport:
    """Fit a character grid using an integer physical size per cell.

    Keeping every cell the same whole-pixel size avoids fractional cell
    boundaries when a fullscreen display is not an exact multiple of the
    logical grid. The unused pixels become letterbox space instead of being
    distributed across glyphs and colored tile edges.
    """
    if min(window_width, window_height, columns, rows) <= 0:
        return Viewport(0, 0, 1, 1)
    cell_size = min(window_width // columns, window_height // rows)
    if cell_size <= 0:
        return fit_viewport(window_width, window_height, columns, rows)
    width = columns * cell_size
    height = rows * cell_size
    return Viewport(
        (window_width - width) // 2,
        (window_height - height) // 2,
        width,
        height,
    )


def logical_position(
    position: tuple[int, int],
    viewport: Viewport,
    logical_width: int,
    logical_height: int,
) -> tuple[int, int] | None:
    """Convert a physical mouse position into logical-canvas coordinates."""
    x, y = position
    if not (
        viewport.x <= x < viewport.x + viewport.width
        and viewport.y <= y < viewport.y + viewport.height
    ):
        return None
    logical_x = (x - viewport.x) * logical_width // viewport.width
    logical_y = (y - viewport.y) * logical_height // viewport.height
    return logical_x, logical_y


def normalize_key_name(name: str) -> str:
    """Normalize Pygame's human-readable key name for game input tables."""
    lowered = name.strip().lower()
    return _KEY_ALIASES.get(lowered, lowered)


def _load_pygame() -> Any:
    """Import Pygame only when the Pygame-owned engine is explicitly used."""
    try:
        import pygame
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Pygame is not installed. Install the project with: python -m pip install -e ."
        ) from exc
    return pygame


def translate_event(pygame: Any, event: Any) -> PygameInputEvent:
    """Translate one Pygame event without exposing it to game domains."""
    event_types = {
        pygame.QUIT: "quit",
        pygame.KEYDOWN: "keydown",
        pygame.KEYUP: "keyup",
        pygame.MOUSEMOTION: "mousemotion",
        pygame.MOUSEBUTTONDOWN: "mousebuttondown",
        pygame.MOUSEBUTTONUP: "mousebuttonup",
    }
    kind = event_types.get(event.type, "other")
    key_name = ""
    modifiers = int(getattr(event, "mod", 0))
    if kind in ("keydown", "keyup"):
        key_name = normalize_key_name(pygame.key.name(event.key))
    position = getattr(event, "pos", None)
    text = getattr(event, "text", getattr(event, "unicode", ""))
    shift_mask = int(getattr(pygame, "KMOD_SHIFT", 3))
    return PygameInputEvent(
        kind=kind,
        key_name=key_name,
        modifiers=modifiers,
        shift=bool(modifiers & shift_mask),
        repeat=bool(getattr(event, "repeat", False)),
        position=position,
        text=text,
    )


class GlyphAtlas:
    """A Pygame surface atlas for fixed-size map glyphs."""

    def __init__(self, pygame: Any, surface: Any, tile_width: int, tile_height: int):
        self._pygame = pygame
        self.surface = surface
        self.tile_width = tile_width
        self.tile_height = tile_height
        self._codepoints = tuple(CP437_CHARMAP)

    @classmethod
    def from_processed_tileset(cls, pygame: Any, tileset: Any) -> "GlyphAtlas":
        """Build an atlas from the processed project-owned glyph tiles."""
        columns = TILESHEET_COLUMNS
        rows = TILESHEET_ROWS
        tile_width = tileset.tile_width
        tile_height = tileset.tile_height
        atlas = pygame.Surface(
            (columns * tile_width, rows * tile_height),
            pygame.SRCALPHA,
        )
        atlas.fill((0, 0, 0, 0))
        for index, codepoint in enumerate(CP437_CHARMAP):
            try:
                tile = tileset[codepoint]
            except KeyError:
                continue
            atlas.blit(
                tile,
                ((index % columns) * tile_width,
                 (index // columns) * tile_height),
            )
        return cls(pygame, atlas, tile_width, tile_height)

    def _source_rect(self, character: str) -> Any | None:
        """Return the source rectangle for ``character``, if mapped."""
        if not character:
            return None
        try:
            index = self._codepoints.index(ord(character))
        except ValueError:
            return None
        columns = self.surface.get_width() // self.tile_width
        return self._pygame.Rect(
            (index % columns) * self.tile_width,
            (index // columns) * self.tile_height,
            self.tile_width,
            self.tile_height,
        )

    def blit(
        self,
        target: Any,
        character: str,
        x: int,
        y: int,
        *,
        fg: Color,
        bg: Color | None = None,
    ) -> None:
        """Paint one tinted glyph and optionally its background."""
        rect = self._pygame.Rect(
            x, y, self.tile_width, self.tile_height,
        )
        if bg is not None:
            target.fill((*bg, 255), rect)
        if character == "█":
            target.fill((*fg, 255), rect)
            return
        source_rect = self._source_rect(character)
        if source_rect is None or character == " ":
            return
        glyph = self.surface.subsurface(source_rect).copy()
        glyph.fill((*fg, 255), special_flags=self._pygame.BLEND_RGBA_MULT)
        target.blit(glyph, rect)


class PygameEngine:
    """Own the Pygame display and logical presentation surface."""

    def __init__(
        self,
        pygame: Any,
        config: PygameEngineConfig | None = None,
        *,
        tileset: Any | None = None,
    ):
        self.pygame = pygame
        self.config = config or PygameEngineConfig()
        self.tileset = tileset
        self.window: Any | None = None
        self.logical_surface: Any | None = None
        self.viewport = Viewport(0, 0, self.config.window_width, self.config.window_height)
        self.glyphs: GlyphAtlas | None = None

    def _display_flags(self, config: PygameEngineConfig) -> int:
        """Return Pygame flags for the requested window mode."""
        if config.fullscreen:
            return getattr(self.pygame, "FULLSCREEN", 0)
        return getattr(self.pygame, "RESIZABLE", 0) if config.resizable else 0

    def _display_size(self, config: PygameEngineConfig) -> tuple[int, int]:
        """Return the physical size requested by the display mode."""
        return (0, 0) if config.fullscreen else (
            config.window_width,
            config.window_height,
        )

    def _set_display_mode(self, config: PygameEngineConfig) -> Any:
        """Create the physical window for ``config`` without touching the canvas."""
        return self.pygame.display.set_mode(
            self._display_size(config),
            self._display_flags(config),
            vsync=int(config.vsync),
        )

    def open(self) -> "PygameEngine":
        """Create the Pygame window and fixed logical canvas."""
        self.pygame.init()
        key_module = getattr(self.pygame, "key", None)
        if key_module is not None and hasattr(key_module, "set_repeat"):
            key_module.set_repeat(KEY_REPEAT_DELAY_MS, KEY_REPEAT_INTERVAL_MS)
        self.pygame.font.init()
        self.window = self._set_display_mode(self.config)
        self.pygame.display.set_caption(self.config.title)
        self.logical_surface = self.pygame.Surface(
            logical_size(self.config), self.pygame.SRCALPHA,
        )
        from .engine import load_tileset

        self.glyphs = GlyphAtlas.from_processed_tileset(
            self.pygame,
            self.tileset if self.tileset is not None else load_tileset(),
        )
        return self

    @property
    def display_config(self) -> DisplayConfig:
        """Return the current user-facing display preferences."""
        if self.window is not None and not self.config.fullscreen:
            width, height = self.window.get_size()
        else:
            width, height = self.config.window_width, self.config.window_height
        return DisplayConfig(
            fullscreen=self.config.fullscreen,
            window_width=width,
            window_height=height,
        ).normalized()

    def apply_display_config(self, display_config: DisplayConfig) -> None:
        """Apply a display preference while preserving the logical surface."""
        if self.window is None:
            raise RuntimeError("PygameEngine.open() must be called first")
        _display = display_config.normalized()
        _new_config = replace(
            self.config,
            window_width=_display.window_width,
            window_height=_display.window_height,
            fullscreen=_display.fullscreen,
        )
        self.window = self._set_display_mode(_new_config)
        self.config = _new_config

    def events(self) -> tuple[PygameInputEvent, ...]:
        """Poll Pygame once and return renderer-neutral input events."""
        return tuple(
            translate_event(self.pygame, event)
            for event in self.pygame.event.get()
        )

    def clear(self, color: Color = (0, 0, 0)) -> None:
        """Clear the logical frame, not the physical window."""
        if self.logical_surface is None:
            raise RuntimeError("PygameEngine.open() must be called first")
        self.logical_surface.fill((*color, 255))

    def present(self) -> Viewport:
        """Scale the logical frame into the window and flip once."""
        if self.window is None or self.logical_surface is None:
            raise RuntimeError("PygameEngine.open() must be called first")
        self.viewport = fit_cell_viewport(
            *self.window.get_size(),
            self.config.logical_width // TILE_WIDTH,
            self.config.logical_height // TILE_HEIGHT,
        )
        self.window.fill((0, 0, 0))
        scaled = self.pygame.transform.scale(
            self.logical_surface,
            (self.viewport.width, self.viewport.height),
        )
        self.window.blit(scaled, (self.viewport.x, self.viewport.y))
        self.pygame.display.flip()
        return self.viewport

    def close(self) -> None:
        """Release Pygame resources owned by this engine."""
        key_module = getattr(self.pygame, "key", None)
        if key_module is not None and hasattr(key_module, "set_repeat"):
            key_module.set_repeat(0)
        self.pygame.display.quit()
        self.pygame.quit()


def open_pygame_engine(
    config: PygameEngineConfig | None = None,
) -> PygameEngine:
    """Load Pygame lazily and return an opened engine."""
    pygame = _load_pygame()
    return PygameEngine(pygame, config).open()
