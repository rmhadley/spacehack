"""Mechanic terminal menu — Refuel, Repair, and Loadout management.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import message_log
from .. import ship as ship_module
from ..data.weapons import find_weapon
from ..game_context import GameContext
from ..engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide


def _pygame_mechanic_enabled() -> bool:
    """Return whether the generic Pygame screen worker is enabled."""
    from .. import pygame_screen

    return pygame_screen.enabled()


def _mechanic_frame(ctx, ship_rec, selected: int):
    """Build a presentation snapshot for the mechanic terminal."""
    from .. import pygame_screen

    owned = ctx.player_owned_ship
    rows = tuple(
        pygame_screen.ScreenRow(label, action=action)
        for label, action in (
            ("Refuel", "REFUEL"),
            ("Repair", "REPAIR"),
            ("Manage Loadout", "LOADOUT"),
            ("Buy Ammo", "AMMO"),
        )
    )
    body = (
        f"Ship: {ship_rec.name}",
        f"Fuel: {owned.fuel} / {ship_rec.max_fuel}    Hull: {owned.hull_damage_pct}% damage",
        f"Credits: {ctx.stats.credits}$",
    )
    return pygame_screen.ScreenFrame(
        "MECHANIC TERMINAL", body, rows,
        ("UP/DOWN or j/k select   ENTER choose   ESC back",), selected,
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
    cost = int(damage * ship_rec.price // 100)
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
        try:
            outcome, action, selected = pygame_screen.run_for_context(
                ctx.context,
                _mechanic_frame(ctx, ship_rec, selected),
                caption="spacehack - mechanic",
            )
        except (pygame_screen.PygameScreenUnavailable, ValueError):
            return None
        if outcome == "GUIDE":
            from ..help import _run_help_guide
            _run_help_guide(ctx)
            continue
        if outcome in {"TAB", "PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "SELECT":
            try:
                _apply_pygame_mechanic_action(ctx, action, planet_id, ship_rec)
            except (KeyError, ValueError):
                return None
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
    if _pygame_mechanic_enabled():
        if _run_pygame_mechanic(ctx, planet_id, ship_rec) is not None:
            return

    console = make_console()
    selected = 0
    _MECH_OPTIONS = ["Refuel", "Repair", "Manage Loadout", "Buy Ammo"]

    def _render() -> None:
        nonlocal selected
        console.clear()
        stat_y = ui.screen_header(console, SCREEN_WIDTH, "MECHANIC TERMINAL")
        _stat_lines = [
            f"Ship: {ship_rec.name}",
            f"Fuel: {owned.fuel} / {ship_rec.max_fuel}  |  Hull: {owned.hull_damage_pct}% damage",
            f"Credits: {ctx.stats.credits}$",
        ]
        for i, _line in enumerate(_stat_lines):
            console.print(x=2, y=stat_y + i, string=_line, fg=ui.COLOR_VALUE_WHITE)
        _opt_items = [(opt, "") for opt in _MECH_OPTIONS]
        _list_title_y = stat_y + len(_stat_lines) + 1
        ui.render_selectable_list(
            console, SCREEN_WIDTH, SCREEN_HEIGHT,
            title="",
            items=_opt_items,
            selected=selected,
            col_x=2,
            title_y=_list_title_y,
            row_spacing=2,
            item_fg_selected=ui.COLOR_OPTION_HIGHLIGHT,
            item_fg_normal=ui.COLOR_OPTION,
            hint="UP/DOWN / j,k navigate - ENTER select - ESC back",
        )
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> _MechanicOutcome:
        nonlocal selected
        if _try_open_guide(event, ctx):
            return _MechanicOutcome.IGNORE
        if isinstance(event, tcod.event.Quit):
            return _MechanicOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _MechanicOutcome.IGNORE
        sym = event.sym
        sym_name: str = getattr(sym, 'name', '').lower()
        if sym in ui._UP_SYMS or sym_name == 'k':
            selected = (selected - 1) % len(_MECH_OPTIONS)
            return _MechanicOutcome.IGNORE
        if sym in ui._DOWN_SYMS or sym_name == 'j':
            selected = (selected + 1) % len(_MECH_OPTIONS)
            return _MechanicOutcome.IGNORE
        if sym in ui._ESCAPE_SYMS:
            return _MechanicOutcome.BACK
        if sym in ui._ENTER_SYMS:
            if selected == 0:
                return _MechanicOutcome.REFUEL
            elif selected == 1:
                return _MechanicOutcome.REPAIR
            elif selected == 2:
                return _MechanicOutcome.LOADOUT
            else:
                return _MechanicOutcome.AMMO
        return _MechanicOutcome.IGNORE

    while True:
        action = ui.Modal(ctx.context, console).run(_render, _update)
        if action is _MechanicOutcome.REFUEL:
            _refuel(ctx, owned, ship_rec)
            continue
        if action is _MechanicOutcome.REPAIR:
            _repair(ctx, owned, ship_rec)
            continue
        if action is _MechanicOutcome.LOADOUT:
            from ._loadout import _run_loadout_menu
            _run_loadout_menu(ctx, planet_id)
            continue
        if action is _MechanicOutcome.AMMO:
            _run_ammo_menu(ctx)
            continue
        return  # BACK or QUIT


def _ammo_frame(ctx, owned, missile_slots, selected):
    """Build a Pygame ammo-management snapshot."""
    from .. import pygame_screen

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
        (f"Credits: {ctx.stats.credits}$",),
        tuple(rows) or (pygame_screen.ScreenRow("No missile weapons installed", selectable=False),),
        ("ENTER buy one round   ESC back",),
        selected,
    )


def _run_pygame_ammo(ctx, owned, missile_slots) -> bool | None:
    """Run ammo purchasing through Pygame, keeping the transaction in parent."""
    from .. import pygame_screen

    selected = 0
    while True:
        try:
            outcome, action, selected = pygame_screen.run_for_context(
                ctx.context,
                _ammo_frame(ctx, owned, missile_slots, selected),
                caption="spacehack - buy ammo",
            )
        except pygame_screen.PygameScreenUnavailable:
            return None
        if outcome == "GUIDE":
            from ..help import _run_help_guide
            _run_help_guide(ctx)
            continue
        if outcome in {"TAB", "PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "QUIT":
            raise SystemExit
        if outcome == "SELECT" and action.startswith("AMMO:"):
            try:
                slot = int(action.split(":")[1])
            except (IndexError, ValueError):
                return None
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

    if _pygame_mechanic_enabled():
        if _run_pygame_ammo(ctx, owned, missile_slots) is not None:
            return

    console = make_console()
    selected = 0

    def _render() -> None:
        nonlocal selected
        console.clear()
        stat_y = ui.screen_header(console, SCREEN_WIDTH, "BUY AMMO")
        console.print(x=2, y=stat_y, string=f"Credits: {ctx.stats.credits}$", fg=ui.COLOR_VALUE_WHITE)
        _items: list[tuple[str, str]] = []
        for _slot in missile_slots:
            _ws = find_weapon(owned.weapons[_slot])
            _cur = owned.weapon_ammo.get(_slot, _ws.ammo_capacity)
            _items.append((
                f"[{_slot + 1}] {_ws.name}: {_cur}/{_ws.ammo_capacity} rounds",
                f"{_ws.ammo_price}$/round  ENTER=+1  SPACE=fill",
            ))
        ui.render_selectable_list(
            console, SCREEN_WIDTH, SCREEN_HEIGHT,
            title="",
            items=_items,
            selected=selected,
            col_x=2,
            title_y=stat_y + 2,
            row_spacing=2,
            item_fg_selected=ui.COLOR_OPTION_HIGHLIGHT,
            item_fg_normal=ui.COLOR_OPTION,
            hint="UP/DOWN / j,k navigate - ENTER buy 1 - SPACE fill - ESC back",
        )
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> _MechanicOutcome:
        nonlocal selected
        if _try_open_guide(event, ctx):
            return _MechanicOutcome.IGNORE
        if isinstance(event, tcod.event.Quit):
            return _MechanicOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _MechanicOutcome.IGNORE
        sym = event.sym
        sym_name: str = getattr(sym, 'name', '').lower()
        if sym in ui._UP_SYMS or sym_name == 'k':
            selected = (selected - 1) % len(missile_slots)
            return _MechanicOutcome.IGNORE
        if sym in ui._DOWN_SYMS or sym_name == 'j':
            selected = (selected + 1) % len(missile_slots)
            return _MechanicOutcome.IGNORE
        if sym in ui._ESCAPE_SYMS:
            return _MechanicOutcome.BACK
        if sym in ui._ENTER_SYMS:
            _buy(ctx, owned, missile_slots[selected], 1)
            return _MechanicOutcome.IGNORE
        if sym_name in ('space', 's'):
            _buy(ctx, owned, missile_slots[selected], 999)
            return _MechanicOutcome.IGNORE
        return _MechanicOutcome.IGNORE

    def _buy(_ctx, _owned, _slot, _rounds) -> None:
        _before = _owned.weapon_ammo.get(_slot, 0)
        _ok, _cost, _reason = ship_module.buy_ammo(_owned, _slot, _rounds, _ctx.stats.credits)
        if not _ok:
            _ctx.log.add(_reason)
            return
        _ws = find_weapon(_owned.weapons[_slot])
        _rounds_bought = _owned.weapon_ammo.get(_slot, 0) - _before
        _ctx.stats.credits -= _cost
        _ctx.log.add(f"Bought {_rounds_bought}x {_ws.name} ammo for {_cost}$. "
                     f"{_owned.weapon_ammo.get(_slot, 0)}/{_ws.ammo_capacity} rounds left.")

    ui.Modal(ctx.context, console).run(_render, _update)
