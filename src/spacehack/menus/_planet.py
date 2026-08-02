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
    """Result of the planet-bump dialog."""
    IGNORE = auto()
    LAND = auto()
    EXPLORE = auto()
    BACK = auto()
    QUIT = auto()


def _build_menu_items(
    planet_obj: solar_system_module.Planet,
    has_port: bool,
    explorable_sites: list[str],
) -> list[tuple[str, str, PlanetMenuOutcome]]:
    """Build the list of (label, description, outcome) triples for the planet menu.

    The order determines display order. ``Leave`` is always last.
    """
    items: list[tuple[str, str, PlanetMenuOutcome]] = []
    if has_port:
        items.append((f"Land on {planet_obj.name}", "Dock at the spaceport", PlanetMenuOutcome.LAND))
    for site_name in explorable_sites:
        items.append((f"Explore {site_name}", f"Descend into {planet_obj.name}'s {site_name.lower()}", PlanetMenuOutcome.EXPLORE))
    items.append(("Leave", "Fly past", PlanetMenuOutcome.BACK))
    return items


def render_planet_menu(
    console: tcod.console.Console,
    ctx: GameContext,
    planet_obj: solar_system_module.Planet,
    *,
    screen_width: int = SCREEN_WIDTH,
    screen_height: int = SCREEN_HEIGHT,
    items: list[tuple[str, str, PlanetMenuOutcome]],
    selected: int,
) -> None:
    """Paint the planet-bump dialog with a selectable list of actions."""
    console.clear()
    _content_x, _desc_w = ui.content_metrics(screen_width, HUD_WIDTH, col_x=2)
    desc_y = ui.screen_header(console, screen_width, planet_obj.name)
    desc_rows = ui.wrap_text(planet_obj.description, _desc_w)
    for i, row in enumerate(desc_rows):
        console.print(x=_content_x, y=desc_y + i, string=row, fg=ui.COLOR_DESCRIPTION)
    _content_bottom = desc_y + max(1, len(desc_rows))
    # Militia checkpoints run cargo scans on landing — warn before the
    # player commits. Teaches the mechanic through gameplay (approach).
    from ..data.planets import has_militia_presence as _hmp
    if _hmp(planet_obj.id):
        _warn = "MILITIA CHECKPOINT ACTIVE - INBOUND CARGO IS SUBJECT TO SCANS"
        console.print(
            x=_content_x,
            y=_content_bottom,
            string=_warn,
            fg=message_log.COLOR_IMPORTANT_EVENT,
        )
        _content_bottom += 1
    ui.render_selectable_list(
        console, screen_width, screen_height,
        title="",
        items=[(label, desc) for label, desc, _outcome in items],
        selected=selected,
        col_x=2,
        title_y=_content_bottom + 1,
    )
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def update_planet_menu(
    event: tcod.event.Event,
    *,
    items: list[tuple[str, str, PlanetMenuOutcome]],
    selected: int,
) -> tuple[PlanetMenuOutcome, int]:
    """Map a key event for the planet-bump dialog.

    Returns ``(outcome, new_selected)``. ``IGNORE`` outcome means the
    modal should keep running.
    """
    if isinstance(event, tcod.event.Quit):
        return (PlanetMenuOutcome.QUIT, selected)
    if not isinstance(event, tcod.event.KeyDown):
        return (PlanetMenuOutcome.IGNORE, selected)
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return (PlanetMenuOutcome.BACK, selected)
    if sym in (tcod.event.KeySym.UP, tcod.event.KeySym.K):
        return (PlanetMenuOutcome.IGNORE, max(0, selected - 1))
    if sym in (tcod.event.KeySym.DOWN, tcod.event.KeySym.J):
        return (PlanetMenuOutcome.IGNORE, min(len(items) - 1, selected + 1))
    if sym in ui._ENTER_SYMS:
        # Return the outcome associated with the selected item.
        if 0 <= selected < len(items):
            return (items[selected][2], selected)
        return (PlanetMenuOutcome.BACK, selected)
    return (PlanetMenuOutcome.IGNORE, selected)


def _run_planet_menu(ctx, planet_obj: solar_system_module.Planet) -> PlanetMenuOutcome:
    """Show the planet-bump modal for ``planet_obj``; return the chosen outcome.

    Builds the action list dynamically: ``Land`` (if the planet has a
    registered port), ``Explore <site>`` (if the planet has explorable
    dungeons/sites), and always ``Leave``.

    The player navigates with UP/DOWN and selects with ENTER.
    """
    from ..data.planets import has_landable_port, has_explorable_sites
    has_port = has_landable_port(planet_obj.id)
    explorable_sites = has_explorable_sites(planet_obj.id)
    # Main quest gate: surface exploration stays locked until its
    # quest beat unlocks it — Mars until the prologue signal; the
    # delve planets only while a chain delve step targets them (see
    # main_quest.surface_exploration_unlocked).
    from .. import main_quest as main_quest_module
    if not main_quest_module.surface_exploration_unlocked(ctx, planet_obj.id):
        explorable_sites = []
    items = _build_menu_items(planet_obj, has_port, explorable_sites)
    console = make_console()
    selected = 0

    def _render() -> None:
        render_planet_menu(console, ctx, planet_obj, items=items, selected=selected)

    def _update(event) -> PlanetMenuOutcome:
        nonlocal selected
        if _try_open_guide(event, ctx):
            return PlanetMenuOutcome.IGNORE
        outcome, new_selected = update_planet_menu(event, items=items, selected=selected)
        selected = new_selected
        return outcome

    return ui.Modal(ctx.context, console).run(_render, _update)
