"""Loadout management split-screen modal for the mechanic terminal.

The modal has three small, deliberately explicit views:

* ``STORE`` — buy catalog equipment and choose what to do with installed gear.
* ``STORAGE`` — install stored equipment and choose what to do with installed gear.

The view switch is intentionally local to this modal. The storage model and
slot mutation remain in :mod:`spacehack.ship`, so this presentation can evolve
without creating a second equipment system.
"""

from __future__ import annotations

from enum import Enum, auto

from .. import ship as ship_module


class _LoadoutOutcome(Enum):
    """Result of the mechanic loadout menu."""

    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


_LOADOUT_MODES: tuple[str, ...] = ("STORE", "STORAGE")
_MODE_LABELS = {
    "STORE": "STORE",
    "STORAGE": "STORAGE",
}
_MODE_NEXT = {
    "STORE": "STORAGE",
    "STORAGE": "STORE",
}


def _storage_list(ctx):
    """Return the player's storage list, creating a legacy default if needed."""
    storage = getattr(ctx, "ship_storage", None)
    if storage is None:
        storage = []
        ctx.ship_storage = storage
    return storage


def _loadout_hint(mode: str) -> str:
    """Return mode-specific controls for the loadout modal."""
    from .. import pygame_ui

    action_hint = {
        "STORE": "ENTER buy/choose",
        "STORAGE": "ENTER install/choose",
    }[mode]
    return pygame_ui.modal_hint(
        "UP/DOWN navigate", "TAB switch panel", action_hint,
        "ESC back", pygame_ui.GUIDE_HINT,
    )


def _mode_selector(mode: str):
    """Build the row that cycles to the next loadout view."""
    from .. import pygame_split

    next_mode = _MODE_NEXT[mode]
    return pygame_split.SplitRow(
        f"View: {_MODE_LABELS[mode]}",
        f"next: {_MODE_LABELS[next_mode]}",
        "Switch between buying equipment and installing stored equipment.",
        f"TOGGLE_VIEW:{next_mode}",
    )


def _weapon_detail(spec, *, ammo: int | None = None) -> str:
    """Format weapon details for a market, storage, or ship row."""
    detail = (
        f"Damage: {spec.damage}  Accuracy: {spec.accuracy}%  "
        f"Range: {spec.min_range}-{spec.max_range}"
    )
    if spec.slot_type == "missile":
        current = spec.ammo_capacity if ammo is None else max(0, min(ammo, spec.ammo_capacity))
        detail += f"  Ammo: {current}/{spec.ammo_capacity}"
    return detail


def _stored_row(stored, index: int, mode: str):
    """Build one stored-equipment row, preserving its actual list index."""
    from .. import pygame_split
    from .. import pygame_ui
    from ..data.modules import find_module
    from ..data.weapons import find_weapon

    if stored.item_type == "weapon":
        spec = find_weapon(stored.item_id)
        detail = _weapon_detail(spec, ammo=stored.ammo)
        value = "INSTALL"
    elif stored.item_type == "module":
        spec = find_module(stored.item_id)
        detail = spec.description
        value = "INSTALL"
    else:
        raise ValueError(f"Unknown stored equipment type: {stored.item_type!r}")
    return pygame_split.SplitRow(spec.name, value, detail, f"INSTALL_STORED:{index}")


def _storage_rows(ctx, mode: str):
    """Build storage rows for installation."""
    from .. import pygame_split

    rows = [_mode_selector(mode), pygame_split.section_header("OWNED EQUIPMENT")]
    valid_rows = []
    for index, stored in enumerate(_storage_list(ctx)):
        try:
            valid_rows.append(_stored_row(stored, index, mode))
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    if valid_rows:
        rows.extend(valid_rows)
    else:
        rows.append(
            pygame_split.SplitRow(
                "[empty]", "", "No equipment is currently held in storage.", "", False,
            )
        )
    return tuple(rows)


