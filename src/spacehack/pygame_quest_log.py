"""Pygame presentation for the Quest Log modal.

The game process remains the source of truth for quest-log content: it renders
the authoritative Quest Log frame into a small capture console, then paints the
captured cell text and colours natively in the shared Pygame runtime. The
presentation never receives mutable game objects or changes mission state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import pygame_ui, pygame_world
from .game_context import GameContext
from .pygame_runtime import PygameContext


class PygameQuestLogUnavailable(RuntimeError):
    """Raised when the Quest Log presentation cannot return a choice."""


@dataclass(frozen=True)
class QuestSpan:
    """One naturally rendered colour run within a Quest Log row."""

    text: str
    fg: tuple[int, int, int]


# The shared tab treatment (ScreenFrame.tabs): sheet order and names.
_QUESTS_PANE, _RUMORS_PANE = "quests", "rumors"
_PANES = (_QUESTS_PANE, _RUMORS_PANE)
_PANE_TABS = ("QUESTS", "RUMORS")


@dataclass(frozen=True)
class QuestFrame:
    """Captured Quest Log rows for one pane/selection/confirm state.

    ``tabs``/``active_tab`` mirror :class:`pygame_screen.ScreenFrame`:
    the shared tab treatment selects the quests sheet or the rumor
    ledger (doc 42)."""

    rows: tuple[tuple[QuestSpan, ...], ...]
    selected: int
    confirm_abandon: bool
    hint: str = ""
    tabs: tuple[str, ...] = ()
    active_tab: int = 0


def _captured_rows(capture: pygame_world.CaptureConsole) -> tuple[tuple[QuestSpan, ...], ...]:
    """Convert final captured cells into naturally rendered row spans."""
    cells: dict[tuple[int, int], pygame_world.world.WorldDrawCommand] = {
        (command.x, command.y): command for command in capture.commands
    }
    rows: list[tuple[QuestSpan, ...]] = []
    for y in range(capture.height):
        row_cells = [
            (x, cells[(x, y)])
            for x in range(capture.width)
            if (x, y) in cells
        ]
        if not row_cells:
            rows.append(())
            continue
        max_x = row_cells[-1][0]
        spans: list[QuestSpan] = []
        current_fg: tuple[int, int, int] | None = None
        current_text = ""
        for x in range(max_x + 1):
            command = cells.get((x, y))
            char = command.char if command is not None else " "
            fg = command.fg if command is not None else (232, 236, 246)
            if fg != current_fg:
                if current_text:
                    spans.append(QuestSpan(current_text, current_fg or fg))
                current_fg = fg
                current_text = char
            else:
                current_text += char
        if current_text:
            spans.append(QuestSpan(current_text, current_fg or (232, 236, 246)))
        rows.append(tuple(spans))
    return tuple(rows)


# The legacy terminal renderer anchors its own header via ui.screen_header
# (title row 2, divider row 3, blank gap row 4), so its real content begins
# at row 5. The Pygame presentation draws its own header, so the captured
# header block is dropped to avoid a double header.
_LEGACY_HEADER_BLOCK = 5

# Legacy footer-hint lines painted by the terminal renderer
# (menus/_quest_log.py). They are pulled out of the captured content so the
# Pygame footer can draw them in the modern position instead of as a body
# row. Prefixes are matched (not exact) so a hint that wraps or carries
# extra spacing still extracts; keep these in sync if the terminal hint
# strings are ever reworded in menus/_quest_log.py.
_HINT_PREFIXES = (
    "UP/DOWN navigate",
    "Press ENTER to abandon",
    "Press ESC to close",
)


def _quest_rows(capture: pygame_world.CaptureConsole) -> tuple[tuple[QuestSpan, ...], ...]:
    """Keep quest content, excluding the legacy header and message-log band."""
    from .engine import MSG_LOG_HEIGHT, SCREEN_HEIGHT

    rows = _captured_rows(capture)[:SCREEN_HEIGHT - MSG_LOG_HEIGHT]
    return rows[_LEGACY_HEADER_BLOCK:]


def _strip_trailing_blank_rows(
    rows: tuple[tuple[QuestSpan, ...], ...],
) -> tuple[tuple[QuestSpan, ...], ...]:
    """Drop trailing blank rows. Runs AFTER the hint split: the
    legacy hint line is the pane's last non-blank row, so stripping
    before the split leaves the blanks the scrollbar counts as
    content (the phantom scrollbar on a fitting ledger)."""
    while rows and not any(span.text.strip() for span in rows[-1]):
        rows = rows[:-1]
    return rows


def _split_hint(rows: tuple[tuple[QuestSpan, ...], ...]) -> tuple[tuple[tuple[QuestSpan, ...], ...], str]:
    """Return ``(content_rows, hint)``, moving a trailing hint row out."""
    if not rows:
        return rows, ""
    text = "".join(span.text for span in rows[-1]).strip()
    if text.startswith(_HINT_PREFIXES):
        return rows[:-1], text
    return rows, ""


def _capture_frame(
    ctx: GameContext, selected: int, confirm_abandon: bool,
    pane: str = "quests",
) -> QuestFrame:
    """``pane`` is ``"quests"`` or ``"rumors"``; the frame carries the
    shared tab fields so the renderer draws the active sheet."""
    """Render one authoritative Quest Log state into portable rows."""
    from .menus._quest_log import render_quest_log
    from .engine import SCREEN_HEIGHT, SCREEN_WIDTH

    capture = pygame_world.CaptureConsole(SCREEN_WIDTH, SCREEN_HEIGHT)
    render_quest_log(
        capture,
        ctx,
        selected=selected,
        confirm_abandon=confirm_abandon,
        pane=pane,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
    )
    rows = _strip_trailing_blank_rows(_quest_rows(capture))
    rows, hint = _split_hint(rows)
    return QuestFrame(
        rows=_strip_trailing_blank_rows(rows),
        selected=selected,
        confirm_abandon=confirm_abandon,
        hint=hint,
        tabs=_PANE_TABS,
        active_tab=_PANES.index(pane),
    )


def _frames_for(
    ctx: GameContext,
) -> tuple[tuple[QuestFrame, ...], tuple[QuestFrame, ...]]:
    """ ``(quests frames, rumor frames)`` — every reachable pane/
    selection/confirmation state. The ledger scrolls, so only the
    quests pane may drive font-height fitting; both constrain width."""
    count = len(ctx.player_active_missions)
    selections = tuple(range(count)) if count else (-1,)
    quests = tuple(
        _capture_frame(ctx, selected, confirm_abandon, _QUESTS_PANE)
        for confirm_abandon in (False, True)
        for selected in selections
    )
    return quests, (_capture_frame(ctx, 0, False, _RUMORS_PANE),)


def _font_path(pygame: Any) -> str | None:
    """Choose the shared readable font family."""
    return pygame_ui._font_path(pygame)


def _fit_font(
    pygame: Any, frames: tuple[QuestFrame, ...], width: int, height: int,
    *, extra_width_frames: tuple[QuestFrame, ...] = (),
) -> Any:
    """Choose the largest font that fits captured rows in the canvas.
    ``extra_width_frames`` constrain width only — scrollable panes
    need no height fit."""
    path = _font_path(pygame)
    _width_frames = frames + extra_width_frames
    max_text_width = max(
        (sum(len(span.text) for span in row) for frame in _width_frames for row in frame.rows),
        default=1,
    )
    max_rows = max((len(frame.rows) for frame in frames), default=1)
    for size in range(24, 11, -1):
        font = pygame.font.Font(path, size)
        if (
            font.get_linesize() * max_rows <= height - 24
            and font.size("M" * max_text_width)[0] <= width - 48
        ):
            return font
    return pygame.font.Font(path, 12)


def _draw_quest_scrollbar(
    pygame: Any, screen: Any, frame: QuestFrame, content: pygame_ui.Rect,
    visible_count: int,
) -> None:
    """Draw a proportional scrollbar when the quest log exceeds its viewport."""
    total = len(frame.rows)
    if total <= visible_count:
        return
    track_x = content.x + content.width - 10
    track_y = content.y
    track_height = max(20, content.height)
    pygame.draw.rect(
        screen, pygame_ui.DEFAULT_PALETTE.border,
        pygame.Rect(track_x, track_y, 6, track_height), border_radius=3,
    )
    thumb_height = max(14, track_height * visible_count // total)
    _scroll = min(frame.selected, total - visible_count)
    thumb_y = track_y + (track_height - thumb_height) * _scroll // max(1, total - visible_count)
    pygame.draw.rect(
        screen, pygame_ui.DEFAULT_PALETTE.selected_border,
        pygame.Rect(track_x, thumb_y, 6, thumb_height), border_radius=3,
    )


def _draw_captured_rows(
    pygame: Any, screen: Any, font: Any, frame: QuestFrame, content: pygame_ui.Rect,
) -> None:
    """Paint captured row spans inside the clipped content region."""
    visible_count = max(1, content.height // font.get_linesize())
    _draw_quest_scrollbar(pygame, screen, frame, content, visible_count)
    screen.set_clip(pygame.Rect(content.x, content.y, content.width, content.height))
    try:
        start = max(0, min(len(frame.rows) - visible_count, frame.selected))
        for row_index, row in enumerate(frame.rows[start:start + visible_count]):
            x = content.x
            y = content.y + row_index * font.get_linesize()
            for span in row:
                pygame_ui.draw_text(
                    pygame, screen, font, span.text, x, y,
                    color=span.fg, antialias=True,
                )
                x += pygame_ui.measure_font(font, span.text)
    finally:
        screen.set_clip(None)


def _content_rect(
    pygame: Any, screen: Any, font: Any, frame: QuestFrame,
    palette: Any, panel: Any, width: int,
) -> pygame_ui.Rect:
    """Draw the shared tab bar when the frame carries sheets and
    return the content region below the header chrome."""
    if frame.tabs:
        from .pygame_screen import draw_tab_bar
        draw_tab_bar(
            pygame, screen, font, palette,
            frame.tabs, frame.active_tab, width, panel.y + 62,
        )
    return pygame_ui.Rect(
        panel.x + 34, panel.y + (106 if frame.tabs else 76),
        max(1, panel.width - 68),
        max(1, panel.height - (130 if frame.tabs else 100)),
    )


def _draw_rows(
    pygame: Any, screen: Any, font: Any, frame: QuestFrame,
    *, context: PygameContext | None = None,
) -> None:
    """Render captured rows inside the shared high-contrast panel treatment."""
    width, height = screen.get_size()
    palette = pygame_ui.DEFAULT_PALETTE
    panel_bottom = (
        pygame_ui.modal_footer_y(height)
        if context is not None else height - 28
    )
    panel = pygame_ui.Rect(32, 28, width - 64, max(1, panel_bottom - 28))
    pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
    pygame_ui.draw_centered_text(
        pygame, screen, font, "LOGS",
        panel, panel.y + 22,
        color=palette.title, antialias=True,
    )
    pygame_ui.draw_rule(
        pygame, screen, panel.x + 24, panel.y + 54,
        panel.width - 48, color=palette.border,
    )
    content = _content_rect(pygame, screen, font, frame, palette, panel, width)
    _draw_captured_rows(pygame, screen, font, frame, content)
    if frame.hint:
        hint_y = (
            pygame_ui.modal_footer_text_y(height, font.get_linesize() + 6)
            if context is not None else panel.y + panel.height - 48
        )
        pygame_ui.draw_centered_text(
            pygame, screen, font, frame.hint, panel, hint_y,
            color=palette.instruction, antialias=True,
        )


def _handle_key(
    pygame: Any, event: Any, selected: int, confirm: bool, count: int,
    pane: str,
) -> tuple[str, int, bool, str]:
    """Map key events to the Quest Log contract — the shared screen
    outcomes (TAB/SHIFT_TAB select the sheet, as on the character
    screen); the ledger scrolls instead of selecting. Returns
    ``(outcome, selected, confirm, pane)``; the caller advances."""
    if event.type == pygame.QUIT:
        return "QUIT", selected, confirm, pane
    if event.type != pygame.KEYDOWN:
        return "IGNORE", selected, confirm, pane
    if event.key == pygame.K_ESCAPE:
        return "BACK", selected, confirm, pane
    if event.key == getattr(pygame, "K_TAB", None):
        _shift = getattr(event, "mod", 0) & getattr(pygame, "KMOD_SHIFT", 0)
        return ("SHIFT_TAB" if _shift else "TAB"), selected, confirm, pane
    if pane == _RUMORS_PANE:
        if event.key in (pygame.K_UP, pygame.K_k):
            return "IGNORE", max(0, selected - 1), confirm, pane
        if event.key in (pygame.K_DOWN, pygame.K_j):
            return "IGNORE", selected + 1, confirm, pane
        return "IGNORE", selected, confirm, pane
    if not confirm and event.key in (pygame.K_UP, pygame.K_k) and count:
        return "IGNORE", (selected - 1) % count, confirm, pane
    if not confirm and event.key in (pygame.K_DOWN, pygame.K_j) and count:
        return "IGNORE", (selected + 1) % count, confirm, pane
    if event.key == pygame.K_a and not confirm and count:
        return "IGNORE", selected, True, pane
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and confirm and count:
        return "ABANDONED", selected, confirm, pane
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE", selected, confirm, pane
    return "IGNORE", selected, confirm, pane



def _advance_quest_log(outcome, selected, confirm, pane):
    """Advance one loop iteration — the character screen's shape:
    TAB/SHIFT_TAB flip the sheet (two sheets, both directions) and
    reset the selection. Returns ``(outcome, selected, confirm, pane,
    done)``."""
    if outcome in ("TAB", "SHIFT_TAB"):
        return outcome, 0, confirm, (
            _RUMORS_PANE if pane == _QUESTS_PANE else _QUESTS_PANE
        ), False
    return outcome, selected, confirm, pane, outcome != "IGNORE"


def _prepare_screen(context, ctx):
    """Bind the shared window (engine + surface), fit the font (quests
    frames drive the height; the scrolling ledger only width), and
    count the missions."""
    engine = getattr(getattr(context, "_runtime", None), "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameQuestLogUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    quests_frames, rumors_frames = _frames_for(ctx)
    if not quests_frames:
        raise PygameQuestLogUnavailable("Quest Log has no renderable frames")
    width, height = screen.get_size()
    font = _fit_font(
        pygame, quests_frames, width, height,
        extra_width_frames=rumors_frames,
    )
    return pygame, screen, engine, font, len(ctx.player_active_missions)


def run_shared(
    context: PygameContext,
    ctx: GameContext,
    selected: int = 0,
    confirm_abandon: bool = False,
) -> tuple[str, int, bool]:
    """Run the stateful Quest Log inside the existing shared window."""
    pygame, screen, engine, font, count = _prepare_screen(context, ctx)
    selected = selected if count else -1
    confirm = confirm_abandon
    pane = _QUESTS_PANE
    while True:
        frame = _capture_frame(ctx, selected, confirm, pane)
        if pane == _RUMORS_PANE:
            selected = min(selected, max(0, len(frame.rows) - 1))
        screen.fill(pygame_ui.DEFAULT_PALETTE.background)
        _draw_rows(pygame, screen, font, frame, context=context)
        pygame_ui.draw_context_log(pygame, screen, ctx.context)
        engine.present()
        event = pygame.event.wait()
        outcome, selected, confirm, pane = _handle_key(
            pygame, event, selected, confirm, count, pane,
        )
        outcome, selected, confirm, pane, done = _advance_quest_log(
            outcome, selected, confirm, pane,
        )
        if not done:
            continue
        return outcome, selected, confirm


def run_for_context(
    ctx: GameContext,
    selected: int = 0,
    confirm_abandon: bool = False,
) -> tuple[str, int, bool]:
    """Run Quest Log in the already-open shared Pygame window."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(ctx.context):
        raise PygameQuestLogUnavailable("Shared Pygame runtime is not open")
    return run_shared(ctx.context, ctx, selected, confirm_abandon)
