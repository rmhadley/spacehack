"""Reusable Pygame presentation for text-heavy interactive screens.

The game process supplies immutable rows and opaque actions. The shared
runtime owns only presentation and input; all game state remains in the game
process.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import inspect
from typing import Any

from . import pygame_menu, pygame_ui
from .pygame_runtime import PygameContext


# Vertical breathing room between content sections (shared screen family,
# see 15_DESIGN_UNIFIED_TERMINAL_UX.md decision #9). Only applied when the
# section above actually exists, so body-less screens get no leading gap.
BODY_ROWS_GAP = 24   # body text -> first selectable row
ROWS_DETAIL_GAP = 20  # last row -> selected-item detail
CONTENT_INDENT = 24   # selectable/informational rows under a section header


class PygameScreenUnavailable(RuntimeError):
    """Raised when the text-screen presentation cannot return."""


def enabled() -> bool:
    """Return whether generic text screens can render in this runtime."""
    return pygame_ui.presentation_enabled()


@dataclass(frozen=True)
class ScreenRow:
    """One selectable, informational, or section-header row."""

    text: str
    detail: str = ""
    action: str = ""
    selectable: bool = True
    header: bool = False


@dataclass(frozen=True)
class ScreenFrame:
    """Presentation-only screen state."""

    title: str
    body: tuple[str, ...]
    rows: tuple[ScreenRow, ...]
    footer: tuple[str, ...] = ()
    selected: int = 0
    page_offset: int = 0
    tabs: tuple[str, ...] = ()
    active_tab: int = 0
    # Long bodies page (PAGE UP/DOWN) instead of shrinking the fitted
    # font to fit on one screen — keeps the font size consistent.
    scrollable: bool = False
    # Optional per-body-line colours used by the console history. Existing
    # screens leave this empty and use the shared description colour.
    body_colors: tuple[tuple[int, int, int], ...] = ()
    # Screens such as the full console history can request newest-first
    # opening without changing the default top-of-document behavior.
    start_at_end: bool = False


def _selectable(frame: ScreenFrame) -> tuple[int, ...]:
    """Return selectable row indices."""
    return tuple(i for i, row in enumerate(frame.rows) if row.selectable)


def _clamp(frame: ScreenFrame) -> int:
    """Clamp selection to a selectable row."""
    indices = _selectable(frame)
    if not indices:
        return 0
    if frame.selected in indices:
        return frame.selected
    return min(indices, key=lambda i: abs(i - frame.selected))


def _handle_key(pygame: Any, event: Any, frame: ScreenFrame) -> tuple[str, int]:
    """Map one event to outcome and selection."""
    selected = _clamp(frame)
    indices = _selectable(frame)
    if event.type == pygame.QUIT:
        return "QUIT", selected
    if event.type != pygame.KEYDOWN:
        return "IGNORE", selected
    if event.key == pygame.K_ESCAPE:
        return "BACK", selected
    if event.key == getattr(pygame, "K_TAB", None):
        return "TAB", selected
    if event.key == getattr(pygame, "K_PAGEDOWN", None):
        return "PAGE_DOWN", selected
    if event.key == getattr(pygame, "K_PAGEUP", None):
        return "PAGE_UP", selected
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE", selected
    if event.key in (pygame.K_UP, pygame.K_k):
        if indices:
            pos = indices.index(selected)
            return "IGNORE", indices[(pos - 1) % len(indices)]
        if frame.scrollable:
            return "PAGE_UP", selected
    if event.key in (pygame.K_DOWN, pygame.K_j):
        if indices:
            pos = indices.index(selected)
            return "IGNORE", indices[(pos + 1) % len(indices)]
        if frame.scrollable:
            return "PAGE_DOWN", selected
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return ("SELECT", selected) if indices else ("BACK", selected)
    return "IGNORE", selected


def _body_lines_with_colors(
    font: Any,
    frame: ScreenFrame,
    width: int,
) -> tuple[tuple[str, tuple[int, int, int] | None], ...]:
    """Wrap body paragraphs while carrying optional line colours."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    lines: list[tuple[str, tuple[int, int, int] | None]] = []
    for index, text in enumerate(frame.body):
        color = frame.body_colors[index] if index < len(frame.body_colors) else None
        lines.extend((line, color) for line in (pygame_ui.wrap_text(text, width, measure) or ("",)))
    return tuple(lines)