def _market_rows(weapon_ids, module_ids):
    """Build catalog rows for the current mechanic's parts inventory."""
    from .. import pygame_split
    from .. import pygame_ui
    from ..data.modules import find_module
    from ..data.weapons import find_weapon

    rows = [_mode_selector("STORE"), pygame_split.section_header("WEAPONS")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            _weapon_detail(spec),
            f"BUY_WEAPON:{spec.id}",
        )
        for spec in sorted((find_weapon(item_id) for item_id in weapon_ids), key=lambda item: item.price)
    )
    rows.append(pygame_split.section_header("MODULES"))
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            spec.description,
            f"BUY_MODULE:{spec.id}",
        )
        for spec in sorted((find_module(item_id) for item_id in module_ids), key=lambda item: item.price)
    )
    return tuple(rows)


def _ship_rows(ctx, ship_spec, mode: str):
    """Build active-ship rows whose Enter action opens Store/Sell choices."""
    from .. import pygame_split
    from .. import pygame_ui
    from ..data.modules import find_module
    from ..data.weapons import find_weapon

    rows = [pygame_split.section_header("WEAPON SLOTS")]
    for item_id, slot_index in ship_module._find_weapon_slots(ctx.player_owned_ship, ship_spec):
        if item_id is None:
            rows.append(pygame_split.SplitRow("[empty]", "", "", "", False))
            continue
        spec = find_weapon(item_id)
        action = f"MANAGE_WEAPON_SLOT:{slot_index}"
        value = ""
        rows.append(
            pygame_split.SplitRow(
                spec.name, value,
                _weapon_detail(spec, ammo=ctx.player_owned_ship.weapon_ammo.get(slot_index)),
                action,
            )
        )
    rows.append(pygame_split.section_header("MODULE SLOTS"))
    for item_id, slot_index in ship_module._find_module_slots(ctx.player_owned_ship, ship_spec):
        if item_id is None:
            rows.append(pygame_split.SplitRow("[empty]", "", "", "", False))
            continue
        spec = find_module(item_id)
        action = f"MANAGE_MODULE_SLOT:{slot_index}"
        value = ""
        rows.append(pygame_split.SplitRow(spec.name, value, spec.description, action))
    return tuple(rows)


def _pygame_loadout_frame(
    ctx,
    planet_id: str = "",
    weapon_ids: tuple[str, ...] | None = None,
    module_ids: tuple[str, ...] | None = None,
    mode: str = "STORE",
):
    """Build one presentation-only loadout frame for ``mode``."""
    from .. import pygame_split
    from .. import pygame_ui

    owned = ctx.player_owned_ship
    if owned is None:
        return pygame_split.SplitFrame(
            pygame_ui.terminal_title("MECHANIC", "SHIP LOADOUT"),
            "Store", "My Ship", (), (), "", "", pygame_split.SPLIT_SHOP_HINT,
        )
    if mode not in _LOADOUT_MODES:
        raise ValueError(f"Unknown loadout mode: {mode!r}")
    ship_spec = ship_module.find_ship(owned.ship_id)
    if mode == "STORE":
        if weapon_ids is None or module_ids is None:
            from ..data.modules import list_modules
            from ..data.weapons import list_weapons
            weapon_ids = tuple(item.id for item in list_weapons())
            module_ids = tuple(item.id for item in list_modules())
        left = _market_rows(weapon_ids, module_ids)
    else:
        left = _storage_rows(ctx, mode)
    right = _ship_rows(ctx, ship_spec, mode)
    right_label = "My Ship"
    return pygame_split.SplitFrame(
        pygame_ui.terminal_title("MECHANIC", "SHIP LOADOUT"),
        _MODE_LABELS[mode].title(), right_label,
        left, right,
        pygame_ui.credits_label(ctx.stats.credits),
        f"Wpn: {len(owned.weapons)}/{ship_spec.weapon_slots}  Mod: {len(owned.modules)}/{ship_spec.module_slots}",
        _loadout_hint(mode),
    )


