"""Armory terminal split-screen for ground equipment ownership.

Phase 2 exposes three left-panel views:

* ``BUY`` — catalog items available at the current armory.
* ``ARMORY`` — the unlimited global warehouse.
* ``EXPEDITION`` — the limited reserve pack prepared for dungeon runs.

The active loadout remains on the right. This module owns presentation and
choice routing only; equipment mutation lives in :mod:`spacehack.ground_equipment`.
"""

from __future__ import annotations

from .. import ground_equipment
from ..game_context import GameContext


_ARMOR_SLOTS: tuple[str, ...] = ("head", "body", "hands", "legs", "feet")
_ARMOR_SLOT_LABELS: dict[str, str] = {
    "head": "Head", "body": "Body", "hands": "Hands",
    "legs": "Legs", "feet": "Feet",
}
_ARMORY_MODES: tuple[str, ...] = ("BUY", "ARMORY", "EXPEDITION")
_MODE_TABS: tuple[str, ...] = ("[B]uy", "[A]rmory")


def _armory_storage(ctx: GameContext) -> list[ground_equipment.StoredGroundEquipment]:
    """Return the unlimited armory warehouse."""
    storage = getattr(ctx, "ground_armory_storage", None)
    if storage is None:
        storage = []
        ctx.ground_armory_storage = storage
    return storage


def _expedition_storage(ctx: GameContext) -> list[ground_equipment.StoredGroundEquipment]:
    """Return the limited expedition pack."""
    storage = getattr(ctx, "ground_expedition_inventory", None)
    if storage is None:
        storage = []
        ctx.ground_expedition_inventory = storage
    return storage


def _armory_items(ctx: GameContext) -> list[ground_equipment.GroundItemStack]:
    """Return unlimited Armory Storage field-item stacks."""
    items = getattr(ctx, "ground_armory_items", None)
    if items is None:
        items = []
        ctx.ground_armory_items = items
    return items


def _expedition_items(ctx: GameContext) -> list[ground_equipment.GroundItemStack]:
    """Return Expedition Pack field-item stacks."""
    items = getattr(ctx, "ground_expedition_items", None)
    if items is None:
        items = []
        ctx.ground_expedition_items = items
    return items


def _strength(ctx: GameContext) -> int:
    """Return Strength with the base-10 legacy-context fallback."""
    return int(getattr(getattr(ctx, "ground_stats", None), "strength", 10))


def _sell_price(item_id: str) -> int:
    """Return half the catalog price for one ground item."""
    from ..data.ground_armor import find_ground_armor
    from ..data.ground_weapons import find_ground_weapon

    try:
        return find_ground_weapon(item_id).price // 2
    except KeyError:
        return find_ground_armor(item_id).price // 2


def _weapon_detail(spec) -> str:
    """Format a ground weapon's useful armory details."""
    hands = "2H" if spec.hands == 2 else "1H"
    bypass = "  Armor bypass" if spec.armor_bypass else ""
    return (
        f"{hands}  {spec.damage_type.title()}  Damage: {spec.damage}  "
        f"Accuracy: {spec.accuracy}%  Range: {spec.min_range}-{spec.max_range}"
        f"{bypass}"
    )


def _armor_effects(spec) -> str:
    """Format one armor piece's cybernetic bonuses, or an empty string."""
    bonuses = []
    if spec.ap_bonus:
        bonuses.append(f"+{spec.ap_bonus} AP")
    if spec.hit_bonus:
        bonuses.append(f"+{spec.hit_bonus}% Hit")
    if spec.melee_bonus:
        bonuses.append(f"+{spec.melee_bonus} Melee")
    if spec.hp_bonus:
        bonuses.append(f"+{spec.hp_bonus} HP")
    return f"  {' '.join(bonuses)}" if bonuses else ""


def _armor_detail(spec) -> str:
    """Format one armor piece's slot, defense, and cybernetic effects."""
    return (
        f"{spec.slot.title()}  Defense: {spec.defense}"
        f"{_armor_effects(spec)}  {spec.description}"
    )


def _equipment_name(entry: ground_equipment.StoredGroundEquipment) -> str:
    """Resolve one stored item's display name."""
    if entry.item_type == "weapon":
        from ..data.ground_weapons import find_ground_weapon
        return find_ground_weapon(entry.item_id).name
    from ..data.ground_armor import find_ground_armor
    return find_ground_armor(entry.item_id).name


