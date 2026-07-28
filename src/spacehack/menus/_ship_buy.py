"""Ship-buy dialog — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import world
from .. import message_log
from .. import ship as ship_module
from .. import hud
from ..game_context import GameContext
from ..engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide


class ShipBuyOutcome(Enum):
    """What happened during a single ship-buy dialog iteration.

    Differentiates ESC (silent back) from Enter-while-unaffordable
    (caller should log "you cannot afford this"). The BUY outcome
    implies the player can afford the ship.
    """
    IGNORE = auto()
    BUY = auto()
    BACK = auto()
    TOO_EXPENSIVE = auto()
    QUIT = auto()


def render_ship_buy(console: tcod.console.Console, ctx: GameContext, ship: ship_module.Ship, *, screen_width: int, screen_height: int) -> None:
    """Paint the centered ship-buy dialog into ``console``.

    Clears first so the dialog fully replaces the city view; the
    caller re-paints city + HUD + msg log once the dialog exits.
    """
    console.clear()
    title = f'A {ship.name.upper()} sits on the showroom floor.'
    body = ship.description
    price_line = f'Cost: {ship.price}$    You have: {ctx.stats.credits}$'
    if ctx.stats.credits >= ship.price:
        afford = 'Press ENTER to buy it.'
    else:
        short = ship.price - ctx.stats.credits
        afford = f'You cannot afford it. ({short}$ short)'
    back = 'Press ESC to walk away.'
    max_w = screen_width - HUD_WIDTH - 2

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[:max_w - 1] + '…'

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=fg)
    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    paint(center_y - 4, fit(title), fg=ui.COLOR_TITLE)
    paint(center_y - 1, fit(body), fg=ui.COLOR_DESCRIPTION)
    paint(center_y + 3, fit(price_line), fg=ui.COLOR_VALUE_WHITE if ctx.stats.credits >= ship.price else ui.COLOR_VALUE_DIM)
    paint(center_y + 5, fit(afford), fg=ui.COLOR_OPTION_HIGHLIGHT if ctx.stats.credits >= ship.price else ui.COLOR_VALUE_DIM)
    paint(center_y + 7, fit(back), fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def update_ship_buy(event: tcod.event.Event, ship: ship_module.Ship, stats: hud.HudStats) -> ShipBuyOutcome:
    """Map a single event for the ship-buy dialog."""
    if isinstance(event, tcod.event.Quit):
        return ShipBuyOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return ShipBuyOutcome.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return ShipBuyOutcome.BACK
    if sym in ui._ENTER_SYMS:
        return ShipBuyOutcome.BUY if stats.credits >= ship.price else ShipBuyOutcome.TOO_EXPENSIVE
    return ShipBuyOutcome.IGNORE


def _run_ship_buy(ctx, blocker: world.Entity, ship: ship_module.Ship) -> ShipBuyOutcome:
    """Show the ship-buy modal for ``ship`` (the entity standing in
    the player's way is ``blocker``). Returns the dialog outcome;
    callers handle the actual purchase (mutating ``stats``, removing
    ``blocker`` from ``game_map.entities``, logging).
    """
    console = make_console()

    def _render() -> None:
        render_ship_buy(console, ctx, ship, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> ShipBuyOutcome:
        if _try_open_guide(event, ctx):
            return ShipBuyOutcome.IGNORE
        return update_ship_buy(event, ship, ctx.stats)
    return ui.Modal(ctx.context, console).run(_render, _update)
