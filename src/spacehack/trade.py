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
      - ``stats.credits``                   (decrement)

    Logs failure reasons when the transaction can't complete.
    """
    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship with cargo space to trade.")
        return False

    good = find_trade_good(good_id)
    volume = good.volume * quantity
    cost = _unit_price(ctx, planet_id, good_id) * quantity

    if ctx.stats.credits < cost:
        ctx.log.add(f"Not enough credits to buy {quantity}x {good.name} ({cost}$ needed).")
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
    ctx.stats.credits -= cost
    ctx.log.add(f"Bought {quantity}x {good.name} for {cost}$.")
    return True


def _can_sell_here(planet_id: str, good_id: str) -> bool:
    """True if ``good_id`` can be sold at ``planet_id``'s market.

    Contraband goods can only be sold at planets that list them in
    their ``produces`` or ``demands`` (e.g. Blockade Station sells
    black-market weapons openly).  All other goods are always
    accepted.
    """
    good = find_trade_good(good_id)
    if good.category != "contraband":
        return True
    spec = find_planet_spec(planet_id)
    for gid, _target in spec.produces:
        if gid == good_id:
            return True
    for gid, _target in spec.demands:
        if gid == good_id:
            return True
    return False


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
      - ``stats.credits``                   (increment)
    """
    owned = ctx.player_owned_ship
    if owned is None:
        return False

    good = find_trade_good(good_id)

    # Reject contraband at non-black-market planets.
    if not _can_sell_here(planet_id, good_id):
        ctx.log.add(f"No one here deals in {good.name} \u2014 contraband.")
        return False

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

    ctx.stats.credits += revenue
    ctx.log.add(f"Sold {quantity}x {good.name} for {revenue}$.")
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
# Quantity prompt (arrow-key adjustment)
# ---------------------------------------------------------------------------

class _QOut(Enum):
    IGNORE = auto()
    BACK = auto()
    CONFIRM = auto()


def _run_quantity_prompt(
    ctx: GameContext,
    label: str,
    max_qty: int,
    price_per: int,
) -> int | None:
    """Show a centred quantity-input modal.

    Arrow keys / +/- adjust the quantity, Enter confirms, ESC
    cancels.  Returns the chosen quantity (>=1) or ``None`` on
    cancel.
    """
    console = make_console()
    qty = 1

    def _render() -> None:
        console.clear()
        prompt = f"{label}  ({price_per}$ each)"
        qty_text = f"Quantity: [{qty}]"
        hint = "UP/+ increase  DOWN/- decrease  ENTER confirm  ESC cancel"

        def paint(row: int, text: str, *, fg) -> None:
            console.print(x=ui.centered_x(text, SCREEN_WIDTH), y=row, string=text, fg=fg)

        cy = (SCREEN_HEIGHT - MSG_LOG_HEIGHT) // 2
        paint(cy - 2, prompt, fg=ui.COLOR_TITLE)
        paint(cy + 1, qty_text, fg=ui.COLOR_VALUE_WHITE)
        paint(cy + 3, hint, fg=ui.COLOR_INSTRUCTION)

    def _update(event: tcod.event.Event) -> _QOut:
        nonlocal qty

        if isinstance(event, tcod.event.Quit):
            return _QOut.BACK
        if not isinstance(event, tcod.event.KeyDown):
            return _QOut.IGNORE

        sym = event.sym
        sym_name = getattr(sym, "name", "").lower()

        if sym in ui._ESCAPE_SYMS:
            return _QOut.BACK
        if sym in ui._ENTER_SYMS:
            return _QOut.CONFIRM

        # Increase (UP, +, =) or decrease (DOWN, -).
        is_up = sym in ui._UP_SYMS or sym_name in ("k", "plus", "equals")
        is_down = sym in ui._DOWN_SYMS or sym_name in ("j", "-", "minus")
        if is_up:
            qty = min(max_qty, qty + 1)
            return _QOut.IGNORE
        if is_down:
            qty = max(1, qty - 1)
            return _QOut.IGNORE

        return _QOut.IGNORE

    outcome = ui.Modal(ctx.context, console).run(_render, _update)
    return qty if outcome is _QOut.CONFIRM else None