def _body_lines(font: Any, frame: ScreenFrame, width: int) -> tuple[str, ...]:
    """Wrap body paragraphs using the candidate font metrics."""
    return tuple(line for line, _color in _body_lines_with_colors(font, frame, width))


def _initial_page_offset(
    font: Any,
    frame: ScreenFrame,
    width: int,
    height: int,
) -> int:
    """Return the first page offset for a scrollable frame."""
    if not frame.start_at_end:
        return frame.page_offset
    body_lines = _body_lines(font, frame, width)
    body_start = 126 if frame.tabs else 84
    footer_start = pygame_ui.modal_footer_y(height)
    body_budget = _body_budget(font, frame, width, height, body_start, footer_start)
    return max(0, len(body_lines) - body_budget)


def _page_offset(
    font: Any,
    frame: ScreenFrame,
    width: int,
    outcome: str,
) -> int:
    """Advance or rewind a scrollable body by one readable page."""
    body_lines = _body_lines(font, frame, width)
    if outcome == "PAGE_DOWN":
        return min(max(0, len(body_lines) - 1), frame.page_offset + 8)
    if outcome == "PAGE_UP":
        return max(0, frame.page_offset - 8)
    return frame.page_offset


def _info_window(frame: ScreenFrame) -> tuple[int, int]:
    """Viewport for frames with no selectable rows: show the whole list.

    :func:`pygame_ui.visible_window` yields ``(0, 0)`` when every row is
    non-selectable, which would blank informational-only frames (the
    Character screen's Equipment tab, empty-cargo / no-missiles
    fallbacks). Non-empty frames without selectable rows instead render
    as a capped list of info rows.
    """
    if not frame.rows:
        return 0, 0
    return 0, min(len(frame.rows), pygame_ui.MAX_VISIBLE_ROWS)


def _rows_height(font: Any, frame: ScreenFrame) -> int:
    """Height of the capped rows viewport, incl. informational frames."""
    line_height = font.get_linesize()
    row_height = pygame_ui.window_height(
        frame.rows, pygame_ui.MAX_VISIBLE_ROWS,
        is_selectable=lambda row: row.selectable,
        selectable_step=line_height + 14, info_step=line_height + 4,
    )
    if row_height == 0 and frame.rows:
        row_height = _info_window(frame)[1] * (line_height + 4)
    return row_height


def _non_body_height(font: Any, frame: ScreenFrame, width: int) -> int:
    """Measure rows, fixed detail region, spacing, and footer.

    Rows use the tallest capped viewport window and details are capped at
    ``MAX_DETAIL_LINES``, so the fitted font — and therefore the rendered
    look — is independent of list length and selection state.
    """
    measure = lambda value: pygame_ui.measure_font(font, value)
    detail_width = width
    detail_lines = min(
        pygame_ui.max_wrapped_lines(
            (row.detail for row in frame.rows if row.selectable),
            detail_width,
            measure,
        ),
        pygame_ui.MAX_DETAIL_LINES,
    )
    line_height = font.get_linesize()
    row_height = _rows_height(font, frame)
    detail_height = max(1, detail_lines) * (line_height + 2)
    footer_height = (max(1, len(frame.footer)) + 1) * (line_height + 3)
    rows_detail_gap = ROWS_DETAIL_GAP if row_height else 0
    return row_height + rows_detail_gap + detail_height + 12 + footer_height


