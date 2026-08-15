"""Pygame selectable-menu presentation in the shared runtime.

The domain modules supply immutable menu frames and receive only an opaque
selected action, mapping it to their existing outcomes in-process.
"""
from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any

from . import pygame_ui
from .pygame_runtime import PygameContext


class PygameMenuUnavailable(RuntimeError):
    """Raised when selectable-menu presentation cannot return."""


def enabled() -> bool:
    """Return whether generic menus can render in this runtime."""
    return pygame_ui.presentation_enabled()


@dataclass(frozen=True)
class MenuItem:
    """One selectable presentation item with a domain-owned action ID."""

    label: str
    description: str
    action: str


@dataclass(frozen=True)
class MenuFrame:
    """One selected state for a selectable text menu."""

    title: str
    body: str
    items: tuple[MenuItem, ...]
    hints: tuple[str, ...]
    selected: int
    art: tuple[str, ...] = ()
    art_color: tuple[int, int, int] | None = None
    art_colors: tuple[tuple[int, int, int], ...] = ()
    initial_selected: int | None = None
    # Pre-game screens (the title menu) must not paint the previous run's
    # console-log band; in-game menus leave this on.
    draw_log: bool = True
    # Small contextual decisions can use a compact centered popup instead of
    # occupying the full modal surface. Default preserves existing menus.
    compact: bool = False


def _font_path(pygame: Any) -> str | None:
    """Reuse the shared readable font selection."""
    return pygame_ui._font_path(pygame)


def _initial_selected(frames: tuple[MenuFrame, ...]) -> int:
    """Return a valid initial cursor index for a menu frame set."""
    if not frames:
        return 0
    count = len(frames[0].items)
    if count == 0:
        return 0
    initial = frames[0].initial_selected
    requested = initial if initial is not None else frames[0].selected
    return max(0, min(count - 1, requested))


def _content_width(width: int) -> int:
    """Return the worker panel's usable text width."""
    return max(1, width - 132)


def _frame_height(font: Any, frame: MenuFrame, content_width: int) -> int:
    """Measure one frame with a fixed description region.

    Item and description counts are capped (``MAX_VISIBLE_ROWS`` /
    ``MAX_DETAIL_LINES``) so the fitted font size — and therefore the
    rendered look — no longer depends on catalog size or the selected
    item's description length.
    """
    measure = lambda text: pygame_ui.measure_font(font, text)
    line_height = font.get_linesize()
    body_lines = pygame_ui.wrap_text(frame.body, content_width, measure)
    description_lines = min(
        pygame_ui.max_wrapped_lines(
            (item.description for item in frame.items),
            content_width - 28,
            measure,
        ),
        pygame_ui.MAX_DETAIL_LINES,
    )
    height = len(body_lines) * (line_height + 3) + 10
    if frame.art:
        height += len(frame.art) * line_height + 10
    height += min(len(frame.items), pygame_ui.MAX_VISIBLE_ROWS) * (line_height + 14)
    height += max(1, description_lines) * (line_height + 2)
    height += 8 + len(frame.hints) * (line_height + 4)
    return height


COMPACT_MAX_VISIBLE_ROWS = 4


def _compact_frame_height(font: Any, frame: MenuFrame, width: int) -> int:
    """Measure a compact popup including wrapped title, body, and rows."""
    popup_width, title_lines, body_lines = _compact_popup_layout(font, frame, width)
    del popup_width
    line_height = font.get_linesize()
    title_step = line_height + 4
    body_step = line_height + 4
    row_height = line_height + 18
    _top, visible_count = pygame_ui.visible_window(
        frame.items, frame.selected, COMPACT_MAX_VISIBLE_ROWS,
        is_selectable=lambda _item: True,
    )
    rule_y = 18 + max(1, len(title_lines)) * title_step + 12
    body_y = rule_y + 16
    return body_y + len(body_lines) * body_step + 16 + visible_count * row_height


def _fit_font(
    pygame: Any,
    frames: tuple[MenuFrame, ...],
    width: int,
    height: int,
    *,
    reserve_log: bool = False,
) -> Any:
    """Choose the largest font that fits wrapped content in every frame."""
    path = _font_path(pygame)
    content_width = _content_width(width)
    available_height = max(1, height - 132)
    if reserve_log:
        available_height -= pygame_ui.LOG_PANEL_HEIGHT + pygame_ui.FOOTER_PAD

    def measure_height(font: Any) -> int:
        # Reject sizes whose ASCII art would overflow the content column.
        if any(
            font.size(line)[0] > content_width
            for frame in frames
            for line in frame.art
        ):
            return available_height + 1
        return max(
            (
                _compact_frame_height(font, frame, width)
                if frame.compact
                else _frame_height(font, frame, content_width)
                for frame in frames
            ),
            default=0,
        )

    return pygame_ui.fit_font(
        pygame, path,
        measure_height=measure_height,
        available_height=max(1, available_height),
    )