def _log_storage_failure(ctx, stored, ship_spec) -> None:
    """Explain why a stored item could not be installed."""
    if stored.item_type == "weapon":
        available = len(ctx.player_owned_ship.weapons) < ship_spec.weapon_slots
        target = "weapon"
    elif stored.item_type == "module":
        available = len(ctx.player_owned_ship.modules) < ship_spec.module_slots
        target = "module"
    else:
        ctx.log.add("That stored item is not valid equipment.")
        return
    if not available:
        ctx.log.add(f"No compatible {target} slot is available on this ship.")
    else:
        ctx.log.add("That stored equipment is no longer available.")


def _apply_stored_install(ctx, action: str) -> None:
    """Install a selected stored entry or explain why it remains stored."""
    storage_index = int(action.split(":", 1)[1])
    owned = ctx.player_owned_ship
    ship_spec = ship_module.find_ship(owned.ship_id)
    storage = _storage_list(ctx)
    if not 0 <= storage_index < len(storage):
        ctx.log.add("That storage entry is no longer available.")
        return
    stored = storage[storage_index]
    if ship_module.install_stored_equipment(owned, storage, storage_index, ship_spec):
        ctx.log.add(f"Installed {stored.item_id.replace('_', ' ').title()} from storage.")
        return
    _log_storage_failure(ctx, stored, ship_spec)


def _choose_ship_action(ctx, action: str) -> str:
    """Ask whether an installed part should be stored or sold."""
    item_type, slot_text = action.split(":", 1)
    slot = int(slot_text)
    owned = ctx.player_owned_ship
    ship_spec = ship_module.find_ship(owned.ship_id)
    slots = (
        ship_module._find_weapon_slots(owned, ship_spec)
        if item_type == "MANAGE_WEAPON_SLOT"
        else ship_module._find_module_slots(owned, ship_spec)
    )
    if not 0 <= slot < len(slots) or slots[slot][0] is None:
        return "__BACK__"
    item_id = slots[slot][0]
    from ..data.modules import find_module
    from ..data.weapons import find_weapon
    spec = find_weapon(item_id) if item_type == "MANAGE_WEAPON_SLOT" else find_module(item_id)
    from .. import pygame_story
    sell_price = ship_module._sell_price(
        "weapon" if item_type == "MANAGE_WEAPON_SLOT" else "module",
        item_id,
    )
    return pygame_story.choose(
        ctx,
        title="MANAGE EQUIPMENT",
        body=spec.name,
        options=(
            ("Store", f"STORE_{'WEAPON' if item_type == 'MANAGE_WEAPON_SLOT' else 'MODULE'}_SLOT:{slot}"),
            (f"Sell for {sell_price}$", f"SELL_{'WEAPON' if item_type == 'MANAGE_WEAPON_SLOT' else 'MODULE'}_SLOT:{slot}"),
        ),
        caption="spacehack - manage equipment",
        compact=True,
    )