def _equipment_detail(entry: ground_equipment.StoredGroundEquipment) -> str:
    """Resolve one stored item's display details."""
    if entry.item_type == "weapon":
        from ..data.ground_weapons import find_ground_weapon
        return _weapon_detail(find_ground_weapon(entry.item_id))
    from ..data.ground_armor import find_ground_armor
    spec = find_ground_armor(entry.item_id)
    return _armor_detail(spec)


def _catalog_items(planet_id: str, month: int):
    """Resolve the buyable ``(weapons, armor)`` for ``planet_id``.

    With a known planet the armory's month-keyed resolved stock is used;
a blank id falls back to the full shop-available catalog.
    """
    from ..data.ground_armor import find_ground_armor, list_ground_armor
    from ..data.ground_weapons import find_ground_weapon, list_ground_weapons

    if planet_id:
        from ..data.planets import resolve_armory_inventory
        weapon_ids, armor_ids = resolve_armory_inventory(planet_id, month)
        return (
            [find_ground_weapon(_w) for _w in weapon_ids],
            [find_ground_armor(_a) for _a in armor_ids],
        )
    weapons = [
        w for w in list_ground_weapons()
        if getattr(w, "shop_available", True)
    ]
    return weapons, list_ground_armor()


def _buy_rows(weapons, armor):
    """Build catalog rows for the Buy view from resolved stock lists."""
    from .. import pygame_split, pygame_ui

    rows = [pygame_split.section_header("WEAPONS")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            _weapon_detail(spec),
            f"BUY_WEAPON:{spec.id}",
        )
        for spec in sorted(weapons, key=lambda item: item.price)
    )
    rows.append(pygame_split.section_header("ARMOUR"))
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            _armor_detail(spec),
            f"BUY_ARMOR:{spec.id}",
        )
        for spec in sorted(armor, key=lambda item: item.price)
    )
    return tuple(rows)


def _buy_ammo_rows():
    """Build buy rows for the ground ammo catalog."""
    from .. import pygame_split, pygame_ui
    from ..data.ground_items import list_ground_ammo

    rows = [pygame_split.section_header("AMMUNITION")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price_per_round),
            f"Ammo stack 0/{spec.rounds_per_stack}  {spec.price_per_round}$/round",
            f"BUY_AMMO:{spec.id}",
        )
        for spec in sorted(list_ground_ammo(), key=lambda item: item.price_per_round)
    )
    return tuple(rows)


def _buy_consumable_rows():
    """Build buy rows for the ground consumable catalog."""
    from .. import pygame_split, pygame_ui
    from ..data.ground_items import list_ground_consumables

    rows = [pygame_split.section_header("CONSUMABLES")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            f"Stack 0/{spec.quantity_per_stack}  {spec.effect_id}",
            f"BUY_CONSUMABLE:{spec.id}",
        )
        for spec in sorted(list_ground_consumables(), key=lambda item: item.price)
    )
    return tuple(rows)


