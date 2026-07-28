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
from typing import Callable, TypeVar

import tcod.console
import tcod.context
import tcod.event

from .data.species import list_species
from .data.classes import list_classes

# Generic modal outcome type. Each modal defines its own enum subclass
# with terminal outcomes plus an IGNORE member (which signals "this
# event wasn't relevant, keep polling"). The Modal helper duck-types
# the IGNORE check via ``outcome.name == "IGNORE"`` so each modal
# doesn't need to import a shared base (Python enums can't subclass
# if the base defines members, so a shared base is impossible).
T = TypeVar("T", bound=Enum)

# Vivid sci-fi palette tuned for the default DejaVu 16x16 tileset.
# Each role gets a thematic hue (cyan for titles, gold for highlights,
# slate for dim/auxiliary text) so the menus pop instead of reading
# as a stack of greys. ``COLOR_OPTION_HIGHLIGHT`` stays pure white
# because that is already the brightest possible value - the gold
# accents in HUD add color elsewhere where escape from pure white
# is desired.
COLOR_TITLE: tuple[int, int, int] = (130, 220, 255)              # bright cyan
COLOR_INSTRUCTION: tuple[int, int, int] = (110, 130, 175)        # muted periwinkle
COLOR_OPTION: tuple[int, int, int] = (200, 200, 220)             # pale lavender-grey
COLOR_OPTION_HIGHLIGHT: tuple[int, int, int] = (255, 255, 255)
COLOR_OPTION_HIGHLIGHT2: tuple[int, int, int] = (150, 200, 220)        # steel-cyan, used for science ports + station glyphs in AoI panel.
    # pure white (brightest)
COLOR_DESCRIPTION: tuple[int, int, int] = (175, 170, 210)        # muted lavender
# Value cells (numbers, prices) - kept here so dialogs in __main__
# (e.g. the ship-buy modal) can use the same near-white/dim pair.
COLOR_VALUE_WHITE: tuple[int, int, int] = (250, 250, 250)
COLOR_VALUE_DIM: tuple[int, int, int] = (150, 150, 150)           # neutral silver (de-saturated so it doesn't echo SIDEWALK)


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
        instruction="ARROW KEYS navigate - ENTER select - ESC start over",
        options=tuple((s.id, s.name) for s in list_species()),
        descriptions={s.id: s.description for s in list_species()},
        selected=0,
    )


