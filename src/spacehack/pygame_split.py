"""Pygame presentation for two-panel split-screen terminals.

The game process owns all domain state and supplies presentation snapshots;
the shared runtime returns an opaque panel/action selection.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections.abc import Callable
from typing import Any

from . import pygame_menu, pygame_ui
from .game_context import GameContext
from .pygame_runtime import PygameContext


class PygameSplitUnavailable(RuntimeError):
    """Raised when the split-screen presentation cannot return."""


def enabled() -> bool:
    """Return whether split screens can render in this runtime."""
    return pygame_ui.presentation_enabled()


@dataclass(frozen=True)
class SplitRow:
    """One selectable or divider row in a split panel."""

    label: str
    value: str
    detail: str
    action: str
    divider: bool = False
    selectable: bool = True


@dataclass(frozen=True)
class SplitFrame:
    """Presentation-only state for one split-screen terminal."""

    title: str
    left_label: str
    right_label: str
    left_rows: tuple[SplitRow, ...]
    right_rows: tuple[SplitRow, ...]
    footer_left: str
    footer_right: str
    hint: str
    focus: int = 0
    selected: int = 0
    # Optional two-choice header tabs used by terminals such as ship loadout.
    # Empty preserves the original single-label panel header.
    left_tabs: tuple[str, ...] = ()
    active_left_tab: int = 0
    # Optional explicit mode outcomes for each left tab. Empty preserves
    # legacy label-based mappings used by existing terminals.
    left_tab_modes: tuple[str, ...] = ()


def _rows(frame: SplitFrame) -> tuple[SplitRow, ...]:
    """Return the currently focused row collection."""
    return frame.left_rows if frame.focus == 0 else frame.right_rows


def _selectable_indices(rows: tuple[SplitRow, ...]) -> tuple[int, ...]:
    """Return row indices that can produce an action."""
    return tuple(
        index for index, row in enumerate(rows)
        if not row.divider and row.selectable and bool(row.action)
    )


# Row/detail caps for the fit solver + viewport — shared single source of
# truth in pygame_ui (see 15_DESIGN_UNIFIED_TERMINAL_UX.md decision #8).
MAX_VISIBLE_ROWS = pygame_ui.MAX_VISIBLE_ROWS
MAX_DETAIL_LINES = pygame_ui.MAX_DETAIL_LINES

# Pinned-detail geometry (decision #7 experiment): the focused panel's
# description is anchored this many px above the panel bottom, with a
# small gap between the last row and the description.
DETAIL_BOTTOM_PAD = 8
ROWS_DETAIL_GAP = 6

# Indent applied to selectable/informational rows when a panel has section
# headers, so content reads as one level below the divider headings.
CONTENT_INDENT = 24

# Canonical hint for every split buy/sell terminal (single source of
# truth — see 15_DESIGN_UNIFIED_TERMINAL_UX.md). Advertises "? guide":
# the ? key works in every modal via pygame_ui.is_guide_key, and the
# split runner opens the guide on the GUIDE outcome (Phase 5 decision).
SPLIT_SHOP_HINT = pygame_ui.modal_hint(
    "UP/DOWN navigate", "TAB switch panel", "ENTER buy/sell",
    "ESC back", pygame_ui.GUIDE_HINT,
)


def section_header(label: str) -> SplitRow:
    """Build a divider row for a labeled list section (``--- WEAPONS ---``)."""
    return SplitRow(f"--- {label} ---", "", "", "", divider=True)


def _visible_window(
    rows: tuple[SplitRow, ...], selected: int, cap: int = MAX_VISIBLE_ROWS,
) -> tuple[int, int]:
    """Return the ``(top, count)`` viewport window centered on ``selected``.

    Delegates to the shared :func:`pygame_ui.visible_window`; every
    selectable row is eligible and dividers are the non-selectable rows
    the window is widened to include.
    """
    return pygame_ui.visible_window(
        rows, selected, cap, is_selectable=lambda row: not row.divider,
    )


def _clamp_selected(frame: SplitFrame) -> int:
    """Clamp selection to a selectable row, or zero for an empty panel."""
    indices = _selectable_indices(_rows(frame))
    if not indices:
        return 0
    if frame.selected in indices:
        return frame.selected
    return min(indices, key=lambda index: abs(index - frame.selected))


def _content_width(width: int) -> int:
    """Return usable width for each panel."""
    return max(1, (width - 132) // 2)


def _frame_height(font: Any, frame: SplitFrame) -> int:
    """Measure the split frame for font fitting.

    Row and detail counts are capped (``MAX_VISIBLE_ROWS`` /
    ``MAX_DETAIL_LINES``) so the height — and therefore the rendered font
    size — no longer depends on catalog size.
    """
    line = font.get_linesize()
    # Reserve the full capped viewport for every frame, even when the
    # current tab has only a few rows. Without this stable budget, switching
    # between a dense Buy catalog and a sparse Storage view refits the font
    # to different heights and causes an abrupt size jump.
    row_height = MAX_VISIBLE_ROWS * (line + 14)
    divider_height = 2 * (line + 5)
    detail_height = MAX_DETAIL_LINES * (line + 2)
    return 150 + row_height + divider_height + detail_height


def _fit_font(pygame: Any, frame: SplitFrame, width: int, height: int) -> Any:
    """Choose the largest readable font that fits the split frame and log."""
    path = pygame_menu._font_path(pygame)
    # Budget = modal_footer_y - 80: mirrors the real panel bottom (footer
    # block of 2 lines + 20px, then a small pad) so the solver accepts the
    # same content the renderer can actually draw. The old -120 left ~70px
    # of empty panel and made lists scroll a row sooner than needed.
    return pygame_ui.fit_font(
        pygame, path,
        measure_height=lambda font: _frame_height(font, frame),
        available_height=max(1, pygame_ui.modal_footer_y(height) - 80),
    )


def _draw_panel(
    pygame: Any,
    screen: Any,
    font: Any,
    frame: SplitFrame,
    rows: tuple[SplitRow, ...],
    *,
    panel: pygame_ui.Rect,
    label: str,
    selected: int,
    focused: bool,
    tabs: tuple[str, ...] = (),
    active_tab: int = 0,
) -> None:
    """Draw one panel and its currently selected detail."""
    palette = pygame_ui.DEFAULT_PALETTE
    pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
    _draw_panel_header(pygame, screen, font, panel, label, focused, tabs, active_tab, palette)
    screen.set_clip(
        pygame.Rect(
            panel.x + 1, panel.y + 1,
            max(1, panel.width - 2), max(1, panel.height - 2),
        )
    )
    try:
        _draw_panel_rows(pygame, screen, font, panel, rows, selected, focused, palette)
    finally:
        screen.set_clip(None)


def _draw_panel_header(
    pygame: Any, screen: Any, font: Any, panel: pygame_ui.Rect,
    label: str, focused: bool, tabs: tuple[str, ...], active_tab: int, palette: Any,
) -> None:
    """Paint a panel's tab header and its divider rule."""
    header_labels = tabs or (label,)
    header_x = panel.x + 20
    measure = lambda text: pygame_ui.measure_font(font, text)
    for tab_index, tab_label in enumerate(header_labels):
        tab_width = measure(tab_label) + 24
        tab_active = tab_index == active_tab
        if tabs and tab_active:
            highlight = pygame.Rect(
                header_x - 8, panel.y + 8, tab_width, font.get_linesize() + 10,
            )
            pygame.draw.rect(screen, palette.selected_background, highlight, border_radius=3)
            pygame.draw.rect(screen, palette.selected_border, highlight, width=1, border_radius=3)
        pygame_ui.draw_text(
            pygame, screen, font, tab_label, header_x, panel.y + 18,
            color=palette.title if tab_active and focused else palette.description,
        )
        header_x += tab_width + 10
    pygame_ui.draw_rule(
        pygame, screen, panel.x + 18, panel.y + 48,
        panel.width - 36, color=palette.border,
    )


