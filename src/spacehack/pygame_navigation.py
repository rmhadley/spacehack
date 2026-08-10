"""Native Pygame presentation for the read-only space navigation map."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import pygame_ui, pygame_world, pygame_quest_log


class PygameNavigationUnavailable(RuntimeError):
    """Raised when the navigation screen cannot use the active Pygame runtime."""


@dataclass(frozen=True)
class NavigationFrame:
    """Captured navigation map rows for one read-only presentation."""

    rows: tuple[tuple[pygame_quest_log.QuestSpan, ...], ...]


def _capture(ctx: Any, ship_pos: Any) -> NavigationFrame:
    """Capture the authoritative navigation renderer into portable rows."""
    from .engine import SCREEN_HEIGHT, SCREEN_WIDTH
    from .navigation import render_navigation

    capture = pygame_world.CaptureConsole(SCREEN_WIDTH, SCREEN_HEIGHT)
    render_navigation(
        capture,
        ctx,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        ship_pos=ship_pos,
    )
    rows = list(pygame_quest_log._captured_rows(capture))
    while rows and not any(span.text.strip() for span in rows[-1]):
        rows.pop()
    return NavigationFrame(tuple(rows))


def _font(pygame: Any, frame: NavigationFrame, width: int, height: int) -> Any:
    """Choose a readable font that fits the captured 100x60 map."""
    from .pygame_merchant import _font_path

    path = _font_path(pygame)
    max_width = max(
        (sum(len(span.text) for span in row) for row in frame.rows),
        default=1,
    )
    max_rows = max(1, len(frame.rows))
    for size in range(24, 11, -1):
        candidate = pygame.font.Font(path, size)
        if (
            candidate.get_linesize() * max_rows <= height - 128
            and candidate.size("M" * max_width)[0] <= width - 96
        ):
            return candidate
    return pygame.font.Font(path, 12)


def _draw(pygame: Any, screen: Any, font: Any, frame: NavigationFrame) -> None:
    """Draw the captured map inside the shared modern panel treatment."""
    width, height = screen.get_size()
    palette = pygame_ui.DEFAULT_PALETTE
    panel = pygame_ui.Rect(32, 28, width - 64, height - 56)
    pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
    pygame_ui.draw_centered_text(
        pygame, screen, font, "NAVIGATION", panel, panel.y + 22,
        color=palette.title,
    )
    pygame_ui.draw_rule(
        pygame, screen, panel.x + 24, panel.y + 54,
        panel.width - 48, color=palette.border,
    )
    content = pygame_ui.Rect(
        panel.x + 34, panel.y + 76,
        max(1, panel.width - 68), max(1, panel.height - 100),
    )
    screen.set_clip(pygame.Rect(content.x, content.y, content.width, content.height))
    try:
        for row_index, row in enumerate(frame.rows):
            x = content.x
            y = content.y + row_index * font.get_linesize()
            for span in row:
                pygame_ui.draw_text(
                    pygame, screen, font, span.text, x, y, color=span.fg,
                )
                x += pygame_ui.measure_font(font, span.text)
    finally:
        screen.set_clip(None)


def _handle_key(pygame: Any, event: Any) -> str:
    """Translate read-only navigation input."""
    if event.type == pygame.QUIT:
        return "QUIT"
    if event.type != pygame.KEYDOWN:
        return "IGNORE"
    if event.key == pygame.K_ESCAPE:
        return "BACK"
    question = getattr(pygame, "K_QUESTION", None)
    if question is not None and event.key == question:
        return "GUIDE"
    return "IGNORE"


def run_shared(context: Any, ctx: Any, ship_pos: Any) -> str:
    """Render navigation inside the already-open game window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameNavigationUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    frame = _capture(ctx, ship_pos)
    font = _font(pygame, frame, *screen.get_size())
    while True:
        screen.fill(pygame_ui.DEFAULT_PALETTE.background)
        _draw(pygame, screen, font, frame)
        engine.present()
        outcome = _handle_key(pygame, pygame.event.wait())
        if outcome != "IGNORE":
            return outcome


def run_for_context(context: Any, ctx: Any, ship_pos: Any) -> str:
    """Use the shared runtime; otherwise request the normal fallback."""
    from . import pygame_runtime

    if not pygame_runtime.shared_enabled():
        raise PygameNavigationUnavailable("Navigation requires the shared Pygame runtime")
    return run_shared(context, ctx, ship_pos)
