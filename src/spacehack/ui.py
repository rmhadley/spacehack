"""In-game UI primitives: menu rendering and input for the
character-creation screens.

This module is deliberately tiny and library-agnostic - it draws a
single centered vertical menu onto an existing ``tcod.console.Console``
and translates key events into menu actions. Higher-level state
sachines (species -> class -> confirm) live in :mod:`spacehack.__main__`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .data.species import list_species
from .data.classes import list_classes
from . import pygame_ui

# High-contrast sci-fi palette for a black background. Normal reading text
# stays neutral or warm-white; color is reserved for hierarchy and state so
# users do not have to decode a dark blue paragraph against black.
COLOR_TITLE: tuple[int, int, int] = (205, 250, 255)              # near-white cyan heading
COLOR_INSTRUCTION: tuple[int, int, int] = (255, 240, 175)        # bright warm hint
COLOR_OPTION: tuple[int, int, int] = (255, 255, 250)             # near-white body text
COLOR_OPTION_HIGHLIGHT: tuple[int, int, int] = (255, 255, 255)   # pure white
COLOR_OPTION_HIGHLIGHT2: tuple[int, int, int] = (220, 250, 255)  # pale cyan accent
COLOR_DESCRIPTION: tuple[int, int, int] = (245, 245, 235)        # bright secondary text
# Value cells (numbers, prices) - kept here so dialogs in __main__
# (e.g. the ship-buy modal) can use the same near-white/dim pair.
COLOR_VALUE_WHITE: tuple[int, int, int] = (255, 255, 255)        # pure white
COLOR_VALUE_DIM: tuple[int, int, int] = (230, 230, 225)           # bright secondary value

# Unified screen-header rule. Single source of truth for the divider
# drawn under every menu title — change these and every screen follows.
DIVIDER_CHAR: str = "="                       # CP437-safe rule char
COLOR_DIVIDER: tuple[int, int, int] = (190, 190, 185)  # visible neutral rule
COLOR_SPLASH_BORDER: tuple[int, int, int] = (205, 205, 200)   # title-frame neutral
COLOR_SPLASH_ART: tuple[int, int, int] = (205, 250, 255)      # title cyan
COLOR_SPLASH_FLAVOR: tuple[int, int, int] = (245, 245, 235)   # title body text
COLOR_SPLASH_PROMPT: tuple[int, int, int] = (255, 240, 175)   # title instruction

class MenuAction(Enum):
    """What a single key event means for a menu screen."""
    NONE = auto()     # no menu-level action (e.g. UP/DOWN navigation)
    CONFIRM = auto()  # user pressed Enter (RETURN/ENTER/KP_ENTER/KP_5)
    BACK = auto()     # user pressed ESC

@dataclass
class MenuScreen:
    """A single centered vertical menu.

    ``options`` is a tuple of ``(id, label)`` pairs. ``descriptions``
    maps each id -> a longer flavor-text line shown below the list.
    """
    title: str
    instruction: str
    options: tuple[tuple[str, str], ...]
    descriptions: dict[str, str]
    selected: int = 0

    @property
    def selected_id(self) -> str:
        return self.options[self.selected][0]

def species_menu() -> MenuScreen:
    """Build the species-choices menu screen."""
    return MenuScreen(
        title="Choose Your Species",
        instruction=pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER select", "ESC start over",
        ),
        options=tuple((s.id, s.name) for s in list_species()),
        descriptions={s.id: s.description for s in list_species()},
        selected=0,
    )

def class_menu() -> MenuScreen:
    """Build the class-choices menu screen."""
    return MenuScreen(
        title="Choose Your Class",
        instruction=pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER select", "ESC go back",
        ),
        options=tuple((c.id, c.name) for c in list_classes()),
        descriptions={c.id: c.description for c in list_classes()},
        selected=0,
    )

# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def centered_x(text: str, screen_width: int) -> int:
    """Column index that horizontally centers ``text`` in the given width."""
    return max(0, (screen_width - len(text)) // 2)

def paint_rect_border(
    console,
    rect: tuple[int, int, int, int],
    *,
    fg: tuple[int, int, int],
    char: str = "+",
) -> None:
    """Paint a simple ASCII rectangle border into ``console``.

    ``rect = (x, y, width, height)`` -- ``(x, y)`` is the TOP-LEFT
    corner. The border is drawn with ``char`` (default ``+``) and
    ``fg``. Corners share the same char. Used by the map-modal
    Areas-of-Interest panel so the player can scan its scope
    visually.

    Interiors are NOT cleared -- this is a pure border overlay
    so the caller can paint content inside the rect freely.
    """
    x, y, w, h = rect
    if w < 2 or h < 2:
        return                                       # nothing to draw.
    # Top + bottom rows.
    console.print(x=x,         y=y,         string=char * w, fg=fg)
    console.print(x=x,         y=y + h - 1, string=char * w, fg=fg)
    # Left + right columns.
    for yy in range(y + 1, y + h - 1):
        console.print(x=x,         y=yy, string=char, fg=fg)
        console.print(x=x + w - 1, y=yy, string=char, fg=fg)

def wrap_text(text: str, max_width: int) -> list[str]:
    """Split ``text`` into wrapped lines fitting ``max_width`` chars.

    Preserves intentional line breaks: ``\n`` creates a new line,
    ``\n\n`` creates a blank line (paragraph break).  Within each
    paragraph, word-wrap is greedy: each line fits as many words as
    possible without exceeding ``max_width``. A single word longer
    than ``max_width`` goes on its own line rather than being split
    mid-word (so a long quest title never loses a chunk of itself
    to an overflow cut).

    Empty / whitespace-only input returns an empty list so callers
    can use ``if wrap_text(...):`` to gate painting cleanly without
    nil-conditional branching.
    """
    if max_width < 1 or not text or not text.strip():
        return []
    # Split into paragraphs first so intentional ``\n`` breaks are
    # preserved (old behaviour collapsed ALL whitespace via split()).
    paragraphs = text.split("\n")
    lines: list[str] = []
    for para in paragraphs:
        if not para.strip():
            # Empty paragraph = empty line (visual paragraph break).
            lines.append("")
            continue
        words = para.split()
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    # Strip trailing blank lines so a final ``\n`` doesn't add
    # unwanted whitespace at the end of the wrapped output.
    while lines and not lines[-1]:
        lines.pop()
    return lines

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Title splash screen
# ---------------------------------------------------------------------------

# SPACEHACK in 7-wide x 5-tall block letters (71 chars per row).
_TITLE_ART: tuple[str, ...] = (
    "####### #######  #####   #####  ####### ##   ##  #####   #####  ##   ##",
    "##      ##   ## ##   ## ##   ## ##      ##   ## ##   ## ##   ## ##  ## ",
    "####### ####### ####### ##      #####   ####### ####### ##      #####  ",
    "     ## ##   ## ##   ## ##   ## ##      ##   ## ##   ## ##   ## ##  ## ",
    "####### ##   ## ##   ##  #####  ####### ##   ## ##   ##  #####  ##   ##",
)

# Detailed spaceship, 18 wide x 15 tall. Each row padded to exactly 18 chars.
# Hull uses CP437 box-drawing (\u2502\u2500) matching planet style.
# Nose keeps ASCII /\ (no CP437 diagonal available). Flame/smoke uses '`.-;().
_SHIP_ART: tuple[str, ...] = (
    "    /\\            ",   # 0  nose tip         (4+2+12=18)
    "   /  \\           ",   # 1  nose cone        (3+4+11=18)
    "  \u2502    \u2502          ",   # 2  hull             (2+6+10=18)
    "  \u2502    \u2502          ",   # 3  hull
    "  \u2502    \u2502          ",   # 4  hull
    "  \u2502    \u2502          ",   # 5  hull
    "  \u2502    \u2502          ",   # 6  hull
    "\u250c'      '\u2510        ",   # 7  engine mount     (2+6+2+8=18)
    " \u2502      \u2502        ",    # 8  engine           (1+8+9=18)
    " \u2502      \u2502        ",    # 9  engine
    " \u2502\u2500\u2500\u2500\u2500\u2500\u2500\u2502        ",    # 10 engine base      (1+8+9=18)
    "  '\u2500`'\u2500`   .     ",    # 11 flame core       (2+10+6=18)
    "  / . \\'\\ . .'    ", # 12 flame             (2+12+4=18)
    " ''( .'\\'.' ' .;'  ", # 13 smoke             (1+15+2=18)
    "'.;.;' ;'.;' ..;;'",   # 14 smoke             (18, unpadded)
)

# ---------------------------------------------------------------------------
# Title menu (after splash screen)
# ---------------------------------------------------------------------------

class TitleMenuOutcome(Enum):
    """Terminal outcomes for the title menu."""
    NEW_GAME = auto()
    CONTINUE = auto()
    TUTORIAL = auto()
    EXIT = auto()
    IGNORE = auto()

# ---------------------------------------------------------------------------
# Title splash screen
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Modal helper
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Shared split-screen primitives (used by trade.py and the loadout UI)
# ---------------------------------------------------------------------------

def fit_text(text: str, max_w: int) -> str:
    """Truncate ``text`` to ``max_w`` columns, appending ``…`` when cut.

    Shared by the terminal-look menu family (mission board, quest log,
    NPC talk, ship buy) so the truncation behaviour lives in one place.
    """
    return text if len(text) <= max_w else text[:max_w - 1] + "..."

def paint_title(console, screen_width: int, row: int, text: str, *, fg) -> None:
    """Print ``text`` horizontally centered at ``row`` — the terminal-look
    title row shared by every menu screen."""
    console.print(x=centered_x(text, screen_width), y=row, string=text, fg=fg)

def paint_line(console, x: int, y: int, text: str, *, fg) -> None:
    """Print ``text`` left-anchored at ``(x, y)`` — terminal-look content."""
    console.print(x=x, y=y, string=text, fg=fg)

def screen_header(
    console,
    screen_width: int,
    title: str,
    *,
    fg=COLOR_TITLE,
    row: int = 2,
    divider_x: int = 2,
    divider_w: int | None = None,
) -> int:
    """Paint the unified screen header: centered title + divider rule.

    Returns the first content row (``row + 3``) so callers anchor
    content one blank row below the divider — the header's breathing
    room.  Every full-screen menu routes its title through this
    function — change the divider char, colour, width, or the
    header-to-content gap here and all of them follow.
    """
    paint_title(console, screen_width, row, title, fg=fg)
    if divider_w is None:
        # Full-width rule: spans to the right edge like the message
        # log underneath it (modals are full-screen, no HUD band).
        divider_w = rule_width(screen_width, x=divider_x)
    console.print(
        x=divider_x, y=row + 1,
        string=DIVIDER_CHAR * divider_w, fg=COLOR_DIVIDER,
    )
    return row + 3

def rule_width(screen_width: int, *, x: int = 2) -> int:
    """Return the rule span for ``screen_width``.

    Rules start at the flush-left content column (``x``, default 2)
    and mirror the same buffer on the right, so the rule sits
    centered with equal margins both sides.  Single source for
    header + section-rule widths so a future margin tweak stays
    a one-line change.
    """
    return max(1, screen_width - 2 * x)

def format_split_row(
    name: str, label: str, suffix: str,
    selected: bool, col_w: int,
) -> str:
    """Format a row that fits exactly in ``col_w`` columns.

    ``name`` is truncated and padded to leave room for the
    ``label`` (e.g. " 14$") and ``suffix`` (e.g. "(30)").
    Marker ``"> "`` or ``"  "`` is included in the width calculation.
    """
    marker = "> " if selected else "  "
    fixed = len(marker) + 1 + len(label) + 1
    name_w = max(4, col_w - fixed - len(suffix))
    trimmed = name[:name_w].ljust(name_w)
    return f"{marker}{trimmed} {label} {suffix}"
