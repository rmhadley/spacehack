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
    return (
        f"{hands}  Damage: {spec.damage}  Accuracy: {spec.accuracy}%  "
        f"Range: {spec.min_range}-{spec.max_range}"
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
    return f"{spec.slot.title()}  Defense: {spec.defense}  {spec.description}"


def _buy_rows():
    """Build catalog rows for the Buy view."""
    from .. import pygame_split, pygame_ui
    from ..data.ground_armor import list_ground_armor
    from ..data.ground_weapons import list_ground_weapons

    rows = [pygame_split.section_header("WEAPONS")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            _weapon_detail(spec),
            f"BUY_WEAPON:{spec.id}",
        )
        for spec in sorted(list_ground_weapons(), key=lambda item: item.price)
        if getattr(spec, "shop_available", True)
    )
    rows.append(pygame_split.section_header("ARMOUR"))
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            f"{spec.slot.title()}  Defense: {spec.defense}  {spec.description}",
            f"BUY_ARMOR:{spec.id}",
        )
        for spec in sorted(list_ground_armor(), key=lambda item: item.price)
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
        rows.append(pygame_split.SplitRow("[empty]", "", "No stored ground equipment.", "", False))
    return tuple(rows)


def _loadout_rows(ctx: GameContext):
    """Build selectable rows for the active ground loadout."""
    from .. import pygame_split, pygame_ui
    from ..data.ground_armor import find_ground_armor
    from ..data.ground_weapons import find_ground_weapon

    rows = [pygame_split.section_header("WEAPON SLOTS")]
    weapons = list(ctx.equipped_ground_weapons)
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
    rows.append(pygame_split.section_header("ARMOUR SLOTS"))
    for slot in _ARMOR_SLOTS:
        item_id = ctx.equipped_ground_armor.get(slot)
        if not item_id:
            rows.append(pygame_split.SplitRow(f"{_ARMOR_SLOT_LABELS[slot]}: [empty]", "", "", "", False))
            continue
        spec = find_ground_armor(item_id)
        rows.append(pygame_split.SplitRow(
            f"{_ARMOR_SLOT_LABELS[slot]}: {spec.name}",
            pygame_ui.sell_cell(_sell_price(item_id)),
            f"Defense: {spec.defense}  {spec.description}",
            f"MANAGE_ARMOR:{slot}",
        ))
    return tuple(rows)


def _pygame_armory_frame(ctx: GameContext, planet_id: str = "", mode: str = "BUY"):
    """Build one armory frame for Buy, Armory, or Expedition mode."""
    from .. import pygame_split, pygame_ui

    if mode not in _ARMORY_MODES:
        raise ValueError(f"Unknown armory mode: {mode!r}")
    if mode == "BUY":
        left_rows = _buy_rows()
        left_label = "Buy"
    elif mode == "ARMORY":
        left_rows = _storage_rows(_armory_storage(ctx), "MANAGE_ARMORY")
        left_label = "Armory Storage"
    else:
        left_rows = _storage_rows(
            _expedition_storage(ctx), "MANAGE_EXPEDITION", "BACKPACK ITEMS",
        )
        left_label = "Expedition Pack"
    capacity = ground_equipment.expedition_capacity(_strength(ctx))
    pack_count = len(_expedition_storage(ctx))
    left_tabs = (
        *_MODE_TABS,
        f"[E]xpedition ({pack_count}/{capacity})",
    )
    return pygame_split.SplitFrame(
        pygame_ui.terminal_title("ARMORY", planet_id),
        left_label,
        "My Loadout",
        left_rows,
        _loadout_rows(ctx),
        pygame_ui.credits_label(ctx.stats.credits),
        f"Pack: {len(_expedition_storage(ctx))}/{capacity}  Armory: unlimited",
        pygame_ui.modal_hint(
            "UP/DOWN navigate", "TAB switch panel", "ENTER choose",
            "B buy", "A armory", "E expedition", "ESC back", pygame_ui.GUIDE_HINT,
        ),
        left_tabs=left_tabs,
        active_left_tab=_ARMORY_MODES.index(mode),
        left_tab_modes=_ARMORY_MODES,
    )


def _choose_destination(ctx, item_type: str, item_id: str) -> str:
    """Ask where a purchase should go."""
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