def _detail_geometry(panel: pygame_ui.Rect, y: int, detail_height: int, detail: str) -> tuple[int, int]:
    """Return ``(detail_y, rows_bottom)`` for the pinned detail description."""
    if detail:
        detail_y = panel.y + panel.height - detail_height - DETAIL_BOTTOM_PAD
        return detail_y, detail_y - ROWS_DETAIL_GAP
    return y, panel.y + panel.height


def _draw_panel_row(
    pygame: Any, screen: Any, font: Any, panel: pygame_ui.Rect, row: SplitRow,
    index: int, selected: int, focused: bool, x: int, content_x: int,
    content_width: int, y: int, measure: Any, palette: Any,
) -> int:
    """Draw one divider, informational, or selectable row; return new y."""
    if row.divider:
        pygame_ui.draw_text(
            pygame, screen, font,
            pygame_ui.fit_text(row.label, panel.width - 40, measure),
            x, y, color=palette.description,
        )
        return y + font.get_linesize() + 5
    if not row.selectable or not row.action:
        return pygame_ui.draw_informational_row(
            pygame, screen, font, row.label,
            content_x, y, content_width,
            color=palette.description,
        )
    selected_row = focused and index == selected
    return pygame_ui.draw_menu_row(
        pygame, screen, font,
        f"{row.label}  {row.value}".rstrip(),
        content_x, y, content_width,
        selected=selected_row,
        palette=palette,
    )


