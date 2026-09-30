"""Ship hangar — tabbed modal runner.

One ``pygame_screen`` modal with SHIP / CARGO / LOADOUT tabs for the
player's owned ship while in city mode (the C-screen pattern): TAB
cycles tabs, ENTER launches on the SHIP tab or jettisons a selected
good on the CARGO tab, ESC walks away. Also exports ``_find_hangar_ship``
used by the landing animation code in ``__main__.py``.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

from .. import world
from .. import ship as ship_module

class ShipMenuAction(Enum):
    """Which sub-modal of the hangar menu the player triggers."""
    IGNORE = auto()
    VIEW = auto()
    LOADOUT = auto()
    REFUEL = auto()
    SELL = auto()
    LAUNCH = auto()
    BACK = auto()
    QUIT = auto()

_HANGAR_TABS: tuple[str, ...] = ("SHIP", "CARGO", "LOADOUT")
"""The single source of truth for the hangar tab names and count."""

# ---------------------------------------------------------------------------
# Effective-stat helpers (sums base + module bonuses)
# ---------------------------------------------------------------------------

def _effective_shields(ship_spec, owned) -> int:
    """Sum base shield max + effective module max_shield_bonuses."""
    from ..combat._stats import _calc_max_shields
    return _calc_max_shields(
        ship_spec, getattr(owned, 'modules', ()) or (),
    )

def _effective_power_gen(ship_spec, owned) -> int:
    """Sum base power gen + effective module power_gen_bonuses."""
    from ..combat._stats import _calc_power_gen
    return _calc_power_gen(
        ship_spec, getattr(owned, 'modules', ()) or (),
    )


def _loadout_section(ctx, owned, ship):
    """Build the LOADOUT tab's body, rows, and footer.

    Doc 56 SETTLED 20 (playtest 2026-09-30, amends 19 for the hangar):
    a list of the active weapons and modules with their stats
    attached — tier-coloured names, the same stat lines the editor's
    tooltip shows. The letter grid stays on the mechanic's tab and
    editor."""
    from .. import pygame_ui
    from ..menus._grid_editor import entry_view

    muted_color = pygame_ui.DEFAULT_PALETTE.muted
    body: list[str] = []
    body_runs: list[tuple | None] = []
    for label, entries in (
        ("WEAPONS", getattr(owned, "weapons", ()) or ()),
        ("MODULES", getattr(owned, "modules", ()) or ()),
    ):
        if not entries:
            continue
        body.append(label)
        body_runs.append(((label, muted_color),))
        for entry in entries:
            try:
                name, stats, color = entry_view(entry)
            except KeyError:
                continue
            body.append(f"{name} - {stats}")
            body_runs.append((
                (name, color), (f" - {stats}", None),
            ))
    if not body:
        body.append("Nothing installed.")
        body_runs.append(None)
    rows = ()
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "TAB ship", "ESC back", pygame_ui.GUIDE_HINT,
    ),)
    return tuple(body), rows, footer, tuple(body_runs)

def _faction_progress_bar(rep: int, width: int = 31) -> str:
    """Return the CP437-safe centered faction reputation bar."""
    half = width // 2
    neg_fill = int((abs(rep) / 100) * half) if rep < 0 else 0
    pos_fill = int((rep / 100) * half) if rep >= 0 else 0
    neg_fill = max(0, min(half, neg_fill))
    pos_fill = max(0, min(half, pos_fill))
    left = ["#" if neg_fill >= half - index else "-" for index in range(half)]
    right = ["#" if pos_fill >= index + 1 else "-" for index in range(half)]
    return "".join(left + ["|"] + right)

async def _run_faction_view(ctx) -> None:
    """Show faction standings with the refreshed Pygame presentation."""
    from .. import pygame_faction

    while True:
        outcome = await pygame_faction.run_for_context(ctx.context, ctx)
        if outcome == "GUIDE":
            from ..help import _open_context_guide
            await _open_context_guide(ctx, "NPCs & Factions")
            continue
        return

def _launch_row():
    """Build the Launch row that lives at the bottom of the SHIP tab."""
    from .. import pygame_screen

    return pygame_screen.ScreenRow(
        "Launch", "Leave the hangar and enter space.", "LAUNCH",
    )

def _ship_section(ctx, owned, ship):
    """Build the SHIP tab's body, rows, and footer."""
    from .. import pygame_ui

    max_cargo = ship_module.effective_max_cargo(ship, owned, ctx)
    _hull_cur, _hull_max = ship_module.hull_cur_max(owned, ship)
    body = (
        ship.description,
        "",
        f"Fuel: {owned.fuel} / {ship.max_fuel}",
        f"Hull: {_hull_cur} / {_hull_max}",
        f"Speed: {ship_module.effective_speed(ship, owned)}",
        f"Shields: {_effective_shields(ship, owned)}",
        f"Power: {_effective_power_gen(ship, owned)}",
        f"Cargo: {owned.cargo_used} / {max_cargo}",
        pygame_ui.credits_label(ctx.stats.credits),
        "",
    )
    rows = (_launch_row(),)
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "ENTER launch", "TAB cargo",
        "ESC back", pygame_ui.GUIDE_HINT,
    ),)
    return body, rows, footer


