"""Ground equipment ownership and loadout mutation.

This module owns the backend contract for ground equipment. The armory
warehouse and expedition pack are deliberately separate containers; the
armory is unlimited while the pack is limited by the player's Strength.
Presentation layers should call these helpers instead of mutating the
GameContext loadout fields directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .data.ground_armor import find_ground_armor
from .data.ground_items import find_ground_ammo, find_ground_consumable
from .data.ground_weapons import find_ground_weapon


ARMORY_STORAGE = "armory"
EXPEDITION_INVENTORY = "expedition"
BASE_EXPEDITION_SLOTS = 4
WEAPON_SLOT_COUNT = 2
_ARMOR_BONUS_FIELDS: tuple[str, ...] = ("ap_bonus", "hit_bonus", "melee_bonus", "hp_bonus")
ITEM_STACK_TYPES: tuple[str, ...] = ("ammo", "consumable")


def sum_armor_bonus(armor_ids: Iterable[str], attr: str) -> int:
    """Sum one numeric armor bonus field across a list of armor ids.

    Skips ``None``/empty ids and unknown catalog ids so a stale save
    entry never raises. ``attr`` must be one of the four cybernetic
    bonus fields on :class:`~spacehack.data.ground_armor.GroundArmorSpec`.
    """
    if attr not in _ARMOR_BONUS_FIELDS:
        raise ValueError(f"unknown armor bonus field: {attr!r}")
    total = 0
    for armor_id in armor_ids:
        if not armor_id:
            continue
        try:
            total += getattr(find_ground_armor(armor_id), attr)
        except KeyError:
            continue
    return total


def sum_armor_defense(armor_ids: Iterable[str]) -> int:
    """Sum flat damage reduction across equipped armor ids."""
    total = 0
    for armor_id in armor_ids:
        if not armor_id:
            continue
        try:
            total += find_ground_armor(armor_id).defense
        except KeyError:
            continue
    return total


def tier_filtered_equipment(
    pool: Iterable[tuple[str, str]], tier: int,
) -> tuple[tuple[str, str], ...]:
    """Return the ``(item_type, item_id)`` loot entries within ``tier``.

    Drops an entry whose item ``tech_level`` exceeds ``tier`` (a T1 NPC
    must never drop T4 gear), and skips unknown catalog ids so a stale
    save entry never raises on kill.
    """
    filtered: list[tuple[str, str]] = []
    for item_type, item_id in pool:
        try:
            if item_type == "weapon":
                tech_level = find_ground_weapon(item_id).tech_level
            else:
                tech_level = find_ground_armor(item_id).tech_level
        except KeyError:
            continue
        if tech_level <= tier:
            filtered.append((item_type, item_id))
    return tuple(filtered)


@dataclass(frozen=True)
class StoredGroundEquipment:
    """One owned ground weapon or armor item."""

    item_type: str
    item_id: str


@dataclass(frozen=True)
class GroundItemStack:
    """One stack of reserve field ammo or consumables.

    ``item_type`` is ``"ammo"`` or ``"consumable"``; ``item_id`` resolves
    through the ground-items catalog. Kept separate from
    :class:`StoredGroundEquipment` so equipment validation stays strict.
    """

    item_type: str
    item_id: str
    quantity: int


@dataclass(frozen=True)
class GroundWeaponInstance:
    """One active ground weapon with its per-instance magazine state.

    ``loaded_ammo`` is ``None`` for infinite/melee weapons and an int
    clamped to ``[0, ammo_capacity]`` for reloadable weapons. Duplicate
    weapon ids are separate instances with independent magazines.
    """

    weapon_id: str
    loaded_ammo: int | None


def expedition_capacity(strength: int) -> int:
    """Return reserve-item capacity for a character's Strength."""
    return BASE_EXPEDITION_SLOTS + max(0, (strength - 10) // 10)


def weapon_hands(weapon_id: str) -> int:
    """Return the logical weapon-slot occupancy for a catalog weapon."""
    return find_ground_weapon(weapon_id).hands


def weapon_instance(weapon_id: str) -> GroundWeaponInstance:
    """Build a fresh instance for a catalog weapon, seeded at full magazine."""
    spec = find_ground_weapon(weapon_id)
    if spec.ammo_capacity <= 0:
        return GroundWeaponInstance(weapon_id, None)
    return GroundWeaponInstance(weapon_id, spec.ammo_capacity)


def weapon_ids(instances: Iterable[GroundWeaponInstance]) -> list[str]:
    """Return the weapon ids from a list of active weapon instances."""
    return [instance.weapon_id for instance in instances]


def parse_weapon_instance(raw) -> GroundWeaponInstance | None:
    """Parse a serialized weapon instance or a legacy string id.

    Legacy ``list[str]`` save entries are seeded at full magazine; a dict
    carrying ``weapon_id`` + ``loaded_ammo`` is validated and clamped to
    ``[0, ammo_capacity]``. Unknown ids return ``None``.
    """
    if isinstance(raw, str):
        try:
            return weapon_instance(raw)
        except KeyError:
            return None
    if not isinstance(raw, dict):
        return None
    weapon_id = raw.get("weapon_id")
    if not isinstance(weapon_id, str) or not weapon_id:
        return None
    try:
        spec = find_ground_weapon(weapon_id)
    except KeyError:
        return None
    if spec.ammo_capacity <= 0:
        return GroundWeaponInstance(weapon_id, None)
    loaded = raw.get("loaded_ammo")
    if loaded is None:
        return GroundWeaponInstance(weapon_id, spec.ammo_capacity)
    try:
        loaded = int(loaded)
    except (TypeError, ValueError):
        return GroundWeaponInstance(weapon_id, spec.ammo_capacity)
    return GroundWeaponInstance(weapon_id, min(max(0, loaded), spec.ammo_capacity))


def weapon_slot_occupancy(weapon_ids: Iterable[str]) -> int:
    """Return logical hand occupancy for an active weapon list."""
    return sum(weapon_hands(weapon_id) for weapon_id in weapon_ids)


def can_fit_weapons(
    instances: Iterable[GroundWeaponInstance], new_weapon_id: str,
) -> bool:
    """Return whether a weapon can fit without replacing active weapons."""
    return weapon_slot_occupancy(weapon_ids(instances)) + weapon_hands(new_weapon_id) <= WEAPON_SLOT_COUNT


def displaced_weapon_count(
    instances: Iterable[GroundWeaponInstance], new_weapon_id: str,
) -> int:
    """Return how many active weapons an equip action must displace."""
    current = tuple(instances)
    return 0 if can_fit_weapons(current, new_weapon_id) else len(current)


def preferred_displacement_container(
    pack_count: int,
    pack_capacity: int,
    displaced_count: int,
    source_container: str,
) -> str:
    """Prefer the expedition pack, falling back to unlimited armory storage.

    Removing an item from the pack frees one slot before displaced gear is
    added back to that same pack.
    """
    available = pack_capacity - pack_count
    if source_container == EXPEDITION_INVENTORY:
        available += 1
    if displaced_count <= available:
        return EXPEDITION_INVENTORY
    return ARMORY_STORAGE


def _validate_entry(entry: StoredGroundEquipment) -> None:
    """Raise ValueError when a stored entry is not a valid catalog item."""
    if entry.item_type == "weapon":
        find_ground_weapon(entry.item_id)
        return
    if entry.item_type == "armor":
        find_ground_armor(entry.item_id)
        return
    raise ValueError(f"Unknown ground equipment type: {entry.item_type!r}")


def validate_storage(entries: Iterable[StoredGroundEquipment]) -> None:
    """Validate every stored entry before a batch mutation."""
    for entry in entries:
        _validate_entry(entry)


def _require_container(container: str) -> None:
    """Validate a storage-container selector."""
    if container not in {ARMORY_STORAGE, EXPEDITION_INVENTORY}:
        raise ValueError(f"Unknown ground equipment container: {container!r}")


def _require_expedition_capacity(entries: list[StoredGroundEquipment], strength: int) -> None:
    """Ensure a proposed expedition container fits the character."""
    if len(entries) > expedition_capacity(strength):
        raise ValueError("Expedition inventory is full")


def _validate_transfer_capacity(
    source: list[StoredGroundEquipment],
    destination: list[StoredGroundEquipment],
    displaced_count: int,
    *,
    destination_container: str,
    strength: int,
) -> None:
    """Validate source removal and destination capacity before mutation."""
    _require_container(destination_container)
    if destination_container != EXPEDITION_INVENTORY:
        return
    final_count = (
        len(source) - 1 + displaced_count
        if source is destination
        else len(destination) + displaced_count
    )
    if final_count > expedition_capacity(strength):
        raise ValueError("Expedition inventory is full")


def _apply_weapon_install(
    equipped_weapons: list[GroundWeaponInstance],
    storage: list[StoredGroundEquipment],
    storage_index: int,
    weapon_id: str,
    displaced_storage: list[StoredGroundEquipment] | None,
    displaced: list[StoredGroundEquipment],
    fits_without_replacement: bool,
) -> None:
    """Apply a previously validated weapon installation."""
    storage.pop(storage_index)
    if displaced_storage is not None:
        displaced_storage.extend(displaced)
    instance = weapon_instance(weapon_id)
    if fits_without_replacement:
        equipped_weapons.append(instance)
    else:
        equipped_weapons[:] = [instance]


def store_weapon(
    equipped_weapons: list[GroundWeaponInstance],
    storage: list[StoredGroundEquipment],
    slot_index: int,
    *,
    container: str = ARMORY_STORAGE,
    strength: int = 10,
) -> StoredGroundEquipment:
    """Move one active weapon into a storage container atomically."""
    _require_container(container)
    if not 0 <= slot_index < len(equipped_weapons):
        raise IndexError("Invalid ground weapon slot")
    instance = equipped_weapons[slot_index]
    entry = StoredGroundEquipment("weapon", instance.weapon_id)
    _validate_entry(entry)
    proposed_storage = [*storage, entry]
    if container == EXPEDITION_INVENTORY:
        _require_expedition_capacity(proposed_storage, strength)
    del equipped_weapons[slot_index]
    storage.append(entry)
    return entry


def store_armor(
    equipped_armor: dict[str, str],
    storage: list[StoredGroundEquipment],
    slot: str,
    *,
    container: str = ARMORY_STORAGE,
    strength: int = 10,
) -> StoredGroundEquipment:
    """Move one active armor piece into a storage container atomically."""
    _require_container(container)
    if slot not in equipped_armor:
        raise KeyError(f"No equipped armor in slot: {slot}")
    entry = StoredGroundEquipment("armor", equipped_armor[slot])
    _validate_entry(entry)
    proposed_storage = [*storage, entry]
    if container == EXPEDITION_INVENTORY:
        _require_expedition_capacity(proposed_storage, strength)
    del equipped_armor[slot]
    storage.append(entry)
    return entry


def add_stored(
    storage: list[StoredGroundEquipment],
    entry: StoredGroundEquipment,
    *,
    container: str,
    strength: int = 10,
) -> StoredGroundEquipment:
    """Add one owned entry to a container after validating capacity."""
    _require_container(container)
    _validate_entry(entry)
    proposed_storage = [*storage, entry]
    if container == EXPEDITION_INVENTORY:
        _require_expedition_capacity(proposed_storage, strength)
    storage.append(entry)
    return entry


def remove_weapon(
    equipped_weapons: list[GroundWeaponInstance],
    slot_index: int,
) -> StoredGroundEquipment:
    """Remove one active weapon and return its owned-equipment entry."""
    if not 0 <= slot_index < len(equipped_weapons):
        raise IndexError("Invalid ground weapon slot")
    instance = equipped_weapons[slot_index]
    entry = StoredGroundEquipment("weapon", instance.weapon_id)
    _validate_entry(entry)
    del equipped_weapons[slot_index]
    return entry


def remove_armor(
    equipped_armor: dict[str, str],
    slot: str,
) -> StoredGroundEquipment:
    """Remove one active armor piece and return its owned-equipment entry."""
    if slot not in equipped_armor:
        raise KeyError(f"No equipped armor in slot: {slot}")
    entry = StoredGroundEquipment("armor", equipped_armor[slot])
    _validate_entry(entry)
    del equipped_armor[slot]
    return entry


def _replace_weapon_slot(
    equipped_weapons: list[GroundWeaponInstance],
    slot_index: int,
    weapon_id: str,
) -> list[StoredGroundEquipment]:
    """Return the active weapons displaced by a slot-targeted swap."""
    current = list(equipped_weapons)
    selected_hands = weapon_hands(weapon_id)
    if selected_hands == 2:
        return [
            StoredGroundEquipment("weapon", instance.weapon_id)
            for instance in current
        ]
    if len(current) == 1 and weapon_hands(current[0].weapon_id) == 2:
        return [StoredGroundEquipment("weapon", current[0].weapon_id)]
    if slot_index < len(current):
        return [StoredGroundEquipment("weapon", current[slot_index].weapon_id)]
    return []


def swap_weapon_from_expedition(
    equipped_weapons: list[GroundWeaponInstance],
    pack: list[StoredGroundEquipment],
    pack_index: int,
    slot_index: int,
    *,
    strength: int = 10,
) -> StoredGroundEquipment:
    """Swap one pack weapon into a requested active weapon slot atomically."""
    selected = _validated_swap_weapon(
        equipped_weapons, pack, pack_index, slot_index,
    )
    displaced = _replace_weapon_slot(equipped_weapons, slot_index, selected.item_id)
    proposed_pack = [
        entry for index, entry in enumerate(pack) if index != pack_index
    ] + displaced
    _require_expedition_capacity(proposed_pack, strength)
    validate_storage(proposed_pack)
    pack[:] = proposed_pack
    _set_swapped_weapon(equipped_weapons, slot_index, selected)
    return selected


def _validated_swap_weapon(
    equipped_weapons: list[GroundWeaponInstance],
    pack: list[StoredGroundEquipment],
    pack_index: int,
    slot_index: int,
) -> StoredGroundEquipment:
    """Validate a pack→loadout weapon swap and return the selected entry."""
    if slot_index not in range(WEAPON_SLOT_COUNT):
        raise IndexError("Invalid ground weapon slot")
    if not 0 <= pack_index < len(pack):
        raise IndexError("Invalid stored ground equipment index")
    selected = pack[pack_index]
    _validate_entry(selected)
    if selected.item_type != "weapon":
        raise ValueError("Stored item is not a weapon")
    if slot_index == 1 and weapon_hands(selected.item_id) == 2:
        raise ValueError("A two-handed weapon must use Weapon 1")
    if slot_index == 1 and equipped_weapons and weapon_hands(equipped_weapons[0].weapon_id) == 2:
        raise ValueError("Weapon 2 is occupied by a two-handed weapon")
    return selected


def _set_swapped_weapon(
    equipped_weapons: list[GroundWeaponInstance],
    slot_index: int,
    selected: StoredGroundEquipment,
) -> None:
    """Install a swapped-in weapon into the requested active slot."""
    selected_hands = weapon_hands(selected.item_id)
    instance = weapon_instance(selected.item_id)
    if selected_hands == 2:
        equipped_weapons[:] = [instance]
    elif len(equipped_weapons) == 1 and weapon_hands(equipped_weapons[0].weapon_id) == 2:
        equipped_weapons[:] = [instance]
    elif slot_index < len(equipped_weapons):
        equipped_weapons[slot_index] = instance
    else:
        equipped_weapons.append(instance)


def swap_armor_from_expedition(
    equipped_armor: dict[str, str],
    pack: list[StoredGroundEquipment],
    pack_index: int,
    slot: str,
    *,
    strength: int = 10,
) -> StoredGroundEquipment:
    """Swap a same-slot pack armor item into an active armor slot atomically."""
    if not 0 <= pack_index < len(pack):
        raise IndexError("Invalid stored ground equipment index")
    selected = pack[pack_index]
    _validate_entry(selected)
    if selected.item_type != "armor":
        raise ValueError("Stored item is not armor")
    selected_slot = find_ground_armor(selected.item_id).slot
    if selected_slot != slot:
        raise ValueError("Stored armor does not fit that slot")
    displaced = (
        [StoredGroundEquipment("armor", equipped_armor[slot])]
        if equipped_armor.get(slot) else []
    )
    proposed_pack = [
        entry for index, entry in enumerate(pack) if index != pack_index
    ] + displaced
    _require_expedition_capacity(proposed_pack, strength)
    validate_storage(proposed_pack)
    pack[:] = proposed_pack
    equipped_armor[slot] = selected.item_id
    return selected


def install_weapon(
    equipped_weapons: list[GroundWeaponInstance],
    storage: list[StoredGroundEquipment],
    storage_index: int,
    *,
    displaced_storage: list[StoredGroundEquipment] | None = None,
    container: str = ARMORY_STORAGE,
    displaced_container: str | None = None,
    strength: int = 10,
) -> StoredGroundEquipment:
    """Install a stored weapon, atomically preserving displaced weapons."""
    _require_container(container)
    if not 0 <= storage_index < len(storage):
        raise IndexError("Invalid stored ground equipment index")
    selected = storage[storage_index]
    _validate_entry(selected)
    if selected.item_type != "weapon":
        raise ValueError("Stored item is not a weapon")
    displaced, fits_without_replacement = _plan_weapon_install(
        equipped_weapons, storage, selected.item_id, displaced_storage,
        container, displaced_container, strength,
    )
    _apply_weapon_install(
        equipped_weapons, storage, storage_index, selected.item_id,
        displaced_storage, displaced, fits_without_replacement,
    )
    return selected


def _plan_weapon_install(
    equipped_weapons: list[GroundWeaponInstance],
    storage: list[StoredGroundEquipment],
    weapon_id: str,
    displaced_storage: list[StoredGroundEquipment] | None,
    container: str,
    displaced_container: str | None,
    strength: int,
) -> tuple[list[StoredGroundEquipment], bool]:
    """Compute weapon displacement and validate the destination."""
    current = list(equipped_weapons)
    fits_without_replacement = can_fit_weapons(current, weapon_id)
    displaced = [] if fits_without_replacement else [
        StoredGroundEquipment("weapon", instance.weapon_id)
        for instance in current
    ]
    if displaced_storage is None and displaced:
        raise ValueError("A destination is required for displaced weapons")
    if displaced and displaced_container is None:
        raise ValueError("A destination container is required for displaced weapons")
    target_storage = displaced_storage if displaced_storage is not None else []
    _validate_transfer_capacity(
        storage, target_storage, len(displaced),
        destination_container=displaced_container or container,
        strength=strength,
    )
    validate_storage([*target_storage, *displaced])
    return displaced, fits_without_replacement


def install_armor(
    equipped_armor: dict[str, str],
    storage: list[StoredGroundEquipment],
    storage_index: int,
    *,
    displaced_storage: list[StoredGroundEquipment] | None = None,
    container: str = ARMORY_STORAGE,
    displaced_container: str | None = None,
    strength: int = 10,
) -> StoredGroundEquipment:
    """Install stored armor, atomically preserving same-slot armor."""
    _require_container(container)
    if not 0 <= storage_index < len(storage):
        raise IndexError("Invalid stored ground equipment index")
    selected = storage[storage_index]
    _validate_entry(selected)
    if selected.item_type != "armor":
        raise ValueError("Stored item is not armor")
    displaced, slot = _plan_armor_install(
        equipped_armor, storage, selected.item_id, displaced_storage,
        container, displaced_container, strength,
    )
    storage.pop(storage_index)
    if displaced_storage is not None:
        displaced_storage.extend(displaced)
    equipped_armor[slot] = selected.item_id
    return selected


def _plan_armor_install(
    equipped_armor: dict[str, str],
    storage: list[StoredGroundEquipment],
    armor_id: str,
    displaced_storage: list[StoredGroundEquipment] | None,
    container: str,
    displaced_container: str | None,
    strength: int,
) -> tuple[list[StoredGroundEquipment], str]:
    """Compute same-slot displacement and validate the destination."""
    slot = find_ground_armor(armor_id).slot
    displaced_id = equipped_armor.get(slot)
    displaced = (
        [StoredGroundEquipment("armor", displaced_id)]
        if displaced_id else []
    )
    if displaced and displaced_storage is None:
        raise ValueError("A destination is required for displaced armor")
    if displaced and displaced_container is None:
        raise ValueError("A destination container is required for displaced armor")
    target_storage = displaced_storage if displaced_storage is not None else []
    _validate_transfer_capacity(
        storage, target_storage, len(displaced),
        destination_container=displaced_container or container,
        strength=strength,
    )
    validate_storage([*target_storage, *displaced])
    return displaced, slot


def transfer_item(
    source: list[StoredGroundEquipment],
    destination: list[StoredGroundEquipment],
    index: int,
    *,
    destination_container: str,
    strength: int,
    destination_items=None,
) -> StoredGroundEquipment:
    """Move one stored item between containers without partial mutation."""
    _require_container(destination_container)
    if not 0 <= index < len(source):
        raise IndexError("Invalid stored ground equipment index")
    entry = source[index]
    _validate_entry(entry)
    proposed = [*destination, entry]
    if destination_container == EXPEDITION_INVENTORY:
        if destination_items is None:
            _require_expedition_capacity(proposed, strength)
        elif len(proposed) + len(destination_items) > expedition_capacity(strength):
            raise ValueError("Expedition inventory is full")
    source.pop(index)
    destination.append(entry)
    return entry


def sell_stored(
    storage: list[StoredGroundEquipment],
    index: int,
) -> StoredGroundEquipment:
    """Remove one stored item for an explicit sale action."""
    if not 0 <= index < len(storage):
        raise IndexError("Invalid stored ground equipment index")
    entry = storage[index]
    _validate_entry(entry)
    return storage.pop(index)


# ---------------------------------------------------------------------------
# Field items (ammo + consumables) — design doc 19, Phase 1
# ---------------------------------------------------------------------------


def item_stack_capacity(item_type: str, item_id: str) -> int:
    """Return the max quantity for one stack of a field item."""
    if item_type == "ammo":
        return find_ground_ammo(item_id).rounds_per_stack
    if item_type == "consumable":
        return find_ground_consumable(item_id).quantity_per_stack
    raise ValueError(f"Unknown field item type: {item_type!r}")


def validate_item_stack(stack: GroundItemStack) -> None:
    """Raise :class:`ValueError` for an invalid item stack."""
    capacity = item_stack_capacity(stack.item_type, stack.item_id)
    if not 0 < stack.quantity <= capacity:
        raise ValueError(
            f"Invalid stack quantity {stack.quantity} for {stack.item_id!r}"
            f" (max {capacity})",
        )


def parse_item_stack(raw) -> GroundItemStack | None:
    """Parse one serialized field-item stack, ignoring or clamping bad values.

    Shared parser policy (save/load and future loot): malformed records
    and unknown catalog ids return ``None``; a non-positive quantity is
    dropped; an over-capacity quantity is clamped to the stack maximum.
    """
    if not isinstance(raw, dict):
        return None
    item_type = raw.get("item_type")
    item_id = raw.get("item_id")
    if item_type not in ITEM_STACK_TYPES or not isinstance(item_id, str) or not item_id:
        return None
    try:
        quantity = int(raw.get("quantity"))
    except (TypeError, ValueError):
        return None
    try:
        capacity = item_stack_capacity(item_type, item_id)
    except KeyError:
        return None
    if quantity <= 0:
        return None
    return GroundItemStack(item_type, item_id, min(quantity, capacity))


def expedition_slot_count(equipment, items) -> int:
    """Return Expedition Pack slot usage across equipment and item stacks."""
    return len(tuple(equipment)) + len(tuple(items))


def item_stack_merge_index(items, stack: GroundItemStack) -> int | None:
    """Return the index of a matching stack with room, else ``None``."""
    capacity = item_stack_capacity(stack.item_type, stack.item_id)
    for index, existing in enumerate(items):
        if existing.item_type != stack.item_type or existing.item_id != stack.item_id:
            continue
        if existing.quantity < capacity:
            return index
    return None


def add_item_stack(
    equipment,
    items,
    stack: GroundItemStack,
    *,
    strength: int,
) -> GroundItemStack | None:
    """Add as much of one field-item stack as the Expedition Pack accepts.

    Matching partial stacks fill first, then new slots are used. The return
    value is an explicit remainder stack when the pack cannot accept the
    complete input; ``None`` means every round/charge was stored. No input
    quantity is silently discarded.
    """
    validate_item_stack(stack)
    remaining = stack.quantity
    capacity = item_stack_capacity(stack.item_type, stack.item_id)
    while remaining > 0:
        partial = item_stack_merge_index(
            items,
            GroundItemStack(stack.item_type, stack.item_id, remaining),
        )
        if partial is not None:
            existing = items[partial]
            room = capacity - existing.quantity
            amount = min(room, remaining)
            items[partial] = GroundItemStack(
                stack.item_type, stack.item_id, existing.quantity + amount,
            )
            remaining -= amount
            continue
        if expedition_slot_count(equipment, items) >= expedition_capacity(strength):
            break
        amount = min(capacity, remaining)
        items.append(GroundItemStack(stack.item_type, stack.item_id, amount))
        remaining -= amount
    if remaining <= 0:
        return None
    return GroundItemStack(stack.item_type, stack.item_id, remaining)


def field_item_capacity(
    equipment,
    items,
    item_type: str,
    item_id: str,
    *,
    strength: int,
    container: str,
) -> int | None:
    """Return how many more charges fit, or ``None`` for Armory Storage."""
    capacity = item_stack_capacity(item_type, item_id)
    if container == ARMORY_STORAGE:
        return None
    if container != EXPEDITION_INVENTORY:
        raise ValueError(f"Unknown field-item container: {container!r}")
    partial_room = sum(
        capacity - stack.quantity
        for stack in items
        if stack.item_type == item_type and stack.item_id == item_id
    )
    free_slots = max(0, expedition_capacity(strength) - expedition_slot_count(equipment, items))
    return partial_room + free_slots * capacity


def add_item_quantity(
    equipment,
    items,
    item_type: str,
    item_id: str,
    quantity: int,
    *,
    strength: int,
    container: str,
) -> None:
    """Add an exact quantity transactionally, splitting it into stacks.

    Armory Storage is unlimited. Expedition Pack capacity is checked before
    mutation, so a failed purchase or transfer cannot partially add charges.
    """
    if quantity <= 0:
        raise ValueError("Field-item quantity must be positive")
    stack_capacity = item_stack_capacity(item_type, item_id)
    available = field_item_capacity(
        equipment, items, item_type, item_id,
        strength=strength, container=container,
    )
    if available is not None and quantity > available:
        raise ValueError("Expedition inventory is full or lacks item capacity")
    remaining = quantity
    while remaining > 0:
        amount = min(stack_capacity, remaining)
        remainder = add_item_stack(
            equipment, items,
            GroundItemStack(item_type, item_id, amount),
            strength=strength,
        )
        if remainder is not None:
            raise ValueError("Field-item capacity changed during insertion")
        remaining -= amount


def transfer_item_stack(
    source_items,
    destination_equipment,
    destination_items,
    index: int,
    *,
    destination_container: str,
    strength: int,
) -> GroundItemStack:
    """Move one complete field-item stack between owned containers."""
    if not 0 <= index < len(source_items):
        raise IndexError("Invalid field-item stack index")
    stack = source_items[index]
    validate_item_stack(stack)
    add_item_quantity(
        destination_equipment, destination_items,
        stack.item_type, stack.item_id, stack.quantity,
        strength=strength, container=destination_container,
    )
    source_items.pop(index)
    return stack


# ---------------------------------------------------------------------------
# Weapon ammo and reload — design doc 19, Phase 3
# ---------------------------------------------------------------------------


def consume_weapon_round(instance: GroundWeaponInstance) -> GroundWeaponInstance:
    """Return the instance after one shot, decrementing its loaded ammo."""
    if instance.loaded_ammo is None:
        return instance
    spec = find_ground_weapon(instance.weapon_id)
    return GroundWeaponInstance(
        instance.weapon_id, max(0, instance.loaded_ammo - spec.ammo_per_shot),
    )


def reload_amount(loaded: int, capacity: int, reserve: int) -> int:
    """Rounds that move from reserve into the magazine (0 if none needed)."""
    return min(max(0, capacity - loaded), reserve)


def matching_ammo_stack_index(items, ammo_type: str) -> int | None:
    """Return the index of the first ammo stack feeding ``ammo_type``."""
    for index, stack in enumerate(items):
        if stack.item_type == "ammo" and find_ground_ammo(stack.item_id).ammo_type == ammo_type:
            return index
    return None


def reserve_ammo_count(items, ammo_type: str) -> int:
    """Total reserve rounds carried for ``ammo_type`` across all stacks."""
    total = 0
    for stack in items:
        if stack.item_type == "ammo" and find_ground_ammo(stack.item_id).ammo_type == ammo_type:
            total += stack.quantity
    return total


def _apply_reload_at(
    equipped_weapons: list[GroundWeaponInstance],
    slot_index: int,
    items,
) -> GroundWeaponInstance:
    """Reload the weapon at ``slot_index`` from the pack; transactional."""
    instance = equipped_weapons[slot_index]
    spec = find_ground_weapon(instance.weapon_id)
    if spec.ammo_capacity <= 0 or spec.ammo_type is None:
        raise ValueError("That weapon cannot be reloaded")
    loaded = instance.loaded_ammo if instance.loaded_ammo is not None else 0
    if loaded >= spec.ammo_capacity:
        raise ValueError("Magazine is already full")
    stack_index = matching_ammo_stack_index(items, spec.ammo_type)
    if stack_index is None:
        raise ValueError(f"No {spec.ammo_type} ammo in the Expedition Pack")
    stack = items[stack_index]
    amount = reload_amount(loaded, spec.ammo_capacity, stack.quantity)
    if amount <= 0:
        raise ValueError("No ammo to load")
    remaining = stack.quantity - amount
    if remaining > 0:
        items[stack_index] = GroundItemStack("ammo", stack.item_id, remaining)
    else:
        del items[stack_index]
    new_instance = GroundWeaponInstance(instance.weapon_id, loaded + amount)
    equipped_weapons[slot_index] = new_instance
    return new_instance


def apply_reload(
    equipped_weapons: list[GroundWeaponInstance],
    slot_index: int,
    items,
) -> GroundWeaponInstance:
    """Reload one active weapon from the Expedition Pack transactionally."""
    if not 0 <= slot_index < len(equipped_weapons):
        raise IndexError("Invalid ground weapon slot")
    return _apply_reload_at(equipped_weapons, slot_index, items)


def reload_slot_for_ammo(
    equipped_weapons: list[GroundWeaponInstance],
    ammo_type: str,
) -> int | None:
    """Return the first equipped weapon slot that can take ``ammo_type``."""
    for slot_index, instance in enumerate(equipped_weapons):
        spec = find_ground_weapon(instance.weapon_id)
        if spec.ammo_capacity <= 0 or spec.ammo_type != ammo_type:
            continue
        loaded = instance.loaded_ammo if instance.loaded_ammo is not None else 0
        if loaded >= spec.ammo_capacity:
            continue
        return slot_index
    return None
