"""Ship-buy dialog — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

from .. import pygame_ui
from .. import world
from .. import ship as ship_module

def _ship_buy_body(ctx, ship, effective_price, price):
    """Description plus trade-in and shortfall lines per the shared policy."""
    body = (ship.description,)
    if effective_price is not None and effective_price < ship.price:
        _trade_in_save = ship.price - effective_price
        body += (
            f"Trade-in value: {pygame_ui.price_cell(_trade_in_save)}  -  "
            f"{pygame_ui.credits_label(ctx.stats.credits)}",
        )
    if ctx.stats.credits < price:
        body += (
            f"You are {pygame_ui.shortfall_label(price - ctx.stats.credits)}"
            " of the asking price.",
        )
    return body


def _ship_buy_frame(ctx, ship: ship_module.Ship, effective_price: int | None, selected: int):
    """Build a modern framed snapshot of the ship-buy modal.

    Content policy is shared with the split terminals (title, price,
    credits, shortfall, hint formats all route through the helpers in
    ``pygame_ui`` — see 15_DESIGN_UNIFIED_TERMINAL_UX.md, Phase 4).
    """
    from .. import pygame_screen

    _price = effective_price if effective_price is not None else ship.price
    _afford = ctx.stats.credits >= _price
    _short = max(0, _price - ctx.stats.credits)
    body = _ship_buy_body(ctx, ship, effective_price, _price)
    detail = (
        f"Price {pygame_ui.price_cell(_price)}  "
        f"{pygame_ui.credits_label(ctx.stats.credits)}"
        + ("" if _afford else f"  ({pygame_ui.shortfall_label(_short)})")
    )
    rows = (
        pygame_screen.ScreenRow(
            f"Buy the {ship.name} - {pygame_ui.price_cell(_price)}",
            detail,
            "BUY",
        ),
    )
    footer = (
        pygame_ui.modal_hint(
            "ENTER buy", "ESC walk away", pygame_ui.GUIDE_HINT,
        ),
    )
    return pygame_screen.ScreenFrame(
        pygame_ui.terminal_title(ship.name, "for sale"),
        body,
        rows,
        footer,
        selected,
    )

def _run_pygame_ship_buy(ctx, ship: ship_module.Ship, effective_price: int | None) -> "ShipBuyOutcome | None":
    """Run Ship Buy in the shared Pygame screen."""
    from .. import pygame_screen

    selected = 0
    while True:
        outcome, action, selected = pygame_screen.run_for_context(
            ctx.context,
            _ship_buy_frame(ctx, ship, effective_price, selected),
            caption="spacehack - ship buy",
        )
        if outcome == "GUIDE":
            from ..help import _open_context_guide
            _open_context_guide(ctx, "Ships & Equipment")
            continue
        if outcome in {"TAB", "PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "SELECT" and action == "BUY":
            _price = effective_price if effective_price is not None else ship.price
            if ctx.stats.credits >= _price:
                return ShipBuyOutcome.BUY
            return ShipBuyOutcome.TOO_EXPENSIVE
        if outcome == "QUIT":
            return ShipBuyOutcome.QUIT
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

def _run_ship_buy(ctx, blocker: world.Entity, ship: ship_module.Ship, *, effective_price: int | None = None) -> ShipBuyOutcome:
    """Show the ship-buy modal for ``ship``.

    When ``effective_price`` is provided (trade-in), the dialog uses
    it for afford checks instead of ``ship.price``.
    """
    result = _run_pygame_ship_buy(ctx, ship, effective_price)
    if result is None:
        raise RuntimeError("Ship-buy menu returned no outcome")
    return result
