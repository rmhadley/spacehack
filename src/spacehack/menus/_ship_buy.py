"""Ship-buy dialog — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import pygame_ui
from .. import world
from .. import message_log
from .. import ship as ship_module
from .. import hud
from ..game_context import GameContext
from ..engine import HUD_WIDTH, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide


def _pygame_ship_buy_enabled() -> bool:
    """Return whether the Pygame Ship Buy modal can render in this runtime."""
    from .. import pygame_runtime

    return pygame_ui.migration_enabled("SPACEHACK_PYGAME_SHIP_BUY") or pygame_runtime.shared_enabled()


def _run_pygame_ship_buy(ctx, ship, effective_price: int | None) -> "ShipBuyOutcome | None":
    """Run Pygame Ship Buy, returning None for tcod fallback."""
    from ..pygame_ship_buy import PygameShipBuyUnavailable, run_for_context

    try:
        outcome = run_for_context(
            getattr(ctx, "context", ctx), ctx, ship, effective_price,
        )
    except PygameShipBuyUnavailable:
        return None
    if outcome == "BUY":
        return ShipBuyOutcome.BUY
    if outcome == "TOO_EXPENSIVE":
        return ShipBuyOutcome.TOO_EXPENSIVE
    if outcome == "QUIT":
        return ShipBuyOutcome.QUIT
    if outcome == "GUIDE":
        from ..help import _run_help_guide
        _run_help_guide(ctx)
    return ShipBuyOutcome.BACK


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

    content_y = ui.screen_header(console, screen_width, ui.fit_text(title, max_w), fg=ui.COLOR_TITLE)
    ui.paint_line(console, content_x, content_y, ui.fit_text(body, max_w), fg=ui.COLOR_DESCRIPTION)
    ui.paint_line(console, content_x, content_y + 3, ui.fit_text(price_line, max_w), fg=ui.COLOR_VALUE_WHITE if ctx.stats.credits >= _price else ui.COLOR_VALUE_DIM)
    ui.paint_line(console, content_x, content_y + 5, ui.fit_text(afford, max_w), fg=ui.COLOR_OPTION_HIGHLIGHT if ctx.stats.credits >= _price else ui.COLOR_VALUE_DIM)
    ui.paint_line(console, content_x, content_y + 7, ui.fit_text(back, max_w), fg=ui.COLOR_INSTRUCTION)
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
    if _pygame_ship_buy_enabled():
        pygame_result = _run_pygame_ship_buy(ctx, ship, effective_price)
        if pygame_result is not None:
            return pygame_result

    console = make_console()

    def _render() -> None:
        render_ship_buy(console, ctx, ship, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, effective_price=effective_price)

    def _update(event) -> ShipBuyOutcome:
        if _try_open_guide(event, ctx):
            return ShipBuyOutcome.IGNORE
        return update_ship_buy(event, ship, ctx.stats, effective_price=effective_price)
    return ui.Modal(ctx.context, console).run(_render, _update)
