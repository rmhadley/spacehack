"""Mechanic terminal menu — Refuel, Repair, and Loadout management.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

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

def _mechanic_frame(ctx, ship_rec, selected: int):
    """Build a presentation snapshot for the mechanic terminal."""
    from .. import pygame_screen, pygame_ui

    owned = ctx.player_owned_ship
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
        pygame_screen.ScreenRow("Manage Loadout", "Buy and sell ship weapons and modules.", "LOADOUT"),
        pygame_screen.ScreenRow("Buy Ammo", "Replenish one missile round at a time.", "AMMO"),
    )
    body = (
        f"Ship: {ship_rec.name}",
        f"Fuel: {owned.fuel} / {ship_rec.max_fuel}    Hull: {ship_module.hull_integrity_pct(owned)}%",
        pygame_ui.credits_label(ctx.stats.credits),
        "Select Refuel or Repair to review the exact total before committing.",
    )
    return pygame_screen.ScreenFrame(
        "MECHANIC TERMINAL", body, rows,
        (pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER choose", "ESC back",
            pygame_ui.GUIDE_HINT,
        ),), selected,
    )

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

def _apply_pygame_mechanic_action(ctx, action: str, planet_id: str, ship_rec) -> bool:
    """Apply one mechanic action and keep the terminal open."""
    owned = ctx.player_owned_ship
    if action == "REFUEL":
        _refuel(ctx, owned, ship_rec)
        return True
    if action == "REPAIR":
        _repair(ctx, owned, ship_rec)
        return True
    if action == "LOADOUT":
        from ._loadout import _run_loadout_menu
        _run_loadout_menu(ctx, planet_id)
        return True
    if action == "AMMO":
        _run_ammo_menu(ctx)
        return True
    if not action:
        return True
    raise ValueError(f"Unknown mechanic action: {action!r}")

def _run_pygame_mechanic(ctx, planet_id: str, ship_rec) -> bool | None:
    """Run the mechanic terminal through Pygame, or return None on fallback."""
    from .. import pygame_screen

    selected = 0
    while True:
        outcome, action, selected = pygame_screen.run_for_context(
            ctx.context,
            _mechanic_frame(ctx, ship_rec, selected),
            caption="spacehack - mechanic",
        )
        if outcome == "GUIDE":
            from ..help import _open_context_guide
            _open_context_guide(ctx, "Ships & Equipment")
            continue
        if outcome in {"TAB", "PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "SELECT":
            try:
                _apply_pygame_mechanic_action(ctx, action, planet_id, ship_rec)
            except (KeyError, ValueError) as exc:
                ctx.log.add(f"Mechanic action failed: {exc}")
            continue
        if outcome == "QUIT":
            raise SystemExit
        return True

class _MechanicOutcome(Enum):
    """Result of the mechanic-terminal menu."""
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()
    REFUEL = auto()
    REPAIR = auto()
    LOADOUT = auto()
    AMMO = auto()

def _run_mech_menu(ctx, planet_id: str = "") -> None:
    """Show the mechanic-terminal menu with Refuel + Repair + Loadout options.

    Refuel buys fuel cells for the player's ship at the standard rate.
    Repair restores hull integrity at a cost based on damage.
    Loadout opens the split-screen part management modal.
    ``planet_id`` is forwarded to the loadout menu so it can resolve
    per-planet weapon/module inventories. Empty string = use full catalog.
    ESC / QUIT returns silently.
    """
    if ctx.player_owned_ship is None:
        ctx.log.add("You need a ship to use the mechanic terminal.")
        return

    owned = ctx.player_owned_ship
    ship_rec = ship_module.find_ship(owned.ship_id)
    _run_pygame_mechanic(ctx, planet_id, ship_rec)
    return

def _ammo_frame(ctx, owned, missile_slots, selected):
    """Build a Pygame ammo-management snapshot."""
    from .. import pygame_screen, pygame_ui

    rows = []
    for slot in missile_slots:
        weapon = find_weapon(owned.weapons[slot])
        current = owned.weapon_ammo.get(slot, weapon.ammo_capacity)
        rows.append(pygame_screen.ScreenRow(
        f"Slot {slot + 1}: {weapon.name} ({current}/{weapon.ammo_capacity})",
        f"{weapon.ammo_price}$/round",
        f"AMMO:{slot}:1",
        ))
    return pygame_screen.ScreenFrame(
        "BUY AMMO",
        (pygame_ui.credits_label(ctx.stats.credits),),
        tuple(rows) or (pygame_screen.ScreenRow("No missile weapons installed", selectable=False),),
        (pygame_ui.modal_hint(
            "ENTER buy one round", "ESC back", pygame_ui.GUIDE_HINT,
        ),),
        selected,
    )

def _run_pygame_ammo(ctx, owned, missile_slots) -> bool | None:
    """Run ammo purchasing through Pygame, keeping the transaction in parent."""
    from .. import pygame_screen

    selected = 0
    while True:
        outcome, action, selected = pygame_screen.run_for_context(
            ctx.context,
            _ammo_frame(ctx, owned, missile_slots, selected),
            caption="spacehack - buy ammo",
        )
        if outcome == "GUIDE":
            from ..help import _open_context_guide
            _open_context_guide(ctx, "Ships & Equipment")
            continue
        if outcome in {"TAB", "PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "QUIT":
            raise SystemExit
        if outcome == "SELECT" and action.startswith("AMMO:"):
            try:
                slot = int(action.split(":")[1])
            except (IndexError, ValueError) as exc:
                ctx.log.add(f"Invalid ammo selection: {exc}")
                continue
            ok, cost, reason = ship_module.buy_ammo(
                owned, slot, 1, ctx.stats.credits,
            )
            if not ok:
                ctx.log.add(reason)
            else:
                ctx.stats.credits -= cost
                weapon = find_weapon(owned.weapons[slot])
                ctx.log.add(f"Bought 1x {weapon.name} ammo for {cost}$.")
            continue
        return True

def _run_ammo_menu(ctx) -> None:
    """Buy missile ammo for installed missile weapons.

    Lists each installed missile weapon with current/max rounds and
    the per-round price. UP/DOWN selects a weapon, ENTER buys one
    round, SPACE buys up to a full magazine, ESC backs out. Persistent
    ammo (spent rounds stay spent until rebought) makes this the
    only way to replenish magazines.
    """
    if ctx.player_owned_ship is None:
        ctx.log.add("You need a ship to use the mechanic terminal.")
        return

    owned = ctx.player_owned_ship
    # Ammo is keyed by weapon SLOT index, so two launchers of the same
    # type keep independent magazines — list slot indices, not ids.
    missile_slots = [
        i for i, wid in enumerate(owned.weapons)
        if find_weapon(wid).slot_type == "missile"
    ]
    if not missile_slots:
        ctx.log.add("No missile weapons installed.")
        return

    _run_pygame_ammo(ctx, owned, missile_slots)
    return