def _storage_rows(
    entries: list[ground_equipment.StoredGroundEquipment],
    action_prefix: str,
    section_label: str = "OWNED EQUIPMENT",
):
    """Build rows for one owned equipment container."""
    from .. import pygame_split, pygame_ui

    rows = [pygame_split.section_header(section_label)]
    for index, entry in enumerate(entries):
        try:
            rows.append(
                pygame_split.SplitRow(
                    _equipment_name(entry),
                    pygame_ui.sell_cell(_sell_price(entry.item_id)),
                    _equipment_detail(entry),
                    f"{action_prefix}:{index}",
                )
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    if len(rows) == 1:
        empty_detail = {
            "OWNED EQUIPMENT": "Armory Storage is unlimited and shared between terminals.",
            "BACKPACK ITEMS": "Your Expedition Pack has no reserve items.",
        }.get(section_label, "No stored ground equipment.")
        rows.append(pygame_split.SplitRow("[empty]", "", empty_detail, "", False))
    return tuple(rows)


def _field_item_name(stack: ground_equipment.GroundItemStack) -> str:
    """Resolve one ammo/consumable stack's display name."""
    from ..data.ground_items import find_ground_item

    return find_ground_item(stack.item_type, stack.item_id).name


def _field_item_detail(stack: ground_equipment.GroundItemStack) -> str:
    """Format quantity and purchase details for one field-item stack."""
    from ..data.ground_items import find_ground_item

    spec = find_ground_item(stack.item_type, stack.item_id)
    maximum = (
        spec.rounds_per_stack
        if stack.item_type == "ammo"
        else spec.quantity_per_stack
    )
    price = (
        f"{spec.price_per_round}$/round"
        if stack.item_type == "ammo"
        else f"{spec.price}$ each"
    )
    return f"{stack.item_type.title()}  {stack.quantity}/{maximum}  {price}"


def _field_item_rows(
    entries: list[ground_equipment.GroundItemStack],
    action_prefix: str,
    section_label: str,
):
    """Build rows for owned ammo/consumable stacks."""
    from .. import pygame_split

    rows = [pygame_split.section_header(section_label)]
    for index, stack in enumerate(entries):
        try:
            rows.append(pygame_split.SplitRow(
                _field_item_name(stack),
                "",
                _field_item_detail(stack),
                f"{action_prefix}:{index}",
            ))
        except (KeyError, TypeError, ValueError):
            continue
    if len(rows) == 1:
        rows.append(pygame_split.SplitRow(
            "[empty]", "", "No field-item stacks.", "", False,
        ))
    return tuple(rows)


def _weapon_slot_rows(ctx: GameContext):
    """Build the weapon-slot rows for the active ground loadout."""
    from .. import pygame_split, pygame_ui
    from ..data.ground_weapons import find_ground_weapon

    rows = [pygame_split.section_header("WEAPON SLOTS")]
    weapons = [instance.weapon_id for instance in ctx.equipped_ground_weapons]
    for index in range(max(2, len(weapons))):
        try:
            two_handed = bool(weapons) and ground_equipment.weapon_hands(weapons[0]) == 2
        except KeyError:
            two_handed = False
        if index == 1 and two_handed:
            rows.append(pygame_split.SplitRow(
                "Weapon 2: --- (occupied by 2H)", "", "", "", False, False,
            ))
            continue
        if index >= len(weapons):
            rows.append(pygame_split.SplitRow(f"Weapon {index + 1}: [empty]", "", "", "", False))
            continue
        try:
            spec = find_ground_weapon(weapons[index])
        except KeyError:
            rows.append(pygame_split.SplitRow(
                f"Weapon {index + 1}: [unavailable]", "", "", "", False, False,
            ))
            continue
        rows.append(pygame_split.SplitRow(
            f"Weapon {index + 1}: {spec.name}",
            pygame_ui.sell_cell(_sell_price(spec.id)),
            _weapon_detail(spec),
            f"MANAGE_WEAPON:{index}",
        ))
    return rows


def _armor_slot_rows(ctx: GameContext):
    """Build the armor-slot rows for the active ground loadout."""
    from .. import pygame_split, pygame_ui
    from ..data.ground_armor import find_ground_armor

    rows = [pygame_split.section_header("ARMOUR SLOTS")]
    for slot in _ARMOR_SLOTS:
        item_id = ctx.equipped_ground_armor.get(slot)
        if not item_id:
            rows.append(pygame_split.SplitRow(f"{_ARMOR_SLOT_LABELS[slot]}: [empty]", "", "", "", False))
            continue
        spec = find_ground_armor(item_id)
        rows.append(pygame_split.SplitRow(
            f"{_ARMOR_SLOT_LABELS[slot]}: {spec.name}",
            pygame_ui.sell_cell(_sell_price(item_id)),
            f"Defense: {spec.defense}{_armor_effects(spec)}  {spec.description}",
            f"MANAGE_ARMOR:{slot}",
        ))
    return rows


def _loadout_rows(ctx: GameContext):
    """Build selectable rows for the active ground loadout."""
    return tuple(_weapon_slot_rows(ctx) + _armor_slot_rows(ctx))


def _resolve_catalog(ctx: GameContext, planet_id: str, catalog):
    """Return the buy catalog, resolving from the month clock when absent."""
    if catalog is not None:
        return catalog
    from ..time import month_index
    return _catalog_items(planet_id, month_index(ctx))


def _armory_left_panel(ctx, planet_id: str, mode: str, catalog):
    """Return the active armory panel label and rows."""
    if mode not in _ARMORY_MODES:
        raise ValueError(f"Unknown armory mode: {mode!r}")
    if mode == "BUY":
        weapons, armor = _resolve_catalog(ctx, planet_id, catalog)
        return "Buy", (
            _buy_rows(weapons, armor)
            + _buy_ammo_rows()
            + _buy_consumable_rows()
        )
    if mode == "ARMORY":
        return "Armory Storage", (
            _storage_rows(_armory_storage(ctx), "MANAGE_ARMORY")
            + _field_item_rows(_armory_items(ctx), "MANAGE_ARMORY_ITEM", "FIELD ITEMS")
        )
    return "Expedition Pack", (
        _storage_rows(
            _expedition_storage(ctx), "MANAGE_EXPEDITION", "BACKPACK ITEMS",
        )
        + _field_item_rows(_expedition_items(ctx), "MANAGE_EXPEDITION_ITEM", "FIELD ITEMS")
    )


def _pygame_armory_frame(ctx: GameContext, planet_id: str = "", mode: str = "BUY", catalog=None):
    """Build one armory frame for Buy, Armory, or Expedition mode."""
    from .. import pygame_split, pygame_ui

    left_label, left_rows = _armory_left_panel(ctx, planet_id, mode, catalog)
    capacity = ground_equipment.expedition_capacity(_strength(ctx))
    pack_count = len(_expedition_storage(ctx)) + len(_expedition_items(ctx))
    left_tabs = (*_MODE_TABS, f"[E]xpedition ({pack_count}/{capacity})")
    return pygame_split.SplitFrame(
        pygame_ui.terminal_title("ARMORY", planet_id), left_label, "My Loadout",
        left_rows, _loadout_rows(ctx), pygame_ui.credits_label(ctx.stats.credits),
        f"Pack: {len(_expedition_storage(ctx))}/{capacity}  Armory: unlimited",
        pygame_ui.modal_hint(
            "UP/DOWN navigate", "TAB switch panel", "ENTER equip/manage",
            "B buy", "A armory", "E expedition", "ESC back", pygame_ui.GUIDE_HINT,
        ),
        left_tabs=left_tabs, active_left_tab=_ARMORY_MODES.index(mode),
        left_tab_modes=_ARMORY_MODES,
    )


def _choose_destination(ctx, item_type: str, item_id: str) -> str:
    """Ask where a ground-equipment purchase should go."""
    from .. import pygame_story
    from ..data.ground_armor import find_ground_armor
    from ..data.ground_weapons import find_ground_weapon

    spec = find_ground_weapon(item_id) if item_type == "weapon" else find_ground_armor(item_id)
    return pygame_story.choose(
        ctx,
        title="BUY GROUND EQUIPMENT",
        body=spec.name,
        options=(
            ("Equip", f"BUY_INSTALL:{item_type}:{item_id}"),
            ("Armory Storage", f"BUY_ARMORY:{item_type}:{item_id}"),
            ("Expedition Pack", f"BUY_EXPEDITION:{item_type}:{item_id}"),
        ),
        caption="spacehack - armory purchase",
        compact=True,
    )


def _choose_field_item_destination(ctx, item_type: str, item_id: str) -> str:
    """Choose a destination before paying for a field item."""
    from .. import pygame_story
    from ..data.ground_items import find_ground_item

    spec = find_ground_item(item_type, item_id)
    price = (
        spec.price_per_round if item_type == "ammo" else spec.price
    )
    title = "BUY AMMUNITION" if item_type == "ammo" else "BUY CONSUMABLE"
    unit = "$/round" if item_type == "ammo" else "$ each"
    return pygame_story.choose(
        ctx, title=title, body=f"{spec.name} - {price}{unit}",
        options=(
            ("Armory Storage", f"BUY_ITEM_ARMORY:{item_type}:{item_id}"),
            ("Expedition Pack", f"BUY_ITEM_EXPEDITION:{item_type}:{item_id}"),
        ),
        caption="spacehack - field-item purchase", compact=True,
    )


def _field_item_purchase_maximum(
    ctx, item_type: str, item_id: str, destination: str,
) -> int:
    """Return affordable and destination-capacity-limited quantity."""
    from ..data.ground_items import find_ground_item

    spec = find_ground_item(item_type, item_id)
    price = spec.price_per_round if item_type == "ammo" else spec.price
    affordable = ctx.stats.credits // price
    if destination == ground_equipment.EXPEDITION_INVENTORY:
        capacity = ground_equipment.field_item_capacity(
            _expedition_storage(ctx), _expedition_items(ctx),
            item_type, item_id,
            strength=_strength(ctx), container=destination,
        )
        return min(affordable, capacity or 0)
    return affordable


def _choose_field_item_quantity(
    ctx, item_type: str, item_id: str, destination: str,
) -> int | None:
    """Choose a field-item quantity after destination selection."""
    from .. import pygame_quantity
    from ..data.ground_items import find_ground_item

    spec = find_ground_item(item_type, item_id)
    maximum = _field_item_purchase_maximum(
        ctx, item_type, item_id, destination,
    )
    if maximum < 1:
        ctx.log.add("That destination cannot hold any more field items.")
        return None
    price = spec.price_per_round if item_type == "ammo" else spec.price
    return pygame_quantity.run_for_context(
        ctx.context, ctx, f"BUY {spec.name}", maximum, price,
    )


def _purchase_field_item(
    ctx, item_id: str, destination: str, item_type: str = "ammo",
) -> None:
    """Buy an exact field-item quantity after destination validation."""
    from ..data.ground_items import find_ground_item

    spec = find_ground_item(item_type, item_id)
    quantity = _choose_field_item_quantity(
        ctx, item_type, item_id, destination,
    )
    if quantity is None:
        return
    unit_price = spec.price_per_round if item_type == "ammo" else spec.price
    cost = quantity * unit_price
    if cost > ctx.stats.credits:
        ctx.log.add("You can no longer afford that ammunition.")
        return
    destination_items = (
        _expedition_items(ctx)
        if destination == ground_equipment.EXPEDITION_INVENTORY
        else _armory_items(ctx)
    )
    destination_equipment = (
        _expedition_storage(ctx)
        if destination == ground_equipment.EXPEDITION_INVENTORY
        else []
    )
    try:
        ground_equipment.add_item_quantity(
            destination_equipment, destination_items,
            item_type, item_id, quantity,
            strength=_strength(ctx), container=destination,
        )
    except (KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return
    ctx.stats.credits -= cost
    label = "Expedition Pack" if destination == ground_equipment.EXPEDITION_INVENTORY else "Armory Storage"
    ctx.log.add(f"Bought {spec.name} x{quantity} into {label} for {cost}$.")


def _needs_displacement(ctx, entry: ground_equipment.StoredGroundEquipment) -> bool:
    """Return whether installing an entry would displace active equipment."""
    if entry.item_type == "weapon":
        return not ground_equipment.can_fit_weapons(
            ctx.equipped_ground_weapons, entry.item_id,
        )
    from ..data.ground_armor import find_ground_armor
    return bool(ctx.equipped_ground_armor.get(find_ground_armor(entry.item_id).slot))


def _displacement_container(ctx, entry, container: str) -> str:
    """Choose Expedition Pack first, falling back to Armory Storage."""
    if entry.item_type == "weapon":
        displaced_count = ground_equipment.displaced_weapon_count(
            ctx.equipped_ground_weapons, entry.item_id,
        )
    else:
        from ..data.ground_armor import find_ground_armor
        displaced_count = int(
            bool(ctx.equipped_ground_armor.get(find_ground_armor(entry.item_id).slot))
        )
    return ground_equipment.preferred_displacement_container(
        len(_expedition_storage(ctx)),
        ground_equipment.expedition_capacity(_strength(ctx)),
        displaced_count,
        container,
    )


def _install_from_container(
    ctx, entries, index: int, container: str,
    displaced_container: str | None = None,
) -> None:
    """Equip an owned item, routing displaced gear automatically."""
    if not 0 <= index < len(entries):
        ctx.log.add("That equipment is no longer available.")
        return
    entry = entries[index]
    try:
        if displaced_container is None and _needs_displacement(ctx, entry):
            displaced_container = _displacement_container(ctx, entry, container)
        displaced_storage = {
            ground_equipment.ARMORY_STORAGE: _armory_storage(ctx),
            ground_equipment.EXPEDITION_INVENTORY: _expedition_storage(ctx),
        }.get(displaced_container or container)
        if entry.item_type == "weapon":
            ground_equipment.install_weapon(
                ctx.equipped_ground_weapons, entries, index,
                displaced_storage=displaced_storage,
                container=container,
                displaced_container=displaced_container or container,
                strength=_strength(ctx),
            )
        else:
            ground_equipment.install_armor(
                ctx.equipped_ground_armor, entries, index,
                displaced_storage=displaced_storage,
                container=container,
                displaced_container=displaced_container or container,
                strength=_strength(ctx),
            )
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return
    ctx.log.add(f"Equipped {_equipment_name(entry)}.")


def _transfer_container_item(ctx, entries, index: int, source: str) -> None:
    """Move one stored item between the armory and expedition containers."""
    destination = (
        ground_equipment.EXPEDITION_INVENTORY
        if source == ground_equipment.ARMORY_STORAGE
        else ground_equipment.ARMORY_STORAGE
    )
    destination_entries = (
        _expedition_storage(ctx)
        if destination == ground_equipment.EXPEDITION_INVENTORY
        else _armory_storage(ctx)
    )
    try:
        ground_equipment.transfer_item(
            entries, destination_entries, index,
            destination_container=destination,
            strength=_strength(ctx),
        )
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return
    ctx.log.add(
        "Moved equipment to "
        + ("the Expedition Pack." if destination == ground_equipment.EXPEDITION_INVENTORY else "Armory Storage.")
    )


def _choose_container_action(ctx, entries, index: int, container: str) -> str:
    """Choose equip, transfer, or sell for one stored item."""
    from .. import pygame_story

    if not 0 <= index < len(entries):
        return "__BACK__"
    entry = entries[index]
    try:
        name = _equipment_name(entry)
        price = _sell_price(entry.item_id)
    except (KeyError, ValueError):
        return "__BACK__"
    transfer_label, transfer_action = {
        ground_equipment.ARMORY_STORAGE: ("Pack", "MOVE_TO_EXPEDITION"),
        ground_equipment.EXPEDITION_INVENTORY: ("Armory", "MOVE_TO_ARMORY"),
    }[container]
    return pygame_story.choose(
        ctx,
        title="GROUND EQUIPMENT",
        body=name,
        options=(
            ("Equip", f"INSTALL_{container}:{index}"),
            (transfer_label, f"{transfer_action}:{index}"),
            (f"Sell for {price}$", f"SELL_{container}:{index}"),
        ),
        caption="spacehack - ground equipment",
        compact=True,
    )


def _apply_container_choice(ctx, entries, index: int, container: str) -> None:
    """Apply an equip, transfer, or sell choice from a storage container."""
    chosen = _choose_container_action(ctx, entries, index, container)
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("INSTALL_"):
        _install_from_container(ctx, entries, index, container)
    elif chosen.startswith("MOVE_TO_"):
        _transfer_container_item(ctx, entries, index, container)
    elif chosen.startswith("SELL_"):
        _sell_from_container(ctx, entries, index)


def _choose_field_item_action(ctx, entries, index: int, container: str) -> str:
    """Choose transfer or discard for one owned field-item stack."""
    from .. import pygame_story

    if not 0 <= index < len(entries):
        return "__BACK__"
    stack = entries[index]
    try:
        name = _field_item_name(stack)
    except (KeyError, TypeError, ValueError):
        return "__BACK__"
    if container == ground_equipment.ARMORY_STORAGE:
        options = (
            ("Pack", f"MOVE_ITEM_TO_EXPEDITION:{index}"),
            ("Discard", f"DISCARD_ITEM:{index}"),
        )
    else:
        options = (
            ("Armory", f"MOVE_ITEM_TO_ARMORY:{index}"),
            ("Discard", f"DISCARD_ITEM:{index}"),
        )
    return pygame_story.choose(
        ctx, title="FIELD ITEM", body=name,
        options=options, caption="spacehack - field item", compact=True,
    )


def _transfer_field_item(ctx, entries, index: int, source: str) -> None:
    """Move one complete field-item stack between Armory and Pack."""
    destination = (
        ground_equipment.EXPEDITION_INVENTORY
        if source == ground_equipment.ARMORY_STORAGE
        else ground_equipment.ARMORY_STORAGE
    )
    destination_items = (
        _expedition_items(ctx)
        if destination == ground_equipment.EXPEDITION_INVENTORY
        else _armory_items(ctx)
    )
    destination_equipment = (
        _expedition_storage(ctx)
        if destination == ground_equipment.EXPEDITION_INVENTORY
        else []
    )
    try:
        ground_equipment.transfer_item_stack(
            entries, destination_equipment, destination_items, index,
            destination_container=destination, strength=_strength(ctx),
        )
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return
    label = "the Expedition Pack" if destination == ground_equipment.EXPEDITION_INVENTORY else "Armory Storage"
    ctx.log.add(f"Moved field item stack to {label}.")


def _apply_field_item_choice(ctx, entries, index: int, container: str) -> None:
    """Apply one transfer/discard choice for an owned field-item stack."""
    chosen = _choose_field_item_action(ctx, entries, index, container)
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("MOVE_ITEM_TO_"):
        _transfer_field_item(ctx, entries, index, container)
    elif chosen.startswith("DISCARD_ITEM:") and 0 <= index < len(entries):
        entries.pop(index)
        ctx.log.add("Discarded field item stack.")


def _sell_from_container(ctx, entries, index: int) -> None:
    """Sell one owned item from a warehouse or expedition pack."""
    if not 0 <= index < len(entries):
        ctx.log.add("That equipment is no longer available.")
        return
    entry = entries[index]
    try:
        removed = ground_equipment.sell_stored(entries, index)
        price = _sell_price(removed.item_id)
    except (IndexError, KeyError, ValueError):
        ctx.log.add("That equipment is no longer available.")
        return
    ctx.stats.credits += price
    ctx.log.add(f"Sold {_equipment_name(entry)} for {price}$.")


def _purchase_spec(item_type: str, item_id: str):
    """Resolve the spec for one buy action."""
    from ..data.ground_armor import find_ground_armor
    from ..data.ground_weapons import find_ground_weapon

    if item_type == "weapon":
        return find_ground_weapon(item_id)
    return find_ground_armor(item_id)


def _install_purchase(ctx, entry, item_type: str) -> None:
    """Equip a fresh purchase, routing displaced gear automatically."""
    pack = _expedition_storage(ctx)
    source = [entry]
    displaced_container = _displacement_container(
        ctx, entry, ground_equipment.ARMORY_STORAGE,
    )
    displaced_storage = (
        pack
        if displaced_container == ground_equipment.EXPEDITION_INVENTORY
        else _armory_storage(ctx)
    )
    if item_type == "weapon":
        ground_equipment.install_weapon(
            ctx.equipped_ground_weapons, source, 0,
            displaced_storage=displaced_storage,
            container=ground_equipment.ARMORY_STORAGE,
            displaced_container=displaced_container,
            strength=_strength(ctx),
        )
    else:
        ground_equipment.install_armor(
            ctx.equipped_ground_armor, source, 0,
            displaced_storage=displaced_storage,
            container=ground_equipment.ARMORY_STORAGE,
            displaced_container=displaced_container,
            strength=_strength(ctx),
        )


def _apply_purchase(ctx, action: str) -> None:
    """Complete a validated purchase destination."""
    _destination, item_type, item_id = action.split(":", 2)
    spec = _purchase_spec(item_type, item_id)
    if ctx.stats.credits < spec.price:
        ctx.log.add(f"You need {spec.price}$ to buy {spec.name}.")
        return
    entry = ground_equipment.StoredGroundEquipment(item_type, item_id)
    try:
        if _destination == "BUY_INSTALL":
            _install_purchase(ctx, entry, item_type)
        elif _destination == "BUY_ARMORY":
            ground_equipment.add_stored(
                _armory_storage(ctx), entry,
                container=ground_equipment.ARMORY_STORAGE,
                strength=_strength(ctx),
            )
        elif _destination == "BUY_EXPEDITION":
            ground_equipment.transfer_item(
                [entry], _expedition_storage(ctx), 0,
                destination_container=ground_equipment.EXPEDITION_INVENTORY,
                strength=_strength(ctx),
            )
        else:
            raise ValueError(f"Unknown purchase destination: {_destination!r}")
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return
    ctx.stats.credits -= spec.price
    destination_label = {
        "BUY_INSTALL": "active loadout",
        "BUY_ARMORY": "armory storage",
        "BUY_EXPEDITION": "expedition pack",
    }[_destination]
    ctx.log.add(f"Bought {spec.name} into {destination_label}.")



def _manage_choice(ctx, kind: str, slot, item_id: str) -> str:
    """Open the Store/Sell chooser for one active equipment slot."""
    from .. import pygame_story

    item_type = "weapon" if kind == "MANAGE_WEAPON" else "armor"
    entry = ground_equipment.StoredGroundEquipment(item_type, item_id)
    label = _equipment_name(entry)
    if kind == "MANAGE_WEAPON":
        options = (
            ("Store in Armory", f"STORE_WEAPON:{slot}"),
            (f"Sell for {_sell_price(item_id)}$", f"SELL_WEAPON:{slot}"),
        )
    else:
        options = (
            ("Store in Armory", f"STORE_ARMOR:{slot}"),
            (f"Sell for {_sell_price(item_id)}$", f"SELL_ARMOR:{slot}"),
        )
    return pygame_story.choose(
        ctx, title="MANAGE LOADOUT", body=label,
        options=options,
        caption="spacehack - manage loadout", compact=True,
    )


def _apply_manage_choice(ctx, chosen: str) -> None:
    """Apply a Store/Sell choice from the manage-loadout chooser."""
    try:
        if chosen.startswith("STORE_WEAPON:"):
            slot = int(chosen.split(":", 1)[1])
            ground_equipment.store_weapon(
                ctx.equipped_ground_weapons, _armory_storage(ctx), slot,
            )
        elif chosen.startswith("STORE_ARMOR:"):
            ground_equipment.store_armor(
                ctx.equipped_ground_armor, _armory_storage(ctx),
                chosen.split(":", 1)[1],
            )
        elif chosen.startswith("SELL_WEAPON:"):
            slot = int(chosen.split(":", 1)[1])
            removed = ground_equipment.remove_weapon(ctx.equipped_ground_weapons, slot)
            ctx.stats.credits += _sell_price(removed.item_id)
        elif chosen.startswith("SELL_ARMOR:"):
            removed = ground_equipment.remove_armor(
                ctx.equipped_ground_armor, chosen.split(":", 1)[1],
            )
            ctx.stats.credits += _sell_price(removed.item_id)
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))


