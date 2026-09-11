"""Ship-buy dialog — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

from .. import pygame_ui
from .. import world
from .. import ship as ship_module
from ..data.ships import list_ships

def _shield_stat(spec) -> str:
    """The shield line: max + regen per turn, or the empty marker."""
    if spec.base_shield_max == 0:
        return "-"
    return f"{spec.base_shield_max} + {spec.base_shield_recharge}/turn"


# The sheet: label, value renderer, and the number the bar/verdict read
# (shields compare by max). Numbers are BASE spec, never installed mods.
_SECTIONS = (
    ("PERFORMANCE", (
        ("Speed", lambda s: f"{s.speed} moves/day", lambda s: s.speed,
         lambda s: str(s.speed)),
        ("Fuel tank", lambda s: str(s.max_fuel), lambda s: s.max_fuel,
         lambda s: str(s.max_fuel)),
    )),
    ("COMBAT", (
        ("Hull", lambda s: str(s.base_hull), lambda s: s.base_hull,
         lambda s: str(s.base_hull)),
        ("Shields", _shield_stat, lambda s: s.base_shield_max, _shield_stat),
        ("Power/turn", lambda s: str(s.base_power_gen), lambda s: s.base_power_gen,
         lambda s: str(s.base_power_gen)),
        ("Weapon slots", lambda s: str(s.weapon_slots), lambda s: s.weapon_slots,
         lambda s: str(s.weapon_slots)),
        ("Module slots", lambda s: str(s.module_slots), lambda s: s.module_slots,
         lambda s: str(s.module_slots)),
    )),
    ("CAPACITY", (
        ("Cargo", lambda s: str(s.max_cargo), lambda s: s.max_cargo,
         lambda s: str(s.max_cargo)),
    )),
)

_BAR_WIDTH = 10
_BEST_BY_LABEL = {
    label: max(number_of(s) for s in list_ships())
    for _section, rows in _SECTIONS
    for label, _value_of, number_of, _yours_of in rows
}


def _stat_bar(offered: int, yours: int | None, catalog_best: int) -> str:
    """One CP437-safe gauge: offered fill, ``|`` at the player's ship."""
    best = max(1, catalog_best)
    fill = min(_BAR_WIDTH, round(offered / best * _BAR_WIDTH))
    cells = ["#"] * fill + ["-"] * (_BAR_WIDTH - fill)
    if yours is not None:
        cells[min(_BAR_WIDTH - 1, round(yours / best * _BAR_WIDTH))] = "|"
    return "".join(cells)


def _verdict_color(offered: int, yours: int):
    """The trade verdict on one stat: gain, regression, or no change."""
    if offered > yours:
        return pygame_ui.DEFAULT_PALETTE.positive
    if offered < yours:
        return pygame_ui.DEFAULT_PALETTE.negative
    return pygame_ui.DEFAULT_PALETTE.muted


def _stat_runs(label, value, bar, yours_value, yours_color):
    """One stat line's paint runs; concatenated text IS the body line."""
    palette = pygame_ui.DEFAULT_PALETTE
    runs = [
        (f"  {label:<13}{value:<15}", palette.description),
        (f"{bar}   ", palette.accent),
    ]
    if yours_value is not None:
        runs.append((f"yours: {yours_value}", yours_color))
    return tuple(runs)


def _stat_line(ship, yours, label, value_of, number_of, yours_of):
    """(plain line, runs) for one stat row of the sheet."""
    offered_number = number_of(ship)
    runs = _stat_runs(
        label,
        value_of(ship),
        _stat_bar(offered_number, None if yours is None else number_of(yours),
                  _BEST_BY_LABEL[label]),
        yours_of(yours) if yours is not None else None,
        (None if yours is None
         else _verdict_color(offered_number, number_of(yours))),
    )
    return "".join(text for text, _color in runs), runs


def _sheet_lines(ship, yours) -> tuple[tuple[str, tuple | None], ...]:
    """(plain line, colour runs) pairs for the sectioned ledger."""
    palette = pygame_ui.DEFAULT_PALETTE
    lines: list[tuple[str, tuple | None]] = []
    for section_index, (section, rows) in enumerate(_SECTIONS):
        if section_index:
            lines.append(("", None))
        lines.append((section, ((section, palette.muted),)))
        for label, value_of, number_of, yours_of in rows:
            lines.append(
                _stat_line(ship, yours, label, value_of, number_of, yours_of),
            )
    return tuple(lines)


def _owned_base_spec(ctx):
    """The owned ship's BASE catalog spec — installed mods never count."""
    owned = ctx.player_owned_ship
    if owned is None:
        return None
    return ship_module.find_ship(owned.ship_id)


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
    body, runs = _sheet_split(ship, _owned_base_spec(ctx))
    if effective_price is not None and effective_price < ship.price:
        _trade_in_save = ship.price - effective_price
        body += (
            f"Trade-in value: {pygame_ui.price_cell(_trade_in_save)}  -  "
            f"{pygame_ui.credits_label(ctx.stats.credits)}",
        )
        runs += (None,)
    if ctx.stats.credits < price:
        body += (
            f"You are {pygame_ui.shortfall_label(price - ctx.stats.credits)}"
            " of the asking price.",
        )
        runs += (None,)
    return body, runs


def _sheet_split(ship, yours):
    """The ledger as parallel ``(body lines, per-line runs)``."""
    pairs = _sheet_lines(ship, yours) + tuple(
        (line, ((line, pygame_ui.DEFAULT_PALETTE.instruction),))
        for line in _includes_lines(ship)
    )
    return (
        tuple(line for line, _runs in pairs),
        tuple(runs for _line, runs in pairs),
    )


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
    body, body_runs = _ship_buy_body(ctx, ship, effective_price, _price)
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
        body_runs=body_runs,
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
