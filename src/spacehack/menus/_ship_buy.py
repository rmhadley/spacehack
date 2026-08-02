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
from ..engine import HUD_WIDTH, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
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


def render_ship_buy(console: tcod.console.Console, ctx: GameContext, ship: ship_module.Ship, *, screen_width: int, screen_height: int, effective_price: int | None = None) -> None:
    """Paint the ship-buy dialog into ``console`` — terminal look:
    centered title at the top, detail lines flush-left at x=2,
    message log pinned at the bottom.

    When ``effective_price`` is provided (trade-in scenario) the
    dialog shows the discounted price and uses it for affordability
    checks instead of ``ship.price``.
    """
    _price = effective_price if effective_price is not None else ship.price
    console.clear()
    title = f'A {ship.name.upper()} sits on the showroom floor.'
    body = ship.description
    if effective_price is not None and effective_price < ship.price:
        _trade_in_save = ship.price - effective_price
        price_line = f'Cost: {ship.price}$  (trade-in {_trade_in_save}$)  You have: {ctx.stats.credits}$'
    else:
        price_line = f'Cost: {ship.price}$    You have: {ctx.stats.credits}$'
    if ctx.stats.credits >= _price:
        afford = 'Press ENTER to buy it.'
    else:
        short = _price - ctx.stats.credits
        afford = f'You cannot afford it. ({short}$ short)'
    back = 'Press ESC to walk away.'
    content_x, max_w = ui.content_metrics(screen_width, HUD_WIDTH, col_x=2)

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[:max_w - 1] + '…'

    def paint_title(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=fg)

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=content_x, y=row, string=text, fg=fg)
    paint_title(2, fit(title), fg=ui.COLOR_TITLE)
    paint(4, fit(body), fg=ui.COLOR_DESCRIPTION)
    paint(7, fit(price_line), fg=ui.COLOR_VALUE_WHITE if ctx.stats.credits >= _price else ui.COLOR_VALUE_DIM)
    paint(9, fit(afford), fg=ui.COLOR_OPTION_HIGHLIGHT if ctx.stats.credits >= _price else ui.COLOR_VALUE_DIM)
    paint(11, fit(back), fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def update_ship_buy(event: tcod.event.Event, ship: ship_module.Ship, stats: hud.HudStats, *, effective_price: int | None = None) -> ShipBuyOutcome:
    """Map a single event for the ship-buy dialog.

    Uses ``effective_price`` (when provided) to decide affordability
    instead of ``ship.price``.
    """
    _price = effective_price if effective_price is not None else ship.price
    if isinstance(event, tcod.event.Quit):
        return ShipBuyOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return ShipBuyOutcome.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return ShipBuyOutcome.BACK
    if sym in ui._ENTER_SYMS:
        return ShipBuyOutcome.BUY if stats.credits >= _price else ShipBuyOutcome.TOO_EXPENSIVE
    return ShipBuyOutcome.IGNORE


def _run_ship_buy(ctx, blocker: world.Entity, ship: ship_module.Ship, *, effective_price: int | None = None) -> ShipBuyOutcome:
    """Show the ship-buy modal for ``ship``.

    When ``effective_price`` is provided (trade-in), the dialog uses
    it for afford checks instead of ``ship.price``.
    """
    console = make_console()

    def _render() -> None:
        render_ship_buy(console, ctx, ship, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, effective_price=effective_price)

    def _update(event) -> ShipBuyOutcome:
        if _try_open_guide(event, ctx):
            return ShipBuyOutcome.IGNORE
        return update_ship_buy(event, ship, ctx.stats, effective_price=effective_price)
    return ui.Modal(ctx.context, console).run(_render, _update)