def _manage_loadout(ctx, action: str) -> None:
    """Open the active-loadout Store/Sell chooser."""
    kind, slot_text = action.split(":", 1)
    if kind == "MANAGE_WEAPON":
        slot = int(slot_text)
        if not 0 <= slot < len(ctx.equipped_ground_weapons):
            return
        item_id = ctx.equipped_ground_weapons[slot].weapon_id
    else:
        slot = slot_text
        item_id = ctx.equipped_ground_armor.get(slot)
        if not item_id:
            return
    chosen = _manage_choice(ctx, kind, slot, item_id)
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    _apply_manage_choice(ctx, chosen)


def _apply_buy_action(ctx: GameContext, action: str) -> None:
    """Apply an equipment or ammo purchase action."""
    if action.startswith(("BUY_INSTALL:", "BUY_ARMORY:", "BUY_EXPEDITION:")):
        _apply_purchase(ctx, action)
        return
    if action.startswith(("BUY_AMMO:", "BUY_CONSUMABLE:")):
        item_type, item_id = action.split(":", 1)
        item_type = "ammo" if item_type == "BUY_AMMO" else "consumable"
        chosen = _choose_field_item_destination(ctx, item_type, item_id)
        if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
            return
        if chosen == "__QUIT__":
            raise SystemExit
        _parts = chosen.split(":", 2)
        destination = (
            ground_equipment.EXPEDITION_INVENTORY
            if _parts[0].endswith("EXPEDITION")
            else ground_equipment.ARMORY_STORAGE
        )
        _purchase_field_item(ctx, _parts[2], destination, _parts[1])
        return
    item_type, item_id = action.split(":", 1)
    chosen = _choose_destination(ctx, item_type.removeprefix("BUY_").lower(), item_id)
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    _apply_purchase(ctx, chosen)