def _cargo_section(ctx, owned, ship):
    """Build the CARGO tab's body, rows, and footer."""
    from .. import pygame_ui
    from ..trade import _cargo_body, _cargo_rows

    max_cargo = ship_module.effective_max_cargo(ship, owned, ctx)
    rows = _cargo_rows(owned)
    body = _cargo_body(ctx, owned, max_cargo)
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "ENTER jettison", "TAB loadout",
        "ESC back", pygame_ui.GUIDE_HINT,
    ),)
    return body, rows, footer


def _ship_hangar_frame(ctx, ship: ship_module.Ship, tab: int, selected: int):
    """Build one tabbed hangar snapshot (SHIP / CARGO / LOADOUT tabs)."""
    from .. import pygame_screen, pygame_ui

    owned = ctx.player_owned_ship
    if owned is None:
        return pygame_screen.ScreenFrame(
            "YOUR SHIP", ("No ship equipped.",), (),
            (pygame_ui.modal_hint("ESC back", pygame_ui.GUIDE_HINT),),
        )
    title = f"YOUR {ship_module.ship_display_name(owned).upper()}"
    sections = {
        0: _ship_section,
        1: _cargo_section,
        2: _loadout_section,
    }
    body, rows, footer, *extra = sections.get(tab, _loadout_section)(ctx, owned, ship)
    body_runs = extra[0] if extra else ()
    return pygame_screen.ScreenFrame(
        title, body, rows, footer, selected,
        tabs=_HANGAR_TABS, active_tab=tab, body_runs=body_runs,
    )

async def _run_pygame_ship_hangar(ctx, ship: ship_module.Ship) -> ShipMenuAction | None:
    """Run the tabbed hangar through the shared Pygame screen.

    TAB cycles SHIP → CARGO → LOADOUT → SHIP; ENTER launches from the
    SHIP tab or jettisons a selected good on the CARGO tab; ``?`` reopens
    the guide; ESC walks away.
    """
    from .. import pygame_screen

    tab = 0
    selected = 0
    while True:
        outcome, action, selected = await pygame_screen.run_for_context(
            getattr(ctx, "context", ctx),
            _ship_hangar_frame(ctx, ship, tab, selected),
            caption="spacehack - ship hangar",
        )
        if outcome == "GUIDE":
            from ..help import _open_context_guide
            await _open_context_guide(ctx, "Ships & Equipment")
            continue
        _next_tab = pygame_screen.cycled_tab(outcome, tab, len(_HANGAR_TABS))
        if _next_tab is not None:
            tab, selected = _next_tab, 0
            continue
        if outcome in {"PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "QUIT":
            return ShipMenuAction.QUIT
        if outcome == "SELECT":
            if action == "LAUNCH":
                return ShipMenuAction.LAUNCH
            if tab == 1:
                from ..trade import _apply_jettison
                owned = ctx.player_owned_ship
                if owned is not None and await _apply_jettison(ctx, owned, action):
                    continue
            return None
        return ShipMenuAction.BACK

async def _run_ship_menu(ctx, ship: ship_module.Ship) -> ShipMenuAction:
    """Show the tabbed hangar modal for ``ship``; return the chosen action.

    One tabbed screen (SHIP / CARGO / LOADOUT, the C-screen pattern): no
    nested sub-modals. TAB cycles tabs, ENTER launches on the SHIP tab
    or jettisons on the CARGO tab, ESC walks away.
    """
    return await _run_pygame_ship_hangar(ctx, ship)

def _find_hangar_ship(city_game_map: world.GameMap, player_owned_ship: ship_module.OwnedShip | None) -> world.Entity | None:
    """Return the player's owned hangar ship entity in ``city_game_map``."""
    if player_owned_ship is None:
        return None
    return next((e for e in city_game_map.entities if e.owned and e.ship_id == player_owned_ship.ship_id), None)
