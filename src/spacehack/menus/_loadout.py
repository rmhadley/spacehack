"""Loadout management split-screen modal for the mechanic terminal.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

from .. import ship as ship_module

class _LoadoutOutcome(Enum):
    """Result of the mechanic loadout menu."""
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()

def _pygame_loadout_frame(
    ctx,
    planet_id: str = "",
    weapon_ids: tuple[str, ...] | None = None,
    module_ids: tuple[str, ...] | None = None,
):
    """Build a presentation-only loadout split frame.

    ``weapon_ids`` and ``module_ids`` are an optional parent-owned
    inventory snapshot. Supplying them keeps a Pygame refresh from
    re-rolling a planet's seeded mechanic stock.
    """
    from .. import pygame_split
    from .. import pygame_ui
    owned = ctx.player_owned_ship
    if owned is None:
        return pygame_split.SplitFrame(
            pygame_ui.terminal_title("MECHANIC", "SHIP LOADOUT"), "For Sale", "My Ship",
            (), (), "", "", pygame_split.SPLIT_SHOP_HINT,
        )
    ship_spec = ship_module.find_ship(owned.ship_id)
    from ..data.weapons import find_weapon as _fw, list_weapons as _lw
    from ..data.modules import find_module as _fm, list_modules as _lm
    _weapons = sorted(
        tuple(_fw(item_id) for item_id in weapon_ids)
        if weapon_ids is not None else _lw(),
        key=lambda spec: spec.price,
    )
    _modules = sorted(
        tuple(_fm(item_id) for item_id in module_ids)
        if module_ids is not None else _lm(),
        key=lambda spec: spec.price,
    )
    _left = [pygame_split.section_header("WEAPONS")]
    _left.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            f"Damage: {spec.damage}  Accuracy: {spec.accuracy}%  Range: {spec.min_range}-{spec.max_range}",
            f"BUY_WEAPON:{spec.id}",
        )
        for spec in _weapons
    )
    _left.append(pygame_split.section_header("MODULES"))
    _left.extend(
        pygame_split.SplitRow(spec.name, pygame_ui.price_cell(spec.price), spec.description, f"BUY_MODULE:{spec.id}")
        for spec in _modules
    )
    _right = [pygame_split.section_header("WEAPON SLOTS")]
    for item_id, slot_index in ship_module._find_weapon_slots(owned, ship_spec):
        if item_id is None:
            _right.append(pygame_split.SplitRow("[empty]", "", "", "", False))
        else:
            spec = _fw(item_id)
            _right.append(pygame_split.SplitRow(
                spec.name,
                pygame_ui.sell_cell(ship_module._sell_price("weapon", item_id)),
                f"Damage: {spec.damage}  Accuracy: {spec.accuracy}%  Range: {spec.min_range}-{spec.max_range}",
                f"SELL_WEAPON_SLOT:{slot_index}",
            ))
    _right.append(pygame_split.section_header("MODULE SLOTS"))
    for item_id, slot_index in ship_module._find_module_slots(owned, ship_spec):
        if item_id is None:
            _right.append(pygame_split.SplitRow("[empty]", "", "", "", False))
        else:
            spec = _fm(item_id)
            _right.append(pygame_split.SplitRow(
                spec.name, pygame_ui.sell_cell(ship_module._sell_price("module", item_id)),
                spec.description, f"SELL_MODULE_SLOT:{slot_index}",
            ))
    return pygame_split.SplitFrame(
        pygame_ui.terminal_title("MECHANIC", "SHIP LOADOUT"), "For Sale", "My Ship",
        tuple(_left), tuple(_right),
        pygame_ui.credits_label(ctx.stats.credits),
        f"Wpn: {len(owned.weapons)}/{ship_spec.weapon_slots}  Mod: {len(owned.modules)}/{ship_spec.module_slots}",
        pygame_split.SPLIT_SHOP_HINT,
    )

def _apply_pygame_loadout_action(ctx, action: str, focus: int, selected: int, planet_id: str) -> bool:
    """Apply one Pygame loadout action using existing mutation helpers."""
    if not action:
        return True
    if action.startswith("BUY_WEAPON:"):
        item_id = action.split(":", 1)[1]
        owned = ctx.player_owned_ship
        ship_spec = ship_module.find_ship(owned.ship_id)
        from ..data.weapons import find_weapon
        spec = find_weapon(item_id)
        if len(owned.weapons) < ship_spec.weapon_slots and ctx.stats.credits >= spec.price:
            if ship_module._install_weapon(owned, item_id, ship_spec):
                ctx.stats.credits -= spec.price
                ctx.log.add(f"Installed {spec.name} for {spec.price}$.")
        return True
    if action.startswith("BUY_MODULE:"):
        item_id = action.split(":", 1)[1]
        owned = ctx.player_owned_ship
        ship_spec = ship_module.find_ship(owned.ship_id)
        from ..data.modules import find_module
        spec = find_module(item_id)
        if len(owned.modules) < ship_spec.module_slots and ctx.stats.credits >= spec.price:
            if ship_module._install_module(owned, item_id, ship_spec):
                ctx.stats.credits -= spec.price
                ctx.log.add(f"Installed {spec.name} for {spec.price}$.")
        return True
    if action.startswith("SELL_WEAPON_SLOT:"):
        slot = int(action.split(":", 1)[1])
        owned = ctx.player_owned_ship
        ship_spec = ship_module.find_ship(owned.ship_id)
        slots = ship_module._find_weapon_slots(owned, ship_spec)
        if not 0 <= slot < len(slots) or slots[slot][0] is None:
            return True
        item_id = slots[slot][0]
        ship_module._remove_weapon(owned, slot)
        ctx.stats.credits += ship_module._sell_price("weapon", item_id)
        return True
    if action.startswith("SELL_MODULE_SLOT:"):
        slot = int(action.split(":", 1)[1])
        owned = ctx.player_owned_ship
        ship_spec = ship_module.find_ship(owned.ship_id)
        slots = ship_module._find_module_slots(owned, ship_spec)
        if not 0 <= slot < len(slots) or slots[slot][0] is None:
            return True
        item_id = slots[slot][0]
        ship_module._remove_module(owned, slot)
        ctx.stats.credits += ship_module._sell_price("module", item_id)
        return True
    raise ValueError(f"Unknown loadout action: {action!r}")

def _run_loadout_menu(ctx, planet_id: str = "") -> None:
    """Show the loadout management terminal in the shared Pygame window."""
    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship to manage its loadout.")
        return

    from ..data.modules import find_module as _fm, list_modules as _lm
    from ..data.planets import resolve_mech_inventory
    from ..data.weapons import find_weapon as _fw, list_weapons as _lw

    if planet_id:
        weapon_ids, module_ids = resolve_mech_inventory(planet_id)
        weapons = tuple(sorted((_fw(item_id) for item_id in weapon_ids), key=lambda item: item.price))
        modules = tuple(sorted((_fm(item_id) for item_id in module_ids), key=lambda item: item.price))
    else:
        weapons = tuple(sorted(_lw(), key=lambda item: item.price))
        modules = tuple(sorted(_lm(), key=lambda item: item.price))

    from .. import pygame_split
    pygame_split.run_interactive(
        ctx,
        lambda: _pygame_loadout_frame(
            ctx,
            planet_id,
            tuple(item.id for item in weapons),
            tuple(item.id for item in modules),
        ),
        lambda action, focus, selected: _apply_pygame_loadout_action(
            ctx, action, focus, selected, planet_id,
        ),
        caption="spacehack - ship loadout",
    )