def _body_budget(
    font: Any,
    frame: ScreenFrame,
    width: int,
    height: int,
    start_y: int,
    footer_start: int | None = None,
) -> int:
    """Return body lines available while reserving rows and footer."""
    footer_start = height - 70 if footer_start is None else footer_start
    reserved = _non_body_height(font, frame, width - 28)
    available = footer_start - start_y - 8 - reserved
    return max(0, available // (font.get_linesize() + 3))


def _layout_height(
    font: Any,
    frame: ScreenFrame,
    width: int,
    *,
    available_height: int | None = None,
) -> int:
    """Measure the worst selectable state using renderer widths."""
    body_lines = _body_lines(font, frame, width)
    body_rows_gap = BODY_ROWS_GAP if body_lines else 0
    height = len(body_lines) * (font.get_linesize() + 3) + body_rows_gap + _non_body_height(
        font, frame, width - 28,
    )
    if frame.scrollable and available_height is not None:
        # Scrollable bodies page (PAGE UP/DOWN) instead of shrinking the
        # font: measure a single screen so every section sizes its font
        # identically regardless of body length.
        return min(height, available_height)
    return height


def _fit_font(
    pygame: Any,
    frame: ScreenFrame,
    width: int,
    height: int,
    *,
    reserve_log: bool = False,
) -> Any:
    """Choose the largest readable font that fits wrapped content."""
    path = pygame_menu._font_path(pygame)
    content_width = max(1, width - 80)
    available_height = max(1, height - 70 - 84)
    if reserve_log:
        available_height -= pygame_ui.LOG_PANEL_HEIGHT + pygame_ui.FOOTER_PAD
    return pygame_ui.fit_font(
        pygame, path,
        measure_height=lambda font: _layout_height(
            font, frame, content_width, available_height=available_height,
        ),
        available_height=max(1, available_height),
    )


def _draw_screen_header(
    pygame: Any, screen: Any, font: Any, frame: ScreenFrame,
    width: int, palette: Any,
) -> int:
    """Draw the title, rule, and tab bar; return the body's starting y."""
    pygame_ui.draw_centered_text(
        pygame, screen, font, frame.title,
        pygame_ui.Rect(24, 16, width - 48, 42), 24,
        color=palette.title,
    )
    pygame_ui.draw_rule(pygame, screen, 48, 62, width - 96, color=palette.border)
    if not frame.tabs:
        return 84
    tab_width = max(1, (width - 80) // len(frame.tabs))
    for index, tab in enumerate(frame.tabs):
        tab_x = 40 + index * tab_width
        selected_tab = index == frame.active_tab
        tab_rect = pygame.Rect(tab_x, 72, tab_width - 8, 36)
        pygame.draw.rect(
            screen,
            palette.selected_background if selected_tab else palette.panel,
            tab_rect, border_radius=4,
        )
        pygame.draw.rect(
            screen,
            palette.selected_border if selected_tab else palette.border,
            tab_rect, width=2 if selected_tab else 1, border_radius=4,
        )
        pygame_ui.draw_centered_text(
            pygame, screen, font, tab,
            pygame_ui.Rect(tab_x, 72, tab_width - 8, 36), 80,
            color=palette.title if selected_tab else palette.description,
        )
    return 126


@dataclass(frozen=True)
class _ScreenLayout:
    """Geometry computed once for a single text-screen render."""

    visible_body: tuple[tuple[str, tuple[int, int, int] | None], ...]
    body_step: int
    body_budget: int
    body_overflow: bool
    body_rows_gap: int
    rows_detail_gap: int
    footer_start: int
    detail_width: int
    detail: str
    detail_height: int
    y: int


def _layout_screen(font: Any, frame: ScreenFrame, width: int, height: int, body_start: int, context: Any) -> _ScreenLayout:
    """Compute the geometry anchoring a text screen's content block."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    body_lines = _body_lines_with_colors(font, frame, width - 80)
    visible_body = body_lines[frame.page_offset:]
    body_step = font.get_linesize() + 3
    footer_start = (
        pygame_ui.modal_footer_y(height) if context is not None else height - 70
    )
    body_budget = _body_budget(font, frame, width - 80, height, body_start, footer_start)
    body_overflow = len(body_lines) > body_budget
    body_block = min(len(visible_body), body_budget) * body_step
    rows_block = _rows_height(font, frame)
    body_rows_gap = BODY_ROWS_GAP if body_block else 0
    rows_detail_gap = ROWS_DETAIL_GAP if rows_block else 0
    detail_width = width - 108
    selected = _clamp(frame)
    detail = frame.rows[selected].detail if 0 <= selected < len(frame.rows) else ""
    detail_height = pygame_ui.wrapped_text_height(
        detail, detail_width, measure, font.get_linesize(), 2,
    )
    y = body_start
    if not frame.scrollable:
        content_height = (
            body_block + body_rows_gap + rows_block
            + rows_detail_gap + detail_height + 8
        )
        y = body_start + max(0, (footer_start - 8 - body_start - content_height) // 2)
    return _ScreenLayout(
        visible_body=visible_body, body_step=body_step, body_budget=body_budget,
        body_overflow=body_overflow, body_rows_gap=body_rows_gap,
        rows_detail_gap=rows_detail_gap, footer_start=footer_start,
        detail_width=detail_width, detail=detail, detail_height=detail_height,
        y=y,
    )


def _draw_screen_body(pygame: Any, screen: Any, font: Any, layout: _ScreenLayout, palette: Any) -> int:
    """Draw the visible body lines and return the y after the block."""
    y = layout.y
    for line, body_color in layout.visible_body[:layout.body_budget]:
        pygame_ui.draw_text(
            pygame, screen, font, line, 40, y,
            color=body_color or palette.description,
        )
        y += layout.body_step
    return y


def _max_detail_height(frame: ScreenFrame, detail_width: int, measure: Any, font: Any) -> int:
    """Return the tallest selectable-row detail, or a minimum fallback."""
    return max(
        (
            pygame_ui.wrapped_text_height(
                row.detail, detail_width, measure, font.get_linesize(), 2,
            )
            for row in frame.rows
            if row.selectable
        ),
        default=font.get_linesize() + 2,
    )


def _draw_screen_rows(
    pygame: Any, screen: Any, font: Any, frame: ScreenFrame,
    width: int, y: int, layout: _ScreenLayout, palette: Any,
) -> tuple[int, int]:
    """Draw rows and the selected detail; return (y, detail block height)."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    selected = _clamp(frame)
    window_top, window_count = pygame_ui.visible_window(
        frame.rows, selected, pygame_ui.MAX_VISIBLE_ROWS,
        is_selectable=lambda row: row.selectable,
    )
    if window_count == 0:
        window_top, window_count = _info_window(frame)
    content_indent = CONTENT_INDENT if any(row.header for row in frame.rows) else 0
    content_x, content_width = 40 + content_indent, width - 80 - content_indent
    for index in range(window_top, window_top + window_count):
        row = frame.rows[index]
        row_height = font.get_linesize() + 14 if row.selectable else font.get_linesize() + 4
        if y + row_height > layout.footer_start:
            break
        row_x = 40 if row.header else content_x
        row_width = width - 80 if row.header else content_width
        if row.selectable:
            y = pygame_ui.draw_menu_row(
                pygame, screen, font, row.text, row_x, y, row_width,
                selected=index == selected, palette=palette,
            )
        else:
            y = pygame_ui.draw_informational_row(
                pygame, screen, font, row.text, row_x, y, row_width,
                color=palette.description,
            )
    measure_detail_height = _max_detail_height(frame, layout.detail_width, measure, font)
    if y + layout.detail_height <= layout.footer_start:
        y += layout.rows_detail_gap
        pygame_ui.draw_wrapped_text(
            pygame, screen, font, layout.detail, 68, y,
            layout.detail_width, color=palette.description, line_gap=2,
        )
    return y, measure_detail_height


def _draw_screen_footer(
    pygame: Any, screen: Any, font: Any, frame: ScreenFrame,
    width: int, y: int, layout: _ScreenLayout, measure_detail_height: int, palette: Any,
) -> int:
    """Draw the footer block and return its final y."""
    footer_lines = frame.footer
    if layout.body_overflow:
        scroll_hint = (
            "PAGE UP/DOWN or j/k/arrows scroll for more"
            if frame.scrollable else "PAGE UP/DOWN scroll for more"
        )
        footer_lines = (scroll_hint,) + footer_lines
    footer_step = font.get_linesize() + 3
    footer_top = layout.footer_start - len(footer_lines) * footer_step
    measure = lambda text: pygame_ui.measure_font(font, text)
    y = max(y + measure_detail_height + 8, footer_top)
    for line in footer_lines:
        if y + font.get_linesize() > layout.footer_start:
            break
        pygame_ui.draw_text(
            pygame, screen, font, pygame_ui.fit_text(line, width - 80, measure),
            40, y, color=palette.instruction,
        )
        y += footer_step
    return y


def _draw_frame(
    pygame: Any,
    screen: Any,
    font: Any,
    frame: ScreenFrame,
    *,
    context: PygameContext | None = None,
    draw_log: bool = True,
) -> None:
    """Paint the current text screen."""
    palette = pygame_ui.DEFAULT_PALETTE
    width, height = screen.get_size()
    screen.fill(palette.background)
    body_start = _draw_screen_header(pygame, screen, font, frame, width, palette)
    layout = _layout_screen(font, frame, width, height, body_start, context)
    y = _draw_screen_body(pygame, screen, font, layout, palette)
    y += layout.body_rows_gap
    y, measure_detail_height = _draw_screen_rows(
        pygame, screen, font, frame, width, y, layout, palette,
    )
    _draw_screen_footer(
        pygame, screen, font, frame, width, y, layout,
        measure_detail_height, palette,
    )
    if context is not None and draw_log:
        pygame_ui.draw_context_log(pygame, screen, context, palette=palette)


def _draw_shared_frame(
    pygame: Any,
    screen: Any,
    font: Any,
    frame: ScreenFrame,
    context: PygameContext,
    *,
    draw_log: bool = True,
) -> None:
    """Draw a shared frame while preserving legacy renderer test doubles."""
    parameters = inspect.signature(_draw_frame).parameters
    kwargs: dict[str, Any] = {}
    if "context" in parameters:
        kwargs["context"] = context
    if "draw_log" in parameters:
        kwargs["draw_log"] = draw_log
    _draw_frame(pygame, screen, font, frame, **kwargs)
    if "context" not in parameters and draw_log:
        pygame_ui.draw_context_log(pygame, screen, context)


def _physical_log_callback(engine: Any, context: PygameContext):
    """Build a callback that paints a modal's log at physical scale."""
    columns = engine.config.logical_width // pygame_ui.TILE_WIDTH
    rows = engine.config.logical_height // pygame_ui.TILE_HEIGHT

    def _draw(pygame: Any, window: Any, viewport: Any) -> None:
        """Paint the reserved modal log band on the physical window."""
        tile_width = max(1, viewport.width // columns)
        tile_height = max(1, viewport.height // rows)
        pygame_ui.draw_context_log(
            pygame,
            window,
            context,
            origin_x=viewport.x,
            origin_y=viewport.y,
            width=viewport.width,
            height=viewport.height,
            tile_width=tile_width,
            tile_height=tile_height,
        )

    return _draw


def run_shared(
    context: PygameContext,
    frame: ScreenFrame,
    *,
    caption: str = "spacehack",
) -> tuple[str, str, int]:
    """Run a text screen inside the already-open shared Pygame window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameScreenUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    width, height = screen.get_size()
    font = _fit_font(pygame, frame, width, height, reserve_log=True)
    frame = replace(
        frame,
        page_offset=_initial_page_offset(font, frame, width - 80, height),
    )
    while True:
        current = replace(frame, selected=_clamp(frame))
        _draw_shared_frame(
            pygame, screen, font, current, context, draw_log=False,
        )
        engine.present(
            physical_overlay=_physical_log_callback(engine, context),
        )
        event = pygame.event.wait()
        outcome, selected = _handle_key(pygame, event, current)
        if outcome in {"IGNORE", "PAGE_DOWN", "PAGE_UP"}:
            frame = replace(
                frame,
                selected=selected,
                page_offset=_page_offset(font, current, width - 80, outcome),
            )
            continue
        row = current.rows[selected] if outcome == "SELECT" else None
        return outcome, row.action if row else "", selected


def run_for_context(
    context: PygameContext,
    frame: ScreenFrame,
    *,
    caption: str = "spacehack",
) -> tuple[str, str, int]:
    """Run the screen in the already-open shared Pygame window."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(context):
        raise PygameScreenUnavailable("Shared Pygame runtime is not open")
    return run_shared(context, frame, caption=caption)


