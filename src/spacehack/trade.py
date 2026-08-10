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

import tcod.console
import tcod.event

from . import ui
from . import message_log
from .engine import MSG_LOG_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT, make_console
from .game_context import GameContext
from .data.planets import find_planet_spec
from .data.trade_goods import find_trade_good, neutral_goods
from .input_helpers import _try_open_guide
from .ui import paint_text, paint_centered, render_split_frame


def _pygame_split_enabled() -> bool:
    """Return whether the shared split-screen Pygame batch is enabled."""
    from . import pygame_split

    return pygame_split.enabled()


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


def _trait_buy_mult(ctx: GameContext) -> float:
    """Trade Route trait: -5% buy prices."""
    from .xp import has_trait
    return 0.95 if has_trait(ctx, "trade_route") else 1.0


def _trait_sell_mult(ctx: GameContext) -> float:
    """Trade Route trait: +5% sell prices."""
    from .xp import has_trait
    return 1.05 if has_trait(ctx, "trade_route") else 1.0


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


def _buy_good(
    ctx: GameContext,
    planet_id: str,
    good_id: str,
    quantity: int = 1,
) -> bool:
    """Buy ``quantity`` units of ``good_id`` from the planet's market.

    Returns True iff the purchase succeeded (enough stock, enough
    credits, enough cargo space).

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

    # Compute sell price (75% of buy price, rep + trait adjusted).
    sell_price = _sell_price(ctx, planet_id, good_id)
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
    # Apply faction rep discount + Trade Route trait discount.
    from .faction import get_attitude, buy_price_modifier
    _merchant_rep = ctx.faction_reputation.get("merchant", 0)
    _attitude = get_attitude(_merchant_rep)
    _mod = buy_price_modifier(_attitude) * _trait_buy_mult(ctx)
    return max(1, int(price * _mod))


def _sell_price(ctx: GameContext, planet_id: str, good_id: str) -> int:
    """Terminal sell price for one unit of ``good_id`` on ``planet_id``.

    75% of the buy price, adjusted by merchant faction reputation and
    the Trade Route trait's +5% sell bonus. Shared by the actual sale
    and the trade-modal display so the price shown always equals the
    credits received.
    """
    buy_price = _unit_price(ctx, planet_id, good_id)
    from .faction import get_attitude, sell_price_modifier
    _merchant_rep = ctx.faction_reputation.get("merchant", 0)
    _attitude = get_attitude(_merchant_rep)
    _sell_mod = sell_price_modifier(_attitude)
    return max(1, int(buy_price * 3 // 4 * _sell_mod * _trait_sell_mult(ctx)))


def _free_cargo(owned) -> int:
    """Remaining cargo capacity on ``owned`` (effective max - used).

    Effective max includes module cargo bonuses.
    """
    from . import ship as ship_module
    ship_spec = ship_module.find_ship(owned.ship_id)
    return ship_module.effective_max_cargo(ship_spec, owned) - owned.cargo_used


# (Shared render helpers _paint_text, _paint_centered, _format_trade_line,
# and _render_trade_frame were extracted to ui.py as paint_text,
# paint_centered, format_split_row, render_split_frame.)
# This module imports them from ui.py at the top of the file.


# ---------------------------------------------------------------------------
# Quantity prompt (arrow-key adjustment)
# ---------------------------------------------------------------------------

class _QOut(Enum):
    IGNORE = auto()
    BACK = auto()
    CONFIRM = auto()


def _pygame_quantity_enabled() -> bool:
    """Return whether the Pygame quantity selector can render in this runtime."""
    from . import pygame_ui

    return pygame_ui.presentation_enabled()


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
# Trade modal
# ---------------------------------------------------------------------------


class _TradeOutcome(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


class _LootOutcome(Enum):
    IGNORE = auto()
    TAKE = auto()
    LEAVE = auto()
    QUIT = auto()


def _run_pygame_loot(ctx: GameContext, title: str, body: str, take_label: str) -> str | None:
    """Run the loot choice through the generic Pygame menu worker."""
    from . import pygame_menu

    item = pygame_menu.MenuItem(take_label, "", "TAKE")
    frame = pygame_menu.MenuFrame(
        title=title,
        body=body,
        items=(item,),
        hints=("ENTER secure/take   ESC leave",),
        selected=0,
    )
    outcome, action, _selected = pygame_menu.run_for_context(
        getattr(ctx, "context", ctx),
        (frame,),
        caption=f"spacehack - {title.lower()}",
    )
    if outcome == "GUIDE":
        from .help import _open_context_guide
        _open_context_guide(ctx, "Trading & Economy")
        return _run_pygame_loot(ctx, title, body, take_label)
    if outcome == "SELECT" and action == "TAKE":
        return "TAKE"
    if outcome == "QUIT":
        return "QUIT"
    return "LEAVE"


def _apply_loot_pickup(
    ctx: GameContext,
    loot_entity,
    owned,
    is_quest: bool,
    goods: list[tuple[str, int]],
    good_id: str,
    quantity: int,
    good,
) -> None:
    """Apply a confirmed loot pickup in the parent process."""
    if is_quest:
        from . import main_quest as _mq
        secured = _mq.secure_quest_loot(ctx, loot_entity, goods)
        if not secured:
            for gid, qty in goods:
                owned.inventory[gid] = owned.inventory.get(gid, 0) + qty
            ctx.log.add("Picked up leftover quest cache goods.")
    else:
        secured = False
        if getattr(loot_entity, "heist_mission", False):
            secured = _secure_heist_cargo(ctx, loot_entity, good_id, quantity)
        if secured:
            ctx.log.add(
                f"Secured mission cargo: {good.name} x{quantity} "
                "(reserved in hold). Do not sell!"
            )
        else:
            owned.inventory[good_id] = owned.inventory.get(good_id, 0) + quantity
            ctx.log.add(f"Picked up {good.name} x{quantity} from space debris.")
    if loot_entity in ctx.game_map.entities:
        ctx.game_map.entities.remove(loot_entity)


def _secure_heist_cargo(ctx: GameContext, loot_entity, good_id: str, quantity: int) -> bool:
    """Mark the intercept mission's loot as secured and reserve hold space.

    Returns True if the loot belonged to an active (not-yet-secured)
    intercept mission, in which case the mission's ``heist_good_secured``
    flag is set and the cargo volume is reserved in
    ``owned.mission_reserved`` (the MISSION CARGO hold concept).
    The good does NOT enter the trade inventory — it cannot be sold
    and buying the same good at a terminal does not count.

    Returns False if no matching active mission exists (e.g. the
    mission was abandoned) — the caller falls back to normal debris
    pickup into the trade inventory.
    """
    _good_id = good_id
    _qty = quantity
    for _am in ctx.player_active_missions:
        if getattr(_am, 'heist_target_good_id', None) != _good_id:
            continue
        # Prefer an exact mission link when the loot entity carries one.
        _mid = getattr(loot_entity, 'heist_mission_id', None)
        if _mid and _am.mission_id != _mid:
            continue
        if getattr(_am, 'heist_good_secured', False):
            continue
        # Reserve the same volume that mission._reserved_heist_volume
        # releases on complete/abort (which assumes quantity 1). The
        # flag is set AFTER this lookup so the two stay in sync.
        try:
            _vol = find_trade_good(_good_id).volume * _qty
        except KeyError:
            _vol = 0
        _am.heist_good_secured = True
        _owned = ctx.player_owned_ship
        if _owned is not None:
            _owned.mission_reserved += _vol
        return True
    return False


def open_loot_pickup(ctx: GameContext, loot_entity) -> None:
    """Open a simple modal to pick up loot from a destroyed ship.

    Shows what's available and lets the player take it (or leave it).
    If cargo space is insufficient, logs the shortfall and stays in
    space so the player can decide what to jettison.

    Intercept-mission loot (``heist_mission`` set) is secured as
    MISSION CARGO — reserved in the hold, kept out of the trade
    inventory, and never sellable. The mission only completes when
    that specific cargo is secured; buying the same good at a
    terminal does not count.

    Quest cache / salvage loot (``main_quest_step_id`` set) is
    handled by :func:`spacehack.main_quest.secure_quest_loot`: the
    goods authored in ``loot_data["goods"]`` are granted to the hold
    and the main-quest step completes in the same action.
    """
    _quest_step_id = getattr(loot_entity, 'main_quest_step_id', '')
    _is_quest = bool(_quest_step_id)
    if _is_quest:
        # Quest cache / salvage loot: goods are a [(good_id, qty)] list.
        # Validate EVERY id up front so a typo'd secondary good can't
        # silently land in the hold via secure_quest_loot's grant loop.
        _goods: list[tuple[str, int]] = []
        for _g in (loot_entity.loot_data.get("goods") or []):
            try:
                find_trade_good(str(_g[0]))
            except KeyError:
                ctx.log.add("The quest cache contains unknown goods - ignored.")
                continue
            _goods.append((str(_g[0]), int(_g[1])))
        if not _goods:
            ctx.log.add("An empty quest cache.")
            return
        good_id, quantity = _goods[0]
    else:
        _goods = []
        good_id = loot_entity.loot_data.get("good_id", "")
        quantity = loot_entity.loot_data.get("quantity", 1)
        if not good_id:
            return
    try:
        good = find_trade_good(good_id)
    except KeyError:
        ctx.log.add("Unknown cargo debris.")
        # Remove the unresolvable loot entity so it doesn't block movement.
        try:
            ctx.game_map.entities.remove(loot_entity)
        except ValueError:
            pass
        return

    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship with cargo space to pick up cargo.")
        return

    if _is_quest:
        # Total volume across all quest goods.
        volume = 0
        for _gid, _qty in _goods:
            try:
                volume += find_trade_good(_gid).volume * _qty
            except KeyError:
                continue
    else:
        volume = good.volume * quantity
    free_cargo = _free_cargo(owned)

    if free_cargo < volume:
        ctx.log.add(
            f"Not enough cargo space to take {good.name} x{quantity} "
            f"(need {volume}, have {free_cargo} free)."
        )
        return

    _is_heist = getattr(loot_entity, 'heist_mission', False)
    if _is_quest:
        title = "QUEST CACHE"
        parts = [
            f"{find_trade_good(gid).name} x{qty}"
            for gid, qty in _goods
        ]
        body = "Secured quest contents: " + ", ".join(parts)
        take_label = "Secure"
    elif _is_heist:
        title = "MISSION CARGO"
        body = f"Secured mission cargo: {good.name} x{quantity}"
        take_label = "Secure"
    else:
        title = "CARGO DEBRIS"
        body = (
            f"You found {good.name} x{quantity}. "
            f"Value: {good.base_price}$ each | Volume: {good.volume} crate(s)"
        )
        take_label = "Take"
    pygame_outcome = _run_pygame_loot(ctx, title, body, take_label)
    if pygame_outcome == "TAKE":
        _apply_loot_pickup(
            ctx, loot_entity, owned, _is_quest, _goods,
            good_id, quantity, good,
        )
    elif pygame_outcome == "QUIT":
        raise SystemExit
    else:
        ctx.log.add("Left the cargo debris in space.")


# ---------------------------------------------------------------------------
# NPC trade modal (Phase 4 — merchant ships from comms)
# ---------------------------------------------------------------------------


class _NpcTradeOutcome(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


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
    owned = ctx.player_owned_ship
    npc_rows = tuple(
        pygame_split.SplitRow(
        find_trade_good(gid).name,
        f"{int(find_trade_good(gid).base_price * buy_mult)}$ ({qty})",
        find_trade_good(gid).description,
        f"BUY_NPC:{gid}",
        )
        for gid, qty in npc_stock.items()
    )
    hold_rows = tuple(
        pygame_split.SplitRow(
        find_trade_good(gid).name,
        f"{int(find_trade_good(gid).base_price * sell_mult)}$ ({qty})",
        find_trade_good(gid).description,
        f"SELL_NPC:{gid}",
        )
        for gid, qty in (owned.inventory.items() if owned is not None else ())
    )
    from . import ship as ship_module
    if owned is not None:
        ship_spec = ship_module.find_ship(owned.ship_id)
        cargo = f"Cargo: {owned.cargo_used}/{ship_module.effective_max_cargo(ship_spec, owned)}"
    else:
        cargo = "Cargo: N/A"
    return pygame_split.SplitFrame(
        f"TRADE - {npc_spec.name.upper()}", npc_spec.name, "Your Hold",
        npc_rows, hold_rows, cargo, f"Credits: {ctx.stats.credits}",
        "UP/DOWN navigate  TAB switch panel  ENTER buy/sell  ESC back",
        focus, selected,
    )


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
    good = find_trade_good(good_id)
    owned = ctx.player_owned_ship
    if owned is None:
        return
    if kind == "BUY_NPC":
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
        return
    if kind != "SELL_NPC":
        raise ValueError(f"Unknown NPC trade kind: {kind!r}")
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


def open_npc_trade(ctx: GameContext, npc_spec) -> None:
    """Open a trade modal with an NPC ship.

    Generated stock from ``npc_spec.cargo_goods`` using
    ``npc_spec.cargo_count`` (picked randomly). The NPC's
    stock is ephemeral — it is NOT stored in
    ``ctx.economy_state`` and does not persist across turns.

    Player buys from NPC at base_price plus 20% markup.
    Player sells to NPC at base_price minus 50% discount.
    """
    # Faction rep gating: enemy/disliked can't trade.
    _npc_faction = getattr(npc_spec, 'faction', 'civilian')
    from .faction import get_attitude, buy_price_modifier, sell_price_modifier
    _npc_rep = ctx.faction_reputation.get(_npc_faction, 0)
    _npc_attitude = get_attitude(_npc_rep)
    if _npc_attitude in ("enemy", "disliked"):
        ctx.log.add(f"{npc_spec.name} refuses to trade with you.")
        return

    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship with cargo space to trade.")
        return

    from .engine import RNG
    _cargo_list = list(npc_spec.cargo_goods)
    if not _cargo_list:
        ctx.log.add(f"{npc_spec.name} has nothing to trade.")
        return

    RNG.shuffle(_cargo_list)
    _selected = _cargo_list[:npc_spec.cargo_count]
    _npc_stock: dict[str, int] = {
        gid: RNG.randint(3, 8) for gid in _selected
    }

    # Price multipliers.
    _BUY_MULT = 1.2   # player buys from NPC at markup
    _SELL_MULT = 0.5  # player sells to NPC at discount

    # Apply faction rep + Trade Route trait modifier on top of NPC trade base rates.
    _BUY_MULT *= buy_price_modifier(_npc_attitude) * _trait_buy_mult(ctx)
    _SELL_MULT *= sell_price_modifier(_npc_attitude) * _trait_sell_mult(ctx)

    _npc_goods: list[str] = list(_npc_stock.keys())
    _focus: int = 0        # 0 = NPC panel, 1 = player panel
    _sel: int = 0

    ctx.log.add(f"You open a trade channel with {npc_spec.name}.")

    result = _run_pygame_npc_trade(
        ctx, npc_spec, _npc_stock, _BUY_MULT, _SELL_MULT,
    )
    if result is None:
        raise RuntimeError("NPC trade returned no outcome")
    return
def _pygame_trade_frame(ctx: GameContext, planet_id: str, station_goods: list[str]):
    """Build a presentation-only station trade frame."""
    from . import pygame_split
    spec = find_planet_spec(planet_id)
    owned = ctx.player_owned_ship
    _stocks = ctx.economy_state.get(planet_id, {})
    left = tuple(
        pygame_split.SplitRow(
        find_trade_good(gid).name,
        f"{_unit_price(ctx, planet_id, gid)}$ ({_stocks.get(gid, 0)})",
        f"{find_trade_good(gid).description}",
        f"BUY:{gid}",
        )
        for gid in station_goods
    )
    right = tuple(
        pygame_split.SplitRow(
        find_trade_good(gid).name,
        f"{_sell_price(ctx, planet_id, gid)}$ ({qty})",
        find_trade_good(gid).description,
        f"SELL:{gid}",
        )
        for gid, qty in (owned.inventory.items() if owned is not None else ())
    )
    return pygame_split.SplitFrame(
        f"TRADE - {spec.name.upper()}", "Station Inventory", "Your Hold",
        left, right,
        f"Cargo: {owned.cargo_used if owned else 0}",
        f"Credits: {ctx.stats.credits}",
        "UP/DOWN navigate  TAB switch panel  ENTER buy/sell  ESC back",
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
    # Produced goods first, then demands, then neutral goods
    # (not in either list) from the full catalog.
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

    if not _station_goods:
        ctx.log.add("This terminal has nothing to trade.")
        return

    # Preserve the tcod path's state gates before opening any optional
    # presentation worker.
    from .faction import get_attitude
    _merchant_rep = ctx.faction_reputation.get("merchant", 0)
    _attitude = get_attitude(_merchant_rep)
    if _attitude in ("enemy", "disliked"):
        ctx.log.add("The merchants refuse to trade with you.")
        return
    if ctx.player_owned_ship is None:
        ctx.log.add("You need a ship with cargo space to use this terminal.")
        return

    result = _run_pygame_trade(ctx, planet_id, _station_goods)
    if result is None:
        raise RuntimeError("Trade terminal returned no outcome")
    return
class _COut(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


def _pygame_cargo_enabled() -> bool:
    """Return whether the generic Pygame screen worker is enabled."""
    from . import pygame_screen

    return pygame_screen.enabled()


def _cargo_frame(ctx, owned, ship_name: str, max_cargo: int, selected: int):
    """Build a readable cargo snapshot with opaque jettison actions."""
    from . import pygame_screen
    from . import ship as ship_module

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
    body = (
        f"Cargo: {owned.cargo_used} / {max_cargo}    Free: {max(0, max_cargo - owned.cargo_used)}",
        f"Mission cargo reserved: {owned.mission_reserved}    Ammo: {owned.cargo_ammo}",
        f"Hull: {owned.hull_damage_pct}% damage",
    )
    footer = ("UP/DOWN or j/k select   ENTER jettison selected   ESC close",)
    return pygame_screen.ScreenFrame(
        f"CARGO - {ship_name.upper()}", body, tuple(items), footer, selected,
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
            if not action.startswith("JETTISON:") or ":" not in action:
                return None
            good_id = action.split(":", 1)[1]
            try:
                quantity = owned.inventory.get(good_id, 0)
                good = find_trade_good(good_id)
            except (KeyError, ValueError):
                return None
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
    from . import mission as mission_module
    ship_spec = ship_module.find_ship(owned.ship_id)

    # Cache static ship stats.
    from . import ship as _ship_mod
    ship_name = ship_module.ship_display_name(owned)
    max_cargo = _ship_mod.effective_max_cargo(ship_spec, owned)
    result = _run_pygame_cargo(ctx, owned, ship_name, max_cargo)
    if result is None:
        raise RuntimeError("Cargo screen returned no outcome")
    return
