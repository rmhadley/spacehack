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

def render_menu(
    console: tcod.console.Console,
    menu: MenuScreen,
    screen_width: int,
    screen_height: int,
) -> None:
    """Paint ``menu`` centered on ``console``. Idempotent (clears first)."""
    console.clear()

    title_y = screen_height // 4
    console.print(
        x=centered_x(menu.title, screen_width),
        y=title_y,
        string=menu.title,
        fg=COLOR_TITLE,
    )
    console.print(
        x=centered_x(menu.instruction, screen_width),
        y=title_y + 2,
        string=menu.instruction,
        fg=COLOR_INSTRUCTION,
    )

    # Options centered vertically around the middle, spaced 2 rows apart.
    list_top = (screen_height // 2) - len(menu.options)
    for i, (_, label) in enumerate(menu.options):
        row = list_top + i * 2
        is_selected = (i == menu.selected)
        marker = "> " if is_selected else "  "
        end_marker = " <" if is_selected else "  "
        text = f"{marker}{label}{end_marker}"
        fg = COLOR_OPTION_HIGHLIGHT if is_selected else COLOR_OPTION
        console.print(
            x=centered_x(text, screen_width),
            y=row,
            string=text,
            fg=fg,
        )

    desc = menu.descriptions.get(menu.selected_id, "")
    if desc:
        console.print(
            x=centered_x(desc, screen_width),
            y=list_top + len(menu.options) * 2 + 1,
            string=desc,
            fg=COLOR_DESCRIPTION,
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

    Mutates ``menu.selected`` on UP/DOWN-style navigation. Other
    events yield ``NONE``.
    """
    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym
        if sym in _UP_SYMS:
            menu.selected = (menu.selected - 1) % len(menu.options)
            return MenuAction.NONE
        if sym in _DOWN_SYMS:
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
