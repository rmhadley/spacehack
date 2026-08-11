"""Reusable Pygame presentation primitives.

The module deliberately does not import Pygame at module load time. Layout
helpers are pure and remain testable without opening the game runtime;
drawing helpers receive the imported Pygame module explicitly.
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
    """Raised when a Pygame worker cannot return a result."""


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


def presentation_enabled() -> bool:
    """Return whether the mandatory Pygame presentation is available."""
    return True


def worker_environment() -> dict[str, str]:
    """Return the environment used by isolated Pygame workers."""
    return {**os.environ, "PYGAME_HIDE_SUPPORT_PROMPT": "1"}


def worker_command(module: str) -> list[str]:
    """Build a worker command for the current Python environment."""
    return [sys.executable, "-m", module, "--worker"]


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
# already renders the log through pygame_overlay, so this is only for modal
# presentation primitives.
LOG_ROWS = 6
LOG_PANEL_HEIGHT = 128
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


def _context_game_context(context: Any) -> Any | None:
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


def _log_font(pygame: Any) -> Any:
    """Load the compact readable font used by modal console logs."""
    from .pygame_merchant import _font_path

    return pygame.font.Font(_font_path(pygame), 16)


def draw_context_log(
    pygame: Any,
    screen: Any,
    context: Any,
    *,
    palette: Palette = DEFAULT_PALETTE,
) -> None:
    """Paint the live console log in the reserved bottom modal band."""
    game_context = _context_game_context(context)
    log = getattr(game_context, "log", None)
    if log is None:
        return
    width, height = screen.get_size()
    panel = Rect(32, max(0, height - LOG_PANEL_HEIGHT), width - 64, LOG_PANEL_HEIGHT)
    draw_panel(pygame, screen, panel, palette=palette)
    font = _log_font(pygame)
    draw_text(
        pygame, screen, font, "CONSOLE LOG", panel.x + 20, panel.y + 10,
        color=palette.title,
    )
    draw_rule(
        pygame, screen, panel.x + 18, panel.y + 34,
        panel.width - 36, color=palette.border,
    )
    entries = log.recent(LOG_ROWS)
    measure = lambda text: measure_font(font, text)
    content_width = panel.width - 40
    for index, entry in enumerate(entries):
        line = fit_text("> " + entry.text, content_width, measure)
        draw_text(
            pygame, screen, font, line,
            panel.x + 20,
            panel.y + 42 + index * (font.get_linesize() + 1),
            color=entry.fg,
        )


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