def _apply_manage_ship_item(ctx, action: str) -> None:
    """Open the Store/Sell chooser and apply its selected action."""
    chosen = _choose_ship_action(ctx, action)
    if chosen in {"__BACK__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("STORE_"):
        _apply_store(ctx, chosen)
    elif chosen.startswith("SELL_"):
        _apply_sell_installed(ctx, chosen)


def _apply_store(ctx, action: str) -> None:
    """Store one installed weapon or module."""
    item_type, slot_text = action.split(":", 1)
    slot = int(slot_text)
    owned = ctx.player_owned_ship
    store = ship_module.store_weapon if item_type == "STORE_WEAPON_SLOT" else ship_module.store_module
    if store(owned, _storage_list(ctx), slot):
        ctx.log.add("Moved equipment to storage.")
    else:
        ctx.log.add("That equipment could not be moved to storage.")


def _apply_sell_installed(ctx, action: str) -> None:
    """Sell one installed weapon or module."""
    item_type, slot_text = action.split(":", 1)
    slot = int(slot_text)
    owned = ctx.player_owned_ship
    slots = (
        ship_module._find_weapon_slots(owned, ship_module.find_ship(owned.ship_id))
        if item_type == "SELL_WEAPON_SLOT"
        else ship_module._find_module_slots(owned, ship_module.find_ship(owned.ship_id))
    )
    if not 0 <= slot < len(slots) or slots[slot][0] is None:
        return
    item_id = slots[slot][0]
    remove = ship_module._remove_weapon if item_type == "SELL_WEAPON_SLOT" else ship_module._remove_module
    remove(owned, slot)
    ctx.stats.credits += ship_module._sell_price("weapon" if item_type == "SELL_WEAPON_SLOT" else "module", item_id)


def _apply_buy_weapon(ctx, action: str) -> None:
    """Buy and install one weapon from the market."""
    item_id = action.split(":", 1)[1]
    owned = ctx.player_owned_ship
    ship_spec = ship_module.find_ship(owned.ship_id)
    from ..data.weapons import find_weapon
    spec = find_weapon(item_id)
    if len(owned.weapons) >= ship_spec.weapon_slots:
        ctx.log.add("No compatible weapon slot is available on this ship.")
    elif ctx.stats.credits < spec.price:
        ctx.log.add(f"You need {spec.price}$ to install {spec.name}.")
    elif ship_module._install_weapon(owned, item_id, ship_spec):
        ctx.stats.credits -= spec.price
        ctx.log.add(f"Installed {spec.name} for {spec.price}$.")


def _apply_buy_module(ctx, action: str) -> None:
    """Buy and install one module from the market."""
    item_id = action.split(":", 1)[1]
    owned = ctx.player_owned_ship
    ship_spec = ship_module.find_ship(owned.ship_id)
    from ..data.modules import find_module
    spec = find_module(item_id)
    if len(owned.modules) >= ship_spec.module_slots:
        ctx.log.add("No compatible module slot is available on this ship.")
    elif ctx.stats.credits < spec.price:
        ctx.log.add(f"You need {spec.price}$ to install {spec.name}.")
    elif ship_module._install_module(owned, item_id, ship_spec):
        ctx.stats.credits -= spec.price
        ctx.log.add(f"Installed {spec.name} for {spec.price}$.")


_LOADOUT_ACTION_HANDLERS = (
    ("BUY_WEAPON:", _apply_buy_weapon),
    ("BUY_MODULE:", _apply_buy_module),
    ("INSTALL_STORED:", _apply_stored_install),
    ("MANAGE_WEAPON_SLOT:", _apply_manage_ship_item),
    ("MANAGE_MODULE_SLOT:", _apply_manage_ship_item),
    ("STORE_WEAPON_SLOT:", _apply_store),
    ("STORE_MODULE_SLOT:", _apply_store),
    ("SELL_WEAPON_SLOT:", _apply_sell_installed),
    ("SELL_MODULE_SLOT:", _apply_sell_installed),
)


def _apply_pygame_loadout_action(ctx, action: str, focus: int, selected: int, planet_id: str) -> bool:
    """Apply one Pygame loadout action using table-driven routing."""
    if not action:
        return True
    handler = next(
        (handler for prefix, handler in _LOADOUT_ACTION_HANDLERS if action.startswith(prefix)),
        None,
    )
    if handler is None:
        raise ValueError(f"Unknown loadout action: {action!r}")
    handler(ctx, action)
    return True


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
    mode = "STORE"

    def build_frame():
        return _pygame_loadout_frame(
            ctx,
            planet_id,
            tuple(item.id for item in weapons),
            tuple(item.id for item in modules),
            mode,
        )

    def apply_action(action, focus, selected):
        nonlocal mode
        if action.startswith("TOGGLE_VIEW:"):
            requested = action.split(":", 1)[1]
            if requested in _LOADOUT_MODES:
                mode = requested
            return True
        return _apply_pygame_loadout_action(ctx, action, focus, selected, planet_id)

    pygame_split.run_interactive(
        ctx,
        build_frame,
        apply_action,
        caption="spacehack - ship loadout",
    )
