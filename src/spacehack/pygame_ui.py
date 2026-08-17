"""Reusable Pygame presentation primitives.

The module deliberately does not import Pygame at module load time. Layout
helpers are pure and remain testable without opening the game runtime;
drawing helpers receive the imported Pygame module explicitly.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .engine import MSG_LOG_HEIGHT, TILE_HEIGHT
from .game_context import GameContext
from .pygame_runtime import PygameContext


def presentation_enabled() -> bool:
    """Return whether the mandatory Pygame presentation is available."""
    return True


Color = tuple[int, int, int]
Measure = Callable[[str], int]


@dataclass(frozen=True)
class Rect:
    """Pixel rectangle used by the Pygame UI."""

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

# Modal screens reserve this bottom band for the live console log. Exploration
# The console log band is drawn identically in world and modal contexts
# (see draw_message_band): MSG_LOG_HEIGHT rows at TILE_HEIGHT each. Every
# modal reserves exactly this band so modal content never overlaps it.
LOG_PANEL_HEIGHT = MSG_LOG_HEIGHT * TILE_HEIGHT
# Clearance between modal footer/hint text and the top border of the console
# log panel. ``modal_footer_y`` is the BOTTOM boundary for footer text — no
# footer glyph may extend below it, so hints never touch the log border.
FOOTER_PAD = 30

# Row/detail caps for every selectable modal family (decision #8 in
# 15_DESIGN_UNIFIED_TERMINAL_UX.md): the shared font solver budgets at most
# this many selectable rows per list and this many wrapped detail lines, so
# rendered fonts stay catalog-independent instead of shrinking as lists grow.
# The viewport scrolls whatever exceeds the cap. EXPERIMENT: bumped from 10
# to 13 at the user's request ("3 more items before scrolling"). At a
# 1600x960 logical window the armory can no longer hold 13 rows at 24px, so
# its font drops to ~19px; revert to 10 to restore uniform 24px everywhere.
MAX_VISIBLE_ROWS = 13
MAX_DETAIL_LINES = 2


def fit_font(
    pygame: Any,
    path: str | None,
    *,
    measure_height: Callable[[Any], int],
    available_height: int,
) -> Any:
    """Choose the largest font (24px down to 11px) that fits the content.

    Single source of truth for the modal font ladder — every list family
    (split terminals, selectable menus, text screens) sizes its font through
    this one loop. Each family supplies its own pure ``measure_height``
    (font -> fitted pixel height) and ``available_height`` (pixel budget).
    """
    for size in range(24, 11, -1):
        font = pygame.font.Font(path, size)
        if measure_height(font) <= available_height:
            return font
    return pygame.font.Font(path, 12)


def visible_window(
    items: tuple[Any, ...],
    selected: int,
    cap: int,
    *,
    is_selectable: Callable[[Any], bool],
) -> tuple[int, int]:
    """Return the ``(top, count)`` viewport window centered on ``selected``.

    The window holds at most ``cap`` selectable items, widened to include
    adjacent non-selectable rows (section headers, dividers), and the
    selection is always inside it. An out-of-range selection clamps to the
    nearest selectable item; empty or all-non-selectable collections yield
    ``(0, 0)``.
    """
    indices = tuple(index for index, item in enumerate(items) if is_selectable(item))
    if not indices or cap <= 0:
        return 0, 0
    if selected not in indices:
        selected = min(indices, key=lambda index: abs(index - selected))
    position = indices.index(selected)
    start = max(0, min(position - cap // 2, len(indices) - cap))
    first = indices[start]
    last = indices[min(len(indices) - 1, start + cap - 1)]
    top = first
    while top > 0 and not is_selectable(items[top - 1]):
        top -= 1
    bottom = last + 1
    while bottom < len(items) and not is_selectable(items[bottom]):
        bottom += 1
    return top, bottom - top


def window_height(
    items: tuple[Any, ...],
    cap: int,
    *,
    is_selectable: Callable[[Any], bool],
    selectable_step: int,
    info_step: int,
) -> int:
    """Return the pixel height of the tallest capped viewport window.

    Used by the font solvers so the fitted height is the worst case across
    every scroll position — selection-independent and list-length-
    independent once the list exceeds the cap.
    """
    indices = tuple(index for index, item in enumerate(items) if is_selectable(item))
    if not indices or cap <= 0:
        return 0
    steps = [selectable_step if is_selectable(item) else info_step for item in items]
    return max(
        sum(steps[top:top + count])
        for position in range(len(indices))
        for top, count in (
            visible_window(items, indices[position], cap, is_selectable=is_selectable),
        )
    )


def _context_game_context(context: PygameContext) -> GameContext | None:
    """Return the live GameContext attached to a shared runtime, if any."""
    runtime = getattr(context, "_runtime", None)
    return getattr(runtime, "game_context", None)


def modal_footer_y(height: int) -> int:
    """Return the bottom boundary for footer text above the modal log panel.

    Footer/hint text must not extend below this line; the console-log panel's
    top border sits ``FOOTER_PAD`` pixels further down.
    """
    return max(0, height - LOG_PANEL_HEIGHT - FOOTER_PAD)


def modal_footer_text_y(height: int, line_height: int) -> int:
    """Return the y for one footer line whose bottom clears the log panel.

    ``line_height`` is the full block height below the returned y (glyph ink
    plus any extra margin); the line's bottom lands at ``modal_footer_y``.
    The clamp guards degenerate tiny-window sizes where the block exceeds the
    available space.
    """
    return max(0, modal_footer_y(height) - line_height)


def is_guide_key(pygame: Any, event: Any) -> bool:
    """Return whether a Pygame event represents the ``?`` key."""
    question = getattr(pygame, "K_QUESTION", None)
    return (
        event.type == getattr(pygame, "KEYDOWN", None)
        and (
            question is not None and event.key == question
            or getattr(event, "unicode", "") == "?"
        )
    )


def _font_path(pygame: Any) -> str | None:
    """Choose a readable monospace font.

    The bundled DejaVu Sans Mono wins so rendering is identical on every
    machine (and it is the only reliable source in frozen builds, where
    system font discovery may miss). System match_font is the fallback for
    editable installs that predate the bundled file.
    """
    bundled = Path(__file__).parent / "data" / "DejaVuSansMono.ttf"
    if bundled.is_file():
        return str(bundled)
    for family in ("DejaVu Sans Mono", "Liberation Mono", "Courier New"):
        path = pygame.font.match_font(family)
        if path:
            return path
    return None


def cell_font(pygame: Any, *, line_height: int) -> Any:
    """Choose the largest native font that fits one cell row.

    Shared by the world overlay and the modal console log so both bands
    render text at the same size (no size jump when a modal opens).
    """
    path = _font_path(pygame)
    for size in range(20, 9, -1):
        candidate = pygame.font.Font(path, size)
        if candidate.get_linesize() <= line_height:
            return candidate
    return pygame.font.Font(path, 10)


def log_band_rows(log: Any) -> tuple[tuple[str, tuple[int, int, int]], ...]:
    """Return the message-band rows as ``(text, fg)``, bottom-aligned.

    Single source of truth for the console-log band content, shared by
    the menu painter (:func:`draw_message_band`) and the exploration
    overlay (:mod:`spacehack.pygame_overlay`). Returns only the
    non-empty rows, in display order — painters place them on the
    bottom ``MSG_LOG_HEIGHT`` rows so a short log stays put when more
    entries arrive.
    """
    entries = log.recent(MSG_LOG_HEIGHT)
    rows: list[tuple[str, tuple[int, int, int]]] = []
    for entry in entries:
        if entry is None or not entry.text:
            continue
        rows.append(("> " + entry.text, tuple(entry.fg)))
    return tuple(rows)


def draw_message_band(
    pygame: Any,
    screen: Any,
    log: Any,
    *,
    palette: Palette = DEFAULT_PALETTE,
) -> None:
    """Paint the bottom console-log band exactly like the world overlay.

    Full-width panel, ``MSG_LOG_HEIGHT`` rows at ``TILE_HEIGHT`` each,
    messages bottom-aligned on cell rows with the shared cell font and
    12px side padding — the same geometry the world renderer produces,
    so log text never jumps when a modal opens. Content comes from
    :func:`log_band_rows`, the same builder the world overlay uses.
    """
    width, height = screen.get_size()
    band_height = MSG_LOG_HEIGHT * TILE_HEIGHT
    panel = Rect(0, max(0, height - band_height), width, band_height)
    draw_panel(pygame, screen, panel, palette=palette)
    font = cell_font(pygame, line_height=TILE_HEIGHT)
    rows = log_band_rows(log)
    measure = lambda text: measure_font(font, text)
    content_x = panel.x + 12
    content_width = max(1, panel.width - 24)
    # Bottom-aligned like the world capture: the newest entry sits on the
    # last band row, so a short log stays put when more entries arrive.
    top = panel.y + (MSG_LOG_HEIGHT - len(rows)) * TILE_HEIGHT
    clip = pygame.Rect(panel.x, panel.y, panel.width, panel.height)
    screen.set_clip(clip)
    try:
        for index, (line_text, color) in enumerate(rows):
            line = fit_text(line_text, content_width, measure)
            draw_text(
                pygame, screen, font, line,
                content_x, top + index * TILE_HEIGHT,
                color=color,
            )
    finally:
        screen.set_clip(None)


def draw_context_log(
    pygame: Any,
    screen: Any,
    context: PygameContext,
    *,
    palette: Palette = DEFAULT_PALETTE,
) -> None:
    """Paint the live console log in the reserved bottom band.

    Delegates to :func:`draw_message_band` so modals render the log
    identically to the world overlay.
    """
    game_context = _context_game_context(context)
    log = getattr(game_context, "log", None)
    if log is None:
        return
    draw_message_band(pygame, screen, log, palette=palette)


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


def max_wrapped_lines(texts: Any, max_width: int, measure: Measure) -> int:
    """Return the fixed line budget needed for a collection of descriptions."""
    return max(
        (len(wrap_text(text, max_width, measure)) for text in texts),
        default=0,
    )


def wrapped_text_height(
    text: str,
    max_width: int,
    measure: Measure,
    line_height: int,
    line_gap: int,
) -> int:
    """Return one wrapped block's pixel height, including an empty slot."""
    return max(1, len(wrap_text(text, max_width, measure))) * (line_height + line_gap)


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
    color: Color | None = None,
) -> int:
    """Render one selectable row and return its recommended next y.

    ``color`` overrides the default text colour (used by terminals that
    colour-code rows, e.g. trade demand/surplus cues). The colour is
    kept even when selected so the cue survives navigation.
    """
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
        color=color if color is not None else (palette.text if not selected else palette.title),
        antialias=antialias,
    )
    return y + row_height


