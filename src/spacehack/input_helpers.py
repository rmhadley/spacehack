"""Input helpers extracted from ``__main__.py``.

Contains the :class:`Outcome` enum, :func:`_run_pick`,
:func:`_run_confirm`, key-press predicates (``_is_q_press``,
``_is_m_press``, etc.), and the :func:`_movement_action`
movement mapper.  Everything here is a pure function — no game state,
no event-loop internals.
"""

from __future__ import annotations
from enum import Enum, auto
from .pygame_runtime import PygameContext
from . import pygame_engine
from . import ui
from . import pygame_ui
from . import world
from .data.species import find_species
from .data.classes import find_class

class Outcome(Enum):
    """What happened at the end of a per-creation-screen loop iteration.

    ``IGNORE`` is the standard "keep polling" signal: an update
    function returns :attr:`IGNORE` for events it doesn't act on, and
    the presentation loop keeps polling. Every other member
    terminates the loop and propagates back to the caller.
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
        hints=(pygame_ui.modal_hint(
            "ENTER begin journey", "ESC start over",
        ),),
        selected=0,
    )

def _is_character_menu(menu: ui.MenuScreen) -> bool:
    """Return whether a menu is one of the two character-creation pickers."""
    return menu.title in {"Choose Your Species", "Choose Your Class"}

def _run_pygame_pick(context, menu: ui.MenuScreen) -> tuple[Outcome, str | None] | None:
    """Run a character picker in the shared Pygame window."""
    from . import pygame_menu

    frames = _pygame_pick_frames(menu)
    if not frames:
        return None
    while True:
        outcome, action, _selected = pygame_menu.run_for_context(
            context,
            frames,
            caption=f"spacehack - {menu.title.lower()}",
        )
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
    """Run character confirmation in the shared Pygame window."""
    from . import pygame_menu

    species = find_species(species_id)
    klass = find_class(class_id)
    frame = _pygame_confirm_frame(species, klass)
    while True:
        outcome, action, _selected = pygame_menu.run_for_context(
            context,
            (frame,),
            caption="spacehack - character creation",
        )
        if outcome == "GUIDE":
            continue
        if outcome == "SELECT" and action == "CONFIRM":
            return Outcome.CONFIRM
        if outcome == "BACK":
            return Outcome.BACK
        if outcome == "QUIT":
            return Outcome.QUIT
        return None

def _run_pick(context: PygameContext, menu: ui.MenuScreen) -> tuple[Outcome, str | None]:
    """Run a character picker in the shared Pygame window."""
    if not _is_character_menu(menu):
        raise RuntimeError("Character picker requires the shared Pygame runtime")
    result = _run_pygame_pick(context, menu)
    if result is None:
        raise RuntimeError("Character picker returned no outcome")
    return result

def _run_confirm(context: PygameContext, species_id: str, class_id: str) -> Outcome:
    """Run character confirmation in the shared Pygame window."""
    result = _run_pygame_confirm(context, species_id, class_id)
    if result is None:
        raise RuntimeError("Character confirmation returned no outcome")
    return result

def _movement_action(event: pygame_engine.PygameInputEvent) -> tuple[int, int] | None:
    """If ``event`` is a project keydown for movement, return ``(dx, dy)``."""
    if not pygame_engine.is_keydown(event):
        return None
    return world.MOVE_KEYS.get(pygame_engine.movement_key_name(event))

def _is_q_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``Q`` key.

    Routes Q through a module-level helper so the smoke test can
    regression-guard the KeySym name lookup. Mirrors
    :func:`_movement_action`'s pattern of being a pure no-side-effect
    helper, so the dispatcher in :func:`_run_game` stays
    declarative.    The project event already exposes a normalized key name, so this helper
    stays independent of backend event classes.

    """
    return pygame_engine.is_keydown(event) and event.key_name == 'q'

def _is_m_press(event: pygame_engine.PygameInputEvent) -> bool:
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
    The project event already exposes a normalized key name, so this helper
    stays independent of backend event classes.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'm'

def _is_period_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``.`` key (period).

    Period = wait one turn. In space mode this triggers the same
    post-move tick logic (combat detection, pirate movement, shield
    regen) without actually moving the player ship.
    """
    return pygame_engine.is_keydown(event) and event.key_name in {'.', 'period'}

def _is_g_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``G`` key (or its
    lowercase alias).

    Routes G (goto / auto-nav) through a module-level helper so
    the smoke test can regression-guard the KeySym name lookup,
    mirroring :func:`_is_m_press` exactly. Lowercase ``g`` and
    uppercase ``G`` both open the goto-target overlay; anything
    else returns False so the dispatcher can route through
    movement + planet-bump handlers.

    ``G``/``g`` is unused by vim movement so it's a clean pick.
    The project event already exposes a normalized key name, so this helper
    stays independent of backend event classes.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'g'

def _is_o_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``O`` key.

    Routes O (dungeon auto-explore) through a module-level helper so
    the smoke test can regression-guard the KeySym name lookup,
    mirroring :func:`_is_g_press` exactly. The project event
    normalizes key names to lowercase; Shift+O is consumed earlier by
    the dev-mode dispatcher (``_is_shift_o_press``), so this helper
    only ever sees the plain key.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'o'

def _is_r_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a plain ``R`` key press."""
    return pygame_engine.is_keydown(event) and event.key_name == 'r'

