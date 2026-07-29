"""Planet-bump dialog — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import solar_system as solar_system_module
from .. import message_log
from ..game_context import GameContext
from ..engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide


class PlanetMenuOutcome(Enum):
    """Result of the planet-bump dialog (single 'Land' option)."""
    IGNORE = auto()
    LAND = auto()
    BACK = auto()
    QUIT = auto()


def render_planet_menu(console: tcod.console.Console, ctx: GameContext, planet_obj: solar_system_module.Planet, *, screen_width: int = SCREEN_WIDTH, screen_height: int = SCREEN_HEIGHT, has_port: bool = True) -> None:
    """Paint the planet-bump dialog.

    Centered title + description, then a single ``Land`` option
    via :func:`ui.render_selectable_list` (or ``No port`` text
    when ``has_port`` is False).
    """
    console.clear()
    title_y = screen_height // 4
    console.print(x=ui.centered_x(planet_obj.name, screen_width), y=title_y, string=planet_obj.name, fg=ui.COLOR_TITLE)
    desc_y = title_y + 2
    desc_rows = ui.wrap_text(planet_obj.description, screen_width - 4)
    for i, row in enumerate(desc_rows):
        console.print(x=ui.centered_x(row, screen_width), y=desc_y + i, string=row, fg=ui.COLOR_DESCRIPTION)
    _content_bottom = desc_y + max(1, len(desc_rows))
    if has_port:
        ui.render_selectable_list(
            console, screen_width, screen_height,
            title="",
            items=[("Land", "")],
            selected=0,
            title_y=_content_bottom + 1,
            hint="ENTER to land - ESC to fly away",
        )
    else:
        console.print(
            x=ui.centered_x("No port on this world.", screen_width),
            y=_content_bottom + 1,
            string="No port on this world.",
            fg=ui.COLOR_DESCRIPTION,
        )
        console.print(
            x=ui.centered_x("ENTER or ESC to fly past.", screen_width),
            y=_content_bottom + 3,
            string="ENTER or ESC to fly past.",
            fg=ui.COLOR_INSTRUCTION,
        )
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def update_planet_menu(event: tcod.event.Event, *, has_port: bool = True) -> PlanetMenuOutcome:
    """Map a single key event for the planet-bump dialog.

    ENTER -> LAND (if has_port) or BACK (no port).
    ESC -> BACK, Quit -> QUIT, anything else -> IGNORE.
    """
    if isinstance(event, tcod.event.Quit):
        return PlanetMenuOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return PlanetMenuOutcome.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return PlanetMenuOutcome.BACK
    if sym in ui._ENTER_SYMS:
        return PlanetMenuOutcome.LAND if has_port else PlanetMenuOutcome.BACK
    return PlanetMenuOutcome.IGNORE


def _run_planet_menu(ctx, planet_obj: solar_system_module.Planet) -> PlanetMenuOutcome:
    """Show the planet-bump modal for ``planet_obj``; return the chosen outcome.

    The ``Land`` option only appears if the planet has a registered
    port — see :func:`spacehack.data.planets.has_landable_port`.
    When the planet has no port the modal still shows so the player
    gets feedback that they bumped something, but ENTER closes the
    modal rather than triggering a landing.
    """
    from ..data.planets import has_landable_port
    has_port = has_landable_port(planet_obj.id)
    console = make_console()

    def _render() -> None:
        render_planet_menu(console, ctx, planet_obj, has_port=has_port)

    def _update(event) -> PlanetMenuOutcome:
        if _try_open_guide(event, ctx):
            return PlanetMenuOutcome.IGNORE
        return update_planet_menu(event, has_port=has_port)
    return ui.Modal(ctx.context, console).run(_render, _update)
