"""Ship-buy dialog — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

from .. import pygame_ui
from .. import world
from .. import ship as ship_module

def _shield_stat(spec) -> str:
    """The shield line: max + regen per turn, or the empty marker."""
    if spec.base_shield_max == 0:
        return "-"
    return f"{spec.base_shield_max} + {spec.base_shield_recharge}/turn"


_STAT_ROWS = (
    ("Speed", lambda spec: f"{spec.speed} moves/day"),
    ("Hull", lambda spec: str(spec.base_hull)),
    ("Shields", _shield_stat),
    ("Power/turn", lambda spec: str(spec.base_power_gen)),
    ("Weapon slots", lambda spec: str(spec.weapon_slots)),
    ("Module slots", lambda spec: str(spec.module_slots)),
    ("Cargo", lambda spec: str(spec.max_cargo)),
    ("Fuel tank", lambda spec: str(spec.max_fuel)),
)


def _owned_base_spec(ctx):
    """The owned ship's BASE catalog spec — installed mods never count."""
    owned = ctx.player_owned_ship
    if owned is None:
        return None
    return ship_module.find_ship(owned.ship_id)


def _spec_ledger(ship, yours) -> tuple[str, ...]:
    """One aligned line per Ship spec stat, with the base-vs-base
    ``yours:`` comparison when the player owns a ship."""
    lines = []
    for label, stat_of in _STAT_ROWS:
        line = f"{label:<13}{stat_of(ship):<18}"
        if yours is not None:
            line += f"yours: {stat_of(yours)}"
        lines.append(line)
    return tuple(lines)


def _catalog_name(resolver, item_id):
    """Resolved catalog name for one loadout item, id on a miss."""
    try:
        return resolver(item_id).name
    except KeyError:
        return item_id


def _includes_lines(ship) -> tuple[str, ...]:
    """The starting-loadout lines: catalog names, id fallback."""
    from ..data.modules import find_module
    from ..data.weapons import find_weapon

    lines = []
    if ship.start_weapons:
        lines.append("Includes: " + ", ".join(
            _catalog_name(find_weapon, item_id) for item_id in ship.start_weapons
        ))
    if ship.start_modules:
        lines.append("Includes: " + ", ".join(
            _catalog_name(find_module, item_id) for item_id in ship.start_modules
        ))
    return tuple(lines)


def _ship_buy_body(ctx, ship, effective_price, price):
    """Spec-sheet ledger plus trade-in and shortfall lines."""
    body = _spec_ledger(ship, _owned_base_spec(ctx)) + _includes_lines(ship)
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