def _is_p_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``P`` key (or its
    lowercase alias).

    Routes P (pickup) through a module-level helper. Lowercase ``p``
    and uppercase ``P`` both pick up nearby loot; anything else
    returns False so space-mode G remains dedicated to Go To.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'p'

def _is_backslash_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a KeyDown for the backslash key."""
    return pygame_engine.is_keydown(event) and event.key_name in {
        "backslash", "nonusbackslash", "\\",
    }

def _is_i_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``I`` key (or its
    lowercase alias).

    Routes I (inventory / cargo menu) through a module-level helper.
    Lowercase ``i`` and uppercase ``I`` both open the cargo-overlay
    modal; anything else returns False.

    ``I``/``i`` is unused by vim movement so it's a clean pick.
    The project event already exposes a normalized key name, so this helper
    stays independent of backend event classes.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'i'

def _is_t_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``T`` key (or its
    lowercase alias).

    Routes T (transmit / comms) through a module-level helper so the
    smoke test can regression-guard the KeySym name lookup,
    mirroring :func:`_is_i_press` exactly. Lowercase ``t`` and
    uppercase ``T`` both open the comms panel; anything
    else returns False so the dispatcher can route through
    movement + planet-bump handlers.

    ``T``/``t`` is unused by vim movement so it's a clean pick.
    The project event already exposes a normalized key name, so this helper
    stays independent of backend event classes.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 't'

def _is_c_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``C`` key (or its
    lowercase alias).

    Routes C (Character screen) through a module-level helper.
    Lowercase ``c`` and uppercase ``C`` both open the character
    sheet; anything else returns False.

    ``C``/``c`` is unused by vim movement so it's a clean pick.
    The project event already exposes a normalized key name, so this helper
    stays independent of backend event classes.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'c'

def _is_f_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``F`` key (or its
    lowercase alias).

    Routes F (faction standings viewer) through a module-level helper.
    Lowercase ``f`` and uppercase ``F`` both open the faction viewer;
    anything else returns False.

    ``F``/``f`` is unused by vim movement so it's a clean pick.
    The project event already exposes a normalized key name, so this helper
    stays independent of backend event classes.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'f'

def _is_shift_press(event: pygame_engine.PygameInputEvent, key_name: str) -> bool:
    """Return whether a key event has the requested key plus Shift."""
    return (
        pygame_engine.is_keydown(event)
        and event.key_name == key_name.lower()
        and pygame_engine.has_shift(event)
    )

def _is_shift_x_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` with Shift+X.

    Used in dev mode (``SPACEHACK_DEV``) to award bonus XP.
    """
    return _is_shift_press(event, 'X')

def _is_question_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``?`` key.

    On most platforms SDL reports ``KeySym.SLASH`` (the physical
    ``/`` key) *plus* a shift modifier, not ``KeySym.QUESTION``.
    We check for both patterns:

    * ``'QUESTION'`` — direct match (some platforms).
    * ``'SLASH'`` + shift modifier (LSHIFT | RSHIFT) — universal.

    Unshifted ``/`` (``KeySym.SLASH`` without a shift modifier)
    returns False so plain-slash never opens the guide.

    The project event already exposes a normalized key name, so this helper
    stays independent of backend event classes.
    """
    return pygame_engine.guide_key(event)

def _is_shift_r_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` with Shift+R.

    Dev-mode only (``SPACEHACK_DEV``): fully reveals dungeon fog.
    """
    return _is_shift_press(event, 'R')

def _is_shift_d_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` with Shift+D.

    Dev-mode only (``SPACEHACK_DEV``): skips 30 days of world clock
    so main-quest time gates can be playtested without waiting real
    minutes (see docs/design/in_progress/07_DESIGN_MAIN_QUEST.md).
    """
    return _is_shift_press(event, 'D')

def _is_shift_o_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a ``KeyDown`` with Shift+O.

    Dev-mode only (``SPACEHACK_DEV``): advances Act 0 to the state
    where the Mars door can be opened. The caller applies the
    environment-variable gate and mutates the quest context.
    """
    return _is_shift_press(event, 'O')

def _is_f3_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a KeyDown for the F3 key.

    Dev-mode only (``SPACEHACK_DEV``): toggles the city debug overlay
    showing camera coords, player tile, district, transit stations,
    buildings, and NPC count.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'f3'

def _is_f5_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a KeyDown for the F5 key.

    Dev-mode only (``SPACEHACK_DEV``): re-parses the story-text JSON
    overlay (src/spacehack/data/text/) so dialogue edits are visible
    without restarting the game.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'f5'

def _is_f6_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a KeyDown for the F6 key.

    Dev-mode only (``SPACEHACK_DEV``): writes the quicksave checkpoint
    (saves/quicksave.json), independent of the autosave flow.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'f6'

def _is_f9_press(event: pygame_engine.PygameInputEvent) -> bool:
    """True iff ``event`` is a KeyDown for the F9 key.

    Dev-mode only (``SPACEHACK_DEV``): restores the quicksave checkpoint
    written by F6, replacing the live game state in place.
    """
    return pygame_engine.is_keydown(event) and event.key_name == 'f9'

def _try_open_guide(event: pygame_engine.PygameInputEvent, ctx) -> bool:
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
