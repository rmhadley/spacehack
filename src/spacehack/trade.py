"""Trade domain: buy/sell goods, economy seeding, trade modal.

Entry point: :func:`open_trade(ctx, planet_id)` — called from the
dispatcher when the player bumps a trade terminal or selects
"> Trade goods <" from an NPC talk dialog.

Owns:
  - :func:`_seed_economy` — populates ``ctx.economy_state[planet_id]``
    on first visit (produced goods start at target stock / surplus;
    demanded goods start at 0 / shortage).
  - :func:`_buy_good` / :func:`_sell_good` — mutate stock + inventory
    + credits.
  - :func:`open_trade` — split-screen modal with station / player hold
    layout + per-good pricing + cargo / credits footer.
"""
from __future__ import annotations

from enum import Enum, auto

from .game_context import GameContext
from .data.planets import find_planet_spec
from .data.trade_goods import find_trade_good, neutral_goods
from .loot import open_loot_pickup  # noqa: F401  (re-exported for callers)

NEUTRAL_TARGET: int = 8

# ---------------------------------------------------------------------------
# Pricing (pure function, shared by station + NPC trade)
# ---------------------------------------------------------------------------

def trade_price(base_price: int, current_stock: int, target_stock: int) -> int:
    """Calculate the buy/sell price given current vs target stock levels.

    Uses a linear curve:
      Stock ratio = 0%   (shortage)  \u2192 2.0\u00d7 base price
      Stock ratio = 50%  (equilibrium) \u2192 1.0\u00d7 base price
      Stock ratio = 100% (surplus)    \u2192 0.6\u00d7 base price

    This is the SINGLE pricing function for both the terminal and
    the NPC trader \u2014 no separate markup constants. The NPC trader
    simply offers access to a different stock pool (better prices
    because the stock levels are different).
    """
    target = max(1, target_stock)
    ratio = current_stock / target
    if ratio < 0.5:
        # Shortage zone: 2.0\u00d7 linearly down to 1.0\u00d7 at 50%.
        return max(1, int(base_price * (2.0 - ratio * 2.0)))
    else:
        # Surplus zone: 1.0\u00d7 linearly down to 0.6\u00d7 at 100%.
        return max(1, int(base_price * (1.0 - (ratio - 0.5) * 0.8)))

# ---------------------------------------------------------------------------
# Economy seeding
# ---------------------------------------------------------------------------

def _seed_economy(ctx: GameContext, planet_id: str) -> None:
    """Seed ``ctx.economy_state[planet_id]`` on first visit.
    Produced = full stock (surplus).  Demanded = 0 (shortage).
    Neutral = NEUTRAL_TARGET // 2 (equilibrium)."""
    if planet_id in ctx.economy_state:
        return
    spec = find_planet_spec(planet_id)
    stocks: dict[str, int] = {}
    for good_id, target in spec.produces:
        stocks[good_id] = target
    for good_id, target in spec.demands:
        if good_id not in stocks:
            stocks[good_id] = 0
    for gid in neutral_goods(spec):
        stocks[gid] = NEUTRAL_TARGET // 2
    ctx.economy_state[planet_id] = stocks

# ---------------------------------------------------------------------------
# Economy tick (passive stock regen)
# ---------------------------------------------------------------------------

def _target_stock_for(planet_id: str, good_id: str) -> int:
    """Equilibrium target for ``good_id`` on ``planet_id``.
    Checks produces, then demands, then NEUTRAL_TARGET."""
    spec = find_planet_spec(planet_id)
    for gid, t in spec.produces:
        if gid == good_id:
            return t
    for gid, t in spec.demands:
        if gid == good_id:
            return t
    return NEUTRAL_TARGET

def tick_economy(ctx: GameContext) -> None:
    """Drift all stocked economies toward target by 1/tick.
    Called on jump / launch.  Idempotent (skips non-seeded planets)."""
    for planet_id, stocks in ctx.economy_state.items():
        for good_id in list(stocks.keys()):
            target = _target_stock_for(planet_id, good_id)
            current = stocks[good_id]
            if current < target:
                stocks[good_id] = min(target, current + 1)
            elif current > target:
                stocks[good_id] = max(target, current - 1)

