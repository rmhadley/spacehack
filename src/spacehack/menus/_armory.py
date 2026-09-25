"""Armory terminal split-screen for ground equipment ownership.

Phase 2 exposes three left-panel views:

* ``BUY`` — catalog items available at the current armory.
* ``ARMORY`` — the unlimited global warehouse.
* ``EXPEDITION`` — the limited reserve pack prepared for dungeon runs.

The active loadout remains on the right. This module owns presentation and
choice routing only; equipment mutation lives in :mod:`spacehack.ground_equipment`.
"""

from __future__ import annotations

from ._armory_buy import (  # noqa: F401 — detail helpers + re-exported buy rows
    _armor_detail,
    _armor_effects,
    _buy_consumable_rows,
    _buy_rows,
    _restock_rows,
    _weapon_detail,
)
from ._armory_field_items import (  # noqa: F401 — re-exported field-item surface
    _choose_field_item_destination,
    _choose_field_item_quantity,
    _destination_storages,
    _field_item_detail,
    _field_item_name,
    _field_item_purchase_maximum,
    _field_item_rows,
    _purchase_field_item,
    _restock_bandolier,
)

from .. import ground_equipment
from ..game_context import GameContext

from ..ground_equipment import (  # noqa: F401 — re-exported slot tables
    ARMOR_SLOTS as _ARMOR_SLOTS,
    ARMOR_SLOT_LABELS as _ARMOR_SLOT_LABELS,
)
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
    """Return effective Strength for pack-capacity calculations."""
    from ..xp import pack_mule_capacity_bonus
    return int(getattr(getattr(ctx, "ground_stats", None), "strength", 10)) + pack_mule_capacity_bonus(ctx) * 10