def _apply_storage_action(ctx: GameContext, action: str) -> None:
    """Apply one equipment or field-item storage action."""
    prefix, index_text = action.split(":", 1)
    index = int(index_text)
    if prefix == "MANAGE_ARMORY":
        _apply_container_choice(ctx, _armory_storage(ctx), index, ground_equipment.ARMORY_STORAGE)
    elif prefix == "MANAGE_EXPEDITION":
        _apply_container_choice(ctx, _expedition_storage(ctx), index, ground_equipment.EXPEDITION_INVENTORY)
    elif prefix == "MANAGE_ARMORY_ITEM":
        _apply_field_item_choice(ctx, _armory_items(ctx), index, ground_equipment.ARMORY_STORAGE)
    else:
        _apply_field_item_choice(ctx, _expedition_items(ctx), index, ground_equipment.EXPEDITION_INVENTORY)


def _apply_pygame_armory_action(ctx: GameContext, action: str, focus: int, selected: int) -> bool:
    """Apply one armory action and keep the modal open."""
    del focus, selected
    if not action:
        return True
    if action.startswith("BUY_"):
        _apply_buy_action(ctx, action)
        return True
    if action.startswith((
        "MANAGE_ARMORY:", "MANAGE_EXPEDITION:",
        "MANAGE_ARMORY_ITEM:", "MANAGE_EXPEDITION_ITEM:",
    )):
        _apply_storage_action(ctx, action)
        return True
    if action.startswith(("MANAGE_WEAPON:", "MANAGE_ARMOR:")):
        _manage_loadout(ctx, action)
        return True
    raise ValueError(f"Unknown armory action: {action!r}")


def _run_armory_menu(ctx: GameContext, planet_id: str = "") -> None:
    """Show the Phase 2 ground-equipment armory modal."""
    from .. import pygame_split
    from ..time import month_index

    catalog = _catalog_items(planet_id, month_index(ctx))
    mode = "BUY"

    def build_frame():
        return _pygame_armory_frame(ctx, planet_id, mode, catalog=catalog)

    def apply_action(action, focus, selected):
        nonlocal mode
        if action.startswith("MODE:"):
            requested = action.split(":", 1)[1]
            if requested not in _ARMORY_MODES:
                raise ValueError(f"Unknown armory mode: {requested!r}")
            mode = requested
            return True
        return _apply_pygame_armory_action(ctx, action, focus, selected)

    pygame_split.run_interactive(
        ctx, build_frame, apply_action, caption="spacehack - armory",
    )