def draw_informational_row(
    pygame: Any,
    screen: Any,
    font: Any,
    label: str,
    x: int,
    y: int,
    width: int,
    *,
    color: Color = DEFAULT_PALETTE.description,
    antialias: bool = True,
) -> int:
    """Render a muted non-selectable row with menu-row geometry."""
    row_height = font.get_linesize() + 14
    marker = "  "
    measure = lambda value: measure_font(font, value)
    fitted_label = fit_text(label, width - measure(marker), measure)
    draw_text(
        pygame, screen, font, marker + fitted_label,
        x + 12, y + 2,
        color=color,
        antialias=antialias,
    )
    return y + row_height


# ---------------------------------------------------------------------------
# Shared modal content conventions (single source of truth)
# ---------------------------------------------------------------------------
# Every modal family (split terminals, text screens, menus, merchant board)
# formats its titles, prices, stats, rewards, and hints through these pure
# helpers, so a global change (e.g. a bigger title font or a "Credits:"
# relabel) is exactly one edit (see 15_DESIGN_UNIFIED_TERMINAL_UX.md).

HINT_SEP = "   "

# Canonical modal phrases (single source of truth — decision #4 in
# 15_DESIGN_UNIFIED_TERMINAL_UX.md): every modal hint navigates with the
# same phrase, and ``GUIDE_HINT`` is advertised only where the modal's
# runner actually opens the in-game guide on the ``?`` key (the key
# itself works in every family via :func:`is_guide_key`).
NAV_HINT = "UP/DOWN navigate"
GUIDE_HINT = "? guide"


