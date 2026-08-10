"""Reusable Pygame presentation primitives.

The module deliberately does not import Pygame at module load time. Layout
helpers are pure and remain testable in the normal tcod-only installation;
drawing helpers receive the imported Pygame module explicitly. This keeps the
migration optional until the game owns the window and event loop globally.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
import subprocess
import sys
from typing import Any


class PygameWorkerUnavailable(RuntimeError):
    """Raised when an optional Pygame worker cannot return a result."""


def run_json_worker(
    command: list[str],
    payload: dict[str, Any],
    *,
    unavailable_message: str,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a JSON-in/JSON-out worker with one consistent fallback path."""
    try:
        result = subprocess.run(
            command,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
            env=environment or os.environ.copy(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PygameWorkerUnavailable(unavailable_message) from exc
    if result.returncode != 0:
        raise PygameWorkerUnavailable(unavailable_message)
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise PygameWorkerUnavailable(unavailable_message) from exc


def worker_environment() -> dict[str, str]:
    """Return the environment used by optional Pygame workers."""
    return {**os.environ, "PYGAME_HIDE_SUPPORT_PROMPT": "1"}


def worker_command(module: str) -> list[str]:
    """Build a worker command for the current Python environment."""
    return [sys.executable, "-m", module, "--worker"]


Color = tuple[int, int, int]
Measure = Callable[[str], int]


@dataclass(frozen=True)
class Rect:
    """Pixel rectangle used by the optional Pygame UI."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Palette:
    """High-contrast colours shared by the Pygame screens."""

    background: Color = (3, 4, 8)
    panel: Color = (8, 10, 16)
    border: Color = (70, 82, 108)
    title: Color = (220, 230, 245)
    text: Color = (232, 236, 246)
    description: Color = (210, 218, 234)
    instruction: Color = (255, 240, 175)
    selected_background: Color = (28, 43, 66)
    selected_border: Color = (130, 210, 240)


DEFAULT_PALETTE = Palette()


def measure_font(font: Any, text: str) -> int:
    """Return the rendered pixel width of ``text`` for ``font``."""
    return int(font.size(text)[0])


def fit_text(text: str, max_width: int, measure: Measure) -> str:
    """Fit one line to ``max_width`` pixels, adding an ASCII ellipsis."""
    if max_width <= 0:
        return ""
    if measure(text) <= max_width:
        return text
    suffix = "..."
    if measure(suffix) >= max_width:
        return suffix
    fitted = text
    while fitted and measure(fitted + suffix) > max_width:
        fitted = fitted[:-1]
    return fitted.rstrip() + suffix


def _split_long_word(word: str, max_width: int, measure: Measure) -> list[str]:
    """Split a word that cannot fit on one line without overflowing."""
    chunks: list[str] = []
    current = ""
    for character in word:
        candidate = current + character
        if current and measure(candidate) > max_width:
            chunks.append(current)
            current = character
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [""]


def wrap_text(text: str, max_width: int, measure: Measure) -> tuple[str, ...]:
    """Wrap text at word boundaries using actual font metrics."""
    if not text or max_width <= 0:
        return ()
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for word in paragraph.split():
            if measure(word) > max_width:
                if current:
                    lines.append(current)
                    current = ""
                lines.extend(_split_long_word(word, max_width, measure))
                continue
            candidate = word if not current else f"{current} {word}"
            if current and measure(candidate) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    while lines and not lines[-1]:
        lines.pop()
    return tuple(lines)


def draw_panel(pygame: Any, screen: Any, rect: Rect, *, palette: Palette = DEFAULT_PALETTE) -> None:
    """Paint a filled panel with a restrained one-pixel border."""
    panel = pygame.Rect(rect.x, rect.y, rect.width, rect.height)
    pygame.draw.rect(screen, palette.panel, panel, border_radius=5)
    pygame.draw.rect(screen, palette.border, panel, width=1, border_radius=5)


def draw_text(
    pygame: Any,
    screen: Any,
    font: Any,
    text: str,
    x: int,
    y: int,
    *,
    color: Color,
    antialias: bool = True,
) -> Any:
    """Render one line with the font's natural glyph spacing."""
    surface = font.render(text, antialias, color)
    screen.blit(surface, (x, y))
    return surface


def draw_centered_text(
    pygame: Any,
    screen: Any,
    font: Any,
    text: str,
    rect: Rect,
    y: int,
    *,
    color: Color,
    antialias: bool = True,
) -> Any:
    """Render one line centered inside ``rect``."""
    width = measure_font(font, text)
    return draw_text(
        pygame, screen, font, text,
        rect.x + max(0, (rect.width - width) // 2), y,
        color=color, antialias=antialias,
    )


def draw_rule(pygame: Any, screen: Any, x: int, y: int, width: int, *, color: Color) -> None:
    """Paint a one-pixel horizontal separator."""
    pygame.draw.line(screen, color, (x, y), (x + max(0, width), y), width=1)


def draw_wrapped_text(
    pygame: Any,
    screen: Any,
    font: Any,
    text: str,
    x: int,
    y: int,
    max_width: int,
    *,
    color: Color,
    line_gap: int = 4,
    antialias: bool = True,
) -> int:
    """Render wrapped text and return the pixel y-coordinate after it."""
    measure = lambda value: measure_font(font, value)
    lines = wrap_text(text, max_width, measure)
    step = font.get_linesize() + line_gap
    for index, line in enumerate(lines):
        draw_text(pygame, screen, font, line, x, y + index * step, color=color, antialias=antialias)
    return y + max(1, len(lines)) * step


def draw_menu_row(
    pygame: Any,
    screen: Any,
    font: Any,
    label: str,
    x: int,
    y: int,
    width: int,
    *,
    selected: bool,
    palette: Palette = DEFAULT_PALETTE,
    antialias: bool = True,
) -> int:
    """Render one selectable row and return its recommended next y."""
    row_height = font.get_linesize() + 14
    if selected:
        row = pygame.Rect(x, y - 5, width, row_height)
        pygame.draw.rect(screen, palette.selected_background, row, border_radius=3)
        pygame.draw.rect(screen, palette.selected_border, row, width=1, border_radius=3)
    marker = "> " if selected else "  "
    measure = lambda value: measure_font(font, value)
    available_width = width - measure(marker)
    fitted_label = fit_text(label, available_width, measure)
    draw_text(
        pygame, screen, font, marker + fitted_label,
        x + 12, y + 2,
        color=palette.text if not selected else palette.title,
        antialias=antialias,
    )
    return y + row_height