def _apply_purchase(ctx, action: str) -> None:
    """Complete a validated purchase destination."""
    _destination, item_type, item_id = action.split(":", 2)
    from ..data.ground_armor import find_ground_armor
    from ..data.ground_weapons import find_ground_weapon

    spec = find_ground_weapon(item_id) if item_type == "weapon" else find_ground_armor(item_id)
    if ctx.stats.credits < spec.price:
        ctx.log.add(f"You need {spec.price}$ to buy {spec.name}.")
        return
    entry = ground_equipment.StoredGroundEquipment(item_type, item_id)
    armory = _armory_storage(ctx)
    pack = _expedition_storage(ctx)
    try:
        if _destination not in {"BUY_INSTALL", "BUY_ARMORY", "BUY_EXPEDITION"}:
            raise ValueError(f"Unknown purchase destination: {_destination!r}")
        if _destination == "BUY_INSTALL":
            source = [entry]
            displaced_container = _displacement_container(
                ctx, entry, ground_equipment.ARMORY_STORAGE,
            )
            displaced_storage = (
                pack
                if displaced_container == ground_equipment.EXPEDITION_INVENTORY
                else armory
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
        elif _destination == "BUY_ARMORY":
            ground_equipment.add_stored(
                armory, entry,
                container=ground_equipment.ARMORY_STORAGE,
                strength=_strength(ctx),
            )
        else:
            ground_equipment.transfer_item(
                [entry], pack, 0,
                destination_container=ground_equipment.EXPEDITION_INVENTORY,
                strength=_strength(ctx),
            )
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



def _manage_loadout(ctx, action: str) -> None:
    """Open the active-loadout Store/Sell chooser."""
    kind, slot_text = action.split(":", 1)
    from .. import pygame_story
    if kind == "MANAGE_WEAPON":
        slot = int(slot_text)
        if not 0 <= slot < len(ctx.equipped_ground_weapons):
            return
        item_id = ctx.equipped_ground_weapons[slot]
        item_type = "weapon"
        label = _equipment_name(ground_equipment.StoredGroundEquipment(item_type, item_id))
        chosen = pygame_story.choose(
            ctx, title="MANAGE LOADOUT", body=label,
            options=(("Store in Armory", f"STORE_WEAPON:{slot}"), (f"Sell for {_sell_price(item_id)}$", f"SELL_WEAPON:{slot}")),
            caption="spacehack - manage loadout", compact=True,
        )
    else:
        slot = slot_text
        item_id = ctx.equipped_ground_armor.get(slot)
        if not item_id:
            return
        label = _equipment_name(ground_equipment.StoredGroundEquipment("armor", item_id))
        chosen = pygame_story.choose(
            ctx, title="MANAGE LOADOUT", body=label,
            options=(("Store in Armory", f"STORE_ARMOR:{slot}"), (f"Sell for {_sell_price(item_id)}$", f"SELL_ARMOR:{slot}")),
            caption="spacehack - manage loadout", compact=True,
        )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("STORE_WEAPON:"):
        try:
            ground_equipment.store_weapon(ctx.equipped_ground_weapons, _armory_storage(ctx), int(chosen.split(":", 1)[1]))
        except (IndexError, KeyError, ValueError) as exc:
            ctx.log.add(str(exc))
    elif chosen.startswith("STORE_ARMOR:"):
        try:
            ground_equipment.store_armor(ctx.equipped_ground_armor, _armory_storage(ctx), chosen.split(":", 1)[1])
        except (IndexError, KeyError, ValueError) as exc:
            ctx.log.add(str(exc))
    elif chosen.startswith("SELL_WEAPON:"):
        slot = int(chosen.split(":", 1)[1])
        try:
            removed = ground_equipment.remove_weapon(ctx.equipped_ground_weapons, slot)
        except (IndexError, KeyError, ValueError) as exc:
            ctx.log.add(str(exc))
            return
        ctx.stats.credits += _sell_price(removed.item_id)
    elif chosen.startswith("SELL_ARMOR:"):
        slot = chosen.split(":", 1)[1]
        try:
            removed = ground_equipment.remove_armor(ctx.equipped_ground_armor, slot)
        except (IndexError, KeyError, ValueError) as exc:
            ctx.log.add(str(exc))
            return
        ctx.stats.credits += _sell_price(removed.item_id)


def _apply_pygame_armory_action(ctx: GameContext, action: str, focus: int, selected: int) -> bool:
    """Apply one armory action and keep the modal open."""
    if not action:
        return True
    if action.startswith("BUY_"):
        if action.startswith(("BUY_INSTALL:", "BUY_ARMORY:", "BUY_EXPEDITION:")):
            _apply_purchase(ctx, action)
            return True
        item_type, item_id = action.split(":", 1)
        chosen = _choose_destination(ctx, item_type.removeprefix("BUY_").lower(), item_id)
        if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
            return True
        if chosen == "__QUIT__":
            raise SystemExit
        _apply_purchase(ctx, chosen)
        return True
    if action.startswith("MANAGE_ARMORY:"):
        index = int(action.split(":", 1)[1])
        _apply_container_choice(
            ctx, _armory_storage(ctx), index, ground_equipment.ARMORY_STORAGE,
        )
        return True
    if action.startswith("MANAGE_EXPEDITION:"):
        index = int(action.split(":", 1)[1])
        _apply_container_choice(
            ctx, _expedition_storage(ctx), index, ground_equipment.EXPEDITION_INVENTORY,
        )
        return True
    if action.startswith(("MANAGE_WEAPON:", "MANAGE_ARMOR:")):
        _manage_loadout(ctx, action)
        return True
    raise ValueError(f"Unknown armory action: {action!r}")


def _run_armory_menu(ctx: GameContext, planet_id: str = "") -> None:
    """Show the Phase 2 ground-equipment armory modal."""
    from .. import pygame_split

    mode = "BUY"

    def build_frame():
        return _pygame_armory_frame(ctx, planet_id, mode)

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
