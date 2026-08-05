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
        return int(base_price * (2.0 - ratio * 2.0))
    else:
        # Surplus zone: 1.0\u00d7 linearly down to 0.6\u00d7 at 100%.
        return int(base_price * (1.0 - (ratio - 0.5) * 0.8))


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

        cy = (SCREEN_HEIGHT - MSG_LOG_HEIGHT) // 2
        paint_centered(console, cy - 2, prompt, fg=ui.COLOR_TITLE)
        paint_centered(console, cy + 1, qty_text, fg=ui.COLOR_VALUE_WHITE)
        paint_centered(console, cy + 3, hint, fg=ui.COLOR_INSTRUCTION)

    def _update(event: tcod.event.Event) -> _QOut:
        nonlocal qty

        if _try_open_guide(event, ctx):
            return _QOut.IGNORE

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


class _LootOutcome(Enum):
    IGNORE = auto()
    TAKE = auto()
    LEAVE = auto()
    QUIT = auto()


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
                ctx.log.add("The quest cache contains unknown goods — ignored.")
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

    console = make_console()
    _is_heist = getattr(loot_entity, 'heist_mission', False)

    def _render() -> None:
        console.clear()
        if _is_quest:
            title = "QUEST CACHE"
            _parts = []
            for _gid, _qty in _goods:
                try:
                    _parts.append(f"{find_trade_good(_gid).name} x{_qty}")
                except KeyError:
                    _parts.append(f"{_gid} x{_qty}")
            label = "Secured quest contents:"
            contents = ", ".join(_parts)
            take_label = "Secure"
            hint = "ENTER to secure  |  ESC to leave"
        elif _is_heist:
            title = "MISSION CARGO"
            label = "Secured mission cargo:"
            contents = f"{good.name} x{quantity}"
            take_label = "Secure"
            hint = "ENTER to secure  |  ESC to leave"
        else:
            title = "CARGO DEBRIS"
            label = f"You found {good.name} x{quantity}"
            contents = ""
            take_label = "Take"
            hint = "ENTER to take  |  ESC to leave"
        line2 = (
            contents
            if contents
            else f"Value: {good.base_price}$ each  |  Volume: {good.volume} crate(s)"
        )

        cy = (SCREEN_HEIGHT - MSG_LOG_HEIGHT) // 2 - 2
        paint_centered(console, cy, title, fg=ui.COLOR_TITLE)
        paint_centered(console, cy + 2, label, fg=ui.COLOR_VALUE_WHITE)
        paint_centered(console, cy + 3, line2, fg=ui.COLOR_VALUE_DIM)

        ui.render_selectable_list(
            console, SCREEN_WIDTH, SCREEN_HEIGHT,
            title="",
            items=[(take_label, "")],
            selected=0,
            title_y=cy + 4,
            hint=hint,
        )

    def _update(event) -> _LootOutcome:
        if _try_open_guide(event, ctx):
            return _LootOutcome.IGNORE
        if isinstance(event, tcod.event.Quit):
            return _LootOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _LootOutcome.IGNORE
        if event.sym in ui._ESCAPE_SYMS:
            return _LootOutcome.LEAVE
        if event.sym in ui._ENTER_SYMS:
            return _LootOutcome.TAKE
        return _LootOutcome.IGNORE

    _outcome = ui.Modal(ctx.context, console).run(_render, _update)
    if _outcome is _LootOutcome.TAKE:
        if _is_quest:
            from . import main_quest as _mq
            _secured = _mq.secure_quest_loot(ctx, loot_entity, _goods)
            if not _secured:
                # Quest step not active (stale cache from an aborted run) —
                # grant the goods anyway so the find isn't wasted.
                for _gid, _qty in _goods:
                    owned.inventory[_gid] = owned.inventory.get(_gid, 0) + _qty
                ctx.log.add("Picked up leftover quest cache goods.")
        else:
            _secured = False
            if getattr(loot_entity, 'heist_mission', False):
                _secured = _secure_heist_cargo(ctx, loot_entity, good_id, quantity)
            if _secured:
                ctx.log.add(
                    f"Secured mission cargo: {good.name} x{quantity} "
                    f"(reserved in hold). Do not sell!"
                )
            else:
                owned.inventory[good_id] = owned.inventory.get(good_id, 0) + quantity
                ctx.log.add(f"Picked up {good.name} x{quantity} from space debris.")
        if loot_entity in ctx.game_map.entities:
            try:
                ctx.game_map.entities.remove(loot_entity)
            except ValueError:
                pass
    elif _outcome is _LootOutcome.LEAVE or _outcome is _LootOutcome.QUIT:
        ctx.log.add("Left the cargo debris in space.")
        return


