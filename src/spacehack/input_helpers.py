"""Input helpers extracted from ``__main__.py``.

Contains the :class:`Outcome` enum, :func:`_run_pick`,
:func:`_run_confirm`, key-press predicates (``_is_q_press``,
``_is_m_press``, etc.), and the :func:`_movement_action`
movement mapper.  Everything here is a pure function or a short
Modal wrapper — no game state, no event-loop internals.
"""

from __future__ import annotations
from enum import Enum, auto
import tcod.console
import tcod.context
import tcod.event
from . import ui
from . import world
from .engine import make_console, SCREEN_WIDTH, SCREEN_HEIGHT
from .data.species import find_species
from .data.classes import find_class


class Outcome(Enum):
    """What happened at the end of a per-creation-screen loop iteration.

    ``IGNORE`` is the standard "keep polling" signal consumed by
    :meth:`spacehack.ui.Modal.run` -- an update function returns
    :attr:`IGNORE` for events it doesn't act on, and Modal keeps
    rendering + polling. Every other member terminates the modal
    loop and propagates back to the caller.
    """
    IGNORE = auto()
    QUIT = auto()
    BACK = auto()
    CONFIRM = auto()


def _pygame_pick_frames(menu: ui.MenuScreen):
    """Build fixed-layout Pygame frames for one character picker."""
    from . import pygame_menu

    items = tuple(
        pygame_menu.MenuItem(
            label=label,
            description=menu.descriptions.get(option_id, ""),
            action=option_id,
        )
        for option_id, label in menu.options
    )
    return tuple(
        pygame_menu.MenuFrame(
            title=menu.title.upper(),
            body="Choose an option to shape your character.",
            items=items,
            hints=(menu.instruction,),
            selected=selected,
        )
        for selected in range(len(items))
    )


def _pygame_confirm_frame(species, klass):
    """Build the fixed-layout Pygame character confirmation frame."""
    from . import pygame_menu

    body = (
        f"You are a {species.name.upper()} {klass.name.upper()}.\n\n"
        f"SPECIES: {species.description}\n"
        f"CLASS: {klass.description}"
    )
    item = pygame_menu.MenuItem(
        label="BEGIN JOURNEY",
        description=f"Starting credits: {klass.credits}$",
        action="CONFIRM",
    )
    return pygame_menu.MenuFrame(
        title="CHARACTER CREATION",
        body=body,
        items=(item,),
        hints=("ENTER begin journey   ESC start over",),
        selected=0,
    )


def _is_character_menu(menu: ui.MenuScreen) -> bool:
    """Return whether a menu is one of the two character-creation pickers."""
    return menu.title in {"Choose Your Species", "Choose Your Class"}


def _pygame_character_enabled() -> bool:
    """Return whether character creation can use the Pygame presentation."""
    from . import pygame_menu, pygame_runtime

    return pygame_menu.enabled() or pygame_runtime.shared_enabled()


def _run_pygame_pick(context, menu: ui.MenuScreen) -> tuple[Outcome, str | None] | None:
    """Run a character picker in Pygame, or return None for tcod fallback."""
    from . import pygame_menu

    frames = _pygame_pick_frames(menu)
    if not frames:
        return None
    while True:
        try:
            outcome, action, _selected = pygame_menu.run_for_context(
                context,
                frames,
                caption=f"spacehack - {menu.title.lower()}",
            )
        except pygame_menu.PygameMenuUnavailable:
            return None
        if outcome == "GUIDE":
            continue
        if outcome == "QUIT":
            return Outcome.QUIT, None
        if outcome == "BACK":
            return Outcome.BACK, None
        if outcome == "SELECT":
            valid_ids = {option_id for option_id, _label in menu.options}
            if action in valid_ids:
                return Outcome.CONFIRM, action
        return None


def _run_pygame_confirm(context, species_id: str, class_id: str) -> Outcome | None:
    """Run character confirmation in Pygame, or return None for tcod fallback."""
    from . import pygame_menu

    species = find_species(species_id)
    klass = find_class(class_id)
    frame = _pygame_confirm_frame(species, klass)
    while True:
        try:
            outcome, action, _selected = pygame_menu.run_for_context(
                context,
                (frame,),
                caption="spacehack - character creation",
            )
        except pygame_menu.PygameMenuUnavailable:
            return None
        if outcome == "GUIDE":
            continue
        if outcome == "SELECT" and action == "CONFIRM":
            return Outcome.CONFIRM
        if outcome == "BACK":
            return Outcome.BACK
        if outcome == "QUIT":
            return Outcome.QUIT
        return None