def _draw_panel_rows(
    pygame: Any, screen: Any, font: Any, panel: pygame_ui.Rect,
    rows: tuple[SplitRow, ...], selected: int, focused: bool, palette: Any,
) -> None:
    """Draw the panel's rows and its pinned detail description."""
    x = panel.x + 20
    y = panel.y + 66
    measure = lambda text: pygame_ui.measure_font(font, text)
    detail = ""
    if focused and 0 <= selected < len(rows) and not rows[selected].divider:
        detail = rows[selected].detail
    detail_width = panel.width - 68
    indent = CONTENT_INDENT if any(row.divider for row in rows) else 0
    content_x = x + indent
    content_width = panel.width - 40 - indent
    step = font.get_linesize() + 2
    detail_height = max(
        1, len(pygame_ui.wrap_text(detail, detail_width, measure)),
    ) * step
    detail_y, rows_bottom = _detail_geometry(panel, y, detail_height, detail)
    viewport_selected = selected if focused else 0
    top, count = _visible_window(rows, viewport_selected, MAX_VISIBLE_ROWS)
    for index in range(top, top + count):
        if y >= rows_bottom:
            break
        y = _draw_panel_row(
            pygame, screen, font, panel, rows[index],
            index, selected, focused, x, content_x, content_width, y, measure, palette,
        )
    pygame_ui.draw_wrapped_text(
        pygame, screen, font, detail,
        x + 28, detail_y, detail_width,
        color=palette.description, line_gap=2,
    )


def _draw_frame(
    pygame: Any, screen: Any, font: Any, frame: SplitFrame,
    *, context: PygameContext | None = None,
) -> None:
    """Paint the split-screen frame."""
    width, height = screen.get_size()
    screen.fill(pygame_ui.DEFAULT_PALETTE.background)
    _draw_frame_header(pygame, screen, font, frame, width)
    left, right, footer_y, hint_y = _layout_panels(font, width, height, context)
    selected = _clamp_selected(frame)
    _draw_panel(
        pygame, screen, font, frame, frame.left_rows,
        panel=left, label=frame.left_label, selected=selected,
        focused=frame.focus == 0,
        tabs=frame.left_tabs,
        active_tab=frame.active_left_tab,
    )
    _draw_panel(
        pygame, screen, font, frame, frame.right_rows,
        panel=right, label=frame.right_label, selected=selected,
        focused=frame.focus == 1,
    )
    _draw_frame_footer(pygame, screen, font, frame, width, footer_y, hint_y)
    if context is not None:
        pygame_ui.draw_context_log(pygame, screen, context)


