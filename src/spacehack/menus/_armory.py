"""Armory terminal split-screen — buy and sell ground-combat gear.

Mirrors the mechanic loadout menu (``_loadout.py``) but for
:class:`spacehack.data.ground_weapons.GroundWeaponSpec` and
:class:`spacehack.data.ground_armor.GroundArmorSpec`. Left panel
lists ground gear for sale; right panel shows weapon and armour
slots with equip/unequip actions, plus unequipped inventory.
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


class _ArmoryOutcome(Enum):
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


# Ordered armour slots for display.
_ARMOR_SLOTS: tuple[str, ...] = ("head", "body", "hands", "legs", "feet")
_ARMOR_SLOT_LABELS: dict[str, str] = {
    "head": "Head",
    "body": "Body",
    "hands": "Hands",
    "legs": "Legs",
    "feet": "Feet",
}


def _run_armory_menu(ctx: GameContext, planet_id: str = "") -> None:
    """Show the armory terminal split-screen modal.

    Left panel: ground weapons + armour for sale.
    Right panel: weapon slots (2), armour slots (5), then unequipped inventory.
    ENTER on left = buy.  ENTER on right slot = equip/unequip.
    """
    from ..data.ground_weapons import find_ground_weapon as _fgw, list_ground_weapons as _lgw
    from ..data.ground_armor import find_ground_armor as _fga, list_ground_armor as _lga

    _all_weapons = sorted(_lgw(), key=lambda w: w.price)
    _all_armor = sorted(_lga(), key=lambda a: a.price)

    # Build left panel items: weapons then armour.
    _left_items: list[tuple[str, str, str, tuple, str, str | None]] = []
    _left_items.append(("--- WEAPONS ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for w in _all_weapons:
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

        # Weapon slots.
        _items.append(("--- WEAPON SLOTS ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))
        _weapons = list(ctx.equipped_ground_weapons)
        # Pad to 2 slots.
        while len(_weapons) < 2:
            _weapons.append("")
        for i, _wid in enumerate(_weapons):
            if _wid:
                try:
                    _s = _fgw(_wid)
                    _label = _s.name
                except KeyError:
                    _label = _wid
                _items.append((_label, "[EQUIPPED]", "", ui.COLOR_OPTION_HIGHLIGHT, "weapon_slot", f"w{i}"))
            else:
                _items.append(("[empty slot]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", f"w{i}"))

        # Armour slots.
        _items.append(("--- ARMOUR SLOTS ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))
        for _slot in _ARMOR_SLOTS:
            _label = _ARMOR_SLOT_LABELS.get(_slot, _slot.title())
            _aid = ctx.equipped_ground_armor.get(_slot)
            if _aid:
                try:
                    _s = _fga(_aid)
                    _name = _s.name
                except KeyError:
                    _name = _aid
                _items.append((f"{_label}: {_name}", "[EQUIPPED]", "", ui.COLOR_OPTION_HIGHLIGHT, "armor_slot", f"s{_slot}"))
            else:
                _items.append((f"{_label}: [empty]", "", "", ui.COLOR_VALUE_DIM, "armor_slot", f"s{_slot}"))

        # Unequipped inventory.
        _items.append(("--- CARRIED ITEMS ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))
        _equipped_ids: set[str] = set()
        for _wid in ctx.equipped_ground_weapons:
            if _wid:
                _equipped_ids.add(_wid)
        for _aid in ctx.equipped_ground_armor.values():
            if _aid:
                _equipped_ids.add(_aid)
        _carried = [gid for gid in ctx.ground_inventory if gid not in _equipped_ids]
        if not _carried:
            _items.append(("(no unequipped items)", "", "", ui.COLOR_VALUE_DIM, "empty", None))
        else:
            for gid in _carried:
                _gtype = "weapon"
                try:
                    _s = _fgw(gid)
                    _name = _s.name
                except KeyError:
                    try:
                        _s = _fga(gid)
                        _name = _s.name
                        _gtype = "armor"
                    except KeyError:
                        _name = gid
                _items.append((_name, "", "", ui.COLOR_OPTION, _gtype, gid))
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
            footer_right=f"Carrying: {len(ctx.ground_inventory)}",
            hint="UP/DOWN navigate  TAB switch panel  ENTER buy/equip  ESC back",
        )

        # Detail line for the currently selected item.
        _items = _left_items if _focus == 0 else _right_items
        if 0 <= _sel < len(_items):
            _name, _label, _suffix, _fg, _itype, _iid = _items[_sel]
            if _itype not in ("divider", "empty"):
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
                    _detail_y = SCREEN_HEIGHT - MSG_LOG_HEIGHT + 1
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

        # TAB = switch focus.
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
                # Buy selected item (left panel).
                if 0 <= _sel < len(_left_items):
                    _name, _label, _suffix, _fg, _itype, _iid = _left_items[_sel]
                    if _itype == "divider":
                        return _ArmoryOutcome.IGNORE
                    if _iid is None:
                        return _ArmoryOutcome.IGNORE
                    if _itype == "weapon":
                        try:
                            _ws = _fgw(_iid)
                        except KeyError:
                            return _ArmoryOutcome.IGNORE
                        if ctx.stats.credits < _ws.price:
                            ctx.log.add(f"Not enough credits to buy {_ws.name} ({_ws.price}$).")
                            return _ArmoryOutcome.IGNORE
                        ctx.stats.credits -= _ws.price
                        ctx.ground_inventory.append(_iid)
                        ctx.log.add(f"Bought {_ws.name} for {_ws.price}$.")
                        _right_items = _build_right()
                        _sel = min(_sel, len(_right_items) - 1)
                    elif _itype == "armor":
                        try:
                            _as = _fga(_iid)
                        except KeyError:
                            return _ArmoryOutcome.IGNORE
                        if ctx.stats.credits < _as.price:
                            ctx.log.add(f"Not enough credits to buy {_as.name} ({_as.price}$).")
                            return _ArmoryOutcome.IGNORE
                        ctx.stats.credits -= _as.price
                        ctx.ground_inventory.append(_iid)
                        ctx.log.add(f"Bought {_as.name} for {_as.price}$.")
                        _right_items = _build_right()
                        _sel = min(_sel, len(_right_items) - 1)
            else:
                # Equip/unequip from right panel.
                if 0 <= _sel < len(_right_items):
                    _name, _label, _suffix, _fg, _itype, _iid = _right_items[_sel]
                    if _itype in ("divider", "empty"):
                        return _ArmoryOutcome.IGNORE
                    if _iid is None:
                        return _ArmoryOutcome.IGNORE

                    # Weapon slot: toggle equip for slot w0/w1.
                    if _itype == "weapon_slot":
                        _slot_idx = int(_iid[1])  # w0 or w1 -> 0 or 1
                        _current = list(ctx.equipped_ground_weapons)
                        # Pad to 2 slots.
                        while len(_current) < 2:
                            _current.append("")
                        if _current[_slot_idx]:
                            # Unequip: return weapon to inventory.
                            _wid = _current[_slot_idx]
                            if _wid not in ctx.ground_inventory:
                                ctx.ground_inventory.append(_wid)
                            _current[_slot_idx] = ""
                            ctx.log.add(f"Unequipped weapon slot {_slot_idx + 1}.")
                        else:
                            # Equip from carried items — prompt will be handled
                            # by a sub-menu. For now, just unequip support.
                            ctx.log.add("Buy a weapon first, then equip from Carried Items.")
                        ctx.equipped_ground_weapons = [w for w in _current if w]
                        _right_items = _build_right()
                        _sel = min(_sel, len(_right_items) - 1)

                    # Armour slot: toggle equip for slot s{name}.
                    elif _itype == "armor_slot":
                        _slot_name = _iid[1:]  # s{name} -> {name}
                        _current = ctx.equipped_ground_armor.get(_slot_name)
                        if _current:
                            # Unequip: return armour to inventory.
                            _aid = _current
                            if _aid not in ctx.ground_inventory:
                                ctx.ground_inventory.append(_aid)
                            del ctx.equipped_ground_armor[_slot_name]
                            _label = _ARMOR_SLOT_LABELS.get(_slot_name, _slot_name)
                            ctx.log.add(f"Unequipped {_label}.")
                        else:
                            ctx.log.add("Buy armour first, then equip from Carried Items.")
                        _right_items = _build_right()
                        _sel = min(_sel, len(_right_items) - 1)

                    # Carried item: equip into the first compatible empty slot.
                    elif _itype in ("weapon", "armor"):
                        # Find a compatible empty slot.
                        _equipped = False
                        if _itype == "weapon":
                            _weaps = list(ctx.equipped_ground_weapons)
                            while len(_weaps) < 2:
                                _weaps.append("")
                            for i in range(2):
                                if not _weaps[i]:
                                    _weaps[i] = _iid
                                    ctx.equipped_ground_weapons = [w for w in _weaps if w]
                                    ctx.log.add(f"Equipped to weapon slot {i + 1}.")
                                    _equipped = True
                                    break
                            if not _equipped:
                                ctx.log.add("Both weapon slots are full. Unequip one first.")
                        elif _itype == "armor":
                            try:
                                _as = _fga(_iid)
                            except KeyError:
                                return _ArmoryOutcome.IGNORE
                            _slot = _as.slot
                            if _slot not in ctx.equipped_ground_armor:
                                ctx.equipped_ground_armor[_slot] = _iid
                                _label = _ARMOR_SLOT_LABELS.get(_slot, _slot)
                                ctx.log.add(f"Equipped {_as.name} ({_label}).")
                                _equipped = True
                            else:
                                _label = _ARMOR_SLOT_LABELS.get(_slot, _slot)
                                ctx.log.add(f"{_label} slot is full. Unequip the current item first.")
                        if _equipped:
                            _right_items = _build_right()
                            _sel = min(_sel, len(_right_items) - 1)
            return _ArmoryOutcome.IGNORE

        return _ArmoryOutcome.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)