# ---------------------------------------------------------------------------
# Transaction helpers
# ---------------------------------------------------------------------------

def _buy_problem(ctx, owned, good, quantity, volume, cost, current_stock) -> str | None:
    """First reason the buy can't complete, or None when it can."""
    if ctx.stats.credits < cost:
        return f"Not enough credits to buy {quantity}x {good.name} ({cost}$ needed)."
    free_cargo = _free_cargo(owned)
    if free_cargo < volume:
        return f"Not enough cargo space ({free_cargo} free, need {volume})."
    if current_stock < quantity:
        return f"The station only has {current_stock} units of {good.name} available."
    return None


def _buy_good(
    ctx: GameContext,
    planet_id: str,
    good_id: str,
    quantity: int = 1,
) -> bool:
    """Buy ``quantity`` units of ``good_id`` from the planet's market.

    Returns True iff the purchase succeeded (enough stock, enough
    credits, enough cargo space).
    """
    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship with cargo space to trade.")
        return False
    good = find_trade_good(good_id)
    volume = good.volume * quantity
    cost = _unit_price(ctx, planet_id, good_id) * quantity
    stocks = ctx.economy_state.get(planet_id, {})
    problem = _buy_problem(
        ctx, owned, good, quantity, volume, cost, stocks.get(good_id, 0),
    )
    if problem:
        ctx.log.add(problem)
        return False
    stocks[good_id] = max(0, stocks.get(good_id, 0) - quantity)
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

def _sell_problem(owned, planet_id: str, good, quantity: int) -> str | None:
    """First reason the sale can't complete, or None when it can."""
    if not _can_sell_here(planet_id, good.id):
        return f"No one here deals in {good.name} \u2014 contraband."
    held = owned.inventory.get(good.id, 0)
    if held < quantity:
        return f"You only have {held} crates of {good.name}."
    return None


def _sell_good(
    ctx: GameContext,
    planet_id: str,
    good_id: str,
    quantity: int = 1,
) -> bool:
    """Sell ``quantity`` units of ``good_id`` back to the planet's market.

    Returns True iff the sale succeeded (player has enough crates).
    """
    owned = ctx.player_owned_ship
    if owned is None:
        return False
    good = find_trade_good(good_id)
    problem = _sell_problem(owned, planet_id, good, quantity)
    if problem:
        ctx.log.add(problem)
        return False
    revenue = _sell_price(ctx, planet_id, good_id) * quantity
    stocks = ctx.economy_state.get(planet_id, {})
    stocks[good_id] = stocks.get(good_id, 0) + quantity
    held = owned.inventory.get(good_id, 0)
    if held <= quantity:
        del owned.inventory[good_id]
    else:
        owned.inventory[good_id] = held - quantity
    ctx.stats.credits += revenue
    ctx.log.add(f"Sold {quantity}x {good.name} for {revenue}$.")
    return True

def _unit_price(ctx: GameContext, planet_id: str, good_id: str) -> int:
    """Current buy price for one unit of ``good_id`` on ``planet_id``.

    For goods the planet produces, the target stock comes from the
    ``produces`` tuple.  For goods the planet demands, the target
    is from ``demands``.  Neutral goods use :data:`NEUTRAL_TARGET`.

    Applies faction reputation buy discount (Liked=5%, Allied=10%)
    based on the player's merchant faction standing (trade terminals
    are merchant infrastructure).
    """
    good = find_trade_good(good_id)
    stocks = ctx.economy_state.get(planet_id, {})
    current = stocks.get(good_id, 0)
    target = _target_stock_for(planet_id, good_id)
    price = trade_price(good.base_price, current, target)
    # Apply the merchant faction reputation discount.
    from .faction import get_attitude, buy_price_modifier
    _merchant_rep = ctx.faction_reputation.get("merchant", 0)
    _attitude = get_attitude(_merchant_rep)
    _mod = buy_price_modifier(_attitude)
    return max(1, int(price * _mod))

