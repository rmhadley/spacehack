"""Input helpers extracted from ``__main__.py``.

Contains the :class:`Outcome` enum, :func:`_run_pick`,
:func:`_run_confirm`, key-press predicates (``_is_q_press``,
``_is_m_press``, etc.), and the :func:`_vim_action` movement
mapper.  Everything here is a pure function or a short Modal
wrapper — no game state, no event-loop internals.
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


def _run_pick(context: tcod.context.Context, menu: ui.MenuScreen) -> tuple[Outcome, str | None]:
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


def _vim_action(event: tcod.event.Event) -> tuple[int, int] | None:
    """If ``event`` is a vim-movement KeyDown, return (dx, dy); else None.

    SDL/tcod reports physical letter key presses as UPPERCASE
    ``KeySym`` members (``KeySym.H.name`` is ``"H"``, not ``"h"`` -
    and ``KeySym.h`` is a Python alias whose ``.name`` is also
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
    return world.VIM_DELTAS.get(sym_name)


def _is_q_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``Q`` key.

    Routes Q through a module-level helper so the smoke test can
    regression-guard the KeySym name lookup. Mirrors
    :func:`_vim_action`'s pattern of being a pure no-side-effect
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


def _is_c_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``C`` key (or its
    lowercase alias).

    Routes C (cargo menu) through a module-level helper so the
    smoke test can regression-guard the KeySym name lookup,
    mirroring :func:`_is_m_press` exactly. Lowercase ``c`` and
    uppercase ``C`` both open the cargo-overlay modal; anything
    else returns False so the dispatcher can route through
    movement + planet-bump handlers.

    ``C``/``c`` is unused by vim movement so it's a clean pick.
    ``getattr(..., "name", "")`` belt-and-suspenders against a
    hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    return sym_name in ('C', 'c')


def _is_t_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``T`` key (or its
    lowercase alias).

    Routes T (transmit / comms) through a module-level helper so the
    smoke test can regression-guard the KeySym name lookup,
    mirroring :func:`_is_c_press` exactly. Lowercase ``t`` and
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