def _fit_shared_font(
    pygame: Any,
    frames: tuple[MenuFrame, ...],
    width: int,
    height: int,
) -> Any:
    """Fit a shared menu while supporting legacy four-argument patches."""
    if "reserve_log" in inspect.signature(_fit_font).parameters:
        return _fit_font(pygame, frames, width, height, reserve_log=True)
    return _fit_font(pygame, frames, width, height)


def _draw_art(
    pygame: Any,
    screen: Any,
    font: Any,
    panel: pygame_ui.Rect,
    frame: MenuFrame,
    y: int,
    content_width: int,
    measure: Any,
) -> int:
    """Paint optional centered ASCII art and return the next content y."""
    if not frame.art:
        return y
    default_color = frame.art_color or pygame_ui.DEFAULT_PALETTE.description
    for index, line in enumerate(frame.art):
        line_color = (
            frame.art_colors[index]
            if index < len(frame.art_colors)
            else default_color
        )
        pygame_ui.draw_centered_text(
            pygame,
            screen,
            font,
            pygame_ui.fit_text(line, content_width, measure),
            panel,
            y,
            color=line_color,
        )
        y += font.get_linesize()
    return y + 10


def _compact_popup_layout(
    font: Any,
    frame: MenuFrame,
    width: int,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    """Return bounded popup width and wrapped title/body lines."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    title_width = measure(frame.title)
    option_width = max(
        (measure(item.label) for item in frame.items),
        default=0,
    )
    max_popup_width = max(1, width - 160)
    popup_width = min(
        max_popup_width,
        max(1, 360, title_width + 64, option_width + 72),
    )
    content_width = max(1, popup_width - 48)
    return (
        popup_width,
        pygame_ui.wrap_text(frame.title, content_width, measure),
        pygame_ui.wrap_text(frame.body, content_width, measure),
    )


def _draw_compact_scrollbar(
    pygame: Any, screen: Any, frame: MenuFrame, popup: pygame_ui.Rect,
    inset: int, row_y: int, row_height: int, top: int, count: int,
) -> None:
    """Paint a proportional scrollbar when compact options overflow."""
    total = len(frame.items)
    if total <= count:
        return
    track_height = count * row_height
    track_width = 5
    track_x = popup.x + popup.width - inset // 2 - track_width // 2
    palette = pygame_ui.DEFAULT_PALETTE
    pygame.draw.rect(
        screen, palette.border,
        pygame.Rect(track_x, row_y, track_width, track_height),
        border_radius=2,
    )
    thumb_height = max(track_width, track_height * count // total)
    thumb_range = track_height - thumb_height
    thumb_y = row_y + thumb_range * top // max(1, total - count)
    pygame.draw.rect(
        screen, palette.selected_border,
        pygame.Rect(track_x, thumb_y, track_width, thumb_height),
        border_radius=2,
    )


def _draw_compact_rows(
    pygame: Any, screen: Any, font: Any, frame: MenuFrame,
    popup: pygame_ui.Rect, inset: int, content_width: int,
    y: int, top: int, count: int, row_height: int,
) -> None:
    """Paint the visible compact menu rows."""
    _draw_compact_scrollbar(
        pygame, screen, frame, popup, inset, y, row_height, top, count,
    )
    for index in range(top, top + count):
        item = frame.items[index]
        pygame_ui.draw_menu_row(
            pygame, screen, font, item.label, popup.x + inset, y,
            content_width, selected=index == frame.selected,
            palette=pygame_ui.DEFAULT_PALETTE,
        )
        y += row_height


def _draw_compact_content(
    pygame: Any,
    screen: Any,
    font: Any,
    frame: MenuFrame,
    popup: pygame_ui.Rect,
    title_lines: tuple[str, ...],
    body_lines: tuple[str, ...],
    top: int,
    count: int,
    title_y: int,
    rule_y: int,
    body_y: int,
    row_height: int,
) -> None:
    """Paint compact popup content inside its already-sized panel."""
    palette = pygame_ui.DEFAULT_PALETTE
    inset = min(24, max(1, popup.width // 2))
    content_width = max(1, popup.width - 2 * inset)
    title_step = row_height - 14
    y = popup.y + title_y
    for line in title_lines or ("",):
        pygame_ui.draw_centered_text(
            pygame, screen, font, line, popup, y, color=palette.title,
        )
        y += title_step
    pygame_ui.draw_rule(
        pygame, screen, popup.x + inset, popup.y + rule_y,
        content_width, color=palette.border,
    )
    y = popup.y + body_y
    for line in body_lines:
        pygame_ui.draw_centered_text(
            pygame, screen, font, line, popup, y, color=palette.description,
        )
        y += font.get_linesize() + 4
    _draw_compact_rows(
        pygame, screen, font, frame, popup, inset, content_width,
        y + 8, top, count, row_height,
    )


def _draw_compact_frame(
    pygame: Any,
    screen: Any,
    font: Any,
    frame: MenuFrame,
) -> None:
    """Paint a small centered two-choice popup."""
    width, height = screen.get_size()
    popup_width, title_lines, body_lines = _compact_popup_layout(font, frame, width)
    line_height = font.get_linesize()
    title_step = line_height + 4
    row_height = line_height + 18
    title_y = 18
    rule_y = title_y + max(1, len(title_lines)) * title_step + 12
    body_y = rule_y + 16
    top, count = pygame_ui.visible_window(
        frame.items, frame.selected, COMPACT_MAX_VISIBLE_ROWS,
        is_selectable=lambda _item: True,
    )
    popup_height = (
        body_y + len(body_lines) * (line_height + 4) + 16 + count * row_height
    )
    popup = pygame_ui.Rect(
        (width - popup_width) // 2,
        (height - popup_height) // 2,
        popup_width,
        popup_height,
    )
    pygame_ui.draw_panel(
        pygame, screen, popup, palette=pygame_ui.DEFAULT_PALETTE,
    )
    _draw_compact_content(
        pygame, screen, font, frame, popup, title_lines, body_lines,
        top, count, title_y, rule_y, body_y, row_height,
    )


def _draw_frame(
    pygame: Any,
    screen: Any,
    font: Any,
    frame: MenuFrame,
    *,
    context: PygameContext | None = None,
) -> None:
    """Paint a menu frame with natural font spacing."""
    if frame.compact:
        _draw_compact_frame(pygame, screen, font, frame)
        return
    palette = pygame_ui.DEFAULT_PALETTE
    width, height = screen.get_size()
    panel = pygame_ui.Rect(32, 28, width - 64, height - 56)
    pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
    pygame_ui.draw_centered_text(
        pygame, screen, font, frame.title, panel, panel.y + 22,
        color=palette.title,
    )
    pygame_ui.draw_rule(
        pygame, screen, panel.x + 24, panel.y + 54,
        panel.width - 48, color=palette.border,
    )
    x = panel.x + 34
    content_width = _content_width(width)
    content_bottom = (
        pygame_ui.modal_footer_y(height)
        if context is not None and frame.draw_log
        else panel.y + panel.height - 20
    )
    _draw_standard_content(
        pygame, screen, font, frame, panel, x, content_width, content_bottom,
    )
    if context is not None and frame.draw_log:
        pygame_ui.draw_context_log(pygame, screen, context, palette=palette)


def _standard_content_geometry(font: Any, frame: MenuFrame, content_width: int, content_bottom: int, top: int):
    """Measure standard-menu content and return its drawing geometry."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    line_height = font.get_linesize()
    body_lines = pygame_ui.wrap_text(frame.body, content_width, measure)
    body_height = len(body_lines) * (line_height + 3) + 10
    if frame.art:
        body_height += len(frame.art) * line_height + 10
    window_top, window_count = pygame_ui.visible_window(
        frame.items, frame.selected, pygame_ui.MAX_VISIBLE_ROWS,
        is_selectable=lambda item: True,
    )
    description_width = content_width - 28
    description = frame.items[frame.selected].description if frame.items else ""
    description_lines = pygame_ui.wrap_text(description, description_width, measure)
    description_height = max(1, len(description_lines)) * (line_height + 2)
    block = body_height + window_count * (line_height + 14) + 8 + description_height + 8
    block += len(frame.hints) * (line_height + 4)
    y = top + max(0, (content_bottom - 8 - top - block) // 2)
    return (
        measure, line_height, body_lines, window_top, window_count,
        description_width, description, description_height, y,
    )


def _draw_standard_body(
    pygame: Any, screen: Any, font: Any, frame: MenuFrame, panel: pygame_ui.Rect,
    x: int, content_width: int, content_bottom: int, geometry,
) -> tuple[int, int]:
    """Draw standard-menu art, body, rows, and description."""
    measure, line_height, body_lines, window_top, window_count, description_width, description, description_height, y = geometry
    y = _draw_art(pygame, screen, font, panel, frame, y, content_width, measure)
    for line in body_lines:
        pygame_ui.draw_text(pygame, screen, font, line, x, y, color=pygame_ui.DEFAULT_PALETTE.description)
        y += line_height + 3
    y += 10
    for index in range(window_top, window_top + window_count):
        item = frame.items[index]
        row_height = line_height + 14
        if y + row_height > content_bottom:
            break
        pygame_ui.draw_menu_row(
            pygame, screen, font, item.label, x, y, content_width,
            selected=index == frame.selected, palette=pygame_ui.DEFAULT_PALETTE,
        )
        y += row_height
    y += 8
    if frame.items and y < content_bottom:
        pygame_ui.draw_wrapped_text(
            pygame, screen, font, description, x + 28, y, description_width,
            color=pygame_ui.DEFAULT_PALETTE.description, line_gap=2,
        )
    return y + description_height + 8, line_height


def _draw_standard_hints(
    pygame: Any, screen: Any, font: Any, frame: MenuFrame, x: int,
    content_width: int, content_bottom: int, measure: Any, y: int, line_height: int,
) -> None:
    """Draw standard-menu hints below the content block."""
    palette = pygame_ui.DEFAULT_PALETTE
    for hint in frame.hints:
        if y + line_height > content_bottom:
            break
        pygame_ui.draw_text(
            pygame, screen, font, pygame_ui.fit_text(hint, content_width, measure),
            x, y, color=palette.instruction,
        )
        y += line_height + 4


def _draw_standard_content(
    pygame: Any, screen: Any, font: Any, frame: MenuFrame, panel: pygame_ui.Rect,
    x: int, content_width: int, content_bottom: int,
) -> None:
    """Measure and paint standard-menu content inside the panel."""
    geometry = _standard_content_geometry(
        font, frame, content_width, content_bottom, panel.y + 76,
    )
    measure = geometry[0]
    screen.set_clip(
        pygame.Rect(panel.x + 1, panel.y + 1, max(1, panel.width - 2), max(1, panel.height - 2))
    )
    try:
        y, line_height = _draw_standard_body(
            pygame, screen, font, frame, panel, x, content_width,
            content_bottom, geometry,
        )
        _draw_standard_hints(
            pygame, screen, font, frame, x, content_width, content_bottom,
            measure, y, line_height,
        )
    finally:
        screen.set_clip(None)


def _draw_shared_frame(
    pygame: Any, screen: Any, font: Any, frame: MenuFrame, context: PygameContext,
) -> None:
    """Draw a shared frame while preserving legacy renderer test doubles."""
    if "context" in inspect.signature(_draw_frame).parameters:
        _draw_frame(pygame, screen, font, frame, context=context)
        return
    _draw_frame(pygame, screen, font, frame)
    if frame.draw_log:
        pygame_ui.draw_context_log(pygame, screen, context)


def _handle_key(pygame: Any, event: Any, selected: int, count: int) -> tuple[str, int]:
    """Map one menu event to navigation or a terminal menu outcome."""
    if event.type == pygame.QUIT:
        return "QUIT", selected
    if event.type != pygame.KEYDOWN:
        return "IGNORE", selected
    if event.key == pygame.K_ESCAPE:
        return "BACK", selected
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE", selected
    if event.key in (pygame.K_UP, pygame.K_k) and count:
        return "IGNORE", (selected - 1) % count
    if event.key in (pygame.K_DOWN, pygame.K_j) and count:
        return "IGNORE", (selected + 1) % count
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return ("SELECT", selected) if count else ("DISMISS", selected)
    return "IGNORE", selected

def _run_shared_loop(
    pygame: Any,
    engine: Any,
    screen: Any,
    font: Any,
    frames: tuple[MenuFrame, ...],
    context: PygameContext,
) -> tuple[str, str, int]:
    """Render shared menu frames until a terminal outcome arrives."""
    selected = _initial_selected(frames)
    count = len(frames[0].items)
    while True:
        frame = frames[selected % len(frames)]
        if not frame.compact:
            screen.fill(pygame_ui.DEFAULT_PALETTE.background)
        _draw_shared_frame(pygame, screen, font, frame, context)
        engine.present()
        outcome, selected = _handle_key(
            pygame, pygame.event.wait(), selected, count,
        )
        if outcome == "IGNORE":
            continue
        action = frame.items[selected].action if outcome == "SELECT" and frame.items else ""
        return outcome, action, selected


def run_shared(
    context: PygameContext,
    frames: tuple[MenuFrame, ...],
    *,
    caption: str = "spacehack",
) -> tuple[str, str, int]:
    """Run a menu inside the already-open shared Pygame window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameMenuUnavailable("Shared Pygame runtime is not open")
    frames = tuple(frames)
    if not frames:
        raise PygameMenuUnavailable("Shared Pygame menu has no frames")
    pygame = engine.pygame
    width, height = engine.logical_surface.get_size()
    font = _fit_shared_font(pygame, frames, width, height)
    return _run_shared_loop(
        pygame, engine, engine.logical_surface, font, frames, context,
    )


def run_for_context(
    context: PygameContext,
    frames: tuple[MenuFrame, ...],
    *,
    caption: str = "spacehack",
) -> tuple[str, str, int]:
    """Run the menu in the already-open shared Pygame window."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(context):
        raise PygameMenuUnavailable("Shared Pygame runtime is not open")
    return run_shared(context, frames, caption=caption)