def _sell_price(item_id: str, quality: int = 0) -> int:
    """Half the catalog price scaled by the quality tier, minimum 1."""
    from ..data.ground_armor import find_ground_armor
    from ..data.ground_weapons import find_ground_weapon
    from ..data.quality import quality_multiplier_pct

    try:
        family, price = "weapon", find_ground_weapon(item_id).price
    except KeyError:
        family, price = "armor", find_ground_armor(item_id).price
    if quality <= 0:
        return price // 2
    return max(1, (price * quality_multiplier_pct(family, quality) + 100) // 200)

def _name_with_tier(name: str, quality: int, prefix: str = "") -> tuple:
    """``(label, runs)`` — the tiered name coloured inside its label."""
    from .. import message_log
    from ..data.quality import quality_mark

    return message_log.with_runs(prefix, quality_mark(name, quality))


def _equipment_name(entry: ground_equipment.StoredGroundEquipment) -> str:
    """Resolve one stored item's token-prefixed display name."""
    return ground_equipment.display_name(
        entry.item_type, entry.item_id, entry.quality,
    )

def _equipment_detail(entry: ground_equipment.StoredGroundEquipment) -> str:
    """Resolve one stored item's effective (tier-scaled) details."""
    from ..data.quality import effective_armor_spec, effective_weapon_spec

    if entry.item_type == "weapon":
        return _weapon_detail(effective_weapon_spec(entry.item_id, entry.quality)) + (
            ground_equipment.stored_mag_suffix(entry)
        )
    return _armor_detail(effective_armor_spec(entry.item_id, entry.quality))

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
            _label, _runs = _name_with_tier(_equipment_name(entry), entry.quality)
            rows.append(
                pygame_split.SplitRow(
                    _label,
                    pygame_ui.sell_cell(_sell_price(entry.item_id, entry.quality)),
                    _equipment_detail(entry),
                    f"{action_prefix}:{index}",
                    runs=_runs,
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

def _weapon_slot_rows(ctx: GameContext):
    """Two class-group weapon rows mirroring the C screen (doc 51.3)."""
    from .. import pygame_split
    from ..ground_weapon_sets import SET_CLASSES, class_home, founded_set_role

    rows = []
    for set_class, label in SET_CLASSES:
        role = founded_set_role(
            ctx.equipped_ground_weapons, ctx.holstered_ground_weapons, set_class,
        )
        marker = f" [{role}]" if role is not None else ""
        rows.append(pygame_split.section_header(f"WEAPONS - {label}{marker}"))
        home = class_home(
            ctx.equipped_ground_weapons, ctx.holstered_ground_weapons, set_class,
        )
        rows.extend(_weapon_member_rows(ctx, home or [], set_class))
    return rows


def _weapon_member_rows(ctx: GameContext, home: list, set_class: str) -> list:
    """Both slot rows for one weapon set — members first, then the
    empty/occupied pad (mirrors the C screen's capacity display)."""
    from .. import pygame_split, pygame_ui
    from ..data.quality import effective_weapon_spec
    from ..ground_equipment import WEAPON_SLOT_COUNT
    from ..ground_weapon_sets import _set_is_two_handed

    del ctx
    rows = []
    for index in range(WEAPON_SLOT_COUNT):
        if index >= len(home):
            occupied = _set_is_two_handed(home)
            label = "--- (occupied by 2H)" if occupied else "[empty]"
            rows.append(pygame_split.SplitRow(label, "", "", "", False, occupied))
            continue
        instance = home[index]
        try:
            spec = effective_weapon_spec(instance.weapon_id, instance.quality)
        except KeyError:
            continue
        _label, _runs = _name_with_tier(
            ground_equipment.display_name(
                "weapon", instance.weapon_id, instance.quality,
            ),
            instance.quality,
        )
        rows.append(pygame_split.SplitRow(
            _label,
            pygame_ui.sell_cell(_sell_price(instance.weapon_id, instance.quality)),
            _weapon_detail(spec),
            f"MANAGE_WEAPON:{set_class}:{index}",
            runs=_runs,
        ))
    return rows

def _armor_slot_rows(ctx: GameContext):
    """Build the armor-slot rows for the active ground loadout."""
    from .. import pygame_split, pygame_ui

    rows = [pygame_split.section_header("ARMOUR SLOTS")]
    for slot in _ARMOR_SLOTS:
        entry = ctx.equipped_ground_armor.get(slot)
        if entry is None:
            rows.append(pygame_split.SplitRow(f"{_ARMOR_SLOT_LABELS[slot]}: [empty]", "", "", "", False))
            continue
        from ..data.quality import effective_armor_spec

        spec = effective_armor_spec(entry.item_id, entry.quality)
        _label, _runs = _name_with_tier(
            ground_equipment.display_name("armor", entry.item_id, entry.quality),
            entry.quality, prefix=f"{_ARMOR_SLOT_LABELS[slot]}: ",
        )
        rows.append(pygame_split.SplitRow(
            _label,
            pygame_ui.sell_cell(_sell_price(entry.item_id, entry.quality)),
            f"Defense: {spec.defense}{_armor_effects(spec)}  {spec.description}",
            f"MANAGE_ARMOR:{slot}",
            runs=_runs,
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
            + _restock_rows(ctx)
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

async def _choose_destination(ctx, item_type: str, item_id: str) -> str:
    """Ask where a ground-equipment purchase should go."""
    from .. import pygame_story
    from ..data.ground_armor import find_ground_armor
    from ..data.ground_weapons import find_ground_weapon

    spec = find_ground_weapon(item_id) if item_type == "weapon" else find_ground_armor(item_id)
    return await pygame_story.choose(
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

def _preferred_displaced_destination(
    ctx, displaced_count: int, source_container: str,
) -> str:
    """Expedition Pack first, falling back to unlimited Armory Storage."""
    return ground_equipment.preferred_displacement_container(
        len(_expedition_storage(ctx)) + len(_expedition_items(ctx)),
        ground_equipment.expedition_capacity(_strength(ctx)),
        displaced_count,
        source_container,
    )


def _displaced_storage_for(ctx, container: str) -> list:
    """The storage list a displacement container names."""
    return {
        ground_equipment.ARMORY_STORAGE: _armory_storage(ctx),
        ground_equipment.EXPEDITION_INVENTORY: _expedition_storage(ctx),
    }[container]


def _chooser_install_destination(
    ctx, fits: bool, displace_index: int | None, home_len: int,
    displaced_container: str | None,
) -> str:
    """Preferred displacement destination for a chooser install."""
    count = 0 if fits else (1 if displace_index is not None else home_len)
    return displaced_container or _preferred_displaced_destination(
        ctx, count, ground_equipment.ARMORY_STORAGE,
    )


async def _install_weapon_with_chooser(
    ctx, source: list, index: int, displaced_container: str | None,
) -> str | None:
    """Set-aware weapon install with the member chooser (doc 51.3).

    A 1H pick into a full home chooses who leaves; a 2H displaces the
    whole set. Returns the landing role (``"ACTIVE"``/``"HOLSTER"``)
    or ``None`` when the chooser was cancelled (nothing changes);
    raises on validation failures the caller logs.
    """
    from .. import ground_weapon_sets
    from ..character_screen import _choose_displaced_member
    from ..ground_equipment import weapon_hands

    entry = source[index]
    resolved = ground_weapon_sets.resolve_weapon_home(
        ctx.equipped_ground_weapons, ctx.holstered_ground_weapons, entry.item_id,
    )
    if resolved is None:
        raise ValueError(ground_weapon_sets.NO_WEAPON_HOME_LINE)
    home, role = resolved
    fits = ground_weapon_sets.can_fit_weapon_set(home, entry.item_id)
    displace_index = None
    if not fits and weapon_hands(entry.item_id) == 1:
        displace_index = await _choose_displaced_member(ctx, home, entry)
        if displace_index is None:
            return None
    destination = _chooser_install_destination(
        ctx, fits, displace_index, len(home), displaced_container,
    )
    ground_weapon_sets.install_set_weapon(
        ctx.equipped_ground_weapons, ctx.holstered_ground_weapons,
        source, index,
        displace_index=displace_index,
        displaced_storage=_displaced_storage_for(ctx, destination),
        displaced_container=destination,
        strength=_strength(ctx),
    )
    return role


async def _install_from_container(
    ctx, entries, index: int, container: str,
    displaced_container: str | None = None,
) -> None:
    """Equip an owned item, routing displaced gear automatically."""
    if not 0 <= index < len(entries):
        ctx.log.add("That equipment is no longer available.")
        return
    entry = entries[index]
    try:
        if entry.item_type == "weapon":
            if await _install_weapon_with_chooser(
                ctx, entries, index, displaced_container,
            ) is None:
                return
        else:
            from ..data.ground_armor import find_ground_armor

            if ctx.equipped_ground_armor.get(find_ground_armor(entry.item_id).slot):
                displaced_container = displaced_container or (
                    _preferred_displaced_destination(ctx, 1, container)
                )
            ground_equipment.install_armor(
                ctx.equipped_ground_armor, entries, index,
                displaced_storage=_displaced_storage_for(
                    ctx, displaced_container or container,
                ),
                container=container,
                displaced_container=displaced_container or container,
                strength=_strength(ctx),
            )
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return
    _log_equipped(ctx, entry)


def _log_equipped(ctx, entry) -> None:
    """``"Equipped Prototype Mono Blade."`` with the tier name coloured."""
    from .. import message_log
    from ..data.quality import quality_mark

    _msg, _runs = message_log.with_runs(
        "Equipped ",
        quality_mark(_equipment_name(entry), entry.quality), ".",
    )
    ctx.log.add(_msg, runs=_runs)

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
            destination_items=_expedition_items(ctx),
        )
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return
    ctx.log.add(
        "Moved equipment to "
        + ("the Expedition Pack." if destination == ground_equipment.EXPEDITION_INVENTORY else "Armory Storage.")
    )

async def _choose_container_action(ctx, entries, index: int, container: str) -> str:
    """Choose equip, transfer, or sell for one stored item."""
    from .. import pygame_story

    if not 0 <= index < len(entries):
        return "__BACK__"
    entry = entries[index]
    try:
        name = _equipment_name(entry)
        price = _sell_price(entry.item_id, entry.quality)
    except (KeyError, ValueError):
        return "__BACK__"
    transfer_label, transfer_action = {
        ground_equipment.ARMORY_STORAGE: ("Pack", "MOVE_TO_EXPEDITION"),
        ground_equipment.EXPEDITION_INVENTORY: ("Armory", "MOVE_TO_ARMORY"),
    }[container]
    return await pygame_story.choose(
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

async def _apply_container_choice(ctx, entries, index: int, container: str) -> None:
    """Apply an equip, transfer, or sell choice from a storage container."""
    chosen = await _choose_container_action(ctx, entries, index, container)
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("INSTALL_"):
        await _install_from_container(ctx, entries, index, container)
    elif chosen.startswith("MOVE_TO_"):
        _transfer_container_item(ctx, entries, index, container)
    elif chosen.startswith("SELL_"):
        _sell_from_container(ctx, entries, index)

async def _choose_field_item_action(ctx, entries, index: int, container: str) -> str:
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
    return await pygame_story.choose(
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
    destination_equipment, destination_items = _destination_storages(
        ctx, destination,
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

async def _apply_field_item_choice(ctx, entries, index: int, container: str) -> None:
    """Apply one transfer/discard choice for an owned field-item stack."""
    chosen = await _choose_field_item_action(ctx, entries, index, container)
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
        price = _sell_price(removed.item_id, removed.quality)
    except (IndexError, KeyError, ValueError):
        ctx.log.add("That equipment is no longer available.")
        return
    ctx.stats.credits += price
    from .. import message_log
    from ..data.quality import quality_mark

    _msg, _runs = message_log.with_runs(
        "Sold ", quality_mark(_equipment_name(entry), entry.quality),
        f" for {price}$.",
    )
    ctx.log.add(_msg, runs=_runs)

def _purchase_spec(item_type: str, item_id: str):
    """Resolve the spec for one buy action."""
    from ..data.ground_armor import find_ground_armor
    from ..data.ground_weapons import find_ground_weapon

    if item_type == "weapon":
        return find_ground_weapon(item_id)
    return find_ground_armor(item_id)

async def _install_purchase(ctx, entry, item_type: str) -> str | None:
    """Equip a fresh purchase; returns the landing role (``None`` =
    weapon chooser cancelled — do not charge)."""
    source = [entry]
    if item_type == "weapon":
        return await _install_weapon_with_chooser(ctx, source, 0, None)
    from ..data.ground_armor import find_ground_armor

    displaced_container = None
    if ctx.equipped_ground_armor.get(find_ground_armor(entry.item_id).slot):
        displaced_container = _preferred_displaced_destination(
            ctx, 1, ground_equipment.ARMORY_STORAGE,
        )
    ground_equipment.install_armor(
        ctx.equipped_ground_armor, source, 0,
        displaced_storage=_displaced_storage_for(
            ctx, displaced_container or ground_equipment.ARMORY_STORAGE,
        ),
        container=ground_equipment.ARMORY_STORAGE,
        displaced_container=displaced_container or ground_equipment.ARMORY_STORAGE,
        strength=_strength(ctx),
    )
    return "ARMOR"


def _purchase_destination_label(destination: str, item_type: str, role) -> str:
    """The buy log's destination — holster-honest for weapons."""
    if destination == "BUY_INSTALL" and item_type == "weapon":
        return "active loadout" if role == "ACTIVE" else "the holstered set"
    return {
        "BUY_INSTALL": "active loadout",
        "BUY_ARMORY": "armory storage",
        "BUY_EXPEDITION": "expedition pack",
    }[destination]


async def _apply_purchase(ctx, action: str) -> None:
    """Complete a validated purchase destination."""
    _destination, item_type, item_id = action.split(":", 2)
    spec = _purchase_spec(item_type, item_id)
    if ctx.stats.credits < spec.price:
        ctx.log.add(f"You need {spec.price}$ to buy {spec.name}.")
        return
    entry = ground_equipment.StoredGroundEquipment(item_type, item_id)
    role = None
    try:
        if _destination == "BUY_INSTALL":
            role = await _install_purchase(ctx, entry, item_type)
            if role is None:
                return
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
                destination_items=_expedition_items(ctx),
            )
        else:
            raise ValueError(f"Unknown purchase destination: {_destination!r}")
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return
    ctx.stats.credits -= spec.price
    label = _purchase_destination_label(_destination, item_type, role)
    ctx.log.add(f"Bought {spec.name} into {label}.")

def _weapon_member(ctx, slot_text: str):
    """``(home_list, index)`` for one ``{class}:{index}`` member address."""
    from ..ground_weapon_sets import class_home

    set_class, index_text = slot_text.split(":")
    home = class_home(
        ctx.equipped_ground_weapons, ctx.holstered_ground_weapons, set_class,
    )
    index = int(index_text)
    if home is None or not 0 <= index < len(home):
        raise IndexError("Invalid weapon set member")
    return home, index

async def _manage_choice(ctx, kind: str, slot, item_id: str) -> str:
    """Open the Store/Sell chooser for one active equipment slot."""
    from .. import pygame_story

    item_type = "weapon" if kind == "MANAGE_WEAPON" else "armor"
    quality = _managed_slot_quality(ctx, kind, slot)
    entry = ground_equipment.StoredGroundEquipment(item_type, item_id, quality)
    label = _equipment_name(entry)
    if kind == "MANAGE_WEAPON":
        options = (
            ("Store in Armory", f"STORE_WEAPON:{slot}"),
            (f"Sell for {_sell_price(item_id, quality)}$", f"SELL_WEAPON:{slot}"),
        )
    else:
        options = (
            ("Store in Armory", f"STORE_ARMOR:{slot}"),
            (f"Sell for {_sell_price(item_id, quality)}$", f"SELL_ARMOR:{slot}"),
        )
    return await pygame_story.choose(
        ctx, title="MANAGE LOADOUT", body=label,
        options=options,
        caption="spacehack - manage loadout", compact=True,
    )

def _apply_manage_choice(ctx, chosen: str) -> None:
    """Apply a Store/Sell choice from the manage-loadout chooser."""
    try:
        if chosen.startswith("STORE_WEAPON:"):
            home, index = _weapon_member(ctx, chosen.split(":", 1)[1])
            ground_equipment.store_weapon(
                home, _armory_storage(ctx), index,
            )
        elif chosen.startswith("STORE_ARMOR:"):
            ground_equipment.store_armor(
                ctx.equipped_ground_armor, _armory_storage(ctx),
                chosen.split(":", 1)[1],
            )
        elif chosen.startswith("SELL_WEAPON:"):
            home, index = _weapon_member(ctx, chosen.split(":", 1)[1])
            removed = ground_equipment.remove_weapon(home, index)
            ctx.stats.credits += _sell_price(removed.item_id, removed.quality)
        elif chosen.startswith("SELL_ARMOR:"):
            removed = ground_equipment.remove_armor(
                ctx.equipped_ground_armor, chosen.split(":", 1)[1],
            )
            ctx.stats.credits += _sell_price(removed.item_id, removed.quality)
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))

def _managed_slot_quality(ctx, kind: str, slot) -> int:
    """The equipped tier of one managed loadout slot."""
    if kind == "MANAGE_WEAPON":
        home, index = _weapon_member(ctx, slot)
        return home[index].quality
    entry = ctx.equipped_ground_armor.get(slot)
    return entry.quality if entry is not None else 0


async def _manage_loadout(ctx, action: str) -> None:
    """Open the Store/Sell chooser for a member of either weapon set."""
    kind, slot_text = action.split(":", 1)
    if kind == "MANAGE_WEAPON":
        home, index = _weapon_member(ctx, slot_text)
        item_id = home[index].weapon_id
    else:
        entry = ctx.equipped_ground_armor.get(slot_text)
        if entry is None:
            return
        item_id = entry.item_id
    chosen = await _manage_choice(ctx, kind, slot_text, item_id)
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    _apply_manage_choice(ctx, chosen)

async def _apply_buy_action(ctx: GameContext, action: str) -> None:
    """Apply an equipment, restock, or consumable purchase action."""
    if action.startswith(("BUY_INSTALL:", "BUY_ARMORY:", "BUY_EXPEDITION:")):
        await _apply_purchase(ctx, action)
        return
    if action.startswith("RESTOCK:"):
        await _restock_bandolier(ctx, action.split(":", 1)[1])
        return
    if action.startswith("BUY_CONSUMABLE:"):
        item_id = action.split(":", 1)[1]
        chosen = await _choose_field_item_destination(ctx, item_id)
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
        await _purchase_field_item(ctx, _parts[2], destination)
        return
    item_type, item_id = action.split(":", 1)
    chosen = await _choose_destination(ctx, item_type.removeprefix("BUY_").lower(), item_id)
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    await _apply_purchase(ctx, chosen)

async def _apply_storage_action(ctx: GameContext, action: str) -> None:
    """Apply one equipment or field-item storage action."""
    prefix, index_text = action.split(":", 1)
    index = int(index_text)
    if prefix == "MANAGE_ARMORY":
        await _apply_container_choice(ctx, _armory_storage(ctx), index, ground_equipment.ARMORY_STORAGE)
    elif prefix == "MANAGE_EXPEDITION":
        await _apply_container_choice(ctx, _expedition_storage(ctx), index, ground_equipment.EXPEDITION_INVENTORY)
    elif prefix == "MANAGE_ARMORY_ITEM":
        await _apply_field_item_choice(ctx, _armory_items(ctx), index, ground_equipment.ARMORY_STORAGE)
    else:
        await _apply_field_item_choice(ctx, _expedition_items(ctx), index, ground_equipment.EXPEDITION_INVENTORY)

async def _apply_pygame_armory_action(ctx: GameContext, action: str, focus: int, selected: int) -> bool:
    """Apply one armory action and keep the modal open."""
    del focus, selected
    if not action:
        return True
    if action.startswith("BUY_"):
        await _apply_buy_action(ctx, action)
        return True
    if action.startswith((
        "MANAGE_ARMORY:", "MANAGE_EXPEDITION:",
        "MANAGE_ARMORY_ITEM:", "MANAGE_EXPEDITION_ITEM:",
    )):
        await _apply_storage_action(ctx, action)
        return True
    if action.startswith(("MANAGE_WEAPON:", "MANAGE_ARMOR:")):
        await _manage_loadout(ctx, action)
        return True
    raise ValueError(f"Unknown armory action: {action!r}")

async def _run_armory_menu(ctx: GameContext, planet_id: str = "") -> None:
    """Show the Phase 2 ground-equipment armory modal."""
    from .. import pygame_split
    from ..time import month_index

    catalog = _catalog_items(planet_id, month_index(ctx))
    mode = "BUY"

    def build_frame():
        return _pygame_armory_frame(ctx, planet_id, mode, catalog=catalog)

    async def apply_action(action, focus, selected):
        nonlocal mode
        if action.startswith("MODE:"):
            requested = action.split(":", 1)[1]
            if requested not in _ARMORY_MODES:
                raise ValueError(f"Unknown armory mode: {requested!r}")
            mode = requested
            return True
        return await _apply_pygame_armory_action(ctx, action, focus, selected)

    await pygame_split.run_interactive(
        ctx, build_frame, apply_action, caption="spacehack - armory",
    )
