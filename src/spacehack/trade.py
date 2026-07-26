"""Trade domain: buy/sell goods, economy seeding, trade modal.

Entry point: :func:`open_trade(ctx, planet_id)` — called from the
dispatcher when the player bumps a trade terminal or selects
"> Trade goods <" from an NPC talk dialog.

Owns:
  - :func:`_seed_economy` — populates ``ctx.economy_state[planet_id]``
    on first visit (produced goods start at target stock / surplus;
    demanded goods start at 0 / shortage).
  - :func:`_buy_good` / :func:`_sell_good` — mutate stock + inventory
    + gold.
  - :func:`render_trade_modal` — split-screen station / player hold
    layout + per-good pricing + cargo / gold footer.
  - :func:`open_trade` — modal loop that ties it all together.
"""
from __future__ import annotations

from enum import Enum, auto

import tcod.console
import tcod.event

from . import ui
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT, make_console
from .game_context import GameContext
from .data.planets import find_planet_spec, trade_price
from .data.trade_goods import find_trade_good


# ---------------------------------------------------------------------------
# Economy seeding
# ---------------------------------------------------------------------------


def _seed_economy(ctx: GameContext, planet_id: str) -> None:
    """Initialise ``ctx.economy_state[planet_id]`` on first visit.

    Produced goods start at their target stock (surplus → cheap to
    buy).  Demanded goods start at 0 (shortage → expensive to buy,
    good to sell).
    """
    if planet_id in ctx.economy_state:
        return
    spec = find_planet_spec(planet_id)
    stocks: dict[str, int] = {}
    for good_id, target in spec.produces:
        stocks[good_id] = target          # start at full stock (surplus)
    for good_id, target in spec.demands:
        # If a good is both produced AND demanded (rare), keep the
        # produce-side stock level — the demand tuple fills the gap.
        if good_id not in stocks:
            stocks[good_id] = 0            # start at 0 (shortage)
    ctx.economy_state[planet_id] = stocks


# ---------------------------------------------------------------------------
# Transaction helpers
# ---------------------------------------------------------------------------


def _buy_good(
    ctx: GameContext,
    planet_id: str,
    good_id: str,
    quantity: int = 1,
) -> bool:
    """Buy ``quantity`` units of ``good_id`` from the planet's market.

    Returns True iff the purchase succeeded (enough stock, enough
    gold, enough cargo space).

    Mutates:
      - ``economy_state[planet_id][good_id]`` (decrement)
      - ``owned_ship.inventory``           (increment)
      - ``stats.gold``                     (decrement)

    Logs failure reasons when the transaction can't complete.
    """
    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship with cargo space to trade.")
        return False

    good = find_trade_good(good_id)
    volume = good.volume * quantity
    cost = _unit_price(ctx, planet_id, good_id) * quantity

    if ctx.stats.gold < cost:
        ctx.log.add(f"Not enough gold to buy {quantity}x {good.name} ({cost}g needed).")
        return False

    free_cargo = _free_cargo(owned)
    if free_cargo < volume:
        ctx.log.add(f"Not enough cargo space ({free_cargo} free, need {volume}).")
        return False

    # Deduct stock (ensure it doesn't go below 0).
    stocks = ctx.economy_state.get(planet_id, {})
    current = stocks.get(good_id, 0)
    if current < quantity:
        ctx.log.add(f"The station only has {current} units of {good.name} available.")
        return False
    stocks[good_id] = max(0, current - quantity)

    # Complete the transaction.
    owned.inventory[good_id] = owned.inventory.get(good_id, 0) + quantity
    ctx.stats.gold -= cost
    ctx.log.add(f"Bought {quantity}x {good.name} for {cost}g.")
    return True