def _run_pick(context: tcod.context.Context, menu: ui.MenuScreen) -> tuple[Outcome, str | None]:
    if _pygame_character_enabled() and _is_character_menu(menu):
        _pygame_result = _run_pygame_pick(context, menu)
        if _pygame_result is not None:
            return _pygame_result
    console = make_console()

    def _render() -> None:
        ui.render_menu(console, menu, SCREEN_WIDTH, SCREEN_HEIGHT)

    def _update(event) -> Outcome:
        if isinstance(event, tcod.event.Quit):
            return Outcome.QUIT
        action = ui.update_menu(menu, event)
        if action is ui.MenuAction.CONFIRM:
            return Outcome.CONFIRM
        if action is ui.MenuAction.BACK:
            return Outcome.BACK
        return Outcome.IGNORE
    outcome = ui.Modal(context, console).run(_render, _update)
    if outcome is Outcome.CONFIRM:
        return (outcome, menu.selected_id)
    return (outcome, None)


def _run_confirm(context: tcod.context.Context, species_id: str, class_id: str) -> Outcome:
    if _pygame_character_enabled():
        _pygame_result = _run_pygame_confirm(context, species_id, class_id)
        if _pygame_result is not None:
            return _pygame_result
    species = find_species(species_id)
    klass = find_class(class_id)
    console = make_console()

    def _render() -> None:
        ui.render_confirm(console, species, klass, SCREEN_WIDTH, SCREEN_HEIGHT)

    def _update(event) -> Outcome:
        if isinstance(event, tcod.event.Quit):
            return Outcome.QUIT
        action = ui.update_confirm(event)
        if action is ui.MenuAction.CONFIRM:
            return Outcome.CONFIRM
        if action is ui.MenuAction.BACK:
            return Outcome.BACK
        return Outcome.IGNORE
    return ui.Modal(context, console).run(_render, _update)


def _movement_action(event: tcod.event.Event) -> tuple[int, int] | None:
    """If ``event`` is a movement KeyDown, return (dx, dy); else None.

    Accepts all three movement key families from
    :data:`world.MOVE_KEYS`: vim keys (``h``/``j``/``k``/``l``,
    ``y``/``u``/``b``/``n``), arrow keys, and the numpad
    (``KP_1``-``KP_9``).

    SDL/tcod reports physical key presses as UPPERCASE ``KeySym``
    members (``KeySym.H.name`` is ``"H"``, not ``"h"`` - and
    ``KeySym.h`` is a Python alias whose ``.name`` is also
    ``"H"``). Without ``.lower()`` every press would miss the
    lowercase-keyed dispatch table and the player would not move.

    The ``getattr(..., "name", "")`` belt-and-suspenders means a
    future tcod build that produces an event whose ``sym`` lacks a
    ``.name`` attribute (e.g. an extension-event subclass) falls
    through to an empty string and returns ``None`` instead of
    crashing with AttributeError.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return None
    sym_name: str = getattr(event.sym, 'name', '').lower()
    return world.MOVE_KEYS.get(sym_name)


def _is_q_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``Q`` key.

    Routes Q through a module-level helper so the smoke test can
    regression-guard the KeySym name lookup. Mirrors
    :func:`_movement_action`'s pattern of being a pure no-side-effect
    helper, so the dispatcher in :func:`_run_game` stays
    declarative. ``getattr(..., "name", "")`` belt-and-suspenders
    against a hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    return getattr(event.sym, 'name', '') == 'Q'


def _is_m_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``M`` key (or its
    lowercase alias).

    Routes M (map / navigation overlay) through a module-level
    helper so the smoke test can regression-guard the KeySym name
    lookup, mirroring :func:`_is_q_press` exactly. Lowercase ``m``
    and uppercase ``M`` both open the system-map overlay; anything
    else returns False so the dispatcher can route through movement
    + planet-bump handlers.

    Why M and not N: the original implementation used ``N``/``n``,
    but ``n`` is in :data:`world.VIM_DELTAS` as a south-east
    diagonal, so the map overlay silently shadowed vim movement in
    city mode and confused the player. ``M``/``m`` is unused by
    vim movement so it's a clean pick.
    ``getattr(..., "name", "")`` belt-and-suspenders against a
    hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    return sym_name in ('M', 'm')


def _is_period_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``.`` key (period).

    Period = wait one turn. In space mode this triggers the same
    post-move tick logic (combat detection, pirate movement, shield
    regen) without actually moving the player ship.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    return getattr(event.sym, 'name', '') == 'PERIOD'


def _is_g_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``G`` key (or its
    lowercase alias).

    Routes G (goto / auto-nav) through a module-level helper so
    the smoke test can regression-guard the KeySym name lookup,
    mirroring :func:`_is_m_press` exactly. Lowercase ``g`` and
    uppercase ``G`` both open the goto-target overlay; anything
    else returns False so the dispatcher can route through
    movement + planet-bump handlers.

    ``G``/``g`` is unused by vim movement so it's a clean pick.
    ``getattr(..., "name", "")`` belt-and-suspenders against a
    hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    return sym_name in ('G', 'g')


def _is_p_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``P`` key (or its
    lowercase alias).

    Routes P (pickup) through a module-level helper. Lowercase ``p``
    and uppercase ``P`` both pick up nearby loot; anything else
    returns False so space-mode G remains dedicated to Go To.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    return sym_name in ('P', 'p')


def _is_i_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``I`` key (or its
    lowercase alias).

    Routes I (inventory / cargo menu) through a module-level helper.
    Lowercase ``i`` and uppercase ``I`` both open the cargo-overlay
    modal; anything else returns False.

    ``I``/``i`` is unused by vim movement so it's a clean pick.
    ``getattr(..., "name", "")`` belt-and-suspenders against a
    hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    return sym_name in ('I', 'i')


def _is_t_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``T`` key (or its
    lowercase alias).

    Routes T (transmit / comms) through a module-level helper so the
    smoke test can regression-guard the KeySym name lookup,
    mirroring :func:`_is_i_press` exactly. Lowercase ``t`` and
    uppercase ``T`` both open the comms panel; anything
    else returns False so the dispatcher can route through
    movement + planet-bump handlers.

    ``T``/``t`` is unused by vim movement so it's a clean pick.
    ``getattr(..., "name", "")`` belt-and-suspenders against a
    hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    return sym_name in ('T', 't')


def _is_c_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``C`` key (or its
    lowercase alias).

    Routes C (Character screen) through a module-level helper.
    Lowercase ``c`` and uppercase ``C`` both open the character
    sheet; anything else returns False.

    ``C``/``c`` is unused by vim movement so it's a clean pick.
    ``getattr(..., "name", "")`` belt-and-suspenders against a
    hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    return sym_name in ('C', 'c')


def _is_f_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``F`` key (or its
    lowercase alias).

    Routes F (faction standings viewer) through a module-level helper.
    Lowercase ``f`` and uppercase ``F`` both open the faction viewer;
    anything else returns False.

    ``F``/``f`` is unused by vim movement so it's a clean pick.
    ``getattr(..., "name", "")`` belt-and-suspenders against a
    hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    return sym_name in ('F', 'f')


def _is_shift_press(event: tcod.event.Event, key_name: str) -> bool:
    """Return whether a key event has the requested key plus Shift."""
    if not isinstance(event, tcod.event.KeyDown):
        return False
    if getattr(event.sym, 'name', '') != key_name:
        return False
    mod = getattr(event, 'mod', 0)
    shift = tcod.event.Modifier.LSHIFT.value | tcod.event.Modifier.RSHIFT.value
    return bool(mod & shift)


def _is_shift_x_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` with Shift+X.

    Used in dev mode (``SPACEHACK_DEV``) to award bonus XP.
    """
    return _is_shift_press(event, 'X')


