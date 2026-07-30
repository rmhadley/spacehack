"""Armory terminal split-screen — buy and sell ground-combat gear.

Mirrors the mechanic loadout menu (``_loadout.py``) but for
:class:`spacehack.data.ground_weapons.GroundWeaponSpec` and
:class:`spacehack.data.ground_armor.GroundArmorSpec`. Left panel
lists ground gear for sale at this planet; right panel shows the
player's carried ground inventory with equip/unequip actions.
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


def _run_armory_menu(ctx: GameContext, planet_id: str = "") -> None:
    """Show the armory terminal split-screen modal.

    Left panel: ground weapons + armour for sale at this planet.
    Right panel: player's carried ground inventory with equip/unequip.
    ENTER on left = buy.  ENTER on right = equip/unequip selected item.
    """
    from ..data.ground_weapons import find_ground_weapon as _fgw, list_ground_weapons as _lgw
    from ..data.ground_armor import find_ground_armor as _fga, list_ground_armor as _lga
    from ..data.planets import find_planet_spec as _fps

    # Resolve per-planet ground gear inventory.
    _all_weapons = sorted(_lgw(), key=lambda w: w.price)
    _all_armor = sorted(_lga(), key=lambda a: a.price)

    # Build left panel items: weapons then armor.
    _left_items: list[tuple[str, str, str, tuple, str, str | None]] = []
    _left_items.append(("--- GROUND WEAPONS ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for w in _all_weapons:
        _left_items.append((w.name, f"{w.price:>4}$", "", ui.COLOR_OPTION, "weapon", w.id))
    _left_items.append(("--- GROUND ARMOR ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))
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

    # Build right panel from current ctx ground_inventory.
    def _build_right() -> list[tuple[str, str, str, tuple, str, str | None]]:
        _items: list[tuple[str, str, str, tuple, str, str | None]] = []
        _items.append(("--- YOUR GEAR ---", "", "", ui.COLOR_VALUE_DIM, "divider", None))

        inv = ctx.ground_inventory
        if not inv:
            _items.append(("(no ground gear)", "", "", ui.COLOR_VALUE_DIM, "empty", None))
        else:
            for gid in inv:
                _name = gid
                _gtype = "weapon"
                try:
                    _spec = _fgw(gid)
                    _name = _spec.name
                    _gtype = "weapon"
                except KeyError:
                    try:
                        _spec = _fga(gid)
                        _name = _spec.name
                        _gtype = "armor"
                    except KeyError:
                        pass

                # Show equipped status.
                _suffix = ""
                if gid == ctx.equipped_ground_weapon:
                    _suffix = "[EQUIPPED]"
                else:
                    # Check if this armor piece is in any slot.
                    for _slot, _aid in ctx.equipped_ground_armor.items():
                        if _aid == gid:
                            _suffix = f"[{_slot.upper()}]"
                            break

                _fg = ui.COLOR_OPTION if not _suffix else ui.COLOR_OPTION_HIGHLIGHT
                _items.append((_name, _suffix, "", _fg, _gtype, gid))
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
            right_label="| My Gear" if _focus == 1 else "  My Gear",
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
            if _itype not in ("divider", "empty") and _iid is not None:
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

        # UP / DOWN navigation (skip dividers).
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

        # ENTER = buy (left) or equip/unequip (right).
        if sym in ui._ENTER_SYMS:
            if _focus == 0:
                # Buy selected item.
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
            else:
                # Equip/unequip selected item.
                if 0 <= _sel < len(_right_items):
                    _name, _label, _suffix, _fg, _itype, _iid = _right_items[_sel]
                    if _itype in ("divider", "empty"):
                        return _ArmoryOutcome.IGNORE
                    if _iid is None:
                        return _ArmoryOutcome.IGNORE
                    if _itype == "weapon":
                        # Toggle equip: if already equipped, unequip. Otherwise equip.
                        if ctx.equipped_ground_weapon == _iid:
                            ctx.equipped_ground_weapon = None
                            ctx.log.add(f"Unequipped {_name}.")
                        else:
                            ctx.equipped_ground_weapon = _iid
                            ctx.log.add(f"Equipped {_name}.")
                    elif _itype == "armor":
                        try:
                            _as = _fga(_iid)
                        except KeyError:
                            return _ArmoryOutcome.IGNORE
                        _slot = _as.slot
                        # Toggle: if this piece is in its slot, unequip.
                        if ctx.equipped_ground_armor.get(_slot) == _iid:
                            del ctx.equipped_ground_armor[_slot]
                            ctx.log.add(f"Unequipped {_as.name}.")
                        else:
                            ctx.equipped_ground_armor[_slot] = _iid
                            ctx.log.add(f"Equipped {_as.name} ({_slot}).")
                    _right_items = _build_right()
            return _ArmoryOutcome.IGNORE

        return _ArmoryOutcome.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)