def _sell_good(
    ctx: GameContext,
    planet_id: str,
    good_id: str,
    quantity: int = 1,
) -> bool:
    """Sell ``quantity`` units of ``good_id`` back to the planet's market.

    Returns True iff the sale succeeded (player has enough crates).

    Mutates:
      - ``owned_ship.inventory``           (decrement, removing key at 0)
      - ``economy_state[planet_id][good_id]`` (increment)
      - ``stats.gold``                     (increment)
    """
    owned = ctx.player_owned_ship
    if owned is None:
        return False

    good = find_trade_good(good_id)
    held = owned.inventory.get(good_id, 0)
    if held < quantity:
        ctx.log.add(f"You only have {held} crates of {good.name}.")
        return False

    # Compute sell price (75% of buy price for the same stock level).
    buy_price = _unit_price(ctx, planet_id, good_id)
    sell_price = max(1, buy_price * 3 // 4)
    revenue = sell_price * quantity

    # Add to stock.
    stocks = ctx.economy_state.get(planet_id, {})
    stocks[good_id] = stocks.get(good_id, 0) + quantity

    # Remove from inventory.
    remaining = held - quantity
    if remaining <= 0:
        del owned.inventory[good_id]
    else:
        owned.inventory[good_id] = remaining

    ctx.stats.gold += revenue
    ctx.log.add(f"Sold {quantity}x {good.name} for {revenue}g.")
    return True


def _unit_price(ctx: GameContext, planet_id: str, good_id: str) -> int:
    """Current buy price for one unit of ``good_id`` on ``planet_id``.

    For goods the planet produces, the target stock comes from the
    ``produces`` tuple.  For goods the planet demands (or neutral
    goods), the target is from ``demands`` or a default of 10.
    """
    spec = find_planet_spec(planet_id)
    good = find_trade_good(good_id)
    stocks = ctx.economy_state.get(planet_id, {})
    current = stocks.get(good_id, 0)

    # Determine target from produces first, then demands, default 10.
    target = 10
    for gid, t in spec.produces:
        if gid == good_id:
            target = t
            break
    else:
        for gid, t in spec.demands:
            if gid == good_id:
                target = t
                break

    return trade_price(good.base_price, current, target)


def _free_cargo(owned) -> int:
    """Remaining cargo capacity on ``owned`` (Ship max - used)."""
    from . import ship as ship_module
    ship_spec = ship_module.find_ship(owned.ship_id)
    return ship_spec.max_cargo - owned.cargo_used


# ---------------------------------------------------------------------------
# Quantity prompt (simple number input)
# ---------------------------------------------------------------------------

_QTY_OUTCOME_IGNORE = object()
_QTY_OUTCOME_BACK = object()
_QTY_OUTCOME_CONFIRM = object()


def _run_quantity_prompt(
    ctx: GameContext,
    label: str,
    max_qty: int,
    price_per: int,
) -> int | None:
    """Show a centred quantity-input modal.

    The player types a number and presses Enter to confirm, or ESC
    to cancel.  Returns the chosen quantity (>=1) or ``None`` on
    cancel.
    """
    console = make_console()
    buf = ""

    def _render() -> None:
        console.clear()
        prompt = f"{label}  ({price_per}g each)"
        qty_text = f"Quantity: {buf or '_'}"
        hint = "ENTER confirm  ESC cancel"

        def paint(row: int, text: str, *, fg) -> None:
            console.print(x=ui.centered_x(text, SCREEN_WIDTH), y=row, string=text, fg=fg)

        cy = (SCREEN_HEIGHT - MSG_LOG_HEIGHT) // 2
        paint(cy - 2, prompt, fg=ui.COLOR_TITLE)
        paint(cy + 1, qty_text, fg=ui.COLOR_VALUE_WHITE)
        paint(cy + 3, hint, fg=ui.COLOR_INSTRUCTION)

    def _update(event: tcod.event.Event):
        nonlocal buf
        if isinstance(event, tcod.event.Quit):
            return _QTY_OUTCOME_BACK
        if not isinstance(event, tcod.event.KeyDown):
            return _QTY_OUTCOME_IGNORE
        sym = event.sym
        sym_name = getattr(sym, "name", "").lower()
        if sym in ui._ESCAPE_SYMS:
            return _QTY_OUTCOME_BACK
        if sym in ui._ENTER_SYMS:
            qty = 1
            if buf:
                try:
                    qty = max(1, min(max_qty, int(buf)))
                except ValueError:
                    qty = 1
            return _QTY_OUTCOME_CONFIRM
        # Numeric input.
        if sym_name in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
            if len(buf) < 4:
                buf += sym_name
            return _QTY_OUTCOME_IGNORE
        if sym_name == "backspace" and buf:
            buf = buf[:-1]
            return _QTY_OUTCOME_IGNORE
        return _QTY_OUTCOME_IGNORE

    # Since Modal.run relies on the enum-name convention, we need a
    # real Enum for the outcome.  Use a local one.
    from enum import Enum, auto

    class _QOut(Enum):
        IGNORE = auto()
        BACK = auto()
        CONFIRM = auto()

    def _wrapped_update(event):
        r = _update(event)
        if r is _QTY_OUTCOME_IGNORE:
            return _QOut.IGNORE
        if r is _QTY_OUTCOME_BACK:
            return _QOut.BACK
        return _QOut.CONFIRM

    outcome = ui.Modal(ctx.context, console).run(_render, _wrapped_update)
    if outcome is _QOut.BACK:
        return None
    qty = 1
    if buf:
        try:
            qty = max(1, min(max_qty, int(buf)))
        except ValueError:
            qty = 1
    return qty


# ---------------------------------------------------------------------------
# Trade modal
# ---------------------------------------------------------------------------


class _TradeOutcome(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


def open_trade(ctx: GameContext, planet_id: str) -> None:
    """Open the trade modal for ``planet_id``.

    Shows a split-screen view: station inventory on the left, player
    inventory on the right.  The player navigates with up/down on the
    focused panel, switches panels with Tab, buys with Enter, and
    sells with Shift+Enter.
    """
    _seed_economy(ctx, planet_id)
    spec = find_planet_spec(planet_id)
    _stocks = ctx.economy_state.get(planet_id, {})

    # Build the ordered list of tradable goods for this planet.
    _station_goods: list[str] = []
    seen: set[str] = set()
    for gid, _target in spec.produces:
        if gid not in seen:
            _station_goods.append(gid)
            seen.add(gid)
    for gid, _target in spec.demands:
        if gid not in seen:
            _station_goods.append(gid)
            seen.add(gid)

    if not _station_goods:
        ctx.log.add("This terminal has nothing to trade.")
        return

    _focus: int = 0        # 0 = station panel, 1 = player panel
    _sel: int = 0
    ctx.log.add(f"You approach the Trade Terminal at {spec.name}.")

    console = make_console()

    def _render() -> None:
        nonlocal _sel
        console.clear()

        owned = ctx.player_owned_ship
        max_w = SCREEN_WIDTH - HUD_WIDTH - 2
        col_w = max_w // 2 - 2

        def paint(x: int, y: int, text: str, *, fg) -> None:
            for i, ch in enumerate(text):
                if x + i < SCREEN_WIDTH - HUD_WIDTH:
                    console.print(x=x + i, y=y, string=ch, fg=fg)

        cy = 2
        # Title bar.
        title = f"TRADE — {spec.name.upper()}"
        paint(ui.centered_x(title, SCREEN_WIDTH), cy, title, fg=ui.COLOR_TITLE)
        cy += 2

        # Column headers.
        left_label = "> Station Inventory <" if _focus == 0 else "  Station Inventory  "
        right_label = "> Your Hold <" if _focus == 1 else "  Your Hold  "
        paint(2, cy, left_label, fg=ui.COLOR_OPTION_HIGHLIGHT if _focus == 0 else ui.COLOR_OPTION)
        paint(max_w // 2 + 2, cy, right_label, fg=ui.COLOR_OPTION_HIGHLIGHT if _focus == 1 else ui.COLOR_OPTION)
        cy += 1

        # Station goods (left panel).
        for i, gid in enumerate(_station_goods):
            if i >= SCREEN_HEIGHT - 12:
                break
            good = find_trade_good(gid)
            price = _unit_price(ctx, planet_id, gid)
            stock = _stocks.get(gid, 0)

            # Pad the name so prices align.
            name_str = good.name[:col_w - 8].ljust(col_w - 8)
            price_str = f"{price:>4}g"
            stock_str = f"({stock})"
            line = f"{name_str} {price_str} {stock_str}"

            is_sel = _focus == 0 and i == _sel
            marker = "> " if is_sel else "  "
            fg = ui.COLOR_OPTION_HIGHLIGHT if is_sel else ui.COLOR_OPTION
            paint(2, cy + i, f"{marker}{line}", fg=fg)

        # Player goods (right panel).
        if owned is not None:
            inv_items = list(owned.inventory.items())
        else:
            inv_items = []
        for i, (gid, qty) in enumerate(inv_items):
            if i >= SCREEN_HEIGHT - 12:
                break
            good = find_trade_good(gid)
            sell_price = max(1, _unit_price(ctx, planet_id, gid) * 3 // 4)
            name_str = good.name[:col_w - 8].ljust(col_w - 8)
            price_str = f"{sell_price:>4}g"
            qty_str = f"({qty})"
            line = f"{name_str} {price_str} {qty_str}"

            col_x = max_w // 2 + 2
            is_sel = _focus == 1 and i == _sel
            marker = "> " if is_sel else "  "
            fg = ui.COLOR_OPTION_HIGHLIGHT if is_sel else ui.COLOR_OPTION
            paint(col_x, cy + i, f"{marker}{line}", fg=fg)

        # Footer — cargo + gold bar.
        foot_y = SCREEN_HEIGHT - MSG_LOG_HEIGHT - 3
        if owned is not None:
            from . import ship as ship_module
            ship_spec = ship_module.find_ship(owned.ship_id)
            cargo_str = f"Cargo: {owned.cargo_used}/{ship_spec.max_cargo}"
            gold_str = f"Gold: {ctx.stats.gold}"
        else:
            cargo_str = "Cargo: N/A"
            gold_str = f"Gold: {ctx.stats.gold}"
        paint(2, foot_y, cargo_str, fg=ui.COLOR_VALUE_WHITE)
        paint(SCREEN_WIDTH - HUD_WIDTH - len(gold_str) - 2, foot_y, gold_str, fg=ui.COLOR_VALUE_WHITE)

        hint = "UP/DOWN navigate  ENTER buy  SHIFT+ENTER sell  TAB switch panel  ESC back"
        paint(2, foot_y + 2, hint, fg=ui.COLOR_INSTRUCTION)

    def _update(event: tcod.event.Event) -> _TradeOutcome:
        nonlocal _focus, _sel

        if isinstance(event, tcod.event.Quit):
            return _TradeOutcome.QUIT

        if not isinstance(event, tcod.event.KeyDown):
            return _TradeOutcome.IGNORE

        sym = event.sym
        sym_name = getattr(sym, "name", "").lower()

        # ESC = back.
        if sym in ui._ESCAPE_SYMS:
            return _TradeOutcome.BACK

        # Tab = switch focus panel.
        if sym_name == "tab":
            _focus = 1 - _focus
            _sel = 0
            return _TradeOutcome.IGNORE

        # Up/Down navigation.
        is_up = sym in ui._UP_SYMS or sym_name == "k"
        is_down = sym in ui._DOWN_SYMS or sym_name == "j"
        if is_up:
            if _focus == 0:
                _sel = (_sel - 1) % max(1, len(_station_goods))
            else:
                owned = ctx.player_owned_ship
                n = len(owned.inventory) if owned is not None else 0
                _sel = (_sel - 1) % max(1, n)
            return _TradeOutcome.IGNORE
        if is_down:
            if _focus == 0:
                _sel = (_sel + 1) % max(1, len(_station_goods))
            else:
                owned = ctx.player_owned_ship
                n = len(owned.inventory) if owned is not None else 0
                _sel = (_sel + 1) % max(1, n)
            return _TradeOutcome.IGNORE

        # Shift+Enter = sell (Shift modifier → sym.name has shift variant).
        is_shift_enter = (sym_name in ("return", "enter") and
                          (event.mod & (tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT)))
        if is_shift_enter and _focus == 1:
            owned = ctx.player_owned_ship
            if owned is not None:
                inv_items = list(owned.inventory.items())
                if 0 <= _sel < len(inv_items):
                    gid, qty = inv_items[_sel]
                    max_qty = min(qty, 9999)
                    price = _unit_price(ctx, planet_id, gid)
                    sell_p = max(1, price * 3 // 4)
                    q = _run_quantity_prompt(ctx, f"Sell {find_trade_good(gid).name}", max_qty, sell_p)
                    if q is not None:
                        _sell_good(ctx, planet_id, gid, q)
            return _TradeOutcome.IGNORE

        # Enter = buy (when focused on station panel).
        if sym in ui._ENTER_SYMS and _focus == 0:
            if 0 <= _sel < len(_station_goods):
                gid = _station_goods[_sel]
                good = find_trade_good(gid)
                price = _unit_price(ctx, planet_id, gid)
                owned = ctx.player_owned_ship
                max_qty = 1
                if owned is not None:
                    free = _free_cargo(owned)
                    stock = _stocks.get(gid, 0)
                    max_qty = min(
                        free // good.volume if good.volume > 0 else 999,
                        stock,
                        999,
                    )
                    can_afford = ctx.stats.gold // price if price > 0 else 999
                    max_qty = min(max_qty, can_afford)
                if max_qty >= 1:
                    q = _run_quantity_prompt(ctx, f"Buy {good.name}", max_qty, price)
                    if q is not None:
                        _buy_good(ctx, planet_id, gid, q)
                else:
                    ctx.log.add(f"Cannot afford or store {good.name}.")
            return _TradeOutcome.IGNORE

        return _TradeOutcome.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)