def _sell_price(ctx: GameContext, planet_id: str, good_id: str) -> int:
    """Terminal sell price for one unit of ``good_id`` on ``planet_id``.

    75% of the buy price, adjusted by merchant faction reputation and
    the merchant faction's reputation bonus. Shared by the actual sale
    and the trade-modal display so the price shown always equals the
    credits received.
    """
    buy_price = _unit_price(ctx, planet_id, good_id)
    from .faction import get_attitude, sell_price_modifier
    _merchant_rep = ctx.faction_reputation.get("merchant", 0)
    _attitude = get_attitude(_merchant_rep)
    _sell_mod = sell_price_modifier(_attitude)
    return max(1, int(buy_price * 3 // 4 * _sell_mod))

def _free_cargo(owned) -> int:
    """Remaining cargo capacity on ``owned`` (effective max - used).

    Effective max includes module cargo bonuses.
    """
    from . import ship as ship_module
    ship_spec = ship_module.find_ship(owned.ship_id)
    return ship_module.effective_max_cargo(ship_spec, owned) - owned.cargo_used

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
    """Show the quantity selector in the shared Pygame window."""
    from . import pygame_quantity

    try:
        return pygame_quantity.run_for_context(
            getattr(ctx, "context", ctx), ctx, label, max_qty, price_per,
        )
    except pygame_quantity.PygameQuantityQuit:
        raise SystemExit

# ---------------------------------------------------------------------------
# NPC trade modal (Phase 4 — merchant ships from comms)
# ---------------------------------------------------------------------------

class _NpcTradeOutcome(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()

def _hold_cargo_label(owned) -> str:
    """Footer cargo label for a trade split screen (``Cargo: N/M``)."""
    from . import pygame_ui
    from . import ship as ship_module
    if owned is None:
        return pygame_ui.cargo_label(0, 0)
    ship_spec = ship_module.find_ship(owned.ship_id)
    return pygame_ui.cargo_label(
        owned.cargo_used,
        ship_module.effective_max_cargo(ship_spec, owned),
    )

def _pygame_npc_trade_frame(
    ctx: GameContext,
    npc_spec,
    npc_stock: dict[str, int],
    buy_mult: float,
    sell_mult: float,
    focus: int = 0,
    selected: int = 0,
):
    """Build a Pygame frame for an ephemeral NPC trade stock pool."""
    from . import pygame_split
    from . import pygame_ui
    owned = ctx.player_owned_ship
    npc_rows = []
    for gid, qty in npc_stock.items():
        good = find_trade_good(gid)
        npc_rows.append(pygame_split.SplitRow(
            good.name,
            pygame_ui.price_cell(int(good.base_price * buy_mult), qty),
            good.description,
            f"BUY_NPC:{gid}",
        ))
    hold_rows = []
    for gid, qty in (owned.inventory.items() if owned is not None else ()):
        good = find_trade_good(gid)
        hold_rows.append(pygame_split.SplitRow(
            good.name,
            pygame_ui.sell_cell(int(good.base_price * sell_mult), qty),
            good.description,
            f"SELL_NPC:{gid}",
        ))
    return pygame_split.SplitFrame(
        pygame_ui.terminal_title("TRADE", npc_spec.name), npc_spec.name, "Your Hold",
        tuple(npc_rows), tuple(hold_rows),
        pygame_ui.credits_label(ctx.stats.credits), _hold_cargo_label(owned),
        pygame_split.SPLIT_SHOP_HINT,
        focus, selected,
    )

def _npc_buy(ctx, npc_spec, npc_stock, good, good_id, buy_mult) -> None:
    """Apply one BUY_NPC transaction (prompt quantity, move stock + credits)."""
    owned = ctx.player_owned_ship
    stock = npc_stock.get(good_id, 0)
    price = int(good.base_price * buy_mult)
    maximum = min(
        stock,
        _free_cargo(owned) // max(1, good.volume),
        ctx.stats.credits // max(1, price),
    )
    quantity = _run_quantity_prompt(
        ctx, f"Buy {good.name} from {npc_spec.name}", maximum, price,
    ) if maximum else None
    if quantity:
        cost = price * quantity
        owned.inventory[good_id] = owned.inventory.get(good_id, 0) + quantity
        npc_stock[good_id] = stock - quantity
        ctx.stats.credits -= cost
        ctx.log.add(f"Bought {quantity}x {good.name} from {npc_spec.name} for {cost}$.")
    elif maximum == 0:
        ctx.log.add(
            f"{npc_spec.name} has insufficient stock or you cannot afford/store {good.name}."
        )


def _npc_sell(ctx, npc_spec, npc_stock, good, good_id, sell_mult) -> None:
    """Apply one SELL_NPC transaction (prompt quantity, move stock + credits)."""
    owned = ctx.player_owned_ship
    held = owned.inventory.get(good_id, 0)
    price = int(good.base_price * sell_mult)
    quantity = _run_quantity_prompt(
        ctx, f"Sell {good.name} to {npc_spec.name}", min(held, 999), price,
    ) if held else None
    if quantity:
        revenue = price * quantity
        remaining = held - quantity
        if remaining <= 0:
            del owned.inventory[good_id]
        else:
            owned.inventory[good_id] = remaining
        npc_stock[good_id] = npc_stock.get(good_id, 0) + quantity
        ctx.stats.credits += revenue
        ctx.log.add(f"Sold {quantity}x {good.name} to {npc_spec.name} for {revenue}$.")


def _npc_trade_transaction(
    ctx: GameContext,
    npc_spec,
    npc_stock: dict[str, int],
    buy_mult: float,
    sell_mult: float,
    kind: str,
    good_id: str,
) -> None:
    """Apply one NPC buy/sell transaction after quantity confirmation."""
    if ctx.player_owned_ship is None:
        return
    good = find_trade_good(good_id)
    if kind == "BUY_NPC":
        _npc_buy(ctx, npc_spec, npc_stock, good, good_id, buy_mult)
    elif kind == "SELL_NPC":
        _npc_sell(ctx, npc_spec, npc_stock, good, good_id, sell_mult)
    else:
        raise ValueError(f"Unknown NPC trade kind: {kind!r}")

def _apply_pygame_npc_trade_action(
    ctx: GameContext,
    npc_spec,
    npc_stock: dict[str, int],
    buy_mult: float,
    sell_mult: float,
    action: str,
) -> bool:
    """Apply one opaque NPC trade action in the parent process."""
    if not action:
        return True
    kind, separator, good_id = action.partition(":")
    if not separator or kind not in {"BUY_NPC", "SELL_NPC"}:
        raise ValueError(f"Unknown NPC trade action: {action!r}")
    _npc_trade_transaction(
        ctx, npc_spec, npc_stock, buy_mult, sell_mult, kind, good_id,
    )
    return True

def _run_pygame_npc_trade(
    ctx: GameContext,
    npc_spec,
    npc_stock: dict[str, int],
    buy_mult: float,
    sell_mult: float,
) -> bool | None:
    """Run NPC trade in the shared Pygame window."""
    from . import pygame_split
    result = pygame_split.run_interactive(
        ctx,
        lambda: _pygame_npc_trade_frame(
        ctx, npc_spec, npc_stock, buy_mult, sell_mult,
        ),
        lambda action, _focus, _selected: _apply_pygame_npc_trade_action(
        ctx, npc_spec, npc_stock, buy_mult, sell_mult, action,
        ),
        caption=f"spacehack - {npc_spec.name} trade",
    )
    return result is not None

def _npc_attitude(ctx: GameContext, npc_spec) -> str:
    """Faction attitude toward the player for this NPC ship."""
    from .faction import get_attitude
    _npc_faction = getattr(npc_spec, "faction", "civilian")
    return get_attitude(ctx.faction_reputation.get(_npc_faction, 0))


def _npc_trade_gate(ctx: GameContext, npc_spec) -> bool:
    """Return False (logging why) when this NPC can't open trade."""
    if _npc_attitude(ctx, npc_spec) in ("enemy", "disliked"):
        ctx.log.add(f"{npc_spec.name} refuses to trade with you.")
        return False
    if ctx.player_owned_ship is None:
        ctx.log.add("You need a ship with cargo space to trade.")
        return False
    return True


def _npc_stock_pool(npc_spec, count: int) -> dict[str, int]:
    """Build the ephemeral random stock pool for an NPC trader."""
    from .engine import RNG
    _cargo_list = list(npc_spec.cargo_goods)
    RNG.shuffle(_cargo_list)
    return {gid: RNG.randint(3, 8) for gid in _cargo_list[:count]}


def _npc_price_multipliers(ctx: GameContext, attitude: str) -> tuple[float, float]:
    """Buy/sell price multipliers for an NPC trade session (reputation)."""
    from .faction import buy_price_modifier, sell_price_modifier
    _buy = 1.2 * buy_price_modifier(attitude)
    _sell = 0.5 * sell_price_modifier(attitude)
    return _buy, _sell


def open_npc_trade(ctx: GameContext, npc_spec) -> None:
    """Open a trade modal with an NPC ship.

    Generated stock from ``npc_spec.cargo_goods`` using
    ``npc_spec.cargo_count`` (picked randomly). The NPC's
    stock is ephemeral — it is NOT stored in
    ``ctx.economy_state`` and does not persist across turns.

    Player buys from NPC at base_price plus 20% markup.
    Player sells to NPC at base_price minus 50% discount.
    """
    if not _npc_trade_gate(ctx, npc_spec):
        return
    _npc_stock = _npc_stock_pool(npc_spec, npc_spec.cargo_count)
    if not _npc_stock:
        ctx.log.add(f"{npc_spec.name} has nothing to trade.")
        return
    _buy_mult, _sell_mult = _npc_price_multipliers(
        ctx, _npc_attitude(ctx, npc_spec),
    )
    ctx.log.add(f"You open a trade channel with {npc_spec.name}.")
    result = _run_pygame_npc_trade(
        ctx, npc_spec, _npc_stock, _buy_mult, _sell_mult,
    )
    if result is None:
        raise RuntimeError("NPC trade returned no outcome")


def _station_goods_for(spec) -> list[str]:
    """Ordered tradable goods: produces, then demands, then neutral catalog."""
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
    # Neutral goods (non-contraband, not in produces/demands).
    for gid in neutral_goods(spec):
        if gid not in seen:
            _station_goods.append(gid)
            seen.add(gid)
    return _station_goods


def _terminal_trade_gate(ctx: GameContext) -> bool:
    """Return False (logging why) when the terminal can't open trade.

    Deliberately NOT faction-gated: merchant reputation only nudges
    prices via :func:`_unit_price` / :func:`_sell_price` (discounts
    for good standing), and can never lock the player out of the
    terminal. Bar / intercept work tanking merchant rep must not
    soft-lock trading.
    """
    if ctx.player_owned_ship is None:
        ctx.log.add("You need a ship with cargo space to use this terminal.")
        return False
    return True


def open_trade(ctx: GameContext, planet_id: str) -> None:
    """Open the trade modal for ``planet_id``.

    Shows a split-screen view: station inventory on the left, player
    inventory on the right.  The player navigates with up/down on the
    focused panel, switches panels with Tab, buys with Enter, and
    sells with Shift+Enter.
    """
    _seed_economy(ctx, planet_id)
    spec = find_planet_spec(planet_id)
    _station_goods = _station_goods_for(spec)
    if not _station_goods:
        ctx.log.add("This terminal has nothing to trade.")
        return
    if not _terminal_trade_gate(ctx):
        return
    result = _run_pygame_trade(ctx, planet_id, _station_goods)
    if result is None:
        raise RuntimeError("Trade terminal returned no outcome")

def _pygame_trade_frame(ctx: GameContext, planet_id: str, station_goods: list[str]):
    """Build a presentation-only station trade frame."""
    from . import pygame_split
    from . import pygame_ui
    spec = find_planet_spec(planet_id)
    owned = ctx.player_owned_ship
    _stocks = ctx.economy_state.get(planet_id, {})
    left = []
    for gid in station_goods:
        good = find_trade_good(gid)
        left.append(pygame_split.SplitRow(
            good.name,
            pygame_ui.price_cell(_unit_price(ctx, planet_id, gid), _stocks.get(gid, 0)),
            good.description,
            f"BUY:{gid}",
        ))
    right = []
    for gid, qty in (owned.inventory.items() if owned is not None else ()):
        good = find_trade_good(gid)
        right.append(pygame_split.SplitRow(
            good.name,
            pygame_ui.sell_cell(_sell_price(ctx, planet_id, gid), qty),
            good.description,
            f"SELL:{gid}",
        ))
    return pygame_split.SplitFrame(
        pygame_ui.terminal_title("TRADE", spec.name), "Station Inventory", "Your Hold",
        tuple(left), tuple(right),
        pygame_ui.credits_label(ctx.stats.credits), _hold_cargo_label(owned),
        pygame_split.SPLIT_SHOP_HINT,
    )

def _apply_pygame_trade_action(ctx: GameContext, planet_id: str, action: str) -> bool:
    """Apply one Pygame trade action through the existing transaction helpers."""
    if not action:
        return True
    if ":" not in action:
        raise ValueError(f"Malformed trade action: {action!r}")
    kind, good_id = action.split(":", 1)
    good = find_trade_good(good_id)
    if kind == "BUY":
        price = _unit_price(ctx, planet_id, good_id)
        owned = ctx.player_owned_ship
        stock = ctx.economy_state.get(planet_id, {}).get(good_id, 0)
        free = _free_cargo(owned) if owned is not None else 0
        max_qty = min(stock, free // max(1, good.volume), ctx.stats.credits // max(1, price))
        quantity = _run_quantity_prompt(ctx, f"Buy {good.name}", max_qty, price) if max_qty else None
        if quantity:
            _buy_good(ctx, planet_id, good_id, quantity)
        return True
    if kind == "SELL":
        owned = ctx.player_owned_ship
        held = owned.inventory.get(good_id, 0) if owned is not None else 0
        price = _sell_price(ctx, planet_id, good_id)
        quantity = _run_quantity_prompt(ctx, f"Sell {good.name}", held, price) if held else None
        if quantity:
            _sell_good(ctx, planet_id, good_id, quantity)
        return True
    raise ValueError(f"Unknown trade action: {action!r}")

def _run_pygame_trade(ctx: GameContext, planet_id: str, station_goods: list[str]) -> bool | None:
    """Run the station trade loop in the shared Pygame window."""
    from . import pygame_split
    result = pygame_split.run_interactive(
        ctx,
        lambda: _pygame_trade_frame(ctx, planet_id, station_goods),
        lambda action, _focus, _selected: _apply_pygame_trade_action(ctx, planet_id, action),
        caption="spacehack - trade terminal",
    )
    return result is not None if result is not None else None

class _COut(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()

def _cargo_rows(owned):
    """Build the cargo inventory rows (opaque ``JETTISON:<id>`` actions).

    Shared by the standalone cargo modal (:func:`_cargo_frame`) and the
    tabbed ship hangar's CARGO tab (``menus/_ship_menu.py``).
    """
    from . import pygame_screen

    items = []
    for good_id, qty in owned.inventory.items():
        try:
            good = find_trade_good(good_id)
        except KeyError:
            continue
        items.append(
            pygame_screen.ScreenRow(
                f"{good.name} x{qty} ({good.volume * qty} volume)",
                f"Value: {good.base_price}$ each",
                f"JETTISON:{good_id}",
            )
        )
    if not items:
        items = [pygame_screen.ScreenRow("No trade goods in hold", selectable=False)]
    return tuple(items)

def _cargo_body(owned, max_cargo: int) -> tuple[str, ...]:
    """Build the cargo summary body lines (shared by the cargo modal and
    the tabbed hangar's CARGO tab)."""
    return (
        f"Cargo: {owned.cargo_used} / {max_cargo}    Free: {max(0, max_cargo - owned.cargo_used)}",
        f"Mission cargo reserved: {owned.mission_reserved}    Ammo: {owned.cargo_ammo}",
    )

def _apply_jettison(ctx, owned, action: str) -> bool:
    """Apply one ``JETTISON:<good_id>`` action and return whether it was
    a recognized jettison request (False = malformed/unknown, the caller
    falls back).

    Prompts the player for the quantity in the shared Pygame window,
    removes that many units from the hold, and logs the jettison. The
    computation (quantity prompt + inventory mutation) is deterministic
    and tested in isolation.
    """
    if not action.startswith("JETTISON:") or ":" not in action:
        return False
    good_id = action.split(":", 1)[1]
    try:
        quantity = owned.inventory.get(good_id, 0)
        good = find_trade_good(good_id)
    except (KeyError, ValueError):
        return False
    if quantity > 0:
        quantity_prompt = _run_quantity_prompt(
            ctx, f"Jettison {good.name}", quantity, 0,
        )
        if quantity_prompt:
            remaining = quantity - quantity_prompt
            if remaining <= 0:
                del owned.inventory[good_id]
            else:
                owned.inventory[good_id] = remaining
            ctx.log.add(
                f"Jettisoned {quantity_prompt}x {good.name} into space."
            )
    return True

def _cargo_frame(ctx, owned, ship_name: str, max_cargo: int, selected: int):
    """Build a readable cargo snapshot with opaque jettison actions."""
    from . import pygame_screen, pygame_ui
    from . import ship as ship_module

    _hull_cur, _hull_max = ship_module.hull_cur_max(
        owned, ship_module.find_ship(owned.ship_id),
    )
    body = (*_cargo_body(owned, max_cargo), f"Hull: {_hull_cur}/{_hull_max}")
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "ENTER jettison selected", "ESC close",
        pygame_ui.GUIDE_HINT,
    ),)
    return pygame_screen.ScreenFrame(
        f"CARGO - {ship_name.upper()}", body, _cargo_rows(owned), footer, selected,
    )

def _run_pygame_cargo(ctx, owned, ship_name: str, max_cargo: int) -> bool | None:
    """Run cargo through Pygame, preserving jettison in the parent."""
    from . import pygame_screen

    selected = 0
    while True:
        outcome, action, selected = pygame_screen.run_for_context(
            getattr(ctx, "context", ctx),
            _cargo_frame(ctx, owned, ship_name, max_cargo, selected),
            caption="spacehack - cargo",
        )
        if outcome == "GUIDE":
            from .help import _run_help_guide
            _run_help_guide(ctx)
            continue
        if outcome in {"TAB", "PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "QUIT":
            raise SystemExit
        if outcome == "SELECT":
            if not _apply_jettison(ctx, owned, action):
                return None
            continue
        return True

def open_cargo(ctx: GameContext) -> None:
    """Open the cargo management modal.

    Full-screen breakdown of cargo: trade goods (itemized with
    quantity + volume), mission reserved space, ammo, and free
    capacity. The player can navigate trade goods with UP/DOWN
    and press J to jettison (destroy) selected goods — like the
    sell interface but without profit.

    Callable from both planet hangar (View option) and space mode
    (C key).
    """
    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You have no ship to inspect cargo on.")
        return

    from . import ship as ship_module
    ship_spec = ship_module.find_ship(owned.ship_id)

    # Cache static ship stats.
    from . import ship as _ship_mod
    ship_name = ship_module.ship_display_name(owned)
    max_cargo = _ship_mod.effective_max_cargo(ship_spec, owned)
    result = _run_pygame_cargo(ctx, owned, ship_name, max_cargo)
    if result is None:
        raise RuntimeError("Cargo screen returned no outcome")
    return