# ---------------------------------------------------------------------------
# NPC trade modal (Phase 4 — merchant ships from comms)
# ---------------------------------------------------------------------------


class _NpcTradeOutcome(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


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

    console = make_console()

    def _render() -> None:
        nonlocal _sel

        # Pre-compute left panel rows (NPC goods).
        _left_rows: list[tuple[str, str, str, tuple]] = []
        for i, gid in enumerate(_npc_goods):
            if i >= SCREEN_HEIGHT - 12:
                break
            good = find_trade_good(gid)
            stock = _npc_stock.get(gid, 0)
            price = int(good.base_price * _BUY_MULT)
            price_label = f"{price:>5}$"
            suffix = f"({stock:>3})"
            _left_rows.append((good.name, price_label, suffix, ui.COLOR_OPTION))

        # Pre-compute right panel rows (player goods).
        _right_rows: list[tuple[str, str, str, tuple]] = []
        inv_items = list(owned.inventory.items())
        for i, (gid, qty) in enumerate(inv_items):
            if i >= SCREEN_HEIGHT - 12:
                break
            good = find_trade_good(gid)
            sell_price = int(good.base_price * _SELL_MULT)
            price_label = f"{sell_price:>5}$"
            suffix = f"({qty:>3})"
            _right_rows.append((good.name, price_label, suffix, ui.COLOR_OPTION))

        # Footer strings.
        from . import ship as ship_module
        ship_spec = ship_module.find_ship(owned.ship_id)
        _eff_cargo = ship_module.effective_max_cargo(ship_spec, owned)
        cargo_str = f"Cargo: {owned.cargo_used}/{_eff_cargo}"
        credits_str = f"Credits: {ctx.stats.credits}"

        render_split_frame(
            console,
            title=f"TRADE \u2014 {npc_spec.name.upper()}",
            left_label=f"\u2502 {npc_spec.name}" if _focus == 0 else f"  {npc_spec.name} ",
            right_label="\u2502 Your Hold" if _focus == 1 else "  Your Hold ",
            focus=_focus,
            sel=_sel,
            left_rows=_left_rows,
            right_rows=_right_rows,
            footer_left=cargo_str,
            footer_right=credits_str,
            hint="UP/DOWN navigate  ENTER buy/sell  TAB switch panel  ESC back",
            log=ctx.log,
        )

    def _update(event: tcod.event.Event) -> _NpcTradeOutcome:
        nonlocal _focus, _sel

        if _try_open_guide(event, ctx):
            return _NpcTradeOutcome.IGNORE

        if isinstance(event, tcod.event.Quit):
            return _NpcTradeOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _NpcTradeOutcome.IGNORE

        sym = event.sym
        sym_name = getattr(sym, "name", "").lower()

        if sym in ui._ESCAPE_SYMS:
            return _NpcTradeOutcome.BACK
        if sym_name == "tab":
            _focus = 1 - _focus
            _sel = 0
            return _NpcTradeOutcome.IGNORE

        is_up = sym in ui._UP_SYMS or sym_name == "k"
        is_down = sym in ui._DOWN_SYMS or sym_name == "j"
        if is_up:
            if _focus == 0:
                _sel = (_sel - 1) % max(1, len(_npc_goods))
            else:
                n = len(owned.inventory)
                _sel = (_sel - 1) % max(1, n)
            return _NpcTradeOutcome.IGNORE
        if is_down:
            if _focus == 0:
                _sel = (_sel + 1) % max(1, len(_npc_goods))
            else:
                n = len(owned.inventory)
                _sel = (_sel + 1) % max(1, n)
            return _NpcTradeOutcome.IGNORE

        if sym in ui._ENTER_SYMS:
            if _focus == 0:
                # Buy from NPC.
                if 0 <= _sel < len(_npc_goods):
                    gid = _npc_goods[_sel]
                    good = find_trade_good(gid)
                    price = int(good.base_price * _BUY_MULT)
                    stock = _npc_stock.get(gid, 0)
                    free = _free_cargo(owned)
                    can_afford = ctx.stats.credits // price if price > 0 else 999
                    max_qty = min(stock, free // max(1, good.volume), can_afford, 999)
                    if max_qty >= 1:
                        q = _run_quantity_prompt(ctx, f"Buy {good.name} from {npc_spec.name}", max_qty, price)
                        if q is not None:
                            cost = price * q
                            owned.inventory[gid] = owned.inventory.get(gid, 0) + q
                            _npc_stock[gid] = stock - q
                            ctx.stats.credits -= cost
                            ctx.log.add(f"Bought {q}x {good.name} from {npc_spec.name} for {cost}$.")
                    else:
                        ctx.log.add(f"{npc_spec.name} has insufficient stock or you cannot afford/store {good.name}.")
            else:
                # Sell to NPC.
                inv_items = list(owned.inventory.items())
                if 0 <= _sel < len(inv_items):
                    gid, qty = inv_items[_sel]
                    good = find_trade_good(gid)
                    sell_price = int(good.base_price * _SELL_MULT)
                    max_q = min(qty, 999)
                    q = _run_quantity_prompt(ctx, f"Sell {good.name} to {npc_spec.name}", max_q, sell_price)
                    if q is not None:
                        revenue = sell_price * q
                        remaining = qty - q
                        if remaining <= 0:
                            del owned.inventory[gid]
                        else:
                            owned.inventory[gid] = remaining
                        # NPC adds to stock (just for bookkeeping, not persisted).
                        _npc_stock[gid] = _npc_stock.get(gid, 0) + q
                        ctx.stats.credits += revenue
                        ctx.log.add(f"Sold {q}x {good.name} to {npc_spec.name} for {revenue}$.")
            return _NpcTradeOutcome.IGNORE

        return _NpcTradeOutcome.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)


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

    # Faction rep gating: enemy/disliked can't use trade terminals.
    from .faction import get_attitude
    _merchant_rep = ctx.faction_reputation.get("merchant", 0)
    _attitude = get_attitude(_merchant_rep)

    if ctx.player_owned_ship is None:
        ctx.log.add("You need a ship with cargo space to use this terminal.")
        return

    _focus: int = 0        # 0 = station panel, 1 = player panel
    _sel: int = 0
    ctx.log.add(f"You approach the Trade Terminal at {spec.name}.")

    console = make_console()

    def _render() -> None:
        nonlocal _sel
        owned = ctx.player_owned_ship

        # Pre-compute left panel rows (station goods).
        _left_rows: list[tuple[str, str, str, tuple]] = []
        for i, gid in enumerate(_station_goods):
            if i >= SCREEN_HEIGHT - 12:
                break
            good = find_trade_good(gid)
            price = _unit_price(ctx, planet_id, gid)
            stock = _stocks.get(gid, 0)
            price_label = f"{price:>5}$"
            suffix = f"({stock:>3})"
            _left_rows.append((good.name, price_label, suffix, ui.COLOR_OPTION))

        # Pre-compute right panel rows (player goods).
        _right_rows: list[tuple[str, str, str, tuple]] = []
        if owned is not None:
            inv_items = list(owned.inventory.items())
        else:
            inv_items = []
        for i, (gid, qty) in enumerate(inv_items):
            if i >= SCREEN_HEIGHT - 12:
                break
            good = find_trade_good(gid)
            sell_price = _sell_price(ctx, planet_id, gid)
            price_label = f"{sell_price:>5}$"
            _contra = good.category == "contraband" and not _can_sell_here(planet_id, gid)
            if _contra:
                price_label = f"  ---$"
            suffix = f"({qty:>3})"
            fg = ui.COLOR_VALUE_DIM if _contra else ui.COLOR_OPTION
            _right_rows.append((good.name, price_label, suffix, fg))

        # Footer strings.
        if owned is not None:
            from . import ship as ship_module
            ship_spec = ship_module.find_ship(owned.ship_id)
            _eff_cargo = ship_module.effective_max_cargo(ship_spec, owned)
            cargo_str = f"Cargo: {owned.cargo_used}/{_eff_cargo}"
        else:
            cargo_str = "Cargo: N/A"
        credits_str = f"Credits: {ctx.stats.credits}"

        render_split_frame(
            console,
            title=f"TRADE — {spec.name.upper()}",
            left_label="\u2502 Station Inventory" if _focus == 0 else "  Station Inventory ",
            right_label="\u2502 Your Hold" if _focus == 1 else "  Your Hold ",
            focus=_focus,
            sel=_sel,
            left_rows=_left_rows,
            right_rows=_right_rows,
            footer_left=cargo_str,
            footer_right=credits_str,
            hint="UP/DOWN navigate  ENTER buy/sell  TAB switch panel  ESC back",
            log=ctx.log,
        )

    def _update(event: tcod.event.Event) -> _TradeOutcome:
        nonlocal _focus, _sel

        if _try_open_guide(event, ctx):
            return _TradeOutcome.IGNORE

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
                        sell_p = _sell_price(ctx, planet_id, gid)
                        q = _run_quantity_prompt(ctx, f"Sell {find_trade_good(gid).name}", max_qty, sell_p)
                        if q is not None:
                            _sell_good(ctx, planet_id, gid, q)
            return _TradeOutcome.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Cargo management modal
# ---------------------------------------------------------------------------


class _COut(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


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
    hull_damage = owned.hull_damage_pct
    weapons_n = len(owned.weapons)
    weapon_slots = ship_spec.weapon_slots
    modules_n = len(owned.modules)
    module_slots = ship_spec.module_slots

    # Active mission titles (for display).
    mission_title = ""
    active_missions = ctx.player_active_missions
    if active_missions:
        titles = [m.title for m in active_missions]
        mission_title = ", ".join(titles) if titles else ""

    console = make_console()
    _sel: int = 0

    def _rebuild_trade_items() -> list[tuple[str, int, int]]:
        """Return [(good_id, qty, volume), ...] from current inventory."""
        items: list[tuple[str, int, int]] = []
        for gid, qty in owned.inventory.items():
            try:
                good = find_trade_good(gid)
                items.append((gid, qty, good.volume * qty))
            except KeyError:
                items.append((gid, qty, 0))
        return items

    def _render() -> None:
        nonlocal _sel
        console.clear()

        _items = _rebuild_trade_items()
        _cargo_used = owned.cargo_used
        _free = max_cargo - _cargo_used
        _ammo = owned.cargo_ammo
        _mission_res = owned.mission_reserved

        # Title + header rule (unified screen header)
        title = f"CARGO \u2014 {ship_name.upper()} ({_cargo_used}/{max_cargo})"
        cy = ui.screen_header(console, SCREEN_WIDTH, title)

        # Ship stats header
        header = f"Hull: {hull_damage}% damage  |  Wpn: {weapons_n}/{weapon_slots}  |  Mod: {modules_n}/{module_slots}"
        paint_text(console, 2, cy, header, fg=ui.COLOR_VALUE_DIM)
        cy += 2

        # Section rule
        ui.paint_rule(console, 2, cy, ui.rule_width(SCREEN_WIDTH))
        cy += 1

        # Trade goods section
        paint_text(console, 2, cy, "TRADE GOODS:", fg=ui.COLOR_TITLE)
        cy += 1
        if _items:
            for i, (gid, qty, vol) in enumerate(_items):
                if i > 25:
                    break
                try:
                    good = find_trade_good(gid)
                    name = good.name
                except KeyError:
                    name = gid
                is_sel = i == _sel
                marker = "> " if is_sel else "  "
                line = f"{marker}{name:<20} {qty:>3} crates ({vol:>3}u)"
                fg = ui.COLOR_OPTION_HIGHLIGHT if is_sel else ui.COLOR_OPTION
                paint_text(console, 4, cy, line, fg=fg)
                cy += 1
        else:
            paint_text(console, 4, cy, "(empty)", fg=ui.COLOR_VALUE_DIM)
            cy += 1
        cy += 1

        # Mission cargo (read-only)
        paint_text(console, 2, cy, "MISSION CARGO:", fg=ui.COLOR_TITLE)
        cy += 1
        if active_missions:
            paint_text(console, 4, cy, f"{_mission_res} unit{'' if _mission_res == 1 else 's'} reserved \u2014 {mission_title}", fg=ui.COLOR_VALUE_WHITE)
        else:
            paint_text(console, 4, cy, "0 units (no active mission)", fg=ui.COLOR_VALUE_DIM)
        cy += 2

        # Ammo (read-only)
        paint_text(console, 2, cy, "AMMO:", fg=ui.COLOR_TITLE)
        cy += 1
        paint_text(console, 4, cy, f"{_ammo} unit{'' if _ammo == 1 else 's'}", fg=ui.COLOR_VALUE_WHITE)
        cy += 2

        # Free space
        paint_text(console, 2, cy, "FREE:", fg=ui.COLOR_TITLE)
        cy += 1
        free_fg = ui.COLOR_VALUE_WHITE if _free > 0 else (255, 80, 80)
        paint_text(console, 4, cy, f"{_free} unit{'' if _free == 1 else 's'}", fg=free_fg)
        cy += 2

        # Jettison hint (only when there are trade goods to jettison)
        if _items:
            hint = "[J] jettison selected  [C/ESC] close"
        else:
            hint = "[C/ESC] close"
        paint_text(console, 2, cy, hint, fg=ui.COLOR_INSTRUCTION)

        # Message log pinned at the bottom (terminal look).
        message_log.render_message_log(
            console, ctx.log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )

    def _update(event: tcod.event.Event) -> _COut:
        nonlocal _sel

        if _try_open_guide(event, ctx):
            return _COut.IGNORE

        if isinstance(event, tcod.event.Quit):
            return _COut.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _COut.IGNORE

        sym = event.sym
        sym_name = getattr(sym, "name", "").lower()

        # ESC or C = close
        if sym in ui._ESCAPE_SYMS or sym_name == "c":
            return _COut.BACK

        # Rebuild for current state.
        _items = _rebuild_trade_items()

        # Shift+J = jettison selected good (checked BEFORE navigation
        # so plain ``j`` still navigates down but Shift+J fires the
        # jettison prompt). SDL/tcod reports the same sym.name for
        # both upper and lowercase letters, so we must check the
        # shift modifier directly rather than relying on the name.
        _shift_held = bool(
            event.mod & (tcod.event.Modifier.LSHIFT | tcod.event.Modifier.RSHIFT)
        ) if hasattr(tcod.event, 'Modifier') else False
        if _shift_held and sym_name == "j" and _items and 0 <= _sel < len(_items):
            gid, qty, _ = _items[_sel]
            try:
                good = find_trade_good(gid)
            except KeyError:
                return _COut.IGNORE
            max_q = min(qty, 9999)
            q = _run_quantity_prompt(
                ctx, f"Jettison {good.name}", max_q, 0,
            )
            if q is not None and q > 0:
                remaining = qty - q
                if remaining <= 0:
                    del owned.inventory[gid]
                else:
                    owned.inventory[gid] = remaining
                ctx.log.add(f"Jettisoned {q}x {good.name} into space.")
                # Rebuild items to update _sel in case last item was removed.
                _new_items = _rebuild_trade_items()
                if _sel >= len(_new_items):
                    _sel = max(0, len(_new_items) - 1)
            return _COut.IGNORE

        # Up/Down navigation (lowercase j = down, k = up).
        is_up = sym in ui._UP_SYMS or sym_name == "k"
        is_down = sym in ui._DOWN_SYMS or sym_name == "j"
        if is_up:
            _sel = (_sel - 1) % max(1, len(_items))
            return _COut.IGNORE
        if is_down:
            _sel = (_sel + 1) % max(1, len(_items))
            return _COut.IGNORE

        return _COut.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)