def _is_question_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``?`` key.

    On most platforms SDL reports ``KeySym.SLASH`` (the physical
    ``/`` key) *plus* a shift modifier, not ``KeySym.QUESTION``.
    We check for both patterns:

    * ``'QUESTION'`` — direct match (some platforms / tcod builds).
    * ``'SLASH'`` + shift modifier (LSHIFT | RSHIFT) — universal.

    Unshifted ``/`` (``KeySym.SLASH`` without a shift modifier)
    returns False so plain-slash never opens the guide.

    ``getattr(..., "name", "")`` belt-and-suspenders against a
    hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    if sym_name == 'QUESTION':
        return True
    if sym_name == 'SLASH':
        mod = getattr(event, 'mod', 0)
        shift = tcod.event.Modifier.LSHIFT.value | tcod.event.Modifier.RSHIFT.value
        return bool(mod & shift)
    return False


def _is_shift_r_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` with Shift+R.

    Dev-mode only (``SPACEHACK_DEV``): fully reveals dungeon fog.
    """
    return _is_shift_press(event, 'R')


def _is_shift_d_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` with Shift+D.

    Dev-mode only (``SPACEHACK_DEV``): skips 30 days of world clock
    so main-quest time gates can be playtested without waiting real
    minutes (see docs/design/in_progress/07_DESIGN_MAIN_QUEST.md).
    """
    return _is_shift_press(event, 'D')


def _is_shift_o_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` with Shift+O.

    Dev-mode only (``SPACEHACK_DEV``): advances Act 0 to the state
    where the Mars door can be opened. The caller applies the
    environment-variable gate and mutates the quest context.
    """
    return _is_shift_press(event, 'O')


def _try_open_guide(event: tcod.event.Event, ctx) -> bool:
    """Open the game guide if ``?`` was pressed.

    Returns ``True`` if the guide was opened (caller should return its
    modal's ``IGNORE`` outcome). Keeps the lazy import of
    ``_run_help_guide`` in one place rather than repeating it at every
    call site across the codebase.
    """
    if _is_question_press(event):
        from .help import _run_help_guide
        _run_help_guide(ctx)
        return True
    return False
