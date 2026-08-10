"""Native Pygame presentation for the read-only space navigation map."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import pygame_quest_log, pygame_ui, pygame_world


class PygameNavigationUnavailable(RuntimeError):
    """Raised when the navigation screen cannot use the active Pygame runtime."""


@dataclass(frozen=True)
class NavigationFrame:
    """Captured navigation content plus semantic panel regions."""

    rows: tuple[tuple[pygame_quest_log.QuestSpan, ...], ...]
    map_rows: tuple[tuple[pygame_quest_log.QuestSpan, ...], ...] = ()
    aoi_rows: tuple[tuple[pygame_quest_log.QuestSpan, ...], ...] = ()
    title: str = "NAVIGATION"
    position: str = ""


def _trim_rows(
    rows: list[tuple[pygame_quest_log.QuestSpan, ...]],
) -> tuple[tuple[pygame_quest_log.QuestSpan, ...], ...]:
    """Remove blank rows around a captured region."""
    while rows and not any(span.text.strip() for span in rows[0]):
        rows.pop(0)
    while rows and not any(span.text.strip() for span in rows[-1]):
        rows.pop()
    return tuple(rows)


def _crop_rows(
    rows: tuple[tuple[pygame_quest_log.QuestSpan, ...], ...],
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> tuple[tuple[pygame_quest_log.QuestSpan, ...], ...]:
    """Crop captured cell spans into one semantic panel region."""
    cropped: list[tuple[pygame_quest_log.QuestSpan, ...]] = []
    for row in rows[y:y + height]:
        cells: list[tuple[str, tuple[int, int, int]]] = []
        for span in row:
            cells.extend((character, span.fg) for character in span.text)
        panel_cells = cells[x:x + width]
        spans: list[pygame_quest_log.QuestSpan] = []
        current_fg: tuple[int, int, int] | None = None
        current_text = ""
        for character, fg in panel_cells:
            if fg != current_fg:
                if current_text:
                    spans.append(pygame_quest_log.QuestSpan(current_text, current_fg or fg))
                current_fg = fg
                current_text = character
            else:
                current_text += character
        if current_text:
            spans.append(pygame_quest_log.QuestSpan(current_text, current_fg or (232, 236, 246)))
        cropped.append(tuple(spans))
    return _trim_rows(cropped)


def _capture(ctx: Any, ship_pos: Any) -> NavigationFrame:
    """Capture the authoritative navigation renderer into semantic regions."""
    from .engine import SCREEN_HEIGHT, SCREEN_WIDTH
    from .navigation import render_navigation
    from . import solar_system

    capture = pygame_world.CaptureConsole(SCREEN_WIDTH, SCREEN_HEIGHT)
    render_navigation(
        capture,
        ctx,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        ship_pos=ship_pos,
    )
    rows = list(pygame_quest_log._captured_rows(capture))
    raw_rows = tuple(rows)
    trimmed_rows = _trim_rows(rows)
    map_rows = _crop_rows(raw_rows, x=20, y=5, width=40, height=30)
    aoi_rows = _crop_rows(raw_rows, x=72, y=5, width=24, height=48)
    title = f"NAVIGATION - {solar_system.current_system().name.upper()}"
    position = f"Position: ({ship_pos.x}, {ship_pos.y})"
    return NavigationFrame(
        rows=trimmed_rows,
        map_rows=map_rows,
        aoi_rows=aoi_rows,
        title=title,
        position=position,
    )


def _font(pygame: Any, frame: NavigationFrame, width: int, height: int) -> Any:
    """Choose the largest readable font that fits both navigation panels."""
    from .pygame_merchant import _font_path

    path = _font_path(pygame)
    panel_width = max(1, (width - 116) // 2)
    panel_height = max(1, height - 190)
    max_map_width = max((sum(len(span.text) for span in row) for row in frame.map_rows), default=1)
    max_aoi_width = max((sum(len(span.text) for span in row) for row in frame.aoi_rows), default=1)
    max_rows = max(len(frame.map_rows), len(frame.aoi_rows), 1)
    for size in range(26, 11, -1):
        candidate = pygame.font.Font(path, size)
        if (
            candidate.get_linesize() * max_rows <= panel_height - 38
            and candidate.size("M" * max_map_width)[0] <= panel_width - 40
            and candidate.size("M" * max_aoi_width)[0] <= panel_width - 40
        ):
            return candidate
    return pygame.font.Font(path, 12)


def _draw_rows(
    pygame: Any,
    screen: Any,
    font: Any,
    rows: tuple[tuple[pygame_quest_log.QuestSpan, ...], ...],
    panel: pygame_ui.Rect,
) -> None:
    """Draw naturally spaced coloured rows inside one clipped panel."""
    content = pygame.Rect(panel.x + 20, panel.y + 58, panel.width - 40, panel.height - 72)
    screen.set_clip(content)
    try:
        for row_index, row in enumerate(rows):
            x = content.x
            y = content.y + row_index * font.get_linesize()
            for span in row:
                pygame_ui.draw_text(pygame, screen, font, span.text, x, y, color=span.fg)
                x += pygame_ui.measure_font(font, span.text)
    finally:
        screen.set_clip(None)


def _draw_panel(
    pygame: Any,
    screen: Any,
    font: Any,
    panel: pygame_ui.Rect,
    heading: str,
    rows: tuple[tuple[pygame_quest_log.QuestSpan, ...], ...],
) -> None:
    """Draw one modern navigation panel and its captured content."""
    palette = pygame_ui.DEFAULT_PALETTE
    pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
    pygame_ui.draw_text(pygame, screen, font, heading, panel.x + 20, panel.y + 18, color=palette.title)
    pygame_ui.draw_rule(pygame, screen, panel.x + 18, panel.y + 46, panel.width - 36, color=palette.border)
    _draw_rows(pygame, screen, font, rows, panel)


def _draw(pygame: Any, screen: Any, font: Any, frame: NavigationFrame) -> None:
    """Draw the navigation map with the shared two-panel screen treatment."""
    width, height = screen.get_size()
    palette = pygame_ui.DEFAULT_PALETTE
    screen.fill(palette.background)
    outer = pygame_ui.Rect(32, 28, width - 64, height - 56)
    pygame_ui.draw_panel(pygame, screen, outer, palette=palette)
    pygame_ui.draw_centered_text(pygame, screen, font, frame.title, outer, outer.y + 22, color=palette.title)
    pygame_ui.draw_rule(pygame, screen, outer.x + 24, outer.y + 54, outer.width - 48, color=palette.border)
    gap = 20
    panel_width = max(1, (outer.width - 68 - gap) // 2)
    panel_height = max(1, height - 190)
    left = pygame_ui.Rect(48, 110, panel_width, panel_height)
    right = pygame_ui.Rect(left.x + panel_width + gap, 110, panel_width, panel_height)
    _draw_panel(pygame, screen, font, left, "SYSTEM MAP", frame.map_rows)
    _draw_panel(pygame, screen, font, right, "AREAS OF INTEREST", frame.aoi_rows)
    pygame_ui.draw_text(pygame, screen, font, frame.position, 52, height - 68, color=palette.text)
    pygame_ui.draw_text(pygame, screen, font, "ESC close   ? guide", width - 270, height - 68, color=palette.instruction)


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
        _draw(pygame, screen, font, frame)
        engine.present()
        outcome = _handle_key(pygame, pygame.event.wait())
        if outcome != "IGNORE":
            return outcome


def run_for_context(context: Any, ctx: Any, ship_pos: Any) -> str:
    """Use the shared runtime; otherwise request the normal fallback."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(context):
        raise PygameNavigationUnavailable("Navigation requires the shared Pygame runtime")
    return run_shared(context, ctx, ship_pos)
