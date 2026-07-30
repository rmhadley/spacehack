"""Loadout management split-screen modal for the mechanic terminal.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import ship as ship_module
from ..game_context import GameContext
from ..engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide
from ..ui import render_split_frame


class _LoadoutOutcome(Enum):
    """Result of the mechanic loadout menu."""
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


def _run_loadout_menu(ctx, planet_id: str = "") -> None:
    """Show the loadout management split-screen modal.

    Left panel: weapons for sale, divider, modules for sale.
    Right panel: installed weapon slots (or [empty]), divider,
    installed module slots (or [empty]).
    ENTER on left panel = buy + install.  ENTER on right panel
    = sell installed part for 50% back.

    ``planet_id`` determines which weapons/modules are for sale —
    empty string = use full catalog (fallback). Inventory is fixed
    per run (seeded by game seed + planet id) and does NOT refresh
    between visits — prevents save-scumming the RNG.
    """
    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship to manage its loadout.")
        return

    ship_spec = ship_module.find_ship(owned.ship_id)
    from ..data.weapons import find_weapon as _fw
    from ..data.modules import find_module as _fm
    from .. import ship as _sm

    # Resolve per-planet weapon/module inventory.
    # Uses the shared engine.RNG — inventory changes naturally each visit.
    if planet_id:
        from ..data.planets import resolve_mech_inventory as _rvi
        _wpn_ids, _mod_ids = _rvi(planet_id)
        _weapons_list = sorted(
            [_fw(wid) for wid in _wpn_ids], key=lambda w: w.price,
        )
        _modules_list = sorted(
            [_fm(mid) for mid in _mod_ids], key=lambda m: m.price,
        )
    else:
        from ..data.weapons import list_weapons as _lw
        from ..data.modules import list_modules as _lm
        _weapons_list = sorted(_lw(), key=lambda w: w.price)
        _modules_list = sorted(_lm(), key=lambda m: m.price)

    # Each left-panel item: (name, label, suffix, fg, item_type, item_id)
    _left_items: list[tuple[str, str, str, tuple, str, str | None]] = []
    _left_items.append(("─── WEAPONS ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for w in _weapons_list:
        _left_items.append((w.name, f"{w.price:>4}$", "", ui.COLOR_OPTION, "weapon", w.id))
    _left_items.append(("─── MODULES ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for m in _modules_list:
        _left_items.append((m.name, f"{m.price:>4}$", "", ui.COLOR_OPTION, "module", m.id))

    # Build right-panel items (My Ship slots).
    _right_items: list[tuple[str, str, str, tuple, str, str | None]] = []
    _right_items.append(("─── WEAPON SLOTS ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for slot_id, _idx in _sm._find_weapon_slots(owned, ship_spec):
        if slot_id is not None:
            try:
                _spec = _fw(slot_id)
                _sell = _sm._sell_price("weapon", slot_id)
                _right_items.append((_spec.name, f"(sell {_sell}$)", "", ui.COLOR_OPTION, "weapon_slot", slot_id))
            except KeyError:
                _right_items.append(("[unknown]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", None))
        else:
            _right_items.append(("[empty]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", None))
    _right_items.append(("─── MODULE SLOTS ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for slot_id, _idx in _sm._find_module_slots(owned, ship_spec):
        if slot_id is not None:
            try:
                _spec = _fm(slot_id)
                _sell = _sm._sell_price("module", slot_id)
                _right_items.append((_spec.name, f"(sell {_sell}$)", "", ui.COLOR_OPTION, "module_slot", slot_id))
            except KeyError:
                _right_items.append(("[unknown]", "", "", ui.COLOR_VALUE_DIM, "module_slot", None))
        else:
            _right_items.append(("[empty]", "", "", ui.COLOR_VALUE_DIM, "module_slot", None))

    # Build the display-only row lists for the split-frame renderer.
    def _build_display_rows(items):
        return [(n, l, s, f) for n, l, s, f, _t, _i in items]

    # Helper: rebuild the right panel from current owned state.
    def _rebuild_right() -> None:
        _right_items.clear()
        _right_items.append(("─── WEAPON SLOTS ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
        for _sid, _sidx in _sm._find_weapon_slots(owned, ship_spec):
            if _sid is not None:
                try:
                    _sp = _fw(_sid)
                    _sv = _sm._sell_price("weapon", _sid)
                    _right_items.append((_sp.name, f"(sell {_sv}$)", "", ui.COLOR_OPTION, "weapon_slot", _sid))
                except KeyError:
                    _right_items.append(("[unknown]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", None))
            else:
                _right_items.append(("[empty]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", None))
        _right_items.append(("─── MODULE SLOTS ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
        for _sid, _sidx in _sm._find_module_slots(owned, ship_spec):
            if _sid is not None:
                try:
                    _sp = _fm(_sid)
                    _sv = _sm._sell_price("module", _sid)
                    _right_items.append((_sp.name, f"(sell {_sv}$)", "", ui.COLOR_OPTION, "module_slot", _sid))
                except KeyError:
                    _right_items.append(("[unknown]", "", "", ui.COLOR_VALUE_DIM, "module_slot", None))
            else:
                _right_items.append(("[empty]", "", "", ui.COLOR_VALUE_DIM, "module_slot", None))

    # Initialize _sel to the first non-divider item on each panel.
    def _first_selectable(items):
        for i, item in enumerate(items):
            if item[4] != "divider":
                return i
        return 0

    console = make_console()
    _focus: int = 0  # 0 = left, 1 = right
    _sel: int = _first_selectable(_left_items)

    def _render() -> None:
        nonlocal _sel
        _left_display = _build_display_rows(_left_items)
        _right_display = _build_display_rows(_right_items)
        _wpn_label = f"Wpn: {len(owned.weapons)}/{ship_spec.weapon_slots}"
        _mod_label = f"Mod: {len(owned.modules)}/{ship_spec.module_slots}"
        render_split_frame(
            console,
            title="MECHANIC \u2014 SHIP LOADOUT",
            left_label=" For Sale" if _focus == 0 else "  For Sale",
            right_label="\u2502 My Ship" if _focus == 1 else "  My Ship",
            focus=_focus,
            sel=_sel,
            left_rows=_left_display,
            right_rows=_right_display,
            footer_left=f"Credits: {ctx.stats.credits}$",
            footer_right=f"{_wpn_label}  {_mod_label}",
            hint="UP/DOWN navigate  TAB switch panel  ENTER buy/sell  ESC back",
            log=ctx.log,
        )

        # Detail line for the currently selected item.
        _items = _left_items if _focus == 0 else _right_items
        if 0 <= _sel < len(_items):
            _name, _label, _suffix, _fg, _itype, _iid = _items[_sel]
            if _itype != "divider" and _iid is not None:
                _detail = ""
                try:
                    if _itype in ("weapon", "weapon_slot"):
                        _ws = _fw(_iid)
                        _detail = (
                            f"Damage: {_ws.damage}  |  Accuracy: {_ws.accuracy}%  |  "
                            f"Range: {_ws.min_range}-{_ws.max_range}  |  "
                            f"AP: {_ws.ap_cost}  |  Power: {_ws.power_cost}"
                        )
                        if _ws.slot_type == "missile":
                            _detail += f"  |  Ammo: {_ws.ammo_capacity} ({_ws.cargo_per_round} cr/rd)"
                    elif _itype in ("module", "module_slot"):
                        _ms = _fm(_iid)
                        _detail = _ms.description
                except KeyError:
                    pass
                if _detail:
                    _max_w = SCREEN_WIDTH - HUD_WIDTH - 2
                    _detail_y = SCREEN_HEIGHT - MSG_LOG_HEIGHT - 2
                    ui.paint_text(console, 2, _detail_y, _detail, fg=ui.COLOR_VALUE_DIM, max_x=2 + _max_w)

    def _update(event: tcod.event.Event) -> _LoadoutOutcome:
        nonlocal _focus, _sel

        if _try_open_guide(event, ctx):
            return _LoadoutOutcome.IGNORE

        if isinstance(event, tcod.event.Quit):
            return _LoadoutOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _LoadoutOutcome.IGNORE

        sym = event.sym
        sym_name = getattr(sym, "name", "").lower()

        if sym in ui._ESCAPE_SYMS:
            return _LoadoutOutcome.BACK

        # TAB = switch focus.
        if sym_name == "tab":
            _focus = 1 - _focus
            _items = _left_items if _focus == 0 else _right_items
            _sel = _first_selectable(_items)
            return _LoadoutOutcome.IGNORE

        # UP / DOWN navigation (skip dividers).
        is_up = sym in ui._UP_SYMS or sym_name == "k"
        is_down = sym in ui._DOWN_SYMS or sym_name == "j"
        if is_up:
            _items = _left_items if _focus == 0 else _right_items
            if _items:
                _sel = (_sel - 1) % len(_items)
                while _items[_sel][4] == "divider":
                    _sel = (_sel - 1) % len(_items)
            return _LoadoutOutcome.IGNORE
        if is_down:
            _items = _left_items if _focus == 0 else _right_items
            if _items:
                _sel = (_sel + 1) % len(_items)
                while _items[_sel][4] == "divider":
                    _sel = (_sel + 1) % len(_items)
            return _LoadoutOutcome.IGNORE

        # ENTER = buy (left) or sell (right).
        if sym in ui._ENTER_SYMS:
            if _focus == 0:
                # Buy + install.
                if 0 <= _sel < len(_left_items):
                    _name, _label, _suffix, _fg, _itype, _iid = _left_items[_sel]
                    if _itype == "divider":
                        return _LoadoutOutcome.IGNORE
                    if _itype == "weapon":
                        if len(owned.weapons) >= ship_spec.weapon_slots:
                            ctx.log.add("All weapon slots are full. Sell one first.")
                            return _LoadoutOutcome.IGNORE
                        try:
                            ws = _fw(_iid)
                        except KeyError:
                            return _LoadoutOutcome.IGNORE
                        if ctx.stats.credits < ws.price:
                            ctx.log.add(f"Not enough credits to buy {ws.name} ({ws.price}$).")
                            return _LoadoutOutcome.IGNORE
                        if _sm._install_weapon(owned, _iid, ship_spec):
                            ctx.stats.credits -= ws.price
                            ctx.log.add(f"Installed {ws.name} for {ws.price}$.")
                            _rebuild_right()
                    elif _itype == "module":
                        if len(owned.modules) >= ship_spec.module_slots:
                            ctx.log.add("All module slots are full. Sell one first.")
                            return _LoadoutOutcome.IGNORE
                        try:
                            ms = _fm(_iid)
                        except KeyError:
                            return _LoadoutOutcome.IGNORE
                        if ctx.stats.credits < ms.price:
                            ctx.log.add(f"Not enough credits to buy {ms.name} ({ms.price}$).")
                            return _LoadoutOutcome.IGNORE
                        if _sm._install_module(owned, _iid, ship_spec):
                            ctx.stats.credits -= ms.price
                            ctx.log.add(f"Installed {ms.name} for {ms.price}$.")
                            _rebuild_right()
            else:
                # Sell installed part.
                if 0 <= _sel < len(_right_items):
                    _name, _label, _suffix, _fg, _itype, _iid = _right_items[_sel]
                    if _itype == "divider":
                        return _LoadoutOutcome.IGNORE
                    if _iid is None:
                        ctx.log.add("That slot is empty.")
                        return _LoadoutOutcome.IGNORE
                    if _itype == "weapon_slot":
                        _wslots = _sm._find_weapon_slots(owned, ship_spec)
                        _slot_idx = next((si for wi, si in _wslots if wi == _iid), None)
                        if _slot_idx is not None:
                            _price = _sm._sell_price("weapon", _iid)
                            try:
                                _wname = _fw(_iid).name
                            except KeyError:
                                _wname = _iid
                            _sm._remove_weapon(owned, _slot_idx)
                            ctx.stats.credits += _price
                            ctx.log.add(f"Sold {_wname} for {_price}$.")
                            _rebuild_right()
                            _sel = min(_sel, len(_right_items) - 1)
                    elif _itype == "module_slot":
                        _mslots = _sm._find_module_slots(owned, ship_spec)
                        _slot_idx = next((si for mid, si in _mslots if mid == _iid), None)
                        if _slot_idx is not None:
                            _price = _sm._sell_price("module", _iid)
                            try:
                                _mname = _fm(_iid).name
                            except KeyError:
                                _mname = _iid
                            _sm._remove_module(owned, _slot_idx)
                            ctx.stats.credits += _price
                            ctx.log.add(f"Sold {_mname} for {_price}$.")
                            _rebuild_right()
                            _sel = min(_sel, len(_right_items) - 1)
            return _LoadoutOutcome.IGNORE

        return _LoadoutOutcome.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)
