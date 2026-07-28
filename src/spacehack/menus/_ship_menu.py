"""Ship hangar menu — render, update, and modal runner.

Provides the ``View Cargo`` / ``Launch`` options for the player's
owned ship while in city mode. Also exports ``_find_hangar_ship``
used by the landing animation code in ``__main__.py``.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import world
from .. import ship as ship_module
from .. import message_log
from ..game_context import GameContext
from ..engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide


class ShipMenuAction(Enum):
    """Which sub-modal of the hangar menu the player triggers."""
    IGNORE = auto()
    VIEW = auto()
    REFUEL = auto()
    SELL = auto()
    LAUNCH = auto()
    BACK = auto()
    QUIT = auto()


SHIP_MENU_OPTIONS: tuple[str, ...] = ('View Cargo', 'Launch')


def render_ship_menu(console: tcod.console.Console, ctx: GameContext, ship: ship_module.Ship, selected: int = 0, *, screen_width: int, screen_height: int) -> None:
    """Paint the 2-option hangar ship menu via :func:`ui.render_selectable_list`.

    Clears first so the modal fully replaces the city view; the
    caller re-paints city + HUD + msg log once the modal exits.
    Ship stats (description, fuel, hull, credits) are rendered
    directly above the list so they don't interfere with selection
    markers.
    """
    console.clear()
    title = f'Your {ship.name.upper()}'
    title_y = screen_height // 6
    console.print(x=ui.centered_x(title, screen_width), y=title_y, string=title, fg=ui.COLOR_TITLE)
    _stat_y = title_y + 2
    if ctx.player_owned_ship is not None:
        _lines = [
            ship.description,
            f'Fuel: {ctx.player_owned_ship.fuel} / {ship.max_fuel}',
            f'Hull: {ctx.player_owned_ship.hull_damage_pct}% damage',
            f'Credits: {ctx.stats.credits}$',
        ]
        for i, _line in enumerate(_lines):
            console.print(x=ui.centered_x(_line, screen_width), y=_stat_y + i, string=_line, fg=ui.COLOR_VALUE_WHITE)
    else:
        console.print(x=ui.centered_x(ship.description, screen_width), y=_stat_y, string=ship.description, fg=ui.COLOR_DESCRIPTION)
    _stats_height = 5 if ctx.player_owned_ship is not None else 1
    _list_title_y = _stat_y + _stats_height + 1
    _opt_items = [(opt, "") for opt in SHIP_MENU_OPTIONS]
    ui.render_selectable_list(
        console, screen_width, screen_height,
        title="",
        items=_opt_items,
        selected=selected,
        col_x=screen_width // 3,
        title_y=_list_title_y,
        title_fg=ui.COLOR_TITLE,
        row_spacing=2,
        item_fg_selected=ui.COLOR_OPTION_HIGHLIGHT,
        item_fg_normal=ui.COLOR_OPTION,
        hint='UP/DOWN / j,k navigate - ENTER select - ESC walk away',
    )
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def _ship_menu_navigate(event: tcod.event.Event, selected: int, n: int = 2) -> int | None:
    """If ``event`` drives hangar-menu nav, return the new
    ``selected`` index (modulo ``n`` options).

    Recognises both arrow keys and vim ``j`` / ``k``.
    """
    if n <= 0:
        return None
    if not isinstance(event, tcod.event.KeyDown):
        return None
    sym = event.sym
    sym_name: str = getattr(sym, 'name', '').lower()
    if sym in ui._UP_SYMS or sym_name == 'k':
        return (selected - 1) % n
    if sym in ui._DOWN_SYMS or sym_name == 'j':
        return (selected + 1) % n
    return None


def update_ship_menu(event: tcod.event.Event, selected: int) -> ShipMenuAction:
    """Map a single event for the hangar menu.

    Pure dispatcher: UP/DOWN navigation is handled by the caller.
    ESC -> BACK, Enter -> action, Quit -> QUIT.
    """
    if isinstance(event, tcod.event.Quit):
        return ShipMenuAction.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return ShipMenuAction.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return ShipMenuAction.BACK
    if sym in ui._ENTER_SYMS:
        return ShipMenuAction.VIEW if selected == 0 else ShipMenuAction.LAUNCH
    return ShipMenuAction.IGNORE


def _run_ship_menu(ctx, ship: ship_module.Ship) -> ShipMenuAction:
    """Show the hub-menu modal for ``ship``; return the chosen action.

    The menu has 2 options (View Cargo, Launch); the highlighted
    option (initially 0 = View Cargo) is mutated by UP / DOWN arrows
    AND vim ``j`` / ``k`` via :func:`_ship_menu_navigate`.
    """
    console = make_console()
    selected = 0
    n = len(SHIP_MENU_OPTIONS)

    def _render() -> None:
        render_ship_menu(console, ctx, ship, selected=selected, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> ShipMenuAction:
        nonlocal selected
        if _try_open_guide(event, ctx):
            return ShipMenuAction.IGNORE
        new = _ship_menu_navigate(event, selected, n)
        if new is not None:
            selected = new
            return ShipMenuAction.IGNORE
        return update_ship_menu(event, selected)
    while True:
        action = ui.Modal(ctx.context, console).run(_render, _update)
        if action is ShipMenuAction.VIEW:
            from ..trade import open_cargo as _open_cargo
            _open_cargo(ctx)
            continue
        return action  # LAUNCH, BACK, or QUIT


def _find_hangar_ship(city_game_map: world.GameMap, player_owned_ship: ship_module.OwnedShip | None) -> world.Entity | None:
    """Return the player's owned hangar ship entity in ``city_game_map``."""
    if player_owned_ship is None:
        return None
    return next((e for e in city_game_map.entities if e.owned and e.ship_id == player_owned_ship.ship_id), None)