def class_menu() -> MenuScreen:
    """Build the class-choices menu screen."""
    return MenuScreen(
        title="Choose Your Class",
        instruction="ARROW KEYS navigate - ENTER select - ESC go back",
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


def render_selectable_list(
    console: tcod.console.Console,
    screen_width: int,
    screen_height: int,
    title: str,
    items: list[tuple[str, str]],
    selected: int,
    *,
    col_x: int | None = None,
    title_y: int | None = None,
    row_spacing: int = 2,
    title_fg: tuple[int, int, int] = COLOR_TITLE,
    item_fg_selected: tuple[int, int, int] = COLOR_OPTION_HIGHLIGHT,
    item_fg_normal: tuple[int, int, int] = COLOR_OPTION,
    desc_fg_selected: tuple[int, int, int] = COLOR_DESCRIPTION,
    desc_fg_normal: tuple[int, int, int] = COLOR_VALUE_DIM,
    hint_fg: tuple[int, int, int] = COLOR_INSTRUCTION,
    hint: str = "UP/DOWN navigate - ENTER select - ESC back",
) -> None:
    """Render a selectable list menu with a fixed-column layout.

    ``items`` is ``[(name, description), ...]`` — name is the
    selectable label, description is an optional second line shown
    in dim text below each item (pass ``""`` for items with no
    description).  Uses consistent-width markers (4 chars for both
    selected and unselected) and a fixed left column so scrolling
    never shifts the text horizontally.

    The console is NOT cleared — callers may want to paint a
    background or message log underneath.  Call ``console.clear()``
    yourself before calling this if you want a clean slate.

    Args:
        console: Target console to draw on.
        screen_width: Width of the console in character cells.
        screen_height: Height of the console in character cells.
        title: Title text (centered).
        items: List of ``(name, description)`` tuples.
        selected: Index of the currently selected item.
        col_x: Left column for item names.  Defaults to ``screen_width // 4``.
        title_y: Y position of the title.  Defaults to ``screen_height // 4``.
        row_spacing: Lines between item rows (default 2: name + desc).
        title_fg: Color for the title.
        item_fg_selected: Color for the selected item name.
        item_fg_normal: Color for unselected item names.
        desc_fg_selected: Color for the selected item's description.
        desc_fg_normal: Color for unselected items' descriptions.
        hint_fg: Color for the hint at the bottom.
        hint: Hint text shown below the list.  Empty string to skip.
    """
    _col_x = col_x if col_x is not None else screen_width // 4
    _title_y = title_y if title_y is not None else screen_height // 4

    # Title (centered).
    console.print(
        x=centered_x(title, screen_width), y=_title_y,
        string=title, fg=title_fg,
    )

    # Items with consistent-width markers.
    n = len(items)
    list_top = _title_y + 2
    for i, (name, desc) in enumerate(items):
        row = list_top + i * row_spacing
        is_selected = i == selected
        marker_open = "> " if is_selected else "  "
        marker_close = " <" if is_selected else "  "
        text = f"{marker_open}{name}{marker_close}"
        item_fg = item_fg_selected if is_selected else item_fg_normal
        console.print(x=_col_x, y=row, string=text, fg=item_fg)

        if desc:
            desc_fg = desc_fg_selected if is_selected else desc_fg_normal
            console.print(
                x=_col_x + 2, y=row + 1,
                string=desc, fg=desc_fg,
            )

    # Hint (centered).
    if hint:
        hint_y = list_top + n * row_spacing + 1
        console.print(
            x=centered_x(hint, screen_width), y=hint_y,
            string=hint, fg=hint_fg,
        )


def render_menu(
    console: tcod.console.Console,
    menu: MenuScreen,
    screen_width: int,
    screen_height: int,
) -> None:
    """Paint ``menu`` centered on ``console``. Idempotent (clears first).

    Delegates to :func:`render_selectable_list` with the menu's title
    serving as the instruction line and its options as the item list.
    """
    console.clear()
    _items = [(label, menu.descriptions.get(id_, "")) for id_, label in menu.options]
    render_selectable_list(
        console, screen_width, screen_height,
        title=menu.title,
        items=_items,
        selected=menu.selected,
        hint=menu.instruction,
    )


def render_confirm(
    console: tcod.console.Console,
    species: character.Species,
    klass: character.GameClass,
    screen_width: int,
    screen_height: int,
) -> None:
    """Paint the confirmation screen. Idempotent (clears first)."""
    line_top = f"You are a {species.name.upper()} {klass.name.upper()}."
    line_sub = species.description
    line_sub2 = klass.description
    line_prompt1 = "Press ENTER to begin your journey."
    line_prompt2 = "Press ESC to start over."

    console.clear()
    center_y = screen_height // 2
    title_y = center_y - 5

    for i, line in enumerate((line_top, "", line_sub, line_sub2, "", line_prompt1, line_prompt2)):
        row = title_y + i
        fg = COLOR_TITLE if i == 0 else COLOR_INSTRUCTION
        if not line:
            continue
        console.print(
            x=centered_x(line, screen_width),
            y=row,
            string=line,
            fg=fg,
        )


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


def render_title_splash(context: tcod.context.Context) -> None:
    """Render the title splash screen and wait for any key.

    Draws a double-line CP437 border, scattered starfield, "SPACEHACK"
    in large block letters, a detailed ASCII spaceship with exhaust
    flame, a short flavor paragraph, and a "Press any key to continue"
    prompt. Blocks until the player presses any key (or closes the
    window).
    """
    from .engine import SCREEN_WIDTH as W, SCREEN_HEIGHT as H, make_console
    import random

    _console = make_console()
    _console.clear()

    # Double-line border
    _TL = "\u2554"  # ╔
    _TR = "\u2557"  # ╗
    _BL = "\u255a"  # ╚
    _BR = "\u255d"  # ╝
    _H  = "\u2550"  # ═
    _V  = "\u2551"  # ║
    _console.print(x=0,  y=0,   string=_TL + _H * (W - 2) + _TR, fg=(100, 110, 160))
    _console.print(x=0,  y=H-1, string=_BL + _H * (W - 2) + _BR, fg=(100, 110, 160))
    for _y in range(1, H - 1):
        _console.print(x=0,   y=_y, string=_V, fg=(100, 110, 160))
        _console.print(x=W-1, y=_y, string=_V, fg=(100, 110, 160))

    # Title
    _title_y = H // 2 - 8
    for _i, _line in enumerate(_TITLE_ART):
        _x = (W - len(_line)) // 2
        _console.print(x=_x, y=_title_y + _i, string=_line, fg=(100, 200, 255))

    # Flavor text
    _lines = [
        "The year is 2156. Humankind has spread across a dozen star systems,",
        "linked by jump gates of unknown origin. You are a freelance pilot",
        "making a living on the frontier \u2014 trading, bounty hunting, and",
        "surviving where the law is what you make of it.",
    ]
    _flavor_y = H // 2 + 6
    for _i, _line in enumerate(_lines):
        _console.print(
            x=centered_x(_line, W), y=_flavor_y + _i,
            string=_line, fg=(160, 175, 210),
        )

    # Spaceship (below flavor text)
    _ship_x = W - 20     # 18 wide, cols 80-97
    _ship_y = _flavor_y + len(_lines)
    _ship_colors = [
        (180, 180, 210),  # 0  nose tip
        (200, 200, 230),  # 1  nose cone
        (220, 220, 245),  # 2  hull
        (210, 210, 235),  # 3  hull
        (210, 210, 235),  # 4  hull
        (210, 210, 235),  # 5  hull
        (200, 200, 225),  # 6  hull
        (180, 170, 190),  # 7  engine mount
        (190, 180, 200),  # 8  engine
        (190, 180, 200),  # 9  engine
        (170, 155, 180),  # 10 engine base
        (255, 120,  60),  # 11 flame core
        (255, 180,  50),  # 12 flame
        (255, 210, 100),  # 13 smoke
        (220, 200, 150),  # 14 smoke
    ]
    for _i, _line in enumerate(_SHIP_ART):
        _console.print(x=_ship_x, y=_ship_y + _i, string=_line, fg=_ship_colors[_i])

    # Starfield
    for _ in range(80):
        _sx = random.randint(2, W - 3)
        _sy = random.randint(2, H - 3)
        if _title_y - 2 <= _sy <= _title_y + len(_TITLE_ART) + 1:
            continue
        if _flavor_y <= _sy <= _flavor_y + len(_lines) - 1:
            continue
        if _ship_x <= _sx <= _ship_x + len(_SHIP_ART[0]) - 1 and _ship_y <= _sy <= _ship_y + len(_SHIP_ART) - 1:
            continue
        if H - 10 <= _sy <= H - 2:
            continue
        _ch = random.choice([".", ".", "*", "."])
        _br = random.randint(100, 200)
        _console.print(x=_sx, y=_sy, string=_ch, fg=(_br, _br, _br))

    # Prompt
    _prompt = "Press any key to begin"
    _console.print(
        x=centered_x(_prompt, W), y=H - 4,
        string=_prompt, fg=(120, 140, 190),
    )
    _console.print(
        x=centered_x("\u2500\u2500\u2500\u2500\u2500\u2500\u2500", W), y=H - 5,
        string="\u2500\u2500\u2500\u2500\u2500\u2500\u2500", fg=(100, 110, 160),
    )

    # Planet
    _planet_art = [
        "  \u250c\u2500\u2500\u2500\u2500\u2510",
        " \u2500\u2502    \u2502\u2500",
        "\u2500\u2500\u2502    \u2502\u2500\u2500",
        " \u2500\u2502    \u2502\u2500",
        "  \u2514\u2500\u2500\u2500\u2500\u2518",
    ]
    _planet_x = 4
    _planet_y = H - 12
    _planet_fg = (90, 130, 160)
    for _i, _line in enumerate(_planet_art):
        _console.print(x=_planet_x, y=_planet_y + _i, string=_line, fg=_planet_fg)
    _console.print(x=_planet_x + 2, y=_planet_y + 2, string="\u25c4", fg=(130, 170, 200))

    # Present and wait for key
    context.present(_console)
    while True:
        for event in tcod.event.wait():
            if isinstance(event, tcod.event.KeyDown):
                return
            if isinstance(event, tcod.event.Quit):
                return


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


def _safe_syms(*names: str) -> tuple:
    """Resolve ``tcod.event.KeySym`` members by name, skipping any that
    aren't exported by the installed tcod version.

    Different tcod releases expose different sets of KeySym aliases -
    for example, ``ENTER`` exists as a synonym for ``RETURN`` in some
    builds but not in others, and the numpad arrows (``KP_8`` /
    ``KP_2`` / ``KP_5``) can also vary. Looking syms up by name and
    silently dropping the missing ones keeps this module importable
    across tcod upgrades; the cost is that, on a tcod build missing
    e.g. ``KP_5``, the user just can't confirm via numpad-5 (main
    keyboard Enter still works via ``RETURN``).
    """
    return tuple(
        getattr(tcod.event.KeySym, name)
        for name in names
        if hasattr(tcod.event.KeySym, name)
    )


_ENTER_SYMS = _safe_syms("RETURN", "ENTER", "KP_ENTER", "KP_5")
_UP_SYMS = _safe_syms("UP", "KP_8")
_DOWN_SYMS = _safe_syms("DOWN", "KP_2")
_ESCAPE_SYMS = _safe_syms("ESCAPE")


def update_menu(menu: MenuScreen, event: tcod.event.Event) -> MenuAction:
    """Apply ``event`` to ``menu`` and return the resulting action."""
    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym
        sym_name: str = getattr(sym, 'name', '').lower()
        if sym in _UP_SYMS or sym_name == 'k':
            menu.selected = (menu.selected - 1) % len(menu.options)
            return MenuAction.NONE
        if sym in _DOWN_SYMS or sym_name == 'j':
            menu.selected = (menu.selected + 1) % len(menu.options)
            return MenuAction.NONE
        if sym in _ENTER_SYMS:
            return MenuAction.CONFIRM
        if sym in _ESCAPE_SYMS:
            return MenuAction.BACK
    return MenuAction.NONE


def update_confirm(event: tcod.event.Event) -> MenuAction:
    """Translate a single key event for the confirm screen."""
    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym
        if sym in _ENTER_SYMS:
            return MenuAction.CONFIRM
        if sym in _ESCAPE_SYMS:
            return MenuAction.BACK
    return MenuAction.NONE


# ---------------------------------------------------------------------------
# Modal helper
# ---------------------------------------------------------------------------


class Modal:
    """Helper to run a render/update event loop.

    Wraps the standard modal pattern so individual ``_run_X`` functions
    in :mod:`spacehack.__main__` don't re-implement it. The console
    is passed at construction time so it can be cleared once per loop
    iteration; ``context`` is held for ``present()`` calls. ``run()``
    blocks until ``update`` returns something that is NOT named
    ``"IGNORE"`` - which is the convention every existing modal enum
    (``NavigationOutcome``, ``ShipMenuAction``, ``PlanetMenuOutcome``,
    etc.) already follows.
    """

    def __init__(
        self,
        context: tcod.context.Context,
        console: tcod.console.Console,
    ) -> None:
        self.context = context
        self.console = console

    def run(
        self,
        render: Callable[[], None],
        update: Callable[[tcod.event.Event], T],
        *,
        ignore: T | None = None,
    ) -> T:
        """Block until ``update`` returns a terminal outcome.

        ``render`` paints the frame; ``update`` maps a single event
        to an outcome. ``ignore`` (optional) names the enum member
        that signals "keep polling" - by default the helper
        duck-types via ``outcome.name == "IGNORE"`` so existing
        modals (NavigationOutcome, ShipMenuAction, etc.) work
        without per-call plumbing.

        Returns whatever ``update`` produced on the terminating
        iteration.
        """
        while True:
            render()
            self.context.present(self.console)
            for event in tcod.event.wait():
                outcome = update(event)
                if ignore is not None:
                    if outcome is ignore:
                        continue
                elif outcome is not None and getattr(outcome, "name", None) == "IGNORE":
                    continue
                return outcome
