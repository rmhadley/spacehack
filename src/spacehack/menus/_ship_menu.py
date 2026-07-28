"""Ship hangar menu — render, update, and modal runner.

Provides the ``View Cargo`` / ``View Loadout`` / ``Launch`` options
for the player's owned ship while in city mode. Also exports
``_find_hangar_ship`` used by the landing animation code in
``__main__.py``.

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
    LOADOUT = auto()
    REFUEL = auto()
    SELL = auto()
    LAUNCH = auto()
    BACK = auto()
    QUIT = auto()


SHIP_MENU_OPTIONS: tuple[str, ...] = ('View Cargo', 'View Loadout', 'Launch')


def render_ship_menu(console: tcod.console.Console, ctx: GameContext, ship: ship_module.Ship, selected: int = 0, *, screen_width: int, screen_height: int) -> None:
    """Paint the hangar ship menu via :func:`ui.render_selectable_list`.

    Clears first so the modal fully replaces the city view; the
    caller re-paints city + HUD + msg log once the modal exits.
    Ship stats (description, fuel, hull, credits) are rendered
    directly above the list.
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


def _ship_menu_navigate(event: tcod.event.Event, selected: int, n: int = 3) -> int | None:
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

    ESC -> BACK, Enter -> action (index 0=Cargo, 1=Loadout, 2=Launch),
    Quit -> QUIT.
    """
    if isinstance(event, tcod.event.Quit):
        return ShipMenuAction.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return ShipMenuAction.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return ShipMenuAction.BACK
    if sym in ui._ENTER_SYMS:
        if selected == 0:
            return ShipMenuAction.VIEW
        elif selected == 1:
            return ShipMenuAction.LOADOUT
        else:
            return ShipMenuAction.LAUNCH
    return ShipMenuAction.IGNORE


def _run_loadout_view(ctx) -> None:
    """Show a centered read-only view of the player's ship loadout.

    Displays installed weapons with combat stats, installed modules,
    and key ship stats (fuel, hull, cargo, shields, power gen).
    """
    owned = ctx.player_owned_ship
    if owned is None:
        return
    ship_spec = ship_module.find_ship(owned.ship_id)
    console = make_console()
    max_w = SCREEN_WIDTH - HUD_WIDTH - 2

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[:max_w - 1] + '…'

    # Left margin for all content lines.
    LEFT_X = 6

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=LEFT_X, y=row, string=text, fg=fg, bg=(0, 0, 0))

    def _render() -> None:
        console.clear()
        from ..data.weapons import find_weapon as _fw
        from ..data.modules import find_module as _fm

        cy = (SCREEN_HEIGHT - MSG_LOG_HEIGHT) // 2 - 4

        # Title (centered)
        title_text = f"YOUR {ship_spec.name.upper()} — LOADOUT"
        console.print(x=ui.centered_x(title_text, SCREEN_WIDTH), y=cy, string=title_text, fg=ui.COLOR_TITLE)
        cy += 2

        # Weapons
        wpn_count = len(owned.weapons)
        wpn_slots = ship_spec.weapon_slots
        paint(cy, f"Weapons ({wpn_count}/{wpn_slots}):", fg=ui.COLOR_VALUE_WHITE)
        cy += 1
        if wpn_count == 0:
            paint(cy, "  (none installed)", fg=ui.COLOR_VALUE_DIM)
            cy += 1
        else:
            for wid in owned.weapons:
                try:
                    ws = _fw(wid)
                    line = f"  {ws.name}  dmg:{ws.damage}  acc:{ws.accuracy}%  range:{ws.min_range}-{ws.max_range}"
                except KeyError:
                    line = f"  {wid} (unknown)"
                paint(cy, fit(line), fg=ui.COLOR_OPTION)
                cy += 1

        cy += 1

        # Modules
        mod_count = len(owned.modules)
        mod_slots = ship_spec.module_slots
        paint(cy, f"Modules ({mod_count}/{mod_slots}):", fg=ui.COLOR_VALUE_WHITE)
        cy += 1
        if mod_count == 0:
            paint(cy, "  (none installed)", fg=ui.COLOR_VALUE_DIM)
            cy += 1
        else:
            for mid in owned.modules:
                try:
                    ms = _fm(mid)
                    paint(cy, f"  {ms.name}", fg=ui.COLOR_OPTION)
                    cy += 1
                    paint(cy, f"    {ms.description}", fg=ui.COLOR_VALUE_DIM)
                    cy += 1
                except KeyError:
                    paint(cy, f"  {mid} (unknown)", fg=ui.COLOR_VALUE_DIM)
                    cy += 1

        cy += 1

        # Stats
        paint(cy, "Stats:", fg=ui.COLOR_VALUE_WHITE)
        cy += 1
        stats_lines = [
            f"  Fuel: {owned.fuel} / {ship_spec.max_fuel}",
            f"  Hull: {owned.hull_damage_pct}% damage",
            f"  Cargo: {owned.cargo_used} / {ship_spec.max_cargo} used",
            f"  Shields: {ship_spec.base_shield_max} max",
            f"  Power Gen: {ship_spec.base_power_gen}",
        ]
        for line in stats_lines:
            paint(cy, fit(line), fg=ui.COLOR_VALUE_WHITE)
            cy += 1

        cy += 1
        paint(cy, "Press ESC to go back.", fg=ui.COLOR_INSTRUCTION)
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event: tcod.event.Event) -> ShipMenuAction | None:
        """Return IGNORE to keep polling, None to close."""
        if _try_open_guide(event, ctx):
            return ShipMenuAction.IGNORE
        if isinstance(event, tcod.event.Quit):
            return None
        if not isinstance(event, tcod.event.KeyDown):
            return ShipMenuAction.IGNORE
        if event.sym in ui._ESCAPE_SYMS:
            return None
        return ShipMenuAction.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)


def _run_ship_menu(ctx, ship: ship_module.Ship) -> ShipMenuAction:
    """Show the hub-menu modal for ``ship``; return the chosen action.

    The menu has 3 options (View Cargo, View Loadout, Launch);
    the highlighted option (initially 0 = View Cargo) is mutated by
    UP / DOWN arrows AND vim ``j`` / ``k`` via
    :func:`_ship_menu_navigate`.
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
        if action is ShipMenuAction.LOADOUT:
            _run_loadout_view(ctx)
            continue
        return action  # LAUNCH, BACK, or QUIT


def _find_hangar_ship(city_game_map: world.GameMap, player_owned_ship: ship_module.OwnedShip | None) -> world.Entity | None:
    """Return the player's owned hangar ship entity in ``city_game_map``."""
    if player_owned_ship is None:
        return None
    return next((e for e in city_game_map.entities if e.owned and e.ship_id == player_owned_ship.ship_id), None)
