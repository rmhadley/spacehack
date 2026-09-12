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
    DIG = auto()
    BACK = auto()
    QUIT = auto()

def _build_menu_items(
    planet_obj: solar_system_module.Planet,
    has_port: bool,
    explorable_sites: list[str],
    discovered_sites: list[dict] | None = None,
) -> list[tuple[str, str, str]]:
    """Build the list of (label, description, action) triples for the planet menu.

    The order determines display order. ``Leave`` is always last. The
    action is the outcome name, or ``DIG:<site id>`` for a discovered
    dig site (doc 42 phase 4) — one row per site, hidden until found.
    """
    discovered = discovered_sites or []
    items: list[tuple[str, str, str]] = []
    if has_port:
        items.append((f"Land on {planet_obj.name}", "Dock at the spaceport", PlanetMenuOutcome.LAND.name))
    for site_name in explorable_sites:
        items.append((f"Explore {site_name}", f"Descend into {planet_obj.name}'s {site_name.lower()}", PlanetMenuOutcome.EXPLORE.name))
    for site in discovered:
        items.append((f"Explore {site['name']}", f"Dig into {planet_obj.name}'s {site['name'].lower()}", f"DIG:{site['id']}"))
    items.append(("Leave", "Fly past", PlanetMenuOutcome.BACK.name))
    return items

def _run_pygame_planet_menu(ctx, planet_obj, items):
    """Run the dynamic planet action list through the Pygame worker."""
    from .. import pygame_menu, pygame_ui

    frames = tuple(
        pygame_menu.MenuFrame(
            title=planet_obj.name,
            body=planet_obj.description,
            items=tuple(
                pygame_menu.MenuItem(label, description, action)
                for label, description, action in items
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
        return PlanetMenuOutcome.BACK, None
    if outcome == "SELECT":
        if action and action.startswith("DIG:"):
            return PlanetMenuOutcome.DIG, action[len("DIG:"):]
        try:
            return PlanetMenuOutcome[action], None
        except KeyError:
            return None, None
    if outcome == "QUIT":
        return PlanetMenuOutcome.QUIT, None
    return PlanetMenuOutcome.BACK, None

def _discovered_on(ctx, planet_id: str) -> list[dict]:
    """The player's discovered dig sites on THIS planet — the menu's
    per-planet row filter (hidden until found, SETTLED 28)."""
    return [
        site for site in getattr(ctx, "discovered_sites", ())
        if site.get("planet") == planet_id
    ]

def _run_planet_menu(ctx, planet_obj: solar_system_module.Planet) -> tuple[PlanetMenuOutcome, str | None]:
    """Show the planet-bump modal for ``planet_obj``.

    Returns ``(outcome, site_id)`` — the site id is set only for a
    picked dig row. Builds the action list dynamically: ``Land`` (if
    the planet has a registered port), ``Explore <site>`` (authored
    explorable sites), one ``Explore <site>`` row per discovered dig
    site (hidden until found), and always ``Leave``.

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
    discovered = _discovered_on(ctx, planet_obj.id)
    items = _build_menu_items(planet_obj, has_port, explorable_sites, discovered)
    result, site_id = _run_pygame_planet_menu(ctx, planet_obj, items)
    if result is None:
        raise RuntimeError("Planet menu returned no outcome")
    return result, site_id