def _draw_frame_header(pygame: Any, screen: Any, font: Any, frame: SplitFrame, width: int) -> None:
    """Paint the centered title and its divider rule."""
    title_rect = pygame_ui.Rect(32, 20, width - 64, 44)
    pygame_ui.draw_centered_text(
        pygame, screen, font, frame.title, title_rect, 24,
        color=pygame_ui.DEFAULT_PALETTE.title,
    )
    pygame_ui.draw_rule(
        pygame, screen, 56, 62, width - 112,
        color=pygame_ui.DEFAULT_PALETTE.border,
    )


def _layout_panels(
    font: Any, width: int, height: int, context: PygameContext | None,
) -> tuple[pygame_ui.Rect, pygame_ui.Rect, int, int]:
    """Return panel rects and footer/hint baselines for a split frame."""
    gap = 20
    panel_width = (width - 64 - gap) // 2
    if context is not None:
        # Panels end above the footer block; the footer and hint lines sit
        # between the panels and the console-log boundary (modal_footer_y)
        # so no glyph ever touches the log panel border.
        footer_block = font.get_linesize() * 2 + 20
        panel_bottom = pygame_ui.modal_footer_y(height) - footer_block
        footer_y = panel_bottom + 6
        hint_y = footer_y + font.get_linesize() + 8
    else:
        panel_bottom = height - 34
        footer_y = height - 58
        hint_y = height - 34
    panel_height = max(1, panel_bottom - 78)
    left = pygame_ui.Rect(32, 78, panel_width, panel_height)
    right = pygame_ui.Rect(32 + panel_width + gap, 78, panel_width, panel_height)
    return left, right, footer_y, hint_y


def _draw_frame_footer(
    pygame: Any, screen: Any, font: Any, frame: SplitFrame,
    width: int, footer_y: int, hint_y: int,
) -> None:
    """Paint the footer labels and the hint line."""
    pygame_ui.draw_text(
        pygame, screen, font, frame.footer_left, 40, footer_y,
        color=pygame_ui.DEFAULT_PALETTE.text,
    )
    footer_width = pygame_ui.measure_font(font, frame.footer_right)
    pygame_ui.draw_text(
        pygame, screen, font, frame.footer_right,
        width - footer_width - 40, footer_y,
        color=pygame_ui.DEFAULT_PALETTE.text,
    )
    pygame_ui.draw_text(
        pygame, screen, font,
        pygame_ui.fit_text(frame.hint, width - 80, lambda value: pygame_ui.measure_font(font, value)),
        40, hint_y,
        color=pygame_ui.DEFAULT_PALETTE.instruction,
    )


_TAB_MODE_DEFAULTS = {
    "[B]uy": "STORE",
    "[S]torage": "STORAGE",
    "[A]rmory": "ARMORY",
    "[E]xpedition": "EXPEDITION",
}


def _tab_modes(pygame: Any, frame: SplitFrame) -> dict[Any, str]:
    """Map each bracketed left-tab key to its target mode."""
    return {
        getattr(pygame, f"K_{label[1].lower()}", None): (
            frame.left_tab_modes[index]
            if index < len(frame.left_tab_modes)
            else _TAB_MODE_DEFAULTS.get(label, label[1].upper())
        )
        for index, label in enumerate(frame.left_tabs)
        if len(label) > 1 and label.startswith("[")
    }