# ---------------------------------------------------------------------------
# Trade modal
# ---------------------------------------------------------------------------


class _TradeOutcome(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


def open_loot_pickup(ctx: GameContext, loot_entity) -> None:
    """Open a simple modal to pick up loot from a destroyed ship.

    Shows what's available and lets the player take it (or leave it).
    If cargo space is insufficient, logs the shortfall and stays in
    space so the player can decide what to jettison.
    """
    good_id = loot_entity.loot_data.get("good_id", "")
    quantity = loot_entity.loot_data.get("quantity", 1)
    if not good_id:
        return
    try:
        good = find_trade_good(good_id)
    except KeyError:
        ctx.log.add("Unknown cargo debris.")
        return

    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship with cargo space to pick up cargo.")
        return

    volume = good.volume * quantity
    free_cargo = _free_cargo(owned)

    if free_cargo < volume:
        ctx.log.add(
            f"Not enough cargo space to take {good.name} x{quantity} "
            f"(need {volume}, have {free_cargo} free)."
        )
        return

    console = make_console()

    def _render() -> None:
        console.clear()
        title = "CARGO DEBRIS"
        line1 = f"You found {good.name} x{quantity}"
        line2 = f"Value: {good.base_price}$ each  |  Volume: {good.volume} crate(s)"
        hint = "ENTER to take  |  ESC to leave"

        cy = (SCREEN_HEIGHT - MSG_LOG_HEIGHT) // 2 - 2
        console.print(
            x=ui.centered_x(title, SCREEN_WIDTH), y=cy,
            string=title, fg=ui.COLOR_TITLE,
        )
        console.print(
            x=ui.centered_x(line1, SCREEN_WIDTH), y=cy + 2,
            string=line1, fg=ui.COLOR_VALUE_WHITE,
        )
        console.print(
            x=ui.centered_x(line2, SCREEN_WIDTH), y=cy + 3,
            string=line2, fg=ui.COLOR_VALUE_DIM,
        )
        console.print(
            x=ui.centered_x(hint, SCREEN_WIDTH), y=cy + 5,
            string=hint, fg=ui.COLOR_INSTRUCTION,
        )

    def _update(event) -> bool:
        """Return True to take loot, False to leave, None to keep polling."""
        if isinstance(event, tcod.event.Quit):
            return False
        if not isinstance(event, tcod.event.KeyDown):
            return None
        if event.sym in ui._ESCAPE_SYMS:
            return False
        if event.sym in ui._ENTER_SYMS:
            return True
        return None

    # Manual modal loop (simpler than ui.Modal for a one-shot decision).
    _taken = False
    while _taken is False:
        _render()
        ctx.context.present(console)
        for _event in tcod.event.wait():
            ctx.context.convert_event(_event)
            _result = _update(_event)
            if _result is True:
                # Take the loot.
                owned.inventory[good_id] = owned.inventory.get(good_id, 0) + quantity
                ctx.log.add(f"Picked up {good.name} x{quantity} from space debris.")
                # Remove the loot entity from the map.
                if loot_entity in ctx.game_map.entities:
                    try:
                        ctx.game_map.entities.remove(loot_entity)
                    except ValueError:
                        pass
                _taken = True
                break
            elif _result is False:
                ctx.log.add("Left the cargo debris in space.")
                _taken = True
                break


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

    if ctx.player_owned_ship is None:
        ctx.log.add("You need a ship with cargo space to use this terminal.")
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

        # Column headers — focused panel gets a bright cyan header
        # that's visually distinct from the "> " selection markers below.
        left_label = "\u2502 Station Inventory" if _focus == 0 else "  Station Inventory "
        right_label = "\u2502 Your Hold" if _focus == 1 else "  Your Hold "
        paint(2, cy, left_label, fg=ui.COLOR_TITLE if _focus == 0 else ui.COLOR_OPTION)
        paint(max_w // 2 + 2, cy, right_label, fg=ui.COLOR_TITLE if _focus == 1 else ui.COLOR_OPTION)
        # Separator between the two panels.
        sep_x = max_w // 2
        for sep_y in range(cy, SCREEN_HEIGHT - MSG_LOG_HEIGHT - 4):
            console.print(x=sep_x, y=sep_y, string="\u2502", fg=ui.COLOR_VALUE_DIM)
        cy += 1

        # Helper: build a line that fits within ``col_w`` chars (incl. marker).
        def _trade_line(name: str, price_label: str, suffix: str, selected: bool) -> str:
            """Format a trade row that fits exactly in ``col_w`` columns.

            ``name`` is truncated and padded to leave room for the
            ``price_label`` (e.g. " 14$") and ``suffix`` (e.g. "(30)").
            Marker ``"> "`` or ``"  "`` is included in the width calculation.
            """
            marker = "> " if selected else "  "
            fixed = len(marker) + 1 + len(price_label) + 1  # marker + spaces around price
            name_w = max(4, col_w - fixed - len(suffix))
            trimmed = name[:name_w].ljust(name_w)
            return f"{marker}{trimmed} {price_label} {suffix}"

        # Station goods (left panel).
        for i, gid in enumerate(_station_goods):
            if i >= SCREEN_HEIGHT - 12:
                break
            good = find_trade_good(gid)
            price = _unit_price(ctx, planet_id, gid)
            stock = _stocks.get(gid, 0)
            price_label = f"{price:>5}$"
            suffix = f"({stock:>3})"
            is_sel = _focus == 0 and i == _sel
            fg = ui.COLOR_OPTION_HIGHLIGHT if is_sel else ui.COLOR_OPTION
            paint(2, cy + i, _trade_line(good.name, price_label, suffix, is_sel), fg=fg)

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
            price_label = f"{sell_price:>5}$"
            _contra = good.category == "contraband" and not _can_sell_here(planet_id, gid)
            if _contra:
                price_label = f"  ---$"
            suffix = f"({qty:>3})"
            col_x = max_w // 2 + 2
            is_sel = _focus == 1 and i == _sel
            fg = ui.COLOR_OPTION_HIGHLIGHT if is_sel else ui.COLOR_OPTION
            if _contra:
                fg = ui.COLOR_VALUE_DIM
            paint(col_x, cy + i, _trade_line(good.name, price_label, suffix, is_sel), fg=fg)

        # Footer — cargo + credits bar.
        foot_y = SCREEN_HEIGHT - MSG_LOG_HEIGHT - 3
        if owned is not None:
            from . import ship as ship_module
            ship_spec = ship_module.find_ship(owned.ship_id)
            cargo_str = f"Cargo: {owned.cargo_used}/{ship_spec.max_cargo}"
            gold_str = f"Credits: {ctx.stats.credits}"
        else:
            cargo_str = "Cargo: N/A"
            gold_str = f"Credits: {ctx.stats.credits}"
        paint(2, foot_y, cargo_str, fg=ui.COLOR_VALUE_WHITE)
        paint(SCREEN_WIDTH - HUD_WIDTH - len(gold_str) - 2, foot_y, gold_str, fg=ui.COLOR_VALUE_WHITE)

        hint = "UP/DOWN navigate  ENTER buy/sell  TAB switch panel  ESC back"
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

        # Enter = buy on station panel, sell on hold panel.
        if sym in ui._ENTER_SYMS:
            if _focus == 0:
                # Buy from station.
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
                        can_afford = ctx.stats.credits // price if price > 0 else 999
                        max_qty = min(max_qty, can_afford)
                    if max_qty >= 1:
                        q = _run_quantity_prompt(ctx, f"Buy {good.name}", max_qty, price)
                        if q is not None:
                            _buy_good(ctx, planet_id, gid, q)
                    else:
                        ctx.log.add(f"Cannot afford or store {good.name}.")
            else:
                # Sell from hold.
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

    ui.Modal(ctx.context, console).run(_render, _update)
