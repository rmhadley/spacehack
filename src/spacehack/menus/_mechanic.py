"""Mechanic terminal — tabbed modal with REPAIRS / AMMO / LOADOUT.

TAB cycles the tabs; the AMMO tab only appears while a missile
launcher is installed (it is added/removed live as the loadout
changes). REPAIRS holds Refuel + Repair; AMMO buys one round per
launcher; LOADOUT shows the installed parts and opens the buy/sell
market. Extracted from the old ``menus.py`` during the package
refactor.
"""

from __future__ import annotations

from .. import ship as ship_module
from ..data.weapons import find_weapon


def _refuel_preview(owned, ship_rec, credits: int) -> tuple[int, int]:
    """Return the fuel units and credits needed by the refuel action."""
    units = max(0, min(ship_rec.max_fuel - owned.fuel, credits // ship_module.FUEL_COST_PER_UNIT))
    return units, units * ship_module.FUEL_COST_PER_UNIT

# Full hull repair costs this percentage of the ship's purchase price.
# Repairing is labour + parts, not a replacement hull — the old
# ``damage_pct * price // 100`` formula charged 100% of the ship's
# value to rebuild it (a 500$ Skiff cost 500$ to repair).
_REPAIR_COST_PCT = 10

def _repair_preview(owned, ship_rec) -> int:
    """Return the hull repair price for the current damage.

    Full repair costs ``_REPAIR_COST_PCT``% of the ship's purchase
    price; partial damage scales linearly (10% damage = 10% of the
    full-repair price).
    """
    damage = max(0, min(100, owned.hull_damage_pct))
    return max(0, int(ship_rec.price * damage * _REPAIR_COST_PCT // 10000))


def _refuel(ctx, owned, ship_rec) -> None:
    """Apply the mechanic's refuel transaction."""
    buyable = ship_rec.max_fuel - owned.fuel
    affordable = ctx.stats.credits // ship_module.FUEL_COST_PER_UNIT
    if buyable <= 0:
        ctx.log.add("The fuel tank is already full.")
    elif affordable <= 0:
        ctx.log.add("You don't have enough credits to buy fuel.")
    else:
        units = min(buyable, affordable)
        cost = units * ship_module.FUEL_COST_PER_UNIT
        ctx.stats.credits -= cost
        owned.fuel += units
        ctx.log.add(f"Refueled {units} units for {cost}$. Fuel: {owned.fuel} / {ship_rec.max_fuel}.")


def _repair(ctx, owned, ship_rec) -> None:
    """Apply the mechanic's hull repair transaction."""
    damage = owned.hull_damage_pct
    if damage <= 0:
        ctx.log.add("No repairs needed -- hull integrity is 100%.")
        return
    cost = _repair_preview(owned, ship_rec)
    if ctx.stats.credits < cost:
        ctx.log.add(f"Repair would cost {cost}$, but you only have {ctx.stats.credits}$.")
        return
    ctx.stats.credits -= cost
    owned.hull_damage_pct = 0
    ctx.log.add(f"Repaired hull to 100% for {cost}$.")


# Table-driven dispatch for the REPAIRS tab (guardrail: no chained
# if/elif for action routing).
_REPAIRS_ACTIONS = {
    "REFUEL": _refuel,
    "REPAIR": _repair,
}


_MECHANIC_TABS: tuple[str, ...] = ("REPAIRS", "AMMO", "LOADOUT")
"""Canonical tab set; the AMMO tab is dropped when no launcher is installed."""


def _mechanic_tabs(missile_slots) -> tuple[str, ...]:
    """Return the mechanic tab set; AMMO only when a launcher is installed."""
    if missile_slots:
        return _MECHANIC_TABS
    return ("REPAIRS", "LOADOUT")


def _ammo_row(owned, slot: int):
    """Build one missile-slot ammo row (buy one round)."""
    from .. import pygame_screen

    weapon = find_weapon(owned.weapons[slot])
    current = owned.weapon_ammo.get(slot, weapon.ammo_capacity)
    return pygame_screen.ScreenRow(
        f"Slot {slot + 1}: {weapon.name} ({current}/{weapon.ammo_capacity})",
        f"{weapon.ammo_price}$/round",
        f"AMMO:{slot}:1",
    )


def _repairs_section(ctx, owned, ship_rec, next_hint, _missile_slots):
    """Build the REPAIRS tab's rows, body, and footer."""
    from .. import pygame_screen, pygame_ui

    _fuel_units, _fuel_cost = _refuel_preview(owned, ship_rec, ctx.stats.credits)
    _repair_cost = _repair_preview(owned, ship_rec)
    rows = (
        pygame_screen.ScreenRow(
            f"Refuel - {_fuel_cost}$ for {_fuel_units} units",
            f"{ship_module.FUEL_COST_PER_UNIT}$/unit; fills the tank up to your available credits.",
            "REFUEL",
        ),
        pygame_screen.ScreenRow(
            f"Repair - {_repair_cost}$ to restore hull",
            f"Restores {owned.hull_damage_pct}% damage; full repair costs 10% of the ship's value.",
            "REPAIR",
        ),
    )
    _hull_cur, _hull_max = ship_module.hull_cur_max(owned, ship_rec)
    body = (
        f"Ship: {ship_rec.name}",
        f"Fuel: {owned.fuel} / {ship_rec.max_fuel}    Hull: {_hull_cur} / {_hull_max}",
        pygame_ui.credits_label(ctx.stats.credits),
        "Select Refuel or Repair to review the exact total before committing.",
    )
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "ENTER choose", next_hint,
        "ESC back", pygame_ui.GUIDE_HINT,
    ),)
    return rows, body, footer


def _ammo_section(ctx, owned, ship_rec, next_hint, missile_slots):
    """Build the AMMO tab's rows, body, and footer."""
    from .. import pygame_ui

    rows = tuple(_ammo_row(owned, slot) for slot in missile_slots)
    body = (
        pygame_ui.credits_label(ctx.stats.credits),
        "Buy one round per missile launcher.",
    )
    footer = (pygame_ui.modal_hint(
        "ENTER buy one round", next_hint, "ESC back", pygame_ui.GUIDE_HINT,
    ),)
    return rows, body, footer


def _loadout_section(ctx, owned, ship_rec, next_hint, _missile_slots):
    """Build the LOADOUT tab's rows, body, and footer."""
    from .. import pygame_screen, pygame_ui
    from ._ship_menu import _loadout_rows

    rows = (
        pygame_screen.ScreenRow("PARTS MARKET", selectable=False, header=True),
        pygame_screen.ScreenRow(
            "Manage Loadout - buy and sell parts",
            "Opens the parts market for this planet (weapons + modules).",
            "LOADOUT",
        ),
    ) + _loadout_rows(owned, ship_rec)
    body = ("Buy and sell ship weapons and modules.",)
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "ENTER manage loadout", next_hint,
        "ESC back", pygame_ui.GUIDE_HINT,
    ),)
    return rows, body, footer