def terminal_title(prefix: str, suffix: str = "") -> str:
    """Return the all-caps ``PREFIX - SUFFIX`` title, or bare ``PREFIX``.

    Single source of truth for modal title grammar: every buy/sell
    terminal title routes through this helper.
    """
    prefix = prefix.upper()
    if not suffix:
        return prefix
    return f"{prefix} - {suffix.upper()}"


def price_cell(price: int, qty: int | None = None) -> str:
    """Format a buy price cell: ``30$`` or ``30$ (12)`` with a qty shown."""
    cell = f"{price}$"
    if qty is not None:
        cell += f" ({qty})"
    return cell


def sell_cell(price: int, qty: int | None = None) -> str:
    """Format a sell-back cell: ``(sell 15$)`` or ``(sell 15$) x2``."""
    cell = f"(sell {price}$)"
    if qty is not None:
        cell += f" x{qty}"
    return cell


def credits_label(credits: int) -> str:
    """Format the credits footer line: ``Credits: 1000$``."""
    return f"Credits: {credits}$"


def cargo_label(used: int, max_cargo: int) -> str:
    """Format the cargo footer line: ``Cargo: 12/50``."""
    return f"Cargo: {used}/{max_cargo}"


def shortfall_label(short: int) -> str:
    """Format an affordability shortfall: ``3000$ short``."""
    return f"{short}$ short"


def reward_label(credits: int, xp: int) -> str:
    """Format a mission reward line: ``Reward: 400$ + 50xp``."""
    return f"Reward: {credits}$ + {xp}xp"


def modal_hint(*parts: str) -> str:
    """Join hint parts with the canonical separator, dropping trailing dots.

    Single source of truth for hint grammar across every modal family:
    ``modal_hint(NAV_HINT, "ENTER select", "ESC back", GUIDE_HINT)``
    → ``"UP/DOWN navigate   ENTER select   ESC back   ? guide"``.
    """
    return HINT_SEP.join(part.rstrip(".").strip() for part in parts)
