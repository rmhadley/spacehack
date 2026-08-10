"""Standalone text-rendering comparison spike.

This tool does not change the game renderer. It opens a separate Pygame
window with the current loaded tcod bitmap raster on the left and Pygame
font-rendered samples on the right.

Run from the project root after installing the optional visual dependency:

    pip install -e '.[visual]'
    python3 tools/text_render_spike.py

Use ``--help`` for font, size, scaling, and antialiasing options. Close the
window or press Escape/Q to exit.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


SAMPLE_LINES: tuple[str, ...] = (
    "SPACEHACK",
    "Mission: Salvage the derelict",
    "Epsilon Eridani  $  1250",
    "Hull 100%   Fuel 42/60   Wpn 3/4",
    "[>] Continue     [ESC] Back",
)
_FONT_CANDIDATES: tuple[str, ...] = (
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Noto Sans Mono",
    "Courier New",
)


@dataclass(frozen=True)
class PanelRect:
    """Pixel rectangle for one comparison panel."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class SpikeConfig:
    """Validated visual settings for the comparison window."""

    width: int = 1280
    height: int = 760
    font_size: int = 30
    bitmap_scale: int = 2
    font_name: str | None = None
    antialias: bool = True


def panel_rects(width: int, height: int, gap: int = 18) -> tuple[PanelRect, PanelRect]:
    """Return balanced left/right panel rectangles for ``width`` x ``height``."""
    outer = 24
    panel_width = (width - outer * 2 - gap) // 2
    panel_height = height - outer * 2
    left = PanelRect(outer, outer, panel_width, panel_height)
    right = PanelRect(outer + panel_width + gap, outer, panel_width, panel_height)
    return left, right


def clamp_config(config: SpikeConfig) -> SpikeConfig:
    """Return a safe configuration without changing unrelated settings."""
    return SpikeConfig(
        width=max(800, config.width),
        height=max(520, config.height),
        font_size=max(12, min(config.font_size, 96)),
        bitmap_scale=max(1, min(config.bitmap_scale, 4)),
        font_name=config.font_name,
        antialias=config.antialias,
    )


def choose_font_path(pygame: Any, requested: str | None) -> str | None:
    """Resolve a requested or preferred monospace font through Pygame."""
    if requested and Path(requested).is_file():
        return requested
    candidates = (requested,) if requested else _FONT_CANDIDATES
    for candidate in candidates:
        if not candidate:
            continue
        path = pygame.font.match_font(candidate)
        if path:
            return path
    return None


def _load_pygame() -> Any:
    """Import Pygame lazily so the project remains tcod-only by default."""
    try:
        import pygame
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Pygame is not installed. Run: pip install -e '.[visual]'"
        ) from exc
    return pygame


def _project_root() -> Path:
    """Return the repository root from this tool's location."""
    return Path(__file__).resolve().parents[1]


def _load_current_tileset():
    """Load the exact bitmap tileset used by the active tcod renderer."""
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from src.spacehack import engine

    return engine.load_tileset()


def _tile_surface(pygame: Any, tile: np.ndarray, color: tuple[int, int, int], scale: int):
    """Convert one tcod RGBA tile into a scaled, tinted Pygame surface."""
    height, width = tile.shape[:2]
    surface = pygame.image.frombuffer(tile.tobytes(), (width, height), "RGBA").convert_alpha()
    if color != (255, 255, 255):
        surface.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    if scale != 1:
        surface = pygame.transform.scale(surface, (width * scale, height * scale))
    return surface


def _draw_panel_frame(pygame: Any, screen: Any, rect: PanelRect, title: str, font: Any) -> None:
    """Draw one comparison panel's background, border, and title."""
    panel = pygame.Rect(rect.x, rect.y, rect.width, rect.height)
    pygame.draw.rect(screen, (8, 10, 16), panel, border_radius=4)
    pygame.draw.rect(screen, (70, 82, 108), panel, width=1, border_radius=4)
    title_surface = font.render(title, True, (220, 230, 245))
    screen.blit(title_surface, (rect.x + 20, rect.y + 18))


