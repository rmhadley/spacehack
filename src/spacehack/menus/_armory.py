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


def _pygame_armory_frame(ctx: GameContext):
    """Build a presentation-only armory split frame."""
    from .. import pygame_split
    from ..data.ground_weapons import list_ground_weapons
    from ..data.ground_armor import list_ground_armor
    _left = [pygame_split.SplitRow("--- WEAPONS ---", "", "", "", True)]
    _left.extend(
        pygame_split.SplitRow(
            spec.name,
            f"{spec.price}$",
            f"Damage: {spec.damage}  Accuracy: {spec.accuracy}%  Range: {spec.min_range}-{spec.max_range}",
            f"BUY_WEAPON:{spec.id}",
        )
        for spec in sorted(list_ground_weapons(), key=lambda item: item.price)
        if getattr(spec, "shop_available", True)
    )
    _left.append(pygame_split.SplitRow("--- ARMOUR ---", "", "", "", True))
    _left.extend(
        pygame_split.SplitRow(spec.name, f"{spec.price}$", spec.description, f"BUY_ARMOR:{spec.id}")
        for spec in sorted(list_ground_armor(), key=lambda item: item.price)
    )
    _right = [pygame_split.SplitRow("--- WEAPON SLOTS ---", "", "", "", True)]
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
                f"(sell {_sell_price(item_id)}$)",
                f"Damage: {spec.damage}  Accuracy: {spec.accuracy}%  Range: {spec.min_range}-{spec.max_range}",
                f"SELL_WEAPON:{index}",
            ))
        else:
            _right.append(pygame_split.SplitRow("[empty]", "", "", "", False))
    _right.append(pygame_split.SplitRow("--- ARMOUR SLOTS ---", "", "", "", True))
    for slot in _ARMOR_SLOTS:
        item_id = ctx.equipped_ground_armor.get(slot)
        if item_id:
            spec = find_ground_armor(item_id)
            _right.append(pygame_split.SplitRow(
                f"{_ARMOR_SLOT_LABELS[slot]}: {spec.name}",
                f"(sell {_sell_price(item_id)}$)", spec.description,
                f"SELL_ARMOR:{slot}",
            ))
        else:
            _right.append(pygame_split.SplitRow(f"{_ARMOR_SLOT_LABELS[slot]}: [empty]", "", "", "", False))
    return pygame_split.SplitFrame(
        "ARMORY", "For Sale", "My Loadout", tuple(_left), tuple(_right),
        f"Credits: {ctx.stats.credits}$", "",
        "UP/DOWN navigate  TAB switch panel  ENTER buy/sell  ESC back",
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
    if _pygame_split_enabled():
        from .. import pygame_split
        result = pygame_split.run_interactive(
            ctx,
            lambda: _pygame_armory_frame(ctx),
            lambda action, focus, selected: _apply_pygame_armory_action(
                ctx, action, focus, selected,
            ),
            caption="spacehack - armory",
        )
        if result is not None:
            return
    from ..data.ground_weapons import find_ground_weapon as _fgw, list_ground_weapons as _lgw
    from ..data.ground_armor import find_ground_armor as _fga, list_ground_armor as _lga

    _all_weapons = sorted(_lgw(), key=lambda w: w.price)
    _all_armor = sorted(_lga(), key=lambda a: a.price)

    # Left panel: items for sale.
    _left_items: list[tuple[str, str, str, tuple, str, str | None]] = []
    _left_items.append(("--- WEAPONS ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for w in _all_weapons:
        # Monster/enemy-only weapons (shop_available=False) never stock.
        if not getattr(w, 'shop_available', True):
            continue
        _left_items.append((w.name, f"{w.price:>4}$", "", ui.COLOR_OPTION, "weapon", w.id))
    _left_items.append(("--- ARMOUR ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for a in _all_armor:
        _left_items.append((a.name, f"{a.price:>4}$", "", ui.COLOR_OPTION, "armor", a.id))

    console = make_console()
    _focus: int = 0  # 0 = left, 1 = right
    _sel: int = 0

    def _first_selectable(items):
        for i, item in enumerate(items):
            if item[4] != "divider":
                return i
        return 0

    def _build_right() -> list[tuple[str, str, str, tuple, str, str | None]]:
        _items: list[tuple[str, str, str, tuple, str, str | None]] = []

        # Weapon slots (2).
        _items.append(("--- WEAPON SLOTS ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))
        _weapons = list(ctx.equipped_ground_weapons)
        while len(_weapons) < 2:
            _weapons.append("")
        for i, _wid in enumerate(_weapons):
            if _wid:
                try:
                    _s = _fgw(_wid)
                    _sell = _sell_price(_wid)
                    _items.append((_s.name, f"(sell {_sell}$)", "", ui.COLOR_OPTION, "weapon_slot", f"w{i}"))
                except KeyError:
                    _items.append(("[unknown]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", f"w{i}"))
            else:
                _items.append(("[empty]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", f"w{i}"))

        # Armour slots (5).
        _items.append(("--- ARMOUR SLOTS ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))
        for _slot in _ARMOR_SLOTS:
            _label = _ARMOR_SLOT_LABELS.get(_slot, _slot.title())
            _aid = ctx.equipped_ground_armor.get(_slot)
            if _aid:
                try:
                    _s = _fga(_aid)
                    _sell = _sell_price(_aid)
                    _items.append((f"{_label}: {_s.name}", f"(sell {_sell}$)", "", ui.COLOR_OPTION, "armor_slot", f"s{_slot}"))
                except KeyError:
                    _items.append((f"{_label}: [unknown]", "", "", ui.COLOR_VALUE_DIM, "armor_slot", f"s{_slot}"))
            else:
                _items.append((f"{_label}: [empty]", "", "", ui.COLOR_VALUE_DIM, "armor_slot", f"s{_slot}"))

        return _items

    _right_items = _build_right()
    _sel = _first_selectable(_left_items)

    def _render() -> None:
        nonlocal _sel
        _left_display = [(n, l, s, f) for n, l, s, f, _t, _i in _left_items]
        _right_display = [(n, l, s, f) for n, l, s, f, _t, _i in _right_items]
        render_split_frame(
            console,
            title="ARMORY",
            left_label=" For Sale" if _focus == 0 else "  For Sale",
            right_label="| My Loadout" if _focus == 1 else "  My Loadout",
            focus=_focus,
            sel=_sel,
            left_rows=_left_display,
            right_rows=_right_display,
            footer_left=f"Credits: {ctx.stats.credits}$",
            footer_right="",
            hint="UP/DOWN navigate  TAB switch panel  ENTER buy/sell  ESC back",
            log=ctx.log,
        )

        # Detail line for the currently selected item.
        _items = _left_items if _focus == 0 else _right_items
        if 0 <= _sel < len(_items):
            _name, _label, _suffix, _fg, _itype, _iid = _items[_sel]
            if _itype not in ("divider",):
                _detail = ""
                try:
                    if _itype == "weapon":
                        _ws = _fgw(_iid)
                        _detail = (
                            f"DMG: {_ws.damage}  |  ACC: {_ws.accuracy}%  |  "
                            f"Range: {_ws.min_range}-{_ws.max_range}  |  "
                            f"AP: {_ws.ap_cost}  |  Hands: {_ws.hands}"
                        )
                        if _ws.ammo_capacity > 0:
                            _detail += f"  |  Ammo: {_ws.ammo_capacity}"
                    elif _itype == "armor":
                        _as = _fga(_iid)
                        _detail = _as.description
                except KeyError:
                    pass
                if _detail:
                    _max_w = SCREEN_WIDTH - HUD_WIDTH - 2
                    _detail_y = SCREEN_HEIGHT - MSG_LOG_HEIGHT - 2
                    ui.paint_text(console, 2, _detail_y, _detail, fg=ui.COLOR_VALUE_DIM, max_x=2 + _max_w)

    def _update(event: tcod.event.Event) -> _ArmoryOutcome:
        nonlocal _focus, _sel, _right_items

        if _try_open_guide(event, ctx):
            return _ArmoryOutcome.IGNORE

        if isinstance(event, tcod.event.Quit):
            return _ArmoryOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _ArmoryOutcome.IGNORE

        sym = event.sym
        sym_name = getattr(sym, "name", "").lower()

        if sym in ui._ESCAPE_SYMS:
            return _ArmoryOutcome.BACK

        if sym_name == "tab":
            _focus = 1 - _focus
            _items = _left_items if _focus == 0 else _right_items
            _sel = _first_selectable(_items)
            return _ArmoryOutcome.IGNORE

        is_up = sym in ui._UP_SYMS or sym_name == "k"
        is_down = sym in ui._DOWN_SYMS or sym_name == "j"
        if is_up:
            _items = _left_items if _focus == 0 else _right_items
            if _items:
                _sel = (_sel - 1) % len(_items)
                while _items[_sel][4] == "divider":
                    _sel = (_sel - 1) % len(_items)
            return _ArmoryOutcome.IGNORE
        if is_down:
            _items = _left_items if _focus == 0 else _right_items
            if _items:
                _sel = (_sel + 1) % len(_items)
                while _items[_sel][4] == "divider":
                    _sel = (_sel + 1) % len(_items)
            return _ArmoryOutcome.IGNORE

        if sym in ui._ENTER_SYMS:
            if _focus == 0:
                # Buy + auto-equip (left panel).
                if 0 <= _sel < len(_left_items):
                    _name, _label, _suffix, _fg, _itype, _iid = _left_items[_sel]
                    if _itype == "divider" or _iid is None:
                        return _ArmoryOutcome.IGNORE

                    if _itype == "weapon":
                        try:
                            _ws = _fgw(_iid)
                        except KeyError:
                            return _ArmoryOutcome.IGNORE
                        if ctx.stats.credits < _ws.price:
                            ctx.log.add(f"Not enough credits to buy {_ws.name} ({_ws.price}$).")
                            return _ArmoryOutcome.IGNORE
                        # Find first empty weapon slot.
                        _weaps = list(ctx.equipped_ground_weapons)
                        while len(_weaps) < 2:
                            _weaps.append("")
                        _slot_found = False
                        for i in range(2):
                            if not _weaps[i]:
                                _weaps[i] = _iid
                                ctx.equipped_ground_weapons = [w for w in _weaps if w]
                                ctx.stats.credits -= _ws.price
                                ctx.log.add(f"Bought and equipped {_ws.name} (slot {i + 1}) for {_ws.price}$.")
                                _slot_found = True
                                break
                        if not _slot_found:
                            ctx.log.add("Both weapon slots are full. Sell one first.")
                            return _ArmoryOutcome.IGNORE

                    elif _itype == "armor":
                        try:
                            _as = _fga(_iid)
                        except KeyError:
                            return _ArmoryOutcome.IGNORE
                        if ctx.stats.credits < _as.price:
                            ctx.log.add(f"Not enough credits to buy {_as.name} ({_as.price}$).")
                            return _ArmoryOutcome.IGNORE
                        # Check if slot is free.
                        if _as.slot in ctx.equipped_ground_armor:
                            _sl = _ARMOR_SLOT_LABELS.get(_as.slot, _as.slot)
                            ctx.log.add(f"{_sl} slot is occupied. Sell current item first.")
                            return _ArmoryOutcome.IGNORE
                        ctx.equipped_ground_armor[_as.slot] = _iid
                        ctx.stats.credits -= _as.price
                        _sl = _ARMOR_SLOT_LABELS.get(_as.slot, _as.slot)
                        ctx.log.add(f"Bought and equipped {_as.name} ({_sl}) for {_as.price}$.")

                    _right_items = _build_right()

            else:
                # Sell equipped item (right panel).
                if 0 <= _sel < len(_right_items):
                    _name, _label, _suffix, _fg, _itype, _iid = _right_items[_sel]
                    if _itype in ("divider",):
                        return _ArmoryOutcome.IGNORE
                    if _iid is None:
                        return _ArmoryOutcome.IGNORE

                    if _itype == "weapon_slot":
                        _slot_idx = int(_iid[1])  # w0 or w1 -> 0 or 1
                        _weaps = list(ctx.equipped_ground_weapons)
                        while len(_weaps) < 2:
                            _weaps.append("")
                        _wid = _weaps[_slot_idx]
                        if not _wid:
                            ctx.log.add("That slot is empty.")
                            return _ArmoryOutcome.IGNORE
                        try:
                            _wname = _fgw(_wid).name
                        except KeyError:
                            _wname = _wid
                        _price = _sell_price(_wid)
                        _weaps[_slot_idx] = ""
                        ctx.equipped_ground_weapons = [w for w in _weaps if w]
                        ctx.stats.credits += _price
                        ctx.log.add(f"Sold {_wname} for {_price}$.")

                    elif _itype == "armor_slot":
                        _slot_name = _iid[1:]  # s{name} -> {name}
                        _aid = ctx.equipped_ground_armor.get(_slot_name)
                        if not _aid:
                            ctx.log.add("That slot is empty.")
                            return _ArmoryOutcome.IGNORE
                        try:
                            _aname = _fga(_aid).name
                        except KeyError:
                            _aname = _aid
                        _price = _sell_price(_aid)
                        del ctx.equipped_ground_armor[_slot_name]
                        ctx.stats.credits += _price
                        _sl = _ARMOR_SLOT_LABELS.get(_slot_name, _slot_name)
                        ctx.log.add(f"Sold {_aname} ({_sl}) for {_price}$.")

                    _right_items = _build_right()
                    _sel = min(_sel, len(_right_items) - 1)
            return _ArmoryOutcome.IGNORE

        return _ArmoryOutcome.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)
