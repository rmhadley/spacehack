"""Planet-bump dialog — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

from .. import solar_system as solar_system_module

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

def _run_pygame_planet_menu(ctx, planet_obj, items):
    """Run the dynamic planet action list through the Pygame worker."""
    from .. import pygame_menu, pygame_ui

    frames = tuple(
        pygame_menu.MenuFrame(
            title=planet_obj.name,
            body=planet_obj.description,
            items=tuple(
                pygame_menu.MenuItem(label, description, outcome.name)
                for label, description, outcome in items
            ),
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER select", "ESC leave",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=selected,
        )
        for selected in range(max(1, len(items)))
    )
    outcome, action, _selected = pygame_menu.run_for_context(
        ctx.context,
        frames,
        caption=f"spacehack - {planet_obj.name}",
    )
    if outcome == "GUIDE":
        from ..help import _run_help_guide
        _run_help_guide(ctx)
        return PlanetMenuOutcome.BACK
    if outcome == "SELECT":
        try:
            return PlanetMenuOutcome[action]
        except KeyError:
            return None
    if outcome == "QUIT":
        return PlanetMenuOutcome.QUIT
    return PlanetMenuOutcome.BACK

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
    result = _run_pygame_planet_menu(ctx, planet_obj, items)
    if result is None:
        raise RuntimeError("Planet menu returned no outcome")
    return result