def _handle_key(pygame: Any, event: Any, frame: SplitFrame) -> tuple[str, int, int]:
    """Map a worker key to ``(outcome, focus, selected)``."""
    selected = _clamp_selected(frame)
    indices = _selectable_indices(_rows(frame))
    if event.type == pygame.QUIT:
        return "QUIT", frame.focus, selected
    if event.type != pygame.KEYDOWN:
        return "IGNORE", frame.focus, selected
    if event.key == pygame.K_ESCAPE:
        return "BACK", frame.focus, selected
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE", frame.focus, selected
    if frame.left_tabs:
        requested = _tab_modes(pygame, frame).get(event.key)
        if requested is not None:
            return f"MODE:{requested}", frame.focus, selected
    if event.key == pygame.K_TAB:
        other = replace(frame, focus=1 - frame.focus, selected=0)
        return "IGNORE", other.focus, _clamp_selected(other)
    if event.key in (pygame.K_UP, pygame.K_k) and indices:
        position = indices.index(selected)
        return "IGNORE", frame.focus, indices[(position - 1) % len(indices)]
    if event.key in (pygame.K_DOWN, pygame.K_j) and indices:
        position = indices.index(selected)
        return "IGNORE", frame.focus, indices[(position + 1) % len(indices)]
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and indices:
        return "SELECT", frame.focus, selected
    return "IGNORE", frame.focus, selected


def run_shared(
    context: PygameContext,
    frame: SplitFrame,
    *,
    caption: str = "spacehack - terminal",
) -> tuple[str, str, int, int]:
    """Run one split frame inside the already-open shared Pygame window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameSplitUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    width, height = screen.get_size()
    font = _fit_font(pygame, frame, width, height)
    while True:
        current = replace(frame, selected=_clamp_selected(frame))
        _draw_frame(pygame, screen, font, current, context=context)
        engine.present()
        event = pygame.event.wait()
        outcome, focus, selected = _handle_key(pygame, event, current)
        if outcome == "IGNORE":
            frame = replace(frame, focus=focus, selected=selected)
            continue
        rows = _rows(current)
        action = rows[selected].action if outcome == "SELECT" else ""
        return outcome, action, focus, selected


def _build_frame(build_frame: Callable[[], SplitFrame], *, rebuilt: bool = False) -> SplitFrame:
    """Call the frame builder, translating build errors into a fallback."""
    label = "rebuilt" if rebuilt else "built"
    try:
        return build_frame()
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        raise PygameSplitUnavailable(f"Pygame split frame could not be {label}") from exc


def _apply_keep_open(
    apply_action: Callable[[str, int, int], bool],
    outcome: str, action: str, focus: int, selected: int,
) -> bool:
    """Apply one selection and report whether the terminal stays open."""
    try:
        return apply_action(
            action if outcome == "SELECT" else outcome,
            focus,
            selected,
        )
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        raise PygameSplitUnavailable("Pygame split frame could not be rebuilt") from exc


def run_interactive(
    ctx: GameContext,
    build_frame: Callable[[], SplitFrame],
    apply_action: Callable[[str, int, int], bool],
    *,
    caption: str,
) -> str:
    """Repeat split selections while the parent applies domain actions.

    ``build_frame`` and ``apply_action`` execute in the game process; the
    worker never receives mutable game state. ``apply_action`` returns True
    when the terminal should remain open after the mutation.
    """
    if not _shared_runtime_enabled(ctx):
        raise PygameSplitUnavailable("Shared Pygame runtime is not open")
    frame = _build_frame(build_frame)
    focus = frame.focus
    selected = frame.selected
    while True:
        frame = replace(frame, focus=focus, selected=selected)
        outcome, action, focus, selected = run_shared(
            ctx.context, frame, caption=caption,
        )
        if outcome == "GUIDE":
            from .help import _run_help_guide
            _run_help_guide(ctx)
            frame = _build_frame(build_frame, rebuilt=True)
            continue
        if outcome == "SELECT" or outcome.startswith("MODE:"):
            keep_open = _apply_keep_open(apply_action, outcome, action, focus, selected)
            if keep_open:
                frame = _build_frame(build_frame, rebuilt=True)
                continue
            return "BACK"
        return outcome


def _shared_runtime_enabled(ctx: GameContext) -> bool:
    """Return whether this process owns the shared Pygame window."""
    from . import pygame_runtime

    return pygame_runtime.is_shared_context(getattr(ctx, "context", None))


