"""In-game UI primitives: menu rendering and input for the
character-creation screens.

This module is deliberately tiny and library-agnostic - it draws a
single centered vertical menu onto an existing project framebuffer
and translates key events into menu actions. Higher-level state
sachines (species -> class -> confirm) live in :mod:`spacehack.__main__`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .data.species import list_species
from .data.classes import list_classes

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

def _modal_hint(*parts: str) -> str:
    """Build a shared modal hint without importing presentation at module load."""
    from . import pygame_ui

    return pygame_ui.modal_hint(pygame_ui.NAV_HINT, *parts)


def species_menu() -> MenuScreen:
    """Build the species-choices menu screen (the generic-menu
    fallback when split presentation is unavailable)."""
    return MenuScreen(
        title="Choose Your Species",
        instruction=_modal_hint("ENTER select", "ESC start over"),
        options=tuple((s.id, s.name) for s in list_species()),
        descriptions={s.id: s.description for s in list_species()},
        selected=0,
    )

def class_menu() -> MenuScreen:
    """Build the class-choices menu screen."""
    return MenuScreen(
        title="Choose Your Class",
        instruction=_modal_hint("ENTER select", "ESC go back"),
        options=tuple((c.id, c.name) for c in list_classes()),
        descriptions={c.id: c.description for c in list_classes()},
        selected=0,
    )


# ---------------------------------------------------------------------------
# Species card (doc 49 SETTLED 2): the split-screen picker's right pane
# ---------------------------------------------------------------------------

# The six stats in card order — ship row first, ground row second.
_SPECIES_STAT_ORDER: tuple[tuple[str, str, int], ...] = (
    # (spec field, display name, which bonus container)
    ("gunnery", "Gunnery", "skill"),
    ("piloting", "Piloting", "skill"),
    ("engineering", "Engineering", "skill"),
    ("reflexes", "Reflexes", "ground"),
    ("strength", "Strength", "ground"),
    ("stamina", "Stamina", "ground"),
)

# Wrap budget for card description lines — informational rows truncate,
# never wrap, so long text is pre-wrapped to fit the narrowest panel.
_SPECIES_CARD_WRAP: int = 36


def _species_start_stats(spec) -> dict[str, int]:
    """The species' six start values (base + species spread, class-free)."""
    from .character import GROUND_STAT_BASE, PILOT_SKILL_BASE
    values: dict[str, int] = {}
    for field, _label, container in _SPECIES_STAT_ORDER:
        base = PILOT_SKILL_BASE if container == "skill" else GROUND_STAT_BASE
        bonus = getattr(
            spec.skill_bonus if container == "skill" else spec.ground_bonus,
            field,
        )
        values[field] = base + bonus
    return values


def species_stats_line(spec) -> str:
    """The card's stat line: absolute values, no +/- (SETTLED 2).

    All six equal reads "All stats N"; otherwise the deviating stats
    are named with their values and the shared base reads "rest 10"
    (e.g. Martian: "Strength 12, Stamina 14, rest 10"). If the two
    base constants ever diverge, the "rest" clause drops out and
    every stat is named — never a mislabeled row.
    """
    from .character import GROUND_STAT_BASE, PILOT_SKILL_BASE
    values = _species_start_stats(spec)
    labeled = []
    for field, label, container in _SPECIES_STAT_ORDER:
        base = PILOT_SKILL_BASE if container == "skill" else GROUND_STAT_BASE
        labeled.append((label, values[field], base))
    if len({value for _label, value, _base in labeled}) == 1:
        return f"All stats {labeled[0][1]}"
    named = [f"{label} {value}" for label, value, base in labeled if value != base]
    bases = {base for _label, _value, base in labeled}
    rest = f", rest {next(iter(bases))}" if len(bases) == 1 else ""
    return ", ".join(named) + rest


def _species_start_row(spec):
    """The card's Armor/HP row, read through the live naked-start
    formulas so the card never disagrees with a fresh game."""
    from types import SimpleNamespace

    from . import pygame_split
    from . import xp

    _naked = SimpleNamespace(
        ground_stats=SimpleNamespace(stamina=_species_start_stats(spec)["stamina"]),
        equipped_ground_armor={},
        player_traits=[spec.trait_id],
        character_info={"species_id": spec.id},
    )
    return pygame_split.SplitRow(
        f"Armor {xp.sturdy_armor_bonus(_naked)}   "
        f"HP {xp.ground_max_hp_total(_naked)}",
        "", "", "", selectable=False,
    )


def _species_card_rows(spec) -> tuple:
    """The right pane's card body. The header row carries the identity
    (``glyph - NAME - home``, in the species color); the body opens
    straight into the numbers (doc 49 SETTLED 2, user title revision
    2026-09-27)."""
    from . import pygame_split

    def _info(label, *, fg=None):
        return pygame_split.SplitRow(
            label, "", "", "", selectable=False, fg=fg,
        )

    rows = [
        pygame_split.section_header("STARTING STATS"),
        _info(species_stats_line(spec)),
        _species_start_row(spec),
        pygame_split.section_header("TRAIT"),
    ]
    from .data.traits.core import ORIGIN_TRAITS
    trait = ORIGIN_TRAITS[spec.trait_id]
    rows.append(_info(trait.name, fg=COLOR_OPTION_HIGHLIGHT))
    rows.extend(_info(line) for line in wrap_text(trait.description, _SPECIES_CARD_WRAP))
    return tuple(rows)


def species_split_frame(selected: int = 0):
    """The species picker's split frame: left cycling options, right
    the hovered species' card (doc 49 SETTLED 2). The card pane's
    title is the species' identity line — ``@ - HUMAN - Earth (Sol)``
    — painted in the species color."""
    from . import pygame_split

    options = tuple(
        pygame_split.SplitRow(label=s.name, value="", detail="", action=s.id)
        for s in list_species()
    )
    roster = list_species()
    spec = roster[max(0, min(selected, len(roster) - 1))]
    return pygame_split.SplitFrame(
        title="CHOOSE YOUR SPECIES",
        left_label="SPECIES",
        right_label=f"{spec.glyph} - {spec.name.upper()} - {spec.home}",
        right_label_color=spec.color,
        left_rows=options,
        right_rows=_species_card_rows(spec),
        footer_left="",
        footer_right="",
        hint=_modal_hint("UP/DOWN browse", "ENTER select", "ESC start over"),
        selected=max(0, min(selected, len(options) - 1)),
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
    lines: list[str] = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        lines.extend(_wrap_paragraph(para.split(), max_width))
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _wrap_paragraph(words: list[str], max_width: int) -> list[str]:
    """Greedy wrap; a word longer than ``max_width`` keeps its own line."""
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
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
