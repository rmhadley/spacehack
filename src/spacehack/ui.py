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

    Word-wrap is greedy: each line fits as many words as possible
    without exceeding ``max_width``. A single word longer than
    ``max_width`` goes on its own line rather than being split
    mid-word (so a long quest title never loses a chunk of itself
    to an overflow cut). Empty / whitespace-only input returns an
    empty list so callers can use ``if wrap_text(...):`` to gate
    painting cleanly without nil-conditional branching.
    """
    if max_width < 1 or not text or not text.strip():
        return []
    words = text.split()
    lines: list[str] = []
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

# SPACEHACK in 7-wide × 5-tall block letters.
# Uses # so it renders on any CP437 / ASCII tileset.
# Each row is 71 characters (9 letters × 7 + 8 inter-letter gaps).
_TITLE_ART: tuple[str, ...] = (
    "####### #######  #####   #####  ####### ##   ##  #####   #####  ##   ##",
    "##      ##   ## ##   ## ##   ## ##      ##   ## ##   ## ##   ## ##  ## ",
    "####### ####### ####### ##      #####   ####### ####### ##      #####  ",
    "     ## ##   ## ##   ## ##   ## ##      ##   ## ##   ## ##   ## ##  ## ",
    "####### ##   ## ##   ##  #####  ####### ##   ## ##   ##  #####  ##   ##",
)

# Simple ASCII rocket ship, 7 wide × 8 tall.
_SHIP_ART: tuple[str, ...] = (
    "   /\\",
    "  /  \\",
    " / |> \\",
    "/______\\",
    "   ||",
    "   ||",
    "  /  \\",
    " /    \\",
)


def render_title_splash(context: tcod.context.Context) -> None:
    """Render the title splash screen and wait for any key.

    Draws a double-line CP437 border, scattered starfield, "SPACEHACK"
    in large block letters, an ASCII rocket, a short flavor paragraph,
    and a "Press any key to continue" prompt. Blocks until the player
    presses any key (or closes the window).
    """
    from .engine import SCREEN_WIDTH as W, SCREEN_HEIGHT as H, make_console
    import random

    _console = make_console()
    _console.clear()

    # ── Double-line border (CP437 box-drawing) ──
    _TL = "╔"  # ┌ in some encodings but ╔ = 201 in CP437 ✓
    _TR = "╗"
    _BL = "╚"
    _BR = "╝"
    _H  = "═"  # horizontal
    _V  = "║"  # vertical
    _console.print(x=0,  y=0,   string=_TL + _H * (W - 2) + _TR, fg=(100, 110, 160))
    _console.print(x=0,  y=H-1, string=_BL + _H * (W - 2) + _BR, fg=(100, 110, 160))
    for _y in range(1, H - 1):
        _console.print(x=0,   y=_y, string=_V, fg=(100, 110, 160))
        _console.print(x=W-1, y=_y, string=_V, fg=(100, 110, 160))

    # ── Starfield (dots scattered away from the title area) ──
    _title_top = H // 2 - 9
    _title_bot = H // 2 + 3
    for _ in range(80):
        _sx = random.randint(2, W - 3)
        _sy = random.randint(2, H - 3)
        # Keep stars away from title block, ship, and prompt areas.
        if _title_top <= _sy <= _title_bot:
            continue
        if H - 10 <= _sy <= H - 2:
            continue
        if H // 2 - 3 <= _sy <= H // 2 + 8 and W // 2 - 10 <= _sx <= W // 2 + 10:
            continue
        _ch = random.choice([".", ".", "*", "."])
        _br = random.randint(100, 200)
        _console.print(x=_sx, y=_sy, string=_ch, fg=(_br, _br, _br))

    # ── Title: "SPACEHACK" ──
    _title_y = H // 2 - 8
    for _i, _line in enumerate(_TITLE_ART):
        _x = (W - len(_line)) // 2
        _console.print(x=_x, y=_title_y + _i, string=_line, fg=(100, 200, 255))

    # ── Rocket ship ──
    _ship_x = W - 26
    _ship_y = H // 2 - 6
    _ship_colors = [(180, 180, 200), (200, 200, 220), (220, 220, 240),
                    (160, 160, 180), (150, 150, 170), (150, 150, 170),
                    (180, 180, 200), (200, 200, 220)]
    for _i, _line in enumerate(_SHIP_ART):
        _console.print(x=_ship_x, y=_ship_y + _i, string=_line, fg=_ship_colors[_i])

    # ── Flavor text ──
    _lines = [
        "The year is 2156. Humankind has spread across a dozen star systems,",
        "linked by jump gates of unknown origin. You are a freelance pilot",
        "making a living on the frontier — trading, bounty hunting, and",
        "surviving where the law is what you make of it.",
    ]
    _flavor_y = H // 2 + 6
    for _i, _line in enumerate(_lines):
        _console.print(
            x=centered_x(_line, W), y=_flavor_y + _i,
            string=_line, fg=(160, 175, 210),
        )

    # ── Prompt ──
    _prompt = "Press any key to begin"
    _console.print(
        x=centered_x(_prompt, W), y=H - 4,
        string=_prompt, fg=(120, 140, 190),
    )
    # Decorative line above prompt.
    _console.print(
        x=centered_x("───────", W), y=H - 5,
        string="───────", fg=(100, 110, 160),
    )

    # ── Planet in the bottom-left corner ──
    _planet_art = [
        "  ┌────┐",
        " ─│    │─",
        "──│    │──",
        " ─│    │─",
        "  └────┘",
    ]
    _planet_x = 4
    _planet_y = H - 12
    _planet_fg = (90, 130, 160)
    for _i, _line in enumerate(_planet_art):
        _console.print(x=_planet_x, y=_planet_y + _i, string=_line, fg=_planet_fg)
    _console.print(x=_planet_x + 2, y=_planet_y + 2, string="◄", fg=(130, 170, 200))

    # ── Present and wait ──
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


# All four key groups go through ``_safe_syms`` so the module is
# tolerant of tcod builds that drop or rename KeySym members.
_ENTER_SYMS = _safe_syms("RETURN", "ENTER", "KP_ENTER", "KP_5")
_UP_SYMS = _safe_syms("UP", "KP_8")
_DOWN_SYMS = _safe_syms("DOWN", "KP_2")
_ESCAPE_SYMS = _safe_syms("ESCAPE")


def update_menu(menu: MenuScreen, event: tcod.event.Event) -> MenuAction:
    """Apply ``event`` to ``menu`` and return the resulting action.

    Mutates ``menu.selected`` on UP/DOWN-style navigation (arrow keys
    and vim ``k``/``j``). Other events yield ``NONE``.
    """
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
# Centralizes the standard "render frame -> present -> poll input ->
# update -> return on non-IGNORE" loop that ~13 _run_X functions in
# ``__main__`` were duplicating. Each modal defines its own render and
# update callbacks plus an enum subclass with an IGNORE member + its
# terminal outcomes; ``Modal.run`` keeps polling until the update
# returns anything whose ``.name != "IGNORE"``, then returns that
# outcome. Modals with mutable state (selection index, fuel info, etc.)
# capture it via closures; modals that need a payload (e.g. the
# picked menu id) read it from the closure after run() returns.


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
        without per-call plumbing. A future modal that names its
        keep-polling member differently can pass it explicitly
        rather than rely on the name convention.

        Returns whatever ``update`` produced on the terminating
        iteration. ``T`` is bound to ``Enum`` but the helper itself
        does not constrain the runtime type - callers pass through
        whatever enum / payload they want.
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
