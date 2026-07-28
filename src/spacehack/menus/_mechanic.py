"""Mechanic terminal menu — Refuel, Repair, and Loadout management.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import message_log
from .. import ship as ship_module
from ..game_context import GameContext
from ..engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide


class _MechanicOutcome(Enum):
    """Result of the mechanic-terminal menu."""
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()
    REFUEL = auto()
    REPAIR = auto()
    LOADOUT = auto()


def _run_mech_menu(ctx) -> None:
    """Show the mechanic-terminal menu with Refuel + Repair + Loadout options.

    Refuel buys fuel cells for the player's ship at the standard rate.
    Repair restores hull integrity at a cost based on damage.
    Loadout opens the split-screen part management modal.
    ESC / QUIT returns silently.
    """
    if ctx.player_owned_ship is None:
        ctx.log.add("You need a ship to use the mechanic terminal.")
        return

    console = make_console()
    selected = 0
    owned = ctx.player_owned_ship
    ship_rec = ship_module.find_ship(owned.ship_id)
    _MECH_OPTIONS = ["Refuel", "Repair", "Manage Loadout"]

    def _render() -> None:
        nonlocal selected
        console.clear()
        title_y = SCREEN_HEIGHT // 6
        console.print(x=ui.centered_x("MECHANIC TERMINAL", SCREEN_WIDTH), y=title_y, string="MECHANIC TERMINAL", fg=ui.COLOR_TITLE)
        stat_y = title_y + 2
        _stat_lines = [
            f"Ship: {ship_rec.name}",
            f"Fuel: {owned.fuel} / {ship_rec.max_fuel}  |  Hull: {owned.hull_damage_pct}% damage",
            f"Credits: {ctx.stats.credits}$",
        ]
        for i, _line in enumerate(_stat_lines):
            console.print(x=ui.centered_x(_line, SCREEN_WIDTH), y=stat_y + i, string=_line, fg=ui.COLOR_VALUE_WHITE)
        _opt_items = [(opt, "") for opt in _MECH_OPTIONS]
        _list_title_y = stat_y + len(_stat_lines) + 1
        ui.render_selectable_list(
            console, SCREEN_WIDTH, SCREEN_HEIGHT,
            title="",
            items=_opt_items,
            selected=selected,
            col_x=SCREEN_WIDTH // 4,
            title_y=_list_title_y,
            row_spacing=2,
            item_fg_selected=ui.COLOR_OPTION_HIGHLIGHT,
            item_fg_normal=ui.COLOR_OPTION,
            hint="UP/DOWN / j,k navigate - ENTER select - ESC back",
        )
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> _MechanicOutcome:
        nonlocal selected
        if _try_open_guide(event, ctx):
            return _MechanicOutcome.IGNORE
        if isinstance(event, tcod.event.Quit):
            return _MechanicOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _MechanicOutcome.IGNORE
        sym = event.sym
        sym_name: str = getattr(sym, 'name', '').lower()
        if sym in ui._UP_SYMS or sym_name == 'k':
            selected = (selected - 1) % len(_MECH_OPTIONS)
            return _MechanicOutcome.IGNORE
        if sym in ui._DOWN_SYMS or sym_name == 'j':
            selected = (selected + 1) % len(_MECH_OPTIONS)
            return _MechanicOutcome.IGNORE
        if sym in ui._ESCAPE_SYMS:
            return _MechanicOutcome.BACK
        if sym in ui._ENTER_SYMS:
            if selected == 0:
                return _MechanicOutcome.REFUEL
            elif selected == 1:
                return _MechanicOutcome.REPAIR
            else:
                return _MechanicOutcome.LOADOUT
        return _MechanicOutcome.IGNORE

    while True:
        action = ui.Modal(ctx.context, console).run(_render, _update)
        if action is _MechanicOutcome.REFUEL:
            buyable = ship_rec.max_fuel - owned.fuel
            if buyable <= 0:
                ctx.log.add("The fuel tank is already full.")
                continue
            affordable = ctx.stats.credits // ship_module.FUEL_COST_PER_UNIT
            if affordable <= 0:
                ctx.log.add("You don't have enough credits to buy fuel.")
                continue
            units = min(buyable, affordable)
            cost = units * ship_module.FUEL_COST_PER_UNIT
            ctx.stats.credits -= cost
            owned.fuel += units
            ctx.log.add(f"Refueled {units} units for {cost}$. Fuel: {owned.fuel} / {ship_rec.max_fuel}.")
            continue
        if action is _MechanicOutcome.REPAIR:
            dmg_pct = owned.hull_damage_pct
            if dmg_pct <= 0:
                ctx.log.add("No repairs needed -- hull integrity is 100%.")
                continue
            repair_cost = int(dmg_pct * ship_rec.price // 100)
            if ctx.stats.credits < repair_cost:
                ctx.log.add(f"Repair would cost {repair_cost}$, but you only have {ctx.stats.credits}$.")
                continue
            ctx.stats.credits -= repair_cost
            owned.hull_damage_pct = 0
            ctx.log.add(f"Repaired hull to 100% for {repair_cost}$.")
            continue
        if action is _MechanicOutcome.LOADOUT:
            from ._loadout import _run_loadout_menu
            _run_loadout_menu(ctx)
            continue
        return  # BACK or QUIT