def _mechanic_frame(ctx, ship_rec, tab: int, selected: int, tabs, missile_slots):
    """Build one tabbed mechanic snapshot (REPAIRS / AMMO / LOADOUT)."""
    from .. import pygame_screen

    owned = ctx.player_owned_ship
    tab_name = tabs[tab]
    next_hint = f"TAB {tabs[(tab + 1) % len(tabs)].lower()}"
    sections = {
        "REPAIRS": _repairs_section,
        "AMMO": _ammo_section,
        "LOADOUT": _loadout_section,
    }
    rows, body, footer = sections[tab_name](
        ctx, owned, ship_rec, next_hint, missile_slots,
    )
    return pygame_screen.ScreenFrame(
        title="MECHANIC TERMINAL", body=body, rows=rows, footer=footer,
        selected=selected, tabs=tabs, active_tab=tab,
    )


def _apply_mechanic_selection(ctx, owned, ship_rec, planet_id, tab_name, action):
    """Apply one REPAIRS/AMMO/LOADOUT selection; the terminal stays open."""
    if tab_name == "REPAIRS":
        handler = _REPAIRS_ACTIONS.get(action)
        if handler is not None:
            handler(ctx, owned, ship_rec)
        return
    if tab_name == "AMMO" and action.startswith("AMMO:"):
        try:
            slot = int(action.split(":")[1])
        except (IndexError, ValueError) as exc:
            ctx.log.add(f"Invalid ammo selection: {exc}")
            return
        ok, cost, reason = ship_module.buy_ammo(owned, slot, 1, ctx.stats.credits)
        if not ok:
            ctx.log.add(reason)
        else:
            ctx.stats.credits -= cost
            weapon = find_weapon(owned.weapons[slot])
            ctx.log.add(f"Bought 1x {weapon.name} ammo for {cost}$.")
        return
    if tab_name == "LOADOUT" and action == "LOADOUT":
        from ._loadout import _run_loadout_menu
        _run_loadout_menu(ctx, planet_id)
        return


def _run_pygame_mechanic(ctx, planet_id: str, ship_rec) -> bool | None:
    """Run the tabbed mechanic terminal through the shared Pygame screen."""
    from .. import pygame_screen

    tab = 0
    selected = 0
    while True:
        owned = ctx.player_owned_ship
        missile_slots = [
            i for i, wid in enumerate(owned.weapons)
            if find_weapon(wid).slot_type == "missile"
        ]
        tabs = _mechanic_tabs(missile_slots)
        if tab >= len(tabs):
            tab = 0
        outcome, action, selected = pygame_screen.run_for_context(
            ctx.context,
            _mechanic_frame(ctx, ship_rec, tab, selected, tabs, missile_slots),
            caption="spacehack - mechanic",
        )
        if outcome == "GUIDE":
            from ..help import _open_context_guide
            _open_context_guide(ctx, "Ships & Equipment")
            continue
        if outcome == "TAB":
            tab = (tab + 1) % len(tabs)
            selected = 0
            continue
        if outcome in {"PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "QUIT":
            raise SystemExit
        if outcome == "SELECT":
            _apply_mechanic_selection(
                ctx, owned, ship_rec, planet_id, tabs[tab], action,
            )
            continue
        return True  # BACK


def _run_mech_menu(ctx, planet_id: str = "") -> None:
    """Show the tabbed mechanic terminal (REPAIRS / AMMO / LOADOUT).

    Refuel buys fuel cells for the player's ship at the standard rate.
    Repair restores hull integrity at a cost based on damage (10% of
    the ship's value at full damage). AMMO buys missile rounds for
    installed launchers. LOADOUT opens the split-screen parts market.
    ``planet_id`` is forwarded to the loadout menu so it can resolve
    per-planet weapon/module inventories. Empty string = use full
    catalog. ESC / QUIT returns silently.
    """
    if ctx.player_owned_ship is None:
        ctx.log.add("You need a ship to use the mechanic terminal.")
        return

    owned = ctx.player_owned_ship
    ship_rec = ship_module.find_ship(owned.ship_id)
    _run_pygame_mechanic(ctx, planet_id, ship_rec)
    return
