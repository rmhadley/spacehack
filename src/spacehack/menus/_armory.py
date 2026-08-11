"""Armory terminal split-screen — buy and sell ground-combat gear.

Mirrors the mechanic loadout menu (``_loadout.py``) exactly:

* Left panel = items for sale (weapons then armour).
* Right panel = your equipped slots (2 weapon + 5 armour) with sell prices.
* ENTER on left = buy + auto-equip to first compatible empty slot.
* ENTER on right = sell equipped item for half price.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from ..game_context import GameContext
from ..engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide
from ..ui import render_split_frame


def _pygame_split_enabled() -> bool:
    """Return whether the shared split-screen Pygame batch is enabled."""
    from .. import pygame_split

    return pygame_split.enabled()


class _ArmoryOutcome(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


_ARMOR_SLOTS: tuple[str, ...] = ("head", "body", "hands", "legs", "feet")
_ARMOR_SLOT_LABELS: dict[str, str] = {
    "head": "Head", "body": "Body", "hands": "Hands",
    "legs": "Legs", "feet": "Feet",
}


def _sell_price(item_id: str) -> int:
    """Half the buy price of a ground weapon or armor piece."""
    from ..data.ground_weapons import find_ground_weapon as _fgw
    from ..data.ground_armor import find_ground_armor as _fga
    try:
        return _fgw(item_id).price // 2
    except KeyError:
        pass
    try:
        return _fga(item_id).price // 2
    except KeyError:
        pass
    return 0


def _pygame_armory_frame(ctx: GameContext, planet_id: str = ""):
    """Build a presentation-only armory split frame.

    ``planet_id`` feeds the venue title (``ARMORY - <PLANET>``); empty
    falls back to a bare ``ARMORY`` title.
    """
    from .. import pygame_split
    from .. import pygame_ui
    from ..data.ground_weapons import list_ground_weapons
    from ..data.ground_armor import list_ground_armor
    _left = [pygame_split.section_header("WEAPONS")]
    _left.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            f"Damage: {spec.damage}  Accuracy: {spec.accuracy}%  Range: {spec.min_range}-{spec.max_range}",
            f"BUY_WEAPON:{spec.id}",
        )
        for spec in sorted(list_ground_weapons(), key=lambda item: item.price)
        if getattr(spec, "shop_available", True)
    )
    _left.append(pygame_split.section_header("ARMOUR"))
    _left.extend(
        pygame_split.SplitRow(spec.name, pygame_ui.price_cell(spec.price), spec.description, f"BUY_ARMOR:{spec.id}")
        for spec in sorted(list_ground_armor(), key=lambda item: item.price)
    )
    _right = [pygame_split.section_header("WEAPON SLOTS")]
    weapons = list(ctx.equipped_ground_weapons)
    while len(weapons) < 2:
        weapons.append("")
    from ..data.ground_weapons import find_ground_weapon
    from ..data.ground_armor import find_ground_armor
    for index, item_id in enumerate(weapons[:2]):
        if item_id:
            spec = find_ground_weapon(item_id)
            _right.append(pygame_split.SplitRow(
                spec.name,
                pygame_ui.sell_cell(_sell_price(item_id)),
                f"Damage: {spec.damage}  Accuracy: {spec.accuracy}%  Range: {spec.min_range}-{spec.max_range}",
                f"SELL_WEAPON:{index}",
            ))
        else:
            _right.append(pygame_split.SplitRow("[empty]", "", "", "", False))
    _right.append(pygame_split.section_header("ARMOUR SLOTS"))
    for slot in _ARMOR_SLOTS:
        item_id = ctx.equipped_ground_armor.get(slot)
        if item_id:
            spec = find_ground_armor(item_id)
            _right.append(pygame_split.SplitRow(
                f"{_ARMOR_SLOT_LABELS[slot]}: {spec.name}",
                pygame_ui.sell_cell(_sell_price(item_id)), spec.description,
                f"SELL_ARMOR:{slot}",
            ))
        else:
            _right.append(pygame_split.SplitRow(f"{_ARMOR_SLOT_LABELS[slot]}: [empty]", "", "", "", False))
    return pygame_split.SplitFrame(
        pygame_ui.terminal_title("ARMORY", planet_id), "For Sale", "My Loadout",
        tuple(_left), tuple(_right),
        pygame_ui.credits_label(ctx.stats.credits),
        f"Wpn: {len(ctx.equipped_ground_weapons)}/2  Arm: {len(ctx.equipped_ground_armor)}/5",
        pygame_split.SPLIT_SHOP_HINT,
    )


def _apply_pygame_armory_action(ctx: GameContext, action: str, focus: int, selected: int) -> bool:
    """Apply one Pygame armory action using the existing parent logic."""
    from ..data.ground_weapons import find_ground_weapon
    from ..data.ground_armor import find_ground_armor
    if not action:
        return True
    if action.startswith("BUY_WEAPON:"):
        item_id = action.split(":", 1)[1]
        spec = find_ground_weapon(item_id)
        weapons = list(ctx.equipped_ground_weapons)
        if ctx.stats.credits >= spec.price and len(weapons) < 2:
            ctx.equipped_ground_weapons.append(item_id)
            ctx.stats.credits -= spec.price
            ctx.log.add(f"Bought and equipped {spec.name} for {spec.price}$.")
    elif action.startswith("BUY_ARMOR:"):
        item_id = action.split(":", 1)[1]
        spec = find_ground_armor(item_id)
        if ctx.stats.credits >= spec.price and spec.slot not in ctx.equipped_ground_armor:
            ctx.equipped_ground_armor[spec.slot] = item_id
            ctx.stats.credits -= spec.price
            ctx.log.add(f"Bought and equipped {spec.name} for {spec.price}$.")
    elif action.startswith("SELL_WEAPON:"):
        index = int(action.split(":", 1)[1])
        weapons = list(ctx.equipped_ground_weapons)
        if 0 <= index < len(weapons) and weapons[index]:
            item_id = weapons[index]
            del weapons[index]
            ctx.equipped_ground_weapons = weapons
            ctx.stats.credits += _sell_price(item_id)
    elif action.startswith("SELL_ARMOR:"):
        slot = action.split(":", 1)[1]
        item_id = ctx.equipped_ground_armor.pop(slot, None)
        if item_id:
            ctx.stats.credits += _sell_price(item_id)
    else:
        raise ValueError(f"Unknown armory action: {action!r}")
    return True


def _run_armory_menu(ctx: GameContext, planet_id: str = "") -> None:
    """Show the armory terminal split-screen modal."""
    from .. import pygame_split
    pygame_split.run_interactive(
        ctx,
        lambda: _pygame_armory_frame(ctx, planet_id),
        lambda action, focus, selected: _apply_pygame_armory_action(
            ctx, action, focus, selected,
        ),
        caption="spacehack - armory",
    )
    return