def _draw_bitmap_line(
    pygame: Any,
    screen: Any,
    tileset: Any,
    text: str,
    x: int,
    y: int,
    scale: int,
    color: tuple[int, int, int],
) -> None:
    """Draw a text line using the actual current tcod bitmap tiles."""
    cursor_x = x
    for character in text:
        tile = np.asarray(tileset[ord(character)])
        glyph = _tile_surface(pygame, tile, color, scale)
        screen.blit(glyph, (cursor_x, y))
        cursor_x += tile.shape[1] * scale


def _draw_bitmap_panel(pygame: Any, screen: Any, rect: PanelRect, tileset: Any, config: SpikeConfig, ui_font: Any) -> None:
    """Render representative text using the current tcod bitmap raster."""
    _draw_panel_frame(pygame, screen, rect, "CURRENT TCOD BITMAP (+3)", ui_font)
    x = rect.x + 20
    y = rect.y + 72
    line_step = config.bitmap_scale * 16 + 22
    for index, line in enumerate(SAMPLE_LINES):
        color = (238, 242, 255) if index == 0 else (190, 204, 226)
        _draw_bitmap_line(
            pygame, screen, tileset, line, x, y + index * line_step,
            config.bitmap_scale, color,
        )
    note = ui_font.render("16px cells; current widened raster", True, (132, 148, 172))
    screen.blit(note, (x, rect.y + rect.height - 38))


def _draw_pygame_sample(
    pygame: Any,
    screen: Any,
    rect: PanelRect,
    font: Any,
    ui_font: Any,
    config: SpikeConfig,
    font_path: str | None,
) -> None:
    """Render the same representative text with a Pygame font."""
    title = "PYGAME FONT (AA)" if config.antialias else "PYGAME FONT (CRISP)"
    _draw_panel_frame(pygame, screen, rect, title, ui_font)
    x = rect.x + 20
    y = rect.y + 78
    line_step = config.font_size + 30
    for index, line in enumerate(SAMPLE_LINES):
        color = (245, 247, 255) if index == 0 else (198, 210, 232)
        rendered = font.render(line, config.antialias, color)
        screen.blit(rendered, (x, y + index * line_step))
    selected = Path(font_path).name if font_path else "Pygame default font"
    note = ui_font.render(f"{selected}  |  {config.font_size}px", True, (132, 148, 172))
    screen.blit(note, (x, rect.y + rect.height - 38))


def run_spike(config: SpikeConfig) -> None:
    """Open and run the standalone comparison window."""
    pygame = _load_pygame()
    config = clamp_config(config)
    pygame.init()
    pygame.font.init()
    try:
        screen = pygame.display.set_mode((config.width, config.height))
        pygame.display.set_caption("spacehack text rendering spike")
        ui_font = pygame.font.Font(None, 20)
        font_path = choose_font_path(pygame, config.font_name)
        font = pygame.font.Font(font_path, config.font_size)
        tileset = _load_current_tileset()
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
            screen.fill((3, 4, 8))
            left, right = panel_rects(config.width, config.height)
            _draw_bitmap_panel(pygame, screen, left, tileset, config, ui_font)
            _draw_pygame_sample(pygame, screen, right, font, ui_font, config, font_path)
            footer = ui_font.render("ESC / Q  close", True, (132, 148, 172))
            screen.blit(footer, (24, config.height - 22))
            pygame.display.flip()
            clock.tick(60)
    finally:
        pygame.quit()


def _parse_args(argv: list[str] | None = None) -> SpikeConfig:
    """Parse command-line settings into a comparison configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", help="Pygame font family or path")
    parser.add_argument("--size", type=int, default=30, help="Pygame font size in pixels")
    parser.add_argument("--scale", type=int, default=2, help="Scale factor for the current bitmap")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=760)
    parser.add_argument("--no-aa", action="store_true", help="Disable Pygame antialiasing")
    args = parser.parse_args(argv)
    return SpikeConfig(
        width=args.width,
        height=args.height,
        font_size=args.size,
        bitmap_scale=args.scale,
        font_name=args.font,
        antialias=not args.no_aa,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the comparison spike from command-line arguments."""
    run_spike(_parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
