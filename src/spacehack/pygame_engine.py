"""Pygame-owned presentation foundation for the game renderer.

This module owns no gameplay state and imports Pygame lazily. The logical
canvas stays at the game's native 100x60 cells (1600x960 pixels), while the
physical window may be resized and letterboxed without changing map
coordinates. Tcod remains available for headless algorithms; no tcod Context
or tcod event pump is created here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .engine import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_HEIGHT,
    TILE_WIDTH,
    WINDOW_TITLE,
)


Color = tuple[int, int, int]

# Match the responsive held-key feel of tcod's terminal input while keeping
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


@dataclass(frozen=True)
class Viewport:
    """The fitted logical canvas rectangle inside the physical window."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class PygameInputEvent:
    """Renderer-neutral input event produced by the Pygame event pump."""

    kind: str
    key_name: str = ""
    modifiers: int = 0
    position: tuple[int, int] | None = None
    text: str = ""
    raw: Any = None


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
            "Pygame is not installed. Install the optional visual extra."
        ) from exc
    return pygame


def _event_from_pygame(pygame: Any, event: Any) -> PygameInputEvent:
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
    text = getattr(event, "text", "")
    return PygameInputEvent(
        kind=kind,
        key_name=key_name,
        modifiers=modifiers,
        position=position,
        text=text,
        raw=event,
    )


class GlyphAtlas:
    """A Pygame surface atlas for fixed-size map glyphs."""

    def __init__(self, pygame: Any, surface: Any, tile_width: int, tile_height: int):
        self._pygame = pygame
        self.surface = surface
        self.tile_width = tile_width
        self.tile_height = tile_height
        self._codepoints = self._load_tcod_charmap()

    @staticmethod
    def _load_tcod_charmap() -> tuple[int, ...]:
        """Use the same CP437 codepoint order as the existing tcod sheet."""
        import tcod.tileset

        return tuple(tcod.tileset.CHARMAP_TCOD)

    @classmethod
    def from_processed_tileset(cls, pygame: Any, tileset: Any) -> "GlyphAtlas":
        """Build an atlas from the project's processed tcod tileset.

        ``engine.load_tileset`` applies the approved text widening and
        procedural texture/box-drawing patches. Building the Pygame atlas from
        those glyph arrays, rather than reloading the raw PNG, keeps both
        renderers visually identical during the shared-renderer transition.
        """
        columns = 32
        rows = 8
        tile_width = tileset.tile_width
        tile_height = tileset.tile_height
        atlas = pygame.Surface(
            (columns * tile_width, rows * tile_height),
            pygame.SRCALPHA,
        )
        atlas.fill((0, 0, 0, 0))
        for index, codepoint in enumerate(cls._load_tcod_charmap()):
            try:
                tile = tileset[codepoint]
            except KeyError:
                continue
            tile_surface = pygame.image.frombuffer(
                tile.tobytes(), (tile_width, tile_height), "RGBA",
            ).convert_alpha()
            atlas.blit(
                tile_surface,
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

    def open(self) -> "PygameEngine":
        """Create the Pygame window and fixed logical canvas."""
        flags = self.pygame.RESIZABLE if self.config.resizable else 0
        self.pygame.init()
        key_module = getattr(self.pygame, "key", None)
        if key_module is not None and hasattr(key_module, "set_repeat"):
            key_module.set_repeat(KEY_REPEAT_DELAY_MS, KEY_REPEAT_INTERVAL_MS)
        self.pygame.font.init()
        self.window = self.pygame.display.set_mode(
            (self.config.window_width, self.config.window_height),
            flags,
            vsync=int(self.config.vsync),
        )
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

    def events(self) -> tuple[PygameInputEvent, ...]:
        """Poll Pygame once and return renderer-neutral input events."""
        return tuple(
            _event_from_pygame(self.pygame, event)
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
        self.viewport = fit_viewport(
            *self.window.get_size(),
            *logical_size(self.config),
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
